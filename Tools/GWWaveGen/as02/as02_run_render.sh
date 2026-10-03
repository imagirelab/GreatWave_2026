#!/usr/bin/env bash
# 美術の見本02（Q30）爪の部：見本 A の面の材質（見本01 の回 2 の値の表 s01a_material_params_r1.txt、属性 v2）を中立の地にして、
# 利用者の 100 本を 3D に戻した爪（as02_claws100.py の並び）を載せて描く。描画は見本01 の AS01SampleRender（-s01bDesign を省くと見本 A）。
# 海・線・Fuji は見本01 と同じ。爪ありの views と回り台は飛沫なし（爪と面を見るため）。時刻は t*（12 s）だけ（爪は t* の 1 コマの静止）。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample02/claws/render/ の下）、2 = 段（views,tt,full）、3 = 爪の並び（Unity/ からの相対）、4 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/claws/render
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2
CL=${3:-Build/Polish/sample02/claws/mesh/ds33_claw_layout.json}
EXTRA=${4:-}
CLAWP=${CLAWP:-G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as02/as02_claw_params.txt}
CP="-pl29ClawShade 1 -pl29ClawParamFile $CLAWP -as01ClawLineColor ${CLAWLINE:-31,60,94} -as01NoLinePrefix ${NOLINE:-U}"
H="-pl29Attr ${A_ATTR:-Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin} -pl29ParamFile ${A_PARAMS:-$T/s01a_material_params_r1.txt} $CP"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as02/as02_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times ${TIMES:-12} -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws ${TTCLAWS:-1} -pl31TtSpray 0"
M="-pl29HeroPkg ${HERO_PKG:-Build/Polish/32/white/hero_pkg} -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look 1"
mkdir -p $B/../logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.ArtSample01.EditorTools.AS01SampleRender.Render -Log $TAG -Extra "$V $EXTRA -pl29Out $OUT $S $H $M -pl29Only $ST" > $B/../logs/run_$TAG.txt 2>&1
tail -2 $B/../logs/run_$TAG.txt
grep -E "AS01S_RENDER_DONE|error CS|Exception" $B/../logs/unity_as02_$TAG.log | head -8
echo "D3D_OOM=$(grep -c 8007000e $B/../logs/unity_as02_$TAG.log)"
date
