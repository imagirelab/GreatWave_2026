# -*- coding: utf-8 -*-
"""仕上げ32 の作る部：metrics_build.json と run_build.json を書く（数は Git 対象外の出力から読み直す）。
記録の部（2026-10-02）で出力の名前を metrics.json・run.json から metrics_build.json・run_build.json に替えた（中身は作る部の 03:52 の出力のまま）。
群の最終の metrics.json・run.json は pl32r_record.py が書く。
使い方：py -3.10 -B Tools/GWWaveGen/pl32/pl32_record.py
"""
import glob
import hashlib
import json
import os

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/32"
E = REPO + "/Docs/Evidence/Polish/32"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def main():
    chk = J(B + "/list/pl32_claw_list_checks.json")
    ids = J(B + "/list/ds32_id_checks.json")
    cc = J(B + "/claws/ds33_claw_checks.json")
    wn = J(B + "/white/pl32_white_numpy.json")
    w31 = J(REPO + "/Unity/Build/Polish/31/white/pl31_white_numpy.json")
    wnp = J(B + "/white_nopin/pl31_white_numpy.json")
    ms = J(B + "/measure/pl32_measure_claws.json")
    dep = J(B + "/measure/pl32_claw_depth.json")
    bl = J(B + "/measure/pl32_bregion_lines.json")
    ind = J(B + "/indep/pl32_indep_check.json")
    rg = J(B + "/r_after/pl28u_regress.json")
    rg31 = J(REPO + "/Unity/Build/Polish/31/r_fx01/pl28u_regress.json")
    pm_s = J(B + "/playmode_single/pl29_playmode.json"); pm_r = J(B + "/playmode_release/pl29_playmode.json")
    rel = J(B + "/release/unity/pl32_build.json"); run = J(B + "/release/runs/main/report.json")
    ev = J(E + "/pl32_eval23.json")

    def gate(r):
        out = {}
        for s in ("t28_white", "t28_claws"):
            st = r["sets"][s]["strict"]["silhouettes_definition_reading"]
            lf = r["sets"][s]["large_form"]["s12"]
            out[s] = {"78": st["78"]["max_px"], "130": st["130"]["max_px"], "131": st["131"]["max_px"],
                      "132_s12_max": lf["132_max_px"], "72_s12_p95": lf["72_p95_px"],
                      "132_definition_max": st["132"]["max_px"], "72_definition_p95": st["72"]["p95_px"]}
        return out
    cnt = lambda c: {k: sum(1 for v in ev[c]["pl32"].values() if v["verdict"] == k) for k in ("pass", "fail", "record-only")}  # noqa: E731
    cnt31 = lambda c: {k: sum(1 for v in ev[c]["prev_pl31"].values() if v["verdict"] == k) for k in ("pass", "fail", "record-only")}  # noqa: E731
    sa, sb = ms["after"]["summary"], ms["before"]["summary"]
    metrics = dict(
        schema="GreatWave.Polish32.metrics/1", group="仕上げ32（設計32 白波群と ID・爪の一覧）", date="2026-10-02",
        state_ja="作る部（2026-10-02 02:11〜）。修正の回はまだ使っていない（作る部の中の試し直しは数えない）。進行役の自己評審の前。HMD 実機ではない",
        before_ja="前＝コミットした仕上げ31（4be87f6、2026-10-02 02:21:33 +0800。この群の着手の時は未コミットで、同じ場面とデータがコミットされた）。描画 r_before は仕上げ31 の最終の描画 r_fx01 と画素まで同じ（4 枚で差 0 画素を確かめた）",
        user_words_ja=["Q8「建议去调查北斋的这幅画的印刷流程以及历史，根据印刷流程去确定爪的基础色」→ ① 摺りの工程の調べ ② 爪の基礎色と IoU の定義（D25）",
                       "Q16・Q21 の b区域の浪尖の爪が原画視点で房として読めない"],
        backlog=["95", "96", "97", "98", "122", "123", "124", "125", "126", "127", "128", "144", "145", "261"],
        time_box_days=1.5,
        plan_rows={
            "1_print_study_base_colour_iou": dict(verdict="満たす（調べと決め直し。判断は進行役、利用者は未確認）",
                                                 claw_pixels_by_print_layer=dict(paper=0.738, light_blue_block=0.245, keyblock_line_edge=0.017, ai_mid=0.0, ai_dark=0.0),
                                                 base_colour_ja="紙の地（摺らない白）。陰は水色の版。藍中の段（仕上げ29 の下面）をやめた（pl32_claw_params.txt、PL32_Claw_Shade.mat）",
                                                 iou=chk["iou"]),
            "2_bregion_claws": dict(verdict="満たす（原画視点の房の帯として読める。b区域の形の 3 つの房は仕上げ28 の限界のまま）",
                                    bregion_claws_before=15, bregion_claws_after=sum(1 for c in J(E + "/pl32_claw_table.json")["claws"] if c["b_region"] and c["zone"] == "main"),
                                    candidates=chk["log"]["bregion"], dark_line_components=bl["values"],
                                    hidden_behind_sheet_before=[x for x in dep["before_design33"]["claws_mostly_behind_sheet"] if x in ("C158", "C159", "C160", "C161", "C163", "C164", "C165", "C166", "C167", "C168", "C170", "C171", "C172", "C173", "C175")]),
            "3_rebind_to_P28R2rec": dict(verdict="満たす", bound=ids["bound"], teleport=ids["teleport_count"], flicker=ids["flicker_count"], item129=ids["group_member_lost_count"],
                                         reprojection=ids["reprojection_tstar_display_px"], claw_depth=dep,
                                         claw_mesh=dict(item105_max_m=cc["item105"]["max_m"], item137_max_m=cc["item137"]["max_m"], item139_pass=cc["item139"]["pass_"],
                                                        vertices=cc["vertices"], teleport=dict(count=cc["teleport"]["count"], first=cc["teleport"]["first"])),
                                         b136=dict(after=wn["claws_136"]["after"].get("violations"), lag_max_s=wn["claws_136"]["after"].get("lag_max_s"),
                                                   design33_with_unpinned_order=wnp["claws_136"]["after"]["violations"]),
                                         b135=dict(prev=w31["b135"]["front"]["spearman_bins"], after=wn["b135"]["front"]["spearman_bins"]),
                                         b102=dict(surface=wn["b102_after"]["surface_fraction_max_increment"], world=wn["b102_after"]["world_fraction_max_increment"]),
                                         spray_pin=dict((k, v) for k, v in wn["pl32_white_spray_pin"].items() if k != "moved_list"),
                                         spray_emitters_white=ind["spray_emitters"]),
            "4_fit_regions_centerlines": dict(verdict="満たす（使える水準。輪郭 ≤4 px は爪の帯の幅とあわせて仕上げ33）",
                                              overlap_pairs=dict(ds32=chk["overlap_pairs_ds32_same_count"], pl32_over5px=chk["overlap_pairs_pl32"], pl32_any=chk["overlap_pairs_pl32_any"]),
                                              roots_inside_other=dict(ds32=15, pl32=len(chk["roots_inside_other_region"])), spikes_removed_px=chk["spikes_removed_px"],
                                              centre_refit=chk["centre_refit"], pale_fraction=chk["pale_fraction"]),
            "5_named_short_claws": dict(verdict="決めた", lengths=chk["lengths_named"], changes=chk["log"]["changes"], continues_past_root=chk["continues_past_root"]),
            "6_upper_row_mouth": dict(verdict="満たす（47 本に口の規則。C042 は目視で当てない）", changed=chk["log"]["upper_mouth"]["changed"]),
            "7_user100": dict(verdict="決めた（記録 第3節）"),
            "8_branch_reps_centre": dict(verdict="決めた（支の規則を領域によらない形に。T3 は 0 本のまま。代表は R1〜R10 のまま、船側中央は C095 のまま）",
                                         branch_rule=chk["branch_rule_ja"], types=dict((k, v) for k, v in J(B + "/claws/ds33_claw_rig.json")["stats"].items() if k == "types")),
        },
        backlog_values=dict(
            b95_98_centre_C095=dict(painting_inventory=dict(b95_root_wider=True, root_width_ref_px=17.2, tip_width_ref_px=14.0, b97_tip_dir_deg=141.8, b98_chord_deg=94.3),
                                    claw_band_tstar_after=sa["centre"], claw_band_tstar_before=sb["centre"], b96_ja="文言が手元にないので数えない"),
            b122_127_128_rows=dict(after=sa["rows"], before=sb["rows"]),
            b123_126_reps=dict(after=dict((k, v) for k, v in sa["reps"].items() if k != "per_claw"), before=dict((k, v) for k, v in sb["reps"].items() if k != "per_claw")),
            b144_145_261_all=dict(after=sa["all_outline"], before=sb["all_outline"], verdict="記録のみ"),
        ),
        painting_gates=dict(after=gate(rg), prev_pl31=gate(rg31),
                            cp1={"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558}, r2601={"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723},
                            note_ja="78・130・131 は爪なしの読み（定義の読み）。132・72 の関門は σ12 の大きな形（爪あり・爪なし）。CP1・26修正01 の値は仕上げ31 の記録の表"),
        evaluator23={c: dict(pl32=cnt(c), prev_pl31=cnt31(c)) for c in ("noline", "noline_noclaws", "line", "line_noclaws")},
        unity=dict(playmode_single=dict(rows=pm_s["rows"], sawPl29Shader=pm_s["sawPl29Shader"], bakePathsEmpty=pm_s["bakePathsEmptyAllFrames"]),
                   playmode_release=dict(rows=pm_r["rows"], sawPl29Shader=pm_r["sawPl29Shader"], bakePathsEmpty=pm_r["bakePathsEmptyAllFrames"]),
                   release=dict(result=rel["buildResult"], dataFiles=rel["dataFiles"], dataBytes=rel["dataBytes"], mustHave=rel["mustHavePresent"], bakeAbsent=rel["bakeFilesAbsent"],
                                absolutePaths=rel["absolutePaths"]),
                   player=dict(pass_=run["pass"], frames=run["frames"], errors=run["errors"], exceptions=run["exceptions"], realSeconds=run["realSeconds"],
                               prev_pl31_frames=50968)),
        independent=ind,
    )
    json.dump(metrics, open(E + "/metrics_build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    code = sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl32/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/pl32/*.ps1") + glob.glob(REPO + "/Tools/GWWaveGen/pl32/*.json")
                  + glob.glob(REPO + "/Tools/GWWaveGen/pl32/*.txt") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Editor/*.cs")
                  + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Scenes/*.unity") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish32/Materials/*.mat"))
    data = [B + "/list/ds32_claw_inventory.json", B + "/list/ds32_ids.json", B + "/list/ds32_claw_hist_f32.bin", B + "/list/pl32_bregion_candidates.json",
            B + "/claws/ds33_claw_rig.json", B + "/claws/ds33_claw_layout.json", B + "/claws/ds33_claw_frames_f32.bin", B + "/claws/ds33_claw_skel_f32.bin",
            B + "/white/hero_pkg/ds27_twhite_r32f.bin", B + "/white/hero_pkg/ds27_keypose.json", B + "/release/player/GreatWave50.exe",
            REPO + "/Docs/References/Met_JP1847_DP130155.jpg", REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json",
            REPO + "/Unity/Build/Design/32/list+ids/ds32_claw_inventory.json", REPO + "/Unity/Build/Polish/31/white/hero_pkg/ds27_twhite_r32f.bin",
            REPO + "/Unity/Build/Polish/31/spray/pl31_spray_table.json", REPO + "/Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json"]
    rj = dict(
        schema="GreatWave.Polish32.run/1",
        tools=dict(python="py -3.10（numpy 2.2.6、OpenCV 4.12.0、Pillow）", unity="6000.4.3f1 batchmode（Tools/GWWaveGen/pl32/run_pl32_unity.ps1、unity.lock）",
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", device="NVIDIA GeForce RTX 3080"),
        commands=[
            "set PYTHONIOENCODING=utf-8, PYTHONUTF8=1。<B> = G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/32",
            "py -3.10 -B Tools/GWWaveGen/pl31/pl31_white.py --claw-pin 0 --out <B>/white_nopin   # 誘導を外した白の順の測り（設計33 の爪で 136）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_white.py --claws G:/Unity/GreatWave_2026_Fresh/Unity/Build/Design/33/claws   # T_white（pl32_white_spray_pin）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_bregion.py   # b区域の爪の候補",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_claw_list.py   # 一覧（目視の判定は EYE と pl32_claw_eye.json）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_ids.py   # ID とシートへの結び付け（pl32_birth_all_corners）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_claws.py all   # 型・骨格（pl32_joint_front_window・支の判定）と帯（pl32_claw_anim.py の pl32_band_lift）",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_white.py --claws <B>/claws   # 136 を仕上げ32 の爪で測り直す（T_white は同じ SHA-256）",
            "powershell -File Tools/GWWaveGen/pl32/run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32Render.Render -Log r_after -Extra \"-pl29Out <B>/r_after <共通> -pl29ClawParamFile Tools/GWWaveGen/pl32/pl32_claw_params.txt -pl29HeroPkg Build/Polish/32/white/hero_pkg -pl31Spray Build/Polish/31/spray -pl32Claws Build/Polish/32/claws/ds33_claw_layout.json -pl29Only views,tt,t28,full,video\"",
            "powershell -File Tools/GWWaveGen/pl32/run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32Render.Render -Log r_before -Extra \"-pl29Out <B>/r_before <共通> -pl29ClawParamFile Tools/GWWaveGen/pl29/pl29_claw_params.txt -pl29HeroPkg Build/Polish/31/white/hero_pkg -pl31Spray Build/Polish/31/spray -pl29Only views,tt,t28,full,video\"",
            "bash <B>/run_eval.sh <B>/r_after   # pl28u_regress と評価器 23 の 4 組",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_measure_claws.py ; pl32_claw_depth.py ; pl32_indep_check.py",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_sheets.py --before <B>/r_before --after <B>/r_after --out Docs/Evidence/Polish/32 ; pl32_figs.py",
            "run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32Setup.BuildScenes -Log build_scenes2",
            "run_pl32_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode2_<single|release> -Extra \"-pl29Scene Assets/GreatWave/Polish32/Scenes/PL32_<SinglePlayback|Release>.unity -pl29Out <B>/playmode_<…> -pl29Limit 120|400\"",
            "run_pl32_unity.ps1 -Method GreatWave.Polish32.EditorTools.PL32ReleaseBuild.BuildAll -Log release_build2 ; powershell -File Tools/GWWaveGen/pl32/run_pl32_player.ps1 -Tag main",
            "py -3.10 -B Tools/GWWaveGen/pl32/pl32_record.py"],
        common_ja="<共通> ＝ -pl30Sea Build/Polish/30/sea -pl30SeaParamFile Tools/GWWaveGen/pl30/pl30_sea_params.txt -pl30LeftSwell Build/Polish/30/left_swell/pl30_left_swell.json "
                  "-pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile Tools/GWWaveGen/pl29/pl29_material_params.txt "
                  "-pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top -pl29VideoViews painting,seat,seat_toward_wave,side_left（手順の写し <B>/run_render.sh）",
        code_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in code},
        data_sha256={os.path.relpath(p, REPO).replace("\\", "/"): sha(p) for p in data if os.path.exists(p)},
        references_ja=["C. Korenberg「The making and evolution of Hokusai's Great Wave」（大英博物館、2020 年の論集の原稿の公開版。https://www.britishmuseum.org/sites/default/files/2022-03/korenberg_article-for_hokusai%20_edited_volume_final-2020_accessible.pdf、"
                       "読んだ PDF の SHA-256 3465148434ebdfaa2f641b5a153e87004cfb996be9e006046ce3ae3bba0f4e2a。リポジトリには入れない）",
                       "M. Vermeulen, L. Burgio, N. Vandeperre, E. Driscoll, M. Viljoen, J. Woo, M. Leona「Beyond the connoisseurship approach: creating a chronology in Hokusai prints using non-invasive techniques and multivariate data analysis」Heritage Science 8, 62 (2020), doi:10.1186/s40494-020-00406-y（書誌は Crossref で確かめ、本文は開けなかった。要旨と検索の要約）",
                       "Wikipedia「Thirty-six Views of Mount Fuji」「The Great Wave off Kanagawa」（G. C. Calza『Hokusai』p. 470、Bayou 2008 p. 130 の引用。二次の出典）",
                       "原画 Docs/References/Met_JP1847_DP130155.jpg（The Met JP1847、H. O. Havemeyer Collection）",
                       "爪形分析のフォルダー・参照モデル・参照の彫刻の写真・G:/research/Wave Simulation はこの群では開いていない。ds33_claw_rig.py が Q8 の例外の README 1 ファイル（G:/Unity/Ukeyoe_Claw/Docs/Research/Claw_Analysis/README.md）から 96 本の中央値を読む（設計33 と同じ。読み取りのみ）"])
    json.dump(rj, open(E + "/run_build.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("metrics_build", os.path.getsize(E + "/metrics_build.json"), "run_build", os.path.getsize(E + "/run_build.json"))


if __name__ == "__main__":
    main()
