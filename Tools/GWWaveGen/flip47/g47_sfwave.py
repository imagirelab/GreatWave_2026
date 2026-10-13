# -*- coding: utf-8 -*-
"""FLIP47：周期の波の流れ関数の解（Fourier の流れ関数法。Rienecker & Fenton 1981、Fenton 1988）。py -3.10、numpy・scipy だけ。
2026-10-13 周期の波の設計の役（Claude）が新しく書いた。ほかの道具は変えていない。

何をするか：平らな海底（水深 h）の上を形を変えずに進む周期 T・波高 H の波（重力だけ・水だけの Euler の式の厳密な解。
  数の誤差は項の数 N で決まる）を解く。閉じた水路（2D の板の水槽）に合わせ、平均の質量の流れを 0 にする（Fenton の 2 つ目の流れの決まり
  ū2 = 0。波の Stokes の流れを戻りの流れが打ち消す）。
座標（計画の座標と同じ向き）：x＝進む向き、y＝上（平均の水面 0、海底 −h）。波と一緒に動く座標 X = x − c t。
  ψ(X, Y) = −Ū Y + Σ_j B_j sinh(j k Y)/cosh(j k h) cos(j k X)（Y = y + h は海底から）
  止まった座標の流速：u = c − Ū + Σ j k B_j cosh(j k Y)/cosh(j k h) cos(j k X)、w = Σ j k B_j sinh(j k Y)/cosh(j k h) sin(j k X)
  水面：η(X) = Σ_{j=0}^{N} E_j cos(j k X)（頂は X = 0）
  Euler の平均の流れ（谷より下の 1 点の時間平均）ū1 = c − Ū（閉じた水路では負：戻りの流れ）。
使い方（道具として）：
  s = solve(h, T, H)             → dict（k, L, c, Ubar, Q, R, B, E, eta_nodes, ...）
  eta(s, x, t)、vel(s, x, y, t)、energy_flux(s)、mass_flux(s)、profile_measures(s)
  highest_H(h, T)                 Fenton 1990 の最も高い波の当てはめ（Williams 1981 の値）
"""
import math
import numpy as np
from scipy.optimize import root, brentq

G = 9.80665


# ------------------------------------------------------------------ 線形の分散
def k_lin(T, h, g=G):
    om = 2 * math.pi / T
    k = max(om * om / g, om / math.sqrt(g * h))
    for _ in range(200):
        th = math.tanh(k * h)
        F = g * k * th - om * om
        dF = g * th + g * k * h * (1 - th * th)
        dk = F / dF
        k -= dk
        if abs(dk) < 1e-15 * k:
            break
    return k


def k_lin_f(f, h, g=G):
    f = np.atleast_1d(np.asarray(f, float))
    return np.array([k_lin(1.0 / v, h, g) for v in f])


def cg_lin(T, h, g=G):
    k = k_lin(T, h, g)
    kh = k * h
    return (2 * math.pi / T) / k * 0.5 * (1 + 2 * kh / math.sinh(2 * kh))


def highest_H(h, T, g=G):
    """Fenton (1990) の最も高い波の当てはめ H/h(L/h)。L は最も高い波の波長が要るが、ここでは線形の波長で引く（目安）。
    L/h → ∞ で 0.833（孤立波）、L/h → 0 で H/L 0.141（深い水）。"""
    L = 2 * math.pi / k_lin(T, h, g)
    r = L / h
    return h * (0.141063 * r + 0.0095721 * r ** 2 + 0.0077829 * r ** 3) / (1 + 0.0788340 * r + 0.0317567 * r ** 2 + 0.0093407 * r ** 3)


# ------------------------------------------------------------------ 双曲線の比（桁あふれを避ける）
def _sh_over_ch(a, b):
    """sinh(a)/cosh(b)（a, b ≥ 0 の配列）。"""
    return (np.exp(a - b) - np.exp(-a - b)) / (1 + np.exp(-2 * b))


def _ch_over_ch(a, b):
    return (np.exp(a - b) + np.exp(-a - b)) / (1 + np.exp(-2 * b))


# ------------------------------------------------------------------ 解く
def _scales(h, g, N, M):
    """未知数と式の大きさの物差し（h と √(g h) で無次元にして解く）。"""
    c0 = math.sqrt(g * h)
    zs = np.concatenate([np.full(M + 1, h), np.full(N, c0 * h), [1.0 / h, c0, c0 * h, g * h]])
    rs = np.concatenate([np.full(M + 1, c0 * h), np.full(M + 1, g * h), [h, h, c0]])
    return zs, rs


def _residual(z, h, T, H, N, M, g):
    e = z[:M + 1]; B = z[M + 1:M + 1 + N]; k, Ub, Q, R = z[M + 1 + N:]
    j = np.arange(1, N + 1)[:, None]; m = np.arange(M + 1)[None, :]
    Y = h + e[None, :]
    cs = np.cos(j * m * math.pi / M); sn = np.sin(j * m * math.pi / M)
    with np.errstate(over="ignore", invalid="ignore"):
        SH = _sh_over_ch(j * k * Y, j * k * h); CH = _ch_over_ch(j * k * Y, j * k * h)
        psi = -Ub * (h + e) + (B[:, None] * SH * cs).sum(0)
        U = -Ub + (j * k * B[:, None] * CH * cs).sum(0)
        V = (j * k * B[:, None] * SH * sn).sum(0)
    r1 = psi + Q
    r2 = 0.5 * (U * U + V * V) + g * e - R
    w = np.ones(M + 1); w[0] = w[-1] = 0.5
    r3 = (w * e).sum() / M
    r4 = e[0] - e[-1] - H
    c = 2 * math.pi / (k * T)
    r5 = c - Q / h                         # ū2 = 0（閉じた水路）
    out = np.concatenate([r1, r2, [r3, r4, r5]])
    return np.where(np.isfinite(out), out, 1e6)


def _residual_nd(zn, h, T, H, N, M, g, zs, rs):
    return _residual(zn * zs, h, T, H, N, M, g) / rs


def _newton(fun, z0, args, tol=1e-12, maxit=60):
    """Newton（差分の Jacobian、最小二乗で解く、段の長さを半分ずつ縮める）。返り値 (z, 残りの最大, 回数)。"""
    z = np.array(z0, float)
    r = fun(z, *args); nr = float(np.abs(r).max())
    for it in range(maxit):
        if nr < tol:
            return z, nr, it
        n = len(z); J = np.empty((len(r), n))
        for i in range(n):
            d = 1e-7 * max(1.0, abs(z[i]))
            zp = z.copy(); zp[i] += d; zm = z.copy(); zm[i] -= d
            J[:, i] = (fun(zp, *args) - fun(zm, *args)) / (2 * d)
        dz = np.linalg.lstsq(J, -r, rcond=None)[0]
        lam = 1.0
        while lam > 1e-4:
            zn = z + lam * dz
            rn = fun(zn, *args); nrn = float(np.abs(rn).max())
            if np.isfinite(nrn) and nrn < nr:
                break
            lam *= 0.5
        else:
            return z, nr, it
        z, r, nr = zn, rn, nrn
    return z, nr, maxit


def _guess(h, T, H, N, M, g):
    k = k_lin(T, h, g); c = 2 * math.pi / (k * T); a = 0.5 * H
    m = np.arange(M + 1)
    e = a * np.cos(m * math.pi / M)
    B = np.zeros(N); B[0] = c * a / math.tanh(k * h)
    return np.concatenate([e, B, [k, c, c * h, 0.5 * c * c]])


def _rescale(z, Nold, Mold, N, M, h):
    """項の数を変えて解き直す時の初めの値（水面は余弦の級数で補う、B は 0 を足す）。"""
    e = z[:Mold + 1]; B = z[Mold + 1:Mold + 1 + Nold]; rest = z[Mold + 1 + Nold:]
    Ej = _cos_coeffs(e, Mold)
    X = np.arange(M + 1) * math.pi / M
    e2 = (Ej[:, None] * np.cos(np.arange(len(Ej))[:, None] * X[None, :])).sum(0)
    B2 = np.zeros(N); B2[:min(N, Nold)] = B[:min(N, Nold)]
    return np.concatenate([e2, B2, rest])


def _cos_coeffs(e, M):
    """節 kX = mπ/M の値から余弦の係数 E_j（j = 0..M）。DCT-I。"""
    w = np.ones(M + 1); w[0] = w[-1] = 0.5
    j = np.arange(M + 1)[:, None]; m = np.arange(M + 1)[None, :]
    E = (2.0 / M) * (w[None, :] * e[None, :] * np.cos(j * m * math.pi / M)).sum(1)
    E[0] *= 0.5; E[-1] *= 0.5
    return E


def solve(h, T, H, N=None, steps=None, g=G, tol=1e-11, init=None):
    """水深 h・周期 T・波高 H の流れ関数の解。高さを steps 段で上げて解く（Fenton 1988 と同じ考え）。
    init に近い解（同じ T の dict）を渡すと、その解から 1 段で解く（水深や高さを少しずつ変える時に速い）。失敗したら段で解き直す。"""
    Hmax = highest_H(h, T, g)
    if H >= 0.995 * Hmax:
        raise ValueError("H %.3f m は最も高い波（目安 %.3f m）を越える" % (H, Hmax))
    if N is None:
        N = int(init["N"]) if init is not None else int(min(48, max(16, round(12 + 40 * (H / Hmax) ** 2))))
    M = N
    zs, rs = _scales(h, g, N, M)
    ok = True; msg = ""
    z = None
    if init is not None and int(init["N"]) == N:
        rH = H / init["H"]
        zi = np.concatenate([np.asarray(init["eta_nodes"]) * rH, np.asarray(init["B"]) * rH,
                             [init["k"] * init["h"] / h, init["Ubar"], init["Q"] * h / init["h"], init["R"]]])
        zt, res, _ = _newton(_residual_nd, zi / zs, (h, T, H, N, M, g, zs, rs))
        if res <= 1e-9:
            z = zt
    if z is None:
        if steps is None:
            steps = int(max(3, math.ceil(12 * H / Hmax)))
        z = _guess(h, T, H / steps, N, M, g) / zs
        sols = []                                # 前の段の解（2 つあれば直線で外挿して次の初めの値にする）。無次元
        for i in range(1, steps + 1):
            Hi = H * i / steps
            z0 = (2 * sols[-1] - sols[-2]) if len(sols) >= 2 else (sols[-1] if sols else z)
            a_ = (h, T, Hi, N, M, g, zs, rs)
            z, res, _ = _newton(_residual_nd, z0, a_)
            sols.append(z.copy())
            if res > 1e-9:
                ok = False; msg = "step %d/%d residual %.3g（無次元）" % (i, steps, res)
                break
    z = z * zs
    e = z[:M + 1]; B = z[M + 1:M + 1 + N]; k, Ub, Q, R = z[M + 1 + N:]
    E = _cos_coeffs(e, M)
    c = 2 * math.pi / (k * T)
    s = dict(h=float(h), T=float(T), H=float(H), N=int(N), M=int(M), g=float(g), k=float(k), L=float(2 * math.pi / k), c=float(c),
             Ubar=float(Ub), Q=float(Q), R=float(R), u1=float(c - Ub), u2=float(c - Q / h), B=B.copy(), E=E.copy(), eta_nodes=e.copy(),
             eta_crest=float(e[0]), eta_trough=float(e[-1]), ok=bool(ok), msg=msg, Hmax_fit=float(Hmax),
             residual_max=float(np.abs(_residual(z, h, T, H, N, M, g)).max()), c_lin=float(2 * math.pi / (k_lin(T, h, g) * T)))
    s["ursell"] = float(H * s["L"] ** 2 / h ** 3)
    return s


# ------------------------------------------------------------------ 場
def eta(s, x, t=0.0):
    X = np.asarray(x, float) - s["c"] * np.asarray(t, float)
    j = np.arange(len(s["E"]))
    return (s["E"][:, None] * np.cos(j[:, None] * s["k"] * np.atleast_1d(X)[None, :])).sum(0)


def vel(s, x, y, t=0.0):
    """止まった座標の流速 (u, w)。x・y は同じ形の配列（y は平均の水面から上向き、水面より上でも級数の値を返す）。"""
    x = np.atleast_1d(np.asarray(x, float)); y = np.atleast_1d(np.asarray(y, float))
    X = x - s["c"] * t; Y = y + s["h"]; k = s["k"]; h = s["h"]
    u = np.full(X.shape, s["c"] - s["Ubar"]); w = np.zeros(X.shape)
    for jj, Bj in enumerate(s["B"], 1):
        a = jj * k * np.maximum(Y, 0.0); b = jj * k * h
        u = u + jj * k * Bj * _ch_over_ch(a, b) * np.cos(jj * k * X)
        w = w + jj * k * Bj * _sh_over_ch(a, b) * np.sin(jj * k * X)
    return u, w


def _bc_residuals(s, n=257):
    """節の間の点での水面の条件の残り（確かめ）。返り値：(運動の条件 |ψ + Q| の最大 ÷ Q、Bernoulli の残りの最大 ÷ (g H))。"""
    X = np.linspace(0, s["L"] / 2, n)
    e = eta(s, X)
    Y = s["h"] + e; k = s["k"]; h = s["h"]
    psi = -s["Ubar"] * Y; U = -s["Ubar"] * np.ones_like(X); V = np.zeros_like(X)
    for jj, Bj in enumerate(s["B"], 1):
        a = jj * k * Y; b = jj * k * h
        psi = psi + Bj * _sh_over_ch(a, b) * np.cos(jj * k * X)
        U = U + jj * k * Bj * _ch_over_ch(a, b) * np.cos(jj * k * X)
        V = V + jj * k * Bj * _sh_over_ch(a, b) * np.sin(jj * k * X)
    r1 = np.abs(psi + s["Q"]).max() / s["Q"]
    r2 = np.abs(0.5 * (U * U + V * V) + s["g"] * e - s["R"]).max() / (s["g"] * s["H"])
    return float(r1), float(r2)


def _depth_quad(s, nX=256, nY=48):
    """1 波長の X と、海底から水面までの Gauss–Legendre の点（エネルギーの流れなどの積分用）。"""
    X = np.arange(nX) * s["L"] / nX
    e = eta(s, X)
    gx, gw = np.polynomial.legendre.leggauss(nY)
    Ytop = s["h"] + e
    Y = 0.5 * (gx[None, :] + 1) * Ytop[:, None]
    W = 0.5 * gw[None, :] * Ytop[:, None]
    return X, e, Y, W


def energy_flux(s, nX=256, nY=48):
    """止まった座標の 1 周期の平均のエネルギーの流れ F（ρ = 1、単位 m³/s³ × ... = W/m ÷ ρ）。
    F = ⟨∫ [p + ½(u² + w²) + g y] u dY⟩、p は動く座標の Bernoulli（p = R − ½|U|² − g y）。質量の流れが 0 なので y の基準によらない。"""
    X, e, Y, W = _depth_quad(s, nX, nY)
    XX = np.repeat(X[:, None], Y.shape[1], 1)
    u, w = vel(s, XX.ravel(), (Y - s["h"]).ravel())
    u = u.reshape(Y.shape); w = w.reshape(Y.shape)
    y = Y - s["h"]
    U = u - s["c"]
    p = s["R"] - 0.5 * (U * U + w * w) - s["g"] * y
    f = (p + 0.5 * (u * u + w * w) + s["g"] * y) * u
    return float((f * W).sum(1).mean())


def mass_flux(s, nX=256, nY=48):
    X, e, Y, W = _depth_quad(s, nX, nY)
    XX = np.repeat(X[:, None], Y.shape[1], 1)
    u, _ = vel(s, XX.ravel(), (Y - s["h"]).ravel())
    return float((u.reshape(Y.shape) * W).sum(1).mean())


def profile_measures(s, n=4001):
    """形の量（STUDY52 と同じ定義の、崩れる前の対称な形の目安）：0.7 η_c の幅 ÷ η_c、後ろの面の 0.7〜0.9 η_c の角（度）、
    η_c/H、谷 ÷ η_c、頂の近くの角（0.95 η_c の弦）。η_c は平均の水面から（静かな水面との差は 1 cm の桁）。"""
    X = np.linspace(-s["L"] / 2, s["L"] / 2, n)
    e = eta(s, X)
    ec = float(e.max())

    def xat(level, side):
        # 頂から side（−1 後ろ、+1 前）へ、初めて level を切る x
        i0 = int(np.argmax(e))
        idx = range(i0, -1, -1) if side < 0 else range(i0, n)
        prev = i0
        for i in idx:
            if e[i] < level:
                x1, x2, e1, e2 = X[prev], X[i], e[prev], e[i]
                return float(x1 + (level - e1) * (x2 - x1) / (e2 - e1))
            prev = i
        return float("nan")
    xb7, xb9 = xat(0.7 * ec, -1), xat(0.9 * ec, -1)
    xf7 = xat(0.7 * ec, +1)
    xb95 = xat(0.95 * ec, -1)
    back = math.degrees(math.atan2(0.2 * ec, xb9 - xb7))
    return dict(eta_c=ec, eta_t=float(e.min()), eta_c_over_H=ec / s["H"], trough_over_eta_c=float(e.min()) / ec,
                width07_over_eta_c=(xf7 - xb7) / ec, back_angle_07_09_deg=back,
                crest_chord_095_deg=math.degrees(math.atan2(0.05 * ec, -xb95)))


def table(s):
    """入口の帯の VEX に渡す表（設計の json に入れる形）。"""
    return dict(h=s["h"], T=s["T"], H=s["H"], N=s["N"], k=s["k"], L=s["L"], c=s["c"], Ubar=s["Ubar"], u1_mean_current=s["u1"],
                Q=s["Q"], R=s["R"], B=[float(v) for v in s["B"]], E=[float(v) for v in s["E"]], eta_crest=s["eta_crest"],
                eta_trough=s["eta_trough"], ursell=s["ursell"], residual_max=s["residual_max"])


# ------------------------------------------------------------------ 浅くなる間の高さ（エネルギーの流れを保つ）
def shoal_step(F0, h, T, s_prev, g=G, qmax=0.985, grow=1.02):
    """前の水深の解 s_prev（同じ T）から続けて、水深 h でエネルギーの流れが F0 になる解を探す。
    返り値 (解 or None, 届いた F の最大, 調べた H の上限)。None は「最も高い波の qmax 倍までで F0 に届かない」＝定常の波では運べない。"""
    Hm = highest_H(h, T, g)
    Hcap = qmax * Hm
    H = min(s_prev["H"], Hcap * 0.999)
    prev = s_prev; lo = None; Flo = None; best = -1.0
    while True:
        s = solve(h, T, H, g=g, init=prev)
        if not s["ok"]:
            break
        F = energy_flux(s); best = max(best, F)
        if F >= F0:
            if lo is None:          # 始めから越えた：H を下げて挟む
                Hd = H
                while F >= F0 and Hd > 0.05 * Hm:
                    Hd /= grow
                    s2 = solve(h, T, Hd, g=g, init=s)
                    F2 = energy_flux(s2)
                    if F2 < F0:
                        lo, Flo, slo = Hd, F2, s2
                        break
                    s, F, H = s2, F2, Hd
                if lo is None:
                    return s, best, Hcap
            # lo..H を割線で詰める
            hi, Fhi, shi = H, F, s
            for _ in range(30):
                Hn = lo + (F0 - Flo) * (hi - lo) / (Fhi - Flo)
                sn = solve(h, T, Hn, g=g, init=shi)
                Fn = energy_flux(sn)
                if abs(Fn - F0) < 1e-6 * F0 or abs(hi - lo) < 1e-5:
                    return sn, max(best, Fn), Hcap
                if Fn < F0:
                    lo, Flo, slo = Hn, Fn, sn
                else:
                    hi, Fhi, shi = Hn, Fn, sn
            return sn, best, Hcap
        lo, Flo, slo = H, F, s
        prev = s
        if H >= Hcap * 0.9999:
            break
        H = min(H * grow, Hcap)
    return None, best, Hcap


def shoal_H(F0, h, T, H_hint=None, g=G):
    """水深 h で、エネルギーの流れが F0 になる H（流れ関数の解の範囲で）。解がない（F0 が届かない）時は None と、その水深で届く F の最大。"""
    Hm = highest_H(h, T, g)
    hi = 0.97 * Hm

    def f(H):
        s_ = solve(h, T, H, g=g)
        if not s_["ok"]:
            raise RuntimeError(s_["msg"])
        return energy_flux(s_) - F0
    # F(H) は最も高い波の手前で最大になることがあるので、粗く走って符号の変わりを探す
    grid = np.linspace(0.05 * Hm, hi, 14)
    if H_hint is not None:
        grid = np.unique(np.concatenate([grid, [min(max(H_hint, 0.05 * Hm), hi)]]))
    vals = []
    for H in grid:
        try:
            vals.append(f(H))
        except Exception:
            vals.append(np.nan)
    vals = np.array(vals)
    for i in range(len(grid) - 1):
        if np.isfinite(vals[i]) and np.isfinite(vals[i + 1]) and vals[i] <= 0 < vals[i + 1]:
            return brentq(f, grid[i], grid[i + 1], xtol=1e-4), float(np.nanmax(vals) + F0)
    return None, float(np.nanmax(vals) + F0)
