# -*- coding: utf-8 -*-
"""FLIP39 D1-1 の図（日本語の札）と、まとめの mech.json。入力は d1_mech.py の mech_raw.json と FLIP37 の hf.npz。"""
import sys, os, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *
from d1_plot import Sheet, Ax, PAL, colormap, font
from PIL import Image

D = json.load(open(os.path.join(OUT, "mech_raw.json"), encoding="utf-8"))
P2, P1, P3, RAYS = D["P2"], D["P1"], D["P3"], D["rays"]
A = lambda v: np.array(v, float)


def pe_series(rid):
    rj, hf = load_run(rid)
    e = hf["eta"]; x = hf["x"]; t = hf["t"]
    m = (x >= 100) & (x <= 700)
    pe = np.array([np.nansum(e[f][:, m] ** 2) for f in range(len(t))])
    return t, pe / pe[0]


def pe_p1(rid):
    d = np.load(os.path.join(FLIP37, "P1", rid, "eta.npz"))
    m = (d["x"] >= 100) & (d["x"] <= 700)
    pe = np.nansum(d["eta"][:, m] ** 2, axis=1)
    return d["t"], pe / pe[0]


# ------------------------------------------------------------------ 図 M1：頂の高さの歩み・位置エネルギー・x と水深
sh = Sheet(1800, 1250, "D1-1 図M1：z=0 の頂の高さは入力でほぼ決まっている（FLIP37 の既存の計算を測った値。線形の見込みは推定）")
ax = Ax(sh, (90, 110, 860, 560), (0, 11), (0, 26), "時刻 t (s)", "頂 (m)", "① z=0 の頂の高さ（実線＝FLIP の測定、点線＝同じ初めの波を線形・平らな海で進めた推定）",
        xticks=range(0, 12), yticks=range(0, 27, 2))
series = [("R18_X30L120LG_H39", P2, PAL[1]), ("R12_L120X30_H37", P2, PAL[3]), ("R08_L120_H33", P2, PAL[0]), ("B025H32_T14_H32_n4_hr26", P1, PAL[2])]
for rid, src, col in series:
    r = src[rid]; tr = A(r["track"])
    tt = tr[:, 0]; on = r["onset"].get("t_any") or r["onset"].get("t_z0")
    sel = tt <= (on + 0.6 if on else 10)
    ax.line(tt[sel], tr[sel, 1], col, 2, label=r["label"])
    li = A(r["linear"]); ax.line(li[:, 0], li[:, 1], col, 2, dash=True)
    if on:
        k = int(np.argmin(abs(tt - on))); ax.points([tt[k]], [tr[k, 1]], col, 5)
tr3 = A(P3["track"]); ax.line(tr3[:, 0], tr3[:, 1], (0, 0, 0), 2, label="P3（R18 の 2.96 s から 0.25 m で）")
ax.points([P3["onset"]["t_z0"]], [P3["onset"]["crest_z0_m"]], (0, 0, 0), 5)
ax.legend("br", 11)
sh.text((95, 603), "● ＝砕け始め（どれかの断面で頂の水の速さ／頂の進む速さ > 0.85）。t=0 の値が入力（hot start の頂）。", 13)
sh.text((95, 623), "どの計算も、t≈2.4〜3.0 s に入力の 58〜74 % まで下がり、砕け始めで入力の 0.94〜1.08 倍に戻る。線形・平らな海の推定の最小は ±30° で 100 %、一列で 84〜86 %。", 13)

ax2 = Ax(sh, (980, 110, 1750, 560), (0, 10), (0.3, 1.1), "時刻 t (s)", "比", "② 水槽の位置エネルギー ∫η² の t=0 との比（x 100〜700 m、全幅）",
         xticks=range(0, 11), yticks=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1])
for rid, col in [("R18_X30L120LG_H39", PAL[1]), ("R08_L120_H33", PAL[0]), ("R05_L120_H29", PAL[4])]:
    t, pe = pe_series(rid); s = t <= 9.0
    ax2.line(t[s], pe[s], col, 2, label=P2[rid]["label"])
t, pe = pe_p1("B025H32_T14_H32_n4_hr26"); s = t <= 9.5
ax2.line(t[s], pe[s], PAL[2], 2, label=P1["B025H32_T14_H32_n4_hr26"]["label"])
ax2.hline(1.0)
ax2.legend("br", 11)
sh.text((985, 603), "線形の進む波なら位置エネルギーは時間で変わらない（運動エネルギーと半々）。測った値は T/4≈3.5 s で 0.46〜0.55 まで下がって戻る。", 13)
sh.text((985, 623), "初めの水面と流速の組が、進む波だけになっていないことを示す（原因は未確認。§1.2）。この戻りが ① の「回復」に当たる。", 13)

# ③ 頂の高さと x、水深
r = P2["R18_X30L120LG_H39"]; tr = A(r["track"])
on = r["onset"]["t_any"]; s = tr[:, 0] <= on + 0.01
ax3 = Ax(sh, (90, 700, 860, 1150), (320, 560), (0, 26), "頂の位置 x (m)（z=0）", "頂 (m)", "③ R18：頂の高さと位置。灰色＝水深 (m)÷3、緑の点線＝入力の頂×線形の浅水係数 Ks(h)/Ks(60 m)",
          xticks=range(320, 561, 20), yticks=range(0, 27, 2))
p = dict(r["parms"]); p.setdefault("Lz", 240.0); p.setdefault("lens_z0", 0.0); p["lg1_d"] = 0.0; p["lg2_d"] = 0.0
tk = Tank(p)
xx = np.arange(320, 561, 2.0); hh = tk.depth(xx, 0 * xx)
ax3.line(xx, hh / 3, (150, 150, 150), 2, label="水深÷3（z=0）")
om = 2 * np.pi / 14.0
ax3.line(xx, r["input"]["crest_z0_m"] * kshoal(om, hh) / kshoal(om, 60.0), PAL[2], 2, dash=True, label="入力の頂×Ks（線形の浅水変形）")
ax3.line(tr[s, 2], tr[s, 1], PAL[1], 2, label="FLIP の頂（0〜7.08 s）")
ax3.vline(420, (120, 120, 120), "斜面の始まり 420 m"); ax3.vline(r["onset"]["x"], PAL[1], "砕け始め")
ax3.legend("bl", 11)

# 表
T0 = 1000
sh.text((T0, 690), "④ 測った値（z=0、FLIP37 の既存の計算）", 16, bold=True)
rows = [("計算", "入力の頂", "入力 H/L", "限界比", "落ち込み", "砕け始めの頂", "入力比", "水深", "線形 Ks")]
for rid in ("R05_L120_H29", "R08_L120_H33", "R12_L120X30_H37", "R15_X30O20_H37", "R16_X30L120LG_H37", "R18_X30L120LG_H39"):
    q = P2[rid]
    rows.append((rid.split("_")[0], "%.1f m" % q["input"]["crest_z0_m"], "%.3f" % q["input"]["steep_H_over_L"], "%.2f" % q["input"]["ratio_to_miche"],
                 "%.1f m（%.1f s）" % (q["dip"]["crest_m"], q["dip"]["t"]), "%.1f m" % q["onset"]["crest_z0_m"],
                 "%.2f" % (q["onset"]["crest_z0_m"] / q["input"]["crest_z0_m"]), "%.1f m" % q["onset"]["depth_m"], "%.3f" % q["onset"]["Ks_lin"]))
q = P1["B025H32_T14_H32_n4_hr26"]
rows.append(("P1最良", "%.1f m" % q["input"]["crest_z0_m"], "%.3f" % q["input"]["steep_H_over_L"], "%.2f" % q["input"]["ratio_to_miche"],
             "%.1f m（%.1f s）" % (q["dip"]["crest_m"], q["dip"]["t"]), "%.1f m" % q["onset"]["crest_z0_m"],
             "%.2f" % (q["onset"]["crest_z0_m"] / q["input"]["crest_z0_m"]), "%.1f m" % q["onset"]["depth_m"], "%.3f" % q["onset"]["Ks_lin"]))
rows.append(("P3", "（R18 から）", "", "", "", "%.1f m" % P3["onset"]["crest_z0_m"], "%.2f" % (P3["onset"]["crest_z0_m"] / P2["R18_X30L120LG_H39"]["input"]["crest_z0_m"]), "", ""))
cw = [70, 90, 75, 60, 130, 110, 60, 70, 70]
for i, rw in enumerate(rows):
    X = T0
    for j, c in enumerate(rw):
        sh.text((X, 725 + 26 * i), c, 13, bold=(i == 0)); X += cw[j]
sh.text((T0, 725 + 26 * len(rows) + 8), "限界比＝入力の (頂−前の谷)/波長 を、その水深の砕ける限界 0.142·tanh(kh)（Miche）で割った値。", 12)
sh.text((T0, 745 + 26 * len(rows) + 8), "入力比＝砕け始めの頂 ÷ t=0 の頂。線形 Ks＝沖 60 m から砕け始めの水深までの浅水係数の比（周期 14 s）。", 12)
sh.text((T0, 765 + 26 * len(rows) + 8), "周期 14 s では水深 60→35 m で群速度がほぼ変わらず、線形の浅水変形は ±1 % しか高さを変えない。", 12)
sh.save(os.path.join(OUT, "sheet_m1_crest_history.png"))

# ------------------------------------------------------------------ 図 M2：x–t 図
sh = Sheet(1800, 900, "D1-1 図M2：z=0 の水面の x–t 図（色＝水面の高さ η、赤が高い）。黒＝斜面の始まり、灰＝岩棚の縁")
for k, (rid, ttl) in enumerate([("R18_X30L120LG_H39", "R18（3D、±30°、0〜10 s）"), ("R08_L120_H33", "R08（3D、一列、0〜10 s）")]):
    rj, hf = load_run(rid)
    e = hf["eta"]; x = hf["x"]; t = hf["t"]; iz = int(np.argmin(abs(hf["z"])))
    sx = (x >= 100) & (x <= 700); st = t <= 10.0
    img = colormap(e[st][:, iz][:, sx], -20, 20)
    im = Image.fromarray(img[::-1]).resize((780, 640), Image.NEAREST)
    X0 = 70 + k * 880; Y0 = 120
    sh.im.paste(im, (X0, Y0))
    sh.text((X0, Y0 - 30), ttl, 15, bold=True)
    for xv, col in [(420, (0, 0, 0)), (556, (110, 110, 110))]:
        px = X0 + (xv - 100) / 600 * 780
        sh.d.line([(px, Y0), (px, Y0 + 640)], fill=col, width=2)
    for tv in range(0, 11, 2):
        py = Y0 + 640 - tv / 10 * 640
        sh.d.line([(X0 - 5, py), (X0, py)], fill=(0, 0, 0)); sh.text((X0 - 30, py - 8), "%d s" % tv, 12)
    for xv in range(100, 701, 100):
        px = X0 + (xv - 100) / 600 * 780
        sh.d.line([(px, Y0 + 640), (px, Y0 + 645)], fill=(0, 0, 0)); sh.text((px - 14, Y0 + 648), "%d" % xv, 12)
    sh.text((X0 + 330, Y0 + 668), "x (m)", 13)
sh.text((70, 820), "読み方：右上へ伸びる赤い帯が頂の通り道。t≈2〜4 s で頂の色が薄く（低く）なり、斜面の始まりの先で濃さが戻る。頂の後ろ（x 150〜250 m）にも新しい山が育つ。", 14)
sh.text((70, 845), "どちらも、波の群が後から一点に集まる形（右上へ収束する何本もの帯）ではなく、t=0 に置いた一つの頂がそのまま進む形である。", 14)
sh.save(os.path.join(OUT, "sheet_m2_xt.png"))

# ------------------------------------------------------------------ 図 M3：交わる二つの列は集まっているか
sh = Sheet(1800, 1200, "D1-1 図M3：±30° の二つの列は計算の中で集まっていない（模様は t=0 に置かれ、砕け始めまでに弱まる）")
ax = Ax(sh, (90, 110, 860, 560), (-120, 120), (0, 1.1), "峰に沿う位置 z (m)", "比", "① 峰に沿う頂の高さ ÷ z=0 の頂（R18）。点線＝初めの模様 cos(kz·z)",
        xticks=range(-120, 121, 40), yticks=[0, 0.2, 0.4, 0.6, 0.8, 1.0])
r = P2["R18_X30L120LG_H39"]; z = A(r["z"])
for nm, col, lab in [("t0", PAL[0], "t=0（入力）"), ("toe", PAL[2], "足元 x=400 m を通る時"), ("onset", PAL[1], "砕け始め 7.08 s")]:
    pr = r["prof"][nm]; cl = A(pr["line"]); ax.line(z, cl / pr["crest_z0"], col, 2, label=lab + "：%.1f m" % pr["crest_z0"])
k0 = kdisp(2 * np.pi / 14, 60.0)
ax.line(z, np.cos(k0 * np.sin(np.radians(30)) * z), (0, 0, 0), 1, dash=True, label="cos(k0 sin30°·z)")
r8 = P2["R08_L120_H33"]; pr = r8["prof"]["onset"]; ax.line(z, A(pr["line"]) / pr["crest_z0"], PAL[7], 2, label="R08（一列）の砕け始め")
ax.legend("bl", 11)

ax2 = Ax(sh, (980, 110, 1750, 560), (0, 9), (0.2, 0.55), "時刻 t (s)", "割合", "② 集まりの指標：頂の前後の η² のうち |z|<30 m にある割合（一様なら 0.25）",
         xticks=range(0, 10), yticks=[0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55])
for i, rid in enumerate(("R10_L120X30_H33", "R12_L120X30_H37", "R15_X30O20_H37", "R16_X30L120LG_H37", "R17_X40L120_H42", "R18_X30L120LG_H39", "R08_L120_H33", "R05_L120_H29")):
    c = A(P2[rid]["conc"])
    ax2.line(c[:, 0], c[:, 2], PAL[i], 2, label=P2[rid]["label"])
ax2.hline(0.25)
ax2.legend("tr", 11)

ax3 = Ax(sh, (90, 690, 860, 1100), (0, 9), (0.9, 1.9), "時刻 t (s)", "比", "③ z=0 の頂 ÷ 峰に沿う頂の平均（z 方向の山の強さ）",
         xticks=range(0, 10), yticks=[0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9])
for i, rid in enumerate(("R10_L120X30_H33", "R12_L120X30_H37", "R15_X30O20_H37", "R16_X30L120LG_H37", "R17_X40L120_H42", "R18_X30L120LG_H39", "R08_L120_H33", "R05_L120_H29")):
    c = A(P2[rid]["conc"])
    ax3.line(c[:, 0], c[:, 1], PAL[i], 2)
X0 = 980
sh.text((X0, 690), "④ 測った値（z=0、R18）", 16, bold=True)
lines = []
for nm, lab in [("t0", "t=0（入力）"), ("toe", "足元を通る時"), ("onset", "砕け始め")]:
    pr = r["prof"][nm]
    lines.append("%s：頂 %.1f m、頂÷平均 %.2f、頂÷z=±100 m %.2f、半分の高さの幅 %.0f m、0.8 倍以上の長さ %.0f m、集まりの指標 %.3f" % (
        lab, pr["crest_z0"], pr["center_over_mean"], pr["center_over_edge100"], pr["half_width_m"], pr["len_above_08"], pr["conc30"]))
lines += ["",
          "t=0 の頂の列（x=330 m）の η(z) を、滑る壁の箱の z 方向の余弦の級数に分けると、",
          "z=0 の高さ 19.5 m のうち %.0f %% が z に一様な成分（向き 0°）。±30° の模様の分は残りの %.0f %%。" % (100 * r["input"]["n0_share_at_z0"], 100 - 100 * r["input"]["n0_share_at_z0"]),
          "",
          "同じ入力のエネルギーの高さ HE＝4·√(η² の平均)（t=0、x 120〜480 m、全幅）あたりの砕け始めの頂：",
          "  ±30°：R12 %.3f、R16 %.3f、R18 %.3f　一列：R05 %.3f、R08 %.3f" % tuple(P2[k]["onset"]["crest_z0_m"] / P2[k]["input"]["HE_m"] for k in ("R12_L120X30_H37", "R16_X30L120LG_H37", "R18_X30L120LG_H39", "R05_L120_H29", "R08_L120_H33")),
          "  → 交わる列は、同じエネルギーで一列より約 5〜8 % 高い頂になった（入力の時点で 5 %）。",
          ]
for i, s in enumerate(lines):
    sh.text((X0, 725 + 22 * i), s, 12)
sh.save(os.path.join(OUT, "sheet_m3_crossing.png"))

# ------------------------------------------------------------------ 図 M4：海底による屈折（レンズ）
sh = Sheet(1800, 700, "D1-1 図M4：レンズの屈折の集まりは、波線の理論（推定）では大きいが、測った頂ではほとんど出ていない")
ax = Ax(sh, (90, 110, 860, 560), (420, 560), (0.8, 2.1), "x (m)", "Kr", "① 波線の理論による z=0 の屈折係数 Kr（周期 14 s、推定）",
        xticks=range(420, 561, 20), yticks=[0.8, 1.0, 1.2, 1.4, 1.6, 1.8, 2.0])
for nm, lab, col in [("R18", "R18 の海底", PAL[1]), ("straight", "まっすぐの岩棚", PAL[7])]:
    for th, dash in (("0", False), ("30", True)):
        w = RAYS[nm][th]; xs_ = A(w["x"]); ks_ = A(w["Kr_z0"]); mm_ = (xs_ >= 310) & (xs_ <= 560); ax.line(xs_[mm_], ks_[mm_], col, 2, dash=dash, label="%s、%s°" % (lab, "0" if th == "0" else "±30"))
ax.vline(502, PAL[1], "R18 砕け始め"); ax.vline(545, (0, 0, 0), "垂直を越す")
ax.legend("tl", 11)
X0 = 980
sh.text((X0, 110), "② 測った値（FLIP）", 16, bold=True)
q12, q15, q16, q8, q5 = (P2[k] for k in ("R12_L120X30_H37", "R15_X30O20_H37", "R16_X30L120LG_H37", "R08_L120_H33", "R05_L120_H29"))
L = ["レンズあり R12 とレンズなし R15（どちらも ±30°・入力 37 m）：",
     "  頂が x=500 m を通る時 %.2f m と %.2f m（%+.0f %%）、砕け始め %.2f m と %.2f m（%+.0f %%）" % (
         q12["at_x500"]["crest_m"], q15["at_x500"]["crest_m"], 100 * (q12["at_x500"]["crest_m"] / q15["at_x500"]["crest_m"] - 1),
         q12["onset"]["crest_z0_m"], q15["onset"]["crest_z0_m"], 100 * (q12["onset"]["crest_z0_m"] / q15["onset"]["crest_z0_m"] - 1)),
     "  （R15 は等深線が 20° 斜めで、z=0 の斜面の始まりが 464 m。水深の違いは線形の Ks で ±1 % 以内）",
     "低い棚あり R16 と なし R12（±30°・37 m）：砕け始めの頂 %.2f m と %.2f m" % (q16["onset"]["crest_z0_m"], q12["onset"]["crest_z0_m"]),
     "一列＋レンズ R08：砕け始めの頂÷z=±100 m の頂 %.2f（R05 は %.2f）" % (q8["prof"]["onset"]["center_over_edge100"], q5["prof"]["onset"]["center_over_edge100"]),
     "  → 波線の理論の 0° の見込み（x 480〜500 m で 1.14〜1.28 倍）は、測った頂には出ていない。",
     "",
     "理由の見立て（推定）：レンズの広がり（ガウスの幅 45 m）が波長（230〜270 m）より",
     "ずっと小さく、波線の理論の前提（海底の変化が波長より大きい）が成り立たない。",
     "回折で横へ広がる。また斜面の始まりから砕け始めまで 80 m（波長の 1/3）しかない。",
     "±30° の成分には、レンズは z=0 へほとんど集めない（理論でも 0.94 対 0.91）。"]
for i, s in enumerate(L):
    sh.text((X0, 145 + 24 * i), s, 13)
sh.save(os.path.join(OUT, "sheet_m4_refraction.png"))
print("figs done")
