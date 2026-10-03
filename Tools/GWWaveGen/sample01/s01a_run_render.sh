#!/usr/bin/env bash
# 美術の見本01・見本 A（彫刻のような刻み）：審査の視点の描画（仕上げ36 の pl36_run_render.sh を写し、描画を S01ARender、
# 出力を Build/Polish/sample01/texA/ の下にしたもの）。海・飛沫・線は仕上げ33修正01／35 の採る状態と同じ。爪は描かない（views の爪なし、回り台も爪なし）。
# 主役波の材質は S01A Groove Keypose（S01ARender の既定。シェーダーの名前から作る）、属性は Build/Polish/sample01/texA/attr、値の表は引数 3。
# 引数 1 = 出力のフォルダー名（Build/Polish/sample01/texA/ の下）、2 = 段（views,tt,ids,fields など）、
#      3 = 主役波の値の表（既定 Tools/GWWaveGen/sample01/s01a_material_params.txt）、4 = 時刻（既定 12,10.5）、5 = 追加の引数
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texA
B31=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31
B30=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/30
PF=${3:-G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01/s01a_material_params.txt}
TIMES=${4:-12,10.5}
EXTRA=${5:-}
# 頂点の属性（環境の変数 S01A_ATTR で替えられる。a7 からは v2：s01a_attr.py --v2 の出力、材質の _AttrV2=1 と組で使う）
ATTR=${S01A_ATTR:-Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin}
H="-pl29Attr $ATTR -pl29ClawShade 1 -pl29ParamFile $PF -pl29ClawParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32/pl32_claw_params.txt"
S="-pl30Sea $B30/sea -pl30SeaParamFile G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell $B30/left_swell/pl30_left_swell.json"
U="powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/sample01/s01a_run_unity.ps1"
V="-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29Times $TIMES -s01ViewsAsis 0 -s01TtClaws 0"
OUT=$B/$1; ST=$2
M="-pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray $B31/spray -pl32Claws Build/Polish/33r01/fix01/claws/ds33_claw_layout.json -pl32Look 1 -pl33Look 1"
mkdir -p $B/logs
TAG=$1_$(echo $ST | tr ',' '_')
date
$U -Method GreatWave.Sample01.TexA.EditorTools.S01ARender.Render -Log $TAG -Extra "$V $EXTRA -pl29Out $OUT $S $H $M -pl29Only $ST" > $B/logs/run_$TAG.txt 2>&1
grep S01A_UNITY $B/logs/run_$TAG.txt
grep -E "S01A_RENDER_DONE|error CS|Exception" $B/logs/unity_s01a_$TAG.log | head -5
echo "D3D_OOM=$(grep -c 8007000e $B/logs/unity_s01a_$TAG.log)"   # メモリ不足で描画の板が作れなかった回数（0 でなければ描き直す）
date
