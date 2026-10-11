# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：入口・伝わり・減り（A1・測った S・A2'・A3'・B1）を自前で計算し直す。
g_analyze.py は使わず、読み込んでもいない。入口の式は g_tanklib.py の VEX の文（読んだだけ）、定義は計画 §5 と「計画の読み方」3・4・5。
py -3.10 check_R4_spec.py → check_R4_spec.json

- 線形の値：造波板の位置 x_p の目標 η_p(t) = E(t) Σ a cos(−k_i x_b − ω_i (t − t_b))（E は始めの 1 周期の 0.5 − 0.5 cos(π t / T)）を
  0〜187.79 s（4,508 点、1/24 s）で作り、2^17 点に 0 で埋め、周波数ごとに exp(−i k(f) Δx) を掛けて測る点まで進め、0〜187.79 s で切る。
- 測った値：一番上の水面の高さを板の内側の 3 節で平均し、x で線形に補間した時系列（静かな水面を引く。4,508 点の窓では定数は 0 Hz にしか入らない）。
- 両方を同じ 4,508 点で FFT。R = F_測 / F_線。
- A1：成分 i〜j の帯域 [f_i − δ/2, f_j + δ/2] の刻みで、|F_線|² を重みに |R| と arg R を平均。測った S = S Σ k|F_測| / Σ k|F_線|（成分の帯域の全体）。
- B1：エネルギーの流れ Σ |F|² c_g（成分の帯域の中）の 測/線 の比。減り = 1 − 比(−10) / 比(帯の出口)。
- A2'：帯の出口と −15 の点の R から e(f) = −Δ arg R / (k Δx)、振幅の変化 |R_−15| / |R_出口|、0.077〜0.134 Hz の刻み。
- A3'：測った値を線形の焦点の模型に入れる（p_plan_numbers.py の focus_with_speed_error と同じ格子の取り方を、自前で書いた）。
  入れ方で結果が変わるかを見るため、いくつかの入れ方を並べる。
"""
import os, json, math
import numpy as np
from ck_common import cfg, load_hf, still_level, PLAN, FPS, G

OUTDIR = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(PLAN, encoding="utf-8"))
Tc = P["full"]["Tc"]; Lc = P["full"]["Lc"]


def k_of_f(f, h):
    f = np.atleast_1d(np.asarray(f, float))
    om = 2 * np.pi * f
    k = np.maximum(om * om / G, om / math.sqrt(G * h))
    k[om == 0] = 0.0
    for _ in range(80):
        th = np.tanh(k * h)
        F = G * k * th - om * om
        dF = G * th + G * k * h * (1 - th * th)
        dk = np.where(dF > 0, F / np.where(dF > 0, dF, 1), 0)
        k = k - dk
    k[om == 0] = 0.0
    return k


def cg_of_f(f, h):
    k = k_of_f(f, h); om = 2 * np.pi * np.asarray(f, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        c = np.where(k > 0, om / k, math.sqrt(G * h))
        n = np.where(k > 0, 0.5 * (1 + 2 * k * h / np.sinh(np.minimum(2 * k * h, 700))), 1.0)
    return c * n


def comps(c):
    p = c["parms"]
    N = int(p["ncomp"]); fc = p["fc"]; dff = p["dff"]; h = p["h0"]
    f = np.linspace(fc * (1 - 0.5 * dff), fc * (1 + 0.5 * dff), N)   # VEX と同じ：fa + (fb − fa) i/(N − 1)
    k = k_of_f(f, h)
    a = p["S"] / k.sum()
    return f, k, a


def linear_at(c, xrel_list, n):
    p = c["parms"]; h = p["h0"]
    f, k, a = comps(c)
    t = np.arange(n) / FPS
    R = p["ramp_s"]
    E = np.where(t < R, 0.5 - 0.5 * np.cos(np.pi * np.clip(t / R, 0, 1)), 1.0)
    om = 2 * np.pi * f
    eta_p = E * np.sum(a * np.cos(-k[None, :] * p["x_b"] - om[None, :] * (t[:, None] - p["t_b"])), axis=1)
    NP = 2 ** 17
    F = np.fft.rfft(eta_p, NP)
    ff = np.fft.rfftfreq(NP, 1 / FPS)
    kk = k_of_f(ff, h)
    out = []
    for dx in xrel_list:
        out.append(np.fft.irfft(F * np.exp(-1j * kk * dx), NP)[:n])
    return np.array(out), eta_p


def gauge_series(hf, c, xrel, off):
    xr = hf["x"] - c["parms"]["x_p"]
    A = hf["in3"]
    j = np.searchsorted(xr, xrel)
    w = (xrel - xr[j - 1]) / (xr[j] - xr[j - 1])
    return (1 - w) * A[:, j - 1] + w * A[:, j] - off


def analyze(run, sub_t1=None):
    c = cfg(run)
    p = c["parms"]; h = p["h0"]; xp = p["x_p"]
    hf = load_hf(run)
    off = still_level(hf, xp, "in3")
    n = len(hf["t"]) if sub_t1 is None else int(np.searchsorted(hf["t"], sub_t1 + 1e-9))
    G_ = {k: v - xp for k, v in c["case"]["gauges"].items()}
    names = list(G_.keys())
    lin, eta_p = linear_at(c, [G_[k] for k in names], n)
    f, k, a = comps(c)
    dlt = (f[-1] - f[0]) / (len(f) - 1)
    ff = np.fft.rfftfreq(n, 1 / FPS)
    kf = k_of_f(ff, h); cg = cg_of_f(ff, h)
    FM = {}; FL = {}
    for i, nm in enumerate(names):
        m = gauge_series(hf, c, G_[nm], off)[:n]
        FM[nm] = np.fft.rfft(m); FL[nm] = np.fft.rfft(lin[i])
    res = dict(run=run, n=n, off_in3=off, df=float(ff[1]), comps_f=[float(f[0]), float(f[-1])], a=float(a), delta=float(dlt), gauges=G_)
    # A1
    ex = "band_exit"
    R = FM[ex] / FL[ex]
    sb = []
    for (i, j) in ([1, 11], [12, 21], [22, 32]):
        m = (ff >= f[i - 1] - dlt / 2) & (ff <= f[j - 1] + dlt / 2)
        w = np.abs(FL[ex][m]) ** 2
        amp = float(np.sum(w * np.abs(R[m])) / np.sum(w)); ph = float(np.sum(w * np.angle(R[m])) / np.sum(w))
        sb.append(dict(components=[i, j], nbins=int(m.sum()), amp=amp, phase=ph, amp_ok=abs(amp - 1) <= 0.05, phase_ok=abs(ph) <= 0.1))
    mb = (ff >= f[0] - dlt / 2) & (ff <= f[-1] + dlt / 2)
    S_meas = p["S"] * float(np.sum(kf[mb] * np.abs(FM[ex][mb])) / np.sum(kf[mb] * np.abs(FL[ex][mb])))
    res["A1"] = dict(subbands=sb, S=S_meas, S_ok=0.334 <= S_meas <= 0.370, pass_=all(s["amp_ok"] and s["phase_ok"] for s in sb) and 0.334 <= S_meas <= 0.370)
    # A1 の感度：一番近い節・真ん中の節だけ
    # B1
    fl = {}
    for nm in names:
        fm_ = float(np.sum(np.abs(FM[nm][mb]) ** 2 * cg[mb])); fl_ = float(np.sum(np.abs(FL[nm][mb]) ** 2 * cg[mb]))
        lo = (ff > 0) & (ff < f[0] - dlt / 2); hi = (ff > f[-1] + dlt / 2)
        hi05 = hi & (ff <= 0.5)
        fl[nm] = dict(ratio=fm_ / fl_, out_low=float(np.sum(np.abs(FM[nm][lo]) ** 2 * cg[lo])) / fm_,
                      out_high=float(np.sum(np.abs(FM[nm][hi]) ** 2 * cg[hi])) / fm_, out_high_le05=float(np.sum(np.abs(FM[nm][hi05]) ** 2 * cg[hi05])) / fm_)
    loss = 1 - fl["kc(x-xb)=-10"]["ratio"] / fl[ex]["ratio"]
    res["B1"] = dict(flux=fl, loss=loss, ok=loss <= 0.05)
    # A2'
    m15 = "kc(x-xb)=-15"
    R15 = FM[m15] / FL[m15]
    m2 = (ff >= 0.077) & (ff <= 0.134)
    dX = G_[m15] - G_[ex]
    dphi = np.angle(R15[m2] / R[m2])
    e = -dphi / (kf[m2] * dX)
    ac = np.abs(R15[m2]) / np.abs(R[m2])
    w1 = np.abs(FL[ex][m2]) ** 2; w2 = np.abs(FL[m15][m2]) ** 2; w3 = np.abs(FL[ex][m2] * FL[m15][m2])
    res["A2p"] = dict(f=ff[m2].tolist(), e=e.tolist(), amp_change=ac.tolist(), dX=dX,
                      e_wmean_exitW=float(np.sum(w1 * e) / np.sum(w1)), e_wmean_m15W=float(np.sum(w2 * e) / np.sum(w2)), e_wmean_geoW=float(np.sum(w3 * e) / np.sum(w3)),
                      e_mean=float(np.mean(e)),
                      ac_wmean_exitW=float(np.sum(w1 * ac) / np.sum(w1)), ac_wmean_m15W=float(np.sum(w2 * ac) / np.sum(w2)), ac_wmean_geoW=float(np.sum(w3 * ac) / np.sum(w3)))
    res["_R_exit"] = (ff, R)
    res["_A2"] = (ff[m2], e, ac)
    res["_comp"] = (f, k, a, p)
    # 測る点の最大（記録の値と比べる）
    res["gauge_max"] = {nm: float(np.max(gauge_series(hf, c, G_[nm], off)[:n])) for nm in names}
    res["gauge_tmax"] = {nm: float(np.argmax(gauge_series(hf, c, G_[nm], off)[:n]) / FPS) for nm in names}
    res["gauge_tmax_lin"] = {nm: float(np.argmax(lin[i]) / FPS) for i, nm in enumerate(names)}
    return res


def a3_model(res, variant, flipped=False, nx=1001, nt=901):
    """線形の焦点の模型（自前）。variant：
    'A2only_const'  A2' の速さの誤差と振幅の変化（定数の掛け算）だけ。計画 §5 A3' の文のまま
    'A2only_exp'    A2' の速さの誤差と振幅の変化（帯の出口からの距離で指数的に伸ばす）
    'A1A2_const'    A1 の帯の出口の比（振幅と位相）も入れる。振幅の変化は定数
    'A1A2_exp'      A1 の比も入れ、振幅の変化は距離で指数的に伸ばす
    速さの誤差・振幅の変化は、測った刻み（0.077〜0.134 Hz）の値を成分の周波数へ線形に補間し、帯域の外は端の値で延ばす。"""
    f, k, a, p = res["_comp"]
    fA, e, ac = res["_A2"]
    ff, R = res["_R_exit"]
    ei = np.interp(f, fA, e); aci = np.interp(f, fA, ac)
    Re = np.interp(f, ff, R.real) + 1j * np.interp(f, ff, R.imag)
    xb = p["x_b"]; tb = p["t_b"]; om = 2 * np.pi * f
    xe = res["gauges"]["band_exit"]; dX = res["A2p"]["dX"]
    xs = xb + np.linspace(-1.0, 1.5, nx) * Lc
    ts = tb + np.linspace(-1.5, 3.0, nt) * Tc
    kk = k / (1 - ei)

    sg = -1.0 if flipped else 1.0

    def field(use_err, amp_mode, use_a1):
        # 位相の向き：線形の成分は cos(k(x − x_b) − ω(t − t_b)) = cos(ωt + θ)。測った値は FFT（e^{−iωt}）で θ + arg R なので、
        # 余分の位相は cos の中で −arg R になる。波数が kk になった分は +(kk − k)(x − x_e)。
        # flipped=True は両方の符号を逆にした形（g_analyze.py の A3' の式の形。記録の値が出るかの確かめに使う）
        A = np.full((len(xs), len(f)), a)
        ph = (-k * xb)[None, :] + 0 * xs[:, None]
        if use_err:
            ph = ph + k[None, :] * xs[:, None] + sg * (kk - k)[None, :] * (xs[:, None] - xe)
            if amp_mode == "const":
                A = A * aci[None, :]
            else:
                A = A * aci[None, :] ** ((xs[:, None] - xe) / dX)
            if use_a1:
                A = A * np.abs(Re)[None, :]
                ph = ph - sg * np.angle(Re)[None, :]
        else:
            ph = ph + k[None, :] * xs[:, None]
        E = np.zeros((len(xs), len(ts)))
        for i in range(len(f)):
            E += A[:, i][:, None] * np.cos(ph[:, i][:, None] - om[i] * (ts[None, :] - tb))
        return E
    def gauge_tmax(xg, use_err, amp_mode, use_a1):
        """模型の −15 の点の時系列の最大の時刻（測った記録と同じ向きに早く着くかの確かめ）"""
        tt = np.arange(100.0, 160.0, 1 / 24)
        A = np.full(len(f), a); ph = k * (xg - xb)
        if use_err:
            ph = ph + sg * (kk - k) * (xg - xe)
            A = A * (aci if amp_mode == "const" else aci ** ((xg - xe) / dX))
            if use_a1:
                A = A * np.abs(Re); ph = ph - sg * np.angle(Re)
        e = np.sum(A[None, :] * np.cos(ph[None, :] - om[None, :] * (tt[:, None] - tb)), axis=1)
        return float(tt[np.argmax(e)])
    mode = "const" if variant.endswith("const") else "exp"
    xg15 = res["gauges"]["kc(x-xb)=-15"]
    t15 = dict(lin=gauge_tmax(xg15, False, mode, False), model=gauge_tmax(xg15, True, mode, variant.startswith("A1A2")))
    use_a1 = variant.startswith("A1A2")
    E0 = field(False, mode, use_a1); E1 = field(True, mode, use_a1)
    i0 = np.unravel_index(np.argmax(E0), E0.shape); i1 = np.unravel_index(np.argmax(E1), E1.shape)

    def Hfront(E, ix, it):
        row = E[:, it]; j = ix
        while j + 1 < len(row) and row[j + 1] < row[j]:
            j += 1
        return float(row[ix] - row[j])

    def Hmin(E, ix, it):
        row = E[:, it]; mm = (xs > xs[ix]) & (xs <= xs[ix] + 0.75 * Lc)
        return float(row[ix] - row[mm].min())
    return dict(variant=variant + ("_flipped_%dx%d" % (nx, nt) if flipped else ""), t_max_at_m15=t15, H_ratio_min075=float(Hmin(E1, *i1) / Hmin(E0, *i0)), dx_Lc=float((xs[i1[0]] - xs[i0[0]]) / Lc), dt_Tc=float((ts[i1[1]] - ts[i0[1]]) / Tc),
                crest_ratio=float(E1[i1] / E0[i0]), H_ratio=float(Hfront(E1, *i1) / Hfront(E0, *i0)),
                lin_focus=[float(xs[i0[0]]), float(ts[i0[1]])])


def main():
    out = {}
    for run in ("R4d", "R3", "R2", "R1b"):
        r = analyze(run)
        if run in ("R4d", "R3"):
            r["A3p"] = [a3_model(r, v) for v in ("A2only_const", "A2only_exp", "A1A2_const", "A1A2_exp")]
            r["A3p"].append(a3_model(r, "A1A2_exp", flipped=True, nx=501, nt=451))
            r["A3p"].append(a3_model(r, "A1A2_exp", flipped=True))
            r139 = analyze(run, sub_t1=139.0)
            r["A1_0_139"] = r139["A1"]
        for kx in ("_R_exit", "_A2", "_comp"):
            r.pop(kx)
        out[run] = r
        sb = r["A1"]["subbands"]
        print(run, "A1", [(round(s["amp"], 4), round(s["phase"], 3)) for s in sb], "S", round(r["A1"]["S"], 4), "B1", round(r["B1"]["loss"], 4),
              "A2p", round(r["A2p"]["e_wmean_exitW"], 5), round(r["A2p"]["ac_wmean_exitW"], 4))
        if "A3p" in r:
            for v in r["A3p"]:
                print("   A3'", v["variant"], round(v["dx_Lc"], 4), round(v["dt_Tc"], 4), round(v["crest_ratio"], 4), round(v["H_ratio"], 4), round(v["H_ratio_min075"], 4), "t_max(-15) lin/model", round(v["t_max_at_m15"]["lin"], 3), round(v["t_max_at_m15"]["model"], 3))
    json.dump(out, open(os.path.join(OUTDIR, "check_R4_spec.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
