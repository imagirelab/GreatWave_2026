# -*- coding: utf-8 -*-
"""FLIP39 D1：hot start の初めの波を、平らな海（水深 h0）の線形の式だけで進めたら頂の高さがどう変わるか（分散だけの効果）。
FLIP の z=0 の頂と並べる。z は滑る壁（Neumann）なので余弦の級数、x は FFT（左右に余白を足して折り返しを避ける）。"""
import sys, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *
from scipy.fft import dct, idct


def linear_flat(parms, tlist, dx=2.0, Lpad=4096 * 2):
    T = Tank(parms)
    Lz = parms["Lz"]; h = parms["h0"]
    nx = int(Lpad / dx)
    x = (np.arange(nx) - nx // 4) * dx           # -2048 .. 6144 m
    nz = int(Lz / 2.0)
    z = -Lz / 2 + (np.arange(nz) + 0.5) * 2.0     # セル中心（DCT-II の格子）
    X, Z = np.meshgrid(x, z)
    eta0, phi0 = T.surface_flat(X, Z)
    kx = 2 * np.pi * np.fft.fftfreq(nx, dx)
    kz = np.pi * np.arange(nz) / Lz
    K = np.sqrt(kx[None, :] ** 2 + kz[:, None] ** 2)
    om = np.sqrt(G * K * np.tanh(K * h))
    A = np.fft.fft(dct(eta0, type=2, axis=0, norm="ortho"), axis=1)
    B = np.fft.fft(dct(phi0, type=2, axis=0, norm="ortho"), axis=1)
    fac = np.where(om > 1e-9, K * np.tanh(K * h) / np.maximum(om, 1e-9), 0.0)
    out = []
    for t in tlist:
        Et = A * np.cos(om * t) + fac * B * np.sin(om * t)
        e = idct(np.real(np.fft.ifft(Et, axis=1)), type=2, axis=0, norm="ortho")
        out.append(e)
    return x, z, np.array(out)


if __name__ == "__main__":
    for rid in ["R18_X30L120LG_H39", "R08_L120_H33"]:
        rj, hf = load_run(rid)
        p = rj["parms"]
        tl = np.arange(0, 7.01, 0.5)
        x, z, E = linear_flat(p, tl)
        iz = np.argmin(abs(z))
        ifl = np.argmin(abs(hf["z"]))
        T = Tank(p)
        e0, _ = T.surface_flat(hf["x"], 0 * hf["x"])
        m = hf["x"] < 400
        print(rid, "t=0 での式と FLIP の差（x<400, z=0）：最大 %.2f m" % np.nanmax(abs(e0[m] - hf["eta"][0, ifl][m])))
        for i, t in enumerate(tl):
            j = np.argmin(abs(x - 0)); sel = (x > 100) & (x < 1500)
            row = E[i, iz][sel]; xx = x[sel]; k = np.argmax(row)
            f = np.argmin(abs(hf["t"] - t)); r2 = hf["eta"][f, ifl]; k2 = np.nanargmax(r2)
            print("  t=%.1f 線形・平ら：頂 %.2f m @x %.0f   FLIP：頂 %.2f m @x %.0f" % (t, row[k], xx[k], r2[k2], hf["x"][k2]))
