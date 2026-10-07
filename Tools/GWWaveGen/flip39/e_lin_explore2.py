import numpy as np, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_lin import *
reef = Bed(); flat = Bed(flat=True)
xg = 150.0; xf = 556.0
for Tc, flo, fhi in ((12, 0.55, 1.6), (12, 0.5, 1.6), (12, 0.55, 1.75), (12, 0.6, 1.6), (11, 0.55, 1.6), (13, 0.5, 1.6)):
    comp = make_components(Tc, flo, fhi, 32, 1.0, reef)
    om = comp["om"]
    for tf in (80.0, 90.0, 100.0):
        t = np.arange(-80, tf + 6, 0.25)
        e_g = eta_xt(comp, reef, [xg], t, xf, tf)[:, 0]
        pre = np.sum(e_g[t < 0] ** 2) / np.sum(e_g ** 2)
        mx_g = np.abs(e_g[t >= 0]).max()
        x = np.arange(150, 706, 2.0)
        t2 = np.arange(tf - 3, tf + 3, 0.25)
        E = eta_xt(comp, reef, x, t2, xf, tf)
        # hybrid start: field at tf-35 for x<420
        th = tf - 35.0
        x3 = np.arange(0, 480, 2.0)
        E3 = eta_xt(comp, reef, x3, [th], xf, tf)[0]
        taper = 0.5 * (1 - np.tanh((x3 - 420) / 30.0))
        print("Tc %d band %.2f-%.2f tf %.0f | pre %.3f | max@xg %.3f | focus %.3f ratio %.2f | S/m %.4f | hybrid t0=%.0f: max init %.3f, energy beyond 420 %.3f" % (
            Tc, flo, fhi, tf, pre, mx_g, E.max(), E.max() / mx_g, steepness_S(comp, 60), th, np.abs(E3 * taper).max(),
            np.sum((E3 * (1 - taper)) ** 2) / np.sum(E3 ** 2)))
