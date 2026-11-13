# Main ACC study: string-stable ACC (main controller)

Cases A (0% ACC), B25, B50, B75 on the 20 evaluation seeds 101–120, unmetered ramp, the frozen baseline
demand (mainline 1,700 veh/h; ramp 100 → 450 → 0 veh/h). Within a seed the arrivals are identical and
ACC assignments are nested. Run with `acc_compare.py --controller stable` (see `eval_seeds_101-120/run.sh`).

**Controller.** Gunter et al. (2020) following law u = k_p [s − (η + h v)] − k_v (v − v_leader) with their
fitted k_p = 0.0131 s⁻² and η = 7.5699 m, h = 1.27 s (project choice, unchanged), and **k_v = 0.80 s⁻¹**:
the smallest round value that satisfies their linear string-stability criterion k_p h² + 2 k_v h − 2 ≥ 0
(needs k_v ≥ 0.779; criterion value +0.05). Cruise, onboard inputs, driver takeover and fallback are as in
the first run.

**Why this controller.** The first run with the fitted k_v = 0.2692 (`../acc_ablation_kv/fitted_kv_0.2692/`) made the merge
bottleneck collapse at every ACC share. The diagnosis there (slow discharge, disturbances that grow
upstream) pointed to the fitted gains failing string stability. k_v = 0.80 follows from the criterion
alone; it was checked only on development seeds 1–4 and in the deterministic tests before this run.
This controller is a design based on the fitted law, not a measured commercial setting.

## Prediction (written 2 Nov 2026, before the evaluation runs)

From development seeds 1–4 (B25 and B75) and `acc_mechanism.py`:

- **Delay** close to A at every share (development seeds: B25 +2 to +24%, B75 −14 to +17% against A);
  no queue reaching the mainline entrance.
- **Discharge**: flow at 1.6 km about the same as A; the flow while the bottleneck is active is not lower
  than A (queue discharge from standstill: 2,062 veh/h with every 4th vehicle ACC and 2,192 with all ACC,
  against 2,089 all HDV).
- **Disturbances**: a 10 m/s dip shrinks to 8.9 m/s behind 40 ACC vehicles (HDV: 5.4, fitted gains: 16.2),
  so disturbances no longer grow, but ACC damps them less than HDVs. Disturbance ratio near A at B25,
  possibly higher at B75.
- **Takeovers** far fewer than with the fitted gains (development seeds: about 60 per run at B25 and
  150 at B75, against 300–700).

## Result (20 evaluation seeds, written after the runs)

Means over seeds 101–120 (`eval_seeds_101-120/comparison.json`; figures `eval_seeds_101-120/acc_summary.png`,
`seed110_speed_maps.png`, and the ablation figure `../acc_ablation_kv/ablation_kv_comparison.png`):

| Measure | A (0%) | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
| … mainline / ramp (veh·h) | 9.9 / 5.0 | 12.0 / 2.4 | 13.2 / 1.2 | 13.1 / 0.9 |
| Flow at 1.6 km, 300–2400 s (veh/h) | 2,085 | 2,095 | 2,093 | 2,088 |
| Flow at 1.6 km while the bottleneck is active (veh/h) | 2,057 | 2,110 | 2,169 | 2,170 |
| 30 s bins with the approach below 40 km/h | 8.4 | 9.9 | 3.0 | 0.4 |
| Congestion duration (s) | 251 | 297 | 89 | 12 |
| Mean speed 300–500 m upstream of the acceleration lane (km/h) | 93 | 84 | 76 | 76 |
| Speed SD alongside the acceleration lane / 300–500 m upstream (km/h) | 23.9 / 12.0 | 20.7 / 19.3 | 17.7 / 20.5 | 16.5 / 17.1 |
| Disturbance ratio | 0.49 | 0.94 | 1.17 | 1.04 |
| Largest queue at the mainline entrance (veh) | 13 | 15 | 22 | 30 |
| Stops at the lane end (per run) | 3.8 | 2.8 | 0.3 | 0.0 |
| Merges after which the follower brakes harder than 3 m/s² | 30 | 81 | 85 | 91 |
| Braking harder than 3 m/s², HDV / ACC (veh·s) | 41 / – | 31 / 23 | 18 / 29 | 4 / 36 |
| Takeover episodes per run (share of ACC mainline time) | – | 68 (4.4%) | 121 (4.6%) | 161 (4.9%) |
| Smallest net gap behind HDV / ACC (m) | 1.01 / – | 1.04 / 1.52 | 1.32 / 1.59 | 2.01 / 1.72 |

Paired changes against A (mean, paired bootstrap 95% interval):

| | B25 | B50 | B75 |
|---|---|---|---|
| Total delay (veh·h) | −0.39 [−1.60, +0.61] | −0.40 [−1.92, +0.86] | −0.84 [−2.45, +0.47] |
| Mainline delay (veh·h) | +2.17 [+0.83, +3.66] | +3.34 [+1.81, +5.08] | +3.27 [+1.51, +5.24] |
| Ramp delay (veh·h) | −2.55 [−4.08, −1.08] | −3.73 [−5.82, −1.76] | −4.11 [−6.20, −2.14] |
| Flow at 1.6 km (veh/h) | +10 [+3, +18] | +7 [−1, +17] | +3 [−6, +12] |
| Congestion duration (s) | +47 [−57, +147] | −162 [−263, −71] | −239 [−341, −146] |
| Disturbance ratio | +0.44 [+0.23, +0.66] | +0.68 [+0.49, +0.85] | +0.54 [+0.36, +0.70] |

All vehicles leave before 60 min in every run; no collision. Time step (development seed 1, dt = 0.05 s
instead of 0.1 s): total delay −7% at B25 and +1% at B75 (fitted gains: up to +35%).

**Against the prediction.** Delay (−3 to −6% against A, inside the predicted range), no queue at the
entrance, unchanged flow, higher discharge while active and the takeover counts were as predicted. The
disturbance ratio was not: at B25 it is already 0.94, not near A's 0.49.

**Interpretation.**

- **Total delay does not change** (all intervals include zero), but the bottleneck changes shape. The deep,
  local queue of A (approach below 40 km/h for about 4 min per run) almost disappears at B50 and B75; instead
  shallow slowdowns spread further upstream (mean speed 300–500 m upstream falls from 93 to 76 km/h).
  ACC damps disturbances less than the HDVs do (platoon test: a 10 m/s dip shrinks to 8.9 m/s behind 40 ACC
  vehicles, to 5.4 m/s behind 40 HDVs), so the disturbance ratio rises to about 1: slowdowns no longer fade
  within 500 m, but they no longer grow either (fitted gains: 16.2 m/s and a collapse).
- **Delay moves from the ramp to the mainline.** Ramp delay falls by 2.5–4.1 veh·h and stops at the lane end
  disappear, because ACC followers keep larger gaps (η = 7.57 m) that ramp vehicles can use; mainline delay
  rises by 2.2–3.3 veh·h.
- **Trade-off: harder braking at cut-ins.** With k_v = 0.80 the ACC brakes at 0.8 m/s² per m/s of closing
  speed, so a slower vehicle merging ahead now triggers a short hard brake: merges followed by braking
  harder than 3 m/s² roughly triple (30 → 81–91 per run). The total time spent braking that hard stays about
  the same (41 → 40–55 veh·s) and the smallest gaps grow.
- **Against the fitted gains** (`../acc_ablation_kv/ablation_kv_comparison.png`): same law, spacing and
  takeover, only k_v differs; delay 14.0–14.5 instead of 51–125 veh·h, flow after the merge 2,090 instead of 1,590–1,900
  veh/h. String stability, set by k_v, decides whether ACC harms this bottleneck.

**Limitations.** k_v = 0.80 is a design value from the linear criterion, not a measured setting; the
criterion ignores the cruise limit, the takeover and actuator lag. The extra hard braking at cut-ins is a
comfort cost a real system might limit. One demand level; exact sensor readings.

## Files

| File | Content |
|---|---|
| `eval_seeds_101-120/comparison.json`, `comparison_console.txt` | Per-seed measures, case means and paired changes |
| `eval_seeds_101-120/parts/`, `run.sh` | The four batches and how to rerun them |
| `eval_seeds_101-120/acc_summary.png` | Delay, flow, disturbance ratio and speed variation by case |
| `seed110_speed_maps.png` | Speed maps for seed 110 in all four cases |
| `mechanism_tests.txt` | Output of `acc_mechanism.py`: platoon disturbance and queue discharge for the main controller, its variants and the fitted gain |
| `seed110_trajectories.png` | Time-space diagrams for seed 110, A against B50, over the same 15 minutes (`acc_figures.py --trajectories`) |
| `seed9_B50/` | Demonstration run: seed 9 with 50% ACC, same layout as `../baseline/seed9/` and `../tmc_alinea/seed9/`. Open `classroom_demo.html`: ACC vehicles have a blue outline in the replay; `acc_trajectories.png` shows trajectories by vehicle type |
| `../acc_ablation_kv/` | Ablation: this controller against the fitted gain k_v = 0.2692 |
