# -*- coding: utf-8 -*-
"""A2: per-row rubric quantities (the rubric's own definitions, rubric_measure / rubric_check) for the rows the rubric
scores, so that each failing row can be traced.  usage: py -3.10 candA2_rowmetrics.py rows.npz [out.json] [--quiet]"""
import sys, os, json, math
import numpy as np
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_measure as RM
import rubric_check as RC


def row_metrics(a, y, H0, jtip=200):
    segs = RM.poly_to_segs(a, y)
    m = RM.section_metrics(segs, 0.0, H0, open_w=0.0) or {}
    out = {k: m.get(k) for k in ("H", "a_top", "a_tip", "y_tip", "theta_c_deg", "overhang_over_H", "lip_thick_0p75_m",
                                  "lip_thick_2m_m", "wall_50_over_H", "inner_wall_a_at_0p3H", "front_trough_depth_over_H")}
    if m.get("H", 0) > 2:
        b = RM.back_shape(segs, 0.0, m["H"], m["a_top"])
        out.update({k: b.get(k) for k in ("back_R_over_H", "back_longest_straight_over_H", "shell_thick_normal_over_H")})
        if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
            t = RM.tube_shape2(segs, 0.0, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"])
            out.update({k: t.get(k) for k in ("tube_fit_rms_over_R", "tube_R_over_H", "tube_wall_turn_max_deg_per_m", "tube_closure_deg", "tube_center_used")})
        q = RC.corner_q17(a, y, jtip)
        out.update(Rmin=q["Rmin_m"], chord2=q["chord2_deg"], fold=q["fold_deg"])
        jt = int(np.argmax(y[:jtip])); jc = min(jtip + 115, len(a) - 1)
        sa = RC.arclen(a[jt:jc + 1], y[jt:jc + 1]); sq = np.arange(0, sa[-1], 0.05)
        pa = gaussian_filter1d(np.interp(sq, sa, a[jt:jc + 1]), 4); py_ = gaussian_filter1d(np.interp(sq, sa, y[jt:jc + 1]), 4)
        hd = np.degrees(np.unwrap(np.arctan2(np.gradient(py_), np.gradient(pa))))
        out["curl_deg"] = float(hd[0] - hd.min())
        Hr = y[jt]; ab = a[:jt + 1]; yb = gaussian_filter1d(y[:jt + 1], 1.0)
        g = np.degrees(np.arctan2(np.gradient(yb), np.gradient(ab)))
        for f in (0.9, 0.95):
            idx = np.nonzero((yb[:-1] - f * Hr) * (yb[1:] - f * Hr) <= 0)[0]
            out["slope_%g" % f] = float(g[idx[-1]]) if len(idx) else None
        inf = RC.back_inflections(a, y, jtip)
        out["back_infl"] = inf[0]; out["back_rough"] = inf[1]
        out["long_straight"] = RC.longest_straight(a, y, 0.1 * y.max(), 0.95 * y.max()) / y.max()
    return out


def main():
    rows = sys.argv[1]
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    H0 = float(Y[int(np.argmin(np.abs(c)))].max())
    res = {}
    for r in range(len(c)):
        if Y[r].max() < 0.5 * H0:
            continue
        res[r] = dict(row_metrics(A[r], Y[r], H0), c=float(c[r]))
    if len(sys.argv) > 2 and not sys.argv[2].startswith("--"):
        json.dump(res, open(sys.argv[2], "w"), indent=1, default=float)
    if "--quiet" in sys.argv:
        return
    def f(v, p=2):
        return "-" if v is None else (("%." + str(p) + "f") % v)
    print("row     c     H   Rmin  th_c  fold slope9 slope95 bR/H bStr  shell  wall5  ovh  tubeRMS tubeR turn  lip075 lip2 curl  trough lstr")
    for r, m in res.items():
        sh = m.get("shell_thick_normal_over_H")
        print("%3d %6.2f %5.1f %5s %5s %5s %6s %6s %5s %5s %5s %5s %5s %6s %5s %5s %5s %5s %5s %5s %5s" % (
            r, m["c"], m["H"], f(m.get("Rmin")), f(m.get("theta_c_deg"), 0), f(m.get("fold"), 1), f(m.get("slope_0.9"), 0),
            f(m.get("slope_0.95"), 0), f(m.get("back_R_over_H")), f(m.get("back_longest_straight_over_H")),
            f(sh[1] if sh else None), f(m.get("wall_50_over_H")), f(m.get("overhang_over_H")), f(m.get("tube_fit_rms_over_R")),
            f(m.get("tube_R_over_H")), f(m.get("tube_wall_turn_max_deg_per_m"), 0), f(m.get("lip_thick_0p75_m")),
            f(m.get("lip_thick_2m_m")), f(m.get("curl_deg"), 0), f(m.get("front_trough_depth_over_H")), f(m.get("long_straight"))))


if __name__ == "__main__":
    main()
