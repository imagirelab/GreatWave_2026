#!/bin/bash
# FLIP39 R：重い計算を順に一つずつ（粗い場の書き出しの終わりを待つ → 確かめ V1（粒子 1 m）→ 本番 H30（粒子 0.3 m、30 分の区切り））
R="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R"
T="G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
export HOUDINI_TEMP_DIR="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/tmp_houdini"
while [ ! -f "$R/C3_export/run.json" ]; do sleep 10; done
while tasklist | grep -qi hython; do sleep 5; done
echo "$(date) V1 start"
"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe" "$T/r_run_window.py" "$(cat $R/V1_val_d10/cfg.json)" > "$R/V1_val_d10/log_A.txt" 2>&1
echo "$(date) V1 end"
if [ -f "$R/HOLD" ]; then echo "HOLD present; not starting H30"; exit 0; fi
while tasklist | grep -qi hython; do sleep 5; done
echo "$(date) H30 start"
py -3.10 "$T/r_chain.py" "$R/H30_E3/cfg.json"
echo "$(date) H30 end"
