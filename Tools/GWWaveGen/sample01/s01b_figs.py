# -*- coding: utf-8 -*-
"""美術の見本01・見本 B（原画のような舌形）：前後の並べ図・見本の図・原画視点の並べ図（同じ視点・同じ時刻・爪なし。1920 幅の PNG）。
前＝採用の状態（PL29 Ukiyoe Keypose。見本 A の部が描いた Build/Polish/sample01/texA/before をそのまま使う）、
後＝見本 B（S01B Tongue Keypose、Build/Polish/sample01/texB/<--after>）。
使い方：py -3.10 -B Tools/GWWaveGen/sample01/s01b_figs.py --after final --out <dir> [--times 120,105] [--sample]
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

ROOT_A = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texA"
ROOT_B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB"
PAINTING = "G:/Unity/GreatWave_2026_Fresh/Tools/PaintingTruth/build/painting_display.png"
FONT = "C:/Windows/Fonts/meiryo.ttc"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
SUB = "同じ視点・同じ時刻・同じ描画（S01BRender、Unity 6000.4.3f1 の PC オフスクリーン描画。HMD ではない）。後は t* の面の座標 (u, w) の上に設計した舌と線（原画カメラの投影なし）。"


def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except Exception:
        return ImageFont.load_default()


def tile(sheet, d, path, x, y, w, h, label, f, box=None):
    if os.path.exists(path):
        im = Image.open(path).convert("RGB")
        if box:
            im = im.crop(box)
        sheet.paste(im.resize((w, h), Image.LANCZOS), (x, y))
    else:
        d.rectangle([x, y, x + w, y + h], fill=(200, 200, 200))
    tb = d.textbbox((0, 0), label, font=f)
    d.rectangle([x + 3, y + 3, x + 11 + tb[2] - tb[0], y + 9 + tb[3] - tb[1]], fill=(20, 20, 20))
    d.text((x + 7, y + 4), label, font=f, fill=(255, 255, 255))


def header(d, W, title, sub):
    d.rectangle([0, 0, W, 66], fill=(28, 34, 48))
    d.text((12, 4), title, font=font(26), fill=(255, 255, 255))
    d.text((12, 40), sub, font=font(15), fill=(200, 205, 215))


def views_sheet(after, ts, tlabel, out):
    W, tw, th, top = 1920, 480, 270, 70
    sheet = Image.new("RGB", (W, top + 4 * th + 8), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 B（原画のような舌形）｜%s｜爪なし｜上：前（採用の PL29）　下：後（見本 B）" % tlabel, SUB)
    f = font(15)
    for k, (v, name) in enumerate(VIEWS):
        grp, col = divmod(k, 4)
        y0 = top + grp * 2 * th
        tile(sheet, d, "%s/before/views/%s_%s_clawfree.png" % (ROOT_A, v, ts), col * tw, y0, tw - 2, th - 2, "前｜" + name, f)
        tile(sheet, d, "%s/%s/views/%s_%s_clawfree.png" % (ROOT_B, after, v, ts), col * tw, y0 + th, tw - 2, th - 2, "後｜" + name, f)
    sheet.save(out)
    print(out)


def tt_sheet(after, ts, tlabel, out):
    W, tw, th, top = 1920, 320, 180, 70
    sheet = Image.new("RGB", (W, top + 4 * th + 8), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 B｜回り台 %s｜爪なし｜方位ごとに上：前（採用の PL29）　下：後（見本 B）" % tlabel,
           "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜36 と同じ置き方）。")
    f = font(13)
    for k in range(12):
        az = k * 30
        grp, col = divmod(k, 6)
        y0 = top + grp * 2 * th
        tile(sheet, d, "%s/before/tt/%s_az%03d_noclaws.png" % (ROOT_A, ts, az), col * tw, y0, tw - 2, th - 2, "前｜方位 %d°" % az, f)
        tile(sheet, d, "%s/%s/tt/%s_az%03d_noclaws.png" % (ROOT_B, after, ts, az), col * tw, y0 + th, tw - 2, th - 2, "後｜方位 %d°" % az, f)
    sheet.save(out)
    print(out)


def sample_sheet(after, ts, tlabel, out):
    W, top = 1920, 70
    vw, vh = 480, 270
    tw, th = 320, 180
    H = top + 2 * vh + 30 + 2 * th + 8
    sheet = Image.new("RGB", (W, H), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 B（原画のような舌形）｜%s｜爪なし｜審査の 7 視点と回り台 12 方位" % tlabel,
           "藍濃の太い舌と藍中の線を、t* の面の座標 (u, w)（m、巻きの向きと頂に並ぶ向き）の上に設計。頂・背の上は白、頂の前は淡い水色の帯に舌の丸い頭。投影なし。")
    f = font(15)
    for k, (v, name) in enumerate(VIEWS):
        r, col = divmod(k, 4)
        tile(sheet, d, "%s/%s/views/%s_%s_clawfree.png" % (ROOT_B, after, v, ts), col * vw, top + r * vh, vw - 2, vh - 2, name, f)
    x0, y0 = 3 * vw + 12, top + vh + 10
    notes = ["見本 B の見どころ",
             "・線は巻きの向き（頂 → 唇・前面）に沿い、面の上の",
             "  m で間をそろえた流線。下へ行くほど間が開き、",
             "  途中で終わる線もある（舌が下で太くなる）",
             "・帯の縁から始まる線ごとに舌の丸い頭（半楕円）。",
             "  頭の間から藍中の線が太く生まれ、下で細る",
             "・背の白の下も同じ座標の上の一様な線",
             "・頂・唇の前は藍：爪（別の部）をここに置く"]
    for i, t in enumerate(notes):
        d.text((x0, y0 + i * 29), t, font=font(18 if i == 0 else 15), fill=(30, 30, 30))
    yT = top + 2 * vh + 30
    d.text((8, yT - 26), "回り台（中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、原画視点の向きから 30° ごと）", font=font(16), fill=(30, 30, 30))
    f2 = font(13)
    for k in range(12):
        az = k * 30
        r, col = divmod(k, 6)
        tile(sheet, d, "%s/%s/tt/%s_az%03d_noclaws.png" % (ROOT_B, after, ts, az), col * tw, yT + r * th, tw - 2, th - 2, "方位 %d°" % az, f2)
    sheet.save(out)
    print(out)


def painting_sheet(after, out):
    """原画視点の波（爪なし）を、前・見本 B・原画で並べる（原画は比べるためだけ。面へは写していない）。"""
    W, top = 1920, 70
    box = (380, 60, 1180, 760)       # 原画視点の 1920×1080 の中の主役波
    tw = W // 3
    th = int(tw * (box[3] - box[1]) / (box[2] - box[0]))
    sheet = Image.new("RGB", (W, top + th + 8), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 B｜原画視点 t*（爪なし）｜左：前（採用の PL29）　中：見本 B　右：原画（比べる相手。面へは写していない）",
           "見本 B の線の向きは巻きの向き ±25° に留めた（唇の上面では原画の縦の線と向きが違う）。舌の頭・太い舌・線の太さの変わり方・白い点を原画に寄せた。")
    f = font(16)
    tile(sheet, d, "%s/before/views/painting_t120_clawfree.png" % ROOT_A, 0, top, tw - 2, th, "前（採用の PL29）", f, box)
    tile(sheet, d, "%s/%s/views/painting_t120_clawfree.png" % (ROOT_B, after), tw, top, tw - 2, th, "見本 B", f, box)
    tile(sheet, d, PAINTING, 2 * tw, top, tw - 2, th, "原画", f, box)
    sheet.save(out)
    print(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--times", default="120,105")
    ap.add_argument("--sample", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    for ts in a.times.split(","):
        tl = "t %s s" % (int(ts) / 10.0) + ("（t*）" if ts == "120" else "")
        views_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01b_ba_views_t%s.png" % ts))
        tt_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01b_ba_tt_t%s.png" % ts))
        if a.sample:
            sample_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01b_sample_t%s.png" % ts))
    painting_sheet(a.after, os.path.join(a.out, "fig_s01b_painting_vs.png"))


if __name__ == "__main__":
    main()
