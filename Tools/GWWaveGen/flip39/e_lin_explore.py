import numpy as np, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_lin import *
reef = Bed(); flat = Bed(flat=True)
xg = 150.0
for Tc in (12.0, 14.0):
    for (flo, fhi) in ((0.6, 1.4), (0.65, 1.5), (0.55, 1.6)):
        for bedn, bed, xf in (("flat", flat, 556.0), ("reef", reef, 556.0), ("reef", reef, 530.0)):
            comp = make_components(Tc, flo, fhi, 32, 1.0, bed)
            om = comp["om"]
            tt = (xf - xg) / cg(om, bed.h0)
            tf = tt.max() + 1.5 * Tc / flo
            t = np.arange(-60, tf + 6, 0.25)
            e_g = eta_xt(comp, bed, [xg], t, xf, tf)[:, 0]
            pre = np.sum(e_g[t < 0] ** 2) / np.sum(e_g ** 2)
            mx_g = np.abs(e_g[t >= 0]).max()
            x = np.arange(150, 706, 2.0)
            t2 = np.arange(tf - 30, tf + 6, 0.25)
            E = eta_xt(comp, bed, x, t2, xf, tf)
            k = np.unravel_index(np.argmax(E), E.shape)
            # rise: max crest in tank vs time
            mxt = E.max(axis=1)
            def tr(r):
                i = np.where(mxt >= r * E.max())[0]; return t2[i[0]] - t2[k[0]] if i.size else None
            S60 = steepness_S(comp, 60.0)
            print("Tc %.0f band %.2f-%.2f %s xf %.0f | tf %.1f s, pre-energy %.3f | max@xg %.3f focus %.3f at x=%.0f t=%.1f ratio %.2f | rise 0.5->1: %.1f s, 0.7: %.1f | S per 1m A: %.4f" % (
                Tc, flo, fhi, bedn, xf, tf, pre, mx_g, E.max(), x[k[1]], t2[k[0]], E.max() / mx_g, tr(0.5), tr(0.7), S60))
