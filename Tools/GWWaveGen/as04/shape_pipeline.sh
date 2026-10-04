#!/usr/bin/env bash
# 美術の見本04 の形づくり：決めた形（final/cand/kstarAS04_a45）から、測り・材質の属性・包み・静止のメッシュ・爪・粘土の描画までを順に作る。
# 使い方：bash Tools/GWWaveGen/as04/shape_pipeline.sh
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
SHA=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/shape
SH=Unity/Build/Polish/sample04/shape
C=$SH/final/cand
LG=$SH/logs
TA=Tools/GWWaveGen/as04
mkdir -p $SH/attr/pl29 $SH/attr/param $SH/attr/a $LG $SHA/clay/views $SHA/clay/tt_AS02C $SHA/clay/tt_AS04
date
py -3.10 -B $TA/shape_eval.py $SHA/final/eval_AS04.json $SHA/final/cand/kstarAS04_a45_rows.npz > $LG/eval_AS04.log 2>&1; echo eval $?
py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py $C/kstarAS04_a45_rows.npz $SH/final/rubric_AS04.json --gate > $LG/rubric_AS04.log 2>&1; echo rubric $?
py -3.10 -B $TA/shape_rubric_diff.py $SH/base/rubric_AS02C.json $SH/final/rubric_AS04.json $SH/final/rubric_diff.json > $LG/rubric_diff.log 2>&1; echo rubric_diff $?
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/kstarAS04_a45.gwb --meta $C/kstarAS04_a45_meta.json --out $SH/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/kstarAS04_a45.gwb --meta $C/kstarAS04_a45_meta.json --attr $SH/attr/pl29/pl29_hero_attr_f32.bin --out $SH/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $SH/attr/pl29/pl29_hero_attr_f32.bin --param $SH/attr/param/s01_param_f32.bin --out $SH/attr/a --v2 --gwb $C/kstarAS04_a45.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/kstarAS04_a45.gwb --rows $C/kstarAS04_a45_rows.npz --meta $C/kstarAS04_a45_meta.json --out $SH/hero_pkg_AS04 > $LG/pkg.log 2>&1; echo pkg $?
py -3.10 -B $TA/shape_mesh.py > $LG/mesh.log 2>&1; echo mesh $?
py -3.10 -B $TA/shape_claws.py > $LG/claws.log 2>&1; echo claws $?
BL="G:/SteamLibrary/steamapps/common/Blender/blender.exe"
"$BL" --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views $SHA/clay/views AS02C=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb,AS04=$SHA/final/cand/kstarAS04_a45.gwb views=all > $LG/clay_views.log 2>&1; echo clay_views $?
"$BL" --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- turntable $SHA/final/cand/kstarAS04_a45.gwb none $SHA/clay/tt_AS04 12 72 16 1280 720 > $LG/clay_tt_AS04.log 2>&1; echo clay_tt $?
date
