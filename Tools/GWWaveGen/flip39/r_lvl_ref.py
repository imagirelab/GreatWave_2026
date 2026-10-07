# -*- coding: utf-8 -*-
"""FLIP39 R 見張りの基準：E3（粗い計算）の一番上の水面の、主役の範囲の内側（境界の帯 + 2 m を除く。壁の側は壁 + 2 m）の平均をコマごとに出す（py -3.10）。
FLIP37 の p3_lvl_ref.py と同じ考え方（主役の範囲は波が出入りするので平均の水面はもともと動く。見張りは「細かい計算の平均 − E3 の平均」が始めより 1 m 下がったら止める）。
使い方: py -3.10 r_lvl_ref.py wx0 wx1 wz0 wz1 pad padz0 → Unity/Build/FLIP39/R/lvl_ref_<wx0>_<wx1>_<wz0>_<wz1>_<pad>.json
"""
import sys, os, json
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from e_analyze import load_hf

wx0, wx1, wz0, wz1, pad, padz0 = (float(v) for v in sys.argv[1:7])
hf = load_hf(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/E3_dir20_lens")
g = hf["grid"]
xs = g["x0"] + g["dx"] * np.arange(hf["eta"].shape[2]); zs = g["z0"] + g["dz"] * np.arange(hf["eta"].shape[1])
ix = (xs > wx0 + pad + 2) & (xs < wx1 - pad - 2); iz = (zs > wz0 + padz0 + 2) & (zs < wz1 - pad - 2)
ref = {int(f): float(np.nanmean(hf["eta"][k][np.ix_(iz, ix)])) for k, f in enumerate(hf["frames"]) if f >= 900}
out = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/lvl_ref_%g_%g_%g_%g_%g.json" % (wx0, wx1, wz0, wz1, pad)
json.dump(ref, open(out, "w"))
print(out, ref[961], ref[1100], ref[1261])
