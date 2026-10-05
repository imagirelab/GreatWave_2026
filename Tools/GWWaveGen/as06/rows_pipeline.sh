#!/usr/bin/env bash
# 美術の見本06 の段の行（B-ROWS）：設計の .json から、行の作り直し（rows_build.py）→ 材質の属性 → 包み → 静止のメッシュ（rows_mesh.py）
# → wave4 fix1 とつなぐ（w4_merge.py）→ 爪 35 本の置き直し（shape_claws.py）までを、置き場 <根> の下に作る。
# as05/fx5_B_pipeline.sh（変えない）の写しで、道具・名前（kstarAS06R・hero_pkg_AS06R）を見本06 のものにした。
# 使い方：bash Tools/GWWaveGen/as06/rows_pipeline.sh <根（絶対パス）> <設計.json>
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
F=$1; D=$2
C=$F/final/cand
N=kstarAS06R_a45
LG=$F/logs
T6=Tools/GWWaveGen/as06
mkdir -p $C $F/attr/pl29 $F/attr/param $F/attr/a $LG $F/union
date
py -3.10 -B $T6/rows_build.py $C/$N $D > $LG/build.log 2>&1; echo build $?
py -3.10 -B Tools/GWWaveGen/as02/back_measure.py $F/final/eval_AS06R_back_measure.json AS02C=Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz AS04=$C/${N}_rows.npz > $LG/back_measure.log 2>&1; echo back $?
py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py $C/${N}_rows.npz $F/final/rubric_AS06R.json --gate > $LG/rubric_AS06R.log 2>&1; echo rubric $?
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --out $F/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --attr $F/attr/pl29/pl29_hero_attr_f32.bin --out $F/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $F/attr/pl29/pl29_hero_attr_f32.bin --param $F/attr/param/s01_param_f32.bin --out $F/attr/a --v2 --gwb $C/$N.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/$N.gwb --rows $C/${N}_rows.npz --meta $C/${N}_meta.json --out $F/hero_pkg_AS06R > $LG/pkg.log 2>&1; echo pkg $?
py -3.10 -B $T6/rows_mesh.py $F $N > $LG/mesh.log 2>&1; echo mesh $?
(cd Tools/GWWaveGen/as04 && py -3.10 -B w4_merge.py $F/mesh/hero_smooth_as06r.json G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json $F/union/union.json > $LG/merge.log 2>&1); echo merge $?
py -3.10 -B -c "
import sys; sys.path.insert(0,'Tools/GWWaveGen/as04'); sys.stdout.reconfigure(encoding='utf-8')
import shape_claws as SCL
SCL.OUT='$F/claws'; SCL.NEW_ROWS='$F/final/cand/${N}_rows.npz'
SCL.main()" > $LG/claws.log 2>&1; echo claws $?
date
