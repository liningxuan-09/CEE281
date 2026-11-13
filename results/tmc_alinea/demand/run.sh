#!/bin/sh
# Changed-demand test: 5 demand combinations x (no control, ALINEA), 20 evaluation seeds, in parts.
C=A,A-ALINEA,A-R350,A-ALINEA-R350,A-R550,A-ALINEA-R550,A-M1500,A-ALINEA-M1500,A-M1900,A-ALINEA-M1900
D=results/tmc_alinea/demand/eval_seeds_101-120
for s in 101-103 104-106 107-109 110-112 113-115 116-118 119-120; do
  python3 -B tmc_compare.py --seeds $s --cases $C --workers 4 --save $D/parts/part_$s.json > $D/parts/part_$s.txt
done
python3 -B tmc_compare.py --merge $D/parts/part_101-103.json $D/parts/part_104-106.json $D/parts/part_107-109.json \
  $D/parts/part_110-112.json $D/parts/part_113-115.json $D/parts/part_116-118.json $D/parts/part_119-120.json \
  --save $D/comparison.json > $D/comparison_console.txt
python3 -B tmc_demand.py
