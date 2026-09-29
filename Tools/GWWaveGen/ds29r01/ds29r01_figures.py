# -*- coding: utf-8 -*-
"""設計29修正01：証拠の図と静止画を Docs/Evidence/Design/29R01/ へ書く（Pillow だけ。Unity の出力を読むだけ）。

入力（Git 対象外）：Unity/Build/Design/29R01/unity/f_final・f_final_kp の t28 の描画と静止画・動画のコマの一覧、
Unity/Build/ArtFirst/28修正01/render（基準の描画）、indep_check/frames（行 239 の切り出し）、measure（唇先の断面の図）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_figures.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")).replace("\\", "/")
B = REPO + "/Unity/Build"
OUT = REPO + "/Docs/Evidence/Design/29R01"
FONT = "C:/Windows/Fonts/YuGothM.ttc"
f18 = ImageFont.truetype(FONT, 18)
f16 = ImageFont.truetype(FONT, 16)

def label(im, text, xy=(6, 4), font=f18):
    d = ImageDraw.Draw(im)
    x, y = xy
    bb = d.textbbox((x, y), text, font=font)
    d.rectangle((bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3), fill=(0, 0, 0))
    d.text((x, y), text, font=font, fill=(255, 255, 255))

def fit(src, w, h):
    im = Image.open(src).convert("RGB")
    im.thumbnail((w, h), Image.LANCZOS)
    return im

# 1) t* の比べ：28修正01（K*＋K* の焼き込み）／29修正01 焼き直しの前（K*′＋古い焼き込み）／29修正01 焼き直し（採用）
cols = [
    (B + "/ArtFirst/28修正01/render", "28修正01：K*＋K* の焼き込み（基準）"),
    (B + "/Design/29R01/unity/f_final/t28/render", "焼き直しの前：K*′＋古い焼き込み"),
    (B + "/Design/29R01/unity/f_final_kp/t28/render", "29修正01（採用）：K*′＋K*′ へ焼き直し"),
]
canvas = Image.new("RGB", (1920, 1080), (20, 20, 20))
for i, (d, name) in enumerate(cols):
    for j, view in enumerate(["painting", "seat"]):
        im = Image.open(d + "/af28r01_%s.png" % view).convert("RGB").resize((640, 360), Image.LANCZOS)
        label(im, "%s｜%s" % (name, "原画視点 t*" if view == "painting" else "座席 v1 t*"), font=f16)
        canvas.paste(im, (640 * i, 360 * j))
# 3 段目：評価器の境界の図（焼き直し）の 2 倍の切り出し
bnd = Image.open(B + "/Design/29R01/unity/f_final_kp/t28/evidence/28R01_boundaries.png").convert("RGB")
crops = [((873.7, 695.0), "73・118・263 の最悪点 (874, 695)／72 の最悪点 (872, 697)"),
         ((1090, 427), "134 の最悪点（唇先 (1090, 427)）"),
         ((938.1, 176.2), "267 の白の帯（最大 69 px²、(938, 176)）")]
for i, ((cx, cy), name) in enumerate(crops):
    x0 = int(round(cx - 160)); y0 = int(round(cy - 90))
    c = bnd.crop((x0, y0, x0 + 320, y0 + 180)).resize((640, 360), Image.NEAREST)
    dd = ImageDraw.Draw(c)
    px, py = (cx - x0) * 2, (cy - y0) * 2
    dd.ellipse((px - 14, py - 14, px + 14, py + 14), outline=(255, 0, 255), width=2)
    label(c, name, font=f16)
    label(c, "評価器の境界の図の 2 倍（シアン＝原画の境界、緑 ≤2・黄 ≤4・赤 >4 px）", xy=(6, 334), font=f16)
    canvas.paste(c, (640 * i, 720))
canvas.save(OUT + "/fig_ds29r01_tstar_compare.png")

# 2) 焼き直しで描いた静止画の一覧（1920×1440 → 枠に収める）
sheet = fit(B + "/Design/29R01/unity/f_final_kp/fig_f_final_kp_stills_sheet.png", 1920, 1080)
sheet.save(OUT + "/fig_ds29r01_stills_sheet.png")
# 3) 動画のコマ（240・330・390・420）の一覧（そのまま 1920×1080）
v = Image.open(B + "/Design/29R01/unity/f_final_kp/frames/sheet_video_kp.png").convert("RGB")
v.save(OUT + "/fig_ds29r01_video_frames.png")
# 4) 原画視点の t*（焼き直し、DS29Render の静止画、1920×1080）
Image.open(B + "/Design/29R01/unity/f_final_kp/stills/ds29_painting_tstar_tau+0.000.png").convert("RGB").save(OUT + "/ds29r01_painting_tstar.png")
Image.open(B + "/Design/29R01/unity/f_final_kp/stills/ds29_seat_toward_wave_tstar_tau+0.000.png").convert("RGB").save(OUT + "/ds29r01_seat_toward_wave_tstar.png")
# 5) 行 239 の奥の線（左の側面 t*、上＝精度の層、下＝16 bit だけ。独立の検査）
fit(B + "/Design/29R01/indep_check/frames/crop_side_left_farline_fine_top_16bit_bottom.png", 1920, 1080).save(OUT + "/fig_ds29r01_row239_farline.png")
# 6) 唇先の薄い断面（測定の図、1600×420）
Image.open(B + "/Design/29R01/measure/fig_lip_thin_sections.png").convert("RGB").save(OUT + "/fig_ds29r01_lip_thin_sections.png")
# 7) 行 239 の図に札を足す
im = fit(B + "/Design/29R01/indep_check/frames/crop_side_left_farline_fine_top_16bit_bottom.png", 1920, 1080)
label(im, "上：精度の層を読む再生器（29修正01、f_final）", xy=(8, 6), font=f16)
label(im, "下：16 bit だけ（28修正01 の F_final の描画）", xy=(8, im.size[1] // 2 + 8), font=f16)
label(im, "左の側面 t* の奥の斜めの縁（行 239 の外殻線）", xy=(8, im.size[1] // 2 - 30), font=f16)
im.save(OUT + "/fig_ds29r01_row239_farline.png")
print("DS29R01_FIGURES done")
