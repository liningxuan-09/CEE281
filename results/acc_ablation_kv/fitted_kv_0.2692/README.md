# Published ACC speed gain: k_v = 0.2692 s⁻¹

Same baseline, spacing (`h = 1.27 s`, `η = 7.5699 m`), takeover rule and seeds 101–120 as the [main study](../../acc_main/README.md). Only the speed gain is restored to the Gunter et al. fitted value; this is not the complete published parameter set.

**Pre-run prediction (2 Nov 2026):** delay about 3–5 times A at B25 and 10 times A at B75, with lower discharge and growing upstream disturbances.

## Core results

| Measure, 20-seed mean | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 17.1 | 52.0 | 81.1 | 127.1 |
| Change from A (veh·h), 95% interval | — | +34.8 [29.5, 39.8] | +64.0 [56.8, 71.4] | +110.0 [96.3, 123.0] |
| Flow at 2.6 km (veh/h) | 2,079 | 1,909 | 1,780 | 1,605 |
| Disturbance ratio | 0.57 | 1.56 | 1.39 | 1.20 |
| Largest mainline entry queue (vehicles) | 13 | 77 | 168 | 234 |

Delay rises on every seed (3.0, 4.7 and 7.4 times A), consistent with the prediction at B25 and below it at B75. Even with the 3 km road the queue fills the mainline and vehicles wait to enter, so congested time and queue length are truncated in this study; total delay is not. The delay-free linear criterion is −1.30; in the 40-vehicle platoon test, a 10 m/s dip grows to 16.2 m/s. The fitted law's stop-and-go behavior and takeover are model assumptions, not validation of a commercial ACC system.

## Reproduction

Run from the project root:

```bash
sh results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/run.sh
```

`eval_seeds_101-120/comparison.json` contains the full results. See the [ablation overview](../README.md) for the comparison figure.
