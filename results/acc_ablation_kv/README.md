# Speed-gain ablation

Only `k_v` changes; demand, spacing, takeover, ACC shares and seeds 101–120 are identical. Baseline A has mean delay 17.1 veh·h.

| Setting | k_v (s⁻¹) | Delay-free linear stability criterion | Delay B25 / B50 / B75 (veh·h) |
|---|---:|---:|---|
| [Main controller](../acc_main/README.md) | 0.80 | +0.05 | 15.6 / 14.7 / 12.8 |
| [Published gain](fitted_kv_0.2692/README.md) | 0.2692 | −1.30 | 52.0 / 81.1 / 127.1 |

The published gain produces growing platoon disturbances and much higher delay. Full per-seed results are in each run's `eval_seeds_101-120/comparison.json`.

## Reproduction

Run the main study first, then the fitted-gain study; redraw the comparison from the project root:

```bash
sh results/acc_main/eval_seeds_101-120/run.sh
sh results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/run.sh
sh make_figures.sh        # redraws the comparison figure
```
