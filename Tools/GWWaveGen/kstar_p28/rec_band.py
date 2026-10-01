# -*- coding: utf-8 -*-
"""仕上げ28 の回復：b区域の帯の上の縁（原画視点）の房の数を数える（評審の j2n_band と同じ読み：candA4_checks.silhouette_band・band_check の
帯の上の縁の曲線を x 245〜705 に 2 px ごとに補間し、scipy.signal.find_peaks の際立ち 6 px・10 px の山を房とする。原画の目標
candA4_band_targets.json の top_raw は x 449・527・585・657 の 4 つ（際立ち 81・43・6・9）。py -3.10 rec_band.py <out.json> label=rows.npz ...
"""
import os
import sys
import json

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402
import candA_common as CA  # noqa: E402
import candA4_checks as CK  # noqa: E402
from scipy.signal import find_peaks  # noqa: E402

XS = np.arange(245, 706, 2.0)


def lobes(x, y, prom):
    yi = np.interp(XS, x, y, left=np.nan, right=np.nan)
    m = np.isfinite(yi)
    if not m.any():
        return [], None
    h = -yi[m]
    pk, pr = find_peaks(h, prominence=prom)
    return [[float(XS[m][i]), round(float(yi[m][i]), 1), round(float(pr["prominences"][j]), 1)] for j, i in enumerate(pk)], [float(XS[m].min()), float(XS[m].max())]


def measure(path):
    V1, tgt, fr = CA.painting_frame()
    z = np.load(path); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
    bd = CK.band_check(c, A, Y, cov)
    tc = np.array(bd["candidate_top_curve"], float)
    o = {kk: bd[kk] for kk in ("top_vs_top_raw", "top_vs_top_smooth", "bottom_vs_bottom_raw")}
    if len(tc) > 3:
        tc = tc[np.argsort(tc[:, 0])]
        for prom in (6.0, 10.0):
            o["lobes_prom%g" % prom] = lobes(tc[:, 0], tc[:, 1], prom)
    return o


def main():
    outp = sys.argv[1]
    bt = json.load(open(os.path.join(RC.REPO, "Tools", "GWWaveGen", "kstar3", "candA4_band_targets.json"), encoding="utf-8"))
    T = np.array(bt["top_raw"], float)
    out = {"target_top_raw": {"prom6": lobes(T[:, 0], T[:, 1], 6.0), "prom10": lobes(T[:, 0], T[:, 1], 10.0)}}
    for a in sys.argv[2:]:
        k, p = a.split("=", 1)
        out[k] = measure(p)
        out[k]["rows_sha256"] = RC.sha256(p)
        print(k, json.dumps({kk: vv for kk, vv in out[k].items()}, ensure_ascii=False), flush=True)
    RC.jdump(out, outp)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
