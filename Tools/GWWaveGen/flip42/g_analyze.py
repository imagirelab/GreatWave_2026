# -*- coding: utf-8 -*-
"""FLIP42：集まる波の群の計算の記録から、計画（plan/plan_ja.md §5・§6）の量を出す（py -3.10、numpy・scipy・scikit-image）。
使い方: py -3.10 g_analyze.py <run_id>   → runs/<run_id>/ana.json
読み方は record_ja.md の「計画の読み方」（結果を見る前に決めた）のとおり：
  静かな水面＝自由に進む所の 0.5〜2.0 s の水面の高さの中央値。測る点の時系列は板の内側の節の平均。
  線形の値＝造波板の位置の目標（始めの 1 周期のなだらかさ込み）を周波数ごとに線形の分散で進め、同じ窓 0〜187.8 s で切ったもの。
出す量：
  A1  帯の出口の 3 つの帯域の振幅の比・位相、測った S（判定）
  A2' 帯の出口と kc(x − xb) = −15 の点の間の、周波数ごとの速さの誤差と振幅の変化（記録）
  A3' A2' の値を線形の焦点の模型に入れた焦点のずれと頂・H の比（R3・R4 で判定。ほかは記録）
  B1  エネルギーの流れの帯の出口から −10 の点までの減り（R3・R4 で判定。ほかは記録）、帯域の外のエネルギー
  N1  帯の出口・−20・−10 の点の、深い谷 3 つの深さの平均（R1 と R1b の比べは g_compare.py）
  巻き始め・着水（断面の水面の場の 0 の等高線）、各コマの H・η_c・前の面の険しさ（C3 の量）・前の面の最大の傾き
  §6 の見た目の量（巻き始めと着水の時刻）
"""
import sys, os, json, glob, math
import numpy as np
from skimage import measure

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import v_lin as VL

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
PLAN = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/plan/plan_numbers.json"
G = VL.G
FPS = 24.0


# ------------------------------------------------------------------ 読み込み
def load_hf(rid):
    rd = os.path.join(ROOT, rid)
    files = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    F, E, W, N, SS, SD = [], [], [], [], [], []
    x = z = None
    for p in files:
        d = np.load(p)
        fr = list(d["frames"])
        if not fr:
            continue
        if F:
            keep = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in keep]; E = [E[i] for i in keep]; W = [W[i] for i in keep]; N = [N[i] for i in keep]
            SS = [SS[i] for i in keep]; SD = [SD[i] for i in keep]
        F += fr; E += list(d["eta"]); W += list(d["wall"]); N += list(d["npts"]); SS += list(d["ss_n"]); SD += list(d["ss_dt"])
        x = d["x"]; z = d["z"]
    F = np.array(F)
    return dict(frames=F, t=(F - 1) / FPS, x=x, z=z, eta=np.array(E, np.float32), wall=np.array(W), npts=np.array(N),
                ss_n=np.array(SS), ss_dt=np.array(SD))


def load_sec(rid):
    """断面の水面の場。コマ F には、F を含む記録のうち起動の始め f0 が最も大きいもの（後の起動が上書き）を使う。"""
    rd = os.path.join(ROOT, rid)
    files = glob.glob(os.path.join(rd, "sec_c*_b*.npz"))
    best = {}
    meta = None
    for p in files:
        b = os.path.basename(p)
        f0 = int(b[5:9])
        d = np.load(p)
        m = json.loads(str(d["meta"]))
        if meta is None:
            meta = m
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i)
    if not best:
        return None
    frs = sorted(best)
    cache = {}
    out = np.zeros((len(frs), meta["ny"], meta["nx"]), np.float16)
    for j, f in enumerate(frs):
        f0, p, i = best[f]
        if p not in cache:
            cache.clear(); cache[p] = np.load(p)["sdf"]
        out[j] = cache[p][i]
    return dict(frames=np.array(frs), t=(np.array(frs) - 1) / FPS, sdf=out, meta=meta)


# ------------------------------------------------------------------ 線形の理論
def plan():
    return json.load(open(PLAN, encoding="utf-8"))


def comps_full(P):
    lab, full = P["lab"], P["full"]
    s = math.sqrt(full["lam"])
    f = np.linspace(lab["fc"] * (1 - lab["dff"] / 2), lab["fc"] * (1 + lab["dff"] / 2), lab["N"]) / s
    om = 2 * np.pi * f
    k = np.array([VL.k_of_omega(o, full["h"]) for o in om])
    a = np.full(len(f), lab["S"] / k.sum())
    cg = np.array([VL.props(2 * np.pi / o, full["h"])["cg"] for o in om])
    return dict(f=f, om=om, k=k, a=a, cg=cg, h=full["h"], xb=full["xb"], tb=full["tb"], ramp=P["tank"]["ramp"],
                df=float(f[1] - f[0]), Tc=full["Tc"], Lc=full["Lc"])


def k_of_f(fr, h):
    om = 2 * np.pi * np.asarray(fr, float)
    k = np.maximum(om * om / G, om / np.sqrt(G * h))
    pos = om > 0
    for _ in range(60):
        th = np.tanh(k * h)
        fval = G * k * th - om * om
        dfv = G * th + G * k * h * (1 - th * th)
        dk = np.where(pos, fval / np.where(dfv > 0, dfv, 1.0), 0.0)
        k = k - dk
    return np.where(pos, k, 0.0)


def cg_of_f(fr, h):
    k = k_of_f(fr, h); om = 2 * np.pi * np.asarray(fr, float)
    kh = k * h
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(k > 0, om / np.where(k > 0, k, 1), np.sqrt(G * h))
        n = np.where(kh > 1e-6, 0.5 * (1 + 2 * kh / np.sinh(np.minimum(2 * kh, 600))), 1.0)
    return c * n


def rampT(t, R):
    c = np.clip(np.asarray(t) / R, 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * c)


def target_at_paddle(C, t):
    th = C["k"][None, :] * (0.0 - C["xb"]) - C["om"][None, :] * (t[:, None] - C["tb"])
    return rampT(t, C["ramp"]) * (C["a"][None, :] * np.cos(th)).sum(1)


def lin_series(C, x_rel, t):
    """造波板の位置の目標を周波数ごとに線形で x_rel まで進め、t の窓で切る。"""
    e0 = target_at_paddle(C, t)
    n = 1 << 18
    F = np.fft.rfft(e0, n)
    fr = np.fft.rfftfreq(n, 1 / FPS)
    kk = k_of_f(fr, C["h"])
    return np.fft.irfft(F * np.exp(-1j * kk * x_rel), n)[:len(t)]


def eta_lin_xt(C, x_rel, t):
    x_rel = np.atleast_1d(x_rel); t = np.atleast_1d(t)
    th = C["k"][None, None, :] * (x_rel[:, None, None] - C["xb"]) - C["om"][None, None, :] * (t[None, :, None] - C["tb"])
    return (C["a"] * np.cos(th)).sum(-1)


# ------------------------------------------------------------------ 記録の読み
def still_level(D, xp):
    m = (D["t"] >= 0.5) & (D["t"] <= 2.0)
    xm = (D["x"] >= xp) & (D["x"] <= xp + 930.0)
    e = D["eta"][m][:, 2, :][:, xm] if D["eta"].shape[1] >= 3 else D["eta"][m][:, 0, :][:, xm]
    return float(np.nanmedian(e))


def zmean(D):
    nz = D["eta"].shape[1]
    zz = slice(1, nz - 1) if nz >= 3 else slice(0, nz)
    with np.errstate(all="ignore"):
        return np.nanmean(D["eta"][:, zz, :], axis=1)


def gauge(EX, x, xs):
    i = np.searchsorted(x, xs) - 1
    w = (xs - x[i]) / (x[i + 1] - x[i])
    return (1 - w) * EX[:, i] + w * EX[:, i + 1]


def spec_ratio(em, el, C):
    Fm = np.fft.rfft(em); Fl = np.fft.rfft(el)
    fr = np.fft.rfftfreq(len(em), 1 / FPS)
    return fr, Fm, Fl


def wmean(v, w):
    return float((v * w).sum() / w.sum()) if w.sum() > 0 else float("nan")


def troughs3(e):
    d = np.diff(e)
    idx = np.where((d[:-1] < 0) & (d[1:] >= 0))[0] + 1
    if len(idx) == 0:
        return [], float("nan")
    v = np.sort(e[idx])[:3]
    return [float(q) for q in v], float(np.mean(v))


# ------------------------------------------------------------------ 断面の形
def resample(path, ds):
    seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < ds:
        return path
    q = np.arange(0, s[-1], ds)
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], 1)


def poly_area(c):
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def frame_shape(sdf, meta, off, vox, Lc, ex_top, xg):
    """1 コマの断面の形：主な水面の線、頂、前の面の最大の傾き、噴流の先、空気を囲む閉じた線。"""
    S = sdf.astype(np.float32)
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"])
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - off
    j0 = int(np.searchsorted(ys, -25.0))      # 海底の境の等高線を拾わないように、静かな水面の 25 m 下より上だけを見る
    S = S[j0:]; ys = ys[j0:]
    cs = measure.find_contours(S, 0.0)
    lines = []
    for c in cs:
        X = xs[0] + c[:, 1] * meta["dx"]; Y = ys[0] + c[:, 0] * meta["dy"]
        lines.append(np.stack([X, Y], 1))
    if not lines:
        return None
    ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
    main = lines[int(np.argmax(ext))]
    ic = int(np.argmax(main[:, 1]))
    xc, yc = main[ic]
    # 前へ向かう向き
    a = main[max(ic - 3, 0)][0]; b = main[min(ic + 3, len(main) - 1)][0]
    fwd = main[ic:] if b >= a else main[:ic + 1][::-1]
    # 静かな水面より下に出るまで（1 Lc まで）
    j_end = len(fwd)
    for j in range(1, len(fwd)):
        if fwd[j, 1] <= 0.0 or abs(fwd[j, 0] - xc) > Lc:
            j_end = j + 1
            break
    face = resample(fwd[:j_end], 0.5 * vox)
    thmax = float("nan"); steep_h60 = 0.0
    tip = None
    if len(face) >= 3:
        d = face[2:] - face[:-2]
        th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
        okm = (th >= 0) & (th <= 180)
        thmax = float(th[okm].max()) if okm.any() else float("nan")
        # 60° より立った所の高さ
        ys60 = face[1:-1][(th >= 60) & (th <= 180)][:, 1]
        steep_h60 = float(ys60.max() - ys60.min()) if len(ys60) >= 2 else 0.0
        # 噴流の先：前へ進んだ x が最大になり、その後 1 格子以上戻る点
        xx = face[:, 0]
        imax = int(np.argmax(xx))
        if imax < len(xx) - 1 and (xx[imax] - xx[imax:].min()) >= vox:
            tip = [float(xx[imax]), float(face[imax, 1])]
    # 空気を囲む閉じた線（面積が格子 1 個以上、頂の後ろ 0.25 Lc から前 0.75 Lc の間）
    cav = []
    for l in lines:
        if len(l) > 4 and np.allclose(l[0], l[-1]):
            A = poly_area(l)
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            if A >= vox * vox and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                ix = int(round((cx - xs[0]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0:
                    cav.append([float(cx), float(cy), float(A)])
    return dict(xc=float(xc), yc=float(yc), thmax=thmax, steep_h60=steep_h60, tip=tip, cav=cav, face=face, main=main)


def top_measures(etop, x, xc, Lc):
    """一番上の水面の高さ（静かな水面から）での頂・前の谷・H・前で静かな水面を切る点・険しさ。"""
    ic = int(np.argmin(abs(x - xc)))
    ec = float(etop[ic])
    m = (x > x[ic]) & (x <= x[ic] + 0.75 * Lc)
    if not m.any():
        return None
    jt = np.where(m)[0][int(np.nanargmin(etop[m]))]
    H = ec - float(etop[jt])
    jz = None
    for j in range(ic, len(x)):
        if etop[j] <= 0:
            jz = j; break
    if jz is None or jz == ic:
        dz = float("nan")
    else:
        x0 = x[jz - 1] + (x[jz] - x[jz - 1]) * etop[jz - 1] / (etop[jz - 1] - etop[jz])
        dz = float(x0 - x[ic])
    return dict(eta_c=ec, H=H, x_trough=float(x[jt]), trough=float(etop[jt]), d_zero=dz, steep=ec / dz if dz and dz > 0 else float("nan"))


# ------------------------------------------------------------------ 本体
def analyze(rid, quick=False):
    P = plan(); C = comps_full(P)
    cfg = json.load(open(os.path.join(ROOT, rid, "cfg.json"), encoding="utf8"))
    xp = cfg["parms"]["x_p"]; Lc = C["Lc"]; Tc = C["Tc"]   # 造波板の位置は計算の設定から（帯を長くした計算のため。計画どおりの計算では P["tank"]["x_p"] と同じ値）
    vox = cfg["parms"]["dp"] * 2.0
    D = load_hf(rid)
    off = still_level(D, xp)
    EX = zmean(D) - off
    t = D["t"]; x = D["x"]
    t_end = P["tank"]["t_end"]
    win = t <= t_end + 1e-9
    out = dict(run_id=rid, dp=cfg["parms"]["dp"], nb=cfg["solver"]["donarrowband"], frames_done=int(D["frames"].max()),
               t_done=float(t.max()), still_level_offset_m=off)
    # 時間と小刻み
    ss = D["ss_n"][D["ss_n"] > 0]
    out["cost"] = dict(wall_per_frame_median=float(np.median(D["wall"][1:])), wall_sum_h=float(D["wall"].sum() / 3600),
                       substeps_hist={str(int(v)): int((ss == v).sum()) for v in np.unique(ss)},
                       particles_max=int(D["npts"].max()))
    # 測る点の時系列
    gnames = list(P["gauges"].keys())
    GA = {}
    for g in gnames:
        xr = P["gauges"][g]["x_rel"]
        em = gauge(EX, x, xp + xr)[win]
        el = lin_series(C, xr, t[win])
        GA[g] = (xr, em, el)
    out["gauges"] = {}
    for g in gnames:
        xr, em, el = GA[g]
        tr, trm = troughs3(em)
        trl, trlm = troughs3(el)
        out["gauges"][g] = dict(x_rel=xr, max=float(np.nanmax(em)), t_max=float(t[win][np.nanargmax(em)]), lin_max=float(el.max()),
                                t_lin_max=float(t[win][np.argmax(el)]), troughs3=tr, troughs3_mean=trm, lin_troughs3=trl, lin_troughs3_mean=trlm)
    complete = D["frames"].max() >= P["tank"]["frames"]
    out["complete"] = bool(complete)
    # ---- A1：帯の出口
    df = C["df"]; f = C["f"]; k = C["k"]
    xr, em, el = GA["band_exit"]
    fr, Fm, Fl = spec_ratio(np.nan_to_num(em), el, C)
    R = Fm / np.where(abs(Fl) > 0, Fl, 1)
    wl = abs(Fl) ** 2
    A1 = dict(subbands=[])
    for (i0, i1) in P["criteria"]["A1_band_exit"]["subbands_components"]:
        m = (fr >= f[i0 - 1] - df / 2) & (fr <= f[i1 - 1] + df / 2)
        amp = wmean(abs(R[m]), wl[m]); ph = wmean(np.angle(R[m]), wl[m])
        A1["subbands"].append(dict(components=[i0, i1], f_range=[float(f[i0 - 1] - df / 2), float(f[i1 - 1] + df / 2)], nbins=int(m.sum()),
                                   amp_ratio=amp, phase_rad=ph, amp_ok=bool(abs(amp - 1) <= 0.05), phase_ok=bool(abs(ph) <= 0.1)))
    mb = (fr >= f[0] - df / 2) & (fr <= f[-1] + df / 2)
    kf = k_of_f(fr, C["h"])
    S_meas = P["lab"]["S"] * (kf[mb] * abs(Fm[mb])).sum() / (kf[mb] * abs(Fl[mb])).sum()
    A1["S_measured"] = float(S_meas); A1["S_ok"] = bool(0.352 * 0.95 <= S_meas <= 0.352 * 1.05)
    A1["pass"] = bool(all(s["amp_ok"] and s["phase_ok"] for s in A1["subbands"]) and A1["S_ok"])
    out["A1"] = A1
    # ---- A2'：帯の出口と −15
    xr2, em2, el2 = GA["kc(x-xb)=-15"]
    fr2, Fm2, Fl2 = spec_ratio(np.nan_to_num(em2), el2, C)
    R2 = Fm2 / np.where(abs(Fl2) > 0, Fl2, 1)
    band = P["criteria"]["A2p_propagation"]["band_Hz"]
    m2 = (fr >= band[0]) & (fr <= band[1])
    dphi = np.angle(R2[m2] / R[m2])
    dx2 = xr2 - xr
    e_f = -dphi / (kf[m2] * dx2)
    g_f = abs(R2[m2]) / abs(R[m2])
    w2 = abs(Fl[m2]) ** 2
    out["A2p"] = dict(f=fr[m2].tolist(), speed_err=e_f.tolist(), amp_change=g_f.tolist(), weight=(w2 / w2.max()).tolist(),
                      speed_err_wmean=wmean(e_f, w2), amp_change_wmean=wmean(g_f, w2), dx=dx2,
                      third_order_bias_est=P["criteria"]["A2p_propagation"]["third_order_speed_bias_est"])
    # ---- A3'：測った値を焦点の模型に入れる（帯の出口の振幅・位相、その先の速さの誤差と振幅の変化）
    Rb = np.interp(f, fr, R.real) + 1j * np.interp(f, fr, R.imag)
    e_i = np.interp(f, fr[m2], e_f); g_i = np.interp(f, fr[m2], g_f)
    xs_ = C["xb"] + np.linspace(-1.0, 1.5, 501) * Lc
    ts_ = C["tb"] + np.linspace(-1.5, 3.0, 451) * Tc
    th0 = C["k"][None, None, :] * (xs_[:, None, None] - C["xb"]) - C["om"][None, None, :] * (ts_[None, :, None] - C["tb"])
    E0 = (C["a"] * np.cos(th0)).sum(-1)
    dxr = (xs_ - xr)[:, None, None]
    kk = C["k"] / (1 - e_i)
    th1 = th0 + np.angle(Rb)[None, None, :] - (kk - C["k"])[None, None, :] * dxr
    amp1 = C["a"][None, None, :] * abs(Rb)[None, None, :] * np.power(g_i[None, None, :], dxr / dx2)
    E1 = (amp1 * np.cos(th1)).sum(-1)
    i0 = np.unravel_index(np.argmax(E0), E0.shape); i1 = np.unravel_index(np.argmax(E1), E1.shape)

    def Hf(E, ix, it):
        row = E[:, it]; mm = (xs_ > xs_[ix]) & (xs_ <= xs_[ix] + 0.75 * Lc)
        return float(row[ix] - row[mm].min()) if mm.any() else float("nan")
    out["A3p_model"] = dict(dx_focus_over_Lc=float((xs_[i1[0]] - xs_[i0[0]]) / Lc), dt_focus_over_Tc=float((ts_[i1[1]] - ts_[i0[1]]) / Tc),
                            crest_ratio=float(E1[i1] / E0[i0]), H_ratio=float(Hf(E1, *i1) / Hf(E0, *i0)),
                            note="帯の出口の振幅・位相（A1 の比）と、A2' の速さの誤差・振幅の変化を、線形の焦点の模型（p_plan_numbers.py の形）に入れた")
    # ---- B1：エネルギーの流れ
    cgf = cg_of_f(fr, C["h"])

    def flux(Fm_, Fl_):
        pin = (abs(Fm_[mb]) ** 2 * cgf[mb]).sum() / (abs(Fl_[mb]) ** 2 * cgf[mb]).sum()
        lo = (fr > 0) & (fr < f[0] - df / 2); hi = fr > f[-1] + df / 2
        Ein = (abs(Fm_[mb]) ** 2 * cgf[mb]).sum()
        return float(pin), float((abs(Fm_[lo]) ** 2 * cgf[lo]).sum() / Ein), float((abs(Fm_[hi]) ** 2 * cgf[hi]).sum() / Ein)
    xr3, em3, el3 = GA["kc(x-xb)=-10"]
    fr3, Fm3, Fl3 = spec_ratio(np.nan_to_num(em3), el3, C)
    p_exit, lo_exit, hi_exit = flux(Fm, Fl)
    p_m15, lo_m15, hi_m15 = flux(Fm2, Fl2)
    p_m10, lo_m10, hi_m10 = flux(Fm3, Fl3)
    out["B1"] = dict(flux_ratio_exit=p_exit, flux_ratio_m15=p_m15, flux_ratio_m10=p_m10, loss_exit_to_m10=float(1 - p_m10 / p_exit),
                     loss_ok=bool(1 - p_m10 / p_exit <= 0.05), outside_low=[lo_exit, lo_m15, lo_m10], outside_high=[hi_exit, hi_m15, hi_m10],
                     note="flux_ratio は測った値 ÷ 線形の値（成分の帯域の中）。outside は帯域の外（低い側・高い側）のエネルギーの流れ ÷ 帯域の中")
    # ---- 各場所の最大の頂（群の集まり）
    tm = t >= min(60.0, 0.5 * float(t.max()))
    xm = (x >= xp) & (x <= xp + 930)
    mx = np.nanmax(EX[tm][:, xm], axis=0)
    out["crest_max_along_x"] = dict(x_rel=(x[xm] - xp).tolist(), max=mx.tolist(), t_at=t[tm][np.nanargmax(EX[tm][:, xm], axis=0)].tolist())
    j = int(np.nanargmax(mx))
    out["overall_max"] = dict(x_rel=float(x[xm][j] - xp), eta=float(mx[j]), t=float(t[tm][np.nanargmax(EX[tm][:, xm][:, j])]))
    # 線形の各場所の最大
    xl = np.arange(0, 931, 2.0); tl = np.arange(60, t_end, 0.1)
    El = np.concatenate([eta_lin_xt(C, xl[i:i + 50], tl) for i in range(0, len(xl), 50)], 0)
    out["lin_crest_max_along_x"] = dict(x_rel=xl.tolist(), max=El.max(1).tolist())
    # ---- 断面：巻き始め・着水・各コマの形
    if not quick:
        SEC = load_sec(rid)
        series = []
        onset = touch = None
        if SEC is not None:
            meta = SEC["meta"]
            xsec0 = meta["x0"]; xsec1 = meta["x0"] + meta["dx"] * (meta["nx"] - 1)
            mid = D["eta"].shape[1] // 2
            frame_index = {int(fv): i for i, fv in enumerate(D["frames"])}
            for j, fv in enumerate(SEC["frames"]):
                i = frame_index.get(int(fv))
                if i is None:
                    continue
                sh = frame_shape(SEC["sdf"][j], meta, off, vox, Lc, None, None)
                if sh is None:
                    continue
                etop = D["eta"][i, mid, :] - off
                xm2 = (x >= xsec0) & (x <= xsec1)
                tmz = top_measures(etop, x, sh["xc"], Lc)
                row = dict(frame=int(fv), t=float(SEC["t"][j]), xc_rel=sh["xc"] - xp, yc=sh["yc"], thmax=sh["thmax"], steep_h60=sh["steep_h60"],
                           tip=None if sh["tip"] is None else [sh["tip"][0] - xp, sh["tip"][1]], ncav=len(sh["cav"]))
                if tmz:
                    row.update(eta_c=tmz["eta_c"], H=tmz["H"], trough=tmz["trough"], x_trough_rel=tmz["x_trough"] - xp, d_zero=tmz["d_zero"], steep=tmz["steep"])
                series.append(row)
                if onset is None and np.isfinite(sh["thmax"]) and sh["thmax"] >= 90.0:
                    onset = dict(row)
                    # 前の面が鉛直になった点の位置
                    onset["face_vertical_x_rel"] = None
                elif onset is not None and touch is None:
                    if (sh["tip"] is not None and sh["tip"][1] <= 0.0) or len(sh["cav"]) > 0:
                        touch = dict(row); touch["by"] = "tip<=0" if (sh["tip"] is not None and sh["tip"][1] <= 0.0) else "cavity"
        out["section_series"] = series
        out["onset"] = onset
        out["touchdown"] = touch
        # N2 の時刻
        if onset is not None:
            n2 = onset; n2_by = "onset"
        else:
            cand = [r for r in series if np.isfinite(r.get("steep", np.nan))]
            n2 = max(cand, key=lambda r: r["steep"]) if cand else None; n2_by = "max_steep"
        out["N2_time"] = dict(by=n2_by, row=n2)
    out["linear"] = dict(eta_c=P["full"]["eta_c_lin"], H_x=P["full"]["H_lin_x"], xb=C["xb"], tb=C["tb"], tob_DK=P["full"]["tob_DK"], xob_DK=P["full"]["xob_DK"],
                         breaking_band_x=P["full"]["breaking_band_RM_x"])
    json.dump(out, open(os.path.join(ROOT, rid, "ana.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


if __name__ == "__main__":
    for rid in sys.argv[1:]:
        if rid.startswith("--"):
            continue
        o = analyze(rid, quick="--quick" in sys.argv)
        s = dict(run=rid, done=o["frames_done"], off=round(o["still_level_offset_m"], 3), A1=[(round(b["amp_ratio"], 3), round(b["phase_rad"], 3)) for b in o["A1"]["subbands"]],
                 S=round(o["A1"]["S_measured"], 4), A1pass=o["A1"]["pass"], e=round(o["A2p"]["speed_err_wmean"], 4), g=round(o["A2p"]["amp_change_wmean"], 3),
                 A3=o["A3p_model"], B1=round(o["B1"]["loss_exit_to_m10"], 3), maxc=o["overall_max"],
                 onset=None if not o.get("onset") else {k: o["onset"][k] for k in ("t", "xc_rel", "yc") if k in o["onset"]},
                 touch=None if not o.get("touchdown") else {k: o["touchdown"][k] for k in ("t", "tip", "by") if k in o["touchdown"]})
        print(json.dumps(s, ensure_ascii=False, default=float))
