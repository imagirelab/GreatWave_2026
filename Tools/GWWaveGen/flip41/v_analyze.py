# -*- coding: utf-8 -*-
"""FLIP41 確かめ：計算の水面 η(x, t) から、波の速さ・高さの減り・跳ね返り・造波の出口の高さと位相を出す（py -3.10）。
使い方: py -3.10 v_analyze.py <run_id> [...]   → runs/<run_id>/ana.json
方法（走らせる前に plan_ja.md §4 で決めたとおり）：
  1. 板の厚さ方向（z、格子 4 個）で平均した η(x, t) から、測る窓（周期の整数倍）で、周波数 nω（n = 1, 2, 3）の複素振幅
     A_n(x) = (2/N) Σ (η − 平均) e^{i n ω t} を各 x で出す。η = a cos(kx − ωt + φ) なら A = a e^{i(kx + φ)}。
  2. 測る区間で、進む波 c1·e^{(ik − α)(x − xm)} と戻る波 c2·e^{−ik(x − xm)} の和に最小二乗で合わせ、k・α・c1・c2 を出す
     （進む波と戻る波の分け方は Goda & Suzuki 1976・Mansard & Funke 1980 と同じ考え。ここでは区間の全部の点を使う）。
  3. 速さ c = ω/k を線形の分散の値と比べる。高さの減りは 3 波長あたり 1 − e^{−3αL}。跳ね返り |c2|/|c1|。
  4. 造波の出口（帯の終わり、またはピストンの 1.5 波長先）の進む波の高さと位相を、目標と比べる。
  5. 測る窓を 1 周期ずつずらした 3 つの窓でも同じことをして、ばらつきを出す。
"""
import sys, os, json, glob, math
import numpy as np
from scipy.optimize import least_squares
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
from v_lin import props, k_of_omega, ks as ks_lin, bed_profile, stokes2_a2, stokes3_dc, G

R = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify/runs"


def load(rid):
    rd = os.path.join(R, rid)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    files = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")))
    F, T, E = [], [], []
    x = z = None
    wall = []
    for fpath in files:
        d = np.load(fpath)
        fr = d["frames"]
        if F:
            keep = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in keep]; T = [T[i] for i in keep]; E = [E[i] for i in keep]; wall = [wall[i] for i in keep]
        F += list(fr); T += list(d["t"]); E += list(d["eta"]); wall += list(d["wall"])
        x = d["x"]; z = d["z"]
    eta = np.array(E, np.float64)       # (nt, nz, nx)
    # 古い記録（T1_dp1）は x を格子の中心（Δ/2 から）に置いていたが、場の標本は節（0 から）だった。場の位置へ戻す
    rj = os.path.join(rd, "run_c0001.json")
    if os.path.exists(rj):
        gi = json.load(open(rj, encoding="utf8")).get("grid") or {}
        if "x0" in gi and abs((x[0] - gi["x0"]) - 0.5 * gi.get("dx", 0)) < 1e-6 and gi.get("dx", 0) > 0:
            x = x - 0.5 * gi["dx"]
    nz = eta.shape[1]
    zz = slice(1, nz - 1) if nz >= 3 else slice(0, nz)
    ex = np.nanmean(eta[:, zz, :], axis=1)
    return cfg, np.array(T), x, ex, np.array(F), np.array(wall)


def load_probe(rid):
    """流速の見張り（v_run.py、2026-10-08 22:45 から）：tp（時刻）、up（時刻, 3 か所, 深さ）、prb_x、prb_y。無ければ None。"""
    rd = os.path.join(R, rid)
    TP, UP = [], []
    px = py_ = None
    for fpath in sorted(glob.glob(os.path.join(rd, "hf_c*.npz"))):
        d = np.load(fpath)
        if "up" not in d.files or len(d["tp"]) == 0:
            continue
        tp = list(d["tp"])
        if TP:
            keep = [i for i, t in enumerate(TP) if t < tp[0] - 1e-9]
            TP = [TP[i] for i in keep]; UP = [UP[i] for i in keep]
        TP += tp; UP += list(d["up"])
        px = d["prb_x"]; py_ = d["prb_y"]
    if not TP:
        return None
    return np.array(TP), np.array(UP), px, py_


def mean_current(rid, t0, t1, eta_mean=None):
    pr = load_probe(rid)
    if pr is None:
        return None
    tp, up, px, py_ = pr
    m = (tp >= t0) & (tp <= t1)
    if m.sum() < 4:
        return None
    um = np.nanmean(up[m], axis=0)      # (3, ny)
    out = []
    for i, xp in enumerate(px):
        prof = um[i]
        ok = np.isfinite(prof) & (np.abs(prof) < 50)
        out.append(dict(x=float(xp), u_depth_mean=float(np.mean(prof[ok])) if ok.any() else None,
                        u_top=float(np.mean(prof[ok][-2:])) if ok.sum() >= 2 else None,
                        u_bottom=float(np.mean(prof[ok][:2])) if ok.sum() >= 2 else None,
                        profile=[float(v) for v in prof], y=[float(v) for v in py_]))
    return out


def harmonics(t, ex, om, t0, t1, nmax=3):
    m = (t >= t0 - 1e-6) & (t < t1 - 1e-6)
    tt = t[m]; ee = ex[m]
    ee = ee - np.nanmean(ee, axis=0)
    ee = np.where(np.isfinite(ee), ee, 0.0)
    N = len(tt)
    out = []
    for n in range(1, nmax + 1):
        out.append((2.0 / N) * (ee * np.exp(1j * n * om * tt)[:, None]).sum(axis=0))
    return out, N


def fit_inc_ref(x, A, k0, xm, decay=True):
    ok = np.isfinite(A)
    x = x[ok]; A = A[ok]
    X = x - xm

    def lin(k, al):
        M = np.stack([np.exp((1j * k - al) * X), np.exp(-1j * k * X)], 1)
        c, *_ = np.linalg.lstsq(M, A, rcond=None)
        return c, M

    def res(p):
        k, al = p[0], (p[1] if decay else 0.0)
        c, M = lin(k, al)
        r = M @ c - A
        return np.concatenate([r.real, r.imag])
    best = None
    for f in np.linspace(0.9, 1.1, 41):
        p0 = [k0 * f, 0.0] if decay else [k0 * f]
        s = np.sum(res(p0) ** 2)
        if best is None or s < best[0]:
            best = (s, p0)
    sol = least_squares(res, best[1], x_scale=[k0, k0 * 0.01][:len(best[1])], xtol=1e-12, ftol=1e-12)
    k = sol.x[0]; al = sol.x[1] if decay else 0.0
    c, M = lin(k, al)
    J = sol.jac
    dof = max(1, 2 * len(A) - len(sol.x) - 4)
    s2 = np.sum(sol.fun ** 2) / dof
    try:
        cov = np.linalg.inv(J.T @ J) * s2
        sk = float(np.sqrt(cov[0, 0])); sal = float(np.sqrt(cov[1, 1])) if decay else 0.0
    except Exception:
        sk, sal = float("nan"), float("nan")
    rms = float(np.sqrt(np.mean(np.abs(M @ c - A) ** 2)))
    return dict(k=float(k), alpha=float(al), c1=c[0], c2=c[1], sk=sk, salpha=sal, rms=rms, n=int(len(A)))


def b1(rid):
    cfg, t, x, ex, F, wall = load(rid)
    cs = cfg["case"]
    om, kl, L, a_t = cs["om"], cs["k"], cs["L"], cs["a"]
    T = cs["T"]; h = cs["h"]
    t0, t1 = cs["t_win"]
    if t[-1] < t1 - 1e-6:
        return dict(run_id=rid, error="計算が測る窓の終わり（%.1f s）まで届いていない（最後 %.1f s）" % (t1, t[-1]))
    xm0, xm1 = cs["x_meas"]
    sel = (x >= xm0) & (x <= xm1)
    xm = 0.5 * (xm0 + xm1)
    res = {}
    wins = [(t0, t1)] + [(t0 + j * T, t0 + j * T + 3 * T) for j in range(0, 3)]
    fits = []
    for (a0, a1) in wins:
        Hs, N = harmonics(t, ex, om, a0, a1)
        f = fit_inc_ref(x[sel], Hs[0][sel], kl, xm)
        fits.append((a0, a1, f, Hs, N))
    a0, a1, f, Hs, N = fits[0]
    k = f["k"]; c = om / k
    c_lin = om / kl
    dc3 = stokes3_dc(a_t, kl, h)
    # 造波の出口：出口から 1 波長の窓で、進む波と戻る波を合わせ（k は窓の中で合わせる）、窓の中心の進む波の振幅を出口の振幅とする。
    # 位相は、窓の中心の位相を窓で合わせた k で出口まで戻した値を、目標の位相 k線形·x と比べる（緩和の帯だけ）
    x_exit = cs["xg"] if cs["wm"] == "relax" else cfg["parms"]["xp0"] + 1.5 * L
    mw = (x >= x_exit) & (x <= x_exit + L)
    fe = fit_inc_ref(x[mw], Hs[0][mw], kl, x_exit + 0.5 * L, decay=True)
    A_exit = fe["c1"] * np.exp(-(1j * fe["k"] - fe["alpha"]) * 0.5 * L)   # 窓の中心から出口まで、窓で合わせた k と減りで戻す
    ph_target = kl * x_exit if cs["wm"] == "relax" else None
    dph = float(np.angle(A_exit * np.exp(-1j * ph_target))) if ph_target is not None else None
    # 場所ごとの速さ：1 波長の窓を半波長ずつずらして、進む波と戻る波を合わせる（減りは入れない）
    local = []
    xc = xm0 + 0.5 * L
    while xc <= xm1 - 0.5 * L + 1e-6:
        mw2 = (x >= xc - 0.5 * L) & (x <= xc + 0.5 * L)
        fl = fit_inc_ref(x[mw2], Hs[0][mw2], kl, xc, decay=False)
        local.append(dict(x=float(xc), c_err=float(kl / fl["k"] - 1), a=float(abs(fl["c1"]))))
        xc += 0.5 * L
    # 2 倍・3 倍の周波数（区間の平均の大きさ）
    a2 = float(np.nanmean(np.abs(Hs[1][sel]))); a3 = float(np.nanmean(np.abs(Hs[2][sel])))
    a1m = float(np.nanmean(np.abs(Hs[0][sel])))
    sub = []
    for (b0, b1_, ff, _, _) in fits[1:]:
        sub.append(dict(win=[b0, b1_], c_err=om / ff["k"] / c_lin - 1, alpha=ff["alpha"], R=float(abs(ff["c2"]) / abs(ff["c1"]))))
    errs = [s["c_err"] for s in sub]
    mc = mean_current(rid, t0, t1)
    res = dict(run_id=rid, case=cs, win=[a0, a1], N=N, mean_current=mc,
               k=k, k_lin=kl, c=c, c_lin=c_lin, c_err=c / c_lin - 1, c_err_sd_fit=f["sk"] / k,
               c_err_spread=float(np.max(errs) - np.min(errs)), stokes3_dc=dc3,
               alpha=f["alpha"], alpha_sd=f["salpha"], decay_3L=float(1 - math.exp(-3 * f["alpha"] * L)),
               decay_3L_sd=float(3 * L * f["salpha"]),
               R=float(abs(f["c2"]) / abs(f["c1"])),
               a_exit=float(abs(A_exit)), a_target=a_t, k_exit_err=float(kl / fe["k"] - 1), R_exit=float(abs(fe["c2"]) / abs(fe["c1"])), a_exit_ratio=float(abs(A_exit) / a_t), dphase_exit=dph,
               a1_mean=a1m, a2_mean=a2, a3_mean=a3, a2_stokes=stokes2_a2(a_t, kl, h), fit_rms=f["rms"], fit_n=f["n"],
               sub_windows=sub, local=local, c_err_local_min=float(min(r['c_err'] for r in local)) if local else None,
               c_err_local_max=float(max(r['c_err'] for r in local)) if local else None,
               wall_per_frame_median=float(np.median(wall[1:])) if len(wall) > 1 else None,
               wall_total_s=float(np.sum(wall)), frames=int(len(F)))
    # 図のための曲線
    res["_curve"] = dict(x=x.tolist(), A1=[[float(v.real), float(v.imag)] for v in Hs[0]],
                         A2=np.abs(Hs[1]).tolist(), sel=[xm0, xm1], xm=xm)
    return res


def b2(rid):
    cfg, t, x, ex, F, wall = load(rid)
    cs = cfg["case"]
    T, om = cs["T"], cs["om"]
    h0, h1, n = cs["h0"], cs["h1"], cs["n"]
    t0, t1 = cs["t_win"]
    if t[-1] < t1 - 1e-6:
        return dict(run_id=rid, error="計算が測る窓の終わり（%.1f s）まで届いていない（最後 %.1f s）" % (t1, t[-1]))
    hx = bed_profile(x, h0, cs["xs0"], n, h1)
    klx = np.array([k_of_omega(om, v) for v in hx])

    def analyse(A):
        # 局所の波数：その場の 1 波長の窓で、進む波と戻る波を合わせる（減りは入れない）
        rows = []
        xc_list = np.arange(cs["xg"] + 0.5 * cs["L0"], cs["xa0"] - 0.5 * cs["L1"], 0.25 * cs["L1"])
        for xc in xc_list:
            Lloc = 2 * math.pi / k_of_omega(om, float(bed_profile(xc, h0, cs["xs0"], n, h1)))
            m = (x >= xc - 0.5 * Lloc) & (x <= xc + 0.5 * Lloc)
            if m.sum() < 8:
                continue
            k0 = 2 * math.pi / Lloc
            f = fit_inc_ref(x[m], A[m], k0, xc, decay=False)
            rows.append(dict(x=float(xc), h=float(bed_profile(xc, h0, cs["xs0"], n, h1)), k=f["k"], k_lin=k0,
                             c_err=k0 / f["k"] - 1, a=float(abs(f["c1"])), R=float(abs(f["c2"]) / max(abs(f["c1"]), 1e-9)), sk=f["sk"] / f["k"]))
        # 沖の基準（斜面の前、平らな所）
        xo0, xo1 = cs["x_off"]
        so = (x >= xo0) & (x <= xo1)
        fo = fit_inc_ref(x[so], A[so], cs["k0"], 0.5 * (xo0 + xo1))
        a_off = float(abs(fo["c1"]))
        for r in rows:
            r["Ks_lin"] = ks_lin(T, h0, r["h"]) if r["h"] < h0 - 1e-6 else 1.0
            r["Ks_num"] = r["a"] / a_off
            r["Ks_err"] = r["Ks_num"] / r["Ks_lin"] - 1
        # 斜面の下の端の高さに対する比（沖の平らな所が乱れている時の、もう一つの基準）
        toe = [r for r in rows if abs(r["x"] - cs["xs0"]) <= 0.5 * cs["L0"]]
        a_toe = float(np.mean([r["a"] for r in toe])) if toe else float("nan")
        for r in rows:
            r["Ks_num_toe"] = r["a"] / a_toe
            r["Ks_lin_toe"] = r["Ks_lin"]
        # 位相の進み（斜面の下の端 → 上の端）：進む波の位相 arg(A) を連続にして、線形の ∫k dx と比べる
        ph = np.unwrap(np.angle(np.where(np.isfinite(A), A, 0)))

        def ph_at(xq, w):
            m = (x >= xq - 0.5 * w) & (x <= xq + 0.5 * w)
            p = np.polyfit(x[m], ph[m], 1)       # 局所の直線で合わせた値（戻る波の小さな揺れをならす）
            return float(np.polyval(p, xq))
        xa = cs["xs0"]; xb = cs["xs1"]
        wa = 2 * math.pi / k_of_omega(om, h0); wb = 2 * math.pi / k_of_omega(om, h1)
        dphi_num = ph_at(xb, wb) - ph_at(xa, wa)
        xx = np.linspace(xa, xb, 4001)
        dphi_lin = float(np.trapezoid([k_of_omega(om, float(v)) for v in bed_profile(xx, h0, cs["xs0"], n, h1)], xx))
        dphi_const = cs["k0"] * (xb - xa)
        return dict(a_off=a_off, a_off_ratio=a_off / cs["a"], a_toe=a_toe,
                    c_err_off=om / fo["k"] / (om / cs["k0"]) - 1, alpha_off=fo["alpha"], R_off=float(abs(fo["c2"]) / abs(fo["c1"])),
                    rows=rows, slope_phase_num=dphi_num, slope_phase_lin=dphi_lin, slope_phase_const=dphi_const,
                    slope_time_num=dphi_num / om, slope_time_lin=dphi_lin / om, slope_time_const=dphi_const / om,
                    slope_time_err=(dphi_num - dphi_lin) / om, ph=ph)

    # (1) 全部の場所で同じ測る窓（計画のとおり）
    Hs, N = harmonics(t, ex, om, t0, t1)
    A = Hs[0]
    g = analyse(A)
    # (2) 場所ごとの窓：その場所に波の先頭（群速度）が着いて 3 周期の後からの 5 周期。後の時刻に造波の帯の近くで育つ乱れ（時空間図）を避ける
    cgx = np.array([max(props_cg(om, v), 0.1) for v in hx])
    tarr = np.concatenate([[0.0], np.cumsum(0.5 * (1 / cgx[1:] + 1 / cgx[:-1]) * np.diff(x))])
    tw0 = np.ceil((0.5 * cs.get("ramp", 3 * T) + tarr + 3 * T) / T) * T
    tw0 = np.minimum(tw0, t1 - 5 * T)
    Ap = np.zeros(len(x), complex)
    for w0 in np.unique(tw0):
        Hw, _ = harmonics(t, ex, om, w0, w0 + 5 * T)
        m = tw0 == w0
        Ap[m] = Hw[0][m]
    gp = analyse(Ap)
    res = dict(run_id=rid, case=cs, win=[t0, t1], N=N, a_target=cs["a"],
               wall_per_frame_median=float(np.median(wall[1:])) if len(wall) > 1 else None, wall_total_s=float(np.sum(wall)))
    res.update({k: v for k, v in g.items() if k != "ph"})
    res["perx"] = {k: v for k, v in gp.items() if k != "ph"}
    res["perx"]["win_start_min"] = float(tw0.min()); res["perx"]["win_start_max"] = float(tw0.max())
    res["_curve"] = dict(x=x.tolist(), absA=np.abs(A).tolist(), absAp=np.abs(Ap).tolist(), h=hx.tolist(), klx=klx.tolist(), ph=g["ph"].tolist())
    return res


def props_cg(om, h):
    k = k_of_omega(om, h)
    kh = k * h
    n_ = 0.5 * (1 + 2 * kh / math.sinh(2 * kh)) if kh < 300 else 0.5
    return om / k * n_


def t1(rid):
    cfg, t, x, ex, F, wall = load(rid)
    cs = cfg["case"]
    t0, t1_ = cs["t_win"]
    m = (t >= t0) & (t <= t1_)
    mean_eta = np.nanmean(ex[m], axis=0)
    ref = np.nanmean(ex[(t > 0.5) & (t < 2.0)], axis=0)        # 圧力が効く前（なだらかさ 30 s の始め）の水面
    d = mean_eta - ref
    ok = np.isfinite(d) & (x > 4) & (x < x.max() - 4)
    M = np.stack([np.ones(ok.sum()), np.cos(cs["k"] * x[ok]), np.sin(cs["k"] * x[ok])], 1)
    cf, *_ = np.linalg.lstsq(M, d[ok], rcond=None)
    resid = d[ok] - M @ cf
    # 揺れ：窓の中の時間の標準偏差（場所の平均）
    sd_t = float(np.nanmean(np.nanstd(ex[m], axis=0)))
    sd_still = float(np.nanmean(np.nanstd(ex[(t > 1) & (t < 6)], axis=0)))
    return dict(run_id=rid, case=cs, cos_amp=float(cf[1]), sin_amp=float(cf[2]), mean_shift=float(cf[0]),
                expect=cs["eta_expect"], ratio=float(cf[1] / cs["eta_expect"]), resid_rms=float(np.sqrt(np.mean(resid ** 2))),
                sd_time_window=sd_t, sd_time_still=sd_still,
                _curve=dict(x=x.tolist(), d=d.tolist()))


def run(rid):
    cfg = json.load(open(os.path.join(R, rid, "cfg.json"), encoding="utf8"))
    kind = cfg["case"]["kind"]
    if kind == "B1":
        out = b1(rid)
    elif kind == "B2":
        out = b2(rid)
    elif kind == "T1":
        out = t1(rid)
    else:
        raise SystemExit("unknown kind " + kind)

    def conv(o):
        if isinstance(o, complex):
            return [o.real, o.imag]
        if isinstance(o, (np.floating, np.integer)):
            return o.item()
        return str(o)
    json.dump(out, open(os.path.join(R, rid, "ana.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=conv)
    return out


if __name__ == "__main__":
    for rid in sys.argv[1:]:
        o = run(rid)
        print(json.dumps({k: v for k, v in o.items() if not k.startswith("_") and k not in ("case", "rows", "sub_windows")}, ensure_ascii=False, default=lambda v: str(v))[:1500])
        if "rows" in o:
            for r in o["rows"][::4]:
                print("  x %.0f h %.1f c_err %+.4f Ks_num %.3f Ks_lin %.3f R %.3f" % (r["x"], r["h"], r["c_err"], r["Ks_num"], r["Ks_lin"], r["R"]))
