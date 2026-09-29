# -*- coding: utf-8 -*-
"""設計30 第B部：Unity の単発再生の静止画を 1 枚の並べ図にし、4 視点の動画を 2 × 2 に並べた確認用の動画を作る（記録用）。

入力：<out>/stills/ds30_<視点>_t<秒>s_tau<τ>.png（DS30Render）、<out>/video/ds30_<視点>_30fps.mp4
出力：<out>/fig_ds30_stills_sheet.png（行 = 視点、列 = t）、<out>/video/ds30_grid_2x2_30fps.mp4
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/ds30/ds30b_sheet.py --out Unity/Build/Design/30/unity/single
"""
import argparse
import glob
import os
import re
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left"]


def font(sz):
    for f in ("C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.exists(f):
            return ImageFont.truetype(f, sz)
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--no-video", action="store_true")
    a = ap.parse_args()
    out = os.path.join(REPO, a.out)
    files = glob.glob(os.path.join(out, "stills", "ds30_*.png"))
    rx = re.compile(r"ds30_(.+)_t(\d+\.\d)s_tau([+-]\d+\.\d+)\.png$")
    cells = {}
    for f in files:
        m = rx.search(os.path.basename(f))
        if m:
            cells[(m.group(1), float(m.group(2)))] = (f, m.group(3))
    ts = sorted({k[1] for k in cells})
    W, H, pad, top, left = 480, 270, 6, 40, 150
    sheet = Image.new("RGB", (left + len(ts) * (W + pad), top + len(VIEWS) * (H + pad)), (255, 255, 255))
    d = ImageDraw.Draw(sheet)
    fs = font(20)
    for j, t in enumerate(ts):
        tau = next((v[1] for k, v in cells.items() if k[1] == t), "")
        d.text((left + j * (W + pad) + 6, 8), "t = %.1f s（τ %s s）" % (t, tau), fill=(0, 0, 0), font=fs)
    for i, v in enumerate(VIEWS):
        d.text((6, top + i * (H + pad) + H // 2 - 10), v, fill=(0, 0, 0), font=fs)
        for j, t in enumerate(ts):
            if (v, t) in cells:
                im = Image.open(cells[(v, t)][0]).convert("RGB").resize((W, H), Image.LANCZOS)
                sheet.paste(im, (left + j * (W + pad), top + i * (H + pad)))
    p = os.path.join(out, "fig_ds30_stills_sheet.png")
    sheet.save(p)
    print("sheet", p, sheet.size)
    if a.no_video:
        return
    vids = [os.path.join(out, "video", "ds30_%s_30fps.mp4" % v) for v in VIEWS]
    if all(os.path.exists(x) for x in vids):
        o = os.path.join(out, "video", "ds30_grid_2x2_30fps.mp4")
        fc = ("[0:v]scale=960:540[a];[1:v]scale=960:540[b];[2:v]scale=960:540[c];[3:v]scale=960:540[d];"
              "[a][b]hstack[top];[c][d]hstack[bot];[top][bot]vstack[v]")
        cmd = [FFMPEG, "-y", "-loglevel", "error"] + sum([["-i", x] for x in vids], []) + ["-filter_complex", fc, "-map", "[v]", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", "-r", "30", o]
        subprocess.run(cmd, check=True)
        print("grid", o)


if __name__ == "__main__":
    main()
