# -*- coding: utf-8 -*-
"""美術の見本02 BACK：背が一つの山かの測り（前後）の図。py -3.10 back_chart.py <measure.json> <out.png> <base_label> <cand_label>
back_measure.py の出力を読み、1920×1080 の 6 つの小さな図にする（前 ＝ 灰の破線、後 ＝ 青の実線、同じ軸）。
py -3.10 には matplotlib がないので PIL で描く（2 倍で描いて縮める）。
  A. 頂の高さ H(c)（シートの行の座標 c）。原画が止める行の帯。
  B. 背の等高線の位置 d(c) = −a_back（0.3・0.5・0.7 H0）。
  C. 弦（等高線の両端を結ぶ線）からの背の出っ張り（0.5・0.7 H0）。
  D. 高さごとの、入り江の深さ（上に凸な包絡との差）とへこみの深さ（水を張った深さ）。
  E. 真後ろ（b90）・後ろ 65°（b65）・−c 側の後ろ（b115）から見た輪郭の一番上（画素）。
  F. 数の表。
"""
import sys
import json

import numpy as np
from PIL import Image, ImageDraw, ImageFont

S = 2
W, H = 1920 * S, 1080 * S
SURF = (252, 252, 251); INK = (11, 11, 11); INK2 = (82, 81, 78); GRID = (228, 227, 223); AXIS = (185, 184, 179)
C_AFTER = (42, 120, 214); C_BEFORE = (141, 140, 135); BAND = (239, 238, 234)
FM = r"C:\Windows\Fonts\YuGothM.ttc"; FB = r"C:\Windows\Fonts\YuGothB.ttc"


def F(sz, b=False):
    return ImageFont.truetype(FB if b else FM, int(sz * S))


class Ax:
    def __init__(self, dr, box, xlim, ylim, title, xlabel="", ylabel="", yticks=True, xticks=True):
        self.dr = dr
        x0, y0, x1, y1 = [v * S for v in box]
        self.title = title
        dr.text((x0, y0), title, fill=INK, font=F(15, True))
        self.L, self.T, self.R, self.B = x0 + 62 * S, y0 + 34 * S, x1 - 10 * S, y1 - 46 * S
        self.xlim, self.ylim = xlim, ylim
        for t in (self.ticks(*xlim) if xticks else []):
            X = self.px(t, ylim[0])[0]
            dr.line([(X, self.T), (X, self.B)], fill=GRID, width=S)
            dr.text((X, self.B + 6 * S), self.fmt(t), fill=INK2, font=F(11), anchor="ma")
        if yticks:
            for t in self.ticks(*ylim):
                Y = self.px(xlim[0], t)[1]
                dr.line([(self.L, Y), (self.R, Y)], fill=GRID, width=S)
                dr.text((self.L - 6 * S, Y), self.fmt(t), fill=INK2, font=F(11), anchor="rm")
        dr.line([(self.L, self.B), (self.R, self.B)], fill=AXIS, width=S)
        dr.line([(self.L, self.T), (self.L, self.B)], fill=AXIS, width=S)
        if xlabel:
            dr.text(((self.L + self.R) / 2, self.B + 24 * S), xlabel, fill=INK2, font=F(11.5), anchor="ma")
        if ylabel:
            dr.text((x0, self.T - 4 * S), ylabel, fill=INK2, font=F(11.5), anchor="ld")

    @staticmethod
    def ticks(a, b):
        span = b - a
        for st in (0.1, 0.2, 0.5, 1, 2, 2.5, 5, 10, 20, 50, 100, 200, 250, 500):
            if span / st <= 7:
                break
        t0 = np.ceil(a / st) * st
        return [round(v, 6) for v in np.arange(t0, b + 1e-9, st)]

    @staticmethod
    def fmt(v):
        return ("%d" % v) if abs(v - round(v)) < 1e-6 else ("%.1f" % v)

    def px(self, x, y):
        X = self.L + (x - self.xlim[0]) / (self.xlim[1] - self.xlim[0]) * (self.R - self.L)
        Y = self.B - (y - self.ylim[0]) / (self.ylim[1] - self.ylim[0]) * (self.B - self.T)
        return X, Y

    def band(self, xa, xb, col=BAND):
        Xa = self.px(max(xa, self.xlim[0]), 0)[0]; Xb = self.px(min(xb, self.xlim[1]), 0)[0]
        self.dr.rectangle([Xa, self.T, Xb, self.B], fill=col)

    def line(self, x, y, col, width=2.0, dash=None):
        x = np.asarray(x, float); y = np.asarray(y, float)
        ok = np.isfinite(x) & np.isfinite(y) & (x >= self.xlim[0]) & (x <= self.xlim[1])
        P = [self.px(a, b) for a, b in zip(x[ok], y[ok])]
        if len(P) < 2:
            return
        if not dash:
            self.dr.line(P, fill=col, width=int(width * S), joint="curve")
            return
        on, off = dash[0] * S, dash[1] * S
        acc, draw = 0.0, True
        for p, q in zip(P[:-1], P[1:]):
            seg = np.hypot(q[0] - p[0], q[1] - p[1])
            t = 0.0
            while t < seg:
                lim = on if draw else off
                step = min(lim - acc, seg - t)
                if draw:
                    a = (p[0] + (q[0] - p[0]) * t / seg, p[1] + (q[1] - p[1]) * t / seg)
                    b = (p[0] + (q[0] - p[0]) * (t + step) / seg, p[1] + (q[1] - p[1]) * (t + step) / seg)
                    self.dr.line([a, b], fill=col, width=int(width * S))
                t += step; acc += step
                if acc >= lim - 1e-9:
                    acc, draw = 0.0, not draw

    def dot(self, x, y, col, r=4.5, square=False):
        X, Y = self.px(x, y)
        bb = [X - r * S, Y - r * S, X + r * S, Y + r * S]
        if square:
            self.dr.rectangle(bb, fill=col, outline=SURF, width=S)
        else:
            self.dr.ellipse(bb, fill=col, outline=SURF, width=2 * S)

    def text(self, x, y, s, col=INK2, size=11, anchor="la", dx=0, dy=0, bold=False):
        X, Y = self.px(x, y)
        self.dr.text((X + dx * S, Y + dy * S), s, fill=col, font=F(size, bold), anchor=anchor)


def legend(dr, x, y, items):
    for k, (lab, col, dash) in enumerate(items):
        yy = (y + k * 20) * S
        xx = x * S
        if dash:
            for i in range(0, 26, 9):
                dr.line([(xx + i * S, yy), (xx + min(i + 5, 26) * S, yy)], fill=col, width=2 * S)
        else:
            dr.line([(xx, yy), (xx + 26 * S, yy)], fill=col, width=2 * S)
        dr.text((xx + 32 * S, yy), lab, fill=INK, font=F(11.5), anchor="lm")


def main():
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    out, lb, lc = sys.argv[2], sys.argv[3], sys.argv[4]
    B, Cc = m["measure"][lb], m["measure"][lc]
    img = Image.new("RGB", (W, H), SURF)
    dr = ImageDraw.Draw(img)
    dr.text((18 * S, 14 * S), "背は一つの山か（要求書 S4）：今の K*′ %s と候補 K*′ %s（t* の静止）" % (lb, lc), fill=INK, font=F(20, True))
    legend(dr, 1300, 30, [("%s（今）" % lb, C_BEFORE, True), ("%s（候補）" % lc, C_AFTER, False)])
    DASH = (7, 4)
    cols = [(18, 76, 640, 560), (650, 76, 1272, 560), (1282, 76, 1904, 560),
            (18, 590, 640, 1070), (650, 590, 1272, 1070), (1282, 590, 1904, 1070)]

    # A
    hb = B["H_profile"]; hc = Cc["H_profile"]
    cb = np.array(hb["c"]); Hb = np.array(hb["H"]); Hc = np.array(hc["H"])
    a = Ax(dr, cols[0], (-40, 16), (0, 22), "A. 頂の高さ H(c) — 変えていない（灰の帯 ＝ 原画が止める行）", "c（m、波峰線に沿う。− ＝ 原画のカメラの側）", "H（m）")
    a.band(-40, -1); a.band(9.6, 13.2)
    a.line(cb, Hb, C_BEFORE, 2.2, DASH); a.line(cb, Hc, C_AFTER, 2.0)
    k = int(np.argmax(Hc)); a.dot(cb[k], Hc[k], C_AFTER)
    a.text(cb[k], Hc[k], "最高 %.2f m（c %.1f）" % (Hc[k], cb[k]), dx=8, dy=-4, anchor="ld")
    a.text(-15.8, 11.08, "b区域の第二の波頭（へこみ 0.23 m）", dx=-8, dy=-10, anchor="rd")
    a.text(-39, 1.0, "灰と青は重なる。H(c) は c ≥ −14 で一つの山（へこみ 0）", size=11)

    # B
    a = Ax(dr, cols[1], (-15, 16), (0, 20), "B. 背の等高線の位置 d(c)（後ろへ出るほど大きい）", "c（m）", "d（m）")
    for f in ("0.30", "0.50", "0.70"):
        pb = B["levels"][f]["profile"]; pc = Cc["levels"][f]["profile"]
        a.line(pb["c"], pb["d"], C_BEFORE, 2.2, DASH); a.line(pc["c"], pc["d"], C_AFTER, 2.0)
        a.text(pc["c"][-1], pc["d"][-1], "%s H0" % f, dx=6, anchor="lm", size=10.5)
    pb = B["levels"]["0.50"]["profile"]
    yb = float(np.interp(0.6, pb["c"], pb["d"]))
    a.text(0.6, yb, "溝 c ≈ +0.4〜+2", dy=10, anchor="ma", size=11)

    # C
    a = Ax(dr, cols[2], (-15, 16), (-0.5, 6.5), "C. 弦（等高線の両端）からの背の出っ張り", "c（m）", "出っ張り（m）")
    for f in ("0.50", "0.70"):
        pb = B["levels"][f]["profile"]; pc = Cc["levels"][f]["profile"]
        a.line(pb["c"], pb["bulge"], C_BEFORE, 2.2, DASH); a.line(pc["c"], pc["bulge"], C_AFTER, 2.0)
        xq = 4.0 if f == "0.50" else 6.0
        a.text(xq, float(np.interp(xq, pc["c"], pc["bulge"])), "%s H0" % f, dy=-8, anchor="md", size=10.5, col=C_AFTER)
    a.text(-14.5, 6.2, "灰：二つの山（c ≈ −4 の肋と奥の端）の間が低い", size=11)
    a.text(-14.5, 5.75, "青：一つの山（中ほどが出て、両側へ下がる）", size=11, col=C_AFTER)

    # D
    levs = list(B["levels"].keys())
    ymax = max(max(B["levels"][k]["bay_depth_m"] for k in levs), 1.0) * 1.12
    a = Ax(dr, cols[3], (-0.5, len(levs) - 0.5), (0, ymax), "D. 高さごとの入り江（●）とへこみ（■）の深さ（c ≥ −14）", "高さ（H0 の割合）", "m", xticks=False)
    for i, k in enumerate(levs):
        X = a.px(i, 0)[0]
        dr.text((X, a.B + 6 * S), k, fill=INK2, font=F(10.5), anchor="ma")
    for M, col, dash in ((B, C_BEFORE, DASH), (Cc, C_AFTER, None)):
        bay = [M["levels"][k]["bay_depth_m"] for k in levs]
        dip = [M["levels"][k]["dip_depth_m"] for k in levs]
        a.line(range(len(levs)), bay, col, 2.0, dash)
        for i in range(len(levs)):
            a.dot(i, bay[i], col)
            a.dot(i, dip[i], col, r=3.5, square=True)
    a.text(-0.4, ymax * 0.93, "候補の入り江 0.3〜0.47 m は c ≈ −11（肩との境）の凹み", size=10.5)

    # E
    a = Ax(dr, cols[4], (250, 1450), (-330, 980), "E. 後ろから見た輪郭の一番上（画素の高さ、3 視点をずらして重ねる）", "画素の x（1280 幅の描画）", "", yticks=False)
    off = {"b65_back65_clay": 260, "b90_back_straight": 0, "b115_back_minus_c": -260}
    name = {"b90_back_straight": "真後ろ b90", "b65_back65_clay": "後ろ 65° b65", "b115_back_minus_c": "−c 側の後ろ b115"}
    for vn in ("b65_back65_clay", "b90_back_straight", "b115_back_minus_c"):
        pb = B["silhouette_views"][vn]["profile"]; pc = Cc["silhouette_views"][vn]["profile"]
        a.line(pb["x"], np.array(pb["h_px"]) + off[vn], C_BEFORE, 2.2, DASH)
        a.line(pc["x"], np.array(pc["h_px"]) + off[vn], C_AFTER, 2.0)
        a.text(pc["x"][-1], pc["h_px"][-1] + off[vn], name[vn], dx=6, anchor="lm", size=10.5)
    a.text(260, -300, "灰の破線は青の下に重なる（頂の高さ H は変えていない）。へこみは b区域だけ", size=10.5)

    # F
    x0, y0 = cols[5][0] * S, cols[5][1] * S
    dr.text((x0, y0), "F. 数（前 → 後）", fill=INK, font=F(15, True))
    sb, sc = m["summary"][lb], m["summary"][lc]
    rows = [
        ("H(c) のへこみ c ≥ −14 ／ 全部の行", "%.3f ／ %.3f" % (sb["H_dip_hero_m"], sb["H_dip_all_m"]), "%.3f ／ %.3f m" % (sc["H_dip_hero_m"], sc["H_dip_all_m"])),
        ("H の最高の c", "%.1f" % sb["H_max_c"], "%.1f" % sc["H_max_c"]),
        ("背の等高線のへこみ（最大）", "%.2f" % sb["back_dip_max_m"], "%.3f m" % sc["back_dip_max_m"]),
        ("背の入り江（最大）", "%.2f" % sb["back_bay_max_m"], "%.2f m" % sc["back_bay_max_m"]),
        ("弦からの出っ張りのへこみ", "%.2f" % sb["back_bulge_dip_max_m"], "%.3f m" % sc["back_bulge_dip_max_m"]),
        ("輪郭のへこみ b90 c ≥ −14", "%.2f" % sb["silhouette_dip_px_hero"]["b90_back_straight"], "%.2f px" % sc["silhouette_dip_px_hero"]["b90_back_straight"]),
        ("輪郭のへこみ b65 c ≥ −14", "%.2f" % sb["silhouette_dip_px_hero"]["b65_back65_clay"], "%.2f px" % sc["silhouette_dip_px_hero"]["b65_back65_clay"]),
        ("輪郭のへこみ b115 c ≥ −14", "%.2f" % sb["silhouette_dip_px_hero"]["b115_back_minus_c"], "%.2f px" % sc["silhouette_dip_px_hero"]["b115_back_minus_c"]),
        ("輪郭のへこみ b115 全部（b区域）", "%.1f" % sb["silhouette_dip_px_all"]["b115_back_minus_c"], "%.1f px" % sc["silhouette_dip_px_all"]["b115_back_minus_c"]),
        ("奥 c > 0 の体積（近い値）", "%.0f" % sb["F04_like"]["far_volume_c_gt_0_m3"], "%.0f m³" % sc["F04_like"]["far_volume_c_gt_0_m3"]),
    ]
    yy = y0 + 44 * S
    dr.text((x0, yy), "項目", fill=INK2, font=F(12))
    dr.text((x0 + 330 * S, yy), "前", fill=INK2, font=F(12))
    dr.text((x0 + 460 * S, yy), "後", fill=C_AFTER, font=F(12, True))
    for r in rows:
        yy += 38 * S
        dr.line([(x0, yy - 8 * S), (x0 + 610 * S, yy - 8 * S)], fill=GRID, width=S)
        dr.text((x0, yy), r[0], fill=INK, font=F(12.5))
        dr.text((x0 + 330 * S, yy), r[1], fill=INK2, font=F(12.5))
        dr.text((x0 + 460 * S, yy), r[2], fill=INK, font=F(12.5, True))
    img = img.resize((1920, 1080), Image.LANCZOS)
    img.save(out)
    print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
