# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: quick diagnostics of a design or a rows npz.
  * sections at chosen c over the painting-view allowed region (fin_allowed) with landmarks,
  * painting-view coverage overlay with the target outline and the b-region band edges.
usage: py -3.10 candA4_view.py (design.json | rows.npz) out_prefix
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")      # one BLAS thread: keeps the commit charge of the parallel workers small
import sys, json, math
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA4_model as M
import fin_allowed as FA

WORK = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\Q20L3\candA4\_work"


def load_rows(path):
    if path.endswith(".json"):
        d = M.load_design(path); c = M.c_rows(); A, Y, inf = M.build(d, c)
        return c, A, Y
    z = np.load(path); return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def fig_sections(c, A, Y, out, cs=(-16, -13, -10, -7, -4.5, -2, 0, 1.5, 3, 4.5, 6, 8, 10, 12), extra=None):
    V1, tgt, fr = C.painting_frame()
    Wt, Ht = 440, 300
    ncol = 4
    img = np.full(((len(cs) + ncol - 1) // ncol * (Ht + 4) + 24, ncol * Wt, 3), 255, np.uint8)
    for i, c0 in enumerate(cs):
        aa, yy, ok, s = FA.allowed_grid(fr, tgt, c0, a_rng=(-22.0, 22.0), y_rng=(-6.0, 24.0), res=0.1)
        tile = np.where(ok[::-1, :, None], np.array([238, 228, 214], np.uint8), np.array([252, 252, 252], np.uint8))
        tile = cv2.resize(tile, (Wt, Ht), interpolation=cv2.INTER_NEAREST)
        def px(a, y):
            return np.stack([(a - aa[0]) / (aa[-1] - aa[0]) * (Wt - 1), (yy[-1] - y) / (yy[-1] - yy[0]) * (Ht - 1)], -1)
        for g in range(-20, 21, 5):
            x = int(px(np.array([g]), np.array([0]))[0, 0]); cv2.line(tile, (x, 0), (x, Ht), (225, 225, 225), 1)
        for g in range(-5, 25, 5):
            y = int(px(np.array([0]), np.array([g]))[0, 1]); cv2.line(tile, (0, y), (Wt, y), (190, 190, 230) if g == 0 else (225, 225, 225), 1)
        if extra is not None:
            for (ce, Ae, Ye, col) in extra:
                r = int(np.argmin(np.abs(ce - c0)))
                if abs(ce[r] - c0) < 0.4:
                    cv2.polylines(tile, [px(Ae[r], Ye[r]).round().astype(np.int32)], False, col, 1, cv2.LINE_AA)
        r = int(np.argmin(np.abs(c - c0)))
        q = px(A[r], Y[r]).round().astype(np.int32)
        cv2.polylines(tile, [q], False, (30, 30, 200), 2, cv2.LINE_AA)
        for j, col in ((18, (0, 150, 0)), (90, (200, 0, 0)), (200, (0, 0, 0)), (314, (200, 0, 200)), (379, (0, 140, 255)), (394, (0, 150, 0))):
            cv2.circle(tile, tuple(q[j]), 3, col, -1)
        cv2.putText(tile, "c=%+.1f H=%.1f" % (c[r], Y[r].max()), (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        ox = (i % ncol) * Wt; oy = 24 + (i // ncol) * (Ht + 4)
        img[oy:oy + Ht, ox:ox + Wt] = tile
    cv2.putText(img, "A4 sections (red) over the painting-view allowed region (beige); grid 5 m; dots: jB green, top blue, tip black, corner magenta, facebot orange", (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1)
    cv2.imwrite(out, img)


def band_targets():
    d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "candA4_band_targets.json"), encoding="utf-8"))
    return {k: np.array(v, float) for k, v in d.items() if isinstance(v, list)}


def fig_painting(c, A, Y, out, crop=(100, 0, 1300, 900), scale=0.8):
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y)
    tris = V1.triangles(A.shape[1], A.shape[0])
    cov = V1.rasterize(fr.cam, X, tris) > 0.5
    base = cv2.imread(os.path.join(WORK, "painting_disp.png"))
    img = (base * 0.55 + 255 * 0.45).astype(np.uint8)
    over = img.copy(); over[cov] = (0.5 * img[cov] + 0.5 * np.array([150, 110, 60])).astype(np.uint8)
    img = over
    cn, _ = cv2.findContours(cov.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(img, cn, -1, (30, 30, 200), 1, cv2.LINE_AA)
    import fin2_warp as W
    pt = W.Painting()
    cv2.polylines(img, [pt.T.round().astype(np.int32)], False, (0, 170, 0), 1, cv2.LINE_AA)
    bt = band_targets()
    for k, col in (("top_smooth", (200, 0, 200)), ("bottom_smooth", (120, 0, 220))):
        if k in bt:
            cv2.polylines(img, [bt[k].round().astype(np.int32)], False, col, 1, cv2.LINE_AA)
    # projected crest line (col 90), tip line (col 200), corner (314)
    for j, col in ((90, (255, 0, 0)), (200, (0, 0, 0)), (314, (200, 0, 200))):
        P = fr.cam.project(X[:, j].reshape(-1, 3))[:, :2]
        m = Y[:, j] > 0.3
        cv2.polylines(img, [P[m].round().astype(np.int32)], False, col, 1, cv2.LINE_AA)
    # detected b-region edges of the candidate (ridge contour / claw edge per shoulder row)
    try:
        import candA4_fit as F
        class _Ctx: pass
        cx = _Ctx(); cx.fr = fr
        rows = np.nonzero((c > -18.5) & (c < -3.5))[0]
        tp, bp = F.band_curves(cx, c, A, Y, X, rows)
        for P, col in ((tp, (255, 0, 255)), (bp, (160, 0, 255))):
            for q in P:
                if np.isfinite(q[0]):
                    cv2.circle(img, (int(round(q[0])), int(round(q[1]))), 2, col, -1)
    except Exception as e:
        print("band overlay failed", e)
    x0, y0, x1, y1 = crop
    img = img[y0:y1, x0:x1]
    img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(out, img)


if __name__ == "__main__":
    c, A, Y = load_rows(sys.argv[1])
    pre = sys.argv[2]
    F = np.load(r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\Q20\final\kstarF_a45_rows.npz")
    fig_sections(c, A, Y, pre + "_sections.png", extra=[(F["c"], F["A"], F["Y"], (160, 160, 160))])
    fig_painting(c, A, Y, pre + "_painting.png")
    print(pre)
