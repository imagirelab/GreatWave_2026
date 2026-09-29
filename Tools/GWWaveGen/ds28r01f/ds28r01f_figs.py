# -*- coding: utf-8 -*-
"""設計28修正01 試行F：パッケージの行の断面を時刻ごとに重ねた図（PIL。粘土の描画ではない、形の確かめ用）。生成器のコードは読まない。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_figs.py --package <パッケージ> --kstar <K* のフォルダー> --out <png>
      [--rows main,peak,140,144,233] [--taus -3,-2.5,-2,-1.6,-1.2,-0.8,-0.4,0] [--label F_R2]
行は番号か main（meta の主断面）・peak（c = +3.85 m に最も近い行）。
"""
import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GW, "..", ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d", "ds28r01e"):
    sys.path.insert(0, os.path.join(GW, sub))
sys.path.insert(0, HERE)

COLS = [(200, 0, 0), (230, 120, 0), (150, 150, 0), (0, 150, 0), (0, 150, 150), (0, 0, 220), (140, 0, 200), (0, 0, 0), (120, 120, 120)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rows", default="main,peak,140,144,233")
    ap.add_argument("--taus", default="-3,-2.5,-2,-1.6,-1.2,-0.8,-0.4,0")
    ap.add_argument("--label", default="")
    ap.add_argument("--box", default="-30,25,-6,24")
    a = ap.parse_args()
    from PIL import Image, ImageDraw, ImageFont
    import ds28r01d_gates as DGW
    import ds28r01e_review as RE
    d = DGW.patch_kstar(a.kstar)
    ks = DGW.DG.KStar(d)
    pkg = a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package)
    pk = RE.FinePackage(pkg, ks, fine=True)
    rows = []
    for s in a.rows.split(","):
        if s == "main":
            rows.append(int(ks.main_row))
        elif s == "peak":
            rows.append(int(np.argmin(np.abs(ks.c - 3.85))))
        else:
            rows.append(int(s))
    taus = [float(x) for x in a.taus.split(",")]
    x0, x1, y0, y1 = [float(v) for v in a.box.split(",")]
    s = 14.0
    W, H = int((x1 - x0) * s), int((y1 - y0) * s)
    f = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 16)
    img = Image.new("RGB", (W * len(rows), H + 40), "white")
    dr = ImageDraw.Draw(img)
    secs = {}
    for t in taus:
        X = np.asarray(pk.local(t), float)
        secs[t] = (X @ ks.t, X[..., 1])
    for k, r in enumerate(rows):
        ox = k * W
        for gx in range(int(x0), int(x1) + 1, 5):
            dr.line([(ox + (gx - x0) * s, 0), (ox + (gx - x0) * s, H)], fill=(232, 232, 232))
        for gy in range(int(y0), int(y1) + 1, 5):
            dr.line([(ox, H - (gy - y0) * s), (ox + W, H - (gy - y0) * s)], fill=(232, 232, 232))
        for i, t in enumerate(taus):
            A, Y = secs[t]
            P = [(ox + (aa - x0) * s, H - (yy - y0) * s) for aa, yy in zip(A[r], Y[r])]
            dr.line(P, fill=COLS[i % len(COLS)], width=1)
            dr.text((ox + 6, 4 + 18 * i), "τ %+.2f" % t, font=f, fill=COLS[i % len(COLS)])
        dr.line([(ox + W - 1, 0), (ox + W - 1, H + 40)], fill=(0, 0, 0))
        dr.text((ox + 8, H + 10), "%s 行 %d（c %+.2f m）" % (a.label, r, ks.c[r]), font=f, fill=(0, 0, 0))
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print(out)


if __name__ == "__main__":
    main()
