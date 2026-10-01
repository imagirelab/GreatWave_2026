# -*- coding: utf-8 -*-
"""仕上げ28 の回復（rec）：記録のための数（metrics_rec.json）と実行条件（run_rec.json）を Docs/Evidence/Polish/28 に書き、
群の全体の metrics.json・run.json（部ごとのファイルの目次と、バックログの項目 → 値 → 判定）も書く（py -3.10）。
読むのは Git 対象外の Unity/Build/Polish/28 の出力だけ（参照モデルは読まない）。
usage: py -3.10 -B Tools/GWWaveGen/pl28/pl28rec_record.py --start 2026-10-01T06:49 --end <時刻>
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import platform
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
P28 = os.path.join(REPO, "Unity", "Build", "Polish", "28")
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "28")
U = os.path.join(P28, "unity")


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def safe(fn, default=None):
    try:
        return fn()
    except Exception as e:  # 記録の道具：欠けた出力は欠けたと書く
        return {"missing_or_error": str(e)[:200]} if default is None else default


def unity_state(scene):
    r = J(os.path.join(U, scene, "pl28u_regress.json"))
    o = {}
    for s in ("t28_white", "t28_claws"):
        e = r["sets"][s]
        st = e["strict"]
        o[s] = {"78_130_131_max_px": [st["silhouettes_definition_reading"][k]["max_px"] for k in ("78", "130", "131")],
                "132_sigma12_max_px": e["large_form"]["s12"]["132_max_px"], "72_sigma12_p95_px": e["large_form"]["s12"]["72_p95_px"],
                "72_sigma24_p95_px": e["large_form"]["s24"]["72_p95_px"],
                "132_detail_max_px": st["silhouettes_definition_reading"]["132"]["max_px"], "72_detail_p95_px": st["silhouettes_definition_reading"]["72"]["p95_px"],
                "71_p95_px": st["silhouettes_definition_reading"]["71"]["p95_px"],
                "colour": {k: {"max_px": v["max_now_px"], "verdict": v["verdict"], "diff_vs_28r01_px": v["worst_abs_diff_vs_28r01_px"]} for k, v in st["colour_items"].items()},
                "colour_265_267": st["colour_265_267"],
                "sym_worst_abs_diff_px": (e.get("sym") or {}).get("worst_abs_diff_px"),
                "sym_rows": (e.get("sym") or {}).get("rows"), "sym_267_bands": (e.get("sym") or {}).get("flat_painting_view_266_267")}
    return o


def eval23(name):
    m = J(os.path.join(U, "eval23", name, "metrics.json"))
    it = m["items"]
    out = {}
    for k in ("157", "159", "71", "72", "76", "212", "213"):
        if k in it:
            ms = it[k]["measures"][0]
            out[k] = {"target": ms.get("target"), "max_px": ms.get("value_max_px"), "p95_px": ms.get("p95_px"), "n_render_assigned": ms.get("n_render_assigned"),
                      "verdict": it[k].get("verdict")}
    out["gate"] = m.get("gate")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-10-01T06:49")
    ap.add_argument("--end", default=None)
    a = ap.parse_args()
    end = a.end or datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
    rec = os.path.join(P28, "rec")
    M = {"schema": "GreatWave.Polish28.rec_metrics/1", "number": "仕上げ28 の原画視点の後退の回復（rec）",
         "made_local": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
         "evidence_kind_ja": "numpy の形の生成器と評価器、Houdini の hython（読んで見せるだけ）、動きの生成器と関門の検査器、Blender 5.2.2 の粘土、"
                             "Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画、原画視点の評価器。HMD 実機の結果ではない。利用者は確かめていない。"}
    M["adopted"] = {"kstar": safe(lambda: J(os.path.join(P28, "kstar_p28rec", "_frozen_from.json"))["files"]),
                    "motion": "Unity/Build/Polish/28/G_p28rec（art_on・timewarp_G_p28rec.json）",
                    "motion_sha256": safe(lambda: {os.path.basename(p): sha(p) for p in [os.path.join(P28, "G_p28rec", "art_on", f) for f in
                                                                                       ("ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_keypose.json", "ds27_twhite_r32f.bin")]
                                                   + [os.path.join(P28, "G_p28rec", "timewarp_G_p28rec.json")]})}
    M["shape"] = {
        "build_report_log": safe(lambda: J(os.path.join(rec, "cand", "kstarP28R2rec_a45_build_report.json"))["log"][-4:]),
        "protect_info": safe(lambda: J(os.path.join(rec, "cand", "kstarP28R2rec_a45_build_report.json"))["protect_info"]),
        "dome_and_back_metrics": safe(lambda: J(os.path.join(rec, "final", "metrics_final.json"))),
        "b_band": safe(lambda: J(os.path.join(rec, "final", "band_final.json"))),
        "lines_and_protect_numpy": safe(lambda: J(os.path.join(rec, "final", "score_final.json"))),
        "mask_preview_record_only": safe(lambda: J(os.path.join(rec, "final", "mask_preview_final.json"))),
        "line_predictor_validation": safe(lambda: J(os.path.join(rec, "linecheck", "rec_linecheck.json"))),
        "kh_eval_table": rel(os.path.join(rec, "final", "eval", "kh_eval_table.md")),
        "tried_not_adopted": {"P1_protect_only": "rec/try/P1（殻が 0.16 H まで薄い）", "P3_with_line_guard": "rec/try/P3（b区域の房の際立ち 38 → 15 px）",
                              "P4": "rec/try/P4（採った設定と同じバイト）"},
        "houdini": safe(lambda: J(os.path.join(rec, "houdini", "rec_hiplc_verify.json")))}
    M["unity"] = {"stage9": safe(lambda: unity_state("scene_stage9")), "p28": safe(lambda: unity_state("scene_p28")), "rec": safe(lambda: unity_state("scene_rec")),
                  "eval23_clawfree_line": {st: safe(lambda st=st: eval23("%s_off_line_noclaws" % st)) for st in ("stage9", "p28", "rec")},
                  "eval23_asis_line": {st: safe(lambda st=st: eval23("%s_off_line" % st)) for st in ("stage9", "p28", "rec")},
                  "boats_and_lines_counts": safe(lambda: J(os.path.join(U, "pl28rec_unity_counts.json"))["states"]),
                  "gpu_check": safe(lambda: {k: v for k, v in J(os.path.join(U, "check_gpu_G_p28rec.json")).items() if not isinstance(v, (list, dict)) or k in ("summary",)}),
                  "render_report": safe(lambda: {k: v for k, v in J(os.path.join(U, "scene_rec", "pl28_render_report.json")).items()
                                                 if k in ("unity", "device", "graphicsApi", "state", "heroPackage", "heroMeshGwb", "heroMeshSha256", "heroSdf", "heroSdfSha256",
                                                          "heroUvWarp", "heroUvWarpSha256", "timewarp", "timewarpSha256", "heroGpuBytes", "protectedUnchanged", "seconds")}),
                  "seam_near_ring": safe(lambda: J(os.path.join(U, "seam_near_ring.json"))["heroes"]),
                  "catmap_seat_toward_wave": safe(lambda: {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in J(os.path.join(U, "catmap_stw_stage9_p28_rec.json"))["states"].items()})}
    M["motion"] = {"gates_table": safe(lambda: {t: J(os.path.join(P28, "motion", "gates_table_rec.json"))["tags"][t]["sets"]["default"] for t in ("F_final", "G_p28b", "G_p28rec")}),
                   "fr_motion_60hz": safe(lambda: {t: {k: v for k, v in J(os.path.join(P28, "motion", "fr", "motion_%s.json" % t)).items() if k in (
                       "selfx_frames", "V_max", "V_loss_frac_from_max", "V_step_last2s_max_before_max_ratio", "chord_pre_lip", "sharp_rows", "loaf")}
                       for t in ("G_p28b", "G_p28rec")}),
                   "loaf": safe(lambda: J(os.path.join(P28, "motion", "loaf_rec.json"))),
                   "timing": safe(lambda: J(os.path.join(P28, "G_p28rec", "pipeline_timing.json"))),
                   "generate_log": safe(lambda: {k: v for k, v in J(os.path.join(P28, "G_p28rec", "art_on", "ds28p_generate_log.json")).items() if k in ("command", "p_on", "p_off", "seconds", "files", "lean_export", "log_only")}),
                   "lip_tip_thickness_and_static_mesh_qa": safe(lambda: rel(os.path.join(rec, "measure_qa", "ds29r01_qa_G_p28rec_fine.md")))}
    with open(os.path.join(EV, "metrics_rec.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(M, f, ensure_ascii=False, indent=1, default=float)
    # run_rec.json
    code = sorted(glob.glob(os.path.join(REPO, "Tools", "GWWaveGen", "kstar_p28", "rec_*.py")) + [os.path.join(REPO, "Tools", "GWWaveGen", "kstar_p28", f) for f in
                  ("r2_build.py", "r2_common.py", "r2_metrics.py", "judge_dome_defs.py")] + [os.path.join(REPO, "Tools", "GWWaveGen", "pl28", f) for f in
                  ("pl28rec_unity_fig.py", "pl28rec_record.py", "pl28u_bake_input.py", "pl28u_tstar_eval.py", "pl28u_regress.py", "pl28u_seam.py", "pl28u_catmap.py",
                   "pl28u_sheets.py", "pl28_clay_compose.py", "pl28_commit_deps.py")] + [os.path.join(REPO, "Unity", "Assets", "GreatWave", "Polish28", "Editor", "PL28Render.cs")])
    R = {"schema": "GreatWave.Polish28.rec_run/1", "made_local": M["made_local"], "timing": {"start": a.start, "end": end},
         "tools": {"python": platform.python_version(), "numpy": __import__("numpy").__version__, "blender": "Steam Blender 5.2.2（G:/SteamLibrary/steamapps/common/Blender）",
                   "houdini": "Steam Houdini Indie 22.0.429 hython", "unity": "6000.4.3f1（E:\\6000.4.3f1\\Editor\\Unity.exe、batchmode、Direct3D11、RTX 3080）",
                   "ffmpeg": "G:/ffmpeg-2024-12-19-git-494c961379-full_build"},
         "commands": [
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_diag.py <rec>/diag0 ; rec_linecheck.py <rec>/linecheck ; rec_score.py <rec>/score_ablation.json P28R1=… P28R2=… A1=… A2=… A3=…",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_build.py G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/rec/cand/kstarP28R2rec_a45 Unity/Build/Polish/28/r2/cand/r2_design.json Unity/Build/Polish/28/rec/cand/rec_design.json",
             "（凍結）rec/cand の gwb・rows・meta を Unity/Build/Polish/28/kstar_p28rec/ へ写し、_frozen_from.json に SHA-256（読み取り専用の属性）",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_eval.py --out <rec>/final/eval P28R2rec=… P28R2=… R4=… P28R1=… Kstar_26R01=…（kh_eval、F13 あり、一時の場所は rec/_tmp）",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/r2_metrics.py <rec>/final/metrics_final.json R4=… P28R2=… P28R2rec=…",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_band.py <rec>/final/band_final.json R4=… P28R2=… P28R2rec=…",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_score.py <rec>/final/score_final.json P28R2=… P28R2rec=…",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_mask_preview.py <rec>/final/mask_preview_final.json P28R2rec=… P28R2=…",
             "blender --background --factory-startup --python-exit-code 1 --python Tools/GWWaveGen/kstar_p28/rays_bl.py -- views <rec>/renders P28R2rec=<gwb> views=all ; … -- turntable <gwb> <rec>/renders/turntable_P28R2rec.mp4 <rec>/renders/turntable_P28R2rec",
             "py -3.10 -B Tools/GWWaveGen/kstar_p28/rec_fig.py <rec>",
             "hython Tools/GWWaveGen/kstar_p28/rec_houdini.py <rec> Houdini/Polish28/rec.hiplc <rec>/houdini/rec_hiplc_verify.json",
             "OPENBLAS_NUM_THREADS=1 py -3.10 -B Tools/GWWaveGen/ds28p/ds28p_generate.py --kstar Unity/Build/Polish/28/kstar_p28rec --name G_p28rec/art_on --out Unity/Build/Polish/28 --workers 4 --p-off upper_back_aspect --lean-export（省メモリの書き出し。第 13 節）",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28_pipeline_limited.py --max-jobs 3 -- --kstar Unity/Build/Polish/28/kstar_p28rec --tag G_p28rec --root Unity/Build/Polish/28 --skip-generate --skip-p20-e --check-workers 4",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28_gate_table.py --tag F_final=… --tag F_p27=… --tag G_final=… --tag G_p28a=… --tag G_p28b=… --tag G_p28rec=Unity/Build/Polish/28/G_p28rec --out Unity/Build/Polish/28/motion/gates_table.json",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28_fr_motion.py G_p28rec Unity/Build/Polish/28/G_p28rec/art_on Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json 60 Unity/Build/Polish/28/motion/fr/motion_G_p28rec.json Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json",
             "sh Tools/GWWaveGen/pl28/run_pl28_clay.sh（Blender の粘土のこま、G_p28rec）; py -3.10 -B Tools/GWWaveGen/pl28/pl28_clay_compose.py video|sheet …",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_bake_input.py --build Unity/Build/Polish/28/unity/bake_rec --kstar-dir Unity/Build/Polish/28/kstar_p28rec --gwb kstarP28R2rec_a45.gwb --meta kstarP28R2rec_a45_meta.json --sha a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
             "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl28/run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log u_bake_rec -Extra \"-ds29r01BakeRoot Build/Polish/28/unity/bake_rec\"",
             "powershell … run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log u_ds29_G_p28rec -Package Build/Polish/28/G_p28rec/art_on -WarpFile Build/Polish/28/G_p28rec/timewarp_G_p28rec.json -OutDir Build/Polish/28/unity/ds29_G_p28rec -Stills \"m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0\" -Views \"painting,seat,seat_toward_wave,side_left\" -Skip timing,video -Extra \"-ds29Name G_p28rec -ds29MeshFromPackage 0 -ds29KStarGwb Build/Polish/28/unity/bake_rec/kstar/kstar_a45.gwb -ds29Sdf Build/Polish/28/unity/bake_rec/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Polish/28/unity/bake_rec/bake/af28r01_uvwarp_a45.json\"",
             "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Polish/28/unity/ds29_G_p28rec --package Unity/Build/Polish/28/G_p28rec/art_on --range=-12,0 --out Unity/Build/Polish/28/unity/check_gpu_G_p28rec.json",
             "powershell … run_pl28_unity.ps1 -Method GreatWave.Polish28.EditorTools.PL28Render.Render -Log u_scene_rec -Extra \"-pl28State p28 -pl28Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/unity/scene_rec -pl28HeroPkg Build/Polish/28/G_p28rec/art_on -pl28HeroGwb Build/Polish/28/unity/bake_rec/kstar/kstar_a45.gwb -pl28HeroSdf Build/Polish/28/unity/bake_rec/bake/af28r01_uvsdf_a45.bin -pl28HeroUvWarp Build/Polish/28/unity/bake_rec/bake/af28r01_uvwarp_a45.json -pl28Timewarp Build/Polish/28/G_p28rec/timewarp_G_p28rec.json\"",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/28/unity/scene_rec --kstar rec",
             "py -3.10 Tools/PaintingTruth/evaluate.py --render Unity/Build/Polish/28/unity/scene_rec/full/painting_t120_off.png --ids …/scene_rec/full/<ids>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir Unity/Build/Polish/28/unity/eval23/rec_<name> --name rec_<name>（4 組）",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28rec_unity_fig.py ; pl28u_seam.py ; pl28u_catmap.py --states stage9,p28,rec --out … ; pl28u_sheets.py --after rec --prefix pl28rec",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28rec_record.py --start 2026-10-01T06:49 --end <時刻>",
             "py -3.10 -B Tools/GWWaveGen/pl28/pl28_commit_deps.py <seed> Unity/Build/Polish/28/commit_list.txt Unity/Build/Polish/28/commit/commit_deps_report.json"],
         "code_sha256": {rel(p): sha(p) for p in code if os.path.isfile(p)},
         "inputs_sha256": {rel(p): sha(p) for p in [os.path.join(P28, "r1_rays", "cand", "kstarP28R1_a45_rows.npz"), os.path.join(P28, "r2", "cand", "r2_design.json"),
                                                   os.path.join(P28, "rec", "cand", "rec_design.json"),
                                                   os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"),
                                                   os.path.join(U, "scene_stage9", "full", "ids_noline_noclaws.png"),
                                                   os.path.join(REPO, "Unity", "Build", "Design", "38", "outlines", "unity", "prep", "ds38_hero_linemask_f32.bin"),
                                                   os.path.join(REPO, "Tools", "PaintingTruth", "targets", "masks", "sky_envelope_cov.png")] if os.path.isfile(p)},
         "outputs_sha256": {rel(p): sha(p) for p in sorted(glob.glob(os.path.join(P28, "kstar_p28rec", "*"))) +
                            [os.path.join(P28, "G_p28rec", "timewarp_G_p28rec.json"), os.path.join(REPO, "Houdini", "Polish28", "rec.hiplc")] +
                            sorted(glob.glob(os.path.join(U, "bake_rec", "bake", "*"))) if os.path.isfile(p)},
         "evidence_sha256": {os.path.basename(p): sha(p) for p in sorted(glob.glob(os.path.join(EV, "*"))) if os.path.basename(p) not in ("metrics_rec.json", "run_rec.json", "metrics.json", "run.json")},
         "reference_model": {"generator_reads_it": False,
                             "evaluator": "kh_eval.py（rec_eval.py の包み）が F13 と量感の比べのためだけに、SHA-256 を照合した一時キャッシュ（Unity/Build/Polish/28/rec/_tmp/ref_cache）で読み、終わりに消した。消したキャッシュの SHA-256 は rec/_tmp/deleted_caches_sha256.txt",
                             "deleted_caches": safe(lambda: open(os.path.join(rec, "_tmp", "deleted_caches_sha256.txt"), encoding="utf-8").read().splitlines(), []),
                             "copied_into_repo_or_outputs": False}}
    with open(os.path.join(EV, "run_rec.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    write_group(M, R)
    print("PL28REC_RECORD_DONE", len(R["evidence_sha256"]), "evidence files")


def write_group(M, R):
    """群の全体の metrics.json（バックログの項目 → 値 → 判定、閉じる目安、原画視点の後退の回復、動きの関門）と run.json（部ごとの記録の目次）。
    値は metrics_rec.json（回復の版）から取る。動きの部・Unity の部の値は metrics_motion.json・metrics_unity.json（回復の前の版まで）。"""
    u = M["unity"].get("rec") or {}
    w = u.get("t28_white", {})
    c = u.get("t28_claws", {})
    col = w.get("colour", {})
    sh = (M["shape"].get("dome_and_back_metrics") or {}).get("P28R2rec", {})
    band = (M["shape"].get("b_band") or {}).get("P28R2rec", {})
    e157 = (M["unity"].get("eval23_clawfree_line", {}).get("rec") or {}).get("157", {})
    g = (M["motion"].get("gates_table") or {}).get("G_p28rec", {})
    sil = w.get("78_130_131_max_px") or [None, None, None]
    items = {
        "68": {"value": "唇先の厚さ（唇先から 0.75 m 奥の鉛直）の最小 0.041 m（t* で 0.281 m）、隣と逆向きの面（二面角 > 120°）77。ds29r01_measure qa（G_p28rec、精度の層、Blender なし）",
               "verdict": "不合格（記録。≥ 0.3 m）"},
        "69": {"value": "主役波の頂の表示の y は段階9 と同じ（輪郭の値が P28R2 と同じ）", "verdict": "記録（設計40 で合格）"},
        "70": {"value": "頂の y が変わらないので、波の上下と右船の長さの関係は設計40 と同じ", "verdict": "記録（設計40 で合格）"},
        "71": {"value": {"p95_px_clawfree": w.get("71_p95_px"), "p95_px_claws": c.get("71_p95_px")}, "verdict": "記録のみ"},
        "72": {"value": {"sigma12_p95_clawfree": w.get("72_sigma12_p95_px"), "sigma12_p95_claws": c.get("72_sigma12_p95_px"),
                         "sigma24_p95_clawfree": w.get("72_sigma24_p95_px"), "detail_p95_clawfree": w.get("72_detail_p95_px")},
               "verdict": "合格（σ12、閉じる目安の読み）。細部込みは不合格・仕上げ33"},
        "73": {"value": (col.get("73") or {}).get("max_px"), "verdict": "合格（28修正01 と +1.83 px。±0.5 超え、段階9 と同じ）"},
        "77": {"value": (col.get("77") or {}).get("max_px"), "verdict": "合格"},
        "78": {"value": sil[0], "verdict": "合格"},
        "79": {"value": (col.get("79") or {}).get("max_px"), "verdict": "合格（28修正01 と +0.68 px。段階9 +0.67）"},
        "130": {"value": sil[1], "verdict": "合格（CP1 より +1.61 px）"},
        "131": {"value": sil[2], "verdict": "合格（CP1 より +1.63 px）"},
        "132": {"value": {"sigma12_max_clawfree": w.get("132_sigma12_max_px"), "detail_max_clawfree": w.get("132_detail_max_px"),
                          "detail_max_claws": c.get("132_detail_max_px")}, "verdict": "合格（σ12）。細部込みは不合格・仕上げ33"},
        "133": {"value": (col.get("133") or {}).get("max_px"), "verdict": "合格"},
        "134": {"value": {"clawfree": (col.get("134") or {}).get("max_px"), "claws": ((c.get("colour") or {}).get("134") or {}).get("max_px")},
                "verdict": "不合格（爪なし。唇先 (1090, 427) で描画が空）。爪ありは合格（記録）"},
    }
    closing = [
        {"criterion_ja": "後ろ 65° と回り台でドームが見えない（Q21）", "value": {"R6_p99_m": sh.get("R6_p99"), "R6_p99_R4_m": 0.693, "by_eye": "R4 と同じに見える（粘土・Unity）"},
         "verdict": "満たさない"},
        {"criterion_ja": "b区域が 3 つの房に読める（Q21）", "value": {"lobes_prom6": band.get("lobes_prom6"), "top_vs_top_raw": band.get("top_vs_top_raw")},
         "verdict": "満たさない（3 つのうち 1 つ）"},
        {"criterion_ja": "F04 ≤ 18.5 m で本体が薄く見えない（Q16・Q21）", "value": {"F04_0p5H0_m": sh.get("F04_side_width_0.5H0_m"), "fullness": 1.35, "shell_ratio": 0.92},
         "verdict": "F04 は満たさない。薄く見えない は満たす"},
        {"criterion_ja": "78・130・131 が定義どおりの読みで ≤ 4 px", "value": sil, "verdict": "満たす"},
        {"criterion_ja": "132・72 の爪なしの大きな輪郭が σ24 の緩めなし（σ12）で ≤ 4 px", "value": [w.get("132_sigma12_max_px"), w.get("72_sigma12_p95_px")], "verdict": "満たす"},
        {"criterion_ja": "134・267 が合格", "value": {"134_clawfree": (col.get("134") or {}).get("max_px"), "267_bands": (w.get("colour_265_267") or {}).get("267_bands_ge_20px")},
         "verdict": "満たさない"},
        {"criterion_ja": "t* の頂と手前の尾の行が弧（Q17）", "value": sh.get("arcs_pm2m"), "verdict": "満たす"},
    ]
    G = {"schema": "GreatWave.Polish28.metrics/1", "number": "仕上げ28（設計28 原画の弧・最後の一コマ）", "made_local": M["made_local"],
         "state_ja": "閉じていない（閉じる目安 7 のうち 3）。採用は K*′ P28R2rec ＋ 動き G_p28rec（原画視点の後退の回復の版）。HMD 実機の結果ではない。利用者は確かめていない。",
         "evidence_kind_ja": M["evidence_kind_ja"], "adopted": M["adopted"],
         "closing_criteria_plan_5_3": closing, "closing_criteria_met": "3/7", "backlog": items,
         "painting_view_regression_recovery": {
             "boat_left_157_clawfree": {"rec": e157, "stage9": {"max_px": 77.5517, "p95_px": 63.5708, "n_render_assigned": 2316},
                                        "p28r2": {"max_px": 191.036, "p95_px": 152.1509, "n_render_assigned": 1592}},
             "boats_and_lines_counts": M["unity"].get("boats_and_lines_counts")},
         "motion_gates_G_p28rec_default": {k: [vv.get("value"), vv.get("pass_")] for k, vv in g.items() if isinstance(vv, dict) and "pass_" in vv},
         "parts": {"motion": "metrics_motion.json（G_p28b まで）", "unity": "metrics_unity.json（P28R2 まで）", "recovery": "metrics_rec.json（採用の P28R2rec・G_p28rec）"}}
    with open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(G, f, ensure_ascii=False, indent=1, default=float)
    RR = {"schema": "GreatWave.Polish28.run/1", "made_local": M["made_local"], "timing": {"start": "2026-09-30T21:20", "end": R["timing"]["end"]},
          "parts": {"shape_round1": "Unity/Build/Polish/28/r1_rays/run.json・r1_faceswap/run.json・r1_backfirst/v4/run.json（Git 対象外）",
                    "shape_round2": "Unity/Build/Polish/28/r2/run.json（Git 対象外）",
                    "motion": "run_motion.json", "unity": "run_unity.json", "recovery": "run_rec.json"},
          "tools": R["tools"], "reference_model": R["reference_model"]}
    with open(os.path.join(EV, "run.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(RR, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
