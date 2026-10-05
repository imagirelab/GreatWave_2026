# -*- coding: utf-8 -*-
"""Q20 final loop 2 (diagnostic): rows (and their control points) of a design in main-equivalent coordinates over the
painting's sky pocket.  usage: py -3.10 fin2_cornerplot.py rows.npz params.json out.png c1,c2,.. a0,a1,y0,y1 [scale]"""
import sys, json
import numpy as np, cv2
import fin_pocket as PK, fin2_design as D
rows, prm_p, out, cl, box = sys.argv[1:6]
S = float(sys.argv[6]) if len(sys.argv) > 6 else 60
a0, a1, y0, y1 = [float(v) for v in box.split(",")]
pk = PK.pocket(); aa, yy = pk["grid"]; m = pk["pocket_mask"]; cs = PK.cam_sec()
img = np.full((int((y1 - y0) * S), int((a1 - a0) * S), 3), 255, np.uint8)
A_, Y_ = np.meshgrid(aa, yy)
xi = ((A_ - a0) * S).astype(int); yi = ((y1 - Y_) * S).astype(int)
ok = m & (xi >= 0) & (xi < img.shape[1]) & (yi >= 0) & (yi < img.shape[0])
for dx in range(int(S * 0.04) + 1):
    for dy in range(int(S * 0.04) + 1):
        img[np.clip(yi[ok] + dy, 0, img.shape[0] - 1), np.clip(xi[ok] + dx, 0, img.shape[1] - 1)] = (235, 205, 205)
Q = pk["path"]; q = np.stack([(Q[:, 0] - a0) * S, (y1 - Q[:, 1]) * S], -1).astype(np.int32); cv2.polylines(img, [q], False, (0, 0, 0), 1)
z = np.load(rows); A, Y, c = z["A"], z["Y"], z["c"]
prm = json.load(open(prm_p, encoding="utf-8")); P = D.row_params(prm, c)
cols = [(0, 0, 255), (0, 160, 0), (255, 0, 0), (0, 140, 255), (160, 0, 160), (0, 120, 120)]
for k, cc in enumerate(float(v) for v in cl.split(",")):
    r = int(np.argmin(abs(c - cc))); col = cols[k % len(cols)]
    E = PK.to_eq(np.stack([A[r], Y[r]], -1), c[r], cs)
    q = np.stack([(E[:, 0] - a0) * S, (y1 - E[:, 1]) * S], -1).astype(np.int32); cv2.polylines(img, [q], False, col, 1)
    p = {kk: float(P[kk][r]) for kk in P}; Pc = D.control_polygon(p, c[r], cs); Ec = PK.to_eq(Pc, c[r], cs)
    for nm, e in zip(D.NAMES, Ec):
        x, y = int((e[0] - a0) * S), int((y1 - e[1]) * S)
        if 0 <= x < img.shape[1] and 0 <= y < img.shape[0]:
            cv2.circle(img, (x, y), 3, col, -1); cv2.putText(img, nm[:6], (x + 4, y - 2), 0, 0.35, col, 1)
    cv2.putText(img, "c=%.2f" % c[r], (5, 15 + 15 * k), 0, 0.45, col, 1)
cv2.imwrite(out, img)
