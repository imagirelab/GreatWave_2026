# -*- coding: utf-8 -*-
"""Q20 final K*': per-row rubric numbers (which rows fail what).  usage: py -3.10 fin_rowdiag.py rows.npz [c0 c1]"""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_check as RC
import rubric_measure as RM


def rowdiag(A, Y, c, r, H0, jtip=200):
    a, y = A[r], Y[r]; H = y.max()
    segs = RM.poly_to_segs(a, y)
    m = RM.section_metrics(segs, 0.0, H0, open_w=0.0) or {}
    q = RC.corner_q17(a, y, jtip)
    d = dict(c=c[r], H=H, Rmin=q["Rmin_m"], ch2=q["chord2_deg"], fold=q["fold_deg"], th=m.get("theta_c_deg", np.nan),
             ov=m.get("overhang_over_H", np.nan), atip=m.get("a_tip", np.nan), l075=m.get("lip_thick_0p75_m", np.nan),
             l2=m.get("lip_thick_2m_m", np.nan), atop=m.get("a_top", np.nan))
    if H >= 0.5 * H0:
        b = RM.back_shape(segs, 0.0, m["H"], m["a_top"])
        d.update(straight=b.get("back_longest_straight_over_H", np.nan), R=b.get("back_R_over_H", np.nan),
                 shell=(b.get("shell_thick_normal_over_H") or [np.nan] * 3)[1], w50=m.get("wall_50_over_H", np.nan))
        if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
            t = RM.tube_shape2(segs, 0.0, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"])
            d.update(trms=t.get("tube_fit_rms_over_R", np.nan), tturn=t.get("tube_wall_turn_max_deg_per_m", np.nan), tR=t.get("tube_R_over_H", np.nan))
        fp = RC.foot_plinth(a, y, jtip)
        d.update(vrun=fp["vertical_run_m"])
        ls = RC.longest_straight(a, y, 0.1 * H, 0.95 * H) / H
        d.update(lsec=ls)
        inf = RC.back_inflections(a, y, jtip)
        d.update(infl=inf[0], rough=inf[1])
        jt = int(np.argmax(y[:jtip])); ab = a[:jt + 1]
        from scipy.ndimage import gaussian_filter1d
        yb = gaussian_filter1d(y[:jt + 1], 1.0)
        g = np.degrees(np.arctan2(np.gradient(yb), np.gradient(ab)))
        for f in (0.9, 0.95):
            idx = np.nonzero((yb[:-1] - f * H) * (yb[1:] - f * H) <= 0)[0]
            d["sl%d" % int(f * 100)] = float(g[idx[-1]]) if len(idx) else np.nan
    return d


if __name__ == "__main__":
    z = np.load(sys.argv[1]); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    c0 = float(sys.argv[2]) if len(sys.argv) > 2 else -12; c1 = float(sys.argv[3]) if len(sys.argv) > 3 else 9
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 3
    H0 = Y[int(np.argmin(np.abs(c)))].max()
    keys = ["c", "H", "Rmin", "th", "ch2", "fold", "ov", "l075", "l2", "atop", "atip", "straight", "R", "shell", "w50", "sl90", "sl95", "infl", "rough", "trms", "tturn", "tR", "vrun", "lsec"]
    print(" ".join("%6s" % k[:6] for k in keys))
    for r in range(len(c)):
        if not (c0 <= c[r] <= c1) or (r % step and abs(c[r]) > 0.01):
            continue
        if Y[r].max() < 0.5 * H0:
            continue
        d = rowdiag(A, Y, c, r, H0)
        print(" ".join(("%6.2f" % d[k]) if isinstance(d.get(k), (float, np.floating)) and np.isfinite(d[k]) else ("%6s" % (d.get(k) if d.get(k) is not None and not isinstance(d.get(k), float) else "  -")) for k in keys))
