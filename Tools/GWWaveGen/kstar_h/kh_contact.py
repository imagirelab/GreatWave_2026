# -*- coding: utf-8 -*-
"""kh_bl.py の描画を並べた対照図（行 = 視点、列 = 候補）と、必要なら 2 つの候補の画像の差の統計（py -3.10）。
usage: py -3.10 kh_contact.py <render_dir> <out.png> <label1,label2,...> [views=all|std|user] [cell=560] [--diff]
       py -3.10 kh_contact.py --turntable <stills_dir> <out.png> [cell=320]"""
import os
import sys
import json

sys.dont_write_bytecode = True
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = r"C:\Windows\Fonts\Deng.ttf"


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def views_list(sel):
    VJ = json.load(open(os.path.join(HERE, "kh_views.json"), encoding="utf-8"))
    std = [v["name"] for v in VJ["standard"]]; usr = [v["name"] for v in VJ["user_failure"]]
    return {"all": std + usr, "std": std, "user": usr}.get(sel, sel.split("+"))


def contact(rdir, out, labels, sel="all", cell=560, diff=False):
    views = views_list(sel)
    f = font(22); fs = font(18)
    head = 40; lab_w = 230
    rows = []
    stats = {}
    for v in views:
        ims = []
        for lab in labels:
            p = os.path.join(rdir, "%s__%s.png" % (lab, v))
            ims.append(Image.open(p).convert("RGB") if os.path.isfile(p) else None)
        ok = [im for im in ims if im is not None]
        if not ok:
            continue
        h = int(round(cell * ok[0].height / ok[0].width))
        row = Image.new("RGB", (lab_w + cell * len(labels), h), (255, 255, 255))
        d = ImageDraw.Draw(row)
        d.text((8, h // 2 - 12), v, fill=(0, 0, 0), font=fs)
        for i, im in enumerate(ims):
            if im is not None:
                row.paste(im.resize((cell, h), Image.LANCZOS), (lab_w + i * cell, 0))
        rows.append(row)
        if diff and len(ims) >= 2 and ims[0] is not None and ims[1] is not None:
            a = np.asarray(ims[0], np.int16); b = np.asarray(ims[1], np.int16)
            dd = np.abs(a - b).max(-1)
            stats[v] = {"pixels_diff_gt8": int((dd > 8).sum()), "pixels_diff_gt32": int((dd > 32).sum()), "max": int(dd.max()),
                        "mean": float(dd.mean()), "pixels": int(dd.size)}
    W = lab_w + cell * len(labels)
    H = head + sum(r.height for r in rows)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    for i, lab in enumerate(labels):
        d.text((lab_w + i * cell + 8, 8), lab, fill=(0, 0, 0), font=f)
    y = head
    for r in rows:
        sheet.paste(r, (0, y)); y += r.height
    sheet.save(out)
    if diff:
        json.dump(stats, open(os.path.splitext(out)[0] + "_imgdiff.json", "w"), indent=1)
    return stats


def turntable_sheet(sdir, out, cell=320):
    fs = sorted(x for x in os.listdir(sdir) if x.startswith("f_") and x.endswith(".png"))
    ims = [Image.open(os.path.join(sdir, x)).convert("RGB") for x in fs]
    h = int(round(cell * ims[0].height / ims[0].width))
    cols = 4
    sheet = Image.new("RGB", (cell * cols, h * ((len(ims) + cols - 1) // cols)), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im.resize((cell, h), Image.LANCZOS), ((i % cols) * cell, (i // cols) * h))
    sheet.save(out)


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "--turntable":
        turntable_sheet(a[1], a[2], int(a[3].split("=")[1]) if len(a) > 3 else 320)
    else:
        kw = {k: v for k, v in (x.split("=", 1) for x in a[3:] if "=" in x)}
        s = contact(a[0], a[1], a[2].split(","), kw.get("views", "all"), int(kw.get("cell", 560)), "--diff" in a)
        if s:
            print(json.dumps(s))
