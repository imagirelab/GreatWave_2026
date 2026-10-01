# -*- coding: utf-8 -*-
"""仕上げ28 第1回（射線の案）：run.json と metrics.json を r1_rays/ に書く（py -3.10）。
metrics.json：候補 P28R1 と比べ（R4 = 直前の採用版、Kstar_26R01 = CP1／26修正01）と試した案（A1〜A5）の主な値、
             閉じる目安ごとの判定（合格／不合格／記録のみ／この回では測っていない）。
run.json    ：命令、道具の版、入出力の SHA-256、参照モデルの扱い（一時キャッシュの SHA-256）、作業中の出来事。"""
import os
import sys
import json
import glob
import hashlib
import platform
import datetime

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rays_common as RC  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def pick(c):
    g, lf, lf4 = c["gate"], c.get("gate_lf", {}), c.get("gate_lf_r4", {})
    chk = {}
    for fid, lst in c["rubric"]["checks"].items():
        for x in lst:
            chk["%s %s" % (fid, x["name"])] = {"value": x["value"], "pass_must": x["pass_must"]}
    b6 = c.get("bulge6", {})
    q3 = c.get("Q21_3", {})
    return {
        "gate_definition_78_130_131_max_px": [g["78"]["max_px"], g["130"]["max_px"], g["131"]["max_px"]],
        "gate_definition_132_max_px_detail": g["132"]["max_px"], "gate_definition_72_p95_px_detail": g["72"]["p95_px"],
        "gate_large_form_sigma12_132_max_px": lf.get("132", {}).get("max_px"), "gate_large_form_sigma12_72_p95_px": lf.get("72", {}).get("p95_px"),
        "gate_large_form_sigma12_pass": c.get("gate_pass_lf"),
        "gate_large_form_sigma24_72_p95_px_recorded_only": lf4.get("72", {}).get("p95_px"),
        "rubric_must_fail": c["rubric"]["summary"]["must_fail"], "rubric_n_checks": c["rubric"]["summary"]["n_checks"],
        "bulge6_R4_p99_max": [b6.get("R4", {}).get("p99"), b6.get("R4", {}).get("max")],
        "bulge6_R6_p99_max": [b6.get("R6", {}).get("p99"), b6.get("R6", {}).get("max")],
        "bulge6_R6_regions_p99_max_gt0p3": b6.get("R6", {}).get("regions"),
        "sag3m_p99_max": [c["Q21_1"]["sag_3m"]["p99_m"], c["Q21_1"]["sag_3m"]["max_m"]],
        "fullness_ratio_area_over_H2": c["Q21_2"].get("ratio_area_over_H2"), "volume_c-14_14_m3": c["Q21_2"].get("volume_above_water_c-14_14_m3"),
        "b_region_ridge_median_p90_max_covered": [q3.get("top_vs_top_smooth", {}).get(k) for k in ("median_px", "p90_px", "max_px", "covered_samples")] if q3.get("top_vs_top_smooth") else None,
        "b_region_claw_edge_median_p90_max_covered": [q3.get("bottom_vs_bottom_smooth", {}).get(k) for k in ("median_px", "p90_px", "max_px", "covered_samples")] if q3.get("bottom_vs_bottom_smooth") else None,
        "F04_side_width_0p5H0_m": chk.get("F04 側面の影の幅 0.5H0（m、波峰に沿って見る）", {}).get("value"),
        "F04_highest_c_m": chk.get("F04 最高点の c（m）", {}).get("value"),
        "F02_main_Rmin_chord_fold": [chk.get("F02 Rmin_m（c -5~+3 の行の最小）", {}).get("value"), chk.get("F02 chord_pm2m_deg（c -5~+3 の最小）", {}).get("value"),
                                     chk.get("F02 fold_deg（1 頂点の折れ、c -5~+3 の最大）", {}).get("value")],
        "F13_within_0p3m_1m": [c.get("F13_proximity", {}).get("within_0p3m"), c.get("F13_proximity", {}).get("within_1m")],
        "mesh_selfx_flip_cross30_cross60": [c["mesh"]["local_selfx_vertices_win6"], c["mesh"]["flipped_quads_gt150"], c["mesh"]["cross_row_gt30_all"], c["mesh"]["cross_row_gt60_all"]],
        "sky_holes_spill_px": [c["sky"]["vs_painting_holes_in_wave"]["px"], c["sky"]["vs_painting_spill_into_sky"]["px"]],
    }


def tail_chord(rows):
    z = np.load(rows); A, Y, c = z["A"], z["Y"], z["c"]
    out = []
    for cc in (-39.7, -36.2, -32.0, -29.8, -27.9, -26.6):
        r = int(np.argmin(np.abs(c - cc)))
        a, y = A[r], Y[r]; s = np.r_[0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]; j = int(np.argmax(y))
        p = np.array([a[j], y[j]]); L = 2.0
        l = np.array([np.interp(s[j] - L, s, a), np.interp(s[j] - L, s, y)]); q = np.array([np.interp(s[j] + L, s, a), np.interp(s[j] + L, s, y)])
        u, v = l - p, q - p
        out.append([round(float(c[r]), 2), round(float(np.degrees(np.arccos(np.dot(u, v) / np.linalg.norm(u) / np.linalg.norm(v)))), 1)])
    return out


def main():
    d = sys.argv[1]
    summ = json.load(open(os.path.join(d, "eval", "kh_eval_summary.json"), encoding="utf-8"))
    by = {c["label"]: c for c in summ["candidates"]}
    M = {lab: pick(c) for lab, c in by.items()}
    br = json.load(open(os.path.join(d, "cand", "kstarP28R1_a45_build_report.json"), encoding="utf-8"))
    hv = json.load(open(os.path.join(d, "houdini_scene_verify.json"), encoding="utf-8"))
    P, R4, K = M["P28R1"], M["R4"], M["Kstar_26R01"]
    notch = {}
    npath = os.path.join(d, "eval", "waist_notch.txt")
    if os.path.isfile(npath):
        for line in open(npath, encoding="utf-8"):
            if " " in line and line.strip().startswith(("P28R1", "R4", "Kstar_26R01", "A1_rays_core", "A5_crest_ramp")):
                lab, js = line.split(" ", 1)
                dd = json.loads(js)
                notch[lab] = {"max": dd["max"], "by_height_m": {k: v[0] for k, v in dd["c-10..+12_h1..16"].items()},
                              "foot_c-30..-10_max": max(v[0] for v in dd["c-30..-10_h1..4.5"].values())}
    crit = [
        {"item": "後ろ 65° と回り台でドームが見えない（Q21）", "status": "不合格",
         "evidence": "renders/fig_views_user_back_P28R1_R4_Kstar.png（b65・b65z・b90・b115）、renders/turntable_R4_P28R1_A5.mp4、figs/sheet_vs_R4_1920x1080.png",
         "value": {"R6_p99": P["bulge6_R6_p99_max"][0], "R6_p99_R4": R4["bulge6_R6_p99_max"][0], "R6_p99_Kstar": K["bulge6_R6_p99_max"][0],
                   "R4_p99": P["bulge6_R4_p99_max"][0], "R4_p99_R4": R4["bulge6_R4_p99_max"][0], "sag3m_p99": P["sag3m_p99_max"][0]},
         "note": "後ろから見た丸い山の輪郭は R4 と同じ。背の下の鉛直の幕と縦の襞は減ったが、ドームは消えていない。R6 p99 は R4 の 0.693 → 0.681（−1.7%）で、第3回を行う条件（−30%）に届かない。"},
        {"item": "b区域が 3 つの房に読める（Q21）", "status": "不合格（1 つの棚のまま。数値は R4 とほぼ同じ）",
         "value": {"ridge": P["b_region_ridge_median_p90_max_covered"], "ridge_R4": R4["b_region_ridge_median_p90_max_covered"],
                   "claw_edge": P["b_region_claw_edge_median_p90_max_covered"], "claw_edge_R4": R4["b_region_claw_edge_median_p90_max_covered"]}},
        {"item": "F04 ≤ 18.5 m で本体が薄く見えない（Q16・Q21）", "status": "不合格（F04）／量感は満ちる",
         "value": {"F04": P["F04_side_width_0p5H0_m"], "F04_R4": R4["F04_side_width_0p5H0_m"], "fullness": P["fullness_ratio_area_over_H2"]}},
        {"item": "78・130・131 ≤ 4 px（定義どおりの読み）", "status": "合格", "value": {"P28R1": P["gate_definition_78_130_131_max_px"],
                                                                        "R4": R4["gate_definition_78_130_131_max_px"], "Kstar_26R01_CP1": K["gate_definition_78_130_131_max_px"]},
         "note": "CP1／26修正01 からの後退は戻っていない（評価基準 F01 の K*+0.5 は 3 つとも否）。"},
        {"item": "132・72 の爪なしの大きな輪郭 ≤ 4 px（σ12、σ24 の緩めなし）", "status": "合格",
         "value": {"132_max": P["gate_large_form_sigma12_132_max_px"], "72_p95": P["gate_large_form_sigma12_72_p95_px"],
                   "R4": [R4["gate_large_form_sigma12_132_max_px"], R4["gate_large_form_sigma12_72_p95_px"]]},
         "note": "72 の合格は、奥の行の唇の先（c −1〜+13.2、列 145〜262）を K*′ R3 の値へ戻したことによる（射線の作り直しそのものではない。A1_rays_core は 72 σ12 p95 6.714 で否）。細部込みの 132・72 は 5.911・5.521 px（段階6 の爪で）。"},
        {"item": "134・267 が合格", "status": "この回では測っていない（焼き込みと Unity の描画が要る）"},
        {"item": "t* の頂と手前の尾の行が弧", "status": "頂は合格／手前の尾は不合格",
         "value": {"F02_main_Rmin_chord_fold": P["F02_main_Rmin_chord_fold"], "tail_rows_chord_pm2m_deg": tail_chord(os.path.join(d, "cand", "kstarP28R1_a45_rows.npz")),
                   "tail_rows_chord_pm2m_deg_R4": tail_chord(RC.R4_ROWS)}},
        {"item": "背のくびれ（上から見た背の切れ込み、kh_R4_notch.py、±4 m の弦）", "status": "記録（R4 と同じか小さい。12 m より上は R4 と同じ値が残る）",
         "value": notch},
        {"item": "400×240 の並び・目印・UV を保つ", "status": "合格",
         "value": {"topology_same_as_kstar": True, "uv": "K* の UV0 と UV2（kh_common.write_candidate）", "rows_c_unchanged": True}},
    ]
    metrics = {"schema": "GreatWave.Polish28.round1_rays.metrics/1", "written": datetime.datetime.now().isoformat(timespec="seconds"),
               "candidate": "P28R1", "compared_with": {"previous_group": "R4（K*′ R4、設計28修正01 の採用版。仕上げ27 は形を変えていない）", "cp1": "Kstar_26R01（CP1／26修正01 の K*）"},
               "closing_criteria": crit, "values": M,
               "spine_build_report": {k: br[k] for k in ("outline_err_abs_max_px", "outline_err_abs_p95_px", "spine", "r6_fast", "objective")},
               "houdini_scene": hv,
               "claws_on_off_note": "爪あり・爪なしの評価器（Unity の描画、ds27 の関門）は、この回では回していない。K*′ の網には爪がないので、上の関門の値は幾何の読み（爪なしの大きな輪郭に当たる）。焼き直しと Unity の描画は仕上げ28 の後の工程。"}
    RC.jdump(metrics, os.path.join(d, "metrics.json"))
    # run.json
    files = {}
    for p in sorted(glob.glob(os.path.join(d, "cand", "*")) + glob.glob(os.path.join(d, "ablation", "*", "*.json")) + glob.glob(os.path.join(d, "ablation", "*", "*.gwb"))
                    + glob.glob(os.path.join(d, "figs", "*.png")) + glob.glob(os.path.join(d, "renders", "*.mp4")) + glob.glob(os.path.join(d, "renders", "fig_*.png"))
                    + [os.path.join(d, "eval", "kh_eval_table.md"), os.path.join(d, "eval", "kh_eval_summary.json")]):
        files[os.path.relpath(p, d).replace("\\", "/")] = {"sha256": sha(p), "bytes": os.path.getsize(p)}
    code = {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(HERE, "rays_*.py")) + glob.glob(os.path.join(HERE, "rays_*.json")) + glob.glob(os.path.join(HERE, "rays_*.sh")))}
    run = {"schema": "GreatWave.Polish28.round1_rays.run/1", "written": datetime.datetime.now().isoformat(timespec="seconds"),
           "workdir": d.replace("\\", "/"),
           "commands": [
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_analyze.py",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_build.py search <r1_rays>/search3 <base design>   (a_s の節の探索。採った節の値は search3/best_design.json)",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_build.py build <r1_rays>/cand/kstarP28R1_a45 <r1_rays>/cand/rays_design.json",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_build.py build <r1_rays>/ablation/<A*>/kstar_<A*> <r1_rays>/ablation/<A*>/rays_design_<A*>.json",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_eval.py --out <r1_rays>/eval P28R1=... R4=... Kstar_26R01=... A1..A5=...   (kh_eval.py、一時の場所だけ r1_rays/_tmp)",
               "blender --background --factory-startup --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <r1_rays>/renders <label=gwb,...> views=all",
               "blender ... rays_bl.py -- turntable <gwb> <mp4> <stills>",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_fig.py <r1_rays>",
               "hython Tools/GWWaveGen/kstar_p28/rays_houdini.py <r1_rays> Houdini/Polish28/rays.hiplc <r1_rays>/houdini_scene_verify.json",
               "py -3.10 Tools/GWWaveGen/kstar_p28/rays_record.py <r1_rays>"],
           "tools": {"python": platform.python_version(), "numpy": np.__version__, "blender": "Steam Blender 5.2.2（G:/SteamLibrary/steamapps/common/Blender）",
                     "houdini": hv.get("houdini"), "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build"},
           "inputs": {"R4_gwb": {"path": RC.R4_GWB.replace("\\", "/"), "sha256": sha(RC.R4_GWB), "expected": RC.R4_SHA["gwb"]},
                      "R4_rows": {"path": RC.R4_ROWS.replace("\\", "/"), "sha256": sha(RC.R4_ROWS), "expected": RC.R4_SHA["rows"]},
                      "R4_meta": {"path": RC.R4_META.replace("\\", "/"), "sha256": sha(RC.R4_META), "expected": RC.R4_SHA["meta"]},
                      "R3_rows_for_lip_graft": {"path": os.path.join(RC.REPO, "Unity", "Build", "Q20H", "final", "_R3", "kstarR3_a45_rows.npz").replace("\\", "/"),
                                                "sha256": sha(os.path.join(RC.REPO, "Unity", "Build", "Q20H", "final", "_R3", "kstarR3_a45_rows.npz"))},
                      "painting_outline": {"path": "Tools/PaintingTruth/targets/main_wave_outline_envelope.json",
                                           "sha256": sha(os.path.join(RC.REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json"))}},
           "reference_model": {"generator_reads_it": False,
                               "evaluator": "kh_eval.py が F13 と量感の比べのためだけに、SHA-256 の頭と尾を照合して一時キャッシュ（r1_rays/_tmp/ref_cache）を作り、終わりに消した。消したキャッシュの SHA-256 は _tmp/deleted_caches_sha256.txt。",
                               "full_sha256_checked": "ab4124f9720d6e27d80e2ae063916292898c87606a64441043f6a64de3d53d40（AGENTS.md の値と一致、2026-09-30 23:08 に読み取りのみで照合）",
                               "copied_into_repo_or_outputs": False},
           "incidents": [
               "2026-09-30 21:37 頃、最初の Blender の描画で出力先を相対パスで渡したため、12 枚の PNG が C:/Unity/Build/Polish/28/r1_rays/try/r_d0 に書かれた。その場所を探すために `find /` を約 60 秒走らせ、止めた（出力なし、表示された名前なし、ファイルの中身は読んでいない）。この探索はドライブ全体を辿るので、AGENTS.md の禁止する場所（一覧を取らない）の下も辿った可能性がある。止めた後は、候補のパスを test -e で 1 つずつ確かめる形に変えた。C: に書いた 12 枚は、この回で作ったものだけなので消した（C:/Unity/Build/Polish を削除。C:/Unity/Build/ArtFirst は前からあり、触れていない）。以後はすべて絶対パスで出力した。",
               "rays_build.py の編集の途中で、クラスの中にメソッドの重複（後の古い定義が勝つ）ができ、試作 t4〜fr2・br2 は古い back_ramp で作られた。見つけて直し、採った候補と試した案はすべて直した後のコードで作り直した（候補はバイトまで再現することを確かめた）。"],
           "timing": {"start": "2026-09-30 21:18", "end": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
           "files_sha256": files, "code_sha256": code}
    RC.jdump(run, os.path.join(d, "run.json"))
    print("ok")


if __name__ == "__main__":
    main()
