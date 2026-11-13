"""Bottleneck feasibility check for the all-HDV baseline.

Runs the current Config on a set of development seeds and checks acceptance criteria
fixed in advance. One demand seed is used for the demonstration runs: the seed
in Config (the selected seed) must pass; the other development seeds show how
typical that is. Nothing is written unless --save is given.

    python3 -B feasibility.py                        # print the report
    python3 -B feasibility.py --save results/baseline/feasibility.json

For every development seed it runs:
  * the with-ramp case (demand profile from Config), and
  * a no-ramp control with identical mainline arrivals and ramp demand set to zero.
It also measures the merge discharge flow and repeats the selected seed with dt halved.
"""
import argparse
import json
import os
from dataclasses import replace, asdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from model import Config, run

DEV_SEEDS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 21, 42)
DT_CHECK = (0.05,)

# Acceptance criteria, fixed before the check is run. Target: a clear but local merge
# bottleneck on an otherwise free-flowing freeway, with realistic freeway speeds and no
# ramp vehicle stranded at the end of the acceleration lane.
MIN_SLOWDOWN_KMH = 20.0       # approach at least this much slower than upstream
MIN_RECOVERY_KMH = 10.0       # downstream at least this much faster than the approach
MIN_UPSTREAM_KMH = 85.0
MAX_QUEUE_M = 1000.0
MAX_SLOW_SHARE = 0.05         # mainline 1 s samples below 30 km/h during the evaluation window
MAX_RAMP_WAIT_S = 30.0        # wait at the ramp entrance
CRITERIA = {
    'bottleneck': f'merge approach (last 500 m) at least {MIN_SLOWDOWN_KMH:.0f} km/h slower than upstream (1.5-1.0 km before merge)',
    'recovery': f'downstream (200-500 m after merge) at least {MIN_RECOVERY_KMH:.0f} km/h faster than the approach',
    'local': f'upstream section >= {MIN_UPSTREAM_KMH:.0f} km/h and queue extent <= {MAX_QUEUE_M:.0f} m',
    'realistic': f'at most {MAX_SLOW_SHARE:.0%} of mainline 1 s samples below 30 km/h in the evaluation window',
    'no_stranding': 'no ramp vehicle stops at the end of the acceleration lane',
    'ramp_entry': f'ramp vehicles wait at most {MAX_RAMP_WAIT_S:.0f} s at the ramp entrance',
    'no_ramp_control': 'without ramp demand the approach is never congested and no cell before the merge is below 70 km/h',
    'cleared': 'all vehicles leave before the end of the run',
    'time_step': 'selected seed with dt halved: approach speed within 5 km/h, total delay within 10%',
}


def slow_share(result, c):
    """Share of mainline 1 s samples below 30 km/h in the evaluation window."""
    v = [z['v_kmh'] for z in result['trajectories']
         if z['lane'] == 0 and c.eval_start <= z['t_s'] < c.demand_end]
    return float(np.mean(np.array(v) < 30.0)) if v else None


KEEP = ['offered', 'offered_main', 'offered_ramp', 'exited', 'merges', 'stops_at_lane_end',
        'mean_merge_speed_kmh', 'mean_merge_position_m', 'upstream_speed_kmh', 'approach_speed_kmh',
        'downstream_speed_kmh', 'upstream_speed_sd_kmh', 'approach_speed_sd_kmh', 'downstream_speed_sd_kmh',
        'congestion_duration_s', 'max_queue_extent_m', 'queue_reaches_entry', 'max_main_external',
        'max_ramp_external', 'max_ramp_onroad', 'mean_ramp_wait_s', 'max_ramp_wait_s',
        'downstream_flow_veh_h', 'completed_mean_delay_s', 'accumulated_delay_veh_s',
        'brake_clipped_vehicle_steps', 'min_net_gap_m', 'remaining_on_road', 'pre_merge_min_cell_kmh',
        'remaining_main_external', 'remaining_ramp_external']


def _task(args):
    kind, seed, overrides = args
    c = replace(Config(), seed=seed, **overrides)
    result = run(c, record=True)
    s = result['summary']
    row = {k: s.get(k) for k in KEEP}
    row.update(kind=kind, seed=seed, dt=c.dt, slow30_share=slow_share(result, c))
    return row


def check_seed(ramp, noramp):
    left = ramp['remaining_on_road'] + ramp['remaining_main_external'] + ramp['remaining_ramp_external']
    up, app, down = ramp['upstream_speed_kmh'], ramp['approach_speed_kmh'], ramp['downstream_speed_kmh']
    ok = up is not None and app is not None and down is not None
    res = {
        'bottleneck': ok and up - app >= MIN_SLOWDOWN_KMH,
        'recovery': ok and down - app >= MIN_RECOVERY_KMH,
        'local': ok and up >= MIN_UPSTREAM_KMH and ramp['max_queue_extent_m'] <= MAX_QUEUE_M,
        'realistic': ramp['slow30_share'] is not None and ramp['slow30_share'] <= MAX_SLOW_SHARE,
        'no_stranding': ramp['stops_at_lane_end'] == 0,
        'ramp_entry': (ramp['max_ramp_wait_s'] or 0.0) <= MAX_RAMP_WAIT_S,
        'no_ramp_control': (noramp['congestion_duration_s'] == 0 and noramp['pre_merge_min_cell_kmh'] is not None
                            and noramp['pre_merge_min_cell_kmh'] >= 70),
        'cleared': left == 0,
    }
    res['all'] = all(res.values())
    return res


def feasibility(seeds=DEV_SEEDS, workers=None):
    c = Config()
    seeds = tuple(dict.fromkeys(tuple(seeds) + (c.seed,)))
    no_ramp = dict(ramp_profile=((0.0, c.demand_end, 0.0),))
    tasks = ([('ramp', s, {}) for s in seeds] + [('noramp', s, no_ramp) for s in seeds]
             + [('dt', c.seed, {'dt': dt}) for dt in DT_CHECK])
    with Pool(workers or min(4, os.cpu_count() or 1)) as pool:
        rows = []
        for row in pool.imap_unordered(_task, tasks):
            rows.append(row)
            print(f"  done: {row['kind']:<6} seed {row['seed']:<3} dt {row['dt']}", flush=True)
    ramp = {r['seed']: r for r in rows if r['kind'] == 'ramp'}
    noramp = {r['seed']: r for r in rows if r['kind'] == 'noramp'}
    per_seed = {s: check_seed(ramp[s], noramp[s]) for s in seeds}
    base = ramp[c.seed]
    dt_rows = [r for r in rows if r['kind'] == 'dt']
    dt_ok = all(abs(r['approach_speed_kmh'] - base['approach_speed_kmh']) < 5
                and abs(r['accumulated_delay_veh_s'] / base['accumulated_delay_veh_s'] - 1) < 0.10
                for r in dt_rows)
    report = {
        'config': asdict(c),
        'selected_seed': c.seed,
        'development_seeds': list(seeds),
        'criteria': CRITERIA,
        'per_seed': {str(s): {'checks': per_seed[s], 'with_ramp': ramp[s], 'no_ramp': noramp[s]} for s in seeds},
        'share_of_seeds_passing': sum(v['all'] for v in per_seed.values()) / len(seeds),
        'time_step': {'seed': c.seed, 'base_dt': c.dt, 'runs': dt_rows, 'passed': dt_ok},
        'passed': bool(per_seed[c.seed]['all'] and dt_ok),
        'interpretation': 'Development check of the baseline design, not empirical validation.',
    }
    return report


def print_report(rep):
    print('\nseed | up/approach/down km/h | <30 km/h | queue m | merges | lane-end stops | max ramp wait s | '
          'discharge veh/h | no-ramp slowest cell | pass')
    fmt = lambda x: '-' if x is None else f'{x:.0f}'
    for s, v in rep['per_seed'].items():
        r, n, k = v['with_ramp'], v['no_ramp'], v['checks']
        mark = ' *' if int(s) == rep['selected_seed'] else '  '
        print(f"{s:>4}{mark}| {fmt(r['upstream_speed_kmh'])}/{fmt(r['approach_speed_kmh'])}/{fmt(r['downstream_speed_kmh'])}"
              f" | {r['slow30_share']:.1%} | {r['max_queue_extent_m']:.0f} | {r['merges']} | {r['stops_at_lane_end']}"
              f" | {fmt(r['max_ramp_wait_s'])} | {fmt(r['downstream_flow_veh_h'])} | {fmt(n['pre_merge_min_cell_kmh'])}"
              f" | {'yes' if k['all'] else 'NO ' + ','.join(x for x, ok in k.items() if not ok and x != 'all')}")
    print(f"\n* selected seed {rep['selected_seed']}")
    print(f"Development seeds meeting all criteria: {rep['share_of_seeds_passing']:.0%}")
    print(f"Time-step check passed: {rep['time_step']['passed']}")
    print(f"OVERALL (selected seed and time step): {'PASSED' if rep['passed'] else 'NOT PASSED'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--save', type=Path, metavar='NEW_FILE', help='Save the JSON report (never overwrites).')
    parser.add_argument('--seeds', type=int, nargs='+', default=list(DEV_SEEDS), help='Development seeds.')
    args = parser.parse_args()
    if args.save and args.save.exists():
        parser.error('Refusing to overwrite an existing report.')
    rep = feasibility(tuple(args.seeds))
    print_report(rep)
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(rep, indent=2), encoding='utf-8')
        print(f'Saved {args.save}')


if __name__ == '__main__':
    main()
