# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：作った行（lobes_build の出力）を素早く測る（形だけ。Unity の描画は使わない）。shapeB_quick.py（見本05、変えない）の写しで、
層の印を lobes_build の _labels.npy（塊の距離で付けた印）にし、船・手前の海の射線の禁止域は外した（Q34：船を避ける制約を外す）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_quick.py <prefix> <out_dir> [--gate] [--sep]
測り：K-top（c ≥ −8 の行の動き）、断面の新しい自己交差、原画の空の射線の禁止域への新しいはみ出し（見本04 AS04F に対して）、
  S8（shape_common.bulge_metric）、S4 の目安（合わせた H(c) のへこみ）、S10（帯の幅、wave4 と合わせて、見本04 と比べる）、
  L1〜L5（s5_targets.geometry、wave4 を含む）、L6-label（原画視点の印の整合）、--sep で L6-sep（15 視点）、--gate で関門の近い値（numpy）。
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lobes_common as L  # noqa: E402

B = L.B
import s5_targets as T5  # noqa: E402
import shapeB_quick as BQ  # noqa: E402


def spill_sky(c, A, Y, base):
    import r2_build as B2
    import r2_common as R
    c0, A0, Y0 = base
    sx = np.array([B2.seg_selfx(A[i], Y[i], 0, None) for i in range(len(c))])
    sx0 = np.array([B2.seg_selfx(A0[i], Y0[i], 0, None) for i in range(len(c))])
    Gs = R.keepout_grids(c, 3, 2, cache=L.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    sky = []
    for i in range(len(c)):
        if np.allclose(A[i], A0[i]) and np.allclose(Y[i], Y0[i]):
            continue
        f0 = R.section_fill(A0[i], Y0[i]); f1 = R.section_fill(A[i], Y[i])
        ns = int((f1 & Gs[i] & ~f0).sum())
        if ns:
            sky.append((L.rnd(c[i], 2), ns))
    return {"selfx_new_rows_c": [L.rnd(c[i], 2) for i in np.nonzero(sx > sx0)[0]],
            "sky_keepout_new_cells": int(sum(n for _, n in sky)), "sky_rows": sky, "cell_m": R.GRES}


def main():
    pre, od = sys.argv[1], sys.argv[2]
    os.makedirs(od, exist_ok=True)
    t0 = time.time()
    rows = pre + "_rows.npz"
    c, A, Y = B.load_rows(rows)
    c0, A0, Y0 = B.load_rows(L.ROWS04F)
    RL = np.load(pre + "_labels.npy")
    res = {"rows": rows, "rows_sha256": L.sha(rows)}
    kt = c >= L.C_KTOP
    res["K_top_max_disp_m"] = L.rnd(max(np.abs(A - A0)[kt].max(), np.abs(Y - Y0)[kt].max()), 4)
    res["spill_vs_AS04F"] = spill_sky(c, A, Y, (c0, A0, Y0))
    res["S8"] = B.SC.bulge_metric(c, A, Y)
    ch4, tri4, _ = T5.S.W4.read_static(L.WAVE4_F1)
    X4 = ch4["position"].astype(np.float64)
    bw, dent = BQ.bands_union(c, Y, X4)
    bw0, dent0 = BQ.bands_union(c0, Y0, X4)
    res["S10_union_widths"] = {"cand": bw, "sample04": bw0, "diff": {k: (L.rnd(bw[k] - bw0[k], 2) if bw[k] is not None and bw0[k] is not None else None) for k in bw}}
    res["S4_H_union_dent_m"] = {"cand": L.rnd(dent, 3), "sample04": L.rnd(dent0, 3)}
    meshes = [{"P": X4, "tri": tri4.astype(np.int64), "vl": np.zeros(len(X4), np.int16), "role": "wave4"}]
    res["geometry"] = T5.geometry(c, A, Y, meshes)
    tris, lab = T5.scene(c, A, Y, RL, meshes)
    res["painting_label_consistency"], _, _ = T5.painting_consistency(tris, lab)
    if "--sep" in sys.argv:
        res["separation_views"], res["separation_summary"] = T5.separation(tris, lab, od + "/views_layers")
    if "--gate" in sys.argv:
        res["gate_proxy"] = B.SC.gate_proxy(c, A, Y, od + "/gate_overlay.png")
    res["seconds"] = round(time.time() - t0, 1)
    L.jdump(od + "/quick.json", res)
    g = res["geometry"]
    LL = g["layers"]

    def lrec(k):
        r = LL.get(k)
        if not r:
            return None
        return {"y/H0": r["crest"]["y_over_H0"], "a": r["crest"]["a"], "c": r["crest"]["c"], "prom": r["prominence_m"], "ahead": r.get("crest_ahead_of_saddle_a_m"),
                "dist": r["dist_to_painting_cam_m"], "lip": r.get("lip_ahead_of_crest_m"), "under": r.get("undercut_m")}
    print(json.dumps({"K_top": res["K_top_max_disp_m"], "spill": {k: v for k, v in res["spill_vs_AS04F"].items() if not k.endswith("rows")},
                      "S8_p95": res["S8"]["dev_from_inner_face_m"]["p95"], "S8_inner": res["S8"]["first_hit_inner_face_share"],
                      "S10diff": res["S10_union_widths"]["diff"], "S4dent": res["S4_H_union_dent_m"],
                      "L1": lrec("1"), "L2": lrec("2"), "L3": lrec("3"), "steps": g["steps"], "Hc_proxy_dent": g["Hc_proxy_dent_m"],
                      "L6label": {k: v["share_label_k"] for k, v in res["painting_label_consistency"].items()},
                      "sep": res.get("separation_summary"), "gate": res.get("gate_proxy"), "sec": res["seconds"]}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
