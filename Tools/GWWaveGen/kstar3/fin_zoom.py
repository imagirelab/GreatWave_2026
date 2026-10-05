# -*- coding: utf-8 -*-
"""zoomed section plot with the painting's allowed region: py -3.10 fin_zoom.py out.png a0,a1,y0,y1 c1,c2,.. rowsA[:lab] rowsB[:lab]"""
import sys, os
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import fin_allowed as FA
out = sys.argv[1]; a0, a1, y0, y1 = [float(v) for v in sys.argv[2].split(",")]
cs = [float(v) for v in sys.argv[3].split(",")]
files = sys.argv[4:]
V1, tgt, fr = C.painting_frame()
res = (a1 - a0) / 480.0
data = []
for f in files:
    p = f.split(".npz")[0] + ".npz"; z = np.load(p); data.append((z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)))
cols = [(0, 0, 220), (220, 0, 0), (0, 150, 0)]
tiles = []
for c0 in cs:
    aa, yy, ok, s = FA.allowed_grid(fr, tgt, c0, a_rng=(a0, a1), y_rng=(y0, y1), res=res)
    t = np.where(ok[::-1, :, None], np.array([205, 225, 235], np.uint8), np.array([250, 250, 250], np.uint8)).copy()
    Hh, Ww = t.shape[:2]
    def px(a, y): return np.stack([(a - aa[0]) / res, (yy[-1] - y) / res], -1)
    for g in np.arange(np.ceil(a0), a1, 1.0):
        x = int((g - aa[0]) / res); cv2.line(t, (x, 0), (x, Hh), (228, 228, 228) if g % 5 else (200, 200, 200), 1)
    for g in np.arange(np.ceil(y0), y1, 1.0):
        y = int((yy[-1] - g) / res); cv2.line(t, (0, y), (Ww, y), (228, 228, 228) if g % 5 else (200, 200, 200), 1)
    for k, (A, Y, c) in enumerate(data):
        r = int(np.argmin(np.abs(c - c0)))
        q = px(A[r], Y[r]); cv2.polylines(t, [q.round().astype(np.int32)], False, cols[k], 1, cv2.LINE_AA)
        for j in (90, 200, 314, 379):
            cv2.circle(t, tuple(q[j].round().astype(int)), 3, cols[k], 1)
    cv2.putText(t, "c=%+.2f" % c0, (5, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
    tiles.append(t)
n = len(tiles); nc = 4; rows = []
for i in range(0, n, nc):
    rr = tiles[i:i + nc]
    while len(rr) < nc:
        rr.append(np.full_like(tiles[0], 255))
    rows.append(np.hstack(rr))
cv2.imwrite(out, np.vstack(rows))
