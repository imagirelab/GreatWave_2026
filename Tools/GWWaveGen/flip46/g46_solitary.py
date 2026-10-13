# -*- coding: utf-8 -*-
"""FLIP46：厳密な孤立波（Tanaka 1986 型。重力だけ、有限の水深、渦なし）を numpy だけで解き、水の中の流速を出す。
2026-10-12 孤立波の解き手の役が新しく書いた。計画：Docs/Research/BigWave_Recipes_ja.md §5.2「E1b」の「初めの波」。

解き方（Clamond & Dutykh 2013, Computers & Fluids 84, 35-38, arXiv:1212.0289 の式を numpy へ書き直した）：
  - 波と一緒に動く座標で、水の領域を等角写像で幅 d の帯 −d ≤ β ≤ 0（ζ = α + iβ）へ移す。複素ポテンシャルは f = −c ζ。
  - 演算子 C：フーリエの記号 k coth(kd)（k = 0 は 1/d）。水面で x_α = 1 + C{η}。
  - Babenko 型の式：c² C{η} − g η − ½ g C{η²} − g η C{η} = 0。
    これを L{η} = N{η}、L = c² − g C⁻¹、N = g C⁻¹{η C{η}} + ½ g η² と書き、Petviashvili の反復
    η ← S² L⁻¹ N{η}、S = <η, Lη> / <η, Nη> で解く（FFT。周期の箱 α ∈ [−L/2, L/2)、既定 L = 80 d、N = 2^15）。
  - F = c/√(gd) を与えると振幅 a が決まる。a/d を与える時は、F を割線法で合わせる。
  - 写像：z(ζ) = ζ + b0 (ζ + i d) + Σ_{m≥1} b_m sin(k_m (ζ + i d)) / sinh(k_m d)、η(α) = b0 + Σ b_m cos(k_m α)（頂を α = 0 に置く）。
    流速（波と動く座標）W = u − i v = −c / z_ζ。止まった座標（波は +x へ c で進む）では u = c (1 − Re(1/z_ζ))、w = c Im(1/z_ζ)。
  - 水の中の点 (x, z) は、写像を Newton 法で逆に解いて ζ を求め、そこで 1/z_ζ を出す（浅い水の近似は使わない）。

座標（FLIP46 の計画と同じ）：x は波の進む向き（上流の壁が 0）、z は上（静かな水面 0、平らな海底 −h0）。止まった座標の流速 (u, w)。
既定：h0 17 m、a/h0 0.6、頂 x0 98.345 m（5.785 h0）、g 9.80665。

使い方（py -3.10 でも hython でも読める。評価の道は numpy だけ）：
  import g46_solitary as S
  wave = S.get_wave()                      # 解（キャッシュの npz があれば読む。なければ解いて書く）
  wave.F, wave.c                           # F = c/√(g h0)、c (m/s)
  wave.eta(x)                              # 水面 (m)、x は配列 (m)
  u, w = wave.velocity(x, z)               # 水の中の点の流速 (m/s)。水面より上・海底より下は NaN（above="surface" で水面の値）
  wave.write_grid(path, xs, zs)            # npz：x, z, eta, u[z,x], w[z,x], c, F, a_over_h, h0, x0, meta/info
  S.solve(0.6)                             # 無次元の解（F・α・x(α)・η(α)・解の確かめ）
コマンド：py -3.10 g46_solitary.py [--check] [--grid]
  --check：確かめ（文献の値・収束・水面の条件の残り・流量・GN との差）を Unity/Build/FLIP46/solitary_check.json へ書く
  --grid ：既定の表 Unity/Build/FLIP46/solitary/tanaka_a0p6.npz（x 0〜328 m・z −17〜+12.25 m、0.25 m 刻み）を書く
"""
import os, sys, json, math, time

import numpy as np

REPO = r"G:/Unity/GreatWave_2026_Fresh"
B46 = REPO + "/Unity/Build/FLIP46"
SOL_DIR = B46 + "/solitary"
CHECK_JSON = B46 + "/solitary_check.json"
GRID_DEFAULT = SOL_DIR + "/tanaka_a0p6.npz"

G = 9.80665
H0 = 17.0
A_OVER_H = 0.6
X0 = 5.785 * H0            # 98.345 m
L_DEF = 80.0               # 周期の箱の長さ（d を 1 とした α の長さ）。裾は e^{-κ|α|}、κ ≈ 1 で ±40 d まで e^{-40}
N_DEF = 2 ** 15


def cache_path(a_over_h, L=L_DEF, N=N_DEF):
    return SOL_DIR + "/tanaka_coef_a%.4f_L%g_N%d.npz" % (a_over_h, L, N)


# ------------------------------------------------------------------ 無次元の解き手（g = d = 1）
def _ops(L, N):
    alpha = -0.5 * L + np.arange(N) * (L / N)
    k = 2.0 * np.pi * np.fft.rfftfreq(N, d=L / N)
    Cs = np.ones_like(k)
    Cs[1:] = k[1:] / np.tanh(k[1:])          # C の記号 k coth k（k = 0 は 1）
    Ci = 1.0 / Cs                             # C⁻¹ の記号 tanh k / k（k = 0 は 1）
    wgt = np.full(k.shape, 2.0)               # 実数の FFT で内積を出す重み（Parseval）
    wgt[0] = 1.0
    if N % 2 == 0:
        wgt[-1] = 1.0
    return alpha, k, Cs, Ci, wgt


def _kappa(F):
    """線形の裾の減り方 κ：F² = tan(κ)/κ（0 < κ < π/2）。二分法。"""
    f2 = F * F
    lo, hi = 1e-12, 0.5 * np.pi - 1e-12
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if math.tan(m) / m < f2:
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


def _sym(e):
    """α → −α の対称を保つ（頂を α = 0 に固定。丸めの誤差で頂がずれないように）。"""
    return 0.5 * (e + np.roll(e[::-1], 1))


def babenko(F, L=L_DEF, N=N_DEF, tol=1e-14, maxit=20000, eta0=None):
    """F を与えて Babenko 型の式を Petviashvili の反復で解く。返り値 (eta, info)。eta は α 格子の上の値（d = 1）。"""
    alpha, k, Cs, Ci, wgt = _ops(L, N)
    rf, irf = np.fft.rfft, np.fft.irfft
    if eta0 is None:
        kap = _kappa(F)
        eta = (F * F - 1.0) / np.cosh(0.5 * kap * alpha) ** 2
    else:
        eta = np.array(eta0, dtype=np.float64)
    Lh = F * F - Ci
    err = np.inf
    it = 0
    for it in range(1, maxit + 1):
        eh = rf(eta)
        Ceta = irf(Cs * eh, N)
        Nh = Ci * rf(eta * Ceta) + 0.5 * rf(eta * eta)
        num = np.sum(wgt * (np.conj(eh) * Lh * eh).real)
        den = np.sum(wgt * (np.conj(eh) * Nh).real)
        S = num / den
        new = _sym(irf(S * S * Nh / Lh, N))
        err = float(np.max(np.abs(new - eta)))
        eta = new
        if err < tol:
            break
    # 式の残り（L η − N η、無次元）
    eh = rf(eta)
    Ceta = irf(Cs * eh, N)
    res = irf(Lh * eh, N) - (irf(Ci * rf(eta * Ceta), N) + 0.5 * eta * eta)
    info = dict(F=float(F), L=float(L), N=int(N), iterations=int(it), last_change=err, S_last=float(S),
                babenko_residual_inf=float(np.max(np.abs(res))))
    return eta, info


def _amp(eta):
    return float(eta[len(eta) // 2])        # α = 0（頂）は格子の N/2 番目


def solve(a_over_h=A_OVER_H, L=L_DEF, N=N_DEF, tol_a=1e-13, F=None, verbose=False):
    """a/h を与えて解く（F を割線法で合わせる）。F を与えた時はその F で解く（a は結果）。
    返り値 dict：F・a_over_h・alpha・eta（α 格子）・x（同じ α での水面の x）・info。長さは h で割った値。"""
    t0 = time.time()
    if F is not None:
        eta, info = babenko(F, L, N)
        hist = [(float(F), _amp(eta))]
    else:
        a = float(a_over_h)
        F1 = math.sqrt(1.0 + a - a * a / 20.0 - 3.0 * a ** 3 / 70.0)    # 3 次の近似（Grimshaw 1971）から始める
        F0 = F1 - 2e-3
        e0, _ = babenko(F0, L, N)
        a0 = _amp(e0)
        e1, info = babenko(F1, L, N, eta0=e0)
        a1 = _amp(e1)
        hist = [(F0, a0), (F1, a1)]
        eta = e1
        for _ in range(40):
            if abs(a1 - a) < tol_a:
                break
            F2 = F1 + (a - a1) * (F1 - F0) / (a1 - a0)
            F0, a0 = F1, a1
            e1, info = babenko(F2, L, N, eta0=e1)
            F1, a1 = F2, _amp(e1)
            hist.append((F1, a1))
            eta = e1
            if verbose:
                print("  F %.15f  a %.15f" % (F1, a1))
        F = F1
    alpha, k, Cs, Ci, wgt = _ops(L, N)
    xs = alpha + np.fft.irfft(Cs * np.fft.rfft(eta) / np.where(k > 0, 1j * k, 1.0) * (k > 0), N).real  # 周期の部分
    eh0 = float(np.mean(eta))
    xs = xs + eh0 * alpha                                       # k = 0 の分（x の伸び b0 α）
    info.update(secant=hist, seconds=time.time() - t0)
    return dict(F=float(F), a_over_h=_amp(eta), alpha=alpha, eta=eta, x=xs, L=float(L), N=int(N), info=info)


# ------------------------------------------------------------------ 写像と流速（無次元、頂が x = 0、α = 0）
class _Map(object):
    """η(α) の余弦の係数 b_m（k_m = m Δk）から、帯の中の任意の ζ で z(ζ)・z_ζ(ζ) を出す。
    e^{i k_m ...} は (e^{i Δk ...})^m の累積の積で出す（指数の関数を呼ぶより速い。m ≤ 2000 で相対の丸め 1e-13 以下）。"""

    def __init__(self, b, k, F, L, N, mode_tol=1e-16, chunk=2048):
        b = np.asarray(b, dtype=np.float64)
        k = np.asarray(k, dtype=np.float64)
        # 係数の裾を切る：|b_m| (1 + k_m) < mode_tol が 64 個続く最初の所まで（その先は丸めの床 1e-19 の桁）
        small = (np.abs(b) * (1.0 + k)) < mode_tol
        M = len(b)
        for m in range(1, len(b) - 64):
            if small[m] and small[m:m + 64].all():
                M = m
                break
        self.b0 = float(b[0])
        self.b = b[1:M].copy()
        self.k = k[1:M].copy()
        self.dk = float(k[1])
        self.F = float(F)
        self.L = float(L)
        self.N = int(N)
        self.modes = M - 1
        self.dropped = float(np.sum(np.abs(b[M:]) * (1.0 + k[M:])))
        den = 1.0 - np.exp(-2.0 * self.k)                  # sinh(k) = e^k (1 − e^{−2k}) / 2
        self.bk = self.b * self.k
        self.bcoth = self.b / np.tanh(self.k)
        self.bkcoth = self.bk / np.tanh(self.k)
        self.b_den = self.b / den
        self.bk_den = self.bk / den
        self.chunk = int(chunk)

    def _pow(self, w):
        """[n] の複素数 w から [n, M] の w^m（m = 1..M）。"""
        P = np.repeat(w[:, None], len(self.k), axis=1)
        return np.cumprod(P, axis=1)

    # 水面（β = 0）
    def surf(self, a):
        a = np.asarray(a, dtype=np.float64).ravel()
        n = a.size
        eta = np.empty(n); x = np.empty(n); xa = np.empty(n); ea = np.empty(n)
        for i0 in range(0, n, self.chunk):
            aa = a[i0:i0 + self.chunk]
            E = self._pow(np.exp(1j * self.dk * aa))
            c, s = E.real, E.imag
            eta[i0:i0 + self.chunk] = self.b0 + c @ self.b
            x[i0:i0 + self.chunk] = aa * (1.0 + self.b0) + s @ self.bcoth
            xa[i0:i0 + self.chunk] = 1.0 + self.b0 + c @ self.bkcoth
            ea[i0:i0 + self.chunk] = -(s @ self.bk)
        return x, eta, xa, ea

    def alpha_of_x(self, x, a_tab, x_tab):
        """水面の x から α を Newton 法で出す（初めは表の線形補間）。"""
        a = np.interp(x, x_tab, a_tab)
        for _ in range(30):
            xx, _, xa, _ = self.surf(a)
            da = (xx - x) / xa
            a = a - da
            if np.max(np.abs(da), initial=0.0) < 1e-14:
                break
        return a

    # 帯の中（−1 ≤ β ≤ 0）
    def zmap(self, zeta):
        """z(ζ) と z_ζ(ζ)。sin(k s)/sinh k = (A − B)/(i (1 − e^{−2k}))、cos(k s)/sinh k = (A + B)/(1 − e^{−2k})、
        s = ζ + i、A = e^{i k (ζ + 2i)}、B = e^{−i k ζ}（−1 ≤ β ≤ 0 でどちらも大きさ 1 以下）。"""
        zeta = np.asarray(zeta, dtype=np.complex128).ravel()
        n = zeta.size
        z = np.empty(n, dtype=np.complex128)
        zz = np.empty(n, dtype=np.complex128)
        for i0 in range(0, n, self.chunk):
            ze = zeta[i0:i0 + self.chunk]
            A = self._pow(np.exp(1j * self.dk * (ze + 2j)))
            B = self._pow(np.exp(-1j * self.dk * ze))
            z[i0:i0 + self.chunk] = ze + self.b0 * (ze + 1j) - 1j * ((A - B) @ self.b_den)
            zz[i0:i0 + self.chunk] = 1.0 + self.b0 + (A + B) @ self.bk_den
        return z, zz


class Solitary(object):
    """実物の大きさの厳密な孤立波（止まった座標。t = 0 で頂が x0、+x へ c で進む）。"""

    def __init__(self, sol, h0=H0, g=G, x0=X0):
        self.h0 = float(h0)
        self.g = float(g)
        self.x0 = float(x0)
        self.F = float(sol["F"])
        self.a_over_h = float(sol["a_over_h"])
        self.c = self.F * math.sqrt(self.g * self.h0)
        self.L = float(sol["L"])
        self.N = int(sol["N"])
        self.alpha = np.asarray(sol["alpha"], dtype=np.float64)
        self.eta_a = np.asarray(sol["eta"], dtype=np.float64)
        self.x_a = np.asarray(sol["x"], dtype=np.float64)
        self.info = dict(sol.get("info", {}))
        alpha, k, Cs, Ci, wgt = _ops(self.L, self.N)
        eh = np.fft.rfft(self.eta_a) / self.N
        sgn = np.where(np.arange(len(k)) % 2 == 0, 1.0, -1.0)   # α の原点を −L/2 から 0 へ移す (−1)^m
        bh = (eh * sgn).real
        b = 2.0 * bh
        b[0] = bh[0]
        if self.N % 2 == 0:
            b[-1] = bh[-1]
        self.map = _Map(b, k, self.F, self.L, self.N)

    # -------------------------------------------------- 無次元の道具（頂が 0、長さは h0 で割る）
    def _xd(self, x, t):
        return (np.asarray(x, dtype=np.float64) - self.x0 - self.c * t) / self.h0

    def _check_range(self, xd):
        lim = 0.5 * self.L * (1.0 + self.map.b0) - 2.0
        if np.any(np.abs(xd) > lim):
            raise ValueError("x が解の周期の箱（頂から ±%.1f h0）の外" % lim)

    # -------------------------------------------------- 水面
    def eta(self, x, t=0.0):
        """水面の高さ (m)。x は配列 (m)。"""
        xd = self._xd(x, t)
        self._check_range(xd)
        a = self.map.alpha_of_x(xd.ravel(), self.alpha, self.x_a)
        _, e, _, _ = self.map.surf(a)
        return (e * self.h0).reshape(np.shape(xd))

    def eta_x(self, x, t=0.0):
        """水面の傾き ∂η/∂x（無次元）。"""
        xd = self._xd(x, t)
        a = self.map.alpha_of_x(xd.ravel(), self.alpha, self.x_a)
        _, _, xa, ea = self.map.surf(a)
        return (ea / xa).reshape(np.shape(xd))

    # -------------------------------------------------- 水の中の流速
    def _zeta_of(self, xd, yd, chunk=4096):
        """無次元の点 (xd, yd)（水の中）から ζ を Newton 法で出す。返り値 ζ・Newton の最後の差。"""
        n = xd.size
        out = np.empty(n, dtype=np.complex128)
        worst = 0.0
        for i0 in range(0, n, chunk):
            xs = xd[i0:i0 + chunk]
            ys = yd[i0:i0 + chunk]
            a = self.map.alpha_of_x(xs, self.alpha, self.x_a)
            _, es, _, _ = self.map.surf(a)
            b = (ys + 1.0) / (1.0 + es) - 1.0                     # 縦に線形に伸ばした初めの値
            zeta = a + 1j * b
            target = xs + 1j * ys
            act = np.ones(len(xs), dtype=bool)
            last = np.zeros(len(xs))
            for _ in range(40):
                idx = np.where(act)[0]
                if len(idx) == 0:
                    break
                z, zz = self.map.zmap(zeta[idx])
                d = (z - target[idx]) / zz
                zeta[idx] = zeta[idx] - d
                ad = np.abs(d)
                last[idx] = ad
                act[idx[ad < 1e-13]] = False
            if act.any():
                worst = max(worst, float(np.max(last[act])))
            out[i0:i0 + chunk] = zeta
        return out, worst

    def velocity(self, x, z, t=0.0, above="nan", return_info=False):
        """止まった座標の流速 (u, w)（m/s）。x・z は同じ形の配列 (m)、z は静かな水面 0・上向き。
        水面より上：above="nan" なら NaN、"surface" ならその x の水面の値。海底（−h0）より下は NaN。"""
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        x, z = np.broadcast_arrays(x, z)
        shp = x.shape
        xd = self._xd(x, t).ravel()
        yd = (z / self.h0).ravel()
        self._check_range(xd)
        a = self.map.alpha_of_x(xd, self.alpha, self.x_a)
        _, es, _, _ = self.map.surf(a)
        wet = (yd <= es + 1e-12) & (yd >= -1.0 - 1e-12)
        ycl = yd.copy()
        if above == "surface":
            up = yd > es
            ycl[up] = es[up]
            wet = wet | (up & (yd >= -1.0))
        u = np.full(xd.shape, np.nan)
        w = np.full(xd.shape, np.nan)
        worst = 0.0
        if wet.any():
            yy = np.clip(ycl[wet], -1.0, None)
            zeta, worst = self._zeta_of(xd[wet], yy)
            _, zz = self.map.zmap(zeta)
            r = 1.0 / zz
            s = math.sqrt(self.g * self.h0)
            u[wet] = self.F * (1.0 - r.real) * s
            w[wet] = self.F * r.imag * s
        if return_info:
            return u.reshape(shp), w.reshape(shp), dict(newton_worst=worst)
        return u.reshape(shp), w.reshape(shp)

    def velocity_points(self, pts, t=0.0, above="nan"):
        """点の並び pts（[n, 2] = (x, z)、または [n, 3] = (x, y_lat, z)）の流速。返り値 [n, 2] = (u, w)（m/s）。"""
        p = np.asarray(pts, dtype=np.float64)
        if p.ndim != 2 or p.shape[1] not in (2, 3):
            raise ValueError("pts は [n, 2] (x, z) か [n, 3] (x, y_lat, z)")
        zc = p[:, -1]
        u, w = self.velocity(p[:, 0], zc, t=t, above=above)
        return np.stack([u, w], axis=1)

    # -------------------------------------------------- 表に書く
    def grid(self, xs, zs, t=0.0):
        """表：eta[nx]、u・w[nz, nx]（水面より上・海底より下は NaN）、u_ext・w_ext（水面より上をその x の水面の厳密な値で埋めた物）、
        u_surf・w_surf[nx]（水面の流速）。"""
        xs = np.asarray(xs, dtype=np.float64).ravel()
        zs = np.asarray(zs, dtype=np.float64).ravel()
        X, Z = np.meshgrid(xs, zs)                   # [z, x]
        u, w = self.velocity(X, Z, t=t, above="nan")
        eta = self.eta(xs, t=t)
        us, ws = self.velocity(xs, eta - 1e-9, t=t)
        up = Z > eta[None, :]
        ue = np.where(up, us[None, :], u)
        we = np.where(up, ws[None, :], w)
        return eta, u, w, ue, we, us, ws

    def meta(self):
        return dict(method="exact solitary wave (Tanaka 1986 type), Babenko + Petviashvili, Clamond & Dutykh 2013 (numpy rewrite)",
                    made_by="g46_solitary.py", a_over_h=self.a_over_h, F=self.F, c=self.c, h0=self.h0, g=self.g, x0=self.x0,
                    L_over_h=self.L, N=self.N, modes=self.map.modes, units="m, m/s", layout="u[z, x]",
                    frame="rest frame; wave moves +x at c; crest at x0 + c t",
                    z="still water z = 0, flat bed z = -h0", above_surface="NaN")

    def write_grid(self, path, xs, zs, t=0.0):
        """npz：x[nx]・z[nz]（m）・eta[nx]（m）・u[nz,nx]・w[nz,nx]（m/s、水面より上は NaN）・c・F・a_over_h・h0・x0・t・meta・info。
        ほかに u_ext・w_ext[nz,nx]（水面より上を水面の厳密な値で埋めた物。NaN なし）・u_surf・w_surf[nx]（水面の流速）。
        g46_tanklib.PYSOP（場面の solution_table）がそのまま読む形（GN の代わりの npz と同じ）。"""
        xs = np.asarray(xs, dtype=np.float64).ravel()
        zs = np.asarray(zs, dtype=np.float64).ravel()
        eta, u, w, ue, we, us, ws = self.grid(xs, zs, t=t)
        m = self.meta()
        m["t"] = float(t)
        js = json.dumps(m, ensure_ascii=False)
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        np.savez_compressed(path, x=xs, z=zs, eta=eta, u=u, w=w, u_ext=ue, w_ext=we, u_surf=us, w_surf=ws,
                            c=np.float64(self.c), F=np.float64(self.F),
                            a_over_h=np.float64(self.a_over_h), h0=np.float64(self.h0), x0=np.float64(self.x0 + self.c * t),
                            t=np.float64(t), meta=js, info=js)
        return path

    # -------------------------------------------------- 解を残す・読む
    def save(self, path):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        np.savez_compressed(path, F=np.float64(self.F), a_over_h=np.float64(self.a_over_h), L=np.float64(self.L),
                            N=np.int64(self.N), alpha=self.alpha, eta=self.eta_a, x=self.x_a,
                            info=json.dumps(self.info, ensure_ascii=False, default=float))
        return path

    @classmethod
    def load(cls, path, h0=H0, g=G, x0=X0):
        d = np.load(path, allow_pickle=False)
        sol = dict(F=float(d["F"]), a_over_h=float(d["a_over_h"]), L=float(d["L"]), N=int(d["N"]),
                   alpha=d["alpha"], eta=d["eta"], x=d["x"], info=json.loads(str(d["info"])))
        return cls(sol, h0=h0, g=g, x0=x0)


def get_wave(a_over_h=A_OVER_H, h0=H0, x0=X0, g=G, L=L_DEF, N=N_DEF, use_cache=True, write_cache=True):
    """解を返す（キャッシュの npz があれば読む。なければ解いて書く）。"""
    p = cache_path(a_over_h, L, N)
    if use_cache and os.path.exists(p):
        return Solitary.load(p, h0=h0, g=g, x0=x0)
    sol = solve(a_over_h, L=L, N=N)
    wv = Solitary(sol, h0=h0, g=g, x0=x0)
    if write_cache:
        try:
            wv.save(p)
        except Exception:
            pass
    return wv


def velocity_points(pts, t=0.0, above="nan", wave=None):
    """点の並び（[n,2] (x,z) か [n,3] (x,y_lat,z)、m）の流速 [n,2] (u,w)（m/s）。粒子の流速を置く時に使う。"""
    wv = wave if wave is not None else get_wave()
    return wv.velocity_points(pts, t=t, above=above)


def write_grid(path, xs, zs, t=0.0, wave=None):
    wv = wave if wave is not None else get_wave()
    return wv.write_grid(path, xs, zs, t=t)


# ------------------------------------------------------------------ GN の孤立波（比べるため。BigWave_Recipes_ja.md §5.1）
def gn_fields(x, z, a=A_OVER_H * H0, h0=H0, x0=X0, g=G):
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    C = math.sqrt(g * h0 * (1.0 + a / h0))
    kap = math.sqrt(3.0 * (a / h0) / (4.0 * (1.0 + a / h0))) / h0
    xi = x - x0
    s2 = 1.0 / np.cosh(kap * xi) ** 2
    eta = a * s2
    etax = -2.0 * a * kap * s2 * np.tanh(kap * xi)
    u = C * eta / (h0 + eta)
    w = -C * h0 * (z + h0) * etax / (h0 + eta) ** 2
    return eta, u, w, C


# ------------------------------------------------------------------ 確かめ
def _gauss(n):
    return np.polynomial.legendre.leggauss(n)


def run_checks(out_json=CHECK_JSON, verbose=True):
    rep = {}
    t0 = time.time()

    def say(*a):
        if verbose:
            print(*a)
            sys.stdout.flush()

    # 1. 文献の値（Clamond & Dutykh 2013・Dutykh & Clamond 2014 の多倍長の計算）を同じ F で写す
    refs = [
        dict(F=1.066365888477383, a_ref=0.138218938724572457342, src="Dutykh & Clamond 2014 (arXiv:1302.1812) §3.3, 多倍長"),
        dict(F=1.274236297977903, a_ref=0.68196566738691572071, src="Clamond & Dutykh 2013 (arXiv:1212.0289) 表 1, 50 桁; Tanaka 法は 0.6819448"),
        dict(F=1.290941713543984, a_ref=0.75839385511604004860, src="Dutykh & Clamond 2014 §3.3, q_c 0.3, 多倍長"),
    ]
    rl = []
    for r in refs:
        s = solve(F=r["F"], L=L_DEF, N=N_DEF)
        d = dict(F=r["F"], a_ours=s["a_over_h"], a_ref=r["a_ref"], diff=s["a_over_h"] - r["a_ref"], source=r["src"],
                 iterations=s["info"]["iterations"], babenko_residual_inf=s["info"]["babenko_residual_inf"])
        rl.append(d)
        say("ref F %.15f  a ours %.16f  ref %.16f  diff %.2e  it %d" % (r["F"], d["a_ours"], r["a_ref"], d["diff"], d["iterations"]))
    rep["literature_F_to_a"] = rl

    # 2. 本番の解 a/h 0.6
    sol = solve(A_OVER_H, L=L_DEF, N=N_DEF)
    wv = Solitary(sol)
    say("a/h %.15f  F %.15f  c %.6f m/s" % (wv.a_over_h, wv.F, wv.c))
    rep["main"] = dict(a_over_h=wv.a_over_h, F=wv.F, F2=wv.F ** 2, c_m_s=wv.c, h0=H0, g=G, x0=X0, L_over_h=L_DEF, N=N_DEF,
                       modes_kept=wv.map.modes, coef_dropped=wv.map.dropped, iterations=sol["info"]["iterations"],
                       babenko_residual_inf=sol["info"]["babenko_residual_inf"],
                       series_F_3rd_order_Grimshaw1971=math.sqrt(1 + 0.6 - 0.36 / 20 - 3 * 0.216 / 70),
                       F_GN=math.sqrt(1.6), plan_value="1.25 (BigWave_Recipes_ja.md §5.2, GG06)")

    # 3. 収束（N と L）：F を本番の値に止めて a を見る
    conv = []
    for (L, N) in [(80.0, 2 ** 11), (80.0, 2 ** 12), (80.0, 2 ** 13), (80.0, 2 ** 14), (80.0, 2 ** 15), (80.0, 2 ** 16),
                   (60.0, 3 * 2 ** 13), (120.0, 3 * 2 ** 14)]:
        s = solve(F=wv.F, L=L, N=N)
        conv.append(dict(L=L, N=N, dalpha=L / N, a=s["a_over_h"], a_minus_main=s["a_over_h"] - wv.a_over_h,
                         iterations=s["info"]["iterations"], residual=s["info"]["babenko_residual_inf"]))
        say("conv L %g N %d  a %.16f  d %.2e" % (L, N, s["a_over_h"], s["a_over_h"] - wv.a_over_h))
    rep["convergence_fixed_F"] = conv
    # 係数の減り方
    bb = np.abs(np.concatenate([[wv.map.b0], wv.map.b]))
    kk = np.concatenate([[0.0], wv.map.k])
    rep["spectrum"] = dict(k_at_1e_6=float(kk[np.where(bb > 1e-6 * bb.max())[0][-1]]),
                           k_at_1e_12=float(kk[np.where(bb > 1e-12 * bb.max())[0][-1]]),
                           k_last_kept=float(wv.map.k[-1]), modes_kept=wv.map.modes)

    # 4. 水面の条件の残り（格子の間の点で。無次元 g = d = 1）
    m = wv.map
    am = wv.alpha[:-1] + 0.5 * (wv.alpha[1] - wv.alpha[0])            # 格子の中点（FFT の点ではない所）
    sel = np.abs(am) < 20.0
    am = am[sel]
    xs, es, xa, ea = m.surf(am)
    q2 = (wv.F ** 2) / (xa ** 2 + ea ** 2)                               # |u − c|² / (g d)（波と動く座標）
    bern = 0.5 * q2 + es - 0.5 * wv.F ** 2
    # 写像の式（2D の z(ζ)）で水面の点を出し直して同じ数か
    z, zz = m.zmap(am + 0j)
    rep["surface_conditions"] = dict(
        bernoulli_residual_inf=float(np.max(np.abs(bern))),
        bernoulli_note="½|∇φ−c|² + g η − ½ c² を g h0 で割った値（格子の中点 |α|<20）",
        map_surface_y_minus_eta=float(np.max(np.abs(z.imag - es))), map_surface_x_minus_x=float(np.max(np.abs(z.real - xs))),
        map_bottom_y_plus_1=float(np.max(np.abs(m.zmap(am - 1j)[0].imag + 1.0))))
    say("Bernoulli residual %.2e" % rep["surface_conditions"]["bernoulli_residual_inf"])

    # 5. 実物の大きさの点で：水の中の Newton の逆と、運動学の条件・流量・渦なし・発散なし
    s = math.sqrt(G * H0)
    xp = X0 + np.linspace(-90.0, 220.0, 621)
    ep = wv.eta(xp)
    ex = wv.eta_x(xp)
    us, ws, inf = wv.velocity(xp, ep - 1e-9, return_info=True)
    kin = ws - (us - wv.c) * ex                                          # 止まった座標：η_t + u η_x = w、η_t = −c η_x
    us2, ws2 = wv.velocity(xp, np.full_like(xp, -H0))
    # 流量：∫_{−h0}^{η} u dz = c η（どの x でも厳密）
    gx, gw = _gauss(48)
    flux_err = []
    xf = X0 + np.array([-60.0, -30.0, -15.0, -5.0, 0.0, 3.0, 10.0, 20.0, 40.0, 80.0])
    for xi in xf:
        e = float(wv.eta(np.array([xi]))[0])
        zq = -H0 + (gx + 1.0) * 0.5 * (e + H0)
        uq, _ = wv.velocity(np.full_like(zq, xi), zq)
        q = float(np.sum(gw * uq) * 0.5 * (e + H0))
        flux_err.append(dict(x=float(xi), eta=e, flux=q, c_eta=wv.c * e, rel=(q - wv.c * e) / (wv.c * wv.a_over_h * H0)))
    # 発散・渦（2 次の中心差分。h 0.1 m と 0.05 m で、残りが h² で 1/4 に減れば差分の誤差で、流速の場そのものは渦なし・発散なし）
    xg = X0 + np.array([-20.0, -8.0, 0.0, 6.0, 15.0])
    zg = np.array([-15.0, -9.0, -3.0, 2.0, 6.0])
    XG, ZG = np.meshgrid(xg, zg)
    ok = ZG < wv.eta(XG) - 0.3
    XG, ZG = XG[ok], ZG[ok]
    fd = {}
    for hh in (0.1, 0.05):
        up, wp = wv.velocity(XG + hh, ZG)
        um, wm = wv.velocity(XG - hh, ZG)
        uu, wu = wv.velocity(XG, ZG + hh)
        ud, wd = wv.velocity(XG, ZG - hh)
        div = (up - um) / (2 * hh) + (wu - wd) / (2 * hh)
        curl = (uu - ud) / (2 * hh) - (wp - wm) / (2 * hh)
        dudx = (up - um) / (2 * hh)
        fd[hh] = (float(np.max(np.abs(div))), float(np.max(np.abs(curl))), float(np.max(np.abs(dudx))))
    rep["interior_checks"] = dict(
        kinematic_residual_inf_m_s=float(np.nanmax(np.abs(kin))),
        kinematic_note="水面の点で w − (u − c) ∂η/∂x（m/s、x0−90〜x0+220 m の 621 点、Newton で逆に解いた流速）",
        bed_w_inf_m_s=float(np.nanmax(np.abs(ws2))),
        newton_worst=inf["newton_worst"],
        flux_identity=flux_err,
        flux_rel_inf=float(max(abs(f["rel"]) for f in flux_err)),
        div_inf_1_s_h0p1=fd[0.1][0], curl_inf_1_s_h0p1=fd[0.1][1], div_inf_1_s_h0p05=fd[0.05][0], curl_inf_1_s_h0p05=fd[0.05][1],
        max_abs_dudx_1_s=fd[0.05][2],
        fd_note="2 次の中心差分の残り。h を半分にして 1/4 になれば差分の誤差（流速の傾き 0.3〜0.5 s⁻¹ に対して 1e-6 の桁）")
    say("kinematic %.2e m/s  bed w %.2e  flux rel %.2e  div %.2e/%.2e curl %.2e/%.2e (h 0.1/0.05)" % (
        rep["interior_checks"]["kinematic_residual_inf_m_s"], rep["interior_checks"]["bed_w_inf_m_s"],
        rep["interior_checks"]["flux_rel_inf"], fd[0.1][0], fd[0.05][0], fd[0.1][1], fd[0.05][1]))

    # 6. 質量・エネルギー（無次元：M/h0²、E/(ρ g h0³)）と、厳密な関係 V = (F² − 1) M / 3（Starr 1947、Longuet-Higgins 1974）
    alpha, k, Cs, Ci, wgt = _ops(wv.L, wv.N)
    e = wv.eta_a
    Ce = np.fft.irfft(Cs * np.fft.rfft(e), wv.N)
    da = wv.L / wv.N
    Mm = float(np.sum(e * (1.0 + Ce)) * da)
    Kk = float(0.5 * wv.F ** 2 * np.sum(e * Ce) * da)
    Vv = float(0.5 * np.sum(e * e * (1.0 + Ce)) * da)
    rep["integrals"] = dict(mass_over_h2=Mm, kinetic_over_rho_g_h3=Kk, potential_over_rho_g_h3=Vv, energy_over_rho_g_h3=Kk + Vv,
                            impulse_over_rho_sqrtg_h52=wv.F * Mm, starr_V_minus_F2m1_M_over_3=Vv - (wv.F ** 2 - 1.0) * Mm / 3.0,
                            mass_m2_per_m=Mm * H0 ** 2, energy_MJ_per_m=(Kk + Vv) * 1000.0 * G * H0 ** 3 / 1e6,
                            note="KE = ½F²∫ηC{η}dα、PE = ½∫η²(1+C{η})dα（Dutykh & Clamond 2014 §2.2）")
    say("M %.10f  K %.10f  V %.10f  Starr %.2e" % (Mm, Kk, Vv, rep["integrals"]["starr_V_minus_F2m1_M_over_3"]))

    # 7. GN（§5.1 の式）との差
    xq = X0 + np.linspace(-98.345, 224.655, 2585)
    eT = wv.eta(xq)
    eG, uG1, _, CG = gn_fields(xq, 0.0)
    half = 0.5 * wv.a_over_h * H0
    def halfwidth(xx, ee):
        i = np.where(ee >= half)[0]
        return float(xx[i[-1]] - xx[i[0]])
    probes = []
    for dxp in (-34.0, -17.0, -8.5, 0.0, 8.5, 17.0, 34.0):
        xi = X0 + dxp
        et = float(wv.eta(np.array([xi]))[0])
        eg, _, _, _ = gn_fields(np.array([xi]), 0.0)
        for zz_ in (-17.0, -12.75, -8.5, -4.25, 0.0, round(et, 3) - 0.01):
            if zz_ > et:
                continue
            ut, wt = wv.velocity(np.array([xi]), np.array([zz_]))
            _, ug, wg, _ = gn_fields(np.array([xi]), np.array([zz_]))
            probes.append(dict(x=xi, x_minus_x0=dxp, z=zz_, eta_tanaka=et, eta_gn=float(eg[0]),
                               u_tanaka=float(ut[0]), w_tanaka=float(wt[0]), u_gn=float(ug[0]), w_gn=float(wg[0])))
    zz0 = np.linspace(-17.0, wv.a_over_h * H0 - 1e-6, 400)
    uc, wc = wv.velocity(np.full_like(zz0, X0), zz0)
    # w の最大（頂の前）
    xw = X0 + np.linspace(0.5, 40.0, 160)
    ew = wv.eta(xw)
    _, ww = wv.velocity(xw, ew - 1e-9)
    eg2, _, wg2, _ = gn_fields(xw, ew - 1e-9)
    rep["vs_GN"] = dict(
        F_tanaka=wv.F, F_GN=CG / s, c_tanaka=wv.c, c_GN=CG,
        eta_max_abs_diff_m=float(np.max(np.abs(eT - eG))), eta_diff_at=float(xq[np.argmax(np.abs(eT - eG))] - X0),
        half_amplitude_width_tanaka_m=halfwidth(xq, eT), half_amplitude_width_gn_m=halfwidth(xq, eG),
        mass_tanaka_m2=float(np.sum(eT) * (xq[1] - xq[0])), mass_gn_m2=float(np.sum(eG) * (xq[1] - xq[0])),
        eta_at_x0_minus_5p785h0_tanaka_m=float(wv.eta(np.array([0.0]))[0]), eta_at_x0_minus_5p785h0_gn_m=float(gn_fields(np.array([0.0]), 0.0)[0][0]),
        u_at_x0_wall_bed_tanaka_m_s=float(wv.velocity(np.array([0.0]), np.array([-17.0]))[0][0]),
        u_crest_bed_tanaka=float(uc[0]), u_crest_surface_tanaka=float(uc[-1]), u_crest_mid_tanaka=float(np.interp(-8.5, zz0, uc)),
        u_crest_gn=float(uG1[np.argmin(np.abs(xq - X0))]),
        w_surface_max_tanaka=float(np.max(ww)), w_surface_max_tanaka_at=float(xw[np.argmax(ww)] - X0),
        w_surface_max_gn=float(np.max(wg2)), w_surface_max_gn_at=float(xw[np.argmax(wg2)] - X0),
        probes=probes)
    say("GN: max|deta| %.3f m  halfwidth T %.2f GN %.2f m  u crest bed/mid/surf %.3f/%.3f/%.3f GN %.3f" % (
        rep["vs_GN"]["eta_max_abs_diff_m"], rep["vs_GN"]["half_amplitude_width_tanaka_m"], rep["vs_GN"]["half_amplitude_width_gn_m"],
        uc[0], rep["vs_GN"]["u_crest_mid_tanaka"], uc[-1], rep["vs_GN"]["u_crest_gn"]))

    # 8. 尾根の式の確かめ（本文の値。g46_common.bed_z と同じ式をここで書いた）
    def depth(xp_, yp_, k_=0.25):
        return 1.0 - max(xp_ - 5.225, 0.0) / np.cosh(k_ * yp_) ** 2 / 15.0
    rep["ridge_text_check"] = dict(depth_x19_y0=depth(19.0, 0.0), slope_y2=float(1 / np.cosh(0.5) ** 2 / 15),
                                   slope_y4=float(1 / np.cosh(1.0) ** 2 / 15), paper=dict(depth_x19=0.082, slope_y2=0.052, slope_y4=0.028))

    # 9. 尾根の上の初めの食い違い（解は平らな海底の解。x' ≥ 5.225 の真ん中の断面では海底が 1:15 で上がるので、海底を通る流れが残る）
    xb = np.arange(5.225 * H0, 160.0 + 1e-9, 0.5)
    zb = -H0 + (xb - 5.225 * H0) / 15.0
    ub, wb = wv.velocity(xb, zb)
    mis = wb - ub / 15.0                                   # 海底に直角な流れ ∝ w − u ∂z_b/∂x（真ん中の断面）
    im = int(np.argmax(np.abs(mis)))
    rep["ridge_toe_mismatch_t0"] = dict(
        max_abs_w_minus_u_slope_m_s=float(np.abs(mis[im])), at_x=float(xb[im]), u_bed_there=float(ub[im]), w_there=float(wb[im]),
        note="t = 0 に x 88.8〜160 m の真ん中の断面の海底で、海底を通る流れ w − u/15（m/s）。解は平らな海底の厳密な解で、"
             "頂 x0' 5.785 は尾根の始まり 5.225 の先なので、波の前半は勾配の上にある（GG06 と同じ置き方）")
    say("ridge mismatch max %.3f m/s at x %.1f (u %.3f)" % (float(np.abs(mis[im])), float(xb[im]), float(ub[im])))
    rep["summary"] = dict(
        a_over_h=wv.a_over_h, F=wv.F, c_m_s=wv.c, crest_x_m=X0, h0_m=H0,
        F_digits_note="F の確かさ 1e-13 の桁（同じ F で解き直した a の差 1.4e-13、文献の 3 点を 1e-14〜3e-13 で写す）",
        literature_max_abs_a_diff=max(abs(r["diff"]) for r in rl),
        bernoulli_residual_inf=rep["surface_conditions"]["bernoulli_residual_inf"],
        kinematic_residual_inf_m_s=rep["interior_checks"]["kinematic_residual_inf_m_s"],
        flux_identity_rel_inf=rep["interior_checks"]["flux_rel_inf"],
        starr_identity=rep["integrals"]["starr_V_minus_F2m1_M_over_3"],
        u_crest_bed_mid_surface_m_s=[rep["vs_GN"]["u_crest_bed_tanaka"], rep["vs_GN"]["u_crest_mid_tanaka"], rep["vs_GN"]["u_crest_surface_tanaka"]],
        u_crest_gn_m_s=rep["vs_GN"]["u_crest_gn"],
        half_amplitude_width_tanaka_gn_m=[rep["vs_GN"]["half_amplitude_width_tanaka_m"], rep["vs_GN"]["half_amplitude_width_gn_m"]])
    rep["sources"] = [
        "Clamond & Dutykh 2013, Fast accurate computation of the fully nonlinear solitary surface gravity waves, Computers & Fluids 84, 35-38, arXiv:1212.0289（式・表 1）",
        "Dutykh & Clamond 2014, Efficient computation of steady solitary gravity waves, Wave Motion 51, 86-99, arXiv:1302.1812（§2.2 の積分の式、§3.3 の値）",
        "Grimshaw 1971 / Fenton 1972 の 3 次の級数 F² = 1 + ε − ε²/20 − 3ε³/70（記憶。ネットで確かめていない）",
        "Guyenne & Grilli 2006 の初めの速さ 1.25（BigWave_Recipes_ja.md §5.2 の値。本文はこの役では開けなかった）"]
    rep["seconds"] = time.time() - t0
    rep["made_by"] = "g46_solitary.py --check (2026-10-12)"
    if out_json:
        os.makedirs(os.path.dirname(out_json), exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    return rep, wv


def grid_interp_check(path, wave, n=4000, seed=46):
    """表の npz を双線形で補った値と厳密な値を、水の中の乱数の点で比べる（m/s）。
    fill_top：場面の読み手（g46_tanklib.PYSOP）と同じく、水面より上の NaN を列のいちばん上の値で埋めた u・w。
    ext：u_ext・w_ext（水面より上を水面の厳密な値で埋めた物）。"""
    d = np.load(path)
    xs, zs = d["x"], d["z"]
    U = np.array(d["u"], dtype=np.float64)
    W = np.array(d["w"], dtype=np.float64)
    for A in (U, W):
        for j in range(A.shape[1]):
            col = A[:, j]
            ok = np.isfinite(col)
            if ok.any():
                i = np.where(ok)[0]
                col[i[-1] + 1:] = col[i[-1]]
    rng = np.random.default_rng(seed)
    xp = rng.uniform(1.0, 320.0, n)
    ep = wave.eta(xp)
    zp = -H0 + rng.uniform(0.0, 1.0, n) * (ep + H0)

    def bil(A):
        fx = (xp - xs[0]) / (xs[1] - xs[0])
        fz = (zp - zs[0]) / (zs[1] - zs[0])
        i = np.clip(np.floor(fx).astype(int), 0, len(xs) - 2)
        j = np.clip(np.floor(fz).astype(int), 0, len(zs) - 2)
        tx = fx - i
        tz = fz - j
        return ((1 - tx) * (1 - tz) * A[j, i] + tx * (1 - tz) * A[j, i + 1] + (1 - tx) * tz * A[j + 1, i] + tx * tz * A[j + 1, i + 1])

    ue, we = wave.velocity(xp, zp)
    near = zp > ep - 0.5
    out = dict(path=path, dx=float(xs[1] - xs[0]), dz=float(zs[1] - zs[0]), points=int(n))
    for tag, (UU, WW) in (("fill_top", (U, W)), ("ext", (np.asarray(d["u_ext"]), np.asarray(d["w_ext"])))):
        du = np.abs(bil(UU) - ue)
        dw = np.abs(bil(WW) - we)
        out[tag] = dict(u_err_inf_m_s=float(du.max()), w_err_inf_m_s=float(dw.max()),
                        u_err_rms_m_s=float(np.sqrt(np.mean(du ** 2))), w_err_rms_m_s=float(np.sqrt(np.mean(dw ** 2))),
                        deep_u_err_inf=float(du[~near].max()), deep_w_err_inf=float(dw[~near].max()))
    out["note"] = "双線形で補った値 − 厳密な値。deep は水面から 0.5 m より深い点"
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--grid", action="store_true")
    ap.add_argument("--dx", type=float, default=0.25)
    ap.add_argument("--dz", type=float, default=0.25)
    ap.add_argument("--out", default=GRID_DEFAULT)
    a = ap.parse_args()
    wv = None
    if a.check:
        rep, wv = run_checks()
        wv.save(cache_path(wv.a_over_h if abs(wv.a_over_h - A_OVER_H) > 1e-9 else A_OVER_H))
    if wv is None:
        wv = get_wave()
    print("F %.15f  c %.6f m/s  a/h %.15f" % (wv.F, wv.c, wv.a_over_h))
    if a.grid:
        t1 = time.time()
        xs = np.arange(0.0, 328.0 + 1e-9, a.dx)
        zs = np.arange(-H0, 12.25 + 1e-9, a.dz)
        p = wv.write_grid(a.out, xs, zs)
        print("wrote", p, "shape", (len(zs), len(xs)), "%.1f s" % (time.time() - t1))
        gi = grid_interp_check(p, wv)
        print("grid bilinear vs exact:", json.dumps(gi))
        if os.path.exists(CHECK_JSON):
            with open(CHECK_JSON, encoding="utf-8") as f:
                rep = json.load(f)
            rep["grid_file"] = gi
            with open(CHECK_JSON, "w", encoding="utf-8") as f:
                json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
