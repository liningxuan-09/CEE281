"""Changed-demand test for the TMC: summary table and figure.

Reads results/tmc_alinea/demand/eval_seeds_101-120/comparison.json (made by tmc_compare.py, see run.sh in
that folder). For each demand combination, ALINEA is compared with no control on the same seeds
(paired differences, 95% paired bootstrap intervals). Writes summary.json, summary.md and
demand_comparison.png next to the comparison file.

    python3 -B tmc_demand.py
"""
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from tmc_compare import DEMAND_MAIN, DEMAND_RAMP

D = Path('results/tmc_alinea/demand/eval_seeds_101-120')
STORAGE = 28            # vehicles that fit on the 200 m ramp road before the stop line
CAPACITY = 2190         # approx. single-lane capacity after the merge (veh/h), for the demand ratio only


def combos():
    """(step, label, mainline veh/h, ramp peak veh/h, no-control case, ALINEA case), baseline in both steps."""
    base = ('A', 'A-ALINEA')
    ramp = [(q, (f'A-R{q}', f'A-ALINEA-R{q}')) for q in DEMAND_RAMP] + [(450, base)]
    main = [(q, (f'A-M{q}', f'A-ALINEA-M{q}')) for q in DEMAND_MAIN] + [(1700, base)]
    out = [('ramp', f'ramp {q}', 1700, q, *c) for q, c in sorted(ramp)]
    out += [('main', f'mainline {q}', q, 450, *c) for q, c in sorted(main)]
    return out


def ci(d):
    return [float(x) for x in np.percentile(np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])]


def summarize(rep):
    t, seeds = rep['per_seed'], [str(s) for s in rep['seeds']]
    rows = []
    for step, label, qm, qr, a, b in combos():
        def v(case, k):
            return np.array([t[case][s][k] for s in seeds], dtype=float)
        row = dict(step=step, label=label, mainline_veh_h=qm, ramp_peak_veh_h=qr, no_control=a, alinea=b,
                   peak_demand_veh_h=qm + qr, peak_demand_over_capacity=(qm + qr) / CAPACITY)
        for case, tag in ((a, 'none'), (b, 'alinea')):
            row[tag] = dict(
                total_delay_veh_h=v(case, 'accumulated_delay_veh_s').mean() / 3600,
                main_delay_veh_h=v(case, 'total_delay_main_veh_s').mean() / 3600,
                ramp_delay_veh_h=v(case, 'total_delay_ramp_veh_s').mean() / 3600,
                stops_at_lane_end=v(case, 'stops_at_lane_end').mean(),
                hard_braking=v(case, 'merges_hard_braking_mainline_follower').mean(),
                max_ramp_queue_mean=v(case, 'max_ramp_queue_veh').mean(),
                max_ramp_queue_worst=float(v(case, 'max_ramp_queue_veh').max()),
                overflow_seeds=int((v(case, 'max_ramp_queue_veh') > STORAGE).sum()),
                spillback_min=v(case, 'ramp_spillback_s').mean() / 60,
                discharge_flow_veh_h=v(case, 'downstream_flow_veh_h').mean(),
                remaining_vehicles=(v(case, 'remaining_on_road') + v(case, 'remaining_ramp_external')).mean(),
            )
        r = v(b, 'mean_release_rate_veh_h')
        row['alinea']['mean_release_rate_veh_h'] = float(np.nanmean(r)) if np.isfinite(r).any() else None
        for k, key in (('total', 'accumulated_delay_veh_s'), ('main', 'total_delay_main_veh_s'),
                       ('ramp', 'total_delay_ramp_veh_s')):
            d = (v(b, key) - v(a, key)) / 3600
            base = v(a, key).mean() / 3600
            row[f'change_{k}'] = dict(mean_veh_h=float(d.mean()), ci95_veh_h=ci(d),
                                      pct=float(100 * d.mean() / base) if base else None,
                                      lower_on_seeds=int((d < 0).sum()), seeds=len(d))
        rows.append(row)
    return rows


def table(rows):
    f = lambda x, n=1: f'{x:,.{n}f}'
    pm = lambda c: (f"{c['mean_veh_h']:+.1f} [{c['ci95_veh_h'][0]:+.1f}, {c['ci95_veh_h'][1]:+.1f}]"
                    + (f" ({c['pct']:+.0f}%)" if c['pct'] is not None else '') + f", lower {c['lower_on_seeds']}/{c['seeds']}")
    lines = []
    for step, title in (('ramp', 'Step 1: ramp demand changed (mainline 1,700 veh/h)'),
                        ('main', 'Step 2: mainline demand changed (ramp peak 450 veh/h)')):
        rs = [r for r in rows if r['step'] == step]
        lines += [f'### {title}', '', '| | ' + ' | '.join(r['label'] + (' (baseline)' if r['no_control'] == 'A' else '') for r in rs) + ' |',
                  '|---|' + '---:|' * len(rs)]
        def add(name, fn):
            lines.append(f'| {name} | ' + ' | '.join(fn(r) for r in rs) + ' |')
        add('Peak demand after the merge (veh/h)', lambda r: f"{r['peak_demand_veh_h']:,} ({100 * r['peak_demand_over_capacity']:.0f}%)")
        add('Total delay, no control / ALINEA (veh·h)', lambda r: f"{f(r['none']['total_delay_veh_h'])} / {f(r['alinea']['total_delay_veh_h'])}")
        add('Mainline delay, no control / ALINEA (veh·h)', lambda r: f"{f(r['none']['main_delay_veh_h'])} / {f(r['alinea']['main_delay_veh_h'])}")
        add('Ramp delay, no control / ALINEA (veh·h)', lambda r: f"{f(r['none']['ramp_delay_veh_h'])} / {f(r['alinea']['ramp_delay_veh_h'])}")
        add('ALINEA − no control: mainline delay [95%]', lambda r: pm(r['change_main']))
        add('ALINEA − no control: ramp delay [95%]', lambda r: pm(r['change_ramp']))
        add('ALINEA − no control: total delay [95%]', lambda r: pm(r['change_total']))
        add('ALINEA mean release rate (veh/h)', lambda r: f"{r['alinea']['mean_release_rate_veh_h']:,.0f}")
        add('Max cars before the stop line, mean / worst: no control', lambda r: f"{r['none']['max_ramp_queue_mean']:.1f} / {r['none']['max_ramp_queue_worst']:.0f}")
        add('Max cars before the stop line, mean / worst: ALINEA', lambda r: f"{r['alinea']['max_ramp_queue_mean']:.1f} / {r['alinea']['max_ramp_queue_worst']:.0f}")
        add(f'Seeds with queue > {STORAGE} cars, no control / ALINEA', lambda r: f"{r['none']['overflow_seeds']} / {r['alinea']['overflow_seeds']}")
        add('Time with cars waiting off the ramp, no control / ALINEA (min)', lambda r: f"{r['none']['spillback_min']:.1f} / {r['alinea']['spillback_min']:.1f}")
        add('Stops at the lane end per run, no control / ALINEA', lambda r: f"{r['none']['stops_at_lane_end']:.1f} / {r['alinea']['stops_at_lane_end']:.1f}")
        add('Hard braking (> 3 m/s²) after merges per run, no control / ALINEA', lambda r: f"{r['none']['hard_braking']:.1f} / {r['alinea']['hard_braking']:.1f}")
        add('Discharge flow at 1.6 km, no control / ALINEA (veh/h)', lambda r: f"{r['none']['discharge_flow_veh_h']:,.0f} / {r['alinea']['discharge_flow_veh_h']:,.0f}")
        add('Vehicles left at the end, no control / ALINEA', lambda r: f"{r['none']['remaining_vehicles']:.1f} / {r['alinea']['remaining_vehicles']:.1f}")
        lines.append('')
    return '\n'.join(lines)


INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
C_NONE, C_ALINEA = '#8a8984', '#6250d6'                # no control: neutral gray; ALINEA: violet
C_MAIN, C_RAMP, C_TOTAL = '#2a78d6', '#eb6834', '#3a3936'


def figure(rows, path):
    plt.rcParams.update({'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2,
                         'xtick.color': INK2, 'ytick.color': INK2, 'axes.spines.top': False,
                         'axes.spines.right': False})
    fig, ax = plt.subplots(3, 2, figsize=(12, 11), sharey='row', facecolor=SURF,
                           gridspec_kw=dict(hspace=0.5, wspace=0.08))
    for j, (step, title, key) in enumerate((('ramp', 'Step 1: ramp peak demand (mainline 1,700)', 'ramp_peak_veh_h'),
                                            ('main', 'Step 2: mainline demand (ramp peak 450)', 'mainline_veh_h'))):
        rs = [r for r in rows if r['step'] == step]
        x = np.arange(len(rs))
        labels = [f"{r[key]:,}" + ('\nbaseline' if r['no_control'] == 'A' else '') + f"\n{100 * r['peak_demand_over_capacity']:.0f}% of cap."
                  for r in rs]
        # Row 1: total delay, no control vs ALINEA.
        a = ax[0, j]
        for tag, col, name, ls in (('none', C_NONE, 'No control', '--'), ('alinea', C_ALINEA, 'ALINEA', '-')):
            y = [r[tag]['total_delay_veh_h'] for r in rs]
            a.plot(x, y, ls, color=col, lw=2, marker='o', ms=8, mec=SURF, mew=2, label=name, zorder=3)
            a.annotate(f'{y[-1]:.0f}', (x[-1], y[-1]), xytext=(8, 0), textcoords='offset points', va='center', color=INK2, fontsize=9)
        a.set_title(title, loc='left', fontsize=11, color=INK, fontweight='bold', pad=22)
        a.text(0, 1.04, 'Total delay (veh·h), mean of 20 seeds', transform=a.transAxes, color=INK2, fontsize=9)
        # Row 2: change with ALINEA (paired, 95% CI).
        a = ax[1, j]; w = 0.26
        for k, (comp, col, name) in enumerate((('main', C_MAIN, 'Mainline'), ('ramp', C_RAMP, 'Ramp'), ('total', C_TOTAL, 'Total'))):
            m = np.array([r[f'change_{comp}']['mean_veh_h'] for r in rs])
            lo = np.array([r[f'change_{comp}']['ci95_veh_h'][0] for r in rs]); hi = np.array([r[f'change_{comp}']['ci95_veh_h'][1] for r in rs])
            a.bar(x + (k - 1) * w, m, w - 0.03, color=col, label=name, zorder=2)
            a.errorbar(x + (k - 1) * w, m, yerr=[m - lo, hi - m], fmt='none', ecolor=INK, elinewidth=1, capsize=3, zorder=3)
        a.axhline(0, color=INK2, lw=1)
        a.text(0, 1.04, 'ALINEA − no control, delay change (veh·h), 95% interval', transform=a.transAxes, color=INK2, fontsize=9)
        # Row 3: ramp queue.
        a = ax[2, j]
        for tag, col, name, ls in (('none', C_NONE, 'No control', '--'), ('alinea', C_ALINEA, 'ALINEA', '-')):
            y = [r[tag]['max_ramp_queue_mean'] for r in rs]
            a.plot(x, y, ls, color=col, lw=2, marker='o', ms=8, mec=SURF, mew=2, label=name, zorder=3)
        a.axhline(STORAGE, color=INK2, lw=1, ls=':')
        a.text(x[0] - 0.45, STORAGE + 1.5, f'ramp road holds {STORAGE} cars', fontsize=8.5, color=INK2, va='bottom')
        a.text(0, 1.04, 'Max cars before the stop line, mean of 20 seeds', transform=a.transAxes, color=INK2, fontsize=9)
        ax[2, j].set_xticks(x, [f"{r[key]:,}\nALINEA queue > {STORAGE}\non {r['alinea']['overflow_seeds']}/20 seeds" for r in rs])
        for i in range(3):
            if i < 2:
                ax[i, j].set_xticks(x, labels)
            ax[i, j].set_xlim(-0.5, len(rs) - 0.5)
            ax[i, j].grid(axis='y', color=GRID, lw=0.8, zorder=0); ax[i, j].set_facecolor(SURF)
        ax[2, j].set_xlabel('mainline veh/h' if step == 'main' else 'ramp peak veh/h', color=INK2)
    ax[0, 0].legend(frameon=False, loc='upper left', handlelength=3.5); ax[1, 0].legend(frameon=False, loc='lower left', ncol=3)
    ax[2, 0].set_ylim(0, None)
    fig.suptitle('TMC changed-demand test: ALINEA vs no control, 20 evaluation seeds (101–120)',
                 x=0.06, ha='left', fontsize=14, fontweight='bold', color=INK)
    fig.savefig(path, dpi=150, facecolor=SURF, bbox_inches='tight')


def main():
    rep = json.loads((D / 'comparison.json').read_text(encoding='utf-8'))
    rows = summarize(rep)
    (D / 'summary.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
    md = table(rows)
    (D / 'summary.md').write_text(md + '\n', encoding='utf-8')
    figure(rows, D / 'demand_comparison.png')
    print(md)


if __name__ == '__main__':
    main()
