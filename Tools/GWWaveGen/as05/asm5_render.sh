#!/usr/bin/env bash
# 美術の見本05 の組み立て（Q33）：形 A・形 B のそれぞれに材質 AS05（白い粒なし T5・内の縁の白の書き換え T6 = mat_edge.py）を当てた静止のメッシュを、
# 爪 35 本（面の内 25・近い海 10。波頭の爪は出さない）と一緒に Unity で t* に描く。見本04 の前・後の比べ用に見本04（FX1 と同じ入力）も描ける。
# shapeA_render.sh・shapeB_render.sh（変えない）の写しで、次だけを替えた。
#   シェーダーは主役波・爪とも GreatWave/ArtSample05/AS05FlatSmoothKeypose、値の表は as05/as05_flat_smooth_params.txt（白い点の値なし）。
#   回り台の爪の有り無しを環境変数 TT_CLAWS（1 = _claws、0 = _noclaws）で替えられる。出力 Build/Polish/sample05/assemble/render/<引数 2>、
#   ログ Build/Polish/sample05/assemble/logs、Unity の起動は as05/asm5_unity.ps1（ロックの印 AS05ASM）。
# 引数 1 = 形（A・B・S04）、2 = 出力のフォルダー名、3 = 段（views,crest,tt,full,t28 など）、4 = 静止のメッシュの .json（S04 では省く）
#   A：主役波 AS05A ＋ wave4 fix1 ＋ ③ の波 layer3。一艘目の船を原画のカメラを中心とする相似（倍率 0.7434）で動かす（AS05ABoatRender、やり方 A の名前の付いた誘導）
#   B：主役波 AS05B ＋ wave4 fix1。船は動かさない（AS03AsmRender）
#   S04：見本04 の最後（FX1 と同じ入力・AS04F・as04 の値の表）。回り台の爪なしなど、FX1 に無い段を前の比べのために描く
# 視点・時刻・海・波頭の回り台・回り台のカメラは見本04 と同じ。原画のカメラの投影は使わない。
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
P5=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample05
B=$P5/assemble/render
LG=$P5/assemble/logs
T5=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
T=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01
VAR=$1; OUT=$B/$2; ST=$3; TTC=${TT_CLAWS:-1}; TAG=asm5_$2_$(echo $3 | tr ',' '_')_tt$TTC
PF=$T5/as05_flat_smooth_params.txt
SHD="GreatWave/ArtSample05/AS05FlatSmoothKeypose"
METHOD=GreatWave.ArtSample03.EditorTools.AS03AsmRender.Render
BO=""
case $VAR in
  A)
    SURF=$4
    CL=Build/Polish/sample05/shapeA/claws/ds33_claw_layout.json
    HERO_PKG=Build/Polish/sample05/shapeA/hero_pkg_AS05A
    HERO_GWB=Build/Polish/sample05/shapeA/hero/cand/kstarAS05A_a45.gwb
    A_ATTR=Build/Polish/sample05/shapeA/attr/a/s01a_hero_attr_v2_f32.bin
    METHOD=GreatWave.ArtSample05.EditorTools.AS05ABoatRender.Render
    BO="-as05BoatScale ${BOAT_S:-0.7434} -as05BoatLog $OUT/as05a_boat_$TTC.json" ;;
  B)
    SURF=$4
    CL=Build/Polish/sample05/shapeB/claws/ds33_claw_layout.json
    HERO_PKG=Build/Polish/sample05/shapeB/hero_pkg_AS05B
    HERO_GWB=Build/Polish/sample05/shapeB/final/cand/kstarAS05B_a45.gwb
    A_ATTR=Build/Polish/sample05/shapeB/attr/a/s01a_hero_attr_v2_f32.bin ;;
  S04)
    SURF=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/union.json
    CL=Build/Polish/sample04/fix1/shape/claws/ds33_claw_layout.json
    HERO_PKG=Build/Polish/sample04/fix1/shape/hero_pkg_AS04F
    HERO_GWB=Build/Polish/sample04/fix1/shape/final/cand/kstarAS04F_a45.gwb
    A_ATTR=Build/Polish/sample04/fix1/shape/attr/a/s01a_hero_attr_v2_f32.bin
    PF=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt
    SHD="GreatWave/ArtSample04/AS04FFlatSmoothKeypose" ;;
  *) echo "形は A・B・S04"; exit 2 ;;
esac
H="-pl29Attr $A_ATTR -pl29ParamFile $T/s01a_material_params_r1.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/as05/asm5_unity.ps1 -LogDir $LG"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times 12 -s01ViewsAsis 1 -as01ViewSpray 0 -s01TtClaws $TTC -pl31TtSpray 0 -pl29TtN 12"
C="-as03CrestCenter -6.63,16.5,-3.27 -as03CrestDist 34 -as03CrestEl 5 -as03CrestFov 35 -as03CrestN 8 -as03CrestHideFlat 1"
M="-pl29HeroPkg $HERO_PKG -pl29HeroGwb $HERO_GWB -pl31Spray $B31/spray -pl32Claws $CL"
X="-as03Surf $SURF -as03Shader ${SHD} -as03Params $PF -as03HeroOutline 1"
G="-as03ClawGlaze ${SHD} -as03ClawParams $PF"
mkdir -p $LG $OUT
date
$U -Method $METHOD -Log $TAG -Extra "$V $C -pl29Out $OUT $S $H $M $X $G $BO -pl29Only $ST" > $LG/run_$TAG.txt 2>&1
tail -2 $LG/run_$TAG.txt
grep -E "AS03ASM_RENDER_DONE|AS05A_BOAT|AS03SURF_MESH|error CS|Exception|Shader error|ERROR|error:" $LG/unity_asm5_$TAG.log | head -12
echo "D3D_OOM=$(grep -c 8007000e $LG/unity_asm5_$TAG.log)"
date
