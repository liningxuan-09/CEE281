#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 2 minutes on 4 cores).
cd "$(dirname "$0")/../../../.."
D=results/acc_demand/peak_550/eval_seeds_101-120
for S in 101-105 106-110 111-115 116-120; do
  python3 -B acc_compare.py --ramp-peak 550 --seeds $S --save $D/parts/part_$S.json
done
python3 -B acc_compare.py --merge $D/parts/part_101-105.json $D/parts/part_106-110.json $D/parts/part_111-115.json $D/parts/part_116-120.json --save $D/comparison.json
