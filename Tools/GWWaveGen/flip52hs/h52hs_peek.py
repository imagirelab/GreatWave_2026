# -*- coding: utf-8 -*-
"""Peek one GW45SRF1 surface record (read only). 2026-10-18 written new (Claude) for the grid-artifact diagnosis."""
import os, sys
os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.dont_write_bytecode = True
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45")
import numpy as np
import g45_export_unity as E45
RUN = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long"
f = int(sys.argv[1]) if len(sys.argv) > 1 else 2149
d = E45.read_frame_bytes(open(RUN + "/surf/s_%05d.gw45s" % f, "rb").read())
P, N, tri = d["P"], d["N"], d["tri"].astype(np.int64)
print("nv", d["nv"], "nt", d["nt"], "lo", d["lo"], "hi", d["hi"], "t", d["t"], "off", d["still_offset"], "qhalf", d["quant_half_step_m"])
e = np.concatenate([np.linalg.norm(P[tri[:, i]] - P[tri[:, (i + 1) % 3]], axis=1) for i in range(3)])
print("edge pct 5/25/50/75/95/99/max", np.round(np.percentile(e, [5, 25, 50, 75, 95, 99, 100]), 3))
for xs in [(0, 100), (100, 200), (200, 260), (260, 300), (300, 420)]:
    m = (P[:, 0] >= xs[0]) & (P[:, 0] < xs[1])
    print("x", xs, "verts", int(m.sum()), "z range", np.round([P[m, 2].min(), P[m, 2].max()], 1) if m.any() else None, "y range", np.round([P[m, 1].min(), P[m, 1].max()], 2) if m.any() else None)
