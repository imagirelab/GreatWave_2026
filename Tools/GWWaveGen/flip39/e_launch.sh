#!/bin/bash
# 使い方: bash e_launch.sh '<JSON>'   （重い計算は一度に一つ。動いている hython があれば止める）
export HOUDINI_TEMP_DIR="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/tmp_houdini"
if tasklist | grep -qi hython; then echo "another hython is running; abort"; exit 3; fi
RID=$(py -3.10 -c "import json,sys; print(json.loads(sys.argv[1])['run_id'])" "$1")
F0=$(py -3.10 -c "import json,sys; print(json.loads(sys.argv[1])['f_start'])" "$1")
mkdir -p "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/$RID"
LOG="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/$RID/log_c$(printf %04d $F0).txt"
date > "$LOG"
"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe" "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39/e_run.py" "$1" 2>&1 | grep -v "^Setting breakpad\|SteamInternal" >> "$LOG"
date >> "$LOG"
tail -3 "$LOG"
