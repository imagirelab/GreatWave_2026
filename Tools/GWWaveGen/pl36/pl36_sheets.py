# -*- coding: utf-8 -*-
"""仕上げ36 の前後の図（1920×1080）と前後を並べた動画（仕上げ33 の pl33_sheets.py を写し、見出し・名前・図を替えた）。

前＝仕上げ35 の状態（＝仕上げ33修正01 のコミット ebcc72c の採る状態と画素まで同じ。描画は Build/Polish/35/r_after。主役波は PL29 Ukiyoe Keypose）、
後＝仕上げ36（Build/Polish/36/r_after。PL36Render、主役波は PL36 Ukiyoe Keypose と Tools/GWWaveGen/pl36/pl36_material_params.txt）。
爪の並び・飛沫・海・線・形・動きは前と同じ。どれも Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。この道具は既にある画像を並べるだけ。

  fig_pl36_ba_view_<視点>.png         7 視点 × t 6・9・10.5・12 s（上：前、次：後）と、t 10.5 s・t* の前後の拡大
  fig_pl36_ba_turntable_t<時刻>.png   回り台 12 方位（爪・飛沫あり）の前後
  fig_pl36_painting_compare.png        原画視点の頂の拡大：原画｜前｜後（t*）と前｜後（t 10.5 s）
  fig_pl36_zone_diag.png               爪の帯（藍の地＝赤、淡い水色の輪＝緑）と谷の底の段（青）の印（_PL29Diag 12、主役波だけ、7 視点 × t 10.5・12 s）
  fig_pl36_valley.png                  谷の底の段：座席から波の方向・座席の低い視点（t28 の組）の前後
  pl36_ba_<視点>_30fps.mp4            前｜後 を左右に並べた動画（t 0〜14 s、30 fps）
使い方：py -3.10 -B Tools/GWWaveGen/pl36/pl36_sheets.py --before Unity/Build/Polish/35/r_after --after Unity/Build/Polish/36/r_after --out Docs/Evidence/Polish/36
"""
import argparse
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pl30"))
from pl30_sheets import font, label, head, tile, fit  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
TS = [("t060", "t 6 s"), ("t090", "t 9 s"), ("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]
ZOOM = {"painting": (300, 50, 1180, 620), "seat": {"t105": (450, 640, 1450, 1080), "t120": (450, 230, 1450, 670)}, "seat_toward_wave": (300, 350, 1700, 1080),
        "side_left": (600, 280, 1500, 800), "side_right": (700, 300, 1400, 800), "back65": (700, 230, 1500, 760), "top": (560, 340, 1460, 900)}
HEAD_B = ("前＝仕上げ35 の状態（仕上げ33修正01 のコミット ebcc72c と同じ画素）：主役波は PL29 Ukiyoe Keypose。前の白は頂から唇の先の側の F_end(c) まで白一色"
          "（房・泡の粒・淡い水色の流れの線）で、3D の白い爪はこの白の上に立つ。前面の下は藍濃に藍中の溝")
HEAD_A = ("後＝仕上げ36：PL36 Ukiyoe Keypose。① 前の白を、頂の白の帯（F < F_cz(c)、縁に揃わない房）と、その先の爪の帯に分け、爪の帯の地を藍"
          "（藍濃に藍中の溝・白い点）にし、頂の白の帯の側に淡い水色の輪（藍中の流れの線、b区域 0.3〜0.4 F・窓 0.10 F・唇の塊 0.5〜0.8 F・唇の端は帯の全部）と、"
          "輪へ食い込む藍の舌（周期 3.1 m）を置いた。背・頂の白の帯・右の側面から見える唇の外の面は白のまま。② 谷の底の段：前面の下で今の高さが −0.8 m より低い所は"
          "胴の藍中の溝を太らせた藍中の地に藍濃の溝、境に線。どれも面の座標（F・c・ca）・今の高さ・T_white だけで決め、原画カメラの投影は使わない（Q28）")


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


def foot(d, y, paras, f=None):
    f = f or font(15)
    for para in paras:
        for ln in wrap(d, para, 1890, f):
            d.text((14, y), ln, fill=(40, 48, 64), font=f)
            y += 21
    return y


def view_sheets(a, out):
    files = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ36 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
             "前＝仕上げ35（＝仕上げ33修正01 ebcc72c）、後＝仕上げ36（限定色：爪の帯の藍の地と淡い水色の輪、谷の底の段）。下の段は t 10.5 s と t* の拡大。Unity の PC オフスクリーン描画（HMD ではない）。")
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        cw = 474
        ch = 300
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            crop = ZOOM.get(v)
            crop = crop[ts] if isinstance(crop, dict) else crop
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 610
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    im.paste(fit(Image.open(p).convert("RGB").crop(crop), (cw, ch)), (x, y))
                label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        foot(d, 610 + ch + 8, (HEAD_B + "。", HEAD_A + "。"))
        p = os.path.join(out, "fig_pl36_ba_view_%s.png" % v)
        im.save(p)
        files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ36 回り台｜%s｜方位ごとに上：前（仕上げ35）　下：後（仕上げ36）（爪・飛沫・線あり、周りの海を含む）" % tn,
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29〜35 と同じ置き方）。Unity の PC 描画。")
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
        p = os.path.join(out, "fig_pl36_ba_turntable_%s.png" % ts)
        im.save(p)
        files.append(p)
    return files


def painting_compare(a, out):
    """原画（表示の枠へ縮めた DP130155）｜前｜後 の頂の拡大（t*）と、前｜後（t 10.5 s）。"""
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ36 原画視点の頂の拡大｜上：原画・前・後（t*）　下：前・後（t 10.5 s）と、後の爪の帯の印（t*）",
         "原画はメトロポリタン美術館 JP1847（DP130155）を表示の枠（1920×1080、左右に黒帯）へ縮めたもの。描画は Unity の PC オフスクリーン描画（作品のまま）。")
    box = (250, 50, 1180, 620)
    cw = 632
    ch = int(round(cw * (box[3] - box[1]) / float(box[2] - box[0])))
    ref = os.path.join(a.look, "painting_display.png")
    tiles = [("原画（DP130155）", ref), ("前｜t*", os.path.join(a.before, "views", "painting_t120_asis.png")),
             ("後｜t*", os.path.join(a.after, "views", "painting_t120_asis.png")),
             ("前｜t 10.5 s", os.path.join(a.before, "views", "painting_t105_asis.png")),
             ("後｜t 10.5 s", os.path.join(a.after, "views", "painting_t105_asis.png")),
             ("後｜爪の帯の印 t*（赤＝藍の地、緑＝淡い水色の輪、青＝谷の底）", os.path.join(a.after, "fields", "painting_t120_m12.png"))]
    for i, (lab, p) in enumerate(tiles):
        x, y = 4 + (i % 3) * (cw + 4), 66 + (i // 3) * (ch + 4)
        if os.path.exists(p):
            src = Image.open(p)
            if "m12" in p:
                arr = np.asarray(src.convert("RGBA")).astype(np.int32)
                m = np.abs(arr[..., 3] - 128) < 3
                base = np.asarray(Image.open(os.path.join(a.after, "views", "painting_t120_clawfree.png")).convert("RGB")).astype(np.float32)
                col = base.copy()
                rgb = arr[..., :3].astype(np.float32)
                hit = m & (rgb.max(-1) > 127)
                col[hit] = 0.35 * base[hit] + 0.65 * rgb[hit]
                src = Image.fromarray(col.astype(np.uint8))
            im.paste(fit(src.convert("RGB").crop(box), (cw, ch)), (x, y))
        label(d, x + 4, y + 4, lab)
    foot(d, 66 + 2 * (ch + 4) + 6, (HEAD_A + "。",))
    p = os.path.join(out, "fig_pl36_painting_compare.png")
    im.save(p)
    return [p]


def zone_diag(a, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ36 爪の帯と谷の底の段の印（主役波だけ、_PL29Diag 12）｜赤＝爪の帯の藍の地　緑＝淡い水色の輪　青＝谷の底の段　灰＝ほかの主役波",
         "上の 2 段：t 10.5 s、下の 2 段：t*。どれも面の座標（F・c・ca）・今の高さ・T_white だけで決まる（原画カメラの投影なし）。Unity の PC オフスクリーン描画。")
    tw, th = 474, 230
    for r, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t*")]):
        for i, (v, name) in enumerate(VIEWS):
            k = r * 8 + i
            x, y = 4 + (k % 4) * (tw + 4), 66 + (k // 4) * (th + 4)
            p = os.path.join(a.after, "fields", "%s_%s_m12.png" % (v, ts))
            if os.path.exists(p):
                arr = np.asarray(Image.open(p).convert("RGBA")).astype(np.int32)
                m = np.abs(arr[..., 3] - 128) < 3
                img = np.full(arr.shape[:2] + (3,), 236, np.uint8)
                rgb = arr[..., :3]
                img[m] = (150, 150, 150)
                hit = m & (rgb.max(-1) > 127)
                img[hit] = rgb[hit].astype(np.uint8)
                im.paste(fit(Image.fromarray(img), (tw, th)), (x, y))
            label(d, x + 4, y + 4, "%s｜%s" % (name, tn))
    p = os.path.join(out, "fig_pl36_zone_diag.png")
    im.save(p)
    return [p]


def valley(a, out):
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ36 谷の底の段（Q16 の谷の色の側）｜左：前　右：後",
         "上：座席から波の方向 t*（作品のまま）。下：座席の低い視点 t*（t28 の組、主役波だけ・爪あり）。Unity の PC オフスクリーン描画。")
    rows = [(os.path.join("views", "seat_toward_wave_t120_asis.png"), (0, 300, 1920, 1080)),
            (os.path.join("t28_claws", "t28", "render", "af28r01_seat_low.png"), (0, 300, 1920, 1080))]
    tw = 950
    for r, (rel, box) in enumerate(rows):
        th = int(round(tw * (box[3] - box[1]) / float(box[2] - box[0])))
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            p = os.path.join(root, rel)
            x, y = 4 + si * (tw + 8), 66 + r * (th + 6)
            if os.path.exists(p):
                im.paste(fit(Image.open(p).convert("RGB").crop(box), (tw, th)), (x, y))
            label(d, x + 4, y + 4, lab)
    p = os.path.join(out, "fig_pl36_valley.png")
    im.save(p)
    return [p]


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        b = os.path.join(a.before, "video", "pl32_%s_30fps.mp4" % v)
        f = os.path.join(a.after, "video", "pl32_%s_30fps.mp4" % v)
        if not (os.path.exists(b) and os.path.exists(f)):
            continue
        p = os.path.join(out, "pl36_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ35':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 仕上げ36':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2")
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "27",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", p]
        subprocess.run(cmd, check=True)
        files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=REPO + "/Unity/Build/Polish/35/r_after")
    ap.add_argument("--after", default=REPO + "/Unity/Build/Polish/36/r_after")
    ap.add_argument("--look", default=REPO + "/Unity/Build/Polish/36/look")
    ap.add_argument("--out", required=True)
    ap.add_argument("--skip-video", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    fs = view_sheets(a, a.out) + turntable(a, a.out) + painting_compare(a, a.out) + zone_diag(a, a.out) + valley(a, a.out)
    if not a.skip_video:
        fs += videos(a, a.out)
    for f in fs:
        print(f, os.path.getsize(f))


if __name__ == "__main__":
    main()
