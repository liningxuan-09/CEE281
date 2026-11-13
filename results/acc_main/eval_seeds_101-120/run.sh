#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 2 minutes on 4 cores).
cd "$(dirname "$0")/../../.."
D=results/acc_main/eval_seeds_101-120
python3 -B acc_compare.py --controller stable --seeds 101-105 --save $D/parts/part_101-105.json
python3 -B acc_compare.py --controller stable --seeds 106-110 --save $D/parts/part_106-110.json
python3 -B acc_compare.py --controller stable --seeds 111-115 --save $D/parts/part_111-115.json
python3 -B acc_compare.py --controller stable --seeds 116-120 --save $D/parts/part_116-120.json
python3 -B acc_compare.py --merge $D/parts/part_101-105.json $D/parts/part_106-110.json $D/parts/part_111-115.json $D/parts/part_116-120.json --save $D/comparison.json
