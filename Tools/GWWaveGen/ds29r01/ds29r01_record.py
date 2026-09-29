# -*- coding: utf-8 -*-
"""設計29修正01：証拠の metrics.json と run.json を書く（numpy・Pillow は使わない。読むだけ）。

入力（どれも Git 対象外の Unity/Build/Design/29R01/ の測定の JSON。値はここで作らず、写すだけ）：
  measure/ds29r01_table.json（Part B：設計29 の検査器を精度の層つきで走らせた表）
  unity/ds29r01_unity_check.json・check_gpu_f_final_kp.json・check_regress_d28_kp.json（Part A と直しの回の Unity の照合）
  unity/ds29r01_rebake_summary.json・f_final_kp/ds29r01_tstar_verdict.json・tstar_sym/tstar_sym.json・lfgate_unity.json（直しの回）
  indep_check/ic_*.json（進行役の独立の検査）
出力：Docs/Evidence/Design/29R01/metrics.json（項目 → 値 → 判定）と run.json（コマンド、道具の版、入出力の SHA-256）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = "Unity/Build/Design/29R01"
EV = "Docs/Evidence/Design/29R01"
FFPROBE_DIR = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin"


def P(rel):
    return os.path.join(REPO, rel)


def load(rel):
    with open(P(rel), encoding="utf-8") as f:
        return json.load(f)


def sha(rel):
    h = hashlib.sha256()
    with open(P(rel), "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def row(table, head):
    for r in table["rows"]:
        if r["item"].startswith(head):
            return r
    raise KeyError(head)


def metrics():
    T = load(B + "/measure/ds29r01_table.json")
    U = load(B + "/unity/ds29r01_unity_check.json")
    G2 = load(B + "/unity/check_gpu_f_final_kp.json")
    R28 = load(B + "/unity/check_regress_d28_kp.json")
    RB = load(B + "/unity/ds29r01_rebake_summary.json")
    SYM = load(B + "/unity/tstar_sym/tstar_sym.json")
    LF = load(B + "/unity/lfgate_unity.json")["runs"][B + "/unity/f_final_kp"]
    RR = load(B + "/unity/f_final_kp/ds29_render_report.json")
    IC = load(B + "/indep_check/ic_check1.json")
    ICB = load(B + "/indep_check/ic_blender_bvh_fine.json")["bvh"]
    ICR = load(B + "/indep_check/ic_blender_rays_fine.json")["rays"]["frames"]
    ICP = load(B + "/indep_check/ic_painting.json")
    QA = load(B + "/measure/qa_F_final_fine/F_final_fine_qa.json")["sweep30"]["compat_P13_ds27"]
    p13 = {k.split(" ")[0]: v for k, v in QA.items()}

    r_static = row(T, "メッシュ検査・静止の網の読み")
    r_sec = row(T, "同・断面の自己交差")
    r_pen = row(T, "メッシュ検査・厳しい読み")
    r_bvh = row(T, "同・頂点を共有しない組")
    r_flip = row(T, "同・30 Hz の前のコマと比べた面の反転")
    r_ray = row(T, "座席 v1 の射線")
    r_ray_pre = row(T, "同・t* より前の外周")
    r_geo = row(T, "原画視点の回帰なし")
    r_gate = row(T, "t* の関門の値")
    r_lip = row(T, "薄膜")
    r_far = row(T, "奥の壁の最後")
    r_ground = row(T, "30 Hz：地面の二階差分")
    r_folds = row(T, "隣と逆向きの面")
    r_239 = row(T, "K*′ の行 239")
    r_farrows = row(T, "形成の間（30 Hz、361 コマ）の奥の端")
    r_layers = row(T, "層の数")
    r_light = row(T, "軽量版：原画視点の輪郭の差")
    r_mem = row(T, "keypose の GPU メモリ")
    mem = U["memory"]
    gpu = U["gpu"]
    sil = RB["silhouettes_vs_kstar_prime"]
    strict = RB["strict_reading_vs_28r01"]

    acceptance = {
        "ja": "計画 §2.1 の設計29 の最小の受入を、設計28修正01 の F_final のパッケージそのもの（K*′ の格子 240 × 400、242 層）を原版として、精度の層つきの読みで測った。painting_colour_* は設計28修正01 §8 の引き継ぎ (a)（計画 §2.0 の後退の規則：色区の項目を 28修正01 の値へ戻す）",
        "mesh_static": {"value": r_static["r01_original_fine"], "verdict": "合格",
                        "note_ja": "非多様体・巻き方向の食い違い・下を向き上に網のない面・3 次元の自己交差（BVH、頂点を共有する組を除く、両方の面 ≥ 5 mm）。36 コマ τ −4.433〜0 s。独立の検査：辺 %d・非多様体 %d・巻き方向の食い違い %d・外周の輪 %d、上に網のない下向きの面は 36 コマで %d" % (
                            IC["edges"], IC["edges_gt2_faces_nonmanifold"], IC["directed_edge_duplicates_winding_mismatch"], IC["boundary_loops"],
                            sum(f["down_facing_open_sky"] for f in ICR))},
        "section_self_crossing": {"value": r_sec["r01_original_fine"], "verdict": "合格", "design29": r_sec["d29_original"]},
        "strict_one_vertex_penetration": {"value": r_pen["r01_original_fine"], "value_16bit_only": r_pen["r01_original_hi"], "design29": r_pen["d29_original"],
                                          "verdict": "合格（精度の層つき）", "note_ja": "30 Hz の全 361 コマ τ −12〜0 s、コマ・組・深さの最大 mm（両方の面 ≥ 5 mm）。16 bit だけの読みでは不合格"},
        "strict_bvh_non_sharing": {"value": r_bvh["r01_original_fine"], "value_16bit_only": r_bvh["r01_original_hi"], "design29": r_bvh["d29_original"],
                                   "verdict": "合格（精度の層つき）",
                                   "note_ja": "361 コマ、コマ・組。独立の検査（Blender の BVH）も両方の面 ≥ 5 mm で %d。5 mm の条件を外すと %d 組・%d コマ（行 238〜239 の間の 5 mm より細い面どうし。記録のみ）" % (
                                       ICB["pairs_alt5mm_total"], ICB["pairs_total"], ICB["frames_with_pairs"])},
        "strict_flips_30hz": {"value": r_flip["r01_original_fine"], "design29": r_flip["d29_original"], "verdict": "合格"},
        "seat_rays_hole_openback_cutend_seam": {"value": r_ray["r01_original_fine"], "verdict": "合格（事前検査。判定は番号41）",
                                                "note_ja": "5 万本 × 36 コマ。t* より前の外周の切断端／縁の下 %s は周りの海（設計30）の範囲で記録のみ" % r_ray_pre["r01_original_fine"]},
        "keypose_gpu_mib": {"value": round(mem["keypose_total_mib"], 2), "verdict": "合格",
                            "position_16bit_mib": round(mem["position_16bit_mib"], 2), "precision_layer_mib": round(mem["position_lo_mib"], 2),
                            "twhite_mib": round(mem["twhite_mib"], 2), "unity_driver_increase_mib": round(mem["driver_increase_keypose_mib"], 2),
                            "readable_cpu_copy": mem["readable_cpu_copy"],
                            "note_ja": "DS29KeyposePlayer の GPU だけの GraphicsBuffer（StructuredBuffer<uint>）。網 %.2f MiB と色区テクスチャ %.0f MiB は別。直しの回の描画でも %.2f MiB（ds29_render_report.json の位置 %d B ＋ 精度の層 %d B ＋ T_white %d B）" % (
                                mem["mesh_vertex_index_mib"], mem["colour_zone_texture_mib"], RB["render"]["keypose_gpu_mib"],
                                RR["positionGpuBytes"], RR["posLoGpuBytes"], RR["whiteGpuBytes"])},
        "painting_regression_geometry": {"value_px": r_geo["r01_original_fine"], "value_16bit_only_px": r_geo["r01_original_hi"], "verdict": "合格",
                                         "gate_values_px_78_130_131_132lf_72lf": r_gate["r01_original_fine"],
                                         "note_ja": "t* の復号した網で K*′ の評価表の値との差の最大。独立の検査も差 %.3f px" % ICP["decoded_fine"]["max_gate_diff_vs_kstar_prime_px"]},
        "painting_unity_silhouettes": {"value_px": {k: v["unity_max_px"] for k, v in sil["rows"].items()},
                                       "diff_vs_kstar_prime_px": {k: v["diff_px"] for k, v in sil["rows"].items()},
                                       "verdict": "合格（K*′ の値と ±0.5 px の内）"},
        "painting_unity_large_form": {"132_sigma12_max_px": round(LF["132_sigma12_max"], 4), "72_sigma24_p95_px": round(LF["72_sigma24_p95"], 4),
                                      "diff_vs_kstar_prime_px": LF["diff_vs_kstar_prime_px"], "worst_72_xy": LF["72_worst_xy"],
                                      "verdict": "後退なし（±0.5 px の内）。72 は 4 px の関門を 0.0075 px 超える（記録。仕上げ28）",
                                      "note_ja": "引き継ぎ (d)。Unity の t* の色区 ID 画像の空から測った。焼き直しの前・28R01F の画像でも同じ値"},
        "painting_colour_strict": {"worst_abs_diff_px": strict["worst_abs_diff_px"],
                                   "items": {k: {"now_max_px": v["now_max_px"], "r28r01_max_px": v["r28r01_max_px"], "diff_px": v["worst_abs_diff_px"],
                                                 "verdict_now": v["verdict_now"], "verdict_28r01": v["verdict_28r01"]} for k, v in strict["items"].items()},
                                   "items_over_0p5": strict["items_over_0p5"], "265_266_267_now_vs_28r01": RB["strict_265_267"],
                                   "267_white_bands_ge_20px": len(RB["strict_267_bands"]),
                                   "267_band_areas_px2": [b["area"] for b in RB["strict_267_bands"]],
                                   "worst_points_distance_to_sky_px": RB["strict_worst_points_at_kstar_prime_silhouette"],
                                   "verdict": "不合格（評価器の定義のままの読み。6 項目が ±0.5 px を超え、134 と 267 が合格 → 不合格）。記録として残し、仕上げ28 へ",
                                   "before_rebake_worst_px": U["tstar_fine_vs_16bit"]["fine_worst_vs_28r01_px"],
                                   "note_ja": "焼き直しの前（古い焼き込み、精度の層つき）は最悪 %.2f px。最悪の点と 267 の帯は、描画の空が原画の色区に入り込んだ所（worst_points_distance_to_sky_px：描画の空から 0〜1.41 px、原画の空から 2.24〜3.61 px）" % U["tstar_fine_vs_16bit"]["fine_worst_vs_28r01_px"]},
        "painting_colour_two_sided": {"worst_abs_diff_px": SYM["worst_abs_diff_px"],
                                      "rows": [{k: r[k] for k in ("item", "measure", "kp_sym_max_px", "r28_sym_max_px", "diff_px")} for r in SYM["rows"]],
                                      "verdicts_now": SYM["verdicts_kp_sym"], "verdicts_28r01": SYM["verdicts_28_sym"],
                                      "267_white": SYM["flat_painting_view_266_267"]["kp"]["white"]["sym"]["bands_ge_20px"],
                                      "px_removed_near_render_sky": SYM["flat_painting_view_266_267"]["kp"]["white"]["px_removed_near_render_sky"],
                                      "verdict": "合格（採った読み。175 の藍中の −1.153 px は改善で、175 は 28修正01 から不合格）。進行役の読み（Q24）で、評価器の定義ではない",
                                      "note_ja": "輪郭の両側（原画の空または描画の空から 2 px 以内）を除き、28修正01 の描画にも同じ読みを当てて比べた（ds29r01_tstar_sym.py）"},
        "gpu_readback_vs_numpy_mm": {"value": round(gpu["worst_in_range_vs_fine_mm"], 4), "captures": gpu["captures_in_range"], "range_tau": gpu["range_tau"],
                                     "rebaked_run_value": round(G2["worst_in_range_vs_fine_mm"], 4), "rebaked_run_captures": G2["captures_in_range"],
                                     "vs_16bit_only_mm": [round(IC["gpu"]["min_mm_vs16_all"], 3), round(IC["gpu"]["max_mm_vs16_all"], 3)],
                                     "tstar_gpu_vs_kstar_prime_mm": round(gpu["tstar_vs_kstar"]["gpu_vs_kstar_max_mm"], 4),
                                     "independent_all_520_mm": round(IC["gpu"]["max_mm_fine_all"], 4),
                                     "verdict": "合格（≤ 0.25 mm）"},
        "old_packages_identical": {"design28": {"files": [U["regress_d28"]["files_same_sha256"], U["regress_d28"]["files_compared"]],
                                                "videos": [U["regress_d28"]["videos_same_sha256"], U["regress_d28"]["videos_compared"]]},
                                   "design28_after_fix": {"files": [R28["files_same_sha256"], R28["files_compared"]],
                                                          "videos": [R28["videos_same_sha256"], R28["videos_compared"]]},
                                   "design27": {"files": [U["regress_d27"]["files_same_sha256"], U["regress_d27"]["files_compared"]],
                                                "videos": [U["regress_d27"]["videos_same_sha256"], U["regress_d27"]["videos_compared"]]},
                                   "verdict": "合格（SHA-256 まで同じ）"},
        "shader_variants": {"value": U["shader_check"]["allCompiled"], "stereo_output": U["shader_check"]["allStereoOutput"],
                            "compute_errors": U["shader_check"]["computeErrorCount"], "verdict": "合格（コンパイルだけ。ステレオの描画と HMD は未検証）"},
    }

    handoffs_in = {
        "a_rebake": {"value": "K*′ へ焼き直した（直接 %d テクセル、空き %d、ラスタ化されない %d、2 回目の焼き込みで SHA-256 が同じ）" % (
            RB["bake"]["direct"], RB["bake"]["emptyAfterFill"], RB["bake"]["notRasterised"]),
            "uvsdf_sha256": RB["bake"]["uvsdf_sha256"], "uvwarp_sha256": RB["bake"]["uvwarp_sha256"],
            "verdict": "済（両側の読みで合格、評価器の定義のままの読みでは 6 項目が残る）"},
        "b_gpu_memory": {"value_mib": round(mem["keypose_total_mib"], 2), "verdict": "済（読み取り可能の写しを持たない GPU だけのバッファ）"},
        "c_row239": {"value_fine": r_239["r01_original_fine"], "value_16bit_only": r_239["r01_original_hi"],
                     "formation_rows_235_237_flipped_normals_fine": r_farrows["r01_original_fine"],
                     "verdict": "直しは要らない（精度の層つきで K*′ と同じ法線。形成の間の奥の端の折れは見えない）"},
        "d_large_form_from_unity": {"72_sigma24_p95_px": round(LF["72_sigma24_p95"], 4), "132_sigma12_max_px": round(LF["132_sigma12_max"], 4),
                                    "verdict": "測った（72 は 4 px を 0.0075 px 超える。記録、仕上げ28）"},
    }

    backlog = {
        "ja": "計画 §2.1 の設計29 のバックログ（117、83・115・116）と、設計28 から引き継いだ 106・107",
        "items": {
            "83": {"value": "開いた背面 0・t* の切断端 0・穴 0（5 万本 × 36 コマ）", "verdict": "合格（事前検査。判定は番号41）"},
            "115": {"value": "同上", "verdict": "合格（事前検査。判定は番号41）"},
            "116": {"value": "同上", "verdict": "合格（事前検査。判定は番号41）"},
            "117": {"value": "原版：継ぎ目の切断 0・穴 0、減面なし。軽量版：原画視点の輪郭の差 %.3f px（座席の視点は未測定）" % r_light["r01_light"],
                    "verdict": "合格（原版）"},
            "106": {"value": "P13 (5d) 行の間の伸び %s（基準 %s）" % (p13["(5d)"]["value"], p13["(5d)"]["threshold"]),
                    "verdict": "合格（設計28・29 は不合格）" if p13["(5d)"]["pass"] else "不合格・記録のみ"},
            "107": {"value": "30 Hz の面の反転 %s（P13 (5g) %s）" % (r_flip["r01_original_fine"], p13["(5g)"]["value"]),
                    "verdict": "合格（設計29 の原版は %s）" % r_flip["d29_original"] if r_flip["r01_original_fine"] == 0 and p13["(5g)"]["pass"] else "不合格・記録のみ"},
            "P13_other": {k: {"value": v["value"], "threshold": v["threshold"], "pass": v["pass"]} for k, v in p13.items() if k in ("(2)", "(5b)", "(5c)", "(5e)")},
        },
    }

    record_only = {
        "lip_thickness_min_m": {"value": r_lip["r01_original_fine"], "light": r_lip["r01_light"], "design29": r_lip["d29_original"],
                                "verdict": "不合格・記録のみ（K*′ と動きの値。仕上げ28）", "note_ja": r_lip["note"]},
        "farwall_last_0p067s_m": {"value": r_far["r01_original_fine"], "design29": r_far["d29_original"], "verdict": "合格（設計29 の急な下がりは消えた）"},
        "ground_second_difference_30hz_m": {"value": r_ground["r01_original_fine"], "where": r_ground["note"], "verdict": "不合格・記録のみ（動きの値）"},
        "folds_over_120deg_per_frame_max": {"value": r_folds["r01_original_fine"], "criterion": r_folds["criterion"], "verdict": "記録のみ"},
        "pre_tstar_rim_cut_under_edge": {"value": r_ray_pre["r01_original_fine"], "verdict": "記録のみ（設計30）"},
        "layers": r_layers["r01_original_fine"],
        "light_120x200": {"layers": r_layers["r01_light"], "painting_regression_px": r_geo["r01_light"], "gate_values_px": r_gate["r01_light"],
                          "outline_diff_vs_original_px": r_light["r01_light"], "gpu_mib_estimate": r_mem["r01_light"],
                          "verdict": "名前を付けた非常用の予備（原画視点の回帰 0.669 px で不合格。色区と座席の輪郭は未測定。UV3 は古い 28修正01 の表）"},
        "tstar_fine_vs_16bit_old_bake_263_lower_px": [x for x in U["tstar_fine_vs_16bit"]["boundaries"] if x["item"] == "263"],
        "timing_ms_painting_seat": {"with_layer": [round(U["timing"]["pos_lo_1"]["wave_ms"]["painting"], 3), round(U["timing"]["pos_lo_1"]["wave_ms"]["seat"], 3)],
                                    "without_layer": [round(U["timing"]["pos_lo_0"]["wave_ms"]["painting"], 3), round(U["timing"]["pos_lo_0"]["wave_ms"]["seat"], 3)],
                                    "note_ja": "壁時計のおおよその値。同じ組でも回によって約 50% 揺れる（設計29）。PC の片目で HMD ではない"},
    }

    decision = {
        "adopted_ja": "原版＝設計28修正01 の F_final のパッケージそのもの（K*′ の格子 240 × 400、242 層）を、精度の層を読む DS29KeyposePlayer で再生し、色区は K*′ へ焼き直した表（af28r01_uvsdf_a45.bin・af28r01_uvwarp_a45.json）で描く",
        "reading_ja": "色区の後退の判定は、輪郭の両側（原画の空または描画の空から 2 px 以内）を除く読み（ds29r01_tstar_sym.py）で行う。直しの回が推奨した案を Q24 に従って採った（利用者の決定ではない）。評価器の定義のままの読みの値（6 項目・267 の帯 7）は記録し、K*′ の輪郭の差（2.7〜3.8 px）として仕上げ28 へ渡す",
        "dropped_ja": "(1) 評価器の定義のままで不合格として止める：焼き込みでは K*′ の輪郭の差を動かせないので、止めても直せない。(2) 2 回目の直し（輪郭の差の所の色区を外へ伸ばす焼き込みの規則を足す）：Q26 の「直しは 1 回まで」を超え、原画にない色を空の側へ塗ることになる",
    }

    return {
        "schema": "GreatWave.DS29R01.metrics/1",
        "number": "設計29修正01",
        "title_ja": "表示用サーフェスを設計28修正01 の新しい動き（F_final・K*′）で作り直し、再生器が精度の層を読むようにする",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_kind_ja": "numpy の検査器（設計29 の検査器を精度の層つきで）、Blender 5.2.2 ヘッドレスの射線と BVH、Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と美術優先28修正01 の評価器、進行役の独立の検査。HMD 実機の結果ではない",
        "acceptance": acceptance,
        "handoffs_from_design28r01": handoffs_in,
        "backlog": backlog,
        "record_only": record_only,
        "decision": decision,
        "time": {"ja": "ファイルの時刻で 9/29 14:46（最初のファイル）〜15:36（直しの回の最後）。Part A（再生器）と Part B（測定）は並べて行った。記録は 15:41〜。Q26 の日程の表では 3 時間で、設計28修正01 からの引き継ぎ (a)〜(d) を含めて進行役が 4 時間とした。Unity の 1 回はどれも 30 分より十分短い（DS29Render・DS27Formation の中の時間 7.6〜42.2 s、焼き込み 5.8 s）"},
        "handoffs_out": {
            "design30_ja": "t* より前の外周の切断端・縁の下（精度の層つき 27,866／1,396 本）。座席の船を新しい谷に座らせる（設計28修正01 から）",
            "design36_38_ja": "設計28 から渡された描画の傷（唇の端の梯子・モアレ、縦の継ぎ目、前面の足の縦の筋、爪の模様が埋まる、左端の横縞）。焼き直しの後の t* で面の中を横切る外殻線（K*′ の折れの線）。座席の見えない内壁の平らな藍濃と左の横の外挿の帯（番号41 とも関わる）",
            "polish28_ja": "評価器の定義のままの読みの色区の差（73・118・263 2.484 px、79 1.012 px、134 8.996 px、175 藍中 16.052 px、267 の白の帯 7）と 72 σ24 の 4.0075 px は、K*′ の輪郭の差（2.7〜3.8 px）によるので、K*′ の縁を原画に合わせ直す時に一緒に直す。唇先の厚さ 0.021 m（t* 0.259 m）。30 Hz の地面の二階差分 0.0673 m",
            "polish29_ja": "行 234〜239 の張り直し（形成の間の行 235〜237 の法線の折れ、行 238〜239 の 5 mm 未満の細い面どうしの接触）。HMD で見えた時だけ。軽量版を新しい UV3 の表で作り直すこと",
            "hmd_ja": "設計08〜10（PS VR2 の導入の後）。SPI はコンパイルだけ確かめた",
        },
    }


def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.splitlines()[0].strip()
    except Exception as e:  # 版が取れなくても記録は書く
        return "不明（%s）" % e


def run_json():
    import numpy
    import PIL
    code = sorted(
        ["Tools/GWWaveGen/ds29r01/" + f for f in os.listdir(P("Tools/GWWaveGen/ds29r01")) if f.endswith((".py", ".ps1"))]
        + ["Unity/Assets/GreatWave/Design27/Shaders/DS27KeyposeCore.cginc",
           "Unity/Assets/GreatWave/Design27/Shaders/DS27_NPR_White.shader",
           "Unity/Assets/GreatWave/Design27/Shaders/DS27_Outline_Keypose.shader",
           "Unity/Assets/GreatWave/Design27/Shaders/DS27KeyposeCapture.compute",
           "Unity/Assets/GreatWave/Design27/Scripts/DS27KeyposePlayer.cs",
           "Unity/Assets/GreatWave/Design29/Scripts/DS29KeyposePlayer.cs",
           "Unity/Assets/GreatWave/Design29/Editor/DS29Render.cs",
           "Unity/Assets/GreatWave/Design29/Editor/DS29R01ShaderCheck.cs",
           "Unity/Assets/GreatWave/Design29/Editor/DS29R01ProjectionBaker.cs",
           "Unity/Assets/GreatWave/Design29/Editor/DS29R01Bake.cs"])
    pkg = "Unity/Build/Design/28R01F/F_final/art_on/"
    inputs = [pkg + f for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin")] + [
        "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json",
        "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45.gwb",
        "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json",
        "Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_rows.npz",
        "Tools/PaintingTruth/colour/af28r01_params.json",
        "Tools/PaintingTruth/colour/af28_bake_input.py"]
    outs = [B + "/bake_kp/bake/af28r01_uvsdf_a45.bin", B + "/bake_kp/bake/af28r01_uvcat_a45.bin", B + "/bake_kp/bake/af28r01_uvwarp_a45.json",
            B + "/bake_kp/bake/af28r01_bake_a45.json", B + "/bake_kp/ds29r01_bake_entry.json",
            B + "/unity/f_final_kp/ds29_render_report.json", B + "/unity/f_final_kp/ds27_tstar_remeasure.json",
            B + "/unity/f_final_kp/ds29r01_tstar_verdict.json", B + "/unity/f_final_kp/t28/render/af28r01_class_ids.png",
            B + "/unity/f_final_kp/t28/render/af28r01_painting.png", B + "/unity/f_final/ds29_render_report.json",
            B + "/unity/check_gpu_f_final.json", B + "/unity/check_gpu_f_final_kp.json", B + "/unity/check_regress_d28.json",
            B + "/unity/check_regress_d28_kp.json", B + "/unity/check_regress_d27.json", B + "/unity/ds29r01_shader_check.json",
            B + "/unity/ds29r01_unity_check.json", B + "/unity/ds29r01_rebake_summary.json", B + "/unity/tstar_sym/tstar_sym.json",
            B + "/unity/lfgate_unity.json", B + "/measure/ds29r01_table.json", B + "/measure/run.json",
            B + "/indep_check/ic_check1.json", B + "/indep_check/ic_strict_fine.json", B + "/indep_check/ic_strict_hi16.json",
            B + "/indep_check/ic_blender_bvh_fine.json", B + "/indep_check/ic_blender_rays_fine.json", B + "/indep_check/ic_painting.json"]
    evidence = sorted(f for f in os.listdir(P(EV)) if f != "run.json")
    ps = "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render"
    commands = [
        "（Part A、再生器）" + ps + " -Log f_final -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/f_final -Stills \"m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0\" -Views \"painting,seat,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name f_final -ds29MeshFromPackage 0 -ds29CaptureRange -6,0\"",
        "（Part A）" + ps + " -Log regress_d28 -Package Build/Design/28/art_on -OutDir Build/Design/29R01/unity/regress_d28 -Views \"painting,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name src_d28 -ds29MeshFromPackage 0\"",
        "（Part A）powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design27.EditorTools.DS27Formation.RenderOnly -Log regress_d27 -Version art_on -Warp default -OutDir Build/Design/29R01/unity/regress_d27（ログの引数：-ds27Views painting,seat,side_left,seat_form -ds27Skip frames,capture）",
        "（Part A）powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01ShaderCheck.Run -Log shader_check",
        "（Part A）" + ps + " -Log timing_f_final_lo1 -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/timing/f_final_lo1 -Skip \"t28,capture,stills,video\" -Extra \"-ds29Name f_final_lo1 -ds29MeshFromPackage 0 -ds29PosLo 1 -ds29TimingFrames 600\"（lo0 は -ds29PosLo 0）",
        "（Part A）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Design/29R01/unity/f_final --package Unity/Build/Design/28R01F/F_final/art_on --range=-6,0 --out Unity/Build/Design/29R01/unity/check_gpu_f_final.json",
        "（Part A）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py regress --new Unity/Build/Design/29R01/unity/regress_d28 --ref Unity/Build/Design/29/unity/src_d28 --out Unity/Build/Design/29R01/unity/check_regress_d28.json（設計27 は --new …/regress_d27 --ref Unity/Build/Design/27/art_on_default --report ds27_render_report.json）",
        "（Part A）py -3.10 -B Tools/GWWaveGen/ds27/ds27_tstar_eval.py --run Unity/Build/Design/29R01/unity/f_final、py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py summary",
        "（Part B、測定）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py qa --decode fine／strict --decode fine／strict --decode hi、ds29r01_extra.py memory／tstar --unity-ids F_final_28R01F=Unity/Build/Design/28R01F/unity/F_final/t28/render/af28r01_class_ids.png／farwall／normals、ds29r01_light.py、ds29r01_table.py（全部は Unity/Build/Design/29R01/measure/run.json）",
        "（進行役の独立の検査、リポジトリの外の ic_decode.py・ic_check1.py・ic_strict.py・ic_blender.py・ic_painting.py。出力 Unity/Build/Design/29R01/indep_check/）",
        "（直しの回）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py",
        "（直しの回）powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds29r01/run_ds29r01_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log bake_kp（決定性：-Log bake_kp_rep -Extra \"-ds29r01BakeRoot Build/Design/29R01/bake_kp_rep\"）",
        "（直しの回）" + ps + " -Log f_final_kp -Package Build/Design/28R01F/F_final/art_on -WarpFile Build/Design/28R01F/F_final/timewarp_F_final.json -OutDir Build/Design/29R01/unity/f_final_kp -Stills \"m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0\" -Views \"painting,seat,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name f_final_kp -ds29MeshFromPackage 0 -ds29KStarGwb Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb -ds29Sdf Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json\"",
        "（直しの回）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_tstar_eval.py --run Unity/Build/Design/29R01/unity/f_final_kp、ds29r01_tstar_sym.py、ds29r01_lfgate.py",
        "（直しの回）" + ps + " -Log regress_d28_kp -Package Build/Design/28/art_on -OutDir Build/Design/29R01/unity/regress_d28_kp -Views \"painting,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name src_d28 -ds29MeshFromPackage 0\"、ds29r01_unity_check.py regress --new Unity/Build/Design/29R01/unity/regress_d28_kp --ref Unity/Build/Design/29/unity/src_d28 --out Unity/Build/Design/29R01/unity/check_regress_d28_kp.json",
        "（記録）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Design/29R01/unity/f_final_kp --package Unity/Build/Design/28R01F/F_final/art_on --range=-12,0 --out Unity/Build/Design/29R01/unity/check_gpu_f_final_kp.json",
        "（記録）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_figures.py（図と静止画。fig_ds29r01_tstar_compare.png の 3 段目は評価器の境界の図 f_final_kp/t28/evidence/28R01_boundaries.png の 2 倍の切り出し）。動画は f_final_kp/video の 4 本を ds29r01_<視点>_30fps.mp4 の名前でそのまま写し、表と照合の JSON・md 7 つも名前だけ変えて写した",
        "（記録）py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_record.py",
    ]
    return {
        "schema": "GreatWave.DS29R01.run/1",
        "number": "設計29修正01",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "machine": platform.platform(),
        "python": platform.python_version(), "numpy": numpy.__version__, "pillow": PIL.__version__,
        "unity": "6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）",
        "blender": "5.2.2（ヘッドレス。設計29 の検査器と独立の検査）",
        "ffmpeg": tool_version([FFPROBE_DIR + "/ffmpeg.exe", "-version"]),
        "commands": commands,
        "scripts": {c: sha(c) for c in code},
        "scripts_outside_repo_ja": "進行役の独立の検査の ic_decode.py・ic_check1.py・ic_strict.py・ic_blender.py・ic_painting.py は、会話の作業フォルダー（リポジトリの外）にあり、コミットしない（作り手のコードを読まずに書いた検査）",
        "inputs": {c: sha(c) for c in inputs},
        "build_outputs": {c: sha(c) for c in outs},
        "evidence": {EV + "/" + f: sha(EV + "/" + f) for f in evidence},
        "protected_ja": "設計26〜28 のコミット済みのファイル、美術優先28・28修正01 の焼き込みと Tools/PaintingTruth は変えていない。DS29Render の報告で場面・設計27 のファイル・K* の前後の SHA-256 が同じ（protectedUnchanged = true）。場面は保存していない",
        "not_in_repo_ja": "パッケージ・焼き込み（64 MiB の色区テクスチャなど）・描画の全出力・GPU の読み戻しは Git 対象外の Unity/Build/Design/29R01/ に置いた",
    }


def main():
    m = metrics()
    with open(P(EV + "/metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
        f.write("\n")
    r = run_json()
    with open(P(EV + "/run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("DS29R01_RECORD metrics=%d keys run.evidence=%d" % (len(m), len(r["evidence"])))


if __name__ == "__main__":
    sys.exit(main())
