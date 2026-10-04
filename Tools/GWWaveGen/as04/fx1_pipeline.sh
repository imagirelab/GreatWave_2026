#!/usr/bin/env bash
# 美術の見本04 の直しの回 1（fix1）：直した主役波 AS04F の行 → 測り → 材質の属性 → 包み → 静止のメッシュ（白い刃の直し）→ 爪の置き直し。
# shape_pipeline.sh（変えない）と同じ道具・同じ引数で、出力だけ Build/Polish/sample04/fix1/shape へ。
# 使い方：bash Tools/GWWaveGen/as04/fx1_pipeline.sh
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
F=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/fix1/shape
FR=Unity/Build/Polish/sample04/fix1/shape
C=$FR/final/cand
N=kstarAS04F_a45
LG=$FR/logs
TA=Tools/GWWaveGen/as04
mkdir -p $FR/attr/pl29 $FR/attr/param $FR/attr/a $LG
date
py -3.10 -B $TA/fx1_build.py $F/final/cand/$N $F/final/design_AS04F.json > $LG/build.log 2>&1; echo build $?
py -3.10 -B $TA/shape_eval.py $F/final/eval_AS04F.json $F/final/cand/${N}_rows.npz > $LG/eval_AS04F.log 2>&1; echo eval $?
py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py $C/${N}_rows.npz $FR/final/rubric_AS04F.json --gate > $LG/rubric_AS04F.log 2>&1; echo rubric $?
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --out $FR/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --attr $FR/attr/pl29/pl29_hero_attr_f32.bin --out $FR/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $FR/attr/pl29/pl29_hero_attr_f32.bin --param $FR/attr/param/s01_param_f32.bin --out $FR/attr/a --v2 --gwb $C/$N.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/$N.gwb --rows $C/${N}_rows.npz --meta $C/${N}_meta.json --out $FR/hero_pkg_AS04F > $LG/pkg.log 2>&1; echo pkg $?
py -3.10 -B $TA/fx1_mesh.py $FR $N > $LG/mesh.log 2>&1; echo mesh $?
py -3.10 -B -c "
import sys; sys.path.insert(0,'$TA'); sys.stdout.reconfigure(encoding='utf-8')
import shape_claws as SCL
SCL.OUT='$F/claws'; SCL.NEW_ROWS='$F/final/cand/${N}_rows.npz'
SCL.main()" > $LG/claws.log 2>&1; echo claws $?
date
