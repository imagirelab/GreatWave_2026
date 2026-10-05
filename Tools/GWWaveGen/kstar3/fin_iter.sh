#!/usr/bin/env bash
# Q20 final: one iteration = pipeline -> gwb -> eval -> half-size renders -> sheet.  usage: bash fin_iter.sh tag [views]
set -e
TAG=$1; VIEWS=${2:-all}
K3=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar3
W=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/final/_work
BL=G:/SteamLibrary/steamapps/common/Blender/blender.exe
cd $K3
py -3.10 fin_pipeline.py fin_params.json $W/$TAG.npz > $W/${TAG}_pipe.log 2>&1
py -3.10 -c "import sys; sys.path.insert(0,'.'); import candA_export as EX; print(EX.export(r'$W/$TAG.npz', r'$W/${TAG}'))" > $W/${TAG}_export.log 2>&1
py -3.10 fin_eval.py $W/$TAG.npz $W/ev_$TAG > $W/ev_${TAG}.log 2>&1 &
$BL --background --factory-startup --python-exit-code 1 --python fin_bl_views.py -- $W/r_$TAG $TAG $W/$TAG.gwb $VIEWS 0.5 > $W/${TAG}_bl.log 2>&1
wait
py -3.10 fin_sheet.py $W/sheet_$TAG.png "$TAG" "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/candA/renders:candA:candA" "$W/r_$TAG:$TAG:$TAG" --w 420 > /dev/null
head -3 $W/ev_${TAG}.log
