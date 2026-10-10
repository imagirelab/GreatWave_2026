# -*- coding: utf-8 -*-
"""FLIP42 R2 の段：(c) 細かさと時間の刻みの比べの図（shape.json から。PIL だけで描く）。
py -3.10 g_figs2.py <out_dir> <run_id> [<run_id> ...]
  c_series.png   巻き始めからの時刻で、η_c・H・前の面の最大の傾き・頂の位置（計算ごとに色）
  c_overlay.png  巻き始めにそろえた時刻（−0.3〜+0.3 Tc と着水）の断面の線を重ねる。x は各計算の巻き始めの点（前の面が鉛直になった点）から
"""
import sys, os, json
import numpy as np
from skimage import measure

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A
import g_plot as GP

PAL = [(31, 119, 180), (214, 39, 40), (44, 160, 44), (255, 127, 14), (148, 103, 189)]


def shp(rid):
    return json.load(open(os.path.join(A.ROOT, rid, "shape.json"), encoding="utf8"))


def name(rid):
    cfg = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))
    p = cfg["parms"]
    s = "%s（粒子 %.3g m" % (rid.replace("R5p", "R5'"), p["dp"])
    if p.get("cfl", 1.0) != 1.0:
        s += "、刻み半分"
    if cfg.get("solver", {}).get("usemgpreconditioner"):
        s += "、前処理だけ多重格子"
    return s + "）"


def fig_series(out, rids, P, C):
    Tc = C["Tc"]
    W, Hh = 1500, 1060
    sh = GP.Sheet(W, Hh, "巻き始めからの時刻で見た、頂の量（細かさと時間の刻みの比べ）")
    X = (-3.0, 2.0)
    xt = np.arange(-3.0, 2.01, 0.5)
    ax1 = GP.Ax(sh, (100, 100, 1440, 330), X, (0, 16), ylabel="m", title="η_c（実線）と H（点線）", xticks=xt, yticks=np.arange(0, 17, 4))
    ax2 = GP.Ax(sh, (100, 420, 1440, 650), X, (0, 180), ylabel="度", title="前の面の最大の傾き（90° で鉛直）", xticks=xt, yticks=np.arange(0, 181, 30))
    ax3 = GP.Ax(sh, (100, 740, 1440, 970), X, (-150, 100), xlabel="巻き始めからの時刻（Tc = %.2f s を単位に）" % Tc, ylabel="m",
                title="頂の位置（各計算の巻き始めの点から）", xticks=xt, yticks=np.arange(-150, 101, 50))
    ax2.hline(90, col=(200, 40, 40))
    for k, rid in enumerate(rids):
        s = shp(rid)
        on = s.get("onset")
        if not on:
            continue
        rows = s["rows"]
        t = np.array([(r["t"] - on["t"]) / Tc for r in rows])
        ax1.line(t, [r.get("eta_c", np.nan) for r in rows], col=PAL[k], w=2, label=name(rid))
        ax1.line(t, [r.get("H", np.nan) for r in rows], col=PAL[k], w=1, dash=True)
        ax2.line(t, [r["thmax"] for r in rows], col=PAL[k], w=1, label=name(rid))
        x0 = on.get("vertical_x_rel") or on["xc_rel"]
        ax3.line(t, [r["xc_rel"] - x0 for r in rows], col=PAL[k], w=2, label=name(rid))
        tou = s.get("touchdown")
        if tou:
            for ax in (ax1, ax2, ax3):
                ax.vline((tou["t"] - on["t"]) / Tc, col=PAL[k])
    for ax in (ax1, ax2, ax3):
        ax.vline(0, col=(0, 0, 0))
    ax1.legend("tl", 11); ax2.legend("tl", 11)
    sh.text((100, 1000), "縦の黒い線＝巻き始め（前の面が初めて鉛直）。色の縦の線＝その計算の着水。", 13)
    sh.save(os.path.join(out, "c_series.png"))


def fig_overlay(out, rids, P, C):
    Tc, Lc = C["Tc"], C["Lc"]
    xp = P["tank"]["x_p"]
    labs = [(-0.3, "−0.3 Tc"), (-0.2, "−0.2 Tc"), (-0.1, "−0.1 Tc"), (0.0, "巻き始め"), (0.1, "+0.1 Tc"), (0.2, "+0.2 Tc"), (0.3, "+0.3 Tc"), ("touch", "着水")]
    X0, X1, Y0, Y1 = -70.0, 60.0, -10.0, 15.0
    pw = 700; s = pw / (X1 - X0); ph = int((Y1 - Y0) * s)
    W = 60 + 2 * (pw + 70); Hh = 120 + 4 * (ph + 80)
    sh = GP.Sheet(W, Hh, "巻き始めにそろえた時刻の断面の線を重ねる（縦横同じ縮尺。x は各計算の巻き始めの点から、高さは静かな水面から）")
    data = []
    for rid in rids:
        s = shp(rid)
        if not s.get("onset"):
            continue
        S = A.load_sec(rid)
        data.append((rid, s, S))
    for q, (o, lab) in enumerate(labs):
        col, row = q % 2, q // 2
        bx = 80 + col * (pw + 70); by = 110 + row * (ph + 80)
        ax = GP.Ax(sh, (bx, by, bx + pw, by + ph), (X0, X1), (Y0, Y1), xlabel="巻き始めの点からの距離（m）" if row == 3 else "", ylabel="m",
                   title=lab, xticks=np.arange(-60, 61, 20), yticks=np.arange(-10, 16, 5))
        ax.hline(0)
        for k, (rid, s, S) in enumerate(data):
            on = s["onset"]
            if o == "touch":
                if not s.get("touchdown"):
                    continue
                tq = s["touchdown"]["t"]
            else:
                tq = on["t"] + o * Tc
            j = int(np.argmin(abs(S["t"] - tq)))
            me = S["meta"]; off = s["still_level_offset_m"]
            x0 = on.get("vertical_x_rel") or on["xc_rel"]
            xpr = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))["parms"]["x_p"]
            xs = me["x0"] + me["dx"] * np.arange(me["nx"]) - xpr - x0
            ys = me["y0"] + me["dy"] * np.arange(me["ny"]) - off
            first = True
            for c in measure.find_contours(S["sdf"][j].astype(np.float32), 0.0):
                cx = xs[0] + c[:, 1] * me["dx"]; cy = ys[0] + c[:, 0] * me["dy"]
                if cy.max() < -20:
                    continue
                vis = (cx >= X0) & (cx <= X1) & (cy >= Y0) & (cy <= Y1)
                ax.line(np.where(vis, cx, np.nan), np.where(vis, cy, np.nan), col=PAL[k], w=2,
                        label=(name(rid) if (first and q == 0) else None))
                first = False
        if q == 0:
            ax.legend("tl", 11)
    sh.save(os.path.join(out, "c_overlay.png"))


if __name__ == "__main__":
    out = sys.argv[1]; rids = sys.argv[2:]
    os.makedirs(out, exist_ok=True)
    P = A.plan(); C = A.comps_full(P)
    fig_series(out, rids, P, C)
    fig_overlay(out, rids, P, C)
    print("figs2 saved", out)
