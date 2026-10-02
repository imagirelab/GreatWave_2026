# -*- coding: utf-8 -*-
"""仕上げ33：爪の道具の共通部（t* の主役波の z バッファと、原画のカメラからの隠れ・見えの判定）。numpy。

z バッファは記録・検査のためだけに使い、色は作らない（Q28：原画カメラからの投影の色は使わない）。爪の形を原画視点で原画の輪郭の内に保つ・隠すための検査。
"""
import json
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

B = REPO + "/Unity/Build/Polish"
HERO = B + "/32/white/hero_pkg"
WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
ZONE = B + "/32/white/pl31_zone_vertex.npy"


class TStarDepth:
    """t*（τ = 0）の主役波（本体の列 U.BODY）の、原画のカメラ（PaintingCam v1、1920×1080）からの z バッファ。"""

    def __init__(self, X0):
        spec = json.load(open(U.TRUTH, encoding="utf-8"))
        self.cam = U.CamWH(spec, 1920, 1080)
        R, C = X0.shape[:2]
        b0, b1 = U.BODY
        Tg = U.K.grid_tris(R, C, b0, b1)
        V = X0.reshape(-1, 3)
        self.idb, self.zb = U.raster(self.cam, V[Tg], np.arange(1, len(Tg) + 1))
        self.znear = cv2.dilate(self.zb.astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.float64)
        self.zfar = cv2.erode(self.zb.astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.float64)
        self.mask = self.zb > 0

    def look(self, Q):
        xy, z = self.cam.project(Q)
        xi = np.round(xy[..., 0]).astype(int)
        yi = np.round(xy[..., 1]).astype(int)
        inb = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080)
        xi = np.clip(xi, 0, 1919)
        yi = np.clip(yi, 0, 1079)
        return xy, z, xi, yi, inb

    def hidden(self, Q, margin):
        """面より margin 以上奥で、5×5 がどれも主役波の画素（原画視点で見えない）。"""
        xy, z, xi, yi, inb = self.look(Q)
        zs = np.where(self.znear[yi, xi] > 0, 1.0 / np.maximum(self.znear[yi, xi], 1e-9), np.inf)
        return inb & (self.zfar[yi, xi] > 0) & (z > zs + margin)

    def visible(self, Q, tol):
        xy, z, xi, yi, inb = self.look(Q)
        zs = np.where(self.zb[yi, xi] > 0, 1.0 / np.maximum(self.zb[yi, xi], 1e-9), np.inf)
        return inb & (z <= zs + tol)

    def inside(self, Q):
        """原画視点で主役波の中（5×5 がどれも主役波の画素）。"""
        xy, z, xi, yi, inb = self.look(Q)
        return inb & (self.zfar[yi, xi] > 0)


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


RING = 8


def layout_tris(n_st, base):
    """設計33（pl32f_claw_anim.layout_tris）と同じ三角形の並びと面の種類（0 上面 白、1 縁の側面と下面、2 根元の円）。"""
    root = base
    ring = lambda j, i: base + 1 + j * RING + (i % RING)  # noqa: E731
    tip = base + 1 + n_st * RING
    skc = tip + 1
    sk = lambda i: skc + 1 + (i % RING)  # noqa: E731
    T, kind = [], []
    up = lambda i: 0 if (i % RING) in (1, 2) else 1  # noqa: E731
    for i in range(RING):
        T.append((root, ring(0, i + 1), ring(0, i))); kind.append(1)
    for j in range(n_st - 1):
        for i in range(RING):
            T.append((ring(j, i), ring(j, i + 1), ring(j + 1, i + 1))); kind.append(up(i))
            T.append((ring(j, i), ring(j + 1, i + 1), ring(j + 1, i))); kind.append(up(i))
    for i in range(RING):
        T.append((ring(n_st - 1, i), ring(n_st - 1, i + 1), tip)); kind.append(up(i))
    for i in range(RING):
        T.append((skc, sk(i), sk(i + 1))); kind.append(2)
    return np.array(T, np.int64), np.array(kind, np.int64)


def sha(p):
    import hashlib
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()
