# Main ACC share study

Cases A (0% ACC), B25, B50 and B75; unmetered ramp; baseline demand; paired seeds 101–120. Main gains: `k_p = 0.0131 s⁻²`, `η = 7.5699 m`, `h = 1.27 s`, `k_v = 0.80 s⁻¹`.

The time gap matches nominal pure-ACC flow to HDV capacity. The speed gain is the smallest 0.05-step value satisfying the delay-free linear string-stability condition. It is a project design, not a measured commercial setting.

**Pre-run prediction (2 Nov 2026):** total delay near A, no entrance-reaching queue, similar flow, and disturbance ratio near A at B25.

## Core results

Means over seeds; total-delay changes are paired differences from A with 95% intervals.

| Measure | A | B25 | B50 | B75 |
|---|---:|---:|---:|---:|
| Total delay (veh·h) | 17.1 | 15.6 | 14.7 | 12.8 |
| Change from A (veh·h), 95% interval | — | −1.51 [−3.03, −0.27] | −2.44 [−3.96, −0.98] | −4.33 [−6.16, −2.63] |
| Change from A (%) | — | −9% | −14% | −25% |
| Mainline / ramp delay (veh·h) | 11.4 / 5.7 | 13.9 / 1.7 | 13.4 / 1.2 | 11.9 / 0.9 |
| Congested time (s) | 243 | 344 | 89 | 11 |
| Disturbance ratio | 0.57 | 0.91 | 1.18 | 1.18 |
| Longest queue (m) | 540 | 930 | 915 | 590 |
| Lane-end stops per run | 4.3 | 1.5 | 0.5 | 0.0 |
| Hard-braking merges per run | 32 | 82 | 90 | 103 |

Total delay falls at every share and all three intervals are below zero; the pre-run prediction of "near A" does not hold. The saving comes from the ramp (ramp delay falls 70–84%, lane-end stops disappear), while mainline delay rises at B25/B50 and hard-braking merges triple. Disturbances travel further upstream (ratio above 1 at B50/B75), but no queue reaches the entrance in any case. All trips finish within 60 min.

**Effect of the road length.** With the earlier 2 km road (1.05 km before the acceleration lane) the same study gave −3%, −3% and −6% with intervals that included zero: queues in the ACC cases reached the entrance, and vehicles waiting to enter added delay that hid the saving. The mainline now runs 2.05 km before the lane.

**Time step.** The total-delay result is the same with dt = 0.05 s (B50: −2.4 veh·h at both steps), but the split between mainline and ramp delay in case A is not ([time_step](../time_step/README.md)).

## Reproduction

Run from the project root:

```bash
sh results/acc_main/eval_seeds_101-120/run.sh
python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json
python3 -B acc_mechanism.py
```

`comparison.json` stores all metrics and paired intervals; `acc_summary.png` is the summary figure. See [speed-gain ablation](../acc_ablation_kv/README.md), [sensor delay](../acc_sensor_delay/README.md) and [demand](../acc_demand/README.md).
