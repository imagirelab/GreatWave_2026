#!/usr/bin/env bash
# 美術の見本06 の段の行（B-ROWS）の試し：設計 .json から 行の作り直し → 断面の下見 → 素早い測り → 粘土（見本05 B と並べる）。
# 使い方：bash Tools/GWWaveGen/as06/rows_try.sh <名前> [sep] [noclay]   設計は Unity/Build/Polish/sample06/rows/try/<名前>.json
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
R=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/rows
N=$1; SEP=${2:-}; NOCLAY=${3:-}
D=$R/try/$N
mkdir -p $D
py -3.10 -B Tools/GWWaveGen/as06/rows_build.py $D/cand $R/try/$N.json > $D/build.log 2>&1 || { echo build_failed; tail -5 $D/build.log; exit 1; }
py -3.10 -B Tools/GWWaveGen/as06/rows_diag.py $D/sections.png B10=Unity/Build/Polish/sample05/fix1/B/final/cand/kstarAS05B_a45_rows.npz $N=$D/cand_rows.npz --c=-23.5,-22.0,-20.5,-19.0,-17.5,-16.2,-15.0,-13.5,-12.0,-10.6,-9.4,-8.6 > /dev/null
Q="--gate"; [ "$SEP" = "sep" ] && Q="--gate --sep"
py -3.10 -B Tools/GWWaveGen/as06/rows_quick.py $D/cand_rows.npz $D/cand_build_log.json $D/quick $Q > $D/quick.log 2>&1 || { echo quick_failed; tail -5 $D/quick.log; }
cat > $D/cand.json << EOT
{"name": "B-ROWS $N", "rows": "$D/cand_rows.npz", "row_labels": "$D/quick/row_labels.npy",
 "meshes": [{"path": "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json", "role": "wave4", "layer": 0}]}
EOT
py -3.10 -B - << EOT
import json
d=json.load(open("$D/quick/quick.json",encoding="utf-8"))
g=d["geometry"]; L=g["layers"]
def f(k):
    r=L.get(k)
    return None if not r else {"y":r["crest"]["y_over_H0"],"a":r["crest"]["a"],"c":r["crest"]["c"],"prom":r["prominence_m"],"ahead":r.get("crest_ahead_of_saddle_a_m"),"sad":r.get("saddle"),"dist":r["dist_to_painting_cam_m"],"under":r.get("undercut_m"),"lip":r.get("lip_ahead_of_crest_m")}
print("Ktop",d["K_top_max_disp_m"],"selfx",d["spill_vs_AS04F"]["selfx_new_rows_c"],"sky",d["spill_vs_AS04F"]["sky_keepout_new_cells"])
print("S8",d["S8"]["dev_from_inner_face_m"]["p95"],d["S8"]["first_hit_inner_face_share"],"S10",d["S10_union_widths"]["diff"],"S4",d["S4_H_union_dent_m"])
print("L2",f("2")); print("L3",f("3")); print("steps",g["steps"])
print("label",{k:v["share_label_k"] for k,v in d["painting_label_consistency"].items()})
print("gate",{k:v["max"] for k,v in d.get("gate_proxy",{}).items()})
print("sep",d.get("separation_summary"))
EOT
if [ "$NOCLAY" != "noclay" ]; then
py -3.10 -B Tools/GWWaveGen/as06/rows_clay.py $D/clay B10=Unity/Build/Polish/sample05/fix1/assemble/measure/targets_B10.json $N=$D/cand.json > $D/clay.log 2>&1; echo clay $?
fi
