#!/bin/sh
# Redraw the summary figures from the saved 20-seed results (about 1 minute on 4 cores).
# Run from anywhere:  sh make_figures.sh
# The 20-seed experiments themselves are rerun with the run.sh in each results folder (README, "Reproducing the figures and tables").
set -e
cd "$(dirname "$0")"
python3 -B arrival_check.py
python3 -B seed_figure.py
python3 -B tmc_demand.py
python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110
python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json --seed 110 --trajectories
python3 -B acc_figures.py --compare results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/comparison.json \
    results/acc_main/eval_seeds_101-120/comparison.json --labels "fitted, kv = 0.2692" "string stable, kv = 0.80" \
    --title "Ablation: speed-difference gain k_v (same law)" --out results/acc_ablation_kv/ablation_kv_comparison.png
python3 -B acc_figures.py --compare results/acc_main/eval_seeds_101-120/comparison.json \
    results/acc_sensor_delay/delay_0.5s/eval_seeds_101-120/comparison.json \
    results/acc_sensor_delay/delay_1.0s/eval_seeds_101-120/comparison.json \
    --labels "no delay (main)" "sensor delay 0.5 s" "sensor delay 1.0 s" --title "Sensor delay (main controller)" \
    --subtitle "Main controller; same seeds and demand; only the age of the gap and leader-speed readings differs." \
    --out results/acc_sensor_delay/delay_comparison.png
echo "Figures redrawn."
