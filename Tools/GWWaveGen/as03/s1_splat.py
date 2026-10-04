# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの一時キャッシュを、点の描画（陰影つき）で確かめるための一時の図にする（数を読む人の目の確かめ用）。
形の画像なので、出力はキャッシュのフォルダー（Git 対象外）だけに置き、s1_obj.py delete で消す。リポジトリ・成果物へは入れない。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_splat.py <名前> <視線 a,y,c> <上 a,y,c> <中心 a,y,c> <幅 m> [画素の幅]
"""
import os
import sys

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402


def vnormals(V, F):
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    fn = np.cross(p1 - p0, p2 - p0)
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return N


def render(V, N, view, up, center, width, px=1400, light=None, ylim=None):
    f = np.asarray(view, float)
    f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    u = u - f * (u @ f)
    u /= np.linalg.norm(u)
    r = np.cross(u, f)
    r /= np.linalg.norm(r)
    Q = V - np.asarray(center, float)
    x = Q @ r
    y = Q @ u
    z = Q @ f
    s = px / width
    W = px
    H = px
    ix = np.round(x * s + W / 2).astype(int)
    iy = np.round(H / 2 - y * s).astype(int)
    ok = (ix >= 0) & (ix < W - 1) & (iy >= 0) & (iy < H - 1)
    if ylim is not None:
        ok &= (V[:, 1] >= ylim)
    if light is None:
        light = -f + u * 0.6 + r * 0.4
    light = np.asarray(light, float)
    light /= np.linalg.norm(light)
    shade = np.clip(N @ light, 0, 1) * 0.8 + 0.2
    face = (N @ -f) > 0
    shade = np.where(face, shade, shade * 0.5)
    img = np.zeros((H, W), np.float32)
    zb = np.full((H, W), np.inf, np.float32)
    o = np.argsort(-z[ok])          # 遠い順に書き、近いもので上書き
    xi, yi, zz, sh = ix[ok][o], iy[ok][o], z[ok][o], shade[ok][o]
    for dx in (0, 1):
        for dy in (0, 1):
            img[yi + dy, xi + dx] = sh
            zb[yi + dy, xi + dx] = zz
    hole = ~np.isfinite(zb)
    img8 = (img * 255).astype(np.uint8)
    img8 = cv2.inpaint(img8, (hole & (cv2.dilate((~hole).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0)).astype(np.uint8), 2, cv2.INPAINT_TELEA)
    # 1 m の目盛り
    for k in range(0, int(width) + 1):
        xx = int(k * s)
        cv2.line(img8, (xx, H - 1), (xx, H - (12 if k % 5 == 0 else 5)), 255, 1)
    return img8


def main():
    name = sys.argv[1]
    view = [float(v) for v in sys.argv[2].split(",")]
    up = [float(v) for v in sys.argv[3].split(",")]
    center = [float(v) for v in sys.argv[4].split(",")]
    width = float(sys.argv[5])
    px = int(sys.argv[6]) if len(sys.argv) > 6 else 1400
    ylim = float(sys.argv[7]) if len(sys.argv) > 7 else None
    V, F = SO.load()
    N = vnormals(V, F)
    img = render(V, N, view, up, center, width, px, ylim=ylim)
    fp = SO.CACHE_DIR + "/tmp_splat_%s.png" % name
    cv2.imwrite(fp, img)
    print(fp)


if __name__ == "__main__":
    main()
