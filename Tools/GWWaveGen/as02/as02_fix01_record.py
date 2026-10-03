# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）修正の回 1：記録（Build/Polish/sample02/fix01/metrics.json・run.json と fix01/delivery/README.txt）。
数は出力のファイルから読み直す（手で写さない）。凍結の入力（仕上げ32 の hero_pkg、P28R2rec、見本01 の属性、見本02 の組み立ての出力）が
変わっていないことを、見本02 の記録の SHA-256 と照らして確かめる。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_record.py <開始 HH:MM> <終了 HH:MM>
"""
import glob
import hashlib
import json
import os
import platform
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
S2 = REPO + "/Unity/Build/Polish/sample02"
FX = S2 + "/fix01"
AS = FX + "/assemble"
NOW = AS + "/render/AS02C_A"
PREV = S2 + "/assemble/render/AS02B_A"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def img(p):
    return cv2.imread(p)


def diff_px(a, b):
    A, B = img(a), img(b)
    return int((np.abs(A.astype(np.int16) - B.astype(np.int16)).max(-1) > 8).sum())


def claw_px(root, v):
    return diff_px(root + "/views/%s_t120_claws.png" % v, root + "/views/%s_t120_clawfree.png" % v)


def main():
    t0, t1 = sys.argv[1], sys.argv[2]
    rules = json.load(open(S2 + "/rules_check.json", encoding="utf-8"))
    old_rules = json.load(open(S2 + "/rules_check_AS02B_A.json", encoding="utf-8"))
    rep = json.load(open(AS + "/claws/mesh/as02_claws_report.json", encoding="utf-8"))
    rep_old = json.load(open(S2 + "/assemble/claws/mesh/as02_claws_report.json", encoding="utf-8"))
    meas = json.load(open(FX + "/back/final/measure.json", encoding="utf-8"))
    chk = json.load(open(FX + "/back/final/check_painting_unchanged.json", encoding="utf-8"))
    rub = json.load(open(FX + "/back/final/rubric_diff_AS02B_AS02C.json", encoding="utf-8"))
    pin = json.load(open(AS + "/attr_pin/as02_asm_attr_pin.json", encoding="utf-8"))
    pl = [c for c in rep["claws"] if c.get("placed")]
    pl_old = {c["user_id"]: c for c in rep_old["claws"] if c.get("placed")}
    views = {v: {"pixels_changed_vs_prev_claws": diff_px(PREV + "/views/%s_t120_claws.png" % v, NOW + "/views/%s_t120_claws.png" % v),
                 "pixels_changed_vs_prev_clawfree": diff_px(PREV + "/views/%s_t120_clawfree.png" % v, NOW + "/views/%s_t120_clawfree.png" % v),
                 "claw_pixels_prev": claw_px(PREV, v), "claw_pixels_now": claw_px(NOW, v)} for v in VIEWS}
    sel = {}
    for c in pl:
        f = c["shape2d"].get("fix01", {})
        k = (f.get("gauss_k"), f.get("spline_k"), f.get("bandpass"))
        sel[str(k)] = sel.get(str(k), 0) + 1
    metrics = {
        "schema": "GreatWave.AS02.fix01_metrics/1",
        "round_ja": "美術の見本02 修正の回 1：落ちた測る規則（S4・C2・C3）だけを直した",
        "rules_verdicts": {"before": old_rules["summary"]["verdicts"], "now": rules["summary"]["verdicts"]},
        "S4": {"peaks_c_by_level": {k: meas["summary"][k]["bulge_peak_c_by_level"] for k in ("P28R2rec", "AS02B", "AS02C")},
               "bulge_over_chord_dip_m": {k: meas["summary"][k]["back_bulge_dip_max_m"] for k in ("P28R2rec", "AS02B", "AS02C")},
               "back_contour_dip_m": {k: meas["summary"][k]["back_dip_max_m"] for k in ("P28R2rec", "AS02B", "AS02C")},
               "silhouette_dip_px": {k: meas["summary"][k]["silhouette_dip_px_hero"] for k in ("P28R2rec", "AS02B", "AS02C")},
               "far_volume_c_gt_0_m3": {k: meas["summary"][k]["F04_like"]["far_volume_c_gt_0_m3"] for k in ("P28R2rec", "AS02B", "AS02C")},
               "painting_view_unchanged": chk["painting_view_unchanged"], "moved_vertices_gt_1mm": chk["moved_vertices_gt_1mm"], "max_move_m": chk["max_move_m"],
               "rubric_summary_AS02B_to_AS02C": [rub["summary_base"], rub["summary_cand"]],
               "rubric_diff_path": rel(FX + "/back/final/rubric_diff_AS02B_AS02C.json")},
        "C2": {"fail_before": len([c for c in pl_old.values() if [x for x in c.get("standard_fails_ja", []) if not x.startswith("面から見た")]]),
               "fail_now": rules["rules"]["C2"]["fail"], "outline_lumps_max_now": max(c["standard"]["outline_lumps_hysteresis"] for c in pl),
               "spine_jump_p95_max_now": max(c["standard"]["spine_curv_jump_p95"] for c in pl),
               "width_over_thickness_mid_range_now": [min(c["standard"]["width_over_thickness_mid"] for c in pl), max(c["standard"]["width_over_thickness_mid"] for c in pl)],
               "selected_smoothing_counts": sel},
        "C3": {"fail_before": sorted(set(old_rules["rules"]["C3"]["iou_painting_below_085"]) | set(old_rules["rules"]["C3"]["iou_face_below_085"])),
               "fail_now": sorted(set(rules["rules"]["C3"]["iou_painting_below_085"]) | set(rules["rules"]["C3"]["iou_face_below_085"])),
               "fail_now_at_old_resolution_s8_600px": sorted(c["user_id"] for c in pl if c["iou_painting_s8"] < 0.85 or c["iou_face_600px"] < 0.85),
               "iou_painting_p10_p50_min_now": rules["rules"]["C3"]["iou_painting_p10_p50_min"],
               "iou_painting_p10_p50_min_before": old_rules["rules"]["C3"]["iou_painting_p10_p50_min"],
               "n_ortho_counts": {str(v): sum(1 for c in pl if c.get("fix01_n_ortho") == v) for v in (0.5, 0.3, 0.15, 0.0)}},
        "C4_record": rules["rules"]["C4_record"],
        "G2_gates_now_vs_prev": {k: [v["now_claws"], v["prev_group_sample02_AS02B_A_claws"], v["CP1"], v["26修正01"]] for k, v in rules["rules"]["G2"]["gates"].items()},
        "claws_layout": {"vertices": rep["layout"]["vertices"], "triangles": rep["layout"]["triangles"], "vertices_before": rep_old["layout"]["vertices"],
                         "collisions": rep["summary"]["collisions"], "penetration_max_m": rep["summary"]["penetration_max_m"]["max"]},
        "attr_pin": {"fixed": pin["vertices"]["fixed"], "moved": pin["vertices"]["moved"], "fixed_u_w_maxabs": pin["fixed_vertices_equal_old"]["u_w_maxabs"]},
        "views": views,
    }
    os.makedirs(FX, exist_ok=True)
    json.dump(metrics, open(FX + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    # 凍結の入力（見本02 の組み立ての記録の SHA-256 と照らす）
    frozen = {
        "Unity/Build/Polish/sample02/back/final/cand/kstarAS02B_a45.gwb": "0ccd0832e3b00bc6d72c7db27abb965056b1be6b31fdc87c0d1ce97c4fe77758",
        "Unity/Build/Polish/sample02/back/final/cand/kstarAS02B_a45_rows.npz": "bc193bdcb031f0abd76f40339436415d2db4b51e2663c8d2d66f87f960d6d2d5",
        "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
        "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_rows.npz": "c55e048d388e41e30289d075089066c481bf2f3b99d84727c655eea9e1a437a3",
        "Unity/Build/Polish/sample02/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin": "7919be2b828bf0f80b48600e4334eb8c47c6fff8abcfad4960da837b4989ef03",
        "Unity/Build/Polish/sample02/assemble/claws/mesh/ds33_claw_layout.json": "47bb5080ad99001f6322ab9ee9ef83416ca7f9c7fa489e890545e8421f111b1d",
        "Unity/Build/Polish/sample02/assemble/hero_pkg_AS02B/ds27_keypose.json": "f31260f6cc631ab8ed33c195d35175d6d5dab4242f13f30e85f4b4fac842700a",
        "Unity/Build/Polish/sample02/back/final/measure.json": "f29d53a9d78352fb088a639f2a0a5f4f93c64cdeb3c2ec3076ebb4b02729e053",
        "Unity/Build/Polish/sample02/assemble/render/measure/gates_AS02B_A/sweep_gates.json": "66c47edaa78ef55e802de36bd384b12378a3d952f9410863993eda64804196bc",
        "Unity/Build/Polish/sample02/claws/user_claw_standard.json": "9f0b269dc8f364c51ae8dfc7e11d9b32a2c163984f1d3e0ba897d24cd6bc48a0",
    }
    old_rr = json.load(open(S2 + "/assemble/run.json", encoding="utf-8"))
    frozen["Unity/Build/Polish/32/white/hero_pkg/ds27_keypose.json"] = "56adab494bf4df9d96ef4f800f3ca1aadff6463ceb785d6729b250b9a6c75267"  # as02_asm_pkg の src_keypose_sha256
    for p in ("Unity/Build/Polish/32/white/hero_pkg/ds27_pos_rgba16.bin", "Unity/Build/Polish/32/white/hero_pkg/ds27_pos_lo_rgba8.bin"):
        frozen.setdefault(p, None)
    for p in ("Unity/Build/Polish/sample02/assemble/hero_pkg_AS02B/ds27_pos_rgba16.bin", "Unity/Build/Polish/sample02/assemble/hero_pkg_AS02B/ds27_pos_lo_rgba8.bin"):
        frozen[p] = old_rr["outputs_sha256"][p]
    frozen_res = {}
    for p, h in frozen.items():
        cur = sha256(REPO + "/" + p)
        if h is None:
            h = old_rr.get("inputs_sha256", {}).get(p) or old_rr.get("outputs_sha256", {}).get(p)
        frozen_res[p] = {"sha256": cur, "unchanged": (cur == h) if h else "記録なし（今の値を残す）"}
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as02/as02_fix01_*.py")) + [
        REPO + "/Tools/GWWaveGen/as02/as02_claws100.py", REPO + "/Tools/GWWaveGen/as02/back_build.py", REPO + "/Tools/GWWaveGen/as02/as02_asm_pkg.py",
        REPO + "/Tools/GWWaveGen/as02/as02_asm_render.sh", REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as02/as02_asm_unity.ps1",
        REPO + "/Tools/GWWaveGen/as02/as02_asm_rules.py", REPO + "/Tools/GWWaveGen/as02/as02_asm_sheets.py", REPO + "/Tools/GWWaveGen/as02/as02_asm_attr_pin.py",
        REPO + "/Tools/GWWaveGen/as02/as02_gallery.py", REPO + "/Tools/GWWaveGen/as02/back_measure.py", REPO + "/Tools/GWWaveGen/as02/back_check.py",
        REPO + "/Tools/GWWaveGen/as02/back_sheet.py", REPO + "/Tools/GWWaveGen/as02/back_tt_sheet.py", REPO + "/Tools/GWWaveGen/as02/back_common.py",
        REPO + "/Tools/GWWaveGen/kstar_p28/rays_bl.py", REPO + "/Tools/GWWaveGen/rubric/rubric_check.py"]
    outs = sorted(glob.glob(FX + "/delivery/*")) + [S2 + "/rules_check.json", S2 + "/rules_check_AS02B_A.json", FX + "/metrics.json",
                                                     FX + "/back/final/cand/kstarAS02C_a45.gwb", FX + "/back/final/cand/kstarAS02C_a45_rows.npz",
                                                     FX + "/back/final/cand/back_design.json", FX + "/back/final/measure.json",
                                                     FX + "/back/final/check_painting_unchanged.json", FX + "/back/final/rubric_AS02C.json",
                                                     AS + "/hero_pkg_AS02C/ds27_keypose.json", AS + "/attr_pin/a/s01a_hero_attr_v2_f32.bin",
                                                     AS + "/claws/mesh/ds33_claw_layout.json", AS + "/claws/mesh/ds33_claw_frames_f32.bin",
                                                     AS + "/claws/mesh/as02_claws_report.json", NOW + "/as01s_render_report.json",
                                                     AS + "/render/measure/gates_AS02C_A/sweep_gates.json", FX + "/claws/conflict_search.json"]
    run = {
        "schema": "GreatWave.AS02.fix01_run/1", "start_local": "2026-10-04T" + t0, "end_local": "2026-10-04T" + t1,
        "python": platform.python_version(), "numpy": np.__version__, "unity": "6000.4.3f1（batchmode、AS01SampleRender、新しい C# は無い）",
        "blender": "Blender 5.2.2 LTS（Steam、Workbench の粘土）", "houdini": "使っていない",
        "reference_model": "読んでいない（rubric_check を --ref なしで回した。一時キャッシュも作っていない）",
        "user_files": "G:/research/爪形分析 のマスク・中心線を読み取りのみで使った（D14・D23。画像・マスクはリポジトリへ写していない。s1・s2 の図は Build だけ）",
        "commands": [
            "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/as02/back_build.py fix01/back/final/cand/kstarAS02C_a45 fix01/back/final/cand/back_design.json（2 度回して .gwb がバイトまで同じ。候補 t1〜t11・u1〜u7 は fix01/back/ の下）",
            "py -3.10 -B Tools/GWWaveGen/as02/back_check.py · rubric/rubric_check.py --gate · back_rubric_diff.py（AS02B → AS02C）· back_measure.py（P28R2rec・AS02B・AS02C）",
            "blender --background --factory-startup --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views / turntable（AS02C）; ffmpeg で AS02B｜AS02C の粘土の回り台",
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py · sample01/s01_param.py --dir isoF · as02/as02_asm_attr_pin.py · sample01/s01a_attr.py --v2（AS02C）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Build/Polish/32/white/hero_pkg --gwb <AS02C> --out fix01/assemble/hero_pkg_AS02C",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_claws100.py --mode paint --fix01 --hero fix01/assemble/hero_pkg_AS02C --out fix01/assemble/claws/mesh（試しの回 mesh_r1・mesh_r2 も残した）",
            "RB=… LG=… CL=… HERO_PKG=… HERO_GWB=… A_ATTR=… bash Tools/GWWaveGen/as02/as02_asm_render.sh AS02C_A views,tt,full,t28",
            "RB=… LG=… bash Tools/GWWaveGen/as02/as02_asm_eval.sh AS02C_A",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_conflict_search.py claw024,claw045 fix01/claws/conflict_search.json",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_rules.py → Build/Polish/sample02/rules_check.json（前の版は rules_check_AS02B_A.json）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_gallery.py --cols 2 --mesh fix01/assemble/claws/mesh · as02_fix01_sheets.py · as02_fix01_back_chart.py · back_sheet.py · back_tt_sheet.py",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_fix01_record.py"],
        "frozen_inputs": frozen_res,
        "tools_sha256": {rel(p): sha256(p) for p in tools if os.path.isfile(p)},
        "tools_before_fix01_copies": {rel(p): sha256(p) for p in sorted(glob.glob(FX + "/tool_before/*"))},
        "outputs_sha256": {rel(p): sha256(p) for p in outs if os.path.isfile(p)},
        "old_mode_reproduced": {
            "claws_without_fix01": {"repro": sha256(FX + "/repro_old_mode/ds33_claw_frames_f32.bin"), "sample02": sha256(S2 + "/assemble/claws/mesh/ds33_claw_frames_f32.bin")},
            "back_build_AS02B_design": {"repro": sha256(FX + "/repro_old_mode/back/kstarAS02B_a45.gwb"), "sample02": sha256(S2 + "/back/final/cand/kstarAS02B_a45.gwb")},
            "note_ja": "直した道具（as02_claws100.py・back_build.py）を前の引数で回すと、見本02 の出力とバイトまで同じ（新しい処理は --fix01 と設計の新しい鍵の時だけ）"},
        "incidents_ja": [
            "Blender の粘土の描画を相対の出力の場所で回したら、静止画 17 枚が C:\\Unity\\Build\\Polish\\sample02\\fix01\\back\\final\\renders に書かれた。"
            "同じ名前で G: の fix01/back/final/renders へ移した（消していない）。C:\\Unity\\Build\\Polish の下に空のフォルダーが残っている（C:\\Unity\\Build は前からあった）。以後は絶対の場所で回した。",
            "rubric_check.py --gate が入力の rows の隣に重ね図の PNG を書くので、fix01/back/final へ移した（候補の場所だけ。凍結のフォルダーには書いていない）。"],
        "git": "add・commit はしていない",
    }
    json.dump(run, open(FX + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    # README
    v = rules["summary"]["verdicts"]
    c3 = rules["rules"]["C3"]
    lines = [
        "美術の見本02（Q30-2）修正の回 1 の渡す図（2026-10-04、Git 対象外。利用者はまだ見ていない）",
        "落ちていた測る規則（S4・C2・C3）だけを直し、Unity 6000.4.3f1 の PC オフスクリーン描画で描き直して測り直した。HMD 実機ではない。飛沫なし。t* の静止。",
        "前 = 見本02 の組み立て（背 AS02B ＋ 爪の部の案 A、Build/Polish/sample02/assemble/render/AS02B_A）、今 = Build/Polish/sample02/fix01/assemble/render/AS02C_A。",
        "",
        "s1_claw_gallery_p1〜p7.png   直した爪の一覧（爪ごと：利用者のマスク｜作り直した 3D の爪を面から｜3/4｜置いた爪 3/4｜利用者の模型 claw_mid）。2300×1684",
        "s2_painting.png              原画視点：原画（＋マスクの縁、緑）｜前｜今。下の段は頂と唇の拡大",
        "s3a_back_material.png        背：後ろ 65°・回り台 180〜270°（見本 A の材質）前｜今",
        "s3b_back_clay_back65_behind.png   背の粘土（Blender）：後ろ 65°・拡大・真後ろ。P28R2rec｜AS02B｜AS02C",
        "s3c_back_clay_minus_c_top.png     背の粘土：−c 側の後ろ・真上・背の 3/4。P28R2rec｜AS02B｜AS02C",
        "s3d_back_unimodal_chart.png       背が一つの山か（S4）：低い高さのふくらみの最大の位置と、S4 のほかの数",
        "s3e_clay_turntable_before_now.mp4 粘土の回り台 AS02B｜AS02C",
        "s3f_clay_turntable_12.png         粘土の回り台 12 方位 AS02B（上）｜AS02C（下）",
        "s4a_views.png                座席・座席から波・左右の側面・真上・座席から見た頂 前｜今",
        "s4b_turntable.png            回り台 12 方位 前｜今",
        "turntable_before_now.mp4     同じ 12 方位の動画（各 0.8 s）",
        "",
        "測る規則（Build/Polish/sample02/rules_check.json）：G1 %s、G2 %s、S4 %s、C2 %s、C3 %s。" % tuple(
            {"pass": "合", "fail": "不合"}[v[k]] for k in ("G1", "G2", "S4", "C2", "C3")),
        "C3 で 0.85 に届かない爪：%s（%s）。" % ("・".join(sorted(set(c3["iou_painting_below_085"]) | set(c3["iou_face_below_085"]))) or "なし",
                                        "利用者のマスクの縁が S 字に曲がる手描きで、C2 の滑らかさまでならすと重なりが 0.83〜0.84 に下がる。C2 を先にした"),
        "C3 の原画視点の IoU は表示の画素の 32 倍で測った（今までは 8 倍）。今までの細かさでは 0.85 に届かない爪は %d 本（%s）。" % (
            len(metrics["C3"]["fail_now_at_old_resolution_s8_600px"]), "・".join(metrics["C3"]["fail_now_at_old_resolution_s8_600px"])),
        "要求書の「通らない見本は出さない」に当たるか（C3 が不合）は進行役が決める。",
        "",
        "s1 と s2 は利用者のマスク（爪形分析）を含むので、リポジトリへ入れない（D14・D23）。",
    ]
    open(FX + "/delivery/README.txt", "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(json.dumps({"rules": rules["summary"]["verdicts"], "C3_fail": metrics["C3"]["fail_now"], "C3_fail_s8": metrics["C3"]["fail_now_at_old_resolution_s8_600px"],
                      "frozen_all_unchanged": all(x["unchanged"] is True for x in frozen_res.values() if x["unchanged"] != "記録なし（今の値を残す）")}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
