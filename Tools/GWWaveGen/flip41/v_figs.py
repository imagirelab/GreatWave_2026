# -*- coding: utf-8 -*-
"""FLIP41 確かめの図（PIL、日本語の見出し）。py -3.10 v_figs.py [all|b1|b2|t1|t2|profiles]
図は Unity/Build/FLIP41/verify/figs/ に置く。数は各計算の runs/<run_id>/ana.json から読む（図のために計算し直さない）。"""
import sys, os, json, glob, math
import numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
from v_plot import Sheet, Ax, PAL, font
from v_lin import props, k_of_omega

V = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP41/verify"
FIG = os.path.join(V, "figs")
os.makedirs(FIG, exist_ok=True)
DPCOL = {1.0: PAL[0], 0.5: PAL[1], 0.35: PAL[2], 0.25: PAL[3]}


def anas(prefix):
    out = []
    for p in sorted(glob.glob(os.path.join(V, "runs", prefix + "*", "ana.json"))):
        a = json.load(open(p, encoding="utf8"))
        if "error" in a:
            continue
        out.append(a)
    return out


def std_b1(wm="relax"):
    return [a for a in anas("B1_") if a["case"]["wm"] == wm and a["case"].get("band_vox", 4) == 4
            and a["case"].get("minsub", 1) == 1 and a["case"].get("vt", "apic") == "apic" and a["case"].get("nb", 1) == 1
            and "_T2" not in a["run_id"] and a["case"].get("P0", 0) == 0]


def mark(ax, a, x, y, col, r=5):
    """振幅/格子 が 0.45 より小さい計算は輪、それ以上は塗りつぶし。"""
    if a["case"]["a_over_vox"] < 0.45:
        ax.rings([x], [y], col, r=r)
    else:
        ax.points([x], [y], col, r=r)


def b1_summary():
    A = std_b1()
    if not A:
        return
    sh = Sheet(1800, 1200, "B1 平らな底の規則波：FLIP の波の速さと高さの減り（緩和の帯で造波）。塗りつぶし：振幅/格子 ≥ 0.45、輪：それより小さい波")
    ce = [100 * a["c_err"] for a in A]
    ylo = min(-6.0, 5 * math.floor(min(ce) / 5)); yhi = max(4.0, 2 * math.ceil(max(ce) / 2))
    ax = Ax(sh, (110, 110, 860, 540), (0, 4.5), (ylo, yhi), "kh（水深 × 波数）", "速さの誤差 (%)",
            "波の速さ c ÷ 線形の分散の式の速さ − 1（測る区間 3 波長でまとめた値）", xticks=np.arange(0, 4.6, 0.5),
            yticks=np.arange(ylo, yhi + 0.1, 5 if yhi - ylo > 20 else 1))
    for y in (-1, 1):
        ax.hline(y, (200, 120, 120))
    ax.hline(0, (60, 60, 60))
    for a in A:
        col = DPCOL.get(a["case"]["dp"], (0, 0, 0))
        mark(ax, a, a["case"]["kh"], 100 * a["c_err"], col)
        X, Y = ax.px(a["case"]["kh"], 100 * a["c_err"])
        sh.text((X + 7, Y - 8), "%gs/%gm a/Δ%.2f" % (a["case"]["T"], a["case"]["h"], a["case"]["a_over_vox"]), 10, col)
    for dp, col in DPCOL.items():
        if any(abs(a["case"]["dp"] - dp) < 1e-9 for a in A):
            ax.leg.append(("粒子 %g m（格子 Δ = %g m）" % (dp, 2 * dp), col, False))
    ax.legend("bl")
    sh.text((120, 590), "赤い線：判定の幅 ±1 %（plan_ja.md §5）。a/Δ：振幅 ÷ 格子", 12, (180, 60, 60))
    # 右上：周期 7 s の速さ vs 水深
    ax2 = Ax(sh, (1000, 110, 1750, 540), (0, 62), (5, 11.5), "水深 h (m)", "速さ (m/s)",
             "同じ周期 7 s の波の速さと水深（線：線形の式、点：FLIP）", xticks=np.arange(0, 61, 10), yticks=np.arange(5, 11.6, 1))
    hh = np.linspace(1, 62, 300)
    ax2.line(hh, [props(7.0, h)["c"] for h in hh], (0, 0, 0), 2, label="線形の分散の式 ω² = gk tanh(kh)")
    for a in A:
        if abs(a["case"]["T"] - 7) < 1e-9:
            col = DPCOL.get(a["case"]["dp"], (0, 0, 0))
            mark(ax2, a, a["case"]["h"], a["c"], col)
    ax2.legend("br")
    # 左下：高さの減り
    de = [100 * a["decay_3L"] for a in A]
    ax3 = Ax(sh, (110, 690, 860, 1100), (0, 4.5), (-5, max(30, 10 * math.ceil(max(de) / 10))), "kh", "3 波長での高さの減り (%)",
             "進む間の高さの減り 1 − e^(−3αL)", xticks=np.arange(0, 4.6, 0.5), yticks=np.arange(-5, max(30, 10 * math.ceil(max(de) / 10)) + 1, 5 if max(de) < 40 else 10))
    ax3.hline(5, (200, 120, 120)); ax3.hline(0, (60, 60, 60))
    for a in A:
        mark(ax3, a, a["case"]["kh"], 100 * a["decay_3L"], DPCOL.get(a["case"]["dp"], (0, 0, 0)))
    sh.text((120, 1150), "赤い線：判定の幅 5 %", 12, (180, 60, 60))
    # 右下：帯の出口の高さの比
    ax4 = Ax(sh, (1000, 690, 1750, 1100), (0, 4.5), (0.4, 1.2), "kh", "帯の出口の高さ ÷ 目標",
             "造波の帯の出口の進む波の高さ（緩和の帯）", xticks=np.arange(0, 4.6, 0.5), yticks=np.arange(0.4, 1.21, 0.1))
    for y in (0.95, 1.05):
        ax4.hline(y, (200, 120, 120))
    ax4.hline(1.0, (60, 60, 60))
    for a in A:
        mark(ax4, a, a["case"]["kh"], a["a_exit_ratio"], DPCOL.get(a["case"]["dp"], (0, 0, 0)))
    sh.text((1010, 1150), "赤い線：判定の幅 ±5 %", 12, (180, 60, 60))
    sh.save(os.path.join(FIG, "B1_summary.png"))


def b1_convergence():
    A = std_b1()
    groups = {}
    for a in A:
        groups.setdefault((a["case"]["T"], a["case"]["h"], round(a["case"]["HL"], 3)), []).append(a)
    groups = {k: v for k, v in groups.items() if len(v) >= 2}
    if not groups:
        return
    sh = Sheet(1700, 640, "B1 細かさを変えた時の速さの誤差と高さの減り（緩和の帯。同じ波を粒子の間隔だけ変えて比べる）")
    ce = [100 * a["c_err"] for v in groups.values() for a in v]
    ylo = min(-6.0, 5 * math.floor(min(ce) / 5)); yhi = max(4.0, 2 * math.ceil(max(ce) / 2))
    ax = Ax(sh, (110, 110, 820, 530), (0, 1.1), (ylo, yhi), "粒子の間隔 (m)", "速さの誤差 (%)", "速さの誤差と粒子の間隔",
            xticks=[0, 0.25, 0.35, 0.5, 0.75, 1.0], yticks=np.arange(ylo, yhi + 0.1, 5 if yhi - ylo > 20 else 1))
    de = [100 * a["decay_3L"] for v in groups.values() for a in v]
    ax2 = Ax(sh, (950, 110, 1660, 530), (0, 1.1), (-5, max(30, 10 * math.ceil(max(de) / 10))), "粒子の間隔 (m)", "3 波長での高さの減り (%)", "高さの減りと粒子の間隔",
             xticks=[0, 0.25, 0.35, 0.5, 0.75, 1.0], yticks=np.arange(-5, max(30, 10 * math.ceil(max(de) / 10)) + 1, 5 if max(de) < 40 else 10))
    for y in (-1, 1):
        ax.hline(y, (200, 120, 120))
    ax.hline(0, (60, 60, 60)); ax2.hline(5, (200, 120, 120)); ax2.hline(0, (60, 60, 60))
    for i, (key, S) in enumerate(sorted(groups.items())):
        S.sort(key=lambda a: a["case"]["dp"])
        col = PAL[(i + 4) % len(PAL)]
        lab = "周期 %g s・水深 %g m・高さ %.2f m（H/L %.2f）" % (key[0], key[1], S[0]["case"]["H"], key[2])
        ax.line([a["case"]["dp"] for a in S], [100 * a["c_err"] for a in S], col, 2, label=lab)
        ax.points([a["case"]["dp"] for a in S], [100 * a["c_err"] for a in S], col, r=4)
        ax2.line([a["case"]["dp"] for a in S], [100 * a["decay_3L"] for a in S], col, 2, label=lab)
        ax2.points([a["case"]["dp"] for a in S], [100 * a["decay_3L"] for a in S], col, r=4)
    ax.legend("bl"); ax2.legend("tr")
    sh.save(os.path.join(FIG, "B1_convergence.png"))


def profile(rid):
    p = os.path.join(V, "runs", rid, "ana.json")
    if not os.path.exists(p):
        return
    a = json.load(open(p, encoding="utf8"))
    if "_curve" not in a or a["case"]["kind"] != "B1":
        return
    cs = a["case"]; cv = a["_curve"]
    x = np.array(cv["x"]); A1 = np.array([c[0] + 1j * c[1] for c in cv["A1"]])
    L = cs["L"]; kl = cs["k"]
    sh = Sheet(1700, 900, "%s：周期 %g s・水深 %g m・粒子 %g m・%s（測る窓 %.0f〜%.0f s）" % (
        rid, cs["T"], cs["h"], cs["dp"], "緩和の帯" if cs["wm"] == "relax" else "ピストン板", a["win"][0], a["win"][1]))
    xm0, xm1 = cv["sel"]
    ymax = max(0.1, float(np.nanmax(np.abs(A1))) * 1.3)
    ax = Ax(sh, (110, 110, 1650, 440), (0, x.max()), (0, ymax), "x (m)", "振幅 (m)",
            "周期 ω の振幅 |A1(x)|（灰：測る区間、点線：目標の振幅）", yticks=np.linspace(0, ymax, 6))
    ax.vline(xm0, (150, 150, 150), "測る区間"); ax.vline(xm1, (150, 150, 150))
    if cs["wm"] == "relax":
        ax.vline(cs["xg"], (90, 160, 90), "帯の出口")
    ax.vline(cs["xa0"], (160, 90, 90), "吸う帯")
    ax.line(x, np.abs(A1), PAL[0], 2, label="FLIP |A1|")
    ax.line([0, x.max()], [cs["a"], cs["a"]], (0, 0, 0), 1, dash=True, label="目標 a = %.3f m" % cs["a"])
    ax.legend("tr")
    # 位相：arg A1 − k線形 x（線形の速さなら水平、遅いと右下がり）
    ph = np.unwrap(np.angle(A1 * np.exp(-1j * kl * x)))
    m = (x >= xm0) & (x <= xm1)
    ph = ph - np.nanmean(ph[m])
    yl = max(0.5, float(np.nanmax(np.abs(ph[m]))) * 1.5)
    ax2 = Ax(sh, (110, 540, 1650, 850), (0, x.max()), (-yl, yl), "x (m)", "位相の差 (rad)",
             "位相 arg A1 − k線形 x（線形の式と同じ速さなら水平。傾き = k線形 − kFLIP。結果：速さの誤差 %+.2f %%、3 波長の減り %.1f %%）" % (100 * a["c_err"], 100 * a["decay_3L"]),
             yticks=np.linspace(-yl, yl, 5))
    ax2.vline(xm0, (150, 150, 150)); ax2.vline(xm1, (150, 150, 150))
    ax2.line(x, ph, PAL[1], 2)
    ax2.hline(0, (60, 60, 60))
    sh.save(os.path.join(FIG, "profile_%s.png" % rid))


def iso_fig():
    """原因を分ける計算：基準と、一つずつ変えた計算の速さの誤差と高さの減り（2 組：粒子 1 m・H/L 0.01、粒子 0.5 m・H/L 0.04）。"""
    groups = [("粒子 1 m・格子 2 m、高さ 0.74 m（振幅/格子 0.19）", "B1_T7_h25_dp1_relax", [("_nb0", "帯を使わない（水の全体に粒子）"), ("_band12", "粒子の帯 4 → 12 格子"),
               ("_sub2", "最小の小刻み 1 → 2（時間の刻み半分）"), ("_flip", "流速の受け渡し APIC → FLIP")]),
              ("粒子 0.5 m・格子 1 m、高さ 2.97 m（振幅/格子 1.49）", "B1_T7_h25_dp0.5_relax_HL0.04", [("_nb0", "帯を使わない（水の全体に粒子）"),
               ("_sub2", "最小の小刻み 1 → 2（時間の刻み半分）")])]
    rows = []
    for gl, base, vars_ in groups:
        p = os.path.join(V, "runs", base, "ana.json")
        if not os.path.exists(p):
            continue
        rows.append(("— " + gl, None))
        rows.append(("基準（今までの設定）", json.load(open(p, encoding="utf8"))))
        for tag, lab in vars_:
            q = os.path.join(V, "runs", base + tag, "ana.json")
            if os.path.exists(q):
                a = json.load(open(q, encoding="utf8"))
                if "error" not in a:
                    rows.append((lab, a))
    sh = Sheet(1700, 150 + 62 * len(rows) + 40, "原因を分ける計算（周期 7 s・水深 25 m、緩和の帯）：一つずつ変えた時の速さの誤差と高さの減り")
    x0 = 520; w1 = 520; x1 = x0 + w1 + 80; w2 = 520
    sh.text((x0, 70), "速さの誤差 (%)：左端 −25 %、右端 +5 %、灰の線 0、赤の線 ±1 %", 13)
    sh.text((x1, 70), "3 波長での高さの減り (%)：左端 0 %、右端 100 %、赤の線 5 %", 13)

    def X1(v):
        return x0 + (v + 25) / 30 * w1

    def X2(v):
        return x1 + v / 100 * w2
    y = 100
    for lab, a in rows:
        if a is None:
            sh.text((20, y + 10), lab, 15, bold=True)
            y += 40
            continue
        sh.text((40, y + 10), lab, 14)
        sh.d.rectangle([x0, y, x0 + w1, y + 44], outline=(0, 0, 0))
        sh.d.rectangle([x1, y, x1 + w2, y + 44], outline=(0, 0, 0))
        for v, col in ((0, (120, 120, 120)), (-1, (200, 120, 120)), (1, (200, 120, 120))):
            sh.d.line([(X1(v), y), (X1(v), y + 44)], fill=col)
        sh.d.line([(X2(5), y), (X2(5), y + 44)], fill=(200, 120, 120))
        v = 100 * a["c_err"]
        sh.d.rectangle([min(X1(0), X1(v)), y + 10, max(X1(0), X1(v)), y + 34], fill=PAL[0])
        sh.text((X1(v) - 70 if v < -20 else X1(v) + 6, y + 12), "%+.1f %%" % v, 13)
        d = 100 * a["decay_3L"]
        sh.d.rectangle([X2(0), y + 10, X2(d), y + 34], fill=PAL[1])
        sh.text((X2(d) + 6, y + 12), "%.0f %%" % d, 13)
        y += 62
    sh.save(os.path.join(FIG, "B1_cause_isolation.png"))


def amp_scatter():
    """場所ごとの窓（1 波長、半波長ずつずらす）の速さの誤差と高さの減りを、その窓の振幅 ÷ 格子 に対して描く（B1 の緩和の帯・ピストン、一つずつ変えた計算は除く）。"""
    A = [a for a in anas("B1_") if "local" in a and a["case"].get("band_vox", 4) == 4 and a["case"].get("minsub", 1) == 1
         and a["case"].get("vt", "apic") == "apic" and a["case"].get("nb", 1) == 1 and "_T2" not in a["run_id"]]
    if not A:
        return
    sh = Sheet(1800, 700, "B1 場所ごとの速さの誤差と高さの減りを、その場の振幅 ÷ 格子の大きさに対して描いた図（1 点 = 1 波長の窓）")
    ax = Ax(sh, (110, 110, 860, 600), (0, 3.2), (-45, 10), "その場の振幅 ÷ 格子", "速さの誤差 (%)", "速さの誤差",
            xticks=np.arange(0, 3.21, 0.4), yticks=np.arange(-45, 11, 5))
    ax2 = Ax(sh, (1000, 110, 1750, 600), (0, 3.2), (-10, 60), "その場の振幅 ÷ 格子", "1 波長あたりの高さの減り (%)", "1 波長進む間の高さの減り",
             xticks=np.arange(0, 3.21, 0.4), yticks=np.arange(-10, 61, 10))
    for y in (-1, 1):
        ax.hline(y, (200, 120, 120))
    ax.hline(0, (60, 60, 60)); ax2.hline(0, (60, 60, 60)); ax2.hline(100 * (1 - 0.95 ** (1 / 3)), (200, 120, 120))
    keys = sorted(set((a["case"]["T"], a["case"]["h"]) for a in A))
    marker = {k: PAL[(i + 4) % len(PAL)] for i, k in enumerate(keys)}
    for a in A:
        cs = a["case"]; vox = cs["vox"]
        loc = a["local"]
        col = DPCOL.get(cs["dp"], (0, 0, 0))
        ax.points([l["a"] / vox for l in loc], [100 * l["c_err"] for l in loc], col, r=3 if cs["wm"] == "relax" else 5)
        if len(loc) >= 3:
            xs = [l["a"] / vox for l in loc[1:-1]]
            # 1 波長の比：x ± 0.5 波長の窓の振幅の比
            dec = [100 * (1 - loc[i + 1]["a"] / loc[i - 1]["a"]) for i in range(1, len(loc) - 1)]
            ax2.points(xs, dec, col, r=3 if cs["wm"] == "relax" else 5)
    for dp, col in DPCOL.items():
        if any(abs(a["case"]["dp"] - dp) < 1e-9 for a in A):
            ax.leg.append(("粒子 %g m（格子 %g m）" % (dp, 2 * dp), col, False))
    ax.legend("br")
    sh.text((1010, 655), "赤い線：3 波長で 5 % の減りを 1 波長に直した値（1.7 %）", 12, (180, 60, 60))
    sh.text((120, 655), "赤い線：判定の幅 ±1 %。大きい点はピストン板", 12, (180, 60, 60))
    sh.save(os.path.join(FIG, "B1_amplitude_vs_grid.png"))


def snapshots(rids, out, title):
    """測る窓の終わりの時刻の水面 η(x) を、線形の理論の波（帯の出口の目標の位相のまま、減らずに進む波）と重ねる。"""
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip41")
    import v_analyze
    rids = [r for r in rids if os.path.exists(os.path.join(V, "runs", r, "ana.json"))]
    if not rids:
        return
    sh = Sheet(1700, 140 + 330 * len(rids), title)
    for i, rid in enumerate(rids):
        cfg, t, x, ex, F, wall = v_analyze.load(rid)
        a = json.load(open(os.path.join(V, "runs", rid, "ana.json"), encoding="utf8"))
        cs = cfg["case"]
        j = int(np.argmin(np.abs(t - cs["t_win"][1])))
        eta = ex[j] - np.nanmean(ex[(t >= cs["t_win"][0]) & (t <= cs["t_win"][1])], axis=0)
        th = cs["a"] * np.cos(cs["k"] * x - cs["om"] * t[j])
        x0 = cs["xg"] if cs["wm"] == "relax" else 0.0
        th = np.where(x >= x0, th, np.nan)
        ym = max(2.0 * cs["a"], 0.1)
        ax = Ax(sh, (110, 110 + 330 * i, 1650, 340 + 330 * i), (0, cs["xa0"]), (-ym, ym), "x (m)", "η (m)",
                "%s：粒子 %g m、H/L %.2f（振幅/格子 %.2f、波長/格子 %.0f）、t = %.1f s。速さの誤差 %+.1f %%、3 波長の減り %.0f %%" % (
                    rid, cs["dp"], cs["HL"], cs["a_over_vox"], cs["L_over_vox"], t[j], 100 * a["c_err"], 100 * a["decay_3L"]),
                yticks=np.linspace(-ym, ym, 5))
        ax.line(x, th, (0, 0, 0), 1, dash=True, label="線形の理論の波（減らない）")
        ax.line(x, eta, PAL[0], 2, label="FLIP")
        ax.vline(cs["x_meas"][0], (150, 150, 150)); ax.vline(cs["x_meas"][1], (150, 150, 150))
        if cs["wm"] == "relax":
            ax.vline(cs["xg"], (90, 160, 90), "帯の出口")
        ax.legend("tr")
    sh.save(os.path.join(FIG, out))


def spacetime(rid, vmax=None):
    """水面 η(x, t) の時空間図（横 x、縦 t：上が後の時刻）。始めの 1〜3 秒の水面を 0 とした。"""
    import v_analyze
    from PIL import Image
    from v_plot import colormap
    if not os.path.exists(os.path.join(V, "runs", rid, "ana.json")):
        return
    cfg, t, x, ex, F, wall = v_analyze.load(rid)
    cs = cfg["case"]
    e = ex - np.nanmedian(ex[(t > 1) & (t < 3)], axis=0)
    if vmax is None:
        vmax = round(1.5 * cs["a"], 2)
    im = colormap(e[::-1], -vmax, vmax)
    W, H = 1400, 820
    img = Image.fromarray(im).resize((W, H), Image.NEAREST)
    sh = Sheet(1600, 980, "%s：水面 η(x, t)。横 x 0〜%.0f m、縦 t 0〜%.0f s（上が後の時刻）、赤 +%.2f m・青 −%.2f m" % (rid, x.max(), t.max(), vmax, vmax))
    sh.im.paste(img, (110, 70))
    d = sh.d
    for xx in np.linspace(0, x.max(), 6):
        X = 110 + xx / x.max() * W
        d.line([(X, 70 + H), (X, 70 + H + 6)], fill=(0, 0, 0)); sh.text((X - 14, 70 + H + 8), "%.0f" % xx, 12)
    for tt in np.linspace(0, t.max(), 6):
        Y = 70 + H - tt / t.max() * H
        d.line([(104, Y), (110, Y)], fill=(0, 0, 0)); sh.text((60, Y - 8), "%.0f" % tt, 12)
    sh.text((110 + W // 2 - 20, 70 + H + 26), "x (m)", 13); sh.text((20, 50), "t (s)", 13)
    for key, col, lab in (("xg", (40, 160, 40), "帯の出口"), ("xs0", (120, 90, 50), "斜面の下の端"), ("xs1", (120, 90, 50), "斜面の上の端"), ("xa0", (160, 60, 60), "吸う帯")):
        if cs.get(key) and cs[key] < x.max():
            X = 110 + cs[key] / x.max() * W
            d.line([(X, 70), (X, 70 + H)], fill=col, width=1); sh.text((X + 3, 72), lab, 11, col)
    for tt in cs.get("t_win") or []:
        Y = 70 + H - tt / t.max() * H
        d.line([(110, Y), (110 + W, Y)], fill=(90, 90, 90)); sh.text((110 + W + 4, Y - 8), "測る窓", 11, (90, 90, 90))
    sh.save(os.path.join(FIG, "spacetime_%s.png" % rid))


def b2_fig(rid):
    p = os.path.join(V, "runs", rid, "ana.json")
    if not os.path.exists(p):
        return
    a = json.load(open(p, encoding="utf8"))
    if "rows" not in a:
        return
    cs = a["case"]; cv = a["_curve"]
    src = a.get("perx") or a          # 場所ごとの窓（無ければ同じ窓）
    rows = src["rows"]
    x = np.array(cv["x"]); h = np.array(cv["h"])
    sh = Sheet(1700, 1150, "%s：水深 %g → %g m（1:%g）、周期 %g s、粒子 %g m" % (rid, cs["h0"], cs["h1"], cs["n"], cs["T"], cs["dp"]))
    ax0 = Ax(sh, (110, 100, 1650, 290), (0, x.max()), (-cs["h0"] - 2, 2), "x (m)", "y (m)", "水槽の断面（海底）",
             yticks=np.linspace(-cs["h0"], 0, 5))
    ax0.line(x, -h, (120, 90, 50), 3, label="海底")
    ax0.hline(0, (60, 120, 200))
    xr = np.array([r["x"] for r in rows])
    ax1 = Ax(sh, (110, 380, 1650, 680), (0, x.max()), (-6, 4), "x (m)", "速さの誤差 (%)",
             "場所ごとの速さ（1 波長の窓で合わせた波数。測る時刻は場所ごとの窓）÷ その場の水深の線形の速さ − 1", yticks=np.arange(-6, 4.1, 2))
    for y in (-2, 2):
        ax1.hline(y, (200, 120, 120))
    ax1.hline(0, (60, 60, 60))
    ax1.line(xr, [100 * r["c_err"] for r in rows], PAL[1], 2, label="FLIP")
    ax1.vline(cs["xs0"], (150, 150, 150), "斜面の下の端"); ax1.vline(cs["xs1"], (150, 150, 150), "上の端")
    ax1.legend("tr")
    ax2 = Ax(sh, (110, 770, 1650, 1080), (0, x.max()), (0.0, 1.3), "x (m)", "高さの比",
             "高さ ÷ 沖の平らな所の高さ（線：線形の浅水係数 Ks、点：FLIP）。斜面を上る時間：FLIP %.2f s、線形 %.2f s、40 m のまま %.2f s" % (
                 src["slope_time_num"], src["slope_time_lin"], src["slope_time_const"]), yticks=np.arange(0.0, 1.31, 0.1))
    ax2.line(xr, [r["Ks_lin"] for r in rows], (0, 0, 0), 2, label="線形の Ks")
    ax2.points(xr, [r["Ks_num"] for r in rows], PAL[0], r=3, label="FLIP")
    ax2.vline(cs["xs0"], (150, 150, 150)); ax2.vline(cs["xs1"], (150, 150, 150))
    ax2.legend("tr")
    sh.save(os.path.join(FIG, "B2_%s.png" % rid))


def t1_fig():
    A = anas("T1_")
    if not A:
        return
    sh = Sheet(1700, 160 + 350 * len(A), "T1 水面の圧力の場の単位と向き：静かな水（水深 25 m）に、一様な圧力 + cos(kx) の圧力（波長 40 m）を 30 秒かけて与えた時の水面")
    for i, a in enumerate(A):
        cv = a["_curve"]; x = np.array(cv["x"]); d = np.array(cv["d"])
        cs = a["case"]
        ax = Ax(sh, (110, 110 + 350 * i, 1650, 380 + 350 * i), (0, x.max()), (-0.8, 0.8), "x (m)", "水面の変わり (m)",
                "%s（粒子 %g m%s、圧力 %g + %g cos(kx) Pa）：cos の振幅 %.3f m、式 −p0/(ρg) = %.3f m、比 %.3f" % (a["run_id"], cs["dp"], "、粒子の帯なし" if cs.get("nb", 1) == 0 else "", cs["p0u"], cs["p0c"], a["cos_amp"], a["expect"], a["ratio"]),
                yticks=np.arange(-0.8, 0.81, 0.4))
        ax.line(x, d, PAL[0], 2, label="FLIP（45〜60 s の平均 − 始めの水面）")
        ax.line(x, a["expect"] * np.cos(cs["k"] * x), (0, 0, 0), 1, dash=True, label="式 η = −p0 cos(kx)/(ρg)")
        ax.hline(0, (60, 60, 60))
        ax.legend("tr")
    sh.save(os.path.join(FIG, "T1_pressure_units.png"))


def t2_fig():
    """T2：進む波の振幅（1 波長の窓で、戻る波と分けて合わせた値）を、風なしの計算の同じ場所の値で割った比。"""
    p = os.path.join(V, "t2_summary.json")
    if not os.path.exists(p):
        return
    S = json.load(open(p, encoding="utf8"))
    N = json.load(open(os.path.join(V, "runs", S["base"], "ana.json"), encoding="utf8"))
    xN = np.array([l["x"] for l in N["local"]]); aN = np.array([l["a"] for l in N["local"]])
    sh = Sheet(1700, 760, "T2 風の圧力で波が育つか（周期 5 s・水深 25 m・高さ 1.56 m、粒子 0.25 m、U10 30 m/s）")
    x0 = S["x_meas"][0]
    ax = Ax(sh, (110, 110, 1650, 620), (x0 - 10, S["x_meas"][1] + 10), (0.9, 1.3), "x (m)", "進む波の振幅 ÷ 風なしの振幅",
            "1 波長の窓ごとの進む波の振幅の比（点と実線：FLIP、点線：入れた圧力の式 γ = P0kω/(ρg) から決まる増え方）", yticks=np.arange(0.9, 1.31, 0.05))
    ax.hline(1.0, (60, 60, 60))
    cols = {"_T2M": PAL[1], "_T2J": PAL[2], "_T2MT": PAL[3]}
    for r in S["runs"]:
        tag = "_" + r["run_id"].split("_")[-1]
        col = cols.get(tag, PAL[4])
        W = json.load(open(os.path.join(V, "runs", r["run_id"], "ana.json"), encoding="utf8"))
        xW = np.array([l["x"] for l in W["local"]]); aW = np.array([l["a"] for l in W["local"]])
        rat = aW / np.interp(xW, xN, aN)
        ax.line(xW, rat, col, 2, label="%s（FLIP、γ の比 %.2f）" % (r["label"], r["ratio_to_theory"]))
        ax.points(xW, rat, col, r=4)
        xx = np.linspace(xW[0], xW[-1], 50)
        if r["gamma_theory"] > 0:
            ax.line(xx, np.exp(r["gamma_theory"] / (2 * S["cg"]) * (xx - xW[0])) * rat[0], col, 1, dash=True)
    ax.legend("tl")
    sh.text((120, 680), "比は窓の最初の値から始めた。Miles 型 + 接線の応力の点線は Miles 型と同じ（圧力の式は同じで、接線の応力の効きを比べる相手の式は持っていない）。", 12)
    sh.save(os.path.join(FIG, "T2_wind_growth.png"))


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "b1"):
        b1_summary(); b1_convergence()
    if what in ("all", "profiles"):
        for p in glob.glob(os.path.join(V, "runs", "B1_*")):
            profile(os.path.basename(p))
    if what in ("all", "b2"):
        for p in glob.glob(os.path.join(V, "runs", "B2_*")):
            b2_fig(os.path.basename(p))
    if what in ("all", "t1"):
        t1_fig()
    if what in ("all", "t2"):
        t2_fig()
    print("figs in", FIG)
