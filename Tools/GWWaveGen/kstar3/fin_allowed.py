# -*- coding: utf-8 -*-
"""Q20 final (K*'): painting-view allowed region per row plane (diagnostic, no model data).

For a plane c = const of the K* section frame, a point (a, y) may hold surface without touching the painting gate if its
PaintingCam v1 image is inside the painted big-wave region (raw sky sdf < -margin), below the horizon, or outside the
scored frame.  The rows of candidates are drawn on top.
usage: py -3.10 fin_allowed.py out.png rowsA.npz[:label] [rowsB.npz[:label] ...] --cs -10,-5,0,2,4,5,6,8,10,12
"""
import sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

HORIZON = 787.7


def allowed_grid(fr, tgt, c0, a_rng=(-30.0, 20.0), y_rng=(-5.0, 26.0), res=0.1, margin=0.0):
    aa = np.arange(a_rng[0], a_rng[1] + 1e-9, res); yy = np.arange(y_rng[0], y_rng[1] + 1e-9, res)
    A, Y = np.meshgrid(aa, yy)
    X = C.world(np.full(A.shape[0], c0), A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    s = tgt.sample(P[:, :2], comp=False)
    ok = (s < -margin) | (P[:, 1] > HORIZON) | (P[:, 0] < tgt.x0) | (P[:, 0] > tgt.x1) | (P[:, 2] <= 0.5)
    return aa, yy, ok.reshape(A.shape), s.reshape(A.shape)


def main():
    args = sys.argv[1:]
    out = args[0]
    cs = [float(v) for v in args[args.index("--cs") + 1].split(",")] if "--cs" in args else [-10, -5, 0, 2, 4, 5, 6, 8, 10, 12]
    rows = [a for a in args[1:] if a.endswith(".npz") or ".npz:" in a]
    V1, tgt, fr = C.painting_frame()
    cols = [(215, 40, 40), (40, 90, 220), (30, 160, 60), (200, 120, 20)]
    data = []
    for k, r in enumerate(rows):
        p, lab = (r.split(".npz:")[0] + ".npz", r.split(".npz:")[1]) if ".npz:" in r else (r, os.path.basename(r))
        z = np.load(p); data.append((lab, z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)))
    W, H = 500, 310; res = 0.1
    ncol = 4; nrow = int(np.ceil(len(cs) / ncol))
    img = np.full((nrow * (H + 24) + 30, ncol * W, 3), 255, np.uint8)
    for i, c0 in enumerate(cs):
        aa, yy, ok, s = allowed_grid(fr, tgt, c0, res=res)
        tile = np.where(ok[::-1, :, None], np.array([235, 225, 205], np.uint8), np.array([250, 250, 250], np.uint8))
        tile = cv2.resize(tile, (W, H), interpolation=cv2.INTER_NEAREST)
        def px(a, y):
            return np.stack([(a - aa[0]) / (aa[-1] - aa[0]) * (W - 1), (yy[-1] - y) / (yy[-1] - yy[0]) * (H - 1)], -1)
        for g in range(-30, 21, 5):
            x = int(px(np.array([g]), np.array([0]))[0, 0]); cv2.line(tile, (x, 0), (x, H), (220, 220, 220), 1)
        for g in range(-5, 26, 5):
            y = int(px(np.array([0]), np.array([g]))[0, 1]); cv2.line(tile, (0, y), (W, y), (200, 200, 230) if g == 0 else (220, 220, 220), 1)
        for k, (lab, A, Y, c) in enumerate(data):
            r = int(np.argmin(np.abs(c - c0)))
            if abs(c[r] - c0) > 0.35:
                continue
            q = px(A[r], Y[r]).round().astype(np.int32)
            cv2.polylines(tile, [q], False, cols[k % len(cols)], 2 if k == 0 else 1, cv2.LINE_AA)
        cv2.putText(tile, "c=%+.1f" % c0, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1)
        ox = (i % ncol) * W; oy = 30 + (i // ncol) * (H + 24)
        img[oy:oy + H, ox:ox + W] = tile
    t = "allowed (painted wave / below horizon / outside frame) = beige; grid 5 m; " + " ".join("%s=%s" % (["red", "blue", "green", "orange"][k], d[0]) for k, d in enumerate(data))
    cv2.putText(img, t, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.imwrite(out, img)
    print(out)


if __name__ == "__main__":
    main()
