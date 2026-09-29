# -*- coding: utf-8 -*-
"""K*′ 精修 R4 の記録（py -3.10）：R3 の評審 2 人の must-fix への対応（R4 | R3 | A4 の数値）、決めたこと（Q24：推奨を選んだ理由と落とした案）、
原画・利用者の言葉・評価基準がぶつかる所と選んだ順（利用者の言葉 Q16〜Q22 > 大きな輪郭の関門 > 評価基準の暫定の上限）、
72 の大きな輪郭の定義し直し、参照モデルとの意図した違い、動きの当て直しの試験。
入力は kh_R4_deliver.py の出力（評価器の要約・追加の表・BVH）、_work/R4/R4_experiments.json（試しの記録）、kstarR4_visual_review.json（手で書く）、
kstarR4_retarget_ds28r01e.json。出力：kstarR4_difference_record.json、kstarR4_mustfix_table.md、kstarR4_eval_table.md の末尾に付記。
  py -3.10 kh_R4_record.py <final dir>
"""
import os
import sys
import json
import datetime

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


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


def rows_of(p):
    z = np.load(p)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def far_lip_thickness(c, A, Y):
    """the rubric's lip thickness 2 m from the tip (rubric_measure.section_metrics) on the far rows c +10 / +11 / +12 (the judges' 'far thin curl')."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "GWWaveGen", "rubric"))
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "rubric"))
    import rubric_measure as RM
    H0 = float(Y.max(1)[int(np.argmin(np.abs(c)))])
    out = {}
    for cc in (10.0, 11.0, 12.0):
        r = int(np.argmin(np.abs(c - cc)))
        m = RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
        out["c%+g" % cc] = rnd(m.get("lip_thick_2m_m"), 2)
    return out


def judge_rerun(d):
    """the R3 judges' own scripts (copied read-only into _work/R4/judgecheck with the R4 / R3 paths) re-run on the delivered rows."""
    jd = os.path.join(d, "_work", "R4", "judgecheck")
    out = {"where": "_work/R4/judgecheck (copies of Unity/Build/Q20H/_judge_R3/j3_*.py and num/n3_*.py with the file paths changed to R4 / R3)"}
    sh = load(os.path.join(jd, "n3_shape_R4_R3.json"))
    if sh:
        out["n3_shape"] = {lab: {"notch_half4": v.get("notch_half4"), "notch_half3": v.get("notch_half3"), "bulge_R4_p99": (v.get("bulge") or {}).get("R4", {}).get("p99"),
                                 "bulge_R6_p99": (v.get("bulge") or {}).get("R6", {}).get("p99"), "bulge_R6_max": (v.get("bulge") or {}).get("R6", {}).get("max")}
                           for lab, v in sh.items() if isinstance(v, dict)}
    lp = load(os.path.join(jd, "n3_lip_R4.json"))
    if lp:
        out["n3_lip_tipline_col200"] = {lab: (v.get("200") if isinstance(v, dict) else v) for lab, v in lp.items()}
    for f in ("j3_shape.out", "j3_lip2.out", "j3_bulge.out"):
        p = os.path.join(jd, f)
        if os.path.isfile(p):
            out[f] = open(p, encoding="utf-8", errors="replace").read()[-3000:]
    return out


def main(d):
    import kh_R4_lipsmooth as LS
    import kh_fitA as KF
    summ = load(os.path.join(d, "eval", "kh_eval_summary.json"))
    cand = {x["label"]: x for x in summ["candidates"]}
    R4, R3, A4 = cand["R4"], cand["R3"], cand["A4"]
    sup = load(os.path.join(d, "kstarR4_supplementary.json"))
    bvh = load(os.path.join(d, "kstarR4_bvh_selfx.json"), {})
    rt = load(os.path.join(d, "kstarR4_retarget_ds28r01e.json"))
    rt3 = load(os.path.join(d, "_R3", "kstarR3_retarget_ds28r01e.json"))
    vis = load(os.path.join(d, "kstarR4_visual_review.json"), {})
    exp = load(os.path.join(d, "_work", "R4", "R4_experiments.json"), {})
    design = load(os.path.join(d, "kstarR4_design.json"))
    rep = load(os.path.join(d, "kstarR4_deliver_report.json"), {})
    paths = {"R4": os.path.join(d, "kstarR4_a45_rows.npz"), "R3": os.path.join(d, "_R3", "kstarR3_a45_rows.npz"),
             "A4": os.path.join(os.path.dirname(os.path.dirname(d)), "Q20L3", "candA4", "kstarA4_a45_rows.npz")}
    extra = {}
    for lab, p in paths.items():
        c, A, Y = rows_of(p)
        b = KF.bump4(c, A, Y)["d1"]
        m = np.broadcast_to(KF.BUMP_C[None, :] >= -5, b.shape)
        extra[lab] = {"tipline_residual_c-9_12": LS.tipline_residual(c, A, Y), "bump4_d1_p99_c_ge_-5": round(float(np.percentile(b[m], 99)), 3),
                      "bump4_d1_p99_c_lt_-5": round(float(np.percentile(b[~m], 99)), 3), "lip_thick_2m_c10_11_12": far_lip_thickness(c, A, Y)}
    c, A, Y = rows_of(paths["R4"])
    H = Y.max(1)
    H0 = float(H[int(np.argmin(np.abs(c)))])

    def per(fn):
        out = {}
        for lab, x, s in (("R4", R4, sup.get("R4")), ("R3", R3, sup.get("R3")), ("A4", A4, sup.get("A4"))):
            try:
                out[lab] = fn(x, s, extra[lab])
            except Exception as e:
                out[lab] = "n/a (%s: %s)" % (type(e).__name__, e)
        return out

    def g(x, k, f="max_px"):
        return rnd(x["gate"][k][f])

    def glf(x, k, f):
        return rnd(x["gate_lf"][k][f])

    def glf4(x, k, f):
        return rnd(x["gate_lf_r4"][k][f])

    def notch_list(s, key, heights):
        t = s["notch_all_heights"][key]
        return {h: t.get(h) for h in heights}

    rt_rows = {k: {kk: v.get(kk) for kk in ("section_selfx_rows", "local_selfx_vertices", "cross_row_gt30", "cross_row_gt90", "Hmax")}
               for k, v in (rt or {}).get("frames", {}).items()} or None
    rt3_rows = {k: {kk: v.get(kk) for kk in ("section_selfx_rows", "local_selfx_vertices", "cross_row_gt90")}
                for k, v in (rt3 or {}).get("frames", {}).items()} or None

    dome_ja = ("u11・v9 の中央の丸い山（評審の『唇の上面のドーム』）は、主断面のまわり（c −8〜+2）の唇の上面そのもの。主断面から肩へ頂が下がる勾配 dH/dc は "
               "c −12〜−6 で 0.72〜0.89。この頂の点は原画の外輪郭 78 / 130 / 131 を描くので、原画カメラの視線に沿ってしか動かせない。その視線の勾配は "
               "dy/dc 0.36〜0.47、同時に da/dc −1.3〜−2.0（視線に沿って c が 1 m 進むと頂は 1.3〜2 m 後ろへ下がる）。山をなだらかにする（肩の頂を高くする）には "
               "肩の頂を 5〜6 m 後ろへ引くことになり、利用者が Q21 で受け入れないとした『真上から見た後ろへ引かれたふくらみ』になる。唇の上面の中央（c −3〜0）は "
               "132 を、c −3〜+10 の唇先は 72 を描く。したがって山の高さと広がりは、原画の輪郭と今の 3D の読み（頂の線 = 左上の外輪郭）で決まり、R4 では変えなかった"
               "（関門を割る変え方は利用者の言葉 Q21 の『両側の縁で合わせる』に反する）。R4 で変えたのは、山を区切っていた背の縦の筋・膝の折れ・奥の端の瘤と、"
               "上から見たくびれ、奥の端の尖った頂。")
    items = [
        {"id": "1", "item_ja": "ドーム・レモン形（Q21、利用者が受け入れられないとした所。評審の blocker）：R6 p99 ≤ 0.6 m（区域ごとにも）、R4 p99 ≤ 0.31 m、R6 最大 ≤ 1.0 m。"
                                "目で見て v6・v9・u11・f160・f180・f200 にドーム・レモン形・鞍がない",
         "done_ja": "①整えの層 sculpt（kh_R4_sculpt.py）：評審の膨らみの測り（R4・R6）と上から見たくびれを最小にする断面の法線の向きの変位の層を、原画視点の輪郭の縁"
                    "（外の輪郭から 3 px 以内に写る頂点と、b 区域の稜などの見えている中の輪郭）を動かさない条件で解いた。背・頂・唇の上面の前半（列 18〜130）だけ。"
                    "主断面と肩の頂（0.92 H より上）、低い行、唇の頭は動かさない。②far_back：奥の行（c ≥ 6）の背を足から 1 本の曲線に（鉛直の壁と膝の折れ = "
                    "後ろから見た山を区切る折れ線をなくした）。③back_smooth の列の重みの移りを c 1→5 から c −3→9 へ広げた（c 1〜4 の背の段と S 字の折れ）。"
                    "④背の面そのものの c 方向の 2 階差を sculpt の罰に入れた（背の縦の筋）。",
         "result": per(lambda x, s, e: {"R6_p99": rnd(x["bulge6"]["R6"]["p99"], 3), "R6_max": rnd(x["bulge6"]["R6"]["max"], 3), "R4_p99": rnd(x["bulge6"]["R4"]["p99"], 3),
                                        "R6_regions_p99": s["bulge6_regions"]["R6"].get("regions_p99"), "R4_regions_p99": s["bulge6_regions"]["R4"].get("regions_p99"),
                                        "R6_max_at": s["bulge6_regions"]["R6"].get("at_c_col")}),
         "not_fixed_ja": ["R6 p99 と R4 p99 は目標に届かない。残りは (a) 肩の b 区域の稜（c −16〜−13、列 140〜180。第二の波頭そのもの。項目 5）と (b) 奥の端の丸い頂"
                          "（c +9〜+13。頂を丸くするほど 4 m の 2 次曲面に乗らない。項目 3）。どちらも利用者の言葉（Q16・Q21 の b 区域、Q17 の丸い頂）を優先した。",
                          dome_ja],
         "visual_ja": vis.get("item1")},
        {"id": "2", "item_ja": "くびれ：上から見た背の平面の線（±4 m の弦）の前への出 ≤ 1.1 m をすべての高さ 1〜16 m で（c −10〜+12）、手前の足（c −30〜−10）も。"
                                "y 3・6 m は ≤ 0.9 m を狙う。弦の端の値（c −14）でない値を出す",
         "done_ja": "sculpt の中で、高さ 1〜10 m（c −10〜+12）と 1〜7 m（手前の肩と尾、c −34〜−10.5）のくびれ、評審 1 の台本の y 3・6 m の値（弦の左の端を c −14 に留める所）を"
                    "1.0 m を超えないように埋めた。back_depth の c −25 の鍵 0.3 → 0.42（足）。",
         "result": per(lambda x, s, e: {"judges_script_y3_y6_y10": [s["judge_R2_notch_as_scripted"][k] for k in ("y3", "y6", "y10")],
                                        "interior_y3_y6_y10": [s["judge_R2_notch_interior_chords"][k] for k in ("y3", "y6", "y10")],
                                        "all_heights_c-10_12": notch_list(s, "c-10..+12_h1..16", ["y%d" % h for h in range(1, 17)]),
                                        "foot_c-30_-10": s["notch_all_heights"]["c-30..-10_h1..4.5"], "max_all": s["notch_all_heights"]["max"]}),
         "not_fixed_ja": ["評審 2 の台本の y 10 m、c −14.25 の 2.19 m（R3 2.22）は、肩の頂の高さの鞍（c −16 で H 11.1 m、両側 12.5 / 14.8 m）を 10 m の平面が横切る所。"
                          "肩の頂は原画の左上の外輪郭 78 / 130 を描く（輪郭の縁として sculpt でも動かさない）ので、関門を優先して残した。",
                          "手前の足 y 1 m（c −24.5）は 1.14 m（R3 1.83）。足の 0.3〜1.5 m は海になじむ所で sculpt を弱めているので 1.1 に少し届かない。",
                          "高さ 12 m 以上（主断面の 0.6 H より上）は 1.1 m を超える（R4 12 m 1.11、16 m 1.81 m。R3 2.33 m）。この高さの『くびれ』は奥の半分の頂の線の平面の曲がり"
                          "（c 0 から奥で頂の線が後ろへ曲がる）で、13 m まで埋めると本体の行（c 1.4〜2.4）の背の断面に小さな S 字の膨らみが出た（試し c6：評価基準 F03 の"
                          "曲率の符号の変わり目 3）。Q21 の『中ほどに無理なふくらみを作らない』を優先して 10 m までにした。真上から見える背の外形（低い高さ）にはくびれはない。"]},
        {"id": "3", "item_ja": "奥の行（c +7〜+12.5）の頂の折れ（Q17）：頂の Rmin ≥ 1.5 m、1 m の中の向きの変わり ≤ 45°、最も高い点を列 90 ±10 に",
         "done_ja": "far_top：c 5.5〜8.5 から奥の行の頂（列 66〜176）を、列 66 と列 176 を通り、この範囲の最も高い所を頂とする左右の放物線へ（頂と唇の上面の間の平らな台と、"
                    "唇の頭の手前の折れをなくす）。列を弧長で配り直して列 90（j_top）を頂に置いた（どの行でも最も高い点が列 90）。唇の頭と唇先（72）は動かない。"
                    "sculpt は奥の行の頂（0.975 H より上）を動かさない。",
         "result": per(lambda x, s, e: {"top_roundness": s.get("top_roundness"),
                                        "F02_far_Rmin_theta_chord_fold": [rnd(val(x, "F02", "Rmin_m（奥")), rnd(val(x, "F02", "theta_c_deg（奥")),
                                                                          rnd(val(x, "F02", "chord_pm2m_deg（奥")), rnd(val(x, "F02", "fold_deg（1 頂点の折れ、奥"))]}),
         "notes_ja": ["kh_R4_top.py の測り：頂の近く（y ≥ 0.85 H、列 50〜176。唇の頭の丸い先は頂ではないので除く）の、弧長 1 m の中の向きの変わりの最大と、"
                      "±0.5 m の 3 点の円の半径の最小（上へ膨らむ所）。評審 2 の測りの定義は同じではない（評審は R3 で Rmin 0.47〜0.93、112°、kh_R4_top は 0.34、87°）。",
                      "評価基準 F02 の奥の行（Rmin・θc・弦角）は頂の ±3 m の窓に唇の頭の鉤が入るので鋭く出る（R3 と同じ理由、記録）。"],
         "tradeoff_ja": "頂を丸くするほど R4 の奥の区域は上がる（丸さ 0 / 0.5 / 0.75 / 1 で R4 奥の頂 0.53 / 0.63 / 0.71 / 0.78）。Q17 を優先した。",
         "visual_ja": vis.get("item3")},
        {"id": "4", "item_ja": "唇の縁の波打ち：鍵 ≥ 3 m か同じ効果のならし。bump4 d1 p99 ≤ 0.5〜0.6、先の線の ±2 m の 2 次式からの残差 p99 ≤ 0.08 m、唇の縁 d1 p99 ≤ 1.0。"
                                "u11・v7・f0020・f0040 に波・こぶがない。f0060 のねじれた肩の唇の端と穴",
         "done_ja": "①72 の大きな輪郭を定義し直した（評審 2 人の推奨、Q24）：爪の房の間の湾（8〜12 px、爪の大きさ）を閉じるため、72 だけを σ 24 px でならす"
                    "（唇の頭の先との継ぎ目は σ 12 px のまま、72 に沿って 30〜100 px で移す。kh_gate_lfR4.py）。132 は σ 12 px のまま。関門の数（72 は p95 ≤ 4）は変えない。"
                    "②唇の頭の鍵を c 0〜9.5 で σ 0.6 m にならした（c 2〜8 の lip_drop の ±0.5 m の交互の上下が消えた）。③back_smooth の列の重みの移りを広げた（c 1〜4 の 4 階差）。"
                    "④手前の尾（原画の枠の外）の巻きをうねりへ移した（tail_fade）。",
         "result": per(lambda x, s, e: {"bump4_d1_p99": s["bump4"]["d1_p99"], "bump4_c_ge_-5": e["bump4_d1_p99_c_ge_-5"], "bump4_c_lt_-5": e["bump4_d1_p99_c_lt_-5"],
                                        "lipedge_d1_p99": s["bump4"]["lipedge_d1_p99"], "tipline_residual": e["tipline_residual_c-9_12"],
                                        "72_lf_sigma24_p95": glf4(x, "72", "p95_px"), "72_lf_sigma12_p95": glf(x, "72", "p95_px"), "132_lf_max": glf(x, "132", "max_px")}),
         "not_fixed_ja": ["bump4 と先の線の残差は目標に届かない。残りの主な 2 つ：(a) 主断面のまわり c −1〜+1 の唇の頭の鍵の上下（0.64 / −0.55 / 0.39 m）。この行の唇の頭は"
                          "132 の唇の頭の先と 72 の継ぎ目を描き、ならすと 132 が 4.02〜4.19 px、72 p95 が 5.3 px で関門を割った（試した）。(b) c −5 より手前は b 区域の房"
                          "（視線の向きの ±1.2 m の凹凸、1.25 m おき）で、房を消すと b 区域の帯の p90 が 18.9 px に戻る（項目 5）。",
                          "f0060 の肩の唇の端の穴：尾（c −21 より手前、原画の枠の外）はうねりへ移したので針とねじれは短くなったが、関門を描く行（c −21〜−17）の巻きの管の口は残る。"],
         "gate_redefinition": {"what": "72 large form: sigma 12 px -> 24 px (blend from 12 px at the lip-head junction over 30..100 px along 72)",
                               "tool": "Tools/GWWaveGen/kstar_h/kh_gate_lfR4.py", "why_ja": "R3 の評審 2 人の推奨（湾は段階6 の爪で作る）。Q24 により推奨を選んだ。",
                               "painting_vs_its_own_large_form": {"sigma12_72_p95": 2.87, "sigma24_72_p95": 6.77},
                               "values": per(lambda x, s, e: {"72_sigma12_p95": glf(x, "72", "p95_px"), "72_sigma24_p95": glf4(x, "72", "p95_px")})},
         "experiments": (exp.get("lip_edge") or {}).get("runs"),
         "visual_ja": vis.get("item4")},
        {"id": "5", "item_ja": "b 区域：u13・v3 で 3 つの大きな房が読める。稜の差の最大 ≤ 30 px（p90 ≤ 15 は保つ）、46 / 46 の試料を覆う。できなければ帯の右の端に届かない理由",
         "done_ja": "稜の幅・強さ・谷の深さ・房・稜の位置を試した（kh_R4_bregion.py、_work/R4/R4_experiments.json の b_region）。どれも関門（78・132）か帯の中央値・p90 を割るか、"
                    "肩の R6 を下げない。R3 の母数のまま。",
         "result": per(lambda x, s, e: {"ridge_median_p90_max_px": [rnd(x["Q21_3"]["top_vs_top_smooth"][k], 1) for k in ("median_px", "p90_px", "max_px")],
                                        "ridge_covered": [x["Q21_3"]["top_vs_top_smooth"].get("covered_samples"), x["Q21_3"]["top_vs_top_smooth"].get("target_samples")],
                                        "claw_median_p90_max_px": [rnd(x["Q21_3"]["bottom_vs_bottom_smooth"][k], 1) for k in ("median_px", "p90_px", "max_px")]}
                       if x.get("Q21_3", {}).get("top_vs_top_smooth") else None),
         "right_end_ja": (exp.get("b_region") or {}).get("right_end_ja"),
         "not_fixed_ja": "3 つの大きな房は u13・v3 では読めない（房は原画の視線の向きの凹凸で、原画視点の帯を守る）。房を断面の法線の向きに大きくすると帯から外れ、"
                         "唇の縁にも波が出る（R3 の試し、R4 の bump4）。b 区域の輪郭の位置（Q21 の利用者の言葉）を 3 つの房の見え方（評審の読み）より優先した。",
         "experiments": (exp.get("b_region") or {}).get("runs"),
         "visual_ja": vis.get("item5")},
        {"id": "6", "item_ja": "関門を保つ（余裕 ≥ 0.3 px を狙う）：78/130/131 最大 ≤ 4、132 大きな輪郭 ≤ 4、72 大きな輪郭 p95 ≤ 4",
         "result": per(lambda x, s, e: {"78": g(x, "78"), "130": g(x, "130"), "131": g(x, "131"), "132_lf": glf(x, "132", "max_px"),
                                        "72_lf_sigma12_p95": glf(x, "72", "p95_px"), "72_lf_R4_sigma24_p95": glf4(x, "72", "p95_px"),
                                        "gate_pass_lf_sigma12": x.get("gate_pass_lf"), "gate_pass_lf_R4": x.get("gate_pass_lf_r4")}),
         "not_fixed_ja": "余裕は R3 と同じ（130 は 0.17 px、132 は 0.09 px）。輪郭の縁は sculpt で動かさなかったので下がりはしないが、広げる当てはめはしていない"
                         "（R3 の当てはめの道具 kh_R3_sil.py の R4 版は関門の最大を下げる歩みを見つけられず動かない）。"},
        {"id": "7", "item_ja": "奥の細い巻きをこれ以上悪くしない：F05 奥の端の 0.5H の固まりの幅 ≤ 6.2 m（必須 ≤ 3）、c 10〜12 の唇の厚み（先から 2 m）≤ 1.0 m",
         "result": per(lambda x, s, e: {"F05_far_mass_m": rnd(val(x, "F05", "奥の端")), "F06_lip_2m_max": rnd(val(x, "F06", "先から 2 m"))}),
         "notes_ja": "奥の固まりの幅は c +3〜+6 の本体の行（頂から 4 m より奥）の半分の高さの厚みで、くびれを埋めた分だけ厚い（Q21 の量感と、くびれなしを優先）。"},
        {"id": "8", "item_ja": "網：BVH の三角形どうしの交差 0、裏返り 0、局所の自己交差 0、行をまたぐ折れ > 60° が 0。唇の上下の間隔 ≥ 0.03 m",
         "done_ja": "尾の唇の厚み（lip_thick の c −26 の鍵 0.02 → 0.05）。sculpt は薄い所（2.5 m 未満）を厚みの 0.6 倍より内へ動かさない。",
         "result": per(lambda x, s, e: {"bvh_pairs": (bvh.get(x["label"]) or {}).get("pairs_all") if x["label"] in bvh else None,
                                        "local_selfx": x["mesh"]["local_selfx_vertices_win6"], "flipped": x["mesh"]["flipped_quads_gt150"],
                                        "cross_row_gt60": x["mesh"]["cross_row_gt60_all"], "cross_row_gt30": x["mesh"]["cross_row_gt30_all"],
                                        "lip_clearance_min_m": s["shape_checks"].get("lip_clearance_min_m"), "section_selfx_rows": s["shape_checks"].get("section_selfx_rows")})},
        {"id": "9", "item_ja": "小さな見た目：v5・f0060 の肩の尾の針のようなとがり、v3 の手前の尾の端の V 字を、水面へなじませる",
         "done_ja": "tail_fade：原画の枠の外の尾（c −21 より手前。行の頂の像が x < 0）の巻きを、c に沿って長くなめらかにうねりへ移した。crest_height の手前の端の鍵を "
                    "2 つ上げて尾を長く低く伸ばした（鍵の数は同じ。c −21 より奥の行は 3 mm 以内しか動かない）。うねりは両端（列 18 = j_B、列 394 = j_E）で高さ 0"
                    "（最初の版は列 18 が 0.5 m 浮き、動きの生成器が j_B を海に留めるので当て直しの t* と K*′ が最大 0.52 m ずれた。直して t* は 1e-14 m で一致）。",
         "motion_side_effect_ja": "尾が巻かなくなったので、当て直しの τ −6 s の行をまたぐ法線の反転 > 90° が減った（R3 167 → R4 は当て直しの表）。",
         "visual_ja": vis.get("item9")},
        {"id": "10", "item_ja": "動きの当て直し（E を K*′ で作り直す時）：τ −2.0・−1.5 s の断面の自己交差 0、−0.5 / −0.4 s も 0、τ −6 s の行をまたぐ法線の反転 > 90° ≤ 117",
         "result": {"R4": rt_rows, "R3": rt3_rows},
         "notes_ja": "動きの生成器（ds28r01e）は読むだけで変えていない（この番号の最後の一コマの精修の範囲の外。E を採用する K*′ で作り直す時の仕事）。"
                     "当て直しの試験（kh_R1_retarget.py、τ −6〜0 s の 8 こま）の値をそのまま記録する。"},
    ]
    rec = {
        "schema": "GreatWave.kstar_h.R4.difference_record/1",
        "candidate": "K*' R4 (Houdini, refinement loop 4, the last loop; lineage H1A -> R1 -> R2 -> R3 -> R4)",
        "reference": "wave_repair_zbrush2.obj - a scan of someone else's exhibited sculpture (author and collection unconfirmed, D18). "
                     "Reference only: layout, proportions and 3-D large forms (Q18-Q20). It is never read by the generator, the fit or the sculpt solver.",
        "credit_ja": "参考：他者の展示作品（北斎『神奈川沖浪裏』の立体作品）のスキャン。作者・所蔵は未確認（D18）。配置・比率・大きな形の考え方だけを参考にし、形は写していない"
                     "（生成器・当てはめ・整えの層の解き方は参照の網を読まない）。",
        "method_ja": "形は Houdini の網（Houdini/Design28R01/kstar_h_R4.hiplc の /obj/kstar_h_design：CTRL の ramp → 断面の案内の曲線 → 奥の形のならし → 背の形 → "
                     "唇の上面の断面の形 → b 区域 → 唇の頭 → 両端（R4：手前の尾をうねりへ・奥の背をなめらかに・奥の頂を丸く）→ 側の縁 → 整えの層（R4）→ Skin）が作る。"
                     "設計の json は R3 の設計から kh_R4_make_design.py で作り直せる（鍵の変更 → 唇の頭のならし → 整えの層の解き方。作り直した json は納品と同じ）。"
                     "参照モデルは F13 と量感の比較の数値のためにだけ、評価器が一時のキャッシュで読み、消す。",
        "scene": {k: (rep.get("scene") or {}).get(k) for k in ("saved", "hip_bytes", "hiplc_sha256", "removed_reference_nodes", "reference_path_leaks",
                                                               "reference_strings_in_hiplc", "verify")},
        "gwb_sha256": (rep.get("bridge") or {}).get("gwb_sha256"),
        "bridge_vs_numpy_max_m": rep.get("bridge_vs_numpy_max_m"),
        "F13_proximity_all_reference_vertices": R4.get("F13_proximity"),
        "priority_rule_ja": "目標どうしがぶつかる時の順（依頼）：利用者の言葉（Q16〜Q22）> 大きな輪郭の関門 > 評価基準の暫定の上限。",
        "must_fix_responses_R3_judges": items,
        "rubric_F03_R4_ja": {
            "values": {"R4": {"shell": val(R4, "F03", "殻の厚み"), "wall": val(R4, "F03", "壁 0.5H")}, "R3": {"shell": val(R3, "F03", "殻の厚み"), "wall": val(R3, "F03", "壁 0.5H")}},
            "why_accepted_ja": "R4 の殻・壁の最大（本体の行 c 1.4〜4）は、上から見たくびれを高さ 10 m まで埋めた分。R3 で緩めた 0.42 を超える。進行役の決定（Q24）は"
                               "『back_fill と F03 のぶつかりは Q21（くびれなし、満ちた本体）を優先』なので、上限をさらに緩めることはせず、否のまま記録して受け入れる。"},
        "deliberate_differences": [
            {"id": "D1", "what_ja": "背の輪郭をもっと滑らかに（樽の中心のまわりの同心の殻、彫りの波なし）。R4：背の縦の筋と奥の膝の折れを消し、上から見たくびれを 1〜11 m で埋めた",
             "F03_inflections": chk(R4, "F03", "曲率の符号"), "F03_roughness": chk(R4, "F03", "ざらつき"), "reference": "変わり目 3〜5、ざらつき 10〜26（×1e-3）"},
            {"id": "D2", "what_ja": "球の台座なし。足は前の谷へ流れ、谷から前の海へ一続き", "F08_step": chk(R4, "F08", "鉛直の段"), "F08_trough": chk(R4, "F08", "前の谷")},
            {"id": "D3", "what_ja": "唇先は原画の大きな輪郭（132 は σ 12 px、72 は R4 で σ 24 px）に合わせたなめらかな鉤。爪・指と爪の房の間の湾は作らない（段階6）",
             "gate_large_form": {k: R4["gate_lf"][k] for k in ("132", "72")}, "gate_large_form_r4": R4.get("gate_lf_r4")},
            {"id": "D4", "what_ja": "b 区域の稜と爪の縁は原画の帯から（参照の房・指の位置は使わない）", "Q21_3": R4.get("Q21_3")},
            {"id": "D5", "what_ja": "奥の端は我々の設計：唇先が原画の管の内側の輪郭 72 を描き、R4 で背を 1 本の曲線・頂を 1 つの丸い弧にし、c +15 で相似に縮む巻きで閉じる",
             "H_over_H0_far": {("c=%+.0f" % cc): round(float(H[int(np.argmin(np.abs(c - cc)))] / H0), 3) for cc in (4, 6, 8, 10, 12, 13, 14, 15)},
             "F05_far_mass": chk(R4, "F05", "奥の端")},
            {"id": "D6", "what_ja": "手前の頂の線は原画の外輪郭（78/130/131）が決める。主断面 H0 と最高点は c −1〜+3", "gate": {k: R4["gate"][k] for k in ("78", "130", "131")},
             "H0_m": H0, "highest": {"H_m": float(H.max()), "c_m": float(c[int(np.argmax(H))])}},
            {"id": "D7", "what_ja": "R4：手前の肩の尾（原画の枠の外）は巻きを消してうねりで海へなじませる（参照の尾の形は使わない）"},
        ],
        "decisions_taken_ja": [
            "R3 の系統（H1A → R1 → R2 → R3）を続け、R3 の本体の母数と原画の輪郭の縁（頂の線・唇・管・殻・唇の上面の断面・側の縁・b 区域）はそのまま使った（関門を保つ）。",
            "形の手続きの節点を 2 つ足した（far_end・sculpt）。sculpt の値は解き方（kh_R4_sculpt.py）が出し、輪郭の縁の頂点を動かさない条件つきで解いた。形は鍵に対して線形なので"
            "同じ鍵から Houdini でも同じ形になる（Houdini と numpy の差の最大は納品の report）。",
            "72 の大きな輪郭の定義し直し（σ 24 px）は評審 2 人の推奨で、Q24 により選んだ。σ 12 px の値も表に残す（R4 は σ 12 px の 72 p95 6.7 px で否）。",
            "主断面のまわり（c −1〜+1）の唇の頭の上下はならさなかった（関門 132 / 72 を優先。唇の縁の波打ちは一部だけ）。",
            "くびれの目標の高さは 10 m までにした（13 m まで埋めると背の断面に S 字の小さな膨らみ。Q21 の『無理なふくらみ』を避けた）。",
            "奥の行の頂を丸くした（Q17 を優先。R4 の測りの奥の区域は上がる）。",
            "b 区域は R3 の母数のまま（輪郭の位置 = Q21 を 3 つの房の見え方より優先）。",
            "尾（原画の枠の外）はうねりへ移した。",
            "動きの生成器（ds28r01e）は変えていない（この精修の範囲の外）。",
            "何も commit していない。Unity は使っていない。大きな出力は Unity/Build/Q20H（git の外）。",
        ],
        "conflicts_ja": [
            "評審の R6 / R4 の上限と、b 区域の第二の波頭（Q16・Q21 の利用者の言葉）：肩の R6 の残りは稜そのもの。",
            "評審の R4 の上限と、奥の行の頂の丸さ（Q17 の利用者の言葉）：丸くするほど奥の R4 が上がる。",
            "評審の唇の縁の目標（bump4・先の線の残差）と、原画の輪郭 132 / 72（関門）：主断面の唇の頭の上下が残る。",
            "評審のくびれ（すべての高さ）と、背の断面に無理なふくらみを作らない（Q21）・評価基準 F03（S 字）：12 m より上は残した。",
            "評価基準 F03 の殻・壁の上限 0.42 と、くびれを埋めること（Q21）：0.46 で否のまま。",
            "F10 奥で頂の線が後ろへ流れる角・F04 の幅・F05 奥の固まりは、奥の行の唇先が原画の管の輪郭 72 を描くことと両立しない（R1〜R3 と同じ）。",
            "F10 上から見た頂の線の向きの変化（2 m あたり）：R4 86°（c 10）は R3 75.7°（c −5）より大きい。R3 は奥の行の頂が平らな台で、最も高い点が唇の上面（列 91〜124）を"
            "動いていたので、奥で頂の線が後ろへ曲がってから c 12〜14 で前へ戻る所（R3 から引き継いだ crest_a の鍵。奥の行の唇先が管の口の輪郭 72 を描く）が測りに出なかった。"
            "R4 は頂を列 90 の丸い弧にしたので、その曲がりがそのまま出る。頂の丸さ（Q17）を優先した。",
        ],
        "experiments_file": "_work/R4/R4_experiments.json",
        "retarget_ds28r01e": {"R4": rt_rows, "R3": rt3_rows, "R4_build_ok": (rt or {}).get("build_ok"), "R4_Hmax_all_frames": (rt or {}).get("Hmax_all_frames"),
                              "R4_tstar": {k: rt["frames"]["0"].get(k) for k in ("tstar_vs_cand_max_m", "tstar_vs_cand_p99_m")} if rt and rt.get("frames") else None},
        "visual_review": vis,
        "design_keys_file": "kstarR4_design.json",
        "sculpt_log": {k: v for k, v in ((design or {}).get("sculpt_log") or {}).items() if k != "iters"},
        "extra_measures": extra,
        "judges_scripts_rerun_on_R4": judge_rerun(d),
    }
    chg = []
    for fid, lst in R4["rubric"]["checks"].items():
        for x in lst:
            y = next((t for t in R3["rubric"]["checks"].get(fid, []) if t["name"] == x["name"]), None)
            if y is None:
                continue
            if bool(x["pass_must"]) != bool(y["pass_must"]) or (isinstance(x["value"], float) and isinstance(y["value"], float)
                                                               and abs(x["value"] - y["value"]) > 0.05 * max(abs(y["value"]), 1e-6)):
                chg.append({"check": "%s %s" % (fid, x["name"]), "R3": rnd(y["value"], 3), "R4": rnd(x["value"], 3), "must": x["must"],
                            "R3_pass": y["pass_must"], "R4_pass": x["pass_must"]})
    rec["rubric_changes_vs_R3"] = chg
    rec["rubric_must_fail"] = {"R4": R4["rubric"]["summary"], "R3": R3["rubric"]["summary"], "A4": A4["rubric"]["summary"]}
    json.dump(rec, open(os.path.join(d, "kstarR4_difference_record.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)

    # ---------------- the R4 | R3 | A4 table of the must-fix targets
    def fm(v):
        if v is None:
            return "—"
        if isinstance(v, dict) and "notch_max_m" in v:
            return "%.2f m（c %s）" % (v["notch_max_m"], v["at_c"])
        if isinstance(v, bool):
            return "合" if v else "否"
        if isinstance(v, float):
            return "%.3g" % v
        if isinstance(v, list):
            return " / ".join(fm(x) for x in v)
        return str(v)
    it = {x["id"]: x for x in items}

    def r(iid, lab, *keys):
        v = it[iid]["result"].get(lab)
        for k in keys:
            if not isinstance(v, dict):
                return None
            v = v.get(k)
        return v

    def notch_pair(lab, h):
        v = r("2", lab, "all_heights_c-10_12", h)
        return "%.2f（c %g）" % (v[0], v[1]) if v else "—"

    def top(lab, reg, k):
        v = r("3", lab, "top_roundness", reg)
        return None if not v else v.get(k)
    L = ["# K*′ R4：評審（R3 の 2 人）の must-fix の目標と R4 | R3 | A4（%s）" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "",
         "値は `kstarR4_difference_record.json`（評価器 `eval/kh_eval_summary.json`、追加の表 `kstarR4_supplementary.json`、BVH `kstarR4_bvh_selfx.json`）から。"
         "目標がぶつかる時の順：利用者の言葉（Q16〜Q22）> 大きな輪郭の関門 > 評価基準の暫定の上限。", "",
         "| # | 項目 | 目標 | R4 | R3 | A4 |", "| --- | --- | --- | --- | --- | --- |"]
    rows = [
        ("1", "R6 p99 / 最大", "≤ 0.6 / ≤ 1.0 m", lambda lab: "%s / %s" % (fm(r("1", lab, "R6_p99")), fm(r("1", lab, "R6_max")))),
        ("1", "R4 p99", "≤ 0.31 m", lambda lab: fm(r("1", lab, "R4_p99"))),
        ("1", "R6 p99 区域（肩 / 主 / 中 / 奥）", "各 ≤ 0.6", lambda lab: " / ".join(fm((r("1", lab, "R6_regions_p99") or {}).get(k)) for k in ("shoulder c<-5", "main -5..+3", "mid +3..+9", "far +9..+16"))),
        ("1", "R4 p99 区域（肩 / 主 / 中 / 奥）", "各 ≤ 0.31", lambda lab: " / ".join(fm((r("1", lab, "R4_regions_p99") or {}).get(k)) for k in ("shoulder c<-5", "main -5..+3", "mid +3..+9", "far +9..+16"))),
        ("2", "くびれ y 3 / 6 / 10 m（評審の台本のまま）", "≤ 1.1 m", lambda lab: " / ".join(fm(v) for v in (r("2", lab, "judges_script_y3_y6_y10") or []))),
        ("2", "くびれ y 3 / 6 / 10 m（弦の両端が範囲の中）", "≤ 1.1（y 3・6 は ≤ 0.9）", lambda lab: " / ".join(fm(v) for v in (r("2", lab, "interior_y3_y6_y10") or []))),
        ("2", "くびれ y 11 / 12 / 14 / 16 m（c −10〜+12）", "≤ 1.1 m", lambda lab: " / ".join(notch_pair(lab, h) for h in ("y11", "y12", "y14", "y16"))),
        ("2", "手前の足のくびれ y 1 / 3 m（c −30〜−10）", "≤ 1.1 m", lambda lab: " / ".join("%.2f（c %g）" % tuple(r("2", lab, "foot_c-30_-10", h)) if r("2", lab, "foot_c-30_-10", h) else "—" for h in ("y1", "y3"))),
        ("3", "奥 c +7〜+12.5 の頂：最も高い列 / 1 m の向きの変わり / 凸の最小半径", "90±10 / ≤ 45° / ≥ 1.5 m",
         lambda lab: "%s / %s° / %s m" % (fm(top(lab, "far +7..+12.5", "top_col_range")), fm(top(lab, "far +7..+12.5", "turn1m_max_deg")), fm(top(lab, "far +7..+12.5", "Rmin_convex_min")))),
        ("3", "主 c −5〜+3 の頂：最も高い列 / 向きの変わり / 凸の最小半径", "保つ", lambda lab: "%s / %s° / %s m" % (fm(top(lab, "main -5..+3", "top_col_range")), fm(top(lab, "main -5..+3", "turn1m_max_deg")), fm(top(lab, "main -5..+3", "Rmin_convex_min")))),
        ("3", "F02 奥：Rmin / θc / 弦角 / 1 頂点の折れ", "記録（唇の頭が窓に入る）", lambda lab: fm(r("3", lab, "F02_far_Rmin_theta_chord_fold"))),
        ("4", "bump4 d1 p99（全体 / c ≥ −5 / c < −5）", "≤ 0.5〜0.6", lambda lab: "%s / %s / %s" % (fm(r("4", lab, "bump4_d1_p99")), fm(r("4", lab, "bump4_c_ge_-5")), fm(r("4", lab, "bump4_c_lt_-5")))),
        ("4", "先の線の ±2 m の 2 次式からの残差 p99 / 最大", "≤ 0.08 m", lambda lab: "%s / %s" % (fm((r("4", lab, "tipline_residual") or {}).get("p99")), fm((r("4", lab, "tipline_residual") or {}).get("max")))),
        ("4", "唇の縁 d1 p99", "≤ 1.0", lambda lab: fm(r("4", lab, "lipedge_d1_p99"))),
        ("5", "b 区域 稜 中央値 / p90 / 最大", "p90 ≤ 15、最大 ≤ 30 px", lambda lab: fm(r("5", lab, "ridge_median_p90_max_px"))),
        ("5", "b 区域 稜の試料", "46 / 46", lambda lab: fm(r("5", lab, "ridge_covered"))),
        ("6", "78 / 130 / 131 最大", "≤ 4 px", lambda lab: "%s / %s / %s" % (fm(r("6", lab, "78")), fm(r("6", lab, "130")), fm(r("6", lab, "131")))),
        ("6", "132 大きな輪郭 最大", "≤ 4 px", lambda lab: fm(r("6", lab, "132_lf"))),
        ("6", "72 大きな輪郭 p95：R4 の定義（σ 24）/ 元の定義（σ 12）", "≤ 4 px（R4 の定義）", lambda lab: "%s / %s" % (fm(r("6", lab, "72_lf_R4_sigma24_p95")), fm(r("6", lab, "72_lf_sigma12_p95")))),
        ("7", "F05 奥の端の 0.5H の固まりの幅", "≤ 6.2 m（必須 ≤ 3）", lambda lab: fm(r("7", lab, "F05_far_mass_m"))),
        ("7", "F06 唇の厚み 先から 2 m（最大、c −10〜+3）", "記録", lambda lab: fm(r("7", lab, "F06_lip_2m_max"))),
        ("7", "唇の厚み 先から 2 m（c +10 / +11 / +12）", "≤ 1.0 m", lambda lab: " / ".join(fm(v) for v in (extra[lab]["lip_thick_2m_c10_11_12"] or {}).values())),
        ("8", "BVH の三角形どうしの交差", "0", lambda lab: fm(r("8", lab, "bvh_pairs"))),
        ("8", "裏返り / 局所の自己交差 / 折れ > 60°", "0 / 0 / 0", lambda lab: "%s / %s / %s" % (fm(r("8", lab, "flipped")), fm(r("8", lab, "local_selfx")), fm(r("8", lab, "cross_row_gt60")))),
        ("8", "唇の上下の間隔の最小", "≥ 0.03 m", lambda lab: fm(r("8", lab, "lip_clearance_min_m"))),
    ]
    for iid, name, tgt, fn in rows:
        vals = []
        for lab in ("R4", "R3", "A4"):
            try:
                vals.append(fn(lab))
            except Exception as e:
                vals.append("n/a")
        L.append("| %s | %s | %s | %s | %s | %s |" % (iid, name, tgt, vals[0], vals[1], vals[2]))
    L.append("| — | 評価基準 必須の否（関門を含む） | 0 | %d / %d | %d / %d | %d / %d |" % (
        R4["rubric"]["summary"]["must_fail"], R4["rubric"]["summary"]["n_checks"], R3["rubric"]["summary"]["must_fail"], R3["rubric"]["summary"]["n_checks"],
        A4["rubric"]["summary"]["must_fail"], A4["rubric"]["summary"]["n_checks"]))
    L += ["", "目で見た所（v6・v9・u11・u13・v3・v5・v7・ターンテーブル）は `kstarR4_visual_review.json`。", ""]
    if rt_rows:
        ks = sorted(rt_rows, key=float)
        L += ["## 動きの当て直しの試験（E の生成器、読むだけ。`kh_R1_retarget.py R4 Unity/Build/Q20H/final …`）", "",
              "| τ [s] | " + " | ".join(ks) + " |", "| --- |" + " --- |" * len(ks)]
        for k, lab in (("section_selfx_rows", "断面の自己交差の行 R4"), ("local_selfx_vertices", "局所の自己交差の頂点 R4"), ("cross_row_gt90", "行をまたぐ法線の反転 > 90° R4"),
                       ("Hmax", "最高点 [m] R4")):
            L.append("| %s | " % lab + " | ".join(fm(rt_rows[t].get(k)) for t in ks) + " |")
        if rt3_rows:
            for k, lab in (("section_selfx_rows", "断面の自己交差の行 R3"), ("cross_row_gt90", "行をまたぐ法線の反転 > 90° R3")):
                L.append("| %s | " % lab + " | ".join(fm(rt3_rows.get(t, {}).get(k)) for t in ks) + " |")
        L += ["", "生成：%s、t* と候補の差の最大 %s m。" % ((rt or {}).get("build_ok"), fm((rec["retarget_ds28r01e"].get("R4_tstar") or {}).get("tstar_vs_cand_max_m"))), ""]
    open(os.path.join(d, "kstarR4_mustfix_table.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    tp = os.path.join(d, "kstarR4_eval_table.md")
    if os.path.isfile(tp):
        t = open(tp, encoding="utf-8").read()
        mark = "\n\n## R4 の付記（kh_R4_record.py）\n"
        if mark in t:
            t = t[:t.index(mark)]
        app = [mark,
               "- **72 の大きな輪郭を定義し直した（2026-09-29 R4、Q24 により評審 2 人の推奨を選んだ記録）**：72（唇の下と管）の大きな輪郭を σ 12 px から σ 24 px にした"
               "（唇の頭の先との継ぎ目は σ 12 px、72 に沿って 30〜100 px で移す。`Tools/GWWaveGen/kstar_h/kh_gate_lfR4.py`）。爪の房の間の湾（8〜12 px）は段階6 の爪で作る。"
               "132・78・130・131 と関門の数（72 は p95 ≤ 4 px）は変えない。表の『大きな輪郭の関門 R4』の行がこの版、『大きな輪郭の関門（20:00 の判断）』の行が元の版"
               "（R4 は元の版の 72 p95 %s px で否）。原画そのものと、その大きな輪郭との差（自己試験）：72 p95 は σ 12 で 2.87 px、σ 24 で 6.77 px。" % fm(glf(R4, "72", "p95_px")),
               "- **評価基準 F03 の殻・壁**：R4 は殻 %s、壁 %s で、R3 で緩めた上限 0.42 を超える（くびれを高さ 10 m まで埋めた本体の行 c 1.4〜4）。進行役の決定"
               "（Q21 を F03 より優先）に従い、上限は変えずに否のまま受け入れた。" % (fm(val(R4, "F03", "殻の厚み")), fm(val(R4, "F03", "壁 0.5H"))),
               "- **くびれ（すべての高さ）・頂の丸さ・唇の縁・b 区域・動きの当て直し**の R4 | R3 | A4 の表は `kstarR4_mustfix_table.md`、理由と試しは `kstarR4_difference_record.json`"
               "と `_work/R4/R4_experiments.json`。",
               "- **網の衛生（Blender BVH の三角形どうしの交差）**：R4 %s 組、R3 %s 組（`kstarR4_bvh_selfx.json`）。"
               % ((bvh.get("R4") or {}).get("pairs_all"), (bvh.get("R3") or {}).get("pairs_all"))]
        open(tp, "w", encoding="utf-8").write(t + "\n".join(app) + "\n")
    print(open(os.path.join(d, "kstarR4_mustfix_table.md"), encoding="utf-8").read())


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1])
