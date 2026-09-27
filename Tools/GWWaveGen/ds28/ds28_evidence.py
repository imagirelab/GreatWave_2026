# -*- coding: utf-8 -*-
"""設計28（美術の誘導の作り直し）：図と数値の証拠をまとめる。

入力（どれも読むだけ。Unity/Build/ は Git 対象外）：
  Unity/Build/Design/28/<版>/                 生成器のパッケージ（版 art_on・art_off）と ds28_generate_log.json・ds27_checks.json
  Unity/Build/Design/28/gates/<版>_<時間曲線>.json   ds28_gates.py の出力（P1〜P20）
  Unity/Build/Design/28/p20/ds28_p20.json      P20（美術の誘導の大きさ）
  Unity/Build/Design/27/art_on/                比べる設計27 の入れた版（パッケージ）
  Unity/Build/Design/28/<版>_<時間曲線>[_stages]/  Unity の描画（設計27 の DS27Formation を変えずに使う）
  Unity/Build/Design/26/paper/img_465〜468.jpg  論文 Fig. 4 a〜d（PDF から取り出した埋め込み JPEG。設計26 の run.json の SHA-256 を照合）
図の関数（下の 3 つの図を作る関数は ds28_record.py が import して、Docs/Evidence/Design/28/ へ書く）：
  fig_ds28_sections.png     主断面と峰の行の断面（噴流の始まりから t* まで 10 の τ）。設計28 の入れた版（太線）と設計27 の入れた版（細い破線）、灰は K*
  fig_ds28_water_wall.png   本体の水（本体の列の断面積）・内壁の 0.3H の点・唇先の、頂からの距離（波の枠）の時系列（設計27 と設計28、入れた版と切った版）
  fig_ds28_p15_fig4.png     段階 a〜d：断面・左の側面・原画視点（Unity）と論文 Fig. 4 a〜d（掲載の向き、CC BY の表示）
この main() の出力（Git 対象外の Unity/Build/Design/28/evidence_draft/。Docs/Evidence/Design/28/ には書かない）：
  上の図の草稿、2×2 の動画、ds28_art_guidance_metrics.json・ds28_art_guidance_run.json
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28/ds28_evidence.py
統合の後（ds28_record.py）：この main() は、美術の誘導の担当の草稿（2×2 の動画・ds28_art_guidance_metrics.json など）を Git 対象外の
Unity/Build/Design/28/evidence_draft/ へ書くだけにした。Docs/Evidence/Design/28/ の図・動画・metrics.json・run.json は ds28_record.py が
書き、ここの関数（断面の図・水と内壁の図・唇の弾道の当てはめなど）を import して使う。
利用者の高解像度の写真（webp）は読まない。
"""
import argparse
import datetime
import glob
import hashlib
import json
import math
import os
import platform
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
sys.path.insert(0, HERE)
sys.path.insert(0, DS27)
import ds27_gates as DG  # noqa: E402
import ds28_gates_extra as GX  # noqa: E402

REPO = DG.REPO
B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
B27 = os.path.join(REPO, "Unity", "Build", "Design", "27")
EVID = os.path.join(REPO, "Docs", "Evidence", "Design", "28")
DRAFT = os.path.join(B28, "evidence_draft")   # 統合の後：この main() の出力は草稿（Git 対象外）。証拠のフォルダーは ds28_record.py が書く
PAPER = os.path.join(REPO, "Unity", "Build", "Design", "26", "paper")
FONT = "C:/Windows/Fonts/YuGothM.ttc"
PAPER_SHA = {465: "cdb74dc99d8f29f0ca935d71db4ebdb191e848a65ffab6a9d03601cfbd9022c7", 466: "bbd72d8060763c6a64c87180a09bec9501ecf677e0074e57c8daf6db366b718c",
             467: "6adf0edd3be90bb30ea273dd5dc3424aaa55b73d7ef9e68339554ff1bb78b4b3", 468: "4eb20ece7a33129cbe2acea72fafd0f5745990b5f4c7d1efbf82a76afac0dd37"}
CREDIT = ["McAllister et al. 2019, J. Fluid Mech. 860, Fig. 4, photos D. Noble, CC BY 4.0 https://creativecommons.org/licenses/by/4.0/",
          "- cropped, mirrored to published orientation (PDF-embedded JPEG, obj 465-468)"]
STAGE_JA = {"a": "a 丸い峰", "b": "b 尖った塔", "c": "c 鉛直の壁・噴流の始まり", "d": "d 先が前へ返る"}
SIDE_CROP = (240, 260, 1680, 1070)
COL = {"main": (20, 40, 120), "peak": (230, 120, 0), "kstar": (185, 185, 185), "ds27": (120, 150, 200), "ds27p": (240, 190, 140)}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def font(sz):
    return ImageFont.truetype(FONT, sz)


_C = {}


def ks():
    if "ks" not in _C:
        _C["ks"] = DG.KStar()
    return _C["ks"]


def pkg(path):
    if path not in _C:
        _C[path] = DG.Package(path, ks())
    return _C[path]


def section_local(path, tau):
    """パッケージの波の枠（局所）の断面（行ごとの a、y）と、行ごとの頂の a・H・θc・Lo。"""
    K = ks()
    Xl = pkg(path).local(float(tau)) + K.O
    A, Y, _ = K.section(Xl)
    rm = DG.row_metrics(A, Y, K.crest_hi, K.j_E)
    return A, Y, rm


def draw_sec(img, box, tau, paths, xr=(-38.0, 26.0), yr=(-5.0, 33.0), label=True, fs=13):
    """box に主断面（紺）と峰の行（橙）を、それぞれの頂の a をそろえて等倍で描く。paths[0] は太線（設計28）、paths[1:] は細線（設計27）。"""
    K = ks()
    x0, y0, w, h = box
    d = ImageDraw.Draw(img)
    s = min(w / (xr[1] - xr[0]), h / (yr[1] - yr[0]))

    def P(a, y):
        return (x0 + (a - xr[0]) * s, y0 + h - (y - yr[0]) * s)
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=(200, 200, 200), fill=(250, 250, 250))
    for gx in range(int(math.ceil(xr[0] / 10.0)) * 10, int(xr[1]) + 1, 10):
        d.line([P(gx, yr[0]), P(gx, yr[1])], fill=(228, 228, 228))
    for gy in range(0, int(yr[1]) + 1, 10):
        d.line([P(xr[0], gy), P(xr[1], gy)], fill=(215, 215, 215) if gy else (150, 170, 200), width=1 if gy else 2)
    mr, pr = K.main_row, K.peak_row
    cj = int(np.argmax(np.where(np.arange(K.nu) <= K.crest_hi[pr], K.Y[pr], -np.inf)))
    d.line([P(a - K.A[pr, cj], y) for a, y in zip(K.A[pr], K.Y[pr]) if xr[0] - 5 < a - K.A[pr, cj] < xr[1] + 5], fill=COL["kstar"], width=1)
    info = None
    for k, path in enumerate(paths[::-1]):
        main = (k == len(paths) - 1)
        A, Y, rm = section_local(path, tau)
        for r, key in ((mr, "main"), (pr, "peak")):
            ca = rm["ca"][r]
            pts = [P(a - ca, y) for a, y in zip(A[r], Y[r]) if xr[0] - 5 < a - ca < xr[1] + 5]
            if main:
                d.line(pts, fill=COL[key], width=2)
            else:
                ck = COL["ds27" if key == "main" else "ds27p"]
                for i in range(0, len(pts) - 1, 2):
                    d.line(pts[i:i + 2], fill=ck, width=1)
        if main:
            info = rm
    if label:
        d.text((x0 + 5, y0 + 3), "τ %+.2f s　峰の行 H %.1f m・θc %.0f°・Lo %.2fH" % (tau, info["H"][pr], info["theta"][pr], info["Lo"][pr] / max(info["H"][pr], 1e-6)),
               fill=(40, 40, 40), font=font(fs))
    return info


SECTION_TAUS = (-2.7, -2.4, -2.2, -2.0, -1.8, -1.5, -1.2, -0.8, -0.4, 0.0)


def sections_figure(out, p28, p27, note=""):
    W, H, cols = 380, 250, 5
    nrow = int(math.ceil(len(SECTION_TAUS) / cols))
    img = Image.new("RGB", (cols * W + 20, 50 + nrow * (H + 12) + 76), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 8), "設計28 入れた版（太線：紺＝主断面 行 159、橙＝峰の行 行 192）と設計27 の入れた版（細い破線：同じ色の淡い色）。灰＝t* の K*（行 192）。各行の頂の a をそろえ、縦横等倍、格子 10 m",
           fill=(0, 0, 0), font=font(16))
    for i, tv in enumerate(SECTION_TAUS):
        x0 = 10 + (i % cols) * W
        y0 = 40 + (i // cols) * (H + 12)
        draw_sec(img, (x0, y0, W - 8, H), tv, [p28, p27] if p27 else [p28])
    yb = 40 + nrow * (H + 12) + 4
    d.text((10, yb), "パッケージ（量子化した keypose）を ds27_gates.py と同じ Hermite で読んだ numpy の図（Unity の描画ではない）。τ は物理の時刻（t* = 0）。",
           fill=(60, 60, 60), font=font(14))
    if note:
        d.text((10, yb + 22), note, fill=(120, 30, 30), font=font(14))
    img.save(out, optimize=True)


def plot_series(img, box, xs, series, yr, title, ylab, xr=(-4.0, 0.0), marks=()):
    x0, y0, w, h = box
    d = ImageDraw.Draw(img)
    pl, pb = 52, 26
    X0, Y0, Wd, Hd = x0 + pl, y0 + 22, w - pl - 10, h - 22 - pb

    def P(x, y):
        return (X0 + (x - xr[0]) / (xr[1] - xr[0]) * Wd, Y0 + Hd - (y - yr[0]) / (yr[1] - yr[0]) * Hd)
    d.text((x0 + 4, y0 + 2), title, fill=(0, 0, 0), font=font(14))
    d.rectangle([X0, Y0, X0 + Wd, Y0 + Hd], outline=(170, 170, 170))
    for t in np.arange(xr[0], xr[1] + 1e-9, 0.5):
        d.line([P(t, yr[0]), P(t, yr[1])], fill=(235, 235, 235))
        d.text((P(t, yr[0])[0] - 12, Y0 + Hd + 4), "%.1f" % t, fill=(80, 80, 80), font=font(11))
    step = (yr[1] - yr[0]) / 4
    for k in range(5):
        v = yr[0] + k * step
        d.line([P(xr[0], v), P(xr[1], v)], fill=(235, 235, 235))
        d.text((x0 + 4, P(xr[0], v)[1] - 7), "%.0f" % v if abs(step) >= 1 else "%.1f" % v, fill=(80, 80, 80), font=font(11))
    d.text((x0 + 4, Y0 + Hd + 4), ylab, fill=(80, 80, 80), font=font(11))
    for tm, lab in marks:
        d.line([P(tm, yr[0]), P(tm, yr[1])], fill=(200, 60, 60), width=1)
        d.text((P(tm, yr[1])[0] + 2, Y0 + 2), lab, fill=(200, 60, 60), font=font(11))
    for name, ys, col, wid in series:
        pts = [P(x, y) for x, y in zip(xs, ys) if np.isfinite(y) and xr[0] <= x <= xr[1] and yr[0] <= y <= yr[1]]
        if len(pts) > 1:
            d.line(pts, fill=col, width=wid)
    ly = Y0 + 4
    for name, ys, col, wid in series:
        d.line([(X0 + Wd - 190, ly + 7), (X0 + Wd - 170, ly + 7)], fill=col, width=wid)
        d.text((X0 + Wd - 165, ly), name, fill=(40, 40, 40), font=font(11))
        ly += 15


def water_wall_figure(out, S28, S27, S28off, onset):
    K = ks()
    img = Image.new("RGB", (1500, 900), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 6), "本体の水と内壁・唇先（波の枠、頂からの距離）。赤い縦線＝噴流の始まり（ds26_conditions の行の唇先の放出）と前面が鉛直になった時刻（φ ≥ 90°）",
           fill=(0, 0, 0), font=font(16))
    for i, (r, nm) in enumerate(((K.main_row, "主断面 行 159"), (K.peak_row, "峰の行 行 192"))):
        x0 = 10 + i * 745
        t = S28["taus"]
        mk = [(onset[r]["cal"], "始まり"), (onset[r]["meas"], "鉛直")]
        ser = [("設計28 入れた版", S28["A"][:, r] / S28["A"][-1, r], COL["main"], 2)]
        if S27 is not None:
            ser.append(("設計27 入れた版", np.interp(t, S27["taus"], S27["A"][:, r]) / S27["A"][-1, r], (140, 140, 140), 1))
        if S28off is not None:
            ser.append(("設計28 切った版", np.interp(t, S28off["taus"], S28off["A"][:, r]) / S28off["A"][-1, r], (60, 160, 60), 1))
        plot_series(img, (x0, 30, 735, 280), t, ser, (0.5, 1.5), nm + "：本体の断面積（列 j_B〜j_E）/ その版の t* の値", "比", marks=mk)
        for j, (key, lab) in enumerate((("w3", "内壁の 0.3H の点"), ("tip", "唇先（K* の唇先の列）"))):
            ser = [("設計28 入れた版", S28[key][:, r] - S28["crest"][:, r], COL["main"], 2)]
            if S27 is not None:
                ser.append(("設計27 入れた版", np.interp(t, S27["taus"], S27[key][:, r] - S27["crest"][:, r]), (140, 140, 140), 1))
            if S28off is not None:
                ser.append(("設計28 切った版", np.interp(t, S28off["taus"], S28off[key][:, r] - S28off["crest"][:, r]), (60, 160, 60), 1))
            yr = (-3.0, 16.0) if key == "w3" else (-1.0, 14.0)
            plot_series(img, (x0, 320 + j * 285, 735, 275), t, ser, yr, nm + "：" + lab + " − 頂の a（波の枠）", "m", marks=mk)
    img.save(out, optimize=True)


def still(run_dir, view, name):
    f = glob.glob(os.path.join(run_dir, "stills", "ds27_%s_%s_tau*.png" % (view, name)))
    return f[0] if f else None


def load_view(p, size):
    im = Image.open(p).convert("RGB")
    if "_side_left_" in os.path.basename(p) and im.size == (1920, 1080):
        im = im.crop(SIDE_CROP)
    return im.resize(size, Image.LANCZOS)


def tau_of(p):
    b = os.path.basename(p)
    return float(b.split("_tau")[1][:-4]) if "_tau" in b else float("nan")


def p15_figure(out, p28, run_dir, taus):
    for n, h in PAPER_SHA.items():
        if sha(os.path.join(PAPER, "img_%d.jpg" % n)) != h:
            raise SystemExit("論文の図の JPEG の SHA-256 が設計26 の記録と違う")
    pan = [Image.open(os.path.join(PAPER, "img_%d.jpg" % n)).convert("RGB").transpose(Image.FLIP_LEFT_RIGHT) for n in (465, 466, 467, 468)]
    pw, ph = pan[0].size
    pan = [p.resize((480, int(round(ph * 480.0 / pw))), Image.LANCZOS) for p in pan]
    ph2 = pan[0].size[1]
    W, H = 480, 270
    lab_w = 230
    rows = [("我々の波：断面\n（設計28 入れた版。\n紺＝主断面、橙＝峰の行、\n灰＝t* の K*）", "section", H),
            ("我々の波：左の側面\n（Unity、波の枠と\nともに動く）", "side_left", H),
            ("我々の波：原画視点\n（Unity、PaintingCam v1）", "painting", H), ("論文 Fig. 4 a〜d\n（120°、掲載の向き）", None, ph2)]
    img = Image.new("RGB", (lab_w + 4 * W, 40 + sum(h + 30 for _, _, h in rows) + 120), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, s in enumerate("abcd"):
        d.text((lab_w + k * W + 6, 8), STAGE_JA[s], fill=(0, 0, 0), font=font(22))
    y = 40
    for title, view, h in rows:
        d.text((6, y + 6), title, fill=(0, 0, 0), font=font(16))
        for k, s in enumerate("abcd"):
            if view is None:
                img.paste(pan[k], (lab_w + k * W, y))
                d.text((lab_w + k * W + 6, y + h + 4), "(%s)" % s, fill=(0, 0, 0), font=font(18))
            elif view == "section":
                tv = taus[s]
                draw_sec(img, (lab_w + k * W + 2, y, W - 4, h), tv, [p28], xr=(-30.0, 24.0), yr=(-3.0, 30.0))
                d.text((lab_w + k * W + 6, y + h + 4), "τ = %+.3f s（峰の行の %s）" % (tv, s), fill=(0, 0, 0), font=font(15))
            else:
                p = still(run_dir, view, s) if run_dir else None
                if p:
                    img.paste(load_view(p, (W, H)), (lab_w + k * W, y))
                    d.text((lab_w + k * W + 6, y + h + 4), "τ = %+.3f s" % tau_of(p), fill=(0, 0, 0), font=font(15))
                else:
                    d.text((lab_w + k * W + 20, y + h // 2), "（Unity の描画なし）", fill=(150, 150, 150), font=font(15))
        y += h + 30
    for i, t in enumerate(CREDIT):
        d.text((6, y + 4 + 22 * i), t, fill=(0, 0, 0), font=font(15))
    d.text((6, y + 4 + 22 * len(CREDIT)), "上の 3 段は我々の波（設計28 入れた版・既定の時間曲線）。段階の τ は、関門の検査器 ds27_gates.py が峰で最も高い巻きの行（c = +3.85 m）で各段階の判定を初めて満たした時刻。",
           fill=(60, 60, 60), font=font(14))
    img.save(out, optimize=True)


FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT_FF = "C\\:/Windows/Fonts/YuGothM.ttc"
CMP = [("設計28 入れた版・既定", os.path.join(B28, "art_on_default")), ("設計27 入れた版・既定（比べる）", os.path.join(B27, "art_on_default")),
       ("設計28 入れた版・代案（瞬間の停止）", os.path.join(B28, "art_on_alt")), ("設計28 切った版・既定", os.path.join(B28, "art_off_default"))]


def compare_video(view, out):
    """4 本を 2×2 に並べる（1280×720、30 fps、421 コマ）。ffmpeg はリポジトリの根で、相対パスで呼ぶ。"""
    import subprocess
    ins = []
    for lab, d in CMP:
        p = os.path.join(d, "video", "ds27_%s_30fps.mp4" % view)
        if not os.path.isfile(p):
            raise SystemExit("動画がない：%s" % p)
        ins.append(p)
    fc = []
    for i, (lab, _) in enumerate(CMP):
        fc.append("[%d:v]scale=640:360:flags=lanczos,drawbox=x=0:y=0:w=640:h=30:color=black@0.55:t=fill,"
                  "drawtext=fontfile='%s':text='%s':x=8:y=5:fontsize=18:fontcolor=white[v%d]" % (i, FONT_FF, lab, i))
    fc.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[out]")
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for p in ins:
        cmd += ["-i", rel(p)]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
            "-r", "30", "-frames:v", "421", "-movflags", "+faststart", rel(out)]
    subprocess.run(cmd, check=True, cwd=REPO)
    return [rel(p) for p in ins]


WHITE_TAUS = (-2.6, -2.4, -2.25, -2.1, -1.9)
WHITE_CROP = (0, 150, 260, 560)     # 原画視点の 1920×1080 の左端（波が画面に入り始める所）


def white_figure(out):
    """原画視点の左端を拡大し、段階 c〜d の唇先の白（ds_tip_white_line）を設計27 と比べる。動画の連番（既定の時間曲線）から τ に一番近いコマ。"""
    rows = [("設計28 入れた版", os.path.join(B28, "art_on_default")), ("設計27 入れた版", os.path.join(B27, "art_on_default"))]
    rows = [r for r in rows if os.path.isdir(os.path.join(r[1], "frames", "painting"))]
    cw, ch = WHITE_CROP[2] - WHITE_CROP[0], WHITE_CROP[3] - WHITE_CROP[1]
    lab = 170
    img = Image.new("RGB", (lab + cw * len(WHITE_TAUS), 40 + (ch + 26) * len(rows) + 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 8), "原画視点（Unity、PaintingCam v1）の左端を拡大：段階 c（表 −2.4 s）〜d の唇先の白。動画の連番から τ に一番近いコマ", fill=(0, 0, 0), font=font(16))
    used = []
    for i, (nm, rd) in enumerate(rows):
        y = 36 + i * (ch + 26)
        d.text((6, y + 10), nm, fill=(0, 0, 0), font=font(15))
        T = np.array(jload(os.path.join(rd, "video", "ds27_frames_tau.json"))["tau"], float)
        for k, tv in enumerate(WHITE_TAUS):
            j = int(np.argmin(np.abs(T - tv)))
            pth = os.path.join(rd, "frames", "painting", "f_%04d.png" % j)
            im = Image.open(pth).convert("RGB").crop(WHITE_CROP).resize((cw, ch), Image.LANCZOS)
            img.paste(im, (lab + k * cw, y))
            d.text((lab + k * cw + 4, y + ch + 3), "τ %+.3f s（コマ %d）" % (T[j], j), fill=(0, 0, 0), font=font(13))
            used.append(rel(pth))
    d.text((6, img.size[1] - 30), "座席 v1 は t ≈ 10 s まで波が画面に入らず、座席の仰角 30°（seat_form）は手前の仮置き（設計39・40 まで）が波の下半分を隠すので、座席の視点では段階 c の白を示せない。",
           fill=(120, 30, 30), font=font(13))
    img.save(out, optimize=True)
    return used


REV_TAUS = (-3.4, -2.9, -2.4, -2.0, -1.4, -0.8, 0.0)


def revisions_figure(out, revs):
    """修正ごとの断面（numpy、パッケージを Hermite で読む）。revs = [(名前, パッケージのフォルダー)]。"""
    W, H = 300, 210
    lab = 150
    img = Image.new("RGB", (lab + W * len(REV_TAUS), 40 + (H + 24) * len(revs) + 30), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((6, 8), "修正ごとの断面（紺＝主断面、橙＝峰の行、灰＝t* の K*）。上の τ は物理の時刻", fill=(0, 0, 0), font=font(16))
    for i, (nm, path) in enumerate(revs):
        y = 34 + i * (H + 24)
        d.text((6, y + 8), nm, fill=(0, 0, 0), font=font(15))
        for k, tv in enumerate(REV_TAUS):
            draw_sec(img, (lab + k * W, y, W - 6, H), tv, [path], xr=(-28.0, 20.0), yr=(-3.0, 28.0), fs=11)
    d.text((6, img.size[1] - 24), "初回（r00）は Unity で描いていない（numpy の断面だけ）。提出版は Unity の描画も fig_ds28_p15_fig4.png と動画にある。", fill=(60, 60, 60), font=font(13))
    img.save(out, optimize=True)


def lips_ballistic(p28):
    """引き継ぎ 3 の確かめ：唇の点を、打ち出しの補間の後（放出 + 補間の長さ + 0.02 s）から t* まで 240 Hz でパッケージから読み、
    2 次式の当てはめの加速度（地面、縦 ay・進行方向 a_h）を測る。唇先と上面の s 0.25・0.5。行は生成器の唇の行すべて（κ < 1 の行を含む）。"""
    import ds28_model as M8
    K = ks()
    pk = pkg(p28)
    g = M8.Generator("art_on")
    rows_out = {}
    fits = []
    for r in sorted(g.lip.keys()):
        L = g.lip[r]
        upm = L["upm"]
        s_ = L["s"]
        iu = np.nonzero(upm)[0]
        picks = [("tip", int(iu[np.argmin(s_[iu])]))] + [("s%.2f" % v, int(iu[np.argmin(np.abs(s_[iu] - v))])) for v in (0.25, 0.5)]
        ent = []
        for nm, i in picks:
            Tc = float(L["Tc"][i])
            Tr = float(np.atleast_1d(L["Tr"])[i]) if np.ndim(L["Tr"]) else float(L["Tr"])
            t0 = -Tc + Tr + 0.02
            if -t0 < 0.25:
                continue
            tq = np.linspace(t0, 0.0, int(round(-t0 * 240)) + 1)
            W = pk.sub(tq, np.array([r * K.nu + int(L["cols"][i])]), 0)[:, 0, :]
            ay = float(2.0 * np.polyfit(tq, W[:, 1], 2)[0])
            ah = float(2.0 * np.polyfit(tq, (W - K.O) @ K.t, 2)[0])
            ent.append(dict(point=nm, window_s=round(-t0, 3), ay=round(ay, 3), a_h=round(ah, 3)))
            fits.append((r, nm, ay, ah, float(g.kappa[r])))
        rows_out[int(r)] = dict(c_m=round(float(K.c[r]), 2), kappa=round(float(g.kappa[r]), 3), mode=L.get("mode"), points=ent)
    fa = np.array([(f_[2], f_[3]) for f_ in fits])
    ok = (np.abs(fa[:, 0] + 9.81) <= 0.5) & (np.abs(fa[:, 1]) <= 0.5)
    beyond = [f_ for f_ in fits if K.c[f_[0]] > K.c[K.peak_row]]
    tip_b = [f_[2] for f_ in beyond if f_[1] == "tip"]
    return dict(ja="唇の点の打ち出しの補間の後から t* までの 2 次式の当てはめの加速度（地面、m/s²）。重力だけなら ay = −9.81、a_h = 0。当てはめの窓が 0.25 s 未満の点は除く",
                points=int(len(fits)), within_0p5=int(ok.sum()),
                exceptions=[dict(row=int(f_[0]), point=f_[1], ay=round(f_[2], 2), a_h=round(f_[3], 2), kappa=round(f_[4], 3)) for f_, o in zip(fits, ok) if not o],
                rows_beyond_peak=dict(rows=sorted(set(int(f_[0]) for f_ in beyond)), tip_ay_range=[round(min(tip_b), 2), round(max(tip_b), 2)] if tip_b else None,
                                      ja="峰の行の外側（c > 3.85 m、κ < 1 の行 193〜214 のうち窓が 0.25 s 以上のもの）"),
                per_row_every_6={str(k): v for k, v in list(rows_out.items())[::6]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-unity", action="store_true")
    a = ap.parse_args()
    os.makedirs(DRAFT, exist_ok=True)
    K = ks()
    p28 = os.path.join(B28, "art_on")
    p28off = os.path.join(B28, "art_off")
    p27 = os.path.join(B27, "art_on")
    have27 = os.path.isfile(os.path.join(p27, "ds27_keypose.json"))
    cond, _ = DG.load_conditions()
    Tc = GX.calib_onset(K, cond)
    S28 = GX.series(K, pkg(p28), t_start=-4.0, log=lambda *x: None)
    S27 = GX.series(K, pkg(p27), t_start=-4.0, log=lambda *x: None) if have27 else None
    S28off = GX.series(K, pkg(p28off), t_start=-4.0, log=lambda *x: None) if os.path.isdir(p28off) else None
    onset = {}
    for r in (K.main_row, K.peak_row):
        kk = np.nonzero(np.nan_to_num(S28["phi"][:, r], nan=0.0) >= 90)[0]
        onset[r] = dict(cal=-float(Tc[r]), meas=float(S28["taus"][kk[0]]) if len(kk) else None)
    outs = {}
    p = os.path.join(DRAFT, "fig_ds28_sections.png")
    sections_figure(p, p28, p27 if have27 else None)
    outs["fig_ds28_sections.png"] = p
    p = os.path.join(DRAFT, "fig_ds28_water_wall.png")
    water_wall_figure(p, S28, S27, S28off, onset)
    outs["fig_ds28_water_wall.png"] = p
    revs = [("初回（r00）", os.path.join(B28, "r00", "art_on")), ("修正1（r01）", p28)]
    if os.path.isdir(os.path.join(B28, "r01", "art_on")):
        revs = [("初回（r00）", os.path.join(B28, "r00", "art_on")), ("修正1（r01）", os.path.join(B28, "r01", "art_on")), ("修正2（r02）", p28)]
    revs = [x for x in revs if os.path.isfile(os.path.join(x[1], "ds27_keypose.json"))]
    p = os.path.join(DRAFT, "fig_ds28_revisions.png")
    revisions_figure(p, revs)
    outs["fig_ds28_revisions.png"] = p
    g = jload(os.path.join(B28, "gates", "art_on_default.json"))
    st = g["gates"]["P15"]["detail"]["峰で最も高い巻きの行"]["tau"]
    run_dir = None if a.no_unity else os.path.join(B28, "art_on_default_stages")
    p = os.path.join(DRAFT, "fig_ds28_p15_fig4.png")
    p15_figure(p, p28, run_dir if run_dir and os.path.isdir(run_dir) else None, {k: float(st[k]) for k in "abcd"})
    outs["fig_ds28_p15_fig4.png"] = p
    if not a.no_unity:
        p = os.path.join(DRAFT, "fig_ds28_white_c.png")
        white_figure(p)
        outs["fig_ds28_white_c.png"] = p
    videos = {}
    if not a.no_unity:
        for view in ("painting", "seat_form", "side_left"):
            p = os.path.join(DRAFT, "ds28_compare_%s.mp4" % view)
            try:
                videos[os.path.basename(p)] = dict(inputs=compare_video(view, p))
                outs[os.path.basename(p)] = p
            except SystemExit as e:
                print("動画を作れない：", e)
    # 数値
    series_out = {}
    for nm, S in (("ds28_art_on", S28), ("ds27_art_on", S27), ("ds28_art_off", S28off)):
        if S is None:
            continue
        series_out[nm] = {"taus": [round(float(t), 3) for t in S["taus"][::6]]}
        for r in (K.main_row, K.peak_row):
            for key in ("A", "w3", "w5", "tip"):
                v = S[key][::6, r] - (S["crest"][::6, r] if key != "A" else 0.0)
                series_out[nm]["%s_%d" % (key, r)] = [None if not np.isfinite(x) else round(float(x), 3) for x in v]
    rec = dict(schema="GreatWave.DS28.art_guidance_metrics/1", number="設計28",
               ja="設計28 の美術の誘導の作り直し（引き継ぎ 1〜3）の数値。関門は Unity/Build/Design/28/gates/ の ds28_gates.py の出力の写し。系列は波の枠で頂からの距離（A は本体の断面積 m²）",
               onset=onset, series_every_0p1s=series_out, figures={k: dict(path=rel(v), sha256=sha(v)) for k, v in outs.items()}, videos=videos,
               generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"))
    for nm in ("art_on_default", "art_on_alt", "art_off_default", "art_off_alt"):
        gp = os.path.join(B28, "gates", nm + ".json")
        if os.path.isfile(gp):
            G = jload(gp)
            rec.setdefault("gates", {})[nm] = dict(source=dict(path=rel(gp), sha256=sha(gp)),
                                                   P={k: dict(value=v["value"], threshold=v["threshold"], pass_=v["pass"]) for k, v in list(G["gates"].items()) + list(G["gates_ds28"].items())},
                                                   failed=G["summary_all"]["failed"], p20=G.get("p20"))
    # t* の測り直し・再生の照合・決定性・keypose（記録）
    t_rem = os.path.join(B28, "art_on_default", "ds27_tstar_remeasure.json")
    pchk = os.path.join(B28, "art_on_default", "ds27_playback_check.json")
    if os.path.isfile(t_rem):
        T = jload(t_rem)
        rec["tstar_remeasure"] = {k: T[k] for k in ("worst_abs_diff_px", "criterion_px", "pass", "summary_verdicts_ds27", "summary_verdicts_28r01", "pixel_diff_vs_af30_t28") if k in T}
        rec["tstar_remeasure"]["source"] = dict(path=rel(t_rem), sha256=sha(t_rem))
    if os.path.isfile(pchk):
        C = jload(pchk)
        rec["playback_check"] = {k: C[k] for k in C if not isinstance(C[k], (list, dict)) and k != "capture_report"}
        rec["playback_check"]["source"] = dict(path=rel(pchk), sha256=sha(pchk))
    det = {}
    for v in ("art_on", "art_off"):
        for fn in ("ds27_pos_rgba16.bin", "ds27_twhite_r32f.bin", "ds27_keypose.json"):
            a1, a2 = os.path.join(B28, v, fn), os.path.join(B28, "_twice", v, fn)
            if os.path.isfile(a1) and os.path.isfile(a2):
                h1, h2 = sha(a1), sha(a2)
                det["%s/%s" % (v, fn)] = dict(sha256=h1, same_bytes=(h1 == h2))
    rec["determinism"] = dict(ja="同じ入力から Unity/Build/Design/28/_twice/ へ作り直した 3 ファイル × 2 版の SHA-256", files=det)
    kp = {}
    for v in ("art_on", "art_off"):
        K_ = jload(os.path.join(B28, v, "ds27_keypose.json"))
        ch = jload(os.path.join(B28, v, "ds27_checks.json"))
        gl = jload(os.path.join(B28, v, "ds28_generate_log.json"))
        kp[v] = dict(layers=K_["layers"], pos_mib=round(K_["pos_bytes"] / 2 ** 20, 2), gpu_positions_6B_per_vertex_mib=round(K_["layers"] * 96000 * 6 / 2 ** 20, 2),
                     quantization_max_err_m=K_["quantization_max_err_m"], hermite_playback_err_m=ch["hermite_playback_err_m"]["max"],
                     tstar_vs_kstar_world_max_m=ch["tstar_vs_kstar_world_max_m"], generate_seconds=gl["result"]["seconds"], summary=K_["generator"]["summary"],
                     pos_sha256=K_["pos_sha256"], twhite_sha256=K_["twhite_sha256"], code_sha256=gl["code_sha256"], command=gl["command"])
    rec["keypose"] = kp
    rec["lip_ballistic"] = lips_ballistic(p28)
    x27 = os.path.join(B28, "gates", "ds27_art_on_default_extra.json")
    if os.path.isfile(x27):
        X = jload(x27)["gates"]
        rec["ds27_art_on_same_measures"] = dict(
            ja="比べる：設計27 の入れた版（Unity/Build/Design/27/art_on）を同じ検査器 ds28_gates_extra.py で測った P17〜P19（コマンドは run の欄）",
            source=dict(path=rel(x27), sha256=sha(x27)),
            P={k: dict(value=v["value"], pass_=v["pass"]) for k, v in X.items()},
            P18_worst=X["P18"]["detail"]["worst"], P18_rows_over=len(X["P18"]["detail"]["rows_over"]))
    p20p = os.path.join(B28, "p20", "ds28_p20.json")
    if os.path.isfile(p20p):
        rec["p20_source"] = dict(path=rel(p20p), sha256=sha(p20p))
    with open(os.path.join(DRAFT, "ds28_art_guidance_metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print("DONE", ", ".join(outs))


if __name__ == "__main__":
    main()
