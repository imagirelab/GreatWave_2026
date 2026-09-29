# K*' R1: copy of the judges' triangle-triangle self-intersection check (Q20H/judge_H1A_fid/jt_selfx_bl.py, same logic).
# Blender headless: triangle-triangle self-intersection of GWW0 sheets (BVH overlap, pairs sharing a vertex removed).
# blender --background --factory-startup --python-exit-code 1 --python jt_selfx_bl.py -- out.json label=path.gwb ...
import sys, json, struct
import numpy as np
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
res = {}
for arg in argv[1:]:
    lab, p = arg.split("=", 1)
    b = open(p, "rb").read()
    assert b[:4] == b"GWW0"
    ver, nu, nv, nf = np.frombuffer(b[4:20], "<i4"); ntri = int(np.frombuffer(b[28:32], "<i4")[0])
    n = int(nu) * int(nv); o = 32 + n * 16
    F = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).astype(np.int64); o += ntri * 12
    X = np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)
    bvh = BVHTree.FromPolygons([tuple(v) for v in X], F.tolist(), all_triangles=True, epsilon=0.0)
    pairs = bvh.overlap(bvh)
    P = np.array(pairs, dtype=np.int64) if pairs else np.zeros((0, 2), np.int64)
    P = P[P[:, 0] < P[:, 1]]
    Fa, Fb = F[P[:, 0]], F[P[:, 1]]
    share = np.zeros(len(P), bool)
    for i in range(3):
        for j in range(3):
            share |= Fa[:, i] == Fb[:, j]
    Q = P[~share]
    a, bb, c = X[F[:, 0]], X[F[:, 1]], X[F[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(bb - a, c - a), axis=1)
    emax = np.maximum.reduce([np.linalg.norm(bb - a, axis=1), np.linalg.norm(c - bb, axis=1), np.linalg.norm(a - c, axis=1)])
    resolv = 2 * area / np.maximum(emax, 1e-15) >= 0.005
    Qr = Q[resolv[Q[:, 0]] & resolv[Q[:, 1]]] if len(Q) else Q
    cell = lambda t: (int(t // 2 // (nu - 1)), int(t // 2 % (nu - 1)))
    rows = sorted(set([cell(t)[0] for t in Q.ravel()]))
    # separate same-row-neighbourhood (local fold) vs distant (sheet passes through another part)
    far = []
    for p, q in Q:
        rp, cp = cell(p); rq, cq = cell(q)
        if abs(rp - rq) > 3 or abs(cp - cq) > 6:
            far.append((p, q))
    verts = set()
    for p, q in Q:
        verts.update(F[p].tolist()); verts.update(F[q].tolist())
    res[lab] = {"pairs_all": int(len(Q)), "pairs_resolvable_alt5mm": int(len(Qr)), "pairs_distant": len(far),
                "vertices_involved": len(verts), "n_rows_involved": len(rows), "rows_involved": rows,
                "samples": [[list(cell(p)), list(cell(q)), [round(float(v), 2) for v in X[F[p]].mean(0)]] for p, q in Q[:12]],
                "distant_samples": [[list(cell(p)), list(cell(q)), [round(float(v), 2) for v in X[F[p]].mean(0)]] for p, q in far[:8]]}
    print("SELFX", lab, json.dumps({k: v for k, v in res[lab].items() if k != "rows_involved"}), flush=True)
json.dump(res, open(out, "w"), indent=1)
