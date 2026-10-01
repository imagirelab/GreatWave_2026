# -*- coding: utf-8 -*-
"""仕上げ28：粘土のこま（pl28_clay_render.py、960×540）を、同じ視点・同じ画面の時刻で E｜F_final｜G_final と並べる。
設計28修正01 の試行F の評審の並べ（作業場所の compose_f.py）と同じ考え方で、列を 3 つ（またはそれ以上）にした。形と速さの確認用で、作品の見た目ではない。

  video VIEW [TAGS]    ：画面の時刻 t 0〜14 s を 30 fps で横に並べた動画（各列はその版自身の時間曲線 τ(t)）。
                         各列 640×360（証拠の 5 MB に収めるため縮める。元のこまは 960×540）。
  mosaic [TAGS]        ：4 視点（正側面・座席 仰角 30°・座席から波の方向・後ろ 65°）× 版 の動画（各 480×270）
  sheet VIEW T1,T2,... [TAGS]：1920×1080 の PNG。行 = 版、列 = 画面の時刻（同じ視点・同じ時刻の前後の図）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl28/pl28_clay_compose.py video side_follow
版の指定：E・F_final・G_final は下の TAG_DEF。ほかは NAME=こまのフォルダー|時間曲線 の形で TAGS に書ける。
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
R = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = os.path.join(R, "Unity", "Build", "Polish", "28", "clay")
FF = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
FONT = r"C:\Windows\Fonts\meiryo.ttc"
TAG_DEF = {
    "E": (os.path.join(R, "Unity", "Build", "Design", "28R01F", "clay", "frames", "E"),
          os.path.join(R, "Tools", "GWWaveGen", "ds28r01e", "timewarp_default_E.json")),
    "F_final": (os.path.join(R, "Unity", "Build", "Design", "28R01F", "clay", "frames", "F_final"),
                os.path.join(R, "Unity", "Build", "Design", "28R01F", "F_final", "timewarp_F_final.json")),
    "G_final": (os.path.join(OUT, "frames", "G_final"),
                os.path.join(R, "Unity", "Build", "Polish", "28", "G_final", "timewarp_G_final.json")),
}
LABEL = {"E": "E（古い K* ＋ 動き E。設計28修正01 の途中）", "F_final": "F_final（K*′ R4 ＋ 動き F。今の体験）",
         "G_final": "G_final（K*′ P28R2 ＋ 動きの当て直し。仕上げ28）", "G_p28a": "G_p28a（修正の回：上の背＋奥の鉤。採らない）",
         "G_p28b": "G_p28b（修正の回：奥の鉤だけ。回復の前）",
         "G_p28rec": "G_p28rec（K*′ P28R2rec ＋ 奥の鉤。仕上げ28 の回復・採用）"}
LCOL = {"E": (200, 100, 0), "F_final": (20, 80, 210), "G_final": (20, 140, 70), "G_p28b": (120, 60, 140), "G_p28rec": (170, 40, 40)}
VIEWNAME = {"side_follow": "正側面（波の枠を追う）", "seat_up30": "座席（仰角 30°）", "seat_toward_wave": "座席から波の方向",
            "painting": "原画視点", "back34_follow": "後ろ 65°（波の枠を追う）"}
VIEWS4 = ["side_follow", "seat_up30", "seat_toward_wave", "back34_follow"]
CROP = {"side_follow": (300, 60, 700, 300), "back34_follow": (330, 110, 820, 450)}   # 動画で波を大きく見せる切り出し（960×540 のこまの座標）
DEFAULT_TAGS = ["E", "F_final", "G_final"]


def parse_tags(s):
    out = []
    for x in (s.split(",") if s else DEFAULT_TAGS):
        if "=" in x:
            n, v = x.split("=", 1)
            d, w = v.split("|")
            TAG_DEF[n] = (d if os.path.isabs(d) else os.path.join(R, d), w if os.path.isabs(w) else os.path.join(R, w))
            LABEL.setdefault(n, n)
            LCOL.setdefault(n, (90, 90, 90))
            x = n
        out.append(x)
    return out


def warp(tag):
    w = json.load(open(TAG_DEF[tag][1], encoding="utf-8"))
    return np.asarray(w["t"], float), np.asarray(w["tau"], float)


def F(sz):
    return ImageFont.truetype(FONT, sz)


def fpath(tag, view, i):
    return os.path.join(TAG_DEF[tag][0], view, "f_%04d.png" % i)


def writer(out, W, H, crf):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    return subprocess.Popen([FF, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", "30", "-i", "-",
                             "-c:v", "libx264", "-preset", "medium", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", out],
                            stdin=subprocess.PIPE)


def header(d, W, text, t, taus):
    d.rectangle([0, 0, W, 56], fill=(20, 20, 20))
    d.text((10, 4), text, fill=(255, 255, 255), font=F(20))
    d.text((10, 30), "画面の時刻 t = %5.2f s（t* = 12.0 s）   " % t + "   ".join("%s τ = %+.2f s" % (k, v) for k, v in taus),
           fill=(220, 220, 220), font=F(17))


def video(view, tags, n=420, pw=640, ph=360, crf=24):
    box = CROP.get(view)
    if box:
        ph = int(round(pw * (box[3] - box[1]) / (box[2] - box[0])))
        ph += ph % 2
    W, H = pw * len(tags), 56 + ph + 30
    W += W % 2
    wv = {k: warp(k) for k in tags}
    out = os.path.join(OUT, "video", "clay_%s_%s.mp4" % (view, "_vs_".join(tags)))
    p = writer(out, W, H, crf)
    for i in range(n):
        t = i / 30.0
        img = Image.new("RGB", (W, H), (20, 20, 20))
        d = ImageDraw.Draw(img)
        header(d, W, "粘土（形と速さだけを見る。作品の色ではない）  %s" % VIEWNAME[view], t, [(k, float(np.interp(t, *wv[k]))) for k in tags])
        for j, k in enumerate(tags):
            im = Image.open(fpath(k, view, i)).convert("RGB")
            if box:
                im = im.crop(box)
            im = im.resize((pw, ph), Image.LANCZOS)
            img.paste(im, (j * pw, 56))
            d.rectangle([j * pw, 56 + ph, (j + 1) * pw, H], fill=LCOL[k])
            d.text((j * pw + 8, 56 + ph + 4), LABEL[k], fill=(255, 255, 255), font=F(16))
        p.stdin.write(np.asarray(img, np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    print("video", out, os.path.getsize(out))
    return out


def mosaic(tags, n=420, cw=480, ch=270, crf=26):
    W, H = 170 + cw * len(tags), 56 + 30 + ch * len(VIEWS4)
    W += W % 2
    wv = {k: warp(k) for k in tags}
    out = os.path.join(OUT, "video", "clay_4views_%s.mp4" % "_vs_".join(tags))
    p = writer(out, W, H, crf)
    for i in range(n):
        t = i / 30.0
        img = Image.new("RGB", (W, H), (20, 20, 20))
        d = ImageDraw.Draw(img)
        header(d, W, "粘土 4 視点（列：%s）" % "｜".join(tags), t, [(k, float(np.interp(t, *wv[k]))) for k in tags])
        for j, k in enumerate(tags):
            d.rectangle([170 + j * cw, 56, 170 + (j + 1) * cw, 86], fill=LCOL[k])
            d.text((170 + j * cw + 6, 60), k, fill=(255, 255, 255), font=F(17))
        for r, v in enumerate(VIEWS4):
            d.text((6, 86 + r * ch + ch // 2 - 10), VIEWNAME[v], fill=(255, 255, 255), font=F(15))
            for j, k in enumerate(tags):
                im = Image.open(fpath(k, v, i)).convert("RGB").resize((cw, ch), Image.BILINEAR)
                img.paste(im, (170 + j * cw, 86 + r * ch))
        p.stdin.write(np.asarray(img, np.uint8).tobytes())
    p.stdin.close()
    p.wait()
    print("mosaic", out, os.path.getsize(out))
    return out


def sheet(view, times, tags, out=None, crop=None):
    """1920×1080：行 = 版、列 = 画面の時刻。crop = (x0, y0, x1, y1)（960×540 のこまの座標）で切り出す。"""
    W, H = 1920, 1080
    left, top = 150, 64
    ncol = len(times)
    cw = (W - left) // ncol
    box = crop or (0, 0, 960, 540)
    bh = int(round(cw * (box[3] - box[1]) / (box[2] - box[0])))
    rh = min(bh + 26, (H - top) // len(tags))
    bh = rh - 26
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((10, 6), "粘土 %s：同じ視点・同じ画面の時刻（t* = 12 s）。行：%s" % (VIEWNAME[view], "｜".join(tags)), fill=(0, 0, 0), font=F(22))
    d.text((10, 36), "形と速さだけを見る図（作品の色・線・白ではない）。各行はその版自身の時間曲線 τ(t) で描いた", fill=(60, 60, 60), font=F(16))
    for ri, k in enumerate(tags):
        y = top + ri * rh
        d.rectangle([0, y, left - 6, y + bh], fill=LCOL[k])
        d.text((6, y + 4), k, fill=(255, 255, 255), font=F(20))
        wt, wtau = warp(k)
        for c, t in enumerate(times):
            i = int(round(t * 30))
            im = Image.open(fpath(k, view, min(i, 419))).convert("RGB").crop(box)
            bw = cw - 4
            im = im.resize((bw, int(round(bw * (box[3] - box[1]) / (box[2] - box[0])))), Image.LANCZOS)
            if im.height > bh:
                im = im.crop((0, (im.height - bh) // 2, bw, (im.height - bh) // 2 + bh))
            img.paste(im, (left + c * cw, y))
            d.text((left + c * cw + 3, y + bh + 2), "t %.1f  τ %+.2f" % (t, float(np.interp(t, wt, wtau))), fill=(0, 0, 0), font=F(14))
    out = out or os.path.join(OUT, "sheet_%s_%s.png" % (view, "_".join(tags)))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("sheet", out, img.size)
    return out


if __name__ == "__main__":
    m = sys.argv[1]
    if m == "video":
        pw = int(sys.argv[4]) if len(sys.argv) > 4 else 640
        video(sys.argv[2], parse_tags(sys.argv[3] if len(sys.argv) > 3 else ""), pw=pw)
    elif m == "mosaic":
        mosaic(parse_tags(sys.argv[2] if len(sys.argv) > 2 else ""))
    elif m == "sheet":
        crop = None
        tags = parse_tags(sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else "")
        if len(sys.argv) > 5:
            crop = tuple(int(v) for v in sys.argv[5].split(","))
        out = sys.argv[6] if len(sys.argv) > 6 else None
        sheet(sys.argv[2], [float(x) for x in sys.argv[3].split(",")], tags, out=out, crop=crop)
    else:
        raise SystemExit(__doc__)
