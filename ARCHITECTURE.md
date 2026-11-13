# Model Architecture and Assumptions

This describes the **acceleration-lane model** used from the `baseline` run on. The previous merge-zone model (run 7) is archived with its source code in `results/dev_history/merge_zone/code/`; run 1 keeps its outputs and `ISSUE_SUMMARY.md` but no code snapshot.

## Units and state

Internally: position in m, time in s, speed in m/s, acceleration in m/s². Outputs use km, km/h and veh/h.

Each vehicle stores an ID, its origin (`0` = mainline demand, `1` = ramp demand), its lane (`0` = mainline, `1` = ramp road and acceleration lane), front-bumper position `x` in mainline coordinates, speed `v`, last applied acceleration `a`, scheduled arrival time and entry time. Arrivals that cannot enter yet wait in counted external queues at the mainline entrance and at the ramp entrance.

## Geometry

```text
 mainline entry (25 m/s)                acceleration lane                 exit
 0 ───────────────────────────────────── 1.2 ══════════════ 1.5 ─────────── 2.0 km
                                        /  (lane 1, beside lane 0)
                    ramp road 200 m    /
           ramp entrance (1.0 km) ────┘   detectors: 0.5, 1.0, 1.4, 1.6 km and the exit
```

| Field | Default | Meaning |
|---|---:|---|
| `road_end` | 2000 m | mainline exit |
| `merge_x` | 1500 m | end of the acceleration lane |
| `acc_length` | 450 m | acceleration lane length (from 1050 m) |
| `ramp_length` | 200 m | ramp road before the acceleration lane; no lane change allowed there |
| `ramp_entry_speed`, `ramp_v0` | 60 km/h | entry speed and desired speed on the ramp road |

## Car following: IDM+CAH

```text
net_gap   s = leader_x - follower_x - length
delta_v     = v - v_leader                      (positive = closing)
s_star      = s0 + max(0, v*T + v*delta_v / (2*sqrt(a*b)))
a_IDM       = a * (1 - (v/v0)^delta - (s_star/s)^2)

a_l~  = min(a_leader, a)                       (leader's last applied acceleration)
a_CAH = v^2 a_l~ / (v_leader^2 - 2 s a_l~)     if v_leader*delta_v <= -2 s a_l~
        a_l~ - max(delta_v, 0)^2 / (2 s)       otherwise
a     = a_IDM                                                        if a_IDM >= a_CAH
        (1-c) a_IDM + c [a_CAH + b tanh((a_IDM - a_CAH)/b)]          otherwise
```

Kesting, Treiber & Helbing (2010). A cut-in at a short gap that is not closing gives a_CAH close to the leader's acceleration, so the follower brakes gently instead of in an emergency.

**Collision floor (project addition).** If the follower is closing in (delta_v > 0) and stopping its approach 0.5 m behind the leader takes more than b, it brakes at least `delta_v^2 / (2 (s - 0.5))`. Ordinary approaches stay pure IDM+CAH.

| Parameter | Value | Unit | Note |
|---|---:|---|---|
| v0 | 33.33 | m/s | 120 km/h |
| T | 1.2 | s | literature 1.5; project choice |
| a | 2.0 | m/s² | literature 1.4; project choice |
| b | 2.0 | m/s² | literature |
| s0 | 2 | m | literature |
| delta | 4 | – | literature |
| c (`cool`) | 0.99 | – | literature; `cool = 0` gives plain IDM |
| length | 5 | m | project choice |

Applied acceleration is clipped to [−4, +2] m/s².

**Why a = 2.0 and T = 1.2 s.** IDM with a = 1.4 m/s² is string-unstable below about 60 km/h. A slowdown at the merge then grew into stop-and-go waves below 30 km/h, which is unrealistic for one freeway lane at this demand. With a = b = 2.0 m/s², platoons are string-stable at all speeds. T = 1.2 s raises single-lane capacity to about 2,190 veh/h, so that realistic demand gives a merge bottleneck rather than a capacity jam.

## ACC vehicles

**Equipment.** `acc_share` of each stream (default 0). Each arrival draws one uniform number from a fourth random stream (the mainline, ramp and detector-error streams are unchanged) and is equipped if the number is below `acc_share`. Arrivals are therefore identical for every share, and every vehicle equipped at 25% is also equipped at 50% and 75%. `acc_share = 0` reproduces the pre-ACC model exactly (tested against a value recorded with the pre-ACC code).

**Where the ACC acts.** Only on the mainline (lane 0). On the ramp road and the acceleration lane equipped vehicles drive and merge with the HDV rules (`target_speed`, `merge_test`) and switch the ACC on once they are on the mainline. The merge rule judges every new follower with the HDV law, whatever its type.

**Observation interface (`acc_inputs`).** Every step (command interval = dt = 0.1 s) an ACC vehicle receives its own speed and, for the vehicle directly ahead in the same lane, the net gap s and that vehicle's speed (s = ∞ if nothing is ahead). Readings are exact. Nothing else reaches the controller: no leader acceleration, no vehicles further ahead or on the acceleration lane (a merging vehicle appears only once it has changed lane), no V2V or I2V messages.

**Sensor delay (`acc_sensor_delay`, degraded-information test; default 0).** The gap and leader speed passed to the controller are the readings taken `acc_sensor_delay` s earlier (`delayed_reading`, a per-vehicle buffer of past readings); own speed is current, and the driver's takeover uses the current situation. A vehicle whose ACC has just switched on holds its first reading until the delay has passed. The delay must be a multiple of dt.

**Controller (`acc_command`).**

```text
cruise   = a (1 - (v/v0)^delta)                         IDM free-road term, same v0 and a as the HDVs
follow   = k_p [s - (eta + h v)] - k_v (v - v_leader)    Gunter et al. (2020)
u        = min(follow, cruise) with a vehicle ahead, cruise otherwise
fallback   u = -2 m/s^2 while the reading is missing (unit-tested; never triggered, readings are exact)
```

| Parameter | Value | Source |
|---|---:|---|
| k_p | 0.0131 s⁻² | Gunter et al. (2020), Table I: one vehicle at its longest gap setting |
| k_v | 0.80 s⁻¹ | project choice: the smallest round value meeting the string-stability criterion below (needs ≥ 0.779); their fit, 0.2692 s⁻¹, fails it |
| η | 7.5699 m | same |
| h | 1.27 s | project choice (their fit: 1.6881 s). The flow of 100% ACC traffic at v0, v0 / (η + h v0 + ℓ) = 2,186 veh/h, equals the IDM capacity (2,192 veh/h) |

The equilibrium gap is η + h v. Because η > s0, ACC traffic carries less than IDM traffic at bottleneck speeds in steady state (1,960 vs 2,160 veh/h at 80 km/h). Linear string stability (Gunter et al. 2020) needs k_p h² + 2 k_v h − 2 ≥ 0. With k_v = 0.80 it is +0.05. With the fitted k_v = 0.2692 it is −1.30: oscillations with periods above about 48 s grow along an ACC platoon, and the ACC trails a leader accelerating at 2 m/s² by about 7 m/s (k_v = 0.80: about 2.5 m/s). That lowered queue discharge and made the merge bottleneck collapse in the first run (`results/acc_ablation_kv/fitted_kv_0.2692/`, the ablation), which is why k_v was redesigned (`acc_mechanism.py` compares the two k_v values).

**Driver takeover (`driver_takeover`, project rule).** The fitted law does not cover cut-ins and brakes at most about 0.4 m/s² even at a zero gap. With a_drv the driver's own IDM+CAH response (the HDV law, which uses the leader's last acceleration as a driver perceives it):

```text
takeover starts   a_drv < -acc_takeover_b (2 m/s^2) and a_drv < u
takeover lasts    while a_drv < u              (hand back once the driver brakes less than the ACC)
applied           a_drv during a takeover, u otherwise; then clipped to [amin, amax]
```

This follows Adebisi et al. (2020), whose C/ACC hands emergency braking to a conventional car-following model while a collision warning is active. Episodes and their duration are counted (`acc_takeover_episodes`, `acc_takeover_vehicle_s`). *Changed 2 Nov 2026, before the evaluation runs:* a kinematic rule (command at most −Δv²/[2 max(s − s0, 0.1 m)] above 2 m/s²) let a merged ACC vehicle creep into its leader at 0.57 m/s, and a takeover without the hand-back hysteresis chattered.

## Integration and collision checks

All requests are computed from one snapshot of both lanes; then every vehicle moves with constant acceleration over the step:

```text
x_next = x + v*dt + 0.5*a*dt^2,   v_next = v + a*dt
```

A vehicle that would stop inside the step stops at t = −v/a and holds its position. The minimum gap is checked **within** each step in each lane: the step is split at the stopping times and the stationary points of the relative motion are tested. Any overlap raises an error with debug information; vehicles are never moved or deleted to hide one.

## Ramp and merge

1. **Entering.** Arrivals join counted queues. A mainline vehicle enters at 0 m and 25 m/s; a ramp vehicle enters at the ramp entrance at 60 km/h. Either may enter only if it would not need to brake (`entry_brake = 0`) and could stop behind its leader. With `ramp_release_rate` set, the ramp is metered at the stop line with the same signal cycle as ALINEA (green 2 s, one car per green, then red; unused greens are lost).
2. **Ramp road.** Ramp vehicles follow each other with IDM+CAH at desired speed `ramp_v0`.
3. **Acceleration lane: desired speed** (`target_speed`). The vehicle's IDM desired speed is set each step:
   - Side by side with a mainline vehicle: push ahead if its front is ahead; otherwise drop back to that vehicle's speed minus `drop_dv` (10 km/h).
   - A faster mainline vehicle close behind is let pass.
   - Otherwise it lines up with the nearest gap it could merge into and matches that gap's speed. The correction is `align_k` (0.3 s⁻¹) per metre of distance to the gap.
4. **Merge test** (`merge_test`), each step, for every vehicle fully on the acceleration lane, front-most first. It uses the nearest mainline vehicles ahead (L) and behind (F).
   - Urgency u = distance travelled along the lane / lane length (0 to 1).
   - Both net gaps must be at least `merge_gap_min`·(1 − 0.75u), and still at least `merge_gap_min` (2 m) after `merge_horizon` (2 s) at current speeds.
   - Braking budget bs = `b_safe` + (`b_safe_end` − `b_safe`)·u², from 2 to 4 m/s².
   - The merging vehicle's IDM+CAH acceleration behind L must be at least −bs.
   - F must be able to come down to the merging vehicle's speed braking at most bs (allowing for the merging vehicle's own acceleration), and at most |amin| whatever the merging vehicle does.
   - The merging vehicle must be able to come down to L's speed within bs.
   - F's IDM+CAH acceleration behind the merging vehicle must be at least −bs.
   The follower's response is always judged with the HDV law, so any future follower type faces the same rule.
5. **Forced merge.** In the last `force_zone` (60 m), or once v²/(2·room) > 0.9·`end_trigger`, the vehicle takes a gap that is either:
   - **safe:** with both vehicles braking at |amin| = 4 m/s², it can stop behind L and F can stop behind it, with 1 m to spare; or
   - **brisk:** it has ≥ 30 m of free road ahead and can accelerate at ≥ 0.8·`acc_lane_a`, and F copes braking at most 0.6·|amin|.
6. **Lane end.** When stopping before the lane end would take more than `end_trigger` (3.8 m/s²), the vehicle brakes to stop 1 m before it, and waits there for a gap. Such stops are counted (`stops_at_lane_end`).
7. **Lane change** is instantaneous: the vehicle moves to lane 0 between L and F at its current position and speed. The replay draws a 3 s lane change for illustration.
8. **No yielding.** Mainline vehicles ignore the acceleration lane; they react only once a vehicle is in front of them in lane 0.

## Per-step sequence

1. Move scheduled arrivals into the mainline and ramp queues.
2. Admit at most one mainline vehicle and (if a release is available) one ramp vehicle.
3. Merges: test lane-1 vehicles front-most first; move accepted ones into lane 0 and log the event with the follower's braking before and after.
4. Record one-second samples (trajectories, replay frames).
5. Compute accelerations from one snapshot of both lanes (IDM+CAH; ACC vehicles on lane 0 use `acc_command` with `driver_takeover`; on lane 1 the desired speed from `target_speed` and the lane-end braking), integrate, check within-step clearance, and record detector crossings and exits.
6. Remove exited vehicles, add queue waiting to the delay, and assert vehicle conservation.

## Demand (baseline)

| | Default |
|---|---|
| Mainline | 1,700 veh/h, 0–40 min |
| Ramp | 100 veh/h (0–5 min), 450 veh/h (5–35 min), 0 (35–40 min) |
| Seed | 9 (demonstration); comparisons use seeds 101–120 |
| Run length | 60 min (all vehicles clear) |
| Ramp metering | none |

Arrivals are Poisson with a piecewise-constant rate (`schedule_profile`); the two streams use independent random streams from one seed.

## Feasibility check (`feasibility.py`)

*Designed for the earlier default (1,700 + 500 veh/h, 300 m lane) and not rerun for the current one. The current default was chosen instead by a demand sweep on the development seeds (450 m lane): 1,700 + 450 veh/h gives a clear bottleneck without control (approach about 30 km/h slower than upstream, 4–5 min congested on average) and an ALINEA that restricts the ramp in most peak cycles, while only a few ramp vehicles stop at the lane end (0.75 per run on the development seeds). 1,600 + 350 veh/h removed the stops but also the bottleneck, so ALINEA hardly acted.*

Criteria fixed in advance, checked for the selected seed and reported for 13 development seeds:

- **bottleneck:** approach (last 500 m) ≥ 20 km/h slower than upstream (1.5–1.0 km before the merge);
- **recovery:** downstream (200–500 m after the merge) ≥ 10 km/h faster than the approach;
- **local:** upstream ≥ 85 km/h and queue extent ≤ 1 km;
- **realistic:** ≤ 5% of mainline 1 s samples below 30 km/h in the evaluation window;
- **no stranding:** no stop at the lane end;
- **ramp entry:** wait at the ramp entrance ≤ 30 s;
- **no-ramp control:** never congested, and no cell before the merge below 70 km/h;
- **cleared:** all vehicles leave;
- **time step:** with dt = 0.05 s, the selected seed's approach speed changes by < 5 km/h and total delay by < 10%.

## Metrics

```text
trip delay   = exit time - scheduled arrival - free-flow time of the origin
free-flow    mainline: lone IDM vehicle over 2.0 km from 25 m/s
             ramp: lone vehicle from the ramp entrance (ramp road at 60 km/h,
                   acceleration lane, merging as soon as it is fully on the lane)
```

Trip delay includes queue waiting. Total delay (`accumulated_delay_veh_s`) uses the same reference: it is integrated every step as time spent minus distance covered × (free-flow time / route length of the vehicle's origin), plus queue waiting, so it also counts vehicles that have not finished. Once all vehicles have left it equals the sum of trip delays and therefore mainline + ramp delay (`total_delay_main_veh_s` + `total_delay_ramp_veh_s`); the run asserts this.

*Changed 1 Nov 2026:* the integrated total previously used distance / v0 as its reference (60.0 s mainline, 30.0 s ramp instead of 61.3 s and 39.1 s), so it exceeded mainline + ramp by about 3,820 veh·s per run. Paired differences between cases on the same seed were unaffected; totals and percentage changes were not.

Bottleneck indicators over the evaluation window (300–2400 s):

- **Section speeds**, mean of 1 s samples of mainline vehicles:
  - upstream: 1.5 to 1.0 km before the merge;
  - approach: last 500 m before the end of the acceleration lane;
  - downstream: 200 to 500 m after it.
- **Speed variability:** standard deviation of the same samples per section.
- **Discharge flow** at the first detector downstream (1.6 km).
- **Congestion duration:** 30 s bins in which the approach averages below `congested_kmh` (40 km/h).
- **Queue extent:** distance from the merge to the farthest congested 100 m cell (30 s × 100 m cells).
- Both use only the 30 s bins inside the window, like the speeds and flows. The whole run is reported separately for reference (`congestion_duration_full_run_s`, `max_queue_extent_full_run_m`); it also covers the queue dissolving after demand ends. *Changed 1 Nov 2026:* both previously covered the whole run (baseline seed 105: 570 s reported, 420 s inside the window).
- **Merges:** count, mean speed and position on the lane, followers that had to brake (with the follower's own law), stops at the lane end.
- **Discharge while active** (`discharge_flow_active_veh_h`): flow at 1.6 km during the 30 s bins in which the approach averages below 40 km/h (`bottleneck_active_bins`).
- **Disturbance ratio:** speed SD 300–500 m upstream of the acceleration lane (0.55–0.75 km) ÷ speed SD alongside it (1.05–1.5 km). Below 1, merge disturbances fade upstream; above 1, they grow.
- **ACC:** equipped vehicles per stream, ACC time on the mainline, takeover episodes and time, braking harder than 3 m/s² by type, smallest within-step gap by follower type, delay by type.

## Observation and TMC (`tmc_alinea` run)

**Detector reports.** Every `report_interval` (30 s) each mainline detector at 0.5, 1.0, 1.4 and 1.6 km reports, in the guide's observation format:

| Field | Meaning |
|---|---|
| `sensor_id` | `D0500` … `D1600`; ramp counters `RAMP_IN` (queue tail, arrivals) and `RAMP_OUT` (meter, releases) |
| `interval_start_s`, `interval_end_s` | report interval |
| `count`, `cum_count` | vehicles whose presence started in the interval; running counter |
| `occupancy` | share of the interval the point detector was covered (front crossing to rear crossing) |
| `mean_speed_mps` | mean of length / covered time (single loop, known 5 m length) |
| `quality_flag` | `ok`, or `missing` when the report is lost (`report_dropout`); values are then empty |

A vehicle that merges with its rear before a detector and its front past it starts a presence at the merge time. Counters keep running when a report is lost, so cumulative counts are correct again in the next report.

**TMC cycle** (every 30 s, at the start of the step, before new arrivals):

```text
observe   reports for [t - 30 s, t)
estimate  Q_hat = cum(RAMP_IN) - cum(RAMP_OUT)        vehicles waiting at the meter
predict   Q_hat(t+H) = max(0, Q_hat + H (q_in - q_out)), H = 60 s, rates = mean of the last 4 reports
          (advisory only; compared with the persistence forecast Q_hat(t+H) = Q_hat)
decide    mode, in this order:
            fallback  no valid occupancy report for more than 60 s  -> r = 500 veh/h
            override  only if ramp_storage is set (off by default; ablation): Q_hat > ramp_storage -> r = rate_max
            hold      this report missing, last one recent          -> r unchanged
            alinea    r = clip(r_prev + K_R (o* - o_1.4km), 200, 900 veh/h)
act       signal at the stop line (end of the ramp road, 1.05 km): cycle = 3600 / r s (4-18 s); each cycle
          starts with a green of meter_green = 2 s in which the first waiting vehicle within 30 m of the
          line may go (one car per green), then red (at least meter_min_red = 2 s); an unused green is
          lost; at r = rate_max the signal rests in green (no restriction); a vehicle is committed to pass only once it
          could no longer stop at the line braking at b, so everyone further upstream stops when
          metering resumes
evaluate  one row per cycle in result['tmc'] (true queue and occupancy logged for scoring only)
```

| Parameter | Value | Source |
|---|---:|---|
| `alinea_detector` | 1400 m | Chosen with the earlier 300 m lane and 1,700 + 500 veh/h, kept unchanged. Downstream of most merges: merges spread along the acceleration lane (mean 1.33 km, middle half 1.21–1.44 km). Its 30 s flow-occupancy data show the congested branch (about 2,070 veh/h at 12–16%, about 1,750 veh/h above 24%), whereas the 1.6 km detector never exceeds 17% and stays in free flow, so ALINEA there hardly ever restricts the ramp (development seeds: below ramp demand in 0–30% of peak cycles vs. 23–62% at 1.4 km) |
| o* (`alinea_target_occ`) | 0.14 | ≈ 0.9 × critical occupancy. IDM equilibrium: capacity 2,190 veh/h at 70 km/h, o_cr = q ℓ / v = 15.6%. In the first acceleration-lane run (300 m lane, 1,700 + 500 veh/h) the 1.6 km reports showed peak-period occupancy 14–17% with flows of 2,140–2,230 veh/h |
| K_R (`alinea_gain`) | 70 veh/h per % | Papageorgiou et al. (1991) |
| `rate_min`, `rate_max` | 200, 900 veh/h | 900 veh/h = shortest signal cycle 4 s (green 2 s + red 2 s), the usual practical maximum of a single-lane, one-car-per-green meter; 200 veh/h = 18 s cycle |
| `meter_green`, `meter_min_red` | 2 s, 2 s | signal timing of a one-car-per-green meter: a short green for one vehicle, then red |
| `ramp_storage` | None (no override) | Earlier demand, development seeds: an override at 20 or 28 vehicles flushes the queued vehicles as a platoon that then strands on the acceleration lane, and it removes most of the benefit. The street is not modelled, so spillback is reported instead (`ramp_spillback_s`, `max_ramp_external`, `ramp_overflow_s` against the ramp's capacity of 28 stopped vehicles). The override is kept as an ablation. |
| `report_stale`, `fallback_rate` | 60 s, 500 veh/h | project choice; set for the earlier 500 veh/h ramp peak, slightly above the current 450 veh/h peak |

**Detector defects** (off by default; observation tests). `detector_miss_prob`: each passage is missed with this probability; a missed vehicle adds nothing to count, occupancy or speed, and the ramp counters lose it. `occupancy_noise_sd`: Gaussian noise added to reported occupancy (clipped to [0, 1]). `report_delay`: reports reach the TMC this many seconds after their interval ends, so the controller acts on older data; the stale-data limit is extended by the delay. `report_dropout`: reports lost in time windows. Every report also carries the true count and occupancy (`count_true`, `occupancy_true`) for scoring only. Error measures in the summary: `detector_count_error_veh` (mean absolute count error per 30 s at the ALINEA detector), `detector_occupancy_mae`, `queue_estimate_mae_veh` (estimate vs. true queue at the data time). The queue estimate is clipped at zero. Detector errors use their own random stream, so traffic is unchanged.

**Ramp meter.** The stop line (`meter_x`, default: where the acceleration lane begins) holds every vehicle that has not been released: IDM treats the line as a stopped leader, so vehicles queue on the 200 m ramp road (about 28 fit) and start from rest when released. Arrivals that find the ramp road full wait off the road (spillback, `ramp_spillback_s`). The `RAMP_IN` counter is at the queue tail (arrival) and `RAMP_OUT` at the stop line, so Q̂ counts every ramp vehicle that has not yet passed the line. Fixed-rate metering (`ramp_release_rate`) uses the same stop line. Resting in green at the maximum rate is a project choice: it corresponds to switching a meter off when no restriction is needed, and avoids stopping every vehicle in light traffic. Green is a state, not a lasting permission. While it lasts nobody is held; a vehicle becomes committed (released) when it could no longer stop at the line braking at `b` (v² > 2 b × distance, i.e. within about 69 m at 60 km/h) or when it passes the line. When the rate falls below the maximum, every uncommitted vehicle stops at the red signal and waits for a green. The run asserts that no vehicle passes the line uncommitted while metering. *Changed 1 Nov 2026:* resting in green used to release every vehicle on the ramp road permanently, so up to two vehicles per switch passed the line after metering had resumed (evaluation runs: 4 vehicles on seed 5, 1 on seed 105).

When the rate changes, the next green starts 3600 / r after the start of the last one; a green that is then already due starts at once rather than releasing a burst. Every green is logged (`result['signal']`: start, end, vehicle released). Without `ramp_control`, reports and forecasts are still produced and the traffic is identical to the unmetered model (checked: the baseline delay is reproduced exactly).

## Persistence boundary

`model.run()`, `validate.validate()` and `feasibility.feasibility()` return dictionaries and never write files. Only `run_demo.py --save` (through `present.render()` and `make_gif.make()`), `validate.py --save` and `feasibility.py --save` write to disk.

## Known limitations

- Lane changes are instantaneous and there is no lateral motion.
- All HDVs are identical: no heterogeneity, no reaction delay.
- Without yielding, a vehicle stopped at the lane end needs a large gap. At the default demand this happens to a few ramp vehicles per run on some seeds; the 450 m lane keeps the queue behind them short.
- Merge thresholds, ramp speeds, a and T are project choices for a realistic baseline, not calibrated to a site.
- Detectors are ideal point detectors unless a defect is switched on (missed passages, occupancy noise, delayed or lost reports; all tested). Speed noise and placement errors are not modelled.
- ACC readings are exact; the takeover is a project rule. The main controller's k_v is a design value, not a measured one. Gunter et al. fitted their law to small oscillations at highway speed.
- Gipps is not modelled yet (planned as the second human-driver model).
