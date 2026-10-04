# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：粘土（形だけ）の描画。numpy の z バッファで、主役波の行（列 18〜394）＋ wave4（見本04 fix1）＋ 近い海を、
平らな灰の粘土（光の向きの陰影だけ）と、三つの層の色づけ（① 赤・② 緑・③ 水色・wave4 青・ほかの前の面 灰）で描く。遮る縁は黒い線。
Unity の描画ではない（形を見る道具）。原画の色は使わない。

py -3.10 -B Tools/GWWaveGen/as05/shapeB_clay.py <rows.npz> <row_labels.npy または - > <out_dir> <名前> [視点,...]
視点の既定：painting,seat,seat_toward_wave,side_left,side_right,back65,top,tt0..tt330（30° おき）
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeB_common as B  # noqa: E402
import s5_targets as T5  # noqa: E402

A_ = T5.A
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"] + ["tt%d" % a for a in range(0, 360, 30)]
TINT = {1: (214, 64, 52), 2: (64, 160, 72), 3: (40, 170, 190), 4: (176, 176, 170), 8: (150, 150, 146), 5: (70, 96, 200), 6: (206, 214, 220)}
LIGHT = np.array([0.35, 0.85, -0.40]); LIGHT /= np.linalg.norm(LIGHT)


def scene(rows, rl_path):
    c, A, Y = B.load_rows(rows)
    RL = np.load(rl_path) if rl_path and rl_path != "-" else np.zeros(A.shape, np.int16)
    ch4, tri4, _ = T5.S.W4.read_static(B.WAVE4_F1)
    X4 = ch4["position"].astype(np.float64)
    meshes = [{"P": X4, "tri": tri4.astype(np.int64), "vl": np.zeros(len(X4), np.int16), "role": "wave4"}]
    tris, lab = T5.scene(c, A, Y, RL, meshes)
    return tris, lab


def render(cam, tris, lab):
    idb, D, L = A_.raster(cam, tris, lab)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    # 視点の側へ向ける（両面）
    cen = tris.mean(1)
    v = cam.pos[None, :] - cen
    n = np.where(((n * v).sum(1) < 0)[:, None], -n, n)
    sh = 0.42 + 0.58 * np.clip(n @ LIGHT, 0, 1)
    S_ = np.where(idb > 0, sh[np.maximum(idb - 1, 0)], 1.0)
    edge = A_.occl_edges(np.where(np.isfinite(D), D, np.inf))
    clay = np.full(L.shape + (3,), 236, np.float64)
    base = np.array([196, 190, 180], float)
    m = idb > 0
    clay[m] = base[None, :] * S_[m][:, None]
    sea = L == 6
    clay[sea] = np.array([206, 214, 220]) * (0.85 + 0.15 * S_[sea][:, None])
    tint = clay.copy()
    for k, col in TINT.items():
        mk = (L == k) & (k != 6)
        tint[mk] = np.array(col, float)[None, :] * (0.55 + 0.45 * S_[mk][:, None])
    clay[edge & m] = (40, 40, 40); tint[edge & m] = (25, 25, 25)
    return np.clip(clay, 0, 255).astype(np.uint8), np.clip(tint, 0, 255).astype(np.uint8), L


def main():
    rows, rl, od, name = sys.argv[1:5]
    views = sys.argv[5].split(",") if len(sys.argv) > 5 else VIEWS
    os.makedirs(od, exist_ok=True)
    tris, lab = scene(rows, rl)
    for vn in views:
        cam = A_.painting_cam(1) if vn == "painting" else A_.view_cam(vn)
        clay, tint, L = render(cam, tris, lab)
        cv2.imwrite(od + "/%s_%s_clay.png" % (name, vn), clay[..., ::-1])
        cv2.imwrite(od + "/%s_%s_tint.png" % (name, vn), tint[..., ::-1])
        print("clay", name, vn, flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
