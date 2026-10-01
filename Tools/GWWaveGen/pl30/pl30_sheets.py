# -*- coding: utf-8 -*-
"""仕上げ30 の前後の図（1920×1080）と前後を並べた動画。

前＝仕上げ29 の状態（PL30Render -pl30Old 1：設計30 の海のパッケージと設計36 の t* の高さの段、仮置きの板）、
後＝仕上げ30（PL30Render：G_p28rec につないだ海・PL30 Ukiyoe Sea・右の高い波の遅れと肩の稜・左奥の船のうねり）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。この道具は既にある画像を並べて数を書き込むだけ（新しい描画はしない）。

  fig_pl30_ba_view_<視点>.png  7 視点 × t 6・9・10.5・12 s（上：前、次：後）と t* の前後の拡大、右の欄に海の画素の色区の割合
  fig_pl30_ba_turntable_t<時刻>.png  回り台 12 方位（周りの海を含む）の前後
  fig_pl30_fuji.png  原画視点 t 7・8・9・10 s の前後と、富士の雪・山腹の見える画素の時間の図（S5-2）
  fig_pl30_items.png  項目ごとの切り抜き（手前の小波、仮置きの板、近い海の尾の刃、継ぎ目と船の支え、稜線の段 S5-3、遠い海の線）
  pl30_ba_<視点>_30fps.mp4  前｜後 を左右に並べた動画（t 0〜14 s、30 fps）
使い方：py -3.10 -B Tools/GWWaveGen/pl30/pl30_sheets.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/fix01/r10
        --measure Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json --out Docs/Evidence/Polish/30
（修正01 の後は --after を fix01/r10、修正02 の後は fix02/r_final にする。作る部は after_r7）
"""
import argparse
import json
import os
import subprocess

from PIL import Image, ImageDraw, ImageFont

FONT = "C:/Windows/Fonts/NotoSansJP-VF.ttf"
FONTB = "C:/Windows/Fonts/NotoSansJP-Bold.ttf"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
ZOOM = {"painting": (700, 330, 1920, 1016)}
HEAD_B = "前＝仕上げ29 の状態（設計30 の海・設計36 の t* の高さの段・仮置きの板）"
HEAD_A = "後＝仕上げ30 修正02（G_p28rec につないだ海、連続な面の座標の PL30 Ukiyoe Sea、白は今の育ち×t* の高さの比で抑える、右の高い波の白の幅の上限、肩の稜の細い白い線と高くした上り口、左奥の船のうねり）"


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


def label(d, x, y, text, sz=15):
    w = d.textlength(text, font=font(sz, True)) + 10
    d.rectangle([x, y, x + w, y + sz + 8], fill=(20, 20, 20))
    d.text((x + 5, y + 2), text, fill=(255, 255, 255), font=font(sz, True))


def head(d, title, sub):
    d.rectangle([0, 0, 1920, 62], fill=(28, 36, 52))
    d.text((14, 4), title, fill=(255, 255, 255), font=font(22, True))
    d.text((14, 38), sub, fill=(205, 212, 225), font=font(15))


def tile(p, size, crop=None):
    if not os.path.exists(p):
        return None
    a = Image.open(p).convert("RGB")
    if crop:
        a = a.crop(crop)
    return a.resize(size, Image.LANCZOS)


def fit(a, size, bg=(238, 238, 238)):
    """画像 a の縦横の比を保って size の枠に収める（余りは bg で埋め、真ん中に置く）。"""
    w, h = a.size
    s = min(size[0] / float(w), size[1] / float(h))
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    out = Image.new("RGB", size, bg)
    out.paste(a.resize((nw, nh), Image.LANCZOS), ((size[0] - nw) // 2, (size[1] - nh) // 2))
    return out


def tile_fit(p, size, crop=None, bg=(238, 238, 238)):
    """tile と同じだが、切り抜きの縦横の比を保つ。仕上げ30 の記録の部で足した（修正01・修正02 の must-fix の前後の図は、
    切り抜きを枠の比へ引き伸ばしていて、回り台の右の高い波の白の房が横に最大 3.7 倍縮んで見えていた）。"""
    if not os.path.exists(p):
        return None
    a = Image.open(p).convert("RGB")
    if crop:
        a = a.crop(crop)
    return fit(a, size, bg)


def pct(x):
    return "—" if x is None else "%.1f%%" % (100.0 * x)


def view_sheets(a, M, out):
    files = []
    seaid = M.get("seaid", {})
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ30 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま）" % name,
             HEAD_B + "、" + HEAD_A + "。Unity の PC 描画（HMD ではない）。")
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        crop = ZOOM.get(v)
        bw, bh = 818, 460
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            x, y = 4 + si * (bw + 6), 610
            t = tile(os.path.join(root, "views", "%s_t120_asis.png" % v), (bw, bh), crop)
            if t is not None:
                im.paste(t, (x, y))
            label(d, x + 4, y + 4, "%s｜t 12 s（t*）%s" % (lab, "・右の高い波と富士と手前の小波の拡大" if crop else ""))
        x0, y0 = 1660, 616
        d.text((x0, y0), "海の画素の色区（ID）", fill=(20, 20, 20), font=font(16, True))
        yy = y0 + 28
        for ts, tn in TS:
            key = "%s_%s" % (v, ts)
            rb = seaid.get("before", {}).get(key)
            ra = seaid.get("after", {}).get(key)
            if not rb and not ra:
                continue
            d.text((x0, yy), tn, fill=(20, 20, 20), font=font(14, True)); yy += 20
            for lab, r in (("前", rb), ("後", ra)):
                if r and r.get("sea_px"):
                    d.text((x0 + 8, yy), "%s 白 %s 淡 %s 藍中 %s" % (lab, pct(r["white_frac"]), pct(r["mizuiro_frac"]), pct(r["ai_mid_frac"])),
                           fill=(40, 40, 40), font=font(13)); yy += 18
            yy += 4
        d.text((x0, 1040), "白・淡い水色・藍中の割合は\n主役波でない海の画素の中", fill=(90, 90, 90), font=font(12))
        p = os.path.join(out, "fig_pl30_ba_view_%s.png" % v)
        im.save(p); files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ30 回り台｜%s｜方位ごとに上：前　下：後（爪あり・飛沫なし・線あり、周りの海を含む）" % tn,
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29 と同じ置き方。仕上げ29 は主役波だけ、ここは海も描く）。Unity の PC 描画。")
        tw, th = 316, 178
        for k in range(12):
            az = k * 30
            col, blk = k % 6, k // 6
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + col * (tw + 4), 66 + blk * (2 * th + 30) + si * (th + 2)
                t = tile(os.path.join(root, "tt", "%s_az%03d_claws.png" % (ts, az)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 3, y + 3, "%s｜方位 %d°" % (lab, az), 12)
        p = os.path.join(out, "fig_pl30_ba_turntable_%s.png" % ts)
        im.save(p); files.append(p)
    return files


def fuji_sheet(a, M, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 S5-2：原画視点 t 5〜10 s に右の高い波が富士を隠さない（上：前　下：後）",
         "前は t 7.0〜10.0 s に富士の雪が 0 画素（右の高い波の『雪山』）。後は右の高い波の育ちを遅らせた（pl30_right_lag）。画素は富士の材質だけ ID の色で描いた画像（原画視点、1920×1080）から数えた。")
    tw, th = 474, 267
    for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
        for k, t in enumerate([700, 800, 900, 1000]):
            x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
            img = tile(os.path.join(root, "fuji", "painting_fuji_t%04d.png" % t), (tw, th))
            if img is not None:
                im.paste(img, (x, y))
            label(d, x + 4, y + 4, "%s｜t %.1f s（ID：富士の雪 マゼンタ・山腹 紫、空 水色）" % (lab, t / 100), 13)
    # 色の画像（t 9 s）
    for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
        x, y = 4 + si * 480, 610
        img = tile(os.path.join(root, "views", "painting_t090_asis.png"), (474, 267))
        if img is not None:
            im.paste(img, (x, y))
        label(d, x + 4, y + 4, "%s｜t 9 s 作品のまま" % lab, 13)
    # 時間の図
    gx, gy, gw, gh = 1000, 640, 880, 380
    d.rectangle([gx, gy, gx + gw, gy + gh], fill=(255, 255, 255), outline=(150, 150, 150))
    F = M.get("fuji", {})
    tmin, tmax = 5.0, 12.0
    def X(t):
        return gx + 40 + (t - tmin) / (tmax - tmin) * (gw - 60)
    def Y(v, vmax):
        return gy + gh - 30 - v / vmax * (gh - 60)
    for lab, key, col, vmax, dash in (("雪（前）", ("before", "snow"), (200, 60, 60), 2400, False), ("雪（後）", ("after", "snow"), (40, 90, 200), 2400, False),
                                      ("山腹（前）", ("before", "slope"), (230, 150, 150), 11000, True), ("山腹（後）", ("after", "slope"), (140, 170, 230), 11000, True)):
        pts = [(X(r["t"]), Y(r[key[1]], vmax)) for r in F.get(key[0], [])]
        if len(pts) > 1:
            d.line(pts, fill=col, width=3 if not dash else 2)
    d.text((gx + 10, gy + 6), "富士の見える画素（雪：0〜2,400 の目盛、山腹：0〜11,000 の目盛）。横軸 t 5〜12 s", fill=(30, 30, 30), font=font(13, True))
    yy = gy + 26
    for lab, col in (("雪 前", (200, 60, 60)), ("雪 後", (40, 90, 200)), ("山腹 前", (230, 150, 150)), ("山腹 後", (140, 170, 230))):
        d.line([(gx + gw - 140, yy + 8), (gx + gw - 110, yy + 8)], fill=col, width=3); d.text((gx + gw - 104, yy), lab, fill=(30, 30, 30), font=font(12)); yy += 18
    for t in range(5, 13):
        d.text((X(t) - 6, gy + gh - 24), str(t), fill=(60, 60, 60), font=font(12))
    p = os.path.join(out, "fig_pl30_fuji.png")
    im.save(p)
    return [p]


def items_sheet(a, M, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ30 項目ごとの切り抜き（上：前　下：後）",
         "左から：手前の小波（原画視点 t*）、仮置きの板と左奥の船（座席の低い視点 t*）、近い海の尾の『刃』（左の側面 t 6 s）、稜線の段 S5-3（座席 v1 コマ 280）、船の支えと谷（座席から波の方向 t 10.5 s）、遠い海の線（右の側面 t 12 s）。")
    cells = [("手前の小波", lambda r: os.path.join(r, "views", "painting_t120_asis.png"), (520, 520, 920, 1077)),
             ("仮置きの板", lambda r: os.path.join(r, "views", "seat_low_t120_asis.png"), (0, 0, 776, 1080)),
             ("尾の刃", lambda r: os.path.join(r, "views", "side_left_t060_clawfree.png"), (1150, 8, 1920, 1080)),
             ("稜線 S5-3", lambda r: os.path.join(r, "s5", "seat_f0280.png"), (1640, 380, 1920, 770)),
             ("船の支え", lambda r: os.path.join(r, "views", "seat_toward_wave_t105_clawfree.png"), (300, 105, 1000, 1080)),
             ("遠い海の線", lambda r: os.path.join(r, "views", "side_right_t120_clawfree.png"), (1200, 77, 1920, 1080))]
    tw, th = 316, 440
    for k, (name, fp, crop) in enumerate(cells):
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            x, y = 4 + k * (tw + 4), 70 + si * (th + 6)
            img = tile(fp(root), (tw, th), crop)
            if img is not None:
                im.paste(img, (x, y))
            label(d, x + 3, y + 3, "%s｜%s" % (lab, name), 12)
    p = os.path.join(out, "fig_pl30_items.png")
    im.save(p)
    return [p]


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        pb = os.path.join(a.before, "video", "pl30_%s_30fps.mp4" % v)
        pa = os.path.join(a.after, "video", "pl30_%s_30fps.mp4" % v)
        if not (os.path.exists(pb) and os.path.exists(pa)):
            continue
        o = os.path.join(out, "pl30_ba_%s_30fps.mp4" % v)
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", pb, "-i", pa, "-filter_complex",
               "[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前（仕上げ29）':x=10:y=10:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
               "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後（仕上げ30 修正02）':x=10:y=10:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2",
               "-c:v", "libx264", "-preset", "medium", "-crf", "28", "-pix_fmt", "yuv420p", "-movflags", "+faststart", o]
        subprocess.run(cmd, check=True)
        files.append(o)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="Unity/Build/Polish/30/before")
    ap.add_argument("--after", default="Unity/Build/Polish/30/after_r7")
    ap.add_argument("--measure", default="Unity/Build/Polish/30/measure_r7/pl30_measure.json")
    ap.add_argument("--out", default="Docs/Evidence/Polish/30")
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    M = json.load(open(a.measure, encoding="utf-8"))
    files = view_sheets(a, M, a.out) + turntable(a, a.out) + fuji_sheet(a, M, a.out) + items_sheet(a, M, a.out)
    if not a.no_video:
        files += videos(a, a.out)
    for f in files:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
