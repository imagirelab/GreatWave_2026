# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 6：数をまとめて metrics.json・run.json を書く（新しい計算・描画はしない）。

入力：Unity/Build/Polish/33r01/houdini/ の prep・key・claws・r_after・gpu_after・gpu_before・measure・setup と、前（仕上げ33 採用）の描画 r_fix02。
出力：<candidate>/evidence/metrics.json・run.json（候補の証拠。Docs/Evidence への配置は進行役が決める）
"""
import argparse
import glob
import json
import os
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import houdini_common as H  # noqa: E402
import pl33f_record as R33  # noqa: E402

B = REPO + "/Unity/Build/Polish/33r01/houdini"
BEFORE = REPO + "/Unity/Build/Polish/33/fix02/r_fix02"
CP1 = {"78": 2.772, "130": 1.968, "131": 1.814, "132_s12": 1.326, "72_s12_p95": 1.558}
R26 = {"78": 1.641, "130": 1.953, "131": 1.798, "132_s12": 1.574, "72_s12_p95": 1.723}


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=B + "/r_after")
    ap.add_argument("--out", default=B + "/candidate/evidence")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    g_after = R33.gates(a.run)
    g_before = R33.gates(BEFORE)
    gpu = {}
    for k in ("after", "before"):
        p = B + "/gpu_%s/gpu/pl33r01h_gpu_claws.json" % k
        if os.path.exists(p):
            r = jl(p)
            gpu[k] = {"state": r.get("state"), "device": r.get("device"), "timing_ms": {t["cond"]: {"on": round(t["medianOnMs"], 3), "off": round(t["medianOffMs"], 3),
                                                                                                    "claws_ms": round(t["heroMs"], 3)} for t in r["timing"]},
                      "method_ja": r.get("methodJa", "").replace("主役波", "爪の層")}
    dep = jl(B + "/claws/deform_report.json")
    bld = jl(B + "/key/build_report.json")
    prp = jl(B + "/prep/prep_report.json")
    mea = jl(B + "/measure/pl33r01h_measure.json") if os.path.exists(B + "/measure/pl33r01h_measure.json") else {}
    lay = jl(B + "/claws/ds33_claw_layout.json")
    gate_rows = {}
    for item, key in (("78", ("def", "78", "max_px")), ("130", ("def", "130", "max_px")), ("131", ("def", "131", "max_px"))):
        gate_rows[item] = {"after_claws": g_after["t28_claws"]["def"][item]["max_px"], "after_noclaws": g_after["t28_white"]["def"][item]["max_px"],
                           "before_claws": g_before["t28_claws"]["def"][item]["max_px"], "cp1": CP1[item], "r26": R26[item], "gate": 4.0}
    gate_rows["132_s12"] = {"after_claws": g_after["t28_claws"]["s12_132"], "after_noclaws": g_after["t28_white"]["s12_132"], "before_claws": g_before["t28_claws"]["s12_132"],
                            "cp1": CP1["132_s12"], "r26": R26["132_s12"], "gate": 4.0}
    gate_rows["72_s12_p95"] = {"after_claws": g_after["t28_claws"]["s12_72p95"], "after_noclaws": g_after["t28_white"]["s12_72p95"], "before_claws": g_before["t28_claws"]["s12_72p95"],
                               "cp1": CP1["72_s12_p95"], "r26": R26["72_s12_p95"], "gate": 4.0}
    for k, v in gate_rows.items():
        v["verdict"] = "合格（後退なし）" if v["after_claws"] <= v["gate"] and v["after_claws"] <= v["before_claws"] + 0.05 else (
            "合格（前より +%.3f px）" % (v["after_claws"] - v["before_claws"]) if v["after_claws"] <= v["gate"] else "不合格")
    raw = {"132_raw_max": {"after_claws": g_after["t28_claws"]["def"]["132"]["max_px"], "after_noclaws": g_after["t28_white"]["def"]["132"]["max_px"],
                           "before_claws": g_before["t28_claws"]["def"]["132"]["max_px"]},
           "72_raw_p95": {"after_claws": g_after["t28_claws"]["def"]["72"]["p95_px"], "after_noclaws": g_after["t28_white"]["def"]["72"]["p95_px"],
                          "before_claws": g_before["t28_claws"]["def"]["72"]["p95_px"]},
           "72_raw_max": {"after_claws": g_after["t28_claws"]["def"]["72"]["max_px"], "before_claws": g_before["t28_claws"]["def"]["72"]["max_px"]},
           "72_s24_p95": {"after_claws": g_after["t28_claws"]["s24_72p95"], "before_claws": g_before["t28_claws"]["s24_72p95"]}}
    m = {"number": "仕上げ33修正01（Houdini の変種）：立つ白い爪の指", "state_ja": "候補（進行役の評審の前）。HMD 実機の結果ではない。利用者は見ていない。",
         "gates_painting_view": gate_rows, "raw_detail_with_claws": raw,
         "eval23": {"after": g_after["eval23"], "before": g_before["eval23"]},
         "counts": {"fingers": dep.get("by_kind"), "fingers_total": sum(dep.get("by_kind", {}).values()), "webs_kept": (dep.get("webs") or {}).get("webs"),
                    "vertices_total": dep.get("vertices_total"), "triangles_total": dep.get("triangles_total"),
                    "finger_vertices": bld["points"], "finger_triangles": bld["triangles"],
                    "before_vertices": 95547, "before_triangles": 183240, "frames_bytes": dep.get("frames_bytes")},
         "gpu_claw_layer_ms": gpu,
         "motion": {"nan": dep.get("nan"), "jump_max_rel_root_m": dep.get("jump_max_rel_root_m"), "jumps_over_0p5m": dep.get("jumps_over_0p5m"),
                    "jumps_over_0p25m": dep.get("jumps_over_0p25m"), "jumps_top": dep.get("jumps_top"), "birth_frame_pct": dep.get("birth_frame_pct")},
         "houdini_vs_numpy": {"stand_spine_max_m": dep.get("err_stand_vs_houdini_m"), "radius_max_m": dep.get("err_radius_vs_houdini_m"),
                              "key_frame_vs_houdini_mesh_m": dep.get("err_key_frame_vs_houdini_mesh_m")},
         "prep": {k: prp[k] for k in ("A_star_pct", "H_pct_CS", "len3d_pct", "rmed_pct", "paint_width_ratio_pct_CS", "dropped_collapsed_tstar") if k in prp},
         "measure": {k: v for k, v in mea.items() if k != "rule_ja"}}
    json.dump(m, open(a.out + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    files = {}
    for p in [B + "/claws/ds33_claw_layout.json", B + "/claws/ds33_claw_frames_f32.bin", B + "/claws/ds33_claw_tris_i32.bin", B + "/claws/ds33_claw_tri_attr_u16.bin",
              B + "/claws/pl33r01h_vattr_f32.bin", B + "/key/key_tstar_mesh.npz", B + "/key/ramps.json", B + "/prep/fingers_tstar.json", B + "/prep/frames_spines.npz",
              B + "/pl33r01h_fingers.hiplc"] + sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl33r01/houdini_*.py")) + \
             sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33R01/houdini/*/*.cs")) + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/Polish33R01/houdini/Scenes/*.unity")):
        if os.path.exists(p):
            files[os.path.relpath(p, REPO).replace("\\", "/")] = {"sha256": H.sha256(p), "bytes": os.path.getsize(p)}
    run = {"commands": [
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_prep.py",
        "hython Tools/GWWaveGen/pl33r01/houdini_build.py --fingers Unity/Build/Polish/33r01/houdini/prep/fingers_tstar.json --hip Unity/Build/Polish/33r01/houdini/pl33r01h_fingers.hiplc --out Unity/Build/Polish/33r01/houdini/key --npts-scale 0.85",
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_deform.py",
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_unity.py --method GreatWave.Polish33R01H.EditorTools.PL33R01HSetup.BuildScenes --log setup",
        "bash Unity/Build/Polish/33r01/houdini/run_render.sh r_after views,tt,t28,full,video   （PL33R01HRender、-pl33r01hLook 1）",
        "houdini_unity.py … PL33R01HRender.Render -pl29Only gpu -pl29Gpu 1 -pl30GpuTarget claws（後：-pl33r01hLook 1、前：仕上げ33 の爪の並び -pl32Look 1 -pl33Look 1）",
        "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/33r01/houdini/r_after --kstar rec",
        "py -3.10 -B Tools/PaintingTruth/evaluate.py --render <r_after>/full/painting_t120_off.png --ids <r_after>/full/ids_<line|line_noclaws|noline|noline_noclaws>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir <r_after>/eval23/off_<…>",
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_measure.py --runs before=Unity/Build/Polish/33/fix02/r_fix02 after=Unity/Build/Polish/33r01/houdini/r_after --out Unity/Build/Polish/33r01/houdini/measure/pl33r01h_measure.json",
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_figs.py --after Unity/Build/Polish/33r01/houdini/r_after --out Unity/Build/Polish/33r01/houdini/candidate/evidence",
        "py -3.10 -B Tools/GWWaveGen/pl33r01/houdini_record.py"],
        "tools": {"houdini": bld.get("houdini"), "hython": "G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe", "unity": "6000.4.3f1",
                  "python": sys.version.split()[0]},
        "inputs": {"claws_src_layout_sha256": prp.get("src_layout_sha256"), "claws_src_frames_sha256": prp.get("src_frames_sha256"),
                   "claw_inventory": "Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"},
        "reference_reads_ja": "参照の彫刻の写真（利用者の指示 Q16 の例外 G:/research/reality scan/北斋参考）の 2 枚（左45.jpg・正面图.jpg）を画面で見ただけ（指が塊から立って先で巻く・分かれる作りを見た）。"
                              "画像・寸法・形・Exif はリポジトリと成果物に入れていない。参照モデルの OBJ、G:/research/爪形分析、G:/research/Wave Simulation は開いていない。生成器は OBJ を読まない（F13-1）。",
        "files": files}
    json.dump(run, open(a.out + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"gates": gate_rows, "raw": raw, "gpu": {k: v["timing_ms"] for k, v in gpu.items()}}, ensure_ascii=False)[:3000])


if __name__ == "__main__":
    main()
