# -*- coding: utf-8 -*-
"""K*′ 精修 R4：整えの層（kh_designR4 の sculpt_01..15 の ramp の鍵）を解く（py -3.10、scipy、約 2 分）。

形は鍵に対して正確に線形（X(θ) = X_pre + Σ θ_bk φ_bk n_pre。n_pre は sculpt の前の形の断面の法線、φ は列の帯 × c の B-spline の基底 ×
sculpt_scale）なので、測りだけを線形化して、減衰つきの Gauss-Newton（1 回の歩み ≤ --steplim m）でくり返し、いちばんよい回を残す。
最小にするもの（重みつきの 2 乗和。片側の条件は超えそうな所だけ）：
  1 評審の膨らみの測り（kh_R1_quick.bulge6 と同じ式：局所の 2 次曲面を半径 4 m・6 m で当てた中心の残差、列 18〜120）。中心の残差は、近くの
    頂点の変位の線形の和（2 次曲面の当てはめの擬似逆行列の 0 行目）。大きな残差ほど重い（--tail）。
  2 上から見た背のくびれ：高さ 1〜--notch-hmax m の背の平面の線 a_b(c) の ±4 m の弦からの前への出（c −10〜+12）と、高さ 1〜7 m の
    手前の肩と尾（c −34〜−10.5）が --notch を超えない。評審の台本（弦の端を c −14 に留める）の y 3・6 m の値（c −14〜−10.5）も同じ。
  3 原画視点の輪郭を動かさない（sculpt の前の形で決める）：外の輪郭（空との境）から 3 px 以内に写る頂点は像の境の法線の向きの動きを 0 へ
    （両向き、--pin）、3〜30 px の頂点は外へ出ない（片側）、c −22〜−1 の見えていて視線がかすめる頂点（b 区域の稜などの中の輪郭）は面の法線の
    向きの動き [px] を 0 へ。
  4 薄い所（背・頂・唇の上面から反対の面までが 2.5 m 未満）は、厚みの 0.6 倍より内へ動かさない（片側）。
  5 奥の行（c 6.5〜13）の唇の上面が頂の列 90 より高くならない（片側）。
  6 なめらかさ：鍵の c 方向の 2 階差、変位の場の列方向・c 方向の 2 階差（--lamdc / --lamdr）、背と頂の面そのものの c 方向の 2 階差
    （--wfair、背の縦の筋）、鍵の大きさ。
usage: py -3.10 kh_R4_sculpt.py in.json out.json [--iters 16] [--pin 50] [--bound 1.5] [--notch 1.0] [--notch-hmax 10] [--wr4 3] [--t4 0.2]
                                               [--lamdc 10] [--lamdr 1] [--wfair 0.5]
R4 の納品の設計はこの引数（kh_R4_make_design.py の SCULPT_ARGS）で解いた。
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "4")
import sys
import json
import time
import math
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import scipy.sparse as sp  # noqa: E402
import cv2  # noqa: E402
import kh_designR4 as D  # noqa: E402

UPV = np.array([0.0, 1.0, 0.0])
SCULPT_KEYS = [-60.0, -40.0, -34.0, -30.0, -27.0, -24.0, -21.5, -19.5] + [float(x) for x in np.arange(-18.0, 14.01, 1.0)] + [15.0, 16.0, 18.0]
ZERO_KEYS = (-60.0, -40.0, 15.0, 16.0, 18.0)          # held at 0 (the far closing rows and the near tail far away)


# ------------------------------------------------------------------ basis
def key_basis(kc, c):
    n = len(kc)
    return np.stack([D.bspline_ramp(kc, np.eye(n)[i], c) for i in range(n)], 1)


def basis_matrix(c, Ypre, kc):
    """sparse (nv*nu, K*nk): displacement (m along the in-plane normal) of every vertex per unit key value."""
    nv, nu = Ypre.shape
    Bc = key_basis(kc, c)                           # (nv, nk)
    Bc[np.abs(Bc) < 1e-7] = 0.0
    W = D.sculpt_band_weights(nu)                   # (K, nu)
    W[W < 1e-5] = 0.0
    body = D.sculpt_scale(Ypre, c)                  # (nv, nu) body mask x low-row fade x lip scale x crest-top mask
    nk = len(kc); K = W.shape[0]
    rows, cols, vals = [], [], []
    for b in range(K):
        js = np.nonzero(W[b] > 0)[0]
        for k in range(nk):
            rs = np.nonzero(Bc[:, k] != 0)[0]
            if len(rs) == 0:
                continue
            R_, J_ = np.meshgrid(rs, js, indexing="ij")
            v = Bc[R_, k] * W[b, J_] * body[R_, J_]
            m = np.abs(v) > 1e-9
            rows.append((R_ * nu + J_)[m]); cols.append(np.full(m.sum(), b * nk + k)); vals.append(v[m])
    Phi = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(nv * nu, K * nk))
    return Phi


def theta_from_design(d, kc):
    c = D.c_rows()
    B = key_basis(kc, c)
    th = []
    for n in D.SCULPT_NAMES:
        cur = D.bspline_ramp(d.keys[n][0], d.keys[n][1], c) if len(d.keys[n][0]) > 1 else np.full(len(c), d.keys[n][1][0])
        if np.max(np.abs(cur)) < 1e-9:
            th.append(np.zeros(len(kc))); continue
        v, *_ = np.linalg.lstsq(B, cur, rcond=None)
        th.append(v)
    return np.concatenate(th)


def set_theta(d, th, kc):
    nk = len(kc)
    for b, n in enumerate(D.SCULPT_NAMES):
        v = th[b * nk:(b + 1) * nk]
        d.keys[n] = (list(kc), [round(float(x), 5) for x in v])


# ------------------------------------------------------------------ camera
class Cam:
    def __init__(self):
        import candA_common as C
        import gw_wavegen as G0
        V1, tgt, fr = C.painting_frame()
        self.V1, self.tgt, self.fr, self.cam = V1, tgt, fr, fr.cam
        self.seacov, _ = G0.sea_horizon_cover(fr.cam, tgt.spec)

    def proj(self, X):
        return self.cam.project(X.reshape(-1, 3)).reshape(X.shape[:-1] + (3,))

    def jac(self, X):
        """(…, 2, 3) d(px)/dX."""
        cam = self.cam
        d = X - cam.pos
        cx, cy, cz = d @ cam.r, d @ cam.u, d @ cam.f
        kx = 0.5 * cam.W / (cam.t * cam.asp); ky = 0.5 * cam.H / cam.t
        Jx = kx * (cam.r[None, :] * cz[..., None] - cam.f[None, :] * cx[..., None]) / (cz[..., None] ** 2)
        Jy = -ky * (cam.u[None, :] * cz[..., None] - cam.f[None, :] * cy[..., None]) / (cz[..., None] ** 2)
        return np.stack([Jx, Jy], -2), cz

    def coverage(self, X, nu, nv):
        return self.V1.rasterize(self.cam, X, self.V1.triangles(nu, nv))


def pin_rows(cam, c, A, Y, n3, sil_px=3.0, band_px=30.0, graze=0.15, c_inner=(-22.0, -1.0)):
    """reference image data of the pre-sculpt shape.
    returns per vertex: dpx (distance of the projection to the wave/sky boundary), s1 (px per metre of normal displacement along the
    outward boundary normal), sil (dpx <= sil_px: the outline vertices, both directions pinned), band (sil_px < dpx <= band_px: only
    outward motion limited), w2 (visible grazing vertices of rows c_inner, not under the reference sea: the inner outlines such as
    the b-region ridge, both directions pinned; s2 = px per metre along the surface normal)."""
    nv, nu = A.shape
    X = D.world_u(c, A, Y)
    Pp = cam.proj(X)
    cov = cam.coverage(X, nu, nv)
    other = np.maximum(cov, cam.seacov)
    sky = other < 0.5
    wave = cov >= 0.5
    k3 = np.ones((3, 3), np.uint8)
    bnd = wave & cv2.dilate(sky.astype(np.uint8), k3).astype(bool)
    dist, lab = cv2.distanceTransformWithLabels((~bnd).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    cs = cv2.GaussianBlur(cov.astype(np.float32), (0, 0), 3.0)
    gy, gx = np.gradient(cs)
    gn = np.hypot(gx, gy) + 1e-9
    gxs, gys = -gx / gn, -gy / gn
    by, bx = np.nonzero(bnd)
    labs_b = lab[by, bx]
    nx_of = np.zeros(lab.max() + 1, np.float32); ny_of = np.zeros(lab.max() + 1, np.float32)
    nx_of[labs_b] = gxs[by, bx]; ny_of[labs_b] = gys[by, bx]
    H, W = cov.shape
    px = np.clip(np.round(Pp[..., 0]).astype(int), 0, W - 1); py = np.clip(np.round(Pp[..., 1]).astype(int), 0, H - 1)
    inside = (Pp[..., 0] >= 0) & (Pp[..., 0] < W) & (Pp[..., 1] >= 0) & (Pp[..., 1] < H)
    dpx = np.where(inside, dist[py, px], 1e9)
    g = np.stack([nx_of[lab[py, px]], ny_of[lab[py, px]]], -1)
    J, depth = cam.jac(X)
    body = D.body_mask(Y) > 0.02
    s1 = np.einsum("...i,...ij,...j->...", g, J, n3)
    sil = body & (dpx <= sil_px)
    band = body & (dpx > sil_px) & (dpx <= band_px)
    zb = np.full((H, W), np.inf)
    np.minimum.at(zb, (py[inside], px[inside]), Pp[..., 2][inside])
    zb = -cv2.dilate((-np.where(np.isfinite(zb), zb, 1e6)).astype(np.float32), np.ones((5, 5), np.uint8))
    vis = inside & (Pp[..., 2] <= zb[py, px] + 0.6)
    du = np.gradient(X, axis=1); dv = np.gradient(X, axis=0)
    N = np.cross(dv, du); N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-12)
    ray = X - cam.cam.pos; ray /= np.linalg.norm(ray, axis=-1, keepdims=True)
    cosv = np.sum(N * ray, -1)
    fpx = 0.5 * cam.cam.H / cam.cam.t
    undersea = cam.seacov[py, px] > 0.5
    rowsel = ((c >= c_inner[0]) & (c <= c_inner[1]))[:, None]
    w2 = vis * np.exp(-(cosv / graze) ** 2) * body * (dpx > sil_px) * (~undersea) * rowsel
    s2 = np.sum(N * n3, -1) * fpx / depth
    return {"dpx": dpx, "s1": s1, "sil": sil, "band": band, "w2": w2, "s2": s2, "vis": vis, "cov": cov}


def lip_top_thickness(A, Y, j0=18, j1=190, k0=196, k1=394):
    """(nv, nu) distance of the outer-side vertices (cols j0..j1: back, crest, lip top) to the inner side of the same row (cols k0..k1:
    tip cap, lip underside, tube, face; densified 4x); 99 elsewhere and on the sea."""
    from scipy.spatial import cKDTree
    out = np.full(A.shape, 99.0)
    t = np.linspace(0, 1, 4, endpoint=False)[None, :, None]
    for r in range(A.shape[0]):
        if Y[r].max() < 0.5:
            continue
        L = np.stack([A[r, k0:k1 + 1], Y[r, k0:k1 + 1]], -1)
        L = L[L[:, 1] > 0.05] if (L[:, 1] > 0.05).sum() > 3 else L
        Ld = (L[:-1, None, :] * (1 - t) + L[1:, None, :] * t).reshape(-1, 2)
        tr = cKDTree(Ld)
        U = np.stack([A[r, j0:j1 + 1], Y[r, j0:j1 + 1]], -1)
        dd, _ = tr.query(U)
        ok = Y[r, j0:j1 + 1] > 0.3
        out[r, j0:j1 + 1] = np.where(ok, dd, 99.0)
    return out


def fartop3_rows(c, A, Y, n2, Phi, c0=6.0, c1=13.8, j0=60, j1=184, s_=4):
    """third differences (2-D) of the far-row sections over the top region: (value (m), G) pairs; minimising them evens out the
    curvature of the top (no crease between the crest and the lip head, Q17)."""
    nv, nu = A.shape
    vals, G = [], []
    co = (1.0, -3.0, 3.0, -1.0)
    for r in range(nv):
        if not (c0 <= c[r] <= c1) or Y[r].max() < 2.0:
            continue
        H = Y[r].max()
        sc = 1.0 / max(H / 15.0, 0.3)
        for j in range(j0, j1 - 3 * s_ + 1, 2):
            js = [j + k * s_ for k in range(4)]
            rowsP = Phi[[r * nu + jj for jj in js]].toarray()
            for q in range(2):
                P_ = A if q == 0 else Y
                val = sum(cf * P_[r, jj] for cf, jj in zip(co, js)) * sc
                g = sum(cf * rowsP[k] * n2[r, jj, q] for k, (cf, jj) in enumerate(zip(co, js))) * sc
                vals.append(val); G.append(g)
    return np.array(vals), np.array(G)


# ------------------------------------------------------------------ bulge (linearised)
def bulge_lin(c, A, Y, n3, Phi, radii=(4.0, 6.0), row_step=2, col_step=3, jmax=120):
    """-> dict R: (residual r (n,), G (n, ncoef) dense, centres [(r, j)])."""
    X = D.world_u(c, A, Y)
    nv, nu = A.shape
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.linalg.norm(np.diff(X, axis=1), axis=-1), 1)], 1)
    rows = [r for r in range(nv) if abs(c[r]) <= 16][::row_step]
    Xf = X.reshape(-1, 3); nf = n3.reshape(-1, 3)
    out = {}
    for Rm in radii:
        res, G, cen = [], [], []
        for r0 in rows:
            rs = np.nonzero(np.abs(c - c[r0]) <= Rm)[0][::2]
            for j0 in range(18, jmax + 1, col_step):
                if Y[r0, j0] < 0.5 or j0 > 200 - 12:
                    continue
                idx = []
                for r in rs:
                    jj = np.nonzero((np.abs(s[r] - s[r, j0]) <= Rm) & (np.arange(nu) <= 192))[0][::2]
                    idx.append(r * nu + jj)
                idx = np.concatenate(idx)
                P = Xf[idx]
                keep = np.linalg.norm(P - X[r0, j0], axis=1) <= Rm
                idx = idx[keep]; P = P[keep]
                if len(P) < 30:
                    continue
                mu = P.mean(0); _, _, Vt = np.linalg.svd(P - mu, full_matrices=False)
                Q = P - X[r0, j0]; u = Q @ Vt[0]; v = Q @ Vt[1]; w = Q @ Vt[2]
                Mx = np.c_[np.ones_like(u), u, v, u * u, u * v, v * v]
                beta = np.linalg.pinv(Mx)[0]
                co0 = float(beta @ w)
                ic = r0 * nu + j0
                # the judges' value is |co0|; the sign: + = the centre sits inside (below) the local fit
                a = beta * (nf[idx] @ Vt[2])
                g = Phi[idx].T @ a - Phi[ic].toarray()[0] * float(nf[ic] @ Vt[2]) * beta.sum()
                res.append(co0); G.append(np.asarray(g).ravel()); cen.append((r0, j0))
        out["R%g" % Rm] = (np.array(res), np.array(G), cen)
    return out


# ------------------------------------------------------------------ back plan notch (linearised)
def back_cross(A, Y, n2, r, h):
    """a of the back crossing of height h in row r (cols 0..top) and its derivative weights [(vertex col, coef)] per metre of the
    normal displacement of those vertices; None if the row is lower."""
    top = int(np.argmax(Y[r]))
    y = Y[r, :top + 1]; a = A[r, :top + 1]
    if y.max() < h + 0.3:
        return None
    i = np.nonzero(y >= h)[0]
    if len(i) == 0 or i[0] == 0:
        return None
    k = int(i[0]) - 1
    t = (h - y[k]) / (y[k + 1] - y[k])
    s = (a[k + 1] - a[k]) / (y[k + 1] - y[k])
    av = a[k] + t * (a[k + 1] - a[k])
    w0 = (1 - t) * (n2[r, k, 0] - s * n2[r, k, 1]); w1 = t * (n2[r, k + 1, 0] - s * n2[r, k + 1, 1])
    return av, [(k, w0), (k + 1, w1)]


def notch_lin(c, A, Y, n2, Phi, heights, c_lo, c_hi, half=4.0, dq=0.5, clamp=None):
    """rows: notch value(c_q, h) = v(c_q) - 0.5 (v(c_q - 4) + v(c_q + 4)), linearised. -> (vals, G, labels)
    clamp=(lo, hi): the chord ends are clamped into [lo, hi] as in the judges' script (rj_shape.py / j3_shape.py: c -14..+14; at c -14 the left end is
    the point itself, so the value there is half the plan slope toward c -10)."""
    nv, nu = A.shape
    vals, G, labs = [], [], []
    for h in heights:
        pv = {}
        for r in range(nv):
            if c[r] < c_lo - half - 1 or c[r] > c_hi + half + 1:
                continue
            x = back_cross(A, Y, n2, r, h)
            if x is not None:
                pv[r] = x
        if len(pv) < 6:
            continue
        rr = np.array(sorted(pv)); cc = c[rr]; av = np.array([pv[r][0] for r in rr])

        def interp_w(cq):
            if cq < cc[0] or cq > cc[-1]:
                return None
            k = int(np.clip(np.searchsorted(cc, cq) - 1, 0, len(cc) - 2))
            t = (cq - cc[k]) / (cc[k + 1] - cc[k])
            return [(rr[k], 1 - t), (rr[k + 1], t)]
        for cq in np.arange(c_lo, c_hi + 1e-9, dq):
            cl, cr = cq - half, cq + half
            if clamp is not None:
                cl = max(cl, clamp[0])
                if cr > clamp[1]:
                    continue
            ws = [interp_w(cq), interp_w(cl), interp_w(cr)]
            if any(w is None for w in ws):
                continue
            val = 0.0
            row = {}
            for (wlist, f) in zip(ws, (1.0, -0.5, -0.5)):
                for r, t in wlist:
                    val += f * t * pv[r][0]
                    for (j, wj) in pv[r][1]:
                        row[r * nu + j] = row.get(r * nu + j, 0.0) + f * t * wj
            ids = np.array(list(row.keys())); cf = np.array(list(row.values()))
            g = Phi[ids].T @ cf
            vals.append(val); G.append(np.asarray(g).ravel()); labs.append((float(h), float(cq)))
    return np.array(vals), np.array(G), labs


# ------------------------------------------------------------------ far-row top (the crest col 90 is the highest point)
def fartop_lin(c, A, Y, n2, Phi, c0=6.5, c1=13.0, j0=102, j1=190, margin=0.03):
    """rows: Y[r, j] - Y[r, 90] + margin * H * smoothstep((j - 90) / 25) (<= 0 wanted)."""
    nv, nu = A.shape
    vals, G = [], []
    for r in range(nv):
        if not (c0 <= c[r] <= c1):
            continue
        H = Y[r, 90]
        if H < 2.0:
            continue
        for j in range(j0, j1 + 1, 3):
            m = margin * H * D.smoothstep((j - 90.0) / 25.0)
            val = Y[r, j] - Y[r, 90] + m
            g = Phi[r * nu + j].toarray()[0] * n2[r, j, 1] - Phi[r * nu + 90].toarray()[0] * n2[r, 90, 1]
            vals.append(val); G.append(g)
    return np.array(vals), np.array(G)



def field_smooth_ops(c, nu, Phi, rows_c=(-24.0, 15.5), j0=14, j1=206, sc=3, sr=1.0):
    """GtG of the 2nd differences of the displacement field D = Phi theta along the columns (every sc columns) and along c (neighbours
    about sr metres away, divided by the spacing squared): suppresses ripples of the sculpt layer."""
    nv = len(c)
    rows = np.nonzero((c >= rows_c[0]) & (c <= rows_c[1]))[0]
    I, Jx, V = [], [], []
    k = 0
    for r in rows:
        for j in range(j0 + sc, j1 - sc + 1, 2):
            for (jj, w) in ((j - sc, 1.0), (j, -2.0), (j + sc, 1.0)):
                I.append(k); Jx.append(r * nu + jj); V.append(w)
            k += 1
    Lc = sp.csr_matrix((V, (I, Jx)), shape=(k, nv * nu))
    I, Jx, V = [], [], []
    k = 0
    for r in rows:
        # neighbours about sr metres before and after
        rb = int(np.argmin(np.abs(c - (c[r] - sr)))); ra = int(np.argmin(np.abs(c - (c[r] + sr))))
        if rb == r or ra == r:
            continue
        h1, h2 = c[r] - c[rb], c[ra] - c[r]
        wb, wr, wa = 2.0 / (h1 * (h1 + h2)), -2.0 / (h1 * h2), 2.0 / (h2 * (h1 + h2))
        for j in range(j0, j1 + 1, 2):
            for (rr, w) in ((rb, wb), (r, wr), (ra, wa)):
                I.append(k); Jx.append(rr * nu + j); V.append(w)
            k += 1
    Lr = sp.csr_matrix((V, (I, Jx)), shape=(k, nv * nu))
    Qc = Lc @ Phi; Qr = Lr @ Phi
    return (Qc.T @ Qc).toarray(), (Qr.T @ Qr).toarray()


def back_fair_ops(c, A0, Y0, n3, Phi, rows_c=(-20.0, 12.0), j0=18, j1=110, sr=1.2):
    """R4: second differences of the SURFACE (not the displacement) along c over the back and crest (cols j0..j1), neighbours about sr m
    away: residual = L (X0 + Phi theta n3) = r0 + G theta (3 components). Minimising it evens out the vertical ribs and grooves of the
    back (the judges' 'hood with vertical ribs'); the large dome curvature along c is ~10x smaller at this spacing."""
    X0 = D.world_u(c, A0, Y0)
    nv, nu = A0.shape
    rows = np.nonzero((c >= rows_c[0]) & (c <= rows_c[1]))[0]
    R0, I, Jx, V = [], [], [], []
    k = 0
    for r in rows:
        rb = int(np.argmin(np.abs(c - (c[r] - sr)))); ra = int(np.argmin(np.abs(c - (c[r] + sr))))
        if rb == r or ra == r:
            continue
        h1, h2 = c[r] - c[rb], c[ra] - c[r]
        wb, wr, wa = 2.0 / (h1 * (h1 + h2)), -2.0 / (h1 * h2), 2.0 / (h2 * (h1 + h2))
        for j in range(j0, j1 + 1, 2):
            if Y0[r, j] < 1.0:
                continue
            val = wb * X0[rb, j] + wr * X0[r, j] + wa * X0[ra, j]
            for q in range(3):
                for (rr, w) in ((rb, wb), (r, wr), (ra, wa)):
                    I.append(k); Jx.append(rr * nu + j); V.append(w * n3[rr, j, q])
                R0.append(val[q]); k += 1
    L = sp.csr_matrix((V, (I, Jx)), shape=(k, nv * nu))
    G = L @ Phi
    return np.array(R0), G


def d2_rows(nk, K):
    """second difference of the keys along c for every band (the key spacing is ~1 m in the dense part)."""
    Ls = []
    for b in range(K):
        for k in range(1, nk - 1):
            row = np.zeros(K * nk); row[b * nk + k - 1] = 1; row[b * nk + k] = -2; row[b * nk + k + 1] = 1
            Ls.append(row)
    return np.array(Ls)


def main():
    a = sys.argv[1:]
    din, dout = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    iters, notch_t, pin_w, lam2, lam0 = opt("--iters", 4), opt("--notch", 0.8), opt("--pin", 5.0), opt("--lam2", 0.5), opt("--lam0", 0.02)
    w_r6, w_r4, w_notch, w_top = opt("--wr6", 1.0), opt("--wr4", 1.0), opt("--wnotch", 1.0), opt("--wtop", 1.0)
    t6, t4 = opt("--t6", 0.45), opt("--t4", 0.25)
    bound = opt("--bound", 2.5)
    lm, step_lim = opt("--lm", 0.3), opt("--steplim", 0.6)
    w3 = opt("--w3", 0.0)
    lamDc, lamDr = opt("--lamdc", 20.0), opt("--lamdr", 2.0)
    notch_hmax = opt("--notch-hmax", 16)
    tail = opt("--tail", 4.0)
    wfair = opt("--wfair", 0.0)
    d = D.Design.load(din)
    c = D.c_rows()
    kc = SCULPT_KEYS
    nk = len(kc); K = len(D.SCULPT_NAMES)
    t0 = time.time()
    c, A0, Y0, P = D.build_pre_sculpt(d, c)
    nv, nu = A0.shape
    n2 = D.sheet_normals(A0, Y0)
    n3 = n2[..., 0:1] * D.FRAME_T[None, None, :] + n2[..., 1:2] * UPV[None, None, :]
    Phi = basis_matrix(c, Y0, kc)
    free = np.ones(K * nk, bool)
    for b in range(K):
        for k, ck in enumerate(kc):
            if ck in ZERO_KEYS:
                free[b * nk + k] = False
    cam = Cam()
    th = theta_from_design(d, kc) * free
    L2 = d2_rows(nk, K)
    RGc, RGr = field_smooth_ops(c, nu, Phi)
    fr0, fG = back_fair_ops(c, A0, Y0, n3, Phi)
    fGtG = (fG.T @ fG).toarray(); fGtr = fG.T @ fr0
    # reference image data (pre-sculpt shape): the outline must not move
    pins = pin_rows(cam, c, A0, Y0, n3)
    ids_sil = np.nonzero(pins["sil"].ravel())[0]
    G_sil = sp.diags(pins["s1"].ravel()[ids_sil]) @ Phi[ids_sil]
    ids_band = np.nonzero(pins["band"].ravel())[0]
    G_band = sp.diags(pins["s1"].ravel()[ids_band]) @ Phi[ids_band]
    lim_band = (pins["dpx"].ravel()[ids_band] - 3.0) * 0.5
    w2v = pins["w2"].ravel(); ids_in = np.nonzero(w2v > 0.05)[0]
    G_in = sp.diags(np.sqrt(w2v[ids_in]) * pins["s2"].ravel()[ids_in]) @ Phi[ids_in]
    GtG_pin = (G_sil.T @ G_sil).toarray() + (G_in.T @ G_in).toarray()
    thick0 = lip_top_thickness(A0, Y0).ravel()
    ids_lip = np.nonzero(thick0 < 2.5)[0]
    G_lip = Phi[ids_lip]
    print("setup %.1fs  ncoef %d (free %d)  pins: outline %d, band %d, inner %d, thin lip %d" % (
        time.time() - t0, K * nk, free.sum(), len(ids_sil), len(ids_band), len(ids_in), len(ids_lip)), flush=True)
    log = []
    best = None
    for it in range(iters):
        ti = time.time()
        Dm = (Phi @ th).reshape(nv, nu)
        A = A0 + Dm * n2[..., 0]; Y = Y0 + Dm * n2[..., 1]
        bl = bulge_lin(c, A, Y, n3, Phi)
        hts = [1.0, 2.0, 3.0, 4.5, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0]
        nv1, nG1, nl1 = notch_lin(c, A, Y, n2, Phi, [float(h) for h in range(1, notch_hmax + 1)], -10.0, 12.0)
        nv2, nG2, nl2 = notch_lin(c, A, Y, n2, Phi, [1.0, 2.0, 3.0, 4.5, 6.0, 7.0], -34.0, -10.5)
        nv3, nG3, nl3 = notch_lin(c, A, Y, n2, Phi, [3.0, 6.0], -14.0, -10.5, clamp=(-14.0, 14.0))   # the judges' script's clamped chords
        nvl = np.r_[nv1, nv2, nv3]; nG = np.vstack([nG1, nG2] + ([nG3] if len(nv3) else [])); nlab = nl1 + nl2 + nl3
        tv, tG = fartop_lin(c, A, Y, n2, Phi, margin=0.0)
        f3v, f3G = fartop3_rows(c, A, Y, n2, Phi) if w3 > 0 else (np.zeros(0), np.zeros((0, K * nk)))
        rep = {"it": it}
        M = np.zeros((K * nk, K * nk)); bvec = np.zeros(K * nk)

        def add(Gd, rd, w=1.0):
            M[:] += w * (Gd.T @ Gd); bvec[:] += w * (Gd.T @ rd)
        score = 0.0
        for R, wR, tR, tgt in (("R6", w_r6, t6, 0.6), ("R4", w_r4, t4, 0.31)):
            r_, G_, _ = bl[R]
            ar = np.abs(r_)
            p99 = float(np.percentile(ar, 99))
            rep[R] = {"p99": round(p99, 3), "max": round(float(ar.max()), 3), "n_over": int((ar > tgt).sum())}
            score += max(p99 / tgt, 0.8) + 0.3 * max(float(ar.max()) / tgt, 1.0)
            w = wR * (1.0 + tail * D.smoothstep((ar - tR) / 0.2))
            add(np.sqrt(w)[:, None] * G_, -np.sqrt(w) * r_)
        rep["notch_max"] = round(float(nvl.max()), 3) if len(nvl) else None
        rep["notch_worst"] = nlab[int(np.argmax(nvl))] if len(nvl) else None
        score += max(float(nvl.max()) / 1.1, 0.8) if len(nvl) else 0
        act = nvl > notch_t - 0.15
        if act.any():
            add(nG[act], -(nvl[act] - (notch_t - 0.2)), 9.0 * w_notch)
        rep["fartop_max"] = round(float(tv.max()), 3) if len(tv) else None
        acttop = tv > -0.05
        if acttop.any() and w_top > 0:
            add(tG[acttop], -(tv[acttop] + 0.05), 9.0 * w_top)
        rep["fartop3_rms"] = round(float(np.sqrt(np.mean(f3v ** 2))), 4) if len(f3v) else None
        if len(f3v):
            add(f3G, -f3v, w3)
        M += pin_w * GtG_pin; bvec -= pin_w * (GtG_pin @ th)
        o_sil = G_sil @ th; o_in = G_in @ th
        rep["pin_outline_px_max"] = round(float(np.abs(o_sil).max()), 3) if len(o_sil) else 0
        rep["pin_inner_px_max"] = round(float(np.abs(o_in).max()), 3) if len(o_in) else 0
        ob = G_band @ th
        ab = ob > lim_band - 1.0
        rep["band_violations"] = int((ob > lim_band).sum())
        if ab.any():
            Gb = G_band[np.nonzero(ab)[0]].toarray()
            add(Gb, -(ob[ab] - (lim_band[ab] - 1.5)), pin_w)
        dl = G_lip @ th
        al = -dl > 0.6 * thick0[ids_lip] - 0.14
        rep["lip_violations"] = int((-dl > 0.6 * thick0[ids_lip] - 0.08).sum())
        if al.any():
            Gl = G_lip[np.nonzero(al)[0]].toarray()
            add(Gl, -(dl[al] + (0.6 * thick0[ids_lip][al] - 0.16)), 400.0)
        M += lam2 * (L2.T @ L2); bvec -= lam2 * (L2.T @ (L2 @ th))
        M += lamDc * RGc + lamDr * RGr; bvec -= lamDc * (RGc @ th) + lamDr * (RGr @ th)
        if wfair > 0:     # the back surface's second differences along c: residual fr0 + fG theta (theta total)
            M += wfair * fGtG; bvec -= wfair * (fGtr + fGtG @ th)
            rep["fair_rms"] = round(float(np.sqrt(np.mean((fr0 + fG @ th) ** 2))), 4)
        M += lam0 * np.eye(K * nk); bvec -= lam0 * th
        rep["score"] = round(score, 3)
        if best is None or score < best[0]:
            best = (score, th.copy(), it)
        fi = np.nonzero(free)[0]
        dth = np.zeros(K * nk)
        Mf = M[np.ix_(fi, fi)]
        dth[fi] = np.linalg.solve(Mf + lm * np.diag(np.diag(Mf)) + 1e-9 * np.eye(len(fi)), bvec[fi])
        sc_ = min(1.0, step_lim / max(float(np.abs(dth).max()), 1e-9))
        dth *= sc_
        th = np.clip(th + dth, -bound, bound)
        rep["step_max"] = round(float(np.abs(dth).max()), 3); rep["theta_max"] = round(float(np.abs(th).max()), 3)
        rep["sec"] = round(time.time() - ti, 1)
        log.append(rep)
        print(json.dumps(rep), flush=True)
    if "--last" not in a:
        print("best iterate", best[2], "score", round(best[0], 3), flush=True)
        th = best[1]
    set_theta(d, th, kc)
    j = d.to_json()
    j["sculpt_log"] = {"keys": kc, "iters": log, "args": a[2:], "seconds": round(time.time() - t0, 1)}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("saved", dout, round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
