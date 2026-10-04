#!/usr/bin/env bash
# 美術の見本03 の作り B2（Q31）：主役波の彫りの面（surf_relief.py の静止のメッシュ）を AS03 FLAT・SCULPT の材質で、t* の 7 視点と波頭の回り台 8 方位で描く。
# 入力・海・爪の並びは調べ S3 の as03_s3_render.sh（見本02 修正の回 1 と同じ）。描画の道具は AS03SurfRender（AS03StudyRender の写し＋静止のメッシュ）。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample03/surface/render/ の下）、2 = 段（views,crest,ids など）、3 = flat|sculpt、4 = メッシュの名前（surface/mesh/<名前>.json）、
# 5 以降 = 足す引数（任意。-s01ViewsAsis 1 -as03ClawGlaze … など）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/logs
MESH=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/mesh
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as03
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
S2=Build/Polish/sample02/fix01
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; MODE=$3; MN=$4; TAG=$1_$(echo $2 | tr ',' '_'); shift 4; XTRA="$*"
# FLAT は主役波の外殻の線（設計38）を描く（回 11：白 (248,243,223) と空 (249,232,196) の差が小さく、線がないと頂の輪郭が空に溶けた）。SCULPT は線なし
if [ "$MODE" = "flat" ]; then SH="GreatWave/ArtSample03/AS03_Flat"; PF=$TA/surf_flat_params.txt; OL=1; else SH="GreatWave/ArtSample03/AS03_Sculpt"; PF=$TA/surf_sculpt_params.txt; OL=0; fi
CL=$S2/assemble/claws/mesh/ds33_claw_layout.json
HERO_PKG=$S2/assemble/hero_pkg_AS02C
HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
A_ATTR=$S2/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as03/surf_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 0 -as01ViewSpray 0 -s01TtClaws 0 -pl31TtSpray 0"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1 -pl30TtSea 0"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
# シェーダーの名前の空白はシェル・PowerShell の引数で割れるので、C# の側で "_" を " " に戻す（AS03_Flat → AS03 Flat Keypose）
X="-as03Surf $MESH/$MN.json -as03Shader ${SH}_Keypose -as03Params $PF -as03HeroOutline $OL"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03SurfRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03SURF_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR" $LG/unity_as03b2_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as03b2_$TAG.log)"
date
