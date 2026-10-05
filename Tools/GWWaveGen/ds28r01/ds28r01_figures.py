# -*- coding: utf-8 -*-
"""設計28修正01：Q13 の図（numpy の断面と時系列。Unity の描画ではない）。

  fig_ds28r01_q13_sections.png   主断面（行 159）と峰の行（行 192）の断面を、段階 a から t* まで、設計28 の入れた版（細い破線）と
                                 設計28修正01 の入れた版（太線）で重ね、下に同じ時間の軸で頂の高さ H/Hf・張り出し Lo/H・唇先の頂からの前への距離の曲線
  fig_ds28r01_claws_timewarp.png 爪・鉤の細部の割合 C(τ) と唇の伸び出しの進み E(τ)（T2）、画面の時刻 t での頂の高さと張り出し（T5：時間曲線を通す）
入力（読むだけ。Git 対象外）：パッケージ Unity/Build/Design/28/art_on・Unity/Build/Design/28R01/art_on、ds28r01_q13.py の出力（q13/*.json）、
関門の出力（gates/art_on_default.json、P15' の段階の時刻）、時間曲線の表（設計27 の既定・ds28r01 の既定）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01/ds28r01_figures.py [--out Docs/Evidence/Design/28R01]
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
DS27 = os.path.abspath(os.path.join(HERE, "..", "ds27"))
DS28 = os.path.abspath(os.path.join(HERE, "..", "ds28"))
for p in (DS28, DS27):
    if p not in sys.path:
        sys.path.insert(0, p)
import ds28_evidence as EV  # noqa: E402

REPO = EV.REPO
B28 = os.path.join(REPO, "Unity", "Build", "Design", "28")
BR = os.path.join(REPO, "Unity", "Build", "Design", "28R01")
font = EV.font
C_OLD = {"main": (120, 150, 200), "peak": (240, 180, 120)}
C_NEW = {"main": (20, 40, 120), "peak": (220, 100, 0)}
TAUS = [(-4.2, "a"), (-3.4, "b"), (-2.8, "c'"), (-2.4, "放出"), (-2.05, "d"), (-1.5, ""), (-1.0, ""), (-0.5, ""), (0.0, "t*")]


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def dashed(d, pts, fill, width=1, on=3):
    for i in range(0, len(pts) - 1, 2 * on):
        d.line(pts[i:i + on + 1], fill=fill, width=width)


def panel(img, box, r, key, tau, p_old, p_new, xr=(-30.0, 22.0), yr=(-3.0, 26.0)):
    K = EV.ks()
    x0, y0, w, h = box
    d = ImageDraw.Draw(img)
    s = min(w / (xr[1] - xr[0]), h / (yr[1] - yr[0]))

    def P(a, y):
        return (x0 + (a - xr[0]) * s, y0 + h - (y - yr[0]) * s)
    d.rectangle([x0, y0, x0 + w - 1, y0 + h - 1], outline=(200, 200, 200), fill=(251, 251, 251))
    for gx in range(-30, 21, 10):
        d.line([P(gx, yr[0]), P(gx, yr[1])], fill=(232, 232, 232))
    for gy in (0, 10, 20):
        d.line([P(xr[0], gy), P(xr[1], gy)], fill=(160, 175, 205) if gy == 0 else (225, 225, 225), width=2 if gy == 0 else 1)
    cj = int(np.argmax(np.where(np.arange(K.nu) <= K.crest_hi[r], K.Y[r], -np.inf)))
    a0 = K.A[r, cj]                                          # K* の頂の a（どちらの版も同じ波の枠なので、そのまま重ねる）
    out = {}
    for path, col, wid, nm in ((p_old, C_OLD[key], 1, "old"), (p_new, C_NEW[key], 2, "new")):
        A, Y, rm = EV.section_local(path, tau)
        pts = [P(a - a0, y) for a, y in zip(A[r], Y[r]) if xr[0] - 3 < a - a0 < xr[1] + 3]
        if nm == "old":
            dashed(d, pts, col, 1)
        else:
            d.line(pts, fill=col, width=wid)
        out[nm] = rm
    Hf_o = out["old"]["H"][r]
    return out


def series_H_Lo(q):
    s = q["series"]
    t = np.array(s["taus"], float)
    res = {}
    for nm in ("main", "peak"):
        H = np.array(s["H_" + nm], float)
        Lo = np.array(s["Lo_" + nm], float)
        tip = np.array(s["tipa_" + nm], float) - np.array(s["ca_" + nm], float)
        res[nm] = dict(Hn=H / H[-1], lo=Lo / H, tip=tip / H[-1], H=H)
    return t, res


def ext_start(q, nm):
    return q["results"]["T1"]["rows"][nm].get("ext_start_tau")


def fig_sections(out, q_old, q_new, gates_new):
    K = EV.ks()
    p_old = os.path.join(B28, "art_on")
    p_new = os.path.join(BR, "art_on")
    W, Hp = 212, 150
    ncol = len(TAUS)
    img = Image.new("RGB", (ncol * W + 30, 64 + 2 * (Hp + 40) + 2 * 300 + 90), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((12, 8), "Q13：唇の伸び出しと頂の上昇の重なり。細い破線＝設計28 の入れた版（既定）、太線＝設計28修正01 の入れた版（既定）。紺＝主断面 行 159、橙＝峰の行 行 192",
           fill=(0, 0, 0), font=font(17))
    d.text((12, 32), "断面：波の枠の局所座標（どちらの版も同じ枠）を K* の頂の a から測り、縦横等倍（格子 10 m）。各こまの下：H/Hf と Lo/H（左 設計28 → 右 修正01）。τ は物理の時刻（t* = 0）",
           fill=(60, 60, 60), font=font(13))
    for ri, (r, key, lab) in enumerate(((K.main_row, "main", "主断面"), (K.peak_row, "peak", "峰の行"))):
        y0 = 58 + ri * (Hp + 40)
        d.text((12, y0 + Hp // 2 - 8), "", fill=(0, 0, 0), font=font(13))
        for ci, (tau, st) in enumerate(TAUS):
            x0 = 12 + ci * W
            o = panel(img, (x0, y0, W - 8, Hp), r, key, tau, p_old, p_new)
            Hf_o = o["old"]["H"][r] / q_old["results"]["T1"]["rows"][key]["Hf_m"]
            Hf_n = o["new"]["H"][r] / q_new["results"]["T1"]["rows"][key]["Hf_m"]
            lo_o = o["old"]["Lo"][r] / max(o["old"]["H"][r], 1e-6)
            lo_n = o["new"]["Lo"][r] / max(o["new"]["H"][r], 1e-6)
            d.text((x0 + 3, y0 + 2), "%s τ %+.2f %s" % (lab, tau, st), fill=(30, 30, 30), font=font(12))
            d.text((x0 + 3, y0 + Hp + 2), "H %.2f→%.2f  Lo %.2f→%.2f" % (Hf_o, Hf_n, np.nan_to_num(lo_o), np.nan_to_num(lo_n)), fill=(60, 60, 60), font=font(12))
    # 時系列
    t_o, S_o = series_H_Lo(q_old)
    t_n, S_n = series_H_Lo(q_new)
    yb = 58 + 2 * (Hp + 40) + 6
    st_new = gates_new["stage_table"]["stage_tau_peak_row_s"] if gates_new else {"a": -4.2, "b": -3.4, "c": -2.8, "d": -2.05}
    marks = [(float(v), k) for k, v in st_new.items()] + [(-2.4, "放出")]
    Wp = (ncol * W) // 2 - 6
    for pi, nm in enumerate(("main", "peak")):
        x0 = 12 + pi * (Wp + 12)
        lab = "主断面 行 159" if nm == "main" else "峰の行 行 192"
        EV.plot_series(img, (x0, yb, Wp, 290), t_n,
                       [("修正01 H/Hf", S_n[nm]["Hn"], C_NEW[nm], 3), ("設計28 H/Hf", np.interp(t_n, t_o, S_o[nm]["Hn"]), C_OLD[nm], 2)],
                       (0.4, 1.2), "%s：頂の高さ H/Hf（縦の赤線＝T4 の表の段階（峰の行の τ）と唇先の放出）" % lab, "τ（s）", xr=(-4.6, 0.0), marks=marks)
        EV.plot_series(img, (x0, yb + 300, Wp, 290), t_n,
                       [("修正01 Lo/H", S_n[nm]["lo"], C_NEW[nm], 3), ("設計28 Lo/H", np.interp(t_n, t_o, S_o[nm]["lo"]), C_OLD[nm], 2),
                        ("修正01 唇先−頂/Hf", S_n[nm]["tip"], (40, 150, 60), 2), ("設計28 唇先−頂/Hf", np.interp(t_n, t_o, S_o[nm]["tip"]), (150, 210, 150), 1)],
                       (0.0, 0.8), "%s：張り出し Lo/H（定義 A）と唇先の頂からの前への距離 /Hf" % lab, "τ（s）", xr=(-4.6, 0.0), marks=marks)
        dd = ImageDraw.Draw(img)
        for q, col, tag in ((q_old, C_OLD[nm], "設計28"), (q_new, C_NEW[nm], "修正01")):
            te = ext_start(q, nm)
            if te is None:
                continue
            X0p, Wd = x0 + 52, Wp - 62
            px = X0p + (te + 4.6) / 4.6 * Wd
            dd.line([(px, yb + 22), (px, yb + 300 + 290 - 26)], fill=col, width=1)
            Hs = q["results"]["T1"]["rows"][nm]["H_at_start_over_Hf"]
            dd.text((X0p + 6, yb + 300 + 30 + (16 if tag == "修正01" else 0)), "%s：伸び出しの始まり（縦の細線）τ %.2f、そのときの H/Hf %.2f" % (tag, te, Hs), fill=col, font=font(12))
    yb2 = yb + 600
    d.text((12, yb2 + 4), "伸び出しの始まり＝Lo ≥ 0.05H を満たし t* まで満たし続ける最初の時刻（ds28r01_q13.py、60 Hz）。パッケージ（量子化した keypose）を ds27_gates.py と同じ Hermite で読んだ numpy の図。",
           fill=(60, 60, 60), font=font(13))
    d.text((12, yb2 + 24), "設計28：噴流の始まり（τ −2.4 s）で H 0.89、唇の伸び出しの大半は H ≥ 0.93 の最後の約 1 s。修正01：始まりで H 0.73、伸び出しの間に H は 0.7 → 1.0 と上がり続け、最高は t*。",
           fill=(120, 30, 30), font=font(13))
    img.save(out, optimize=True)


def warp(path):
    J = jload(path)
    return np.array(J["t"], float), np.array(J["tau"], float)


def fig_claws_warp(out, q_old, q_new):
    img = Image.new("RGB", (1900, 600), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((12, 8), "T2（爪・鉤の細部は唇の伸び出しとともに育つ）と T5（画面の時刻で、上昇の後半と唇の伸び出しを同じ 0.5 倍で見せる）。細い線＝設計28、太線＝設計28修正01",
           fill=(0, 0, 0), font=font(17))
    so, sn = q_old["series"], q_new["series"]
    to, tn = np.array(so["taus"], float), np.array(sn["taus"], float)
    ser = []
    for s, t, w, tag in ((so, to, 1, "設計28"), (sn, tn, 3, "修正01")):
        ser.append(("%s E 伸び出しの進み" % tag, np.interp(tn, t, s["E_median"]), (60, 60, 60), w))
        ser.append(("%s C 行の間の爪" % tag, np.interp(tn, t, s["claw_cross_frac"]), (200, 40, 40), w))
        ser.append(("%s C 行の中の鉤" % tag, np.interp(tn, t, s["hook_frac"]), (40, 90, 200), w))
    EV.plot_series(img, (12, 40, 930, 420), tn, ser, (0.0, 1.2), "爪・鉤の細部の割合 C（t* の模様への射影）と伸び出しの進み E（巻きの行の中央値）", "τ（s）", xr=(-4.0, 0.0))
    d.text((20, 466), "C：唇の前の部分の頂からの相対座標の、行の間（σ 1 m）・行の中（5 列）の高域を t* の場へ射影した係数（t* で 1）。",
           fill=(60, 60, 60), font=font(12))
    d.text((20, 482), "E：(Lo/H − 0.05)/(Lo/H(t*) − 0.05) を 0〜1 に切った値の巻きの行の中央値。",
           fill=(60, 60, 60), font=font(12))
    # T5：画面の時刻
    tw_o = warp(os.path.join(DS27, "timewarp_default.json"))
    tw_n = warp(os.path.join(HERE, "timewarp_default.json"))
    tw_a = warp(os.path.join(DS27, "timewarp_alt.json"))
    tg = np.arange(0.0, 12.0 + 1e-9, 1.0 / 60)
    res = []
    for (tt, tau), s, t, w, tag in ((tw_o, so, to, 1, "設計28・設計26 の既定"), (tw_n, sn, tn, 3, "修正01・新しい既定")):
        ta = np.interp(tg, tt, tau)
        Hn = np.interp(ta, t, np.array(s["H_peak"], float) / s["H_peak"][-1], left=np.nan)
        lo = np.interp(ta, t, np.array(s["Lo_peak"], float) / np.array(s["H_peak"], float), left=np.nan)
        rr = np.gradient(ta, tg)
        res += [("%s H/Hf" % tag, Hn, C_NEW["peak"] if w == 3 else C_OLD["peak"], w), ("%s Lo/H×2" % tag, 2 * lo, (40, 150, 60) if w == 3 else (150, 210, 150), w),
                ("%s 速さ r = dτ/dt" % tag, rr, (90, 90, 90) if w == 3 else (190, 190, 190), w)]
    EV.plot_series(img, (960, 40, 930, 420), tg, res, (0.0, 1.2), "峰の行：画面の時刻 t での頂の高さ H/Hf、張り出し 2·Lo/H、時間曲線の速さ r", "t（s）", xr=(4.0, 12.0))
    d.text((968, 466), "新しい既定：t 4.8〜5.8 s で 0.5 倍へ（τ −3.75 → −3.0 s）、t 5.8〜11.6 s は 0.5 倍の一定、t 11.6〜12 s で止める。",
           fill=(60, 60, 60), font=font(12))
    d.text((968, 482), "t = 0 の τ は −8.55 s（設計26 の既定は −10.12 s）。",
           fill=(60, 60, 60), font=font(12))
    # 画面の区間の表
    lines = []
    for (tt, tau), tag in ((tw_o, "設計26 の既定（設計28）"), (tw_n, "修正01 の既定"), (tw_a, "代案（実時間＋瞬間の停止）")):
        def t_of(tv):
            return float(np.interp(tv, tau[:int(round(12 * 240)) + 1], tt[:int(round(12 * 240)) + 1]))
        lines.append("%s：τ −3.4（b）t %.2f、−2.8（c'）t %.2f、−2.4（放出）t %.2f、−2.05（d）t %.2f、−1.0 t %.2f、t* 12.00。放出 → t* の画面の時間 %.2f s、b → 放出 %.2f s"
                     % (tag, t_of(-3.4), t_of(-2.8), t_of(-2.4), t_of(-2.05), t_of(-1.0), 12.0 - t_of(-2.4), t_of(-2.4) - t_of(-3.4)))
    for i, L in enumerate(lines):
        d.text((20, 510 + i * 22), L, fill=(30, 30, 30), font=font(14))
    img.save(out, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "Docs", "Evidence", "Design", "28R01"))
    ap.add_argument("--q-old", default=os.path.join(BR, "q13", "ds28_art_on.json"))
    ap.add_argument("--q-new", default=os.path.join(BR, "q13", "art_on.json"))
    ap.add_argument("--gates", default=os.path.join(BR, "gates", "art_on_default.json"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    q_old, q_new = jload(a.q_old), jload(a.q_new)
    gates = jload(a.gates) if os.path.isfile(a.gates) else None
    p1 = os.path.join(a.out, "fig_ds28r01_q13_sections.png")
    fig_sections(p1, q_old, q_new, gates)
    p2 = os.path.join(a.out, "fig_ds28r01_claws_timewarp.png")
    fig_claws_warp(p2, q_old, q_new)
    print(json.dumps(dict(figures=[EV.rel(p1), EV.rel(p2)]), ensure_ascii=False))


if __name__ == "__main__":
    main()
