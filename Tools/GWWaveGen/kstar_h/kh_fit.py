# -*- coding: utf-8 -*-
"""候補 H1：Houdini のネットワークの母数（CTRL の ramp の鍵）を原画に合わせる最適化（py -3.10）。

形は kh_design（Houdini の Python SOP と同じ式）で作り、原画視点の評価は round 3 の道具（candA4_fit.Ctx：
被覆の符号付き距離を目標の輪郭の点で読む、空のはみ出し・波の中の穴の探り、b 区域の帯の縁）を読み取り専用で使う。
動かすのは「原画視点で輪郭を作る縁」を動かす母数だけ（頂の高さ・頂の a・唇と鉤・管、b 区域の稜、側の縁の帯の ramp）。
中の形の母数（殻の厚み・背・足・谷）は参照の比率へ正則化し、鍵の値の 2 階差（なめらかさ）も罰する。
Q21-1（中の膨らみ・凹みがない）のために、3 m の撓み（c 方向）が 0.15 m を超える分も罰する。
ヤコビアンは差分を並列（multiprocessing）で求め、Levenberg–Marquardt で進む。
usage: py -3.10 kh_fit.py design_in.json design_out.json STAGE [--iters N] [--workers N]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import math
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"))
import numpy as np  # noqa: E402
import kh_design as D  # noqa: E402

LARGE_FORM = True
FD_STEP = 1.0          # finite-difference step in units of SCALE (0.35 was below the raster noise for the lip controls)

SCALE = {"crest_height": 0.3, "crest_a": 0.3, "tube_radius": 0.02, "tube_oval": 0.03, "lean": 3.0, "shell_top": 0.02,
         "shell_back": 0.02, "shell_base": 0.03, "back_low": 4.0, "foot_spread": 0.03, "tip_angle": 4.0, "hook_depth": 0.015,
         "hook_span": 8.0, "lip_len": 4.0, "lip_thick": 0.01, "tip_round": 0.05, "tube_end": 5.0, "trough_depth": 0.02,
         "trough_reach": 0.03, "trough_len": 0.04, "ledge_amp": 0.2, "ledge_pos": 0.04, "ledge_width": 0.02,
         "edge_top": 0.08, "edge_lip": 0.08, "edge_hook": 0.08}


class Ctx:
    def __init__(self):
        import candA4_fit as F
        self.F = F
        self.base = F.Ctx()           # painting targets, sky / wave probes, band targets (read-only round-3 code)
        self.c = D.c_rows()
        self.sag_c = np.arange(-19.0, 13.51, 0.5)
        import kh_gate_lf as KG
        from scipy.spatial import cKDTree
        self.Tlab = self.base.Tlab
        # large-form targets (coordinator decision 2026-09-28 20:00): 132 / 72 smoothed along the line (sigma 12 px);
        # the claw bumps and notches are matched later by the stage-6 claw meshes
        self.T = KG.fit_targets(self.base.T, self.base.Tlab) if LARGE_FORM else self.base.T
        # sky / wave probes: drop those within 20 px of the 132 / 72 target line (they would pin the claw detail)
        m = np.isin(self.Tlab, ("132", "72"))
        kd = cKDTree(self.T[m])
        # + painted sky between the end of the 72 target (display y 735) and the horizon, left of the boats (the foot and
        #   the front face must not stick out into the dark sky behind the wave)
        g = np.mgrid[736:786:4, 850:1100:4].reshape(2, -1).T[:, ::-1].astype(float)
        sg = self.base.tgt.sample(g, comp=True)
        extra = g[sg > 5]
        sky = np.vstack([self.base.sky, extra])
        # + painted wave up to 90 px inside the outline (holes seen through under the barrel), y < 735
        gw = np.mgrid[0:735:5, 160:1760:5].reshape(2, -1).T[:, ::-1].astype(float)
        sw = self.base.tgt.sample(gw, comp=True)
        dT = cKDTree(self.base.T).query(gw)[0]
        self.base.wav = np.vstack([self.base.wav, gw[(sw < -5) & (dT >= 35) & (dT < 90)]])
        self.sky = sky[kd.query(sky)[0] > 20.0] if LARGE_FORM else sky
        self.wav = self.base.wav[kd.query(self.base.wav)[0] > 20.0] if LARGE_FORM else self.base.wav

    def cov_sdf(self, c, A, Y):
        """signed distance to the candidate's painting-view coverage (>0 outside), computed at 2x (half-pixel quantisation
        instead of the round-3 1x), returned as a sampler on display px plus the 1x coverage."""
        import cv2
        V1, fr = self.base.V1, self.base.fr
        X = fr.world(c, A, Y)
        r0 = int(np.searchsorted(c, -40.0))
        Xs = X[r0:]
        key = (r0, A.shape)
        if getattr(self, "_tk", None) != key:
            self._tk = key; self._tris = V1.triangles(A.shape[1], A.shape[0] - r0)
        cam = fr.cam; ss = 2
        Pp = cam.project(Xs.reshape(-1, 3))
        xy = (Pp[:, :2] + 0.5) * ss - 0.5
        ok = Pp[:, 2] > 0.5
        img = np.zeros((cam.H * ss, cam.W * ss), np.uint8)
        ip = np.round(xy * 16).astype(np.int32)
        tv = ok[self._tris].all(1)
        for tri in ip[self._tris[tv]]:
            cv2.fillConvexPoly(img, tri, 1, lineType=cv2.LINE_8, shift=4)
        din = cv2.distanceTransform(img, cv2.DIST_L2, 5)
        dout = cv2.distanceTransform(1 - img, cv2.DIST_L2, 5)
        sdf2 = (dout - din) / ss
        cov = img.reshape(cam.H, ss, cam.W, ss).mean((1, 3))
        return _Sdf2(sdf2, ss), cov, X


class _Sdf2:
    """sampler: display px (x, y) -> signed distance (display px) from a 2x supersampled distance map."""

    def __init__(self, img, ss):
        self.img = img; self.ss = ss


def sdf_at(sdf, P):
    import candA4_fit as F
    if isinstance(sdf, _Sdf2):
        Q = (np.asarray(P, float) + 0.5) * sdf.ss - 0.5
        return F.bilin(sdf.img, Q)
    return F.bilin(sdf, P)


class Problem:
    def __init__(self, ctx, design, active, weights, ref_design=None):
        self.ctx = ctx
        self.d = design
        self.active = active
        self.w = weights
        self.ref = ref_design if ref_design is not None else D.Design({n: (list(v[0]), list(v[1])) for n, v in design.keys.items()})
        self.x0 = np.array([design.keys[n][1][i] for n, i in active])

    def set(self, x):
        for (n, i), v in zip(self.active, x):
            self.d.keys[n][1][i] = float(v)

    def residual(self, x, detail=False):
        ctx, w, F = self.ctx, self.w, self.ctx.F
        self.set(x)
        c, A, Y, P = D.build(self.d, ctx.c)
        sdf, cov, X = ctx.cov_sdf(c, A, Y)
        res, info = [], {}
        rT = sdf_at(sdf, ctx.T)
        for k in ("78", "130", "131", "132", "72"):
            m = ctx.Tlab == k
            # beyond 3 px the error counts more (the gate is a max)
            e = rT[m]
            nrm = 1.0 / math.sqrt(max(m.sum(), 1) / 100.0)          # each item counts like 100 points
            res.append(nrm * w.get("gate_" + k, 1.0) * (e + 1.5 * np.sign(e) * np.maximum(np.abs(e) - 3.0, 0.0)))
            info[k] = e
        rs = np.maximum(0.0, -sdf_at(sdf, ctx.sky)); rw = np.maximum(0.0, sdf_at(sdf, ctx.wav))
        res.append(w.get("spill", 0.5) * rs / math.sqrt(len(rs) / 400.0)); res.append(w.get("hole", 0.3) * rw / math.sqrt(len(rw) / 200.0))
        info["spill"] = rs; info["hole"] = rw
        if w.get("band", 0) > 0:
            rows = np.nonzero((c > -18.5) & (c < -3.5))[0]
            tp, bp = F.band_curves(ctx.base, c, A, Y, X, rows)
            rt = F.curve_vs_target(tp, ctx.base.band_top); rb = F.curve_vs_target(bp, ctx.base.band_bot)
            res.append(w["band"] * rt * 1.5); res.append(w["band"] * rb * 1.5); info["band_top"] = rt; info["band_bot"] = rb
        # lip validity: the upper surface stays clear of the underside (every 3rd row)
        pen = []
        for r in np.nonzero((c > -20) & (c < 14))[0][::3]:
            if Y[r].max() < 3.0:
                pen.append(0.0); continue
            Pu = np.stack([A[r, 100:196], Y[r, 100:196]], -1); Pl = np.stack([A[r, 206:300:2], Y[r, 206:300:2]], -1)
            dmin = float(np.min(np.linalg.norm(Pu[:, None, :] - Pl[None, :, :], axis=-1)))
            pen.append(max(0.0, 0.25 - dmin))
        res.append(w.get("valid", 20.0) * np.array(pen if pen else [0.0]))
        # Q21-1: 3 m sag across the rows beyond what a smooth wave needs
        if w.get("sag", 0) > 0:
            X3 = D_world(c, A, Y)
            cs = ctx.sag_c
            cols = np.arange(18, 395, 4)
            Xi = np.stack([np.stack([np.interp(cs + dc, c, X3[:, j, k]) for k in range(3)], -1) for dc in (-1.5, 0.0, 1.5) for j in cols], 0)
            Xi = Xi.reshape(3, len(cols), len(cs), 3)
            sag = np.linalg.norm(Xi[1] - 0.5 * (Xi[0] + Xi[2]), axis=-1)
            yok = Xi[1, :, :, 1] > 0.3
            rsag = np.where(yok, np.maximum(0.0, sag - 0.12), 0.0).ravel()
            res.append(w["sag"] * rsag / 0.05 / math.sqrt(len(rsag) / 400.0)); info["sag_max"] = float(np.where(yok, sag, 0).max())
            info["sag_p99"] = float(np.percentile(sag[yok], 99)) if yok.any() else 0.0
        # Q21-1 bumps: 4th differences along c (1 m and 2 m steps) remove the smooth trend of the crest (its peak and
        # its end are allowed) and keep local bulges / dents of 1..4 m width
        if w.get("bump", 0) > 0:
            bq = bump4(c, A, Y)
            # thresholds: a design with constant shape ramps (only the crest height / plan varying) gives p99 0.29 / 1.7 m
            res.append(w["bump"] * np.maximum(0.0, bq["d1"] - BUMP_T1).ravel() / 0.02 / math.sqrt(bq["d1"].size / 400.0))
            res.append(w["bump"] * np.maximum(0.0, bq["d2"] - BUMP_T2).ravel() / 0.04 / math.sqrt(bq["d2"].size / 400.0))
            info["bump"] = [float(np.percentile(bq["d1"], 99)), float(bq["d1"].max()), float(np.percentile(bq["d2"], 99)), float(bq["d2"].max())]
        # regularisation: toward the reference proportions, and smoothness of the key values along c
        reg = []
        rw_ = w.get("reg", 0.3); rws = w.get("reg_sil", 0.02)
        for (n, i), v in zip(self.active, x):
            wt = rws if n in ("crest_height", "crest_a") or n.startswith("edge_") else rw_
            reg.append(wt * (v - self.ref.keys[n][1][i]) / SCALE[n])
        for n in sorted(set(n for n, i in self.active)):
            s, v = self.d.keys[n]
            for i in range(1, len(v) - 1):
                h0, h1 = s[i] - s[i - 1], s[i + 1] - s[i]
                d2 = ((v[i + 1] - v[i]) / h1 - (v[i] - v[i - 1]) / h0) / (0.5 * (h0 + h1))
                reg.append(w.get("smooth", 1.0) * d2 * 2.0 / SCALE[n])
        # shape priors on the keys: behind the main section the crest height only falls and the crest top only recedes
        # (one peak, a plan line that sweeps back smoothly: no twisted far crest)
        if w.get("mono", 0) > 0:
            for n, c0 in (("crest_height", -1.0), ("crest_a", 0.0)):
                cs, vs = self.d.keys[n]
                for i in range(len(cs) - 1):
                    if cs[i] >= c0 - 1e-9:
                        reg.append(w["mono"] * max(0.0, vs[i + 1] - vs[i]) / SCALE[n])
        res.append(np.array(reg))
        r = np.concatenate([np.atleast_1d(q) for q in res])
        if detail:
            return r, info, (c, A, Y, cov)
        return r


BUMP_T1, BUMP_T2 = 0.20, 0.90
BUMP_C = np.arange(-17.0, 9.01, 0.5)
BUMP_J = np.r_[np.arange(18, 186, 4), np.arange(214, 380, 4)]      # the lip-tip strip (186..214) is the hook itself


def bump4(c, A, Y):
    """|Δ⁴ X| along c at 1 m and 2 m steps (m), columns every 4, rows c -18..+12, points above 0.3 m."""
    X3 = D_world(c, A, Y)[:, BUMP_J, :]
    out = {}
    for key, h in (("d1", 1.0), ("d2", 2.0)):
        P = [np.stack([np.stack([np.interp(BUMP_C + k * h, c, X3[:, j, q]) for q in range(3)], -1) for j in range(len(BUMP_J))], 0)
             for k in (-2, -1, 0, 1, 2)]
        d4 = P[0] - 4 * P[1] + 6 * P[2] - 4 * P[3] + P[4]
        v = np.linalg.norm(d4, axis=-1)
        out[key] = np.where(P[2][..., 1] > 0.3, v, 0.0)
    return out


def D_world(c, A, Y):
    E = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
    O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
    return O[None, None, :] + A[..., None] * T + Y[..., None] * np.array([0, 1.0, 0]) + np.asarray(c)[:, None, None] * E


_G = {}


def _init(dj, active, weights, refj):
    _G["p"] = Problem(Ctx(), D.Design.from_json(dj), active, weights, D.Design.from_json(refj))


def _eval(x):
    return _G["p"].residual(np.array(x))


def fit(design, active, weights, iters=8, workers=18, ref=None, ckpt=None, log=lambda *a: print(*a, flush=True)):
    import multiprocessing as mp
    ctx = Ctx()
    ref = ref or D.Design.from_json(design.to_json())
    prob = Problem(ctx, design, active, weights, ref)
    lo = np.array([D.PBOUNDS[n][0] for n, i in active]); hi = np.array([D.PBOUNDS[n][1] for n, i in active])
    x = np.clip(prob.x0.copy(), lo, hi)
    steps = np.array([FD_STEP * SCALE[n] for n, i in active])
    pool = mp.Pool(workers, initializer=_init, initargs=(design.to_json(), active, weights, ref.to_json()))
    lam = 1.0
    r = prob.residual(x); f = 0.5 * r @ r
    log("start cost %.1f  n_res %d  n_par %d  %s" % (f, len(r), len(x), json.dumps(summary(prob)[0])))
    t0 = time.time()
    for it in range(iters):
        # central differences (the painting-view terms have kinks where the silhouette switches rows)
        xs = []
        for k in range(len(x)):
            hp = min(steps[k], hi[k] - x[k]); hm = min(steps[k], x[k] - lo[k])
            if hp < 0.2 * steps[k]:
                hp = 0.0
            if hm < 0.2 * steps[k]:
                hm = 0.0
            if hp == 0 and hm == 0:
                hp = steps[k]
            xp = x.copy(); xp[k] += hp; xm = x.copy(); xm[k] -= hm
            xs.append((xp, xm, hp, hm))
        R = pool.map(_eval, [list(q) for t in xs for q in (t[0], t[1])])
        cols = []
        for k, (xp, xm, hp, hm) in enumerate(xs):
            rp, rm = R[2 * k], R[2 * k + 1]
            if hp > 0 and hm > 0:
                cols.append((rp - rm) / (hp + hm))
            elif hp > 0:
                cols.append((rp - r) / hp)
            else:
                cols.append((r - rm) / hm)
        J = np.stack(cols, 1)
        g = J.T @ r; Hm = J.T @ J
        improved = False
        for _ in range(7):
            dx = -np.linalg.solve(Hm + lam * np.diag(np.diag(Hm) + 1e-6), g)
            xn = np.clip(x + dx, lo, hi)
            rn = prob.residual(xn); fn = 0.5 * rn @ rn
            if fn < f:
                x, r, f = xn, rn, fn; lam = max(lam / 3, 1e-4); improved = True
                break
            lam *= 4
        prob.set(x)
        log("it %d cost %.1f lam %.3g %s  %.0fs  %s" % (it, f, lam, "" if improved else "(no step)", time.time() - t0, json.dumps(summary(prob)[0])))
        if ckpt:
            prob.d.save(ckpt)
        if not improved and lam > 1e4:
            break
    pool.close(); pool.join()
    prob.set(x)
    return design, prob


def summary(prob):
    x = np.array([prob.d.keys[n][1][i] for n, i in prob.active])
    r, info, (c, A, Y, cov) = prob.residual(x, detail=True)
    s = {}
    for k in ("78", "130", "131", "132", "72"):
        v = np.abs(info[k]); s[k] = [round(float(v.max()), 1), round(float(np.percentile(v, 95)), 1)]
    s["spill"] = [round(float(info["spill"].max()), 1), int((info["spill"] > 2).sum())]
    s["hole"] = [round(float(info["hole"].max()), 1), int((info["hole"] > 2).sum())]
    for k in ("band_top", "band_bot"):
        if k in info:
            v = np.abs(info[k]); s[k] = [round(float(np.median(v)), 1), round(float(v.max()), 1)]
    if "bump" in info:
        s["bump_d1_p99max_d2_p99max"] = [round(x, 3) for x in info["bump"]]
    if "sag_max" in info:
        s["sag_max_p99"] = [round(info["sag_max"], 2), round(info["sag_p99"], 2)]
    return s, (c, A, Y)


def active_for(design, spec):
    act = []
    for n, (c0, c1) in spec.items():
        for i, v in enumerate(design.keys[n][0]):
            if c0 - 1e-9 <= v <= c1 + 1e-9:
                act.append((n, i))
    return act


# the crest line: its height everywhere; its plan position only on the far side (c >= 1): on the near side the crest top
# stays at a = 0 (the K* section frame is built on it), so the fit cannot trade depth for height (a lower crest nearer
# the camera would draw the same outline)
SILR = {"crest_height": (-32, 16.5), "crest_a": (1, 16.5)}      # keys at c >= 18 are fixed: the far end closes (H -> 0)
LIP = ("tube_radius", "tube_oval", "lean", "tip_angle", "hook_depth", "lip_thick", "shell_top")
LIP2 = LIP + ("hook_span", "lip_len", "tip_round")
EDGES = {k: (-24, 20) for k in ("edge_top", "edge_lip", "edge_hook")}
STAGES = {
    "crest": dict(params=dict(SILR, **{k: (-20, 14) for k in ("lean", "tip_angle", "tube_radius")}),
                  weights={"spill": 1.0, "hole": 0.5, "reg": 0.3, "reg_sil": 0.15, "smooth": 5.0, "bump": 1.0,
                           "gate_132": 0.5, "gate_72": 0.3}),
    "crest2": dict(params=dict(SILR, **{k: (-20, 16) for k in ("tube_radius", "lean", "tip_angle", "hook_depth", "shell_top", "tip_round", "lip_thick")}),
                   weights={"spill": 1.0, "hole": 0.5, "reg": 0.5, "reg_sil": 0.1, "smooth": 30.0, "bump": 1.0, "mono": 10.0}),
    "lip": dict(params=dict(SILR, **{k: (-20, 14) for k in LIP2}),
                weights={"spill": 1.0, "hole": 0.5, "reg": 0.3, "reg_sil": 0.15, "smooth": 5.0, "bump": 1.0}),
    "all": dict(params=dict(SILR, **{k: (-20, 14) for k in LIP2}, **EDGES),
                weights={"spill": 1.0, "hole": 0.5, "reg": 0.3, "reg_sil": 0.1, "smooth": 5.0, "bump": 1.0}),
    "band2": dict(params=dict({k: (-19, -3) for k in ("ledge_amp", "ledge_pos", "ledge_width")},
                              **{k: (-17, -7) for k in ("tube_radius", "lean", "tip_angle", "hook_depth", "shell_top", "lip_thick", "crest_height")}),
                  weights={"band": 1.0, "spill": 1.0, "hole": 0.5, "reg": 0.5, "reg_sil": 0.1, "smooth": 20.0, "bump": 1.0, "mono": 10.0}),
    "band": dict(params=dict({k: (-19, -3) for k in ("ledge_amp", "ledge_pos", "ledge_width")}),
                 weights={"band": 1.0, "spill": 1.0, "hole": 0.5, "reg": 0.3, "smooth": 3.0, "bump": 1.0}),
    "edges": dict(params=dict(EDGES),
                  weights={"band": 0.5, "spill": 1.0, "hole": 0.5, "reg_sil": 0.3, "smooth": 2.0, "bump": 1.0}),
}


if __name__ == "__main__":
    din, dout, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 8
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 18
    d = D.Design.load(din)
    st = STAGES[stage]
    act = active_for(d, st["params"])
    t0 = time.time()
    d, prob = fit(d, act, st["weights"], iters=iters, workers=workers, ckpt=dout + ".ckpt.json")
    s, _ = summary(prob)
    out = d.to_json(); out["fit_log"] = {"stage": stage, "summary": s, "n_active": len(act), "seconds": round(time.time() - t0)}
    json.dump(out, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL", json.dumps(s))
