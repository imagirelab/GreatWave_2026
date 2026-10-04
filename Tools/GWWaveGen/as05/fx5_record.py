# -*- coding: utf-8 -*-
"""美術の見本05 の直しの回 fix1（Q33）：道具・入力・出力・描画の記録の SHA-256 を Unity/Build/Polish/sample05/fix1/assemble/run.json に書く。
asm5_record.py（変えない）の写しで、置き場と道具の一覧を直しの回のものにした。
py -3.10 -B Tools/GWWaveGen/as05/fx5_record.py
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
FX = P5 + "/fix1"
ASM = FX + "/assemble"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def main():
    T5 = REPO + "/Tools/GWWaveGen/as05/"
    tools = sorted(glob.glob(T5 + "fx5_*"))
    used = [T5 + n for n in ("shapeB_build.py", "shapeB_mesh.py", "shapeB_common.py", "shapeB_quick.py", "shapeA_common.py", "shapeA_hero.py", "shapeA_mesh.py",
                             "shapeA_l3.py", "shapeA_labels.py", "shapeA_claws.py", "shapeA_rules.py", "asm5_rules.py", "asm5_render.sh", "asm5_unity.ps1",
                             "asm5_measure.py", "asm5_sheets.py", "asm5_b_edge.py", "mat_edge.py", "mat_common.py", "s5_targets.py", "as05_flat_smooth_params.txt")]
    used += [REPO + "/Unity/Assets/GreatWave/ArtSample05/Shaders/AS05_Flat_Smooth_Keypose.shader", REPO + "/Unity/Assets/GreatWave/ArtSample05/Shaders/AS05Common.cginc",
             REPO + "/Unity/Assets/GreatWave/ArtSample05/Editor/AS05ABoatRender.cs", REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs",
             REPO + "/Tools/GWWaveGen/as04/asm4_rules.py", REPO + "/Tools/GWWaveGen/as04/asm4_common.py", REPO + "/Tools/GWWaveGen/as04/w4_merge.py",
             REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as02/back_measure.py"]
    inputs = [P5 + "/shapeB/final/design_AS05B.json", P5 + "/shapeA/hero/design_AS05A.json", P + "/sample04/fix1/shape/final/cand/kstarAS04F_a45_rows.npz",
              P + "/sample04/wave4/mesh_fix1/wave4.json", P5 + "/study/targets.json", P5 + "/rules_check_A_before_fix.json", P5 + "/rules_check_B_before_fix.json"]
    outs = [FX + "/B/final/design_AS05B_fix1.json", FX + "/B/final/cand/kstarAS05B_a45_rows.npz", FX + "/B/final/cand/kstarAS05B_a45_build_log.json",
            FX + "/B/union/union.json", FX + "/B/union/union.bin", FX + "/B/claws/ds33_claw_layout.json", FX + "/B/final/quick/quick.json",
            FX + "/A/design_AS05A_fix1.json", FX + "/A/hero/cand/kstarAS05A_a45_rows.npz", FX + "/A/mesh/union_AS05A.json", FX + "/A/mesh/union_AS05A.bin",
            FX + "/A/l3/layer3.json", FX + "/A/l3/layer3_build_report.json", FX + "/A/claws/ds33_claw_layout.json",
            ASM + "/A/mesh/union_AS05A_f1.json", ASM + "/A/mesh/union_AS05A_f1.bin", ASM + "/A/mesh/wave4_layer3.json",
            ASM + "/B/mesh/union_AS05B_f1.json", ASM + "/B/mesh/union_AS05B_f1.bin", ASM + "/B/mesh/union_AS05B_f1_edge_report.json",
            P5 + "/rules_check_A.json", P5 + "/rules_check_B.json"] + sorted(glob.glob(ASM + "/measure/*.json")) + sorted(glob.glob(ASM + "/sheets/*.png"))
    reports = {}
    for d in ("A9", "A9_ttnc", "B10", "B10_ttnc", "B10H"):
        p = ASM + "/render/%s/as03asm_render_report.json" % d
        if os.path.isfile(p):
            r = json.load(open(p, encoding="utf-8"))
            reports[d] = {k: r.get(k) for k in ("unity", "device", "graphicsApi", "utc", "as03Surf", "as03SurfSha256", "as03Shader", "as03Params", "as03ParamsSha256",
                                                "clawLayout", "heroPackage", "heroMeshGwb", "protectedUnchanged", "changedFiles", "secondsTotal")}
    run = {"schema": "GreatWave.AS05.fix1_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": ("美術の見本05 の直しの回 fix1（Q33）：形 B（B10）と形 A（A9）の否の規則と批評の直す点を直し、全部の視点を描き直して、規則を測り直した。"
                       "Unity 6000.4.3f1 の PC オフスクリーン描画で、HMD 実機ではない。Git には入れていない"),
           "commands": [
               "bash Tools/GWWaveGen/as05/fx5_B_pipeline.sh <fix1/B> <fix1/B/final/design_AS05B_fix1.json> full",
               "py -3.10 -B Tools/GWWaveGen/as05/fx5_b_edge.py <fix1/B/union/union.json> <fix1/assemble/B/mesh/union_AS05B_f1.json>",
               "py -3.10 -B Tools/GWWaveGen/as05/fx5_A_run.py <fix1/A/design_AS05A_fix1.json> full",
               "py -3.10 -B Tools/GWWaveGen/as05/mat_edge.py --mesh <fix1/A/mesh/union_AS05A.json> --out <fix1/assemble/A/mesh/union_AS05A_f1.json> --hero-verts 314400 --claws <fix1/A/claws/ds33_claw_layout.json>",
               "py -3.10 -B Tools/GWWaveGen/as04/w4_merge.py <wave4 fix1> <fix1/A/l3/layer3.json> <fix1/assemble/A/mesh/wave4_layer3.json>",
               "TT_CLAWS=1 bash Tools/GWWaveGen/as05/fx5_render.sh BF B10 views,crest,tt,full,t28 <union_AS05B_f1.json>（TT_CLAWS=0 で B10_ttnc tt、主役波だけ B10H views,full,t28）",
               "TT_CLAWS=1 bash Tools/GWWaveGen/as05/fx5_render.sh AF A9 views,crest,tt,full,t28 <union_AS05A_f1.json>（TT_CLAWS=0 で A9_ttnc tt）",
               "bash Unity/Build/Polish/sample05/fix1/assemble/run_measure_chain.sh（shapeB_quick → as02_asm_eval B10・A9 → s5_targets measure）",
               "bash Unity/Build/Polish/sample05/fix1/assemble/run_measure_chain2.sh（asm5_measure の T5・T6）",
               "py -3.10 -B Tools/GWWaveGen/as05/fx5_rules.py B（と A）→ Unity/Build/Polish/sample05/rules_check_B.json・rules_check_A.json（前の版は *_before_fix.json）",
               "py -3.10 -B Tools/GWWaveGen/as05/fx5_sheets.py（と rules）"],
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
