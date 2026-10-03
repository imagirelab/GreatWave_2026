#!/usr/bin/env bash
# 美術の見本01（Q29）爪の部：Unity の描画の手順（仕上げ33修正01 の r01_run_render.sh を写し、描画の道具を AS01ClawsRender、時刻を t* だけ、
# 出力を Build/Polish/sample01/claws/ の下にしたもの。主役波・海・材質の引数は仕上げ33修正01 の採用の状態と同じ）。
# 引数 1 = 出力のフォルダー名（claws/ の下）、2 = 段（views,tt）、3 = 爪の並び（Unity/ からの相対）、4 = 追加の引数。
# 環境変数 HERO_PKG で主役波のパッケージを替える（既定 Build/Polish/32/white/hero_pkg。爪の帯の地を藍にする提案は Build/Polish/sample01/claws/hero_backing）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/claws
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
H="-pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as01/claws_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -pl31TtSpray 0 -as01ViewSpray 0"
OUT=$B/$1; ST=$2; CL=${3:-Build/Polish/sample01/claws/mesh/ds33_claw_layout.json}; EXTRA=${4:-}
HP=${HERO_PKG:-Build/Polish/32/white/hero_pkg}
M="-pl29HeroPkg $HP -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look 1"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.ArtSample01.EditorTools.AS01ClawsRender.Render -Log $TAG -Extra "$EXTRA -pl29Out $OUT $S $H $M $V -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
grep AS01_UNITY $B/logs/run_$TAG.txt
grep -E "AS01_RENDER_DONE|error CS|Exception" $B/logs/unity_as01_$TAG.log | head -5
date
