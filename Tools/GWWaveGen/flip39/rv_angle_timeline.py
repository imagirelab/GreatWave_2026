# -*- coding: utf-8 -*-
"""FLIP39 レビュー（10/8）：座席の乗る目から見た仰角の時間の歩みを、乗る目の終わりまでの時間でそろえて並べる（py -3.10、PIL）。
P3＝FLIP37 P3（D1 の seat_measures_raw.json の alpha_riding、終わり 9.2 s）、V1・R＝R/V1_val_d10・R/H30_E3 の seat_r_z-080.json（best_seat の乗る目）。
出力：Unity/Build/FLIP39/review_angle_timeline.png と、標準出力に数の表。
"""
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

B = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/"
FONT = r"C:/Windows/Fonts/YuGothM.ttc"
FONTB = r"C:/Windows/Fonts/YuGothB.ttc"


def load():
    d1 = json.load(open(B + "D1/seat_measures_raw.json", encoding="utf8"))["series"]
    t = np.array(d1["t"], float)
    a = np.array([np.nan if v is None else v for v in d1["alpha_riding"]], float)
    out = [("P3（FLIP37、粒子 0.25 m、seat_v1）", t, a, 9.2, "#2a78d6", None)]
    for nm, f, col in (("V1（E3 を箱で再現、粒子 1 m、x 505 m）", "R/V1_val_d10/seat_r_z-080.json", "#eb6834"),
                       ("R（粒子 0.3 m、x 530 m）", "R/H30_E3/seat_r_z-080.json", "#1baf7a")):
        bs = json.load(open(B + f, encoding="utf8"))["best_seat"]
        se = bs["ride"]["series"]
        out.append((nm, np.array(se["t_group"], float), np.array(se["alpha"], float), float(bs["ride"]["end_t_group"]), col, bs["ride"].get("view_s")))
    return out


def stats(t, a, te):
    m = t <= te + 1e-6
    t, a = t[m], np.nan_to_num(a[m])
    dt = float(np.median(np.diff(t)))
    k = lambda back: float(a[np.argmin(np.abs(t - (te - back)))])
    t10 = float(t[np.argmax(a >= 10.0)])
    return dict(max=float(a.max()), a2=k(2.0), a1=k(1.0), t25=float(np.sum(a >= 25) * dt), t45=float(np.sum(a >= 45) * dt), view=te - t10)


def main():
    S = load()
    W, H = 1640, 900
    im = Image.new("RGB", (W, H), (252, 252, 251))
    dr = ImageDraw.Draw(im)
    fb = ImageFont.truetype(FONTB, 26); f1 = ImageFont.truetype(FONT, 20); f2 = ImageFont.truetype(FONT, 17)
    dr.text((30, 18), "座席の乗る目から見た頂の仰角（乗る目の終わりまでの時間でそろえた）", fill=(11, 11, 11), font=fb)
    dr.text((30, 56), "どれも物理だけの計算。乗る目＝船が上下だけ水面に乗る（傾き・押し流しなし）。\n終わり：P3 は船が頂へ持ち上げられた、V1 は頂の 0.85 倍まで持ち上げられた、R は水が目の高さに来た。",
            fill=(82, 81, 78), font=f2, spacing=4)
    x0, x1, y0, y1 = 110, 1060, 120, 750
    T0, T1, A0, A1 = -8.0, 0.0, 0.0, 80.0
    X = lambda t: x0 + (t - T0) / (T1 - T0) * (x1 - x0)
    Y = lambda a: y1 - (a - A0) / (A1 - A0) * (y1 - y0)
    for a in range(0, 81, 10):
        dr.line([X(T0), Y(a), X(T1), Y(a)], fill=(232, 232, 230) if a else (170, 170, 168), width=1)
        dr.text((x0 - 50, Y(a) - 11), "%d°" % a, fill=(82, 81, 78), font=f2)
    for t in range(-8, 1):
        dr.text((X(t) - 12, y1 + 8), "%d" % t, fill=(82, 81, 78), font=f2)
    dr.text((X(-4.6), y1 + 34), "乗る目の終わりまでの時間（秒）", fill=(82, 81, 78), font=f2)
    for a, lab in ((25, "25°：目だけで見上げる上の端（D1）"), (45, "45°"), (55, "55°：PS VR2 の視野の上の端の見込み（D1、推定）")):
        for xs in np.arange(X(T0), X(T1), 12):
            dr.line([xs, Y(a), xs + 6, Y(a)], fill=(150, 150, 148), width=1)
        dr.text((X(T0) + 6, Y(a) - 22), lab, fill=(82, 81, 78), font=f2)
    rows = []
    for nm, t, a, te, col, vs in S:
        m = (t <= te + 1e-6) & (t >= te + T0)
        pts = [(X(tt - te), Y(min(aa, A1))) for tt, aa in zip(t[m], a[m]) if np.isfinite(aa)]
        dr.line(pts, fill=col, width=3)
        st = stats(t, a, te)
        if vs is not None:
            st["view"] = float(vs)   # r_seat.py の値（記録と同じ。P3 は alpha_riding から）
        rows.append((nm, st))
        ex, ey = pts[-1]
        dr.ellipse([ex - 5, ey - 5, ex + 5, ey + 5], fill=col, outline=(252, 252, 251), width=2)
    # 右の凡例と数（文字は文字の色、印だけ系列の色）
    lx, ly = 1100, 130
    for nm, st in rows:
        col = [c for n2, _, _, _, c, _ in S if n2 == nm][0]
        dr.line([lx, ly + 12, lx + 30, ly + 12], fill=col, width=4)
        dr.text((lx + 38, ly), nm.split("（")[0], fill=(11, 11, 11), font=f1)
        dr.text((lx + 38, ly + 28), "（" + nm.split("（", 1)[1], fill=(82, 81, 78), font=f2)
        dr.text((lx + 38, ly + 54), "最大 %.0f°・2 秒前 %.0f°" % (st["max"], st["a2"]), fill=(11, 11, 11), font=f2)
        dr.text((lx + 38, ly + 78), "25° 以上 %.2f s・45° 以上 %.2f s" % (st["t25"], st["t45"]), fill=(11, 11, 11), font=f2)
        dr.text((lx + 38, ly + 102), "10° から終わりまで %.2f s" % st["view"], fill=(11, 11, 11), font=f2)
        ly += 150
    dr.text((1100, ly + 10), "読み方：高く見える（45° 以上）のは\nどれも終わりの 0.46〜0.58 秒だけ。\n2 秒前はどれも 30° 未満。", fill=(11, 11, 11), font=f1, spacing=6)
    dr.text((30, H - 58), "出典：D1 seat_measures_raw.json（P3）、R/V1_val_d10・R/H30_E3 の seat_r_z-080.json。道具 Tools/GWWaveGen/flip39/rv_angle_timeline.py（10/8 レビュー）。\nP3 は D1 の道具、V1・R は r_seat.py で測った。座席の選び方も違う（P3 は seat_v1 のまま、V1・R は調べて選んだ所）。",
            fill=(82, 81, 78), font=f2, spacing=4)
    out = B + "review_angle_timeline.png"
    im.save(out)
    print(out)
    for nm, st in rows:
        print(nm, {k: round(v, 2) for k, v in st.items()})


if __name__ == "__main__":
    main()
