# -*- coding: utf-8 -*-
"""仕上げ30 修正の回 2：自己評審の must-fix（7 件）ごとの前後の切り抜き（前＝修正01 の採用 fix01/r10、後＝修正02 の採用）と、
富士の雪の画素（t 5〜12 s の全部のコマ）・主役波の尾の刃の出所（左の側面 t* の主役波の印）の図。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_sheets.py --f1 Unity/Build/Polish/30/fix01/r10 --f2 Unity/Build/Polish/30/fix02/r_final
        --fuji Unity/Build/Polish/30/fix02/fuji_final --fuji-f1 Unity/Build/Polish/30/fix02/fuji_f1 --mask Unity/Build/Polish/30/fix02/r_final_diag7 --out Docs/Evidence/Polish/30
出力：fig_pl30_fix02_a.png・fig_pl30_fix02_b.png（項目ごとの切り抜き、上：修正01、下：修正02）、fig_pl30_fix02_fuji.png（富士の雪の画素の時刻の列）、
      fig_pl30_fix02_tail.png（左の側面 t* の主役波の尾の刃：作品のままと主役波の印）、pl30_fix02_fuji.json・pl30_fix02_trough_share.json。
      記録の部で足したもの：fig_pl30_record_review.png（修正02 の採用を全解像度で切り抜いた残る見え方）。切り抜きはどれも縦横の比を保つ（tile_fit・fit）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画の画像を並べ・数えるだけ（新しい描画はしない）。HMD 実機ではない。
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw

from pl30_sheets import font, label, head, tile_fit, fit  # 記録の部：切り抜きの縦横の比を保つ（tile は枠の比へ引き伸ばしていた）

ITEMS_A = [
    ("1 原画視点 t 6 s：形成の途中の白い刃", "views/painting_t060_asis.png", (120, 640, 620, 880)),
    ("1 原画視点 t 9 s：白い筋", "views/painting_t090_asis.png", (620, 740, 1060, 900)),
    ("1・2 回り台 t 6 s 方位 0°：平らな刃と触手", "tt/t060_az000_claws.png", (700, 380, 1900, 1080)),
    ("2 原画視点 t*：小波の頂の三日月", "views/painting_t120_asis.png", (600, 590, 900, 760)),
]
ITEMS_B = [
    # 記録の部：縦横の比を保つ図にしたので、右の高い波の房の所を枠に近い比で切り抜く（元は (0, 540, 1920, 1080)・(0, 520, 1100, 1080) を枠へ引き伸ばしていた）
    ("3 回り台 t* 方位 90°：右の高い波の白（x 1000〜1520）", "tt/t120_az090_claws.png", (1000, 560, 1520, 1080)),
    ("3 回り台 t* 方位 120°（x 0〜560）", "tt/t120_az120_claws.png", (0, 520, 560, 1080)),
    ("4 原画視点 t*：水平線の白い楔", "views/painting_t120_asis.png", (960, 700, 1420, 870)),
    ("4・5 右の側面 t*：白い稜の一続きと鞍", "views/side_right_t120_asis.png", (0, 300, 1300, 900)),
]
ITEMS_C = [
    ("4・5 真上 t*：Y の白い稜", "views/top_t120_asis.png", (880, 330, 1720, 1000)),
    ("6 真上 t*：谷の縁の段の端", "views/top_t120_asis.png", (660, 560, 900, 720)),
    ("2 真上 t*：小波の白の中の輪", "views/top_t120_asis.png", (740, 620, 900, 760)),
    ("3 回り台 t 10.5 s 方位 60°", "tt/t105_az060_claws.png", (0, 200, 1920, 1080)),
]


def pair_sheet(items, f1, f2, title, sub, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, title, sub)
    tw, th = 474, 498
    for k, (name, rel, crop) in enumerate(items):
        for si, (lab, root) in enumerate((("修正01", f1), ("修正02", f2))):
            x, y = 4 + k * (tw + 4), 66 + si * (th + 6)
            t = tile_fit(os.path.join(root, rel), (tw, th), crop)
            if t is not None:
                im.paste(t, (x, y))
            label(d, x + 4, y + 4, "%s｜%s" % (lab, name), 13)
    im.save(out)
    return out


def fuji_counts(d):
    out = []
    fd = os.path.join(d, "fuji")
    for fn in sorted(os.listdir(fd)):
        if not fn.endswith(".png"):
            continue
        a = np.asarray(Image.open(os.path.join(fd, fn)).convert("RGB")).astype(np.int16)
        snow = (a[..., 0] == 255) & (a[..., 1] == 0) & (a[..., 2] == 255)
        slope = (a[..., 1] == 0) & (np.abs(a[..., 0] - a[..., 2]) <= 1) & (a[..., 0] > 20) & ~snow
        t = int(fn.split("_t")[-1].split(".")[0]) / 100.0
        out.append(dict(t=t, snow=int(snow.sum()), slope=int(slope.sum())))
    return sorted(out, key=lambda r: r["t"])


def fuji_fig(f2dir, f1dir, out_png, out_json):
    A = fuji_counts(f2dir)
    Bf = fuji_counts(f1dir) if f1dir and os.path.exists(os.path.join(f1dir, "fuji")) else []
    im = Image.new("RGB", (1920, 1080), (250, 250, 250))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 修正02：原画視点の富士の雪の画素（t 5〜12 s、1/30 s おきの全部のコマ。Unity の fuji 段）",
         "赤：修正02（肩の稜の上り口を高くし、足し分だけ育ちを遅らせた pl30_shoulder_lag）。灰：修正01（低い鞍）。上の線＝ 2,260 画素（t* の雪の全部）。")
    x0, x1, y0, y1 = 120, 1860, 140, 980
    ymax = 2400.0
    def X(t): return x0 + (t - 5.0) / 7.0 * (x1 - x0)
    def Y(v): return y1 - v / ymax * (y1 - y0)
    d.rectangle([x0, y0, x1, y1], outline=(120, 120, 120))
    for t in range(5, 13):
        d.line([X(t), y1, X(t), y1 + 8], fill=(80, 80, 80)); label(d, X(t) - 12, y1 + 12, "%d s" % t, 16)
    for v in (0, 1000, 2000, 2260):
        d.line([x0 - 8, Y(v), x0, Y(v)], fill=(80, 80, 80)); label(d, x0 - 100, Y(v) - 10, "%d" % v, 16)
    d.line([x0, Y(2260), x1, Y(2260)], fill=(160, 160, 160))
    for S, col in ((Bf, (150, 150, 150)), (A, (200, 30, 30))):
        pts = [(X(r["t"]), Y(r["snow"])) for r in S if 5.0 <= r["t"] <= 12.0]
        if len(pts) > 1:
            d.line(pts, fill=col, width=3)
    mn = min(r["snow"] for r in A) if A else None
    label(d, x0 + 20, y0 + 20, "修正02：%d コマ、雪の最小 %s 画素、2,260 でないコマ %d" % (len(A), mn, sum(1 for r in A if r["snow"] != 2260)), 18)
    if Bf:
        label(d, x0 + 20, y0 + 50, "修正01：%d コマ、雪の最小 %d 画素" % (len(Bf), min(r["snow"] for r in Bf)), 18)
    im.save(out_png)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dict(number="仕上げ30 修正02", what_ja="原画視点の富士の雪（ID の色 (255,0,255)）と山腹の画素。PL30Render の fuji 段（-pl30FujiT1 12 -pl30FujiDt 1/30）",
                       fix02=A, fix01=Bf, fix02_frames=len(A), fix02_min_snow=mn, fix02_frames_not_2260=sum(1 for r in A if r["snow"] != 2260)), f, ensure_ascii=False, indent=1)
    return out_png


def tail_fig(f1, out_png):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 修正02（記録の 7）：群の指示の「手前の尾の刃」は主役波の形（範囲の外）",
         "左：左の側面 t* の作品のまま（修正01 fix01/r10）、右：同じ視点の主役波の印（主役波だけ赤〜緑、海は黄・青、空は水色）。刃（右下へ伸びる細い尾）は主役波の印の中にある。")
    a = Image.open(os.path.join(f1, "views", "side_left_t120_asis.png")).convert("RGB")
    b = Image.open(os.path.join(f1, "diag", "side_left_t120_hero_claws1.png")).convert("RGB")
    tw, th = 950, 534
    im.paste(a.resize((tw, th)), (6, 80)); im.paste(b.resize((tw, th)), (964, 80))
    crop = (500, 280, 1300, 760)
    im.paste(fit(a.crop(crop), (tw, 400)), (6, 630)); im.paste(fit(b.crop(crop), (tw, 400)), (964, 630))
    label(d, 10, 84, "作品のまま", 16); label(d, 968, 84, "主役波の印", 16)
    label(d, 10, 634, "拡大（尾の刃）", 14); label(d, 968, 634, "拡大（尾の刃は主役波の印）", 14)
    im.save(out_png)
    return out_png


REVIEW = [  # 記録の部：全解像度の画像で見直した残る見え方（修正02 の採用。作品のまま）
    ("回り台 t* 方位 90°：白い縦の棒・縦の溝の帯・四角い歯（x 1000〜1600・y 560〜1080）", "tt/t120_az090_claws.png", (1000, 560, 1600, 1080)),
    ("回り台 t* 方位 60°：右の高い波の房（四角い歯）（x 1100〜1920・y 500〜1000）", "tt/t120_az060_claws.png", (1100, 500, 1920, 1000)),
    ("後ろ 65° t*：主役波の右の端の横の縦縞の斑（x 500〜900・y 450〜850）", "views/back65_t120_asis.png", (500, 450, 900, 850)),
    ("回り台 t 10.5 s 方位 90°：下の縦の帯（x 1000〜1600・y 700〜1080）", "tt/t105_az090_claws.png", (1000, 700, 1600, 1080)),
    ("真上 t*：二つの稜の間の縞と重なり（x 1150〜1750・y 250〜750）", "views/top_t120_asis.png", (1150, 250, 1750, 750)),
    ("原画視点 t*：右の高い波の白の帯の左の端（x 1500〜1920・y 540〜780）", "views/painting_t120_asis.png", (1500, 540, 1920, 780)),
]


def review_fig(f2, out_png):
    """記録の部：修正02 の採用の画像を全解像度の切り抜き（縦横の比を保つ）で並べ、残る見え方を示す。新しい描画はしない。"""
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 記録の部：全解像度で見直した残る見え方（修正02 の採用 fix02/r_final、作品のまま、縦横の比を保つ切り抜き）",
         "Q18 ③ を一部と読み直した元。房は先の平らな四角い歯、方位 90° に白い縦の棒と縦の溝の帯、後ろ 65° に縦縞の斑。Unity 6000.4.3f1 の PC 描画（HMD ではない）。")
    tw, th = 634, 500
    for k, (name, rel, crop) in enumerate(REVIEW):
        x, y = 4 + (k % 3) * (tw + 2), 68 + (k // 3) * (th + 6)
        t = tile_fit(os.path.join(f2, rel), (tw, th), crop)
        if t is not None:
            im.paste(t, (x, y))
        label(d, x + 4, y + 4, name, 12)
    im.save(out_png)
    return out_png


def trough_share(f2, mask, out_json):
    rec = {}
    for v in ("seat_toward_wave", "seat_low", "painting", "top"):
        p = os.path.join(mask, "views", "%s_t120_clawfree.png" % v)
        if not os.path.exists(p):
            continue
        m = np.asarray(Image.open(p).convert("RGB")).astype(int)
        mk = (m[..., 0] == 255) & (m[..., 1] == 0) & (m[..., 2] == 255)
        rec[v] = dict(trough_px=int(mk.sum()), frac_of_image=float(mk.mean()))
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dict(number="仕上げ30 修正02", what_ja="谷の縁の段（材質の _PL29Diag = 7 の印）の画素。t*。修正02 で帯の幅を重み tw で端へ細らせた", views=rec), f, ensure_ascii=False, indent=1)
    return rec


def white_px(f1, f2, out_json):
    """白（生成りの色 R > 235・G > 230・B > 200）の画素を、項目の場所で数える（修正01・修正02 の同じ画像の同じ場所）。"""
    boxes = [
        ("1 原画視点 t 6 s の白い刃（x 250〜420・y 735〜775 の周り）", "views/painting_t060_asis.png", (200, 700, 470, 820)),
        ("1 原画視点 t 9 s の白い筋（x 700〜940・y 815〜835 の周り）", "views/painting_t090_asis.png", (650, 790, 990, 860)),
        ("1 回り台 t 6 s 方位 0° の下半分（刃と小波）", "tt/t060_az000_claws.png", (0, 540, 1920, 1080)),
        ("1 回り台 t 6 s 方位 30° の下半分", "tt/t060_az030_claws.png", (0, 540, 1920, 1080)),
        ("1 回り台 t 6 s 方位 60° の下半分", "tt/t060_az060_claws.png", (0, 540, 1920, 1080)),
        ("1 回り台 t 6 s 方位 90° の下半分", "tt/t060_az090_claws.png", (0, 540, 1920, 1080)),
        ("3 回り台 t* 方位 60° の下半分（右の高い波）", "tt/t120_az060_claws.png", (0, 540, 1920, 1080)),
        ("3 回り台 t* 方位 90° の下半分（右の高い波）", "tt/t120_az090_claws.png", (0, 540, 1920, 1080)),
        ("3 回り台 t* 方位 120° の下半分（右の高い波）", "tt/t120_az120_claws.png", (0, 540, 1920, 1080)),
        ("3 回り台 t 10.5 s 方位 90° の下半分", "tt/t105_az090_claws.png", (0, 540, 1920, 1080)),
        ("4 原画視点 t* の水平線の白い楔（x 1005〜1350・y 765〜830）", "views/painting_t120_asis.png", (1000, 760, 1360, 835)),
    ]
    rec = []
    for name, rel, (x0, y0, x1, y1) in boxes:
        r = dict(item=name, image=rel, box=[x0, y0, x1, y1])
        for lab, root in (("fix01", f1), ("fix02", f2)):
            p = os.path.join(root, rel)
            if os.path.exists(p):
                a = np.asarray(Image.open(p).convert("RGB")).astype(int)[y0:y1, x0:x1]
                r[lab] = int(((a[..., 0] > 235) & (a[..., 1] > 230) & (a[..., 2] > 200)).sum())
        rec.append(r)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(dict(number="仕上げ30 修正02", what_ja="白（生成り）の画素を項目の場所で数えた（修正01 fix01/r10 と修正02 の同じ視点・同じ時刻・作品のまま）。主役波の白も同じ色なので、場所は海の白の所を選んだ（回り台の下半分は右の高い波・小波・海）。",
                       boxes=rec), f, ensure_ascii=False, indent=1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--f1", default="Unity/Build/Polish/30/fix01/r10")
    ap.add_argument("--f2", default="Unity/Build/Polish/30/fix02/r_final")
    ap.add_argument("--fuji", default="Unity/Build/Polish/30/fix02/fuji_final")
    ap.add_argument("--fuji-f1", default="Unity/Build/Polish/30/fix02/fuji_f1")
    ap.add_argument("--mask", default="Unity/Build/Polish/30/fix02/r_final_diag7")
    ap.add_argument("--out", default="Docs/Evidence/Polish/30")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    sub = "上：修正01 の採用（fix01/r10）、下：修正02 の採用（fix02）。同じ視点・同じ時刻・作品のまま。Unity 6000.4.3f1 の PC 描画（HMD ではない）。"
    fs = [pair_sheet(ITEMS_A, a.f1, a.f2, "仕上げ30 修正02：自己評審の must-fix の前後（1/3：偽の白・小波）", sub, os.path.join(a.out, "fig_pl30_fix02_a.png")),
          pair_sheet(ITEMS_B, a.f1, a.f2, "仕上げ30 修正02：自己評審の must-fix の前後（2/3：右の高い波の白・水平線の楔・鞍）", sub, os.path.join(a.out, "fig_pl30_fix02_b.png")),
          pair_sheet(ITEMS_C, a.f1, a.f2, "仕上げ30 修正02：自己評審の must-fix の前後（3/3：真上・谷の縁の端）", sub, os.path.join(a.out, "fig_pl30_fix02_c.png")),
          fuji_fig(a.fuji, a.fuji_f1, os.path.join(a.out, "fig_pl30_fix02_fuji.png"), os.path.join(a.out, "pl30_fix02_fuji.json")),
          tail_fig(a.f1, os.path.join(a.out, "fig_pl30_fix02_tail.png")),
          review_fig(a.f2, os.path.join(a.out, "fig_pl30_record_review.png"))]
    if os.path.exists(a.mask):
        print("trough", trough_share(a.f2, a.mask, os.path.join(a.out, "pl30_fix02_trough_share.json")))
    for r in white_px(a.f1, a.f2, os.path.join(a.out, "pl30_fix02_white_px.json")):
        print("white", r["item"], r.get("fix01"), "->", r.get("fix02"))
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
