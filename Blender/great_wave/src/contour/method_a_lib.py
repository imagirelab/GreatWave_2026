"""領域に基づく方法Aの基準輪郭向け補助機能。numpy のみで画像の形態演算、
連結成分、画素間の境界追跡、折れ線処理を行う。

マスクは上から下へ並ぶ bool 配列。点は gw.frame の連続画素座標を使う。
画素 (i, j) は [i, i+1] x [j, j+1] を覆い、`trace_cracks` が追跡する
境界はその整数座標の画素角の格子上にある。

scipy / cv2 は使わない。ユークリッド距離変換は上限付きの正確な EDT で、
行方向の1D距離と上下 cap 行の最小加算処理を組み合わせる。
半径が約100 px 以下の場合に適する。
"""
import math

import numpy as np


# ------------------------------------------------------------------ 距離と形態演算
def edt_capped(mask, cap, pad_mode="edge"):
    """各 True 画素の中心から最も近い False 画素の中心までの正確なユークリッド距離。

    cap を超える値は cap + 1、False 画素は 0 を返す。pad_mode='edge' では
    画像の端を複製し、枠に接する領域が枠外にも続くものとして扱う。
    """
    m = np.asarray(mask, dtype=bool)
    cap = int(cap)
    big = cap + 1
    p = cap + 2
    mp = np.pad(m, p, mode=pad_mode) if pad_mode == "edge" else np.pad(m, p, mode="constant", constant_values=False)
    h, w = mp.shape
    idx = np.arange(w, dtype=np.int32)[None, :]
    far = np.int32(10 ** 7)
    left = np.where(mp, -far, idx)
    np.maximum.accumulate(left, axis=1, out=left)
    right = np.where(mp, far, idx)
    right = np.minimum.accumulate(right[:, ::-1], axis=1)[:, ::-1]
    g = np.minimum(idx - left, right - idx)
    np.minimum(g, big, out=g)
    g2 = (g.astype(np.float32)) ** 2
    d2 = g2.copy()
    lim = float(big * big)
    for dy in range(1, big + 1):
        c = float(dy * dy)
        if c >= lim:
            break
        np.minimum(d2[dy:], g2[:-dy] + c, out=d2[dy:])
        np.minimum(d2[:-dy], g2[dy:] + c, out=d2[:-dy])
    np.minimum(d2, lim, out=d2)
    d = np.sqrt(d2)
    return d[p:-p, p:-p]


def erode_disc(mask, r):
    """半径 r の円盤で収縮する（背景までの距離が r より大きい画素を残す）。"""
    if r <= 0:
        return np.asarray(mask, dtype=bool).copy()
    return edt_capped(mask, int(math.ceil(r)) + 1) > r


def dilate_disc(mask, r):
    """半径 r の円盤で膨張する（マスクからの距離が r 以下の画素を含める）。"""
    if r <= 0:
        return np.asarray(mask, dtype=bool).copy()
    return ~(edt_capped(~np.asarray(mask, dtype=bool), int(math.ceil(r)) + 1) > r)


def open_disc(mask, r):
    return dilate_disc(erode_disc(mask, r), r)


def close_disc(mask, r):
    return erode_disc(dilate_disc(mask, r), r)


# ------------------------------------------------------------------ 連結成分
def label_components(mask):
    """真偽マスクの4近傍連結成分を求める。

    ラベル配列 int32（0 は背景）と成分数を返す。各行の連続区間を節点、上下の重なりを
    辺とするグラフを作り、最小ラベルの結合とポインタジャンピングで成分を求める。
    """
    m = np.asarray(mask, dtype=bool)
    h, w = m.shape
    start = m.copy()
    start[:, 1:] &= ~m[:, :-1]
    rid = np.cumsum(start.ravel(), dtype=np.int64).reshape(h, w)
    rid[~m] = 0
    n = int(rid.max())
    if n == 0:
        return np.zeros((h, w), np.int32), 0
    sel = m[:-1] & m[1:] & (start[:-1] | start[1:])
    a = rid[:-1][sel]
    b = rid[1:][sel]
    parent = np.arange(n + 1, dtype=np.int64)
    for _ in range(10000):
        pa = parent[a]
        pb = parent[b]
        diff = pa != pb
        if not diff.any():
            break
        pa, pb = pa[diff], pb[diff]
        mn = np.minimum(pa, pb)
        np.minimum.at(parent, pa, mn)
        np.minimum.at(parent, pb, mn)
        while True:
            pp = parent[parent]
            if np.array_equal(pp, parent):
                break
            parent = pp
    roots, inv = np.unique(parent, return_inverse=True)
    # 根の 0 は背景（rid 0 -> parent 0）。
    lab_of_run = inv.astype(np.int32)
    if roots[0] != 0:
        lab_of_run = lab_of_run + 1
    labels = lab_of_run[rid]
    return labels, int(labels.max())


def components_touching(mask, seeds_xy):
    """種画素 (x, y) を含む `mask` の4近傍連結成分の和を返す。

    False 画素上にある種は二つ目の返却値に記録する。
    """
    labels, _ = label_components(mask)
    keep, missed = set(), []
    for (x, y) in seeds_xy:
        l = int(labels[int(y), int(x)])
        if l == 0:
            missed.append((int(x), int(y)))
        else:
            keep.add(l)
    if not keep:
        return np.zeros_like(mask, dtype=bool), missed
    lut = np.zeros(int(labels.max()) + 1, bool)
    lut[list(keep)] = True
    return lut[labels], missed


def box_mean(a, k):
    """二次元浮動小数点配列 a を (2k+1) x (2k+1) の窓で平均する。端は複製する。"""
    a = np.asarray(a, dtype=np.float32)
    if k <= 0:
        return a.copy()
    n = 2 * k + 1
    p = np.pad(a, k, mode="edge").astype(np.float64)
    c = np.cumsum(p, axis=0)
    c = np.concatenate([np.zeros((1, c.shape[1])), c], axis=0)
    r = c[n:] - c[:-n]
    c = np.cumsum(r, axis=1)
    c = np.concatenate([np.zeros((c.shape[0], 1)), c], axis=1)
    r = c[:, n:] - c[:, :-n]
    return (r / float(n * n)).astype(np.float32)


# ------------------------------------------------------------------ 境界の追跡
_DIRS = ((1, 0), (0, 1), (-1, 0), (0, -1))     # 画像座標（y は下向き）で東、南、西、北。+1 は右折。


def _pix(mask, x, y, outside):
    h, w = mask.shape
    if x < 0 or y < 0 or x >= w or y >= h:
        return outside(x, y)
    return bool(mask[y, x])


def trace_cracks(mask, start_vertex, start_dir, stop_fn, max_steps=2000000, outside=None):
    """本体を右、背景を左に置きながら `mask` の画素間境界を追跡する。

    画像座標は y が下向きで、本体は8近傍連結とする。start_vertex は整数の角座標
    (x, y)、start_dir は東・南・西・北の番号。stop_fn(x, y, n) が True を返すと
    停止する。outside(x, y) は配列外のマスク値（既定値 False）を与える。
    角頂点の整数配列 (N, 2) を返す。
    """
    if outside is None:
        outside = lambda x, y: False
    x, y = int(start_vertex[0]), int(start_vertex[1])
    d = int(start_dir)
    pts = [(x, y)]
    for n in range(max_steps):
        dx, dy = _DIRS[d]
        # 頂点の前にある画素を、進行方向から見た左前と右前に分ける。
        if d == 0:      # 東: 左前は北側 y-1、右前は南側 y の画素。
            fl, fr = (x, y - 1), (x, y)
        elif d == 1:    # 南: 左は東。
            fl, fr = (x, y), (x - 1, y)
        elif d == 2:    # 西: 左は南。
            fl, fr = (x - 1, y), (x - 1, y - 1)
        else:           # 北: 左は西。
            fl, fr = (x - 1, y - 1), (x, y - 1)
        bl = _pix(mask, fl[0], fl[1], outside)
        br = _pix(mask, fr[0], fr[1], outside)
        if bl:
            d = (d + 3) % 4          # 左折。
        elif br:
            pass                      # 直進。
        else:
            d = (d + 1) % 4          # 右折。
        dx, dy = _DIRS[d]
        x, y = x + dx, y + dy
        pts.append((x, y))
        if stop_fn(x, y, n):
            break
    return np.array(pts, dtype=np.int64)


# ------------------------------------------------------------------ 折れ線
def arclength(pts):
    p = np.asarray(pts, dtype=np.float64)
    seg = np.hypot(np.diff(p[:, 0]), np.diff(p[:, 1]))
    return np.concatenate([[0.0], np.cumsum(seg)])


def resample(pts, spacing, s=None, return_s=False):
    """弧長を等間隔で再標本化する（線形補間）。

    両端点を必ず保持し、標本の間隔が正確に等しくなるよう少し調整する。
    """
    p = np.asarray(pts, dtype=np.float64)
    s = arclength(p) if s is None else s
    total = s[-1]
    n = max(1, int(round(total / spacing)))
    t = np.linspace(0.0, total, n + 1)
    out = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    return (out, t) if return_s else out


def interp_at(pts, s, t):
    p = np.asarray(pts, dtype=np.float64)
    return np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)


def gaussian_smooth(values, sigma, step=1.0):
    """等間隔 `step` の系列 (N, k) または (N,) をガウス平滑化する。

    端点で点対称に反射して系列を延長するため、端点の位置と接線を保ち、端が縮まない。
    """
    v = np.asarray(values, dtype=np.float64)
    one_d = v.ndim == 1
    if one_d:
        v = v[:, None]
    if sigma <= 0:
        return v[:, 0].copy() if one_d else v.copy()
    sg = sigma / float(step)
    r = int(math.ceil(4.0 * sg))
    r = min(r, len(v) - 1)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sg) ** 2)
    k /= k.sum()
    head = 2.0 * v[0] - v[1:r + 1][::-1]
    tail = 2.0 * v[-1] - v[-r - 1:-1][::-1]
    ext = np.concatenate([head, v, tail], axis=0)
    out = np.stack([np.convolve(ext[:, c], k, mode="valid") for c in range(v.shape[1])], axis=1)
    return out[:, 0] if one_d else out


def tangent_angles(pts):
    """画素座標で与えた折れ線の各点について、中心差分による接線方向を度数で返す。

    gw.frame の規約に従い、0 は右向きの +X、+90 は上向き。
    """
    p = np.asarray(pts, dtype=np.float64)
    d = np.gradient(p, axis=0)
    return np.degrees(np.arctan2(-d[:, 1], d[:, 0]))


def angle_diff_deg(a, b):
    """角度 a - b の最小符号付き差を度数で返す。"""
    return (np.asarray(a) - np.asarray(b) + 180.0) % 360.0 - 180.0


def point_to_polyline_dist(q, pts):
    """各照会点 (M, 2) から折れ線 pts (N, 2) の線分までの正確な距離を返す。

    分割して計算し、計算量は O(M * N)。
    """
    q = np.atleast_2d(np.asarray(q, dtype=np.float64))
    p = np.asarray(pts, dtype=np.float64)
    a, b = p[:-1], p[1:]
    ab = b - a
    l2 = np.maximum((ab ** 2).sum(1), 1e-12)
    out = np.empty(len(q))
    step = max(1, int(4000000 // max(1, len(a))))
    for i in range(0, len(q), step):
        qq = q[i:i + step]
        t = ((qq[:, None, :] - a[None]) * ab[None]).sum(2) / l2[None]
        t = np.clip(t, 0.0, 1.0)
        c = a[None] + t[:, :, None] * ab[None]
        out[i:i + step] = np.sqrt(((qq[:, None, :] - c) ** 2).sum(2)).min(1)
    return out
