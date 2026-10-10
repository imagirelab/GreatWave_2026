# -*- coding: utf-8 -*-
"""2b. 再生した形と R3 の線の距離（R3 → Unity の向き）を、R3 の線の頂点そのものと 0.01 m おきの点の両方から測り直す
（一様の間隔の点だけでは折れ目の頂点を飛ばすことがあるため）。x 200〜825 m。出力：out/k_v2exact.json"""
import numpy as np
from k_lib import *

my = MyFrames()
res = {}
for which in ("editor",):
    ix = jload(RT + f"/verify/coarse/unity_{which}/index.json"); cur = np.fromfile(RT + f"/verify/coarse/unity_{which}/curves.bin", dtype="<f4")
    src = {(c["pair"], round(c["alpha"], 6)): c for c in ix["curves"] if c["group"] == "src556"}
    per = []
    for f in range(F0, F1 + 1):
        c = src[(f - F0, 0.0)] if f - F0 < 570 else src[(569, 1.0)]
        o = c["offsetFloats"]; U = cur[o:o + 4 * 8192].reshape(8192, 4)[:, :2].astype(np.float64); U[:, 0] += c["seatX"]
        R = my.main_of(f)
        Q = np.vstack([R, densify(R, 0.01)])
        Q = Q[(Q[:, 0] >= 200.0) & (Q[:, 0] <= 825.0)]
        d, _ = SegTree([U]).dist(Q)
        per.append((float(d.max()), f))
    m = max(per)
    res[which] = dict(max=m[0], frame=m[1], n_over_0_02=sum(1 for v, _ in per if v > 0.02), median=float(np.median([v for v, _ in per])))
    print(which, res[which])
jsave(OUT + "/k_v2exact.json", res)
