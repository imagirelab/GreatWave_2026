# -*- coding: utf-8 -*-
"""FLIP39 R：座席の列（z −80 m）の断面の粒子を、細かい計算（粒子 0.3 m、茶）と E3（粒子 1 m、青）で同じ時刻に重ねて並べる（py -3.10、PIL）。
使い方: py -3.10 r_strip.py <箱の run_dir> <z> <t0> <t1> <n>   （t は群の時刻）
y はそれぞれの水面のずれ（E3 0.46 m、箱は r_seat の推定）を引いた値。断面は |z − zc| < 0.75 m（箱）・1.5 m（E3）の粒子。
"""
import sys, os, glob, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
E3 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/E3_dir20_lens"
TOFF = 35.0
FONT = r"C:/Windows/Fonts/YuGothM.ttc"


def snaps(d):
    return {int(os.path.basename(f)[5:9]): f for f in glob.glob(os.path.join(d, "snap_*.npz"))}


def main(rd, z, t0, t1, n):
    an = json.load(open(os.path.join(rd, "analysis_r.json"), encoding="utf8"))
    off = an["off_box_m"]
    sb = snaps(os.path.join(rd, "sec", "z%+04d" % int(z)))
    se = snaps(os.path.join(E3, "sec", "z%+04d" % int(z)))
    fb = np.array(sorted(sb)); fe = np.array(sorted(se))
    W, H = 640, 300
    cols = 3
    rows = int(np.ceil(n / cols))
    font = ImageFont.truetype(FONT, 18)
    im = Image.new("RGB", (cols * W, rows * H + 50), (252, 252, 250))
    dr = ImageDraw.Draw(im)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8")) if os.path.isfile(os.path.join(rd, "cfg.json")) else {"parms": {"dp": 0.3}}
    dpb = float(cfg["parms"].get("dp", 0.3))
    dr.text((10, 12), "z %.0f m の断面（茶＝箱の計算 粒子 %.2g m、青＝E3 粒子 1 m。y は静かな水面から。縦横同じ縮尺、横の目盛り 10 m・縦 5 m。灰の縦線＝E3 の座席 x 500 m、赤の縦線＝R の座席 x 530 m）" % (z, dpb), fill=(20, 20, 20), font=font)
    ts = np.linspace(t0, t1, n)
    for i, tg in enumerate(ts):
        f = int(round((tg - TOFF) * 24)) + 1
        kb = fb[np.argmin(np.abs(fb - f))]; ke = fe[np.argmin(np.abs(fe - f))] if len(fe) else None
        B = np.load(sb[kb])
        xc = float(B["x"][np.argmax(B["y"])])
        x0, x1 = xc - 70, xc + 50
        y0, y1 = -8.0, 24.0
        ox, oy = (i % cols) * W, 50 + (i // cols) * H
        sx = (W - 20) / (x1 - x0); sy = sx   # 【10/8 レビューで直した】縦横同じ縮尺（前の版は sy=(H-40)/(y1-y0) で縦が 1.57 倍だった）

        def P(x, y):
            return ox + 10 + (x - x0) * sx, oy + H - 20 - (y - y0) * sy
        for gx in np.arange(np.ceil(x0 / 10) * 10, x1, 10):
            dr.line([P(gx, y0), P(gx, y1)], fill=(232, 232, 232))
        for gy in np.arange(-5, 25, 5):
            dr.line([P(x0, gy), P(x1, gy)], fill=(232, 232, 232) if gy else (190, 190, 190))
        if x0 < 500 < x1:
            dr.line([P(500, y0), P(500, y1)], fill=(150, 150, 150), width=2)
        if x0 < 530 < x1:
            dr.line([P(530, y0), P(530, y1)], fill=(200, 60, 60), width=2)
        if ke is not None and abs(ke - f) <= 2:
            E = np.load(se[ke])
            m = (E["x"] > x0) & (E["x"] < x1)
            for x, y in zip(E["x"][m], E["y"][m] - 0.46):
                px, py = P(x, y); dr.point((px, py), fill=(60, 110, 190))
        m = (B["x"] > x0) & (B["x"] < x1) & (B["y"] > y0)
        xs_, ys_ = B["x"][m], B["y"][m] - off
        if len(xs_) > 60000:
            sel = np.random.default_rng(0).choice(len(xs_), 60000, replace=False); xs_, ys_ = xs_[sel], ys_[sel]
        for x, y in zip(xs_, ys_):
            px, py = P(x, y); dr.point((px, py), fill=(150, 90, 40))
        dr.text((ox + 14, oy + 4), "群の時刻 %.2f s（箱 f%d、E3 f%s）" % ((kb - 1) / 24 + TOFF, kb, ke), fill=(20, 20, 20), font=font)
    out = os.path.join(rd, "strip_z%+04d_vs_E3.png" % int(z))
    im.save(out)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]))
