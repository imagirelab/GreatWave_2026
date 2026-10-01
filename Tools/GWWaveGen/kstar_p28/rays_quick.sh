#!/bin/bash
# 仕上げ28 第1回：候補の粘土の早見（後ろの視点など）。usage: rays_quick.sh <out_dir> <label=gwb,...> [views]
OUT="$1"; ITEMS="$2"; VIEWS="${3:-b65_back65_clay+b65z_back65_zoom+b90_back_straight+b115_back_minus_c+u11_v9zoom_crest_bulge+v1_painting+v6_top_down+u13_v8zoom_b_region}"
mkdir -p "$OUT"
"G:/SteamLibrary/steamapps/common/Blender/blender.exe" --background --factory-startup --python-exit-code 1 --python "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar_p28/rays_bl.py" -- views "$OUT" "$ITEMS" "views=$VIEWS" > "$OUT/blender.log" 2>&1 || { echo "blender failed"; tail -20 "$OUT/blender.log"; exit 1; }
LABS=$(echo "$ITEMS" | tr ',' '\n' | cut -d= -f1 | paste -sd, -)
py -3.10 "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar_p28/rays_sheet.py" "$OUT" "$OUT/sheet.png" "$LABS" "$(echo $VIEWS | tr '+' ',')" 1600
echo "sheet $OUT/sheet.png"
