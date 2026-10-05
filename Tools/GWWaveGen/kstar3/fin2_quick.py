# -*- coding: utf-8 -*-
"""Q20 final loop 2: quick painting-view coverage check of a rows npz (holes / spill vs the painting, gate items).
usage: py -3.10 fin2_quick.py rows.npz [--gate]"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import fin_eval as FE
V1, tgt, fr = C.painting_frame()
import gw_wavegen as G0
z = np.load(sys.argv[1]); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
s = FE.sky_diff(fr, tgt, V1, G0, c, A, Y, os.path.splitext(sys.argv[1])[0] + "_qsky.png")
print("holes", s["vs_painting_holes_in_wave"]["px"], s["vs_painting_holes_in_wave"]["largest_area_x0y0x1y1"][:4])
print("spill", s["vs_painting_spill_into_sky"]["px"], s["vs_painting_spill_into_sky"]["largest_area_x0y0x1y1"][:4])
if "--gate" in sys.argv:
    g = V1.preview_metrics(fr, tgt, fr.world(c, A, Y), V1.triangles(A.shape[1], A.shape[0]), os.path.splitext(sys.argv[1])[0] + "_qgate.png", "q")
    print(json.dumps({k: (round(v["max_px"], 2), round(v["p95_px"], 2)) for k, v in g.items()}))
if "--who" in sys.argv:
    import collections
    X = fr.world(c, A, Y).reshape(-1, 3); P = fr.cam.project(X)
    sdf = tgt.sample(P[:, :2], comp=True)
    inf = (P[:, 0] >= tgt.x0) & (P[:, 0] <= tgt.x1) & (P[:, 1] < 786) & (P[:, 2] > 1)
    bad = np.nonzero(inf & (sdf > 1.0))[0]
    r = bad // A.shape[1]; j = bad % A.shape[1]
    cnt = collections.Counter(zip(np.round(c[r], 1), (j // 10) * 10))
    print("spilling vertices", len(bad)); print(sorted(cnt.items(), key=lambda t: -t[1])[:40])
if "--foot" in sys.argv:
    import cv2
    im = cv2.imread(os.path.splitext(sys.argv[1])[0] + "_qsky.png")
    reg = im[730:788, 900:1010]
    hole = ((reg[..., 2] == 255) & (reg[..., 1] == 0)).sum(); spill = ((reg[..., 0] == 255) & (reg[..., 1] == 160)).sum()
    print("foot region holes %d spill %d" % (hole, spill))
