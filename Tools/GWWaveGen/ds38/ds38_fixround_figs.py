# -*- coding: utf-8 -*-
"""設計38 修正の回（進行役の検査の後の 1 回、Q26）の図（1920×1080。文字は英数字だけ）。

  fig_ds38_fixround_before_after.png  修正1（左）と修正の回（右）：原画視点の動画のコマ 296（t 9.87 s）の右の高い波、座席のコマ 226（t 7.53 s）の稜線、
                                       頭の揺れ（座席から波の方向 t 9 s）の線の ID のコマ 33・34（主役波の唇の内側の細い線の出入り）
  fig_ds38_fixround_limits.png        残る限界：原画視点 t 9.87 s の右の高い波の 2 つの尖り（near の行 25〜27・列 556〜601 の扇）、
                                       座席 t 7.53 s の稜線の段の小さな鉤、座席から波の方向のコマ 420 の暗い海を横切る継ぎ目の線（設計36・修正1・修正の回）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds38/ds38_fixround_figs.py
"""
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds38_line_eval as le  # noqa: E402

ROOT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design"
O = ROOT + "/38/outlines"
NEW, OLD = O + "/unity", O + "/unity_fix1"
D36V = ROOT + "/36/palette/unity/video/ds36_palette_seat_toward_wave_30fps.mp4"
FF = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
W, H = 1920, 1080


def frame(mp4, n):
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "f.png")
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", mp4, "-vf", "select=eq(n\\,%d)" % n, "-vframes", "1", p], check=True)
        return cv2.imread(p)


def label(im, text, org=(8, 26), scale=0.75):
    cv2.putText(im, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 4, cv2.LINE_AA)
    cv2.putText(im, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 20), 2, cv2.LINE_AA)
    return im


def ids(path, q, box, fx):
    fr = le.read_frames(path)[q]
    m = np.zeros((H * W, 3), np.uint8)
    for k, c in {1: (60, 60, 255), 2: (0, 200, 0), 4: (255, 150, 0)}.items():
        m[fr["idx"][fr["sheet"] == k]] = c
    x0, y0, x1, y1 = box
    return cv2.resize(m.reshape(H, W, 3)[y0:y1, x0:x1], None, fx=fx, fy=fx, interpolation=cv2.INTER_NEAREST)


def fit(im, w, h):
    s = min(w / im.shape[1], h / im.shape[0])
    r = cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_NEAREST)
    c = np.full((h, w, 3), 245, np.uint8)
    c[:r.shape[0], :r.shape[1]] = r
    return c


def main():
    vp = "/video/ds38_formation_painting_30fps.mp4"
    vs = "/video/ds38_formation_seat_30fps.mp4"
    vw = "/video/ds38_formation_seat_toward_wave_30fps.mp4"
    cv_ = np.full((H, W, 3), 245, np.uint8)
    bx_p, bx_s = (1100, 250, 1920, 760), (1100, 600, 1920, 1080)
    for col, (d, tag) in enumerate(((OLD, "fix1 (delivered before)"), (NEW, "fix round (adopted)"))):
        a = frame(d + vp, 296)[bx_p[1]:bx_p[3], bx_p[0]:bx_p[2]]
        b = frame(d + vs, 226)[bx_s[1]:bx_s[3], bx_s[0]:bx_s[2]]
        cv_[0:430, col * 960:col * 960 + 955] = label(fit(a, 955, 430), tag + "  painting frame 296 (t 9.87 s)")
        cv_[435:750, col * 960:col * 960 + 955] = label(fit(b, 955, 315), "seat frame 226 (t 7.53 s)")
        sw = d + "/l191/l191_sway_seat_toward_wave_t09.bin"
        tiles = [label(ids(sw, q, (756, 246, 876, 326), 2), "sway %d" % q, scale=0.5) for q in (32, 33, 34, 56, 57)]
        cv_[755:1080, col * 960:col * 960 + 955] = fit(np.hstack(tiles), 955, 325)
    os.makedirs(O + "/fig", exist_ok=True)
    cv2.imwrite(O + "/fig/fig_ds38_fixround_before_after.png", cv_)

    lim = np.full((H, W, 3), 245, np.uint8)
    a = frame(NEW + vp, 296)[250:420, 1500:1920]
    lim[0:360, 0:955] = label(fit(a, 955, 360), "limit: 2 peak tips of right high wave (near rows 25-27), painting t 9.87 s")
    b = frame(NEW + vs, 226)[800:1080, 1100:1560]
    lim[0:360, 965:1920] = label(fit(b, 955, 360), "limit: small hooks at ridge steps (S5-3), seat t 7.53 s")
    for k, (p, tag) in enumerate(((D36V, "DS36"), (OLD + vw, "fix1"), (NEW + vw, "fix round"))):
        f = frame(p, 420)
        lim[370:1080, k * 640:k * 640 + 635] = label(fit(f[300:1080, 0:1100], 635, 710), tag + " seat_toward_wave frame 420 (seam line)", scale=0.55)
    cv2.imwrite(O + "/fig/fig_ds38_fixround_limits.png", lim)
    print("ok")


if __name__ == "__main__":
    main()
