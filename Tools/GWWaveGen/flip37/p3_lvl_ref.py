# -*- coding: utf-8 -*-
"""見張りの基準：R18（粗い計算）の一番上の水面の、主役の範囲の内側（境界の帯 + 2 m を除く）の平均を、コマごとに出す（py -3.10）。
主役の範囲は波が出入りするので、平均の水面はもともと動く。見張りは「細かい計算の平均 − R18 の平均」が始めより 1 m 下がったら止める。
使い方: py -3.10 p3_lvl_ref.py wx0 wx1 wz0 wz1 pad  → Unity/Build/FLIP37/P3/lvl_ref_<wx0>_<wx1>_<wz0>_<wz1>_<pad>.json
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import p3_compare_coarse as C

wx0, wx1, wz0, wz1, pad = (float(v) for v in sys.argv[1:6])
R = C.load_r18()
ix = (R["xs"] > wx0 + pad + 2) & (R["xs"] < wx1 - pad - 2); iz = (R["zs"] > wz0 + pad + 2) & (R["zs"] < wz1 - pad - 2)
ref = {int(f): float(np.nanmean(R["eta"][k][np.ix_(iz, ix)])) for k, f in enumerate(R["frames"])}
out = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P3/lvl_ref_%g_%g_%g_%g_%g.json" % (wx0, wx1, wz0, wz1, pad)
json.dump(ref, open(out, "w"))
print(out, ref[72], ref[115], ref[274])
