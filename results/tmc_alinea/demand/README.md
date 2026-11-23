# ALINEA demand sensitivity

Change one demand at a time around mainline 1,700 veh/h and ramp peak 450 veh/h. Each combination compares no control with ALINEA on the same seeds 101–120; road and controller settings are unchanged.

**Pre-run expectations:** little effect at low demand; mainline protection with greater ramp overflow at high demand. At mainline 1,900 veh/h, the mainline benefit was expected to weaken.

## Core results

Delays are mean veh·h; changes are paired ALINEA minus no control, with 95% intervals.

| Mainline / ramp peak (veh/h) | No control | ALINEA | Change [95%] | ALINEA storage exceedances |
|---|---:|---:|---|---:|
| 1,700 / 350 | 9.9 | 10.2 | +0.3 [+0.1, +0.5] | 1/20 |
| 1,700 / 450 | 17.1 | 16.6 | −0.5 [−1.8, +0.6] | 7/20 |
| 1,700 / 550 | 35.2 | 30.5 | −4.7 [−7.5, −2.3] | 19/20 |
| 1,500 / 450 | 6.3 | 6.7 | +0.3 [+0.1, +0.6] | 0/20 |
| 1,900 / 450 | 57.7 | 45.3 | −12.4 [−16.9, −8.4] | 20/20 |

ALINEA reduces total delay 13–22% at high demand, but exceeds 28-vehicle storage on 19 or 20 of 20 seeds. Mean maximum queues are 58 and 81 vehicles. At low demand it adds a little delay (+3% to +5%). Contrary to the expectation, the mainline benefit does not weaken at mainline 1,900: the mainline-delay reduction is 38%, the same as at ramp 550 (37%).

## Reproduction

Run from the project root:

```bash
sh results/tmc_alinea/demand/eval_seeds_101-120/run.sh
```

Outputs in `eval_seeds_101-120/`: `comparison.json`, `summary.json`, `summary.md` and `demand_comparison.png`. To redraw only the summary, run `python3 -B tmc_demand.py`.
