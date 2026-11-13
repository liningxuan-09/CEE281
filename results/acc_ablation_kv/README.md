# Ablation: speed-difference gain k_v

Does string stability decide whether ACC harms the merge bottleneck? Two runs on the same 20 evaluation seeds
(101–120), same cases (A, B25, B50, B75), control law, spacing (η = 7.57 m, h = 1.27 s), takeover and demand;
only the speed-difference gain differs.

| Run | k_v | String-stability criterion k_p h² + 2 k_v h − 2 | Total delay B25 / B50 / B75 (veh·h; A = 14.9) |
|---|---:|---:|---|
| `fitted_kv_0.2692/` (Gunter et al. fit) | 0.2692 s⁻¹ | −1.30 (unstable) | 51.2 / 83.0 / 124.6 |
| `../acc_main/` (main controller) | 0.80 s⁻¹ | +0.05 (stable) | 14.5 / 14.5 / 14.0 |

| File | Content |
|---|---|
| `ablation_kv_comparison.png` | Delay, flow after the merge, disturbance ratio and hard-braking merges for both runs |
| `mechanism_tests.txt` | Deterministic platoon-disturbance and queue-discharge tests (`acc_mechanism.py`); the two rows that matter here are "main (kv = 0.80)" and "Gunter fit (kv = 0.2692)" |
| `fitted_kv_0.2692/` | The run with the fitted gain: prediction, results, diagnosis and the changes made while checking |

Rebuild:

```bash
python3 -B acc_figures.py --compare results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/comparison.json \
    results/acc_main/eval_seeds_101-120/comparison.json --labels "fitted, kv = 0.2692" "string stable, kv = 0.80" \
    --title "Ablation: speed-difference gain k_v (same law)" --out results/acc_ablation_kv/ablation_kv_comparison.png
python3 -B acc_mechanism.py > results/acc_ablation_kv/mechanism_tests.txt
```
