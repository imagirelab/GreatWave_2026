# -*- coding: utf-8 -*-
"""設計28修正01 試行F：E（古い K*）と F の各タグ（F_R1・F_R2・…）を並べる表（json と md）。検査の出力だけを読む（生成器は読まない）。

読むもの：E は Unity/Build/Design/28R01E/{review/review_E.json, E/gates/*.json, E/art_on/ds27_checks.json, E/art_on/ds28r01e_generate_log.json}
と <根>/E_ref/scan_E.json。F は <根>/<tag>/{scan.json, gates/*.json, art_on/ds27_checks.json, art_on/ds28r01f_generate_log.json, art_on/p20_f_layers.json,
pipeline_timing.json} と <根>/review/review_<tag>.json。
使い方：py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_table.py [--root Unity/Build/Design/28R01F]
"""
import argparse
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def jl(p):
    p = p if os.path.isabs(p) else os.path.join(REPO, p)
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def g(d, *ks, default=None):
    for k in ks:
        if d is None:
            return default
        if isinstance(d, dict):
            d = d.get(k)
        elif isinstance(d, list) and isinstance(k, int) and k < len(d):
            d = d[k]
        else:
            return default
    return default if d is None else d


def fmt(v, n=3):
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "合" if v else "否"
    if isinstance(v, float):
        return ("%%.%dg" % n) % v if abs(v) < 1e4 else "%.0f" % v
    if isinstance(v, (list, tuple)):
        return "／".join(fmt(x, n) for x in v)
    return str(v)


def collect(tag, root):
    if tag == "E":
        E = "Unity/Build/Design/28R01E"
        return dict(tag="E（古い K*）", review=g(jl(E + "/review/review_E.json"), "E"), scan=jl(root + "/E_ref/scan_E.json"),
                    gates={k: jl("%s/E/gates/%s.json" % (E, k)) for k in ("default", "default_fine", "default_fine_stop13", "alt", "default_q13")},
                    checks=jl(E + "/E/art_on/ds27_checks.json"), gen=jl(E + "/E/art_on/ds28r01e_generate_log.json"), p20=None, timing=None,
                    p20e={k: jl("%s/p20/%s.json" % (E, k)) for k in ("lean_with_height", "tower_peak_off", "curl_lead", "back_hold_water")},
                    rows=("159", "192"))
    rv = jl("%s/review/review_%s.json" % (root, tag))
    rv = g(rv, tag)
    rows = tuple(k for k in (g(rv, "front_crest") or {}).keys())
    return dict(tag=tag, review=rv, scan=jl("%s/%s/scan.json" % (root, tag)),
                gates={k: jl("%s/%s/gates/%s.json" % (root, tag, k)) for k in ("default", "default_fine", "default_fine_stop13", "alt", "default_q13")},
                checks=jl("%s/%s/art_on/ds27_checks.json" % (root, tag)), gen=jl("%s/%s/art_on/ds28r01f_generate_log.json" % (root, tag)),
                p20=jl("%s/%s/art_on/p20_f_layers.json" % (root, tag)), timing=jl("%s/%s/pipeline_timing.json" % (root, tag)),
                p20w=jl("%s/%s/art_on/p20_back_width_retarget.json" % (root, tag)),
                p20e={k: jl("%s/%s/p20_e/%s.json" % (root, tag, k)) for k in ("lean_with_height", "tower_peak_off", "curl_lead", "back_hold_water")},
                rows=rows)


def gate_val(G, p):
    if G is None:
        return None
    for sec in ("gates", "gates_ds28"):
        e = g(G, sec, p)
        if e is not None:
            return e
    return None


def pair(rv, key, sub, rows):
    return [g(rv, key, r, *sub) for r in rows] if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="Unity/Build/Design/28R01F")
    a = ap.parse_args()
    root = a.root
    tags = ["E"] + sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(REPO, root, "F_*", "scan.json")))
    C = [collect(t, root) for t in tags]
    L = []

    def row(name, crit, fn):
        vals = []
        for c in C:
            try:
                vals.append(fn(c))
            except Exception:
                vals.append(None)
        L.append(dict(item=name, criterion=crit, values={c["tag"]: v for c, v in zip(C, vals)}))
    # ---- M1
    row("M1 断面の自己交差のこま（60 Hz、τ −8〜0）", "0", lambda c: g(c["scan"], "m1", "section_selfx_frames"))
    row("M1 断面の自己交差の行", "なし", lambda c: (lambda v: "%d 行（%s）" % (len(v), fmt(v[:6])) if v else "なし")(g(c["scan"], "m1", "section_selfx_rows")))
    row("M1 動きが作った網の局所の自己交差のこま", "0", lambda c: g(c["scan"], "m1", "local_selfx_motion_frames"))
    row("M1 K*′ から受け継いだ局所の自己交差（t* の頂点）", "記録", lambda c: "%s（行 %s）" % (g(c["scan"], "m1", "local_selfx_kstar_inherited_at_tstar"),
                                                                                        fmt(g(c["scan"], "m1", "local_selfx_kstar_inherited_rows"))))
    row("M1 E のまま（F の層なし）の断面の自己交差のこま（120 Hz）／行", "記録", lambda c: "%s／%s 行" % (
        g(c["gen"], "result", "scan", "prebridge", "e_raw", "section_frames"), len(g(c["gen"], "result", "scan", "prebridge", "e_raw", "section_rows") or [])))
    # ---- M2
    row("M2 t* と K*′ の差の最大（行の断面／gwb float32）[mm]", "≤ 1 mm", lambda c: [1000 * g(c["scan"], "m2", "tstar", "max_vs_kstar_rows_m"),
                                                                                1000 * g(c["scan"], "m2", "tstar", "max_vs_gwb_float32_m")])
    row("M2 本体の水 V（τ −2／−1／0）[m³]", "跳びなし", lambda c: [g(c["scan"], "m2", "volume", "V_at", k) for k in ("-2.0", "-1.0", "+0.0")])
    row("M2 最後の 2 s の 1 こまの変化の最大 ÷ その前（τ −4〜−2）の最大", "≤ 1（跳びなし）", lambda c: g(c["scan"], "m2", "volume", "last2s_step_ratio"))
    row("M2 最後の 2 s の最小からの戻り（V、主断面の断面積）", "記録（設計27 は +33%）", lambda c: [g(c["scan"], "m2", "volume", "refill_after_min_frac"),
                                                                                      g(c["scan"], "m2", "volume", "A_main_refill_after_min_frac")])
    row("M2 最後の 1 s の行き過ぎて戻る量の最大／p99 [m]", "≤ E", lambda c: [g(c["scan"], "m2", "backtrack_last1s", "overshoot_max_m"),
                                                                        g(c["scan"], "m2", "backtrack_last1s", "overshoot_p99_m")])
    row("M2 最後の 1 s の逆向きの道のりの最大／p99 [m]", "≤ E", lambda c: [g(c["scan"], "m2", "backtrack_last1s", "retro_max_m"),
                                                                     g(c["scan"], "m2", "backtrack_last1s", "retro_p99_m")])
    # ---- M3
    row("M3 唇ができる前の頂の角 θc の最小（主断面／峰の行）[°]", "≥ 125", lambda c: [g(c["scan"], "m3", "rows", "main", "theta_c_min_before_lip_deg"),
                                                                             g(c["scan"], "m3", "rows", "c+3.85", "theta_c_min_before_lip_deg")])
    row("M3 同じ、巻きのある全行の最小（行）", "≥ 125", lambda c: "%s（行 %s）、< 125 の行 %s" % (fmt(g(c["scan"], "m3", "curled_rows_min_deg")),
                                                                                  g(c["scan"], "m3", "curled_rows_min_at", "row"), g(c["scan"], "m3", "curled_rows_below_125")))
    row("M3 t* の θc（主断面／峰の行）[°]", "K*′ の丸い頂", lambda c: [g(c["scan"], "m3", "rows", "main", "theta_c_tstar_deg"),
                                                               g(c["scan"], "m3", "rows", "c+3.85", "theta_c_tstar_deg")])
    row("M3 画面の最後の 3 s の θc の最小（主断面／峰の行）[°]", "直角にならない", lambda c: [g(c["scan"], "m3", "rows", "main", "last3s_theta_c_min_deg"),
                                                                           g(c["scan"], "m3", "rows", "c+3.85", "last3s_theta_c_min_deg")])
    row("M3 最後の 3 s に t* より尖った量（主断面／峰の行）[°]", "≈ 0", lambda c: [g(c["scan"], "m3", "rows", "main", "last3s_sharpen_below_tstar_deg"),
                                                                        g(c["scan"], "m3", "rows", "c+3.85", "last3s_sharpen_below_tstar_deg")])
    # ---- E から保つもの（目標の検査器）
    row("保つ：小山 → C 字の画面の時間（主断面／峰の行）[s]", "≥ 3.0", lambda c: pair(c["review"], "pace", ("hump_to_C_s",), c["rows"]))
    row("保つ：形の変わる速さの立ち上がり（速さの段）[m/s²]", "≤ 2.0", lambda c: pair(c["review"], "pace", ("vdef_up_rise_max_mps2",), c["rows"]))
    row("保つ：唇の見え始めの H/Hf（Lo 0.05H）", "≤ 0.85／0.91", lambda c: pair(c["review"], "front_crest", ("events", "Lo0.05H", "H_over_Hf"), c["rows"]))
    row("保つ：唇の見え始め（唇先 1 m 前）の H/Hf", "≤ 0.85／0.91", lambda c: [min(v["H_over_Hf_visible"] for v in (g(c["review"], "curl_share_checker", r) or {}).values() if v)
                                                                       for r in c["rows"]])
    row("保つ：巻き下がりの画面 10 s より後の割合（唇先の列の最小〜最大）", "峰の行 ≤ 0.50",
        lambda c: ["%s〜%s" % (fmt(min(v["share_after_t10"] for v in (g(c["review"], "curl_share_checker", r) or {}).values() if v and v.get("share_after_t10") is not None)),
                              fmt(max(v["share_after_t10"] for v in (g(c["review"], "curl_share_checker", r) or {}).values() if v and v.get("share_after_t10") is not None)))
                   for r in c["rows"]])
    row("保つ：唇先の頂点の後の再上昇 > 1 cm の点（唇／管）", "0", lambda c: [g(c["review"], "no_rebound", "lip", "rerise_gt_1cm"), g(c["review"], "no_rebound", "tube", "rerise_gt_1cm")])
    def trough_of(c, key):
        if c["tag"].startswith("E"):
            return [g(v, key) for v in (g(c["review"], "trough") or {}).values()]
        k2 = {"D_over_H_tstar": "D_over_H_tstar", "spearman_H_D": "spearman_H_D_10hz"}[key]
        return [g(v, k2) for v in (g(c["scan"], "trough", "rows") or {}).values()]
    row("保つ：前の谷 D/H（t*、谷の行。E は E の検査器、F は走査（列 j_corner より前の最低点））", "高さとともに深く", lambda c: trough_of(c, "D_over_H_tstar"))
    row("保つ：前の谷の深さと高さの順位相関（谷の行）", "≈ 1", lambda c: trough_of(c, "spearman_H_D"))
    row("保つ：行のジグザグ J1 の最大（τ −6〜0）", "≤ 0.07", lambda c: max(v["J1_zigzag_frac"] for k, v in (g(c["review"], "spatial") or {}).items()
                                                                         if isinstance(v, dict) and "J1_zigzag_frac" in v))
    row("保つ：量子化の刻み（精度の層つき）[mm]", "≤ 0.25", lambda c: g(c["review"], "quant_step_mm"))
    row("保つ：止め（速さ 0.5 → 0）[s]", "≥ 0.8", lambda c: g(c["review"], "warp", "stop_len_s"))
    row("保つ：Hermite の再生の差の最大 [mm]", "≤ 4", lambda c: 1000 * g(c["checks"], "hermite_playback_err_m", "max"))
    row("保つ：唇先の画面の加速度、最後の 1 s（波の枠）[m/s²]", "≤ 8", lambda c: [g(c["review"], "tip_screen_accel_last1s", r, "max_wave_frame_mps2") for r in c["rows"]])
    row("保つ：最後の 2 s の頂の尖り θc(t10) − θc(t*)（E の検査器）[°]", "≤ 5", lambda c: pair(c["review"], "front_crest", ("sharpen_last2s_deg",), c["rows"]))
    row("保つ：節点のこま ÷ 間のこまの法線の段（精度の層）", "≤ 1.3", lambda c: g(c["review"], "j5", "fine", "ratio_knot_over_between"))
    row("層の数／GPU の見積もり（精度の層、MiB）", "≤ 512（読み取り可能の写し込み）", lambda c: [g(c["gen"], "result", "layers"),
                                                                             g(c["gen"], "result", "gpu_estimate", "fine_texture2darray_readable_mib")])
    # ---- 関門
    for p in ["P%d" % k for k in range(1, 20)] + ["Painting"]:
        def fg(c, p=p):
            e = gate_val(c["gates"]["default"], p)
            ef = gate_val(c["gates"]["default_fine"], p)
            if e is None:
                return None
            v = e.get("value")
            ok = e.get("pass")
            s = "%s %s" % ("合" if ok else ("否" if ok is False else "—"), fmt(v if not isinstance(v, dict) else list(v.values())))
            if ef is not None and ef.get("pass") != ok:
                s += "（精度の層：%s）" % ("合" if ef.get("pass") else "否")
            return s
        row("関門 %s（16 bit の既定）" % p, "", fg)
    row("関門 P16（精度の層、止め 1.3 s まで）", "≤ 0.05", lambda c: "%s %s" % ("合" if gate_val(c["gates"]["default_fine_stop13"], "P16").get("pass") else "否",
                                                                          fmt(gate_val(c["gates"]["default_fine_stop13"], "P16").get("value"))))
    row("関門の不合格（16 bit の既定、P1〜P19）", "", lambda c: fmt(g(c["gates"]["default"], "summary_all", "failed")))
    # ---- M5
    row("M5 生成の時間 [s]", "≤ 1,800", lambda c: g(c["gen"], "result", "seconds"))
    row("M5 生成と検査の全体 [s]", "記録", lambda c: g(c["timing"], "timing", "total_s"))
    row("F の層の大きさ P20（層：最大の頂点の差 [m]）", "記録", lambda c: "；".join("%s %s" % (k.split("（")[0], fmt(v.get("max_vertex_diff_m")))
                                                                  for k, v in (g(c["p20"], "layers") or {}).items() if k != "back_width_retarget") or None)
    row("F の層の大きさ P20：ds_back_width_retarget（近似）[m]", "記録", lambda c: g(c.get("p20w"), "max_vertex_diff_m"))
    row("E の値の大きさ P20（lean_with_height・tower_peak_off・curl_lead・back_hold_water）[m]", "記録",
        lambda c: [g(c["p20e"], k, "max_vertex_diff_m") for k in ("lean_with_height", "tower_peak_off", "curl_lead", "back_hold_water")])
    out = dict(tags=[c["tag"] for c in C], rows_measured={c["tag"]: list(c["rows"]) for c in C}, table=L)
    op = os.path.join(REPO, root, "table_E_F.json")
    with open(op, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    md = ["# 設計28修正01 試行F：E（古い K*）と F の比べ", "",
          "行（主断面／峰の行）：" + "、".join("%s = %s" % (c["tag"], "／".join(c["rows"])) for c in C) + "（K*′ では c = 0 と +3.85 m の行）", "",
          "| 項目 | 基準 | " + " | ".join(c["tag"] for c in C) + " |", "| --- | --- | " + " | ".join("---" for _ in C) + " |"]
    for r in L:
        md.append("| %s | %s | %s |" % (r["item"], r["criterion"], " | ".join(fmt(r["values"][c["tag"]]) for c in C)))
    with open(os.path.join(REPO, root, "table_E_F.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(md) + "\n")
    print(op)


if __name__ == "__main__":
    main()
