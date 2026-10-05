# -*- coding: utf-8 -*-
"""Q20 final K*': side-by-side sheet of the 9 standard views: columns = given render prefixes (e.g. K* | K*' | ref).
usage: py -3.10 fin_sheet.py out.png "title" dir1:prefix1:label1 dir2:prefix2:label2 ... [--w 560]"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

VIEWS = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
         "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
FONT = r"C:\Windows\Fonts\Deng.ttf"


def main():
    a = sys.argv[1:]
    out, title = a[0], a[1]
    W = int(a[a.index("--w") + 1]) if "--w" in a else 560
    cols = [x for x in a[2:] if x.count(":") >= 2 and not x.startswith("--")]
    cols = [x.rsplit(":", 2) for x in cols]
    f = ImageFont.truetype(FONT, 20); f2 = ImageFont.truetype(FONT, 16)
    tiles = []
    for vn in VIEWS:
        row = []
        for d, pre, lab in cols:
            p = os.path.join(d, "%s__%s.png" % (pre, vn))
            if os.path.isfile(p):
                im = Image.open(p).convert("RGB")
                h = int(im.size[1] * W / im.size[0]); im = im.resize((W, h), Image.LANCZOS)
            else:
                im = Image.new("RGB", (W, int(W * 0.5625)), (200, 200, 200))
            row.append(im)
        tiles.append(row)
    hs = [max(im.size[1] for im in r) for r in tiles]
    Hh = 40 + sum(h + 26 for h in hs)
    sheet = Image.new("RGB", (W * len(cols) + 8 * (len(cols) - 1), Hh), (250, 250, 248))
    d = ImageDraw.Draw(sheet)
    d.text((8, 8), title, fill=(20, 20, 20), font=f)
    y = 40
    for vn, r, h in zip(VIEWS, tiles, hs):
        for k, im in enumerate(r):
            x = k * (W + 8)
            d.text((x + 4, y + 2), "%s | %s" % (vn, cols[k][2]), fill=(30, 30, 30), font=f2)
            sheet.paste(im, (x, y + 24))
        y += h + 26
    sheet.save(out)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
