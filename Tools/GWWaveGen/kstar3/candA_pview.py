# -*- coding: utf-8 -*-
"""Q20 cand A: painting-camera coverage check of a rows npz (A, Y, c).
Writes an overlay PNG: grey = both covered, red = candidate covers the painting's sky (above the horizon),
blue = painting wave not covered by the candidate; the outline items 78/130/131/132/72 in green.
With --gate also runs V1.preview_metrics (the rubric's F01 numbers).
usage: py -3.10 candA_pview.py rows.npz out.png [--gate]"""
import sys, os, json
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C


def coverage(fr, V1, c, A, Y):
    X = fr.world(c, A, Y)
    tris = V1.triangles(A.shape[1], A.shape[0])
    return V1.rasterize(fr.cam, X, tris), X, tris


def main():
    rows, out = sys.argv[1], sys.argv[2]
    V1, tgt, fr = C.painting_frame()
    z = np.load(rows); A, Y, c = z["A"], z["Y"], z["c"]
    cov, X, tris = coverage(fr, V1, c, A, Y)
    Hh, Ww = cov.shape
    yy = np.arange(Hh)[:, None] * np.ones((1, Ww))
    xx = np.ones((Hh, 1)) * np.arange(Ww)[None, :]
    s = tgt.sample(np.stack([xx.ravel(), yy.ravel()], -1), comp=False).reshape(Hh, Ww)
    sky = (s > 0) & (yy < 787.7)
    wave = ~sky & (yy < 787.7)
    img = np.full((Hh, Ww, 3), 255, np.uint8)
    cv = cov > 0.5
    img[cv & wave] = (175, 175, 175)
    img[cv & sky] = (40, 40, 230)
    img[~cv & wave] = (230, 170, 60)
    img[yy >= 787.7] = (235, 235, 235)
    for k in V1.SEGS:
        P = np.round(tgt.seg[k]).astype(np.int32)
        cv2.polylines(img, [P], False, (30, 160, 30), 2)
    bad_sky = int((cv & sky).sum()); miss = int((~cv & wave & (xx >= tgt.x0) & (xx <= tgt.x1)).sum())
    cv2.putText(img, "%s  candidate on sky %d px  wave not covered %d px" % (os.path.basename(rows), bad_sky, miss), (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    cv2.imwrite(out, img)
    res = {"cand_on_sky_px": bad_sky, "wave_uncovered_px": miss}
    if "--gate" in sys.argv:
        g = V1.preview_metrics(fr, tgt, X, tris, os.path.splitext(out)[0] + "_gate.png", "cand A")
        res["gate"] = g
    print(json.dumps(res))


if __name__ == "__main__":
    main()
