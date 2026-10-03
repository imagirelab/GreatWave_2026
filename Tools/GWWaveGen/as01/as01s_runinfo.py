# -*- coding: utf-8 -*-
"""美術の見本01（Q29）組み立て：コマンド・版・入力と出力の SHA-256（as01s_run.json）と、数のまとめ（as01s_metrics.json）を書く（記録。新しい計算はしない）。
使い方：py -3.10 -B Tools/GWWaveGen/as01/as01s_runinfo.py
"""
import glob
import hashlib
import json
import os
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
S01 = REPO + "/Unity/Build/Polish/sample01"
AS = S01 + "/assemble"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    inputs = [REPO + "/Unity/Build/Polish/sample01/claws/mesh/ds33_claw_layout.json", REPO + "/Unity/Build/Polish/sample01/claws/mesh/ds33_claw_frames_f32.bin",
              REPO + "/Unity/Build/Polish/sample01/claws/mesh/ds33_claw_tris_i32.bin",
              S01 + "/texA/attr/s01a_hero_attr_v2_f32.bin", REPO + "/Tools/GWWaveGen/sample01/s01a_material_params.txt",
              S01 + "/texB/work/design_final/s01b_design_f16.bin", S01 + "/texB/work/design_final/s01b_attr_f32.bin", REPO + "/Tools/GWWaveGen/sample01/s01b_material_params.txt",
              REPO + "/Unity/Assets/GreatWave/Sample01/TexA/Shaders/S01A_Groove_Hero.shader", REPO + "/Unity/Assets/GreatWave/Sample01/TexB/Shaders/S01B_Tongue_Hero.shader"]
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/as01/as01s_*")) + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/*/*.cs"))
    assets = sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/Scenes/*.unity")) + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/Materials/*.mat"))
    outs = sorted(glob.glob(AS + "/sheets/*.png")) + sorted(glob.glob(AS + "/measure/*.png")) + sorted(glob.glob(S01 + "/internal/*.png"))
    renders = sorted(glob.glob(AS + "/[AB]/views/*.png")) + sorted(glob.glob(AS + "/[AB]/tt/*.png")) + sorted(glob.glob(AS + "/[AB]/full/*.png"))
    run = dict(
        tool="Tools/GWWaveGen/as01/as01s_runinfo.py", utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        unity="6000.4.3f1（Built-in、Linear、PC の batchmode のオフスクリーン描画。HMD 実機ではない）", python="py -3.10",
        commands=["bash Tools/GWWaveGen/as01/as01s_run_render.sh A A views,tt,full,t28",
                  "bash Tools/GWWaveGen/as01/as01s_run_render.sh B B views,tt,full,t28",
                  "bash Tools/GWWaveGen/as01/as01s_run_eval.sh",
                  "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run Unity/Build/Polish/33r01/fix01/r_fix01 --after-run Unity/Build/Polish/sample01/assemble/B --out Unity/Build/Polish/sample01/assemble/measure/gates_B_vs_33r01",
                  "py -3.10 -B Tools/GWWaveGen/as01/as01s_eval_summary.py",
                  "py -3.10 -B Tools/GWWaveGen/as01/claws_overlay.py Unity/Build/Polish/sample01/assemble/measure/overlay_painting Unity/Build/Polish/sample01/claws/before_33r01 Unity/Build/Polish/sample01/assemble/A Unity/Build/Polish/sample01/assemble/B",
                  "py -3.10 -B Tools/GWWaveGen/as01/as01s_sheets.py --internal",
                  "bash Tools/GWWaveGen/as01/as01s_run_unity_steps.sh setup",
                  "bash Tools/GWWaveGen/as01/as01s_run_unity_steps.sh playmode",
                  "試し（採らない）：claws_rim.RIM['SKY_TOL'] = 2 で claws_build.py --out Unity/Build/Polish/sample01/assemble/exp_skytol2/mesh、"
                  "as01s_run_render.sh B exp_skytol2_B views,t28 …/exp_skytol2/mesh/ds33_claw_layout.json、pl28u_regress.py、sweep_gates.py"],
        inputs={rel(p): sha(p) for p in inputs if os.path.exists(p)},
        code={rel(p): sha(p) for p in code}, assets={rel(p): sha(p) for p in assets},
        figures={rel(p): sha(p) for p in outs}, renders={rel(p): sha(p) for p in renders},
        reference_obj_read=False,
        sculpture_photos_note_ja="G:/research/reality scan/北斋参考 の 7 枚（正面图・左45・左图・右图・右45・背图・顶图）を内部の図（Build/Polish/sample01/internal/、Git 対象外）にだけ縮めて貼った。"
                                 "選ぶための一時の縮小図 2 枚は作業の一時フォルダー（リポジトリの外）に作り、見た後に消した（photos_contact.jpg d2d0a39e…c24f、pair_check.jpg be052c8f…ecc1）。",
    )
    json.dump(run, open(AS + "/as01s_run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    met = dict(tool="Tools/GWWaveGen/as01/as01s_runinfo.py")
    met["eval_summary"] = json.load(open(AS + "/measure/as01s_eval_summary.json", encoding="utf-8"))
    met["overlay_painting"] = json.load(open(AS + "/measure/overlay_painting.json", encoding="utf-8"))
    g = json.load(open(AS + "/logs/gates_exp_skytol2.txt", encoding="utf-8"))
    met["exp_skytol2_gates"] = {k: v["after_claws"] for k, v in g["gates"].items()}
    met["setup"] = json.load(open(AS + "/setup/as01s_setup.json", encoding="utf-8"))
    pm = {}
    for d in sorted(glob.glob(AS + "/playmode_*")):
        p = os.path.join(d, "pl29_playmode.json")
        if os.path.exists(p):
            j = json.load(open(p, encoding="utf-8"))
            pm[os.path.basename(d)] = {k: v for k, v in j.items() if not isinstance(v, list)}
    met["playmode"] = pm
    json.dump(met, open(AS + "/as01s_metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RUNINFO", len(run["renders"]), "renders", len(run["figures"]), "figures", "playmode", list(pm))


if __name__ == "__main__":
    main()
