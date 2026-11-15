# ACC sensor delay: 0.5 and 1.0 s

Main ACC controller, baseline demand and seeds 101–120. Gap and leader speed are delayed; own speed and driver takeover use current information. The all-human case A is reused from the [main study](../acc_main/README.md).

**Pre-run prediction (3 Nov 2026):** B50 delay about twice A with 0.5 s delay and five times A with 1.0 s delay; stronger upstream disturbances.

## Core results

| Sensor delay | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| 0 s: total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
| 0.5 s: total delay (veh·h) | 14.9 | 20.4 | 27.5 | 33.4 |
| 1.0 s: total delay (veh·h) | 14.9 | 31.7 | 54.1 | 77.0 |

Both delayed settings increase delay above A on every seed; paired 95% intervals exclude zero. At B50, delay is 1.8 and 3.6 times A, below the predicted magnitudes. A 10 m/s dip grows to 11.6 and 14.2 m/s in the 40-vehicle platoon test. The delay-free design is insufficient under these sensing delays. Sensor noise, dropouts and actuator lag are not tested here.

## Reproduction

Run the main study first, then from the project root:

```bash
sh results/acc_sensor_delay/delay_0.5s/eval_seeds_101-120/run.sh
sh results/acc_sensor_delay/delay_1.0s/eval_seeds_101-120/run.sh
```

Each run stores its full metrics and paired intervals in `eval_seeds_101-120/comparison.json`. Redraw `delay_comparison.png` with `sh make_figures.sh`.
