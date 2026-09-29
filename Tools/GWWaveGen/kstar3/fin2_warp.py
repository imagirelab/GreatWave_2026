# -*- coding: utf-8 -*-
"""Q20 final loop 2 (copy of candA_warp.py + far_att: the hidden far side keeps its design).
Q20 cand A, step 3: silhouette-locked warp to the painting (PaintingCam v1).

The pre-warp secondary design (candA_design.py) is ~30-150 px off the painting outline.  We warp it with a smooth
2-D field of the painting-camera image, applied inside each row plane (each vertex is projected, its image point is
moved by the field, and the moved image point is cast back onto the SAME c plane), so rows stay planar and the
grid / landmark columns are kept.  Because the image of every triangle moves with the field, the painting-view
coverage of the warped sheet is the field's image of the old coverage: we choose the field so that the old outline
maps onto the painting outline (78 / 130 / 131 / 132 / 72, envelope, half-width compensated like K*).

  * correspondences: the candidate's sky boundary and the target outline are cut at matching landmarks (left frame
    edge, the 78|130 and 130|131 joints, the crest top, the lip tip, the tube's back-most point, the 72 end, the
    horizon) and matched by arc length in between; later rounds match by the nearest target point (small offsets);
  * field: thin-plate spline with regularisation (image px), zero at far anchors; attenuated to 0 on the flat sea
    (y < 0.8 m -> 0, full above 3 m) and for rows far outside the frame (c < -24);
  * rounds with decreasing smoothing; the total 3-D displacement per vertex is recorded (the warp magnitude field).
usage: py -3.10 candA_warp.py pre_rows.npz out_rows.npz [--rounds N]
"""
import sys, os, json, math
import numpy as np
import cv2
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

HORIZON = 787.7


def tps_fit(ctrl, vals, lam):
    n = len(ctrl)
    d = np.linalg.norm(ctrl[:, None, :] - ctrl[None, :, :], axis=-1)
    K = np.where(d > 0, d * d * np.log(np.maximum(d, 1e-12)), 0.0)
    P = np.hstack([np.ones((n, 1)), ctrl])
    M = np.zeros((n + 3, n + 3)); M[:n, :n] = K + lam * np.eye(n); M[:n, n:] = P; M[n:, :n] = P.T
    rhs = np.zeros((n + 3, vals.shape[1])); rhs[:n] = vals
    sol = np.linalg.solve(M, rhs)
    return sol[:n], sol[n:]


def tps_eval(ctrl, w, aff, q, chunk=3000):
    out = np.zeros((len(q), w.shape[1]))
    for k in range(0, len(q), chunk):
        qq = q[k:k + chunk]
        d = np.linalg.norm(qq[:, None, :] - ctrl[None, :, :], axis=-1)
        K = np.where(d > 0, d * d * np.log(np.maximum(d, 1e-12)), 0.0)
        out[k:k + chunk] = K @ w + np.hstack([np.ones((len(qq), 1)), qq]) @ aff
    return out


class Painting:
    def __init__(self):
        self.V1, self.tgt, self.fr = C.painting_frame()
        V1, tgt = self.V1, self.tgt
        # target outline: concatenation 78 -> 130 -> 131 -> 132 -> 72, moved inward by the indigo half width (as K*)
        segs = []
        self.joint_idx = {}
        n0 = 0
        for k in V1.SEGS:
            P = np.array(tgt.seg[k], float)
            P = V1.inward_offset_display(P, np.full(len(P), tgt.half_w[k]), lambda q: tgt.sample(q, comp=False))
            if segs:
                P = P[1:]
            segs.append(P); n0 += len(P)
            self.joint_idx[k] = n0 - 1
        T = np.vstack(segs)
        # extend below the 72 end to the horizon along the raw sky boundary (unscored, keeps the foot continuous)
        end = T[-1]
        ext = [end]
        p = end.copy()
        for _ in range(400):
            if p[1] >= HORIZON - 0.5:
                break
            # walk down along the sdf=0 contour: step down, then re-centre horizontally on the boundary
            q = p + np.array([0.0, 1.0])
            xs = q[0] + np.arange(-6, 6.01, 0.25)
            s = tgt.sample(np.stack([xs, np.full_like(xs, q[1])], -1), comp=False)
            i = np.nonzero(np.diff(np.sign(s)) != 0)[0]
            if len(i):
                j = i[np.argmin(np.abs(xs[i] - q[0]))]
                q[0] = xs[j] - s[j] * (xs[j + 1] - xs[j]) / (s[j + 1] - s[j])
            p = q; ext.append(p.copy())
        self.T = C.resample_poly(T, step=1.0)       # the target ends at the 72 end (display y 735); below it is not scored
        # landmarks on the target
        Ts = self.T
        itop = int(np.argmin(Ts[:, 1]))
        itip = int(np.argmax(Ts[:, 0]))
        seg72 = np.arange(itip, len(Ts))
        low = seg72[(Ts[seg72, 1] > 430) & (Ts[seg72, 1] < 700)]
        iwall = int(low[np.argmin(Ts[low, 0])])
        i735 = len(Ts) - 1
        ij1 = int(np.argmin(np.linalg.norm(Ts - np.array(tgt.seg["130"][0]), axis=1)))
        ij2 = int(np.argmin(np.linalg.norm(Ts - np.array(tgt.seg["131"][0]), axis=1)))
        self.lm = {"start": 0, "j78_130": ij1, "j130_131": ij2, "top": itop, "tip": itip, "wall": iwall, "end72": i735}

    def project(self, X):
        return self.fr.cam.project(X.reshape(-1, 3))


def cand_boundary(pt, c, A, Y):
    """candidate's sky boundary (display px) from the left frame edge over the wave to the horizon, as a polyline."""
    V1, fr, tgt = pt.V1, pt.fr, pt.tgt
    X = fr.world(c, A, Y)
    tris = V1.triangles(A.shape[1], A.shape[0])
    cov = V1.rasterize(fr.cam, X, tris, ss=2)
    Hh, Ww = cov.shape
    m = (cov > 0.5).astype(np.uint8)
    m[int(math.ceil(HORIZON)):, :] = 1
    m[:, :int(tgt.x0)] = m[:, int(tgt.x0):int(tgt.x0) + 1]      # extend the first scored column to the left
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cn = max(cnts, key=cv2.contourArea)[:, 0, :].astype(float)
    # keep only the part above the horizon and right of the frame's left edge, ordered from the left edge
    ok = (cn[:, 1] < HORIZON - 1) & (cn[:, 0] > tgt.x0 + 0.5)
    # rotate so that we start at the first point after a gap
    idx = np.nonzero(ok)[0]
    if len(idx) == 0:
        return None, cov
    brk = np.nonzero(~ok)[0]
    if len(brk):
        start = (brk[0] + 1) % len(cn)
        cn = np.roll(cn, -start, 0); ok = np.roll(ok, -start)
    runs = []; cur = []
    for i, v in enumerate(ok):
        if v:
            cur.append(i)
        elif cur:
            runs.append(cur); cur = []
    if cur:
        runs.append(cur)
    run = max(runs, key=len)
    B = cn[run]
    # orient: start at the left edge (small x) and go over the top
    if B[0, 0] > B[-1, 0] and B[-1, 1] < B[0, 1]:
        B = B[::-1]
    if B[0, 1] > HORIZON - 5:     # started at the horizon: reverse
        B = B[::-1]
    return C.resample_poly(B, step=1.0), cov


def cand_landmarks(B, pt):
    itop = int(np.argmin(B[:, 1]))
    # tip: right-most point of the lip (above y 480, right of the top)
    rr = np.arange(itop, len(B))
    up = rr[B[rr, 1] < 520]
    itip = int(up[np.argmax(B[up, 0])])
    seg = np.arange(itip, len(B))
    low = seg[(B[seg, 1] > 430) & (B[seg, 1] < 700)]
    iwall = int(low[np.argmin(B[low, 0])]) if len(low) else itip + 1
    i735 = int(iwall + np.argmin(np.abs(B[iwall:, 1] - 735.4)))
    # joints by display x along the top part (between start and top)
    tt = np.arange(0, itop + 1)
    ij1 = int(tt[np.argmin(np.abs(B[tt, 0] - pt.tgt.seg["130"][0][0]))])
    ij2 = int(tt[np.argmin(np.abs(B[tt, 0] - pt.tgt.seg["131"][0][0]))])
    return {"start": 0, "j78_130": ij1, "j130_131": ij2, "top": itop, "tip": itip, "wall": iwall, "end72": i735}


def correspond_arclen(B, lb, T, lt):
    keys = ["start", "j78_130", "j130_131", "top", "tip", "wall", "end72"]
    sB = C.arclen(B[:, 0], B[:, 1]); sT = C.arclen(T[:, 0], T[:, 1])
    src, dst = [], []
    for k0, k1 in zip(keys[:-1], keys[1:]):
        b0, b1, t0, t1 = lb[k0], lb[k1], lt[k0], lt[k1]
        if b1 <= b0 or t1 <= t0:
            continue
        n = max(int((sB[b1] - sB[b0]) / 3.0), 2)
        u = np.linspace(0, 1, n, endpoint=False)
        qb = sB[b0] + u * (sB[b1] - sB[b0]); qt = sT[t0] + u * (sT[t1] - sT[t0])
        src.append(np.stack([np.interp(qb, sB, B[:, 0]), np.interp(qb, sB, B[:, 1])], -1))
        dst.append(np.stack([np.interp(qt, sT, T[:, 0]), np.interp(qt, sT, T[:, 1])], -1))
    return np.vstack(src), np.vstack(dst)


def correspond_nearest(B, T, maxd=60.0):
    kd = cKDTree(T)
    d, i = kd.query(B)
    ok = d < maxd
    return B[ok], T[i[ok]]


def backproject_to_plane(pt, P2, c_rows_v):
    """display points (n,2) -> world points on the planes c = c_rows_v (n,)."""
    cam = pt.fr.cam
    D = cam.rays(P2)
    # plane: (X - O) . E = c  ->  (pos + s D - O).E = c
    s = (c_rows_v - (cam.pos - C.O) @ C.E) / (D @ C.E)
    return cam.pos[None, :] + s[:, None] * D


def warp_round(pt, c, A, Y, lam, mode, anchors_grid=True, falloff=None, y_att=(0.0, 2.5), c_att=(-26.0, -20.0), local3d=None, far_att=None):
    B, cov = cand_boundary(pt, c, A, Y)
    if mode == "arclen":
        lb = cand_landmarks(B, pt)
        src, dst = correspond_arclen(B, lb, pt.T, pt.lm)
    else:
        lb = cand_landmarks(B, pt)
        Bu = B[:lb["end72"] + 1]
        src, dst = correspond_nearest(Bu, pt.T)
    # thin the controls to ~4 px spacing
    keep = np.r_[0, np.nonzero(np.cumsum(np.linalg.norm(np.diff(src, axis=0), axis=1)) // 4.0 != 0)[0]]
    _, ui = np.unique(np.round(src / 4.0), axis=0, return_index=True)
    ui = np.sort(ui)
    src, dst = src[ui], dst[ui]
    ctrl = src; vals = dst - src
    if anchors_grid:
        gx, gy = np.meshgrid(np.linspace(-800, 2700, 15), np.linspace(-800, 1900, 12))
        G = np.stack([gx.ravel(), gy.ravel()], -1)
        dmin = cKDTree(src).query(G)[0]
        G = G[dmin > 350]
        hz = np.stack([np.linspace(700, 1500, 9), np.full(9, HORIZON + 60.0)], -1)
        G = np.vstack([G, hz])
        ctrl = np.vstack([ctrl, G]); vals = np.vstack([vals, np.zeros_like(G)])
    w, aff = tps_fit(ctrl, vals, lam)
    # apply to all vertices
    nv, nu = A.shape
    X = pt.fr.world(c, A, Y).reshape(-1, 3)
    P = pt.project(X)
    yv = Y.reshape(-1)
    disp = tps_eval(ctrl, w, aff, P[:, :2])
    cr = np.repeat(c, nu)
    attc = C.smoothstep((cr - c_att[0]) / (c_att[1] - c_att[0])) * C.smoothstep((8.5 - cr) / 2.5) * (P[:, 2] > 1.0)   # the hidden far tail (c > 8.5) keeps its design
    if local3d:
        # the field acts on the surface near the silhouette-forming vertices (3-D distance), not on hidden geometry
        # that merely projects near the outline (back of the wave, tube wall seen through the tube)
        import candA_swarp as SW
        tris = pt.V1.triangles(nu, nv)
        zb = SW.zbuffer(P, tris, 1920, 1080)
        xi = np.round(P[:, 0]).astype(int).clip(0, 1919); yi = np.round(P[:, 1]).astype(int).clip(0, 1079)
        vis = P[:, 2] <= zb[yi, xi] + 0.6
        dB, _ = cKDTree(B[:lb["end72"] + 1] if lb else B).query(P[:, :2])
        silv = np.nonzero((dB <= 2.0) & vis & (yv > 0.4))[0]
        if len(silv):
            d3, _ = cKDTree(X[silv]).query(X)
            attc = attc * np.exp(-(d3 / local3d) ** 2)
    if far_att:
        # loop 2: the hidden far side (c > 0) keeps its design; the field fades out over far_att = (c0, c1, floor)
        c0, c1, fmin = far_att
        attc = attc * (fmin + (1 - fmin) * C.smoothstep((c1 - cr) / (c1 - c0)))
    P2 = P[:, :2] + disp * attc[:, None]
    Xn = backproject_to_plane(pt, P2, np.repeat(c, nu))
    Sn = C.sec(Xn)
    dA = Sn[:, 0] - A.reshape(-1); dY = Sn[:, 1] - yv
    wy = C.smoothstep((yv - y_att[0]) / (y_att[1] - y_att[0]))       # the flat sea stays at y = 0 (slides along a only)
    wlow = C.smoothstep((yv - 0.3) / 2.0)                             # the foot / trough below the scored outline keeps its design
    An = (A.reshape(-1) + dA * wlow).reshape(nv, nu); Yn = (yv + dY * wy * wlow).reshape(nv, nu)
    Xn = pt.fr.world(c, An, Yn).reshape(-1, 3)
    moved = np.linalg.norm(Xn - X, axis=1).reshape(nv, nu)
    res = np.linalg.norm(dst - src, axis=1)
    return An, Yn, moved, {"n_ctrl": int(len(src)), "corr_max_px": float(res.max()), "corr_p95_px": float(np.percentile(res, 95)),
                           "corr_mean_px": float(res.mean()), "move_max_m": float(moved.max()), "landmarks_cand": lb}


def section_crossings(P):
    p, q = P[:-1], P[1:]
    dd = q - p
    dx = dd[:, None, :]; ex = dd[None, :, :]
    w = p[None, :, :] - p[:, None, :]
    den = dx[..., 0] * ex[..., 1] - dx[..., 1] * ex[..., 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (w[..., 0] * ex[..., 1] - w[..., 1] * ex[..., 0]) / den
        t = (w[..., 0] * dx[..., 1] - w[..., 1] * dx[..., 0]) / den
    hit = (np.abs(den) > 1e-12) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
    return int(np.triu(hit, 2).sum())


def snap_round(pt, c, A, Y, band=2.0, target_s=0.2, cap=0.5, sig=2.5, comp=True):
    """final silhouette lock (like gw_wavegen_v1.snap_tps, local): vertices at / outside the (half-width compensated)
    target, or within `band` px inside it, move along the in-plane normal of their row curve so that their image lands
    at sdf = target_s; the move is spread to the surface neighbourhood (Gaussian over rows / columns, sigma `sig`
    grid steps ~ 0.8 m) and is not applied where it would make a row curve cross itself."""
    from scipy.ndimage import gaussian_filter
    tgt, fr = pt.tgt, pt.fr
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = pt.project(X)
    s = tgt.sample(P[:, :2], comp=comp).reshape(nv, nu)
    dA = np.gradient(A, axis=1); dY = np.gradient(Y, axis=1)
    L = np.maximum(np.hypot(dA, dY), 1e-9)
    na, ny = dY / L, -dA / L
    eps = 0.01
    X2 = fr.world(c, A + eps * na, Y + eps * ny).reshape(-1, 3)
    s2 = tgt.sample(pt.project(X2)[:, :2], comp=comp).reshape(nv, nu)
    g = (s2 - s) / eps
    # turning angle per column (exclude tight turns: hook tip)
    h = np.unwrap(np.arctan2(dY, dA), axis=1)
    turn = np.degrees(np.abs(np.gradient(h, axis=1)))
    Pp = P.reshape(nv, nu, 3)
    inframe = (Pp[..., 0] >= tgt.x0 - 2) & (Pp[..., 0] <= tgt.x1 + 2) & (Pp[..., 1] >= 0) & (Pp[..., 1] <= 781) & (Pp[..., 2] > 1)
    sel = (s > -band) & (np.abs(g) > 10.0) & (Y > 0.6) & inframe & (turn < 12.0)
    dd = np.where(sel, (target_s - s) / np.where(sel, g, 1.0), 0.0)
    dd = np.clip(dd, -cap, cap)
    Fa = dd * na; Fy = dd * ny
    w = sel.astype(float)
    ws = gaussian_filter(w, sig)
    Fas = gaussian_filter(Fa * w, sig) / np.maximum(ws, 1e-6)
    Fys = gaussian_filter(Fy * w, sig) / np.maximum(ws, 1e-6)
    conf = np.clip(ws / max(ws.max(), 1e-9) * 4.0, 0, 1)
    Fa2 = Fas * conf; Fy2 = Fys * conf          # smooth everywhere (no single-vertex kinks); repeated rounds converge
    Fy2 = Fy2 * C.smoothstep(Y / 2.5)
    An = A + Fa2; Yn = Y + Fy2
    reverted = 0
    for r in range(nv):
        if np.abs(Fa2[r]).max() < 1e-6 and np.abs(Fy2[r]).max() < 1e-6:
            continue
        if section_crossings(np.stack([An[r], Yn[r]], -1)) > section_crossings(np.stack([A[r], Y[r]], -1)):
            An[r], Yn[r] = A[r], Y[r]; reverted += 1
    return An, Yn, {"n_sel": int(sel.sum()), "s_max_px": float(s[sel].max()) if sel.any() else 0.0,
                    "move_max_m": float(np.hypot(Fa2, Fy2).max()), "rows_reverted": reverted}


def main():
    pre, out = sys.argv[1], sys.argv[2]
    rounds = json.loads(sys.argv[sys.argv.index("--rounds") + 1]) if "--rounds" in sys.argv else [
        ["arclen", 3000.0], ["arclen", 1000.0], ["arclen", 300.0], ["nearest", 100.0], ["nearest", 30.0], ["nearest", 10.0]]
    z = np.load(pre); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    pt = Painting()
    A0, Y0 = A.copy(), Y.copy()
    log = []
    for k, rd in enumerate(rounds):
        mode, lam = rd[0], rd[1]
        loc = rd[2] if len(rd) > 2 else None
        A, Y, moved, info = warp_round(pt, c, A, Y, lam, mode, local3d=loc)
        info.update(round=k, mode=mode, lam=lam)
        info.pop("landmarks_cand", None)
        log.append(info)
        print(json.dumps(info), flush=True)
    nsnap = int(sys.argv[sys.argv.index("--snap") + 1]) if "--snap" in sys.argv else 8
    for k in range(nsnap):
        A, Y, info = snap_round(pt, c, A, Y)
        info.update(round="snap%d" % k); log.append(info); print(json.dumps(info), flush=True)
    X0 = C.world(c, A0, Y0); X1 = C.world(c, A, Y)
    mag = np.linalg.norm(X1 - X0, axis=-1)
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0, warp_mag=mag)
    json.dump({"rounds": log, "warp_mag_max_m": float(mag.max()), "warp_mag_p95_m": float(np.percentile(mag[Y0 > 0.5], 95))},
              open(os.path.splitext(out)[0] + "_warp.json", "w"), indent=1)
    print("warp max %.2f m" % mag.max())


if __name__ == "__main__":
    main()
