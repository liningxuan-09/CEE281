# Changed demand: ramp peak 350, 450 and 550 veh/h

Required by the guide ("Include changed demand or a stronger disturbance"). Main controller (k_v = 0.80),
cases A, B25, B50, B75 on the evaluation seeds 101–120; only the ramp demand in the 5–35 min peak changes
(mainline 1,700 veh/h, warm-up 100 veh/h and the ramp-free tail unchanged). Peak 450 is the main study
(`../acc_main/`). Run with `acc_compare.py --ramp-peak 350` and `--ramp-peak 550` (`peak_*/eval_seeds_101-120/run.sh`).

| Peak | After the merge (veh/h) | Share of the 2,190 veh/h capacity |
|---:|---:|---:|
| 350 | 2,050 | 94% |
| 450 | 2,150 | 98% |
| 550 | 2,250 | 103% (overloaded) |

## Prediction (written 3 Nov 2026, before the evaluation runs)

From development seeds 1–4 (A and B50):

- **350**: almost no bottleneck in A (no 30 s bin with the approach below 40 km/h); ACC changes total delay
  little at any share (development seeds: B50 −8 to +1% against A).
- **550**: A is heavily congested and ramp vehicles stop at the lane end (4–11 stops per run), so ramp delay
  is a large part of the total. ACC removes most stops and cuts ramp delay, but mainline delay rises and the
  queue reaches further upstream (1.1–1.3 km); total delay at B50 about A's level (development seeds: −20 to
  +15%).
- The main result therefore holds across demand: the main controller does not raise total delay; it moves
  delay from the ramp to the mainline, more strongly the heavier the merge.

## Result (20 evaluation seeds, written after the runs)

Figure: `demand_comparison.png`.

**Means over seeds 101–120**

| Run | Measure | A (0%) | B25 | B50 | B75 |
|---|---|---:|---:|---:|---:|
| Peak 350 | Total delay (veh·h) | 8.3 | 8.2 | 8.2 | 7.7 |
|  | Mainline / ramp delay (veh·h) | 7.4 / 0.9 | 7.6 / 0.7 | 7.6 / 0.6 | 7.2 / 0.5 |
|  | Flow at 1.6 km (veh/h) | 2,020 | 2,020 | 2,018 | 2,017 |
|  | Congestion duration (s) | 72 | 48 | 4 | 0 |
|  | Queue extent (m) / largest entry queue (veh) | 265 / 13 | 335 / 13 | 330 / 14 | 105 / 17 |
|  | Stops at the lane end | 1.00 | 0.20 | 0.10 | 0.00 |
|  | Disturbance ratio | 0.42 | 0.60 | 0.83 | 0.94 |
|  | Hard-braking merges | 11 | 46 | 67 | 93 |
|  | Takeovers per run (share of ACC time) | – | 39 (3.8%) | 81 (4.0%) | 104 (3.4%) |
| Peak 450 (main) | Total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 12.0 / 2.4 | 13.2 / 1.2 | 13.1 / 0.9 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,095 | 2,093 | 2,088 |
|  | Congestion duration (s) | 250 | 297 | 88 | 12 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 870 / 15 | 830 / 22 | 550 / 30 |
|  | Stops at the lane end | 3.80 | 2.80 | 0.30 | 0.00 |
|  | Disturbance ratio | 0.49 | 0.94 | 1.17 | 1.03 |
|  | Hard-braking merges | 30 | 81 | 85 | 91 |
|  | Takeovers per run (share of ACC time) | – | 68 (4.4%) | 121 (4.6%) | 161 (4.9%) |
| Peak 550 | Total delay (veh·h) | 32.5 | 26.2 | 24.9 | 24.4 |
|  | Mainline / ramp delay (veh·h) | 14.3 / 18.2 | 21.5 / 4.7 | 22.6 / 2.3 | 23.1 / 1.3 |
|  | Flow at 1.6 km (veh/h) | 2,083 | 2,134 | 2,133 | 2,125 |
|  | Congestion duration (s) | 567 | 795 | 272 | 18 |
|  | Queue extent (m) / largest entry queue (veh) | 865 / 17 | 1240 / 32 | 1145 / 45 | 875 / 58 |
|  | Stops at the lane end | 13.60 | 2.30 | 0.90 | 0.00 |
|  | Disturbance ratio | 0.88 | 1.35 | 1.26 | 1.06 |
|  | Hard-braking merges | 48 | 121 | 100 | 80 |
|  | Takeovers per run (share of ACC time) | – | 85 (3.7%) | 148 (4.3%) | 203 (5.5%) |

**Paired change of total delay against A at the same demand (mean, 95% interval, seeds above A)**

| Run | Change | B25 | B50 | B75 |
|---|---|---|---|---|
| Peak 350 | vs A (veh·h) | -0.0 [-0.3, +0.2], 10/20 | -0.0 [-0.3, +0.3], 10/20 | -0.6 [-1.0, -0.1], 5/20 |
| Peak 450 (main) | vs A (veh·h) | -0.4 [-1.6, +0.6], 13/20 | -0.4 [-1.9, +0.9], 12/20 | -0.8 [-2.5, +0.5], 11/20 |
| Peak 550 | vs A (veh·h) | -6.3 [-8.4, -4.2], 2/20 | -7.6 [-10.2, -5.0], 3/20 | -8.1 [-11.2, -5.3], 3/20 |

All vehicles leave before 60 min in every run; no collision.

**Against the prediction.** As predicted, at 350 veh/h ACC changes little (−0.6 veh·h at B75, nothing at B25
and B50), and at 550 veh/h ACC removes most lane-end stops and moves delay from the ramp to the mainline.
Total delay at 550 fell more than predicted: −19 to −25% against A (predicted −20 to +15%), lower on 17–18 of
20 seeds.

**Interpretation.**

- The main controller never raises total delay at any demand, and its benefit grows with the merge load:
  none at 350, none detectable at 450, −6 to −8 veh·h at 550.
- The reason is the ramp: in A at 550 veh/h ramp vehicles stop at the lane end 13.6 times per run and ramp
  delay (18 veh·h) exceeds mainline delay. ACC followers keep larger gaps, so ramp vehicles merge before the
  lane end (stops 2.3 → 0 from B25 to B75), ramp delay falls to about 1 veh·h and the flow after the merge
  rises (2,083 → about 2,130 veh/h). Mainline delay rises (14 → 23 veh·h) and the queue reaches further
  upstream (up to 1.2 km).
- At every demand ACC adds hard braking after cut-ins (hard-braking merges per run rise from 11–48 in A to
  46–121 with ACC).

## Files

| File | Content |
|---|---|
| `demand_comparison.png` | Delay, flow after the merge, disturbance ratio and hard-braking merges at the three demands |
| `peak_350/`, `peak_550/` | `eval_seeds_101-120/comparison.json`, `comparison_console.txt`, `parts/`, `run.sh` |
