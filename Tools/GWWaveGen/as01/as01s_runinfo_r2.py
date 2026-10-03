# -*- coding: utf-8 -*-
"""美術の見本01（Q29）改善の回 2（2026-10-03、回 1 の残り＝爪が「白い虫」に見えること、B の点の減り過ぎ、場面の写しが回 0 のまま）：
コマンド・入力と出力の SHA-256（as01s_run_r2.json）と数のまとめ（as01s_metrics_r2.json）を書く（記録。新しい計算はしない。回 0・回 1 のファイルは変えない）。
あわせて、利用者に見せる 6 枚の図（assemble/sheets_r2 の us1・us2・us3_tt_AB・us4・us5・us6）を Docs/Evidence/ArtSample01/ へ写し、
そこへ metrics.json（= as01s_metrics_r2.json）と run.json（= as01s_run_r2.json ＋ 写した図の対応と SHA-256）を書く。
使い方：py -3.10 -B Tools/GWWaveGen/as01/as01s_runinfo_r2.py
"""
import glob
import hashlib
import json
import os
import shutil
import time

from PIL import Image

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
       "B_DES=G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample01/texB/work/design_r2 "
       "B_PARAMS=G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/sample01/s01b_material_params_r1.txt")
L = "Build/Polish/sample01/claws/mesh_r2/ds33_claw_layout.json"
EVIDENCE = [("us1_painting_view", "as01_1_painting_view.png", "原画視点：原画｜見本 A｜見本 B（t* = 12 s・爪あり）と、頂と唇の切り出し（同じ枠）"),
            ("us2_views_t120", "as01_2_views_t120.png", "6 視点（座席・座席から波・左右の側面・後ろ 65°・真上）× 見本 A・B（t* = 12 s・爪あり、頂と唇の所）"),
            ("us3_tt_AB", "as01_3_turntable_AB.png", "回り台 12 方位 × 見本 A・B（t* = 12 s・爪あり）"),
            ("us4_rounds", "as01_4_claw_rounds.png", "爪の回ごとの前後：前（採用の仕上げ33修正01）・回 0・回 1・回 2（原画視点の頂と唇）"),
            ("us5_t105", "as01_5_surface_t105.png", "t 10.5 s・爪なし：面の模様だけの比べ（原画視点・左の側面・後ろ 65°・真上）"),
            ("us6_seat_vs_outline", "as01_6_seat_vs_outline.png", "座席で頂の指を見せるか、原画視点の輪郭を守るか（回 0 と回 2 の見本 A）")]


def main():
    inputs = [S01 + "/claws/mesh_r2/ds33_claw_layout.json", S01 + "/claws/mesh_r2/ds33_claw_frames_f32.bin", S01 + "/claws/mesh_r2/ds33_claw_tris_i32.bin",
              S01 + "/claws/mesh_r2/ds33_claw_tri_attr_u16.bin", S01 + "/claws/mesh_r2/as01_claws_report.json",
              S01 + "/texA/attr/s01a_hero_attr_v2_f32.bin", T + "/sample01/s01a_material_params_r1.txt",
              S01 + "/texB/work/design_r2/s01b_design_f16.bin", S01 + "/texB/work/design_r2/s01b_attr_f32.bin", S01 + "/texB/work/design_r2/s01b_design.json",
              T + "/sample01/s01b_material_params_r1.txt", T + "/as01/as01_claw_params.txt", S01 + "/param/s01_param_f32.bin",
              REPO + "/Unity/Assets/GreatWave/Sample01/TexA/Shaders/S01A_Groove_Hero.shader", REPO + "/Unity/Assets/GreatWave/Sample01/TexB/Shaders/S01B_Tongue_Hero.shader"]
    code = ([T + "/as01/claws_v15.py", T + "/as01/claws_v14.py", T + "/sample01/s01b_design2.py"] + sorted(glob.glob(T + "/as01/as01s_*"))
            + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/*/*.cs")))
    unity = sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/Scenes/*.unity")) + sorted(glob.glob(REPO + "/Unity/Assets/GreatWave/ArtSample01/Materials/*.mat"))
    outs = sorted(glob.glob(AS + "/sheets_r2/*.png")) + sorted(glob.glob(AS + "/measure_r2/*"))
    renders = []
    for d in ("A2", "B2", "A2_t105", "B2_t105"):
        renders += sorted(glob.glob(AS + "/" + d + "/views/*.png")) + sorted(glob.glob(AS + "/" + d + "/tt/*.png")) + sorted(glob.glob(AS + "/" + d + "/full/*.png"))
    pm = {}
    for n in ("A_Release", "B_Release", "A_SinglePlayback", "B_SinglePlayback"):
        f = AS + "/playmode_" + n + "/pl29_playmode.json"
        if os.path.exists(f):
            pm[n] = sha(f)
    run = dict(
        tool="Tools/GWWaveGen/as01/as01s_runinfo_r2.py", utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        round="改善の回 2（回 1 の残り：爪が白い虫・カニに見える、B の点の減り過ぎ、場面の写しが回 0 のまま）",
        unity="6000.4.3f1（Built-in、Linear、PC の batchmode のオフスクリーン描画と Editor の Play モード。HMD 実機ではない）", python="py -3.10",
        commands=[
            "py -3.10 -B Tools/GWWaveGen/as01/claws_v15.py   # → Unity/Build/Polish/sample01/claws/mesh_r2（試しの並び mesh_v15i と同じバイト列。2 回作って cmp で同じ）",
            "py -3.10 -B Tools/GWWaveGen/sample01/s01b_design2.py --out Unity/Build/Polish/sample01/texB/work/design_r2 --max-rot 25 --blur 2.5 --cz-width 0.9,1.4 "
            "--tip-lo -0.35 --tip-hi 0.25 --miz-off 0.05 --lam0 2.4 --lam-clip 1.9,3.6 --hw 0.14,0.12,0.25,0.30,0.14 --top-wedge 0.5,5 --hw-back 0.11,0.12 "
            "--dot-cell 0.40 --dots 0.75,0.025,0.12,0.03,0.06,0.08 --dot-v2 6.0,0.9,4.0,0.045,0.17,2.6 --lam-grow 30 --seed-jit 0.35 --early 0.3,6,18 "
            "--head-var 0.3 --head 1.0,1.4,1.7 --band-rel 9   # 回 1（design_r1）から --dot-v2 の減り 3.5 → 6.0 m・半径の下限 0.035 → 0.045 m だけ。点 1,339 → 2,039。白・水色・藍の 3 つの面は画素で同じ",
            ENV + " bash Tools/GWWaveGen/as01/as01s_run_render.sh A A2 views,tt,full,t28 " + L,
            ENV + " TIMES=10.5 TTCLAWS=0 bash Tools/GWWaveGen/as01/as01s_run_render.sh A A2_t105 views,tt " + L + "   # 爪なしの 20 枚は A1_t105 と画素で同じ",
            ENV + " bash Tools/GWWaveGen/as01/as01s_run_render.sh B B2 views,tt,full,t28 " + L,
            ENV + " TIMES=10.5 TTCLAWS=0 bash Tools/GWWaveGen/as01/as01s_run_render.sh B B2_t105 views,tt " + L,
            "SAMPLES=\"A2 B2\" bash Tools/GWWaveGen/as01/as01s_run_eval.sh   # A2 の pl28u_regress は回 0・回 1 と同じく色区 267 の読みで止まる（関門は B2 の値。空の被覆は A2 と画素で同じ）",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run Unity/Build/Polish/33r01/fix01/r_fix01 --after-run Unity/Build/Polish/sample01/assemble/B2 --out Unity/Build/Polish/sample01/assemble/measure/gates_B2_vs_33r01",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_gates.py --before-run Unity/Build/Polish/sample01/assemble/B1 --after-run Unity/Build/Polish/sample01/assemble/B2 --out Unity/Build/Polish/sample01/assemble/measure/gates_B2_vs_B1",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_eval_summary.py --round r2",
            "py -3.10 -B Tools/GWWaveGen/as01/claws_overlay.py Unity/Build/Polish/sample01/assemble/measure_r2/overlay_painting Unity/Build/Polish/sample01/claws/before_33r01 "
            "Unity/Build/Polish/sample01/assemble/A1 Unity/Build/Polish/sample01/assemble/A2 Unity/Build/Polish/sample01/assemble/B2",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_foam_share.py Unity/Build/Polish/sample01/assemble/measure_r2/foam_share.json before_33r01=… A=… A1=… B1=… A2=… B2=…",
            "bash Tools/GWWaveGen/as01/as01s_run_unity_steps.sh setup   # 場面の写し 4 つを回 2 の状態へ（AS01SampleSetup）",
            "bash Tools/GWWaveGen/as01/as01s_run_unity_steps.sh playmode   # Play モードの確かめ 4 つ（回 0 の出力は playmode_*_r0 へ名前を替えて残した）",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_sheets.py --round r2",
            "py -3.10 -B Tools/GWWaveGen/as01/as01s_runinfo_r2.py   # この記録と、証拠 Docs/Evidence/ArtSample01 の図 6 枚・metrics.json・run.json"],
        inputs={rel(p): sha(p) for p in inputs if os.path.exists(p)},
        code={rel(p): sha(p) for p in code if os.path.exists(p)},
        unity_assets={rel(p): sha(p) for p in unity},
        figures={rel(p): sha(p) for p in outs if os.path.isfile(p)}, renders={rel(p): sha(p) for p in renders},
        playmode_reports=pm,
        reference_obj_read=False,
        sculpture_photos_note_ja="この回は彫刻の写真を開いていない（内部の図も作っていない）。",
        trials_ja="爪の試しの並び claws/mesh_v15a〜v15j（と v15i_nolobe）、描画の試し assemble/r2_try_*（原画視点と 6 視点）。採ったのは v15i（= mesh_r2、claws_v15.py の既定の値）。",
    )
    json.dump(run, open(AS + "/as01s_run_r2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    met = dict(tool="Tools/GWWaveGen/as01/as01s_runinfo_r2.py")
    met["eval_summary"] = json.load(open(AS + "/measure/as01s_eval_summary_r2.json", encoding="utf-8"))
    met["overlay_painting"] = json.load(open(AS + "/measure_r2/overlay_painting.json", encoding="utf-8"))
    met["foam_share"] = json.load(open(AS + "/measure_r2/foam_share.json", encoding="utf-8"))
    for k in ("gates_B2_vs_33r01", "gates_B2_vs_B1"):
        met[k] = json.load(open(AS + "/logs/" + k + ".txt", encoding="utf-8"))["gates"]
    met["claws_r2_counts"] = json.load(open(S01 + "/claws/mesh_r2/as01_claws_report.json", encoding="utf-8"))["counts"]
    met["claws_r1_counts"] = json.load(open(S01 + "/claws/mesh_r1/as01_claws_report.json", encoding="utf-8"))["counts"]
    met["texB_design_r2_dots"] = json.load(open(S01 + "/texB/work/design_r2/s01b_design.json", encoding="utf-8")).get("dots")
    met["sky_xor_A2_B2"] = dict(t28_claws=0, t28_white=0, note_ja="A2 と B2 の class_ids の空（白）の画素の xor。形の関門の値が A2・B2 で共通な理由")
    met["t105_A2_vs_A1_clawfree_maxdiff"] = 0
    pmj = {}
    for n in ("A_Release", "B_Release", "A_SinglePlayback", "B_SinglePlayback"):
        f = AS + "/playmode_" + n + "/pl29_playmode.json"
        if os.path.exists(f):
            d = json.load(open(f, encoding="utf-8"))
            pmj[n] = {k: d[k] for k in list(d.keys())[:12] if not isinstance(d[k], (list, dict))}
    met["playmode"] = pmj
    json.dump(met, open(AS + "/as01s_metrics_r2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 証拠（Docs/Evidence/ArtSample01）
    E = REPO + "/Docs/Evidence/ArtSample01"
    os.makedirs(E, exist_ok=True)
    ev = []
    for src, dst, ja in EVIDENCE:
        sp = AS + "/sheets_r2/" + src + ".png"
        dp = E + "/" + dst
        shutil.copyfile(sp, dp)
        im = Image.open(dp)
        assert im.size == (1920, 1080), (dst, im.size)
        ev.append({"file": rel(dp), "from": rel(sp), "sha256": sha(dp), "size": list(im.size), "bytes": os.path.getsize(dp), "ja": ja})
    run_e = dict(run, evidence_files=ev,
                 note_ja="美術の見本01（回 2）の証拠。図は Git 対象外の Unity/Build/Polish/sample01/assemble/sheets_r2 から写した（彫刻の写真とそこから作った画像は入れていない。"
                         "原画はメトロポリタン美術館の公開の画像の表示）。描画・メッシュ・設計のテクスチャは Git 対象外で、SHA-256 をここに記録した。")
    json.dump(run_e, open(E + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    shutil.copyfile(AS + "/as01s_metrics_r2.json", E + "/metrics.json")
    print("RUNINFO_R2", len(run["renders"]), "renders", len(run["figures"]), "figures", len(run["unity_assets"]), "unity assets", len(ev), "evidence figures")


if __name__ == "__main__":
    main()
