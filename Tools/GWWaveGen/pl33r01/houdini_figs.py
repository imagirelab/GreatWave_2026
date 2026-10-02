# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 5：前（仕上げ33 の採用）と後（立つ白い爪の指）の図と動画（PIL・ffmpeg）。

  fig_pl33r01h_ba_view_<視点>.png        7 視点 × t 9・10.5・12 s（上：前、下：後）と t 10.5 s・t* の拡大
  fig_pl33r01h_ba_turntable_t<時刻>.png  回り台 12 方位の前後（t 9・10.5・12 s）
  fig_pl33r01h_overlay_painting.png      原画視点 t*：原画（DP130155 を表示の枠へ）｜後｜後 ＋ 爪の一覧の中心線（赤）と領域（緑）｜前 ＋ 同じ重ね
  pl33r01h_ba_<視点>_30fps.mp4           前｜後 の横並び（5 MB 以下）
原画の図はリポジトリの DP130155 だけ。参照の彫刻の写真・参照モデルから作った図はない。
"""
import argparse
import json
import os
import subprocess
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl30")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
from pl30_sheets import font, label, head, tile, fit  # noqa: E402
import pl32f_measure as M  # noqa: E402

FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
ZOOM = {"painting": (380, 60, 1180, 620), "seat": (450, 150, 1500, 900), "seat_toward_wave": (300, 0, 1500, 675),
        "side_left": (600, 280, 1500, 800), "side_right": (780, 330, 1320, 800), "back65": (700, 230, 1500, 760), "top": (420, 340, 1140, 900)}
HEAD_B = "前＝仕上げ33（コミット 1ed9aa8、修正の回 2 の採用）：原画の爪 184 の低い浮き彫り（面に沿う帯）、鉤の内の水色の膜 184、b区域の添え指 114、頂の裏の冠の爪 79"
HEAD_A = ("後＝仕上げ33修正01（Houdini の変種）：爪の一覧の中心線（原画の爪 184・b区域の添え指 101、計 285 本）から、Houdini の CTRL の曲がりと細りのランプで先へ細る丸い指を立て"
          "（原画のカメラへの射線の上で手前へ立ち上げ、断面は射線の向きへ 3 倍に伸ばす。原画視点の投影は一覧の形と幅のまま）、頂の帯（根元の白の円の上の薄い台）と"
          "VDB の滑らかな和（VDB Reshape SDF の close）で根元が盛り上がる一つの塊にした。t* の鍵の形を中心線に結び付けて全コマへ動かす。鉤の内の水色の膜 184 と頂の裏の冠の爪 79 は仕上げ33 のまま。"
          "色は PL29 Claw Shade の白と水色の版の段だけ（原画の投影なし）")


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


def view_sheets(a, out):
    files = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ33修正01（Houdini）視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
             "前＝仕上げ33 の採用、後＝立つ白い爪の指（Houdini）。下の段は t 10.5 s と t* の拡大。Unity の PC オフスクリーン描画（HMD ではない）。")
        tw, th = 636, 270
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
        ch = min(ch, 330)
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 616
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    t = fit(Image.open(p).convert("RGB").crop(crop), (cw, ch))
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        f = font(14)
        y = 616 + ch + 6
        for para in (HEAD_B + "。", HEAD_A + "。"):
            for ln in wrap(d, para, 1890, f):
                d.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 19
        p = os.path.join(out, "fig_pl33r01h_ba_view_%s.png" % v)
        im.save(p)
        files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ33修正01（Houdini）回り台｜%s｜方位ごとに上：前　下：後（爪・飛沫・線あり、周りの海を含む）" % tn,
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜33 と同じ置き方）。Unity の PC 描画。")
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
        p = os.path.join(out, "fig_pl33r01h_ba_turntable_%s.png" % ts)
        im.save(p)
        files.append(p)
    return files


def overlay(a, out):
    inv = json.load(open(INV, encoding="utf-8"))
    P = M.paint_disp()[:, :, ::-1].copy()   # BGR → RGB
    aft = np.array(Image.open(os.path.join(a.after, "views", "painting_t120_asis.png")).convert("RGB"))
    bef = np.array(Image.open(os.path.join(a.before, "views", "painting_t120_asis.png")).convert("RGB"))

    def draw_list(img):
        o = img.copy()
        for c in inv["claws"]:
            if c.get("zone") != "main":
                continue
            if c.get("region_polygon_ref"):
                q = np.round(M.r2d(np.asarray(c["region_polygon_ref"], np.float64))).astype(np.int32)
                cv2.polylines(o, [q], True, (40, 170, 60), 1, cv2.LINE_AA)
            if c.get("centerline_ref"):
                q = np.round(M.r2d(np.asarray(c["centerline_ref"], np.float64))).astype(np.int32)
                cv2.polylines(o, [q], False, (230, 30, 30), 1, cv2.LINE_AA)
        return o
    crop = (300, 40, 1260, 580)
    panels = [("原画（DP130155、表示の枠）", P), ("後（立つ白い爪の指）t*", aft), ("後 ＋ 爪の一覧（赤：中心線、緑：領域）", draw_list(aft)),
              ("前（仕上げ33）＋ 爪の一覧", draw_list(bef))]
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    for k, (nm, arr) in enumerate(panels):
        t = Image.fromarray(arr[crop[1]:crop[3], crop[0]:crop[2]]).resize((956, 538), Image.LANCZOS)
        x, y = (k % 2) * 962 + 2, (k // 2) * 541 + 2
        im.paste(t, (x, y))
        label(d, x + 6, y + 6, nm, 18)
    p = os.path.join(out, "fig_pl33r01h_overlay_painting.png")
    im.save(p)
    return [p]


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        b = os.path.join(a.before, "video", "pl32_%s_30fps.mp4" % v)
        f = os.path.join(a.after, "video", "pl32_%s_30fps.mp4" % v)
        if not (os.path.exists(b) and os.path.exists(f)):
            continue
        p = os.path.join(out, "pl33r01h_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ33':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 立つ指（Houdini）':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2")
        for crf in ("27", "31", "35"):
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", crf,
                   "-pix_fmt", "yuv420p", "-movflags", "+faststart", p]
            subprocess.run(cmd, check=True)
            if os.path.getsize(p) <= 5 * 1024 * 1024:
                break
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/33/fix02/r_fix02")
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fs = []
    if not a.only or "views" in a.only:
        fs += view_sheets(a, a.out)
    if not a.only or "tt" in a.only:
        fs += turntable(a, a.out)
    if not a.only or "overlay" in a.only:
        fs += overlay(a, a.out)
    if not a.skip_video and (not a.only or "video" in a.only):
        fs += videos(a, a.out)
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
