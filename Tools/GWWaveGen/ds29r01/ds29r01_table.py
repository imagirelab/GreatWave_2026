# -*- coding: utf-8 -*-
"""設計29修正01：測定の結果（Unity/Build/Design/29R01/measure/ の JSON）を、設計29 の原版（設計28 の網、16 bit）と並べた表にする。

入力（どれも読むだけ）：ds29r01_measure.py・ds29r01_extra.py・ds29r01_light.py の出力と、設計29 の証拠
（Docs/Evidence/Design/29/metrics.json の acceptance_original・sets、ds29_review_checks.json）。
出力：<out>/ds29r01_table.md（日本語の表）と ds29r01_table.json（値と判定）。
使い方：py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_table.py [--measure Unity/Build/Design/29R01/measure] [--out 同じ]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds29r01_common as C  # noqa: E402

REPO = C.REPO
EV29 = os.path.join(REPO, "Docs", "Evidence", "Design", "29")


def load(p):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def v(rep, key):
    if not rep:
        return None
    x = rep["verdicts"].get(key)
    return None if x is None else x["value"]


def fmt(x):
    if x is None:
        return "—"
    if isinstance(x, float):
        return "%.4g" % x
    if isinstance(x, (list, tuple)):
        return "／".join(fmt(y) for y in x)
    return str(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", default=os.path.join(C.OUT_ROOT, "measure"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    M = a.measure
    out_dir = a.out or M
    m29 = load(os.path.join(EV29, "metrics.json"))
    r29 = load(os.path.join(EV29, "ds29_review_checks.json"))
    acc29 = m29["acceptance_original"]
    s29 = m29["sets"]
    half29 = s29.get("half_r02") or {}
    qa = load(os.path.join(M, "qa_F_final_fine", "F_final_fine_qa.json"))
    qal = load(os.path.join(M, "qa_half_120x200_fine", "half_120x200_fine_qa.json"))
    qk = load(os.path.join(M, "qa_kstar_prime", "kstar_qa.json"))
    st = {k: load(os.path.join(M, "strict", "%s.json" % k)) for k in (
        "mesh_F_final_fine", "bvh_F_final_fine", "mesh_F_final_hi", "bvh_F_final_hi", "mesh_half_120x200_fine", "bvh_half_120x200_fine")}
    ts = load(os.path.join(M, "ds29r01_tstar.json"))
    fw = load(os.path.join(M, "ds29r01_farwall.json"))
    nm = load(os.path.join(M, "ds29r01_normals.json"))
    mem = load(os.path.join(M, "ds29r01_memory.json"))
    lt = load(os.path.join(M, "ds29r01_light_tstar.json"))
    lb = load(os.path.join(C.OUT_ROOT, "light", "ds29r01_light_build_half_120x200.json"))

    def sv(k):
        x = st.get(k)
        return None if not x else [x["shared_vertex"]["frames_with_hits"], x["shared_vertex"]["pairs_total"], x["shared_vertex"]["max_depth_mm"]]

    def bv(k):
        x = st.get(k)
        return None if not x else [x["frames_with_selfx"], x["pairs_total"]]

    def fo(k):
        x = st.get(k)
        return None if not x else [x["folds"]["frames_with_folds"], x["folds"]["fold_face_frames"], x["folds"]["transient_runs_ge3"],
                                   x["folds"]["faces_folded_at_tstar"]]

    rows = []

    def row(item, crit, d29, fine, hi, light, verdict, note=""):
        rows.append(dict(item=item, criterion=crit, d29_original=d29, r01_original_fine=fine, r01_original_hi=hi, r01_light=light,
                         verdict=verdict, note=note))

    # ---- 最小の受入
    stat = lambda rep: None if not rep else [v(rep, "非多様体の辺"), v(rep, "面の向きの反転（隣と巻き方向が食い違う辺）"),
                                             v(rep, "下を向き、上に網のない面（面の向きの反転、コマの和）"), v(rep, "自己交差（3 次元、BVH の重なり、コマの和）")]
    sf = stat(qa)
    row("メッシュ検査・静止の網の読み（36 コマ τ −4.433〜0 s）：非多様体・巻き方向の食い違い・下を向き上に網のない面・3 次元の自己交差（BVH、頂点を共有する組を除く、両方の面 ≥ 5 mm）",
        "0", [0, 0, 0, 0], sf, None, stat(qal), "合格" if sf and all(x == 0 for x in sf) else "不合格")
    row("同・断面の自己交差（線分 ≥ 5 mm、36 コマの和）", "0", acc29["section_self_crossing"]["value"],
        v(qa, "自己交差（行の断面、線分 ≥ 5 mm、コマの和）"), None, v(qal, "自己交差（行の断面、線分 ≥ 5 mm、コマの和）"),
        "合格" if v(qa, "自己交差（行の断面、線分 ≥ 5 mm、コマの和）") == 0 else "不合格")
    s_f, s_h = sv("mesh_F_final_fine"), sv("mesh_F_final_hi")
    b_f, b_h = bv("bvh_F_final_fine"), bv("bvh_F_final_hi")
    row("メッシュ検査・厳しい読み（30 Hz 全 361 コマ τ −12〜0 s）：頂点を 1 つ共有する組の貫通（コマ・組・深さの最大 mm、両方の面 ≥ 5 mm）",
        "0", [7, 7, 3.45], s_f, s_h, sv("mesh_half_120x200_fine"), "合格" if s_f and s_f[0] == 0 else ("—" if not s_f else "不合格"))
    row("同・頂点を共有しない組（BVH、361 コマ：コマ・組）", "0", [r29["bvh_src_d28"]["frames_with_selfx"], r29["bvh_src_d28"]["pairs_total"]],
        b_f, b_h, bv("bvh_half_120x200_fine"), "合格" if b_f and b_f[0] == 0 else ("—" if not b_f else "不合格"))
    row("同・30 Hz の前のコマと比べた面の反転（通し、361 コマ）", "0", acc29["temporal_flips_30hz"]["value"],
        v(qa, "30 Hz：前のコマと比べた面の反転（通し）"), None, v(qal, "30 Hz：前のコマと比べた面の反転（通し）"),
        "合格" if v(qa, "30 Hz：前のコマと比べた面の反転（通し）") == 0 else "不合格")
    seat = lambda rep: None if not rep else [v(rep, "座席 v1 の射線：穴（コマの和）"), v(rep, "座席 v1 の射線：開いた背面（コマの和）"),
                                             v(rep, "座席 v1 の射線：切断端＋縁の下のすき間（外周、t* のコマ）"), v(rep, "座席 v1 の射線：継ぎ目の切断（117、コマの和）")]
    se = seat(qa)
    row("座席 v1 の射線 5 万本 × 36 コマ：穴・開いた背面・t* の切断端・継ぎ目の切断（83・115・116・117）", "0",
        acc29["seat_rays_hole_openback_cutend_tstar"]["value"] + [0], se, None, seat(qal), "合格" if se and all(x == 0 for x in se) else "不合格")
    row("同・t* より前の外周の切断端／縁の下（記録。周りの海は設計30）", "記録", [37215, 33303],
        v(qa, "座席 v1 の射線：切断端／縁の下のすき間（外周、t* より前のコマの和。記録）"), None,
        v(qal, "座席 v1 の射線：切断端／縁の下のすき間（外周、t* より前のコマの和。記録）"), "記録")
    lay = mem["layouts"] if mem else {}
    row("keypose の GPU メモリ（位置＋T_white＋網、MiB。見積もり＝バッファの大きさの和）", "≤ 512",
        acc29["keypose_gpu_mib"]["value"],
        [lay["texture2darray_rgba64_rgba32_12B"]["total_with_twhite_mesh_mib"], lay["hi_plus_lo_structuredbuffer_10B"]["total_with_twhite_mesh_mib"]] if lay else None,
        lay["hi_only_structuredbuffer_6B"]["total_with_twhite_mesh_mib"] if lay else None,
        (lb or {}).get("gpu_estimate", {}).get("position_structured_buffer_mib"),
        "合格（読み取り不可のとき）", "精度の層つき：12 B（RGBA64＋RGBA32 の読み取り不可）／10 B（StructuredBuffer）。読み取り可能の写しを持つと %s MiB で不合格。Unity の実測は再生器の側" % (
            lay["texture2darray_rgba64_rgba32_readable_24B"]["total_with_twhite_mesh_mib"] if lay else "—"))
    tf = ts["decoded_tstar"]["fine"] if ts else None
    th = ts["decoded_tstar"]["hi"] if ts else None
    row("原画視点の回帰なし（t* の幾何の関門、K*′ の値との差の最大 px）", "±0.5", acc29["painting_regression"]["value_px"],
        tf["max_abs_diff_vs_kstar_gwb_px"] if tf else None, th["max_abs_diff_vs_kstar_gwb_px"] if th else None,
        (lt or {}).get("half_120x200", {}).get("max_abs_diff_vs_kstar_px"),
        "合格" if tf and tf["max_abs_diff_vs_kstar_gwb_px"] <= 0.5 else "不合格",
        "設計29 の値は Unity の t* の描画（28修正01 との差）。ここは幾何（同じ評価器、K*′ の評価表を差 0 で再現）。Unity の新しい描画は再生器の側")
    if tf:
        g = tf["gate"]
        row("t* の関門の値（78／130／131 最大、132 大きな輪郭 σ12 最大、72 大きな輪郭 σ24 p95、px）", "各 ≤ 4",
            None, [g["raw_78"]["max_px"], g["raw_130"]["max_px"], g["raw_131"]["max_px"], g["lf_132"]["max_px"], g["lf72_s24"]["p95_px"]],
            [th["gate"][k][s] for k, s in (("raw_78", "max_px"), ("raw_130", "max_px"), ("raw_131", "max_px"), ("lf_132", "max_px"), ("lf72_s24", "p95_px"))],
            [lt["half_120x200"]["gate"][k][s] for k, s in (("raw_78", "max_px"), ("raw_130", "max_px"), ("raw_131", "max_px"), ("lf_132", "max_px"), ("lf72_s24", "p95_px"))] if lt else None,
            "合格" if g["gate_pass"] else "不合格", "K*′ の評価表：2.741／3.831／2.924／3.905／3.746")
    if ts and ts.get("unity_image"):
        u = list(ts["unity_image"].values())[0]
        g = u["gate"]
        row("同・Unity の t* の画像（28R01F の F_final の描画、16 bit の再生器、ID 画像の被覆。引き継ぎ (d)）", "各 ≤ 4",
            None, None, [g["raw_78"]["max_px"], g["raw_130"]["max_px"], g["raw_131"]["max_px"], g["lf_132"]["max_px"], g["lf72_s24"]["p95_px"]], None,
            "合格" if g["gate_pass"] else "不合格（72 の大きな輪郭 σ24 p95 %.3f px）" % g["lf72_s24"]["p95_px"],
            "幾何との差の最大 %.3f px（±0.5 の内）" % u["max_abs_diff_vs_kstar_gwb_px"])
    row("t* の網と K*′ の差（頂点の最大 mm）", "記録", 1.2, tf["vertex_diff_vs_kstar_mm"]["max"] if tf else None,
        th["vertex_diff_vs_kstar_mm"]["max"] if th else None, None, "記録")
    # ---- 記録の項目
    lip = lambda rep: None if not rep else v(rep, "唇先の厚さ（唇先から 0.75 m 奥の鉛直）の最小_m")
    tl = None
    if qa:
        fr = [f for f in qa["frames"] if f["tau"] == 0.0]
        tl = fr[0]["lip_thick_min_m"] if fr else None
    row("薄膜：唇先の厚さの最小（唇先から 0.75 m 奥の鉛直、36 コマ）m", "≥ 0.3", 0.557, lip(qa), None, lip(qal),
        "不合格（記録。K*′ と動きの値）", "t* は %s m（K*′ 自身 %s m、c −24.2 m の 4 断面）。形成の途中は τ −2.7〜−2.4 s の唇の出始めに 0.021〜0.085 m" % (
            fmt(tl), fmt(qk["frames"][0]["lip_thick_min_m"] if qk else None)))
    if fw:
        row("奥の壁の最後の 0.067 s の下がり（30 Hz の二階差分の最大 m、τ −1/30 s）", "≤ 0.0218（2 g）", 0.111,
            fw["fine"]["max_last_m"], fw["hi"]["max_last_m"], None, "合格" if fw["fine"]["max_last_m"] <= fw["threshold_m"] else "不合格",
            "2 g を超える行 %d（設計29 は行 209〜214）。最後の 0.1 s の最大 %s m" % (fw["fine"]["n_rows_over_2g_last"], fmt(fw["fine"]["max_last_0p1s_m"])))
    row("30 Hz：地面の二階差分（全頂点、検査器の通し。P13 (2) は巻きの行だけ）m", "≤ 0.0218", 0.111,
        v(qa, "30 Hz：地面の二階差分（全頂点）_m"), None, v(qal, "30 Hz：地面の二階差分（全頂点）_m"), "不合格（記録。動きの値）",
        "場所：%s" % json.dumps(qa["sweep30"]["acc_all_m"]["at"], ensure_ascii=False) if qa else "")
    row("隣と逆向きの面（二面角 > 120°、36 コマのコマの最大）", "記録（K*′ 自身 %s）" % fmt(qk["frames"][0]["fold_edges_gt120deg"] if qk else None),
        161, v(qa, "隣と逆向きの面（二面角 > 120°、コマの最大）"), None, v(qal, "隣と逆向きの面（二面角 > 120°、コマの最大）"), "記録")
    row("折れ返り（隣 2 つ以上と逆向きの面、361 コマ）：折れのあるコマ・面コマ・t* の前に終わる 3 コマ以上の続き・t* の面", "記録",
        [r29["mesh_src_d28"]["folds"][k] for k in ("frames_with_folds", "fold_face_frames", "transient_runs_ge3", "faces_folded_at_tstar")],
        fo("mesh_F_final_fine"), fo("mesh_F_final_hi"), fo("mesh_half_120x200_fine"), "記録")
    if nm:
        f0 = nm["decoded"]["fine"]["frames"][0]
        h0 = nm["decoded"]["hi"]["frames"][0]
        row("K*′ の行 239（最後の行、1 mm 未満の線分 %d）の再生器の法線：決まらない法線（+Y）／行 238 との角度の最大°／K*′ の法線との角度の最大°（t*）" % nm["kstar_row239"]["row_segments_lt_1mm"],
            "K*′ と同じ", None, [f0["undefined"], f0["ang_vs_row238_deg"]["max"], f0["ang_vs_kstar_shader_normal_deg"]["239"]["max"]],
            [h0["undefined"], h0["ang_vs_row238_deg"]["max"], h0["ang_vs_kstar_shader_normal_deg"]["239"]["max"]], None,
            "合格（精度の層つき）" if f0["undefined"] == 0 and f0["ang_vs_kstar_shader_normal_deg"]["239"]["max"] < 2 else "不合格",
            "K*′ 自身：行 238 との角度の最大 %s°。16 bit だけでは最後の 1 s の最悪 %s°（決まらない %d）" % (
                nm["kstar_self"]["ang_row239_vs_238_deg"]["max"], nm["decoded"]["hi"]["worst"]["ang_vs_238_max"], nm["decoded"]["hi"]["worst"]["undefined"]))
        ff = nm["decoded"]["fine"].get("formation_far_rows")
        fh = nm["decoded"]["hi"].get("formation_far_rows")
        if ff:
            row("形成の間（30 Hz、361 コマ）の奥の端の行 228〜239：再生器の法線が 1 つ手前の行と 90° を超えて違う頂点（コマ・頂点コマ・最悪のコマ）",
                "記録", None, [ff["frames_with_flip"], ff["flip_vertex_frames"], ff["worst"]["n"] if ff["worst"] else 0],
                [fh["frames_with_flip"], fh["flip_vertex_frames"], fh["worst"]["n"] if fh["worst"] else 0] if fh else None, None,
                "記録（見えない：28R01F の Unity の静止画 τ −4.889・−3.202 s で、座席から波の方向は 88〜123 m 先で船の陰、原画視点は画面の左端の一様な藍濃（帯の幅 約 0.5 px）。measure/crop_farrows_*.png）",
                "最悪 τ %s s の行 %s・列 %s（c +14.2〜+14.6 m、高さ 2 m 未満の奥の端。このコマでは原画視点の画面の外、τ −3.2 s ごろに画面の左端へ入る）。K*′ の行 234 と 235 の間で列の割り付けが約 1 m 跳ぶ所の剪断。t* では 0" % (
                    ff["worst"]["tau"], ff["worst"]["rows"], ff["worst"]["cols"]) if ff["worst"] else "")
    if lb:
        row("層の数／節点の追加（軽量版は管の天井の弧長の滑りで足す）", "記録", 186, 242, 242, "%d（%s）" % (lb["layers"], "＋".join(str(r["added"]) for r in lb["adaptive_rounds"])), "記録")
    if lt:
        row("軽量版：原画視点の輪郭の差（原版の t* との対称の距離、px）", "≤ 4（117）", 3.6, None, None,
            lt["half_120x200"]["silhouette_vs_original_painting"]["max_px"] if lt["half_120x200"]["silhouette_vs_original_painting"] else None, "合格（原画視点）", "座席の視点の輪郭と色区は Unity の描画が要る（未測定）")
    doc = dict(schema="GreatWave.DS29R01.table/1", number="設計29修正01", rows=rows,
               sources=dict(d29_metrics=C.rel(os.path.join(EV29, "metrics.json")), d29_review=C.rel(os.path.join(EV29, "ds29_review_checks.json")), measure=C.rel(M)))
    C.jdump(os.path.join(out_dir, "ds29r01_table.json"), doc)
    L = ["# 設計29修正01：表示用サーフェス（F_final の K*′ の格子）の測定と設計29 の原版の比べ", "",
         "- 設計29 の原版＝設計28 の網（K\\* 26修正01 の格子、16 bit の読み）。29修正01 の原版＝設計28修正01 の F_final のパッケージそのもの（K\\*′ の格子 240 × 400、242 層）。",
         "- 復号：「精度の層」＝16 bit ＋ ds27_pos_lo_rgba8.bin（刻み 6.9 µm）、「16 bit」＝設計27〜29 の再生器の読み（刻み 1.75 mm、参考）。",
         "- 軽量版＝120 × 200 の r02 の張り方（唇 column・管の天井 arc_tau）を F_final から作り直したもの（精度の層つき）。", "",
         "| 項目 | 基準 | 設計29 の原版 | 29修正01 原版（精度の層） | 同（16 bit、参考） | 軽量版 120 × 200 | 判定（原版） | 注 |",
         "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (r["item"], r["criterion"], fmt(r["d29_original"]), fmt(r["r01_original_fine"]),
                                                               fmt(r["r01_original_hi"]), fmt(r["r01_light"]), r["verdict"], r["note"]))
    with open(os.path.join(out_dir, "ds29r01_table.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    # 実行の記録（コマンド・道具と入出力の SHA-256）
    tools = [os.path.join(HERE, f) for f in ("ds29r01_common.py", "ds29r01_measure.py", "ds29r01_extra.py", "ds29r01_light.py", "ds29r01_table.py")]   # パート B の道具だけ
    ds29 = [os.path.join(REPO, "Tools", "GWWaveGen", "ds29", f) for f in ("ds29_qa.py", "ds29_blender_qa.py", "ds29_review_checks.py",
                                                                          "ds29_review_blender.py", "ds29_surface.py", "ds29_build.py", "ds29_params.json")]
    pkg = os.path.join(REPO, C.DEFAULT_PACKAGE)
    kd = os.path.join(REPO, C.DEFAULT_KSTAR)
    inputs = [os.path.join(pkg, f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin")]
    inputs += [os.path.join(kd, f) for f in sorted(os.listdir(kd)) if not f.startswith("_")]
    outs = []
    for root, _, files in os.walk(M):
        for f in files:
            if f.endswith((".json", ".md", ".png")):
                outs.append(os.path.join(root, f))
    lite = os.path.join(C.OUT_ROOT, "light", "half_120x200")
    if os.path.isdir(lite):
        outs += [os.path.join(lite, f) for f in ("ds27_keypose.json", "ds27_pos_rgba16.bin", "ds27_pos_lo_rgba8.bin", "ds27_twhite_r32f.bin", "ds29_uv3_f32.bin")]
    run = dict(schema="GreatWave.DS29R01.run/1", number="設計29修正01（表示用サーフェスの測定、パート B）",
               python="py -3.10（numpy %s）" % __import__("numpy").__version__, blender="Blender 5.2.2（ds29_qa.BLENDER）",
               commands=["py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py qa --decode fine",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py strict --decode fine",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py strict --decode hi",
                         "py -3.10 -B -c（ds29_qa.main --kstar を ds29r01_common.setup() の後に。出力 measure/qa_kstar_prime）",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py memory",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py tstar --unity-ids F_final_28R01F=Unity/Build/Design/28R01F/unity/F_final/t28/render/af28r01_class_ids.png",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py farwall",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py normals",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_light.py（決定性：--out Unity/Build/Design/29R01/light/_twice）",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py qa --package half_120x200=Unity/Build/Design/29R01/light/half_120x200 --ref Unity/Build/Design/28R01F/F_final/art_on",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_measure.py strict --package half_120x200=Unity/Build/Design/29R01/light/half_120x200",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_extra.py light_tstar --light half_120x200=Unity/Build/Design/29R01/light/half_120x200",
                         "py -3.10 -B Tools/GWWaveGen/ds29r01/ds29r01_table.py"],
               tools={C.rel(p): C.sha256_file(p) for p in tools + ds29 if os.path.isfile(p)},
               inputs={C.rel(p): C.sha256_file(p) for p in inputs if os.path.isfile(p)},
               outputs={C.rel(p): C.sha256_file(p) for p in sorted(outs) if os.path.isfile(p) and not p.endswith("run.json")})
    C.jdump(os.path.join(out_dir, "run.json"), run)


if __name__ == "__main__":
    main()
