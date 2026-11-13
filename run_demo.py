"""Run the HDV freeway with ramp demand; write outputs only when --save is requested."""

import argparse
from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path

from model import Config, run


def main(argv=None):
    """Keep simulation, console reporting, and optional export as separate steps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=int, default=Config().seed, help='Demand seed (default: the chosen baseline seed).')
    parser.add_argument('--dt', type=float, default=0.1, help='Integration step in seconds.')
    parser.add_argument('--main', type=float, help='Constant mainline demand in veh/h (default: the Config profile).')
    parser.add_argument('--control', choices=('none', 'alinea'), default='none', help='Ramp control by the TMC.')
    parser.add_argument('--acc-share', type=float, help='Share of ACC vehicles in both streams, 0-1 (default 0).')
    parser.add_argument('--acc-controller', choices=('stable', 'gunter'), default='stable',
                        help='ACC gain: stable (main, kv = 0.80) or gunter (fitted kv = 0.2692, the k_v ablation). '
                             'Default: stable.')
    parser.add_argument('--acc-length', type=float, help='Acceleration lane length in m (default: Config, 450).')
    parser.add_argument('--target-occ', type=float, help='ALINEA target occupancy o* as a fraction (default: Config).')
    parser.add_argument('--dropout', type=float, nargs=2, action='append', metavar=('START', 'END'),
                        help='Lose all detector reports whose interval ends between START and END s (repeatable).')
    parser.add_argument('--miss', type=float, help='Detector defect: probability that a passage is missed.')
    parser.add_argument('--occ-noise', type=float, help='Detector defect: SD of occupancy noise (fraction).')
    parser.add_argument('--report-delay', type=float, help='Detector defect: report delay in s (multiple of 30).')
    parser.add_argument('--signal', type=float, nargs=2, metavar=('GREEN', 'MIN_RED'),
                        help='Meter signal timing: green and minimum red in s (default: Config, 2 and 2).')
    parser.add_argument('--rate-max', type=float, help='ALINEA maximum release rate in veh/h (default: Config).')
    parser.add_argument('--save', action='store_true', help='Explicitly export data and presentation files.')
    parser.add_argument('--gif', action='store_true', help='Also export a GIF; requires --save.')
    parser.add_argument('--validate', action='store_true', help='Run the additional seed/time-step checks.')
    parser.add_argument('--output', type=Path, help='New output directory; requires --save.')
    args = parser.parse_args(argv)
    if (args.gif or args.output is not None) and not args.save:
        parser.error('--gif and --output require --save')

    # Check the destination before doing any work. Never overwrite previous runs.
    destination = None
    if args.save:
        destination = args.output or Path(__file__).parent / 'results' / datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        if destination.exists():
            parser.error(f'Output directory already exists: {destination}')

    # Dense trajectory/replay buffers are unnecessary for console-only runs.
    config = replace(Config(), seed=args.seed, dt=args.dt)
    if args.main is not None:
        config = replace(config, main_profile=((0.0, config.demand_end, args.main),))
    if args.control == 'alinea':
        config = replace(config, ramp_control='alinea')
    if args.acc_length is not None:
        config = replace(config, acc_length=args.acc_length)
    if args.acc_share is not None:
        config = replace(config, acc_share=args.acc_share)
    config = replace(config, **{'stable': {}, 'gunter': {'acc_kv': 0.2692}}[args.acc_controller])
    if args.target_occ is not None:
        config = replace(config, alinea_target_occ=args.target_occ)
    for flag, key in ((args.miss, 'detector_miss_prob'), (args.occ_noise, 'occupancy_noise_sd'),
                      (args.report_delay, 'report_delay')):
        if flag is not None:
            config = replace(config, **{key: flag})
    if args.signal:
        config = replace(config, meter_green=args.signal[0], meter_min_red=args.signal[1])
    if args.rate_max is not None:
        config = replace(config, rate_max=args.rate_max)
    if args.dropout:
        config = replace(config, report_dropout=tuple(tuple(w) for w in args.dropout))
    print('Running with_ramp ...', flush=True)
    results = {'with_ramp': run(config, record=args.save)}
    print(json.dumps(results['with_ramp']['summary'], indent=2))

    # Verification returns an in-memory report, just like the simulation kernel.
    evidence = None
    if args.validate:
        from validate import validate
        evidence = validate()

    # No-save mode stops here: no result directory, plots, CSV or report is created.
    if not args.save:
        print('Finished. No simulation results were saved.')
        return results

    # Export is an explicit user choice. Imports are lazy so console runs need only NumPy.
    destination.mkdir(parents=True)
    for name, result in results.items():
        (destination / f'{name}_raw.json').write_text(json.dumps(result), encoding='utf-8')
    from present import render
    render(results, destination)
    if evidence is not None:
        (destination / 'validation.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    if args.gif:
        from make_gif import make
        make(destination)
    print(f'Saved user-requested outputs to: {destination.resolve()}')
    return results


if __name__ == '__main__':
    main()
