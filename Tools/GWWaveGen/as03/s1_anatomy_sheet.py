# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照の彫刻の測りの数を、我々が描いた模式図に載せる（sculpture_anatomy.png）。
写真の画素も OBJ の形も使わない（線・多角形・楕円だけで描く）。数は sculpture_spec.json から読む。ラベルは日本語。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_anatomy_sheet.py
"""
import json
import math

import numpy as np
from PIL import Image, ImageDraw, ImageFont

STUDY = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study"
SPEC = STUDY + "/sculpture_spec.json"
OUT = STUDY + "/sculpture_anatomy.png"
W, H = 2400, 1500
FR = "C:/Windows/Fonts/YuGothM.ttc"
FB = "C:/Windows/Fonts/YuGothB.ttc"
BG = (247, 246, 243)
INK = (40, 40, 48)
GRID = (205, 205, 210)
WHITE = (252, 252, 250)
WHITE_S = (175, 178, 184)
INDIGO = (24, 34, 70)
INDIGO_M = (40, 58, 98)
LBLUE = (70, 115, 185)
ACC = (190, 70, 40)


def f(sz, bold=False):
    return ImageFont.truetype(FB if bold else FR, sz)


def panel(d, x0, y0, x1, y1, title):
    d.rectangle([x0, y0, x1, y1], outline=GRID, width=2)
    d.text((x0 + 14, y0 + 8), title, font=f(25, True), fill=INK)


def txt(d, xy, s, sz=20, col=INK, bold=False):
    d.text(xy, s, font=f(sz, bold), fill=col)


def wrap(d, xy, s, sz, maxw, col=INK, bold=False):
    """幅 maxw の中で折り返して書き、次の行の y を返す。英数字の続き（数・単位）は切らず、句読点・閉じ括弧で行を始めない。"""
    import re
    fo = f(sz, bold)
    x, y = xy
    toks = re.findall(r"[A-Za-z0-9.%+\-^_/*]+|\s+|.", s)
    line = ""
    for t in toks:
        if line and fo.getlength(line + t) > maxw and t not in "。、）」・，．)":
            d.text((x, y), line, font=fo, fill=col)
            y += int(sz * 1.35)
            line = t.lstrip()
        else:
            line += t
    if line:
        d.text((x, y), line, font=fo, fill=col)
        y += int(sz * 1.35)
    return y


def arrow(d, p0, p1, col=ACC, w=3, head=12):
    d.line([p0, p1], fill=col, width=w)
    a = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (-0.45, 0.45):
        d.line([p1, (p1[0] - head * math.cos(a + s), p1[1] - head * math.sin(a + s))], fill=col, width=w)


def tube(d, pts, r0, r1, fill=WHITE, outline=WHITE_S):
    """背骨 pts に沿って半径 r0 → r1 で細る管を、丸い先で描く。"""
    n = len(pts)
    left, right = [], []
    for i, p in enumerate(pts):
        q0 = pts[max(i - 1, 0)]
        q1 = pts[min(i + 1, n - 1)]
        tx, ty = q1[0] - q0[0], q1[1] - q0[1]
        L = math.hypot(tx, ty) or 1
        nx, ny = -ty / L, tx / L
        r = r0 + (r1 - r0) * (i / (n - 1))
        left.append((p[0] + nx * r, p[1] + ny * r))
        right.append((p[0] - nx * r, p[1] - ny * r))
    d.polygon(left + right[::-1], fill=fill, outline=outline)
    e = pts[-1]
    d.ellipse([e[0] - r1, e[1] - r1, e[0] + r1, e[1] + r1], fill=fill, outline=outline)
    d.line([left[-1], right[-1]], fill=fill, width=3)


def curve(p0, p1, bend, n=12):
    """p0 → p1 を、垂直の向きに bend だけ曲げた点列（二次ベジェ）。"""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy) or 1
    cx, cy = mx - dy / L * bend, my + dx / L * bend
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * cx + t * t * p1[0], (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * cy + t * t * p1[1])
            for t in [k / n for k in range(n + 1)]]


def hand(d, root, ang_deg, length, thick, digit_d, tip_d, br=0.42, spread=41, droop=0.3):
    """一つの手：平たい掌（台形）＋ 3 本の指。ang_deg は画面の角（0 = 右、正 = 下）。length・太さは画素。"""
    a = math.radians(ang_deg)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    pl = length * br
    w1 = 2.6 * digit_d
    pe = (root[0] + pl * ux, root[1] + pl * uy)
    palm = [(root[0] + nx * thick / 2, root[1] + ny * thick / 2), (pe[0] + nx * w1 / 2, pe[1] + ny * w1 / 2),
            (pe[0] - nx * w1 / 2, pe[1] - ny * w1 / 2), (root[0] - nx * thick / 2, root[1] - ny * thick / 2)]
    d.polygon(palm, fill=WHITE, outline=WHITE_S)
    dl = length * (1 - br)
    for k in (-1, 0, 1):
        st_ = (pe[0] + nx * k * digit_d * 0.9, pe[1] + ny * k * digit_d * 0.9)
        aa = a + math.radians(k * spread / 2)
        tip = (st_[0] + dl * math.cos(aa), st_[1] + dl * math.sin(aa) + dl * droop)
        tube(d, curve(st_, tip, dl * 0.08 * k, 10), digit_d / 2, tip_d / 2)


def main():
    S = json.load(open(SPEC, encoding="utf-8"))
    sc = S["scale"]
    c1 = S["1_crest_crown"]
    c2 = S["2_white_and_drip_edge"]
    c3 = S["3_carved_face"]
    c4 = S["4_colour_and_shading"]
    H0 = sc["H_hero_m"]["value"]
    hm = lambda r: r * H0
    L_ = c1["length"]
    T = c1["thickness"]
    B = c1["branching"]
    lh = L_["hand_len_over_H"]["value"]["p50"]
    ld = L_["digit_len_over_H"]["value"]["p50"]
    db = T["digit_diam_base_over_H"]["value"]["p50"]
    dm = T["digit_diam_mid_over_H"]["value"]["p50"]
    dt = T["digit_diam_tip_over_H"]["value"]["p50"]
    hb = T["hand_diam_base_over_H"]["value"]["p50"]
    br = B["branch_start_fraction_of_hand_length"]["value"]["p50"]
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    txt(d, (24, 14), "美術の見本03 の調べ S1：参照の彫刻の波頭の冠・垂れる縁・彫りの面・陰影（模式図）", 34, bold=True)
    txt(d, (24, 60), "数は参照の彫刻から測った比（H = 主の頂の高さ、L = 冠の縁の長さ）と、主役波 K*′ AS02C（H0 = %.2f m）へ当てた m。"
                     "図は我々が線で描いた模式図で、写真の画素も OBJ の形も使っていない。" % H0, 20)

    # ------------------------------------------------ A 断面（横から）
    x0, y0, x1, y1 = 24, 100, 1000, 830
    panel(d, x0, y0, x1, y1, "A 横から見た断面：冠のある所と指の向き（指は実の大きさ）")
    base_y = 790
    Hpx = 500
    ox = 300
    P = lambda a, y: (ox + a * Hpx, base_y - y * Hpx)
    body = [P(-0.50, 0.0), P(-0.40, 0.30), P(-0.25, 0.60), P(-0.10, 0.86), P(0.0, 0.97), P(0.06, 1.0), P(0.14, 0.98),
            P(0.24, 0.92), P(0.33, 0.83), P(0.39, 0.72), P(0.40, 0.62), P(0.35, 0.58), P(0.28, 0.64), P(0.18, 0.69),
            P(0.08, 0.66), P(0.00, 0.57), P(-0.04, 0.42), P(-0.03, 0.26), P(0.03, 0.12), P(0.15, 0.04), P(0.32, 0.0)]
    d.polygon(body, fill=INDIGO)
    whiteA = [P(-0.43, 0.22), P(-0.40, 0.30), P(-0.25, 0.60), P(-0.10, 0.86), P(0.0, 0.97), P(0.06, 1.0), P(0.14, 0.98),
              P(0.24, 0.92), P(0.33, 0.83), P(0.39, 0.72), P(0.37, 0.69), P(0.28, 0.77), P(0.17, 0.82), P(0.06, 0.83),
              P(-0.04, 0.78), P(-0.15, 0.62), P(-0.25, 0.46), P(-0.34, 0.32)]
    d.polygon(whiteA, fill=WHITE, outline=WHITE_S)
    for k in range(4):
        r = 0.05 + 0.05 * k
        arc = [P(0.20 - (0.18 + r) * math.cos(t) * 0.8, 0.36 + (0.18 + r) * math.sin(t)) for t in [math.pi * (-0.35 + 0.85 * i / 20) for i in range(21)]]
        d.line(arc, fill=LBLUE, width=3)
    d.line([(x0 + 10, base_y), (x0 + 600, base_y)], fill=GRID, width=2)
    txt(d, (x0 + 520, base_y + 6), "海面 0", 17)
    # 冠：手（掌＋3 本の指）を実の大きさで、頂の前と唇の背に置く（向きは前・下、下の段ほど下向き）
    hl, ht, hdd, htd = lh * Hpx, hb * Hpx, db * Hpx, dt * Hpx
    roots = [(0.08, 0.995, 6), (0.16, 0.975, 14), (0.24, 0.92, 22), (0.31, 0.86, 32), (0.36, 0.78, 45), (0.395, 0.70, 58),
             (0.39, 0.63, 75), (0.12, 0.93, 20), (0.21, 0.87, 30), (0.29, 0.80, 42)]
    for ra, ry, ang in roots:
        hand(d, P(ra, ry), ang, hl, ht, hdd, htd, br=br, spread=41, droop=0.3)
    rh = c1["coverage"]["root_height_above_sea_over_H"]["value"]
    bx = x0 + 650
    d.line([(bx, P(0, rh["p90"])[1]), (bx, P(0, rh["p10"])[1])], fill=ACC, width=3)
    for key, nm in (("p90", "p90"), ("p50", "中央値"), ("p10", "p10")):
        yy = P(0, rh[key])[1]
        d.line([(bx - 8, yy), (bx + 8, yy)], fill=ACC, width=3)
        txt(d, (bx + 14, yy - 12), "%s %.2f H（%.1f m）" % (nm, rh[key], hm(rh[key])), 18, ACC)
    txt(d, (bx - 20, P(0, rh["p90"])[1] - 40), "指の根元の高さ（海面から）", 18, ACC, True)
    dr = c1["direction"]
    ax0, ay0 = bx, base_y - 130
    d.line([(ax0, ay0), (ax0 + 140, ay0)], fill=GRID, width=2)
    arrow(d, (ax0, ay0), (ax0 + 130 * math.cos(math.radians(24)), ay0 + 130 * math.sin(math.radians(24))))
    txt(d, (ax0 + 150, ay0 - 12), "水平", 16)
    wrap(d, (bx - 20, ay0 + 66), "指の向き：水平から 24° 下（中央値）。先は 33° 下。%d%% が下向き、%d%% が前（唇の上）へ。根元の面の法線から 22°（p10 12°・p90 39°）"
         % (round(100 * dr["frac_tips_pointing_down"]["value"]), round(100 * dr["frac_forward_over_lip"]["value"])), 16, x1 - (bx - 20) - 12)
    wrap(d, (x0 + 18, y0 + 46), "背には指がない（76 本のうち頂の線より後ろは 1 本）。白は頂から海面の 0.25〜0.40 H まで、境は滑らか。"
         "冠は頂の線の前、0〜0.32 H 下まで（2〜3 段）。藍の面の弧は溝の流れ", 17, 600)
    txt(d, P(-0.45, 0.08), "藍", 22, WHITE, True)
    txt(d, P(-0.27, 0.52), "白", 22, INK, True)
    arrow(d, (x0 + 30, y0 + 150), (x0 + 120, y0 + 150), col=INK, w=2)
    txt(d, (x0 + 128, y0 + 138), "進む向き（+a）", 17)

    # ------------------------------------------------ B 一つの手
    x0, y0, x1, y1 = 1010, 100, 1640, 830
    panel(d, x0, y0, x1, y1, "B 一つの手（掌＋指）の作り")
    sc_ = 330 / lh
    root = (x0 + 100, 340)
    d.rectangle([x0 + 6, root[1] - 130, root[0], root[1] + 130], fill=(225, 226, 228))
    txt(d, (x0 + 14, root[1] + 134), "胴", 18)
    a = math.radians(6)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    pl = lh * br * sc_
    t0 = hb * sc_
    w1 = 2.5 * db * sc_
    pe = (root[0] + pl * ux, root[1] + pl * uy)
    # 掌：根元の厚み t0 から、分かれ目で指 3 本ぶんの幅 w1 へ広がる平たい葉の形
    lobe = []
    for i in range(21):
        u = i / 20
        half = (t0 / 2) * (1 - u) + (w1 / 2) * u + 10 * math.sin(math.pi * u)
        lobe.append((root[0] + pl * u * ux + nx * half, root[1] + pl * u * uy + ny * half))
    for i in range(20, -1, -1):
        u = i / 20
        half = (t0 / 2) * (1 - u) + (w1 / 2) * u + 10 * math.sin(math.pi * u)
        lobe.append((root[0] + pl * u * ux - nx * half, root[1] + pl * u * uy - ny * half))
    d.polygon(lobe, fill=WHITE, outline=WHITE_S)
    dl = lh * (1 - br) * sc_
    tips = []
    for k in (-1, 0, 1):
        st_ = (pe[0] - 8 * ux + nx * k * db * sc_ * 0.8, pe[1] - 8 * uy + ny * k * db * sc_ * 0.8)
        aa = a + math.radians(k * 41 / 2)
        tip = (st_[0] + dl * math.cos(aa), st_[1] + dl * math.sin(aa) + dl * 0.25)
        tube(d, curve(st_, tip, -dl * 0.10, 14), db * sc_ / 2, dt * sc_ / 2)
        tips.append(tip)
    tip = tips[0]
    rr = dt * sc_ * 0.24
    d.ellipse([tip[0] - rr, tip[1] - rr, tip[0] + rr, tip[1] + rr], fill=(150, 150, 156))
    txt(d, (tip[0] + 26, tip[1] - 34), "管の先（約 1 割）", 16)
    d.line([(root[0], root[1] - w1 / 2 - 40), (pe[0], pe[1] - w1 / 2 - 40)], fill=ACC, width=2)
    d.line([(pe[0], pe[1] - w1 / 2 - 50), (pe[0], pe[1] + w1 / 2 + 20)], fill=ACC, width=1)
    txt(d, (root[0] + 4, root[1] - w1 / 2 - 72), "掌（平たい）＝手の長さの %.2f" % br, 16, ACC)
    txt(d, (pe[0] + 8, pe[1] + w1 / 2 + 2), "指の開き 41°", 16, ACC)
    ty = 520
    rows = [
        ("手の長さ", "%.3f H（%.2f m）" % (lh, hm(lh))),
        ("手の根元の径", "%.3f H（%.2f m）" % (hb, hm(hb))),
        ("指の長さ", "%.3f H（%.2f m）p10 %.3f・p90 %.3f" % (ld, hm(ld), L_["digit_len_over_H"]["value"]["p10"], L_["digit_len_over_H"]["value"]["p90"])),
        ("指の径", "根元・中・先 %.3f・%.3f・%.3f H" % (db, dm, dt)),
        ("", "（%.2f・%.2f・%.2f m）" % (hm(db), hm(dm), hm(dt))),
        ("細り", "r/r根元 = 1 − %.2f f^%.2f（ほぼ直線）" % (T["taper_law_digit"]["value"]["k"], T["taper_law_digit"]["value"]["p"])),
        ("分かれる所", "手の長さの %.2f（p25 %.2f・p75 %.2f）" % (br, B["branch_start_fraction_of_hand_length"]["value"]["p25"], B["branch_start_fraction_of_hand_length"]["value"]["p75"])),
        ("手の中の指", "写真 3 本（2〜5）／スキャン 1.5（下限）"),
        ("指どうしの開き", "41°（p25 24°・p75 67°）"),
        ("手の曲がり", "根元から先へ 43°（先が垂れる）"),
        ("先の形", "丸い半球が多数。管の先 約 1 割"),
        ("", "しずく形はまれ。針のように尖らない"),
        ("長さ / 径", "写真 約 3.5（2.5〜5.5）／スキャン 2.0"),
    ]
    for i, (k, v) in enumerate(rows):
        txt(d, (x0 + 16, ty + i * 23), k, 17, ACC, True)
        txt(d, (x0 + 170, ty + i * 23), v, 17)

    # ------------------------------------------------ C 冠の縁に沿った数
    x0, y0, x1, y1 = 1650, 100, 2376, 830
    panel(d, x0, y0, x1, y1, "C 冠の縁に沿った数（前から）")
    cnt = c1["counts"]
    Lr = sc["L_ref_m"]["value"]
    Lh_ = sc["L_hero_m"]["value"]
    px0, px1, pyb, phh = 1680, 2350, 470, 260
    # 模式の頂の線（参照の形ではない。両端 0.42 H・0.57 H、中ほど 1.0 の一つの山）
    PP = [(px0 + (px1 - px0) * u, pyb - phh * (0.42 + 0.58 * math.exp(-((u - 0.5) / 0.28) ** 2) + 0.15 * u / (1 + math.exp(-(u - 0.5) / 0.06))))
          for u in [i / 40 for i in range(41)]]
    d.line(PP, fill=INK, width=4, joint="curve")
    nh = cnt["hands_per_m_of_L"]["hero"]["count_on_L_hero"]
    nt = cnt["fingertips_per_m_of_L"]["hero"]["count_on_L_hero"]
    xs = np.array([p[0] for p in PP])
    ys = np.array([p[1] for p in PP])
    cs = np.r_[0, np.cumsum(np.hypot(np.diff(xs), np.diff(ys)))]
    for k in range(nt):
        s_ = (k + 0.5) / nt * cs[-1]
        xx, yy = np.interp(s_, cs, xs), np.interp(s_, cs, ys)
        d.line([(xx, yy + 6), (xx + 4, yy + 26)], fill=WHITE_S, width=3)
    for k in range(nh):
        s_ = (k + 0.5) / nh * cs[-1]
        xx, yy = np.interp(s_, cs, xs), np.interp(s_, cs, ys)
        d.ellipse([xx - 7, yy - 7, xx + 7, yy + 7], fill=WHITE, outline=INK)
    txt(d, (px0, pyb + 30), "← b区域の肩（-c、原画視点の左）", 16)
    txt(d, (px1 - 200, pyb + 30), "唇の先（+c、右）→", 16)
    txt(d, (px0, pyb + 52), "線は模式（参照の形ではない）", 15)
    wrap(d, (x0 + 16, 140), "○ 手（主役波に %d 個）　| 指先（主役波に %d 本）を、縁に沿って等間隔に置いた図（実際の並びは不規則）" % (nh, nt), 16, x1 - x0 - 30)
    yy0 = 560
    lines = [
        ("縁の長さ L", "参照 %.1f m（%.2f H）／主役波 %.1f m（%.2f H0）" % (Lr, sc["L_ref_m"]["rel"]["L_over_H"], Lh_, sc["L_hero_m"]["rel"]["L_over_H"])),
        ("指先の数", "参照 %d 本＝%.2f 本/m（%.1f 本/H）" % (cnt["fingertips_total_ref"]["value"], cnt["fingertips_per_m_of_L"]["value"], cnt["fingertips_per_m_of_L"]["rel"]["per_H_of_L"])),
        ("　主役波へ", "%.2f 本/m × L → %d 本（%d〜%d）" % (cnt["fingertips_per_m_of_L"]["hero"]["per_m"], nt, cnt["fingertips_per_m_of_L"]["hero"]["range"][0], cnt["fingertips_per_m_of_L"]["hero"]["range"][1])),
        ("手（一次の指）", "参照 %d 個＝%.2f 個/m（定義で 0.62〜1.11）" % (cnt["hands_total_ref"]["value"], cnt["hands_per_m_of_L"]["value"])),
        ("　主役波へ", "%d 個（%d〜%d）" % (nh, cnt["hands_per_m_of_L"]["hero"]["range"][0], cnt["hands_per_m_of_L"]["hero"]["range"][1])),
        ("根元の間隔", "最も近い根元まで %.3f H（%.2f m）" % (c1["layering"]["nearest_root_spacing_over_H"]["value"]["p50"], c1["layering"]["nearest_root_spacing_over_H"]["hero"]["p50_m"])),
        ("段", "2〜3 段：最前列は唇の縁から垂れる"),
        ("すき間", "垂れる帯の中ほどで白 35%（藍が 55〜75% 見える）"),
        ("前の小波", "指なし（滑らかな白い帽子＋藍の舌の縁）"),
        ("b区域の肩", "ある（白い塊に穴、下の縁から指）"),
    ]
    for i, (k, v) in enumerate(lines):
        txt(d, (x0 + 16, yy0 + i * 26), k, 17, ACC, True)
        txt(d, (x0 + 180, yy0 + i * 26), v, 17)

    # ------------------------------------------------ D 面の溝の断面
    x0, y0, x1, y1 = 24, 840, 800, 1486
    panel(d, x0, y0, x1, y1, "D 彫りの面：溝の断面（横の切り口）")
    per = 150
    yb = 1040
    wr = c3["light_blue_width_over_period"]["value"]
    for k in range(4):
        cx = 80 + k * per
        rib = per * (1 - wr)
        pts = [(cx + t, yb - 26 * math.sin(math.pi * t / rib)) for t in np.linspace(0, rib, 30)]
        d.polygon(pts + [(cx + rib, yb + 40), (cx, yb + 40)], fill=INDIGO_M)
        d.line([(cx + rib * 0.38, yb - 25), (cx + rib * 0.6, yb - 25)], fill=(235, 235, 245), width=4)
        gx = cx + rib
        d.rectangle([gx, yb - 4, gx + per * wr, yb + 40], fill=LBLUE)
        d.ellipse([gx, yb - 12, gx + per * wr, yb + 4], fill=LBLUE)
    d.line([(80, yb + 70), (80 + per, yb + 70)], fill=ACC, width=3)
    txt(d, (80, yb + 76), "周期", 18, ACC, True)
    gp = c3["groove_period_over_H"]
    wf = float(sc["W_hero_m"]["note"].split("は ")[1].split(" m")[0])
    rows = [
        ("周期", "中ほど %.3f H（%.2f m）、上 %.3f・下 %.3f H（%.2f・%.2f m）" % (gp["value"], gp["hero"], gp["rel"]["upper_just_below_crown"], gp["rel"]["lower_face"], hm(gp["rel"]["upper_just_below_crown"]), hm(gp["rel"]["lower_face"]))),
        ("水色の幅", "周期の %.2f（主役波 %.2f m）。藍の稜 : 水色 ≈ 3 : 1" % (wr, c3["light_blue_width_over_period"]["hero"])),
        ("深さ", "深さ / 周期 ≈ 0.1（0.05〜0.25、写真の陰影からの推定）"),
        ("スキャン", "OBJ の面に規則的な溝は残っていない（RMS 0.2% H の雑音）"),
        ("見える数", "前から見える面で 上 10〜12・中 12〜14・下 8〜10 本"),
        ("流れ", "空洞を中心とする入れ子の C 字。下で横へ寝て谷へ流れる"),
        ("Y 字", "線 3〜4 本に 1 つ、下流へ開く"),
        ("終わり", "上：冠の垂れる指の陰で消える（白に触れない）"),
        ("", "下：前の小波の白の後ろ・谷の横線へ"),
        ("主役波の面", "藍の面の幅 %.1f m なら中ほどで約 %d 本" % (wf, int(round(wf / gp["hero"])))),
    ]
    for i, (k, v) in enumerate(rows):
        txt(d, (x0 + 16, 1150 + i * 32), k, 18, ACC, True)
        txt(d, (x0 + 150, 1150 + i * 32), v, 18)

    # ------------------------------------------------ E 白の範囲と舌の縁
    x0, y0, x1, y1 = 810, 840, 1560, 1486
    panel(d, x0, y0, x1, y1, "E 白の範囲と、藍の舌の縁（前の小波）")
    tw = c2["tongues_small_wave"]
    k_ = 1000.0
    wpx = tw["width_over_H"]["value"] * k_
    sp = tw["spacing_over_H"]["value"] * k_
    ln = tw["length_over_H"]["value"] * k_
    yb2 = 1150
    d.rectangle([x0 + 20, 920, x1 - 20, yb2 + 40], fill=WHITE, outline=WHITE_S)
    d.rectangle([x0 + 20, yb2, x1 - 20, yb2 + 40], fill=INDIGO)
    for k in range(6):
        cx = x0 + 80 + k * sp
        d.rectangle([cx - wpx / 2, yb2 - ln + wpx / 2, cx + wpx / 2, yb2 + 2], fill=INDIGO)
        d.ellipse([cx - wpx / 2, yb2 - ln, cx + wpx / 2, yb2 - ln + wpx], fill=INDIGO)
        d.line([(cx, yb2 - ln + wpx * 0.6), (cx, yb2 + 30)], fill=LBLUE, width=3)
    cx = x0 + 80
    d.line([(cx - wpx / 2, yb2 - ln - 14), (cx + wpx / 2, yb2 - ln - 14)], fill=ACC, width=3)
    txt(d, (cx - wpx / 2, yb2 - ln - 44), "幅", 17, ACC, True)
    d.line([(cx, yb2 + 52), (cx + sp, yb2 + 52)], fill=ACC, width=3)
    txt(d, (cx + sp / 2 - 20, yb2 + 56), "間隔", 17, ACC, True)
    xe = cx + sp * 5 + wpx / 2 + 14
    d.line([(xe, yb2 - ln), (xe, yb2)], fill=ACC, width=3)
    txt(d, (xe + 6, yb2 - ln / 2 - 10), "長さ", 17, ACC, True)
    txt(d, (x0 + 30, 930), "（図の大きさは H = 1000 画素にそろえた）", 15)
    rows = [
        ("舌の幅", "%.3f H（%.2f m）" % (tw["width_over_H"]["value"], tw["width_over_H"]["hero"])),
        ("舌の間隔", "%.2f H（%.2f m）＝境 1 H あたり %.1f 本" % (tw["spacing_over_H"]["value"], tw["spacing_over_H"]["hero"], tw["spacing_over_H"]["rel"]["per_H_of_boundary"])),
        ("舌の長さ", "%.2f H（%.2f m、見える長さ）" % (tw["length_over_H"]["value"], tw["length_over_H"]["hero"])),
        ("舌の頭", "半円で丸い。間の白は下向きに尖った V。舌に水色の線 1 本"),
        ("背の白", "頂から海面の 0.25〜0.40 H（%.1f〜%.1f m）まで。境は滑らか" % (hm(0.25), hm(0.40))),
        ("主役波の前", "白は冠（立体の指）だけ。面に塗った白い舌はない"),
        ("溝の中の白", "ない"),
        ("右の端（+c の外）", "背の白が海面近くまで下りる"),
    ]
    for i, (k, v) in enumerate(rows):
        txt(d, (x0 + 16, 1240 + i * 29), k, 17, ACC, True)
        txt(d, (x0 + 190, 1240 + i * 29), v, 17)

    # ------------------------------------------------ F 色と艶
    x0, y0, x1, y1 = 1570, 840, 2376, 1486
    panel(d, x0, y0, x1, y1, "F 色（白を中立に直した sRGB）と艶")
    C = c4["colors"]
    names = [("white", "白"), ("lightblue", "水色（溝の線）"), ("indigo", "藍"), ("gold", "金（舟）"), ("base", "台の水色")]
    yy = 892
    for key, nm in names:
        c = C[key]
        txt(d, (x0 + 16, yy + 16), nm, 18, INK, True)
        for j, lvl in enumerate(("lit", "mid", "shadow")):
            col = tuple(c["%s_srgb_wb" % lvl])
            bx = x0 + 200 + j * 190
            d.rectangle([bx, yy, bx + 56, yy + 52], fill=col, outline=GRID)
            txt(d, (bx + 62, yy + 2), {"lit": "光", "mid": "中", "shadow": "陰"}[lvl] + " L*%.0f" % c["L_%s" % lvl], 16)
            txt(d, (bx + 62, yy + 24), "%d,%d,%d" % col, 15)
        yy += 64
    rows = [
        ("写真のまま", "白の光 %s・水色の中 %s・藍の中 %s（暖かい電球の光）" % (tuple(C["white"]["lit_srgb_raw"]), tuple(C["lightblue"]["mid_srgb_raw"]), tuple(C["indigo"]["mid_srgb_raw"]))),
        ("陰影の幅", "白 ΔL* 約 31（光 81 → 陰 50）。藍の拡散は L* 2〜6 で、形は艶で読む"),
        ("艶", "鋭い小さな光の点（指の径の 0.12〜0.18）、背に窓の映り込み。粗さ 0.05〜0.15（推定）"),
        ("縁の光・線", "描いた縁の光も縁取りの線もない。斜めの所の映り込みが明るい"),
    ]
    yq = 1220
    for k, v in rows:
        txt(d, (x0 + 16, yq), k, 16, ACC, True)
        yq = wrap(d, (x0 + 140, yq), v, 16, x1 - x0 - 155) + 4
    wrap(d, (x0 + 16, yq + 4), "主役波への当てはめ：H 参照 %.2f m → H0 %.2f m（長さの倍率 %.3f）。W（頂 ≥ 0.5 H の幅）参照 %.1f m → 主役波 %.1f m（藍の面の幅 %.1f m）"
         % (sc["H_ref_m"]["value"], H0, sc["length_scale_ref_to_hero"], sc["W_ref_m"]["value"], sc["W_hero_m"]["value"], wf), 15, x1 - x0 - 30)
    img.save(OUT)
    print("wrote", OUT, img.size)


if __name__ == "__main__":
    main()
