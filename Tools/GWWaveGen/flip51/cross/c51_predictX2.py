# -*- coding: utf-8 -*-
"""FLIP51 crossing (2026-10-17, Claude): c51_predict rule applied to the isolated hybrid X2 (Gaussian lobes +-60 deg, sigma 28 deg)."""
import sys, json, math
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import numpy as np
import c51_screen as C, c51_predict as P, c51_sweepD as D
th, w = D.gauss_lobes(60.0, 28.0, n=17, cap=85.0)
r = P.predict("X2_T7_G60s28_xf220", 7.0, th, w, 220.25, D.A_D)
r["weights"] = [float(v) for v in w]
json.dump(r, open(C.OUT + "/predict_X2.json", "w", encoding="utf8"), indent=1, default=float)
print("a_j(mean) %.3f A_f %.2f eps %.2f Hc_lin %.2f Hc_2nd %.2f c_in %.2f kAband %.2f ap %.2f" % (r["a_j"], r["A_f_lin"], r["eps_lin"], r["Hc_lin"], r["Hc_2nd"], r["c_in_x110"], r["kA_inlet_band_max"], r["aperture"]))
print("central", {k: round(v, 2) for k, v in r["central"].items()})
print("range", {k: [round(a, 2), round(b, 2)] for k, (a, b) in r["range"].items()})
print("gains", {k: round(v, 2) for k, v in r["gains"].items()})
print("theta", [round(v, 1) for v in th[len(th)//2:]]); print("w", [round(v, 4) for v in w[len(w)//2:]])
om = 2 * math.pi / 7.0; k0 = float(C.DF.kdisp(om, 19.0)); print("T7 h19: k0 %.5f L0 %.2f c %.2f cg %.2f; h13 k %.5f L %.2f" % (k0, 2*math.pi/k0, om/k0, float(C.DF.cg(om, 19.0)), float(C.DF.kdisp(om, 13.0)), 2*math.pi/float(C.DF.kdisp(om, 13.0))))
