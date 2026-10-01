# -*- coding: utf-8 -*-
"""仕上げ28 第1回：候補の速い確かめ（大きな輪郭の関門 σ12・78/130/131 の包絡の差・網の衛生）。py -3.10 rays_quickcheck.py label=rows.npz ..."""
import os, sys, json
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rays_common as RC  # noqa
sys.path.insert(0, os.path.join(RC.REPO, "Tools", "GWWaveGen", "kstar3")); sys.path.insert(0, os.path.join(RC.REPO, "Tools", "PaintingTruth")); sys.path.insert(0, os.path.join(RC.REPO, "Tools", "GWWaveGen"))
import kh_gate_lf as KG  # noqa
import candA_common as C  # noqa
import fin_eval as FE  # noqa
g = KG.LFGate()
V1, tgt, fr = C.painting_frame()
for arg in sys.argv[1:]:
    lab, p = arg.split("=", 1)
    z = np.load(p); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    r, cov = g.measure_rows(c, A, Y)
    m = FE.mesh_hygiene(c, A, Y, V1)
    print(lab, "132 max %.2f  72 p95 %.2f | selfx %d rows %s flip %d rows %s cross>60 %d" % (r["132"]["max_px"], r["72"]["p95_px"], m["local_selfx_vertices_win6"], m["local_selfx_rows"][:6], m["flipped_quads_gt150"], m["flipped_rows"][:6], m["cross_row_gt60_all"]))
