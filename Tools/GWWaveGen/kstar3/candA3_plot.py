# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A3: tiny PIL plotting helper (no matplotlib here): grids of (a, y) section panels."""
from PIL import Image, ImageDraw, ImageFont

FONT = r"C:\Windows\Fonts\Deng.ttf"


def panels(path, title, items, ncol=4, W=470, H=330, xl=(-22.0, 18.0), yl=(-6.0, 23.0), grid=5.0, legend=None):
    """items: list of dict(title=str, lines=[(pts (n,2), (r,g,b), width, dashed?)], marks=[((a,y), (r,g,b), text)])."""
    nrow = (len(items) + ncol - 1) // ncol
    top = 44 + (24 if legend else 0)
    im = Image.new("RGB", (W * ncol, (H + 26) * nrow + top), (250, 250, 248)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 18); f2 = ImageFont.truetype(FONT, 15)
    d.text((8, 8), title, fill=(20, 20, 20), font=f)
    if legend:
        d.text((8, 32), legend, fill=(60, 60, 60), font=f2)
    sx = W / (xl[1] - xl[0]); sy = H / (yl[1] - yl[0])
    for k, it in enumerate(items):
        ox = (k % ncol) * W; oy = top + (k // ncol) * (H + 26)
        g = grid * (int(xl[0] / grid) - 1)
        while g <= xl[1]:
            d.line([(ox + (g - xl[0]) * sx, oy), (ox + (g - xl[0]) * sx, oy + H)], fill=(232, 232, 232))
            g += grid
        g = grid * (int(yl[0] / grid) - 1)
        while g <= yl[1]:
            d.line([(ox, oy + H - (g - yl[0]) * sy), (ox + W, oy + H - (g - yl[0]) * sy)], fill=(232, 232, 232) if abs(g) > 1e-9 else (150, 170, 210))
            g += grid
        d.rectangle([ox, oy, ox + W - 1, oy + H], outline=(200, 200, 200))

        def xy(p):
            return (ox + (p[0] - xl[0]) * sx, oy + H - (p[1] - yl[0]) * sy)
        for ln in it.get("lines", []):
            pts, col, w = ln[0], ln[1], ln[2]
            dashed = len(ln) > 3 and ln[3]
            q = [xy(p) for p in pts]
            if len(q) < 2:
                continue
            if dashed:
                for i in range(0, len(q) - 1, 4):
                    d.line(q[i:i + 2], fill=col, width=w)
            else:
                d.line(q, fill=col, width=w)
        for (p, col, txt) in it.get("marks", []):
            x, y = xy(p); d.ellipse([x - 3, y - 3, x + 3, y + 3], outline=col, width=2)
            if txt:
                d.text((x + 4, y - 16), txt, fill=col, font=f2)
        d.text((ox + 6, oy + 4), it.get("title", ""), fill=(0, 0, 0), font=f2)
        if it.get("note"):
            d.text((ox + 6, oy + H - 20), it["note"], fill=(60, 60, 60), font=f2)
    im.save(path)
    return path
