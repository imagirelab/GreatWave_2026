# -*- coding: utf-8 -*-
"""FLIP50 option D, screen S2: the U3 depth-averaged Boussinesq/NSW hybrid with a DIRECTIONAL inlet band and side band.
numpy/scipy only (py -3.10 -I). 2026-10-15, Claude. The U3 numerics (Unity/Build/FLIP48/diag/U3_bed/u3_model.py) are imported
read-only; the time loop is re-written here only to change the band targets. No flip45-49 file and no U3 file is edited.

What changes against u3_model.run:
  * inlet band 0 <= x <= L_in: horizontal velocity relaxed to the depth-averaged velocity of the linear directional field
    (g50_dirfield, +-theta pairs, phases aligned at (x_f, 0) at t = 0) instead of a laterally uniform stream-function wave.
  * side band W - Ls <= y <= W (new): relaxed to the same target where x <= x_gen, blended (smooth01) to an absorbing band
    (target 0, 1 - exp(-sigma chi^2 dt)) over x_gen..x_sw and absorbing beyond (FLIP45 g45_tanklib 'bands' rule).
  * corner: largest weight, target factor = product (FLIP45 rule). Ramp: half cosine over t_ramp. Upstream wall taper smooth01(x/20).
  * no exit band when the bed is a beach (the 1:10 slope runs through the still level; wet/dry as in U3).
Never pulls the surface level; nothing acts outside the bands but gravity and the bed.
Result tag: computed, screening only (depth-averaged, no overturning). It ranks candidates and checks the band generation; it does
not judge P2/P3/P5.
usage: py -3.10 -I u50_dir.py <case> [<case> ...]     (one case < 5 min CPU)
"""
import os, sys, math, time, json
os.environ.setdefault("OMP_NUM_THREADS", "2"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
U3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP48/diag/U3_bed"
sys.path.append(U3)
import numpy as np
import scipy.sparse.linalg as spla
import u3_model as M          # read only
import g50_dirfield as DF

G = M.G
OUT = os.path.join(HERE, "screen")
SCR = os.environ.get("FLIP50_SCRATCH", r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP50/screen_u50")   # 2026-10-16 会話の一時置き場から Build/FLIP50 へ移した


def smooth01(c):
    c = np.clip(c, 0.0, 1.0)
    return c * c * (3.0 - 2.0 * c)


BASE = dict(T=12.0, thm=60.0, n=30, weight="uniform", s_cos=None, delta=-20.0, a_sum=None, gamma_b=1.081, hb_target=11.0,
            W=120.0, Ls=35.0, x_gen_off=0.0, x_sw_len=30.0, L_in=100.0, wall_taper=20.0, t_ramp=None, gain=1.0,
            dx=2.0, Lx=416.0, t_end=90.0, rec_dt=0.125, h_lo=2.5, h_hi=4.0, kappa_on=1.5, kappa_off=0.3, cfl=0.45, sigma=1.41,
            bed=dict(h0=17.0, x_toe=180.25, s=10.0, kind="beach"), L_ex=0.0)


def a_sum_for(c):
    """sum of component amplitudes so that the linear centre-row break (2|A|/h >= gamma_b) is at h_b,target (s50_linear rule)."""
    import s50_linear as S
    r = S.screen_one(c["T"], c["thm"], n=c["n"], weight=c["weight"], delta=c["delta"], gamma_b=c["gamma_b"], spec=c["bed"],
                     hb_target=c["hb_target"], s_cos=c["s_cos"], apertures=(), gen_offsets=())
    return r["a_sum"], r


def run(c, verbose=True):
    T0w = time.time()
    dx = float(c["dx"]); Lx = float(c["Lx"]); W = float(c["W"])
    nx = int(round(Lx / dx)); ny = int(round(W / dx))
    xc = (np.arange(nx) + 0.5) * dx; yc = (np.arange(ny) + 0.5) * dx
    X, Y = np.meshgrid(xc, yc)
    spec = c["bed"]
    h1 = DF.bed_h(xc, spec)
    h = np.repeat(h1[None, :], ny, 0)
    h_lo = float(c["h_lo"]); h_hi = float(c["h_hi"])
    m = np.clip((h - h_lo) / (h_hi - h_lo), 0.0, 1.0)
    lu = spla.splu(M.dispersion_matrix(h, m, dx), permc_spec="COLAMD")
    lim = M.lim_vanleer
    ncell = nx * ny
    k_on = float(c["kappa_on"]); k_off = float(c["kappa_off"])
    brk = np.zeros((ny, nx), bool)
    eta = np.where(h < 0.0, -h, 0.0); P = np.zeros((ny, nx)); Q = np.zeros((ny, nx))
    # ---------------- directional target on the band cells
    T = float(c["T"]); om = 2 * math.pi / T
    xb_t = spec["x_toe"] + (spec["h0"] - c["hb_target"]) * spec["s"]
    x_f = xb_t + float(c["delta"])
    th, w = DF.components(c["thm"], c["n"], c["weight"], c["s_cos"])
    df = DF.DirField(T, th, w, float(c["a_sum"]) * float(c["gain"]), xc, spec, x_f)
    L_in = float(c["L_in"]); Ls = float(c["Ls"])
    x_gen = spec["x_toe"] + float(c["x_gen_off"]); x_sw = x_gen + float(c["x_sw_len"])
    in_band = xc < L_in
    side = (yc > W - Ls) if Ls > 0 else np.zeros(ny, bool)
    band = np.zeros((ny, nx), bool); band[:, in_band] = True; band[side, :] = True
    bx = np.where(band.any(axis=0))[0]                      # x columns that hold any band cell
    Uc, Vc = df.complex_vel(yc, depth_avg=True)               # (nx, ny)
    Uc = Uc.T; Vc = Vc.T                                       # (ny, nx)
    # weights (per small step converted inside the loop)
    w_in = np.zeros((ny, nx)); fac_in = np.zeros((ny, nx))
    chi_in = np.clip((L_in - xc) / L_in, 0.0, 1.0)
    e_wall = smooth01(xc / float(c["wall_taper"]))
    w_in[:, in_band] = M.relaxw(chi_in[in_band])[None, :]
    fac_in[:, in_band] = e_wall[in_band][None, :]
    w_sg = np.zeros((ny, nx)); chi_s = np.zeros((ny, nx)); s_x = np.zeros((ny, nx))
    if Ls > 0:
        chy = np.clip((yc - (W - Ls)) / Ls, 0.0, 1.0)
        chi_s[side, :] = chy[side][:, None]
        w_sg[side, :] = M.relaxw(chy[side])[:, None]
        s_x[side, :] = smooth01((xc - x_gen) / max(x_sw - x_gen, 1e-6))[None, :]
    fac_sd = np.where(side[:, None], 1.0 - s_x, 1.0)
    sig = float(c["sigma"])
    t_ramp = float(c["t_ramp"] if c.get("t_ramp") else 2.0 * T)
    L_ex = float(c.get("L_ex", 0.0))
    chi_ex = np.clip((xc - (Lx - L_ex)) / L_ex, 0.0, 1.0) if L_ex > 0 else np.zeros(nx)
    ex_band = chi_ex > 0

    def vel(H, P_, Q_):
        H4 = H ** 4
        d = np.sqrt(H4 + np.maximum(H4, M.EPS_H ** 4))
        f = math.sqrt(2.0) * H / d
        return P_ * f, Q_ * f

    corr = np.ones((ny, nx))

    def rhs(eta, P, Q):
        H = np.maximum(h + eta, 0.0)
        u, v = vel(H, P, Q)
        f0, f1E, f1W, f2, Sx, sx = M._faces_x(M._pad_x(H, False), M._pad_x(eta, False), M._pad_x(u, True), M._pad_x(v, False), lim)
        g0, g1E, g1W, g2, Sy, sy = M._faces_x(M._pad_x(H.T, False), M._pad_x(eta.T, False), M._pad_x(v.T, True), M._pad_x(u.T, False), lim)
        g0 = g0.T; g1E = g1E.T; g1W = g1W.T; g2 = g2.T; Sy = Sy.T
        de = -(f0[:, 1:] - f0[:, :-1]) / dx - (g0[1:, :] - g0[:-1, :]) / dx
        dP = -(f1E[:, 1:] - f1W[:, :-1]) / dx - (g2[1:, :] - g2[:-1, :]) / dx + Sx / dx
        dQ = -(f2[:, 1:] - f2[:, :-1]) / dx - (g1E[1:, :] - g1W[:-1, :]) / dx + Sy / dx
        Hs = np.maximum(H, 0.1)
        wet = (H > 0.05) & (m > 0)
        ax = np.where(wet, (dP - u * de) / Hs, 0.0); ay = np.where(wet, (dQ - v * de) / Hs, 0.0)
        b = lu.solve(np.concatenate([ax.ravel(), ay.ravel()]))
        dP = dP + H * (b[:ncell].reshape(ny, nx) - ax) * corr
        dQ = dQ + H * (b[ncell:].reshape(ny, nx) - ay) * corr
        return de, dP, dQ, max(sx, sy)

    t_end = float(c["t_end"]); rec_dt = float(c["rec_dt"]); cfl = float(c["cfl"])
    snaps = [eta.astype(np.float16)]; times = [0.0]; vols = [float(eta.sum() * dx * dx)]
    next_rec = rec_dt
    acc = dict(eta=np.zeros((ny, nx)), P=np.zeros((ny, nx)), Q=np.zeros((ny, nx)), tw=0.0); per_mean = []; per_P = []; per_Q = []; k_per = 0
    t = 0.0; nstep = 0; stop = "t_end"
    smax = math.sqrt(G * (h.max() + 5.0))
    sub = band[:, bx]
    while t < t_end - 1e-9:
        dt = min(cfl * dx / max(smax, 1.0), t_end - t, next_rec - t + 1e-12)
        k1 = rhs(eta, P, Q)
        e1 = eta + dt * k1[0]; P1 = P + dt * k1[1]; Q1 = Q + dt * k1[2]
        k2 = rhs(e1, P1, Q1)
        e2 = 0.75 * eta + 0.25 * (e1 + dt * k2[0]); P2 = 0.75 * P + 0.25 * (P1 + dt * k2[1]); Q2 = 0.75 * Q + 0.25 * (Q1 + dt * k2[2])
        k3 = rhs(e2, P2, Q2)
        eta = eta / 3.0 + 2.0 / 3.0 * (e2 + dt * k3[0]); P = P / 3.0 + 2.0 / 3.0 * (P2 + dt * k3[1]); Q = Q / 3.0 + 2.0 / 3.0 * (Q2 + dt * k3[2])
        smax = max(k1[3], k2[3], k3[3])
        t += dt; nstep += 1
        H = h + eta
        neg = H < 0.0
        if neg.any():
            eta[neg] = -h[neg]; H[neg] = 0.0
        dry = H < 1e-4
        P[dry] = 0.0; Q[dry] = 0.0
        # ---- bands (horizontal velocity only)
        r = 0.5 * (1.0 - math.cos(math.pi * t / t_ramp)) if t < t_ramp else 1.0
        ph = np.exp(-1j * om * t)
        sl = (slice(None), bx)
        wg_in = 1.0 - (1.0 - np.clip(w_in[sl], 0, 1)) ** (dt / M.DT0)
        wg_sd = 1.0 - (1.0 - np.clip(w_sg[sl], 0, 1)) ** (dt / M.DT0)
        wa_sd = 1.0 - np.exp(-sig * chi_s[sl] ** 2 * dt)
        wsd = np.where(side[:, None], wg_sd * (1.0 - s_x[sl]) + wa_sd * s_x[sl], 0.0)
        wdt = np.maximum(wg_in, wsd) * sub
        ftg = np.where(in_band[bx][None, :], fac_in[sl], 1.0) * fac_sd[sl]
        uT = r * ftg * np.real(Uc[sl] * ph); vT = r * ftg * np.real(Vc[sl] * ph)
        Hb = np.maximum(H[sl], 1e-3)
        ub = P[sl] / Hb; vb = Q[sl] / Hb
        P[sl] = Hb * (ub + wdt * (uT - ub)); Q[sl] = Hb * (vb + wdt * (vT - vb))
        if L_ex > 0:
            f = np.exp(-sig * chi_ex[ex_band] ** 2 * dt)[None, :]
            P[:, ex_band] *= f; Q[:, ex_band] *= f
        if k_on > 0:
            brk = (brk | ((eta > k_on * h) & (m > 0))) & ~(eta < k_off * h)
            corr = 1.0 - M._dilate(brk).astype(float)
        if not np.isfinite(eta).all() or not np.isfinite(P).all():
            stop = "blowup"; break
        acc["eta"] += eta * dt; acc["P"] += P * dt; acc["Q"] += Q * dt; acc["tw"] += dt
        if t >= (k_per + 1) * T - 1e-9:
            per_mean.append((acc["eta"] / acc["tw"]).astype(np.float32)); per_P.append((acc["P"] / acc["tw"]).astype(np.float32))
            per_Q.append((acc["Q"] / acc["tw"]).astype(np.float32))
            acc = dict(eta=np.zeros((ny, nx)), P=np.zeros((ny, nx)), Q=np.zeros((ny, nx)), tw=0.0); k_per += 1
        if t >= next_rec - 1e-9:
            snaps.append(eta.astype(np.float16)); times.append(t); vols.append(float(eta.sum() * dx * dx))
            next_rec += rec_dt
    res = dict(t=np.array(times), eta=np.array(snaps), xc=xc, yc=yc, h=h1, stop=stop, wall_s=time.time() - T0w, nstep=nstep, vol=np.array(vols),
               per_mean=np.array(per_mean), per_P=np.array(per_P), per_Q=np.array(per_Q), x_f=x_f, xb_target=xb_t, x_gen=x_gen, x_sw=x_sw, df=df)
    if verbose:
        print("u50 %s: stop %s t %.2f steps %d wall %.1f s vol drift %.2e m3" % (c.get("name"), stop, t, nstep, res["wall_s"], vols[-1] - vols[0]), flush=True)
    return res


# ======================================================================= analysis
def analyse(c, res):
    xs = res["xc"]; ys = res["yc"]; E = res["eta"].astype(np.float32); tt = res["t"]; h = res["h"]; df = res["df"]
    T = float(c["T"]); om = 2 * math.pi / T; dx = xs[1] - xs[0]
    L0 = 2 * math.pi / df.k0
    W = float(c["W"])
    out = dict()
    # 1. generated field on the flat vs the linear target (periods 4..end-1): H = max - min over the last 3 periods
    sel = tt >= max(tt[-1] - 3 * T, 4 * T)
    A_lin = df.complex_amp(ys)                       # linear target everywhere (x grid = cell centres)
    gen = {}
    for xg in (110.0, 128.0, 160.0):
        i = int(np.argmin(np.abs(xs - xg)))
        Hm = E[sel][:, :, i].max(axis=0) - E[sel][:, :, i].min(axis=0)
        Ht = 2 * np.abs(A_lin[i, :])
        rows = {}
        for yq in (1.0, 20.0, 40.0, 60.0, 80.0):
            j = int(np.argmin(np.abs(ys - yq)))
            rows["y%d" % yq] = dict(H=round(float(Hm[j]), 2), H_lin=round(float(Ht[j]), 2), ratio=round(float(Hm[j] / max(Ht[j], 1e-6)), 3))
        inner = ys <= W - c["Ls"]
        rows["mean_ratio_interior"] = round(float(Hm[inner].mean() / Ht[inner].mean()), 3)
        rows["corr_interior"] = round(float(np.corrcoef(Hm[inner], Ht[inner])[0, 1]), 3)
        gen["x%d" % xg] = rows
    out["generation"] = gen
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
    import g47_sfwave as SF
    xt = c["bed"]["x_toe"]; fl = (xs >= 110.0) & (xs <= xt)
    Hax = E[sel][:, 0, :].max(axis=0) - E[sel][:, 0, :].min(axis=0)
    hm = SF.highest_H(c["bed"]["h0"], T)
    out["flat_axis"] = dict(H_max=float(Hax[fl].max()), x_at=float(xs[fl][int(np.argmax(Hax[fl]))]), Hmax2d=float(hm), ratio=float(Hax[fl].max() / hm),
                            crest_max=float(E[sel][:, 0, :][:, fl].max()))
    # 2. per-period breaking: centre row, first x (>= 110) where the per-period envelope / h >= kappa, kappa 1 (A screen rule) and 0.86
    nper = int(tt[-1] // T)
    per = []
    for p in range(3, nper):
        s = (tt >= p * T) & (tt < (p + 1) * T)
        if s.sum() < 4:
            continue
        env = E[s].max(axis=0)                       # (ny, nx)
        hh = np.where(h > 0.3, h, np.nan)
        rr = env / hh[None, :]
        rec = dict(p=p)
        for kap in (0.86, 1.0):
            ok = (rr[0] >= kap) & (xs >= 110.0)
            if ok.any():
                i = int(np.argmax(ok)); rec["x_k%g" % kap] = float(xs[i]); rec["h_k%g" % kap] = float(h[i])
            else:
                rec["x_k%g" % kap] = None
        i_b = int(np.argmin(np.abs(xs - rec["x_k0.86"]))) if rec.get("x_k0.86") else int(np.nanargmax(rr[0]))
        # frame where the centre crest is highest at x_b; crest profile c(y) in xc0 +- L0/2 at that frame
        ss = np.where(s)[0]
        n = ss[int(np.argmax(E[ss, 0, i_b]))]
        e = E[n]
        lo, hi = xs[i_b] - 0.5 * L0, xs[i_b] + 0.5 * L0
        win = (xs >= lo) & (xs <= hi)
        jc = np.where(win)[0][int(np.argmax(e[0, win]))]
        xc0 = xs[jc]
        win = (xs >= xc0 - 0.5 * L0) & (xs <= xc0 + 0.5 * L0)
        cprof = e[:, win].max(axis=1)
        c0 = float(cprof[0])
        sb = (ys >= 70.0) & (ys <= 84.0)
        cs = float(cprof[sb].mean()) if sb.any() else None
        Hc = c0
        c4 = float(np.interp(4 * Hc, ys, cprof))
        thr = (cs or 0) + 0.5 * (c0 - (cs or 0))
        fw = 2 * float(ys[np.argmax(cprof < thr)]) if (cprof < thr).any() else None
        w90 = 2 * float(ys[np.argmax(cprof < 0.9 * c0)]) if (cprof < 0.9 * c0).any() else None
        # curl-width proxy: per row, first frame in [t_n - 1, t_n + 4] where the crest near the centre crest (x within xc(t) -20..+30)
        # reaches eta >= 0.86 h; lag behind the centre row
        lag = np.full(len(ys), np.nan)
        fr = np.where((tt >= tt[n] - 1.0) & (tt <= tt[n] + 4.0))[0]
        xc_t = []
        for q in fr:
            row0 = E[q, 0]
            ww = (xs >= xc0 - 40) & (xs <= xc0 + 60)
            xc_t.append(xs[ww][int(np.argmax(row0[ww]))])
        xc_t = np.array(xc_t)
        hit_t = np.full(len(ys), np.nan)
        for qi, q in enumerate(fr):
            ww = (xs >= xc_t[qi] - 20.0) & (xs <= xc_t[qi] + 30.0) & (h > 0.3)
            rrq = E[q][:, ww] / h[ww][None, :]
            hit = (rrq >= 0.86).any(axis=1)
            new = hit & np.isnan(hit_t)
            hit_t[new] = tt[q]
        t0 = hit_t[0]
        lag = hit_t - t0

        def width(D):
            if not np.isfinite(t0):
                return None
            ok = np.isfinite(lag) & (lag <= D + 1e-9)
            if not ok[0]:
                return 0.0
            nb = int(np.argmax(~ok)) if (~ok).any() else len(ys)
            return 2.0 * (ys[nb - 1] + 0.5 * dx)
        far = ys >= 4 * Hc
        rec.update(t=float(tt[n]), x_b=float(xs[i_b]), h_b=float(h[i_b]), xc0=float(xc0), c0=c0, c_side=cs, P4a=(c0 / cs) if cs else None,
                   c_4Hc=c4, P4b=c0 / c4 if c4 > 0 else None, fwhm_excess=fw, w90=w90,
                   t_onset_proxy=float(t0) if np.isfinite(t0) else None,
                   widths={str(D): width(D) for D in (0.25, 0.75, 1.5)},
                   widths_over_c0={str(D): (width(D) / c0 if width(D) is not None else None) for D in (0.25, 0.75, 1.5)},
                   far_rows_min_lag=(float(np.nanmin(lag[far])) if (far & np.isfinite(lag)).any() else None),
                   lag_rows={str(int(yq)): (round(float(lag[int(np.argmin(np.abs(ys - yq)))]), 3) if np.isfinite(lag[int(np.argmin(np.abs(ys - yq)))]) else None)
                             for yq in (5, 10, 15, 20, 30, 40, 60)},
                   cprof=[round(float(v), 2) for v in cprof[::2]])
        per.append(rec)
    out["periods"] = per
    j = [r for r in per if r["p"] >= 4]
    if j:
        x = np.array([r["x_b"] for r in j]); cc = np.array([r["c0"] for r in j])
        out["periodicity"] = dict(n=len(j), x_b=[r["x_b"] for r in j], x_b_spread=float(x.max() - x.min()), c0=[round(v, 2) for v in cc],
                                  c0_cv=float(cc.std() / cc.mean()), onset_t=[r["t_onset_proxy"] for r in j],
                                  intervals=[round(b["t_onset_proxy"] - a["t_onset_proxy"], 2) for a, b in zip(j[:-1], j[1:])
                                             if a["t_onset_proxy"] and b["t_onset_proxy"]])
    # 3. period-mean levels
    pm = res["per_mean"]
    def lev(x, y):
        i = int(np.argmin(np.abs(xs - x))); jj = int(np.argmin(np.abs(ys - y)))
        return [round(float(v), 3) for v in pm[:, jj, i]]
    xsl = spec_shoreline(c)
    out["levels"] = {"band_core_x60_y1": lev(60, 1), "flat_x140_y1": lev(140, 1), "break_x%d_y1" % res["xb_target"]: lev(res["xb_target"], 1),
                     "inner_surf_x%d_y1" % (xsl - 40): lev(xsl - 40, 1), "inner_surf_x%d_y60" % (xsl - 40): lev(xsl - 40, 60),
                     "swash_x%d_y1" % (xsl - 10): lev(xsl - 10, 1), "swash_x%d_y60" % (xsl - 10): lev(xsl - 10, 60)}
    out["vol_drift_m3"] = float(res["vol"][-1] - res["vol"][0])
    # period-mean depth-averaged currents (mass flux / depth): onshore at the centre / offshore at the sides = rip-type circulation
    if len(res.get("per_P", [])):
        PP = res["per_P"]; QQ = res["per_Q"]; hh = np.maximum(h + 0.0, 0.5)
        def cur(x0, x1, y0, y1):
            ix = (xs >= x0) & (xs <= x1); iy = (ys >= y0) & (ys <= y1)
            u = (PP[:, iy][:, :, ix] / hh[ix][None, None, :]).mean(axis=(1, 2)); v = (QQ[:, iy][:, :, ix] / hh[ix][None, None, :]).mean(axis=(1, 2))
            return dict(u=[round(float(a), 3) for a in u], v=[round(float(a), 3) for a in v])
        xb_ = res["xb_target"]; xsl = spec_shoreline(c)
        out["mean_currents"] = {"centre_surf_y0-10": cur(xb_ + 10, xsl - 10, 0, 10), "mid_surf_y20-40": cur(xb_ + 10, xsl - 10, 20, 40),
                                "side_surf_y60-84": cur(xb_ + 10, xsl - 10, 60, 84), "offshore_centre_y0-10": cur(xb_ - 60, xb_ - 10, 0, 10),
                                "offshore_side_y60-84": cur(xb_ - 60, xb_ - 10, 60, 84)}
    return out


def spec_shoreline(c):
    b = c["bed"]
    return b["x_toe"] + b["h0"] * b["s"]


CASES = {
    "D12_60_m20": dict(T=12.0, thm=60.0, delta=-20.0),
    "D12_75_m40": dict(T=12.0, thm=75.0, delta=-40.0),
    "D10_60_m20": dict(T=10.0, thm=60.0, delta=-20.0),
    "D10_75_m40": dict(T=10.0, thm=75.0, delta=-40.0),
    "D10_75_m20": dict(T=10.0, thm=75.0, delta=-20.0),
    "D10_60_m20_W150": dict(T=10.0, thm=60.0, delta=-20.0, W=150.0, Ls=50.0),
    "D10_60_m20_W85nosb": dict(T=10.0, thm=60.0, delta=-20.0, W=85.0, Ls=0.0),
    "D12_60_m20_W150": dict(T=12.0, thm=60.0, delta=-20.0, W=150.0, Ls=50.0),
    # h0 19 m (FLIP47 S2 / P1c depth): 1:10 from 19 m through the still level to a +6 m beach top (x 430.25)
    "E10_80_m20": dict(T=10.0, thm=80.0, delta=-20.0, Lx=432.0, bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="beach")),
    "E12_80_m20": dict(T=12.0, thm=80.0, delta=-20.0, Lx=432.0, bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="beach")),
    "E10_80_m20_W150": dict(T=10.0, thm=80.0, delta=-20.0, Lx=432.0, W=150.0, Ls=50.0, bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="beach")),
    "E10_80_m20_W85nosb": dict(T=10.0, thm=80.0, delta=-20.0, Lx=432.0, W=85.0, Ls=0.0, bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="beach")),
    "E10_80_m20_W85sb15": dict(T=10.0, thm=80.0, delta=-20.0, Lx=432.0, W=85.0, Ls=15.0, bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="beach")),
    # final layout candidates: toe moved to x 160.25 (gauges 110/128/160 stay on the 19 m flat), W 140 with a 45 m side band generating to x_toe + 20
    "F12_main": dict(T=12.0, thm=80.0, delta=-20.0, Lx=412.0, W=140.0, Ls=45.0, x_gen_off=20.0, bed=dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")),
    "F10_fallback": dict(T=10.0, thm=80.0, delta=-20.0, Lx=412.0, W=140.0, Ls=45.0, x_gen_off=20.0, bed=dict(h0=19.0, x_toe=160.25, s=10.0, kind="beach")),
    # S2 shelf 1.9 m, 20 m reef top, 1:2 drop to a 6 m lagoon, 80 m exit sponge (option A back structure, laterally straight)
    "E10_80_m20_shelf": dict(T=10.0, thm=80.0, delta=-20.0, Lx=462.0, L_ex=80.0,
                             bed=dict(h0=19.0, x_toe=180.25, s=10.0, kind="shelf", h_s=1.9, x_back=371.25, s_back=2.0, h_lag=6.0)),
}


def build(name, over=None):
    c = json.loads(json.dumps(BASE))
    c.update(CASES.get(name, {}))
    if over:
        c.update(over)
    c["name"] = name
    if c.get("a_sum") is None:
        c["a_sum"], lin = a_sum_for(c)
        c["linear_ref"] = dict(x_b0=lin["x_b0"], h_b0=lin["h_b0"], widths_over_Hc=lin["widths_over_Hc"], P4a_lin=lin["P4a_lin"], P4b_lin=lin["P4b_lin"])
    return c


def main(names):
    os.makedirs(OUT, exist_ok=True); os.makedirs(SCR, exist_ok=True)
    for nm in names:
        over = None
        if ":" in nm:                       # name:gain=1.1
            nm, kv = nm.split(":", 1)
            over = {k: float(v) for k, v in (p.split("=") for p in kv.split(","))}
        c = build(nm, over)
        res = run(c)
        an = analyse(c, res)
        tag = nm + ("" if not over else "_" + "_".join("%s%g" % kv for kv in over.items()))
        np.savez_compressed(os.path.join(SCR, "u50_%s.npz" % tag), t=res["t"], eta=res["eta"], xc=res["xc"], yc=res["yc"], h=res["h"], per_mean=res["per_mean"])
        meta = dict(name=tag, case={k: v for k, v in c.items()}, stop=res["stop"], wall_s=res["wall_s"], nstep=res["nstep"], x_f=res["x_f"],
                    xb_target=res["xb_target"], x_gen=res["x_gen"], x_sw=res["x_sw"], analysis=an,
                    tag="computed, screening only (U3 depth-averaged Boussinesq/NSW with a directional band target; no overturning); not a FLIP result")
        json.dump(meta, open(os.path.join(OUT, "u50_%s.json" % tag), "w"), indent=1, default=float)
        g = an["generation"]
        print("== %s  wall %.0f s  a_sum %.3f  x_f %.1f" % (tag, res["wall_s"], c["a_sum"] * c["gain"], res["x_f"]))
        print("  generation H/H_lin interior mean x110 %.3f x128 %.3f x160 %.3f (corr %.2f %.2f %.2f)" % (
            g["x110"]["mean_ratio_interior"], g["x128"]["mean_ratio_interior"], g["x160"]["mean_ratio_interior"],
            g["x110"]["corr_interior"], g["x128"]["corr_interior"], g["x160"]["corr_interior"]))
        print("  x160 rows", {k: v for k, v in g["x160"].items() if k.startswith("y")})
        print("  flat axis", json.dumps(an["flat_axis"]))
        for r in an["periods"]:
            wo = r["widths_over_c0"]
            print("  p%d t %6.2f x_b %5.1f h_b %5.2f (x_k1 %s) c0 %5.2f side %s P4a %s P4b %4.2f fwhm %s w90 %s | w/c0 %s %s %s | far lag %s | lag %s" % (
                r["p"], r["t"], r["x_b"], r["h_b"], r.get("x_k1"), r["c0"], "%.2f" % r["c_side"] if r["c_side"] else "-",
                "%.2f" % r["P4a"] if r["P4a"] else "-", r["P4b"] or 0, r["fwhm_excess"], r["w90"],
                *["%.2f" % wo[k] if wo[k] is not None else "-" for k in ("0.25", "0.75", "1.5")], r["far_rows_min_lag"], r["lag_rows"]))
        if an.get("periodicity"):
            print("  periodicity", json.dumps(an["periodicity"]))
        print("  levels", json.dumps(an["levels"]))
        if an.get("mean_currents"):
            print("  mean currents", json.dumps(an["mean_currents"]))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main(sys.argv[1:])
