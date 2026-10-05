#!/usr/bin/env bash
# 美術の見本06 の直しの回（段の行 R8 → R9）：asm6_render.sh（変えない）の写し。形 R の置き場を直しの回のパイプラインの根
# Build/Polish/sample06/fix/final へ、出力を sample06/fix/render/<引数 2>、ログを sample06/fix/logs にした。ほかの決まり（視点・時刻・海・回り台・
# シェーダー AS05 Flat Smooth・値の表・一艘目の船の相似 0.6）は組み立てと同じ。
# 元の説明：美術の見本06 の組み立て（Q34）：as06/lobes_render.sh・rows_render.sh（変えない）の写し。形・爪の並び・船の倍率を引数と環境変数で渡し、
# 出力を Build/Polish/sample06/assemble/render/<引数 2>、ログを sample06/assemble/logs にした。視点・時刻・海・波頭の回り台・回り台のカメラ・
# シェーダー（AS05 Flat Smooth）・値の表は見本05・06 の作りと同じ。原画のカメラの投影は使わない。
# 一艘目の船：Q34「船可以挪」に従い、原画のカメラを中心とする相似（倍率 BOAT_S、既定 0.6 = 段の行 R8 と同じ）で手前へ動かす
# （AS05ABoatRender を変えずに使う。描画の時だけメモリの中で動かし、場面・プレハブは変えない）。
# 引数 1 = 形（L = 塊 AS06L、R = 段の行 AS06R）、2 = 出力のフォルダー名、3 = 段（views,crest,tt,full,t28 など）、4 = 静止のメッシュの .json、
#      5 = 爪の並び ds33_claw_layout.json（Unity/ からの相対）
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
PA=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/fix
B=$PA/render
LG=$PA/logs
T5=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
VAR=$1; OUT=$B/$2; ST=$3; SURF=$4; CL=$5; TTC=${TT_CLAWS:-1}; TAG=fix6_$2_$(echo $3 | tr ',' '_')_tt$TTC
PF=$T5/as05_flat_smooth_params.txt
SHD="GreatWave/ArtSample05/AS05FlatSmoothKeypose"
case $VAR in
  L)
    FR=Build/Polish/sample06/lobes/final2
    HERO_PKG=$FR/hero_pkg_AS06L
    HERO_GWB=$FR/cand/kstarAS06L_a45.gwb
    A_ATTR=$FR/attr/a/s01a_hero_attr_v2_f32.bin ;;
  R)
    FR=Build/Polish/sample06/fix/final
    HERO_PKG=$FR/hero_pkg_AS06R
    HERO_GWB=$FR/final/cand/kstarAS06R_a45.gwb
    A_ATTR=$FR/attr/a/s01a_hero_attr_v2_f32.bin ;;
  *) echo "形は L・R"; exit 2 ;;
esac
METHOD=GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render
BO="-as05BoatScale ${BOAT_S:-0.6} -as05BoatLog $OUT/as06asm_boat_$TTC.json"
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as06/asm6_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws $TTC -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline 1"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG $OUT
date
$U -Method $METHOD -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G $BO -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS05A_BOAT|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_asm6_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_asm6_$TAG.log)"
date
