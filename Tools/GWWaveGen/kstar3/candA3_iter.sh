#!/usr/bin/env bash
# Q20 loop 3 cand A3: one iteration = pipeline -> gwb -> eval (bg) -> half-size renders (clay + AO) -> sheet vs loop 2 / ref.
# usage: bash candA3_iter.sh tag params.json [vol.npz]
set -e
TAG=$1; PRM=$2
K3=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar3
W=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20L3/candA3/_work
VOL=${3:-G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20L3/candA3/_tmp/vol_p0.npz}
BL=G:/SteamLibrary/steamapps/common/Blender/blender.exe
cd $K3
py -3.10 candA3_pipeline.py $VOL $PRM $W/$TAG.npz > $W/${TAG}_pipe.log 2>&1
py -3.10 -c "import sys; sys.path.insert(0,'.'); import candA_export as EX; EX.export(r'$W/$TAG.npz', r'$W/${TAG}')" > $W/${TAG}_export.log 2>&1
py -3.10 fin_eval.py $W/$TAG.npz $W/ev_$TAG > $W/ev_${TAG}.log 2>&1 &
$BL --background --factory-startup --python-exit-code 1 --python candA3_bl.py -- views $W/r_$TAG "$TAG=$W/$TAG.gwb" all 0.5 > $W/${TAG}_bl.log 2>&1
wait
py -3.10 fin_sheet.py $W/sheet_$TAG.png "A3 $TAG (plain clay + AO) | left K*' loop 2 | right reference (someone else's sculpture)" "$W/r_kf:kstarF:K*' loop 2" "$W/r_$TAG:$TAG:A3 $TAG" "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/rubric/renders:ref:reference" --w 420 > /dev/null
py -3.10 $W/diag_rows.py $W/$TAG.npz $W/rows_$TAG.png
py -3.10 $W/hyg.py $W/$TAG.npz
grep -o '"gate": {[^}]*}' $W/${TAG}_pipe.log | tail -1
tail -1 $W/${TAG}_pipe.log
head -3 $W/ev_${TAG}_brief.txt 2>/dev/null || true
