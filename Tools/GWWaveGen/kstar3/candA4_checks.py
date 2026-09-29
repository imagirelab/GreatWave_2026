# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: the new hard checks of Q21, measured the same way on any K*-format rows npz (400 x N).

Q21-1  no interior bulges / dents
  * silhouette band: vertices that form the painting-view outline (their image lies within 3 px of the coverage
    boundary) plus everything within 1.5 m on the surface of them.  "Interior" = the rest (y > 0.3 m, |c| <= 16).
  * low-order surface fit: per region (back 18-90, lip 90-200, underside/tube 200-314, face 314-379; rows c -18..+15,
    y > 0.3 m) a tensor cubic B-spline with 6 x 12 control points (u = column within the region, v = c) fitted to
    the 3-D positions of the interior vertices; report max / p99 of the distance.
  * 3 m sag: |X(c) - (X(c-1.5) + X(c+1.5)) / 2| per column; max / p99 over the interior (a smooth wave needs
    < ~0.15 m; a bump of 1 m over 3 m shows as ~0.5-1 m).
  * mean-curvature extrema: mean curvature H of the grid surface (smoothed 1 cell), count interior points that are a
    strict extremum in a +-1.2 m (c) x +-8 column window with |H| >= 0.15 /m and prominence >= 0.08 /m against the
    window mean (a round bump / dent; ridges along c such as the crest are not counted because they are not strict
    extrema along c).
Q21-2  fullness: section area above still water and A / H^2, back-normal shell thickness (median 0.2-0.8 H), back
    convex fraction and concave-foot extent, per big-wave row; volume above water.  Compared with the reference model's
    numbers (numbers-only file written by the TEMP model-side script: _model_side/ref_fullness.json).
Q21-3  b region: ridge contour and claw edge of the shoulder rows in the painting view vs the band's smoothed and raw
    edges (per-edge max / median px), and whether the band stays inside the silhouette.
usage: py -3.10 candA4_checks.py rows.npz out.json [--label name]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys, json, math
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter, maximum_filter, minimum_filter, uniform_filter
from scipy.interpolate import BSpline
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

HERE = os.path.dirname(os.path.abspath(__file__))
REF_FULL = r"G:\Unity\GreatWave_2026_Fresh\Unity\Build\Q20L3\candA4\_model_side\ref_fullness.json"
REGIONS = {"back": (18, 90), "lip": (90, 200), "under_tube": (200, 314), "face": (314, 379)}


def silhouette_band(c, A, Y, V1, fr, dist_m=1.5):
    X = fr.world(c, A, Y)
    tris = V1.triangles(A.shape[1], A.shape[0])
    cov = (V1.rasterize(fr.cam, X, tris) > 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(cov, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    dt = cv2.distanceTransform(1 - edge, cv2.DIST_L2, 5)
    P = fr.cam.project(X.reshape(-1, 3))
    xi = np.clip(np.round(P[:, 0]).astype(int), 0, 1919); yi = np.clip(np.round(P[:, 1]).astype(int), 0, 1079)
    inside = (P[:, 0] >= 0) & (P[:, 0] < 1920) & (P[:, 1] >= 0) & (P[:, 1] < 1080) & (P[:, 2] > 0)
    sil = (inside & (dt[yi, xi] <= 3.0)).reshape(A.shape)
    # grow by dist_m along the surface (grid neighbours, metric distance approx. by cell sizes)
    Xw = X
    du = np.linalg.norm(np.diff(Xw, axis=1), axis=-1); dv = np.linalg.norm(np.diff(Xw, axis=0), axis=-1)
    step = max(float(np.median(du[Y[:, 1:] > 0.3])), 0.05)
    k = max(int(round(dist_m / step)), 1)
    grown = cv2.dilate(sil.astype(np.uint8), np.ones((max(int(round(dist_m / max(np.median(dv[Y[1:] > 0.3]), 0.05))), 1) * 2 + 1, 2 * k + 1), np.uint8))
    return sil, grown.astype(bool), cov


def bspline_basis(x, n, deg=3):
    lo, hi = float(x.min()), float(x.max())
    inner = np.linspace(lo, hi, n - deg + 1)
    t = np.r_[[lo] * deg, inner, [hi] * deg]
    B = np.zeros((len(x), n))
    for k in range(n):
        cc = np.zeros(n); cc[k] = 1
        B[:, k] = BSpline(t, cc, deg, extrapolate=True)(np.clip(x, lo, hi))
    return B


def surface_fit(c, A, Y, interior, nu=6, nv=12):
    X = C.world(c, A, Y)
    out = {}
    rows = np.nonzero((c >= -18) & (c <= 15))[0]
    for name, (j0, j1) in REGIONS.items():
        rr, jj = np.meshgrid(rows, np.arange(j0, j1 + 1), indexing="ij")
        m = interior[rr, jj] & (Y[rr, jj] > 0.3)
        if m.sum() < 200:
            out[name] = None; continue
        u = (jj[m] - j0) / float(j1 - j0); v = c[rr[m]]
        Bu = bspline_basis(u, nu); Bv = bspline_basis(v, nv)
        Bm = (Bu[:, :, None] * Bv[:, None, :]).reshape(len(u), -1)
        P = X[rr[m], jj[m]]
        coef, *_ = np.linalg.lstsq(Bm, P, rcond=None)
        d = np.linalg.norm(Bm @ coef - P, axis=1)
        imax = int(np.argmax(d))
        out[name] = {"n": int(m.sum()), "max_m": float(d.max()), "p99_m": float(np.percentile(d, 99)), "p95_m": float(np.percentile(d, 95)),
                     "worst_c": float(v[imax]), "worst_col": int(jj[m][imax])}
    return out


def sag3m(c, A, Y, interior):
    X = C.world(c, A, Y)
    Xu = np.gradient(X, axis=1); Xv = np.gradient(X, c, axis=0)
    Nrm = np.cross(Xu, Xv); Nrm /= np.maximum(np.linalg.norm(Nrm, axis=-1), 1e-12)[..., None]
    rows = np.nonzero((c >= -18.5) & (c <= 14.5))[0]
    vals = []; per_c = []
    for r in rows:
        q = c[r]
        Xm = np.stack([np.stack([np.interp(q + dq, c, X[:, j, k]) for k in range(3)], -1) for dq in (-1.5, 1.5) for j in range(18, 380)], 0).reshape(2, -1, 3)
        # normal component only (a smooth sliding of the columns along the surface is not a bump)
        s = np.abs(((X[r, 18:380] - 0.5 * (Xm[0] + Xm[1])) * Nrm[r, 18:380]).sum(-1))
        ok = interior[r, 18:380] & (Y[r, 18:380] > 0.3)
        if ok.any():
            vals.append(s[ok]); per_c.append((float(q), float(s[ok].max()), int(18 + np.argmax(np.where(ok, s, -1)))))
    v = np.concatenate(vals)
    worst = sorted(per_c, key=lambda t: -t[1])[:8]
    return {"max_m": float(v.max()), "p99_m": float(np.percentile(v, 99)), "p95_m": float(np.percentile(v, 95)),
            "n_gt_0.3m": int((v > 0.3).sum()), "worst_c_col": worst}


def mean_curvature(c, A, Y):
    X = C.world(c, A, Y)
    Xu = np.gradient(X, axis=1); Xv = np.gradient(X, c, axis=0)
    Xuu = np.gradient(Xu, axis=1); Xvv = np.gradient(Xv, c, axis=0); Xuv = np.gradient(Xu, c, axis=0)
    n = np.cross(Xu, Xv); nn = np.linalg.norm(n, axis=-1); n = n / np.maximum(nn, 1e-12)[..., None]
    E = (Xu * Xu).sum(-1); F = (Xu * Xv).sum(-1); G = (Xv * Xv).sum(-1)
    L = (Xuu * n).sum(-1); M = (Xuv * n).sum(-1); N = (Xvv * n).sum(-1)
    den = 2 * (E * G - F * F)
    Hc = (E * N - 2 * F * M + G * L) / np.where(np.abs(den) > 1e-12, den, np.inf)
    return Hc


def curvature_extrema(c, A, Y, interior, thr=0.15, prom=0.08, win_c=1.2, win_j=8):
    Hc = mean_curvature(c, A, Y)
    Hs = gaussian_filter(np.nan_to_num(Hc), 1.0)
    dc = np.median(np.diff(c[(c > -18) & (c < 15)]))
    kr = max(int(round(win_c / dc)), 1)
    size = (2 * kr + 1, 2 * win_j + 1)
    mx = maximum_filter(Hs, size=size); mn = minimum_filter(Hs, size=size); mean = uniform_filter(Hs, size=size)
    ext = ((Hs >= mx - 1e-12) | (Hs <= mn + 1e-12)) & (np.abs(Hs) >= thr) & (np.abs(Hs - mean) >= prom)
    ok = interior & (Y > 0.3) & (c[:, None] >= -18) & (c[:, None] <= 15)
    # the tip cap (+-6 columns) and the sea contacts are features, not bulges
    ok[:, 194:207] = False
    ext = ext & ok
    rr, jj = np.nonzero(ext)
    pts = [(round(float(c[r]), 2), int(j), round(float(Hs[r, j]), 3)) for r, j in zip(rr, jj)]
    return {"count": int(len(pts)), "points_c_col_H": pts[:40], "thr_per_m": thr, "prominence_per_m": prom}


def fullness(c, A, Y, sil_grown=None):
    sys.path.insert(0, C.RUBRIC_TOOLS)
    import rubric_check as RC
    H = Y.max(1); r0 = int(np.argmin(np.abs(c))); H0 = H[r0]
    rows = {}
    for cc in np.arange(-8.0, 12.01, 1.0):
        r = int(np.argmin(np.abs(c - cc)))
        a, y = A[r], Y[r]
        area = RC.section_area(a, y)
        # back-normal shell thickness: from back points (0.2..0.8 H) along the inward normal to the next surface crossing
        jt = int(np.argmax(y[:200]))
        P = np.stack([a, y], -1)
        th = []
        for j in range(20, jt):
            if not (0.2 * H[r] <= y[j] <= 0.8 * H[r]):
                continue
            t = P[j + 1] - P[j - 1]; t /= np.linalg.norm(t) + 1e-12
            nrm = np.array([t[1], -t[0]])      # right of the travel = into the water on the back
            best = None
            for k in range(jt + 5, 395):
                p0, p1 = P[k], P[k + 1]
                d = p1 - p0
                Mx = np.array([[nrm[0], -d[0]], [nrm[1], -d[1]]])
                if abs(np.linalg.det(Mx)) < 1e-12:
                    continue
                s_, u_ = np.linalg.solve(Mx, p0 - P[j])
                if s_ > 0.05 and 0 <= u_ <= 1:
                    best = s_ if best is None else min(best, s_)
            if best is not None:
                th.append(best)
        # back convexity: signed curvature along the back (0.1 H .. 0.95 H)
        m = (y[:jt + 1] > 0.1 * H[r]) & (y[:jt + 1] < 0.95 * H[r])
        xb, yb = a[:jt + 1][m], y[:jt + 1][m]
        if len(xb) > 8:
            s = C.arclen(xb, yb); ss = np.arange(0, s[-1], 0.05)
            xx = gaussian_filter(np.interp(ss, s, xb), 6); yy = gaussian_filter(np.interp(ss, s, yb), 6)
            dx, dy = np.gradient(xx), np.gradient(yy); ddx, ddy = np.gradient(dx), np.gradient(dy)
            kap = (dx * ddy - dy * ddx) / np.maximum((dx * dx + dy * dy) ** 1.5, 1e-12)
            convex = float((kap < -0.002).mean()); concave_len = float((kap > 0.002).sum() * 0.05)
            concave_ext = float(np.ptp(xx[kap > 0.002])) if (kap > 0.002).any() else 0.0
        else:
            convex = concave_len = concave_ext = None
        rows["%+.0f" % cc] = {"c": float(c[r]), "H": float(H[r]), "area_m2": float(area), "area_over_H2": float(area / max(H[r], 1e-6) ** 2),
                              "shell_normal_median_over_H": float(np.median(th) / H[r]) if th else None,
                              "back_convex_fraction": convex, "back_concave_length_m": concave_len, "back_concave_a_extent_m": concave_ext}
    # volume above water over c -15..+15 (trapezoid over rows)
    ar = np.array([RC.section_area(A[r], Y[r]) for r in range(len(c))])
    m = (c >= -15) & (c <= 15)
    vol = float(np.trapezoid(ar[m], c[m]))
    ref = json.load(open(REF_FULL, encoding="utf-8")) if os.path.isfile(REF_FULL) else None
    return {"rows": rows, "volume_above_water_c_-15_15_m3": vol, "H0": float(H0), "reference": ref}


def band_check(c, A, Y, cov):
    import candA4_fit as F
    V1, tgt, fr = C.painting_frame()
    class _Ctx: pass
    cx = _Ctx(); cx.fr = fr
    X = fr.world(c, A, Y)
    rows = np.nonzero((c > -18.5) & (c < -3.5))[0]
    tp, bp = F.band_curves(cx, c, A, Y, X, rows)
    bt = json.load(open(os.path.join(HERE, "candA4_band_targets.json"), encoding="utf-8"))
    din = cv2.distanceTransform(cov.astype(np.uint8), cv2.DIST_L2, 5)
    out = {}
    for nm, cand, keys in (("top", tp, ("top_smooth", "top_raw")), ("bottom", bp, ("bottom_smooth", "bottom_raw"))):
        for k in keys:
            T = np.array(bt[k], float)
            r = F.curve_vs_target(cand, T, big=np.nan)
            cov_x = np.isfinite(r)
            v = np.abs(r[cov_x])
            out["%s_vs_%s" % (nm, k)] = {"max_px": float(v.max()) if len(v) else None, "median_px": float(np.median(v)) if len(v) else None,
                                          "p90_px": float(np.percentile(v, 90)) if len(v) else None,
                                          "target_samples": int(len(T)), "covered_samples": int(cov_x.sum())}
        m = np.isfinite(cand[:, 0])
        q = cand[m]
        inside = din[np.clip(np.round(q[:, 1]).astype(int), 0, 1079), np.clip(np.round(q[:, 0]).astype(int), 0, 1919)]
        out["%s_depth_inside_silhouette_px_min" % nm] = float(inside.min()) if len(inside) else None
    out["candidate_top_curve"] = [[round(float(x), 1), round(float(y), 1)] for x, y in tp if np.isfinite(x)]
    out["candidate_bottom_curve"] = [[round(float(x), 1), round(float(y), 1)] for x, y in bp if np.isfinite(x)]
    return out


def run(rows_path, out_path, label=None, band=True):
    z = np.load(rows_path); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    V1, tgt, fr = C.painting_frame()
    sil, grown, cov = silhouette_band(c, A, Y, V1, fr)
    interior = ~grown & (Y > 0.3) & (np.abs(c)[:, None] <= 16)
    res = {"rows": rows_path, "label": label,
           "silhouette_band": {"sil_vertices": int(sil.sum()), "band_vertices_1p5m": int(grown.sum()), "interior_vertices": int(interior.sum())},
           "Q21_1": {"surface_fit_6x12": surface_fit(c, A, Y, interior), "sag_3m": sag3m(c, A, Y, interior),
                     "mean_curvature_extrema": curvature_extrema(c, A, Y, interior)},
           "Q21_2": fullness(c, A, Y)}
    if band:
        res["Q21_3"] = band_check(c, A, Y, cov)
    json.dump(res, open(out_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return res


if __name__ == "__main__":
    lab = sys.argv[sys.argv.index("--label") + 1] if "--label" in sys.argv else None
    r = run(sys.argv[1], sys.argv[2], lab)
    q1 = r["Q21_1"]
    print(json.dumps({"surface_fit": {k: (None if v is None else [round(v["max_m"], 2), round(v["p99_m"], 2)]) for k, v in q1["surface_fit_6x12"].items()},
                      "sag": [round(q1["sag_3m"]["max_m"], 2), round(q1["sag_3m"]["p99_m"], 2), q1["sag_3m"]["n_gt_0.3m"]],
                      "Hext": q1["mean_curvature_extrema"]["count"]}))
