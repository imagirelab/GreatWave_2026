# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：証拠のフォルダー（Docs/Evidence/Polish/33）へ、修正の回の数の JSON を写し、metrics_fix01.json と run_fix01.json を書く（新しい計算はしない）。

使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_record.py
"""
import glob
import json
import os
import shutil
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
from pl33_common import sha  # noqa: E402

B = REPO + "/Unity/Build/Polish/33"
F = B + "/fix01"
EV = REPO + "/Docs/Evidence/Polish/33"


def jl(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def eval_counts(run):
    out = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        m = jl(run + "/eval23/off_%s/metrics.json" % c)
        cnt = {}
        for k, v in m["items"].items():
            cnt[v.get("verdict")] = cnt.get(v.get("verdict"), 0) + 1
        out[c] = cnt
    return out


def gates(run):
    g = jl(run + "/pl28u_regress.json")["sets"]
    res = {}
    for s in ("t28_white", "t28_claws"):
        d = g[s]["strict"]["silhouettes_definition_reading"]
        res[s] = {"def": {k: d[k] for k in ("78", "130", "131", "132", "72")}, "s12_132": g[s]["large_form"]["s12"]["132_max_px"],
                  "s12_72p95": g[s]["large_form"]["s12"]["72_p95_px"], "s24_72p95": g[s]["large_form"]["s24"]["72_p95_px"],
                  "sym_pass": g[s]["sym"]["pass"], "colour_pass": g[s]["strict"]["pass_colour"]}
    res["eval23"] = eval_counts(run)
    return res


def main():
    copies = {F + "/measure/pl33f_measure.json": "pl33f_measure.json", F + "/relief/pl33f_relief_report.json": "pl33f_relief_report.json",
              F + "/claws/pl33_crown.json": "pl33f_crown.json", F + "/measure/pl33_bumps_fix.json": "pl33_bumps_fix.json",
              F + "/measure/crown_painting_vis_all.json": "pl33f_crown_painting_vis_all.json", F + "/r_fix01/pl28u_regress.json": "pl28u_regress_fix01.json",
              F + "/playmode_Release/pl29_playmode.json": "playmode_release_fix01.json", F + "/playmode_SinglePlayback/pl29_playmode.json": "playmode_single_fix01.json",
              F + "/setup/pl33_setup.json": "pl33_setup_fix01.json", B + "/release/unity/pl33_build.json": "release_build_fix01.json",
              F + "/r_fix01/pl29_render_report.json": "render_report_fix01.json"}
    for s, d in copies.items():
        if os.path.exists(s):
            shutil.copyfile(s, os.path.join(EV, d))
    g = {"before_pl32": jl(EV + "/pl33_gates.json")["before"], "build": jl(EV + "/pl33_gates.json")["after"], "fix01": gates(F + "/r_fix01"),
         "rim_try": {"t28_claws_def": jl(F + "/r_rim1/pl28u_regress.json")["sets"]["t28_claws"]["strict"]["silhouettes_definition_reading"],
                     "t28_claws_s12": jl(F + "/r_rim1/pl28u_regress.json")["sets"]["t28_claws"]["large_form"]["s12"]}}
    json.dump(g, open(EV + "/pl33_gates_fix01.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    m = jl(F + "/measure/pl33f_measure.json")
    players = {}
    for t in ("f01pair1", "f01pair2", "pair1", "pair2"):
        p = B + "/release/runs/%s/report.json" % t
        if os.path.exists(p):
            r = jl(p)
            players[t] = {k: r.get(k) for k in ("pass", "frames", "errors", "endShownFrame", "quitFrame")}
    json.dump(players, open(EV + "/pl33_players_fix01.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    V = m["views"]
    geo = m["geometry"]
    rg = m["closed_rings"]
    rh = m["painting_tstar_rhythm"]
    sil = m["painting_outside_hero"]
    bumps = jl(F + "/measure/pl33_bumps_fix.json")["items"]
    met = {
        "schema": "GreatWave.Polish33.metrics_fix01/1",
        "before": "仕上げ32（ede11c8、Build/Polish/32/fix01/r_fix01）", "build": "仕上げ33 作る部（Build/Polish/33/r_after）", "fix01": "仕上げ33 修正の回 1（Build/Polish/33/fix01/r_fix01）",
        "must_fix": {
            "1_seat_hmd_slabs_crescents": {"seat_t120_over_indigo_px": [V["seat_t120"][k]["over_indigo_px"] for k in ("before", "build", "fix")],
                                           "seat_t120_largest_mostly_indigo_comp_px": [V["seat_t120"][k]["largest_mostly_indigo"] for k in ("before", "build", "fix")],
                                           "seat_toward_wave_t120_over_indigo_px": [V["seat_toward_wave_t120"][k]["over_indigo_px"] for k in ("before", "build", "fix")],
                                           "verdict_ja": "直した（目視：座席・座席から波の方向・HMD の枠の t* で角の四角い板・藍の上の白い三日月は見えない）"},
            "2_stw_t105_pebbles": {"over_indigo_px": [V["seat_toward_wave_t105"][k]["over_indigo_px"] for k in ("before", "build", "fix")],
                                   "largest_mostly_indigo_comp_px": [V["seat_toward_wave_t105"][k]["largest_mostly_indigo"] for k in ("before", "build", "fix")],
                                   "verdict_ja": "直した"},
            "3_painting_t105_fangs_t9_crown_spikes": {"outside_hero_px_t090_t105": [[sil[t][k]["claw_px_outside_hero"] for t in ("t090", "t105")] for k in ("before", "build", "fix")],
                                                     "crown_painting_visible_vertices_frames_225_360_step3": 0, "verdict_ja": "直した（前と同じ値に戻った）"},
            "4_crown_rice_grains_and_ring": {"ridge_ringed_fraction_tstar": m["ridge_ringed_fraction_tstar"], "crowns": geo["fix"]["counts"]["K"],
                                             "verdict_ja": "一部：ドームの面に散る離れた鉤・米粒はなくした。稜の縁取りの割合は作る部より低い（房の間の空き）"},
            "5_8_bregion_user_words": {"bregion": {k: rh["bregion_" + k] for k in ("painting", "before", "build", "fix")},
                                       "rings_t120": [rg["%s_t120_bregion" % k]["rings"] for k in ("before", "build", "fix")],
                                       "verdict_ja": "一部（2 回目の作り直しの後）"},
            "6_9_132_72_detail": {"fix01": {k: {"max_px": bumps[k]["max_px"], "p95_px": bumps[k]["p95_px"]} for k in ("132", "72")},
                                  "rim_try": g["rim_try"]["t28_claws_def"], "verdict_ja": "満たさない（へこみを埋める帯を試したが 4 px に届かず、ほかの視点で白い棒になったので採らない）"},
            "7_12_row5_orientation": {"frame_flips_gt90": [geo[k]["section_orientation"]["frame_flips_gt90"] for k in ("before", "build", "fix")],
                                      "ring_twists_gt60": [geo[k]["section_orientation"]["ring_twists_gt60"] for k in ("before", "build", "fix")], "verdict_ja": "直した"},
            "7_13_row6_bends": {k: geo[k]["bends_tstar"] for k in ("before", "build", "fix")}, "7_row8_growth": "pl33f_onscreen_birth（45 本）",
            "7_row10_notches": m["lip_outline_white_notches_tstar"],
            "10_11_rings": {k: {t: [rg["%s_%s_all" % (k, t)]["rings"], rg["%s_%s_all" % (k, t)]["rings_hole_ge4"]] for t in ("t090", "t105", "t120")} for k in ("before", "build", "fix")},
            "15_penetration": {k: geo[k]["penetration"] for k in ("before", "build", "fix")},
            "motion": {k: geo[k]["motion"] for k in ("before", "build", "fix")},
        },
        "gates_painting_view": g["fix01"], "gates_before": g["before_pl32"],
        "cp1_26r01_reference": {"78": [2.772, 1.641], "130": [1.968, 1.953], "131": [1.814, 1.798], "132": [1.326, 1.574], "72": [1.558, 1.723]},
        "players": players,
    }
    json.dump(met, open(EV + "/metrics_fix01.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    code = ["Tools/GWWaveGen/pl33/pl33f_relief.py", "Tools/GWWaveGen/pl33/pl33f_tuft.py", "Tools/GWWaveGen/pl33/pl33f_crown.py", "Tools/GWWaveGen/pl33/pl33f_rim.py",
            "Tools/GWWaveGen/pl33/pl33f_measure.py", "Tools/GWWaveGen/pl33/pl33f_sheets.py", "Tools/GWWaveGen/pl33/pl33f_figs.py", "Tools/GWWaveGen/pl33/pl33f_record.py",
            "Unity/Assets/GreatWave/Polish33/Scripts/PL33ClawLook.cs", "Unity/Assets/GreatWave/Polish33/Editor/PL33Setup.cs", "Unity/Assets/GreatWave/Polish33/Editor/PL33ReleaseBuild.cs",
            "Unity/Assets/GreatWave/Polish33/Scenes/PL33_Release.unity", "Unity/Assets/GreatWave/Polish33/Scenes/PL33_SinglePlayback.unity"]
    outs = [F + "/claws/ds33_claw_layout.json", F + "/claws/ds33_claw_frames_f32.bin", F + "/claws/ds33_claw_tris_i32.bin", F + "/claws/ds33_claw_tri_attr_u16.bin",
            F + "/relief/ds33_claw_layout.json", F + "/relief_t/ds33_claw_layout.json", B + "/release/player/GreatWave50.exe"]
    run = {"schema": "GreatWave.Polish33.run_fix01/1",
           "commands": [
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_relief.py",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_tuft.py",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_crown.py --relief Unity/Build/Polish/33/fix01/relief_t",
               "bash Unity/Build/Polish/33/fix01/run_render_f.sh r_fix01 views,tt,t28,full,video",
               "bash Unity/Build/Polish/32/run_eval.sh Unity/Build/Polish/33/fix01/r_fix01",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33_bumps.py Unity/Build/Polish/33/fix01/r_fix01/t28_claws Unity/Build/Polish/33/fix01/measure/pl33_bumps_fix.json",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_measure.py",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_rim.py ; bash Unity/Build/Polish/33/fix01/run_render_f.sh r_rim1 views,t28 Build/Polish/33/fix01/try_rim/ds33_claw_layout.json ; py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/33/fix01/r_rim1 --kstar rec（試し、採らない）",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33Setup.BuildScenes -Log f01_build_scenes -Extra \"-pl33Out …/fix01/setup\"",
               "run_pl33_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log f01_playmode_<Release|SinglePlayback> -Extra \"-pl29Scene Assets/GreatWave/Polish33/Scenes/PL33_<…>.unity -pl29Out …/fix01/playmode_<…> -pl29Limit 400|120\"",
               "run_pl33_unity.ps1 -Method GreatWave.Polish33.EditorTools.PL33ReleaseBuild.BuildAll -Log f01_release_build",
               "run_pl33_player.ps1 -Tag f01pair1 ; run_pl33_player.ps1 -Tag f01pair2",
               "py -3.10 -B Tools/GWWaveGen/pl33/pl33f_sheets.py ; py -3.10 -B Tools/GWWaveGen/pl33/pl33f_figs.py ; py -3.10 -B Tools/GWWaveGen/pl33/pl33f_record.py"],
           "code_sha256": {c: sha(REPO + "/" + c) for c in code if os.path.exists(REPO + "/" + c)},
           "outputs_sha256": {rel(o): sha(o) for o in outs if os.path.exists(o)},
           "archive_build": "Unity/Build/Polish/33/record/archive_build（作る部の図・動画・記録の写し。archive_index.json に SHA-256）",
           "c_drive_note_ja": "C: の空きが 0 だったので、会話の作業フォルダー（C: の Temp の scratchpad）のうち 9/29 より前の古いフォルダー 119 個（約 1.54 GB）を Unity/Build/_scratch_moved_20261002（G:、Git 対象外）へ移した（消していない）。q26gov と objref は動かしていない。"}
    json.dump(run, open(EV + "/run_fix01.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F_RECORD_DONE", len(copies), "copies")


if __name__ == "__main__":
    main()
