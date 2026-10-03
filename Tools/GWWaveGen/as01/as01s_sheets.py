# -*- coding: utf-8 -*-
"""美術の見本01（Q29）組み立て：見本 A・B（面の模様 A／B ＋ 爪の部の爪）の並べ図（PIL・OpenCV。Unity の描画を並べるだけ）。

入力（Git 対象外。as01s_run_render.sh の出力と各部の final）：
  Build/Polish/sample01/assemble/A・B/        views（7 視点、t 12 s、爪あり・飛沫なし _claws／爪なし _clawfree）、tt（12 方位、爪あり）
  Build/Polish/sample01/texA/final・texB/final  t 10.5 s の爪なし（爪は t* の 1 コマの静止の見本なので、10.5 s は面の模様だけ）
  Build/Polish/sample01/claws/before_33r01/   前（採用の仕上げ33修正01 の爪＋PL29 の面、飛沫なし）
  Tools/PaintingTruth/build/painting_display.png  原画（原画視点の枠）
出力（Build/Polish/sample01/assemble/sheets/）：
  view_<視点>.png   [原画 | 見本 A | 見本 B]、上の段 t*（爪あり）、下の段 t 10.5 s（爪なし）
  zoom_crest_lip.png 原画視点の頂と唇の切り出し 3 つ [原画 | A | B]（同じ画面の枠）
  tt.png            回り台 12 方位（前・A・B の 3 つの塊、頂と唇の所を切り出し）
  ba_views.png      前後（[前 | A | B]、7 視点、頂と唇の所を切り出し、t*）
  --internal で、彫刻の写真を足した図（美術監督の確認用。Build/Polish/sample01/internal/。Git に入れない・リポジトリに写さない）
使い方：py -3.10 -B Tools/GWWaveGen/as01/as01s_sheets.py [--internal]
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

REPO = "G:/Unity/GreatWave_2026_Fresh"
S01 = REPO + "/Unity/Build/Polish/sample01"
AS = S01 + "/assemble"
PAINT = REPO + "/Tools/PaintingTruth/build/painting_display.png"
PHOTOS = "G:/research/reality scan/北斋参考"
FONT = "C:/Windows/Fonts/meiryo.ttc"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
from claws_sheet import BOX  # noqa: E402  頂と唇の帯を各視点へ投影した切り出しの枠（爪の部と同じ）

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
VJA = {"painting": "原画視点", "seat": "座席", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面", "side_right": "右の側面",
       "back65": "後ろ 65°", "top": "真上"}
LAB_A = "見本 A：彫刻のような刻み（a7）＋爪"
LAB_B = "見本 B：原画のような舌形（c9）＋爪"
LAB_P = "原画"
LAB_0 = "前：採用（PL29 の面＋仕上げ33修正01 の爪）"
# 回 0（既定）と改善の回 1（--round r1）で替える：t* の描画、t 10.5 s の描画、見出し
CFG = dict(A=AS + "/A", B=AS + "/B", A105=S01 + "/texA/final", B105=S01 + "/texB/final", out=AS + "/sheets", tag="組み立て")
# 原画視点の切り出し（表示の画素 x0, y0, x1, y1。16:9）：頂と唇の全体・唇の先・上側の爪の輪
ZOOM = [((260, 60, 1220, 600), "頂と唇の全体"), ((800, 180, 1200, 405), "唇の先（巻きの先の爪）"), ((480, 60, 960, 330), "頂の上側の爪の輪")]
# 美術監督の確認用：彫刻の写真と、向きの近い描画（目安。写真は縮めて図に貼るだけで、形・画像をリポジトリに入れない）
INTERNAL = [("正面图.jpg", "painting", "正面 ↔ 原画視点"), ("左45.jpg", "tt30", "左 45° ↔ 回り台 30°"), ("左图.jpg", "tt0", "左 ↔ 回り台 0°"),
            ("右图.jpg", "side_left", "右 ↔ 左の側面（白い背と頂の指）"), ("右45.jpg", "tt300", "右 45° ↔ 回り台 300°"),
            ("背图.jpg", "back65", "背 ↔ 後ろ 65°"), ("顶图、.jpg", "top", "上 ↔ 真上")]


def font(n):
    return ImageFont.truetype(FONT, n)


def rgb(path):
    im = cv2.imread(path)
    if im is None:
        raise FileNotFoundError(path)
    return Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))


def fit(im, w, h, box=None):
    if box is not None:
        im = im.crop(box)
    return im.resize((w, h), Image.LANCZOS)


def fitc(im, w, h, box=None, bg=(24, 24, 24)):
    """縦横の比を保って w × h の中に収める（余りは暗い地）。"""
    if box is not None:
        im = im.crop(box)
    k = min(w / im.width, h / im.height)
    r = im.resize((max(1, int(round(im.width * k))), max(1, int(round(im.height * k)))), Image.LANCZOS)
    out = Image.new("RGB", (w, h), bg)
    out.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return out


def label(img, xy, text, size=24):
    d = ImageDraw.Draw(img)
    f = font(size)
    x, y = xy
    tw = d.textlength(text, font=f)
    d.rectangle([x, y, x + tw + 12, y + size + 10], fill=(0, 0, 0))
    d.text((x + 6, y + 3), text, font=f, fill=(255, 255, 255))


def header(w, text, h=56, size=28):
    im = Image.new("RGB", (w, h), (24, 24, 24))
    ImageDraw.Draw(im).text((12, (h - size) // 2 - 2), text, font=font(size), fill=(255, 255, 255))
    return im


def stack(parts, w):
    H = sum(p.height for p in parts)
    out = Image.new("RGB", (w, H), (24, 24, 24))
    y = 0
    for p in parts:
        out.paste(p, (0, y))
        y += p.height
    return out


def row(tiles, gap=0):
    w = sum(t.width for t in tiles) + gap * (len(tiles) - 1)
    h = max(t.height for t in tiles)
    out = Image.new("RGB", (w, h), (24, 24, 24))
    x = 0
    for t in tiles:
        out.paste(t, (x, 0))
        x += t.width + gap
    return out


def vpath(root, v, ts, kind):
    if v.startswith("tt"):
        return "%s/tt/%s_az%03d_%s.png" % (root, ts, int(v[2:]), kind)
    return "%s/views/%s_%s_%s.png" % (root, v, ts, kind)


def view_sheets(out):
    P = rgb(PAINT)
    W, H = 960, 540
    for v in VIEWS:
        pl = LAB_P + ("（原画視点の枠）" if v == "painting" else "（参考。視点は違う）")
        r1 = row([fit(P, W, H), fit(rgb(vpath(CFG["A"], v, "t120", "claws")), W, H), fit(rgb(vpath(CFG["B"], v, "t120", "claws")), W, H)], 0)
        r2 = row([fit(P, W, H), fit(rgb(vpath(CFG["A105"], v, "t105", "clawfree")), W, H), fit(rgb(vpath(CFG["B105"], v, "t105", "clawfree")), W, H)], 0)
        for r, t in ((r1, "t* = 12 s・爪あり"), (r2, "t 10.5 s・爪なし")):
            for k, lb in enumerate([pl, LAB_A, LAB_B]):
                if k and r is r2:
                    lb = lb.replace("＋爪 v14", "").replace("＋爪 v15", "").replace("＋爪", "")
                label(r, (k * W + 8, 8), lb if k == 0 else lb + "｜" + t)
        sheet = stack([header(3 * W, "美術の見本01・" + CFG["tag"] + "｜%s｜上：t* = 12 s（爪あり・飛沫なし）　下：t 10.5 s（爪なし。爪は t* の 1 コマの静止の見本）" % VJA[v]), r1, r2], 3 * W)
        sheet.save(os.path.join(out, "view_%s.png" % v))
        print("SHEET", "view_" + v, sheet.size)


def zoom_sheet(out):
    P = rgb(PAINT)
    A = rgb(vpath(CFG["A"], "painting", "t120", "claws"))
    B = rgb(vpath(CFG["B"], "painting", "t120", "claws"))
    W, H = 640, 360
    rows = [header(3 * W, "美術の見本01・" + CFG["tag"] + "｜原画視点の頂と唇の切り出し（同じ画面の枠）｜t* = 12 s・爪あり・飛沫なし", 48, 24)]
    for box, name in ZOOM:
        r = row([fit(P, W, H, box), fit(A, W, H, box), fit(B, W, H, box)])
        for k, lb in enumerate([LAB_P + "｜" + name, "見本 A（刻み）", "見本 B（舌形）"]):
            label(r, (k * W + 6, 6), lb, 20)
        rows.append(r)
    sheet = stack(rows, 3 * W)
    sheet.save(os.path.join(out, "zoom_crest_lip.png"))
    print("SHEET zoom_crest_lip", sheet.size)


def tt_sheet(out):
    W, H = 480, 270
    blocks = [header(4 * W, "美術の見本01・" + CFG["tag"] + "｜回り台 12 方位（72 m、頂と唇の所を切り出し）｜t* = 12 s・爪あり・飛沫なし", 48, 24)]
    for root, lb in ((S01 + "/claws/before_33r01", LAB_0), (CFG["A"], LAB_A), (CFG["B"], LAB_B)):
        blocks.append(header(4 * W, lb, 40, 22))
        tiles = []
        for az in range(0, 360, 30):
            t = fit(rgb(vpath(root, "tt%d" % az, "t120", "claws")), W, H, tuple(BOX["tt%d" % az]))
            label(t, (4, 4), "%d°" % az, 18)
            tiles.append(t)
        for k in range(0, 12, 4):
            blocks.append(row(tiles[k:k + 4]))
    sheet = stack(blocks, 4 * W)
    sheet.save(os.path.join(out, "tt.png"))
    print("SHEET tt", sheet.size)


def ba_sheet(out):
    W, H = 640, 360
    rows = [header(3 * W, "美術の見本01・" + CFG["tag"] + "｜前後（同じ視点・同じ時刻 t* = 12 s、爪あり・飛沫なし、頂と唇の所を切り出し）", 48, 22)]
    for v in VIEWS:
        r = row([fit(rgb(vpath(root, v, "t120", "claws")), W, H, tuple(BOX[v])) for root in (S01 + "/claws/before_33r01", CFG["A"], CFG["B"])])
        for k, lb in enumerate(["前（採用）", "見本 A（刻み）", "見本 B（舌形）"]):
            label(r, (k * W + 6, 6), VJA[v] + "｜" + lb, 20)
        rows.append(r)
    sheet = stack(rows, 3 * W)
    sheet.save(os.path.join(out, "ba_views.png"))
    print("SHEET ba_views", sheet.size)


# 改善の回の前後の図：前の回（PREV）と今の回（CUR、描画は CFG）。回 1 は 回 0 → 回 1、回 2 は 回 1 → 回 2
PREV = dict(A=AS + "/A", B=AS + "/B", A105=S01 + "/texA/final", B105=S01 + "/texB/final", n="回 0",
            labA="A 回 0（a7＋v13b）", labB="B 回 0（c9＋v13b）")
CUR = dict(n="回 1", labA="A 回 1（a8＋v14）", labB="B 回 1（d1＋v14）")


def round_sheets(out):
    """改善の回：前の回と今の回の前後。同じ視点・同じ時刻。t* は爪あり（頂と唇の所を切り出し）、t 10.5 s は爪なし（全体）。"""
    W, H = 640, 360
    tag = "%s → %s" % (PREV["n"], CUR["n"])
    for ts, kind, crop, name in (("t120", "claws", True, "ba_round_t120.png"), ("t105", "clawfree", False, "ba_round_t105.png")):
        rows = [header(4 * W, "美術の見本01・" + CFG["tag"] + "｜前後（%s、同じ視点・同じ時刻 %s、%s）" % (tag, "t* = 12 s" if ts == "t120" else "t 10.5 s", "爪あり・飛沫なし、頂と唇の所を切り出し" if crop else "爪なし"), 48, 22)]
        r0A, r0B = (PREV["A"], PREV["B"]) if ts == "t120" else (PREV["A105"], PREV["B105"])
        r1A, r1B = (CFG["A"], CFG["B"]) if ts == "t120" else (CFG["A105"], CFG["B105"])
        for v in VIEWS:
            r = row([fit(rgb(vpath(root, v, ts, kind)), W, H, tuple(BOX[v]) if crop else None) for root in (r0A, r1A, r0B, r1B)])
            for k, lb in enumerate([PREV["labA"], CUR["labA"], PREV["labB"], CUR["labB"]]):
                label(r, (k * W + 6, 6), VJA[v] + "｜" + lb, 20)
            rows.append(r)
        sheet = stack(rows, 4 * W)
        sheet.save(os.path.join(out, name))
        print("SHEET", name, sheet.size)
    # 回り台（t*、爪あり）：前の回と今の回
    W2, H2 = 480, 270
    blocks = [header(4 * W2, "美術の見本01・" + CFG["tag"] + "｜回り台 12 方位の前後（%s、t* = 12 s・爪あり・飛沫なし）" % tag, 48, 22)]
    for root, lb in ((PREV["A"], PREV["labA"]), (CFG["A"], CUR["labA"]), (PREV["B"], PREV["labB"]), (CFG["B"], CUR["labB"])):
        blocks.append(header(4 * W2, lb, 36, 20))
        tiles = []
        for az in range(0, 360, 30):
            t = fit(rgb(vpath(root, "tt%d" % az, "t120", "claws")), W2, H2, tuple(BOX["tt%d" % az]))
            label(t, (4, 4), "%d°" % az, 18)
            tiles.append(t)
        for k in range(0, 12, 4):
            blocks.append(row(tiles[k:k + 4]))
    sheet = stack(blocks, 4 * W2)
    sheet.save(os.path.join(out, "ba_round_tt.png"))
    print("SHEET ba_round_tt", sheet.size)


def user_sheets(out):
    """改善の回 2：利用者に見せる 1920×1080 の図（Docs/Evidence/ArtSample01 へ写す元）。彫刻の写真は使わない（原画は原画視点の枠の表示だけ）。
    us1_painting_view：原画｜A｜B（原画視点、t* 爪あり）を上、頂と唇の切り出しを下。
    us2_views_t120：6 視点（座席・座席から波・左右の側面・後ろ 65°・真上）× A・B（t* 爪あり、頂と唇の所）。
    us3_tt_A・us3_tt_B：回り台 12 方位（t* 爪あり）。us3_tt_AB：A と B を 1 枚に（小さめ）。
    us4_rounds：前（採用）｜回 0｜回 1｜回 2 の原画視点の頂と唇（A の上の段、B の下の段）。
    us5_t105：t 10.5 s・爪なしの 4 視点（原画視点・左の側面・後ろ 65°・真上、主役波の所を切り出し）× A・B（面の模様だけを比べる）。
    us6_seat_vs_outline：座席の頂の指と原画視点の輪郭の両立しない所（回 0 の A と回 2 の A、原画視点の赤＝原画の空へ出た爪の画素）。"""
    W0, H0 = 1920, 1080
    P = rgb(PAINT)
    A = rgb(vpath(CFG["A"], "painting", "t120", "claws"))
    B = rgb(vpath(CFG["B"], "painting", "t120", "claws"))
    hd = 48
    # us1（下の段の切り出しは 640 × 672 の比に合わせた枠：頂と唇の全体）
    zbox = (540, 40, 1130, 660)
    top = row([fit(P, 640, 360), fit(A, 640, 360), fit(B, 640, 360)])
    for k, lb in enumerate(["原画（原画視点の枠）", LAB_A, LAB_B]):
        label(top, (k * 640 + 6, 6), lb, 18)
    zh = H0 - hd - 360
    bot = row([fit(P, 640, zh, zbox), fit(A, 640, zh, zbox), fit(B, 640, zh, zbox)])
    for k, lb in enumerate(["原画｜頂と唇", "見本 A（刻み）｜頂と唇", "見本 B（舌形）｜頂と唇"]):
        label(bot, (k * 640 + 6, 6), lb, 18)
    stack([header(W0, "美術の見本01（回 2）｜原画視点 t* = 12 s・爪あり・飛沫なし｜上：全体　下：頂と唇の切り出し（同じ枠）", hd, 24), top, bot], W0).save(os.path.join(out, "us1_painting_view.png"))
    # us2
    vv = ["seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    tw, th = 640, (H0 - hd - 2 * 34) // 4
    rows_ = [header(W0, "美術の見本01（回 2）｜6 視点 × 見本 A・B（t* = 12 s・爪あり・飛沫なし、頂と唇の所を切り出し）", hd, 24)]
    for root, lb in ((CFG["A"], LAB_A), (CFG["B"], LAB_B)):
        rows_.append(header(W0, lb, 34, 20))
        tiles = []
        for v in vv:
            t = fitc(rgb(vpath(root, v, "t120", "claws")), tw, th, tuple(BOX[v]))
            label(t, (4, 4), VJA[v], 16)
            tiles.append(t)
        rows_.append(row(tiles[:3]))
        rows_.append(row(tiles[3:]))
    stack(rows_, W0).save(os.path.join(out, "us2_views_t120.png"))
    # us3
    for key, lb in (("A", LAB_A), ("B", LAB_B)):
        tw, th = 480, (H0 - hd) // 3
        rows_ = [header(W0, "美術の見本01（回 2）｜回り台 12 方位（72 m、t* = 12 s・爪あり・飛沫なし）｜" + lb, hd, 24)]
        tiles = []
        for az in range(0, 360, 30):
            t = fitc(rgb(vpath(CFG[key], "tt%d" % az, "t120", "claws")), tw, th, tuple(BOX["tt%d" % az]))
            label(t, (4, 4), "%d°" % az, 18)
            tiles.append(t)
        for k in range(0, 12, 4):
            rows_.append(row(tiles[k:k + 4]))
        stack(rows_, W0).save(os.path.join(out, "us3_tt_%s.png" % key))
    # us3_tt_AB：A と B の回り台 12 方位を 1 枚に（各 6 列 × 2 段）
    tw, th = 320, (H0 - hd - 2 * 30) // 4
    rows_ = [header(W0, "美術の見本01（回 2）｜回り台 12 方位（72 m、t* = 12 s・爪あり・飛沫なし、頂と唇の所を切り出し）｜上：見本 A　下：見本 B", hd, 22)]
    for key, lb in (("A", LAB_A), ("B", LAB_B)):
        rows_.append(header(W0, lb, 30, 18))
        tiles = []
        for az in range(0, 360, 30):
            t = fitc(rgb(vpath(CFG[key], "tt%d" % az, "t120", "claws")), tw, th, tuple(BOX["tt%d" % az]))
            label(t, (4, 4), "%d°" % az, 16)
            tiles.append(t)
        rows_.append(row(tiles[:6]))
        rows_.append(row(tiles[6:]))
    stack(rows_, W0).save(os.path.join(out, "us3_tt_AB.png"))
    # us4
    tw, th = 480, (H0 - hd - 2 * 34) // 2
    rows_ = [header(W0, "美術の見本01｜爪の回ごとの前後（原画視点の頂と唇、t* = 12 s・爪あり・飛沫なし、同じ枠）", hd, 24)]
    for key, lb, r0, r1 in (("A", "見本 A（刻み）", AS + "/A", AS + "/A1"), ("B", "見本 B（舌形）", AS + "/B", AS + "/B1")):
        rows_.append(header(W0, lb + "｜左から：前（採用の仕上げ33修正01）・回 0（爪 v13b）・回 1（爪 v14）・回 2（爪 v15）", 34, 20))
        tiles = []
        for root, l2 in ((S01 + "/claws/before_33r01", "前（採用）"), (r0, "回 0"), (r1, "回 1"), (CFG[key], "回 2")):
            t = fit(rgb(vpath(root, "painting", "t120", "claws")), tw, th, (560, 50, 1120, 612))
            label(t, (4, 4), l2, 18)
            tiles.append(t)
        rows_.append(row(tiles))
    stack(rows_, W0).save(os.path.join(out, "us4_rounds.png"))
    # us5
    vv = ["painting", "side_left", "back65", "top"]
    # t 10.5 s の主役波の所の切り出し（t* の BOX とは位置が違うので、この図だけの枠。表示の画素）
    B105 = {"painting": (0, 100, 840, 940), "side_left": (560, 200, 1500, 1000), "back65": (640, 150, 1760, 1000), "top": (400, 150, 1300, 950)}
    tw, th = 480, (H0 - hd - 2 * 34) // 2
    rows_ = [header(W0, "美術の見本01（回 2）｜t 10.5 s・爪なし（面の模様だけ）｜4 視点 × 見本 A・B", hd, 24)]
    for key, lb in (("A105", LAB_A.split("＋")[0]), ("B105", LAB_B.split("＋")[0])):
        rows_.append(header(W0, lb, 34, 20))
        tiles = []
        for v in vv:
            t = fitc(rgb(vpath(CFG[key], v, "t105", "clawfree")), tw, th, B105[v])
            label(t, (4, 4), VJA[v], 18)
            tiles.append(t)
        rows_.append(row(tiles))
    stack(rows_, W0).save(os.path.join(out, "us5_t105.png"))
    # us6：座席の頂の指と原画視点の輪郭の両立しない所（回 0 の A ↔ 回 2 の A2）。上：座席（全体）、下：原画視点の頂と唇（赤＝爪が原画の空へ出た画素）
    sky = cv2.imread(REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png", cv2.IMREAD_UNCHANGED).astype(np.float64) / 65535.0 > 0.5
    tw, th = 960, (H0 - hd - 2 * 34) // 2
    tiles_s, tiles_p = [], []
    for root, l2 in ((AS + "/A", "回 0（A＋爪 v13b）"), (CFG["A"], "回 2（A＋爪 v15）")):
        t = fitc(rgb(vpath(root, "seat", "t120", "claws")), tw // 1, th)
        label(t, (4, 4), "座席｜" + l2, 18)
        tiles_s.append(t)
        a = cv2.imread(vpath(root, "painting", "t120", "claws")).astype(int)
        b = cv2.imread(vpath(root, "painting", "t120", "clawfree")).astype(int)
        cl = np.abs(a - b).sum(2) > 40
        out_ = cl & sky
        im = cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_BGR2RGB)
        im[cv2.dilate(out_.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0] = (230, 30, 30)
        t = fitc(Image.fromarray(im), tw, th, (260, 40, 1220, 580))
        label(t, (4, 4), "原画視点｜%s｜赤＝爪が原画の空へ出た所（約 %s 画素）" % (l2, format(int(round(out_.sum(), -2)), ",")), 18)
        tiles_p.append(t)
    rows_ = [header(W0, "美術の見本01｜座席で頂の指を見せるか、原画視点の輪郭を守るか（同じ向きの 2 つのカメラ。t* = 12 s・爪あり・飛沫なし）", hd, 22),
             header(W0, "座席（主な VR の視点）：回 0 は頂に白い角が立つ ／ 回 2 は頂の上に白い泡の塊だけ", 34, 20), row(tiles_s),
             header(W0, "原画視点：回 0 はその角が原画の空へ出て形の関門 3 つが通らない ／ 回 2 は通る", 34, 20), row(tiles_p)]
    stack(rows_, W0).save(os.path.join(out, "us6_seat_vs_outline.png"))
    for f in ("us1_painting_view", "us2_views_t120", "us3_tt_A", "us3_tt_B", "us3_tt_AB", "us4_rounds", "us5_t105", "us6_seat_vs_outline"):
        print("SHEET", f, Image.open(os.path.join(out, f + ".png")).size)


def internal_sheet(out):
    # 美術監督の確認用だけ（Git 対象外の Build/Polish/sample01/internal/）。写真は縮めて貼るだけ（形・画像をリポジトリに入れない）
    W, H = 640, 360
    rows = [header(3 * W, "【内部・美術監督の確認用・外へ出さない】彫刻の写真（参考）と見本 A・B の向きの近い描画（向きは目安）", 48, 22)]
    for fn, v, name in INTERNAL:
        ph = ImageOps.exif_transpose(Image.open(os.path.join(PHOTOS, fn))).convert("RGB")
        pw, phh = ph.size
        ch = int(round(pw * 9 / 16))
        y0 = max(0, (phh - ch) // 2)
        ph = ph.crop((0, y0, pw, y0 + min(ch, phh))).resize((W, H), Image.LANCZOS)
        tiles = [ph]
        for root in (CFG["A"], CFG["B"]):
            tiles.append(fit(rgb(vpath(root, v, "t120", "claws")), W, H, tuple(BOX[v])))
        r = row(tiles)
        for k, lb in enumerate(["彫刻（参考）｜" + name, "見本 A（刻み）", "見本 B（舌形）"]):
            label(r, (k * W + 6, 6), lb, 20)
        rows.append(r)
    sheet = stack(rows, 3 * W)
    sheet.save(os.path.join(out, "internal_sculpture_vs_samples.png"))
    print("SHEET internal", sheet.size)


def internal_sheet_r1(out):
    # 回 1 の内部の図（彫刻の写真と A1・B1）。名前を替えるだけ（回 0 の図は残す）
    src = os.path.join(out, "internal_sculpture_vs_samples.png")
    keep = src + ".r0.png"
    if os.path.exists(src) and not os.path.exists(keep):
        os.replace(src, keep)
    internal_sheet(out)
    os.replace(src, os.path.join(out, "internal_sculpture_vs_samples_r1.png"))
    if os.path.exists(keep):
        os.replace(keep, src)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--internal", action="store_true")
    ap.add_argument("--round", default="r0", help="r1：改善の回 1（A1・B1、t 10.5 s は A1_t105・B1_t105、出力 assemble/sheets_r1）、r2：改善の回 2（A2・B2、出力 assemble/sheets_r2）")
    a = ap.parse_args()
    global LAB_A, LAB_B
    if a.round == "r1":
        CFG.update(A=AS + "/A1", B=AS + "/B1", A105=AS + "/A1_t105", B105=AS + "/B1_t105", out=AS + "/sheets_r1", tag="改善の回 1")
        LAB_A = "見本 A：彫刻のような刻み（a8）＋爪 v14"
        LAB_B = "見本 B：原画のような舌形（d1）＋爪 v14"
    if a.round == "r2":
        # 改善の回 2（2026-10-03）：A2・B2（爪 v15、B は点を戻した d2）。t 10.5 s は A2_t105（A1_t105 と画素で同じ）・B2_t105
        CFG.update(A=AS + "/A2", B=AS + "/B2", A105=AS + "/A2_t105", B105=AS + "/B2_t105", out=AS + "/sheets_r2", tag="改善の回 2")
        PREV.update(A=AS + "/A1", B=AS + "/B1", A105=AS + "/A1_t105", B105=AS + "/B1_t105", n="回 1", labA="A 回 1（a8＋v14）", labB="B 回 1（d1＋v14）")
        CUR.update(n="回 2", labA="A 回 2（a8＋v15）", labB="B 回 2（d2＋v15）")
        LAB_A = "見本 A：彫刻のような刻み（a8）＋爪 v15"
        LAB_B = "見本 B：原画のような舌形（d2）＋爪 v15"
    out = CFG["out"]
    os.makedirs(out, exist_ok=True)
    view_sheets(out)
    zoom_sheet(out)
    tt_sheet(out)
    ba_sheet(out)
    if a.round in ("r1", "r2"):
        round_sheets(out)
    if a.round == "r2":
        user_sheets(out)
    if a.internal:
        io = S01 + "/internal"
        os.makedirs(io, exist_ok=True)
        internal_sheet(io) if a.round == "r0" else internal_sheet_r1(io)


if __name__ == "__main__":
    main()
