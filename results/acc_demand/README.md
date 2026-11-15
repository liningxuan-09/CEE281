# ACC demand sensitivity: ramp peak 350, 450 and 550 veh/h

Use the main controller (`k_v = 0.80 s⁻¹`) and seeds 101–120. Only ramp demand during minutes 5–35 changes; mainline demand remains 1,700 veh/h. Peak 450 is the [main study](../acc_main/README.md).

**Pre-run prediction (3 Nov 2026):** little effect at 350 veh/h; fewer lane-end stops at 550, with a B50 total-delay change between −20% and +15% relative to A.

## Core results

Mean total delay in veh·h; each row has its own paired baseline A.

| Ramp peak (veh/h) | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| 350 | 8.3 | 8.2 | 8.2 | 7.7 |
| 450 | 14.9 | 14.5 | 14.5 | 14.0 |
| 550 | 32.5 | 26.2 | 24.9 | 24.4 |

At 550 veh/h, delay falls 19–25% with paired 95% intervals below zero, a larger benefit than predicted at B50. Lane-end stops fall from 13.6 per run in A to 2.3 / 0.9 / 0.0. At 350/450 veh/h, changes are smaller. Hard-braking merges increase at all three demands.

## Reproduction

Run from the project root:

```bash
sh results/acc_demand/peak_350/eval_seeds_101-120/run.sh
sh results/acc_demand/peak_550/eval_seeds_101-120/run.sh
python3 -B acc_figures.py --compare results/acc_demand/peak_350/eval_seeds_101-120/comparison.json \
    results/acc_main/eval_seeds_101-120/comparison.json results/acc_demand/peak_550/eval_seeds_101-120/comparison.json \
    --labels "ramp 350" "ramp 450" "ramp 550" --out results/acc_demand/demand_comparison.png
```

Each `peak_*/eval_seeds_101-120/comparison.json` contains the full metrics and paired intervals. The main study must be available before drawing the comparison.
