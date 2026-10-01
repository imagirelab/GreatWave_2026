# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：metrics.json（項目 → 値 → 判定）と run.json（命令・道具の版・入出力の SHA-256）を書く（py -3.10）。
usage: py -3.10 faceswap_record.py <round_dir>   （round_dir = Unity/Build/Polish/28/r1_faceswap）"""
import os
import sys
import json
import glob
import platform

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC


def g(d, *ks, default=None):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return default
        d = d[k]
    return d


def rubric_value(c, fid, key_part):
    for x in g(c, "rubric", "checks", fid, default=[]) or []:
        if key_part in x["name"]:
            return x["value"], x.get("must"), x.get("pass_must")
    return None, None, None


def main():
    rd = os.path.abspath(sys.argv[1])
    ev = os.path.join(rd, "eval")
    summ = json.load(open(os.path.join(ev, "kh_eval_summary.json"), encoding="utf-8"))
    C = {c["label"]: c for c in summ["candidates"]}
    ex = json.load(open(os.path.join(ev, "faceswap_extra.json"), encoding="utf-8"))
    hv = json.load(open(os.path.join(rd, "houdini", "faceswap_hiplc_verify.json"), encoding="utf-8"))
    sg = json.load(open(os.path.join(rd, "sheets", "sheet_gates.json"), encoding="utf-8"))
    L0, L1 = "R4", "FS1"
    items = []

    def add(item_id, backlog, name_ja, crit, v0, v1, verdict, note=None):
        items.append({"id": item_id, "backlog": backlog, "item_ja": name_ja, "criterion": crit, "R4": v0, "FS1": v1, "verdict_FS1": verdict,
                      **({"note_ja": note} if note else {})})

    q0, q1 = sg["gates"][L0], sg["gates"][L1]
    for k, bl in (("78", [78]), ("130", [130]), ("131", [131])):
        add("gate_%s" % k, bl, "原画視点の輪郭 %s（定義どおりの読み：原画の線そのもの、最大）" % k, "≤ 4 px", round(q0[k]["max_px"], 3), round(q1[k]["max_px"], 3),
            "合格" if q1[k]["max_px"] <= 4 else "不合格")
    add("gate_132_lf12", [132], "132 の爪なしの大きな輪郭（σ12、最大。σ24 の緩めなし）", "≤ 4 px", round(q0["132_lf12"]["max_px"], 3), round(q1["132_lf12"]["max_px"], 3),
        "合格" if q1["132_lf12"]["max_px"] <= 4 else "不合格")
    add("gate_72_lf12", [72], "72 の爪なしの大きな輪郭（σ12、p95。σ24 の緩めなし）", "≤ 4 px", round(q0["72_lf12"]["p95_px"], 3), round(q1["72_lf12"]["p95_px"], 3),
        "合格" if q1["72_lf12"]["p95_px"] <= 4 else "不合格")
    add("gate_132_raw", [132], "132 の細部込み（原画の線そのもの、最大）", "記録（爪のこぶは仕上げ33）", round(q0["132"]["max_px"], 3), round(q1["132"]["max_px"], 3), "記録のみ")
    add("gate_72_raw", [72], "72 の細部込み（原画の線そのもの、p95）", "記録（爪のこぶは仕上げ33）", round(q0["72"]["p95_px"], 3), round(q1["72"]["p95_px"], 3), "記録のみ")
    lf4 = lambda c: g(c, "gate_lf_r4", "72", "p95_px")
    add("gate_72_lf24", [72], "72 の σ24 の読み（R4 の緩め。参考）", "記録", lf4(C[L0]), lf4(C[L1]), "記録のみ")
    for R in ("R6", "R4"):
        crit = "p99 ≤ 0.6 m" if R == "R6" else "p99 ≤ 0.31 m"
        thr = 0.6 if R == "R6" else 0.31
        v0, v1 = g(C[L0], "bulge6", R, "p99"), g(C[L1], "bulge6", R, "p99")
        add("dome_%s" % R, [68, 69], "中ほどのドーム：評審の膨らみの測り %s（局所の二次曲面の当てはめの残差）" % R, crit, v0, v1,
            "不合格" if v1 is None or v1 > thr else "合格")
        add("dome_%s_regions" % R, [68, 69], "同上の区域ごと（p99, max, >0.3 m の割合）", "記録", g(C[L0], "bulge6", R, "regions"), g(C[L1], "bulge6", R, "regions"), "記録のみ")
    s0, s1 = g(C[L0], "Q21_1", "sag_3m", "p99_m"), g(C[L1], "Q21_1", "sag_3m", "p99_m")
    add("dome_sag3m", [68, 69], "3 m の撓み p99（中のふくらみ・凹み）", "≤ 0.15 m（暫定）", s0, s1, "不合格" if s1 is None or s1 > 0.15 else "合格")
    add("dome_visual_b65", [68, 69], "後ろ 65° と回り台でドームが見えない（見た目）", "見えない",
        "見える（R4）", "見える（R4 とほぼ同じレモン形の輪郭。後ろ 65°・真後ろ・回り台のどれでも変わらない。奥の端の縦の襞もそのまま）", "不合格")
    for nm, key in (("稜（帯の上端）", "top_vs_top_smooth"), ("爪の縁（帯の下端）", "bottom_vs_bottom_smooth")):
        b0, b1 = g(C[L0], "Q21_3", key), g(C[L1], "Q21_3", key)
        pk = lambda b: None if not b else {"median_px": round(b["median_px"], 2), "p90_px": round(b["p90_px"], 2), "max_px": round(b["max_px"], 2),
                                           "covered": "%d/%d" % (b["covered_samples"], b["target_samples"])}
        ok = b1 and b1["p90_px"] <= 15 and b1["max_px"] <= 30 and b1["covered_samples"] >= b1["target_samples"]
        add("bregion_%s" % key.split("_")[0], [], "b区域の %s の像と原画の帯の差" % nm, "p90 ≤ 15、最大 ≤ 30 px、46/46（28修正01 の関門）", pk(b0), pk(b1),
            "合格" if ok else "不合格", "3 つの房に読めるかは第1回では直していない（FACE-SWAP の対象外）" if key.startswith("top") else None)
    for part, lab in (("側面の影の幅 0.5H0", "F04 横の厚み（側面の影の幅 0.5H0）"), ("正面の影の幅 0.75H0", "F04 正面の影の幅 0.75H0"), ("水面より上の体積", "F04 奥 c > 0 の水面より上の体積（m³）")):
        v0 = rubric_value(C[L0], "F04", part); v1 = rubric_value(C[L1], "F04", part)
        add("F04_%s" % part, [], lab, v1[1], v0[0], v1[0], "合格" if v1[2] else "不合格")
    n0, n1 = ex[L0]["back_notch_kh_R4_notch"]["max"], ex[L1]["back_notch_kh_R4_notch"]["max"]
    add("waist_notch", [], "背のくびれ（上から見た背の線の ±4 m の弦からの張り出しの最大、kh_R4_notch）", "≤ 1.1 m（28修正01 の F11）", n0, n1, "合格" if n1 <= 1.1 else "不合格")
    ch0, ch1 = ex[L0]["apex_chord_pm2m_deg"], ex[L1]["apex_chord_pm2m_deg"]
    add("tail_arc", [70], "手前の尾の行（c −39.8〜−26.6）の頂 ±2 m の弦の角の最小（t* の手前の尾が弧か）", "≥ 110°（R4 は 67〜105.5°）",
        ch0["near_tail_c-39.8..-26.6_min"], ch1["near_tail_c-39.8..-26.6_min"], "合格" if (ch1["near_tail_c-39.8..-26.6_min"] or 0) >= 110 else "不合格")
    add("main_arc", [70], "本体の行（c −24〜+12）の頂 ±2 m の弦の角の最小 / 125° 未満の行の数", "記録（F02 は c −5〜+3 で ≥ 125°）",
        [ch0["main_c-24..+12_min"], ch0["main_rows_below_125"]], [ch1["main_c-24..+12_min"], ch1["main_rows_below_125"]], "記録のみ")
    mf0, mf1 = g(C[L0], "rubric", "summary", "must_fail"), g(C[L1], "rubric", "summary", "must_fail")
    add("rubric_must_fail", [], "評価基準の必須の否の数（F01〜F13）", "0", "%s/%s" % (mf0, g(C[L0], "rubric", "summary", "n_checks")),
        "%s/%s" % (mf1, g(C[L1], "rubric", "summary", "n_checks")), "不合格" if mf1 else "合格")
    f0, f1 = g(C[L0], "F13_proximity", "within_0p3m"), g(C[L1], "F13_proximity", "within_0p3m")
    add("F13_distance", [], "参照モデル（他者の作品）から 0.3 m 以内の頂点の割合（写しにしない）", "≤ 0.25", f0, f1, "合格" if f1 is not None and f1 <= 0.25 else "不合格")
    for key, nm in (("local_selfx_vertices_win6", "局所の自己交差の頂点"), ("flipped_quads_gt150", "裏返りの四角形"), ("degenerate_lt_1e-6", "面積 < 1e-6 m² の三角形")):
        add("mesh_%s" % key, [], "網の衛生：%s" % nm, "0", g(C[L0], "mesh", key), g(C[L1], "mesh", key), "合格" if g(C[L1], "mesh", key) == 0 else "不合格")
    add("mesh_bvh_selfx", [], "網の衛生：三角形どうしの自己交差（Blender BVH、頂点を共有しない組）", "0",
        g(ex[L0], "selfx_bvh", "pairs_all"), g(ex[L1], "selfx_bvh", "pairs_all"), "合格" if g(ex[L1], "selfx_bvh", "pairs_all") == 0 else "不合格")
    add("wall_thickness", [], "背と管の内側の壁の厚みの最小（c の区間ごと）", "記録（管が背を突き抜けない：> 0）",
        ex[L0]["wall_thickness_back_to_tube_m"], ex[L1]["wall_thickness_back_to_tube_m"], "記録のみ")
    sh0, sh1 = ex[L0]["outline_generator_shift_vs_R4"], ex[L1]["outline_generator_shift_vs_R4"]
    add("faceswap_generators", [78, 130, 131], "FACE-SWAP の確かめ：左の外輪郭の見本（78・130・131 の 27 点）のうち、描く点が同じ行の R4 の背の頂（列 90）より 0.5 m 以上前（唇の側）の割合",
        "記録（R4 は背の頂かその後ろ）", sh0["share_forward_of_R4_crest_ge_0p5m"], sh1["share_forward_of_R4_crest_ge_0p5m"], "記録のみ")
    add("faceswap_generator_shift", [78, 130, 131], "同じ画素で、描く点が R4 からどれだけ動いたか（平均 / 最小 / 最大、m）：a（+ = 前）、c（− = 原画カメラの側）、y（高さ）",
        "記録", None, {"d_a": sh1["d_a_mean_min_max_m"], "d_c": sh1["d_c_mean_min_max_m"], "d_y": sh1["d_y_mean_min_max_m"]}, "記録のみ")
    add("fullness", [], "量感の比（断面積 / H²、参照の数値に対して、c −2〜+2）", "≥ 0.90（暫定）", g(C[L0], "Q21_2", "ratio_area_over_H2"),
        g(C[L1], "Q21_2", "ratio_area_over_H2"), "合格" if (g(C[L1], "Q21_2", "ratio_area_over_H2") or 0) >= 0.9 else "不合格")
    add("colour_134_267", [134, 267], "色区 134・267（定義どおりの読み）", "合格", "不合格（段階7確認）", "未測（焼き直しと Unity の描画が要る。第1回の範囲の外）", "未測")
    add("houdini_scene", [], "Houdini のシーン（R4 → faceswap → OUT）と候補の差", "≤ 1 mm", None, hv.get("max_diff_to_candidate_m"),
        "合格" if (hv.get("max_diff_to_candidate_m") or 1) <= 1e-3 else "不合格")
    met = {"schema": "GreatWave.Polish28.r1_faceswap.metrics/1", "round": "仕上げ28 第1回 FACE-SWAP", "candidate": "FS1 (kstarFS1_a45)",
           "baseline": "R4 (kstar_final)", "items": items}
    json.dump(met, open(os.path.join(rd, "metrics.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    # run.json
    files = {}
    for sub in ("candidate", "eval", "look", "sheets", "figs", "houdini"):
        for p in sorted(glob.glob(os.path.join(rd, sub, "**", "*"), recursive=True)):
            if os.path.isfile(p) and os.path.getsize(p) < 200_000_000 and not p.endswith(".npz_tmp"):
                if p.lower().endswith((".png", ".json", ".gwb", ".obj", ".npz", ".mp4", ".md", ".hiplc", ".log", ".txt")):
                    files[os.path.relpath(p, rd).replace("\\", "/")] = {"bytes": os.path.getsize(p), "sha256": KC.sha256(p)}
    tools = sorted(glob.glob(os.path.join(HERE, "faceswap_*.py")))
    run = {"schema": "GreatWave.Polish28.r1_faceswap.run/1",
           "commands": [
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_build.py Tools/GWWaveGen/kstar_p28/faceswap_design_r1.py %s/candidate/kstarFS1_a45" % rd.replace("\\", "/"),
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_eval.py %s/eval R4=%s FS1=%s/candidate/kstarFS1_a45_rows.npz" % (rd.replace("\\", "/"), F.R4_ROWS.replace("\\", "/"), rd.replace("\\", "/")),
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_look.py %s/look R4=... FS1=... --scale 1.0" % rd.replace("\\", "/"),
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_sheet.py %s/eval %s/look %s/sheets R4=... FS1=..." % ((rd.replace("\\", "/"),) * 3),
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_figs.py %s/figs R4=... FS1=..." % rd.replace("\\", "/"),
               "\"G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe\" Tools/GWWaveGen/kstar_p28/faceswap_houdini.py --cand <FS1 rows> --out Houdini/Polish28/faceswap.hiplc --verify %s/houdini/faceswap_hiplc_verify.json" % rd.replace("\\", "/"),
               "py -3.10 Tools/GWWaveGen/kstar_p28/faceswap_record.py %s" % rd.replace("\\", "/")],
           "tools": {"python": platform.python_version(), "numpy": np.__version__, "blender": "5.2.2 (Steam, headless)",
                     "houdini": hv.get("houdini_version"), "hython": "G:/SteamLibrary/steamapps/common/Houdini Indie/bin/hython.exe"},
           "inputs": {"R4_rows": {"path": F.R4_ROWS, "sha256": KC.sha256(F.R4_ROWS)}, "R4_gwb": {"path": F.R4_GWB, "sha256": KC.sha256(F.R4_GWB)},
                      "painting_truth_envelope": {"path": F.ENVELOPE, "sha256": KC.sha256(F.ENVELOPE)},
                      "reference_model_note_ja": "参照モデル（他者の作品）は生成器では読まない（F13-1）。kh_eval が F13 と量感の数値のためだけに、SHA-256 を照合して一時のキャッシュ（eval/_tmp）へ読み、最後に消した（消したキャッシュの SHA-256 は eval/deleted_caches_sha256.txt）。"},
           "code_sha256": {os.path.basename(p): KC.sha256(p) for p in tools + [os.path.join(F.REPO, "Houdini", "Polish28", "faceswap.hiplc")]},
           "outputs": files}
    json.dump(run, open(os.path.join(rd, "run.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    for it in items:
        print(it["id"], "|", it["R4"] if not isinstance(it["R4"], dict) else "…", "->", it["FS1"] if not isinstance(it["FS1"], dict) else "…", "|", it["verdict_FS1"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
