# -*- coding: utf-8 -*-
"""A2 diagnostic: row sections over the painting's allowed region, painting-view visible vertices in red, hidden in
blue.  usage: py -3.10 candA2_diag.py rows.npz out.png [--cs -8,-6,...] [--rows2 other.npz]"""
import sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA2_common as K


def main():
    rows, out = sys.argv[1], sys.argv[2]
    args = sys.argv[3:]
    cs = [float(v) for v in args[args.index("--cs") + 1].split(",")] if "--cs" in args else [-10, -8, -6, -4, -2, 0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12]
    A, Y, c = K.load_rows(rows)
    vis, _ = K.visibility(c, A, Y)
    other = None
    if "--rows2" in args:
        other = K.load_rows(args[args.index("--rows2") + 1])
    W, H = 520, 320
    a_rng, y_rng = (-30.0, 22.0), (-6.0, 26.0)
    ncol = 4; nrow = int(np.ceil(len(cs) / ncol))
    img = np.full((nrow * (H + 6) + 26, ncol * (W + 6), 3), 255, np.uint8)
    for i, c0 in enumerate(cs):
        aa, yy, ok, s = K.allowed_grid(c0, a_rng, y_rng, res=0.1)
        tile = np.where(ok[::-1, :, None], np.array([222, 214, 200], np.uint8), np.array([252, 252, 252], np.uint8))
        tile = cv2.resize(tile, (W, H), interpolation=cv2.INTER_NEAREST)
        def px(a, y):
            return np.stack([(a - a_rng[0]) / (a_rng[1] - a_rng[0]) * (W - 1), (y_rng[1] - y) / (y_rng[1] - y_rng[0]) * (H - 1)], -1)
        for g in range(-30, 23, 5):
            x = int(px(np.array([g]), np.array([0]))[0, 0]); cv2.line(tile, (x, 0), (x, H), (205, 205, 205), 1)
        for g in range(-5, 27, 5):
            yv = int(px(np.array([0]), np.array([g]))[0, 1]); cv2.line(tile, (0, yv), (W, yv), (150, 150, 210) if g == 0 else (205, 205, 205), 1)
        r = int(np.argmin(np.abs(c - c0)))
        if other is not None:
            A2, Y2, c2 = other; r2 = int(np.argmin(np.abs(c2 - c0)))
            q = px(A2[r2], Y2[r2]).round().astype(np.int32); cv2.polylines(tile, [q], False, (60, 170, 60), 1, cv2.LINE_AA)
        q = px(A[r], Y[r]).round().astype(np.int32)
        for j in range(len(q) - 1):
            col = (40, 40, 230) if (vis[r, j] and vis[r, j + 1]) else (200, 90, 30)
            cv2.line(tile, tuple(q[j]), tuple(q[j + 1]), col, 2, cv2.LINE_AA)
        for j, nm in ((90, "T"), (200, "t"), (314, "k"), (379, "b")):
            cv2.circle(tile, tuple(q[j]), 3, (0, 0, 0), -1)
        cv2.putText(tile, "c=%+.1f (row %d)" % (c[r], r), (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
        ox = (i % ncol) * (W + 6); oy = 26 + (i // ncol) * (H + 6)
        img[oy:oy + H, ox:ox + W] = tile
    cv2.putText(img, "beige = allowed by the painting view; red = visible from PaintingCam, blue = hidden; green = other; grid 5 m",
                (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
    cv2.imwrite(out, img)
    print(out, "visible vertex share", vis.mean())


if __name__ == "__main__":
    main()
