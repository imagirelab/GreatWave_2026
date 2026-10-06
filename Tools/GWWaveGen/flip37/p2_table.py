# -*- coding: utf-8 -*-
"""P2 の表（py -3.10）：各計算の analysis.json を集めて Unity/Build/FLIP37/P2/table_ja.md・table.json を書く。
使い方: py -3.10 p2_table.py <run_id> ...
"""
import sys, os, json
import numpy as np
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

P2 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2"


def reef_ja(p):
    s = []
    if p.get("lens_A", 0) > 0:
        s.append("レンズ A%g・幅%g・両側+%g m" % (p["lens_A"], p["lens_zl"], p.get("lens_dh", 0)))
    if abs(p.get("lens_z0", 0) or 0) > 0:
        s.append("レンズの中心 z %g" % p["lens_z0"])
    if abs(p.get("obl_deg", 0)) > 0:
        s.append("斜め %g°" % p["obl_deg"])
    if p.get("lg1_d", 0) > 0:
        s.append("低い棚 %g m（z %g）" % (p["lg1_d"], p["lg1_z"]))
    if p.get("lg2_d", 0) > 0:
        s.append("低い棚 %g m（z %g）" % (p["lg2_d"], p["lg2_z"]))
    return "、".join(s) if s else "まっすぐ（B0）"


def row(rid):
    an = json.load(open(os.path.join(P2, rid, "analysis.json"), encoding="utf8"))
    p = an["parms"]; b = an.get("best") or {}; a = an.get("at_best") or {}
    secs = an.get("sections", {})
    zc = (secs.get("z-118") or secs.get("z-119") or {}) if float(p.get("mirror_z", 0) or 0) > 0.5 else (secs.get("z+000") or {})
    ev = zc.get("events") or {}
    # 張り出しのある切り口の数と、その瞬間に近い切り口の値（頂の z に近い順）
    over = [k for k, v in secs.items() if (v.get("at_best") or {}).get("overturned")]
    zcrest = a.get("z_crest", 0.0)
    near = min(secs.items(), key=lambda kv: abs(int(kv[0][1:]) - zcrest)) if secs else (None, {})
    if an.get("section_hump") and an["section_hump"] in secs:
        near = (an["section_hump"], secs[an["section_hump"]])   # 20:55 から：最初に巻いた切り口の値
    q = (near[1] or {}).get("at_best") or {}
    plunge_secs = [k for k, v in secs.items() if v.get("plunging")]
    r = {
        "run_id": rid, "reef": reef_ja(p), "cross_deg": p.get("cross_deg", 0), "H_in": p.get("H"), "T": p.get("T"),
        "stopped": an.get("stopped"),
        "t_best": b.get("t"), "psi_deg": b.get("psi_deg"), "scale": b.get("scale"), "iou": b.get("iou"),
        "dist_mean_px": (b.get("outline_dist") or {}).get("mean_px"), "dist_median_px": (b.get("outline_dist") or {}).get("median_px"),
        "Hc": a.get("Hc_m"), "z_crest": a.get("z_crest"), "n_peaks": a.get("n_peaks_prom08"), "peaks": a.get("peaks"),
        "crest_len_075": a.get("crest_len_075Hc_m"), "crest_len_15": a.get("crest_len_15m_m"),
        "over_z_extent": a.get("overturned_z_extent_m"), "over_z_range": a.get("overturned_z_range"),
        "side_swell": a.get("side_swell_m"),
        "sec_near_crest": near[0], "overhang_Hc": q.get("overhang_over_Hc"), "reach_Hc": q.get("reach_over_Hc"), "drop_Hc": q.get("drop_over_Hc"),
        "tube_aspect": q.get("tube_aspect_w_over_h"), "face_deg": q.get("front_face_chord_angle_deg"), "tube_r": q.get("tube_inscribed_r_m"),
        "center_onset": ev.get("breaking_onset_B085"), "center_overturn": ev.get("face_past_vertical"), "center_tube": ev.get("tube_closed_or_nearly"),
        "plunging_sections": sorted(plunge_secs, key=lambda s: int(s[1:])), "n_sections": len(secs),
        "wall_min": (an.get("wall_total_s") or 0) / 60, "s_per_frame": an.get("wall_per_frame_median_s"),
        "mirror": bool(a.get("mirror")), "cross_z0": p.get("cross_z0", 0),
        "near46": (a.get("side_swell_m") or {}).get("near_dz-46"), "far46": (a.get("side_swell_m") or {}).get("far_dz+46"),
        "recall": b.get("recall_painting_covered"), "outside": b.get("outside_covered"),
        "toe": {k: v.get("H_toe_m") for k, v in (an.get("toe_gauge_x400") or {}).items()},
        "n_vert_sections": sum(1 for v in secs.values() if (v.get("events") or {}).get("face_past_vertical")),
        "t_first_vert": an.get("t_first_overturn_any_section"), "f_end_done": an.get("f_end_done"),
        "onset": an.get("at_onset"), "first_ov": an.get("at_first_overturn"),
        "particles_max": an.get("particles_max"), "rss_peak_gb": an.get("rss_peak_gb"),
    }
    return r


def f(v, fmt="%.2f"):
    return "—" if v is None else (fmt % v)


def main(rids):
    rows = [row(r) for r in rids]
    json.dump(rows, open(os.path.join(P2, "table.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    L = ["| 計算 | 岩棚 | 交わり | 入力 H (m) | 足元の波の高さ z=0 (m) | 原画に近い瞬間 t (s) | 置き方 ψ・倍率 | IoU | 原画の波を覆う割合・外を覆う割合 | 輪郭の距離 平均/中央 (px) | 頂 Hc (m) | 山の数 | 頂から手前 46 m・奥 46 m の頂 (m) | 峰の長さ 0.75Hc / 15 m (m) | 張り出しの z の幅 (m) | 横のうねり z<-100 / z>100 (m) | 砕け始めの峰：時刻・山の数・頂・半分の高さの幅・手前 46 m の頂・端 100 m の遅れ | 最初に巻いた切り口：かぶり・届き・落ち (/Hc) | 空洞の幅/高さ・前の面 | 中央の切り口：砕け・垂直を過ぎた・空洞 (s) | 垂直を過ぎた切り口・巻いた切り口 | 最初に垂直を過ぎた (s) | 時間 (分)・1 コマ (s) |",
         "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        ce = r["center_onset"] or {}; co = r["center_overturn"] or {}; ct = r["center_tube"] or {}
        toe0 = r["toe"].get("z-120") if r["mirror"] else r["toe"].get("z+0")
        on = r["onset"] or {}
        ons = "%s s・%s・%s m・%s m・%s m・%s m" % (f(on.get("t")), f(on.get("n_peaks_prom08"), "%d"), f(on.get("Hc_m"), "%.1f"), f(on.get("half_width_m"), "%.0f"),
                                                f(on.get("near_dz-46"), "%.1f"), f(on.get("x_lag_at_dz100"), "%.0f")) if on else "—"
        L.append("| %s | %s | %s | %s | %s | %s | %s°・%s | %s | %s・%s | %s / %s | %s | %s | %s・%s | %s / %s | %s | %s / %s | %s | %s：%s・%s・%s | %s・%s° | %s・%s・%s | %d・%d/%d | %s | %s・%s |" % (
            r["run_id"], r["reef"], (("±%g°" % r["cross_deg"]) + ("（水路の形・壁で鏡）" if r["mirror"] else "")) if r["cross_deg"] else "—", f(r["H_in"], "%g"), f(toe0, "%.1f"), f(r["t_best"]),
            f(r["psi_deg"], "%d"), f(r["scale"], "%.1f"), f(r["iou"], "%.3f"), f(r["recall"], "%.2f"), f(r["outside"], "%.2f"), f(r["dist_mean_px"], "%.0f"), f(r["dist_median_px"], "%.0f"),
            f(r["Hc"], "%.1f"), f(r["n_peaks"], "%d"), f(r["near46"], "%.1f"), f(r["far46"], "%.1f"), f(r["crest_len_075"], "%.0f"), f(r["crest_len_15"], "%.0f"), f(r["over_z_extent"], "%.0f"),
            f((r["side_swell"] or {}).get("z<-100"), "%.1f"), f((r["side_swell"] or {}).get("z>100"), "%.1f"), ons,
            r["sec_near_crest"] or "—", f(r["overhang_Hc"]), f(r["reach_Hc"]), f(r["drop_Hc"]), f(r["tube_aspect"]), f(r["face_deg"], "%.0f"),
            f(ce.get("t")), f(co.get("t")), f(ct.get("t")), r["n_vert_sections"], len(r["plunging_sections"]), r["n_sections"], f(r["t_first_vert"]), f(r["wall_min"], "%.1f"), f(r["s_per_frame"])))
    open(os.path.join(P2, "table_ja.md"), "w", encoding="utf8").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main(sys.argv[1:])
