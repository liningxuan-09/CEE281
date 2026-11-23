#!/bin/sh
# Reproduce comparison.json from the project folder (each part takes about 1 minute on 4 cores).
# No control versus ALINEA, with the observation-defect cases.
cd "$(dirname "$0")/../../.."
D=results/tmc_alinea/eval_seeds_101-120
for S in 101-102 103-104 105-106 107-108 109-110 111-112 113-114 115-116 117-118 119-120; do
  python3 -B tmc_compare.py --seeds $S --cases A,A-ALINEA,A-ALINEA-fault,A-ALINEA-miss2,A-ALINEA-noise2,A-ALINEA-delay30 --save $D/parts/part_$S.json > $D/parts/part_$S.txt
done
python3 -B tmc_compare.py --merge $D/parts/part_*.json --save $D/comparison.json > $D/comparison_console.txt
