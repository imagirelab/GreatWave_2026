# -*- coding: utf-8 -*-
"""報告の図（Docs/Evidence/Basilisk/fig_*.png）を作る。

  fig_A_levels.png  ：A の量が格子の細かさでどう動くか（破線が論文の値）
  fig_BC_score3.png ：B・C の score3（3 つの内訳を積んだ横棒、小さいほど原画に近い）
  fig_B_shapes.png  ：B の S1・S2・S5 の score3 最小のコマと着水のコマ、原画の輪郭を重ねる
  fig_top3.png      ：C の上位 3 つの score3 最小のコマ

使い方：python3 figures.py
"""
import os, sys, json, math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gwread as G  # noqa: E402
import gwruler as R  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
EVID = os.environ.get("GW_EVID", os.path.join(REPO, "Docs", "Evidence", "Basilisk"))
ANA = os.environ.get("GW_ANA", "/opt/gw/ana")
RUNS = os.environ.get("GW_RUNS", "/opt/gw/runs")
CASES = json.load(open(os.path.join(HERE, "..", "cases.json"), encoding="utf8"))
H0M = 19.0

for f in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",):
    if os.path.exists(f):
        font_manager.fontManager.addfont(f)
plt.rcParams.update({"font.family": ["Noto Sans CJK JP", "DejaVu Sans"], "axes.spines.top": False, "axes.spines.right": False,
                     "axes.edgecolor": "#8a8984", "axes.labelcolor": "#2b2b29", "xtick.color": "#52514e",
                     "ytick.color": "#52514e", "axes.grid": True, "grid.color": "#e6e5e1", "grid.linewidth": 0.8,
                     "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb"})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED = "#0b0b0b", "#8a8984"

PAPER = dict(t_touchdown=19.96, eta_c_touchdown=0.64, x_tip_touchdown=42.05, A_O_over_Htd2=0.352, A_J_over_Htd2=0.219,
             W_over_L=0.300, theta_O_deg=29.0, jet_width=0.05)


def load(name):
    p = os.path.join(ANA, name + ".json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def fig_A_levels(names=("A_L9", "A_L10", "A_L11", "A_L12", "A_L13")):
    rows = []
    for n in names:
        d = load(n)
        if d and d["summary"].get("t_touchdown") is not None:
            c = CASES[n]
            rows.append((c["lbox"] / 2 ** c["level"], c["level"], d["summary"]))
    if not rows:
        return
    items = [("t_touchdown", "着水の時刻 t̃"), ("eta_c_touchdown", "着水の時の頂の高さ / h0（論文 Hb）"),
             ("x_tip_touchdown", "着水の時の唇の先の x / h0（論文 xbp）"), ("A_O_over_Htd2", "空洞の面積 A_O / H²"),
             ("A_J_over_Htd2", "噴流の面積 A_J / H²"), ("W_over_L", "空洞の縦横の比 W/L"),
             ("theta_O_deg", "空洞の向き |θ_O|（度）"), ("jet_width", "噴流の幅 / h0")]
    fig, axs = plt.subplots(2, 4, figsize=(15, 6.6))
    dx = np.array([r[0] for r in rows])
    for ax, (k, lab) in zip(axs.ravel(), items):
        v = np.array([abs(r[2][k]) if r[2].get(k) is not None else np.nan for r in rows])
        ax.plot(dx, v, "-", color=BLUE, lw=2)
        ax.plot(dx, v, "o", ms=8, color=BLUE, mec="#fcfcfb", mew=2)
        for x, y, r in zip(dx, v, rows):
            ax.annotate("%d 段" % r[1], (x, y), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=8, color="#52514e")
        ax.axhline(PAPER[k], color=MUTED, ls="--", lw=1.5)
        ax.annotate("論文 %g" % PAPER[k], (1, PAPER[k]), xycoords=("axes fraction", "data"), xytext=(-4, 4),
                    textcoords="offset points", ha="right", fontsize=8, color="#52514e")
        ax.set_xscale("log"); ax.invert_xaxis()
        ax.set_title(lab, fontsize=10, color=INK)
        ax.set_xlabel("最も細かい格子 Δ / h0（右ほど細かい）", fontsize=8)
    fig.suptitle("A：Feddersen ら 2024 の風なしの算例を Basilisk で解き直した量（点）と論文の値（破線）。定義は報告の §3.1（論文の本文は未読、定義は推測）",
                 fontsize=10, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(os.path.join(EVID, "fig_A_levels.png"), dpi=110)
    plt.close(fig)


def fig_score3(names, out="fig_BC_score3.png", title=""):
    rows = []
    for n in names:
        d = load(n)
        if d and d["ruler"]["best"]:
            b = d["ruler"]["best"]
            rows.append((n, b["score3"], b["score3_parts"], CASES.get(n, {}).get("short_ja", n)))
    if not rows:
        return
    rows.sort(key=lambda r: r[1])
    fig, ax = plt.subplots(figsize=(11, 0.36 * len(rows) + 1.6))
    y = np.arange(len(rows))[::-1]
    keys = [("face_chord_deg_01_05", "前の面の弦の角度", BLUE), ("front_x01_rel", "前の足", ORANGE), ("hood_area", "覆いの面積", AQUA)]
    left = np.zeros(len(rows))
    for k, lab, col in keys:
        w = np.array([r[2][k] for r in rows])
        ax.barh(y, w, left=left, color=col, height=0.62, label=lab, edgecolor="#fcfcfb", linewidth=2)
        left += w
    for yy, r in zip(y, rows):
        ax.text(r[1] + 0.03, yy, "%.2f" % r[1], va="center", fontsize=8, color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(["%s　%s" % (r[0], r[3]) for r in rows], fontsize=8)
    ax.set_xlabel("score3（帯の外の距離 ÷ 原画の値、各 1 まで。0 は 3 つとも原画の帯の中）", fontsize=9)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=8, frameon=False)
    ax.grid(axis="y", visible=False)
    ax.set_title(title, fontsize=10, color=INK, loc="left", pad=22)
    fig.tight_layout()
    fig.savefig(os.path.join(EVID, out), dpi=110)
    plt.close(fig)


def _panel(ax, name, r, label):
    fr = G.read_frame(os.path.join(RUNS, name, r["file"]))
    M, X, Z = R.frame_mask(fr)
    ax.imshow(M, origin="lower", extent=[X[0] / H0M, X[-1] / H0M, Z[0] / H0M, Z[-1] / H0M], cmap="Blues", vmin=0, vmax=1.6,
              interpolation="nearest")
    outer, inner, d = R.S.print_outline()
    P = R._P
    s = r["eta_c"] / P["eta_c"]
    for pl in (outer, inner):
        xx = pl[:, 0]; zz = (R.S.Y_HORIZON - pl[:, 1]) / R.S.STRETCH
        ax.plot((r["x_c"] + (xx - P["x_c"]) * s) / H0M, zz * s / H0M, "-", color=ORANGE, lw=1.4)
    ax.axhline(0, color=MUTED, lw=0.8, ls="--")
    xc = r["x_c"] / H0M
    ax.set_xlim(xc - 1.6, xc + 1.4); ax.set_ylim(-0.35, 1.0); ax.set_aspect("equal")
    ax.set_title("%s　t̃ = %.2f　score3 = %.2f\n前の面 %.0f°・前の足 %.2f・覆い %.3f・唇の下 %.2f・唇の厚み %.2f" % (
        label, r["t"], r["score3"], r["face_chord_deg_01_05"], r["front_x01_rel"], r["hood_area"], r.get("gap_max", float("nan")),
        r.get("lip_thick_mid", float("nan"))), fontsize=8, color=INK)
    ax.set_xlabel("x / h0", fontsize=8); ax.set_ylabel("y / h0", fontsize=8)
    ax.grid(False)


def fig_shapes(names, out, title):
    ok = [n for n in names if load(n) and load(n)["ruler"]["best"]]
    if not ok:
        return
    fig, axs = plt.subplots(len(ok), 2, figsize=(12, 3.3 * len(ok)), squeeze=False)
    for i, n in enumerate(ok):
        d = load(n)
        _panel(axs[i, 0], n, d["ruler"]["best"], "%s　score3 最小" % n)
        if d["ruler"]["touchdown"]:
            _panel(axs[i, 1], n, d["ruler"]["touchdown"], "%s　着水" % n)
        else:
            axs[i, 1].set_visible(False)
    fig.suptitle(title, fontsize=10, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(os.path.join(EVID, out), dpi=100)
    plt.close(fig)


def bc_names(done):
    """score3 の図に入れる算例：B（S1・S2・S5 の各段、頂 15 h0 と論文の物性の確かめは除く）と C。"""
    return [n for n in done if (n.startswith("B_S") and "x15" not in n and "S1p" not in n) or n.startswith("C")]


if __name__ == "__main__":
    os.makedirs(EVID, exist_ok=True)
    fig_A_levels()
    lv = sys.argv[1] if len(sys.argv) > 1 else "L11"
    fig_score3(bc_names([n for n in CASES if load(n)]), "fig_BC_score3.png",
               "B・C の score3（score3 最小のコマ）。格子の段は算例の名前の末尾（L10 = 10 段）")
    fig_shapes(["B_S1_" + lv, "B_S2_" + lv, "B_S5_" + lv], "fig_B_shapes.png",
               "B：S1・S2・S5（重力だけに近い条件）。橙の線は原画の輪郭（縦÷1.3、頂の高さと位置を合わせた）")
    top = json.load(open(os.path.join(EVID, "top3.json"), encoding="utf8"))["fine"] if os.path.exists(os.path.join(EVID, "top3.json")) else []
    if top:
        fig_shapes(top, "fig_top3.png", "C の上位 3 つを細かい格子で解き直した結果。橙の線は原画の輪郭")
