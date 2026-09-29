# -*- coding: utf-8 -*-
"""Q20 cand A, step 3 (final): silhouette-locked SURFACE warp to the painting (PaintingCam v1).

Why not a pure image-space field: a field on the image also moves hidden geometry that happens to project near the
outline (the back of the wave, the tube's back wall seen through the tube), by metres.  Here only the vertices that
form the candidate's painting-view silhouette are moved (their image is moved onto the nearest point of the painting
outline 78/130/131/132/72, half-width compensated like K*, and cast back onto their own row plane); the moves are
spread over the surface in its own parameter domain (arc length along the row sigma, crest coordinate c) with a
thin-plate spline, a Gaussian falloff (the surface far from the silhouette does not move) and zero anchors.
Rounds repeat (new silhouette vertices appear as the outline moves); then candA_warp.snap_round polishes (sub-px).
The total 3-D move per vertex is kept as the warp magnitude field.
usage: py -3.10 candA_swarp.py pre_rows.npz out_rows.npz [--rounds N] [--falloff m] [--snap N]
"""
import sys, os, json, math
import numpy as np
import cv2
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA_warp as W


def zbuffer(P, tris, W_, H_):
    """approximate depth buffer at display resolution from vertices + edge midpoints (min depth per pixel, 3x3 min)."""
    pts = [P]
    for (i, j) in ((0, 1), (1, 2), (2, 0)):
        pts.append(0.5 * (P[tris[:, i]] + P[tris[:, j]]))
    Q = np.vstack(pts)
    ok = (Q[:, 2] > 1) & (Q[:, 0] >= 0) & (Q[:, 0] < W_) & (Q[:, 1] >= 0) & (Q[:, 1] < H_)
    Q = Q[ok]
    z = np.full(W_ * H_, np.inf)
    idx = np.round(Q[:, 1]).astype(int).clip(0, H_ - 1) * W_ + np.round(Q[:, 0]).astype(int).clip(0, W_ - 1)
    np.minimum.at(z, idx, Q[:, 2])
    z = z.reshape(H_, W_)
    zf = np.where(np.isfinite(z), z, 1e9).astype(np.float32)
    zf = cv2.erode(zf, np.ones((5, 5), np.uint8))      # min filter
    return zf


def surface_round(pt, c, A, Y, falloff=3.0, maxd=80.0, cell=0.4, lam=0.05, y_att=(0.0, 2.5)):
    tgt, fr = pt.tgt, pt.fr
    nv, nu = A.shape
    B, cov = W.cand_boundary(pt, c, A, Y)
    lb = W.cand_landmarks(B, pt)
    Bu = B[:lb["end72"] + 1]
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = pt.project(X)
    tris = pt.V1.triangles(nu, nv)
    zb = zbuffer(P, tris, 1920, 1080)
    xi = np.round(P[:, 0]).astype(int).clip(0, 1919); yi = np.round(P[:, 1]).astype(int).clip(0, 1079)
    vis = P[:, 2] <= zb[yi, xi] + 0.6
    dB, _ = cKDTree(Bu).query(P[:, :2])
    kdT = cKDTree(pt.T)
    dT, iT = kdT.query(P[:, :2])
    yv = Y.reshape(-1)
    sil = (dB <= 1.6) & vis & (yv > 0.4) & (dT < maxd) & (P[:, 2] > 1)
    # per-row arc length from the lip-tip column (the surface parameter sigma)
    seg = np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1))
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(seg, 1)], 1)
    sig = (s - s[:, [200]]).reshape(-1)
    cc = np.repeat(c, nu)
    # target displacement of the silhouette vertices: image -> nearest target outline point, cast back to the row plane
    iv = np.nonzero(sil)[0]
    P2 = pt.T[iT[iv]]
    Xn = W.backproject_to_plane(pt, P2, cc[iv])
    Sn = C.sec(Xn)
    da = Sn[:, 0] - A.reshape(-1)[iv]; dy = Sn[:, 1] - yv[iv]
    # thin controls per (sigma, c) cell (keep the one with the largest move)
    key = np.stack([np.floor(sig[iv] / cell), np.floor(cc[iv] / cell)], -1)
    order = np.argsort(-np.hypot(da, dy))
    _, first = np.unique(key[order], axis=0, return_index=True)
    ci = order[first]
    ctrl = np.stack([sig[iv][ci], cc[iv][ci]], -1); vals = np.stack([da[ci], dy[ci]], -1)
    # zero anchors: surface points far (in sigma, c) from any silhouette vertex
    allq = np.stack([sig, cc], -1)
    dsil, _ = cKDTree(ctrl).query(allq)
    far = np.nonzero((dsil > 2.5 * falloff) & (yv > -99))[0]
    fkey = np.stack([np.floor(sig[far] / 2.0), np.floor(cc[far] / 2.0)], -1)
    _, ff = np.unique(fkey, axis=0, return_index=True)
    anc = allq[far[ff]]
    ctrl2 = np.vstack([ctrl, anc]); vals2 = np.vstack([vals, np.zeros((len(anc), 2))])
    w, aff = W.tps_fit(ctrl2, vals2, lam)
    near = np.nonzero(dsil < 3.0 * falloff)[0]
    field = np.zeros((nv * nu, 2))
    field[near] = W.tps_eval(ctrl2, w, aff, allq[near])
    field *= np.exp(-(dsil / falloff) ** 2)[:, None]
    field[:, 1] *= C.smoothstep((yv - y_att[0]) / (y_att[1] - y_att[0]))
    field *= C.smoothstep((yv - 0.3) / 2.0)[:, None]
    An = A + field[:, 0].reshape(nv, nu); Yn = Y + field[:, 1].reshape(nv, nu)
    reverted = 0
    for r in range(nv):
        if np.abs(field.reshape(nv, nu, 2)[r]).max() < 1e-6:
            continue
        if W.section_crossings(np.stack([An[r], Yn[r]], -1)) > W.section_crossings(np.stack([A[r], Y[r]], -1)):
            An[r], Yn[r] = A[r], Y[r]; reverted += 1
    res = np.hypot(dT[sil], 0)
    return An, Yn, {"n_sil": int(sil.sum()), "n_ctrl": int(len(ctrl)), "sil_dist_max_px": float(dT[sil].max()) if sil.any() else 0.0,
                    "sil_dist_p95_px": float(np.percentile(dT[sil], 95)) if sil.any() else 0.0,
                    "move_max_m": float(np.hypot(field[:, 0], field[:, 1]).max()), "rows_reverted": reverted}


def main():
    pre, out = sys.argv[1], sys.argv[2]
    nr = int(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else 8
    fo = float(sys.argv[sys.argv.index("--falloff") + 1]) if "--falloff" in sys.argv else 3.0
    ns = int(sys.argv[sys.argv.index("--snap") + 1]) if "--snap" in sys.argv else 8
    z = np.load(pre); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    pt = W.Painting()
    A0, Y0 = A.copy(), Y.copy()
    log = []
    for k in range(nr):
        A, Y, info = surface_round(pt, c, A, Y, falloff=fo)
        info["round"] = k; log.append(info); print(json.dumps(info), flush=True)
    for k in range(ns):
        A, Y, info = W.snap_round(pt, c, A, Y)
        info["round"] = "snap%d" % k; log.append(info); print(json.dumps(info), flush=True)
    X0 = C.world(c, A0, Y0); X1 = C.world(c, A, Y)
    mag = np.linalg.norm(X1 - X0, axis=-1)
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0, warp_mag=mag)
    json.dump({"method": "surface warp (sigma, c) TPS + falloff %.1f m, then snap" % fo, "rounds": log,
               "warp_mag_max_m": float(mag.max()), "warp_mag_p95_m": float(np.percentile(mag[Y0 > 0.5], 95)),
               "warp_mag_p50_m": float(np.percentile(mag[Y0 > 0.5], 50))},
              open(os.path.splitext(out)[0] + "_warp.json", "w"), indent=1, default=float)
    print("warp max %.2f m, p95 %.2f m" % (mag.max(), np.percentile(mag[Y0 > 0.5], 95)))


if __name__ == "__main__":
    main()
