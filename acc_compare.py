"""ACC penetration study: all-HDV case A versus 25, 50 and 75% ACC (B25, B50, B75), paired on seeds.

--controller picks the ACC gain: 'stable' (main controller, the Config defaults: Gunter et al. law with
kv = 0.80, string stable) or 'gunter' (their fitted kv = 0.2692, the k_v ablation).

Within a seed the arrivals are identical in every case and the ACC assignments are nested (every
vehicle equipped at 25% is also equipped at 50% and 75%), so the cases differ only in the vehicle mix.
The ramp is unmetered in every case. Each run is recorded (record=True) because the speed-variation
and discharge measures need the trajectories. Nothing is written unless --save is given.

    python3 -B acc_compare.py --seeds 1-4 --controller gunter       # development seeds
    python3 -B acc_compare.py --seeds 101-105 --save part1.json     # evaluation seeds, in parts
    python3 -B acc_compare.py --merge part1.json part2.json --save all.json

Test conditions: --ramp-peak 550 changes the ramp peak (5-35 min, veh/h) in every case; --set KEY=VALUE
overrides any Config field in every case (e.g. --set acc_sensor_delay=0.5 or --set acc_h=1.6881);
--a-from REPORT reuses case A from an earlier report when the overrides do not affect it (ACC-only fields).
"""
import argparse
import json
from dataclasses import replace
from multiprocessing import Pool
from pathlib import Path

import numpy as np

from model import Config, run

CASES = {'A': {}, 'B25': {'acc_share': 0.25}, 'B50': {'acc_share': 0.5}, 'B75': {'acc_share': 0.75}}
CONTROLLERS = {'stable': {}, 'gunter': {'acc_kv': 0.2692}}
METRICS = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s',
           'total_delay_hdv_veh_s', 'total_delay_acc_veh_s',
           'downstream_flow_veh_h', 'discharge_flow_active_veh_h', 'bottleneck_active_bins',
           'merge_area_speed_kmh', 'far_upstream_speed_kmh', 'merge_area_speed_sd_kmh', 'far_upstream_speed_sd_kmh',
           'disturbance_ratio', 'approach_speed_kmh', 'congestion_duration_s', 'max_queue_extent_m', 'queue_reaches_entry',
           'max_main_external', 'max_ramp_external', 'stops_at_lane_end', 'merges', 'merges_with_acc_follower',
           'merges_hard_braking_mainline_follower', 'acc_vehicles_main', 'acc_vehicles_ramp',
           'acc_takeover_episodes', 'acc_takeover_vehicle_s', 'acc_mainline_vehicle_s',
           'hard_braking_vehicle_s_hdv', 'hard_braking_vehicle_s_acc',
           'min_net_gap_m', 'min_net_gap_hdv_follower_m', 'min_net_gap_acc_follower_m', 'min_applied_acceleration_mps2',
           'remaining_on_road', 'offered', 'exited')
# Paired changes against A are reported for these measures (None values drop that seed).
PAIRED = ('accumulated_delay_veh_s', 'total_delay_main_veh_s', 'total_delay_ramp_veh_s', 'downstream_flow_veh_h',
          'discharge_flow_active_veh_h', 'disturbance_ratio', 'far_upstream_speed_sd_kmh', 'congestion_duration_s',
          'stops_at_lane_end')


def one(item):
    seed, name, controller, overrides = item
    s = run(replace(Config(), seed=seed, **CONTROLLERS[controller], **overrides, **CASES[name]), record=True)['summary']
    return seed, name, {k: (float(s[k]) if isinstance(s[k], (float, np.floating)) else s[k]) for k in METRICS}


def parse_seeds(text):
    out = []
    for part in text.split(','):
        a, _, b = part.partition('-')
        out.extend(range(int(a), int(b) + 1) if b else [int(a)])
    return tuple(out)


def paired(table, seeds, cases):
    """Per measure: mean, median and paired bootstrap 95% interval of (case - A) over the seeds."""
    out = {}
    for n in cases:
        if n == 'A':
            continue
        out[n] = {}
        for m in PAIRED:
            pairs = [(table[n][str(s)][m], table['A'][str(s)][m]) for s in seeds]
            d = np.array([x - y for x, y in pairs if x is not None and y is not None], dtype=float)
            if not len(d):
                out[n][m] = None
                continue
            ci = np.percentile(np.random.default_rng(0).choice(d, (5000, len(d))).mean(axis=1), [2.5, 97.5])
            out[n][m] = dict(seeds=int(len(d)), mean_change=float(d.mean()), median_change=float(np.median(d)),
                             mean_change_95ci=[float(ci[0]), float(ci[1])], higher_than_A=int(np.sum(d > 0)))
    return out


def means(table, seeds, cases):
    out = {}
    for n in cases:
        out[n] = {}
        for m in METRICS:
            vals = [table[n][str(s)][m] for s in seeds]
            vals = [float(v) for v in vals if v is not None and not isinstance(v, bool)]
            out[n][m] = float(np.mean(vals)) if vals else None
        out[n]['queue_reaches_entry_seeds'] = int(sum(bool(table[n][str(s)]['queue_reaches_entry']) for s in seeds))
        vals = [table[n][str(s)] for s in seeds]
        if all(v.get('acc_mainline_vehicle_s') for v in vals):
            out[n]['takeover_share_of_acc_time'] = float(np.mean([v['acc_takeover_vehicle_s'] / v['acc_mainline_vehicle_s'] for v in vals]))
    return out


def a_config(cfg):
    """The configuration that case A depends on (everything except the ACC fields)."""
    return json.loads(json.dumps({k: v for k, v in cfg.items() if not k.startswith('acc_')}))


def compare(seeds, cases, controller='stable', workers=4, overrides=None, a_from=None):
    overrides = overrides or {}
    config = replace(Config(), **CONTROLLERS[controller], **overrides).__dict__
    table = {}
    if a_from is not None:
        ref = json.loads(Path(a_from).read_text(encoding='utf-8'))
        if a_config(ref['config']) != a_config(config) or any(str(s) not in ref['per_seed']['A'] for s in seeds):
            raise SystemExit(f'{a_from}: case A has another configuration or lacks some seeds')
        table['A'] = {str(s): ref['per_seed']['A'][str(s)] for s in seeds}
    todo = [n for n in cases if n not in table]
    with Pool(workers) as pool:
        rows = pool.map(one, [(s, n, controller, overrides) for s in seeds for n in todo])
    by = {(s, n): m for s, n, m in rows}
    table.update({n: {str(s): by[(s, n)] for s in seeds} for n in todo})
    table = {n: table[n] for n in cases}
    return dict(seeds=list(seeds), cases={n: CASES[n] for n in cases}, controller=controller,
                controller_overrides=CONTROLLERS[controller], overrides=overrides,
                a_from=str(a_from) if a_from else None, config=config,
                per_seed=table, means=means(table, seeds, cases), paired=paired(table, seeds, cases))


def merge(files):
    reps = [json.loads(Path(f).read_text(encoding='utf-8')) for f in files]
    cases = list(reps[0]['cases'])
    if any(list(r['cases']) != cases for r in reps):
        raise SystemExit('reports cover different cases')
    seeds = [s for r in reps for s in r['seeds']]
    table = {n: {k: v for r in reps for k, v in r['per_seed'][n].items()} for n in cases}
    if any(r.get('controller') != reps[0].get('controller') or r.get('overrides') != reps[0].get('overrides')
           for r in reps):
        raise SystemExit('reports use different controllers or test conditions')
    return dict(seeds=seeds, cases=reps[0]['cases'], controller=reps[0].get('controller'),
                controller_overrides=reps[0].get('controller_overrides'), overrides=reps[0].get('overrides', {}),
                a_from=reps[0].get('a_from'), config=reps[0]['config'], per_seed=table,
                means=means(table, seeds, cases), paired=paired(table, seeds, cases), merged_from=[str(f) for f in files])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--seeds', default='1-4', help='e.g. "101-120" (default: development seeds 1-4)')
    p.add_argument('--cases', default='A,B25,B50,B75', help='comma-separated subset of ' + ', '.join(CASES))
    p.add_argument('--controller', default='stable', choices=list(CONTROLLERS), help='ACC controller (default: stable)')
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--ramp-peak', type=float, metavar='VEH_H', help='ramp demand in the 5-35 min peak (default 450)')
    p.add_argument('--set', action='append', metavar='KEY=VALUE', help='override a Config field in every case')
    p.add_argument('--a-from', type=Path, metavar='REPORT', help='reuse case A from this report')
    p.add_argument('--merge', nargs='+', type=Path, metavar='REPORT', help='combine saved reports instead of running')
    p.add_argument('--save', type=Path, metavar='NEW_FILE', help='write the report as JSON (never overwrites)')
    a = p.parse_args()
    if a.save and a.save.exists():
        p.error('Refusing to overwrite an existing report.')
    if a.merge:
        rep = merge(a.merge)
    else:
        cases = [n.strip() for n in a.cases.split(',')]
        if 'A' not in cases or any(n not in CASES for n in cases):
            p.error('cases must include A and come from ' + ', '.join(CASES))
        overrides = {}
        if a.ramp_peak is not None:
            prof = [tuple(seg) for seg in Config().ramp_profile]
            prof[1] = (prof[1][0], prof[1][1], float(a.ramp_peak))
            overrides['ramp_profile'] = tuple(prof)
        for item in a.set or []:
            key, _, value = item.partition('=')
            if key not in Config.__dataclass_fields__:
                p.error(f'unknown Config field: {key}')
            try:
                overrides[key] = float(value)
            except ValueError:
                overrides[key] = value
        rep = compare(parse_seeds(a.seeds), cases, a.controller, a.workers, overrides, a.a_from)
    cases, seeds = list(rep['cases']), rep['seeds']
    print('seed ' + ''.join(f'{n + " delay":>14}{"down":>6}' for n in cases))
    for s in seeds:
        print(f'{s:4d} ' + ''.join(f"{rep['per_seed'][n][str(s)]['accumulated_delay_veh_s']:14.0f}"
                                   f"{rep['per_seed'][n][str(s)]['downstream_flow_veh_h']:6.0f}" for n in cases))
    print(json.dumps({n: {m: (v and round(v['mean_change'], 3)) for m, v in d.items()} for n, d in rep['paired'].items()}, indent=1))
    if a.save:
        a.save.parent.mkdir(parents=True, exist_ok=True)
        a.save.write_text(json.dumps(rep, indent=2), encoding='utf-8')
        print(f'Saved {a.save}')
    else:
        print('No report was saved.')


if __name__ == '__main__':
    main()
