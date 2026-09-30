# -*- coding: utf-8 -*-
"""仕上げ27：関門 P2・P3 の直す前（F_final）と後（F_p27）を、同じ時刻・同じ行で並べた図（1920×1080）。

入力は pl27_diag.py の出力（*_series.npz と JSON）。P2 は 225 m の窓の |A_net|/A_pos の、時刻ごとの巻きの行の最大（判定の区間 τ ≤ −2.0 s）。
直す前は元の標本（a −330 m から）の値と、標本を広げた値（窓の欠けを除いた値）の両方を描く。P3 は行ごとの値（噴流の始まりから τ −2.0 s）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_fig_gates.py --before Unity/Build/Polish/27/diag/diag_F_final.json \
      --after Unity/Build/Polish/27/diag/diag_F_p27.json --out Docs/Evidence/Polish/27/fig_pl27_p2_p3_before_after.png
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


def load(jp):
    J = json.load(open(ab(jp), encoding="utf-8"))
    Z = np.load(os.path.splitext(ab(jp))[0] + "_series.npz")
    return J, Z


def ratio(An, Ap):
    return np.where(Ap >= 1.0, np.abs(An) / np.maximum(Ap, 1e-9), np.nan)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    Jb, Zb = load(a.before)
    Ja, Za = load(a.after)
    W, H = 1920, 1080
    im = Image.new("RGB", (W, H), (250, 248, 242))
    dr = ImageDraw.Draw(im)
    f1 = ImageFont.truetype(FONT, 28)
    f2 = ImageFont.truetype(FONT, 20)
    f3 = ImageFont.truetype(FONT, 17)
    dr.text((30, 14), "仕上げ27：関門 P2・P3 の直す前（F_final）と後（F_p27：num_sea_sample_range・num_balance_swell_calm）", fill=(20, 30, 60), font=f1)

    def panel(box, title, xr, yr, series, hline, xlabel, xticks, yticks):
        x0, y0, x1, y1 = box
        dr.rectangle(box, outline=(120, 120, 120), fill=(255, 255, 255))
        dr.text((x0, y0 - 30), title, fill=(20, 30, 60), font=f2)

        def X(v):
            return x0 + (v - xr[0]) / (xr[1] - xr[0]) * (x1 - x0)

        def Y(v):
            return y1 - (min(max(v, yr[0]), yr[1]) - yr[0]) / (yr[1] - yr[0]) * (y1 - y0)
        for t in xticks:
            dr.line([X(t), y0, X(t), y1], fill=(230, 230, 230))
            dr.text((X(t) - 14, y1 + 6), ("%g" % t), fill=(60, 60, 60), font=f3)
        for v in yticks:
            dr.line([x0, Y(v), x1, Y(v)], fill=(230, 230, 230))
            dr.text((x0 - 52, Y(v) - 10), "%.2f" % v, fill=(60, 60, 60), font=f3)
        dr.line([x0, Y(hline), x1, Y(hline)], fill=(200, 40, 40), width=2)
        dr.text((x1 - 170, Y(hline) - 24), "しきい値 %.2f" % hline, fill=(200, 40, 40), font=f3)
        dr.text(((x0 + x1) // 2 - 60, y1 + 30), xlabel, fill=(60, 60, 60), font=f3)
        ly = y0 + 10
        for xs, ys, col, lab, wdt in series:
            pts = [(X(x), Y(y)) for x, y in zip(xs, ys) if np.isfinite(y)]
            if len(pts) > 1:
                dr.line(pts, fill=col, width=wdt)
            dr.line([x0 + 14, ly + 10, x0 + 54, ly + 10], fill=col, width=4)
            dr.text((x0 + 62, ly), lab, fill=(30, 30, 30), font=f3)
            ly += 26

    # ---- P2：時刻ごとの最大（判定の区間 τ ≤ −2.0 s）
    tb = Zb["taus"]
    jb = tb <= -2.0 + 1e-9
    Rb = ratio(Zb["An"], Zb["Ap"])
    RbE = ratio(Zb["AnE"], Zb["ApE"])
    Ra = ratio(Za["An"], Za["Ap"])
    ta = Za["taus"]
    ja = ta <= -2.0 + 1e-9
    mb = np.nanmax(np.where(np.isfinite(Rb), Rb, -1), 1)
    mbE = np.nanmax(np.where(np.isfinite(RbE), RbE, -1), 1)
    ma = np.nanmax(np.where(np.isfinite(Ra), Ra, -1), 1)
    panel((110, 110, 1880, 500), "P2：225 m の窓の |A_net| / A_pos（巻きの行の最大、時刻ごと。判定の区間 τ ≤ −2.0 s）", (-12.0, -2.0), (0.0, 0.5),
          [(tb[jb], mb[jb], (150, 150, 150), "直す前 F_final（元の標本 a ≥ −330 m。τ −10.8 s まで窓が欠ける）　最大 %.3f" % Jb["P2"]["all"]["max"], 3),
           (tb[jb], mbE[jb], (60, 110, 200), "直す前 F_final（標本を a ≥ −480 m へ広げて測った値）　最大 %.3f" % Jb["P2_ext"]["all"]["max"], 3),
           (ta[ja], ma[ja], (200, 110, 20), "直した後 F_p27　最大 %.3f" % Ja["P2"]["all"]["max"], 4)],
          0.2, "物理の時刻 τ（s）", [-12, -11, -10, -9, -8, -7, -6, -5, -4, -3, -2], [0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    # ---- P3：行ごとの値
    def p3_rows(J):
        top = J["P3"]
        return top
    rows_b = Zb["rows"]

    def p3_series(Z, J):
        taus = Z["taus"]
        rows = Z["rows"]
        An, Ap = Z["An"], Z["Ap"]
        on = {}
        GJ = json.load(open(ab(J["gates_json"]), encoding="utf-8"))
        for k, v in GJ["onset_tau_by_row"].items():
            if v is not None:
                on[int(k)] = float(v)
        judge = taus <= -2.0 + 1e-9
        out = np.full(len(rows), np.nan)
        for i, r in enumerate(rows):
            if int(r) not in on:
                continue
            m_all = taus >= on[int(r)] - 1e-9
            m = m_all & judge
            if not m.any():
                continue
            k0 = int(np.nonzero(m_all)[0][0])
            out[i] = float(np.abs(An[m, i] - An[k0, i]).max() / max(Ap[-1, i], 1e-9))
        return rows, out
    rb, vb = p3_series(Zb, Jb)
    ra, va = p3_series(Za, Ja)
    panel((110, 620, 1880, 1000), "P3：前面が鉛直になってから τ −2.0 s までの窓の A_net の変化 / t* の A_pos（巻きの行ごと）", (float(rb.min()), float(rb.max())), (0.0, 0.2),
          [(rb, vb, (60, 110, 200), "直す前 F_final　最大 %.4f（行 %s）" % (Jb["P3"]["max"], Jb["P3"]["worst_row"]), 3),
           (ra, va, (200, 110, 20), "直した後 F_p27　最大 %.4f（行 %s）" % (Ja["P3"]["max"], Ja["P3"]["worst_row"]), 4)],
          0.10, "K*′ の行の番号（行 164 = 主断面、c = 0）", list(range(50, 200, 25)), [0.0, 0.05, 0.10, 0.15, 0.2])
    os.makedirs(os.path.dirname(ab(a.out)), exist_ok=True)
    im.save(ab(a.out), optimize=True)
    print("図", a.out)


if __name__ == "__main__":
    main()
