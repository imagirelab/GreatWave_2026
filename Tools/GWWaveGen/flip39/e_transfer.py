# -*- coding: utf-8 -*-
"""FLIP39 E：較正の計算（C1）の水面計で、成分の周波数ごとの振幅の比と位相の差（計算 ÷ 線形の見込み）を測る。py -3.10。
最小二乗で、各水面計の時系列を成分の周波数の cos・sin の和に当てはめる（成分の周波数は分かっている）。"""
import sys, json, os
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf, linear_eta, run_info, bed_of, focus_row

rd = sys.argv[1]
rj, cj = run_info(rd)
hf = load_hf(rd)
g = hf["grid"]; x = g["x0"] + g["dx"] * np.arange(hf["eta"].shape[2])
t = hf["t"] + float(rj["parms"].get("t_off", 0.0))
row = focus_row(hf, rj) - 0.423
bed = bed_of(rj, cj)
om = np.array(cj["om"]); a = np.array(cj["a"])
out = {}
for xg in (160.0, 200.0, 300.0, 400.0, 480.0, 520.0):
    i = int(np.argmin(np.abs(x - xg)))
    lin = linear_eta(cj, bed, [x[i]], t)[:, 0]
    sel = (t > 25.0) & np.isfinite(row[:, i])
    A = np.hstack([np.cos(np.outer(t[sel], om)), np.sin(np.outer(t[sel], om)), np.ones((sel.sum(), 1))])
    cs, *_ = np.linalg.lstsq(A, row[sel, i], rcond=None)
    cl, *_ = np.linalg.lstsq(A, lin[sel], rcond=None)
    n = len(om)
    zs = cs[:n] - 1j * cs[n:2 * n]; zl = cl[:n] - 1j * cl[n:2 * n]
    ratio = np.abs(zs) / np.maximum(np.abs(zl), 1e-9)
    dph = np.angle(zs / zl)
    out["%d" % xg] = dict(f=(om / 2 / np.pi).round(4).tolist(), amp_ratio=ratio.round(3).tolist(), dphase_rad=dph.round(3).tolist())
    print("x %.0f  amp ratio (low→high f):" % xg, np.round(ratio[::3], 2), " dphase:", np.round(dph[::3], 2))
json.dump(out, open(os.path.join(rd, "transfer.json"), "w"), indent=0)
