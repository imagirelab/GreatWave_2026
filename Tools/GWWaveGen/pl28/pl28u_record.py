# -*- coding: utf-8 -*-
"""仕上げ28（焼き直しと Unity の描画）：数値の記録（metrics_unity.json・run_unity.json）と、関門の表の図・原画視点の図を作る。

読むもの（どれも Git 対象外の Unity/Build/Polish/28/unity/ の下。作り方は run_unity.json の commands）：
  bake_kp・bake_kp_rep（焼き直しと 2 回目）、ds29_G_p28b（DS29Render の描画・GPU の照合・評価）、scene_stage9・scene_p28（PL28Render と評価）、
  eval23（評価器23 の全体の合成）、f71（F7-1 の数え）、seam_near_ring.json、catmap_stw.json、pl28u_sheets.json。
比べる値：CP1・26修正01（設計40 の ds40_acceptance の cp1_26r01_regression_stated と CP1 の記録の表）、28修正01（評価器の基準）、
  段階9（設計40・50。この道具が段階9 の状態を同じ手順で描き直して測った値で、設計40 の t* の組・評価器23 の値と画素・数値まで同じ）。
使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl28/pl28u_record.py
出力：Docs/Evidence/Polish/28/metrics_unity.json・run_unity.json・fig_pl28u_gates.png・fig_pl28u_painting_tstar.png・pl28u_painting_t120_{clawfree,asis}.png
"""
import datetime
import hashlib
import json
import os
import shutil

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
U = os.path.join(REPO, "Unity", "Build", "Polish", "28", "unity")
EV = os.path.join(REPO, "Docs", "Evidence", "Polish", "28")
FONT, FONTB = "C:/Windows/Fonts/YuGothM.ttc", "C:/Windows/Fonts/YuGothB.ttc"

# CP1・26修正01（設計40 の ds40_acceptance.json の cp1_26r01_regression_stated、CP1 の記録の表）
CP1 = {"78": 2.772, "130": 1.9675, "131": 1.8143, "132": 1.3256, "72": 1.5581}
R26 = {"78": 1.6408, "130": 1.953, "131": 1.798, "132": 1.5739, "72": 1.7233}
CP1_COLOUR = {"73": 0.68, "77": 1.21, "79": 0.35, "118": 0.68, "120": 0.29, "133": 0.39, "134": 0.68, "263": 0.40, "270": 0.56, "175": 18.38, "265": 0.55}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


def eval23(st, name):
    m = load(os.path.join(U, "eval23", "%s_%s" % (st, name), "metrics.json"))["items"]
    out = {}
    for k in ("78", "130", "131", "132", "72", "71", "76", "213", "212"):
        ms = m[k]["measures"][0]
        out[k] = {"max_px": ms.get("value_max_px", ms.get("value")), "p95_px": ms.get("p95_px"), "verdict": m[k]["verdict"]}
    return out


def crest_top_y(ids_png):
    im = np.asarray(Image.open(ids_png).convert("RGB"))
    nonsky = ~np.all(im == 255, axis=-1)
    rows = np.nonzero(nonsky.any(1))[0]
    return round(float(rows.min()) / 2.0, 2) if rows.size else None


def main():
    R = {st: load(os.path.join(U, "scene_" + st, "pl28u_regress.json")) for st in ("stage9", "p28")}
    D = load(os.path.join(U, "ds29_G_p28b", "pl28u_regress.json"))
    geo = load(os.path.join(REPO, "Unity", "Build", "Polish", "28", "r2", "metrics.json"))["values"]
    V = {}
    for st in ("stage9", "p28"):
        for s in ("t28_white", "t28_claws"):
            e = R[st]["sets"][s]
            V[(st, s)] = e
    E23 = {(st, n): eval23(st, n) for st in ("stage9", "p28") for n in ("off_noline", "off_noline_noclaws", "off_line")}

    def sil(st, s, k):
        return V[(st, s)]["strict"]["silhouettes_definition_reading"][k]

    def col(st, s, k):
        return V[(st, s)]["strict"]["colour_items"][k]

    def lf(st, s, sig, k):
        return V[(st, s)]["large_form"][sig][k]

    rows = []   # (項目, 基準, CP1, 26修正01/28修正01, 段階9 爪なし, 段階9 爪あり, 仕上げ28 爪なし, 仕上げ28 爪あり, 判定)

    def add(item, crit, cp1, r26, s9w, s9c, pw, pc, verdict, note=""):
        rows.append({"item": item, "criterion": crit, "cp1": cp1, "r26r01_or_28r01": r26, "stage9_clawfree": s9w, "stage9_claws": s9c,
                     "p28_clawfree": pw, "p28_claws": pc, "verdict": verdict, "note_ja": note})

    for k in ("78", "130", "131"):
        pw = sil("p28", "t28_white", k)["max_px"]
        add(k + " 最大（定義どおり）", "≤ 4 px", CP1[k], R26[k], sil("stage9", "t28_white", k)["max_px"], sil("stage9", "t28_claws", k)["max_px"],
            pw, sil("p28", "t28_claws", k)["max_px"], "合格" if pw <= 4.0 else "不合格")
    pw = lf("p28", "t28_white", "s12", "132_max_px")
    add("132 大きな輪郭 σ12 最大", "≤ 4 px（σ24 の緩めなし）", CP1["132"], R26["132"], lf("stage9", "t28_white", "s12", "132_max_px"),
        lf("stage9", "t28_claws", "s12", "132_max_px"), pw, lf("p28", "t28_claws", "s12", "132_max_px"), "合格" if pw <= 4 else "不合格")
    pw = lf("p28", "t28_white", "s12", "72_p95_px")
    add("72 大きな輪郭 σ12 p95", "≤ 4 px（σ24 の緩めなし）", CP1["72"], R26["72"], lf("stage9", "t28_white", "s12", "72_p95_px"),
        lf("stage9", "t28_claws", "s12", "72_p95_px"), pw, lf("p28", "t28_claws", "s12", "72_p95_px"), "合格" if pw <= 4 else "不合格")
    add("72 大きな輪郭 σ24 p95", "記録（段階5〜9 の関門の読み）", None, None, lf("stage9", "t28_white", "s24", "72_p95_px"),
        lf("stage9", "t28_claws", "s24", "72_p95_px"), lf("p28", "t28_white", "s24", "72_p95_px"), lf("p28", "t28_claws", "s24", "72_p95_px"), "記録")
    add("132 細部込み 最大", "記録（爪のこぶは仕上げ33）", None, None, sil("stage9", "t28_white", "132")["max_px"], sil("stage9", "t28_claws", "132")["max_px"],
        sil("p28", "t28_white", "132")["max_px"], sil("p28", "t28_claws", "132")["max_px"], "記録")
    add("72 細部込み p95", "記録（仕上げ33）", None, None, sil("stage9", "t28_white", "72")["p95_px"], sil("stage9", "t28_claws", "72")["p95_px"],
        sil("p28", "t28_white", "72")["p95_px"], sil("p28", "t28_claws", "72")["p95_px"], "記録")
    add("71 内側の空域 p95", "記録", None, None, E23[("stage9", "off_noline_noclaws")]["71"]["p95_px"], E23[("stage9", "off_noline")]["71"]["p95_px"],
        E23[("p28", "off_noline_noclaws")]["71"]["p95_px"], E23[("p28", "off_noline")]["71"]["p95_px"], "記録")
    base28 = {k: V[("stage9", "t28_white")]["strict"]["colour_items"][k]["r28r01_at_worst_px"] for k in V[("stage9", "t28_white")]["strict"]["colour_items"]}
    for k in ("73", "77", "79", "118", "120", "133", "134", "263", "270"):
        pw = col("p28", "t28_white", k)
        add(k + "（色区、定義のまま）", "評価器の合否・28修正01 と ±0.5 px", CP1_COLOUR.get(k), base28[k], col("stage9", "t28_white", k)["max_now_px"],
            col("stage9", "t28_claws", k)["max_now_px"], pw["max_now_px"], col("p28", "t28_claws", k)["max_now_px"],
            ("合格" if pw["verdict"] == "pass" else "不合格") + ("（±0.5 超え）" if pw["worst_abs_diff_vs_28r01_px"] > 0.5 else ""))
    rm = {}
    for st in ("stage9", "p28"):
        for s in ("t28_white", "t28_claws"):
            R0 = load(os.path.join(U, "scene_" + st, s, "ds27_tstar_remeasure.json"))
            rm[(st, s)] = {r["measure"]: r for r in R0["boundaries_vs_28r01"] if r["item"] == "175"}
    for m, lab in (("boundary_by_class/ai_mid", "175 藍中"), ("boundary_by_class/mizuiro", "175 淡い水色"), ("boundary_by_class/ai_dark", "175 藍濃")):
        add(lab + "（定義のまま）", "もともと不合格（記録）", None, rm[("stage9", "t28_white")][m]["r28r01_max_px"], rm[("stage9", "t28_white")][m]["ds27_max_px"],
            rm[("stage9", "t28_claws")][m]["ds27_max_px"], rm[("p28", "t28_white")][m]["ds27_max_px"], rm[("p28", "t28_claws")][m]["ds27_max_px"], "不合格（もともと）")
    c = {k: V[k]["strict"]["colour_265_267"] for k in V}
    add("265 内側の水色 ΔE00", "合格", CP1_COLOUR["265"], 0.545, c[("stage9", "t28_white")]["265_dE00"], c[("stage9", "t28_claws")]["265_dE00"],
        c[("p28", "t28_white")]["265_dE00"], c[("p28", "t28_claws")]["265_dE00"], "合格" if c[("p28", "t28_white")]["265"] == "pass" else "不合格")
    add("266 水色の平塗り", "合格", "合格", "合格", c[("stage9", "t28_white")]["266"], c[("stage9", "t28_claws")]["266"], c[("p28", "t28_white")]["266"],
        c[("p28", "t28_claws")]["266"], "合格" if c[("p28", "t28_white")]["266"] == "pass" else "不合格")
    add("267 白の平塗り：20 px 以上の帯", "0", 0, 0, c[("stage9", "t28_white")]["267_bands_ge_20px"]["painting_view"],
        c[("stage9", "t28_claws")]["267_bands_ge_20px"]["painting_view"], c[("p28", "t28_white")]["267_bands_ge_20px"]["painting_view"],
        c[("p28", "t28_claws")]["267_bands_ge_20px"]["painting_view"], "合格" if c[("p28", "t28_white")]["267"] == "pass" else "不合格")
    for st in ("stage9", "p28"):
        for s in ("t28_white", "t28_claws"):
            V[(st, s)]["sym_regress_worst"] = max([x["diff_px"] for x in V[(st, s)]["sym"]["rows"]] + [0.0])
    add("両側の読み：28修正01 から悪くなった向きの最大", "±0.5 px（記録。段階5〜9 が採った読み）", None, None, V[("stage9", "t28_white")]["sym_regress_worst"],
        V[("stage9", "t28_claws")]["sym_regress_worst"], V[("p28", "t28_white")]["sym_regress_worst"], V[("p28", "t28_claws")]["sym_regress_worst"],
        "記録（79・175 淡い水色が ±0.5 超え）")

    # F7-1
    f71 = {k: load(os.path.join(U, "f71", "count_G_p28b_%s.json" % k))["windows_video_frames"] for k in ("video", "pngseq", "reenc")}
    mm = load(os.path.join(EV, "metrics_motion.json"))["F7_1"]
    f71_rec = {"window_ja": "t 9〜11.5 s（動画のコマ 270〜345）、段階7確認の M1b（塗りのちらつき、20 px 以上の塊）",
               "F_final_29r01": {"video_M1b_sum_px": mm["video_ds29r01"]["windows_video_frames"]["270_345"]["M1b_sum_px"],
                                 "lossless_M1b_sum_px": mm["lossless"]["270_345"]["M1b_sum_px"], "reencoded_M1b_sum_px": mm["reencoded"]["270_345"]["M1b_sum_px"]},
               "G_p28b_rebaked": {"video_M1b_sum_px": f71["video"]["270_345"]["M1b_sum_px"], "video_M1b_max_px": f71["video"]["270_345"]["M1b_max_px"],
                                  "lossless_M1b_sum_px": f71["pngseq"]["270_345"]["M1b_sum_px"], "lossless_M1b_max_px": f71["pngseq"]["270_345"]["M1b_max_px"],
                                  "reencoded_M1b_sum_px": f71["reenc"]["270_345"]["M1b_sum_px"]}}
    g = f71_rec["G_p28b_rebaked"]
    g["encoder_share"] = round(1 - g["lossless_M1b_sum_px"] / g["reencoded_M1b_sum_px"], 4)
    fz = f71_rec["F_final_29r01"]
    fz["encoder_share"] = round(1 - fz["lossless_M1b_sum_px"] / fz["reencoded_M1b_sum_px"], 4)
    f71_rec["conclusion_ja"] = ("焼き直した描画でも、無圧縮の数は F_final の 29修正01 の描画とほぼ同じ（+2.3%）で、動画の数の約 38% が圧縮で足される。"
                                "動きの幾何は F_final と同じくなめらか（動きの部の記録：逆向き 0）。原因は描画と圧縮の側（仕上げ29・37）で、動きの修正は要らない。")

    seam = load(os.path.join(U, "seam_near_ring.json"))
    cat = load(os.path.join(U, "catmap_stw.json"))
    bake = {k: load(os.path.join(U, "bake_kp", "bake", "af28r01_bake_a45.json")).get(k) for k in ("direct", "innerDark", "uFill", "vFill", "sea", "emptyAfterFill", "notRasterised", "visible", "onScreen")}
    bake29 = {k: load(os.path.join(REPO, "Unity", "Build", "Design", "29R01", "bake_kp", "bake", "af28r01_bake_a45.json")).get(k) for k in bake}
    rep_bake = [f for f in ("af28r01_uvsdf_a45.bin", "af28r01_uvwarp_a45.json", "af28r01_uvcat_a45.bin", "af28r01_uvsdf_a45_rule28.bin")]
    det = {f: sha256(os.path.join(U, "bake_kp", "bake", f)) == sha256(os.path.join(U, "bake_kp_rep", "bake", f)) for f in rep_bake}
    rin = load(os.path.join(U, "bake_kp", "bake_input", "af28_bake_input_record.json"))
    gpu = load(os.path.join(U, "check_gpu_G_p28b.json"))
    rr = {st: load(os.path.join(U, "scene_" + st, "pl28_render_report.json")) for st in ("stage9", "p28")}
    ds29rep = load(os.path.join(U, "ds29_G_p28b", "ds29_render_report.json"))
    d40 = os.path.join(REPO, "Unity", "Build", "Design", "40", "compare", "unity")
    same40 = {}
    for s in ("t28_white", "t28_claws"):
        d = os.path.join(U, "scene_stage9", s, "t28", "render")
        same40[s] = all(sha256(os.path.join(d, fn)) == sha256(os.path.join(d40, s, "t28", "render", fn)) for fn in V[("stage9", s)]["t28_sha256"])
    e23_same40 = all(abs(E23[("stage9", "off_noline")][k]["max_px"] - load(os.path.join(EV, "..", "..", "Design", "40", "ds40_eval_off_noline_metrics.json"))["items"][k]["measures"][0]["value_max_px"]) < 1e-9
                     for k in ("78", "130", "131", "132", "72", "71"))
    rerender = {}
    for st in ("stage9", "p28"):
        p1 = os.path.join(U, "scene_%s_report_run1.json" % st)
        if os.path.exists(p1):
            a1 = {i["path"]: i["sha256"] for i in load(p1)["images"]}
            b1 = {i["path"]: i["sha256"] for i in rr[st]["images"]}
            same = [k for k in a1 if a1[k] == b1.get(k)]
            diff = [os.path.basename(k) for k in a1 if a1[k] != b1.get(k)]
            rerender[st] = {"images_same": len(same), "images_changed": diff,
                            "note_ja": "1 回目の描画（回り台は周りの海入り）と 2 回目（回り台を主役波だけにした）の比べ。変わったのは回り台の 12 枚だけ"}
    crest = {st: crest_top_y(os.path.join(U, "scene_" + st, "t28_white", "t28", "render", "af28r01_class_ids.png")) for st in ("stage9", "p28")}

    closing = [
        {"criterion_ja": "後ろ 65° と回り台でドームが見えない", "value_ja": "見える（Unity の後ろ 65°・回り台 180°〜270°）。形の部の R6 p99 0.685 m（R4 0.693 m）", "verdict": "満たさない",
         "evidence": ["fig_pl28u_ba_back65.png", "fig_pl28u_ba_turntable.png", "pl28u_ba_back65.mp4", "pl28u_ba_turntable.mp4"]},
        {"criterion_ja": "b区域が3つの房に読める", "value_ja": "Unity の原画視点では左肩の模様の区切りは変わったが、3 つの房の読みはこの部では測っていない（形の部の b_region の値を見る）", "verdict": "この部では判定しない"},
        {"criterion_ja": "F04 ≤ 18.5 m で本体が薄く見えない", "value_ja": "F04 27.64 m（形の部の r2/metrics.json、P28R2）", "verdict": "満たさない"},
        {"criterion_ja": "78・130・131 が定義どおりの読みで ≤ 4 px", "value_ja": "Unity の画像で 2.741／3.5815／3.4419 px（爪なし・爪ありとも同じ）", "verdict": "満たす"},
        {"criterion_ja": "132・72 が爪なしの大きな輪郭を σ24 の緩めなし（σ12）で ≤ 4 px", "value_ja": "132 最大 %.4f px、72 p95 %.4f px（Unity の画像、t28_white）" % (
            lf("p28", "t28_white", "s12", "132_max_px"), lf("p28", "t28_white", "s12", "72_p95_px")), "verdict": "満たす"},
        {"criterion_ja": "134・267 が合格（評価器の定義のままの読み）", "value_ja": "爪なし：134 %.3f px 不合格、267 の帯 %d 不合格。爪あり（記録）：134 %.3f px 合格、267 の帯 %d 不合格" % (
            col("p28", "t28_white", "134")["max_now_px"], c[("p28", "t28_white")]["267_bands_ge_20px"]["painting_view"], col("p28", "t28_claws", "134")["max_now_px"],
            c[("p28", "t28_claws")]["267_bands_ge_20px"]["painting_view"]), "verdict": "満たさない"},
        {"criterion_ja": "t* の頂と手前の尾が弧", "value_ja": "±2 m の弦角の最小：主 113.3°、手前の尾 123.3°、110° 未満の行 0（形の部の r2/metrics.json）", "verdict": "満たす（幾何）"},
    ]

    backlog = {
        "68": {"value": "この部では測っていない（形は K*' P28R2。唇と内壁の下端の幾何は形の部）", "verdict": "未測定"},
        "69": {"value": "主役波の頂の表示の y：段階9 %s → 仕上げ28 %s px（ID 画像）。右船は変わらない" % (crest["stage9"], crest["p28"]), "verdict": "記録（設計40 で合格）"},
        "70": {"value": "頂の y が変わらないので、波の上下と右船の長さの関係は設計40 と同じ", "verdict": "記録（設計40 で合格）"},
        "71": {"value": {"max_px": E23[("p28", "off_noline")]["71"]["max_px"], "p95_px_claws": E23[("p28", "off_noline")]["71"]["p95_px"],
                         "p95_px_clawfree": E23[("p28", "off_noline_noclaws")]["71"]["p95_px"]}, "verdict": "記録のみ"},
        "72": {"value": {"sigma12_p95_clawfree": lf("p28", "t28_white", "s12", "72_p95_px"), "sigma24_p95_clawfree": lf("p28", "t28_white", "s24", "72_p95_px"),
                         "detail_p95_clawfree": sil("p28", "t28_white", "72")["p95_px"], "detail_p95_claws": sil("p28", "t28_claws", "72")["p95_px"]},
               "verdict": "合格（閉じる目安の σ12 の読み）。細部込みは不合格・仕上げ33"},
        "73": {"value": col("p28", "t28_white", "73")["max_now_px"], "verdict": "合格（28修正01 と +1.829 px。±0.5 超え、段階9 と同じ値）"},
        "77": {"value": col("p28", "t28_white", "77")["max_now_px"], "verdict": "合格"},
        "78": {"value": sil("p28", "t28_white", "78")["max_px"], "verdict": "合格"},
        "79": {"value": col("p28", "t28_white", "79")["max_now_px"], "verdict": "合格（28修正01 と +0.764 px。±0.5 超え。段階9 は +0.672）"},
        "130": {"value": sil("p28", "t28_white", "130")["max_px"], "verdict": "合格"},
        "131": {"value": sil("p28", "t28_white", "131")["max_px"], "verdict": "合格"},
        "132": {"value": {"sigma12_max_clawfree": lf("p28", "t28_white", "s12", "132_max_px"), "detail_max_clawfree": sil("p28", "t28_white", "132")["max_px"],
                          "detail_max_claws": sil("p28", "t28_claws", "132")["max_px"]}, "verdict": "合格（σ12）。細部込みは不合格・仕上げ33"},
        "133": {"value": col("p28", "t28_white", "133")["max_now_px"], "verdict": "合格"},
        "134": {"value": {"clawfree": col("p28", "t28_white", "134")["max_now_px"], "claws": col("p28", "t28_claws", "134")["max_now_px"]},
                "verdict": "不合格（爪なし。唇先の輪郭 (1090, 427) で描画が空）。爪ありは合格（記録）"},
    }

    metrics = {
        "schema": "GreatWave.Polish28.metrics_unity/1", "number": "仕上げ28（焼き直しと Unity の描画）",
        "made_local": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "evidence_kind_ja": "Unity 6000.4.3f1 の Editor batchmode の PC オフスクリーン描画（RTX 3080、Direct3D11）と numpy の評価器。HMD 実機ではない。利用者は確かめていない。",
        "inputs": {"kstar_p28": {"path": "Unity/Build/Polish/28/kstar_p28/kstarP28R2_a45.gwb", "sha256": rin.get("kstar_source", {}).get("gwb_sha256") or
                                 "79ff9fde8ea8ebf9b04897915d19717108fe826f0626b72384e891a6d53c6992"},
                   "motion": {"package": "Unity/Build/Polish/28/G_p28b/art_on", "pos_sha256": "050c35b3566b7390e11cfde3bb5299aa2e3713175b9f5434cb52a29eb4e30a5b",
                              "pos_lo_sha256": "2e33d203d474a11250351ff637e2952462a068b8ddec2f163b13d85563b84754", "layers": 251,
                              "timewarp": "Unity/Build/Polish/28/G_p28b/timewarp_G_p28b.json", "timewarp_sha256": rr["p28"]["timewarpSha256"],
                              "tau_t_same_as_F_final": True}},
        "bake": {"method_ja": "設計29修正01 の焼き込み（ds29r01_bake_input.py → DS29R01Bake.BakeKStarPrime）を K*' P28R2 で回し直した（pl28u_bake_input.py が固定値だけを差し替える）",
                 "out_sdf_sha256": sha256(os.path.join(U, "bake_kp", "bake", "af28r01_uvsdf_a45.bin")),
                 "out_warp_sha256": sha256(os.path.join(U, "bake_kp", "bake", "af28r01_uvwarp_a45.json")),
                 "counts_p28": bake, "counts_29r01_R4": bake29, "second_bake_identical": det,
                 "paint_side_same_as_28r01": rin.get("same_as_28r01_paint_side"),
                 "uv3_px_per_texel_max_u_v": [rin["kstar"]["a45"]["uv3_warp"]["achieved_px_per_texel_u_max"], rin["kstar"]["a45"]["uv3_warp"]["achieved_px_per_texel_v_max"]]},
        "unity": {
            "ds29_render": {"out": "Unity/Build/Polish/28/unity/ds29_G_p28b", "posLo_used": ds29rep.get("posLoUsed"), "posLo_sha256": ds29rep.get("posLoSha256"),
                            "gpu_readback_vs_numpy_hermite_mm": gpu.get("worst_in_range_vs_fine_mm"), "gpu_captures": gpu.get("captures"), "gpu_check_pass": gpu.get("passed"), "tstar_vs_kstar": gpu.get("tstar_vs_kstar")},
            "scene_render": {"scene": "Assets/GreatWave/Design39/Scenes/DS39_Paper.unity（保存しない）", "stage9_t28_identical_to_design40": same40,
                             "stage9_evaluator23_identical_to_design40": e23_same40,
                             "rerender_identical_images": rerender, "protected_unchanged": {st: rr[st]["protectedUnchanged"] for st in rr},
                             "hero_gpu_bytes": {st: rr[st]["heroGpuBytes"] for st in rr}, "hero_layers": {st: rr[st]["heroLayers"] for st in rr},
                             "seconds": {st: rr[st]["secondsTotal"] for st in rr},
                             "gpu_mib_hero_near_far_p28": round(rr["p28"]["heroGpuBytes"] / 1048576 + 125.21 + 10.85, 2)}},
        "painting_gates_table": rows,
        "closing_criteria_plan_5_3": closing,
        "backlog": backlog,
        "evaluator23_full_composite": {"%s_%s" % k: v for k, v in E23.items()},
        "sym_reading": {"%s_%s" % k: {"worst_abs_diff_px": V[k]["sym"]["worst_abs_diff_px"], "regress_worst_px": V[k]["sym_regress_worst"],
                                     "rows_over_0p5": [x for x in V[k]["sym"]["rows"] if abs(x["diff_px"]) > 0.5],
                                     "267_sym_bands": V[k]["sym"]["flat_painting_view_266_267"]} for k in V},
        "kstar_geometry_px": {"P28R2": geo["P28R2"]["outline_78_130_131_max_px_definition_reading"], "R4": geo["R4"]["outline_78_130_131_max_px_definition_reading"],
                              "P28R2_sigma12_132_72": [geo["P28R2"]["large_form_sigma12_132_max_px"], geo["P28R2"]["large_form_sigma12_72_p95_px"]]},
        "worst_points_display_px": {"73_118_263": [873.7, 695.0], "79": [252.0, 470.0], "134": [1090.2, 427.0], "175_ai_mid": [378.4, 283.5],
                                    "note_ja": "73・118・263 と 134 は段階9 と同じ所（輪郭の差）。79 は左の側の白の境で、両側の読みでも +0.764 px 残る（焼き込みの境のずれ）"},
        "F7_1": f71_rec,
        "seam_near_ring": {"G_p28b_max_m": seam["heroes"]["G_p28b"]["max_m"], "G_p28b_at_tstar_m": seam["heroes"]["G_p28b"]["at_tstar_max_m"],
                           "F_final_max_m": seam["heroes"]["F_final"]["max_m"], "worst": seam["heroes"]["G_p28b"]["worst"],
                           "note_ja": "near の行 0 と主役波の本体の境の輪（列 18 の後ろ側・列 394 の前側）が、海面の高さ（y = 0）の上で進む向きに最大 4.13 m ずれる。"
                                      "6 視点の描画では穴・段は見えない（同じ高さの平らな所）。接続帯の作り直しは仕上げ30 の最初"},
        "seat_toward_wave_inner_dark_band": {k: cat.get(k) for k in ("states", "band_rowcol_box_categories")},
        "handoffs_ja": [
            "仕上げ29：表示用サーフェスの検査（ds29r01_measure の静止と厳しい読み、座席の射線）を G_p28b で回し直す。F7-1 の描画・圧縮の側",
            "仕上げ29／36／41：座席から波の方向の t* の模様のない藍濃の縦の帯（K*' P28R2 の行 137〜153・列 286〜319 が原画視点で自身に隠れ、焼き込みの規則で平らな藍濃になった）",
            "仕上げ30：near の行 0 を G_p28b の境の輪で作り直す（最大 4.13 m のずれ）",
            "仕上げ31：T_white（設計31 の ds31_twhite）を G_p28b で作り直す（この部は動きの生成器の T_white を使った）",
            "仕上げ32・33：爪の軌跡を K*' P28R2 に合わせ直す（爪ありの読みは合わせる前の値）。132・72 の細部込みの値",
            "仕上げ36・38：線の印（ds38_hero_linemask）と色の同期を K*' P28R2 で作り直す",
            "形（次の K*' の版）：ドーム、F04、134（唇先の輪郭）と 267 の帯（輪郭の差の所）"],
    }
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, "metrics_unity.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=1, default=float)
        f.write("\n")

    # ---------------- 図：関門の表
    W, H = 1920, 1080
    S = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(S)
    fb, fm, fs = ImageFont.truetype(FONTB, 24), ImageFont.truetype(FONT, 17), ImageFont.truetype(FONTB, 17)
    d.text((14, 8), "仕上げ28：原画視点 t* の関門と色区（Unity の画像。爪なし＝関門、爪あり＝そのまま記録。単位 px）", font=fb, fill=(20, 24, 32))
    d.text((14, 42), "段階9 ＝ 設計40・50 の状態をこの道具で描き直した値（設計40 の t* の組と画素まで同じ）。CP1・26修正01 は設計40 の表。色区の 26修正01 の欄は評価器の基準の 28修正01", font=fm, fill=(20, 24, 32))
    cols = [("項目", 380), ("基準", 300), ("CP1", 90), ("26修正01／28修正01", 170), ("段階9 爪なし", 140), ("段階9 爪あり", 140), ("仕上げ28 爪なし", 160), ("仕上げ28 爪あり", 160), ("判定（爪なし）", 360)]
    x = 10; y = 76
    for name, w in cols:
        d.rectangle([x, y, x + w - 2, y + 28], fill=(40, 56, 84))
        d.text((x + 6, y + 4), name, font=fs, fill=(255, 255, 255))
        x += w
    y += 30

    def fmt(v):
        if v is None:
            return "—"
        if isinstance(v, (int, float)):
            return ("%.4f" % v).rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
        return {"pass": "合格", "fail": "不合格"}.get(v, str(v))
    for i, r in enumerate(rows):
        x = 10
        bg = (244, 246, 250) if i % 2 == 0 else (255, 255, 255)
        d.rectangle([10, y, 10 + sum(w for _, w in cols), y + 28], fill=bg)
        vals = [r["item"], r["criterion"], fmt(r["cp1"]), fmt(r["r26r01_or_28r01"]), fmt(r["stage9_clawfree"]), fmt(r["stage9_claws"]), fmt(r["p28_clawfree"]),
                fmt(r["p28_claws"]), r["verdict"]]
        for j, ((name, w), v) in enumerate(zip(cols, vals)):
            colr = (20, 24, 32)
            if j == 8:
                colr = (0, 110, 40) if v.startswith("合格") else ((170, 20, 20) if v.startswith("不合格") else (60, 60, 60))
                if v.startswith("合格") and "超え" in v:
                    colr = (190, 110, 0)
            if j == 6 and isinstance(r["p28_clawfree"], (int, float)) and isinstance(r["stage9_clawfree"], (int, float)) and "267" not in r["item"] and "265" not in r["item"]:
                dv = r["p28_clawfree"] - r["stage9_clawfree"]
                if abs(dv) >= 0.05:
                    colr = (0, 110, 40) if dv < 0 else (170, 20, 20)
            t = str(v)
            fnt = fm
            while d.textlength(t, font=fnt) > w - 10 and len(t) > 4:
                t = t[:-2]
            d.text((x + 6, y + 5), t, font=fnt, fill=colr)
            x += w
        y += 29
    y += 6
    txt = ("仕上げ28 爪なしの欄の色：段階9 より 0.05 px 以上良い＝緑、悪い＝赤。判定の橙＝評価器では合格だが 28修正01 との差が ±0.5 px を超える（計画 §2.0 の回帰の読み）。F7-1（t 9〜11.5 s の M1b）：無圧縮 %d px（F_final %d）、動画 %d px（F_final %d）、圧縮の分 %.0f%%。"
           "near の行 0 と主役波の境のずれ 最大 %.2f m（仕上げ30）。GPU：主役波 %.1f MiB（精度の層つき、near・far と合わせて %.1f MiB ≤ 512）。GPU の読み戻しと numpy の差 %.4f mm" % (
               g["lossless_M1b_sum_px"], fz["lossless_M1b_sum_px"], g["video_M1b_sum_px"], fz["video_M1b_sum_px"], 100 * g["encoder_share"],
               seam["heroes"]["G_p28b"]["max_m"], rr["p28"]["heroGpuBytes"] / 1048576, rr["p28"]["heroGpuBytes"] / 1048576 + 125.21 + 10.85,
               metrics["unity"]["ds29_render"]["gpu_readback_vs_numpy_hermite_mm"] or 0.0))
    # 折り返し
    line = ""
    for ch in txt:
        if d.textlength(line + ch, font=fm) > W - 30:
            d.text((14, y), line, font=fm, fill=(20, 24, 32)); y += 24; line = ""
        line += ch
    d.text((14, y), line, font=fm, fill=(20, 24, 32))
    S.save(os.path.join(EV, "fig_pl28u_gates.png"))

    # ---------------- 図：原画視点 t*（仕上げ28 の爪なし・爪あり、評価器の境界の図の拡大 段階9／仕上げ28）
    S = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(S)
    d.text((14, 8), "仕上げ28：原画視点 t*　上：仕上げ28 の爪なし（関門の読み）｜爪・飛沫をそのまま（爪は K*' R4 に合わせたまま）", font=fb, fill=(20, 24, 32))
    a1 = Image.open(os.path.join(U, "scene_p28", "views", "painting_t120_clawfree.png")).convert("RGB").resize((952, 536), Image.LANCZOS)
    a2 = Image.open(os.path.join(U, "scene_p28", "views", "painting_t120_asis.png")).convert("RGB").resize((952, 536), Image.LANCZOS)
    S.paste(a1, (4, 44)); S.paste(a2, (964, 44))
    d.text((14, 590), "下：評価器（美術優先28修正01）の境界の図の拡大（爪なし）。シアン＝原画の色区の境界、緑・黄・赤＝描画の境界の点の差 ≤2・≤4・>4 px、赤丸＝4 px を超えた所。"
           "左：段階9　右：仕上げ28", font=fm, fill=(20, 24, 32))
    for i, st in enumerate(("stage9", "p28")):
        b = Image.open(os.path.join(U, "scene_" + st, "t28_white", "t28", "evidence", "28R01_boundaries.png")).convert("RGB").crop((140, 60, 1240, 600))
        b = b.resize((952, int(952 * b.height / b.width)), Image.LANCZOS)
        S.paste(b, (4 + i * 960, 620))
    S.save(os.path.join(EV, "fig_pl28u_painting_tstar.png"))
    for cnd in ("clawfree", "asis"):
        shutil.copyfile(os.path.join(U, "scene_p28", "views", "painting_t120_%s.png" % cnd), os.path.join(EV, "pl28u_painting_t120_%s.png" % cnd))

    # ---------------- run_unity.json
    sc = "Tools/GWWaveGen/pl28/"
    code = [sc + f for f in ("pl28u_bake_input.py", "pl28u_tstar_eval.py", "pl28u_regress.py", "pl28u_sheets.py", "pl28u_seam.py", "pl28u_catmap.py", "pl28u_record.py")] + \
        ["Unity/Assets/GreatWave/Polish28/Editor/PL28Render.cs", sc + "run_pl28_unity.ps1", sc + "pl28_f71_count.py", "Tools/GWWaveGen/ds29r01/ds29r01_bake_input.py",
         "Tools/GWWaveGen/ds29r01/ds29r01_tstar_eval.py", "Tools/GWWaveGen/ds29r01/ds29r01_tstar_sym.py", "Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py",
         "Tools/GWWaveGen/kstar_h/kh_gate_lf.py", "Tools/GWWaveGen/kstar_h/kh_gate_lfR4.py", "Tools/PaintingTruth/evaluate.py",
         "Unity/Assets/GreatWave/Design29/Editor/DS29Render.cs", "Unity/Assets/GreatWave/Design29/Editor/DS29R01Bake.cs"]
    outs = []
    for root in (os.path.join(U, "bake_kp", "bake"), os.path.join(U, "ds29_G_p28b", "video"), os.path.join(U, "scene_p28", "video"), os.path.join(U, "scene_stage9", "video")):
        for fn in sorted(os.listdir(root)):
            outs.append(rel(os.path.join(root, fn)))
    outs += [rel(os.path.join(U, x)) for x in ("scene_p28/pl28u_regress.json", "scene_stage9/pl28u_regress.json", "ds29_G_p28b/pl28u_regress.json",
                                                  "scene_p28/pl28_render_report.json", "scene_stage9/pl28_render_report.json", "ds29_G_p28b/ds29_render_report.json",
                                                  "check_gpu_G_p28b.json", "seam_near_ring.json", "catmap_stw.json", "f71/count_G_p28b_video.json",
                                                  "f71/count_G_p28b_pngseq.json", "f71/count_G_p28b_reenc.json", "pl28u_sheets.json")]
    ev = sorted(fn for fn in os.listdir(EV) if fn.startswith(("fig_pl28u", "pl28u_")) or fn == "metrics_unity.json")
    run = {
        "schema": "GreatWave.Polish28.run_unity/1", "made_local": metrics["made_local"],
        "tools": {"python": "3.10（numpy 2.2.6、Pillow 12.0.0、OpenCV 4.12.0）", "unity": "6000.4.3f1 Editor batchmode（PC オフスクリーン、RTX 3080、Direct3D11）",
                  "ffmpeg": "2024-12-19 full_build"},
        "commands": [
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_bake_input.py（--build Unity/Build/Polish/28/unity/bake_kp。決定性の確かめは --build …/bake_kp_rep）",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/pl28/run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29R01Bake.BakeKStarPrime -Log u_bake_kp -Extra \"-ds29r01BakeRoot Build/Polish/28/unity/bake_kp\"（2 回目は -Log u_bake_kp_rep と bake_kp_rep）",
            "powershell … run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log u_ds29_G_p28b -Package Build/Polish/28/G_p28b/art_on -WarpFile Build/Polish/28/G_p28b/timewarp_G_p28b.json -OutDir Build/Polish/28/unity/ds29_G_p28b -Stills \"m6=-6,m3=-3,m2=-2,m1=-1,m05=-0.5,tstar=0\" -Views \"painting,seat,seat_toward_wave,side_left\" -Skip timing -Extra \"-ds29Name G_p28b -ds29MeshFromPackage 0 -ds29KStarGwb Build/Polish/28/unity/bake_kp/kstar/kstar_a45.gwb -ds29Sdf Build/Polish/28/unity/bake_kp/bake/af28r01_uvsdf_a45.bin -ds29Warp Build/Polish/28/unity/bake_kp/bake/af28r01_uvwarp_a45.json\"",
            "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_unity_check.py gpu --run Unity/Build/Polish/28/unity/ds29_G_p28b --package Unity/Build/Polish/28/G_p28b/art_on --range=-12,0 --out Unity/Build/Polish/28/unity/check_gpu_G_p28b.json",
            "powershell … run_pl28_unity.ps1 -Method GreatWave.Polish28.EditorTools.PL28Render.Render -Log u_scene_p28_r2 -Extra \"-pl28State p28 -pl28Out G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/28/unity/scene_p28\"（段階9 は -pl28State stage9 と scene_stage9）",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_regress.py --scene Unity/Build/Polish/28/unity/scene_p28 --kstar p28（段階9 は --scene …/scene_stage9 --kstar r4、DS29Render の組は --scene …/ds29_G_p28b --kstar p28 --sets .）",
            "py -3.10 Tools/PaintingTruth/evaluate.py --render Unity/Build/Polish/28/unity/scene_<st>/full/painting_t120_off.png --ids Unity/Build/Polish/28/unity/scene_<st>/full/<ids>.png --idmap Unity/Build/Design/40/compare/eval/idmap.json --out-dir Unity/Build/Polish/28/unity/eval23/<st>_<name> --name <st>_<name>（<st> = stage9・p28、<name>:<ids> = off_noline:ids_noline・off_noline_noclaws:ids_noline_noclaws・off_line:ids_line・off_line_noclaws:ids_line_noclaws）",
            "powershell … run_pl28_unity.ps1 -Method GreatWave.Design29.EditorTools.DS29Render.Render -Log u_f71_G_p28b -Package Build/Polish/28/G_p28b/art_on -WarpFile Build/Polish/28/G_p28b/timewarp_G_p28b.json -OutDir Build/Polish/28/unity/f71/unity_G_p28b -Stills <コマ 264〜351 の τ（timewarp_G_p28b.json の線形補間。F_final と同じ）> -Skip \"t28,capture,video,timing\" -Extra \"-ds29Name f71_G_p28b -ds29MeshFromPackage 0 -ds29StillViews painting -ds29KStarGwb … -ds29Sdf … -ds29Warp …\"",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_count.py --kind video|pngseq|reenc …（--win 60,269 --win 270,345 --win 346,360、PNG は --first 264 --win 270,345 --win 265,269 --win 346,350）",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_seam.py", "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_catmap.py",
            "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_sheets.py", "py -3.10 -B Tools/GWWaveGen/pl28/pl28u_record.py"],
        "code_sha256": {p: sha256(os.path.join(REPO, p)) for p in code},
        "inputs_sha256": {p: sha256(os.path.join(REPO, p)) for p in (
            "Unity/Build/Polish/28/kstar_p28/kstarP28R2_a45.gwb", "Unity/Build/Polish/28/G_p28b/art_on/ds27_keypose.json",
            "Unity/Build/Polish/28/G_p28b/art_on/ds27_pos_rgba16.bin", "Unity/Build/Polish/28/G_p28b/art_on/ds27_pos_lo_rgba8.bin",
            "Unity/Build/Polish/28/G_p28b/art_on/ds27_twhite_r32f.bin", "Unity/Build/Polish/28/G_p28b/timewarp_G_p28b.json",
            "Unity/Assets/GreatWave/Design39/Scenes/DS39_Paper.unity", "Unity/Build/Design/29R01/bake_kp/bake/af28r01_uvsdf_a45.bin")},
        "outputs_sha256": {p: sha256(os.path.join(REPO, p)) for p in outs},
        "evidence_sha256": {fn: sha256(os.path.join(EV, fn)) for fn in ev},
        "logs": sorted(rel(os.path.join(REPO, "Unity", "Build", "Polish", "28", "logs", f)) for f in os.listdir(os.path.join(REPO, "Unity", "Build", "Polish", "28", "logs")) if f.startswith("unity_pl28_u_")),
        "not_used_ja": "参照モデルの OBJ・利用者の解算・写真のフォルダー・爪形分析のフォルダーは開いていない。Blender・Houdini は使っていない。git は使っていない。",
    }
    with open(os.path.join(EV, "run_unity.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("PL28U_RECORD_DONE rows", len(rows))


if __name__ == "__main__":
    main()
