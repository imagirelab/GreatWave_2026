# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：粘土（形だけ）の描画。numpy の z バッファ（Unity の描画ではない）。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_clay.py <name> <rows.npz> <row_labels.npy|-> <mesh.json:layer,...> <out_dir> [views]

- 層の色づけ（①赤・②緑・③青緑・ほかの前の灰・背の濃い灰・wave4 青・近い海・爪 白）と、色づけなしの粘土（一つの灰色に、固定の光の
  半ランバートと遮る縁の線）を、同じ視点で描く。視点：原画視点・座席・左右の側面・後ろ 65°・真上・回り台 12 方位（asm4_common.view_cam）。
- 一艘目の船は numpy の場面に入れていない（Unity の描画で見る）。爪は -claws で入れる。
"""
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import s5_targets as T5  # noqa: E402

A = T5.A
S5 = T5.S
VIEWS = ["painting", "seat", "side_left", "side_right", "back65", "top"] + ["tt%d" % a for a in range(0, 360, 30)]
LIGHT = np.array([-0.35, 0.8, -0.5]); LIGHT = LIGHT / np.linalg.norm(LIGHT)


def cam_for(v):
    return A.painting_cam(1) if v == "painting" else A.view_cam(v)


def shade_img(cam, tris, lab, idb, D):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    ctr = tris.mean(1)
    vdir = cam.pos[None, :] - ctr
    flip = (n * vdir).sum(1) < 0
    n[flip] *= -1
    sh = 0.5 + 0.5 * (n @ LIGHT)
    sh = 0.35 + 0.65 * sh
    t = idb - 1
    img = np.full(idb.shape + (3,), (238, 234, 222), np.float64)
    m = t >= 0
    base = np.array([196, 190, 178], float)
    col = np.where((lab[t[m]] == 6)[:, None], np.array([160, 172, 182], float), base)
    col = np.where((lab[t[m]] == 7)[:, None], np.array([250, 250, 250], float), col)
    img[m] = col * sh[t[m]][:, None]
    e = A.occl_edges(np.where(np.isfinite(D), D, np.inf))
    img[e] = (30, 30, 30)
    return np.clip(img, 0, 255).astype(np.uint8)


def build_scene(rows, row_labels, meshes, claws=None):
    cand = {"rows": rows, "row_labels": row_labels if row_labels != "-" else None, "meshes": meshes}
    c, Ar, Yr, RL, ms = T5.load_cand(cand)
    tris, lab = T5.scene(c, Ar, Yr, RL, ms)
    if claws:
        cl, _ = A.claws_tris(claws)
        tris = np.concatenate([tris] + [x["verts"][x["tris"]] for x in cl])
        lab = np.concatenate([lab] + [np.full(len(x["tris"]), 7, np.int16) for x in cl])
    return tris, lab


def main():
    name, rows, rl, mspec, out = sys.argv[1:6]
    views = sys.argv[6].split(",") if len(sys.argv) > 6 and sys.argv[6] not in ("all", "") else VIEWS
    claws = os.environ.get("SHAPEA_CLAWS")
    meshes = []
    for m in [x for x in mspec.split(",") if x]:
        p, k = m.rsplit(":", 1)
        rec = {"path": p, "layer": int(k), "role": os.path.basename(p)}
        vl = os.path.splitext(p)[0] + "_labels.npy"
        if int(k) and os.path.isfile(vl):
            rec["vertex_labels"] = vl
        meshes.append(rec)
    tris, lab = build_scene(rows, rl, meshes, claws)
    os.makedirs(out, exist_ok=True)
    rep = {}
    for v in views:
        cam = cam_for(v)
        idb, D, L = A.raster(cam, tris, lab)
        cv2.imwrite(out + "/%s_%s_layers.png" % (name, v), A.tint(L, np.where(np.isfinite(D), D, np.inf))[..., ::-1])
        cv2.imwrite(out + "/%s_%s_clay.png" % (name, v), shade_img(cam, tris, lab, idb, D)[..., ::-1])
        rep[v] = {str(k): int((L == k).sum()) for k in (1, 2, 3, 4, 5, 8)}
        print(v, rep[v], flush=True)
    C.jdump(out + "/%s_clay_report.json" % name, {"views": rep, "rows": rows, "row_labels": rl, "meshes": meshes, "claws": claws,
                                                  "note_ja": "numpy の z バッファの粘土（Unity の描画ではない）。船は入れていない"})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
