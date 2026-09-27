# -*- coding: utf-8 -*-
"""設計27：証拠（Docs/Evidence/Design/27/）をまとめる。

入力（どれも読むだけ。Unity/Build/ は Git 対象外）：
  Unity/Build/Design/27/<版>/ds27_keypose.json               生成器のパッケージ（版 art_on・art_off）
  Unity/Build/Design/27/ds27_generate_log_<版>.json          生成の記録（時間・節点）
  Unity/Build/Design/27/gates/<版>_<時間曲線>.json           関門の検査器 ds27_gates.py の出力
  Unity/Build/Design/27/<版>_<時間曲線>/                     Unity の描画（DS27Formation）：stills/・video/・frames/・
                                                             ds27_render_report.json・ds27_tstar_remeasure.json・ds27_playback_check.json・t28/render/
  Unity/Build/Design/26/paper/img_465〜468.jpg               論文 Fig. 4 a〜d（PDF から取り出した埋め込み JPEG。設計26 の run.json の SHA-256 を照合）
  Unity/Build/ArtFirst/28修正01/render/・ArtFirst/30/t28/render/  t* の画像の比較先
出力（Docs/Evidence/Design/27/）：
  fig_ds27_stages_painting.png・fig_ds27_stages_seat.png・fig_ds27_stages_side.png   段階の並べ図（入れた版・切った版）
  fig_ds27_p15_fig4.png        我々の波（左の側面・原画視点・主断面と峰の行の断面）の a〜d と論文 Fig. 4 a〜d（掲載の向き、CC BY の表示）
  fig_ds27_sections.png        主断面と峰の行の断面を、噴流の始まりから t* まで 10 の τ で並べた図（パッケージを Hermite で読む）
  fig_ds27_stages_seat_form.png  座席から仰角 30° の視点（seat_form）の動画の連番から、段階の τ に一番近いコマ
  fig_ds27_revisions.png       修正ごとの静止画（初回・修正1・修正2）
  ds27_compare_painting.mp4・ds27_compare_seat.mp4・ds27_compare_side_left.mp4
                               3 本（入れた版の既定・入れた版の代案・切った版の既定）を 2×2 に並べた 1280×720 の動画
  metrics.json・run.json
レビュー対応で足した入力：Unity/Build/Design/27/review/ds27_review_measure.json（ds27_review_measure.py）、
  Unity/Build/Design/27/_twice/（決定性の確認）、Unity/Build/Design/27/r00/gates/（初回の関門の出力）、
  Unity/Build/Design/27/gates_af30/ds27_gates_af30.json（美術優先30 を同じ検査器で測った値。バックログの対応表に使う）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds27/ds27_evidence.py [--skip-video]
  [--records-only 版_時間曲線:関門,...] [--not-judgeable 版_時間曲線:関門,...] [--revisions Unity/Build/Design/27/ds27_revisions.json]
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
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B27 = os.path.join(REPO, "Unity", "Build", "Design", "27")
EVID = os.path.join(REPO, "Docs", "Evidence", "Design", "27")
PAPER = os.path.join(REPO, "Unity", "Build", "Design", "26", "paper")
R28 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "28修正01", "render")
R30 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30", "t28", "render")
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONT_FF = "C\\:/Windows/Fonts/YuGothM.ttc"
PAPER_SHA = {   # 設計26 の run.json（Docs/Evidence/Design/26/run.json）の値
    465: "cdb74dc99d8f29f0ca935d71db4ebdb191e848a65ffab6a9d03601cfbd9022c7",
    466: "bbd72d8060763c6a64c87180a09bec9501ecf677e0074e57c8daf6db366b718c",
    467: "6adf0edd3be90bb30ea273dd5dc3424aaa55b73d7ef9e68339554ff1bb78b4b3",
    468: "4eb20ece7a33129cbe2acea72fafd0f5745990b5f4c7d1efbf82a76afac0dd37",
}
CREDIT = ["McAllister et al. 2019, J. Fluid Mech. 860, Fig. 4, photos D. Noble, CC BY 4.0 https://creativecommons.org/licenses/by/4.0/",
          "- cropped, mirrored to published orientation (PDF-embedded JPEG, obj 465-468)"]
RUNS = [("art_on", "default"), ("art_on", "alt"), ("art_off", "default")]
LABEL = {("art_on", "default"): "入れた版・既定の時間曲線（D31 の (a)）", ("art_on", "alt"): "入れた版・代案（実時間＋t* で瞬間に停止）",
         ("art_off", "default"): "切った版（美術の誘導なし）・既定の時間曲線"}
STAGES = ["a", "b", "c", "d", "apex", "tstar"]
STAGE_JA = {"a": "a 丸い峰", "b": "b 尖った塔", "c": "c 鉛直の壁・噴流の始まり", "d": "d 先が前へ返る", "apex": "唇先の頂点", "tstar": "t*（原画）"}


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


def still(run_dir, view, name):
    f = glob.glob(os.path.join(run_dir, "stills", "ds27_%s_%s_tau*.png" % (view, name)))
    return f[0] if f else None


SIDE_CROP = (240, 260, 1680, 1070)   # 左の側面は波が画面の中ほどにあるので、16:9 のまま切り出す（1920×1080 から）


def load_view(p, size):
    im = Image.open(p).convert("RGB")
    if "_side_left_" in os.path.basename(p) and im.size == (1920, 1080):
        im = im.crop(SIDE_CROP)
    return im.resize(size, Image.LANCZOS)


def tau_of(path):
    b = os.path.basename(path)
    if "_tau" in b:
        return float(b.split("_tau")[1][:-4])
    return FRAME_TAU.get(os.path.abspath(path), float("nan"))


FRAME_TAU = {}


def frame_at(run_dir, view, tau):
    """動画の連番（frames/<視点>/f_NNNN.png）から、物理の時刻 τ に一番近いコマ。seat_form のように静止画のない視点に使う。"""
    ft = os.path.join(run_dir, "video", "ds27_frames_tau.json")
    fd = os.path.join(run_dir, "frames", view)
    if not (os.path.isfile(ft) and os.path.isdir(fd)):
        return None
    T = jload(ft)
    tt = np.array(T["tau"], float)
    k = int(np.argmin(np.abs(tt - tau)))
    p = os.path.join(fd, "f_%04d.png" % k)
    if not os.path.isfile(p):
        return None
    FRAME_TAU[os.path.abspath(p)] = float(tt[k])
    return p


def STAGE_RUN(ver, warp):
    """段階の τ（関門の検査器で測った時刻）で描いた静止画のフォルダー（<版>_<時間曲線>_stages）。無ければ本体の描画。"""
    p = os.path.join(B27, "%s_%s_stages" % (ver, warp))
    return p if os.path.isdir(os.path.join(p, "stills")) else os.path.join(B27, "%s_%s" % (ver, warp))


def stage_sheet(view, out, runs, cell=(480, 270), taus=None):
    W, H = cell
    lab_w, head_h = 250, 34
    img = Image.new("RGB", (lab_w + W * len(STAGES), head_h + (H + 30) * len(runs) + 40), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, s in enumerate(STAGES):
        d.text((lab_w + k * W + 6, 6), STAGE_JA[s], fill=(0, 0, 0), font=font(20))
    used = []
    for i, (ver, warp) in enumerate(runs):
        rd = STAGE_RUN(ver, warp) if view != "seat_form" else os.path.join(B27, "%s_%s" % (ver, warp))
        y = head_h + i * (H + 30)
        d.text((6, y + 8), LABEL[(ver, warp)].replace("・", "\n"), fill=(0, 0, 0), font=font(18))
        for k, s in enumerate(STAGES):
            if view == "seat_form":
                p = frame_at(rd, view, taus[s][0]) if taus and taus.get(s) and taus[s][0] is not None else None
            else:
                p = still(rd, view, s)
            if not p:
                continue
            used.append(p)
            img.paste(load_view(p, (W, H)), (lab_w + k * W, y))
            d.text((lab_w + k * W + 6, y + H + 4), "τ = %+.3f s" % tau_of(p), fill=(0, 0, 0), font=font(18))
    d.text((6, img.size[1] - 32), "Unity 6000.4.3f1 の PC オフスクリーン描画（DS27Formation）。τ は物理の時刻（t* = 0）。段階の τ は関門の検査器の峰で最も高い巻きの行（c = +3.85 m）の値（入れた版）。HMD 実機ではない。",
           fill=(60, 60, 60), font=font(16))
    img.save(out, optimize=True)
    return used


_SEC = {}


def section_rows(tau, ver="art_on"):
    """パッケージ（ds27_gates の読み方と同じ Hermite）から、主断面（行 159）と峰の行（行 192）の断面（地面の a、y）と頂の a。"""
    import ds27_gates as DG
    if "ks" not in _SEC:
        _SEC["ks"] = DG.KStar()
    ks = _SEC["ks"]
    if ver not in _SEC:
        _SEC[ver] = DG.Package(os.path.join(B27, ver), ks)
    pk = _SEC[ver]
    A, Y, _ = ks.section(pk.world(float(tau)))
    rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
    out = {}
    for r in (ks.main_row, ks.peak_row):
        out[int(r)] = dict(a=A[r], y=Y[r], ca=float(rm["ca"][r]), H=float(rm["H"][r]), theta=float(rm["theta"][r]), Lo=float(rm["Lo"][r]))
    kd = {}
    for r in (ks.main_row, ks.peak_row):
        cj = int(np.argmax(np.where(np.arange(ks.nu) <= ks.crest_hi[r], ks.Y[r], -np.inf)))
        kd[int(r)] = dict(a=ks.A[r], y=ks.Y[r], ca=float(ks.A[r, cj]))
    return out, kd, int(ks.main_row), int(ks.peak_row)


SEC_COL = {"main": (20, 40, 120), "peak": (230, 120, 0), "kstar": (185, 185, 185)}


def draw_profile(img, box, tau, xr=(-40.0, 28.0), yr=(-5.0, 33.0), label=True, fs=14):
    """box = (x0, y0, w, h) に、主断面（紺）と峰の行（橙）の断面を、それぞれの頂の a をそろえて等倍で描く。灰は t* の K*（峰の行）。"""
    x0, y0, w, h = box
    d = ImageDraw.Draw(img)
    sx = w / (xr[1] - xr[0])
    sy = h / (yr[1] - yr[0])
    s = min(sx, sy)

    def P(a, y):
        return (x0 + (a - xr[0]) * s, y0 + h - (y - yr[0]) * s)
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=(200, 200, 200), fill=(250, 250, 250))
    for gx in range(int(math.ceil(xr[0] / 10.0)) * 10, int(xr[1]) + 1, 10):
        d.line([P(gx, yr[0]), P(gx, yr[1])], fill=(228, 228, 228))
    for gy in range(0, int(yr[1]) + 1, 10):
        d.line([P(xr[0], gy), P(xr[1], gy)], fill=(215, 215, 215) if gy else (150, 170, 200), width=1 if gy else 2)
    rows, kd, mr, pr = section_rows(tau)
    ka = kd[pr]
    d.line([P(a - ka["ca"], y) for a, y in zip(ka["a"], ka["y"]) if xr[0] - 5 < a - ka["ca"] < xr[1] + 5], fill=SEC_COL["kstar"], width=1)
    for r, key in ((mr, "main"), (pr, "peak")):
        q = rows[r]
        pts = [P(a - q["ca"], y) for a, y in zip(q["a"], q["y"]) if xr[0] - 5 < a - q["ca"] < xr[1] + 5]
        d.line(pts, fill=SEC_COL[key], width=2)
    if label:
        q = rows[pr]
        d.text((x0 + 6, y0 + 4), "τ %+.2f s　峰の行 H %.1f m・θc %.0f°・Lo %.2fH" % (tau, q["H"], q["theta"], q["Lo"] / max(q["H"], 1e-6)),
               fill=(40, 40, 40), font=font(fs))
    return rows


def p15_figure(out, run_on, taus, profile_note=""):
    for n, h in PAPER_SHA.items():
        p = os.path.join(PAPER, "img_%d.jpg" % n)
        if sha(p) != h:
            raise SystemExit("論文の図の JPEG の SHA-256 が設計26 の記録と違う：%s" % p)
    pan = [Image.open(os.path.join(PAPER, "img_%d.jpg" % n)).convert("RGB").transpose(Image.FLIP_LEFT_RIGHT) for n in (465, 466, 467, 468)]
    pw, ph = pan[0].size
    sc = 480.0 / pw
    pan = [p.resize((480, int(round(ph * sc))), Image.LANCZOS) for p in pan]
    ph2 = pan[0].size[1]
    W, H = 480, 270
    lab_w = 230
    rows = [("我々の波：断面\n（紺＝主断面 行 159、\n橙＝峰の行 行 192、\n灰＝t* の K*（行 192）。\n頂の a をそろえ等倍、\n格子 10 m）", "section", H),
            ("我々の波：左の側面\n（波の枠とともに動く。\n後ろ斜めから見るので\n唇は向こう側で見えない）", "side_left", H),
            ("我々の波：原画視点\n（PaintingCam v1。a・b\nの波はまだ画面の外、\nc・d は左端に入り始め）", "painting", H), ("論文 Fig. 4 a〜d\n（120°、掲載の向き）", None, ph2)]
    tot_h = 40 + sum(h + 30 for _, _, h in rows) + 150
    img = Image.new("RGB", (lab_w + 4 * W, tot_h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, s in enumerate("abcd"):
        d.text((lab_w + k * W + 6, 8), STAGE_JA[s], fill=(0, 0, 0), font=font(22))
    y = 40
    used = []
    for title, view, h in rows:
        d.text((6, y + 6), title, fill=(0, 0, 0), font=font(17))
        for k, s in enumerate("abcd"):
            if view is None:
                img.paste(pan[k], (lab_w + k * W, y))
                d.text((lab_w + k * W + 6, y + h + 4), "(%s)" % s, fill=(0, 0, 0), font=font(18))
            elif view == "section":
                tv = taus[s][0]
                draw_profile(img, (lab_w + k * W + 2, y, W - 4, h), tv)
                d.text((lab_w + k * W + 6, y + h + 4), "τ = %+.3f s（%s）" % (tv, taus.get(s, ("", ""))[1]), fill=(0, 0, 0), font=font(16))
            else:
                p = still(run_on, view, s)
                if p:
                    used.append(p)
                    img.paste(load_view(p, (W, H)), (lab_w + k * W, y))
                    d.text((lab_w + k * W + 6, y + h + 4), "τ = %+.3f s（%s）" % (tau_of(p), taus.get(s, ("", ""))[1]), fill=(0, 0, 0), font=font(16))
        y += h + 30
    for i, t in enumerate(CREDIT):
        d.text((6, y + 4 + 22 * i), t, fill=(0, 0, 0), font=font(16))
    d.text((6, y + 4 + 22 * len(CREDIT)), "上の 3 段は我々の波（入れた版・既定。断面はパッケージを Hermite で読んだ numpy の図、側面と原画視点は Unity の描画）。段階の τ は、関門の検査器が峰で最も高い巻きの行で各段階の判定を初めて満たした時刻。形成の順と見た目の手本は利用者の写真と同じ場面の Fig. 4（D30）。",
           fill=(60, 60, 60), font=font(15))
    if profile_note:
        d.text((6, y + 4 + 22 * (len(CREDIT) + 1)), profile_note, fill=(120, 30, 30), font=font(15))
    img.save(out, optimize=True)
    return used


SECTION_TAUS = (-2.5, -2.2, -1.967, -1.8, -1.6, -1.4, -1.2, -0.8, -0.4, 0.0)


def sections_figure(out, note=""):
    """主断面と峰の行の断面を、噴流の始まり（峰の行 −2.5 s）から t* まで 10 の τ で並べる（入れた版）。"""
    W, H, cols = 380, 250, 5
    nrow = int(math.ceil(len(SECTION_TAUS) / cols))
    img = Image.new("RGB", (cols * W + 20, 50 + nrow * (H + 12) + 70), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "設計27 入れた版：断面（紺＝主断面 行 159、橙＝峰の行 行 192、灰＝t* の K* の行 192。各行の頂の a をそろえ、縦横等倍、格子 10 m、青い線 = 静水面）",
           fill=(0, 0, 0), font=font(17))
    for i, tv in enumerate(SECTION_TAUS):
        x0 = 10 + (i % cols) * W
        y0 = 45 + (i // cols) * (H + 12)
        draw_profile(img, (x0, y0, W - 8, H), tv, xr=(-38.0, 26.0), yr=(-5.0, 33.0), fs=13)
    yb = 45 + nrow * (H + 12) + 4
    d.text((10, yb), "τ −2.5 s は峰の行の段階 c、−1.967 s は段階 d（関門の検査器の判定を初めて満たした時刻）。パッケージ（量子化した keypose）を ds27_gates.py と同じ Hermite で読んだ numpy の図。Unity の描画ではない。",
           fill=(60, 60, 60), font=font(14))
    if note:
        d.text((10, yb + 22), note, fill=(120, 30, 30), font=font(14))
    img.save(out, optimize=True)


def revisions_figure(out):
    """修正ごとの静止画（入れた版・既定、左の側面と原画視点、設計26 §3.1 の峰の行の表の τ）。初回と修正1 は
    Unity/Build/Design/27/r00・r01/ に残した描画、修正2（提出版）は Unity/Build/Design/27/art_on_default/。"""
    rows = [("初回", os.path.join(B27, "r00", "art_on_default")), ("修正1", os.path.join(B27, "r01", "art_on_default")),
            ("修正2（提出）", os.path.join(B27, "art_on_default"))]
    cols = [("side_left", "a"), ("side_left", "b"), ("side_left", "c"), ("side_left", "d"), ("painting", "apex"), ("side_left", "tstar")]
    W, H = 400, 225
    lab_w = 150
    img = Image.new("RGB", (lab_w + W * len(cols), 36 + (H + 26) * len(rows) + 30), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for k, (v, s_) in enumerate(cols):
        d.text((lab_w + k * W + 6, 8), "%s（%s）" % (STAGE_JA[s_], "側面" if v == "side_left" else "原画視点"), fill=(0, 0, 0), font=font(17))
    used = []
    for i, (name, rd) in enumerate(rows):
        y = 36 + i * (H + 26)
        d.text((6, y + 8), name, fill=(0, 0, 0), font=font(20))
        for k, (v, s_) in enumerate(cols):
            p = still(rd, v, s_)
            if not p:
                continue
            used.append(p)
            img.paste(load_view(p, (W, H)), (lab_w + k * W, y))
            d.text((lab_w + k * W + 6, y + H + 3), "τ = %+.3f s" % tau_of(p), fill=(0, 0, 0), font=font(15))
    d.text((6, img.size[1] - 26), "入れた版・既定の時間曲線。τ は設計26 §3.1 の峰で最も高い巻きの行の表の時刻（修正の前後を同じ τ で比べる）。Unity の PC 描画。",
           fill=(60, 60, 60), font=font(15))
    img.save(out, optimize=True)
    return used


def compare_video(view, out):
    """3 本を 2×2 に並べる。ffmpeg はリポジトリの根で、入出力をリポジトリからの相対パスで渡す（run.json に絶対パスを残さない）。"""
    ins = []
    for ver, warp in RUNS:
        p = os.path.join(B27, "%s_%s" % (ver, warp), "video", "ds27_%s_30fps.mp4" % view)
        if not os.path.isfile(p):
            raise SystemExit("動画がない：%s" % p)
        ins.append(p)
    lab = [LABEL[r] for r in RUNS]
    fc = []
    for i in range(3):
        fc.append("[%d:v]scale=640:360:flags=lanczos,drawbox=x=0:y=0:w=640:h=30:color=black@0.55:t=fill,"
                  "drawtext=fontfile='%s':text='%s':x=8:y=5:fontsize=18:fontcolor=white[v%d]" % (i, FONT_FF, lab[i].replace(":", "\\:"), i))
    vname = {"painting": "原画視点（PaintingCam v1）", "seat": "座席 v1（seat_v1.json）", "side_left": "左の側面（波の枠とともに動く）"}[view]
    extra = ""
    if view == "seat":
        # レビュー対応：切った版の座席の暗転（シートの前の端が目の上を通る。設計30 の海の継ぎ目）
        extra = (",drawtext=fontfile='%s':text='切った版（左下）は t 9.9〜10.1 s に、シートの前の端（静水面の':x=20:y=292:fontsize=15:fontcolor=0x803020"
                 ",drawtext=fontfile='%s':text='上 2.5〜2.7 m）が目（1.83 m）の上を通り、画面が暗い青になる（設計30）':x=20:y=314:fontsize=15:fontcolor=0x803020"
                 % (FONT_FF, FONT_FF))
    fc.append("color=c=white:s=640x360:r=30:d=14.1,drawtext=fontfile='%s':text='設計27 %s':x=20:y=30:fontsize=24:fontcolor=black,"
              "drawtext=fontfile='%s':text='体験の時刻 t = %%{pts\\:flt} s（t* = 12 s、12〜14 s は保持）':x=20:y=80:fontsize=20:fontcolor=black,"
              "drawtext=fontfile='%s':text='左上：入れた版・既定 ／ 右上：入れた版・代案':x=20:y=140:fontsize=18:fontcolor=black,"
              "drawtext=fontfile='%s':text='左下：切った版・既定':x=20:y=170:fontsize=18:fontcolor=black,"
              "drawtext=fontfile='%s':text='Unity の PC 描画（HMD ではない）。周りの海は仮置き':x=20:y=230:fontsize=16:fontcolor=0x404040,"
              "drawtext=fontfile='%s':text='（設計30 で接続する前なので、動くシートの端が見える）':x=20:y=256:fontsize=16:fontcolor=0x404040%s[v3]"
              % (FONT_FF, vname, FONT_FF, FONT_FF, FONT_FF, FONT_FF, FONT_FF, extra))
    fc.append("[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|640_0|0_360|640_360[out]")
    cmd = [FFMPEG, "-y", "-loglevel", "error"]
    for p in ins:
        cmd += ["-i", rel(p)]
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
            "-r", "30", "-frames:v", "421", "-movflags", "+faststart", rel(out)]
    subprocess.run(cmd, check=True, cwd=REPO)
    return ins, cmd


def pixel_diff(a, b):
    A = np.asarray(Image.open(a).convert("RGB"), np.int16)
    B = np.asarray(Image.open(b).convert("RGB"), np.int16)
    if A.shape != B.shape:
        return dict(shape_mismatch=True)
    dd = np.abs(A - B).max(-1)
    return dict(pixels=int(dd.size), differing=int((dd > 0).sum()), differing_gt8=int((dd > 8).sum()), max_channel_diff=int(dd.max()),
                fraction_differing=round(float((dd > 0).mean()), 6))


def gate_table(g):
    out = {}
    for k, v in g["gates"].items():
        det = v.get("detail", {})
        e = dict(value=v["value"], threshold=v["threshold"], pass_=v["pass"])
        if v.get("scope_ja"):
            e["scope_ja"] = v["scope_ja"]
        if k == "P13":
            e["items"] = {kk: dict(value=vv["value"], threshold=vv["threshold"], pass_=vv["pass"]) for kk, vv in det.items() if isinstance(vv, dict) and "threshold" in vv}
        out[k] = e
    return out


SECTIONS_NOTE_JA = ("断面が示すこと：c（−2.5 s）・d（−1.97 s）は頂が平らで、前面がほぼ鉛直（放出の前の唇の帯の下面 約 80°）。先が前へ返るのが見えるのは −1.6 s（小さな鉤）〜−1.4 s から。"
                    "−1.6〜−0.8 s は内壁が頂の真下より後ろへ下がり（唇の下の楔）、最後の約 1 s で K* の内壁の位置（頂の 3.6 m 前）へ戻る（錨を K* へ寄せる ease-in と ψ_t）。")


def profile_note_ja(RV):
    if not RV:
        return ""
    pr = RV.get("profiles_art_on", {}).get("rows", {})
    st = RV.get("profiles_art_on", {}).get("stage_tau_peak_row", {})

    def vh(name, tau):
        for e in pr.get(name, []):
            if e.get("tau") is not None and abs(e["tau"] - tau) < 1e-3:
                return e.get("near_vertical_front_height_m")
        return None
    c_, d_ = st.get("c"), st.get("d")
    vals = [vh(n, t) for n in ("main_row_159", "peak_row_192") for t in (c_, d_)]
    if None in vals:
        return ""
    return ("断面が示すこと：a は広く丸い山。b は高くなるが頂は丸いまま（頂の帽子）で、Fig. 4b のような尖った塔ではない。c・d は頂が平らで前面がほぼ鉛直（0.3H より上で 75° 以上の区間の高さ c %.0f〜%.0f m・d %.0f〜%.0f m。放出の前の唇の帯の下面 約 80°）。\n"
            "先が前へ返るのが見えるのは断面で τ −1.6 s（小さな鉤）〜−1.4 s、原画視点で τ ≈ −1.7〜−1.6 s からで、関門の d（−1.97 s）より 0.3〜0.6 s 後。c の唇先のしぶき・白は断面にはない（最初の白は峰の行 τ −2.30 s）。"
            % (min(vals[0], vals[2]), max(vals[0], vals[2]), min(vals[1], vals[3]), max(vals[1], vals[3])))


def apply_verdicts(gt, gates, rec_only, not_judge):
    """関門ごとの判定の語（合格／不合格／記録のみ（F1）／判定できない（記録のみ））を gt に書き、版ごとの一覧を返す。"""
    out = {}
    for run, G in gt.items():
        vv = {}
        for k, e in G.items():
            key = "%s:%s" % (run, k)
            if key in not_judge:
                e["pass_harness"] = e["pass_"]
                e["pass_"] = None
                e["verdict_ja"] = "判定できない（記録のみ）"
                if k == "P3":
                    dd = gates[run]["gates"]["P3"]["detail"]
                    rr = dd.get("rows_record", {})
                    mr, pk = rr.get("主断面", {}), rr.get("峰で最も高い巻きの行", {})
                    e["note_ja"] = ("検査器は ds_sea_calm_painting のため τ > −2.0 s を判定から除くので、判定の区間は主断面 %s s・峰の行 %s s だけで、巻きの行 %s 行のうち %s 行は区間が空。"
                                    "検査器の値 %s は、その短い区間の値。除いた区間を含めた始まり → t* の窓の A_net の変化 / t* の A_pos は主断面 %s・峰の行 %s・最大 %s（行 %s）で、"
                                    "τ −2.0 s から周りの海と搬送波を全体に平らにして谷がなくなる分（review_measurements.sea_calm）と、巻きの間の本体の水の減りと戻り"
                                    "（review_measurements.water_art_on）を含む" % (
                                        mr.get("judged_interval_s"), pk.get("judged_interval_s"), dd.get("rows_with_onset"), dd.get("rows_judged_interval_empty"),
                                        gates[run]["gates"]["P3"]["value"], mr.get("full_interval_max_abs_change_frac"),
                                        pk.get("full_interval_max_abs_change_frac"), dd.get("full_interval_worst_frac"), dd.get("full_interval_worst_row")))
            elif e["pass_"] is True:
                e["verdict_ja"] = "合格"
            elif e["pass_"] is False and key in rec_only:
                e["verdict_ja"] = "記録のみ（F1）"
            elif e["pass_"] is False:
                e["verdict_ja"] = "不合格"
            else:
                e["verdict_ja"] = "判定なし"
            vv[k] = e["verdict_ja"]
        out[run] = vv
    return out


def p13_items(g):
    d = g["gates"]["P13"]["detail"]
    it = {}
    for k, v in d.items():
        if isinstance(v, dict) and "threshold" in v:
            it[k.split(")")[0] + ")"] = dict(name=k, value=v["value"], pass_=v["pass"])
    return it


def backlog_map(gates, AF30G, AF30M, RV, pkgs):
    """バックログ番号 → 値 → 判定（AGENTS.md）。80・106・107・111 は連続性の項目なので、t* の原画の関門ではなく P13 と同じ検査器の値で書き、
    美術優先30 を同じ検査器で測った値（ds27_gates_af30.py）と並べる。美術優先30 の記録（自前の検査一式）とは読みが違うので直接比べない。"""
    on = p13_items(gates["art_on_default"])
    af = p13_items(AF30G) if AF30G else {}
    name = {}
    if AF30M:
        for n in ("80", "106", "107", "111"):
            name[n] = AF30M.get("items", {}).get(n, {}).get("name_ja")
    lips = (RV or {}).get("lips_art_on", {}).get("rows_beyond_peak", {})
    g = gates["art_on_default"]["gates"]

    def v(key, src):
        return src.get(key, {}).get("value")
    common = dict(index_constant_ja="全コマで同じ 96,000 頂点・同じ三角形（パッケージの約束。Unity の再生も同じ K* の格子）",
                  step_30hz_m=v("(1)", on), second_diff_30hz_m=v("(2)", on), self_intersections=v("(5f)", on),
                  continuity_items_failed="12 項目中 %d 項目" % sum(1 for x in on.values() if x["pass_"] is False),
                  af30_same_harness_items_failed=("12 項目中 %d 項目" % sum(1 for x in af.values() if x["pass_"] is False)) if af else None)
    B = {
        "80": dict(name_ja=name.get("80"), value=dict(common, min_triangle_area_m2=v("(5a)", on), normals_finite_m2=v("(6)", on),
                                                     seat_v1_wave_in_view_from_t_s=10.0),
                   verdict="記録のみ",
                   note_ja="形の切替（添字は全コマ同じ）と欠落（(5a)・(6) 合格）は 0。ただし座席 v1 から波が画面に入るのは t ≈ 10 s からで（座席 v1 の段階 a〜d の静止画は同じ画像）、"
                           "この項目の座席の仰角の値は測り直していない。連続性の検査一式は 12 項目中 5 項目が不合格"),
        "106": dict(name_ja=name.get("106"), value=dict(common, cross_row_stretch_max=v("(5d)", on), af30_same_harness_cross_row_stretch_max=v("(5d)", af)),
                    verdict="不合格",
                    note_ja="行の間の辺の伸び（(5d)）が K* の 10.9 倍（しきい値 4 倍。美術優先30 の記録の『裂けの目安 6 倍』も超える。場所は K* の列の割り付けが跳ぶ行 157/158・180/181・187〜189）。"
                            "位置跳び（(1)）は合格。同じ検査器で美術優先30 も 10.66 倍で不合格なので、この読みでの後退は小さい（+0.25 倍）"),
        "107": dict(name_ja=name.get("107"), value=dict(common, face_flips_30hz=v("(5g)", on), af30_same_harness_face_flips=v("(5g)", af)),
                    verdict="不合格",
                    note_ja="面の反転 30（奥の壁の手前の行 199 付近の唇、τ −1.77〜−0.47 s）。この項目の『面の反転 0』を満たさない。同じ検査器で美術優先30 は 15,013"),
        "111": dict(name_ja=name.get("111"), value=dict(common, P4_main_row_mps2=g["P4"]["value"], P16_default_max_mps2=g["P16"]["value"],
                                                        rows_beyond_peak_tip_ay_mps2=lips.get("tip_ay_range_mps2"), rows_beyond_peak=lips.get("rows")),
                    verdict="記録のみ",
                    note_ja="巻きの行の唇先は重力だけで落ちる（P4 −9.68 m/s²、P16 既定で下向き）、位置跳び（(1)）は合格。ただし峰の行の外側の 22 行（193〜214）の唇は κ で本体と混ざり、"
                            "唇先の縦の加速度は −9.3〜−0.5 m/s²（弾道ではない）。座席からの唇先の向きの値は測り直していない"),
        "112": dict(name_ja="性能（番号32 の 81・112）の前提", value=dict(keypose_gpu_MiB_art_on=pkgs["art_on"]["gpu_buffer_MiB"], budget_MiB=512),
                    verdict="記録のみ", note_ja="前提（keypose の容量）だけ。性能は測っていない（番号32 の手順で測る）"),
    }
    B["regression_vs_af30_ja"] = ("計画 §2.1 の『後退なし』は、同じ検査器（ds27_gates.py）では美術優先30 が P13 の 12 項目中 7 項目不合格・面の反転 15,013・行の間の伸び 10.66 倍、"
                                  "設計27 が 5 項目・30・10.9 倍。美術優先30 の記録（自前の検査一式。80・106・107・111 は合格、面の反転 0）とは読みが違うので、"
                                  "その記録と比べて後退がないとは言えない。t* の原画の関門の測り直しは t* の姿だけを見るので、これらの連続性の項目は確かめられない")
    return B


def min_acceptance(gates, verdicts, tstar, seat_st):
    on = verdicts.get("art_on_default", {})
    bad = [k for k, v in on.items() if v not in ("合格",) and k.startswith("P")]
    uniq = len(set(seat_st.get(s) for s in "abcd" if seat_st.get(s)))
    return {
        "source_ja": "計画 §2.1 の設計27［Q11］の最小の受入",
        "連続性の検査一式（形成から t*）": dict(verdict="不合格", value=gates["art_on_default"]["gates"]["P13"]["value"]),
        "t* の原画視点の値 ±0.5 px": dict(verdict="合格" if tstar.get("art_on_default", {}).get("pass_") else "不合格",
                                    value_px=tstar.get("art_on_default", {}).get("worst_abs_diff_px")),
        "P1〜P16（入れた版）": dict(verdict="一部不合格", value={k: on[k] for k in bad if k != "Painting"}),
        "座席の静止画 3 枚（噴流の始まり・段階 d・t*）": dict(
            verdict="代替（記録のみ）",
            value=dict(seat_v1_stage_a_to_d_unique_images=uniq),
            note_ja="座席 v1 は上を急に見上げるので、噴流の始まりと段階 d の静止画に波が入らない（段階 a〜d の 4 枚が同じ画像）。座席の目から仰角 30° の seat_form の連番のコマで代えた（fig_ds27_stages_seat_form.png）"),
    }


def determinism(inputs):
    """同じ入力でパッケージの 3 ファイルが同じバイトになるか（Unity/Build/Design/27/_twice に、run_ds27.ps1 -Twice の 2 回目と同じ引数で作り直したもの）。"""
    tw = os.path.join(B27, "_twice")
    if not os.path.isdir(tw):
        return dict(checked=False, ja="提出版では確かめていない")
    files = {}
    for ver in ("art_on", "art_off"):
        for fn in ("ds27_pos_rgba16.bin", "ds27_keypose.json", "ds27_twhite_r32f.bin"):
            p1, p2 = os.path.join(B27, ver, fn), os.path.join(tw, ver, fn)
            if not os.path.isfile(p2):
                continue
            h1, h2 = sha(p1), sha(p2)
            files["%s/%s" % (ver, fn)] = dict(sha256=h1, regenerated_sha256=h2, same=(h1 == h2))
    logs = {}
    for ver in ("art_on", "art_off"):
        lg = os.path.join(tw, "ds27_generate_log_%s.json" % ver)
        if os.path.isfile(lg):
            L = jload(lg)
            logs[ver] = dict(generated_utc=L.get("generated_utc"), command=L.get("command"), seconds=L.get("seconds_total"))
            inputs[rel(lg)] = sha(lg)
    return dict(checked=True, all_same=all(v["same"] for v in files.values()) and len(files) == 6, files=files, regenerate=logs,
                ja="提出版（修正2）のパッケージを、同じ ds27_model.py・ds27_params.json・K*・ds26_conditions.json から Unity/Build/Design/27/_twice へ作り直し"
                   "（ds27_generate.py --no-check --no-sea --no-tables。run_ds27.ps1 -Twice の 2 回目と同じ）、3 ファイル × 2 版の SHA-256 を比べた")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-video", action="store_true")
    ap.add_argument("--records-only", default="", help="P1〜P9・P15・P16 のうち、損切り F1 で「記録のみ」にした関門（カンマ区切り、版_時間曲線:関門）")
    ap.add_argument("--revisions", default="", help="修正の記録の JSON（Unity/Build/Design/27/ds27_revisions.json）")
    ap.add_argument("--not-judgeable", default="", help="判定の区間が実質的にないので、合格と書かずに「判定できない（記録のみ）」にする関門（版_時間曲線:関門）")
    a = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    inputs, outputs = {}, {}
    # 関門
    gates = {}
    for ver, warp in RUNS:
        p = os.path.join(B27, "gates", "%s_%s.json" % (ver, warp))
        gates["%s_%s" % (ver, warp)] = jload(p)
        inputs[rel(p)] = sha(p)
    # 段階の τ（入れた版・既定、峰の行）
    g0 = gates["art_on_default"]["gates"]
    st = g0["P15"]["detail"]["峰で最も高い巻きの行"]
    taus = {}
    for s in "abcd":
        v = st["tau"].get(s)
        taus[s] = (v, "測った時刻") if v is not None else (st["table_tau"][s], "表の時刻（判定を満たさず）")
    ap_ = g0["P4"]["detail"]["峰で最も高い巻きの行"].get("apex_tau")
    taus["apex"] = (ap_, "唇先の頂点")
    taus["tstar"] = (0.0, "t*")
    # レビュー対応の測定（ds27_review_measure.py）
    rp = os.path.join(B27, "review", "ds27_review_measure.json")
    RV = jload(rp) if os.path.isfile(rp) else None
    if RV is not None:
        inputs[rel(rp)] = sha(rp)
    # 図
    used = []
    for view, name in (("painting", "fig_ds27_stages_painting.png"), ("seat", "fig_ds27_stages_seat.png"), ("seat_form", "fig_ds27_stages_seat_form.png"),
                       ("side_left", "fig_ds27_stages_side.png")):
        p = os.path.join(EVID, name)
        runs_ = [("art_on", "default"), ("art_off", "default")]
        u = stage_sheet(view, p, runs_, taus=taus)
        if not u:
            os.remove(p)
            continue
        used += u
        outputs[rel(p)] = sha(p)
    p = os.path.join(EVID, "fig_ds27_revisions.png")
    used += revisions_figure(p)
    outputs[rel(p)] = sha(p)
    p = os.path.join(EVID, "fig_ds27_p15_fig4.png")
    used += p15_figure(p, STAGE_RUN("art_on", "default"), taus, profile_note=profile_note_ja(RV))
    outputs[rel(p)] = sha(p)
    p = os.path.join(EVID, "fig_ds27_sections.png")
    sections_figure(p, note=SECTIONS_NOTE_JA)
    outputs[rel(p)] = sha(p)
    for v in ("art_on", "art_off"):
        q = os.path.join(B27, v, "ds27_pos_rgba16.bin")
        if rel(q) not in inputs:
            inputs[rel(q)] = jload(os.path.join(B27, v, "ds27_keypose.json"))["pos_sha256"]
    for n in PAPER_SHA:
        q = os.path.join(PAPER, "img_%d.jpg" % n)
        inputs[rel(q)] = sha(q)
    for q in sorted(set(used)):
        inputs[rel(q)] = sha(q)
    cmds = []
    if not a.skip_video:
        for view in ("painting", "seat", "side_left"):
            p = os.path.join(EVID, "ds27_compare_%s.mp4" % view)
            ins, cmd = compare_video(view, p)
            for q in ins:
                inputs[rel(q)] = sha(q)
            outputs[rel(p)] = sha(p)
            cmds.append(" ".join('"%s"' % c if (" " in c or ";" in c) else c for c in cmd))
    # 描画と t* の測り直し
    renders, tstar, playback, pixdiff = {}, {}, {}, {}
    for ver, warp in RUNS:
        rd = os.path.join(B27, "%s_%s" % (ver, warp))
        rr = jload(os.path.join(rd, "ds27_render_report.json"))
        inputs[rel(os.path.join(rd, "ds27_render_report.json"))] = sha(os.path.join(rd, "ds27_render_report.json"))
        renders["%s_%s" % (ver, warp)] = dict(layers=rr.get("layers"), positionGpuBytes=rr.get("positionGpuBytes"), whiteGpuBytes=rr.get("whiteGpuBytes"),
                                               texture2DArrayRgba64EquivalentBytes=rr.get("texture2DArrayRgba64EquivalentBytes"),
                                               clampedKnotCalls=rr.get("clampedKnotCalls"), clampedFrameCalls=rr.get("clampedFrameCalls"),
                                               warpTauMin=rr.get("warpTauMin"), totalSeconds=rr.get("totalSeconds"),
                                               videos=[dict(view=v.get("view"), frames=v.get("frames"), seconds=v.get("seconds"), ffmpegError=v.get("ffmpegError")) for v in rr.get("videos", [])],
                                               stillSource=rr.get("stillSource"))
        tp = os.path.join(rd, "ds27_tstar_remeasure.json")
        if os.path.isfile(tp):
            T = jload(tp)
            inputs[rel(tp)] = sha(tp)
            sil = {x["item"]: dict(max_px=x.get("ds27_max_px"), p95_px=x.get("ds27_p95_px"), diff_vs_26r01_max_px=x.get("diff_vs_26r01_max_px"),
                                   diff_vs_26r01_p95_px=x.get("diff_vs_26r01_p95_px"), diff_vs_28r01_max_px=x.get("diff_vs_28r01_max_px"))
                   for x in T.get("silhouettes_vs_26r01_28r01", [])}
            bnd = {x["item"]: dict(ds27_max_px=x.get("ds27_max_px"), r28r01_max_px=x.get("r28r01_max_px"), diff_px=x.get("diff_px"), verdict=x.get("ds27_verdict"))
                   for x in T.get("boundaries_vs_28r01", [])}
            tstar["%s_%s" % (ver, warp)] = dict(worst_abs_diff_px=T.get("worst_abs_diff_px"), criterion_px=T.get("criterion_px"), pass_=T.get("pass"),
                                                 verdicts_ds27=T.get("summary_verdicts_ds27"), verdicts_28r01=T.get("summary_verdicts_28r01"),
                                                 silhouettes=sil, boundaries=bnd, colour_265_266_267={k: v.get("ds27_verdict") for k, v in T.get("colour_265_266_267", {}).items()},
                                                 pixel_diff_vs_af30_t28=T.get("pixel_diff_vs_af30_t28"))
        pp = os.path.join(rd, "ds27_playback_check.json")
        if os.path.isfile(pp):
            pb = jload(pp)
            if isinstance(pb.get("package"), dict) and os.path.isabs(str(pb["package"].get("dir", ""))):
                pb["package"]["dir"] = rel(pb["package"]["dir"])
            if os.path.isabs(str(pb.get("capture_report", ""))):
                pb["capture_report"] = rel(pb["capture_report"])
            playback["%s_%s" % (ver, warp)] = pb
            inputs[rel(pp)] = sha(pp)
        # t* の画像と 28修正01 の画像の画素の差
        diffs = {}
        for f in ("af28r01_painting.png", "af28r01_seat.png", "af28r01_seat_low.png", "af28r01_class_ids.png", "af28r01_line_ids.png"):
            mine = os.path.join(rd, "t28", "render", f)
            if os.path.isfile(mine) and os.path.isfile(os.path.join(R28, f)):
                diffs[f] = dict(vs_28r01=pixel_diff(mine, os.path.join(R28, f)),
                                vs_af30=(pixel_diff(mine, os.path.join(R30, f)) if os.path.isfile(os.path.join(R30, f)) else None))
        pixdiff["%s_%s" % (ver, warp)] = diffs
    # パッケージ
    pkgs = {}
    for ver in ("art_on", "art_off"):
        J = jload(os.path.join(B27, ver, "ds27_keypose.json"))
        lg = os.path.join(B27, "ds27_generate_log_%s.json" % ver)
        L = jload(lg) if os.path.isfile(lg) else {}
        pos = os.path.join(B27, ver, "ds27_pos_rgba16.bin")
        pkgs[ver] = dict(layers=J["layers"], knot_tau_range=[J["knot_tau"][0], J["knot_tau"][-1]], pos_bytes=os.path.getsize(pos),
                         pos_MiB=round(os.path.getsize(pos) / 2 ** 20, 1), pos_sha256=J["pos_sha256"], twhite_sha256=J["twhite_sha256"],
                         keypose_json_sha256=sha(os.path.join(B27, ver, "ds27_keypose.json")),
                         gpu_buffer_MiB=round(J["layers"] * 96000 * 6 / 2 ** 20, 1), texture2darray_rgba64_MiB=round(os.path.getsize(pos) / 2 ** 20, 1),
                         generate_seconds=(L.get("versions", {}).get(ver, {}).get("seconds") or L.get("seconds_total")),
                         generate_seconds_ja="ds27_generate_log_<版>.json の versions.<版>.seconds（生成・海の標本・自前の検査を含む）",
                         hermite_playback_err_m=(RV or {}).get("hermite", {}).get(ver),
                         generator_summary=J.get("generator", {}).get("summary") if isinstance(J.get("generator"), dict) else None)
        inputs[rel(os.path.join(B27, ver, "ds27_keypose.json"))] = sha(os.path.join(B27, ver, "ds27_keypose.json"))
        if os.path.isfile(lg):
            inputs[rel(lg)] = sha(lg)
        ck = os.path.join(B27, ver, "ds27_checks.json")
        if os.path.isfile(ck):
            inputs[rel(ck)] = sha(ck)
    rec_only = [x for x in a.records_only.split(",") if x]
    not_judge = [x for x in a.not_judgeable.split(",") if x]
    revisions = jload(a.revisions) if a.revisions and os.path.isfile(a.revisions) else None
    if a.revisions and os.path.isfile(a.revisions):
        inputs[rel(a.revisions)] = sha(a.revisions)
    for sub in ("r00", "r01"):
        for q in sorted(glob.glob(os.path.join(B27, sub, "gates", "*.json"))):
            inputs[rel(q)] = sha(q)
    af30p = os.path.join(B27, "gates_af30", "ds27_gates_af30.json")
    AF30G = jload(af30p) if os.path.isfile(af30p) else None
    if AF30G is not None:
        inputs[rel(af30p)] = sha(af30p)
    af30m = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "30", "metrics.json")
    AF30M = jload(af30m) if os.path.isfile(af30m) else None
    gt = {k: gate_table(v) for k, v in gates.items()}
    verdicts = apply_verdicts(gt, gates, rec_only, not_judge)
    det = determinism(inputs)
    seat_st = {}
    for s_ in ("a", "b", "c", "d", "apex", "tstar"):
        q = still(STAGE_RUN("art_on", "default"), "seat", s_)
        if q:
            seat_st[s_] = sha(q)
    M = dict(
        schema="GreatWave.DS27.metrics/1", number="設計27",
        status_ja="初回提出＋レビュー対応（numpy の生成器と検査器、Unity の PC オフスクリーン描画。HMD 実機の結果ではない）",
        evidence_kind_ja="関門は numpy の測定（パッケージを Hermite で補間して読む）。t* の原画の関門は Unity の描画を美術優先23 の評価器で測り直した値。動画・静止画は Unity の PC 描画。review_measurements は関門の外の numpy の測定（記録のみ）",
        backlog_ja="80・106・107・111（計画 §2.1：形成と重なる区間の後退なし）、112 の前提。項目ごとの値と判定は backlog（連続性の項目は t* の原画の関門では確かめられないので、P13 と同じ検査器の値で書く）",
        backlog=backlog_map(gates, AF30G, AF30M, RV, pkgs),
        minimum_acceptance_q11=min_acceptance(gates, verdicts, tstar, seat_st),
        gates=gt,
        gates_summary={k: v["summary"] for k, v in gates.items()},
        verdicts=verdicts,
        records_only_F1=rec_only,
        not_judgeable=not_judge,
        stage_tau_used_for_stills=taus,
        seat_v1_stage_stills_sha256=seat_st,
        painting_gates_tstar=tstar, tstar_pixel_diff=pixdiff, playback_check=playback, renders=renders, keypose=pkgs,
        determinism=det,
        review_measurements=RV,
        revisions=revisions,
    )
    p = os.path.join(EVID, "metrics.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(M, f, ensure_ascii=False, indent=1, default=str)
        f.write("\n")
    outputs[rel(p)] = sha(p)
    tools = dict(python=platform.python_version(), numpy=np.__version__, pillow=Image.__version__)
    try:
        tools["ffmpeg"] = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    except Exception as e:  # noqa: BLE001
        tools["ffmpeg"] = "不明（%s）" % e
    code = {}
    for f in sorted(glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(HERE, "*.json")) + glob.glob(os.path.join(HERE, "*.ps1"))):
        code[rel(f)] = sha(f)
    for f in sorted(glob.glob(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Design27", "**", "*.*"), recursive=True)):
        if not f.endswith(".meta"):
            code[rel(f)] = sha(f)
    R = dict(schema="GreatWave.DS27.run/1", number="設計27", started_utc=started,
             finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             commands_ja="Docs/Progress/Design_27_ja.md の「再現」を参照。ffmpeg の並べ図のコマンドは下の ffmpeg_commands", ffmpeg_commands=cmds,
             tools=tools, code_sha256=code, inputs_sha256=inputs, outputs_sha256=outputs,
             not_committed_ja="Unity/Build/Design/27/ は Git 対象外（/Unity/Build/）。パッケージ（版ごとに 3 ファイル、ds27_sea.npz）、関門の JSON、Unity の描画（1920×1080 の静止画・動画・連番）はそこに置き、SHA-256 だけを記録する。")
    p = os.path.join(EVID, "run.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("DS27_EVIDENCE done ->", rel(EVID))


if __name__ == "__main__":
    main()
