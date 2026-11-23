"""Human-model check: is the effect of 50% ACC the same when the human drivers follow Gipps instead of IDM?

Reads two saved acc_compare.py reports on the same seeds: the main study (A = all IDM drivers, B50 = 50% ACC)
and the Gipps study (run with --set human_model=gipps; its "A" is case C, all Gipps drivers, and its "B50" is
case D, 50% ACC with Gipps drivers). Reports the four cases, the ACC effect under each human model
(B50 - A and D - C) and the difference between the two effects, all paired on seeds with bootstrap 95%
intervals. Writes summary.json, summary.md and gipps_comparison.png into --out; nothing is simulated.

    python3 -B gipps_compare.py
"""
import argparse
import json
from pathlib import Path

import numpy as np

IDM = Path('results/acc_main/eval_seeds_101-120/comparison.json')
GIPPS = Path('results/human_model_gipps/eval_seeds_101-120/comparison.json')
# measure: (label, factor)
MEASURES = {'accumulated_delay_veh_s': ('Total delay (veh·h)', 1 / 3600),
            'total_delay_main_veh_s': ('Mainline delay (veh·h)', 1 / 3600),
            'total_delay_ramp_veh_s': ('Ramp delay (veh·h)', 1 / 3600),
            'congestion_duration_s': ('Congested time (min)', 1 / 60),
            'approach_speed_kmh': ('Speed before the merge (km/h)', 1),
            'far_upstream_speed_sd_kmh': ('Speed variation upstream (km/h)', 1),
            'stops_at_lane_end': ('Stops at the lane end', 1),
            'hard_braking_vehicle_s': ('Hard braking, > 3 m/s² (veh·s)', 1),
            'downstream_flow_veh_h': ('Downstream flow (veh/h)', 1)}


def boot(d):
    d = np.asarray(d, float)
    ci = np.percentile(np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])
    return dict(mean=float(d.mean()), ci=[float(ci[0]), float(ci[1])], positive_seeds=int(np.sum(d > 0)), seeds=len(d))


def column(rep, case, m, seeds):
    if m == 'hard_braking_vehicle_s':
        return np.array([rep['per_seed'][case][str(s)]['hard_braking_vehicle_s_hdv'] +
                         rep['per_seed'][case][str(s)]['hard_braking_vehicle_s_acc'] for s in seeds])
    return np.array([rep['per_seed'][case][str(s)][m] for s in seeds], float) * MEASURES[m][1]


def summarise(idm, gipps):
    seeds = [s for s in idm['seeds'] if s in gipps['seeds']]
    cases = {'A': (idm, 'A'), 'B50': (idm, 'B50'), 'C': (gipps, 'A'), 'D': (gipps, 'B50')}
    out = dict(seeds=seeds, gipps=dict(a=gipps['config']['gipps_a'], b=gipps['config']['gipps_b'],
                                       s_m=gipps['config']['gipps_sm'], tau=gipps['config']['gipps_tau']),
               cases={'A': 'all IDM', 'B50': '50% ACC, others IDM', 'C': 'all Gipps', 'D': '50% ACC, others Gipps'},
               means={}, effect={})
    for m in MEASURES:
        col = {n: column(rep, c, m, seeds) for n, (rep, c) in cases.items()}
        out['means'][m] = {n: float(v.mean()) for n, v in col.items()}
        d_idm, d_gipps = col['B50'] - col['A'], col['D'] - col['C']
        out['effect'][m] = dict(idm=boot(d_idm), gipps=boot(d_gipps), gipps_minus_idm=boot(d_gipps - d_idm),
                                human_model=boot(col['C'] - col['A']))
    return out


def table(s):
    f = lambda z: f'{z["mean"]:+.2f} [{z["ci"][0]:+.2f}, {z["ci"][1]:+.2f}]'
    g = s['gipps']
    lines = [f'Human-model check, {len(s["seeds"])} seeds ({s["seeds"][0]}-{s["seeds"][-1]}). '
             f'Gipps: a_G = {g["a"]} m/s², b_G = -{g["b"]} m/s², s_m = {g["s_m"]} m, tau = {g["tau"]} s.', '',
             'Mean per run | A (all IDM) | B50 (50% ACC + IDM) | C (all Gipps) | D (50% ACC + Gipps)', '---|---|---|---|---']
    for m, (lab, _) in MEASURES.items():
        v = s['means'][m]
        lines.append(f'{lab} | {v["A"]:.2f} | {v["B50"]:.2f} | {v["C"]:.2f} | {v["D"]:.2f}')
    lines += ['', 'Paired change (95% interval) | ACC effect with IDM: B50 − A | ACC effect with Gipps: D − C | '
              'Gipps effect minus IDM effect | Human model alone: C − A', '---|---|---|---|---']
    for m, (lab, _) in MEASURES.items():
        e = s['effect'][m]
        lines.append(f'{lab} | {f(e["idm"])} | {f(e["gipps"])} | {f(e["gipps_minus_idm"])} | {f(e["human_model"])}')
    return '\n'.join(lines) + '\n'


def figure(s, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    ink, muted, grid, blue, orange = '#0b0b0b', '#52514e', '#e1e0d9', '#2a78d6', '#eb6834'
    ms = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s', 'hard_braking_vehicle_s')
    fig, axes = plt.subplots(2, 4, figsize=(12, 5.6))
    for j, m in enumerate(ms):
        ax = axes[0, j]
        v = s['means'][m]
        ax.bar([0, 1, 2.4, 3.4], [v['A'], v['B50'], v['C'], v['D']], color=[orange, blue, orange, blue], width=0.8)
        ax.set_xticks([0, 1, 2.4, 3.4])
        ax.set_xticklabels(['A', 'B50', 'C', 'D'])
        ax.set_title(MEASURES[m][0], fontsize=10, color=ink, loc='left')
        ax.text(0.5, -0.2, 'IDM drivers', transform=ax.get_xaxis_transform(), ha='center', fontsize=8.5, color=muted)
        ax.text(2.9, -0.2, 'Gipps drivers', transform=ax.get_xaxis_transform(), ha='center', fontsize=8.5, color=muted)
        ax = axes[1, j]
        for k, key in enumerate(('idm', 'gipps')):
            d = s['effect'][m][key]
            ax.errorbar(k, d['mean'], yerr=[[d['mean'] - d['ci'][0]], [d['ci'][1] - d['mean']]], fmt='o', color=ink,
                        capsize=4, lw=1.6, ms=6)
        ax.axhline(0, color=muted, lw=0.8)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(['B50 − A\n(IDM)', 'D − C\n(Gipps)'])
        ax.set_xlim(-0.6, 1.6)
        ax.set_title('Effect of 50% ACC', fontsize=10, color=ink, loc='left')
    for ax in axes.ravel():
        ax.grid(axis='y', color=grid, lw=0.6)
        ax.set_axisbelow(True)
        for sp in ('top', 'right'):
            ax.spines[sp].set_visible(False)
    fig.suptitle(f'Human-model check: IDM versus Gipps drivers, without (orange) and with 50% ACC (blue). '
                 f'Means over {len(s["seeds"])} seeds; bottom row: paired change with 95% interval.',
                 fontsize=10.5, color=ink, x=0.01, ha='left')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(path, dpi=160)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--idm', type=Path, default=IDM)
    p.add_argument('--gipps', type=Path, default=GIPPS)
    p.add_argument('--out', type=Path, default=Path('results/human_model_gipps'))
    a = p.parse_args()
    s = summarise(*(json.loads(f.read_text(encoding='utf-8')) for f in (a.idm, a.gipps)))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'summary.json').write_text(json.dumps(s, indent=2), encoding='utf-8')
    (a.out / 'summary.md').write_text(table(s), encoding='utf-8')
    figure(s, a.out / 'gipps_comparison.png')
    print(table(s))


if __name__ == '__main__':
    main()
