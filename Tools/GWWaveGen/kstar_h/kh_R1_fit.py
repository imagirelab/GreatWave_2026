# -*- coding: utf-8 -*-
"""K*′ 精修 R1（候補 H1A の続き）：Houdini のネットワークの母数（CTRL の ramp の鍵）を原画と評審の must-fix に合わせる（py -3.10）。

H1A の当てはめ（kh_fitA.py）から変えた所
  * 形は kh_designR1（Houdini の Python SOP と同じ式）。唇・管・殻の母数の鍵を 2.5〜3 m おきにし、原画の輪郭を「本体の大きな形」で
    合わせる。側の縁の帯（edge_*）は ±0.3 m まで、鍵 2 m おき、なめらかさを強く（H1A は ±1.5 m で 1 m おきに振れ、中央のふくらみ
    （ドーム）と背のこぶを作った）。
  * 罰を足した：唇の上面と下面の間隔（交差させない、≥ 0.35 m）、頂の列（90）より高い点を作らない、H(c) の山は 1 つ（c −20〜−1.5 は
    下がらない、c +3〜+15 は上がらない。0.3 m までの小さなくぼみは許す）、主断面の高さ H0 ≥ 20.3 m、最高点 ≤ 1.04 H0。
  * 原画の関門は大きな輪郭（進行役の 20:00 の判断、σ 12 px）で、kh_fitA.Ctx（round 3 の目標・空と波の探り・b 区域の帯）をそのまま使う。
usage: py -3.10 kh_R1_fit.py design_in.json design_out.json STAGE [--iters N] [--workers N]
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
import kh_designR1 as D  # noqa: E402
import kh_fitA as KF  # noqa: E402  (Ctx, bump4, D_world: read-only reuse)

SCALE = dict(KF.SCALE)
SCALE.update({"lipprof_%d" % k: 0.08 for k in range(1, 6)})
SCALE.update({"edge_%d" % k: 0.08 for k in range(1, 10)})
FIT_BOUNDS = {"tube_radius": (0.30, 0.52), "tube_oval": (-0.18, 0.18), "lean": (-5.0, 34.0), "tip_angle": (-40.0, 40.0),
              "hook_depth": (0.0, 0.15), "hook_span": (20.0, 95.0), "lip_len": (8.0, 50.0), "lip_thick": (0.02, 0.14),
              "tip_round": (0.10, 1.20), "shell_top": (0.15, 0.36), "shell_back": (0.18, 0.40), "ledge_amp": (0.0, 3.0),
              "ledge_pos": (0.45, 0.85), "ledge_width": (0.08, 0.25), "ledge_lobe": (-1.0, 2.0),
              **{"edge_%d" % k: (-0.3, 0.3) for k in range(1, 10)}, "edge_tip": (-0.35, 0.35),
              **{"lipprof_%d" % k: (-0.6, 0.6) for k in range(1, 6)}, "crest_a": (-16.0, 2.0),
              "tube_end": (215.0, 265.0), "trough_reach": (0.05, 0.6), "trough_depth": (0.12, 0.32), "trough_len": (0.15, 0.8)}
CLEAR_MIN = 0.35
CORNER_MIN = 0.335
H0_MIN = 20.3


class Problem:
    def __init__(self, ctx, design, active, weights, ref_design=None):
        self.ctx = ctx
        self.d = design
        self.active = active
        self.w = weights
        self.ref = ref_design if ref_design is not None else D.Design.from_json(design.to_json())
        self.x0 = np.array([design.keys[n][1][i] for n, i in active])
        c = ctx.c
        self.r_main = int(np.argmin(np.abs(c)))
        self.rows_clear = np.nonzero((c > -22) & (c < 14.6))[0][::2]
        self.rows_top = np.nonzero((c > -24) & (c < 14.0))[0]
        self.m_left = (c >= -20.0) & (c <= -0.5)
        self.m_right = (c >= 3.0) & (c <= 15.01)

    def set(self, x):
        for (n, i), v in zip(self.active, x):
            self.d.keys[n][1][i] = float(v)

    def residual(self, x, detail=False):
        ctx, w, F = self.ctx, self.w, self.ctx.F
        self.set(x)
        c, A, Y, P = D.build(self.d, ctx.c)
        sdf, cov, X = ctx.cov_sdf(c, A, Y)
        res, info = [], {}
        if w.get("official", 0) > 0:
            # R1: the official gate's measure (truth -> render and render -> truth, 132 / 72 large form), fixed length
            if not hasattr(ctx, "snap"):
                import kh_R1_snap as SN
                ctx.snap = SN.Snap()
            fe, met = ctx.snap.fixed(c, A, Y)
            for k in ("78", "130", "131", "132", "72"):
                e_tr, e_rt = fe[k]
                nrm = 1.0 / math.sqrt(max(len(e_tr), 1) / 100.0)
                thr = 2.5 if k != "72" else 3.0
                for e in (e_tr, e_rt):
                    res.append(nrm * w.get("gate_" + k, 1.0) * (e + 3.0 * np.sign(e) * np.maximum(np.abs(e) - thr, 0.0)))
                info[k] = np.r_[e_tr, e_rt]
            info["official"] = met
        else:
            rT = F.bilin(sdf, ctx.T)
            for k in ("78", "130", "131", "132", "72"):
                m = ctx.Tlab == k
                e = rT[m]
                nrm = 1.0 / math.sqrt(max(m.sum(), 1) / 100.0)
                res.append(nrm * w.get("gate_" + k, 1.0) * (e + 1.5 * np.sign(e) * np.maximum(np.abs(e) - 3.0, 0.0)))
                info[k] = e
        rs = np.maximum(0.0, -F.bilin(sdf, ctx.sky)); rw = np.maximum(0.0, F.bilin(sdf, ctx.wav))
        res.append(w.get("spill", 0.5) * rs / math.sqrt(len(rs) / 400.0)); res.append(w.get("hole", 0.3) * rw / math.sqrt(len(rw) / 200.0))
        info["spill"] = rs; info["hole"] = rw
        if w.get("holeb", 0) > 0:
            sb = ctx.body_sdf(c, A, Y)
            hb = np.maximum(0.0, F.bilin(sb, ctx.wav_base) - 2.0)
            res.append(w["holeb"] * hb / math.sqrt(max(len(hb), 1) / 100.0)); info["holeb"] = hb
            if len(ctx.T72ext):
                e72 = F.bilin(sb, ctx.T72ext)
                res.append(w["holeb"] * (e72 + 1.5 * np.sign(e72) * np.maximum(np.abs(e72) - 3.0, 0.0)) / math.sqrt(max(len(e72), 1) / 50.0))
                info["t72ext"] = e72
        if w.get("vspill", 0) > 0:
            vs = ctx.vertex_spill(c, A, Y)
            res.append(w["vspill"] * 0.2 * vs); info["vspill"] = vs
        if w.get("band", 0) > 0:
            rows = np.nonzero((c > -18.5) & (c < -3.5))[0]
            pos = np.asarray(P["ledge_pos"])[rows]; wd = np.asarray(P["ledge_width"])[rows]
            jr = 90.0 + 110.0 * pos; jv = 90.0 + 110.0 * (pos - 1.6 * wd)

            def at(jf):
                j0 = np.clip(np.floor(jf).astype(int), 0, 398); t = (jf - j0)[:, None]
                return X[rows, j0] * (1 - t) + X[rows, j0 + 1] * t
            pv = ctx.base.fr.cam.project(at(jv))[:, :2]
            Pw = ctx.base.fr.cam.project(X[rows, 150:216].reshape(-1, 3))[:, :2].reshape(len(rows), 66, 2)
            jj = np.arange(150, 216)[None, :]
            win = (jj >= jr[:, None] - 15) & (jj <= jr[:, None] + 8)
            yw = np.where(win, Pw[..., 1], np.inf); kr_ = np.argmin(yw, 1)
            pr = Pw[np.arange(len(rows)), kr_]
            kb_ = 38 + np.argmax(Pw[:, 38:66, 1], 1)
            pb = Pw[np.arange(len(rows)), kb_]
            rt = F.curve_vs_target(pr, ctx.base.band_top); rb = F.curve_vs_target(pb, ctx.base.band_bot)
            amp = np.asarray(P["ledge_amp"])[rows]
            vv = np.where(amp > 0.3, np.maximum(0.0, 8.0 - (pv[:, 1] - pr[:, 1])), 0.0)
            res.append(w["band"] * vv * 0.5)
            res.append(w["band"] * rt * 1.5); res.append(w["band"] * rb * 1.5); info["band_top"] = rt; info["band_bot"] = rb
        # R1: the lip never passes through itself (signed clearance of the upper lip over the lower surface)
        mins, _ = D.lip_clearance(A, Y, self.rows_clear)
        cl = mins[self.rows_clear]
        res.append(w.get("clear", 30.0) * np.maximum(0.0, CLEAR_MIN - cl)); info["clear_min"] = float(cl.min())
        # R1: the top column is the highest point of the section (no ledge / lip above it)
        te = D.top_excess(A, Y)[self.rows_top]
        res.append(w.get("topx", 10.0) * np.maximum(0.0, te + 0.05)); info["top_excess_max"] = float(te.max())
        # R1: one peak of H(c), main height, highest point near the main section
        Hc = Y.max(1)
        # R1: the corner column (314, the rearmost point of the tube) stays above 0.3 H: the motion generator (ds27 ja, the first
        #     0.3 H crossing after j_corner) rebuilds the inner wall from there; H1A's corner at 0.20 H broke the re-target
        hb = Hc >= 3.0
        cr = np.where(hb, np.maximum(0.0, CORNER_MIN - Y[:, 314] / np.maximum(Hc, 1e-6)), 0.0)
        res.append(w.get("corner", 50.0) * cr / math.sqrt(max(hb.sum(), 1) / 20.0)); info["corner_min"] = float(np.min(np.where(hb, Y[:, 314] / np.maximum(Hc, 1e-6), 9)))
        L = Hc[self.m_left]; dipL = np.maximum.accumulate(L) - L
        R = Hc[self.m_right]; dipR = np.maximum.accumulate(R[::-1])[::-1] - R
        res.append(w.get("peak", 5.0) * np.maximum(0.0, dipL - 0.3) / math.sqrt(len(L) / 20.0))
        res.append(w.get("peak", 5.0) * np.maximum(0.0, dipR - 0.3) / math.sqrt(len(R) / 20.0))
        # R1: the far end falls at most 3.3 m per m of crest (rubric F10 <= 3.5) and reaches still water at the last row
        cf = c[self.m_right]; slope = np.abs(np.diff(R) / np.maximum(np.diff(cf), 1e-6))
        res.append(w.get("fall", 20.0) * np.maximum(0.0, slope - 3.3) / math.sqrt(len(slope) / 20.0)); info["fall_max"] = float(slope.max())
        # R1: the far crest line sweeps back monotonically in plan (no hook back at the end: A4 is monotone; H1A / R1a had a
        #     reversal at c 11..14 that the judges' bulge measure reads as a 0.6-0.8 m bump on the far back)
        if w.get("plan", 0) > 0:
            mp = (c >= 2.0) & (c <= 14.6)
            aT = A[mp, 90]; cc_ = c[mp]
            da = np.diff(aT) / np.maximum(np.diff(cc_), 1e-6)
            d2a = np.diff(da) / np.maximum(0.5 * (np.diff(cc_)[1:] + np.diff(cc_)[:-1]), 1e-6)
            res.append(w["plan"] * np.maximum(0.0, da + 0.05) / math.sqrt(len(da) / 20.0))
            res.append(0.3 * w["plan"] * np.maximum(0.0, np.abs(d2a) - 1.2) / math.sqrt(len(d2a) / 20.0))
            info["plan_rev_max"] = float(da.max()); info["plan_curv_max"] = float(np.abs(d2a).max())
        H0 = float(Y[self.r_main].max())
        res.append(np.array([w.get("h0", 5.0) * max(0.0, H0_MIN - H0), w.get("h0", 5.0) * max(0.0, float(Hc.max()) - 1.04 * H0)]))
        info["H0"] = H0; info["Hmax_c"] = [float(Hc.max()), float(c[int(np.argmax(Hc))])]
        info["dip"] = [float(dipL.max()), float(dipR.max())]
        # R1: creases across the rows (rubric F11: quads with |c| <= 16, y > 0.3 m, the lip-tip strip excluded; > 30 deg must be rare)
        if w.get("fold", 0) > 0:
            ang = fold_angles(c, A, Y)
            res.append(w["fold"] * np.maximum(0.0, ang - 22.0) / 10.0); info["fold_gt30"] = int((ang > 30).sum())
        if w.get("bump", 0) > 0:
            bq = KF.bump4(c, A, Y)
            res.append(w["bump"] * np.maximum(0.0, bq["d1"] - KF.BUMP_T1).ravel() / 0.02 / math.sqrt(bq["d1"].size / 400.0))
            res.append(w["bump"] * np.maximum(0.0, bq["d2"] - KF.BUMP_T2).ravel() / 0.04 / math.sqrt(bq["d2"].size / 400.0))
            info["bump"] = [float(np.percentile(bq["d1"], 99)), float(bq["d1"].max()), float(np.percentile(bq["d2"], 99)), float(bq["d2"].max())]
        reg = []
        rw_ = w.get("reg", 0.3); rws = w.get("reg_sil", 0.02)
        for (n, i), v in zip(self.active, x):
            wt = rws if n in ("crest_height", "crest_a") or n.startswith("edge_") else rw_
            reg.append(wt * (v - self.ref.keys[n][1][i]) / SCALE[n])
        for n in sorted(set(n for n, i in self.active)):
            s, v = self.d.keys[n]
            sm = w.get("smooth_edges", w.get("smooth", 1.0)) if n.startswith("edge_") else w.get("smooth", 1.0)
            for i in range(1, len(v) - 1):
                h0, h1 = s[i] - s[i - 1], s[i + 1] - s[i]
                d2 = ((v[i + 1] - v[i]) / h1 - (v[i] - v[i - 1]) / h0) / (0.5 * (h0 + h1))
                reg.append(sm * d2 * 2.0 / SCALE[n])
        res.append(np.array(reg))
        r = np.concatenate([np.atleast_1d(q) for q in res])
        if detail:
            return r, info, (c, A, Y, cov)
        return r


def fold_angles(c, A, Y, jtip=200):
    """rubric F11 (rubric_check.py): angle (deg) between the normals of quads adjacent across the rows, masked like the rubric."""
    nu = A.shape[1]
    Xg = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
    du = Xg[:, 1:] - Xg[:, :-1]; dv = Xg[1:] - Xg[:-1]
    n = np.cross(du[:-1], dv[:, :-1]); n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
    ang_r = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
    cols = np.arange(nu - 1)[None, :]
    mr = (Y[1:-1, :-1] > 0.3) & ~((cols >= jtip - 10) & (cols <= jtip + 12)) & (np.abs(c[1:-1, None]) <= 16)
    return np.where(mr, ang_r, 0.0).ravel()


_G = {}


def _init(dj, active, weights, refj):
    _G["p"] = Problem(KF.Ctx(), D.Design.from_json(dj), active, weights, D.Design.from_json(refj))


def _eval(x):
    return _G["p"].residual(np.array(x))


def bounds_of(n):
    return FIT_BOUNDS.get(n, D.PBOUNDS[n])


def fit(design, active, weights, iters=8, workers=18, ref=None, ckpt=None, log=lambda *a: print(*a, flush=True)):
    import multiprocessing as mp
    ctx = KF.Ctx()
    ref = ref or D.Design.from_json(design.to_json())
    prob = Problem(ctx, design, active, weights, ref)
    lo = np.array([bounds_of(n)[0] for n, i in active]); hi = np.array([bounds_of(n)[1] for n, i in active])
    x = np.clip(prob.x0.copy(), lo, hi)
    steps = np.array([0.35 * SCALE[n] for n, i in active])
    pool = mp.Pool(workers, initializer=_init, initargs=(design.to_json(), active, weights, ref.to_json()))
    lam = 1.0
    r = prob.residual(x); f = 0.5 * r @ r
    log("start cost %.1f  n_res %d  n_par %d  %s" % (f, len(r), len(x), json.dumps(summary(prob)[0])))
    t0 = time.time()
    for it in range(iters):
        xs = []
        for k in range(len(x)):
            xp = x.copy(); xp[k] = xp[k] + steps[k] if xp[k] + steps[k] <= hi[k] else xp[k] - steps[k]
            xs.append(xp)
        R = pool.map(_eval, [list(q) for q in xs])
        J = np.stack([(R[k] - r) / (xs[k][k] - x[k]) for k in range(len(x))], 1)
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
        if "official" in info:
            s[k] = [round(info["official"][k]["max"], 2), round(info["official"][k]["p95"], 2)]
        else:
            v = np.abs(info[k]); s[k] = [round(float(v.max()), 1), round(float(np.percentile(v, 95)), 1)]
    s["spill"] = [round(float(info["spill"].max()), 1), int((info["spill"] > 2).sum())]
    s["hole"] = [round(float(info["hole"].max()), 1), int((info["hole"] > 2).sum())]
    for k in ("band_top", "band_bot"):
        if k in info:
            v = np.abs(info[k]); s[k] = [round(float(np.median(v)), 1), round(float(v.max()), 1)]
    if "vspill" in info:
        s["vspill_max_n>4"] = [round(float(info["vspill"].max()), 1), int((info["vspill"] > 4).sum())]
    if "bump" in info:
        s["bump"] = [round(q, 3) for q in info["bump"]]
    for k in ("clear_min", "top_excess_max", "H0", "corner_min", "fall_max"):
        pass
    if "fold_gt30" in info:
        s["fold_gt30"] = info["fold_gt30"]
    for k in ("plan_rev_max", "plan_curv_max"):
        if k in info:
            s[k] = round(info[k], 3)
    for k in ("clear_min", "top_excess_max", "H0", "corner_min", "fall_max"):
        s[k] = round(info[k], 3)
    s["Hmax_c"] = [round(q, 2) for q in info["Hmax_c"]]; s["dip"] = [round(q, 2) for q in info["dip"]]
    return s, (c, A, Y)


def active_for(design, spec):
    act = []
    for n, (c0, c1) in spec.items():
        for i, v in enumerate(design.keys[n][0]):
            if c0 - 1e-9 <= v <= c1 + 1e-9:
                act.append((n, i))
    return act


LIP = ("tube_radius", "tube_oval", "lean", "tip_angle", "hook_depth", "lip_thick", "shell_top", "hook_span", "lip_len", "tip_round")
LEDGE = ("ledge_amp", "ledge_pos", "ledge_width", "ledge_lobe")
EDGES = {"edge_%d" % k: (-24, 15) for k in range(1, 10)}
SCALE["edge_tip"] = 0.08
LIPPROF = {"lipprof_%d" % k: (-10, 8) for k in range(1, 6)}
W_BASE = {"band": 0.7, "spill": 1.0, "hole": 0.5, "holeb": 1.5, "vspill": 5.0, "reg": 0.5, "reg_sil": 0.1, "smooth": 6.0, "bump": 2.0,
          "gate_72": 1.5, "gate_132": 1.5, "clear": 150.0, "topx": 30.0, "peak": 100.0, "h0": 200.0, "corner": 8000.0}
STAGES = {
    # the crest line alone (height everywhere, plan position on the far side)
    "crest": dict(params={"crest_height": (-34, 14.5), "crest_a": (1, 14)}, weights=dict(W_BASE)),
    # body: crest line + lip / tube / shell (large forms) + b region, no side-edge strips
    "base": dict(params=dict({"crest_height": (-34, 14.5), "crest_a": (1, 14)}, **{k: (-20, 14) for k in LIP}, **{k: (-19, -3) for k in LEDGE}),
                 weights=dict(W_BASE)),
    "lip": dict(params=dict({"crest_height": (-10, 14.5), "crest_a": (1, 14)}, **{k: (-10, 14) for k in LIP}), weights=dict(W_BASE)),
    "far": dict(params=dict({"crest_height": (4, 14.5), "crest_a": (4, 14)}, **{k: (4, 16) for k in LIP + ("tube_end", "trough_reach")}),
                weights=dict(W_BASE, gate_72=2.0)),
    "band": dict(params=dict({k: (-19, -3) for k in LEDGE}, **{k: (-20, -3) for k in ("tip_angle", "hook_depth", "lip_len", "lean", "lip_thick")}),
                 weights=dict(W_BASE, band=1.0)),
    # lip-top section profile (+ lip / tube / crest near the main section, + the far rows for 72)
    "prof": dict(params=dict({"crest_height": (-10, 14.5), "crest_a": (1, 14)}, **{k: (-10, 14) for k in LIP}, **LIPPROF),
                 weights=dict(W_BASE, gate_132=2.0, gate_72=2.0)),
    # the side-edge strips, bounded +-0.3 m, strongly smoothed along c
    "edges": dict(params=dict(EDGES), weights=dict(W_BASE, reg_sil=0.3, smooth_edges=4.0, bump=3.0, gate_78=2.5, gate_130=2.5, gate_131=2.5,
                                                   gate_132=2.5, gate_72=2.5)),
    "base2": dict(params=dict({"crest_height": (-34, 14.5), "crest_a": (1, 14)}, **{k: (-20, 15) for k in LIP}, **{k: (-19, -3) for k in LEDGE},
                              **LIPPROF, **{k: (1, 15) for k in ("back_low", "foot_spread", "shell_back")}),
                  weights=dict(W_BASE, gate_132=2.0, gate_72=2.0)),
    # final: the official gate measure, side-edge strips (+-0.3 m) + lip-top profile + the lip / crest near the main section
    "fin": dict(params=dict(EDGES, **{"edge_tip": (-10, 15)}, **LIPPROF),
                weights=dict(W_BASE, official=1.0, reg_sil=0.3, smooth_edges=3.0, bump=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0,
                             gate_132=2.0, gate_72=1.5)),
    "fin2": dict(params=dict(EDGES, **{"edge_tip": (-10, 15)}, **LIPPROF, **{"crest_height": (-24, 14.5), "crest_a": (1, 14)},
                             **{k: (-10, 15) for k in LIP}),
                 weights=dict(W_BASE, official=1.0, reg_sil=0.3, smooth_edges=3.0, bump=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0,
                              gate_132=2.0, gate_72=1.5)),
    # R1 final pair: the body with the official gate measure (no edge strips), then the edge strips alone
    "body_off": dict(params=dict({"crest_height": (-24, 14.5), "crest_a": (1, 14)}, **{k: (-10, 15) for k in LIP}, **LIPPROF,
                                 **{k: (0, 15) for k in ("tube_end", "trough_reach", "trough_depth")}),
                     weights=dict(W_BASE, official=1.0, gate_78=2.0, gate_130=2.0, gate_131=2.0, gate_132=2.0, gate_72=1.5)),
    "far_off": dict(params=dict({"crest_height": (6, 14.5), "crest_a": (6, 14)}, **{k: (8, 16) for k in LIP},
                                **{k: (8, 16) for k in ("tube_end", "trough_reach", "trough_depth")}),
                    weights=dict(W_BASE, official=1.0, fall=400.0, fold=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0, gate_132=2.0, gate_72=1.5)),
    "e72": dict(params=dict({"edge_tip": (-4, 15)}, **{"edge_%d" % k: (0, 15) for k in (6, 7, 8, 9)}),
                weights=dict(W_BASE, official=1.0, reg_sil=0.05, smooth_edges=0.4, bump=3.0, fold=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0,
                             gate_132=2.0, gate_72=3.0)),
    "lip132": dict(params=dict(LIPPROF, **{"edge_%d" % k: (-6, 4) for k in (2, 3, 4, 5)}),
                   weights=dict(W_BASE, official=1.0, reg=0.1, reg_sil=0.05, smooth_edges=0.8, smooth=2.0, bump=3.0, fold=3.0, gate_78=2.0,
                                gate_130=2.0, gate_131=2.0, gate_132=3.0, gate_72=2.0)),
    "farplan": dict(params=dict({"crest_height": (6, 14.5), "crest_a": (6, 16)}, **{k: (8, 16) for k in LIP},
                                **{k: (8, 16) for k in ("tube_end", "trough_reach", "trough_depth")}, **{"edge_tip": (8, 15)}),
                    weights=dict(W_BASE, official=1.0, plan=300.0, fall=100.0, fold=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0,
                                 gate_132=2.0, gate_72=1.5)),
    "edges_off": dict(params=dict(EDGES, **{"edge_tip": (-10, 15)}),
                      weights=dict(W_BASE, official=1.0, reg_sil=0.3, smooth_edges=1.5, bump=3.0, fold=3.0, gate_78=2.0, gate_130=2.0, gate_131=2.0,
                                   gate_132=2.0, gate_72=1.5)),
    "all": dict(params=dict({"crest_height": (-34, 14.5), "crest_a": (1, 14)}, **{k: (-20, 14) for k in LIP}, **{k: (-19, -3) for k in LEDGE},
                            **EDGES),
                weights=dict(W_BASE, smooth_edges=4.0, gate_78=2.0, gate_130=2.0, gate_131=2.0, gate_132=2.0, gate_72=2.0)),
}


if __name__ == "__main__":
    din, dout, stage = sys.argv[1], sys.argv[2], sys.argv[3]
    if "--fdscale" in sys.argv:
        # larger finite-difference steps for the official gate measure (the rasterised boundary moves in pixel steps)
        f = float(sys.argv[sys.argv.index("--fdscale") + 1])
        for k in list(SCALE):
            if k.startswith("lipprof_") or k.startswith("edge_"):
                SCALE[k] = SCALE[k] * f
    iters = int(sys.argv[sys.argv.index("--iters") + 1]) if "--iters" in sys.argv else 8
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 18
    ref = D.Design.load(sys.argv[sys.argv.index("--ref") + 1]) if "--ref" in sys.argv else None
    d = D.Design.load(din)
    st = STAGES[stage]
    act = active_for(d, st["params"])
    t0 = time.time()
    d, prob = fit(d, act, st["weights"], iters=iters, workers=workers, ref=ref, ckpt=dout + ".ckpt.json")
    s, _ = summary(prob)
    out = d.to_json(); out["fit_log"] = {"stage": stage, "summary": s, "n_active": len(act), "seconds": round(time.time() - t0)}
    json.dump(out, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL", json.dumps(s))
