# -*- coding: utf-8 -*-
"""Q21: the user's failure viewpoints, loop-2 K*' (left, what the user rejected) vs candidate A3b (right).
usage: py -3.10 candA3b_usersheet.py out.png <loop2_dir> <a3b_dir>"""
import sys, os
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\Deng.ttf"
ROWS = [("u11_v9zoom_crest_bulge", "user_img11: V9 (az 30, el 25) zoomed on the crest - loop-2 central bulge"),
        ("u12a_v5_back_three_quarter", "user_img12 top: V5 back three-quarter"),
        ("v6_top_down", "user_img12 bottom: V6 top-down - loop-2 bulge on the right pulled backwards"),
        ("u13_v8zoom_b_region", "user_img13: V8 (az 290, el 5) zoomed on the b region (red circle)"),
        ("u10_foot_zoom", "user_img10: the foot / trough junction")]


def main(out, d1, d2):
    w, h = 720, 520
    im = Image.new("RGB", (2 * w + 10, 40 + len(ROWS) * (h + 30)), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 20); f2 = ImageFont.truetype(FONT, 16)
    d.text((8, 8), "Q21 failure viewpoints: left = loop-2 K*' (rejected by the user), right = candidate A3b (same camera, clay, light)", fill=(0, 0, 0), font=f)
    for k, (v, lab) in enumerate(ROWS):
        y = 40 + k * (h + 30)
        d.text((8, y + 4), lab, fill=(30, 30, 30), font=f2)
        for i, (dd, pre) in enumerate(((d1, "kstarF"), (d2, "A3b"))):
            p = os.path.join(dd, "%s__%s.png" % (pre, v))
            if os.path.isfile(p):
                a = Image.open(p).convert("RGB")
                s = min(w / a.size[0], h / a.size[1])
                a = a.resize((int(a.size[0] * s), int(a.size[1] * s)), Image.LANCZOS)
                im.paste(a, (i * (w + 10), y + 26))
    im.save(out); print(out, im.size)


if __name__ == "__main__":
    main(*sys.argv[1:4])
