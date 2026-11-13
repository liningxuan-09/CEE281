"""Check that the generated arrivals are Poisson with the intended rates (no simulation needed).

Arrival times come from model.schedule_profile with the same random streams as model.run, so they are
exactly the arrivals of each seed. Pools the 20 evaluation seeds (101-120) at the baseline demand and
draws two panels: cumulative arrivals vs. the target rate (seed 9) and counts per 30 s vs. the
Poisson distribution. Headway (KS) and entry checks are written to arrival_check.json only. Writes results/baseline/arrivals/.

    python3 -B arrival_check.py
"""
import json, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from model import Config, schedule_profile

OUT = Path('results/baseline/arrivals')
SEEDS = range(101, 121)
INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
C_MAIN, C_RAMP, C_THEORY = '#2a78d6', '#eb6834', '#0b0b0b'


def arrivals(seed, c=Config()):
    streams = np.random.SeedSequence(seed).spawn(4)          # same streams as model.run
    return [np.array(schedule_profile(p, np.random.default_rng(s)))
            for p, s in zip((c.main_profile, c.ramp_profile), streams[:2])]


def expected_cum(profile, t):
    return np.array([sum(max(0.0, min(x, b) - a) * q / 3600 for a, b, q in profile) for x in t])


def ks_exp(h, mean):
    """KS statistic of headways against Exp(mean) and its asymptotic p-value."""
    h = np.sort(h); n = len(h); F = 1 - np.exp(-h / mean)
    d = max(np.max(np.arange(1, n + 1) / n - F), np.max(F - np.arange(n) / n))
    lam = (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n)) * d
    p = 2 * sum((-1) ** (k - 1) * math.exp(-2 * k * k * lam * lam) for k in range(1, 101))
    return float(d), float(min(max(p, 0.0), 1.0))


def counts(t, a, b, w=30.0):
    return np.histogram(t, bins=np.arange(a, b + 1e-9, w))[0]


def main():
    c = Config(); OUT.mkdir(parents=True, exist_ok=True)
    main_rate, (r0, r1, ramp_rate) = c.main_profile[0][2], c.ramp_profile[1]
    hm, hr, cm, cr, nm, nr = [], [], [], [], [], []
    for s in SEEDS:
        m, r = arrivals(s, c)
        nm.append(len(m)); nr.append(len(r))
        hm.append(np.diff(m)); rp = r[(r >= r0) & (r < r1)]; hr.append(np.diff(rp))
        cm.append(counts(m, 0, c.main_profile[0][1])); cr.append(counts(r, r0, r1))
    hm, hr, cm, cr = map(np.concatenate, (hm, hr, cm, cr))
    res = dict(
        seeds=[min(SEEDS), max(SEEDS)],
        mainline=dict(target_veh_h=main_rate, expected_vehicles=float(expected_cum(c.main_profile, [2400])[0]),
                      generated_mean=float(np.mean(nm)), headway_mean_s=float(hm.mean()), target_headway_s=3600 / main_rate,
                      ks=ks_exp(hm, 3600 / main_rate), counts30_mean=float(cm.mean()), counts30_var=float(cm.var()),
                      dispersion=float(cm.var() / cm.mean())),
        ramp_peak=dict(target_veh_h=ramp_rate, expected_vehicles=float(expected_cum(c.ramp_profile, [2400])[0]),
                       generated_mean=float(np.mean(nr)), headway_mean_s=float(hr.mean()), target_headway_s=3600 / ramp_rate,
                       ks=ks_exp(hr, 3600 / ramp_rate), counts30_mean=float(cr.mean()), counts30_var=float(cr.var()),
                       dispersion=float(cr.var() / cr.mean())))
    # Seed 9 as simulated (baseline): generated vs. entered.
    import csv
    trips = list(csv.DictReader(open('results/baseline/seed9/with_ramp_trips.csv')))
    m9, r9 = arrivals(9, c)
    sched = np.sort([float(t['scheduled_s']) for t in trips if t['origin'] == '0'])
    assert len(sched) == len(m9) and np.allclose(sched, m9), 'arrivals differ from the saved seed 9 run'
    ent = np.array([(float(t['scheduled_s']), float(t['entry_s'])) for t in trips if t['origin'] == '0'])
    res['seed9_check'] = dict(mainline_arrivals_match_saved_run=True, mainline_vehicles=len(m9), ramp_vehicles=len(r9),
                              entry_wait_mean_s=float((ent[:, 1] - ent[:, 0]).mean()),
                              entry_wait_max_s=float((ent[:, 1] - ent[:, 0]).max()),
                              share_waiting_over_1s=float(np.mean(ent[:, 1] - ent[:, 0] > 1.0)))
    (OUT / 'arrival_check.json').write_text(json.dumps(res, indent=1), encoding='utf-8')

    plt.rcParams.update({'font.size': 10, 'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'xtick.color': INK2,
                         'ytick.color': INK2, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), facecolor=SURF, gridspec_kw=dict(wspace=0.22))
    ax = {(0, 0): axs[0], (1, 0): axs[1]}
    for a in axs:
        a.set_facecolor(SURF); a.grid(color=GRID, lw=0.8, zorder=0)
    # (a) cumulative arrivals, seed 9
    a = ax[(0, 0)]; tt = np.linspace(0, 2400, 400)
    for arr, prof, col, name in ((m9, c.main_profile, C_MAIN, 'Mainline'), (r9, c.ramp_profile, C_RAMP, 'Ramp')):
        a.step(np.r_[0, arr] / 60, np.arange(len(arr) + 1), where='post', color=col, lw=2, label=f'{name}, generated')
        a.plot(tt / 60, expected_cum(prof, tt), color=C_THEORY, lw=1, ls='--')
    a.plot([], [], color=C_THEORY, lw=1, ls='--', label='Target: rate × time')
    a.annotate('ramp 100 → 450 veh/h', (5, expected_cum(c.ramp_profile, [300])[0]), xytext=(8, 40), textcoords='offset points',
               fontsize=8.5, color=INK2, arrowprops=dict(arrowstyle='-', color=INK2, lw=0.8))
    a.annotate('ramp 450 → 0', (35, expected_cum(c.ramp_profile, [2100])[0]), xytext=(-10, 40), textcoords='offset points',
               fontsize=8.5, color=INK2, ha='right', arrowprops=dict(arrowstyle='-', color=INK2, lw=0.8))
    a.set_xlabel('Time (min)'); a.set_ylabel('Cumulative vehicles generated')
    a.set_title('(a) Generated arrivals follow the target rates (seed 9)', loc='left', fontsize=10.5, color=INK, fontweight='bold')
    a.legend(frameon=False, loc='upper left', fontsize=9)
    # (c) counts per 30 s
    a = ax[(1, 0)]
    for cc, col, name, off in ((cm, C_MAIN, 'Mainline', 0), (cr, C_RAMP, 'Ramp peak', 0)):
        k = np.arange(0, cc.max() + 2); lam = cc.mean()
        emp = np.bincount(cc, minlength=len(k))[:len(k)] / len(cc)
        pmf = np.array([math.exp(-lam) * lam ** i / math.factorial(i) for i in k])
        a.bar(k, emp, 0.8, color=col, alpha=0.55, zorder=2, label=f'{name}: mean {lam:.2f}, variance/mean {cc.var() / lam:.2f}')
        a.plot(k, pmf, 'o-', color=col, ms=4, lw=1.2, zorder=3)
    a.plot([], [], 'o-', color=INK2, ms=4, lw=1.2, label='Poisson, same mean')
    a.set_xlabel('Vehicles generated per 30 s'); a.set_ylabel('Share of 30 s intervals')
    a.set_title('(b) Vehicles per 30 s follow the Poisson distribution (20 seeds)', loc='left', fontsize=10.5, color=INK, fontweight='bold')
    a.legend(frameon=False, fontsize=8.5)
    fig.suptitle('Arrival generation check: Poisson arrivals at the baseline demand (mainline 1,700, ramp 100 / 450 / 0 veh/h)',
                 x=0.06, y=1.04, ha='left', fontsize=13, fontweight='bold', color=INK)
    fig.savefig(OUT / 'poisson_arrivals.png', dpi=150, facecolor=SURF, bbox_inches='tight')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
