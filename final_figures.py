"""Trajectory figures for the final report, in the style of the mid-report figures.

Every figure shows one example seed with identical arrivals in all panels: the whole road and 0-45 min, one
line per mainline vehicle coloured by speed (one scale for every figure), dashed lines at the acceleration
lane, a dotted line at the end of demand, and total delay and congested time under each panel.

    python3 -B final_figures.py            # about 1 minute; writes results/figures/*.png
    python3 -B final_figures.py --seed 119
"""
import argparse
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize

from model import Config, run
from present import REPORT_FONT, SPEED_MAX_KMH, _speed_cmap, trajectory_panel

SEED = 9        # the demonstration seed (Config default), also used by the demo folders
OUT = Path('results/figures')
CASES = {'A': ({}, 'Baseline: 0% ACC'), 'ALINEA': ({'ramp_control': 'alinea'}, 'ALINEA, all human-driven'),
         'B25': ({'acc_share': 0.25}, '25% ACC, unmetered'), 'B50': ({'acc_share': 0.5}, '50% ACC, unmetered'),
         'B75': ({'acc_share': 0.75}, '75% ACC, unmetered'),
         'B50 fitted': ({'acc_share': 0.5, 'acc_kv': 0.2692}, '50% ACC, fitted $k_v$ = 0.2692')}
FIGURES = {'trajectories_alinea.png': ('A', 'ALINEA'), 'trajectories_acc.png': ('A', 'B25', 'B50', 'B75'),
           'trajectories_kv.png': ('B50', 'B50 fitted')}


def one(item):
    seed, name = item
    r = run(replace(Config(), seed=seed, **CASES[name][0]), record=True)
    return name, dict(summary=r['summary'], trajectories=[z for z in r['trajectories'] if z['lane'] == 0])


def figure(R, names, path, seed):
    """Panels two by two, each drawn by present.trajectory_panel; one colour bar."""
    rows = (len(names) + 1) // 2
    h = 3.8 + 3.4 * (rows - 1)                       # inches; one row is the mid-report figure
    fig = plt.figure(figsize=(6.5, h))
    top, ph, step = 1 - 0.76 / h, 1.86 / h, 3.4 / h   # panel top of row 0, panel height, row pitch (figure fractions)
    for k, n in enumerate(names):
        row, col = divmod(k, 2)
        ax = fig.add_axes([.11 + .39 * col, top - ph - step * row, .34, ph])
        trajectory_panel(ax, R[n], f'({chr(97 + k)}) {CASES[n][1]}')
        if col == 0:
            ax.set_ylabel('Position (km)')
        else:
            ax.tick_params(labelleft=False)
    fig.text(.11, 1 - 0.19 / h, f'Seed {seed} | trajectories | 0-45 min', ha='left', va='top')
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0, SPEED_MAX_KMH), cmap=_speed_cmap()),
                      cax=fig.add_axes([.88, top - ph, .018, ph]))
    cb.set_ticks([0, 30, 60, 90, 120])
    cb.set_label('Speed (km/h)', labelpad=6)
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--seed', type=int, default=SEED)
    a = p.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    with Pool(4) as pool:
        R = dict(pool.map(one, [(a.seed, n) for n in CASES]))
    with plt.rc_context(REPORT_FONT):
        for name, cases in FIGURES.items():
            figure(R, cases, OUT / name, a.seed)
            print('Saved', OUT / name)


if __name__ == '__main__':
    main()
