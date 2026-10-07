#!/bin/bash
E="G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E"
cd "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39"
# 板の flat の座席は走っている e_seat（全コマ）の終わりを待つ
while tasklist | grep -q " 58904 "; do sleep 10; done
py -3.10 e_post.py E1_flat_S036 --no-analyze --no-seat
py -3.10 e_post.py E1_reef_S036 E1h_reef_S048 --no-analyze
py -3.10 e_post.py E1_reef_S060 --no-analyze --no-seat
py -3.10 e_post.py E1_reef_S048 --no-analyze --no-seat --clip
echo post2-done
