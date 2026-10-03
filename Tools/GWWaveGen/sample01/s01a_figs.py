# -*- coding: utf-8 -*-
"""美術の見本01・見本 A：前後の並べ図（同じ視点・同じ時刻・爪なし。1920 幅の PNG）。
前＝採用の状態（PL29 Ukiyoe Keypose、Build/Polish/sample01/texA/before）、後＝見本 A（S01A Groove Keypose、--after のフォルダー）。
使い方：py -3.10 -B Tools/GWWaveGen/sample01/s01a_figs.py --after <texA の下の名前> --out <dir> [--times 120,105] [--sample]
--sample：前を並べず、見本 A だけの 1 枚（審査の 7 視点＋回り台 12 方位）も作る（利用者が見本 A・B を見比べるための図）。
"""
import argparse
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texA"
FONT = "C:/Windows/Fonts/meiryo.ttc"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]


def font(n):
    try:
        return ImageFont.truetype(FONT, n)
    except Exception:
        return ImageFont.load_default()


def tile(sheet, d, path, x, y, w, h, label, f):
    if os.path.exists(path):
        im = Image.open(path).convert("RGB").resize((w, h), Image.LANCZOS)
        sheet.paste(im, (x, y))
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
    header(d, W, "美術の見本01・見本 A（彫刻のような刻み）｜%s｜爪なし｜上：前（採用の PL29）　下：後（見本 A）" % tlabel,
           "同じ視点・同じ時刻・同じ描画（S01ARender、Unity 6000.4.3f1 の PC オフスクリーン描画。HMD ではない）。後は w（t* の面の上で巻きの向きにそろえた座標）の等値線に 1 m ごとの溝。")
    f = font(15)
    for k, (v, name) in enumerate(VIEWS):
        grp, col = divmod(k, 4)
        y0 = top + grp * 2 * th
        tile(sheet, d, "%s/before/views/%s_%s_clawfree.png" % (ROOT, v, ts), col * tw, y0, tw - 2, th - 2, "前｜" + name, f)
        tile(sheet, d, "%s/%s/views/%s_%s_clawfree.png" % (ROOT, after, v, ts), col * tw, y0 + th, tw - 2, th - 2, "後｜" + name, f)
    sheet.save(out)
    print(out)


def tt_sheet(after, ts, tlabel, out):
    W, tw, th, top = 1920, 320, 180, 70
    sheet = Image.new("RGB", (W, top + 4 * th + 8), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 A｜回り台 %s｜爪なし｜方位ごとに上：前（採用の PL29）　下：後（見本 A）" % tlabel,
           "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜36 と同じ置き方）。")
    f = font(13)
    for k in range(12):
        az = k * 30
        grp, col = divmod(k, 6)
        y0 = top + grp * 2 * th
        tile(sheet, d, "%s/before/tt/%s_az%03d_noclaws.png" % (ROOT, ts, az), col * tw, y0, tw - 2, th - 2, "前｜方位 %d°" % az, f)
        tile(sheet, d, "%s/%s/tt/%s_az%03d_noclaws.png" % (ROOT, after, ts, az), col * tw, y0 + th, tw - 2, th - 2, "後｜方位 %d°" % az, f)
    sheet.save(out)
    print(out)


def sample_sheet(after, ts, tlabel, out):
    W, top = 1920, 70
    vw, vh = 480, 270          # 7 視点（4 × 2、最後の 1 枠は説明）
    tw, th = 320, 180          # 回り台 12 方位（6 × 2）
    H = top + 2 * vh + 30 + 2 * th + 8
    sheet = Image.new("RGB", (W, H), (238, 238, 238))
    d = ImageDraw.Draw(sheet)
    header(d, W, "美術の見本01・見本 A（彫刻のような刻み）｜%s｜爪なし｜審査の 7 視点と回り台 12 方位" % tlabel,
           "深い藍の胴に、巻きの向き（背 → 頂 → 唇）に沿う等間隔の溝（3 次元の周期 1 m、溝の中に淡い藍の線）。背の上と頂は白、頂・唇の前は藍。原画カメラの投影は使わない。")
    f = font(15)
    for k, (v, name) in enumerate(VIEWS):
        r, col = divmod(k, 4)
        tile(sheet, d, "%s/%s/views/%s_%s_clawfree.png" % (ROOT, after, v, ts), col * vw, top + r * vh, vw - 2, vh - 2, name, f)
    x0, y0 = 3 * vw + 12, top + vh + 14
    notes = ["見本 A の見どころ", "・溝は t* の面の座標 w の等値線（面の上で", "  ほぼ一様の 1 m）。動きの間も頂点と動く", "・溝の本数は面の開き（|∇w|）で 2 倍ずつ", "  変え、Y 字に枝分かれする", "・頂・唇の前は藍：立体の白い爪をここに置く", "・爪は別の部（この図には描かない）"]
    for i, t in enumerate(notes):
        d.text((x0, y0 + i * 30), t, font=font(18 if i == 0 else 16), fill=(30, 30, 30))
    yT = top + 2 * vh + 30
    d.text((8, yT - 26), "回り台（中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、原画視点の向きから 30° ごと）", font=font(16), fill=(30, 30, 30))
    f2 = font(13)
    for k in range(12):
        az = k * 30
        r, col = divmod(k, 6)
        tile(sheet, d, "%s/%s/tt/%s_az%03d_noclaws.png" % (ROOT, after, ts, az), col * tw, yT + r * th, tw - 2, th - 2, "方位 %d°" % az, f2)
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
        views_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01a_ba_views_t%s.png" % ts))
        tt_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01a_ba_tt_t%s.png" % ts))
        if a.sample:
            sample_sheet(a.after, "t" + ts, tl, os.path.join(a.out, "fig_s01a_sample_t%s.png" % ts))


if __name__ == "__main__":
    main()
