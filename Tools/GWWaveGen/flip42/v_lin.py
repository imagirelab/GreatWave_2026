# -*- coding: utf-8 -*-
"""FLIP41 確かめ（verify）：線形の波の理論の式（ほかの v_*.py が使う）。
g は Houdini の Gravity DOP の既定値 9.80665 m/s²（計算と同じ値で比べる）。
- 分散の関係 ω² = g k tanh(kh)（Dean & Dalrymple 1991）
- 群速度 cg = c (1 + 2kh/sinh 2kh)/2
- 線形の浅水係数 Ks = sqrt(cg0/cg)
- ピストン造波の Biésel の比 H/S = 2(cosh 2kh − 1)/(sinh 2kh + 2kh)
- Stokes 2 次の拘束された 2 倍の波の振幅 a2 = k a² cosh(kh)(2 + cosh 2kh)/(4 sinh³ kh)
- Stokes 3 次の振幅による速さの補正（深い海の極限 (ka)²/2。有限の水深は Fenton 1985 の C2 の式）
"""
import numpy as np

G = 9.80665


def k_of_omega(om, h):
    om = float(om)
    if h <= 0:
        return om * om / G
    k = max(om * om / G, om / np.sqrt(G * h))
    for _ in range(100):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h / np.cosh(k * h) ** 2
        dk = f / df
        k -= dk
        if abs(dk) < 1e-14 * k:
            break
    return float(k)


def props(T, h):
    om = 2 * np.pi / T
    k = k_of_omega(om, h)
    c = om / k
    kh = k * h
    n = 0.5 * (1 + 2 * kh / np.sinh(2 * kh)) if kh < 300 else 0.5
    return dict(T=T, h=h, om=om, k=k, L=2 * np.pi / k, c=c, cg=c * n, kh=kh)


def ks(T, h0, h1):
    return float(np.sqrt(props(T, h0)["cg"] / props(T, h1)["cg"]))


def biesel_HS(kh):
    return float(2 * (np.cosh(2 * kh) - 1) / (np.sinh(2 * kh) + 2 * kh))


def stokes2_a2(a, k, h):
    kh = k * h
    return float(k * a * a / 4 * np.cosh(kh) * (2 + np.cosh(2 * kh)) / np.sinh(kh) ** 3)


def stokes3_dc(a, k, h):
    """3 次の速さの補正 Δc/c（Fenton 1985 の C2、ε = ka）。S = sech(2kh)。"""
    kh = k * h
    S = 1.0 / np.cosh(2 * kh)
    C2 = (2 + 7 * S * S) / (4 * (1 - S) ** 2)
    return float((k * a) ** 2 * C2)


def bed_profile(x, h0, xs0, slope_n, h1):
    """平らな沖 h0 → x ≥ xs0 で 1:slope_n で上る → 水深 h1 で平ら。水深を返す。"""
    x = np.asarray(x, float)
    if slope_n <= 0:
        return np.full_like(x, h0)
    return np.maximum(h0 - np.maximum(0.0, x - xs0) / slope_n, h1)


if __name__ == "__main__":
    for T, h in [(5, 25), (7, 25), (10, 25), (20, 25), (7, 10), (7, 5), (10, 8), (12, 60), (12, 26), (7, 60), (4, 25), (7, 40), (7, 8), (10, 40)]:
        p = props(T, h)
        print("T %5.1f h %5.1f  L %7.2f  kh %5.2f  c %6.3f  cg %6.3f  H/S %.3f" % (T, h, p["L"], p["kh"], p["c"], p["cg"], biesel_HS(p["kh"])))
    print("C2 deep", stokes3_dc(0.1, 1, 100) / 0.01)
