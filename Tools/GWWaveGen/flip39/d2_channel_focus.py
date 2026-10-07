# -*- coding: utf-8 -*-
"""FLIP39 D2：両側が滑る壁の水路（幅 W）で、線形の重ね合わせだけでどれだけ一点に集められるかの見積もり。
流体の計算ではない。平らな海（水深 h）、線形、砕けなし、粘りなし。

焦点は壁の上（z = -W/2、壁を対称の面に使う）か、水路の中央（z = 0）。
横の形は cos(nπ(z+W/2)/W)（滑る壁の固有の形）。周波数ごとに伝わる形だけを使う。
比 = 焦点の線形の山（成分の振幅の和）/ 造波の線（x = 0）で、全時刻・全 z の最も高い山。
出力：G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/channel_focus.json
"""
import json
import numpy as np

G = 9.81
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/channel_focus.json"


def kdisp(om, h):
    k = om * om / G / np.sqrt(np.tanh(om * om * h / G))
    for _ in range(50):
        th = np.tanh(k * h)
        f = G * k * th - om * om
        df = G * th + G * k * h * (1 - th * th)
        k = k - f / df
    return k


def case(Tc, h, W, xf, bw, focus="wall", sigma_deg=None, nf=48):
    fc = 1.0 / Tc
    if bw > 0:
        f = np.linspace(fc * (1 - bw / 2), fc * (1 + bw / 2), nf)
    else:
        f = np.array([fc])
    zf = -W / 2 if focus == "wall" else 0.0
    comps = []  # (a, k, kx, n, om)
    for fi in f:
        om = 2 * np.pi * fi
        k = kdisp(om, h)
        nmax = int(np.floor(W * k / np.pi))
        for n in range(nmax + 1):
            kz = n * np.pi / W
            kx = np.sqrt(max(k * k - kz * kz, 0.0))
            th = np.degrees(np.arcsin(min(kz / k, 1.0)))
            if focus == "centre" and n % 2 == 1:
                continue  # 中央が節の形は中央の焦点に寄与しない
            if sigma_deg is not None and th > 3 * sigma_deg:
                continue
            w = 1.0 if sigma_deg is None else np.exp(-0.5 * (th / sigma_deg) ** 2)
            if sigma_deg == 0:
                w = 1.0 if n == 0 else 0.0
            # 横の形の焦点での値（壁で 1、中央で cos(nπ/2)=±1）を 1 にそろえる
            sgn = np.cos(n * np.pi * (zf + W / 2) / W)
            comps.append((w * sgn, k, kx, n, om))
    a = np.array([c[0] for c in comps])
    kx = np.array([c[2] for c in comps])
    n = np.array([c[3] for c in comps])
    om = np.array([c[4] for c in comps])
    amp = np.abs(a)
    A = amp.sum()
    a = a / A  # 焦点の山 = 1
    z = np.linspace(-W / 2, W / 2, 121)
    Z = np.cos(np.outer(n, np.pi * (z + W / 2) / W))  # (ncomp, nz)
    cgmin = 3.0
    t = np.arange(-(xf / cgmin + 4 * Tc), 2 * Tc, Tc / 24)
    # x = 0 の η(z, t)
    ph = kx[:, None] * (0 - xf) - om[:, None] * t[None, :]  # (ncomp, nt)
    eta = np.einsum("c,cz,ct->zt", a, Z, np.cos(ph))
    mx0 = np.abs(eta).max()
    # 確かめ：焦点で 1 になるか
    chk = float((a * np.cos(n * np.pi * (zf + W / 2) / W)).sum())
    return dict(Tc=Tc, h=h, W=W, xf=xf, bw=bw, focus=focus, sigma_deg=sigma_deg,
                n_components=int(len(a)), modes_used=sorted(set(int(v) for v in n)),
                focus_value_check=round(chk, 3), ratio_focus_over_wavemaker_max=round(float(1.0 / mx0), 3))


out = []
for Tc in (10, 12, 14):
    for h in (60, 80):
        for W in (240.0, 480.0):
            for focus in ("wall", "centre"):
                for bw in (0.0, 0.6, 1.0):
                    for sig in (0, 15, 30, None):
                        out.append(case(Tc, h, W, 450.0, bw, focus, sig))
with open(OUT, "w", encoding="utf-8") as fo:
    json.dump({"note": "線形の見積もり。sigma_deg=0 は一方向、None は伝わる形を同じ重みで全部。xf=450 m（造波の線から）",
               "cases": out}, fo, ensure_ascii=False, indent=1)
for r in out:
    if r["h"] == 80:
        print(r["Tc"], r["W"], r["focus"], r["bw"], r["sigma_deg"], r["modes_used"], r["ratio_focus_over_wavemaker_max"])
