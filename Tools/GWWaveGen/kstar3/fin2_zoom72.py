# -*- coding: utf-8 -*-
"""Q20 final loop 2 (diagnostic): zoom of the painting view at the lower end of 72 with projected rows.
usage: py -3.10 fin2_zoom72.py rows.npz skydiff.png out.png c1,c2,... [x0,y0,x1,y1] [S]"""
import sys
import numpy as np, cv2
import candA_common as C
V1, tgt, fr = C.painting_frame()
rows, skyp, out, cl = sys.argv[1:5]
x0, y0, x1, y1 = [int(v) for v in (sys.argv[5] if len(sys.argv) > 5 else "820,600,1060,800").split(",")]
S = int(sys.argv[6]) if len(sys.argv) > 6 else 4
sd = cv2.imread(skyp)
img = cv2.resize(sd[y0:y1, x0:x1], None, fx=S, fy=S, interpolation=cv2.INTER_NEAREST)
z = np.load(rows); A, Y, c = z["A"], z["Y"], z["c"]
cols = [(0, 255, 0), (255, 0, 255), (0, 255, 255), (255, 255, 0), (255, 128, 0), (128, 128, 255), (255, 255, 255)]
for k, cc in enumerate(float(v) for v in cl.split(",")):
    r = int(np.argmin(abs(c - cc)))
    P = fr.cam.project(fr.world(c[r:r + 1], A[r:r + 1], Y[r:r + 1]).reshape(-1, 3))
    q = ((P[:, :2] - [x0, y0]) * S).round().astype(np.int32)
    cv2.polylines(img, [q], False, cols[k % len(cols)], 1)
    ins = np.nonzero((q[:, 0] > 0) & (q[:, 0] < img.shape[1]) & (q[:, 1] > 0) & (q[:, 1] < img.shape[0]))[0]
    if len(ins):
        cv2.putText(img, "%.1f" % c[r], tuple(int(v) for v in q[ins[len(ins) // 2]]), 0, 0.45, cols[k % len(cols)], 1)
cv2.imwrite(out, img)
