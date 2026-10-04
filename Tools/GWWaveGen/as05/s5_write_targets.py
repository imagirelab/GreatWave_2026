# -*- coding: utf-8 -*-
"""美術の見本05 の調べ（Q33）：測れる目標 targets.json を書く。
入力（どれも Git 対象外の Unity/Build/Polish/sample05/study/ と sample04/ の測り）：baseline_sample04.json（s5_targets.py baseline）、
diag.json（s5_diag.py）、s5_obj_numbers.json（s5_obj.py。参照モデルの数だけ）、tmp/ray_heights.json（原画の射線の高さ）、sample04/rules_check.json。
目標の値は進行役の既定（利用者の言葉ではない）。美術が届いたかは利用者が決める（Q29・Q30）。
使い方：py -3.10 -B Tools/GWWaveGen/as05/s5_write_targets.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_common as S  # noqa: E402


def jl(p):
    return json.load(open(p, encoding="utf-8"))


# 進行役が読んだ原画の点（原画の画素）。L3 = ③ の爪の群れの上の縁、L2 = ② の爪の群れの上の縁、face_top = 藍の面の上の縁
RAY_POINTS = {"L3_crest_230_1080": (230, 1080), "L3_crest_380_1090": (380, 1090), "L3_crest_500_1110": (500, 1110),
              "L3_face_top_300_1180": (300, 1180), "L3_face_top_450_1170": (450, 1170),
              "L2_crest_780_950": (780, 950), "L2_crest_930_930": (930, 930), "L2_crest_1180_930": (1180, 930),
              "L2_face_top_900_1250": (900, 1250), "boat_bow_tip_115_1235": (115, 1235)}


def ray_heights():
    import numpy as np
    cam = S.painting_cam()
    out = {}
    for k, (x, y) in RAY_POINTS.items():
        d = S.S4.ref_to_disp(np.array([x, y], float))
        D = np.asarray(cam.ray(np.array(d[0]), np.array(d[1])), float).reshape(-1)[-3:]
        D = D / np.linalg.norm(D)
        rows = []
        for dist in (36, 40, 44, 48, 52):
            q = S.K.sec((S.K.CAM_POS_U + dist * D)[None])[0]
            rows.append({"dist_m": dist, "a": S.rnd(q[0], 2), "y_over_H0": S.rnd(q[1] / S.H0), "c": S.rnd(q[2], 2)})
        out[k] = rows
    return out


def main():
    B = jl(S.OUT + "/baseline_sample04.json")
    D = jl(S.OUT + "/diag.json")
    R = jl(S.OUT + "/s5_obj_numbers.json")
    RC = jl(S.P4 + "/rules_check.json")["rules"]
    g = B["geometry"]["layers"]
    ap = B["appearance"]
    sep = B["separation_summary"]
    pc = B["painting_label_consistency"]
    ref = {p["c"]: p for p in R["peaks"]}
    ref_shoulder = [p for p in R["peaks"] if p["prominence_m"] != "global_max" and -11 <= p["c"] <= -9 and p["y"] > 12]
    ref_low = [p for p in R["peaks"] if p["prominence_m"] != "global_max" and -12 <= p["c"] <= -10 and 5 < p["y"] < 8]
    rs = ref_shoulder[0] if ref_shoulder else None
    rl = ref_low[0] if ref_low else None
    s10 = RC["S10"]["AS04_union_hero_wave4"]
    T = []

    def add(id_, rule, metric, op, thr, base, why, ref_v=None, kind="must"):
        T.append({"id": id_, "kind": kind, "rule_ja": rule, "metric": metric, "pass_if": {"op": op, "value": thr},
                  "baseline_sample04": base, "reference_model_numbers": ref_v, "why_ja": why})

    # ---------------------------------------------------------------- L：層の形
    add("L1-2", "② b区域に自分の頂（上から見た高さの場の峰）があり、原画視点で ② の多角形（±40 原画画素）に入る。峰の突出（自分より高い所への道の最も高い鞍まで）",
        "geometry.layers.2.prominence_m", ">=", 0.6, g["2"]["prominence_m"] if g.get("2") else None,
        "見本04 の ② は唇の上の 0.39 m の小さな瘤で、鞍は横（唇に沿って c の向き）にある。前の層として読むには自分の頂の線が要る。参照の ② の肩の縁は 0.33 m（肩の段）、"
        "前の低い房は 1.4 m。② は肩でよいが、見本04 より少しはっきりさせる",
        {"shoulder_c_-9.75": rs and {"prominence_m": rs["prominence_m"], "y_over_Href": S.rnd(rs["y"] / R["H_ref_m"])}})
    add("L1-3", "③ 最左側の小区域に自分の頂があり、原画視点で ③ の多角形（±40 原画画素）に入る。峰の突出", "geometry.layers.3.prominence_m", ">=", 1.0,
        None, "見本04 は ③ の多角形に入る峰がない（③ に当たる形は ② と同じ一本の唇の左の部分と、その下の巻きの内の面）。参照の前の低い房は突出 1.4 m",
        rl and {"prominence_m": rl["prominence_m"], "y_over_Href": S.rnd(rl["y"] / R["H_ref_m"]), "crest_ahead_of_saddle_a_m": rl["crest_ahead_of_saddle_a_m"]})
    add("L2-2", "② の峰は鞍より前（a の向き、原画のカメラの側）にある：峰の a − 鞍の a", "geometry.layers.2.crest_ahead_of_saddle_a_m", ">=", 1.5,
        g["2"]["crest_ahead_of_saddle_a_m"] if g.get("2") else None,
        "見本04 は鞍が横（−0.25 m）で、② は唇に沿って ① とつながる一枚の棚に見える。鞍（引っ込み）が後ろにあれば、② は主の体の前へ出た層として読める",
        rs and {"crest_ahead_of_saddle_a_m": rs["crest_ahead_of_saddle_a_m"]})
    add("L2-3", "③ の峰は鞍より前にある：峰の a − 鞍の a", "geometry.layers.3.crest_ahead_of_saddle_a_m", ">=", 2.0, None,
        "③ は ② の下の前へ出た小さな層（参照の前の低い房は 2.75 m 前）", rl and {"crest_ahead_of_saddle_a_m": rl["crest_ahead_of_saddle_a_m"]})
    add("L3-2", "② の頂の高さ（H0 = 20.75 m）", "geometry.layers.2.crest.y_over_H0", "between", [0.48, 0.60], g["2"]["crest"]["y_over_H0"] if g.get("2") else None,
        "原画の ② の爪の群れの上の縁（原画の y 930〜1010）の射線は、カメラから 44〜52 m で 0.48〜0.56 H0。見本04 の調べ S の層の計画は 0.52〜0.60。"
        "0.6 H を越えると峰に沿う 0.6 H の帯（S10）が左へ延びる")
    add("L3-3", "③ の頂の高さ（奥行きと組。原画視点で ③ の爪の群れの上の縁 y 1080〜1110 に写る高さは、カメラから 40 m で 0.40、44 m で 0.425、48 m で 0.45、52 m で 0.476 H0）",
        "geometry.layers.3.crest.y_over_H0", "between", [0.36, 0.48], None,
        "③ の頂は L1-3 で ③ の多角形（±60 画素）に写ることを求めるので、高さは奥行きで決まる。上の端は空の射線の禁止域（a 0〜14 m で c −22〜−14 は 0.41〜0.55 H0）と、"
        "同じ c の主の体の頂より低いこと（S4）。下の端は船（boat_left）と手前の海の射線の禁止域の上の端（行 c −24〜−12 で 0.29〜0.37 H0）")
    add("L3-23", "② と ③ の頂の高さの差", "geometry.steps.H2_minus_H3_over_H0", ">=", 0.10, None,
        "見本04 の c の帯の頂の差は 0.093 H0 で、側面から段に見えなかった。③ は ② より目に見えて低い")
    add("L4-12", "原画のカメラからの奥行き：② の峰は ① の峰より手前", "geometry.steps.dist1_minus_dist2_m", ">=", 5.0, B["geometry"]["steps"].get("dist1_minus_dist2_m"),
        "原画で ② の爪は ① の面（藍）の前に重なる（② が前）")
    add("L4-23", "原画のカメラからの奥行き：③ の峰は ② の峰より手前", "geometry.steps.dist2_minus_dist3_m", ">=", 2.0, None,
        "③ は ② の左下の前の小さな層。見本03 の形では ③ が ② より奥（逆の順）、見本04 の c の帯でも 1.65 m しか手前でない。やり方 A（③ を 40〜44 m）なら 4 m 以上、やり方 B（段、③ の縁 46〜50 m）でも 2 m は取れる")
    add("L5-2", "② の前の縁の下の引っ込み（峰の c ± 0.5 m で、前の縁から 0.08〜0.25 H0 下の面の前の端が、前の縁より後ろへ何 m か）", "geometry.layers.2.undercut_m", ">=", 2.0,
        g["2"].get("undercut_m") if g.get("2") else None, "各層の下に藍の面（または影の引っ込み）があると、上の層の白い頂と下の層の白い頂の間に藍の帯が見え、色が一つのクリーム色の塊にならない")
    add("L5-3", "③ の前の縁の下の引っ込み（小さな巻き）", "geometry.layers.3.undercut_m", ">=", 1.5, None,
        "③ の頂の下の面は、船（boat_left）と手前の海の射線の禁止域（0.31〜0.36 H0 より下）より後ろへ引っ込む必要がある。小さな巻きで面を後ろへ返す")
    add("L5-lip", "②・③ の唇（前の縁 − 峰の a）は長い舌にしない", "geometry.layers.{2,3}.lip_ahead_of_crest_m", "<=", 5.0,
        {"2": g["2"].get("lip_ahead_of_crest_m") if g.get("2") else None, "section_rows_c_-20_-14_lip_ahead_of_ridge_m": [7.09, 8.5]},
        "見本04 の左の部分（c −21〜−13）は、頂の線（a ≈ 0）から 7〜8.5 m 前へ延びる平らな舌で、主の巻きを小さく写したように一枚の棚に読めた。参照の ② の唇は頂より 1〜2 m 前",
        kind="should")
    add("L6-sep", "15 視点（左右の側面・真上・回り台 12 方位）で、隣の層の組 ①②・②③ が両方見える視点のうち、分かれて読める視点の割合（見本04 の S11 と同じ決めごと。"
        "分かれる＝深さの跳びなしに触れていない、かつ遮る縁 20 画素以上か、前の面が別の塊）", "separation_summary.{1-2,2-3}.separated_share", ">=", 0.5,
        {"1-2": sep["1-2"]["separated_share"], "2-3": sep["2-3"]["separated_share"]},
        "見本04 の S11 の代わりの測り。層の印は作り手が付ける（下の L6-label で原画の区域と合っているかを確かめる）")
    add("L6-label", "原画視点で、区域 k の多角形の中の面（主役波と足したメッシュ）の画素のうち、層 k の印の割合", "painting_label_consistency.{r1,r2,r3}.share_label_k", ">=",
        {"r1": 0.5, "r2": 0.6, "r3": 0.6}, {k: pc[k]["share_label_k"] for k in pc},
        "見本04 の S11 は c の帯（② −15.5〜−11.5・③ −23〜−17）に印を付けたが、原画の ③ の多角形の中で ③ の印は 12.6% しかなく（多くは ② の帯と巻きの内の面）、"
        "測っていた ③ は利用者の ③ ではなかった。層の印は原画の区域と合わせる")
    add("L6-vis3", "③ が 15 視点のうち 2,000 画素以上見える視点の数", "separation_summary.layer3_views_with_2000px", ">=", 8, sep["layer3_views_with_2000px"],
        "③ を小さくしすぎない", kind="should")
    # ---------------------------------------------------------------- P：原画視点の見え方
    r3, r2 = ap["r3"], ap["r2"]
    add("P1-top", "③ の上の帯（原画の y 1110〜1300）：白と水色の頂（藍は少し）", "appearance.r3.top_1110_1300.candidate",
        "ranges", {"white+mizuiro": [0.55, 0.85], "mizuiro": [0.10, 1.0], "indigo": [0.10, 0.40]},
        r3["top_1110_1300"]["candidate"], "原画は 藍 %.2f・水色 %.2f・白 %.2f。見本04 はクリーム色 0.90 で、② と左の白と一つの塊になっていた（水色 0.006）" % (
            r3["top_1110_1300"]["painting"]["indigo"], r3["top_1110_1300"]["painting"]["mizuiro"], r3["top_1110_1300"]["painting"]["white"]))
    add("P1-mid", "③ の中の帯（原画の y 1300〜1560）：藍の面（爪の白が少し載る）", "appearance.r3.mid_1300_1560.candidate", "ranges",
        {"indigo": [0.40, 0.80], "white+mizuiro": [0.20, 0.60]}, r3["mid_1300_1560"]["candidate"],
        "原画は 藍 %.2f・水色 %.2f・白 %.2f（船 %.2f）" % (r3["mid_1300_1560"]["painting"]["indigo"], r3["mid_1300_1560"]["painting"]["mizuiro"],
                                                  r3["mid_1300_1560"]["painting"]["white"], r3["mid_1300_1560"]["painting"]["boat"]))
    add("P1-cells", "③ の多角形の上と中（y 1110〜1560）の 8 画素の升ごとの藍の割合が、原画と合う", "appearance.r3.cell_agreement_indigo", "ranges",
        {"indigo_share_mae": [0.0, 0.28], "pearson_r": [0.45, 1.0]}, r3["cell_agreement_indigo"], "白の頂の上に藍の面がある並びが、原画のある所に出ているか")
    add("P2-top", "② の上の帯（原画の y 880〜1180）：白と水色の爪の群れが、主の藍の面の手前に出る", "appearance.r2.top_880_1180.candidate", "ranges",
        {"indigo": [0.10, 0.40], "mizuiro": [0.10, 1.0]}, r2["top_880_1180"]["candidate"],
        "原画は 藍 %.2f・水色 %.2f・白 %.2f。見本04 は ② の多角形の 53%% が巻きの奥の内の面（藍、カメラから 62 m）で、② 自身の面は左の一部だけ" % (
            r2["top_880_1180"]["painting"]["indigo"], r2["top_880_1180"]["painting"]["mizuiro"], r2["top_880_1180"]["painting"]["white"]))
    add("P2-cells", "② の多角形の 8 画素の升ごとの藍の割合が原画と合う", "appearance.r2.cell_agreement_indigo", "ranges",
        {"indigo_share_mae": [0.0, 0.28], "pearson_r": [0.5, 1.0]}, r2["cell_agreement_indigo"], "", kind="should")
    # ---------------------------------------------------------------- K：守ること
    gt = RC["G2"]["gates"]
    K = [
        {"id": "K-G2", "rule_ja": "原画視点の関門（主役波・wave4・足したメッシュを合わせた輪郭）：78・130・131 ≤ 4 px（定義どおり）、132 σ12・72 σ12 p95 ≤ 4 px",
         "tool": "Tools/GWWaveGen/as04/asm4_rules.py の g2（as02_gates.py の sweep）", "pass_if": {"78": 4.0, "130": 4.0, "131": 4.0, "132_s12": 4.0, "72_s12_p95": 4.0},
         "baseline_sample04": {k: v["claws"] for k, v in gt.items()}},
        {"id": "K-S8", "rule_ja": "利用者の黄色の線（Q32-3）の中は内の面の弧の上：射線の最初の当たりの内の面の線からの距離 p95 ≤ 0.15 m、内の面に当たる割合 ≥ 0.95。"
         "② の頂は原画視点でこの輪の下の縁（原画の (948,803)→(1031,852)→(1214,939)→(1399,1006)）より上へ出さない",
         "tool": "asm4_rules.s8（shape_common.bulge_metric）", "pass_if": {"dev_p95_m": 0.15, "first_hit_inner_share_min": 0.95},
         "baseline_sample04": {"dev_p95_m": RC["S8"]["AS04"]["dev_from_inner_face_m"]["p95"], "first_hit_inner_share": RC["S8"]["AS04"]["first_hit_inner_face_share"]}},
        {"id": "K-S9", "rule_ja": "④（区間 78 の x < 360）の真値の点の 95% 以上を wave4 が作る。左の白は低いまま（白の最も左の c ≥ −23.4 m、c −17.2〜−12.6 m の白の頂を上げない）。"
         "③ の白い頂は低い（L3-3）ので、この規則と同じ向き", "tool": "asm4_rules.s9",
         "pass_if": {"region4_wave4_share_min": 0.95, "leftmost_white_c_min_m": -23.4},
         "baseline_sample04": {"region4_wave4_share": RC["S9"]["per_segment"]["78"]["region4_x_lt_360"]["owner_share"]["wave4"], "leftmost_white_c_m": -23.38}},
        {"id": "K-S4", "rule_ja": "背は一つの山：合わせた頂の高さ H(c) のへこみ 0（c ≥ −14 の窓）・全体 0.07 m 以下、後ろからの輪郭のへこみ 1 px まで、背の等高線のへこみ 0.10 m まで。"
         "② と ③ の峰の突出は、主の体の高い所（背の頂の線）が同じ c で峰より高いことで作り、H(c) に谷を作らない", "tool": "asm4_rules.s4",
         "pass_if": {"H_dip_union_c_ge_-14_m": 0.0, "H_dip_union_all_m_max": 0.07, "silhouette_dip_px_max": 1.0, "back_contour_dip_m_max": 0.10},
         "baseline_sample04": RC["S4"]["checks"]},
        {"id": "K-S10", "rule_ja": "峰に沿う長さ：0.6〜0.9 H の帯（いちばん高い峰）の幅は見本04 と同じ（±0.25 m）。低い帯（0.1〜0.5 H）は見本04 より長くしない（+0.5 m まで）。H = 20.27 m",
         "tool": "asm4_rules.s10（bands_union）", "pass_if": {"high_bands_equal_to_sample04_tol_m": 0.25, "low_bands_max_increase_m": 0.5},
         "baseline_sample04_union_widths_m": {k: v["width_m"] for k, v in s10.items()}},
        {"id": "K-T5", "rule_ja": "波の本体の面に白い粒を描かない：原画視点の爪なしの描画で、主役波の藍の面に囲まれた白・水色の小さな塊（2〜400 画素）の数",
         "tool": "Tools/GWWaveGen/as05/s5_targets.py（appearance）", "pass_if": {"max": 0}, "baseline_sample04": ap.get("T5_small_white_blobs_on_hero_indigo")},
        {"id": "K-T6", "rule_ja": "利用者の切り出し（見本04 の原画視点の表示の画素 x 736〜891、y 300〜721）：藍の面の右の縁から 16 画素の帯の、主役波の画素のうち白・水色の割合",
         "tool": "s5_targets.py（appearance）", "pass_if": {"max": 0.02}, "baseline_sample04": ap.get("T6_inner_edge_band_pale_share")},
        {"id": "K-top", "rule_ja": "いちばん高い峰（主の頂と唇、行 c ≥ −8 m）の形は見本04 のまま（点の動き 0.05 m まで）。頂の幅（Q33）・S8・関門 130〜72 を守る一番簡単な形",
         "tool": "行の npz の差（c ≥ −8 の行の |ΔA|・|ΔY| の最大）", "pass_if": {"max_disp_m": 0.05}, "baseline_sample04": 0.0},
        {"id": "K-boat", "rule_ja": "一艘目の船（boat_left、Unity の位置 (−15.29, 4.82, −12.53)、断面の座標 a 0.76・y 4.82・c −12.68、原画のカメラから 51.8 m、原画の (421, 1660) に写る）を、"
         "原画視点で層の面が隠さない。原画では舳先（原画の x 110〜290、y 1230〜1470）が ③ の藍の面の手前に描かれるので、そこでは ③ の面は船より奥。"
         "船を動かす場合は原画のカメラを中心とする相似（原画視点の画は画素まで同じ）にし、名前の付いた美術の誘導として記録し、船・手前の海の射線の禁止域を新しい船の奥行きで作り直す",
         "tool": "船・手前の海の射線の禁止域（Polish/28/rec/cache/protect_grids.npz、shape_limit・shape_eval の spill の測り）と、Unity の原画視点の ID 画像の船の画素の数",
         "pass_if": {"protect_spill_new_cells": 0, "boat_left_pixels_min_ratio_vs_sample04": 0.98}},
        {"id": "K-S3", "rule_ja": "新しいふくらみ・鰭・台を作らない（15 視点と回り台を目で見る道具。閉じる条件にはしない）", "tool": "目で見る", "pass_if": None},
        {"id": "K-G1", "rule_ja": "原画のカメラの投影を使わない（色は頂点の属性とワールドの位置だけ）", "tool": "asm4_rules.g1 と同じコードの検査", "pass_if": None},
        {"id": "K-claws", "rule_ja": "面の内の爪 25 本・近い海の爪 10 本は残し、面が動いた所は根元を置き直す（C3 の原画視点の影の IoU p10 ≥ 0.85）。波頭の爪は出さない（Q33）",
         "tool": "asm4_rules.c2_c3", "pass_if": {"C3_iou_p10_min": 0.85}},
    ]
    out = {"schema": "GreatWave.AS05.targets/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "status_ja": "見本05 の作り手のための測れる目標（進行役の既定。利用者の言葉ではない）。美術が届いたかは利用者が決める（Q29・Q30）。目で見た審査は道具で、閉じる条件ではない",
           "source_user_words": "Q33（Docs/Workflow/Production_Workflow_ja.md）：「我希望先靠着造型来区分这3层 我觉得第3部分现在依然没有很好的得到体现」ほか",
           "units_ja": "長さ m。H0 = 20.75 m（主役波の t* の高さの基準）。断面の座標 a（+ が前・原画のカメラの側）・y（高さ）・c（+ が原画視点の右奥）。原画の画素は DP130155（3859×2594）",
           "how_to_measure": {"layers_and_appearance": "py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure <cand.json> <out.json>（cand.json の形はファイルの先頭）",
                              "kept_constraints": "Tools/GWWaveGen/as04/asm4_rules.py の g2・s4・s8・s9・s10・c2_c3 を見本05 の部品へ向けて使う",
                              "layer_labels_ja": "層の印（1 ①・2 ②・3 ③）は作り手が、主役波の行の格子（row_labels の npy）と足したメッシュ（layer か vertex_labels）に付ける。"
                                                 "既定は見本04 の c の帯（③ だけ下の端を 0.12 H0）"},
           "layer_reading_ja": {"r1": "① 浪尖：主の頂と唇。いちばん高く（0.98 H0）、原画のカメラから 55〜62 m。形は見本04 のまま（K-top）",
                                "r2": "② b区域：① の面（藍）の左下の手前に出る、爪の群れを載せた中ほどの層。頂 0.48〜0.60 H0、カメラから 44〜52 m。後ろに引っ込み（鞍）",
                                "r3": "③ 最左側の小区域：② の左下の、より低い小さな層。白・水色の頂の下に藍の面があり、一艘目の船（boat_left、カメラから 51.8 m）の舳先がその面の前に立つ。"
                                      "頂は 0.36〜0.48 H0（奥行き 40〜52 m に応じて）。舳先の重なる所の面は船より奥（K-boat）"},
           "painting_ray_heights": ray_heights(),
           "painting_ray_heights_note_ja": "原画の画素（x, y）の射線が、原画のカメラから d m の所で通る (d, a, y/H0, c)。L2・L3 は進行役が読んだ ②・③ の爪の群れの上の縁、"
                                           "face_top は藍の面の上の縁、boat_bow_tip は一艘目の船の舳先の先",
           "targets": T, "kept_constraints": K,
           "baseline_note_ja": "見本04 の値は s5_targets.py baseline（主役波 AS04F の行 ＋ wave4 fix1、層の印は既定の c の帯）と sample04/rules_check.json。"
                               "15 視点の分かれは見本04 の S11 と同じ値（①② 0.273・②③ 0.636）になることを確かめた",
           "reference_note_ja": "参照モデル（他者の展示作品のスキャン）の数は s5_obj.py で数だけを測った（メモリの中だけ、キャッシュは書かない。整列 B は大まかで ±50〜130 原画画素）。写し取らない"}
    S.jdump(S.OUT + "/targets.json", out)
    print("targets", len(T), "kept", len(K))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
