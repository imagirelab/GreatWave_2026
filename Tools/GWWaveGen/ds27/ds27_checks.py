# -*- coding: utf-8 -*-
"""設計27：生成器の自前の簡単な検査（正式の関門は別の検査器 ds27_gates.py が行う）。

- 連続性（設計26 P13 (1)(2)）：30 Hz の物理の時刻で、1 コマの変位（波の枠）と二階差分（地面）。
- 網の形（P13 (5)）：唇・管の天井（巻きのある行の頂〜内壁の錨の列）の行の方向の辺の最短、行の方向・行の間の辺の K* に対する比、
  三角形の最小の面積、rim と最初の管の天井の辺の比、面の反転（隣のコマとの面の法線の内積 < 0）、断面の自己交差（行ごとの 2 次元）。
- 法線（P13 (6)）：頂点の法線が有限か（1 環の面積が 0 でないか）。
- 段階の目安（P15 の自前の見積もり）：主断面と峰の行の H/H*、頂の角 θc、前面の最大の角 φ、張り出し Lo（定義 A）。
numpy だけを使う。
"""
import math

import numpy as np

G = 9.81


def tri_normals(X, tris):
    V = X.reshape(-1, 3)
    return np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])


def vertex_normal_ok(X, tris):
    fn = tri_normals(X, tris)
    V = X.reshape(-1, 3)
    n = np.zeros_like(V)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1)
    return int(np.sum(~np.isfinite(ln))), int(np.sum(ln < 1e-12)), float(ln.min())


def section_self_intersections(A, Y, rows, j0, j1):
    """行ごとの断面の折れ線（列 j0〜j1）の、隣り合わない線分どうしの交差の数。戻り値は {行: 数}。"""
    out = {}
    for r in rows:
        P = np.stack([A[r, j0:j1 + 1], Y[r, j0:j1 + 1]], -1)
        p, q = P[:-1], P[1:]
        d = q - p
        lo = np.minimum(p, q)
        hi = np.maximum(p, q)
        ov = (lo[:, None, 0] <= hi[None, :, 0]) & (lo[None, :, 0] <= hi[:, None, 0]) & (lo[:, None, 1] <= hi[None, :, 1]) & (lo[None, :, 1] <= hi[:, None, 1])
        ov = np.triu(ov, 2)
        ii, jj = np.nonzero(ov)
        if not len(ii):
            continue
        dx, ex = d[ii], d[jj]
        w = p[jj] - p[ii]
        den = dx[:, 0] * ex[:, 1] - dx[:, 1] * ex[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (w[:, 0] * ex[:, 1] - w[:, 1] * ex[:, 0]) / den
            t = (w[:, 0] * dx[:, 1] - w[:, 1] * dx[:, 0]) / den
        hit = (np.abs(den) > 1e-14) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
        n = int(hit.sum())
        if n:
            out[int(r)] = n
    return out


class MeshStats:
    """30 Hz のコマを順に渡して、網の形と連続性の最悪値を集める。"""

    def __init__(self, gen, hz=30.0):
        self.g = gen
        K = gen.K
        nv, nu = K.nv, K.nu
        self.hz = hz
        self.tris = K.tris
        # 唇・管の領域（巻きのある行の頂〜内壁の錨）
        M = np.zeros((nv, nu), bool)
        for r in gen.lip:
            M[r, int(gen.root[r]):int(gen.ja[r]) + 1] = True
        self.M = M
        self.rowE = M[:, :-1] & M[:, 1:]                         # 行の方向の辺
        body = gen.has_body
        self.crossE = (M[:-1, :] | M[1:, :]) & body[:-1, None] & body[1:, None]
        XK = K.X
        self.eK_row = np.linalg.norm(np.diff(XK, axis=1), axis=-1)
        self.eK_cross = np.linalg.norm(np.diff(XK, axis=0), axis=-1)
        # 三角形（格子の四角ごとに 2 つ。K* の .gwb の添字と同じ並びとは限らないので、ここでは格子から作る）
        r_, c_ = np.meshgrid(np.arange(nv - 1), np.arange(nu - 1), indexing="ij")
        i00 = r_ * nu + c_
        t1 = np.stack([i00, i00 + nu, i00 + 1], -1).reshape(-1, 3)
        t2 = np.stack([i00 + 1, i00 + nu, i00 + nu + 1], -1).reshape(-1, 3)
        self.gtris = np.concatenate([t1, t2])
        mq = (M[:-1, :-1] | M[1:, :-1] | M[:-1, 1:] | M[1:, 1:]).reshape(-1)
        self.triM = np.concatenate([mq, mq])
        aK = 0.5 * np.linalg.norm(tri_normals(XK, self.gtris), axis=1)
        self.areaK_min_region = float(aK[self.triM].min())
        self.seam = [(int(r), int(gen.lip[r]["rim"])) for r in gen.lip if gen.kappa[r] >= 1.0]
        self.res = dict(step_max_m=0.0, step_at=None, d2_max_m=0.0, d2_at=None, d2_max_lip_rows_m=0.0,
                        row_edge_min_m=np.inf, row_edge_min_at=None, row_stretch_min=np.inf, row_stretch_max=0.0, row_stretch_max_at=None,
                        cross_stretch_min=np.inf, cross_stretch_max=0.0, cross_stretch_max_at=None,
                        cross_stretch_max_all_rows=0.0, cross_stretch_max_all_rows_at=None,
                        tri_area_min_m2=np.inf, tri_area_min_at=None, face_flips=0, face_flips_region=0, face_flip_samples=[],
                        seam_ratio_min=np.inf, seam_ratio_max=0.0, seam_ratio_min_at=None, d2_max_lip_rows_at=None, d2_over_2g_vertices=0, d2_over_2g_frames=0, self_intersections=0, self_intersection_samples=[],
                        normal_nonfinite=0, normal_zero=0, frames=0, nan=0)
        self.Xp = self.Xpp = None
        self.Np = None
        self.kstar_row_edge_min_region = float(self.eK_row[self.rowE].min())

    def add(self, tau, X_local, A, Y, si=True):
        g = self.g
        R = self.res
        R["frames"] += 1
        if not np.all(np.isfinite(X_local)):
            R["nan"] += int((~np.isfinite(X_local)).sum())
        Xg = X_local + g.origin(tau)[None, None, :]
        if self.Xp is not None:
            d = np.linalg.norm(X_local - self.Xp[0], axis=-1)
            m = float(d.max())
            if m > R["step_max_m"]:
                i = np.unravel_index(int(d.argmax()), d.shape)
                R["step_max_m"], R["step_at"] = m, dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]))
            if self.Xpp is not None:
                d2 = np.linalg.norm(Xg - 2 * self.Xp[1] + self.Xpp[1], axis=-1)
                m2 = float(d2.max())
                if m2 > R["d2_max_m"]:
                    i = np.unravel_index(int(d2.argmax()), d2.shape)
                    R["d2_max_m"], R["d2_at"] = m2, dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), c_m=round(float(g.K.c[i[0]]), 2))
                lr = np.array(sorted(g.lip.keys()))
                v = float(d2[lr].max())
                if v > R["d2_max_lip_rows_m"]:
                    i = np.unravel_index(int(d2[lr].argmax()), d2[lr].shape)
                    R["d2_max_lip_rows_m"] = v
                    R["d2_max_lip_rows_at"] = dict(tau=round(tau, 4), row=int(lr[i[0]]), col=int(i[1]), c_m=round(float(g.K.c[lr[i[0]]]), 2))
                big = d2 > 0.0218
                if big.any():
                    R["d2_over_2g_vertices"] = R.get("d2_over_2g_vertices", 0) + int(big.sum())
                    R["d2_over_2g_frames"] = R.get("d2_over_2g_frames", 0) + 1
        self.Xpp, self.Xp = self.Xp, (X_local, Xg)
        # 行の方向の辺
        er = np.linalg.norm(np.diff(X_local, axis=1), axis=-1)
        v = np.where(self.rowE, er, np.inf)
        k = int(v.argmin())
        if v.flat[k] < R["row_edge_min_m"]:
            i = np.unravel_index(k, v.shape)
            R["row_edge_min_m"] = float(v.flat[k])
            R["row_edge_min_at"] = dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), kstar_edge_m=float(self.eK_row[i]))
        st = er / np.maximum(self.eK_row, 1e-9)
        v = np.where(self.rowE, st, np.inf)
        k = int(v.argmin())
        if v.flat[k] < R["row_stretch_min"]:
            i = np.unravel_index(k, v.shape)
            R["row_stretch_min"] = float(v.flat[k])
            R["row_stretch_min_at"] = dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), kstar_edge_m=round(float(self.eK_row[i]), 5))
        v = np.where(self.rowE, st, 0.0)
        k = int(v.argmax())
        if v.flat[k] > R["row_stretch_max"]:
            i = np.unravel_index(k, v.shape)
            R["row_stretch_max"], R["row_stretch_max_at"] = float(v.flat[k]), dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]))
        ec = np.linalg.norm(np.diff(X_local, axis=0), axis=-1)
        sc = ec / np.maximum(self.eK_cross, 1e-9)
        v = np.where(self.crossE, sc, np.inf)
        k = int(v.argmin())
        if v.flat[k] < R["cross_stretch_min"]:
            i = np.unravel_index(k, v.shape)
            R["cross_stretch_min"] = float(v.flat[k])
            R["cross_stretch_min_at"] = dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), c_m=round(float(g.K.c[i[0]]), 2), kstar_edge_m=round(float(self.eK_cross[i]), 4))
        # 噴流の区間（τ ≥ −2.7 s。設計26 E4b の窓）だけの最悪値
        if tau >= -2.7 - 1e-9:
            J = R.setdefault("jet_window", dict(tau_from=-2.7, cross_stretch_max=0.0, cross_stretch_min=np.inf, row_stretch_max=0.0, row_stretch_min=np.inf, row_edge_min_m=np.inf))
            J["cross_stretch_max"] = max(J["cross_stretch_max"], float(sc[self.crossE].max()))
            J["cross_stretch_min"] = min(J["cross_stretch_min"], float(sc[self.crossE].min()))
            stj = er / np.maximum(self.eK_row, 1e-9)
            J["row_stretch_max"] = max(J["row_stretch_max"], float(stj[self.rowE].max()))
            J["row_stretch_min"] = min(J["row_stretch_min"], float(stj[self.rowE].min()))
            J["row_edge_min_m"] = min(J["row_edge_min_m"], float(er[self.rowE].min()))
            big = self.crossE & (sc > 4.0)
            if big.any():
                J["cross_stretch_over4_vertices"] = J.get("cross_stretch_over4_vertices", 0) + int(big.sum())
                rr = np.nonzero(big)[0]
                J["cross_stretch_over4_c_range"] = [min(J.get("cross_stretch_over4_c_range", [9e9, -9e9])[0], float(g.K.c[rr.min()])),
                                                    max(J.get("cross_stretch_over4_c_range", [9e9, -9e9])[1], float(g.K.c[rr.max() + 1]))]
        v = np.where(self.crossE, sc, 0.0)
        k = int(v.argmax())
        if v.flat[k] > R["cross_stretch_max"]:
            i = np.unravel_index(k, v.shape)
            R["cross_stretch_max"], R["cross_stretch_max_at"] = float(v.flat[k]), dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), c_m=round(float(g.K.c[i[0]]), 2))
        k = int(sc.argmax())
        if sc.flat[k] > R["cross_stretch_max_all_rows"]:
            i = np.unravel_index(k, sc.shape)
            R["cross_stretch_max_all_rows"], R["cross_stretch_max_all_rows_at"] = float(sc.flat[k]), dict(tau=round(tau, 4), row=int(i[0]), col=int(i[1]), c_m=round(float(g.K.c[i[0]]), 2))
        # rim と最初の管の天井の辺（K* に対する比）
        if self.seam:
            rr = np.array([s[0] for s in self.seam])
            jj = np.array([s[1] for s in self.seam])
            ratio = er[rr, jj] / np.maximum(self.eK_row[rr, jj], 1e-9)
            if float(ratio.min()) < R["seam_ratio_min"]:
                k = int(ratio.argmin())
                R["seam_ratio_min_at"] = dict(tau=round(tau, 4), row=int(rr[k]), col=int(jj[k]))
            R["seam_ratio_min"] = min(R["seam_ratio_min"], float(ratio.min()))
            R["seam_ratio_max"] = max(R["seam_ratio_max"], float(ratio.max()))
        # 三角形と面の反転
        fn = tri_normals(X_local, self.gtris)
        ar = 0.5 * np.linalg.norm(fn, axis=1)
        v = np.where(self.triM, ar, np.inf)
        k = int(v.argmin())
        if v[k] < R["tri_area_min_m2"]:
            q = k % (len(ar) // 2)
            R["tri_area_min_m2"], R["tri_area_min_at"] = float(v[k]), dict(tau=round(tau, 4), row=int(q // (g.K.nu - 1)), col=int(q % (g.K.nu - 1)))
        if self.Np is not None:
            both = (ar > 1e-12) & (np.linalg.norm(self.Np, axis=1) > 1e-12)
            flip = both & ((fn * self.Np).sum(1) < 0)
            nf = int(flip.sum())
            if nf:
                R["face_flips"] += nf
                R["face_flips_region"] += int((flip & self.triM).sum())
                if len(R["face_flip_samples"]) < 10:
                    q = int(np.nonzero(flip)[0][0]) % (len(ar) // 2)
                    R["face_flip_samples"].append(dict(tau=round(tau, 4), n=nf, row=int(q // (g.K.nu - 1)), col=int(q % (g.K.nu - 1))))
        self.Np = fn
        if si:
            rows = [r for r in range(g.K.nv) if g.has_body[r] and g.w_cplx[r] > 0]
            hits = section_self_intersections(A, Y, rows, g.jB, g.jE)
            if hits:
                R["self_intersections"] += int(sum(hits.values()))
                if len(R["self_intersection_samples"]) < 12:
                    r0 = min(hits)
                    R["self_intersection_samples"].append(dict(tau=round(tau, 4), rows=len(hits), first_row=r0, c_m=round(float(g.K.c[r0]), 2), n=int(sum(hits.values()))))

    def normals_check(self, X_local):
        a, b, m = vertex_normal_ok(X_local, self.tris)
        self.res["normal_nonfinite"] += a
        self.res["normal_zero"] += b

    def result(self):
        R = dict(self.res)
        R["kstar_row_edge_min_region_m"] = self.kstar_row_edge_min_region
        R["kstar_tri_area_min_region_m2"] = self.areaK_min_region
        for k, v in list(R.items()):
            if isinstance(v, float) and not math.isfinite(v):
                R[k] = None
        if "jet_window" in R:
            R["jet_window"] = {k: (None if isinstance(v, float) and not math.isfinite(v) else v) for k, v in R["jet_window"].items()}
        return R


# ---------------------------------------------------------------- 段階の目安（自前）
def stage_metrics(A, Y, r, jE=394, crest_hi=None):
    """行 r の断面の、頂の高さ、頂の角 θc（頂から 0.1H 下の前後の点への弦）、前面の最大の角 φ（0.15〜0.97H、90° で鉛直）、
    頂の下 0.1〜0.2H の前面の最大の角、張り出し Lo（0.3H の内壁から 0.3H より上の前の部分の a の最大まで）。"""
    a, y = A[r], Y[r]
    hi = len(a) - 1 if crest_hi is None else crest_hi
    cj = int(np.argmax(y[:hi + 1]))
    H = float(y[cj])
    if H <= 0.1:
        return dict(H=H)
    # 背面の 0.1H 下の点
    yb = y[:cj + 1]
    kb = np.where(yb <= 0.9 * H)[0]
    if len(kb):
        k = kb[-1]
        f = (0.9 * H - y[k]) / (y[k + 1] - y[k] + 1e-12)
        pb = np.array([a[k] + f * (a[k + 1] - a[k]), 0.9 * H])
    else:
        pb = np.array([a[0], y[0]])
    yf = y[cj:jE + 1]
    kf = np.where(yf <= 0.9 * H)[0]
    if len(kf):
        k = cj + kf[0]
        f = (0.9 * H - y[k - 1]) / (y[k] - y[k - 1] + 1e-12)
        pf = np.array([a[k - 1] + f * (a[k] - a[k - 1]), 0.9 * H])
    else:
        pf = np.array([a[jE], y[jE]])
    top = np.array([a[cj], H])
    v1, v2 = pb - top, pf - top
    thc = math.degrees(math.acos(np.clip(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-12), -1, 1)))
    da, dy = np.diff(a[cj:jE + 1]), np.diff(y[cj:jE + 1])
    ym = 0.5 * (y[cj:jE] + y[cj + 1:jE + 1])
    ang = np.degrees(np.arctan2(-dy, da))                     # 下り 0〜180（90 で鉛直、>90 張り出し）
    L = np.hypot(da, dy)
    band = (ym > 0.15 * H) & (ym < 0.97 * H) & (dy < 0) & (L > 1e-6)
    phi = float(ang[band].max()) if band.any() else 0.0
    bb = (ym > 0.8 * H) & (ym < 0.9 * H) & (dy < 0) & (L > 1e-6)
    phib = float(ang[bb].max()) if bb.any() else 0.0
    # 張り出し：前の部分で 0.3H を最後に下へ横切る点 → 0.3H より上の前の部分の a の最大
    yy = y[cj:jE + 1]
    aa = a[cj:jE + 1]
    cr = np.where((yy[:-1] >= 0.3 * H) & (yy[1:] < 0.3 * H))[0]
    if len(cr):
        k = cr[-1]
        f = (yy[k] - 0.3 * H) / (yy[k] - yy[k + 1] + 1e-12)
        a03 = aa[k] + f * (aa[k + 1] - aa[k])
        amax = float(aa[:k + 1][yy[:k + 1] >= 0.3 * H].max())
        Lo = max(amax - a03, 0.0)
    else:
        Lo = 0.0
    return dict(H=H, crest_a=float(a[cj]), theta_c=thc, phi=phi, phi_band=phib, Lo_over_H=Lo / H)
