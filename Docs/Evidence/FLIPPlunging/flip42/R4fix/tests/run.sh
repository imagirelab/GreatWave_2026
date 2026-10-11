#!/bin/sh
# 使い方: sh run.sh <name> '<JSON>'   → <name>.txt
cd "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/R4fix/tests"
export HOUDINI_TEMP_DIR="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini" TEMP="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini" TMP="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/tmp_houdini"
"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe" "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42/x_r4fix_still.py" "$2" > "$1.txt" 2>&1
grep -v -E "breakpad|Steam" "$1.txt" | cut -c1-600
