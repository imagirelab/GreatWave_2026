# -*- coding: utf-8 -*-
"""FLIP48：計算の動画と確かめの図（py -3.10 -B、numpy・scipy・scikit-image・PIL・ffmpeg）。2026-10-15 新しく書いた。
FLIP46 の g46_video.py（Tools/GWWaveGen/flip46、変えていない）をこの起動の中だけ読み替えて使う（ファイルは書き換えない）：
  - 記録の読み：g48_analyze.Ctx48（棚のある海底。断面の砂の色・上からの図の等深線も棚の形になる）。出力は Unity/Build/FLIP48 の中だけ。
  - 頭書き（heads）：FLIP48 の尾根・棚・孤立波の値と「選んだ物・計算した物」の一行。
  - 横からの断面（section）：GG06 の崩れる点 x 273.5 m の赤い印を出さない（巻き始めの青い印は出す）。
  - 1 コマの 4 つの図（render）：下の段を、斜め上から（左）と頂の高さの横の分け方 c(y)（右。2 Hc・4 Hc と横の端の帯の印）に分けた。
  - 拡大の時刻（key_times）：巻き始めがなければ記録の後ろ 40 % から選ぶ（GG06 の t' を使わない）。
使い方：py -3.10 -B g48_video.py <記録> [g46_video と同じ引数：--only=video,zoom,mesh,boat --t0= --t1= --still= --boat_d= ...]
出す物：<記録>/video/<名前>_4view.mp4 ほか（g46_video と同じ）。どの計算も mp4 を出す（この研究の決まり）。
"""
import os, sys, json, math

sys.dont_write_bytecode = True
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, _HERE)
import numpy as np                  # noqa: E402
from PIL import Image, ImageDraw     # noqa: E402
import g48_common as GC             # noqa: E402
import g48_analyze as A48           # noqa: E402  （読み込むと g46_analyze の Ctx・B46 がこの起動の中だけ FLIP48 用になる）
import g46_video as V46             # noqa: E402
import g48_peak_metrics as PM       # noqa: E402

for _nm in ("Data", "section", "plan_view", "zoom_window", "render", "heads", "key_times", "main", "V45"):
    if not hasattr(V46, _nm):
        raise SystemExit("g46_video.py に %s がない（FLIP46 の道具が変わった。g48_video.py を直す）" % _nm)
V45 = V46.V45
font = V46.font
W, H = V46.W, V46.H
_section46 = V46.section


def section48(im, dr, D, f, box, xr0, xr1, z0, z1, title, tick=50.0, marks=True, scale_label=True):
    """g46_video.section から GG06 の崩れる点の赤い印だけを除いた物（巻き始めの青い印は出す）。"""
    ph = _section46(im, dr, D, f, box, xr0, xr1, z0, z1, title, tick=tick, marks=False, scale_label=scale_label)
    if marks and D.ana.get("onset"):
        px0, py0, px1 = box
        s = (px1 - px0) / (xr1 - xr0)
        xo = D.ana["onset"]["xc"]
        if xr0 <= xo <= xr1:
            X = px0 + (xo - xr0) * s
            dr.polygon([(X, py0 + 2), (X - 6, py0 + 12), (X + 6, py0 + 12)], fill=V46.BLUE_MARK)
    return ph


def heads48(D, opt):
    cx = D.cx
    b = cx.cfg.get("bed") or {}
    sol = cx.cfg.get("solitary") or {}
    coarse = "（粗い）" if cx.dp > 0.25 + 1e-9 else ""
    head = "FLIP48 %s：尾根 k %s・真ん中 1:%s・棚 %s m に、孤立波 H0/h0 %s（まっすぐな頂）。粒子 %.4g m（格子 %.4g m）%s。力は重力だけ。%s" % (
        D.name, b.get("k"), _g(b.get("s")), _g(b.get("h_sh")), _g(sol.get("H0_nd")), cx.dp, cx.vox, coarse, opt.get("label", ""))
    # 2026-10-15 R3 の試し：先細り・溝・段・前の谷があれば頭書きに足す（選んだ形を書かずに見せないため）
    ex = []
    if b.get("k_end") is not None:
        ex.append("先細り k→%s" % _g(b.get("k_end")))
    if (b.get("ch_h") or 0) > 0:
        ex.append("横の遠くの溝 %s m" % _g(b.get("ch_h")))
    if (b.get("s1") or 0) > 0:
        ex.append("段 1:%s・%s m" % (_g(b.get("s2")), _g(b.get("dL"))))
    w = cx.cfg.get("wave") or {}
    if w.get("kind") == "nwave":
        ex.append("前の谷 β %s（定常な解ではない）" % _g(w.get("beta")))
    if ex:
        head = head.replace("（まっすぐな頂）。", "（まっすぐな頂）＋%s。" % "・".join(ex), 1)
    sub = ("縦横同じ縮尺。高さは静かな水面から（点線、ずれ %.3f m を引いた）。半分の幅を解き、y = 0 は対称の面、y = %g m は壁。"
           "選んだ物：振幅と海底。計算した物：真ん中の伸び・崩れ・巻き" % (D.off, cx.y_max))
    return head, sub


def _g(v):
    return "—" if v is None else ("%g" % v)


def key_times48(D):
    on = D.ana.get("onset") or {}
    if on:
        return V46.__dict__["_key_times46"](D)
    t_last = D.t(D.frames[-1]); t_first = D.t(D.frames[0])
    return list(np.linspace(t_first + 0.6 * (t_last - t_first), t_last, 6))


_LAT = {}


def lateral_strip(im, dr, D, f, box):
    """頂の高さの横の分け方 c(y)（hf。y = 0 で写して全幅）。2 Hc・4 Hc の線と横の端の帯。"""
    px0, py0, px1, py1 = box
    if "hf" not in _LAT:
        _LAT["hf"] = PM.load_hf(D.rd)
        _LAT["idx"] = {int(fr): i for i, fr in enumerate(_LAT["hf"]["frames"])}
    Hh = _LAT["hf"]
    i = _LAT["idx"].get(int(f))
    dr.text((px0, py0 - 26), "頂の高さの横の分け方 c(y)（x %g〜%g m の最大）" % (PM.X_MIN, D.cx.x_max - PM.X_END_PAD), fill=V46.TXT, font=font(18, True))
    dr.rectangle([px0, py0, px1, py1], outline=(120, 120, 120))
    if i is None:
        return
    c, _ = PM.crest_profile(Hh["eta"][i], Hh["xs"], PM.X_MIN, D.cx.x_max - PM.X_END_PAD)
    c = c - D.off
    ys = Hh["ys"]
    yy = np.concatenate([-ys[::-1], ys]); cc = np.concatenate([c[::-1], c])
    hi = max(10.0, float(np.nanmax(cc)) + 1.0) if np.isfinite(cc).any() else 10.0
    L, R, T, B = px0 + 44, px1 - 10, py0 + 10, py1 - 28
    X = lambda v: L + (v - yy[0]) / max(yy[-1] - yy[0], 1e-9) * (R - L)
    Y = lambda v: B - v / hi * (B - T)
    for g in range(0, int(hi) + 1, 4):
        dr.line([(L, Y(g)), (R, Y(g))], fill=(225, 225, 225)); dr.text((px0 + 4, Y(g) - 8), "%d m" % g, fill=V46.SUB, font=font(12))
    Hc = (D.ana.get("onset") or {}).get("eta_c")
    if Hc:
        for mlt, col in ((2, (200, 150, 60)), (4, (200, 90, 60))):
            for sgn in (-1, 1):
                xv = sgn * mlt * Hc
                if yy[0] <= xv <= yy[-1]:
                    dr.line([(X(xv), T), (X(xv), B)], fill=col, width=1)
            if mlt * Hc <= yy[-1]:
                dr.text((X(mlt * Hc) + 2, T), "%d Hc" % mlt, fill=col, font=font(12))
    sb = PM.side_band(D.cx.y_max)
    if D.cx.y_max > 12.0:
        for sgn in (-1, 1):
            a_, b_ = sorted((X(sgn * sb[0]), X(sgn * sb[1])))
            dr.rectangle([a_, B - 5, b_, B], fill=(170, 170, 170))
    pts = [(X(a), Y(max(b, 0.0))) for a, b in zip(yy, cc) if np.isfinite(b)]
    if len(pts) > 1:
        dr.line(pts, fill=(30, 70, 150), width=3)
    lt = PM.lateral(c, ys, band=sb)
    txt = "c0 %.2f m" % lt["c0"]
    if lt.get("ratio_side"):
        txt += "  c0/c_side %.2f" % lt["ratio_side"]
    if lt.get("half_excess_width_m"):
        txt += "  半分の幅 %.0f m" % lt["half_excess_width_m"]
    dr.text((L, B + 6), txt, fill=V46.TXT, font=font(14))


def render48(D, f, head, sub):
    im = Image.new("RGB", (W, H), V46.BG); dr = ImageDraw.Draw(im)
    cx = D.cx
    t = D.t(f)
    dr.text((40, 14), head, fill=V46.TXT, font=font(21, True))
    dr.text((40, 46), sub, fill=V46.SUB, font=font(15))
    dr.text((W - 330, 14), "t = %6.2f s" % t, fill=V46.TXT, font=font(26, True))
    on = D.ana.get("onset") or {}
    if on:
        dr.text((W - 330, 50), "巻き始め t %.2f s・x %.0f m" % (on["t"], on["xc"]), fill=V46.SUB, font=font(15))
    zlo = -cx.h0
    ph = section48(im, dr, D, f, (60, 110, W - 60), cx.x_min, cx.x_max, zlo, 16.0, "横から（y = 0 の断面。砂の色は真ん中の海底：1:%s で棚 %s m へ）" % (
        _g((cx.cfg.get("bed") or {}).get("s")), _g((cx.cfg.get("bed") or {}).get("h_sh"))))
    yb = 110 + ph + 64
    lo, hi = -4.0, 10.0
    V46.plan_view(im, dr, D, f, (60, yb, 920, yb + 400), "上から（高さ %+g〜%+g m、y = 0 で写して全幅。線は海底の等深線）" % (lo, hi), lo, hi)
    xz0, xz1 = V46.zoom_window(D)
    section48(im, dr, D, f, (980, yb, W - 60), xz0, xz1, max(zlo, -8.0), 16.0, "y = 0 の断面の拡大（x %.0f〜%.0f m）" % (xz0, xz1), tick=10.0)
    yo = 760
    xlo = float((cx.cfg.get("bed") or {}).get("x_toe", 143.0)) - 20.0
    V45.oblique(im, dr, D, f, (60, yo + 30, 1240, H - 10), "斜め上から（y = 0〜%g m を 6 m ごと、x %.0f〜%.0f m）" % (cx.y_max, xlo, cx.x_max),
                ymax=cx.y_max, x_lo=xlo, x_hi=cx.x_max)
    lateral_strip(im, dr, D, f, (1300, yo + 30, W - 60, H - 10))
    return im


# この起動の中だけ読み替える
V46.__dict__["_key_times46"] = V46.key_times
V46.section = section48
V46.heads = heads48
V46.key_times = key_times48
V46.render = render48

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    V46.main()
