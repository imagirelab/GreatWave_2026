# -*- coding: utf-8 -*-
"""美術の見本05 の渡す準備：粘土（色なし・爪なし）と三つの層の色づけを、見本04・形 A（A9）・形 B（B10）で同じ視点・同じカメラで描く。
numpy の z バッファ（Unity の描画ではない）。場面は測りの係と同じ s5_targets.load_cand・scene（主役波の行 ＋ wave4 ＋ 形 A は layer3 ＋ 近い海）。
カメラは asm4_common.view_cam（Unity の描画と同じ視点）を 960×540 で使う。原画の色・原画カメラの投影は使わない。船・爪は入れない。
py -3.10 -B Tools/GWWaveGen/as05/as05_clay.py [視点,...]
出力：Unity/Build/Polish/sample05/deliver/clay/<S04|A9|B10>_<視点>_{clay,tint}.png・_labels.npy（並べ図の切り抜き用）と clay_report.json
"""
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_targets as T5  # noqa: E402

A = T5.A
P = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish"
OUT = P + "/sample05/deliver/clay"
CANDS = {"S04": P + "/sample05/study/baseline_sample04.json",
         "A9": P + "/sample05/fix1/assemble/measure/targets_A9.json",
         "B10": P + "/sample05/fix1/assemble/measure/targets_B10.json"}
VIEWS = ["side_left", "side_right", "top", "back65", "tt0", "tt30", "tt60", "tt90", "tt240", "tt270", "tt300", "tt330"]
LIGHT = np.array([-0.35, 0.8, -0.5]); LIGHT = LIGHT / np.linalg.norm(LIGHT)      # shapeA_clay.py と同じ光
TINT = {1: (214, 64, 52), 2: (64, 160, 72), 3: (40, 170, 190), 4: (190, 186, 176), 8: (140, 138, 132), 5: (70, 96, 200), 6: (206, 214, 220)}


def render(cam, tris, lab):
    idb, D, L = A.raster(cam, tris, lab)
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    v = cam.pos[None, :] - tris.mean(1)
    n[(n * v).sum(1) < 0] *= -1
    sh = 0.35 + 0.65 * (0.5 + 0.5 * (n @ LIGHT))
    t = idb - 1
    m = t >= 0
    s = sh[t[m]][:, None]
    lt = lab[t[m]]
    clay = np.full(idb.shape + (3,), (238, 234, 222), np.float64)
    base = np.where((lt == 6)[:, None], np.array([170, 180, 188], float), np.array([196, 190, 178], float))
    clay[m] = base * s
    tint = np.full(idb.shape + (3,), (238, 234, 222), np.float64)
    col = np.zeros((len(lt), 3))
    for k, c in TINT.items():
        col[lt == k] = c
    tint[m] = col * (0.55 + 0.45 * s)
    e = A.occl_edges(np.where(np.isfinite(D), D, np.inf))
    clay[e] = (30, 30, 30); tint[e] = (20, 20, 20)
    return np.clip(clay, 0, 255).astype(np.uint8), np.clip(tint, 0, 255).astype(np.uint8), L


def main():
    views = sys.argv[1].split(",") if len(sys.argv) > 1 else VIEWS
    os.makedirs(OUT, exist_ok=True)
    rep = {"note_ja": "numpy の z バッファの粘土（Unity の描画ではない）。船・爪なし。カメラは asm4_common.view_cam の 960×540",
           "light": LIGHT.tolist(), "views": views, "kinds": {}}
    for kind, jp in CANDS.items():
        cand = json.load(open(jp, encoding="utf-8"))["candidate"]
        t0 = time.time()
        c, Ar, Yr, RL, ms = T5.load_cand(cand)
        tris, lab = T5.scene(c, Ar, Yr, RL, ms)
        del c, Ar, Yr, RL, ms
        rep["kinds"][kind] = {"candidate": cand, "candidate_json": jp, "triangles": int(len(tris)), "pixels": {}}
        for v in views:
            cam = A.view_cam(v, 960, 540)
            clay, tint, L = render(cam, tris, lab)
            cv2.imwrite(OUT + "/%s_%s_clay.png" % (kind, v), clay[..., ::-1])
            cv2.imwrite(OUT + "/%s_%s_tint.png" % (kind, v), tint[..., ::-1])
            np.save(OUT + "/%s_%s_labels.npy" % (kind, v), L.astype(np.uint8))
            rep["kinds"][kind]["pixels"][v] = {str(k): int((L == k).sum()) for k in (1, 2, 3, 4, 5, 8)}
            print("clay", kind, v, "%.1fs" % (time.time() - t0), flush=True)
        del tris, lab
    json.dump(rep, open(OUT + "/clay_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
