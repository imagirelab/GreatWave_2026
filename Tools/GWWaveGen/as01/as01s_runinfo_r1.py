# -*- coding: utf-8 -*-
"""美術の見本01（Q29）改善の回 1（2026-10-03、美術監督の 8 項目）：コマンド・入力と出力の SHA-256（as01s_run_r1.json）と数のまとめ（as01s_metrics_r1.json）を書く
（記録。新しい計算はしない。回 0 の as01s_run.json・as01s_metrics.json は変えない）。
使い方：py -3.10 -B Tools/GWWaveGen/as01/as01s_runinfo_r1.py
"""
import glob
import hashlib
import json
import os
import time

REPO = "G:/Unity/GreatWave_2026_Fresh"
S01 = REPO + "/Unity/Build/Polish/sample01"
AS = S01 + "/assemble"
T = REPO + "/Tools/GWWaveGen"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


ENV = ("NOLINE=U CLAWP=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as01/as01_claw_params.txt CLAWLINE=31,60,94 "
       "A_PARAMS=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01/s01a_material_params_r1.txt "
       "B_DES=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/design_r1 "
       "B_PARAMS=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01/s01b_material_params_r1.txt")
L = "Build/Polish/sample01/claws/mesh_r1/ds33_claw_layout.json"


def main():
    inputs = [S01 + "/claws/mesh_r1/ds33_claw_layout.json", S01 + "/claws/mesh_r1/ds33_claw_frames_f32.bin", S01 + "/claws/mesh_r1/ds33_claw_tris_i32.bin",
              S01 + "/claws/mesh_r1/ds33_claw_tri_attr_u16.bin", S01 + "/claws/mesh_r1/as01_claws_report.json",
              S01 + "/texA/attr/s01a_hero_attr_v2_f32.bin", T + "/sample01/s01a_material_params_r1.txt",
              S01 + "/texB/work/design_r1/s01b_design_f16.bin", S01 + "/texB/work/design_r1/s01b_attr_f32.bin", S01 + "/texB/work/design_r1/s01b_design.json",
              T + "/sample01/s01b_material_params_r1.txt", T + "/as01/as01_claw_params.txt",
              REPO + "/Unity/Assets/GreatWave/Sample01/TexA/Shaders/S01A_Groove_Hero.shader", REPO + "/Unity/Assets/GreatWave/Sample01/TexB/Shaders/S01B_Tongue_Hero.shader"]
    code = ([T + "/as01/claws_v14.py", T + "/sample01/s01b_design2.py"] + sorted(glob.glob(T + "/as01/as01s_*"))
            + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/*/*.cs")))
    outs = sorted(glob.glob(AS + "/sheets_r1/*.png")) + sorted(glob.glob(AS + "/measure_r1/*")) + sorted(glob.glob(S01 + "/internal/*_r1.png"))
    renders = []
    for d in ("A1", "B1", "A1_t105", "B1_t105"):
        renders += sorted(glob.glob(AS + "/" + d + "/views/*.png")) + sorted(glob.glob(AS + "/" + d + "/tt/*.png")) + sorted(glob.glob(AS + "/" + d + "/full/*.png"))
    run = dict(
        tool="Tools/GWWaveGen/as01/as01s_runinfo_r1.py", utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), round="改善の回 1（美術監督の 8 項目、1 回）",
        unity="6000.4.3f1（Built-in、Linear、PC の batchmode のオフスクリーン描画。HMD 実機ではない）", python="py -3.10",
        commands=[
            "py -3.10 -B Tools/GWWaveGen/as01/claws_v14.py   # → Unity/Build/Polish/sample01/claws/mesh_r1（同じバイト列で作り直せることを cmp で確かめた）",
            "py -3.10 -B Tools/GWWaveGen/sample01/s01b_design2.py --out Unity/Build/Polish/sample01/texB/work/design_r1 --max-rot 25 --blur 2.5 --cz-width 0.9,1.4 "
            "--tip-lo -0.35 --tip-hi 0.25 --miz-off 0.05 --lam0 2.4 --lam-clip 1.9,3.6 --hw 0.14,0.12,0.25,0.30,0.14 --top-wedge 0.5,5 --hw-back 0.11,0.12 "
            "--dot-cell 0.40 --dots 0.75,0.025,0.12,0.03,0.06,0.08 --dot-v2 3.5,0.9,4.0,0.035,0.17,2.6 --lam-grow 30 --seed-jit 0.35 --early 0.3,6,18 "
            "--head-var 0.3 --head 1.0,1.4,1.7 --band-rel 9",
            ENV + " bash Tools/GWWaveGen/as01/as01s_run_render.sh A A1 views,tt,full,t28 " + L,
            ENV + " TIMES=10.5 TTCLAWS=0 bash Tools/GWWaveGen/as01/as01s_run_render.sh A A1_t105 views,tt " + L,
            ENV + " bash Tools/GWWaveGen/as01/as01s_run_render.sh B B1 views,tt,full,t28 " + L,
            ENV + " TIMES=10.5 TTCLAWS=0 bash Tools/GWWaveGen/as01/as01s_run_render.sh B B1_t105 views,tt " + L,
            "SAMPLES=\"A1 B1\" bash Tools/GWWaveGen/as01/as01s_run_eval.sh",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run Unity/Build/Polish/33r01/fix01/r_fix01 --after-run Unity/Build/Polish/sample01/assemble/B1 --out Unity/Build/Polish/sample01/assemble/measure/gates_B1_vs_33r01",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run Unity/Build/Polish/sample01/assemble/B --after-run Unity/Build/Polish/sample01/assemble/B1 --out Unity/Build/Polish/sample01/assemble/measure/gates_B1_vs_B",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_eval_summary.py --round r1",
            "py -3.10 -B Tools/GWWaveGen/as01/claws_overlay.py Unity/Build/Polish/sample01/assemble/measure_r1/overlay_painting Unity/Build/Polish/sample01/claws/before_33r01 "
            "Unity/Build/Polish/sample01/assemble/A Unity/Build/Polish/sample01/assemble/A1 Unity/Build/Polish/sample01/assemble/B1",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_sheets.py --round r1 --internal",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_runinfo_r1.py"],
        inputs={rel(p): sha(p) for p in inputs if os.path.exists(p)},
        code={rel(p): sha(p) for p in code if os.path.exists(p)},
        figures={rel(p): sha(p) for p in outs if os.path.isfile(p)}, renders={rel(p): sha(p) for p in renders},
        reference_obj_read=False,
        sculpture_photos_note_ja="この回は彫刻の写真を新しく開いていない（内部の図 internal_sculpture_vs_samples_r1.png は回 0 と同じ 7 枚を Git 対象外の図に縮めて貼っただけ）。",
        trials_ja="爪の試しの並び claws/mesh_v14a〜v14x（描画の試し assemble/r1_try_*）。採ったのは v14v（= mesh_r1）。",
    )
    json.dump(run, open(AS + "/as01s_run_r1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    met = dict(tool="Tools/GWWaveGen/as01/as01s_runinfo_r1.py")
    met["eval_summary"] = json.load(open(AS + "/measure/as01s_eval_summary_r1.json", encoding="utf-8"))
    met["overlay_painting"] = json.load(open(AS + "/measure_r1/overlay_painting.json", encoding="utf-8"))
    for k in ("gates_B1_vs_33r01", "gates_B1_vs_B"):
        met[k] = json.load(open(AS + "/logs/" + k + ".txt", encoding="utf-8"))["gates"]
    met["claws_r1_counts"] = json.load(open(S01 + "/claws/mesh_r1/as01_claws_report.json", encoding="utf-8"))["counts"]
    met["texB_design_r1"] = {k: v for k, v in json.load(open(S01 + "/texB/work/design_r1/s01b_design.json", encoding="utf-8")).items() if k in ("spacing", "streamlines", "streamlines_by_kind")}
    json.dump(met, open(AS + "/as01s_metrics_r1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("RUNINFO_R1", len(run["renders"]), "renders", len(run["figures"]), "figures")


if __name__ == "__main__":
    main()
