# -*- coding: utf-8 -*-
"""small cv2 plotting helpers for section inspection (work images only)."""
import numpy as np, cv2
from candB_common import *


def allowed_img(cf, a0=-30, a1=25, y0=-4, y1=26, st=0.05, margin=1.0):
    from candB_geom import inside_px
    aa = np.arange(a0, a1, st); yy = np.arange(y0, y1, st)
    Ag, Yg = np.meshgrid(aa, yy)
    P = O[None, None, :] + Ag[..., None] * T + Yg[..., None] * UP + cf * E
    d = inside_px(P) >= margin
    return aa, yy, d


class Canvas:
    def __init__(self, a0=-30, a1=25, y0=-4, y1=26, st=0.05, bg=None):
        self.a0, self.a1, self.y0, self.y1, self.st = a0, a1, y0, y1, st
        W = int((a1 - a0) / st); H = int((y1 - y0) / st)
        self.img = np.full((H, W, 3), 245, np.uint8) if bg is None else bg
        for g in range(int(np.ceil(a0 / 5) * 5), int(a1) + 1, 5):
            x, _ = self.pt(g, 0); cv2.line(self.img, (x, 0), (x, H), (215, 215, 215), 1)
        for g in range(int(np.ceil(y0 / 5) * 5), int(y1) + 1, 5):
            _, y = self.pt(0, g); cv2.line(self.img, (0, y), (W, y), (215, 215, 215) if g else (160, 120, 60), 1)

    def pt(self, a, y):
        return int(round((a - self.a0) / self.st)), int(round((self.y1 - y) / self.st))

    def poly(self, a, y, col, th=2):
        P = np.array([self.pt(x, z) for x, z in zip(a, y)], np.int32)
        cv2.polylines(self.img, [P], False, col, th, cv2.LINE_AA)

    def dots(self, a, y, idx, col, r=5):
        for j in idx:
            cv2.circle(self.img, self.pt(a[j], y[j]), r, col, -1)

    def text(self, s, xy=(10, 40), col=(0, 0, 0), sc=1.0):
        cv2.putText(self.img, s, xy, 0, sc, col, 2, cv2.LINE_AA)

    def allowed(self, cf, margin=1.0):
        aa, yy, d = allowed_img(cf, self.a0, self.a1, self.y0, self.y1, self.st, margin)
        m = d[::-1]
        self.img[m] = (self.img[m] * 0.55 + np.array([255, 255, 255]) * 0.45).astype(np.uint8)
        self.img[~m] = (self.img[~m] * 0.6 + np.array([60, 50, 40]) * 0.4).astype(np.uint8)

    def save(self, fn, scale=0.5):
        cv2.imwrite(fn, cv2.resize(self.img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA))
