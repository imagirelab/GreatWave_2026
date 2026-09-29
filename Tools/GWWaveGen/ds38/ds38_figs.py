# -*- coding: utf-8 -*-
"""設計38 第「輪郭線」部：証拠の図（1920×1080）。ds38_line_eval.py の後に回す。

  fig_ds38_before_after.png   設計36（左）と設計38（右）：原画視点 t*・座席 t*・座席から波の方向 t 10.5 s（Mock の左目）の色の画像
  fig_ds38_claws_seat.png     座席 t* の波頭の拡大（設計36 と設計38。爪の縁の線と、爪が重なる所の手前の線）
  fig_ds38_painting_mask.png  原画視点 t* の線の ID（設計36 と設計38。原画にない面の中の線を原画視点では描かない）
  fig_ds38_191.png            191 の各組の線の画素の数と、点滅・跳びの塊の数（設計37 の定義の数も）
  fig_ds38_mock.png           Mock の両眼（座席から波の方向 t 10.5 s・座席 t 12 s）と線の画素の数
  fig_ds38_near.png           近くの線の太さ（4・8・16 m、設計27 の決まりと DS38）
  fig_ds38_seam.png           座席から波の方向 t 11・11.9 s の継ぎ目の近く（設計36 と設計38）
文字は英数字だけ（OpenCV の字）。説明は記録（Design_38_ja.md）に書く。
"""
import argparse
import json
import os

import cv2
import numpy as np

W, H = 1920, 1080
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
D36 = os.path.join(REPO, "Unity", "Build", "Design", "36", "palette", "unity")
FF = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"


def imread(p):
    return cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_COLOR)


def imwrite(p, im):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cv2.imencode(".png", im)[1].tofile(p)


def label(im, text, org=(10, 30), scale=0.9):
    cv2.putText(im, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 4, cv2.LINE_AA)
    cv2.putText(im, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (20, 20, 20), 2, cv2.LINE_AA)
    return im


def canvas():
    return np.full((H, W, 3), 245, np.uint8)


def frame_from_video(mp4, t, tmp):
    import subprocess
    subprocess.run([FF, "-y", "-loglevel", "error", "-ss", "%.3f" % t, "-i", mp4, "-frames:v", "1", tmp], check=True)
    return imread(tmp)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--unity", required=True)       # 連続・Mock・近く・動画のある出力
    ap.add_argument("--t28", required=True)         # t28 の組のある出力
    ap.add_argument("--fig", required=True)
    a = ap.parse_args()
    ud, td, fd = a.unity, a.t28, a.fig
    os.makedirs(fd, exist_ok=True)
    met = json.load(open(os.path.join(os.path.dirname(ud), "ds38_outlines_metrics.json"), encoding="utf-8"))
    tmp = os.path.join(fd, "_tmp.png")

    # 前後
    c = canvas()
    rows = [("painting t12 (t*)", imread(os.path.join(D36, "t28_claws", "t28", "render", "af28r01_painting.png")), imread(os.path.join(td, "t28_claws", "t28", "render", "af28r01_painting.png"))),
            ("seat t12 (t*)", imread(os.path.join(D36, "t28_claws", "t28", "render", "af28r01_seat.png")), imread(os.path.join(td, "t28_claws", "t28", "render", "af28r01_seat.png")))]
    v36 = os.path.join(D36, "video", "ds36_palette_seat_toward_wave_30fps.mp4")
    v38 = os.path.join(ud, "video", "ds38_formation_seat_toward_wave_30fps.mp4")
    if os.path.exists(v36) and os.path.exists(v38):
        rows.append(("seat_toward_wave t10.5", frame_from_video(v36, 10.5, tmp), frame_from_video(v38, 10.5, tmp)))
    hh = H // len(rows)
    ww = int(hh * 16 / 9)
    for i, (n, x36, x38) in enumerate(rows):
        c[i * hh:i * hh + hh, 0:ww] = cv2.resize(x36, (ww, hh), interpolation=cv2.INTER_AREA)
        c[i * hh:i * hh + hh, W - ww:W] = cv2.resize(x38, (ww, hh), interpolation=cv2.INTER_AREA)
        label(c, "DS36 " + n, (10, i * hh + 30), 0.8)
        label(c, "DS38 " + n, (W - ww + 10, i * hh + 30), 0.8)
    imwrite(os.path.join(fd, "fig_ds38_before_after.png"), c)

    # 爪（座席 t* の波頭）
    s36 = imread(os.path.join(D36, "t28_claws", "t28", "render", "af28r01_seat.png"))
    s38 = imread(os.path.join(td, "t28_claws", "t28", "render", "af28r01_seat.png"))
    y0, y1, x0, x1 = 420, 780, 560, 1200
    c = canvas()
    a36 = cv2.resize(s36[y0:y1, x0:x1], (960, 540), interpolation=cv2.INTER_NEAREST)
    a38 = cv2.resize(s38[y0:y1, x0:x1], (960, 540), interpolation=cv2.INTER_NEAREST)
    c[270:810, 0:960] = a36
    c[270:810, 960:1920] = a38
    label(c, "DS36 seat t* crest (x560-1200, y420-780) x1.5", (10, 260), 0.8)
    label(c, "DS38 claw edge lines + near-side lines", (970, 260), 0.8)
    imwrite(os.path.join(fd, "fig_ds38_claws_seat.png"), c)

    # 原画視点の線の ID（2 倍の画像を縮める）
    l36 = imread(os.path.join(D36, "t28_claws", "t28", "render", "af28r01_line_ids.png"))
    l38 = imread(os.path.join(td, "t28_claws", "t28", "render", "af28r01_line_ids.png"))
    c = canvas()
    for i, (n, im) in enumerate((("DS36 painting t* line ids (magenta = line)", l36), ("DS38 (interior lines masked in painting view)", l38))):
        m = (im[:, :, 2] >= 250) & (im[:, :, 1] <= 5) & (im[:, :, 0] >= 250)
        base = cv2.resize(imread(os.path.join(td if i else D36, "t28_claws", "t28", "render", "af28r01_painting_kstar.png")), (im.shape[1], im.shape[0]))
        base = (0.45 * base + 0.55 * 255).astype(np.uint8)
        base[m] = (140, 0, 200)
        c[270:810, i * 960:(i + 1) * 960] = cv2.resize(base, (960, 540), interpolation=cv2.INTER_AREA)
        label(c, n, (i * 960 + 10, 260), 0.75)
    imwrite(os.path.join(fd, "fig_ds38_painting_mask.png"), c)

    # 191
    c = canvas()
    seqs = met["191"]["sequences"]
    names = list(seqs.keys())
    ph = (H - 60) // max(1, len(names))
    for i, n in enumerate(names):
        s = seqs[n]
        y0 = 40 + i * ph
        lp = np.asarray(s["line_px"], np.float64)
        x = np.linspace(80, W - 40, len(lp))
        top, bot = y0 + 10, y0 + ph - 30
        cv2.rectangle(c, (80, top), (W - 40, bot), (200, 200, 200), 1)
        mx = max(1.0, lp.max())
        pts = np.stack([x, bot - (bot - top) * lp / mx], 1).astype(np.int32)
        cv2.polylines(c, [pts], False, (160, 90, 30), 2, cv2.LINE_AA)
        for k, col in (("hole_ds37", (0, 140, 255)), ("hole", (0, 0, 220)), ("flash", (200, 0, 200)), ("jump", (0, 160, 0))):
            for q, v in enumerate(s[k]):
                if v > 0:
                    cv2.line(c, (int(x[q]), bot), (int(x[q]), bot - min(bot - top, 6 * v)), col, 2)
        label(c, "%s  line px (blue, max %d)  flash %d  hole %d  jump %d  | DS37-def hole (orange) %d" % (n, mx, s["flash_clusters"], s["hole_clusters"], s["jump_clusters"], s["hole_ds37_clusters"]), (90, y0 + 5), 0.6)
    label(c, "191: 301 consecutive frames per row (30 fps). Bars: clusters >= 10 px per frame.", (10, H - 12), 0.6)
    imwrite(os.path.join(fd, "fig_ds38_191.png"), c)

    # Mock
    c = canvas()
    mk = met.get("mock", {}).get("pairs", [])
    sel = [("seat_toward_wave", 10.5), ("seat", 12.0)]
    for i, (v, t) in enumerate(sel):
        for j, e in enumerate(("L", "R")):
            p = os.path.join(ud, "mock", "colour_%s_t%04.1fs_%s.png" % (v, t, e))
            if not os.path.exists(p):
                continue
            im = cv2.resize(imread(p), (960, 540), interpolation=cv2.INTER_AREA)
            c[i * 540:(i + 1) * 540, j * 960:(j + 1) * 960] = im
            pr = [x for x in mk if x["view"] == v and abs(x["t"] - t) < 1e-3]
            n = pr[0]["%s_px" % e] if pr else -1
            rd = pr[0]["rel_diff"] if pr else float("nan")
            label(c, "Mock %s eye  %s t%.1f  line px %d  |L-R|/mean %.3f" % (e, v, t, n, rd), (j * 960 + 10, i * 540 + 30), 0.7)
    imwrite(os.path.join(fd, "fig_ds38_mock.png"), c)

    # Mock の左右差が 10% を超えた組（座席の低い視点 t 6 s）
    c = canvas()
    for j, e in enumerate(("L", "R")):
        p = os.path.join(ud, "mock", "colour_seat_low_t06.0s_%s.png" % e)
        if os.path.exists(p):
            im = imread(p)
            c[0:540, j * 960:(j + 1) * 960] = cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA)
            c[540:1080, j * 960:(j + 1) * 960] = cv2.resize(im[540:1080, 960:1920], (960, 540), interpolation=cv2.INTER_NEAREST)
            pr = [x for x in mk if x["view"] == "seat_low" and abs(x["t"] - 6.0) < 1e-3]
            n = pr[0]["%s_px" % e] if pr else -1
            rd = pr[0]["rel_diff"] if pr else float("nan")
            label(c, "Mock %s  seat_low t6.0  line px %d  |L-R|/mean %.3f" % (e, n, rd), (j * 960 + 10, 30), 0.7)
            label(c, "x2 crop (x960-1920, y540-1080)", (j * 960 + 10, 570), 0.7)
    imwrite(os.path.join(fd, "fig_ds38_mock_limit_seat_low_t06.png"), c)

    # 191 の限界：near の右の高い波の稜線の階段から出る棘の線（座席 t 7.67 s・座席から波の方向 t 7.5 s）
    vs = os.path.join(ud, "video", "ds38_formation_seat_30fps.mp4")
    if os.path.exists(vs) and os.path.exists(v38):
        c = canvas()
        a1 = frame_from_video(vs, 7.667, tmp)[780:1080, 1200:1920]
        a2 = frame_from_video(v38, 7.5, tmp)[0:300, 1250:1920]
        c[40:40 + 450, 0:1080] = cv2.resize(a1, (1080, 450), interpolation=cv2.INTER_NEAREST)
        c[540:540 + 450, 0:1005] = cv2.resize(a2, (1005, 450), interpolation=cv2.INTER_NEAREST)
        label(c, "seat t7.67 (x1200-1920, y780-1080) x1.5: near-sheet spike lines at the stair-stepped ridge", (10, 30), 0.7)
        label(c, "seat_toward_wave t7.5 (x1250-1920, y0-300) x1.5", (10, 530), 0.7)
        imwrite(os.path.join(fd, "fig_ds38_191_limit_spikes.png"), c)

    # 近く
    c = canvas()
    nr = met.get("near", {}).get("probes", [])
    for j, dist in enumerate((4, 8, 16)):
        for i, law in enumerate(("ds27_v0", "ds38")):
            p = os.path.join(ud, "near", "colour_%s_%02dm.png" % (law, dist))
            if not os.path.exists(p):
                continue
            im = imread(p)
            cut = cv2.resize(im[270:810, 480:1440], (640, 360), interpolation=cv2.INTER_AREA)
            c[60 + i * 480:60 + i * 480 + 360, j * 640:(j + 1) * 640] = cut
            pr = [x for x in nr if x["law"] == law and abs(x["dist_m"] - dist) < 1e-3]
            th = pr[0] if pr else {}
            label(c, "%s %dm  p95 %.1f px  max %.1f px" % (law, dist, th.get("p95") or 0, th.get("max") or 0), (j * 640 + 10, 50 + i * 480), 0.65)
    label(c, "near-line width: seat fov 80 deg, camera moved to 4/8/16 m from the nearest hero point (centre crop 960x540 -> 640x360)", (10, H - 12), 0.6)
    imwrite(os.path.join(fd, "fig_ds38_near.png"), c)

    # 継ぎ目
    v36 = os.path.join(D36, "video", "ds36_palette_seat_toward_wave_30fps.mp4")
    if os.path.exists(v36) and os.path.exists(v38):
        c = canvas()
        for i, t in enumerate((11.0, 11.9)):
            for j, (n, v) in enumerate((("DS36", v36), ("DS38", v38))):
                im = frame_from_video(v, t, tmp)
                c[i * 540:(i + 1) * 540, j * 960:(j + 1) * 960] = cv2.resize(im, (960, 540), interpolation=cv2.INTER_AREA)
                label(c, "%s seat_toward_wave t%.1f" % (n, t), (j * 960 + 10, i * 540 + 30), 0.8)
        imwrite(os.path.join(fd, "fig_ds38_seam.png"), c)
    if os.path.exists(tmp):
        os.remove(tmp)


if __name__ == "__main__":
    main()
