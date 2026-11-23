# Time-gap ablation: 1.6881 versus 1.27 s

Only `h` changes from the [main controller](../acc_main/README.md); gains, takeover, baseline demand and seeds 101–120 are unchanged. Case A is reused from the main study. Both settings satisfy the delay-free linear stability criterion.

**Pre-run prediction (3 Nov 2026):** larger entry queues and higher total delay, about 2.5 times A at B50.

## Core results

| Measure, 20-seed mean | B25 | B50 | B75 |
|---|---:|---:|---:|
| Main h = 1.27 s: total delay (veh·h) | 15.6 | 14.7 | 12.8 |
| h = 1.6881 s: total delay (veh·h) | 22.1 | 31.5 | 41.2 |
| Change from main (veh·h), 95% interval | +6.5 [5.6, 7.4] | +16.8 [15.2, 18.5] | +28.5 [26.5, 30.5] |
| h = 1.6881 s: largest entry queue (vehicles) | 15 | 47 | 91 |

Baseline A is 17.1 veh·h. The larger time gap reduces nominal pure-ACC flow to about 1,740 veh/h; at the entry speed it is about 1,640 veh/h, below mainline demand. Delay therefore accumulates at the entrance. The predicted direction holds (delay rises on 19–20 of 20 seeds); B50 delay is 1.8 times A.

## Reproduction

Run the main study first, then from the project root:

```bash
sh results/acc_ablation_h/h_1.69/eval_seeds_101-120/run.sh
sh make_figures.sh        # redraws the comparison figure
```

Full metrics and intervals: `h_1.69/eval_seeds_101-120/comparison.json`.
