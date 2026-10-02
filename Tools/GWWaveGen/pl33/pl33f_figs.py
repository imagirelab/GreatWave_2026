# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1 の記録の図（1920×1080。既にある Unity の PC オフスクリーン描画と numpy の数から並べるだけ）。

  fig_pl33_claws_views.png   t* と t 10.5 s の拡大：原画視点の頂と唇（原画｜前｜作る部｜修正の回）、座席・座席から波の方向・後ろ 65°（前｜作る部｜修正の回）
  fig_pl33_bregion.png       b区域（［利用者の言葉］Q16・Q21）：原画｜前｜作る部｜修正の回（t* と t 10.5 s）
  fig_pl33f_rim_try.png      132・72 の細部込みのへこみを埋める試し（pl33f_rim_fill、採らなかった）：原画視点の拡大と、座席から波の方向・真上に出た白い棒
作る部の同じ名前の図は Unity/Build/Polish/33/record/archive_build/ に残した。
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_figs.py
"""
import json
import os
import sys

from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "pl30"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "pl33"))
from pl30_sheets import font, label, head  # noqa: E402
from pl33_figs import paint_disp  # noqa: E402

BEF = REPO + "/Unity/Build/Polish/32/fix01/r_fix01"
BLD = REPO + "/Unity/Build/Polish/33/r_after"
FIX = REPO + "/Unity/Build/Polish/33/fix01/r_fix01"
RIM = REPO + "/Unity/Build/Polish/33/fix01/r_rim1"
OUT = REPO + "/Docs/Evidence/Polish/33"
MEAS = REPO + "/Unity/Build/Polish/33/fix01/measure/pl33f_measure.json"


def op(root, v, t):
    return Image.open(root + "/views/%s_%s_asis.png" % (v, t)).convert("RGB")


def views_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 修正の回 1｜爪の造形の拡大：前（仕上げ32）｜作る部｜修正の回（同じ視点・同じ時刻・作品のまま）",
         "上の段：原画視点 t* の頂と唇（原画を含む）。中の段：t 10.5 s（原画視点の唇の下・座席から波の方向）。下の段：t*（座席・後ろ 65°）。Unity の PC オフスクリーン描画（HMD ではない）。")
    P = paint_disp()
    box = (560, 100, 1130, 500)
    for i, (lab, src) in enumerate([("原画", P), ("前", op(BEF, "painting", "t120")), ("作る部", op(BLD, "painting", "t120")), ("修正の回", op(FIX, "painting", "t120"))]):
        t = src.crop(box).resize((474, 333), Image.LANCZOS)
        im.paste(t, (4 + i * 478, 66))
        label(d, 8 + i * 478, 70, "原画視点 t*｜" + lab, 13)
    row2 = [("painting", "t105", (700, 260, 1150, 560), "原画視点 t 10.5 s 唇"), ("seat_toward_wave", "t105", (500, 0, 1300, 560), "座席から波の方向 t 10.5 s")]
    x = 4
    for v, t, bx, nm in row2:
        for lab, root in (("前", BEF), ("作る部", BLD), ("修正の回", FIX)):
            c = op(root, v, t).crop(bx)
            c.thumbnail((316, 222), Image.LANCZOS)
            im.paste(c, (x, 404))
            label(d, x + 3, 408, "%s｜%s" % (lab, nm), 11)
            x += 320
    row3 = [("seat", "t120", (500, 300, 1400, 1080), "座席 t*"), ("back65", "t120", (700, 180, 1500, 700), "後ろ 65° t*")]
    x = 4
    for v, t, bx, nm in row3:
        for lab, root in (("前", BEF), ("作る部", BLD), ("修正の回", FIX)):
            c = op(root, v, t).crop(bx)
            c.thumbnail((316, 250), Image.LANCZOS)
            im.paste(c, (x, 632))
            label(d, x + 3, 636, "%s｜%s" % (lab, nm), 11)
            x += 320
    m = json.load(open(MEAS, encoding="utf-8"))
    vs = m["views"]
    f = font(14)
    lines = [
        "・座席 t* の藍の上の爪の画素：前 %d、作る部 %d、修正の回 %d（作る部の立ち上げ 0.35×弧長・最大 0.8 m の角の四角い板と藍の上の白い三日月をやめ、低い浮き彫り 0.12×弧長・最大 0.22 m にした）。"
        % (vs["seat_t120"]["before"]["over_indigo_px"], vs["seat_t120"]["build"]["over_indigo_px"], vs["seat_t120"]["fix"]["over_indigo_px"]),
        "・座席から波の方向 t 10.5 s の藍の上の爪の画素：前 %d、作る部 %d、修正の回 %d。原画視点 t 9 s・10.5 s の主役波の外の爪の画素：作る部 %d・%d → 修正の回 %d・%d（前 %d・%d）。"
        % (vs["seat_toward_wave_t105"]["before"]["over_indigo_px"], vs["seat_toward_wave_t105"]["build"]["over_indigo_px"], vs["seat_toward_wave_t105"]["fix"]["over_indigo_px"],
           m["painting_outside_hero"]["t090"]["build"]["claw_px_outside_hero"], m["painting_outside_hero"]["t105"]["build"]["claw_px_outside_hero"],
           m["painting_outside_hero"]["t090"]["fix"]["claw_px_outside_hero"], m["painting_outside_hero"]["t105"]["fix"]["claw_px_outside_hero"],
           m["painting_outside_hero"]["t090"]["before"]["claw_px_outside_hero"], m["painting_outside_hero"]["t105"]["before"]["claw_px_outside_hero"]),
        "・後ろ 65°：冠の爪を稜に沿う 3 本以上の指の房（18 房 79 本）にし、ドームの面に離れて散る小さな鉤・米粒をなくした。冠の爪は生まれてから t* まで原画のカメラから隠れる（3 コマおきの確かめで 0 頂点）。",
    ]
    y = 900
    for s in lines:
        d.text((14, y), s, fill=(40, 48, 64), font=f)
        y += 24
    p = OUT + "/fig_pl33_claws_views.png"
    im.save(p)
    return p


def bregion_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 修正の回 1｜b区域の爪（［利用者の言葉］Q16・Q21）：原画｜前｜作る部｜修正の回（上：t*、下：t 10.5 s）",
         "修正の回：b区域の爪 57 本の両側に短い添え指（pl33f_tuft_fingers、外の縁だけに墨版の線）、鉤の内の水色の膜を帯の幅 × 3.0。藍の窓と 3 つの房の形は主役波の形と材質（仕上げ28・29）。")
    P = paint_disp()
    box = (150, 340, 790, 650)
    for r, ts in enumerate(("t120", "t105")):
        srcs = [("原画", P if ts == "t120" else None), ("前", op(BEF, "painting", ts)), ("作る部", op(BLD, "painting", ts)), ("修正の回", op(FIX, "painting", ts))]
        for i, (lab, src) in enumerate(srcs):
            if src is None:
                continue
            t = src.crop(box).resize((474, 230), Image.LANCZOS)
            im.paste(t, (4 + i * 478, 66 + r * 240))
            label(d, 8 + i * 478, 70 + r * 240, "%s｜%s" % (lab, "t*" if ts == "t120" else "t 10.5 s"), 13)
    # 拡大（t*、修正の回）
    big = op(FIX, "painting", "t120").crop((330, 380, 650, 600)).resize((640, 440), Image.LANCZOS)
    pb = P.crop((330, 380, 650, 600)).resize((640, 440), Image.LANCZOS)
    im.paste(pb, (4, 552)); label(d, 8, 556, "原画｜拡大", 13)
    im.paste(big, (648, 552)); label(d, 652, 556, "修正の回 t*｜拡大", 13)
    m = json.load(open(MEAS, encoding="utf-8"))
    rh = m["painting_tstar_rhythm"]
    rg = m["closed_rings"]
    f = font(14)
    lines = ["b区域の帯の中の白い地の上の数（原画｜前｜作る部｜修正の回）：",
             "  水色の版の割合 %.3f｜%.3f｜%.3f｜%.3f" % (rh["bregion_painting"]["mizuiro"], rh["bregion_before"]["mizuiro"], rh["bregion_build"]["mizuiro"], rh["bregion_fix"]["mizuiro"]),
             "  暗い線の画素 %d｜%d｜%d｜%d" % (rh["bregion_painting"]["dark_line_px"], rh["bregion_before"]["dark_line_px"], rh["bregion_build"]["dark_line_px"], rh["bregion_fix"]["dark_line_px"]),
             "  暗い線の成分 %d｜%d｜%d｜%d" % (rh["bregion_painting"]["components"], rh["bregion_before"]["components"], rh["bregion_build"]["components"], rh["bregion_fix"]["components"]),
             "  水色の置き場所の再現（4 px の許し） —｜%.3f｜%.3f｜%.3f" % (rh["bregion_before"]["miz_recall_tol4"], rh["bregion_build"]["miz_recall_tol4"], rh["bregion_fix"]["miz_recall_tol4"]),
             "  閉じた輪（米粒）t*：%d｜%d｜%d（穴 4 px 以上 %d｜%d｜%d）" % (rg["before_t120_bregion"]["rings"], rg["build_t120_bregion"]["rings"], rg["fix_t120_bregion"]["rings"],
                                                         rg["before_t120_bregion"]["rings_hole_ge4"], rg["build_t120_bregion"]["rings_hole_ge4"], rg["fix_t120_bregion"]["rings_hole_ge4"]),
             "  閉じた輪 t 10.5 s：%d｜%d｜%d" % (rg["before_t105_bregion"]["rings"], rg["build_t105_bregion"]["rings"], rg["fix_t105_bregion"]["rings"]),
             "判定は一部（2 回目の作り直しの後）：指は 2〜3 本の束で同じ向きに巻いて読めるが、",
             "原画の 5〜10 本の房と房の間の藍の窓、水色の版の量（%.3f）には届かない。" % rh["bregion_painting"]["mizuiro"]]
    y = 560
    for s in lines:
        d.text((1300, y), s, fill=(40, 48, 64), font=f)
        y += 26
    p = OUT + "/fig_pl33_bregion.png"
    im.save(p)
    return p


def rim_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 修正の回 1｜132・72 の細部込みのへこみを埋める試し（pl33f_rim_fill）— 採らなかった",
         "包絡の真値に 4 px より届かない描画の空の境界の塊ごとに、境界と真値の間を埋める白い帯（10 本）を主役波のシートに結び付けた。原画視点では埋まるが、ほかの視点で白い棒になる。")
    lay = json.load(open(REPO + "/Unity/Build/Polish/33/fix01/try_rim/ds33_claw_layout.json", encoding="utf-8"))
    xys = [c["pl33f_rim_xy"] for c in lay["claws"] if c["id"].startswith("R")][:6]
    A = op(FIX, "painting", "t120"); Bm = op(RIM, "painting", "t120")
    for i, (x, y) in enumerate(xys):
        x, y = int(x), int(y)
        bx = (x - 60, y - 40, x + 60, y + 40)
        for j, (lab, src) in enumerate((("修正の回", A), ("試し", Bm))):
            t = src.crop(bx).resize((300, 200), Image.NEAREST)
            px = 4 + (i % 3) * 620 + j * 304
            py = 66 + (i // 3) * 210
            im.paste(t, (px, py))
            label(d, px + 3, py + 3, "%s｜(%d, %d)" % (lab, x, y), 11)
    for j, (v, bx) in enumerate((("seat_toward_wave", (950, 300, 1450, 700)), ("top", (1200, 300, 1600, 700)))):
        for k, (lab, root) in enumerate((("修正の回", FIX), ("試し", RIM))):
            c = op(root, v, "t120").crop(bx).resize((300, 240), Image.LANCZOS)
            px = 4 + (2 * j + k) * 304
            im.paste(c, (px, 500))
            label(d, px + 3, 503, "%s｜%s t*" % (lab, v), 11)
    g = json.load(open(REPO + "/Unity/Build/Polish/33/fix01/r_rim1/pl28u_regress.json", encoding="utf-8"))["sets"]["t28_claws"]["strict"]["silhouettes_definition_reading"]
    f = font(15)
    lines = ["試し（爪あり、定義の読み）：132 最大 %.4f px（修正の回 5.3771）、72 p95 %.4f px（修正の回 5.1476）。78・130・131 は変わらない。" % (g["132"]["max_px"], g["72"]["p95_px"]),
             "4 px に届かない。座席から波の方向と真上で、帯が藍と空の上の細い白い棒になる（Q28：どの視点でも読める爪の目的と逆）。帯を原画視点だけ見えるようにするのは視点に依る形で採らない。",
             "残りのこぶ（描画が包絡の外）は主役波の面の輪郭（爪なしでも同じ所）。限界として 10/29 以降の一覧へ送る。"]
    y = 770
    for s in lines:
        d.text((14, y), s, fill=(40, 48, 64), font=f)
        y += 26
    p = OUT + "/fig_pl33f_rim_try.png"
    im.save(p)
    return p


def main():
    for fn in (views_fig, bregion_fig, rim_fig):
        print(fn())


if __name__ == "__main__":
    main()
