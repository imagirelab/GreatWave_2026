set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
F=${1:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/lobes/final}; C=$F/cand; N=kstarAS06L_a45; LG=$F/logs
mkdir -p $F/attr/pl29 $F/attr/param $F/attr/a $LG $F/union
date
py -3.10 -B Tools/GWWaveGen/rubric/rubric_check.py $C/${N}_rows.npz $F/rubric_AS06L.json --gate > $LG/rubric_AS06L.log 2>&1; echo rubric $?
py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --out $F/attr/pl29 --param arc > $LG/attr_pl29.log 2>&1; echo pl29 $?
py -3.10 -B Tools/GWWaveGen/sample01/s01_param.py --gwb $C/$N.gwb --meta $C/${N}_meta.json --attr $F/attr/pl29/pl29_hero_attr_f32.bin --out $F/attr/param --dir isoF > $LG/attr_param.log 2>&1; echo param $?
py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr $F/attr/pl29/pl29_hero_attr_f32.bin --param $F/attr/param/s01_param_f32.bin --out $F/attr/a --v2 --gwb $C/$N.gwb > $LG/attr_a.log 2>&1; echo attr_a $?
py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Unity/Build/Polish/32/white/hero_pkg --gwb $C/$N.gwb --rows $C/${N}_rows.npz --meta $C/${N}_meta.json --out $F/hero_pkg_AS06L > $LG/pkg.log 2>&1; echo pkg $?
date
