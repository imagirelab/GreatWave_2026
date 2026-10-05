#!/usr/bin/env bash
# 美術の見本06 の直しの回（Q34 の後、批評の直し。段の行 R8 → R9）：設計 design_R9.json から、行・材質の属性・静止のメッシュ・爪の置き直し（fix6_pipeline.sh）
# → T6 の内の縁（rows_b_edge.py）→ Unity の描画（fix6_render.sh：7 視点・波頭の回り台 8 方位・回り台 12 方位、爪あり・なし、一艘目の船は相似 0.6）
# → 測りの鎖（関門 G2・S11 の目標・T5/T6。組み立て asm6_run.sh の chain と同じ）→ 規則（fix6_rules.py）→ 確かめ（fix6_check.py）。
# 置き場：Build/Polish/sample06/fix（Git の対象外）。組み立てと同じ決まりで、前（B10）・直す前（R8 = 組み立ての R8A）と並べられるようにする。
# 引数：段（build・render・measure・rules を , で区切って。既定は全部）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
ST=${1:-build,render,measure,rules}
P=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish
PF=$P/sample06/fix
F=$PF/final
LG=$PF/logs
TL=Tools/GWWaveGen/as06
N=R9
UNION=$PF/mesh/union_AS06R9_f1.json
HERO=$F/mesh/hero_smooth_as06r.json
CL=${FIX6_CLAWS:-Build/Polish/sample06/fix/final/claws/ds33_claw_layout.json}
mkdir -p $LG $PF/measure $PF/mesh
date
if [[ $ST == *build* ]]; then
  bash $TL/fix6_pipeline.sh $F $PF/design_R9.json > $LG/pipe_$N.txt 2>&1; echo pipe $?; grep -v "^Mon" $LG/pipe_$N.txt | tr '\n' ' '; echo
  py -3.10 -B $TL/rows_b_edge.py $F/union/union.json $HERO $UNION > $LG/b_edge_$N.log 2>&1; echo bedge $?
  # 部品の頂点の数（parts）を合わせたメッシュの記録へ写す（fix6_check.py の食い込みの確かめが主役波と wave4 の分け目に使う）
  py -3.10 -c "
import json; u=json.load(open('$F/union/union.json',encoding='utf-8')); d=json.load(open('$UNION',encoding='utf-8'))
d['parts']=u['parts']; json.dump(d,open('$UNION','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
  py -3.10 -B $TL/rows_stretch.py $HERO
fi
if [[ $ST == *render* ]]; then
  for J in "R $N views,crest,tt,full,t28 $UNION 1" "R ${N}_ttnc tt $UNION 0" "R ${N}H views,full,t28 $HERO 1"; do
    set -- $J
    TT_CLAWS=$5 BOAT_S=0.6 bash $TL/fix6_render.sh $1 $2 $3 $4 $CL > $LG/render_$2.txt 2>&1; echo render $2 $?
  done
  cp $PF/render/${N}_ttnc/tt/*.png $PF/render/$N/tt/
  grep -h "RENDER_DONE\|OOM\|BOAT_DONE\|error" $LG/render_*.txt
fi
if [[ $ST == *measure* ]]; then
  NV=$(py -3.10 -c "import json;print(json.load(open('$HERO',encoding='utf-8'))['vertices'])")
  echo hero_vertices $NV
  py -3.10 -B $TL/rows_quick.py $F/final/cand/kstarAS06R_a45_rows.npz $F/final/cand/kstarAS06R_a45_build_log.json $PF/measure/quick_$N --sep --gate > $LG/quick_$N.log 2>&1; echo quick $?
  cat > $PF/measure/cand_$N.json << EOT
{"name": "AS06_fix6_$N", "rows": "$F/final/cand/kstarAS06R_a45_rows.npz", "row_labels": "$PF/measure/quick_$N/row_labels.npy",
 "meshes": [{"path": "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json", "role": "wave4", "layer": 0}],
 "render_dir": "$PF/render/$N"}
EOT
  RB=$PF/render LG=$LG BEFORE=$P/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh $N > $LG/eval_$N.txt 2>&1; echo eval $?
  py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure $PF/measure/cand_$N.json $PF/measure/targets_$N.json > $LG/targets_$N.log 2>&1; echo targets $?
  py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $PF/render/$N --mesh $UNION --out $PF/measure/t5t6_${N}_v.json --parts views,t6 --hero-verts $NV > $LG/t5t6_${N}_v.log 2>&1; echo t56v $?
  py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render $PF/render/$N --mesh $UNION --out $PF/measure/t5t6_${N}_ct.json --parts crest,tt --hero-verts $NV --ttnc $PF/render/${N}_ttnc > $LG/t5t6_${N}_ct.log 2>&1; echo t56ct $?
  py -3.10 -B $TL/fix6_prof.py $F/final/cand/kstarAS06R_a45_rows.npz $PF/measure/prof_$N.json --mesh=$HERO > $LG/prof_$N.log 2>&1; echo prof $?
fi
if [[ $ST == *rules* ]]; then
  py -3.10 -B $TL/fix6_check.py $PF/check/fix6_check.json > $LG/check_$N.log 2>&1; echo check $?
  py -3.10 -B $TL/fix6_rules.py $N > $LG/rules_$N.log 2>&1; echo rules $?; tail -1 $LG/rules_$N.log
fi
date
echo FIX6_DONE
