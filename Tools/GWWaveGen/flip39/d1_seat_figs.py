# -*- coding: utf-8 -*-
"""FLIP39 D1-2 の図と seat_measures.json。入力は d1_seat.py の seat_raw.json・seat_skyline.npz、P3 の hf と網目。"""
import sys, os, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import *
from d1_plot import Sheet, Ax, PAL, font
from d1_seat import setup

D = json.load(open(os.path.join(OUT, "seat_raw.json"), encoding="utf-8"))
SK = np.load(os.path.join(OUT, "seat_skyline.npz"))
S = D["seat"]; FR = S["frames"]; SL = S["seat_line"]; CR = S["crest"]
C = setup(); eye = C["eye"]; SC = C["S"]
EYE_U = float(C["seat"]["seat"]["eye_world"][1])            # 作品での目の高さ（平らな海から）1.832 m
BOAT_L = float(C["seat"]["boat"]["tip_to_tip_length_m"])     # 11.33 m
t = np.array([f["t"] for f in FR])
amax = np.array([f["view"]["alpha_max"] for f in FR]); amax_r = np.array([f["view_ride"]["alpha_max"] for f in FR])
hmd = np.array([f["stats"]["hmd_fill"] for f in FR]); hmd_r = np.array([f["stats_ride"]["hmd_fill"] for f in FR])
hemi = np.array([f["stats"]["upper_hemi_frac"] for f in FR])
w10 = np.array([f["stats"]["width_above_deg"]["10"] for f in FR]); w30 = np.array([f["stats"]["width_above_deg"]["30"] for f in FR])
eta_seat = np.array([s["eta_at_seat"] for s in SL]); crest_x = np.array([s["crest_x"] for s in SL]); crest_y = np.array([s["crest_y"] for s in SL])
face = np.array([np.nan if s["face_deg"] is None else s["face_deg"] for s in SL]); tip = np.array([np.nan if s["lip_tip_x"] is None else s["lip_tip_x"] for s in SL])
Hc = np.array([c["Hc"] for c in CR]); L80 = np.array([c["L80"] for c in CR]); L90 = np.array([c["L90"] for c in CR])

# 目が水に入る時（固定の目）
wet = eta_seat > eye[1]
k_wet = int(np.argmax(wet)); t_wet = float(t[k_wet])
dry = t < t_wet
k_last = k_wet - 1

# 座席の列の、目の高さの水面の先（前の面の足）と、唇の先との差
p3 = load_p3()
iz = int(np.argmin(abs(p3["z"] - eye[2]))); xg = p3["x"]
toe = []
for fi in range(len(t)):
    row = p3["eta"][fi, iz].astype(float)
    kc = int(np.argmin(abs(xg - crest_x[fi])))
    j = kc
    while j + 1 < len(xg) and np.isfinite(row[j + 1]) and row[j + 1] > eye[1]:
        j += 1
    toe.append(xg[j])
toe = np.array(toe)
lip_lead = tip - toe                        # 正なら唇の先が前の面の足（目の高さ）より座席側に出ている
chord = np.degrees(np.arctan2(crest_y - eye[1], np.maximum(toe - crest_x, 1e-6)))   # 目の高さの足から頂までの前の面の弦

# 仰角の変化を「頂が高くなる分」と「近づく分」に分ける（座席の列の頂、固定の目）
def sm(a, n=13):
    k = np.ones(n) / n
    return np.convolve(np.pad(a, (n // 2, n // 2), mode="edge"), k, mode="valid")


# 座席の列の頂の位置と高さを 0.5 s（13 コマ）でならしてから速さを求める（頂の位置が升目で跳ぶため）
Dh = sm(eye[0] - crest_x); Hh = sm(crest_y - eye[1])
al = np.arctan2(Hh, Dh)
dt = np.gradient(t)
dH = np.gradient(Hh) / dt; dD = np.gradient(Dh) / dt
rate_grow_s = np.degrees(Dh * dH / (Dh ** 2 + Hh ** 2)); rate_appr_s = np.degrees(-Hh * dD / (Dh ** 2 + Hh ** 2))
tau = al / np.maximum(np.radians(rate_grow_s + rate_appr_s), 1e-6)

ev = D["seat"]  # noqa
P3ev = json.load(open(os.path.join(FLIP37, "P3", "H25_R18_mg", "sec", "z+000", "analysis.json"), encoding="utf-8"))["events"]
t_on = P3ev["breaking_onset_B085"]["t"]; t_ov = P3ev["face_past_vertical"]["t"]; t_tube = 8.88

# ------------------------------------------------------------------ 図 S1：時間の歩み
sh = Sheet(1800, 1300, "D1-2 図S1：座席（seat_v1 の目、P3 の置き方）から見た P3。固定の目は %.2f s に水の中に入る（前の面の足が先に届く）" % t_wet)
ax = Ax(sh, (90, 110, 860, 560), (3, 9.5), (0, 90), "時刻 t (s)", "仰角 (°)", "① 水の最も高く見える仰角（地平線から）。実線＝固定の目、点線＝船が上下だけ水面に乗る目",
        xticks=np.arange(3, 9.6, 0.5), yticks=range(0, 91, 10))
for y, lab in [(25, "目だけで見上げられる上限の目安 25°"), (55, "PS VR2 の視野 約110° の半分 55°"), (60, "視野の上の端 約60°")]:
    ax.hline(y, (170, 170, 170)); sh.text((ax.px(3.05, y)[0], ax.px(3.05, y)[1] - 16), lab, 11, (110, 110, 110))
ax.line(t[dry], amax[dry], PAL[1], 3, label="固定の目（目が水に入るまで）")
ax.line(t[t <= 9.15], amax_r[t <= 9.15], PAL[0], 2, dash=True, label="水面に乗る目（9.2 s で頂の上へ）")
for tv, lab in [(t_on, "砕け始め"), (t_ov, "垂直を越す"), (t_wet, "目が水に入る"), (t_tube, "管が閉じる")]:
    ax.vline(tv, (60, 60, 60), lab)
ax.legend("tl", 11)

ax2 = Ax(sh, (980, 110, 1750, 560), (3, 9.5), (0, 1.0), "時刻 t (s)", "割合", "② 前の窓（方位 ±55°・仰角 0〜55°）を水が占める割合と、地平線より上の半球の割合",
         xticks=np.arange(3, 9.6, 0.5), yticks=np.arange(0, 1.01, 0.1))
ax2.hline(0.5, (170, 170, 170))
ax2.line(t[dry], hmd[dry], PAL[1], 3, label="前の窓（固定の目）")
ax2.line(t[t <= 9.15], hmd_r[t <= 9.15], PAL[0], 2, dash=True, label="前の窓（水面に乗る目）")
ax2.line(t[dry], hemi[dry], PAL[2], 2, label="上の半球 2π sr のうち水")
ax2.line(t[dry], w10[dry] / 360, PAL[4], 2, label="仰角 10° 以上の方位の幅 ÷ 360°")
ax2.vline(t_wet, (60, 60, 60), "目が水に入る")
ax2.legend("tl", 11)

ax3 = Ax(sh, (90, 690, 860, 1140), (3, 9.5), (-10, 40), "時刻 t (s)", "°/s・s", "③ 座席の列の頂の仰角の速さ（°/s）を「頂が高くなる分」と「近づく分」に分けた値、と τ (s)",
         xticks=np.arange(3, 9.6, 0.5), yticks=range(-10, 41, 5))
ax3.hline(0, (120, 120, 120))
ax3.line(t[dry], rate_grow_s[dry], PAL[2], 3, label="頂が高くなる分（°/s）")
ax3.line(t[dry], rate_appr_s[dry], PAL[3], 3, label="近づく分（°/s）")
ax3.line(t[dry], np.clip(tau[dry], 0, 40), (0, 0, 0), 2, dash=True, label="τ＝仰角÷仰角の速さ（s、Lee 1976）")
ax3.line(t[dry], np.clip(t_wet - t[dry], 0, 40), (120, 120, 120), 1, label="実際に目が水に入るまでの時間（s）")
ax3.vline(5.2, (60, 60, 60), "ここから頂の高さが変わらない")
ax3.legend("tr", 11)

X0 = 980
sh.text((X0, 690), "④ 測った値（P3、座席 seat_v1、置き方 place_p3.json）", 16, bold=True)
k = k_last
lines = [
    "座席の目：作品の世界 (3.954, 1.832, −15.031) → 計算の座標 (%.1f, %.2f, %.1f)。水深 28 m の所、船の長さ %.2f m。" % (eye[0], eye[1], eye[2], BOAT_L),
    "  P3 の頂が巻いた所（z=0・−20 m、x 510 m）から岸の側へ 42 m。管が閉じた所（x 535〜540 m）の 12〜17 m 先。",
    "頂の高さ（窓の中の最大、作品の長さ＝計算×1.1）：%.1f m。目より上 %.1f m＝目の高さの %.1f 倍、船の長さの %.2f 倍。" % (
        SC * np.nanmax(Hc[dry]), SC * np.nanmax(Hc[dry]) - EYE_U, (SC * np.nanmax(Hc[dry]) - EYE_U) / EYE_U, SC * np.nanmax(Hc[dry]) / BOAT_L),
    "固定の目が水に入る：%.2f s（座席の列の水面が目の高さを越えた）。その時の頂は %.0f m 沖、唇の先は %.0f m 沖。" % (
        t_wet, eye[0] - crest_x[k_wet], eye[0] - tip[k_wet] if np.isfinite(tip[k_wet]) else float("nan")),
    "目が水に入る直前（%.2f s）：最大の仰角 %.1f°（水平の距離 %.1f m）、前の窓の水の割合 %.2f、" % (t[k], amax[k], FR[k]["view"]["dist_h"], hmd[k]),
    "  上の半球の水 %.2f、仰角 10° 以上の幅 %.0f°、30° 以上の幅 %.0f°。" % (hemi[k], w10[k], w30[k]),
    "目が水に入るまでの最大の仰角：%.1f°。水面に乗る目（上下だけ）では最大 %.1f°（%.2f s、目は水面＋1.83 m）。" % (np.max(amax[dry]), np.max(amax_r[t <= 9.1]), t[np.argmax(np.where(t <= 9.1, amax_r, -99))]),
    "前の面の弦（目の高さの足→頂）：%.0f°（%.2f s）。いちばん急な所の傾き %.0f°。" % (chord[k], t[k], face[k]),
    "唇の先と前の面の足（目の高さ）の差：%.1f m（負＝足が先に座席へ来る）。" % lip_lead[k],
    "峰に沿う頂の長さ（窓 140 m の中）：0.8 倍以上 %.0f m、0.9 倍以上 %.0f m（頂 %.1f m に対して %.1f 倍）。" % (L80[k], L90[k], Hc[k], L80[k] / Hc[k]),
    "仰角が 10° を越えてから目が水に入るまで：%.1f s（%.2f→%.2f s）。" % (t_wet - t[np.argmax(amax > 10)], t[np.argmax(amax > 10)], t_wet),
    "5.2 s より後、頂の高さはほとんど変わらない（%.1f〜%.1f m）。仰角が増えるのは、ほとんど近づくため。" % (np.min(Hc[(t > 5.2) & dry]), np.max(Hc[(t > 5.2) & dry])),
    "3.0〜5.2 s の頂の伸び（12.7→20.8 m）は hot start の落ち込みからの戻り（D1-1）で、海の仕組みではない。",
]
for i, s in enumerate(lines):
    sh.text((X0, 725 + 26 * i), s, 12)
sh.save(os.path.join(OUT, "sheet_s1_seat_timeline.png"))

# ------------------------------------------------------------------ 図 S2：座席から見た空の線（パノラマ）
sh = Sheet(1800, 980, "D1-2 図S2：座席から見た水の上の縁（方位 −180〜180°、0°＝沖＝波の来る向き）。灰の枠＝前の窓 ±55°×55°")
az = SK["az"]; sky = SK["sky"]; tt = SK["t"]
ax = Ax(sh, (90, 110, 1750, 560), (-120, 120), (0, 70), "方位 (°)（+ は +z の側）", "仰角 (°)", "① 固定の目。点線＝同じ高さ・同じ距離のまっすぐで無限に長い峰（参考）",
        xticks=range(-120, 121, 20), yticks=range(0, 71, 10))
sel = [5.0, 6.5, 7.29, 7.71, float(t[k_last])]
for i, tv in enumerate(sel):
    fi = int(np.argmin(abs(tt - tv)))
    ax.line(az, np.clip(sky[fi], 0, 90), PAL[i], 2, label="t=%.2f s" % tt[fi])
    Dn = eye[0] - crest_x[fi]; H = crest_y[fi] - eye[1]
    ref = np.degrees(np.arctan(H * np.cos(np.radians(az)) / Dn)); ref[np.abs(az) >= 89] = np.nan
    ax.line(az, ref, PAL[i], 1, dash=True)
for xv in (-55, 55):
    ax.vline(xv, (150, 150, 150))
ax.hline(55, (150, 150, 150))
ax.legend("tr", 12)
sh.text((95, 600), "読み方：実線が点線とほぼ重なるほど、座席から見て、峰は端の見えない一様な壁（長い峰）に見える。実線が点線より狭い山なら、低い肩が見える。", 13)
sh.text((95, 625), "P3 では、どの時刻も前の窓 ±55° の中に頂の端（頂の 0.8 倍まで下がる所）が入らない：0.8 倍以上の方位の幅 %s°。" % (
    "・".join("%.0f" % FR[int(np.argmin(abs(t - tv)))]["stats"]["w80_deg"] for tv in sel)), 13)
sh.text((95, 650), "峰に沿う頂の 0.8 倍以上の長さは %.0f〜%.0f m（頂 %.1f m の %.1f〜%.1f 倍）で、窓 ±55° の中に両端が入るには、頂から %.0f m 以内の距離では足りない。" % (
    np.min(L80[(t > 6.5) & dry]), np.max(L80[(t > 6.5) & dry]), np.max(Hc[dry]), np.min(L80[(t > 6.5) & dry]) / np.max(Hc[dry]), np.max(L80[(t > 6.5) & dry]) / np.max(Hc[dry]),
    np.min(L80[(t > 6.5) & dry]) / 2 / np.tan(np.radians(55))), 13)
# ② 座席の列の断面（網目）
ax2 = Ax(sh, (90, 730, 1750, 940), (470, 580), (-6, 24), "x (m)（計算の座標、+ が岸。座席の列 z=%.1f m）" % eye[2], "y (m)", "② 座席の列の水面の断面（P3 の網目の |z−座席|<0.5 m の点）と目の位置（黒の点）",
          xticks=range(470, 581, 10), yticks=range(-6, 25, 3))
for i, tv in enumerate([7.29, 7.71, float(t[k_last]), 8.21, 8.71]):
    f = int(round(tv * 24)) + 1
    mp = os.path.join(FLIP37, "P3", "H25_R18_mg", "mesh", "mesh_%04d.npz" % f)
    if os.path.isfile(mp):
        M = np.load(mp)["P"]
        mm = (np.abs(M[:, 2] - eye[2]) < 0.5) & (M[:, 0] > 470) & (M[:, 0] < 580)
        ax2.points(M[mm, 0], M[mm, 1], PAL[i], 1, label="t=%.2f s" % ((f - 1) / 24))
ax2.points([eye[0]], [eye[1]], (0, 0, 0), 5, label="目（固定）")
ax2.legend("tr", 11)
sh.save(os.path.join(OUT, "sheet_s2_seat_view.png"))

# ------------------------------------------------------------------ seat_measures.json
pos = D["positions"]
M = dict(
    source=dict(p3_hf="Unity/Build/FLIP37/P3/H25_R18_mg/hf_A..L.npz", r18_hf="Unity/Build/FLIP37/P2/R18_X30L120LG_H39/hf.npz",
                place="Unity/Build/FLIP37/P3/H25_R18_mg/place_p3.json（M_sim_to_unity、倍率 1.1）", seat="Tools/GWContext/seat_v1.json（seat.eye_world）",
                note_ja="角度は相似変換で変わらないので計算の座標で求めた。長さは作品の長さ（計算×1.1）。R18 の箱の外（|z|>120 m）は平らな海とした。"),
    eye_sim=eye.tolist(), eye_height_world_m=EYE_U, boat_length_m=BOAT_L, scale=SC,
    t_eye_wet_s=t_wet, t_last_dry_s=float(t[k_last]),
    p3=dict(
        crest_height_world_m=float(SC * np.nanmax(Hc[dry])), crest_above_eye_world_m=float(SC * np.nanmax(Hc[dry]) - EYE_U),
        crest_above_eye_in_eye_heights=float((SC * np.nanmax(Hc[dry]) - EYE_U) / EYE_U), crest_over_boat_length=float(SC * np.nanmax(Hc[dry]) / BOAT_L),
        alpha_max_fixed_before_wet_deg=float(np.max(amax[dry])), alpha_max_riding_deg=float(np.max(amax_r[t <= 9.1])),
        hmd_fill_max_before_wet=float(np.max(hmd[dry])), upper_hemi_max_before_wet=float(np.max(hemi[dry])),
        width_alpha10_deg_last_dry=float(w10[k_last]), width_alpha30_deg_last_dry=float(w30[k_last]),
        face_chord_deg_last_dry=float(chord[k_last]), face_max_slope_deg_last_dry=float(face[k_last]),
        lip_lead_m_last_dry=float(lip_lead[k_last]), L80_m_last_dry=float(L80[k_last]), L90_m_last_dry=float(L90[k_last]), Hc_sim_m=float(np.nanmax(Hc[dry])),
        L80_over_Hc=float(L80[k_last] / Hc[k_last]),
        t_alpha10_s=float(t[np.argmax(amax > 10)]), watch_time_alpha10_to_wet_s=float(t_wet - t[np.argmax(amax > 10)]),
        crest_height_const_after_s=5.2, crest_height_range_after_5_2_s=[float(np.min(Hc[(t > 5.2) & dry])), float(np.max(Hc[(t > 5.2) & dry]))]),
    series=dict(t=t, alpha_fixed=amax, alpha_riding=amax_r, hmd_fill=hmd, hmd_fill_riding=hmd_r, upper_hemi=hemi, width10=w10, width30=w30,
                crest_x=crest_x, crest_y=crest_y, toe_x=toe, lip_tip_x=tip, lip_lead=lip_lead, face_chord=chord, face_max_slope=face,
                eta_at_seat=eta_seat, Hc=Hc, L80=L80, L90=L90, rate_grow_deg_s=rate_grow_s, rate_approach_deg_s=rate_appr_s, tau_s=tau),
    seat_x_scan=[{k: v for k, v in p.items() if k != "series"} for p in pos],
)
jdump(M, os.path.join(OUT, "seat_measures_raw.json"))
print("t_wet", t_wet, "last dry", t[k_last], "amax", amax[k_last], "chord", chord[k_last], "lip_lead", lip_lead[k_last], "toe", toe[k_last], "tip", tip[k_last])
print("riding max", np.max(amax_r[t <= 9.1]))
for tv in (6.0, 7.0, 7.5, 7.75, 7.96):
    i = int(np.argmin(abs(t - tv))); print(tv, "grow %.1f appr %.1f tau %.2f chord %.0f lead %.1f toe %.0f tip %.0f" % (rate_grow_s[i], rate_appr_s[i], tau[i], chord[i], lip_lead[i], toe[i], tip[i]))
