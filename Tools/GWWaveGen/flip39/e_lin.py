# -*- coding: utf-8 -*-
"""FLIP39 E：集まる波の群の線形の設計（numpy）。流体の計算ではない。
海底は FLIP37 の岩棚の並び（沖 60 m、斜面 1:4 が xs0 から、岩棚 hr）か平らな海。
成分 i の位相 Θi(x) − Θi(xf) − ωi (t − tf)（Θ はその場の水深の波数を x で積む＝WKB）、振幅は線形の浅水係数。
向きの広がりは、幅 W の滑る壁の水路の固有の形 cos(nπ(z − zf)/W)（zf は壁＝対称の面）で入れる（kz は保たれる＝Snell）。
"""
import numpy as np, json
G = 9.80665


def kdisp(om, h):
    om = np.asarray(om, float); h = np.asarray(h, float)
    k = om * om / G / np.sqrt(np.tanh(om * om * h / G))
    for _ in range(40):
        th = np.tanh(k * h)
        k = k - (G * k * th - om * om) / (G * th + G * k * h * (1 - th * th))
    return k


def cg(om, h):
    k = kdisp(om, h); kh = k * h
    return 0.5 * (1 + 2 * kh / np.sinh(2 * kh)) * om / k


def kshoal(om, h):
    k = kdisp(om, h); kh = k * h
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh))
    return 1.0 / np.sqrt(n * np.tanh(kh))


class Bed:
    """海底（焦点の列の上）。mound＝(x 中心, 広がり sx, 頂の水深 d)：焦点の列の上を通る盛り上がり（E3 のレンズ。e_tank の lg1 と同じ式の z = 中心の値）。"""
    def __init__(self, h0=60.0, hr=26.0, slope_n=4.0, xs0=420.0, flat=False, mound=None):
        self.h0, self.hr, self.n, self.xs0, self.flat, self.mound = h0, hr, slope_n, xs0, flat, mound

    def h(self, x):
        x = np.asarray(x, float)
        if self.flat:
            y = np.full_like(x, -self.h0)
        else:
            y = -self.h0 + np.maximum(0.0, x - self.xs0) / self.n
            y = np.minimum(y, -self.hr)
        if self.mound is not None:
            mx, sx, d = self.mound
            y = np.maximum(y, -self.h0 + (self.h0 - d) * np.exp(-((x - mx) / sx) ** 2))
        return np.maximum(-y, 0.5)


def theta_x(bed, x, om, kz=0.0, nx=4000):
    """∫ kx dx を 0 から x まで（x は配列）。"""
    xs = np.linspace(0, max(np.max(x), 1.0), nx)
    kk = kdisp(om, bed.h(xs))
    kx = np.sqrt(np.maximum(kk * kk - kz * kz, 1e-12))
    cum = np.concatenate([[0], np.cumsum(0.5 * (kx[1:] + kx[:-1]) * np.diff(xs))])
    return np.interp(x, xs, cum)


def make_components(Tc, f_lo, f_hi, nf, A_f, bed, sigma_deg=0.0, W=240.0, spectrum="flat"):
    """成分の表：om, a（焦点の沖の水深での振幅）, n（横の形）, kz。sum(a) = A_f（線形で焦点の山）。"""
    fc = 1.0 / Tc
    f = np.linspace(fc * f_lo, fc * f_hi, nf)
    om = 2 * np.pi * f
    k0 = kdisp(om, bed.h0)
    if spectrum == "flat":
        ai = np.ones(nf)
    else:
        raise ValueError
    rows = []
    for i in range(nf):
        if sigma_deg <= 0:
            rows.append((om[i], ai[i], 0, 0.0)); continue
        nmax = int(np.floor(W * k0[i] / np.pi))
        ws = []
        for n in range(nmax + 1):
            kz = n * np.pi / W
            th = np.arcsin(min(kz / k0[i], 1.0))
            if np.degrees(th) > 3 * sigma_deg or np.degrees(th) > 75:
                continue
            # 形 n≥1 は ±θ の二つを合わせた cos の形。重みは正規分布 × 角度の間隔（Δθ = (π/W)/(k cos θ)）
            dth = (np.pi / W) / (k0[i] * max(np.cos(th), 0.2))
            w = np.exp(-0.5 * (np.degrees(th) / sigma_deg) ** 2) * dth * (2.0 if n > 0 else 1.0)
            ws.append((n, kz, w))
        sw = sum(w for _, _, w in ws)
        for n, kz, w in ws:
            rows.append((om[i], ai[i] * w / sw, n, kz))
    C = np.array(rows)
    a = C[:, 1] * A_f / C[:, 1].sum()
    return dict(om=C[:, 0], a=a, n=C[:, 2].astype(int), kz=C[:, 3], f=f, Tc=Tc, f_lo=f_lo, f_hi=f_hi, A_f=A_f, sigma_deg=sigma_deg, W=W)


def eta_xt(comp, bed, x, t, xf, tf, z=None, zf=-120.0, ramp=None):
    """η(x, t)（z を与えれば η(z, x, t) の z の 1 点）。ramp(t) は始めのなだらかさ。"""
    x = np.asarray(x, float); t = np.asarray(t, float)
    out = np.zeros((len(t), len(x)))
    for om, a, n, kz in zip(comp["om"], comp["a"], comp["n"], comp["kz"]):
        th = theta_x(bed, x, om, kz) - theta_x(bed, np.array([xf]), om, kz)[0]
        amp = a * kshoal(om, bed.h(x)) / kshoal(om, bed.h0)
        zz = 1.0 if z is None else np.cos(kz * (z - zf))
        out += zz * amp[None, :] * np.cos(th[None, :] - om * (t[:, None] - tf))
    if ramp is not None:
        pass
    return out


def steepness_S(comp, h):
    return float(np.sum(comp["a"] * kdisp(comp["om"], h)))
