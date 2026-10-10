# -*- coding: utf-8 -*-
"""FLIP42 R1 / R1b の独立の確かめ（g_analyze.py・g_compare.py は使わない、読み込まない）。
読むもの：runs/<run>/cfg.json・run_c*.json・chain.log・hf_c*.npz・sec_c*_b*.npz（記録だけ）。
Houdini は起動しない。出力：check/R1/check_R1.json（数）と標準出力。
py -3.10 check_R1.py
"""
import glob, json, os, re, sys
import numpy as np
from scipy import ndimage
from skimage import measure, draw

ROOT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42"
OUT = os.path.join(ROOT, "check", "R1")
G = 9.80665
FPS = 24.0
RUNS = ["R1", "R1b"]


# ---------------------------------------------------------------- 線形の理論（自前）
def k_of_f(f, h):
    f = np.atleast_1d(np.asarray(f, float))
    om = 2 * np.pi * f
    k = np.maximum(om ** 2 / G, om / np.sqrt(G * h))
    k = np.where(k == 0, 1e-12, k)
    for _ in range(100):
        th = np.tanh(k * h)
        F = G * k * th - om ** 2
        dF = G * th + G * k * h * (1 - th ** 2)
        k = k - F / dF
    return np.where(f == 0, 0.0, k)


def cg_of_f(f, h):
    k = k_of_f(f, h)
    om = 2 * np.pi * np.atleast_1d(f)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(k > 0, om / k, np.sqrt(G * h))
        n = np.where(k > 0, 0.5 * (1 + 2 * k * h / np.sinh(2 * k * h)), 1.0)
    return c * n


class Lin:
    def __init__(self, p):
        self.h = p["h0"]; self.N = int(p["ncomp"]); self.fc = p["fc"]; self.dff = p["dff"]
        self.S = p["S"]; self.xb = p["x_b"]; self.tb = p["t_b"]; self.ramp = p["ramp_s"]
        self.f = np.linspace(self.fc * (1 - self.dff / 2), self.fc * (1 + self.dff / 2), self.N)
        self.k = k_of_f(self.f, self.h)
        self.om = 2 * np.pi * self.f
        self.a = self.S / self.k.sum()

    def eta(self, X, t):
        """造波板から X の解析の和（なだらかな始めなし）。X・t は放送できる配列"""
        X = np.asarray(X, float)[..., None]; t = np.asarray(t, float)[..., None]
        return (self.a * np.cos(self.k * (X - self.xb) - self.om * (t - self.tb))).sum(-1)

    def paddle(self, t):
        t = np.asarray(t, float)
        c = np.clip(t / self.ramp, 0, 1)
        R = 0.5 - 0.5 * np.cos(np.pi * c)
        return self.eta(np.zeros_like(t), t) * R

    def at_gauges(self, Xs, nt, npad=2 ** 16, fcut=0.5):
        """造波板の信号（0〜窓の終わり、なだらかな始めつき）を 0 で埋めて長くし、周波数ごとに X まで進めて窓で切る"""
        t = np.arange(nt) / FPS
        s = np.zeros(npad); s[:nt] = self.paddle(t)
        F = np.fft.rfft(s); fr = np.fft.rfftfreq(npad, 1 / FPS)
        kf = k_of_f(fr, self.h)
        out = {}
        for name, X in Xs.items():
            P = np.where(fr <= fcut, np.exp(-1j * kf * X), 0.0)
            out[name] = np.fft.irfft(F * P, npad)[:nt]
        return out


# ---------------------------------------------------------------- 記録の読み込み
def load_hf(run):
    files = sorted(glob.glob(os.path.join(ROOT, "runs", run, "hf_c*.npz")))
    byframe = {}
    src = {}
    for fn in files:  # 後の起動を優先（続きの計算が正）
        z = np.load(fn)
        for i, fr in enumerate(z["frames"]):
            byframe[int(fr)] = (fn, i)
    frames = np.array(sorted(byframe))
    cache = {}
    for fn in files:  # npz の鍵は読むたびに解凍するので、先に配列へ
        z = np.load(fn)
        cache[fn] = {k: z[k] for k in ("eta", "x", "z", "frames", "t", "ss_n", "lvl")}
    x = cache[files[0]]["x"]; zz = cache[files[0]]["z"]
    eta = np.empty((len(frames), len(zz), len(x)), np.float32)
    t = np.empty(len(frames)); ssn = np.empty(len(frames), int); lvl = np.empty(len(frames))
    for j, fr in enumerate(frames):
        fn, i = byframe[fr]
        eta[j] = cache[fn]["eta"][i]; t[j] = cache[fn]["t"][i]; ssn[j] = cache[fn]["ss_n"][i]; lvl[j] = cache[fn]["lvl"][i]
    # 重なったコマの差（再開の再現性）
    overlap = []
    for a_fn in files:
        for b_fn in files:
            if a_fn >= b_fn:
                continue
            fa = cache[a_fn]["frames"]; fb = cache[b_fn]["frames"]
            com = np.intersect1d(fa, fb)
            if len(com):
                ia = np.searchsorted(fa, com); ib = np.searchsorted(fb, com)
                d = np.abs(cache[a_fn]["eta"][ia].astype(float) - cache[b_fn]["eta"][ib].astype(float))
                d = np.nan_to_num(d)
                overlap.append({"a": os.path.basename(a_fn), "b": os.path.basename(b_fn), "frames": [int(com[0]), int(com[-1])],
                                "n": int(len(com)), "max_abs_diff_m": float(d.max()), "first_frame_max_diff_m": float(d[0].max()),
                                "last_frame_max_diff_m": float(d[-1].max())})
    return dict(frames=frames, t=t, x=x, z=zz, eta=eta, ssn=ssn, lvl=lvl, overlap=overlap, files=[os.path.basename(f) for f in files])


def load_sec(run):
    files = sorted(glob.glob(os.path.join(ROOT, "runs", run, "sec_c*_b*.npz")))
    byframe = {}
    meta = None
    for fn in files:  # c の番号の小さい順に読む → 後の起動が上書き
        z = np.load(fn)
        meta = json.loads(str(z["meta"]))
        sdf_all = z["sdf"]; t_all = z["t"]
        for i, fr in enumerate(z["frames"]):
            byframe[int(fr)] = (sdf_all[i].astype(np.float32), float(t_all[i]))
    frames = np.array(sorted(byframe))
    sdf = np.stack([byframe[f][0] for f in frames]); t = np.array([byframe[f][1] for f in frames])
    return dict(frames=frames, t=t, sdf=sdf, meta=meta)


# ---------------------------------------------------------------- 形（断面の水面の場）
def front_face(sdf, meta, still, x_p):
    """0 の等高線から、頂（最も高い点）の前の面を取り出す。返す：頂、最大の傾き（度）、かぶさりの長さ、閉じた空気"""
    cs = measure.find_contours(sdf, 0.0)
    x0, dx, y0, dy = meta["x0"], meta["dx"], meta["y0"], meta["dy"]
    best = None
    cav = []
    nx = sdf.shape[1]
    for c in cs:
        X = x0 + c[:, 1] * dx; Y = y0 + c[:, 0] * dy
        closed = np.allclose(c[0], c[-1])
        if closed:
            # 閉じた線：中が空気（sdf > 0）で、海底より上、場の端に触れないもの
            if Y.min() < -40 or c[:, 1].min() <= 0.5 or c[:, 1].max() >= nx - 1.5:
                continue
            area = 0.5 * abs(np.dot(X, np.roll(Y, 1)) - np.dot(Y, np.roll(X, 1)))
            rr, cc = draw.polygon(c[:, 0], c[:, 1], sdf.shape)
            if len(rr):
                inside = float(np.mean(sdf[rr, cc]))
            else:
                cy, cx = c[:, 0].mean(), c[:, 1].mean()
                inside = float(ndimage.map_coordinates(sdf, [[cy], [cx]], order=1)[0])
            if inside > 0:
                cav.append({"area_m2": float(area), "x_rel": float(X.mean() - x_p), "y": float(Y.mean() - still)})
            continue
        if best is None or Y.max() > best[1].max():
            best = (X, Y)
    if best is None:
        return None
    X, Y = best
    ic = int(np.argmax(Y))
    # 下流の向き：線の端のうち x が大きい方へ
    d = 1 if X[-1] > X[0] else -1
    idx = np.arange(ic, len(X) if d == 1 else -1, d)
    Xf, Yf = X[idx], Y[idx]
    # 静かな水面まで
    below = np.nonzero(Yf - still <= 0)[0]
    end = below[0] if len(below) else len(Xf) - 1
    Xf, Yf = Xf[:end + 1], Yf[:end + 1]
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(Xf), np.diff(Yf)))])
    thmax = -999.0; th_at = None
    j = 0
    for i in range(len(Xf)):
        while j < len(Xf) and s[j] - s[i] < 1.0 * dx:
            j += 1
        if j >= len(Xf):
            break
        ddx = Xf[j] - Xf[i]; ddy = Yf[j] - Yf[i]
        if ddy >= 0:
            continue
        th = np.degrees(np.arctan2(-ddy, ddx))
        if th > thmax:
            thmax = th; th_at = (float(Xf[i] - x_p), float(Yf[i] - still))
    runmax = np.maximum.accumulate(Xf)
    over = float(np.max(runmax - Xf)) if len(Xf) else 0.0
    xzero = float(Xf[-1]) if len(below) else np.nan
    return {"xc_rel": float(X[ic] - x_p), "eta_c": float(Y[ic] - still), "thmax_deg": float(thmax), "th_at": th_at,
            "overhang_m": over, "x_tip_rel": float(runmax[-1] - x_p), "tip_y": float(Yf[int(np.argmax(Xf))] - still), "d_zero_m": float(xzero - X[ic]) if np.isfinite(xzero) else None,
            "cavities": cav}


# ---------------------------------------------------------------- 本体
def main():
    res = {"note": "独立の確かめ（check_R1.py）。g_analyze.py・g_compare.py は使っていない"}
    plan = json.load(open(os.path.join(ROOT, "plan", "plan_numbers.json"), encoding="utf-8"))
    res["plan_numbers_keys"] = list(plan.keys())[:40]
    runs = {}
    for run in RUNS:
        cfg = json.load(open(os.path.join(ROOT, "runs", run, "cfg.json"), encoding="utf-8"))
        p = cfg["parms"]; case = cfg["case"]
        x_p = p["x_p"]
        lin = Lin(p)
        Tc = case["Tc"]; Lc = case["Lc"]
        R = {"cfg": {"dp": p["dp"], "Lx": p["Lx"], "h0": p["h0"], "ytop": p["ytop"], "Lz": p["Lz"], "band": cfg["solver"]["donarrowband"],
                     "band_vox": p["band_vox"], "maxsub": p["maxsub"], "minsub": p["minsub"], "cfl": p["cfl"], "pcfl": p["pcfl"],
                     "S": p["S"], "x_p": x_p, "x_b": p["x_b"], "t_b": p["t_b"], "xa0_rel": p["xa0"] - x_p, "f_end": cfg["f_end"],
                     "ckpt_every": cfg["ckpt_every"], "sec_rel": [cfg["sec"]["x0"] - x_p, cfg["sec"]["x1"] - x_p], "sec_t0": cfg["sec"]["t0"],
                     "gauges_rel": {k: v - x_p for k, v in case["gauges"].items()}}}
        # 線形の値
        R["lin"] = {"a_m": lin.a, "f_range": [float(lin.f[0]), float(lin.f[-1])], "df_comp": float(lin.f[1] - lin.f[0]),
                    "eta_c_focus": float(lin.eta(p["x_b"], p["t_b"])), "Tc": Tc, "Lc": Lc,
                    "kc": float(k_of_f(1 / Tc, p["h0"])[0])}
        # 線形の焦点の形：頂から前の谷までの H（その時刻）
        xx = np.arange(p["x_b"] - 150, p["x_b"] + 150, 0.25)
        e0 = lin.eta(xx, p["t_b"])
        ic = np.argmax(e0); ahead = (xx > xx[ic]) & (xx <= xx[ic] + 0.75 * Lc)
        R["lin"]["H_front_at_tb"] = float(e0[ic] - e0[ahead].min()); R["lin"]["x_front_trough_rel"] = float(xx[ahead][np.argmin(e0[ahead])] - xx[ic])
        # 線形の最大の頂の場所と時刻（x・t の格子で探す）
        XX = np.arange(400, 800, 0.5); TT = np.arange(150, 187.8, 1 / FPS)
        best = (-1, 0, 0)
        for tt in TT:
            e = lin.eta(XX, tt); i = np.argmax(e)
            if e[i] > best[0]:
                best = (float(e[i]), float(XX[i]), float(tt))
        R["lin"]["max_crest_search"] = {"eta": best[0], "x_rel": best[1], "t": best[2]}

        hf = load_hf(run)
        fr = hf["frames"]
        R["records"] = {"hf_files": hf["files"], "n_frames": int(len(fr)), "first": int(fr[0]), "last": int(fr[-1]),
                        "contiguous": bool(np.all(np.diff(fr) == 1)), "t_last": float(hf["t"][-1]),
                        "t_matches_frames": bool(np.allclose(hf["t"], (fr - 1) / FPS)),
                        "overlap": hf["overlap"],
                        "substeps_hist": {str(k): int(v) for k, v in zip(*np.unique(hf["ssn"], return_counts=True))}}
        x = hf["x"]; Xrel = x - x_p
        eta = hf["eta"]
        # 静かな水面：0〜930 m・0.5〜2.0 s の中央値
        tm = (hf["t"] >= 0.5) & (hf["t"] <= 2.0); xm = (Xrel >= 0) & (Xrel <= 930)
        still_c = float(np.nanmedian(eta[tm][:, 2, :][:, xm]))
        still_3 = float(np.nanmedian(eta[tm][:, 1:4, :][:, :, xm]))
        still_5 = float(np.nanmedian(eta[tm][:, :, xm]))
        R["still"] = {"center": still_c, "inner3": still_3, "all5": still_5}
        still = still_c
        # 最大の頂（60 s から、0〜930 m）
        tmask = hf["t"] >= 60.0
        for lab, E in (("center", eta[:, 2, :]), ("inner3_mean", eta[:, 1:4, :].mean(1)), ("max_over_z", np.nanmax(eta, axis=1))):
            sub = np.where(np.isfinite(E), E, -99)[tmask][:, xm] - still
            j, i = np.unravel_index(np.argmax(sub), sub.shape)
            R.setdefault("max_crest", {})[lab] = {"eta_c": float(sub[j, i]), "x_rel": float(Xrel[xm][i]), "t": float(hf["t"][tmask][j])}
        # 150 s の頂
        j150 = int(np.argmin(np.abs(hf["t"] - 150.0)))
        e150 = eta[j150, 2, :] - still
        m = (Xrel > 300) & (Xrel < 600)
        i = np.nanargmax(np.where(m, e150, -99))
        R["crest_150s"] = {"eta_c": float(e150[i]), "x_rel": float(Xrel[i])}
        # 140〜160 s の最大の頂（場所と時刻）
        tm2 = (hf["t"] >= 140) & (hf["t"] <= 160)
        sub = np.where(np.isfinite(eta[:, 2, :]), eta[:, 2, :], -99)[tm2][:, m] - still
        j, i = np.unravel_index(np.argmax(sub), sub.shape)
        R["crest_140_160"] = {"eta_c": float(sub[j, i]), "x_rel": float(Xrel[m][i]), "t": float(hf["t"][tm2][j])}

        # 測る点の時系列（内側の 3 節の平均、x を線形に補間）
        nt = len(fr)
        Gs = {k: v - x_p for k, v in case["gauges"].items()}
        E3 = eta[:, 1:4, :].mean(1).astype(float) - still_3
        gser = {}
        for name, X in Gs.items():
            xs = X + x_p
            i0 = int(np.floor(xs)); w = xs - i0
            gser[name] = (1 - w) * E3[:, i0] + w * E3[:, i0 + 1]
        linser = lin.at_gauges(Gs, nt)
        gres = {}
        for name in Gs:
            g = gser[name]; L = linser[name]
            # 深い谷：極小を全部並べたもの と、0 を下に切ってから上に切るまでの一つの谷で一つの値
            mins = np.nonzero((g[1:-1] < g[:-2]) & (g[1:-1] <= g[2:]))[0] + 1
            order = mins[np.argsort(g[mins])][:3]
            # 谷ごと（0 を下に切る〜上に切る区間の最小）
            sgn = g < 0
            seg = []
            j = 0
            while j < nt:
                if sgn[j]:
                    k = j
                    while k < nt and sgn[k]:
                        k += 1
                    seg.append(float(g[j:k].min())); j = k
                else:
                    j += 1
            seg = sorted(seg)[:3]
            Lmins = []
            sgnL = L < 0; j = 0
            while j < nt:
                if sgnL[j]:
                    k = j
                    while k < nt and sgnL[k]:
                        k += 1
                    Lmins.append(float(L[j:k].min())); j = k
                else:
                    j += 1
            Lmins = sorted(Lmins)[:3]
            gres[name] = {"x_rel": float(Gs[name]), "max": float(g.max()), "t_max": float(hf["t"][np.argmax(g)]),
                          "lin_max": float(L.max()), "t_lin_max": float(np.argmax(L) / FPS),
                          "dt_crest_s": float(hf["t"][np.argmax(g)] - np.argmax(L) / FPS),
                          "troughs3_localmin": [float(g[o]) for o in order], "troughs3_localmin_t": [float(hf["t"][o]) for o in order],
                          "troughs3_localmin_mean": float(np.mean(g[order])),
                          "troughs3_distinct": seg, "troughs3_distinct_mean": float(np.mean(seg)),
                          "lin_troughs3_distinct": Lmins}
        R["gauges"] = gres

        # スペクトル：A1・A2'・B1
        F = {n: np.fft.rfft(gser[n]) for n in Gs}; FL = {n: np.fft.rfft(linser[n]) for n in Gs}
        fr_ = np.fft.rfftfreq(nt, 1 / FPS)
        dfc = lin.f[1] - lin.f[0]
        inb = (fr_ >= lin.f[0] - dfc / 2) & (fr_ <= lin.f[-1] + dfc / 2)
        cg = cg_of_f(fr_, p["h0"]); kf = k_of_f(fr_, p["h0"])
        B = {}
        for n in Gs:
            Em = np.abs(F[n]) ** 2; El = np.abs(FL[n]) ** 2
            low = (fr_ > 0) & (fr_ < lin.f[0] - dfc / 2); high = (fr_ > lin.f[-1] + dfc / 2) & (fr_ <= 0.5)
            B[n] = {"flux_ratio": float((Em[inb] * cg[inb]).sum() / (El[inb] * cg[inb]).sum()),
                    "energy_ratio_unweighted": float(Em[inb].sum() / El[inb].sum()),
                    "out_low_over_in": float((Em[low] * cg[low]).sum() / (Em[inb] * cg[inb]).sum()),
                    "out_high_over_in": float((Em[high] * cg[high]).sum() / (Em[inb] * cg[inb]).sum()),
                    "flux_incl_out_ratio": float((Em[(fr_ > 0) & (fr_ <= 0.5)] * cg[(fr_ > 0) & (fr_ <= 0.5)]).sum() / (El[inb] * cg[inb]).sum())}
        e_, m15, m10 = "band_exit", "kc(x-xb)=-15", "kc(x-xb)=-10"
        B["loss_exit_to_m10"] = 1 - B[m10]["flux_ratio"] / B[e_]["flux_ratio"]
        B["loss_exit_to_m10_unweighted"] = 1 - B[m10]["energy_ratio_unweighted"] / B[e_]["energy_ratio_unweighted"]
        B["loss_exit_to_m10_incl_out"] = 1 - B[m10]["flux_incl_out_ratio"] / B[e_]["flux_incl_out_ratio"]
        B["inband_bins"] = [float(fr_[inb][0]), float(fr_[inb][-1]), int(inb.sum())]
        R["B1"] = B
        # A1
        Rx = F[e_] / FL[e_]
        sub = []
        for (i1, i2) in ((1, 11), (12, 21), (22, 32)):
            mm = (fr_ >= lin.f[i1 - 1] - dfc / 2) & (fr_ < lin.f[i2 - 1] + dfc / 2)
            if i2 == 32:
                mm = (fr_ >= lin.f[i1 - 1] - dfc / 2) & (fr_ <= lin.f[i2 - 1] + dfc / 2)
            w = np.abs(FL[e_][mm]) ** 2
            sub.append({"comp": [i1, i2], "nbins": int(mm.sum()), "amp": float((np.abs(Rx[mm]) * w).sum() / w.sum()),
                        "phase": float((np.angle(Rx[mm]) * w).sum() / w.sum()),
                        "amp_rms": float(np.sqrt((np.abs(F[e_][mm]) ** 2).sum() / w.sum()))})
        S_meas = p["S"] * (kf[inb] * np.abs(F[e_][inb])).sum() / (kf[inb] * np.abs(FL[e_][inb])).sum()
        R["A1"] = {"subbands": sub, "S_measured": float(S_meas)}
        # A2'
        band2 = (fr_ >= 0.077) & (fr_ <= 0.134)
        R15 = F[m15] / FL[m15]
        dphi = np.angle(R15[band2] / Rx[band2])
        dX = Gs[m15] - Gs[e_]
        e = -dphi / (kf[band2] * dX)
        amp = np.abs(R15[band2]) / np.abs(Rx[band2])
        w = np.abs(FL[e_][band2]) ** 2
        R["A2p"] = {"f": fr_[band2].tolist(), "speed_err": e.tolist(), "amp_change": amp.tolist(), "dx": dX,
                    "speed_err_wmean_Elin_exit": float((e * w).sum() / w.sum()), "amp_change_wmean_Elin_exit": float((amp * w).sum() / w.sum()),
                    "speed_err_plain_mean": float(e.mean()), "amp_change_plain_mean": float(amp.mean())}
        # 測った帯域の中の記録を線形で焦点へ進めた時の頂（測った減りを入れた線形の見込み）
        proj = {}
        for n in (e_, m10):
            Xg = Gs[n]
            npad = 2 ** 15
            s = np.zeros(npad); s[:nt] = gser[n]
            Fs = np.fft.rfft(s); ff = np.fft.rfftfreq(npad, 1 / FPS); kk = k_of_f(ff, p["h0"])
            mband = (ff >= lin.f[0] - dfc / 2) & (ff <= lin.f[-1] + dfc / 2)
            s2 = np.zeros(npad); s2[:nt] = linser[n]
            Fl2 = np.fft.rfft(s2)
            bestm = (-9, 0, 0); bestl = (-9, 0, 0)
            for Xt in np.arange(Xg + 50, 760, 1.0):
                P = np.where(mband, np.exp(-1j * kk * (Xt - Xg)), 0)
                em = np.fft.irfft(Fs * P, npad)[:nt]; el = np.fft.irfft(Fl2 * P, npad)[:nt]
                if em.max() > bestm[0]:
                    bestm = (float(em.max()), float(Xt), float(np.argmax(em) / FPS))
                if el.max() > bestl[0]:
                    bestl = (float(el.max()), float(Xt), float(np.argmax(el) / FPS))
            proj[n] = {"meas_inband_linear_focus": {"eta": bestm[0], "x_rel": bestm[1], "t": bestm[2]},
                       "lin_inband_linear_focus": {"eta": bestl[0], "x_rel": bestl[1], "t": bestl[2]},
                       "ratio": bestm[0] / bestl[0]}
        R["linear_projection"] = proj

        # 断面の量（一番上の水面の高さの真ん中の節、計画の読み方 9）
        smask = (Xrel >= cfg["sec"]["x0"] - x_p) & (Xrel <= cfg["sec"]["x1"] - x_p)
        Ec = eta[:, 2, :] - still
        rows = []
        for j in np.nonzero(hf["t"] >= cfg["sec"]["t0"] - 1e-9)[0]:
            e = np.where(np.isfinite(Ec[j]), Ec[j], -99)
            idx = np.nonzero(smask)[0]
            ic = idx[np.argmax(e[idx])]
            ah = idx[(Xrel[idx] > Xrel[ic]) & (Xrel[idx] <= Xrel[ic] + 0.75 * Lc)]
            if len(ah) == 0:
                continue
            itr = ah[np.argmin(e[ah])]
            # 前で静かな水面を切る点
            cr = ah[e[ah] <= 0]
            dz = None
            if len(cr):
                i1 = cr[0]; i0 = i1 - 1
                xz = Xrel[i0] + (Xrel[i1] - Xrel[i0]) * e[i0] / (e[i0] - e[i1])
                dz = xz - Xrel[ic]
            rows.append((hf["t"][j], Xrel[ic], e[ic], e[ic] - e[itr], Xrel[itr], dz))
        rows = np.array([[r[0], r[1], r[2], r[3], r[4], r[5] if r[5] is not None else np.nan] for r in rows])
        jH = int(np.argmax(rows[:, 3]))
        R["section_max_H"] = {"t": float(rows[jH, 0]), "xc_rel": float(rows[jH, 1]), "eta_c": float(rows[jH, 2]), "H": float(rows[jH, 3])}
        jE = int(np.argmax(rows[:, 2]))
        R["section_max_eta_c"] = {"t": float(rows[jE, 0]), "xc_rel": float(rows[jE, 1]), "eta_c": float(rows[jE, 2]), "H": float(rows[jE, 3])}
        steep = rows[:, 2] / rows[:, 5]
        jS = int(np.nanargmax(steep))
        R["section_max_steep"] = {"t": float(rows[jS, 0]), "xc_rel": float(rows[jS, 1]), "eta_c": float(rows[jS, 2]), "H": float(rows[jS, 3]),
                                  "steep": float(steep[jS]), "x_trough_rel": float(rows[jS, 4])}
        at = {}
        for tq in (168.9167, 172.0, 173.7, 174.875):
            j = int(np.argmin(np.abs(rows[:, 0] - tq)))
            at["%.3f" % tq] = {"t": float(rows[j, 0]), "xc_rel": float(rows[j, 1]), "eta_c": float(rows[j, 2]), "H": float(rows[j, 3]),
                               "steep": float(steep[j]), "x_trough_rel": float(rows[j, 4])}
        R["section_at"] = at

        # 断面の水面の場から形
        sec = load_sec(run)
        R["sec_records"] = {"n": int(len(sec["frames"])), "first": int(sec["frames"][0]), "last": int(sec["frames"][-1]),
                            "contiguous": bool(np.all(np.diff(sec["frames"]) == 1)), "x0_rel": sec["meta"]["x0"] - x_p,
                            "x1_rel": sec["meta"]["x0"] + (sec["meta"]["nx"] - 1) * sec["meta"]["dx"] - x_p, "t0": float(sec["t"][0])}
        shapes = []
        for j in range(len(sec["frames"])):
            ff = front_face(sec["sdf"][j], sec["meta"], still, x_p)
            if ff is None:
                continue
            ff["t"] = float(sec["t"][j]); ff["frame"] = int(sec["frames"][j])
            shapes.append(ff)
        th = np.array([s["thmax_deg"] for s in shapes]); ts = np.array([s["t"] for s in shapes])
        ov = np.array([s["overhang_m"] for s in shapes])
        jm = int(np.argmax(th))
        R["shape"] = {"thmax_overall": {"deg": float(th[jm]), "t": float(ts[jm]), "xc_rel": shapes[jm]["xc_rel"], "eta_c": shapes[jm]["eta_c"]}}
        first90 = np.nonzero(th >= 90)[0]
        R["shape"]["first_ge90"] = ({"t": float(ts[first90[0]]), "xc_rel": shapes[first90[0]]["xc_rel"], "eta_c": shapes[first90[0]]["eta_c"],
                                     "deg": float(th[first90[0]]), "overhang_m": float(ov[first90[0]])} if len(first90) else None)
        R["shape"]["n_frames_ge90"] = int(len(first90))
        R["shape"]["frames_ge90_t"] = [float(ts[i]) for i in first90[:40]]
        firstov = np.nonzero(ov > 0.0)[0]
        R["shape"]["first_overhang_gt0"] = ({"t": float(ts[firstov[0]]), "overhang_m": float(ov[firstov[0]])} if len(firstov) else None)
        R["shape"]["max_overhang"] = {"m": float(ov.max()), "t": float(ts[int(np.argmax(ov))])}
        cavs = [(s["t"], c) for s in shapes for c in s["cavities"] if c["area_m2"] >= 1.0]
        R["shape"]["first_cavity_ge1m2"] = ({"t": cavs[0][0], **cavs[0][1]} if cavs else None)
        R["shape"]["n_cavity_frames"] = len(set(c[0] for c in cavs))
        R["shape"]["cavities_ge1m2"] = [{"t": c[0], **c[1]} for c in cavs]
        R["shape"]["cavities_any_count_frames"] = len(set(c[0] for c in [(s["t"], c) for s in shapes for c in s["cavities"]]))
        ovr = [s for s in shapes if s["overhang_m"] > 0]
        R["shape"]["overhang_frames"] = {"n": len(ovr), "t_first": ovr[0]["t"] if ovr else None, "t_last": ovr[-1]["t"] if ovr else None,
                                         "tip_y_min": min(o["tip_y"] for o in ovr) if ovr else None,
                                         "n_overhang_ge1m": int(sum(o["overhang_m"] >= 1.0 for o in ovr))}
        cav_any = [(s["t"], c) for s in shapes for c in s["cavities"]]
        R["shape"]["first_cavity_any"] = ({"t": cav_any[0][0], **cav_any[0][1]} if cav_any else None)
        tl = {}
        for tq in np.arange(170.0, 178.01, 0.5):
            j = int(np.argmin(np.abs(ts - tq)))
            s = shapes[j]
            tl["%.1f" % tq] = {"t": s["t"], "thmax": round(s["thmax_deg"], 1), "overhang": round(s["overhang_m"], 2), "xc_rel": s["xc_rel"],
                               "eta_c": round(s["eta_c"], 2), "tip_y": round(s["tip_y"], 2), "x_tip_rel": round(s["x_tip_rel"], 1), "ncav": len(s["cavities"]),
                               "cav_areas": [round(c["area_m2"], 2) for c in s["cavities"]]}
        R["shape"]["timeline"] = tl
        jj = int(np.argmin(np.abs(ts - 172.0)))
        R["shape"]["at_172"] = {k: shapes[jj][k] for k in ("t", "thmax_deg", "overhang_m", "xc_rel", "eta_c", "d_zero_m")}
        runs[run] = R
        print(run, "done", flush=True)

    res["runs"] = runs
    # N2 の再計算
    a, b = runs["R1"], runs["R1b"]
    res["N2_recomputed"] = {
        "R1_maxsteep": a["section_max_steep"], "R1b_at_172": b["section_at"]["172.000"],
        "rel_H": a["section_max_steep"]["H"] / b["section_at"]["172.000"]["H"] - 1,
        "rel_eta_c": a["section_max_steep"]["eta_c"] / b["section_at"]["172.000"]["eta_c"] - 1,
        "rel_steep": a["section_max_steep"]["steep"] / b["section_at"]["172.000"]["steep"] - 1,
        "same_time_172": {"rel_H": a["section_at"]["172.000"]["H"] / b["section_at"]["172.000"]["H"] - 1,
                          "rel_eta_c": a["section_at"]["172.000"]["eta_c"] / b["section_at"]["172.000"]["eta_c"] - 1,
                          "rel_steep": a["section_at"]["172.000"]["steep"] / b["section_at"]["172.000"]["steep"] - 1},
        "R1_at_own_max_eta_c": a["section_max_eta_c"], "R1b_max_eta_c": b["section_max_eta_c"]}
    n1 = {}
    for g in ("band_exit", "kc(x-xb)=-20", "kc(x-xb)=-10"):
        n1[g] = {"localmin_diff": a["gauges"][g]["troughs3_localmin_mean"] - b["gauges"][g]["troughs3_localmin_mean"],
                 "distinct_diff": a["gauges"][g]["troughs3_distinct_mean"] - b["gauges"][g]["troughs3_distinct_mean"],
                 "R1_localmin_t": a["gauges"][g]["troughs3_localmin_t"], "R1b_localmin_t": b["gauges"][g]["troughs3_localmin_t"]}
    res["N1_recomputed"] = n1
    with open(os.path.join(OUT, "check_R1.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=1, default=float)
    print("wrote", os.path.join(OUT, "check_R1.json"))


if __name__ == "__main__":
    main()
