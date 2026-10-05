#!/usr/bin/env bash
# 美術の見本06 の組み立て（Q34）：段の行 R8 と塊 LB2 を、同じ描画の決まり（AS05 の材質・爪 35 本・一艘目の船は相似 0.6・7 視点・波頭の回り台 8 方位・
# 回り台 12 方位、爪あり・なし）で Unity に描き、同じ測りの鎖（関門 G2・S11 の目標・T5/T6）と規則（asm6_rules.py）を通す。
# 置き場：Build/Polish/sample06/assemble（Git の対象外）。形・材質の属性・合わせた静止のメッシュは作りの物をそのまま使う（変えない）。
# 爪の並び：R8 は作りのまま。LB2 は claw074 だけを asm6_claws.py で相似の手前へ（原画視点で隠れていたため）。
# 引数：段（render・measure・rules を , で区切って。既定は全部）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
ST=${1:-render,measure,rules}
P=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish
PA=$P/sample06/assemble
LG=$PA/logs
TL=Tools/GWWaveGen/as06
R_UNION=$P/sample06/rows/mesh/union_AS06R_d_f1.json
R_HERO=$P/sample06/rows/final_d/mesh/hero_smooth_as06r.json
R_CL=Build/Polish/sample06/rows/final_d/claws/ds33_claw_layout.json
L_UNION=$P/sample06/lobes/assemble2/mesh/union_AS06L.json
L_HERO=$P/sample06/lobes/assemble2/mesh/hero_AS06L_edge.json
L_CL=Build/Polish/sample06/assemble/lobes/claws/ds33_claw_layout.json
mkdir -p $LG $PA/measure
date
if [[ $ST == *render* ]]; then
  for J in "R R8A views,crest,tt,full,t28 $R_UNION $R_CL 1" "R R8A_ttnc tt $R_UNION $R_CL 0" "R R8AH views,full,t28 $R_HERO $R_CL 1" \
           "L LB2A views,crest,tt,full,t28 $L_UNION $L_CL 1" "L LB2A_ttnc tt $L_UNION $L_CL 0" "L LB2AH views,full,t28 $L_HERO $L_CL 1"; do
    set -- $J
    TT_CLAWS=$6 BOAT_S=0.6 bash $TL/asm6_render.sh $1 $2 $3 $4 $5 > $LG/render_$2.txt 2>&1; echo render $2 $?
  done
  cp $PA/render/R8A_ttnc/tt/*.png $PA/render/R8A/tt/
  cp $PA/render/LB2A_ttnc/tt/*.png $PA/render/LB2A/tt/
  grep -h "RENDER_DONE\|OOM\|BOAT_DONE\|error" $LG/render_*.txt
fi
chain() {   # 引数：名前 静止のメッシュ 主役波の頂点の数 層の印
  N=$1; U=$2; NV=$3; LAB=$4
  cat > $PA/measure/cand_$N.json << EOT
{"name": "AS06_asm6_$N", "rows": "$5", "row_labels": "$LAB",
 "meshes": [{"path": "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json", "role": "wave4", "layer": 0}],
 "render_dir": "$PA/render/$N"}
EOT
  RB=$PA/render LG=$LG BEFORE=$P/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh $N > $LG/eval_$N.txt 2>&1; echo eval $N $?
  py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure $PA/measure/cand_$N.json $PA/measure/targets_$N.json > $LG/targets_$N.log 2>&1; echo targets $N $?
  py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $PA/render/$N --mesh $U --out $PA/measure/t5t6_${N}_v.json --parts views,t6 --hero-verts $NV > $LG/t5t6_${N}_v.log 2>&1; echo t56v $N $?
  py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $PA/render/$N --mesh $U --out $PA/measure/t5t6_${N}_ct.json --parts crest,tt --hero-verts $NV --ttnc $PA/render/${N}_ttnc > $LG/t5t6_${N}_ct.log 2>&1; echo t56ct $N $?
}
if [[ $ST == *measure* ]]; then
  chain R8A $R_UNION 326400 $P/sample06/rows/measure/quick_R8/row_labels.npy $P/sample06/rows/final_d/final/cand/kstarAS06R_a45_rows.npz > $LG/chain_R8A.txt 2>&1 &
  chain LB2A $L_UNION 324000 $P/sample06/lobes/final2/cand/kstarAS06L_a45_labels.npy $P/sample06/lobes/final2/cand/kstarAS06L_a45_rows.npz > $LG/chain_LB2A.txt 2>&1
  wait
  cat $LG/chain_R8A.txt $LG/chain_LB2A.txt
fi
if [[ $ST == *rules* ]]; then
  py -3.10 -B $TL/asm6_rules.py rows R8A > $LG/rules_R8A.log 2>&1; echo rules rows $?; tail -1 $LG/rules_R8A.log
  py -3.10 -B $TL/asm6_rules.py lobes LB2A > $LG/rules_LB2A.log 2>&1; echo rules lobes $?; tail -1 $LG/rules_LB2A.log
fi
date
echo ASM6_DONE
