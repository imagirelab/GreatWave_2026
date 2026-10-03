# -*- coding: utf-8 -*-
"""美術の見本01：描画の画像を 1 枚の並べ図にする（見るための図。1920×1080 の PNG）。
使い方：py -3.10 -B Tools/GWWaveGen/sample01/s01_sheet.py --out <png> --title <文字> [--cols 4] <画像> [<画像> ...]
画像の名前（views/<視点>_<t>_<条件>.png、tt/<t>_az<方位>_<条件>.png）から札を作る。--labels で札を明示してもよい（| 区切り）。
"""
import argparse
import os

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/meiryo.ttc"


def label_of(p):
    b = os.path.splitext(os.path.basename(p))[0]
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="")
    ap.add_argument("--sub", default="")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--labels", default="")
    ap.add_argument("--W", type=int, default=1920)
    ap.add_argument("--H", type=int, default=1080)
    ap.add_argument("imgs", nargs="+")
    a = ap.parse_args()
    labels = a.labels.split("|") if a.labels else [label_of(p) for p in a.imgs]
    n = len(a.imgs)
    cols = a.cols
    rows = (n + cols - 1) // cols
    top = 70 if (a.title or a.sub) else 0
    tw = a.W // cols
    th = int(tw * 9 / 16)
    H = max(a.H, top + rows * th)
    sheet = Image.new("RGB", (a.W, H), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    try:
        f1 = ImageFont.truetype(FONT, 26); f2 = ImageFont.truetype(FONT, 15); f3 = ImageFont.truetype(FONT, 15)
    except Exception:
        f1 = f2 = f3 = ImageFont.load_default()
    if top:
        d.rectangle([0, 0, a.W, top - 4], fill=(28, 34, 48))
        d.text((12, 6), a.title, font=f1, fill=(255, 255, 255))
        d.text((12, 42), a.sub, font=f2, fill=(200, 205, 215))
    for k, p in enumerate(a.imgs):
        im = Image.open(p).convert("RGB").resize((tw - 4, th - 4), Image.LANCZOS)
        x = (k % cols) * tw + 2; y = top + (k // cols) * th + 2
        sheet.paste(im, (x, y))
        lb = labels[k] if k < len(labels) else ""
        tb = d.textbbox((0, 0), lb, font=f3)
        d.rectangle([x + 4, y + 4, x + 12 + tb[2] - tb[0], y + 10 + tb[3] - tb[1]], fill=(20, 20, 20))
        d.text((x + 8, y + 5), lb, font=f3, fill=(255, 255, 255))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.save(a.out)
    print(a.out, sheet.size)


if __name__ == "__main__":
    main()
