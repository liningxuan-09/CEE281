# Published ACC speed gain: k_v = 0.2692 s⁻¹

Same baseline, spacing (`h = 1.27 s`, `η = 7.5699 m`), takeover rule and seeds 101–120 as the [main study](../../acc_main/README.md). Only the speed gain is restored to the Gunter et al. fitted value; this is not the complete published parameter set.

**Pre-run prediction (2 Nov 2026):** delay about 3–5 times A at B25 and 10 times A at B75, with lower discharge and growing upstream disturbances.

## Core results

| Measure, 20-seed mean | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 14.9 | 51.2 | 83.0 | 124.6 |
| Change from A (veh·h), 95% interval | — | +36.3 [32.0, 40.6] | +68.2 [62.1, 74.1] | +109.8 [98.3, 121.5] |
| Flow at 1.6 km (veh/h) | 2,085 | 1,901 | 1,748 | 1,588 |
| Disturbance ratio | 0.49 | 1.55 | 1.30 | 1.12 |
| Largest mainline entry queue (vehicles) | 13 | 114 | 210 | 286 |

Delay rises on every seed, consistent with the prediction. The delay-free linear criterion is −1.30; in the 40-vehicle platoon test, a 10 m/s dip grows to 16.2 m/s. The fitted law's stop-and-go behavior and takeover are model assumptions, not validation of a commercial ACC system.

## Reproduction

Run from the project root:

```bash
sh results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/run.sh
```

`eval_seeds_101-120/comparison.json` contains the full results. See the [ablation overview](../README.md) for the comparison figure.
