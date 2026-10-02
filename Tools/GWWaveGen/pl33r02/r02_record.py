# -*- coding: utf-8 -*-
"""仕上げ33修正02：証拠の一式（Docs/Evidence/Polish/33R02）を作る。図・動画・元の数の JSON を写し、metrics.json（進行役の直すべき 3 つ → 値 → 判定）と
run.json（コマンド・道具の版・入出力の SHA-256）を書く（記録。新しい描画・計算はしない。pl33r01/r01_record.py を写して作り直した）。
進行役の評審 2 件と採否の決定（measure/r02_review.json）があれば、metrics.json の adoption と証拠の r02_review.json へ写す。進行役は採らなかった
（採用は仕上げ33修正01 のまま）ので、Unity の統合（Unity/Assets/GreatWave/Polish33R02 と r02_run_unity_steps.sh）はコミットせず、run.json には
SHA-256 だけを not_committed として残す（ファイルがなければ null）。

読むもの（Git 対象外）：Unity/Build/Polish/33r02（claws・r_final・measure・evidence・logs・setup・release・playmode_*）、前（仕上げ33修正01）の Unity/Build/Polish/33r01。
使い方：py -3.10 -B Tools/GWWaveGen/pl33r02/r02_record.py
"""
import hashlib
import json
import os
import shutil
import subprocess

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/33r02"
B1 = REPO + "/Unity/Build/Polish/33r01"
F1 = B1 + "/fix01"
OUT = REPO + "/Docs/Evidence/Polish/33R02"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sha_opt(p):
    return sha(p) if os.path.exists(p) else None


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def main():
    os.makedirs(OUT, exist_ok=True)
    copies = {}
    for f in sorted(os.listdir(B + "/evidence")):
        if f.endswith(".png") or f.endswith(".mp4"):
            shutil.copyfile(os.path.join(B, "evidence", f), os.path.join(OUT, f))
            copies[f] = rel(os.path.join(B, "evidence", f))
    shutil.copyfile(B + "/measure/fig_pl33r02_overlay_list.png", OUT + "/fig_pl33r02_overlay_list.png")
    copies["fig_pl33r02_overlay_list.png"] = rel(B + "/measure/fig_pl33r02_overlay_list.png")
    src = {"pl33r02_gates.json": B + "/measure/sweep_gates.json", "pl33r02_views_geometry.json": B + "/measure/sweep_measure.json",
           "pl33r02_overlay.json": B + "/measure/r02_overlay.json", "pl33f_measure_pl33r02.json": B + "/measure/pl33f_measure_r02.json",
           "r01_quick_pl33r02.json": B + "/measure/r01_quick_r02.json", "r01_measure.json": B + "/measure/r01_measure.json",
           "r02_seatfan.json": B + "/measure/r02_seatfan.json", "r02_quick_before_r01.json": B + "/measure/r02_quick_before_r01.json",
           "r02_quick_after.json": B + "/measure/r02_quick_after.json", "r02_perf.json": B + "/measure/r02_perf.json",
           "r02_report.json": B + "/claws/r02_report.json", "pl28u_regress.json": B + "/r_final/pl28u_regress.json",
           "render_report.json": B + "/r_final/pl33_render_report.json", "playmode_release.json": B + "/playmode_Release/pl29_playmode.json",
           "playmode_single.json": B + "/playmode_SinglePlayback/pl29_playmode.json", "release_build.json": B + "/release/unity/pl33r02_build.json",
           "setup.json": B + "/setup/pl33r02_setup.json", "r02_tries.json": B + "/measure/r02_tries.json",
           "r02_review.json": B + "/measure/r02_review.json"}
    for k, v in src.items():
        if os.path.exists(v):
            shutil.copyfile(v, os.path.join(OUT, k))
            copies[k] = rel(v)

    g = J(B + "/measure/sweep_gates.json")
    sm = J(B + "/measure/sweep_measure.json")
    pm = J(B + "/measure/pl33f_measure_r02.json")
    rm = J(B + "/measure/r01_measure.json")
    sf = J(B + "/measure/r02_seatfan.json")
    qb = J(B + "/measure/r02_quick_before_r01.json")
    qa = J(B + "/measure/r02_quick_after.json")
    qg = J(B + "/measure/r01_quick_r02.json")["geo"]
    qg1 = J(F1 + "/measure/r01_quick.json")["geo"]
    perf = J(B + "/measure/r02_perf.json")
    rep = J(B + "/claws/r02_report.json")
    lay = J(B + "/claws/ds33_claw_layout.json")
    lay1 = J(F1 + "/claws/ds33_claw_layout.json")
    rb = J(B + "/release/unity/pl33r02_build.json")
    rb1 = J(B1 + "/release/unity/pl33r01_build.json")
    ov = J(B + "/measure/r02_overlay.json")
    rh = pm["painting_tstar_rhythm"]
    x = lay["pl33r02"]
    rv = J(B + "/measure/r02_review.json") if os.path.exists(B + "/measure/r02_review.json") else None
    adoption = (dict(adopted=rv["adopted"], decision_ja=rv["decision_ja"], reasons_ja=rv["reasons_ja"],
                     judges=[{k: j[k] for k in ("judge", "better", "broom_gone", "painting_claw_ring", "summary_ja")} for j in rv["judges"]],
                     judges_detail="r02_review.json", handles_for_after_1029_ja=rv["handles_for_after_1029_ja"])
                if rv else dict(adopted=None, decision_ja="進行役の評審の前"))

    def kinds(L):
        return {k: sum(1 for c in L["claws"] if (c["id"][:2] if c["id"].startswith("W") else c["id"][0]) == k) for k in ("C", "K", "WF", "WC")}

    def pen(d):
        return {k: dict(entries=v["entries"], deepest_m=v["deepest"]) for k, v in d.items() if k[:2] in ("C_", "W_", "K_")}

    def acc(d):
        return {k: dict(events=v["n"], entries=v["entries"], worst=v["top"][0] if v["top"] else None) for k, v in d["accel_events"].items()}

    def ph(t, k):
        return {p: perf[t][p][k] for p in ("Formation", "Hold")}

    def seat(d):
        return {k: v for k, v in d.items() if k != "fingers"}

    views = sorted(sm["after"]["images"])
    m = {
        "schema": "GreatWave.Polish33R02.metrics/1",
        "number": {"group": "仕上げ33修正02", "design": "設計33 爪の造形（Q28 の［利用者の言葉］の修正の回 2）",
                   "backlog": "99〜101、103〜105、129、136〜141、180、200、204〜208、238、262（仕上げ33 と同じ）",
                   "decision_ja": "進行役の決定（2026-10-02、計画 §5.1：［利用者の言葉］の項目は 2 回目の修正の回を行ってよい）。時間枠 6 時間。SWEEP の作り方（r01_build.py）の上で直す",
                   "plan": "Docs/Design/Stage9_Plan_2026-09-26_ja.md §5.1・§5.2・§5.3 仕上げ33・§2.6"},
        "adoption": adoption,
        "before_ja": "仕上げ33修正01（コミット ebcc72c。採用の状態のまま）。爪の並び Unity/Build/Polish/33r01/fix01/claws、描画 Unity/Build/Polish/33r01/fix01/r_fix01",
        "after_ja": "仕上げ33修正02 の修正の回 2 の最終の候補（既定の引数の r02_build.py の出力。try12 とバイトまで同じ。進行役は採らなかった）。爪の並び Unity/Build/Polish/33r02/claws、描画 Unity/Build/Polish/33r02/r_final",
        "evidence_kind_ja": "Unity 6000.4.3f1 の PC オフスクリーン描画、Editor の Play モード 2 つ、Release のプレイヤーを PC（RTX 3080、1920×1080 の窓）で動かした結果、numpy・OpenCV・scipy の計算。HMD 実機ではない。利用者は見ていない",
        "projection_colour_used": False,
        "claw_layer": dict(vertices=lay["vertices"], triangles=lay["triangles"], entries=len(lay["claws"]), kinds=kinds(lay),
                           band_fallback=x["culled"], crowns_kept=x["crowns_kept"], crowns_culled_low=x["crowns_culled_low"], crowns_culled_few=len(x["crowns_culled_few"]),
                           webs_rim_skipped=x["webs_rim_skipped"], webs33_dropped_edge=x["webs33_dropped_edge"],
                           before=dict(vertices=lay1["vertices"], triangles=lay1["triangles"], entries=len(lay1["claws"]), kinds=kinds(lay1)),
                           frames_sha256=lay["files"]["frames"]["sha256"], frames_bytes=lay["files"]["frames"]["bytes"]),
        "must_fix": {
            "1_seat_broom_to_fan": dict(
                seat_fan=dict(before=seat(sf["before_r01"]), after=seat(sf["after_r02"]),
                              rule_ja="座席のカメラ（DS27 seat と同じ位置・回転・縦の視野 80°）へ t* の指（C…）の背骨を写し、描画で見える指の根元 → 先の画面の向きの単位ベクトルの平均の長さ R（1＝全部同じ向き＝箒、0＝ばらばら）。r02_seatfan.py"),
                finger_3d=dict(before=sm["before"]["geometry"]["C"], after=sm["after"]["geometry"]["C"]),
                seat_images=dict(t105=dict(before=sm["before"]["images"]["seat_t105"], after=sm["after"]["images"]["seat_t105"]),
                                 t120=dict(before=sm["before"]["images"]["seat_t120"], after=sm["after"]["images"]["seat_t120"])),
                verdict="一部（評審 2 件とも箒はなくなったとしたが、指が頂からほとんど立たず、外へ扇に開く読みはない。唇の下の冠の爪の扇は右下を向く羽の束のまま）",
                note_ja="箒（射線の向きに伸びた真っ直ぐな棒）と孤立した長い棒はなくなり、指は不揃いな長さで先が巻く。けれども、原画視点の一覧の道を守る限り、座席の画面で「立って見える」向きは原画のカメラの射線の向き（座席からは同じ点から放射する向き）と同じなので、立ち上がりを低くした（1 m 以上立つ指 45 → 0）。座席から外向きに扇に開いて立つ指は、原画視点の道から外れる造形が要る（限界）"),
            "2_painting_claw_ring": dict(
                rhythm=dict(painting=dict(claw_zone=rh["claw_zone_painting"], bregion=rh["bregion_painting"]),
                            before=dict(claw_zone=rh["claw_zone_build"], bregion=rh["bregion_build"]), after=dict(claw_zone=rh["claw_zone_fix"], bregion=rh["bregion_fix"])),
                list_overlay=dict(before=ov["before"], after=ov["after"]),
                lip_outline_white_notches_tstar=dict(before=qb["notch"], after=qa["notch"]),
                closed_rings=pm["closed_rings"], painting_outside_hero=pm["painting_outside_hero"],
                verdict="満たさない（評審 2 件とも、目で見て原画視点は t 9・10.5・12 s でほとんど変わらず、爪の輪の頂はない。小さな巻きの減りは目で見えず、暗い線の成分は原画 398 から少し離れた（266 → 256）。数では唇の白い欠け 246 → 165 px・閉じた輪 13 → 8・精度 0.851 → 0.868 が少し良く、水色は 0.432 で原画 0.412 を越えた（+4.8%、5% の内））",
                note_ja="唇の輪郭の白い欠けは 246 → 165 px（線のない膜が輪郭をまたぐ所はなくした。残りは輪郭をまたぐ指の白い胴で、指自身の縁の線が回る）。水色の版は 0.399 → 0.432（原画 0.412）。"
                        "大きな白い爪の輪（藍の舌を縁取る白い鉤）は読めない：一覧の爪の所の主役波の地が白なので、白い指は線だけの小さな巻きに見える（原画では爪の間が藍。主役波の色の範囲の問題で、原画カメラからの投影の色は使えない）"),
            "3_fingers_not_fur_72m": dict(
                crowns=dict(before=sum(1 for c in lay1["claws"] if c["id"].startswith("K")) - len(lay1["pl33r01_fix01"]["crowns_culled_low"]), after=x["crowns_kept"],
                            section_scale_before=dict(root=1.4, tip=2.2), section_scale_after=dict(root=2.4, tip=3.2)),
                white_body_px_t120={v: dict(before=sm["before"]["images"][v + "_t120"]["white_body"], after=sm["after"]["images"][v + "_t120"]["white_body"])
                                    for v in ("side_left", "side_right", "top", "back65")},
                claw_px_t120={v: dict(before=sm["before"]["images"][v + "_t120"]["claw"], after=sm["after"]["images"][v + "_t120"]["claw"])
                              for v in ("side_left", "side_right", "top", "back65")},
                ridge_ringed_fraction_tstar={k: dict(before=v["build"], after=v["fix"]) for k, v in pm["ridge_ringed_fraction_tstar"].items()},
                crown_geometry=dict(before=sm["before"]["geometry"]["K"], after=sm["after"]["geometry"]["K"]),
                outline_rule_ja="縁の線は設計38 の決まりのまま（押し出し幅 = max(min(d × 0.0012866, 0.3 m), d × 1.5 px の角)）。72 m で約 0.093 m（世界寸法の上限 0.3 m に届かない）",
                verdict="一部（冠の爪は回り台 180〜330°・後ろ 65°・真上・右の側面で数えられる太い鉤になった。左の側面の唇の側は毛のまま、真上と回り台 60° の唇の側は粒や屑の点々、回り台 0° は唇の長い垂れる指が短く崩れた小さな後退、後ろ 65° の一部は角ばった柱に見える）"),
        },
        "keep": {
            "gates": dict(gates=g["gates"], raw_detail_with_claws=g["raw_detail_with_claws"], eval23=g["eval23"], verdict="通る（≤ 4 px）。72 σ12 p95 の爪ありは 3.9059 → 3.5694"),
            "crown_hidden_from_painting_cam": pm["geometry"]["fix"]["crown_painting_cam_visibility"],
            "id_growth_continuity": dict(r01_measure={k: {t: {kk: rm[k][t][kk] for kk in ("entries", "frame_flips", "ring_twists_gt60", "accel_events_gt0p15", "accel_entries", "accel_worst", "teleports_gt0p5m", "nan")}
                                                         for t in ("C", "K", "W")} for k in ("33r01/fix01/claws", "33r02/claws")},
                                         accel_judge_formula=dict(before=acc(qg1), after=acc(qg)), motion_pl33f=pm["geometry"]["fix"]["motion"],
                                         note_ja="id の並びと成長の割合（仕上げ33 の帯の長さの割合）は前のまま。帯に戻した 2 本（C087・C092）は仕上げ33 の帯の頂点そのもの"),
            "penetration_vertex": dict(before=pen(qg1), after=pen(qg)),
            "vr_budget": dict(vertices=dict(before=lay1["vertices"], after=lay["vertices"]), triangles=dict(before=lay1["triangles"], after=lay["triangles"]),
                              release_data_bytes=dict(before=rb1["dataBytes"], after=rb["dataBytes"]),
                              players={t: dict(frames=perf[t]["frames"], passed=perf[t]["pass"], errors=perf[t]["errors"], exceptions=perf[t]["exceptions"],
                                               ftGpu_ms=ph(t, "ftGpu"), ftCpuMain_ms=ph(t, "ftCpuMain")) for t in ("r01_1", "r02_1", "r01_2", "r02_2")},
                              note_ja="PC の窓（1920×1080、RTX 3080）。90 Hz の予算 11.1 ms。PSVR2 の GPU の時間は導入後に測る（未検証）"),
        },
        "views_images": {k: dict(before=sm["before"]["images"][k], after=sm["after"]["images"][k]) for k in views},
        "unity": dict(playmode_release=J(B + "/playmode_Release/pl29_playmode.json").get("end"), playmode_single=J(B + "/playmode_SinglePlayback/pl29_playmode.json").get("end"),
                      release=dict(result=rb["buildResult"], data_files=rb["dataFiles"], data_bytes=rb["dataBytes"], must_have=rb["mustHavePresent"], bake_absent=rb["bakeFilesAbsent"],
                                   exe_sha256=rb["exeSha256"], scene=rb["scene"], scene_sha256=rb["sceneSha256"])),
        "build_summary": rep["summary"],
        "copies": copies,
    }
    if os.path.exists(B + "/measure/r02_tries.json"):
        m["tries"] = J(B + "/measure/r02_tries.json")
    tm = J(B + "/measure/r02_time.json") if os.path.exists(B + "/measure/r02_time.json") else {}
    tm = {k: v.replace("採る状態", "最終の候補") if isinstance(v, str) else v for k, v in tm.items()}
    if rv:
        tm["record_ja"] = tm.get("record_ja", "").replace("17:54〜", "17:54〜17:59")
        tm.update(rv["time_ja"])
    m["time"] = tm
    json.dump(m, open(OUT + "/metrics.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    tools = ["Tools/GWWaveGen/pl33r02/r02_build.py", "Tools/GWWaveGen/pl33r02/r02_seatfan.py", "Tools/GWWaveGen/pl33r02/r02_quick.py",
             "Tools/GWWaveGen/pl33r02/r02_overlay.py", "Tools/GWWaveGen/pl33r02/r02_sheets.py", "Tools/GWWaveGen/pl33r02/r02_figs.py",
             "Tools/GWWaveGen/pl33r02/r02_record.py", "Tools/GWWaveGen/pl33r02/r02_run_unity.ps1", "Tools/GWWaveGen/pl33r02/r02_run_player.ps1",
             "Tools/GWWaveGen/pl33r02/r02_run_render.sh", "Tools/GWWaveGen/pl33r02/r02_run_eval.sh",
             "Tools/GWWaveGen/pl33r01/r01_build.py", "Tools/GWWaveGen/pl33r01/sweep_build.py", "Tools/GWWaveGen/pl33r01/r01_quick.py",
             "Tools/GWWaveGen/pl33r01/r01_measure.py", "Tools/GWWaveGen/pl33r01/sweep_gates.py", "Tools/GWWaveGen/pl33r01/sweep_measure.py",
             "Tools/GWWaveGen/pl33r01/sweep_overlay.py", "Tools/GWWaveGen/pl33r01/sweep_perf.py"]
    # 採らない状態の Unity の統合（コミットしない。作業ツリーに未追跡で残す）
    not_committed = ["Tools/GWWaveGen/pl33r02/r02_run_unity_steps.sh",
                     "Unity/Assets/GreatWave/Polish33R02/Editor/PL33R02Setup.cs", "Unity/Assets/GreatWave/Polish33R02/Editor/PL33R02ReleaseBuild.cs",
                     "Unity/Assets/GreatWave/Polish33R02/Scenes/PL33R02_Release.unity", "Unity/Assets/GreatWave/Polish33R02/Scenes/PL33R02_SinglePlayback.unity"]
    inputs = ["Unity/Build/Polish/33/fix02/claws/ds33_claw_frames_f32.bin", "Unity/Build/Polish/33/fix02/claws/ds33_claw_layout.json",
              "Unity/Build/Polish/32/fix01/claws/ds33_claw_rig.json", "Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json",
              "Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", "Unity/Build/Polish/33r01/sweep/crown/ds33_claw_frames_f32.bin",
              "Unity/Build/Polish/33r01/sweep/crown/ds33_claw_layout.json"]
    outputs = ["Unity/Build/Polish/33r02/claws/ds33_claw_frames_f32.bin", "Unity/Build/Polish/33r02/claws/ds33_claw_tris_i32.bin",
               "Unity/Build/Polish/33r02/claws/ds33_claw_tri_attr_u16.bin", "Unity/Build/Polish/33r02/claws/ds33_claw_layout.json",
               "Unity/Build/Polish/33r02/release/player/GreatWave50.exe"]
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    run = {
        "schema": "GreatWave.Polish33R02.run/1",
        "note_ja": "仕上げ33修正02 の修正の回 2 と統合。試し（try1〜try12、Unity/Build/Polish/33r02/try*・r_try*）は記録の第 7 節と r02_tries.json。最終の候補は既定の引数の r02_build.py（try12 とバイトまで同じ）。"
                   "進行役は採らなかった（採用は仕上げ33修正01 のまま。metrics.json の adoption と r02_review.json）",
        "adopted": rv["adopted"] if rv else None,
        "not_committed_ja": "採らない状態の Unity の統合（Polish33R02 の Editor のコードと場面、それを回す r02_run_unity_steps.sh）はコミットしない（作業ツリーに未追跡で残す）。SHA-256 だけを残す",
        "not_committed_sha256": {t: sha_opt(os.path.join(REPO, t)) for t in not_committed},
        "commands_chain": [
            "py -3.10 -B Tools/GWWaveGen/pl33r02/r02_build.py（出力 Unity/Build/Polish/33r02/claws）",
            "bash Tools/GWWaveGen/pl33r02/r02_run_render.sh r_final views,tt,t28,full,video（PL33Render、-pl32Claws Build/Polish/33r02/claws/ds33_claw_layout.json）",
            "bash Tools/GWWaveGen/pl33r02/r02_run_eval.sh（pl28u_regress・評価器 23 の 4 組・sweep_gates・sweep_measure・sweep_overlay・pl33f_measure・r01_quick・r01_measure・r02_seatfan・r02_quick）",
            "py -3.10 -B Tools/GWWaveGen/pl33r02/r02_overlay.py --after-run Unity/Build/Polish/33r02/r_final --after-claws Unity/Build/Polish/33r02/claws --out Unity/Build/Polish/33r02/measure",
            "bash Tools/GWWaveGen/pl33r02/r02_run_unity_steps.sh setup / playmode / release / players（PL33R02Setup・PL29PlayModeCheck・PL33R02ReleaseBuild・仕上げ33修正01 の exe と交互に 2 回ずつ。この道具と Polish33R02 はコミットしない）",
            "py -3.10 -B Tools/GWWaveGen/pl33r02/r02_sheets.py ; py -3.10 -B Tools/GWWaveGen/pl33r02/r02_figs.py ; py -3.10 -B Tools/GWWaveGen/pl33r02/r02_record.py"],
        "tools": {t: sha(os.path.join(REPO, t)) for t in tools},
        "inputs_sha256": {t: sha(os.path.join(REPO, t)) for t in inputs},
        "outputs_sha256": {t: sha(os.path.join(REPO, t)) for t in outputs},
        "params": rep["params"],
        "versions": {"unity": "6000.4.3f1", "python": "3.10", "ffmpeg": "2024-12-19-git-494c961379-full_build"},
        "reference_reads_ja": "写真のフォルダー（G:/research/reality scan/北斋参考）の 2 枚（左45.jpg・正面图.jpg）を、読み取りのみで画面で見た（写しは作っていない。見たのは指の作り方：塊から外へ放射し、先が巻き、太く、頂と唇に密）。参照モデル（G:/research/model/wave_repair_zbrush2.obj）と G:/research/Wave Simulation は読んでいない。生成器は OBJ を読まない（F13-1）。"
                              + ("評審：" + rv["reference_reads_ja"] if rv else ""),
        "time": m["time"],
        "git_head": head,
    }
    json.dump(run, open(OUT + "/run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    big = [(f, os.path.getsize(os.path.join(OUT, f))) for f in os.listdir(OUT) if os.path.getsize(os.path.join(OUT, f)) > 5 * 1024 * 1024]
    print("R02_RECORD_DONE", len(os.listdir(OUT)), "files", "over5MB", big)


if __name__ == "__main__":
    main()
