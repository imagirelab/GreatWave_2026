# -*- coding: utf-8 -*-
"""cv2 だけで描く簡単な折れ線の図（matplotlib がないため）。"""
import numpy as np
import cv2

PAL = [(31, 119, 180), (255, 127, 14), (44, 160, 44), (214, 39, 40), (148, 103, 189), (140, 86, 75), (227, 119, 194),
       (127, 127, 127), (188, 189, 34), (23, 190, 207), (0, 0, 0), (255, 0, 255), (0, 128, 255), (128, 0, 0)]


class Plot:
    def __init__(self, w, h, xlim, ylim, title="", equal=False, margin=50, gx=5, gy=5):
        self.w, self.h, self.m = w, h, margin
        self.gx, self.gy = gx, gy
        self.x0, self.x1 = xlim
        self.y0, self.y1 = ylim
        if equal:
            sx = (w - 2 * margin) / (self.x1 - self.x0); sy = (h - 2 * margin) / (self.y1 - self.y0)
            s = min(sx, sy)
            self.sx = self.sy = s
        else:
            self.sx = (w - 2 * margin) / (self.x1 - self.x0); self.sy = (h - 2 * margin) / (self.y1 - self.y0)
        self.img = np.full((h, w, 3), 255, np.uint8)
        cv2.putText(self.img, title, (margin, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        self.legend = []
        self._axes()

    def px(self, x, y):
        return np.stack([self.m + (np.asarray(x) - self.x0) * self.sx, self.h - self.m - (np.asarray(y) - self.y0) * self.sy], -1)

    def _axes(self):
        sx, sy = self.gx, self.gy
        for k, gx in enumerate(np.arange(np.ceil(self.x0 / sx) * sx, self.x1 + 1e-9, sx)):
            p = self.px([gx, gx], [self.y0, self.y1]).astype(int)
            major = abs((gx / (2 * sx)) - round(gx / (2 * sx))) < 1e-6
            cv2.line(self.img, tuple(p[0]), tuple(p[1]), (215, 215, 215) if major else (235, 235, 235), 1)
            if major:
                cv2.putText(self.img, "%g" % gx, (int(p[0][0]) - 8, self.h - self.m + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)
        for gy in np.arange(np.ceil(self.y0 / sy) * sy, self.y1 + 1e-9, sy):
            p = self.px([self.x0, self.x1], [gy, gy]).astype(int)
            major = abs((gy / (2 * sy)) - round(gy / (2 * sy))) < 1e-6
            cv2.line(self.img, tuple(p[0]), tuple(p[1]), (215, 215, 215) if major else (235, 235, 235), 1)
            cv2.putText(self.img, "%g" % gy, (4, int(p[0][1]) + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (80, 80, 80), 1)

    def line(self, x, y, k=0, label=None, th=1, col=None):
        col = col or PAL[k % len(PAL)][::-1]
        P = self.px(x, y)
        ok = np.all(np.isfinite(P), 1)
        P = P[ok]
        if len(P) > 1:
            cv2.polylines(self.img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], False, col, th, cv2.LINE_AA)
        if label:
            self.legend.append((label, col))

    def dots(self, x, y, k=0, r=3, col=None):
        col = col or PAL[k % len(PAL)][::-1]
        for p in self.px(np.atleast_1d(x), np.atleast_1d(y)):
            if np.all(np.isfinite(p)):
                cv2.circle(self.img, (int(p[0]), int(p[1])), r, col, -1, cv2.LINE_AA)

    def finish(self, path=None):
        for i, (lab, col) in enumerate(self.legend):
            y = 40 + 16 * i
            cv2.line(self.img, (self.w - 230, y), (self.w - 200, y), col, 2)
            cv2.putText(self.img, lab, (self.w - 195, y + 4), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        if path:
            cv2.imwrite(path, self.img)
        return self.img
