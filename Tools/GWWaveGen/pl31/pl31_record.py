# -*- coding: utf-8 -*-
"""仕上げ31 の記録（修正01 を含む）：数の JSON の写しと metrics.json・run.json を Docs/Evidence/Polish/31 に書く（新しい計算はしない）。
使い方：py -3.10 -B Tools/GWWaveGen/pl31/pl31_record.py
"""
import glob
import hashlib
import json
import os
import shutil
import sys

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/31"
B30 = REPO + "/Unity/Build/Polish/30"
EV = REPO + "/Docs/Evidence/Polish/31"
R = B + "/r_fx01"
R0 = B + "/r_final2"
RB = B + "/r_before2"


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def J(p):
    return json.load(open(p, encoding="utf-8-sig"))


def ev23(root):
    out = {}
    for c in ("noline", "noline_noclaws", "line", "line_noclaws"):
        p = glob.glob(root + "/eval23/*off_" + c + "/metrics.json")[0]
        it = J(p)["items"]
        v = {k: x["verdict"] for k, x in it.items()}
        out[c] = dict(pass_=sum(1 for x in v.values() if x == "pass"), fail=sum(1 for x in v.values() if x == "fail"), verdicts=v,
                      sky=[dict(item=k, target=m.get("target"), value_max_px=m.get("value_max_px"), p95_px=m.get("p95_px"), verdict=m.get("verdict"))
                           for k in ("76", "212", "213") if k in it for m in it[k]["measures"]])
    return out


def main():
    os.makedirs(EV, exist_ok=True)
    W = J(B + "/white/pl31_white_numpy.json")
    W0 = J(B + "/white_before/pl31_white_numpy.json")
    Wr0 = J(B + "/white_r0/pl31_white_numpy.json")
    G = J(B + "/spray/pl31_spray_generate_log.json")
    Gr0 = J(B + "/spray_r0/pl31_spray_generate_log.json")
    M = J(B + "/measure_fx01/pl31_measure.json")
    Mr0 = J(B + "/measure_final2/pl31_measure.json")
    C150 = J(B + "/fix01/check150_spray.json")
    C150r0 = J(B + "/fix01/check150_spray_r0.json")
    CLr0 = J(B + "/fix01/claws_r0.json")
    EMR = J(B + "/fix01/emitters_robust.json")
    SIZ = J(B + "/fix01/spray_sizes.json")
    RG = J(R + "/pl28u_regress.json")
    RG30 = J(B30 + "/fix02/r_final/pl28u_regress.json")
    RR = J(R + "/pl31_render_report.json")
    RRB = J(RB + "/pl31_render_report.json")
    SET = J(B + "/setup/pl31_setup.json")
    PMS = J(B + "/fx_playmode_single/pl29_playmode.json")
    PMR = J(B + "/fx_playmode_release/pl29_playmode.json")
    REL = J(B + "/release/unity/pl31_build.json")
    RUN = J(B + "/release/runs/fx01/report.json")
    # 修正前（仕上げ31 の 1 回目）の写しは消す（名前を替えて残す）
    for old in ("pl31_measure_pass1.json", "release_run_main.json"):
        if os.path.exists(os.path.join(EV, old)):
            os.remove(os.path.join(EV, old))
    for src, dst in ((B + "/white/pl31_white_numpy.json", "pl31_white_numpy.json"), (B + "/white_before/pl31_white_numpy.json", "pl31_white_numpy_before.json"),
                     (B + "/white_r0/pl31_white_numpy.json", "pl31_white_numpy_r0.json"),
                     (B + "/white/pl31_white_onset.json", "pl31_white_onset.json"), (B + "/spray/pl31_spray_generate_log.json", "pl31_spray_generate_log.json"),
                     (B + "/spray_r0/pl31_spray_generate_log.json", "pl31_spray_generate_log_r0.json"),
                     (B + "/measure_fx01/pl31_measure.json", "pl31_measure.json"), (B + "/measure_final2/pl31_measure.json", "pl31_measure_r0.json"),
                     (B + "/fix01/measure_drop_merged3.json", "pl31_measure_fx01_drop.json"),
                     (B + "/fix01/check150_spray.json", "pl31_check150.json"), (B + "/fix01/check150_spray_r0.json", "pl31_check150_r0.json"),
                     (B + "/fix01/claws_r0.json", "pl31_claws_r0.json"), (B + "/fix01/emitters_robust.json", "pl31_emitters_robust.json"),
                     (B + "/fix01/spray_sizes.json", "pl31_spray_sizes.json"),
                     (R + "/pl28u_regress.json", "pl28u_regress_after.json"), (B + "/setup/pl31_setup.json", "pl31_setup.json"),
                     (B + "/release/unity/pl31_build.json", "release_build.json"), (B + "/release/runs/fx01/report.json", "release_run.json"),
                     (B + "/fx_playmode_single/pl29_playmode.json", "playmode_single.json"), (B + "/fx_playmode_release/pl29_playmode.json", "playmode_release.json"),
                     (R + "/pl31_render_report.json", "render_report_after.json"), (RB + "/pl31_render_report.json", "render_report_before.json")):
        shutil.copyfile(src, os.path.join(EV, dst))
    for f in ("pl31_spray_tone0_frames.json", "pl31_spray_tone1_frames.json", "pl31_spray_f8_tone0_frames.json", "pl31_spray_f8_tone1_frames.json"):
        shutil.copyfile(B + "/spray/" + f, os.path.join(EV, f))
    gates = {}
    for k in ("t28_white", "t28_claws"):
        lf = RG["sets"][k]["large_form"]
        gates[k] = dict(sha_same_as_pl30=RG["sets"][k]["t28_sha256"] == RG30["sets"][k]["t28_sha256"], s12=lf["s12"])
    e_after, e_30, e_r0 = ev23(R), ev23(B30 + "/fix02/r_final"), ev23(R0)
    b102 = W["b102_after"]; b102_0 = W0["b102_before"]; b102_r0 = Wr0["b102_after"]
    cl = W["claws_136"]
    metrics = dict(
        schema="GreatWave.Polish31.metrics/1", group="仕上げ31（設計31 白波の発生と飛沫）", date="2026-10-02",
        state_ja="作る部と修正の回 1 回（計画 §5.1。この群に［利用者の言葉］の項目はないので 1 回）。修正01 は自己評審の指摘 9 件（白の 1 画素の線、尾の頂の糸、計画の 4 行、"
                 "前の記述、爪の芽、150 の検査の範囲、仕上げ30 のコミット、放出点の Hash1、149 の子）。自己評審の must-fix への修正の回 1 の後、"
                 "記録の部（2026-10-02）で証拠と提出の一覧を整えた。進行役の再評審の前。HMD 実機ではない",
        user_words_ja="計画 §5.3 仕上げ31：「この群に、利用者の言葉でまだ満たしていないものはない」。［利用者の言葉］の項目は 0 件（2 回目の修正の回はない）。"
                      "Q28（色に原画カメラの投影を使わない）は守る：白は材質 PL29 の白の範囲 ∧ T_white ≤ τ、飛沫の色は限定色 2 段を粒の t* の世界の高さで決める",
        record_phase=dict(
            date="2026-10-02",
            checks_ja=["証拠の PNG 20 枚がどれも 1920×1080、MP4 5 本がどれも 5 MB 以下（最大 1.69 MB）",
                       "run.json の code_sha256（18 ファイル）が今のファイルと同じ（記録の部で直した pl31_sheets.py・pl31_record.py は再実行で更新）",
                       "PL31 の場面 2 つの guid 78 個：追跡済みの .meta 73、この群の PL31SprayFollow.cs.meta 1、パッケージ 2（XR Origin・TrackedPoseDriver）、組み込み 2",
                       "場面の SHA-256（PL31_Release fae6da09…・PL31_SinglePlayback 468512a0…）、T_white 76e00d0b…、exe 5be81b3f… が metrics.json と同じ",
                       "追跡済みのファイルの変更 0（git status）。README.md・Docs/Progress/README.md は変えていない"],
            sheets_ja="視点ごとの前後の図 7 枚の見出しの 2 行目が右端で切れていた（「原画の点 210」の後）ので、pl31_sheets.py で見出しを短くし、前・後の中身を図の下の欄に折り返した。"
                      "拡大の段は切り抜きの縦横の比の高さで上に詰めた。回り台の 4 枚は作り直してもバイト単位で同じ（同じ描画から作れることの確かめ）。動画は作り直していない"),
        before_ja="前＝コミットした仕上げ30（b9140db、2026-10-01 22:31:47 +0800、修正02 を含む）。前の描画 r_before2（22:57）はこのコミットの後に -pl31Old 1 で作った",
        backlog=["102", "135", "149", "150", "151", "152", "172", "173", "174", "176", "201", "220", "223", "226", "230"],
        time_box_days=1.0,
        plan_rows={
            "1 白の出現・発生の表・放出点を G_p28rec で作り直す": dict(result="作り直した（修正01 で白の順を作り直した）", twhite_sha256=W["twhite_out"]["sha256"],
                                                           onset_records=W["onset"]["records"], judgement="満たす"),
            "2 放出点を終態が白の頂点に限る": dict(emitters_zone_white=G["summary"]["emitters_zone_white"], emitters_total=G["summary"]["emitters_total"],
                                          emitters_white_before_emit=G["summary"]["emitters_white_before_emit"],
                                          emitters_hash_robust=G["summary"]["emitters_zone_robust"], emitters_r0=EMR["spray_r0"], emitters_fx01=EMR["spray"],
                                          before_ja="設計31：63／186 が白でない頂点。修正前（仕上げ31 の 1 回目）：2,495 とも白の範囲だが、房の Hash1 によらない白の範囲は 2,462（この道具の下限の読み）",
                                          judgement="満たす（2,495／2,495 が Hash1 によらない白の範囲で、放出の時に白）"),
            "3 原画の白い点の取り出しを手の注記と照合・区域の外の点・主役波の前に来る 6 点": dict(eye=G["extract"], over_hero=G["place"]["over_hero"],
                                                                         over_hero_white_kept=G["place"]["over_hero_white_kept"], judgement="満たす（目の照合 1 回。二人目なし）"),
            "4 飛沫の数・大小・分布（2〜3 千個）、設計39 の ③ の子": dict(total=G["summary"]["total"], parents=G["summary"]["parents"], children=G["summary"]["children"],
                                                          child_rules=G["children"]["rules"], child_rules_r0=Gr0["children"]["rules"],
                                                          painting_tstar_components_outside_dots=M["spray"]["after"]["components_outside_dots"],
                                                          radius_m=G["summary"]["radius_m"], radius_p10_50_90=SIZ,
                                                          judgement="満たす（数 2,500。子の半径は原画の点に合わせた親の分布 ×0.85〜1.15、原画の点の中の子は点の円に収まる大きさ。"
                                                                    "原画視点の分布は原画の点の中 200（点ごと 2 個まで）・白の上 2,090 で、t* に原画にない点 0。原画視点の外の分布は原画に手本がなく、唇のまわりの飛沫として目で確かめた）"),
            "5 151 の ΔE00": dict(colour_reading_before=G["colour"]["de00_white_only"], colour_reading_after=G["colour"]["de00_two_tones"],
                                 render_reading_before=M["spray"]["before"]["de00_render_at_dots"], render_reading_after=M["spray"]["after"]["de00_render_at_dots"],
                                 judgement="改善（≤5 は全部では満たさない。記録のみ）"),
            "6 135・177 を今の動きで測る、F8 の見え方": dict(b135_before=W0["b135"]["front"]["spearman_bins"], b135_r0=Wr0["b135"]["front"]["spearman_bins"],
                                                b135_after=W["b135"]["front"]["spearman_bins"], b135_back=W["b135"]["back"]["spearman_bins"],
                                                b135_bins_after=W["b135"]["front"]["bins_t_median"],
                                                b177_all_rise=W["b177"]["all_rise"], b177_rise_min_m=min(W["b177"]["rise_m"]),
                                                f8_variant=G["f8_variant"], f8_used=G["emit"]["f8"],
                                                judgement="測った（135：0.93。爪の根元の白（pl31_white_claw_pin）で F 1.6〜2.0 の区間が早まる。177 合格、F8 は図で比べた）"),
            "7 V3 の寿命が 150 で延びない粒": dict(extendable_x1_6=G["emit"]["v3_extendable"], not_extendable=G["emit"]["v3_not_extendable"], before_ja="設計35：105／186 が同じ",
                                             judgement="測った（134／205 は延ばせない。V3 は比べの版で場面に入らない）"),
            "8 評価器に飛沫と爪の層を分けるマスク": dict(decision_ja="評価器の ID には飛沫を入れない今の読みを続け、飛沫の印は『飛沫あり − 飛沫なし』の差の画像で別に数える（pl31_measure.py）。評価器そのものは変えない",
                                               judgement="決めた"),
            "9 白の出現の精度（美術優先31 の残り）": dict(b102=dict(surface_max=b102["surface_fraction_max_increment"], world_max=b102["world_fraction_max_increment"],
                                                         over2_surface=b102["surface_frames_over_2pct"], over2_world=b102["world_frames_over_2pct"],
                                                         first_white_t=b102["first_white_t_exact"], all_white_t=b102["all_white_t"]),
                                                 b102_before=dict(surface_max=b102_0["surface_fraction_max_increment"], world_max=b102_0["world_fraction_max_increment"],
                                                                  over2_surface=b102_0["surface_frames_over_2pct"], over2_world=b102_0["world_frames_over_2pct"]),
                                                 b102_r0=dict(surface_max=b102_r0["surface_fraction_max_increment"], world_max=b102_r0["world_fraction_max_increment"]),
                                                 unity_outside_final_white_max_px=M["white"]["after_summary"]["outside_final_white_max"],
                                                 unity_nonwhite_changed_max_px=M["white"]["after_summary"]["nonwhite_changed_max"], judgement="満たす"),
        },
        fix01=dict(
            white_order=W["pl31_white_order"], claw_pin=W["pl31_white_claw_pin"], rate_cap=W["pl31_white_rate_cap"],
            claws_136=dict(rule_ja=cl["rule_ja"], before_pl30={k: v for k, v in cl["before"].items() if k != "worst"},
                           r0={k: v for k, v in CLr0.items() if k != "worst"}, after={k: v for k, v in cl["after"].items() if k != "worst"},
                           judge_reading_ja="自己評審の読み：修正前 32／131（前 8）、最大 +1.68 s（C171）"),
            check150=dict(rule_ja=C150["rule_ja"], r0={k: C150r0[k] for k in ("inside", "inside_tstar_hold", "contact", "never_left", "inside_by_kind", "gap_0p2s_m")},
                          after={k: C150[k] for k in ("inside", "inside_tstar_hold", "contact", "never_left", "inside_by_kind", "gap_0p2s_m")},
                          judge_reading_ja="自己評審の読み：修正前 9 粒が水へ入り 8 粒が t* の保持で水の中"),
            children=G["children"], children_r0=Gr0["children"]["rules"],
            painting_white_fraction_unity={k: round(v["frac"], 3) for k, v in M["white"]["after"].items() if k.startswith("painting")},
            painting_white_fraction_unity_before={k: round(v["frac"], 3) for k, v in M["white"]["before"].items() if k.startswith("painting")},
        ),
        painting_gates=dict(after=gates, cp1=dict(g78=2.772, g130=1.968, g131=1.814, g132=1.326, g72=1.558), ds26r01=dict(g78=1.641, g130=1.953, g131=1.798, g132=1.574, g72=1.723),
                            note_ja="t* の ID の画像（t28_white・t28_claws）が仕上げ30 と SHA-256 まで同じなので、形の関門の値は仕上げ30 と同じ"),
        evaluator23=dict(after={k: dict(pass_=v["pass_"], fail=v["fail"], sky=v["sky"]) for k, v in e_after.items()},
                         r0={k: dict(pass_=v["pass_"], fail=v["fail"]) for k, v in e_r0.items()},
                         pl30={k: dict(pass_=v["pass_"], fail=v["fail"], sky=v["sky"]) for k, v in e_30.items()},
                         changed_vs_pl30={c: {k: (e_after[c]["verdicts"][k], e_30[c]["verdicts"].get(k)) for k in e_after[c]["verdicts"] if e_after[c]["verdicts"][k] != e_30[c]["verdicts"].get(k)}
                                          for c in e_after}),
        unity=dict(render_after_seconds=RR["secondsTotal"], render_protected_unchanged=RR["protectedUnchanged"], spray_data=RR["sprayData"], hero_twhite_sha256=RR["heroTwhiteSha256"],
                   before_spray=RRB.get("sprayData"), playmode_single_rows=PMS.get("rows"), playmode_release_rows=PMR.get("rows"),
                   scenes=[dict(to=x["to"], sha256=x["toSha256"]) for x in SET["scenes"]],
                   release=dict(result=REL.get("buildResult"), data_files=REL.get("dataFiles"), data_bytes=REL.get("dataBytes"), mustHave=REL.get("mustHavePresent"),
                                bake_absent=REL.get("bakeFilesAbsent"), absolute_paths=REL.get("absolutePaths"), scene_sha256=REL.get("sceneSha256"), exe_sha256=REL.get("exeSha256")),
                   player_run=dict(pass_=RUN.get("pass"), frames=RUN.get("frames"), errors=RUN.get("errors"), exceptions=RUN.get("exceptions"), quitCause=RUN.get("quitCause"))),
        measure_r0=dict(components_outside_dots=Mr0["spray"]["after"]["components_outside_dots"], px=Mr0["spray"]["after"]["px_outside_dots"]),
    )
    json.dump(metrics, open(os.path.join(EV, "metrics.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    files = {}
    for p in sorted(glob.glob(REPO + "/Tools/GWWaveGen/pl31/*.py") + glob.glob(REPO + "/Tools/GWWaveGen/pl31/*.ps1") + glob.glob(REPO + "/Tools/GWWaveGen/pl31/*.json")
                    + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish31/*/*.cs") + glob.glob(REPO + "/Unity/Assets/GreatWave/Polish31/Scenes/*.unity")):
        files[p.replace(REPO + "/", "").replace("\\", "/")] = sha(p)
    data = {}
    for p in (B + "/white/pl31_twhite_r32f.bin", B + "/white/pl31_white_onset_f32.bin", B + "/white/hero_pkg/ds27_keypose.json", B + "/white/hero_pkg/ds27_twhite_r32f.bin",
              B + "/white_r0/pl31_twhite_r32f.bin",
              B + "/spray/pl31_spray_tone0_frames.bin", B + "/spray/pl31_spray_tone1_frames.bin", B + "/spray/pl31_spray_table.json",
              B + "/spray/pl31_spray_f8_tone0_frames.bin", B + "/spray/pl31_spray_f8_tone1_frames.bin", B + "/spray_r0/pl31_spray_table.json",
              REPO + "/Unity/Build/Polish/28/G_p28rec/art_on/ds27_pos_rgba16.bin", REPO + "/Unity/Build/Polish/28/G_p28rec/art_on/ds27_twhite_r32f.bin",
              REPO + "/Unity/Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin", REPO + "/Tools/GWWaveGen/pl29/pl29_material_params.txt",
              REPO + "/Unity/Build/Design/33/claws/ds33_claw_rig.json", REPO + "/Unity/Build/Design/33/claws/ds33_claw_skel_f32.bin",
              REPO + "/Docs/References/Met_JP1847_DP130155.jpg", R + "/full/painting_t120_off.png", R + "/full/painting_t120_nospray.png",
              B + "/release/player/GreatWave50.exe"):
        data[p.replace(REPO + "/", "")] = sha(p)
    run = dict(schema="GreatWave.Polish31.run/1",
               tools=dict(python="py -3.10 (numpy 2.2.6, OpenCV 4.12.0, SciPy)", unity="6000.4.3f1 batchmode（Tools/GWWaveGen/pl31/run_pl31_unity.ps1、unity.lock）",
                          ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", device=RR.get("device")),
               commands=[
                   "# 修正01（採った版）。<B> = G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/31。修正前の出力は white_r0・spray_r0・r_final2・measure_final2 に名前を替えて残した",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_white.py   # 既定：--order-mode patch --patch-ks 1 --patch-kb 1 --claw-pin 0.6 --claw-pin-v 1.5 --claw-pin-cone 0.6 --rate-cap 0.018",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_white.py --order 0 --rate-cap 0 --out <B>/white_before   # 前（G_p28rec の T_white）の測り",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_spray.py   # 既定：--child-mode targeted --check full（1 回目の描画 fix01/r_s4 の前）",
                   "run_pl31_unity.ps1 -Method GreatWave.Polish31.EditorTools.PL31Render.Render -Log fx_s4 -Extra \"-pl29Out <B>/fix01/r_s4 <共通> -pl29HeroPkg Build/Polish/31/white/hero_pkg -pl31Spray <B>/spray -pl29Views painting -pl29Only full\"",
                   "（子の描画の確かめ：pl31_measure.spray_stage で原画の点の円の外に見えた塊を、fix01/r_s4（17 塊）・r_fx01 の 1 回目（1）・子を点ごと 2 個までにした後の fix01/r_s5（8）・fix01/r_s6（1）から順に合わせた（fix01/measure_drop_merged3.json、27 塊）。子の置き方の値の変更：child_per_dot 7→5・dot_child_max 4→2・dot_depth_m 0.6→0.35・over_white_tries 9000→10500（回り台 30〜60° で点の射線に並んだ子が短い点線に見えたため）",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_spray.py --drop-visible <B>/fix01/measure_drop_merged3.json   # 採った飛沫",
                   "run_pl31_unity.ps1 ... -Log r_fx01 -Extra \"-pl29Out <B>/r_fx01 <共通> -pl29HeroPkg Build/Polish/31/white/hero_pkg -pl31Spray <B>/spray <視点> -pl29Only views,tt,t28,full,video,white\"",
                   "run_pl31_unity.ps1 ... -Log r_fx01x -Extra \"-pl29Out <B>/r_fx01x ... -pl29Only views,tt -pl29Times 6.5,7,7.5,8,8.5,9.5,10,11,11.5\"（前：fix01/r_bx に -pl31Old 1、修正前：fix01/r_r0x に -pl29HeroPkg Build/Polish/31/white_r0/hero_pkg -pl31Spray <B>/spray_r0）",
                   "run_pl31_unity.ps1 ... -Log r_fx01_f8 / r_fx01_f8t（-pl31SprayStem pl31_spray_f8 の有無、-pl29Only views -pl29Times 11,11.6,12）",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_measure.py --before <B>/r_before2 --after <B>/r_fx01 --out <B>/measure_fx01",
                   "bash <B>/run_eval.sh <B>/r_fx01   # pl28u_regress と評価器 23 の 4 組",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_fx01_check150.py --spray <B>/spray --out <B>/fix01/check150_spray.json（修正前は --spray <B>/spray_r0）",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_sheets.py --before <B>/r_before2 --after <B>/r_fx01 --out Docs/Evidence/Polish/31",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_figs.py --before <B>/r_before2 --after <B>/r_fx01 --f8 <B>/r_fx01_f8 --after-f8times <B>/r_fx01_f8t --out Docs/Evidence/Polish/31",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_fx01_figs.py --before <B>/fix01/r_bx --before-main <B>/r_before2 --r0 <B>/fix01/r_r0x --r0-main <B>/r_final2 --after <B>/r_fx01x --after-main <B>/r_fx01 --out Docs/Evidence/Polish/31",
                   "run_pl31_unity.ps1 -Method GreatWave.Polish31.EditorTools.PL31Setup.BuildScenes -Log fx_build_scenes",
                   "run_pl31_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log fx_playmode_single|fx_playmode_release -Extra \"-pl29Scene Assets/GreatWave/Polish31/Scenes/PL31_<SinglePlayback|Release>.unity -pl29Out <B>/fx_playmode_<…> -pl29Limit 120|400\"",
                   "run_pl31_unity.ps1 -Method GreatWave.Polish31.EditorTools.PL31ReleaseBuild.BuildAll -Log fx_release_build ; powershell -File Tools/GWWaveGen/pl31/run_pl31_player.ps1 -Tag fx01",
                   "py -3.10 -B Tools/GWWaveGen/pl31/pl31_record.py"],
               render_sh_ja="<共通> は記録の第 12 節（-pl30Sea・-pl30SeaParamFile・-pl30LeftSwell・-pl29Attr・-pl29ClawShade 1・-pl29ParamFile・-pl29ClawParamFile）。前は -pl31Old 1。手順の写し run_render.sh・run_eval.sh は Git 対象外の Unity/Build/Polish/31/",
               code_sha256=files, data_sha256=data,
               references_ja="参照モデル（wave_repair_zbrush2.obj）・参照の彫刻の写真・G:\\research\\Wave Simulation・爪形分析は、この群（修正01 を含む）では開いていない。原画はリポジトリの Docs/References/Met_JP1847_DP130155.jpg だけ")
    json.dump(run, open(os.path.join(EV, "run.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ok", len(files), len(data))


if __name__ == "__main__":
    main()
