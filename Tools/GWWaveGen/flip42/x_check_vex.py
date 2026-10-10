# -*- coding: utf-8 -*-
"""FLIP42：場面の VEX の目標の波（groupwave）を、numpy の線形の重ね合わせと比べる（場面は保存しない。読むだけ）。"""
import hou, sys, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_tanklib as L, v_lin
hou.hipFile.load(r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc", suppress_save_prompt=True, ignore_load_warnings=True)
ct = hou.node("/obj/G_SETUP/CTRL")
P = {p.name(): p.eval() for p in ct.parms()}
pts = [(135.463 + 33.866, -2.0, 100.0), (135.463 + 33.866, 5.0, 104.0), (60.0, -10.0, 120.0), (100.0, -30.0, 171.5), (135.463, 0.0, 50.0)]
w = hou.node("/obj/G_SETUP").createNode("attribwrangle", "chk")
w.parm("class").set(0)
code = L.VEX_HEAD + "\n"
for i, (x, y, t) in enumerate(pts):
    code += "{ float e; vector v; groupwave(%r, %r, %r, 1.0, e, v); int p = addpoint(0, set(%r, %r, %r)); setpointattrib(0, \"eta\", p, e); setpointattrib(0, \"vel\", p, v); }\n" % (x, y, t, x, y, t)
w.parm("snippet").set(code)
w.parm("vex_precision").set("64")
g = w.geometry()
h = P["h0"]; N = int(P["ncomp"]); fc = P["fc"]; dff = P["dff"]
f = np.linspace(fc * (1 - dff / 2), fc * (1 + dff / 2), N); om = 2 * np.pi * f
k = np.array([v_lin.k_of_omega(o, h) for o in om]); a = P["S"] / k.sum()
print("a", a, "k", k[0], k[-1])
for pt, (x, y, t) in zip(g.points(), pts):
    th = k * (x - P["x_p"] - P["x_b"]) - om * (t - P["t_b"])
    e = (a * np.cos(th)).sum()
    ye = min(max(h * (y - e) / (h + e), -h), 0.0)
    u = (a * om * np.cosh(k * (ye + h)) / np.sinh(k * h) * np.cos(th)).sum()
    v = (a * om * np.sinh(k * (ye + h)) / np.sinh(k * h) * np.sin(th)).sum()
    print("x %.1f y %.1f t %.1f  VEX eta %.5f u %.5f v %.5f | numpy eta %.5f u %.5f v %.5f" % (x, y, t, pt.attribValue("eta"), pt.attribValue("vel")[0], pt.attribValue("vel")[1], e, u, v))
