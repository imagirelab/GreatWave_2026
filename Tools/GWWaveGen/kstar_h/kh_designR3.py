# -*- coding: utf-8 -*-
"""設計28修正01 K*′（最後の一コマ）を Houdini で作るための断面の生成器（候補 H1A の精修 R3 = 精修の第 3 回）。numpy だけ（hython と py -3.10）。

R3 で R2（kh_designR2.py）から変えた所（R2 の評審の must-fix に対して、手続きの母数と節点で直す。中を削って原画に合わせない。
原画視点の輪郭を作る列（頂 76〜104、唇の上面 103〜191、唇の頭と唇の下 161〜343）は背の節点では動かさない）：
  * back_out（新しい母数、背を外へ）：背（列 18〜約 85、行の高さの比 f < 0.9）を水平に後ろ（− a、外）へ出す量 [m]。奥の行の薄い殻と
    肩の行を外へ満たす（中を削らない。外へ足すだけ）。
  * back_env（新しい母数、背の平面の輪郭のくびれを埋める）：各高さ（0.5〜8 m）の背の平面の位置 a(c) を、±BE_L m の弦から前へ BE_TOL m より
    出ない所まで外へ埋める（上から見たくびれ、評審の notch）。行ごとの量を c の方向にならし、高さに比例するずらし（断面の凸凹の数を変えない）で
    外へだけ動かす。頂の近く（0.88 H より上）は動かない。
  * back_depth（新しい母数、背の奥行きの下限 /H）：半分の高さで頂から背までの水平の距離が back_depth × H より浅い行を外へ埋める（肩の行 c ≤ −8.4。
    行ごとの奥行きの差＝上から・後ろから見たレモン形を減らす）。back_tail（新しい母数）：c ≥ 9 の奥の端の背を c 9 の行の背の形の相似な縮小へ寄せる
    （奥の端の背の膨らみ R6）。どちらも外へ足すだけで、頂の近くと唇・中の面は動かさない。
  * crest_lift（新しい母数、頂の持ち上げ）：奥の行（c ≥ 2.5）の頂のまわり（列 20〜186、列 60〜96 で全部）を鉛直に上げる（最大 1.4 m、c +7）。
    唇の頭と唇先（原画の輪郭 72 を描く列 186〜）と足は動かさない。奥の頂が主断面より早く低くなり、前から上から見て（u11・v9）頂と唇の上面が
    レモン形に見えたのを、頂の線を奥まで続く巻きの稜にする。
  * lip_under（新しい母数、唇の頭の下面の厚み）：試したが値は 0（3 m おきの唇の鍵と合わせても原画の輪郭 72 に届かなかった。_work/R3 の記録）。
  * 奥の端の閉じ方（CONE）：奥の端（c > 0）の 1.5 m より低い行は、巻きの形を a・y とも同じ比で縮め（相似）、最後の行も極小の同じ形に
    する（平らな帯へ移さない）。R2 は 0.9 m より低い行を単調な帯へ移したので、c +14.8 の行で唇先の頭と平らな行が交差・裏返った。
  * 唇の頭の移動（lip_shift / lip_drop）：鍵を 3 m おきにすると原画の輪郭 72 の大きな輪郭（σ 12 px）に残る爪の房の間の湾に合わず関門を割る
    （p95 9.7 px）ので、1 m おきの鍵のまま、関門を守る範囲で区間ごとに c 方向にならした（kh_R3_lipsmooth.py）。低い奥の行ではなめらかに 0。
  * b 区域の房（ledge_lobe_depth、新しい母数）：房の凹凸を原画カメラの視線の向き（断面の面の中の成分）へ付ける。原画視点の輪郭はほとんど
    動かさず、ほかの視点（u13・v3）で 3 つの大きな房に見せる。
以下は R2 の説明（そのまま）。

設計28修正01 K*′（最後の一コマ）を Houdini で作るための断面の生成器（候補 H1A の精修 R2 = 精修の第 2 回）。numpy だけ（hython と py -3.10）。

R2 で R1（kh_designR1.py）から変えた所（R1 の評審の must-fix に対して、手続きの母数と節点で直す。中を削って原画に合わせない）：
  * back_smooth（新しい節点、背のならし）：背の列（0〜約 85）を c の方向へガウスでならす（σ = ramp back_smooth [m]、行の間隔の重み）。
    原画視点の輪郭を作る頂の近く（列 75〜100）は動かさない（列の重みは c に応じて列 70/86 で 0 へ落ちる）。奥の背（c +8〜+12）の
    膨らみ（評審の R4/R6）と、上から見た足の線のくびれ・S 字の折れを消す。背が頂より高くならないようにやわらかく抑える。
  * lip_shift（新しい節点、唇の頭の移動）：唇の頭（列 186〜214 は 1、列 140 と 268 で 0 へなめらかに落ちる）を唇先の法線の向きへ
    まとめて動かす（ramp lip_shift [m]）。唇の下の輪郭 72（原画の爪の房の間の湾）を唇の縁そのもので合わせる。R1 の edge_tip
    （列 200 のまわり σ 6 列の細い帯を法線の向きへ ±0.35 m）は管の壁に 91°/m の曲がりを作っていたので 0 にし、使わない。
  * edgeL_1..12（新しい側の縁の帯、細）：唇の上面（列 97〜185、8 列おき、σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ。
    唇の上の輪郭 132 の S（x 925〜990）を合わせる。中の面は動かない（graze の重み）。
  * 巻きの消え方（fade_small）：H 5.0 m → 1.2 m の間でなめらかに（R1 は 3.5 → 2.0 m で 2〜3 行の間に形が変わり、c +14.0〜+14.6 に
    行をまたぐ折れ 228 を作っていた）。
以下は R1 の説明（そのまま）。

設計28修正01 K*′（最後の一コマ）を Houdini で作るための断面の生成器（候補 H1A の精修 R1）。numpy だけ（hython と py -3.10 の両方）。

R1 で H1A（kh_designA.py）から変えた所（評審の must-fix に対して、形の手続きの側で直す）：
  * 側の縁の移動は、海面（y < 0.3 m）と低い行では 0（H1A では平らな海も視線をかすめるので縁の ramp で動き、c −60 の行に −0.74 m の谷、
    c +15 の行に 2.8 m の段ができていた）。
  * 列 314（j_corner）= 管の中の最も後ろの点（lean で回した後の a の最小。H1A は回す前の φ = 180° で、2〜3 m ずれていた）。
  * b 区域の谷は、その所の唇の厚みの 40% より深く押さない（H1A は薄い唇を谷が突き抜け、151 行で唇の上面と下面が交差していた）。
  * 検査の関数：lip_clearance（唇の上面と下面の符号つきの間隔）、section_selfx（断面の折れ線の自己交差）、top_excess（頂より高い点）。
以下は H1A の説明（そのまま）。


Houdini のネットワーク（kh_design_scene.py が作る /obj/kstar_h_design）の Python SOP がこの関数を呼び、
最適化（kh_fit.py）は同じ関数を Houdini の外で呼ぶ（同じ式なので同じ形。最後に Houdini で cook し橋で格子へ移して確かめる）。

断面（c 一定の行、a = 進行方向、y = 高さ）は「樽（管）の中心 B のまわりの同心の殻」:
  内の面（管）   r_in(φ)  = R (1 + e2 cos 2φ) − 鉤の引き込み h (1 − (φ − φtip)/span)²       φ ∈ [φtip, φend]
  外の面（背）   r_out(φ) = r_in(φ) + τ(φ)          τ = 殻の厚み（単調な 3 次、先 → 唇 → 頂 → 背 → 背の下）
  唇先           外と内を丸い先（3 次 Bezier）でつなぐ
  足             背の下（φbl）から凹の丸みで後ろの海へ（台座なし）
  前             管（φend）から前の谷の底 D へ、D から前の海 E へ（台座なし、谷あり）
頂（列 90）は外の面の最も高い点。形は H で割った比で作り、頂を (aT, H) に置く（H と aT が原画の側の縁を動かす）。
行の母数は c の関数（CTRL の ramp、数個の鍵、単調 3 次で補間）。
その後の 2 つの段（どちらも別の節点）:
  b 区域（左肩の第二の波頭）: 肩の行の唇の上面を法線の向きへ「谷 → 稜」に押す（3 つの房は c 方向のなだらかな山）
  側の縁の合わせ（edge）: 原画視点で輪郭を作る縁の列の帯だけを、法線の向きへ c のなめらかな ramp で動かす（中は動かさない）
列の目印（K* と同じ）: j_B 18 背の足 / j_top 90 頂 / j_tip 200 唇先 / j_corner 314 管の最も後ろ（φ = 180°）/
j_facebot 379 前の谷の底 / j_E 394 前の海の始まり。
"""
import math
import json
import numpy as np

NU, NV = 400, 240
SEGCOLS = [0, 18, 90, 200, 314, 379, 394, 399]
LM = {"j_B": 18, "j_top": 90, "j_tip": 200, "j_corner": 314, "j_facebot": 379, "j_E": 394}
C_LO, C_HI = -60.0, 18.0          # ramp の 0..1 に当てる c の範囲（R1：鍵が c +17 まであるので 18 に広げた。曲線は c の単位で同じ）
C_DENSE0, C_DENSE1, DC = -19.0, 15.0, 0.2

# 名前、既定値、単位・意味、下限、上限（CTRL の ramp の名前 = 名前）
PARAMS = [
    ("crest_height", 20.5, "H 頂の高さ [m]（原画の側の縁）", 0.0, 24.0),
    ("crest_a", 0.0, "aT 頂の a 位置 [m]（波峰線の平面、原画の側の縁）", -16.0, 8.0),
    ("tube_radius", 0.40, "R/H 管の半径", 0.15, 0.60),
    ("tube_oval", -0.10, "e2 管の楕円（+ = 横長、- = 縦長）", -0.30, 0.30),
    ("lean", 18.0, "殻全体の傾き [deg]（B のまわりの回転、+ = 頂が後ろ・唇先が上）", -20.0, 50.0),
    ("shell_top", 0.20, "τ/H 頂の殻の厚み（φ = 90°）", 0.03, 0.45),
    ("shell_back", 0.27, "τ/H 背の殻の厚み（φ = 180°）", 0.03, 0.55),
    ("shell_base", 0.48, "τ/H 背の下の殻（φbl、胴の裾）", 0.05, 0.90),
    ("back_low", 212.0, "φbl 背の丸みが足の凹へ移る角 [deg]", 185.0, 240.0),
    ("foot_spread", 0.18, "足の凹の長さ /H", 0.04, 0.60),
    ("far_smooth", 0.0, "奥の行の形のならし σ [m]（c の方向。唇先を基準に行の高さで割った断面の形を混ぜる。唇先は動かない。R2）", 0.0, 4.0),
    ("back_fill", 0.0, "背の埋め 0〜1（R2）：主断面（c −4）から奥へ、同じ高さの比の背の点が前へ戻らない（上から見たくびれを埋める。背を後ろへ出すだけ）", 0.0, 1.0),
    ("back_smooth", 0.0, "背のならし σ [m]（c の方向、背の列だけ。R2：奥の背の膨らみ・足の線のくびれを消す。0 = ならさない）", 0.0, 4.0),
    ("back_out", 0.0, "背を外へ [m]（R3：背の列を水平に後ろ = 外へ。f < 0.9、頂の近くは 0。奥の行の薄い殻・肩を満たす。削らない）", 0.0, 4.0),
    ("back_env", 0.0, "背のくびれを埋める強さ 0〜1（R3：各高さの背の平面の線を ±4 m の弦から 0.8 m より前へ出さない所まで外へ埋める。高さに比例するずらし）", 0.0, 1.0),
    ("crest_lift", 0.0, "頂の持ち上げ [m]（R3：奥の行の頂のまわり（列 30〜175、列 60〜120 で全部）を上へ。唇の頭・唇先（原画の輪郭 72）と足は動かない。"
                        "奥の頂が主断面より早く低くなる『レモン形』を、唇先を動かさずに減らす）", 0.0, 4.0),
    ("back_tail", 0.0, "奥の端の背を相似に 0〜1（R3：c ≥ BT_C0 の行の背（列 0〜84）を、BT_C0 の行の背の形を行の高さで縮めた形へ寄せる。奥の端の背の膨らみ R6）", 0.0, 1.0),
    ("back_depth", 0.0, "背の奥行きの下限 /H（R3：半分の高さで頂から背までの水平の距離がこの比より浅い行を、外へ埋める。0 = 使わない。上から・後ろから見たレモン形＝行ごとの奥行きの差を減らす）", 0.0, 1.0),
    ("tip_angle", 28.0, "φtip 唇先の角（B から、deg。負 = 唇先が管の中心より下へ垂れる鉤）", -75.0, 80.0),
    ("hook_depth", 0.07, "鉤の引き込み h/H（唇先が管の中へ下がる）", 0.0, 0.25),
    ("hook_span", 55.0, "鉤の引き込みが効く角の幅 [deg]", 10.0, 120.0),
    ("lip_len", 26.0, "唇の刃の長さ（φtip からの角、deg）", 5.0, 60.0),
    ("lip_thick", 0.055, "唇の刃の厚み τ/H（φtip + lip_len）", 0.01, 0.20),
    ("lip_shift", 0.0, "唇の頭の移動 [m]（唇先の法線の向きへ唇の頭をまとめて動かす。唇の下の輪郭 72 を作る縁そのもの。R2）", -1.2, 1.2),
    ("lip_drop", 0.0, "唇の頭を下げる量 [m]（鉛直に下へ、唇の頭をまとめて動かす。唇の下の輪郭 72 の縁。R2）", -1.2, 1.2),
    ("lip_under", 0.0, "唇の頭の下面の厚み [m]（R3：唇先（列 200）のすぐ後ろの下面（列 204〜214、列 200 と 236 で 0）を断面の法線の向き（+ = 下へ厚く）へ。唇先の線は動かさずに、原画の唇の下の輪郭 72 の大きな凹凸（爪の房の間の湾）を唇の頭の厚みで作る。唇の縁は波打たない）", -0.8, 0.8),
    ("tip_round", 0.22, "唇先の頭の丸み [m]（先の厚みの半分。刃 lip_thick より厚くすると、細い首の先の丸い頭になる）", 0.05, 2.20),
    ("tube_end", 246.0, "φend 管から前の面へ移る角 [deg]", 205.0, 275.0),
    ("trough_depth", 0.20, "前の谷の深さ /H", 0.02, 0.40),
    ("trough_reach", 0.20, "管の端から谷の底までの a /H", 0.03, 0.80),
    ("trough_len", 0.32, "谷の底から前の海までの a /H", 0.08, 1.20),
    ("ledge_amp", 0.0, "b 区域：第二の波頭の強さ [m]（肩の行）", 0.0, 3.5),
    ("ledge_pos", 0.62, "b 区域：稜の位置（頂 0 → 唇先 1 の列の比）", 0.30, 0.92),
    ("ledge_width", 0.16, "b 区域：稜と谷の幅（列の比）", 0.05, 0.40),
    ("ledge_lobe", 0.0, "b 区域：房（稜の張り出しの足し分、m）。c 方向の山が房になる（3 つ）", -1.0, 2.5),
    ("ledge_lobe_depth", 0.0, "b 区域：房の凹凸を原画カメラの視線の向きへ [m]（R3：原画の輪郭をほとんど動かさずに、ほかの視点で房に見せる）", -2.5, 2.5),
    ("lipprof_1", 0.0, "唇の上面の断面の形 1：頂から唇先へ 10% の所のまわり（列の幅 ±11）を法線の向きへ [m]（R1、大きな形の線）", -0.8, 0.8),
    ("lipprof_2", 0.0, "唇の上面の断面の形 2：30% の所 [m]", -0.8, 0.8),
    ("lipprof_3", 0.0, "唇の上面の断面の形 3：50% の所 [m]", -0.8, 0.8),
    ("lipprof_4", 0.0, "唇の上面の断面の形 4：70% の所 [m]", -0.8, 0.8),
    ("lipprof_5", 0.0, "唇の上面の断面の形 5：88% の所（唇の頭）[m]", -0.8, 0.8),
    ("edge_tip", 0.0, "側の縁：唇先の縁（列 200 のまわり σ 6 列。唇の下の輪郭 72 を作る縁そのもの）を法線の向きへ [m]（R1）", -0.4, 0.4),
    ("edge_1", 0.0, "側の縁 1：列 70 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_2", 0.0, "側の縁 2：列 100 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_3", 0.0, "側の縁 3：列 130 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_4", 0.0, "側の縁 4：列 160 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_5", 0.0, "側の縁 5：列 188 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_6", 0.0, "側の縁 6：列 210 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_7", 0.0, "側の縁 7：列 240 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edge_8", 0.0, "側の縁 8：列 280 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
    ("edgeL_1", 0.0, "側の縁（細）1：唇の上面の列 97 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_2", 0.0, "側の縁（細）2：唇の上面の列 105 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_3", 0.0, "側の縁（細）3：唇の上面の列 113 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_4", 0.0, "側の縁（細）4：唇の上面の列 121 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_5", 0.0, "側の縁（細）5：唇の上面の列 129 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_6", 0.0, "側の縁（細）6：唇の上面の列 137 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_7", 0.0, "側の縁（細）7：唇の上面の列 145 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_8", 0.0, "側の縁（細）8：唇の上面の列 153 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_9", 0.0, "側の縁（細）9：唇の上面の列 161 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_10", 0.0, "側の縁（細）10：唇の上面の列 169 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_11", 0.0, "側の縁（細）11：唇の上面の列 177 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edgeL_12", 0.0, "側の縁（細）12：唇の上面の列 185 のまわり（σ 5 列）の、原画カメラの視線がかすめる所だけを法線の向きへ [m]（R2。輪郭 132）", -0.4, 0.4),
    ("edge_9", 0.0, "側の縁 9：列 320 のまわり（σ 14 列）の、原画カメラの視線がかすめる所（輪郭の縁）だけを法線の向きへ [m]（R1。中の面は動かない）", -0.4, 0.4),
]
PNAMES = [p[0] for p in PARAMS]
PDEF = {p[0]: p[1] for p in PARAMS}
PBOUNDS = {p[0]: (p[3], p[4]) for p in PARAMS}
PDESC = {p[0]: p[2] for p in PARAMS}
EDGE_CENTERS = (70, 100, 130, 160, 188, 210, 240, 280, 320)       # R1: 9 column bands (Gaussian, partition of unity)
EDGE_SIG = 14.0
EDGEL_CENTERS = tuple(97 + 8 * k for k in range(12))             # R2: 12 fine bands on the lip top (the 132 outline)
EDGEL_SIG = 5.0
EDGE_NAMES = ["edge_%d" % (k + 1) for k in range(len(EDGE_CENTERS))] + ["edge_tip"] + ["edgeL_%d" % (k + 1) for k in range(len(EDGEL_CENTERS))]
TIP_SIG = 6.0


# ------------------------------------------------------------------ rows
def c_rows():
    n_dense = int(round((C_DENSE1 - C_DENSE0) / DC))
    dense = C_DENSE0 + DC * np.arange(n_dense + 1)
    n_left = NV - len(dense)
    L = C_DENSE0 - C_LO
    lo, hi = 1.0, 1.3
    for _ in range(100):
        g = 0.5 * (lo + hi)
        s = DC * (g ** np.arange(1, n_left + 1))
        if s.sum() > L:
            hi = g
        else:
            lo = g
    s = DC * (g ** np.arange(1, n_left + 1)); s *= L / s.sum()
    left = C_DENSE0 - np.cumsum(s)
    c = np.r_[left[::-1], dense]
    c[0] = C_LO
    return c


# ------------------------------------------------------------------ monotone cubic (Fritsch-Carlson), the ramp basis
def pchip(xk, yk, x):
    xk = np.asarray(xk, float); yk = np.asarray(yk, float); x = np.asarray(x, float)
    if len(xk) == 1:
        return np.full_like(x, yk[0])
    o = np.argsort(xk); xk, yk = xk[o], yk[o]
    h = np.diff(xk); d = np.diff(yk) / h
    m = np.zeros_like(yk)
    if len(xk) == 2:
        m[:] = d[0]
    else:
        for i in range(1, len(xk) - 1):
            if d[i - 1] * d[i] <= 0:
                m[i] = 0.0
            else:
                w1 = 2 * h[i] + h[i - 1]; w2 = h[i] + 2 * h[i - 1]
                m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
        # end slopes: flat (a ramp holds its end value; also keeps the rows constant outside the keys)
        m[0] = 0.0; m[-1] = 0.0
    xc = np.clip(x, xk[0], xk[-1])
    i = np.clip(np.searchsorted(xk, xc) - 1, 0, len(xk) - 2)
    t = (xc - xk[i]) / h[i]
    h00 = (1 + 2 * t) * (1 - t) ** 2; h10 = t * (1 - t) ** 2; h01 = t * t * (3 - 2 * t); h11 = t * t * (t - 1)
    return h00 * yk[i] + h10 * h[i] * m[i] + h01 * yk[i + 1] + h11 * h[i] * m[i + 1]


def bspline_ramp(xk, yk, x, per_span=48):
    """ramp の B-spline 基底（Houdini の ramp の「B-Spline」と同じ考え方）：鍵 (c_k, v_k) を制御点とする
    開いた一様 3 次 B-spline（両端の鍵を通る）。曲線は鍵の多角形の中に収まり（波打たない）、2 階まで連続。
    鍵の外では端の値のまま。"""
    xk = np.asarray(xk, float); yk = np.asarray(yk, float); x = np.asarray(x, float)
    o = np.argsort(xk, kind="stable"); xk, yk = xk[o], yk[o]
    n = len(xk)
    if n == 1:
        return np.full_like(x, yk[0])
    if n < 4:
        return np.interp(x, xk, yk)
    m = n - 3
    kn = np.r_[[0.0] * 3, np.arange(m + 1, dtype=float), [float(m)] * 3]
    t = np.linspace(0.0, m, m * per_span + 1)
    t[-1] = m - 1e-12
    # de Boor basis (vectorised Cox-de Boor)
    B = np.zeros((len(t), len(kn) - 1))
    for i in range(len(kn) - 1):
        B[:, i] = (kn[i] <= t) & (t < kn[i + 1])
    for d in range(1, 4):
        Bn = np.zeros((len(t), len(kn) - 1 - d))
        for i in range(len(kn) - 1 - d):
            a = (t - kn[i]) / (kn[i + d] - kn[i]) if kn[i + d] > kn[i] else 0.0
            b = (kn[i + d + 1] - t) / (kn[i + d + 1] - kn[i + 1]) if kn[i + d + 1] > kn[i + 1] else 0.0
            Bn[:, i] = a * B[:, i] + b * B[:, i + 1]
        B = Bn
    cx = B @ xk; cy = B @ yk
    cx[-1] = xk[-1]; cy[-1] = yk[-1]
    return np.interp(x, cx, cy)


RAMP_BASIS = "bspline"


class Design:
    """母数ごとの鍵（c [m] と値）。Houdini の ramp（位置 u = (c − C_LO)/(C_HI − C_LO)、基底 B-Spline）と同じ中身。"""

    def __init__(self, keys=None):
        self.keys = {}
        for n in PNAMES:
            k = (keys or {}).get(n)
            self.keys[n] = ([float(x) for x in k[0]], [float(v) for v in k[1]]) if k else ([0.0], [PDEF[n]])

    def eval(self, c):
        f = bspline_ramp if RAMP_BASIS == "bspline" else pchip
        return {n: f(self.keys[n][0], self.keys[n][1], c) for n in PNAMES}

    def to_json(self):
        return {"schema": "GreatWave.kstar_h.design/1", "c_range_for_ramps": [C_LO, C_HI],
                "keys": {n: {"c": self.keys[n][0], "v": self.keys[n][1]} for n in PNAMES}}

    @staticmethod
    def from_json(d):
        return Design({n: (v["c"], v["v"]) for n, v in d["keys"].items()})

    @staticmethod
    def load(path):
        return Design.from_json(json.load(open(path, encoding="utf-8")))

    def save(self, path):
        json.dump(self.to_json(), open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# ------------------------------------------------------------------ curve helpers
def arclen(P):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(P[:, 0]), np.diff(P[:, 1])))]


def resample(P, n):
    s = arclen(P)
    if s[-1] < 1e-12:
        return np.repeat(P[:1], n + 1, 0)
    q = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def resample_at(P, q):
    s = arclen(P)
    return np.stack([np.interp(q, s, P[:, 0]), np.interp(q, s, P[:, 1])], -1)


def bezier(P0, P1, P2, P3, n):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * P0 + 3 * (1 - t) ** 2 * t * P1 + 3 * (1 - t) * t * t * P2 + t ** 3 * P3


def hermite(P0, T0, P1, T1, k0, k1, n=None):
    d = float(np.linalg.norm(P1 - P0))
    if n is None:
        n = max(int(math.ceil(1.6 * d / 0.004)), 8)
    return bezier(P0, P0 + k0 * d * T0, P1 - k1 * d * T1, P1, n)


def cat(parts):
    out = [parts[0]]
    for p in parts[1:]:
        out.append(p[1:] if np.linalg.norm(p[0] - out[-1][-1]) < 1e-9 else p)
    return np.vstack(out)


def unit(v):
    return v / max(float(np.linalg.norm(v)), 1e-12)


def smooth_poly(P, sig, step):
    """弧長で取り直してガウスでならす（端は固定）。sig・step は同じ単位。"""
    if sig <= 0 or len(P) < 5:
        return P
    s = arclen(P)
    q = np.arange(0.0, s[-1] + 1e-12, step)
    if len(q) < 7:
        return P
    X = resample_at(P, q)
    r = int(math.ceil(3 * sig / step))
    ker = np.exp(-0.5 * (np.arange(-r, r + 1) * step / sig) ** 2); ker /= ker.sum()
    Xp = np.pad(X, ((r, r), (0, 0)), mode="edge")
    Xs = np.stack([np.convolve(Xp[:, k], ker, "valid") for k in range(2)], -1)
    w = np.clip(np.minimum(np.arange(len(q)), np.arange(len(q))[::-1]) / max(r, 1), 0, 1)
    return X + w[:, None] * (Xs - X)


# ------------------------------------------------------------------ one section (unit height, barrel centre at the origin)
def _polar(r, phi):
    return np.stack([r * np.cos(phi), r * np.sin(phi)], -1)


def unit_section(p, Hm):
    """p: scalars of one row (ratios of H).  Hm = the row height in metres (for the absolute tip radius).
    returns dict of polylines in unit coordinates (B at the origin) and landmarks."""
    D = math.radians
    R = float(p["tube_radius"]); e2 = float(p["tube_oval"])
    ptip = D(float(p["tip_angle"])); span = D(max(float(p["hook_span"]), 1.0)); hk = float(p["hook_depth"])
    pbl = D(float(p["back_low"]))
    # R1: the tube hands over to the front face before its lowest point (after the lean), so the face runs down into the
    # trough without first rising (H1A's vertical S-fold on the tube face): soft minimum with 262 deg - lean
    te, tl = float(p["tube_end"]), 262.0 - float(p.get("lean", 0.0))
    kq = 3.0
    pend = D(-kq * math.log(math.exp(-te / kq) + math.exp(-tl / kq)))
    # R1: the round head of the lip never exceeds 3.5 % of the row height (soft minimum): in the low closing rows a head of
    #     fixed metres dominated the tiny curl and creased the sheet across the rows
    tr, tl_ = max(float(p["tip_round"]), 0.03), 0.035 * Hm
    kr = 0.02
    rt = max(-kr * math.log(math.exp(-tr / kr) + math.exp(-tl_ / kr)), 0.02) / Hm
    tau_tip = 2.0 * rt
    llen = D(max(float(p["lip_len"]), 2.0))
    tk_phi = [ptip, ptip + llen, 0.5 * math.pi, math.pi, pbl]
    tk_val = [tau_tip, max(float(p["lip_thick"]), 0.01), float(p["shell_top"]), float(p["shell_back"]), float(p["shell_base"])]
    # keep the knots ordered (the lip knot may not pass the top)
    # soft clamp (no crease across the rows when the lip knot meets its limit)
    kk = D(3.0)
    lim = 0.5 * math.pi - D(8)
    tk_phi[1] = -kk * math.log(math.exp(-tk_phi[1] / kk) + math.exp(-lim / kk))
    tk_phi[1] = kk * math.log(math.exp(tk_phi[1] / kk) + math.exp((ptip + D(2)) / kk))
    # the thickness never shrinks from the lip blade toward the back; the tip head may be thicker than the blade
    # (a round head on a thinner neck: the painting's drooping lip head, its concave くびれ on the lip top)
    for i in range(2, len(tk_val)):
        tk_val[i] = max(tk_val[i], tk_val[i - 1] + 1e-4)

    def r_in(phi):
        u = np.clip(1.0 - (phi - ptip) / span, 0.0, 1.0)
        return R * (1.0 + e2 * np.cos(2.0 * phi)) - hk * u * u

    def dr_in(phi):
        u = np.clip(1.0 - (phi - ptip) / span, 0.0, 1.0)
        return -2.0 * R * e2 * np.sin(2.0 * phi) + 2.0 * hk * u / span * ((phi - ptip) < span)

    def tau(phi):
        return pchip(tk_phi, tk_val, phi)

    step = D(0.25)
    # outer: from the back-low angle down to the tip
    pho = np.linspace(pbl, ptip, 1000)
    ro = r_in(pho) + tau(pho)
    outer = _polar(ro, pho)
    # inner: from the tip up to the tube end
    phi_i = np.linspace(ptip, pend, 1000)
    inner = _polar(r_in(phi_i), phi_i)
    # headings
    eps = 1e-4

    def d_outer(phi):          # traversal toward the tip = decreasing phi
        P1 = _polar(r_in(phi + eps) + tau(phi + eps), phi + eps); P0 = _polar(r_in(phi - eps) + tau(phi - eps), phi - eps)
        return unit(P0 - P1)

    def d_inner(phi):          # traversal away from the tip = increasing phi
        return unit(_polar(r_in(phi + eps), phi + eps) - _polar(r_in(phi - eps), phi - eps))
    # tip cap (rounded, bulging along the outer heading)
    Po, Pi = outer[-1], inner[0]
    ho, hi = d_outer(ptip), d_inner(ptip)
    k = 0.95 * float(np.linalg.norm(Po - Pi))
    cap = bezier(Po, Po + k * ho, Pi - k * hi, Pi, 81)
    # lean: rotate the whole shell about B (CCW = crest back, tip up)
    lw = D(float(p.get("lean", 0.0)))
    Rm = np.array([[math.cos(lw), -math.sin(lw)], [math.sin(lw), math.cos(lw)]])
    outer = outer @ Rm.T; inner = inner @ Rm.T; cap = cap @ Rm.T
    d_o0, d_i0 = d_outer, d_inner
    d_outer = lambda phi: Rm @ d_o0(phi)
    d_inner = lambda phi: Rm @ d_i0(phi)
    # top = highest point of the outer, located continuously (parabola through the 3 samples around the maximum)
    # soft argmax (continuous when the top is flat or has two near-equal humps; a hard argmax would jump and
    # crease the sheet across the rows)
    yo = outer[:, 1]
    wts = np.exp((yo - yo.max()) / 0.004)
    kt_soft = float(np.sum(wts * np.arange(len(yo))) / np.sum(wts))
    kt = int(np.clip(np.floor(kt_soft), 1, len(outer) - 2)); ft = kt_soft - kt
    # corner (R1) = the rearmost point of the tube (minimum a after the lean), located continuously (soft argmin over the
    # inner curve from phi = 90 deg to the tube end); kept at least 60 samples before the tube end
    lo = int(np.searchsorted(phi_i, 0.5 * math.pi))
    xi = inner[lo:, 0]
    wts_c = np.exp(-(xi - xi.min()) / 0.004)
    fc = lo + float(np.sum(wts_c * np.arange(len(xi))) / np.sum(wts_c))
    fc = float(np.clip(fc, lo, len(phi_i) - 61))
    return dict(outer=outer, inner=inner, cap=cap, kt=kt + ft, corner_f=fc,
                pbl=pbl, pend=pend, lean=lw, d_outer=d_outer, d_inner=d_inner, r_in=r_in, tau=tau, R=R)


def split_frac(P, f):
    """split polyline P at the fractional index f -> (P[..f], P[f..]) sharing the interpolated point."""
    f = float(np.clip(f, 0.0, len(P) - 1.0))
    k = int(math.floor(f)); t = f - k
    if k >= len(P) - 1:
        return P.copy(), P[-1:].copy()
    Q = P[k] + t * (P[k + 1] - P[k])
    first = np.vstack([P[:k + 1], Q[None]]) if t > 1e-9 else P[:k + 1].copy()
    second = np.vstack([Q[None], P[k + 1:]]) if t > 1e-9 else P[k:].copy()
    return first, second


def split_arc(P, frac):
    s = arclen(P)
    f = float(np.interp(frac * s[-1], s, np.arange(len(P))))
    return split_frac(P, f)


def section(p):
    """p: scalars of one row.  returns (400, 2) (a, y) in metres and info."""
    H_true = max(float(p["crest_height"]), 0.0)
    Hm = max(H_true, 1.5)
    squash = H_true / Hm
    aT = float(p["crest_a"])
    U = unit_section(p, Hm)
    outer, inner, cap = U["outer"], U["inner"], U["cap"]
    back_all, lip_top = split_frac(outer, U["kt"])
    top = lip_top[0].copy()
    ysea = top[1] - 1.0                  # still water in unit coordinates
    # ---- back: the outer from the back-low angle, starting where it is at the foot height (interpolated crossing)
    foot_h = 0.06
    yy = back_all[:, 1] - (ysea + foot_h)
    above = np.nonzero(yy >= 0)[0]
    if len(above) == 0:
        f_foot = float(len(back_all) - 2)
    elif above[0] == 0:
        f_foot = 0.0
    else:
        k = int(above[0]); f_foot = (k - 1) + float(-yy[k - 1] / (yy[k] - yy[k - 1]))
    # R1: the round back never runs under itself: it starts at the rearmost point of the outer curve (minimum a, soft) when
    # that is higher than the foot height; below it the concave foot flows back into the sea (no undercut kick at the foot)
    xb = back_all[:, 0]
    wr = np.exp(-(xb - xb.min()) / REAR_T)
    f_rear = float(np.sum(wr * np.arange(len(xb))) / np.sum(wr))
    kk2 = 2.0
    f = kk2 * math.log(math.exp(f_foot / kk2) + math.exp(f_rear / kk2))        # smooth max of the two sample indices
    f = float(np.clip(f, 0.0, len(back_all) - 2.0))
    back_round = split_frac(back_all, f)[1] if f > 1e-9 else back_all
    Pb = back_round[0]
    hb = unit(back_round[min(3, len(back_round) - 1)] - back_round[0])
    # never let the back start by heading down (undercut): soft floor of the upward component at 0.2
    kk = 0.05
    hy = 0.2 + kk * math.log1p(math.exp((hb[1] - 0.2) / kk)) if (hb[1] - 0.2) / kk < 30 else hb[1]
    hb = unit(np.array([hb[0], hy]))
    F = np.array([Pb[0] - float(p["foot_spread"]) - 0.35 * (Pb[1] - ysea), ysea])
    fillet = hermite(F, np.array([1.0, 0.0]), Pb, hb, 0.45, 0.45)
    back = cat([fillet, back_round])
    # ---- upper lip: top -> tip apex (arc-length middle of the cap)
    cap_up, cap_lo = split_arc(cap, 0.5)
    upper = cat([lip_top, cap_up])
    # ---- inner: cap second half -> tube to 180 deg (corner) -> tube end
    tube_a, tube_b = split_frac(inner, U["corner_f"])
    lower = cat([cap_lo, tube_a])
    face_tube = tube_b
    Qe = face_tube[-1]
    he = U["d_inner"](U["pend"])
    yD = ysea - float(p["trough_depth"])
    Dp = np.array([Qe[0] + float(p["trough_reach"]) + 0.6 * max(Qe[1] - yD, 0.0) * max(he[0], 0.0), yD])
    # the trough bottom stays below the tube end (soft minimum, no crease across the rows)
    kk = 0.02
    lim = Qe[1] - 0.02
    Dp[1] = -kk * math.log(math.exp(-Dp[1] / kk - (-lim / kk)) + 1.0) + (-kk * (-lim / kk)) if False else         min(Dp[1], lim) - kk * math.log1p(math.exp(-abs(Dp[1] - lim) / kk))
    face = cat([face_tube, hermite(Qe, he, Dp, np.array([1.0, 0.0]), 0.40, 0.45)])
    E = np.array([Dp[0] + float(p["trough_len"]), ysea])
    ramp = hermite(Dp, np.array([1.0, 0.0]), E, np.array([1.0, 0.0]), 0.45, 0.45)
    # ---- to metres (top at (aT, H)); the geometry is built at >= 1.5 m and squashed below
    # R2: below 1.5 m the section is scaled down uniformly (a and y) about the crest top's foot, so the tiny closing curls keep their shape
    #     (R1 squashed them vertically only)
    # R3 (CONE): the far end (c > 0) scales the whole 1.5 m section uniformly (a and y) by s = max(H / 1.5, CONE_SMIN), so the rows below
    #     1.5 m are similar copies shrinking to a tiny copy in the last row (a cone to a small apex: no fold, no self-crossing). The near
    #     end keeps R1's vertical squash.
    #     R3: the near end too (R2 faded the near tail into a swell between 3.5 and 2.0 m: folds up to 86 deg at c -37.5)
    if p.get("_far", 1.0) > 0.5 or CONE_NEAR:
        sa = max(squash, CONE_SMIN); sy = sa
    else:
        sa = 1.0; sy = squash

    def m(P):
        Q = np.empty_like(P)
        Q[:, 0] = aT + Hm * (P[:, 0] - top[0]) * sa
        Q[:, 1] = Hm * (P[:, 1] - ysea) * sy
        return Q
    back, upper, lower, face, ramp = m(back), m(upper), m(lower), m(face), m(ramp)
    # light smoothing of the G1 joints (curvature), keeping the landmark points
    sg = 0.20 * min(1.0, Hm / 8.0)
    back = smooth_poly(back, sg, 0.02); face = smooth_poly(face, sg, 0.02); ramp = smooth_poly(ramp, sg, 0.02)
    Fm, Em = back[0], ramp[-1]
    backsea = np.array([[Fm[0] - 40.0, 0.0], [Fm[0], 0.0]])
    frontsea = np.array([[Em[0], 0.0], [Em[0] + 30.0, 0.0]])
    segs = [backsea, back, upper, lower, face, ramp, frontsea]
    out = [resample(segs[0], SEGCOLS[1])]
    TIPC, TIPL = 12, 0.9
    for k in range(1, 7):
        n = SEGCOLS[k + 1] - SEGCOLS[k]
        P = segs[k]
        if k in (2, 3):
            s_ = arclen(P); L = s_[-1]; Lt = min(TIPL, 0.3 * L)
            if k == 2:
                q = np.r_[np.linspace(0, L - Lt, n - TIPC + 1)[:-1], np.linspace(L - Lt, L, TIPC + 1)]
            else:
                q = np.r_[np.linspace(0, Lt, TIPC + 1)[:-1], np.linspace(Lt, L, n - TIPC + 1)]
            Q = resample_at(P, q)
        else:
            Q = resample(P, n)
        out.append(Q[1:])
    S = np.vstack(out)
    assert S.shape == (NU, 2), S.shape
    info = {"H": H_true, "tip": S[200].copy(), "top": S[90].copy(), "B": np.array([aT + Hm * (0 - top[0]), Hm * (0 - ysea) * squash]),
            "R_m": U["R"] * Hm}
    return S, info


# ------------------------------------------------------------------ in-plane normals of a row, normal displacement bands
def row_normals(a, y):
    """単位の法線（進む向きの左 = 断面の外側。背では後ろ上、唇の上では上、管の中では管の中心の向き）"""
    ta = np.gradient(a); ty = np.gradient(y)
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    return np.stack([-ty / L, ta / L], -1)


def band_weight(j0, j1, ramp, nu=NU):
    j = np.arange(nu, dtype=float)
    w = np.clip((j - j0) / max(ramp, 1), 0, 1) * np.clip((j1 - j) / max(ramp, 1), 0, 1)
    return w * w * (3 - 2 * w)


FADE_NEAR_HI, FADE_NEAR_LO = 0.0, 0.0   # R3: no fade at the near end either (R2 kept R1's fade 3.5 -> 2.0 m and vertical squash: folds 64..86 deg at c -37.5)
CONE_NEAR = True                        # R3: the near tail below 1.5 m is also a cone of similar sections
FADE_HI, FADE_LO = 0.0, 0.0      # R3: no fade at the far end (R2 faded the last rows below 0.9 m into a monotone strip: the tip cap of c +14.8 met the flat
                                 #     c +15 row, 39 triangle pairs and 74 flipped quads); the far end is a cone of similar sections (CONE_SMIN)
SMALL_UNIFORM = True
SMALL_FLOOR = 0.25               # (R2, not used in R3)
CONE_SMIN = 0.004                # R3: the last far row is a 0.4 % copy of the 1.5 m section (6 mm high, about 0.15 m long): a small apex, no zero-area triangle
LS_FADE_FAR = (0.3, 3.0)         # R3: the lip-head move fades out on the low far rows (H 3.0 m -> 0.3 m), so the small cone sections keep their shape


def fade_small(A, Y, H, c=None):
    """低い行（波の両端）: 巻きを単調な膨らみへなだらかに移す（平面で折り返さない）。
    R2：奥の端（c > 0）は FADE_HI → FADE_LO（0.9 → 0 m、巻きのまま相似に縮む）、手前の肩の端（c ≤ 0、行が疎）は R1 のまま（3.5 → 2.0 m）。"""
    for r in range(len(A)):
        h = H[r]
        # R1: the curl fades out between 3.5 m and 2.0 m (H1A: 3.0 -> 0.6 m); lower rows are a pure swell, so the tiny
        #     squashed curls of the end rows never cross themselves
        fb, lo = (FADE_HI, FADE_LO) if (c is None or c[r] > 0.0) else (FADE_NEAR_HI, FADE_NEAR_LO)
        if h >= fb or fb <= lo:
            continue
        w = float(np.clip((h - lo) / (fb - lo), 0.0, 1.0)); w = w * w * (3 - 2 * w)
        a, y = A[r], Y[r]
        j0, j1 = SEGCOLS[1], SEGCOLS[6]
        s = np.r_[0.0, np.cumsum(np.hypot(np.diff(a[j0:j1 + 1]), np.diff(y[j0:j1 + 1])))]
        f = s / max(s[-1], 1e-9)
        flat_a = a[j0] + f * (a[j1] - a[j0])
        # a monotone swell of the same height centred at the crest top
        at = a[90]
        sw = 0.5 * (a[j1] - a[j0])
        flat_y = h * np.exp(-0.5 * ((flat_a - at) / max(0.35 * sw, 0.3)) ** 2)
        A[r, j0:j1 + 1] = w * a[j0:j1 + 1] + (1 - w) * flat_a
        Y[r, j0:j1 + 1] = w * y[j0:j1 + 1] + (1 - w) * flat_y
    return A, Y


# ------------------------------------------------------------------ the three stages
def build_base(design, c=None):
    if c is None:
        c = c_rows()
    P = design.eval(c)
    A = np.zeros((len(c), NU)); Y = np.zeros((len(c), NU))
    for r in range(len(c)):
        p = {k: float(P[k][r]) for k in PNAMES}
        p["_far"] = 1.0 if c[r] > 0.0 else 0.0
        S, _ = section(p)
        A[r], Y[r] = S[:, 0], S[:, 1]
    A, Y = fade_small(A, Y, P["crest_height"], c)
    return c, A, Y, P


LIPPROF_U = (0.10, 0.30, 0.50, 0.70, 0.88)
LIPPROF_SIG = 0.10


def apply_lipprof(c, A, Y, P):
    """R1 唇の上面の断面の形：頂（列 90）→ 唇先（列 200）の外の面を、5 つのなめらかな山（列の比 0.1/0.3/0.5/0.7/0.88、幅 σ 0.1）の
    和の量だけ法線の向きへ動かす。量は c の ramp（鍵 2.5 m おき）。原画視点で唇の上の輪郭（132）を作るのは主断面のまわりの行の
    この断面の線そのものなので、その線の形（凸の頂 → くびれ → 凸の鉤）を断面の側で決める（行ごとに振らない）。"""
    names = ["lipprof_%d" % (k + 1) for k in range(len(LIPPROF_U))]
    if not any(n in P and np.any(np.abs(P[n]) > 1e-7) for n in names):
        return A, Y
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    # the band rises slowly from the crest top (22 columns ~ 2 m, C1 smoothstep) so the top stays one round arc (Q17: no kink at
    # the top; a 5-column ramp made a 12-17 deg single-vertex fold at column 92)
    x0 = np.clip((j - 90.0) / 22.0, 0.0, 1.0); x1 = np.clip((199.0 - j) / 6.0, 0.0, 1.0)
    wband = (x0 * x0 * (3 - 2 * x0)) * (x1 * x1 * (3 - 2 * x1))
    basis = [np.exp(-0.5 * ((u - uk) / LIPPROF_SIG) ** 2) * wband for uk in LIPPROF_U]
    for r in range(len(c)):
        prof = sum(float(P[n][r]) * b for n, b in zip(names, basis))
        if not np.any(np.abs(prof) > 1e-7):
            continue
        prof = prof * body_mask(Y[r])
        n = row_normals(A[r], Y[r])
        A[r] += prof * n[:, 0]; Y[r] += prof * n[:, 1]
    return A, Y


LEDGE_VALLEY = 0.5           # depth of the valley in front of the ridge (x amp); R1 0.85; R2 0.5 (a broad second crest, not a pleat)


def apply_ledge(c, A, Y, P):
    """b 区域：肩の行の唇の上面（列 90〜200）を法線の向きへ、谷（頂の側）→ 稜（唇先の側）の形に押す。
    強さ ledge_amp(c)、稜の位置 ledge_pos、幅 ledge_width（列の比）。唇先そのもの（列 190〜）は動かさない。"""
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    for r in range(len(c)):
        amp = float(P["ledge_amp"][r]); lobe = float(P["ledge_lobe"][r]) if "ledge_lobe" in P else 0.0
        if abs(amp) < 1e-6 and abs(lobe) < 1e-6:
            continue
        pos = float(P["ledge_pos"][r]); wd = max(float(P["ledge_width"][r]), 0.03)
        ridge = np.exp(-0.5 * ((u - pos) / wd) ** 2)
        prof = amp * (ridge - LEDGE_VALLEY * np.exp(-0.5 * ((u - (pos - 1.6 * wd)) / (0.9 * wd)) ** 2)) + lobe * ridge
        prof *= band_weight(92, 196, 6)
        # R1: the valley (inward push) never goes deeper than 40 % of the local lip thickness (smooth cap)
        th = lip_thickness(A[r], Y[r])
        cap = np.maximum(0.40 * th, 0.02)
        prof = np.where(prof < 0.0, -cap * np.tanh(-prof / cap), prof)
        prof = prof * body_mask(Y[r])          # R1: never on the sea
        n = row_normals(A[r], Y[r])
        A[r] += prof * n[:, 0]; Y[r] += prof * n[:, 1]
    return A, Y


# PaintingCam v1（Unity、kh_common と同じ値）と K* の断面の枠
CAM_POS_U = np.array([0.0, 3.0, -62.0])
FRAME_E = np.array([0.6798348938056157, 0.0, 0.733365200404483])
FRAME_T = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
FRAME_O = np.array([-7.227685896240013, 0.0, -2.7131699203121187])
REAR_T = 0.004        # R1: softness of the rearmost-point search of the back (unit section coordinates)
GRAZE = 0.12          # |cos(視線, 面の法線)| がこの程度までを「輪郭の縁」とみなす（なめらかな重み）


def world_u(c, A, Y):
    return FRAME_O[None, None, :] + A[..., None] * FRAME_T + Y[..., None] * np.array([0.0, 1.0, 0.0]) + np.asarray(c)[:, None, None] * FRAME_E


def graze_weight(c, A, Y):
    """原画カメラから見て面が視線に沿う（輪郭を作る）所ほど 1 になる重み exp(-(cosθ/GRAZE)²)。"""
    X = world_u(c, A, Y)
    du = np.gradient(X, axis=1); dv = np.gradient(X, axis=0)
    n = np.cross(du, dv)
    v = X - CAM_POS_U
    cos = np.sum(n * v, -1) / np.maximum(np.linalg.norm(n, axis=-1) * np.linalg.norm(v, axis=-1), 1e-12)
    return np.exp(-(cos / GRAZE) ** 2)


def edge_band_weights(nu=NU):
    """R1: the 9 column bands of the side-edge strips: Gaussians (sigma 14 columns) normalised to a partition of unity over
    columns 60..330, fading to 0 outside (the sea margins and the far back never move)."""
    j = np.arange(nu, dtype=float)
    g = np.stack([np.exp(-0.5 * ((j - cc) / EDGE_SIG) ** 2) for cc in EDGE_CENTERS])
    g = g / np.maximum(g.sum(0, keepdims=True), 1e-12)
    return g * band_weight(40, 350, 20)[None, :]


def edge_modes(c, A, Y):
    """R1: per band b the field M_b(r, j) = smooth_cols(W_b * G) * body: the displacement (m, along the section normal) per
    metre of the band's ramp value.  The side-edge displacement is sum_b ramp_b(c_r) * M_b(r, j)."""
    G = graze_weight(c, A, Y)
    # copy A: the grazing weight is smoothed over the sheet (4 columns, 3 rows) and the displacement again along the
    # section (3 columns), so the side-edge strips never kink a section or crease across the rows
    G = _smooth2(G, 4.0, 3.0)
    W = edge_band_weights(A.shape[1])
    body = body_mask(Y)
    modes = [_smooth2(W[b][None, :] * G, 3.0, 0.0) * body for b in range(len(W))]
    # the lip-tip edge (the underside outline 72 is drawn by the tips of the rows): a narrow band around column 200,
    # not weighted by the grazing (the tip cap is the edge itself)
    j = np.arange(A.shape[1], dtype=float)
    modes.append(np.exp(-0.5 * ((j - 200.0) / TIP_SIG) ** 2)[None, :] * body)
    # R2: the fine lip-top bands (the 132 outline): Gaussians (sigma 5 columns) weighted by the grazing, never past the lip head
    head = np.clip((194.0 - j) / 8.0, 0.0, 1.0)
    for cc in EDGEL_CENTERS:
        wl = np.exp(-0.5 * ((j - cc) / EDGEL_SIG) ** 2) * head * band_weight(88, 200, 6)
        modes.append(_smooth2(wl[None, :] * G, 2.0, 0.0) * body)
    return np.stack(modes)


def apply_edges(c, A, Y, P, modes=None):
    """側の縁の合わせ（R1）：原画視点で輪郭を作る縁（視線が面をかすめる所、なめらかな重み）だけを、9 本の列の帯の ramp の量だけ
    断面の法線の向きへ動かす。中の面・海・低い行は動かない。"""
    A = A.copy(); Y = Y.copy()
    if not any(np.any(np.abs(P[k]) > 1e-7) for k in EDGE_NAMES):
        return A, Y
    M = edge_modes(c, A, Y) if modes is None else modes
    Dm = sum(np.asarray(P[k])[:, None] * M[b] for b, k in enumerate(EDGE_NAMES))
    for r in range(len(c)):
        d = Dm[r]
        if not np.any(np.abs(d) > 1e-7):
            continue
        n = row_normals(A[r], Y[r])
        A[r] += d * n[:, 0]; Y[r] += d * n[:, 1]
    return A, Y


def _gk(sig):
    if sig <= 0:
        return np.array([1.0])
    r = int(np.ceil(3 * sig)); k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    return k / k.sum()


def _smooth2(M, sig_col, sig_row):
    """separable Gaussian smoothing (edge-padded) along columns (axis 1) and rows (axis 0)."""
    out = M
    for ax, sg in ((1, sig_col), (0, sig_row)):
        if sg <= 0:
            continue
        k = _gk(sg); r = len(k) // 2
        pad = [(0, 0), (0, 0)]; pad[ax] = (r, r)
        Q = np.pad(out, pad, mode="edge")
        out = np.apply_along_axis(lambda v: np.convolve(v, k, "valid"), ax, Q)
    return out


def body_mask(Y, y0=0.3, y1=1.5):
    """1 on the wave body, 0 on the sea (y <= y0), smooth in between (R1)."""
    x = np.clip((np.asarray(Y) - y0) / (y1 - y0), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def lip_thickness(a, y, j0=90, j1=200, jl1=330):
    """R1: per column j0..j1 of the upper lip, the distance to the nearest point of the lower chain (cols j1..jl1); other
    columns get a large value.  (distance to the vertices, densified 4x along the lower chain)"""
    out = np.full(len(a), 99.0)
    L = np.stack([a[j1:jl1 + 1], y[j1:jl1 + 1]], -1)
    t = np.linspace(0, 1, 4, endpoint=False)[None, :, None]
    Ld = (L[:-1, None, :] * (1 - t) + L[1:, None, :] * t).reshape(-1, 2)
    U = np.stack([a[j0:j1 - 3], y[j0:j1 - 3]], -1)
    d = np.sqrt(((U[:, None, :] - Ld[None, :, :]) ** 2).sum(-1)).min(1)
    out[j0:j1 - 3] = d
    return out


def lip_clearance(A, Y, rows=None, j0=95, j1=197, jl0=203, jl1=None):
    """R1: signed clearance (m) of the upper lip (cols j0..j1) above the lower surface (cols jl0..jl1, default up to the
    corner 314 + 30): + = the water body between them, − = the upper surface has passed through the lower one.
    returns (per-row minimum, per-row column of the minimum)."""
    nv = A.shape[0]
    rows = range(nv) if rows is None else rows
    jl1 = jl1 or 344
    mins = np.full(nv, 99.0); cols = np.zeros(nv, int)
    for r in rows:
        if Y[r].max() < 1.0:
            continue
        L = np.stack([A[r, jl0:jl1 + 1], Y[r, jl0:jl1 + 1]], -1)
        tl = np.gradient(L, axis=0)
        tl /= np.maximum(np.linalg.norm(tl, axis=1, keepdims=True), 1e-12)
        nl = np.stack([-tl[:, 1], tl[:, 0]], -1)             # left of the lower chain's traversal = away from the water
        U = np.stack([A[r, j0:j1 + 1], Y[r, j0:j1 + 1]], -1)
        D = U[:, None, :] - L[None, :, :]
        dist = np.sqrt((D ** 2).sum(-1))
        k = np.argmin(dist, 1)
        sgn = -np.sign(np.einsum("ij,ij->i", D[np.arange(len(U)), k], nl[k]))
        sd = sgn * dist[np.arange(len(U)), k]
        i = int(np.argmin(sd))
        mins[r] = float(sd[i]); cols[r] = j0 + i
    return mins, cols


def segx_count(P, i0=0, i1=None):
    """R1: number of crossings between non-adjacent segments of the polyline P[i0:i1] (2-D)."""
    P = P[i0:i1]
    a0 = P[:-1]; a1 = P[1:]
    n = len(a0)
    I, J = np.triu_indices(n, 2)
    mn = np.minimum(a0, a1); mx = np.maximum(a0, a1)
    ok = (mn[J, 0] <= mx[I, 0]) & (mx[J, 0] >= mn[I, 0]) & (mn[J, 1] <= mx[I, 1]) & (mx[J, 1] >= mn[I, 1])
    I, J = I[ok], J[ok]
    if len(I) == 0:
        return 0, []
    p, r = a0[I], a1[I] - a0[I]; q, s_ = a0[J], a1[J] - a0[J]
    rxs = r[:, 0] * s_[:, 1] - r[:, 1] * s_[:, 0]
    qp = q - p
    den = np.where(np.abs(rxs) < 1e-15, 1e-15, rxs)
    t = (qp[:, 0] * s_[:, 1] - qp[:, 1] * s_[:, 0]) / den
    u = (qp[:, 0] * r[:, 1] - qp[:, 1] * r[:, 0]) / den
    m = (np.abs(rxs) > 1e-15) & (t > 1e-9) & (t < 1 - 1e-9) & (u > 1e-9) & (u < 1 - 1e-9)
    return int(m.sum()), list(zip((I[m] + i0).tolist(), (J[m] + i0).tolist()))


def section_selfx(A, Y, j0=0, j1=None):
    """R1: rows whose section polyline (cols j0..j1) crosses itself -> {row: n_crossings}."""
    out = {}
    for r in range(A.shape[0]):
        if Y[r].max() < 0.5 and Y[r].min() > -0.5:
            continue
        n, _ = segx_count(np.stack([A[r], Y[r]], -1), j0, j1)
        if n:
            out[r] = n
    return out


def top_excess(A, Y, j_top=90, j1=200):
    """R1: per row, how much the highest point of cols j_top+1..j1 rises above the top column (m, >0 = the top is not the
    highest point)."""
    return Y[:, j_top + 1:j1].max(1) - Y[:, j_top]


# ------------------------------------------------------------------ R2 stages
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


BS_JEND_NEAR, BS_JEND_FAR = 70.0, 150.0     # the column where the smoothing ends: near rows (their crest draws the outlines 78/130/131 at cols
                                            # 75..104 and the lip top of c -3..0 draws 132) / far rows (hidden back, top and the first half of the
                                            # lip top; the lip head from col 186 on and the whole inner side draw 72 and are never smoothed).
                                            # (186 / fade 80 was tried: the far tops got sharper, rubric F02 far fold 13.9 deg)
BS_FADE_NEAR, BS_FADE_FAR = 16.0, 70.0      # columns over which the smoothing fades out (far rows: cols 80..150)
BS_Y_RATIO = 0.4                            # the height is smoothed with 0.4 sigma (the plan position with sigma)
BS_C0, BS_C1 = 1.0, 5.0                     # the smoothing end moves from the near to the far column between these c


def _sym_window_weights(c, r, sig, c_end, dc):
    hw = min(3.0 * sig, c[r] - c[0], c_end - c[r])
    s_ = min(sig, hw / 3.0)
    if s_ <= 0.02:
        return None
    w = np.exp(-0.5 * ((c - c[r]) / s_) ** 2) * dc
    w[np.abs(c - c[r]) > hw + 1e-9] = 0.0
    return w / w.sum()


def backsmooth_colweight(c):
    """(nv, nu) weight of the back smoothing: 1 up to jend - fade, 0 from jend on; jend = 70 (fade 16) for c <= 1, rising to 186 (fade 80)
    for c >= 5."""
    j = np.arange(NU, dtype=float)[None, :]
    t = smoothstep((np.asarray(c, float)[:, None] - BS_C0) / (BS_C1 - BS_C0))
    jend = BS_JEND_NEAR + (BS_JEND_FAR - BS_JEND_NEAR) * t
    fade = BS_FADE_NEAR + (BS_FADE_FAR - BS_FADE_NEAR) * t
    return smoothstep((jend - j) / fade)


def apply_backsmooth(c, A, Y, P):
    """R2 背のならし：背（近い行では頂の手前の列 70 まで、奥の行 c ≥ 5 では唇の頭の手前の列 176 まで。奥の行の背・頂・唇の上面は原画視点で
    隠れている）の点を、c の方向にガウス（σ = back_smooth(c) m、行の間隔を重みに）でならす。行の面（c 一定）は保つ（a と y だけを混ぜる）。
    唇の頭（列 186〜214）と中の面（管・前の面）は動かさない（輪郭 72 を作る縁）。"""
    sig = np.asarray(P["back_smooth"], float)
    if not np.any(sig > 0.02):
        return A, Y
    A = A.copy(); Y = Y.copy()
    c = np.asarray(c, float)
    dc = np.gradient(c)
    W = backsmooth_colweight(c)
    jm = int(np.max(np.nonzero(W.max(0) > 0)[0])) + 1
    A0, Y0 = A[:, :jm].copy(), Y[:, :jm].copy()
    c_lo, c_hi = float(c[0]), float(c[-1])
    Hr = Y.max(1)
    c_end = float(c[np.nonzero(Hr > 0.05)[0][-1]]) + 0.2 if np.any(Hr > 0.05) else c_hi
    for r in range(len(c)):
        # a symmetric window only (never reaches past the end of the wave: the end rows are not lifted by their taller neighbours);
        # the plan position a is smoothed with sigma, the height y with BS_Y_RATIO * sigma (the rows keep their own heights)
        wr = W[r, :jm]
        wa = _sym_window_weights(c, r, sig[r], c_end, dc)
        if wa is not None:
            A[r, :jm] = A0[r] + wr * (wa @ A0 - A0[r])
        wy = _sym_window_weights(c, r, BS_Y_RATIO * sig[r], c_end, dc)
        if wy is not None:
            Y[r, :jm] = Y0[r] + wr * (wy @ Y0 - Y0[r])
    return A, Y


FS_UP = (172.0, 190.0)       # far smoothing, upper side: 1 up to col 172, 0 from col 190 (the lip head and tip keep their place)
FS_LO = (212.0, 236.0)       # lower side: 0 up to col 212, 1 from col 236 on (only where far_lower(c) > 0)
FS_LO_C = (7.0, 9.0)         # the lower side (lip underside, tube, face) is smoothed only for c >= 9 (c 4..7 draw the claw bay of 72)


def farsmooth_colweight(c):
    j = np.arange(NU, dtype=float)[None, :]
    up = smoothstep((FS_UP[1] - j) / (FS_UP[1] - FS_UP[0]))
    lo = smoothstep((j - FS_LO[0]) / (FS_LO[1] - FS_LO[0])) * smoothstep((np.asarray(c, float)[:, None] - FS_LO_C[0]) / (FS_LO_C[1] - FS_LO_C[0]))
    return np.maximum(up, lo)


def apply_farsmooth(c, A, Y, P):
    """R2 奥の行の形のならし：各行の断面を「唇先（列 200）を原点、行の高さ H で割った形」にし、c の方向にガウス（σ = far_smooth(c) m、
    左右対称の窓、行の間隔の重み）で混ぜて、その行の唇先と H へ戻す。唇先の点（原画の管の輪郭 72 を描く）はそのまま。背・頂・唇の上面
    （列 0〜172）と、c ≥ 9 では唇の下面・管・前の面（列 236〜）も混ぜる。海（y < 0.3 m）の高さは変えない。"""
    sig = np.asarray(P["far_smooth"], float)
    if not np.any(sig > 0.02):
        return A, Y
    c = np.asarray(c, float)
    dc = np.gradient(c)
    Hr = Y.max(1)
    c_end = float(c[np.nonzero(Hr > 0.05)[0][-1]]) + 0.2 if np.any(Hr > 0.05) else float(c[-1])
    Hs = np.maximum(Hr, 1.5)[:, None]
    ta, ty = A[:, 200:201], Y[:, 200:201]
    U = (A - ta) / Hs; V = (Y - ty) / Hs
    W = farsmooth_colweight(c)
    bm = body_mask(Y)
    A2 = A.copy(); Y2 = Y.copy()
    for r in range(len(c)):
        if sig[r] <= 0.02:
            continue
        w = _sym_window_weights(c, r, sig[r], c_end, dc)
        if w is None:
            continue
        Us = w @ U; Vs = w @ V
        An = ta[r] + Hs[r] * Us; Yn = ty[r] + Hs[r] * Vs
        A2[r] = A[r] + W[r] * (An - A[r])
        Y2[r] = Y[r] + W[r] * bm[r] * (Yn - Y[r])
    return A2, Y2


BF_C0 = -4.0                 # back fill: the running envelope starts at the main section
BF_F = np.linspace(0.02, 0.92, 46)


def backfill_rate(c):
    """allowed forward move of the back (m per m of crest) for the back fill: 0.15 up to c +10, rising to 2.0 at c +12.5 (the end closes)"""
    return 0.15 + 1.85 * smoothstep((np.asarray(c, float) - 10.0) / 2.5)


def apply_backfill(c, A, Y, P):
    """R2 背の埋め：主断面（c −4）から奥へ c の順に、背（列 18〜90）の各高さの比 f = y/H の点の a を「それまでの行の一番後ろ + 0.15 m/m」
    より前へ出さない（くびれを後ろから埋める。奥の端 c +10〜+12.5 では前へ戻ってよい）。強さ back_fill(c)。頂の近く（f > 0.65）は
    0.9 までに 0 へ落とす（原画の輪郭 78/130/131 を作る頂は動かない）。背の後ろの海（列 0〜17）は足と一緒に動く。背を後ろへ出すだけで、削らない。"""
    wf = np.asarray(P["back_fill"], float)
    if not np.any(wf > 1e-4):
        return A, Y
    c = np.asarray(c, float)
    A = A.copy()
    H = Y.max(1)
    nv = len(c)
    aF = np.full((nv, len(BF_F)), np.nan)
    for r in range(nv):
        if H[r] < 2.0:
            continue
        y = Y[r, 18:91]; a = A[r, 18:91]
        yk = np.maximum.accumulate(y)
        aF[r] = np.interp(BF_F * H[r], yk, a)
    T = aF.copy()
    rs = [r for r in range(nv) if c[r] >= BF_C0 and np.isfinite(aF[r, 0])]
    rate = backfill_rate(c)
    for i in range(1, len(rs)):
        r0, r1 = rs[i - 1], rs[i]
        T[r1] = np.minimum(T[r0] + rate[r1] * (c[r1] - c[r0]), aF[r1])
    for r in rs:
        if wf[r] <= 1e-4:
            continue
        d = np.minimum(0.0, T[r] - aF[r])
        if not np.any(d < -1e-6):
            continue
        f = np.clip(Y[r, 18:91] / H[r], BF_F[0], BF_F[-1])
        fade = smoothstep((0.9 - f) / 0.25)
        dA = wf[r] * fade * np.interp(f, BF_F, d)
        A[r, 18:91] += dA
        # the back sea (cols 0..17) follows the foot
        A[r, :18] += dA[0] * (np.arange(18) / 18.0)
    return A, Y


# ------------------------------------------------------------------ R3 back stages (the back columns 18..90 below 0.9 H only: the columns that
# draw the painting outlines (crest 76..104 above 0.9 H, lip 103..343) never move)
BO_FADE = (0.9, 0.45)        # back_out: 1 below 0.45 H, 0 from 0.9 H (smoothstep)
BE_F = np.linspace(0.0, 0.9, 46)
BE_L, BE_TOL, BE_SIG, BE_IT = 4.0, 0.6, 1.5, 120     # back_env: chord half-length (m), allowed forward notch (m), smoothing of the fill along c (m), iterations
BE_YMAX = 8.0                # back_env: the plan lines are filled up to this absolute height (the judges' notch at y 3 / 6 m)
BE_PROF = (0.95, 0.55)       # (first try, not used: a smoothstep profile made new S folds in the back)
BE_YREF, BE_FHI, BE_W = 4.5, 0.88, 0.03   # back_env: the shear equals the fill at 4.5 m and is 0 from 0.88 H (softplus rounding 0.03 H);
                                          # 0.95 moved the shoulder crest (row c -8, col 80, the worst point of the painting outline 130: 3.83 -> 3.87 px)
BE_C = (-19.0, 14.6)         # the dense rows (0.2 m) the envelope is computed on


def _back_heights(A, Y, r, F):
    """a of the back (cols 18..90) at the heights F * H (running maximum of y, so a small dip never folds the lookup)."""
    H = Y[r].max()
    y = Y[r, 18:91]; a = A[r, 18:91]
    yk = np.maximum.accumulate(y)
    yk = yk + 1e-9 * np.arange(len(yk))
    return np.interp(F * H, yk, a)


def _apply_back_da(A, Y, r, F, d, fade_hi=0.9, fade_w=0.2):
    """move the back points of row r horizontally by d(f) (m, f = y / H on the grid F), fading to 0 at fade_hi; the back sea follows the foot."""
    H = Y[r].max()
    f = np.clip(Y[r, 18:91] / max(H, 1e-9), 0.0, 1.0)
    fade = smoothstep((fade_hi - f) / fade_w)
    top = int(np.argmax(Y[r, 18:91]))
    fade[top:] = 0.0                                   # never past the crest top
    dA = fade * np.interp(f, F, d)
    A[r, 18:91] += dA
    A[r, :18] += dA[0] * (np.arange(18) / 18.0)


def apply_backout(c, A, Y, P):
    """R3 背を外へ：背の列（18〜頂、f < 0.9）を水平に後ろ（− a）へ back_out(c) m。0.45 H より下は全部、0.9 H で 0 へ。低い行（H < 2 m）は動かない。"""
    d = np.asarray(P["back_out"], float)
    if not np.any(d > 1e-4):
        return A, Y
    A = A.copy()
    H = Y.max(1)
    F = np.linspace(0.0, 1.0, 51)
    for r in range(len(c)):
        if d[r] <= 1e-4 or H[r] < 2.0:
            continue
        prof = -d[r] * smoothstep((BO_FADE[0] - F) / (BO_FADE[0] - BO_FADE[1]))
        _apply_back_da(A, Y, r, F, prof, fade_hi=0.95, fade_w=0.05)
    return A, Y


def backenv_fill(c, A, Y):
    """-> (rows, need (n_rows,) m <= 0): the plan line a_y(c) of the back at every absolute height y (0.5 m steps, up to 0.85 H of the row
    and BE_YMAX) over the dense rows, filled outward (- a) until no point is more than BE_TOL in front of the chord of its neighbours
    +-BE_L m (the judges' notch); per row the largest fill below BE_YMAX, smoothed along c (sigma BE_SIG)."""
    c = np.asarray(c, float)
    H = Y.max(1)
    rows = np.nonzero((c >= BE_C[0]) & (c <= BE_C[1]) & (H >= 2.0))[0]
    if len(rows) < 10:
        return rows, np.zeros(len(rows))
    cc = c[rows]
    Yg = np.arange(0.5, BE_YMAX + 1e-6, 0.5)
    V0 = np.full((len(rows), len(Yg)), np.nan)
    for i, r in enumerate(rows):
        ok = Yg <= 0.85 * H[r]
        if ok.any():
            V0[i, ok] = _back_heights(A, Y, r, Yg[ok] / H[r])
    V = V0.copy()
    for k in range(len(Yg)):
        m = np.isfinite(V[:, k])
        if m.sum() < 10:
            continue
        ci = cc[m]; v = V[m, k].copy()
        okc = ((ci - BE_L) >= ci[0]) & ((ci + BE_L) <= ci[-1])
        for _ in range(BE_IT):
            ch = 0.5 * (np.interp(ci - BE_L, ci, v) + np.interp(ci + BE_L, ci, v)) + BE_TOL
            vn = np.where(okc, np.minimum(v, ch), v)
            done = np.max(np.abs(vn - v)) < 1e-4
            v = vn
            if done:
                break
        V[m, k] = v
    d = np.where(np.isfinite(V), V - V0, 0.0)
    need = d.min(1)
    dc = float(np.median(np.diff(cc)))
    kk = _gk(BE_SIG / dc)
    r_ = len(kk) // 2
    need = np.convolve(np.pad(need, (r_, r_), mode="edge"), kk, "valid")
    return rows, np.minimum(need, 0.0)


def apply_backenv(c, A, Y, P):
    """R3 背のくびれを埋める：backenv_fill の行ごとの量 × back_env(c) だけ、背の点を水平に外へ。量は BE_PROF（f = y/H が BE_PROF[1] より下で全部、
    BE_PROF[0] で 0）の形で高さに沿ってなめらかに（背の断面に新しい S の折れを作らない）。頂は動かない。"""
    w = np.asarray(P["back_env"], float)
    if not np.any(w > 1e-4):
        return A, Y
    A = A.copy()
    rows, need = backenv_fill(c, A, Y)
    F = np.linspace(0.0, 1.0, 201)
    H = Y.max(1)
    for i, r in enumerate(rows):
        if w[r] <= 1e-4 or need[i] > -1e-4:
            continue
        # a shear of the back (the move is linear in the height, so the section keeps its convex/concave parts: no new S fold), equal to the
        # fill at the reference height BE_YREF, rounded off to 0 at BE_FHI of the row height (softplus of width BE_W)
        fr = min(BE_YREF / H[r], 0.5 * BE_FHI)
        sp = BE_W * np.logaddexp(0.0, (BE_FHI - F) / BE_W)
        prof = sp / (BE_W * np.logaddexp(0.0, (BE_FHI - fr) / BE_W))
        _apply_back_da(A, Y, r, F, w[r] * need[i] * prof, fade_hi=0.995, fade_w=0.01)
    return A, Y


BD_SIG = 1.5                 # back_depth: smoothing of the fill along c (m)
BT_C0 = 9.0                  # back_tail: the row whose back shape the far tail copies
BT_RAMP = 1.5                # back_tail: the copy fades in over c BT_C0 .. BT_C0 + BT_RAMP
BT_J = (70.0, 84.0)          # back_tail: all of the back up to col 70, fading to 0 at col 84 (the crest top col 90 and the lip never move)


def apply_backtail(c, A, Y, P):
    """R3 奥の端の背を相似に：c ≥ BT_C0 の行の背（列 0〜84）を、BT_C0 の行の背を（頂からの水平の距離と高さの両方で）その行の高さの比で
    縮めた形へ back_tail(c) の強さで寄せる。奥の端の背が、頂の線（a_top(c)、H(c)）に沿うなめらかな錐のようになる。背の後ろの海（列 0〜17）は
    足から 40 m のまま。"""
    wt = np.asarray(P["back_tail"], float)
    if not np.any(wt > 1e-4):
        return A, Y
    c = np.asarray(c, float)
    A = A.copy(); Y = Y.copy()
    H = Y.max(1)
    r0 = int(np.argmin(np.abs(c - BT_C0)))
    H0_ = max(H[r0], 1e-6)
    J1 = int(BT_J[1]) + 1
    U = (A[r0, :J1] - A[r0, 90]) / H0_
    V = Y[r0, :J1] / H0_
    j = np.arange(J1, dtype=float)
    wcol = smoothstep((BT_J[1] - j) / (BT_J[1] - BT_J[0]))
    wcol[:18] = 1.0
    for r in range(len(c)):
        wr = wt[r] * smoothstep((c[r] - BT_C0) / BT_RAMP)
        if wr <= 1e-4 or H[r] < 1e-3:
            continue
        At = A[r, 90] + U * H[r]
        Yt = V * H[r]
        At[:18] = At[18] - 40.0 * (1.0 - np.arange(18) / 18.0)         # the back sea: 40 m behind the foot, flat
        Yt[:18] = 0.0
        w = wr * wcol
        A[r, :J1] += w * (At - A[r, :J1])
        Y[r, :J1] += w * (Yt - Y[r, :J1])
    return A, Y


BD_FHI = 0.88                # back_depth: the shear is 0 from 0.88 H (the shoulder crest columns 76..104 that draw the painting outlines 78/130 stay)


def _shear_prof(F, fref, fhi=None):
    """the height profile of the R3 back shears: 1 at the height ratio fref, linear in the height (keeps the section's convex/concave parts),
    rounded off to 0 at fhi (default BE_FHI; softplus of width BE_W)."""
    fhi = BE_FHI if fhi is None else fhi
    sp = BE_W * np.logaddexp(0.0, (fhi - F) / BE_W)
    return sp / (BE_W * np.logaddexp(0.0, (fhi - fref) / BE_W))


def apply_backdepth(c, A, Y, P):
    """R3 背の奥行きの下限：半分の高さ（0.5 H）で、頂（列 90）から背までの水平の距離が back_depth(c) × H より浅い行は、その差だけ背を外へ
    （高さに比例するずらし、頂は動かない）。足りない量は c の方向にならす（σ BD_SIG）。外へ足すだけで、削らない。"""
    D_ = np.asarray(P["back_depth"], float)
    if not np.any(D_ > 1e-4):
        return A, Y
    A = A.copy()
    c = np.asarray(c, float)
    H = Y.max(1)
    need = np.zeros(len(c))
    for r in range(len(c)):
        if D_[r] <= 1e-4 or H[r] < 2.0:
            continue
        a50 = _back_heights(A, Y, r, np.array([0.5]))[0]
        need[r] = min(0.0, (A[r, 90] - D_[r] * H[r]) - a50)
    # smoothing along c by distance (the rows are 0.2 m apart from c -19 on and wider on the near tail: an index convolution over the dense
    # rows only left a slope jump at c -19, a visible vertical crease on the back)
    dcw = np.gradient(c)
    Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / BD_SIG) ** 2) * dcw[None, :]
    need = np.minimum((Wm @ need) / Wm.sum(1), 0.0)
    need *= smoothstep(D_ / 0.1)            # the smoothing never spreads the fill into rows where the ramp is 0
    F = np.linspace(0.0, 1.0, 201)
    prof = _shear_prof(F, 0.5, BD_FHI)
    for r in range(len(c)):
        if need[r] > -1e-4 or H[r] < 2.0:
            continue
        _apply_back_da(A, Y, r, F, need[r] * prof, fade_hi=0.995, fade_w=0.01)
    return A, Y


def apply_ledge_depth(c, A, Y, P):
    """R3 b 区域の房：稜（ledge_pos のまわり、ledge_width の幅）を、原画カメラの視線（断面の面へ写した向き）へ ledge_lobe_depth(c) m 動かす。
    唇先（列 190〜）と海は動かない。"""
    dd = np.asarray(P["ledge_lobe_depth"], float) if "ledge_lobe_depth" in P else None
    if dd is None or not np.any(np.abs(dd) > 1e-6):
        return A, Y
    A = A.copy(); Y = Y.copy()
    j = np.arange(NU, dtype=float)
    u = (j - 90.0) / 110.0
    X = world_u(c, A, Y)
    for r in range(len(c)):
        if abs(dd[r]) < 1e-6:
            continue
        pos = float(P["ledge_pos"][r]); wd = max(float(P["ledge_width"][r]), 0.03)
        prof = dd[r] * np.exp(-0.5 * ((u - pos) / (1.3 * wd)) ** 2) * band_weight(92, 196, 6) * body_mask(Y[r])
        v = X[r] - CAM_POS_U
        va = v @ FRAME_T; vy = v[:, 1]
        L = np.maximum(np.hypot(va, vy), 1e-9)
        A[r] += prof * va / L; Y[r] += prof * vy / L
    return A, Y


LS_J = (140.0, 186.0, 214.0, 268.0)          # lip-head shift: 0 at col 140 -> 1 from 186 to 214 -> 0 at 268


def lipshift_weight():
    j = np.arange(NU, dtype=float)
    a, b, c_, d = LS_J
    return smoothstep((j - a) / (b - a)) * smoothstep((d - j) / (d - c_))


def tip_normals(A, Y, jt=200):
    """unit outward normal of each row at the lip tip (the section normal of column jt, pointing out of the tip cap)."""
    ta = A[:, jt + 1] - A[:, jt - 1]; ty = Y[:, jt + 1] - Y[:, jt - 1]
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    return np.stack([-ty / L, ta / L], -1)


def apply_lipshift(c, A, Y, P):
    """R2 唇の頭の移動：唇の頭（列 186〜214）を唇先の法線の向きへ lip_shift(c) m、鉛直に下へ lip_drop(c) m だけまとめて動かし、
    列 140 と 268 までなめらかに戻す。
    唇の下の輪郭（72）を作る縁の形は保ったまま位置だけを動かす（細い帯の法線の移動のような折れを作らない）。海と低い行は動かない。"""
    s_ = np.asarray(P["lip_shift"], float)
    dr = np.asarray(P["lip_drop"], float) if "lip_drop" in P else np.zeros_like(s_)
    if not (np.any(np.abs(s_) > 1e-7) or np.any(np.abs(dr) > 1e-7)):
        return A, Y
    A = A.copy(); Y = Y.copy()
    n = tip_normals(A, Y)
    # never on the low end rows whose curl has faded into a swell (the same fade as fade_small)
    Hr = Y.max(1)
    wc = smoothstep((Hr - LS_FADE_FAR[0]) / (LS_FADE_FAR[1] - LS_FADE_FAR[0]))        # R3
    cc_ = np.asarray(c, float)       # R3: the same fade at both ends (the lip-head keys are 0 on the near tail anyway)
    s_ = s_ * wc; dr = dr * wc
    w = lipshift_weight()[None, :] * body_mask(Y)
    A += s_[:, None] * w * n[:, 0:1]
    Y += s_[:, None] * w * n[:, 1:2] - dr[:, None] * w
    return A, Y


CL_J = (20.0, 60.0, 96.0, 186.0)             # crest_lift: 0 at col 20 -> 1 from 60 to 96 -> 0 at col 186 (the lip head 186.. never moves); (24, 62, 118, 176) made a 15.6 deg single-vertex fold at the far tops


def crestlift_weight():
    j = np.arange(NU, dtype=float)
    a, b, c_, d = CL_J
    return smoothstep((j - a) / (b - a)) * smoothstep((d - j) / (d - c_))


def apply_crestlift(c, A, Y, P):
    """R3 頂の持ち上げ：行の頂のまわり（列 24〜176、列 62〜118 で全部）を鉛直に crest_lift(c) m 上げる。唇の頭と唇先（列 186〜、原画の輪郭 72 を描く）、
    足と海は動かない。背は上の方ほど高くなり、唇の上面は頂から唇の頭へ長く下る（奥の行の唇の上面が主断面と同じように見える）。"""
    L = np.asarray(P["crest_lift"], float) if "crest_lift" in P else None
    if L is None or not np.any(np.abs(L) > 1e-6):
        return A, Y
    Y = Y.copy()
    w = crestlift_weight()
    for r in range(len(c)):
        if abs(L[r]) < 1e-6:
            continue
        # scaled by the row's own height ratio at each column (the foot and the sea stay put: y / H weight)
        H = max(Y[r].max(), 1e-6)
        f = np.clip(Y[r] / H, 0.0, 1.0)
        Y[r] += L[r] * w * smoothstep(f / 0.5)
    return A, Y


LU_J = (200.0, 205.0, 214.0, 236.0)          # lip_under: 0 at the tip apex col 200 -> 1 from 205 to 214 -> 0 at 236


def lipunder_weight():
    j = np.arange(NU, dtype=float)
    a, b, c_, d = LU_J
    return smoothstep((j - a) / (b - a)) * smoothstep((d - j) / (d - c_))


def apply_lipunder(c, A, Y, P):
    """R3 唇の頭の下面の厚み：唇先のすぐ後ろの下面（列 204〜214、列 200 と 236 で 0）を断面の法線の向き（外 = 管の中の空気の側、+ = 唇が下へ厚く）へ
    lip_under(c) m。唇先の点（列 200）と唇の上面は動かない（唇の縁の線は波打たない）。低い奥の行ではなめらかに 0。"""
    u = np.asarray(P["lip_under"], float) if "lip_under" in P else None
    if u is None or not np.any(np.abs(u) > 1e-7):
        return A, Y
    A = A.copy(); Y = Y.copy()
    Hr = Y.max(1)
    wc = smoothstep((Hr - LS_FADE_FAR[0]) / (LS_FADE_FAR[1] - LS_FADE_FAR[0]))
    w = lipunder_weight()
    for r in range(len(c)):
        if abs(u[r] * wc[r]) < 1e-7:
            continue
        n = row_normals(A[r], Y[r])
        dd = u[r] * wc[r] * w * body_mask(Y[r])
        A[r] += dd * n[:, 0]; Y[r] += dd * n[:, 1]
    return A, Y


CROWN_C = (98.0, 99.0)         # the crown applies from c >= 3 (ramp from c = 1): the far rows (their lip top is hidden in the painting view)
CROWN_M = 0.035               # the lip top stays at least 3.5 % of the row height below the crest top (reached 25 columns after the top)


def apply_crown(c, A, Y):
    """R2 頂の冠：奥の行（c ≥ 3）では、唇の上面（列 92〜196）が頂（列 90）より行の高さの 3.5% 以上低い（やわらかい上限）。
    奥の行で唇が頂の高さの台になり頂の列が飛ぶ（上から見た頂の線が折れて見える、F10）ことと、低い行で唇の頭が頂より上がることを防ぐ。"""
    c = np.asarray(c, float)
    t = smoothstep((c - CROWN_C[0]) / (CROWN_C[1] - CROWN_C[0]))
    if not np.any(t > 0):
        return A, Y
    Y = Y.copy()
    j = np.arange(92, 197)
    m = CROWN_M * smoothstep((j - 90.0) / 25.0)
    for r in np.nonzero(t > 0)[0]:
        H = Y[r, 90]
        if H < 0.5:
            continue
        lim = H - m * H
        k = max(0.02 * H, 0.02)
        y = Y[r, j]
        ys = -k * np.logaddexp(-y / k, -lim / k)            # soft minimum(y, lim)
        # only where the lip is near the limit (elsewhere the soft minimum would pull the whole lip down by a few mm)
        w = smoothstep((y - (lim - 4 * k)) / (4 * k))
        Y[r, j] = y + t[r] * w * (ys - y)
    return A, Y


def apply_backshape(c, A, Y, P):
    """R3 背の形の節点（Houdini の back_shape）：背を外へ → 背の埋め（R2、0）→ 背のならし → 奥の端の背を相似に → 背の奥行きの下限 → 背のくびれを埋める（最後の背の平面の線で測る）。"""
    A, Y = apply_backout(c, A, Y, P)
    A, Y = apply_backfill(c, A, Y, P)
    A, Y = apply_backsmooth(c, A, Y, P)
    A, Y = apply_backtail(c, A, Y, P)         # the far tail as similar copies of one row's back
    A, Y = apply_backdepth(c, A, Y, P)        # the depth floor (lemon: rows much thinner than their neighbours), then
    A, Y = apply_backenv(c, A, Y, P)          # last: the waist fill is computed on the final back (the plan line the judges measure)
    return A, Y


def apply_bregion(c, A, Y, P):
    """b 区域の節点（Houdini の bregion_ledge）：稜と谷（R2）→ 房を視線の向きへ（R3）。"""
    A, Y = apply_ledge(c, A, Y, P)
    A, Y = apply_ledge_depth(c, A, Y, P)
    return A, Y


def build_pre_edges(design, c=None):
    """R3: everything but the graze-weighted side-edge strips (the body the strips are solved on)."""
    c, A, Y, P = build_base(design, c)
    A, Y = apply_farsmooth(c, A, Y, P)
    A, Y = apply_crestlift(c, A, Y, P)
    A, Y = apply_backshape(c, A, Y, P)
    A, Y = apply_lipprof(c, A, Y, P)
    A, Y = apply_bregion(c, A, Y, P)
    A, Y = apply_lipshift(c, A, Y, P)
    A, Y = apply_lipunder(c, A, Y, P)
    A, Y = apply_crown(c, A, Y)
    return c, A, Y, P


def build(design, c=None):
    c, A, Y, P = build_pre_edges(design, c)
    A, Y = apply_edges(c, A, Y, P)
    return c, A, Y, P
