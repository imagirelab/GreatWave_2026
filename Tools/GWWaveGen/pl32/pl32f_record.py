# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1：metrics_fix01.json と run_fix01.json を書き、数の JSON を Docs/Evidence/Polish/32 へ写す（数は Git 対象外の出力から読み直す）。
動きの検査（judge_motion：根元に対する帯の頂点のコマの間の動きの最大と弧長の 1 コマの跳び）は、前（設計33 の爪）・作る部・修正01 を同じ関数で数え直す。
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32f_record.py
"""
import glob
import hashlib
import json
import os

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/32"
F = B + "/fix01"
E = REPO + "/Docs/Evidence/Polish/32"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def W(name, obj):
    json.dump(obj, open(os.path.join(E, name), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))


def judge_motion(cd):
    """根元に対する帯の頂点のコマの間の動き（見えるコマ）と弧長の 1 コマの跳び（増え > 0.1 m かつ前後のコマの増えの 3 倍超）。"""
    lay = J(cd + "/ds33_claw_layout.json")
    nv, nf, nc = lay["vertices"], lay["frames"], len(lay["claws"])
    V = np.memmap(cd + "/" + lay["files"]["frames"]["file"], dtype="<f4", mode="r", shape=(nf, nv, 3))
    SK = np.memmap(cd + "/" + lay["files"]["skel"]["file"], dtype="<f4", mode="r", shape=(nf, nc, 36))
    vis = SK[:, :, 34] > 0.5
    arcl = SK[:, :, 35].astype(np.float64)
    best, top, jumps = 0.0, [], []
    for i, c in enumerate(lay["claws"]):
        o, n = c["vert_offset"], c["vert_count"]
        X = np.asarray(V[:, o:o + n], np.float64)
        rel = X - X[:, :1]
        mv = np.linalg.norm(np.diff(rel, axis=0), axis=2).max(1)
        both = vis[1:, i] & vis[:-1, i]
        mv = np.where(both, mv, 0.0)
        top.append((c["id"], int(np.argmax(mv)) + 1, round(float(mv.max()), 4)))
        da = np.diff(arcl[:, i])
        for f in range(1, nf - 2):
            if vis[f - 1, i] and vis[f, i] and vis[f + 1, i]:
                g = da[f]
                if g > 0.1 and g > 3.0 * max(abs(da[f - 1]), abs(da[f + 1]), 0.01):
                    jumps.append((c["id"], f + 1, round(float(g), 4)))
    top.sort(key=lambda x: -x[2])
    return dict(claws=nc, rel_move_max_m=top[0][2], top=top[:5], growth_jumps=jumps, growth_jump_count=len(jumps))


def gate(r):
    out = {}
    for s in ("t28_white", "t28_claws"):
        st = r["sets"][s]["strict"]["silhouettes_definition_reading"]
        lf = r["sets"][s]["large_form"]["s12"]
        out[s] = {"78": st["78"]["max_px"], "130": st["130"]["max_px"], "131": st["131"]["max_px"],
                  "132_s12_max": lf["132_max_px"], "72_s12_p95": lf["72_p95_px"],
                  "132_definition_max": st["132"]["max_px"], "72_definition_p95": st["72"]["p95_px"]}
    return out


def verdict_12(f, b, p):
    """審査の指摘 12 の判定の文。値は同じ項目の数（fix01・build・prev_pl31 の爪あり）から書く（修正の回 2：文と数の食い違いを直した）。"""
    f, b, p = f["t28_claws"], b["t28_claws"], p["t28_claws"]
    d132 = f["132_definition_max"] - p["132_definition_max"]
    d72 = f["72_s12_p95"] - p["72_s12_p95"]
    if abs(d132) < 5e-5:
        t132 = "仕上げ31 と同じ %.4f px（作る部 %.4f px）" % (f["132_definition_max"], b["132_definition_max"])
    else:
        t132 = "作る部 %.4f → %.4f px で、仕上げ31 の %.4f px %s（%+.3f px）" % (
            b["132_definition_max"], f["132_definition_max"], p["132_definition_max"], "より大きい" if d132 > 0 else "より小さい", d132)
    s132 = (" で仕上げ31 と同じ" if abs(f["132_s12_max"] - p["132_s12_max"]) < 5e-5 else "（仕上げ31 %.4f px）" % p["132_s12_max"])
    return ("一部（72 σ12 p95 の爪ありは作る部 %.4f → %.4f px、仕上げ31 %.4f px より %+.3f px（関門 ≤ 4 px の内）。"
            "記録のみの 132 定義の読みの爪ありは%s。132 σ12 の最大は %.4f px%s）"
            % (b["72_s12_p95"], f["72_s12_p95"], p["72_s12_p95"], d72, t132, f["132_s12_max"], s132))


def eval23(run):
    res = {}
    for c in ("noline", "noline_noclaws", "line", "line_noclaws"):
        it = J(run + "/eval23/off_%s/metrics.json" % c)["items"]
        cnt = {k: sum(1 for v in it.values() if v.get("verdict") == k) for k in ("pass", "fail", "record-only")}
        vals = {}
        for k in ("132", "72", "132_claws", "72_claws", "213"):
            if k in it:
                m = (it[k].get("measures") or [{}])[0]
                vals[k] = dict(verdict=it[k].get("verdict"), max_px=m.get("value_max_px"), p95_px=m.get("p95_px"))
        res[c] = dict(counts=cnt, values=vals, verdicts={k: v.get("verdict") for k, v in it.items()})
    return res


def main():
    chk = J(F + "/list/pl32_claw_list_checks.json")
    chk0 = J(B + "/list/pl32_claw_list_checks.json")
    ids = J(F + "/list/ds32_id_checks.json")
    rig = J(F + "/claws/ds33_claw_rig.json")
    cc = J(F + "/claws/ds33_claw_checks.json")
    cc0 = J(B + "/claws/ds33_claw_checks.json")
    wn = J(F + "/white/pl32_white_numpy.json")
    ms = J(F + "/measure/pl32_measure_claws.json")
    ms0 = J(B + "/measure/pl32_measure_claws.json")
    mf = J(F + "/measure/pl32f_measure.json")
    dep = J(F + "/measure/pl32_claw_depth.json")
    ind = J(F + "/indep/pl32_indep_check.json")
    rg = J(F + "/r_fix01/pl28u_regress.json"); rg0 = J(B + "/r_after/pl28u_regress.json")
    rg31 = J(REPO + "/Unity/Build/Polish/31/r_fx01/pl28u_regress.json")
    perf = J(F + "/perf_out.json")
    pm_s = J(F + "/playmode_single/pl29_playmode.json"); pm_r = J(F + "/playmode_release/pl29_playmode.json")
    rel = J(B + "/release/unity/pl32_build.json")
    corr = J(F + "/list/ds32_user100_correspondence_pl32f.json")
    jm = dict(prev_design33_pl31=judge_motion(REPO + "/Unity/Build/Design/33/claws"), build=judge_motion(B + "/claws"), fix01=judge_motion(F + "/claws"))
    print("judge_motion", {k: (v["rel_move_max_m"], v["growth_jump_count"]) for k, v in jm.items()})
    ev_f, ev_b = eval23(F + "/r_fix01"), eval23(B + "/r_after")
    sa, sb, s31 = ms["after"]["summary"], ms0["after"]["summary"], ms["before"]["summary"]

    # 数の JSON を写す
    W("pl32f_list_checks.json", chk)
    W("pl32f_user100_correspondence.json", dict(schema=corr.get("schema"), pl32f=corr["pl32f"], source_registration=corr.get("source_registration"),
                                                note_ja="設計32 の対応表（数値）に、仕上げ32 修正の回 1 の位置合わせのし直しと扱いの決め直しを足したもの。画像・マスクは複製していない"))
    W("pl32f_id_checks.json", ids)
    W("pl32f_claw_rig_summary.json", dict(stats=rig["stats"], params=rig["params"], dropped_white_root=rig["dropped_white_root"],
                                          claws=[{k: c[k] for k in ("id", "row", "type", "parent", "children", "segments", "joint_how", "joint_kind", "free_why", "len_m")} for c in rig["claws"]]))
    W("pl32f_claw_checks.json", {k: v for k, v in cc.items() if k not in ("reprojection_tstar_record_only", "web_join")} |
      dict(reprojection_tstar_record_only={k: v for k, v in cc["reprojection_tstar_record_only"].items() if k != "per_claw"},
           judge_motion_same_function=jm))
    W("pl32f_white_numpy.json", dict(claws_136=wn["claws_136"], b102_after={k: v for k, v in wn["b102_after"].items() if not isinstance(v, list)},
                                     b135_front_spearman=wn["b135"]["front"].get("spearman_bins"), t_white_sha256=sha(F + "/white/hero_pkg/ds27_twhite_r32f.bin")))
    W("pl32f_measure_claws.json", ms)
    W("pl32f_measure.json", mf)
    W("pl32f_claw_depth.json", dep)
    W("pl32f_indep_check.json", ind)
    W("pl28u_regress_fix01.json", rg)
    W("pl32f_eval23.json", dict(fix01=ev_f, build=ev_b))
    W("pl32f_perf.json", dict(rule_ja="Release のプレイヤーを PC で、仕上げ31 のプレイヤーと交互に 2 組（自動の試し main、上限なしのフレーム）。フェーズごとの CPU 主スレッド・GPU のフレーム時間の中央値（ms）",
                              runs=perf, judge_build_ja="作る部（修正の前）は審査の組の測りで 50,609 → 41,721 フレーム（−17.6%）、記録の 1 回は 42,010"))
    W("playmode_single_fix01.json", pm_s); W("playmode_release_fix01.json", pm_r)
    W("release_build_fix01.json", rel)
    W("pl32f_setup.json", J(F + "/setup/pl32_setup.json"))
    W("render_report_fix01.json", J(F + "/r_fix01/pl32_render_report.json"))

    metrics = dict(
        schema="GreatWave.Polish32.metrics_fix01/1", group="仕上げ32 修正の回 1（設計32 白波群と ID・爪の一覧）", date="2026-10-02",
        state_ja="修正の回 1（計画 §5.1：［利用者の言葉］は 2 回まで、ほかは 1 回）。進行役の自己評審の前。HMD 実機ではない",
        before_ja="比べの相手：前＝コミットした仕上げ31（4be87f6、r_before）、作る部＝仕上げ32 の作る部（r_after、審査の対象）、修正01＝この回（fix01/r_fix01）",
        corrections_ja=["修正の回 2（2026-10-02、記録のみ・作り直しなし）：must_fix 12_72_132 の判定の文が「132 定義の読みは仕上げ31 と同じ 5.2998 に戻った」と"
                        "書いていたが、同じ項目の数（fix01 の t28_claws 132_definition_max）は 5.3771 px で仕上げ31 より +0.077 px。文を同じ項目の数から"
                        "書くようにした（verdict_12）。数・画像・動画・Unity の出力は変えていない"],
        must_fix={
            "1_seat_claws_left_edge": dict(verdict="直した（藍の上の棒・くねった白は消えた。稜の帯のはみ出しは細い線として残る）",
                                           over_indigo_seat_spot=dict(prev=mf["claws_over_indigo"]["before"]["seat_t120_spot"], build=mf["claws_over_indigo"]["build"]["seat_t120_spot"],
                                                                      fix01=mf["claws_over_indigo"]["fix01"]["seat_t120_spot"])),
            "2_stw_upper_left": dict(verdict="直した", over_indigo_stw_spot=dict(prev=mf["claws_over_indigo"]["before"]["seat_toward_wave_t120_spot"],
                                                                               build=mf["claws_over_indigo"]["build"]["seat_toward_wave_t120_spot"],
                                                                               fix01=mf["claws_over_indigo"]["fix01"]["seat_toward_wave_t120_spot"])),
            "3_rice_grains_t105": dict(verdict="直した（閉じた輪 4 → 1。根元で線を開いた）", closed_rings=mf["bregion_closed_rings"]),
            "4_bregion_tufts_user_words": dict(verdict="一部（根元が開いた鉤と水色の版の雲。房の形と藍の窓は主役波の形・材質で、仕上げ33 と 10/29 の後の一覧へ）",
                                               lines=mf["bregion_lines_tstar"], mizuiro=mf["bregion_mizuiro_fraction_tstar"], bregion_claws_built=sa["rows"]["b区域"]["claws"],
                                               second_fix_round_ja="［利用者の言葉］の 2 回目の修正の回は使っていない（残す）"),
            "5_6_C095_95_97": dict(verdict="直した（95・97・98 とも満たす）", fix01=sa["centre"], build=sb["centre"], prev=s31["centre"]),
            "7_reps_123_126": dict(verdict="一部（≤4 px 5／10、幅は領域の 0.71〜1.14 倍）", fix01={k: v for k, v in sa["reps"].items() if k != "per_claw"},
                                   build={k: v for k, v in sb["reps"].items() if k != "per_claw"}),
            "8_root_continuation": dict(verdict="直した（18 → 11。残る 11 は目視の判定つき）", final=chk["continues_past_root"], build=chk0["continues_past_root"],
                                        root_extend=chk["fix01"]["root_extend"]),
            "9_user100_branch": dict(verdict="満たす（加えた 15・まとめた 3・対応 7・加えない 6、不確か 7 → 4。T3 1 本）",
                                     additions=chk["fix01"]["user100_additions"], reregister=chk["fix01"]["reregister"], types=rig["stats"]["types"]),
            "10_motion": dict(verdict="直した（瞬間移動 0、成長の跳び 0、根元に対する動きの最大は仕上げ31 より小さい）", judge_motion=jm,
                              teleport=dict(fix01=cc["teleport"]["count"], build=cc0["teleport"]["count"])),
            "11_performance": dict(verdict="直した（フレーム 約 +81%、導入・接近・余韻の CPU 主スレッド −0.3〜−1.0 ms）", runs=perf),
            "12_72_132": dict(verdict=verdict_12(gate(rg), gate(rg0), gate(rg31)),
                              fix01=gate(rg), build=gate(rg0), prev_pl31=gate(rg31)),
            "13_outline_144_145_261": dict(verdict="記録のみ（≤4 px 96／184 本、幅は領域の 0.91〜1.00 倍）", fix01=sa["all_outline"], build=sb["all_outline"],
                                           rows=dict(fix01=sa["rows"], build=sb["rows"])),
        },
        claws=dict(built=len(rig["claws"]), dropped_white_root=len(rig["dropped_white_root"]), free_why=rig["stats"]["free_why"],
                   item105_max_m=cc["item105"]["max_m"], item137_max_m=cc["item137"]["max_m"], item139_pass=cc["item139"]["pass_"], vertices=cc["vertices"],
                   b136=wn["claws_136"]["after"].get("violations"), b136_zone_rooted=wn["claws_136"]["after"].get("zone_rooted"),
                   b102=dict(surface=wn["b102_after"]["surface_fraction_max_increment"], world=wn["b102_after"]["world_fraction_max_increment"]),
                   depth=dep.get("fix01_pl32"), ids=dict(bound=ids["bound"], teleport=ids["teleport_count"], flicker=ids["flicker_count"], item129=ids["group_member_lost_count"])),
        list=dict(counts=chk["counts"], overlap_pairs_over5=chk["overlap_pairs_pl32"], roots_inside_other=chk["roots_inside_other_region"], iou=chk["iou"]),
        painting_gates=dict(fix01=gate(rg), build=gate(rg0), prev_pl31=gate(rg31),
                            cp1={"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558}, r2601={"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723}),
        evaluator23=dict(fix01={k: v["counts"] for k, v in ev_f.items()}, build={k: v["counts"] for k, v in ev_b.items()}),
        unity=dict(playmode_single=dict(rows=pm_s.get("rows"), sawPl29Shader=pm_s.get("sawPl29Shader")),
                   playmode_release=dict(rows=pm_r.get("rows"), sawPl29Shader=pm_r.get("sawPl29Shader")),
                   release=dict(result=rel.get("buildResult"), dataFiles=rel.get("dataFiles"), dataBytes=rel.get("dataBytes"), mustHave=rel.get("mustHavePresent"))),
        independent=ind,
    )
    W("metrics_fix01.json", metrics)
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl32/pl32f_*.py") + [REPO + "/Tools/GWWaveGen/pl32/" + x for x in
                  ("pl32_claw_list.py", "pl32_ids.py", "pl32_sheets.py", "pl32_indep_check.py", "pl32_claw_depth.py", "pl32_claw_eye.json")]
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/*/*.cs") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Shaders/*.shader")
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Scenes/*.unity") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Materials/*.mat"))
    data = [F + "/list/ds32_claw_inventory.json", F + "/list/ds32_ids.json", F + "/claws/ds33_claw_rig.json", F + "/claws/ds33_claw_layout.json",
            F + "/claws/ds33_claw_frames_f32.bin", F + "/claws/ds33_claw_skel_f32.bin", F + "/claws/ds33_claw_tris_i32.bin", F + "/claws/ds33_claw_tri_attr_u16.bin",
            B + "/white/hero_pkg/ds27_twhite_r32f.bin", B + "/white/pl31_zone_vertex.npy", B + "/release/player/GreatWave50.exe",
            REPO + "/Docs/References/Met_JP1847_DP130155.jpg", REPO + "/Unity/Build/Design/32/list+ids/ds32_user100_correspondence.json"]
    user_files = {}
    for u in sorted(chk["fix01"]["reregister"].keys()):
        for nm in ("original.png", "fill_mask.png"):
            p = "G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3/%s/%s" % (u, nm)
            if os.path.exists(p):
                user_files[p] = sha(p)
    p = "G:/research/爪形分析/final_100_claw_structural_points_v2/final_points_long.csv"
    user_files[p] = sha(p)
    rj = dict(
        schema="GreatWave.Polish32.run_fix01/1",
        tools=dict(python="py -3.10（numpy 2.2.6、OpenCV 4.12.0、Pillow）", unity="6000.4.3f1 batchmode（run_pl32_unity.ps1、unity.lock）",
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", device="NVIDIA GeForce RTX 3080"),
        commands=[
            "set PYTHONIOENCODING=utf-8, PYTHONUTF8=1。<B> = G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/32、<F> = <B>/fix01",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_claw_list.py --fix01 --out <F>/list   # 一覧の直し（pl32f_list_steps.py、目視の判定は pl32_claw_eye.json の pl32f_cont）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_ids.py --list <F>/list   # ID とシートへの結び付け",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32f_claws.py all   # rig（pl32f_claw_rig.py）と帯（pl32f_claw_anim.py）。出力 <F>/claws",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_white.py --claws <F>/claws --out <F>/white   # 136（T_white は作る部と同じ SHA-256）",
            "bash <F>/run_render.sh r_fix01 views,tt,t28,full,video   # PL32Render に -pl32Claws Build/Polish/32/fix01/claws/ds33_claw_layout.json -pl32Look 1（試しの描画は test1〜7）",
            "bash <B>/run_eval.sh <F>/r_fix01   # pl28u_regress と評価器 23 の 4 組",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_measure_claws.py --after-claws <F>/claws --after-inv <F>/list/ds32_claw_inventory.json --out <F>/measure/pl32_measure_claws.json",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32f_measure.py ; PL32F_CLAWS=<F>/claws PL32F_OUT=<F>/measure/pl32_claw_depth.json py -3.10 -B Tools/GWWaveGen/pl32/pl32_claw_depth.py ; PL32_BASE=<F> py -3.10 -B Tools/GWWaveGen/pl32/pl32_indep_check.py",
            "run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32Setup.BuildScenes -Log fix01_build_scenes -Extra \"-pl32Out <F>/setup\"",
            "run_pl32_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log fix01_playmode_<single|release> -Extra \"-pl29Scene Assets/GreatWave/Polish32/Scenes/PL32_<SinglePlayback|Release>.unity -pl29Out <F>/playmode_<…> -pl29Limit 120|400\"",
            "run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32ReleaseBuild.BuildAll -Log fix01_release_build",
            "仕上げ31 と交互に 2 組：powershell -File Tools/GWWaveGen/pl31/run_pl31_player.ps1 -Tag pl32fix01_pair<3|4> ; powershell -File Tools/GWWaveGen/pl32/run_pl32_player.ps1 -Tag fix01_pair<3|4> ; py -3.10 <F>/perf.py …",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_sheets.py --before <B>/r_before --after <F>/r_fix01 --out Docs/Evidence/Polish/32 --fix01 ; py -3.10 -B Tools/GWWaveGen/pl32/pl32f_figs.py",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32f_record.py"],
        code_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in code},
        data_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in data if os.path.exists(p)},
        read_only_user_files_sha256=user_files,
        read_only_note_ja=("位置合わせのし直しで、利用者の爪形分析のフォルダー（Q8 の例外、読み取りのみ）の 9 本の切り抜き・マスクと構造点の表を読んだ（メモリの中だけ。"
                           "画像・マスクはリポジトリと成果物へ複製していない。数は変換と NCC だけ）。参照モデル・参照の彫刻の写真・G:/research/Wave Simulation は開いていない"),
        prohibited_paths_ja="AGENTS.md の禁止の場所は開いていない（ds33 の型の数を写した README 1 ファイルは設計33 と同じ Q8 の例外）")
    W("run_fix01.json", rj)
    print("metrics_fix01", os.path.getsize(E + "/metrics_fix01.json"), "run_fix01", os.path.getsize(E + "/run_fix01.json"))


if __name__ == "__main__":
    main()
