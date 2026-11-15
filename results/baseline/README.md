# Baseline: all-human traffic, unmetered ramp

Uses the [default road, demand and driver settings](../../README.md#model-and-evaluation). Mainline vehicles do not yield in advance.

| Measure, mean over seeds 101–120 | Value |
|---|---:|
| Total delay (veh·h) | 14.9 |
| Mainline / ramp delay (veh·h) | 9.9 / 5.0 |
| Lane-end stops per run | 3.8 |

The same case A is stored in the [TMC](../tmc_alinea/eval_seeds_101-120/comparison.json) and [ACC](../acc_main/eval_seeds_101-120/comparison.json) comparisons. `seed9/` is a separate demo; current report illustrations use seed 110.

## Arrival check and reproduction

```bash
python3 -B arrival_check.py
python3 -B run_demo.py --seed 110 --save --output results/baseline_seed110
```

Outputs: `arrivals/arrival_check.json` and `arrivals/poisson_arrivals.png`. On the evaluation seeds, the exponential-headway KS tests give p = 0.15 (mainline) and 0.61 (ramp peak); both 30 s count variance-to-mean ratios are 0.99. These are input-process checks, not field validation.
