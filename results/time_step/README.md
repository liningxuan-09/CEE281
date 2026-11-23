# Time-step sensitivity: dt = 0.1 s versus 0.05 s

Cases A (no control), ALINEA and B50 (50% ACC) rerun with half the integration step on seeds 101–120. Arrivals are generated before the simulation and all timing windows are in seconds, so only the step differs. The dt = 0.1 s runs reproduce the saved main results exactly. Results are for the 3 km road.

**Prediction.** None was recorded before the run. The criterion set earlier for one development seed was a change in total delay below 10%.

## Core results

Means per run in veh·h; `summary.md` has all measures and intervals.

| Case | Total delay, 0.1 s | 0.05 s | change | Mainline delay, 0.1 s | 0.05 s | Ramp delay, 0.1 s | 0.05 s |
|---|---:|---:|---|---:|---:|---:|---:|
| A | 17.1 | 16.8 | −2% [−1.26, +0.80] | 11.4 | 14.9 | 5.7 | 1.9 |
| ALINEA | 16.6 | 16.2 | −2% [−0.79, +0.11] | 9.8 | 9.7 | 6.8 | 6.5 |
| B50 | 14.7 | 14.5 | −1% [−0.47, +0.02] | 13.4 | 13.2 | 1.2 | 1.2 |

| Reported comparison | dt = 0.1 s | dt = 0.05 s |
|---|---|---|
| ALINEA − A, total delay | −0.55 [−1.83, +0.63] | −0.61 [−2.00, +0.61] |
| ALINEA − A, mainline delay | −1.57 [−2.43, −0.70] (−14%) | −5.21 [−8.08, −2.71] (−35%) |
| ALINEA − A, ramp delay | +1.02 [−0.43, +2.42] | +4.60 [+3.00, +6.58] |
| B50 − A, total delay | −2.44 [−3.96, −0.98] | −2.36 [−4.39, −0.69] |
| B50 − A, mainline delay | +2.05 [+0.54, +3.91] | −1.71 [−3.53, −0.05] |
| B50 − A, ramp delay | −4.49 [−7.65, −1.92] | −0.66 [−1.21, −0.23] |
| B50 − A, congested time (min) | −2.58 [−4.35, −0.95] | −6.58 [−10.03, −3.42] |

- **Total delay is not sensitive to the step** in any case (changes of −1% to −2%, all intervals include zero), and both total-delay conclusions hold at both steps: ALINEA does not change total delay clearly, and 50% ACC reduces it by 2.4 veh·h.
- **The split of delay in the uncontrolled case A is sensitive.** With the smaller step almost no ramp vehicle stops at the lane end (0.4 instead of 4.3 per run), ramp delay falls 67% and mainline delay rises 31%. The likely reason is that a merge is attempted once per step, so a waiting vehicle gets twice as many chances per second; this was not tested separately. ALINEA and B50 hardly change.
- **Consequences for the reported effects.** Statements about how delay is divided between mainline and ramp relative to A depend on the step: ALINEA's mainline-delay reduction grows from 14% to 35%, and the effect of 50% ACC on mainline delay changes sign (+2.1 at 0.1 s, −1.7 at 0.05 s). Total delay, congested time (lower with ALINEA and with ACC at both steps) and the direction of the ramp-delay changes do not.

## Reproduction

```bash
sh results/time_step/run.sh
```
