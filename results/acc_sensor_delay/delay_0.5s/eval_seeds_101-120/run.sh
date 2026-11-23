#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 1 minute on 4 cores).
# Sensor delay 0.5 s. Needs the main study (case A is reused).
cd "$(dirname "$0")/../../../.."
D=results/acc_sensor_delay/delay_0.5s/eval_seeds_101-120
for S in 101-102 103-104 105-106 107-108 109-110 111-112 113-114 115-116 117-118 119-120; do
  python3 -B acc_compare.py --set acc_sensor_delay=0.5 --a-from results/acc_main/eval_seeds_101-120/comparison.json --seeds $S --save $D/parts/part_$S.json
done
python3 -B acc_compare.py --merge $D/parts/part_*.json --save $D/comparison.json
