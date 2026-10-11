# -*- coding: utf-8 -*-
"""Independent C3 for the fine bake: each pair's A against frame k's own contour of the stored phi, B against frame k+1's,
two-way, exact point-to-segment distances from points densified at 0.005 m. Usage: py -3.10 q_c3.py"""
import json, time
import numpy as np
from multiprocessing import Pool
import q_lib as Q

OFF = None
PAIRS = Q.DATA + "/fine/pairs.bin"


def contour(f):
    phi, xs, ys = Q.load_phi(f)
    return Q.main_curve(phi, xs, ys - OFF)


def twoway(P, C, h=0.005):
    d1 = Q.seg_dist(Q.densify(P, h), C)
    d2 = Q.seg_dist(Q.densify(C, h), P)
    i1 = int(np.argmax(d1)); i2 = int(np.argmax(d2))
    Pd = Q.densify(P, h); Cd = Q.densify(C, h)
    return max(d1[i1], d2[i2]), (Pd[i1] if d1[i1] >= d2[i2] else Cd[i2]), d1[i1], d2[i2]


def one(p):
    global OFF
    if OFF is None:
        OFF = Q.still_offset_fine()
    pairs = np.memmap(PAIRS, dtype="<f4", mode="r", shape=(570, 2, 8192, 2))
    k = 3319 + p
    out = []
    for side, f in ((0, k), (1, k + 1)):
        P = np.array(pairs[p, side], dtype=np.float64); P[:, 0] += Q.X0B
        C = contour(f)
        m, where, d_pc, d_cp = twoway(P, C)
        # restricted to x 200-825
        sel = (P[:, 0] >= 200) & (P[:, 0] <= 825)
        selc = (C[:, 0] >= 200) & (C[:, 0] <= 825)
        Pd = Q.densify(P, 0.005); Cd = Q.densify(C, 0.005)
        a = Q.seg_dist(Pd[(Pd[:, 0] >= 200) & (Pd[:, 0] <= 825)], C)
        b = Q.seg_dist(Cd[(Cd[:, 0] >= 200) & (Cd[:, 0] <= 825)], P)
        out.append(dict(side=side, frame=f, max=float(m), x=float(where[0]), y=float(where[1]), A_to_contour=float(d_pc), contour_to_A=float(d_cp),
                        max_200_825=float(max(a.max(), b.max()))))
    return p, out


if __name__ == "__main__":
    T0 = time.time()
    with Pool(10) as pool:
        res = dict(pool.map(one, range(570)))
    m = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
    rows = []
    for p in range(570):
        a, b = res[p]
        rows.append(dict(p=p, k=3319 + p, max=max(a["max"], b["max"]), max_200_825=max(a["max_200_825"], b["max_200_825"]),
                         where=(a if a["max"] >= b["max"] else b), manifest_c3=m["pairs"][p]["c3_max"], interp=m["pairs"][p]["interp"]))
    arr = np.array([r["max"] for r in rows]); ks = np.array([r["k"] for r in rows])
    onset, K = 3709, 3745
    def phase(sel):
        return dict(max=float(arr[sel].max()), n=int(sel.sum()), n_over=int((arr[sel] > 0.02).sum()))
    worst = rows[int(np.argmax(arr))]
    s = dict(max=float(arr.max()), worst=worst, n_over_0p02=int((arr > 0.02).sum()),
             before_onset=phase(ks + 1 < onset), onset_to_K=phase((ks + 1 >= onset) & (ks + 1 < K)), after_K=phase(ks + 1 >= K),
             interp_pairs=phase(np.array([r["interp"] for r in rows])),
             max_200_825=float(max(r["max_200_825"] for r in rows)),
             max_abs_diff_vs_manifest_c3=float(max(abs(r["max"] - r["manifest_c3"]) for r in rows)),
             seconds=round(time.time() - T0, 1))
    print(json.dumps(s, indent=1, default=float))
    json.dump(dict(summary=s, rows=rows), open(Q.OUT + "/q_c3.json", "w"), indent=1, default=float)
