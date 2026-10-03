#!/usr/bin/env bash
# 美術の見本01（Q29）組み立て：爪の部の爪（Build/Polish/sample01/claws/mesh）と面の模様の部 A・B を 1 つの描画で組み合わせる。
# 描画は AS01SampleRender（見本 B の S01BRender の写し。-s01bDesign を省くと見本 A）。海・線・Fuji は仕上げ33修正01／35 の採る状態のまま。
# 爪ありの views は飛沫なし（_claws。爪の部・面の模様の部と同じく、爪と面を見るため）。回り台も爪あり・飛沫なし。
# 時刻は t*（12 s）だけ：爪の層は t* の 1 コマの静止の見本で、ほかの時刻では主役波と合わない（t 10.5 s は各部の爪なしの描画を使う）。
# 引数 1 = A か B、2 = 出力のフォルダー名（Build/Polish/sample01/assemble/ の下）、3 = 段（views,tt,full）、
#      4 = 爪の並び（Unity/ からの相対。既定 Build/Polish/sample01/claws/mesh/ds33_claw_layout.json）、5 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/assemble
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
SAMPLE=$1; OUT=$B/$2; ST=$3
CL=${4:-Build/Polish/sample01/claws/mesh/ds33_claw_layout.json}
EXTRA=${5:-}
# 環境変数（美術の見本01 の改善の回 1、2026-10-03）：CLAWP＝爪の陰の値の表（既定は前の回の pl32_claw_params.txt）、CLAWLINE＝爪の縁の線の色 r,g,b、
# A_PARAMS・A_ATTR＝見本 A の値の表と属性、B_DES・B_PARAMS＝見本 B の設計のフォルダーと値の表（既定はどれも前の回の a7・c9）
CLAWP=${CLAWP:-G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt}
CP="-pl29ClawShade 1 -pl29ClawParamFile $CLAWP"
if [ -n "${CLAWLINE:-}" ]; then CP="$CP -as01ClawLineColor $CLAWLINE"; fi
if [ -n "${NOLINE:-}" ]; then CP="$CP -as01NoLinePrefix $NOLINE"; fi
if [ "$SAMPLE" = "A" ]; then
  # 見本 A（a7）：texA の README のとおり（属性 v2・値の表 s01a_material_params.txt）
  H="-pl29Attr ${A_ATTR:-Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin} -pl29ParamFile ${A_PARAMS:-$T/s01a_material_params.txt} $CP"
elif [ "$SAMPLE" = "B" ]; then
  # 見本 B（c9）：texB の README のとおり（設計のフォルダー work/design_final・値の表 s01b_material_params.txt）
  DES=${B_DES:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/design_final}
  H="-s01bDesign $DES -pl29Attr $DES/s01b_attr_f32.bin -pl29ParamFile ${B_PARAMS:-$T/s01b_material_params.txt} $CP"
else
  echo "引数 1 は A か B"; exit 2
fi
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as01/as01s_run_unity.ps1"
# TIMES（既定 12）・TTCLAWS（既定 1）：改善の回 1 で t 10.5 s の爪なしを同じ道具で描くため
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times ${TIMES:-12} -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws ${TTCLAWS:-1} -pl31TtSpray 0"
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look 1"
mkdir -p $B/logs
TAG=$2_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.ArtSample01.EditorTools.AS01SampleRender.Render -Log $TAG -Extra "$V $EXTRA -pl29Out $OUT $S $H $M -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
tail -2 $B/logs/run_$TAG.txt
grep -E "AS01S_RENDER_DONE|AS01S_DESIGN_LOADED|error CS|Exception" $B/logs/unity_as01s_$TAG.log | head -8
echo "D3D_OOM=$(grep -c 8007000e $B/logs/unity_as01s_$TAG.log)"
date
