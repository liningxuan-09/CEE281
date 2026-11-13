"""Deterministic single-lane tests that explain the ACC results (no merge, no randomness).

1. Platoon disturbance: a leader at 25 m/s slows to 15 m/s at 2 m/s^2, holds 20 s and recovers;
   40 followers start at their equilibrium gaps. Reports each follower's speed drop.
2. Queue discharge: 30 vehicles stand at their standstill gaps; the leader drives off freely.
   Reports the flow past a point 300 m downstream (5th vehicle to the last).

Both use the model's own laws (drive, acc_command, driver_takeover, motion) and print a table for the
main controller (kv = 0.80), the k_v ablation (Gunter et al. fitted kv = 0.2692) and the main controller
under a sensor delay or the longer time gap h = 1.69 s; nothing is written.    python3 -B acc_mechanism.py
"""
from collections import deque
from dataclasses import replace

import numpy as np

from model import Config, drive, acc_command, driver_takeover, motion, delayed_reading

CONTROLLERS = {'main (kv = 0.80)': {}, 'main, sensor delay 0.5 s': {'acc_sensor_delay': 0.5},
               'main, sensor delay 1.0 s': {'acc_sensor_delay': 1.0}, 'main, h = 1.69 s': {'acc_h': 1.6881},
               'Gunter fit (kv = 0.2692)': {'acc_kv': 0.2692}}


def step_all(c, x, v, a, is_acc, active, lead_a, hist):
    gap = np.diff(-x) - c.length
    a_drv = drive(v[1:], gap, v[:-1], a[:-1], c)
    g_in, lv_in = gap, v[:-1]
    if c.acc_sensor_delay > 0:                     # the ACC sees readings taken acc_sensor_delay s earlier
        g_in, lv_in = delayed_reading(hist, (gap.copy(), v[:-1].copy()), round(c.acc_sensor_delay / c.dt))
    u = acc_command(v[1:], g_in, lv_in, c)
    a_acc, take = driver_takeover(u, a_drv, c, active)
    acc = np.clip(np.r_[lead_a, np.where(is_acc, a_acc, a_drv)], c.amin, c.amax)
    acc = np.where((v <= 0) & (acc < 0), 0.0, acc)
    dx, nv = motion(v, acc, c.dt)
    return x + dx, nv, acc, take & is_acc, gap


def platoon(c, kinds, v0=25.0, vlow=15.0, decel=2.0, hold=20.0, t_end=300.0):
    is_acc = np.array([k == 'ACC' for k in kinds])
    x = [0.0]
    for k in kinds:
        s = c.acc_eta + c.acc_h * v0 if k == 'ACC' else (c.s0 + c.T * v0) / np.sqrt(1 - (v0 / c.v0) ** c.delta)
        x.append(x[-1] - c.length - s)
    x, v, a = np.array(x), np.full(len(kinds) + 1, v0), np.zeros(len(kinds) + 1)
    active, minv, mingap, takeovers = np.zeros(len(kinds), bool), np.full(len(kinds) + 1, v0), np.inf, 0
    hist = deque()
    t1 = (v0 - vlow) / decel
    for step in range(int(round(t_end / c.dt))):
        t = step * c.dt
        lead = -decel if 10 <= t < 10 + t1 else (decel if 10 + t1 + hold <= t < 10 + 2 * t1 + hold else 0.0)
        x, v, a, take, gap = step_all(c, x, v, a, is_acc, active, lead, hist)
        takeovers += int(np.sum(take & ~active))
        active = take
        minv, mingap = np.minimum(minv, v), min(mingap, float(gap.min()))
    return v0 - minv, mingap, takeovers


def discharge(c, kinds, t_end=200.0, xd=300.0):
    is_acc = np.array([k == 'ACC' for k in kinds])
    x = [0.0]
    for k in kinds:
        x.append(x[-1] - c.length - (c.acc_eta if k == 'ACC' else c.s0))
    x, v, a = np.array(x), np.zeros(len(kinds) + 1), np.zeros(len(kinds) + 1)
    active, cross = np.zeros(len(kinds), bool), np.full(len(kinds) + 1, np.nan)
    hist = deque()
    for step in range(int(round(t_end / c.dt))):
        lead = float(c.a * (1 - (v[0] / c.v0) ** c.delta))
        nx, v, a, active, _ = step_all(c, x, v, a, is_acc, active, lead, hist)
        hit = np.isnan(cross) & (x < xd) & (nx >= xd)
        cross[hit] = (step + 1) * c.dt
        x = nx
    ok = cross[~np.isnan(cross)]
    return 3600 * (len(ok) - 5) / (ok[-1] - ok[4])


def mixes(n):
    return {'all HDV': ['HDV'] * n, '25% ACC (every 4th)': ['ACC' if i % 4 == 3 else 'HDV' for i in range(n)],
            '100% ACC': ['ACC'] * n}


def main():
    base = Config()
    print(f'Spacing eta={base.acc_eta} m, h={base.acc_h} s; takeover above {base.acc_takeover_b} m/s^2')
    for label, over in CONTROLLERS.items():
        c = replace(base, **over)
        print(f'\n=== {label} ===')
        print('1. Platoon disturbance (speed drop in m/s; leader drops 10 m/s)')
        for name, kinds in mixes(40).items():
            drop, mingap, takeovers = platoon(c, kinds)
            print(f'   {name:20s} follower 5: {drop[5]:5.1f}  10: {drop[10]:5.1f}  20: {drop[20]:5.1f}  40: {drop[40]:5.1f}'
                  f'  | min gap {mingap:5.1f} m, takeovers {takeovers}')
        print('2. Queue discharge from standstill (veh/h past 300 m): ' +
              '  '.join(f'{name}: {discharge(c, kinds):5.0f}' for name, kinds in mixes(30).items()))


if __name__ == '__main__':
    main()
