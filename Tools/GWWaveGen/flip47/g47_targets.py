# -*- coding: utf-8 -*-
"""FLIP47：文献の目標と、海底を変える 2D の組（6 本）の案を数で出す（py -3.10 -B。numpy だけ）。
2026-10-12 文献と走らせる組の案の役（Claude）が書いた。Houdini は使わない。書くのは Unity/Build/FLIP47/targets.json だけ。
読む物：Unity/Build/STUDY52/shape_measures.json（原画と FLIP42 の物差しの値）、Unity/Build/FLIP47/lit/lit_ruler.json（g47_lit_ruler.py の出力）。

式の出典（本文で確かめた）：
  Pick & Feddersen 2026（JFM 1040 A8）：ψ0 = s/(H0/h0)^(1/4)（式 3.5）、S0 = 1.521 s/(H0/h0)^(1/2)（式 3.3）、
    γb = Hb/hb = 0.871 exp(11.874 ψ0)（3.6）、γb = 0.841 exp(6.421 S0)（3.4、Grilli ら 1997 の式）、
    AO/HI² = 5.319 ψ0 − 0.043（3.7）、AJ/HI² = 37.072 ψ0² − 0.587 ψ0 + 0.020（3.8）、WO/LO = 1.661 ψ0 + 0.298（3.9）、
    θO = −5746.4 ψ0² + 225.2 ψ0 + 48.4（3.10）、急になる速さ = 2.476 ψ1² + 0.684 ψ1 + 0.047、ψ1 = s/(H0/h0)^(3/2)（3.11・3.12）。
    当てはめの範囲：噴流が斜面の上に着く物だけ（S0 < 0.2、ψ0 < 0.1）。s = 1/10 は全部、s = 1/15・H0/h0 0.2 は浅い平らな所の上で着き、外した。
  Grilli・Svendsen・Subramanya 1997：S0 < 0.025 こぼれ、0.025〜0.30 巻き、0.30〜0.37 寄せ（二次の資料。原典は読めていない）。
  Feddersen ら 2024（JFM 1000 A48）：E1a の目標（§2.1・§3.3〜3.5、図 5〜7）。
"""
import os, sys, json, math
sys.dont_write_bytecode = True
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
B47 = REPO + "/Unity/Build/FLIP47"
G = 9.80665
H0 = 19.0
TS = math.sqrt(H0 / G)          # 1.392 s
CS = math.sqrt(G * H0)          # 13.65 m/s
FPS = 24.0


# ------------------------------------------------------------------ Pick & Feddersen 2026 の式
def psi0(s, r): return s / r ** 0.25
def S0(s, r): return 1.521 * s / r ** 0.5
def psi1(s, r): return s / r ** 1.5
def AJ(p): return 37.072 * p * p - 0.587 * p + 0.020
def AO(p): return 5.319 * p - 0.043
def WL(p): return 1.661 * p + 0.298
def thO(p): return -5746.4 * p * p + 225.2 * p + 48.4
def gam_psi(p): return 0.871 * math.exp(11.874 * p)
def gam_S0(s0): return 0.841 * math.exp(6.421 * s0)
def steep_rate(p1): return 2.476 * p1 * p1 + 0.684 * p1 + 0.047


def grilli_type(s0):
    if s0 < 0.025: return "spilling（こぼれ）"
    if s0 < 0.30: return "plunging（巻き）"
    if s0 < 0.37: return "surging（寄せ）"
    return "no breaking（崩れない）"


# 着水の時の頂 HI/h0（H0/h0 0.6）【推定】
#   1/30〜1/15：P&F の s 1/30 の本文の値 0.707 と、図 5c（s 1/15）を測った 0.599 の間を s で直線に。
#   1/10：1/15 の 0.599 に、H0/h0 0.2 の比（本文の s 1/10 の HI 0.212 ÷ 図 5a を測った s 1/15 の 0.239 = 0.887）を掛ける。
#   それより急（1:7 の岩棚）：式で出さない（None）。
def HI_interp(s):
    s1, h1, s2, h2 = 1 / 30, 0.707, 1 / 15, 0.599
    if s <= s2 + 0.003:
        return h1 + (h2 - h1) * (s - s1) / (s2 - s1), "P&F の 1/30（0.707）と 1/15（0.599）の間を s で直線に"
    if abs(s - 0.1) < 1e-9:
        return h2 * 0.212 / 0.239, "1/15 の 0.599 × H0/h0 0.2 の 1/10 と 1/15 の比 0.887"
    return None, "式で出さない"


HB_OVER_HI = 0.749 / 0.707      # P&F の例 (i)（s 1/30、H0/h0 0.6）：崩れ始め 0.749、着水 0.707


# ------------------------------------------------------------------ 原画の帯と点数（走らせる前に決める）
def print_bands(s52):
    P = s52["print"]
    names = ["drawn", "cn", "cn_swl_low", "cn_swl_high"]
    def rng(k): return [min(P[n][k] for n in names), max(P[n][k] for n in names)]
    return dict(
        face_chord_deg_01_05=dict(center=P["cn"]["face_chord_deg_01_05"], band=rng("face_chord_deg_01_05")),
        front_x01_rel=dict(center=P["cn"]["front_x01_rel"], band=rng("front_x01_rel")),
        gap_max=dict(center=P["cn"]["gap_max"], band=[min(P[n]["gap_max"] for n in names), None], note_ja="原画は下限（唇の下の前の面の下は描かれていない）"),
        lip_thick_mid=dict(center=P["cn"]["lip_thick_mid"], band=rng("lip_thick_mid")),
        hood_area=dict(center=P["cn"]["hood_area"], band=rng("hood_area")),
        reach=dict(center=P["cn"]["reach"], band=rng("reach"), note_ja="参考（点数に入れない）"),
        tip_z=dict(center=P["cn"]["tip_z"], band=rng("tip_z"), note_ja="参考（点数に入れない）"))


SCORE_KEYS = ["face_chord_deg_01_05", "front_x01_rel", "gap_max", "lip_thick_mid", "hood_area"]


def score(m, bands):
    """原画の帯の外へ出た分 ÷ 原画（cn）の値（1 で頭打ち）、の 5 つの和。帯の中なら 0。小さいほど原画に近い（0〜5）。
    頭打ちは、前の足（原画 0.25 と小さい値で割る）の 1 つだけで順位が決まらないようにするため。"""
    tot, parts = 0.0, {}
    for k in SCORE_KEYS:
        v = m.get(k)
        if v is None:
            parts[k] = None; continue
        lo, hi = bands[k]["band"]
        c = bands[k]["center"]
        d = 0.0
        if lo is not None and v < lo: d = (lo - v) / c
        if hi is not None and v > hi: d = (v - hi) / c
        d = min(d, 1.0)
        parts[k] = round(d, 3); tot += d
    parts["n_in_band"] = sum(1 for k in SCORE_KEYS if parts.get(k) == 0.0)
    return round(tot, 3), parts


# ------------------------------------------------------------------ 海底（[x m, 水深 m]。水深は静かな水面から下へ正。両端の外は端の水深で平ら）
X_TOE = 30.0 * H0                     # 570 m（E1a と同じ斜面の足）
X_END = 1130.0                        # 海底の表の終わり（E1a の全部の領域と同じ）


def slope_bed(s, h_top):
    x_top = X_TOE + (H0 - h_top) / s
    return [[0.0, H0], [X_TOE, H0], [round(x_top, 3), round(h_top, 4)], [X_END, round(h_top, 4)]], x_top


def runs():
    out = []
    # 1. E1a（Feddersen ら 2024 の海底そのもの）
    bed = [[0.0, H0], [X_TOE, H0], [742.45, 7.049], [X_END, 7.049]]
    out.append(dict(id="S1_E1a", name_ja="E1a：勾配 0.0693（1:14.4）で水深 0.371 h0 の棚（論文の海底）", s=0.0693, h_top_over_h0=0.371,
                    bed=bed, x_top=742.45, domain=[380.0, 893.0], crest=475.0, a_over_h=0.6, wave="GN", flat_kind="shelf_0.371",
                    why_ja="論文の再現と物差しの基準。論文の図 5b を同じ物差しで測った値（lit_ruler.json）と比べられる唯一の組"))
    # 2〜4. 斜面から浅い平ら（0.1 h0）へ（Pick & Feddersen の形。平らを 0.05 → 0.1 h0 にしたのは格子 0.5 m で 4 個にするため）
    for sid, s, nm in (("S2_s1-10", 0.1, "1:10"), ("S3_s1-14.4", 0.0693, "1:14.4（E1a と同じ勾配）"), ("S4_s1-20", 0.05, "1:20")):
        bed, xt = slope_bed(s, 0.1 * H0)
        out.append(dict(id=sid, name_ja="勾配 %s で水深 0.1 h0（1.9 m）の浅い平らへ" % nm, s=s, h_top_over_h0=0.1, bed=bed, x_top=xt,
                        domain=[380.0, 950.0], crest=475.0, a_over_h=0.6, wave="GN", flat_kind="shallow_flat_0.1",
                        why_ja={"S2_s1-10": "Pick & Feddersen のいちばん急な勾配。噴流が浅い平らの上（静かな水面）に着く型で、唇の下の壁が立つ見込み（図 5a の型）",
                                "S3_s1-14.4": "E1a と同じ勾配で棚だけを変える（0.371 → 0.1 h0）。棚の深さの効きを分ける。当てはめの中（ψ0 0.079）",
                                "S4_s1-20": "ゆるい側の目印（ψ0 0.057）。1:30 の値は論文の図 5d を測った値で代える（FLIP42 に近い）"}[sid]))
    # 5. 急な岩棚（Enright 2002 の 1:7 と水面下 0.2 h0 の棚）
    bed, xt = slope_bed(1.0 / 7.0, 0.2 * H0)
    out.append(dict(id="S5_ledge1-7", name_ja="急な岩棚：勾配 1:7 で水深 0.2 h0（3.8 m）の棚", s=1.0 / 7.0, h_top_over_h0=0.2, bed=bed, x_top=xt,
                    domain=[380.0, 950.0], crest=475.0, a_over_h=0.6, wave="GN", flat_kind="ledge_0.2",
                    why_ja="重力だけの 3D の巻きと空気の管が出た Enright 2002（孤立波 H/h 0.7、1:7、水面下 0.2 h の棚、2D の試しで選んだ棚）の海底。"
                           "Grilli の S0 0.28 で巻きの範囲の端。P&F の当てはめの外（ψ0 0.16）"))
    # 6. 2 段の段差（Desmons & Lubin 2022 の合わさった崩れ）
    R2, R1, X1 = 0.4, 0.848, 5.0
    xs1 = X_TOE; xs2 = X_TOE + X1 * H0
    bed = [[0.0, H0], [xs1, H0], [xs1, round((1 - R2) * H0, 4)], [xs2, round((1 - R2) * H0, 4)], [xs2, round((1 - R1) * H0, 4)],
           [X_END, round((1 - R1) * H0, 4)]]
    out.append(dict(id="S6_twostep", name_ja="2 段の段差：R2/h0 0.4（水深 11.4 m）を X1 5 h0（95 m）、その先に R1/h0 0.848（水深 2.89 m）",
                    s=None, h_top_over_h0=1 - R1, bed=bed, x_top=xs2, domain=[266.0, 950.0], crest=22.0 * H0, a_over_h=0.5, wave="GN",
                    flat_kind="two_step",
                    why_ja="Desmons & Lubin 2022 の表 4 で、R2/h1 0.4 は X1/h1 4.0・6.5 が合わさった崩れ（1.0・2.0 はふつうの巻き、10 は 2 回の崩れ）。"
                           "その真ん中の 5。波は論文に合わせて H1/h1 0.5（ほかの 5 本の 0.6 から変えた理由：合わさる窓は H1/h1 0.5 でしか調べられていない）。"
                           "段は鉛直（論文と同じ。g47_tanklib の海底の SDF は折れ線への本当の距離なので鉛直の面も扱える）"))
    return out


def water_area(bed, x0, x1, a_over_h, nx=20000):
    xs = np.linspace(x0, x1, nx)
    bx = np.array([p[0] for p in bed]); bd = np.array([p[1] for p in bed])
    d = np.interp(xs, bx, bd)
    a0 = a_over_h * H0
    kap = math.sqrt(3 * a_over_h / (4 * (1 + a_over_h))) / H0
    return float(np.sum(0.5 * (d[1:] + d[:-1]) * np.diff(xs))) + 2 * a0 / kap        # 静かな水 + 孤立波の量（GN：2 a0/κ）


def main():
    s52 = json.load(open(REPO + "/Unity/Build/STUDY52/shape_measures.json", encoding="utf8"))
    lit = json.load(open(B47 + "/lit/lit_ruler.json", encoding="utf8"))
    bands = print_bands(s52)
    # ---------------- 物差しの基準点（原画・FLIP42・文献の図）
    refs = {}
    for n in ("drawn", "cn", "cn_swl_low", "cn_swl_high"):
        m = s52["print"][n]
        refs["print_" + n] = {k: m[k] for k in SCORE_KEYS + ["reach", "tip_z", "hood_low_z"]}
    for r in s52["flip"]:
        m = s52["flip"][r]["max_overturn"]
        refs["FLIP42_%s_max_overturn" % r] = {k: m[k] for k in SCORE_KEYS + ["reach", "tip_z", "hood_low_z"]}
    for k, m in lit.items():
        if isinstance(m, dict) and "eta_c" in m:
            refs["lit_" + k] = {kk: m[kk] for kk in SCORE_KEYS + ["reach", "tip_z", "hood_low_z", "eta_c_over_h0"]}
    for k, m in refs.items():
        sc, parts = score(m, bands)
        m["score"] = sc; m["score_parts"] = parts
    # ---------------- 組の予測
    table = []
    for r in runs():
        a = r["a_over_h"]
        row = dict(r)
        x0, x1 = r["domain"]
        V = water_area(r["bed"], x0, x1, a) * (4 * 0.5)          # 板の厚さ：格子 4 個 × 0.5 m（粒子 0.25 m）
        N = 112.0 * V
        if r["s"] is not None:
            s = r["s"]
            p0 = psi0(s, a); s0 = S0(s, a); p1 = psi1(s, a)
            inside = (p0 < 0.1) and (s0 < 0.2)
            HI, how = HI_interp(s)
            g_b = gam_psi(p0)
            if HI is None:
                Hb = None; hb = None; xb = r["x_top"] / H0
            else:
                Hb = HI * HB_OVER_HI
                hb = Hb / g_b
                xb = X_TOE / H0 + (1 - hb) / s if hb > r["h_top_over_h0"] else r["x_top"] / H0
            pf = dict(psi0=round(p0, 4), S0=round(s0, 4), psi1=round(p1, 4), fit_valid=inside,
                      AJ_over_HI2=round(AJ(p0), 3), AO_over_HI2=round(AO(p0), 3), WO_over_LO=round(WL(p0), 3), thetaO_deg=round(thO(p0), 1),
                      gamma_b_psi=round(g_b, 2), gamma_b_S0=round(gam_S0(s0), 2), steepening_rate=round(steep_rate(p1), 3),
                      grilli_type=grilli_type(s0))
            rd = (lambda v, n: None if v is None else round(v, n))
            pred = dict(HI_over_h0=rd(HI, 3), HI_m=rd(None if HI is None else HI * H0, 1), Hb_over_h0=rd(Hb, 3),
                        Hb_m=rd(None if Hb is None else Hb * H0, 1), hb_over_h0_from_gamma=rd(hb, 3), x_break_over_h0=round(xb, 1),
                        x_break_m=round(xb * H0, 0), x_impact_over_h0=round(xb + (2.0 if p0 < 0.1 else 1.5), 1),
                        note_ja="HI：%s【推定】。Hb = HI × 0.749/0.707（P&F の例 (i)）。崩れる所は γb（式 3.6）から hb を出し、斜面の上の hb の所。"
                                "hb が棚・平らより浅い時は棚・平らの始めとした。着水は崩れの 2 h0 先（ψ0 ≥ 0.1 は 1.5 h0）" % how)
            if HI is None:
                pred.update(HI_range_over_h0=[0.6, 0.75], Hb_range_m=[11.4, 14.3],
                            note_ja="式の外【考え】。急で短い斜面では浅くなって高くなる分が小さい（P&F の s 1/10・H0/h0 0.2 で Hb/H0 1.13）。"
                                    "Green の式の上限は 0.6 × (1/0.2)^¼ = 0.90 h0。岩棚の始め（x 35.6 h0）を越えた直後に崩れる見込み")
        else:
            pf = dict(psi0=None, S0=None, fit_valid=False, grilli_type="段（式の外）")
            pred = dict(HI_over_h0=None, Hb_over_h0=None, x_break_over_h0=round(r["x_top"] / H0 + 1.0, 1),
                        x_impact_over_h0=round(r["x_top"] / H0 + 2.5, 1),
                        note_ja="式なし【考え】。高い段（x 35 h0）を越えた直後に崩れる見込み。Desmons & Lubin の合わさった崩れなら巻きの下の空気が"
                                "ふつうの巻きより 6 割以上大きく、噴流の幅が着水まで細らない")
        if r["id"] == "S1_E1a":
            pred.update(HI_over_h0=0.64, HI_m=12.2, Hb_over_h0=0.64, Hb_m=12.2, x_break_over_h0=40.0, x_break_m=760.0,
                        x_break_note_ja="崩れ始め（前の面が鉛直）は棚の上 39.5〜40.5 h0 の推定：Re* 2400 で噴流が出た t̃ 18.30 の頂 x 39.2 h0（図 3c）に、"
                                        "風なしの着水の遅れ（t̃ 0.83、1.2 h0）を足した。論文は風なしの崩れ始めの位置を書いていない【推定】",
                        x_impact_over_h0=42.05, note_ja="論文の DNS（風なし）の値。P&F の当てはめは AJ 0.204・AO 0.376・WO/LO 0.429・θO 30.5°（本文 §4.1 は 0.19・0.38・0.41・29〜33°）")
        # 物差しの予測（文献の図の近い物）
        key = {"S1_E1a": "F24_fig5b_Re0_t19.96", "S2_s1-10": "PF_fig5a_s1-15_H0.2_impact_on_flat", "S3_s1-14.4": "PF_fig5c_s1-15_H0.6"}.get(r["id"])
        if key:
            m = lit[key]
            rp = {k: round(m[k], 3) for k in SCORE_KEYS + ["reach", "tip_z"]}
            rp["source_ja"] = {"S1_E1a": "論文の図 5b（同じ海底・同じ波）を測った値（着水の時）",
                               "S2_s1-10": "P&F 図 5a（s 1/15・H0/h0 0.2、ψ0 0.100、浅い平らの上に着く）を測った値。S2 は ψ0 0.114 でさらに急",
                               "S3_s1-14.4": "P&F 図 5c（s 1/15・H0/h0 0.6、ψ0 0.076）を測った値。S3 は ψ0 0.079"}[r["id"]] + "【推定：近い物を写した】"
        elif r["id"] == "S4_s1-20":
            A, B = lit["PF_fig5d_s1-30_H0.6"], lit["PF_fig5c_s1-15_H0.6"]
            f = (psi0(0.05, 0.6) - psi0(1 / 30, 0.6)) / (psi0(1 / 15, 0.6) - psi0(1 / 30, 0.6))
            rp = {k: round(A[k] + f * (B[k] - A[k]), 3) for k in SCORE_KEYS + ["reach", "tip_z"]}
            rp["source_ja"] = "P&F 図 5d（1/30）と 5c（1/15）を ψ0 で直線に挟んだ値（f = %.2f）【推定】" % f
        else:
            rp = dict(source_ja="近い図がない【考え】：%s" % ("噴流が棚の上の水（水深 0.2 h0）に着く型で、S2 と同じく唇の下の壁が立ち唇が厚い側の見込み。"
                                                          "寄せ（S0 0.3）に近く、崩れが弱く跳ね返りが大きい恐れもある" if r["id"] == "S5_ledge1-7"
                                                          else "合わさった崩れなら巻きの下の空気が大きく、唇が着水まで細らない（Desmons & Lubin）。物差しの数はない"))
        if "face_chord_deg_01_05" in rp:
            rp["score"], rp["score_parts"] = score(rp, bands)
        t_imp = (pred["x_impact_over_h0"] * H0 - r["crest"]) / (1.33 * CS) if isinstance(pred["x_impact_over_h0"], float) else None
        t_end = (t_imp + 2.0) if t_imp else None
        cost = dict(water_area_m2=round(V / 2.0, 0), slab_m=2.0, volume_m3=round(V, 0), particles_M_dp0p25=round(N / 1e6, 2),
                    t_impact_s=round(t_imp, 1) if t_imp else None, t_end_s=round(t_end, 1) if t_end else None,
                    frames=int(round(t_end * FPS)) + 1 if t_end else None,
                    minutes=[round(N / 1e6 * 0.27 * t_end * FPS / 60, 0), round(N / 1e6 * 1.0 * t_end * FPS / 60, 0)] if t_end else None,
                    note_ja="粒子 = 112 × 水の体積（m³）（BigWave_Recipes_ja.md §3.5）。1 コマ = 粒子（百万）×（0.27〜1.0）s。"
                            "着水の時刻 = 頂から着水の所まで ÷ 1.33 √(g h0)（論文 §3.2 の測った速さ）。終わり = 着水 + 2 s")
        row.update(bed_over_h0=[[round(x / H0, 4), round(d / H0, 4)] for x, d in r["bed"]], domain_over_h0=[x0 / H0, x1 / H0],
                   crest_over_h0=r["crest"] / H0, a0_m=round(a * H0, 2), pick_feddersen=pf, predicted=pred, ruler_predicted=rp, cost=cost)
        table.append(row)
    out = dict(
        note_ja="FLIP47 の文献の目標と、海底を変える 2D の組の案。h0 19 m、粒子 0.25 m。g47_targets.py が書いた（2026-10-12）。"
                "海底の bed は [x m, 水深 m]（静かな水面から下へ正、両端の外は端の水深で平ら）で g47_cfg.py の cfg の bed にそのまま入る",
        h0_m=H0, time_unit_s=round(TS, 4), sqrt_gh0_ms=round(CS, 3),
        e1a_paper=dict(
            source="Feddersen, Hanson, Mostert & Fincham 2024, J. Fluid Mech. 1000, A48（本文 §2.1・§3.3〜3.5・§4、図 1・5〜7）",
            setup=dict(Lx_over_h0=60, flat_to_over_h0=30, slope=0.0693, slope_length_over_h0=9.08, shelf_depth_over_h0=0.371,
                       shelf_length_over_h0="nearly 20", air_height_over_h0=10, end_walls="x = 0 と 60 h0 に鉛直の壁（u = 0、滑らない）",
                       bed_bc="滑らない（no-slip）", a0_over_h0=0.6, x0_over_h0=15, C_over_sqrtgh0=1.265,
                       eq_2_4="η0 = a0 sech²( (x − x0)/h0 · √(3(a0/h0)/(4(1 + a0/h0))) )",
                       eq_2_5="u = C η/(h0 + η)、w = −C (z + h0)/(h0 + η) · ∂η/∂x · (1 − η/(h0 + η)) = −C h0 (z + h0) ∂η/∂x/(h0 + η)²（符号は連続の式で決めた。抜き出した文字では読めない）",
                       Re_w=4.0e4, Bo=4000, rho_a_over_rho_w=0.001, mu_a_over_mu_w=0.018, lab_scale_h0_m=0.055,
                       amr_levels=14, dx_min_over_h0=3.7e-3, output_dt="0.05（t < 18）、0.01（t ≥ 18）"),
            adjustment_ja="GN の初めの波は NS の解ではなく、始めに細く少し高く（頂 約 0.68 h0）整い、後ろに小さな波を残す。Tanaka の解なら整いは小さい見込み（§2.1.2）",
            shoaling_ja="斜面の上で速さはほぼ一定（当てはめ 1.33、1.32）。頂は 0.77 h0 未満、Green の式よりゆっくり（§3.2）",
            no_wind=dict(t_impact=19.96, t_impact_s_at_h0_19=round(19.96 * TS, 2), xbp_over_h0=42.05, Hb_over_h0=0.64, AO_over_Hb2=0.352,
                         W_over_L=0.300, AJ_over_Hb2=0.219, thetaO_deg=29.0, jet_cross_width_over_h0=0.05, jet_cross_width_over_Hb=round(0.05 / 0.64, 3)),
            wind_range=dict(xbp_over_h0=[40.9, 42.2], Hb_over_h0=[0.627, 0.674], AO_over_Hb2=[0.301, 0.352], W_over_L=[0.296, 0.381],
                            AJ_over_Hb2=[0.132, 0.229], thetaO_deg=[29, 39],
                            onshore_Re2400=dict(t=19.13, xbp=40.85, Hb=0.674, AO=0.301, WL=0.381, AJ=0.132, theta=39),
                            offshore_Re_minus1800=dict(t=20.22, xbp=42.25, Hb=0.627, AO=0.344, AJ_range=[0.219, 0.229])),
            definitions=dict(
                touchdown_ja="噴流のいちばん低い所とその下の水面の縦の隙間 Δz が 0.015 h0（0.285 m）以下になる最初の時刻（a0 の 2.5%、最小格子の約 4 倍）。"
                             "出力の刻みで触れた後になった時は Δz = 0 を切る最も小さい x（§3.3）",
                xbp_ja="着水の時刻に Δz がいちばん小さい所の x（§3.3）",
                Hb_ja="着水の時刻の水面の最大の高さ（波の前に谷がないので静かな水面から測る）（§3.4）",
                AO_ja="巻きの中の空気を囲む境（図 6 の赤）の面積（§3.4）",
                AJ_ja="水面が x について多価になる上の水（噴流）の面積（図 6 の灰色）（§3.4）",
                WL_theta_ja="境を巻きの向き θO だけ回し、Longuet-Higgins 1982 の式 z/W = ±(3√3/4)(x/L)^(1/2)(x/L − 1) に当てて長さ L・幅 W（式 3.1）",
                jet_width_ja="噴流の横切りの幅 約 0.05 h0。最小格子で 13.5 個（§3.3）"),
            wind_dependence_ja="岸へ吹く風（Re* 正）で早く沖で崩れ（Δxbp +0.9）、Hb 上がり、AO・AJ 下がり（AJ 0.132 = −40%）、W/L と θO 上がる。"
                               "沖へ吹く風（Re* 負）ではほぼ動かない（AJ 0.219〜0.229、AO 0.344〜0.352）。観測（Surf Ranch）の 2〜3 倍の風が要った（§3.5・§5）",
            slope_dependence_ja="論文は勾配を変えていない（Surf Ranch の勾配に固定）。勾配が大きいほど巻きが大きいのは Grilli ら 1997・Mostert & Deike 2020・O'Dea ら 2021 による（§2.1.1）",
            differences_from_ours_ja=[
                "論文は 2 相（空気の密度比 0.001、粘りの比 0.018）。私たちは水だけ。巻きの中の空気の圧力（着水で p̃ 0.08 に上がる、図 12）がない。着水の前の形はほぼ同じで、着水の後は違う見込み",
                "論文は表面張力あり（Bo 4000）。著者は崩れの近くで表面張力の項が圧力の項と同じ桁になり、巻きの形に効きうると書く（§3.7・§4.2.1）。私たちは表面張力なし（実物の Bo は 3.6×10⁵ 以上）",
                "論文は粘りあり（Re_w 4×10⁴、h0 5.5 cm の実験室の大きさ）、海底は滑らない。私たちは粘りなし・滑る海底、h0 19 m",
                "論文は空気の流れ（風）を解く。風なしでも波に対する相対の風があり、波の後ろに渦が出る（§3.3）。私たちにはない",
                "格子：論文は最小 3.7×10⁻³ h0（噴流に 13.5 個）。私たちは粒子 0.25 m・格子 0.5 m = 0.026 h0（噴流の幅 0.95 m に約 2 個）",
                "Pick & Feddersen 2026 の FNPF（空気・表面張力・粘りなし。私たちと同じ重力だけ）の当てはめは、同じ s・H0/h0 で AJ 0.19・AO 0.38・WO/LO 0.41。重力だけの比べには FNPF の値の方が近い相手"]),
        e1a_targets_for_flip=dict(
            Hb_over_h0=dict(target=0.64, band_5pct=[0.608, 0.672]),
            xbp_over_h0=dict(target=42.05, paper_wind_envelope=[40.9, 42.2]),
            AJ_over_Hb2=dict(dns=0.219, fnpf_fit=0.204, fnpf_paper=0.19, band=[0.18, 0.23]),
            AO_over_Hb2=dict(dns=0.352, fnpf_fit=0.376, fnpf_paper=0.38, band=[0.33, 0.40]),
            W_over_L=dict(dns=0.300, fnpf_fit=0.429, fnpf_paper=0.41, band=[0.28, 0.45]),
            thetaO_deg=dict(dns=29.0, fnpf_fit=30.5, band=[27, 35]),
            jet_cross_width_over_h0=dict(dns=0.05, note_ja="格子 0.5 m では 2 個で測れない。粒子 0.125・0.0625 m の段で見る"),
            ruler_at_touchdown_from_paper_fig5b={k: round(lit["F24_fig5b_Re0_t19.96"][k], 3) for k in SCORE_KEYS + ["reach", "tip_z", "hood_low_z", "eta_c_over_h0"]},
            band_note_ja="帯は DNS と FNPF の値の両方を含めて ±5% ほど広げた案。走らせる前に凍結する"),
        pick_feddersen_2026=dict(
            source="Pick & Feddersen 2026, J. Fluid Mech. 1040, A8（本文 §2・§3・§4.1、図 5・6。CC BY 4.0）",
            setup_ja="2D の FNPF（surftank、MATLAB）。深い平ら（長さ W_f + 5 h0）→ 勾配 s の平らな斜面（足 x = 0）→ 水深 0.05 h0・長さ 10 h0 の浅い平ら。"
                     "初めの波は Dutykh & Clamond 2014 の Euler の厳密な孤立波（Tanaka と同じ）、頂は x0 = −W_f/2 − 4 h0。"
                     "s = 1/100・1/50・1/30・1/20・1/15・1/10、H0/h0 = 0.2〜0.6 の 30 本。節点の間隔 0.064 h0（1/50・1/100 は 0.102）",
            definitions_ja="崩れ始め t_b：水面が多価になる 1 つ前の出力（前の面が鉛直）。Hb：その時の最大の高さ、hb：その x の静かな水深。"
                           "着水 t_I：噴流が下の水面に触れる直前の出力。HI：その時の最大の高さ（HI/Hb は 1 より少し小さい）。AJ・AO・WO・LO・θO は Feddersen ら 2024 と同じ定義で、HI² で割る",
            fits=dict(eq3_3="S0 = 1.521 s/(H0/h0)^(1/2)", eq3_4="γb = 0.841 exp(6.421 S0)（Grilli ら 1997、r² 0.937）",
                      eq3_5="ψ0 = s/(H0/h0)^(1/4)", eq3_6="γb = 0.871 exp(11.874 ψ0)（r² 0.990）",
                      eq3_7="AO/HI² = 5.319 ψ0 − 0.043（0.04〜0.43、r² 0.990）", eq3_8="AJ/HI² = 37.072 ψ0² − 0.587 ψ0 + 0.020（0.012〜0.266、r² 0.997）",
                      eq3_9="WO/LO = 1.661 ψ0 + 0.298（0.30〜0.44）", eq3_10="θO = −5746.4 ψ0² + 225.2 ψ0 + 48.4（52.7°〜22.4°）",
                      eq3_11_12="急になる速さ = 2.476 ψ1² + 0.684 ψ1 + 0.047、ψ1 = s/(H0/h0)^(3/2)", valid="噴流が斜面に着く物だけ：S0 < 0.2、ψ0 < 0.1"),
            exclusions_ja="s 1/10 で H0/h0 0.2・0.3 は崩れ始めが浅い平らの上（外した）。s 1/10 の全部と s 1/15・H0/h0 0.2 は着水が浅い平らの上（巻きの量から外した）。"
                          "s 1/10 の巻きは静かな水面に底を押さえられた翼の形（図 5a の型）",
            correction_ja="前の調べ（FLIP45 diag physics_levers_ja.md）の「勾配 1/100 → 1/10 で AJ 0.012 → 0.266」は言い過ぎ。当てはめに入るのは ψ0 < 0.1 だけで、"
                          "H0/h0 0.6 の 1/10 は ψ0 0.114 で外。0.266 は 1/15 前後（H0/h0 0.3）の値【計算】",
            ruler_measured=dict((k, refs["lit_" + k]) for k in lit if isinstance(lit[k], dict) and k.startswith("PF_"))),
        other_literature=dict(
            grilli_1997="Grilli・Svendsen・Subramanya 1997（JWPCOE 123(3)、102–112）：1:100〜1:8 の斜面の孤立波（FNPF と実験）。S0 で こぼれ < 0.025 < 巻き < 0.30 < 寄せ < 0.37、"
                        "12° より急な斜面では崩れない（要旨）。γb = 0.841 exp(6.421 S0)（P&F の本文で確かめた）。閾値は二次の資料（arXiv 1911.06896）で、原典は読めていない（ifremer の写しは 403）",
            desmons_lubin_2022="Desmons & Lubin 2022（Water Waves 4）：2D の 2 相 DNS（Notus）。h1 0.31 m、孤立波 H1 0.155 m（H1/h1 0.5、1 次の解）、頂 x 2.6 m。"
                               "高い段 R1 は x 8.1 m、上の水深 d 0.047 m（d/h1 0.15）。R1 は本文で 0.248 m（R1/h1 0.8）と書くが d と合わず、Yasuda の 0.263 m（0.848）と合う（著者も表 3 で食い違いを書く）。"
                               "低い段 R2/h1 0.3〜0.6 を X1 手前に。段は鉛直。表 4：R2/h1 0.4 で X1/h1 1.0・2.0 ふつうの巻き、4.0・6.5 合わさった崩れ、10.0 2 回の崩れ。"
                               "合わさった崩れでは巻きの下の空気の面積がふつうの巻きより 6 割以上大きく、上の噴流の幅は着水まで細らないか少し太る（図 8e・9b）。格子 0.8 mm、1,325 万セル、320 コアで 1 本 60 時間",
            enright_2002="Enright 2002（Stanford の学位論文 §4.5.4）：孤立波 H 7 m・水深 10 m、勾配 1:7 で水面下 2 m の棚。重力だけで 3D の巻き・空気の管（リポジトリ BigWave_Recipes_ja.md C9）",
            face_angle_literature_ja="唇の下の前の面の角度を数で書いた文献は見つからなかった（野外の lidar は空洞の形と面積：O'Dea ら 2021、Duck の学位論文は前の面の傾きを崩れの判定に使うが唇の下ではない）。"
                                     "このため、論文の図を同じ物差しで測った値（lit_ruler.json）を証拠に使う"),
        print_bands=bands,
        score_rule_ja="点数 = 前の面の弦・前の足・唇の下の空気・唇の厚み・覆いの面積の 5 つについて、原画の 4 つの読み（drawn・cn・cn_swl_low・cn_swl_high）の幅の外へ出た分 ÷ 原画（cn）の値（1 つ 1 で頭打ち）、の和（0〜5）。"
                      "幅の中なら 0。唇の下の空気は原画が下限なので下だけ。各組で巻き始めから着水までの全部のコマを測り、(1) 点数がいちばん小さいコマ、(2) STUDY52 の決まり（覆いの高さが最大のコマ）、"
                      "(3) 着水のコマ、の 3 つを出す。組の順位は (1) で決め、同じなら (3)。走らせる前に凍結する",
        reference_scores=refs,
        scan=table,
        reserve_runs_ja=[
            "R7：勾配 1:30 で 0.1 h0 の平らへ（FLIP が FNPF の図 5d を再現するかの確かめ。物差しの予測は図 5d の値 = FLIP42 に近い）",
            "R8：S6 の低い段なし（X1 = 0、高い段だけ）。Desmons & Lubin の「6 割増し」を同じ FLIP で比べる相手",
            "R9：S2 の H0/h0 0.3（h0 38 m・a0 11.4 m、ψ0 0.135）。同じ高さの波で h0 を深くすると ψ0 が上がる（P&F の (H0/h0)^(−1/4)）。粒子は約 4 倍"])
    json.dump(out, open(B47 + "/targets.json", "w", encoding="utf8"), ensure_ascii=False, indent=1)
    # 画面へ短い表
    print("id | s | ψ0 | S0 | fit | AJ | AO | HI/h0 | x_b/h0 | particles M | minutes | ruler(chord,foot,gap,lip,area) score")
    for r in table:
        pf = r["pick_feddersen"]; pr = r["predicted"]; rp = r["ruler_predicted"]; c = r["cost"]
        print(r["id"], r["s"], pf.get("psi0"), pf.get("S0"), pf.get("fit_valid"), pf.get("AJ_over_HI2"), pf.get("AO_over_HI2"),
              pr.get("HI_over_h0"), pr.get("x_break_over_h0"), c["particles_M_dp0p25"], c["minutes"],
              [rp.get(k) for k in SCORE_KEYS], rp.get("score"))
    print("refs:")
    for k, m in refs.items():
        print(" ", k, m["score"], [round(m[kk], 3) for kk in SCORE_KEYS])


if __name__ == "__main__":
    main()
