# -*- coding: utf-8 -*-
"""K*′ 精修 R4：行ごとの頂の丸さ（Q17）を測る（py -3.10）。頂の近く（y ≥ 0.85 H、列 50〜185）の断面の線について、
  （列 176 より先の唇の頭の丸い先は頂ではないので除く）
  * 最も高い点の列
  * 弧長 1 m の窓の中の向きの変わり（最大、度）
  * 弧長 ±0.5 m の 3 点の円の半径の最小（m、凸の所だけ = 上へ膨らむ所）と凹の所の最小半径
を出し、区間（主 c −5〜+3、奥 c +3〜+7、+7〜+12.5、+12.5〜+14）ごとにまとめる。
usage: py -3.10 kh_R4_top.py label=rows.npz|design.json ...
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402


def row_top(a, y, j0=50, j1=176, fr=0.85, step=0.05):
    H = y.max()
    P = np.stack([a[j0:j1 + 1], y[j0:j1 + 1]], -1)
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    q = np.arange(0.0, s[-1], step)
    X = np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)
    k = int(round(0.5 / step))
    turn, rconv, rconc = 0.0, 99.0, 99.0
    for i in range(k, len(X) - k):
        if X[i, 1] < fr * H:
            continue
        v1 = X[i] - X[i - k]; v2 = X[i + k] - X[i]
        ang = np.degrees(np.arctan2(v1[0] * v2[1] - v1[1] * v2[0], v1 @ v2))
        turn = max(turn, abs(ang))
        A_, B_, C_ = X[i - k], X[i], X[i + k]
        cr = (B_[0] - A_[0]) * (C_[1] - A_[1]) - (B_[1] - A_[1]) * (C_[0] - A_[0])
        la, lb, lc = np.linalg.norm(B_ - A_), np.linalg.norm(C_ - B_), np.linalg.norm(C_ - A_)
        R = la * lb * lc / max(2 * abs(cr), 1e-12)
        if cr < 0:          # traversal back -> front: a right turn is convex (the top bulges up)
            rconv = min(rconv, R)
        else:
            rconc = min(rconc, R)
    return {"top_col": int(j0 + np.argmax(y[j0:j1 + 1])), "turn1m_deg": round(turn, 1), "Rmin_convex": round(rconv, 2), "Rmin_concave": round(rconc, 2)}


def tops(c, A, Y):
    out = {}
    for nm, (c0, c1) in (("main -5..+3", (-5, 3)), ("far +3..+7", (3, 7)), ("far +7..+12.5", (7, 12.5)), ("end +12.5..+14", (12.5, 14))):
        rows = [r for r in range(len(c)) if c0 <= c[r] < c1 and Y[r].max() > 3.0]
        R = [row_top(A[r], Y[r]) for r in rows]
        if not R:
            continue
        out[nm] = {"top_col_range": [min(x["top_col"] for x in R), max(x["top_col"] for x in R)],
                   "turn1m_max_deg": max(x["turn1m_deg"] for x in R), "Rmin_convex_min": min(x["Rmin_convex"] for x in R),
                   "Rmin_concave_min": min(x["Rmin_concave"] for x in R)}
    return out


if __name__ == "__main__":
    for a in sys.argv[1:]:
        lab, p = a.split("=", 1)
        if p.endswith(".json"):
            import kh_designR4 as D
            c, A, Y, _ = D.build(D.Design.load(p))
        else:
            z = np.load(p); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
        print(lab, json.dumps(tops(c, A, Y)))
