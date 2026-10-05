#!/usr/bin/env bash
# Q20 final loop 2: build the deliverables from a chosen iteration.  usage: bash fin2_final.sh <tag> <params.json>
set -e
TAG=$1; PRM=$2
K3=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar3
F=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/final
W=$F/_work2
BL=G:/SteamLibrary/steamapps/common/Blender/blender.exe
cd $K3
cp $W/$TAG.npz $W/final_rows.npz; cp $W/${TAG}_warp.json $W/final_rows_warp.json
py -3.10 fin2_deliver.py $W/final_rows.npz $PRM > $W/final_deliver.log 2>&1
tail -2 $W/final_deliver.log
py -3.10 $F/_analysis_model/fin_model_measure.py > $W/final_f13.log 2>&1
tail -1 $W/final_f13.log
$BL --background --factory-startup --python-exit-code 1 --python G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/judge_tech/bl_selfx.py -- $F/kstarF_bvh_selfx.json $F/kstarF_a45.gwb > $W/final_selfx.log 2>&1
grep SELFX $W/final_selfx.log | cut -c1-300
rm -rf $F/renders; mkdir -p $F/renders
$BL --background --factory-startup --python-exit-code 1 --python fin2_bl.py -- views $F/renders "kstarF=$F/kstarF_a45.gwb" all 1.0 > $W/final_bl.log 2>&1
mkdir -p $F/renders_kstar_current; cp $W/r_kstar/*.png $W/r_kstar/*.json $F/renders_kstar_current/
py -3.10 fin_sheet.py $F/fig_views_kstar_final_ref.png "Q20 K*' final (loop 2): 9 standard views - left K* 26修正01 (current) / middle K*' final / right reference model (someone else's sculpture, align B; shape reference only)" "$F/renders_kstar_current:kstar:K* 26修正01 (current)" "$F/renders:kstarF:K*' final" "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/rubric/renders:ref:reference model" --w 560
echo done
