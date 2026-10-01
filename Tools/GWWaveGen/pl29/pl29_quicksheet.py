# -*- coding: utf-8 -*-
"""仕上げ29：作る部の確かめの並べ図（作業用）。PL29Render の views/ の 7 視点（と任意で前の点検の同じ画像）を 1 枚に並べる。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_quicksheet.py <after_dir> <ts> <cond> <out.png> [--before <before_dir>] [--title <文字>]
  ts は t060・t090・t105・t120、cond は clawfree・asis。
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
FONTB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("after")
    ap.add_argument("ts")
    ap.add_argument("cond")
    ap.add_argument("out")
    ap.add_argument("--before")
    ap.add_argument("--title", default="")
    a = ap.parse_args()
    tw, th = 480, 270
    rows = 2 if not a.before else 4
    cols = 4
    W, H = cols * tw, rows * th + 40
    im = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(im)
    d.text((10, 6), a.title or (a.after + " " + a.ts + " " + a.cond), fill=(20, 20, 20), font=font(20, True))
    sets = [("後", a.after)] if not a.before else [("前", a.before), ("後", a.after)]
    for si, (lab, root) in enumerate(sets):
        for k, (v, name) in enumerate(VIEWS):
            p = os.path.join(root, "views", "%s_%s_%s.png" % (v, a.ts, a.cond))
            x, y = (k % 4) * tw, 40 + (si * 2 + k // 4) * th
            if os.path.exists(p):
                im.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
            d.rectangle([x, y, x + 150, y + 24], fill=(20, 20, 20))
            d.text((x + 4, y + 1), lab + "｜" + name, fill=(255, 255, 255), font=font(16, True))
    im.save(a.out)


if __name__ == "__main__":
    main()
