# Baseline: all-human traffic, unmetered ramp

Uses the [default road, demand and driver settings](../../README.md#model-and-evaluation). Mainline vehicles do not yield in advance.

| Measure, mean over seeds 101–120 | Value |
|---|---:|
| Total delay (veh·h) | 17.1 |
| Mainline / ramp delay (veh·h) | 11.4 / 5.7 |
| Lane-end stops per run | 4.3 |
| Congested time at the merge (min) | 4.0 |
| Longest queue upstream of the lane end (m) | 540 |

The same case A is stored in the [TMC](../tmc_alinea/eval_seeds_101-120/comparison.json) and [ACC](../acc_main/eval_seeds_101-120/comparison.json) comparisons. `seed9/` is a single-seed demo (replay page and figures).

`feasibility.json` is the feasibility check (`python3 -B feasibility.py`) on 13 development seeds: 7 seeds, including the demonstration seed 9, meet every seed criterion; 5 show too weak a bottleneck and 1 has too many speeds below 30 km/h. Its single-seed time-step criterion is not met for seed 9; see [time_step](../time_step/README.md) for the 20-seed check.

## Arrival check and reproduction

```bash
python3 -B arrival_check.py
python3 -B run_demo.py --save --gif --output results/baseline/seed9     # the demo folder (must not exist yet)
```

Outputs: `arrivals/arrival_check.json` and `arrivals/poisson_arrivals.png`. On the evaluation seeds, the exponential-headway KS tests give p = 0.15 (mainline) and 0.61 (ramp peak); both 30 s count variance-to-mean ratios are 0.99. These are input-process checks, not field validation.
