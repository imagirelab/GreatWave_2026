# -*- coding: utf-8 -*-
"""仕上げ33 の前後の図（1920×1080）と前後を並べた動画（pl32_sheets.py を写し、見出し・拡大の所・名前を替えた）。

前＝仕上げ32（コミット ede11c8 の状態＝修正の回 1。描画は Build/Polish/32/fix01/r_fix01、PL32Render の同じ手順）、
後＝仕上げ33（Build/Polish/33/r_after。PL33Render、爪の並び Build/Polish/33/claws、-pl33Look 1）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。この道具は既にある画像を並べるだけ（新しい描画はしない）。

  fig_pl33_ba_view_<視点>.png         7 視点 × t 6・9・10.5・12 s（上：前、次：後）と、t 10.5 s・t* の前後の拡大
  fig_pl33_ba_turntable_t<時刻>.png   回り台 12 方位（爪・飛沫あり）の前後
  pl33_ba_<視点>_30fps.mp4           前｜後 を左右に並べた動画（t 0〜14 s、30 fps）
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33_sheets.py --before Unity/Build/Polish/32/fix01/r_fix01 --after Unity/Build/Polish/33/r_after --out Docs/Evidence/Polish/33
"""
import argparse
import os
import subprocess
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, label, head, tile, fit  # noqa: E402

FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
# 拡大の所（爪の頂・唇・b区域・冠の爪）
ZOOM = {"painting": (380, 60, 1180, 620), "seat": (500, 300, 1500, 1080), "seat_toward_wave": (300, 0, 1500, 675),
        "side_left": (600, 280, 1500, 800), "side_right": (780, 330, 1320, 800), "back65": (700, 230, 1500, 760), "top": (420, 340, 1140, 900)}
HEAD_B = ("前＝仕上げ32（コミット ede11c8。修正の回 1 の状態）：爪 184 本（b区域 57）を K*′ P28R2rec のシートに結び付け、面に沿う帯"
          "（原画のカメラの向きへ 8.5 cm＋厚みの 1/4）。根元の円は水色の版、縁の線は根元で開く。爪は原画のカメラから見える面（頂の前・唇・b区域）だけにある")
HEAD_A = ("後＝仕上げ33：① pl33_ray_relief：原画の爪の輪と先を、t* のその点から原画のカメラへの射線の向きへ立ち上げ（帯の弧長 × 0.35 × 根元 0 → 先の形、"
          "上限 0.8 m、根元の座標系で運ぶ。原画視点の投影は変えない）、② pl33_hook_web・pl33_tuft_web：爪の巻きの内側に水色の版の膜（帯の幅 × 1.0、b区域は × 1.8。"
          "縁の線なし。原画視点で主役波の外へ出る輪は潰す）、③ pl33_crown：頂の裏（原画のカメラから隠れた白の範囲、稜から 0.8〜4.5 m）に冠の爪 168 本"
          "（長さ 1.0〜3.0 m・中央値 1.9 m、法線から立ち上がって稜の向き（47 本は逆の向き）へ巻く鉤。t* の原画視点で見えないことを描画の差 0 画素で確かめた）")


def view_sheets(a, out):
    files = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ33 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
             "前＝仕上げ32（ede11c8、修正の回 1 の状態）、後＝仕上げ33（爪の造形）。下の段は t 10.5 s と t* の拡大。前・後の中身は図の下の欄。Unity の PC オフスクリーン描画（HMD ではない）。")
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        crop = ZOOM.get(v)
        cw = 474
        ch = int(round(cw * (crop[3] - crop[1]) / float(crop[2] - crop[0])))
        ch = min(ch, 300)
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 610
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    t = fit(Image.open(p).convert("RGB").crop(crop), (cw, ch))
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        f = font(15)
        y = 610 + ch + 8
        for para in (HEAD_B + "。", HEAD_A + "。"):
            for ln in wrap(d, para, 1890, f):
                d.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 21
        p = os.path.join(out, "fig_pl33_ba_view_%s.png" % v)
        im.save(p)
        files.append(p)
    return files


def wrap(d, text, width, f):
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ33 回り台｜%s｜方位ごとに上：前　下：後（爪・飛沫・線あり、周りの海を含む）" % tn,
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜32 と同じ置き方）。Unity の PC 描画。")
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
        p = os.path.join(out, "fig_pl33_ba_turntable_%s.png" % ts)
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
        p = os.path.join(out, "pl33_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ32':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 仕上げ33':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2")
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "27",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", p]
        subprocess.run(cmd, check=True)
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
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
