# ALINEA demand sensitivity

Change one demand at a time around mainline 1,700 veh/h and ramp peak 450 veh/h. Each combination compares no control with ALINEA on the same seeds 101–120; road and controller settings are unchanged.

**Pre-run expectations:** little effect at low demand; mainline protection with greater ramp overflow at high demand. At mainline 1,900 veh/h, the mainline benefit was expected to weaken.

## Core results

Delays are mean veh·h; changes are paired ALINEA minus no control, with 95% intervals.

| Mainline / ramp peak (veh/h) | No control | ALINEA | Change [95%] | ALINEA storage exceedances |
|---|---:|---:|---|---:|
| 1,700 / 350 | 8.3 | 8.4 | +0.1 [−0.1, +0.3] | 2/20 |
| 1,700 / 450 | 14.9 | 15.6 | +0.8 [−0.1, +1.6] | 9/20 |
| 1,700 / 550 | 32.5 | 29.7 | −2.8 [−4.6, −1.1] | 20/20 |
| 1,500 / 450 | 5.3 | 5.6 | +0.3 [+0.2, +0.5] | 0/20 |
| 1,900 / 450 | 53.1 | 43.0 | −10.1 [−13.0, −7.5] | 20/20 |

ALINEA reduces total delay 9–19% at high demand, but exceeds 28-vehicle storage on every seed. Mean maximum queues are 61 and 83 vehicles. Contrary to the expectation, mainline 1,900 has the largest mainline-delay reduction (46%).

## Reproduction

Run from the project root:

```bash
sh results/tmc_alinea/demand/run.sh
```

Outputs in `eval_seeds_101-120/`: `comparison.json`, `summary.json`, `summary.md` and `demand_comparison.png`. To redraw only the summary, run `python3 -B tmc_demand.py`.
