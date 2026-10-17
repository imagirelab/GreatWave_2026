# -*- coding: utf-8 -*-
"""Calibrate the linear screen on measured FLIP runs (DM1A, DF1A, DA3): gamma at the measured onset, linear crest metrics. [computed]"""
import os, sys, json, math, time
import numpy as np
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import l51_mse as M
import l51_screen as S
t0 = time.time()
res = {}
DX = 2.0
cases = {
  "DM1A": dict(T=12.0, a_sum=6.331240146143423, xb=256.5, Hc=7.78),
  "DF1A": dict(T=10.0, a_sum=6.503, xb=256.5, Hc=7.26),
}
for nm, c in cases.items():
    x = np.arange(0, 412 + 1e-9, DX); y = np.arange(0, 140 + 1e-9, DX)
    h = M.bed_beach(x, y)
    fan = dict(h0=19.0, x_toe=160.25, s=10.0, a_sum=1.0, x_f=220.25)
    tk, A1, AT = S.run_case(c["T"], x, y, h, target_kind="fan", fan=fan, side=(95.0, 180.25, 210.25), periods=30)
    hb = float(np.interp(c["xb"], x, h[0]))
    out = S.analyse(tk, A1, c["a_sum"], gamma_b=1.0, r_hc=c["Hc"] / hb, x_b_force=c["xb"], label=nm)
    res[nm] = out
    np.savez_compressed(os.path.join(S.OUT, "cal_%s_A1.npz" % nm), A=A1, x=x, y=y, h=h)
# DA3: plane T 12, a = 3.75 (H 7.5 linear proxy) over the DA3 bed, W 85 walls, exit sponge 362-442
x = np.arange(0, 442 + 1e-9, DX); y = np.arange(0, 85 + 1e-9, DX)
h = M.bed_da3(x, y)
tk, A1, AT = S.run_case(12.0, x, y, h, target_kind="plane", side=None, exit_x0=362.0, swash=(3.0, 2.0, 2), periods=30)
hb = float(np.interp(268.5, x, h[0]))
res["DA3"] = S.analyse(tk, A1, 3.75, gamma_b=1.0, r_hc=6.41 / hb, x_b_force=268.5, label="DA3")
np.savez_compressed(os.path.join(S.OUT, "cal_DA3_A1.npz"), A=A1, x=x, y=y, h=h)
res["wall_s"] = time.time() - t0
for k, v in res.items():
    if isinstance(v, dict):
        print(k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items() if kk not in ("profile_y", "profile_c_over_Hc")})
json.dump(res, open(os.path.join(S.OUT, "calib.json"), "w"), indent=1)
