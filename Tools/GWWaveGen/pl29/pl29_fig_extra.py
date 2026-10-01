# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の作る部の図（1920×1080）2 枚：
  fig_pl29b_painting_compare.png：原画視点 t* の比べ（原画の色区の地図｜前｜後）と、白・淡い水色と藍の一致の地図（前・後）と数。
  fig_pl29b_playmode_release.png：PL29_Release（DS50_Release の写し）を Editor の Play モードで通した時の、船の HMD カメラ（PC の画面）の 4 時刻。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_fig_extra.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/after/p29d
         --playmode Unity/Build/Polish/29/after/playmode_release --out <dir>
"""
import argparse
import glob
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
F = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
F2 = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
LABELS = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels.png")


def lab(d, x, y, t, sz=15):
    f = ImageFont.truetype(F, sz)
    w = d.textlength(t, font=f) + 12
    d.rectangle([x, y, x + w, y + sz + 10], fill=(20, 20, 20))
    d.text((x + 6, y + 3), t, fill=(255, 255, 255), font=f)


def ids(p):
    a = np.array(Image.open(p).convert("RGBA")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    c = np.full(r.shape, 0)
    c[(r > 200) & (g < 50) & (b < 50)] = 1
    c[(r < 50) & (g > 200) & (b < 50)] = 2
    c[(r < 50) & (g < 50) & (b > 200)] = 3
    c[(r > 200) & (g > 200) & (b < 50)] = 4
    return c


def painting_compare(before, after, out):
    L = np.array(Image.open(LABELS).convert("L"))
    pal = {0: (249, 232, 196), 1: (248, 243, 223), 2: (198, 215, 203), 3: (44, 105, 147), 4: (35, 64, 97), 5: (71, 80, 95), 9: (249, 232, 196)}
    C = np.zeros(L.shape + (3,), np.uint8)
    for k, v in pal.items():
        C[L == k] = v
    box = (130, 60, 1170, 860)
    tiles = [("原画の色区（美術優先28 の色区の地図、表示フレーム）", Image.fromarray(C)),
             ("前｜投影の焼き込み（t*、作品のまま）", Image.open(os.path.join(before, "views", "painting_t120_asis.png"))),
             ("後｜視点によらない立体の材質（t*、作品のまま）", Image.open(os.path.join(after, "views", "painting_t120_asis.png")))]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 1920, 62], fill=(28, 36, 52))
    d.text((14, 4), "仕上げ29（Q28）｜原画視点 t* の比べ：原画の色区｜前｜後", fill=(255, 255, 255), font=ImageFont.truetype(F, 24))
    d.text((14, 38), "後の色は面の座標・高さ・面の向き・T_white だけで決め、原画カメラからの投影を使わない。前後の主役波の形と動きは同じ（K*′ P28R2rec・G_p28rec）。Unity の PC 描画（HMD ではない）。",
           fill=(205, 212, 225), font=ImageFont.truetype(F2, 15))
    tw = 632
    th = int(tw * (box[3] - box[1]) / (box[2] - box[0]))
    for k, (t, a) in enumerate(tiles):
        x, y = 4 + k * (tw + 6), 72
        im.paste(a.convert("RGB").crop(box).resize((tw, th), Image.LANCZOS), (x, y))
        lab(d, x, y, t)
    res = {}
    for k, (nm, p) in enumerate([("前", os.path.join(before, "diag", "painting_t120_id_claws1.png")), ("後", os.path.join(after, "diag", "painting_t120_id_claws1.png"))]):
        Cc = ids(p)
        m = (L >= 1) & (L <= 4) & (Cc >= 1)
        W1 = np.isin(Cc, [1, 2]); W2 = np.isin(L, [1, 2])
        o = np.full(L.shape + (3,), 238, np.uint8)
        o[m & (W1 == W2)] = (150, 190, 150); o[m & W2 & ~W1] = (210, 70, 60); o[m & ~W2 & W1] = (60, 90, 210)
        o[(L >= 1) & (L <= 4) & ~m] = (200, 200, 200)
        x, y = 4 + (k + 1) * (tw + 6), 72 + th + 10
        im.paste(Image.fromarray(o).crop(box).resize((tw, th), Image.NEAREST), (x, y))
        lab(d, x, y, nm + "｜白・淡い水色と藍の一致（緑 一致、赤 原画は白で描画は藍、青 原画は藍で描画は白、灰 主役波が隠れる）", 13)
        valid = m
        res[nm] = {"白と藍の一致": round(float(((W1 == W2) & valid).sum() / valid.sum()), 3), "色区の一致": round(float(((Cc == L) & valid).sum() / valid.sum()), 3)}
        for kk, n in [(1, "白"), (2, "淡い水色"), (3, "藍中"), (4, "藍濃")]:
            mm = (L >= 1) & (L <= 4)
            a_ = (Cc == kk) & mm; b_ = (L == kk) & mm
            res[nm][n] = {"iou": round(float((a_ & b_).sum() / max((a_ | b_).sum(), 1)), 3), "render": round(float(a_.sum() / mm.sum()), 3), "painting": round(float(b_.sum() / mm.sum()), 3)}
    a = res["後"]; b = res["前"]
    txt = ["原画視点 t* の色区の一致（爪あり）",
           "前（投影）：白と藍の一致 %.3f、色区の一致 %.3f" % (b["白と藍の一致"], b["色区の一致"]),
           "後（立体の材質）：白と藍の一致 %.3f、色区の一致 %.3f" % (a["白と藍の一致"], a["色区の一致"]),
           "面積の割合（後／原画）：",
           "　白 %.3f／%.3f、淡い水色 %.3f／%.3f" % (a["白"]["render"], a["白"]["painting"], a["淡い水色"]["render"], a["淡い水色"]["painting"]),
           "　藍中 %.3f／%.3f、藍濃 %.3f／%.3f" % (a["藍中"]["render"], a["藍中"]["painting"], a["藍濃"]["render"], a["藍濃"]["painting"]),
           "IoU（後）：白 %.2f、淡い水色 %.2f、藍中 %.2f、藍濃 %.2f" % (a["白"]["iou"], a["淡い水色"]["iou"], a["藍中"]["iou"], a["藍濃"]["iou"]),
           "色区の項目 73〜270 は投影をやめたので値が動く",
           "（新しい読みとして記録。投影に戻して追わない）。",
           "輪郭の関門 78・130・131・132・72 は前と同じ値。"]
    y = 72 + th + 12
    for i, t in enumerate(txt):
        d.text((14, y + i * 28), t, fill=(20, 20, 20), font=ImageFont.truetype(F if i == 0 else F2, 15))
    im.save(out)
    return res


def playmode(pdir, out):
    fs = sorted(glob.glob(os.path.join(pdir, "pl29_playmode_hmd_t*.png")))
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    for k, f in enumerate(fs[:4]):
        a = Image.open(f).convert("RGB")
        x, y = (k % 2) * 960, (k // 2) * 540
        im.paste(a, (x, y))
        lab(d, x + 6, y + 6, "PL29_Release（DS50_Release の写し）の Play モード｜船の HMD カメラ（PC の画面）｜大波の時刻 " + os.path.basename(f).split("_T")[1].replace(".png", "") + " s")
    im.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--playmode", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    r = painting_compare(a.before, a.after, os.path.join(a.out, "fig_pl29b_painting_compare.png"))
    playmode(a.playmode, os.path.join(a.out, "fig_pl29b_playmode_release.png"))
    with open(os.path.join(a.out, "painting_match.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    print("done")


if __name__ == "__main__":
    main()
