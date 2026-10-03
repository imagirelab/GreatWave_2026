# -*- coding: utf-8 -*-
"""美術の見本02 爪の部：数（metrics.json）と、コマンド・入力・出力の SHA-256（run.json）を Build/Polish/sample02/claws/ へ書く（記録の部の材料）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_record.py
"""
import glob
import hashlib
import json
import os
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
B2 = REPO + "/Unity/Build/Polish/sample02/claws"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    std = jl(B2 + "/user_claw_standard.json")
    ref = {r: jl(B2 + "/ref/as02_ref_claw_placement%s.json" % r) for r in ("", "_r0.7", "_r1.0")}
    repA = jl(B2 + "/mesh/as02_claws_report.json")
    repB = jl(B2 + "/mesh_ref/as02_claws_report.json")
    vis = jl(B2 + "/work/visible_claw_px.json")
    gates = {k: jl(B2 + "/render/measure/gates_%s/sweep_gates.json" % k) for k in ("A_final", "B_ref_final")}

    def claw_rows(rep):
        rows = []
        for c in rep["claws"]:
            r = {"user_id": c["user_id"], "placed": c.get("placed", False), "why_not_ja": c.get("why_not_ja"), "duplicate_of": c.get("duplicate_of"),
                 "registration_ncc": c["registration"]["ncc_after_ecc"], "registration_source": c["registration"]["source"],
                 "pl32_status": c.get("pl32_status"), "pl32_best_id": c.get("pl32_best_id")}
            if c.get("placed"):
                r.update({k: c.get(k) for k in ("iou_face", "iou_painting", "iou_painting_visible", "iou_face_placed_own_axis", "visible_fraction",
                                                "alpha_deg", "beta_deg", "stretch", "root_dir_vs_normal_deg", "overall_dir_vs_normal_deg",
                                                "curl_root_to_tip_deg", "tip_down_component", "length_3d_m", "width_max_m", "thick_max_m",
                                                "penetration_max_m", "nearest_root_m", "nearest_root_over_length", "fan_to_nearest_deg",
                                                "painting_overlap_fraction", "standard_fails_ja")})
                r["root_surface"] = c["root_hit"]["surface"]
                r["standard"] = c.get("standard")
            rows.append(r)
        return rows

    def fails(rep):
        out = []
        for c in rep["claws"]:
            if c.get("placed") and (c.get("standard_fails_ja") or c.get("iou_painting", 1) < 0.85 or c.get("penetration_max_m", 0) > 0.1
                                    or c.get("visible_fraction", 1) < 0.75):
                why = list(c.get("standard_fails_ja") or [])
                if c.get("iou_painting", 1) < 0.85:
                    why.append("原画視点の IoU %.3f < 0.85" % c["iou_painting"])
                if c.get("penetration_max_m", 0) > 0.1:
                    why.append("面へ %.2f m 潜る" % c["penetration_max_m"])
                if c.get("visible_fraction", 1) < 0.75:
                    why.append("原画視点で主役波・海に %.0f%% 隠れる" % (100 * (1 - c["visible_fraction"])))
                out.append({"user_id": c["user_id"], "why_ja": why})
        return out
    m = {
        "schema": "GreatWave.AS02.claws100_metrics/1",
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "state_ja": "美術の見本02 爪の部（Q30-2）。t* = 12 s の静止。PC のオフスクリーン描画（Unity 6000.4.3f1）と numpy。HMD 実機ではない。利用者は見ていない。",
        "user_claw_standard": {k: {kk: v[kk] for kk in ("bbox_m", "spine_from_BL_to_top", "width_over_thickness_median_mid60", "section_fill_median_mid60",
                                                        "taper_top_end", "tip_top", "heel", "spine_curvature_x_wmax", "outline_lumps_hysteresis")}
                               for k, v in std["models"].items()},
        "reference_model_placement": {r or "_r0.42": {k: v for k, v in d.items() if isinstance(v, dict) and "p50" in v} | {"claw_count": d["claw_count"]}
                                      for r, d in ref.items()},
        "variant_A_paint": {"summary": {k: v for k, v in repA["summary"].items() if k not in ("reference",)}, "fails": fails(repA)},
        "variant_B_ref": {"summary": {k: v for k, v in repB["summary"].items() if k not in ("reference",)}, "fails": fails(repB)},
        "visible_claw_pixels_per_view": vis,
        "painting_view_gates_and_eval23": {k: {"gates": v["gates"], "eval23": v["eval23"], "before_run": v["before_run"]} for k, v in gates.items()},
        "claws_A": claw_rows(repA),
        "claws_B": claw_rows(repB),
    }
    json.dump(m, open(B2 + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as02/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/as02/*.sh")
                   + glob.glob(REPO + "/Tools/GWWaveGen/as02/*.ps1") + glob.glob(REPO + "/Tools/GWWaveGen/as02/*.txt"))
    outs = sorted(glob.glob(B2 + "/mesh/*") + glob.glob(B2 + "/mesh_ref/*") + glob.glob(B2 + "/figs/*.png") + glob.glob(B2 + "/ref/*.json")
                  + [B2 + "/user_claw_standard.json", B2 + "/metrics.json"])
    renders = sorted(glob.glob(B2 + "/render/A_final/views/*.png") + glob.glob(B2 + "/render/A_final/tt/*.png")
                     + glob.glob(B2 + "/render/B_ref_final/views/*.png") + glob.glob(B2 + "/render/B_ref_final/tt/*.png"))
    run = {
        "schema": "GreatWave.AS02.claws100_run/1",
        "utc": m["utc"],
        "commands_ja": [
            "py -3.10 -B Tools/GWWaveGen/as02/as02_user_claw_standard.py",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_ref_claws.py cache → measure（AS02_R_OPEN=0.42 / 0.7 / 1.0）→ delete",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_claws100.py --mode paint   （案 A、Build/Polish/sample02/claws/mesh）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_claws100.py --mode ref --out …/mesh_ref   （案 B）",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_gallery.py --cols 2",
            "bash Tools/GWWaveGen/as02/as02_run_render.sh A_final views,tt,full,t28 ; … B_ref_final views,tt,full,t28 Build/Polish/sample02/claws/mesh_ref/ds33_claw_layout.json",
            "bash Tools/GWWaveGen/as02/as02_run_eval.sh A_final B_ref_final",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_sheets.py",
            "py -3.10 -B Tools/GWWaveGen/as02/as02_record.py"],
        "inputs": {
            "user_claw_models": {p: sha(p) for p in ("G:/research/model/claw_mid.obj", "G:/research/model/claw_low.obj")},
            "user_claw_analysis_note_ja": "G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3/clawNNN/{fill_mask.png,centerline_raw.csv}。SHA-256 は "
                                          "Build/Design/32/list+ids/ds32_user100_registration.json の user_files_sha256（設計32 で記録）",
            "registration": {rel(REPO + "/Unity/Build/Design/32/list+ids/ds32_user100_registration.json"): sha(REPO + "/Unity/Build/Design/32/list+ids/ds32_user100_registration.json"),
                             rel(REPO + "/Unity/Build/Polish/32/fix01/list/ds32_user100_correspondence_pl32f.json"): sha(REPO + "/Unity/Build/Polish/32/fix01/list/ds32_user100_correspondence_pl32f.json")},
            "hero_pkg": "Unity/Build/Polish/32/white/hero_pkg（K*′ P28R2rec、τ = 0）",
            "sea_near_tstar": {rel(REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb"): sha(REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb")},
            "reference_model": {"file": "G:/research/model/wave_repair_zbrush2.obj", "sha256": "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40",
                                "cache_log": rel(B2 + "/ref/as02_ref_cache_log.json"), "cache_deleted": not os.path.isdir(REPO + "/Unity/Build/Polish/sample02/_objcache")},
            "surface_material": "見本 A（見本01 の回 2：Tools/GWWaveGen/sample01/s01a_material_params_r1.txt、Build/Polish/sample01/texA/attr/s01a_hero_attr_v2_f32.bin）",
            "before": "Unity/Build/Polish/sample01/assemble/A2（見本01 の回 2 の見本 A の描画）",
        },
        "tools": {rel(p): sha(p) for p in tools},
        "outputs": {rel(p): sha(p) for p in outs if os.path.isfile(p)},
        "renders": {rel(p): sha(p) for p in renders},
        "unity_logs": sorted(rel(p) for p in glob.glob(B2 + "/logs/unity_as02_*final*.log")),
    }
    json.dump(run, open(B2 + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("AS02_RECORD_DONE", len(run["outputs"]), len(run["renders"]))


if __name__ == "__main__":
    main()
