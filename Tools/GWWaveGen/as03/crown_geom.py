# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1：冠の指の形の道具（numpy）。管の掃引（回転の少ない枠・楕円の断面・丸い先・口の開いた先・ふくらむ先）、
根元を面へ沈めて広げる、法線を面の法線へなめらかに移す、主役波の面からの符号付きの高さ、AO と固定の光の見通し（距離の場で近似）。
"""
import math

import numpy as np
from scipy.spatial import cKDTree

UP = np.array([0.0, 1.0, 0.0])
LIGHT = np.array([-0.45, 0.75, -0.5]) / np.linalg.norm([-0.45, 0.75, -0.5])   # 光の来る向き（見本01・02 と同じ）


def nrm(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def rot(v, axis, ang):
    """ロドリゲスの回転（v：(...,3)、axis：(3,)）。"""
    k = nrm(axis)
    v = np.asarray(v, np.float64)
    c, s = math.cos(ang), math.sin(ang)
    return v * c + np.cross(k, v) * s + np.outer(v @ k, k).reshape(v.shape) * (1 - c) if v.ndim > 1 else v * c + np.cross(k, v) * s + k * (k @ v) * (1 - c)


def slerp(a, b, t):
    a, b = nrm(a), nrm(b)
    d = float(np.clip(a @ b, -1, 1))
    om = math.acos(d)
    if om < 1e-6:
        return a
    return (math.sin((1 - t) * om) * a + math.sin(t * om) * b) / math.sin(om)


def angle(a, b):
    return math.degrees(math.acos(float(np.clip(nrm(a) @ nrm(b), -1, 1))))


class Sheet:
    """主役波の面（t*）を細かくした点群と法線。高さ（空気の側が +）と最も近い点。"""

    def __init__(self, X, N, rows=(40, 239), cols=(18, 394), sub=2):
        r0, r1 = rows
        c0, c1 = cols
        rs = np.linspace(r0, r1, (r1 - r0) * sub + 1)
        cs = np.linspace(c0, c1, (c1 - c0) * sub + 1)
        RR, CC = np.meshgrid(rs, cs, indexing="ij")
        self.P = bil(X, RR, CC).reshape(-1, 3)
        self.N = nrm(bil(N, RR, CC).reshape(-1, 3))
        self.rc = np.stack([RR.ravel(), CC.ravel()], -1)
        self.tree = cKDTree(self.P)

    def height(self, Q, k=4):
        Q = np.asarray(Q, np.float64)
        sh = Q.shape[:-1]
        Qf = Q.reshape(-1, 3)
        d, j = self.tree.query(Qf, k=k)
        # 近い 4 点の平面の高さの重み付き平均（細い唇の縁で符号がぶれないように、最も近い点の重みを大きく）
        w = 1.0 / np.maximum(d, 1e-3) ** 2
        hh = ((Qf[:, None, :] - self.P[j]) * self.N[j]).sum(-1)
        h = (hh * w).sum(1) / w.sum(1)
        return h.reshape(sh), d[:, 0].reshape(sh)

    def nearest(self, Q):
        d, j = self.tree.query(np.asarray(Q, np.float64).reshape(-1, 3))
        return self.P[j], self.N[j], self.rc[j], d


def bil(A, r, c):
    R, C = A.shape[:2]
    r = np.asarray(r, np.float64)
    c = np.asarray(c, np.float64)
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    fr = r - r0
    fc = c - c0
    if A.ndim == 3:
        fr = fr[..., None]
        fc = fc[..., None]
    return A[r0, c0] * (1 - fr) * (1 - fc) + A[r0 + 1, c0] * fr * (1 - fc) + A[r0, c0 + 1] * (1 - fr) * fc + A[r0 + 1, c0 + 1] * fr * fc


def resample(P, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, P[:, k]) for k in range(3)], -1), d[-1]


def rmf(P, side_hint):
    """回転の少ない枠（二重の反射）。T 接線、A 横（side_hint に近い）、B = T × A。"""
    n = len(P)
    T = np.gradient(P, axis=0)
    T = nrm(T)
    A = np.zeros_like(P)
    a0 = side_hint - (side_hint @ T[0]) * T[0]
    if np.linalg.norm(a0) < 1e-6:
        a0 = np.cross(T[0], UP)
    A[0] = nrm(a0)
    for i in range(n - 1):
        v1 = P[i + 1] - P[i]
        c1 = v1 @ v1
        if c1 < 1e-14:
            A[i + 1] = A[i]
            continue
        rL = A[i] - (2 / c1) * (v1 @ A[i]) * v1
        tL = T[i] - (2 / c1) * (v1 @ T[i]) * v1
        v2 = T[i + 1] - tL
        c2 = v2 @ v2
        A[i + 1] = rL - (2 / c2) * (v2 @ rL) * v2 if c2 > 1e-14 else rL
        A[i + 1] = nrm(A[i + 1] - (A[i + 1] @ T[i + 1]) * T[i + 1])
    B = np.cross(T, A)
    return T, A, B


def tube(P, rad, nseg, aspect=None, side_hint=None, tip="round", root_sink=None):
    """背骨 P（根元 → 先、n 点）と半径 rad（n）から、輪 nseg 角の管を作る。aspect（n、幅／厚み、面積を保つ楕円）。
    tip：round（半球）、open（口の開いた丸い先：浅いくぼみ）、bulb（先を 1.25 倍にふくらませた丸）。根元は開いたまま（面の下に沈める）。
    戻り値 V（m×3）、F（三角形）、f（根元 0 → 先 1 の道のりの割合）、ring_id。"""
    P = np.asarray(P, np.float64)
    n = len(P)
    rad = np.asarray(rad, np.float64).copy()
    if aspect is None:
        aspect = np.ones(n)
    if side_hint is None:
        side_hint = np.cross(nrm(P[-1] - P[0]), UP)
        if np.linalg.norm(side_hint) < 1e-6:
            side_hint = np.array([1.0, 0, 0])
    L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    f = L / max(L[-1], 1e-9)
    if tip == "bulb":
        rad = rad * (1 + 0.25 * np.exp(-((f - 0.93) / 0.05) ** 2))
    T, A, B = rmf(P, nrm(side_hint))
    th = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    sx = np.sqrt(aspect)[:, None]
    sy = 1.0 / np.sqrt(aspect)[:, None]
    ca, sa = np.cos(th)[None, :], np.sin(th)[None, :]
    V = P[:, None, :] + rad[:, None, None] * (sx[..., None] * ca[..., None] * A[:, None, :] + sy[..., None] * sa[..., None] * B[:, None, :])
    rings = [V]
    fr = [np.repeat(f[:, None], nseg, 1)]
    # 先の閉じ方
    rt = rad[-1]
    te = T[-1]
    pe = P[-1]
    if tip == "open":
        prof = [(0.92, 0.30), (0.72, 0.50), (0.55, 0.52), (0.42, 0.40)]      # (半径の比, 前への出の比)：縁を作ってから内へ
        apex = pe + te * (0.18 * rt)
    else:
        prof = [(math.cos(a), math.sin(a)) for a in np.radians([22, 45, 64, 80])]
        apex = pe + te * rt
    for k, (rr, hh) in enumerate(prof):
        rings.append(pe[None, None, :] + te[None, None, :] * (hh * rt) + rr * rt * (sx[-1:, ..., None] * ca[..., None] * A[-1][None, None, :] + sy[-1:, ..., None] * sa[..., None] * B[-1][None, None, :]))
        fr.append(np.full((1, nseg), 1.0))
    Vr = np.concatenate(rings, 0)
    nr = Vr.shape[0]
    V = np.concatenate([Vr.reshape(-1, 3), apex[None, :]], 0)
    F = []
    idx = np.arange(nr * nseg).reshape(nr, nseg)
    for i in range(nr - 1):
        a = idx[i]
        b = idx[i + 1]
        a1 = np.roll(a, -1)
        b1 = np.roll(b, -1)
        F.append(np.stack([a, b, b1], 1))
        F.append(np.stack([a, b1, a1], 1))
    ap = nr * nseg
    last = idx[-1]
    F.append(np.stack([last, np.full(nseg, ap), np.roll(last, -1)], 1))
    # 根元も丸く閉じる（面の下に沈むが、向きによって口が面の上に出ても穴に見えないように）
    rap = ap + 1
    first = idx[0]
    V = np.concatenate([V, (P[0] - T[0] * rad[0] * 0.6)[None, :]], 0)
    F.append(np.stack([first, np.roll(first, -1), np.full(nseg, rap)], 1))
    F = np.concatenate(F, 0)
    fv = np.concatenate([np.concatenate(fr, 0).ravel(), [1.0, 0.0]])
    ring_id = np.concatenate([np.repeat(np.arange(nr), nseg), [nr, -1]])
    return V, F, fv, ring_id


def vertex_normals(V, F):
    n = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], n)
    return nrm(vn)


def orient_outward(V, F, P_spine):
    """管の三角形の向きを、背骨から外へ向く法線にそろえる（最初の三角形で判定し、全体を反転するだけ）。"""
    vn = vertex_normals(V, F)
    c = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = V[F].mean(1)
    tree = cKDTree(P_spine)
    _, j = tree.query(cen)
    s = np.sign(((cen - P_spine[j]) * c).sum(-1))
    if (s < 0).mean() > 0.5:
        F = F[:, [0, 2, 1]]
    return F


def hand_sdf_mesh(tubes, vox=0.035, k=0.045, pad=0.2):
    """手（掌＋指）の管の背骨と半径から、距離の場のなめらかな和で 1 つの閉じた面を作る（掌と指の股に丸みが出る）。
    掌（kind 0）は平たさを、横へ ±0.35 r ずらした 2 本の鎖（半径 0.75 r）で表す。各管の中は鎖の最小（そのまま）、管どうしは
    指数のなめらかな最小（k）。面は skimage の marching cubes。戻り値 V, F, N（外向き）、各頂点の最も近い管の番号と道のりの割合。"""
    from skimage.measure import marching_cubes
    chains = []          # (A, B, rA, rB, tube_index, fA, fB)
    for ti, t in enumerate(tubes):
        P = t["P"]
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        n2 = max(6, int(L[-1] / 0.06) + 1)
        Pn, _ = resample(P, n2)
        Ln = np.linspace(0, L[-1], n2)
        r = np.interp(Ln, L, t["rad"])
        if t.get("tip") == "bulb":
            fq = Ln / max(Ln[-1], 1e-9)
            r = r * (1 + 0.25 * np.exp(-((fq - 0.93) / 0.05) ** 2))
        f = Ln / max(Ln[-1], 1e-9)
        if t["kind"] == 0 and float(np.mean(t["aspect"])) > 1.05:
            T = nrm(np.gradient(Pn, axis=0))
            side = t["side"] - (T @ t["side"])[:, None] * T
            side = nrm(side)
            for sgn in (-1.0, 1.0):
                Q = Pn + sgn * 0.35 * r[:, None] * side
                chains.append((Q, 0.75 * r, ti, f))
        else:
            chains.append((Pn, r, ti, f))
    allP = np.concatenate([c[0] for c in chains])
    rmax = max(float(c[1].max()) for c in chains)
    lo = allP.min(0) - rmax - pad
    hi = allP.max(0) + rmax + pad
    shape = np.ceil((hi - lo) / vox).astype(int) + 1
    gx = lo[0] + vox * np.arange(shape[0])
    gy = lo[1] + vox * np.arange(shape[1])
    gz = lo[2] + vox * np.arange(shape[2])
    G = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
    acc = np.zeros(len(G))
    best = np.full(len(G), np.inf)
    owner = np.zeros(len(G), np.int32)
    for ci, (Q, r, ti, f) in enumerate(chains):
        A = Q[:-1]
        B = Q[1:]
        rA = r[:-1]
        rB = r[1:]
        dmin = np.full(len(G), np.inf)
        step = 60000
        for s0 in range(0, len(G), step):
            g = G[s0:s0 + step]
            AB = B - A
            l2 = np.maximum((AB * AB).sum(1), 1e-12)
            tt = np.clip(((g[:, None, :] - A[None]) * AB[None]).sum(-1) / l2[None], 0, 1)
            q = A[None] + tt[..., None] * AB[None]
            d = np.linalg.norm(g[:, None, :] - q, axis=-1) - (rA[None] + tt * (rB - rA)[None])
            dmin[s0:s0 + step] = d.min(1)
        acc += np.exp(-np.clip(dmin, -1.0, 2.0) / k)
        upd = dmin < best
        best[upd] = dmin[upd]
        owner[upd] = ti
    sdf = -k * np.log(np.maximum(acc, 1e-300))
    vol = sdf.reshape(shape)
    if vol.min() >= 0 or vol.max() <= 0:
        return None
    verts, faces, normals, _ = marching_cubes(vol, level=0.0, spacing=(vox, vox, vox))
    V = verts + lo
    # 法線は外向き。skimage の marching_cubes の normals は値の減る向き（距離の場では内向き）なので反転する（球で確かめた）。
    # 三角形の巻きは外向き（同じく球で確かめた）
    N = -nrm(normals)
    F = faces.astype(np.int64)
    # 三角形の向きを法線にそろえる
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if ((fn * N[F].mean(1)).sum(1) < 0).mean() > 0.5:
        F = F[:, [0, 2, 1]]
    # 各頂点の持ち主の管と、その管の道のりの割合
    from scipy.spatial import cKDTree as _T
    pts, own, fr = [], [], []
    for (Q, r, ti, f) in chains:
        pts.append(Q)
        own.append(np.full(len(Q), ti))
        fr.append(f)
    tr = _T(np.concatenate(pts))
    _, j = tr.query(V)
    return V, F, N, np.concatenate(own)[j], np.concatenate(fr)[j], [(c[0], c[1]) for c in chains]
