# -*- coding: utf-8 -*-
"""3b. 補間した線（Unity の書き出し interp556：38 組 × 割合 1/30〜29/30）が、頂 ±30 m の窓で自分と交わらないか（隣り合う線分を除く）、
窓の外で x が線に沿って増え続けるか。出力：out/k_selfx.json"""
import numpy as np
from k_lib import *

ix = jload(RT + "/verify/coarse/unity_editor/index.json"); cur = np.fromfile(RT + "/verify/coarse/unity_editor/curves.bin", dtype="<f4")
rows = jload(OUT + "/k_r3.json")["rows"]


def n_cross(P):
    A, B = P[:-1], P[1:]
    n = len(A); cnt = 0
    for s0 in range(0, n, 512):
        a = A[s0:s0 + 512, None]; b = B[s0:s0 + 512, None]; c = A[None]; d = B[None]
        o = lambda p, q, r: (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
        o1, o2, o3, o4 = o(a, b, c), o(a, b, d), o(c, d, a), o(c, d, b)
        hit = (o1 * o2 < 0) & (o3 * o4 < 0)
        ii = np.arange(s0, s0 + len(a))[:, None]; jj = np.arange(n)[None]
        cnt += int((hit & (jj > ii + 1)).sum())
    return cnt


tot, worst, nonmono = 0, 0, 0
for c in ix["curves"]:
    if c["group"] != "interp556":
        continue
    o = c["offsetFloats"]; U = cur[o:o + 4 * 8192].reshape(8192, 4)[:, :2].astype(np.float64); U[:, 0] += c["seatX"]
    xc = rows[c["frameA"] - F0]["crest_x"]
    win = (U[:, 0] >= xc - 30) & (U[:, 0] <= xc + 30)
    k = n_cross(U[win]); tot += k; worst = max(worst, k)
    dx = np.diff(U[:, 0]); out = ~(win[:-1] | win[1:])
    nonmono += int(((dx <= 0) & out).sum())
res = dict(n_curves=sum(1 for c in ix["curves"] if c["group"] == "interp556"), crossings_total=tot, nonmonotone_outside=nonmono)
print(res); jsave(OUT + "/k_selfx.json", res)
