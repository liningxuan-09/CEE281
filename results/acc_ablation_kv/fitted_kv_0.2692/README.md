# ACC with the fitted Gunter et al. gains (first run, design starting point)

> This was the first run of the main experiment (folder `acc_penetration` until 2 Nov 2026). Its result —
> the merge bottleneck collapses at every ACC share — and the diagnosis below led to the string-stable
> main controller (k_v = 0.80) in `../../acc_main/`; together they form the k_v ablation (`../`). The `Config` default is now k_v = 0.80; reproduce this
> run with `acc_compare.py --controller gunter` (`eval_seeds_101-120/run.sh`).

Cases A (0% ACC), B25, B50, B75 on the 20 evaluation seeds 101–120, unmetered ramp, the frozen baseline
demand (mainline 1,700 veh/h; ramp 100 → 450 → 0 veh/h). Within a seed the arrivals are identical and
ACC assignments are nested.

ACC settings: Gunter et al. (2020) following law with k_p = 0.0131 s⁻², k_v = 0.2692 s⁻¹, η = 7.5699 m
(their fit), h = 1.27 s (project choice: 100% ACC capacity at v0 = IDM capacity); IDM free-road term as
cruise; driver takeover with the HDV law when it brakes harder than 2 m/s² and harder than the ACC,
handing back once it no longer brakes harder than the ACC; onboard readings only (gap and speed of the
vehicle directly ahead in the same lane); ramp vehicles merge as drivers and switch the ACC on once on
the mainline.

## Prediction (written 2 Nov 2026, before the evaluation runs)

From the development seeds 1–4 and two deterministic tests (platoon disturbance, queue discharge):

- **Delay** rises with every ACC share: B25 about 3–5 × A, B75 about 10 × A. The order of B50 and B75 may
  not be monotonic once the queue reaches the mainline entrance.
- **Discharge**: flow at 1.6 km over the evaluation window falls from about 2,050 veh/h (A) to about
  1,900 (B25) and 1,600–1,700 (B75); the flow while the bottleneck is active falls more steeply.
- **Disturbances**: the disturbance ratio (speed SD 300–500 m upstream of the acceleration lane ÷ speed
  SD alongside it) rises from about 0.2 in A (merge disturbances fade) to about 1 or more with ACC.
- **Mechanism**: not spacing (η = 2 m, h = 1.2 s gave the same picture) but the small fitted gains. An ACC
  vehicle trails a leader accelerating at 2 m/s² by about 7 m/s, so queue discharge from standstill drops
  from 2,090 veh/h (all HDV) to about 1,750 (25% ACC) and 1,150 (100% ACC).

## Result (20 evaluation seeds, written after the runs)

Means over seeds 101–120 (`eval_seeds_101-120/comparison.json`; figure `eval_seeds_101-120/acc_summary.png`):

| Measure | A (0%) | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 14.9 | 51.2 | 83.0 | 124.6 |
| … mainline / ramp (veh·h) | 9.9 / 5.0 | 48.6 / 2.6 | 80.9 / 2.1 | 122.7 / 1.9 |
| Flow at 1.6 km, 300–2400 s (veh/h) | 2,085 | 1,901 | 1,748 | 1,588 |
| Flow at 1.6 km while the bottleneck is active (veh/h) | 2,057 | 1,848 | 1,571 | 1,341 |
| Speed SD alongside the acceleration lane (km/h) | 23.9 | 21.8 | 31.1 | 35.4 |
| Speed SD 300–500 m upstream of it (km/h) | 12.0 | 33.4 | 40.4 | 39.4 |
| Disturbance ratio (upstream ÷ alongside) | 0.49 | 1.55 | 1.30 | 1.12 |
| Largest queue at the mainline entrance (veh) | 13 | 114 | 210 | 286 |
| Stops at the lane end (per run) | 3.8 | 0.7 | 0.3 | 0.45 |
| Takeover episodes per run (per ACC vehicle) | – | 366 (1.1) | 519 (0.75) | 680 (0.65) |
| Time under driver control (share of ACC vehicle time) | – | 7.6% | 4.4% | 2.8% |
| Braking harder than 3 m/s², HDV / ACC (veh·s) | 41 / – | 43 / 5 | 23 / 13 | 12 / 37 |
| Smallest net gap (m) | 1.01 | 1.01 | 1.01 | 1.01 |

Paired changes against A on the same seeds (mean, paired bootstrap 95% interval, seeds with a higher value than A):

| | B25 | B50 | B75 |
|---|---|---|---|
| Total delay (veh·h) | +36.3 [32.0, 40.6], 20/20 | +68.2 [62.1, 74.1], 20/20 | +109.8 [98.3, 121.5], 20/20 |
| Flow at 1.6 km (veh/h) | −184 [−201, −167], 0/20 | −337 [−359, −315], 0/20 | −497 [−535, −461], 0/20 |
| Flow while active (veh/h, 18 seeds) | −207 [−245, −166] | −490 [−529, −446] | −717 [−755, −676] |
| Disturbance ratio | +1.06 [0.86, 1.24], 20/20 | +0.81 [0.61, 0.98], 18/20 | +0.62 [0.43, 0.79], 16/20 |

All vehicles leave before 60 min in every run; no collision (the run asserts this every step).

**Against the prediction.** Delay, discharge and the disturbance ratio all moved in the predicted direction and
within the predicted ranges (B75 delay 8.4 × A, predicted about 10 ×; B25 3.4 ×, predicted 3–5 ×). The order
B25 < B50 < B75 is monotonic on every seed.

**Interpretation.**

- **Delay.** Every ACC share increases total delay, and all of the increase is on the mainline. Ramp delay
  halves because the slower mainline offers more usable gaps (stops at the lane end fall from 3.8 to below 1).
- **Discharge.** The flow leaving the merge falls by 9, 16 and 24%, and by 10, 24 and 35% while the bottleneck
  is active. This matches the queue-discharge test (`mechanism_tests.txt`: 2,089 veh/h all HDV, 1,743 with
  every 4th vehicle ACC, 1,147 all ACC). With k_p = 0.0131 s⁻² and k_v = 0.2692 s⁻¹ an ACC vehicle trails a
  leader that accelerates at 2 m/s² by about 7 m/s, so it leaves a long gap every time traffic speeds up again.
- **Disturbances.** In A, speed variation 300–500 m upstream of the acceleration lane is a third of that
  alongside it on 16 of 20 seeds (the other 4 had long queues): merge disturbances fade. With any ACC share the
  ratio exceeds 1 on every seed: each slowdown grows into a stop-and-go wave that runs back to the entrance
  (`seed110_speed_maps.png`). The ratio falls from B25 to B75 because the merge area itself becomes more
  variable, not because the waves weaken (upstream SD stays near 40 km/h). In the platoon test a 10 m/s dip
  shrinks to 5.4 m/s behind 40 HDVs, stays at 9.1 m/s with every 4th vehicle ACC and grows to 16.2 m/s behind
  40 ACC vehicles: ACC removes the damping that the HDVs provide.
- **Spacing is not the cause.** With η = 2 m and h = 1.2 s (the HDV spacing at every speed) or η = 7.57 m and
  h = 1.0 s, the development seeds showed the same collapse. The result comes from the fitted gains.
- **Braking and gaps.** The smallest gap (about 1 m, set by forced merges near the lane end) and the total time
  of hard braking hardly change; hard braking shifts from HDVs to ACC vehicles as the share grows. Drivers
  take over 0.65–1.1 times per ACC vehicle, for 3–8% of ACC vehicle time.

**Limitations.**

- Gunter et al. fitted the law to car following with small speed oscillations at highway speed. Repeated
  stop-and-go and discharge from standstill are extrapolations. Commercial systems switch between speed and gap
  regulation (for example the protocol described by Adebisi et al. 2020) and would probably accelerate sooner
  once the gap opens, so the size of the effect is likely an upper bound for this controller. The direction
  (slower discharge, waves that do not fade) agrees with Gunter et al.'s finding that the vehicle is not
  string stable.
- Time step: on development seed 1, dt = 0.05 s instead of 0.1 s changed total delay by +10% (A), −8% (B25)
  and +35% (B75); the order and direction did not change. Severe stop-and-go is sensitive to timing, which is
  why only 20-seed paired comparisons are interpreted.
- With ACC the queue reaches the mainline entrance; its waiting is included in the delay, but absolute delays
  depend on the 1.4 km of road upstream of the acceleration lane.
- One demand level and exact sensor readings; the changed-demand and degraded-information tests are not run.
- The takeover rule is a project choice and sets the cut-in response whenever the driver would brake harder
  than 2 m/s².

## Changes made while checking (before the evaluation runs)

1. **Takeover rule.** The first rule (command at most −Δv²/[2 max(s − s0, 0.1 m)] while that exceeds
   2 m/s²) let a merged ACC vehicle creep into its leader at 0.57 m/s on seed 101 at 25% ACC: inside s0 the
   floor capped the required braking below the threshold, and the fitted law brakes only about 0.4 m/s² at a
   zero gap. Replaced by a takeover with the HDV law (IDM+CAH) whenever it brakes harder than 2 m/s² and
   harder than the ACC, as Adebisi et al. (2020) hand emergency braking to a conventional car-following model.
2. **Takeover hysteresis.** Taking over and handing back on the same condition chattered (about 8,000
   episodes of 0.17 s per run). The driver now hands back only once the HDV law no longer brakes harder than
   the ACC, so acceleration is continuous at the handover (platoon test: 848 → 40 episodes).
3. **Spacing.** Checked η = 2 m / h = 1.2 s and η = 7.57 m / h = 1.0 s on development seeds 1–4 (see above);
   h = 1.27 s and η = 7.57 m were kept.
4. **Measures added** before the evaluation runs: flow while the bottleneck is active and the disturbance ratio.

## Files

| File | Content |
|---|---|
| `eval_seeds_101-120/comparison.json` | Per-seed measures, case means and paired changes |
| `eval_seeds_101-120/comparison_console.txt` | Delay and flow per seed and case |
| `eval_seeds_101-120/parts/`, `run.sh` | The four batches it was merged from, and how to rerun them |
| `eval_seeds_101-120/acc_summary.png` | Delay, flow, disturbance ratio and speed variation by case |
| `seed110_speed_maps.png` | Speed maps for seed 110 (A delay close to the 20-seed mean) in all four cases |
| `mechanism_tests.txt` | Output of `acc_mechanism.py` (platoon disturbance, queue discharge) |
