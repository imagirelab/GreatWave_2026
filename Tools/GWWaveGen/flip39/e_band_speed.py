# -*- coding: utf-8 -*-
"""FLIP39 E：較正の計算（C1）で、周波数の帯ごとに、水面計 x=200 m と x=400 m の間の群の遅れと位相の遅れを、計算と線形の見込みで比べる。py -3.10。"""
import sys, json, os
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf, linear_eta, run_info, bed_of, focus_row
rd = sys.argv[1]
rj, cj = run_info(rd); hf = load_hf(rd)
g = hf["grid"]; x = g["x0"] + g["dx"] * np.arange(hf["eta"].shape[2])
t = hf["t"]; row = focus_row(hf, rj) - 0.423
bed = bed_of(rj, cj)
sel = (t >= 20) & (t <= 95)
tt = t[sel]; dt = tt[1] - tt[0]
fc = 1 / 12.0
bands = [(0.55, 0.8), (0.8, 1.05), (1.05, 1.3), (1.3, 1.6)]
res = {}
def band(sig, lo, hi):
    F = np.fft.rfft(sig); f = np.fft.rfftfreq(len(sig), dt)
    F[(f < lo * fc) | (f > hi * fc)] = 0
    return np.fft.irfft(F, len(sig))
def hilb_env(s):
    F = np.fft.fft(s); n = len(s); h = np.zeros(n); h[0] = 1; h[1:(n + 1) // 2] = 2
    if n % 2 == 0: h[n // 2] = 1
    return np.abs(np.fft.ifft(F * h))
for xa, xb in ((200.0, 300.0), (200.0, 400.0)):
    ia = int(np.argmin(np.abs(x - xa))); ib = int(np.argmin(np.abs(x - xb)))
    la = linear_eta(cj, bed, [x[ia]], tt)[:, 0]; lb = linear_eta(cj, bed, [x[ib]], tt)[:, 0]
    sa = np.nan_to_num(row[sel, ia]); sb = np.nan_to_num(row[sel, ib])
    for lo, hi in bands:
        out = {}
        for nm, A, B in (("sim", sa, sb), ("lin", la, lb)):
            a = band(A, lo, hi); b = band(B, lo, hi)
            ea, eb = hilb_env(a), hilb_env(b)
            # 群の遅れ：包絡の重心の時刻の差
            tga = np.sum(tt * ea ** 2) / np.sum(ea ** 2); tgb = np.sum(tt * eb ** 2) / np.sum(eb ** 2)
            out[nm] = dict(group_delay=tgb - tga, rms_a=float(np.sqrt(np.mean(a ** 2))), rms_b=float(np.sqrt(np.mean(b ** 2))))
        k = "%d-%d_f%.2f-%.2f" % (xa, xb, lo, hi)
        res[k] = out
        print(k, "group delay sim %.2f s lin %.2f s | rms at b: sim %.3f lin %.3f | rms ratio b/a sim %.2f lin %.2f" % (
            out["sim"]["group_delay"], out["lin"]["group_delay"], out["sim"]["rms_b"], out["lin"]["rms_b"],
            out["sim"]["rms_b"] / out["sim"]["rms_a"], out["lin"]["rms_b"] / out["lin"]["rms_a"]))
json.dump(res, open(os.path.join(rd, "band_speed.json"), "w"), indent=1)
