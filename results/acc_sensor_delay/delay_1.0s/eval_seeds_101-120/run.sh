#!/bin/sh
# Reproduce comparison.json from the project folder (case A is reused from the main study).
cd "$(dirname "$0")/../../../.."
D=results/acc_sensor_delay/delay_1.0s/eval_seeds_101-120
A=results/acc_main/eval_seeds_101-120/comparison.json
for S in 101-105 106-112 113-120; do
  python3 -B acc_compare.py --set acc_sensor_delay=1.0 --a-from $A --seeds $S --save $D/parts/part_$S.json
done
python3 -B acc_compare.py --merge $(for S in 101-105 106-112 113-120; do printf '%s ' $D/parts/part_$S.json; done) --save $D/comparison.json
