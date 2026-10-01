# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：試しの形を素早く測る（py -3.10）。関門（定義どおり＋σ12）、評審の膨らみ（j_bulge6）、3 m の撓み、
行の断面と視錐の跡の図。参照モデルは読まない。
usage: py -3.10 faceswap_probe.py <design.json> <work_dir> [--rows c1,c2,...] [--label L]"""
import os
import sys
import json
import time
import subprocess

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
import faceswap_build as FB  # noqa: E402
KC = F.KC
for p in (os.path.join(F.REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(F.REPO, "Tools", "GWWaveGen"), os.path.join(F.REPO, "Tools", "PaintingTruth")):
    if p not in sys.path:
        sys.path.insert(0, p)
J_BULGE = os.path.join(F.REPO, "Unity", "Build", "Q20L3", "judge_fid", "j_bulge6.py")


def q21_numbers(c, A, Y):
    import candA_common as C
    import candA4_checks as CK
    V1, tgt, fr = C.painting_frame()
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    interior = ~grown & (Y > 0.3) & (np.abs(c)[:, None] <= 16)
    s = CK.sag3m(c, A, Y, interior)
    out = {"sag3m_p99": s["p99_m"], "sag3m_max": s["max_m"], "sag3m_n_gt0p3": s["n_gt_0.3m"], "sag3m_worst": s["worst_c_col"][:4]}
    try:
        b = CK.band_check(c, A, Y, cov)
        out["band_top"] = {k: b["top_vs_top_smooth"][k] for k in ("median_px", "p90_px", "max_px", "covered_samples")}
        out["band_bottom"] = {k: b["bottom_vs_bottom_smooth"][k] for k in ("median_px", "p90_px", "max_px", "covered_samples")}
    except Exception as e:
        out["band"] = str(e)
    return out


def bulge(rows_npz, pref, label):
    r = subprocess.run([sys.executable, J_BULGE, pref, "%s=%s" % (label, rows_npz)], capture_output=True, text=True, timeout=900,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    d = json.load(open(pref + ".json"))[label]
    return {R: {"p99": round(d[R]["p99"], 3), "max": round(d[R]["max"], 3), "at": d[R]["max_at_row_col_c"],
                "regions": d[R]["regions_p99_max_gt0p3"]} for R in ("R4", "R6")}


def row_plots(c, A, Y, A0, Y0, lead_px, rows_c, path):
    import cv2
    ims = []
    for c0 in rows_c:
        r = int(np.argmin(abs(c - c0)))
        tr, _ = F.ray_row_trace(lead_px, c[r])
        p = F.Plot((-22, 18), (-1, 24), 520, 340, "row %d c=%.2f H %.2f -> %.2f" % (r, c[r], Y0[r].max(), Y[r].max()))
        p.line(A0[r], Y0[r], (170, 170, 170), 1)
        p.line(A[r], Y[r], (0, 0, 0), 1)
        p.line(tr[:, 0], tr[:, 1], (200, 160, 0), 1)
        for jj, col in ((18, (0, 160, 0)), (90, (0, 0, 255)), (150, (120, 0, 120)), (200, (255, 0, 0)), (314, (255, 0, 255))):
            p.dot(A[r, jj], Y[r, jj], col)
        jm = int(np.argmax(Y[r, :200]))
        p.dot(A[r, jm], Y[r, jm], (0, 200, 255), 4)
        ims.append(p.img)
    cv2.imwrite(path, F.grid_images(ims, 4))


def main():
    dpath, work = sys.argv[1], sys.argv[2]
    lab = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else "probe"
    rows_c = [float(x) for x in sys.argv[sys.argv.index("--rows") + 1].split(",")] if "--rows" in sys.argv else \
        [-22, -20, -18, -16, -14, -12, -10, -8, -6, -4, -2.5, 6]
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    d = FB.load_design(dpath)
    B = FB.Builder(d)
    c, A, Y = B.build()
    npz = os.path.join(work, lab + "_rows.npz")
    np.savez_compressed(npz, c=c, A=A, Y=Y)
    g = F.QuickGate()
    gate, cov = g.measure_rows(c, A, Y)
    res = {"label": lab, "design": dpath, "gate": gate}
    print("GATE", F.QuickGate.brief(gate), flush=True)
    res["bulge"] = bulge(npz, os.path.join(work, lab + "_bulge6"), lab)
    print("BULGE R4 %.3f/%.3f R6 %.3f/%.3f" % (res["bulge"]["R4"]["p99"], res["bulge"]["R4"]["max"], res["bulge"]["R6"]["p99"], res["bulge"]["R6"]["max"]),
          json.dumps(res["bulge"]["R6"]["regions"]), flush=True)
    res["q21"] = q21_numbers(c, A, Y)
    print("SAG p99 %.3f max %.3f n>0.3 %d" % (res["q21"]["sag3m_p99"], res["q21"]["sag3m_max"], res["q21"]["sag3m_n_gt0p3"]),
          "worst", res["q21"]["sag3m_worst"], flush=True)
    print("BAND", json.dumps({k: res["q21"].get(k) for k in ("band_top", "band_bottom")}), flush=True)
    H = Y.max(1)
    res["shape"] = {"H0": float(H[int(np.argmin(abs(c)))]), "Hmax": float(H.max()), "c_Hmax": float(c[int(np.argmax(H))]),
                    "top_col_off90": int(sum(1 for r in range(len(c)) if Y[r].max() > 1 and abs(int(np.argmax(Y[r, :200])) - 90) > 5))}
    print("SHAPE", res["shape"], flush=True)
    row_plots(c, A, Y, B.A0, B.Y0, B.lead_px, rows_c, os.path.join(work, lab + "_rows.png"))
    import cv2
    ov = (cov > 0.5)
    plate = cv2.imread(os.path.join(F.REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png"))
    img = (plate * 0.6).astype(np.uint8)
    img[ov] = (img[ov] * 0.5 + np.array([200, 120, 40]) * 0.5).astype(np.uint8)
    for k, col in (("78", (0, 255, 0)), ("130", (0, 255, 0)), ("131", (0, 255, 0)), ("132", (0, 255, 255)), ("72", (255, 0, 255))):
        P = F.outline_segments()[k]
        cv2.polylines(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], False, col, 1, cv2.LINE_AA)
    cv2.imwrite(os.path.join(work, lab + "_painting.png"), img[40:800, 100:1300])
    res["seconds"] = round(time.time() - t0, 1)
    json.dump(res, open(os.path.join(work, lab + "_probe.json"), "w", encoding="utf-8"), indent=1, default=float)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
