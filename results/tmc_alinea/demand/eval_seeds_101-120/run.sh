#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 1 minute on 4 cores).
# Changed demand, each combination without control and with ALINEA.
cd "$(dirname "$0")/../../../.."
D=results/tmc_alinea/demand/eval_seeds_101-120
for S in 101-102 103-104 105-106 107-108 109-110 111-112 113-114 115-116 117-118 119-120; do
  python3 -B tmc_compare.py --seeds $S --cases A,A-ALINEA,A-R350,A-ALINEA-R350,A-R550,A-ALINEA-R550,A-M1500,A-ALINEA-M1500,A-M1900,A-ALINEA-M1900 --save $D/parts/part_$S.json > $D/parts/part_$S.txt
done
python3 -B tmc_compare.py --merge $D/parts/part_*.json --save $D/comparison.json > $D/comparison_console.txt
python3 -B tmc_demand.py
