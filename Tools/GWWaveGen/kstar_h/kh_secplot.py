# -*- coding: utf-8 -*-
"""断面の図（cv2 だけ。py -3.10）。候補の行を c ごとに並べ、比べる候補を重ねる。
usage (module): sections_png(out, [(label, c, A, Y, (b,g,r)), ...], cs, title)"""
import numpy as np
import cv2


def _panel(w, h, xr, yr, grid=5.0):
    img = np.full((h, w, 3), 250, np.uint8)
    sx = w / (xr[1] - xr[0]); sy = h / (yr[1] - yr[0])
    s = min(sx, sy)

    def tp(a, y):
        return np.stack([(a - xr[0]) * s, h - (y - yr[0]) * s], -1)
    for g in np.arange(np.ceil(xr[0] / grid) * grid, xr[1] + 1e-9, grid):
        x = int(tp(np.array([g]), np.array([0.0]))[0, 0]); cv2.line(img, (x, 0), (x, h), (225, 225, 225), 1)
    for g in np.arange(np.ceil(yr[0] / grid) * grid, yr[1] + 1e-9, grid):
        y = int(tp(np.array([0.0]), np.array([g]))[0, 1]); cv2.line(img, (0, y), (w, y), (225, 225, 225), 1)
    y0 = int(tp(np.array([0.0]), np.array([0.0]))[0, 1]); cv2.line(img, (0, y0), (w, y0), (160, 160, 160), 1)
    return img, tp


def sections_png(out, cands, cs, title="", xr=(-26, 26), yr=(-7, 25), cols=4, pw=520, ph=330, marks=(18, 90, 200, 314, 379, 394)):
    rows = int(np.ceil(len(cs) / cols))
    canvas = np.full((rows * ph + 40, cols * pw, 3), 255, np.uint8)
    cv2.putText(canvas, title, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)
    for i, cc in enumerate(cs):
        img, tp = _panel(pw, ph, xr, yr)
        txt = "c=%+.1f" % cc
        for lab, c, A, Y, col in cands:
            r = int(np.argmin(np.abs(np.asarray(c) - cc)))
            P = tp(A[r], Y[r]).astype(np.int32)
            cv2.polylines(img, [P.reshape(-1, 1, 2)], False, col, 2 if lab == cands[0][0] else 1, cv2.LINE_AA)
            if lab == cands[0][0]:
                for j in marks:
                    cv2.circle(img, tuple(int(v) for v in P[j]), 3, (0, 0, 0), -1)
                txt += "  %s H=%.1f" % (lab, Y[r].max())
        cv2.putText(img, txt, (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        r0, c0 = divmod(i, cols)
        canvas[40 + r0 * ph:40 + (r0 + 1) * ph, c0 * pw:(c0 + 1) * pw] = img
        cv2.rectangle(canvas, (c0 * pw, 40 + r0 * ph), ((c0 + 1) * pw - 1, 40 + (r0 + 1) * ph - 1), (200, 200, 200), 1)
    cv2.imwrite(out, canvas)
    return out
