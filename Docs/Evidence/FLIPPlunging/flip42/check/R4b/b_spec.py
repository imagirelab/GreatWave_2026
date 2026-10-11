# -*- coding: utf-8 -*-
"""R4b 確かめ：A1・測った S・A2'・A3'（直した符号と 10/9 の符号）・B1・測る点の最大を、記録から自前で出す。
py -3.10 b_spec.py → b_spec.json
A3' の符号の確かめ：(1) 模型を −15 の点で時系列に戻し、測った時系列・線形の時系列との時刻のずれを比べる。
(2) 合成の試し：線形の値を入口で 0.5 s 早めた・成分を 1 % 速くした場合に、模型の焦点がどちらへ動くか。
"""
import math, sys
import numpy as np
import b_common as B

RUNS = ["R1b", "R2", "R3", "R4d"]


def spectra(D, C, P, off, xp, x_rel, t):
    em = np.nan_to_num(B.gauge_series(D, xp + x_rel, off))
    el = B.linear_series(C, x_rel, t)
    return em, el, np.fft.rfft(em), np.fft.rfft(el), np.fft.rfftfreq(len(t), 1 / B.FPS)


def wmean(v, w):
    return float((v * w).sum() / w.sum())


def model_field(C, comp_amp, comp_phase_shift, kdiff, gexp, xs, ts, x_e, dx2):
    """E(x,t) = Σ a_i A_i g_i^((x−x_e)/Δx) cos(k_i(x−x_b) − ω_i(t−t_b) + s_i + kdiff_i (x − x_e))。"""
    E = np.zeros((len(xs), len(ts)))
    for i in range(len(C["f"])):
        th_x = C["k"][i] * (xs - C["xb"]) + comp_phase_shift[i] + kdiff[i] * (xs - x_e)
        amp_x = C["a"][i] * comp_amp[i] * np.power(gexp[i], (xs - x_e) / dx2)
        th_t = C["om"][i] * (ts - C["tb"])
        # cos(A − B) = cos A cos B + sin A sin B
        E += np.outer(amp_x * np.cos(th_x), np.cos(th_t)) + np.outer(amp_x * np.sin(th_x), np.sin(th_t))
    return E


def focus(E, xs, ts, Lc):
    ix, it = np.unravel_index(np.argmax(E), E.shape)
    row = E[:, it]
    m = (xs > xs[ix]) & (xs <= xs[ix] + 0.75 * Lc)
    H75 = row[ix] - row[m].min()
    j = ix
    while j + 1 < len(row) and row[j + 1] < row[j]:
        j += 1
    Hloc = row[ix] - row[j]
    return dict(x=float(xs[ix]), t=float(ts[it]), crest=float(E[ix, it]), H75=float(H75), Hloc=float(Hloc))


def a3p(C, Rb, e_i, g_i, x_e, dx2, nx, nt, sign=+1):
    """sign=+1：直した符号（−arg R、+(kk−k)(x−x_e)）。sign=−1：10/9 の符号。"""
    Lc, Tc = C["Lc"], C["Tc"]
    xs = C["xb"] + np.linspace(-1.0, 1.5, nx) * Lc
    ts = C["tb"] + np.linspace(-1.5, 3.0, nt) * Tc
    kk = C["k"] / (1 - e_i)
    E0 = model_field(C, np.ones(len(C["f"])), np.zeros(len(C["f"])), np.zeros(len(C["f"])), np.ones(len(C["f"])), xs, ts, x_e, dx2)
    E1 = model_field(C, np.abs(Rb), -sign * np.angle(Rb), sign * (kk - C["k"]), g_i, xs, ts, x_e, dx2)
    f0 = focus(E0, xs, ts, Lc); f1 = focus(E1, xs, ts, Lc)
    return dict(dx_Lc=(f1["x"] - f0["x"]) / Lc, dt_Tc=(f1["t"] - f0["t"]) / Tc, dx_m=f1["x"] - f0["x"], dt_s=f1["t"] - f0["t"],
                crest_ratio=f1["crest"] / f0["crest"], H_ratio_075Lc=f1["H75"] / f0["H75"], H_ratio_first_trough=f1["Hloc"] / f0["Hloc"],
                lin_focus=[f0["x"], f0["t"]], model_focus=[f1["x"], f1["t"]])


def series_at(C, Rb, e_i, g_i, x_e, dx2, x, t, sign):
    kk = C["k"] / (1 - e_i)
    th = (C["k"] * (x - C["xb"]))[None, :] - C["om"][None, :] * (t[:, None] - C["tb"]) - sign * np.angle(Rb)[None, :] \
        + sign * ((kk - C["k"]) * (x - x_e))[None, :]
    amp = C["a"] * np.abs(Rb) * np.power(g_i, (x - x_e) / dx2)
    return (amp[None, :] * np.cos(th)).sum(1)


def xcorr_lag(a, b, t, win):
    """a が b より何秒早いか（+ は a が早い）。窓の中の相互相関の最大、0.01 s まで補間。"""
    m = (t >= win[0]) & (t <= win[1])
    aa = a[m] - a[m].mean(); bb = b[m] - b[m].mean()
    lags = np.arange(-72, 73)
    cc = np.array([np.dot(np.roll(aa, -L), bb) for L in lags])
    j = int(np.argmax(cc))
    if 0 < j < len(cc) - 1:
        y0, y1, y2 = cc[j - 1], cc[j], cc[j + 1]
        d = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
    else:
        d = 0.0
    return float(-(lags[j] + d) / B.FPS)


def main():
    P = B.plan(); C = B.components(P)
    gz = P["gauges"]
    t_end = P["tank"]["t_end"]
    band = P["criteria"]["A2p_propagation"]["band_Hz"]
    out = {}
    for rid in RUNS:
        cf = B.cfg(rid); xp = cf["parms"]["x_p"]
        D = B.hf(rid)
        off_mid = B.still(D, xp, "mid"); off_in = B.still(D, xp, "inner")
        win = D["t"] <= t_end + 1e-9
        Dw = dict(D); Dw["eta"] = D["eta"][win]; Dw["t"] = D["t"][win]
        t = Dw["t"]
        o = dict(frames=[int(D["frames"].min()), int(D["frames"].max()), len(D["frames"])], nfiles=D["nfiles"], overlap_frames=D["ndup"],
                 overlap_frames_differing=D["ndiff"], still_mid=off_mid, still_inner=off_in, n_window=int(win.sum()))
        x_e = gz["band_exit"]["x_rel"]; x15 = gz["kc(x-xb)=-15"]["x_rel"]; x10 = gz["kc(x-xb)=-10"]["x_rel"]; x5 = gz["kc(x-xb)=-5"]["x_rel"]
        em, el, Fm, Fl, fr = spectra(Dw, C, P, off_mid, xp, x_e, t)
        em2, el2, Fm2, Fl2, _ = spectra(Dw, C, P, off_mid, xp, x15, t)
        em3, el3, Fm3, Fl3, _ = spectra(Dw, C, P, off_mid, xp, x10, t)
        em5, el5, _, _, _ = spectra(Dw, C, P, off_mid, xp, x5, t)
        R = Fm / np.where(abs(Fl) > 0, Fl, 1); R2 = Fm2 / np.where(abs(Fl2) > 0, Fl2, 1)
        wl = abs(Fl) ** 2
        f = C["f"]; df = C["df"]
        sub = []
        for (i0, i1) in [(1, 11), (12, 21), (22, 32)]:
            m = (fr >= f[i0 - 1] - df / 2) & (fr <= f[i1 - 1] + df / 2)
            sub.append(dict(comp=[i0, i1], amp=wmean(abs(R[m]), wl[m]), phase=wmean(np.angle(R[m]), wl[m]), nbins=int(m.sum())))
        o["A1"] = sub
        mb = (fr >= f[0] - df / 2) & (fr <= f[-1] + df / 2)
        kf = B.wavenumber(2 * np.pi * fr, C["h"])
        o["S_meas"] = float(P["lab"]["S"] * (kf[mb] * abs(Fm[mb])).sum() / (kf[mb] * abs(Fl[mb])).sum())
        # A2'
        m2 = (fr >= band[0]) & (fr <= band[1])
        dphi = np.angle(R2[m2] / R[m2]); dx2 = x15 - x_e
        e_f = -dphi / (kf[m2] * dx2); g_f = abs(R2[m2]) / abs(R[m2]); w2 = wl[m2]
        o["A2p"] = dict(speed_err_wmean=wmean(e_f, w2), amp_change_wmean=wmean(g_f, w2), dx=dx2,
                        f=fr[m2].tolist(), e=e_f.tolist(), g=g_f.tolist())
        s1113 = (fr[m2] >= 0.11) & (fr[m2] <= 0.13)
        o["A2p"]["e_0p11_0p13"] = [float(e_f[s1113].min()), float(e_f[s1113].max())]
        # B1
        cg = B.group_speed(2 * np.pi * fr, C["h"])
        lo = (fr > 0) & (fr < f[0] - df / 2); hi = fr > f[-1] + df / 2

        def flux(Fm_, Fl_):
            pin = (abs(Fm_[mb]) ** 2 * cg[mb]).sum() / (abs(Fl_[mb]) ** 2 * cg[mb]).sum()
            Ein = (abs(Fm_[mb]) ** 2 * cg[mb]).sum()
            return float(pin), float((abs(Fm_[lo]) ** 2 * cg[lo]).sum() / Ein), float((abs(Fm_[hi]) ** 2 * cg[hi]).sum() / Ein)
        pe = flux(Fm, Fl); p15 = flux(Fm2, Fl2); p10 = flux(Fm3, Fl3)
        o["B1"] = dict(flux_exit=pe[0], flux_m15=p15[0], flux_m10=p10[0], loss=1 - p10[0] / pe[0], outside_low_m10=p10[1], outside_high_m10=p10[2])
        # 測る点の最大
        o["gauge_max"] = {}
        for nm, (a_, b_) in dict(m15=(em2, el2), m10=(em3, el3), m5=(em5, el5)).items():
            o["gauge_max"][nm] = dict(max=float(a_.max()), t_max=float(t[np.argmax(a_)]), lin_max=float(b_.max()), t_lin=float(t[np.argmax(b_)]))
        # A3'
        Rb = np.interp(f, fr, R.real) + 1j * np.interp(f, fr, R.imag)
        e_i = np.interp(f, fr[m2], e_f); g_i = np.interp(f, fr[m2], g_f)
        a3 = {}
        for nm, (nx, nt) in dict(g501=(501, 451), g1001=(1001, 901)).items():
            a3[nm] = dict(fixed=a3p(C, Rb, e_i, g_i, x_e, dx2, nx, nt, +1), old=a3p(C, Rb, e_i, g_i, x_e, dx2, nx, nt, -1))
        # 入れ方の感度（501 × 451、直した符号）：振幅と位相で補間
        Rb2 = np.interp(f, fr, abs(R)) * np.exp(1j * np.interp(f, fr, np.unwrap(np.angle(R))))
        a3["g501_interp_amp_phase"] = dict(fixed=a3p(C, Rb2, e_i, g_i, x_e, dx2, 501, 451, +1))
        a3["g501_A2p_only_const_amp"] = dict(fixed=a3p(C, np.ones(len(f)) * (1 + 0j), e_i, np.ones(len(f)), x_e, dx2, 501, 451, +1))
        a3["g501_phase_only"] = dict(fixed=a3p(C, np.exp(1j * np.angle(Rb)), e_i, np.ones(len(f)), x_e, dx2, 501, 451, +1))
        o["A3p"] = a3
        # 符号の確かめ (1)：−15 の点の時系列
        tt = t
        ms_fix = series_at(C, Rb, e_i, g_i, x_e, dx2, x15, tt, +1)
        ms_old = series_at(C, Rb, e_i, g_i, x_e, dx2, x15, tt, -1)
        ml = series_at(C, np.ones(len(f)) * (1 + 0j), np.zeros(len(f)), np.ones(len(f)), x_e, dx2, x15, tt, +1)
        wwin = (110.0, 150.0)
        o["sign_test_m15"] = dict(
            t_max_measured=float(tt[np.argmax(em2)]), t_max_linear_series=float(tt[np.argmax(el2)]),
            t_max_model_fixed=float(tt[np.argmax(ms_fix)]), t_max_model_old=float(tt[np.argmax(ms_old)]), t_max_model_linear=float(tt[np.argmax(ml)]),
            lead_measured_vs_linear_s=xcorr_lag(em2, el2, tt, wwin), lead_fixed_vs_linear_s=xcorr_lag(ms_fix, ml, tt, wwin),
            lead_old_vs_linear_s=xcorr_lag(ms_old, ml, tt, wwin),
            corr_measured_fixed=float(np.corrcoef(em2[(tt > wwin[0]) & (tt < wwin[1])], ms_fix[(tt > wwin[0]) & (tt < wwin[1])])[0, 1]),
            corr_measured_old=float(np.corrcoef(em2[(tt > wwin[0]) & (tt < wwin[1])], ms_old[(tt > wwin[0]) & (tt < wwin[1])])[0, 1]))
        # 各場所の最大の頂（60 s から、0〜930 m）：真ん中の節と内側 3 節
        tm = D["t"] >= 60.0
        xm = (D["x"] >= xp) & (D["x"] <= xp + 930)
        res = {}
        for nm, E in dict(mid=D["eta"][:, 2, :] - off_mid, inner3=np.nanmean(D["eta"][:, 1:-1, :], axis=1) - off_mid).items():
            sub_ = E[tm][:, xm]
            k = np.unravel_index(np.nanargmax(sub_), sub_.shape)
            res[nm] = dict(eta=float(sub_[k]), t=float(D["t"][tm][k[0]]), x_rel=float(D["x"][xm][k[1]] - xp))
        o["overall_max"] = res
        # 各場所の最大の頂の並び（470〜530 m）
        Em = (np.nanmean(D["eta"][:, 1:-1, :], axis=1) - off_mid)[tm]
        xr_ = D["x"] - xp
        cm = {}
        for xq in [470, 480, 484.4, 490, 500, 505, 510, 515, 520, 530]:
            j = int(np.argmin(abs(xr_ - xq)))
            cm[str(xq)] = float(np.nanmax(Em[:, j]))
        o["crest_max_inner3_at_x"] = cm
        out[rid] = o
        print(rid, "A1", [(round(s["amp"], 4), round(s["phase"], 3)) for s in sub], "S", round(o["S_meas"], 4),
              "e", round(o["A2p"]["speed_err_wmean"], 5), "g", round(o["A2p"]["amp_change_wmean"], 4), "B1", round(o["B1"]["loss"], 4))
        for nm in ("g501", "g1001"):
            for sg in ("fixed", "old"):
                r = a3[nm][sg]
                print("  A3'", nm, sg, round(r["dx_Lc"], 4), round(r["dt_Tc"], 4), round(r["crest_ratio"], 4), round(r["H_ratio_075Lc"], 4),
                      round(r["H_ratio_first_trough"], 4), "dx_m", round(r["dx_m"], 1), "dt_s", round(r["dt_s"], 2))
        print("  sign", o["sign_test_m15"])
        print("  max", res, "gauge", o["gauge_max"]["m5"])
        sys.stdout.flush()
    B.dump("b_spec.json", out)


if __name__ == "__main__":
    main()
