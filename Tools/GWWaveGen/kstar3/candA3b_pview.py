# -*- coding: utf-8 -*-
"""Q21 candidate A3b: painting-view diagnostic of a rows npz: hue = row c, stripes = 1 m height bands, white = painted
outline (78/130/131/132/72), black = painted b-region band edges.  usage: py -3.10 candA3b_pview.py rows.npz out.png"""
import sys, os, numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C, candA3b_common as B, fin2_warp as W, fin_eval as FE


def main(rows, out):
    V1, tgt, fr = C.painting_frame(); pt = W.Painting()
    z = np.load(rows); A, Y, c = z["A"], z["Y"], z["c"]
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    tris = V1.triangles(nu, nv)
    cov = V1.rasterize(fr.cam, X, tris) > 0.5
    zb, ib = FE.zbuf_ids(P, tris, 1920, 1080)
    ok = (ib >= 0) & cov
    r = np.where(ok, np.maximum(ib, 0) // nu, 0); j = np.where(ok, np.maximum(ib, 0) % nu, 0)
    cv = c[r]; yv = Y[r, j]
    hue = np.clip((cv + 20) / 34 * 160, 0, 160)
    val = np.where((np.floor(yv) % 2) == 0, 235, 175)
    img = cv2.cvtColor(np.dstack([hue, np.full_like(hue, 200), val]).astype(np.uint8), cv2.COLOR_HSV2BGR)
    img[~ok] = (40, 40, 40)
    img[cov & ~ok] = (120, 120, 120)
    cv2.polylines(img, [np.round(pt.T).astype(np.int32)], False, (255, 255, 255), 2)
    t, b = B.band_edges()
    cv2.polylines(img, [np.round(t).astype(np.int32)], False, (0, 0, 0), 2)
    cv2.polylines(img, [np.round(b).astype(np.int32)], False, (0, 0, 0), 2)
    for k, cc in enumerate(range(-20, 15, 2)):
        col = tuple(int(x) for x in cv2.cvtColor(np.uint8([[[(cc + 20) / 34 * 160, 200, 235]]]), cv2.COLOR_HSV2BGR)[0, 0])
        cv2.putText(img, "%d" % cc, (20 + k * 50, 1060), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
    cv2.imwrite(out, img)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
