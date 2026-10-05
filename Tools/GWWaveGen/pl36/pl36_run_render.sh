#!/usr/bin/env bash
# 仕上げ36：審査の視点の描画（仕上げ35 の pl35_run_render.sh を写し、描画を PL36Render、出力を Build/Polish/36/ の下にしたもの）。
# 爪の並び・飛沫・海・線は仕上げ33修正01／35 の採る状態と同じ。主役波の材質と値の表だけを引数で選ぶ。
# 引数 1 = 出力のフォルダー名（Build/Polish/36/ の下）、2 = 段（views,tt,t28,full,video,ids,fields）、
#      3 = 主役波の材質（Assets/… 既定 PL36_Ukiyoe_Hero.mat）、4 = 主役波の値の表（既定 pl36_material_params.txt）、5 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/36
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
MAT=${3:-Assets/GreatWave/Polish36/Materials/PL36_Ukiyoe_Hero.mat}
PF=${4:-G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl36/pl36_material_params.txt}
EXTRA=${5:-}
H="-pl36HeroMat $MAT -pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile $PF -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl36/pl36_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29VideoViews painting,seat,seat_toward_wave,side_left"
OUT=$B/$1; ST=$2
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws Build/Polish/33r01/fix01/claws/ds33_claw_layout.json -pl32Look 1 -pl33Look 1"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.Polish36.EditorTools.PL36Render.Render -Log $TAG -Extra "$V $EXTRA -pl29Out $OUT $S $H $M -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
grep PL36_UNITY $B/logs/run_$TAG.txt
grep -E "PL36_RENDER_DONE|error CS|Exception" $B/logs/unity_pl36_$TAG.log | head -5
date
