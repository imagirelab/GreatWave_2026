#!/usr/bin/env bash
# 美術の見本04 の形づくり：新しい主役波 K*′ AS04 の t* を AS04 Flat Smooth（調べ M の材質、変えない）で描く。調べ M の mat_render.sh の写しで、次を替えた。
#   主役波 = AS04 の滑らかな静止のメッシュ（as04/shape_mesh.py、Build/Polish/sample04/shape/mesh/hero_smooth_as04）、
#   keypose の包み・.gwb・12 個の属性 = AS04 のもの（shape/hero_pkg_AS04・final/cand/kstarAS04_a45.gwb・attr/a）、
#   爪 = 置き直した 35 本（shape/claws）。冠・泡の皮・滴・頂の瘤は置かない。描画の道具は見本03 の AS03AsmRender（変えない）。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample04/shape/render/ の下）、2 = 段（views,tt,full,t28 など）、3 = 値の表（省くと as04_flat_smooth_params.txt）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
SH=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/shape
B=$SH/render
LG=$SH/logs
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; PF=${3:-$TA/as04_flat_smooth_params.txt}; TAG=shape_$1_$(echo $2 | tr ',' '_'); shift 2; [ $# -gt 0 ] && shift; XTRA="$*"
SHD="GreatWave/ArtSample04/AS04FlatSmoothKeypose"
# 比べの「前」（AS02C）を同じ材質で描く時は、環境変数 CL・HERO_PKG・HERO_GWB・A_ATTR・SURF で入力を替える
CL=${CL:-Build/Polish/sample04/shape/claws/ds33_claw_layout.json}
HERO_PKG=${HERO_PKG:-Build/Polish/sample04/shape/hero_pkg_AS04}
HERO_GWB=${HERO_GWB:-Build/Polish/sample04/shape/final/cand/kstarAS04_a45.gwb}
A_ATTR=${A_ATTR:-Build/Polish/sample04/shape/attr/a/s01a_hero_attr_v2_f32.bin}
SURF=${SURF:-$SH/mesh/hero_smooth_as04.json}
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
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as04mat_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as04mat_$TAG.log)"
date
