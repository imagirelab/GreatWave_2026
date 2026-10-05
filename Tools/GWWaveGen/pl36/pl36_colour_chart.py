# -*- coding: utf-8 -*-
"""仕上げ36：色票（設計36 の ds36_colour_chart.csv と同じ考え方）を、Q28 の 7 視点 × 4 時刻の作品のままの描画で作り直す（記録）。

調色板は主役波の材質 PL36_Ukiyoe_Hero.mat の _White・_Mizuiro・_AiMid・_AiDark・_LineCol（仕上げ29 と同じ値。海の材質 PL30 はこの値を写す）と、
爪の材質（PL29 Claw Shade、pl32_claw_params.txt）の淡い水色。描画の画素を CIELAB で最も近い調色板の色へ分け（ΔE00 が 10 を超える画素は「調色板の外」）、
領域ごとに割合を数える。領域は PL36Render の ids の段の画像から：
  主役波＝爪ありの主役波の印（_PL29Diag 1、アルファ 128）、爪＝爪ありと爪なしで色区 ID が違う画素、ほか＝それ以外（海・空・船・飛沫・富士）。
出力：<out>/pl36_colour_chart.csv・pl36_colour_chart.json・fig_pl36_colour_chart.png（1920×1080）
使い方：py -3.10 -B Tools/GWWaveGen/pl36/pl36_colour_chart.py --run before,Unity/Build/Polish/35/r_after,Unity/Build/Polish/36/r_before --run after,Unity/Build/Polish/36/r_after,Unity/Build/Polish/36/r_after --out Docs/Evidence/Polish/36
  （--run 名前,作品のままの描画のフォルダー,ids の段のフォルダー）
"""
import argparse
import csv
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, head  # noqa: E402

PALETTE = [("白", "white", (248, 243, 223)), ("淡い水色（主役波・海）", "mizuiro", (198, 215, 203)), ("淡い水色（爪）", "mizuiro_claw", (203, 215, 206)),
           ("藍中", "ai_mid", (44, 105, 147)), ("藍濃", "ai_dark", (35, 64, 97)), ("藍の線", "line", (71, 80, 95))]
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", 6.0), ("t090", 9.0), ("t105", 10.5), ("t120", 12.0)]


def srgb_to_lab(rgb):
    c = rgb.astype(np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116.0)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def de76(a, b):
    return np.sqrt(((a - b) ** 2).sum(-1))


PL = srgb_to_lab(np.array([p[2] for p in PALETTE], np.float64))


def classify(img):
    lab = srgb_to_lab(img.reshape(-1, 3))
    d = np.stack([de76(lab, PL[i]) for i in range(len(PALETTE))], -1)
    k = d.argmin(-1)
    k[d.min(-1) > 10.0] = -1
    return k.reshape(img.shape[:2]), lab.reshape(img.shape[:2] + (3,))


def regions(ids_dir, v, ts):
    a1 = np.asarray(Image.open(os.path.join(ids_dir, "diag", "%s_%s_id_claws1.png" % (v, ts))).convert("RGB")).astype(np.int32)
    a0 = np.asarray(Image.open(os.path.join(ids_dir, "diag", "%s_%s_id_claws0.png" % (v, ts))).convert("RGB")).astype(np.int32)
    h1 = np.asarray(Image.open(os.path.join(ids_dir, "diag", "%s_%s_hero_claws1.png" % (v, ts))).convert("RGBA"))[..., 3].astype(int)
    hero = np.abs(h1 - 128) < 3
    claws = (np.abs(a1 - a0).sum(-1) > 0) & ~hero
    return {"hero": hero, "claws": claws, "other": ~hero & ~claws}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rows, js = [], {"palette": [{"name_ja": p[0], "key": p[1], "srgb": p[2], "hex": "#%02X%02X%02X" % p[2], "L": round(float(PL[i][0]), 2)} for i, p in enumerate(PALETTE)],
                    "rule_ja": __doc__.strip().split("\n\n")[0], "runs": {}}
    for item in a.run:
        name, rdir, idir = item.split(",")
        js["runs"][name] = {"render": rdir, "ids": idir, "rows": []}
        for v, vn in VIEWS:
            for ts, t in TS:
                p = os.path.join(rdir, "views", "%s_%s_asis.png" % (v, ts))
                if not os.path.exists(p):
                    continue
                img = np.asarray(Image.open(p).convert("RGB"))
                k, lab = classify(img)
                regs = regions(idir, v, ts)
                for rn, m in regs.items():
                    n = int(m.sum())
                    if n == 0:
                        continue
                    r = {"run": name, "view": v, "t": t, "region": rn, "px": n, "frame_share_pct": round(100.0 * n / m.size, 3)}
                    for i, pp in enumerate(PALETTE):
                        r["share_%s_pct" % pp[1]] = round(100.0 * float((k[m] == i).mean()), 2)
                    r["share_off_palette_pct"] = round(100.0 * float((k[m] == -1).mean()), 2)
                    r["mean_L"] = round(float(lab[..., 0][m].mean()), 2)
                    rows.append(r)
                    js["runs"][name]["rows"].append(r)
    keys = list(rows[0].keys())
    with open(os.path.join(a.out, "pl36_colour_chart.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    with open(os.path.join(a.out, "pl36_colour_chart.json"), "w", encoding="utf-8") as f:
        json.dump(js, f, ensure_ascii=False, indent=1)
    # 図：調色板の見本と、t* と t 10.5 s の主役波・爪の割合の帯（前・後）
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ36 色票｜調色板（主役波・海・爪で共通の限定色）と、7 視点の主役波・爪の色の割合（前＝仕上げ35、後＝仕上げ36）",
         "描画（Unity の PC オフスクリーン描画、作品のまま）の画素を CIELAB で最も近い調色板の色へ分けた（ΔE76 > 10 は調色板の外）。領域は ids の段の画像から。")
    f20, f15, f13 = font(20), font(15), font(13)
    x = 14
    for i, p in enumerate(PALETTE):
        d.rectangle([x, 74, x + 90, 134], fill=p[2], outline=(60, 60, 60))
        d.text((x + 98, 76), p[0], fill=(30, 36, 50), font=f15)
        d.text((x + 98, 98), "sRGB %d,%d,%d  %s" % (p[2] + ("#%02X%02X%02X" % p[2],)), fill=(30, 36, 50), font=f13)
        d.text((x + 98, 116), "L* %.1f" % PL[i][0], fill=(30, 36, 50), font=f13)
        x += 312
    cols = [p[2] for p in PALETTE] + [(200, 80, 200)]
    y0 = 150
    bw = 380
    hdr = ["視点", "時刻", "領域"]
    d.text((14, y0), "帯：白｜淡い水色（主役波）｜淡い水色（爪）｜藍中｜藍濃｜線｜調色板の外（マゼンタ）。帯の右の数は％（白／淡い水色の計／藍中＋藍濃）", fill=(30, 36, 50), font=f15)
    for j, nm in enumerate(list(js["runs"].keys())[:2]):
        d.text((330 + j * (bw + 200), y0 + 22), {"before": "前（仕上げ35）", "after": "後（仕上げ36）"}.get(nm, nm), fill=(30, 36, 50), font=f15)
    y = y0 + 46
    for v, vn in VIEWS:
        for ts, t in (("t105", 10.5), ("t120", 12.0)):
            for rn, rj in (("hero", "主役波"), ("claws", "爪")):
                d.text((14, y + 2), "%s｜t %s｜%s" % (vn, ("%.1f" % t).rstrip("0").rstrip("."), rj), fill=(30, 36, 50), font=f13)
                for j, name in enumerate(list(js["runs"].keys())[:2]):
                    rr = [r for r in js["runs"][name]["rows"] if r["view"] == v and r["t"] == t and r["region"] == rn]
                    xx = 330 + j * (bw + 200)
                    if not rr:
                        continue
                    r = rr[0]
                    shares = [r["share_%s_pct" % p[1]] for p in PALETTE] + [r["share_off_palette_pct"]]
                    cx = xx
                    for s, c in zip(shares, cols):
                        wpx = int(round(bw * s / 100.0))
                        if wpx > 0:
                            d.rectangle([cx, y, cx + wpx, y + 12], fill=c)
                        cx += wpx
                    d.text((xx + bw + 8, y - 1), "%.0f／%.0f／%.0f" % (shares[0], shares[1] + shares[2], shares[3] + shares[4]), fill=(30, 36, 50), font=f13)
                y += 16
        y += 2
    fn = ("爪の領域は、爪ありと爪なしで色区 ID が違う画素（主役波の外）。地と同じ色区の爪の画素（白い地の上の白い爪）は数えないので、前は爪の画素が少なく、"
          "淡い水色に寄る。後は藍・淡い水色の地の上の白い爪も数える（爪が地から分かれて見える画素の量でもある）。")
    yy = y + 10
    for i0 in range(0, len(fn), 80):
        d.text((14, yy), fn[i0:i0 + 80], fill=(30, 36, 50), font=f15)
        yy += 21
    p = os.path.join(a.out, "fig_pl36_colour_chart.png")
    im.save(p)
    print(p, len(rows))


if __name__ == "__main__":
    main()
