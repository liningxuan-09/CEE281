"""Time-step sensitivity: the three main cases rerun with a smaller integration step, paired on seeds.

Cases: A (all human-driven, no control), ALINEA (ramp metering) and B50 (50% ACC). Everything else is
unchanged: the arrivals are generated before the simulation, so they are identical for every step, and all
timing windows (reports, signal cycle, evaluation window) are defined in seconds. Individual merges are
discrete events and are expected to differ between steps; the check is whether the 20-seed results and the
differences between cases stay the same. Nothing is written unless --save or --out is given.

    python3 -B dt_check.py --dt 0.05 --seeds 101-104 --save part.json     # run (in parts)
    python3 -B dt_check.py --merge part1.json part2.json --save all.json
    python3 -B dt_check.py --summary dt_0.1.json dt_0.05.json --out results/time_step
"""
import argparse
import json
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from model import Config, run

CASES = {'A': {}, 'ALINEA': {'ramp_control': 'alinea'}, 'B50': {'acc_share': 0.5}}
METRICS = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s', 'congestion_duration_s',
           'stops_at_lane_end', 'downstream_flow_veh_h', 'approach_speed_kmh', 'merges', 'min_net_gap_m', 'offered', 'exited')
LABEL = {'accumulated_delay_veh_s': 'Total delay (veh·h)', 'total_delay_main_veh_s': 'Mainline delay (veh·h)',
         'total_delay_ramp_veh_s': 'Ramp delay (veh·h)', 'congestion_duration_s': 'Congested time (min)',
         'stops_at_lane_end': 'Stops at the lane end', 'downstream_flow_veh_h': 'Downstream flow (veh/h)'}
SCALE = {'accumulated_delay_veh_s': 1 / 3600, 'total_delay_main_veh_s': 1 / 3600, 'total_delay_ramp_veh_s': 1 / 3600,
         'congestion_duration_s': 1 / 60}


def one(item):
    seed, name, dt = item
    s = run(replace(Config(), seed=seed, dt=dt, **CASES[name]), record=True)['summary']
    return seed, name, {k: (None if s[k] is None else float(s[k])) for k in METRICS}


def parse_seeds(text):
    out = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        out.extend(range(int(a), int(b) + 1) if b else [int(a)])
    return tuple(out)


def boot(d):
    """Mean and paired bootstrap 95% interval of the per-seed values d (fixed resampling seed)."""
    d = np.asarray(d, float)
    ci = np.percentile(np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])
    return dict(mean=float(d.mean()), ci=[float(ci[0]), float(ci[1])], positive_seeds=int(np.sum(d > 0)), seeds=len(d))


def summary(coarse, fine):
    seeds = [s for s in coarse['seeds'] if s in fine['seeds']]
    col = lambda rep, case, m: np.array([rep['per_seed'][case][str(s)][m] for s in seeds]) * SCALE.get(m, 1)
    out = dict(dt=[coarse['dt'], fine['dt']], seeds=seeds, levels={}, step_effect={}, case_differences={})
    for m in LABEL:
        out['levels'][m] = {c: [float(col(coarse, c, m).mean()), float(col(fine, c, m).mean())] for c in CASES}
        # Effect of the step on each case: fine minus coarse, paired on seeds.
        out['step_effect'][m] = {c: boot(col(fine, c, m) - col(coarse, c, m)) for c in CASES}
        # The comparisons the project reports (case minus A) at each step, and how much the step moves them.
        out['case_differences'][m] = {}
        for c in ('ALINEA', 'B50'):
            dc, df = col(coarse, c, m) - col(coarse, 'A', m), col(fine, c, m) - col(fine, 'A', m)
            out['case_differences'][m][c] = dict(coarse=boot(dc), fine=boot(df), change=boot(df - dc))
    return out


def table(s):
    a, b = s['dt']
    lines = [f'Time-step sensitivity, {len(s["seeds"])} seeds ({s["seeds"][0]}-{s["seeds"][-1]}): dt = {a} s versus {b} s', '',
             f'Mean per run | case | dt = {a} | dt = {b} | change (95% interval)', '---|---|---|---|---']
    for m, lab in LABEL.items():
        for c in CASES:
            x, y = s['levels'][m][c]
            e = s['step_effect'][m][c]
            pct = f', {100 * e["mean"] / x:+.0f}%' if abs(x) > 1e-9 else ''
            lines.append(f'{lab} | {c} | {x:.2f} | {y:.2f} | {e["mean"]:+.2f} [{e["ci"][0]:+.2f}, {e["ci"][1]:+.2f}]{pct}')
    lines += ['', f'Difference from case A | case | dt = {a} (95% interval) | dt = {b} (95% interval) | shift caused by the step', '---|---|---|---|---']
    f = lambda z: f'{z["mean"]:+.2f} [{z["ci"][0]:+.2f}, {z["ci"][1]:+.2f}]'
    for m, lab in LABEL.items():
        for c in ('ALINEA', 'B50'):
            z = s['case_differences'][m][c]
            lines.append(f'{lab} | {c} − A | {f(z["coarse"])} | {f(z["fine"])} | {f(z["change"])}')
    return '\n'.join(lines) + '\n'


def figure(s, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ink, muted, grid, blue, orange = '#0b0b0b', '#52514e', '#e1e0d9', '#2a78d6', '#eb6834'
    a, b = s['dt']
    ms = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s')
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), sharey=True)
    for ax, m in zip(axes, ms):
        for k, c in enumerate(('ALINEA', 'B50')):
            z = s['case_differences'][m][c]
            for off, key, col, lab in ((-0.12, 'coarse', blue, f'dt = {a} s'), (0.12, 'fine', orange, f'dt = {b} s')):
                d = z[key]
                ax.errorbar(k + off, d['mean'], yerr=[[d['mean'] - d['ci'][0]], [d['ci'][1] - d['mean']]], fmt='o', color=col,
                            capsize=4, lw=1.6, ms=6, label=lab if k == 0 else None)
        ax.axhline(0, color=muted, lw=0.8)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['ALINEA − A', 'B50 − A'])
        ax.set_xlim(-0.6, 1.6)
        ax.set_title(LABEL[m].replace(' (veh·h)', ''), fontsize=11, color=ink, loc='left')
        ax.grid(axis='y', color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
    axes[0].set_ylabel('Change against case A (veh·h)')
    axes[0].legend(frameon=False, fontsize=9, loc='best')
    fig.suptitle(f'Time-step check: case differences with dt = {a} s and {b} s (mean and 95% interval, {len(s["seeds"])} seeds)',
                 fontsize=11, color=ink, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=160)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--dt', type=float, default=0.05, help='integration step in s (default 0.05; the model uses 0.1)')
    p.add_argument('--seeds', default='1-2')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--merge', nargs='+', type=Path, metavar='REPORT')
    p.add_argument('--summary', nargs=2, type=Path, metavar=('COARSE', 'FINE'), help='compare two saved reports')
    p.add_argument('--out', type=Path, metavar='FOLDER', help='with --summary: write summary.json, summary.md and the figure')
    p.add_argument('--save', type=Path, metavar='NEW_FILE', help='write the report as JSON (never overwrites)')
    a = p.parse_args()
    if a.summary:
        s = summary(*(json.loads(f.read_text(encoding='utf-8')) for f in a.summary))
        print(table(s))
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / 'summary.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
            (a.out / 'summary.md').write_text(table(s), encoding='utf-8')
            figure(s, a.out / 'time_step_comparison.png')
        return
    if a.save and a.save.exists():
        p.error('Refusing to overwrite an existing report.')
    if a.merge:
        reps = [json.loads(f.read_text(encoding='utf-8')) for f in a.merge]
        if any(r['dt'] != reps[0]['dt'] for r in reps):
            p.error('reports use different steps')
        rep = dict(dt=reps[0]['dt'], seeds=[s for r in reps for s in r['seeds']], cases=CASES,
                   per_seed={c: {k: v for r in reps for k, v in r['per_seed'][c].items()} for c in CASES},
                   merged_from=[str(f) for f in a.merge])
    else:
        seeds = parse_seeds(a.seeds)
        with Pool(a.workers) as pool:
            rows = pool.map(one, [(s, c, a.dt) for s in seeds for c in CASES])
        rep = dict(dt=a.dt, seeds=list(seeds), cases=CASES,
                   per_seed={c: {str(s): m for s, n, m in rows if n == c} for c in CASES})
    for c in CASES:
        print(c, 'mean total delay (veh·h):', round(float(np.mean([v['accumulated_delay_veh_s'] for v in rep['per_seed'][c].values()])) / 3600, 2))
    if a.save:
        a.save.parent.mkdir(parents=True, exist_ok=True)
        a.save.write_text(json.dumps(rep, indent=2), encoding='utf-8')
        print(f'Saved {a.save}')
    else:
        print('No report was saved.')


if __name__ == '__main__':
    main()
