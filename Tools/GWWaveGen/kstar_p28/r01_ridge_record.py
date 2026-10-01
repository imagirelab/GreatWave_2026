# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE：metrics.json（項目 → 値 → 判定）と run.json（命令・道具の版・入出力とコードの SHA-256）を書く（py -3.10）。
入力は <ridge dir> の eval（kh_eval）、final（r2_metrics の評審の測り・r01_ridge_metrics・rec_band・rec_score）、houdini の確かめ、図と動画。
usage: py -3.10 r01_ridge_record.py <ridge dir> <start iso> <end iso> <eye_verdict_json>
"""
import os
import sys
import json
import glob
import platform
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_ridge_common as RR  # noqa: E402


def J(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    d, t_start, t_end, eye_p = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    eye = J(eye_p)
    ev = {c["label"]: c for c in J(os.path.join(d, "eval", "kh_eval_summary.json"))["candidates"]}
    dome = J(os.path.join(d, "final", "metrics_dome.json"))
    rid = J(os.path.join(d, "final", "metrics_ridge.json"))
    band = J(os.path.join(d, "final", "band.json"))
    score = {x["label"]: x for x in J(os.path.join(d, "final", "score.json"))["items"]}
    hou = J(os.path.join(d, "houdini", "r01_ridge_hiplc_verify.json"))
    rep = J(os.path.join(d, "cand", "kstarP28R01RG_a45_build_report.json"))

    def chk(lab, fid, name_part):
        for x in ev[lab]["rubric"]["checks"].get(fid, []):
            if name_part in x["name"]:
                return {"value": x["value"], "must": x["must"], "pass_must": x["pass_must"]}
        return None

    def must_fails(lab):
        return sorted("%s %s" % (k, x["name"]) for k, v in ev[lab]["rubric"]["checks"].items() for x in v if not x["pass_must"])
    rg, base = "RG", "P28R2rec"
    added = sorted(set(must_fails(rg)) - set(must_fails(base))); removed = sorted(set(must_fails(base)) - set(must_fails(rg)))
    g = {lab: ev[lab]["gate"] for lab in ev}; glf = {lab: ev[lab]["gate_lf"] for lab in ev}
    M = {
        "schema": "GreatWave.Polish28r01.ridge.metrics/1",
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "variant": "RIDGE（仕上げ28修正01、RAYS の A5 を P28R2rec の上で作り直す）",
        "candidate": "K*′ P28R01RG（Unity/Build/Polish/28r01/ridge/cand/kstarP28R01RG_a45.*）",
        "compared_with": {"previous_group": "K*′ P28R2rec（仕上げ28 の採用、土台）", "cp1": "Kstar_26R01（CP1／26修正01 の K*）",
                          "a5": "RAYS A5（仕上げ28 第1回の crest_ramp）", "stage9": "K*′ R4"},
        "eye_verdict_dome": eye,
        "closing_criteria_plan_5_3": [
            {"item": "後ろ 65° と回り台でドームが見えない（Q21）", "status": eye["status"], "evidence": eye["evidence"],
             "value": {"note_ja": eye["summary_ja"],
                       "groove_depth_max_m_[y,depth,c]": {k: rid[k]["groove_max"] for k in ("RG", "P28R2rec", "A5", "R4")},
                       "crest_low_behind_painted_top_m": {k: rid[k]["H_dip_behind_painted_top_m"] for k in ("RG", "P28R2rec", "A5")},
                       "H_max_m_and_c": {k: [rid[k]["H_max"], rid[k]["c_H_max"]] for k in ("RG", "P28R2rec", "A5")},
                       "R6_p99_record_only_(does_not_track_the_visible_dome)": {k: dome[k]["R6_p99"] for k in ("RG", "P28R2rec", "A5", "R4")},
                       "back_elliptic_frac": {k: dome[k]["back_elliptic_frac"] for k in ("RG", "P28R2rec", "A5", "R4")},
                       "back_plan_bow_0.5H0_0.7H0_m": {k: [dome[k]["back_plan_bow_0.5H0_L8_max_m"], dome[k]["back_plan_bow_0.7H0_L8_max_m"]] for k in ("RG", "P28R2rec", "A5", "R4")}}},
            {"item": "b区域が 3 つの房に読める（Q21）", "status": "不合格（P28R2rec と同じ 1 つ）",
             "value": {"RG_lobes_prom6": band["RG"]["lobes_prom6"], "P28R2rec_lobes_prom6": band["P28R2rec"]["lobes_prom6"],
                       "top_vs_top_raw_median_p90_max_px": [band["RG"]["top_vs_top_raw"][k] for k in ("median_px", "p90_px", "max_px")]}},
            {"item": "F04 ≤ 18.5 m で本体が薄く見えない（Q16・Q21）", "status": "F04 は不合格、薄く見えないは合格",
             "value": {"F04_0.5H0_m": {k: chk(k, "F04", "0.5H0")["value"] for k in ("RG", "P28R2rec", "A5", "Kstar_26R01")},
                       "F04_0.9H0_m": {k: chk(k, "F04", "0.9H0")["value"] for k in ("RG", "P28R2rec")},
                       "fullness_ratio_area_over_H2_and_shell": {k: [ev[k]["Q21_2"].get("ratio_area_over_H2"), ev[k]["Q21_2"].get("ratio_shell_over_H")] for k in ("RG", "P28R2rec")}}},
            {"item": "78・130・131 が定義どおりの読みで ≤ 4 px", "status": "合格（P28R2rec と同じ値）",
             "value": {k: [g[k]["78"]["max_px"], g[k]["130"]["max_px"], g[k]["131"]["max_px"]] for k in ("RG", "P28R2rec", "Kstar_26R01", "R4")}},
            {"item": "132・72 の爪なしの大きな輪郭 ≤ 4 px（σ12、σ24 の緩めなし）", "status": "合格（P28R2rec と同じ値）",
             "value": {k: [glf[k]["132"]["max_px"], glf[k]["72"]["p95_px"]] for k in ("RG", "P28R2rec", "Kstar_26R01", "R4")}},
            {"item": "134・267 が合格", "status": "未測（Unity の描画をしていない）。原画視点の numpy の読みは P28R2rec と画素まで同じ（見える面の奥行きの差 > 1 cm は 0 画素、ss=2）ので、P28R2rec の 134 7.264 px・267 の帯 6 と同じ見込み（不合格）",
             "value": {"painting_view_depth_diff_px_gt_1cm_ss2": eye.get("painting_depth_diff_px_ss2")}},
            {"item": "t* の頂と手前の尾の行が弧（Q17）", "status": "合格",
             "value": {"arcs_pm2m_near_tail_and_main": {k: dome[k]["arcs_pm2m"] for k in ("RG", "P28R2rec", "A5")},
                       "ridge_rows_top_chord_pm2m_min_deg_c-2..9": {k: rid[k]["top_chord_pm2m_min_deg_c-2_9"] for k in ("RG", "P28R2rec", "A5")}}},
        ],
        "ridge_task_items": {
            "vertical_groove_at_c_about_-0.5": {"RG": rid["RG"]["groove_max"], "A5": rid["A5"]["groove_max"], "P28R2rec": rid["P28R2rec"]["groove_max"],
                                               "verdict": "溝は消えた（背の溝の深さ 0.13 m、A5 0.47 m、P28R2rec 1.73 m。真後ろの拡大で縦の溝の線が見えない）"},
            "spine_3d_curvature": {k: rid[k]["spine3d"] for k in ("RG", "A5", "P28R2rec")},
            "F04_highest_point_c_and_ratio": {k: [chk(k, "F04", "最高点の c")["value"], chk(k, "F04", "最高点 / H0")["value"]] for k in ("RG", "A5", "P28R2rec", "Kstar_26R01")},
            "F10_step_and_peaks_and_cliff": {k: [chk(k, "F10", "高さの段")["value"], chk(k, "F10", "山")["value"], chk(k, "F10", "落ち")["value"]] for k in ("RG", "A5", "P28R2rec")},
            "F02_Rmin_c-5..3": {k: chk(k, "F02", "Rmin_m（c -5~+3")["value"] for k in ("RG", "A5", "P28R2rec")},
            "boat_left_157_and_new_lines_numpy": {k: {kk: score[k][kk] for kk in ("new_line_px", "protected_closer_px_1m", "boat_left_closer_px_0p05m", "protected_newcover_px")} for k in ("RG", "P28R2rec")},
            "sky_holes_in_wave_px_and_spill_px": {k: [ev[k]["sky"]["vs_painting_holes_in_wave"]["px"], ev[k]["sky"].get("vs_painting_spill_into_sky", {}).get("px")] for k in ("RG", "P28R2rec")},
        },
        "rubric_must_fail": {k: ev[k]["rubric"]["summary"]["must_fail"] for k in ev},
        "rubric_must_fail_added_vs_P28R2rec": added, "rubric_must_fail_removed_vs_P28R2rec": removed,
        "record_only": {
            "R6_R4_p99": {k: [dome[k]["R6_p99"], dome[k]["R4_p99"]] for k in ("RG", "P28R2rec", "A5", "R4")},
            "sag3m_p99_and_count_gt0.3": {k: [ev[k]["Q21_1"]["sag_3m"]["p99_m"], ev[k]["Q21_1"]["sag_3m"]["n_gt_0.3m"]] for k in ("RG", "P28R2rec", "A5", "R4")},
            "mean_curvature_extrema": {k: ev[k]["Q21_1"]["mean_curvature_extrema"] for k in ("RG", "P28R2rec", "A5", "R4")},
            "bump4_d1_p99_max": {k: dome[k]["bump4_d1_p99_max"] for k in ("RG", "P28R2rec", "R4")},
            "cross_row_folds_gt30_gt60": {k: dome[k]["cross_row_folds_gt30_gt60"] for k in ("RG", "P28R2rec")},
            "F13_within_0.3m_1m": {k: [ev[k]["F13_proximity"]["within_0p3m"], ev[k]["F13_proximity"]["within_1m"]] for k in ev if "F13_proximity" in ev[k]},
            "waist_notch": {k: dome[k]["waist_notch"] for k in ("RG", "P28R2rec")},
        },
        "build_log": rep["log"][-1],
        "houdini_scene": hou,
    }
    RR.jdump(M, os.path.join(d, "metrics.json"))
    code = sorted(glob.glob(os.path.join(HERE, "r01_ridge_*.py"))) + [os.path.join(HERE, f) for f in (
        "rec_build.py", "rec_common.py", "r2_build.py", "r2_common.py", "r2_metrics.py", "rec_band.py", "rec_score.py", "rays_bl.py", "judge_dome_defs.py", "r2_fig.py")] + [
        os.path.join(RR.REPO, "Tools", "GWWaveGen", "kstar_h", f) for f in ("kh_common.py", "kh_eval.py", "kh_bl.py", "kh_houdini.py")] + [
        os.path.join(RR.REPO, "Tools", "GWWaveGen", "rubric", f) for f in ("rubric_check.py", "rubric_measure.py")]
    outs = sorted(glob.glob(os.path.join(d, "cand", "*"))) + sorted(glob.glob(os.path.join(d, "sheets", "*.png"))) + sorted(glob.glob(os.path.join(d, "figs", "*.png"))) + \
        sorted(glob.glob(os.path.join(d, "videos", "*.mp4"))) + [os.path.join(RR.REPO, "Houdini", "Polish28", "r01_ridge.hiplc")]
    ins = {"P28R2rec_rows": RR.BASE_ROWS, "P28R2rec_gwb": RR.BASE_GWB, "R4_rows": RR.ROWS["R4"], "A5_rows": RR.ROWS["A5"], "Kstar_26R01_rows": RR.ROWS["Kstar_26R01"],
           "sky_envelope_cov": os.path.join(RR.REPO, "Tools", "PaintingTruth", "targets", "masks", "sky_envelope_cov.png"),
           "stage9_ids_for_boat_keepout": os.path.join(RR.P28, "unity", "scene_stage9", "full", "ids_noline_noclaws.png"),
           "design38_linemask_read_only": os.path.join(RR.REPO, "Unity", "Build", "Design", "38", "outlines", "unity", "prep", "ds38_hero_linemask_f32.bin")}
    import numpy, scipy, cv2, PIL
    R = {
        "schema": "GreatWave.Polish28r01.ridge.run/1",
        "time": {"start": t_start, "end": t_end},
        "machine": {"python": sys.version.split()[0], "numpy": numpy.__version__, "scipy": scipy.__version__, "opencv": cv2.__version__, "pillow": PIL.__version__,
                    "platform": platform.platform(), "blender": "5.2.2 (G:/SteamLibrary/steamapps/common/Blender/blender.exe)",
                    "houdini": "Houdini Indie 22.0.429 hython (G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe)", "ffmpeg": RR.FFMPEG},
        "commands_from_repo_root": [
            "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_build.py build Unity/Build/Polish/28r01/ridge/cand/kstarP28R01RG_a45 Unity/Build/Polish/28r01/ridge/cand/ridge_design.json",
            "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_build.py build Unity/Build/Polish/28r01/ridge/cand_repro/kstarP28R01RG_a45 Unity/Build/Polish/28r01/ridge/cand/ridge_design.json   # 決定的の確かめ",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_eval.py --out Unity/Build/Polish/28r01/ridge/eval RG=… RGlow=… P28R2rec=… A5=… R4=… Kstar_26R01=…   # kh_eval（F13 あり）",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r2_metrics.py <ridge>/final/metrics_dome.json RG=… RGlow=… P28R2rec=… A5=… R4=…",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_metrics.py <ridge>/final/metrics_ridge.json （同じ）",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_band.py <ridge>/final/band.json RG=… P28R2rec=…",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_score.py <ridge>/final/score.json P28R2rec=… RG=…",
            "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <ridge>/renders RG=<gwb>,P28R2rec=<gwb>,A5=<gwb>,RGlow=<gwb> views=all",
            "blender … --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- turntable <gwb> <ridge>/renders/turntable_<label>.mp4 <ridge>/renders/turntable_<label>   # RG と P28R2rec",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_fig.py <ridge>",
            "\"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe\" Tools/GWWaveGen/kstar_p28/r01_ridge_houdini.py <ridge> Houdini/Polish28/r01_ridge.hiplc <ridge>/houdini/r01_ridge_hiplc_verify.json",
            "py -3.10 -B Tools/GWWaveGen/kstar_p28/r01_ridge_record.py <ridge> <start> <end> <ridge>/final/eye_verdict.json"],
        "determinism_note_ja": "OPENBLAS_NUM_THREADS=1 で 2 度（コードの整理の前と後）作り、rows・gwb がバイトまで同じ。並びの BLAS では A の 17 個が 1e-14 m 違う（gwb は同じ）。",
        "determinism": {"cand_gwb": RR.sha256(os.path.join(d, "cand", "kstarP28R01RG_a45.gwb")), "cand_repro_gwb": RR.sha256(os.path.join(d, "cand_repro", "kstarP28R01RG_a45.gwb")),
                        "cand_rows": RR.sha256(os.path.join(d, "cand", "kstarP28R01RG_a45_rows.npz")), "cand_repro_rows": RR.sha256(os.path.join(d, "cand_repro", "kstarP28R01RG_a45_rows.npz"))},
        "inputs_sha256": {k: RR.sha256(v) for k, v in ins.items() if os.path.isfile(v)},
        "outputs_sha256": {os.path.relpath(p, RR.REPO).replace("\\", "/"): RR.sha256(p) for p in outs if os.path.isfile(p)},
        "code_sha256": {os.path.relpath(p, RR.REPO).replace("\\", "/"): RR.sha256(p) for p in code if os.path.isfile(p)},
        "reference_model": {"path": r"G:\research\model\wave_repair_zbrush2.obj", "use": "kh_eval の F13 と量感の比べの数値だけ（評価器が SHA-256 を照合した一時キャッシュで読み、終わりに消した）。生成器は読まない（F13-1）。複製していない",
                            "expected_sha256": "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40",
                            "deleted_caches_log": open(os.path.join(d, "_tmp", "deleted_caches_sha256.txt"), encoding="utf-8").read().splitlines(),
                            "ref_cache_dir_left_files": os.listdir(os.path.join(d, "_tmp", "ref_cache")) if os.path.isdir(os.path.join(d, "_tmp", "ref_cache")) else []},
        "git_writes": "なし（add・commit・push をしていない）",
        "note_ja": "Unity の描画はしていない（粘土は Blender の Workbench、原画視点は numpy の z バッファー）。HMD 実機の結果ではない。動き・焼き込み・爪・色の当て直しはしていない。",
    }
    RR.jdump(R, os.path.join(d, "run.json"))
    print("RECORD_DONE", len(R["outputs_sha256"]), len(R["code_sha256"]), "added", added, "removed", removed)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
