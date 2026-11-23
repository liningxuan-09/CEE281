#!/bin/sh
# Redraw the summary figures from the saved 20-seed results and the trajectory figures (about 2 minutes on 4 cores).
# Run from anywhere:  sh make_figures.sh
# The 20-seed experiments themselves are rerun with the run.sh in each results folder (README, "Reproducing the figures and tables").
set -e
cd "$(dirname "$0")"
python3 -B arrival_check.py
python3 -B seed_figure.py
python3 -B tmc_demand.py > /dev/null
python3 -B acc_figures.py results/acc_main/eval_seeds_101-120/comparison.json
python3 -B acc_figures.py --compare results/acc_ablation_kv/fitted_kv_0.2692/eval_seeds_101-120/comparison.json \
    results/acc_main/eval_seeds_101-120/comparison.json --labels "fitted gain, kv = 0.2692" "main controller, kv = 0.80" \
    --title "Ablation: ACC speed-difference gain k_v" \
    --subtitle "Same seeds, demand, spacing and takeover rule; only the gain k_v differs." \
    --out results/acc_ablation_kv/ablation_kv_comparison.png
python3 -B acc_figures.py --compare results/acc_main/eval_seeds_101-120/comparison.json \
    results/acc_ablation_h/h_1.69/eval_seeds_101-120/comparison.json --labels "h = 1.27 s (main)" "h = 1.6881 s (fitted)" \
    --title "Ablation: ACC time gap h" --subtitle "Same seeds, demand and gains; only the time gap h differs." \
    --out results/acc_ablation_h/ablation_h_comparison.png
python3 -B acc_figures.py --compare results/acc_main/eval_seeds_101-120/comparison.json \
    results/acc_sensor_delay/delay_0.5s/eval_seeds_101-120/comparison.json \
    results/acc_sensor_delay/delay_1.0s/eval_seeds_101-120/comparison.json \
    --labels "no delay (main)" "sensor delay 0.5 s" "sensor delay 1.0 s" --title "ACC with delayed sensor readings" \
    --subtitle "Main controller, same seeds and demand; only the age of the gap and leader-speed readings differs." \
    --out results/acc_sensor_delay/delay_comparison.png
python3 -B acc_figures.py --compare results/acc_demand/peak_350/eval_seeds_101-120/comparison.json \
    results/acc_main/eval_seeds_101-120/comparison.json results/acc_demand/peak_550/eval_seeds_101-120/comparison.json \
    --labels "ramp peak 350 veh/h" "ramp peak 450 veh/h (baseline)" "ramp peak 550 veh/h" --title "ACC effect at three ramp demands" \
    --subtitle "Main controller, same seeds and mainline demand; only the ramp peak demand differs." \
    --out results/acc_demand/demand_comparison.png
python3 -B gipps_compare.py > /dev/null
python3 -B dt_check.py --summary results/time_step/dt_0.1/comparison.json results/time_step/dt_0.05/comparison.json --out results/time_step > /dev/null
python3 -B final_figures.py
echo "Figures redrawn."
