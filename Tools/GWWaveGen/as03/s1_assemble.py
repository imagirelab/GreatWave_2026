# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照の彫刻（他者の展示作品。参考にとどめ写し取らない）から測った数を、sculpture_spec.json にまとめる。
数・不確かさ・出典（写真のファイル名か OBJ の測り）を一つずつ書き、主の頂の高さ H・冠の縁の長さ L・面の幅 W に対する比と、
主役波 K*′ AS02C へ当てた値（m）を出す。形・頂点・画像は書かない。
入力（どれも Git 対象外の study/ の下）：s1_crown2_numbers_m05b.json、s1_crown_numbers_v06.json、s1_ref_dims.json、s1_hero_dims.json、
s1_face_relief.json、s1_photo_colors.jsonl、s1_photo_lines.jsonl。写真から目で読んだ数は、この中の PHOTO_READ に根拠とともに書く。
"""
import json
import os
import time

import numpy as np

STUDY = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study"
OUT = STUDY + "/sculpture_spec.json"
PH = "G:/research/reality scan/北斋参考"
PHOTOS = {
    "N05": "扫描2/近景扫描_1.0焦距_水平/近景扫描_1.0焦距_水平_5.jpg",
    "C06": "扫描2/特写_3.0焦距_水平/特写_3.0焦距_水平_6.jpg",
    "C19": "扫描2/特写_3.0焦距_水平/特写_3.0焦距_水平_19.jpg",
    "C34": "扫描2/特写_3.0焦距_水平/特写_3.0焦距_水平_34.jpg",
    "C44": "扫描2/特写_3.0焦距_水平/特写_3.0焦距_水平_44.jpg",
    "C49": "扫描2/特写_3.0焦距_水平/特写_3.0焦距_水平_49.jpg",
    "U13": "扫描2/近景扫描_1.0焦距_上45度/近景扫描_1.0焦距_上45度_13.jpg",
    "U45": "扫描2/近景扫描_1.0焦距_上45度/近景扫描_1.0焦距_上45度_45.jpg",
    "B00": "背图.jpg",
    "T00": "顶图、.jpg",
}


def J(p):
    return json.load(open(os.path.join(STUDY, p), encoding="utf-8"))


def jl(p):
    return [json.loads(l) for l in open(os.path.join(STUDY, p), encoding="utf-8") if l.strip()]


def num(v, unit, unc, src, rel=None, hero=None, note=None):
    d = {"value": v, "unit": unit, "uncertainty": unc, "source": src}
    if rel is not None:
        d["rel"] = rel
    if hero is not None:
        d["hero"] = hero
    if note:
        d["note"] = note
    return d


def srgb2lin(c):
    c = np.asarray(c, float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(x):
    x = np.clip(np.asarray(x, float), 0, 1)
    return np.round(255 * np.where(x <= 0.0031308, 12.92 * x, 1.055 * x ** (1 / 2.4) - 0.055)).astype(int).tolist()


def main():
    cr = J("s1_crown2_numbers_m05b.json")
    cr42 = J("s1_crown_numbers_v06.json")
    rd = J("s1_ref_dims.json")
    hd = J("s1_hero_dims.json")
    fr = J("s1_face_relief.json")
    cols = jl("s1_photo_colors.jsonl")
    lines = jl("s1_photo_lines.jsonl")

    H_ref = rd["H_ref_body_m"]                     # 開く半径 0.42 m の胴の頂（指を除く）
    H_ref_f = rd["H_ref_incl_fingers_m"]
    H0 = hd["H0_m"]
    s = H0 / H_ref                                  # 長さの写し（参照の m → 主役波の m）
    L_ref = rd["H_ge_0.40"]["rim_len_3d_m"]
    L_hero = hd["rim_H_ge_0.4"]["rim_len_3d_m"]
    W_ref = rd["H_ge_0.50"]["dc_m"]
    W_hero = hd["rim_H_ge_0.5"]["dc_m"]
    W_hero_face = hd["face_rows_crossing_0.50H"]["W_m"]
    lip_hero = hd["rim_H_ge_0.4"]["lip_tip_line_len_3d_m"]
    hm = lambda rel_H: round(rel_H * H0, 3)       # H に対する比 → 主役波の m
    per_m_hero = lambda n_ref: n_ref / L_ref / s  # 参照の縁 1 m あたりの数 → 主役波の 1 m あたり
    D = cr["digits"]
    Hn = cr["hands"]
    OBJ = "OBJ wave_repair_zbrush2.obj（SHA-256 AB4124F9…3D40）を整列 B で主役波の断面の座標へ置いた一時キャッシュ；s1_crown2.py（格子 0.05 m、指 = 半径 0.30 m で開いた差、手 = 0.85 m）"
    OBJ42 = "同じ OBJ；s1_crown.py（格子 0.06 m、半径 0.42 m で開いた差）"

    spec = {
        "schema": "GreatWave.AS03.S1.sculpture_spec/1",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note_ja": "参照の彫刻（他者の展示作品。Q19・Q20：参考にとどめ写し取らない）から測った数だけ。写真・写真から作った画像・OBJ の形は入れていない。"
                   "rel は主の頂の高さ H・冠の縁の長さ L・面の幅 W に対する比、hero は主役波 K*′ AS02C（H0 = 20.753 m）へ当てた値（m）。",
        "frame": {
            "coords": "主役波の断面の座標 (a = 進行方向 T・前が +a, y = 高さ, c = 波峰線 E)。原画視点では +c が画面の右（唇の先・富士の側）、-c が左（b区域の肩）。",
            "reference_alignment": "Docs/Evidence/ArtFirst/26/reference/align_B_upright.json（尺度 1.572、行列式 < 0：Unity の左手系への置き換えを含む）",
            "reference_sea_y_m": rd["sea_y"],
        },
        "scale": {
            "H_ref_m": num(round(H_ref, 3), "m", "±0.4 m（開く半径で頂が丸まる。指を含めると %.2f m）" % H_ref_f, OBJ42),
            "H_hero_m": num(round(H0, 3), "m", "AS02C の実の最高は %.2f m（c = %.1f）" % (hd["H_max_m"], hd["c_at_H_max"]), "Tools/GWWaveGen/as02/back_common.py の H0・kstarAS02C_a45_rows.npz"),
            "length_scale_ref_to_hero": round(s, 4),
            "L_def": "頂の線（胴の各 c の最も高い点。高さは 1 m、平面の位置は 3 m の窓でならす）の 3 次元の長さ。頂の高さ ≥ 0.4 H の最も長い区間",
            "L_ref_m": num(round(L_ref, 2), "m", "±3 m（参照は台の円盤で両端が切れている：+c の端で頂はまだ 0.57 H）", "s1_ref_dims.py", rel={"L_over_H": round(L_ref / H_ref, 3)}),
            "L_hero_m": num(round(L_hero, 2), "m", "±1 m", "s1_hero_dims.py", rel={"L_over_H": round(L_hero / H0, 3)}),
            "lip_tip_line_hero_m": num(round(lip_hero, 2), "m", "±1 m", "s1_hero_dims.py（列 j_tip=200 の線、頂 ≥ 0.4 H の行）"),
            "front_overhang": num({"ref_m": {k: round(rd["front_overhang_m"][k], 2) for k in ("p10", "p50", "p90")},
                                   "hero_lip_tip_ahead_of_crest_m": {k: round(v, 2) for k, v in hd["lip_overhang_a_tip_minus_crest_m"].items()}},
                                  "m", "±0.5 m", "s1_ref_dims.py・s1_hero_dims.py",
                                  note="参照は頂から前へ p50 約 3 m（0.14 H）しか張り出さず、面は張り出しの下の深い凹みの壁。主役波の唇の先は p50 7.5 m（0.36 H0）前に出る。"
                                       "冠の数は縁 1 m あたりで当て、面の数は H に対する比で当てる"),
            "W_def": "頂の高さ ≥ 0.5 H の最も長い区間の c の幅（主役波には、面の列 j_tip..j_facebot が 0.5 H を通る行の幅も書く）",
            "W_ref_m": num(round(W_ref, 2), "m", "±2 m", "s1_ref_dims.py", rel={"W_over_H": round(W_ref / H_ref, 3)}),
            "W_hero_m": num(round(W_hero, 2), "m", "±1 m", "s1_hero_dims.py", rel={"W_over_H": round(W_hero / H0, 3)},
                            note="面の列が 0.5 H0 を通る行の幅（藍の面の幅）は %.1f m" % W_hero_face),
        },
    }

    # ---------------------------------------------------------------- 1. 冠
    tipsD = D["n"]
    tipsD42 = cr42["n_fingers"]
    hands = Hn["n"]
    c1 = {
        "coverage": {
            "rim_part": num("頂の線の全体（参照の頂 ≥ 0.4 H の区間 c %.1f..%.1f m に対し、指の根元は c %.1f..%.1f m）。b区域の肩（-c）から唇の先（+c）まで切れ目なく続く"
                            % (rd["H_ge_0.40"]["c_range"][0], rd["H_ge_0.40"]["c_range"][1], cr["crown_root_c_range_m"][0], cr["crown_root_c_range_m"][1]),
                            "-", "端は台の円盤で切れているので、それより外は分からない", OBJ),
            "back_side": num("背には指がない：指 76 本のうち頂の線より後ろ（da < -0.5 m）は 1 本、線の上 3 本、前 72 本", "-", "—", OBJ + "；写真 B00・U45（背は滑らかな白）"),
            "front_band_root_dy_below_rim_over_H": num(D["root_dy_below_rim_over_H"], "H", "格子 0.05 m", OBJ, note="根元は頂の線から前の面を 0〜0.32 H（p90〜p10）下まで。中央値 0.13 H"),
            "front_band_root_ahead_of_rim_over_H": num(D["root_da_ahead_of_rim_over_H"], "H", "頂の線の a の位置は 3 m の窓でならした", OBJ),
            "root_height_above_sea_over_H": num(D["root_height_above_sea_over_H"], "H", "格子 0.05 m", OBJ,
                                                hero={"p10_m": hm(D["root_height_above_sea_over_H"]["p10"]), "p50_m": hm(D["root_height_above_sea_over_H"]["p50"]),
                                                      "p90_m": hm(D["root_height_above_sea_over_H"]["p90"])}),
        },
        "counts": {
            "fingertips_total_ref": num(tipsD, "本", "−10〜+30%%（細い指はスキャンで欠ける。半径 0.42 m で開くと %d 本。写真 N05 の前から見える先は約 70）" % tipsD42, OBJ + "；写真 N05"),
            "fingertips_per_m_of_L": num(round(tipsD / L_ref, 3), "1/m", "±25%", OBJ, rel={"per_H_of_L": round(tipsD / L_ref * H_ref, 2)},
                                         hero={"per_m": round(per_m_hero(tipsD), 3), "count_on_L_hero": int(round(per_m_hero(tipsD) * L_hero)),
                                               "range": [int(round(per_m_hero(tipsD42) * L_hero)), int(round(per_m_hero(tipsD) * L_hero * 1.25))]}),
            "hands_total_ref": num(hands, "個", "大きさの定義による：開く半径 0.70 m で 50 個、0.85 m で 28 個。写真の『掌＋指』の読みは 0.85 m に近い", OBJ),
            "hands_per_m_of_L": num(round(hands / L_ref, 3), "1/m", "+80% / −0%（0.70 m の定義なら 1.11/m）", OBJ, rel={"per_H_of_L": round(hands / L_ref * H_ref, 2)},
                                    hero={"per_m": round(per_m_hero(hands), 3), "count_on_L_hero": int(round(per_m_hero(hands) * L_hero)),
                                          "range": [int(round(per_m_hero(hands) * L_hero)), int(round(per_m_hero(50) * L_hero))]}),
            "count_by_c_4m_digits": D["count_by_c_4m"],
            "count_by_root_height_over_H_digits": D["count_by_root_height_over_H"],
        },
        "length": {
            "digit_len_over_H": num(D["len_over_H"], "H", "スキャンは細い先を短くしがち：+0〜30%", OBJ,
                                    hero={k: hm(v) for k, v in D["len_over_H"].items() if k.startswith("p")}),
            "hand_len_over_H": num(Hn["len_over_H"], "H", "±20%", OBJ, hero={k: hm(v) for k, v in Hn["len_over_H"].items() if k.startswith("p")}),
            "digit_len_over_base_diam_mesh": num(D["len_over_base_diam"], "-", "根元の太さは開く半径 0.30 m で上が切れる", OBJ),
            "digit_len_over_base_diam_photo": num({"p50": 3.5, "range": [2.5, 5.5]}, "-", "目の読み（指が掌から分かれる所からの長さ）",
                                                  "写真 C06（特写 6）・N05（近景水平 5）：見える指 15 本ほどの目の読み"),
        },
        "thickness": {
            "digit_diam_base_over_H": num(D["diam_base_over_H"], "H", "開く半径 0.30 m（径 0.60 m）より太い所は胴に入る", OBJ, hero={"p50_m": hm(D["diam_base_over_H"]["p50"])}),
            "digit_diam_mid_over_H": num(D["diam_mid_over_H"], "H", "格子 0.05 m（径で ±0.1 m）", OBJ, hero={"p50_m": hm(D["diam_mid_over_H"]["p50"])}),
            "digit_diam_tip_over_H": num(D["diam_tip_over_H"], "H", "格子 0.05 m（径で ±0.1 m）", OBJ, hero={"p50_m": hm(D["diam_tip_over_H"]["p50"])}),
            "hand_diam_base_over_H": num(Hn["diam_base_over_H"], "H", "±20%", OBJ, hero={"p50_m": hm(Hn["diam_base_over_H"]["p50"])}),
            "taper_law_digit": num(D["taper_fit_r_over_rbase_eq_1_minus_k_f_pow_p"], "r/r_base = 1 − k f^p（f = 根元からの道のりの割合）", "k ±0.1, p ±0.3", OBJ,
                                   note="ほぼ直線の細り。先の半径は根元の約 0.36。10 区間の中央値 %s" % D["r_profile_norm_median_10bands"]),
            "taper_law_hand": num(Hn["taper_fit_r_over_rbase_eq_1_minus_k_f_pow_p"], "同上", "k ±0.1, p ±0.3", OBJ, note="10 区間の中央値 %s" % Hn["r_profile_norm_median_10bands"]),
            "palm_shape": num("掌は平たい（幅 > 厚み）。指は丸い管", "-", "目の読み", "写真 C06・C34；OBJ の描画（一時）"),
        },
        "branching": {
            "digits_per_hand_mesh": num(Hn["digits_per_hand"], "本", "スキャンは細い指を欠く：下限", OBJ, note="分布 %s" % Hn["digits_per_hand_hist"]),
            "digits_per_hand_photo": num({"p50": 3, "range": [2, 5]}, "本", "目の読み", "写真 C06・N05・C34"),
            "branch_start_fraction_of_hand_length": num(Hn["digit_start_fraction_of_hand_length"], "-", "±0.1", OBJ, note="指は手の長さの 0.35〜0.51（p25〜p75）の所から分かれる"),
            "angle_between_digits_same_hand_deg": num({"p25": 24.3, "p50": 41.5, "p75": 67.2, "n_pairs": 207}, "deg", "±10°", OBJ),
            "angle_to_nearest_digit_deg": num(D["fan_angle_to_nearest_deg"], "deg", "±10°", OBJ),
        },
        "tip_shape": {
            "tip_over_neck_radius_mesh": num(D["tip_last_over_neck_radius"], "-", "格子 0.05 m", OBJ, note="先の区間の半径 / 0.7〜0.8 の区間の半径。≥1 なら膨らみ。分類 %s" % D["tip_class_counts"]),
            "reading": num("丸い先（半球）が多数。膨らんだしずくはまれ（<5%）。先が口の開いた管（穴のある丸い先）が約 10%。鋭い針はない", "-", "目の読み",
                           "写真 N05（管の先 6〜8 本）・C06・C49；OBJ の描画（一時）で管の先を確認"),
        },
        "direction": {
            "angle_digit_vs_root_normal_deg": num(D["ang_overall_vs_normal_deg"], "deg", "法線は胴をぼかした場の勾配：±8°", OBJ, note="指は根元の面からほぼ法線の向きに出る（中央値 22°）"),
            "angle_digit_overall_vs_up_deg": num(D["ang_overall_vs_up_deg"], "deg", "±5°", OBJ, note="90° = 水平。中央値 114° = 水平から 24° 下"),
            "angle_digit_tip_vs_up_deg": num(D["ang_tip_vs_up_deg"], "deg", "±8°", OBJ, note="先は根元よりさらに下へ垂れる（中央値 123°）"),
            "frac_tips_pointing_down": num(D["frac_tip_pointing_down"], "-", "写真 N05 では見える指先 約 70 のうち 10〜15（15〜20%）が頂の輪郭で上・外を向く（どれも短い指）。スキャンでは上向きは 7〜10%（開く半径 0.42 m でも下向き 93%）", OBJ + "；写真 N05"),
            "frac_forward_over_lip": num(D["frac_overall_forward_plus_a"], "-", "±0.05", OBJ),
            "angle_digit_vs_forward_deg": num(D["ang_overall_vs_forward_plus_a_deg"], "deg", "±8°", OBJ),
            "curl_root_to_tip_deg": num({"digit": D["curl_root_to_tip_deg"], "hand": Hn["curl_root_to_tip_deg"]}, "deg", "±8°", OBJ,
                                        note="手は根元から先へ中央値 43° 曲がる（先が垂れる）。指 1 本では 19°"),
        },
        "layering": {
            "hand_root_dy_below_rim_hist": num(Hn["rows_dy_over_H_hist_0p04"], "H", "格子 0.05 m", OBJ,
                                               note="手の根元は頂の線から 0〜0.08 H に約半分、0.10〜0.20 H に約 3 割、0.25〜0.45 H（唇の巻きの下）に約 2 割：2〜3 段"),
            "photo_rows": num("前から見て 2〜3 段：最前列は唇の縁から下へ垂れ、その上の段は前・外へ出て先が垂れる。隣の手は横に 2〜4 割重なり、指が互いに入り込む", "-", "目の読み", "写真 N05・C44・C06・C19"),
            "nearest_root_spacing_over_H": num(D["nearest_root_spacing_over_H"], "H", "±0.01 H", OBJ, hero={"p50_m": hm(D["nearest_root_spacing_over_H"]["p50"])}),
        },
        "gaps": {
            "white_fraction_along_hanging_band": num({"near_crown_base": [0.47, 0.80], "mid_band_p50": 0.35, "mid_band_range": [0.25, 0.45], "near_tips": [0.11, 0.29]}, "-",
                                                     "写真の向きと焦点のぼけで ±0.1", "写真 N05（近景水平 5）・C49（特写 49）・C44（特写 44）の横の線の上の白の割合（s1_assemble の PHOTO_READ）",
                                                     note="垂れる指の帯の中ほどでは、指の間に藍が 55〜75% 見える"),
        },
        "continuation": {
            "along_lip_into_curl": num("続く。唇が巻き下がる +c の側（原画視点の右）で、根元は海面から 0.39 H（p10）まで下がる。4 m ごとの数はほぼ一様（%s）" % D["count_by_c_4m"]["counts"], "-", "台の円盤で切れる所の先は不明", OBJ + "；写真 C19・N05"),
            "b_region_second_crest": num("ある。-c の肩（c -16〜-9 m）に指 11 本・手 5 個。白い塊に穴（藍が透けて見える）があり、塊の下の縁から指が外・下へ出る", "-", "目の読み＋OBJ", OBJ + "；写真 C34（特写 34）"),
            "small_foreground_wave": num("指はない（前の小波の範囲で、船の部品などを除くと 0）。頂は滑らかな白い帽子で、境は藍の舌の縁（2 節）", "-", "—", "s1_crown2.py の前の小波の箱（a 4.5〜16.5 m）；写真 U13・N05"),
        },
    }
    spec["1_crest_crown"] = c1

    # ---------------------------------------------------------------- 2. 白の範囲と垂れる縁
    c2 = {
        "white_on_back": num({"lower_edge_above_sea_over_H": [0.25, 0.40]}, "H", "±0.05 H（写真の角度）", "写真 B00（背图）・U45（近景上45 45）",
                             hero={"lower_edge_m": [hm(0.25), hm(0.40)]},
                             note="背は頂から海面の 0.25〜0.40 H まで一続きの滑らかな艶のある白。境はゆるい一つの波のような曲線で、舌も指もない。その下は藍"),
        "white_on_main_front": num("前の面の白は冠（立体の指と掌）だけ。冠の下の縁は頂の線から 0.15〜0.3 H 下。面に平らに塗った白い舌はない。船のそばに白い泡の三日月が少し（面の 1〜2%）", "-",
                                   "目の読み", "写真 C49・U13・N05・C44"),
        "main_front_boundary": num("白から藍への移りは、垂れる立体の指そのもの（2.5 節の指の数と長さ）。指の間に藍が見える", "-", "—", "写真 C06・C44・C49；OBJ"),
        "right_end": num("+c の端（唇の先の側の外）は背の白が海面近くまで下りる", "-", "目の読み", "写真 C19（特写 19）"),
        "tongues_small_wave": {
            "shape": num("藍の舌が下から白の中へ立ち上がる。頭は半円で丸く、舌と舌の間の白は下向きに尖った V。舌そのものも少し盛り上がり（艶の光が頭に乗る）、中に水色の線が 1 本通る", "-", "目の読み", "写真 U13（近景上45 13）・N05"),
            "width_over_H": num(0.065, "H", "±0.015 H", "写真 N05（明るくした一時の切り出しで、舌 5 本の目の読み。H は同じ写真の頂〜海面 約 740 px）", hero=hm(0.065)),
            "spacing_over_H": num(0.12, "H", "±0.03 H", "同上", hero=hm(0.12), rel={"per_H_of_boundary": round(1 / 0.12, 1)}),
            "length_over_H": num(0.15, "H", "±0.05 H", "同上（見える長さ。根元は次の舌と重なる）", hero=hm(0.15)),
            "end": num("丸い（半径 ≈ 舌の幅の半分）", "-", "—", "写真 U13・N05"),
        },
        "white_in_grooves": num("ない。水色の線は冠の垂れる指のすぐ下から始まり、溝に白は入らない", "-", "—", "写真 C49・U13"),
    }
    spec["2_white_and_drip_edge"] = c2

    # ---------------------------------------------------------------- 3. 彫りの面
    per = []
    wr = []
    for L in lines:
        for y, r in L["rows"].items():
            if r["n_lines"] >= 4 and r["line_width_over_period"]:
                per.append((L["image"], y, r["period_px_p50"], r["n_lines"]))
                wr.append(r["line_width_over_period"])
    c3 = {
        "mesh_relief": num(fr, "m", "—", "OBJ（s1_face_relief.py：面の下の帯 0.25〜0.40 H の前から見た深さを c の向きに 1.5 m でならした残り）",
                           note="スキャン（修理済み）の面には規則的な溝の凹凸が残っていない：0.35〜0.40 H で残りの RMS 0.04〜0.05 m（0.2% H）、山の間隔は 0.2〜0.4 m の不規則（雑音）。"
                                "溝の数・幅は写真から測った。溝の深さは写真の陰影からの推定だけ"),
        "line_count_across_visible_face": num({"upper_just_below_crown": [10, 12], "mid_height": [12, 14], "lower": [8, 10]}, "本", "±2 本",
                                              "写真 N05（明るくした一時の切り出し）の目の読み；C49 の自動の数え（中ほどで 10〜11 本、見える幅 620〜670 px）",
                                              note="前から見える面（船の右から空洞の縁まで、中ほどの高さで約 0.6〜0.7 H の幅）での数"),
        "groove_period_over_H": num(0.045, "H", "±0.01 H（面の曲がりと写真の向きによる縮み）",
                                    "写真 N05（明るくした一時の切り出し。H ≈ 740 px／縮めた写し、≈ 1480 px／切り出し）の目の読みと自動の数え・C49・U13 の自動の数え",
                                    hero=hm(0.045), rel={"upper_just_below_crown": 0.035, "mid_height": 0.045, "lower_face": 0.056},
                                    note="線は下へ行くほど開く（上 0.035・中 0.045・下 0.056 H。主役波で %.2f・%.2f・%.2f m）。主役波の藍の面の幅（面の列が 0.5 H0 を通る %.1f m）なら中ほどで約 %d 本"
                                         % (hm(0.035), hm(0.045), hm(0.056), W_hero_face, int(round(W_hero_face / hm(0.045))))),
        "light_blue_width_over_period": num(round(float(np.median(wr)), 3), "-", "±0.05", "写真 C49・U13・N05 の自動の数え（%d 本の線の帯）" % len(wr),
                                            hero=round(float(np.median(wr)) * hm(0.045), 3), note="溝（水色）: 稜（藍）の幅 ≈ 1 : 3"),
        "cross_section": num("藍の稜は幅広く丸い凸（艶の光が稜の背に細い弧で乗る）。稜と稜の継ぎ目の細い溝に水色の線が入る。水色の線そのものも少し丸く盛り上がって見える（溝の中の細い玉縁）", "-",
                             "目の読み（深さは測れない。陰影から深さ / 周期 ≈ 0.1、範囲 0.05〜0.25）", "写真 C44（特写 44 の空洞の内側）・C49・U13"),
        "follow_curl": num("溝は空洞を中心とする入れ子の C 字（弧）。唇の下では放射に近く上から下へ、面の下では横へ寝て谷に沿って流れ、手前の海へ続く", "-", "目の読み", "写真 N05・U13・C44"),
        "forks": num({"per_line_per_visible_length": [0.25, 0.35]}, "-", "±0.15（自動の骨格の数えは雑音が多いので目の読みを採る）",
                     "写真 U13（近景上45 13）・C49 の目の読み", note="線 3〜4 本に 1 つほどの Y 字。分かれた 2 本は下流（下）へ開く"),
        "ends_near_crest": num("冠の垂れる指の陰のすぐ下（頂の線から約 0.2〜0.3 H 下）で、陰に入って見えなくなる。冠の白に触れる所まで線は続かない", "-", "目の読み", "写真 C49・N05"),
        "ends_at_base": num("面の下で横へ寝て、前の小波の白の後ろか、谷の水色の横線へつながる", "-", "目の読み", "写真 N05・U13"),
        "light_blue_gradient": num("線の中は一様な色（中央がわずかに明るい）。藍との境はぼかさない（はっきり）", "-", "目の読み", "写真 C49・U13"),
    }
    spec["3_carved_face"] = c3

    # ---------------------------------------------------------------- 4. 色と陰影
    agg = {}
    for c in cols:
        for k in ("white", "lightblue", "indigo", "gold", "base"):
            if c.get(k):
                agg.setdefault(k, []).append((c["image"], c[k]))
    colors = {}
    # 白の光の所を中立の白とみなして色温度を直す（写真は暖かい電球の光）。露出は白の光の所を sRGB 245 にそろえる
    wl = np.median([v["lit_srgb"] for _, v in agg["white"]], axis=0)
    lin_w = srgb2lin(wl)
    gain = (lin_w.max() / lin_w) * (srgb2lin([245, 245, 245])[0] / lin_w.max())
    for k, lst in agg.items():
        d = {"photos": [n for n, _ in lst]}
        for lvl in ("lit", "mid", "shadow"):
            raw = np.median([v["%s_srgb" % lvl] for _, v in lst], axis=0)
            d["%s_srgb_raw" % lvl] = [int(round(x)) for x in raw]
            d["%s_srgb_wb" % lvl] = lin2srgb(srgb2lin(raw) * gain)
            d["L_%s" % lvl] = round(float(np.median([v["L_%s" % lvl] for _, v in lst])), 1)
        colors[k] = d
    c4 = {
        "white_balance_note": "写真は暖かい電球の光で撮られている。_raw は写真のままの sRGB の中央値、_wb は白の光の所を中立の白（sRGB 245）とみなして直した値（線形の空間で各色に掛け算）。"
                              "lit/mid/shadow は類の中の L* の上位 15%・中ほど 20%・下位 15%。鏡のような光の点（明るさ ≥ 245 かつ彩度 ≤ 35）は除いた",
        "wb_gain_linear": [round(float(x), 3) for x in gain],
        "colors": colors,
        "names": {"white": "白（冠・背）", "lightblue": "淡い水色（面の溝の線。実際は中くらいの明るさのコバルトの青）", "indigo": "藍（面の地）", "gold": "金（舟）", "base": "台の水色（海の円盤）"},
        "indigo_dark_vs_mid": num({"indigo_dark_wb": colors["indigo"]["shadow_srgb_wb"], "indigo_mid_wb": colors["indigo"]["mid_srgb_wb"], "indigo_lit_wb": colors["indigo"]["lit_srgb_wb"]},
                                  "sRGB", "±10（写真ごとの差）", "写真 C06・C49・U13・U45・B00・N05・C44",
                                  note="藍の拡散の色は黒に近い（L* 2〜6）。見える形はほとんど艶の映り込みと光の点（L* 17〜21）で出る"),
        "gloss": num({"specular_spot_eq_diam_px_p50": [5.7, 8.4], "finger_diam_px_same_photos": [45, 60], "spot_over_finger_diam": [0.12, 0.18],
                      "specular_area_frac": [0.001, 0.004]}, "-", "写真の解像度とぼけ", "写真 C06・C49・U13・C44（特写・近景の切り出し）",
                     note="強い艶：小さく鋭い光の点が指・稜の背に乗り、背の広い白には窓・電灯の細長い映り込み。粗さの目安 GGX 0.05〜0.15（推定）"),
        "form_shading_range": num({"white_L_lit": colors["white"]["L_lit"], "white_L_mid": colors["white"]["L_mid"], "white_L_shadow": colors["white"]["L_shadow"],
                                   "indigo_L_lit": colors["indigo"]["L_lit"], "indigo_L_mid": colors["indigo"]["L_mid"], "indigo_L_shadow": colors["indigo"]["L_shadow"],
                                   "lightblue_L_lit": colors["lightblue"]["L_lit"], "lightblue_L_shadow": colors["lightblue"]["L_shadow"]}, "L*", "±5",
                                  "同上", note="白は光の所から陰まで ΔL* 約 30（輝度でおよそ 3 : 1）の本当の陰影がある。藍は拡散が暗く、陰影は艶で読む"),
        "rim_light": num("描いた縁の光はない。艶の映り込みが斜めの所で明るくなる（フレネルのような）：藍の稜の縁、白い背の輪郭沿いに明るい帯", "-", "目の読み", "写真 C44・C19・U45"),
        "outlines": num("ない。白・藍・水色の境ははっきりしているが、線で縁取っていない", "-", "—", "全部の写真"),
        "sparkle": num("藍の上に小さな星形の光の点が多数（撮影の多灯の光の映り込みか、艶の層の細かい凹凸）", "-", "目の読み", "写真 U13（近景上45 13）"),
    }
    spec["4_colour_and_shading"] = c4

    # ---------------------------------------------------------------- 5. 原画の向きに近い写真
    c5 = {
        "photo": num("N05（近景水平 5）。原画視点（OBJ を原画のカメラの向きから描いた一時の図）と、頂・唇の先・b区域・空洞の並びがいちばん近い。向きの差は約 20° 以内（目の読み）", "-", "±20°", "写真 N05；OBJ の一時の描画"),
        "reading": num("冠は一続きの太い白い泡の帯で、指が上・外・前・下の全部の向きへ放射して、とげのある珊瑚か毛虫のように読める。前から見える指先は約 70。"
                       "最前列の垂れる指は原画の爪が面へかかる所に当たるが、先は丸く、鉤に巻かず、藍の縁取りも水色の内側もない", "-", "目の読み", "写真 N05・C44"),
        "vs_painting": num({"painting_band_claws": 191, "painting_claws_total_approx": 300, "sculpture_tips_visible_front": 70, "sculpture_tips_total_mesh": tipsD,
                            "ratio_sculpture_to_painting_band": round(70 / 191, 2)}, "本", "原画の数はリポジトリの記録（美術の見本01 §2.4 の帯の爪 191 本、見本02 §7 の約 300）",
                           "Docs/Progress/ArtSample_01_ja.md・ArtSample_02_ja.md；写真 N05",
                           note="彫刻の冠は原画の爪の縁より数が約 1/3、1 本が太く短く丸い。原画の縁は細い鉤が扇に開き、間から空が透ける細かいレース。彫刻は塊の量感と艶と陰影で読ませ、原画は線と形で読ませる"),
    }
    spec["5_painting_direction"] = c5

    spec["sources"] = {
        "photo_folder": PH,
        "photos": PHOTOS,
        "obj": {"file": "G:/research/model/wave_repair_zbrush2.obj", "sha256": "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40",
                "use": "数だけ（一時キャッシュ、測った後に消した。s1_objcache_log.json）"},
        "hero": hd["source"], "hero_sha256": hd["source_sha256"],
        "tools": "Tools/GWWaveGen/as03/s1_*.py",
        "limits_ja": ["スキャンの OBJ は修理（ZBrush）されていて、面の溝が残っていない。細い指も短く・少なく出やすい（数と長さは下限寄り）",
                      "写真から読んだ数（溝の周期・舌の大きさ・白の下の縁）は、写真の向きと面の曲がりで ±20〜30% ずれうる",
                      "色は暖かい電球の光の写真から取った。_wb は白を中立とみなした直しで、本当の釉薬の色ではない",
                      "参照は台の円盤で両端が切れているので、L と W は下限寄り"],
    }
    json.dump(spec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    print("wrote", OUT, os.path.getsize(OUT))
    print(json.dumps(colors, ensure_ascii=False))
    print("s", s, "L", L_ref, L_hero, "W", W_ref, W_hero, "tips hero", per_m_hero(tipsD) * L_hero, "hands hero", per_m_hero(hands) * L_hero)


if __name__ == "__main__":
    main()
