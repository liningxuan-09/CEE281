#!/bin/sh
# Reproduce comparison.json from the project folder (case A is reused from the main study).
cd "$(dirname "$0")/../../../.."
D=results/acc_ablation_h/h_1.69/eval_seeds_101-120
A=results/acc_main/eval_seeds_101-120/comparison.json
for S in 101-106 107-113 114-120; do
  python3 -B acc_compare.py --set acc_h=1.6881 --a-from $A --seeds $S --save $D/parts/part_$S.json
done
python3 -B acc_compare.py --merge $D/parts/part_101-106.json $D/parts/part_107-113.json $D/parts/part_114-120.json --save $D/comparison.json
