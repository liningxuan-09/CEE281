"""Run additional development checks in memory; saving is optional."""

import argparse
from dataclasses import replace
import json
from pathlib import Path

from model import Config, run


def validate():
    """Compare fixed demand schedules across integration steps and selected seeds."""
    results = []
    # Timing windows remain unchanged in seconds when the numerical step changes.
    for seed, dt in [(21, 0.1), (21, 0.05), (21, 0.025), (7, 0.1), (42, 0.1)]:
        # record=True so the section speeds that identify the bottleneck are available.
        summary = run(replace(Config(), seed=seed, dt=dt), record=True)['summary']
        results.append(summary)
        speeds = '/'.join('n/a' if summary.get(k) is None else f"{summary[k]:.0f}"
                          for k in ('upstream_speed_kmh', 'approach_speed_kmh', 'downstream_speed_kmh'))
        print(f"Checked seed={seed}, dt={dt}: {summary['exited']}/{summary['offered']} exited, "
              f"{summary['merges']} merges, upstream/approach/downstream {speeds} km/h", flush=True)

    # Merge events are discrete; explicitly report numerical sensitivity instead
    # of assuming a smaller time step must preserve every individual merge time.
    baseline = results[0]
    changes = []
    for summary in results[1:3]:
        delay = baseline['accumulated_delay_veh_s']
        changes.append({
            'dt': summary['config']['dt'],
            'delay_relative_difference': summary['accumulated_delay_veh_s'] / delay - 1 if delay else None,
            'merges_difference': summary['merges'] - baseline['merges'],
            'downstream_flow_difference': summary['downstream_flow_300_900_veh_h'] - baseline['downstream_flow_300_900_veh_h'],
            'approach_speed_difference_kmh': (None if summary.get('approach_speed_kmh') is None
                                              or baseline.get('approach_speed_kmh') is None
                                              else summary['approach_speed_kmh'] - baseline['approach_speed_kmh']),
        })
    report = {
        'runs': results,
        'step_comparison': changes,
        'interpretation': 'Development checks, not empirical validation or a universal safety guarantee.',
    }
    print(json.dumps({'step_comparison': changes}, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--save', type=Path, metavar='NEW_FILE', help='Explicitly save a JSON report.')
    args = parser.parse_args()
    if args.save and args.save.exists():
        parser.error('Refusing to overwrite an existing report.')
    report = validate()
    if args.save:
        args.save.parent.mkdir(parents=True, exist_ok=True)
        args.save.write_text(json.dumps(report, indent=2), encoding='utf-8')
    else:
        print('No validation report was saved.')


if __name__ == '__main__':
    main()
