# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：診断の図。候補の格子を、任意の視点から numpy の点の z バッファーで描き、行の c の帯（2 m ごとの色）と
列の帯（背 0..80・頂 80..110・唇 110..200・管 200..）で塗る（後ろから見たドームが、どの行・列でできているかを見る）。
usage: py -3.10 r01_shoulder_cband.py <out.png> <rows.npz> [view=b65_back65_clay] [w=960]"""
import os
import sys
import json
import math

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_shoulder_common as S  # noqa: E402
KC = S.KC


def look(eye, tgt, vfov, W, H):
    f = np.asarray(tgt, float) - np.asarray(eye, float); f /= np.linalg.norm(f)
    r = np.cross(f, [0, 1.0, 0]); r /= np.linalg.norm(r)     # Unity は左手系：右 = f × up の符号は描いて確かめる
    u = np.cross(r, f)
    t = math.tan(math.radians(vfov) / 2)
    return np.asarray(eye, float), r, u, f, t, W / H


def main():
    out, rows = sys.argv[1], sys.argv[2]
    opts = dict(a.split("=", 1) for a in sys.argv[3:])
    vn = opts.get("view", "b65_back65_clay"); W = int(opts.get("w", "960")); H = int(W * 9 / 16)
    V = json.load(open(os.path.join(HERE, "rays_views.json"), encoding="utf-8"))
    vv = {v["name"]: v for k in V if isinstance(V[k], list) for v in V[k]}[vn]
    eye, r, u, f, t, asp = look(vv["eye"], vv["tgt"], vv["vfov"], W, H)
    c, A, Y = S.load_rows(rows)
    # 4 倍に細かく（双一次）
    up = 4
    nv, nu = A.shape
    ri = np.linspace(0, nv - 1, (nv - 1) * up + 1); ci = np.linspace(0, nu - 1, (nu - 1) * up + 1)
    from scipy.ndimage import map_coordinates
    RR, CC = np.meshgrid(ri, ci, indexing="ij")
    Af = map_coordinates(A, [RR, CC], order=1); Yf = map_coordinates(Y, [RR, CC], order=1)
    cf = np.interp(ri, np.arange(nv), c)[:, None] * np.ones_like(Af)
    X = KC.world(cf[:, 0], Af, Yf)
    # 法線（格子の差分）
    du = np.gradient(X, axis=1); dv = np.gradient(X, axis=0)
    n = np.cross(du, dv); n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    P = X.reshape(-1, 3) - eye
    zc = P @ f
    ok = zc > 0.5
    x = (P @ r) / (zc * t * asp); y = (P @ u) / (zc * t)
    px = ((x + 1) * 0.5 * W).astype(int); py = ((1 - (y + 1) * 0.5) * H).astype(int)
    ok &= (px >= 0) & (px < W) & (py >= 0) & (py < H)
    idx = np.nonzero(ok)[0]
    z = np.full(W * H, np.inf); pix = py[idx] * W + px[idx]
    order = np.argsort(-zc[idx])          # 遠い順に書き、近いものが上書き
    sel = idx[order]; pix = pix[order]
    img = np.full((H * W, 3), 235, np.float32)
    cc = cf.reshape(-1)[sel]; jj = (CC.reshape(-1)[sel]).astype(int)
    band = np.floor(cc / 2.0).astype(int)
    pal = np.array([[230, 80, 80], [240, 170, 60], [220, 220, 70], [90, 200, 90], [70, 190, 210], [80, 110, 230], [170, 90, 220], [230, 120, 180]], np.float32)
    col = pal[band % 8].copy()
    col[cc < -16] = [150, 150, 150]
    col[np.abs(cc) < 0.25] = [0, 0, 0]
    col[np.abs(cc - 10) < 0.15] = [255, 255, 255]
    nn = n.reshape(-1, 3)[sel]
    vdir = -(P[sel]) / np.linalg.norm(P[sel], axis=1, keepdims=True)
    lam = np.abs((nn * vdir).sum(1))
    shade = 0.45 + 0.55 * lam
    colj = np.where((jj > 110)[:, None], col * 0.6, col)
    img[pix] = colj * shade[:, None]
    im = Image.fromarray(np.clip(img.reshape(H, W, 3), 0, 255).astype(np.uint8))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out)


if __name__ == "__main__":
    main()
