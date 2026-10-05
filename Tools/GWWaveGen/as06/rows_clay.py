# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS）：粘土（色なし・爪なし・船なし）と三つの層の色づけを、見本05 B（B10）と新しい行で同じ視点に描き、並べ図にする。
as05/as05_clay.py（変えない）の写し。numpy の z バッファ（Unity の描画ではない）。場面は s5_targets.load_cand・scene（主役波の行 ＋ wave4 ＋ 近い海）。
カメラは asm4_common.view_cam（Unity の描画と同じ視点）と原画のカメラ（asm4_common.painting_cam）を 960×540 で使う。原画の色・原画カメラの投影は使わない。
py -3.10 -B Tools/GWWaveGen/as06/rows_clay.py <out_dir> <名前=cand.json> [<名前=cand.json> ...] [--views=painting,seat,...]
  cand.json は s5_targets.measure の形（{"rows", "row_labels", "meshes"}）か、その形を "candidate" に持つ測りの .json。
出力：<out_dir>/<名前>_<視点>_{clay,tint}.png、並べ図 sheet_clay.png・sheet_tint.png（見本05 B と新しい行を上下に）、clay_report.json
"""
import json
import os
import sys
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
import s5_targets as T5  # noqa: E402

A = T5.A
VIEWS = ["painting", "seat", "side_left", "side_right", "back65", "top"] + ["tt%d" % a for a in range(0, 360, 30)]
NAMES_JA = {"painting": "原画視点", "seat": "座席", "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
LIGHT = np.array([-0.35, 0.8, -0.5]); LIGHT = LIGHT / np.linalg.norm(LIGHT)      # as05_clay.py と同じ光
TINT = {1: (214, 64, 52), 2: (64, 160, 72), 3: (40, 170, 190), 4: (190, 186, 176), 8: (140, 138, 132), 5: (70, 96, 200), 6: (206, 214, 220)}


def font(sz):
    for p in ("C:/Windows/Fonts/BIZ-UDGothicR.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def cam_for(v):
    if v == "painting":
        return A.painting_cam(0.5)
    return A.view_cam(v, 960, 540)


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


def crop_box(out_dir, kinds, v, pad=0.10):
    """視点 v で、どの候補でも主役波・wave4 が入る四角（16:9、余白 pad）。原画視点と座席は切らない。"""
    if v in ("painting", "seat"):
        return (0, 0, 960, 540)
    m = None
    for k in kinds:
        p = os.path.join(out_dir, "%s_%s_labels.npy" % (k, v))
        if os.path.isfile(p):
            L = np.isin(np.load(p), (1, 2, 3, 4, 5, 8))
            m = L if m is None else (m | L)
    if m is None or not m.any():
        return (0, 0, 960, 540)
    ys, xs = np.nonzero(m)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    w, h = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
    w = max(w, h * 16 / 9, 160); h = w * 9 / 16
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    x0 = int(np.clip(cx - w / 2, 0, 960 - w)); y0 = int(np.clip(cy - h / 2, 0, 540 - h))
    return (x0, y0, int(x0 + min(w, 960)), int(y0 + min(h, 540)))


def sheet(out_dir, kinds, views, kind_ja, suffix, title, cols=6, tw=480):
    th = tw * 540 // 960
    boxes = {v: crop_box(out_dir, kinds, v) for v in views}
    rows_per_kind = (len(views) + cols - 1) // cols
    W = cols * tw + 10
    H = 70 + len(kinds) * rows_per_kind * (th + 4) + 30
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((8, 6), title, font=font(24), fill=(0, 0, 0))
    d.text((8, 40), "numpy の z バッファの粘土（Unity の描画ではない）。t* = 12 s の静止。爪・船なし。黒い線 = 遮る縁。色づけ：赤 ①・緑 ②・水色 ③・青 wave4・灰 ほかの前の面・濃い灰 背。原画視点・座席のほかは波の所を切り出して拡大（同じ視点は同じ切り出し）",
           font=font(14), fill=(60, 60, 60))
    y = 70
    for k in kinds:
        for r in range(rows_per_kind):
            for cidx in range(cols):
                vi = r * cols + cidx
                if vi >= len(views):
                    continue
                v = views[vi]
                p = os.path.join(out_dir, "%s_%s_%s.png" % (k, v, suffix))
                if not os.path.isfile(p):
                    continue
                im = Image.open(p).convert("RGB").crop(boxes[v]).resize((tw, th), Image.LANCZOS)
                x = 5 + cidx * tw
                img.paste(im, (x, y))
                lab = "%s ／ %s" % (kind_ja.get(k, k), NAMES_JA.get(v, ("回り台 %s°" % v[2:]) if v.startswith("tt") else v))
                bb = d.textbbox((x + 4, y + 3), lab, font=font(15))
                d.rectangle((bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2), fill=(255, 255, 255))
                d.text((x + 4, y + 3), lab, font=font(15), fill=(0, 0, 0))
            y += th + 4
    img.save(os.path.join(out_dir, "sheet_%s.png" % suffix))


def main():
    out = sys.argv[1]
    items = [a for a in sys.argv[2:] if not a.startswith("--")]
    views = VIEWS
    for a in sys.argv[2:]:
        if a.startswith("--views="):
            views = a[8:].split(",")
    os.makedirs(out, exist_ok=True)
    rep = {"note_ja": "numpy の z バッファの粘土（Unity の描画ではない）。船・爪なし。カメラは asm4_common.view_cam・painting_cam の 960×540",
           "light": LIGHT.tolist(), "views": views, "kinds": {}}
    kinds = []
    for it in items:
        kind, jp = it.split("=", 1)
        kinds.append(kind)
        cj = json.load(open(jp, encoding="utf-8"))
        cand = cj.get("candidate", cj)
        t0 = time.time()
        c, Ar, Yr, RL, ms = T5.load_cand(cand)
        tris, lab = T5.scene(c, Ar, Yr, RL, ms)
        del c, Ar, Yr, RL, ms
        rep["kinds"][kind] = {"candidate": cand, "candidate_json": jp, "triangles": int(len(tris)), "pixels": {}}
        for v in views:
            cam = cam_for(v)
            clay, tint, L = render(cam, tris, lab)
            cv2.imwrite(out + "/%s_%s_clay.png" % (kind, v), clay[..., ::-1])
            cv2.imwrite(out + "/%s_%s_tint.png" % (kind, v), tint[..., ::-1])
            np.save(out + "/%s_%s_labels.npy" % (kind, v), L.astype(np.uint8))
            rep["kinds"][kind]["pixels"][v] = {str(k): int((L == k).sum()) for k in (1, 2, 3, 4, 5, 8)}
        print("clay", kind, "%.1fs" % (time.time() - t0), flush=True)
        del tris, lab
    kind_ja = {k: k for k in kinds}
    kind_ja.update({"B10": "見本05 B", "S04": "見本04"})
    for suf, ttl in (("clay", "段の行（B-ROWS）：色なしの粘土"), ("tint", "段の行（B-ROWS）：三つの層の色づけ")):
        sheet(out, kinds, views, kind_ja, suf, ttl + "　" + "｜".join(kind_ja[k] for k in kinds))
    json.dump(rep, open(out + "/clay_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
