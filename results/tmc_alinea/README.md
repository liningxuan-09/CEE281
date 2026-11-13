# tmc_alinea: ALINEA ramp metering driven by detector reports

Same road, demand and drivers as `../baseline/` (mainline 1,700 veh/h, ramp peak 450 veh/h, 450 m acceleration lane).

## Design

| Step | What it does |
|---|---|
| Observe | Every 30 s, reports from point detectors D0500, D1000, D1400, D1600 (count, occupancy, speed) and two ramp counters: `RAMP_IN` at the queue tail, `RAMP_OUT` at the stop line. The controller reads nothing else. |
| Estimate | Q̂ = cumulative `RAMP_IN` − cumulative `RAMP_OUT` (ramp vehicles before the stop line), clipped at 0 |
| Predict | 60 s queue forecast Q̂ + H (q_in − q_out), mean flows of the last 4 reports; advisory only |
| Decide | ALINEA on **D1400**: r_k = clip(r_{k−1} + 70 veh/h per % × (14% − o_k), 200, 900 veh/h), updated every 30 s. Hold while a report is missing; 500 veh/h after 60 s without data. No queue override. |
| Act | Ramp signal at 1.05 km (end of the 200 m ramp road, where the acceleration lane begins; about 28 cars fit on the ramp road). **Signal cycle = 3600 / r s: green 2 s, in which the first waiting vehicle within 30 m of the line may go (one car per green), then red until the next cycle.** Shortest cycle 4 s (green 2 s + red 2 s), so at most 900 veh/h; longest 18 s at 200 veh/h. At 900 veh/h the signal rests in green (no metering). A vehicle is committed only once it could no longer stop at the line (braking at b). |

ALINEA changes the rate every 30 s; within those 30 s the signal runs several cycles of 4–18 s.

## Example run: `seed9/` (open `classroom_demo.html`; `signal_timing.png` shows the signal cycle)

| Seed 9 | No control (`../baseline/seed9/`) | ALINEA |
|---|---:|---:|
| Approach speed (upstream 96 km/h) | 42 km/h | **64 km/h** |
| Congested time at the merge | 18 min | **1.0 min** |
| Queue extent upstream of the merge | 800 m | 400 m |
| Total delay (veh·s) | 60,311 | **57,290 (−5%)** |
| Mainline / ramp delay (veh·s) | 52,918 / 7,393 | 33,003 / 24,287 |
| Merges forcing the follower to brake > 3 m/s² | 108 of 224 | 12 of 224 |
| Ramp vehicles stopped at the lane end | 0 | 0 |
| Max cars before the stop line / waiting off the ramp | 7 / 2 | 27 / 12 |
| Time with cars waiting off the ramp | 1 min | 11.3 min |

The controller restricts the ramp for most of the peak: between 5 and 40 min the rate is below the 450 veh/h ramp demand in 44 of 70 updates, at its 200 veh/h minimum (18 s cycle) in 38, and resting in green in 13. Occupancy at 1.4 km still averages 18%, above the 14% target, but the long mainline queue that forms without control does not appear. The cost is waiting at the signal, which fills the ramp road.

## Results on the 20 evaluation seeds (101–120)

`eval_seeds_101-120/comparison.json` (`run.sh` reproduces it). `seed_by_seed.png` (`seed_figure.py`) shows every seed: total delay with and without ALINEA, and the paired change in total and mainline delay. The demo seed 9 (a development seed) is drawn beside them for reference; its no-control delay is higher than on 14 of the 20 evaluation seeds. Same arrivals per seed in every case; means over seeds; total delay = mainline + ramp delay; 95% paired bootstrap intervals.

| | No control | **ALINEA** | Lost reports 1200–1500 s |
|---|---:|---:|---:|
| Total delay (veh·s) | 53,487 | **56,191** | 57,425 |
| Mainline / ramp delay (veh·s) | 35,570 / 17,917 | 29,558 / 26,633 | 28,994 / 28,431 |
| Mainline delay change vs. no control [95%] | – | **−6,010 [−10,130, −2,360] (−17%), lower on 15/20 seeds** | −6,580 [−10,810, −3,000] (−18%), lower on 18/20 |
| Total delay change vs. no control [95%] | – | +2,700 [−380, +5,730] (+5.1%, not significant), lower on 6/20 | +3,940 [−10, +7,890] (+7.4%, borderline), lower on 6/20 |
| Ramp vehicles stopped at the lane end, per run | 3.8 | **2.05** | 1.7 |
| Mainline followers braking harder than 3 m/s² after a merge, per run | 30.4 | **9.9** | 10.3 |
| Max cars before the stop line (mean / worst seed) | 6.8 / 9 | 29.6 / 60 | 29.8 / 56 |
| Seeds where the queue exceeds the 28 cars the ramp holds | 0 | 9/20 | 7/20 |
| Time with cars waiting off the ramp (s) | 65 | 584 | 604 |
| Discharge flow at 1.6 km (veh/h) | 2,085 | 2,094 | 2,090 |

## Detector defects (guide: test at least one observation defect)

| | ALINEA, perfect detectors | 2% of passages missed | Occupancy noise, SD 2 points | Reports delayed 30 s |
|---|---:|---:|---:|---:|
| Count error per 30 s at D1400 (veh) | 0 | 0.33 | 0 | 0 |
| Occupancy error at D1400 (MAE, points) | 0 | 0.3 | 1.6 | 0 |
| Queue estimate error (MAE, veh) | 0 | 1.6 | 0 | 0 |
| Total delay (veh·s) | 56,191 | 54,528 | 56,391 | **60,359** |
| Total delay change vs. no control [95%] | +2,700 [−380, +5,730] | +1,040 [−3,030, +4,810] | +2,900 [−1,280, +6,840] | **+6,870 [+2,840, +10,790] (+13%)** |
| Mainline delay change vs. no control | −17% | −16% | −18% | −7% (not significant) |
| Ramp vehicles stopped at the lane end, per run | 2.05 | 1.9 | 1.55 | 3.4 |

## Interpretation

- **What ALINEA does.** It measures occupancy just downstream of the merges and, in the peak, holds ramp vehicles at the signal so that the merge stays below its critical occupancy. The mainline gains clearly: 17% less mainline delay, about two thirds fewer hard braking events forced by merges, and fewer ramp vehicles stuck at the lane end.
- **What it costs.** The time saved on the mainline is spent waiting at the signal, so total delay does not improve (+5%, not significant; 6 of 20 seeds better). On 9 of 20 seeds the queue outgrows the 200 m ramp road and cars wait off the ramp, which would block the street in reality.
- **Seed 9** is a case where the mainline would break down badly without control; there ALINEA also lowers total delay (−5%). On seeds without breakdown it mostly moves delay from the mainline to the ramp.
- **Robustness.** Missed passages and occupancy noise hardly change the result. Lost reports for 5 min are absorbed by holding and the fallback rate. **A 30 s report delay is the weak point**: the controller acts on old data, the mainline benefit falls to 7% and total delay rises by 13%.
- **Forecast.** The 60 s queue forecast is not better than persistence (MAE 3.8 vs. 3.4 vehicles).
- **Stops at the lane end still happen** without control on 12 of 20 seeds (up to 14 vehicles on one seed): a vehicle that does stop needs a large gap, because nobody yields.

## Changed-demand test → `demand/`

Ramp peak 350 / 450 / 550 veh/h (mainline 1,700) and mainline 1,500 / 1,700 / 1,900 veh/h (ramp peak 450),
each with and without ALINEA on the 20 evaluation seeds. Below capacity ALINEA changes little (slightly
worse total delay at mainline 1,500); at the high demands it lowers total delay (−9% and −19%) but the ramp
queue exceeds the 28-car storage on every seed. See `demand/README.md`.
