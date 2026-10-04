#!/usr/bin/env bash
# 美術の見本05 のやり方 A：主役波 AS05A の行 → 材質の属性（pl29 → s01_param → s01a）→ 包み → 静止のメッシュ（白の区域）→ ③ の波 layer3
# → 層の印 → 爪の置き直し → 合わせた静止のメッシュ（主役波 ＋ wave4 fix1 ＋ layer3）。見本04 の fx1_pipeline.sh と同じ道具・同じ引数で、出力だけ
# Build/Polish/sample05/shapeA へ。使い方：bash Tools/GWWaveGen/as05/shapeA_pipeline.sh
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
F=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05/shapeA
FR=Unity/Build/Polish/sample05/shapeA
C=$FR/hero/cand
N=kstarAS05A_a45
LG=$FR/logs
T5=Tools/GWWaveGen/as05
W4=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json
mkdir -p $FR/attr/pl29 $FR/attr/param $FR/attr/a $LG $FR/mesh
date
py -3.10 -B $T5/shapeA_hero.py > $LG/hero.log 2>&1; echo hero $?
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --out $FR/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --attr $FR/attr/pl29/pl29_hero_attr_f32.bin --out $FR/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $FR/attr/pl29/pl29_hero_attr_f32.bin --param $FR/attr/param/s01_param_f32.bin --out $FR/attr/a --v2 --gwb $C/$N.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/$N.gwb --rows $C/${N}_rows.npz --meta $C/${N}_meta.json --out $FR/hero_pkg_AS05A > $LG/pkg.log 2>&1; echo pkg $?
py -3.10 -B $T5/shapeA_mesh.py > $LG/mesh.log 2>&1; echo mesh $?
py -3.10 -B $T5/shapeA_l3.py > $LG/l3.log 2>&1; echo l3 $?
py -3.10 -B $T5/shapeA_labels.py > $LG/labels.log 2>&1; echo labels $?
py -3.10 -B $T5/shapeA_claws.py > $LG/claws.log 2>&1; echo claws $?
py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py $F/mesh/hero_smooth_as05a.json $W4 $F/mesh/_hero_w4.json > $LG/merge1.log 2>&1; echo merge1 $?
py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py $F/mesh/_hero_w4.json $F/l3/layer3.json $F/mesh/union_AS05A.json > $LG/merge2.log 2>&1; echo merge2 $?
date
