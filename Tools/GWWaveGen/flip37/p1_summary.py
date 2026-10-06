# -*- coding: utf-8 -*-
"""P1 の探索の表：各計算の analysis.json をまとめて table.json と table_ja.md を作る（py -3.10）。
使い方: py -3.10 p1_summary.py <run_id> ...（並べたい順）"""
import json, os, sys, math
sys.stdout.reconfigure(encoding="utf-8")

ROOT = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P1"
PT = json.load(open(ROOT + "/painting/painting_section.json", encoding="utf8"))
RA = PT["readings"]["A_side"]


def f(v, nd=2):
    return "—" if v is None or (isinstance(v, float) and not math.isfinite(v)) else ("%.*f" % (nd, v))


rows = []
md = ["| 計算 | 波 | 周期 T (s) | 入力の高さ (m) | 足元の波の高さ (m) | 斜面 1:n | 岩棚の水深 (m) | B の最大 | 砕けの始まり B>0.85：時刻 s / x m | 前の面が垂直を過ぎた：時刻 s / x m | 空洞が閉じた・ほぼ閉じた：時刻 s | 張り出し前の頂の高さ (m) | 巻き波 | 届き/Hc | 落ち/Hc | かぶり/Hc | 前の面の弦 (°) | 原画 A との点数（小さいほど近い） | 計算の時間 |",
      "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
for rid in sys.argv[1:]:
    p = os.path.join(ROOT, rid, "analysis.json")
    if not os.path.exists(p):
        continue
    a = json.load(open(p, encoding="utf8"))
    P = a["parms"]; ev = a["events"]
    bf = a["best_frame_vs_painting"]["A_side"]
    q = [x for x in a["timeline"] if bf and x["frame"] == bf["frame"]]
    q = q[0] if q else {}
    mode = int(round(P.get("wave_mode", 0)))
    kind = {0: "周期波の先頭", 1: "孤立波", 2: "群"}[mode]
    row = {"run_id": rid, "kind": kind, "T": P.get("T"), "H_in": P.get("H") if mode == 0 else P.get("Hs"),
           "H_toe": a.get("toe_gauge", {}).get("H_toe_m"), "slope_n": P.get("slope_n"), "hr": P.get("hr"), "h0": P.get("h0"),
           "B_max": ev["B_max"], "breaking_onset": ev["breaking_onset_B085"], "face_past_vertical": ev["face_past_vertical"],
           "tube_closed_or_nearly": ev["tube_closed_or_nearly"], "crest_max_before_overturn_m": ev["crest_max_before_overturn_m"],
           "plunging": a["plunging"], "best_vs_painting_A": bf,
           "shape_at_best": {k: q.get(k) for k in ("crest", "lip_tip", "inner_wall", "reach_over_Hc", "drop_over_Hc", "overhang_over_Hc",
                                                     "tube_aspect_w_over_h", "front_face_chord_angle_deg", "front_face_concavity_m",
                                                     "back_dx_to_075Hc_m", "back_slope_crest_to_075Hc_deg", "back_slope_25_75_deg",
                                                     "trough_ahead_m", "tube_inscribed_r_m", "covered_air_area_m2", "covered_air_LW")},
           "wall_total_s": a.get("wall_total_s"), "wall_per_frame_median_s": a.get("wall_per_frame_median_s"),
           "particles_max": a.get("particles_max"), "rss_peak_gb": a.get("rss_peak_gb"), "stopped": a.get("stopped"), "W": P.get("W"), "dp": P.get("dp")}
    rows.append(row)
    def tx(e):
        return ("%.2f / %.0f" % (e["t"], e["x"])) if e else "—"
    md.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        rid, kind, f(P.get("T"), 0) if mode != 1 else "—", f(row["H_in"], 0), f(row["H_toe"], 1), f(P.get("slope_n"), 0), f(P.get("hr"), 0) if mode != 1 else "（h0 %s）" % f(P.get("h0"), 0),
        f(ev["B_max"]), tx(ev["breaking_onset_B085"]), tx(ev["face_past_vertical"]),
        f(ev["tube_closed_or_nearly"]["t"]) if ev["tube_closed_or_nearly"] else "—", f(ev["crest_max_before_overturn_m"], 1),
        "**はい**" if a["plunging"] else "いいえ", f(q.get("reach_over_Hc")), f(q.get("drop_over_Hc")), f(q.get("overhang_over_Hc")),
        f(q.get("front_face_chord_angle_deg"), 0), ("%s（頂込み %s）" % (f(bf["score"], 3), f(bf.get("score_run"), 3))) if bf else "—",
        "%.1f 分" % ((a.get("wall_total_s") or 0) / 60.0)))
md.append("")
md.append("原画（読み A、主）の値：届き/Hc %s、落ち/Hc %s、かぶり/Hc %s、前の面の弦 %s°。" % (f(RA["reach_over_Hc"]), f(RA["drop_over_Hc"]), f(RA["overhang_over_Hc"]), f(RA["front_face_chord_angle_deg"], 0)))
json.dump(rows, open(ROOT + "/table.json", "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
open(ROOT + "/table_ja.md", "w", encoding="utf8").write("\n".join(md) + "\n")
print("\n".join(md))
