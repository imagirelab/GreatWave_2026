#!/usr/bin/env bash
# 美術の見本03 の調べ S3（Q31）：見本02（K*′ AS02C ＋ fix01 の爪 83 本 ＋ 見本 A の材質 ＋ 海 PL30）を t* で描く。
# as02/as02_asm_render.sh（修正の回 1 の引数）と同じ入力・同じ材質で、描画の道具だけ AS03StudyRender（AS01SampleRender の写し＋波頭の回り台）にした。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample03/study/render/ の下）、2 = 段（views,crest,ids など）、3 以降 = 足す引数（任意）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study/logs
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
S2=Build/Polish/sample02/fix01
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; TAG=$1_$(echo $2 | tr ',' '_'); shift 2; XTRA="$*"
CL=$S2/assemble/claws/mesh/ds33_claw_layout.json
HERO_PKG=$S2/assemble/hero_pkg_AS02C
HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
A_ATTR=$S2/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin
CLAWP=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as02/as02_claw_params.txt
CP="-pl29ClawShade 1 -pl29ClawParamFile $CLAWP -as01ClawLineColor 31,60,94 -as01NoLinePrefix U"
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt $CP"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as03/as03_s3_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL -pl32Look 1 -pl33Look 1"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03StudyRender.Render -Log $TAG -Extra "$V -pl29Out $OUT $S $H $M -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS01S_RENDER_DONE|error CS|Exception" $LG/unity_as03s3_$TAG.log | head -8
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as03s3_$TAG.log)"
date
