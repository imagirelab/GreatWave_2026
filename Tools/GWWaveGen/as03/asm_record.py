# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：実行の記録（コマンド・道具の版・入出力の SHA-256・出来事）を Unity/Build/Polish/sample03/assemble/asm_run.json に書く（読み取りのみ）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/asm_record.py
"""
import glob
import hashlib
import json
import os
import platform
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
U = REPO + "/Unity"
S3 = U + "/Build/Polish/sample03"
ASM = S3 + "/assemble"
T = REPO + "/Tools/GWWaveGen/as03"


def sha(p):
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    inputs = [S3 + "/surface/mesh/hero_relief_b1v2c.json", S3 + "/surface/mesh/hero_relief_b1v2c.bin",
              S3 + "/crown/OUT/as03_crown.json", S3 + "/crown/OUT/as03_crown.bin", S3 + "/crown/OUT/as03_crown_layout.json", S3 + "/crown/OUT/as03_crown_report.json",
              S3 + "/crown/IN/as03_crown.json", S3 + "/crown/IN/as03_crown.bin", S3 + "/crown/IN/as03_crown_layout.json", S3 + "/crown/IN/as03_crown_report.json",
              S3 + "/shared/white_mask.json", S3 + "/shared/white_mask_f32.bin", S3 + "/shared/white_mask_params.json", S3 + "/shared/white_mask_band_f32.bin",
              S3 + "/study/sculpture_spec.json", S3 + "/study/claw_roles.json",
              U + "/Build/Polish/sample02/fix01/assemble/claws/mesh/ds33_claw_layout.json", U + "/Build/Polish/sample02/fix01/assemble/claws/mesh/ds33_claw_frames_f32.bin",
              U + "/Build/Polish/sample02/fix01/assemble/claws/mesh/as02_claws_report.json",
              U + "/Build/Polish/sample02/fix01/assemble/hero_pkg_AS02C/ds27_keypose.json", U + "/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb",
              U + "/Build/Polish/sample02/fix01/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin",
              REPO + "/Tools/GWWaveGen/pl30/pl30_sea_params.txt", T + "/surf_flat_params.txt", T + "/surf_sculpt_params.txt",
              U + "/Assets/GreatWave/ArtSample03/Shaders/AS03Common.cginc", U + "/Assets/GreatWave/ArtSample03/Shaders/AS03_Flat_Keypose.shader",
              U + "/Assets/GreatWave/ArtSample03/Shaders/AS03_Sculpt_Keypose.shader", U + "/Assets/GreatWave/ArtSample03/Scripts/AS03StaticMesh.cs",
              U + "/Assets/GreatWave/ArtSample03/Editor/AS03SurfRender.cs"]
    tools = sorted(glob.glob(T + "/asm_*")) + [U + "/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs", U + "/Assets/GreatWave/ArtSample03/Editor/AS03AsmRender.cs.meta"]
    outs = {}
    for v in ("V1", "V2", "V3", "V1_cmp", "V1_ids", "V3_ids"):
        d = ASM + "/render/" + v
        rr = json.load(open(d + "/as03asm_render_report.json", encoding="utf-8"))
        outs[v] = {"report": {"path": d + "/as03asm_render_report.json", "sha256": sha(d + "/as03asm_render_report.json")},
                   "images": len(rr["images"]), "crown_masks": len(rr.get("as03CrownMaskFiles") or []), "protectedUnchanged": rr["protectedUnchanged"],
                   "secondsTotal": rr["secondsTotal"], "unity": rr["unity"], "device": rr["device"], "graphicsApi": rr["graphicsApi"], "colorSpace": rr["colorSpace"],
                   "gates": {"path": ASM + "/render/measure/gates_%s/sweep_gates.json" % v, "sha256": sha(ASM + "/render/measure/gates_%s/sweep_gates.json" % v)} if v in ("V1", "V2", "V3") else None}
    sheets = sorted(glob.glob(ASM + "/sheets/*.png"))
    rec = {
        "schema": "GreatWave.AS03.asm_run/1", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "unity": "6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode、unity.lock で 1 つずつ）"},
        "commands_ja": [
            "py -3.10 -B Tools/GWWaveGen/as03/asm_claws35.py        # 面の内 25・近い海 10 の爪の並び（冠の役 48 本は根元へ潰す）",
            "py -3.10 -B Tools/GWWaveGen/as03/asm_make_render_cs.py  # AS03SurfRender.cs（B2）を写して AS03AsmRender.cs（冠の画・比べの視点）",
            "bash Tools/GWWaveGen/as03/asm_render.sh V1 OUT sculpt views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/asm_render.sh V2 OUT flat views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/asm_render.sh V3 IN sculpt views,crest,tt,full,t28",
            "bash Tools/GWWaveGen/as03/asm_render.sh V1_cmp OUT sculpt cmp -as03Cmp \"front:30:15:72:34;right45:-15:28:72:34;left45:75:28:72:34;back:210:18:72:34;top:30:85:95:40\"",
            "RB=…/sample03/assemble/render LG=…/sample03/assemble/logs BEFORE=…/sample02/fix01/assemble/render/AS02C_A bash Tools/GWWaveGen/as02/as02_asm_eval.sh V3 V1 V2",
            "bash Tools/GWWaveGen/as03/asm_render.sh V1_ids OUT sculpt views,crest,tt,ids   # 主役波の印（冠 ÷ 波の影の記録のため。V2 は V1 と形が同じ）",
            "bash Tools/GWWaveGen/as03/asm_render.sh V3_ids IN sculpt views,crest,tt,ids",
            "py -3.10 -B Tools/GWWaveGen/as03/asm_rules.py           # rules_check.json",
            "py -3.10 -B Tools/GWWaveGen/as03/asm_ref_copies.py make  # 利用者だけの図の写真の一時の写し（user_only/ref_asm）",
            "py -3.10 -B Tools/GWWaveGen/as03/asm_sheets.py all       # 並べ図と利用者だけの図",
            "py -3.10 -B Tools/GWWaveGen/as03/asm_record.py"],
        "compare_view_choice_ja": ("利用者だけの図の向きは、V1 を方位 −60〜+60°（15〜30° おき）・180±15°・210〜230°・真上で描いた試し（消した）を写真と目で並べて選んだ："
                                   "正面＝方位 30°（波の進む向き t は約 40°）、右45＝−15°（写真の『右45』は彫刻を右へ回した向きで、カメラは左へ回る）、左45＝75°、背＝210°、上＝30°・仰角 85°。"),
        "inputs_sha256": {p.replace(REPO + "/", ""): sha(p) for p in inputs},
        "tools_sha256": {p.replace(REPO + "/", ""): sha(p) for p in tools},
        "render_tool_used_for_renders_sha256": "2acb4942bd0160056ba601c2aef897a5229265f4e24ea288694b91a676eefc0c（描画の後に説明の文だけ直した。写しは assemble/AS03AsmRender_rendered_2acb4942.cs.txt）",
        "outputs": {"renders": outs, "rules_check": {"path": S3 + "/rules_check.json", "sha256": sha(S3 + "/rules_check.json")},
                    "sheets": {p.replace(REPO + "/", ""): sha(p) for p in sheets},
                    "claws35_layout_sha256": sha(ASM + "/claws35/ds33_claw_layout.json"), "claws35_frames_sha256": sha(ASM + "/claws35/ds33_claw_frames_f32.bin")},
        "user_only": {"sheet": {"path": S3 + "/user_only/sculpture_vs_V1.png", "sha256": sha(S3 + "/user_only/sculpture_vs_V1.png")},
                      "log": S3 + "/user_only/sculpture_vs_V1_log.json", "photo_copies_log": S3 + "/user_only/ref_asm/ref_asm_log.json"},
        "incidents_ja": [
            "描画の 1 回目（10:23〜10:26）：冠の画（_crownmask）に冠が入らなかった。冠の GameObject は HideFlags.DontSave で、FindObjectsByType に出ないため、材質の入れ替えが効かなかった。"
            "冠の色 (1,0,1) はほかの物（色区の ID で同じ色になる物、原画視点 8,362 画素）とも重なった。直し：覚えておいた冠のレンダラーを直に替え、冠の色を (0.25,0.5,1)（書き出しで (13,55,255)）にした。"
            "3 つの変種と比べの視点を描き直し、評価器も回し直した。1 回目の出力（render_try1、冠の画のほかは同じ描画）は消した。",
            "写真の 5 枚を目で見るための縮めた並べ（写真から作った画、1800×900）を、1 度だけ会話の作業フォルダー（Build/Polish/sample03 の外、C: のスクラッチパッド）に書き、すぐ消した"
            "（SHA-256 4a78e526621b70f19d39511fe2d464a8d224ecf79adb7c10ccb18a2140e63480）。同じ物を sample03/user_only/ref_asm の中で作り直して見て、終わりに消した（ref_asm_log.json）。",
            "描画の記録（as03asm_render_report.json）の as03AsmNote の冠の色の数（64,128,255）は誤り。正しくは (13,55,255)。道具の説明の文は描画の後に直した。"],
        "noteJa": "PC オフスクリーン描画（HMD 実機ではない）。原画カメラの投影は使わない。参照モデルの OBJ は読んでいない。写真は Q16 のフォルダーの 5 枚だけを一時の写しで読んだ。"
                  "見本01・02・採用の場面・材質・スクリプトは変えていない（描画のたびに守るファイルの SHA-256 が同じ）。git の add・commit・push はしていない。",
    }
    json.dump(rec, open(ASM + "/asm_run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(ASM + "/asm_run.json")


if __name__ == "__main__":
    main()
