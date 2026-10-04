# -*- coding: utf-8 -*-
"""美術の見本04 の組み立て（Q32）：run.json（道具・入力・出力・図の SHA-256、命令、描画の記録、関門）を Build/Polish/sample04/assemble/run.json に書く。
使い方：py -3.10 -B Tools/GWWaveGen/as04/asm4_record.py
"""
import glob
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import asm4_common as A  # noqa: E402

REPO = A.REPO


def git(*a):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def main():
    tools = sorted(glob.glob(HERE + "/asm4_*"))
    reused = [HERE + "/" + n for n in ("mat_unity.ps1", "s4_common.py", "w4_common.py", "shape_common.py", "shape_eval.py", "as04_flat_smooth_params.txt")]
    reused += [REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as02/as02_gates.py", REPO + "/Tools/GWWaveGen/as02/back_common.py",
               REPO + "/Tools/GWWaveGen/as03/asm_sheets.py"]
    unity = [REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04_Flat_Smooth_Keypose.shader", REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04Common.cginc",
             REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs"]
    inputs = [A.UNION, A.UNION.replace(".json", ".bin"), A.WAVE4, A.WAVE4.replace(".json", ".bin"), A.HERO_SM04, A.HERO_SM04.replace(".json", ".bin"),
              A.ROWS04, A.GWB04, A.CLAWS04, A.P4 + "/shape/claws/ds33_claw_frames_f32.bin", A.P4 + "/shape/hero_pkg_AS04/ds27_keypose.json",
              A.P4 + "/shape/attr/a/s01a_hero_attr_v2_f32.bin", A.ROWS02C, A.GWB02C, A.HERO_SM02C, A.CLAWS03, A.RELIEF03]
    R = A.ASM + "/render/S04"
    renders = sorted(glob.glob(R + "/views/*.png") + glob.glob(R + "/crest/*.png") + glob.glob(R + "/tt/*.png") + glob.glob(R + "/full/*.png"))
    sheets = sorted(glob.glob(A.ASM + "/sheets/*.png"))
    rep = A.jl(R + "/as03asm_render_report.json")
    rc = A.jl(A.P4 + "/rules_check.json")
    out = {"schema": "GreatWave.AS04.assemble_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": "美術の見本04 の組み立て（Q32）。主役波 K*′ AS04 ＋ ④ の別の青い波 wave4 ＋ AS04 Flat Smooth ＋ 爪 35 本を Unity で t* に描き、測る規則を確かめた。形・材質は変えていない。",
           "commands": [
               "bash Tools/GWWaveGen/as04/asm4_render.sh S04 views,crest,tt,full,t28",
               "RB=.../sample04/assemble/render LG=.../sample04/assemble/logs BEFORE=.../sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh S04",
               "py -3.10 -B Tools/GWWaveGen/as04/asm4_rules.py（その後 asm4_rules.py G1 S11 で 2 つを測り直し）",
               "py -3.10 -B Tools/GWWaveGen/as04/asm4_sheets.py",
               "py -3.10 -B Tools/GWWaveGen/as04/asm4_record.py"],
           "tools": {A.rel(p): A.sha(p) for p in tools + reused},
           "unity_assets_used_unchanged": {A.rel(p): A.sha(p) for p in unity},
           "inputs": {A.rel(p): A.sha(p) for p in inputs},
           "before_after_renders_reused_ja": {"見本03 V2": "Unity/Build/Polish/sample03/fix01/render/V2（views・crest・tt）", "見本02": "Unity/Build/Polish/sample02/fix01/assemble/render/AS02C_A（views・tt）、波頭の回り台は Unity/Build/Polish/sample03/study/render/S3_AS02C_crest2",
                                              "hero_only": "Unity/Build/Polish/sample04/shape/render/A4（S9 の wave4 あり・なしの差）",
                                              "note_ja": "見本02・03 は描き直さず、前の描画をそのまま使った（同じ視点・同じカメラ・同じ時刻 t* 12 s）"},
           "render_report": {k: rep.get(k) for k in ("unity", "device", "graphicsApi", "utc", "scene", "sceneSha256", "as03Surf", "as03Shader", "as03Params", "as03HeroOutline",
                                                      "clawLayout", "as03Crown", "heroPackage", "heroMeshGwb", "heroMeshSha256", "protectedUnchanged", "changedFiles")},
           "renders_sha256": {A.rel(p): A.sha(p) for p in renders},
           "sheets_sha256": {A.rel(p): A.sha(p) for p in sheets},
           "rules_check": {"path": A.rel(A.P4 + "/rules_check.json"), "sha256": A.sha(A.P4 + "/rules_check.json"), "summary": rc.get("summary")},
           "gates_S04": {k: v["claws"] for k, v in rc["rules"]["G2"]["gates"].items()},
           "git": {"branch": git("rev-parse", "--abbrev-ref", "HEAD"), "head": git("rev-parse", "HEAD"),
                   "tracked_modified": [l for l in git("status", "--porcelain").splitlines() if not l.startswith("??")]},
           "references_ja": "参照モデルの OBJ と彫刻の写真は読んでいない。原画は比べの図と、測り（輪郭の真値・利用者の区域の位置）にだけ使った。",
           "no_git_ja": "git の add・commit・push はしていない。"}
    A.jdump(A.ASM + "/run.json", out)
    print(json.dumps({"tools": len(out["tools"]), "renders": len(renders), "sheets": len(sheets), "tracked_modified": out["git"]["tracked_modified"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
