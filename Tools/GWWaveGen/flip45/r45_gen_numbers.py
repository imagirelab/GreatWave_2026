# -*- coding: utf-8 -*-
"""FLIP45 の調べ「3D の水槽で向きのある波を起こし、吸う方法」（Unity/Build/FLIP45/research/generation_ja.md）の数を出す。
py -3.10 -I r45_gen_numbers.py で走らせる（numpy だけ。Houdini は使わない。数秒）。
出力：Unity/Build/FLIP45/research/generation_numbers.json

1. Fochesato・Grilli・Dias 2007 の成分の振幅：曲がる造波板（底で回る板）の伝達の式（Biésel）と、著者の原稿の式 (21) の 1/cosθ。
2. 定常の線形の場（成分を無限に広い平らな波とした重ね合わせ）の包絡を、窓（x 130〜340 m、y 0〜108 m）と帯の上で。
3. 焦点へ向かう光線が窓のどの辺から入るか。
4. 造波板を 3 周期で立ち上げた時の線形の過渡の場（周波数で分けて足す）と、群速度で前線を動かす近似との差。
5. 吸う帯・寄せる帯の跳ね返り：Perić & Abdel-Maksoud 2018（Ocean Eng. 147）の 1 次元の理論を、帯に斜めに入る波へ広げた計算。
   検算：(a) 同論文の「指数の重み、γ = πω、帯 2λ で CR < 1 %」、(b) FLIP37 P0 の測った跳ね返り。
6. 窓の案ごとの粒子・メモリー・時間（FLIP42 R3 の記録の係数から）。
"""
import json, math, os
import numpy as np

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/research/generation_numbers.json"
g = 9.81
res = {}


def wavenumber(om, h):
    """ω² = g k tanh(k h) を Newton で解く。"""
    k = om * om / g
    if k * h > 15.0:          # 深い水（tanh = 1）
        return k
    for _ in range(60):
        f = g * k * math.tanh(k * h) - om * om
        df = g * math.tanh(k * h) + g * k * h / math.cosh(k * h) ** 2
        k -= f / df
    return k


def flap_tf(kh):
    """底で回る板（flap）の造波：波の振幅 / 板の水面での振幅（Biésel、Dean & Dalrymple の式）。"""
    return 4.0 * math.sinh(kh) * (1.0 - math.cosh(kh) + kh * math.sinh(kh)) / (kh * (math.sinh(2 * kh) + 2 * kh))


# ---------------------------------------------------------------- 1. Fochesato ら 2007 の成分
h = 20.0
Om = 0.8971                       # 著者の原稿 §3.3
k0 = wavenumber(Om, h)
lam = 2 * math.pi / k0
c0 = Om / k0
n_ = 0.5 * (1 + 2 * k0 * h / math.sinh(2 * k0 * h))
cg = n_ * c0
a_stroke = 0.2
tf = flap_tf(k0 * h)
A0 = a_stroke * tf
N = 30
th = np.radians(np.linspace(-45.0, 45.0, N))           # 端を含む等間隔（原稿：θn は [−θmax, θmax] に一様）
th_mid = np.radians(-45.0 + 90.0 * (np.arange(N) + 0.5) / N)   # 比べ：端を含まない置き方
An = A0 / np.cos(th)
res["fochesato"] = {
    "omega": Om, "h": h, "k": k0, "lambda": lam, "c": c0, "cg": cg, "kh": k0 * h,
    "flap_tf_A_over_stroke": tf, "A0_theta0": A0, "kA0": k0 * A0,
    "sum_equal_A0": float(N * A0),
    "sum_A0_over_cos_endpoints": float(An.sum()),
    "sum_A0_over_cos_midpoints": float((A0 / np.cos(th_mid)).sum()),
    "sum_0p19_over_cos": float((0.19 / np.cos(th)).sum()),
    "A_theta45": float(A0 / math.cos(math.radians(45))),
    "note": "原稿の式 (21) は An = an (1/cosθn) × 伝達の式。kA 0.0162 は θ = 0 の成分の値（原稿 §3.3）。",
}

# ---------------------------------------------------------------- 2. 定常の線形の場の包絡
xf = 250.0
xs = np.arange(120.0, 350.01, 1.0)
ys = np.arange(0.0, 120.01, 1.0)
X, Y = np.meshgrid(xs, ys, indexing="ij")


def envelope(amps, thetas, X, Y):
    Z = np.zeros_like(X, dtype=complex)
    for a, t in zip(amps, thetas):
        Z += a * np.exp(1j * k0 * ((X - xf) * math.cos(t) + Y * math.sin(t)))
    return np.abs(Z)


def region_stats(E, x0, x1, y0, y1):
    m = (X >= x0) & (X <= x1) & (Y >= y0) & (Y <= y1)
    v = E[m]
    return {"max": float(v.max()), "median": float(np.median(v)), "p90": float(np.percentile(v, 90)), "min": float(v.min())}


E = envelope(An, th, X, Y)
E_eq = envelope(np.full(N, A0), th, X, Y)
iy0 = 0
row = E[:, iy0]
res["steady_envelope"] = {
    "focus_250_0": float(E[np.argmin(abs(xs - 250)), 0]),
    "at_211_0": float(E[np.argmin(abs(xs - 211)), 0]),
    "y0_profile_every10m": {str(int(x)): float(E[np.argmin(abs(xs - x)), 0]) for x in range(130, 341, 10)},
    "inlet_band_x130_166": region_stats(E, 130, 166, 0, 108),
    "inlet_line_x130": region_stats(E, 130, 130, 0, 108),
    "side_band_y72_108_all_x": region_stats(E, 130, 340, 72, 108),
    "side_band_y72_108_x130_200": region_stats(E, 130, 200, 72, 108),
    "side_band_y72_108_x250_340": region_stats(E, 250, 340, 72, 108),
    "exit_band_x304_340": region_stats(E, 304, 340, 0, 108),
    "exit_band_x304_340_y0_36": region_stats(E, 304, 340, 0, 36),
    "equal_amp_focus": float(E_eq[np.argmin(abs(xs - 250)), 0]),
    "note": "成分を無限に広い平らな波とした定常の包絡（m）。Fochesato らの水槽（造波板の幅 600 m）の場とは焦点から遠い所で違う。",
}
# 横の向き（y = 0 の線を離れる）の包絡の半分の幅（焦点の x で）
col = E[np.argmin(abs(xs - 250)), :]
half = col[0] / 2
iy = int(np.argmax(col < half))
res["steady_envelope"]["focus_half_width_y_m"] = float(ys[iy])

# 2b. 窓の入口を上流へ移した時（造波板の位置 x = 0 から）。y = 0 と、横の帯の上の包絡、2 次の束縛の波の目安
xs2 = np.arange(0.0, 350.01, 1.0)
ys2 = np.arange(0.0, 180.01, 1.0)
X2, Y2 = np.meshgrid(xs2, ys2, indexing="ij")
E2 = envelope(An, th, X2, Y2)


def st2(x0, x1, y0, y1):
    m = (X2 >= x0) & (X2 <= x1) & (Y2 >= y0) & (Y2 <= y1)
    v = E2[m]
    return {"max": float(v.max()), "median": float(np.median(v)), "p90": float(np.percentile(v, 90))}


sig = math.tanh(k0 * h)


def stokes2_ratio(a):
    """一つの平らな波の 2 次の束縛の成分の振幅 ÷ 1 次の振幅（Stokes 2 次、有限水深）。交わる波の 2 次とは違う目安。"""
    return k0 * a / 4.0 * (3 - sig ** 2) / sig ** 3


res["upstream"] = {
    "y0_profile": {str(x): float(E2[x, 0]) for x in [0, 18, 36, 54, 72, 94, 112, 130, 166]},
    "band_x0_36": st2(0, 36, 0, 108),
    "band_x0_72": st2(0, 72, 0, 144),
    "band_x94_166": st2(94, 166, 0, 144),
    "side_y72_144_x0_200": st2(0, 200, 72, 144),
    "side_y108_180_x0_200": st2(0, 200, 108, 180),
    "side_y72_144_x250_376": st2(250, 340, 72, 144),
    "stokes2_ratio": {str(a): stokes2_ratio(a) for a in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.8, 6.3]},
    "miche_H_over_L": 0.142 * sig,
}

# ---------------------------------------------------------------- 3. 光線の入る辺
rays = []
for deg in [5, 10, 15, 20, 25, 30, 35, 40, 41.9, 45]:
    t = math.radians(deg)
    # 焦点 (250, 0) へ −y 向きに進む成分（+y の側から来る）。光線 y = (250 − x) tanθ
    y_at_130 = (250 - 130) * math.tan(t)
    y_at_166 = (250 - 166) * math.tan(t)
    x_at_y108 = 250 - 108 / math.tan(t)
    x_at_y72 = 250 - 72 / math.tan(t)
    rays.append({"theta_deg": deg, "y_at_x130": y_at_130, "y_at_x166": y_at_166,
                 "x_at_y108": x_at_y108, "x_at_y72": x_at_y72,
                 "enters_via": "upstream x=130" if y_at_130 <= 108 else "side y=108"})
res["rays_to_focus"] = {"critical_theta_deg_for_side_entry": math.degrees(math.atan(108 / 120)), "rays": rays,
                        "paddle_y_for_45deg_ray_in_fochesato_tank": 250 * math.tan(math.radians(45))}

# ---------------------------------------------------------------- 4. 線形の過渡（3 周期の立ち上げ）
T = 2 * math.pi / Om
dt = 0.1
Ttot = 819.2
tt = np.arange(0, Ttot, dt)
nt = len(tt)


def ramp(kind, t):
    if kind == "tanh_a":        # tanh(t / T)：t = 3T で 0.995
        r = np.tanh(t / T)
    elif kind == "tanh_s":      # 0.5(1 + tanh(2t/T − 3))：t = 0 で 0.0025、3T で 0.9975
        r = 0.5 * (1 + np.tanh(2 * t / T - 3))
    else:
        raise ValueError(kind)
    down = np.clip((t - 300.0) / 30.0, 0, 1)          # 300〜330 s で下げる（FFT の周期の折り返しを避ける）
    return r * (1 - 0.5 + 0.5 * np.cos(math.pi * down)) * (t < 330)


om_f = 2 * math.pi * np.fft.fftfreq(nt, dt)            # e^{-iωt} の約束で ω>0 が進む波
xq = np.array([36.0, 72.0, 94.0, 130.0, 166.0, 211.0, 250.0, 304.0])
tq_idx = np.arange(0, int(120 / dt))
trans = {}
for kind in ["tanh_a", "tanh_s"]:
    R = ramp(kind, tt)
    # 一つの成分の板の動き z(t) = a R(t) e^{-iΩt}（位相 e^{-ik xf cosθ} と e^{i ky y} は外に出す）
    zt = a_stroke * R * np.exp(-1j * Om * tt)
    Zw = np.fft.fft(zt)                                  # z(t) = (1/n) Σ Z e^{+iω' t}；numpy は e^{-2πi...} の順
    # numpy: Z[m] = Σ z e^{-i ω_m t}、z = (1/n) Σ Z[m] e^{+i ω_m t}。e^{-iωt} の約束では ω = −ω_m。
    omp = -om_f
    good = (omp > 0.05) & (omp < 4.0)                    # 4 rad/s より上は立ち上げの裾で、振幅は無視できる
    kk = np.array([wavenumber(o, h) if gd else 0.0 for o, gd in zip(omp, good)])
    tfw = np.array([flap_tf(k * h) if k > 0 else 0.0 for k in kk])
    eta_t = np.zeros((len(xq), len(tq_idx)), dtype=complex)
    for a_n, t_n in zip(An, th):
        ky = k0 * math.sin(t_n)
        kx2 = kk ** 2 - ky ** 2
        prop = good & (kx2 > 0)
        kx = np.sqrt(np.where(prop, kx2, 1.0))
        G = np.where(prop, tfw * kk / kx, 0.0)
        ph0 = np.exp(-1j * k0 * xf * math.cos(t_n))    # 板の式 (19) の −k xf cosθ
        for ix, x in enumerate(xq):
            spec = Zw * G * np.exp(1j * kx * x)
            sig = np.fft.ifft(spec)                       # z と同じ並びの時間の信号
            eta_t[ix] += ph0 * sig[tq_idx] * (1.0 / math.cos(0.0))
    env = np.abs(eta_t)
    steady = float(abs(sum(A0 / math.cos(t_n) for t_n in th)))   # 焦点 (250,0) の定常の値の目安
    out = {}
    for ix, x in enumerate(xq):
        e = env[ix]
        ss = float(np.median(e[int(90 / dt):int(118 / dt)]))
        def first(frac):
            idx = np.argmax(e >= frac * ss)
            return float(tt[tq_idx][idx]) if e[idx] >= frac * ss else None
        out[str(int(x))] = {"steady_env_late": ss, "t50": first(0.5), "t90": first(0.9), "t99": first(0.99),
                           "env_at_48.3s": float(e[int(round(48.3 / dt))]),
                           "env_at_40s": float(e[int(round(40.0 / dt))]),
                           # 211 m・48.3 s に着く群の部分がこの x を通った時（群速度、θ = 0 の目安）の包絡
                           "t_pass_for_211_48.3": 48.3 - (211.0 - x) / cg if x < 211 else None,
                           "env_at_t_pass": float(e[int(round((48.3 - (211.0 - x) / cg) / dt))]) if x < 211 else None}
    # 群速度で前線を動かす近似：η ≈ Σ A_n R(t − x/(cg cosθ)) e^{i(...)}（y = 0）
    approx = np.zeros((len(xq), len(tq_idx)), dtype=complex)
    for a_n, t_n in zip(An, th):
        for ix, x in enumerate(xq):
            tdel = tt[tq_idx] - x / (cg * math.cos(t_n))
            Rt = np.where(tdel > 0, ramp(kind, np.maximum(tdel, 0)), 0.0)
            approx[ix] += a_n * Rt * np.exp(1j * (k0 * (x - xf) * math.cos(t_n) - Om * tt[tq_idx]))
    diff = {}
    for ix, x in enumerate(xq):
        ea = np.abs(approx[ix]); ee = env[ix]
        ss = out[str(int(x))]["steady_env_late"]
        diff[str(int(x))] = {"max_abs_env_diff_over_steady": float(np.max(np.abs(ea - ee)) / ss),
                             "rms_env_diff_over_steady_0_100s": float(np.sqrt(np.mean((ea[:1000] - ee[:1000]) ** 2)) / ss)}
    out["group_front_approx_vs_exact"] = diff
    trans[kind] = out
res["transient"] = trans
res["transient_note"] = ("造波板 x = 0、幅は無限、平らな底 20 m、線形。立ち上げの形は原稿に「3 周期の tanh に似た立ち上げ」とだけあり、"
                         "式は Brandini & Grilli（原稿の文献 [7]）にあると思われるが未確認。二つの形で幅を見た。")

# ---------------------------------------------------------------- 5. 跳ね返りの理論
def reflection(kx_free, rate_cells, om, dx, k_free, theta=0.0, mode="iso"):
    """Perić & Abdel-Maksoud 2018 の §3.1 を、帯に角 θ で入る波へ広げた計算。
    帯の中の cell j の強さ r_j（1/s、水平の流速を目標へ寄せる速さ）で、
      iso：水平の二つの向きをどちらも寄せる → kx_j² = k²(cos²θ + i r_j/ω)
      normal：帯に直角な向きの流速だけ寄せる → kx_j² = k² cos²θ (1 + i r_j/ω)
    帯の外側は壁（水平の変位 0）。帯の入口での |B/A| を返す。"""
    c2 = math.cos(theta) ** 2
    ks = []
    for r in rate_cells:
        if mode == "iso":
            q = k_free ** 2 * (c2 + 1j * r / om)
        else:
            q = k_free ** 2 * c2 * (1 + 1j * r / om)
        kj = np.sqrt(q + 0j)
        if kj.imag < 0:
            kj = -kj
        ks.append(kj)
    # 壁から戻る。X = A e^{ikx} + B e^{-ikx}、r = B e^{-ikx} / (A e^{ikx})。壁で X = 0 → r = −1。
    rr = -1.0 + 0j
    for j in range(len(ks) - 1, -1, -1):
        kj = ks[j]
        rr = rr * np.exp(2j * kj * dx)                    # cell の幅だけ戻る
        Yv = (1 + rr) / (1j * kj * (1 - rr))             # X / X_x は境で続く
        kprev = ks[j - 1] if j > 0 else kx_free + 0j
        rr = (1j * kprev * Yv - 1) / (1j * kprev * Yv + 1)
    return float(abs(rr))


def cells(xd, dx):
    n = max(1, int(round(xd / dx)))
    chi = (np.arange(n) + 0.5) / n                         # 0 = 帯の入口、1 = 壁
    return chi, xd / n


def rate_sponge(chi, sigma, p=2.0):
    return sigma * chi ** p


def rate_exp2(chi, gamma):
    return gamma * (np.exp(chi ** 2) - 1) / (math.e - 1)


def rate_relaxw(chi, dt_ref, cap=1e4):
    w = (np.exp(chi ** 3.5) - 1) / (math.e - 1)
    w = np.clip(w, 0, 1 - 1e-12)
    return np.minimum(-np.log(1 - w) / dt_ref, cap)


def CR(T_, h_, xd, ratefun, dx=0.5, theta_deg=0.0, mode="iso"):
    om = 2 * math.pi / T_
    k = wavenumber(om, h_)
    chi, dxx = cells(xd, dx)
    r = ratefun(chi)
    th_ = math.radians(theta_deg)
    return reflection(k * math.cos(th_), r, om, dxx, k, th_, mode)


refl = {}
# (a) 検算：Perić ら 2018 の「指数の重み (e^{χ²}−1)/(e−1)、γ = πω、帯 2λ で CR < 1 %」（深い水の T = 1.6 s、λ ≈ 4 m）
Tt = 1.6; hdeep = 50.0; omt = 2 * math.pi / Tt; lt = 2 * math.pi / wavenumber(omt, hdeep)
refl["check_peric_exp_gamma_pi_omega"] = {str(m): CR(Tt, hdeep, m * lt, lambda c: rate_exp2(c, math.pi * omt), dx=lt / 100)
                                          for m in [0.5, 1.0, 1.5, 2.0]}
# (b) 検算：FLIP37 P0（T 14 s、水深 60 m、λ 270.4 m、帯 300 m、格子 0.7 m）
T37 = 14.0; h37 = 60.0
refl["check_flip37_P0"] = {
    "lambda": 2 * math.pi / wavenumber(2 * math.pi / T37, h37),
    "relaxw_per_substep_dt_1_48": CR(T37, h37, 300.0, lambda c: rate_relaxw(c, 1 / 48), dx=0.7),
    "relaxw_per_substep_dt_1_24": CR(T37, h37, 300.0, lambda c: rate_relaxw(c, 1 / 24), dx=0.7),
    "sponge_sigma0.4_chi2": CR(T37, h37, 300.0, lambda c: rate_sponge(c, 0.4), dx=0.7),
    "measured": "relaxw：8.8〜14.7 %（時間とともに増えた）、スポンジ σmax 0.4：0.2〜3.8 %（FLIP37 P0 record §4.3）",
}
_om37 = 2 * math.pi / T37; _k37 = wavenumber(_om37, h37)
_cg37 = 0.5 * (1 + 2 * _k37 * h37 / math.sinh(2 * _k37 * h37)) * _om37 / _k37
refl["check_flip37_P0"]["cg"] = _cg37
refl["check_flip37_P0"]["t_wall_return_to_690m_from_700m_at_t0"] = (1000 - 700) / _cg37 + (1000 - 690) / _cg37
refl["check_flip37_P0"]["t_wall_return_to_545m"] = (1000 - 700) / _cg37 + (1000 - 545) / _cg37
refl["check_flip37_P0"]["measured_windows_end_s"] = 40.0
# (c) 本題：T 7 s、水深 20 m
T7 = 2 * math.pi / Om
om7 = Om
plan = {}
for xd in [36.0, 54.0, 72.0, 108.0, 144.0]:
    row = {}
    row["sponge_sigma0.8_chi2(FLIP44)"] = {str(a): CR(T7, h, xd, lambda c: rate_sponge(c, 0.8), theta_deg=a) for a in [0, 30, 45, 60]}
    row["exp2_gamma_pi_omega"] = {str(a): CR(T7, h, xd, lambda c: rate_exp2(c, math.pi * om7), theta_deg=a) for a in [0, 30, 45, 60]}
    row["relaxw_dt0_1_24(FLIP42 band)"] = {str(a): CR(T7, h, xd, lambda c: rate_relaxw(c, 1 / 24), theta_deg=a) for a in [0, 30, 45, 60]}
    row["relaxw_dt0_1_24_normal_only"] = {str(a): CR(T7, h, xd, lambda c: rate_relaxw(c, 1 / 24), theta_deg=a, mode="normal") for a in [0, 30, 45, 60]}
    # 二乗の重みで σ を振って最小を探す（直角に入る波）
    best = None
    for s in np.geomspace(0.05, 50, 121):
        v = CR(T7, h, xd, lambda c: rate_sponge(c, s))
        if best is None or v < best[1]:
            best = (float(s), v)
    row["sponge_chi2_best_sigma_normal"] = {"sigma": best[0], "CR": best[1],
                                            "CR_at_30_45_60": {str(a): CR(T7, h, xd, lambda c: rate_sponge(c, best[0]), theta_deg=a) for a in [30, 45, 60]}}
    best3 = None
    for s in np.geomspace(0.05, 50, 121):
        v = CR(T7, h, xd, lambda c: rate_sponge(c, s, p=3.0))
        if best3 is None or v < best3[1]:
            best3 = (float(s), v)
    row["sponge_chi3_best_sigma_normal"] = {"sigma": best3[0], "CR": best3[1]}
    plan["xd_%dm(%.2flambda)" % (xd, xd / lam)] = row
refl["T7_h20"] = plan
# 2 倍の周波数（束縛の波は別、自由な 2 倍の波として）と長い波
refl["other_periods_for_xd72_sponge_best"] = {}
s72 = plan["xd_72m(1.00lambda)"]["sponge_chi2_best_sigma_normal"]["sigma"] if "xd_72m(1.00lambda)" in plan else None
for Tx in [3.5, 7.0, 14.0, 30.0]:
    refl["other_periods_for_xd72_sponge_best"][str(Tx)] = {
        "lambda": 2 * math.pi / wavenumber(2 * math.pi / Tx, h),
        "CR_sigma_best7s": CR(Tx, h, 72.0, lambda c: rate_sponge(c, s72)) if s72 else None,
        "CR_sigma0.8": CR(Tx, h, 72.0, lambda c: rate_sponge(c, 0.8)),
    }
res["reflection"] = refl
res["reflection_note"] = ("Perić & Abdel-Maksoud 2018 の 1 次元の理論（線形、一定の重みの cell を並べ、外側は壁）。斜めに入る波への広げ方は"
                          "この計算で足した物で、著者は 3D・斜めを確かめていない（同論文の結び）。")

# ---------------------------------------------------------------- 6. 窓の案の費用（FLIP42 R3 の記録の係数）
per_m2_h42_dp025 = 4690.0        # R3：平面 1 m² あたりの粒子（水深 42 m、粒子 0.25 m）
s_frame_pre, s_frame_break = 3.0, 7.5
n_r3 = 11.27e6
mem0, mem_per_M = 5.3, 0.12
bytes_ckpt = 55.0


def cost(name, Lx, Ly, dp, depth=20.0, frames=960, air=14.0):
    n = per_m2_h42_dp025 * (depth / 42.0) * (0.25 / dp) ** 3 * Lx * Ly
    vox = 2 * dp
    cells = (Lx / vox) * (Ly / vox) * ((depth + air + 2) / vox)
    tlo = frames * s_frame_pre * n / n_r3 / 3600
    thi = frames * s_frame_break * n / n_r3 / 3600 * 1.5
    return {"name": name, "Lx": Lx, "Ly": Ly, "dp": dp, "frames": frames, "particles_M": n / 1e6, "grid_cells_M": cells / 1e6,
            "mem_GB": mem0 + mem_per_M * n / 1e6, "hours_lo": tlo, "hours_hi": thi, "ckpt_GB": n * bytes_ckpt / 1e9}


res["cost"] = [
    cost("A 調べの案（x 130〜340、y 0〜108、帯 36 m）", 210, 108, 0.25),
    cost("A 粗い下見", 210, 108, 0.5),
    cost("A 細かさの確かめ", 210, 108, 181 / 1024),
    cost("B 帯 72 m（x 94〜376、y 0〜144）", 282, 144, 0.25),
    cost("B 粗い下見", 282, 144, 0.5),
    cost("C 横を広く壁に（x 130〜376、y 0〜300、横の帯なし）粗い", 246, 300, 0.5),
    cost("C 同 0.25 m", 246, 300, 0.25),
    cost("E 入口を 36〜72 m に（x 36〜340、y 0〜108、帯 36 m）50 s", 304, 108, 0.25, frames=1200),
    cost("E 粗い下見", 304, 108, 0.5, frames=1200),
    cost("D0 造波板から（x 0〜340、y 0〜108、帯 36 m）60 s", 340, 108, 0.25, frames=1440),
    cost("D0 粗い下見", 340, 108, 0.5, frames=1440),
    cost("D1 造波板から（x 0〜376、y 0〜144、帯 72 m）60 s", 376, 144, 0.25, frames=1440),
    cost("D1 粗い下見", 376, 144, 0.5, frames=1440),
    cost("D1 繰り返しを 10 周期見る（130 s）", 376, 144, 0.25, frames=3120),
    cost("D2 造波板から（x 0〜412、y 0〜180、帯 108 m）60 s", 412, 180, 0.25, frames=1440),
    cost("D2 粗い下見", 412, 180, 0.5, frames=1440),
]
# 30 分の起動の中で進めるコマの数（途中保存の間隔の上限の目安）と、全部の途中保存の大きさ
for c in res["cost"]:
    f_lo = c["hours_lo"] * 3600 / c.get("frames", 960) if "frames" in c else None
    n = c["particles_M"] * 1e6
    s_pre = s_frame_pre * n / n_r3
    s_brk = s_frame_break * n / n_r3 * 1.5
    c["s_per_frame_pre"] = s_pre
    c["s_per_frame_break_hi"] = s_brk
    c["frames_per_30min_pre"] = 1800 / s_pre
    c["frames_per_30min_break"] = 1800 / s_brk
res["cost_note"] = "粒子・時間は R3（1,127 万粒子、1 コマ 3.0〜7.5 秒）に比例させ上を 1.5 倍、メモリーは 5.3 GB＋100 万粒子あたり 0.12 GB、途中保存は 1 粒子 55 バイト。物理の時間 40 s（960 コマ）。"

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("wrote", OUT)
