# -*- coding: utf-8 -*-
"""仕上げ28修正01：記録の証拠を作る（py -3.10。PIL・numpy・ffmpeg）。形は作らない。

入力は Git 対象外の Unity/Build/Polish/28r01/ の出力だけ：
  - ridge/renders（rays_bl.py の粘土。土台 P28R2rec と RIDGE の候補 P28R01RG の同じ視点、回り台のコマと動画）
  - shoulder/final/renders（同じ。SHOULDER の候補 P28R01SH）
  - ridge/final・ridge/metrics.json・shoulder/final（作る部の数値）、_judge/numbers（評審の数値）
  - 行の npz（頂の高さ H(c) の図のため。土台・RIDGE・SHOULDER）
参照モデルは読まない。出力は Docs/Evidence/Polish/28R01/（1920×1080 の PNG、5 MB 以下の MP4、metrics.json、run.json）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28r01_record.py all --start 2026-10-01T10:09 --end <時刻>
  （all ＝ sheets・hc・video・metrics・run を順に。どれか 1 つだけも可）
"""
import datetime
import glob
import hashlib
import json
import os
import platform
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Polish", "28r01")
B28 = os.path.join(REPO, "Unity", "Build", "Polish", "28")
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "28R01")
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
FFPROBE = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffprobe.exe"

FONT_M = r"C:\Windows\Fonts\YuGothM.ttc"
FONT_B = r"C:\Windows\Fonts\YuGothB.ttc"


def font(sz, bold=False):
    for p in ((FONT_B if bold else FONT_M), r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


# 3 つの形（列の順）
SHAPES = [
    ("base", "P28R2rec（採用のまま）", os.path.join(B, "ridge", "renders", "P28R2rec__%s.png"),
     os.path.join(B, "ridge", "renders", "turntable_P28R2rec", "f_%04d.png"), os.path.join(B, "ridge", "renders", "turntable_P28R2rec.mp4")),
    ("RG", "RIDGE P28R01RG（採らない）", os.path.join(B, "ridge", "renders", "RG__%s.png"),
     os.path.join(B, "ridge", "renders", "turntable_RG", "f_%04d.png"), os.path.join(B, "ridge", "renders", "turntable_RG.mp4")),
    ("SH", "SHOULDER P28R01SH（採らない）", os.path.join(B, "shoulder", "final", "renders", "P28R01SH__%s.png"),
     os.path.join(B, "shoulder", "final", "renders", "turntable_P28R01SH", "f_%04d.png"),
     os.path.join(B, "shoulder", "final", "renders", "turntable_P28R01SH.mp4")),
]

VIEW_JA = {
    "b65_back65_clay": "後ろ 65°（b65）",
    "b65z_back65_zoom": "後ろ 65° の拡大（b65z）",
    "b90_back_straight": "真後ろ（b90）",
    "b115_back_minus_c": "−c 側の後ろ（b115）",
    "v5_back_three_quarter": "後ろ斜め（v5）",
    "v6_top_down": "真上（v6）",
    "v4_true_side_perp_crest_front": "正面の真横（v4）",
    "v7_user6_az330_el10": "利用者の視点 v7（az330 el10）",
    "v8_user7_az290_el5": "利用者の視点 v8（az290 el5）",
    "v9_user8_az030_el25": "利用者の視点 v9（az030 el25）",
    "v1_painting": "原画視点（v1）",
    "v2_seat": "座席（v2）",
}

DIFF_T = 24  # 差の数え方：どれかの色の値の差が 24 を超える画素（判者の _judge の数え方と同じしきい値）


def load(p):
    return np.asarray(Image.open(p).convert("RGB"))


def diff_px(a, b):
    return int((np.abs(a.astype(np.int16) - b.astype(np.int16)).max(-1) > DIFF_T).sum())


def label(im, text, f, y=0):
    d = ImageDraw.Draw(im)
    tw = d.textlength(text, font=f)
    d.rectangle([0, y, tw + 12, y + f.size + 10], fill=(0, 0, 0))
    d.text((6, y + 3), text, fill=(255, 230, 0), font=f)


NL = chr(10)


def wrap(d, text, f, width):
    """日本語は 1 字ずつ、英数字の続き（数・名前）は切らずに折り返す。"""
    toks, cur = [], ""
    for ch in text:
        if ord(ch) < 128 and ch not in (" ", NL):
            cur += ch
            continue
        if cur:
            toks.append(cur); cur = ""
        toks.append(ch)
    if cur:
        toks.append(cur)
    out, line = [], ""
    for t in toks:
        if t == NL:
            out.append(line); line = ""; continue
        if line and d.textlength(line + t, font=f) > width:
            out.append(line); line = t.lstrip()
        else:
            line += t
    if line:
        out.append(line)
    return out


def panel(w, h, title, paras, f=None, ft=None):
    f = f or font(21)
    ft = ft or font(27, True)
    im = Image.new("RGB", (w, h), (250, 250, 247))
    d = ImageDraw.Draw(im)
    y = 14
    for ln in wrap(d, title, ft, w - 28):
        d.text((14, y), ln, fill=(10, 10, 10), font=ft); y += ft.size + 8
    y += 8
    for p in paras:
        for ln in wrap(d, p, f, w - 28):
            d.text((14, y), ln, fill=(40, 40, 38), font=f); y += f.size + 7
        y += 10
    return im


# ---------------------------------------------------------------- 前後の図
def sheet_views(views, out, title, paras):
    """3 視点（行）× 3 つの形（列）。描画は 1100×1000 なので縦横比を保って 396×360 にし、右に判定の欄を置く。"""
    tw, th = 396, 360
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    stats = {}
    for r, v in enumerate(views):
        base = load(SHAPES[0][2] % v)
        for c, (key, name, pat, _, _) in enumerate(SHAPES):
            a = load(pat % v)
            n = 0 if key == "base" else diff_px(a, base)
            stats.setdefault(v, {})[key] = n
            im = Image.fromarray(a).resize((tw, th), Image.LANCZOS)
            label(im, name, font(15, True))
            label(im, VIEW_JA.get(v, v) + ("" if key == "base" else "｜差 %s 画素" % format(n, ",")), font(15), y=26)
            W.paste(im, (c * tw, r * th))
    W.paste(panel(1920 - 3 * tw, 1080, title, paras), (3 * tw, 0))
    W.save(out)
    return stats


def sheet_turntable(frames, out):
    """回り台のコマ（1280×720）を 640×360 で 3 行 × 3 列。"""
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    stats = {}
    for r, fr in enumerate(frames):
        base = load(SHAPES[0][3] % fr)
        for c, (key, name, _, pat, _) in enumerate(SHAPES):
            a = load(pat % fr)
            n = 0 if key == "base" else diff_px(a, base)
            stats.setdefault("f%04d" % fr, {})[key] = n
            im = Image.fromarray(a).resize((640, 360), Image.LANCZOS)
            label(im, name, font(16, True))
            label(im, "回り台 f%04d" % fr + ("" if key == "base" else "｜差 %s 画素" % format(n, ",")), font(16), y=28)
            W.paste(im, (c * 640, r * 360))
    W.save(out)
    return stats


def crop_box(views_bbox, shape=(1000, 1100), pad=1.35, minw=360):
    x0, y0, x1, y1 = views_bbox
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w = max((x1 - x0) * pad, (y1 - y0) * pad * 16 / 9, minw)
    w = min(w, shape[1])
    h = w * 9 / 16
    h = min(h, shape[0])
    cx = min(max(cx, w / 2), shape[1] - w / 2)
    cy = min(max(cy, h / 2), shape[0] - h / 2)
    return int(round(cx - w / 2)), int(round(cy - h / 2)), int(round(cx + w / 2)), int(round(cy + h / 2))


def bbox_of(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (float(np.percentile(xs, 1)), float(np.percentile(ys, 1)), float(np.percentile(xs, 99)), float(np.percentile(ys, 99)))


def sheet_zoom(views, out):
    """RIDGE（と SHOULDER）が土台と違う所を切り出す。窓は差の画素の 1〜99% の範囲を 1.35 倍に広げ、16:9 にした同じ窓を 3 列に使う。"""
    W = Image.new("RGB", (1920, 1080), (255, 255, 255))
    boxes = {}
    for r, v in enumerate(views):
        base = load(SHAPES[0][2] % v)
        ms = []
        for key, _, pat, _, _ in SHAPES[1:]:
            a = load(pat % v)
            ms.append(np.abs(a.astype(np.int16) - base.astype(np.int16)).max(-1) > DIFF_T)
        bb = bbox_of(ms[0] | ms[1])
        box = crop_box(bb, base.shape[:2])
        boxes[v] = box
        for c, (key, name, pat, _, _) in enumerate(SHAPES):
            im = Image.open(pat % v).convert("RGB").crop(box).resize((640, 360), Image.LANCZOS)
            label(im, name, font(16, True))
            label(im, "%s の拡大（x %d〜%d、y %d〜%d）" % (VIEW_JA.get(v, v), box[0], box[2], box[1], box[3]), font(15), y=28)
            W.paste(im, (c * 640, r * 360))
    W.save(out)
    return boxes


# ---------------------------------------------------------------- 頂の高さ H(c) の図
def hc_figure(out):
    """後ろから見た山の輪郭を決める頂の高さ H(c)（行ごとの Y の最大）と、原画が許す幅（silhouette_freedom.json）。"""
    rows = {
        "base": os.path.join(B28, "kstar_p28rec", "kstarP28R2rec_a45_rows.npz"),
        "RG": os.path.join(B, "ridge", "cand", "kstarP28R01RG_a45_rows.npz"),
        "SH": os.path.join(B, "shoulder", "cand", "kstarP28R01SH_a45_rows.npz"),
    }
    H = {}
    for k, p in rows.items():
        z = np.load(p)
        H[k] = (z["c"].astype(float), z["Y"].max(axis=1).astype(float))
    sf = json.load(open(os.path.join(B, "shoulder", "final", "silhouette_freedom.json"), encoding="utf-8"))["rows"]
    sh_same = float(np.abs(H["SH"][1] - H["base"][1]).max())

    W, Hh = 1920, 1080
    im = Image.new("RGB", (W, Hh), (252, 252, 251))
    d = ImageDraw.Draw(im)
    L, R, T, Bm = 120, 1450, 120, 960
    cx0, cx1, y0, y1 = -20.0, 16.0, 0.0, 28.0
    X = lambda c: L + (c - cx0) / (cx1 - cx0) * (R - L)
    Y = lambda y: Bm - (y - y0) / (y1 - y0) * (Bm - T)
    ink, ink2, grid = (11, 11, 11), (82, 81, 78), (228, 228, 224)
    blue, orange, band = (42, 120, 214), (235, 104, 52), (214, 214, 208)
    # 原画が H を止める範囲の帯（灰の地）
    bands = ((cx0, -1.0, ["原画が頂の高さを止める（c ≤ −1）"], T + 8), (9.6, 13.2, ["c 9.6〜13.2：", "管の口から見える", "唇の上で止まる"], Y(6.5)))
    for a, b, txts, ty in bands:
        d.rectangle([X(a), T, X(b), Bm], fill=(240, 240, 236))
    for a, b, txts, ty in bands:
        for i, txt in enumerate(txts):
            d.text((X(a) + 4, ty + i * 22), txt, fill=ink2, font=font(16))
    for g in range(0, 29, 4):
        d.line([L, Y(g), R, Y(g)], fill=grid, width=1)
        d.text((L - 46, Y(g) - 12), "%d" % g, fill=ink2, font=font(19))
    for g in range(-20, 17, 4):
        d.line([X(g), T, X(g), Bm], fill=grid, width=1)
        d.text((X(g) - 14, Bm + 8), "%+d" % g if g else "0", fill=ink2, font=font(19))
    d.line([L, Bm, R, Bm], fill=ink2, width=2)
    d.text((L + 470, Bm + 40), "c（m）：峰に沿う位置。− が手前の尾、+ が奥の端", fill=ink, font=font(21))
    d.text((L - 100, T - 30), "高さ（m）", fill=ink, font=font(19))
    # 原画が許す幅：下限（管の口から見える唇と天井）と上限（空の射線）
    pts = [(r["c"], r["visible_max_y"], r["ceiling_above_crest"], r["ceiling_max_within_12m_behind_crest"], r["crest_visible_in_painting"]) for r in sf]
    cs = [p[0] for p in pts]
    lo = [p[1] for p in pts]
    hi = [min(p[2], y1) for p in pts]
    hi12 = [min(p[3], y1) for p in pts]
    poly = [(X(c), Y(h)) for c, h in zip(cs, hi)] + [(X(c), Y(l if l is not None else 0.0)) for c, l in reversed(list(zip(cs, lo)))]
    d.polygon(poly, fill=band)
    for seq, col, dash in ((hi12, (150, 150, 144), 10), (hi, (110, 110, 104), 0)):
        for i in range(len(cs) - 1):
            if dash and (i % 2 or cs[i] < -1.0):
                continue  # 後ろへずらす上限は、原画の頂の奥（c ≥ −1）だけで意味がある
            d.line([X(cs[i]), Y(seq[i]), X(cs[i + 1]), Y(seq[i + 1])], fill=col, width=2)
    # 頂の高さ：P28R2rec（＝SHOULDER）を全部、RIDGE は P28R2rec と 1 cm 以上違う所だけ（同じ所は重なるので）
    cb0, hb0 = H["base"]
    m = (cb0 >= cx0) & (cb0 <= cx1)
    d.line([(X(a), Y(b)) for a, b in zip(cb0[m], hb0[m])], fill=blue, width=4)
    cr0, hr0 = H["RG"]
    m = (cr0 >= cx0) & (cr0 <= cx1) & (np.abs(hr0 - np.interp(cr0, cb0, hb0)) > 0.01)
    idx = np.nonzero(m)[0]
    if len(idx):
        i0, i1 = max(idx[0] - 1, 0), min(idx[-1] + 1, len(cr0) - 1)
        d.line([(X(a), Y(b)) for a, b in zip(cr0[i0:i1 + 1], hr0[i0:i1 + 1])], fill=orange, width=4)
    # 頂が原画の輪郭を描く行（H は動かせない）
    for c, l, h, h12, vis in pts:
        if vis:
            yv = float(np.interp(c, H["base"][0], H["base"][1]))
            d.polygon([(X(c), Y(yv) - 12), (X(c) - 9, Y(yv) + 4), (X(c) + 9, Y(yv) + 4)], fill=ink)
    # 直接の名札
    cb, hb = H["base"]
    d.text((X(-14.0), Y(22.6)), "P28R2rec・SHOULDER（同じ。RIDGE も c < 0 は同じ）", fill=ink, font=font(21, True))
    d.line([X(-7.0), Y(21.7), X(-7.0), Y(float(np.interp(-7.0, cb, hb))) - 6], fill=blue, width=2)
    cr, hr = H["RG"]
    d.text((X(3.0), Y(21.95)), "RIDGE（奥へ上る稜、最高 21.27 m・c +5.8）", fill=ink, font=font(21, True))
    d.text((X(-19.5), Y(26.5)), "灰の帯：原画を変えずに頂が取れる高さ（下限＝管の口から見える唇と天井、上限＝原画の空の射線。頂の平面の位置のまま）", fill=ink2, font=font(18))
    d.text((X(-19.5), Y(25.3)), "破線：頂を後ろへ 12 m までずらした時の上限。▲：頂が原画の輪郭を描く行（高さは動かせない）", fill=ink2, font=font(18))
    d.text((X(-19.5), Y(24.1)), "c 0〜9 で帯の下の方へ下げる向きは、管の天井と殻の厚みに当たる（SHOULDER の S5 で最大 1.4 m）", fill=ink2, font=font(18))
    # 題と欄
    d.text((L, 26), "後ろから見た山の輪郭は、行ごとの頂の高さ H(c) で決まる（t*、K*′）", fill=ink, font=font(32, True))
    d.text((L, 64), "SHOULDER は H(c) を変えない（差の最大 %.3f m）。動かせるのは c 0〜9 で頂を上げる向きだけで、RIDGE はそれを使った" % sh_same,
           fill=ink2, font=font(21))
    lines = []
    for r in sf:
        if r["c"] in (-12.0, -6.0, -2.0, -1.0, 0.0, 2.0, 4.0, 6.0, 8.0, 9.6, 11.4, 13.2):
            lines.append("c %+5.1f  H %5.2f  下限 %s  上限 %5.2f%s" % (r["c"], r["H_base"], ("%5.2f" % r["visible_max_y"]) if r["visible_max_y"] is not None else "  —  ",
                                                                   r["ceiling_above_crest"], "  ▲" if r["crest_visible_in_painting"] else ""))
    pp = panel(1920 - R - 30, 900, "行ごとの値（m、P28R2rec）", ["silhouette_freedom.json（SHOULDER の作る部）から"] + [], f=font(19), ft=font(24, True))
    dd = ImageDraw.Draw(pp)
    yy = 120
    for ln in lines:
        dd.text((14, yy), ln, fill=(30, 30, 30), font=font(18)); yy += 30
    cap58 = float(np.interp(float(cr[np.argmax(hr)]), cs, hi))
    for ln in wrap(dd, "▲＝頂が原画の輪郭を描く行。RIDGE の最高 %.2f m（c %+.1f）は上限の内（この図の頂の平面の位置のままの読みで約 %.1f m。RIDGE は頂を最大 1.1 m 後ろへずらし、船・手前の海の射線と Rmin の見張りも入れた自分の読みで 22.81 m）。"
                   % (float(hr.max()), float(cr[np.argmax(hr)]), cap58), font(18), 1920 - R - 30 - 28):
        dd.text((14, yy + 16), ln, fill=(30, 30, 30), font=font(18)); yy += 27
    im.paste(pp, (R + 30, 120))
    im.save(out)
    return {"SH_H_minus_base_max_m": sh_same,
            "base_Hmax": [float(hb.max()), float(cb[np.argmax(hb)])],
            "RG_Hmax": [float(hr.max()), float(cr[np.argmax(hr)])]}


# ---------------------------------------------------------------- 回り台の動画
def video(out):
    """3 つの回り台（各 1280×720、30 fps、240 コマ）を 960×540 の 2×2 に並べ、右下に説明を置く。"""
    ov = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    for i, (key, name, _, _, _) in enumerate(SHAPES):
        x, y = (i % 2) * 960, (i // 2) * 540
        f = font(24, True)
        tw = d.textlength(name, font=f)
        d.rectangle([x, y, x + tw + 16, y + f.size + 14], fill=(0, 0, 0, 255))
        d.text((x + 8, y + 5), name, fill=(255, 230, 0, 255), font=f)
    p = panel(960, 540, "仕上げ28修正01：回り台（粘土、t*、Blender Workbench）",
              ["同じカメラ・同じコマで、P28R2rec（採用のまま）・RIDGE・SHOULDER を並べた。",
               "後ろ側（f120〜f220、およそ 4〜7.3 s）で、どれも頭巾の形のドームが残る。RIDGE は頂が奥の端へ移り、f180・f200 で丸い冠、f220 で瘤。SHOULDER は頭巾の頭が同じで、奥の端が後ろへ長い鰭になる。",
               "原画視点と座席から見える面は 3 つとも画素まで同じ。作品の色・線・白ではない（形だけ）。HMD 実機の結果ではない。"],
              f=font(22), ft=font(26, True))
    ov.paste(p.convert("RGBA"), (960, 540))
    ovp = os.path.join(B, "record", "video_overlay.png")
    os.makedirs(os.path.dirname(ovp), exist_ok=True)
    ov.save(ovp)
    vids = [s[4] for s in SHAPES]
    flt = ("[0:v]scale=960:540,setsar=1[a];[1:v]scale=960:540,setsar=1[b];[2:v]scale=960:540,setsar=1[c];"
           "color=c=0x101010:s=960x540:r=30:d=8[d];[a][b][c][d]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[g];"
           "[g][3:v]overlay=0:0:shortest=1,format=yuv420p[v]")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", vids[0], "-i", vids[1], "-i", vids[2], "-loop", "1", "-i", ovp,
           "-filter_complex", flt, "-map", "[v]", "-r", "30", "-frames:v", "240", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", out]
    subprocess.run(cmd, check=True)
    return {"cmd": " ".join('"%s"' % c if (" " in c or "|" in c or ";" in c) else c for c in cmd), "bytes": os.path.getsize(out)}


# ---------------------------------------------------------------- 数値
def J(p):
    return json.load(open(p, encoding="utf-8"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def metrics(out, extra):
    rg = J(os.path.join(B, "ridge", "metrics.json"))
    shm = J(os.path.join(B, "shoulder", "final", "metrics.json"))
    jn = os.path.join(B, "_judge", "numbers")
    zb = J(os.path.join(jn, "jn_zbuf.json"))
    gate = J(os.path.join(jn, "jn_gate_P28R2rec_RG_SH.json"))
    seat = J(os.path.join(jn, "jn_extra.json"))
    band = J(os.path.join(jn, "jn_band.json"))
    dome = J(os.path.join(jn, "jn_dome_R4_P28R2rec_RG_SH.json"))
    cons = J(os.path.join(jn, "jn_consist.json"))
    m28 = J(os.path.join(REPO, "Docs", "Evidence", "Polish", "28", "metrics.json"))
    rr = rg["closing_criteria_plan_5_3"][0]["value"]
    shd = shm["dome_metrics_r2"]
    carried = {k: v for k, v in m28["backlog"].items()}
    M = {
        "schema": "GreatWave.Polish28r01.metrics/1",
        "number": "仕上げ28修正01（設計28 原画の弧・最後の一コマ。後ろから見たドームのもう一度の試み。進行役の決定 2026-10-01、Q24）",
        "made_local": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "state_ja": "達成していない。ドームは目で見て消えていない（RIDGE・SHOULDER のどちらも）。どちらも採らず、K*′ P28R2rec と動き G_p28rec のままにする。HMD 実機の結果ではない。利用者は見ていない。",
        "evidence_kind_ja": "numpy の形の生成器と評価器、Blender 5.2.2 の粘土（Workbench）、numpy の z バッファー（原画視点・座席）。Unity の描画・動きの当て直し・焼き込みはしていない。",
        "adopted": {"kstar": "K*′ P28R2rec（Unity/Build/Polish/28/kstar_p28rec、変えない）", "motion": "G_p28rec（変えない）",
                    "kstar_gwb_sha256": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94"},
        "candidates": {
            "RIDGE": {"name": "K*′ P28R01RG", "gwb_sha256": cons["RG"]["sha256"], "verdict": "採らない",
                      "by_eye_ja": rg["eye_verdict_dome"]["status"]},
            "SHOULDER": {"name": "K*′ P28R01SH", "gwb_sha256": cons["SH"]["sha256"], "verdict": "採らない",
                         "by_eye_ja": shm["dome_by_eye_ja"]},
        },
        "dome_by_eye": {
            "verdict": "満たさない（3 つとも、後ろ 65° と回り台の後ろ側で頭巾の形のドームが残る）",
            "views_ja": "後ろ 65°・その拡大・真後ろ・−c 側の後ろ・後ろ斜め・真上・回り台（12 コマ）、正面の真横・利用者の視点 v7・v8・v9、原画視点・座席",
            "judges": [
                {"best": "P28R2rec", "dome_gone_by_eye": False, "scores_0_10": {
                    "P28R2rec": {"dome_back65": 2, "dome_back90_115": 2, "turntable_back": 2, "painting_view_intact": 10, "user_views_clean": 7, "thickness_Q16": 3, "overall": 4},
                    "RIDGE": {"dome_back65": 3, "dome_back90_115": 5, "turntable_back": 3, "painting_view_intact": 10, "user_views_clean": 4, "thickness_Q16": 2, "overall": 4},
                    "SHOULDER": {"dome_back65": 2, "dome_back90_115": 2, "turntable_back": 1, "painting_view_intact": 10, "user_views_clean": 4, "thickness_Q16": 0, "overall": 2}}},
                {"best": "P28R2rec", "dome_gone_by_eye": False, "note_ja": "数値の判者。原画視点・座席の不変、関門、b区域、F04、F10、Q17、R6 を gwb から読み直した"}],
            "pixel_diff_vs_P28R2rec": extra.get("diff", {}),
        },
        "closing_criteria_plan_5_3": [
            {"criterion_ja": "後ろ 65° と回り台でドームが見えない（Q21）", "verdict": "満たさない（3 つとも）",
             "value": {"groove_depth_max_m_[y,depth,c]": rr["groove_depth_max_m_[y,depth,c]"], "H_max_m_and_c": rr["H_max_m_and_c"],
                       "back_elliptic_frac": {"P28R2rec": 0.359, "RIDGE": rr["back_elliptic_frac"]["RG"], "SHOULDER": shd["P28R01SH"]["back_elliptic_frac"], "R4": 0.445},
                       "back_plan_bow_0.5H0_0.7H0_m": {"P28R2rec": [4.344, 1.263], "RIDGE": rr["back_plan_bow_0.5H0_0.7H0_m"]["RG"],
                                                       "SHOULDER": [shd["P28R01SH"]["back_plan_bow_0.5H0_L8_max_m"], shd["P28R01SH"]["back_plan_bow_0.7H0_L8_max_m"]], "R4": [3.929, 2.025]},
                       "R6_p99_record_only": {"P28R2rec": 0.69, "RIDGE": 0.90, "SHOULDER": 0.69, "R4": 0.693,
                                              "judge_gwb_reading": {"P28R2rec": dome["P28R2rec"]["bulge6"]["R6"]["p99"], "RIDGE": dome["RG"]["bulge6"]["R6"]["p99"],
                                                                    "SHOULDER": dome["SH"]["bulge6"]["R6"]["p99"], "R4": dome["R4"]["bulge6"]["R6"]["p99"]},
                                              "note_ja": "R6 は目で見るドームを測っていない（P28R2rec・SHOULDER の最大は b区域のこぶ c −15・列 174、RIDGE は新しい奥の頂 c +7.0・列 87）"}}},
            {"criterion_ja": "b区域が 3 つの房に読める（Q21）", "verdict": "満たさない（3 つとも房 1 つ、x 425、際立ち 35.9 px。原画視点が変わらないので同じ）",
             "value": {k: band[k]["lobes_prom6"] for k in ("P28R2rec", "RG", "SH")}},
            {"criterion_ja": "F04 ≤ 18.5 m で本体が薄く見えない（Q16・Q21）", "verdict": "F04 は満たさない（3 つとも）。SHOULDER は大きく悪化、RIDGE は上の段で太る。薄く見えないは満たす",
             "value": {"F04_0.5H0_m": {"P28R2rec": dome["P28R2rec"]["F04_side_0.50H0"]["width_m"], "RIDGE": dome["RG"]["F04_side_0.50H0"]["width_m"], "SHOULDER": dome["SH"]["F04_side_0.50H0"]["width_m"]},
                       "F04_0.75H0_m": {"P28R2rec": dome["P28R2rec"]["F04_side_0.75H0"]["width_m"], "RIDGE": dome["RG"]["F04_side_0.75H0"]["width_m"], "SHOULDER": dome["SH"]["F04_side_0.75H0"]["width_m"]},
                       "F04_0.9H0_m": {"P28R2rec": dome["P28R2rec"]["F04_side_0.90H0"]["width_m"], "RIDGE": dome["RG"]["F04_side_0.90H0"]["width_m"], "SHOULDER": dome["SH"]["F04_side_0.90H0"]["width_m"]},
                       "rows_abs_c_le_6_width_m": {"P28R2rec": 10.35, "RIDGE": 10.63, "SHOULDER": 19.76},
                       "volume_far_c_gt_0_m3": {"P28R2rec": 1887.51, "RIDGE": 2136, "SHOULDER": 3574.98},
                       "fullness_ratio": {"P28R2rec": 1.35, "RIDGE": 1.51, "SHOULDER": 2.20}}},
            {"criterion_ja": "78・130・131 が定義どおりの読みで ≤ 4 px", "verdict": "満たす（3 つとも同じ値）",
             "value": {"unity_P28R2rec_carried": [2.741, 3.5815, 3.4419], "geometric_all_three": gate["P28R2rec"]["definition"]["78"][:1] + gate["P28R2rec"]["definition"]["130"][:1] + gate["P28R2rec"]["definition"]["131"][:1],
                       "CP1": [2.772, 1.968, 1.814], "26R01": [1.641, 1.953, 1.798]}},
            {"criterion_ja": "132・72（爪なし）が σ24 の緩めなし（σ12）で ≤ 4 px", "verdict": "満たす（3 つとも同じ値）",
             "value": {"unity_P28R2rec_carried": [3.5576, 3.8507], "lf_sigma12_all_three": [gate["P28R2rec"]["lf_sigma12"]["132"][0], gate["P28R2rec"]["lf_sigma12"]["72"][1]],
                       "CP1": [1.326, 1.558], "26R01": [1.574, 1.723]}},
            {"criterion_ja": "134・267 が合格", "verdict": "満たさない（原画視点が変わらないので仕上げ28 の値のまま：134 爪なし 7.264 px、267 の帯 6）",
             "value": {"134_clawfree": 7.264, "134_claws": 2.047, "267_bands_clawfree": 6, "267_bands_claws": 4}},
            {"criterion_ja": "t* の頂と手前の尾の行が弧（Q17）", "verdict": "満たす（3 つとも）。RIDGE は本体の Rmin と稜の行の弦の余裕を減らす",
             "value": {"arcs": {k: rg["closing_criteria_plan_5_3"][6]["value"]["arcs_pm2m_near_tail_and_main"].get(k) for k in ("P28R2rec", "RG")},
                       "SHOULDER_arcs": shd["P28R01SH"]["arcs_pm2m"],
                       "F02_Rmin_c-5..3_m": {"P28R2rec": 2.418, "RIDGE": 1.606, "SHOULDER": 2.418},
                       "ridge_rows_top_chord_min_deg_c-2..9": {"P28R2rec": 137.5, "RIDGE": 120.3}}},
        ],
        "closing_criteria_met": "3/7（仕上げ28 と同じ。この修正で変わった目安はない）",
        "painting_view_unchanged": {
            "zbuffer_painting_3840x2160_vs_P28R2rec": zb,
            "seat_angular_raster_0p05deg": {k: {"RG": v["RG"], "SH": v["SH"]} for k, v in seat.items() if k.startswith("seat")},
            "SHOULDER_check": {k: shm["painting_view_unchanged"][k] for k in ("painting_zbuffer_ss1", "painting_zbuffer_ss2", "shell_lines_ss1", "H_change_max_m")},
            "evaluator_note_ja": "Unity の評価器（爪あり・爪なし）は回していない。原画視点で見える面が画素まで同じ（見える三角形の違い 0 画素、奥行きの差の最大 0.24 mm）なので、値は仕上げ28 の Unity の読み（P28R2rec）のまま。どちらの案も採らないので、採用の状態の値も変わらない。",
        },
        "topology_kept": {k: {"tris_same": cons[k]["tris_same_as_rec"], "uv_same": cons[k]["uv_same_as_rec"], "uv2_same": cons[k]["uv2_same_as_rec"],
                              "move_vs_P28R2rec_m": cons[k]["move_vs_rec_m"]} for k in ("RG", "SH")},
        "rubric_must_fail_builder_reading": {"P28R2rec": 27, "RIDGE": 28, "SHOULDER": 30, "R4": 28,
                                             "RIDGE_added": rg["rubric_must_fail_added_vs_P28R2rec"], "RIDGE_removed": rg["rubric_must_fail_removed_vs_P28R2rec"],
                                             "SHOULDER_added": list(shm["rubric_must_fail_new_vs_base"].keys())},
        "surface_quality_record_only": {"bump4_p99": {"P28R2rec": 1.628, "RIDGE": 1.829, "SHOULDER": 1.688},
                                        "mean_curvature_extrema": {"P28R2rec": 29, "RIDGE": 31},
                                        "cross_row_folds_gt30": {"P28R2rec": 57, "RIDGE": 57, "SHOULDER": 49},
                                        "F10_height_step_m": {"P28R2rec": 0.047, "RIDGE": 0.047, "A5": 0.433}},
        "hc_figure": extra.get("hc", {}),
        "silhouette_freedom_ja": "後ろから見た山の輪郭は行ごとの頂の高さ H(c) で決まる。c ≤ −1 の行は頂が原画の輪郭を描くか、見える点が頂の 0.25 m 以内にあり、空の射線の天井も頂の 0.1〜0.5 m 上しかない。c 9.6〜13.2 の行は管の口から見える唇の約 1 m 上で止まる。背の殻だけを変える案（SHOULDER）は H(c) を変えない。動かせるのは c 0〜9 で頂を上げる向き（天井 20.6〜24.8 m）だけで、それが RIDGE。",
        "backlog_carried_from_polish28": {"note_ja": "どちらの案も採らないので、採用の状態（P28R2rec・G_p28rec）の値は仕上げ28 の metrics.json のまま", "items": carried},
        "not_done_ja": ["Unity の描画（どちらの案も採らないので行わない）", "動きの当て直し・焼き込み・爪・色の作り直し（同じ）", "HMD 実機"],
    }
    json.dump(M, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def run_json(out, start, end, outputs):
    code = sorted(glob.glob(os.path.join(REPO, "Tools", "GWWaveGen", "kstar_p28", "r01_*.py"))) + [os.path.abspath(__file__)]
    inputs = [
        os.path.join(B28, "kstar_p28rec", "kstarP28R2rec_a45.gwb"),
        os.path.join(B28, "kstar_p28rec", "kstarP28R2rec_a45_rows.npz"),
        os.path.join(B, "ridge", "cand", "kstarP28R01RG_a45.gwb"),
        os.path.join(B, "ridge", "cand", "kstarP28R01RG_a45_rows.npz"),
        os.path.join(B, "ridge", "cand", "ridge_design.json"),
        os.path.join(B, "shoulder", "cand", "kstarP28R01SH_a45.gwb"),
        os.path.join(B, "shoulder", "cand", "kstarP28R01SH_a45_rows.npz"),
        os.path.join(B, "shoulder", "cand", "shoulder_design.json"),
        os.path.join(B, "ridge", "metrics.json"), os.path.join(B, "ridge", "run.json"),
        os.path.join(B, "shoulder", "final", "metrics.json"), os.path.join(B, "shoulder", "final", "run.json"),
        os.path.join(B, "shoulder", "final", "silhouette_freedom.json"), os.path.join(B, "shoulder", "final", "trials_table.json"),
        os.path.join(B, "ridge", "renders", "turntable_P28R2rec.mp4"), os.path.join(B, "ridge", "renders", "turntable_RG.mp4"),
        os.path.join(B, "shoulder", "final", "renders", "turntable_P28R01SH.mp4"),
    ] + sorted(glob.glob(os.path.join(B, "_judge", "numbers", "*.json"))) + sorted(glob.glob(os.path.join(B, "_judge", "numbers", "*.py"))) \
      + sorted(glob.glob(os.path.join(B, "_judge", "*.py"))) + sorted(glob.glob(os.path.join(B, "_judge", "*.png"))) \
      + [os.path.join(B, "ridge", "_tmp", "deleted_caches_sha256.txt"), os.path.join(B, "shoulder", "_tmp", "deleted_caches_sha256.txt")]
    hip = [os.path.join(REPO, "Houdini", "Polish28", "r01_ridge.hiplc"), os.path.join(REPO, "Houdini", "Polish28", "r01_shoulder.hiplc")]
    try:
        ffv = subprocess.run([FFMPEG, "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    except Exception:
        ffv = "?"
    import PIL
    R = {
        "schema": "GreatWave.Polish28r01.run/1",
        "time_local": {"start": start, "end": end, "time_box": "1 日（進行役の決定、2026-10-01、Q24）",
                       "parts": {"SHOULDER": "10:09:27〜10:51:25", "RIDGE": "10:09〜11:34（記録 11:36）", "judges": "〜11:42", "record": "11:45〜12:10"}},
        "machine": {"python": platform.python_version(), "numpy": np.__version__, "pillow": PIL.__version__, "platform": platform.platform(), "ffmpeg": ffv,
                    "blender": "5.2.2 (G:/SteamLibrary/steamapps/common/Blender/blender.exe)、粘土は rays_bl.py（Workbench）",
                    "houdini": "Houdini Indie 22.0.429 hython（候補を読んで見せるシーンだけ。形は作らない）"},
        "commands_from_repo_root": [
            "# RIDGE（全部は Unity/Build/Polish/28r01/ridge/run.json）",
            "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_build.py build Unity/Build/Polish/28r01/ridge/cand/kstarP28R01RG_a45 Unity/Build/Polish/28r01/ridge/cand/ridge_design.json",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_eval.py --out Unity/Build/Polish/28r01/ridge/eval RG=… RGlow=… P28R2rec=… A5=… R4=… Kstar_26R01=…",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_metrics.py <ridge>/final/metrics_ridge.json …",
            "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <ridge>/renders RG=<gwb>,P28R2rec=<gwb>,A5=<gwb>,RGlow=<gwb> views=all",
            "blender … --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- turntable <gwb> <ridge>/renders/turntable_<label>.mp4 <ridge>/renders/turntable_<label>",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_fig.py <ridge>; py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_record.py <ridge> <start> <end> <ridge>/final/eye_verdict.json",
            "# SHOULDER（全部は Unity/Build/Polish/28r01/shoulder/final/run.json）",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_build.py <sd>/cand/kstarP28R01SH_a45 <sd>/cand/shoulder_design.json",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_check.py <sd>/final/check_painting_unchanged.json <sd>/cand/kstarP28R01SH_a45_rows.npz",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_freedom.py <sd>/final/silhouette_freedom.json <sd>/cand/kstarP28R01SH_a45_rows.npz",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_eval.py --out <sd>/final/eval P28R01SH=… P28R2rec=… R4=… Kstar_26R01=…",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_fig.py <sd>; py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_shoulder_record.py <sd> <start> <end> fig",
            "# 評審（Git 対象外の Unity/Build/Polish/28r01/_judge/。同じカメラの並べ図 sheet.py・tt.py、数値 numbers/jn_all.py・jn_extra.py・jn_extra2.py）",
            "# 記録（この run.json を書いた命令）",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28r01_record.py all --start %s --end %s" % (start, end),
        ],
        "code_sha256": {rel(p): sha(p) for p in code if os.path.isfile(p)},
        "inputs_sha256": {rel(p): sha(p) for p in inputs if os.path.isfile(p)},
        "houdini_scenes_not_committed_sha256": {rel(p): sha(p) for p in hip if os.path.isfile(p)},
        "outputs_sha256": {rel(p): sha(p) for p in outputs if os.path.isfile(p)},
        "reference_model": {
            "path": "G:\\research\\model\\wave_repair_zbrush2.obj（他者の展示作品のスキャン。作者・所蔵は未確認）",
            "expected_sha256": "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40",
            "use_ja": "評価器 kh_eval.py の F13 と量感の比べの数値だけ。SHA-256 を照合した一時キャッシュで読み、終わりに消した（RIDGE 4 回、SHOULDER 2 回。下の 2 つの記録）。生成器は読まない（F13-1）。この記録の道具と評審の数値の道具は読まない。複製していない。参照モデルを描いた画像はない。",
            "deleted_caches_logs": [rel(os.path.join(B, "ridge", "_tmp", "deleted_caches_sha256.txt")), rel(os.path.join(B, "shoulder", "_tmp", "deleted_caches_sha256.txt"))],
            "ref_cache_dirs_empty": all(len(os.listdir(os.path.join(B, x, "_tmp", "ref_cache"))) == 0 for x in ("ridge", "shoulder")),
        },
        "forbidden_paths_touched": "なし（旧試作・G:\\research の禁止の場所は読まず、一覧も取っていない。find / のような全体をたどる命令は使っていない）",
        "git_writes": "なし（add・commit・push をしていない）",
        "note_ja": "Unity の描画・動きの当て直し・焼き込みはしていない。HMD 実機の結果ではない。利用者は見ていない。",
    }
    json.dump(R, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    args = sys.argv[1:]
    what = args[0] if args else "all"
    start = args[args.index("--start") + 1] if "--start" in args else "2026-10-01T10:09"
    end = args[args.index("--end") + 1] if "--end" in args else datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    os.makedirs(EV, exist_ok=True)
    extra_p = os.path.join(B, "record", "record_extra.json")
    os.makedirs(os.path.dirname(extra_p), exist_ok=True)
    extra = json.load(open(extra_p, encoding="utf-8")) if os.path.isfile(extra_p) else {}
    outs = []
    if what in ("all", "sheets"):
        diff = {}
        diff.update(sheet_views(
            ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight"], os.path.join(EV, "fig_p28r01_ba_back65_back90.png"),
            "後ろ 65°・その拡大・真後ろ：ドームは消えていない",
            ["列：左 P28R2rec（採用のまま）、中 RIDGE、右 SHOULDER。同じカメラ・同じ t*。粘土（Blender Workbench）で、形だけを見る。",
             "RIDGE：真後ろでは中ほどの丸い頂が消え、原画の頂の高さからほぼ平らに続いて奥へ上る稜になった。P28R2rec の c ≈ 0 の縦の溝（深さ 1.73 m）は 0.13 m に浅くなった。後ろ 65° では、縦の襞のある大きな頭巾のままで、頭巾の頂が奥の端の尖った角へ移っただけ。",
             "SHOULDER：頭巾の頭（中ほどの丸い頂）は P28R2rec と同じ。奥の端の縦の壁が右下へ長い斜面になった。真後ろの丸い山の輪郭は同じ。",
             "判定：どちらもドームを消していない。P28R2rec のまま。"]))
        diff.update(sheet_views(
            ["b115_back_minus_c", "v5_back_three_quarter", "v6_top_down"], os.path.join(EV, "fig_p28r01_ba_back115_v5_top.png"),
            "−c 側の後ろ・後ろ斜め・真上",
            ["RIDGE：−c 側の後ろ（b115）では、奥の端が高く丸い冠になる。ドームが消えたのではなく、奥へ動いた。真上（v6）は P28R2rec に近い。",
             "SHOULDER：−c 側の後ろで、左下の裾へ長い斜面が伸びる。真上では奥の端が後ろへ長く引かれた鰭になる（平面の弓なり 0.5H0 で 4.34 → 7.37 m）。Q21 で利用者が受け入れないとした「真上から見た右側の後ろへ引かれたふくらみ」と同じ種類。",
             "差の画素は、どれかの色の値が 24 を超えて違う画素（描画 1100×1000 の読み）。"]))
        diff.update(sheet_views(
            ["v4_true_side_perp_crest_front", "v7_user6_az330_el10", "v8_user7_az290_el5"], os.path.join(EV, "fig_p28r01_ba_side_user_views.png"),
            "正面の真横と、原画視点に近い利用者の視点",
            ["RIDGE：v7（az330 el10）で唇の頂の奥に小さな瘤（上げた稜の頂）が見える。v8（az290 el5）で頂の輪郭が二つの山になる。v4（正面の真横）で奥の端の頂が角ばる。拡大は fig_p28r01_zoom_ridge_side_effects.png。",
             "SHOULDER：v4・v7 は P28R2rec と画素まで同じ。v8 では頂の後ろに長い斜面が出る。",
             "どちらも、原画視点では見えない所だけを動かしたので、ほかの視点で新しい形が見える。"]))
        diff.update(sheet_views(
            ["v1_painting", "v2_seat", "v9_user8_az030_el25"], os.path.join(EV, "fig_p28r01_painting_seat_unchanged.png"),
            "原画視点と座席は 3 つとも同じ",
            ["原画視点（v1）と座席（v2）の粘土は、3 つとも画素まで同じ（差 0 画素）。numpy の z バッファー（3840×2160）でも、見える三角形の違い 0 画素、奥行きの差の最大 0.24 mm（RIDGE）・0（SHOULDER）。座席の目と、頭を ±0.5 m 動かした 3 つの目でも、輪郭の画素の増減 0。",
             "このため、原画視点の関門（78・130・131・132・72）と b区域・船・134・267 の値は仕上げ28 の P28R2rec のまま。",
             "v9（az030 el25）では RIDGE の上げた稜が見え、SHOULDER は奥の端の右下が変わる。"]))
        tt = {}
        tt.update(sheet_turntable([120, 140, 160], os.path.join(EV, "fig_p28r01_ba_turntable_f120_f160.png")))
        tt.update(sheet_turntable([180, 200, 220], os.path.join(EV, "fig_p28r01_ba_turntable_f180_f220.png")))
        boxes = sheet_zoom(["v7_user6_az330_el10", "v8_user7_az290_el5", "v4_true_side_perp_crest_front"], os.path.join(EV, "fig_p28r01_zoom_ridge_side_effects.png"))
        extra["diff"] = {"threshold": "どれかの色の値の差 > %d" % DIFF_T, "views_1100x1000": diff, "turntable_1280x720": tt, "zoom_boxes": boxes}
    if what in ("all", "hc"):
        extra["hc"] = hc_figure(os.path.join(EV, "fig_p28r01_crest_height_freedom.png"))
    if what in ("all", "video"):
        extra["video"] = video(os.path.join(EV, "clay_turntable_P28R2rec_RIDGE_SHOULDER.mp4"))
    json.dump(extra, open(extra_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if what in ("all", "metrics"):
        metrics(os.path.join(EV, "metrics.json"), extra)
    if what in ("all", "run"):
        outs = sorted(glob.glob(os.path.join(EV, "*.png"))) + sorted(glob.glob(os.path.join(EV, "*.mp4"))) + [os.path.join(EV, "metrics.json")]
        run_json(os.path.join(EV, "run.json"), start, end, outs)
    print(json.dumps({k: (v if k != "diff" else "…") for k, v in extra.items()}, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
