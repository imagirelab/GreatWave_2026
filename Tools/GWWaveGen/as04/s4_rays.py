# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S：画素の射線と三角形メッシュのすべての交点（奥行きの層）を求める道具。
三角形を画面のタイルへ振り分け、画素ごとにそのタイルの三角形だけを当てる（射線ごとの総当たりを避ける）。"""
import numpy as np


def ray_tri(o, d, A, B, Cc):
    e1, e2 = B - A, Cc - A
    p = np.cross(d, e2)
    det = (e1 * p).sum(-1)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = o[None, :] - A
    u = (tv * p).sum(-1) * inv
    q = np.cross(tv, e1)
    v = (d * q).sum(-1) * inv
    s = (e2 * q).sum(-1) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (s > 1e-6)
    return hit, s, u, v


class TileHits:
    """cam（project・ray・pos・W・H を持つ）から見た三角形（V：n×3、F：m×3）を tile 画素ごとに振り分ける。"""

    def __init__(self, cam, V, F, tile=16):
        self.cam, self.V, self.F, self.tile = cam, np.asarray(V, np.float64), np.asarray(F, np.int64), tile
        xy, z = cam.project(self.V)
        tx = xy[self.F][..., 0]; ty = xy[self.F][..., 1]; tz = z[self.F]
        front = (tz > 0.1).all(1)
        x0 = np.floor(tx.min(1) / tile).astype(np.int64); x1 = np.floor(tx.max(1) / tile).astype(np.int64)
        y0 = np.floor(ty.min(1) / tile).astype(np.int64); y1 = np.floor(ty.max(1) / tile).astype(np.int64)
        nx, ny = cam.W // tile + 1, cam.H // tile + 1
        inb = front & (x1 >= 0) & (x0 < nx) & (y1 >= 0) & (y0 < ny)
        idx = np.nonzero(inb)[0]
        x0, x1, y0, y1 = [np.clip(a[idx], 0, n - 1) for a, n in ((x0, nx), (x1, nx), (y0, ny), (y1, ny))]
        span = (x1 - x0 + 1) * (y1 - y0 + 1)
        self.buckets = {}
        small = span == 1
        keys = y0[small] * nx + x0[small]
        o = np.argsort(keys, kind="stable")
        ks, ts = keys[o], idx[small][o]
        cut = np.nonzero(np.diff(ks))[0] + 1
        for kk, tt in zip(np.split(ks, cut), np.split(ts, cut)):
            if len(kk):
                self.buckets[int(kk[0])] = [tt]
        for t, a, b, c_, d_ in zip(idx[~small], x0[~small], x1[~small], y0[~small], y1[~small]):
            if (b - a + 1) * (d_ - c_ + 1) > 4000:
                continue
            for yy in range(c_, d_ + 1):
                for xx in range(a, b + 1):
                    self.buckets.setdefault(int(yy * nx + xx), []).append(np.array([t]))
        self.nx = nx

    def hits(self, x, y):
        """表示の画素 (x, y) の射線のすべての交点：[(s, 三角形の番号, u, v)]（近い順）。"""
        k = int(np.floor(y / self.tile)) * self.nx + int(np.floor(x / self.tile))
        b = self.buckets.get(k)
        if not b:
            return []
        t = np.unique(np.concatenate(b))
        d = self.cam.ray(np.array([x], float), np.array([y], float))[0]
        Vt = self.V[self.F[t]]
        hit, s, u, v = ray_tri(self.cam.pos, d, Vt[:, 0], Vt[:, 1], Vt[:, 2])
        if not hit.any():
            return []
        o = np.argsort(s[hit])
        return list(zip(s[hit][o], t[hit][o], u[hit][o], v[hit][o]))


def merge_layers(h, tol=0.05):
    """同じ面の継ぎ目で二重に数えた交点（距離の差 tol 以下）を一つにする。"""
    out = []
    for e in h:
        if out and abs(e[0] - out[-1][0]) < tol:
            continue
        out.append(e)
    return out
