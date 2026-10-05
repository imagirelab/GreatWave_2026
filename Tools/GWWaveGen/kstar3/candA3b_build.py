# -*- coding: utf-8 -*-
"""Q21 candidate A3b, step 2 (pipeline): build the 400 x 240 sheet from the design field (candA3b_sheet.Design).

  rows c >= c_tpl : design field (placed smoothed model, shoulder stretch s_y(c), barrel shell behind the painted
                    pocket, edge-only carve) -> upper boundary -> our foot / trough -> 400 columns (landmarks)
  rows c <  c_tpl : the near shoulder beyond the model's end: the c_tpl row carried along a continued crest line and
                    scaled (height from the painting-view silhouette cone, width ~ sqrt), down to the sea
  then the landmark fractions and the grid are smoothed along the crest (local-linear Gaussian, rows stay planar).
Whole-body / low-frequency only: s_y(c) is one number per row, smoothed along c.
usage: py -3.10 candA3b_build.py candA3b_params.json out_rows.npz
"""
import sys, os, json, math, time
import numpy as np
from scipy.ndimage import gaussian_filter1d, maximum_filter1d
from scipy.interpolate import PchipInterpolator
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B
import candA3b_sheet as SH
import fin2_design as FD
import fin2_relax as RX


def _unused_upper_sky_floor(D, allowed):
    """per column a: lowest y of the top-most sky run (the painted outline's cone seen in this plane); nan if none."""
    sky = ~allowed
    ny = sky.shape[0]
    out = np.full(sky.shape[1], np.nan)
    top = sky[-1]
    for j in np.nonzero(top)[0]:
        k = ny - 1
        while k > 0 and sky[k - 1, j]:
            k -= 1
        out[j] = D.yy[k]
    return out


def touch_scale(D, c, frac=0.35):
    """vertical scale at which the row's upper profile first touches the painted outline's cone (from inside)."""
    prm = dict(D.prm); prm["carve"] = False
    D0 = D.prm; D.prm = prm
    try:
        P = D.row_curve(c, 1.0)
    finally:
        D.prm = D0
    allowed, _ = D.allowed(c)
    ytop = SH.upper_sky_floor(D.yy, allowed)
    H = P[:, 1].max()
    m = P[:, 1] > frac * H
    j = np.clip(np.round((P[m, 0] - D.aa[0]) / D.step).astype(int), 0, len(D.aa) - 1)
    yt = ytop[j]
    ok = np.isfinite(yt)
    if not ok.any():
        return 1.0, H
    return float(np.min(yt[ok] / P[m, 1][ok])), H


_D = None


def _init(prm):
    global _D
    _D = SH.Design(prm)


def _job_touch(cc):
    return touch_scale(_D, cc)[0]


def _job_row(args):
    cc, syr, fam = args
    inf = {}
    P = _D.row_curve(cc, syr, inf, fam)
    return P, inf


def _job_field(args):
    cc, syr, fam = args
    inf = {}
    d, _ = _D.row_sdf(cc, syr, inf, fam, carve=not _D.prm.get("carve_after_smooth", False))
    return d.astype(np.float32), inf


def _job_carve(args):
    cc, d = args
    return _D.extract(ndi_blur(_D.carve(cc, d), _D.prm.get("blur_px", 1.0)))


def ndi_blur(d, px):
    from scipy import ndimage as ndi
    return ndi.gaussian_filter(d, px)


def _job_ytop(cc):
    allowed, _ = _D.allowed(cc, _D.prm.get("carve_smooth_m", 0.25))
    return SH.upper_sky_floor(_D.yy, allowed)


def main(prm_path, out, log=print, procs=5):
    t0 = time.time()
    prm = json.load(open(prm_path, encoding="utf-8"))
    c = FD.c_rows({"grid": prm["grid"]})
    D = SH.Design(prm)
    nv = len(c)
    b = prm["build"]
    c_tpl = b["c_tpl"]
    # ---- 1. shoulder stretch s_y(c): touch the painted outline's cone, upper envelope along c
    sy = np.ones(nv)
    rows_fit = [r for r in range(nv) if c_tpl - 0.01 <= c[r] <= b["sy_c1"]]
    import multiprocessing as mp
    pool = mp.Pool(procs, initializer=_init, initargs=(prm,))
    sel = rows_fit[::b.get("sy_every", 3)]
    raw = dict(zip(sel, pool.map(_job_touch, [float(c[r]) for r in sel])))
    rr = np.array(sorted(raw)); vv = np.array([raw[r] for r in rr])
    sy_fit = np.interp(c, c[rr], vv)
    sy_fit = np.where((c >= c_tpl - 0.01) & (c <= b["sy_c1"]), sy_fit, 1.0)
    env = maximum_filter1d(sy_fit, size=b.get("sy_env_rows", 9))
    env = gaussian_filter1d(env, b.get("sy_sig_rows", 4.0), mode="nearest")
    sy = np.clip(env * (1.0 + b["sy_over"]), 1.0, b["sy_max"])
    # fade to 1 at the main crest (the crest top is the K* anchor)
    sy = 1.0 + (sy - 1.0) * SH.smoothstep((b["sy_c1"] - c) / max(b["sy_c1"] - b["sy_c0"], 1e-6))
    log("s_y: " + " ".join("%+.1f:%.3f" % (c[r], sy[r]) for r in range(0, nv, 12)))
    # ---- 2. design rows: raw curves, then the model's body width W (back at 0.5 H) smoothed along c, then post
    raws = {}
    info = {}
    fam = prm["families"]
    jobs = [(r, "M") for r in range(nv) if c_tpl - 0.01 <= c[r] <= fam["M1"]] + [(r, "S") for r in range(nv) if c[r] >= fam["S0"]]
    res_ = pool.map(_job_field, [(float(c[r]), float(sy[r]), f_) for r, f_ in jobs])
    fM, fS = {}, {}
    for (r, f_), (d_, inf) in zip(jobs, res_):
        (fM if f_ == "M" else fS)[r] = d_
        info.setdefault(r, {}).update({(k_ if f_ == "M" else "S_" + k_): v_ for k_, v_ in inf.items()})
    del res_
    # blend the families as implicit fields (a morph, not a cut), then smooth the field stack along the crest:
    # one implicit surface, smooth across rows (no per-row folds); the painting-view edges are locked afterwards
    rows_d = sorted(set(fM) | set(fS))
    Fd = {}
    for r in rows_d:
        if r in fM and r in fS:
            w_ = float(SH.smoothstep((c[r] - fam["S0"]) / (fam["M1"] - fam["S0"])))
            kb = fam.get("blend_k", 0.5)
            if fam.get("blend_mode", "union") == "linear":
                # a morph of the two implicit fields (the inner face slides from the model's to the barrel's)
                Fd[r] = ((1 - w_) * fM[r] + w_ * fS[r]).astype(np.float32)
            else:
                # weighted soft union: d_M at w 0, d_S at w 1, the union of both in between (no dip of the crest)
                Fd[r] = (-kb * np.logaddexp(np.log(max(1 - w_, 1e-6)) - fM[r] / kb, np.log(max(w_, 1e-6)) - fS[r] / kb)).astype(np.float32)
        else:
            Fd[r] = fM[r] if r in fM else fS[r]
    del fM, fS
    tabf = b["field_sigma_c"]
    sgf = np.interp(c, [t_[0] for t_ in tabf], [t_[1] for t_ in tabf])
    rarr = np.array(rows_d)
    smoothed = []
    lz = b.get("lower_zone")
    def stack_avg(r, sg):
        dc = c[rarr] - c[r]
        sel_ = np.abs(dc) < 3.0 * sg
        wk = np.exp(-0.5 * (dc[sel_] / sg) ** 2)
        acc = np.zeros_like(Fd[r])
        for k_, w_ in zip(rarr[sel_], wk):
            acc += w_ * Fd[k_]
        return acc / wk.sum()
    for r in rows_d:
        F1 = stack_avg(r, sgf[r])
        if lz:
            # the lower front / back of the shoulder (below the b region and the lip) is smoothed harder along the crest:
            # the smoothed reference still carries the sculpture's vertical flutes there
            wc = float(SH.smoothstep((c[r] - lz["c0"]) / 1.5) * SH.smoothstep((lz["c1"] - c[r]) / 1.5))
            if wc > 0:
                F2 = stack_avg(r, lz["sigma_m"])
                wy = SH.smoothstep((lz["y1"] - D.YY) / (lz["y1"] - lz["y0"])) * wc
                F1 = (1 - wy) * F1 + wy * F2
        smoothed.append(F1)
    if prm.get("carve_after_smooth", False):
        # the carve comes AFTER the along-crest smoothing: the interior is smooth, the painted silhouette is cut exactly
        Ps = pool.map(_job_carve, [(float(c[r]), dd) for r, dd in zip(rows_d, smoothed)], chunksize=4)
    else:
        Ps = [D.extract(dd) for dd in smoothed]
    del smoothed
    for r, P in zip(rows_d, Ps):
        if P is None or P[:, 1].max() < 0.5:
            raws[r] = None; continue
        raws[r] = SH.smooth_poly(P, prm["post"].get("smooth_m", 0.12))
    rawsS = {}
    log("design fields done %.0fs" % (time.time() - t0))
    Wr = np.full(nv, np.nan); Hr = np.full(nv, np.nan)
    for r, P in list(raws.items()) + [(r_, P_) for r_, P_ in rawsS.items() if r_ not in raws]:
        if P is None:
            continue
        H = P[:, 1].max(); Hr[r] = H
        if c[r] > b["w_c1"]:
            continue
        it = int(np.argmax(P[:, 1]))
        back = P[:it + 1]
        k = np.nonzero(back[:, 1] >= 0.5 * H)[0]
        if len(k):
            Wr[r] = P[it, 0] - back[k[0], 0]
    ok = np.isfinite(Wr) & np.isfinite(Hr)
    ratio = np.interp(np.arange(nv), np.nonzero(ok)[0], (Wr / Hr)[ok])
    ratio = gaussian_filter1d(ratio, b.get("w_sig_rows", 6.0), mode="nearest")
    ratio = np.clip(ratio, b["w_ratio_min"], b["w_ratio_max"])
    rows = {}; rowsS = {}
    fa = b.get("fullness")
    wsc = np.ones(nv)
    prot = {r: float(SH.smoothstep((c[r] - fam["S0"]) / (fam["M1"] - fam["S0"]))) * b.get("protect_scale", 1.0) for r in raws}
    if fa:
        # fullness (Q21-2): the hidden back (dome width) per row so that the section area above still water is
        # `ratio` x the smoothed reference section's area (bisection on the width; bounded by the barrel wall);
        # the width scale is then smoothed along the crest (no row-to-row steps)
        have_w = []
        for r, P in raws.items():
            if P is None or not (fa["c0"] <= c[r] <= fa["c1"]):
                continue
            W = float(ratio[r] * P[:, 1].max())
            aa_, yy_, g_ = D.pf.section(c[r], step=0.1)
            tgt_area = float((g_[yy_ >= 0] > 0.5).sum()) * 0.01 * fa["ratio"]
            lo_, hi_ = fa["w_lo"], fa["w_hi"]
            for _ in range(9):
                mid = 0.5 * (lo_ + hi_)
                Qm, _, _ = SH.post_row(P, prm, W * mid, prot[r], float(c[r]))
                if SH.area_above_sea(Qm) > tgt_area:
                    hi_ = mid
                else:
                    lo_ = mid
            wsc[r] = 0.5 * (lo_ + hi_); have_w.append(r)
            info.setdefault(r, {})["target_area_m2"] = tgt_area
        hw = np.array(have_w)
        ww = np.interp(np.arange(nv), hw, wsc[hw])
        fade = SH.smoothstep((c - (fa["c0"] - 2.0)) / 2.0) * SH.smoothstep(((fa["c1"] + 2.0) - c) / 2.0)
        ww = 1.0 + (ww - 1.0) * fade
        wsc = C.gauss1d_nonuniform(ww, c, fa.get("smooth_c_m", 1.2))
    # the trough line (a of the trough bottom) smoothed along the crest: no back-and-forth grooves
    atr = np.full(nv, np.nan)
    for r, P in raws.items():
        if P is None:
            continue
        W = float(ratio[r] * P[:, 1].max() * wsc[r]) if b.get("bell", True) else None
        atr[r] = SH.post_row(P, prm, W, prot[r], float(c[r]))[2]["a_trough"]
    okt = np.isfinite(atr)
    atr_s = C.gauss1d_nonuniform(np.interp(np.arange(nv), np.nonzero(okt)[0], atr[okt]), c, b.get("trough_smooth_c_m", 2.5))
    for r, P in raws.items():
        if P is None:
            rows[r] = None; continue
        Hh = P[:, 1].max()
        W = float(ratio[r] * Hh * wsc[r]) if b.get("bell", True) else None
        Q, lm, pinf = SH.post_row(P, prm, W, prot[r], float(c[r]), atr_s[r])
        pinf["w_scale"] = float(wsc[r]); pinf["area_m2"] = SH.area_above_sea(Q)
        info.setdefault(r, {}).update(pinf)
        rows[r] = (Q, lm)
    log("W/H: " + " ".join("%+.1f:%.2f" % (c[r], ratio[r]) for r in range(80, nv, 10)))
    # ---- 3. landmark fractions smoothed along c (per family), resample, blend the families in their overlap
    keys = SH.LMK

    def resample_family(rows_):
        fr = {k: np.full(nv, np.nan) for k in keys}
        for r, v in rows_.items():
            if v is None:
                continue
            Q, lm = v
            s_ = C.arclen(Q[:, 0], Q[:, 1])
            for k in keys:
                fr[k][r] = s_[lm[k]] / s_[-1]
        Af = np.zeros((nv, 400)); Yf = np.zeros((nv, 400))
        hv = sorted(r for r, v in rows_.items() if v is not None)
        if not hv:
            return Af, Yf, set()
        idx = np.array(hv, int)
        for k in keys:
            v = fr[k][idx]
            fr[k][idx] = gaussian_filter1d(v, b.get("lm_sig_rows", 2.0), mode="nearest")
        for r in hv:
            Q, lm = rows_[r]
            s_ = C.arclen(Q[:, 0], Q[:, 1])
            lm2 = {k: int(np.argmin(np.abs(s_ - fr[k][r] * s_[-1]))) for k in keys}
            for k in ("j_top", "j_tip"):
                if abs(s_[lm2[k]] - s_[lm[k]]) > b.get("lm_slide_max", 0.6):
                    lm2[k] = lm[k]
            for a_, b_ in zip(keys[:-1], keys[1:]):
                lm2[b_] = max(lm2[b_], lm2[a_] + 1)
            Af[r], Yf[r] = SH.resample400(Q, lm2)
        return Af, Yf, set(hv)

    AM, YM, hM = resample_family(rows)
    AS, YS, hS = resample_family(rowsS)
    A = np.zeros((nv, 400)); Y = np.zeros((nv, 400))
    for r in range(nv):
        if r in hM and r in hS:
            w_ = float(SH.smoothstep((c[r] - fam["S0"]) / (fam["M1"] - fam["S0"])))
            A[r] = (1 - w_) * AM[r] + w_ * AS[r]; Y[r] = (1 - w_) * YM[r] + w_ * YS[r]
        elif r in hM:
            A[r], Y[r] = AM[r], YM[r]
        elif r in hS:
            A[r], Y[r] = AS[r], YS[r]
    have = np.array(sorted(hM | hS))
    rows = {r: True for r in have}
    # ---- 4. near shoulder beyond the model: the template row carried along a continued crest line, scaled, and
    # morphed into a plain round hump (no curl) toward the near end; heights touch the painted outline's cone
    rt = int(have.min())
    At, Yt = A[rt].copy(), Y[rt].copy()
    Ht = Yt.max(); jt = int(np.argmax(Yt[:200])); a_t = At[jt]
    kaT = np.array(b["kstar_aT"], float)
    aT = PchipInterpolator(kaT[:, 0], kaT[:, 1], extrapolate=True)
    a_off = a_t - float(aT(c[rt]))
    kH = np.array(b["near_H"], float)
    Hn = PchipInterpolator(kH[:, 0], kH[:, 1], extrapolate=False)
    Wt = float(ratio[rt] * Ht)

    def hump(ac, H, W):
        fk = prm["post"]["bell"]
        kn = [(ac - W * f, u * H) for u, f in zip(fk["u"], fk["f"])]
        fr_ = [(ac + 0.35 * W, 0.8 * H), (ac + 0.8 * W, 0.45 * H), (ac + 1.3 * W, 0.08 * H), (ac + 1.7 * W, -0.15 * H), (ac + 2.8 * W, 0.0)]
        ka = np.array([ac - W * fk["f"][0] - 3.0] + [k_[0] for k_ in kn] + [ac] + [k_[0] for k_ in fr_] + [ac + 2.8 * W + 3.0])
        ky = np.array([0.0] + [k_[1] for k_ in kn] + [H] + [k_[1] for k_ in fr_] + [0.0])
        f = PchipInterpolator(ka, ky)
        aa = np.linspace(ka[1], ka[-2], 1500); Q = np.stack([aa, f(aa)], -1)
        idx = lambda a_: int(np.argmin(np.abs(aa - a_)))
        lm = {"j_B": 0, "j_top": idx(ac), "j_tip": idx(ac + 0.35 * W), "j_corner": idx(ac + 0.8 * W), "j_facebot": idx(ac + 1.7 * W), "j_E": len(aa) - 1}
        return SH.resample400(Q, lm)

    def near_row(cc, H):
        ac = float(aT(cc)) + a_off * math.exp(-(c[rt] - cc) / b["crest_relax_m"])
        syr = H / Ht
        sar = b["near_sa0"] + (1 - b["near_sa0"]) * syr
        Ar = ac + (At - a_t) * sar; Yr = Yt * syr
        wm = float(SH.smoothstep((cc - (c[rt] - b["morph_len"])) / b["morph_len"]))
        Ah, Yh = hump(ac, H, max(Wt * sar, 0.5))
        Ar = wm * Ar + (1 - wm) * Ah; Yr = wm * Yr + (1 - wm) * Yh
        Ar[:C.LM["j_B"] + 1] = np.linspace(min(-49.2, Ar[C.LM["j_B"]] - 5), Ar[C.LM["j_B"]], C.LM["j_B"] + 1)
        Ar[C.LM["j_E"]:] = np.linspace(Ar[C.LM["j_E"]], max(33.0, Ar[C.LM["j_E"]] + 5), 400 - C.LM["j_E"])
        return Ar, Yr

    Hnear = np.zeros(nv)
    ytops = dict(zip(range(rt), pool.map(_job_ytop, [float(c[r]) for r in range(rt)]))) if b.get("near_touch", True) else {}
    for r in range(rt - 1, -1, -1):
        cc = c[r]
        H = float(np.nan_to_num(Hn(np.clip(cc, kH[0, 0], kH[-1, 0])), nan=0.0)) / float(Hn(kH[-1, 0])) * Ht
        if b.get("near_touch", True) and H > 0.8:
            ytop = ytops[r]
            for _ in range(3):
                Ar, Yr = near_row(cc, H)
                m = Yr > 0.35 * Yr.max()
                j = np.clip(np.round((Ar[m] - D.aa[0]) / D.step).astype(int), 0, len(D.aa) - 1)
                yt = ytop[j]; okk = np.isfinite(yt)
                if not okk.any():
                    break
                H = H * float(np.min(yt[okk] / np.maximum(Yr[m][okk], 1e-3))) * (1.0 + b.get("near_over", 0.0))
                H = min(H, Ht * b.get("near_H_max_frac", 1.25))
        Hnear[r] = H
    Hs = gaussian_filter1d(np.maximum.accumulate(Hnear[:rt][::-1])[::-1] * 0 + Hnear[:rt], b.get("near_H_sig_rows", 3.0), mode="nearest") if rt > 0 else Hnear[:0]
    last_a = None
    for r in range(rt - 1, -1, -1):
        H = float(Hs[r]) if Hnear[r] > 0 else 0.0
        if H < 0.05:
            # flat sea rows keep the column layout of the last hump row (consistent columns across rows: no folds
            # when the rows are smoothed along the crest)
            if last_a is None:
                A[r] = np.linspace(-49.2, 33.0, 400)
            else:
                A[r] = last_a
            Y[r] = 0.0; continue
        A[r], Y[r] = near_row(c[r], H)
        last_a = np.maximum.accumulate(A[r] + np.arange(400) * 1e-4)
    pool.close()
    log("near H: " + " ".join("%+.1f:%.2f" % (c[r], Y[r].max()) for r in range(0, rt, 8)))
    # far end beyond the last design row: flat sea
    for r in range(nv):
        if r not in rows or rows[r] is None:
            if c[r] > 0 and (A[r] == 0).all():
                A[r] = np.linspace(-49.2, 33.0, 400); Y[r] = 0.0
    # ---- 5. along-crest smoothing (local-linear Gaussian: keeps trends at the ends)
    A0, Y0 = A.copy(), Y.copy()
    tab = b["relax_sigma_c"]
    sg = np.interp(c, [t_[0] for t_ in tab], [t_[1] for t_ in tab])
    w = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0)
    w = np.maximum(w, np.roll(w, 1, 1)); w = np.maximum(w, np.roll(w, -1, 1))
    A, Y = RX.cross_rows_ll(A, Y, c, sg, weight=w)
    # hidden parts (the back from the sea to below the crest, the barrel's lower wall, the trough) are smoothed
    # harder along the crest: one smooth round mass, no row-to-row grooves (the painting sees only the edges)
    for (j0, j1, j2, j3, tabk) in b.get("zone_smooth", []):
        sgz = np.interp(c, [t_[0] for t_ in tabk], [t_[1] for t_ in tabk])
        Az, Yz = RX.cross_rows_ll(A, Y, c, sgz, weight=w)
        jj = np.arange(400)
        wz = np.clip(np.minimum((jj - j0) / max(j1 - j0, 1), (j3 - jj) / max(j3 - j2, 1)), 0, 1)
        wz = wz * wz * (3 - 2 * wz)
        A = A + (Az - A) * wz[None, :]; Y = Y + (Yz - Y) * wz[None, :]
    hs = b.get("hidden_smooth")
    if hs:
        # everything that does not form the painting-view silhouette is smoothed harder along the crest (one round
        # mass, no row-wise columns / grooves); the silhouette-forming band keeps its shape (the painting's edges)
        import candA3b_fit as FI
        import fin2_warp as W_
        from scipy.ndimage import binary_dilation, gaussian_filter
        pt = W_.Painting()
        sil, _, _ = FI.silhouette_vertices(pt, c, A, Y, near_px=60.0, tol_px=2.0)
        band = binary_dilation(sil, np.ones((2 * hs["rows"] + 1, 2 * hs["cols"] + 1), bool))
        wgt = 1.0 - gaussian_filter(band.astype(float), (hs["rows"] / 2.0, hs["cols"] / 2.0))
        wgt = np.clip(wgt, 0, 1) * SH.smoothstep((Y - hs.get("y0", 0.3)) / (hs.get("y1", 1.5) - hs.get("y0", 0.3)))
        # behind the painted sky pocket (c > c_pocket) hidden geometry can come into view when smoothed: there only the
        # back (behind the crest) is smoothed
        jj = np.arange(A.shape[1])[None, :]
        near = SH.smoothstep((hs["c_pocket"] - c[:, None]) / 1.5)
        wgt = wgt * np.maximum(near, SH.smoothstep((82.0 - jj) / 30.0))
        for _ in range(hs.get("iters", 2)):
            As, Ys = RX.cross_rows_ll(A, Y, c, hs["sigma_m"])
            A = A + wgt * (As - A); Y = Y + wgt * (Ys - Y)
        log("hidden smooth: %d silhouette vertices, band %d" % (int(sil.sum()), int(band.sum())))
    tt = b.get("tail_taper")
    if tt:
        # the far end runs into the sea by the last row (no cut face at the end of the grid); a flattened curl is
        # unfolded toward the row's monotone version so that it does not lie on itself
        f = np.where(c > tt[0], SH.smoothstep((tt[1] - c) / (tt[1] - tt[0])), 1.0)
        jj = np.arange(A.shape[1]) * 1e-4
        Am = np.maximum.accumulate(A, axis=1) + jj[None, :]
        A = f[:, None] * A + (1 - f[:, None]) * Am
        Y = Y * f[:, None]
    np.savez_compressed(out, A=A, Y=Y, c=c, A_raw=A0, Y_raw=Y0, sy=sy)
    json.dump({"rows": {str(int(r)): {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in inf.items()} for r, inf in info.items()},
               "sy": sy.tolist(), "c": c.tolist(), "seconds": time.time() - t0},
              open(os.path.splitext(out)[0] + "_build.json", "w"), indent=1, default=float)
    log("done %s  H0 %.2f  Hmax %.2f at c %.2f  %.0fs" % (out, Y[159].max(), Y.max(), c[int(np.argmax(Y.max(1)))], time.time() - t0))
    return out


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
