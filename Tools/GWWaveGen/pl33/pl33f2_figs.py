# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 2 の記録の図（1920×1080。既にある Unity の PC オフスクリーン描画と numpy の数から並べるだけ）。

  fig_pl33f2_sliver.png      b区域の頂から藍へ垂れる水色の細片（WC223・SC223m・WC224）：原画視点 t* と t 10.5 s の拡大（前｜修正の回 1｜修正の回 2）と、
                             t 10.0〜12.0 s の毎コマ（61 コマ）の「藍の上の明るい爪の一番大きい成分」と「藍の上の明るい爪の画素」の折れ線
  fig_pl33_claws_views.png   爪の造形の拡大：原画視点の頂と唇（原画｜前｜修正の回 1｜修正の回 2）、t 10.5 s・t* の座席から波の方向・座席・後ろ 65°
  fig_pl33_bregion.png       b区域（［利用者の言葉］Q16・Q21）：原画｜前｜修正の回 1｜修正の回 2（t* と t 10.5 s）
修正の回 1 の同じ名前の図は Unity/Build/Polish/33/record/archive_fix01/ に残した。
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_figs.py
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
F1 = REPO + "/Unity/Build/Polish/33/fix01/r_fix01"
F2 = REPO + "/Unity/Build/Polish/33/fix02/r_fix02"
W2 = REPO + "/Unity/Build/Polish/33/fix02/work"
OUT = REPO + "/Docs/Evidence/Polish/33"
MEAS = REPO + "/Unity/Build/Polish/33/fix02/measure/pl33f2_measure.json"
SEQ = [W2 + "/seqm_f2.json", W2 + "/seqm_hold1.json", W2 + "/seqm_hold2.json"]
COLS = {"pre": (120, 120, 120), "fix01": (200, 60, 50), "f2": (30, 90, 200)}


def op(root, v, t):
    return Image.open(root + "/views/%s_%s_asis.png" % (v, t)).convert("RGB")


def series():
    """3 つの JSON（0.1 s おき＋1 コマ後＋2 コマ後）から、前・修正の回 1・修正の回 2 の毎コマの (t, 合計, 一番大きい成分)。"""
    out = {"pre": [], "fix01": [], "f2": []}
    for p in SEQ:
        d = json.load(open(p, encoding="utf-8"))
        for k, rows in d.items():
            key = "pre" if k.endswith("pre") else ("fix01" if k.endswith("fix01") else "f2")
            out[key] += [(r["t"], r["total"], r["largest"]) for r in rows]
    for k in out:
        out[k].sort()
    return out


def plot(d, box, data, idx, title, ymax):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=(250, 250, 250), outline=(160, 160, 160))
    f = font(13)
    d.text((x0 + 8, y0 + 4), title, fill=(30, 30, 40), font=font(14, True))
    px0, py0, px1, py1 = x0 + 60, y0 + 30, x1 - 12, y1 - 30
    for v in range(0, ymax + 1, ymax // 4):
        y = py1 - (py1 - py0) * v / ymax
        d.line([(px0, y), (px1, y)], fill=(225, 225, 225))
        d.text((x0 + 6, y - 8), "%d" % v, fill=(90, 90, 90), font=f)
    for t in (10.0, 10.5, 11.0, 11.5, 12.0):
        x = px0 + (px1 - px0) * (t - 10.0) / 2.0
        d.line([(x, py0), (x, py1)], fill=(225, 225, 225))
        d.text((x - 14, py1 + 6), "%.1f s" % t, fill=(90, 90, 90), font=f)
    for k, rows in data.items():
        pts = [(px0 + (px1 - px0) * (r[0] - 10.0) / 2.0, py1 - (py1 - py0) * min(r[idx], ymax) / ymax) for r in rows]
        d.line(pts, fill=COLS[k], width=3)
    lx = px0 + 10
    for k, nm in (("pre", "前（仕上げ32）"), ("fix01", "修正の回 1"), ("f2", "修正の回 2")):
        d.line([(lx, py0 + 10), (lx + 26, py0 + 10)], fill=COLS[k], width=3)
        d.text((lx + 32, py0 + 2), nm, fill=(40, 40, 40), font=f)
        lx += 150


def sliver_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 修正の回 2｜b区域の頂から藍へ垂れる水色の細片（WC223・SC223m・WC224）を、t 10 s〜t* のどのコマでも出さない（pl33f2_white_clip）",
         "上：原画視点の拡大（前｜修正の回 1｜修正の回 2、作品のまま）。下：t 10.0〜12.0 s の毎コマ 61 コマ（自己評審の数の評審の式：作品と爪なしの差 > 12・爪なしの明るさ < 110・作品の明るさ > 150）。")
    rows = [("t120", (420, 470, 620, 640), "原画視点 t*"), ("t105", (200, 460, 360, 620), "原画視点 t 10.5 s")]
    for r, (t, bx, nm) in enumerate(rows):
        for i, (lab, root) in enumerate((("前", BEF), ("修正の回 1", F1), ("修正の回 2", F2))):
            c = op(root, "painting", t).crop(bx)
            w = 316 if r == 0 else 316
            h = int(w * (bx[3] - bx[1]) / (bx[2] - bx[0]))
            c = c.resize((w, h), Image.NEAREST)
            x = 4 + i * 318 + r * 958
            im.paste(c, (x, 66))
            label(d, x + 3, 70, "%s｜%s" % (lab, nm), 12)
    data = series()
    plot(d, (8, 420, 956, 860), data, 2, "藍の上の明るい爪の一番大きい成分（px）", 1600)
    plot(d, (964, 420, 1912, 860), data, 1, "藍の上の明るい爪の画素の合計（px）", 4400)
    f = font(15)
    pre = {r[0]: r for r in data["pre"]}
    f1 = {r[0]: r for r in data["fix01"]}
    f2 = {r[0]: r for r in data["f2"]}
    dmax = max(f2[t][2] - pre[t][2] for t in f2 if t in pre)
    lines = ["・t*：一番大きい成分 前 %d → 修正の回 1 %d → 修正の回 2 %d px、合計 %d → %d → %d px。t 10.5 s：%d → %d → %d px、合計 %d → %d → %d px。"
             % (pre[12.0][2], f1[12.0][2], f2[12.0][2], pre[12.0][1], f1[12.0][1], f2[12.0][1], pre[10.5][2], f1[10.5][2], f2[10.5][2], pre[10.5][1], f1[10.5][1], f2[10.5][1]),
             "・t 10.0〜12.0 s の毎コマ 61 コマで、修正の回 2 の一番大きい成分は前（仕上げ32）との差が最大 +%d px（修正の回 1 は最大 +%d px）。"
             % (dmax, max(f1[t][2] - pre[t][2] for t in f1 if t in pre)),
             "・検査は 0.1 s おきの 21 コマ（爪なしの描画と主役波の z バッファ、3D の白の範囲）。間の 40 コマは 1 コマ後・2 コマ後の描画で確かめた（検査に使っていない）。",
             "・縮めたもの：膜 38 本（t* で 32 本 341 輪。全部の輪を 0 にした膜 WC002・WC201、WC223 は 20 輪のうち 13 輪・WC224 は 16 輪を 0）、添え指 22 本（t* で 16 本、根元へ潰した 12 本：SC223m・SC224p・SC224m など）。原画の爪・冠の爪は変えていない。"]
    y = 880
    for s in lines:
        d.text((14, y), s, fill=(40, 48, 64), font=f)
        y += 30
    p = OUT + "/fig_pl33f2_sliver.png"
    im.save(p)
    return p


def views_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 修正の回 2｜爪の造形の拡大：前（仕上げ32）｜修正の回 1｜修正の回 2（同じ視点・同じ時刻・作品のまま）",
         "上の段：原画視点 t* の頂と唇（原画を含む）。中の段：t 10.5 s（原画視点の b区域の下・座席から波の方向）。下の段：t*（座席・後ろ 65°）。Unity の PC オフスクリーン描画（HMD ではない）。")
    P = paint_disp()
    box = (560, 100, 1130, 500)
    for i, (lab, src) in enumerate([("原画", P), ("前", op(BEF, "painting", "t120")), ("修正の回 1", op(F1, "painting", "t120")), ("修正の回 2", op(F2, "painting", "t120"))]):
        t = src.crop(box).resize((474, 333), Image.LANCZOS)
        im.paste(t, (4 + i * 478, 66))
        label(d, 8 + i * 478, 70, "原画視点 t*｜" + lab, 13)
    row2 = [("painting", "t105", (150, 380, 600, 640), "原画視点 t 10.5 s b区域の下"), ("seat_toward_wave", "t105", (500, 0, 1300, 560), "座席から波の方向 t 10.5 s")]
    x = 4
    for v, t, bx, nm in row2:
        for lab, root in (("前", BEF), ("修正の回 1", F1), ("修正の回 2", F2)):
            c = op(root, v, t).crop(bx)
            c.thumbnail((316, 222), Image.LANCZOS)
            im.paste(c, (x, 404))
            label(d, x + 3, 408, "%s｜%s" % (lab, nm), 11)
            x += 320
    row3 = [("seat", "t120", (500, 300, 1400, 1080), "座席 t*"), ("back65", "t120", (700, 180, 1500, 700), "後ろ 65° t*")]
    x = 4
    for v, t, bx, nm in row3:
        for lab, root in (("前", BEF), ("修正の回 1", F1), ("修正の回 2", F2)):
            c = op(root, v, t).crop(bx)
            c.thumbnail((316, 250), Image.LANCZOS)
            im.paste(c, (x, 632))
            label(d, x + 3, 636, "%s｜%s" % (lab, nm), 11)
            x += 320
    m = json.load(open(MEAS, encoding="utf-8"))
    vs = m["views"]
    rh = m["painting_tstar_rhythm"]
    f = font(14)
    lines = [
        "・座席 t* の藍の上の爪の画素：前 %d、修正の回 1 %d、修正の回 2 %d。座席から波の方向 t 10.5 s：前 %d、修正の回 1 %d、修正の回 2 %d。"
        % (vs["seat_t120"]["before"]["over_indigo_px"], vs["seat_t120"]["build"]["over_indigo_px"], vs["seat_t120"]["fix"]["over_indigo_px"],
           vs["seat_toward_wave_t105"]["before"]["over_indigo_px"], vs["seat_toward_wave_t105"]["build"]["over_indigo_px"], vs["seat_toward_wave_t105"]["fix"]["over_indigo_px"]),
        "・座席・座席から波の方向の爪は仕上げ32 とほぼ同じ見え方（面に沿う帯）で、座席から「立ち上がる白い指」は読めない（限界、第 15.6 節）。",
        "・原画視点 t* の一覧の爪の領域の水色の版の割合：原画 %.3f、前 %.3f、修正の回 1 %.3f、修正の回 2 %.3f（律動は一部）。"
        % (rh["claw_zone_painting"]["mizuiro"], rh["claw_zone_before"]["mizuiro"], rh["claw_zone_build"]["mizuiro"], rh["claw_zone_fix"]["mizuiro"]),
        "・後ろ 65°：冠の爪の房（18 房 79 本）は修正の回 1 のまま（修正の回 2 で変えていない）。",
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
    head(d, "仕上げ33 修正の回 2｜b区域の爪（［利用者の言葉］Q16・Q21）：原画｜前｜修正の回 1｜修正の回 2（上：t*、下：t 10.5 s）",
         "修正の回 2：膜と房の添え指を t 10 s〜t* の白の範囲の内に縮めた（藍へ垂れる細片をなくした）。房の数・藍の窓・3 つの房の形は主役波の形と材質（仕上げ28・29）。")
    P = paint_disp()
    box = (150, 340, 790, 650)
    for r, ts in enumerate(("t120", "t105")):
        srcs = [("原画", P if ts == "t120" else None), ("前", op(BEF, "painting", ts)), ("修正の回 1", op(F1, "painting", ts)), ("修正の回 2", op(F2, "painting", ts))]
        for i, (lab, src) in enumerate(srcs):
            if src is None:
                continue
            t = src.crop(box).resize((474, 230), Image.LANCZOS)
            im.paste(t, (4 + i * 478, 66 + r * 240))
            label(d, 8 + i * 478, 70 + r * 240, "%s｜%s" % (lab, "t*" if ts == "t120" else "t 10.5 s"), 13)
    big = op(F2, "painting", "t120").crop((330, 380, 650, 600)).resize((640, 440), Image.LANCZOS)
    pb = P.crop((330, 380, 650, 600)).resize((640, 440), Image.LANCZOS)
    im.paste(pb, (4, 552)); label(d, 8, 556, "原画｜拡大", 13)
    im.paste(big, (648, 552)); label(d, 652, 556, "修正の回 2 t*｜拡大", 13)
    m = json.load(open(MEAS, encoding="utf-8"))
    rh = m["painting_tstar_rhythm"]
    rg = m["closed_rings"]
    f = font(14)
    lines = ["b区域の帯の中の白い地の上の数（原画｜前｜修正の回 1｜修正の回 2）：",
             "  水色の版の割合 %.3f｜%.3f｜%.3f｜%.3f" % (rh["bregion_painting"]["mizuiro"], rh["bregion_before"]["mizuiro"], rh["bregion_build"]["mizuiro"], rh["bregion_fix"]["mizuiro"]),
             "  暗い線の画素 %d｜%d｜%d｜%d" % (rh["bregion_painting"]["dark_line_px"], rh["bregion_before"]["dark_line_px"], rh["bregion_build"]["dark_line_px"], rh["bregion_fix"]["dark_line_px"]),
             "  暗い線の成分 %d｜%d｜%d｜%d" % (rh["bregion_painting"]["components"], rh["bregion_before"]["components"], rh["bregion_build"]["components"], rh["bregion_fix"]["components"]),
             "  水色の置き場所の再現（4 px の許し） —｜%.3f｜%.3f｜%.3f" % (rh["bregion_before"]["miz_recall_tol4"], rh["bregion_build"]["miz_recall_tol4"], rh["bregion_fix"]["miz_recall_tol4"]),
             "  閉じた輪（米粒）t*：%d｜%d｜%d（穴 4 px 以上 %d｜%d｜%d）" % (rg["before_t120_bregion"]["rings"], rg["build_t120_bregion"]["rings"], rg["fix_t120_bregion"]["rings"],
                                                         rg["before_t120_bregion"]["rings_hole_ge4"], rg["build_t120_bregion"]["rings_hole_ge4"], rg["fix_t120_bregion"]["rings_hole_ge4"]),
             "  閉じた輪 t 10.5 s：%d｜%d｜%d" % (rg["before_t105_bregion"]["rings"], rg["build_t105_bregion"]["rings"], rg["fix_t105_bregion"]["rings"]),
             "判定は一部（［利用者の言葉］の 2 回目の修正の回の後）：藍へ垂れる細片はなくなった。",
             "藍の上にあった添え指 12 本を潰した分、線の成分と水色は修正の回 1 より少し減った。",
             "原画の 5〜10 本の房・藍の窓・水色の量（%.3f）には届かない。" % rh["bregion_painting"]["mizuiro"]]
    y = 560
    for s in lines:
        d.text((1300, y), s, fill=(40, 48, 64), font=f)
        y += 26
    p = OUT + "/fig_pl33_bregion.png"
    im.save(p)
    return p


def main():
    for fn in (sliver_fig, views_fig, bregion_fig):
        print(fn())


if __name__ == "__main__":
    main()
