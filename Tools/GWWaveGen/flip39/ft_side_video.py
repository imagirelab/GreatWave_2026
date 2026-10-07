# -*- coding: utf-8 -*-
"""FLIP39 まとめ（10/8）：横から見た断面の動画（縦横同じ縮尺）。R（E3 の主役の範囲、粒子 0.3 m）の
座席の列 z −80 m と、いちばんはっきり巻いた列 z −60 m の断面の粒子を、固定の窓で並べる（py -3.10、PIL、ffmpeg）。
新しい流体計算はしない。読むのは R/H30_E3/sec/z-080・z-060 の snap_*.npz（2 コマおき）と analysis_r.json・seat_r_z-080.json。
使い方: py -3.10 ft_side_video.py
出力: Unity/Build/FLIP39/FT/side/frames/*.png と Unity/Build/FLIP39/FT/R_side_sections.mp4
"""
import os, glob, json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont

RD = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/H30_E3"
OUT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/FT"
FF = r"G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"
TOFF = 35.0                      # 箱のコマ番号 → 群の時刻（r_strip.py と同じ）
X0, X1, Y0, Y1 = 320.0, 575.0, -14.0, 24.0   # 固定の窓（m）。x は 75 s の頂（z −80 m で x 324〜333 m）から箱の端（566 m）まで
W, H = 1280, 720
PX = (W - 40) / (X1 - X0)        # 縦横同じ縮尺（px/m）
MARKS = [(80.08, "頂の先が崩れ始めた（z −80）"), (84.50, "座席の目に水"), (85.92, "z −60 で空洞が閉じた")]


def snaps(z):
    return {int(os.path.basename(f)[5:9]): f for f in glob.glob(os.path.join(RD, "sec", "z%+04d" % z, "snap_*.npz"))}


def main():
    off = json.load(open(os.path.join(RD, "analysis_r.json"), encoding="utf8"))["off_box_m"]
    ride = json.load(open(os.path.join(RD, "seat_r_z-080.json"), encoding="utf8"))["best_seat"]["ride"]
    rt = np.array(ride["series"]["t_group"], float); ry = np.array(ride["series"]["eye_y"], float)
    rend = float(ride["end_t_group"])
    s80, s60 = snaps(-80), snaps(-60)
    frames = sorted(set(s80) & set(s60))
    fd = os.path.join(OUT, "side", "frames"); os.makedirs(fd, exist_ok=True)
    for f in glob.glob(os.path.join(fd, "*.png")):
        os.remove(f)
    fb = ImageFont.truetype(FONTB, 24); f1 = ImageFont.truetype(FONT, 17); f2 = ImageFont.truetype(FONT, 15)
    panels = [(-80, s80, 92, "z −80 m（座席の列。赤の線＝座席 x 530 m、灰の箱＝船。上下だけ水面に乗せた）"),
              (-60, s60, 372, "z −60 m（いちばんはっきり前へ巻いた列）")]
    ph = (Y1 - Y0) * PX
    t_all = [(k - 1) / 24.0 + TOFF for k in frames]
    tmin, tmax = min(t_all), max(t_all)
    for i, k in enumerate(frames):
        tg = (k - 1) / 24.0 + TOFF
        im = Image.new("RGB", (W, H), (251, 251, 249))
        dr = ImageDraw.Draw(im)
        dr.text((20, 10), "④ 横から見た断面（縦横同じ縮尺）　群の時刻 %.2f s" % tg, fill=(15, 15, 15), font=fb)
        dr.text((20, 44), "物理だけ（境界の造波と海底のみ）。茶＝R の粒子 0.3 m（断面 ±0.75 m。粒子は水面の下 5 m 前後の帯だけで、その下の水は描いていない）。\n高さは静かな水面から（水面のずれ 0.63 m を引いた推定）。目盛り 10 m × 5 m。", fill=(80, 80, 78), font=f2, spacing=3)
        for z, ss, oy, lab in panels:
            X = lambda x: 20 + (x - X0) * PX
            Y = lambda y: oy + 24 + ph - (y - Y0) * PX
            dr.text((20, oy), lab, fill=(30, 30, 30), font=f1)
            for gx in np.arange(330, X1 + 0.1, 10):
                dr.line([(X(gx), Y(Y0)), (X(gx), Y(Y1))], fill=(234, 234, 232))
            for gy in np.arange(-10, Y1 + 0.1, 5):
                dr.line([(X(X0), Y(gy)), (X(X1), Y(gy))], fill=(185, 185, 185) if gy == 0 else (234, 234, 232))
            dr.text((X(X1) - 120, Y(0) - 18), "静かな水面 0 m", fill=(150, 150, 150), font=f2)
            for gx in (350, 400, 450, 500, 550):
                dr.text((X(gx) - 18, Y(Y0) + 2), "x %d" % gx, fill=(150, 150, 150), font=f2)
            d = np.load(ss[k])
            x = d["x"]; y = d["y"] - off
            m = (x > X0) & (x < X1) & (y > Y0) & (y < Y1)
            px = np.clip(((x[m] - X0) * PX + 20).astype(int), 0, W - 2)
            py = np.clip((oy + 24 + ph - (y[m] - Y0) * PX).astype(int), 0, H - 2)
            a = np.asarray(im).copy()
            for dx in (0, 1):
                for dy in (0, 1):
                    a[py + dy, px + dx] = (150, 92, 44)
            im = Image.fromarray(a); dr = ImageDraw.Draw(im)
            if m.any():
                j = int(np.argmax(y[m])); cx, cy = float(x[m][j]), float(y[m][j])
                dr.line([(X(cx), Y(cy)), (X(cx), Y(0))], fill=(40, 90, 170), width=1)
                dr.text((X(cx) + 6, Y(cy) - 6), "最も高い粒子 %.1f m" % cy, fill=(40, 90, 170), font=f2)
            if z == -80:
                dr.line([(X(530), Y(Y0)), (X(530), Y(Y1))], fill=(200, 60, 60), width=2)
                if tg <= rend + 1e-6:
                    ey = float(np.interp(tg, rt, ry))
                    by = ey - 1.83
                    dr.rectangle([X(530 - 5.67), Y(by + 0.6), X(530 + 5.67), Y(by)], fill=(110, 110, 120))
                    dr.ellipse([X(530) - 4, Y(ey) - 4, X(530) + 4, Y(ey) + 4], fill=(200, 60, 60))
                else:
                    dr.text((X(530) + 6, Y(Y1) + 2), "84.5 s に座席の目に水", fill=(200, 60, 60), font=f2)
            if z == -60 and tg >= 85.92:
                dr.text((X(526) - 60, Y(Y0) - 20), "空洞が閉じた 85.92 s・x 526 m", fill=(200, 60, 60), font=f2)
        # 時刻の帯
        bx0, bx1, by = 20, W - 20, 668
        dr.rectangle([bx0, by, bx1, by + 8], fill=(225, 225, 222))
        dr.rectangle([bx0, by, bx0 + (bx1 - bx0) * (tg - tmin) / (tmax - tmin), by + 8], fill=(60, 80, 110))
        for tm, lab in MARKS:
            xx = bx0 + (bx1 - bx0) * (tm - tmin) / (tmax - tmin)
            dr.line([(xx, by - 4), (xx, by + 14)], fill=(200, 60, 60), width=2)
            dr.text((xx + 4, by + 12), lab, fill=(200, 60, 60), font=f2)
        dr.text((bx0, by - 22), "%.1f s" % tmin, fill=(120, 120, 120), font=f2)
        dr.text((bx1 - 50, by - 22), "%.1f s" % tmax, fill=(120, 120, 120), font=f2)
        im.save(os.path.join(fd, "f%04d.png" % i))
    n = len(frames)
    out = os.path.join(OUT, "R_side_sections.mp4")
    # 断面は 2 コマおき（12 コマ/秒）＝実時間。最後のコマを 1 秒止める
    subprocess.run([FF, "-v", "error", "-y", "-framerate", "12", "-i", os.path.join(fd, "f%04d.png"),
                    "-vf", "tpad=stop_mode=clone:stop_duration=1,fps=24", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", out], check=True)
    print(out, n, "frames", tmin, tmax)


if __name__ == "__main__":
    main()
