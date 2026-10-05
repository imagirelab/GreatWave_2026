# -*- coding: utf-8 -*-
"""美術の見本06 の組み立て（Q34）：道具・入力・出力の SHA-256 を Build/Polish/sample06/assemble/run.json へ書く。
py -3.10 -B Tools/GWWaveGen/as06/asm6_record.py
"""
import glob
import hashlib
import json
import os
import platform
import sys
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
PA = P + "/sample06/assemble"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as06/asm6_*"))
    called = [REPO + "/Tools/GWWaveGen/as06/" + x for x in ("rows_rules.py", "lobes_rules.py", "rows_clay.py", "lobes_stretch.py")] + \
             [REPO + "/Tools/GWWaveGen/as05/" + x for x in ("asm5_measure.py", "s5_targets.py", "as05_deliver.py", "as05_flat_smooth_params.txt")] + \
             [REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as04/shape_claws.py", REPO + "/Tools/GWWaveGen/as04/asm4_rules.py",
              REPO + "/Tools/GWWaveGen/as04/asm4_common.py", REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs",
              REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs"]
    inputs = [P + "/sample06/rows/mesh/union_AS06R_d_f1.json", P + "/sample06/rows/mesh/union_AS06R_d_f1.bin",
              P + "/sample06/rows/final_d/mesh/hero_smooth_as06r.json", P + "/sample06/rows/final_d/final/cand/kstarAS06R_a45_rows.npz",
              P + "/sample06/rows/final_d/final/cand/kstarAS06R_a45.gwb", P + "/sample06/rows/final_d/claws/ds33_claw_layout.json",
              P + "/sample06/rows/measure/quick_R8/row_labels.npy", P + "/sample06/rows/design_R8.json",
              P + "/sample06/lobes/assemble2/mesh/union_AS06L.json", P + "/sample06/lobes/assemble2/mesh/union_AS06L.bin",
              P + "/sample06/lobes/assemble2/mesh/hero_AS06L_edge.json", P + "/sample06/lobes/final2/mesh/hero_smooth_as06l.json",
              P + "/sample06/lobes/final2/cand/kstarAS06L_a45_rows.npz", P + "/sample06/lobes/final2/cand/kstarAS06L_a45.gwb",
              P + "/sample06/lobes/final2/cand/kstarAS06L_a45_labels.npy", P + "/sample06/lobes/final2/claws/ds33_claw_layout.json",
              REPO + "/Tools/GWWaveGen/as06/lobes_design_LB2.json",
              P + "/sample04/wave4/mesh_fix1/wave4.json", P + "/sample04/wave4/mesh_fix1/wave4.bin", P + "/sample04/wave4/mesh_fix1/wave4_grid.npz",
              P + "/sample05/fix1/assemble/B/mesh/union_AS05B_f1.json", P + "/sample05/rules_check_B.json", P + "/sample05/study/targets.json"]
    outs = [P + "/sample06/rules_check_rows.json", P + "/sample06/rules_check_lobes.json", PA + "/check/asm6_check.json", PA + "/record_ja.md",
            PA + "/lobes/claws/ds33_claw_layout.json", PA + "/lobes/claws/ds33_claw_frames_f32.bin"]
    outs += sorted(glob.glob(PA + "/measure/*.json")) + sorted(glob.glob(PA + "/sheets/*.png"))
    outs += sorted(glob.glob(PA + "/render/*/as03asm_render_report.json")) + sorted(glob.glob(PA + "/render/*/as06asm_boat_1.json"))
    run = {"schema": "GreatWave.AS06.asm6_run/1", "date": time.strftime("%Y-%m-%d %H:%M"), "host": platform.node(), "python": sys.version.split()[0],
           "unity": "6000.4.3f1（PC オフスクリーン、batchmode。HMD 実機ではない）",
           "tools_new": {rel(p): sha(p) for p in tools}, "tools_called_unchanged": {rel(p): sha(p) for p in called if os.path.isfile(p)},
           "inputs": {rel(p): sha(p) for p in inputs if os.path.isfile(p)},
           "outputs": {rel(p): sha(p) for p in outs if os.path.isfile(p)},
           "renders": {os.path.basename(d): len(glob.glob(d + "/**/*.png", recursive=True)) for d in sorted(glob.glob(PA + "/render/*")) if os.path.isdir(d)},
           "not_read_ja": "参照モデルの OBJ と彫刻の写真は開いていない。見本01〜05 と採用のファイル・Unity の資産は変えていない（描画の記録 protectedUnchanged=True）。新しい Unity の資産は作っていない"}
    json.dump(run, open(PA + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("outputs", len(run["outputs"]), "renders", run["renders"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
