# -*- coding: utf-8 -*-
"""FLIP39 D2：分散による集中で、水槽の中の最も高い山が時間とともにどう育つか（線形・一方向・平らな海の見積もり）。
流体の計算ではない。焦点の時刻 tf=0 の前の各時刻で、x 140〜806 m（造波の帯の外）の最も高い山を、焦点の線形の山（=1）に対する比で出す。
出力：G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/rise_time.json
"""
import json
import numpy as np
G = 9.81


def kdisp(om, h):
    k = om * om / G / np.sqrt(np.tanh(om * om * h / G))
    for _ in range(50):
        th = np.tanh(k * h)
        k = k - (G * k * th - om * om) / (G * th + G * k * h * (1 - th * th))
    return k


out = []
for Tc in (12, 14):
    for h in (80,):
        for bw in (0.6, 1.0):
            for xf_from_band in (400.0, 450.0):
                fc = 1 / Tc
                f = np.linspace(fc * (1 - bw / 2), fc * (1 + bw / 2), 96)
                a = np.ones_like(f) / len(f)
                om = 2 * np.pi * f
                k = kdisp(om, h)
                xb = 140.0
                xf = xb + xf_from_band
                x = np.arange(xb, 806.0, 1.0)
                ts = np.arange(-90.0, 0.01, 0.5)
                mx = []
                for t in ts:
                    eta = (a[:, None] * np.cos(k[:, None] * (x[None, :] - xf) - om[:, None] * t)).sum(0)
                    mx.append(float(eta.max()))
                mx = np.array(mx)
                def t_at(r):
                    i = np.where(mx >= r)[0]
                    return float(ts[i[0]]) if i.size else None
                out.append(dict(Tc=Tc, h=h, bw=bw, xf_from_band=xf_from_band,
                                max_crest_ratio_at_t=[[float(t), round(m, 3)] for t, m in zip(ts[::10], mx[::10])],
                                t_first_reach_0p6=t_at(0.6), t_first_reach_0p8=t_at(0.8), t_first_reach_0p9=t_at(0.9)))
json.dump({"note": "線形の見積もり。比は焦点の山=1。t は焦点の時刻からの秒（負は前）", "cases": out},
          open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/D2/rise_time.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in out:
    print(r["Tc"], r["bw"], r["xf_from_band"], "0.6:", r["t_first_reach_0p6"], "0.8:", r["t_first_reach_0p8"], "0.9:", r["t_first_reach_0p9"])
    print("   ", r["max_crest_ratio_at_t"])
