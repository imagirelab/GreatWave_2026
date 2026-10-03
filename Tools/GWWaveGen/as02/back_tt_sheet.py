# -*- coding: utf-8 -*-
"""美術の見本02 BACK：回り台の 12 方位（30° おき）の粘土の静止画を、土台と候補で上下に並べた 1920×1080 の図。py -3.10
usage: back_tt_sheet.py <out.png> <stills_base_dir> <stills_cand_dir> <title> [frames=0,20,...] [lab_base] [lab_cand]
"""
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from back_sheet import font  # noqa: E402

W, H = 1920, 1080


def main():
    out, d0, d1, title = sys.argv[1:5]
    rest = sys.argv[5:]
    frames = [int(x) for x in (rest[0].split(",") if rest and rest[0][0].isdigit() else "0,20,40,60,80,100,120,140,160,180,200,220".split(","))]
    labs = [x for x in rest if not x[0].isdigit()] or ["P28R2rec", "AS02B"]
    img = Image.new("RGB", (W, H), (247, 246, 242))
    dr = ImageDraw.Draw(img)
    dr.text((16, 10), title, fill=(20, 20, 20), font=font(26, True))
    half = len(frames) // 2
    cw = (W - 120) // half
    top = 56
    rh = (H - top - 10) // 4
    for blk in range(2):
        for k, (d, lab) in enumerate(((d0, labs[0]), (d1, labs[1]))):
            r = blk * 2 + k
            y0 = top + r * rh
            dr.text((8, y0 + rh // 2 - 12), lab, fill=(42, 120, 214) if k else (82, 81, 78), font=font(18, True))
            for j, f in enumerate(frames[blk * half:(blk + 1) * half]):
                p = os.path.join(d, "f_%04d.png" % f)
                if not os.path.isfile(p):
                    continue
                im = Image.open(p).convert("RGB")
                s = min((cw - 4) / im.width, (rh - 22) / im.height)
                im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
                x0 = 120 + j * cw
                img.paste(im, (x0, y0 + 18))
                if k == 0:
                    dr.text((x0 + 2, y0), "%d°" % int(round(f * 360 / 240)), fill=(30, 30, 30), font=font(15))
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
