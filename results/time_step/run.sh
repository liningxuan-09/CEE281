#!/bin/sh
# Reproduce the time-step check from the project folder (about 15 minutes on 4 cores).
cd "$(dirname "$0")/../.."
D=results/time_step
for DT in 0.1 0.05; do
  for S in 101-102 103-104 105-106 107-108 109-110 111-112 113-114 115-116 117-118 119-120; do
    python3 -B dt_check.py --dt $DT --seeds $S --save $D/dt_$DT/parts/part_$S.json
  done
  python3 -B dt_check.py --merge $D/dt_$DT/parts/part_*.json --save $D/dt_$DT/comparison.json
done
python3 -B dt_check.py --summary $D/dt_0.1/comparison.json $D/dt_0.05/comparison.json --out $D
