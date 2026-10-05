# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：作り直した行の断面の図（道具。判定ではない）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_plot.py <prefix> <out.png> [c,c,...]
灰 = 見本04 AS04F、薄緑 = 見本05 B10、青 = 新しい行（層の印の所は ② 緑・③ 水色）、赤の点 = 塊の縁の頂 R。横線 = 0.4・0.5 H0。
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lobes_common as L  # noqa: E402

B = L.B


def main():
    pre, out = sys.argv[1], sys.argv[2]
    cs = [float(v) for v in sys.argv[3].split(",")] if len(sys.argv) > 3 else [-23.0, -21.5, -20.0, -18.5, -17.0, -15.5, -14.5, -13.5, -12.0, -10.5, -9.5, -8.6]
    z = np.load(pre + "_rows.npz"); c, A, Y = z["c"], z["A"], z["Y"]
    lab = np.load(pre + "_labels.npy")
    c0, A0, Y0 = B.load_rows(L.ROWS04F)
    zb = np.load(L.ROWS05B); Ab, Yb = zb["A"], zb["Y"]
    log = json.load(open(pre + "_build_log.json", encoding="utf-8"))["log"]["rows"]
    W, H = 520, 380
    ncol = 4
    nrow = (len(cs) + ncol - 1) // ncol
    img = np.full((H * nrow, W * ncol, 3), 250, np.uint8)
    sc = 20.0
    for k, cc in enumerate(cs):
        i = int(np.argmin(np.abs(c - cc)))
        ox, oy = (k % ncol) * W, (k // ncol) * H
        P = lambda a, y: (int(ox + W * 0.38 + a * sc), int(oy + H - 40 - y * sc))
        for yy in (0.0, 0.4 * L.H0, 0.5 * L.H0, 0.6 * L.H0):
            cv2.line(img, P(-12, yy), P(14, yy), (215, 215, 215), 1)
        for AA, YY, col, t in ((A0, Y0, (170, 170, 170), 1), (Ab, Yb, (150, 220, 150), 1), (A, Y, (190, 60, 30), 2)):
            pts = np.array([P(AA[i, j], YY[i, j]) for j in range(18, 396)], np.int32)
            cv2.polylines(img, [pts], False, col, t, cv2.LINE_AA)
        for j in range(18, 396):
            if lab[i, j] in (2, 3):
                cv2.circle(img, P(A[i, j], Y[i, j]), 2, (60, 160, 60) if lab[i, j] == 2 else (190, 170, 40), -1)
        for j, col in ((90, (0, 0, 0)), (200, (0, 0, 255)), (314, (255, 0, 255))):
            cv2.circle(img, P(A[i, j], Y[i, j]), 3, col, -1)
        r = [x for x in log if x.get("row") == i]
        tx = "c %.2f" % c[i]
        if r:
            for key in ("r2", "r3"):
                if key in r[0]:
                    R = r[0][key]["R"]
                    cv2.circle(img, P(R[0], R[1]), 4, (0, 0, 220), 1)
                    tx += " %s f%.2f" % (key, r[0][key]["f"])
        cv2.putText(img, tx, (ox + 6, oy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.rectangle(img, (ox, oy), (ox + W - 1, oy + H - 1), (200, 200, 200), 1)
    cv2.imwrite(out, img)
    print("plot", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
