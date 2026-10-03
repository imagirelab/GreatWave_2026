#!/usr/bin/env bash
# 美術の見本02（Q30-2）組み立て：背を一つの山にした候補 K*′ AS02B（hero_pkg の t* の層だけを置き換えた写し、as02_asm_pkg.py）に、
# 利用者の 100 本を 3D に戻した爪（案 A、as02_claws100.py --hero で置き直した並び）を載せ、見本 A の材質（AS02B で作り直した属性）で t* に描く。
# 爪の部の as02_run_render.sh と同じ引数・同じ描画（AS01SampleRender、新しい C# は無い）。違うのは主役波の包み・.gwb・属性・爪の並びと出力の場所だけ。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample02/assemble/render/ の下）、2 = 段（views,tt,full,t28）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=${RB:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/assemble/render}   # 修正の回 1 は RB・LG で置き場を変える
LG=${LG:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/assemble/logs}
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2
CL=${CL:-Build/Polish/sample02/assemble/claws/mesh/ds33_claw_layout.json}
HERO_PKG=${HERO_PKG:-Build/Polish/sample02/assemble/hero_pkg_AS02B}
HERO_GWB=${HERO_GWB:-Build/Polish/sample02/back/final/cand/kstarAS02B_a45.gwb}
A_ATTR=${A_ATTR:-Build/Polish/sample02/assemble/attr/a/s01a_hero_attr_v2_f32.bin}
CLAWP=${CLAWP:-G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as02/as02_claw_params.txt}
CP="-pl29ClawShade 1 -pl29ClawParamFile $CLAWP -as01ClawLineColor 31,60,94 -as01NoLinePrefix U"
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt $CP"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as02/as02_asm_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look 1"
mkdir -p $LG
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.ArtSample01.EditorTools.AS01SampleRender.Render -Log $TAG -Extra "$V -pl29Out $OUT $S $H $M -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS01S_RENDER_DONE|error CS|Exception" $LG/unity_as02a_$TAG.log | head -8
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as02a_$TAG.log)"
date
