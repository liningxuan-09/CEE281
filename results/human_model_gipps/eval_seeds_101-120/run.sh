#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 1 minute on 4 cores).
# In this report "A" is case C (all Gipps drivers) and "B50" is case D (50% ACC, other vehicles Gipps).
cd "$(dirname "$0")/../../.."
D=results/human_model_gipps/eval_seeds_101-120
for S in 101-102 103-104 105-106 107-108 109-110 111-112 113-114 115-116 117-118 119-120; do
  python3 -B acc_compare.py --cases A,B50 --set human_model=gipps --seeds $S --save $D/parts/part_$S.json
done
python3 -B acc_compare.py --merge $D/parts/part_*.json --save $D/comparison.json
