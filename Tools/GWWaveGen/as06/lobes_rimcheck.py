# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：塊の縁の頂の点（断面の座標）を原画の画素へ写し、原画の層の頂の線 READ_CREST・S8 の輪の下の縁・
区域の多角形と比べる（道具。原画のカメラは測りにだけ使う）。
py -3.10 -B Tools/GWWaveGen/as06/lobes_rimcheck.py <design.json>
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lobes_common as L  # noqa: E402
import lobes_build as LB  # noqa: E402

S5 = L.B.S5 if hasattr(L.B, "S5") else None
import s5_common as S  # noqa: E402

S8_EDGE = np.array([(948, 803), (1031, 852), (1214, 939), (1399, 1006)], float)


def main():
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    cam = S.CAM_SEC
    for key in ("r2", "r3"):
        st = d["lobes"][key]
        q = LB.rim_line(key, st)
        rc = np.array(L.B.READ_CREST[key], float)
        print("==", key)
        for t in np.linspace(0, len(q) - 1, 11).astype(int):
            a, y, c = q[t]
            px, fr = S.sec_to_ref_px(np.array([[a, y, c]]))
            x, yy = px[0]
            dist = float(np.linalg.norm(L.B.K.world(np.array([c]), np.array([[a]]), np.array([[y]])).reshape(3) - L.B.K.CAM_POS_U))
            rcy = np.interp(x, rc[:, 0], rc[:, 1], left=np.nan, right=np.nan)
            s8 = np.interp(x, S8_EDGE[:, 0], S8_EDGE[:, 1], left=np.nan, right=np.nan)
            regs = [k for k in ("r1", "r2", "r3", "r4") if S.in_poly(px, S.REG[k], 0)[0]]
            print("c %6.2f a %5.2f y %5.2f (%.3f H0) d %5.1f -> px (%6.1f, %6.1f)  READ_CREST %6.1f  S8edge %6.1f  %s" % (c, a, y, y / L.H0, dist, x, yy, rcy, s8, regs))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
