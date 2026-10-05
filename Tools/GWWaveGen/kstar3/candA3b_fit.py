# -*- coding: utf-8 -*-
"""Q21 candidate A3b, step 4: EDGE-ONLY silhouette lock to the painting (PaintingCam v1).

Only the vertices that FORM the candidate's painting-view silhouette (visible, on the sky boundary of the coverage, near
the painted main-wave outline 78/130/131/132/72) are given a target move: along the in-plane normal of their row curve,
so that their image lands on the painted outline (half-width compensated sky sdf = target_s).  The moves are spread over
the surface with a compact falloff band: along the row by arc length (Gaussian sigma_s, cut at 3 sigma_s) and across rows
(Gaussian sigma_c in metres of c); vertices farther than the band from any silhouette vertex never move (the interior
stays the smoothed large form).  Rounds repeat (new silhouette vertices appear as the outline moves).  The accumulated
3-D move per vertex is the deformation field reported for Q21-1 (edge band vs interior).
usage: py -3.10 candA3b_fit.py in_rows.npz out_rows.npz [rounds=14]
"""
import sys, os, json, math, time
import numpy as np
import cv2
from scipy.spatial import cKDTree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3b_common as B
import fin2_warp as W
import candA_swarp as SW


def silhouette_vertices(pt, c, A, Y, near_px=40.0, tol_px=1.8):
    V1, fr, tgt = pt.V1, pt.fr, pt.tgt
    nv, nu = A.shape
    X = fr.world(c, A, Y).reshape(-1, 3)
    P = fr.cam.project(X)
    tris = V1.triangles(nu, nv)
    cov = V1.rasterize(fr.cam, X, tris, ss=2)
    m = (cov > 0.5).astype(np.uint8)
    m[int(math.ceil(B.HORIZON)):, :] = 1
    cnts, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    bd = np.vstack([cn[:, 0, :] for cn in cnts]).astype(float)
    bd = bd[(bd[:, 1] < B.HORIZON - 1) & (bd[:, 0] > tgt.x0) & (bd[:, 0] < tgt.x1)]
    zb = SW.zbuffer(P, tris, 1920, 1080)
    xi = np.round(P[:, 0]).astype(int).clip(0, 1919); yi = np.round(P[:, 1]).astype(int).clip(0, 1079)
    vis = P[:, 2] <= zb[yi, xi] + 0.6
    dB, _ = cKDTree(bd).query(P[:, :2]) if len(bd) else (np.full(len(P), 1e9), None)
    dT, _ = cKDTree(pt.T).query(P[:, :2])
    yv = Y.reshape(-1)
    sil = vis & (dB <= tol_px) & (dT <= near_px) & (yv > 0.5) & (P[:, 2] > 1) & (P[:, 1] < B.HORIZON - 2)
    return sil.reshape(nv, nu), P.reshape(nv, nu, 3), cov


def spread(c, A, Y, Da, Dy, w, sig_s, sig_c, cut=3.0):
    """normalised Gaussian spreading of the per-vertex moves (Da, Dy) with weights w: along each row by arc length
    (sigma sig_s, compact support cut*sig_s), then across rows (sigma sig_c in metres, compact support)."""
    nv, nu = A.shape
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1)), 1)], 1)
    Na = np.zeros_like(A); Ny = np.zeros_like(A); Nw = np.zeros_like(A)
    for r in range(nv):
        js = np.nonzero(w[r] > 0)[0]
        if len(js) == 0:
            continue
        d = s[r][:, None] - s[r][js][None, :]
        K = np.exp(-0.5 * (d / sig_s) ** 2) * (np.abs(d) < cut * sig_s)
        Na[r] = K @ (w[r, js] * Da[r, js]); Ny[r] = K @ (w[r, js] * Dy[r, js]); Nw[r] = K @ w[r, js]
    # across rows (compact)
    Kc = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig_c) ** 2) * (np.abs(c[:, None] - c[None, :]) < cut * sig_c)
    Na2 = Kc @ Na; Ny2 = Kc @ Ny; Nw2 = Kc @ Nw
    Kc1 = Kc @ np.ones(nv)
    conf = np.clip(Nw2 / 0.8, 0, 1)                    # ~1 at and next to a silhouette vertex
    fa = np.where(Nw2 > 1e-9, Na2 / np.maximum(Nw2, 1e-12), 0.0) * conf
    fy = np.where(Nw2 > 1e-9, Ny2 / np.maximum(Nw2, 1e-12), 0.0) * conf
    return fa, fy


def lock_round(pt, c, A, Y, target_s=-0.4, cap=0.6, sig_s=1.2, sig_c=0.35, near_px=40.0, x_min=None):
    tgt, fr = pt.tgt, pt.fr
    nv, nu = A.shape
    sil, P, cov = silhouette_vertices(pt, c, A, Y, near_px=near_px)
    s = tgt.sample(P.reshape(-1, 3)[:, :2], comp=True).reshape(nv, nu)
    dA = np.gradient(A, axis=1); dY = np.gradient(Y, axis=1)
    L = np.maximum(np.hypot(dA, dY), 1e-9)
    na, ny = dY / L, -dA / L                      # in-plane normal (outward for the row's upper side)
    eps = 0.02
    X2 = fr.world(c, A + eps * na, Y + eps * ny).reshape(-1, 3)
    s2 = tgt.sample(fr.cam.project(X2)[:, :2], comp=True).reshape(nv, nu)
    g = (s2 - s) / eps
    ok = sil & (np.abs(g) > 5.0)
    if x_min is not None:
        ok &= P[..., 0] >= x_min
    dd = np.where(ok, (target_s - s) / np.where(ok, g, 1.0), 0.0)
    dd = np.clip(dd, -cap, cap)
    Da = dd * na; Dy = dd * ny
    fa, fy = spread(c, A, Y, Da, Dy, ok.astype(float), sig_s, sig_c)
    fy = fy * C.smoothstep(Y / 1.5)
    fa = fa * C.smoothstep(Y / 1.0)
    An = A + fa; Yn = Y + fy
    reverted = 0
    for r in range(nv):
        if np.abs(fa[r]).max() < 1e-7 and np.abs(fy[r]).max() < 1e-7:
            continue
        if W.section_crossings(np.stack([An[r], Yn[r]], -1)) > W.section_crossings(np.stack([A[r], Y[r]], -1)):
            An[r], Yn[r] = A[r], Y[r]; reverted += 1
    res = s[sil]
    return An, Yn, {"n_sil": int(sil.sum()), "n_move": int(ok.sum()), "s_sil_max": float(res.max()) if len(res) else 0.0,
                    "s_sil_min": float(res.min()) if len(res) else 0.0, "s_sil_p95abs": float(np.percentile(np.abs(res), 95)) if len(res) else 0.0,
                    "move_max_m": float(np.hypot(fa, fy).max()), "rows_reverted": reverted}


def flipped_quads(V1, c, A, Y):
    nv, nu = A.shape
    X = C.world(c, A, Y).reshape(-1, 3)
    tris = V1.triangles(nu, nv)
    fn = np.cross(X[tris[:, 1]] - X[tris[:, 0]], X[tris[:, 2]] - X[tris[:, 0]])
    un = fn / np.maximum(np.linalg.norm(fn, axis=1), 1e-15)[:, None]
    return ((un[0::2] * un[1::2]).sum(1) < -0.866).reshape(nv - 1, nu - 1)


def unflip(pt, c, A, Y, max_iter=80):
    """mesh hygiene: flipped quads (the two triangles of a quad facing opposite ways: column zig-zags of a few mm)
    are removed by in-plane Laplacian smoothing of their vertices and the next ones (rows stay planar)."""
    hist = []
    for it in range(max_iter):
        fl = flipped_quads(pt.V1, c, A, Y)
        n = int(fl.sum()); hist.append(n)
        if n == 0:
            break
        nv, nu = A.shape
        mark = np.zeros((nv, nu), bool)
        for r, j in zip(*np.nonzero(fl)):
            mark[max(r - 1, 0):r + 3, max(j - 2, 0):j + 4] = True
        mark[:, 0] = mark[:, -1] = False; mark[0, :] = mark[-1, :] = False
        An = A.copy(); Yn = Y.copy()
        An[1:-1, 1:-1] = 0.5 * A[1:-1, 1:-1] + 0.25 * (A[1:-1, :-2] + A[1:-1, 2:])
        Yn[1:-1, 1:-1] = 0.5 * Y[1:-1, 1:-1] + 0.25 * (Y[1:-1, :-2] + Y[1:-1, 2:])
        if it > 20:
            An[1:-1, 1:-1] = 0.5 * A[1:-1, 1:-1] + 0.125 * (A[:-2, 1:-1] + A[2:, 1:-1] + A[1:-1, :-2] + A[1:-1, 2:])
            Yn[1:-1, 1:-1] = 0.5 * Y[1:-1, 1:-1] + 0.125 * (Y[:-2, 1:-1] + Y[2:, 1:-1] + Y[1:-1, :-2] + Y[1:-1, 2:])
        A = np.where(mark, An, A); Y = np.where(mark, Yn, Y)
    return A, Y, hist


def creases(c, A, Y, thr=30.0):
    X = C.world(c, A, Y)
    d1 = X[1:, 1:] - X[:-1, :-1]; d2 = X[:-1, 1:] - X[1:, :-1]
    n = np.cross(d1, d2); qa = np.linalg.norm(n, axis=-1); n = n / np.maximum(qa, 1e-15)[..., None]
    ym = np.maximum.reduce([Y[:-1, :-1], Y[1:, :-1], Y[:-1, 1:], Y[1:, 1:]])
    ok = (qa > 1e-6) & (ym > 0.3)
    vr = np.degrees(np.arccos(np.clip((n[:-1] * n[1:]).sum(-1), -1, 1)))
    along = np.degrees(np.arccos(np.clip((n[:, :-1] * n[:, 1:]).sum(-1), -1, 1)))
    return (ok[:-1] & ok[1:] & (vr > thr)), vr, (ok[:, :-1] & ok[:, 1:] & (along > thr))


def uncrease(pt, c, A, Y, max_iter=60, thr=30.0):
    """mesh hygiene: cross-row creases > thr degrees are relaxed by an in-plane Laplacian ACROSS the rows on the
    vertices around them (rows stay planar; each vertex moves toward the average of its neighbours in the next rows)."""
    hist = []
    for it in range(max_iter):
        cr, vr, al = creases(c, A, Y, thr)
        n = int(cr.sum()); hist.append(n)
        if n == 0:
            break
        nv, nu = A.shape
        mark = np.zeros((nv, nu), bool)
        for r, j in zip(*np.nonzero(cr)):
            mark[max(r - 1, 0):r + 4, max(j - 1, 0):j + 3] = True
        mark[:, 0] = mark[:, -1] = False; mark[0, :] = mark[-1, :] = False
        An = A.copy(); Yn = Y.copy()
        An[1:-1, 1:-1] = 0.5 * A[1:-1, 1:-1] + 0.25 * (A[:-2, 1:-1] + A[2:, 1:-1])
        Yn[1:-1, 1:-1] = 0.5 * Y[1:-1, 1:-1] + 0.25 * (Y[:-2, 1:-1] + Y[2:, 1:-1])
        A = np.where(mark, An, A); Y = np.where(mark, Yn, Y)
    return A, Y, hist


def gate(pt, c, A, Y, png=None):
    V1 = pt.V1
    g = V1.preview_metrics(pt.fr, pt.tgt, pt.fr.world(c, A, Y), V1.triangles(A.shape[1], A.shape[0]),
                           png or os.path.join(B.WORK, "_lockgate.png"), "A3b lock")
    return {k: (round(v["max_px"], 2), round(v["p95_px"], 2)) for k, v in g.items()}


def relax(c, A, Y, prm):
    """low-frequency regularisation of the whole sheet between lock passes: local-linear Gaussian along the crest
    (sigma by c) and a light arc-length Laplacian along each row (no painting data; keeps the forms smooth)."""
    import fin2_relax as RX
    tab = prm["relax_sigma_c"]
    sg = np.interp(c, [t_[0] for t_ in tab], [t_[1] for t_ in tab])
    w = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0)
    w = np.maximum(w, np.roll(w, 1, 1)); w = np.maximum(w, np.roll(w, -1, 1))
    A2, Y2 = RX.cross_rows_ll(A, Y, c, sg, weight=w)
    for _ in range(prm.get("row_lap_iters", 2)):
        la = 0.5 * (np.roll(A2, 1, 1) + np.roll(A2, -1, 1)) - A2; ly = 0.5 * (np.roll(Y2, 1, 1) + np.roll(Y2, -1, 1)) - Y2
        la[:, [0, -1]] = 0; ly[:, [0, -1]] = 0
        A2 = A2 + prm.get("row_lap", 0.3) * la * w; Y2 = Y2 + prm.get("row_lap", 0.3) * ly * w
    return A2, Y2


def main(inp, out, rounds=14, log=print, prm=None):
    t0 = time.time()
    z = np.load(inp)
    A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    A0, Y0 = A.copy(), Y.copy()
    pt = W.Painting()
    fp = (prm or {}).get("fit", {})
    hist = []
    for outer in range(fp.get("relax_loops", 0)):
        A, Y = relax(c, A, Y, fp)
        for k in range(fp.get("lock_per_loop", 6)):
            A, Y, inf = lock_round(pt, c, A, Y, sig_s=fp.get("sig_s", 1.4), sig_c=fp.get("sig_c", 0.55), cap=fp.get("cap", 0.4))
            inf.update(round="relax%d_%d" % (outer, k)); hist.append(inf)
        gg = gate(pt, c, A, Y); hist.append({"round": "relax%d" % outer, "gate": gg}); log("relax loop %d gate %s  %.0fs" % (outer, json.dumps(gg), time.time() - t0))
    sched = [tuple(x) for x in fp.get("sched", [(1.8, 0.9, 0.5), (1.6, 0.85, 0.4), (1.5, 0.8, 0.35), (1.4, 0.75, 0.3), (1.3, 0.7, 0.25), (1.2, 0.65, 0.2)])]
    for k in range(rounds):
        sig_s, sig_c, cap = sched[min(k // 3, len(sched) - 1)]
        A, Y, inf = lock_round(pt, c, A, Y, sig_s=sig_s, sig_c=sig_c, cap=cap)
        inf.update(round=k, sig_s=sig_s, sig_c=sig_c); hist.append(inf); log(json.dumps(inf))
        if k % 4 == 3 or k == rounds - 1:
            gg = gate(pt, c, A, Y); hist.append({"round": k, "gate": gg}); log("gate %s  %.0fs" % (json.dumps(gg), time.time() - t0))
    def score(gg):
        # the F01 gate as one number: the worst excess over the limits (78/130/131/132 max 4 px, 72 p95 4 px)
        return max(max(gg[k][0] for k in ("78", "130", "131", "132")) - 4.0, gg["72"][1] - 4.0, -4.0) + 0.05 * gg["72"][1]
    best = (score(gate(pt, c, A, Y)), A.copy(), Y.copy())
    for k in range(fp.get("polish_rounds", 0)):
        # polish: a narrower band (the painted claw heads of 132 / 72 at the lip hook); keep the best state
        A, Y, inf = lock_round(pt, c, A, Y, sig_s=fp.get("polish_sig_s", 0.7), sig_c=fp.get("polish_sig_c", 0.35), cap=0.2, x_min=fp.get("polish_x_min"))
        inf.update(round="polish%d" % k); hist.append(inf)
        if k % 4 == 3 or k == fp.get("polish_rounds", 0) - 1:
            gg = gate(pt, c, A, Y); sc_ = score(gg)
            hist.append({"round": "polish%d" % k, "gate": gg, "score": sc_}); log("polish %d gate %s score %.2f" % (k, json.dumps(gg), sc_))
            if sc_ < best[0]:
                best = (sc_, A.copy(), Y.copy())
    if fp.get("polish_rounds", 0):
        A, Y = best[1], best[2]
        gg = gate(pt, c, A, Y); hist.append({"round": "polish_best", "gate": gg}); log("polish best gate %s  %.0fs" % (json.dumps(gg), time.time() - t0))
    if fp.get("untangle", True):
        # mesh hygiene: untangle local 3-D self-intersections (in-plane smoothing of the touching vertices only)
        A, Y, hist_u, mv = pt.V1.fix_self_intersections(pt.fr, c, A, Y, max_iter=60, win=12)
        gg = gate(pt, c, A, Y); hist.append({"round": "untangle", "history": hist_u, "move_max_m": mv, "gate": gg})
        log("untangle %s move %.3f gate %s" % (hist_u[:6], mv, json.dumps(gg)))
    if fp.get("respace", False):
        # mesh hygiene: even out the column spacing along each row ON the row polyline (the shape does not change):
        # clustered columns (a few mm apart) zig-zag and give flipped quads
        from scipy.ndimage import gaussian_filter1d as g1
        for r in range(A.shape[0]):
            a, y = A[r], Y[r]
            s_ = np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]
            if s_[-1] < 1e-6:
                continue
            ds = np.maximum(np.diff(s_), 0.0)
            ds2 = np.maximum(g1(ds, fp.get("respace_sigma_cols", 1.5), mode="nearest"), 1e-4)
            ds2 *= s_[-1] / ds2.sum()
            # keep the landmark columns where they are (the grid's meaning)
            s_new = np.r_[0.0, np.cumsum(ds2)]
            for j0, j1 in zip([0] + list(C.LM.values()), list(C.LM.values()) + [len(a) - 1]):
                if j1 <= j0:
                    continue
                t = (s_new[j0:j1 + 1] - s_new[j0]) / max(s_new[j1] - s_new[j0], 1e-9)
                s_new[j0:j1 + 1] = s_[j0] + t * (s_[j1] - s_[j0])
            A[r] = np.interp(s_new, s_, a); Y[r] = np.interp(s_new, s_, y)
        gg = gate(pt, c, A, Y); hist.append({"round": "respace", "gate": gg}); log("respace gate %s" % json.dumps(gg))
    if fp.get("unflip", True):
        A, Y, nfl = unflip(pt, c, A, Y)
        A, Y, hu2, mv2 = pt.V1.fix_self_intersections(pt.fr, c, A, Y, max_iter=60, win=12)
        A, Y, nfl2 = unflip(pt, c, A, Y)
        nfl = nfl + ["untangle %s" % hu2[:3]] + nfl2
        gg = gate(pt, c, A, Y); hist.append({"round": "unflip", "flips_history": nfl, "gate": gg}); log("unflip %s gate %s" % (nfl[:8], json.dumps(gg)))
    mag = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    extra = {k: z[k] for k in z.files if k not in ("A", "Y", "c")}
    np.savez_compressed(out, A=A, Y=Y, c=c, A_prefit=A0, Y_prefit=Y0, fit_mag=mag, **extra)
    json.dump({"rounds": hist, "fit_mag_max_m": float(mag.max()), "fit_mag_p99_m": float(np.percentile(mag, 99))},
              open(os.path.splitext(out)[0] + "_fit.json", "w"), indent=1, default=float)
    log("fit max %.2f m, p99 %.2f m, %.0fs" % (mag.max(), np.percentile(mag, 99), time.time() - t0))


if __name__ == "__main__":
    prm = json.load(open(sys.argv[4], encoding="utf-8")) if len(sys.argv) > 4 else json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "candA3b_params.json"), encoding="utf-8"))
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 14, prm=prm)
