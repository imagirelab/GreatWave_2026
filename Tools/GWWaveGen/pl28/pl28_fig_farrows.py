# -*- coding: utf-8 -*-
"""仕上げ28：奥の行（c +12〜+14 m）の唇の前の頂の尖り（M7）の前後の図（1920×1080 の PNG）。
上段：行の断面（波の枠の局所の a・y）の上の部分を、同じ行・同じ τ で重ねる（灰＝直す前 G_final、緑＝直した後）。
下段：その行の頂の ±2 m 弦角の時間の変化（唇ができる前だけ。pl28_fr_motion の motion_<版>.npz）。110° の線を引く。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_fig_farrows.py --before G_final --after G_p28b --rows 226,230,233 --taus -2.45,-2.2,-2.05 --out <png>
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import pl28_f71_geom as GM  # noqa: E402

B = os.path.join(REPO, "Unity", "Build", "Polish", "28")
FONT = r"C:\Windows\Fonts\meiryo.ttc"


def F(sz):
    return ImageFont.truetype(FONT, sz)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default="G_final")
    ap.add_argument("--after", default="G_p28b")
    ap.add_argument("--rows", default="226,230,233")
    ap.add_argument("--taus", default="-2.45,-2.2,-2.05")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    meta = json.load(open(os.path.join(B, "kstar_p28", "kstarP28R2_a45_meta.json"), encoding="utf-8"))
    T = np.asarray(meta["frame"]["t_travel"], float)
    cm = np.asarray(meta["rows"]["c_m"], float)
    rows = [int(x) for x in a.rows.split(",")]
    taus = [float(x) for x in a.taus.split(",")]
    pk = {k: GM.Pkg(os.path.join(B, k, "art_on")) for k in (a.before, a.after)}
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    d.text((16, 8), "奥の行の唇の前の頂の尖り（M7）：灰＝%s（直す前）、緑＝%s（ds_far_hook_earlier）。同じ行・同じ物理の時刻 τ" % (a.before, a.after), fill=(0, 0, 0), font=F(22))
    d.text((16, 40), "上：行の断面の上の部分（波の枠の局所、進む向き a → 右、高さ y ↑、1 m ＝ 18 px）。下：頂の ±2 m 弦角（唇ができる前、画面の時刻）。赤の線 110°", fill=(70, 70, 70), font=F(15))
    cw = (W - 40) // len(taus)
    sc = 18.0
    for j, tau in enumerate(taus):
        for i, r in enumerate(rows):
            x0 = 20 + j * cw
            y0 = 80 + i * 170
            d.rectangle([x0, y0, x0 + cw - 10, y0 + 160], outline=(200, 200, 200))
            d.text((x0 + 6, y0 + 4), "行 %d（c %+.1f m）τ %.2f" % (r, cm[r], tau), fill=(0, 0, 0), font=F(14))
            prof = {}
            for k, p in pk.items():
                X = (p.world(tau) - np.array([np.interp(tau, p.ftau, p.forg[:, q]) for q in range(3)])).reshape(p.nv, p.nu, 3)
                A, Y = X[r] @ T, X[r, :, 1]
                prof[k] = (A, Y)
            A0, Y0 = prof[a.before]
            jc = int(np.argmax(Y0[18:395])) + 18
            ac, yc = A0[jc], Y0[jc]
            for k, col, wd in ((a.before, (150, 150, 150), 4), (a.after, (20, 150, 60), 2)):
                A, Y = prof[k]
                m = (Y > yc - 7.0) & (np.abs(A - ac) < 14)
                pts = [(x0 + (cw - 10) / 2 + (A[q] - ac) * sc, y0 + 150 - (Y[q] - (yc - 7.0)) * sc) for q in range(len(A)) if m[q]]
                if len(pts) > 1:
                    d.line(pts, fill=col, width=wd)
    # 下：弦角の時間
    y0 = 80 + len(rows) * 170 + 10
    ph = H - y0 - 30
    d.rectangle([20, y0, W - 20, y0 + ph], outline=(200, 200, 200))
    zz = {k: np.load(os.path.join(B, "motion", "fr", "motion_%s.npz" % k)) for k in (a.before, a.after)}
    t_lo, t_hi, c_lo, c_hi = 5.0, 8.5, 70.0, 180.0
    X = lambda t: 70 + (t - t_lo) / (t_hi - t_lo) * (W - 120)  # noqa: E731
    Yv = lambda c: y0 + ph - 10 - (c - c_lo) / (c_hi - c_lo) * (ph - 20)  # noqa: E731
    for c in (90, 110, 125, 150, 180):
        d.line([(70, Yv(c)), (W - 50, Yv(c))], fill=(230, 60, 60) if c == 110 else (225, 225, 225), width=2 if c == 110 else 1)
        d.text((26, Yv(c) - 9), "%d°" % c, fill=(90, 90, 90), font=F(13))
    for t in np.arange(5.0, 8.51, 0.5):
        d.text((X(t) - 12, y0 + ph + 4), "t %.1f" % t, fill=(90, 90, 90), font=F(13))
    for k, col in ((a.before, (150, 150, 150)), (a.after, (20, 150, 60))):
        z = zz[k]
        t, ch, lo, Hh = z["t"], z["chord"], z["lo"], z["H"]
        Hf = Hh[-1]
        for r in rows:
            pre = (lo[:, r] < 0.05) & (Hh[:, r] >= 0.3 * Hf[r]) & np.isfinite(ch[:, r]) & (t >= t_lo) & (t <= t_hi)
            pts = [(X(t[q]), Yv(ch[q, r])) for q in np.nonzero(pre)[0]]
            if len(pts) > 1:
                d.line(pts, fill=col, width=2)
            if pts:
                d.text((pts[-1][0] + 4, pts[-1][1] - 8), str(r), fill=col, font=F(12))
    img.save(a.out)
    print("fig", a.out)


if __name__ == "__main__":
    main()
