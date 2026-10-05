# -*- coding: utf-8 -*-
"""Q21 candidate A3b: section series plot of a rows npz (red = candidate, with the landmark columns; optional grey =
another rows npz).  usage: py -3.10 candA3b_plot.py rows.npz out.png c1,c2,... [other.npz] [--raw]"""
import sys, os, numpy as np
from PIL import Image, ImageDraw, ImageFont
FONT = r"C:\Windows\Fonts\Deng.ttf"
LM = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_corner": 314, "j_facebot": 379, "j_E": 394}


def main():
    z = np.load(sys.argv[1]); out = sys.argv[2]; cs = [float(x) for x in sys.argv[3].split(",")]
    other = np.load(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].endswith(".npz") else None
    raw = "--raw" in sys.argv
    A, Y, c = (z["A_raw"], z["Y_raw"], z["c"]) if raw else (z["A"], z["Y"], z["c"])
    W_, H_ = 480, 330; xl = (-22.0, 16.0); yl = (-6.0, 24.0)
    sx = W_ / (xl[1] - xl[0]); sy = H_ / (yl[1] - yl[0]); cols = 4
    rows_n = (len(cs) + cols - 1) // cols
    im = Image.new("RGB", (W_ * cols, (H_ + 8) * rows_n), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 14)
    for k, cc in enumerate(cs):
        ox = (k % cols) * W_; oy = (k // cols) * (H_ + 8)
        X = lambda a, y: (ox + (a - xl[0]) * sx, oy + H_ - (y - yl[0]) * sy)
        for g in range(-20, 17, 5):
            d.line([X(g, yl[0]), X(g, yl[1])], fill=(228, 228, 228))
        for g in range(-5, 25, 5):
            d.line([X(xl[0], g), X(xl[1], g)], fill=(228, 228, 228) if g else (150, 170, 220))
        if other is not None:
            r2 = int(np.argmin(np.abs(other["c"] - cc)))
            d.line([X(a, y) for a, y in zip(other["A"][r2], other["Y"][r2])], fill=(150, 150, 150), width=1)
        r = int(np.argmin(np.abs(c - cc)))
        d.line([X(a, y) for a, y in zip(A[r], Y[r])], fill=(210, 30, 30), width=2)
        for nm, j in LM.items():
            px, py = X(A[r, j], Y[r, j]); d.ellipse([px - 3, py - 3, px + 3, py + 3], fill=(0, 0, 0))
        for j in range(0, 400, 20):
            px, py = X(A[r, j], Y[r, j]); d.ellipse([px - 1, py - 1, px + 1, py + 1], fill=(40, 90, 200))
        d.text((ox + 4, oy + 2), "c = %+.2f (row %d)  H %.2f" % (c[r], r, Y[r].max()), fill=(0, 0, 0), font=f)
    im.save(out)


if __name__ == "__main__":
    main()
