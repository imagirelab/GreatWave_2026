#!/usr/bin/env bash
# 美術の見本05 の直しの回（fix1）・形 B：設計の .json から、行の作り直し（shapeB_build.py）→ 材質の属性 → 包み → 静止のメッシュ（shapeB_mesh.py）
# → wave4 fix1 とつなぐ（w4_merge.py）までを、置き場 <根> の下に作る。shapeB_pipeline.sh（変えない）の写しで、置き場を引数にしただけ。
# 使い方：bash Tools/GWWaveGen/as05/fx5_B_pipeline.sh <根（絶対パス）> <設計.json> [full]
#   full を付けると、背の測り・評価基準・爪の置き直しも作る（最後の版）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
F=$1; D=$2; MODE=${3:-try}
C=$F/final/cand
N=kstarAS05B_a45
LG=$F/logs
T5=Tools/GWWaveGen/as05
mkdir -p $C $F/attr/pl29 $F/attr/param $F/attr/a $LG $F/union
date
py -3.10 -B $T5/fx5_B_build.py $C/$N $D > $LG/build.log 2>&1; echo build $?
if [ "$MODE" = "full" ]; then
py -3.10 -B Tools/GWWaveGen/as02/back_measure.py $F/final/eval_AS05B_back_measure.json AS02C=Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz AS04=$C/${N}_rows.npz > $LG/back_measure.log 2>&1; echo back $?
py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py $C/${N}_rows.npz $F/final/rubric_AS05B.json --gate > $LG/rubric_AS05B.log 2>&1; echo rubric $?
fi
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --out $F/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --attr $F/attr/pl29/pl29_hero_attr_f32.bin --out $F/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $F/attr/pl29/pl29_hero_attr_f32.bin --param $F/attr/param/s01_param_f32.bin --out $F/attr/a --v2 --gwb $C/$N.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/$N.gwb --rows $C/${N}_rows.npz --meta $C/${N}_meta.json --out $F/hero_pkg_AS05B > $LG/pkg.log 2>&1; echo pkg $?
py -3.10 -B $T5/fx5_B_mesh.py $F $N > $LG/mesh.log 2>&1; echo mesh $?
(cd Tools/GWWaveGen/as04 && py -3.10 -B w4_merge.py $F/mesh/hero_smooth_as05b.json G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json $F/union/union.json > $LG/merge.log 2>&1); echo merge $?
if [ "$MODE" = "full" ]; then
py -3.10 -B -c "
import sys; sys.path.insert(0,'Tools/GWWaveGen/as04'); sys.stdout.reconfigure(encoding='utf-8')
import shape_claws as SCL
SCL.OUT='$F/claws'; SCL.NEW_ROWS='$F/final/cand/${N}_rows.npz'
SCL.main()" > $LG/claws.log 2>&1; echo claws $?
fi
date
