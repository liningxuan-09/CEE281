"""Summary figures for the ACC studies, drawn from saved comparison.json files (nothing is simulated).

    python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json          # acc_summary.png
    python3 -B acc_figures.py --compare A.json B.json --labels "a" "b" --title "..." --subtitle "..." --out file.png

Trajectory figures are drawn by final_figures.py.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


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
    ax.set_xticklabels(['0%\n(case A)', '25%\n(B25)', '50%\n(B50)', '75%\n(B75)'])
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
    fig.subplots_adjust(left=0.08, right=0.85, top=0.88, bottom=0.09, hspace=0.55, wspace=0.3)
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
    draw(ax, series(rep, 'downstream_flow_veh_h'), BLUE, 'minutes 5-40', dots=False, label_end=True)
    draw(ax, series(rep, 'discharge_flow_active_veh_h'), ORANGE, 'while the merge is congested', dots=False, label_end=True)
    ax.set_title('Flow leaving the merge, at 2.6 km (veh/h)', loc='left', fontsize=10.5, color=INK)
    ax = axes[1][0]
    style(ax)
    draw(ax, series(rep, 'disturbance_ratio'), BLUE)
    ax.axhline(1.0, color=AXIS, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.set_title('Speed variation upstream ÷ at the merge\n(above the dashed line: slowdowns grow upstream)', loc='left', fontsize=10.5, color=INK)
    ax.set_ylim(bottom=0)
    ax = axes[1][1]
    style(ax)
    draw(ax, series(rep, 'merge_area_speed_sd_kmh'), BLUE, 'at the merge', dots=False, label_end=True)
    draw(ax, series(rep, 'far_upstream_speed_sd_kmh'), ORANGE, '300-500 m upstream', dots=False, label_end=True)
    ax.set_title('Speed variation (standard deviation of speed, km/h)', loc='left', fontsize=10.5, color=INK)
    ax.set_ylim(bottom=0)
    for a in axes.flat:
        a.set_xlabel('Share of vehicles with ACC', fontsize=9, color=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def compare_figure(reps, labels, path, title=None, subtitle=None):
    colors = (BLUE, ORANGE, '#1baf7a')
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2))
    fig.patch.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.08, right=0.82, top=0.88, bottom=0.14, hspace=0.55, wspace=0.3)
    seeds = reps[0]['seeds']
    fig.text(0.08, 0.955, (title or 'Comparison') + f', seeds {seeds[0]}-{seeds[-1]}', fontsize=13,
             color=INK, weight='bold')
    fig.text(0.08, 0.925, 'Mean with 95% bootstrap interval of the mean. ' + (subtitle or 'Same seeds and arrivals in every line.'), fontsize=9, color=INK_2)
    panels = (('accumulated_delay_veh_s', 1 / 3600, 'Total delay (veh·h)'),
              ('downstream_flow_veh_h', 1.0, 'Flow leaving the merge, at 2.6 km (veh/h)'),
              ('disturbance_ratio', 1.0, 'Speed variation upstream ÷ at the merge\n(above the dashed line: slowdowns grow upstream)'),
              ('merges_hard_braking_mainline_follower', 1.0, 'Merges per run with hard braking behind (> 3 m/s²)'))
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
    fig.legend(*axes[0][0].get_legend_handles_labels(), frameon=False, fontsize=9.5, labelcolor=INK_2, loc='lower center', ncol=len(labels))
    for a in axes.flat:
        a.set_xlabel('Share of vehicles with ACC', fontsize=9, color=INK_2)
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('report', type=Path, nargs='?')
    p.add_argument('--compare', type=Path, nargs='+', metavar='REPORT')
    p.add_argument('--labels', nargs='+')
    p.add_argument('--out', type=Path)
    p.add_argument('--title')
    p.add_argument('--subtitle')
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
    summary_figure(rep, out / 'acc_summary.png')
    print('Saved', out / 'acc_summary.png')


if __name__ == '__main__':
    main()
