#!/bin/sh
# 仕上げ28：粘土のこま（Blender Workbench、ヘッドレス、960×540、t 0〜14 s を 30 fps）を、設計28修正01 の E・F_final のこまと同じ設定・同じ視点で描く。
# 設計28修正01 の評審の run_clay_f.sh（作業場所）の frames と同じ分け方（3 つの Blender を同時に）。出力は Git 対象外の Unity/Build/Polish/28/clay/frames/<TAG>/。
# 使い方（リポジトリの根で）：sh Tools/GWWaveGen/pl28/run_pl28_clay.sh <TAG> <包み> <時間曲線> <K*′ のフォルダー>
#   例：sh Tools/GWWaveGen/pl28/run_pl28_clay.sh G_final Unity/Build/Polish/28/G_final/art_on Unity/Build/Polish/28/G_final/timewarp_G_final.json Unity/Build/Polish/28/kstar_G_final
B="G:/SteamLibrary/steamapps/common/Blender/blender.exe"
R="G:/Unity/GreatWave_2026_Fresh"
W="$R/Tools/GWWaveGen/pl28"
TAG="$1"; PKG="$R/$2"; WARP="$R/$3"; KST="$4"
G="$R/Unity/Build/Polish/28/clay"
LOG="$G/logs"
OUT="$G/frames/$TAG"
mkdir -p "$LOG" "$OUT"
export PYTHONIOENCODING=utf-8
run() { # views log
  "$B" --background --factory-startup --python-exit-code 1 --python "$W/pl28_clay_render.py" -- --mode frames --kstar "$KST" --pkg "$PKG" --warp "$WARP" --fine auto --out "$OUT" --views "$1" --w 960 --h 540 > "$LOG/frames_$2_$TAG.txt" 2>&1
  echo "frames $2 $TAG exit $?"
}
run side_follow,seat_up30 a &
run seat_toward_wave,painting b &
run back34_follow c &
wait
echo CLAY_PL28_DONE "$TAG"
