#!/usr/bin/env bash
# 美術の見本04 の組み立て（Q32）：主役波 K*′ AS04 ＋ 左端の別の青い波 wave4 ＋ AS04 Flat Smooth ＋ 爪 35 本（面の内 25・近い海 10）を
# Unity で t* に描く。形づくりの shape_render.sh（変えない）の写しで、次だけを替えた。
#   静止のメッシュ = 主役波 AS04 と wave4 をつないだ 1 つのメッシュ（wave4 の作り w4_merge.py の出力 wave4/mesh_as04/union.json。
#     描画の道具 AS03AsmRender の -as03Surf は 1 つしか読まないため）。
#   出力 Build/Polish/sample04/assemble/render/<引数 1>、ログ Build/Polish/sample04/assemble/logs。
# keypose の包み・.gwb・12 個の属性・爪の並びは形づくりの AS04（shape/）のまま（設計38 の外殻の線が AS04 の形に合う。AS04_OL=1）。
# 視点・時刻・海・波頭の回り台・回り台のカメラは見本03 と同じ。描画の道具は見本03 の AS03AsmRender（変えない）。冠・泡の皮・滴・瘤は置かない。
# 引数 1 = 出力のフォルダー名、2 = 段（views,crest,tt,full,t28 など）、3 = 静止のメッシュの .json（省くと wave4/mesh_as04/union.json）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P4=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04
B=$P4/assemble/render
LG=$P4/assemble/logs
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; SURF=${3:-$P4/wave4/mesh_as04/union.json}; TAG=asm4_$1_$(echo $2 | tr ',' '_')
PF=${AS04_PF:-$TA/as04_flat_smooth_params.txt}
SHD="${AS04_SHD:-GreatWave/ArtSample04/AS04FlatSmoothKeypose}"
CL=${CL:-Build/Polish/sample04/shape/claws/ds33_claw_layout.json}
HERO_PKG=${HERO_PKG:-Build/Polish/sample04/shape/hero_pkg_AS04}
HERO_GWB=${HERO_GWB:-Build/Polish/sample04/shape/final/cand/kstarAS04_a45.gwb}
A_ATTR=${A_ATTR:-Build/Polish/sample04/shape/attr/a/s01a_hero_attr_v2_f32.bin}
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as04/mat_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline ${AS04_OL:-1}"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as04mat_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as04mat_$TAG.log)"
date
