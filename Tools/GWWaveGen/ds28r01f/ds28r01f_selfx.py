# -*- coding: utf-8 -*-
"""設計28修正01 試行F：断面の自己交差（行ごとの 2 次元）と網の局所の自己交差（3 次元）の速い検査器（numpy だけ）。

- section_selfx_rows(A, Y)：Tools/GWWaveGen/gw_wavegen.py の self_intersections と同じ定義（行の断面の折れ線の全列、隣り合わない
  線分どうしの内部の交差）。線分の外接箱の重なりで候補を先に絞るので速い（結果は同じ。_selftest で確かめる）。
- local_selfx(X, win=6)：Tools/GWWaveGen/gw_wavegen_v1.py の local_self_intersections と同じ定義（同じ帯と隣の帯、列の差が win 以内で
  頂点を共有しない三角形どうしの交差。Möller–Trumbore、端を除く）。三角形の外接箱の重なりで候補を先に絞る（結果は同じ）。
  元の関数は 1 コマ 約 13 s、これは 約 0.3〜1 s。
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))


def _seg_tri_hits(P, Q, V0, V1, V2, eps=1e-7):
    d = Q - P
    e1 = V1 - V0
    e2 = V2 - V0
    h = np.cross(d, e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > 1e-14
    f = np.where(ok, 1.0 / np.where(ok, a, 1.0), 0.0)
    sv = P - V0
    u = f * np.einsum("ij,ij->i", sv, h)
    q = np.cross(sv, e1)
    v = f * np.einsum("ij,ij->i", d, q)
    t = f * np.einsum("ij,ij->i", e2, q)
    return ok & (u > eps) & (v > eps) & (u + v < 1 - eps) & (t > eps) & (t < 1 - eps)


def triangles(nu, nv):
    iu, iv = np.meshgrid(np.arange(nu - 1), np.arange(nv - 1))
    a = (iv * nu + iu).ravel()
    b = ((iv + 1) * nu + iu).ravel()
    c = (iv * nu + iu + 1).ravel()
    d = ((iv + 1) * nu + iu + 1).ravel()
    return np.stack([np.stack([a, b, c], -1), np.stack([c, b, d], -1)], 1).reshape(-1, 3).astype(np.int64)


_TRI = {}


def local_selfx(X, win=6, pad=1e-9):
    """戻り値：交差した三角形の頂点の (行, 列) の集合（gw_wavegen_v1.local_self_intersections と同じ）。
    三角形の外接箱を格子の形 (nv−1, nu−1, 2, 3) に置き、組のずれ (dv, dj, s0, s1) ごとに切り出しで重なりを調べてから、残った組だけを
    Möller–Trumbore で調べる。"""
    nv, nu, _ = X.shape
    V = X.reshape(-1, 3)
    if (nu, nv) not in _TRI:
        _TRI[(nu, nv)] = triangles(nu, nv)
    tris = _TRI[(nu, nv)]
    T = V[tris]                                  # (nt, 3, 3)、三角形の番号 = 2·(帯·(nu−1) + 列) + s
    lo = (T.min(1) - pad).reshape(nv - 1, nu - 1, 2, 3)
    hi = (T.max(1) + pad).reshape(nv - 1, nu - 1, 2, 3)
    R, C = nv - 1, nu - 1
    bad = set()
    for dv in (0, 1):
        for dj in range(-win, win + 1):
            for s0 in (0, 1):
                for s1 in (0, 1):
                    if dv == 0 and (dj < 0 or (dj == 0 and s1 <= s0)):
                        continue
                    ra0, ra1 = 0, R - dv
                    ca0, ca1 = max(0, -dj), min(C, C - dj)
                    if ra1 <= ra0 or ca1 <= ca0:
                        continue
                    la = lo[ra0:ra1, ca0:ca1, s0]
                    ha = hi[ra0:ra1, ca0:ca1, s0]
                    lb = lo[ra0 + dv:ra1 + dv, ca0 + dj:ca1 + dj, s1]
                    hb = hi[ra0 + dv:ra1 + dv, ca0 + dj:ca1 + dj, s1]
                    ov = np.all((la <= hb) & (lb <= ha), axis=-1)
                    rr, cc = np.nonzero(ov)
                    if len(rr) == 0:
                        continue
                    rr = rr + ra0
                    cc = cc + ca0
                    ia = 2 * (rr * C + cc) + s0
                    ib = 2 * ((rr + dv) * C + (cc + dj)) + s1
                    A_ = tris[ia]
                    B_ = tris[ib]
                    share = (A_[:, :, None] == B_[:, None, :]).any((1, 2))
                    A_, B_ = A_[~share], B_[~share]
                    if len(A_) == 0:
                        continue
                    hit = np.zeros(len(A_), bool)
                    for (T1, T2) in ((A_, B_), (B_, A_)):
                        for e0, e1 in ((0, 1), (1, 2), (2, 0)):
                            hit |= _seg_tri_hits(V[T1[:, e0]], V[T1[:, e1]], V[T2[:, 0]], V[T2[:, 1]], V[T2[:, 2]])
                    for t in np.concatenate([A_[hit].ravel(), B_[hit].ravel()]):
                        bad.add((int(t // nu), int(t % nu)))
    return bad


def section_hits_row(a, y):
    """1 行の断面の折れ線の、隣り合わない線分どうしの交差の組 [(i, j)]（gw_wavegen.self_intersections の定義）。"""
    P = np.stack([a, y], -1)
    p, q = P[:-1], P[1:]
    lo = np.minimum(p, q)
    hi = np.maximum(p, q)
    n = len(p)
    ii, jj = np.nonzero(np.triu((lo[:, None, 0] <= hi[None, :, 0]) & (lo[None, :, 0] <= hi[:, None, 0])
                               & (lo[:, None, 1] <= hi[None, :, 1]) & (lo[None, :, 1] <= hi[:, None, 1]), 2))
    if not len(ii):
        return []
    d = q - p
    dx, ex = d[ii], d[jj]
    w = p[jj] - p[ii]
    den = dx[:, 0] * ex[:, 1] - dx[:, 1] * ex[:, 0]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (w[:, 0] * ex[:, 1] - w[:, 1] * ex[:, 0]) / den
        t = (w[:, 0] * dx[:, 1] - w[:, 1] * dx[:, 0]) / den
    hit = (np.abs(den) > 1e-12) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
    return list(zip(ii[hit].tolist(), jj[hit].tolist()))


def section_selfx_rows(A, Y):
    """{行: 交差の数}（交差のある行だけ）。"""
    out = {}
    for r in range(A.shape[0]):
        h = section_hits_row(A[r], Y[r])
        if h:
            out[int(r)] = len(h)
    return out


def _selftest(npz_paths):
    sys.path.insert(0, GW)
    import time
    import gw_wavegen as G0
    import gw_wavegen_v1 as V1
    for p in npz_paths:
        z = np.load(p)
        X, A, Y = z["X"], z["A"], z["Y"]
        t0 = time.time()
        b0 = V1.local_self_intersections(X, win=6)
        t1 = time.time()
        b1 = local_selfx(X, win=6)
        t2 = time.time()
        s0 = {r: k for r, k in enumerate(G0.self_intersections(A, Y)) if k > 0}
        t3 = time.time()
        s1 = section_selfx_rows(A, Y)
        t4 = time.time()
        print(os.path.basename(p), "local same", b0 == b1, len(b0), "%.1f s → %.2f s" % (t1 - t0, t2 - t1),
              "| section same", s0 == s1, len(s0), "%.2f s → %.2f s" % (t3 - t2, t4 - t3))


if __name__ == "__main__":
    _selftest(sys.argv[1:])
