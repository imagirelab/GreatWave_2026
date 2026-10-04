#!/usr/bin/env bash
# 美術の見本04 の作り W4（Q32、S9）：別の波（④）を AS04 Flat Smooth で描く。調べ M の mat_render.sh（変えない）の写しで、次を替えた。
#   主役波の静止のメッシュ = 引数 3 の .json（既定：仮の主役波 standin と別の波をつないだ Build/Polish/sample04/wave4/mesh/union_standin.json）、
#   主役波の外殻の線（設計38）は既定で出さない（AS04_OL=0。線は keypose の AS02C の形を描くので、下げた仮の主役波とずれる）。
#   出力 Build/Polish/sample04/wave4/render/<引数 1>、ログ Build/Polish/sample04/wave4/logs。描画の道具は見本03 の AS03AsmRender（変えない）。
# 引数 1 = 出力のフォルダー名、2 = 段（views など）、3 = 静止のメッシュの .json（省くと既定）、4 以降 = 足す引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/logs
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
S2=Build/Polish/sample02/fix01
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; MESHJ=${3:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh/union_standin.json}; TAG=w4_$1_$(echo $2 | tr ',' '_'); shift 2; [ $# -gt 0 ] && shift; XTRA="$*"
PF=${AS04_PF:-$TA/as04_flat_smooth_params.txt}
SH="${AS04_SHD:-GreatWave/ArtSample04/AS04FlatSmoothKeypose}"
# 主役波の keypose の包み・.gwb・12 個の属性・爪は、既定で AS02C（見本02・03）。形を作る側の AS04 で描く時は W4_HERO_PKG・W4_HERO_GWB・W4_ATTR・W4_CLAWS で替える
#（その時は AS04_OL=1 で設計38 の外殻の線が AS04 の形に合う）
CL=${W4_CLAWS:-Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json}
HERO_PKG=${W4_HERO_PKG:-$S2/assemble/hero_pkg_AS02C}
HERO_GWB=${W4_HERO_GWB:-$S2/back/final/cand/kstarAS02C_a45.gwb}
A_ATTR=${W4_ATTR:-$S2/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin}
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as04/mat_unity.ps1 -LogDir $LG"
V="-pl29Views ${W4_VIEWS:-painting,seat,seat_toward_wave,side_left,side_right,back65,top} -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $MESHJ -as03Shader ${SH} -as03Params $PF -as03HeroOutline ${AS04_OL:-0}"
G="-as03ClawGlaze ${SH} -as03ClawParams $PF"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as04mat_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as04mat_$TAG.log)"
date
