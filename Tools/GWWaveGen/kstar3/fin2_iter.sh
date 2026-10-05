#!/usr/bin/env bash
# Q20 final loop 2: one iteration = pipeline -> gwb -> eval (bg) -> half-size renders (new sea) -> sheet vs loop 1.
# usage: bash fin2_iter.sh tag params.json [views]
set -e
TAG=$1; PRM=$2; VIEWS=${3:-all}
K3=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar3
W=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/final/_work2
BL=G:/SteamLibrary/steamapps/common/Blender/blender.exe
cd $K3
py -3.10 fin2_pipeline.py $PRM $W/$TAG.npz > $W/${TAG}_pipe.log 2>&1
py -3.10 -c "import sys; sys.path.insert(0,'.'); import candA_export as EX; EX.export(r'$W/$TAG.npz', r'$W/${TAG}')" > $W/${TAG}_export.log 2>&1
py -3.10 fin_eval.py $W/$TAG.npz $W/ev_$TAG > $W/ev_${TAG}.log 2>&1 &
$BL --background --factory-startup --python-exit-code 1 --python fin2_bl.py -- views $W/r_$TAG "$TAG=$W/$TAG.gwb" $VIEWS 0.5 > $W/${TAG}_bl.log 2>&1
wait
py -3.10 fin_sheet.py $W/sheet_$TAG.png "$TAG" "$W/r_base:base:loop1" "$W/r_$TAG:$TAG:$TAG" --w 420 > /dev/null
head -2 $W/ev_${TAG}_brief.txt
