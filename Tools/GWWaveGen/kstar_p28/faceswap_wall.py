# -*- coding: utf-8 -*-
"""仕上げ28 第1回：背と管の内側の壁の間の厚み（行ごと、高さごと）を測る（py -3.10）。管が背を突き抜けていないかの検査に使う。"""
import numpy as np


def wall_thickness(a, y, jB=18, jc=90, jt0=200, jt1=380, nh=40, hmin=0.05, hmax=0.95):
    """1 行：各高さ h で、背（列 jB..jc）の a と、管の内側の壁（列 jt0..jt1 の、その高さの最も後ろの a）の差（m）。"""
    H = float(y[jc])
    if H < 0.5:
        return None
    hs = np.linspace(hmin * H, hmax * H, nh)

    def cross(ta, ty, pick):
        out = np.full(len(hs), np.nan)
        for k in range(len(ta) - 1):
            y0, y1 = ty[k], ty[k + 1]
            lo, hi = min(y0, y1), max(y0, y1)
            m = (hs >= lo) & (hs <= hi) & (hi > lo)
            if m.any():
                t = (hs[m] - y0) / (y1 - y0)
                v = ta[k] + t * (ta[k + 1] - ta[k])
                out[m] = np.where(np.isnan(out[m]), v, pick(out[m], v))
        return out
    back = cross(a[jB:jc + 1], y[jB:jc + 1], np.maximum)       # 背：その高さの最も前の点
    wall = cross(a[jt0:jt1], y[jt0:jt1], np.minimum)          # 管の壁：その高さの最も後ろの点
    return hs, back, wall, wall - back


def summary(c, A, Y, rows=None):
    out = []
    rows = range(len(c)) if rows is None else rows
    for r in rows:
        w = wall_thickness(A[r], Y[r])
        if w is None:
            continue
        hs, b, wl, t = w
        ok = np.isfinite(t)
        if ok.any():
            out.append((float(c[r]), float(np.nanmin(t)), float(hs[ok][int(np.nanargmin(t[ok]))]), float(Y[r, 90])))
    return out
