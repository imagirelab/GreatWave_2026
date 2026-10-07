# -*- coding: utf-8 -*-
"""FLIP39 E：長い板の水槽（E1L）の線形の見込み。焦点までの距離を延ばすと、帯を出た所の頂と、途中の最も高い頂に対する焦点の頂の比がどう変わるか。推定。"""
import sys, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_lin import Bed, make_components, eta_xt, cg
out = []
for shift in (0.0, 300.0, 600.0):
    bed = Bed(xs0=420.0 + shift)
    xf = 556.0 + shift
    comp = make_components(12.0, 0.55, 1.6, 32, 1.0, bed)
    tmax = (xf - 150.0) / cg(comp["om"], 60.0).min() + 16.0
    tf = float(np.ceil(tmax / 5.0) * 5.0)
    t = np.arange(0.0, tf + 2.0, 0.5)
    x = np.arange(150.0, xf + 60.0, 4.0)
    E = eta_xt(comp, bed, x, t, xf, tf)
    ex = E[:, x <= 182].max()
    tl = t[:, None] * np.ones_like(E)
    early = E[t < tf - 10.0].max()
    fin = E.max()
    out.append(dict(shift=shift, xf=xf, tf=tf, exit_max=float(ex), early_max=float(early), focus=float(fin), m1=float(fin / ex), m1s=float(fin / early)))
    print(out[-1], flush=True)
json.dump(out, open(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/lin_long_tank.json", "w"), indent=1)
