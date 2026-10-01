# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の作る部の前後の図（1920×1080）。前（前の点検 PL29Audit：投影の焼き込み）と後（PL29Render：視点によらない立体の材質）を、
同じ視点・同じ時刻で並べる。前の点検の図（fig_pl29a_*）と同じ視点・時刻・回り台の方位。

  views  ：時刻ごとに 1 枚。上の 2 段＝前、下の 2 段＝後。7 視点（原画視点・座席・座席から波の方向・左の側面・右の側面・後ろ 65°・真上）と、8 枠目は
           原画視点の拡大（前と後）。cond は clawfree（爪なし）か asis（作品のまま：爪・飛沫・線）。
  tt     ：回り台 12 方位（t* ほか）。上の 3 段 × 4 列＝前（6 方位ずつ 2 組…）ではなく、前と後を方位ごとに上下に並べる（6 方位 × 2 枚 × 2 段）。
  crops  ：前の点検の破れの切り抜きの場所（catalogue_audit.json の上位）を、後の同じ画像の同じ場所で切り抜いて並べる。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_build_sheets.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/after/p29b --out Docs/Evidence/Polish/29
       ［修正の回］--prefix fig_pl29c --title … --blabel … --alabel … --note … で題と見出しを替える（既定は作る部の文）。
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
FONTB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TNAME = {"t060": "t 6 s", "t090": "t 9 s", "t105": "t 10.5 s", "t120": "t 12 s（t*）"}


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def label(d, x, y, text, sz=15):
    w = d.textlength(text, font=font(sz, True)) + 10
    d.rectangle([x, y, x + w, y + sz + 8], fill=(20, 20, 20))
    d.text((x + 5, y + 2), text, fill=(255, 255, 255), font=font(sz, True))


def header(im, title, sub):
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 62], fill=(28, 36, 52))
    d.text((14, 4), title, fill=(255, 255, 255), font=font(24, True))
    d.text((14, 38), sub, fill=(205, 212, 225), font=font(15))
    return d


BL = "前（原画カメラからの投影の焼き込み）"
AL = "後（視点によらない立体の材質）"
NOTE = "同じ視点・同じ時刻。前＝PL29Audit（K*′ P28R2rec・G_p28rec・bake_rec）、後＝PL29Render（同じ形と動き、PL29 Ukiyoe Keypose、爪は設計34 の白・淡い水色）。Unity 6000.4.3f1 の PC 描画（HMD ではない）。"
TITLE = "仕上げ29 前後（Q28）"


def views_sheet(before, after, ts, cond, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "%s｜%s｜%s｜上 2 段：%s　下 2 段：%s" % (TITLE, TNAME[ts], "爪なし" if cond == "clawfree" else "作品のまま（爪・飛沫・線）", BL, AL), NOTE)
    tw, th = 476, 252
    y0 = 66
    for si, (lab, root) in enumerate([("前", before), ("後", after)]):
        for k, (v, name) in enumerate(VIEWS + [("zoom", "原画視点の拡大")]):
            x, y = 4 + (k % 4) * (tw + 4), y0 + (si * 2 + k // 4) * (th + 2)
            if v == "zoom":
                p = os.path.join(root, "views", "painting_%s_%s.png" % (ts, cond))
                if os.path.exists(p):
                    a = Image.open(p).convert("RGB").crop((140, 60, 1240, 678)).resize((tw, th), Image.LANCZOS)
                    im.paste(a, (x, y))
            else:
                p = os.path.join(root, "views", "%s_%s_%s.png" % (v, ts, cond))
                if os.path.exists(p):
                    im.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
            label(d, x, y, lab + "｜" + name)
    im.save(out)


def tt_sheet(before, after, ts, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "%s｜回り台｜%s｜方位ごとに上：前　下：後（爪あり・飛沫なし・線あり、主役波だけ）" % (TITLE, TNAME[ts]),
               "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと。前の点検と同じ置き方。Unity の PC 描画（HMD ではない）。")
    tw, th = 316, 178
    for k in range(12):
        az = k * 30
        col, rowblk = k % 6, k // 6
        x = 4 + col * (tw + 4)
        for si, root in enumerate([before, after]):
            y = 66 + rowblk * (2 * th + 30) + si * (th + 2)
            p = os.path.join(root, "tt", "%s_az%03d_claws.png" % (ts, az))
            if os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").crop((240, 0, 1680, 810)).resize((tw, th), Image.LANCZOS), (x, y))
            label(d, x, y, ("前" if si == 0 else "後") + "｜方位 %d°" % az, 13)
    im.save(out)


KIND_JA = {"flat": "平らな面", "band": "外挿の帯", "seam": "継ぎ目", "stretch": "引き伸ばし", "claw": "溶けた爪"}


def crops_sheet(before, after, catalogue, out):
    """前の点検の破れ（catalogue_audit.json）の種類ごとの大きい順 4 つを、前と後の同じ画像（爪なし。爪は作品のまま）の同じ場所で切り抜いて並べる。"""
    cat = json.load(open(catalogue, encoding="utf-8"))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = header(im, "%s｜前の点検の破れの場所を、後の同じ画像の同じ場所で切り抜く（種類ごとに大きい順 4 つ。左：前　右：後）" % TITLE,
               "前＝%s、後＝%s。同じ視点・同じ時刻・同じ画素の範囲。溶けた爪は作品のまま（爪あり）、ほかは爪なし。" % (BL, AL))
    kinds = ["flat", "band", "seam", "stretch", "claw"]
    tw, th = 214, 190
    for r, kind in enumerate(kinds):
        items = sorted([c for c in cat if c["kind"] == kind], key=lambda c: -c["area"])
        seen, pick = set(), []
        for c in items:
            key = (c["view"], c["t"])
            if key in seen:
                continue
            seen.add(key); pick.append(c)
            if len(pick) == 4:
                break
        y = 66 + r * (th + 12)
        label(d, 4, y, KIND_JA[kind], 14)
        for k, c in enumerate(pick):
            x0, y0, x1, y1 = c["bbox"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            half = max(x1 - x0, (y1 - y0) * tw / th, 120) / 2 + 20
            hh = half * th / tw
            box = (int(max(0, cx - half)), int(max(0, cy - hh)), int(min(1920, cx + half)), int(min(1080, cy + hh)))
            cond = "asis" if kind == "claw" else "clawfree"
            for si, root in enumerate([before, after]):
                p = os.path.join(root, "views", "%s_%s_%s.png" % (c["view"], c["t"], cond))
                x = 110 + k * (2 * tw + 22) + si * (tw + 2)
                if os.path.exists(p):
                    im.paste(Image.open(p).convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (x, y))
                label(d, x, y + th - 22, ("前" if si == 0 else "後") + "｜" + dict(VIEWS).get(c["view"], c["view"]) + " " + TNAME[c["t"]], 11)
    im.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="fig_pl29b")
    ap.add_argument("--catalogue", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--blabel", default="")
    ap.add_argument("--alabel", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    global TITLE, BL, AL, NOTE
    TITLE = a.title or TITLE; BL = a.blabel or BL; AL = a.alabel or AL; NOTE = a.note or NOTE
    os.makedirs(a.out, exist_ok=True)
    for ts in TNAME:
        views_sheet(a.before, a.after, ts, "clawfree", os.path.join(a.out, "%s_ba_%s_clawfree.png" % (a.prefix, ts)))
        views_sheet(a.before, a.after, ts, "asis", os.path.join(a.out, "%s_ba_%s_asis.png" % (a.prefix, ts)))
        tt_sheet(a.before, a.after, ts, os.path.join(a.out, "%s_ba_turntable_%s.png" % (a.prefix, ts)))
    if a.catalogue:
        crops_sheet(a.before, a.after, a.catalogue, os.path.join(a.out, "%s_ba_crops.png" % a.prefix))
    print("done")


if __name__ == "__main__":
    main()
