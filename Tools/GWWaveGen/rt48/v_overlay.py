# -*- coding: utf-8 -*-
"""RT48：細かい元と粗い元の焼いた線を、同じコマ・同じ縮尺（縦横同じ）で重ねて描く（py -3.10、PIL）。C2 の外れの所を見るための確かめの絵。
細かい元（粒子から作った細かい面 0.125 m）を青の塗りと濃い青の線、粗い元（解く格子 0.5 m の面）を橙の線で描く。囲んだ空気は白、離れた水は塗る。
どちらも焼いた曲線（組 k の A、最後のコマは最後の組の B）。手で形を変えない。
使い方: py -3.10 v_overlay.py <出力.png> <コマ:x0:x1:y0:y1>[,...]"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"
FONT = "C:/Windows/Fonts/YuGothM.ttc"


def load(src):
    d = os.path.join(BUILD, "data", src)
    m = json.load(open(os.path.join(d, "manifest.json"), encoding="utf8"))
    P = np.fromfile(os.path.join(d, "pairs.bin"), "<f4").reshape(m["files"]["pairs"]["shape"])
    Lp = np.fromfile(os.path.join(d, "loops.bin"), "<f4").reshape(-1, 2)
    li = {r["frame"]: r["loops"] for r in m["loops_index"]}
    return m, P, Lp, li


def curve(m, P, f):
    p = f - m["time"]["first_frame"]
    c = P[p, 0] if p < P.shape[0] else P[P.shape[0] - 1, 1]
    return np.stack([c[:, 0].astype(float) + m["coords"]["origin_x_rel"], c[:, 1].astype(float)], 1)


def main(outp, spec):
    S = {s: load(s) for s in ("fine", "coarse")}
    panels = [tuple(float(v) for v in q.split(":")) for q in spec.split(",")]
    W = 900
    fnt = ImageFont.truetype(FONT, 18); fs = ImageFont.truetype(FONT, 14)
    tiles = []
    for (f, xa, xb, ya, yb) in panels:
        f = int(f)
        s = W / (xb - xa); H = int((yb - ya) * s) + 60
        img = Image.new("RGB", (W, H), (236, 240, 244)); dr = ImageDraw.Draw(img)
        tp = lambda x, y: ((x - xa) * s, 50 + (yb - y) * s)
        m, P, Lp, li = S["fine"]
        c = curve(m, P, f)
        sel = (c[:, 0] >= xa - 20) & (c[:, 0] <= xb + 20)
        cc = c[sel]
        poly = [tp(x, y) for x, y in cc] + [tp(cc[-1, 0], ya - 5), tp(cc[0, 0], ya - 5)]
        dr.polygon(poly, fill=(120, 165, 200))
        for (o, n, ph, ar) in li.get(f, []):
            q = Lp[o:o + n].astype(float); q[:, 0] += m["coords"]["origin_x_rel"]
            if q[:, 0].max() < xa or q[:, 0].min() > xb:
                continue
            dr.polygon([tp(x, y) for x, y in q], fill=(255, 255, 255) if ph == 1 else (120, 165, 200))
        dr.line([tp(x, y) for x, y in cc], fill=(20, 50, 120), width=2)
        m2, P2, Lp2, li2 = S["coarse"]
        c2 = curve(m2, P2, f); sel2 = (c2[:, 0] >= xa - 20) & (c2[:, 0] <= xb + 20)
        dr.line([tp(x, y) for x, y in c2[sel2]], fill=(230, 120, 20), width=2)
        for (o, n, ph, ar) in li2.get(f, []):
            q = Lp2[o:o + n].astype(float); q[:, 0] += m2["coords"]["origin_x_rel"]
            if q[:, 0].max() < xa or q[:, 0].min() > xb:
                continue
            dr.line([tp(x, y) for x, y in np.vstack([q, q[:1]])], fill=(230, 120, 20), width=2)
        # 1 m の格子
        for xm in range(int(np.ceil(xa)), int(xb) + 1):
            X, _ = tp(xm, 0)
            dr.line([(X, H - 8), (X, H - (14 if xm % 5 == 0 else 10))], fill=(80, 80, 80))
        X0, Y0 = tp(xa + 0.5, ya + 0.5); dr.line([(X0, Y0), (X0 + s, Y0)], fill=(0, 0, 0), width=3); dr.text((X0 + s + 6, Y0 - 9), "1 m", font=fs, fill=(0, 0, 0))
        dr.text((8, 6), "コマ %d（%.3f s）　x %g〜%g m　青の塗りと濃い青の線：細かい元（粒子から作った面 0.125 m）　橙の線：粗い元（解く格子の面 0.5 m）" % (
            f, (f - 1) / 24.0, xa, xb), font=fs, fill=(0, 0, 0))
        dr.text((8, 26), "どちらも焼いた曲線（8,192 点）。縦横同じ縮尺", font=fs, fill=(60, 60, 60))
        tiles.append(img)
    Wt = W; Ht = sum(t.size[1] for t in tiles)
    out = Image.new("RGB", (Wt, Ht), "white"); y = 0
    for t in tiles:
        out.paste(t, (0, y)); y += t.size[1]
    out.save(outp)
    print("saved", outp, out.size)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
