# -*- coding: utf-8 -*-
"""K*′ 精修 R2 の記録：参照モデルとの意図した違い（D1〜D6、数値つき、出典）、R1 の評審の must-fix への対応（数値つき）、決めたこと
（推奨を選んだもの）、原画と基準がぶつかる所（py -3.10）。入力は kh_R2_deliver.py の出力（評価器の要約と追加の表）と R1 の記録だけ。
  py -3.10 kh_R2_record.py <final dir>
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


def main(d):
    summ = json.load(open(os.path.join(d, "eval", "kh_eval_summary.json"), encoding="utf-8"))
    cand = {x["label"]: x for x in summ["candidates"]}
    r = cand["R2"]; r1 = cand.get("R1"); a4 = cand.get("A4")
    sup = json.load(open(os.path.join(d, "kstarR2_supplementary.json"), encoding="utf-8"))
    design = json.load(open(os.path.join(d, "kstarR2_design.json"), encoding="utf-8"))
    z = np.load(os.path.join(d, "kstarR2_a45_rows.npz"))
    c, A, Y = z["c"], z["A"], z["Y"]
    H = Y.max(1)
    H0 = float(H[int(np.argmin(np.abs(c)))])
    far = {("c=%+.0f" % cc): round(float(H[int(np.argmin(np.abs(c - cc)))] / H0), 3) for cc in (4, 6, 8, 10, 12, 13, 14, 15)}
    selfx = None
    p = os.path.join(d, "kstarR2_bvh_selfx.json")
    if os.path.isfile(p):
        selfx = json.load(open(p, encoding="utf-8")).get("R2")
    rt = None
    p = os.path.join(d, "kstarR2_retarget_ds28r01e.json")
    if os.path.isfile(p):
        q = json.load(open(p, encoding="utf-8"))
        rt = {"build_ok": q.get("build_ok"), "Hmax_all_frames": q.get("Hmax_all_frames"),
              "tstar": {k: q["frames"]["0"].get(k) for k in ("tstar_vs_cand_max_m", "tstar_vs_cand_p99_m")} if q.get("frames") else None}

    def pair(key_fn):
        out = {}
        for lab, x in (("R2", r), ("R1", r1), ("A4", a4)):
            try:
                out[lab] = key_fn(x)
            except Exception:
                out[lab] = None
        return out

    def g(x, k, f="max_px"):
        return round(x["gate"][k][f], 2)

    def glf(x, k, f):
        return round(x["gate_lf"][k][f], 2)

    must_fix = [  # noqa
        {"id": "M1", "item_ja": "原画の関門（132 大きな輪郭 最大 ≤ 4、72 大きな輪郭 p95 ≤ 4、78/130/131 ≤ 4）。輪郭を作る縁だけで。",
         "done_ja": "唇の頭の節点 lip_head を足した：唇の頭（列 186〜214、列 140 / 268 までなめらかに 0）を唇先の法線の向き（lip_shift）と鉛直に下"
                    "（lip_drop）へまとめて動かす。唇の上面の細い側の縁 edgeL（12 本、視線がかすめる所だけ）で 132。解き方は kh_R2_sil.py（公式の測り方を"
                    "線形化、よくなる時だけ進む）。R1 の細い唇先の帯 edge_tip と管の壁の帯 edge_6〜9（±0.3 m の逆向きの S）は 0 にした。",
         "result": pair(lambda x: {"132_lf_max": glf(x, "132", "max_px"), "72_lf_p95": glf(x, "72", "p95_px"), "78": g(x, "78"), "130": g(x, "130"),
                                   "131": g(x, "131"), "pass_lf": x.get("gate_pass_lf")})},
        {"id": "M2", "item_ja": "奥の背の膨らみ・上から見た S 字（R4 p99 ≤ 0.31、c +9〜+12 の撓み、F10、v6 のくびれ）",
         "done_ja": "背のならしの節点 back_smooth を足した（背の点の平面の位置を c に沿って σ 0.5〜2.5 m でならす。奥の行 c ≥ 5 では頂と唇の上面の"
                    "前半（列 150 まで、列 80 から 70 列でぼかす）もならす。唇の頭と中の面は動かさない。左右対称の窓で端の行を持ち上げない）。",
         "result": pair(lambda x: {"R4_p99": round(x["bulge6"]["R4"]["p99"], 3), "R6_p99": round(x["bulge6"]["R6"]["p99"], 3),
                                   "R4_regions": x["bulge6"]["R4"].get("regions"),
                                   "F10_plan_turn_deg": val(x, "F10", "2 m あたり"), "sag3m_p99": round(x["Q21_1"]["sag_3m"]["p99_m"], 3)}),
         "remaining_ja": "奥の背（c +9〜+12、列 40〜90）はまだ最も高い（A4 の 0.31 に届かない）。奥の行は唇先が原画の管の輪郭 72 を描き、頂はその 1〜2 m 上に"
                         "しか置けないので、15 m の高さの背がほぼ鉛直の壁になり（c +7〜+9）、c +10 から傾く。その変わり目が残る。平面の頂の線は原画の管の口に"
                         "出ないため c +10 で向きを変える（R1 と同じ理由）。上から見た c 0〜+4 のくびれは、背を後ろから埋めると消えるが F03 の殻の厚み・壁の必須を割るので残した"
                         "（背の埋め back_fill の節点は値 0 で残す）。"},
        {"id": "M3", "item_ja": "後ろから見た頂のレモン形（v9 / u11）",
         "done_ja": "背のならしで主断面の背と奥の背の段差を小さくした。H(c) は原画の外輪郭 78/130/131 が決めるので、肩が低く主断面が高い形そのものは残る。"},
        {"id": "M4", "item_ja": "b 区域：薄い帯 2〜3 枚ではなく厚みのある 3 つの房。稜 p90 ≈ 10〜15 px、最大 ≤ 約 30 px",
         "done_ja": "稜の幅を 0.08〜0.10 → 0.13〜0.16（列の比）に広げ、谷の深さを 0.85 → 0.5（× 強さ）に浅くし、稜の強さを c に沿って 3 つの房"
                    "（c −16.5 / −11.5 / −6.5、間を 0.25 m 下げる）で変えた。唇の上面を外へ押すだけ（下面は動かさない）なので、房の分だけ唇が厚い。"
                    "kh_R2_fit の ledge2 / ledge3 で原画の帯へ合わせた。",
         "result": {"band": sup.get("band_round3_detector"), "Q21_3": r.get("Q21_3", {}).get("top_vs_top_smooth"),
                    "R4_crest_liptop_shoulder": (r["bulge6"]["R4"].get("regions") or {}).get("crest_liptop/shoulder")},
         "remaining_ja": "帯の右の端（原画 x 600〜710、c −6〜−3.5 の行）は主断面の唇の頭の上にあり、稜の検出が届かない（覆われない試料 = 40 px）。p90 はこの端で決まる。"},
        {"id": "M5", "item_ja": "閉じる行 c +14〜+15 の行をまたぐ折れ（F11 > 30° ≤ 50、> 60° ≈ 0）と裏返り",
         "done_ja": "巻きを「ふくらみ」へ消すのをやめ（R1 は H 3.5 → 2.0 m の 2〜3 行で形が変わった）、1.5 m より低い行は断面を a と y の両方で同じ比に縮める"
                    "（R1 は縦だけ押しつぶした）。0.9 m より低い最後の行だけ単調な帯へ移す。低い行の唇の頭の移動もそこで 0 にした。"
                    "手前の肩の端（c ≤ 0、行が疎）は R1 の消し方のまま。",
         "result": pair(lambda x: {"F11_gt30": val(x, "F11", "> 30"), "mesh_gt30_all": x["mesh"].get("cross_row_gt30_all"),
                                   "mesh_gt60_all": x["mesh"].get("cross_row_gt60_all"), "flipped": x["mesh"].get("flipped_quads_gt150")})},
        {"id": "M6", "item_ja": "lip_clearance −0.171 m（7 行）を証明するか直す",
         "done_ja": "直った：唇の頭をまとめて動かし、細い唇先の帯をやめたので、全行で唇の上面と下面の符号つきの間隔が正。三角形どうしの交差の検査（Blender BVH）も記録。",
         "result": {"lip_clearance_min_m": sup.get("shape_checks", {}).get("lip_clearance_min_m"),
                    "rows_lt0": sup.get("shape_checks", {}).get("lip_clearance_rows_lt0"), "bvh_triangle_pairs": selfx},
         "remaining_ja": "三角形の交差は最後の帯（c +14.8 の高さ 0.7 m の小さな巻きと c +15 の平らな行の間）だけに残る（R1 は 0）。唇の交差ではない。"
                         "この 1 行を平らにすると c +14.6〜+14.8 で行をまたぐ折れ > 60° が 47〜106 に増えた（試した）。"},
        {"id": "M7", "item_ja": "管の壁 F07 の曲がり（≤ 50°/m）と丸さ（≤ 0.18）",
         "done_ja": "曲がりの最大は唇先のすぐ後ろ（列 207〜213）の鉤の下面で、R1 の細い唇先の帯（σ 6 列で ±0.35 m）が作っていた。帯をやめ、唇の頭をまとめて動かした。",
         "result": pair(lambda x: {"wall_turn": val(x, "F07", "曲がり"), "roundness": val(x, "F07", "丸さ"), "R_over_H": val(x, "F07", "半径")}),
         "remaining_ja": "曲がりはまだ 50°/m を超える（鉤の引き込み hook_depth 0.08〜0.15 の行 c +0.5〜+5）。丸さ 0.22 は R1 と同じ。"},
        {"id": "M8", "item_ja": "通っているものを保つ",
         "result": pair(lambda x: {"H0": round(float(x["shape"]["H0"]), 2) if isinstance(x.get("shape"), dict) and "H0" in x["shape"] else None,
                                   "F02_main_Rmin": val(x, "F02", "Rmin_m（c -5"), "F08_trough": val(x, "F08", "前の谷"),
                                   "fullness_area": round(x["Q21_2"]["area_over_H2_mean_c-2_2"] / x["Q21_2"]["reference"]["area_over_H2_mean"], 2),
                                   "F13": round(x["F13_proximity"]["within_0p3m"], 4)}),
         "retarget_ds28r01e": rt},
    ]
    rec = {
        "schema": "GreatWave.kstar_h.R2.difference_record/1",
        "candidate": "K*' R2 (Houdini, refinement loop 2; lineage H1A -> R1 -> R2)",
        "reference": "wave_repair_zbrush2.obj - a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18). "
                     "Reference only: layout, proportions and 3-D large forms (Q18-Q20). It is never read by the generator or the fit.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18、確かめるまで開いたまま）。"
                     "配置・比率・大きな形の考え方だけを参考にし、形は写していない（生成器と当てはめは参照の網を読まない）。",
        "method_ja": "形は Houdini の網（Houdini/Design28R01/kstar_h_R2.hiplc の /obj/kstar_h_design：CTRL の ramp → 断面の案内の曲線 → 奥の形のならし → "
                     "背のならし → 唇の上面の断面の形 → b 区域 → 唇の頭 → 側の縁 → Skin）が作る。参照モデルは F13 と量感の比較の数値のためにだけ、"
                     "評価器が一時のキャッシュで読み、消す（SHA-256 を Q20H/deleted_caches_sha256.txt に記録）。シーンには参照の節点を残さない。",
        "F13_proximity_all_reference_vertices": r.get("F13_proximity"),
        "deliberate_differences": [
            {"id": "D1", "what_ja": "背の輪郭をもっと滑らかに（樽の中心のまわりの同心の殻、彫りの波なし）。R2：背を波峰に沿ってもならした（上から見た背の線）",
             "F03_inflections": chk(r, "F03", "曲率の符号"), "F03_roughness": chk(r, "F03", "ざらつき"),
             "reference": "変わり目 3〜5、ざらつき 10〜26（×1e-3）", "views": "V3・V5・V6・V8"},
            {"id": "D2", "what_ja": "球の台座なし。足は前の谷へ流れ、谷から前の海へ一続き",
             "F08_step": chk(r, "F08", "鉛直の段"), "F08_trough": chk(r, "F08", "前の谷"), "views": "V3・V4・V9"},
            {"id": "D3", "what_ja": "唇先は原画の大きな輪郭（σ 12 px）に合わせたなめらかな鉤。爪・指は作らない（段階6 で原画から）。R2：唇の頭をまとめて動かし、"
                                    "爪の房の間の湾（2〜3 m）をゆるい起伏として持つ",
             "gate_large_form_132_72": sup.get("gate_large_form"),
             "rubric_measures_ja": "ルーブリックの爪の根（0.5 m 以内 ≤ 10 %）と指の根（14 本のうち ≤ 3）は、爪・指がまだ無いので段階6 まで該当なし。",
             "views": "V1・V2・V7"},
            {"id": "D4", "what_ja": "b 区域（第二の波頭）の稜と爪の縁は原画の帯から（参照の房・指の位置は使わない）。R2：幅の広い稜と 3 つの房",
             "band_round3_detector": sup.get("band_round3_detector"), "Q21_3_detector": r.get("Q21_3"),
             "rubric_measures_ja": "帯の縁の高さ S2 ±0.5 m・房の指の数は段階6（爪）で測る（該当なし）。ここでは帯の上端（稜）と下端（爪の縁）の原画視点の px。",
             "views": "V1・V7・V8"},
            {"id": "D5", "what_ja": "奥の端は我々の設計：原画視点で管の内側の輪郭（72）を唇先が描き、c +15 で静水面まで高さと厚みが一緒に細る巻きで閉じる"
                                    "（R2：最後まで巻きの形のまま、1.5 m より下は相似に縮む）",
             "H_over_H0_far": far, "F05_far_mass": chk(r, "F05", "奥の端"),
             "reference": "参照は唇の巻きが c +12 まで H 0.6〜0.75 で続く", "views": "V4・V5・V9"},
            {"id": "D6", "what_ja": "手前の頂の線は原画の外輪郭（78/130/131）が決める（K* の断面の枠の a = 0 に頂）。主断面 H0 と最高点は c −1〜+3",
             "gate": {k: r["gate"][k] for k in ("78", "130", "131")}, "H0_m": H0,
             "highest": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])}, "views": "V1・V6"},
        ],
        "must_fix_responses_R1_rejudge": must_fix,
        "decisions_taken_ja": [
            "R1 の系統（H1A → R1）を続け、R1 の本体の母数（頂の線・唇・管・殻・唇の上面の断面の形）はそのまま使った（関門 78/130/131 と 0 の交差を保つ）。",
            "原画の輪郭 72 は唇の頭をまとめて動かして合わせた（評審の推奨「輪郭の帯の中だけで唇先・唇の下の帯を 0.35 m より広げる」）：唇先の法線の向き ±1.0 m、"
            "鉛直 ±1.2 m、鍵 1 m おき（c −9〜+14）。細い帯の法線の移動（R1 の edge_tip）は管の壁の曲がりを作るので 0。",
            "132 は唇の上面の細い帯（edgeL、σ 5 列、視線がかすめる所だけ、鍵 1 m おき c −5〜+1、±0.35 m）。",
            "関門は進行役の 20:00 の判断どおり大きな輪郭（σ 12 px）で合わせ、細部込みの値も表に残した。",
            "背のならしは平面の位置を σ、高さを 0.4 σ でならす（高さも強くならすと奥の唇の上面が行ごとに混ざって折れ・交差ができた。試した）。",
            "背の埋め（back_fill、主断面から奥へ背の点が前へ戻らないように後ろから埋める）は節点に入れたが値は 0：上から見たくびれ（c 0〜+4）は消えるが、"
            "その行（ルーブリック F03 の本体の行 c −5〜+4）の殻の厚みが 0.37〜0.43 H、壁 0.5H が 0.38〜0.42 H になり F03 の必須（≤ 0.34 / ≤ 0.36）を割る（試した）。",
            "背のならしは奥の行で列 150 まで（70 列でぼかす）。列 186 まで広げると奥の頂が尖り F02 の奥の行の 1 頂点の折れが 13.9° になった（試した）。",
            "奥の行の形のならし（far_smooth、唇先を基準）は節点として入れたが値は 0（背のならしと重ねると頂の列が飛ぶ所が増えた）。",
            "頂の冠（奥の行の唇の上面を頂より下へやわらかく抑える）は関数を残したが使わない（平らな台を作って膨らみの測りが悪くなった）。",
            "奥の端では巻きをふくらみへ消すのをやめ、1.5 m より低い行は相似に縮めた（平面の広がりは 25 % より縮めない）。行をまたぐ折れ > 30° は 228 → 29。"
            "最後の 1 行（H < 0.9 m）だけ単調な帯へ移す。手前の肩の端は R1 のまま。",
            "b 区域は稜の幅の下限 0.13、谷 0.5、3 つの房 0.25 m。房を 0.35 m 以上にすると原画の帯の稜の中央値が 13 px を超えた（試した）。",
            "何も commit していない。Unity は使っていない。大きな出力は Unity/Build/Q20H（git の外）。",
        ],
        "conflicts_ja": [
            "F10 奥で頂の線が後ろへ流れる角 ≤ 20°、F04 の幅、F05 奥の固まり ≤ 3 m は、奥の行の唇先が原画の管の輪郭 72 を描くことと両立しない（K* 58°、第 2 回 51°、A4 48°、"
            "R1 53° も同じ理由）。",
            "F10 の平面の向きの変化は、奥の行（c +9〜+12）で唇の上面が頂とほぼ同じ高さの台になり、最も高い点の列が飛ぶので大きく出る（頂の列 90 は設計上の頂）。",
            "奥の背の膨らみの測り（c +9〜+12）：奥の行は高さ 15 m で頂が唇先の 1〜2 m 上しかなく、背は鉛直に近い壁になる。R4 は A4 の水準に届かない。",
            "ルーブリック F02 の奥の行（c > +3）の Rmin は、頂の ±3 m の窓に唇の頭が入るので小さく出る（R1 と同じ）。R2 の背のならしは奥の行の頂も"
            "ならすので、奥の行の弦角・1 頂点の折れも基準を割った（必須の不合格が 2 つ増えた。膨らみの測りとの引き換え）。",
        ],
        "rubric_changes_vs_R1_ja": [
            "直った：F11 行をまたぐ折れ > 30° 228 → 15。",
            "新しく割った：F02 奥の行の弦角 132° → 107°（背のならしが奥の頂も丸めるため。列 150 までに止め、1 頂点の折れは 7.3° で通る）。",
            "新しく割った：F05 断面の最長の直線 0.29 → 0.40 H（c −3.6〜−3.4 の唇の上面：唇の頭の移動と b 区域の稜の端の間がまっすぐになる）。"
            "稜の端（c > −5）を消すと直線は 0.33 H で通るが、132 の大きな輪郭が 4.70 px に戻り関門を割った（試した）。関門を優先した。",
        ],
        "design_keys_file": "kstarR2_design.json",
        "fit_log": design.get("fit_log"),
    }
    json.dump(rec, open(os.path.join(d, "kstarR2_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({"F13": rec["F13_proximity_all_reference_vertices"], "M1": must_fix[0]["result"]}, default=float, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
