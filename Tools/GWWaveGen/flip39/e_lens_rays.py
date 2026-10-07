# -*- coding: utf-8 -*-
"""FLIP39 E3 の海底の盛り上がり（屈折のレンズ）の設計：線形の波線（周期 T）で、焦点の列（z = −120 m の壁＝対称の面）の上に
波線が集まる x を見積もる。推定（線形の理論）であり、FLIP の測った値ではない。"""
import sys, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_lin import kdisp
G = 9.80665
Lz = 240.0; zw = -120.0


def depth(x, z, mound):
    h0, hr, n, xs0 = 60.0, 26.0, 4.0, 420.0
    y = -h0 + np.maximum(0.0, x - xs0) / n
    y = np.minimum(y, -hr)
    if mound:
        mx, mz, sx, sz, d = mound
        gg = np.exp(-((x - mx) / sx) ** 2 - ((z - mz) / sz) ** 2)
        y = np.maximum(y, -h0 + (h0 - d) * gg)
    return -y


def trace(T, mound, x0=150.0, xend=600.0, dz0=0.5):
    om = 2 * np.pi / T
    xg = np.arange(100.0, 650.0, 1.0); zg = np.arange(-480.0, 240.0, 1.0)   # 壁の鏡を含めて広げた海（z=-120 を中心）
    X, Z = np.meshgrid(xg, zg)
    zz = Z.copy()
    # 鏡：z=-120 と z=+120 の壁を鏡とする周期 480 m の折り返し
    u = np.mod(zz + 120.0, 480.0); zz = np.where(u <= 240.0, u, 480.0 - u) - 120.0
    C = om / kdisp(om, depth(X, zz, mound))
    dCx = np.gradient(C, xg, axis=1); dCz = np.gradient(C, zg, axis=0)

    def it(F, x, z):
        fx = np.clip(x - xg[0], 0, len(xg) - 1.001); fz = np.clip(z - zg[0], 0, len(zg) - 1.001)
        i = fx.astype(int); j = fz.astype(int); ax = fx - i; az = fz - j
        return F[j, i] * (1 - ax) * (1 - az) + F[j, i + 1] * ax * (1 - az) + F[j + 1, i] * (1 - ax) * az + F[j + 1, i + 1] * ax * az
    z = np.arange(-360.0, 120.0, dz0); x = np.full_like(z, x0); th = np.zeros_like(z)
    stations = np.arange(200.0, xend + 1, 5.0)
    zs_at = {s: np.full_like(z, np.nan) for s in stations}
    ds = 1.0
    for _ in range(800):
        c = it(C, x, z); cx = it(dCx, x, z); cz = it(dCz, x, z)
        dth = (np.sin(th) * cx - np.cos(th) * cz) / c
        xm = x + 0.5 * ds * np.cos(th); zm = z + 0.5 * ds * np.sin(th); thm = th + 0.5 * ds * dth
        c2 = it(C, xm, zm); cx2 = it(dCx, xm, zm); cz2 = it(dCz, xm, zm)
        dth2 = (np.sin(thm) * cx2 - np.cos(thm) * cz2) / c2
        xn = x + ds * np.cos(thm); zn = z + ds * np.sin(thm)
        for s in stations:
            cr = (x < s) & (xn >= s)
            if cr.any():
                f = (s - x[cr]) / np.maximum(xn[cr] - x[cr], 1e-9)
                zs_at[s][cr] = z[cr] + f * (zn[cr] - z[cr])
        x, z, th = xn, zn, th + ds * dth2
        if (x > xend + 2).all():
            break
    # 焦点の列（|z+120| < 10 m）の波線の密度の比（線形の屈折の係数の 2 乗の目安）
    out = []
    for s in stations:
        zz2 = zs_at[s]
        n_in = np.sum(np.abs(zz2 - zw) < 10.0)
        n0 = 20.0 / dz0
        out.append((float(s), float(n_in / n0)))
    return out


if __name__ == "__main__":
    res = {}
    for T in (12.0, 9.0, 16.0):
        for mound in (None, (300, -120, 70, 90, 30), (320, -120, 60, 100, 32), (340, -120, 60, 90, 30), (300, -120, 80, 110, 28), (280, -120, 60, 80, 30)):
            r = trace(T, mound)
            k = max(r, key=lambda q: q[1] if q[0] <= 600 else 0)
            v540 = [q for q in r if q[0] == 540.0][0][1]; v520 = [q for q in r if q[0] == 520.0][0][1]
            print("T %.0f mound %s: peak Kr2 %.2f at x %.0f | at 520 %.2f at 540 %.2f" % (T, mound, k[1], k[0], v520, v540))
            res["T%.0f_%s" % (T, mound)] = r
    json.dump(res, open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/lens_rays.json", "w"), indent=0)
