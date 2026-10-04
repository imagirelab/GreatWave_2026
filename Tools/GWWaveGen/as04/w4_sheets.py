# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4：別の波（④）の確かめの図（日本語の見出し）。
図 1：原画視点の ④ の所の拡大（原画 | 別の波あり AS04 | 別の波なし AS04 | 粘土）と全体。
図 2：視点ごと（原画・座席・左の側面・右の側面・真上・後ろ 65°）に、粘土（別の波は青）| AS04 別の波あり | AS04 別の波なし。
図 3：別の波のある所の拡大（左の側面・後ろ 65°・真上）。
入力：Build/Polish/sample04/wave4/render/<名前>/views（Unity の PC の描画。HMD ではない）と check/<名前>/clay_*.png（numpy の z バッファ）。
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_sheets.py [名前（既定 final）] [別の波なしの描画の名前かフォルダー（既定 final_nowave4）] [図の名前の後ろに付ける字（既定なし）] [主役波の説明（見出し）]
"""
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import w4_common as W

S = W.S
FONT = "C:/Windows/Fonts/meiryo.ttc"
FONTB = "C:/Windows/Fonts/meiryob.ttc"
VJA = {"painting": "原画視点", "seat": "座席", "side_left": "左の側面", "side_right": "右の側面", "top": "真上", "back65": "後ろ 65°",
       "seat_toward_wave": "座席から波の方向"}


def font(n, b=False):
    return ImageFont.truetype(FONTB if b else FONT, n)


def plate():
    pim = cv2.imread(S.PAINT)
    M = np.array([[S.A_DISP, 0, 0.5 * S.A_DISP - 0.5 + S.OFFX], [0, S.A_DISP, 0.5 * S.A_DISP - 0.5]], np.float32)
    return cv2.warpAffine(pim, M, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(250, 250, 250))[..., ::-1]


def rdir(nm):
    """描画のフォルダー：名前だけなら wave4/render/<名前>、パスならそのまま。"""
    return nm if ("/" in nm or ":" in nm) else W.OUT + "/render/" + nm


def rgb(p, size=None):
    im = cv2.imread(p)
    if im is None:
        im = np.full((1080, 1920, 3), 200, np.uint8)
    im = im[..., ::-1]
    if size:
        im = cv2.resize(im, size, interpolation=cv2.INTER_AREA)
    return im


def put(canvas, img, x, y):
    canvas.paste(Image.fromarray(img), (x, y))


def seg78(img, x0, y0, sc, col=(255, 120, 0)):
    seg = S.outline_segments()["78"]
    pts = ((S.ref_to_disp(seg) - [x0, y0]) * sc).astype(np.int32)
    out = img.copy()
    cv2.polylines(out, [pts.reshape(-1, 1, 2)], False, col, 1, cv2.LINE_AA)
    return out


def sheet1(name):
    R = rdir(name) + "/views/painting_t120_clawfree.png"
    R0 = rdir(NOW) + "/views/painting_t120_clawfree.png"
    CL = W.OUT + "/check/" + name + "/clay_painting.png"
    x0, x1, y0, y1, sc = 0, 520, 300, 520, 1.8
    pl = plate()
    crops = []
    for im in (pl, rgb(R), rgb(R0), rgb(CL, (1920, 1080))):
        c = im[y0:y1, x0:x1]
        c = cv2.resize(c, None, fx=sc, fy=sc, interpolation=cv2.INTER_CUBIC)
        crops.append(seg78(c, x0, y0, sc))
    cw, ch = crops[0].shape[1], crops[0].shape[0]
    Wd = 2 * cw + 60
    full = rgb(R, (Wd // 2 - 30, int((Wd // 2 - 30) * 9 / 16)))
    full0 = rgb(R0, (Wd // 2 - 30, int((Wd // 2 - 30) * 9 / 16)))
    H = 120 + 2 * (ch + 60) + full.shape[0] + 60 + 200
    cv = Image.new("RGB", (Wd, H), (248, 246, 240))
    d = ImageDraw.Draw(cv)
    d.text((20, 14), "見本04 W4：左端の別の小さな青い波（④）— 原画視点の ④ の所", font=font(34, True), fill=(20, 30, 50))
    d.text((20, 64), "橙の線＝原画の輪郭の区間 78（真値）。原画の左の縁は表示の x 157（それより左は原画の画の外）。主役波：" + HERO_JA,
           font=font(19), fill=(60, 60, 60))
    labs = ["原画（表示の画素に合わせた）", "AS04 別の波あり（Unity、爪なし）", "AS04 別の波なし（主役波だけ）", "粘土（numpy。別の波は青、主役波は灰）"]
    for k, (c, lb) in enumerate(zip(crops, labs)):
        x = 20 + (k % 2) * (cw + 20)
        y = 120 + (k // 2) * (ch + 60)
        d.text((x, y), lb, font=font(22, True), fill=(20, 30, 50))
        put(cv, c, x, y + 34)
    y = 120 + 2 * (ch + 60)
    d.text((20, y), "全体：別の波あり", font=font(22, True), fill=(20, 30, 50))
    d.text((Wd // 2 + 10, y), "全体：別の波なし", font=font(22, True), fill=(20, 30, 50))
    put(cv, full, 20, y + 34)
    put(cv, full0, Wd // 2 + 10, y + 34)
    p = W.OUT + "/w4_sheet1_painting_view" + SUF + ".png"
    cv.save(p)
    return p


def sheet2(name):
    views = ["painting", "seat", "side_left", "side_right", "top", "back65"]
    tw, th = 760, 428
    Wd = 20 + 3 * (tw + 16) + 4
    H = 110 + len(views) * (th + 46) + 20
    cv = Image.new("RGB", (Wd, H), (248, 246, 240))
    d = ImageDraw.Draw(cv)
    d.text((20, 12), "見本04 W4：別の波（④）を視点ごとに — 粘土 | AS04 別の波あり | AS04 別の波なし", font=font(32, True), fill=(20, 30, 50))
    d.text((20, 60), "粘土は numpy の z バッファ（青＝別の波、灰＝主役波、淡い色＝近い海）。AS04 は Unity 6000.4.3f1 の PC の描画（t* 12.0 s、爪なし）。HMD では見ていない。主役波：" + HERO_JA,
           font=font(18), fill=(60, 60, 60))
    for i, v in enumerate(views):
        y = 110 + i * (th + 46)
        d.text((20, y), VJA[v], font=font(22, True), fill=(20, 30, 50))
        ims = [rgb(W.OUT + "/check/" + name + "/clay_%s.png" % v, (tw, th)),
               rgb(rdir(name) + "/views/%s_t120_clawfree.png" % v, (tw, th)),
               rgb(rdir(NOW) + "/views/%s_t120_clawfree.png" % v, (tw, th))]
        for k, im in enumerate(ims):
            put(cv, im, 20 + k * (tw + 16), y + 32)
    p = W.OUT + "/w4_sheet2_views" + SUF + ".png"
    cv.save(p)
    return p


def sheet3(name):
    """図 3：別の波のある所の拡大（左の側面・後ろ 65°・真上）。AS04 別の波あり | なし。"""
    spec = [("side_left", (560, 330, 1400, 760)), ("back65", (1000, 380, 1840, 810)), ("top", (620, 380, 1460, 810))]
    tw, th = 840, 430
    Wd = 20 + 2 * (tw + 16) + 4
    H = 110 + len(spec) * (th + 46) + 20
    cv = Image.new("RGB", (Wd, H), (248, 246, 240))
    d = ImageDraw.Draw(cv)
    d.text((20, 12), "見本04 W4：別の波のある所の拡大 — AS04 別の波あり | 別の波なし", font=font(32, True), fill=(20, 30, 50))
    d.text((20, 60), "Unity の PC の描画（表示の画素 1920×1080 の切り出し、等倍）。爪なし。主役波：" + HERO_JA, font=font(18), fill=(60, 60, 60))
    for i, (v, (x0, y0, x1, y1)) in enumerate(spec):
        y = 110 + i * (th + 46)
        d.text((20, y), VJA[v], font=font(22, True), fill=(20, 30, 50))
        for k, nm in enumerate((name, NOW)):
            im = rgb(rdir(nm) + "/views/%s_t120_clawfree.png" % v)[y0:y1, x0:x1]
            put(cv, np.ascontiguousarray(im), 20 + k * (tw + 16), y + 32)
    p = W.OUT + "/w4_sheet3_zoom" + SUF + ".png"
    cv.save(p)
    return p


NOW = "final_nowave4"
SUF = ""
HERO_JA = "計画 (b) の仮の主役波（形を作る側の本物ではない。外殻の線なし）"

if __name__ == "__main__":
    nm = sys.argv[1] if len(sys.argv) > 1 else "final"
    if len(sys.argv) > 2:
        NOW = sys.argv[2]
    if len(sys.argv) > 3:
        SUF = sys.argv[3]
    if len(sys.argv) > 4:
        HERO_JA = sys.argv[4]
    print(sheet1(nm))
    print(sheet2(nm))
    print(sheet3(nm))
