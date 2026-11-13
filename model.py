"""All-HDV freeway with an on-ramp and an explicit acceleration lane. SI units internally.

Ramp vehicles drive a ramp road and then a parallel acceleration lane (lane 1) beside the single
mainline lane (lane 0). Car following everywhere is IDM with the constant-acceleration heuristic
(IDM+CAH, Kesting, Treiber & Helbing 2010), so a vehicle that cuts in at a short gap without being
slower does not trigger emergency braking. On the acceleration lane a ramp vehicle accelerates,
lines up with a mainline gap (target_speed) and changes lane when the merge is safe (merge_test):
neither it nor its new follower would have to brake harder than b_safe (rising to b_safe_end
towards the lane end). Close to the lane end it forces its way into any gap the new follower can
still handle. No vehicle yields: mainline vehicles ignore the acceleration lane until a vehicle
has merged in front of them.

ACC vehicles (acc_share of both streams) follow on the mainline with the main controller (acc_command:
the following law of Gunter et al. 2020 with string-stable gains), fed only by onboard readings (acc_inputs),
with a driver takeover. On the ramp road and the acceleration lane they drive and merge like HDVs.
"""
from dataclasses import dataclass, asdict
from typing import Optional
from collections import deque, Counter
import bisect
import math
import numpy as np


@dataclass
class Config:
    """Parameters for the HDV merge-bottleneck baseline. Meters, seconds, m/s unless noted.

    Defaults are the chosen all-HDV baseline: seed 9, mainline 1,700 veh/h, ramp
    100 -> 450 -> 0 veh/h (5 / 30 / 5 min), 2 km road, 450 m acceleration lane: a clear merge
    bottleneck in which only a few ramp vehicles have to wait at the end of the acceleration lane."""
    seed: int = 9
    dt: float = 0.1
    duration: float = 3600.0
    demand_end: float = 2400.0
    # Demand profiles, ((start_s, end_s, veh_h), ...), piecewise-constant Poisson rates.
    main_profile: tuple = ((0.0, 2400.0, 1700.0),)
    ramp_profile: tuple = ((0.0, 300.0, 100.0), (300.0, 2100.0, 450.0), (2100.0, 2400.0, 0.0))
    # Geometry (mainline coordinates). The acceleration lane runs beside the mainline from
    # merge_x - acc_length to merge_x; the ramp road before it is ramp_length long.
    road_end: float = 2000.0
    merge_x: float = 1500.0
    acc_length: float = 450.0
    ramp_length: float = 200.0
    # Ramp road and acceleration lane behaviour.
    ramp_v0: float = 60 / 3.6          # desired speed on the ramp road
    ramp_entry_speed: float = 60 / 3.6
    acc_lane_a: float = 2.0            # free-road acceleration (m/s^2) used on the acceleration lane
    drop_dv: float = 10 / 3.6          # with no feasible gap nearby, slow to the speed beside minus this
    align_k: float = 0.3               # 1/s: speed correction per m of distance to the targeted gap
    b_safe: float = 2.0                # largest braking a merge may impose at the lane start (m/s^2)
    b_safe_end: float = 4.0            # ... rising (quadratically) to this at the lane end
    merge_gap_min: float = 2.0         # smallest net gap ahead of and behind the merging vehicle
    merge_horizon: float = 2.0         # s; gaps are judged as they will be this much later
    end_trigger: float = 3.8           # brake for the lane end once stopping needs more than this (m/s^2)
    end_margin: float = 1.0            # m left before the lane end when stopped there
    force_zone: float = 60.0           # last m of the lane where a vehicle forces its way in
    # Fixed-rate ramp metering (veh/h; None = no fixed metering).
    ramp_release_rate: Optional[float] = None
    # Ramp meter stop line (m, mainline coordinates; None = end of the ramp road, where the
    # acceleration lane begins). Metered vehicles queue on the ramp road, stop at the line and
    # each green releases one vehicle within meter_checkin m of the line, which starts from rest.
    meter_x: Optional[float] = None
    meter_checkin: float = 30.0
    # Signal timing: each cycle starts with a green of meter_green s in which the first waiting vehicle
    # may go (one car per green), then red until the next cycle starts. Cycle = 3600 / rate s, which must
    # be at least meter_green + meter_min_red at the maximum rate (2 + 2 s: 4 s, i.e. 900 veh/h).
    meter_green: float = 2.0
    meter_min_red: float = 2.0
    # Observation interface: every mainline detector reports count, occupancy and speed every
    # report_interval s; the ramp has a queue-tail counter (RAMP_IN) and a counter at the meter
    # (RAMP_OUT). Reports whose interval ends inside a report_dropout window are lost.
    report_interval: float = 30.0
    report_dropout: tuple = ()          # ((start_s, end_s), ...)
    # Detector defects (observation tests; all off by default). Each passage is missed with
    # detector_miss_prob (a missed vehicle adds nothing to count, occupancy or speed; the ramp
    # counters lose the count); reported occupancy gets Gaussian noise with SD occupancy_noise_sd
    # (fraction, clipped to [0, 1]); reports reach the TMC report_delay s after their interval ends.
    detector_miss_prob: float = 0.0
    occupancy_noise_sd: float = 0.0
    report_delay: float = 0.0
    # Queue forecast (advisory): horizon (s) and number of recent reports averaged.
    forecast_horizon: float = 60.0
    forecast_reports: int = 4
    # Traffic management centre: None (no ramp control) or 'alinea'. ALINEA (Papageorgiou,
    # Hadj-Salem & Blosseville 1991) updates the release rate every report_interval s from the
    # occupancy measured at alinea_detector: r_k = clip(r_{k-1} + K_R (o* - o_k), rate_min, rate_max).
    ramp_control: Optional[str] = None
    # Detector 1.4 km: downstream of most merges (merges spread along the acceleration lane, mean
    # 1.33 km); its flow-occupancy data show the congested branch, while 1.6 km never leaves free flow.
    alinea_detector: float = 1400.0
    alinea_target_occ: float = 0.14     # o*, fraction of time occupied
    alinea_gain: float = 7000.0         # K_R, veh/h per unit occupancy (= 70 veh/h per %)
    rate_min: float = 200.0             # veh/h
    rate_max: float = 900.0             # veh/h (shortest signal cycle 4 s, single-lane one car per green)
    # Queue override: None = off (default). With a number, more vehicles than this before the stop line
    # force the maximum rate (protects the street; tested as an ablation). The ramp holds about 28.
    ramp_storage: Optional[int] = None
    report_stale: float = 60.0          # s without a valid occupancy report before the fallback
    fallback_rate: float = 500.0        # veh/h, fixed release rate used without valid reports
    main_entry_speed: float = 25.0
    entry_brake: float = 0.0
    eval_start: float = 300.0
    congested_kmh: float = 40.0
    detectors: tuple = (500.0, 1000.0, 1400.0, 1600.0)
    # IDM: v0 (m/s), T (s), a/b (m/s^2), s0/length (m), delta. a = 2.0 with b = 2.0 and T = 1.2 s
    # keeps platoons string-stable at every speed, so slowdowns at the merge do not grow into
    # stop-and-go waves; single-lane capacity is about 2,200 veh/h.
    v0: float = 33.33
    T: float = 1.2
    a: float = 2.0
    b: float = 2.0
    s0: float = 2.0
    length: float = 5.0
    delta: float = 4.0
    amin: float = -4.0
    amax: float = 2.0
    # Constant-acceleration heuristic (Kesting, Treiber & Helbing 2010): softens IDM braking when
    # a vehicle cuts in at a short gap but is not slower; cool = 0 gives plain IDM.
    cool: float = 0.99
    # ACC (adaptive cruise control). acc_share is the equipped fraction of both streams. Each arrival
    # draws one uniform number from its own random stream and is equipped if it is below acc_share, so
    # arrivals are identical for every share and assignments are nested (every vehicle equipped at 25%
    # is also equipped at 50% and 75%). Equipped vehicles drive with acc_command on the mainline; ramp
    # vehicles drive and merge like HDVs and switch the ACC on once they are on the mainline.
    acc_share: float = 0.0
    # ACC controller: the following law of Gunter et al. (2020),
    # u = kp [s - (eta + h v)] - kv (v - v_leader), with their fitted kp and standstill gap eta (one
    # commercial vehicle). Two project choices: h = 1.27 s (their fit, 1.6881 s, is the longest gap
    # setting; with 1.27 s the capacity of 100% ACC traffic at v0 equals the IDM capacity, about
    # 2,190 veh/h) and kv = 0.80 s^-1, the smallest round value that makes platoons string stable by
    # their criterion kp h^2 + 2 kv h - 2 >= 0 (needs kv >= 0.779). Their fitted kv = 0.2692 fails the
    # criterion and made the merge bottleneck collapse (results/acc_ablation_kv/fitted_kv_0.2692).
    acc_kp: float = 0.0131             # s^-2
    acc_kv: float = 0.80               # s^-1  (Gunter et al. fit: 0.2692)
    acc_eta: float = 7.5699            # m
    acc_h: float = 1.27                # s
    # Driver takeover (project rule; the fitted law does not cover cut-ins): when the driver's own
    # car-following response (the HDV law, IDM+CAH) brakes harder than acc_takeover_b and harder than
    # the ACC, the driver brakes instead (after the collision-warning fallback in Adebisi et al. 2020).
    acc_takeover_b: float = 2.0        # m/s^2
    # Fallback (project rule) for a missing sensor reading: brake at this rate until it returns.
    acc_fallback_decel: float = 2.0    # m/s^2
    # Sensor delay (degraded-information test; 0 = off): the gap and leader speed given to the ACC are the
    # readings taken acc_sensor_delay s earlier (a multiple of dt); own speed is current. A vehicle whose
    # ACC has just switched on holds its first reading until the delay has passed.
    acc_sensor_delay: float = 0.0      # s


def idm(v, gap=np.inf, leader_v=0.0, c=None, v0=None):
    """Requested IDM acceleration (m/s^2); v0 may be a per-vehicle desired speed."""
    c = c or Config()
    v0 = c.v0 if v0 is None else v0
    desired = c.s0 + np.maximum(0.0, v * c.T + v * (v - leader_v) / (2 * math.sqrt(c.a * c.b)))
    return c.a * (1 - (v / v0) ** c.delta - (desired / np.maximum(gap, 1e-09)) ** 2)


def drive(v, gap, lv, la, c, v0=None):
    """Car-following acceleration: IDM, blended with the constant-acceleration heuristic (CAH)
    when IDM brakes harder than CAH would (IDM+CAH, Kesting et al. 2010). la: leader acceleration."""
    a_idm = idm(v, gap, lv, c, v0)
    if c.cool <= 0:
        return a_idm
    v, gap, lv, la = np.broadcast_arrays(np.asarray(v, float), np.asarray(gap, float), np.asarray(lv, float), np.asarray(la, float))
    finite = np.isfinite(gap)
    g = np.where(finite, np.maximum(gap, 1e-9), 1.0)
    al = np.minimum(la, c.a)
    dv = v - lv
    denom = lv * lv - 2 * g * al
    cond = (lv * dv <= -2 * g * al) & (denom > 1e-9)
    a_cah = np.where(cond, v * v * al / np.where(denom > 1e-9, denom, 1.0),
                     al - np.where(dv > 0, dv * dv, 0.0) / (2 * g))
    blend = (1 - c.cool) * a_idm + c.cool * (a_cah + c.b * np.tanh((a_idm - a_cah) / c.b))
    acc = np.where(~finite | (a_idm >= a_cah), a_idm, blend)
    # Collision-avoidance floor: when closing in, brake at least as hard as needed to come down
    # to the leader's speed 0.5 m behind it (constant leader speed).
    dv = v - lv
    room = np.maximum(g - 0.5, 0.05)
    need = -np.where(dv > 0, dv * dv, 0.0) / (2 * room)
    # Only when that takes more than comfortable braking (ordinary approaches stay pure IDM+CAH).
    return np.where(finite & (dv > 0) & (need < -c.b), np.minimum(acc, need), acc)


def acc_inputs(x, v, length):
    """ACC observation interface (onboard sensing) for one lane sorted front to back: the net gap to
    the vehicle directly ahead in the same lane and that vehicle's speed, as a radar measures them
    (gap = inf: nothing ahead). Readings are exact. Nothing else reaches the controller: no leader
    acceleration, no vehicles further ahead or on the acceleration lane, no V2V/I2V messages."""
    x, v = np.asarray(x, float), np.asarray(v, float)
    gap = np.r_[np.inf, np.diff(-x) - length]
    leader_v = np.r_[v[:1], v[:-1]]
    return gap, leader_v


def delayed_reading(history, reading, steps):
    """Sensor delay: append the current reading to a vehicle's history (a deque) and return the reading
    taken `steps` updates earlier (the oldest available while the history is shorter than that)."""
    history.append(reading)
    while len(history) > steps + 1:
        history.popleft()
    return history[0]


def acc_command(v, gap, leader_v, c, valid=True):
    """ACC acceleration command (m/s^2) from onboard readings only.

    Cruise: the IDM free-road term with the common v0 and a, so ACC and IDM differ only in following.
    Following (Gunter et al. 2020): u = kp [s - (eta + h v)] - kv (v - v_leader); with a vehicle ahead
    the smaller of following and cruise is used. Fallback (project rule): without a valid reading,
    brake at acc_fallback_decel. The command is held for one step (command interval dt, no actuator
    lag); driver_takeover may override it, and the vehicle applies the result clipped to [amin, amax]."""
    v, gap, leader_v, valid = np.broadcast_arrays(np.asarray(v, float), np.asarray(gap, float),
                                                  np.asarray(leader_v, float), np.asarray(valid, bool))
    cruise = c.a * (1 - (v / c.v0) ** c.delta)
    ahead = np.isfinite(gap)
    s = np.where(ahead, gap, 0.0)
    follow = c.acc_kp * (s - (c.acc_eta + c.acc_h * v)) - c.acc_kv * (v - leader_v)
    u = np.where(ahead, np.minimum(follow, cruise), cruise)
    return np.where(valid, u, -c.acc_fallback_decel)


def driver_takeover(u_acc, a_driver, c, active=False):
    """Driver takeover (project rule): the fitted ACC law does not cover cut-ins and brakes weakly at
    short gaps. The driver takes over when their own response a_driver (the HDV law, IDM+CAH) brakes
    harder than acc_takeover_b and harder than the ACC command u_acc, and hands back to the ACC once
    a_driver is no longer below u_acc (so the acceleration is continuous at the handover). `active`:
    takeover state from the previous step. Adebisi et al. (2020) likewise hand emergency braking to a
    conventional car-following model while a collision warning is active. Returns (acceleration, takeover)."""
    u_acc, a_driver, active = np.broadcast_arrays(np.asarray(u_acc, float), np.asarray(a_driver, float),
                                                  np.asarray(active, bool))
    take = (a_driver < u_acc) & (active | (a_driver < -c.acc_takeover_b))
    return np.where(take, a_driver, u_acc), take


def motion(v, a, t):
    v, a, t = np.broadcast_arrays(v, a, t)
    stop = np.full(v.shape, np.inf)
    np.divide(-v, a, out=stop, where=a < 0)
    h = np.minimum(t, stop)
    return (v * h + 0.5 * a * h * h, np.maximum(0.0, v + a * h))


def continuous_min_gap(gap, vf, af, vl, al, dt):
    gap, vf, af, vl, al = map(np.asarray, (gap, vf, af, vl, al))
    sf, sl = (np.full(vf.shape, dt), np.full(vl.shape, dt))
    np.divide(-vf, af, out=sf, where=af < 0)
    np.divide(-vl, al, out=sl, where=al < 0)
    knots = np.sort(np.stack([np.zeros_like(vf), np.clip(sf, 0, dt), np.clip(sl, 0, dt), np.full_like(vf, dt)]), axis=0)
    best = gap.copy()

    def evaluate(t):
        return gap + motion(vl, al, t)[0] - motion(vf, af, t)[0]
    for lo, hi in zip(knots[:-1], knots[1:]):
        mid = (lo + hi) / 2
        rel_a = np.where(mid < sl, al, 0.0) - np.where(mid < sf, af, 0.0)
        rel_v = motion(vl, al, lo)[1] - motion(vf, af, lo)[1]
        root = lo.copy()
        np.divide(-rel_v, rel_a, out=root, where=np.abs(rel_a) > 1e-12)
        root = np.where(np.abs(rel_a) > 1e-12, lo + root, lo)
        best = np.minimum(best, np.minimum(evaluate(hi), evaluate(np.clip(root, lo, hi))))
    return best


def crossing_time(distance, v, a, dt):
    lo, hi = (0.0, dt)
    for _ in range(32):
        mid = (lo + hi) / 2
        if float(motion(v, a, mid)[0]) < distance:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def schedule(rate, end, rng, start=0.0):
    if rate <= 0:
        return []
    out, t = ([], start)
    while True:
        t += rng.exponential(3600 / rate)
        if t >= end:
            return out
        out.append(float(t))


def schedule_profile(segments, rng):
    out = []
    for start, end, rate in segments:
        if end > start:
            out.extend(schedule(rate, end, rng, start))
    return out


def free_flow_time(v_entry, distance, c):
    """Travel time of a lone mainline IDM vehicle over `distance` from `v_entry`."""
    x, v, t = 0.0, float(v_entry), 0.0
    while x < distance:
        a = float(np.clip(idm(v, c=c), c.amin, c.amax))
        dx, nv = motion(v, a, c.dt)
        dx, nv = float(dx), float(nv)
        if x + dx >= distance:
            return t + crossing_time(distance - x, v, a, c.dt)
        x, v, t = x + dx, nv, t + c.dt
    return t


def ramp_free_time(c):
    """Travel time of a lone ramp vehicle from the ramp entrance to the road end: the ramp
    road at ramp_v0, then the acceleration lane, merging as soon as it is fully on it."""
    xs = c.merge_x - c.acc_length
    x, v, t = xs - c.ramp_length, float(c.ramp_entry_speed), 0.0
    lane = 1
    while True:
        if lane == 1 and x >= xs + c.length:
            lane = 0
        v0 = c.ramp_v0 if (lane == 1 and x < xs) else c.v0
        a = float(np.clip(idm(v, c=c, v0=v0), c.amin, c.amax))
        dx, nv = motion(v, a, c.dt)
        dx, nv = float(dx), float(nv)
        if x + dx >= c.road_end:
            return t + crossing_time(c.road_end - x, v, a, c.dt)
        x, v, t = x + dx, nv, t + c.dt


def merge_test(car, L, F, c, xs):
    """Safety test for a lane change from the acceleration lane. Returns (ok, s_l, s_f, a_self, a_f)."""
    s_l = L['x'] - car['x'] - c.length if L else math.inf
    s_f = car['x'] - F['x'] - c.length if F else math.inf
    room = max(c.merge_x - c.end_margin - car['x'], 0.05)
    if c.merge_x - car['x'] < c.force_zone or car['v'] ** 2 / (2 * room) > 0.9 * c.end_trigger:
        # Forced merge near the lane end (or once the vehicle would have to start braking for it):
        # take a gap that is physically safe even if both then brake at |amin|, or one where the
        # vehicle has 30 m or more of free road to accelerate briskly (a_go) and the follower copes
        # braking at most 0.6 |amin|. No courtesy from the mainline is assumed.
        bm = -c.amin
        if s_l < 1.0 or s_f < 1.0 or (L and s_l < 1.0 + max(0.0, car['v'] ** 2 - L['v'] ** 2) / (2 * bm)):
            return False, s_l, s_f, None, None
        safe = not F or s_f >= 1.0 + max(0.0, F['v'] ** 2 - car['v'] ** 2) / (2 * bm)
        a_go = float(drive(car['v'], s_l, L['v'], L.get('a', 0.0), c)) if L else float(idm(car['v'], c=c))
        a_go = min(a_go, c.acc_lane_a)
        brisk = (a_go >= 0.8 * c.acc_lane_a and s_l >= 30.0 and
                 (not F or s_f >= 1.0 + max(0.0, F['v'] - car['v']) ** 2 / (2 * (0.6 * bm + a_go))))
        ok = safe or brisk
        a_f = float(drive(F['v'], s_f, car['v'], max(a_go, 0.0), c)) if (ok and F) else None
        return ok, s_l, s_f, None, a_f
    # Urgency u grows along the lane: the braking a merge may impose grows from b_safe to
    # b_safe_end and the smallest accepted gap shrinks.
    u = min(max((car['x'] - xs) / c.acc_length, 0.0), 1.0)
    gmin = c.merge_gap_min * (1 - 0.75 * u)          # squeezing in near the lane end
    if s_l < gmin or s_f < gmin:
        return False, s_l, s_f, None, None
    # Gaps as they will be merge_horizon s later if speeds are kept (a closing gap must stay open).
    h = c.merge_horizon
    if L and s_l + (L['v'] - car['v']) * h < c.merge_gap_min:
        return False, s_l, s_f, None, None
    if F and s_f + (car['v'] - F['v']) * h < c.merge_gap_min:
        return False, s_l, s_f, None, None
    bs = c.b_safe + (c.b_safe_end - c.b_safe) * u * u
    # The merging vehicle's acceleration once it is on the mainline (following its new leader;
    # it no longer brakes for the lane end). Its new follower is judged against that.
    a_self = float(drive(car['v'], s_l, L['v'], L.get('a', 0.0), c)) if L else float(idm(car['v'], c=c))
    if a_self < -bs:
        return False, s_l, s_f, a_self, None
    a_post = min(a_self, c.amax)
    # Speed matching within the braking budget: a faster follower can come down to the merging
    # vehicle's speed braking at most bs, and the merging vehicle can come down to its new
    # leader's speed the same way, each with 1 m to spare.
    if F and s_f < 1.0 + max(0.0, F['v'] - car['v']) ** 2 / (2 * (bs + max(a_post, 0.0))):
        return False, s_l, s_f, a_self, None
    # ... and, whatever the merging vehicle does next, the follower can still come down to its
    # present speed braking at |amin|.
    if F and s_f < 1.0 + max(0.0, F['v'] - car['v']) ** 2 / (2 * -c.amin):
        return False, s_l, s_f, a_self, None
    if L and s_l < 1.0 + max(0.0, car['v'] - L['v']) ** 2 / (2 * (bs + max(L.get('a', 0.0), 0.0))):
        return False, s_l, s_f, a_self, None
    a_f = float(drive(F['v'], s_f, car['v'], a_post, c)) if F else None
    if a_f is not None and a_f < -bs:
        return False, s_l, s_f, a_self, a_f
    return True, s_l, s_f, a_self, a_f


def target_speed(z, main, mx, c, xs):
    """Desired speed of a vehicle on the acceleration lane: line up with the nearest mainline gap
    it could merge into and match that gap's speed (feasible front positions leave merge_gap_min to
    both neighbours). Side by side with a mainline vehicle it pushes ahead or drops back; a faster
    vehicle closing in from behind is let past; with no feasible gap nearby it lets traffic pass."""
    x, v = z['x'], z['v']
    k = bisect.bisect_left(mx, x)
    # Side by side with a mainline vehicle at a similar speed: push ahead if already in front
    # of it, otherwise drop back behind it (avoids driving alongside it to the lane end).
    for m in (main[k - 1] if k > 0 else None, main[k] if k < len(main) else None):
        if m and abs(m['x'] - x) < c.length + c.merge_gap_min and abs(m['v'] - v) < 3.0:
            if x > m['x'] and v < c.v0 - 1.0:
                return c.v0 + 3.0
            return max(m['v'] - c.drop_dv, 2.0)
    # A faster mainline vehicle behind that would catch up before this vehicle could match its
    # speed: let it pass and merge behind it.
    if k > 0:
        F = main[k - 1]
        dv = F['v'] - v
        a_av = max(c.acc_lane_a * (1 - (v / c.v0) ** c.delta), 0.3)
        if dv > 1.0 and x - c.length - F['x'] < dv * dv / (2 * a_av) + c.merge_gap_min + 5.0:
            return max(F['v'] - c.drop_dv, 2.0)
    lead = c.merge_gap_min
    lo = bisect.bisect_left(mx, x - 200.0)
    hi = bisect.bisect_left(mx, x + 150.0)
    best = None
    for i in range(lo, hi + 1):
        F = main[i - 1] if i > 0 else None
        L = main[i] if i < len(main) else None
        if F is None and L is None:
            return c.v0
        low = F['x'] + c.length + c.merge_gap_min if F else -math.inf
        high = L['x'] - c.length - lead if L else math.inf
        if low > high:
            continue
        target = min(max(x, low), high) if (F is None or L is None) else 0.5 * (low + high)
        vg = (F['v'] + L['v']) / 2 if F and L else (L or F)['v']
        if best is None or abs(target - x) < abs(best[0] - x):
            best = (target, vg)
    if best is None:
        near = [m['v'] for m in main[max(lo, 0):hi + 1]] or [c.v0]
        return max(min(near) - c.drop_dv, 2.0)
    target, vg = best
    return min(max(vg + c.align_k * (target - x), 2.0), c.v0 + 2.0)


def run(c, record=True):
    """Run one deterministic scenario and return all data in memory (no files)."""
    if c.dt <= 0 or abs(round(c.duration / c.dt) * c.dt - c.duration) > 1e-07:
        raise ValueError('duration must be a multiple of positive dt')
    if abs(round(1.0 / c.dt) * c.dt - 1.0) > 1e-07:
        raise ValueError('dt must divide the 1 s sampling period')
    if not 0 <= c.demand_end <= c.duration:
        raise ValueError('invalid demand interval')
    if not 0 < c.merge_x < c.road_end:
        raise ValueError('invalid geometry')
    if not (0 < c.acc_length and c.ramp_length > 0 and c.merge_x - c.acc_length - c.ramp_length > 0):
        raise ValueError('invalid ramp geometry')
    if c.ramp_release_rate is not None and c.ramp_release_rate <= 0:
        raise ValueError('invalid ramp release rate')
    if (not 0.0 <= c.acc_share <= 1.0 or min(c.acc_kp, c.acc_kv, c.acc_eta, c.acc_h) < 0
            or min(c.acc_takeover_b, c.acc_fallback_decel) <= 0):
        raise ValueError('invalid ACC settings')
    if c.acc_sensor_delay < 0 or abs(round(c.acc_sensor_delay / c.dt) * c.dt - c.acc_sensor_delay) > 1e-07:
        raise ValueError('the ACC sensor delay must be a non-negative multiple of dt')
    delay_steps = round(c.acc_sensor_delay / c.dt)
    detector_x = sorted({float(d) for d in c.detectors if 0 < d < c.road_end} | {float(c.road_end)})
    occ_x = [d for d in detector_x if d < c.road_end]          # detectors that report occupancy
    if c.ramp_control not in (None, 'alinea'):
        raise ValueError('unknown ramp control')
    if c.ramp_control is not None and c.ramp_release_rate is not None:
        raise ValueError('use either a fixed release rate or ramp control')
    if c.report_interval <= 0 or abs(round(c.report_interval / c.dt) * c.dt - c.report_interval) > 1e-07:
        raise ValueError('report interval must be a positive multiple of dt')
    if (c.forecast_reports < 1 or c.forecast_horizon < 0
            or abs(round(c.forecast_horizon / c.report_interval) * c.report_interval - c.forecast_horizon) > 1e-07):
        raise ValueError('forecast horizon must be a multiple of the report interval')
    alinea_x = next((d for d in occ_x if abs(d - c.alinea_detector) < 1e-6), None)
    if not (0 <= c.detector_miss_prob < 1) or c.occupancy_noise_sd < 0 or c.report_delay < 0 or \
            abs(round(c.report_delay / c.report_interval) * c.report_interval - c.report_delay) > 1e-07:
        raise ValueError('invalid detector defect settings')
    delay_cycles = round(c.report_delay / c.report_interval)
    x_meter = (c.merge_x - c.acc_length) if c.meter_x is None else float(c.meter_x)
    ramp_capacity = int((x_meter - (c.merge_x - c.acc_length - c.ramp_length)) // (c.length + c.s0))  # stopped vehicles
    if not (c.merge_x - c.acc_length - c.ramp_length < x_meter <= c.merge_x - c.acc_length) or c.meter_checkin <= 0:
        raise ValueError('the meter stop line must lie on the ramp road')
    if c.ramp_control == 'alinea':
        if alinea_x is None:
            raise ValueError('ALINEA needs an occupancy detector at alinea_detector')
        if (not (0 < c.rate_min <= c.fallback_rate <= c.rate_max) or (c.ramp_storage is not None and c.ramp_storage < 0)
                or c.report_stale < c.report_interval):
            raise ValueError('invalid ALINEA settings')
    top = c.rate_max if c.ramp_control == 'alinea' else c.ramp_release_rate
    if top is not None and (c.meter_green <= 0 or c.meter_min_red < 0
                            or 3600.0 / top < c.meter_green + c.meter_min_red - 1e-9):
        raise ValueError('signal timing: the shortest cycle 3600 / max rate must hold green + minimum red')
    xs = c.merge_x - c.acc_length                  # start of the acceleration lane
    x_rs = xs - c.ramp_length                      # ramp entrance (mainline coordinates)

    streams = np.random.SeedSequence(c.seed).spawn(4)    # mainline, ramp, detector errors, ACC equipment
    profiles = []
    for prof in (c.main_profile, c.ramp_profile):
        if any(not (0 <= a <= b <= c.demand_end) or r < 0 for a, b, r in prof):
            raise ValueError('demand profile segments must lie within [0, demand_end]')
        profiles.append([tuple(map(float, seg)) for seg in prof])
    arrivals = [schedule_profile(prof, np.random.default_rng(s)) for prof, s in zip(profiles, streams[:2])]
    # ACC equipment: one uniform number per arrival from its own stream (nested across shares).
    eq_rng = np.random.default_rng(streams[3])
    equip_u = [eq_rng.random(len(arrivals[0])), eq_rng.random(len(arrivals[1]))]
    equipped = {}                # vehicle id -> ACC-equipped, decided at arrival
    free_time = [free_flow_time(c.main_entry_speed, c.road_end, c), ramp_free_time(c)]
    origin_distance = [c.road_end, c.road_end - x_rs]
    # Delay reference: a lone vehicle's free-flow time from the same origin, spread evenly over its
    # route, so the integrated delay of a completed trip equals its trip delay (delay_s).
    free_pace = [free_time[o] / origin_distance[o] for o in (0, 1)]

    pointers = [0, 0]
    queues = [deque(), deque()]
    main, ramp = [], []          # vehicles on the mainline (lane 0) and on the ramp road / acceleration lane (lane 1)
    uid = 0
    logs, frames, trajectories, events, trips, detectors = [], [], [], [], [], []
    reject = Counter()
    min_gap = math.inf
    amin_seen = 0.0
    vmax = 0.0
    clips = 0
    merges = 0
    stops_at_end = 0
    offered = entered = exited = 0
    accumulated_delay = 0.0
    speed_sum = speed_n = 0.0
    max_wait = [0, 0]
    max_onramp = 0
    conservation_checks = 0
    alinea = c.ramp_control == 'alinea'
    metered = c.ramp_release_rate is not None or alinea
    release_interval = 3600.0 / c.ramp_release_rate if c.ramp_release_rate is not None else None
    last_slot = -1
    token = False
    slots_used = slots_lost = 0
    green_open, green_until = False, -math.inf     # signal timing: current green, if any
    signal_log = []                                  # [green start, green end, vehicles released] per cycle
    stopped_ids = set()
    takeover_episodes = takeover_steps = 0
    acc_steps = 0                                        # lane-0 ACC vehicle-steps
    hard_brake_steps = Counter()                         # lane-0 vehicle-steps braking harder than 3 m/s^2
    min_gap_type = {'HDV': math.inf, 'ACC': math.inf}    # lane-0 within-step minimum gap by follower type

    # Observation: presence intervals at the mainline detectors and the two ramp counters. Each
    # passage carries a flag `missed` (detector defect); true values ignore the flag.
    sensor_ids = {d: f'D{int(round(d)):04d}' for d in occ_x}
    det_rng = np.random.default_rng(streams[2])
    on_since = {d: {} for d in occ_x}        # vehicle id -> (time its front reached the detector, missed)
    presences = {d: [] for d in occ_x}       # completed (t_on, t_off, missed) since the last report
    onsets = {d: [] for d in occ_x}          # (presence start time, missed) since the last report
    ramp_events = {'RAMP_IN': [], 'RAMP_OUT': []}   # (time, missed)
    cum_true, cum_meas = Counter(), Counter()   # detector counters keep running when a report is lost
    reports, tmc_log, compiled = [], [], []
    true_queue_at = {}
    report_steps = round(c.report_interval / c.dt)
    # TMC state.
    rate = c.rate_max if alinea else c.ramp_release_rate
    next_open, last_open = 0.0, None         # variable-rate release slots (ALINEA)
    last_valid_data_t = None
    q_hat, q_hat_ok = 0, True
    flows_in = deque(maxlen=c.forecast_reports)
    flows_out = deque(maxlen=c.forecast_reports)
    modes = Counter()
    cycle_released = cycle_lost = 0

    def missed():
        return bool(c.detector_miss_prob > 0 and det_rng.random() < c.detector_miss_prob)

    def compile_reports(t1):
        """Detector reports for [t1 - report_interval, t1): what the detectors measured (with any
        defects) and the true values (perfect detectors; scoring only). A report is lost when its
        interval ends inside a report_dropout window; otherwise it reaches the TMC report_delay s later."""
        t0 = t1 - c.report_interval
        lost = any(a <= t1 < b for a, b in c.report_dropout)
        meas, true = {}, {}
        for d in occ_x:
            done, ongoing = presences[d], list(on_since[d].values())

            def busy(seen_only):
                return (sum(min(b, t1) - max(a, t0) for a, b, m in done if not (seen_only and m))
                        + sum(t1 - max(a, t0) for a, m in ongoing if not (seen_only and m)))
            n_true, n_meas = len(onsets[d]), sum(1 for _, m in onsets[d] if not m)
            occ_true = max(0.0, busy(False)) / c.report_interval
            occ_meas = max(0.0, busy(True)) / c.report_interval
            if c.occupancy_noise_sd > 0:
                occ_meas = min(max(occ_meas + det_rng.normal(0.0, c.occupancy_noise_sd), 0.0), 1.0)
            # Speed of a vehicle = length / time it covered the detector (single loop, known length).
            speeds = [c.length / (b - a) for a, b, m in done if b > a and not m]
            sid = sensor_ids[d]
            cum_true[sid] += n_true
            cum_meas[sid] += n_meas
            meas[sid] = dict(count=n_meas, cum_count=cum_meas[sid], occupancy=occ_meas,
                             mean_speed_mps=float(np.mean(speeds)) if speeds else None)
            true[sid] = dict(count=n_true, occupancy=occ_true)
            done.clear()
            onsets[d].clear()
        for key, ev in ramp_events.items():
            n_true, n_meas = len(ev), sum(1 for _, m in ev if not m)
            cum_true[key] += n_true
            cum_meas[key] += n_meas
            meas[key] = dict(count=n_meas, cum_count=cum_meas[key], occupancy=None, mean_speed_mps=None)
            true[key] = dict(count=n_true, occupancy=None)
            ev.clear()
        for sid, val in meas.items():
            reports.append(dict(sensor_id=sid, interval_start_s=t0, interval_end_s=t1,
                                **({k: None for k in val} if lost else val),
                                quality_flag='missing' if lost else 'ok',
                                received_s=None if lost else t1 + c.report_delay,
                                count_true=true[sid]['count'], occupancy_true=true[sid]['occupancy']))
        compiled.append(dict(t1=t1, meas=meas, true=true, lost=lost))

    def ramp_waiting():
        """True number of ramp vehicles that arrived but have not passed the stop line (scoring only)."""
        return len(queues[1]) + sum(1 for z in ramp if 'meter_t' not in z)

    def tmc_cycle(t1):
        """One TMC update: observe, estimate, predict, decide, act (evaluation uses the log)."""
        nonlocal rate, next_open, last_valid_data_t, q_hat, q_hat_ok, cycle_released, cycle_lost
        true_queue_at[round(t1, 6)] = ramp_waiting()
        compile_reports(t1)
        # Observe: the report that arrives now is the one whose interval ended report_delay s ago.
        k = len(compiled) - 1 - delay_cycles
        rep = compiled[k] if k >= 0 and not compiled[k]['lost'] else None
        data_t = rep['t1'] if rep else None
        # Estimate: vehicles before the stop line = cumulative arrivals (queue tail) - passages (stop line).
        if rep:
            q_hat = max(0, rep['meas']['RAMP_IN']['cum_count'] - rep['meas']['RAMP_OUT']['cum_count'])
            flows_in.append(rep['meas']['RAMP_IN']['count'] / c.report_interval)
            flows_out.append(rep['meas']['RAMP_OUT']['count'] / c.report_interval)
        q_hat_ok = rep is not None
        # Predict (advisory only; not used by the controller): Q_hat + H (q_in - q_out), H s after the data.
        forecast = (max(0.0, q_hat + c.forecast_horizon * (np.mean(flows_in) - np.mean(flows_out)))
                    if flows_in else float(q_hat))
        sid = sensor_ids.get(alinea_x) if alinea_x is not None else None
        occ = rep['meas'][sid]['occupancy'] if (rep and sid) else None   # only reports that arrived
        occ_true = rep['true'][sid]['occupancy'] if (rep and sid) else None
        if occ is not None:
            last_valid_data_t = data_t
        prev = rate
        if alinea:
            age = math.inf if last_valid_data_t is None else t1 - last_valid_data_t
            if age > c.report_stale + c.report_delay:
                mode, rate = 'fallback', c.fallback_rate
            elif c.ramp_storage is not None and q_hat_ok and q_hat > c.ramp_storage:
                mode, rate = 'override', c.rate_max
            elif occ is None:
                mode = 'hold'
            else:
                mode = 'alinea'
                rate = min(max(prev + c.alinea_gain * (c.alinea_target_occ - occ), c.rate_min), c.rate_max)
            if rate != prev and last_open is not None:
                next_open = last_open + 3600.0 / rate      # the new rate applies from the last release slot
        else:
            mode = 'fixed' if metered else 'none'
        modes[mode] += 1
        tmc_log.append(dict(
            t_s=t1, data_time_s=data_t, report_ok=rep is not None, occupancy=occ, occupancy_true=occ_true,
            queue_est_veh=q_hat, queue_true_veh=true_queue_at.get(round(data_t, 6)) if rep else None,
            queue_est_ok=q_hat_ok, forecast_veh=forecast,
            forecast_target_s=(data_t if rep else t1) + c.forecast_horizon, persistence_veh=float(q_hat),
            released_veh=cycle_released, slots_lost=cycle_lost,
            rate_prev_veh_h=prev, rate_veh_h=rate, mode=mode))
        cycle_released = cycle_lost = 0

    def admission_ok(lane, v, x):
        ahead = [z for z in lane if z['x'] >= x]
        if not ahead:
            return True
        leader = min(ahead, key=lambda z: z['x'])
        gap = leader['x'] - x - c.length
        return (gap >= c.s0 and float(idm(v, gap, leader['v'], c)) >= -c.entry_brake
                and gap >= c.s0 + max(0.0, (v * v - leader['v'] ** 2) / (-2 * c.amin)))

    steps = round(c.duration / c.dt)
    for step in range(steps):
        t = step * c.dt
        if step > 0 and step % report_steps == 0:
            tmc_cycle(t)
        for origin in (0, 1):
            while pointers[origin] < len(arrivals[origin]) and arrivals[origin][pointers[origin]] <= t + 1e-09:
                scheduled = arrivals[origin][pointers[origin]]
                equipped[uid] = bool(equip_u[origin][pointers[origin]] < c.acc_share)
                pointers[origin] += 1
                queues[origin].append((uid, scheduled))
                if origin == 1:
                    ramp_events['RAMP_IN'].append((t, missed()))
                uid += 1
                offered += 1
                accumulated_delay += t - scheduled
        if queues[0] and admission_ok(main, c.main_entry_speed, 0.0):
            i, scheduled = queues[0].popleft()
            main.append(dict(id=i, origin=0, lane=0, x=0.0, v=c.main_entry_speed, scheduled=scheduled, entry=t,
                             type='ACC' if equipped.pop(i) else 'HDV'))
            entered += 1
        # Ramp entrance (optionally metered: one release per slot, unused slots are lost).
        # At the upper bound the ALINEA meter rests in green (as if switched off): while it lasts nobody
        # is held. Green is a state, not a lasting permission: a vehicle is committed (released) only once
        # it could no longer stop at the line braking at b, so when metering resumes every vehicle further
        # upstream stops at the red signal.
        resting = alinea and rate >= c.rate_max - 1e-9
        if metered:
            opened = False
            if alinea:
                # Variable rate: a slot opens every 3600 / rate s; a slot that fell behind after a
                # rate change opens now instead of releasing a burst.
                if t + 1e-9 >= next_open:
                    last_open = next_open if next_open > t - c.dt else t
                    next_open = last_open + 3600.0 / rate
                    opened = True
            else:
                slot = int((t + 1e-9) // release_interval)
                if slot != last_slot:
                    last_slot = slot
                    opened = True
            waiting = [z for z in ramp if z['x'] < x_meter and not z.get('released')]
            if resting:
                green_open = False
                for z in waiting:
                    if z['v'] * z['v'] > 2 * c.b * max(x_meter - z['x'], 1e-3):
                        z['released'], z['release_t'], z['release_x'] = True, t, z['x']
            else:
                # Signal timing: green for meter_green s at the start of each cycle, red for the rest.
                # The first waiting vehicle within meter_checkin m may go during the green (one car per
                # green); a green that ends without a vehicle is lost.
                if opened:
                    green_open, green_until = True, (last_open if alinea else t) + c.meter_green
                    signal_log.append([green_until - c.meter_green, green_until, 0])
                if green_open:
                    head = max(waiting, key=lambda z: z['x']) if waiting else None
                    if t < green_until - 1e-9 and head is not None and x_meter - head['x'] <= c.meter_checkin:
                        head['released'], head['release_t'], head['release_x'] = True, t, head['x']
                        slots_used += 1
                        signal_log[-1][2] = 1
                        green_open = False
                    elif t + c.dt >= green_until - 1e-9:
                        slots_lost += 1
                        cycle_lost += 1
                        green_open = False
        if queues[1] and admission_ok(ramp, c.ramp_entry_speed, x_rs):
            i, scheduled = queues[1].popleft()
            ramp.append(dict(id=i, origin=1, lane=1, x=x_rs, v=c.ramp_entry_speed, scheduled=scheduled, entry=t,
                             type='ACC' if equipped.pop(i) else 'HDV'))
            entered += 1

        # Merges: vehicles fully on the acceleration lane, front-most first.
        main.sort(key=lambda z: z['x'])
        if ramp:
            mx = [z['x'] for z in main]
            for car in sorted((z for z in ramp if z['x'] >= xs + c.length), key=lambda z: -z['x']):
                k = bisect.bisect_left(mx, car['x'])
                L = main[k] if k < len(main) else None
                F = main[k - 1] if k > 0 else None
                ok, s_l, s_f, a_self, a_f = merge_test(car, L, F, c, xs)
                if not ok:
                    reject['no_gap'] += 1
                    continue
                rear = dict(rear_id=None, rear_origin=None, rear_type=None, rear_gap_m=None, rear_speed_mps=None,
                            rear_acc_before_mps2=None, rear_acc_after_mps2=None, rear_acc_judged_mps2=None)
                if F:
                    old_gap = L['x'] - F['x'] - c.length if L else np.inf
                    # The merge rule judged the follower with the HDV law (a_f); the logged requests
                    # before and after the merge use the follower's own law.
                    before = float(drive(F['v'], old_gap, L['v'] if L else 0.0, L.get('a', 0.0) if L else 0.0, c))
                    after = a_f
                    if F['type'] == 'ACC':
                        before = float(driver_takeover(acc_command(F['v'], old_gap, L['v'] if L else F['v'], c),
                                                       before, c)[0])
                        after = float(driver_takeover(acc_command(F['v'], s_f, car['v'], c), after, c)[0])
                    rear = dict(rear_id=F['id'], rear_origin=F['origin'], rear_type=F['type'], rear_gap_m=s_f,
                                rear_speed_mps=F['v'], rear_acc_before_mps2=before, rear_acc_after_mps2=after,
                                rear_acc_judged_mps2=a_f)
                ramp.remove(car)
                car['lane'] = 0
                car['merge_t'] = t
                for d in occ_x:          # merged with its rear before a detector: presence starts now
                    if car['x'] - c.length < d < car['x']:
                        m = missed()
                        on_since[d][car['id']] = (t, m)
                        onsets[d].append((t, m))
                main.insert(k, car)
                mx.insert(k, car['x'])
                merges += 1
                reject['accepted'] += 1
                events.append(dict(t=t, id=car['id'], result='accepted', x=car['x'], v=car['v'],
                                   leader_gap_m=None if math.isinf(s_l) else s_l,
                                   follower_gap_m=None if math.isinf(s_f) else s_f,
                                   stopped_before=car['id'] in stopped_ids, **rear))

        if record and step % round(1 / c.dt) == 0:
            allv = main + ramp
            frames.append([round(t, 3), [[z['id'], round(z['x'], 2), round(z['v'] * 3.6, 2), z['lane'], z['origin']]
                                         for z in allv], len(queues[0]), len(queues[1])])
            trajectories.extend(dict(t_s=t, id=z['id'], origin=z['origin'], lane=z['lane'],
                                     x_km=z['x'] / 1000, v_kmh=z['v'] * 3.6) for z in allv)

        # Accelerations from one snapshot (both lanes), then motion.
        main.sort(key=lambda z: z['x'])
        mx = [z['x'] for z in main]
        plan = []
        for lane_id, cars in ((0, main), (1, ramp)):
            if not cars:
                continue
            cars = sorted(cars, key=lambda z: z['x'], reverse=True)
            x = np.array([z['x'] for z in cars])
            v = np.array([z['v'] for z in cars])
            gap = np.r_[np.inf, np.diff(-x) - c.length]
            lv = np.r_[v[0], v[:-1]]
            prev_a = np.array([z.get('a', 0.0) for z in cars])
            la = np.r_[0.0, prev_a[:-1]]
            if len(cars) > 1 and np.min(gap) <= 0:
                raise AssertionError(f'overlap in lane {lane_id} at {t}')
            if lane_id == 0:
                raw = drive(v, gap, lv, la, c)
                is_acc = np.array([z['type'] == 'ACC' for z in cars])
                if is_acc.any():
                    s_acc, lv_acc = acc_inputs(x, v, c.length)      # onboard readings, same lane only
                    if delay_steps:                                    # degraded information: old readings
                        for j in np.flatnonzero(is_acc):
                            s_acc[j], lv_acc[j] = delayed_reading(cars[j].setdefault('readings', deque()),
                                                                  (s_acc[j], lv_acc[j]), delay_steps)
                    was = np.array([z.get('takeover', False) for z in cars])
                    u_acc = acc_command(v, s_acc, lv_acc, c)
                    a_acc, take = driver_takeover(u_acc, raw, c, was)      # raw: the driver's own law
                    raw = np.where(is_acc, a_acc, raw)
                    take &= is_acc
                    acc_steps += int(np.sum(is_acc))
                    takeover_episodes += int(np.sum(take & ~was))
                    takeover_steps += int(np.sum(take))
                    for j in np.flatnonzero(take != was):
                        cars[j]['takeover'] = bool(take[j])
            else:
                # Desired speed: ramp_v0 on the ramp road; on the acceleration lane line up with a
                # mainline gap (target_speed).
                v0 = np.empty(len(cars))
                for j, z in enumerate(cars):
                    if z['x'] < xs:
                        v0[j] = c.ramp_v0
                        continue
                    v0[j] = target_speed(z, main, mx, c, xs)
                raw = drive(v, gap, lv, la, c, v0=v0)
                # On the acceleration lane drivers accelerate harder towards the speed beside them.
                on_lane = x >= xs
                boost = (c.acc_lane_a - c.a) * (1 - (v / v0) ** c.delta)
                raw = np.where(on_lane & (boost > 0), raw + boost, raw)
                # Lane end: brake to stop end_margin before merge_x once that needs more than end_trigger.
                room = c.merge_x - c.end_margin - x
                need = np.where(room > 0.05, v * v / (2 * np.maximum(room, 0.05)), np.inf)
                raw = np.where(need > c.end_trigger, np.minimum(raw, -need), raw)
                raw = np.where((room <= 0.05) & (v <= 0.05), 0.0, raw)
                if metered:
                    # Red signal: a vehicle not yet released treats the stop line as a stopped leader.
                    held = np.array([not resting and z['x'] < x_meter and not z.get('released') for z in cars])
                    if held.any():
                        zero = np.zeros_like(v)
                        a_stop = drive(v, np.maximum(x_meter - x, 1e-3), zero, zero, c, v0=v0)
                        raw = np.where(held, np.minimum(raw, a_stop), raw)
            acc = np.clip(raw, c.amin, c.amax)
            acc = np.where((v <= 0) & (acc < 0), 0, acc)
            if lane_id == 0:
                clips += int(np.sum(raw < c.amin - 1e-09))
                hard = acc < -3.0
                hard_brake_steps['ACC'] += int(np.sum(hard & is_acc))
                hard_brake_steps['HDV'] += int(np.sum(hard & ~is_acc))
            plan.append((lane_id, cars, x, v, gap, acc))

        for lane_id, cars, x, v, gap, acc in plan:
            dx, nv = motion(v, acc, c.dt)
            if lane_id == 1:
                # Never run past the lane end (numerical guard); a vehicle there is stopped.
                over = x + dx > c.merge_x - 0.01
                dx = np.where(over, np.maximum(c.merge_x - 0.01 - x, 0.0), dx)
                nv = np.where(over, 0.0, nv)
                if metered:
                    held = np.array([not resting and z['x'] < x_meter and not z.get('released') for z in cars])
                    stop = held & (x + dx > x_meter - 0.01)            # never run a red light (numerical guard)
                    dx = np.where(stop, np.maximum(x_meter - 0.01 - x, 0.0), dx)
                    nv = np.where(stop, 0.0, nv)
            if not (np.all(np.isfinite(nv)) and np.all(nv >= 0) and np.all(dx >= 0)):
                raise AssertionError('invalid motion')
            if len(cars) > 1:
                cg = continuous_min_gap(gap[1:], v[1:], acc[1:], v[:-1], acc[:-1], c.dt)
                mg = float(np.min(cg))
                min_gap = min(min_gap, mg)
                if lane_id == 0:
                    fol = np.array([z['type'] == 'ACC' for z in cars[1:]])
                    for kind, sel in (('ACC', fol), ('HDV', ~fol)):
                        if sel.any():
                            min_gap_type[kind] = min(min_gap_type[kind], float(cg[sel].min()))
                if mg <= 0:
                    j = int(np.argmin(cg)) + 1
                    lead, fol = cars[j - 1], cars[j]
                    info = (f"follower {fol['id']} o{fol['origin']} v={v[j]:.2f} a={acc[j]:.2f} merged={fol.get('merge_t')} | "
                            f"leader {lead['id']} o{lead['origin']} v={v[j-1]:.2f} a={acc[j-1]:.2f} merged={lead.get('merge_t')} | gap={gap[j]:.2f}")
                    raise AssertionError(f'continuous collision in lane {lane_id} at {t}: {mg} :: {info}')
            amin_seen = min(amin_seen, float(acc.min()))
            vmax = max(vmax, float(nv.max()))
            for j, z in enumerate(cars):
                end = x[j] + dx[j]
                active = c.dt
                travelled = float(dx[j])
                if lane_id == 1 and x[j] < x_meter <= end:
                    if metered and not z.get('released'):
                        if not resting:
                            raise AssertionError(f"vehicle {z['id']} passed a red signal at {t}")
                        z['released'], z['release_t'], z['release_x'] = True, t, x[j]   # passed during rest-in-green
                    # Stop-line counter (RAMP_OUT), also without metering.
                    z['meter_t'] = t + crossing_time(x_meter - x[j], v[j], acc[j], c.dt)
                    ramp_events['RAMP_OUT'].append((z['meter_t'], missed()))
                    cycle_released += 1
                if lane_id == 0:
                    for d in occ_x:
                        # Presence at a detector: from the front crossing it to the rear crossing it.
                        if x[j] < d <= end:
                            t_on = t + crossing_time(d - x[j], v[j], acc[j], c.dt)
                            m = missed()
                            on_since[d][z['id']] = (t_on, m)
                            onsets[d].append((t_on, m))
                        if x[j] < d + c.length <= end and z['id'] in on_since[d]:
                            t_on, m = on_since[d].pop(z['id'])
                            presences[d].append((t_on, t + crossing_time(d + c.length - x[j], v[j], acc[j], c.dt), m))
                    for d in detector_x:
                        if x[j] < d <= end:
                            ct = t + crossing_time(d - x[j], v[j], acc[j], c.dt)
                            detectors.append(dict(t_s=ct, detector_km=d / 1000, id=z['id'], origin=z['origin']))
                            if d == c.road_end:
                                active = ct - t
                                travelled = c.road_end - x[j]
                accumulated_delay += active - travelled * free_pace[z['origin']]
                z['x'] = float(end)
                z['v'] = float(nv[j])
                z['a'] = float(acc[j])
                if lane_id == 1 and z['v'] < 0.5 and z['x'] > c.merge_x - 20 and z['id'] not in stopped_ids:
                    stopped_ids.add(z['id'])
                    stops_at_end += 1
                if lane_id == 0 and end >= c.road_end:
                    exit_t = t + active
                    o = z['origin']
                    trips.append(dict(
                        id=z['id'], origin=o, type=z['type'], scheduled_s=z['scheduled'], entry_s=z['entry'], exit_s=exit_t,
                        merge_s=z.get('merge_t'), release_s=z.get('release_t'), release_x_m=z.get('release_x'), meter_s=z.get('meter_t'),
                        wait_s=z['entry'] - z['scheduled'],
                        delay_s=exit_t - z['scheduled'] - free_time[o]))
                    exited += 1
            if lane_id == 0:
                speed_sum += float(np.sum(v)) * c.dt
                speed_n += len(v) * c.dt

        main = [z for z in main if z['x'] < c.road_end]
        accumulated_delay += c.dt * sum(map(len, queues))
        if offered != exited + len(main) + len(ramp) + sum(map(len, queues)):
            raise AssertionError('vehicle conservation')
        if entered != exited + len(main) + len(ramp):
            raise AssertionError('admission conservation')
        conservation_checks += 1
        max_wait = [max(max_wait[i], len(queues[i])) for i in (0, 1)]
        max_onramp = max(max_onramp, len(ramp))
        if step % round(1 / c.dt) == 0:
            speeds = [z['v'] for z in main]
            logs.append(dict(
                t_s=t + c.dt, main_vehicles=len(main), ramp_vehicles=len(ramp),
                ramp_external=len(queues[1]), main_external=len(queues[0]), ramp_queue=len(queues[1]) + sum(1 for z in ramp if z['v'] < 2.0),
                ramp_before_meter=ramp_waiting(),
                main_mean_kmh=float(np.mean(speeds) * 3.6) if speeds else 0.0,
                main_slow_vehicles=sum(s < 15 for s in speeds), exited=exited, merges=merges))

    for origin in (0, 1):
        for scheduled in arrivals[origin][pointers[origin]:]:
            queues[origin].append((uid, scheduled))
            uid += 1
            offered += 1
            accumulated_delay += c.duration - scheduled
    road = main + ramp
    assert offered == exited + len(road) + sum(map(len, queues))
    assert len({d['id'] for d in detectors if d['detector_km'] == c.road_end / 1000}) == exited

    accepted = events
    main_followers = [e for e in accepted if e['rear_origin'] == 0]
    ramp_trips = [z for z in trips if z['origin'] == 1]
    main_traj = [z for z in trajectories if z['lane'] == 0]

    def section_speed(lo, hi, t0, t1, stat=np.mean):
        vals = [z['v_kmh'] for z in main_traj if lo <= z['x_km'] * 1000 < hi and t0 <= z['t_s'] < t1]
        return float(stat(vals)) if vals else None

    def bottleneck_extent(t0, t1):
        """Congestion indicators over the 30 s bins tb with t0 // 30 <= tb < t1 // 30: congested time at
        the merge approach, queue extent upstream of the merge, whether the queue reaches the entry, and
        the slowest 30 s x 100 m cell before the merge."""
        b0, b1 = t0 // 30, t1 // 30
        cells = {}
        for z in main_traj:
            key = (int(z['t_s'] // 30), int(z['x_km'] * 1000 // 100))
            if not b0 <= key[0] < b1:
                continue
            acc = cells.setdefault(key, [0.0, 0])
            acc[0] += z['v_kmh']
            acc[1] += 1
        mean = {k: a / n for k, (a, n) in cells.items()}
        approach = {}
        for (tb, xb), (a, n) in cells.items():
            if c.merge_x - 500 <= xb * 100 < c.merge_x:
                sa = approach.setdefault(tb, [0.0, 0])
                sa[0] += a
                sa[1] += n
        congested_bins = sum(1 for a, n in approach.values() if a / n < c.congested_kmh)
        top = int(c.merge_x // 100) - 1
        free_kmh = 1.5 * c.congested_kmh
        extent, reaches_entry = 0.0, False
        for tb in {k[0] for k in mean}:
            xb0 = max((xb for xb in range(top, int(xs // 100) - 1, -1) if mean.get((tb, xb), math.inf) < c.congested_kmh), default=None)
            if xb0 is None:
                continue
            xb, tail = xb0, xb0
            while xb >= 0 and mean.get((tb, xb), math.inf) < free_kmh:
                if mean[(tb, xb)] < c.congested_kmh:
                    tail = xb
                xb -= 1
            extent = max(extent, (top - tail + 1) * 100.0)
            reaches_entry = reaches_entry or tail == 0
        pre = [m for (tb, xb), m in mean.items() if (xb + 1) * 100 <= c.merge_x]
        return congested_bins * 30.0, extent, reaches_entry, (min(pre) if pre else None)

    def flow(d_m, t0, t1):
        n = sum(1 for z in detectors if abs(z['detector_km'] * 1000 - d_m) < 1e-6 and t0 <= z['t_s'] < t1)
        return n * 3600 / (t1 - t0)

    def active_discharge(d_m, t0, t1):
        """Bottleneck discharge: flow at detector d_m during the 30 s bins (inside [t0, t1)) in which
        the merge approach (last 500 m before the lane end) averages below congested_kmh, i.e. while
        the bottleneck is active. Returns (veh/h or None, number of such bins)."""
        b0, b1 = int(t0 // 30), int(t1 // 30)
        sums = {}
        for z in main_traj:
            tb = int(z['t_s'] // 30)
            if b0 <= tb < b1 and c.merge_x - 500 <= z['x_km'] * 1000 < c.merge_x:
                a = sums.setdefault(tb, [0.0, 0])
                a[0] += z['v_kmh']
                a[1] += 1
        active = {tb for tb, (s, n) in sums.items() if s / n < c.congested_kmh}
        if not active:
            return None, 0
        n = sum(1 for z in detectors if abs(z['detector_km'] * 1000 - d_m) < 1e-6 and int(z['t_s'] // 30) in active)
        return n * 3600 / (30.0 * len(active)), len(active)

    window = (c.eval_start, c.demand_end) if c.demand_end > c.eval_start else (0.0, max(c.demand_end, c.dt))
    congestion_s, queue_extent, queue_at_entry, pre_merge_min = bottleneck_extent(*window) if record else (None,) * 4
    congestion_full_s, queue_extent_full = bottleneck_extent(0.0, c.duration + 30.0)[:2] if record else (None,) * 2
    sec = {'upstream': (max(0.0, c.merge_x - 1500), max(0.0, c.merge_x - 1000)), 'approach': (c.merge_x - 500, c.merge_x),
           'downstream': (c.merge_x + 200, min(c.merge_x + 700, c.road_end))}
    downstream_d = min((d for d in detector_x if d > c.merge_x), default=c.road_end)
    # Disturbance propagation: speed variation alongside the acceleration lane (where merges happen)
    # and 300-500 m upstream of its start; their ratio < 1 means merge disturbances fade upstream.
    sec['merge_area'] = (xs, c.merge_x)
    sec['far_upstream'] = (max(0.0, xs - 500), max(0.0, xs - 300))
    discharge_active, active_bins = active_discharge(downstream_d, *window) if record else (None, None)
    sd_merge = section_speed(*sec['merge_area'], *window, stat=np.std) if record else None
    sd_far = section_speed(*sec['far_upstream'], *window, stat=np.std) if record else None
    # Forecast evaluation against the true queue at the target time, issued inside the window.
    pairs = [(z['forecast_veh'], z['persistence_veh'], true_queue_at[round(z['forecast_target_s'], 6)]) for z in tmc_log
             if window[0] <= z['t_s'] < window[1] and z['queue_est_ok'] and round(z['forecast_target_s'], 6) in true_queue_at]
    cycles_in_window = [z for z in tmc_log if window[0] <= z['t_s'] < window[1]]
    # Observation error measures (guide: count error per interval, queue-length MAE in vehicles).
    a_sid = f'D{int(round(alinea_x)):04d}' if alinea_x is not None else None
    a_reps = [z for z in reports if z['sensor_id'] == a_sid and z['quality_flag'] == 'ok'
              and window[0] <= z['interval_start_s'] < window[1]]
    q_err = [abs(z['queue_est_veh'] - z['queue_true_veh']) for z in cycles_in_window if z['queue_est_ok']]
    summary = dict(
        config=asdict(c),
        offered=offered, offered_main=len(arrivals[0]), offered_ramp=len(arrivals[1]),
        entered=entered, exited=exited,
        remaining_on_road=len(road), remaining_main_external=len(queues[0]), remaining_ramp_external=len(queues[1]),
        merges=merges, stops_at_lane_end=stops_at_end,
        merges_during_demand=sum(e['t'] < c.demand_end for e in accepted),
        merges_after_demand=sum(e['t'] >= c.demand_end for e in accepted),
        mean_merge_speed_kmh=float(np.mean([e['v'] for e in accepted]) * 3.6) if accepted else None,
        mean_merge_position_m=float(np.mean([e['x'] - xs for e in accepted])) if accepted else None,
        merges_with_mainline_follower=len(main_followers),
        merges_braking_mainline_follower=sum(e['rear_acc_after_mps2'] < -0.1 for e in main_followers),
        merges_hard_braking_mainline_follower=sum(e['rear_acc_after_mps2'] < -3.0 for e in main_followers),
        ramp_metered=metered,
        ramp_release_slots_used=slots_used if metered else None,
        ramp_release_slots_lost=slots_lost if metered else None,
        ramp_control=c.ramp_control,
        tmc_cycles=len(tmc_log),
        tmc_modes=dict(modes),
        reports_missing_cycles=sum(not z['report_ok'] for z in tmc_log),
        mean_release_rate_veh_h=(float(np.mean([z['rate_veh_h'] for z in cycles_in_window]))
                                 if metered and cycles_in_window else None),
        ramp_storage_veh=c.ramp_storage,
        ramp_capacity_veh=ramp_capacity,
        meter_x_m=x_meter,
        max_ramp_queue_veh=max((z['ramp_before_meter'] for z in logs), default=0),
        # More vehicles before the stop line than the ramp road holds (they wait off the road).
        ramp_overflow_s=float(sum(1 for z in logs if z['ramp_before_meter'] > ramp_capacity)),
        total_delay_main_veh_s=sum(z['delay_s'] for z in trips if z['origin'] == 0),
        total_delay_ramp_veh_s=sum(z['delay_s'] for z in trips if z['origin'] == 1),
        detector_count_error_veh=float(np.mean([abs(z['count'] - z['count_true']) for z in a_reps])) if a_reps else None,
        detector_occupancy_mae=float(np.mean([abs(z['occupancy'] - z['occupancy_true']) for z in a_reps])) if a_reps else None,
        queue_estimate_mae_veh=float(np.mean(q_err)) if q_err else None,
        forecast_horizon_s=c.forecast_horizon,
        forecast_pairs=len(pairs),
        forecast_mae_veh=float(np.mean([abs(f - q) for f, _, q in pairs])) if pairs else None,
        persistence_mae_veh=float(np.mean([abs(p - q) for _, p, q in pairs])) if pairs else None,
        mean_ramp_wait_s=float(np.mean([z['wait_s'] for z in ramp_trips])) if ramp_trips else None,
        max_ramp_wait_s=float(max(z['wait_s'] for z in ramp_trips)) if ramp_trips else None,
        free_flow_time_main_s=free_time[0], free_flow_time_ramp_s=free_time[1],
        min_net_gap_m=min_gap if math.isfinite(min_gap) else None,
        min_applied_acceleration_mps2=amin_seen,
        max_speed_kmh=vmax * 3.6,
        brake_clipped_vehicle_steps=clips,
        conservation_checks=conservation_checks,
        continuous_collision_checks_passed=True,
        accumulated_delay_veh_s=accumulated_delay,
        completed_delay_veh_s=sum(z['delay_s'] for z in trips),
        completed_mean_delay_s=float(np.mean([z['delay_s'] for z in trips])) if trips else 0.0,
        main_vehicle_time_mean_kmh=3.6 * speed_sum / speed_n if speed_n else 0.0,
        max_main_external=max_wait[0],
        max_ramp_external=max_wait[1],
        max_ramp_onroad=max_onramp,
        ramp_spillback_s=float(sum(1 for z in logs if z['ramp_external'] > 0)),
        merge_attempts=dict(reject),
        measurement_window_s=list(window),
        downstream_detector_km=downstream_d / 1000,
        downstream_flow_veh_h=flow(downstream_d, *window),
        downstream_flow_300_900_veh_h=flow(downstream_d, *window),
        approach_speed_kmh=section_speed(*sec['approach'], *window) if record else None,
        upstream_speed_kmh=section_speed(*sec['upstream'], *window) if record else None,
        downstream_speed_kmh=section_speed(*sec['downstream'], *window) if record else None,
        approach_speed_sd_kmh=section_speed(*sec['approach'], *window, stat=np.std) if record else None,
        upstream_speed_sd_kmh=section_speed(*sec['upstream'], *window, stat=np.std) if record else None,
        downstream_speed_sd_kmh=section_speed(*sec['downstream'], *window, stat=np.std) if record else None,
        congestion_duration_s=congestion_s,
        max_queue_extent_m=queue_extent,
        congestion_duration_full_run_s=congestion_full_s,
        max_queue_extent_full_run_m=queue_extent_full,
        queue_reaches_entry=queue_at_entry,
        pre_merge_min_cell_kmh=pre_merge_min,
        acc_share=c.acc_share,
        acc_mainline_vehicle_s=acc_steps * c.dt,
        acc_vehicles_main=int(np.sum(equip_u[0] < c.acc_share)),
        acc_vehicles_ramp=int(np.sum(equip_u[1] < c.acc_share)),
        acc_takeover_episodes=takeover_episodes,
        acc_takeover_vehicle_s=takeover_steps * c.dt,
        hard_braking_vehicle_s_hdv=hard_brake_steps['HDV'] * c.dt,
        hard_braking_vehicle_s_acc=hard_brake_steps['ACC'] * c.dt,
        min_net_gap_hdv_follower_m=min_gap_type['HDV'] if math.isfinite(min_gap_type['HDV']) else None,
        min_net_gap_acc_follower_m=min_gap_type['ACC'] if math.isfinite(min_gap_type['ACC']) else None,
        merges_with_acc_follower=sum(e['rear_type'] == 'ACC' for e in accepted),
        total_delay_hdv_veh_s=sum(z['delay_s'] for z in trips if z['type'] == 'HDV'),
        total_delay_acc_veh_s=sum(z['delay_s'] for z in trips if z['type'] == 'ACC'),
        discharge_flow_active_veh_h=discharge_active,
        bottleneck_active_bins=active_bins,
        merge_area_speed_kmh=section_speed(*sec['merge_area'], *window) if record else None,
        far_upstream_speed_kmh=section_speed(*sec['far_upstream'], *window) if record else None,
        merge_area_speed_sd_kmh=sd_merge,
        far_upstream_speed_sd_kmh=sd_far,
        disturbance_ratio=(sd_far / sd_merge) if (sd_far is not None and sd_merge) else None,
    )
    if not road and not any(queues):
        total = sum(z['delay_s'] for z in trips)
        assert abs(accumulated_delay - total) < 1e-06 + 1e-09 * abs(total), (accumulated_delay, total)
    return dict(summary=summary, logs=logs, frames=frames, trajectories=trajectories,
                events=events, trips=trips, detectors=detectors, reports=reports, tmc=tmc_log, signal=signal_log)
