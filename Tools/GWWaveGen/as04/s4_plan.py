# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S の 5：作り直しの計画の数（Q32）。s4_map.json・s4_bulge.json・s4_obj_numbers.json と AS02C から、
(a) 出っ張りを内の面の弧へならす量、(b) 左の白を下げる量と別の青い波の頂の置き場所、(c) 波峰線の向きを詰めた後の帯の長さ（試算）、
(d) 三つの層の目標の数、(e) 背の一つの山（S4）の試算の確かめ、を出す。形は作らない（数と試算だけ）。
使い方：py -3.10 -B Tools/GWWaveGen/as04/s4_plan.py
出力：Unity/Build/Polish/sample04/map/s4_plan.json、s4_F_plan.png
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S  # noqa: E402

FONT = "C:/Windows/Fonts/meiryo.ttc"
FONTB = "C:/Windows/Fonts/meiryob.ttc"


def font(n, b=False):
    return ImageFont.truetype(FONTB if b else FONT, n)


def segdist(P, Q):
    A = Q[:-1]; B = Q[1:]; AB = B - A; L2 = np.maximum((AB ** 2).sum(1), 1e-12)
    t = np.clip(((P[:, None, :] - A[None]) * AB[None]).sum(-1) / L2[None], 0, 1)
    D = A[None] + t[..., None] * AB[None]
    return np.sqrt(((P[:, None, :] - D) ** 2).sum(-1)).min(1)


def band_ext(c, H, Href, fr=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    out = {}
    for f in fr:
        ok = np.nonzero(H >= f * Href)[0]
        out["%.1f" % f] = S.rnd(c[ok[-1]] - c[ok[0]]) if len(ok) else 0.0
    return out


def dip(f):
    L = np.maximum.accumulate(f); R = np.maximum.accumulate(f[::-1])[::-1]
    return np.minimum(L, R) - f


def main():
    X0 = S.load_hero()
    SX = S.hero_sec(X0)
    cm = S.rows_c()
    M = json.load(open(S.OUT + "/s4_map.json", encoding="utf-8"))
    B = json.load(open(S.OUT + "/s4_bulge.json", encoding="utf-8"))
    O = json.load(open(S.OUT + "/s4_obj_numbers.json", encoding="utf-8"))
    plan = {"schema": "GreatWave.ArtSample04.study_plan/1", "base": "K*' AS02C（t*）", "H0_m": S.H0}

    # ---------------------------------------------------------------- (a) 出っ張り
    ref_rows = range(160, 173)            # 主の頂の行（c −0.8〜+1.6）：唇の板の厚みの手本
    cols = (150, 170, 185, 195)
    th_ref = {}
    for j in cols:
        th_ref[j] = float(np.median([segdist(np.c_[SX[i, j, 0], SX[i, j, 1]], np.c_[SX[i, 200:315, 0], SX[i, 200:315, 1]])[0] for i in ref_rows]))
    rows_a = []
    for i in range(104, 141, 2):
        th = {j: float(segdist(np.c_[SX[i, j, 0], SX[i, j, 1]], np.c_[SX[i, 200:315, 0], SX[i, 200:315, 1]])[0]) for j in cols}
        rows_a.append({"row": i, "c_m": S.rnd(cm[i]), "thickness_m": {str(j): S.rnd(th[j]) for j in cols},
                       "reduce_to_main_m": {str(j): S.rnd(max(0.0, th[j] - th_ref[j])) for j in cols}})
    offs = {p["row"]: p["bulge_offset_from_inner_arc_m"] for p in B["per_row_inner_arc"]}
    plan["a_bulge"] = {
        "where": {"rows_full": [113, 133], "rows_blend_to_zero": [108, 138], "c_full_m": [S.rnd(cm[113]), S.rnd(cm[133])],
                  "c_blend_m": [S.rnd(cm[108]), S.rnd(cm[138])], "cols_move": [135, 197], "cols_blend": [120, 135]},
        "measured": {"visible_layer": "唇の外の面（列 144〜196）", "behind_layer": "唇の下〜角の内の面（列 213〜237）",
                     "gap_along_ray_m": B["second_layer"]["gap_along_ray_m"], "offset_from_inner_arc_by_row": offs},
        "lip_thickness_main_rows_m": {str(j): S.rnd(v) for j, v in th_ref.items()},
        "lip_thickness_by_row": rows_a,
        "target_ja": "c −10〜−6 m の唇の板の外の面（列 135〜197）を、内の面の弧の側へ寄せ、唇の板の厚みを主の頂の行（c −0.8〜+1.6）と同じにする"
                     "（列 170 で約 %.2f m、列 185 で約 %.2f m）。原画視点で見えている点の、内の面の弧からの出を p50 1.3〜1.6 m → 0.5 m 以下、最大 3.1 m → 1.0 m 以下にする。"
                     "外の面の頂の下の折れ（急に下りて棚になる所）をなくし、頂から唇の先まで一つの凸の弧にする。" % (th_ref[170], th_ref[185]),
        "keep_ja": "頂（列 80〜102、関門 130・131 の行 111〜156）は動かさない。唇の先（列 ≥ 196）は行 ≥ 128 で動かさない（関門 72 の始まり）。",
        "gates_check_ja": "直した後に 78・130・131 ≤ 4 px と 132・72 σ12 ≤ 4 px を測る。見えている唇の外の面が奥へ下がるので、その奥の内の面（列 213〜237）が見えるようになる（藍・淡い青の面の色で塗る）。",
    }

    # ---------------------------------------------------------------- (b) 左側
    cam = S.CC.painting_cam()
    s78 = S.outline_segments()["78"]
    cols4 = M["region4"]["columns"]
    lower = []
    for e in cols4:
        if e["x_ref"] > 340 or e.get("wedge_lower_edge_y_ref_smooth") is None or "hero_depth_m" not in e:
            continue
        xd, yd = S.ref_to_disp(np.array([e["x_ref"], e["wedge_lower_edge_y_ref_smooth"]]))
        d = cam.ray(np.array([xd]), np.array([yd]))[0]
        s0 = e["hero_depth_m"] / float(d @ cam.f)
        out = {"x_ref": e["x_ref"], "white_top_target_y_ref": e["wedge_lower_edge_y_ref_smooth"], "now_top_y_m": e["hero_y_m"],
               "lower_by_m_at_same_depth": e["lower_by_m_at_hero_depth"]}
        for ds in (-3.0, 0.0, 3.0):
            P = cam.pos + (s0 + ds) * d
            q = S.K.sec(P[None])[0]
            out["along_ray_%+d" % ds] = {"a": S.rnd(q[0]), "c": S.rnd(q[2]), "y": S.rnd(q[1])}
        lower.append(out)
    blue = []
    for xr in (4, 40, 80, 120, 160, 200, 240, 280, 320, 360):
        k = int(np.argmin(np.abs(s78[:, 0] - xr)))
        xd, yd = S.ref_to_disp(s78[k])
        d = cam.ray(np.array([xd]), np.array([yd]))[0]
        e = next((q for q in cols4 if q["x_ref"] == 4 * round(xr / 4) and "hero_depth_m" in q), None)
        hd = e["hero_depth_m"] / float(d @ cam.f) if e else np.nan
        row = {"x_ref": S.rnd(s78[k, 0], 1), "y_ref": S.rnd(s78[k, 1], 1), "hero_crest_dist_m": S.rnd(hd), "by_dist": {}}
        for dist in (50.0, 53.0, 56.0, 60.0):
            P = cam.pos + dist * d
            q = S.K.sec(P[None])[0]
            row["by_dist"]["%d" % dist] = {"a": S.rnd(q[0]), "c": S.rnd(q[2]), "y": S.rnd(q[1])}
        if np.isfinite(hd):
            P = cam.pos + (hd + 5.0) * d
            q = S.K.sec(P[None])[0]
            row["hero_plus_5m"] = {"dist": S.rnd(hd + 5.0), "a": S.rnd(q[0]), "c": S.rnd(q[2]), "y": S.rnd(q[1])}
        blue.append(row)
    # 左の尾を詰めた後の H(c)（試算）：左の白を楔の下の縁まで下げ（行 77〜101）、c < −18 は c −26 で海へ下りる直線より上を切る
    H = SX[:, S.J_B:S.J_TIP, 1].max(1)
    Hn = H.copy()
    xs_low = np.array([q["now_top_y_m"] - q["lower_by_m_at_same_depth"] for q in lower])
    c_low = np.array([next(e["hero_c_m"] for e in cols4 if e["x_ref"] == q["x_ref"]) for q in lower])
    o = np.argsort(c_low)
    c_end, c_start = -26.0, -18.0
    h_start = float(np.interp(c_start, c_low[o], xs_low[o]))
    for i in range(len(cm)):
        if c_start <= cm[i] <= c_low.max():
            Hn[i] = min(Hn[i], float(np.interp(cm[i], c_low[o], xs_low[o])))
    for i in range(len(cm)):
        if cm[i] < c_start:
            Hn[i] = min(Hn[i], max(0.0, h_start * (cm[i] - c_end) / (c_start - c_end)))
    Href = float(H.max())
    ext_now = band_ext(cm, H, Href)
    ext_new = band_ext(cm, Hn, Href)
    ref_ext = {f: v["length_m"] for f, v in O["crest_length"]["ref_band_extent"].items()}
    plan["b_left"] = {
        "region4_now_ja": "④ の輪郭（区間 78 の x 0〜360）は今、主役波の左の部分の頂（行 77〜101、c −17.4〜−12.5 m、列 85〜106、高さ 10.9〜12.1 m、"
                          "カメラから 46.5〜51.6 m）が作っている。海ではない。見本03 はここに白い冠を載せたので、白い塊が高い輪郭に合って見えた。",
        "wedge_ja": "原画の青い楔は x 0〜約 330（厚み 左端 177 原画画素 → x 300 で 29）。その下の生成りの白が楔の手前で楔の下を隠す。",
        "white_lowered_target": lower,
        "blue_wave_crest_on_rays": blue,
        "blue_wave_recommend_ja": "別の小さな青い波（新しいメッシュ、主役波とは別の物）を、頂の縁が ④ の射線（区間 78 の x 0〜360）の上で、今の主役波の頂より 5 m 奥"
                                  "（射線の上の距離 %.1f〜%.1f m、高さ %.1f〜%.1f m = %.2f〜%.2f H0、a %.1f〜%.1f、c %.1f〜%.1f）に置く。x ≈ 340〜360 で主役波の頂の線の後ろへ入り（そこから右の輪郭は主役波）、" % (
                                      min(q["hero_plus_5m"]["dist"] for q in blue), max(q["hero_plus_5m"]["dist"] for q in blue),
                                      min(q["hero_plus_5m"]["y"] for q in blue), max(q["hero_plus_5m"]["y"] for q in blue),
                                      min(q["hero_plus_5m"]["y"] for q in blue) / S.H0, max(q["hero_plus_5m"]["y"] for q in blue) / S.H0,
                                      min(q["hero_plus_5m"]["a"] for q in blue), max(q["hero_plus_5m"]["a"] for q in blue),
                                      min(q["hero_plus_5m"]["c"] for q in blue), max(q["hero_plus_5m"]["c"] for q in blue)) +
                                  "左は原画の画の外（x < 0）へ、c −25 m あたりまで下りながら延ばす（画の外なので関門に入らない）。前の面は藍、頂の縁は淡い水色の帯（原画の楔の色）で、白を載せない。"
                                  "前の下の部分は、下げた主役波の左の白（手前）に隠れる。",
        "shorten_ja": "行 0〜62（c −60〜−20.6 m）は原画の画の外。c −18 m（白の上の縁 ≈ %.1f m）から c −26 m で海の高さへ下ろし、それより左は海の高さにする（格子・行の c・境の輪は変えない）。" % h_start,
        "band_extent_now_m": ext_now, "band_extent_after_b_m": ext_new, "band_extent_reference_m": ref_ext,
        "H_ref_for_bands_m": S.rnd(Href),
    }

    # ---------------------------------------------------------------- (c) 詰め
    ratio = {f: S.rnd(ext_new[f] / ext_now[f]) if ext_now[f] else None for f in ext_now}
    plan["c_compact"] = {
        "now_vs_ref_ja": "高さの帯ごとの c の幅（主役波 / 参照）：" + "、".join("%s H %.1f/%.1f m" % (f, ext_now[f], ref_ext.get(f, float("nan"))) for f in ext_now),
        "after_b_ratio": ratio,
        "target_m": {"0.1": 40.0, "0.2": 36.0, "0.5": 27.5, "0.8": 13.0, "0.9": 8.0},
        "target_ja": "低い帯（0.1〜0.5 H）は (b) の左の尾の切りと白を下げることで参照に近づく（試算の after_b）。高い帯（0.8・0.9 H）は主役波が参照の 1.6〜2.4 倍で、"
                     "頂が平らな尾根になっている。ここは原画の輪郭 131・132・72 に縛られるので、行を原画のカメラの射線の上で動かす（画は変えずに奥行きだけ変える）ことでだけ詰められる。"
                     "射線の向きは波峰線と約 45°（D6 の 45° の立体解釈）なので、射線の上で 1 m 動かすと c は約 0.70 m、高さは約 0.10〜0.20 m 変わる。"
                     "左の部分を奥へ、右の部分を手前へ動かすと c の幅が詰まる。D6（45°）を部分的に変えることになるので、(a)(b)(d) の見本を利用者が見た後の第 2 段にする。",
        "free_ja": "自由に動かせる行：0〜62（c −60〜−20.6 m、画の外）、231〜239（c +13.2〜+15 m）。原画視点で見えない頂点（背の頂より下、唇の下の奥）も自由。"
                   "見えるが輪郭を作らない頂点は射線の上だけ動かせる。輪郭を作る行は 78〜230（c −17.2〜+13.2 m）で、(b) の後は 78 の x 0〜360 を青い波が受け持つので、行 77〜101 の頂は縛りから外れる。",
    }

    # ---------------------------------------------------------------- (d) 三つの層
    reg = M["regions"]
    secs = O.get("sections_by_c", {})
    plan["d_layers"] = {
        "now": {k: {"rows": [reg[k]["row"]["min"], reg[k]["row"]["max"]], "c_m": [reg[k]["c_m"]["p05"], reg[k]["c_m"]["p95"]],
                    "y_over_H0": [reg[k]["y_over_H0"]["min"], reg[k]["y_over_H0"]["max"]], "depth_m_p50": reg[k]["depth_m"]["p50"],
                    "cols": [reg[k]["col"]["p05"], reg[k]["col"]["p95"]], "col_band_share": reg[k].get("col_band_share")} for k in ("r1", "r2", "r3")},
        "now_ja": "② は左の行（c −16〜−9 m が主）の唇の外の面、③ は同じ左の行の唇の下と前の面の下の方で、① の唇から ②・③ まで一枚の唇の板が続いている。"
                  "② は ① より原画のカメラに 7 m 近い（深さ p50 44.6 / 51.4 m）が、③ は ② より奥（p50 51.0 m）で、層として前後が逆。側面・上からは段が読めない。",
        "reference_ja": "参照モデル（数だけ、整列 B は粗いので ±20〜30%）：主の頂 1.0 H（c ≈ 0）の唇は短く、0.70〜0.85 H の前の縁は a −0.2〜+1.9 m（主役波は +5.7〜+11 m）。"
                        "主の頂の左、c −12〜−9 m に 0.57〜0.63 H の肩（b区域の白い塊）があり、肩の前の縁（0.45〜0.55 H）は a −0.5〜+1.7 m で主の唇の前とほぼ同じ線。"
                        "肩の下 0.35 H の帯は a −2.2〜−5.4 m へ引っ込み（段）、その下の前に 0.25 H で a +5.1〜+5.4 m、0.15 H で a +7.0〜+7.6 m の低い前の形（手前の小波を含む）が出る。"
                        "左の端は c −13〜−15 m で 0.40〜0.48 H に下がり、台で切られる。主役波は同じ c で、② の唇（0.35〜0.45 H）が a +7.0〜+10.5 m まで出るが、"
                        "その下 0.15〜0.25 H は a −1.3〜−4.9 m の前の面で、低い前の房（③）がない。左は 0.55 H の平らな白が c −20 m まで、尾が c −45 m（0.1 H）まで続く。",
        "target": {
            "r1": {"c_m": [-7.0, 9.0], "top_over_H0": [0.85, 1.0], "depth_m": ">= 48", "ja": "主の頂と唇。(a) の直しのほかは変えない。"},
            "r2": {"c_m": [-15.0, -8.0], "top_over_H0": [0.52, 0.60], "depth_m": "44〜47", "front_a_m": [4.0, 9.0],
                   "ja": "自分の丸い頂（肩）を持つ房。頂は 0.52〜0.60 H0、① の唇の板とは c −9〜−7 m の鞍（深さ 0.08〜0.12 H0 の切れ込み）で分ける。前の縁（爪の縁）は ① の内の面より 0.3 H0 以上前。"
                         "上から見て前の縁が ① の前の縁から 0.1 H0（2 m）以上下がる段を作る。原画視点の ② の画は変えない（射線の上で動かす）。"},
            "r3": {"c_m": [-21.0, -14.0], "top_over_H0": [0.36, 0.42], "depth_m": "40〜44", "front_a_m": [5.0, 9.0],
                   "ja": "最も左の小さな低い房。② より低く（頂の差 0.12〜0.2 H0）、② より手前（原画のカメラに 2〜4 m 近い）。② の下に 0.3 H0 あたりの引っ込み"
                         "（② の前の縁より 3〜7 m 後ろ。参照の肩の下の段と同じ比）を作り、その下の前へ ③ の房を 0.2〜0.25 H0（4〜5 m）出す。一艘目の船の舳先の上に爪が垂れる。"
                         "今の ③ の画（原画視点）は唇の下と前の面なので、射線の上で手前へ出して別の房にする（原画視点の画は変えない）。左の白（(b) で下げた生成り）はこの房の上の背。"},
        },
        "sculpture_sections_by_c": secs.get("ref", [])[:0],
    }

    # ---------------------------------------------------------------- (e) 背の一つの山（試算）
    dp_now = float(dip(H).max()); dp_new = float(dip(Hn).max())
    plan["e_keep"] = {"S4_crest_profile_dip_now_m": S.rnd(dp_now), "S4_crest_profile_dip_after_b_m": S.rnd(dp_new),
                      "argmax_c_now": S.rnd(cm[int(np.argmax(H))]), "argmax_c_after_b": S.rnd(cm[int(np.argmax(Hn))]),
                      "ja": "(b) の試算の頂の高さ H(c) は一つの山のまま（へこみ 0）。背の等高線の一つの山（AS02C の back_check の測り）は作り直しの後に測り直す。"
                            "別の青い波は主役波より低く（0.56〜0.62 H0）、主役波の背の左の奥にあるので、後ろ 65° と真後ろで二つ目の山に見えないか（S4）、"
                            "上から見て鰭や切り欠きにならないか（S3）を目で確かめる。"}
    plan["H_profile"] = {"c": S.rnd(cm, 2), "H_now": S.rnd(H, 2), "H_after_b": S.rnd(Hn, 2)}
    S.jdump(S.OUT + "/s4_plan.json", plan)
    print(json.dumps({"ext_now": ext_now, "ext_new": ext_new, "ref": ref_ext, "dip": [dp_now, dp_new], "th_ref": th_ref}, ensure_ascii=False))
    for q in blue:
        print(q["x_ref"], q["hero_crest_dist_m"], q.get("hero_plus_5m"))
    sheet(plan, cm, H, Hn, O)


def sheet(plan, cm, H, Hn, O):
    W, Hh = 2600, 1500
    Cv = Image.new("RGB", (W, Hh), (250, 248, 242))
    d = ImageDraw.Draw(Cv)
    d.text((18, 12), "調べ S-5：作り直しの計画（数）— 頂の高さ H(c)：今と (b) の試算、三つの層と青い波の置き場所", font=font(34, True), fill=(20, 20, 20))
    d.text((18, 60), "横軸 c（m、− が原画視点の左・手前）、縦軸 高さ（m）。図は試算で、形はまだ作っていない。参照モデルは帯の長さの数だけ（形は描かない）。", font=font(20), fill=(70, 70, 70))
    x0, x1, y0, y1 = 140, 1700, 140, 820
    cmin, cmax, hmax = -62.0, 18.0, 22.0

    def P(c, h):
        return (x0 + (c - cmin) / (cmax - cmin) * (x1 - x0), y1 - h / hmax * (y1 - y0))
    for cv in range(-60, 16, 5):
        d.line([P(cv, 0), P(cv, hmax)], fill=(228, 228, 228))
        d.text((P(cv, 0)[0] - 14, y1 + 6), "%d" % cv, font=font(18), fill=(80, 80, 80))
    for hv in range(0, 22, 4):
        d.line([P(cmin, hv), P(cmax, hv)], fill=(228, 228, 228))
        d.text((x0 - 50, P(cmin, hv)[1] - 12), "%d" % hv, font=font(18), fill=(80, 80, 80))
    d.line([P(cmin, 0), P(cmax, 0)], fill=(120, 120, 120), width=2)
    # 層の目標の帯
    T = plan["d_layers"]["target"]
    cols = {"r1": (215, 55, 55), "r2": (40, 160, 70), "r3": (30, 150, 200)}
    for k in ("r1", "r2", "r3"):
        c0, c1 = T[k]["c_m"]; h0, h1 = T[k]["top_over_H0"]
        a = P(c0, h1 * S.H0); b = P(c1, h0 * S.H0)
        d.rectangle([a[0], a[1], b[0], b[1]], outline=cols[k], width=4)
        d.text((a[0] + 4, a[1] - 28), {"r1": "① 目標", "r2": "② 目標", "r3": "③ 目標"}[k], font=font(20, True), fill=cols[k])
    d.line([P(c, h) for c, h in zip(cm, H)], fill=(60, 90, 160), width=4)
    d.line([P(c, h) for c, h in zip(cm, Hn)], fill=(230, 120, 30), width=3)
    # 青い波の頂（射線の上、主役波の頂 + 5 m）
    bl = [q["hero_plus_5m"] for q in plan["b_left"]["blue_wave_crest_on_rays"] if "hero_plus_5m" in q]
    for q in bl:
        p = P(q["c"], q["y"]); d.ellipse([p[0] - 6, p[1] - 6, p[0] + 6, p[1] + 6], fill=(20, 60, 200))
    p = P(-24, 8.5); d.line([P(-15.0, 12.2), P(-20, 10.5), P(-25, 7.0), P(-29, 2.0)], fill=(20, 60, 200), width=3)
    d.text((P(-50, 14.6)[0], P(-50, 14.6)[1]), "別の青い波の頂の点（④ の射線の上、主役波の頂 + 5 m）→ 画の外へ下りる（線は案）", font=font(18), fill=(20, 60, 200))
    d.text((P(-20, 5.2)[0], P(-20, 5.2)[1]), "②・③ の目標の箱は前の房の頂（同じ行の背の頂 H(c) ではない）", font=font(18), fill=(60, 60, 60))
    d.rectangle([P(cmin, hmax)[0], P(cmin, hmax)[1], P(-20.6, 0)[0], P(-20.6, 0)[1]], outline=(220, 170, 170), width=2)
    d.text((P(-60, 21)[0], P(-60, 21)[1]), "行 0〜62：原画の画の外（自由）", font=font(19), fill=(170, 90, 90))
    leg = [("今の頂の高さ H(c)（AS02C）", (60, 90, 160)), ("(b) の試算（左の白を楔の下の縁へ下げ、c −18 → −26 m で海へ）", (230, 120, 30)),
           ("青い波の頂の点", (20, 60, 200))]
    yy = y1 + 46
    for nm, col in leg:
        d.rectangle([x0, yy + 6, x0 + 28, yy + 26], fill=col)
        d.text((x0 + 36, yy), nm, font=font(20), fill=(30, 30, 30))
        yy += 32
    # 右：帯の長さの表
    bx = 1760
    d.text((bx, 140), "高さの帯の c の幅（m）", font=font(24, True), fill=(20, 20, 20))
    d.text((bx, 176), "帯     今      (b) 後    参照", font=font(21), fill=(40, 40, 40))
    b = plan["b_left"]
    for k, f in enumerate(["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]):
        d.text((bx, 210 + 32 * k), "%s H  %6.1f  %6.1f  %6.1f" % (f, b["band_extent_now_m"][f], b["band_extent_after_b_m"][f], b["band_extent_reference_m"].get(f, float("nan"))),
               font=font(21), fill=(30, 30, 30))
    d.text((bx, 520), "H は主役波のメッシュの最大 %.2f m。参照は台で" % b["H_ref_for_bands_m"], font=font(18), fill=(80, 80, 80))
    d.text((bx, 546), "切れているので低い帯は下限。", font=font(18), fill=(80, 80, 80))
    a = plan["a_bulge"]
    lines = [
        "(a) 出っ張り：c %.1f〜%.1f m（行 113〜133、行 108・138 で 0 へ）の唇の外の面（列 135〜197）を内の面の弧へ寄せ、唇の厚みを主の頂の行と同じ（列 170 %.2f m・列 185 %.2f m）にする。弧からの出 p50 1.3〜1.6 → ≤ 0.5 m。" % (
            a["where"]["c_full_m"][0], a["where"]["c_full_m"][1], float(a["lip_thickness_main_rows_m"]["170"]), float(a["lip_thickness_main_rows_m"]["185"])),
        "(b) 左：④ の輪郭は別の小さな青い波（頂 0.56〜0.62 H0、主役波の頂の 5 m 奥の射線の上）が作る。主役波の左の白は原画の楔の下の縁まで下げ（左端で 1.46 m）、c −18 → −26 m で海へ下ろす（今は c −60 m まで尾）。",
        "(c) 詰め：低い帯は (b) で参照に近づく（0.1 H %.0f → %.0f m、0.5 H %.0f → %.0f m）。高い帯（0.8・0.9 H）は射線の上の移しで第 2 段（D6 45° に触れる）。" % (
            b["band_extent_now_m"]["0.1"], b["band_extent_after_b_m"]["0.1"], b["band_extent_now_m"]["0.5"], b["band_extent_after_b_m"]["0.5"]),
        "(d) 層：① 主（c ≥ −7、0.85〜1.0 H0、深さ ≥ 48 m）／② 肩の房（c −15〜−8、頂 0.52〜0.60 H0、深さ 44〜47 m、① と鞍で分ける）／③ 小さな房（c −21〜−14、頂 0.36〜0.42 H0、深さ 40〜44 m、② より手前・低い）。",
        "(e) 背の一つの山：(b) の試算の H(c) のへこみ %.2f m（一つの山のまま）。青い波が後ろから二つ目の山に見えないか、上から鰭にならないかを目で確かめる。" % plan["e_keep"]["S4_crest_profile_dip_after_b_m"],
    ]
    yy = 1000
    for t in lines:
        d.text((40, yy), t, font=font(21), fill=(30, 30, 30))
        yy += 40
    Cv.save(S.OUT + "/s4_F_plan.png")


if __name__ == "__main__":
    main()
