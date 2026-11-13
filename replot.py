"""Re-render a saved run with the current figures, HTML report and GIF.

Usage::

    python3 -B replot.py results/dev_history/first_model

Output goes to a new ``replot/`` folder inside the run (refused if it exists).
The original files are only read. Nothing is re-simulated: everything is drawn
from the run's ``with_ramp_raw.json``. Fields that older model versions did not
record are either derived from the stored events or shown as not available.
"""
import argparse
import json
from pathlib import Path

from present import render, fill_derived
from make_gif import make


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('run', type=Path, help='Saved run folder containing with_ramp_raw.json.')
    parser.add_argument('--no-gif', action='store_true', help='Skip the GIF.')
    args = parser.parse_args(argv)
    raw = args.run / 'with_ramp_raw.json'
    if not raw.exists():
        parser.error(f'{raw} not found')
    out = args.run / 'replot'
    if out.exists():
        parser.error(f'{out} already exists; remove it first if you want to re-render')
    result = json.loads(raw.read_text(encoding='utf-8'))
    derived = fill_derived(result)
    render({'with_ramp': result}, out, tables=False)
    if not args.no_gif:
        make(out, raw=raw)
    note = ['Re-rendered with the current presentation code (replot.py).',
            f'Source data: ../{raw.name} (unchanged; no re-simulation).']
    if derived:
        note.append('Derived from recorded events because this model version did not store them: '
                    + ', '.join(derived) + '.')
    (out / 'REPLOT_NOTE.txt').write_text('\n'.join(note) + '\n', encoding='utf-8')
    print(f'Re-rendered {args.run} into {out}')


if __name__ == '__main__':
    main()
