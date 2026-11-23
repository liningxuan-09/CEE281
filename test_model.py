"""Analytical and numerical checks; tests do not retain simulation outputs."""
import bisect
import math
import unittest
from collections import deque
from dataclasses import replace

import numpy as np

from model import (Config, idm, drive, motion, continuous_min_gap, free_flow_time, merge_test, run, schedule,
                   schedule_profile, acc_inputs, acc_command, driver_takeover, delayed_reading, gipps, follow)


def demand(main, ramp, end, **kw):
    """Config with constant mainline and ramp rates (veh/h) from 0 to end (s); 300 m acceleration lane
    and the short 2 km road (merge at 1.5 km, detectors at 0.5, 1.0, 1.4 and 1.6 km) unless given
    (the scenarios below were set up for them)."""
    kw.setdefault('acc_length', 300.0)
    kw.setdefault('road_end', 2000.0)
    kw.setdefault('merge_x', 1500.0)
    kw.setdefault('detectors', (500.0, 1000.0, 1400.0, 1600.0))
    kw.setdefault('alinea_detector', 1400.0)
    kw.setdefault('seed', 5)
    return Config(main_profile=((0.0, float(end), float(main)),), ramp_profile=((0.0, float(end), float(ramp)),),
                  demand_end=float(end), **kw)


class DynamicsTests(unittest.TestCase):

    def test_equilibrium(self):
        """At the analytical equilibrium spacing, IDM acceleration should be zero."""
        c = Config()
        v = 20.0
        s = (c.s0 + v * c.T) / np.sqrt(1 - (v / c.v0) ** c.delta)
        self.assertAlmostEqual(float(idm(v, s, v, c)), 0, places=12)

    def test_free_acceleration(self):
        """An unobstructed vehicle should approach the desired speed."""
        c = Config()
        v = 0.0
        for _ in range(4000):
            _, v = motion(v, float(idm(v, c=c)), 0.1)
        self.assertLess(abs(float(v) - c.v0), 1e-06)

    def test_exact_stop(self):
        """Within-step braking must give the exact physical stopping distance."""
        dx, v = motion(1.0, -4.0, 1.0)
        self.assertAlmostEqual(float(dx), 0.125)
        self.assertEqual(float(v), 0.0)

    def test_substep_collision(self):
        """Detect an interior collision even when both endpoint gaps are positive."""
        g = continuous_min_gap(np.array([0.2]), np.array([2.0]), np.array([-2.0]), np.array([0.0]), np.array([2.0]), 1.0)
        self.assertLess(float(g[0]), 0.0)

    def test_min_gap_matches_dense_reference(self):
        """Check analytic within-step minima against dense independent time sampling."""
        rng = np.random.default_rng(1)
        for _ in range(40):
            vf, vl = rng.uniform(0, 4, 2)
            af, al = rng.uniform(-4, 2, 2)
            exact = float(continuous_min_gap(np.array([5.0]), np.array([vf]), np.array([af]),
                                             np.array([vl]), np.array([al]), 1.0)[0])
            ts = np.linspace(0, 1.0, 10001)
            dense = np.min(5 + motion(vl, al, ts)[0] - motion(vf, af, ts)[0])
            self.assertAlmostEqual(exact, dense, places=6)

    def test_free_flow_time(self):
        """At v0 the unimpeded time is distance / v0; starting slower takes longer."""
        c = Config()
        self.assertAlmostEqual(free_flow_time(c.v0, 1000.0, c), 1000.0 / c.v0, delta=0.05)
        self.assertGreater(free_flow_time(20.0, 1000.0, c), 1000.0 / c.v0 + 1.0)


class MergeTests(unittest.TestCase):
    """Acceleration lane: IDM+CAH followers and the safety test for leaving the lane."""

    c = Config()
    xs = c.merge_x - c.acc_length

    def car(self, x, v, a=0.0):
        return dict(x=x, v=v, a=a)

    def test_cah_softens_cut_in(self):
        """A vehicle cutting in 10 m ahead at the same speed: IDM brakes hard, IDM+CAH about b."""
        c = self.c
        self.assertLess(float(idm(28.0, 10.0, 28.0, c)), -10.0)
        self.assertGreater(float(drive(28.0, 10.0, 28.0, 0.0, c)), -c.b - 0.5)

    def test_empty_mainline_accepts(self):
        ok = merge_test(self.car(self.xs + 20, 20.0), None, None, self.c, self.xs)[0]
        self.assertTrue(ok)

    def test_matched_speed_gap_is_accepted(self):
        """Mid-lane, at the speed of the gap, 25 m net gaps on both sides are accepted (20 m are not)."""
        x = self.xs + 120
        L, F = self.car(x + 30, 25.0), self.car(x - 30, 25.0)
        self.assertFalse(merge_test(self.car(x, 25.0, 0.5), self.car(x + 25, 25.0), self.car(x - 25, 25.0),
                                    self.c, self.xs)[0])
        self.assertTrue(merge_test(self.car(x, 25.0, 0.5), L, F, self.c, self.xs)[0])

    def test_fast_follower_close_behind_is_rejected(self):
        x = self.xs + 60
        F = self.car(x - 20, 30.0)
        self.assertFalse(merge_test(self.car(x, 15.0, 1.0), None, F, self.c, self.xs)[0])

    def test_forced_merge_at_lane_end_needs_stopping_room(self):
        """A vehicle stopped at the lane end merges only where the follower could stop behind it."""
        x = self.c.merge_x - 2
        stopped = self.car(x, 0.0)
        near = self.car(x - 5 - 30, 25.0)
        far = self.car(x - 5 - 90, 25.0)          # 25^2 / (2 * 4) + 1 = 79 m needed
        self.assertFalse(merge_test(stopped, None, near, self.c, self.xs)[0])
        self.assertTrue(merge_test(stopped, None, far, self.c, self.xs)[0])


class RunTests(unittest.TestCase):

    def test_release_rate_limits_insertions_without_banking(self):
        """At most one ramp insertion per release interval, even with a long queue."""
        c = demand(0, 1800, 60, duration=600, ramp_release_rate=600)
        r = run(c, False)
        self.assertEqual(r['summary']['offered'], r['summary']['exited'])
        entries = sorted(z['release_s'] for z in r['trips'] if z['origin'] == 1)   # green at the stop line
        self.assertGreater(len(entries), 10)
        interval = 3600 / c.ramp_release_rate
        slots = [int((t + 1e-9) // interval) for t in entries]
        self.assertEqual(len(slots), len(set(slots)))
        # Each release falls inside the green at the start of its cycle.
        self.assertTrue(all((t + 1e-9) % interval <= c.meter_green + c.dt + 1e-9 for t in entries))
        self.assertTrue(all(b - a >= interval - c.meter_green - c.dt - 1e-9 for a, b in zip(entries, entries[1:])))

    def test_unmetered_ramp_tries_every_step(self):
        """Without metering, no release slots exist and the head is never kept waiting for one."""
        c = demand(600, 900, 60, seed=21, eval_start=0.0, duration=300)
        r = run(c, True)
        s = r['summary']
        self.assertFalse(s['ramp_metered'])
        self.assertIsNone(s['ramp_release_slots_used'])
        self.assertNotIn('waiting_release', s['merge_attempts'])
        self.assertEqual(s['offered'], s['exited'])
        for key in ('approach_speed_sd_kmh', 'congestion_duration_s', 'max_queue_extent_m', 'ramp_spillback_s'):
            self.assertIsNotNone(s[key], key)

    def test_no_vehicle_yields_and_merges_force_braking(self):
        """No yielding exists; in a busy merge some mainline followers must brake after a merge,
        and ramp vehicles accelerate on the acceleration lane before merging."""
        s = run(demand(1300, 600, 300, duration=900), False)['summary']
        self.assertNotIn('yield_vehicle_steps', s)
        self.assertEqual(s['offered'], s['exited'])
        self.assertGreater(s['merges_braking_mainline_follower'], 0)
        self.assertGreater(s['min_net_gap_m'], 0)
        self.assertGreater(s['mean_merge_speed_kmh'], Config().ramp_entry_speed * 3.6)

    def test_inserted_vehicles_keep_clearance(self):
        """A dense mixed run must finish without overlaps or invalid motion."""
        c = demand(1500, 500, 180, duration=600, ramp_release_rate=900)
        s = run(c, False)['summary']
        self.assertGreater(s['merges'], 10)
        self.assertGreater(s['min_net_gap_m'], 0.0)
        self.assertEqual(s['offered'], s['exited'] + s['remaining_on_road']
                         + s['remaining_main_external'] + s['remaining_ramp_external'])

    def test_reproducibility_and_cleared_delay(self):
        """The seed must repeat; a cleared cohort has equal integrated and summed delays."""
        c = demand(500, 150, 30, duration=300)
        a = run(c, False)
        b = run(c, False)
        self.assertEqual(a['summary'], b['summary'])
        self.assertEqual(a['summary']['offered'], a['summary']['exited'])
        self.assertAlmostEqual(a['summary']['accumulated_delay_veh_s'],
                               sum(z['delay_s'] for z in a['trips']), places=6)

    def test_delay_parts_add_up_to_the_total(self):
        """Total, mainline and ramp delay share one reference (the free-flow time of the origin): once the
        network has cleared, mainline + ramp equals the integrated total, also in a congested run."""
        s = run(demand(1700, 900, 600, duration=900), False)['summary']
        self.assertEqual(s['offered'], s['exited'])
        self.assertGreater(s['stops_at_lane_end'], 0)
        self.assertAlmostEqual(s['accumulated_delay_veh_s'], s['total_delay_main_veh_s'] + s['total_delay_ramp_veh_s'],
                               delta=1e-6 * s['accumulated_delay_veh_s'])
        self.assertAlmostEqual(s['completed_delay_veh_s'], s['accumulated_delay_veh_s'], delta=1e-6 * s['accumulated_delay_veh_s'])

    def test_bottleneck_indicators_cover_the_evaluation_window(self):
        """Congested time and queue extent count only 30 s bins inside the evaluation window, like the
        speeds; the whole run is reported separately. Here congestion outlasts the demand."""
        c = demand(1700, 900, 600, duration=900, eval_start=120.0)
        r = run(c, True)
        s = r['summary']
        bins = {}
        for z in r['trajectories']:
            if z['lane'] == 0 and c.merge_x - 500 <= z['x_km'] * 1000 < c.merge_x:
                b = bins.setdefault(int(z['t_s'] // 30), [0.0, 0])
                b[0] += z['v_kmh']
                b[1] += 1
        slow = [tb for tb, (a, n) in bins.items() if a / n < c.congested_kmh]
        inside = [tb for tb in slow if c.eval_start // 30 <= tb < c.demand_end // 30]
        self.assertGreater(len(slow), len(inside))
        self.assertEqual(s['congestion_duration_s'], 30.0 * len(inside))
        self.assertEqual(s['congestion_duration_full_run_s'], 30.0 * len(slow))
        self.assertLessEqual(s['max_queue_extent_m'], s['max_queue_extent_full_run_m'])
        self.assertEqual(s['measurement_window_s'], [c.eval_start, c.demand_end])

    def test_longer_acceleration_lane(self):
        """A 450 m lane extended upstream: the lane still ends at merge_x, the ramp road and the stop line
        move upstream with it, ramp trips are longer, and the hard-braking count matches the merge events."""
        c = demand(1500, 600, 300, duration=600, acc_length=450.0, ramp_control='alinea')
        r = run(c, False)
        s = r['summary']
        self.assertEqual(s['offered'], s['exited'])
        self.assertAlmostEqual(s['meter_x_m'], c.merge_x - 450.0)
        self.assertGreater(s['free_flow_time_ramp_s'], run(demand(0, 0, 5, duration=10), False)['summary']['free_flow_time_ramp_s'])
        self.assertTrue(all(c.merge_x - 450.0 <= e['x'] <= c.merge_x for e in r['events'] if e['result'] == 'accepted'))
        hard = sum(e['rear_origin'] == 0 and e['rear_acc_after_mps2'] < -3.0 for e in r['events'] if e['result'] == 'accepted')
        self.assertEqual(s['merges_hard_braking_mainline_follower'], hard)

    def test_peak_profile(self):
        """A single-segment profile equals the constant stream; a peak raises the early arrival rate."""
        one = schedule_profile([(0.0, 3600.0, 1000.0)], np.random.default_rng(5))
        self.assertEqual(one, schedule(1000.0, 3600.0, np.random.default_rng(5)))
        prof = schedule_profile([(0.0, 1800.0, 2000.0), (1800.0, 3600.0, 500.0)], np.random.default_rng(5))
        early = sum(t < 1800 for t in prof)
        late = len(prof) - early
        self.assertTrue(800 < early < 1200 and 150 < late < 350)
        self.assertEqual(prof, sorted(prof))

    def test_empty(self):
        """Zero demand must produce neither vehicles nor delay."""
        r = run(demand(0, 0, 5, duration=10), False)
        self.assertEqual(r['summary']['offered'], 0)
        self.assertEqual(r['summary']['accumulated_delay_veh_s'], 0)

    def test_invalid_parameters_are_rejected(self):
        for bad in (dict(merge_x=0.0), dict(merge_x=4000.0), dict(ramp_release_rate=0.0), dict(acc_length=0.0), dict(ramp_length=2000.0),
                    dict(dt=0.3)):
            with self.assertRaises(ValueError):
                run(replace(demand(0, 0, 10, duration=30), **bad), False)


class ObservationTMCTests(unittest.TestCase):
    """Detector reports, queue estimate, forecast and the ALINEA ramp-metering loop."""

    @classmethod
    def setUpClass(cls):
        # Short busy scenario in which downstream occupancy exceeds the ALINEA target at times.
        cls.c = demand(1700, 600, 600, duration=900, ramp_control='alinea')
        cls.r = run(cls.c, False)

    def test_occupancy_and_speed_of_free_vehicles(self):
        """Vehicles cruising at 25 m/s cover a point detector for length / 25 s each."""
        c = demand(120, 0, 300, duration=600, v0=25.0, seed=3)
        r = run(c, False)
        rows = [z for z in r['reports'] if z['sensor_id'] == 'D1000']
        n = sum(z['count'] for z in rows)
        self.assertGreater(n, 3)
        busy = sum(z['occupancy'] for z in rows) * c.report_interval
        self.assertAlmostEqual(busy, n * c.length / 25.0, delta=0.01 * n * c.length / 25.0)
        speeds = [z['mean_speed_mps'] for z in rows if z['mean_speed_mps'] is not None]
        self.assertTrue(all(abs(v - 25.0) < 0.25 for v in speeds))

    def test_report_format_and_counts(self):
        """Every sensor reports every interval; counts at the downstream detector match crossings."""
        c, r = self.c, self.r
        cycles = len(r['tmc'])
        self.assertEqual(cycles, round(c.duration / c.report_interval) - 1)
        sensors = {z['sensor_id'] for z in r['reports']}
        self.assertEqual(sensors, {'D0500', 'D1000', 'D1400', 'D1600', 'RAMP_IN', 'RAMP_OUT'})
        self.assertEqual(len(r['reports']), cycles * len(sensors))
        end = cycles * c.report_interval
        crossings = sum(1 for z in r['detectors'] if z['detector_km'] == 1.6 and z['t_s'] < end)
        self.assertEqual(sum(z['count'] for z in r['reports'] if z['sensor_id'] == 'D1600'), crossings)
        self.assertTrue(all(0 <= z['occupancy'] <= 1 for z in r['reports'] if z['occupancy'] is not None))

    def test_queue_estimate_equals_truth_with_perfect_counters(self):
        """Cumulative arrivals minus releases equals the number waiting at the meter."""
        t = self.r['tmc']
        self.assertTrue(any(z['queue_true_veh'] > 0 for z in t))
        self.assertTrue(all(z['queue_est_veh'] == z['queue_true_veh'] for z in t))
        self.assertTrue(all(z['forecast_veh'] >= 0 for z in t))

    def test_alinea_law_and_bounds(self):
        """Each ALINEA update follows r_k = clip(r_{k-1} + K_R (o* - o_k)) within the bounds."""
        c = self.c
        steps = [z for z in self.r['tmc'] if z['mode'] == 'alinea']
        self.assertTrue(any(z['rate_veh_h'] < c.rate_max for z in steps))
        for z in steps:
            expect = min(max(z['rate_prev_veh_h'] + c.alinea_gain * (c.alinea_target_occ - z['occupancy']), c.rate_min), c.rate_max)
            self.assertAlmostEqual(z['rate_veh_h'], expect, places=9)
        self.assertTrue(all(c.rate_min <= z['rate_veh_h'] <= c.rate_max for z in self.r['tmc']))

    def test_releases_respect_the_rate_without_banking(self):
        """While metering (rate below its maximum) greens come no faster than the rate allows and
        one vehicle passes per green; unused slots are not saved. At the maximum the meter rests green."""
        c, r = self.c, self.r
        cyc = r['tmc']
        times = [0.0] + [z['t_s'] for z in cyc]
        rates = [c.rate_max] + [z['rate_veh_h'] for z in cyc]

        def rate_at(t):
            return rates[bisect.bisect_right(times, t + 1e-9) - 1]
        metered = sorted(z['release_s'] for z in r['trips'] if z['origin'] == 1 and z['release_s'] is not None
                         and rate_at(z['release_s']) < c.rate_max - 1e-9)
        self.assertGreater(len(metered), 5)
        # Signal cycle: greens of meter_green s, at most one vehicle each, separated by at least the minimum red.
        greens = r['signal']
        self.assertTrue(greens)
        self.assertTrue(all(abs((g1 - g0) - c.meter_green) < 1e-9 and u in (0, 1) for g0, g1, u in greens))
        self.assertTrue(all(b[0] - a[1] >= c.meter_min_red - 1e-9 for a, b in zip(greens, greens[1:])))
        self.assertTrue(all(any(g0 - 1e-9 <= t < g1 for g0, g1, _ in greens) for t in metered))
        self.assertEqual(sum(u for _, _, u in greens), r['summary']['ramp_release_slots_used'])
        for z in cyc:
            if z['rate_prev_veh_h'] < c.rate_max - 1e-9:
                self.assertLessEqual(z['released_veh'], math.ceil(c.report_interval * z['rate_prev_veh_h'] / 3600) + 2)
        self.assertGreater(r['summary']['ramp_release_slots_lost'], 0)
        # Nobody passes the stop line before its green.
        self.assertTrue(all(z['meter_s'] >= z['release_s'] - 1e-9 for z in r['trips'] if z['origin'] == 1))

    def test_rest_in_green_commits_only_vehicles_that_cannot_stop(self):
        """Resting in green is a state, not a lasting permission. A vehicle is committed (released) only
        once it could no longer stop at the line braking at b, so when metering resumes everybody further
        upstream waits for a green. (The model also asserts that nobody passes a red signal.)"""
        c, r = self.c, self.r
        times = [0.0] + [z['t_s'] for z in r['tmc']]
        rates = [c.rate_max] + [z['rate_veh_h'] for z in r['tmc']]

        def resting(t):
            return rates[bisect.bisect_right(times, t + 1e-9) - 1] >= c.rate_max - 1e-9
        self.assertTrue(any(a >= c.rate_max - 1e-9 > b for a, b in zip(rates, rates[1:])))   # metering resumes
        ramp = [z for z in r['trips'] if z['origin'] == 1]
        self.assertTrue(all(z['release_s'] is not None and z['meter_s'] >= z['release_s'] - 1e-9 for z in ramp))
        committed = [z for z in ramp if resting(z['release_s'])]
        self.assertTrue(committed)
        x_meter = c.merge_x - c.acc_length
        reach = c.ramp_v0 ** 2 / (2 * c.b)            # stopping distance at b from the ramp speed
        self.assertTrue(all(0 <= x_meter - z['release_x_m'] <= reach + 1.0 for z in committed))
        # Released by a green slot: within check-in distance of the line.
        slot = [z for z in ramp if not resting(z['release_s'])]
        self.assertTrue(slot)
        self.assertTrue(all(x_meter - z['release_x_m'] <= c.meter_checkin + 1e-9 for z in slot))

    def test_red_signal_stops_vehicles_on_the_ramp(self):
        """Metered vehicles queue on the ramp road and stop just before the stop line."""
        r = run(self.c, True)
        xm = (self.c.merge_x - self.c.acc_length) / 1000
        stopped = [z for z in r['trajectories'] if z['origin'] == 1 and z['lane'] == 1
                   and xm - 0.01 < z['x_km'] < xm and z['v_kmh'] < 1.0]
        self.assertTrue(stopped)
        self.assertGreater(r['summary']['max_ramp_queue_veh'], 3)

    def test_queue_override(self):
        """With no storage, any waiting vehicle forces the maximum release rate."""
        r = run(replace(self.c, ramp_storage=0), False)
        over = [z for z in r['tmc'] if z['queue_est_veh'] > 0]
        self.assertTrue(over)
        self.assertTrue(all(z['mode'] == 'override' and z['rate_veh_h'] == self.c.rate_max for z in over))

    def test_missing_reports_hold_then_fallback(self):
        """Lost reports: hold the rate while the last report is recent, then use the fixed fallback."""
        c = replace(self.c, report_dropout=((300.0, 450.0),))
        r = run(c, False)
        modes = {z['t_s']: z['mode'] for z in r['tmc']}
        self.assertEqual([modes[t] for t in (270.0, 300.0, 330.0, 360.0, 420.0, 450.0)],
                         ['alinea', 'hold', 'hold', 'fallback', 'fallback', 'alinea'])
        self.assertTrue(all(z['rate_veh_h'] == c.fallback_rate for z in r['tmc'] if z['mode'] == 'fallback'))
        lost = [z for z in r['reports'] if z['quality_flag'] == 'missing']
        self.assertEqual(len(lost), 5 * 6)
        self.assertTrue(all(z['count'] is None and z['occupancy'] is None for z in lost))
        # Counters keep running: the estimate is exact again once reports return.
        after = [z for z in r['tmc'] if z['t_s'] >= 450.0]
        self.assertTrue(all(z['queue_est_veh'] == z['queue_true_veh'] for z in after))

    def test_no_control_matches_unmetered_dynamics(self):
        """Reports and forecasts are passive: without ramp control the traffic is unchanged."""
        base = run(replace(self.c, ramp_control=None), False)
        self.assertTrue(all(z['mode'] == 'none' for z in base['tmc']))
        self.assertFalse(base['summary']['ramp_metered'])
        # Same arrivals and no metering: every ramp vehicle enters as soon as admission allows.
        self.assertLess(max(z['wait_s'] for z in base['trips'] if z['origin'] == 1), 30.0)

    def test_missed_detections(self):
        """Missed passages lower measured counts (about by the miss rate) but never the true ones;
        detector defects are passive, so traffic without ramp control is unchanged."""
        c = replace(self.c, ramp_control=None, detector_miss_prob=0.2)
        r = run(c, False)
        base = run(replace(c, detector_miss_prob=0.0), False)
        self.assertEqual(r['summary']['accumulated_delay_veh_s'], base['summary']['accumulated_delay_veh_s'])
        rows = [z for z in r['reports'] if z['sensor_id'] == 'D1400']
        self.assertTrue(all(z['count'] <= z['count_true'] and z['occupancy'] <= z['occupancy_true'] + 1e-12 for z in rows))
        ratio = sum(z['count'] for z in rows) / sum(z['count_true'] for z in rows)
        self.assertAlmostEqual(ratio, 0.8, delta=0.05)
        self.assertGreater(r['summary']['queue_estimate_mae_veh'], 0)
        self.assertTrue(all(z['queue_est_veh'] >= 0 for z in r['tmc']))

    def test_occupancy_noise(self):
        """Noise changes only the reported occupancy, which stays within [0, 1]."""
        r = run(replace(self.c, occupancy_noise_sd=0.05), False)
        rows = [z for z in r['reports'] if z['sensor_id'].startswith('D')]
        self.assertTrue(all(0 <= z['occupancy'] <= 1 for z in rows))
        self.assertTrue(all(z['count'] == z['count_true'] for z in rows))
        self.assertGreater(r['summary']['detector_occupancy_mae'], 0.01)

    def test_report_delay(self):
        """A delayed report is used one interval late; before the first one arrives the meter
        uses the fallback rate."""
        c = replace(self.c, report_delay=30.0)
        r = run(c, False)
        t = r['tmc']
        self.assertEqual(t[0]['mode'], 'fallback')
        self.assertFalse(t[0]['report_ok'])
        self.assertTrue(all(z['data_time_s'] == z['t_s'] - 30.0 for z in t[1:] if z['report_ok']))
        self.assertTrue(all(z['queue_est_veh'] == z['queue_true_veh'] for z in t if z['report_ok']))
        self.assertTrue(all(z['received_s'] == z['interval_end_s'] + 30.0 for z in r['reports']))

    def test_invalid_tmc_settings_are_rejected(self):
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, ramp_control='pid'), False)
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, ramp_control='alinea', ramp_release_rate=600), False)
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, ramp_control='alinea', alinea_detector=1550.0), False)
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, report_delay=10.0), False)
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, detector_miss_prob=1.0), False)


class ACCTests(unittest.TestCase):
    """ACC: onboard inputs, Gunter et al. (2020) following law, cruise, driver takeover, fallback and
    nested equipment assignment."""

    def test_onboard_inputs_are_same_lane_gap_and_leader_speed(self):
        gap, lv = acc_inputs(np.array([500.0, 460.0, 400.0]), np.array([30.0, 25.0, 20.0]), 5.0)
        self.assertTrue(math.isinf(gap[0]))
        np.testing.assert_allclose(gap[1:], [35.0, 55.0])
        np.testing.assert_allclose(lv[1:], [30.0, 25.0])

    def test_equilibrium_gap_is_eta_plus_h_v(self):
        c = Config()
        for v in (5.0, 15.0, 25.0, 32.0):
            s = c.acc_eta + c.acc_h * v
            self.assertAlmostEqual(float(acc_command(v, s, v, c)), 0.0, places=12)
            self.assertLess(float(acc_command(v, s - 1.0, v, c)), 0.0)       # too close: slow down
            self.assertGreater(float(acc_command(v, s + 1.0, v, c)), 0.0)    # too far: speed up

    def test_following_law_has_the_gunter_form(self):
        c = Config()
        v, s, lv = 20.0, 30.0, 18.0
        expected = c.acc_kp * (s - c.acc_eta - c.acc_h * v) - c.acc_kv * (v - lv)
        self.assertAlmostEqual(float(acc_command(v, s, lv, c)), expected, places=12)

    def test_cruise_equals_idm_free_road(self):
        """Without a vehicle ahead, or far behind one, ACC accelerates like a free IDM vehicle."""
        c = Config()
        for v in (0.0, 10.0, 25.0, 33.0):
            self.assertAlmostEqual(float(acc_command(v, math.inf, v, c)), float(idm(v, c=c)), places=12)
        self.assertAlmostEqual(float(acc_command(10.0, 1e5, 10.0, c)), float(idm(10.0, c=c)), places=12)

    def test_fallback_brakes_without_a_valid_reading(self):
        c = Config()
        u = acc_command(np.array([20.0, 20.0]), np.array([50.0, 50.0]), np.array([20.0, 20.0]), c,
                        valid=np.array([True, False]))
        self.assertAlmostEqual(float(u[0]), float(acc_command(20.0, 50.0, 20.0, c)), places=12)
        self.assertEqual(float(u[1]), -c.acc_fallback_decel)

    def test_takeover_rule_and_handover(self):
        c = Config()
        a, take = driver_takeover(-0.3, -2.5, c)                 # driver brakes harder than b_TO and the ACC
        self.assertTrue(bool(take))
        self.assertEqual(float(a), -2.5)
        a, take = driver_takeover(-3.0, -2.5, c)                 # the ACC already brakes harder
        self.assertFalse(bool(take))
        self.assertEqual(float(a), -3.0)
        self.assertFalse(bool(driver_takeover(-0.3, -1.5, c)[1]))   # mild braking does not start a takeover
        a, take = driver_takeover(-0.3, -1.5, c, active=True)      # ... but continues one
        self.assertTrue(bool(take))
        self.assertEqual(float(a), -1.5)
        a, take = driver_takeover(-0.3, -0.2, c, active=True)      # handover once the driver brakes less
        self.assertFalse(bool(take))
        self.assertEqual(float(a), -0.3)

    def test_close_slow_cut_in_hands_over_and_mild_cut_in_does_not(self):
        c = replace(Config(), acc_kv=0.2692)                      # fitted gains: the ACC brakes weakly
        v = 20.0
        a, take = driver_takeover(acc_command(v, 8.0, 15.0, c), drive(v, 8.0, 15.0, 0.0, c), c)
        self.assertTrue(bool(take))
        self.assertLess(float(a), -c.acc_takeover_b)
        a, take = driver_takeover(acc_command(v, 20.0, 20.0, c), drive(v, 20.0, 20.0, 1.0, c), c)
        self.assertFalse(bool(take))
        self.assertGreater(float(a), -1.0)                        # the ACC brakes only gently
        # With the string-stable gains the ACC itself brakes about as hard as the driver would.
        self.assertLess(float(acc_command(v, 8.0, 15.0, Config())), -c.acc_takeover_b)

    def test_default_gain_is_string_stable_and_the_fitted_one_is_not(self):
        """kv meets kp h^2 + 2 kv h - 2 >= 0 as the smallest value rounded up to 0.05; the fitted
        kv = 0.2692 of Gunter et al. fails it."""
        c = Config()
        self.assertGreaterEqual(c.acc_kp * c.acc_h ** 2 + 2 * c.acc_kv * c.acc_h - 2, 0.0)
        self.assertLess(c.acc_kp * c.acc_h ** 2 + 2 * (c.acc_kv - 0.05) * c.acc_h - 2, 0.0)
        self.assertLess(c.acc_kp * c.acc_h ** 2 + 2 * 0.2692 * c.acc_h - 2, 0.0)

    def test_mixed_platoon_keeps_clearance_when_the_leader_brakes_hard(self):
        """Leader brakes from 25 to 5 m/s at 3 m/s^2; HDV and ACC followers keep more than 1 m."""
        c = Config()
        kinds = ['ACC', 'HDV', 'ACC', 'ACC', 'HDV', 'ACC'] * 3
        is_acc = np.array([k == 'ACC' for k in kinds])
        x = [0.0]
        for k in kinds:
            s = c.acc_eta + c.acc_h * 25.0 if k == 'ACC' else (c.s0 + c.T * 25.0) / math.sqrt(1 - (25.0 / c.v0) ** c.delta)
            x.append(x[-1] - c.length - s)
        x, v, a = np.array(x), np.full(len(kinds) + 1, 25.0), np.zeros(len(kinds) + 1)
        active = np.zeros(len(kinds), bool)
        lowest = math.inf
        for step in range(1200):
            t = step * c.dt
            lead = -3.0 if 5.0 <= t < 5.0 + 20.0 / 3.0 else 0.0
            gap = np.diff(-x) - c.length
            a_drv = drive(v[1:], gap, v[:-1], a[:-1], c)
            a_acc, take = driver_takeover(acc_command(v[1:], gap, v[:-1], c), a_drv, c, active)
            active = take & is_acc
            acc = np.clip(np.r_[lead, np.where(is_acc, a_acc, a_drv)], c.amin, c.amax)
            acc = np.where((v <= 0) & (acc < 0), 0.0, acc)
            lowest = min(lowest, float(np.min(continuous_min_gap(gap, v[1:], acc[1:], v[:-1], acc[:-1], c.dt))))
            dx, v = motion(v, acc, c.dt)
            x, a = x + dx, acc
        self.assertGreater(lowest, 1.0)

    def test_zero_share_reproduces_the_pre_acc_model(self):
        """acc_share = 0 leaves the traffic unchanged (value recorded with the pre-ACC code)."""
        s = run(demand(1300, 400, 300, duration=900), False)['summary']
        self.assertEqual(s['accumulated_delay_veh_s'], 2049.3992098680105)
        self.assertEqual(s['acc_vehicles_main'] + s['acc_vehicles_ramp'] + s['acc_takeover_episodes'], 0)

    def test_equipment_is_nested_and_arrivals_are_identical(self):
        base = demand(1200, 300, 300, duration=900, seed=7)
        trips = {}
        for share in (0.0, 0.25, 0.5, 1.0):
            r = run(replace(base, acc_share=share), False)
            self.assertEqual(r['summary']['offered'], r['summary']['exited'])
            trips[share] = {z['id']: (z['type'], z['scheduled_s']) for z in r['trips']}
        ids = set(trips[0.0])
        for share, tr in trips.items():
            self.assertEqual(set(tr), ids)
            self.assertTrue(all(tr[i][1] == trips[0.0][i][1] for i in ids))
        acc = {s: {i for i, (k, _) in tr.items() if k == 'ACC'} for s, tr in trips.items()}
        self.assertEqual(acc[0.0], set())
        self.assertEqual(acc[1.0], ids)
        self.assertTrue(acc[0.25] <= acc[0.5])
        self.assertAlmostEqual(len(acc[0.5]) / len(ids), 0.5, delta=0.1)

    def test_ramp_acc_vehicles_merge_like_hdvs(self):
        """With no mainline traffic the first ramp vehicle merges and exits identically with and without
        equipment: HDV rules on the ramp, and ACC cruise equals IDM free-road driving."""
        c = demand(0, 600, 120, duration=600)
        ra, rb = run(c, False), run(replace(c, acc_share=1.0), False)
        ea, eb = (min(r['events'], key=lambda e: e['t']) for r in (ra, rb))
        self.assertEqual((ea['id'], ea['t'], ea['x']), (eb['id'], eb['t'], eb['x']))
        ta, tb = ({z['id']: z for z in r['trips']}[ea['id']] for r in (ra, rb))
        self.assertEqual(tb['type'], 'ACC')
        self.assertAlmostEqual(ta['exit_s'], tb['exit_s'], places=9)

    def test_full_acc_run_is_collision_free(self):
        s = run(demand(1500, 500, 300, duration=900, acc_share=1.0), False)['summary']
        self.assertEqual(s['offered'], s['exited'] + s['remaining_on_road']
                         + s['remaining_main_external'] + s['remaining_ramp_external'])
        self.assertGreater(s['merges'], 10)
        self.assertGreater(s['merges_with_acc_follower'], 0)
        self.assertGreater(s['min_net_gap_m'], 0.0)
        self.assertIsNone(s['min_net_gap_hdv_follower_m'])
        self.assertGreater(s['min_net_gap_acc_follower_m'], 0.0)

    def test_delayed_reading_holds_then_lags(self):
        self.assertEqual([delayed_reading(h, r, 2) for h in [deque()] for r in (1, 2, 3, 4, 5)], [1, 1, 1, 2, 3])
        self.assertEqual(delayed_reading(deque(), 7, 0), 7)

    def test_sensor_delay_run_is_collision_free_and_changes_traffic(self):
        c = demand(1500, 500, 300, duration=900, acc_share=1.0)
        a = run(c, False)['summary']
        b = run(replace(c, acc_sensor_delay=1.0), False)['summary']
        self.assertGreater(b['min_net_gap_m'], 0.0)
        self.assertEqual(b['offered'], b['exited'] + b['remaining_on_road']
                         + b['remaining_main_external'] + b['remaining_ramp_external'])
        self.assertNotEqual(a['accumulated_delay_veh_s'], b['accumulated_delay_veh_s'])
        with self.assertRaises(ValueError):
            run(replace(c, acc_sensor_delay=0.05), False)

    def test_invalid_acc_settings_are_rejected(self):
        for kw in (dict(acc_share=1.5), dict(acc_share=-0.1), dict(acc_h=-1.0), dict(acc_takeover_b=0.0)):
            with self.assertRaises(ValueError):
                run(demand(100, 100, 60, duration=120, **kw), False)



class GippsTests(unittest.TestCase):
    """Second human-driver model (human-model check)."""

    def test_equilibrium_gap_is_sm_plus_one_and_a_half_tau_v(self):
        c = Config()
        for v in (5.0, 15.0, 30.0):
            s = c.gipps_sm + 1.5 * c.gipps_tau * v
            self.assertAlmostEqual(float(gipps(v, s, v, c)), 0.0, places=9)
            self.assertLess(float(gipps(v, s - 2.0, v, c)), 0.0)
            self.assertGreater(float(gipps(v, s + 2.0, v, c)), 0.0)

    def test_free_road_term_and_desired_speed(self):
        c = Config()
        v = 10.0
        expect = 2.5 * c.gipps_a * (1 - v / c.v0) * math.sqrt(0.025 + v / c.v0)
        self.assertAlmostEqual(float(gipps(v, np.inf, 0.0, c)), expect, places=12)
        self.assertAlmostEqual(float(gipps(c.v0, np.inf, 0.0, c)), 0.0, places=12)
        self.assertLess(float(gipps(c.v0 + 2.0, np.inf, 0.0, c)), 0.0)
        # With a far leader the free-road term decides.
        self.assertAlmostEqual(float(gipps(v, 500.0, v, c)), expect, places=12)

    def test_capacity_matches_idm(self):
        """tau was chosen so that the Gipps capacity at v0 is about the IDM capacity."""
        c = Config()
        v = np.linspace(1.0, c.v0 - 0.01, 20000)
        idm_cap = np.max(3600 * v / ((c.s0 + c.T * v) / np.sqrt(1 - (v / c.v0) ** c.delta) + c.length))
        gipps_cap = 3600 * c.v0 / (c.length + c.gipps_sm + 1.5 * c.gipps_tau * c.v0)
        self.assertAlmostEqual(c.length + c.gipps_sm, 6.5)
        self.assertLess(abs(gipps_cap / idm_cap - 1), 0.01)

    def test_follow_dispatches_on_the_human_model(self):
        c = Config()
        args = (20.0, 30.0, 18.0, 0.0)
        self.assertEqual(float(follow(*args, c)), float(drive(*args, c)))
        g = replace(c, human_model='gipps')
        self.assertEqual(float(follow(*args, g)), float(gipps(20.0, 30.0, 18.0, g)))
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, human_model='other'), False)
        with self.assertRaises(ValueError):
            run(demand(100, 100, 60, duration=120, human_model='gipps', gipps_tau=0.0), False)

    def test_platoon_keeps_clearance_when_the_leader_brakes_hard(self):
        c = replace(Config(), human_model='gipps')
        n, v0 = 15, 25.0
        x = -np.arange(n + 1) * (c.length + c.gipps_sm + 1.5 * c.gipps_tau * v0)
        v, mingap = np.full(n + 1, v0), np.inf
        for step in range(600):
            gap = np.diff(-x) - c.length
            a = np.clip(np.r_[c.amin if step < 80 else 0.0, gipps(v[1:], gap, v[:-1], c)], c.amin, c.amax)
            a = np.where((v <= 0) & (a < 0), 0.0, a)
            mingap = min(mingap, float(continuous_min_gap(gap, v[1:], a[1:], v[:-1], a[:-1], c.dt).min()))
            dx, v = motion(v, a, c.dt)
            x = x + dx
        self.assertGreater(mingap, 0.5)
        self.assertLess(float(v.max()), 0.5)        # the leader stopped and stays stopped; so does everyone

    def test_gipps_runs_are_collision_free_and_conserve_vehicles(self):
        for share in (0.0, 0.5):
            s = run(demand(1500, 500, 300, duration=900, human_model='gipps', acc_share=share), False)['summary']
            self.assertGreater(s['min_net_gap_m'], 0.0)
            self.assertEqual(s['offered'], s['exited'] + s['remaining_on_road']
                             + s['remaining_main_external'] + s['remaining_ramp_external'])

    def test_default_human_model_is_idm(self):
        c = demand(1500, 500, 300, duration=600)
        self.assertEqual(run(c, False)['summary']['accumulated_delay_veh_s'],
                         run(replace(c, human_model='idm'), False)['summary']['accumulated_delay_veh_s'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
