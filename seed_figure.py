"""Seed-by-seed figure of the TMC test: no control vs. ALINEA on the 20 evaluation seeds (paired).

Reads results/tmc_alinea/eval_seeds_101-120/comparison.json and the seed 9 demo summaries, writes
seed_by_seed.png next to the comparison file.

    python3 -B seed_figure.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = Path('results/tmc_alinea/eval_seeds_101-120')
INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
C_NONE, C_ALINEA, C_BETTER, C_WORSE = '#8a8984', '#6250d6', '#2a78d6', '#eb6834'


def ci(d):
    return np.percentile(np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])


def main():
    r = json.loads((D / 'comparison.json').read_text(encoding='utf-8'))['per_seed']
    seeds = sorted(r['A'], key=lambda s: r['A'][s]['accumulated_delay_veh_s'])           # by no-control delay
    s9 = {k: json.load(open(f'results/{k}/seed9/with_ramp_summary.json')) for k in ('baseline', 'tmc_alinea')}
    plt.rcParams.update({'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2,
                         'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(3, 1, figsize=(12, 12), facecolor=SURF, gridspec_kw=dict(hspace=0.55, height_ratios=[1.3, 1, 1]))
    x = np.arange(len(seeds)); xs9 = -1.5
    labels = ['seed 9\n(demo)'] + seeds
    # (a) total delay per seed, paired
    a = ax[0]
    y0 = np.array([r['A'][s]['accumulated_delay_veh_s'] for s in seeds]) / 3600
    y1 = np.array([r['A-ALINEA'][s]['accumulated_delay_veh_s'] for s in seeds]) / 3600
    a.vlines(x, np.minimum(y0, y1), np.maximum(y0, y1), color=GRID, lw=2.5, zorder=1)
    a.plot(x, y0, 'o', color=C_NONE, ms=8, mec=SURF, mew=1.5, label=f'No control (dashed: mean of 20 seeds, {y0.mean():.1f})', zorder=3)
    a.plot(x, y1, 'o', color=C_ALINEA, ms=8, mec=SURF, mew=1.5, label=f'ALINEA (dashed: mean of 20 seeds, {y1.mean():.1f})', zorder=3)
    b0, b1 = (s9[k]['accumulated_delay_veh_s'] / 3600 for k in ('baseline', 'tmc_alinea'))
    a.vlines(xs9, min(b0, b1), max(b0, b1), color=GRID, lw=2.5)
    a.plot(xs9, b0, 'o', color=C_NONE, ms=8, mec=SURF, mew=1.5); a.plot(xs9, b1, 'o', color=C_ALINEA, ms=8, mec=SURF, mew=1.5)
    a.axvline(-0.75, color=GRID, lw=1)
    a.axhline(y0.mean(), color=C_NONE, ls='--', lw=1); a.axhline(y1.mean(), color=C_ALINEA, ls='--', lw=1)
    a.set_ylabel('Total delay (veh·h)')
    a.set_title(f'(a) Same arrivals, two controls: total delay per seed (seeds sorted by no-control delay; range {y0.min():.0f}–{y0.max():.0f} veh·h)',
                loc='left', fontsize=10.5, color=INK, fontweight='bold')
    a.legend(frameon=False, loc='upper left')
    # (b), (c) paired change per seed
    for a, key, name in ((ax[1], 'accumulated_delay_veh_s', 'total'), (ax[2], 'total_delay_main_veh_s', 'mainline')):
        d = np.array([r['A-ALINEA'][s][key] - r['A'][s][key] for s in seeds]) / 3600
        a.bar(x, d, 0.7, color=np.where(d < 0, C_BETTER, C_WORSE), zorder=2)
        d9 = (s9['tmc_alinea'][key] - s9['baseline'][key]) / 3600
        a.bar(xs9, d9, 0.7, color=C_BETTER if d9 < 0 else C_WORSE, zorder=2)
        a.axvline(-0.75, color=GRID, lw=1); a.axhline(0, color=INK2, lw=1)
        lo, hi = ci(d)
        a.axhspan(lo, hi, xmin=0.08, color=INK2, alpha=0.12, lw=0, zorder=1)
        a.axhline(d.mean(), xmin=0.08, color=INK, lw=1.2, ls='--', zorder=3)
        base = np.mean([r['A'][s][key] for s in seeds]) / 3600
        a.text(0.09, 0.97, f'dashed: mean {d.mean():+.1f} veh·h ({100 * d.mean() / base:+.0f}%), 95% interval [{lo:+.1f}, {hi:+.1f}] (shaded)',
               color=INK2, fontsize=8.5, ha='left', va='top', transform=a.transAxes)
        a.set_ylabel('ALINEA − no control (veh·h)')
        a.set_title(f'({"b" if name == "total" else "c"}) Change in {name} delay per seed: lower on {int((d < 0).sum())} of 20 seeds '
                    f'(blue = ALINEA better, orange = worse)', loc='left', fontsize=10.5, color=INK, fontweight='bold')
    for a in ax:
        a.set_xticks(np.r_[xs9, x], labels, fontsize=8.5); a.set_xlim(xs9 - 0.8, len(seeds) - 0.3)
        a.grid(axis='y', color=GRID, lw=0.8, zorder=0); a.set_facecolor(SURF)
    ax[2].set_xlabel('Evaluation seed (each seed = one random draw of Poisson arrivals at the same demand)')
    fig.suptitle('TMC test seed by seed: no control vs. ALINEA on the same 20 evaluation seeds',
                 x=0.06, ha='left', fontsize=13, fontweight='bold', color=INK)
    fig.savefig(D / 'seed_by_seed.png', dpi=150, facecolor=SURF, bbox_inches='tight')
    print('seed 9 total change %.1f, rank of seed 9 no-control delay among eval seeds: %d of 20 below it' % (
        b1 - b0, int((y0 < b0).sum())))


if __name__ == '__main__':
    main()
