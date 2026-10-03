#!/usr/bin/env bash
# 美術の見本01・見本 B（原画のような舌形）：審査の視点の描画（見本 A の s01a_run_render.sh を写し、描画を S01BRender、出力を
# Build/Polish/sample01/texB/ の下にしたもの）。海・飛沫・線は仕上げ33修正01／35 の採る状態と同じ。爪は描かない（views の爪なし、回り台も爪なし）。
# 主役波の材質は S01B Tongue Keypose（S01BRender の既定。シェーダーの名前から作る）。設計のテクスチャと属性は引数 3 のフォルダー（s01b_design.py の出力）。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample01/texB/ の下）、2 = 段（views,tt など）、3 = 設計のフォルダー（絶対パス）、
#      4 = 時刻（既定 12,10.5）、5 = 値の表（省略可）、6 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
DES=$3
TIMES=${4:-12,10.5}
PF=${5:-}
EXTRA=${6:-}
PFA=""
if [ -n "$PF" ]; then PFA="-pl29ParamFile $PF"; fi
H="-s01bDesign $DES -pl29Attr $DES/s01b_attr_f32.bin -pl29ClawShade 1 $PFA -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/sample01/s01b_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times $TIMES -s01ViewsAsis 0 -s01TtClaws 0"
OUT=$B/$1; ST=$2
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws Build/Polish/33r01/fix01/claws/ds33_claw_layout.json -pl32Look 1 -pl33Look 1"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.Sample01.TexB.EditorTools.S01BRender.Render -Log $TAG -Extra "$V $EXTRA -pl29Out $OUT $S $H $M -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
tail -3 $B/logs/run_$TAG.txt
grep -E "S01B_RENDER_DONE|S01B_DESIGN_LOADED|error CS|Exception" $B/logs/unity_s01b_$TAG.log | head -8
echo "D3D_OOM=$(grep -c 8007000e $B/logs/unity_s01b_$TAG.log)"
date
