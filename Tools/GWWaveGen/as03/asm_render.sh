#!/usr/bin/env bash
# 美術の見本03 の組み立て（Q31）：B1 の冠（OUT・IN）＋ B2 の彫りの面とシェーダー（SCULPT・FLAT）＋ 見本02 修正の回 1 の爪のうち面の内 25・近い海 10 の 35 本
# （asm_claws35.py。爪にも同じシェーダーの白い釉）を、t* の 1 つの描画で組み合わせる。描画の道具は AS03AsmRender（B2 の AS03SurfRender の写し＋冠の画・比べの視点）。
#   V1 = 冠 OUT ＋ SCULPT、V2 = 冠 OUT ＋ FLAT、V3 = 冠 IN ＋ SCULPT。
# 視点・時刻・海・主役波の包みは B2 の surf_render.sh（調べ S3・見本02 修正の回 1 と同じ）。回り台 tt は見本02 と同じ（爪あり・飛沫なし・海あり）。
# 波頭の回り台 crest は S3・B1・B2 と同じカメラで主役波（と冠・爪）だけ（AS03AsmRender が crest の間だけ周りの海のシートを隠す）。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample03/assemble/render/ の下）、2 = 冠 OUT|IN、3 = flat|sculpt、4 = 段（views,crest,tt,full,t28,cmp）、
# 5 以降 = 足す引数（-as03Cmp … など）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/assemble/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/assemble/logs
MESH=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/surface/mesh
CRW=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/crown
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as03
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
S2=Build/Polish/sample02/fix01
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; CM=$2; MODE=$3; ST=$4; TAG=$1_$(echo $4 | tr ',' '_'); shift 4; XTRA="$*"
if [ "$MODE" = "flat" ]; then SH="GreatWave/ArtSample03/AS03_Flat"; PF=$TA/surf_flat_params.txt; OL=1; else SH="GreatWave/ArtSample03/AS03_Sculpt"; PF=$TA/surf_sculpt_params.txt; OL=0; fi
CL=Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json
HERO_PKG=$S2/assemble/hero_pkg_AS02C
HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
A_ATTR=$S2/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as03/asm_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $MESH/hero_relief_b1v2c.json -as03Shader ${SH}_Keypose -as03Params $PF -as03HeroOutline $OL -as03Crown $CRW/$CM/as03_crown.json"
G="-as03ClawGlaze ${SH}_Keypose -as03ClawParams $PF -as03CrownMask 1 -as03CrownMaskCheck 1"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR" $LG/unity_as03asm_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as03asm_$TAG.log)"
date
