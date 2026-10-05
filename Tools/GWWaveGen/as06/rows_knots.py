# -*- coding: utf-8 -*-
"""美術の見本06 の段の行：縁の頂 E の節点を作るための下調べ（数を出すだけ）。
py -3.10 -B Tools/GWWaveGen/as06/rows_knots.py rays r2:46.5:0 r3:41:20      … READ_CREST の各点の射線の上で、原画のカメラから d m の点 (c, a, y/H0)
py -3.10 -B Tools/GWWaveGen/as06/rows_knots.py proj <design.json>          … design の E_knots を原画の画素へ写す（原画の画素 x, y）
原画のカメラは置き場の数を出すことにだけ使う（色は写さない）。
"""
import json
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import shapeB_common as B  # noqa: E402
import asm4_common as A  # noqa: E402


def main():
    if sys.argv[1] == "rays":
        for spec in sys.argv[2:]:
            key, d, dy = spec.split(":")
            if "~" in d:                      # d0~d1：原画の x の向きに、線の端から端まで距離を線形に替える
                d0, d1 = [float(v) for v in d.split("~")]
                xr = np.array(B.READ_CREST[key], float)[:, 0]
                dist = (lambda x, d0=d0, d1=d1, xa=xr.min(), xb=xr.max(): d0 + (d1 - d0) * (x - xa) / (xb - xa))
            else:
                dist = float(d)
            q, xs, ys = B.crest_curve(key, dist, n=13, dy_px=float(dy))
            print(key, "d", d, "dy_px", dy)
            for x, y, qq in zip(xs, ys, q):
                print("  x %4d y %4d  -> c %.2f  a %.2f  y/H0 %.3f" % (x, y, qq[2], qq[0], qq[1] / B.H0))
    else:
        d = json.load(open(sys.argv[2], encoding="utf-8"))
        pc = A.painting_cam(1)
        for c_, a_, yh in d["E_knots"]:
            X = B.K.world(np.array([c_]), np.array([[a_]]), np.array([[yh * B.H0]])).reshape(1, 3)
            p, z = pc.project(X)
            q = A.px_to_ref(p)[0]
            print("c %.2f a %.2f y/H0 %.3f -> 原画 (%d, %d)  奥行き %.1f m" % (c_, a_, yh, q[0], q[1], float(z[0])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
