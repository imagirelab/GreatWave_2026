#!/usr/bin/env bash
# 美術の見本04 の調べ M（Q32）：AS04 Flat Smooth を t* で描く。見本03 の fix1_render.sh（変えない）の写しで、次を替えた。
#   主役波 = 凹凸のない静止のメッシュ（as04/mat_smooth_mesh.py、Build/Polish/sample04/mat/mesh/hero_smooth_as02c）、
#   材質 = GreatWave/ArtSample04/AS04FlatSmoothKeypose（AS04 Flat Smooth） ＋ 値の表（引数 3、既定 as04_flat_smooth_params.txt）、主役波の外殻の線あり、
#   冠・泡の皮・滴・頂の瘤は置かない（-as03Crown を渡さない）。爪は見本03 と同じ面の内 25・近い海 10 の 35 本に同じ材質（_AS03Src 2）。
#   描画の道具は見本03 の AS03AsmRender（変えない）。視点・時刻・海・回り台 crest のカメラは見本03 と同じ。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample04/mat/render/ の下）、2 = 段（views,crest など）、3 = 値の表（省くと既定）、4 以降 = 足す引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/render
LG=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/logs
MESH=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/mat/mesh
TA=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
S2=Build/Polish/sample02/fix01
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
OUT=$B/$1; ST=$2; PF=${3:-$TA/as04_flat_smooth_params.txt}; TAG=$1_$(echo $2 | tr ',' '_'); shift 2; [ $# -gt 0 ] && shift; XTRA="$*"
SH="GreatWave/ArtSample04/AS04FlatSmoothKeypose"
CL=Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json
HERO_PKG=$S2/assemble/hero_pkg_AS02C
HERO_GWB=$S2/back/final/cand/kstarAS02C_a45.gwb
A_ATTR=$S2/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as04/mat_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws 1 -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $MESH/hero_smooth_as02c.json -as03Shader ${SH} -as03Params $PF -as03HeroOutline ${AS04_OL:-1}"
G="-as03ClawGlaze ${SH} -as03ClawParams $PF"
mkdir -p $LG
date
$U -Method GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G -pl29Only $ST $XTRA" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_as04mat_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_as04mat_$TAG.log)"
date
