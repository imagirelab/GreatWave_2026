# -*- coding: utf-8 -*-
"""美術の見本05 の材質 AS05（Q33、T5・T6）の記録：道具・Unity の材質・入力・出力の SHA-256、形が同じことの確かめ、測りのまとめを
Unity/Build/Polish/sample05/mat/run.json に書く。

  py -3.10 -B Tools/GWWaveGen/as05/mat_record.py
"""
import glob
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402

R = M.REPO


def main():
    tools = sorted(glob.glob(R + "/Tools/GWWaveGen/as05/mat_*") + [R + "/Tools/GWWaveGen/as05/as05_flat_smooth_params.txt"])
    unity = sorted(glob.glob(R + "/Unity/Assets/GreatWave/ArtSample05/**/*", recursive=True))
    unity = [p for p in unity if os.path.isfile(p)] + [R + "/Unity/Assets/GreatWave/ArtSample05.meta"]
    same = [R + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04F_Flat_Smooth_Keypose.shader", R + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04FCommon.cginc",
            R + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs", R + "/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt"]
    mesh_out = M.MAT + "/mesh/union_as05.json"
    inputs = [M.UNION04F, M.UNION04F.replace(".json", ".bin"), M.CLAWS04F, M.P4 + "/fix1/shape/final/cand/kstarAS04F_a45_rows.npz"]
    outputs = [mesh_out, mesh_out.replace(".json", ".bin"), M.MAT + "/mesh/union_as05_edge_report.json", M.MAT + "/mesh/union_as05_edge_weight.npy"]
    # 形が同じこと（位置・三角形・whiteSD 以外の属性）
    ch0, t0, _ = M.read_static(M.UNION04F)
    ch1, t1, _ = M.read_static(mesh_out)
    geo = {"triangles_equal": bool(np.array_equal(t0, t1)), "position_equal": bool(np.array_equal(ch0["position"], ch1["position"]))}
    for k in ch0:
        a, b = ch0[k], ch1[k]
        if k == "uv5":
            geo["uv5_xyw_equal"] = bool(np.array_equal(a[:, [0, 1, 3]], b[:, [0, 1, 3]]))
            geo["uv5_z_whiteSD_changed_vertices"] = int((np.abs(a[:, 2] - b[:, 2]) > 1e-6).sum())
            geo["uv5_z_changed_only_hero"] = bool((np.abs(a[M.N_HERO04F:, 2] - b[M.N_HERO04F:, 2]) <= 1e-6).all())
        elif k != "position":
            geo[k + "_equal"] = bool(np.array_equal(a, b))
    renders = {}
    for tag in ("AS05F", "AS05_T5only", "AS05_v3"):
        d = M.MAT + "/render/" + tag
        if os.path.isdir(d):
            rep = M.jl(d + "/as03asm_render_report.json")
            renders[tag] = {"report": {k: rep.get(k) for k in ("unity", "device", "graphicsApi", "utc", "scene", "sceneSha256", "as03Surf", "as03SurfSha256", "as03Shader",
                                                               "as03Params", "as03ParamsSha256", "clawLayout", "heroPackage", "heroMeshGwb", "protectedUnchanged", "changedFiles")},
                            "images_sha256": {M.rel(p): M.sha(p) for p in sorted(glob.glob(d + "/views/*.png") + glob.glob(d + "/crest/*.png"))}}
    meas = {}
    for n in ("before_AS04F", "after_AS05F", "after_AS05_T5only", "after_AS05_v3"):
        p = M.MAT + "/measure/%s.json" % n
        if os.path.isfile(p):
            m = M.jl(p)
            meas[n] = {"K_T5_T6_study_rule": m.get("K_T5_T6_study_rule"), "T6_surface_edge": m.get("T6_surface_edge"),
                       "T5_views": {k: v["small_white_blobs_on_hero_indigo"] for k, v in m.get("T5_views", {}).items()}, "T5_crest": m.get("T5_crest")}
    sheets = sorted(glob.glob(M.MAT + "/sheets/*.png"))
    out = {"schema": "GreatWave.AS05.mat_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": ("美術の見本05 の材質 AS05（Q33）：T5 波の本体の白い粒を材質から外し、T6 唇の下の内の縁の白・水色を頂点の白の印の書き換えで外した。"
                       "形（主役波 K*′ AS04F ＋ wave4 fix1、爪 35 本）は見本04 の最後と同じ。Unity 6000.4.3f1 の PC オフスクリーン描画で、HMD 実機ではない。"),
           "commands": [
               "py -3.10 -B Tools/GWWaveGen/as05/mat_edge.py --out Unity/Build/Polish/sample05/mat/mesh/union_as05.json（入力の既定は見本04 の union.json）",
               "bash Tools/GWWaveGen/as05/mat_render.sh AS05F views,crest <union_as05.json>",
               "bash Tools/GWWaveGen/as05/mat_render.sh AS05_T5only views,crest <見本04 の union.json>（材質だけの差）",
               "py -3.10 -B Tools/GWWaveGen/as05/mat_measure.py --render <描画> --mesh <メッシュ> --edge-report <報告> --out measure/<名前>.json（前 = FX1、後 = AS05F・AS05_T5only）",
               "py -3.10 -B Tools/GWWaveGen/as05/mat_sheets.py --after Unity/Build/Polish/sample05/mat/render/AS05F --measure-after measure/after_AS05F.json",
               "py -3.10 -B Tools/GWWaveGen/as05/mat_record.py"],
           "tools": {M.rel(p): M.sha(p) for p in tools},
           "unity_assets_new": {M.rel(p): M.sha(p) for p in unity},
           "unity_assets_used_unchanged": {M.rel(p): M.sha(p) for p in same},
           "inputs": {M.rel(p): M.sha(p) for p in inputs},
           "outputs": {M.rel(p): M.sha(p) for p in outputs if os.path.isfile(p)},
           "geometry_identity": geo,
           "renders": renders, "measures": meas,
           "sheets": {M.rel(p): M.sha(p) for p in sheets}}
    M.jdump(M.MAT + "/run.json", out)
    print(geo)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
