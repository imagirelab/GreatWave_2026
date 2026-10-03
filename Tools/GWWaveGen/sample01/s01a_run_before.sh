#!/usr/bin/env bash
# 美術の見本01・見本 A：前（採用の状態＝仕上げ29 の材質 PL29 Ukiyoe Keypose、仕上げ29 修正の回の面の座標と値の表）を、
# 見本 A と同じ描画（S01ARender）・同じ視点・同じ時刻・爪なしで描く。出力 Build/Polish/sample01/texA/before。
set -u
cd G:/Unity/GreatWave_2026_Fresh
B=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texA
EXTRA="-pl36HeroMat Assets/GreatWave/Polish29/Materials/PL29_Ukiyoe_Hero.mat"
H="-pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin"
bash Tools/GWWaveGen/sample01/s01a_retry.sh before ${1:-views,tt} G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29/pl29_material_params.txt ${2:-12,10.5} "$EXTRA $H"
exit $?
for i in 1 2 3; do
  out=$(bash Tools/GWWaveGen/sample01/s01a_run_render.sh before ${1:-views,tt} G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl29/pl29_material_params.txt ${2:-12,10.5} "$EXTRA $H" 2>&1)
  echo "$out" | grep -E "DONE|OOM|error"
  echo "$out" | grep -q "D3D_OOM=0" && break
  sleep 20
done
