# Main ACC share study

Cases A (0% ACC), B25, B50 and B75; unmetered ramp; baseline demand; paired seeds 101–120. Main gains: `k_p = 0.0131 s⁻²`, `η = 7.5699 m`, `h = 1.27 s`, `k_v = 0.80 s⁻¹`.

The time gap matches nominal pure-ACC flow to HDV capacity. The speed gain is the smallest 0.05-step value satisfying the delay-free linear string-stability condition. It is a project design, not a measured commercial setting.

**Pre-run prediction (2 Nov 2026):** total delay near A, no entrance-reaching queue, similar flow, and disturbance ratio near A at B25.

## Core results

Means over seeds; total-delay changes are paired differences from A with 95% intervals.

| Measure | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 14.9 | 14.5 | 14.5 | 14.0 |
| Change from A (veh·h), 95% interval | — | −0.39 [−1.60, +0.61] | −0.40 [−1.92, +0.86] | −0.84 [−2.45, +0.47] |
| Mainline / ramp delay (veh·h) | 9.9 / 5.0 | 12.0 / 2.4 | 13.2 / 1.2 | 13.1 / 0.9 |
| Congested time (s) | 251 | 297 | 89 | 12 |
| Disturbance ratio | 0.49 | 0.94 | 1.17 | 1.04 |
| Lane-end stops per run | 3.8 | 2.8 | 0.3 | 0.0 |
| Hard-braking merges per run | 30 | 81 | 85 | 91 |

Total-delay intervals include zero; this does not establish equivalence. At B50/B75, local congestion decreases, delay shifts from ramp to mainline, and hard-braking merges increase. The B25 disturbance ratio exceeds the pre-run expectation. All trips finish within 60 min.

## Reproduction

Run from the project root:

```bash
sh results/acc_main/eval_seeds_101-120/run.sh
python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110
python3 -B acc_mechanism.py
```

`comparison.json` stores all metrics and paired intervals; `acc_summary.png` is the summary figure. Use `python3 -B report_sync_figures.py` for the current report's 0–45 min trajectories. See [speed-gain ablation](../acc_ablation_kv/README.md), [sensor delay](../acc_sensor_delay/README.md) and [demand](../acc_demand/README.md).
