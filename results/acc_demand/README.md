# ACC demand sensitivity: ramp peak 350, 450 and 550 veh/h

Use the main controller (`k_v = 0.80 s⁻¹`) and seeds 101–120. Only ramp demand during minutes 5–35 changes; mainline demand remains 1,700 veh/h. Peak 450 is the [main study](../acc_main/README.md).

**Pre-run prediction (3 Nov 2026):** little effect at 350 veh/h; fewer lane-end stops at 550, with a B50 total-delay change between −20% and +15% relative to A.

## Core results

Mean total delay in veh·h; each row has its own paired baseline A.

| Ramp peak (veh/h) | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| 350 | 9.9 | 9.6 | 9.0 | 7.4 |
| 450 | 17.1 | 15.6 | 14.7 | 12.8 |
| 550 | 35.2 | 27.3 | 24.7 | 22.3 |

Delay falls at every demand and share, and all paired 95% intervals are below zero: 3 / 9 / 25% at 350 veh/h, 9 / 14 / 25% at 450 and 23 / 30 / 37% at 550, a larger benefit than predicted. At 550 veh/h lane-end stops fall from 10.6 per run in A to 2.9 / 0.6 / 0.3. Hard-braking merges increase at all three demands.

## Reproduction

Run from the project root:

```bash
sh results/acc_demand/peak_350/eval_seeds_101-120/run.sh
sh results/acc_demand/peak_550/eval_seeds_101-120/run.sh
sh make_figures.sh        # redraws the comparison figure
```

Each `peak_*/eval_seeds_101-120/comparison.json` contains the full metrics and paired intervals. The main study must be available before drawing the comparison.
