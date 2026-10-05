# -*- coding: utf-8 -*-
"""Q20 cand A: which rows fail which rubric measures (worst rows per measure)."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_measure as RM
import rubric_check as RC
z = np.load(sys.argv[1]); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
H = Y.max(1); H0 = H[int(np.argmin(np.abs(c)))]
big = [r for r in range(len(c)) if H[r] >= 0.5 * H0]
res = {}
for r in big:
    segs = RM.poly_to_segs(A[r], Y[r]); m = RM.section_metrics(segs, 0.0, H0, open_w=0.0) or {}
    cq = RC.corner_q17(A[r], Y[r], 200)
    fp = RC.foot_plinth(A[r], Y[r], 200)
    d = {"Rmin": cq["Rmin_m"], "fold": cq["fold_deg"], "l075": m.get("lip_thick_0p75_m"), "l2": m.get("lip_thick_2m_m"),
         "ovh": m.get("overhang_over_H"), "vrun": fp["vertical_run_m"], "tip_a": m.get("a_tip"), "tip_y": m.get("y_tip")}
    if H[r] >= 0.75 * H0 and -5 <= c[r] <= 4:
        b = RM.back_shape(segs, 0.0, m["H"], m["a_top"])
        d.update(straight=b.get("back_longest_straight_over_H"), shell=(b.get("shell_thick_normal_over_H") or [None, None])[1], wall=m.get("wall_50_over_H"))
    if -6 <= c[r] <= 3 and H[r] >= 0.75 * H0 and "inner_wall_a_at_0p3H" in m:
        t = RM.tube_shape2(segs, 0.0, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"])
        d.update(turn=t.get("tube_wall_turn_max_deg_per_m"), tR=t.get("tube_R_over_H"), trms=t.get("tube_fit_rms_over_R"))
    res[r] = d
def worst(key, hi=True, n=6):
    rows = [(v[key], r) for r, v in res.items() if v.get(key) is not None]
    rows.sort(reverse=hi)
    return ", ".join("r%d c%+.2f:%.2f" % (r, c[r], v) for v, r in rows[:n])
for k, hi in (("Rmin", False), ("fold", True), ("l075", True), ("l2", True), ("ovh", False), ("vrun", True), ("straight", True), ("shell", True), ("wall", True), ("turn", True), ("trms", True)):
    print(k, "->", worst(k, hi))
d2 = np.abs(np.diff(H, 2)); i = np.argsort(-d2 * (H[1:-1] > 0.25 * H0))[:5]
print("H 2nd diff worst:", ", ".join("c%+.2f:%.2f" % (c[j + 1], d2[j]) for j in i))
