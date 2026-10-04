#!/usr/bin/env bash
# 美術の見本05 のやり方 A の描画：主役波 AS05A ＋ wave4（fix1）＋ ③ の波 layer3（合わせた 1 つの静止のメッシュ）＋ 材質 AS04F Flat Smooth（白い点を描かない値の表）
# ＋ 爪 35 本（面の内 25・近い海 10。波頭の爪は出さない）を Unity で t* に描く。見本04 の asm4_render.sh（変えない）の写しで、次だけを替えた。
#   描画の入口 = GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render（一艘目の船を原画のカメラを中心とする相似で動かしてから AS03AsmRender.Render を呼ぶ）。
#   -as05BoatScale（環境変数 BOAT_S、既定 1）・-as05BoatLog。出力 Build/Polish/sample05/shapeA/render/<引数 1>、ログ Build/Polish/sample05/shapeA/logs。
# 引数 1 = 出力のフォルダー名、2 = 段（views,crest,tt,full,t28 など）、3 = 静止のメッシュの .json（省くと mesh/union_AS05A.json）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P5=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05/shapeA
B=$P5/render
LG=$P5/logs
T5=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; SURF=${3:-$P5/mesh/union_AS05A.json}; TAG=as05a_$1_$(echo $2 | tr ',' '_')
PF=${AS05A_PF:-$T5/shapeA_flat_smooth_params.txt}
SHD="${AS05A_SHD:-GreatWave/ArtSample04/AS04FFlatSmoothKeypose}"
CL=${CL:-Build/Polish/sample05/shapeA/claws/ds33_claw_layout.json}
HERO_PKG=${HERO_PKG:-Build/Polish/sample05/shapeA/hero_pkg_AS05A}
HERO_GWB=${HERO_GWB:-Build/Polish/sample05/shapeA/hero/cand/kstarAS05A_a45.gwb}
A_ATTR=${A_ATTR:-Build/Polish/sample05/shapeA/attr/a/s01a_hero_attr_v2_f32.bin}
BOAT_S=${BOAT_S:-1}
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as05/shapeA_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline ${AS05A_OL:-1}"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
BO="-as05BoatScale $BOAT_S -as05BoatLog $OUT/as05a_boat.json"
mkdir -p $LG $OUT
date
$U -Method GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G $BO -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS05A_BOAT|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as05a_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as05a_$TAG.log)"
date
