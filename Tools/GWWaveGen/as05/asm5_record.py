# -*- coding: utf-8 -*-
"""美術の見本05 の組み立て（Q33）：道具・入力・出力・描画の記録の SHA-256 を Unity/Build/Polish/sample05/assemble/run.json に書く。
py -3.10 -B Tools/GWWaveGen/as05/asm5_record.py
"""
import glob
import hashlib
import json
import os
import sys
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
P5 = P + "/sample05"
ASM = P5 + "/assemble"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    tools = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as05/asm5_*")) + [REPO + "/Tools/GWWaveGen/as05/" + n for n in (
        "mat_edge.py", "mat_common.py", "mat_measure.py", "as05_flat_smooth_params.txt", "s5_targets.py", "shapeA_rules.py")]
    used = [REPO + "/Unity/Assets/GreatWave/ArtSample05/Shaders/AS05_Flat_Smooth_Keypose.shader", REPO + "/Unity/Assets/GreatWave/ArtSample05/Shaders/AS05Common.cginc",
            REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs", REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs",
            REPO + "/Tools/GWWaveGen/as04/asm4_rules.py", REPO + "/Tools/GWWaveGen/as04/asm4_common.py", REPO + "/Tools/GWWaveGen/as04/w4_merge.py",
            REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as02/back_measure.py"]
    inputs = [P5 + "/shapeA/mesh/union_AS05A.json", P5 + "/shapeA/mesh/union_AS05A.bin", P5 + "/shapeB/union/union.json", P5 + "/shapeB/union/union.bin",
              P5 + "/shapeA/claws/ds33_claw_layout.json", P5 + "/shapeB/claws/ds33_claw_layout.json", P5 + "/shapeA/l3/layer3.json",
              P5 + "/shapeA/hero/cand/kstarAS05A_a45_rows.npz", P5 + "/shapeB/final/cand/kstarAS05B_a45_rows.npz",
              P + "/sample04/wave4/mesh_fix1/union.json", P + "/sample04/wave4/mesh_fix1/wave4.json", P5 + "/study/targets.json"]
    outs = [ASM + "/A/mesh/union_AS05A_m.json", ASM + "/A/mesh/union_AS05A_m.bin", ASM + "/A/mesh/union_AS05A_m_edge_report.json",
            ASM + "/B/mesh/union_AS05B_m.json", ASM + "/B/mesh/union_AS05B_m.bin", ASM + "/B/mesh/union_AS05B_m_edge_report.json",
            ASM + "/A/mesh/wave4_layer3.json", ASM + "/A/eval_AS05A_back_measure.json",
            P5 + "/rules_check_A.json", P5 + "/rules_check_B.json"] + sorted(glob.glob(ASM + "/measure/*.json")) + sorted(glob.glob(ASM + "/sheets/*.png"))
    reports = {}
    for d in ("A5", "A5_ttnc", "B5", "B5_ttnc", "S04_ttnc"):
        p = ASM + "/render/%s/as03asm_render_report.json" % d
        if os.path.isfile(p):
            r = json.load(open(p, encoding="utf-8"))
            reports[d] = {k: r.get(k) for k in ("unity", "device", "graphicsApi", "utc", "as03Surf", "as03SurfSha256", "as03Shader", "as03Params", "as03ParamsSha256",
                                                "clawLayout", "heroPackage", "heroMeshGwb", "protectedUnchanged", "changedFiles", "secondsTotal")}
    run = {"schema": "GreatWave.AS05.assemble_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": ("美術の見本05 の組み立て（Q33）：形 A・形 B に材質 AS05（T5 白い粒なし・T6 内の縁の白の書き換え）を当て、爪 35 本と一緒に Unity で t* に描いて、"
                       "規則を確かめた。Unity 6000.4.3f1 の PC オフスクリーン描画で、HMD 実機ではない。Git には入れていない"),
           "commands": [
               "py -3.10 -B Tools/GWWaveGen/as05/mat_edge.py --mesh <shapeA/mesh/union_AS05A.json> --out <assemble/A/mesh/union_AS05A_m.json> --hero-verts 314400 --claws <shapeA/claws>",
               "py -3.10 -B Tools/GWWaveGen/as05/mat_edge.py --mesh <shapeB/union/union.json> --out <assemble/B/mesh/union_AS05B_m.json> --hero-verts 314400 --claws <shapeB/claws>",
               "TT_CLAWS=1 bash Tools/GWWaveGen/as05/asm5_render.sh A A5 views,crest,tt,full,t28 <union_AS05A_m.json>（TT_CLAWS=0 で A5_ttnc tt）",
               "TT_CLAWS=1 bash Tools/GWWaveGen/as05/asm5_render.sh B B5 views,crest,tt,full,t28 <union_AS05B_m.json>（TT_CLAWS=0 で B5_ttnc tt）",
               "TT_CLAWS=0 bash Tools/GWWaveGen/as05/asm5_render.sh S04 S04_ttnc tt（見本04 の回り台の爪なし、前の比べ）",
               "RB=<assemble/render> LG=<assemble/logs> BEFORE=<sample02/fix01/assemble/render/AS02C_A> bash Tools/GWWaveGen/as02/as02_asm_eval.sh A5（と B5。1 つずつ）",
               "py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py <wave4 fix1> <shapeA/l3/layer3.json> <assemble/A/mesh/wave4_layer3.json>",
               "py -3.10 -B Tools/GWWaveGen/as02/back_measure.py <assemble/A/eval_AS05A_back_measure.json> AS02C=<rows> AS04=<AS05A rows>",
               "py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure <assemble/measure/cand_A.json|cand_B.json> <assemble/measure/targets_A5.json|targets_B5.json>",
               "py -3.10 -B Tools/GWWaveGen/as05/asm5_measure.py --render <描画> --mesh <静止のメッシュ> --out <assemble/measure/t5t6_<名前>_v|ct.json> --parts views,t6|crest,tt",
               "py -3.10 -B Tools/GWWaveGen/as05/asm5_rules.py A（と B）→ Unity/Build/Polish/sample05/rules_check_A.json・rules_check_B.json",
               "py -3.10 -B Tools/GWWaveGen/as05/asm5_sheets.py（と rules）"],
           "tools_sha256": {rel(p): sha(p) for p in tools if os.path.isfile(p)},
           "used_unchanged_sha256": {rel(p): sha(p) for p in used if os.path.isfile(p)},
           "inputs_sha256": {rel(p): sha(p) for p in inputs if os.path.isfile(p)},
           "outputs_sha256": {rel(p): sha(p) for p in outs if os.path.isfile(p)},
           "render_reports": reports,
           "reference_model_read": False, "photos_read": False,
           "git": "add・commit・push はしていない"}
    with open(ASM + "/run.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("書いた", ASM + "/run.json", len(run["outputs_sha256"]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
