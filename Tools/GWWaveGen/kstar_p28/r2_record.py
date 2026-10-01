# -*- coding: utf-8 -*-
"""仕上げ28 第2回（r2）：metrics.json と run.json を書く（py -3.10）。値は eval/kh_eval_summary.json（kh_eval）、
metrics_r2.json（r2_metrics.py）、figs/fig_b_band_values.json（r2_fig.py）、cand/*_build_report.json、houdini/*.json から集める。
usage: py -3.10 r2_record.py <r2 dir> <start ISO> <end ISO>
"""
import os
import sys
import json
import hashlib
import platform
import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_common as R  # noqa: E402
REPO = R.REPO
B = os.path.join(REPO, "Unity", "Build")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def cand_by_label(summ, lab):
    for x in summ["candidates"]:
        if x["label"] == lab:
            return x
    return None


def g(x, *keys, default=None):
    for k in keys:
        if isinstance(x, dict) and k in x:
            x = x[k]
        else:
            return default
    return x


def main():
    d, t0, t1 = sys.argv[1], sys.argv[2], sys.argv[3]
    summ = json.load(open(os.path.join(d, "eval", "kh_eval_summary.json"), encoding="utf-8"))
    pa = os.path.join(d, "eval_ablation", "kh_eval_summary.json")
    if os.path.isfile(pa):
        sa = json.load(open(pa, encoding="utf-8"))
        have = {x["label"] for x in summ["candidates"]}
        summ["candidates"] += [x for x in sa["candidates"] if x["label"] not in have]
    mets = json.load(open(os.path.join(d, "metrics_r2.json"), encoding="utf-8"))
    band = json.load(open(os.path.join(d, "figs", "fig_b_band_values.json"), encoding="utf-8"))
    hou = json.load(open(os.path.join(d, "houdini", "r2_hiplc_verify.json"), encoding="utf-8")) if os.path.isfile(os.path.join(d, "houdini", "r2_hiplc_verify.json")) else None
    labs = [x["label"] for x in summ["candidates"]]

    def row(lab):
        x = cand_by_label(summ, lab); m = mets.get(lab, {})
        q3 = g(x, "Q21_3") or {}
        return {
            "outline_78_130_131_max_px_definition_reading": [g(x, "gate", "78", "max_px"), g(x, "gate", "130", "max_px"), g(x, "gate", "131", "max_px")],
            "large_form_sigma12_132_max_px": g(x, "gate_lf", "132", "max_px"),
            "large_form_sigma12_72_p95_px": g(x, "gate_lf", "72", "p95_px"),
            "large_form_sigma24_72_p95_px_record_only": g(x, "gate_lf_r4", "72", "p95_px"),
            "detail_132_max_72_p95_px_record_only": [g(x, "gate", "132", "max_px"), g(x, "gate", "72", "p95_px")],
            "gate_pass_large_form_sigma12": g(x, "gate_pass_lf"),
            "rubric_must_fail": g(x, "rubric", "summary", "must_fail"),
            "R6_p99_max": [m.get("R6_p99"), m.get("R6_max")], "R4_p99_max": [m.get("R4_p99"), m.get("R4_max")],
            "R6_regions_p99": m.get("R6_regions_p99"),
            "sag3m_p99_max": [g(x, "Q21_1", "sag_3m", "p99_m"), g(x, "Q21_1", "sag_3m", "max_m")],
            "surface_fit_back_max_p99": [g(x, "Q21_1", "surface_fit_6x12", "back", "max_m"), g(x, "Q21_1", "surface_fit_6x12", "back", "p99_m")],
            "back_elliptic_frac": m.get("back_elliptic_frac"), "upper_back_elliptic_frac": m.get("upper_back_elliptic_frac"),
            "back_convex_along_c_R25_frac": m.get("back_convex_along_c_R25_frac"),
            "back_plan_bow_0.5H0_0.7H0_L8_m": [m.get("back_plan_bow_0.5H0_L8_max_m"), m.get("back_plan_bow_0.7H0_L8_max_m")],
            "F04_side_width_0.5H0_m": m.get("F04_side_width_0.5H0_m"), "F04_rows_abs_c_le_6_m": m.get("F04_rows_abs_c_le_6_m"),
            "fullness_area_ratio": g(x, "Q21_2", "ratio_area_over_H2"), "fullness_shell_ratio": g(x, "Q21_2", "ratio_shell_over_H"),
            "b_region_ridge_med_p90_max_covered": [g(q3, "top_vs_top_smooth", "median_px"), g(q3, "top_vs_top_smooth", "p90_px"), g(q3, "top_vs_top_smooth", "max_px"), g(q3, "top_vs_top_smooth", "covered_samples")],
            "b_region_claw_edge_med_p90_max_covered": [g(q3, "bottom_vs_bottom_smooth", "median_px"), g(q3, "bottom_vs_bottom_smooth", "p90_px"), g(q3, "bottom_vs_bottom_smooth", "max_px"), g(q3, "bottom_vs_bottom_smooth", "covered_samples")],
            "arcs_pm2m": m.get("arcs_pm2m"), "waist_notch": m.get("waist_notch"), "bump4_d1_p99_max": m.get("bump4_d1_p99_max"),
            "far_back_to_tube_wall_m": m.get("far_back_to_tube_wall_m"), "cross_row_folds_gt30_gt60": m.get("cross_row_folds_gt30_gt60"),
            "mesh": g(x, "mesh"), "F13_within_0.3m_1m": g(x, "F13_proximity"), "sky_holes_spill_px": g(x, "sky"),
        }
    values = {lab: row(lab) for lab in labs}
    p2 = values["P28R2"]; r4 = values["R4"]; p1 = values["P28R1"]; k26 = values.get("Kstar_26R01", {})
    r6_drop = (r4["R6_p99_max"][0] - p2["R6_p99_max"][0]) / r4["R6_p99_max"][0]
    metrics = {
        "schema": "GreatWave.Polish28.round2.metrics/1",
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "candidate": "P28R2", "candidate_dir": os.path.join(d, "cand").replace("\\", "/"),
        "base": "P28R1（第1回の射線の案の候補。評審 j1 の best）",
        "compared_with": {"previous_group": "R4（K*′ R4。仕上げ27 は形を変えていない）", "round1_best": "P28R1", "cp1": "Kstar_26R01（CP1／26修正01 の K*）",
                          "round1_lowest_R6": "BF_P28bf（第1回の BACK-FIRST。関門を満たす版のうち R6 p99 が最小）"},
        "R6_p99_change_vs_R4": round(float(r6_drop), 4),
        "third_round_condition_R6_drop_ge_30pct_and_gates": bool(r6_drop >= 0.30 and p2["gate_pass_large_form_sigma12"]),
        "values": values,
        "b_region_band_all_readings": band,
        "claws_on_off_note": "爪あり（Unity の焼き込み・爪の描画）の評価器はこの回では回していない。形が採られた後に、29修正01 の焼き直し → Unity の描画で、爪あり・爪なしの両方を測る（仕上げ28 の中の一度の焼き直し）。",
        "houdini_scene": hou,
    }
    R.jdump(metrics, os.path.join(d, "metrics.json"))
    # run.json
    files = {}
    for rel in ("cand/kstarP28R2_a45.gwb", "cand/kstarP28R2_a45_rows.npz", "cand/kstarP28R2_a45.obj", "cand/kstarP28R2_a45_meta.json", "cand/r2_design.json"):
        p = os.path.join(d, rel)
        if os.path.isfile(p):
            files[rel] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    tools = {}
    for f in sorted(os.listdir(HERE)):
        if f.startswith("r2_") and f.endswith(".py"):
            tools["Tools/GWWaveGen/kstar_p28/" + f] = sha(os.path.join(HERE, f))
    inputs = {"P28R1_rows_base": os.path.join(B, "Polish", "28", "r1_rays", "cand", "kstarP28R1_a45_rows.npz"),
              "R4_rows": os.path.join(B, "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"),
              "sky_envelope_mask": R.SKY_MASK,
              "band_targets": os.path.join(REPO, "Tools", "GWWaveGen", "kstar3", "candA4_band_targets.json"),
              "painting_outline": os.path.join(REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json")}
    run = {
        "schema": "GreatWave.Polish28.round2.run/1",
        "written": datetime.datetime.now().isoformat(timespec="seconds"),
        "workdir": d.replace("\\", "/"),
        "timing": {"start": t0, "end": t1},
        "commands": [
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_build.py <r2>/cand/kstarP28R2_a45 <r2>/cand/r2_design.json",
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_build.py <r2>/ablation/<A*>/kstar_<A*> <r2>/ablation/<A*>/r2_design_<A*>.json   (1 つずつ順に)",
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_eval.py --out <r2>/eval P28R2=... R4=... P28R1=... Kstar_26R01=... BF_P28bf=... A1..A6=...   (kh_eval.py、F13 あり、一時の場所は r2/_tmp)",
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_metrics.py <r2>/metrics_r2.json <label=rows ...>",
            "blender --background --factory-startup --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <r2>/renders <label=gwb,...> views=all",
            "blender ... rays_bl.py -- turntable <gwb> <r2>/renders/turntable_<label>.mp4 <r2>/renders/turntable_<label>",
            "ffmpeg -i turntable_R4.mp4 -i turntable_P28R2.mp4 -filter_complex hstack ... turntable_R4_vs_P28R2.mp4",
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_fig.py <r2>",
            "hython Tools/GWWaveGen/kstar_p28/r2_houdini.py <r2> Houdini/Polish28/r2.hiplc <r2>/houdini/r2_hiplc_verify.json",
            "py -3.10 Tools/GWWaveGen/kstar_p28/r2_record.py <r2> <start> <end>"],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "blender": "Steam Blender 5.2.2（G:/SteamLibrary/steamapps/common/Blender）",
                  "houdini": "Steam Houdini Indie 22.0.429 hython", "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build", "code_sha256": tools},
        "inputs": {k: {"path": v.replace("\\", "/"), "sha256": sha(v)} for k, v in inputs.items()},
        "outputs": files,
        "reference_model": {
            "generator_reads_it": False,
            "evaluator": "kh_eval.py が F13 と量感の比べのためだけに、SHA-256 の頭と尾を照合して一時キャッシュ（r2/_tmp/ref_cache）を作り、終わりに消した。"
                         "消したキャッシュの SHA-256 は r2/_tmp/deleted_caches_sha256.txt。",
            "copied_into_repo_or_outputs": False},
        "decisions_Q24": [
            "土台は評審 j1 の best の P28R1（第1回の射線の案）。第1回の 3 案の共通の原因（断面が管を包む頭巾）を、原画の空の射線の禁止域の内で断面を作り直して読み直す（第1回の頂の線の配り直しを繰り返さない）。",
            "頂の線を原画の頂の奥で上げる案（A4、第1回の A5 の続き）は、c 0〜+2.4 の行が原画の頂と 132 の唇で止まり（禁止域の測り：上げられる量 0.01〜0.1 m）、後ろから見て二つの山と谷になるので採らない。",
            "頂を締めて左の輪郭を当て直す案（A5）は、背の楕円の面は減るが R6 と頂の弦（Q17 の弧）が悪くなるので採らない。",
            "背の傾きは 52°（A6 の 56° は後ろから見て細いが、殻の比 0.80 で「又太单薄了」（Q21）の暫定基準 ≥ 0.90 を割る）。",
            "b区域の稜を原画の帯の 3 つの房へ合わせる（L）。R6 p99 は +0.045 m ほど上がる（A2 との差）が、b区域は利用者の言葉（Q21）、R6 は代わりの測りなので、b区域を採る。R6 を最も下げる版は A3（稜のこぶをならす、帯の中央値が 10 px を超える）として記録。",
            "第3回の条件（R6 p99 が R4 の 0.693 m より 30% 以上下がる）は満たさない。計画 §5.1 のとおり、関門を満たす版のうち R6 p99 の最も小さい版を採るのは進行役の判断（この回では決めない）。"],
        "incidents": [
            "2026-10-01 01:36 頃、試した案の生成（numpy）を 5 つ並べて同時に走らせ、1 つ（A5）が MemoryError で止まった（AGENTS の注意「重い numpy を同時に走らせない」に反した）。以後は 1 つずつ順に走らせた。A5 は作り直した（ablation の build_log_parallel_memoryerror.txt は古い版の記録、今の ablation は最終の設計からの作り直し）。",
            "2026-10-01 01:58 頃、古い候補（V6）で走らせていた kh_eval を止めた（形を V13 に替えたため）。止めた時に参照モデルの F13 用の一時キャッシュ（_tmp/ref_cache/_kh_ref_f13_cache_9584.npz）が残ったので、SHA-256 を記録して手で消した（_tmp/deleted_caches_sha256.txt）。",
            "2026-10-01 02:29〜02:30、最終候補の kh_eval（背景で実行中）と同時に、b区域の強い当てはめの試し（r2_build）と帯の図（r2_fig）を走らせ、kh_eval（P28R1 の行で）と帯の図が MemoryError で止まった（重い numpy の同時実行。2 度目）。kh_eval は後始末で参照モデルの一時キャッシュを消していた（_tmp/deleted_caches_sha256.txt 02:30:19）。止まった出力は r2/_superseded/eval_failed_memoryerror_0230 に移し、kh_eval を他に何も走らせずに 2 回（eval/：P28R2・R4・P28R1・K* 26R01・BF_P28bf、eval_ablation/：P28R2・A1〜A6）に分けて走らせ直した。以後の r2_metrics・図・hython もすべて 1 つずつ走らせた。",
            "候補を 3 度替えた（θ_b 56° → 52°：殻の比、奥の壁 0.04 m の折れ目 → 管の角の高さだけ厚く、奥の壁の厚さの c の範囲 → 端の行の折れ）。古い版は r2/_superseded/（cand_v1_theta56、v2_V6、v3_V13）に残した（Git 対象外）。"
        ],
        "eval_split": {"eval": "P28R2, R4, P28R1, Kstar_26R01, BF_P28bf（kh_eval_table.md が本表）", "eval_ablation": "P28R2, A1〜A6（試した案の表）"},
        "houdini_personal_strings": "Houdini/Polish28/r2.hiplc に Houdini が書く作成者の文字列 wang6@Williams が 35 か所、個人設定のフォルダーのパス（C:/Users/wang6/houdini22.0/poselib）が 1 か所ある（第1回の rays.hiplc と同じ既知の問題）。コミットの前に扱いを決める。",
        "not_done_this_round": ["爪あり・爪なしの評価器（Unity の焼き込みと描画）", "134・267 の色区", "動き F_final の当て直し", "焼き込み 29/30/31/32/33/36/38 の当て直し",
                                "F7-1 の切り分け", "Q10 の物理の関門"],
    }
    R.jdump(run, os.path.join(d, "run.json"))
    print("metrics.json / run.json written; R6 change vs R4 %.1f%%" % (100 * r6_drop))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
