# -*- coding: utf-8 -*-
"""Q21 candidate A3b, step 1: global (whole-body, low-frequency) placement of the smoothed reference large forms.

The crest top of the smoothed model is put on the K* anchor (a = 0, c = 0, H0 = 20.75 m: the painted crest top on the
PaintingCam ray at K*'s depth, the seat / boats / motion rigs are built around it); its sea stays at y = 0.  The
remaining whole-body degrees of freedom (yaw about the vertical through the crest, horizontal stretch along a and
along c, a lean of a with height) are fitted to the painting outline 78/130/131/132 (72 is the lip / tube region and is
fitted later at the edges).  Writes the placement json and an overlay (temporary, model-derived -> _tmp).
usage: py -3.10 candA3b_place.py [--fit]
"""
import sys, os, json, math
import numpy as np
import cv2
from scipy.spatial import cKDTree
from scipy.optimize import minimize
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B
import fin2_warp as W


def crest_top(S):
    i = int(np.argmax(S[:, 1]))
    return S[i]


def transform(S, p, top):
    """crest-anchored whole-body transform: yaw th (deg), stretch sa (a), sc (c), lean k (a += k (y - H) ), global s."""
    th, sa, sc, k = p
    s = C.H0_KSTAR / top[1]
    a = S[:, 0] - top[0]; c = S[:, 2] - top[2]; y = S[:, 1]
    t = math.radians(th)
    ar = math.cos(t) * a - math.sin(t) * c
    cr = math.sin(t) * a + math.cos(t) * c
    ys = s * y
    return np.stack([s * sa * ar + k * (ys - C.H0_KSTAR), ys, s * sc * cr], -1)


def outline_cost(pt, V1, fr, S, tris, segs_keep=("78", "130", "131", "132"), ret=False):
    X = B.sec_to_world(S)
    cov, Bd = B.silhouette(V1, fr, X, tris)
    T = pt.T
    lm = pt.lm
    # target samples of the chosen segments: from start to the lip tip (78/130/131/132)
    Tsel = T[:lm["tip"] + 1]
    Tsel = Tsel[Tsel[:, 0] >= 250.0]          # left of x 250 the painted shoulder runs past the model's end (c < -16)
    d, _ = cKDTree(Bd).query(Tsel)
    cost = float(np.sqrt(np.mean(np.minimum(d, 200.0) ** 2)))
    if ret:
        return cost, cov, Bd, d
    return cost


def overlay(pt, cov, Bd, path, title):
    img = (np.dstack([cov * 90, cov * 90, cov * 90]) + 40).astype(np.uint8)
    cv2.polylines(img, [np.round(pt.T).astype(np.int32)], False, (0, 220, 255), 2)
    for p in Bd.astype(int):
        cv2.circle(img, tuple(p), 1, (60, 60, 255), -1)
    top, bot = B.band_edges()
    cv2.polylines(img, [np.round(top).astype(np.int32)], False, (0, 255, 0), 1)
    cv2.polylines(img, [np.round(bot).astype(np.int32)], False, (255, 120, 0), 1)
    cv2.putText(img, title, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
    cv2.imwrite(path, img)


def main():
    V1, tgt, fr = C.painting_frame()
    pt = W.Painting()
    S0, F = B.field_mesh(step=2)
    top = crest_top(S0)
    print("model crest top (model section frame)", top, "verts", len(S0))
    res = {}
    p0 = np.array([0.0, 1.0, 1.0, 0.0])
    cost, cov, Bd, d = outline_cost(pt, V1, fr, transform(S0, p0, top), F, ret=True)
    overlay(pt, cov, Bd, os.path.join(B.TMP, "place_p0.png"), "crest at O, H0, yaw 0: rms %.1f px" % cost)
    res["p0"] = {"p": p0.tolist(), "rms_px": cost}
    print("p0", cost)
    if "--fit" in sys.argv:
        f = lambda p: outline_cost(pt, V1, fr, transform(S0, p, top), F) + 20.0 * ((p[1] - 1) ** 2 + (p[2] - 1) ** 2) + 5.0 * p[3] ** 2
        best = None
        for th0 in (-20.0, -10.0, 0.0, 10.0, 20.0):
            r = minimize(f, np.array([th0, 1.0, 1.0, 0.0]), method="Nelder-Mead", options={"xatol": 0.05, "fatol": 0.05, "maxiter": 120, "initial_simplex": None})
            print("start", th0, r.x, r.fun, flush=True)
            if best is None or r.fun < best.fun:
                best = r
        cost, cov, Bd, d = outline_cost(pt, V1, fr, transform(S0, best.x, top), F, ret=True)
        overlay(pt, cov, Bd, os.path.join(B.TMP, "place_fit.png"), "fit yaw %.1f sa %.2f sc %.2f lean %.2f: rms %.1f px" % (*best.x, cost))
        res["fit"] = {"p": best.x.tolist(), "rms_px": cost, "p95_px": float(np.percentile(d, 95)), "max_px": float(d.max())}
    res["model_top_model_frame"] = top.tolist()
    json.dump(res, open(os.path.join(B.TMP, "placement.json"), "w"), indent=1)
    print(json.dumps(res))


if __name__ == "__main__":
    main()
