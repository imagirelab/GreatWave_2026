# -*- coding: utf-8 -*-
"""美術の見本02 爪の部：並べ図（どれも 1920×1080、Git 対象外の Build/Polish/sample02/claws/figs/）。
  fig1_painting.png   原画視点：原画の切り出し｜前（見本01 A2 の爪）｜案 A（原画の射線の上）｜案 B（参照モデルの置き方）と、利用者のマスクの重ね
  fig2_views_*.png    見直しの視点（座席・座席から波・左右の側面・後ろ 65°・真上）：前｜案 A｜案 B（同じ視点・同じ時刻 t* = 12 s）
  fig3_closeups.png   爪の所の拡大（各視点で爪の頂点の範囲を切り出す）：案 A｜案 B
  fig4_turntable_*.png 回り台 12 方位（案 A・案 B・前）
原画の画像はリポジトリの Docs/References/Met_JP1847_DP130155.jpg（メトロポリタン美術館の公開画像）。利用者のマスクの重ねを含む図は Build にだけ置く。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_sheets.py
"""
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_claws100 as A  # noqa: E402

CC = A.CC
B2 = REPO + "/Unity/Build/Polish/sample02/claws"
REND = {"before": REPO + "/Unity/Build/Polish/sample01/assemble/A2", "A": B2 + "/render/A_final", "B": B2 + "/render/B_ref_final"}
LAB = {"before": "before: art sample 01 A2 claws", "A": "A: user's 100 claws, on painting rays", "B": "B: user's 100 claws, stood up like reference"}
MESH = {"A": B2 + "/mesh", "B": B2 + "/mesh_ref"}
OUT = B2 + "/figs"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]


def put(img, text, org=(10, 28), s=0.8, col=(0, 0, 0), bg=(255, 255, 255)):
    (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, s, 2)
    cv2.rectangle(img, (org[0] - 4, org[1] - h - 6), (org[0] + w + 4, org[1] + 6), bg, -1)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, s, col, 2, cv2.LINE_AA)
    return img


def canvas():
    return np.full((1080, 1920, 3), 255, np.uint8)


def fit(img, w, h):
    s = min(w / img.shape[1], h / img.shape[0])
    r = cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), 255, np.uint8)
    out[(h - r.shape[0]) // 2:(h - r.shape[0]) // 2 + r.shape[0], (w - r.shape[1]) // 2:(w - r.shape[1]) // 2 + r.shape[1]] = r
    return out


def painting_disp():
    pa = cv2.imdecode(np.fromfile(REPO + "/Docs/References/Met_JP1847_DP130155.jpg", np.uint8), cv2.IMREAD_COLOR)
    s = 0.4163454124903624
    return cv2.warpAffine(pa, np.array([[s, 0, s * 0.5 - 0.5 + 156.66152659984573], [0, s, s * 0.5 - 0.5]]), (1920, 1080), flags=cv2.INTER_AREA)


def view_img(key, v, claws=True):
    if v.startswith("tt"):
        p = REND[key] + "/tt/t120_az%03d_claws.png" % int(v[2:])
    else:
        p = REND[key] + "/views/%s_t120_%s.png" % (v, "claws" if claws else "clawfree")
    im = cv2.imread(p)
    if im is None:
        im = np.full((1080, 1920, 3), 200, np.uint8)
        put(im, "missing " + os.path.basename(p), (20, 60))
    return im


def fig_painting():
    disp = painting_disp()
    users, _, _ = A.load_user()
    mk = np.zeros((1080, 1920), np.uint8)
    for u in users:
        m = A.imread_u(u["dir"] + "/fill_mask.png", cv2.IMREAD_GRAYSCALE)
        mk = np.maximum(mk, cv2.warpAffine(m, A.disp_affine(u["A"]), (1920, 1080), flags=cv2.INTER_LINEAR))
    x0, y0, x1, y1 = 470, 30, 1190, 540     # 主浪の頂と唇
    cw, ch = 940, 510
    c = canvas()
    tiles = [("painting (Met DP130155) + user masks", disp.copy()), (LAB["before"], view_img("before", "painting")),
             (LAB["A"], view_img("A", "painting")), (LAB["B"], view_img("B", "painting"))]
    cnt, _ = cv2.findContours((mk > 127).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(tiles[0][1], cnt, -1, (0, 160, 0), 1)
    for k, (lab, im) in enumerate(tiles):
        crop = im[y0:y1, x0:x1]
        t = fit(crop, cw, ch)
        put(t, lab, (12, 30), 0.7)
        r, cc = divmod(k, 2)
        c[20 + r * (ch + 20):20 + r * (ch + 20) + ch, 13 + cc * (cw + 14):13 + cc * (cw + 14) + cw] = t
    cv2.imwrite(OUT + "/fig1_painting.png", c)
    # 全体（縮小）の並べ
    c2 = canvas()
    full = [("painting", disp), (LAB["before"], view_img("before", "painting")), (LAB["A"], view_img("A", "painting")), (LAB["B"], view_img("B", "painting"))]
    for k, (lab, im) in enumerate(full):
        t = fit(im, 940, 528)
        put(t, lab, (12, 30), 0.7)
        r, cc = divmod(k, 2)
        c2[10 + r * 535:10 + r * 535 + 528, 13 + cc * 954:13 + cc * 954 + 940] = t
    cv2.imwrite(OUT + "/fig1b_painting_full.png", c2)


def fig_views():
    groups = [["seat", "seat_toward_wave", "side_left"], ["side_right", "back65", "top"]]
    for gi, g in enumerate(groups):
        c = canvas()
        cw, ch = 624, 351
        for r, v in enumerate(g):
            for k, key in enumerate(["before", "A", "B"]):
                t = fit(view_img(key, v), cw, ch)
                put(t, "%s | %s" % (v, LAB[key].split(":")[0]), (10, 26), 0.6)
                c[5 + r * (ch + 8):5 + r * (ch + 8) + ch, 5 + k * (cw + 8):5 + k * (cw + 8) + cw] = t
        cv2.imwrite(OUT + "/fig2_views_%d.png" % (gi + 1), c)


def claw_box(mesh, view, pad=0.25):
    E = np.load(mesh + "/as02_entries.npy", allow_pickle=True)
    V = np.concatenate([e["V"] for e in E])
    cam = CC.painting_cam() if view == "painting" else CC.cam_view(view)
    q, z = cam.project(V)
    ok = (z > 0.1) & (q[:, 0] > -200) & (q[:, 0] < 2120) & (q[:, 1] > -200) & (q[:, 1] < 1280)
    q = q[ok]
    if not len(q):
        return 0, 0, 1920, 1080
    lo = np.percentile(q, 3, axis=0)
    hi = np.percentile(q, 97, axis=0)
    c = 0.5 * (lo + hi)
    half = np.maximum((hi - lo) * (0.5 + pad), [160, 90])
    # 16:9 にそろえる
    if half[0] / half[1] < 16 / 9:
        half[0] = half[1] * 16 / 9
    else:
        half[1] = half[0] * 9 / 16
    x0, y0 = c - half
    x1, y1 = c + half
    x0, y0 = max(int(x0), 0), max(int(y0), 0)
    x1, y1 = min(int(x1), 1920), min(int(y1), 1080)
    return x0, y0, x1, y1


def diff_box(key, v, pad=0.35):
    """爪ありと爪なしの描画の差（爪が見える画素）の範囲を 16:9 で返す（見える爪が少ない時は真ん中の 1/2）。"""
    a = view_img(key, v, True).astype(np.int16)
    b = view_img(key, v, False).astype(np.int16)
    d = (np.abs(a - b).sum(2) > 40).astype(np.uint8)
    d = cv2.morphologyEx(d, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    ys, xs = np.nonzero(d)
    if len(xs) < 30:
        return 480, 270, 1440, 810, int(len(xs))
    x0, x1 = np.percentile(xs, [2, 98])
    y0, y1 = np.percentile(ys, [2, 98])
    c = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
    half = np.maximum(np.array([x1 - x0, y1 - y0]) * (0.5 + pad), [120, 68])
    if half[0] / half[1] < 16 / 9:
        half[0] = half[1] * 16 / 9
    else:
        half[1] = half[0] * 9 / 16
    x0, y0 = np.maximum(c - half, 0).astype(int)
    x1, y1 = np.minimum(c + half, [1920, 1080]).astype(int)
    return x0, y0, x1, y1, int(len(xs))


def fig_closeups():
    vs = ["seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    for key in ["A", "B", "before"]:
        c = canvas()
        cw, ch = 950, 345
        for k, v in enumerate(vs):
            x0, y0, x1, y1, npx = diff_box(key, v)
            t = fit(view_img(key, v)[y0:y1, x0:x1], cw, ch)
            put(t, "%s close-up x%.1f | %s | claw px %d" % (v, 1920.0 / max(x1 - x0, 1), LAB[key].split(":")[0], npx), (10, 26), 0.6)
            r, cc = divmod(k, 2)
            c[5 + r * (ch + 10):5 + r * (ch + 10) + ch, 6 + cc * (cw + 8):6 + cc * (cw + 8) + cw] = t
        cv2.imwrite(OUT + "/fig3_closeups_%s.png" % key, c)


def fig_tt():
    for key in ["A", "B", "before"]:
        c = canvas()
        cw, ch = 472, 265
        for k, az in enumerate(range(0, 360, 30)):
            t = fit(view_img(key, "tt%d" % az), cw, ch)
            put(t, "az %03d" % az, (8, 24), 0.6)
            r, cc = divmod(k, 4)
            c[60 + r * (ch + 8):60 + r * (ch + 8) + ch, 8 + cc * (cw + 6):8 + cc * (cw + 6) + cw] = t
        put(c, "turntable 12 az, t* = 12 s | " + LAB[key], (12, 40), 0.9)
        cv2.imwrite(OUT + "/fig4_turntable_%s.png" % key, c)


def main():
    os.makedirs(OUT, exist_ok=True)
    fig_painting()
    fig_views()
    fig_closeups()
    fig_tt()
    print("AS02_SHEETS", sorted(f for f in os.listdir(OUT) if f.startswith("fig")))


if __name__ == "__main__":
    main()
