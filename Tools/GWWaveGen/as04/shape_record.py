# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：記録 run.json（道具・入力・出力・図の SHA-256、使った命令、測りの数、守ったこと）を書く。py -3.10 -B shape_record.py"""
import glob
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402

SH = S.OUT
R = S.REPO
TOOLS = ["shape_common.py", "shape_ops.py", "shape_build.py", "shape_limit.py", "shape_eval.py", "shape_rubric_diff.py", "shape_mesh.py", "shape_claws.py",
         "shape_clay.py", "shape_union_check.py", "shape_sheets.py", "shape_record.py", "shape_render.sh", "shape_pipeline.sh"]


def rel(p):
    return p.replace("\\", "/").replace(R + "/", "")


def sh(p):
    return S.sha(p) if os.path.isfile(p) else None


def main():
    ev = json.load(open(SH + "/final/eval_AS04.json", encoding="utf-8"))
    g = json.load(open(SH + "/render/measure/gates_A4/sweep_gates.json", encoding="utf-8"))
    un = json.load(open(SH + "/final/union_wave4_check.json", encoding="utf-8"))
    rd = json.load(open(SH + "/final/rubric_diff.json", encoding="utf-8"))
    cl = json.load(open(SH + "/claws/ds33_claw_layout.json", encoding="utf-8"))["as04_shape"]
    mesh = json.load(open(SH + "/mesh/hero_smooth_as04_report.json", encoding="utf-8"))
    rep = json.load(open(SH + "/render/A4/as03asm_render_report.json", encoding="utf-8"))
    bm = json.load(open(SH + "/final/eval_AS04_back_measure.json", encoding="utf-8"))["summary"]
    try:
        gst = subprocess.run(["git", "-C", R, "status", "--porcelain"], capture_output=True, text=True, encoding="utf-8").stdout
    except Exception:  # noqa
        gst = "?"
    out = {
        "schema": "GreatWave.AS04.shape_run/1",
        "date": "2026-10-04",
        "task_ja": "美術の見本04（Q32）の形づくり：主役波 K*′ AS04（t*）。計画 (a)(c)(d)(e) と (b) の主役波の部分。",
        "tools": {t: {"path": "Tools/GWWaveGen/as04/" + t, "sha256": sh(R + "/Tools/GWWaveGen/as04/" + t)} for t in TOOLS},
        "inputs": {
            "base_rows_AS02C": {"path": rel(S.BASE_ROWS), "sha256": S.sha(S.BASE_ROWS)},
            "plan_s4": {"path": rel(S.PLAN), "sha256": S.sha(S.PLAN)},
            "white_mask_sample03_v2": {"path": "Unity/Build/Polish/sample03/shared/white_mask_f32.bin", "sha256": sh(R + "/Unity/Build/Polish/sample03/shared/white_mask_f32.bin")},
            "claws35_sample03": {"path": "Unity/Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json", "sha256": sh(R + "/Unity/Build/Polish/sample03/assemble/claws35/ds33_claw_layout.json")},
            "src_hero_pkg": "Unity/Build/Polish/32/white/hero_pkg（as02_asm_pkg.py で最後の層だけを AS04 に置き換えた写し）",
            "material": {"shader": "Unity/Assets/GreatWave/ArtSample04/Shaders/AS04_Flat_Smooth_Keypose.shader", "sha256": sh(R + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04_Flat_Smooth_Keypose.shader"),
                         "params": "Tools/GWWaveGen/as04/as04_flat_smooth_params.txt", "params_sha256": sh(R + "/Tools/GWWaveGen/as04/as04_flat_smooth_params.txt")},
            "wave4_for_union_check_only": {"path": rel(un["wave4_mesh"]), "bin_sha256": un["wave4_sha256"]},
        },
        "outputs": {
            "design": {"path": rel(SH + "/final/design_AS04.json"), "sha256": sh(SH + "/final/design_AS04.json")},
            "rows": {"path": rel(SH + "/final/cand/kstarAS04_a45_rows.npz"), "sha256": sh(SH + "/final/cand/kstarAS04_a45_rows.npz")},
            "gwb": {"path": rel(SH + "/final/cand/kstarAS04_a45.gwb"), "sha256": sh(SH + "/final/cand/kstarAS04_a45.gwb")},
            "obj": {"path": rel(SH + "/final/cand/kstarAS04_a45.obj"), "sha256": sh(SH + "/final/cand/kstarAS04_a45.obj")},
            "meta": {"path": rel(SH + "/final/cand/kstarAS04_a45_meta.json"), "sha256": sh(SH + "/final/cand/kstarAS04_a45_meta.json")},
            "hero_pkg": {"path": rel(SH + "/hero_pkg_AS04"), "keypose_sha256": sh(SH + "/hero_pkg_AS04/ds27_keypose.json")},
            "attr_pl29": sh(SH + "/attr/pl29/pl29_hero_attr_f32.bin"), "attr_param": sh(SH + "/attr/param/s01_param_f32.bin"), "attr_s01a_v2": sh(SH + "/attr/a/s01a_hero_attr_v2_f32.bin"),
            "white_mask": {"path": rel(SH + "/mesh/white_mask_as04_f32.bin"), "sha256": sh(SH + "/mesh/white_mask_as04_f32.bin")},
            "static_mesh": {"path": rel(SH + "/mesh/hero_smooth_as04.json"), "bin_sha256": mesh["mesh"]["sha256"], "vertices": mesh["mesh"]["vertices"], "displacement_m": mesh["displacement_m"]},
            "claws": {"path": rel(SH + "/claws/ds33_claw_layout.json"), "sha256": sh(SH + "/claws/ds33_claw_layout.json"), "moved": cl["moved_abs_m"]},
            "sheets": {os.path.basename(p): sh(p) for p in sorted(glob.glob(SH + "/shape_*.png"))},
        },
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/as04/shape_build.py Unity/Build/Polish/sample04/shape/final/cand/kstarAS04_a45 Unity/Build/Polish/sample04/shape/final/design_AS04.json",
            "bash Tools/GWWaveGen/as04/shape_pipeline.sh（測り・評価基準・属性 pl29→s01_param→s01a v2・包み as02_asm_pkg・静止のメッシュ shape_mesh・爪 shape_claws・Blender の粘土）",
            "bash Tools/GWWaveGen/as04/shape_render.sh A4 views,tt,full,t28,crest（Unity、AS04 Flat Smooth）",
            "CL=… HERO_PKG=… HERO_GWB=… A_ATTR=… SURF=… bash Tools/GWWaveGen/as04/shape_render.sh before_AS02C views,tt,crest（比べの前）",
            "RB=…/shape/render LG=…/shape/logs BEFORE=…/sample04/mat/render/final bash Tools/GWWaveGen/as02/as02_asm_eval.sh A4（関門・評価器 23）",
            "py -3.10 -B Tools/GWWaveGen/as04/shape_union_check.py …/sample04/wave4/mesh/wave4.json …/shape/final/union_wave4_check.json",
            "py -3.10 -B Tools/GWWaveGen/as04/shape_clay.py …/shape/clay/np_plain ・ --layers …/np_layers",
            "py -3.10 -B Tools/GWWaveGen/as04/shape_sheets.py ・ shape_record.py",
        ],
        "metrics": {
            "S8_bulge": ev["S8_bulge"],
            "gates_unity_A4": {k: {"after": v.get("after_claws"), "before_AS02C_material": v.get("before_claws"), "pass": v.get("pass_after")} for k, v in g["gates"].items()},
            "eval23_unity_A4": g.get("eval23"),
            "gate_proxy_numpy": ev["G2_gate_proxy"], "outline78_split_numpy": ev["G2_outline_split"],
            "union_with_wave4": {k: un[k] for k in un if k.startswith("outline78") or k.startswith("wave4_in_front") or k == "wave4_visible_px"},
            "union_crest_compare_by_c": un["crest_compare_by_c"],
            "S10_band_extent": ev["S10_band_extent"],
            "S11_layers": {k: {kk: vv for kk, vv in v.items() if kk != "front_edge_by_row"} for k, v in ev["S11_layers"].items()},
            "S4_back": bm,
            "rubric_diff": rd,
            "shape_checks": ev["shape_checks"],
        },
        "rules_kept_ja": [
            "参照モデルの OBJ と写真は読んでいない（形づくりの道具はどちらも開かない。数は調べ S の s4_plan.json だけ）。",
            "原画のカメラは測り（出っ張りの射線・輪郭の近い値・爪の置き直しの射線）にだけ使い、色は面へ写していない。",
            "見本01〜03 と採用の資産は変えていない（描画の記録 protectedUnchanged=%s）。Unity の新しい資産は作っていない（材質は調べ M の AS04 のまま）。" % rep.get("protectedUnchanged", rep.get("protected_unchanged")),
            "git の add・commit・push はしていない。",
        ],
        "git_status_porcelain": gst,
        "incidents_ja": [
            "Blender の粘土の描画（1 回目）に Unity の場所からの相対のパスを渡したため、Blender が C:/Unity/Build/Polish/sample04/shape/clay/ に 58 ファイル（63 MB）を書いた。"
            "G: の shape/clay へ写し、自分が作った C:/Unity/Build/Polish フォルダーだけを消した（C:/Unity/Build/ArtFirst は前からあり、触れていない）。以後は G: の絶対のパスを渡した。",
            "初めの版（18:20 ごろ、禁止域の押さえ shape_limit を通した版）は行ごとの押さえで折れと段ができたので使わず、shape/final/superseded_v1/ に残した。",
        ],
    }
    S.jdump(SH + "/run.json", out)
    print("SHAPE_RECORD_DONE", SH + "/run.json")


if __name__ == "__main__":
    main()
