# -*- coding: utf-8 -*-
"""FLIP42：1 本または 2 本の計算の図（PIL だけで描く。matplotlib はこの機械の Python に入っていない）。
py -3.10 g_figs.py <out_dir> <run_id> [<run_id2>]
図（字は日本語）：
  xt_<run>.png      水面の高さの時間と場所の図（群が集まる様子）。線形の焦点と D&K の着水の点
  gauges.png        測る点の水面の時系列（計算と線形の値）
  spectra.png       帯の出口と −15 の点の、線形の値に対する比（振幅・位相）と、間の速さの誤差
  crestmax.png      各場所の最大の頂（計算と線形）
  series.png        断面の範囲の頂の高さ η_c・波高 H・前の面の最大の傾き（時刻ごと）
  shapes.png        頂の時刻の前後（−0.3〜+0.3 Tc）の断面の形（2 本なら上下に並べる）
"""
import sys, os, json
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A
import g_plot as GP

PAL = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (255, 127, 14), (148, 103, 189)]


def xp_of(rid):
    return json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))["parms"]["x_p"]


def ana(rid):
    return json.load(open(os.path.join(A.ROOT, rid, "ana.json"), encoding="utf8"))


def fig_xt(out, rid, P, C):
    D = A.load_hf(rid); a = ana(rid)
    EX = A.zmean(D) - a["still_level_offset_m"]
    xp = xp_of(rid)
    xm = (D["x"] >= xp) & (D["x"] <= xp + 930)
    X = D["x"][xm] - xp; T = D["t"]
    E = EX[:, xm]
    W, Hh = 1500, 900
    sh = GP.Sheet(W, Hh, "%s：水面の高さ（静かな水面から、m）の時間と場所の図。群が集まる様子" % rid)
    box = (110, 90, 1300, 820)
    ax = GP.Ax(sh, box, (0, 930), (0, 188), xlabel="造波板からの距離（m）", ylabel="時刻（s）",
               xticks=np.arange(0, 931, 100), yticks=np.arange(0, 189, 20))
    x0, y0, x1, y1 = box
    nxp, nyp = x1 - x0, y1 - y0
    xi = np.clip(((np.arange(nxp) + 0.5) / nxp * 930 / (X[1] - X[0])).astype(int), 0, len(X) - 1)
    ti = np.clip(((1 - (np.arange(nyp) + 0.5) / nyp) * 188 * 24).astype(int), 0, len(T) - 1)
    img = GP.colormap(E[ti][:, xi], -8, 8)
    sh.im.paste(Image.fromarray(img), (x0, y0)); sh.d = ImageDraw.Draw(sh.im); ax.d = sh.d
    sh.d.rectangle(box, outline=(0, 0, 0))
    ax.rings([C["xb"]], [C["tb"]], col=(0, 0, 0), r=8, label="線形の焦点（592 m・171.5 s）")
    ax.points([P["full"]["xob_DK"]], [P["full"]["tob_DK"]], col=(0, 160, 0), r=6, label="D&K の着水（584.5 m・159.3 s）")
    if a.get("onset"):
        ax.points([a["onset"]["xc_rel"]], [a["onset"]["t"]], col=(255, 0, 255), r=6, label="巻き始め（この計算）")
    ax.legend("tl")
    # 色の見本
    for i in range(200):
        v = 8 - 16 * i / 199
        c = tuple(int(q) for q in GP.colormap(np.array([v]), -8, 8)[0])
        sh.d.line([(1330, 120 + i * 3), (1360, 120 + i * 3)], fill=c, width=3)
    sh.text((1366, 112), "+8 m", 13); sh.text((1366, 712), "−8 m", 13); sh.text((1366, 412), "0", 13)
    sh.save(os.path.join(out, "xt_%s.png" % rid))


def fig_gauges(out, rids, P, C):
    names = list(P["gauges"].keys())
    W, Hh = 1500, 220 * len(names) + 100
    sh = GP.Sheet(W, Hh, "測る点の水面（静かな水面から）：計算と線形の重ね合わせ（造波板の位置の目標を線形で進めた値）")
    xp = P["tank"]["x_p"]
    Ds = [(rid, A.load_hf(rid), ana(rid)) for rid in rids]
    for gi, g in enumerate(names):
        xr = P["gauges"][g]["x_rel"]
        box = (90, 90 + gi * 220 + 40, W - 40, 90 + gi * 220 + 190)
        lab = "帯の出口" if g == "band_exit" else g
        ax = GP.Ax(sh, box, (40, 188), (-9, 13), xlabel="時刻（s）" if gi == len(names) - 1 else "", ylabel="m",
                   title="%s（造波板から %.1f m）" % (lab, xr), xticks=np.arange(40, 189, 20), yticks=[-8, -4, 0, 4, 8, 12])
        ax.hline(0)
        t = Ds[0][1]["t"]
        el = A.lin_series(C, xr, t[t <= P["tank"]["t_end"] + 1e-9])
        ax.line(t[:len(el)], el, col=(120, 120, 120), w=1, label="線形")
        for k, (rid, D, a) in enumerate(Ds):
            em = A.gauge(A.zmean(D) - a["still_level_offset_m"], D["x"], xp_of(rid) + xr)
            ax.line(D["t"], em, col=PAL[k], w=1, label=rid)
        if gi == 0:
            ax.legend("tl")
    sh.save(os.path.join(out, "gauges.png"))


def fig_spectra(out, rids, P, C):
    W, Hh = 1500, 980
    sh = GP.Sheet(W, Hh, "帯の出口（A1）と −15 の点の、線形の値に対する比、その間の速さの誤差（A2'）")
    f = C["f"]
    ax1 = GP.Ax(sh, (100, 110, 720, 430), (0.06, 0.15), (0.5, 1.3), xlabel="周波数（Hz）", ylabel="振幅の比",
                title="振幅の比 |測った ÷ 線形|", xticks=np.arange(0.06, 0.151, 0.01), yticks=np.arange(0.5, 1.31, 0.1))
    ax2 = GP.Ax(sh, (820, 110, 1440, 430), (0.06, 0.15), (-1.0, 1.0), xlabel="周波数（Hz）", ylabel="rad",
                title="位相の差（測った − 線形）", xticks=np.arange(0.06, 0.151, 0.01), yticks=np.arange(-1, 1.01, 0.25))
    ax3 = GP.Ax(sh, (100, 560, 720, 880), (0.06, 0.15), (-0.10, 0.20), xlabel="周波数（Hz）", ylabel="e",
                title="帯の出口 → −15 の点の速さの誤差 e = 1 − 測った速さ ÷ 線形", xticks=np.arange(0.06, 0.151, 0.01), yticks=np.arange(-0.1, 0.201, 0.05))
    ax4 = GP.Ax(sh, (820, 560, 1440, 880), (0.06, 0.15), (0.5, 1.3), xlabel="周波数（Hz）", ylabel="比",
                title="帯の出口 → −15 の点の振幅の変化", xticks=np.arange(0.06, 0.151, 0.01), yticks=np.arange(0.5, 1.31, 0.1))
    for ax in (ax1, ax2, ax3, ax4):
        for fv in (f[0], f[11], f[21], f[-1]):
            ax.vline(fv, col=(200, 200, 200))
    ax1.hline(1.0); ax1.hline(0.95, col=(200, 120, 120)); ax1.hline(1.05, col=(200, 120, 120))
    ax2.hline(0.0); ax2.hline(0.1, col=(200, 120, 120)); ax2.hline(-0.1, col=(200, 120, 120))
    ax3.hline(0.0); ax4.hline(1.0)
    xp = P["tank"]["x_p"]
    for k, rid in enumerate(rids):
        D = A.load_hf(rid); a = ana(rid)
        EX = A.zmean(D) - a["still_level_offset_m"]
        win = D["t"] <= P["tank"]["t_end"] + 1e-9
        for g, mk in (("band_exit", "o"), ("kc(x-xb)=-15", "r")):
            xr = P["gauges"][g]["x_rel"]
            em = np.nan_to_num(A.gauge(EX, D["x"], xp_of(rid) + xr)[win]); el = A.lin_series(C, xr, D["t"][win])
            fr, Fm, Fl = A.spec_ratio(em, el, C)
            m = (fr >= 0.06) & (fr <= 0.15) & (abs(Fl) > 0.02 * abs(Fl).max())
            R = Fm[m] / Fl[m]
            if mk == "o":
                ax1.points(fr[m], abs(R), col=PAL[k], r=3, label="%s 帯の出口" % rid)
                ax2.points(fr[m], np.angle(R), col=PAL[k], r=3, label="%s 帯の出口" % rid)
            else:
                ax1.rings(fr[m], abs(R), col=PAL[k], r=4, label="%s −15 の点" % rid, w=1)
                ax2.rings(fr[m], np.angle(R), col=PAL[k], r=4, label="%s −15 の点" % rid, w=1)
        e = np.array(a["A2p"]["speed_err"]); g = np.array(a["A2p"]["amp_change"]); fa = np.array(a["A2p"]["f"])
        ax3.line(fa, e, col=PAL[k], w=2, label=rid); ax3.points(fa, e, col=PAL[k], r=2)
        ax4.line(fa, g, col=PAL[k], w=2, label=rid); ax4.points(fa, g, col=PAL[k], r=2)
    for ax in (ax1, ax2, ax3, ax4):
        ax.legend("tr", 11)
    sh.text((100, 920), "縦の灰の線：成分の帯域の境（成分 1・12・22・32）。赤の横線：A1 の幅（振幅 ±5 %、位相 ±0.1 rad）。読む帯域（A2'）0.077〜0.134 Hz", 13)
    sh.save(os.path.join(out, "spectra.png"))


def fig_crestmax(out, rids, P, C):
    W, Hh = 1500, 760
    sh = GP.Sheet(W, Hh, "各場所の最大の頂 η_c（60 s から終わりまで。静かな水面から）")
    ax = GP.Ax(sh, (100, 100, 1440, 640), (0, 930), (0, 16), xlabel="造波板からの距離（m）", ylabel="m",
               xticks=np.arange(0, 931, 100), yticks=np.arange(0, 17, 2))
    a0 = ana(rids[0])
    ax.line(a0["lin_crest_max_along_x"]["x_rel"], a0["lin_crest_max_along_x"]["max"], col=(120, 120, 120), w=2, label="線形の重ね合わせ")
    for k, rid in enumerate(rids):
        a = ana(rid)
        ax.line(a["crest_max_along_x"]["x_rel"], a["crest_max_along_x"]["max"], col=PAL[k], w=2, label=rid)
    bb = P["full"]["breaking_band_RM_x"]
    ax.vline(bb[0], col=(0, 150, 0), label="実験で崩れた範囲（484〜592 m）"); ax.vline(bb[1], col=(0, 150, 0))
    ax.vline(P["full"]["xob_DK"], col=(200, 40, 40), label="D&K の着水 584.5 m")
    ax.legend("tl")
    sh.save(os.path.join(out, "crestmax.png"))


def fig_series(out, rids, P, C):
    W, Hh = 1500, 1000
    sh = GP.Sheet(W, Hh, "断面の範囲（造波板から 321〜863 m）で最も高い頂の、時刻ごとの量（138.2 s から）")
    ax1 = GP.Ax(sh, (100, 100, 1440, 330), (138, 188), (0, 16), xlabel="", ylabel="m", title="η_c（静かな水面から頂）と H（頂から前の谷）",
                xticks=np.arange(140, 189, 5), yticks=np.arange(0, 17, 4))
    ax2 = GP.Ax(sh, (100, 420, 1440, 650), (138, 188), (0, 180), xlabel="", ylabel="度", title="前の面の最大の傾き（90° で鉛直、それより大きいと前へかぶさる）",
                xticks=np.arange(140, 189, 5), yticks=np.arange(0, 181, 30))
    ax3 = GP.Ax(sh, (100, 740, 1440, 940), (138, 188), (0, 950), xlabel="時刻（s）", ylabel="m", title="頂の位置（造波板から）",
                xticks=np.arange(140, 189, 5), yticks=np.arange(0, 951, 150))
    ax2.hline(90, col=(200, 40, 40)); ax2.hline(60, col=(200, 160, 160))
    for k, rid in enumerate(rids):
        a = ana(rid); s = a["section_series"]
        t = [r["t"] for r in s]
        ax1.line(t, [r.get("eta_c", np.nan) for r in s], col=PAL[k], w=2, label="%s η_c" % rid)
        ax1.line(t, [r.get("H", np.nan) for r in s], col=PAL[k], w=1, label="%s H" % rid, dash=True)
        ax2.line(t, [r["thmax"] for r in s], col=PAL[k], w=1, label=rid)
        ax3.points(t, [r["xc_rel"] for r in s], col=PAL[k], r=1, label=rid)
        for ax in (ax1, ax2, ax3):
            if a.get("onset"):
                ax.vline(a["onset"]["t"], col=PAL[k])
    for ax in (ax1, ax2, ax3):
        ax.vline(P["full"]["tob_DK"], col=(0, 150, 0)); ax.vline(C["tb"], col=(120, 120, 120))
    ax1.legend("tl", 11); ax2.legend("tl", 11)
    sh.text((100, 960), "縦の線：緑＝D&K の着水の時刻 159.3 s、灰＝線形の焦点の時刻 171.5 s、色＝その計算の巻き始め", 13)
    sh.save(os.path.join(out, "series.png"))


def fig_shapes(out, rids, P, C):
    """頂の時刻（巻き始め、なければ最も険しくなった時刻）の前後の断面。"""
    Tc, Lc = C["Tc"], C["Lc"]
    offs = [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]
    W = 1500; ph = 300
    Hh = 90 + len(rids) * (ph + 60) + 40
    sh = GP.Sheet(W, Hh, "断面の形（縦横同じ縮尺）。基準の時刻（巻き始め、なければ最も険しくなった時刻）から −0.3〜+0.3 Tc")
    for k, rid in enumerate(rids):
        a = ana(rid)
        ref = a.get("onset") or a["N2_time"]["row"]
        S = A.load_sec(rid)
        me = S["meta"]; off = a["still_level_offset_m"]
        xs = me["x0"] + me["dx"] * np.arange(me["nx"]) - xp_of(rid)
        ys = me["y0"] + me["dy"] * np.arange(me["ny"]) - off
        xc = ref["xc_rel"]
        X0, X1, Y0, Y1 = xc - 0.45 * Lc, xc + 0.45 * Lc, -12, 16
        box = (90, 90 + k * (ph + 60) + 30, W - 40, 90 + k * (ph + 60) + 30 + ph)
        sc = min((box[2] - box[0]) / (X1 - X0), ph / (Y1 - Y0))
        bw = (X1 - X0) * sc; bh = (Y1 - Y0) * sc
        box = (box[0], box[1], int(box[0] + bw), int(box[1] + bh))
        ax = GP.Ax(sh, box, (X0, X1), (Y0, Y1), xlabel="造波板からの距離（m）", ylabel="m",
                   title="%s（基準 %.2f s・%.0f m、%s）" % (rid, ref["t"], xc, "巻き始め" if a.get("onset") else "最も険しくなった時刻"),
                   xticks=np.arange(np.ceil(X0 / 20) * 20, X1, 20), yticks=np.arange(-12, 17, 4))
        ax.hline(0)
        for q, o in enumerate(offs):
            tt = ref["t"] + o * Tc
            j = int(np.argmin(abs(S["t"] - tt)))
            from skimage import measure
            cs = measure.find_contours(S["sdf"][j].astype(np.float32), 0.0)
            col = (int(30 + 200 * q / 6), int(60 + 40 * (1 - abs(q - 3) / 3)), int(220 - 190 * q / 6))
            first = True
            for c in cs:
                cx = xs[0] + c[:, 1] * me["dx"]; cy = ys[0] + c[:, 0] * me["dy"]
                if cy.max() < -20:
                    continue
                vis = (cx >= X0) & (cx <= X1) & (cy >= Y0) & (cy <= Y1)
                cx = np.where(vis, cx, np.nan); cy = np.where(vis, cy, np.nan)
                ax.line(cx, cy, col=col, w=2, label=("%+.1f Tc" % o) if first else None)
                first = False
        ax.legend("tr", 11)
    sh.save(os.path.join(out, "shapes.png"))


if __name__ == "__main__":
    out = sys.argv[1]; rids = sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    P = A.plan(); C = A.comps_full(P)
    for rid in rids:
        fig_xt(out, rid, P, C)
    fig_gauges(out, rids, P, C)
    fig_spectra(out, rids, P, C)
    fig_crestmax(out, rids, P, C)
    fig_series(out, rids, P, C)
    fig_shapes(out, rids, P, C)
    print("figs saved", out)
