# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：作った行（shapeB_build の出力）を素早く測る（形だけ。Unity の描画は使わない）。
py -3.10 -B Tools/GWWaveGen/as05/shapeB_quick.py <cand_rows.npz> <build_log.json> <out_dir> [--gate] [--sep] [--plot]

  層の印（row_labels）：① 行 c ≥ c1_lo の頂より前（列 ≥ 90）、② ・③ は段の窓の行（build_log の layer）の溝より前（溝 = 背の頂と縁の頂の間の最も低い列）。
     層の間は印を空けて（ギャップ）、隣どうしの層の印が直に触れないようにする（見本04 の c の帯と同じ考え）。
  測り：K-top（c ≥ −8 の行の動き）、断面の新しい自己交差、原画の空・船と手前の海の射線の禁止域への新しいはみ出し（見本04 AS04F に対して）、
     S8（shape_common.bulge_metric）、S4 の目安（合わせた H(c) のへこみ）、S10（帯の幅、wave4 と合わせて、見本04 と比べる）、
     L1〜L5（s5_targets.geometry、wave4 を含む）、L6-label（原画視点の印の整合）、--sep で L6-sep（15 視点）、--gate で関門の近い値（numpy）。
"""
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeB_common as B  # noqa: E402
import s5_targets as T5  # noqa: E402

# 層の印の c の範囲（層の間は印を空ける）。① は K-top の行、② は ② の段の行、③ は ③ の段と、その左の舌を短くした行（最左側の小区域）
LAB_C = {1: (-8.0, 15.0), 2: (-13.6, -8.9), 3: (-21.5, -14.6)}
LAB_YMIN = {1: 0.25, 2: 0.20, 3: 0.12}


def row_labels(c, A, Y, lay, s):
    RL = np.zeros(A.shape, np.int16)
    J = np.arange(A.shape[1])
    for i in np.nonzero((c >= LAB_C[1][0]) & (c <= LAB_C[1][1]))[0]:
        RL[i, (J >= B.J_TOP) & (J <= B.J_FACEBOT) & (Y[i] >= LAB_YMIN[1] * B.H0)] = 1
    for i in range(len(c)):
        L = 3 if LAB_C[3][0] <= c[i] <= LAB_C[3][1] else (2 if LAB_C[2][0] <= c[i] <= LAB_C[2][1] else 0)
        if not L:
            continue
        je = 110 + int(np.argmax(Y[i, 110:262]))
        jg = 100 + int(np.argmin(Y[i, 100:je + 1])) if je > 101 else B.J_TOP
        RL[i, (J >= jg) & (J <= B.J_FACEBOT) & (Y[i] >= LAB_YMIN[L] * B.H0)] = L
    return RL


def spill(c, A, Y, base):
    import r2_build as B2
    import r2_common as R
    c0, A0, Y0 = base
    sx = np.array([B2.seg_selfx(A[i], Y[i], 0, None) for i in range(len(c))])
    sx0 = np.array([B2.seg_selfx(A0[i], Y0[i], 0, None) for i in range(len(c))])
    Gs = R.keepout_grids(c, 3, 2, cache=B.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    zp = np.load(B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
    Gp = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    sky, prot = [], []
    for i in range(len(c)):
        if np.allclose(A[i], A0[i]) and np.allclose(Y[i], Y0[i]):
            continue
        f0 = R.section_fill(A0[i], Y0[i]); f1 = R.section_fill(A[i], Y[i])
        ns = int((f1 & Gs[i] & ~f0).sum()); npr = int((f1 & Gp[i] & ~f0).sum())
        if ns:
            sky.append((B.rnd(c[i], 2), ns))
        if npr:
            prot.append((B.rnd(c[i], 2), npr))
    return {"selfx_new_rows_c": [B.rnd(c[i], 2) for i in np.nonzero(sx > sx0)[0]],
            "sky_keepout_new_cells": int(sum(n for _, n in sky)), "sky_rows": sky,
            "boat_nearsea_keepout_new_cells": int(sum(n for _, n in prot)), "boat_rows": prot, "cell_m": R.GRES}


def bands_union(c, Yr, X4, H=20.27, fr=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    Hc = Yr[:, B.J_B:B.J_TIP + 1].max(1)
    cg = np.arange(-60.0, 15.0001, 0.05)
    hh = np.interp(cg, c, Hc)
    Q = B.K.sec(X4)
    k = np.clip(np.round((Q[:, 2] + 60.0) / 0.05).astype(int), 0, len(cg) - 1)
    w4 = np.zeros(len(cg)); np.maximum.at(w4, k, Q[:, 1])
    hu = np.maximum(hh, w4)
    out = {}
    for f in fr:
        sel = np.nonzero(hu >= f * H)[0]
        out["%.1f" % f] = B.rnd(cg[sel[-1]] - cg[sel[0]], 2) if len(sel) else None
    dent = 0.0
    im = int(np.argmax(hu))
    for seg in (hu[:im + 1], hu[im:][::-1]):
        dent = max(dent, float((np.maximum.accumulate(seg) - seg).max()))
    return out, dent


def main():
    rows, logp, od = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(od, exist_ok=True)
    t0 = time.time()
    c, A, Y = B.load_rows(rows)
    c0, A0, Y0 = B.load_rows(B.ROWS04F)
    lg = json.load(open(logp, encoding="utf-8"))["log"]
    lay, s = np.array(lg["layer"]), np.array(lg["s"])
    RL = row_labels(c, A, Y, lay, s)
    np.save(od + "/row_labels.npy", RL)
    res = {"rows": rows, "rows_sha256": B.sha(rows)}
    kt = c >= B.C_KTOP
    res["K_top_max_disp_m"] = B.rnd(max(np.abs(A - A0)[kt].max(), np.abs(Y - Y0)[kt].max()), 4)
    res["spill_vs_AS04F"] = spill(c, A, Y, (c0, A0, Y0))
    res["S8"] = B.SC.bulge_metric(c, A, Y)
    ch4, tri4, _ = T5.S.W4.read_static(B.WAVE4_F1)
    X4 = ch4["position"].astype(np.float64)
    bw, dent = bands_union(c, Y, X4)
    bw0, dent0 = bands_union(c0, Y0, X4)
    res["S10_union_widths"] = {"cand": bw, "sample04": bw0, "diff": {k: (B.rnd(bw[k] - bw0[k], 2) if bw[k] is not None and bw0[k] is not None else None) for k in bw}}
    res["S4_H_union_dent_m"] = {"cand": B.rnd(dent, 3), "sample04": B.rnd(dent0, 3)}
    meshes = [{"P": X4, "tri": tri4.astype(np.int64), "vl": np.zeros(len(X4), np.int16), "role": "wave4"}]
    res["geometry"] = T5.geometry(c, A, Y, meshes)
    tris, lab = T5.scene(c, A, Y, RL, meshes)
    res["painting_label_consistency"], _, _ = T5.painting_consistency(tris, lab)
    if "--sep" in sys.argv:
        res["separation_views"], res["separation_summary"] = T5.separation(tris, lab, od + "/views_layers")
    if "--gate" in sys.argv:
        res["gate_proxy"] = B.SC.gate_proxy(c, A, Y, od + "/gate_overlay.png")
    res["seconds"] = round(time.time() - t0, 1)
    B.jdump(od + "/quick.json", res)
    g = res["geometry"]
    L = g["layers"]
    def lrec(k):
        r = L.get(k)
        if not r:
            return None
        return {"y/H0": r["crest"]["y_over_H0"], "a": r["crest"]["a"], "c": r["crest"]["c"], "prom": r["prominence_m"], "ahead": r.get("crest_ahead_of_saddle_a_m"),
                "dist": r["dist_to_painting_cam_m"], "lip": r.get("lip_ahead_of_crest_m"), "under": r.get("undercut_m")}
    print(json.dumps({"K_top": res["K_top_max_disp_m"], "spill": {k: v for k, v in res["spill_vs_AS04F"].items() if not k.endswith("rows")},
                      "S8_p95": res["S8"]["dev_from_inner_face_m"]["p95"], "S8_inner": res["S8"]["first_hit_inner_face_share"],
                      "S10diff": res["S10_union_widths"]["diff"], "S4dent": res["S4_H_union_dent_m"],
                      "L2": lrec("2"), "L3": lrec("3"), "steps": g["steps"], "Hc_proxy_dent": g["Hc_proxy_dent_m"],
                      "L6label": {k: v["share_label_k"] for k, v in res["painting_label_consistency"].items()},
                      "sep": res.get("separation_summary"), "gate": res.get("gate_proxy"), "sec": res["seconds"]}, ensure_ascii=False, indent=0))
    if "--plot" in sys.argv:
        plot_sections(c, A, Y, c0, A0, Y0, lg, od + "/sections.png")


def plot_sections(c, A, Y, c0, A0, Y0, lg, out):
    import cv2
    import r2_common as R
    zp = np.load(B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
    Gp = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    Gs = R.keepout_grids(c, 3, 2, cache=B.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    cs = [-21.0, -19.5, -18.0, -16.8, -15.6, -14.4, -13.2, -12.0, -11.0, -10.0, -9.2, -8.4]
    W, H = 480, 330
    img = np.full((H * 3, W * 4, 3), 250, np.uint8)
    sc = 22.0
    for k, cc in enumerate(cs):
        i = int(np.argmin(np.abs(c - cc)))
        ox, oy = (k % 4) * W, (k // 4) * H
        def P(a, y):
            return (int(ox + W * 0.42 + a * sc), int(oy + H - 20 - y * sc))
        for G, col in ((Gs[i], (215, 215, 215)), (Gp[i], (150, 200, 250))):
            ys, xs = np.nonzero(G[::2, ::2])
            for yy, xx in zip(ys, xs):
                a = R.GA0 + xx * 2 * R.GRES; y = R.GY0 + yy * 2 * R.GRES
                q = P(a, y)
                if ox <= q[0] < ox + W and oy <= q[1] < oy + H:
                    img[q[1], q[0]] = col
        for AA, YY, col, t in ((A0, Y0, (160, 160, 160), 1), (A, Y, (40, 40, 200), 2)):
            pts = np.array([P(AA[i, j], YY[i, j]) for j in range(0, 400)], np.int32)
            cv2.polylines(img, [pts], False, col, t, cv2.LINE_AA)
        r = [x for x in lg["rows"] if x.get("row") == i]
        tx = "c %.2f" % c[i]
        if r:
            tx += " s %.2f L%d" % (r[0]["s"], r[0]["layer"])
        cv2.putText(img, tx, (ox + 6, oy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.line(img, P(-12, 0), P(10, 0), (120, 120, 120), 1)
        for yy in (0.4, 0.5):
            cv2.line(img, P(-12, yy * B.H0), P(-11, yy * B.H0), (0, 0, 0), 1)
    cv2.imwrite(out, img)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
