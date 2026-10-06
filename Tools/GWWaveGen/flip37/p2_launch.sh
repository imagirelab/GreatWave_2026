#!/bin/sh
# P2 の計算を 1 本走らせる（Git Bash）。使い方: sh p2_launch.sh <run_id> '<parms JSON>' [f_end]
RID="$1"; PARMS="$2"; FEND="${3:-360}"
export HOUDINI_TEMP_DIR="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/tmp_houdini"
J="{\"run_id\": \"$RID\", \"parms\": $PARMS, \"f_start\": 1, \"f_end\": $FEND, \"snap_from\": 145, \"snap_every\": 2, \"snap_x\": [380, 806], \"snap_zhalf\": 1.5, \"mesh_from\": 145, \"mesh_every\": 3, \"wall_limit_s\": 1740}"
"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe" "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37/run_p2.py" "$J" 2>&1 | grep -v -i "steam\|breakpad" > "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/logs/$RID.log"
