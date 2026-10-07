#!/bin/bash
# FLIP39 E：E3 の後に、長い板の水槽 E1L（焦点まで 1006 m）を流す。
E="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
cd "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
until grep -q "queue-done" "$E/_queue.log" 2>/dev/null; do sleep 15; done
CFGL=$(py -3.10 e_cfg.py E1L_reef_S048 13.07 hybrid=0 shift=600 tf=190)
mkdir -p "$E/E1L_reef_S048"
py -3.10 e_chain.py "$CFGL" --wait > "$E/E1L_reef_S048/chain.log" 2>&1
py -3.10 e_post.py E1L_reef_S048 --clip > "$E/_post_E1L.log" 2>&1
echo queue2-done
