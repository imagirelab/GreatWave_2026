#!/usr/bin/env bash
# 美術の見本06 の直しの回（R8 → R9）の試し：rows_try.sh（変えない）の写し。設計 .json から 行の作り直し（fix6_build.py）→ 断面の下見（R8 と並べる）
# → 素早い測り（rows_quick.py）→ 断面の数（fix6_prof.py）→ [pipe] 静止のメッシュまで作って帯の座標 w の伸び（G1）とメッシュの折れ角 → [clay] 粘土。
# 使い方：bash Tools/GWWaveGen/as06/fix6_try.sh <名前> [sep] [pipe] [clay]   設計は Unity/Build/Polish/sample06/fix/try/<名前>.json
set -u
cd G:/Unity/GreatWave_2026_Fresh
export PYTHONIOENCODING=utf-8
R=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/fix
R8=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/rows/final_d/final/cand/kstarAS06R_a45_rows.npz
N=$1; shift; OPT="$*"
D=$R/try/$N
mkdir -p $D
py -3.10 -B Tools/GWWaveGen/as06/fix6_build.py $D/cand $R/try/$N.json > $D/build.log 2>&1 || { echo build_failed; tail -5 $D/build.log; exit 1; }
py -3.10 -B Tools/GWWaveGen/as06/rows_diag.py $D/sections.png R8=$R8 $N=$D/cand_rows.npz --c=-23.5,-22.45,-21.6,-21.07,-20.09,-19.42,-18.0,-16.2,-15.0,-13.6,-12.0,-10.6 > /dev/null
Q="--gate"; [[ "$OPT" == *sep* ]] && Q="--gate --sep"
py -3.10 -B Tools/GWWaveGen/as06/rows_quick.py $D/cand_rows.npz $D/cand_build_log.json $D/quick $Q > $D/quick.log 2>&1 || { echo quick_failed; tail -5 $D/quick.log; }
cat > $D/cand.json << EOT
{"name": "R9 try $N", "rows": "$D/cand_rows.npz", "row_labels": "$D/quick/row_labels.npy",
 "meshes": [{"path": "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample04/wave4/mesh_fix1/wave4.json", "role": "wave4", "layer": 0}]}
EOT
py -3.10 -B - << EOT
import json
d=json.load(open("$D/quick/quick.json",encoding="utf-8"))
g=d["geometry"]; L=g["layers"]
def f(k):
    r=L.get(k)
    return None if not r else {"y":r["crest"]["y_over_H0"],"a":r["crest"]["a"],"c":r["crest"]["c"],"prom":r["prominence_m"],"ahead":r.get("crest_ahead_of_saddle_a_m"),"dist":r["dist_to_painting_cam_m"],"under":r.get("undercut_m"),"lip":r.get("lip_ahead_of_crest_m")}
print("Ktop",d["K_top_max_disp_m"],"selfx",d["spill_vs_AS04F"]["selfx_new_rows_c"],"sky",d["spill_vs_AS04F"]["sky_keepout_new_cells"],"boatcells",d["spill_vs_AS04F"]["boat_nearsea_keepout_new_cells"])
print("S8",d["S8"]["dev_from_inner_face_m"]["p95"],d["S8"]["first_hit_inner_face_share"],"S10",d["S10_union_widths"]["diff"],"S4",d["S4_H_union_dent_m"])
print("L2",f("2")); print("L3",f("3")); print("steps",g["steps"])
print("label",{k:v["share_label_k"] for k,v in d["painting_label_consistency"].items()})
print("gate",{k:v["max"] for k,v in d.get("gate_proxy",{}).items()})
print("sep",d.get("separation_summary"))
EOT
py -3.10 -B Tools/GWWaveGen/as06/fix6_prof.py $D/cand_rows.npz $D/prof.json > $D/prof.log 2>&1; grep -v "^dihedral" $D/prof.log | cut -c1-260
if [[ "$OPT" == *pipe* ]]; then
  py -3.10 -c "
import json; d=json.load(open('$R/try/$N.json',encoding='utf-8')); d['write_candidate']=True
json.dump(d,open('$R/try/${N}_w.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)"
  bash Tools/GWWaveGen/as06/fix6_pipeline.sh $R/try/${N}_pipe $R/try/${N}_w.json > $R/try/${N}_pipe.txt 2>&1
  grep -v "^Mon" $R/try/${N}_pipe.txt | tr '\n' ' '; echo
  py -3.10 -B Tools/GWWaveGen/as06/rows_stretch.py $R/try/${N}_pipe/mesh/hero_smooth_as06r.json
  py -3.10 -B Tools/GWWaveGen/as06/fix6_prof.py $D/cand_rows.npz --mesh=$R/try/${N}_pipe/mesh/hero_smooth_as06r.json 2>&1 | grep mesh_dih
fi
if [[ "$OPT" == *clay* ]]; then
  py -3.10 -B Tools/GWWaveGen/as06/rows_clay.py $D/clay R8=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample06/assemble/measure/cand_R8A.json $N=$D/cand.json > $D/clay.log 2>&1; echo clay $?
fi
