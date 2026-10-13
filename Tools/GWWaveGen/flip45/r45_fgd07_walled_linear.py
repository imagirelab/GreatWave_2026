# -*- coding: utf-8 -*-
"""Fochesato・Grilli・Dias 2007（Wave Motion 44, 395-416）の水槽の線形の場：横の壁あり（幅 600 m）と、幅が無限の場合を比べる。
調べの記録：Unity/Build/FLIP45/research/fochesato_ja.md（§4）
py -3.10 -I r45_fgd07_walled_linear.py で走らせる（numpy だけ。Houdini は使わない。1 分ほど。優先度を下げて走る）。
出力：Unity/Build/FLIP45/research/fochesato_linear.json

置いた物（刊行版 §3.2・§3.3 の式 (17)〜(21) と数）：
  水深 d 20 m、Ω 0.8971 rad/s、成分 30（θn は −45〜45° に端を含む等間隔）、板の振幅 a 0.2 m（全部同じ）、
  焦点 xf 250 m、板は x = 0 で底で回る（flap）、横の壁は y = ±300 m（水を通さない）。
  板の振れ S(y,t) = R(t) Σ a cos(k(y sinθn − xf cosθn) − Ωt)（式 (19)）。R(t) は 3 周期の tanh に似た立ち上げ。
    刊行版は形を書かない。Brandini & Grilli 2001（ISOPE、式 (24) の後）は「板の振れに tanh の関数を掛けて、決めた時間で 0 から最大へ上げる」とだけ書く。
    ここでは 2 つの形で幅を見る：tanh_a = tanh(t/T)、tanh_s = 0.5(1 + tanh(2t/T − 3))（r45_gen_numbers.py と同じ 2 つ）。
解き方（線形、平らな底）：
  横の壁があると、水の動きは横の余弦の形 cos(qj y)、qj = jπ/300 m に分かれる（壁で ∂/∂y = 0）。
  板の振れを cos(qj y) に分け、各 j の時間の信号を周波数に分けて、各周波数で
    η = F(kd) · k/kx · (板の振れ) を 90° ずらして運ぶ（kx = √(k² − qj²)。F は板の式、Dean & Dalrymple。刊行版の式 (21) の 1/cosθ は k/kx と同じ）。
  時間の窓の折り返しを消すため、信号に e^{−σt} を掛けて変換し（s = σ + iω のラプラス変換）、伝達を ω − iσ（numpy の e^{+iωt} の向き）で求め、
  最後に e^{σt} を掛ける（σ = 10/窓の長さ）。
  幅が無限の場合は、板の 30 成分の横の波数 pn = k sinθn をそのまま形にする（壁なし）。
入っていない物：非線形（2 次の束縛波を含む）、遠い端の吸う板（x 440 m。48 s までに前線は届かない）、板の近くの縦の消える波（x 100 m より先では小さい）。
"""
import json, math, os, sys, time
import numpy as np

# 優先度を下げる（Windows の BELOW_NORMAL_PRIORITY_CLASS）
try:
    import ctypes
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
except Exception:
    pass

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/research/fochesato_linear.json"
g = 9.81
d = 20.0
Om = 0.8971
T = 2 * math.pi / Om
a = 0.2
N = 30
thmax = 45.0
xf = 250.0
Lh = 300.0          # 壁までの半分の幅


def k_real(om):
    k = om * om / g
    for _ in range(60):
        f = g * k * math.tanh(k * d) - om * om
        df = g * math.tanh(k * d) + g * k * d / math.cosh(k * d) ** 2
        k -= f / df
    return k


def k_complex(om):
    """ω（複素の配列）に対して ω² = g k tanh(kd) を複素の Newton で解く。"""
    om = np.asarray(om, dtype=complex)
    k = np.array([k_real(abs(w.real)) if abs(w.real) > 1e-6 else 1e-6 for w in om], dtype=complex)
    k = np.where(np.abs(k) < 1e-6, 1e-6, k)
    for _ in range(40):
        th = np.tanh(k * d)
        f = g * k * th - om * om
        df = g * th + g * k * d * (1 - th * th)
        k = k - f / df
    return k


def flap_F(k):
    kd = k * d
    return 4 * np.sinh(kd) * (1 - np.cosh(kd) + kd * np.sinh(kd)) / (kd * (np.sinh(2 * kd) + 2 * kd))


k0 = k_real(Om)
F0 = float(flap_F(k0))
A0 = a * F0
th = np.radians(np.linspace(-thmax, thmax, N))
pn = k0 * np.sin(th)
psi = -k0 * xf * np.cos(th)
res = {"inputs": {"d": d, "Omega": Om, "T": T, "a": a, "N": N, "theta_max_deg": thmax, "xf": xf, "half_width_wall": Lh,
                  "k": k0, "lambda": 2 * math.pi / k0, "F_flap": F0, "A0_theta0": A0,
                  "A_star_ideal_sum_A0_over_cos": float((A0 / np.cos(th)).sum())}}

# ---------------------------------------------------------------- 横の形
J = 60
qj = np.arange(J + 1) * math.pi / Lh


def proj(p):
    """cos(p y) を [−Lh, Lh] の cos(qj y) に分けた係数（j = 0..J）。"""
    I = Lh * (np.sinc((p - qj) * Lh / math.pi) + np.sinc((p + qj) * Lh / math.pi))   # ∫ cos(py) cos(qy) dy
    c = I / Lh
    c[0] = I[0] / (2 * Lh)
    return c


C = np.array([proj(p) for p in pn])          # (N, J+1)
# 壁あり：形 j の板の信号 = R(t) [Pj cos Ωt + Qj sin Ωt]
Pw = (a * C * np.cos(psi)[:, None]).sum(axis=0)
Qw = (a * C * np.sin(psi)[:, None]).sum(axis=0)
# 壁なし：形 n（横の波数 pn）の板の信号 = R(t) a [cos ψn cos Ωt + sin ψn sin Ωt]
Pi = a * np.cos(psi)
Qi = a * np.sin(psi)

# 板の振れの分け方の確かめ：y = 0 と y = 200 m で、元の式と形の和
ycheck = {}
for yv in [0.0, 100.0, 200.0, 290.0]:
    t0 = 0.37 * T
    s_orig = float((a * np.cos(pn * yv + psi - Om * t0)).sum())
    s_modes = float((np.cos(qj * yv) * (Pw * math.cos(Om * t0) + Qw * math.sin(Om * t0))).sum())
    ycheck[str(yv)] = {"stroke_formula": s_orig, "stroke_modes": s_modes}
res["mode_check_stroke_at_t_0p37T"] = ycheck


# ---------------------------------------------------------------- 定常（ω = Ω）の複素の振幅
def steady_amp(P, Q, qs, x, y):
    k = k0
    kx = np.sqrt(k * k - qs * qs + 0j)
    kxc = np.conj(kx)
    # 板の信号 Re[(P − iQ) e^{iΩt}]、η = Re[(P − iQ) · i F k/kx* · e^{−i kx* x} e^{iΩt}] cos(q y)
    Z = np.zeros(np.broadcast(x, y).shape, dtype=complex)
    for P1, Q1, q1, kx1 in zip(P, Q, qs, kxc):
        if abs(kx1) < 1e-9:
            continue
        Z = Z + (P1 - 1j * Q1) * 1j * F0 * (k / kx1) * np.exp(-1j * kx1 * x) * np.cos(q1 * y)
    return Z


xs = np.arange(100.0, 350.01, 1.0)
Zw0 = steady_amp(Pw, Qw, qj, xs, 0.0)
Zi0 = steady_amp(Pi, Qi, pn, xs, 0.0)
iw = int(np.argmax(np.abs(Zw0)))
ii = int(np.argmax(np.abs(Zi0)))
res["steady"] = {
    "walled_amp_at_xf_y0": float(abs(Zw0[xs == xf][0])),
    "ideal_amp_at_xf_y0": float(abs(Zi0[xs == xf][0])),
    "walled_max_amp_y0": float(abs(Zw0[iw])), "walled_x_of_max": float(xs[iw]),
    "ideal_max_amp_y0": float(abs(Zi0[ii])), "ideal_x_of_max": float(xs[ii]),
    "walled_amp_y0_every10m": {str(int(x)): round(float(abs(z)), 3) for x, z in zip(xs, Zw0) if int(x) % 10 == 0},
    "ideal_amp_y0_every10m": {str(int(x)): round(float(abs(z)), 3) for x, z in zip(xs, Zi0) if int(x) % 10 == 0},
}
# 造波板から窓の入口までの定常の振幅（y = 0 と、各 x での y 0〜300 m の最大）
xs_up = np.arange(10.0, 350.01, 10.0)
Zw_up = np.abs(steady_amp(Pw, Qw, qj, xs_up, 0.0))
Zi_up = np.abs(steady_amp(Pi, Qi, pn, xs_up, 0.0))
Xu, Yu = np.meshgrid(xs_up, np.arange(0.0, 300.01, 2.0), indexing="ij")
Zw_upmax = np.abs(steady_amp(Pw, Qw, qj, Xu, Yu)).max(axis=1)
res["steady_upstream"] = {str(int(x)): {"walled_y0": round(float(a1), 2), "ideal_y0": round(float(b1), 2),
                                        "walled_max_over_y0_300": round(float(c1), 2)}
                          for x, a1, b1, c1 in zip(xs_up, Zw_up, Zi_up, Zw_upmax)}
# 検算 3：壁を遠く（半分の幅 3000 m、形 600 個）に置くと、幅が無限の場合に近づくはず
Lh_far = 3000.0
q_far = np.arange(601) * math.pi / Lh_far


def proj_far(p):
    I = Lh_far * (np.sinc((p - q_far) * Lh_far / math.pi) + np.sinc((p + q_far) * Lh_far / math.pi))
    c = I / Lh_far
    c[0] = I[0] / (2 * Lh_far)
    return c


C_far = np.array([proj_far(p) for p in pn])
P_far = (a * C_far * np.cos(psi)[:, None]).sum(axis=0)
Q_far = (a * C_far * np.sin(psi)[:, None]).sum(axis=0)
Z_far = np.abs(steady_amp(P_far, Q_far, q_far, np.array([150.0, 212.0, 250.0, 300.0]), 0.0))
res["check_far_walls"] = {"x": [150, 212, 250, 300], "walls_at_3000m": [round(float(v), 3) for v in Z_far],
                          "ideal": [round(float(abs(steady_amp(Pi, Qi, pn, np.array([xv]), 0.0)[0])), 3) for xv in [150.0, 212.0, 250.0, 300.0]],
                          "note": "壁が遠いと幅が無限の値に近づけば、形に分ける解き方は正しい。板は y ±3000 m まで続く（板の幅も広がる）ので完全には一致しない"}
# 窓の帯の上の定常の振幅（入口の帯 x 130〜166 m の y 0〜108、横の帯 y 72〜108 の x 130〜340）
Xg, Yg = np.meshgrid(np.arange(130.0, 340.01, 2.0), np.arange(0.0, 108.01, 2.0), indexing="ij")
Zw2 = np.abs(steady_amp(Pw, Qw, qj, Xg, Yg))
Zi2 = np.abs(steady_amp(Pi, Qi, pn, Xg, Yg))


def stats(Z, m):
    v = Z[m]
    return {"min": round(float(v.min()), 3), "mean": round(float(v.mean()), 3), "max": round(float(v.max()), 3)}


m_in = (Xg <= 166)
m_side = (Yg >= 72)
res["steady_bands"] = {
    "inlet_band_x130_166": {"walled": stats(Zw2, m_in), "ideal": stats(Zi2, m_in)},
    "side_band_y72_108": {"walled": stats(Zw2, m_side), "ideal": stats(Zi2, m_side)},
    "whole_window": {"walled": stats(Zw2, Xg >= 0), "ideal": stats(Zi2, Xg >= 0)},
    "rel_diff_walled_vs_ideal_whole_window_max": round(float(np.max(np.abs(Zw2 - Zi2)) / np.max(Zi2)), 3),
}

# ---------------------------------------------------------------- 過渡（3 周期の立ち上げ）
dt = 0.1
NT = 2 ** 15
Tw = NT * dt
sig = 10.0 / Tw
tt = np.arange(NT) * dt
om_b = 2 * math.pi * np.fft.rfftfreq(NT, dt)
use = (om_b >= 0.05) & (om_b <= 3.0)
omc = om_b[use] - 1j * sig
kc = k_complex(omc)
Fc = flap_F(kc)
t_keep = tt <= 100.0 + 1e-9
x_eval = np.arange(100.0, 350.01, 1.0)


def ramp(kind, t):
    if kind == "tanh_a":
        return np.tanh(t / T)
    if kind == "tanh_s":
        return 0.5 * (1 + np.tanh(2 * t / T - 3))
    raise ValueError(kind)


def transient(P, Q, qs, kind):
    """形ごとに η_j(x, t) を返す（y = 0 での値。横は cos(q y) を掛けて足す）。"""
    R = ramp(kind, tt)
    damp = np.exp(-sig * tt)
    keep_e = np.exp(sig * tt[t_keep])
    out = np.zeros((len(qs), len(x_eval), int(t_keep.sum())))
    base_c = R * np.cos(Om * tt) * damp
    base_s = R * np.sin(Om * tt) * damp
    Sc = np.fft.rfft(base_c)
    Ss = np.fft.rfft(base_s)
    for j, (P1, Q1, q1) in enumerate(zip(P, Q, qs)):
        if abs(P1) + abs(Q1) < 1e-12:
            continue
        X = P1 * Sc + Q1 * Ss
        # numpy の向き e^{+iωt}。e^{−σt} を掛けた信号の変換は s = σ + iω のラプラス変換なので、伝達は ω̃ = ω − iσ で求める。
        # 外へ出る波は e^{i(ω̃t − kx x)}。kx は虚部が負の根（x → ∞ で有界。伝わる形も消える形も同じ枝）。
        kx = np.sqrt(kc * kc - q1 * q1)
        kx = np.where(kx.imag > 0, -kx, kx)
        Hn = 1j * Fc * kc / kx      # 板の振れ → 水面：η = i F (k/kx) X e^{−i kx x}（水面は板の速さと同じ位相）
        ph = np.exp(-1j * np.outer(x_eval, kx))   # (nx, nω)
        spec = np.zeros((len(x_eval), len(om_b)), dtype=complex)
        spec[:, use] = X[use][None, :] * Hn[None, :] * ph
        eta = np.fft.irfft(spec, n=NT, axis=1)[:, t_keep] * keep_e[None, :]
        out[j] = eta
    return out


def summarize(eta_modes, qs, label):
    eta0 = eta_modes.sum(axis=0)          # y = 0
    tk = tt[t_keep]
    s = {}
    for xv in [130.0, 166.0, 200.0, 211.0, 230.0, 250.0, 270.0, 300.0]:
        ix = int(np.argmin(np.abs(x_eval - xv)))
        ser = eta0[ix]
        s[str(int(xv))] = {
            "max_eta_t_le_48p2": round(float(ser[tk <= 48.2].max()), 3),
            "t_of_that_max": round(float(tk[tk <= 48.2][np.argmax(ser[tk <= 48.2])]), 2),
            "max_eta_t_le_70": round(float(ser[tk <= 70].max()), 3),
            "t_of_max_le_70": round(float(tk[tk <= 70][np.argmax(ser[tk <= 70])]), 2),
            "crest_times_and_heights_30_70s": [(round(float(tk[i]), 2), round(float(ser[i]), 2))
                                               for i in range(1, len(ser) - 1)
                                               if 30 <= tk[i] <= 70 and ser[i] > ser[i - 1] and ser[i] >= ser[i + 1] and ser[i] > 0.3],
            "trough_times_and_depths_30_70s": [(round(float(tk[i]), 2), round(float(ser[i]), 2))
                                               for i in range(1, len(ser) - 1)
                                               if 30 <= tk[i] <= 70 and ser[i] < ser[i - 1] and ser[i] <= ser[i + 1] and ser[i] < -0.3],
            "eta_at_48p2": round(float(ser[int(np.argmin(np.abs(tk - 48.2)))]), 2),
        }
    # 各時刻の y = 0 の最大の頂と、その場所
    env = []
    for tv in np.arange(30.0, 70.01, 1.0):
        it = int(np.argmin(np.abs(tk - tv)))
        ix = int(np.argmax(eta0[:, it]))
        env.append((round(float(tv), 1), round(float(eta0[ix, it]), 2), round(float(x_eval[ix]), 0)))
    s["largest_crest_on_y0_by_time"] = env
    it48 = int(np.argmin(np.abs(tk - 48.2)))
    s["profile_y0_t48p2_every5m"] = [(float(x_eval[i]), round(float(eta0[i, it48]), 2)) for i in range(0, len(x_eval), 5)]
    # 窓の入口（x 130 m、y 0〜108 m）の最大の振れ（t ≤ 60 s）
    ix130 = int(np.argmin(np.abs(x_eval - 130.0)))
    ys = np.arange(0.0, 108.01, 6.0)
    m = []
    for yv in ys:
        ser = (eta_modes[:, ix130, :] * np.cos(qs * yv)[:, None]).sum(axis=0)
        m.append((float(yv), round(float(np.abs(ser[tk <= 60]).max()), 3)))
    s["x130_max_abs_eta_t_le_60_by_y"] = m
    return s


t0 = time.time()
# 検算 1：2D（横の形 q = 0 だけ、板 a cos Ωt）。遅い時刻の振幅は a F、前線は群速度で進む。
chk = transient(np.array([a]), np.array([0.0]), np.array([0.0]), "tanh_a")[0]
tk = tt[t_keep]
ix200 = int(np.argmin(np.abs(x_eval - 200.0)))
cg0 = (Om / k0) * 0.5 * (1 + 2 * k0 * d / math.sinh(2 * k0 * d))
ser = chk[ix200]
half_t = float(tk[np.argmax(np.abs(ser) > 0.5 * a * F0)])
res["check_2d"] = {"late_amp_x200_t80_100": round(float(np.abs(ser[tk >= 80]).max()), 4), "expected_aF": round(a * F0, 4),
                   "t_first_half_amp_x200": half_t, "x_over_cg": round(200.0 / cg0, 2),
                   "note": "立ち上げ tanh(t/T) の半ばは t ≈ 0.55 T（3.8 s）なので、前線の半分の高さは x/cg + 約 4 s に来るはず"}
# 検算 2：幅が無限の場合、遅い時刻の焦点の振幅は定常の和に近づく
ei_chk = transient(Pi, Qi, pn, "tanh_a").sum(axis=0)
ix250 = int(np.argmin(np.abs(x_eval - 250.0)))
res["check_ideal_late"] = {"max_abs_eta_x250_t85_100": round(float(np.abs(ei_chk[ix250][tk >= 85]).max()), 3),
                           "steady_ideal_amp_x250": res["steady"]["ideal_amp_at_xf_y0"]}
trans = {}
for kind in ["tanh_a", "tanh_s"]:
    ew = transient(Pw, Qw, qj, kind)
    ei = transient(Pi, Qi, pn, kind)
    trans[kind] = {"walled": summarize(ew, qj, "walled"), "ideal": summarize(ei, pn, "ideal")}
res["transient"] = trans
res["runtime_s"] = round(time.time() - t0, 1)
res["sigma"] = sig
res["window_s"] = Tw

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(res, f, ensure_ascii=False, indent=1)
print("wrote", OUT, "runtime", res["runtime_s"], "s")
print(json.dumps({"steady": {k: v for k, v in res["steady"].items() if not k.endswith("every10m")},
                  "bands": res["steady_bands"]}, indent=1))
