"""Figures for the ACC studies. Reads a comparison.json for the 20-seed summary and reruns one seed
(recorded) for the speed maps; --compare draws several controllers' reports side by side. Writes only
the named PNG files.

    python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110
    python3 -B acc_figures.py --compare results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/comparison.json \
        results/acc_main/eval_seeds_101-120/comparison.json --labels "fitted, kv = 0.2692" "string stable, kv = 0.80" \
        --title "Ablation: speed-difference gain k_v (same law)" --out results/acc_ablation_kv/ablation_kv_comparison.png
"""
import argparse
import json
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize

from model import Config, run
from present import SPEED_STOPS, SPEED_MAX_KMH, _segments, busiest_window

INK, INK_2, MUTED, GRID, AXIS, SURFACE = '#0b0b0b', '#52514e', '#898781', '#e1e0d9', '#c3c2b7', '#fcfcfb'
BLUE, ORANGE = '#2a78d6', '#eb6834'
CASES = ('A', 'B25', 'B50', 'B75')
SHARE = {'A': 0, 'B25': 25, 'B50': 50, 'B75': 75}


def style(ax):
    ax.set_facecolor(SURFACE)
    for s in ('top', 'right'):
        ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'):
        ax.spines[s].set_color(AXIS)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis='y', color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_xticks([0, 25, 50, 75])
    ax.set_xticklabels(['A\n0%', 'B25\n25%', 'B50\n50%', 'B75\n75%'])
    ax.set_xlim(-10, 85)


def ci(vals):
    vals = np.asarray(vals, float)
    boot = np.random.default_rng(0).choice(vals, (5000, len(vals))).mean(axis=1)
    return vals.mean(), np.percentile(boot, 2.5), np.percentile(boot, 97.5)


def series(rep, metric, scale=1.0):
    out = []
    for n in CASES:
        vals = [rep['per_seed'][n][str(s)][metric] for s in rep['seeds']]
        vals = [v * scale for v in vals if v is not None]
        out.append((SHARE[n], vals, *ci(vals)))
    return out


def draw(ax, data, color, label=None, dots=True, label_end=False):
    xs = [d[0] for d in data]
    if dots:
        for x, vals, *_ in data:
            jitter = np.random.default_rng(x).uniform(-2.5, 2.5, len(vals))
            ax.scatter(x + jitter, vals, s=9, color=MUTED, alpha=0.45, lw=0, zorder=2)
    m = [d[2] for d in data]
    ax.plot(xs, m, color=color, lw=2, zorder=3, label=label)
    ax.errorbar(xs, m, yerr=[[d[2] - d[3] for d in data], [d[4] - d[2] for d in data]], fmt='o', ms=6,
                color=color, mec=SURFACE, mew=1.5, capsize=0, lw=2, zorder=4)
    if label_end:
        ax.annotate(label, (xs[-1], m[-1]), xytext=(6, 0), textcoords='offset points', va='center',
                    fontsize=8.5, color=INK_2)


LABEL = {'stable': 'main ACC (kv = 0.80, string stable)', 'gunter': 'Gunter et al. fit (kv = 0.2692)'}


def summary_figure(rep, path):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.08, right=0.85, top=0.88, bottom=0.09, hspace=0.45, wspace=0.3)
    fig.text(0.08, 0.955, f"ACC share at the on-ramp merge: {LABEL.get(rep.get('controller'), 'ACC')}, "
             f"seeds {rep['seeds'][0]}-{rep['seeds'][-1]}", fontsize=13, color=INK, weight='bold')
    fig.text(0.08, 0.925, 'Mean with 95% bootstrap interval of the mean; grey dots are single seeds. '
             'Same arrivals in every case; unmetered ramp.', fontsize=9, color=INK_2)
    ax = axes[0][0]
    style(ax)
    draw(ax, series(rep, 'accumulated_delay_veh_s', 1 / 3600), BLUE)
    ax.set_title('Total delay (veh·h)', loc='left', fontsize=10.5, color=INK)
    ax.set_ylim(bottom=0)
    ax = axes[0][1]
    style(ax)
    draw(ax, series(rep, 'downstream_flow_veh_h'), BLUE, 'whole window', dots=False, label_end=True)
    draw(ax, series(rep, 'discharge_flow_active_veh_h'), ORANGE, 'bottleneck active', dots=False, label_end=True)
    ax.set_title('Flow at 1.6 km, after the merge (veh/h)', loc='left', fontsize=10.5, color=INK)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc='lower left')
    ax = axes[1][0]
    style(ax)
    draw(ax, series(rep, 'disturbance_ratio'), BLUE)
    ax.axhline(1.0, color=AXIS, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.text(-8, 1.03, 'grows upstream', fontsize=8, color=MUTED, va='bottom')
    ax.text(-8, 0.97, 'fades upstream', fontsize=8, color=MUTED, va='top')
    ax.set_title('Disturbance ratio (speed SD upstream ÷ SD at merge)', loc='left', fontsize=10.5, color=INK)
    ax.set_ylim(bottom=0)
    ax = axes[1][1]
    style(ax)
    draw(ax, series(rep, 'merge_area_speed_sd_kmh'), BLUE, 'at the merge', dots=False, label_end=True)
    draw(ax, series(rep, 'far_upstream_speed_sd_kmh'), ORANGE, '300-500 m upstream', dots=False, label_end=True)
    ax.set_title('Speed variation, SD of 1 s speeds (km/h)', loc='left', fontsize=10.5, color=INK)
    ax.legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc='lower right')
    ax.set_ylim(bottom=0)
    for a in axes[1]:
        a.set_xlabel('Case and ACC share', fontsize=9, color=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def compare_figure(reps, labels, path, title=None, subtitle=None):
    colors = (BLUE, ORANGE, '#1baf7a')
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.08, right=0.82, top=0.88, bottom=0.09, hspace=0.45, wspace=0.3)
    seeds = reps[0]['seeds']
    fig.text(0.08, 0.955, (title or 'ACC controllers compared') + f', seeds {seeds[0]}-{seeds[-1]}', fontsize=13,
             color=INK, weight='bold')
    fig.text(0.08, 0.925, 'Mean with 95% bootstrap interval of the mean. ' + (subtitle or 'Same arrivals, spacing '
             '(eta, h), takeover and unmetered ramp; only the controller differs.'), fontsize=9, color=INK_2)
    panels = (('accumulated_delay_veh_s', 1 / 3600, 'Total delay (veh·h)'),
              ('downstream_flow_veh_h', 1.0, 'Flow at 1.6 km, after the merge (veh/h)'),
              ('disturbance_ratio', 1.0, 'Disturbance ratio (speed SD upstream ÷ SD at merge)'),
              ('merges_hard_braking_mainline_follower', 1.0, 'Merges after which the follower brakes > 3 m/s²'))
    for k, (ax, (metric, scale, title)) in enumerate(zip(axes.flat, panels)):
        style(ax)
        data = [series(rep, metric, scale) for rep in reps]
        ends = sorted(d[-1][2] for d in data)
        lo, hi = min(min(x[2] for x in d) for d in data), max(max(x[2] for x in d) for d in data)
        apart = all(b - a > 0.06 * max(hi - lo, 1e-9) for a, b in zip(ends, ends[1:]))   # end labels would not overlap
        for d, label, color in zip(data, labels, colors):
            draw(ax, d, color, label, dots=False, label_end=(k % 2 == 1 and apart))
        ax.set_title(title, loc='left', fontsize=10.5, color=INK)
        if metric == 'disturbance_ratio':
            ax.axhline(1.0, color=AXIS, lw=1, ls=(0, (4, 3)), zorder=1)
        ax.set_ylim(bottom=0 if metric != 'downstream_flow_veh_h' else None)
    axes[0][0].legend(frameon=False, fontsize=8.5, labelcolor=INK_2, loc='upper left')
    for a in axes[1]:
        a.set_xlabel('Case and ACC share', fontsize=9, color=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def recorded(item):
    seed, share, overrides = item
    r = run(replace(Config(), seed=seed, acc_share=share, **overrides), record=True)
    return share, [z for z in r['trajectories'] if z['lane'] == 0], r['summary']


def speed_maps(seed, path, overrides=None, label='ACC'):
    with Pool(4) as p:
        res = p.map(recorded, [(seed, SHARE[n] / 100, overrides or {}) for n in CASES])
    c = Config()
    cmap = LinearSegmentedColormap.from_list('speed', SPEED_STOPS)
    tb, xb, t_end = 30.0, 100.0, c.duration
    nt, nx = int(t_end // tb), int(c.road_end // xb)
    fig, axes = plt.subplots(2, 2, figsize=(11, 7.6), sharex=True, sharey=True)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.07, right=0.89, top=0.87, bottom=0.08, hspace=0.25, wspace=0.08)
    fig.text(0.07, 0.95, f'Mainline speed, seed {seed}, {label}: 30 s × 100 m cells', fontsize=13, color=INK,
             weight='bold')
    fig.text(0.07, 0.92, 'Dashed lines: the acceleration lane (1.05-1.5 km) and the end of demand (40 min). '
             'White: no vehicles.', fontsize=9, color=INK_2)
    for ax, (share, tr, s), n in zip(axes.flat, res, CASES):
        sums, cnt = np.zeros((nx, nt)), np.zeros((nx, nt))
        for z in tr:
            i, j = int(z['x_km'] * 1000 // xb), int(z['t_s'] // tb)
            if i < nx and j < nt:
                sums[i, j] += z['v_kmh']
                cnt[i, j] += 1
        speed = np.where(cnt > 0, sums / np.maximum(cnt, 1), np.nan)
        im = ax.imshow(speed, origin='lower', aspect='auto', cmap=cmap, norm=Normalize(0, SPEED_MAX_KMH),
                       extent=[0, t_end / 60, 0, c.road_end / 1000], interpolation='nearest')
        for y in ((c.merge_x - c.acc_length) / 1000, c.merge_x / 1000):
            ax.axhline(y, color=INK, lw=0.8, ls=(0, (4, 3)))
        ax.axvline(c.demand_end / 60, color=MUTED, lw=0.8, ls=(0, (4, 3)))
        ax.set_title(f'{n} ({int(share * 100)}% ACC): total delay {s["accumulated_delay_veh_s"] / 3600:.0f} veh·h',
                     loc='left', fontsize=10, color=INK)
        ax.tick_params(colors=INK_2, labelsize=9)
        for sp in ax.spines.values():
            sp.set_color(AXIS)
    for ax in axes[1]:
        ax.set_xlabel('Simulation time (min)', fontsize=9, color=INK_2)
    for ax in axes[:, 0]:
        ax.set_ylabel('Position (km)', fontsize=9, color=INK_2)
    cax = fig.add_axes([0.905, 0.08, 0.015, 0.79])
    cb = fig.colorbar(im, cax=cax)
    cb.set_label('Speed (km/h)', color=INK_2)
    cb.outline.set_visible(False)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def trajectory_figure(seed, path, overrides=None, label='ACC', cases=('A', 'B50')):
    """Time-space diagrams of the mainline for two cases on one seed, over the same 15 minutes
    (starting 2.5 min before the slowest 10 minutes of the first case), colored by speed."""
    from matplotlib.collections import LineCollection
    with Pool(len(cases)) as p:
        res = p.map(recorded, [(seed, SHARE[n] / 100, overrides or {}) for n in cases])
    c = Config()
    start = max(0.0, busiest_window(dict(trajectories=res[0][1], summary=res[0][2])) - 150.0)
    cmap, norm = LinearSegmentedColormap.from_list('speed', SPEED_STOPS), Normalize(0, SPEED_MAX_KMH)
    fig, axes = plt.subplots(len(cases), 1, figsize=(11, 4.1 * len(cases)), sharex=True)
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.07, right=0.89, top=0.89, bottom=0.07, hspace=0.16)
    fig.text(0.07, 0.955, f'Mainline trajectories, seed {seed}, {label}', fontsize=13, color=INK, weight='bold')
    fig.text(0.07, 0.925, 'One line per vehicle, colored by speed; same arrivals in both cases. Dashed lines: '
             'the acceleration lane (1.05-1.5 km).', fontsize=9, color=INK_2)
    for ax, (share, tr, s), n in zip(axes, res, cases):
        seg, v = _segments([z for z in tr if start - 2 <= z['t_s'] <= start + 902], 0)
        lc = LineCollection(seg, cmap=cmap, norm=norm, linewidths=0.7)
        lc.set_array(v)
        ax.add_collection(lc)
        for y in ((c.merge_x - c.acc_length) / 1000, c.merge_x / 1000):
            ax.axhline(y, color=INK, lw=0.8, ls=(0, (4, 3)))
        ax.set_xlim(start / 60, start / 60 + 15)
        ax.set_ylim(0, c.road_end / 1000)
        ax.set_ylabel('Position (km)', fontsize=9, color=INK_2)
        ax.set_title(f'{n} ({int(share * 100)}% ACC): total delay {s["accumulated_delay_veh_s"] / 3600:.1f} veh·h, '
                     f'{s["congestion_duration_s"] / 60:.1f} min congested at the merge',
                     loc='left', fontsize=10, color=INK)
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=INK_2, labelsize=9)
        for sp in ax.spines.values():
            sp.set_color(AXIS)
    axes[-1].set_xlabel('Simulation time (min)', fontsize=9, color=INK_2)
    cax = fig.add_axes([0.905, 0.07, 0.015, 0.82])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax)
    cb.set_label('Speed (km/h)', color=INK_2)
    cb.outline.set_visible(False)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('report', type=Path, nargs='?')
    p.add_argument('--seed', type=int, default=110)
    p.add_argument('--compare', type=Path, nargs='+', metavar='REPORT')
    p.add_argument('--labels', nargs='+')
    p.add_argument('--out', type=Path)
    p.add_argument('--title')
    p.add_argument('--subtitle')
    p.add_argument('--trajectories', action='store_true',
                   help='Only draw the A vs B50 time-space diagram for --seed (seed<N>_trajectories.png).')
    a = p.parse_args()
    if a.compare:
        reps = [json.loads(f.read_text(encoding='utf-8')) for f in a.compare]
        if any(r['seeds'] != reps[0]['seeds'] for r in reps):
            p.error('reports must cover the same seeds')
        a.out.parent.mkdir(parents=True, exist_ok=True)
        compare_figure(reps, a.labels or [LABEL.get(r.get('controller'), '?') for r in reps], a.out, a.title, a.subtitle)
        print('Saved', a.out)
        return
    rep = json.loads(a.report.read_text(encoding='utf-8'))
    out = a.report.parent
    overrides = rep.get('controller_overrides') or {}
    if a.trajectories:
        target = out.parent / f'seed{a.seed}_trajectories.png'
        trajectory_figure(a.seed, target, overrides, LABEL.get(rep.get('controller'), 'ACC'))
        print('Saved', target)
        return
    summary_figure(rep, out / 'acc_summary.png')
    speed_maps(a.seed, out.parent / f'seed{a.seed}_speed_maps.png', overrides, LABEL.get(rep.get('controller'), 'ACC'))
    print('Saved', out / 'acc_summary.png', 'and', out.parent / f'seed{a.seed}_speed_maps.png')


if __name__ == '__main__':
    main()
