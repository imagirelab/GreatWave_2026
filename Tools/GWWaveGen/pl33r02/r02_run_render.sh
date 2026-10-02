#!/usr/bin/env bash
# 仕上げ33修正02 修正の回 2：描画の手順（pl33r01/r01_run_render.sh を写し、出力を Build/Polish/33r02/ の下、Unity の呼び出しを r02_run_unity.ps1 にしたもの）。
# 引数 1 = 出力のフォルダー名（33r02/ の下）、2 = 段（views,tt,t28,full,video）、3 = 爪の並び（Unity/ からの相対）、4 = pl33Look（既定 1）、5 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/33r02
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
H="-pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl33r02/r02_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29VideoViews painting,seat,seat_toward_wave,side_left"
OUT=$B/$1; ST=$2; CL=${3:-Build/Polish/33r02/claws/ds33_claw_layout.json}; LK=${4:-1}; EXTRA=${5:-}
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look $LK"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.Polish33.EditorTools.PL33Render.Render -Log $TAG -Extra "$EXTRA -pl29Out $OUT $S $H $M $V -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
grep R02_UNITY $B/logs/run_$TAG.txt
grep -E "PL33_RENDER_DONE|PL29_RENDER_DONE|error CS|Exception" $B/logs/unity_r02_$TAG.log | head -5
date
