#!/usr/bin/env bash
# 美術の見本04 の作り W4（Q32、S9）：別の小さな青い波（④）を、主役波の行に合わせて作り直し、つないで描き、測る（一続きの手順）。
# 引数 1 = 名前（出力 Build/Polish/sample04/wave4/{mesh_<名前>,render/<名前>,check/<名前>}）、
#      2 = 主役波の行の npz（地面と頂の位置）、3 = 主役波の AS04 の静止のメッシュ .json（つなぐ相手・交わりの検査）、
#      4 = 別の波なしの描画のフォルダー（比べの図。省くと final_nowave4）。図の見出しの主役波の説明は W4_HERO_JA
# 主役波を AS02C 以外の keypose で描く時は W4_HERO_PKG・W4_HERO_GWB・W4_ATTR・W4_CLAWS と AS04_OL=1 を付けて呼ぶ（w4_render.sh を見る）。
# 例（形を作る側の AS04）：
#   W4_HERO_PKG=Build/Polish/sample04/shape/hero_pkg_AS04 W4_HERO_GWB=Build/Polish/sample04/shape/final/cand/kstarAS04_a45.gwb \
#   W4_ATTR=Build/Polish/sample04/shape/attr/a/s01a_hero_attr_v2_f32.bin W4_CLAWS=Build/Polish/sample04/shape/claws/ds33_claw_layout.json AS04_OL=1 \
#   bash Tools/GWWaveGen/as04/w4_run_all.sh as04 Unity/Build/Polish/sample04/shape/final/cand/kstarAS04_a45_rows.npz \
#        Unity/Build/Polish/sample04/shape/mesh/hero_smooth_as04.json G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/shape/render/A2
set -eu
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
N=$1; ROWS=$2; HMESH=$3; NOW=${4:-final_nowave4}
W4=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4
M=$W4/mesh_$N
date
py -3.10 -B Tools/GWWaveGen/as04/w4_paint.py > /dev/null
py -3.10 -B Tools/GWWaveGen/as04/w4_build.py --hero-rows $ROWS --out $M | grep "iter': 3"
py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py $HMESH $M/wave4.json $M/union.json
bash Tools/GWWaveGen/as04/w4_render.sh $N views,full,t28 $M/union.json
RB=$W4/render LG=$W4/logs BEFORE=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/render/final bash Tools/GWWaveGen/as02/as02_asm_eval.sh $N | tail -2
py -3.10 -B Tools/GWWaveGen/as04/w4_check.py --hero-rows $ROWS --hero-mesh $HMESH --wave4 $M/wave4.json --grid $M/wave4_grid.npz --tag $N | tail -2
py -3.10 -B Tools/GWWaveGen/as04/w4_sheets.py $N $NOW _$N "${W4_HERO_JA:-計画 (b) の仮の主役波（形を作る側の本物ではない。外殻の線なし）}"
date
