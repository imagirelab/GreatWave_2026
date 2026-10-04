# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S：粘土の下見の描画（numpy の z バッファ。Unity の描画ではない）。三角形ごとの色に、向きの陰（両面）と輪郭の線を付ける。"""
import cv2
import numpy as np

import s4_common as S

LIGHT = np.array([0.35, 0.85, -0.40])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def render(cam, tris, rgb, bg=(236, 236, 232), line=(40, 40, 50)):
    """tris (N,3,3) ワールド、rgb (N,3) 0..255。戻り値 RGB の画像と id。"""
    ids = np.arange(1, len(tris) + 1)
    idb, zb = S.U.raster(cam, tris, ids)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    lam = 0.42 + 0.58 * np.abs(n @ LIGHT)
    img = np.zeros((cam.H, cam.W, 3), np.float64)
    img[:] = np.array(bg, np.float64)
    m = idb > 0
    t = idb[m] - 1
    img[m] = np.asarray(rgb, np.float64)[t] * lam[t, None]
    # 輪郭：空との境と深さの段差
    sky = ~m
    e = np.zeros_like(sky)
    e[:, 1:] |= sky[:, 1:] != sky[:, :-1]
    e[1:, :] |= sky[1:, :] != sky[:-1, :]
    z = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 0)
    for dy, dx in ((0, 1), (1, 0)):
        a = z[: cam.H - dy, : cam.W - dx]; b = z[dy:, dx:]
        j = (a > 0) & (b > 0) & (np.abs(a - b) > 0.03 * np.minimum(a, b) + 0.4)
        e[: cam.H - dy, : cam.W - dx] |= j
    e = cv2.dilate(e.astype(np.uint8), np.ones((2, 2), np.uint8)) > 0
    img[e] = np.array(line, np.float64)
    return np.clip(img, 0, 255).astype(np.uint8), idb


def hero_tris(hero):
    return hero.V[hero.Tg]


def tri_vertex_rc(hero):
    """各三角形の 3 頂点の (行, 列)。"""
    T = hero.Tg
    r, c = np.divmod(T, hero.C)
    return r, c
