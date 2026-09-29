# -*- coding: utf-8 -*-
"""K*′ 精修 R4：上から見た背のくびれ（notch）を高さ 1〜16 m のすべてで測る（評審 2 の読み：±4 m の弦、弦の両端が範囲の中の所だけ）。py -3.10
各高さ h の背（列 0〜頂）の平面の位置 a_b(c) を 0.5 m おきに取り、a_b(c) − (a_b(c−4) + a_b(c+4))/2 の最大（+ = 前へ出る = くびれ）。
区間は c −10〜+12（高さ 1〜16 m）と c −30〜−10（高さ 1〜4.5 m、手前の足）。
usage: py -3.10 kh_R4_notch.py label=rows.npz|design.json ...
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402


def back_line(c, A, Y, h):
    nv = len(c)
    H = Y.max(1); top = Y.argmax(1)
    ab = np.full(nv, np.nan)
    for r in range(nv):
        if H[r] < h + 0.3:
            continue
        yy = Y[r, :top[r] + 1]; aa = A[r, :top[r] + 1]
        i = np.nonzero(yy >= h)[0]
        if len(i) == 0 or i[0] == 0:
            continue
        i = i[0]; t = (h - yy[i - 1]) / (yy[i] - yy[i - 1]); ab[r] = aa[i - 1] + t * (aa[i] - aa[i - 1])
    return ab


def notch_table(c, A, Y, heights=tuple(float(h) for h in range(1, 17)), c_lo=-10.0, c_hi=12.0, half=4.0):
    out = {}
    for h in heights:
        ab = back_line(c, A, Y, h)
        m = np.isfinite(ab)
        if m.sum() < 5:
            continue
        cm, am = c[m], ab[m]
        best = (-9.0, None)
        for cq in np.arange(c_lo, c_hi + 1e-9, 0.5):
            if cq - half < cm.min() or cq + half > cm.max():
                continue
            v = np.interp([cq - half, cq, cq + half], cm, am)
            dv = v[1] - 0.5 * (v[0] + v[2])
            if dv > best[0]:
                best = (float(dv), float(cq))
        if best[1] is not None:
            out["y%g" % h] = [round(best[0], 3), best[1]]
    return out


def all_notches(c, A, Y):
    main = notch_table(c, A, Y)
    foot = notch_table(c, A, Y, (1.0, 2.0, 3.0, 4.5), -30.0, -10.0)
    mx = max([v[0] for v in main.values()] + [v[0] for v in foot.values()])
    return {"c-10..+12_h1..16": main, "c-30..-10_h1..4.5": foot, "max": round(mx, 3)}


if __name__ == "__main__":
    for a in sys.argv[1:]:
        lab, p = a.split("=", 1)
        if p.endswith(".json"):
            import kh_designR4 as D
            c, A, Y, _ = D.build(D.Design.load(p))
        else:
            z = np.load(p); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
        print(lab, json.dumps(all_notches(c, A, Y)))
