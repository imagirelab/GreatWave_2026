#!/usr/bin/env bash
# 美術の見本01・見本 B（原画のような舌形）の採る版（final）を作り直す：設計（numpy、約 9 秒）→ Unity の描画（views・tt・full、t 12・10.5 s、約 25 秒）
# → 評価器 23 の 4 組 → 前後の並べ図。出力は Build/Polish/sample01/texB/ の下（Git 対象外）。重い numpy の処理は 1 つずつ。
# 前もって要るもの（Git 対象外の work/。無ければ先に作る）：
#   py -3.10 -B Tools/GWWaveGen/sample01/s01b_raster_cache.py painting   → work/raster_painting.npz（原画視点の z バッファ）
#   py -3.10 -B Tools/GWWaveGen/sample01/s01b_target.py                  → work/target_face.png・target_skel.npz（原画の藍中の線の並び。色は写さない）
#   部 A の面の座標 Build/Polish/sample01/param/s01_param_f32.bin（Tools/GWWaveGen/sample01/s01_param.py）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
T=Tools/GWWaveGen/sample01
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB
date
py -3.10 -B $T/s01b_design2.py --out $B/work/design_final --max-rot 25 --blur 2.5 --cz-width 1.8,2.8 --tip-lo -0.35 --tip-hi 0.25 --miz-off 0.15 \
  --lam0 2.4 --lam-clip 1.9,3.6 --hw 0.14,0.12,0.25,0.30,0.14 --top-wedge 0.5,5 --hw-back 0.11,0.12 --dot-cell 0.45 --dots 0.6,0.025,0.12,0.05,0.06,0.08 \
  --lam-grow 30 --seed-jit 0.35 --early 0.3,6,18 --head-var 0.3 --head 1.0,1.4,1.7 --band-rel 9 > $B/logs/design_final.txt 2>&1; echo design $?
bash $T/s01b_run_render.sh final views,tt,full $B/work/design_final 12,10.5 G:/Unity/GreatWave_2026_Fresh/$T/s01b_material_params.txt
mkdir -p $B/final/eval23 $B/eval_before
for c in line line_noclaws noline noline_noclaws; do
  py -3.10 -B Tools/PaintingTruth/evaluate.py --render $B/final/full/painting_t120_off.png --ids $B/final/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $B/final/eval23/off_$c --name off_$c > $B/final/eval23/off_$c.log 2>&1; echo eval $c $?
  # 前（採用の PL29、見本 A の部が描いた texA/before）も同じ評価器で数える
  py -3.10 -B Tools/PaintingTruth/evaluate.py --render Unity/Build/Polish/sample01/texA/before/full/painting_t120_off.png --ids Unity/Build/Polish/sample01/texA/before/full/ids_$c.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir $B/eval_before/off_$c --name off_$c > $B/eval_before/off_$c.log 2>&1; echo eval_before $c $?
done
py -3.10 -B $T/s01b_eval_summary.py
py -3.10 -B $T/s01b_figs.py --after final --out $B/look/final --sample
date
