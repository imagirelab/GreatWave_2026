# -*- coding: utf-8 -*-
"""per-row version of the Q20 rubric section checks (same functions as rubric_check.py) for fast design loops."""
import math
import numpy as np
from scipy.ndimage import gaussian_filter1d
from candB_common import *
import rubric_check as RC
import rubric_measure as RM


def row_metrics(a, y, H0_=H0, jtip=200, full=True):
    out = {}
    segs = RM.poly_to_segs(a, y)
    m = RM.section_metrics(segs, 0.0, H0_, open_w=0.0) or {}
    cq = RC.corner_q17(a, y, jtip)
    out.update(H=m.get("H"), theta_c=m.get("theta_c_deg"), Rmin=cq["Rmin_m"], chord2=cq["chord2_deg"], fold=cq["fold_deg"],
               top_col=cq["top_col"], wall50=m.get("wall_50_over_H"), overhang=m.get("overhang_over_H"),
               lip075=m.get("lip_thick_0p75_m"), lip2=m.get("lip_thick_2m_m"), a_top=m.get("a_top"), a_tip=m.get("a_tip"))
    if not full or not m or m.get("H", 0) < 2:
        return out
    b = RM.back_shape(segs, 0.0, m["H"], m["a_top"])
    out.update(backR=b.get("back_R_over_H"), straight=b.get("back_longest_straight_over_H"),
               shell=(b.get("shell_thick_normal_over_H") or [None, None, None])[1])
    jt = int(np.argmax(y[:jtip])); Hr = y[jt]
    ab = a[:jt + 1]; yb = gaussian_filter1d(y[:jt + 1], 1.0)
    g = np.degrees(np.arctan2(np.gradient(yb), np.gradient(ab)))
    for f in (0.9, 0.95):
        idx = np.nonzero((yb[:-1] - f * Hr) * (yb[1:] - f * Hr) <= 0)[0]
        out["slope%02d" % int(f * 100)] = float(g[idx[-1]]) if len(idx) else None
    inf = RC.back_inflections(a, y, jtip)
    out.update(infl=inf[0], rough=inf[1])
    out["straight_any"] = RC.longest_straight(a, y, 0.1 * Hr, 0.95 * Hr) / Hr
    fp = RC.foot_plinth(a, y, jtip); out["vrun"] = fp["vertical_run_m"]
    out["trough"] = RC.trough(a, y, jtip, Hr)["trough_depth_over_H"]
    if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
        t = RM.tube_shape2(segs, 0.0, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"])
        out.update(tube_rms=t.get("tube_fit_rms_over_R"), tube_turn=t.get("tube_wall_turn_max_deg_per_m"), tube_R=t.get("tube_R_over_H"))
    # lip curl (crest -> underside root)
    jc = min(jtip + 115, len(a) - 1)
    sa = arclen(a[jt:jc + 1], y[jt:jc + 1]); sq = np.arange(0, sa[-1], 0.05)
    pa = gaussian_filter1d(np.interp(sq, sa, a[jt:jc + 1]), 4); py_ = gaussian_filter1d(np.interp(sq, sa, y[jt:jc + 1]), 4)
    hd = np.degrees(np.unwrap(np.arctan2(np.gradient(py_), np.gradient(pa))))
    out["curl"] = float(hd[0] - hd.min())
    return out


def fmt(m):
    ks = ["H", "theta_c", "Rmin", "chord2", "fold", "slope90", "slope95", "backR", "straight", "shell", "wall50", "infl", "rough",
          "straight_any", "overhang", "lip075", "lip2", "curl", "tube_rms", "tube_turn", "tube_R", "vrun", "trough"]
    s = []
    for k in ks:
        v = m.get(k)
        if v is None:
            continue
        s.append("%s %s" % (k, ("%.2f" % v) if isinstance(v, float) else v))
    return " | ".join(s)
