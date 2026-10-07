# -*- coding: utf-8 -*-
"""FLIP39 D1：海底の形による屈折の集まり（線形の波の向きの線＝波線）。周期 T の波を x=300 m から入れ、
波線の間隔の変化から屈折の係数 Kr = sqrt(b0/b) を出す。両側の滑る壁（z=±Lz/2）は鏡として跳ね返す。
推定（線形の理論）であり、FLIP の測った値ではない。"""
import sys, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *


def fold(z, Lz):
    """滑る壁 z=±Lz/2 を鏡とした、周期 2Lz の折り返し。"""
    u = np.mod(z + Lz / 2, 2 * Lz)
    return np.where(u <= Lz, u, 2 * Lz - u) - Lz / 2


def cfield(tank, T, x, z):
    om = 2 * np.pi / T
    X, Z = np.meshgrid(x, z)
    h = tank.depth(X, fold(Z, tank.p["Lz"]))
    return om / kdisp(om, h)            # 位相の速さ（z, x）


def trace(tank, T, theta_deg, x0=300.0, dz0=0.25, ds=1.0, xend=640.0):
    Lz = tank.p["Lz"]
    ext = 3 * Lz
    xg = np.arange(250.0, 700.0, 1.0); zg = np.arange(-Lz / 2 - ext, Lz / 2 + ext + 0.5, 1.0)
    C = cfield(tank, T, xg, zg)
    dCx = np.gradient(C, xg, axis=1); dCz = np.gradient(C, zg, axis=0)

    def interp(F, x, z):
        fx = np.clip((x - xg[0]) / 1.0, 0, len(xg) - 1.001); fz = np.clip((z - zg[0]) / 1.0, 0, len(zg) - 1.001)
        i = fx.astype(int); j = fz.astype(int); ax = fx - i; az = fz - j
        return (F[j, i] * (1 - ax) * (1 - az) + F[j, i + 1] * ax * (1 - az) + F[j + 1, i] * (1 - ax) * az + F[j + 1, i + 1] * ax * az)

    z = np.arange(-Lz / 2 - ext + 40 + dz0 / 2, Lz / 2 + ext - 40, dz0)
    x = np.full_like(z, x0); th = np.full_like(z, np.radians(theta_deg))
    stations = np.arange(300.0, xend + 1, 10.0)
    rec = {float(s): None for s in stations}
    done = np.zeros_like(z, bool)
    zs_at = {float(s): np.full_like(z, np.nan) for s in stations}
    th_at = {float(s): np.full_like(z, np.nan) for s in stations}
    for it in range(4000):
        c = interp(C, x, z); cx = interp(dCx, x, z); cz = interp(dCz, x, z)
        dth = (np.sin(th) * cx - np.cos(th) * cz) / c
        xm = x + 0.5 * ds * np.cos(th); zm = z + 0.5 * ds * np.sin(th); thm = th + 0.5 * ds * dth
        c2 = interp(C, xm, zm); cx2 = interp(dCx, xm, zm); cz2 = interp(dCz, xm, zm)
        dth2 = (np.sin(thm) * cx2 - np.cos(thm) * cz2) / c2
        xn = x + ds * np.cos(thm); zn = z + ds * np.sin(thm); thn = th + ds * dth2
        # 壁は鏡：海底を折り返して広げた海で波線を進め、数える時に箱へ折り返す
        for s in stations:
            cross = (x < s) & (xn >= s)
            if cross.any():
                f = (s - x[cross]) / np.maximum(xn[cross] - x[cross], 1e-9)
                zs_at[float(s)][cross] = z[cross] + f * (zn[cross] - z[cross])
                th_at[float(s)][cross] = th[cross] + f * (thn[cross] - th[cross])
        x, z, th = xn, zn, thn
        if (x > xend + 2).all():
            break
    return (zs_at, th_at, np.radians(theta_deg)), dz0


def density_Kr(res, dz0, Lz, bin_m=6.0):
    """各 x の z の帯（bin_m）の中の波線の数 N と向き θ から、Kr² = (N/n0)·cosθ0/cosθ（波線に直角な間隔の比）。
    箱へ折り返して数える（鏡の像の波線も箱の中の同じ波の一部）。"""
    zs_at, th_at, th0 = res
    edges = np.arange(-Lz / 2, Lz / 2 + 1e-6, bin_m); zc = 0.5 * (edges[1:] + edges[:-1])
    n0 = bin_m / dz0
    out = {}
    for s, zz in zs_at.items():
        tt = th_at[s]; ok = np.isfinite(zz)
        zf = fold(zz[ok], Lz); tf = tt[ok]
        cnt, _ = np.histogram(zf, edges)
        cs, _ = np.histogram(zf, edges, weights=np.abs(np.cos(tf)))
        cmean = np.where(cnt > 0, cs / np.maximum(cnt, 1), 1.0)
        out[s] = np.sqrt(cnt / n0 * np.cos(th0) / cmean)
    return zc, out


if __name__ == "__main__":
    import json
    rj, _ = load_run("R18_X30L120LG_H39")
    for name, mod in [("R18（レンズ＋低い棚）", {}), ("R12（レンズ）", {"lg1_d": 0, "lg2_d": 0}), ("まっすぐ（レンズなし）", {"lg1_d": 0, "lg2_d": 0, "lens_A": 0, "lens_dh": 0})]:
        p = dict(rj["parms"]); p.update(mod); tk = Tank(p)
        for th in (0.0, 30.0, -30.0):
            res, dz0 = trace(tk, 14.0, th)
            zc, Kr = density_Kr(res, dz0, p["Lz"])
            i0 = np.argmin(abs(zc))
            print(name, th, " ".join("x%.0f:%.2f" % (s, Kr[s][i0]) for s in (420.0, 460.0, 500.0, 520.0, 540.0, 560.0)))
