# -*- coding: utf-8 -*-
"""Q20 cand A: per-row diagnostics with the rubric's own measures + crease map (rows x columns).
usage: py -3.10 candA_diag.py rows.npz out_prefix [c0,c1]"""
import sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
sys.path.insert(0, C.RUBRIC_TOOLS)
import rubric_measure as RM
import rubric_check as RC

z = np.load(sys.argv[1]); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
pre = sys.argv[2]
rng = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else [-20, 14]
H = Y.max(1); main = int(np.argmin(np.abs(c))); H0 = H[main]
print("row     c      H   top  a_top  fold  Rmin  thc   ch2  ovh   tipa  tipy  l075  l2   strt  inwall")
for r in range(len(c)):
    if not (rng[0] <= c[r] <= rng[1]) or H[r] < 0.5 * H0:
        continue
    cq = RC.corner_q17(A[r], Y[r], 200)
    m = RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
    ls = RC.longest_straight(A[r], Y[r], 0.1 * H[r], 0.95 * H[r]) / H[r]
    f = lambda k: m.get(k) if m.get(k) is not None else np.nan
    print("%3d %6.2f %6.2f %4d %6.2f %5.1f %5.2f %5.1f %5.1f %5.2f %6.2f %5.2f %5.2f %5.2f %5.2f %6.2f" % (
        r, c[r], H[r], cq["top_col"], f("a_top"), cq["fold_deg"], cq["Rmin_m"], f("theta_c_deg"), cq["chord2_deg"],
        f("overhang_over_H"), f("a_tip"), f("y_tip"), f("lip_thick_0p75_m"), f("lip_thick_2m_m"), ls, f("inner_wall_a_at_0p3H")))
# crease map
Xg = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
du = Xg[:, 1:] - Xg[:, :-1]; dv = Xg[1:] - Xg[:-1]
n = np.cross(du[:-1], dv[:, :-1]); n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
ang_r = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
img = np.clip(ang_r / 45.0 * 255, 0, 255).astype(np.uint8)
img = cv2.applyColorMap(img, cv2.COLORMAP_JET)
img = cv2.resize(img, (img.shape[1] * 3, img.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
for j in (18, 90, 200, 314, 379, 394):
    cv2.line(img, (j * 3, 0), (j * 3, img.shape[0]), (255, 255, 255), 1)
for cc in (-16, -10, -5, 0, 3, 5, 8):
    r = int(np.argmin(np.abs(c - cc))); cv2.line(img, (0, r * 3), (img.shape[1], r * 3), (255, 255, 255), 1)
    cv2.putText(img, "c%+d" % cc, (2, r * 3 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
cv2.imwrite(pre + "_crease_rows.png", img)
m = (Y[1:-1, :-1] > 0.3) & (np.abs(c[1:-1, None]) <= 16)
bad = (ang_r > 30) & m
rr, jj = np.nonzero(bad)
print("creases >30:", bad.sum())
if len(rr):
    import collections
    print("by row c:", collections.Counter(np.round(c[rr + 1]).astype(int)).most_common(12))
    print("by col bin:", collections.Counter((jj // 20 * 20)).most_common(12))
