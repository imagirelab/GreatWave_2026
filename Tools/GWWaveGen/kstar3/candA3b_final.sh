#!/usr/bin/env bash
# Q21 candidate A3b: build the deliverables from a chosen iteration.  usage: bash candA3b_final.sh <tag> <params.json>
set -e
TAG=$1; PRM=$2
K3=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/kstar3
O=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20L3/candA3b
W=$O/_work
F2=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/final
RR=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/rubric/renders
BL=G:/SteamLibrary/steamapps/common/Blender/blender.exe
cd $K3
cp $W/$TAG.npz $W/final_rows.npz
py -3.10 candA3b_deliver.py $W/final_rows.npz $PRM > $W/final_deliver.log 2>&1
grep -E "^gate|^F13|^rubric" $W/final_deliver.log
$BL --background --factory-startup --python-exit-code 1 --python G:/Unity/GreatWave_2026_Fresh/Unity/Build/Q20/judge_tech/bl_selfx.py -- $O/candA3b_bvh_selfx.json $O/kstarA3b_a45.gwb > $W/final_selfx.log 2>&1
grep SELFX $W/final_selfx.log | cut -c1-300 || true
rm -rf $O/renders; mkdir -p $O/renders
$BL --background --factory-startup --python-exit-code 1 --python candA3b_bl.py -- views $O/renders "A3b=$O/kstarA3b_a45.gwb" all 1.0 > $W/final_bl.log 2>&1
mkdir -p $O/renders_loop2_user
$BL --background --factory-startup --python-exit-code 1 --python candA3b_bl.py -- views $O/renders_loop2_user "kstarF=$F2/kstarF_a45.gwb" u11_v9zoom_crest_bulge,u12a_v5_back_three_quarter,u13_v8zoom_b_region,u10_foot_zoom 1.0 > $W/final_bl2.log 2>&1
cp $F2/renders/kstarF__v6_top_down.png $O/renders_loop2_user/
py -3.10 fin_sheet.py $O/fig_views_loop2_A3b_ref.png "Q21 candidate A3b: 9 standard views - left loop-2 K*' (Q21 rejected) / middle A3b / right reference model (someone else's sculpture, align B)" "$F2/renders:kstarF:loop-2 K*' (rejected)" "$O/renders:A3b:A3b" "$RR:ref:reference model" --w 560
py -3.10 candA3b_usersheet.py $O/fig_user_failure_views.png $O/renders_loop2_user $O/renders
mkdir -p $O/turntable_stills
$BL --background --factory-startup --python-exit-code 1 --python candA3b_bl.py -- turntable $O/kstarA3b_a45.gwb $O/candA3b_turntable.mp4 $O/turntable_stills 240 72 16 1280 720 > $W/final_tt.log 2>&1
py -3.10 fin2_contact.py $O/turntable_stills $O/fig_turntable_contact.png "Q21 candidate A3b: clay turntable (12 of 240 frames, radius 72 m, elevation 16 deg)"
echo done
