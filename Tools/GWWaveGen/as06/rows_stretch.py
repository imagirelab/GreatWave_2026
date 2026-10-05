# -*- coding: utf-8 -*-
"""美術の見本06 の段の行：静止のメッシュの帯の座標 w の伸び（G1 の面の伸び、asm4_rules.stretch_masks と同じ決めごと）を素早く数える。
py -3.10 -B Tools/GWWaveGen/as06/rows_stretch.py <hero_smooth.json>
模様の面の三角形のうち |∇w| が 1/3〜3 倍の外の数と、その場所（c・高さ）。見本05 B と見本03 の形は 0。"""
import os
import sys

import numpy as np

os.environ.setdefault("AS04_FIX", "fix1")
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as04")
import asm4_common as A  # noqa: E402
import asm4_rules as R  # noqa: E402

p = sys.argv[1]
A.N_HERO = int(A.jl(p)["vertices"])
m = R.stretch_masks(p, "hero")
bad = m["sel"] & m["pat"] & ((m["gw"] < 1 / 3) | (m["gw"] > 3))
Q = A.K.sec(m["pos"])
cm = Q[:, 2][m["tri"]].mean(1); ym = Q[:, 1][m["tri"]].mean(1)
print("w_outside", int(bad.sum()), "c", np.round(np.percentile(cm[bad], (0, 50, 100)), 2).tolist() if bad.any() else None,
      "y", np.round(np.percentile(ym[bad], (10, 50, 90)), 1).tolist() if bad.any() else None)
