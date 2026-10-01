#!/bin/sh
# 仕上げ28 の回復（rec）：K*′ P28R2rec と動き G_p28rec の焼き直しと Unity の描画と原画視点の評価器を、順に 1 つずつ回す（重い処理を同時に走らせない）。
# 前提：Unity/Build/Polish/28/kstar_p28rec（凍結）、Unity/Build/Polish/28/G_p28rec/art_on と timewarp_G_p28rec.json（ds28r01f_pipeline の時間曲線）。
# 使い方（リポジトリの根で）：sh Tools/GWWaveGen/pl28/run_pl28rec_unity.sh
set -e
R="G:/Unity/GreatWave_2026_Fresh"
cd "$R"
PS="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl28/run_pl28_unity.ps1"
B=Build/Polish/28
KS=a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94
if [ -z "$SKIP_BAKE_INPUT" ]; then   # SKIP_BAKE_INPUT=1 で、作り済みの焼き込みの入力を使う（Unity の焼きだけをやり直す時）
echo "== bake input $(date)"
py -3.10 -B Tools/GWWaveGen/pl28/pl28u_bake_input.py --build Unity/$B/unity/bake_rec --kstar-dir Unity/$B/kstar_p28rec --gwb kstarP28R2rec_a45.gwb --meta kstarP28R2rec_a45_meta.json --sha $KS
fi
echo "== unity bake $(date)"
$PS -Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log u_bake_rec -Extra "-ds29r01BakeRoot $B/unity/bake_rec"
echo "== unity DS29Render $(date)"
$PS -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log u_ds29_G_p28rec -Package $B/G_p28rec/art_on -WarpFile $B/G_p28rec/timewarp_G_p28rec.json -OutDir $B/unity/ds29_G_p28rec -Stills "m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0" -Views "painting,seat,seat_toward_wave,side_left" -Skip "timing,video" -Extra "-ds29Name G_p28rec -ds29MeshFromPackage 0 -ds29KStarGwb $B/unity/bake_rec/kstar/kstar_a45.gwb -ds29Sdf $B/unity/bake_rec/bake/af28r01_uvsdf_a45.bin -ds29Warp $B/unity/bake_rec/bake/af28r01_uvwarp_a45.json"
echo "== gpu check $(date)"
py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/$B/unity/ds29_G_p28rec --package Unity/$B/G_p28rec/art_on --range=-12,0 --out Unity/$B/unity/check_gpu_G_p28rec.json
echo "== unity PL28Render rec $(date)"
$PS -Method GreatWave.Polish28.EditorTools.PL28Render.Render -Log u_scene_rec -Extra "-pl28State p28 -pl28Out $R/Unity/$B/unity/scene_rec -pl28HeroPkg $B/G_p28rec/art_on -pl28HeroGwb $B/unity/bake_rec/kstar/kstar_a45.gwb -pl28HeroSdf $B/unity/bake_rec/bake/af28r01_uvsdf_a45.bin -pl28HeroUvWarp $B/unity/bake_rec/bake/af28r01_uvwarp_a45.json -pl28Timewarp $B/G_p28rec/timewarp_G_p28rec.json"
echo "== regress $(date)"
py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/$B/unity/scene_rec --kstar rec
echo "== evaluator23 $(date)"
for pair in off_noline:ids_noline off_noline_noclaws:ids_noline_noclaws off_line:ids_line off_line_noclaws:ids_line_noclaws; do
  n=${pair%%:*}; ids=${pair##*:}
  py -3.10 Tools/PaintingTruth/evaluate.py --render Unity/$B/unity/scene_rec/full/painting_t120_off.png --ids Unity/$B/unity/scene_rec/full/$ids.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir Unity/$B/unity/eval23/rec_$n --name rec_$n
done
echo "== done $(date)"
