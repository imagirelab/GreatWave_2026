# -*- coding: utf-8 -*-
"""仕上げ33修正01：証拠の一式（Docs/Evidence/Polish/33R01）を作る。図・動画・元の数の JSON を写し、metrics.json（評審の直すべき 11 の指摘 → 値 → 判定）と
run.json（コマンド・道具の版・入出力の SHA-256）を書く（記録。新しい描画・計算はしない）。
記録の部で、2 つの変種（SWEEP・Houdini）の候補の証拠（metrics・run・前後の図の一部）と評審の数（_judge/numbers）を写し、
metrics.json の variants と run.json の variants・time を加えた。

読むもの（Git 対象外）：Unity/Build/Polish/33r01/fix01（claws・r_fix01・measure・evidence・logs）、sweep（変種 SWEEP の数と evidence）、
houdini/candidate/evidence（変種 Houdini）、_judge/numbers（評審の数）、setup・release。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/r01_record.py
"""
import hashlib
import json
import os
import shutil
import subprocess

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/33r01"
F1 = B + "/fix01"
SW = B + "/sweep"
SE = SW + "/evidence"
HV = B + "/houdini/candidate/evidence"
JN = B + "/_judge/numbers"
OUT = REPO + "/Docs/Evidence/Polish/33R01"

# 変種の候補の証拠と評審の数（記録の部で加えた。名前を変えて写す）
VARIANT_SRC = {
    "variant_sweep_metrics.json": SE + "/metrics.json", "variant_sweep_run.json": SE + "/run.json", "variant_sweep_eye.json": SE + "/eye_verdicts.json",
    "variant_houdini_metrics.json": HV + "/metrics.json", "variant_houdini_run.json": HV + "/run.json",
    "judge_unified_measure.json": JN + "/unified_measure.json", "judge_geo.json": JN + "/judge_geo.json", "judge_geo2.json": JN + "/judge_geo2.json",
    "judge_img2.json": JN + "/judge_img2.json", "judge_overlay.json": JN + "/judge_overlay.json",
    "fig_pl33r01s_ba_view_seat.png": SE + "/fig_pl33r01s_ba_view_seat.png", "fig_pl33r01s_ba_view_back65.png": SE + "/fig_pl33r01s_ba_view_back65.png",
    "fig_pl33r01h_ba_view_seat.png": HV + "/fig_pl33r01h_ba_view_seat.png", "fig_pl33r01h_ba_view_painting.png": HV + "/fig_pl33r01h_ba_view_painting.png",
    "fig_pl33r01h_ba_turntable_t120.png": HV + "/fig_pl33r01h_ba_turntable_t120.png",
}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    os.makedirs(OUT, exist_ok=True)
    copies = {}
    # 図と動画
    for f in sorted(os.listdir(F1 + "/evidence")):
        if f.endswith(".png") or f.endswith(".mp4"):
            shutil.copyfile(os.path.join(F1, "evidence", f), os.path.join(OUT, f))
            copies[f] = rel(os.path.join(F1, "evidence", f))
    shutil.copyfile(F1 + "/measure/fig_pl33r01_overlay_list.png", OUT + "/fig_pl33r01_overlay_list.png")
    copies["fig_pl33r01_overlay_list.png"] = rel(F1 + "/measure/fig_pl33r01_overlay_list.png")
    # 元の数
    src = {"pl33r01_gates.json": F1 + "/measure/sweep_gates.json", "pl33r01_gates_vs_sweep.json": F1 + "/measure/vs_sweep/sweep_gates.json",
           "pl33r01_views_geometry.json": F1 + "/measure/sweep_measure.json", "pl33r01_overlay.json": F1 + "/measure/r01_overlay.json",
           "pl33f_measure_pl33r01.json": F1 + "/measure/pl33f_measure_fix01.json", "pl33f_measure_sweep.json": SW + "/measure/pl33f_measure_sweep.json",
           "r01_quick.json": F1 + "/measure/r01_quick.json", "r01_quick_geo_sweep.json": F1 + "/measure/r01_quick_geo_sweep.json",
           "r01_quick_geo_pl33.json": F1 + "/measure/r01_quick_geo_pl33.json", "r01_measure.json": F1 + "/measure/r01_measure.json",
           "r01_perf.json": F1 + "/measure/r01_perf.json", "sweep_perf.json": SW + "/measure/sweep_perf.json",
           "r01_report.json": F1 + "/claws/r01_report.json", "pl28u_regress.json": F1 + "/r_fix01/pl28u_regress.json",
           "render_report.json": F1 + "/r_fix01/pl33_render_report.json", "playmode_release.json": F1 + "/playmode_Release/pl29_playmode.json",
           "playmode_single.json": F1 + "/playmode_SinglePlayback/pl29_playmode.json", "release_build.json": B + "/release/unity/pl33r01_build.json",
           "setup.json": B + "/setup/pl33r01_setup.json"}
    for k, v in src.items():
        shutil.copyfile(v, os.path.join(OUT, k))
        copies[k] = rel(v)
    for k, v in VARIANT_SRC.items():
        shutil.copyfile(v, os.path.join(OUT, k))
        copies[k] = rel(v)

    g = J(F1 + "/measure/sweep_gates.json")
    gs = J(F1 + "/measure/vs_sweep/sweep_gates.json")
    q = J(F1 + "/measure/r01_quick.json")
    qs = J(F1 + "/measure/r01_quick_geo_sweep.json")["geo"]
    qp = J(F1 + "/measure/r01_quick_geo_pl33.json")["geo"]
    ov = J(F1 + "/measure/r01_overlay.json")
    pm = J(F1 + "/measure/pl33f_measure_fix01.json")
    pms = J(SW + "/measure/pl33f_measure_sweep.json")
    rm = J(F1 + "/measure/r01_measure.json")
    sm = J(F1 + "/measure/sweep_measure.json")
    ssm = J(SW + "/measure/sweep_measure.json")
    perf = J(F1 + "/measure/r01_perf.json")
    rep = J(F1 + "/claws/r01_report.json")
    lay = J(F1 + "/claws/ds33_claw_layout.json")
    rb = J(B + "/release/unity/pl33r01_build.json")
    rh = pm["painting_tstar_rhythm"]

    def pen(d):
        return {k: dict(entries=v["entries"], deepest_m=v["deepest"]) for k, v in d.items() if k[:2] in ("C_", "W_", "K_", "S_")}

    def acc(d):
        return {k: dict(events=v["n"], entries=v["entries"], worst=v["top"][0] if v["top"] else None) for k, v in d["accel_events"].items()}

    def ph(t, k):
        return {p: perf[t][p][k] for p in ("Formation", "Hold")}

    m = {
        "schema": "GreatWave.Polish33R01.metrics/1",
        "number": {"group": "仕上げ33修正01", "design": "設計33 爪の造形（Q28：立つ 3D の白い指）", "backlog": "99〜101、103〜105、129、136〜141、180、200、204〜208、238、262（仕上げ33 と同じ）",
                   "decision_ja": "進行役の決定（2026-10-02、Q24）。時間枠 1 日。変種 SWEEP を採り、評審の直すべき 11 の指摘に 1 回の修正の回",
                   "plan": "Docs/Design/Stage9_Plan_2026-09-26_ja.md §5.1・§5.2・§5.3 仕上げ33・§2.6"},
        "before_ja": "仕上げ33（コミット 1ed9aa8、修正の回 2）。爪の並び Unity/Build/Polish/33/fix02/claws、描画 Unity/Build/Polish/33/fix02/r_fix02",
        "sweep_ja": "変種 SWEEP（評審の前、採った候補）。爪の並び Unity/Build/Polish/33r01/sweep/claws、描画 Unity/Build/Polish/33r01/sweep/r_final",
        "after_ja": "仕上げ33修正01 の修正の回 1 の後（採る状態）。爪の並び Unity/Build/Polish/33r01/fix01/claws、描画 Unity/Build/Polish/33r01/fix01/r_fix01",
        "evidence_kind_ja": "Unity 6000.4.3f1 の PC オフスクリーン描画、Editor の Play モード 2 つ、Release のプレイヤーを PC（RTX 3080、1920×1080 の窓）で動かした結果、numpy・OpenCV・scipy の計算。HMD 実機ではない。利用者は見ていない",
        "projection_colour_used": False,
        "claw_layer": dict(vertices=lay["vertices"], triangles=lay["triangles"], entries=len(lay["claws"]),
                           kinds={k: sum(1 for c in lay["claws"] if (c["id"][:2] if c["id"].startswith("W") else c["id"][0]) == k) for k in ("C", "K", "WF", "WC")},
                           culled_fingers=lay["pl33r01_fix01"]["culled"], culled_crowns=lay["pl33r01_fix01"]["crowns_culled_low"], heroes=lay["pl33r01_fix01"]["heroes"],
                           before=dict(vertices=95547, triangles=183240), sweep=dict(vertices=54763, triangles=105032), frames_sha256=lay["files"]["frames"]["sha256"]),
        "must_fix": {
            "1_9_mizuiro": dict(painting=dict(claw_zone=rh["claw_zone_painting"]["mizuiro"], bregion=rh["bregion_painting"]["mizuiro"]),
                                before_pl33=dict(claw_zone=rh["claw_zone_build"]["mizuiro"], bregion=rh["bregion_build"]["mizuiro"]),
                                sweep=dict(claw_zone=pms["painting_tstar_rhythm"]["claw_zone_fix"]["mizuiro"], bregion=pms["painting_tstar_rhythm"]["bregion_fix"]["mizuiro"]),
                                after=dict(claw_zone=rh["claw_zone_fix"]["mizuiro"], bregion=rh["bregion_fix"]["mizuiro"]),
                                target_ja="仕上げ33 の値（0.356・0.331）以上", verdict="直した"),
            "2_fan_curl_seat": dict(seat_t120_claw_px=dict(before=sm["before"]["images"]["seat_t120"]["claw"], sweep=ssm["after"]["images"]["seat_t120"]["claw"], after=sm["after"]["images"]["seat_t120"]["claw"]),
                                    seat_t120_white_body_px=dict(before=sm["before"]["images"]["seat_t120"]["white_body"], sweep=ssm["after"]["images"]["seat_t120"]["white_body"], after=sm["after"]["images"]["seat_t120"]["white_body"]),
                                    verdict="一部", note_ja="稜の指は外向きの法線へ扇に開き、先で巻く。面がカメラを向く指は原画視点の道を守る限り射線の向きにしか立てられず、座席から同じ向きに傾く（限界）。唇の先の C085 は 132 の関門のため長いまま"),
            "3_flat_hooks": dict(found_ja="評審の読みと違い、平たい鉤の群れは冠の爪の低い房（K027〜K029・K037〜K040、ほかに K109〜K111）だった",
                                 crowns_culled=lay["pl33r01_fix01"]["crowns_culled_low"], fingers_culled=lay["pl33r01_fix01"]["culled"], verdict="直した"),
            "4_7_list_overlay": dict(before=ov["before"], after=ov["after"],
                                     sweep=J(SW + "/measure/sweep_overlay.json")["after"], components=dict(painting=rh["claw_zone_painting"]["components"],
                                     before=rh["claw_zone_build"]["components"], sweep=pms["painting_tstar_rhythm"]["claw_zone_fix"]["components"], after=rh["claw_zone_fix"]["components"]),
                                     dark_line_px=dict(painting=rh["claw_zone_painting"]["dark_line_px"], before=rh["claw_zone_build"]["dark_line_px"],
                                                       sweep=pms["painting_tstar_rhythm"]["claw_zone_fix"]["dark_line_px"], after=rh["claw_zone_fix"]["dark_line_px"]),
                                     verdict="直した（一覧への重なり）。輪の律動は一部（成分 266、原画 398）"),
            "5_bold_72m": dict(white_body_px_t120={v: dict(before=sm["before"]["images"][v + "_t120"]["white_body"], sweep=ssm["after"]["images"][v + "_t120"]["white_body"],
                                                           after=sm["after"]["images"][v + "_t120"]["white_body"]) for v in ("side_left", "side_right", "top", "back65")},
                               ridge_ringed_fraction_tstar={k: dict(before=v["build"], after=v["fix"]) for k, v in pm["ridge_ringed_fraction_tstar"].items()},
                               verdict="一部"),
            "6_section_pops": dict(r01_measure=rm, pl33f_measure_after=pm["geometry"]["fix"]["section_orientation"], pl33f_measure_sweep=pms["geometry"]["fix"]["section_orientation"],
                                   note_ja="ねじれ（> 60°）の 99% は一覧の中心線の 60° を超える折れの所（隣の輪の接線が違うので数に出る）。断面の白の向きは背骨に沿って平行に運ぶので、接線のまわりのねじれは作りの上で 0",
                                   vr_pop_check_ja="PSVR2 は未導入。HMD での見え方は未検証。PC の描画と数でだけ確かめた", verdict="直した（裏返り 0）。HMD は未検証"),
            "8_penetration_vertex": dict(before=pen(qp), sweep=pen(qs), after=pen(q["geo"]), rule_ja="評審 judge_geo と同じ式：全部の列の頂点の法線、接線の離れ 0.3 m 未満、u > 0.3 で 5 cm より下の頂点を持つ項目の数と最も深い所", verdict="直した（一部残る）"),
            "10_growth_pops": dict(before=acc(qp) if qp.get("accel_events") else {}, sweep=acc(qs), after=acc(q["geo"]), rule_ja="根元に対する頂点の 2 階差 > 0.15 m/コマ²", verdict="直した（一部残る）"),
            "11_gates": dict(gates=g["gates"], raw_detail_with_claws=g["raw_detail_with_claws"], sweep=dict(gates={k: v["before_claws"] for k, v in gs["gates"].items()},
                             raw={k: v["before_claws"] for k, v in gs["raw_detail_with_claws"].items()}), eval23=g["eval23"], verdict="関門は通る（≤ 4 px）。72 σ12 p95 は仕上げ33 より +0.33 px"),
        },
        "views_images": {k: dict(before=sm["before"]["images"][k], sweep=ssm["after"]["images"].get(k), after=sm["after"]["images"][k]) for k in sorted(sm["after"]["images"])},
        "standing_geometry": dict(before=sm["before"]["geometry"], sweep=ssm["after"]["geometry"], after=sm["after"]["geometry"]),
        "painting_view_other": dict(lip_outline_white_notches_tstar=pm["lip_outline_white_notches_tstar"], painting_outside_hero=pm["painting_outside_hero"],
                                    closed_rings=pm["closed_rings"], crown_painting_cam_visibility=pm["geometry"]["fix"]["crown_painting_cam_visibility"]),
        "unity": dict(playmode_release=J(F1 + "/playmode_Release/pl29_playmode.json").get("end"), playmode_single=J(F1 + "/playmode_SinglePlayback/pl29_playmode.json").get("end"),
                      release=dict(result=rb["buildResult"], data_files=rb["dataFiles"], data_bytes=rb["dataBytes"], must_have=rb["mustHavePresent"], bake_absent=rb["bakeFilesAbsent"],
                                   exe_sha256=rb["exeSha256"], scene=rb["scene"], scene_sha256=rb["sceneSha256"]),
                      players={t: dict(frames=perf[t]["frames"], passed=perf[t]["pass"], errors=perf[t]["errors"], exceptions=perf[t]["exceptions"], ftGpu_ms=ph(t, "ftGpu"), ftCpuMain_ms=ph(t, "ftCpuMain"))
                               for t in ("pl33_1", "r01_1", "pl33_2", "r01_2")},
                      gpu=perf["r01_1"].get("gpu"), note_ja="PC の窓（1920×1080）。PSVR2 の GPU の時間は導入後に測る（未検証）"),
        "build_summary": rep["summary"],
        "copies": copies,
    }

    # 変種と評審（記録の部で加えた）
    sv = J(SE + "/metrics.json")
    hv = J(HV + "/metrics.json")
    um = J(JN + "/unified_measure.json")
    ur = um["painting_tstar_rhythm"]
    m["variants"] = {
        "note_ja": "進行役の決定（2026-10-02、Q24）で、2 つの変種を同じ時間枠の中で別々に作り、進行役の評審（2 件、Git 対象外の Unity/Build/Polish/33r01/_judge）が"
                   "同じ視点・同じ時刻で仕上げ33（修正の回 2）と並べて SWEEP を採った。値は各変種の候補の証拠（variant_*_metrics.json）と評審の数（judge_*.json）から写した",
        "SWEEP": dict(dir="Unity/Build/Polish/33r01/sweep", time_ja="11:36〜13:26（約 1.9 時間、作る部と修正の回 1 つ）",
                      how_ja="原画の爪 184 本を、原画のカメラの射線の上で深さを動的計画法で選んで立てた掃引の管（2 次元の道は一覧の中心線の 1.5 倍）にし、冠の爪を同じ断面の長い指 137 本に作り直した。膜と b区域の添え指は作らない",
                      entries=sv["claw_layer"]["entries"], vertices=sv["claw_layer"]["vertices"], triangles=sv["claw_layer"]["triangles"],
                      seat_t120_claw_px=sv["standing_images"]["seat_t120"]["claw"],
                      painting_rhythm=dict(claw_zone=ur["claw_zone_sweep"], bregion=ur["bregion_sweep"]),
                      gates_72_s12_p95_claws=sv["gates"]["72_s12_p95"]["after_claws"], raw_detail_with_claws={k: v["after_claws"] for k, v in sv["raw_detail_with_claws"].items()},
                      release_data_bytes=sv["release_data_bytes"]["sweep"],
                      player_hold_ftGpu_ms=dict(sweep=[sv["perf"]["sweep_1"]["Hold"]["ftGpu"], sv["perf"]["sweep_2"]["Hold"]["ftGpu"]],
                                                pl33=[sv["perf"]["pl33_1"]["Hold"]["ftGpu"], sv["perf"]["pl33_2"]["Hold"]["ftGpu"]])),
        "HOUDINI": dict(dir="Unity/Build/Polish/33r01/houdini", time_ja="11:36〜13:57（約 2.4 時間、作る部の試し try1〜v7、修正の回は使っていない）",
                        hython_ja="Steam の Houdini Indie の hython。版の表示は 22.0.459（指示の 22.0.429 と違う）。Program Files の 21.0.729 は使っていない",
                        how_ja="一覧の爪の中心線（原画の爪 184、b区域の添え指のうち t* で潰れない 101）を Houdini の CTRL のランプで巻きと細りを付けて射線の上で立ち上げ、断面を射線の向きへ 3 倍、頂の薄い帯と VDB の滑らかな和で根元を盛り上げた。仕上げ33 の膜 184・冠の爪 79 はそのまま",
                        fingers=hv["counts"]["fingers"], vertices=hv["counts"]["vertices_total"], triangles=hv["counts"]["triangles_total"], frames_bytes=hv["counts"]["frames_bytes"],
                        painting_rhythm=dict(claw_zone=ur["claw_zone_houdini"], bregion=ur["bregion_houdini"]),
                        gates_72_s12_p95_claws=hv["gates_painting_view"]["72_s12_p95"]["after_claws"],
                        raw_detail_with_claws={k: v["after_claws"] for k, v in hv["raw_detail_with_claws"].items()},
                        motion=dict(jumps_over_0p25m=hv["motion"]["jumps_over_0p25m"], jump_max_rel_root_m=hv["motion"]["jump_max_rel_root_m"]),
                        claw_layer_ms_painting=hv["gpu_claw_layer_ms"]["after"]["timing_ms"]["painting_1920x1080_msaa8"]["claws_ms"],
                        claw_layer_ms_2eyes=hv["gpu_claw_layer_ms"]["after"]["timing_ms"]["seat_toward_wave_2eyes_2064x2208_msaa4"]["claws_ms"]),
        "before_pl33_rhythm": dict(claw_zone=ur["claw_zone_before"], bregion=ur["bregion_before"]),
        "painting_rhythm": dict(claw_zone=ur["claw_zone_painting"], bregion=ur["bregion_painting"]),
        "judges": dict(count=2, adopted="SWEEP", reads_as_fingers_all_views=False, painting_claw_ring=False, gates_ok=True,
                       reason_ja="SWEEP だけが原画視点の外（座席・右の側面・後ろ 65° の稜・回り台の縁）の見え方を変え、仕上げ33 より軽い。Houdini は座席の頂の束だけで、側面・後ろ・回り台はほぼ変わらず、重い",
                       must_fix_count=11),
    }
    m["time"] = dict(box_ja="1 日（進行役の決定、Q24）", variants_ja="11:36〜13:57（2 つの変種を並べて作った）", judges_ja="約 13:59〜14:03（評審の数のファイルの時刻）",
                     fix_ja="14:05〜16:15（修正の回 1 と統合）", record_ja="16:15〜（記録の部）")
    json.dump(m, open(OUT + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    tools = ["Tools/GWWaveGen/pl33r01/r01_build.py", "Tools/GWWaveGen/pl33r01/r01_quick.py", "Tools/GWWaveGen/pl33r01/r01_measure.py",
             "Tools/GWWaveGen/pl33r01/r01_overlay.py", "Tools/GWWaveGen/pl33r01/r01_sheets.py", "Tools/GWWaveGen/pl33r01/r01_figs.py",
             "Tools/GWWaveGen/pl33r01/r01_record.py", "Tools/GWWaveGen/pl33r01/r01_run_unity.ps1", "Tools/GWWaveGen/pl33r01/r01_run_player.ps1",
             "Tools/GWWaveGen/pl33r01/sweep_build.py", "Tools/GWWaveGen/pl33r01/sweep_crown.py", "Tools/GWWaveGen/pl33r01/sweep_gates.py",
             "Tools/GWWaveGen/pl33r01/sweep_measure.py", "Tools/GWWaveGen/pl33r01/sweep_perf.py", "Tools/GWWaveGen/pl33r01/sweep_overlay.py",
             "Tools/GWWaveGen/pl33r01/r01_run_render.sh", "Tools/GWWaveGen/pl33r01/r01_run_eval.sh", "Tools/GWWaveGen/pl33r01/r01_run_unity_steps.sh",
             "Unity/Assets/GreatWave/Polish33R01/Editor/PL33R01Setup.cs", "Unity/Assets/GreatWave/Polish33R01/Editor/PL33R01ReleaseBuild.cs"]
    variant_tools = ["Tools/GWWaveGen/pl33r01/sweep_record.py", "Tools/GWWaveGen/pl33r01/sweep_sheets.py",
                     "Tools/GWWaveGen/pl33r01/sweep_run_unity.ps1", "Tools/GWWaveGen/pl33r01/sweep_run_player.ps1",
                     "Unity/Assets/GreatWave/Polish33R01/sweep/Editor/PL33R01SweepSetup.cs", "Unity/Assets/GreatWave/Polish33R01/sweep/Editor/PL33R01SweepReleaseBuild.cs",
                     "Tools/GWWaveGen/pl33r01/houdini_common.py", "Tools/GWWaveGen/pl33r01/houdini_prep.py", "Tools/GWWaveGen/pl33r01/houdini_build.py",
                     "Tools/GWWaveGen/pl33r01/houdini_deform.py", "Tools/GWWaveGen/pl33r01/houdini_unity.py", "Tools/GWWaveGen/pl33r01/houdini_measure.py",
                     "Tools/GWWaveGen/pl33r01/houdini_figs.py", "Tools/GWWaveGen/pl33r01/houdini_record.py",
                     "Unity/Assets/GreatWave/Polish33R01/houdini/Scripts/PL33R01HClawLook.cs", "Unity/Assets/GreatWave/Polish33R01/houdini/Editor/PL33R01HSetup.cs",
                     "Unity/Assets/GreatWave/Polish33R01/houdini/Editor/PL33R01HRender.cs"]
    inputs = ["Unity/Build/Polish/33/fix02/claws/ds33_claw_frames_f32.bin", "Unity/Build/Polish/33/fix02/claws/ds33_claw_layout.json",
              "Unity/Build/Polish/32/fix01/claws/ds33_claw_rig.json", "Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json",
              "Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", "Unity/Build/Polish/33r01/sweep/crown/ds33_claw_frames_f32.bin",
              "Unity/Build/Polish/33r01/sweep/crown/ds33_claw_layout.json"]
    outputs = ["Unity/Build/Polish/33r01/fix01/claws/ds33_claw_frames_f32.bin", "Unity/Build/Polish/33r01/fix01/claws/ds33_claw_tris_i32.bin",
               "Unity/Build/Polish/33r01/fix01/claws/ds33_claw_tri_attr_u16.bin", "Unity/Build/Polish/33r01/fix01/claws/ds33_claw_layout.json",
               "Unity/Assets/GreatWave/Polish33R01/Scenes/PL33R01_Release.unity", "Unity/Assets/GreatWave/Polish33R01/Scenes/PL33R01_SinglePlayback.unity",
               "Unity/Build/Polish/33r01/release/player/GreatWave50.exe"]
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    run = {
        "schema": "GreatWave.Polish33R01.run/1",
        "note_ja": "仕上げ33修正01 の修正の回 1 と統合。試し（try1〜try20、Unity/Build/Polish/33r01/fix01/try*）は記録の第 9 節。採る状態は既定の引数の r01_build.py（try20 と同じバイト）",
        "commands_adopted_chain": [
            "py -3.10 -B Tools/GWWaveGen/pl33r01/r01_build.py（出力 Unity/Build/Polish/33r01/fix01/claws。冠の爪は変種 SWEEP の sweep_crown の出力 Unity/Build/Polish/33r01/sweep/crown）",
            "bash Tools/GWWaveGen/pl33r01/r01_run_render.sh r_fix01 views,tt,t28,full,video（PL33Render、-pl32Claws Build/Polish/33r01/fix01/claws/ds33_claw_layout.json）",
            "bash Tools/GWWaveGen/pl33r01/r01_run_eval.sh（pl28u_regress・評価器 23 の 4 組・sweep_gates・sweep_measure・sweep_overlay・pl33f_measure・r01_quick・r01_measure）",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/r01_overlay.py --after-run Unity/Build/Polish/33r01/fix01/r_fix01 --after-claws Unity/Build/Polish/33r01/fix01/claws --out Unity/Build/Polish/33r01/fix01/measure",
            "bash Tools/GWWaveGen/pl33r01/r01_run_unity_steps.sh setup（PL33R01Setup.BuildScenes）",
            "bash Tools/GWWaveGen/pl33r01/r01_run_unity_steps.sh playmode（PL29PlayModeCheck、PL33R01_Release 400 s・PL33R01_SinglePlayback 120 s）",
            "bash Tools/GWWaveGen/pl33r01/r01_run_unity_steps.sh release（PL33R01ReleaseBuild.BuildAll）",
            "bash Tools/GWWaveGen/pl33r01/r01_run_unity_steps.sh players（仕上げ33 の exe と交互に 2 回ずつ、sweep_perf.py）",
            "py -3.10 -B Tools/GWWaveGen/pl33r01/r01_sheets.py ; py -3.10 -B Tools/GWWaveGen/pl33r01/r01_figs.py ; py -3.10 -B Tools/GWWaveGen/pl33r01/r01_record.py"],
        "tools": {t: sha(os.path.join(REPO, t)) for t in tools},
        "inputs_sha256": {t: sha(os.path.join(REPO, t)) for t in inputs},
        "outputs_sha256": {t: sha(os.path.join(REPO, t)) for t in outputs},
        "params": rep["params"],
        "versions": {"unity": "6000.4.3f1", "python": "3.10", "ffmpeg": "2024-12-19-git-494c961379-full_build"},
        "reference_reads_ja": "参照モデル（G:/research/model/wave_repair_zbrush2.obj）・写真のフォルダー（北斋参考）・G:/research/Wave Simulation は、この修正の回では読んでいない（数も形も使っていない）",
        "variants": {
            "note_ja": "2 つの変種の候補の証拠（コマンド・入出力の SHA-256）は variant_sweep_run.json・variant_houdini_run.json に写した。変種の描画と Unity の段の手順（run_render.sh・run_final.sh・run_unity_steps.sh）は Git 対象外の各変種のフォルダーにある。Houdini の変種のシーン pl33r01h_fingers*.hiplc は houdini_build.py が作る出力で、Git 対象外の Unity/Build/Polish/33r01/houdini に置いた（コミットしない）",
            "tools": {t: sha(os.path.join(REPO, t)) for t in variant_tools},
            "judges_ja": "評審の道具（_judge/numbers/judge_*.py・_judge/*.py）は進行役の評審の作業用で Git 対象外。数は judge_*.json に写した",
        },
        "time": m["time"],
        "git_head": head,
    }
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    big = [(f, os.path.getsize(os.path.join(OUT, f))) for f in os.listdir(OUT) if os.path.getsize(os.path.join(OUT, f)) > 5 * 1024 * 1024]
    print("R01_RECORD_DONE", len(os.listdir(OUT)), "files", "over5MB", big)


if __name__ == "__main__":
    main()
