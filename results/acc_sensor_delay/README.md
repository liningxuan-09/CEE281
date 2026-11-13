# Degraded information: sensor delay 0.5 s and 1.0 s

Required by the guide ("a delay/dropout or noncompliance condition relevant to the design"). Main controller
(k_v = 0.80), cases B25, B50, B75 on the evaluation seeds 101–120; case A is reused from `../acc_main/`
(it has no ACC vehicles, so the delay cannot change it; checked on seed 101). The gap and leader speed given
to the ACC are the readings taken 0.5 s or 1.0 s earlier; own speed is current; the driver's takeover uses
the current situation. Run with `acc_compare.py --set acc_sensor_delay=0.5 --a-from ...`
(`delay_*/eval_seeds_101-120/run.sh`).

**Why it matters here.** The main controller meets the linear string-stability criterion with a small
margin (+0.05). A delay makes the condition stricter, so this test checks whether the conclusion survives
realistic sensing.

## Prediction (written 3 Nov 2026, before the evaluation runs)

From `../acc_main/mechanism_tests.txt` and development seeds 1–4 (B50):

- Platoon test: a 10 m/s dip behind 40 ACC vehicles grows to 11.6 m/s (0.5 s) and 14.2 m/s (1.0 s) instead
  of shrinking to 8.9 m/s; queue discharge with all ACC falls from 2,192 to 1,746 and 1,429 veh/h. The delay
  removes the string stability.
- **0.5 s**: total delay at B50 about twice A (development: ×2.0–2.6), congestion 8–12 min per run instead
  of about 1 min, takeovers about twice as frequent.
- **1.0 s**: total delay at B50 about five times A (development: ×4.5–6.1), stop-and-go waves reaching the
  entrance, discharge below 1,900 veh/h, about 550 takeovers per run.
- Effects grow with the ACC share.

## Result (20 evaluation seeds, written after the runs)

Figure: `delay_comparison.png`.

**Means over seeds 101–120 (case A is the same in every run)**

| Run | Measure | A (0%) | B25 | B50 | B75 |
|---|---|---:|---:|---:|---:|
| No delay (main) | Total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 12.0 / 2.4 | 13.2 / 1.2 | 13.1 / 0.9 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,095 | 2,093 | 2,088 |
|  | Congestion duration (s) | 250 | 297 | 88 | 12 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 870 / 15 | 830 / 22 | 550 / 30 |
|  | Stops at the lane end | 3.80 | 2.80 | 0.30 | 0.00 |
|  | Disturbance ratio | 0.49 | 0.94 | 1.17 | 1.03 |
|  | Hard-braking merges | 30 | 81 | 85 | 91 |
|  | Takeovers per run (share of ACC time) | – | 68 (4.4%) | 121 (4.6%) | 161 (4.9%) |
| Delay 0.5 s | Total delay (veh·h) | 14.9 | 20.4 | 27.5 | 33.4 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 16.4 / 4.0 | 25.6 / 1.9 | 31.8 / 1.6 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,065 | 2,024 | 1,984 |
|  | Congestion duration (s) | 250 | 718 | 760 | 522 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 1015 / 20 | 1335 / 52 | 1345 / 81 |
|  | Stops at the lane end | 3.80 | 3.25 | 1.00 | 0.15 |
|  | Disturbance ratio | 0.49 | 1.21 | 1.44 | 1.31 |
|  | Hard-braking merges | 30 | 90 | 102 | 103 |
|  | Takeovers per run (share of ACC time) | – | 148 (4.3%) | 241 (3.3%) | 274 (2.7%) |
| Delay 1.0 s | Total delay (veh·h) | 14.9 | 31.7 | 54.1 | 77.0 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 29.4 / 2.3 | 51.8 / 2.3 | 74.9 / 2.1 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,004 | 1,885 | 1,778 |
|  | Congestion duration (s) | 250 | 1149 | 1168 | 915 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 1345 / 51 | 1425 / 120 | 1460 / 192 |
|  | Stops at the lane end | 3.80 | 1.80 | 0.65 | 0.05 |
|  | Disturbance ratio | 0.49 | 1.41 | 1.29 | 1.21 |
|  | Hard-braking merges | 30 | 94 | 69 | 55 |
|  | Takeovers per run (share of ACC time) | – | 274 (9.0%) | 559 (9.3%) | 777 (10.1%) |

**Paired change of total delay (mean, 95% interval, seeds above)**

| Run | Change | B25 | B50 | B75 |
|---|---|---|---|---|
| No delay (main) | vs A (veh·h) | -0.4 [-1.6, +0.6], 13/20 | -0.4 [-1.9, +0.9], 12/20 | -0.8 [-2.5, +0.5], 11/20 |
| Delay 0.5 s | vs A (veh·h) | +5.5 [+4.0, +7.1], 20/20 | +12.6 [+10.1, +15.2], 20/20 | +18.5 [+16.5, +20.7], 20/20 |
| | vs no delay (veh·h) | +5.9 [+4.3, +7.6], 20/20 | +13.0 [+10.7, +15.3], 20/20 | +19.4 [+17.5, +21.3], 20/20 |
| Delay 1.0 s | vs A (veh·h) | +16.9 [+13.6, +20.0], 20/20 | +39.2 [+35.3, +43.0], 20/20 | +62.1 [+58.1, +66.1], 20/20 |
| | vs no delay (veh·h) | +17.3 [+13.9, +20.5], 20/20 | +39.6 [+35.7, +43.2], 20/20 | +63.0 [+59.0, +66.8], 20/20 |

All vehicles leave before 60 min in every run; no collision.

**Against the prediction.** Delay grew with the delay and with the share, on every seed, as predicted. At B50
the 0.5 s delay gave 1.8 × A (predicted about 2 ×) and the 1.0 s delay 3.6 × A (predicted about 5 ×); the
flow after the merge at B50 fell to 1,885 veh/h and drivers took over 559 times per run, as predicted.

**Interpretation.**

- **This is the failure condition of the main controller.** Its string stability rests on prompt readings:
  a delay of 0.5 s already turns a shrinking disturbance into a growing one (platoon test: 10 → 11.6 m/s
  instead of 8.9) and doubles delay at B75 (+18.5 veh·h); at 1.0 s delay is 5 × A at B75, queues back up to
  the entrance and the flow after the merge falls to about 1,780 veh/h.
- The effect is the same mechanism as the fitted gains (`../acc_ablation_kv/`): without string stability,
  merge slowdowns grow on the way upstream (disturbance ratio 1.2–1.4) and the queue discharges slowly.
- Design implication: string stability has to hold with the sensing and actuation delay included. The
  delay-free criterion with a +0.05 margin is not enough; a delay-aware design would need a larger k_v (or h).
- Not modelled: noise and dropouts (the readings are exact but old); actuator lag.

## Files

| File | Content |
|---|---|
| `delay_comparison.png` | Delay, flow after the merge, disturbance ratio and hard-braking merges for 0, 0.5 and 1.0 s |
| `delay_0.5s/`, `delay_1.0s/` | `eval_seeds_101-120/comparison.json` (A copied from `../acc_main/`), `comparison_console.txt`, `parts/`, `run.sh` |
