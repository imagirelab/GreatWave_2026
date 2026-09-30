# -*- coding: utf-8 -*-
"""仕上げ27：Unity の PC オフスクリーン描画（設計27 の DS27Formation、同じ場面・同じ再生器・同じ τ(t)・同じ視点と時刻）で、
直す前（28修正01 の F_final の描画 Unity/Build/Design/28R01F/unity/F_final）と後（F_p27、Unity/Build/Polish/27/unity/F_p27）を並べ、
画素の差を数える。図は 1920×1080：原画視点と左の側面の τ −1.700 s（差の最も大きい時刻の一つ）、原画視点の t*。差の画像は差を 5 倍にした。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_unity.py
"""
import hashlib
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
A = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "unity", "F_final", "stills")
B = os.path.join(REPO, "Unity", "Build", "Polish", "27", "unity", "F_p27", "stills")
OUT = os.path.join(REPO, "Docs", "Evidence", "Polish", "27")
FONT = "C:/Windows/Fonts/YuGothM.ttc"
NAMES = ("t03_tau-4.889", "t05_tau-3.202", "t065_tau-2.450", "t08_tau-1.700", "t095_tau-0.950", "t11_tau-0.203", "tstar_tau+0.000")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    rec = dict(schema="GreatWave.pl27.unity_before_after/1", before=rel(A), after=rel(B),
               evidence_kind_ja="Unity 6000.4.3f1 Editor の batchmode の PC オフスクリーン描画（DS27Formation.RenderOnly、16 bit だけを読む再生器）。HMD 実機ではない",
               diffs={})
    for v in ("painting", "seat", "side_left"):
        for n in NAMES:
            f = "ds27_%s_%s.png" % (v, n)
            a = np.asarray(Image.open(os.path.join(A, f)).convert("RGB")).astype(int)
            b = np.asarray(Image.open(os.path.join(B, f)).convert("RGB")).astype(int)
            d = np.abs(a - b).max(-1)
            m = d > 8
            rec["diffs"]["%s %s" % (v, n)] = dict(px_diff_gt0=int((d > 0).sum()), px_diff_gt8=int(m.sum()), max=int(d.max()),
                                                  bbox_gt8=[int(np.nonzero(m)[1].min()), int(np.nonzero(m)[0].min()), int(np.nonzero(m)[1].max()), int(np.nonzero(m)[0].max())] if m.any() else None,
                                                  before_sha256=sha(os.path.join(A, f)), after_sha256=sha(os.path.join(B, f)))
    W, H = 1920, 1080
    cw, ch = 560, 315
    sheet = Image.new("RGB", (W, H), (245, 241, 230))
    dr = ImageDraw.Draw(sheet)
    f1 = ImageFont.truetype(FONT, 24)
    f2 = ImageFont.truetype(FONT, 19)
    dr.text((24, 8), "仕上げ27：num_balance_swell_calm・num_sea_sample_range の前後（Unity、同じ視点・同じ τ）。左：直す前 F_final、中：直した後 F_p27、右：差 ×5",
            fill=(20, 30, 60), font=f1)
    gx = (W - 3 * cw) // 4
    xs = [gx, 2 * gx + cw, 3 * gx + 2 * cw]
    rows = [("painting", "t08_tau-1.700", "原画視点（PaintingCam v1）τ −1.700 s"), ("side_left", "t08_tau-1.700", "左の側面（波の枠とともに動く）τ −1.700 s"),
            ("painting", "tstar_tau+0.000", "原画視点 t*（τ = 0）")]
    for i, (v, n, lab) in enumerate(rows):
        y = 78 + i * (ch + 28)
        f = "ds27_%s_%s.png" % (v, n)
        a = Image.open(os.path.join(A, f)).convert("RGB")
        b = Image.open(os.path.join(B, f)).convert("RGB")
        d = np.clip(np.abs(np.asarray(a).astype(int) - np.asarray(b).astype(int)) * 5, 0, 255).astype(np.uint8)
        di = Image.fromarray(255 - d.max(-1)).convert("RGB")
        st = rec["diffs"]["%s %s" % (v, n)]
        dr.text((xs[0], y - 26), lab + "：差 > 8 の画素 %d（最大 %d/255）" % (st["px_diff_gt8"], st["max"]), fill=(20, 30, 60), font=f2)
        for k, im in enumerate((a, b, di)):
            sheet.paste(im.resize((cw, ch), Image.LANCZOS), (xs[k], y))
            if k == 2 and st["bbox_gt8"]:
                x0, y0, x1, y1 = st["bbox_gt8"]
                s = cw / 1920.0
                dr.rectangle([xs[k] + x0 * s - 6, y + y0 * s - 6, xs[k] + x1 * s + 6, y + y1 * s + 6], outline=(220, 40, 40), width=3)
    p = os.path.join(OUT, "fig_pl27_unity_before_after.png")
    sheet.save(p, optimize=True)
    rec["figure"] = dict(path=rel(p), sha256=sha(p))
    with open(os.path.join(REPO, "Unity", "Build", "Polish", "27", "unity", "unity_before_after.json"), "w", encoding="utf-8", newline="\n") as fo:
        json.dump(rec, fo, ensure_ascii=False, indent=1)
    print("図", rel(p))


if __name__ == "__main__":
    main()
