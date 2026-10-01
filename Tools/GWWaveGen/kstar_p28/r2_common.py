# -*- coding: utf-8 -*-
"""仕上げ28 第2回（r2：波の断面の読み直し「管を前へ・背を波の背に」）の共通部。py -3.10（numpy・scipy・cv2・PIL）。

第1回の3案（RAYS・FACE-SWAP・BACK-FIRST）はどれも、各行の断面（背が管を大きく包む「頭巾」）を保ったまま頂の線や背の足を
動かしたので、後ろから見たドームは変わらなかった。第2回は、原画視点で見えない所（背・管の奥・唇の上）を、原画の空を通る
射線に触れない範囲（行ごとの「空の射線の禁止域」）で作り直す。原画の輪郭を作る点（78・130・131 の頂の列、132 の唇、72 の唇先と
面の縁）は動かさない。座標は kh_common と同じ（a = 進行方向 T、y = 高さ、c = 波峰線 E）。参照モデルは読まない（F13-1）。
"""
import os
import sys
import json
import math

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KH = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h")
for p in (KH, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import kh_common as KC  # noqa: E402

OUT = os.path.join(REPO, "Unity", "Build", "Polish", "28", "r2")
BASE_ROWS = os.path.join(REPO, "Unity", "Build", "Polish", "28", "r1_rays", "cand", "kstarP28R1_a45_rows.npz")
BASE_SHA = "see run.json"
R4_ROWS = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz")
SKY_MASK = os.path.join(REPO, "Tools", "PaintingTruth", "targets", "masks", "sky_envelope_cov.png")

# 禁止域の格子（断面の a, y）
GA0, GA1, GY0, GY1, GRES = -34.0, 30.0, -8.0, 32.0, 0.12
NA = int(round((GA1 - GA0) / GRES)) + 1
NY = int(round((GY1 - GY0) / GRES)) + 1


def load_rows(p):
    z = np.load(p)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def cam_sec():
    s = KC.sec(KC.CAM_POS_U[None])[0]
    return s  # (a, y, c)


def sky_rays(dilate_px=3, step=2):
    """原画の空（包絡版の空の被覆 > 0.5）を dilate_px 画素だけ波の側へ広げた画素の射線（Unity の単位方向）。"""
    from PIL import Image
    import cv2
    sky = np.array(Image.open(SKY_MASK)).astype(np.float32) / 65535.0
    m = (sky > 0.5).astype(np.uint8)
    if dilate_px > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * dilate_px + 1, 2 * dilate_px + 1))
        m = cv2.dilate(m, k)
    ys, xs = np.nonzero(m[::step, ::step])
    xs = xs * step; ys = ys * step
    pos, r, u, f = KC.cam_basis_unity()
    t = math.tan(math.radians(KC.CAM_VFOV) / 2.0); asp = KC.CAM_W / float(KC.CAM_H)
    vx = (xs + 0.5) / KC.CAM_W; vy = 1.0 - (ys + 0.5) / KC.CAM_H
    D = ((2 * vx - 1) * t * asp)[:, None] * r + ((2 * vy - 1) * t)[:, None] * u + f[None, :]
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    return D, np.c_[xs, ys]


def keepout_grids(c, dilate_px=3, step=2, cache=None):
    """行ごとの空の射線の禁止域（NY×NA の bool、行 = y 昇順、列 = a 昇順）。"""
    if cache and os.path.isfile(cache):
        z = np.load(cache)
        if np.allclose(z["c"], c) and int(z["dilate"]) == dilate_px:
            return np.unpackbits(z["G"], axis=-1)[..., :NA].astype(bool)
    import cv2
    D, _ = sky_rays(dilate_px, step)
    P0 = KC.CAM_POS_U
    dE = D @ KC.E; dT = D @ KC.T; dY = D[:, 1]
    s0 = KC.sec(P0[None])[0]
    G = np.zeros((len(c), NY, NA), bool)
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    for i, cc in enumerate(c):
        ok = dE > 1e-6
        t = (cc - s0[2]) / dE[ok]
        pos = t > 0
        a = s0[0] + t[pos] * dT[ok][pos]; y = s0[1] + t[pos] * dY[ok][pos]
        ia = np.round((a - GA0) / GRES).astype(int); iy = np.round((y - GY0) / GRES).astype(int)
        m = (ia >= 0) & (ia < NA) & (iy >= 0) & (iy < NY)
        g = np.zeros((NY, NA), np.uint8); g[iy[m], ia[m]] = 1
        g = cv2.dilate(g, k)
        G[i] = g.astype(bool)
    if cache:
        np.savez_compressed(cache, c=c, dilate=dilate_px, G=np.packbits(G, axis=-1))
    return G


def section_fill(a, y, bottom=-7.9):
    """1 行の断面（列 0..399 の折れ線）を海の下の底で閉じた多角形の塗り（NY×NA の bool）。"""
    import cv2
    xs = (np.r_[a, a[-1], a[0]] - GA0) / GRES
    ys = (np.r_[y, bottom, bottom] - GY0) / GRES
    pts = np.round(np.c_[xs, ys] * 16).astype(np.int32)
    g = np.zeros((NY, NA), np.uint8)
    cv2.fillPoly(g, [pts], 1, lineType=cv2.LINE_8, shift=4)
    return g.astype(bool)


def spill_rows(c, A, Y, G, base=None, rows=None):
    """行ごとの、禁止域にかかる塗りのセル数（base を渡せば base より増えた分だけ）。"""
    rows = range(len(c)) if rows is None else rows
    out = np.zeros(len(c), int)
    for i in rows:
        f = section_fill(A[i], Y[i]) & G[i]
        if base is not None:
            f &= ~section_fill(base[0][i], base[1][i])
        out[i] = int(f.sum())
    return out


def ss(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def csmooth(c, v, sigma):
    dc = np.gradient(c)
    W = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sigma) ** 2) * dc[None, :]
    W /= W.sum(1, keepdims=True)
    return W @ v


def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
