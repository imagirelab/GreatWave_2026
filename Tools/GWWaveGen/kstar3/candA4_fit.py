# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: fit the low-DOF parametric sculpt to the painting BY ITS EDGES.

Only the B-spline control values of the section parameters move (a handful per parameter along the crest), so the
fit can change the large forms but cannot put a bump into the interior of the surface.  The residual vector:
  * gate outline 78/130/131/132/72: signed distance (px) from each target point to the candidate's painting-view
    coverage boundary (coverage sdf sampled at the target points; the target is the half-width compensated envelope,
    as for K*),
  * spill / holes: probe points in the painted sky (the tube opening and above the outline) that the candidate must not
    cover, and probe points just inside the painted wave near the outline that it must cover,
  * b region (Q21-3): the second crest's ridge contour and claw edge, taken per shoulder row from the projected lip
    chain (ridge = local minimum of the image height between the valley and the tip, claw = the tip's lowest image
    point), against the band's smoothed top / bottom edges,
  * regularisation toward the initial proportions (reference-model ranges) and smoothness of the control values.
The Jacobian is a parallel finite difference (multiprocessing).
usage: py -3.10 candA4_fit.py design_in.json design_out.json stage [--iters N]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")      # one BLAS thread: keeps the commit charge of the parallel workers small
import sys, json, math, time
import numpy as np
import cv2
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA4_model as M

HORIZON = 787.7
HERE = os.path.dirname(os.path.abspath(__file__))

# typical scale of each parameter (for regularisation and FD steps)
SCALE = {"H": 1.0, "aT": 1.0, "ea": 0.05, "eb": 0.05, "thb": 6.0, "rf": 0.04, "r1": 0.03, "t1": 6.0, "r2": 0.08, "t2": 6.0,
         "r3": 0.03, "t3": 8.0, "r4": 0.03, "t4": 10.0, "r5": 0.02, "t5": 8.0, "rt": 0.05, "tc": 15.0, "k0": 0.08, "k1": 0.08,
         "bx": 0.04, "by": 0.04, "rR": 0.03, "e2c": 0.04, "e2s": 0.04, "e3c": 0.03, "e3s": 0.03, "phj": 8.0, "phe": 8.0,
         "lr": 0.08, "dt": 0.03, "dsea": 0.2, "fb": 0.5}
BOUNDS = {"H": (0.0, 24.0), "aT": (-16, 6), "ea": (0.2, 0.9), "eb": (0.5, 0.95), "thb": (50, 89), "rf": (0.03, 0.5),
          "r1": (0.05, 0.6), "t1": (5, 80), "r2": (0.05, 2.0), "t2": (0, 80), "r3": (0.02, 0.6), "t3": (0, 110),
          "r4": (0.03, 0.5), "t4": (0, 150), "r5": (0.02, 0.4), "t5": (0, 120), "rt": (0.08, 0.5), "tc": (90, 200),
          "k0": (0.1, 0.8), "k1": (0.1, 0.8), "bx": (-0.3, 0.8), "by": (-0.1, 0.8), "rR": (0.1, 0.6),
          "e2c": (-0.2, 0.2), "e2s": (-0.2, 0.2), "e3c": (-0.12, 0.12), "e3s": (-0.12, 0.12), "phj": (10, 120),
          "phe": (-20, 40), "lr": (0.1, 1.2), "dt": (0.03, 0.4), "dsea": (-2, 0), "fb": (1.5, 9.0)}


class Ctx:
    def __init__(self):
        import fin2_warp as W
        self.pt = W.Painting()
        self.V1, self.tgt, self.fr = self.pt.V1, self.pt.tgt, self.pt.fr
        self.c = M.c_rows()
        self.tris = self.V1.triangles(M.NU, M.NV)
        T = self.pt.T; lm = self.pt.lm
        self.T = T
        lab = np.empty(len(T), object)
        lab[:lm["j78_130"]] = "78"; lab[lm["j78_130"]:lm["j130_131"]] = "130"; lab[lm["j130_131"]:lm["top"]] = "131"
        lab[lm["top"]:lm["tip"]] = "132"; lab[lm["tip"]:] = "72"
        self.Tlab = lab
        # probes
        Hh, Ww = 1080, 1920
        g = np.mgrid[0:Hh:5, 0:Ww:5].reshape(2, -1).T[:, ::-1].astype(float)
        s = self.tgt.sample(g, comp=True)
        from scipy.spatial import cKDTree
        d, _ = cKDTree(T).query(g)
        infr = (g[:, 0] > self.tgt.x0 + 2) & (g[:, 0] < self.tgt.x1) & (g[:, 1] < 735)
        # painted sky: near the outline densely, and the whole sky of the scored frame above the horizon sparsely
        # (the tube opening down to the horizon and the sky over the shoulder must stay empty)
        g8 = np.mgrid[0:int(HORIZON):8, 0:Ww:8].reshape(2, -1).T[:, ::-1].astype(float)
        s8 = self.tgt.sample(g8, comp=True)
        in8 = (g8[:, 0] > self.tgt.x0 + 2) & (g8[:, 0] < self.tgt.x1)
        self.sky = np.vstack([g[infr & (s > 5) & (d < 70)], g8[in8 & (s8 > 8)]])
        self.wav = g[infr & (s < -5) & (d < 35)]
        bt = json.load(open(os.path.join(HERE, "candA4_band_targets.json"), encoding="utf-8"))
        self.band_top = np.array(bt["top_smooth"], float); self.band_bot = np.array(bt["bottom_smooth"], float)
        self.sag_c = np.arange(-20.0, 12.51, 0.5)
        self.mono_rows = np.nonzero((self.c > -17.5) & (self.c < 13.8))[0][::2]

    def cov_sdf(self, c, A, Y):
        X = self.fr.world(c, A, Y)
        r0 = int(np.searchsorted(c, -19.0))
        Xs = X[r0:]
        if not hasattr(self, "tris_s") or self.tris_s[0] != r0:
            self.tris_s = (r0, self.V1.triangles(A.shape[1], A.shape[0] - r0))
        cov = (self.V1.rasterize(self.fr.cam, Xs, self.tris_s[1]) > 0.5).astype(np.uint8)
        din = cv2.distanceTransform(cov, cv2.DIST_L2, 5)
        dout = cv2.distanceTransform(1 - cov, cv2.DIST_L2, 5)
        return dout - din, cov, X      # >0 outside the candidate


def bilin(img, P):
    x = np.clip(P[:, 0], 0, img.shape[1] - 1.001); y = np.clip(P[:, 1], 0, img.shape[0] - 1.001)
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
    return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def band_curves(ctx, c, A, Y, X, rows):
    """per shoulder row: image of the ridge contour (local min of image y on the lip chain between the valley and the tip)
    and of the claw edge (max image y around the tip).  returns arrays (n,2) (NaN where the row has no ridge)."""
    top, bot = [], []
    for r in rows:
        P = ctx.fr.cam.project(X[r, 88:216].reshape(-1, 3))[:, :2]
        yv = P[:, 1]
        jt = 200 - 88
        # valley = max image y between the crest top and the ridge; ridge = min image y after the valley, before the tip
        seg = yv[:jt + 1]
        kv = None
        for k in range(4, jt - 4):
            if seg[k] >= seg[max(k - 4, 0):k + 5].max() - 1e-9 and seg[k] > seg[0] + 1.0:
                kv = k; break
        if kv is None:
            top.append([np.nan, np.nan])
        else:
            kr = kv + int(np.argmin(seg[kv:]))
            top.append(P[kr] if kr < jt - 1 and seg[kr] < seg[kv] - 0.5 else [np.nan, np.nan])
        kb = jt - 12 + int(np.argmax(yv[jt - 12:jt + 16]))
        bot.append(P[kb])
    return np.array(top, float), np.array(bot, float)


def curve_vs_target(cand, tgt, big=40.0):
    """vertical distance of each target sample to the candidate image curve (interpolated in x); big where not covered."""
    m = np.isfinite(cand[:, 0])
    if m.sum() < 2:
        return np.full(len(tgt), big)
    cx, cy = cand[m, 0], cand[m, 1]
    o = np.argsort(cx); cx, cy = cx[o], cy[o]
    out = np.interp(tgt[:, 0], cx, cy) - tgt[:, 1]
    outside = (tgt[:, 0] < cx[0] - 3) | (tgt[:, 0] > cx[-1] + 3)
    out[outside] = big
    return out


class Problem:
    def __init__(self, ctx, design, active, weights, reg_ref=None):
        self.ctx = ctx
        self.d = design
        self.active = active            # list of (name, site_index)
        self.w = weights
        self.ref = {k: design.vals[k].copy() for k in M.PARAMS} if reg_ref is None else reg_ref
        self.x0 = np.array([design.vals[n][i] for n, i in active])

    def set(self, x):
        for (n, i), v in zip(self.active, x):
            self.d.vals[n][i] = v

    def rows(self, x):
        self.set(x)
        A, Y, inf = M.build(self.d, self.ctx.c)
        return A, Y, inf

    def residual(self, x, detail=False):
        ctx = self.ctx; w = self.w
        A, Y, inf = self.rows(x)
        sdf, cov, X = ctx.cov_sdf(ctx.c, A, Y)
        res = []; info = {}
        rT = bilin(sdf, ctx.T)
        for k in ("78", "130", "131", "132", "72"):
            m = ctx.Tlab == k
            res.append(w.get("gate_" + k, 1.0) * rT[m]); info[k] = rT[m]
        rs = np.maximum(0.0, -bilin(sdf, ctx.sky))          # spill depth into the painted sky
        rw = np.maximum(0.0, bilin(sdf, ctx.wav))           # hole depth inside the painted wave
        res.append(w.get("spill", 0.5) * rs); res.append(w.get("hole", 0.3) * rw)
        info["spill"] = rs; info["hole"] = rw
        if w.get("band", 0) > 0:
            rows = np.nonzero((ctx.c > -18.5) & (ctx.c < -3.5))[0]
            tp, bp = band_curves(ctx, ctx.c, A, Y, X, rows)
            rt = curve_vs_target(tp, ctx.band_top); rb = curve_vs_target(bp, ctx.band_bot)
            res.append(w["band"] * rt); res.append(w["band"] * rb); info["band_top"] = rt; info["band_bot"] = rb
        # section validity: shell thickness / self-intersection proxies (per row, cheap)
        pen = []
        for r in np.nonzero((ctx.c > -30) & (ctx.c < 13.8))[0][::3]:
            a, y = A[r], Y[r]
            if y.max() < 3.0:
                pen.append(0.0); continue
            # the inner curve (cols 214..379) must stay below/behind the outer curve (cols 18..186): min distance
            O = np.stack([a[18:186], y[18:186]], -1); I = np.stack([a[214:379], y[214:379]], -1)
            dmin = np.min(np.linalg.norm(O[:, None, :] - I[None, ::3, :], axis=-1))
            pen.append(max(0.0, 0.08 * Y[r].max() - dmin))
        res.append(w.get("valid", 30.0) * np.array(pen))
        # anti-bulge (Q21-1): sag of every column over a 3 m span across the rows, beyond what a smooth wave needs
        if w.get("sag", 0) > 0:
            X3 = C.world(ctx.c, A, Y)
            cs = ctx.sag_c
            Xi = np.stack([np.stack([np.interp(q, ctx.c, X3[:, j, k]) for k in range(3)], -1) for j in range(18, 395, 3) for q in (cs - 1.5, cs, cs + 1.5)], 0)
            Xi = Xi.reshape(-1, 3, len(cs), 3)
            sag = np.linalg.norm(Xi[:, 1] - 0.5 * (Xi[:, 0] + Xi[:, 2]), axis=-1)
            yok = Xi[:, 1, :, 1] > 0.3
            res.append(w["sag"] * np.where(yok, np.maximum(0.0, sag - 0.15), 0.0).ravel() / 0.05)
        if w.get("mono", 0) > 0:
            Hc = np.array([Y[r].max() for r in ctx.mono_rows])
            dH = np.diff(Hc)
            cm = ctx.c[ctx.mono_rows][1:]
            bad = np.where(cm <= -1.0, np.maximum(0.0, -dH), np.where(cm >= 1.5, np.maximum(0.0, dH), 0.0))
            res.append(w["mono"] * bad / 0.02)
        # regularisation toward the reference proportions and smoothness along c
        reg = []
        for (n, i), v in zip(self.active, x):
            reg.append(w.get("reg", 1.0) * (v - self.ref[n][i]) / SCALE[n])
        names = sorted(set(n for n, i in self.active))
        for n in names:
            v = self.d.vals[n]; s = self.d.sites[n]
            for i in range(1, len(v) - 1):
                h0, h1 = s[i] - s[i - 1], s[i + 1] - s[i]
                d2 = ((v[i + 1] - v[i]) / h1 - (v[i] - v[i - 1]) / h0) / (0.5 * (h0 + h1))
                reg.append(w.get("smooth", 1.0) * d2 * 2.0 / SCALE[n])
        res.append(np.array(reg))
        r = np.concatenate([np.atleast_1d(q) for q in res])
        if detail:
            return r, info, (A, Y, cov)
        return r


# ------------------------------------------------------------------ parallel FD Jacobian
_G = {}


def _init(design_json, active, weights, ref):
    ctx = Ctx()
    d = M.Design(design_json)
    _G["p"] = Problem(ctx, d, active, weights, reg_ref={k: np.array(v) for k, v in ref.items()})


def _eval(args):
    x = args
    return _G["p"].residual(np.array(x))


def fit(design, active, weights, iters=8, workers=10, log=lambda *a: print(*a, flush=True), ref=None, ckpt=None):
    import multiprocessing as mp
    ctx = Ctx()
    ref = ref or {k: design.vals[k].copy() for k in M.PARAMS}
    prob = Problem(ctx, design, active, weights, reg_ref=ref)
    x = prob.x0.copy()
    lo = np.array([BOUNDS[n][0] for n, i in active]); hi = np.array([BOUNDS[n][1] for n, i in active])
    x = np.clip(x, lo, hi)
    steps = np.array([0.35 * SCALE[n] for n, i in active])
    pool = mp.Pool(workers, initializer=_init, initargs=(design.to_json(), active, weights, {k: list(map(float, v)) for k, v in ref.items()}))
    lam = 1.0
    r = prob.residual(x); f = 0.5 * r @ r
    log("start cost %.1f  n_res %d  n_par %d" % (f, len(r), len(x)))
    t0 = time.time()
    for it in range(iters):
        xs = []
        for k in range(len(x)):
            xp = x.copy(); xp[k] = min(xp[k] + steps[k], hi[k]) if xp[k] + steps[k] <= hi[k] else xp[k] - steps[k]
            xs.append(xp)
        R = pool.map(_eval, [list(q) for q in xs])
        J = np.stack([(R[k] - r) / (xs[k][k] - x[k]) for k in range(len(x))], 1)
        g = J.T @ r; Hm = J.T @ J
        improved = False
        for _ in range(6):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-6), g)
            xn = np.clip(x + dx, lo, hi)
            rn = prob.residual(xn); fn = 0.5 * rn @ rn
            if fn < f:
                x, r, f = xn, rn, fn; lam = max(lam / 3, 1e-4); improved = True
                break
            lam *= 4
        log("it %d cost %.1f lam %.3g %s  %.0fs" % (it, f, lam, "" if improved else "(no step)", time.time() - t0))
        if ckpt:
            prob.set(x); json.dump(prob.d.to_json(), open(ckpt, "w", encoding="utf-8"), indent=1)
        if not improved and lam > 1e4:
            break
    pool.close(); pool.join()
    prob.set(x)
    return design, prob


def summary(prob, x=None):
    x = prob.x0 if x is None else x
    r, info, (A, Y, cov) = prob.residual(np.array([prob.d.vals[n][i] for n, i in prob.active]), detail=True)
    s = {}
    for k in ("78", "130", "131", "132", "72"):
        v = np.abs(info[k]); s[k] = [round(float(v.max()), 2), round(float(np.percentile(v, 95)), 2), round(float(np.median(v)), 2)]
    s["spill_max"] = round(float(info["spill"].max()), 2); s["hole_max"] = round(float(info["hole"].max()), 2)
    s["spill_n>2"] = int((info["spill"] > 2).sum()); s["hole_n>2"] = int((info["hole"] > 2).sum())
    for k in ("band_top", "band_bot"):
        if k in info:
            v = np.abs(info[k]); s[k] = [round(float(v.max()), 1), round(float(np.median(v)), 1)]
    return s, A, Y


ALLP = ["H", "r1", "t1", "r2", "t2", "r3", "t3", "r4", "t4", "t5", "bx", "by", "rR", "e2c", "e2s", "phj"]
STAGES = {
    "tip": dict(params={k: (-2.5, 3.5) for k in ("r2", "t2", "r3", "t3", "r4", "t4", "r5", "t5", "tc", "rt", "k0", "k1", "phj", "bx", "by", "rR")},
                weights={"band": 0.5, "gate_72": 3.0, "gate_132": 3.0, "spill": 2.0, "hole": 1.0, "reg": 0.15, "smooth": 0.5, "sag": 1.0, "mono": 1.0}),
    "far72": dict(params={k: (0.5, 12.5) for k in ("H", "r1", "t1", "r2", "t2", "t3", "r4", "t4", "t5", "bx", "by", "rR", "e2c", "e2s", "phj")},
                  weights={"band": 0.5, "gate_72": 3.0, "gate_132": 1.5, "spill": 2.0, "hole": 1.0, "reg": 0.5, "smooth": 1.0, "sag": 1.0, "mono": 1.0}),
    "band2": dict(params={k: (-18, -6.5) for k in ("H", "r1", "t1", "r2", "t2", "r3", "t3", "r4", "t4", "t5", "bx", "by", "rR")},
                  weights={"band": 1.0, "gate_72": 1.0, "spill": 1.0, "hole": 0.5, "reg": 1.0, "smooth": 1.0, "sag": 1.0, "mono": 1.0}),
    "joint": dict(params={k: (-22, 15.5) for k in ALLP},
                  weights={"gate_72": 1.0, "spill": 1.0, "hole": 0.5, "reg": 0.5, "smooth": 1.0, "sag": 1.0, "mono": 1.0}),
    "jointband": dict(params={k: (-22, 15.5) for k in ALLP},
                  weights={"band": 1.0, "gate_72": 1.0, "spill": 1.0, "hole": 0.5, "reg": 0.5, "smooth": 1.0, "sag": 1.0, "mono": 1.0}),
    "jointsparse": dict(params={k: (-22, 14.5) for k in ALLP},
                  weights={"band": 1.0, "gate_72": 1.5, "gate_132": 1.5, "spill": 1.5, "hole": 0.7, "reg": 0.3, "smooth": 2.0, "sag": 1.5, "mono": 1.0}),
    # crest line (78/130/131) by the heights of the shoulder rows and the crest arc
    "crest": dict(params={"H": (-28, 3.5), "r1": (-22, 2)}, weights={"gate_132": 0.3, "gate_72": 0.0, "spill": 0.3, "hole": 0.3, "reg": 0.3, "smooth": 1.0}),
    # main lip (132) and the tip / underside (72 top)
    "lip": dict(params={"H": (-4.5, 3.5), "aT": (0.5, 3.5), "r1": (-4.5, 3.5), "t1": (-4.5, 3.5), "r2": (-4.5, 3.5), "t2": (-4.5, 3.5),
                        "r3": (-4.5, 3.5), "t3": (-4.5, 3.5), "r4": (-4.5, 3.5), "t4": (-4.5, 3.5), "r5": (-4.5, 3.5), "t5": (-4.5, 3.5),
                        "tc": (-4.5, 3.5)}, weights={"gate_72": 0.5, "spill": 0.5, "hole": 0.3, "reg": 0.3, "smooth": 1.0}),
    # far part / barrel: 72 and the tube opening (no spill)
    "far": dict(params={"H": (2, 15.5), "bx": (2, 15.5), "by": (2, 15.5), "rR": (2, 15.5), "e2c": (2, 15.5), "e2s": (2, 15.5),
                        "r1": (2, 15.5), "t1": (2, 15.5), "r2": (2, 15.5), "t2": (2, 15.5), "t3": (2, 15.5), "t4": (2, 15.5),
                        "t5": (2, 15.5), "phj": (2, 15.5)},
                weights={"gate_72": 1.0, "spill": 1.0, "hole": 0.5, "reg": 0.5, "smooth": 1.5}),
    # b region: lip chain of the shoulder rows against the band edges (+ the silhouette stays)
    "band": dict(params={"H": (-22, -4.5), "t1": (-22, -4.5), "r2": (-22, -4.5), "t2": (-22, -4.5), "r3": (-22, -4.5), "t3": (-22, -4.5),
                         "r4": (-22, -4.5), "t4": (-22, -4.5), "t5": (-22, -4.5)},
                 weights={"band": 1.0, "gate_132": 0.3, "gate_72": 0.3, "spill": 0.5, "hole": 0.3, "reg": 0.3, "smooth": 1.0}),
}


def active_for(design, spec):
    act = []
    for n, (c0, c1) in spec.items():
        s = design.sites[n]
        for i, v in enumerate(s):
            if c0 - 1e-9 <= v <= c1 + 1e-9:
                act.append((n, i))
    return act


if __name__ == "__main__":
    din, dout, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 8
    d = M.load_design(din)
    st = STAGES[stage]
    act = active_for(d, st["params"])
    d, prob = fit(d, act, st["weights"], iters=iters, ckpt=dout + ".ckpt.json")
    s, A, Y = summary(prob)
    print(json.dumps(s))
    out = d.to_json(); out["fit_log"] = {"stage": stage, "summary": s}
    json.dump(out, open(dout, "w", encoding="utf-8"), indent=1)
