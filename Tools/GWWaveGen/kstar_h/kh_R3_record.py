# -*- coding: utf-8 -*-
"""K*′ 精修 R3 の記録（py -3.10）：R2 の評審の must-fix 1〜5 への対応（R3 | R2 | A4 の数値）、決めたこと（Q24：推奨を選んだ理由）、
原画と基準がぶつかる所、評価基準 F03 を緩めたこと（理由と再現の証拠）、参照モデルとの意図した違い（D1〜D6）、動きの当て直しの試験。
入力は kh_R3_deliver.py の出力（評価器の要約・追加の表・BVH）、_work/R3 の実験の記録、見た目の審査（kstarR3_visual_review.json、手で書く）。
出力：kstarR3_difference_record.json、kstarR3_mustfix_table.md（R3 | R2 | A4 の表）、kstarR3_eval_table.md の末尾に付記。
  py -3.10 kh_R3_record.py <final dir>
"""
import os
import sys
import json

import numpy as np

sys.dont_write_bytecode = True


def chk(r, fid, name_part):
    for x in r["rubric"]["checks"].get(fid, []):
        if name_part in x["name"]:
            return {"name": x["name"], "value": x["value"], "must": x["must"], "pass_must": x["pass_must"]}
    return None


def val(r, fid, name_part):
    x = chk(r, fid, name_part)
    return None if x is None else x["value"]


def rnd(v, n=2):
    if v is None:
        return None
    if isinstance(v, (list, tuple)):
        return [rnd(x, n) for x in v]
    try:
        return round(float(v), n)
    except Exception:
        return v


def load(p, default=None):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else default


def main(d):
    summ = load(os.path.join(d, "eval", "kh_eval_summary.json"))
    cand = {x["label"]: x for x in summ["candidates"]}
    R3, R2, A4, KS = cand["R3"], cand["R2"], cand["A4"], cand.get("Kstar")
    sup = load(os.path.join(d, "kstarR3_supplementary.json"))
    bvh = load(os.path.join(d, "kstarR3_bvh_selfx.json"), {})
    rt = load(os.path.join(d, "kstarR3_retarget_ds28r01e.json"))
    rt2 = load(os.path.join(d, "_R2", "kstarR2_retarget_ds28r01e.json"))
    vis = load(os.path.join(d, "kstarR3_visual_review.json"), {})
    work = os.path.join(d, "_work", "R3")
    repro = load(os.path.join(work, "rubric_repro_R2.json"))
    lipexp = load(os.path.join(work, "lip_key_spacing_experiment.json"))
    design = load(os.path.join(d, "kstarR3_design.json"))
    rep = load(os.path.join(d, "kstarR3_deliver_report.json"), {})
    z = np.load(os.path.join(d, "kstarR3_a45_rows.npz"))
    c, A, Y = z["c"], z["A"], z["Y"]
    H = Y.max(1)
    H0 = float(H[int(np.argmin(np.abs(c)))])

    def per(fn):
        out = {}
        for lab, x, s in (("R3", R3, sup.get("R3")), ("R2", R2, sup.get("R2")), ("A4", A4, sup.get("A4"))):
            try:
                out[lab] = fn(x, s)
            except Exception as e:
                out[lab] = "n/a (%s)" % type(e).__name__
        return out

    def g(x, k, f="max_px"):
        return rnd(x["gate"][k][f])

    def glf(x, k, f):
        return rnd(x["gate_lf"][k][f])

    rt_rows = None
    if rt and rt.get("frames"):
        rt_rows = {k: {"section_selfx_rows": v.get("section_selfx_rows"), "local_selfx_vertices": v.get("local_selfx_vertices"),
                       "cross_row_gt30": v.get("cross_row_gt30"), "Hmax": rnd(v.get("Hmax"))} for k, v in rt["frames"].items()}
    rt2_rows = None
    if rt2 and rt2.get("frames"):
        rt2_rows = {k: {"section_selfx_rows": v.get("section_selfx_rows"), "local_selfx_vertices": v.get("local_selfx_vertices")} for k, v in rt2["frames"].items()}

    items = [
        {"id": "1", "item_ja": "Q21 のくびれと膨らみ（利用者が受け入れられないとした所）：上から見た背のくびれ notch ≤ 1.1 m（y 3〜6 m）、R6 p99 ≤ 0.6 m、R4 p99 ≤ 0.31 m、"
                                "目で見て v6・v9・u11・ターンテーブルにドーム・レモン形・くびれがない",
         "done_ja": "背の節点 back_shape を作った（外へ足すだけ、頂の近く 0.88 H より上・唇・中の面・原画の輪郭を作る列は動かない）："
                    "①back_env：各高さ 0.5〜8 m の背の平面の線を ±4 m の弦から 0.6 m より前へ出ない所まで外へ埋め、行ごとの量を c にならし、高さに比例するずらし"
                    "（断面の凸凹の数を変えない）で動かす（進行役の決定どおり F03 の殻・壁の必須を 0.42 へ緩めて使った）。②back_depth：肩の行（c ≤ −8.4）の背の奥行きの下限 0.6 H"
                    "（半分の高さ）。③back_tail：c ≥ 9 の奥の端の背を c 9 の背の相似な縮小へ寄せる。④back_smooth の奥の σ を 2.5 → 3.5 m。"
                    "⑤crest_lift（新しい節点の母数、far_smooth の節点の中）：奥の行（c ≥ 2.5）の頂のまわり（列 20〜186）を最大 1.4 m（c +7）上げる。唇の頭と唇先"
                    "（原画の輪郭 72）は動かない。u11・v9 のレモン形は、奥の頂が主断面より早く低くなり、唇の上面の舌が真ん中だけ大きいことから来ていた"
                    "（頂の高さ crest_height をそのまま上げると唇先も動き、72 の p95 が 33〜55 px に壊れた。試した）。",
         "result": per(lambda x, s: {"notch_y3_as_scripted": s["judge_R2_notch_as_scripted"]["y3"], "notch_y6_as_scripted": s["judge_R2_notch_as_scripted"]["y6"],
                                     "notch_y3_interior": s["judge_R2_notch_interior_chords"]["y3"], "notch_y6_interior": s["judge_R2_notch_interior_chords"]["y6"],
                                     "R4_p99": rnd(x["bulge6"]["R4"]["p99"], 3), "R6_p99": rnd(x["bulge6"]["R6"]["p99"], 3),
                                     "R6_p99_regions": s["bulge6_regions"]["R6"].get("regions_p99"), "R4_p99_regions": s["bulge6_regions"]["R4"].get("regions_p99")}),
         "notes_ja": ["評審の notch の台本（Unity/Build/Q20H/_judge_R2/rj_shape.py と同じ式）は、c −14〜−10.5 で弦の左の端が c −14 自身に留まるので、そこでは"
                      "『くびれ』ではなく平面の傾きの半分を返す。R3 の台本どおりの最大はこの端の値。弦の両端が測る範囲に入る所だけの値（interior）も並べた。",
                      "R2 のくびれ（c +3.5、2.11 / 2.15 m）は interior の値で比べる。"],
         "visual_ja": vis.get("item1")},
        {"id": "2", "item_ja": "きれいな網：三角形どうしの交差 0、裏返り 0、局所の自己交差 0、行をまたぐ折れ > 60° ≈ 0",
         "done_ja": "両端（奥 c > 0 と手前の肩の尾）の 1.5 m より低い行を、1.5 m の断面の a・y とも同じ比の縮小（相似）にし、最後の行も 0.4 % の極小の同じ形"
                    "（高さ 6 mm 以下）にした。平らな帯へ移す（R2 の奥）・ふくらみへ消す（R1・R2 の手前）のをやめた。三角形の面積 < 1e-6 m² は 0 のまま。",
         "result": per(lambda x, s: {"bvh_triangle_pairs": (bvh.get("R3" if x is R3 else "R2") or {}).get("pairs_all") if x is not A4 else None,
                                     "local_selfx_vertices": x["mesh"]["local_selfx_vertices_win6"], "flipped_quads": x["mesh"]["flipped_quads_gt150"],
                                     "cross_row_gt60": x["mesh"]["cross_row_gt60_all"], "cross_row_gt30": x["mesh"]["cross_row_gt30_all"],
                                     "degenerate_lt_1e-6": x["mesh"]["degenerate_lt_1e-6"], "min_tri_area_m2": x["mesh"]["min_tri_area_m2"],
                                     "edge_rows_absY_max": s["shape_checks"].get("edge_rows_absY_max")}),
         "notes_ja": ["最後の行（c +15 と c −60）の高さは 0 ではなく 6 mm 以下（極小の相似の断面）。外周の行を静水面にそろえる検査では 0.006 m と出る。"]},
        {"id": "3", "item_ja": "唇の縁の波打ち：lip_shift / lip_drop の鍵を 3 m 以上か、正則化する（爪の房の間の湾は段階6）",
         "done_ja": "鍵の間隔を 3 m・2 m・1.5 m・1.25 m・3 m ＋ 唇の頭の下面の厚みで試し、どれも原画の関門（72 の大きな輪郭 p95 ≤ 4 か 132 の大きな輪郭 ≤ 4）を"
                    "割った（_work/R3/lip_key_spacing_experiment.json）。関門は保つ項目なので、1 m の鍵のまま、区間ごとに c 方向の σ 1.5 m のならしへ寄せる"
                    "『正則化』を、関門（72 p95 ≤ 3.7、132 ≤ 3.93）を守る最大まで入れた（kh_R3_lipsmooth.py）。",
         "result": per(lambda x, s: {"bump4_d1_p99": s["bump4"]["d1_p99"], "bump4_d1_max": s["bump4"]["d1_max"], "lipedge_d1_p99": s["bump4"]["lipedge_d1_p99"],
                                     "72_lf_p95": glf(x, "72", "p95_px"), "132_lf_max": glf(x, "132", "max_px")}),
         "key_spacing_experiment": lipexp.get("runs") if lipexp else None,
         "lipsmooth_t_by_region": (design or {}).get("fit_log", {}).get("lipsmooth_log", {}).get("t"),
         "regions_c": (design or {}).get("fit_log", {}).get("lipsmooth_log", {}).get("regions"),
         "not_fixed_ja": "must-fix 3 は一部だけ。原画の唇の下の輪郭 72 の大きな輪郭（σ 12 px）には爪の房の間の湾（8〜12 px）が残り、p95 ≤ 4 px で合わせるには唇の頭を"
                         "c に沿って 1〜1.5 m の間隔で上下させる必要がある。主断面のまわり（c −4〜+1）は 132 もかかるので全くならせない（t = 0）。"
                         "解き方の候補（進行役・利用者の判断が要る）：(a) 段階6 で湾を爪の房として作り、唇の縁そのものはならす、(b) 72 の大きな輪郭を湾も除く線"
                         "（σ を大きく、または湾を閉じる形態の処理）に定義し直す、(c) 72 の p95 の上限を 6〜7 px に緩める（2 m の鍵で 6.3 px）。"},
        {"id": "4", "item_ja": "b 区域：1 枚の棚ではなく 3 つの大きな房（u13・v3）。稜 p90 ≤ 15 px、最大 ≤ 30 px、または帯の右の端に届かない理由",
         "done_ja": "稜の房（c −16.5 / −11.5 / −6.5）を、断面の法線ではなく原画カメラの視線を断面の面へ写した向きに −1.2 m（房の間は +0.6 m）動かす"
                    "節点 ledge_lobe_depth を足した。法線の向きの房（ledge_lobe）を 1.1 / 1.5 m に強めると稜の差の中央値が 16.7 / 23 px に悪化した（試した）。",
         "result": per(lambda x, s: {"ridge_median_p90_max_px": [rnd(x["Q21_3"]["top_vs_top_smooth"][k], 1) for k in ("median_px", "p90_px", "max_px")] if x.get("Q21_3", {}).get("top_vs_top_smooth") else None,
                                     "ridge_covered": [x["Q21_3"]["top_vs_top_smooth"].get("covered_samples"), x["Q21_3"]["top_vs_top_smooth"].get("target_samples")] if x.get("Q21_3", {}).get("top_vs_top_smooth") else None,
                                     "claw_median_p90_max_px": [rnd(x["Q21_3"]["bottom_vs_bottom_smooth"][k], 1) for k in ("median_px", "p90_px", "max_px")] if x.get("Q21_3", {}).get("bottom_vs_bottom_smooth") else None}),
         "notes_ja": ["稜の最大は帯の右の端（原画 x 600〜710、c −6〜−3.5）で決まる。そこは主断面の唇の頭の上で、稜の検出（谷の後の最小）が届かない試料がある（R2 と同じ理由）。"],
         "visual_ja": vis.get("item4")},
        {"id": "5", "item_ja": "評価基準の新しい必須の否（F02 奥の行の弦角 107°、F05 最長の直線 0.40 H at c −3.4）を記録し、受け入れる理由を書く",
         "result": per(lambda x, s: {"F02_far_chord": rnd(val(x, "F02", "chord_pm2m_deg（奥")), "F02_far_fold": rnd(val(x, "F02", "fold_deg（1 頂点の折れ、奥")),
                                     "F05_longest_straight": rnd(val(x, "F05", "最長 / H(c)"))}),
         "why_accepted_ja": ["F02 奥の行の弦角：奥の行（c > +3）は唇先が原画の管の輪郭 72 を描き、頂は唇の頭の 1〜2 m 上にしか置けない。頂の ±2 m の弦に唇の頭が入るので"
                             "弦角は鋭く出る（R1 132°、R2 107°）。R2・R3 は奥の頂も背のならしで丸めている（1 頂点の折れは基準内）。奥の頂のならしを列 120 / 96 までに"
                             "減らすと 1 頂点の折れが 14.2° / 65.8° になり、弦角も 107° / 120° で通らなかった（試した）。",
                             "F05 最長の直線：c −3.6〜−3.4 の唇の上面の、唇の頭の移動と b 区域の稜の端の間の区間。稜の端を消すと 132 の大きな輪郭が 4.70 px に戻り関門を割る"
                             "（R2 で試した）。R3 は 132 の所（c −4〜+1）の唇の鍵を動かしていないので同じ値。"]},
        {"id": "keep", "item_ja": "保つもの：大きな輪郭の関門、どの断面でも丸い頂（Q17）、台座なし、満ちた量感、樽と唇の巻き、奥の細い巻き、唇の間隔 > 0、色の焼き直しの UV",
         "result": per(lambda x, s: {"78": g(x, "78"), "130": g(x, "130"), "131": g(x, "131"), "132_lf": glf(x, "132", "max_px"), "72_lf_p95": glf(x, "72", "p95_px"),
                                     "gate_pass_lf": x.get("gate_pass_lf"), "F02_main_Rmin_theta_chord_fold": [rnd(val(x, "F02", "Rmin_m（c -5")), rnd(val(x, "F02", "theta_c_deg（c -5")),
                                                                                                             rnd(val(x, "F02", "chord_pm2m_deg（c -5")), rnd(val(x, "F02", "fold_deg（1 頂点の折れ、c -5"))],
                                     "F08_step_trough": [rnd(val(x, "F08", "鉛直の段")), rnd(val(x, "F08", "前の谷"))],
                                     "fullness_area_shell_ratio": [rnd(x["Q21_2"].get("ratio_area_over_H2")), rnd(x["Q21_2"].get("ratio_shell_over_H"))],
                                     "lip_clearance_min_m": s["shape_checks"].get("lip_clearance_min_m"), "section_selfx_rows": s["shape_checks"].get("section_selfx_rows"),
                                     "F13_within_0p3m": rnd(x["F13_proximity"]["within_0p3m"], 4) if x.get("F13_proximity") else None}),
         "uv_ja": "UV は kh_bridge.py が K* と同じ並び（K* の uv / uv2）を付ける（トポロジーは K* と同じ 400×240。deliver_report の bridge.checks.topology_same_as_kstar）。"},
    ]
    rubric_f03 = {
        "change_ja": "2026-09-29（R3、進行役の決定 Q24 の記録）：評価基準 F03 の必須を 2 つ緩めた。殻の厚み（背の法線、中央値）/ H：0.20〜0.34 → 0.20〜0.42、"
                     "壁 0.5H（水平）/ H：≤ 0.36 → ≤ 0.42。目標（0.22〜0.30、≤ 0.32）は変えない。",
        "reason_ja": "0.34・0.36 は Q20 の評価基準を作った時の我々の暫定の数（参照の 0.23〜0.31 から置いた）で、利用者の決定ではない。R2 で上から見たくびれを後ろから埋めると"
                     "本体の行（c −5〜+4）の殻が 0.37〜0.43 H になり、この必須とぶつかった。利用者の Q21（くびれ・中の膨らみがない、満ちた量感）を優先する。",
        "where": "Tools/GWWaveGen/rubric/rubric_check.py（日付つきの注）と rubric_ja.md の冒頭の追記",
        "repro": repro,
        "R3_values": {"shell": val(R3, "F03", "殻の厚み"), "wall": val(R3, "F03", "壁 0.5H")},
    }
    rec = {
        "schema": "GreatWave.kstar_h.R3.difference_record/1",
        "candidate": "K*' R3 (Houdini, refinement loop 3; lineage H1A -> R1 -> R2 -> R3)",
        "reference": "wave_repair_zbrush2.obj - a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18). "
                     "Reference only: layout, proportions and 3-D large forms (Q18-Q20). It is never read by the generator or the fit.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18、確かめるまで開いたまま）。"
                     "配置・比率・大きな形の考え方だけを参考にし、形は写していない（生成器と当てはめは参照の網を読まない）。",
        "method_ja": "形は Houdini の網（Houdini/Design28R01/kstar_h_R3.hiplc の /obj/kstar_h_design：CTRL の ramp → 断面の案内の曲線 → 奥の形のならし → "
                     "背の形（R3：外へ・ならし・奥の端の相似・奥行きの下限・くびれを埋める）→ 唇の上面の断面の形 → b 区域（R3：房を視線の向きへ）→ 唇の頭 → 側の縁 → Skin）が作る。"
                     "参照モデルは F13 と量感の比較の数値のためにだけ、評価器が一時のキャッシュで読み、消す（SHA-256 を Q20H/deleted_caches_sha256.txt に記録）。"
                     "シーンには参照の節点・参照のパスの文字列・参照から作った候補（第 3 回の A3b）の節点を残さない。",
        "scene": {k: (rep.get("scene") or {}).get(k) for k in ("saved", "hip_bytes", "hiplc_sha256", "removed_reference_nodes", "reference_path_leaks",
                                                               "reference_strings_in_hiplc", "verify")},
        "gwb_sha256": (rep.get("bridge") or {}).get("gwb_sha256"),
        "F13_proximity_all_reference_vertices": R3.get("F13_proximity"),
        "must_fix_responses_R2_judge": items,
        "rubric_F03_relaxation": rubric_f03,
        "deliberate_differences": [
            {"id": "D1", "what_ja": "背の輪郭をもっと滑らかに（樽の中心のまわりの同心の殻、彫りの波なし）。R3：背を波峰に沿ってならし、上から見たくびれを外へ埋めた",
             "F03_inflections": chk(R3, "F03", "曲率の符号"), "F03_roughness": chk(R3, "F03", "ざらつき"), "reference": "変わり目 3〜5、ざらつき 10〜26（×1e-3）"},
            {"id": "D2", "what_ja": "球の台座なし。足は前の谷へ流れ、谷から前の海へ一続き", "F08_step": chk(R3, "F08", "鉛直の段"), "F08_trough": chk(R3, "F08", "前の谷")},
            {"id": "D3", "what_ja": "唇先は原画の大きな輪郭（σ 12 px）に合わせたなめらかな鉤。爪・指は作らない（段階6）", "gate_large_form": {k: R3["gate_lf"][k] for k in ("132", "72")}},
            {"id": "D4", "what_ja": "b 区域の稜と爪の縁は原画の帯から（参照の房・指の位置は使わない）。R3：3 つの房を原画の視線の向きへ", "Q21_3": R3.get("Q21_3")},
            {"id": "D5", "what_ja": "奥の端は我々の設計：唇先が原画の管の内側の輪郭 72 を描き、c +15 で相似に縮む巻きで閉じる（R3：最後まで巻きの形、極小の頂点で閉じる）",
             "H_over_H0_far": {("c=%+.0f" % cc): round(float(H[int(np.argmin(np.abs(c - cc)))] / H0), 3) for cc in (4, 6, 8, 10, 12, 13, 14, 15)},
             "F05_far_mass": chk(R3, "F05", "奥の端")},
            {"id": "D6", "what_ja": "手前の頂の線は原画の外輪郭（78/130/131）が決める。主断面 H0 と最高点は c −1〜+3", "gate": {k: R3["gate"][k] for k in ("78", "130", "131")},
             "H0_m": H0, "highest": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])}},
        ],
        "decisions_taken_ja": [
            "R2 の系統（H1A → R1 → R2）を続け、R2 の本体の母数（頂の線・唇・管・殻・唇の上面の断面の形・側の縁）はそのまま使った（関門を保つ）。",
            "F03 と back_fill のぶつかりは進行役の決定（Q24）どおり Q21 を優先し、F03 の殻・壁の必須を 0.42 に緩めた。R2 の back_fill（走る包絡）ではなく、"
            "評審の notch と同じ定義（±4 m の弦）で埋める back_env を新しく作った（R2 の back_fill は 0.15 m/m の前への戻りの上限だけで、奥へ振れる頂の線の所で埋めきれない）。",
            "『奥の行の背を外へ埋める方を先に』（進行役の推奨）は試した：奥（c ≥ 6.5）に背の奥行きの下限 0.5〜0.6 H を入れると、奥の背が後ろへ出る分だけ c +2〜+5 の"
            "くびれが深くなり、それを埋めると本体の行の殻が 0.44〜0.48 H になって緩めた 0.42 も割った。奥には相似の尾（back_tail）とならし σ 3.5 m だけを使った。",
            "肩（c ≤ −8.4）は背の奥行きの下限 0.6 H で外へ満たした（肩が細く主断面が太いレモン形を減らす。評審の notch の台本の端の値も下がる）。",
            "両端の閉じ方を相似に縮む錐にした（網の交差・裏返りをなくす）。",
            "唇の頭の鍵は 1 m のまま正則化（関門を保つ項目を優先。must-fix 3 は一部）。",
            "奥の頂を上げる crest_lift を入れた（膨らみの測り R6 p99 は少し上がる：頂の持ち上げなし 0.84 → 0.89。目で見たレモン形と F10 の平面の頂の線の折れ 136° → 76° の改善を優先）。"
            "c ≤ 2 の行（原画の 132 を描く）は上げない（c 0 から上げると 132 が 4.49 px で関門を割った。試した）。",
            "b 区域の房は視線の向きの凹凸で作った（稜の差の p90 が下がる向き）。法線の向きの大きな房は原画の帯から外れる。",
            "評価基準の道具をリポジトリへ写し、kh_eval.py が写しを確実に読むように直した（fin_eval が Git 対象外の道具を先に読む順序の問題も直した）。",
            "何も commit していない。Unity は使っていない。大きな出力は Unity/Build/Q20H（git の外）。",
        ],
        "conflicts_ja": [
            "must-fix 3（唇の鍵 ≥ 3 m）と、保つ関門（72 の大きな輪郭 p95 ≤ 4）は両立しない（上の item 3）。",
            "評審の R6 p99 ≤ 0.6 m・R4 p99 ≤ 0.31 m：R6 の残りは奥の端（c +10〜+13、背の上半分）と肩の b 区域（唇の上面の稜）。奥の端は、唇先が原画の管の輪郭 72 を描くため c +13 まで"
            "高さ 7 m 以上を保ち、c +15 で 0 まで落とす（網は c +15 で終わる）ので、6 m の広さの 2 次曲面に乗らない。A4 は奥の端を c +7 から低くしている（その代わり 72 の"
            "大きな輪郭 p95 9.65 px で関門を割る）。肩の b 区域は第二の波頭の稜と房そのもので、must-fix 4 の『大きな房』と R4 / R6 の上限はぶつかる。",
            "F10 奥で頂の線が後ろへ流れる角 ≤ 20°、F04 の幅、F05 奥の固まり ≤ 3 m は、奥の行の唇先が原画の管の輪郭 72 を描くことと両立しない（R1・R2 と同じ）。",
        ],
        "retarget_ds28r01e": {"R3": rt_rows, "R2": rt2_rows, "R3_build_ok": (rt or {}).get("build_ok"), "R3_Hmax_all_frames": (rt or {}).get("Hmax_all_frames"),
                              "R3_tstar": {k: rt["frames"]["0"].get(k) for k in ("tstar_vs_cand_max_m", "tstar_vs_cand_p99_m")} if rt and rt.get("frames") else None},
        "visual_review": vis,
        "design_keys_file": "kstarR3_design.json",
        "fit_log": (design or {}).get("fit_log"),
    }
    # rubric: every check whose MUST result differs between R2 and R3 (the R2 row is re-evaluated with the same, relaxed rubric)
    chg = []
    for fid, lst in R3["rubric"]["checks"].items():
        for x in lst:
            y = next((t for t in R2["rubric"]["checks"].get(fid, []) if t["name"] == x["name"]), None)
            if y is None:
                continue
            if bool(x["pass_must"]) != bool(y["pass_must"]) or (isinstance(x["value"], float) and isinstance(y["value"], float)
                                                               and abs(x["value"] - y["value"]) > 0.05 * max(abs(y["value"]), 1e-6)):
                chg.append({"check": "%s %s" % (fid, x["name"]), "R2": rnd(y["value"], 3), "R3": rnd(x["value"], 3), "must": x["must"],
                            "R2_pass": y["pass_must"], "R3_pass": x["pass_must"]})
    rec["rubric_changes_vs_R2"] = chg
    rec["rubric_must_fail"] = {"R3": R3["rubric"]["summary"], "R2": R2["rubric"]["summary"], "A4": A4["rubric"]["summary"]}
    json.dump(rec, open(os.path.join(d, "kstarR3_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # the R3 | R2 | A4 table of the must-fix targets
    import datetime
    L = ["# K*′ R3：評審 R2 の must-fix の目標と R3 | R2 | A4（%s）" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
         "値は `kstarR3_difference_record.json`（評価器 `eval/kh_eval_summary.json`、追加の表 `kstarR3_supplementary.json`、BVH `kstarR3_bvh_selfx.json`）から。", "",
         "| # | 項目 | 目標 | R3 | R2 | A4 |", "| --- | --- | --- | --- | --- | --- |"]

    def cell(it, k, sub=None, f=lambda v: v):
        out = []
        for lab in ("R3", "R2", "A4"):
            v = it["result"].get(lab)
            if isinstance(v, dict):
                v = v.get(k)
                if sub is not None and isinstance(v, dict):
                    v = v.get(sub)
            out.append(f(v))
        return out

    def fm(v):
        if v is None:
            return "—"
        if isinstance(v, dict) and "notch_max_m" in v:
            return "%.2f m（c %s）" % (v["notch_max_m"], v["at_c"])
        if isinstance(v, float):
            return "%.3g" % v
        if isinstance(v, list):
            return " / ".join(fm(x) for x in v)
        return str(v)
    it = {x["id"]: x for x in items}
    rows = [("1", "くびれ notch y 3 m（評審の台本のまま）", "≤ 1.1 m", "notch_y3_as_scripted"),
            ("1", "くびれ notch y 6 m（評審の台本のまま）", "≤ 1.1 m", "notch_y6_as_scripted"),
            ("1", "くびれ notch y 3 m（弦の両端が範囲の中）", "≤ 1.1 m", "notch_y3_interior"),
            ("1", "くびれ notch y 6 m（弦の両端が範囲の中）", "≤ 1.1 m", "notch_y6_interior"),
            ("1", "膨らみ R6 p99", "≤ 0.6 m", "R6_p99"), ("1", "膨らみ R4 p99", "≤ 0.31 m", "R4_p99"),
            ("2", "三角形どうしの交差（BVH）", "0", "bvh_triangle_pairs"), ("2", "裏返り", "0", "flipped_quads"),
            ("2", "局所の自己交差の頂点", "0", "local_selfx_vertices"), ("2", "行をまたぐ折れ > 60°", "≈ 0", "cross_row_gt60"),
            ("3", "唇の縁 bump4 d1 p99（評審の式）", "R1 0.28 に近く", "bump4_d1_p99"), ("3", "72 大きな輪郭 p95", "≤ 4 px（保つ）", "72_lf_p95"),
            ("4", "b 区域 稜 中央値 / p90 / 最大", "p90 ≤ 15、最大 ≤ 30 px", "ridge_median_p90_max_px"),
            ("5", "F02 奥の行の弦角", "≥ 125°（必須）", "F02_far_chord"), ("5", "F05 断面の最長の直線 / H", "≤ 0.35（必須）", "F05_longest_straight"),
            ("keep", "原画 78 / 130 / 131 最大", "≤ 4 px", None), ("keep", "132 大きな輪郭 最大", "≤ 4 px", "132_lf"),
            ("keep", "量感の比（面積 / 殻）", "≥ 0.90", "fullness_area_shell_ratio"), ("keep", "唇の間隔の最小", "> 0 m", "lip_clearance_min_m")]
    for iid, name, tgt, key in rows:
        if key is None:
            vals = []
            for lab in ("R3", "R2", "A4"):
                v = it["keep"]["result"][lab]
                vals.append("%s / %s / %s" % (v["78"], v["130"], v["131"]) if isinstance(v, dict) else "—")
        else:
            vals = [fm(v) for v in cell(it[iid], key)]
        L.append("| %s | %s | %s | %s | %s | %s |" % (iid, name, tgt, vals[0], vals[1], vals[2]))
    L += ["", "目で見た所（v6・v9・u11・u13・ターンテーブル）は `kstarR3_visual_review.json` と記録の visual_review。", ""]
    if rt_rows:
        L += ["## 動きの当て直しの試験（E の生成器、`kh_R1_retarget.py R3 Unity/Build/Q20H/final …`）", "",
              "| τ [s] | " + " | ".join(sorted(rt_rows, key=float)) + " |", "| --- |" + " --- |" * len(rt_rows)]
        for k, lab in (("section_selfx_rows", "断面の自己交差の行 R3"), ("local_selfx_vertices", "局所の自己交差の頂点 R3"), ("cross_row_gt30", "行をまたぐ折れ > 30° R3"),
                       ("Hmax", "最高点 [m] R3")):
            L.append("| %s | " % lab + " | ".join(str(rt_rows[t].get(k)) for t in sorted(rt_rows, key=float)) + " |")
        if rt2_rows:
            for k, lab in (("section_selfx_rows", "断面の自己交差の行 R2"), ("local_selfx_vertices", "局所の自己交差の頂点 R2")):
                L.append("| %s | " % lab + " | ".join(str(rt2_rows.get(t, {}).get(k)) for t in sorted(rt_rows, key=float)) + " |")
        L += ["", "生成：%s、t* の差の最大 %s m。" % ((rt or {}).get("build_ok"), fm((rec["retarget_ds28r01e"].get("R3_tstar") or {}).get("tstar_vs_cand_max_m"))), ""]
    open(os.path.join(d, "kstarR3_mustfix_table.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    # appendix to the evaluation table
    tp = os.path.join(d, "kstarR3_eval_table.md")
    if os.path.isfile(tp):
        t = open(tp, encoding="utf-8").read()
        mark = "\n\n## R3 の付記（kh_R3_record.py）\n"
        if mark in t:
            t = t[:t.index(mark)]
        app = [mark,
               "- **評価基準 F03 を緩めた（2026-09-29、進行役の決定 Q24 の記録）**：殻の厚み 0.20〜0.34 → 0.20〜0.42 H、壁 0.5H ≤ 0.36 → ≤ 0.42。0.34・0.36 は評価基準を作った時の我々の暫定の数で、"
               "利用者の決定ではない。R2 で上から見たくびれを後ろから埋めると本体の行の殻が 0.37〜0.43 H になってぶつかったので、利用者の Q21（くびれ・中の膨らみがなく満ちた量感）を優先した。"
               "目標は変えない。表の F03 の行の『基準』はこの版。R3 の値：殻 %s、壁 %s。" % (fm(val(R3, "F03", "殻の厚み")), fm(val(R3, "F03", "壁 0.5H"))),
               "- **道具の再現**：評価基準の道具を Git 対象外の `Unity/Build/Q20/rubric/tools/` からリポジトリの `Tools/GWWaveGen/rubric/` へ写し（`rubric_check.py`・`rubric_measure.py`・"
               "`rubric_ja.md`）、kh_eval.py が写しを読むようにした。写した直後の道具（SHA-256 同じ）と、緩めた後の写しの両方で R2 を評価し直し、R2 の列の 93 行の値が同じ"
               "（変わったのは F03 の 2 行の『基準』の文字だけ）ことを確かめた（`_work/R3/rubric_repro_R2.json`）。",
               "- **受け入れた必須の否（R2 からの新しいもの）**：F02 奥の行の弦角（R3 %s°）と F05 断面の最長の直線（R3 %s H）。理由は `kstarR3_difference_record.json` の item 5。"
               % (fm(val(R3, "F02", "chord_pm2m_deg（奥")), fm(val(R3, "F05", "最長 / H(c)"))),
               "- **上から見た背のくびれ（評審 R2 の notch、±4 m の弦からの前への出）**：R3 は y 3 m %s、y 6 m %s（評審の台本のまま）／ %s、%s（弦の両端が範囲の中の所だけ）。"
               "R2 は c +3.5 で 2.11 / 2.15 m、A4 は 1.13 / 1.10 m。"
               % (fm(sup["R3"]["judge_R2_notch_as_scripted"]["y3"]), fm(sup["R3"]["judge_R2_notch_as_scripted"]["y6"]),
                  fm(sup["R3"]["judge_R2_notch_interior_chords"]["y3"]), fm(sup["R3"]["judge_R2_notch_interior_chords"]["y6"])),
               "- **網の衛生（Blender BVH の三角形どうしの交差）**：R3 %s 組、R2 %s 組（`kstarR3_bvh_selfx.json`）。"
               % ((bvh.get("R3") or {}).get("pairs_all"), (bvh.get("R2") or {}).get("pairs_all")),
               "- 評審 R2 の測り（くびれ notch・R4 / R6 の区域・bump4・網の衛生・BVH）と R3 | R2 | A4 の表は `kstarR3_mustfix_table.md`。動きの当て直しは `kstarR3_retarget_ds28r01e.json`"
               "（こまごとの断面の自己交差の行も `kstarR3_mustfix_table.md` の末尾）。"]
        open(tp, "w", encoding="utf-8").write(t + "\n".join(app) + "\n")
    print(open(os.path.join(d, "kstarR3_mustfix_table.md"), encoding="utf-8").read())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
