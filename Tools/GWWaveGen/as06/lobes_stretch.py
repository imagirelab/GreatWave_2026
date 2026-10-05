# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：主役波の静止のメッシュの帯の座標 w の伸び（G1 の測り、asm4_rules.stretch と同じ決めごと）を、作り直しの途中で素早く測る道具。
py -3.10 -B Tools/GWWaveGen/as06/lobes_stretch.py <主役波の静止のメッシュ.json>
伸びの三角形（模様の面で |∇w| が 1/3〜3 倍の外）の数と、その場所（c・高さ・列）の分布を出す。
"""
import json
import os
import sys

import numpy as np

os.environ["AS04_FIX"] = "fix1"
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04")
import asm4_common as A  # noqa: E402
import asm4_rules as R  # noqa: E402


def main():
    p = sys.argv[1]
    A.N_HERO = json.load(open(p, encoding="utf-8"))["vertices"]
    m = R.stretch_masks(p, "hero")
    bad = m["sel"] & m["pat"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
    Q = A.K.sec(m["pos"])
    t = m["tri"][bad]
    cm = Q[:, 2][t].mean(1); ym = Q[:, 1][t].mean(1); col = (t[:, 0] % 400)
    hc, ec = np.histogram(cm, bins=np.arange(-25, 16, 1.0))
    out = {"bad_tri": int(bad.sum()), "c_hist": {"%.0f" % e: int(n) for e, n in zip(ec[:-1], hc) if n},
           "y_p10_p50_p90": [round(float(x), 1) for x in np.percentile(ym, (10, 50, 90))] if bad.any() else None,
           "col_p10_p50_p90": [int(x) for x in np.percentile(col, (10, 50, 90))] if bad.any() else None}
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
