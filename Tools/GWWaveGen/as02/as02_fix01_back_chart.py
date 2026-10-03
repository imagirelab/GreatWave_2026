# -*- coding: utf-8 -*-
"""美術の見本02 修正の回 1：背が一つの山か（要求書 S4）の、落ちていた検査「各高さのふくらみの最大が中ほどの区間にあるか」の図（1920×1080）。
上の段：低い高さ 0.05・0.15・0.30・0.40 H0 の、弦（等高線の両端）からの背の出っ張り g(c)。もとの P28R2rec・見本02 の AS02B・修正の回 1 の AS02C を重ね、
中ほどの区間（c −6〜+6、頂が 0.9 Hmax 以上の行）を灰の帯、各形の最大を点で示す。
下の段：全部の高さの最大の位置の表と、S4 のほかの数（へこみ・後ろからの輪郭・奥の体積）。
数は back_measure.py の measure.json から読むだけ（参照モデルは読まない）。PIL で描く（matplotlib は入っていない）。
使い方：py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_back_chart.py <measure.json> <out.png>
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

S = 2
W, H = 1920 * S, 1080 * S
SURF = (252, 252, 251)
INK = (31, 31, 30)
INK2 = (95, 94, 90)
GRID = (226, 225, 220)
ZONE = (236, 235, 230)
# 分類の色（青・橙・緑。見本02 の AS02B は緑 (27,175,122) の点線。渡す時の直し（as02_deliver）で、図の中の説明を「水色」から「緑」に合わせた）
COL = {"P28R2rec": (235, 104, 52), "AS02B": (27, 175, 122), "AS02C": (42, 120, 214)}
DASH = {"P28R2rec": (5, 4), "AS02B": (2, 3), "AS02C": None}
NAME = {"P28R2rec": "もと P28R2rec", "AS02B": "見本02 AS02B", "AS02C": "今 AS02C"}
ZONE_C = (-6.0, 6.0)


def F(sz, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), int(sz * S))


def poly(dr, pts, col, w, dash):
    if not dash:
        dr.line(pts, fill=col, width=int(w * S), joint="curve")
        return
    on, off = dash[0] * S, dash[1] * S
    acc, draw = 0.0, True
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        L = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        t = 0.0
        while t < L:
            seg = (on if draw else off) - acc
            t1 = min(L, t + seg)
            if draw:
                dr.line([(x0 + (x1 - x0) * t / L, y0 + (y1 - y0) * t / L), (x0 + (x1 - x0) * t1 / L, y0 + (y1 - y0) * t1 / L)], fill=col, width=int(w * S))
            acc += t1 - t
            t = t1
            if acc >= (on if draw else off) - 1e-6:
                acc, draw = 0.0, not draw


def panel(dr, box, lev, M, labels):
    x0, y0, x1, y1 = [v * S for v in box]
    dr.text((x0, y0), "高さ %s H0：弦からの出っ張り g(c)" % lev, fill=INK, font=F(17, True))
    L, T, R, B = x0 + 46 * S, y0 + 84 * S, x1 - 10 * S, y1 - 34 * S
    allg = [g for lab in labels for g in M[lab]["levels"][lev]["profile"]["bulge"]]
    gmin, gmax = min(0.0, min(allg)), max(allg) * 1.1
    cmin, cmax = -15.0, 15.5

    def px(c, g):
        return L + (c - cmin) / (cmax - cmin) * (R - L), B - (g - gmin) / (gmax - gmin) * (B - T)
    zx0, zx1 = px(ZONE_C[0], 0)[0], px(ZONE_C[1], 0)[0]
    dr.rectangle([zx0, T, zx1, B], fill=ZONE)
    dr.text(((zx0 + zx1) / 2, T + 4 * S), "中ほどの区間 c −6〜+6", fill=INK2, font=F(11), anchor="ma")
    for gv in range(0, int(gmax) + 1, 2):
        y = px(0, gv)[1]
        dr.line([(L, y), (R, y)], fill=GRID, width=S)
        dr.text((L - 6 * S, y), "%d" % gv, fill=INK2, font=F(11), anchor="rm")
    for cv in range(-15, 16, 5):
        x = px(cv, 0)[0]
        dr.text((x, B + 6 * S), "%d" % cv, fill=INK2, font=F(11), anchor="ma")
    dr.line([(L, B), (R, B)], fill=INK2, width=S)
    dr.text(((L + R) / 2, B + 20 * S), "c（m、波峰線に沿う）", fill=INK2, font=F(11), anchor="ma")
    dr.text((L - 40 * S, T - 2 * S), "m", fill=INK2, font=F(11))
    for lab in labels:
        p = M[lab]["levels"][lev]["profile"]
        pts = [px(c, g) for c, g in zip(p["c"], p["bulge"])]
        poly(dr, pts, COL[lab], 2.2 if lab == "AS02C" else 1.8, DASH[lab])
    for k, lab in enumerate(labels):
        v = M[lab]["levels"][lev]
        cx, gy = px(v["c_at_bulge_max"], v["bulge_over_chord_max_m"])
        r = 5 * S
        inside = ZONE_C[0] <= v["c_at_bulge_max"] <= ZONE_C[1]
        dr.ellipse([cx - r, gy - r, cx + r, gy + r], fill=COL[lab] if inside else SURF, outline=SURF if inside else COL[lab], width=2 * S)
        dr.text((L, y0 + (28 + 16 * k) * S), "%s 最大 c %+.1f %s" % (NAME[lab], v["c_at_bulge_max"], "（中ほど）" if inside else "（外）"),
                fill=COL[lab] if lab == "AS02C" else INK, font=F(11.5, lab == "AS02C"), anchor="la")


def main():
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    out = sys.argv[2]
    labels = [x for x in ("P28R2rec", "AS02B", "AS02C") if x in m["measure"]]
    M = m["measure"]
    img = Image.new("RGB", (W, H), SURF)
    dr = ImageDraw.Draw(img)
    dr.text((18 * S, 12 * S), "背は一つの山か（要求書 S4）：各高さで背のふくらみの最大が中ほどの区間にあるか。もと｜見本02｜今（修正の回 1）", fill=INK, font=F(21, True))
    dr.text((18 * S, 44 * S), "t* の静止の主役波の背（原画視点からは見えない所）。g(c) ＝ 背の等高線の位置 − 両端を結ぶ弦。点が塗りつぶし ＝ 中ほどの区間の中、白抜き ＝ 外。"
            "破線：もと（橙）、点線：見本02（緑）、実線：今（青）", fill=INK2, font=F(13))
    boxes = [(18, 74, 490, 560), (490, 74, 962, 560), (962, 74, 1434, 560), (1434, 74, 1906, 560)]
    for b, lev in zip(boxes, ("0.05", "0.15", "0.30", "0.40")):
        panel(dr, b, lev, M, labels)
    # 表
    x0, y0 = 18 * S, 600 * S
    dr.text((x0, y0), "高さごとの最大の位置 c（m）。中ほどの区間 −6〜+6 の外を「外」", fill=INK, font=F(16, True))
    levs = list(M[labels[0]]["levels"].keys())
    cw = 150 * S
    yy = y0 + 34 * S
    dr.text((x0, yy), "高さ（H0）", fill=INK2, font=F(12.5))
    for j, lv in enumerate(levs):
        dr.text((x0 + 190 * S + j * 0 + j * 120 * S, yy), lv, fill=INK2, font=F(12.5))
    for lab in labels:
        yy += 30 * S
        dr.line([(x0, yy - 6 * S), (x0 + 1420 * S, yy - 6 * S)], fill=GRID, width=S)
        dr.text((x0, yy), NAME[lab], fill=INK, font=F(12.5, lab == "AS02C"))
        for j, lv in enumerate(levs):
            c = M[lab]["levels"][lv]["c_at_bulge_max"]
            ins = ZONE_C[0] <= c <= ZONE_C[1]
            dr.text((x0 + 190 * S + j * 120 * S, yy), "%+.1f%s" % (c, "" if ins else " 外"), fill=INK if ins else (176, 60, 40), font=F(12.5, not ins))
    # ほかの数
    yy += 50 * S
    dr.text((x0, yy), "S4 のほかの数（どれも 0.10 m・1 px の許しの中なら合）", fill=INK, font=F(16, True))
    rows = [("H(c) のへこみ（c −14 より +c 側）", "H_dip_hero_m", "%.3f m"), ("背の等高線のへこみ（最大）", "back_dip_max_m", "%.3f m"),
            ("弦からの出っ張りのへこみ（最大）", "back_bulge_dip_max_m", "%.3f m")]
    sm = m["summary"]
    yy += 32 * S
    hx = [x0 + 420 * S + k * 260 * S for k in range(len(labels))]
    for k, lab in enumerate(labels):
        dr.text((hx[k], yy), NAME[lab], fill=INK2, font=F(12.5))
    for name, key, fmt in rows:
        yy += 28 * S
        dr.text((x0, yy), name, fill=INK, font=F(12.5))
        for k, lab in enumerate(labels):
            dr.text((hx[k], yy), fmt % sm[lab][key], fill=INK, font=F(12.5))
    yy += 28 * S
    dr.text((x0, yy), "後ろからの輪郭のへこみ b65・b90・b115（px）", fill=INK, font=F(12.5))
    for k, lab in enumerate(labels):
        s = sm[lab]["silhouette_dip_px_hero"]
        dr.text((hx[k], yy), "%.2f・%.2f・%.2f" % (s["b65_back65_clay"], s["b90_back_straight"], s["b115_back_minus_c"]), fill=INK, font=F(12.5))
    yy += 28 * S
    dr.text((x0, yy), "奥 c > 0 の水面より上の体積（近い値）", fill=INK, font=F(12.5))
    for k, lab in enumerate(labels):
        dr.text((hx[k], yy), "%.0f m³" % sm[lab]["F04_like"]["far_volume_c_gt_0_m3"], fill=INK, font=F(12.5))
    img = img.resize((1920, 1080), Image.LANCZOS)
    img.save(out)
    print(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
