# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4：run.json（道具・入力・出力の SHA-256、使った命令、数）を書く。
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_record.py
出力：Unity/Build/Polish/sample04/wave4/run.json（Git 対象外）
"""
import glob
import json
import os
import time

import w4_common as W

R = W.REPO


def rel(p):
    return os.path.relpath(p, R).replace("\\", "/")


def shas(paths):
    return {rel(p): W.sha(p) for p in paths if os.path.isfile(p)}


def main():
    O = W.OUT
    tools = sorted(glob.glob(R + "/Tools/GWWaveGen/as04/w4_*"))
    inputs = [R + "/Docs/References/Met_JP1847_DP130155.jpg", R + "/Tools/PaintingTruth/targets/palette.json",
              R + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json",
              R + "/Unity/Build/Polish/sample04/map/s4_map.json", R + "/Unity/Build/Polish/sample04/map/s4_plan.json",
              W.HERO_ROWS_AS02C, W.HERO_MESH_AS02C, R + "/Unity/Build/Polish/sample04/mat/mesh/hero_smooth_as02c.bin",
              R + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb", R + "/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt",
              R + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04_Flat_Smooth_Keypose.shader",
              R + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04Common.cginc"]
    outs = []
    for pat in ("meas/*.json", "standin/*", "mesh/*", "mesh_as04/wave4*", "mesh_standin/wave4*", "mesh_as04/union.json", "mesh_standin/union.json",
                "check/*/w4_check.json", "render/measure/*/sweep_gates.json", "w4_sheet*.png", "render/*/as03asm_render_report.json"):
        outs += sorted(glob.glob(O + "/" + pat))
    snap = sorted(glob.glob(O + "/as04_snap/**/*", recursive=True))
    res = {"schema": "GreatWave.AS04.w4_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": "美術の見本04 の作り W4（Q32、S9）：左端の別の小さな青い波（④）。Unity 6000.4.3f1 の PC の描画（batchmode）と numpy の z バッファの測り。HMD 実機ではない。"
                      "参照モデルの OBJ・写真は読んでいない。原画の色は面へ写していない（帯の境の位置・白い点の位置だけを面の属性 u・c の値として持つ）。",
           "commands": [
               "py -3.10 -B Tools/GWWaveGen/as04/w4_paint.py",
               "py -3.10 -B Tools/GWWaveGen/as04/w4_standin.py",
               "bash Tools/GWWaveGen/as04/w4_render.sh final_nowave4 views G:/…/sample04/wave4/standin/hero_standin.json",
               "bash Tools/GWWaveGen/as04/w4_run_all.sh standin …/wave4/standin/standin_rows.npz …/wave4/standin/hero_standin.json final_nowave4",
               "（as04_snap を shape/ から写した後）W4_HERO_PKG=…/as04_snap/hero_pkg_AS04 W4_HERO_GWB=…/as04_snap/final/cand/kstarAS04_a45.gwb "
               "W4_ATTR=…/as04_snap/attr/a/s01a_hero_attr_v2_f32.bin W4_CLAWS=…/as04_snap/claws/ds33_claw_layout.json AS04_OL=1 "
               "bash Tools/GWWaveGen/as04/w4_render.sh as04_nowave4 views …/as04_snap/mesh/hero_smooth_as04.json",
               "（同じ環境の値で）bash Tools/GWWaveGen/as04/w4_run_all.sh as04 …/as04_snap/final/cand/kstarAS04_a45_rows.npz …/as04_snap/mesh/hero_smooth_as04.json as04_nowave4",
               "cp wave4/mesh_as04/wave4* wave4/mesh/",
               "py -3.10 -B Tools/GWWaveGen/as04/w4_record.py"],
           "tools": shas(tools), "inputs": shas(inputs), "as04_snapshot": shas(snap), "outputs": shas(outs),
           "protected_unchanged_ja": "見本01〜03 と採用のアセット、AS04 の材質（シェーダー・値の表）は変えていない。Unity の描画の報告はどれも protectedUnchanged=True。"}
    for nm in ("standin", "as04"):
        try:
            g = json.load(open(O + "/render/measure/gates_%s/sweep_gates.json" % nm, encoding="utf-8"))
            res["gates_" + nm] = {k: {"after_noclaws": v["after_noclaws"], "after_claws": v["after_claws"], "pass": v["pass_after"]} for k, v in g["gates"].items()}
            res["eval23_" + nm] = g.get("eval23", {}).get("after")
            c = json.load(open(O + "/check/%s/w4_check.json" % nm, encoding="utf-8"))
            res["check_" + nm] = {"silhouette_union": {k: v for k, v in c["silhouette"]["union"].items() if k != "by_x"},
                                  "silhouette_hero_only": {k: v for k, v in c["silhouette"]["hero_only"].items() if k != "by_x"},
                                  "wedge_visible_lower_y_ref_vs_painting": c["silhouette"]["wedge_visible_lower_y_ref_vs_painting"],
                                  "back_H": {k: v for k, v in c["back_H"].items() if k != "by_c"}, "penetration": c["penetration"]}
            b = json.load(open(O + "/mesh_%s/wave4_build_report.json" % nm, encoding="utf-8"))
            res["build_" + nm] = {k: b[k] for k in ("vertices", "triangles", "params", "clearance_above_ground_m", "boundary_height_above_ground_m",
                                                    "steep_triangles_dy_gt_0p5_slope_gt_3", "a_range", "c_range", "height_max_m", "crest_by_c",
                                                    "silhouette_iterations", "chips")}
        except FileNotFoundError as e:
            res["missing_" + nm] = str(e)
    W.jdump(O + "/run.json", res)
    print("run.json", len(res["tools"]), len(res["outputs"]), len(res["as04_snapshot"]))


if __name__ == "__main__":
    main()
