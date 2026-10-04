#!/usr/bin/env bash
# 美術の見本05 の材質 AS05（Q33、要求書 T5・T6）：静止のメッシュ（主役波 ＋ wave4）を材質 AS05 Flat Smooth で Unity に t* で描く。
# 見本04 の as04/asm4_render.sh（変えない）の写しで、次だけを替えた。
#   出力 Build/Polish/sample05/mat/render/<引数 1>、ログ Build/Polish/sample05/mat/logs、Unity の起動は as05/mat_unity.ps1（ロックの印 AS05MAT）。
#   既定のシェーダー GreatWave/ArtSample05/AS05FlatSmoothKeypose、既定の値 as05/as05_flat_smooth_params.txt（爪にも同じ表）。
#   既定の keypose の包み・.gwb・12 個の属性・爪の並びは見本04 の最後（fix1、主役波 K*′ AS04F）。形を作り直したら HERO_PKG・HERO_GWB・A_ATTR・CL を替える。
# 視点・時刻・海・波頭の回り台・回り台のカメラは見本04 と同じ。描画の道具は見本03 の AS03AsmRender（変えない）。原画のカメラの投影は使わない。
# 引数 1 = 出力のフォルダー名、2 = 段（views,crest など。views = 7 視点、crest = 波頭の回り台 8 方位）、3 = 静止のメッシュの .json（必須）
# 例：bash Tools/GWWaveGen/as05/mat_render.sh AS05 views,crest G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05/mat/mesh/union_as05.json
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P5=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05
B=$P5/mat/render
LG=$P5/mat/logs
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; SURF=$3; TAG=as05_$1_$(echo $2 | tr ',' '_')
PF=${AS05_PF:-$TA/as05_flat_smooth_params.txt}
SHD="${AS05_SHD:-GreatWave/ArtSample05/AS05FlatSmoothKeypose}"
CL=${CL:-Build/Polish/sample04/fix1/shape/claws/ds33_claw_layout.json}
HERO_PKG=${HERO_PKG:-Build/Polish/sample04/fix1/shape/hero_pkg_AS04F}
HERO_GWB=${HERO_GWB:-Build/Polish/sample04/fix1/shape/final/cand/kstarAS04F_a45.gwb}
A_ATTR=${A_ATTR:-Build/Polish/sample04/fix1/shape/attr/a/s01a_hero_attr_v2_f32.bin}
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as05/mat_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline ${AS05_OL:-1}"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as05mat_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as05mat_$TAG.log)"
date
