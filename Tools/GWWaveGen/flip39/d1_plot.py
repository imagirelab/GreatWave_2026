# -*- coding: utf-8 -*-
"""FLIP39 D1：PIL だけで描く簡単な折れ線の図（matplotlib はこの機械の Python に入っていない）。日本語は Meiryo。"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PAL = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (255, 127, 14), (148, 103, 189), (140, 86, 75),
       (227, 119, 194), (127, 127, 127), (188, 189, 34), (23, 190, 207), (0, 0, 0)]


def font(sz, bold=False):
    for p in (("C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc"), "C:/Windows/Fonts/msgothic.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


class Sheet:
    def __init__(self, w, h, title=None):
        self.im = Image.new("RGB", (w, h), (255, 255, 255))
        self.d = ImageDraw.Draw(self.im)
        if title:
            self.d.text((16, 10), title, fill=(0, 0, 0), font=font(22, True))

    def text(self, xy, s, sz=14, col=(0, 0, 0), bold=False):
        self.d.text(xy, s, fill=col, font=font(sz, bold))

    def save(self, p):
        self.im.save(p)


class Ax:
    def __init__(self, sh, box, xlim, ylim, xlabel="", ylabel="", title="", xticks=None, yticks=None):
        self.sh = sh; self.d = sh.d; self.box = box; self.xlim = xlim; self.ylim = ylim
        x0, y0, x1, y1 = box
        d = self.d
        d.rectangle(box, outline=(0, 0, 0))
        f = font(12)
        if xticks is None:
            xticks = np.linspace(xlim[0], xlim[1], 6)
        if yticks is None:
            yticks = np.linspace(ylim[0], ylim[1], 6)
        for v in xticks:
            px = self.px(v, ylim[0])[0]
            d.line([(px, y1), (px, y1 + 4)], fill=(0, 0, 0)); d.line([(px, y0), (px, y1)], fill=(235, 235, 235))
            d.text((px - 14, y1 + 6), self._fmt(v), fill=(0, 0, 0), font=f)
        for v in yticks:
            py = self.px(xlim[0], v)[1]
            d.line([(x0 - 4, py), (x0, py)], fill=(0, 0, 0)); d.line([(x0, py), (x1, py)], fill=(235, 235, 235))
            d.text((x0 - 44, py - 8), self._fmt(v), fill=(0, 0, 0), font=f)
        d.rectangle(box, outline=(0, 0, 0))
        d.text((x0 + (x1 - x0) // 2 - 6 * len(xlabel), y1 + 24), xlabel, fill=(0, 0, 0), font=font(13))
        d.text((x0 - 46, y0 - 22), ylabel, fill=(0, 0, 0), font=font(13))
        d.text((x0, y0 - 42), title, fill=(0, 0, 0), font=font(15, True))
        self.leg = []

    @staticmethod
    def _fmt(v):
        return ("%.0f" % v) if abs(v - round(v)) < 1e-6 or abs(v) >= 10 else ("%.2f" % v).rstrip("0").rstrip(".")

    def px(self, x, y):
        x0, y0, x1, y1 = self.box
        X = x0 + (x - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * (x1 - x0)
        Y = y1 - (y - self.ylim[0]) / (self.ylim[1] - self.ylim[0]) * (y1 - y0)
        return X, Y

    def line(self, x, y, col=(0, 0, 0), w=2, label=None, dash=False):
        x = np.asarray(x, float); y = np.asarray(y, float)
        ok = np.isfinite(x) & np.isfinite(y)
        pts = []
        segs = []
        for xi, yi, o in zip(x, y, ok):
            if o:
                X, Y = self.px(xi, yi)
                x0, y0, x1, y1 = self.box
                pts.append((min(max(X, x0), x1), min(max(Y, y0), y1)))
            elif pts:
                segs.append(pts); pts = []
        if pts:
            segs.append(pts)
        for s in segs:
            if len(s) > 1:
                if dash:
                    for i in range(0, len(s) - 1, 2):
                        self.d.line(s[i:i + 2], fill=col, width=w)
                else:
                    self.d.line(s, fill=col, width=w)
        if label:
            self.leg.append((label, col, dash))

    def points(self, x, y, col=(0, 0, 0), r=3, label=None):
        for xi, yi in zip(np.atleast_1d(x), np.atleast_1d(y)):
            if np.isfinite(xi) and np.isfinite(yi):
                X, Y = self.px(xi, yi)
                self.d.ellipse([X - r, Y - r, X + r, Y + r], fill=col)
        if label:
            self.leg.append((label, col, False))

    def hline(self, y, col=(120, 120, 120)):
        a, b = self.px(self.xlim[0], y), self.px(self.xlim[1], y)
        self.d.line([a, b], fill=col, width=1)

    def vline(self, x, col=(120, 120, 120), label=None):
        a, b = self.px(x, self.ylim[0]), self.px(x, self.ylim[1])
        self.d.line([a, b], fill=col, width=1)
        if label:
            self.d.text((a[0] + 3, b[1] + 2), label, fill=col, font=font(11))

    def legend(self, where="tr", sz=12):
        x0, y0, x1, y1 = self.box
        f = font(sz)
        wmax = max([self.d.textlength(l, font=f) for l, _, _ in self.leg] + [10])
        X = x1 - wmax - 40 if where.endswith("r") else x0 + 8
        Y = y0 + 6 if where.startswith("t") else y1 - 6 - 17 * len(self.leg)
        self.d.rectangle([X - 4, Y - 2, X + wmax + 34, Y + 17 * len(self.leg) + 2], fill=(255, 255, 255), outline=(180, 180, 180))
        for i, (l, c, dash) in enumerate(self.leg):
            yy = Y + 17 * i + 8
            if dash:
                self.d.line([(X, yy), (X + 8, yy)], fill=c, width=3); self.d.line([(X + 14, yy), (X + 22, yy)], fill=c, width=3)
            else:
                self.d.line([(X, yy), (X + 22, yy)], fill=c, width=3)
            self.d.text((X + 28, yy - 8), l, fill=(0, 0, 0), font=f)


def colormap(v, vmin, vmax):
    """青（低い）→ 白 → 赤（高い）。"""
    t = np.clip((v - vmin) / (vmax - vmin), 0, 1)
    r = np.where(t < 0.5, 2 * t, 1.0); b = np.where(t < 0.5, 1.0, 2 * (1 - t)); g = np.where(t < 0.5, 2 * t, 2 * (1 - t))
    rgb = np.stack([r, g, b], -1)
    rgb = np.where(np.isfinite(v)[..., None], rgb, 0.85)
    return (rgb * 255).astype(np.uint8)
