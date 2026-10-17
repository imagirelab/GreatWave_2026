# -*- coding: utf-8 -*-
"""FLIP51 crossing (2026-10-17, Claude): how high must a summit jet rise for the frozen core metrics to enter the target ranges?
Geometric model [guess, not physics]: the predicted pre-jet mound (c51_predict rule: f_H 0.86, f_W 1.12) plus a jet of rise factor J
(summit = J x mound crest) shaped as a lateral triangle whose base (width b) sits at 0.9 x mound crest, added as max(mound, jet) on the
height field around the summit. Reports W50, W80, W95, K, S2 and the target miss vs J and b."""
import sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import numpy as np
import c51_screen as C, c51_predict as P, c51_sweepD as D

t0 = time.time()
x = np.arange(0.0, 290.25, 1.0); y = np.arange(0.0, 140.0 + 1e-9, 1.0)
sets = {}
th, w = C.DF.components(80.0, 30, "uniform"); sets["U80 (control)"] = (th, w)
th, w = P.lobes(60.0, 15.0, 11); sets["X1 L60d15"] = (th, w)
th, w = D.gauss_lobes(60.0, 28.0, n=17, cap=85.0); sets["X2 G60s28"] = (th, w)
out = {}
for nm, (th, w) in sets.items():
    F = C.Field(7.0, th, w, 220.25, x, y)
    xc = D.iso(F, D.A_D)["x_axis_max"]; xwin = (xc - 60.0, xc + 35.0); tg = np.linspace(-2.1, 2.1, 43)
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    Hs = max(float(F.eta(D.A_D, t, 2)[sel].max()) for t in tg)
    s = P.solve_s(F, 0.86 * Hs, xwin, tg, D.A_D)
    best = max(((float(F.eta(s, t, 2)[sel].max()), t) for t in tg))
    e = F.eta(s, best[1], 2)
    e = np.array([np.interp(y / 1.12, y, row) for row in e])          # f_W 1.12
    ix, iy = np.unravel_index(np.argmax(np.where(sel[:, None], e, -9)), e.shape)
    H0 = float(e[ix, iy])
    res = []
    for b in (6.0, 12.0):
        for J in (1.0, 1.2, 1.4, 1.6, 1.8, 2.0):
            ej = e.copy()
            if J > 1.0:
                X, Y = np.meshgrid(x, y, indexing="ij")
                r = np.hypot(X - x[ix], Y - y[iy])
                jet = H0 * (J - (J - 0.9) * r / (b / 2.0))
                ej = np.where(r <= b / 2.0, np.maximum(ej, jet), ej)
            meta = dict(x0=0.0, dx=1.0, z0=0.0, dz=1.0)
            m = C.EM.hf_metrics(ej.T.copy(), meta, 0.0, xwin=xwin)
            miss, per = C.EM.score_vs_target(m)
            res.append(dict(b=b, J=J, Hc=m["Hc"], W50=m["W50"], W80=m["W80"], W95=m["W95"], K=m["K"], S2=m["S2"], miss=miss))
            print("%-14s b %4.1f J %.1f Hc %5.2f W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f miss %.2f" % (nm, b, J, m["Hc"], m["W50"], m["W80"], m["W95"], m["K"], m["S2"], miss))
    out[nm] = dict(H_mound=H0, rows=res)
json.dump(dict(doc=__doc__, sets=out, cpu_s=time.time() - t0), open(C.OUT + "/jet_requirement.json", "w", encoding="utf8"), indent=1, default=float)
print("cpu %.1f s" % (time.time() - t0))
