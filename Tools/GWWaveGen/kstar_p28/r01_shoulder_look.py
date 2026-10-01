# -*- coding: utf-8 -*-
"""仕上げ28修正01 SHOULDER：候補を Blender の粘土（rays_bl.py = kh_bl.py、Workbench）で描き、視点 × 候補の並べ図を作る（目で見る用）。
usage: py -3.10 r01_shoulder_look.py <out_dir> <sheet.png> views=v1+v2 label=gwb [label=gwb ...] [w=640]
"""
import os
import sys
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
BL = os.path.join(HERE, "rays_bl.py")


def font(sz):
    for p in (r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def main():
    out, sheet = sys.argv[1], sys.argv[2]
    opts = dict(a.split("=", 1) for a in sys.argv[3:] if a.split("=", 1)[0] in ("views", "w", "title", "render"))
    items = [a.split("=", 1) for a in sys.argv[3:] if a.split("=", 1)[0] not in ("views", "w", "title", "render")]
    views = opts.get("views", "b65_back65_clay+b65z_back65_zoom+b90_back_straight+b115_back_minus_c")
    w = int(opts.get("w", "640"))
    os.makedirs(out, exist_ok=True)
    if opts.get("render", "1") == "1":
        arg = ",".join("%s=%s" % (l, p) for l, p in items)
        cmd = [BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", BL, "--", "views", out, arg, "views=" + views]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:])
            raise SystemExit(1)
    vs = views.split("+")
    tiles = []
    f = font(18)
    for v in vs:
        row = []
        for lab, _ in items:
            p = os.path.join(out, "%s__%s.png" % (lab, v))
            im = Image.open(p).convert("RGB")
            im = im.resize((w, int(im.size[1] * w / im.size[0])))
            d = ImageDraw.Draw(im)
            d.rectangle([0, 0, w, 24], fill=(0, 0, 0))
            d.text((6, 2), "%s | %s" % (lab, v), fill=(255, 230, 0), font=f)
            row.append(im)
        tiles.append(row)
    hmax = [max(t.size[1] for t in row) for row in tiles]
    title = opts.get("title", "")
    th = 30 if title else 0
    W = Image.new("RGB", (w * len(items), sum(hmax) + th), (255, 255, 255))
    if title:
        ImageDraw.Draw(W).text((8, 4), title, fill=(0, 0, 0), font=f)
    y = th
    for row, h in zip(tiles, hmax):
        for k, t in enumerate(row):
            W.paste(t, (k * w, y))
        y += h
    os.makedirs(os.path.dirname(sheet), exist_ok=True)
    W.save(sheet)
    print("sheet", sheet, W.size)


if __name__ == "__main__":
    main()
