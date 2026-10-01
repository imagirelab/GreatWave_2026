# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）の記録：metrics.json（項目 → 値 → 判定、R4 と K* 26修正01 との比べ）と run.json（命令・道具・入力と出力の SHA-256）。
usage: py -3.10 backfirst_record.py V3_DIR"""
import os
import sys
import json
import glob
import datetime
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import kh_common as KC  # noqa: E402


def r3(x):
    return None if x is None else round(float(x), 3)


def collect_raw(v):
    """kh_eval_summary.json と行の npz から metrics_raw.json と tstar_arcs.json を作る。"""
    import numpy as np
    sys.path.insert(0, HERE)
    import importlib.util
    for _n in ("rubric_measure", "rubric_check"):
        _sp = importlib.util.spec_from_file_location(_n, os.path.join(REPO, "Tools", "GWWaveGen", "rubric", _n + ".py"))
        _m = importlib.util.module_from_spec(_sp); sys.modules[_n] = _m; _sp.loader.exec_module(_m)
    RC = sys.modules["rubric_check"]
    import backfirst_eval as BE
    import kh_R4_quick as Q
    s = json.load(open(os.path.join(v, "eval", "kh_eval_summary.json"), encoding="utf-8"))
    C = {x["label"]: x for x in s["candidates"]}

    def gate(x):
        g = x["gate"]; lf = x["gate_lf"]; l4 = x["gate_lf_r4"]
        return {"78_max": g["78"]["max_px"], "130_max": g["130"]["max_px"], "131_max": g["131"]["max_px"],
                "132_s12_max": lf["132"]["max_px"], "72_s12_p95": lf["72"]["p95_px"], "72_s12_max": lf["72"]["max_px"],
                "132_raw_max": g["132"]["max_px"], "72_raw_p95": g["72"]["p95_px"], "72_s24_p95": l4["72"]["p95_px"],
                "pass_definition_78_130_131_and_s12_132_72": bool(x["gate_pass_lf"])}
    out = {"schema": "GreatWave.Polish28.round1_backfirst.metrics_raw/1", "round_ja": "仕上げ28 第1回：背から先に作る案（back-first）",
           "claws_on_off_ja": "この回は幾何の候補（K*′）だけ。爪（設計32・33 の結び付け）と NPR の焼き込みはこの形へまだ当て直していないので、Unity の評価器の爪あり／爪なしの測りは回していない（仕上げ28 の採否の後、焼き直しと爪の当て直しで行う）。ここの原画の関門は爪なしの幾何（大きな輪郭）の読み。",
           "cp1_unity_reference_ja": "段階5確認 §6.3 の CP1／26修正01（Unity の描画）：78/130/131 1.64/1.95/1.80 px、132 最大 1.57 px、72 p95 1.72 px。134・267 合格。Kstar26R01 は同じ形の幾何の読み。",
           "labels": {}}
    rows_of = {"P28bf": os.path.join(v, "candidate", "kstarP28bf_a45_rows.npz"),
               "R4": os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz")}
    for lab in ("P28bf", "R4", "Kstar26R01"):
        x = C[lab]
        o = {"gate": gate(x), "dome_j_bulge6": x.get("bulge6"), "sag_3m": x["Q21_1"]["sag_3m"], "mean_curvature_extrema": x["Q21_1"]["mean_curvature_extrema"],
             "surface_fit_6x12": x["Q21_1"]["surface_fit_6x12"],
             "fullness": {k: x["Q21_2"].get(k) for k in ("area_over_H2_mean_c-2_2", "ratio_area_over_H2", "ratio_shell_over_H", "volume_above_water_c-14_14_m3")},
             "b_region_band": {k: x["Q21_3"].get(k) for k in ("top_vs_top_smooth", "bottom_vs_bottom_smooth")},
             "rubric_must_fail": x["rubric"]["summary"]["must_fail"], "rubric_n": x["rubric"]["summary"]["n_checks"],
             "F13_proximity": x.get("F13_proximity"),
             "mesh": {k: x["mesh"][k] for k in ("local_selfx_vertices_win6", "flipped_quads_gt150", "cross_row_gt30_all", "cross_row_gt60_all", "degenerate_lt_1e-6")},
             "shape": x["shape"]}
        if lab in rows_of:
            z = np.load(rows_of[lab]); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
            o["f04_extents"] = BE.f04(c, A, Y); o["lip_edge_bump4"] = Q.bump(c, A, Y); o["back_plan_notch"] = Q.back_plan_notch(c, A, Y)
        out["labels"][lab] = o
    arcs = {}
    for lab, p in rows_of.items():
        z = np.load(p); A, Y, c = z["A"], z["Y"], z["c"]
        H = Y.max(1); rw = []
        for r in range(len(c)):
            if H[r] < 3.0:
                continue
            q = RC.corner_q17(A[r], Y[r], 200); rw.append((float(c[r]), float(H[r]), q["chord2_deg"], q["Rmin_m"]))
        rw = np.array(rw)
        tail = rw[(rw[:, 0] >= -39.7) & (rw[:, 0] <= -26.7)]; body = rw[(rw[:, 0] >= -5) & (rw[:, 0] <= 3)]; far = rw[rw[:, 0] > 3]
        arcs[lab] = {"method_ja": "rubric_check.corner_q17 の ±2 m の弦角（頂の尖り）、高さ 3 m 以上の行、t* の最後の一コマ",
                     "near_tail_c-39.7..-26.7": {"rows": int(len(tail)), "chord_min_deg": round(float(tail[:, 2].min()), 1), "rows_lt_110": int((tail[:, 2] < 110).sum()), "Rmin_min_m": round(float(tail[:, 3].min()), 2)},
                     "body_c-5..3": {"chord_min_deg": round(float(body[:, 2].min()), 1), "Rmin_min_m": round(float(body[:, 3].min()), 2)},
                     "far_c_gt_3": {"chord_min_deg": round(float(far[:, 2].min()), 1), "rows_lt_110": int((far[:, 2] < 110).sum()),
                                    "worst": [[round(a, 1), round(b, 1), round(cc, 1)] for a, b, cc, d in far[np.argsort(far[:, 2])[:6]]]}}
    out["tstar_arcs"] = arcs
    json.dump(arcs, open(os.path.join(v, "tstar_arcs.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(out, open(os.path.join(v, "metrics_raw.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    return out


def main():
    v3 = sys.argv[1]
    raw = collect_raw(v3)
    L = raw["labels"]; P, R, K = L["P28bf"], L["R4"], L["Kstar26R01"]
    arcs = raw["tstar_arcs"]
    bvh = json.load(open(os.path.join(v3, "bvh_selfx.json"), encoding="utf-8"))
    hv = json.load(open(os.path.join(v3, "houdini_scene_verify.json"), encoding="utf-8"))

    def item(name, crit, pv, rv, kv, verdict, note=""):
        return {"item": name, "criterion": crit, "P28bf": pv, "R4": rv, "Kstar26R01": kv, "verdict": verdict, "note": note}
    g = lambda X, k: r3(X["gate"][k])
    dome = lambda X, R_: {"p99": r3(X["dome_j_bulge6"][R_]["p99"]), "max": r3(X["dome_j_bulge6"][R_]["max"]),
                          "regions_p99": {k: v[0] for k, v in X["dome_j_bulge6"][R_]["regions"].items()}}
    items = [
        item("78/130/131 最大（定義どおりの読み）", "≤ 4 px", [g(P, "78_max"), g(P, "130_max"), g(P, "131_max")], [g(R, "78_max"), g(R, "130_max"), g(R, "131_max")],
             [g(K, "78_max"), g(K, "130_max"), g(K, "131_max")], "満たす", "R3・R4 と同じ肩の頂の列（輪郭を作る縁）を残した。余裕は 130 で 0.17 px"),
        item("132 大きな輪郭 最大（σ 12 px、爪なし）", "≤ 4 px", g(P, "132_s12_max"), g(R, "132_s12_max"), g(K, "132_s12_max"), "満たす", "余裕 0.10 px"),
        item("72 大きな輪郭 p95 / 最大（σ 12 px、爪なし。σ 24 の緩めなし）", "p95 ≤ 4 px", [g(P, "72_s12_p95"), g(P, "72_s12_max")], [g(R, "72_s12_p95"), g(R, "72_s12_max")],
             [g(K, "72_s12_p95"), g(K, "72_s12_max")], "満たす（R4 は否）", "奥の行の唇先を 72 の壁へ合わせる（far_lip_reach・reach_adjust）"),
        item("132 最大・72 p95（細部込み、記録）", "仕上げ33 で閉じる", [g(P, "132_raw_max"), g(P, "72_raw_p95")], [g(R, "132_raw_max"), g(R, "72_raw_p95")],
             [g(K, "132_raw_max"), g(K, "72_raw_p95")], "記録", "爪のこぶと湾の分"),
        item("72 大きな輪郭 p95（σ 24、R4 の緩めた読み、記録）", "記録", g(P, "72_s24_p95"), g(R, "72_s24_p95"), g(K, "72_s24_p95"), "記録",
             "σ 12 の読みで合わせたので σ 24 の線とは 4.09 px（σ 24 の線は原画の線から p95 6.77 px 離れる。28修正01 §4.3）"),
        item("評審のドーム R6（j_bulge6、6 m の局所 2 次曲面の残差）", "R4 0.693 m より 30% 以上下がる（≤ 0.485 m）なら第3回の条件", dome(P, "R6"), dome(R, "R6"), dome(K, "R6"),
             "満たさない（%+.1f%%）" % (100.0 * (P["dome_j_bulge6"]["R6"]["p99"] / R["dome_j_bulge6"]["R6"]["p99"] - 1.0)),
             "奥の背（back/far）と肩の唇の上（b 区域のこぶ）は下がった。主と肩の背（back/main・back/shoulder）は R4 の整えの層より上がった（regions_p99 を見る）"),
        item("評審のドーム R4（4 m）", "記録（A4 0.306）", dome(P, "R4"), dome(R, "R4"), dome(K, "R4"), "記録（%+.1f%%）" % (100.0 * (P["dome_j_bulge6"]["R4"]["p99"] / R["dome_j_bulge6"]["R4"]["p99"] - 1.0))),
        item("3 m の撓み p99 / 最大 / 0.3 m を超える頂点", "p99 ≤ 0.15 m（暫定）", [r3(P["sag_3m"]["p99_m"]), r3(P["sag_3m"]["max_m"]), P["sag_3m"]["n_gt_0.3m"]],
             [r3(R["sag_3m"]["p99_m"]), r3(R["sag_3m"]["max_m"]), R["sag_3m"]["n_gt_0.3m"]], [r3(K["sag_3m"]["p99_m"]), r3(K["sag_3m"]["max_m"]), K["sag_3m"]["n_gt_0.3m"]],
             "満たさない（p99 %+.1f%%）" % (100.0 * (P["sag_3m"]["p99_m"] / R["sag_3m"]["p99_m"] - 1.0))),
        item("後ろ 65°・回り台でドームが見えない", "目で見る（sheet_back_views, sheet_turntable, turntable_P28bf.mp4）", "見える", "見える", "—", "満たさない",
             "後ろからは頭巾のような丸い山のまま。縦の襞と奥の端の急な落ちは減った。u11 の中ほどの丸いふくらみ（頂の線の山と唇の先の平面のレモン形）は R4 とほとんど同じ"),
        item("F04 側面の影の幅 0.5H0 / 0.9H0 / 正面の幅 / 奥の体積", "≤ 18.5 m / ≤ 9.5 / ≤ 13 / ≤ 600 m³", [r3(P["f04_extents"]["side_0p5"]), r3(P["f04_extents"]["side_0p9"]), r3(P["f04_extents"]["front_0p75"]), r3(P["f04_extents"]["far_vol"])],
             [r3(R["f04_extents"]["side_0p5"]), r3(R["f04_extents"]["side_0p9"]), r3(R["f04_extents"]["front_0p75"]), r3(R["f04_extents"]["far_vol"])], None,
             "満たさない（%.2f m 狭くなっただけ）" % (R["f04_extents"]["side_0p5"] - P["f04_extents"]["side_0p5"]), "端は奥の行 c +8〜+10 の背（a −16.4）と肩の唇 c −9.8（a +10.4、b 区域）"),
        item("本体が薄くない（量感 面積/H² の参照比）", "≥ 0.90（暫定）", r3(P["fullness"]["ratio_area_over_H2"]), r3(R["fullness"]["ratio_area_over_H2"]), r3(K["fullness"]["ratio_area_over_H2"]), "満たす"),
        item("b 区域 稜（帯の上端）中央値 / p90 / 最大・覆った試料", "中央値 ≤ 10 px（暫定）・3 つの房", P["b_region_band"]["top_vs_top_smooth"], R["b_region_band"]["top_vs_top_smooth"], None,
             "一部（中央値は通る、3 つの房には読めない）", "肩のこぶを σ 3 列と c 方向 σ 1 m でならした（最大 30.3 → 21.4 px、覆い 36 → 37/46）"),
        item("b 区域 爪の縁（帯の下端）", "中央値 ≤ 10 px（暫定）", P["b_region_band"]["bottom_vs_bottom_smooth"], R["b_region_band"]["bottom_vs_bottom_smooth"], K["b_region_band"]["bottom_vs_bottom_smooth"], "満たす（R4 と同じ）"),
        item("t* の頂の弧（主の行 c −5〜+3、±2 m 弦角の最小）", "≥ 125°（F02）", arcs["P28bf"]["body_c-5..3"], arcs["R4"]["body_c-5..3"], None, "満たす"),
        item("手前の尾の行 c −39.7〜−26.7 の頂の弧", "±2 m 弦角 ≥ 110°", arcs["P28bf"]["near_tail_c-39.7..-26.7"], arcs["R4"]["near_tail_c-39.7..-26.7"], None, "満たす（R4 は 22 行が否）",
             "尾を c −17.6 の行の相似の族（高さ (1−cos)/2、幅は高さの 0.75 乗）にし、背の掃引をかけた"),
        item("奥の行 c > +3 の頂の弧", "±2 m 弦角 ≥ 110°（記録。R4 も 1 行否）", arcs["P28bf"]["far_c_gt_3"], arcs["R4"]["far_c_gt_3"], None,
             "満たさない（R4 %d 行 → %d 行、最小 %.1f°）" % (arcs["R4"]["far_c_gt_3"]["rows_lt_110"], arcs["P28bf"]["far_c_gt_3"]["rows_lt_110"], arcs["P28bf"]["far_c_gt_3"]["chord_min_deg"]),
             "奥の端を低くならし唇先を 72 の壁へ動かすと c +10〜+11 の小さな巻きの頂が詰まる。当てはめ（backfirst_fitfar、BF_TOP_PEN=1）に頂の形の罰を入れて和らげた。原画視点では隠れる"),
        item("唇の縁の波打ち bump4 d1 p99", "≤ 0.5〜0.6（評審）", r3(P["lip_edge_bump4"]["d1_p99"]), r3(R["lip_edge_bump4"]["d1_p99"]), None, "満たさない（後退：R4 1.20 → %.2f）" % P["lip_edge_bump4"]["d1_p99"],
             "c +3.5〜+4.5 の唇の下面（列 230〜246）。天井を作る行と奥の当てはめの境"),
        item("背のくびれ（平面の切れ込み）y 3 / 6 / 10 m", "≤ 1.1 m", P["back_plan_notch"], R["back_plan_notch"], None, "一部（y 10 は %.2f m、R4 %.2f m）" % (P["back_plan_notch"]["y10"]["notch_max_m"], R["back_plan_notch"]["y10"]["notch_max_m"])),
        item("評価基準 必須の否", "0", P["rubric_must_fail"], R["rubric_must_fail"], K["rubric_must_fail"], "満たさない（%d/56、R4 %d/56）" % (P["rubric_must_fail"], R["rubric_must_fail"]),
             "新しく否：F03 背の S 字 3、F02 奥の行。新しく合：F10 奥の端の落ち 3.33、F11 折れ"),
        item("網の衛生：局所の自己交差 / 裏返り / 行をまたぐ折れ >60° / 面積 <1e-6 / BVH の三角形の交差の組", "0",
             [P["mesh"]["local_selfx_vertices_win6"], P["mesh"]["flipped_quads_gt150"], P["mesh"]["cross_row_gt60_all"], P["mesh"]["degenerate_lt_1e-6"], bvh["P28bf"]["pairs_all"]],
             [R["mesh"]["local_selfx_vertices_win6"], R["mesh"]["flipped_quads_gt150"], R["mesh"]["cross_row_gt60_all"], R["mesh"]["degenerate_lt_1e-6"], bvh["R4"]["pairs_all"]],
             [K["mesh"]["local_selfx_vertices_win6"], K["mesh"]["flipped_quads_gt150"], K["mesh"]["cross_row_gt60_all"], K["mesh"]["degenerate_lt_1e-6"], None], "満たす" if (P["mesh"]["local_selfx_vertices_win6"] == 0 and P["mesh"]["flipped_quads_gt150"] == 0 and bvh["P28bf"]["pairs_all"] == 0) else "満たさない"),
        item("F13 参照モデルから 0.3 m / 1 m 以内の頂点の割合（写しにしない）", "0.3 m ≤ 0.25", P.get("F13_proximity"), R.get("F13_proximity"), K.get("F13_proximity"), "満たす"),
        item("134・267（色区の定義どおりの読み）", "合格", None, None, None, "測っていない", "NPR の焼き直しと Unity の描画が要る（この回は幾何の候補だけ）"),
        item("爪あり・爪なしの評価器", "両方", None, None, None, "爪なし（幾何）だけ", raw["claws_on_off_ja"]),
    ]
    # the alternative (not adopted): the same design with the b-region knob smoothed sigma 12 columns
    alt = None
    try:
        sys.path.insert(0, HERE)
        import backfirst_model as M_
        import backfirst_eval as BE_
        d = json.load(open(os.path.join(os.path.dirname(v3), "backfirst_design_final.json"), encoding="utf-8"))
        d["shoulder_knob"]["sigma_j"] = 12.0
        ca, Aa, Ya = M_.build(d)
        q = BE_.quick(ca, Aa, Ya)
        altd = os.path.join(os.path.dirname(v3), "alt_knob12"); os.makedirs(altd, exist_ok=True)
        json.dump(d, open(os.path.join(altd, "backfirst_design_alt_knob12.json"), "w", encoding="utf-8"), indent=1)
        import numpy as np
        np.savez_compressed(os.path.join(altd, "alt_knob12_rows.npz"), A=Aa, Y=Ya, c=ca)
        alt = {"name": "alt_knob12（Unity/Build/Polish/28/r1_backfirst/alt_knob12/）",
               "change_ja": "候補と同じ設計で、肩の b 区域のこぶ（列 112〜196、c −17.5〜−5.5）を列に沿って σ 12 列でならした（候補は σ 3 列）",
               "fast_eval": {"gate_78_130_131": [q["gate"]["78"]["max"], q["gate"]["130"]["max"], q["gate"]["131"]["max"]], "132_s12_max": q["gate"]["132lf"]["max"],
                             "72_s12_p95": q["gate"]["72lf"]["p95"], "dome_R6_p99": q["dome"]["R6"]["p99"], "dome_R4_p99": q["dome"]["R4"]["p99"],
                             "dome_R6_regions_p99": q["dome"]["R6"]["regions_p99"], "b_band_top": q["band"]["top_vs_top_smooth"], "b_band_bottom": q["band"]["bottom_vs_bottom_smooth"]},
               "reading_ja": "評審の R6 p99 は R4 より 40% 前後低くなり関門も通るが、b 区域の稜（帯の上端）が消える。粘土では u11 の中ほどの丸いふくらみも後ろからの山も変わらない"
                             "（sheet_alt_knob12_vs_P28bf.png）。R6 p99 の残りの大部分は b 区域の第二の波頭のこぶで、利用者が否とした大きなドームは 6 m の局所 2 次曲面の残差にはほとんど出ない。"
                             "Q21 の b 区域を捨てることになるので候補には採らない（Q24：b 区域を保つ側を採る）。"}
    except Exception as e:
        alt = {"error": "%s: %s" % (type(e).__name__, e)}
    metrics = {"schema": "GreatWave.Polish28.round1_backfirst/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
               "round_ja": raw["round_ja"], "candidate_dir": os.path.join(v3, "candidate"), "evidence_kind_ja": "numpy の生成器と評価器、Blender 5.2.2 Workbench の粘土、Houdini 22.0.429 hython のシーン。Unity・HMD ではない。",
               "cp1_unity_reference_ja": raw["cp1_unity_reference_ja"], "items": items, "alternative_not_adopted": alt}
    json.dump(metrics, open(os.path.join(v3, "metrics.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # run.json
    files = {}
    for p in sorted(glob.glob(os.path.join(v3, "candidate", "*")) + glob.glob(os.path.join(v3, "sheets", "sheet_*.png")) +
                    glob.glob(os.path.join(v3, "eval", "renders", "turntable_*.mp4")) + [os.path.join(v3, "eval", "kh_eval_table.md"), os.path.join(v3, "eval", "kh_eval_summary.json")]):
        files[os.path.relpath(p, v3).replace("\\", "/")] = {"sha256": KC.sha256(p), "bytes": os.path.getsize(p)}
    code = {os.path.basename(p): KC.sha256(p) for p in sorted(glob.glob(os.path.join(HERE, "backfirst_*.py")))}
    run = {"schema": "GreatWave.Polish28.round1_backfirst.run/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "commands": [
               "py -3.10 Tools/GWWaveGen/kstar_p28/backfirst_fitfar.py <out> <design.json> --iters 30 --workers 16 --w-crest 0.3   (env BF_NK=8 BF_FIT_VARS=reach; the reach_adjust keys of the final design)",
               "py -3.10 Tools/GWWaveGen/kstar_p28/backfirst_deliver.py Unity/Build/Polish/28/r1_backfirst/backfirst_design_final.json Unity/Build/Polish/28/r1_backfirst/v3   (candidate + kh_eval.py --turntable, reference cache in v3/_tmp, deleted, SHA-256 in v3/deleted_caches_sha256.txt)",
               "py -3.10 Tools/GWWaveGen/kstar_p28/backfirst_render.py v3/renders_back b1_back_p65+b2_back_0+b3_back_m65 P28bf=... R4=... Kstar26R01=...",
               "py -3.10 Tools/GWWaveGen/kstar_p28/backfirst_sheets.py v3",
               "hython Tools/GWWaveGen/kstar_p28/backfirst_houdini.py v3/candidate/kstarP28bf_a45 Houdini/Polish28/backfirst.hiplc v3/houdini_scene_verify.json",
               "blender --background --factory-startup --python Tools/GWWaveGen/kstar_h/kh_R1_selfx_bl.py -- v3/bvh_selfx.json P28bf=... R4=...",
               "py -3.10 Tools/GWWaveGen/kstar_p28/backfirst_record.py v3"],
           "tools": {"python": "py -3.10 (numpy, scipy, opencv)", "blender": KC.BLENDER, "hython": KC.HYTHON + " (Houdini Indie 22.0.429)"},
           "inputs": {"R3_rows": {"path": "Unity/Build/Q20H/final/_R3/kstarR3_a45_rows.npz", "sha256": KC.sha256(os.path.join(REPO, "Unity", "Build", "Q20H", "final", "_R3", "kstarR3_a45_rows.npz"))},
                      "R4_rows": {"path": "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_rows.npz", "sha256": KC.sha256(os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"))},
                      "design_json": {"path": "Unity/Build/Polish/28/r1_backfirst/backfirst_design_final.json", "sha256": KC.sha256(os.path.join(os.path.dirname(v3), "backfirst_design_final.json"))},
                      "reference_model_ja": "生成器・当てはめは読まない。kh_eval の F13 と量感の比べ（ref_fullness.json の数値）だけ。一時キャッシュの SHA-256 は deleted_caches_sha256.txt"},
           "reference_cache_log": open(os.path.join(v3, "deleted_caches_sha256.txt"), encoding="utf-8").read().strip(),
           "houdini_scene": {"path": "Houdini/Polish28/backfirst.hiplc", "sha256": hv["hip_sha256"], "bytes": hv["hip_bytes"], "points": hv["points"],
                             "max_abs_diff_m_vs_rows": hv["max_abs_diff_m_vs_rows"], "reference_model_string_hits": hv["reference_model_string_hits"]},
           "code_sha256": code, "outputs": files}
    json.dump(run, open(os.path.join(v3, "run.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("metrics.json / run.json written;", len(items), "items,", len(files), "files")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
