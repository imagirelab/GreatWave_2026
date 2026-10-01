# -*- coding: utf-8 -*-
# 仕上げ28：pl28_fr_motion.py（設計28修正01 の最終の評審の断面の走査の写し）の頂の ±2 m 弦角 crest_chord と張り出し lo_ratio を、
# 引数を読まずに import できるように写したもの（式は同じ）。pl28_probe_cap.py などが使う。
import numpy as np

jB, jE, jTIP = 18, 394, 200


def crest_chord(A, Y, L=2.0):
    res = []
    for r in range(A.shape[0]):
        a, y = A[r, jB:jE + 1], Y[r, jB:jE + 1]
        jc = int(np.argmax(y)); s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(a), np.diff(y)))])
        sc = s[jc]
        if sc - L < 0 or sc + L > s[-1]:
            res.append(np.nan); continue
        pa = np.array([np.interp(sc - L, s, a), np.interp(sc - L, s, y)]); pb = np.array([np.interp(sc + L, s, a), np.interp(sc + L, s, y)])
        pc = np.array([a[jc], y[jc]]); u, v = pa - pc, pb - pc
        nu_, nv_ = np.linalg.norm(u), np.linalg.norm(v)
        if nu_ < 1e-9 or nv_ < 1e-9:
            res.append(np.nan); continue
        res.append(float(np.degrees(np.arccos(np.clip(u @ v / nu_ / nv_, -1, 1)))))
    return res


def lo_ratio(A, Y, r, SF):
    a, y = A[r, jB:jE + 1] * SF, Y[r, jB:jE + 1]
    jc = int(np.argmax(y)); H = y[jc]
    if H <= 0.05:
        return 0.0
    Fa, Fy = a[jc:], y[jc:]; ok = Fy > 0.05 * H
    ra = np.maximum.accumulate(np.where(ok, Fa, -1e9))
    return float(np.max(np.where(ok, ra - Fa, 0.0)) / H)


