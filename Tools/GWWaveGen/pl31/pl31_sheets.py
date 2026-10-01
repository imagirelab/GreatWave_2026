# -*- coding: utf-8 -*-
"""仕上げ31 の前後の図（1920×1080）と前後を並べた動画。

前＝コミットした仕上げ30（b9140db）の状態（PL31Render -pl31Old 1：主役波の T_white は G_p28rec のまま、飛沫は設計31 の 186 粒）、
後＝仕上げ31 修正01（T_white に pl31_white_order（patch）・pl31_white_claw_pin・pl31_white_rate_cap、飛沫は親 210・子（原画の点の中と白の上）、限定色 2 段）。
どれも Unity 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。この道具は既にある画像を並べるだけ（新しい描画はしない）。

  fig_pl31_ba_view_<視点>.png         7 視点 × t 6・9・10.5・12 s（上：前、次：後）と、t* の飛沫の所の前後の拡大
  fig_pl31_ba_turntable_t<時刻>.png   回り台 12 方位（爪・飛沫あり）の前後
  pl31_ba_<視点>_30fps.mp4           前｜後 を左右に並べた動画（t 0〜14 s、30 fps）
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_sheets.py --before Unity/Build/Polish/31/r_before --after Unity/Build/Polish/31/r_after --out Docs/Evidence/Polish/31
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
# 拡大の所（t 10.5 s と t* の飛沫と白の所）
ZOOM = {"painting": (200, 40, 1160, 680), "seat": (500, 0, 1700, 675), "seat_toward_wave": (360, 0, 1560, 675),
        "side_left": (560, 200, 1360, 650), "side_right": (500, 200, 1420, 717), "back65": (480, 160, 1440, 700), "top": (560, 200, 1360, 650)}
HEAD_B = "前＝コミットした仕上げ30（b9140db）の状態（T_white は G_p28rec のまま、飛沫は設計31 の 186 粒で F_final の唇から出る）"
def _head_a():
    import json as _j
    try:
        g = _j.load(open("G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31/spray/pl31_spray_generate_log.json", encoding="utf-8"))["summary"]
        n = "飛沫 {:,} 粒：原画の点 {}・子 {:,}".format(g["total"], g["parents"], g["children"])
    except Exception:
        n = "飛沫"
    return ("後＝仕上げ31 修正01（T_white を頂の最も高い所から面の上の距離の順に・爪の根元は伸び始めまでに白く・1 コマ 2% 以下、"
            + n + "（子は原画の点の中と白の上に狙って置く）、放出点は Hash1 によらない白の範囲、限定色 2 段）")


HEAD_A = _head_a()


def wrap(d, text, width, f):
    """text を幅 width（画素）で折り返した行の並び（日本語は文字ごとに折る）。"""
    lines, cur = [], ""
    for ch in text:
        if d.textlength(cur + ch, font=f) > width and cur:
            lines.append(cur); cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def view_sheets(a, out):
    # 記録の部（2026-10-02）：見出しの 2 行目は 1 行に収まらず右端で切れていた（「飛沫 2,500 粒：原画の点 210」の後）。
    # 見出しは短くし、前・後の説明は図の下の欄に折り返して書く。拡大の段は切り抜きの縦横の比の高さで上に詰めて置く（見出しの札と画像の間の空きをなくす）。
    files = []
    for v, name in VIEWS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ31 視点ごとの前後｜%s｜上の段：前　次の段：後（同じ視点・同じ時刻・作品のまま：爪・飛沫・線あり）" % name,
             "前＝コミットした仕上げ30（b9140db）、後＝仕上げ31 修正01。下の段は t 10.5 s と t* の拡大。前・後の中身は図の下の欄。Unity の PC オフスクリーン描画（HMD ではない）。")
        tw, th = 474, 267
        for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
            for k, (ts, tn) in enumerate(TS):
                x, y = 4 + k * (tw + 4), 66 + si * (th + 3)
                t = tile(os.path.join(root, "views", "%s_%s_asis.png" % (v, ts)), (tw, th))
                if t is not None:
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s" % (lab, tn))
        crop = ZOOM.get(v)
        bw, bh = 474, 0
        # 下の段：t 10.5 s と t* の拡大（前・後）
        cw = 474
        ch = int(round(cw * (crop[3] - crop[1]) / float(crop[2] - crop[0])))
        ch = min(ch, 470)
        for k, (ts, tn) in enumerate([("t105", "t 10.5 s"), ("t120", "t 12 s（t*）")]):
            for si, (lab, root) in enumerate([("前", a.before), ("後", a.after)]):
                x, y = 4 + (2 * k + si) * (cw + 4), 610
                p = os.path.join(root, "views", "%s_%s_asis.png" % (v, ts))
                if os.path.exists(p):
                    t = fit(Image.open(p).convert("RGB").crop(crop), (cw, ch))
                    im.paste(t, (x, y))
                label(d, x + 4, y + 4, "%s｜%s 拡大" % (lab, tn))
        f = font(15)
        y = 610 + ch + 10
        for para in (HEAD_B + "。", HEAD_A + "。"):
            for ln in wrap(d, para, 1890, f):
                d.text((14, y), ln, fill=(40, 48, 64), font=f)
                y += 22
        p = os.path.join(out, "fig_pl31_ba_view_%s.png" % v)
        im.save(p); files.append(p)
    return files


def turntable(a, out):
    files = []
    for ts, tn in TS:
        im = Image.new("RGB", (1920, 1080), (238, 238, 238))
        d = ImageDraw.Draw(im)
        head(d, "仕上げ31 回り台｜%s｜方位ごとに上：前　下：後（爪・飛沫・線あり、周りの海を含む）" % tn,
             "回り台：中心 O(t)+(0,9,0)、半径 72 m、仰角 16°、縦の画角 34°、原画視点の向きから 30° ごと（仕上げ29・30 と同じ置き方）。Unity の PC 描画。")
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
        p = os.path.join(out, "fig_pl31_ba_turntable_%s.png" % ts)
        im.save(p); files.append(p)
    return files


def videos(a, out):
    files = []
    for v in ("painting", "seat", "seat_toward_wave", "side_left", "tt"):
        b = os.path.join(a.before, "video", "pl31_%s_30fps.mp4" % v)
        f = os.path.join(a.after, "video", "pl31_%s_30fps.mp4" % v)
        if not (os.path.exists(b) and os.path.exists(f)):
            continue
        p = os.path.join(out, "pl31_ba_%s_30fps.mp4" % v)
        vf = ("[0:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='前 仕上げ30':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[l];"
              "[1:v]drawtext=fontfile='C\\:/Windows/Fonts/NotoSansJP-Bold.ttf':text='後 仕上げ31 修正01':x=8:y=8:fontsize=22:fontcolor=white:box=1:boxcolor=black@0.6[r];[l][r]hstack=inputs=2")
        cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", b, "-i", f, "-filter_complex", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "26",
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
