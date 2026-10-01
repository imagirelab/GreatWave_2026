# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：行の断面と空の射線の禁止域（青）・原画視点で見える四角形（赤）を並べた図（cv2 で描く。matplotlib はない）。
usage: py -3.10 r01_shoulder_secplot.py <out.png> <rows.npz> [<rows2.npz> ...] [c=-12,-8,...]
最初の rows は黒、2 つ目以降は青・橙の線で重ねる。"""
import os
import sys

import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402

R = S.R


def main():
    out = sys.argv[1]
    paths = [a for a in sys.argv[2:] if "=" not in a]
    opts = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    cs = [float(v) for v in opts.get("c", "-12,-8,-4,-1,1,3,5,7,9,11,13,14.4").split(",")]
    rows = [S.load_rows(p) for p in paths]
    c = rows[0][0]
    G = R.keepout_grids(c, 3, 2, cache=S.KEEPOUT_CACHE)
    vis = None
    vp = os.path.join(S.OUT, "quick", "vis_base.npy")
    if os.path.isfile(vp):
        vis = np.load(vp)
    a0, a1, y0, y1 = -34.0, 14.0, -3.0, 29.0
    sc = 12
    W, H = int((a1 - a0) * sc), int((y1 - y0) * sc)
    cols = [(0, 0, 0), (200, 90, 20), (0, 140, 255), (0, 160, 0)]
    tiles = []
    for cc in cs:
        r = int(np.argmin(np.abs(c - cc)))
        img = np.full((H, W, 3), 255, np.uint8)
        g = G[r]
        ys, xs = np.nonzero(g)
        aa = R.GA0 + xs * R.GRES; yy = R.GY0 + ys * R.GRES
        px = ((aa - a0) * sc).astype(int); py = (H - 1 - (yy - y0) * sc).astype(int)
        m = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        img[py[m], px[m]] = (250, 225, 200)
        for gx in range(int(a0), int(a1) + 1, 2):
            cv2.line(img, (int((gx - a0) * sc), 0), (int((gx - a0) * sc), H - 1), (235, 235, 235) if gx % 10 else (200, 200, 200), 1)
        for gy in range(int(y0), int(y1) + 1, 2):
            cv2.line(img, (0, int(H - 1 - (gy - y0) * sc)), (W - 1, int(H - 1 - (gy - y0) * sc)), (235, 235, 235) if gy % 10 else (200, 200, 200), 1)
        for k, (cc_, A, Y) in enumerate(rows):
            P = np.c_[(A[r] - a0) * sc, H - 1 - (Y[r] - y0) * sc].astype(np.int32)
            cv2.polylines(img, [P], False, cols[k % 4], 2 if k == 0 else 1, cv2.LINE_AA)
            if k == 0 and vis is not None:
                v = np.zeros(A.shape[1], bool); v[:-1] |= vis[r]; v[1:] |= vis[r]
                for q in P[v]:
                    cv2.circle(img, tuple(int(t) for t in q), 2, (0, 0, 230), -1)
            for j, col in ((18, (0, 150, 0)), (78, (200, 0, 200)), (90, (255, 0, 0)), (200, (200, 200, 0)), (314, (0, 200, 200))):
                cv2.circle(img, (int(P[j, 0]), int(P[j, 1])), 4, col, -1 if k == 0 else 1)
        cv2.putText(img, "c=%.1f" % c[r], (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        tiles.append(img)
    ncol = 4
    while len(tiles) % ncol:
        tiles.append(np.full_like(tiles[0], 255))
    rows_img = [np.hstack(tiles[i:i + ncol]) for i in range(0, len(tiles), ncol)]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    cv2.imwrite(out, np.vstack(rows_img))


if __name__ == "__main__":
    main()
