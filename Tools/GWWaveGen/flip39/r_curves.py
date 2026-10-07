# -*- coding: utf-8 -*-
"""FLIP39 R：座席の列（z −80 m）の頂の歩み（E3・V1・R）と、座席の乗る目の仰角（V1・R）を並べた図（py -3.10、PIL）。
使い方: py -3.10 r_curves.py <R の run_dir> <V1 の run_dir> <z_seat>
頂＝箱の内側（境界の帯 + 2 m を除く）の座席の列（±0.9 m）の一番上の水面の最も高い所（それぞれの水面のずれを引いた）。
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from r_seat import Merged, TOFF, OFF_E3

FONT = r"C:/Windows/Fonts/YuGothM.ttc"


def crest_series(M, zs, coarse=False):
    if coarse:
        C = M.C
        rows = np.abs(M.zc - zs) <= 1.01
        inx = (M.xc >= M.win[0] + 2) & (M.xc <= M.win[1] - 2)
        sel = (C["frames"] >= 961) & (C["frames"] <= 1261)
        t = C["t"][sel] + TOFF
        e = np.array([np.nanmax(C["eta"][k][rows][:, inx]) for k in np.nonzero(sel)[0]]) - OFF_E3
        return t, e
    B = M.B
    rows = np.abs(M.zb - zs) <= max(0.9, 0.51 * (M.zb[1] - M.zb[0]))
    t = B["t"] + TOFF
    e = np.array([np.nanmax(B["eta"][k][rows][:, M.inb_x]) for k in range(len(t))]) - M.off_box
    return t, e


def main(rd, v1, zs):
    MR = Merged(rd); MV = Merged(v1)
    curves = [("E3（粒子 1 m の水槽）", (60, 110, 190)) + crest_series(MR, zs, coarse=True),
              ("V1（箱、粒子 1 m）", (120, 120, 120)) + crest_series(MV, zs),
              ("R（箱、粒子 0.3 m）", (170, 90, 30)) + crest_series(MR, zs)]
    seats = []
    for lab, d, col in (("V1", v1, (120, 120, 120)), ("R", rd, (170, 90, 30))):
        p = os.path.join(d, "seat_r_z%+04d.json" % int(round(zs)))
        if os.path.isfile(p):
            S = json.load(open(p, encoding="utf8"))
            sb = S.get("series_best") or {}
            if sb.get("t_group"):
                seats.append(("%s 座席 x %.0f m の乗る目の仰角" % (lab, S["best_seat"]["x_seat"]), col, np.array(sb["t_group"]), np.array(sb["alpha"])))
    W, H = 1400, 900
    im = Image.new("RGB", (W, H), (252, 252, 250)); dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 20); f2 = ImageFont.truetype(FONT, 17)
    dr.text((20, 12), "座席の列 z %.0f m：上＝頂の高さ（静かな水面から）、下＝座席の乗る目から見た水の仰角の最大。横＝群の時刻" % zs, fill=(20, 20, 20), font=f1)

    def panel(y0, h, ymin, ymax, series, ylab):
        x0, x1 = 90, W - 30; t0, t1 = 75.0, 87.5
        P = lambda t, v: (x0 + (x1 - x0) * (t - t0) / (t1 - t0), y0 + h - h * (v - ymin) / (ymax - ymin))
        for tt in np.arange(75, 88, 1.0):
            dr.line([P(tt, ymin), P(tt, ymax)], fill=(232, 232, 232)); dr.text((P(tt, ymin)[0] - 10, y0 + h + 4), "%d" % tt, fill=(80, 80, 80), font=f2)
        step = 2 if ymax - ymin <= 20 else 10
        for vv in np.arange(ymin, ymax + 1e-6, step):
            dr.line([P(t0, vv), P(t1, vv)], fill=(232, 232, 232)); dr.text((x0 - 45, P(t0, vv)[1] - 10), "%g" % vv, fill=(80, 80, 80), font=f2)
        dr.text((x0, y0 - 26), ylab, fill=(40, 40, 40), font=f2)
        for k, (lab, col, t, v) in enumerate(series):
            ok = np.isfinite(v) & (t >= t0) & (t <= t1)
            pts = [P(a, b) for a, b in zip(t[ok], np.clip(v[ok], ymin, ymax))]
            if len(pts) > 1:
                dr.line(pts, fill=col, width=3)
            dr.text((x1 - 420, y0 + 8 + 24 * k), "― " + lab, fill=col, font=f2)
    panel(80, 330, 6, 20, [(a, b, c, d) for a, b, c, d in curves], "頂 (m)")
    if seats:
        panel(500, 330, 0, 90, seats, "仰角 (°)")
    out = os.path.join(rd, "sheet_curves_r.png")
    im.save(out)
    for lab, col, t, v in curves:
        k = int(np.nanargmax(v)); print(lab, "max %.2f at %.2f" % (v[k], t[k]))
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]))
