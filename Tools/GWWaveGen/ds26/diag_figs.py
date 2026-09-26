# -*- coding: utf-8 -*-
"""診断の図（PIL だけ）。diag_measure.py の出力と、主断面の再生（keypose の Catmull-Rom）から描く。
使い方（リポジトリの根で）: py -3.10 -B Tools/GWWaveGen/ds26/diag_figs.py
入力：Unity/Build/Design/26/diag/（diag_measure.py の出力）。図は Docs/Evidence/Design/26/diag_f1〜f4_*.png に書く。
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import ds26_paths as DP  # noqa: E402
REPO, OUT = DP.REPO, DP.OUT_DIAG
FIG = DP.outdir(DP.EVID)
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
import af30_formation as F30  # noqa: E402

FONT = "C:/Windows/Fonts/YuGothM.ttc"
FONTB = "C:/Windows/Fonts/YuGothB.ttc"


def font(sz, bold=False):
    return ImageFont.truetype(FONTB if bold else FONT, sz)


R = json.load(open(os.path.join(OUT, "diag_measure.json"), encoding="utf-8"))
Z = np.load(os.path.join(OUT, "diag_sections.npz"))
G = 9.81
C_REF = 20.6   # Draupner 型（論文）を主断面の頂 20.8 m へ Froude で直した位相速度の目安
C_MIN = 8.1    # K* の足跡 20.9 m を半波長とみなした深水の位相速度（下限の目安）


class Axes:
    def __init__(self, img, box, xr, yr, title="", xlabel="", ylabel="", grid=True, xt=None, yt=None, fs=18):
        self.d = ImageDraw.Draw(img)
        self.box = box
        self.xr, self.yr = xr, yr
        x0, y0, x1, y1 = box
        d = self.d
        d.rectangle(box, outline=(90, 90, 90), width=1)
        f = font(fs - 3)
        if xt is None:
            xt = nice_ticks(*xr)
        if yt is None:
            yt = nice_ticks(*yr)
        for v in xt:
            X = self.X(v)
            if grid:
                d.line([(X, y0), (X, y1)], fill=(228, 228, 228))
            d.line([(X, y1), (X, y1 + 5)], fill=(90, 90, 90))
            s = fmt(v)
            w = d.textlength(s, font=f)
            d.text((X - w / 2, y1 + 7), s, fill=(40, 40, 40), font=f)
        for v in yt:
            Y = self.Y(v)
            if grid:
                d.line([(x0, Y), (x1, Y)], fill=(228, 228, 228))
            d.line([(x0 - 5, Y), (x0, Y)], fill=(90, 90, 90))
            s = fmt(v)
            w = d.textlength(s, font=f)
            d.text((x0 - 8 - w, Y - (fs - 3) * 0.6), s, fill=(40, 40, 40), font=f)
        d.rectangle(box, outline=(90, 90, 90), width=1)
        if title:
            d.text((x0, y0 - fs - 8), title, fill=(0, 0, 0), font=font(fs, True))
        if xlabel:
            w = d.textlength(xlabel, font=font(fs - 2))
            d.text(((x0 + x1) / 2 - w / 2, y1 + fs + 8), xlabel, fill=(30, 30, 30), font=font(fs - 2))
        if ylabel:
            tmp = Image.new("RGBA", (int(d.textlength(ylabel, font=font(fs - 2))) + 4, fs + 6), (255, 255, 255, 0))
            ImageDraw.Draw(tmp).text((2, 0), ylabel, fill=(30, 30, 30), font=font(fs - 2))
            tmp = tmp.rotate(90, expand=True)
            img.paste(tmp, (int(x0 - 70 - tmp.size[0] / 2 + 10), int((y0 + y1) / 2 - tmp.size[1] / 2)), tmp)

    def X(self, v):
        x0, _, x1, _ = self.box
        return x0 + (v - self.xr[0]) / (self.xr[1] - self.xr[0]) * (x1 - x0)

    def Y(self, v):
        _, y0, _, y1 = self.box
        return y1 - (v - self.yr[0]) / (self.yr[1] - self.yr[0]) * (y1 - y0)

    def inside(self, x, y):
        return self.xr[0] <= x <= self.xr[1] and self.yr[0] <= y <= self.yr[1]

    def line(self, xs, ys, col, w=2, dash=None, clip=True):
        pts = []
        segs = []
        for x, y in zip(xs, ys):
            if not (np.isfinite(x) and np.isfinite(y)) or (clip and not self.inside(x, y)):
                if len(pts) > 1:
                    segs.append(pts)
                pts = []
                continue
            pts.append((self.X(x), self.Y(y)))
        if len(pts) > 1:
            segs.append(pts)
        for s in segs:
            if dash:
                draw_dashed(self.d, s, col, w, dash)
            else:
                self.d.line(s, fill=col, width=w, joint="curve")

    def dot(self, x, y, col, r=4):
        if self.inside(x, y):
            X, Y = self.X(x), self.Y(y)
            self.d.ellipse([X - r, Y - r, X + r, Y + r], fill=col)

    def vline(self, x, col, w=1, dash=(6, 5), label=None, fs=15, ypos=0.02):
        if self.xr[0] <= x <= self.xr[1]:
            X = self.X(x)
            draw_dashed(self.d, [(X, self.box[1]), (X, self.box[3])], col, w, dash) if dash else self.d.line([(X, self.box[1]), (X, self.box[3])], fill=col, width=w)
            if label:
                self.d.text((X + 3, self.box[1] + (self.box[3] - self.box[1]) * ypos), label, fill=col, font=font(fs))

    def hline(self, y, col, w=1, dash=(6, 5), label=None, fs=15, xpos=0.01):
        if self.yr[0] <= y <= self.yr[1]:
            Y = self.Y(y)
            draw_dashed(self.d, [(self.box[0], Y), (self.box[2], Y)], col, w, dash) if dash else self.d.line([(self.box[0], Y), (self.box[2], Y)], fill=col, width=w)
            if label:
                self.d.text((self.box[0] + (self.box[2] - self.box[0]) * xpos, Y - fs - 3), label, fill=col, font=font(fs))

    def text(self, x, y, s, col=(0, 0, 0), fs=15, bold=False):
        self.d.text((self.X(x), self.Y(y)), s, fill=col, font=font(fs, bold))

    def span(self, xa, xb, col):
        Xa, Xb = self.X(max(xa, self.xr[0])), self.X(min(xb, self.xr[1]))
        self.d.rectangle([Xa, self.box[1] + 1, Xb, self.box[3] - 1], fill=col)

    def legend(self, items, pos=(0.01, 0.03), fs=15):
        x = self.box[0] + (self.box[2] - self.box[0]) * pos[0] + 6
        y = self.box[1] + (self.box[3] - self.box[1]) * pos[1]
        for lab, col, dash in items:
            if dash:
                draw_dashed(self.d, [(x, y + fs * 0.6), (x + 30, y + fs * 0.6)], col, 3, dash)
            else:
                self.d.line([(x, y + fs * 0.6), (x + 30, y + fs * 0.6)], fill=col, width=3)
            self.d.text((x + 36, y), lab, fill=(20, 20, 20), font=font(fs))
            y += fs + 6


def draw_dashed(d, pts, col, w, dash):
    on, off = dash
    acc = 0.0
    draw = True
    for (xa, ya), (xb, yb) in zip(pts[:-1], pts[1:]):
        L = math.hypot(xb - xa, yb - ya)
        s = 0.0
        while s < L:
            seg = (on if draw else off) - acc
            e = min(L, s + seg)
            if draw:
                d.line([(xa + (xb - xa) * s / L, ya + (yb - ya) * s / L), (xa + (xb - xa) * e / L, ya + (yb - ya) * e / L)], fill=col, width=w)
            acc += e - s
            if acc >= (on if draw else off) - 1e-9:
                acc = 0.0
                draw = not draw
            s = e


def nice_ticks(a, b, n=6):
    span = b - a
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    s = math.ceil(a / step) * step
    out = []
    while s <= b + 1e-9:
        out.append(round(s, 10))
        s += step
    return out


def fmt(v):
    return ("%d" % v) if abs(v - round(v)) < 1e-9 else ("%g" % v)


def arrow(d, p, q, col, w=2, hl=9):
    d.line([p, q], fill=col, width=w)
    ang = math.atan2(q[1] - p[1], q[0] - p[0])
    L = math.hypot(q[0] - p[0], q[1] - p[1])
    if L < 3:
        return
    for s in (+1, -1):
        a2 = ang + math.pi + s * 0.45
        d.line([q, (q[0] + hl * math.cos(a2), q[1] + hl * math.sin(a2))], fill=col, width=w)


def lerp_col(c0, c1, f):
    return tuple(int(round(a + (b - a) * f)) for a, b in zip(c0, c1))


ms = R["main_series"]
t = np.array(ms["t"])
kin = R["kinematics_240hz_main_row"]
t2 = np.array(kin["t"])
kf = R["kstar"]
seat_a, seat_y = 16.57, 1.83
ev = {"t0": 2.0, "phi60": 6.77, "phi90": 8.37, "wall90": 8.83, "ovh": 9.32, "apex": 9.60, "tstar": 12.0}

# ================================================================ 図1：主断面の動きと唇先の運動学
W, H = 2200, 1150
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((30, 18), "図1　主断面（行 159、c = 0 m）の再生（16 ビット keypose の Catmull-Rom）：その場で育ち、唇が伸びて曲がる", fill=(0, 0, 0), font=font(26, True))
ax = Axes(img, (110, 110, 1330, 1030), (-22, 26), (-1, 26), title="断面の形（2.5〜12 s を 0.5 s おき、淡→濃）、黒太線 = K*（t* = 12 s）",
          xlabel="a：進行方向の距離 [m]（原点は K* の断面原点）", ylabel="y：静水面からの高さ [m]", fs=19)
keys = sorted([k for k in Z.files if k.startswith("t") and k[1:2].isdigit()], key=lambda s: float(s[1:]))
keys = [k for k in keys if float(k[1:]) >= 2.5]
for i, k in enumerate(keys):
    S = Z[k][0]
    f = i / max(len(keys) - 1, 1)
    ax.line(S[:, 0], S[:, 1], lerp_col((170, 205, 235), (20, 60, 130), f), 2)
ax.line(Z["AK"][0], Z["YK"][0], (0, 0, 0), 4)
# 唇先の軌跡（列 200）と頂の軌跡
tip = Z["tip_all"][:, 159]
m = (t >= 2.0) & (t <= 12.0)
ax.line(tip[m, 0], tip[m, 1], (220, 30, 30), 3)
for tt in range(3, 13):
    i = int(np.argmin(np.abs(t - tt)))
    ax.dot(tip[i, 0], tip[i, 1], (220, 30, 30), 5)
    ax.text(tip[i, 0] + 0.3, tip[i, 1] + 0.9, "%d s" % tt, (200, 20, 20), 14)
ca, cy = np.array(ms["crest_a"]), np.array(ms["crest_y"])
m2 = (t >= 3.0) & (t <= 12.0)
ax.line(ca[m2], cy[m2], (0, 150, 60), 3)
ax.dot(ca[np.argmin(abs(t - 3))], cy[np.argmin(abs(t - 3))], (0, 150, 60), 5)
ax.dot(ca[-1], cy[-1], (0, 150, 60), 6)
# 重力の放物線（頂点 9.6 s、実際の水平の速さ 1.83 m/s で投げたとき）
a_ap, y_ap, vx = 8.149, 15.079, 1.83
aa = np.linspace(a_ap, a_ap + 2.6, 60)
yy = y_ap - G / (2 * vx ** 2) * (aa - a_ap) ** 2
ax.line(aa, yy, (240, 140, 0), 3, dash=(10, 6))
tt_ = np.array([0.25, 0.5, 0.77])
for q in tt_:
    ax.dot(a_ap + vx * q, y_ap - 0.5 * G * q * q, (240, 140, 0), 4)
ax.text(12.6, 9.2, "実時間の重力なら 0.77 s で 2.87 m 落ちる\n（水平の速さ 1.83 m/s のまま、1.4 m 進む間）", (200, 110, 0), 15)
ax.text(11.0, 18.6, "rig の唇先：頂点 9.6 s → t* まで 2.4 s で 2.87 m\n（水平に 3.5 m、最後は上向きに減速して止まる）", (200, 20, 20), 15)
# 1 s の間に物理的な波が進む距離
x0, yb = -20.5, 24.3
ax.d.line([(ax.X(x0), ax.Y(yb)), (ax.X(x0 + C_REF), ax.Y(yb))], fill=(120, 0, 160), width=5)
ax.text(x0, yb - 0.4, "物理的な波の頂が 1 s で進む距離（c ≈ 20.6 m/s）", (120, 0, 160), 16)
ax.d.line([(ax.X(x0), ax.Y(yb - 2.3)), (ax.X(x0 + 0.53), ax.Y(yb - 2.3))], fill=(0, 150, 60), width=5)
ax.text(x0 + 0.8, yb - 1.8, "rig の頂の 3〜12 s の平均の進み 1 s ぶん（0.53 m）", (0, 130, 50), 16)
ax.dot(seat_a, seat_y, (0, 0, 0), 7)
ax.text(seat_a - 3.2, seat_y + 2.2, "座席 v1（断面へ投影）", (0, 0, 0), 15)
ax.legend([("唇先（列 200）の軌跡・1 s おき", (220, 30, 30), None), ("波頂（最高点）の軌跡 3→12 s", (0, 150, 60), None),
           ("重力の放物線（比較）", (240, 140, 0), (10, 6))], pos=(0.01, 0.27), fs=16)
# 右：唇に沿った速さ（頂の列 90 → 唇先 200）
cols = kin["cols"]
cs = np.array(kin["col_speed"])
ax2 = Axes(img, (1480, 110, 2150, 540), (0, 1), (0, 4), title="唇に沿った速さ（主断面、240 Hz の中心差分）",
           xlabel="唇の位置：頂の列 90（0）→ 唇先の列 200（1）", ylabel="速さ [m/s]", fs=19)
xs = (np.array(cols) - 90) / 110.0
pal = [(40, 40, 200), (0, 140, 200), (0, 160, 80), (220, 120, 0), (200, 0, 0), (120, 0, 120)]
for (tt, col) in zip([9.6, 10.0, 10.6, 11.0, 11.6, 11.9], pal):
    i = int(np.argmin(np.abs(t2 - tt)))
    ax2.line(xs, cs[i], col, 3)
    for x_, y_ in zip(xs, cs[i]):
        ax2.dot(x_, y_, col, 4)
ax2.legend([("%.1f s" % tt, col, None) for tt, col in zip([9.6, 10.0, 10.6, 11.0, 11.6, 11.9], pal)], pos=(0.02, 0.03), fs=15)
ax2.text(0.25, 3.7, "唇の中ほどが止まり（11 s で 0.09 m/s）、\n唇先だけが回る＝指が曲がる動き", (0, 0, 0), 15)
d.text((1480, 600), "投げ出された水なら（物理の目安）", fill=(0, 0, 0), font=font(19, True))
lines = [
    "・波頂そのものが位相速度 c（この高さで約 18〜21 m/s）で前へ進み、",
    "  唇は頂に運ばれながら、頂より速く（唇先 ≈ 1〜1.3c）飛び出す。",
    "・唇の根から唇先へ速さは増える（中ほどで止まる所はない）。",
    "・唇先は放物線の上を下向きに g で加速し続け、空中で止まらない。",
    "rig の値（主断面）",
    "・唇先の最大 3.7 m/s（7.65 s）、頂点後は 1.8〜2.8 m/s。",
    "・頂点（9.6 s）→ t*：縦の加速度の平均 −0.04 m/s²（g = 9.81）。",
    "  11.2〜12.0 s は平均 +1.85 m/s²（上向き、最大 +4.2）＝重力に逆らう減速。",
    "・頂は 9.8〜12 s に 0.6 m 後ろへ戻る（前傾 8° → 0°）。",
    "・唇の弧長（列 90→200）は 9→12 s で 7.35 → 15.12 m（+7.8 m、2.6 m/s）",
    "  ＝ 根が止まったまま伸びる（角の成長）。",
]
y = 640
for s in lines:
    bold = s.startswith("rig")
    d.text((1480, y), s, fill=(0, 0, 0), font=font(17, bold))
    y += 30
img.save(os.path.join(FIG, "diag_f1_section_kinematics.png"))

# ================================================================ 図2：時系列
W, H = 2000, 2350
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((30, 14), "図2　形成の時系列（再生される keypose、60 Hz。主断面 = 行 159、c = 0 m）", fill=(0, 0, 0), font=font(26, True))
L, Rr = 150, 1850
panels = []
ph = 280
gap = 95
top = 100
tick_t = list(range(0, 18))


def mk(i, yr, title, ylabel, yt=None):
    b = (L, top + i * (ph + gap), Rr, top + i * (ph + gap) + ph)
    a = Axes(img, b, (0, 17), yr, title=title, xlabel="t [s]" if i == 5 else "", ylabel=ylabel, xt=tick_t, yt=yt, fs=19)
    a.span(12.0, 17.0, (238, 238, 238))
    Axes(img, b, (0, 17), yr, xt=tick_t, yt=yt, fs=19)  # 格子を描き直す
    for k_, lab in (("t0", "形成の始まり 2 s"), ("phi90", "前面が鉛直 8.37 s"), ("apex", "唇先の頂点 9.6 s"), ("tstar", "t* 12 s（以後 5 s 静止）")):
        a.vline(ev[k_], (120, 120, 120), 1, (5, 5), lab if i == 0 else None, 14, 0.02 + 0.09 * ["t0", "phi90", "apex", "tstar"].index(k_))
    return a


gs = R["global_series"]
tg = np.array(gs["t"])
# 1 高さと体積
a1 = mk(0, (0, 26), "(1) 波頂の高さと海面より上の体積：0 から作られ、唇の区間で 23% 消える。谷（海面より下）は全区間で 0", "高さ [m] / 体積 [10³ m³]")
a1.line(t, cy, (20, 60, 160), 3)
a1.line(tg, np.array(gs["peak_crest_m"]), (120, 160, 220), 2, dash=(8, 5))
a1.line(tg, np.array(gs["volume_above_swl_m3"]) / 250.0, (200, 60, 0), 3)
a1.line(t, np.array(ms["area"]) / 10.0, (240, 150, 60), 2, dash=(8, 5))
a1.legend([("主断面の頂の高さ [m]", (20, 60, 160), None), ("全行の最高点 [m]", (120, 160, 220), (8, 5)),
           ("海面より上の体積 ÷ 250 [m³]（最大 5,784 @9.15 s → t* 4,446）", (200, 60, 0), None), ("主断面の面積 ÷ 10 [m²]（最大 251.5 → 204.4）", (240, 150, 60), (8, 5))], pos=(0.01, 0.3), fs=15)
# 2 水平位置
a2 = mk(1, (-12, 16), "(2) 水平の位置 a：頂・面積の重心・唇先はほとんど進まない（紫の線 = c 20.6 m/s・8.1 m/s で進む頂）", "a [m]")
a2.line(t[t >= 2.9], ca[t >= 2.9], (0, 150, 60), 3)
a2.line(t[t >= 2.9], np.array(ms["centroid_a"])[t >= 2.9], (0, 90, 40), 2, dash=(8, 5))
a2.line(t[t >= 2.0], np.array(ms["tip_a"])[t >= 2.0], (220, 30, 30), 3)
for c_, lab in ((C_REF, "c = 20.6 m/s"), (C_MIN, "c = 8.1 m/s")):
    tt_ = np.linspace(0, 17, 400)
    aa_ = ca[-1] + c_ * (tt_ - 12.0)
    a2.line(tt_, aa_, (120, 0, 160), 2, dash=(10, 6))
    yl = -10.5 if c_ > 10 else -6.0
    i = np.argmin(np.abs(aa_ - yl))
    a2.text(tt_[i] + 0.15, yl + 0.6, lab, (120, 0, 160), 14)
a2.legend([("波頂の a（3→10.6 s に +5.35 m、その後 0.6 m 戻る）", (0, 150, 60), None), ("面積の重心の a（3→12 s に +7.0 m）", (0, 90, 40), (8, 5)),
           ("唇先（列 200）の a", (220, 30, 30), None)], pos=(0.72, 0.6), fs=15)
# 3 速さ
a3 = mk(2, (0, 22), "(3) 速さ：水面の動きは最大 4 m/s 程度で、t* へ 0 まで減速する（物理の目安の帯 = 波頂の位相速度 18〜21 m/s）", "速さ [m/s]")
a3.d.rectangle([a3.X(0.01), a3.Y(21), a3.X(16.99), a3.Y(18)], fill=(236, 226, 246))
Axes(img, a3.box, (0, 17), (0, 22), xt=tick_t, fs=19)
tipv = np.array(kin["tip_v"])
a3.line(t2, np.hypot(tipv[:, 0], tipv[:, 1]), (220, 30, 30), 3)
a3.line(tg[1:], np.array(gs["speed_mean_body_mps"])[1:], (20, 60, 160), 3)
a3.line(tg[1:], np.array(gs["speed_p95_body_mps"])[1:], (120, 160, 220), 2, dash=(8, 5))
a3.text(0.3, 20.3, "波頂の位相速度の目安（Draupner 型を Froude で換算 20.6 m/s、足跡からの下限 8.1 m/s）", (120, 0, 160), 15)
a3.legend([("唇先（列 200）の速さ", (220, 30, 30), None), ("水面（y > 0.5 m）の頂点の速さの平均", (20, 60, 160), None), ("同 p95", (120, 160, 220), (8, 5))], pos=(0.01, 0.35), fs=15)
# 4 唇先の縦の加速度
acc = np.array(kin["tip_acc_box"])
a4 = mk(3, (-12, 6), "(4) 唇先の縦の加速度（key の間隔 1/15 s の箱で平滑）：頂点の後も −g にならず、最後は上向き", "a_y [m/s²]")
a4.hline(-G, (0, 0, 0), 2, (10, 6), "−g = −9.81 m/s²（投げ出された水）", 15)
a4.hline(0, (150, 150, 150), 1, None)
a4.line(t2, acc[:, 1], (220, 30, 30), 3)
a4.line(t2, acc[:, 0], (240, 160, 160), 2, dash=(6, 4))
a4.legend([("唇先の縦の加速度", (220, 30, 30), None), ("唇先の横の加速度", (240, 160, 160), (6, 4))], pos=(0.01, 0.62), fs=15)
# 5 前面の角
a5 = mk(4, (0, 180), "(5) 前面の角（水平から。90° = 鉛直、90° 超 = 張り出し）", "角 [°]", yt=[0, 30, 60, 90, 120, 150, 180])
a5.hline(90, (0, 0, 0), 1, (6, 4))
pm = np.array(ms["phi_max"]).astype(float); pm[pm < 0] = np.nan
phh = np.array(ms["phi_half"]).astype(float); phh[phh < 0] = np.nan
a5.line(t, pm, (20, 60, 160), 3)
a5.line(t, phh, (0, 150, 150), 3, dash=(8, 5))
ov = np.array(ms["overhang"]) / 20.8 * 100
a5.line(t, ov * 1.8, (200, 60, 0), 2)
a5.legend([("前面の最も急な所の角 φ_max", (20, 60, 160), None), ("0.5H の内壁の角 φ_half", (0, 150, 150), (8, 5)),
           ("張り出し ÷ H × 180（0.41H で t*）", (200, 60, 0), None)], pos=(0.01, 0.3), fs=15)
# 6 白
w = R["white"]
wt, wf = np.array(w["t"]), np.array(w["fraction"])
a6 = mk(5, (0, 1.05), "(6) 白（番号31）の出た割合（UV、終態の白 = 1）：水面が上がり始めた 2.0 s（頂の高さ 0 m）から出る", "白の割合", yt=[0, 0.25, 0.5, 0.75, 1.0])
a6.line(wt, wf, (40, 40, 40), 3)
a6.line(t, cy / 20.8, (20, 60, 160), 2, dash=(8, 5))
a6.dot(8.37, 0.552, (220, 30, 30), 7)
a6.text(8.5, 0.46, "前面が鉛直になった時（砕波の始まり）にすでに 55%", (220, 30, 30), 15)
a6.dot(4.0, 0.092, (220, 30, 30), 6)
a6.text(4.1, 0.03, "4 s：頂 1.6 m の小山で 9%", (220, 30, 30), 15)
a6.legend([("白の割合", (40, 40, 40), None), ("主断面の頂の高さ ÷ 20.8 m", (20, 60, 160), (8, 5))], pos=(0.01, 0.2), fs=15)
img.save(os.path.join(FIG, "diag_f2_timeseries.png"))

# ================================================================ 図3：時空間図（主断面の上側の包絡）
kp = json.load(open(os.path.join(REPO, "Unity/Build/ArtFirst/30/keypose/af30_keypose.json"), encoding="utf-8"))
nk, nv, nu = kp["layers"], kp["nv"], kp["nu"]
times = np.array(kp["key_times_s"])
lo, size = np.array(kp["bbox_min"]), np.array(kp["bbox_size"])
mm = np.memmap(os.path.join(REPO, "Unity/Build/ArtFirst/30/keypose/af30_pos_rgba16.bin"), dtype="<u2", mode="r", shape=(nk, nv, nu, 4))
row = np.array(mm[:, 159, :, :3]).astype(np.float64)
Xr = lo + row / 65535.0 * size
meta = json.load(open(os.path.join(REPO, "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45_meta.json"), encoding="utf-8"))
O = np.array(meta["frame"]["section_origin_world"]); tv = np.array(meta["frame"]["t_travel"])
Ak = (Xr - O) @ tv
Yk = Xr[..., 1]
ag = np.linspace(-45, 30, 751)
tt3 = np.arange(0, 17.0001, 1 / 30)
env = np.zeros((len(tt3), len(ag)))
for i, tq in enumerate(tt3):
    idx, wts = F30.cr_weights(times, tq)
    A = sum(wts[q] * Ak[idx[q]] for q in range(4) if wts[q] != 0)
    Y = sum(wts[q] * Yk[idx[q]] for q in range(4) if wts[q] != 0)
    e = np.zeros(len(ag))
    for j in range(len(A) - 1):
        a0, a1_ = A[j], A[j + 1]
        if abs(a1_ - a0) < 1e-9:
            continue
        lo_, hi_ = min(a0, a1_), max(a0, a1_)
        k0, k1 = np.searchsorted(ag, lo_), np.searchsorted(ag, hi_)
        if k1 > k0:
            f = (ag[k0:k1] - a0) / (a1_ - a0)
            e[k0:k1] = np.maximum(e[k0:k1], Y[j] + f * (Y[j + 1] - Y[j]))
    env[i] = e
W, H = 1900, 1300
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((30, 14), "図3　時空間図：主断面の水面の高さ η(a, t)（上側の包絡、再生される keypose、30 Hz）", fill=(0, 0, 0), font=font(26, True))
ax = Axes(img, (130, 110, 1330, 1180), (-45, 30), (0, 17), title="色 = 高さ（0 m 白 → 23 m 濃い藍）。物理的な波の頂は右上がりの線に沿って進む",
          xlabel="a：進行方向 [m]", ylabel="t [s]", fs=19, yt=list(range(0, 18)))
x0, y0, x1, y1 = ax.box
hm = np.clip(env / 23.0, 0, 1)
rgb = np.zeros(hm.shape + (3,), np.uint8)
c0 = np.array([255, 255, 255.]); c1 = np.array([150, 190, 230.]); c2 = np.array([15, 40, 110.])
f = hm[..., None]
col = np.where(f < 0.4, c0 + (c1 - c0) * (f / 0.4), c1 + (c2 - c1) * ((f - 0.4) / 0.6))
rgb = col.astype(np.uint8)[::-1]  # t が上へ
him = Image.fromarray(rgb).resize((int(x1 - x0), int(y1 - y0)), Image.NEAREST)
img.paste(him, (int(x0), int(y0)))
ax = Axes(img, (130, 110, 1330, 1180), (-45, 30), (0, 17), fs=19, yt=list(range(0, 18)), grid=False)
ax.span(-45, -44.9, (0, 0, 0))
ax.line(ca[t >= 3], t[t >= 3], (0, 170, 60), 3)
tip = Z["tip_all"][:, 159]
ax.line(tip[t >= 2, 0], t[t >= 2], (220, 30, 30), 3)
for c_, lab in ((C_REF, "c = 20.6 m/s"), (C_MIN, "c = 8.1 m/s")):
    tq = np.linspace(0, 12, 200)
    aq = ca[-1] + c_ * (tq - 12)
    ax.line(aq, tq, (120, 0, 160), 3, dash=(12, 7))
    ax.text(-39.0 if c_ > 10 else -23.0, 9.75 if c_ > 10 else 8.6, lab, (120, 0, 160), 17, True)
ax.hline(12, (0, 0, 0), 2, (8, 6), "t* 12 s（以後静止）", 16, 0.02)
ax.hline(2, (0, 0, 0), 1, (8, 6), "形成の始まり 2 s", 16, 0.02)
ax.legend([("波頂の軌跡（rig）", (0, 170, 60), None), ("唇先（列 200）の軌跡", (220, 30, 30), None), ("同じ t* に同じ所へ着く物理的な頂（位相速度 c）", (120, 0, 160), (12, 7))], pos=(0.01, 0.2), fs=16)
d.text((1370, 130), "読み方", fill=(0, 0, 0), font=font(21, True))
lines = [
    "・rig の波は、ほぼ同じ a（−5 → 0 m）に立ったまま",
    "  10 s かけて高くなる（色の帯がほぼ縦）。",
    "・進む波なら、帯は右上がりに傾く。",
    "  c = 20.6 m/s なら t* の 10 s 前に頂は",
    "  206 m 後ろ（図の外）にあり、",
    "  1 s で 21 m ずつ近づく。",
    "・足跡の平行移動は t* までに 4 m（rig の設定）。",
    "  頂の 3〜12 s の平均の進みは 0.53 m/s",
    "  （c の 2.6%、下限 8.1 m/s の 6.5%）。",
    "・前後の海は全区間で平ら（η = 0）。",
    "  谷がないので、海面より上の水は",
    "  どこからも来ていない（図2 (1)）。",
]
y = 175
for s in lines:
    d.text((1370, y), s, fill=(0, 0, 0), font=font(18))
    y += 34
img.save(os.path.join(FIG, "diag_f3_spacetime.png"))

# ================================================================ 図4：波峰線に沿った同時性
rs = R["rows"]
c = np.array(rs["c_m"]); Hf = np.array(rs["H_final_m"])
t50, t90, tp90 = np.array(rs["t50"]), np.array(rs["t90"]), np.array(rs["t_phi90"])
curl = np.array(rs["curl_rows"])
W, H = 1900, 1050
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((30, 14), "図4　波峰線に沿った時刻：全行が同じ時刻に育つ（行ごとの進みの表が同じ）", fill=(0, 0, 0), font=font(26, True))
ax = Axes(img, (130, 110, 1330, 900), (-40, 16), (5, 13), title="行ごとの事象の時刻（頂の高さ > 3 m の 175 行）",
          xlabel="c：波峰線方向の位置 [m]（負 = 手前の肩、+5.5 m = 最も高い行）", ylabel="t [s]", fs=19)
big = Hf > 3
for x_, y_ in zip(c[big], t50[big]):
    ax.dot(x_, y_, (20, 60, 160), 3)
for x_, y_ in zip(c[big], t90[big]):
    ax.dot(x_, y_, (0, 150, 150), 3)
for x_, y_ in zip(c[curl], tp90[curl]):
    ax.dot(x_, y_, (220, 30, 30), 4)
ax.hline(12, (0, 0, 0), 1, (6, 4), "t*", 15)
ax.vline(5.5, (120, 120, 120), 1, (6, 4), "最も高い行 c = 5.5 m（23.3 m）", 15, 0.9)
ax2 = Axes(img, (130, 110, 1330, 900), (-40, 16), (0, 26), grid=False, xt=[], yt=[])
ax2.line(c, Hf, (160, 160, 160), 2)
ax.legend([("頂の高さが最終の 50% に届く時刻（全行 6.73 s、標準偏差 0）", (20, 60, 160), None), ("同 90%（9.38〜9.40 s）", (0, 150, 150), None),
           ("前面が鉛直になる時刻（巻きのある 133 行、6.2〜8.6 s）", (220, 30, 30), None), ("最終の頂の高さ（右の目盛 0〜26 m、灰）", (160, 160, 160), None)], pos=(0.01, 0.02), fs=15)
d.text((1370, 130), "読み方", fill=(0, 0, 0), font=font(21, True))
lines = [
    "・波峰線 42.6 m にわたって、全行が",
    "  同じ時刻に同じ割合で高くなる。",
    "  rig の進みの表 u(t) が行によらない。",
    "・鉛直になる時刻は行の形の違いだけで",
    "  ばらつき、低い手前の肩（c ≈ −29 m、",
    "  6.2 s）が先、最も高い所（8.6 s）が後。",
    "  （時刻と高さの相関 +0.80）",
    "・物理的な期待（定性）：砕波は最も高く",
    "  急な所から始まり、低い肩へ遅れて",
    "  広がる（交差波では合流する所）。",
    "  頂の高さの成長も、群の包絡が進むので",
    "  行ごとにずれる。",
]
y = 175
for s in lines:
    d.text((1370, y), s, fill=(0, 0, 0), font=font(18))
    y += 34
img.save(os.path.join(FIG, "diag_f4_rowsync.png"))
print("figs done")
