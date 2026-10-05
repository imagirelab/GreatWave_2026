#!/usr/bin/env bash
# 美術の見本06・B-LOBES：測りの鎖（関門 G2・S11 の目標・T5/T6・背の測り S4 → 測る規則）。as05 の run_measure_chain*.sh と同じ道具を、置き場を替えて呼ぶ。
# 使い方：bash Tools/GWWaveGen/as06/lobes_measure.sh <描画の名前（LB1・LB2）> <組み立ての置き場（assemble・assemble2）> <形の置き場（final・final2）>
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
N=$1; ASM=$2; FIN=$3
P6=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/lobes
LG=$P6/$ASM/logs
NV=$(py -3.10 -c "import json;print(json.load(open('$P6/$FIN/mesh/hero_smooth_as06l.json'))['vertices'])")
date
RB=$P6/$ASM/render LG=$LG BEFORE=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh $N > $LG/eval_$N.txt 2>&1; echo eval $?
py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure $P6/$ASM/measure/cand_$N.json $P6/$ASM/measure/targets_$N.json > $LG/targets_$N.log 2>&1; echo targets $?
py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $P6/$ASM/render/$N --mesh $P6/$ASM/mesh/union_AS06L.json --out $P6/$ASM/measure/t5t6_${N}_v.json --parts views,t6 --hero-verts $NV > $LG/t5t6_${N}_v.log 2>&1; echo t56v $?
py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $P6/$ASM/render/$N --mesh $P6/$ASM/mesh/union_AS06L.json --out $P6/$ASM/measure/t5t6_${N}_ct.json --parts crest,tt --hero-verts $NV --ttnc $P6/$ASM/render/${N}_ttnc > $LG/t5t6_${N}_ct.log 2>&1; echo t56ct $?
py -3.10 -B Tools/GWWaveGen/as02/back_measure.py $P6/$FIN/eval_AS06L_back_measure.json AS02C=Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz AS04=$P6/$FIN/cand/kstarAS06L_a45_rows.npz > $LG/back_measure.log 2>&1; echo back $?
AS06L_ASM=$ASM AS06L_FIN=$FIN py -3.10 -B Tools/GWWaveGen/as06/lobes_rules.py $N > $LG/rules_$N.log 2>&1; echo rules $?
tail -1 $LG/rules_$N.log
date
echo MEASURE_DONE
