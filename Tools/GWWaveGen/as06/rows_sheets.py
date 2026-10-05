# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS）：見本05 B（B10）と段の行（R6b）を並べる図（1920×1080、ラベルは日本語）。
py -3.10 -B Tools/GWWaveGen/as06/rows_sheets.py <新しい描画の名前（R6b）> <粘土の置き場> <出力の置き場>
  rows_1_painting.png   原画視点：原画｜見本05 B｜段の行（Unity、材質 AS05・爪あり。段の行は一艘目の船を相似で手前へ）と左側の拡大
  rows_2_clay.png       色なしの粘土（爪・船なし、numpy）：原画視点・座席・左右の側面・後ろ 65°・真上（見本05 B｜段の行）
  rows_3_tint.png       同じ 6 視点の層の色づけ
  rows_4_turntable_clay.png・rows_5_turntable_tint.png   回り台 12 方位の粘土と層の色づけ
  rows_6_turntable_material.png  Unity の材質の回り台（爪なし）0・30・60・90・270・300・330°
  rows_7_sections.png   断面の並び（rows_diag.py の出力を写す）
原画の色・原画カメラの投影は面へ使わない（並べ図に原画を置くのは見比べのためだけ）。
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_targets as T5  # noqa: E402
import rows_clay as RC  # noqa: E402

S = T5.S
A = T5.A
P = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish"
B10 = P + "/sample05/fix1/assemble/render/B10"
NEW, CLAY, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
RNEW = P + "/sample06/rows/render/" + NEW
os.makedirs(OUT, exist_ok=True)
NJA = {"B10": "見本05 B", NEW: "段の行 " + NEW}
COL = {"r1": (220, 30, 30), "r2": (20, 150, 40), "r3": (0, 150, 190)}


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def label(d, xy, text, sz=18):
    bb = d.textbbox(xy, text, font=font(sz))
    d.rectangle((bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3), fill=(255, 255, 255))
    d.text(xy, text, font=font(sz), fill=(0, 0, 0))


def head(img, title, sub):
    d = ImageDraw.Draw(img)
    d.text((14, 8), title, font=font(30, True), fill=(0, 0, 0))
    y = 50
    for s in sub:
        d.text((14, y), s, font=font(17), fill=(50, 50, 50))
        y += 24
    return d, y + 6


def regions(img_rgb):
    im = Image.fromarray(img_rgb)
    d = ImageDraw.Draw(im)
    for k, c in COL.items():
        pts = [tuple(p) for p in A.ref_to_px(S.REG[k])]
        d.line(pts + [pts[0]], fill=c, width=3)
    return np.array(im)


def sheet_painting():
    img = Image.new("RGB", (1920, 1080), (255, 255, 255))
    d, y0 = head(img, "段の行（B-ROWS）：原画視点（爪あり）　原画｜見本05 B｜段の行 " + NEW,
                 ["線：赤 ① 浪尖・緑 ② b区域・水色 ③ 最左側の小区域（利用者が確かめた範囲）。下の段は左側（②・③）の拡大。",
                  "段の行は Q34 で船を避ける制約を外し、一艘目の船を原画のカメラを中心とする相似で手前へ動かして描いた（倍率 0.6。原画視点の船の画は同じ、ほかの視点では小さくなる）。"])
    pd = T5.painting_disp()
    ims = [("原画", pd), (NJA["B10"], np.array(Image.open(B10 + "/views/painting_t120_claws.png").convert("RGB"))),
           (NJA[NEW], np.array(Image.open(RNEW + "/views/painting_t120_claws.png").convert("RGB")))]
    w, h = 628, 353
    for i, (nm, a) in enumerate(ims):
        x = 8 + i * (w + 8)
        img.paste(Image.fromarray(regions(a)).resize((w, h), Image.LANCZOS), (x, y0))
        label(d, (x + 6, y0 + 6), nm)
        z = Image.fromarray(regions(a)).crop((0, 280, 900, 786)).resize((w, int(w * 506 / 900)), Image.LANCZOS)
        img.paste(z, (x, y0 + h + 12))
        label(d, (x + 6, y0 + h + 18), nm + " ／ 左側の拡大")
    d.text((14, 1048), "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし、波頭の爪なし。美術が届いたかは利用者が決める（Q29・Q30）。",
           font=font(15), fill=(60, 60, 60))
    img.save(OUT + "/rows_1_painting.png")


def sheet_views(views, suffix, fname, title, cols=3):
    kinds = ["B10", NEW]
    rows_per_ = (len(views) + cols - 1) // cols
    tw_ = (1920 - 16 - (cols - 1) * 6) // cols
    img = Image.new("RGB", (1920, 120 + len(kinds) * rows_per_ * (tw_ * 9 // 16 + 6) + 20), (255, 255, 255))
    d, y0 = head(img, title, ["numpy の z バッファ（Unity の描画ではない）。t* = 12 s の静止。爪・船なし。黒い線 = 遮る縁。原画視点・座席のほかは波の所を切り出して拡大（同じ視点は同じ切り出し）。",
                              "色づけ：赤 ①・緑 ②・水色 ③・青 wave4（左端の青い波）・灰 ほかの前の面・濃い灰 背" if suffix == "tint" else
                              "色なしの粘土：光は全部の図で同じ。上の段 = 見本05 B、下の段 = 段の行"])
    rows_per = (len(views) + cols - 1) // cols
    tw = (1920 - 16 - (cols - 1) * 6) // cols
    th = tw * 9 // 16
    y = y0
    for k in kinds:
        for r in range(rows_per):
            for ci in range(cols):
                vi = r * cols + ci
                if vi >= len(views):
                    continue
                v = views[vi]
                box = RC.crop_box(CLAY, kinds, v)
                p = os.path.join(CLAY, "%s_%s_%s.png" % (k, v, suffix))
                x = 8 + ci * (tw + 6)
                img.paste(Image.open(p).convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (x, y))
                nm = RC.NAMES_JA.get(v, ("回り台 %s°" % v[2:]) if v.startswith("tt") else v)
                label(d, (x + 4, y + 4), "%s ／ %s" % (NJA[k], nm), 15)
            y += th + 6
        y += 6
    img.save(OUT + "/" + fname)


def sheet_tt_material():
    azs = ["000", "030", "060", "090", "270", "300", "330"]
    img = Image.new("RGB", (1920, 1080), (255, 255, 255))
    d, y0 = head(img, "段の行（B-ROWS）：材質の回り台（爪なし、Unity）　上：見本05 B／下：段の行 " + NEW,
                 ["材質 AS05（平らな塗り・白い粒なし・内の縁の白の書き換え）。段の行の白は段の縁の帯だけ（溝の底〜唇の先を回って唇の下 0.6 m まで）。回り台は見本04 と同じカメラ。"])
    tw = (1920 - 16 - 6 * 6) // 7
    th = tw * 9 // 16
    for ri, (k, base) in enumerate((("B10", B10), (NEW, RNEW))):
        for ci, a in enumerate(azs):
            x = 8 + ci * (tw + 6); y = y0 + ri * (th * 2 + 20)
            im = Image.open(base + "/tt/t120_az%s_noclaws.png" % a).convert("RGB")
            W, H = im.size
            im = im.crop((int(W * 0.18), int(H * 0.12), int(W * 0.82), int(H * 0.88))).resize((tw, th * 2 - 10), Image.LANCZOS)
            img.paste(im, (x, y))
            label(d, (x + 4, y + 4), "%s ／ %s°" % (NJA[k], int(a)), 14)
    img.save(OUT + "/rows_6_turntable_material.png")


def main():
    sheet_painting()
    v6 = ["painting", "seat", "side_left", "side_right", "back65", "top"]
    sheet_views(v6, "clay", "rows_2_clay.png", "段の行（B-ROWS）：色なしの粘土（爪・船なし）　見本05 B｜段の行 " + NEW)
    sheet_views(v6, "tint", "rows_3_tint.png", "段の行（B-ROWS）：三つの層の色づけ（爪・船なし）　見本05 B｜段の行 " + NEW)
    tts = ["tt%d" % a for a in range(0, 360, 30)]
    sheet_views(tts, "clay", "rows_4_turntable_clay.png", "段の行（B-ROWS）：回り台 12 方位の粘土　見本05 B｜段の行 " + NEW, cols=4)
    sheet_views(tts, "tint", "rows_5_turntable_tint.png", "段の行（B-ROWS）：回り台 12 方位の層の色づけ　見本05 B｜段の行 " + NEW, cols=4)
    sheet_tt_material()
    print("SHEETS_DONE", OUT)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
