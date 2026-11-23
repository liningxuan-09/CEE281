# Trajectory figures

Drawn by `python3 -B final_figures.py` (also run by `sh make_figures.sh`) in the style of the mid-report figures: whole road and 0–45 min, one line per mainline vehicle coloured by speed, dashed lines at the acceleration lane, dotted line at the end of demand, total delay and congested time under each panel. All panels use the demonstration seed 9 (the same as the `seed9/` demo folders) with identical arrivals; `--seed N` draws another seed.

| File | Panels |
|---|---|
| `trajectories_alinea.png` | Baseline, ALINEA |
| `trajectories_acc.png` | Main ACC study: 0%, 25%, 50% and 75% ACC |
| `trajectories_kv.png` | 50% ACC with the main controller and with the fitted gain k_v = 0.2692 (ablation) |
