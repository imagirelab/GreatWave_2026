# -*- coding: utf-8 -*-
"""仕上げ30 修正の回 1：自己評審の must-fix ごとの前後の切り抜き（前＝作る部の採用 after_r7、後＝修正01 の採用 fix01/r10）と、谷の縁の段の印の図・数。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_sheets.py --r7 Unity/Build/Polish/30/after_r7 --f1 Unity/Build/Polish/30/fix01/r10
        --mask Unity/Build/Polish/30/fix01/r10_diag7 --measure Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json --out Docs/Evidence/Polish/30
出力：fig_pl30_fix01_a.png・fig_pl30_fix01_b.png（項目ごとの切り抜き、上：作る部、下：修正01）、fig_pl30_fix01_trough.png（谷の縁の段の印を重ねた図）、
      pl30_fix01_trough_share.json（谷の縁の段の画素の割合：画面全体と、主役波でない海の画素の中）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画の画像を並べるだけ（新しい描画はしない）。HMD 実機ではない。
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw

from pl30_sheets import font, label, head, tile_fit, fit  # 記録の部：切り抜きの縦横の比を保つ（tile は枠の比へ引き伸ばしていた）

ITEMS_A = [
    ("継ぎ目の点線（左の側面 t 9 s）", "views/side_left_t090_asis.png", (700, 500, 1400, 1080)),
    ("真上 t*：Y の合流・継ぎ目・斑", "views/top_t120_asis.png", (880, 330, 1720, 1000)),
    ("回り台 t* 方位 90°：右の高い波の白", "tt/t120_az090_claws.png", (0, 260, 1920, 1080)),
    ("座席から波の方向 t 10.5 s：右の壁", "views/seat_toward_wave_t105_asis.png", (900, 250, 1920, 1080)),
]
ITEMS_B = [
    ("右の側面 t*：稜の連続と房", "views/side_right_t120_asis.png", (0, 380, 1300, 1000)),
    ("回り台 t 9 s 方位 0°：谷の斑", "tt/t090_az000_claws.png", (0, 250, 1920, 1080)),
    ("原画視点 t*：手前の船の船底", "views/painting_t120_asis.png", (600, 800, 1920, 1080)),
    ("左の側面 t*：細長い白い角", "views/side_left_t120_asis.png", (250, 200, 1450, 900)),
]


def pair_sheet(items, r7, f1, title, sub, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, title, sub)
    tw, th = 474, 498
    for k, (name, rel, crop) in enumerate(items):
        for si, (lab, root) in enumerate((("作る部", r7), ("修正01", f1))):
            x, y = 4 + k * (tw + 4), 66 + si * (th + 6)
            t = tile_fit(os.path.join(root, rel), (tw, th), crop)
            if t is not None:
                im.paste(t, (x, y))
            label(d, x + 4, y + 4, "%s｜%s" % (lab, name), 13)
    im.save(out)
    return out


def trough(f1, mask, measure, out_png, out_json):
    views = [("seat_toward_wave", "座席から波の方向"), ("seat_low", "座席の低い視点"), ("painting", "原画視点"), ("top", "真上")]
    M = json.load(open(measure, encoding="utf-8")) if measure and os.path.exists(measure) else {}
    sid = M.get("seaid", {}).get("after", {})
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 修正01：谷の縁の段（Q16「浪前方缺少自然的凹陷」）｜t* ｜左：作品のまま　右：段の所をマゼンタで重ねた",
         "段＝生成器の谷の縁のうねり pl30_trough_rim の頂の内（継ぎ目〜頂）と頂の外の唇の帯 0.9 m を、藍中の地に藍濃の溝。頂に藍の線と泡の点。印は材質の _PL29Diag = 7（同じ面の座標・同じ式）。Unity の PC 描画。")
    rec = {}
    tw, th = 474, 252
    for k, (v, name) in enumerate(views):
        a = Image.open(os.path.join(f1, "views", "%s_t120_asis.png" % v)).convert("RGB")
        m = np.asarray(Image.open(os.path.join(mask, "views", "%s_t120_clawfree.png" % v)).convert("RGB")).astype(int)
        mk = (m[..., 0] == 255) & (m[..., 1] == 0) & (m[..., 2] == 255)
        ov = np.asarray(a).astype(float).copy()
        ov[mk] = ov[mk] * 0.45 + np.array([255, 0, 255]) * 0.55
        sea_px = (sid.get("%s_t120" % v) or {}).get("sea_px")
        rec[v] = dict(trough_px=int(mk.sum()), frac_of_image=float(mk.mean()), sea_px=sea_px, frac_of_sea=(float(mk.sum()) / sea_px) if sea_px else None)
        col, row = k % 2, k // 2
        x0, y0 = 4 + col * (2 * tw + 12), 70 + row * (th * 2 + 30)
        im.paste(fit(a, (tw, th)), (x0, y0)); im.paste(fit(Image.fromarray(ov.astype(np.uint8)), (tw, th)), (x0 + tw + 4, y0))
        label(d, x0 + 4, y0 + 4, "%s｜作品のまま" % name, 13)
        label(d, x0 + tw + 8, y0 + 4, "%s｜段 %.2f%%（海の画素の中 %s）" % (name, 100 * rec[v]["frac_of_image"], "—" if rec[v]["frac_of_sea"] is None else "%.1f%%" % (100 * rec[v]["frac_of_sea"])), 13)
        # 拡大（下の段：段の多い下半分）
        big = fit(a.crop((0, 540, 1920, 1080)), (tw, th)); bigo = fit(Image.fromarray(ov.astype(np.uint8)).crop((0, 540, 1920, 1080)), (tw, th))
        im.paste(big, (x0, y0 + th + 6)); im.paste(bigo, (x0 + tw + 4, y0 + th + 6))
        label(d, x0 + 4, y0 + th + 10, "下半分の拡大", 12)
    im.save(out_png)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dict(number="仕上げ30 修正01", what_ja="谷の縁の段（材質の _PL29Diag = 7 の印）の画素。t*。sea_px は pl30_measure.py の seaid（主役波でない海の画素）",
                       views=rec), f, ensure_ascii=False, indent=1)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r7", default="Unity/Build/Polish/30/after_r7")
    ap.add_argument("--f1", default="Unity/Build/Polish/30/fix01/r10")
    ap.add_argument("--mask", default="Unity/Build/Polish/30/fix01/r10_diag7")
    ap.add_argument("--measure", default="Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json")
    ap.add_argument("--out", default="Docs/Evidence/Polish/30")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sub = "上：作る部の採用（after_r7）、下：修正01 の採用（fix01/r10）。同じ視点・同じ時刻・作品のまま。Unity 6000.4.3f1 の PC 描画（HMD ではない）。"
    fs = [pair_sheet(ITEMS_A, a.r7, a.f1, "仕上げ30 修正01：自己評審の must-fix の前後（1/2）", sub, os.path.join(a.out, "fig_pl30_fix01_a.png")),
          pair_sheet(ITEMS_B, a.r7, a.f1, "仕上げ30 修正01：自己評審の must-fix の前後（2/2）", sub, os.path.join(a.out, "fig_pl30_fix01_b.png")),
          trough(a.f1, a.mask, a.measure, os.path.join(a.out, "fig_pl30_fix01_trough.png"), os.path.join(a.out, "pl30_fix01_trough_share.json"))]
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
