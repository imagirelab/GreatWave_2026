#!/usr/bin/env bash
# 仕上げ35：審査の視点の描画（仕上げ33修正01 の r01_run_render.sh を写し、出力を Build/Polish/35/ の下、Unity の 1 回の実行を pl35_run_unity.ps1 にしたもの。
# 描き方・引数（主役波・海・飛沫・爪の並び・色と線の表）は仕上げ33修正01 の採る状態と同じ。この群は見え方を変えないので、後の描画は前と同じ入力で描く）。
# 引数 1 = 出力のフォルダー名（Build/Polish/35/ の下）、2 = 段（views,tt,t28,full,video）、3 = 爪の並び（Unity/ からの相対）、4 = pl33Look（既定 1）、5 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/35
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
H="-pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl35/pl35_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29VideoViews painting,seat,seat_toward_wave,side_left"
OUT=$B/$1; ST=$2; CL=${3:-Build/Polish/33r01/fix01/claws/ds33_claw_layout.json}; LK=${4:-1}; EXTRA=${5:-}
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look $LK"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.Polish33.EditorTools.PL33Render.Render -Log $TAG -Extra "$EXTRA -pl29Out $OUT $S $H $M $V -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
grep PL35_UNITY $B/logs/run_$TAG.txt
grep -E "PL33_RENDER_DONE|PL29_RENDER_DONE|error CS|Exception" $B/logs/unity_pl35_$TAG.log | head -5
date
