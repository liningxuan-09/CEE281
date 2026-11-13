#!/bin/sh
# ALINEA with the meter signal cycle (green 2 s + red >= 2 s, max 900 veh/h), 20 evaluation seeds, in parts.
C=A,A-ALINEA,A-ALINEA-fault,A-ALINEA-miss2,A-ALINEA-noise2,A-ALINEA-delay30
D=results/tmc_alinea/eval_seeds_101-120
for s in 101-104 105-108 109-112 113-116 117-120; do
  python3 -B tmc_compare.py --seeds $s --cases $C --workers 4 --save $D/parts/part_$s.json > $D/parts/part_$s.txt
done
python3 -B tmc_compare.py --merge $D/parts/part_*.json --save $D/comparison.json > $D/comparison_console.txt
