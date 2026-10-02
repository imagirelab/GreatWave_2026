# -*- coding: utf-8 -*-
"""仕上げ33修正02：前（仕上げ33修正01）と後（仕上げ33修正02 修正の回 2 の後の採る状態）の視点ごとの前後の図・回り台の図・前後の動画を作る。
pl33r01/r01_sheets.py を写し、見出し・前後・出力の名前を替えた。時刻は t 9・10.5・12 s。

出力（--out。既定 Unity/Build/Polish/33r02/evidence）：
  fig_pl33r02_ba_view_<視点>.png（7 視点 × t 9・10.5・12 s の前後と、t 10.5 s・t* の拡大の前後）
  fig_pl33r02_ba_turntable_t<時刻>.png（回り台 12 方位の前後）
  pl33r02_ba_<視点>_30fps.mp4（前｜後 を左右に並べた動画）
使い方：py -3.10 -B Tools/GWWaveGen/pl33r02/r02_sheets.py [--after <描画>] [--skip-video]
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_sheets as S  # noqa: E402

TS = [("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
HEAD_B = ("前＝仕上げ33修正01（修正の回 1、コミット ebcc72c）：原画の爪 184 本を原画のカメラの射線の上で立てた 3D の指（長さ 0.7〜6.5 m。射線の向きに長く伸び、"
          "座席から同じ向きに傾く箒に見えた）、鉤の内の水色の膜（指の膜 180・仕上げ33 の膜 180）、冠の爪 127 本")
HEAD_A = ("後＝仕上げ33修正02（修正の回 2）：指の 3D の長さを 2 次元の道の 2.6 倍までにし、そのうち射線の向きの成分を 1.2 m（id ごとに ±30%）までにした（稜と輪郭にかかる指を除く。"
          "主役の指の伸ばしはやめた）。長さは id ごとに ±25% 不揃いにし、立ち上がり・保ち・先の巻き戻り（0.9）の 3 段の鉤にした（指の長さ 0.45〜2.8 m、中央値 1.13 m）。"
          "射線の向きの棒にしかならない 2 本（C087・C092）は仕上げ33 の低い浮き彫りの帯に戻した。膜は主役波の輪郭の帯に出さず、輪郭をまたぐ指 9 本には付けない。"
          "冠の爪は房ごとに 2 本に 1 本（71 本）にして断面を 2.4 倍（先へ 3.2 倍）に太らせた。"
          "色は PL29 Claw Shade の白と水色の版、線は設計38 の縁の線（原画カメラからの投影の色は使わない）")



def view_sheets(a, out):
    files = []
    for v, name in S.VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        S.head(d, "仕上げ33修正02 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
               "前＝仕上げ33修正01、後＝仕上げ33修正02（棒をなくした 3 段の鉤の指）。下の段は t 10.5 s と t* の拡大。Unity の PC オフスクリーン描画（HMD ではない）。")
        tw, th = 632, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = S.tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                S.label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        crop = S.ZOOM.get(v)
        cw = 474
        ch = int(round(cw * (crop[3] - crop[1]) / float(crop[2] - crop[0])))
        ch = min(ch, 300)
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 610
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    t = S.fit(Image.open(p).convert("RGB").crop(crop), (cw, ch))
                    im.paste(t, (x, y))
                S.label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        f = S.font(15)
        y = 610 + ch + 8
        for para in (HEAD_B + "。", HEAD_A + "。"):
            for ln in S.wrap(d, para, 1890, f):
                d.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 21
        p = os.path.join(out, "fig_pl33r02_ba_view_%s.png" % v)
        im.save(p)
        files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        S.head(d, "仕上げ33修正02 回り台｜%s｜方位ごとに上：前（仕上げ33修正01）　下：後（仕上げ33修正02）（爪・飛沫・線あり、周りの海を含む）" % tn,
               "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜33 と同じ置き方）。Unity の PC 描画。")
        tw, th = 316, 178
        for k in range(12):
            az = k * 30
            col, blk = k % 6, k // 6
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + col * (tw + 4), 66 + blk * (2 * th + 30) + si * (th + 2)
                t = S.tile(os.path.join(root, "tt", "%s_az%03d_claws.png" % (ts, az)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                S.label(d, x + 3, y + 3, "%s｜方位 %d°" % (lab, az), 12)
        p = os.path.join(out, "fig_pl33r02_ba_turntable_%s.png" % ts)
        im.save(p)
        files.append(p)
    return files


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        b = os.path.join(a.before, "video", "pl32_%s_30fps.mp4" % v)
        f = os.path.join(a.after, "video", "pl32_%s_30fps.mp4" % v)
        if not (os.path.exists(b) and os.path.exists(f)):
            continue
        p = os.path.join(out, "pl33r02_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ33修正01':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 仕上げ33修正02':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2")
        cmd = [S.FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "28",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", p]
        subprocess.run(cmd, check=True)
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/33r01/fix01/r_fix01")
    ap.add_argument("--after", default=REPO + "/Unity/Build/Polish/33r02/r_final")
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/33r02/evidence")
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fs = view_sheets(a, a.out) + turntable(a, a.out)
    if not a.skip_video:
        fs += videos(a, a.out)
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
