# -*- coding: utf-8 -*-
"""Validation of l51_mse (flat plane wave, 1:10 shoaling vs WKB, option-D fan vs WKB). py -3.10 -B. [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M

OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP51/lens"
res = {}
t0 = time.time()
# V1 flat plane wave
T = 12.0; dx = 2.0
x = np.arange(0, 520 + 1e-9, dx); y = np.arange(0, 40 + 1e-9, dx)
h = 19.0 * np.ones((len(y), len(x)))
tk = M.Tank(T, x, y, h)
AT = np.tile(M.wkb_plane(T, x, h[0], 1.0), (len(y), 1))
w, mu = M.band_maps(x, y, h, inlet_x1=100.0, exit_x0=400.0, swash_h=None)
r = tk.run(AT, w, mu, periods=26)
amp = np.abs(r["A"][0]); m = (x >= 120) & (x <= 380)
res["V1_flat"] = dict(amp_mean=float(amp[m].mean()), amp_min=float(amp[m].min()), amp_max=float(amp[m].max()), dt=r["dt"])
# V2 beach shoaling
x = np.arange(0, 412 + 1e-9, dx)
h = M.bed_beach(x, y)
tk = M.Tank(T, x, y, h)
AT = np.tile(M.wkb_plane(T, x, h[0], 1.0), (len(y), 1))
w, mu = M.band_maps(x, y, h, inlet_x1=100.0, swash_h=2.5)
r = tk.run(AT, w, mu, periods=26)
amp = np.abs(r["A"][0])
wk = np.abs(M.wkb_plane(T, x, h[0], 1.0))
rows = {}
for hv in (19, 15, 12, 10, 8, 6):
    i = int(np.argmin(np.abs(h[0] - hv)))
    rows[str(hv)] = dict(x=float(x[i]), mse=float(amp[i]), wkb=float(wk[i]))
res["V2_beach"] = rows
# V3 option-D fan (DM1A numbers) in the D tank bands
T = 12.0; a_sum = 6.331240146143423; x_f = 220.25
x = np.arange(0, 412 + 1e-9, dx); y = np.arange(0, 140 + 1e-9, dx)
h = M.bed_beach(x, y)
AT = M.fan_target(T, x, y, 19.0, 160.25, 10.0, a_sum, x_f)
tk = M.Tank(T, x, y, h)
w, mu = M.band_maps(x, y, h, inlet_x1=100.0, side=(95.0, 180.25, 210.25), swash_h=2.5)
r = tk.run(AT, w, mu, periods=30)
A = r["A"]
np.savez_compressed(os.path.join(OUT, "V3_fan_DM1A_A.npz"), A=A, x=x, y=y, h=h, AT=AT)
cen = np.abs(A[0]); cw = np.abs(AT[0])
rows = {}
for xv in (120, 160, 200, 220, 240, 256, 270):
    i = int(np.argmin(np.abs(x - xv)))
    rows[str(xv)] = dict(mse=float(cen[i]), wkb=float(cw[i]), h=float(h[0, i]))
res["V3_fan_centre"] = rows
# lateral profile of |A| at x 220 and 256
for xv in (220.0, 256.0):
    i = int(np.argmin(np.abs(x - xv)))
    pm = np.abs(A[:, i]); pw = np.abs(AT[:, i])
    def fw(p):
        lv = 0.5 * p[0]; j = int(np.argmax(p < lv)); return float(2 * y[j])
    res["V3_lat_%d" % int(xv)] = dict(fwhm_mse=fw(pm), fwhm_wkb=fw(pw), peak_mse=float(pm[0]), peak_wkb=float(pw[0]))
res["wall_s"] = time.time() - t0
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.join(OUT, "validate.json"), "w"), indent=1)
