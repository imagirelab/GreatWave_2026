# -*- coding: utf-8 -*-
"""仕上げ27 の修正 1 回目：バックログ 111（座席の上へ延びた水面の先が下向きに曲がる過程）の、唇先の向きと 1 コマの移動の図（1920×1080）。

入力は pl27_seat_items.py の出力（seat_items_F_final.json と *_series.npz。採用の動き F_final、座席 v1 の固定の目、体験の時刻 t の 30 Hz）。
上：座席の近くの行（c が座席 ±3 m）の唇先の向き（唇の上面の最後の 8 列の弦の、断面の中の水平からの角の中央値。負が下向き）と、美術優先30 の
    式の t* の条件（< −20°）。
下：唇先の 1 コマの移動（行の最大）を、地面（世界。美術優先30 の測り方で、波の約 20 m/s の進みを含む）と波の枠（局所）の 2 つで描き、
    美術優先30 の 0.6 m の目安を引く。
111 の美術優先30 の式（af30_evidence.py の ok111）は連続性の検査一式（P13）を含まないので、合否は唇先の移動の読みだけで決まることを示す。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_111.py --items Unity/Build/Polish/27/seat_items/seat_items_F_final.json \
      --out Docs/Evidence/Polish/27/fig_pl27_111_tip.png
"""
import argparse
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FONT = "C:/Windows/Fonts/YuGothM.ttc"


def ab(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    J = json.load(open(ab(a.items), encoding="utf-8"))
    Z = np.load(os.path.splitext(ab(a.items))[0] + "_series.npz")
    it = J["items"]["111"]
    v = it["value"]
    t = Z["t"]
    tip = Z["tip_dir_deg"]
    jg = Z["tip_jump_m"]
    jw = Z["tip_jump_wave_frame_m"]
    W, H = 1920, 1080
    im = Image.new("RGB", (W, H), (250, 248, 242))
    dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 27)
    f2 = ImageFont.truetype(FONT, 20)
    f3 = ImageFont.truetype(FONT, 17)
    dr.text((30, 12), "仕上げ27 修正 1 回目：111（座席の上の唇先が下向きに曲がる）― 美術優先30 の式の合否は、唇先の 1 コマの移動の読みだけで決まる",
            fill=(20, 30, 60), font=f1)
    dr.text((30, 50), "採用の動き F_final（K*′ R4）、座席 v1 の固定の目、体験の時刻 t（30 Hz、t* = 12 s）。包みの幾何の測定で、描画ではない。"
            "美術優先30 の式（af30_evidence.py の ok111）は連続性の検査一式（P13）を含まない", fill=(60, 60, 60), font=f3)

    def panel(box, title, xr, yr, series, hlines, xlabel, xticks, yticks, yfmt):
        x0, y0, x1, y1 = box
        dr.rectangle(box, outline=(120, 120, 120), fill=(255, 255, 255))
        dr.text((x0, y0 - 30), title, fill=(20, 30, 60), font=f2)

        def X(q):
            return x0 + (q - xr[0]) / (xr[1] - xr[0]) * (x1 - x0)

        def Y(q):
            return y1 - (min(max(q, yr[0]), yr[1]) - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
        for q in xticks:
            dr.line([X(q), y0, X(q), y1], fill=(230, 230, 230))
            dr.text((X(q) - 10, y1 + 6), "%g" % q, fill=(60, 60, 60), font=f3)
        for q in yticks:
            dr.line([x0, Y(q), x1, Y(q)], fill=(230, 230, 230))
            dr.text((x0 - 62, Y(q) - 10), yfmt % q, fill=(60, 60, 60), font=f3)
        dr.line([X(12.0), y0, X(12.0), y1], fill=(120, 120, 200), width=2)
        dr.text((X(12.0) + 6, y0 + 6), "t*", fill=(80, 80, 180), font=f2)
        for hv, lab in hlines:
            dr.line([x0, Y(hv), x1, Y(hv)], fill=(200, 40, 40), width=2)
            dr.text((x0 + 8, Y(hv) - 24), lab, fill=(200, 40, 40), font=f3)
        dr.text(((x0 + x1) // 2 - 80, y1 + 30), xlabel, fill=(60, 60, 60), font=f3)
        ly = y0 + 10
        for xs, ys, col, lab, wdt in series:
            pts = [(X(x), Y(y)) for x, y in zip(xs, ys) if np.isfinite(y)]
            if len(pts) > 1:
                dr.line(pts, fill=col, width=wdt)
            dr.line([x0 + 700, ly + 10, x0 + 740, ly + 10], fill=col, width=4)
            dr.text((x0 + 748, ly), lab, fill=(30, 30, 30), font=f3)
            ly += 26

    its = int(np.argmin(np.abs(t - 12.0)))
    panel((110, 130, 1880, 470), "唇先の向き（座席の近くの行の中央値。負が下向き）", (0.0, 14.0), (-130.0, 50.0),
          [(t, tip, (60, 110, 200), "唇先の向き　t* %.2f°、1 コマの向きの変化の最大 %.3f°" % (tip[its], v["tip_dir_step_max_deg_per_frame"]), 3)],
          [(-20.0, "美術優先30 の t* の条件 < −20°")], "体験の時刻 t（s）", list(range(0, 15)), [-120, -90, -60, -30, 0, 30], "%.0f°")
    panel((110, 560, 1880, 900), "唇先の 1 コマの移動（座席の近くの行の最大）", (0.0, 14.0), (0.0, 0.8),
          [(t, jg, (150, 150, 150), "地面（世界。美術優先30 の測り方）　最大 %.4f m　→ 0.6 m を超える" % v["tip_jump_max_m_per_frame"], 3),
           (t, jw, (200, 110, 20), "波の枠（局所。波の約 20 m/s の進みを除く）　最大 %.4f m" % v["tip_jump_max_m_per_frame_wave_frame"], 4)],
          [(0.6, "美術優先30 の目安 0.6 m（その場で育つ rig の値）")], "体験の時刻 t（s）", list(range(0, 15)), [0.0, 0.2, 0.4, 0.6, 0.8], "%.1f")
    vd = {k: s for k, s in it.items() if k.startswith("verdict")}
    lines = ["判定（111）：美術優先30 の式　地面の移動の読み %s（満たさない条件：%s）　／　波の枠の移動の読み %s" % (
                 vd["verdict_af30_formula"], "・".join(v["af30_formula_failed"]) or "なし", vd["verdict_af30_formula_wave_frame"]),
             "項目の言葉の読み（t* = K* の代わりに位置跳び・欠落 0）：地面 %s ／ 波の枠 %s。連続性の検査一式（P13 の 4 項目の不合格）は、111 の判定に入らない"
             "（初めの版の道具は入れていた。修正 1 回目で直した）" % (vd["verdict_item_words"], vd["verdict_item_words_wave_frame"]),
             "どちらの読みを受入に使うかは仕上げ28 の受入で決める（仕上げ27 では地面の読み＝美術優先30 の測り方のまま、不合格と書く）"]
    y = 960
    for s in lines:
        dr.text((40, y), s, fill=(20, 30, 60), font=f3)
        y += 30
    os.makedirs(os.path.dirname(ab(a.out)), exist_ok=True)
    im.save(ab(a.out), optimize=True)
    print("図", a.out)


if __name__ == "__main__":
    main()
