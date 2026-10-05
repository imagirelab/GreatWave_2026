#!/usr/bin/env bash
# 美術の見本06 の段の行（B-ROWS）：as05/fx5_render.sh（変えない）の写し。形 R6（段の行の主役波 AS06R ＋ wave4 fix1、材質 AS05 のまま）を
# Unity で t* に描く。出力は Build/Polish/sample06/rows/render/<引数 2>、ログは Build/Polish/sample06/rows/logs、Unity の起動は as06/rows_unity.ps1。
# Q34「船可以挪」：一艘目の船（boat_left）は原画のカメラを中心とする相似で手前へ動かす（AS05ABoatRender を変えずに使う。倍率は BOAT_S、既定 0.62）。
# 原画視点の船の画は画素まで同じで、ほかの視点では船が小さくなる（船と波の差し込み合いは造型の後で調整する。名前の付いた美術の誘導）。
# 引数 1 = 形（R6）、2 = 出力のフォルダー名、3 = 段（views,crest,tt,full,t28 など）、4 = 静止のメッシュの .json、5 = パイプラインの根（Unity/ からの相対）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P6=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/rows
B=$P6/render
LG=$P6/logs
T5=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
VAR=$1; OUT=$B/$2; ST=$3; TTC=${TT_CLAWS:-1}; TAG=r6_$2_$(echo $3 | tr ',' '_')_tt$TTC
PF=$T5/as05_flat_smooth_params.txt
SHD="GreatWave/ArtSample05/AS05FlatSmoothKeypose"
case $VAR in
  R6)
    SURF=$4; FR=$5
    CL=$FR/claws/ds33_claw_layout.json
    HERO_PKG=$FR/hero_pkg_AS06R
    HERO_GWB=$FR/final/cand/kstarAS06R_a45.gwb
    A_ATTR=$FR/attr/a/s01a_hero_attr_v2_f32.bin
    METHOD=GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render
    BO="-as05BoatScale ${BOAT_S:-0.62} -as05BoatLog $OUT/as06r_boat_$TTC.json" ;;
  *) echo "形は R6"; exit 2 ;;
esac
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as06/rows_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws $TTC -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline 1"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG $OUT
date
$U -Method $METHOD -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G $BO -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS05A_BOAT|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_r6_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_r6_$TAG.log)"
date
