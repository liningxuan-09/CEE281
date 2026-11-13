"""TMC test: no ramp control (case A) versus ALINEA, paired on the same demand seeds.

The merge bottleneck is sensitive to the timing of individual merges: a small change in when
ramp vehicles are released can strand a vehicle at the end of the acceleration lane, and each
stranding adds a large delay. One seed therefore cannot show whether a controller helps. This
script runs every case on the same seeds (identical arrivals within a seed) and reports the
paired differences. Nothing is written unless --save is given.

    python3 -B tmc_compare.py                              # 13 development seeds
    python3 -B tmc_compare.py --seeds 101-105 --save part1.json
    python3 -B tmc_compare.py --merge part1.json part2.json --save all.json
"""
import argparse
import json
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from model import Config, run

DEV_SEEDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 21, 42)


def main_flat(q):
    """Mainline demand profile: q veh/h for the whole 40 min (baseline 1,700)."""
    return ((0.0, 2400.0, float(q)),)


def ramp_peak(q):
    """Ramp demand profile: 100 veh/h for 5 min, q veh/h for 30 min, then 0 for 5 min (baseline 450)."""
    return ((0.0, 300.0, 100.0), (300.0, 2100.0, float(q)), (2100.0, 2400.0, 0.0))


# Changed-demand test: one demand changed at a time around the baseline (mainline 1,700, ramp peak 450).
DEMAND_RAMP = (350, 550)          # step 1: ramp peak changed, mainline 1,700
DEMAND_MAIN = (1500, 1900)        # step 2: mainline changed, ramp peak 450
CASES = {
    'A': {},                                                   # unmetered all-HDV baseline
    'A-ALINEA': {'ramp_control': 'alinea'},
    'A-ALINEA-fault': {'ramp_control': 'alinea', 'report_dropout': ((1200.0, 1500.0),)},  # 5 min of lost reports
    # Ablation: queue override that protects the street (max rate above this many vehicles before the line).
    'A-ALINEA-ovr20': {'ramp_control': 'alinea', 'ramp_storage': 20},
    'A-ALINEA-ovr28': {'ramp_control': 'alinea', 'ramp_storage': 28},
    # Detector defects (observation tests).
    'A-ALINEA-miss2': {'ramp_control': 'alinea', 'detector_miss_prob': 0.02},
    'A-ALINEA-noise2': {'ramp_control': 'alinea', 'occupancy_noise_sd': 0.02},
    'A-ALINEA-delay30': {'ramp_control': 'alinea', 'report_delay': 30.0},
}
# Changed demand: each demand combination run without control (A-...) and with ALINEA (A-ALINEA-...),
# paired on the same seeds. The baseline combination is A / A-ALINEA.
for _q in DEMAND_RAMP:
    CASES[f'A-R{_q}'] = {'ramp_profile': ramp_peak(_q)}
    CASES[f'A-ALINEA-R{_q}'] = {'ramp_control': 'alinea', 'ramp_profile': ramp_peak(_q)}
for _q in DEMAND_MAIN:
    CASES[f'A-M{_q}'] = {'main_profile': main_flat(_q)}
    CASES[f'A-ALINEA-M{_q}'] = {'ramp_control': 'alinea', 'main_profile': main_flat(_q)}
METRICS = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s', 'stops_at_lane_end',
           'max_ramp_queue_veh', 'ramp_overflow_s', 'downstream_flow_veh_h', 'mean_release_rate_veh_h',
           'remaining_on_road', 'remaining_ramp_external', 'ramp_spillback_s', 'max_ramp_external',
           'detector_count_error_veh', 'detector_occupancy_mae', 'queue_estimate_mae_veh',
           'forecast_mae_veh', 'persistence_mae_veh',
           'merges_hard_braking_mainline_follower', 'min_applied_acceleration_mps2')


def one(item):
    seed, name = item
    s = run(replace(Config(), seed=seed, **CASES[name]), record=False)['summary']
    return seed, name, {k: s[k] for k in METRICS} | {'tmc_modes': s['tmc_modes']}


def parse_seeds(text):
    out = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        out.extend(range(int(a), int(b) + 1) if b else [int(a)])
    return tuple(out)


def paired(table, seeds, cases, ref='A'):
    """Paired differences of total delay against the reference case (default A) on identical seeds."""
    out = {}
    for n in cases:
        if n == ref:
            continue
        d = np.array([table[n][str(s)]['accumulated_delay_veh_s'] - table[ref][str(s)]['accumulated_delay_veh_s']
                      for s in seeds])
        out[n] = dict(
            seeds=len(seeds),
            better_than_ref=int(np.sum(d < 0)),
            mean_delay_change_veh_s=float(d.mean()),
            median_delay_change_veh_s=float(np.median(d)),
            # Paired bootstrap 95% interval of the mean change (fixed resampling seed).
            mean_change_95ci_veh_s=[float(x) for x in np.percentile(
                np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])],
            strandings_total=int(sum(table[n][str(s)]['stops_at_lane_end'] for s in seeds)),
        )
    out[ref] = dict(strandings_total=int(sum(table[ref][str(s)]['stops_at_lane_end'] for s in seeds)))
    return out


def compare(seeds, cases, workers=4, ref='A'):
    with Pool(workers) as pool:
        rows = pool.map(one, [(s, n) for s in seeds for n in cases])
    by = {(s, n): m for s, n, m in rows}
    table = {n: {str(s): by[(s, n)] for s in seeds} for n in cases}
    return dict(seeds=list(seeds), cases={n: CASES[n] for n in cases}, ref=ref, per_seed=table,
                paired=paired(table, seeds, cases, ref))


def merge(files):
    """Combine reports saved for different seed ranges (runs longer than one sitting)."""
    reps = [json.loads(Path(f).read_text(encoding='utf-8')) for f in files]
    cases = list(reps[0]['cases'])
    if any(list(r['cases']) != cases for r in reps):
        raise SystemExit('reports cover different cases')
    seeds = [s for r in reps for s in r['seeds']]
    table = {n: {k: v for r in reps for k, v in r['per_seed'][n].items()} for n in cases}
    ref = reps[0].get('ref', 'A')
    return dict(seeds=seeds, cases=reps[0]['cases'], ref=ref, per_seed=table, paired=paired(table, seeds, cases, ref),
                merged_from=[str(f) for f in files])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--seeds', default=None, help='e.g. "1-11,21,42" (default: the 13 development seeds)')
    p.add_argument('--cases', default='A,A-ALINEA,A-ALINEA-fault,A-ALINEA-ovr20,A-ALINEA-ovr28',
                   help='comma-separated subset of ' + ', '.join(CASES))
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--ref', default='A', help='reference case for the paired differences (default A, no control)')
    p.add_argument('--merge', nargs='+', type=Path, metavar='REPORT', help='combine saved reports instead of running')
    p.add_argument('--save', type=Path, metavar='NEW_FILE', help='write the report as JSON (never overwrites)')
    a = p.parse_args()
    if a.save and a.save.exists():
        p.error('Refusing to overwrite an existing report.')
    if a.merge:
        rep = merge(a.merge)
        seeds, cases = rep['seeds'], list(rep['cases'])
    else:
        seeds = parse_seeds(a.seeds) if a.seeds else DEV_SEEDS
        cases = [n.strip() for n in a.cases.split(',')]
        if a.ref not in cases or any(n not in CASES for n in cases):
            p.error(f'cases must include the reference {a.ref} and come from ' + ', '.join(CASES))
        rep = compare(seeds, cases, a.workers, a.ref)
    print('seed ' + ''.join(f'{n + " delay":>22}{"strand":>7}' for n in cases))
    for s in seeds:
        print(f'{s:4d} ' + ''.join(f"{rep['per_seed'][n][str(s)]['accumulated_delay_veh_s']:22.0f}"
                                   f"{rep['per_seed'][n][str(s)]['stops_at_lane_end']:7d}" for n in cases))
    print(json.dumps(rep['paired'], indent=2))
    if a.save:
        a.save.parent.mkdir(parents=True, exist_ok=True)
        a.save.write_text(json.dumps(rep, indent=2), encoding='utf-8')
        print(f'Saved {a.save}')
    else:
        print('No report was saved.')


if __name__ == '__main__':
    main()
