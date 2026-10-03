# -*- coding: utf-8 -*-
"""美術の見本02 BACK：粘土の描画を並べた前後の図（1920×1080、縦横比を保つ）。py -3.10
usage: back_sheet.py <out.png> <render_dir> <title> labels=L1+L2[+L3] views=v1+v2+... [names=名前1+名前2] [vnames=視点名1+...]
行 ＝ 視点、列 ＝ 形（同じカメラ・同じ t*）。粘土（Blender Workbench）で、作品の色・線・白ではない。
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FONT = r"C:\Windows\Fonts\YuGothM.ttc"
FONTB = r"C:\Windows\Fonts\YuGothB.ttc"


def font(sz, bold=False):
    for p in ((FONTB if bold else FONT), r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    out, rdir, title = sys.argv[1], sys.argv[2], sys.argv[3]
    opt = dict(a.split("=", 1) for a in sys.argv[4:])
    labels = opt["labels"].split("+")
    views = opt["views"].split("+")
    names = opt.get("names", opt["labels"]).split("+")
    vnames = opt.get("vnames", opt["views"]).split("+")
    img = Image.new("RGB", (W, H), (250, 249, 245))
    dr = ImageDraw.Draw(img)
    dr.text((16, 10), title, fill=(20, 20, 20), font=font(26, True))
    top = 52
    if opt.get("note"):
        dr.text((16, 48), opt["note"], fill=(82, 81, 78), font=font(17))
        top = 80
    lw = 150
    nr, nc = len(views), len(labels)
    cw = (W - lw - 10) // nc
    rh = (H - top - 40) // nr
    for ci, n in enumerate(names):
        dr.text((lw + ci * cw + 8, top - 2), n, fill=(30, 30, 30), font=font(20, True))
    top += 26
    rh = (H - top - 8) // nr
    for ri, v in enumerate(views):
        y0 = top + ri * rh
        dr.text((8, y0 + rh // 2 - 12), vnames[ri], fill=(30, 30, 30), font=font(18))
        for ci, lab in enumerate(labels):
            p = os.path.join(rdir, "%s__%s.png" % (lab, v))
            if not os.path.isfile(p):
                continue
            im = Image.open(p).convert("RGB")
            s = min((cw - 6) / im.width, (rh - 6) / im.height)
            im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
            x0 = lw + ci * cw + (cw - im.width) // 2
            img.paste(im, (x0, y0 + (rh - im.height) // 2))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
