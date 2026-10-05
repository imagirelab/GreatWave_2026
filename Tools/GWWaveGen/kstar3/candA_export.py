# -*- coding: utf-8 -*-
"""Q20 cand A: export a rows npz (A, Y, c) as a K*-format candidate: GWW0 .gwb (same topology / triangle order as
K* 26修正01, UV0 = (sigma / sigma_total, (c - c_min) / (c_max - c_min)), UV2 = (sigma [m], c [m]); sigma = arc length
of the main section (row 159) per column, as in K*), the rows npz (A, Y, c + K*-style extra arrays) and a meta json.
usage: py -3.10 candA_export.py rows.npz out_prefix [--meta extra.json]"""
import sys, os, json, hashlib, datetime
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C


def export(rows, prefix, extra=None):
    z = np.load(rows); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    nv, nu = A.shape
    K = C.read_gwb(C.KSTAR_GWB)
    tris = K["tris"]
    X = C.world(c, A, Y)
    main = int(np.argmin(np.abs(c)))
    sig = C.arclen(A[main], Y[main])
    U = sig / sig[-1]
    V = (c - c.min()) / (c.max() - c.min())
    uv = np.stack(np.meshgrid(U, V), -1).reshape(-1, 2)
    uv2 = np.stack(np.meshgrid(sig, c), -1).reshape(-1, 2)
    gwb = prefix + ".gwb"
    C.write_gwb(gwb, nu, nv, uv, uv2, tris, X)
    np.savez_compressed(prefix + "_rows.npz", A=A, Y=Y, c=c, P=np.stack([A[main], Y[main]], -1))
    # sanity: same triangle list as K*, finite, no degenerate triangles
    V3 = X.reshape(-1, 3)
    p0, p1, p2 = V3[tris[:, 0]], V3[tris[:, 1]], V3[tris[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    h = hashlib.sha256(open(gwb, "rb").read()).hexdigest()
    info = {"gwb": os.path.basename(gwb), "gwb_sha256": h, "gwb_bytes": os.path.getsize(gwb), "nu": nu, "nv": nv,
            "vertex_count": int(nu * nv), "triangle_count": int(len(tris)), "topology_same_as_kstar": True,
            "nan": int((~np.isfinite(V3)).sum()), "degenerate_triangles_area_lt_1e-6_m2": int((area < 1e-6).sum()),
            "min_triangle_area_m2": float(area.min())}
    if extra:
        info.update(extra)
    return info


if __name__ == "__main__":
    info = export(sys.argv[1], sys.argv[2])
    print(json.dumps(info, indent=1))
