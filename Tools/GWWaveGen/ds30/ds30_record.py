# -*- coding: utf-8 -*-
"""設計30：証拠（Docs/Evidence/Design/30/）の図・動画・JSON の写しと、metrics.json・run.json を書く。

値はここで作らない。Git 対象外の Unity/Build/Design/30/ にある測定の JSON（第A部の numpy の検査、第B部と直し1 の Unity の描画・
Play モード・t* の回帰、進行役の独立の検査の出力の写し indep_check/）から写すだけ。図は 1920 × 1080 の枠に収める（縮尺だけ変える）。
参照モデルを描いた画像は入れない（配置の平面図 ds30_layout_plan_tstar.png は、この番号の海の高さの地図に、参照モデルから測った
数値の位置を印で置いたもの。参照モデルの形は描いていない）。

入力（読むだけ）：
  Unity/Build/Design/30/checks/ds30_checks.json・ds30_painting_regression_table.json（第A部）
  Unity/Build/Design/30/sea/ds30_generate_log.json・sea_function.json・boat_support.json（第A部）
  Unity/Build/Design/30/layout/ds30_layout_record.json・ref/ds30_ref_cache_log.json（第A部、参照モデルは数値だけ）
  Unity/Build/Design/30/unity/single/…（第B部。直しの前）、unity/single_fix1/…（直し1 の後。採用）
  Unity/Build/Design/30/indep_check/seam_out.json・eye_play_out.json・pen_out.json（進行役の独立の検査の出力の写し）
出力：Docs/Evidence/Design/30/（図 7 枚、動画 5 本、JSON の写し、metrics.json、run.json）
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds30/ds30_record.py
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B = "Unity/Build/Design/30"
F1 = B + "/unity/single_fix1"
F0 = B + "/unity/single"
EV = "Docs/Evidence/Design/30"
FF_DIR = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin"
W, H = 1920, 1080


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


def r(x, n=4):
    return None if x is None else round(float(x), n)


# ---------------------------------------------------------------- 図・動画・JSON の写し
FIGS = [
    # (元, 証拠の名前, 何か)
    (F1 + "/stills/ds30_painting_t12.0s_tau+0.000.png", "ds30_painting_tstar.png", "原画視点の t*（Unity、直し1 の後）"),
    (F1 + "/stills/ds30_seat_toward_wave_t10.0s_tau-0.700.png", "ds30_seat_toward_wave_t10.png", "座席から波の方向の t 10 s（右の高い波・手前の小波・谷）"),
    (F1 + "/stills/ds30_seat_toward_wave_t12.0s_tau+0.000.png", "ds30_seat_toward_wave_tstar.png", "座席から波の方向の t*（継ぎ目の灰色の線が消えた）"),
    (F1 + "/t28_seaids/t28/render/af28r01_seat_low.png", "ds30_seat_low_tstar.png", "座席の低い視点の t*（浮いた泡の仮置きが消えた）"),
    (F1 + "/fig_ds30_stills_sheet.png", "fig_ds30_stills_sheet.png", "4 視点 × t 2・6・8・10・11・12 s の一覧（Unity）"),
    (F1 + "/fig_ds30_fix1.png", "fig_ds30_fix1.png", "直し1 の前と後（座席から波の方向 f390・原画視点 f315・座席の低い視点 t*）"),
    (B + "/layout/ds30_layout_plan_tstar.png", "fig_ds30_layout_plan.png", "t* の平面図（numpy。白の × は一次設計の位置、赤の ◇ は二次設計の位置）"),
    (B + "/checks/ds30_painting_tstar_ids_diff.png", "ds30_numpy_painting_ids_diff.png", "第A部の numpy の t* 原画視点の ID の違い（Unity の描画ではない）"),
]
VIDEOS = ["painting", "seat", "seat_toward_wave", "side_left", "grid_2x2"]
JSON_COPIES = [
    (B + "/checks/ds30_checks.json", "ds30_checks_numpy.json"),
    (B + "/checks/ds30_painting_regression_table.json", "ds30_painting_regression_numpy.json"),
    (B + "/layout/ds30_layout_record.json", "ds30_layout_record.json"),
    (B + "/ref/ds30_ref_cache_log.json", "ds30_ref_cache_log.json"),
    (B + "/sea/sea_function.json", "ds30_sea_function.json"),
    (F1 + "/ds30b_summary.json", "ds30_unity_summary.json"),
    (F1 + "/ds30_tstar_regress.json", "ds30_tstar_regress.json"),
    (F1 + "/ds30_fix1.json", "ds30_fix1.json"),
]


def fit_png(src, dst):
    im = Image.open(P(src)).convert("RGB")
    if im.size == (W, H):
        shutil.copyfile(P(src), P(dst))
        return "copy"
    s = min(W / im.size[0], H / im.size[1])
    sz = (max(1, round(im.size[0] * s)), max(1, round(im.size[1] * s)))
    im2 = im.resize(sz, Image.LANCZOS)
    can = Image.new("RGB", (W, H), (28, 28, 28))
    can.paste(im2, ((W - sz[0]) // 2, (H - sz[1]) // 2))
    can.save(P(dst), optimize=True)
    return "fit %dx%d -> %dx%d" % (im.size[0], im.size[1], sz[0], sz[1])


def copy_evidence():
    os.makedirs(P(EV), exist_ok=True)
    log = []
    for src, name, _ in FIGS:
        log.append((name, fit_png(src, EV + "/" + name)))
    for v in VIDEOS:
        src = F1 + "/video/ds30_%s_30fps.mp4" % v
        dst = EV + "/ds30_%s_30fps.mp4" % v
        shutil.copyfile(P(src), P(dst))
        if os.path.getsize(P(dst)) > 5 * 1024 * 1024:
            raise SystemExit("動画が 5 MB を超える：" + dst)
        log.append((dst, "copy"))
    for src, name in JSON_COPIES:
        shutil.copyfile(P(src), P(EV + "/" + name))
        log.append((name, "copy"))
    return log


# ---------------------------------------------------------------- 直し1 の外殻線の切り方の数え直し
def grey_px(rel, y0):
    import numpy as np
    a = np.asarray(Image.open(P(rel)).convert("RGB")).astype(int)
    R, B_ = a[..., 0], a[..., 2]
    return int((((R > 50) & (R < 160)) & ((B_ - R) < 40))[y0:].sum())


def inset_trials():
    """診断の描画（fix1_diag_i<列>）の座席から波の方向の静止画で、灰色の画素（50 < R < 160 かつ B − R < 40、y ≥ 560）を数え直す"""
    out = {"rule_ja": "50 < R < 160 かつ B − R < 40、y ≥ 560（1920 × 1080）。記録の時に静止画から数え直した", "cols": {}}
    for i in ("0", "1", "3", "10", "30", "400"):
        d = B + "/unity/fix1_diag_i%s/stills/" % i
        out["cols"][i] = {"t11": grey_px(d + "ds30_seat_toward_wave_t11.0s_tau-0.203.png", 560),
                          "t12": grey_px(d + "ds30_seat_toward_wave_t12.0s_tau+0.000.png", 560)}
    out["note_ja"] = "400 は本体の列の数より大きいので主役波の外殻線を描かない読み（比べるための下限）"
    same = True
    names = []
    for sub in ("stills", "t28_seaids/t28/render"):
        d8 = B + "/unity/fix1_diag_t28_i8/" + sub
        for f in sorted(os.listdir(P(d8))):
            if not f.endswith(".png"):
                continue
            h = {sha(B + "/unity/fix1_diag_t28_i%s/%s/%s" % (i, sub, f)) for i in ("8", "10", "12")}
            same = same and len(h) == 1
            names.append(sub + "/" + f)
    out["inset_8_10_12_pixel_identical"] = {"value": same, "files": len(names),
                                            "note_ja": "fix1_diag_t28_i8・i10・i12 の静止画（原画視点・座席・座席から波の方向 × t 6・10・11・12 s）と t* の画像の SHA-256 が同じか"}
    return out


def line_ids_changed():
    import numpy as np
    a = np.asarray(Image.open(P(F0 + "/t28_seaids/t28/render/af28r01_line_ids.png")).convert("RGB"))
    b = np.asarray(Image.open(P(F1 + "/t28_seaids/t28/render/af28r01_line_ids.png")).convert("RGB"))
    d = np.any(a != b, axis=-1)
    ys = np.where(d.any(1))[0]
    return {"size": [int(a.shape[1]), int(a.shape[0])], "changed_px": int(d.sum()), "rows": [int(ys.min()), int(ys.max())] if len(ys) else None,
            "note_ja": "t* の原画視点の外殻線の ID 画像（2 倍の大きさ）で、直し1 の前後に違う画素。評価器の値は変わらない"}


def tstar_coverage():
    """t* の色区の ID 画像で、29修正01（主役波だけ）から設計30（主役波＋海）への空 → 波・波 → 空の画素と、原画視点の画像の同じ行"""
    import numpy as np
    a = np.asarray(Image.open(P("Unity/Build/Design/29R01/unity/f_final_kp/t28/render/af28r01_class_ids.png")).convert("RGB"))
    b = np.asarray(Image.open(P(F1 + "/t28_seaids/t28/render/af28r01_class_ids.png")).convert("RGB"))
    sa, sb = np.all(a == 255, -1), np.all(b == 255, -1)
    pa = np.asarray(Image.open(P("Unity/Build/Design/29R01/unity/f_final_kp/t28/render/af28r01_painting.png")).convert("RGB"))
    pb = np.asarray(Image.open(P(F1 + "/t28_seaids/t28/render/af28r01_painting.png")).convert("RGB"))
    d = np.any(pa != pb, -1)
    ys = np.where(d.any(1))[0]
    return {"class_ids_sky_to_wave_px": int((sa & ~sb).sum()), "class_ids_wave_to_sky_px": int((~sa & sb).sum()),
            "painting_first_differing_row": int(ys.min()) if len(ys) else None, "painting_changed_px": int(d.sum()),
            "note_ja": "ID 画像は 3840 × 2160、原画視点の画像は 1920 × 1080。行 0 から最初に違う行の前までは 29修正01 と画素まで同じ（212 の空の上の方）"}


# ---------------------------------------------------------------- metrics.json
def metrics():
    A = load(B + "/checks/ds30_checks.json")
    AR = load(B + "/checks/ds30_painting_regression_table.json")
    G = load(B + "/sea/ds30_generate_log.json")
    SF = load(B + "/sea/sea_function.json")
    BS = load(B + "/sea/boat_support.json")
    LR = load(B + "/layout/ds30_layout_record.json")
    RC = load(B + "/ref/ds30_ref_cache_log.json")
    S1 = load(F1 + "/ds30b_summary.json")
    S0 = load(F0 + "/ds30b_summary.json")
    T1 = load(F1 + "/ds30_tstar_regress.json")
    X1 = load(F1 + "/ds30_fix1.json")
    RR1 = load(F1 + "/ds30_render_report.json")
    RR0 = load(F0 + "/ds30_render_report.json")
    V28 = load(F1 + "/t28_seaids/ds29r01_tstar_verdict.json")
    V29 = load("Unity/Build/Design/29R01/unity/f_final_kp/ds29r01_tstar_verdict.json")
    IS = load(B + "/indep_check/seam_out.json")
    IE = load(B + "/indep_check/eye_play_out.json")
    IP = load(B + "/indep_check/pen_out.json")
    PAR = load("Tools/GWWaveGen/ds30/ds30_params.json")

    it = S1["items"]
    sm = A["seam"]
    nd = sm["normal_dot"]
    fr = nd["by_ray_kind"]
    se = it["start_end"]["per_sheet"]
    tv = T1["sets"]["t28_seaids"]
    tv_hero = T1["sets"]["t28"]
    base = T1["base_29r01"]
    pen_layers = IP["layers"]

    # 色区の項目：設計30（主役波＋海の ID）と 29修正01 と 28修正01 を並べる
    colour_items = {}
    for k, v in V28["colour_boundaries"]["items"].items():
        v29 = V29["colour_boundaries"]["items"].get(k, {})
        colour_items[k] = {"design30_max_px": v["now_max_px"], "design29r01_max_px": v29.get("now_max_px"),
                           "r28r01_max_px": v["r28r01_max_px"], "verdict_now": v["verdict_now"], "verdict_28r01": v["verdict_28r01"],
                           "diff_vs_29r01_px": None if v29.get("now_max_px") is None else round(v["now_max_px"] - v29["now_max_px"], 4)}
    c265 = {k: {"verdict_now": V28["colour_265_267"][k]["verdict_now"], "verdict_28r01": V28["colour_265_267"][k]["verdict_28r01"],
                "verdict_29r01": V29["colour_265_267"][k]["verdict_now"]} for k in ("265", "266", "267")}

    acceptance = {
        "ja": "計画 §2.1 の設計30 の最小の受入（Q26：この番号は最小の受入だけを満たす）。値は直し1 の後（unity/single_fix1）の Unity の描画と、第A部の numpy の検査、進行役の独立の検査から",
        "seam_band_recorded": {
            "verdict": "合格（記録）",
            "hero_near_numpy": {"height_or_position_gap_with_lo_mm": r(sm["seam_fine_max_m"] * 1000, 4), "gap_16bit_only_mm": r(sm["seam_hi_only_max_m"] * 1000, 3),
                                "velocity_diff_mm_s": r(sm["vel_diff_max_mps"] * 1000, 3),
                                "normal_dot_front_outside_boat_min": r(fr["front"]["outside_boat_min"]), "normal_dot_front_outside_boat_p1": r(fr["front"]["outside_boat_p1"]),
                                "normal_dot_front_outside_boat_worst": nd["front_outside_boat_worst"],
                                "normal_dot_back_min": r(fr["back"]["min"]), "normal_dot_back_p1": r(fr["back"]["p1"]),
                                "normal_dot_under_boat_min": r(fr["front"]["under_boat_min"]),
                                "normal_dot_cone_fans_min": [r(fr["fanL"]["min"]), r(fr["fanR"]["min"])],
                                "note_ja": "第A部（numpy、242 節点）。法線は片側の頂点法線どうしの内積。錐の扇（主役波の行 0・239 の縮んだ点）では法線が決まらない"},
            "hero_near_unity": {"max_gap_m": it["seam_hero_near"]["max_gap_m"], "max_dy_m": it["seam_hero_near"]["max_dy_m"], "max_dv_mps": it["seam_hero_near"]["max_dv_mps"],
                                "side_normal_dot_min": r(it["seam_hero_near"]["side_normal_dot_min"]), "side_normal_dot_p01_min": r(it["seam_hero_near"]["side_normal_dot_p01_min"]),
                                "side_below09_max": it["seam_hero_near"]["side_below09_max"], "side_count": it["seam_hero_near"]["side_count"],
                                "all_points_normal_dot_min": r(it["seam_hero_near"]["normal_dot_min"]),
                                "note_ja": "第B部・直し1 の Unity の GPU の読み戻し（再生の全コマ）。法線は GPU の DS27Normal（主役波は描かない余白の列も含む格子で求める）"},
            "near_far_unity": {"max_gap_m": it["seam_near_far"]["max_gap_m"], "tjunction_max_gap_m": it["seam_near_far"]["tjunction_max_gap_m"],
                               "normal_dot_min": r(it["seam_near_far"]["normal_dot_min"])},
            "near_far_numpy": {"gap_mm": r(sm["nearfar_max_m"] * 1000, 4), "tjunction_residual_mm": r(sm["tjunction_resid_max_m"] * 1000, 4)},
            "independent": {"seam_pos_max_mm_lo": r(IS["seam_pos_max_mm_lo"], 4), "seam_height_max_mm_lo": r(IS["seam_height_max_mm_lo"], 4),
                            "seam_pos_max_mm_hi_only": r(IS["seam_pos_max_mm_hi_only"], 3), "seam_height_max_mm_hi_only": r(IS["seam_height_max_mm_hi_only"], 3),
                            "seam_vel_max_mm_s": r(IS["seam_vel_max_mm_s"], 3), "seam_vel_mid_interval_max_mm_s": r(IS["seam_vel_mid_interval_max_mm_s"], 3),
                            "ring_is_body_boundary": IS["ring_is_body_boundary"]["ring_n"] == IS["ring_is_body_boundary"]["boundary_n"] and not IS["ring_is_body_boundary"]["missing_from_ring"],
                            "ring_n": IS["ring_is_body_boundary"]["ring_n"],
                            "hero_row0_row239_cone_spread_mm": [r(IS["hero_row0_spread_m_max"] * 1000, 2), r(IS["hero_row239_spread_m_max"] * 1000, 2)],
                            "seam_orientation_inconsistent_edges": IS["seam_orientation_inconsistent_edges"],
                            "normal_dot_col18": {"min": r(IS["vertex_normal_dot_col18"]["min"]), "p1": r(IS["vertex_normal_dot_col18"]["p1"])},
                            "normal_dot_col394": {"min": r(IS["vertex_normal_dot_col394"]["min"]), "p1": r(IS["vertex_normal_dot_col394"]["p1"])},
                            "normal_dot_sides_worst": IS["vertex_normal_dot_sides_worst"],
                            "normal_dot_tstar_sides": IS["vertex_normal_dot_tstar_sides"],
                            "near_far_seam_max_mm": r(IS["near_far_seam_max_mm"], 4), "tjunction_residual_mm": r(IS["tjunction_residual_mm"], 4),
                            "note_ja": "進行役の独立の検査（作り手のコードを読まずに書いた復号器。リポジトリの外）"},
        },
        "no_step_double_surface_hole": {
            "verdict": "合格（直し1 の後。直しの前は、浮いた泡の仮置き（二重の白）と継ぎ目の灰色の線で不合格）",
            "holes": {"frames": it["holes"]["holes"]["frames"], "seat_worst_px": it["holes"]["holes"]["seatWorstHolePx"],
                      "painting_worst_px": it["holes"]["holes"]["paintingWorstHolePx"],
                      "without_lowered_flat_sea_and_curtain": {"seat_worst_px": it["holes"]["holesNoFlat"]["seatWorstHolePx"], "seat_frames": it["holes"]["holesNoFlat"]["seatFramesWithHoles"],
                                                              "painting_worst_px": it["holes"]["holesNoFlat"]["paintingWorstHolePx"], "painting_frames": it["holes"]["holesNoFlat"]["paintingFramesWithHoles"]},
                      "method_ja": it["holes"]["holes"]["methodJa"]},
            "interpenetration_independent": {"knots": len(pen_layers), "near_in_hero": IP["totals"]["near_in_hero"], "hero_under_near": IP["totals"]["hero_under_near"],
                                             "near_flip_per_knot_max": max(l["near_flip"] for l in pen_layers),
                                             "near_flip_area_per_knot_max_m2": r(max(l["near_flip_area_m2"] for l in pen_layers), 5), "far_flip": IP["totals"]["far_flip"],
                                             "note_ja": "裏返った面は near の行 0 の錐の扇の細片だけ（面積の和 ≤ 0.0013 m²/節点）"},
            "numpy_flips_near_max": A["seam"]["flips_summary"]["near_max"], "numpy_flips_far_max": A["seam"]["flips_summary"]["far_max"],
            "floating_foam_fixed": {"hidden_by_default": "M1_ForegroundFoam_Static" in RR1["hidden"], "attached_foam": RR1["attachedFoam"],
                                    "tstar_seat_low_white_px_before_after": [X1["tstar_seat_low"]["white_before"], X1["tstar_seat_low"]["white_after"]],
                                    "seat_video_hold_white_px_before_after": [X1["videos"]["seat"]["white_before"][24], X1["videos"]["seat"]["white_after"][24]]},
            "seam_grey_line_fixed": {"hero_line_inset_cols": RR1["heroLineInset"], "hero_line_triangles": RR1["heroLineTrianglesWindow"], "hero_triangles": RR1["heroTrianglesWindow"],
                                     "grey_rule_ja": X1["grey_rule_ja"],
                                     "seat_toward_wave_grey_px_frames_330_360_390_420_before": [X1["videos"]["seat_toward_wave"]["grey_before"][i] for i in (18, 24, 30, 36)],
                                     "seat_toward_wave_grey_px_frames_330_360_390_420_after": [X1["videos"]["seat_toward_wave"]["grey_after"][i] for i in (18, 24, 30, 36)],
                                     "tstar_seat_low_grey_px_before_after": [X1["tstar_seat_low"]["grey_before"], X1["tstar_seat_low"]["grey_after"]]},
            "hero_margins_not_drawn": {"hero_cols": [RR1["heroColMin"], RR1["heroColMax"]], "triangles_drawn": RR1["heroTrianglesWindow"], "triangles_full": RR1["heroTrianglesFull"]},
            "placeholders_hidden": RR1["hidden"], "flat_sea": {"mode": RR1["flatSeaMode"], "top_y_m": RR1["flatSeaY"]}, "seam_curtain": RR1["curtain"],
        },
        "tstar_painting_regression": {
            "verdict": "合格（設計30 による後退なし：主役波＋海の ID 画像で 29修正01 と全部の値の差 0。28修正01 に対する 134・267（定義のままの読み）と 72 σ24 p95 4.0075 px は 29修正01 から引き継いだ状態で、29修正01 の両側の読みでは合格のまま）",
            "sea_free_control_identical_to_29r01": T1["ctrl_identical_to_29r01_f_final_kp"]["all"],
            "silhouettes_78_130_131_unity_px": {k: v["unity_max_px"] for k, v in tv["verdict"]["silhouettes_vs_kstar_prime"]["rows"].items()},
            "silhouettes_diff_vs_29r01_px": tv["silhouette_diff_vs_29r01_px"],
            "lfgate": {"132_sigma12_max_px": r(tv["lfgate"]["132_sigma12_max"]), "72_sigma24_p95_px": r(tv["lfgate"]["72_sigma24_p95"]),
                       "diff_vs_29r01_px": tv["lfgate_diff_vs_29r01_px"]},
            "colour_strict_worst_diff_vs_28r01_px": tv["verdict"]["colour_worst_abs_diff_px"], "colour_strict_items_over_0p5": tv["verdict"]["items_over_0p5"],
            "colour_strict_verdict_changes_vs_28r01": tv["verdict"]["verdict_changes_vs_28r01"],
            "colour_items": colour_items, "colour_265_267": c265,
            "colour_two_sided_worst_px": tv["sym"]["worst_abs_diff_px"], "colour_two_sided_diff_vs_29r01_px": tv["sym"]["worst_diff_vs_29r01_px"],
            "colour_two_sided_267_bands": {k: v["sym_bands"] for k, v in tv["sym"]["flat_painting_view_266_267"].items()},
            "items_212_69_70_ja": "212：原画視点の画像の行 0〜379 は 29修正01 と画素まで同じ（空の上の方）。69・70：t* の主役波と右の船は変わらない（主役波の描画は 29修正01 と同じ、右の船は動かさない）。どちらも別には評価していない",
            "hero_only_reading_artefact": {"78_unity_px": tv_hero["verdict"]["silhouettes_vs_kstar_prime"]["rows"]["78"]["unity_max_px"],
                                           "72_sigma24_p95_px": r(tv_hero["lfgate"]["72_sigma24_p95"], 2),
                                           "note_ja": "主役波の本体だけの ID（t28）。余白を描かないので海の所が空になり、評価器が空と読む。回帰ではない（読みは t28_seaids）"},
            "coverage_vs_29r01": tstar_coverage(),
            "numpy_part_a": {r_["item"]: r_["evidence"] for r_ in AR["rows"]},
            "base_29r01_colour_worst_px": base["colour_worst_abs_diff_px"], "base_29r01_sym_worst_px": base["sym_worst_abs_diff_px"],
        },
        "start_end_no_jump": {
            "verdict": "合格",
            "waiting_frames_same_as_t0": it["start_end"]["waiting_frames_same_as_t0"], "holding_frames_same_as_tstar": it["start_end"]["holding_frames_same_as_tstar"],
            "per_sheet_m": {k: {"start_step": r(v["start_step_m"]), "max_next30": r(v["max_next30_m"]), "median_next30": r(v["median_next30_m"]),
                                "end_step_mm": r(v["end_step_m"] * 1000, 3), "max_prev30": r(v["max_prev30_m"]), "hold_max_step": v["hold_max_step_m"],
                                "play_max_step": r(v["play_max_step_m"])} for k, v in se.items()},
            "rule_ja": it["start_end"]["rule_ja"],
            "jitter": it["jitter"],
            "tau_t0": RR1["tauAtT0"], "tau_tstar": RR1["tauAtTStar"],
            "play_mode": it["play_mode"],
            "independent": {"first_steps_m": [r(x) for x in IE["play_first_steps_m"]], "steps_into_tstar_m": [r(x, 6) for x in IE["play_steps_359_362_m"]],
                            "hold_step_max_m": IE["hold_step_max_m"], "play_step_max_m": r(IE["play_step_max_m"])},
        },
        "seat_eye_never_under_water": {
            "verdict": "合格",
            "unity": {"frames": it["seat_eye"]["frames"], "under_water_frames": it["seat_eye"]["under_water_frames"],
                      "min_clearance_m": r(it["seat_eye"]["min_clearance_m"]), "at_t_s": r(it["seat_eye"]["min_clearance_t"], 3)},
            "numpy_part_a": {"frames": A["boat"]["frames"], "heave_under_water_frames": A["boat"]["heave_under_water_frames"],
                             "heave_min_clearance_m": r(A["boat"]["heave_min_clearance_m"]),
                             "static_under_water_frames": A["boat"]["static_under_water_frames"], "static_min_clearance_m": r(A["boat"]["static_min_clearance_m"])},
            "independent": {"heave_under_frames": IE["eye_heave_under_frames"], "heave_min_clear_m": r(IE["eye_heave_min_clear_m"]), "frame": IE["eye_heave_min_clear_frame"],
                            "static_under_frames": IE["eye_static_under_frames"], "static_min_clear_m": r(IE["eye_static_min_clear_m"])},
            "heave": {"delta_range_m": [r(x, 3) for x in A["boat"]["delta_range_m"]], "max_step_m_per_frame": r(A["boat"]["delta_max_step_m_per_frame"]),
                      "max_accel_m_s2": r(A["boat"]["delta_max_accel_m_per_s2"], 2), "smooth_s": PAR["boat"]["smooth_s"]},
            "eye": {"eye_world_tstar": BS["eye_world_tstar"], "deck_world_tstar": BS["deck_world_tstar"], "eye_above_deck_m": BS["eye_above_deck_m"],
                    "note_ja": "作業の指示の「甲板の 1.83 m 上」は目のワールドの高さ（y 1.83 m）。目は甲板の 1.2 m 上（seat_v1）"},
        },
        "outer_rim_not_above_sea": {
            "verdict": "合格",
            "free_edges_numpy": {"count": A["rim"][0]["free_edges_topology"], "y_max_m": r(A["rim"][0]["free_edge_y_max_m"], 3),
                                 "taus": [x["tau"] for x in A["rim"]], "note_ja": "自由な縁は far のすその下端（y = −8 m）だけ。どの τ でも同じ"},
            "hero_cut_edges_design29_29r01": [37215, 27866], "hero_cut_edges_now": 0,
            "note_ja": "主役波の余白（列 0〜17・395〜399）を描かず、near の行 0 が本体の境の輪（1230 点）へつながる。far の外周は y = 0（半径 650 m）",
        },
    }

    ft = SF["features"]
    design = {
        "ja": "計画 §2.1 の設計30 の中身（Q10・Q16・Q17・Q18 の注記。進行役の読み、既定値・利用者未確認）",
        "sea_formula": {"formula_ja": SF["formula_ja"], "reference_impl": SF["reference_impl"],
                        "carrier_components": len(SF["carrier"]["kx"]), "swell_components": len(SF["swell"]["kx"]),
                        "Ac_source": SF["Ac_source"], "Ac_lateral_taper_m": SF["Ac_lateral_taper_m"], "calm": SF["calm"],
                        "note_ja": "計画の「2〜3 成分の解析式」ではなく、主役波と同じ式（搬送波 128・うねり 64 の成分、行ごとの搬送波の振幅の表 Ac_knots）をそのまま使った（Q10 の注記「主役波と同じ交差うねりと搬送波の解析式」を優先。成分の数を減らすと主役波の境で式が合わない）"},
        "sheets": {"near": {"rows": G["near_rows"], "cols": G["near_cols"], "y_range_m": [r(x, 3) for x in G["near_y_range"]], "precision": G["near"]["precision"], "gpu": G["near"]["gpu"]},
                   "far": {"rows": G["far_rows"], "cols": G["far_cols"], "y_range_excluding_skirt_m": [r(x, 3) for x in G["far_y_range_excluding_skirt"]],
                           "precision": G["far"]["precision"], "gpu": G["far"]["gpu"], "radius_m": 650, "skirt_bottom_y_m": -8,
                           "radial_taper_m": [PAR["grid"]["far_taper_start_m"], PAR["grid"]["far_taper_end_m"]]},
                   "knot_tau_same": S1["knot_tau_same"], "frame_same": S1["frame_same"], "layers": 242, "ring0_count": G["ring0_count"],
                   "gpu_mib_sheets_unity": S1["gpu_mib_sheets"]},
        "band": {k: PAR["band"][k] for k in ("carrier_blend_m", "feature_blend_m", "slope_decay_m", "boat_blend_m", "note_ja")},
        "near_outline_ja": "near は本体の境の輪（行 0）から競技場形の外周（前 a +%s・後 a %s・右 c +%s・左 c %s m）まで 44 行。far は near の外周の %s 列ごとを行 0 とし、半径 %s m まで 19 行（far_ring_count %s）、外周の下に %s m のすそ。どれも波の枠とともに動く切り抜き" % (PAR["grid"]["stadium_a_front_m"], PAR["grid"]["stadium_a_back_m"], PAR["grid"]["stadium_c_right_m"], PAR["grid"]["stadium_c_left_m"], PAR["grid"]["far_subsample"], PAR["grid"]["far_radius_m"], PAR["grid"]["far_ring_count"], PAR["grid"]["skirt_depth_m"]),
        "guides": {"ds_swell_calm_tau_s": SF["calm"]["swell_calm_tau_s"], "ds_sea_calm_painting_tau_s": SF["calm"]["sea_calm_painting_tau_s"],
                   "ds30_right_wave_peak": LR["second_design"]["right_wave_peak"], "ds30_small_wave_apex": LR["second_design"]["small_wave"],
                   "ds30_small_wave_params": {k: ft["ds30_small_wave"][k] for k in ("apex_a", "apex_c", "height_m", "radius_back_m", "radius_front_m", "radius_side_m", "power")},
                   "ds30_trough_continue_deepest": LR["second_design"]["trough_continue_deepest"],
                   "ds30_boat_support": {k: ft["ds30_boat_support"][k] for k in ("inner_m", "outer_m", "end_fade_m")},
                   "growth": "g(τ) = 主役波の頂の高さの比（growth_knots、242 点、t* で 1）", "moves_with_wave_frame": True},
        "layout": {"reference_numbers": LR["reference"], "hero": LR["hero"], "first_design": LR["first_design"],
                   "second_design_summary": {k: LR["second_design"][k] for k in ("small_wave", "right_wave_peak", "trough_in_sheet", "trough_continue_deepest")},
                   "differences": [{"id": d["id"], "item": d["item"]} for d in LR["differences"]],
                   "reference_cache": {"created_sha256": RC["events"][0]["sha256"], "deleted_sha256": [e["sha256"] for e in RC["events"] if e["event"] == "cache_deleted" and e["file"].endswith(".npz")],
                                       "cache_dir_exists_after_delete": RC["cache_dir_exists_after_delete"], "source_sha256": RC["source_sha256"]},
                   "credit_ja": LR["reference"]["credit_ja"],
                   "generator_reads_obj": False,
                   "note_ja": "参照モデルは ds30_refmeasure.py だけが読み（SHA-256 を照合、Git 対象外の一時キャッシュ、終わりに削除）、生成器（ds30_generate.py・ds30_sea.py）は OBJ も数値のファイルも読まない。配置の記録 ds30_layout.py は数値のファイル（ds30_ref_layout.json）だけを読む"},
        "boat_support": {"tstar_keel_immersion_m": [r(x, 3) for x in A["boat"]["tstar_keel_immersion_m"]], "draft_m": BS["keel_line"]["draft_m"],
                         "keel_immersion_heave_m": A["boat"]["keel_immersion_heave"],
                         "note_ja": "t* で竜骨 + 喫水の水面（竜骨の沈み 0.45〜0.61 m、喫水 0.38 m）。t* より前は t* の姿勢のまま鉛直だけ上下（heave）"},
    }

    backlog = {
        "ja": "計画 §2.1 の設計30 のバックログ：88・93（海面が途切れない。記録）、94（原画カメラ固定）",
        "items": {
            "88": {"value": "船の周囲から前方の波まで：穴 0 px（座席 5 面 × 141 コマ）、主役波と near の貫通 0、継ぎ目の差 ≤ 0.033 mm、泡の仮置きの二重の白と継ぎ目の灰色の線は直し1 で消した",
                   "verdict": "記録（PC の描画。交接の前・中・後は段階9 の場面の移り変わりで判定）"},
            "93": {"value": "far は半径 650 m、外周 y = 0、すそ −8 m。原画視点の穴 0 px（141 コマ）。自由な縁はすその下端だけ", "verdict": "記録（三船の向こうから水平線まで。PC の描画）"},
            "94": {"value": "原画視点のカメラは PaintingCam v1 のまま動かさない（船の上下 DS30BoatHeave が動かすのは座席の 3 つのカメラと船だけ）。4 視点 × 6 時刻の静止画で原画視点の富士の位置は同じ",
                   "verdict": "記録（原画構図の観察位置と向きは一定）"},
        },
    }

    record_only = {
        "front_seam_ridge_boat_patch": {"value_ja": "主役波の行 約 150〜158・列 394 の前の継ぎ目に t* で 0.80 m の稜、その 0.6 m 外に −1.0 m の溝（船の支えの 1 m の混ぜ）。法線の内積 0.32〜0.59",
                                        "source": "進行役の独立の検査（ridge.py、リポジトリの外）", "verdict": "記録のみ（仕上げ30）"},
        "near_band_transient_kink": {"value_ja": "τ −3.03〜−2.48 s（t 5.3〜6.5 s）に、主役波の行 172〜193（列 394）の 1〜2 m 外で 0.4〜1.05 m の溝・稜（45° より急）。near の y の二階差分の最大 %.3f m／コマ²（コマ %d）" % (IE["acc_max_m_per_frame2"], IE["acc_argmax_frame"]),
                                     "part_a_claim_m": r(A["playback"]["max_step_change_near_m"], 4),
                                     "note_ja": "第A部の「コマの動きの変化の最大 0.013 m」は、全頂点の動きの大きさの最大の変化で、頂点ごとの二階差分ではない。頂点ごとでは 0.199 m／コマ²（44 コマで 0.05 を超える）", "verdict": "記録のみ（仕上げ30）"},
        "seam_normals": {"value_ja": "列 394 の側で頂点法線の内積の最小 0.32（numpy）・0.309（Unity）、t* で 0.586。錐の扇では決まらない", "verdict": "記録のみ（光を使わない平塗りなので陰影には出ない。仕上げ30）"},
        "far_radial_taper": {"value_m": [PAR["grid"]["far_taper_start_m"], PAR["grid"]["far_taper_end_m"]],
                             "note_ja": "far は半径 380 m から 600 m で式の海を y = 0 へ弱める（ds30_params.json の far_taper_start_m・far_taper_end_m）。sea_function.json の式には書いていない（独立の検査で約 400 m より外で最大 3.4 m 違う）。設計43 の前に sea_function.json へ書く",
                             "verdict": "記録のみ（設計43 の前に直す）"},
        "colour_stopgap": {"value_ja": "near・far の色は 2 色（藍濃と白）。白は t* の高さ 0.5 m の等高線、白くなる時刻は第A部の T_white。T_white が走る間、白と藍濃の境がぎざぎざ。座席から右の高い波が大きな平らなクリーム色の面に見える。海のシートに外殻線はない",
                           "verdict": "記録のみ（設計36・38）"},
        "right_wave_join": {"value_ja": "右の高い波は大波と一続きの面だが、波頭の稜では続かない（主役波の右の端は約 0 m の錐。右の高い波は c −8 の 0 m の肩から立ち上がり c +31.5 で 19.0 m）", "verdict": "記録のみ（Q16 の読みの確かめは段階5 の自己評審）"},
        "trough_legibility": {"value_ja": "谷は幾何にある（K*′ の谷 −5.7 m、主役波の右の端の先の続き 最大 2.2 m）が、光を使わない平塗りでは読めない", "verdict": "記録のみ（段階7）"},
        "static_props_float": {"value_ja": "M1_Revision_LeftSupport・boat_left・boat_fg は t* より前に浮く・沈む（前から）。座席の船は t* の姿勢のまま鉛直だけ動く（船首が最大 4.8 m 水面の上、船尾が最大 2.6 m 沈む）",
                               "verdict": "記録のみ（段階8）"},
        "start_speed": {"value_ja": "待機から波の速さ（1 コマ 0.692 m、約 21 m/s）へいきなり入る。Play モードの既定は autoStartDelay 0", "verdict": "記録のみ（設計47 の導入で走ったまま渡す）"},
        "side_left_sky_clip": {"value_ja": "左の側面の確認用の視点で、カメラが波の枠と動くと空のドームが遠くの面で切れる（29修正01 からある）", "verdict": "記録のみ（確認用の視点だけ）"},
        "gpu_memory": {"value_mib": S1["gpu_mib_sheets"], "hero_near_far_bytes": [s["positionGpuBytes"] + s["posLoGpuBytes"] + s["whiteGpuBytes"] for s in S1["sheets"]],
                       "driver_bytes_before_after": [RR1["driverBytesBefore"], RR1["driverBytesAfter"]], "verdict": "合格（≤ 512 MiB。Unity のバッファの大きさ）"},
        "unity_run_seconds": {"render_single": r(RR0["totalSeconds"], 1), "render_single_fix1": r(RR1["totalSeconds"], 1)},
        "hmd": "未検証（PC のオフスクリーン描画と Editor の batch の Play モードだけ。ステレオ・PS VR2 の実機は見ていない）",
    }

    revisions = {
        "part_a_internal_ja": "第A部の生成器の中の修正1（検査の値を決める前）：混ぜを smoothstep → smootherstep、外向きの傾き σ の頑健な求め方（1 コマの 3 m の跳びを消した）、船の支えの 1 m の混ぜ、上下を竜骨の平均から目の点の下の水面へ（竜骨の平均では 421 コマのうち 311 コマで目が水の下）、上下を 0.3 s の窓でならす（0.1 s では加速度 15 m/s²）、手前の小波の半径と裾の形、numpy の描画の 2 つの誤り（近い面の切りなし・平らな面の並べなし。偽の穴に見えた）",
        "fix1_after_independent_check_ja": "直し1（Q26 の 1 回）：(1) M1_ForegroundFoam_Static を海があるときの既定で隠し、小波への取り付けを既定で切った。(2) 主役波の外殻線を本体の縁から 10 列内側からだけ描く（outlineColInset）。面の描画は変えない",
        "fix1_inset_trials": inset_trials(),
        "fix1_painting_line_ids_changed": line_ids_changed(),
        "values_unchanged_by_fix1": {"tstar_regress_identical": X1["same_ds30_tstar_regress"]["identical_values"], "summary_identical": X1["same_ds30b_summary"]["identical_values"]},
        "summary_before_fix_differs_only_in_ja": "ds30b_summary.json は隠した物・取り付けた泡・Play モードのコマの数（%d → %d）だけが違う" % (S0["items"]["play_mode"]["frames"], S1["items"]["play_mode"]["frames"]),
    }

    discrepancies = [
        "第A部の「コマの動きの変化の最大 0.013 m」は全頂点の動きの大きさの変化。頂点ごとの二階差分は 0.199 m／コマ²（独立の検査、第B部の Unity の値も同じ向き）",
        "far の半径方向の弱め（380〜600 m）が sea_function.json の式にない（ds30_params.json にはある）",
        "boat_support.json の note_ja と DS30BoatHeave.cs の説明は「0.1 s でならす」のままだが、生成に使った値は ds30_params.json の smooth_s 0.3 s",
        "Unity/Build/Design/30/sea/README_interface.txt の (4) は泡の仮置きを残す前提のまま。直し1 で既定は隠す",
        "作業の指示の「甲板の 1.83 m 上」は目のワールドの高さ。目は甲板の 1.2 m 上",
        "作業の指示にある Q20_quotes.txt は会話の作業フォルダーになかった。Q20 は AGENTS.md の引用で読んだ",
    ]

    decision = {
        "adopted_ja": "主役波（F_final、精度の層）＋ near（44 × 1231）＋ far（19 × 247）の 3 枚を同じ knot_tau・同じ frame.origin・同じ τ(t) で再生する。主役波は本体の列 18〜394 だけを描き、外殻線は縁から 10 列内側から。平らな仮置きの海は上面 y −9 m へ下げ、near・far の T 字の継ぎ目の下に幕を置く。仮置きの右の斜面・手前の小波・泡は隠す。座席の船は heave（鉛直だけ）",
        "reading_ja": "t* の回帰は主役波＋海の ID 画像（t28_seaids）で 29修正01 と比べる（主役波だけの ID は余白を描かないので海の所を空と読む）。色区は 29修正01 で採った両側の読みを引き継ぐ",
        "dropped_ja": "(1) 泡の仮置きを新しい小波に合わせて置き直す：小波の泡と線は設計36・38 で作り直すので、今は隠す。(2) 継ぎ目の外殻線を縁の 1 列だけ切る：灰色の画素は変わらなかった（原因は縁の法線ではなく、座席から縁の近くの谷の壁を横から見ること）。(3) near・far の T 字を生成器で直す（far の行 0 に near の全列）：幕で 0 px になったので仕上げ30 へ",
    }

    handoffs = {
        "stage5_selfreview_ja": "Q16 の「右の波を大波とつなぐ」の読み（面では一続き、波頭の稜では続かない）の確かめ",
        "polish30_ja": "前の継ぎ目の船の支えの稜 0.80 m と溝 −1.0 m（法線の内積 ≥ 0.9、稜・溝 ≤ 0.1 m を目標）、near の帯の τ −3.03〜−2.48 s の溝と動きの折れ（≤ 0.05 m／コマ²、45° 以下）、右の高い波の輪の間隔（c 30〜60 m で約 3 m）、一次設計（参照モデルの配置）のパッケージ、near・far の T 字（far の行 0 に near の全列）、ds30_right_wave の形",
        "design36_38_ja": "海のシートの色（2 色の仮）と外殻線、継ぎ目をまたぐ外殻線（今は主役波の縁の 10 列と海には線がない）、手前の小波の泡と線、主役波の藍濃 (34,63,96) と海の藍濃 (35,64,97) の 1 段の差",
        "design43_ja": "sea_function.json に far の半径方向の弱めを書く。船は sea_function.json（帯と主役波の中はシート）を読む",
        "stage8_ja": "船の傾きを水面に合わせる、浮く・沈む静止物",
        "design47_ja": "導入から走ったまま単発再生へ渡す",
        "hmd_ja": "設計08〜10（PS VR2 の導入の後）。ステレオ・実時間の再生は未検証",
    }

    return {
        "schema": "GreatWave.DS30.metrics/1",
        "number": "設計30",
        "title_ja": "周囲の海と接続し、Unity で単発再生する（右の高い波・手前の小波・谷の続き・船の支えを含む）",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "evidence_kind_ja": "numpy の生成器と検査（第A部）、Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と Editor の batch の Play モード（第B部・直し1）、美術優先28修正01 の評価器（29修正01 の読み）、進行役の独立の検査（リポジトリの外の numpy）。HMD 実機の結果ではない",
        "acceptance": acceptance,
        "design": design,
        "backlog": backlog,
        "record_only": record_only,
        "revisions": revisions,
        "discrepancies_ja": discrepancies,
        "decision": decision,
        "handoffs": handoffs,
        "time": {"limit_h": 8, "ja": "Q26 の日程で進行役が 8 時間とした。ファイルの時刻で 9/29 16:01（最初のファイル）〜17:11（第A部の最後）、第B部 〜17:26、独立の検査 17:31〜、直し1 17:55〜18:10、記録は 18:13〜。上限の内。Unity の 1 回はどれも 30 分より十分短い（DS30Render の中の時間 43.3 s・42.9 s）"},
    }


# ---------------------------------------------------------------- run.json
def tool_version(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.splitlines()[0].strip()
    except Exception as e:  # 版が取れなくても記録は書く
        return "不明（%s）" % e


def run_json(copy_log):
    import numpy
    import PIL
    code = sorted(["Tools/GWWaveGen/ds30/" + f for f in os.listdir(P("Tools/GWWaveGen/ds30")) if f.endswith((".py", ".ps1", ".json"))])
    for root, _, files in os.walk(P("Unity/Assets/GreatWave/Design30")):
        for f in files:
            if f.endswith((".cs", ".unity")):
                code.append(os.path.relpath(os.path.join(root, f), REPO).replace("\\", "/"))
    code = sorted(code)
    hero = "Unity/Build/Design/28R01F/F_final/art_on/"
    inputs = [hero + f for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds27_sea.npz")] + [
        "Unity/Build/Design/28R01F/F_final/timewarp_F_final.json",
        "Unity/Build/Design/29R01/bake_kp/kstar/kstar_a45.gwb",
        "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin",
        "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvwarp_a45.json",
        "Tools/GWContext/seat_v1.json", "Tools/GWContext/context_layout.json",
        "Docs/Evidence/ArtFirst/26/reference/align_B_upright.json"]
    sea = B + "/sea/"
    outs = [sea + d + "/" + f for d in ("near", "far") for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds30_class_u8.bin", "ds30_tstar.gwb")]
    outs += [sea + "near/ds30_ring0_index.json", sea + "sea_function.json", sea + "boat_support.json", sea + "ds30_generate_log.json", sea + "README_interface.txt",
             B + "/checks/ds30_checks.json", B + "/checks/ds30_painting_regression_table.json", B + "/layout/ds30_layout_record.json",
             B + "/ref/ds30_ref_layout.json", B + "/ref/ds30_ref_cache_log.json"]
    for d in (F0, F1):
        outs += [d + "/ds30_render_report.json", d + "/ds30b_summary.json", d + "/ds30_tstar_regress.json", d + "/ds30_playback_frames.csv",
                 d + "/ds30_holes.csv", d + "/ds30_holes_noflat.csv", d + "/playmode/ds30_playmode.csv", d + "/t28_seaids/ds29r01_tstar_verdict.json",
                 d + "/t28_seaids/t28/render/af28r01_class_ids.png", d + "/t28_seaids/t28/render/af28r01_painting.png"]
        outs += [d + "/video/ds30_%s_30fps.mp4" % v for v in VIDEOS]
    outs += [F1 + "/ds30_fix1.json", F1 + "/fig_ds30_fix1.png",
             B + "/indep_check/seam_out.json", B + "/indep_check/eye_play_out.json", B + "/indep_check/pen_out.json",
             B + "/logs/unity_ds30_single.log", B + "/logs/unity_ds30_single_fix1.log", B + "/logs/unity_ds30_playmode.log", B + "/logs/unity_ds30_playmode_fix1.log"]
    evidence = sorted(f for f in os.listdir(P(EV)) if f != "run.json")
    ps = "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/ds30/run_ds30_unity.ps1"
    commands = [
        "（第A部、参照モデルの数値）py -3.10 -B Tools/GWWaveGen/ds30/ds30_refmeasure.py cache → measure → delete（SHA-256 を照合してから Git 対象外の Unity/Build/Design/30/_objcache に一時キャッシュ。終わりに削除し ref/ds30_ref_cache_log.json に SHA-256 を残す）",
        "（第A部、生成）py -3.10 -B Tools/GWWaveGen/ds30/ds30_generate.py（出力 Unity/Build/Design/30/sea。約 48 s）",
        "（第A部、検査）py -3.10 -B Tools/GWWaveGen/ds30/ds30_checks.py（出力 Unity/Build/Design/30/checks。約 123 s）",
        "（第A部、配置の記録）py -3.10 -B Tools/GWWaveGen/ds30/ds30_layout.py（出力 Unity/Build/Design/30/layout）",
        "（第B部）" + ps + " -Method GreatWave.Design30.EditorTools.DS30Render.Render -Log single -Extra \"-ds30Name single\"",
        "（第B部）" + ps + " -NoQuit -Method GreatWave.Design30.EditorTools.DS30PlayModeCheck.Run -Log playmode -Extra \"-ds30Out Build/Design/30/unity/single/playmode\"",
        "（第B部）py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/30/unity/single、ds30b_sheet.py --out …、ds30b_summary.py --out …",
        "（進行役の独立の検査：リポジトリの外の numpy。出力の写しは Unity/Build/Design/30/indep_check/）",
        "（直し1）" + ps + " -Method GreatWave.Design30.EditorTools.DS30Render.Render -Log single_fix1 -Extra \"-ds30Name single_fix1\"（既定：-ds30Hide に M1_ForegroundFoam_Static、-ds30AttachFoam 0、-ds30LineInset 10。診断の描画 -ds30Name fix1_diag_i{0,1,3,10,30,400}・fix1_diag_t28_i{8,10,12}）",
        "（直し1）" + ps + " -NoQuit -Method GreatWave.Design30.EditorTools.DS30PlayModeCheck.Run -Log playmode_fix1 -Extra \"-ds30Out Build/Design/30/unity/single_fix1/playmode\"",
        "（直し1）py -3.10 -B Tools/GWWaveGen/ds30/ds30b_tstar_regress.py --out Unity/Build/Design/30/unity/single_fix1、ds30b_summary.py、ds30b_sheet.py、ds30_fix1_measure.py",
        "（記録）py -3.10 -B Tools/GWWaveGen/ds30/ds30_record.py",
    ]
    return {
        "schema": "GreatWave.DS30.run/1",
        "number": "設計30",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "machine": platform.platform(),
        "python": platform.python_version(), "numpy": numpy.__version__, "pillow": PIL.__version__,
        "unity": "6000.4.3f1（Editor batchmode、PC オフスクリーン描画、RTX 3080、Direct3D11）",
        "ffmpeg": tool_version([FF_DIR + "/ffmpeg.exe", "-version"]),
        "commands": commands,
        "scripts": {c: sha(c) for c in code},
        "scripts_outside_repo_ja": "進行役の独立の検査のコードは会話の作業フォルダー（リポジトリの外）にあり、コミットしない（作り手のコードを読まずに書いた検査）",
        "reference_model_ja": "参照モデル wave_repair_zbrush2.obj（SHA-256 AB4124F9…3D40。他者の展示作品のスキャン、作者・所蔵は未確認）は ds30_refmeasure.py だけが読んだ。一時キャッシュの npz は作った時と消した時の SHA-256 が同じ（ds30_ref_cache_log.json）。数値だけを使い、形・画像はリポジトリと成果物に入れていない",
        "inputs": {c: sha(c) for c in inputs},
        "build_outputs": {c: sha(c) for c in outs if os.path.exists(P(c))},
        "evidence": {EV + "/" + f: sha(EV + "/" + f) for f in evidence},
        "evidence_sources": [{"name": n, "how": h} for n, h in copy_log],
        "protected_ja": "設計27〜29 のコミット済みのファイルは変えていない（DS30Render の報告で protectedUnchanged = true、changedFiles は空）。場面は Design30 の DS30_SinglePlayback.unity だけを保存した",
        "not_in_repo_ja": "海のパッケージ（near 約 157 MB・far）、描画の全出力、GPU の読み戻し、診断の描画は Git 対象外の Unity/Build/Design/30/ に置いた",
    }


def main():
    log = copy_evidence()
    m = metrics()
    with open(P(EV + "/metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
        f.write("\n")
    r_ = run_json(log)
    with open(P(EV + "/run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(r_, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("DS30_RECORD evidence=%d metrics_keys=%d" % (len(r_["evidence"]), len(m)))


if __name__ == "__main__":
    sys.exit(main())
