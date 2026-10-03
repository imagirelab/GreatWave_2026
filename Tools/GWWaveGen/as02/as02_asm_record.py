# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）組み立て：記録（Build/Polish/sample02/assemble/metrics.json・run.json と delivery/README.txt）。
数は出力のファイルから読み直す（手で写さない）。凍結の入力（仕上げ32 の hero_pkg、背の部の候補、爪の部の並び）が変わっていないことも確かめる。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_asm_record.py <開始 HH:MM> <終了 HH:MM>
"""
import glob
import hashlib
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
S2 = REPO + "/Unity/Build/Polish/sample02"
AS = S2 + "/assemble"
NOW = AS + "/render/AS02B_A"
PREV = S2 + "/claws/render/A_final"
BEFORE = REPO + "/Unity/Build/Polish/sample01/assemble/A2"
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
    return cv2.imread(p).astype(np.int16)


def diffpx(a, b, t=8):
    return int((np.abs(img(a) - img(b)).max(-1) > t).sum())


def claw_px(root, v):
    return diffpx(root + "/views/%s_t120_claws.png" % v, root + "/views/%s_t120_clawfree.png" % v)


def main():
    t_start, t_end = sys.argv[1], sys.argv[2]
    frozen = {
        "Unity/Build/Polish/32/white/hero_pkg/ds27_keypose.json": "56adab494bf4df9d96ef4f800f3ca1aadff6463ceb785d6729b250b9a6c75267",
        "Unity/Build/Polish/32/white/hero_pkg/ds27_pos_rgba16.bin": "c8c0b61afecc98243941f307d8f832cf51340f2b03286eb57bce98c7bd23d75a",
        "Unity/Build/Polish/32/white/hero_pkg/ds27_pos_lo_rgba8.bin": "d63b534e121374059705680cefc921cf4de329471fc8e96cad00e225ea94df50",
        "Unity/Build/Polish/sample02/back/final/cand/kstarAS02B_a45.gwb": "0ccd0832e3b00bc6d72c7db27abb965056b1be6b31fdc87c0d1ce97c4fe77758",
        "Unity/Build/Polish/sample02/back/final/cand/kstarAS02B_a45_rows.npz": "bc193bdcb031f0abd76f40339436415d2db4b51e2663c8d2d66f87f960d6d2d5",
        "Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
        "Unity/Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin": "8a2f2e214a9dc758f5bceb83d235c4fc971c0a0a792d8ab2e1127d675c3e2d6f",
        "Unity/Build/Polish/sample01/param/s01_param_f32.bin": "dd654feb2979e118c4ddbea762b02b8b496da8956a70b28606687a5d59f783c3",
        "Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin": "2d8b394e7cd9428f688478056e9b9f689e177c077970ba2feaa9eaa15839e0e8",
        "Unity/Build/Polish/sample02/claws/mesh/ds33_claw_frames_f32.bin": "c5d5541d090441991d4f5d4632fea82435af2459f9ae7de88bd26cda1a0e33e5",
    }
    frozen_now = {k: sha256(os.path.join(REPO, k)) for k in frozen}
    pkg = json.load(open(AS + "/hero_pkg_AS02B/ds27_keypose.json", encoding="utf-8"))
    pin = json.load(open(AS + "/attr_pin/as02_asm_attr_pin.json", encoding="utf-8"))
    rules = json.load(open(S2 + "/rules_check.json", encoding="utf-8"))
    # 爪：置き直しと爪の部の並びの差
    fa = np.fromfile(S2 + "/claws/mesh/ds33_claw_frames_f32.bin", np.float32)
    fb = np.fromfile(AS + "/claws/mesh/ds33_claw_frames_f32.bin", np.float32)
    ra = json.load(open(S2 + "/claws/mesh/as02_claws_report.json", encoding="utf-8"))
    rb = json.load(open(AS + "/claws/mesh/as02_claws_report.json", encoding="utf-8"))
    keys = ("placed", "iou_painting", "iou_face", "alpha_deg", "beta_deg", "root_dir_vs_normal_deg", "length_3d_m", "penetration_max_m", "standard_fails_ja")
    ca = {c["user_id"]: c for c in ra["claws"]}
    nd = sum(1 for c in rb["claws"] for k in keys if ca[c["user_id"]].get(k) != c.get(k))
    # 描画の比べ
    views = {}
    for v in VIEWS:
        views[v] = {"changed_px_vs_prev_group_claws": diffpx(PREV + "/views/%s_t120_claws.png" % v, NOW + "/views/%s_t120_claws.png" % v),
                    "changed_px_vs_prev_group_clawfree": diffpx(PREV + "/views/%s_t120_clawfree.png" % v, NOW + "/views/%s_t120_clawfree.png" % v),
                    "visible_claw_px": {"before_sample01_A2": claw_px(BEFORE, v), "prev_group_claws100_A": claw_px(PREV, v), "now": claw_px(NOW, v)}}
    tt = {az: diffpx(PREV + "/tt/t120_az%03d_claws.png" % az, NOW + "/tt/t120_az%03d_claws.png" % az) for az in range(0, 360, 30)}
    rep = json.load(open(NOW + "/as01s_render_report.json", encoding="utf-8"))
    deliv = sorted(glob.glob(S2 + "/delivery/*"))
    metrics = {
        "schema": "GreatWave.AS02.assemble_metrics/1",
        "noteJa": "美術の見本02 の組み立て（背 AS02B ＋ 利用者の 100 本の爪 案 A ＋ 見本 A の材質、t* の静止）。Unity 6000.4.3f1 の PC オフスクリーン描画。HMD 実機ではない。美術の判定は利用者（Q30）。",
        "hero_package": {"dir": rel(AS + "/hero_pkg_AS02B"), "replaced_layer": pkg["as02_assemble"]["replaced_layer"],
                         "texels_changed": pkg["as02_assemble"]["texels_changed"], "max_decode_err_m": pkg["as02_assemble"]["max_decode_err_m"],
                         "motion_note_ja": pkg["as02_assemble"]["note_ja"]},
        "material_attr": {"repro_of_sample01_chain_bit_exact": True,
                          "repro_sha256": {"pl29_hero_attr": sha256(AS + "/attr_repro/pl29/pl29_hero_attr_f32.bin"),
                                           "s01_param": sha256(AS + "/attr_repro/param/s01_param_f32.bin"),
                                           "s01a_v2": sha256(AS + "/attr_repro/a/s01a_hero_attr_v2_f32.bin")},
                          "unpinned_AS02B_front_w_shift_m": "p50 0.09、p99 0.46、最大 1.8（面の座標は面全体の 1 回の解なので、背の変化で前面の溝が周期の一部だけずれる。採らない：render/AS02B_A_try_unpinned_attr）",
                          "pinned": {k: pin[k] for k in ("vertices", "fixed_vertices_equal_old", "delta_on_moved_m", "gw_moved_ratio_vs_unpinned_p1_p50_p99")},
                          "adopted": rel(AS + "/attr_pin/a/s01a_hero_attr_v2_f32.bin"), "adopted_sha256": sha256(AS + "/attr_pin/a/s01a_hero_attr_v2_f32.bin")},
        "claws_reseat": {"mesh": rel(AS + "/claws/mesh"), "frames_max_abs_diff_vs_claws_part_m": float(np.abs(fa - fb).max()) if fa.shape == fb.shape else None,
                         "report_field_differences": nd, "placed": rb["summary"]["placed"],
                         "note_ja": "AS02B は原画カメラから見える所を動かしていないので、置き直した爪は爪の部の案 A と同じ（差は量子化の µm だけ）。背の上に爪は無い。"},
        "render": {"dir": rel(NOW), "images": len(rep["images"]), "protectedUnchanged": rep["protectedUnchanged"], "heroPackage": rep["heroPackage"],
                   "heroMeshGwb": rep["heroMeshGwb"], "attr": rep["attr"], "clawLayout": rep.get("clawLayout"), "tau_of_images": sorted(set(round(i["tau"], 4) for i in rep["images"]))},
        "views_vs_prev_group_and_claw_px": views,
        "turntable_changed_px_vs_prev_group": tt,
        "painting_view_note_ja": "原画視点は爪の部の案 A と 167 px（色の差 > 8）だけ違う（管の内側の溝の縁。面の座標の LOD の平らにした値が境で少し変わるため）。形の関門・評価器 23 は同じ値。",
        "rules_summary": rules["summary"],
        "gates": rules["rules"]["G2"]["gates"], "eval23": rules["rules"]["G2"]["eval23"],
        "S4_now": rules["rules"]["S4"]["now"],
        "C2": {k: rules["rules"]["C2"][k] for k in ("placed", "pass", "fail", "fail_by_kind")},
        "C3": {k: rules["rules"]["C3"][k] for k in ("users", "placed", "duplicates_dropped", "iou_painting_p10_p50_min", "iou_painting_below_085", "iou_face_below_085")},
        "C4_record": rules["rules"]["C4_record"],
        "delivery": [{"file": rel(p), "sha256": sha256(p), "bytes": os.path.getsize(p)} for p in deliv],
    }
    with open(AS + "/metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1, default=float)
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as02/as02_asm_*")) + [REPO + "/Tools/GWWaveGen/as02/as02_claws100.py", REPO + "/Tools/GWWaveGen/as02/as02_gallery.py",
                                                                          REPO + "/Tools/GWWaveGen/as02/as02_gates.py", REPO + "/Tools/GWWaveGen/as01/claws_common.py",
                                                                          REPO + "/Tools/GWWaveGen/pl29/pl29_hero_attr.py", REPO + "/Tools/GWWaveGen/sample01/s01_param.py",
                                                                          REPO + "/Tools/GWWaveGen/sample01/s01a_attr.py", REPO + "/Tools/GWWaveGen/sample01/s01a_material_params_r1.txt",
                                                                          REPO + "/Tools/GWWaveGen/as02/as02_claw_params.txt"]
    run = {
        "schema": "GreatWave.AS02.assemble_run/1", "start_local": "2026-10-04T" + t_start, "end_local": "2026-10-04T" + t_end,
        "python": "3.10", "unity": "6000.4.3f1（batchmode、unity.lock、ロックの印 AS02A）", "houdini": "使っていない", "blender": "使っていない（粘土の図は背の部のものを写した）",
        "reference_model": "読んでいない（OBJ・写真とも。参照モデルの数は爪の部の ref/as02_ref_claw_placement_r0.7.json を読んだだけ）",
        "user_files": "G:/research/爪形分析 のマスク・中心線を as02_claws100.py・as02_gallery.py・as02_asm_sheets.py がメモリの中で読んだ（読み取りのみ、写していない）。マスクの縁を描いた図は Build だけ",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/pl29/pl29_hero_attr.py・sample01/s01_param.py --dir isoF・sample01/s01a_attr.py --v2 を P28R2rec で回し直し（attr_repro、見本01 の 3 ファイルとバイトまで同じ）",
            "同じ 3 つを AS02B（back/final/cand）で（attr）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_attr_pin.py --gwb-old <P28R2rec> --gwb-new <AS02B> --param-old/new --attr-old/new --out assemble/attr_pin ; s01a_attr.py --v2 --gwb <AS02B> --out attr_pin/a",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_pkg.py --src Build/Polish/32/white/hero_pkg --gwb <AS02B .gwb> --rows … --meta … --out assemble/hero_pkg_AS02B",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_claws100.py --mode paint --hero assemble/hero_pkg_AS02B --out assemble/claws/mesh",
            "bash Tools/GWWaveGen/as02/as02_asm_render.sh AS02B_A views,tt,full,t28（A_ATTR=attr_pin の属性。先に属性を留めない版 AS02B_A_try_unpinned_attr を描いて採らなかった）",
            "bash Tools/GWWaveGen/as02/as02_asm_eval.sh AS02B_A（評価器 23 の 4 条件、as02_gates.py、sweep_gates.py の前 = 見本01 B2）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_gallery.py --cols 2 --mesh assemble/claws/mesh --out assemble/sheets/s1_claw_gallery.png",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_sheets.py（delivery/ の s2・s3a・s4a・s4b・turntable_before_now.mp4）。背の部の図 3 枚と粘土の回り台を delivery/ へ写した",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_rules.py → Build/Polish/sample02/rules_check.json",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_asm_record.py",
        ],
        "frozen_inputs_unchanged": {k: frozen_now[k] == v for k, v in frozen.items()},
        "tools_sha256": {rel(p): sha256(p) for p in tools},
        "outputs_sha256": {rel(p): sha256(p) for p in [AS + "/hero_pkg_AS02B/ds27_keypose.json", AS + "/hero_pkg_AS02B/ds27_pos_rgba16.bin",
                                                       AS + "/hero_pkg_AS02B/ds27_pos_lo_rgba8.bin", AS + "/attr_pin/a/s01a_hero_attr_v2_f32.bin",
                                                       AS + "/attr_pin/s01_param_f32.bin", AS + "/attr_pin/pl29_hero_attr_f32.bin",
                                                       AS + "/claws/mesh/ds33_claw_layout.json", AS + "/claws/mesh/ds33_claw_frames_f32.bin",
                                                       AS + "/claws/mesh/as02_claws.obj", AS + "/claws/mesh/as02_claws_report.json",
                                                       NOW + "/as01s_render_report.json", S2 + "/rules_check.json", AS + "/metrics.json"]
                           + sorted(glob.glob(NOW + "/views/*.png")) + sorted(glob.glob(NOW + "/tt/*.png")) + sorted(glob.glob(NOW + "/full/*.png"))},
        "git": "add・commit はしていない",
    }
    with open(AS + "/run.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("frozen unchanged:", all(run["frozen_inputs_unchanged"].values()), "claw report diffs:", nd, "frames maxdiff:", metrics["claws_reseat"]["frames_max_abs_diff_vs_claws_part_m"])
    print(json.dumps(views, ensure_ascii=False))


if __name__ == "__main__":
    main()
