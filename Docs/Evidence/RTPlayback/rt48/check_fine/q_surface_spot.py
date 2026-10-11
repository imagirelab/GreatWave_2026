# -*- coding: utf-8 -*-
"""Spot check: rebuild the fine surface (Zhu & Bridson 2005 as the plan states: phi=|x-xbar|-rbar, w=(1-s^2)^3, R=0.5 m, 0.125 m nodes on z=0,
3D distances) from the R3e particles in a +-25 m window around the crest, and compare with the stored phi where it was computed."""
import json, numpy as np
from scipy.spatial import cKDTree
import q_lib as Q
R = 0.5; RB = 0.3
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest = {r["frame"]: r["crest_x"] for r in cm["frames"]}
out = {}
for f in (3600, 3709, 3744, 3760):
    p = np.load(Q.RE + "/particles/p_%04d.npy" % f).astype(np.float64)
    phi, xs, ys = Q.load_phi(f)
    comp = np.load(Q.FINE + "/phi_%04d.npz" % f)["computed"]
    xc = crest[f]
    mx = (xs >= xc - 25) & (xs <= xc + 25)
    X, Y = np.meshgrid(xs[mx] + Q.XP, ys)
    nodes = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], 1)
    sel = (p[:, 0] >= xc + Q.XP - 26) & (p[:, 0] <= xc + Q.XP + 26)
    P = p[sel]
    tree = cKDTree(P)
    lists = tree.query_ball_point(nodes, R)
    ph = np.full(len(nodes), np.nan)
    for n, L in enumerate(lists):
        if not L:
            continue
        q = P[L]
        s2 = ((q - nodes[n]) ** 2).sum(1) / R ** 2
        w = (1 - s2) ** 3
        xb = (w[:, None] * q).sum(0) / w.sum()
        ph[n] = np.linalg.norm(nodes[n] - xb) - RB
    ph = ph.reshape(X.shape)
    st = phi[:, mx]; cpt = comp[:, mx]
    both = cpt & np.isfinite(ph)
    d = np.abs(ph[both] - st[both])
    nopart = cpt & ~np.isfinite(ph)
    out[f] = dict(n_nodes_computed=int(cpt.sum()), n_compared=int(both.sum()), max_abs_diff=float(d.max()), p99=float(np.percentile(d, 99)),
                  n_computed_without_particles=int(nopart.sum()), stored_values_there=sorted(set(np.round(st[nopart], 4).tolist()))[:5],
                  sign_mismatch=int((np.sign(ph[both]) != np.sign(st[both])).sum()), z_range=[float(p[:, 2].min()), float(p[:, 2].max())])
    print(f, out[f])
json.dump(out, open(Q.OUT + "/q_surface_spot.json", "w"), indent=1)
