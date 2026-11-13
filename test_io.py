"""Verify that saving is opt-in; temporary export artifacts are always removed."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from model import Config, run
import run_demo


class OutputTests(unittest.TestCase):
    def test_default_run_does_not_create_directories(self):
        """Exercise CLI policy with a stub, without running the full experiment."""
        stub = {'summary': {'status': 'test-only'}}
        with patch('run_demo.run', return_value=stub) as simulation:
            with patch('pathlib.Path.mkdir', side_effect=AssertionError('Unexpected disk output')):
                with redirect_stdout(StringIO()) as console:
                    results = run_demo.main([])
        self.assertEqual(simulation.call_count, 1)
        self.assertEqual(set(results), {'with_ramp'})
        self.assertEqual(simulation.call_args.args[0].ramp_profile, Config().ramp_profile)
        self.assertTrue(all(call.kwargs['record'] is False for call in simulation.call_args_list))
        self.assertIn('No simulation results were saved', console.getvalue())

    def test_gif_requires_explicit_save(self):
        """A rendering option alone must not silently enable persistence."""
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            run_demo.main(['--gif'])

    def test_export_is_english_and_temporary(self):
        """Smoke-test the exporter using an empty short run, then discard every file."""
        empty = run(Config(main_profile=((0.0, 5.0, 0.0),), ramp_profile=((0.0, 5.0, 0.0),), duration=10, demand_end=5))
        with TemporaryDirectory(prefix='cee281_export_test_') as folder:
            target = Path(folder) / 'requested_run'
            with patch('run_demo.run', return_value=empty), redirect_stdout(StringIO()):
                run_demo.main(['--save', '--gif', '--output', str(target)])
            page = (target / 'classroom_demo.html').read_text(encoding='utf-8')
            self.assertIn('<html lang="en">', page)
            self.assertNotIn('{{', page)
            self.assertNotIn('no_ramp', page)
            self.assertNotIn('Paired extra delay', page)
            self.assertTrue((target / 'with_ramp_raw.json').exists())
            from present import FIGURES
            for filename, _ in FIGURES:
                self.assertTrue((target / filename).exists(), filename)
            self.assertFalse((target / 'no_ramp_raw.json').exists())
            self.assertFalse((target / 'baseline_trajectories.png').exists())
            self.assertFalse((target / 'comparison.json').exists())
            self.assertFalse(any('\u4e00' <= ch <= '\u9fff' for ch in page))
            self.assertTrue((target / 'simulation_replay.gif').exists())
        self.assertFalse(target.exists())

    def test_existing_output_is_not_overwritten(self):
        """A user-saved experiment is protected from accidental reruns."""
        with TemporaryDirectory(prefix='cee281_existing_test_') as folder:
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                run_demo.main(['--save', '--output', folder])


if __name__ == '__main__':
    unittest.main(verbosity=2)
