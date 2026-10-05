#!/usr/bin/env bash
# 美術の見本06・B-LOBES（Q34）：as05/fx5_render.sh（変えない）の写し。形 L（主役波 AS06L ＋ wave4 fix1、材質 AS05 Flat Smooth）だけを、
# 出力 Build/Polish/sample06/lobes/assemble/render/<引数 1>、ログ sample06/lobes/assemble/logs で描く。視点・時刻・海・回り台のカメラは見本05 と同じ。
# 一艘目の船：Q34「船可以挪」に従い、原画のカメラを中心とする相似（倍率 BOAT_S、既定 0.7434 ＝ 見本05 形 A と同じ）で手前へ動かす
# （AS05ABoatRender、原画視点の船の画は同じ。描画の時だけメモリの中で動かし、場面・プレハブは変えない）。BOAT_S=1 なら動かさない。
# 引数 1 = 出力のフォルダー名、2 = 段（views,crest,tt など）、3 = 静止のメッシュの .json
# 原画のカメラの投影は使わない。
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P6=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/lobes
ASM=${ASM:-assemble}; FIN=${FIN:-final}   # 置き場（既定は形 L の最初の版 LB1 の assemble・final）
B=$P6/$ASM/render
LG=$P6/$ASM/logs
T5=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; SURF=$3; TTC=${TT_CLAWS:-1}; TAG=lobes_$1_$(echo $2 | tr ',' '_')_tt$TTC
PF=$T5/as05_flat_smooth_params.txt
SHD="GreatWave/ArtSample05/AS05FlatSmoothKeypose"
CL=Build/Polish/sample06/lobes/$FIN/claws/ds33_claw_layout.json
HERO_PKG=Build/Polish/sample06/lobes/$FIN/hero_pkg_AS06L
HERO_GWB=Build/Polish/sample06/lobes/$FIN/cand/kstarAS06L_a45.gwb
A_ATTR=Build/Polish/sample06/lobes/$FIN/attr/a/s01a_hero_attr_v2_f32.bin
METHOD=GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render
BO="-as05BoatScale ${BOAT_S:-0.7434} -as05BoatLog $OUT/as05a_boat_$TTC.json"
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as06/lobes_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws $TTC -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline 1"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG $OUT
date
$U -Method $METHOD -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G $BO -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS05A_BOAT|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_lobes_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_lobes_$TAG.log)"
date
