# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: last few pixels of the painting gate, moved ONLY at the silhouette-forming edges.

After the parametric fit (candA4_fit.py) the large forms are fixed.  What remains of the gate residual is closed by a
thin edge offset: for every target point of 78/130/131/132/72 we find the candidate vertex that forms the outline
there (the vertex whose image is nearest to the candidate's boundary point closest to the target), and the image
distance to the target along the outline normal.  That distance is turned into a 3-D offset along the row's in-plane
surface normal (metres per pixel measured by projecting a 1 cm step), spread along the section with a Gaussian of
sigma_s (m of arc length) and across rows with sigma_c (m of c), capped, and applied.  Nothing farther than ~3 sigma
from the outline moves, so the interior keeps the parametric (smooth) form.  The total offset field is saved.
usage: py -3.10 candA4_edgesnap.py in_rows.npz out_rows.npz [--rounds 4] [--sig_s 1.0] [--sig_c 0.6] [--cap 0.6]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys, json
import numpy as np
import cv2
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import fin2_warp as W


def row_normals(A, Y):
    """in-plane unit normal of each row polyline (pointing to the right of the column direction = out of the water
    on the back/lip-top, into the tube on the underside...); sign is fixed later per target by the image direction."""
    ta = np.gradient(A, axis=1); ty = np.gradient(Y, axis=1)
    L = np.maximum(np.hypot(ta, ty), 1e-9)
    return np.stack([ty / L, -ta / L], -1)       # (nv, nu, 2) in (a, y)


def snap_round(pt, c, A, Y, sig_s=1.0, sig_c=0.6, cap=0.6, gain=0.8, items=("78", "130", "131", "132", "72")):
    V1, fr, tgt = pt.V1, pt.fr, pt.tgt
    nv, nu = A.shape
    X = fr.world(c, A, Y)
    tris = V1.triangles(nu, nv)
    cov = (V1.rasterize(fr.cam, X, tris) > 0.5).astype(np.uint8)
    din = cv2.distanceTransform(cov, cv2.DIST_L2, 5); dout = cv2.distanceTransform(1 - cov, cv2.DIST_L2, 5)
    sdf = dout - din
    edge = cv2.morphologyEx(cov, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    ey, ex = np.nonzero(edge)
    E = np.stack([ex, ey], -1).astype(float)
    P = fr.cam.project(X.reshape(-1, 3))
    okv = (P[:, 2] > 0) & (Y.reshape(-1) > 0.2)
    vid = np.nonzero(okv)[0]
    kdv = cKDTree(P[vid, :2]); kde = cKDTree(E)
    T = pt.T; lm = pt.lm
    lab = np.empty(len(T), object)
    lab[:lm["j78_130"]] = "78"; lab[lm["j78_130"]:lm["j130_131"]] = "130"; lab[lm["j130_131"]:lm["top"]] = "131"
    lab[lm["top"]:lm["tip"]] = "132"; lab[lm["tip"]:] = "72"
    Nr = row_normals(A, Y)
    D = np.zeros((nv, nu)); Wt = np.zeros((nv, nu))
    stats = []
    for i in range(0, len(T), 2):
        if lab[i] not in items:
            continue
        q = T[i]
        sd = sdf[int(np.clip(round(q[1]), 0, 1079)), int(np.clip(round(q[0]), 0, 1919))]
        if abs(sd) < 0.7:
            continue
        de, ie = kde.query(q)
        if de > 25:
            continue
        b = E[ie]
        # the vertex that forms that boundary point
        dv, iv = kdv.query(b)
        if dv > 6:
            continue
        k = vid[iv]; r, j = divmod(int(k), nu)
        # image direction from the boundary point to the target (move the edge that way by |sd| px)
        v = q - b
        if np.linalg.norm(v) < 1e-6:
            continue
        v = v / np.linalg.norm(v)
        # metres per pixel along the row normal
        n2 = Nr[r, j]
        X0 = X[r, j]; X1 = C.world(np.array([c[r]]), np.array([[A[r, j] + 0.01 * n2[0]]]), np.array([[Y[r, j] + 0.01 * n2[1]]]))[0, 0]
        p0 = fr.cam.project(X0[None])[0, :2]; p1 = fr.cam.project(X1[None])[0, :2]
        g = (p1 - p0) / 0.01                        # px per metre along +n
        along = float(g @ v)
        if abs(along) < 2.0:                        # this normal hardly moves the image in the needed direction
            continue
        dm = np.clip(gain * abs(sd) / along, -cap, cap)
        D[r, j] += dm; Wt[r, j] += 1.0
        stats.append((lab[i], float(sd), r, j, float(dm)))
    m = Wt > 0
    D[m] /= Wt[m]
    # spread along each row (arc length) and across rows (c)
    S = np.zeros_like(D); Sw = np.zeros_like(D)
    rr, jj = np.nonzero(m)
    s_row = np.stack([C.arclen(A[r], Y[r]) for r in range(nv)])
    for r, j in zip(rr, jj):
        rows = np.nonzero(np.abs(c - c[r]) < 3 * sig_c)[0]
        wc = np.exp(-0.5 * ((c[rows] - c[r]) / sig_c) ** 2)
        ws = np.exp(-0.5 * ((s_row[rows] - s_row[r, j][None]) / sig_s) ** 2)
        wgt = wc[:, None] * ws
        S[rows] += wgt * D[r, j]; Sw[rows] += wgt
    F = np.where(Sw > 1e-6, S / np.maximum(Sw, 1.0), 0.0)       # normalised where several edges overlap, never amplified
    F = np.clip(F, -cap, cap)
    A2 = A + F * Nr[..., 0]; Y2 = Y + F * Nr[..., 1]
    return A2, Y2, F, {"n_targets_used": len(stats), "max_abs_offset_m": float(np.abs(F).max()),
                       "n_vertices_moved_gt_1cm": int((np.abs(F) > 0.01).sum())}


def gate(pt, c, A, Y, png=None):
    X = pt.fr.world(c, A, Y); tris = pt.V1.triangles(A.shape[1], A.shape[0])
    g = pt.V1.preview_metrics(pt.fr, pt.tgt, X, tris, png, "A4 edge snap")
    return {k: (round(v["max_px"], 2), round(v["p95_px"], 2)) for k, v in g.items()}


def main():
    a = sys.argv
    src, dst = a[1], a[2]
    rounds = int(a[a.index("--rounds") + 1]) if "--rounds" in a else 4
    items = tuple(a[a.index("--items") + 1].split(",")) if "--items" in a else ("78", "130", "131", "132")
    sig_s = float(a[a.index("--sig_s") + 1]) if "--sig_s" in a else 1.0
    sig_c = float(a[a.index("--sig_c") + 1]) if "--sig_c" in a else 0.6
    cap = float(a[a.index("--cap") + 1]) if "--cap" in a else 0.6
    z = np.load(src); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    A0, Y0 = A.copy(), Y.copy()
    pt = W.Painting()
    tmp = os.path.splitext(dst)[0] + "_gate_tmp.png"
    g = gate(pt, c, A, Y, tmp); log = [{"round": "start", "gate": g}]
    print(json.dumps(log[-1]), flush=True)
    Ftot = np.zeros_like(A)
    def score(g):
        return sum(max(g[k][0], 3.0) for k in ("78", "130", "131", "132")) + 2.0 * max(g["72"][1], 3.0) + 0.25 * g["72"][0]
    best = score(g); gain = float(a[a.index("--gain") + 1]) if "--gain" in a else 0.8
    for k in range(rounds):
        A1, Y1, F, inf = snap_round(pt, c, A, Y, sig_s=sig_s, sig_c=sig_c, cap=cap, items=items, gain=gain)
        g1 = gate(pt, c, A1, Y1, tmp); sc1 = score(g1)
        ok = sc1 < best
        log.append({"round": k, "gate": g1, "score": sc1, "accepted": bool(ok), "gain": gain, **inf}); print(json.dumps(log[-1]), flush=True)
        if ok:
            A, Y, best = A1, Y1, sc1; Ftot += F
        else:
            gain *= 0.5
            if gain < 0.1:
                break
    mag = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    np.savez_compressed(dst, A=A, Y=Y, c=c, A_param=A0, Y_param=Y0, snap_mag=mag)
    json.dump({"log": log, "items": list(items), "sig_s_m": sig_s, "sig_c_m": sig_c, "cap_m": cap, "snap_mag_max_m": float(mag.max()),
               "snap_mag_p99_m": float(np.percentile(mag[Y0 > 0.3], 99)), "moved_gt_1cm": int((mag > 0.01).sum())},
              open(os.path.splitext(dst)[0] + "_snap.json", "w"), indent=1)


if __name__ == "__main__":
    main()
