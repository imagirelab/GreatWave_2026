# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：彫りの面とシェーダー 2 つの図（1920×1080、日本語の見出し）。写真・写真から作った画像は入れない。
入力：surface/render/B2_<版>_flat・B2_<版>_sculpt（AS03SurfRender。既定の版 v9）、見本02 の描画（調べ S3 の study/render/S3_AS02C・S3_AS02C_crest2、同じカメラ）、
surface/render/B2_claws_*・B2_crowntest_*・B2_kp2_sculpt、測り（surface/measure/*.json）、メッシュの report。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_sheets.py [版 v9]"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402

R = S.OUT + "/render"
ST = S.S03 + "/study/render"
OD = S.OUT + "/sheets"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v9"   # 描画の版（surface/render/B2_<版>_flat・_sculpt）
W, H = 1920, 1080
BG = (24, 26, 30)
FG = (236, 236, 236)
AC = (255, 196, 92)


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msyh%s.ttc" % ("bd" if bold else "")):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def load(p, w, h, crop=None):
    im = Image.open(p).convert("RGB")
    if crop:
        im = im.crop(crop)
    return im.resize((w, h), Image.LANCZOS)


def sheet(title, note=None):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 14), title, font=font(30, True), fill=FG)
    if note:
        y = H - 30 * len(note) - 10
        for ln in note:
            d.text((24, y), ln, font=font(19), fill=(200, 200, 200)); y += 30
    return im, d


def grid(im, d, rows, cols, tiles, x0=24, y0=70, tw=None, th=None, gap=10, rowlab=None, collab=None, labw=0):
    tw = tw or (W - x0 - 24 - labw - gap * (len(cols) - 1)) // len(cols)
    th = th or tw * 9 // 16
    yy = y0
    if collab:
        for j, c in enumerate(cols):
            d.text((x0 + labw + j * (tw + gap), yy), c, font=font(20, True), fill=AC)
        yy += 30
    for i, r in enumerate(rows):
        if rowlab:
            d.text((x0, yy + th // 2 - 12), r, font=font(20, True), fill=AC)
        for j, c in enumerate(cols):
            p = tiles.get((i, j))
            if p and (isinstance(p, tuple) or os.path.exists(p)):
                src, crop = (p if isinstance(p, tuple) else (p, None))
                if os.path.exists(src):
                    im.paste(load(src, tw, th, crop), (x0 + labw + j * (tw + gap), yy))
        yy += th + gap
    return yy


def main():
    os.makedirs(OD, exist_ok=True)
    rows = ["見本02（前）", "FLAT（平らな色）", "SCULPT（艶と陰）"]
    dirs = [ST + "/S3_AS02C", R + "/B2_%s_flat" % TAG, R + "/B2_%s_sculpt" % TAG]
    # 1. 主な 3 視点
    vs = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向")]
    im, d = sheet("美術の見本03 B2：彫りの面とシェーダー 2 つ（主役波の面だけ、冠なし）｜t* = 12 s｜主な 3 視点",
                  ["白の境は B1 の共有の白の印 v2（冠の地と垂れる舌）。稜は S1 の数（周期 0.035〜0.056 H、溝の幅／周期 0.244、山と谷 0.12 × 周期）を本当の凹凸として刻んだ静止のメッシュ。",
                   "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。原画カメラの投影は使わない。見本02 は調べ S3 の同じカメラの描画。"])
    t = {(i, j): dirs[i] + "/views/%s_t120_clawfree.png" % v for i in range(3) for j, (v, _) in enumerate(vs)}
    grid(im, d, rows, [x[1] for x in vs], t, rowlab=True, collab=True, labw=210, tw=500, th=281)
    im.save(OD + "/surf_1_views_main.png")
    # 2. ほかの 4 視点
    vs2 = [("side_left", "左の側面"), ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
    im, d = sheet("美術の見本03 B2：ほかの 4 視点（左右の側面・後ろ 65°・真上）",
                  ["SCULPT は白に形の陰と艶、藍の背に映り込み。FLAT は白と淡い水色の 2 段、藍は 2 色の稜。背（白の下の藍）には彫刻のとおり溝を刻まない（S1）。",
                   "PC オフスクリーン描画。HMD 実機ではない。"])
    t = {(i, j): dirs[i] + "/views/%s_t120_clawfree.png" % v for i in range(3) for j, (v, _) in enumerate(vs2)}
    grid(im, d, rows, [x[1] for x in vs2], t, rowlab=True, collab=True, labw=210, tw=405, th=228)
    im.save(OD + "/surf_2_views_other.png")
    # 3. 波頭の回り台（2 枚）
    cdirs = [ST + "/S3_AS02C_crest2", R + "/B2_%s_flat" % TAG, R + "/B2_%s_sculpt" % TAG]
    for part, azs in (("a", [0, 45, 90, 135]), ("b", [180, 225, 270, 315])):
        lab = {0: "0°（原画の向き）", 45: "45°（正面）", 90: "90°", 135: "135°（右の側面）", 180: "180°", 225: "225°（背）", 270: "270°", 315: "315°（左の側面）"}
        im, d = sheet("美術の見本03 B2：波頭の回り台（中心 (−6.63, 16.5, −3.27)、34 m、仰角 5°、画角 35°、主役波だけ）%s" % ("前半" if part == "a" else "後半"),
                      ["冠（B1）はまだ入れていない。頂の上は B1 の白の冠の地（白）だけ。指の冠が入ると輪郭が変わる。",
                       "PC オフスクリーン描画。HMD 実機ではない。"])
        t = {(i, j): cdirs[i] + "/crest/t120_az%03d_clawfree.png" % az for i in range(3) for j, az in enumerate(azs)}
        grid(im, d, rows, [lab[a] for a in azs], t, rowlab=True, collab=True, labw=210, tw=405, th=228)
        im.save(OD + "/surf_3%s_crest.png" % part)
    # 4. 近く
    im, d = sheet("美術の見本03 B2：面の近く（稜の断面と艶）",
                  ["上：原画視点の管の中の切り出し。下：座席から波の方向の切り出し。左から 見本02｜FLAT｜SCULPT。",
                   "下の図：稜の断面（S1 の数から作った式。白い線が藍の稜、青い線が溝の淡い水色）。"])
    crops = [((620, 300, 1180, 620)), ((300, 100, 1500, 775))]
    t = {}
    for j in range(3):
        t[(0, j)] = (dirs[j] + "/views/painting_t120_clawfree.png", crops[0])
        t[(1, j)] = (dirs[j] + "/views/seat_toward_wave_t120_clawfree.png", crops[1])
    grid(im, d, ["原画視点", "座席から波"], ["見本02（前）", "FLAT", "SCULPT"], t, rowlab=True, collab=True, labw=150, tw=520, th=300)
    # 断面の図（実寸と、縦を 4 倍にしたもの）
    meta = S.jload(S.META)
    gp = S.GrooveParams(float(meta["frame"]["H0_m"]), S.jload(S.SPEC))
    lam = float(gp.lam(0.5 * gp.H0))
    q = np.linspace(-1.5, 1.5, 1201)
    h, dd, gh, km, G = S.groove_h(q, np.zeros_like(q), np.ones_like(q) / lam, lam, gp.depth_over_period * lam, gp.gfrac, gp.bead, gp.pexp, gp.lod)
    for k, (ex, lab_) in enumerate(((1.0, "実寸"), (4.0, "縦を 4 倍"))):
        x0, y0, pw = 180 + k * 820, (800 if k == 0 else 880), 700
        sc = pw / (3.0 * lam)                     # 画素／m
        xs = x0 + (q + 1.5) * lam * sc
        ys = y0 - h * sc * ex
        pts = list(zip(xs.tolist(), ys.tolist()))
        for i in range(len(pts) - 1):
            col = (90, 140, 210) if dd[i] < gh else (225, 225, 225)
            d.line([pts[i], pts[i + 1]], fill=col, width=4)
        d.text((x0, 905) if k == 0 else (x0, 780), "稜の断面（%s）" % lab_, font=font(18, True), fill=AC)
    d.text((180, 940), "周期 %.2f m（0.5 H の高さ）・山と谷 %.2f m（周期の %.2f）・溝の淡い水色の幅 %.2f m（周期の %.3f）・溝の中に細い玉縁（深さの %.2f）・稜は超楕円（指数 %.1f）" %
           (lam, gp.depth_over_period * lam, gp.depth_over_period, gp.gfrac * lam, gp.gfrac, gp.bead, gp.pexp), font=font(18), fill=FG)
    im.save(OD + "/surf_4_closeups.png")
    # 6. ほかのメッシュ・道
    im, d = sheet("美術の見本03 B2：同じシェーダーが爪・冠・keypose の主役波にも効くことの確かめ",
                  ["上：見本02 の爪 83 本に AS03 の材質（_AS03Src = 2、法線は t* で計算し直し、爪の縁の線なし）。中：B1 の冠（作業中の版）を -as03Crown で置いた。",
                   "下：keypose の主役波（_AS03Src = 0、形成の動きでも使える道。稜は画素の傾きだけ、白は B1 の白の印を属性 C.w に入れた）。PC オフスクリーン描画。"])
    t = {(0, 0): R + "/B2_claws_Flat_%s/views/painting_t120_claws.png" % TAG, (0, 1): R + "/B2_claws_Sculpt_%s/views/painting_t120_claws.png" % TAG, (0, 2): R + "/B2_claws_Sculpt_%s/views/seat_t120_claws.png" % TAG,
         (1, 0): R + "/B2_crowntest_flat_%s/views/painting_t120_clawfree.png" % TAG, (1, 1): R + "/B2_crowntest_sculpt_%s/views/painting_t120_clawfree.png" % TAG, (1, 2): R + "/B2_crowntest_sculpt_%s/crest/t120_az045_clawfree.png" % TAG,
         (2, 0): R + "/B2_kp_%s/views/painting_t120_clawfree.png" % TAG, (2, 1): R + "/B2_kp_%s/views/seat_toward_wave_t120_clawfree.png" % TAG, (2, 2): R + "/B2_kp_%s/views/back65_t120_clawfree.png" % TAG}
    grid(im, d, ["爪（FLAT・SCULPT）", "B1 の冠", "keypose の道"], ["左", "中", "右"], t, rowlab=True, collab=False, labw=230, tw=490, th=275)
    im.save(OD + "/surf_6_other_meshes.png")
    print("ok", sorted(os.listdir(OD)))


if __name__ == "__main__":
    main()
