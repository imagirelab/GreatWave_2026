# -*- coding: utf-8 -*-
"""仕上げ30 の記録：Docs/Evidence/Polish/30/metrics.json（バックログ項目 → 値 → 判定、閉じる目安、視点ごとの前後、限界）と run.json（コマンド・道具・入出力の SHA-256）を書く。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py
読むもの（どれも既にある出力。新しい計算はしない）：
    修正01 の後：Unity/Build/Polish/30/fix01/{checks_final,checks_r7}/（pl30_checks.json・pl30_fix01_checks.json）、checks_before/pl30_checks.json、
    fix01/measure_r10/pl30_measure.json、fix01/r10・before の pl30_render_report.json、fix01/r10/pl28u_regress.json・eval23（f1_off_*）、
    作る部の採用 after_r7 の pl28u_regress.json・eval23（r7_off_*）と checks_final/pl30_checks.json（作る部の検査）、Polish/29/fix01/p29g の同じもの（前の群）、
    sea/pl30_generate_log.json、sea/boat_support.json、設計30 の boat_support.json、release/unity/pl30_build.json、release/runs/fix01_main/report.json、fix01/setup/pl30_setup.json、
    Docs/Evidence/Polish/30/gpu_sea_fix01_runs.json・pl30_fix01_trough_share.json
修正02（自己評審の修正の回 2）：「後」を修正02 の採用（fix02/r_final・sea）に替え、修正01 の値は fix01 の欄に残す。
    読むもの：fix02/checks_final/（pl30_checks.json・pl30_fix01_checks.json・pl30_fix02_checks.json）、fix02/checks_f1/pl30_fix02_checks.json、fix02/measure_final、
    fix02/r_final の pl30_render_report.json・pl28u_regress.json・eval23（f2_off_*）、release/runs/fix02_main、fix02/setup、
    Docs/Evidence/Polish/30/pl30_fix02_fuji.json・pl30_fix02_trough_share.json・gpu_sea_fix02_runs.json
"""
import datetime
import hashlib
import json
import os

import numpy as np

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
B = os.path.join(REPO, "Unity", "Build", "Polish", "30")
E = os.path.join(REPO, "Docs", "Evidence", "Polish", "30")


def J(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def keel_accel(p):
    r = J(p)
    F = r["frames"]
    t = np.array([f["t"] for f in F])
    kw = np.array([[np.nan if v is None else v for v in f["keel_water_m"]] for f in F])
    acc = np.abs(kw[2:] - 2 * kw[1:-1] + kw[:-2]) * 900.0
    tt = t[1:-1]
    d = np.array([f["delta_m"] for f in F])
    return dict(keel_water_accel_max_m_s2=float(np.nanmax(acc)), at_t=float(tt[np.nanargmax(np.nanmax(acc, 1))]), p99=float(np.nanpercentile(acc, 99)),
                heave_accel_max_m_s2=float(np.abs(np.diff(d, 2)).max() * 900.0), heave_range_m=[float(d.min()), float(d.max())])


def gates(regress):
    out = {}
    for st in ("t28_white", "t28_claws"):
        s = regress["sets"][st]
        sil = s["strict"]["silhouettes_definition_reading"]
        lf = s["large_form"]["s12"]
        out[st] = {"78": sil["78"]["max_px"], "130": sil["130"]["max_px"], "131": sil["131"]["max_px"], "132_s12_max": lf["132_max_px"], "72_s12_p95": lf["72_p95_px"],
                   "colour_items_max_px": {k: v["max_now_px"] for k, v in s["strict"]["colour_items"].items()}, "colour_265_267": s["strict"]["colour_265_267"]}
    return out


def eval23(d, prefix):
    out = {}
    for c in ("line", "line_noclaws", "noline", "noline_noclaws"):
        m = J(os.path.join(d, "eval23", "%s_off_%s" % (prefix, c), "metrics.json"))["items"]
        cnt = {}
        for v in m.values():
            cnt[v.get("verdict")] = cnt.get(v.get("verdict"), 0) + 1
        out[c] = dict(counts=cnt, items={k: [(x.get("target"), x.get("value_max_px"), x.get("p95_px"), x.get("verdict"), x.get("value")) for x in v.get("measures", [])] for k, v in m.items()})
    return out


def main():
    ck_a = J(os.path.join(B, "fix02", "checks_final", "pl30_checks.json"))
    ck_f1 = J(os.path.join(B, "fix01", "checks_final", "pl30_checks.json"))
    fx2_a = J(os.path.join(B, "fix02", "checks_final", "pl30_fix02_checks.json"))
    fx2_f1 = J(os.path.join(B, "fix02", "checks_f1", "pl30_fix02_checks.json"))
    fx_f1 = J(os.path.join(B, "fix01", "checks_final", "pl30_fix01_checks.json"))
    rr_f1 = J(os.path.join(B, "fix01", "r10", "pl30_render_report.json"))
    rg_f1 = J(os.path.join(B, "fix01", "r10", "pl28u_regress.json"))
    ms_f1 = J(os.path.join(B, "fix01", "measure_r10", "pl30_measure.json"))
    ck_r7 = J(os.path.join(B, "checks_final", "pl30_checks.json"))
    ck_b = J(os.path.join(B, "checks_before", "pl30_checks.json"))
    fx_a = J(os.path.join(B, "fix02", "checks_final", "pl30_fix01_checks.json"))
    fx_r7 = J(os.path.join(B, "fix01", "checks_r7", "pl30_fix01_checks.json"))
    ms = J(os.path.join(B, "fix02", "measure_final", "pl30_measure.json"))
    rr_a = J(os.path.join(B, "fix02", "r_final", "pl30_render_report.json"))
    rr_b = J(os.path.join(B, "before", "pl30_render_report.json"))
    rg_a = J(os.path.join(B, "fix02", "r_final", "pl28u_regress.json"))
    rg_r7 = J(os.path.join(B, "after_r7", "pl28u_regress.json"))
    rg_p = J(os.path.join(REPO, "Unity", "Build", "Polish", "29", "fix01", "p29g", "pl28u_regress.json"))
    gen = J(os.path.join(B, "sea", "pl30_generate_log.json"))
    rb = J(os.path.join(B, "release", "unity", "pl30_build.json"))
    rrun = J(os.path.join(B, "release", "runs", "fix02_main", "report.json"))
    setup = J(os.path.join(B, "fix02", "setup", "pl30_setup.json"))
    fuji_a = ms["fuji"]["after"]; fuji_b = ms["fuji"]["before"]
    t510 = lambda L: [x for x in L if 5.0 <= x["t"] <= 10.0]  # noqa: E731
    snow_tstar = [x for x in fuji_b if x["t"] == 12.0][0]["snow"]
    M = dict(
        schema="GreatWave.Polish30.metrics/1", number="仕上げ30（設計30 周りの海）",
        backlog_items="88、93、153〜156、158、160、167〜171、182〜190、202、228、231、233、235、236、239、242、245、248、251〜255、257〜260、264（計画 §5.2・§5.3。項目の文言はリポジトリの外の xlsx にあり、"
                      "この群では計画 §5.3 の各行を項目の代わりに数える（前の群と同じ））",
        made_local=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        evidence_kind_ja="Unity 6000.4.3f1 の batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）、Editor の Play モード 2 つ、Release のプレイヤーを PC で 1 回動かした結果、"
                         "numpy の生成器と検査（継ぎ目・T 字・船の支え・帯の折れ・富士の見え・船の上下）、原画視点の評価器（pl28u_regress と評価器 23）。HMD 実機の結果ではない。",
        adopted=dict(
            sea_package=dict(dir="Unity/Build/Polish/30/sea", near_pos_sha256=gen["near"]["pos_sha256"], far_pos_sha256=gen["far"]["pos_sha256"],
                             near_rows=gen["near_rows"], near_cols=gen["near_cols"], far_rows=gen["far_rows"], far_cols=gen["far_cols"], params_sha256=gen.get("params_sha256")),
            sea_material="Assets/GreatWave/Polish30/Materials/PL30_Ukiyoe_Sea.mat（GreatWave/Polish30/PL30 Ukiyoe Sea Keypose）",
            sea_attr_sha256=rr_a.get("seaAttrSha256"), left_swell=rr_a.get("mound"), boat_support=dict(path="Unity/Build/Polish/30/sea/boat_support.json", sha256=sha(os.path.join(B, "sea", "boat_support.json"))),
            hero="仕上げ29 のまま（K*′ P28R2rec・G_p28rec・PL29 Ukiyoe Keypose・PL29 Claw Shade）",
            gpu_bytes=dict(hero=rr_a["heroGpuBytes"], near=rr_a["nearGpuBytes"], far=rr_a["farGpuBytes"], total_mib=(rr_a["heroGpuBytes"] + rr_a["nearGpuBytes"] + rr_a["farGpuBytes"]) / 2 ** 20,
                           before_near=rr_b["nearGpuBytes"], before_far=rr_b["farGpuBytes"], budget_mib=512)),
        seam=dict(before=ck_b.get("seam"), after=ck_a.get("seam"), note_ja="前は設計30 の海（F_final の 242 節点）と G_p28rec の主役波：τ で読んだ境の輪の隔たり（仕上げ28 の 4.134 m と同じ種類の読み。ここでは 121 点で 3.03 m）。"),
        boat_patch=dict(after=ck_a.get("boat_patch"), before_design30_ja="設計30 §5 の 1：前の継ぎ目の稜 0.80 m・その外の溝 −1.0 m、法線の内積 0.32〜0.59（F_final の主役波。読み方は設計30 の独立の検査）"),
        band_kink=dict(before=ck_b.get("kink"), after=ck_a.get("kink")),
        fuji=dict(before=fuji_b, after=fuji_a, snow_px_tstar=snow_tstar,
                  min_snow_t5_10=dict(before=min(x["snow"] for x in t510(fuji_b)), after=min(x["snow"] for x in t510(fuji_a))),
                  numpy_estimate=dict(before=ck_b.get("fuji", {}).get("min_visible_frac_t5_10"), after=ck_a.get("fuji", {}).get("min_visible_frac_t5_10"))),
        s5_1_pop=dict(frames_180_190=ms.get("pop"), video_jumps=ms.get("video_jumps")),
        f7_2_lines_seat_270_300=ms.get("lines"), s5_3_stair_seat_f280=ms.get("stair"), sea_id_fractions=ms.get("seaid"),
        heave=dict(before_design30=keel_accel(os.path.join(REPO, "Unity", "Build", "Design", "30", "sea", "boat_support.json")),
                   after=keel_accel(os.path.join(B, "sea", "boat_support.json")), after_summary=J(os.path.join(B, "sea", "boat_support.json"))["summary"]),
        painting_view_gates=dict(after=gates(rg_a), fix01_r10=gates(rg_f1), build_round_after_r7=gates(rg_r7), previous_group_polish29_p29g=gates(rg_p),
                                 cp1={"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558}, r26_fix01={"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723},
                                 note_ja="CP1・26修正01 の値は仕上げ29 の記録の表の値（同じ定義の読み）。"),
        evaluator23=dict(after=eval23(os.path.join(B, "fix02", "r_final"), "f2"), fix01_r10=eval23(os.path.join(B, "fix01", "r10"), "f1"), build_round_after_r7=eval23(os.path.join(B, "after_r7"), "r7"),
                         previous_group=eval23(os.path.join(REPO, "Unity", "Build", "Polish", "29", "fix01", "p29g"), "p29g")),
        fix01=dict(note_ja="修正の回 1（自己評審の must-fix 12 件）。build_round は作る部の採用（after_r7・sea_r7）、after は修正01 の採用（fix01/r10・sea_f1。修正02 で sea → sea_f1 に名前を替えた）。",
                   checks_build_round=dict(pl30_checks=dict((k, ck_r7.get(k)) for k in ("seam", "boat_patch", "kink", "fuji")), fix01_checks=fx_r7),
                   checks_after=dict(fix01_checks=fx_f1, pl30_checks=dict((k, ck_f1.get(k)) for k in ("seam", "boat_patch", "kink", "fuji"))),
                   measure=dict((k, ms_f1.get(k)) for k in ("pop", "video_jumps", "lines", "stair", "seaid")),
                   gpu_bytes=dict(near=rr_f1["nearGpuBytes"], far=rr_f1["farGpuBytes"]),
                   trough_share=J(os.path.join(E, "pl30_fix01_trough_share.json")), gpu_runs=J(os.path.join(E, "gpu_sea_fix01_runs.json"))),
        fix02=dict(note_ja="修正の回 2（自己評審の must-fix 7 件）。前＝修正01 の採用（fix01/r10・sea_f1）、後＝修正02 の採用（fix02/r_final・sea）。",
                   fix02_checks=dict(after=fx2_a, fix01=fx2_f1), fuji_all_frames=J(os.path.join(E, "pl30_fix02_fuji.json")),
                   trough_share=J(os.path.join(E, "pl30_fix02_trough_share.json")), gpu_runs=J(os.path.join(E, "gpu_sea_fix02_runs.json")),
                   generate=dict(growth_shoulder_knots=gen.get("growth_shoulder_knots"), shoulder_raise_on=gen.get("shoulder_raise_on"))),
        release=dict(build=dict((k, rb.get(k)) for k in ("buildResult", "buildErrorCount", "dataFiles", "dataBytes", "mustHavePresent", "bakeFilesAbsent", "absolutePaths", "exeSha256", "scene", "sceneSha256")),
                     run_fix02_main=dict((k, rrun.get(k)) for k in list(rrun.keys())[:24])),
        scenes=setup,
    )
    with open(os.path.join(E, "metrics_measured.json"), "w", encoding="utf-8") as f:
        json.dump(M, f, ensure_ascii=False, indent=1)
    # run.json：コマンドと SHA-256
    files_in = ["Tools/GWWaveGen/pl30/" + f for f in sorted(os.listdir(os.path.join(REPO, "Tools", "GWWaveGen", "pl30"))) if f.endswith((".py", ".json", ".txt", ".ps1"))]
    unity = []
    for root, _, fs in os.walk(os.path.join(REPO, "Unity", "Assets", "GreatWave", "Polish30")):
        for f in fs:
            unity.append(rel(os.path.join(root, f)))
    data = [os.path.join(B, "sea", "near", "ds27_keypose.json"), os.path.join(B, "sea", "far", "ds27_keypose.json"), os.path.join(B, "sea", "near", "pl30_sea_attr_f32.bin"),
            os.path.join(B, "sea", "far", "pl30_sea_attr_f32.bin"), os.path.join(B, "sea", "boat_support.json"), os.path.join(B, "sea", "sea_function.json"),
            os.path.join(B, "sea", "near", "pl30_rows.json"), os.path.join(B, "left_swell", "pl30_left_swell.json"),
            os.path.join(B, "release", "player", "GreatWave50.exe")]
    ev = sorted(f for f in os.listdir(E))
    R = dict(
        schema="GreatWave.Polish30.run/1", number="仕上げ30", made_local=M["made_local"],
        tools=dict(python="py -3.10（numpy 2.2.6・scipy 1.15.3・Pillow・OpenCV 4.12）", unity="6000.4.3f1（E:/6000.4.3f1/Editor/Unity.exe、batchmode、unity.lock を run_pl30_unity.ps1 が取る）",
                   ffmpeg="G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe", gpu="RTX 3080（Direct3D11）"),
        commands=[
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_generate.py --out Unity/Build/Polish/30/sea_r2  （後で sea_r2 を Unity/Build/Polish/30/sea へ写した。同じ SHA-256）",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_attr.py --sea Unity/Build/Polish/30/sea_r2",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea_r2 --out Unity/Build/Polish/30/checks_r2   （座席の船の上下 boat_support.json を書く）",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/checks_final --skip boatheave",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Design/30/sea --out Unity/Build/Polish/30/checks_before --skip boat,boatheave",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_left_swell.py",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Dump.Run -Log dump2 -Extra \"-pl30Out <B>/dump/pl30_scene_dump.json\"",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.EnsureMaterial -Log ensure_mat6 -Extra \"-pl30SeaParamFile Tools/GWWaveGen/pl30/pl30_sea_params.txt\"",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log before -Extra \"-pl29Out <B>/before -pl30Old 1 <主役波の引数> -pl29Only views,tt,fuji,s5,video\"（と before_fuji・before_ids）",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log after_r7 -Extra \"-pl29Out <B>/after_r7 -pl30Sea <B>/sea_r2 -pl30SeaParamFile <params> -pl30LeftSwell <B>/left_swell/pl30_left_swell.json <主役波の引数> -pl29Only views,ids,tt,t28,full,fuji,s5,video -pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top,seat_low\"",
            "主役波の引数 = -pl29Attr Build/Polish/29/fix01/attr/pl29_hero_attr_f32.bin -pl29ClawShade 1 -pl29ParamFile Tools/GWWaveGen/pl29/pl29_material_params.txt -pl29ClawParamFile Tools/GWWaveGen/pl29/pl29_claw_params.txt（仕上げ29 の p29g と同じ）",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/30/after_r7 --kstar rec",
            "py -3.10 Tools/PaintingTruth/evaluate.py --render <after_r7>/full/painting_t120_off.png --ids <after_r7>/full/ids_<組>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir <after_r7>/eval23/r7_off_<組> --name r7_off_<組>（組 4 つ）",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_measure.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/after_r7 --out Unity/Build/Polish/30/measure_r7",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_sheets.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/after_r7 --measure Unity/Build/Polish/30/measure_r7/pl30_measure.json --out Docs/Evidence/Polish/30",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.BuildScenes -Log build_scenes -Extra \"-pl30Sea Build/Polish/30/sea -pl30SeaParamFile <params>\"",
            "run_pl30_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log playmode_single|release -Extra \"-pl29Scene Assets/GreatWave/Polish30/Scenes/PL30_<SinglePlayback|Release>.unity -pl29Out <B>/playmode_<single|release> -pl29Limit 120|400\"",
            "run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30ReleaseBuild.BuildAll -Log release_build",
            "powershell -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag main2（main1 は材質の最後の書き直しの前の exe）",
            "py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py",
            '── 修正の回 1（2026-10-01、自己評審の must-fix 12 件）──',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_generate.py --out Unity/Build/Polish/30/sea_f1  （後で sea → sea_r7、sea_f1 → sea に名前を替えた）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_attr.py --sea Unity/Build/Polish/30/sea_f1',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea_f1 --out Unity/Build/Polish/30/fix01/checks_pl30_f1  （boat_support.json を書く）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_left_swell.py  （面の座標を 20 個の並びに）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix01/checks_final --skip boatheave',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix01/checks_final（と --sea Unity/Build/Polish/30/sea_r7 --out Unity/Build/Polish/30/fix01/checks_r7）',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.EnsureMaterial -Log f1_ensure10 -Extra "-pl30SeaParamFile <params>"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f1_r10 -Extra "-pl29Out <B>/fix01/r10 -pl30Sea <B>/sea -pl30SeaParamFile <params> -pl30LeftSwell <B>/left_swell/pl30_left_swell.json <主役波の引数> -pl29Only views,ids,tt,t28,full,fuji,s5,video -pl29VideoViews painting,seat,seat_toward_wave,side_left -pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top,seat_low"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f1_r10d -Extra "-pl29Out <B>/fix01/r10_diag7 （同じ引数） -pl29Only views -pl29Debug 7"  （谷の縁の段の印）',
            'py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/30/fix01/r10 --kstar rec',
            'py -3.10 Tools/PaintingTruth/evaluate.py --render <r10>/full/painting_t120_off.png --ids <r10>/full/ids_<組>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir <r10>/eval23/f1_off_<組> --name f1_off_<組>（組 4 つ）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_measure.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/fix01/r10 --out Unity/Build/Polish/30/fix01/measure_r10',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sheets.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/fix01/r10 --measure Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json --out Docs/Evidence/Polish/30',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_sheets.py --r7 Unity/Build/Polish/30/after_r7 --f1 Unity/Build/Polish/30/fix01/r10 --mask Unity/Build/Polish/30/fix01/r10_diag7 --measure Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json --out Docs/Evidence/Polish/30',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f1_gpu_after<k>|f1_gpu_before<k> -Extra "... -pl29Only gpu -pl29Gpu 1 -pl30GpuTarget sea"（後は -pl30Sea <B>/sea、前は -pl30Old 1。k = 1〜3 を交互）',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.BuildScenes -Log f1_build_scenes -Extra "-pl30Sea Build/Polish/30/sea -pl30SeaParamFile <params> -pl30Out <B>/fix01/setup"',
            'run_pl30_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log f1_playmode_single|f1_playmode_release -Extra "-pl29Scene Assets/GreatWave/Polish30/Scenes/PL30_<SinglePlayback|Release>.unity -pl29Out <B>/fix01/playmode_<single|release> -pl29Limit 120|400"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30ReleaseBuild.BuildAll -Log f1_release_build',
            'powershell -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag fix01_main',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_metrics.py',
            '── 修正の回 2（2026-10-01、自己評審の must-fix 7 件）──',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_checks.py --sea Unity/Build/Polish/30/sea_f1 --out Unity/Build/Polish/30/fix02/checks_f1  （修正01 の海の全 251 節点の継ぎ目の法線・偽の白の数え。sea → sea_f1 に名前を替えた後）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_generate.py --out Unity/Build/Polish/30/fix02/try5/sea_a --params Unity/Build/Polish/30/fix02/try5/pl30_params_try5a.json （上り口を高くする案の試し。採った後に同じ値を pl30_params.json へ）',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f2_try5a_fuji -Extra "-pl29Out <B>/fix02/try5/r_a -pl30Sea <B>/fix02/try5/sea_a ... -pl29Only fuji -pl30FujiT1 12 -pl30FujiDt 0.0333333333333 -pl29Times 12"',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_generate.py --out Unity/Build/Polish/30/sea ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_sea_attr.py --sea Unity/Build/Polish/30/sea',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_growth_table.py --sea Unity/Build/Polish/30/sea  （材質の育ちの表 _GrowR・_GrowS を pl30_sea_params.txt へ）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix02/checks_final --fuji-t1 12 --fuji-dt 0.125  （boat_support.json を書く）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix02/checks_final ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix02/checks_final',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.EnsureMaterial -Log f2_ensure -Extra "-pl30SeaParamFile <params>"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f2_final -Extra "-pl29Out <B>/fix02/r_final -pl30Sea <B>/sea -pl30SeaParamFile <params> -pl30LeftSwell <B>/left_swell/pl30_left_swell.json <主役波の引数> -pl29Only views,ids,tt,t28,full,fuji,s5,video -pl29VideoViews painting,seat,seat_toward_wave,side_left -pl29Views painting,seat,seat_toward_wave,side_left,side_right,back65,top,seat_low"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f2_fuji_final（と f2_fuji_f1） -Extra "-pl29Out <B>/fix02/fuji_final（fuji_f1） -pl30Sea <B>/sea（sea_f1） ... -pl29Only fuji -pl30FujiT1 12 -pl30FujiDt 0.0333333333333 -pl29Times 12"  （t 5〜12 s の全部のコマ）',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f2_final_d7 -Extra "-pl29Out <B>/fix02/r_final_diag7 （同じ引数） -pl29Only views -pl29Debug 7"',
            'py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/30/fix02/r_final --kstar rec ; evaluate.py（組 4 つ、--name f2_off_<組>）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_measure.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/fix02/r_final --out Unity/Build/Polish/30/fix02/measure_final',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_sheets.py --before Unity/Build/Polish/30/before --after Unity/Build/Polish/30/fix02/r_final --measure Unity/Build/Polish/30/fix02/measure_final/pl30_measure.json --out Docs/Evidence/Polish/30',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_sheets.py --f1 Unity/Build/Polish/30/fix01/r10 --f2 Unity/Build/Polish/30/fix02/r_final --fuji Unity/Build/Polish/30/fix02/fuji_final --fuji-f1 Unity/Build/Polish/30/fix02/fuji_f1 --mask Unity/Build/Polish/30/fix02/r_final_diag7 --out Docs/Evidence/Polish/30',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Render.Render -Log f2_gpu_after<k>（と f2_gpu_before<k>） -Extra "... -pl29Only gpu -pl29Gpu 1 -pl30GpuTarget sea"（後は修正02、前は -pl30Old 1。k = 1〜3 を交互）',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30Setup.BuildScenes -Log f2_build_scenes -Extra "-pl30Sea Build/Polish/30/sea -pl30SeaParamFile <params> -pl30Out <B>/fix02/setup"',
            'run_pl30_unity.ps1 -NoQuit -Method GreatWave.Polish29.EditorTools.PL29PlayModeCheck.Run -Log f2_playmode_single（と f2_playmode_release） -Extra "-pl29Scene Assets/GreatWave/Polish30/Scenes/PL30_<SinglePlayback|Release>.unity -pl29Out <B>/fix02/playmode_<single|release> -pl29Limit 120|400"',
            'run_pl30_unity.ps1 -Method GreatWave.Polish30.EditorTools.PL30ReleaseBuild.BuildAll -Log f2_release_build ; powershell -File Tools/GWWaveGen/pl30/run_pl30_player.ps1 -Tag fix02_main',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_metrics.py',
            '── 記録の部（2026-10-01、修正02 の後。新しい描画・計算はしない）──',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix01_sheets.py --r7 Unity/Build/Polish/30/after_r7 --f1 Unity/Build/Polish/30/fix01/r10 --mask Unity/Build/Polish/30/fix01/r10_diag7 --measure Unity/Build/Polish/30/fix01/measure_r10/pl30_measure.json --out Docs/Evidence/Polish/30  （縦横の比を保つ tile_fit で作り直し）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_sheets.py --f1 Unity/Build/Polish/30/fix01/r10 --f2 Unity/Build/Polish/30/fix02/r_final --fuji Unity/Build/Polish/30/fix02/fuji_final --fuji-f1 Unity/Build/Polish/30/fix02/fuji_f1 --mask Unity/Build/Polish/30/fix02/r_final_diag7 --out Docs/Evidence/Polish/30  （同じ。数の JSON は前と同じ内容。記録の部の見直しの図 fig_pl30_record_review.png も書く）',
            'py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_metrics.py ; py -3.10 -B Tools/GWWaveGen/pl30/pl30_record.py  （metrics.json の SHA-256 を run.json へ入れるため record をもう一度）'],
        inputs=dict(hero_package_json=dict(path="Unity/Build/Polish/28/G_p28rec/art_on/ds27_keypose.json", sha256=sha(os.path.join(REPO, "Unity", "Build", "Polish", "28", "G_p28rec", "art_on", "ds27_keypose.json"))),
                    kstar_meta=dict(path="Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45_meta.json", sha256=sha(os.path.join(REPO, "Unity", "Build", "Polish", "28", "kstar_p28rec", "kstarP28R2rec_a45_meta.json"))),
                    timewarp=dict(path="Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", sha256=sha(os.path.join(REPO, "Unity", "Build", "Polish", "28", "G_p28rec", "timewarp_G_p28rec.json"))),
                    scene_dump=dict(path="Unity/Build/Polish/30/dump/pl30_scene_dump.json", sha256=sha(os.path.join(B, "dump", "pl30_scene_dump.json"))),
                    seat_v1=dict(path="Tools/GWContext/seat_v1.json", sha256=sha(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))),
                    painting_truth=dict(path="Tools/PaintingTruth/painting_truth.json", sha256=sha(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json")))),
        reference_use_ja="参照モデル（G:\\research\\model\\wave_repair_zbrush2.obj）・参照の彫刻の写真（G:\\research\\reality scan\\北斋参考）・G:\\research\\Wave Simulation は、この群のどの部でも開いていない"
                         "（右の高い波・手前の小波・谷の配置は設計30 の二次設計の数値のまま。生成器は OBJ を読まない（F13-1））。",
        code=[dict(path=p, sha256=sha(os.path.join(REPO, p))) for p in files_in + sorted(unity)],
        data=[dict(path=rel(p), sha256=sha(p), bytes=os.path.getsize(p)) for p in data if os.path.exists(p)],
        evidence=[dict(path="Docs/Evidence/Polish/30/" + f, sha256=sha(os.path.join(E, f)), bytes=os.path.getsize(os.path.join(E, f))) for f in ev if f not in ("run.json",)],
    )
    with open(os.path.join(E, "run.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=1)
    print("written", os.path.join(E, "metrics_measured.json"), os.path.join(E, "run.json"))


if __name__ == "__main__":
    main()
