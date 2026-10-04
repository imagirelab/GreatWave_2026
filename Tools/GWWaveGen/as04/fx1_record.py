# -*- coding: utf-8 -*-
"""美術の見本04 の直しの回 1（fix1）：run.json（道具・入力・出力・図の SHA-256、命令、描画の記録、関門、規則の前後）を
Build/Polish/sample04/fix1/run.json に書く。
使い方：AS04_FIX=fix1 py -3.10 -B Tools/GWWaveGen/as04/fx1_record.py
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
F = A.P4 + "/fix1"


def git(*a):
    r = subprocess.run(["git", "-C", REPO] + list(a), capture_output=True, text=True, encoding="utf-8")
    return r.stdout.strip()


def main():
    assert A.FIX == "fix1", "AS04_FIX=fix1 で呼ぶ"
    tools = [HERE + "/" + n for n in ("fx1_build.py", "fx1_mesh.py", "fx1_pipeline.sh", "fx1_record.py", "asm4_common.py", "asm4_rules.py", "asm4_sheets.py",
                                      "asm4_render.sh", "w4_render.sh", "w4_run_all.sh", "w4_build.py", "w4_merge.py", "w4_check.py", "shape_build.py", "shape_ops.py",
                                      "shape_common.py", "shape_eval.py", "shape_mesh.py", "shape_claws.py", "mat_unity.ps1")]
    tools += [REPO + "/Tools/GWWaveGen/as02/as02_asm_eval.sh", REPO + "/Tools/GWWaveGen/as02/as02_gates.py", REPO + "/Tools/GWWaveGen/as03/surf_relief.py"]
    unity_new = [REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04F_Flat_Smooth_Keypose.shader",
                 REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04FCommon.cginc"]
    unity_same = [REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04_Flat_Smooth_Keypose.shader",
                  REPO + "/Unity/Assets/GreatWave/ArtSample04/Shaders/AS04Common.cginc",
                  REPO + "/Unity/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs"]
    S = F + "/shape"
    inputs = [S + "/final/design_AS04F.json", A.ROWS04, A.GWB04, S + "/final/cand/kstarAS04F_a45_meta.json", A.HERO_SM04, A.HERO_SM04.replace(".json", ".bin"),
              S + "/mesh/white_mask_as04f_f32.bin", S + "/hero_pkg_AS04F/ds27_keypose.json", S + "/attr/a/s01a_hero_attr_v2_f32.bin",
              A.CLAWS04, S + "/claws/ds33_claw_frames_f32.bin", A.WAVE4, A.WAVE4.replace(".json", ".bin"), A.UNION, A.UNION.replace(".json", ".bin"),
              A.P4 + "/shape/final/cand/kstarAS04_a45_rows.npz", A.ROWS02C, A.HERO_SM02C, A.CLAWS03]
    R = A.ASM + "/render/" + A.RTAG
    renders = sorted(glob.glob(R + "/views/*.png") + glob.glob(R + "/crest/*.png") + glob.glob(R + "/tt/*.png") + glob.glob(R + "/full/*.png")
                     + glob.glob(R + "H/views/*.png"))
    sheets = sorted(glob.glob(A.ASM + "/sheets_fix1/*.png"))
    rep = A.jl(R + "/as03asm_render_report.json")
    rc = A.jl(A.P4 + "/rules_check.json")
    rb = A.jl(A.P4 + "/rules_check_before_fix.json")
    out = {"schema": "GreatWave.AS04.fix1_run/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "note_ja": ("美術の見本04 の直しの回 1（fix1）：落ちた規則（S11）と批評の直すべき所を順に直し、全部の視点を描き直し、測る規則を測り直した。"
                       "主役波 K*′ AS04F（②③ の間の湾）、白の印（白い刃・歯の列）、白い点（AS04F シェーダー）、wave4 の作り直し、関門 78 の記録の直し。"),
           "commands": [
               "bash Tools/GWWaveGen/as04/fx1_pipeline.sh（fx1_build → shape_eval → rubric → pl29 → s01_param → s01a_attr → as02_asm_pkg → fx1_mesh → shape_claws）",
               "AS04_SHD=GreatWave/ArtSample04/AS04FFlatSmoothKeypose W4_HERO_PKG=… W4_HERO_GWB=… W4_ATTR=… W4_CLAWS=… AS04_OL=1 bash Tools/GWWaveGen/as04/w4_run_all.sh fix1 <AS04F の行> <AS04F の静止のメッシュ> <A4>",
               "py -3.10 -B Tools/GWWaveGen/as04/fx1_mesh.py …（歯の列のならしを足して作り直し）→ w4_merge.py（union を作り直し）",
               "AS04_SHD=… HERO_PKG=… HERO_GWB=… A_ATTR=… CL=… AS04_OL=1 bash Tools/GWWaveGen/as04/asm4_render.sh FX1 views,crest,tt,full,t28 wave4/mesh_fix1/union.json",
               "同じ env で asm4_render.sh FX1H views fix1/shape/mesh/hero_smooth_as04f.json（主役波だけ。S9 の差）",
               "RB=…/assemble/render LG=…/assemble/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh FX1",
               "cp rules_check.json rules_check_before_fix.json; AS04_FIX=fix1 py -3.10 -B Tools/GWWaveGen/as04/asm4_rules.py",
               "AS04_FIX=fix1 py -3.10 -B Tools/GWWaveGen/as04/asm4_sheets.py",
               "AS04_FIX=fix1 py -3.10 -B Tools/GWWaveGen/as04/fx1_record.py"],
           "first_render_v1_ja": ("白い点の第 1 版（歪みの大きい所は点を出さない）で描いた FX1 は assemble/render/FX1v1・FX1Hv1（関門 gates_FX1v1）へ移した。"
                                  "黄色の線の中の白い点が 0 になり、原画の 62 の点と違ったので、第 2 版（歪みの大きい所はワールドの格子の点）で描き直したのが FX1。"),
           "tools": {A.rel(p): A.sha(p) for p in tools if os.path.isfile(p)},
           "unity_assets_new": {A.rel(p): A.sha(p) for p in unity_new},
           "unity_assets_used_unchanged": {A.rel(p): A.sha(p) for p in unity_same},
           "inputs": {A.rel(p): A.sha(p) for p in inputs},
           "render_report": {k: rep.get(k) for k in ("unity", "device", "graphicsApi", "utc", "scene", "sceneSha256", "as03Surf", "as03Shader", "as03Params", "as03HeroOutline",
                                                      "clawLayout", "as03Crown", "heroPackage", "heroMeshGwb", "heroMeshSha256", "protectedUnchanged", "changedFiles")},
           "renders_sha256": {A.rel(p): A.sha(p) for p in renders},
           "sheets_sha256": {A.rel(p): A.sha(p) for p in sheets},
           "rules_check": {"path": A.rel(A.P4 + "/rules_check.json"), "sha256": A.sha(A.P4 + "/rules_check.json"), "summary": rc.get("summary"),
                           "before_fix": {"path": A.rel(A.P4 + "/rules_check_before_fix.json"), "sha256": A.sha(A.P4 + "/rules_check_before_fix.json"),
                                          "summary": rb.get("summary")}},
           "gates_FX1": {k: v["claws"] for k, v in rc["rules"]["G2"]["gates"].items()},
           "git": {"branch": git("rev-parse", "--abbrev-ref", "HEAD"), "head": git("rev-parse", "HEAD"),
                   "tracked_modified": [l for l in git("status", "--porcelain").splitlines() if not l.startswith("??")]},
           "references_ja": "参照モデルの OBJ と彫刻の写真は読んでいない。原画は比べの図と、測り（輪郭の真値・利用者の区域の位置）にだけ使った。",
           "no_git_ja": "git の add・commit・push はしていない。"}
    A.jdump(F + "/run.json", out)
    print(json.dumps({"tools": len(out["tools"]), "renders": len(renders), "sheets": len(sheets), "tracked_modified": out["git"]["tracked_modified"]}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
