# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の視点ごとの前後の図（1920×1080、視点 1 つに 1 枚）。

前（前の点検 PL29Audit：原画カメラからの投影の焼き込み）と後（修正の回 p29g：視点によらない立体の材質）を、
同じ視点・同じ時刻（t 6・9・10.5・12 s）・作品のまま（爪・飛沫・線）で並べる。描画はどれも Unity の PC オフスクリーン描画で、
この道具は既にある画像を並べて数を書き込むだけ（新しい描画はしない）。参照の彫刻の写真とそこから作った画像は読まない。

  上の 2 段：前（上）と後（下）、4 時刻。
  下の段  ：t 12 s（t*）の前と後を大きく（原画視点は主役波のまわりの拡大）。右の欄に、その視点の数
            （前の点検の投影の分類・平らな芯、修正の回の平らな芯・爪の分かれる割合）。

使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_view_sheets.py --before Unity/Build/Polish/29/before/p28 --after Unity/Build/Polish/29/fix01/p29g
        --audit Docs/Evidence/Polish/29/metrics_audit.json --fix Docs/Evidence/Polish/29/metrics_fix01.json --out Docs/Evidence/Polish/29
"""
import argparse
import json
import os

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
FONTB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
ZOOM = {"painting": (140, 60, 1240, 679)}


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def label(d, x, y, text, sz=15):
    w = d.textlength(text, font=font(sz, True)) + 10
    d.rectangle([x, y, x + w, y + sz + 8], fill=(20, 20, 20))
    d.text((x + 5, y + 2), text, fill=(255, 255, 255), font=font(sz, True))


def tile(root, v, ts, size, crop=None):
    p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
    if not os.path.exists(p):
        return None, p
    a = Image.open(p).convert("RGB")
    if crop:
        a = a.crop(crop)
    return a.resize(size, Image.LANCZOS), p


def pct(x):
    return "—" if x is None else ("%.1f%%" % (100.0 * x) if x >= 0.001 or x == 0 else "%.2f%%" % (100.0 * x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--fix", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prefix", default="fig_pl29_ba_view")
    a = ap.parse_args()
    audit = json.load(open(a.audit, encoding="utf-8"))["summaryByView"]
    fix = json.load(open(a.fix, encoding="utf-8"))
    flat = fix["clawMeltedIdReading"]["byView"]
    sep = fix["clawSeparation"]["fix_p29g"]
    used = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 1920, 62], fill=(28, 36, 52))
        d.text((14, 4), "仕上げ29（Q28）視点ごとの前後｜%s｜上の段：前（原画カメラからの投影の焼き込み）　次の段：後（視点によらない立体の材質）" % name,
               fill=(255, 255, 255), font=font(22, True))
        d.text((14, 38), "同じ視点・同じ時刻・作品のまま（爪・飛沫・線）。前＝PL29Audit（K*′ P28R2rec・G_p28rec・bake_rec の投影）、"
               "後＝PL29Render 修正の回 p29g（同じ形と動き、PL29 Ukiyoe Keypose、爪は PL29 Claw Shade）。Unity 6000.4.3f1 の PC 描画（HMD ではない）。",
               fill=(205, 212, 225), font=font(15))
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t, p = tile(root, v, ts, (tw, th))
                if t is not None:
                    im.paste(t, (x, y)); used.append(p)
                label(d, x, y, "%s｜%s" % (lab, tn))
        bw, bh = 820, 461
        yb = 66 + 2 * (th + 3) + 4
        for k, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            x = 4 + k * (bw + 4)
            t, p = tile(root, v, "t120", (bw, bh), ZOOM.get(v))
            if t is not None:
                im.paste(t, (x, yb)); used.append(p)
            label(d, x, yb, "%s｜t 12 s（t*）%s" % (lab, "・主役波のまわりの拡大" if v in ZOOM else ""), 17)
        # 数の欄
        xp, yp = 4 + 2 * (bw + 4) + 8, yb + 2
        au = audit.get(v, {})
        fb = flat.get(v, {})
        cs = sep.get(v, {})
        lines = [("この視点の数（4 時刻）", True),
                 ("前の点検（投影）", True),
                 ("投影から色を取る画素 " + pct(au.get("directFrac")), False),
                 ("外挿の帯 " + pct(au.get("bandFrac")), False),
                 ("平らな塗り " + pct(au.get("flatFillFrac")), False),
                 ("平らな芯 " + pct(au.get("flatCoreFracOfHero")), False),
                 ("", False),
                 ("修正の回（立体の材質）", True),
                 ("投影 0（原画カメラを読まない）", False),
                 ("平らな芯 " + pct(fb.get("after", {}).get("flatCoreFracOfHero")), False),
                 ("（同じ読みの前 " + pct(fb.get("before", {}).get("flatCoreFracOfHero")) + "）", False),
                 ("爪の片 %s・縁が分かれる %s" % (cs.get("pieces", "—"), "—" if cs.get("readableFrac") is None else "%.2f" % cs["readableFrac"]), False),
                 ("", False),
                 ("平らな芯＝色の境から 48 px より", False),
                 ("遠い画素の主役波に対する割合。", False),
                 ("爪の縁＝縁の 2 px 以内に暗い画素", False),
                 ("（線・藍）がある縁の割合 ≥ 0.6", False),
                 ("の片の割合（記録のみ）。", False)]
        for txt, b in lines:
            d.text((xp, yp), txt, fill=(20, 28, 40), font=font(15 if not b else 16, b))
            yp += 23
        out = os.path.join(a.out, "%s_%s.png" % (a.prefix, v))
        im.save(out, optimize=True)
        print(out, im.size, os.path.getsize(out))
    print("inputs", len(set(used)))


if __name__ == "__main__":
    main()
