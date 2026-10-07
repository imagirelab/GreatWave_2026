# -*- coding: utf-8 -*-
"""FLIP39 D1 のまとめの JSON（mech.json・seat_measures.json）。数値は mech_raw.json・seat_measures_raw.json から読む。"""
import sys, os, json, numpy as np
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
from d1_common import OUT, jdump, kdisp, kshoal

M = json.load(open(os.path.join(OUT, "mech_raw.json"), encoding="utf-8"))
S = json.load(open(os.path.join(OUT, "seat_measures_raw.json"), encoding="utf-8"))
P2, P1, P3, RAYS = M["P2"], M["P1"], M["P3"], M["rays"]
r18 = P2["R18_X30L120LG_H39"]; tr = np.array(r18["track"], float)
k_on = int(np.argmin(abs(tr[:, 0] - r18["onset"]["t_any"])))
on_crest, on_trough = tr[k_on, 1], tr[k_on, 3]
ray = lambda nm, th, x: RAYS[nm][th]["Kr_z0"][RAYS[nm][th]["x"].index(x)]

mech = dict(
    title_ja="D1-1 今の計算で、波を高くする仕組みがどれだけ働いたか（FLIP37 の既存の計算を測った値）",
    measured_vs_estimated_ja="『測った』＝FLIP37 の hf.npz・eta.npz・analysis.json から読んだ値。『推定』＝線形の理論（平らな海の分散、浅水係数、波線）で出した見込み。",
    answer_ja=[
        "二つの波の列（±30°）は、計算の中で一点へ集まっていない。二つの列は t=0 の初めの水面に、hot start の範囲（x 120〜480 m）の全体で、すでに重ねて置かれている。"
        "z=0 の頂÷峰に沿う頂の平均は t=0 で 1.42、砕け始めで 1.31、頂の前後の η² のうち |z|<30 m の割合は 0.41 → 0.33 と、どちらも時間とともに下がった（測った）。",
        "R18 の砕け始め（7.08 s）の z=0 の頂 20.6 m は、t=0 に置いた頂 19.5 m の 1.06 倍。頂の高さは入力でほぼ決まっている（測った）。",
        "そのうち、t=0 の頂 19.5 m の 70 % は z に一様な成分（向き 0°）、30 % が ±30° の模様の分。模様の分も t=0 に置かれたもので、計算の中で増えていない（測った）。",
        "計算の中の仕組みの効果（z=0 の頂）：浅水変形（線形）は ±0 %（水深 60→39.5 m、推定）、レンズの屈折は +3〜4 %（R12 と R15 の比べ、測った）、低い棚は −1 %（R16 と R12、測った）、"
        "波の群の分散による集中はない（初めの波は一つの頂で、線形の推定では 7 s で −10 %）、交わる列の集中はない（上の 1 行目）。",
        "頂は t≈2.4〜3.0 s に入力の 58〜74 % まで下がり、斜面の上で戻る。水槽の位置エネルギーも同じ時刻に 0.46〜0.55 倍まで下がって戻るので、これは初めの水面と流速の組（hot start）の揺れで、海の仕組みではない（測った。原因は未確認）。",
        "砕け始めの頂が入力を少し越えた分は、頂と谷の上下の形の偏り（頂÷波高 0.59 → 0.87。波高は 33.0 → 23.7 m に下がった）で、エネルギーが増えたのではない（測った）。",
    ],
    budget_R18_z0=dict(
        crest_onset_m=on_crest, t_onset_s=r18["onset"]["t_any"], x_onset_m=r18["onset"]["x"], depth_onset_m=r18["onset"]["depth_m"],
        input_crest_t0_m=r18["input"]["crest_z0_m"], input_uniform_part_m=r18["input"]["crest_z0_m"] * r18["input"]["n0_share_at_z0"],
        input_crossing_part_m=r18["input"]["crest_z0_m"] * (1 - r18["input"]["n0_share_at_z0"]),
        dip_m=r18["dip"]["crest_m"], dip_t_s=r18["dip"]["t"],
        H_t0_m=r18["input"]["H_z0_m"], H_onset_m=on_crest - on_trough, crest_over_H_t0=r18["input"]["crest_z0_m"] / r18["input"]["H_z0_m"], crest_over_H_onset=on_crest / (on_crest - on_trough),
        mechanisms=[
            dict(name_ja="入力（hot start の頂の振幅）", how_ja="t=0 の z=0 の頂", effect_ja="19.5 m（砕け始めの頂の 95 %）", kind="測った"),
            dict(name_ja="浅水変形（線形）", how_ja="Ks(39.5 m)/Ks(60 m)、周期 14 s", effect_ja="×%.3f" % r18["onset"]["Ks_lin"], kind="推定"),
            dict(name_ja="浅水変形（測った波高）", how_ja="z=0 の頂−前の谷", effect_ja="33.0 m（t=0）→ 19.2 m（足元 x=400 m）→ 23.7 m（砕け始め）。足元→砕け始めの 1.24 倍は線形の Ks 1.00 を越え、hot start の揺れの戻りを含む", kind="測った"),
            dict(name_ja="波の群の分散による集中", how_ja="同じ初めの波を線形・平らな海で進めた z=0 の頂", effect_ja="R18：0〜4 s で 100〜102 %、7 s で 90 %。一列（2 次の項を自由な波として進めるので低めに出る）：最小 84〜86 %。集まる点は t=0 の x=330 m", kind="推定"),
            dict(name_ja="向きの違う波の重なり（±30°）", how_ja="頂÷平均・|z|<30 m の η² の割合の時間変化", effect_ja="t=0 に z=0 の頂の 30 %（5.8 m）として置かれ、計算の中では増えない（1.42→1.31、0.41→0.33）", kind="測った"),
            dict(name_ja="海底の屈折（レンズ）", how_ja="R12（レンズ）と R15（レンズなし）の z=0 の頂", effect_ja="x=500 m で +3 %、砕け始めで +4 %。波線の理論（0°）は x 480〜500 m で ×" + "%.2f〜%.2f" % (ray("lens_only", "0", 480.0), ray("lens_only", "0", 500.0)) + " と見込むが出ていない", kind="測った・推定"),
            dict(name_ja="低い棚 2 つ", how_ja="R16 と R12（同じ入力 37 m）", effect_ja="砕け始めの頂 19.72 m と 20.00 m（−1 %）", kind="測った"),
            dict(name_ja="上下の形の偏り（非線形）", how_ja="頂÷波高", effect_ja="0.59 → 0.87。波高が下がっても頂の高さは保たれた", kind="測った"),
        ]),
    why_long_crest_ja=[
        "一列（R05・R08）：初めの水面に z の変化がない。レンズを付けても砕け始めの頂÷z=±100 m の頂は 1.01〜1.02（測った）。峰は箱の幅全部（半分の高さの幅 232 m、R08）。",
        "±30°：初めの模様 cos(k0·sin30°·z) の z の周期は 波長/sin30° = 2×271 = 542 m。頂の 0.8 倍以上の長さは 2·acos(0.8)/(k0·sin30°) = 111 m（理論）、測った値は t=0 で 110 m、R18 の砕け始め 104 m、P3 は 101〜116 m。",
        "±40°（R17）では理論 86 m、測った値 t=0 で 86 m。峰を短くするには角度を大きくするしかなく、同じ入力では頂の水の速さが下がって砕けなかった（P2 の記録）。",
        "周期 14 s の波（沖で波長 271 m、岩棚の上で 200〜240 m）を二つの向きだけで重ねると、峰に沿う高さは波長/(2 sinθ) より短い長さで変われない。向きが二つだけで、向きの広がり（多くの向き）がない。",
        "滑る壁（z=±120 m）が鏡になり、模様が z 方向にくり返されるので、z に一様な成分が z=0 の頂の 70 % を占める。",
        "長くゆるい背：波長÷頂の高さ ≈ 11（岩棚の上の波長 225 m、頂 20 m）。頂から 0.75 Hc まで下がる横の長さ 1.2 Hc（P3 の記録）は、周期 14 s の長い波の形による。",
    ],
    runs={k: dict(label=v["label"], input=v["input"], dip=v["dip"], toe=v["toe"], at_x500=v["at_x500"], onset={kk: vv for kk, vv in v["onset"].items() if kk != "at_onset"},
                  prof={kk: {a: b for a, b in vv.items() if a != "line"} for kk, vv in v["prof"].items()}) for k, v in P2.items()},
    p1={k: dict(label=v["label"], input=v["input"], dip=v["dip"], toe=v["toe"], onset=v["onset"]) for k, v in P1.items()},
    p3=dict(onset=P3["onset"], overturn=P3["overturn"], crest_max_pre_overturn=P3["crest_max_pre_overturn"],
            prof={k: {a: b for a, b in v.items() if a != "line"} for k, v in P3["prof"].items()},
            note_ja="P3 は R18 の t=2.96 s（頂が下がった所）の状態から始まるので、入力の決まり方は R18 と同じ。"),
    rays_Kr_z0={nm: {th: dict(zip(["%.0f" % x for x in v["x"]], v["Kr_z0"])) for th, v in d.items()} for nm, d in RAYS.items()},
    input_spectrum=dict(kx_peak_wavelength_m=315, half_power_dk_over_k=0.71,
                        note_ja="t=0 の z=0 の η(x) の空間スペクトル。1.3 波長の窓をかけた周期波なので幅は広いが、成分はすべて t=0 に x=330 m で山がそろう（集まる点が始めにある）。"),
    files=["sheet_m1_crest_history.png", "sheet_m2_xt.png", "sheet_m3_crossing.png", "sheet_m4_refraction.png", "mech_raw.json"],
)
jdump(mech, os.path.join(OUT, "mech.json"))

p = S["p3"]; ser = S["series"]
t = np.array(ser["t"]); amax = np.array(ser["alpha_fixed"], float); hmd = np.array(ser["hmd_fill"], float)
dry = t < S["t_eye_wet_s"]
t25 = float(t[np.argmax(amax > 25)]); t_h05 = float(t[np.argmax(hmd > 0.5)])
He = p["crest_above_eye_world_m"]
dist_for = {str(a): He / np.tan(np.radians(a)) for a in (25, 45, 55, 60)}
seat = dict(
    title_ja="D1-2 座席の体験の物差し（理由つき）と、今の P3 の値",
    eye_ja="座席 seat_v1 の目（作品の世界 (3.954, 1.832, −15.031)、甲板の 1.2 m 上、平らな海から 1.83 m）。P3 の置き方 place_p3.json の逆で計算の座標 (552.2, 1.67, −9.5) へ写した。"
           "この置き方は原画カメラに合わせて決めたもので、体験から決めた置き方ではない。座席の x を 480〜630 m に動かした場合も測った（seat_x_scan）。",
    eye_models_ja="固定の目＝船が動かない（目は平らな海から 1.83 m）。水面に乗る目＝船が上下だけ水面に従う（目＝座席の真下の水面＋1.83 m）。本当の船の動き（傾き・押し流し）は入れていない。",
    t_eye_wet_s=S["t_eye_wet_s"],
    measures=[
        dict(key="alpha", name_ja="頂の仰角（地平線から）",
             define_ja="目から、水が最も高く見える点への仰角。地平線（海の水平線、目の高さ）からの角度。",
             why_ja="見上げる角度は、目だけで見えるか、頭を上げるか、視野の上へはみ出すかを決める。波が頭の上を覆う感じは、水が視野の上の端を越えて続くこと（空が見えない）に当たる。",
             thresholds=[dict(deg=25, why_ja="目だけで上を見る楽な範囲の上限の目安（VR の快適域の資料。人により 20〜30°）。これより上は頭を上げて見る"),
                         dict(deg=55, why_ja="PS VR2 の視野 約110°（Sony 公表）の半分。頭を水平にした時の画の上の端の目安（縦の視野は公表がないので推定）"),
                         dict(deg=60, why_ja="人の視野の上の端（固視点から約 60°、眉で切られる）。これを越えると頭を水平にしたままでは頂が見えず、視野の上の端まで水になる"),
                         dict(deg=90, why_ja="真上。水が頭の上にある")],
             geometry_ja="頂が目より ΔH 上にある時、仰角 α に必要な水平の距離は ΔH/tan α。P3（ΔH=%.1f m）では 25°：%.0f m、45°：%.0f m、55°：%.0f m、60°：%.0f m。" % (
                 He, dist_for["25"], dist_for["45"], dist_for["55"], dist_for["60"]),
             p3=dict(fixed_max_before_wet_deg=p["alpha_max_fixed_before_wet_deg"], riding_max_deg=p["alpha_max_riding_deg"], t_cross_25_s=t25),
             verdict_ja="固定の目では、仰角は 40° で止まる（その 0.04 s 後に目が水に入る）。55〜60° に届かない。水面に乗る目では 9.04 s に 68°（その後、船は頂の上に出る）。"),
        dict(key="ratio", name_ja="頂の高さ（目の高さ・船の長さとの比）",
             define_ja="頂の高さ（作品の長さ）。目より上の高さ÷目の高さ、頂÷船の長さ。",
             why_ja="海では地平線が目の高さで波を切る。地平線より上の部分÷地平線より下の部分＝(頂−目)/目で、距離を知らなくても『自分の目の高さの何倍か』が見える（horizon ratio、Sedgwick）。船の長さは画の中の身近な物差しで、砕ける波の高さが船の長さの約 0.55 倍でほとんどのヨットが転覆する（Southampton 大学の模型の試験）。",
             thresholds=[dict(value=0.55, unit="頂÷船の長さ", why_ja="砕ける波でほとんどのヨットが転覆する高さ（模型の試験）。危険の物差し")],
             p3=dict(crest_world_m=p["crest_height_world_m"], above_eye_m=He, eye_heights=p["crest_above_eye_in_eye_heights"], boat_lengths=p["crest_over_boat_length"]),
             verdict_ja="頂 23.0 m、目より上 21.2 m＝目の高さの 11.6 倍、船の長さの 2.03 倍（転覆の目安 0.55 倍の 3.7 倍）。この物差しでは高さは不足していない。不足は見え方（下の仰角・峰の長さ・前の面）。"),
        dict(key="fill", name_ja="視野を占める割合",
             define_ja="前の窓（方位 ±55°、仰角 0〜55°。PS VR2 の視野 約110° を水平の正面に置いた時の上半分。方位・仰角の座標で数える）を水が占める割合。地平線より上の半球（2π sr）のうち水の立体角。仰角 10°・30° 以上の方位の幅。",
             why_ja="0.5 を越えると、前の窓の上半分で空より水が多い（波に囲まれる）。1.0 で窓の上半分がすべて水になる。",
             thresholds=[dict(value=0.5, why_ja="空より水が多い"), dict(value=1.0, why_ja="窓の上半分がすべて水")],
             p3=dict(hmd_fill_max_before_wet=p["hmd_fill_max_before_wet"], t_cross_05_s=t_h05, upper_hemi_max_before_wet=p["upper_hemi_max_before_wet"],
                     width_alpha10_deg=p["width_alpha10_deg_last_dry"], width_alpha30_deg=p["width_alpha30_deg_last_dry"]),
             verdict_ja="0.5 を越えるのは %.2f s、目が水に入る %.2f s 前。最大 %.2f。仰角 10° 以上の幅は %.0f°（窓の幅 110° より広い）。" % (t_h05, S["t_eye_wet_s"] - t_h05, p["hmd_fill_max_before_wet"], p["width_alpha10_deg_last_dry"])),
        dict(key="peak", name_ja="峰の短さ（山らしさ）",
             define_ja="峰に沿う頂の 0.8 倍以上の長さ L80 と頂の高さ Hc の比。見え方では、頂の 0.8 倍以上の方位の幅 W80。",
             why_ja="頂の両側に低い肩が見えれば、頂の高さを周りと比べて見られる。肩が窓の外にあると、端の見えない壁（長い斜面）に見える。",
             geometry_ja="頂から距離 D で前の窓 ±55° の中に両端が入るには L80 ≤ 2D·tan55° ≈ 2.86 D。仰角 45°（D=21 m）なら L80 ≤ 61 m、60°（D=12 m）なら L80 ≤ 35 m。",
             p3=dict(L80_m=p["L80_m_last_dry"], L90_m=p["L90_m_last_dry"], L80_over_Hc=p["L80_over_Hc"]),
             verdict_ja="L80 116 m（頂の 5.6 倍）。目が水に入る直前の距離 19 m では、窓に両端が入る長さ（約 54 m）の 2 倍。座席から見ると端のない壁。"),
        dict(key="face", name_ja="前の面の急さと、頭上の張り出し",
             define_ja="座席の列（z=座席）の断面で、目の高さの水面の足から頂までの弦の角度、いちばん急な所の傾き、唇の先と足の差（lip lead＝唇の先 x − 足 x）、目の真上の水。",
             why_ja="固定の目では、水が目の高さに届く瞬間の頂の仰角は、この弦の角とほぼ同じになる（唇が足より前に出ていなければ）。だから『視野の上を越える前に水に入るか』は弦で決まる。"
                    "頭上に崩れてくる（唇を下から見上げ、唇が目の上を越える）には、目がまだ水の上にある間に、唇の先が足より座席側へ出ている（lip lead > 0）ことが要る。",
             thresholds=[dict(deg=55, why_ja="弦がこれ以上なら、水に入る前に頂が PS VR2 の画の上の端（推定）に届く"), dict(value_m=0, why_ja="lip lead > 0 で唇が先に頭上へ来る")],
             p3=dict(chord_deg=p["face_chord_deg_last_dry"], max_slope_deg=p["face_max_slope_deg_last_dry"], lip_lead_m=p["lip_lead_m_last_dry"], overhead_water_while_dry=False),
             verdict_ja="弦 36°、上の方のいちばん急な所 82°。前の面の下が長くゆるい坂で、その足が唇より 17.5 m 先に座席へ届く。目が水の上にある間に頭上に水が来ることはない。"),
        dict(key="rise", name_ja="立ち上がる速さ",
             define_ja="座席の列の頂の仰角の速さを『頂が高くなる分』と『近づく分』に分けた値。τ＝仰角÷仰角の速さ（Lee 1976 の、近づく物に当たるまでの時間の手がかり）。仰角 10° を越えてから目が水に入るまでの時間。",
             why_ja="『立ち上がる』は頂が上へ動くこと、『迫る』は全体が近づくこと。どちらも仰角を増やす。高くなる分が全体の半分を越えると、見える上への動きの主な理由が『育つ』になる（定義の上の境目）。",
             thresholds=[dict(share=0.5, why_ja="仰角の増え方の半分以上が頂の育ち")],
             p3=dict(grow_deg_s_after6=[-0.9, 0.7], approach_deg_s_after6=[4.3, 18.5], tau_s_7_to_8=[1.8, 2.7], watch_alpha10_to_wet_s=p["watch_time_alpha10_to_wet_s"],
                     alpha25_to_wet_s=S["t_eye_wet_s"] - t25),
             verdict_ja="6 s より後、頂が高くなる分は −0.9〜+0.7°/s、近づく分は 4〜18°/s。仰角の増え方の 9 割以上が近づくため。3.0〜5.2 s の頂の伸びは hot start の揺れの戻りで、海の仕組みではない。"),
    ],
    seat_x_scan=S["seat_x_scan"],
    files=["sheet_s1_seat_timeline.png", "sheet_s2_seat_view.png", "seat_measures_raw.json", "seat_raw.json", "seat_skyline.npz"],
    sources=[dict(what_ja="人の視野の上の端 約 60°", url="https://www.ncbi.nlm.nih.gov/books/NBK220/"),
             dict(what_ja="PS VR2 の視野 約 110°", url="https://www.playstation.com/en-mt/ps-vr2/ps-vr2-tech-specs/"),
             dict(what_ja="目だけで上を見る楽な範囲 約 25°（VR の快適域）", url="https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10712900"),
             dict(what_ja="horizon ratio（目の高さで大きさを測る）", url="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10654384/"),
             dict(what_ja="τ（Lee 1976, Perception 5:437-459）", url="https://swov.nl/en/publicatie/tau-potential-control-variable-visually-guided-braking"),
             dict(what_ja="船の長さの 0.55 倍の砕ける波で転覆", url="https://goodoldboat.com/capsize-how-it-happens")],
)
jdump(seat, os.path.join(OUT, "seat_measures.json"))
print("t25", t25, "t_h05", t_h05, dist_for)
