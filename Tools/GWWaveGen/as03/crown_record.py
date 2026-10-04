# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1：記録（run.json）を書く。道具・入力・出力の SHA-256、頂点の数、関門、S1 の数との比べの要約。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_record.py
出力：Unity/Build/Polish/sample03/crown/b1_run.json（Git 対象外）
"""
import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402


def rel(p):
    return os.path.relpath(p, G.REPO).replace("\\", "/")


def main():
    tools = sorted(glob.glob(G.REPO + "/Tools/GWWaveGen/as03/crown_*.py"))
    outs = []
    for m in ("OUT", "IN"):
        for f in ("as03_crown.bin", "as03_crown.json", "as03_crown.obj", "as03_crown_layout.json", "as03_crown_report.json", "as03_crown_attr.npy"):
            p = os.path.join(G.OUT, m, f)
            if os.path.exists(p):
                outs.append(p)
    for f in ("white_mask_f32.bin", "white_mask.json", "white_mask_grid_f32.bin", "white_mask_band_f32.bin", "white_mask_params.json", "README.md"):
        p = os.path.join(G.SHARED, f)
        if os.path.exists(p):
            outs.append(p)
    sheets = sorted(glob.glob(G.OUT + "/sheets/*.png"))
    renders = sorted(glob.glob(G.OUT + "/render/OUT/*.png") + glob.glob(G.OUT + "/render/IN/*.png") + glob.glob(G.OUT + "/render/none/*.png"))
    rep = {m: G.jload(os.path.join(G.OUT, m, "as03_crown_report.json")) for m in ("OUT", "IN")}
    gates = {m: G.jload(os.path.join(G.OUT, "gates", m, "gates_%s.json" % m)) for m in ("OUT", "IN")}
    calib = G.jload(os.path.join(G.OUT, "gates", "calib", "gates_calib.json")) if os.path.exists(os.path.join(G.OUT, "gates", "calib", "gates_calib.json")) else None
    run = {
        "schema": "GreatWave.AS03.B1.run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
        "task_ja": "美術の見本03 の作り B1：波頭の立体の白い指の冠（OUT・IN）と白の垂れる縁（共有の白の印）、Unity 向けの書き出し、粘土の描画",
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/as03/crown_whitemask.py --ver v2",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_build.py --mode OUT --hands 28",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_build.py --mode IN --hands 46",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_gates.py --mode calib|IN|OUT",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_render.py --mode OUT|IN|none（Blender 5.2.2 headless、Workbench）",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_sheets.py",
            "py -3.10 -B Tools/GWWaveGen/as03/crown_record.py"],
        "tools": {rel(p): G.sha(p) for p in tools},
        "inputs": {rel(G.GWB): G.sha(G.GWB), rel(G.ATTR): G.sha(G.ATTR), rel(G.PARAM): G.sha(G.PARAM),
                   rel(G.HERO_PKG + "/ds27_keypose.json"): G.sha(G.HERO_PKG + "/ds27_keypose.json"),
                   rel(G.CLAWD + "/ds33_claw_layout.json"): G.sha(G.CLAWD + "/ds33_claw_layout.json"),
                   rel(G.CLAWD + "/ds33_claw_frames_f32.bin"): G.sha(G.CLAWD + "/ds33_claw_frames_f32.bin"),
                   rel(G.SPEC): G.sha(G.SPEC), rel(G.ROLES): G.sha(G.ROLES), rel(G.PCREST): G.sha(G.PCREST)},
        "outputs": {rel(p): G.sha(p) for p in outs},
        "sheets": {rel(p): G.sha(p) for p in sheets},
        "renders_count": len(renders),
        "vertices": {m: {"vertices": rep[m]["mesh"]["vertices"], "triangles": rep[m]["mesh"]["triangles"]} for m in rep},
        "counts": {m: rep[m]["measure"]["counts"] for m in rep},
        "gates_px": {m: gates[m]["gates_px"] for m in gates}, "gates_pass_le_4px": {m: gates[m]["pass_all_le_4px"] for m in gates},
        "gates_calibration": (calib or {}).get("calib"),
        "checks": {m: rep[m]["checks"] for m in rep},
        "in_constraint": rep["IN"].get("in_constraint"),
        "rules_kept_ja": [
            "原画の色を面へ写していない（Q28）。原画のカメラは、白の境の位置の数、IN の指の置き場所の制約、関門の測りにだけ使った",
            "参照モデルの OBJ・彫刻の写真は読んでいない（数は S1 の sculpture_spec.json から。F13-1）",
            "利用者の爪形分析のマスク・模型は読んでいない（利用者の爪は見本02 の 3D の爪のメッシュを使った）",
            "Unity は使っていない（unity.lock を取っていない）。見本01・02・採用のファイルは変えていない。git の add・commit・push はしていない",
            "重い出力は Git 対象外の Unity/Build/Polish/sample03/ の下"],
    }
    G.jdump(os.path.join(G.OUT, "b1_run.json"), run)
    print("RECORD_DONE", len(run["outputs"]), "outputs", len(run["sheets"]), "sheets")


if __name__ == "__main__":
    main()
