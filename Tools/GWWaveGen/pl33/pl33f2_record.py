# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 2：証拠のフォルダー（Docs/Evidence/Polish/33）へ、修正の回 2 の数の JSON を写し、metrics_fix02.json・run_fix02.json・pl33_gates_fix02.json を書き、
metrics_fix01.json と metrics_build.json（記録の部で metrics.json から名前を替えた作る部の記録）に、自己評審（修正の回 1 の再評審）が指摘した古い判定の読み替えを書き足す（新しい計算はしない。値は既にある JSON から取る）。

使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_record.py
"""
import json
import os
import shutil
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
from pl33_common import sha  # noqa: E402
from pl33f_record import eval_counts, gates, jl, rel  # noqa: E402

B = REPO + "/Unity/Build/Polish/33"
F1 = B + "/fix01"
F2 = B + "/fix02"
EV = REPO + "/Docs/Evidence/Polish/33"


def jd(o, p):
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def main():
    copies = {F2 + "/measure/pl33f2_measure.json": "pl33f2_measure.json", F2 + "/claws/pl33f2_clip_report.json": "pl33f2_clip_report.json",
              F2 + "/measure/pl33_bumps_fix02.json": "pl33_bumps_fix02.json", F2 + "/r_fix02/pl28u_regress.json": "pl28u_regress_fix02.json",
              F2 + "/playmode_Release/pl29_playmode.json": "playmode_release_fix02.json", F2 + "/playmode_SinglePlayback/pl29_playmode.json": "playmode_single_fix02.json",
              F2 + "/setup/pl33_setup.json": "pl33_setup_fix02.json", B + "/release/unity/pl33_build.json": "release_build_fix02.json",
              F2 + "/r_fix02/pl33_render_report.json": "render_report_fix02.json", F2 + "/work/ridge_img.json": "pl33f2_ridge_img.json"}
    for s, d in copies.items():
        shutil.copyfile(s, os.path.join(EV, d))
    seq = {}
    for nm, p in (("t10_t12_step0p1", F2 + "/work/seqm_f2.json"), ("plus1frame", F2 + "/work/seqm_hold1.json"), ("plus2frames", F2 + "/work/seqm_hold2.json")):
        seq[nm] = jl(p)
    seq["rule_ja"] = ("原画視点 t 10.0〜12.0 s の毎コマ（0.1 s おきの 21 コマ＝pl33f2_white_clip の検査のコマ、と 1 コマ後・2 コマ後の 20 コマずつ＝検査に使っていないコマ）。"
                      "藍の上の明るい爪：作品のままと爪なしの差の最大のチャンネル > 12、爪なしの明るさ（RGB の平均）< 110、作品の明るさ > 150。total は画素の数、largest は 8 連結の一番大きい成分。"
                      "pre＝仕上げ32（Build/Polish/32/fix01/claws を PL33Render -pl33Look 0 で描いた）、fix01＝修正の回 1、f2＝修正の回 2。描画は PL33Render（Unity の PC オフスクリーン）。")
    jd(seq, EV + "/pl33f2_seq_overindigo.json")
    g1 = jl(EV + "/pl33_gates_fix01.json")
    g = {"before_pl32": g1["before_pl32"], "fix01": g1["fix01"], "fix02": gates(F2 + "/r_fix02")}
    jd(g, EV + "/pl33_gates_fix02.json")
    players = {}
    for t in ("f02pair1", "f02pair2"):
        r = jl(B + "/release/runs/%s/report.json" % t)
        players[t] = {k: r.get(k) for k in ("pass", "frames", "errors", "endShownFrame", "quitFrame")}
    jd(players, EV + "/pl33_players_fix02.json")
    m = jl(F2 + "/measure/pl33f2_measure.json")
    V, geo, rg, rh, sil = m["views"], m["geometry"], m["closed_rings"], m["painting_tstar_rhythm"], m["painting_outside_hero"]
    K3 = ("before", "build", "fix")
    sq = jl(F2 + "/work/seqm_f2.json")
    ser = {k.split("_")[-1]: {r["t"]: r for r in v} for k, v in sq.items()}
    allrows = {"pre": {}, "fix01": {}, "f2": {}}
    for p in (F2 + "/work/seqm_f2.json", F2 + "/work/seqm_hold1.json", F2 + "/work/seqm_hold2.json"):
        for k, v in jl(p).items():
            allrows[k.split("_")[-1]].update({r["t"]: r for r in v})
    dmax_f2 = max(allrows["f2"][t]["largest"] - allrows["pre"][t]["largest"] for t in allrows["f2"])
    dmax_f1 = max(allrows["fix01"][t]["largest"] - allrows["pre"][t]["largest"] for t in allrows["fix01"])
    clip = jl(F2 + "/claws/pl33f2_clip_report.json")
    bumps = jl(F2 + "/measure/pl33_bumps_fix02.json")["items"]
    ridge = jl(F2 + "/work/ridge_img.json")
    met = {
        "schema": "GreatWave.Polish33.metrics_fix02/1",
        "note_ja": "仕上げ33 修正の回 2（2026-10-02）。比べの欄：before＝仕上げ32（ede11c8、Build/Polish/32/fix01/r_fix01）、fix01＝修正の回 1（Build/Polish/33/fix01/r_fix01）、fix02＝修正の回 2＝採用（Build/Polish/33/fix02/r_fix02）。"
                   "pl33f2_measure.json の build の欄は修正の回 1、fix の欄は修正の回 2（--build-run で入れ替えた）。Unity の PC オフスクリーン描画と numpy の計算。HMD 実機ではない。",
        "must_fix": {
            "1_bregion_sliver_into_indigo": {
                "painting_t120_largest_light_claw_comp_over_indigo_px": [ser["pre"][12.0]["largest"], ser["fix01"][12.0]["largest"], ser["f2"][12.0]["largest"]],
                "painting_t120_light_claw_over_indigo_px": [ser["pre"][12.0]["total"], ser["fix01"][12.0]["total"], ser["f2"][12.0]["total"]],
                "painting_t105_largest_light_claw_comp_over_indigo_px": [ser["pre"][10.5]["largest"], ser["fix01"][10.5]["largest"], ser["f2"][10.5]["largest"]],
                "painting_t105_light_claw_over_indigo_px": [ser["pre"][10.5]["total"], ser["fix01"][10.5]["total"], ser["f2"][10.5]["total"]],
                "t10_t12_every_frame_61": {"max_largest_minus_pre_px": {"fix01": dmax_f1, "fix02": dmax_f2}, "file": "pl33f2_seq_overindigo.json"},
                "clip": clip["summary"],
                "verdict_ja": "直した（t 10.0〜12.0 s の毎コマ 61 コマで、藍の上の明るい爪の一番大きい成分は仕上げ32 との差が最大 +%d px。目視：原画視点 t*・t 10.5 s の細片はない）" % dmax_f2},
            "2_record_row2_and_seat": {"claw_zone_mizuiro_painting_before_fix01_fix02": [rh["claw_zone_painting"]["mizuiro"], rh["claw_zone_before"]["mizuiro"], rh["claw_zone_build"]["mizuiro"], rh["claw_zone_fix"]["mizuiro"]],
                                       "claw_zone_dark_line_px": [rh["claw_zone_painting"]["dark_line_px"], rh["claw_zone_before"]["dark_line_px"], rh["claw_zone_build"]["dark_line_px"], rh["claw_zone_fix"]["dark_line_px"]],
                                       "seat_t120_claw_px_before_fix01_fix02": [V["seat_t120"][k]["claw_px"] for k in K3],
                                       "seat_t120_claw_px_build_r_after": jl(EV + "/pl33f_measure.json")["views"]["seat_t120"]["build"]["claw_px"],
                                       "seat_toward_wave_t120_claw_px": [V["seat_toward_wave_t120"][k]["claw_px"] for k in K3],
                                       "verdict_ja": "記録を直した：計画 §5.3 の行 2 は「一部」（原画視点の律動は水色 0.365（修正の回 1）・0.356（修正の回 2）、原画 0.412。座席・座席から波の方向の爪は仕上げ32 の見え方に戻り、座席から 3D の白い指は読めない＝限界）。作る部の「直した（0.419／90,219）」は取り消し"},
            "3_section_5_1_reading": {"verdict_ja": "記録を直した：作る部は修正の回ではない。［利用者の言葉］Q16・Q21 の 2 回目の修正の回を、この修正の回 2 で使った（細片の除去と、白の範囲の内に収めた添え指の伸び方）。"
                                                    "b区域を広げる試し（pl33f2_tuft_web_wide）は採らなかった。判定は一部のまま、10/29 以降の一覧へ"},
            "4_left_side_overclaim": {"side_left_t120_top_edge_columns_with_claw_within15px": ridge["side_left"], "back65": ridge["back65"], "side_right": ridge["side_right"], "top": ridge["top"],
                                      "verdict_ja": "記録を直した：左の側面は、ドームの左上の 1 か所に房の列が面を下る形で見え、上の縁の大半は滑らか（上の縁の列のうち 15 px 以内に爪がある割合 0.26、白い塊の尾を含む全体の上の縁。自己評審の読みではドームの上の縁で約 0.44）"},
        },
        "bregion_user_words": {k: rh["bregion_" + k] for k in ("painting",) + K3},
        "bregion_rings": {t: [rg["%s_%s_bregion" % (k, t)]["rings"] for k in K3] for t in ("t090", "t105", "t120")},
        "views_t105_t120": {"%s_%s" % (v, t): {k: {kk: V["%s_%s" % (v, t)][k][kk] for kk in ("claw_px", "over_indigo_px", "line_on_light_px", "largest_mostly_indigo")} for k in K3}
                            for v in ("painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top") for t in ("t105", "t120")},
        "painting_outside_hero_px": {t: [sil[t][k]["claw_px_outside_hero"] for k in K3] for t in sil},
        "closed_rings_all": {k: {t: [rg["%s_%s_all" % (k, t)]["rings"], rg["%s_%s_all" % (k, t)]["rings_hole_ge4"]] for t in ("t090", "t105", "t120")} for k in K3},
        "geometry": {k: {"counts": geo[k]["counts"], "motion": geo[k]["motion"], "penetration": geo[k]["penetration"], "section_orientation": geo[k]["section_orientation"]["frame_flips_gt90"],
                         "ring_twists_gt60": geo[k]["section_orientation"]["ring_twists_gt60"], "bends": geo[k]["bends_tstar"], "crown_painting_cam_visibility": geo[k]["crown_painting_cam_visibility"]} for k in K3},
        "C_tstar_projection_shift_px": m["C_tstar_centre_tip_projection_shift_px"],
        "lip_notches": m["lip_outline_white_notches_tstar"],
        "ridge_ringed_fraction_tstar": m["ridge_ringed_fraction_tstar"],
        "bumps_132_72_definition_with_claws": {k: {"max_px": bumps[k]["max_px"], "p95_px": bumps[k]["p95_px"]} for k in ("132", "72")},
        "gates_painting_view": g["fix02"], "gates_fix01": g["fix01"], "gates_before": g["before_pl32"],
        "cp1_26r01_reference": {"78": [2.772, 1.641], "130": [1.968, 1.953], "131": [1.814, 1.798], "132": [1.326, 1.574], "72": [1.558, 1.723]},
        "players": players,
        "trials_not_adopted": {"const_schedule": "全コマ同じ倍率（--mode const）：添え指 15 本・膜 6 本を全部 0 にした。b区域の暗い線の成分 112（採用 115）",
                               "tuft_web_wide_1p9": "b区域の膜を横へ最大 1.9 倍（--web-b-max 1.9）：b区域の水色 0.354（採用 0.331）、暗い線の画素 6,008（6,247）、成分 113（115）、閉じた輪 7（6）、水色の再現 0.642（0.640）",
                               "web_floor": "膜の輪の中ほどが面より 5 cm より下に入らない検査（--web-floor）：面の下の膜の輪 t 9・10.5・12 s は 6・3・10 で変わらず、縮める膜が 3 本増えただけ"},
    }
    jd(met, EV + "/metrics_fix02.json")
    # 修正の回 1 の記録の読み替え（自己評審の指摘 2）
    m1 = jl(EV + "/metrics_fix01.json")
    m1["record_corrections_fix02"] = {
        "plan_5_3_row2_adopted_ja": "計画 §5.3 の行 2（原画視点で 3D の爪が読めない／座席では細かく乱れる）の採用の状態（修正の回 1）は「一部」。作る部の「直した（爪の領域の水色 0.419、座席の爪の画素 90,219）」は"
                                    "修正の回 1 で立ち上げを低い浮き彫りに戻したので当たらない。修正の回 1 の値：爪の領域の水色 0.365（原画 0.412、前 0.322）、座席 t* の爪の画素 38,870（前 36,466）。"
                                    "座席・座席から波の方向の爪は仕上げ32 の見え方に戻り、座席から 3D の白い指は読めない（限界）。",
        "row2_values": {"claw_zone_mizuiro": {"painting": 0.4124, "before": 0.3222, "build": 0.4186, "fix01": 0.3649}, "seat_t120_claw_px": {"before": 36466, "build": 89449, "fix01": 38870}},
        "section_5_1_reading_ja": "作る部は修正の回ではない。修正の回 1 は［利用者の言葉］の修正の回の 1 回目で、計画 §5.1 の上限ではなかった（2 回目は修正の回 2 で使った）。",
        "left_side_ja": "第 14.6 節の左の側面「稜がぎざぎざの指の列として読める」は言い過ぎ。ドームの左上の 1 か所に房の列が面を下り、上の縁の大半は滑らか（metrics_fix02.json の 4_left_side_overclaim）。",
        "by": "仕上げ33 修正の回 2（Tools/GWWaveGen/pl33/pl33f2_record.py）"}
    jd(m1, EV + "/metrics_fix01.json")
    m0 = jl(EV + "/metrics_build.json")
    pr = m0.get("plan_5_3", {}).get("painting_claw_rhythm")
    if pr is not None:
        pr["superseded_ja"] = "作る部の値。採用ではない（修正の回 1 で低い浮き彫りに戻した）。採用の状態は metrics_fix01.json の record_corrections_fix02 と metrics_fix02.json の must_fix.2_record_row2_and_seat（一部）。"
        jd(m0, EV + "/metrics_build.json")
    code = ["Tools/GWWaveGen/pl33/pl33f2_clip.py", "Tools/GWWaveGen/pl33/pl33f_measure.py", "Tools/GWWaveGen/pl33/pl33f2_sheets.py", "Tools/GWWaveGen/pl33/pl33f2_figs.py",
            "Tools/GWWaveGen/pl33/pl33f2_record.py", "Unity/Assets/GreatWave/Polish33/Editor/PL33Setup.cs", "Unity/Assets/GreatWave/Polish33/Editor/PL33ReleaseBuild.cs",
            "Unity/Assets/GreatWave/Polish33/Scenes/PL33_Release.unity", "Unity/Assets/GreatWave/Polish33/Scenes/PL33_SinglePlayback.unity"]
    outs = [F2 + "/claws/ds33_claw_layout.json", F2 + "/claws/ds33_claw_frames_f32.bin", F2 + "/claws/ds33_claw_tris_i32.bin", F2 + "/claws/ds33_claw_tri_attr_u16.bin",
            F2 + "/claws/pl33f2_web_scale.npy", F2 + "/claws/pl33f2_tuft_scale.npy", B + "/release/player/GreatWave50.exe"]
    run = {"schema": "GreatWave.Polish33.run_fix02/1",
           "commands": [
               "bash Unity/Build/Polish/33/fix02/run_render_g.sh seq_fix01 views Build/Polish/33/fix01/claws/ds33_claw_layout.json 1 \"-pl29Views painting -pl29Times 10.0,10.1,…,12.0\"（爪なしの描画＝検査の暗い所）",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_clip.py",
               "bash Unity/Build/Polish/33/fix02/run_render_g.sh r_fix02 views,tt,t28,full,video",
               "bash Unity/Build/Polish/33/fix02/run_render_g.sh <seq_pre|seq_fix01|seq_f2|hold1_*|hold2_*> views <爪の並び> <0|1> \"-pl29Views painting -pl29Times …\"（毎コマの確かめ。hold は 10.0333＋0.1k・10.0667＋0.1k）",
               "bash Unity/Build/Polish/32/run_eval.sh Unity/Build/Polish/33/fix02/r_fix02",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_bumps.py Unity/Build/Polish/33/fix02/r_fix02/t28_claws Unity/Build/Polish/33/fix02/measure/pl33_bumps_fix02.json",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_measure.py --fix-run Unity/Build/Polish/33/fix02/r_fix02 --fix-claws Unity/Build/Polish/33/fix02/claws --build-run Unity/Build/Polish/33/fix01/r_fix01 --build-claws Unity/Build/Polish/33/fix01/claws --out Unity/Build/Polish/33/fix02/measure/pl33f2_measure.json",
               "py -3.10 Unity/Build/Polish/33/fix02/work/seqm.py …（Git 対象外の作業用。式は pl33f2_seq_overindigo.json の rule_ja）、ridge_img.py（左右の側面・真上・後ろ 65° の上の縁の割合）",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33Setup.BuildScenes -Log f02_build_scenes -Extra \"-pl33Out …/fix02/setup\"",
               "run_pl33_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log f02_playmode_<Release|SinglePlayback> -Extra \"-pl29Scene Assets/GreatWave/Polish33/Scenes/PL33_<…>.unity -pl29Out …/fix02/playmode_<…> -pl29Limit 400|120\"",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33ReleaseBuild.BuildAll -Log f02_release_build",
               "run_pl33_player.ps1 -Tag f02pair1 ; run_pl33_player.ps1 -Tag f02pair2",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_sheets.py ; py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_figs.py ; py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_record.py",
               "試し（採らない）：pl33f2_clip.py --mode const --out …/fix02/claws_const、--web-b-max 1.9 --out …/fix02/claws_wide、--web-floor（…/fix02/claws_floortry）"],
           "code_sha256": {c: sha(REPO + "/" + c) for c in code if os.path.exists(REPO + "/" + c)},
           "outputs_sha256": {rel(o): sha(o) for o in outs if os.path.exists(o)},
           "check_masks_sha256": clip["mask_sha256"],
           "archive_fix01": "Unity/Build/Polish/33/record/archive_fix01（修正の回 1 の図・動画・metrics_fix01.json の写し。archive_index.json に SHA-256）"}
    jd(run, EV + "/run_fix02.json")
    print("PL33F2_RECORD_DONE", len(copies), "copies")


if __name__ == "__main__":
    main()
