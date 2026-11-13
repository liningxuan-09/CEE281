# Ablation: time gap h (1.69 vs 1.27 s)

Second ablation, answering "why h = 1.27 s and not the fitted 1.69 s?". Main controller law and gains
(k_p = 0.0131 s⁻², k_v = 0.80 s⁻¹, η = 7.57 m); only h changes: 1.6881 s (Gunter et al. fit, the longest gap
setting) vs 1.27 s (main study, `../acc_main/`). Cases B25, B50, B75 on the evaluation seeds 101–120; case A
is reused from `../acc_main/`. Run with `acc_compare.py --set acc_h=1.6881 --a-from ...`
(`h_1.69/eval_seeds_101-120/run.sh`).

h also enters the string-stability criterion: with h = 1.6881 s it is +0.74 instead of +0.05, so both runs
are string stable and the difference is the spacing, i.e. capacity: 100% ACC traffic carries at most
about 1,740 veh/h with h = 1.69 s (2,190 with 1.27 s), barely above the 1,700 veh/h mainline demand.

## Prediction (written 3 Nov 2026, before the evaluation runs)

From `../acc_main/mechanism_tests.txt` and development seeds 1–4 (B50):

- Disturbances: damped more than with 1.27 s (a 10 m/s dip shrinks to 7.1 m/s behind 40 ACC vehicles,
  8.9 with 1.27 s); queue discharge 2,030 veh/h with all ACC.
- **Total delay rises with the share**: at B50 about 2.5 times A (development: ×2.5–2.8), mostly mainline
  delay from a queue at the mainline entrance (largest entry queue 36–53 vehicles instead of 9–15), while
  congestion at the merge itself stays short. Fewer hard-braking merges than with 1.27 s (about 30 vs 80).
- So the long gap setting harms the bottleneck through capacity, not disturbances: the reason h was matched
  to the IDM capacity.

## Result (20 evaluation seeds, written after the runs)

Figure: `ablation_h_comparison.png`.

**Means over seeds 101–120 (case A is the same in both runs)**

| Run | Measure | A (0%) | B25 | B50 | B75 |
|---|---|---:|---:|---:|---:|
| h = 1.27 s (main) | Total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 12.0 / 2.4 | 13.2 / 1.2 | 13.1 / 0.9 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,095 | 2,093 | 2,088 |
|  | Congestion duration (s) | 250 | 297 | 88 | 12 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 870 / 15 | 830 / 22 | 550 / 30 |
|  | Stops at the lane end | 3.80 | 2.80 | 0.30 | 0.00 |
|  | Disturbance ratio | 0.49 | 0.94 | 1.17 | 1.03 |
|  | Hard-braking merges | 30 | 81 | 85 | 91 |
|  | Takeovers per run (share of ACC time) | – | 68 (4.4%) | 121 (4.6%) | 161 (4.9%) |
| h = 1.69 s | Total delay (veh·h) | 14.9 | 19.8 | 29.6 | 41.6 |
|  | Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 17.8 / 1.9 | 28.4 / 1.3 | 40.8 / 0.8 |
|  | Flow at 1.6 km (veh/h) | 2,085 | 2,075 | 2,019 | 1,951 |
|  | Congestion duration (s) | 250 | 381 | 30 | 0 |
|  | Queue extent (m) / largest entry queue (veh) | 560 / 13 | 1145 / 26 | 940 / 64 | 140 / 106 |
|  | Stops at the lane end | 3.80 | 1.75 | 0.55 | 0.00 |
|  | Disturbance ratio | 0.49 | 1.35 | 1.15 | 0.89 |
|  | Hard-braking merges | 30 | 66 | 28 | 35 |
|  | Takeovers per run (share of ACC time) | – | 51 (1.6%) | 96 (1.8%) | 94 (2.2%) |

**Paired change of total delay (mean, 95% interval, seeds above)**

| Run | Change | B25 | B50 | B75 |
|---|---|---|---|---|
| h = 1.27 s (main) | vs A (veh·h) | -0.4 [-1.6, +0.6], 13/20 | -0.4 [-1.9, +0.9], 12/20 | -0.8 [-2.5, +0.5], 11/20 |
| h = 1.69 s | vs A (veh·h) | +4.9 [+3.4, +6.3], 18/20 | +14.8 [+12.8, +16.8], 20/20 | +26.7 [+24.6, +29.1], 20/20 |
| | vs h = 1.27 s (veh·h) | +5.3 [+4.4, +6.2], 20/20 | +15.2 [+13.6, +16.7], 20/20 | +27.6 [+25.7, +29.6], 20/20 |

All vehicles leave before 60 min in every run; no collision.

**Against the prediction.** As predicted, total delay rose with the share (B50: 2.0 × A, predicted about
2.5 ×), the queue moved to the mainline entrance while congestion at the merge stayed short, and there were
fewer hard-braking merges than with h = 1.27 s.

**Interpretation.**

- With the fitted h = 1.69 s, ACC adds 5–28 veh·h of delay against h = 1.27 s on every seed, rising with the
  share. The merge itself is calmer (congestion 30 s at B50, none at B75; fewer hard-braking merges, 28–35 vs
  85–91), but the mainline can no longer carry its demand: at the 90 km/h entry speed a pure ACC stream with
  h = 1.69 s carries about 1,640 veh/h, less than the 1,700 veh/h offered, so vehicles queue before entering
  (largest entry queue 64 at B50 and 106 at B75, against 22 and 30) and the flow after the merge falls to
  1,950 veh/h at B75.
- Both settings are string stable, so this is the capacity effect the h rule was designed to remove. It
  confirms the choice of h = 1.27 s: with the fitted gap setting the study would measure lane capacity, not
  merge disturbances.

## Files

| File | Content |
|---|---|
| `ablation_h_comparison.png` | Delay, flow after the merge, disturbance ratio and hard-braking merges for h = 1.27 and 1.69 s |
| `h_1.69/` | `eval_seeds_101-120/comparison.json` (A copied from `../acc_main/`), `comparison_console.txt`, `parts/`, `run.sh` |
