# -*- coding: utf-8 -*-
"""FLIP51 crossing screen, sweep E (2026-10-17, Claude): width vs isolation trade-off of the direction set (T 7 s, D19B, focus 220.25 m,
a_sum = DM1A 6.331 m). Families: uniform fan +-theta_max; |sin theta|^p over +-85 deg (weight toward crossing angles, continuous);
Gaussian lobes at +-60 deg with sigma. Same iso() and prediction rule as sweep D."""
import sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import numpy as np
import c51_screen as C, c51_predict as P, c51_sweepD as D

t0 = time.time()
cands = []
for tm in (60.0, 70.0, 80.0, 85.0):
    th, w = C.DF.components(tm, 30, "uniform"); cands.append(("U%g" % tm, th, w))
for p in (1.0, 2.0, 3.0):
    th = np.linspace(-85.0, 85.0, 35); w = np.abs(np.sin(np.radians(th))) ** p; w /= w.sum(); cands.append(("S85p%g" % p, th, w))
for sg in (20.0, 28.0, 36.0):
    th, w = D.gauss_lobes(60.0, sg, n=17, cap=85.0); cands.append(("G60s%g" % sg, th, w))
x = np.arange(0.0, 290.25, 1.0); y = np.arange(0.0, 140.0 + 1e-9, 1.0)
rows = []
for nm, th, w in cands:
    F = C.Field(7.0, th, w, 220.25, x, y)
    r = dict(name=nm, theta=[float(v) for v in th], w=[float(v) for v in w], **D.iso(F, D.A_D))
    xc = r["x_axis_max"]; xwin = (xc - 60.0, xc + 35.0); tg = np.linspace(-2.1, 2.1, 43)
    sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
    Hs = max(float(F.eta(D.A_D, t, 2)[sel].max()) for t in tg)
    s = P.solve_s(F, 0.86 * Hs, xwin, tg, D.A_D)
    m = P.stretch_metrics(F, s, 1.12, xwin, tg); r.update(Hc_2nd=Hs, pred=m); rows.append(r)
    print("%-9s axis kA %.2f at x %.0f hot80 %3.0f m side %.2f at (%3.0f,%3.0f) sb %.2f in %.2f | Hc %.2f W50 %.2f W80 %.2f W95 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f A50 %.2f miss %.2f"
          % (nm, r["kA_axis_max"], r["x_axis_max"], r["hot_len80_m"], r["side_max_rel"], r["side_at"][0], r["side_at"][1], r["kA_side_band"], r["kA_inlet_band"],
             m["Hc"], m["W50"], m["W80"], m["W95"], m["K"], m["S2"], m.get("ring_max", float("nan")), m["Lx50"], m["A50"], m["target_miss"]))
json.dump(dict(rows=rows, cpu_s=time.time() - t0), open(C.OUT + "/screen_E.json", "w", encoding="utf8"), indent=1, default=float)
print("cpu %.1f s" % (time.time() - t0))
