# -*- coding: utf-8 -*-
"""gwcase の JSON を集めて、数の表（JSON）と報告用の Markdown の表を作る。

使い方：python3 gwtable.py 出力.json 解析1.json 解析2.json ...
"""
import os, sys, json

PAPER = dict(Hb_over_h0=0.64, x_bp=42.05, t_touchdown=19.96, A_J_over_Hb2=0.219, A_O_over_Hb2=0.352,
             W_over_L=0.300, theta_O_deg=29.0, jet_width_over_h0=0.05)


def row(path):
    d = json.load(open(path, encoding="utf8"))
    s = d["summary"]; meta = d.get("meta", {})
    b = d["ruler"]["best"] or {}; td = d["ruler"]["touchdown"] or {}
    pick = lambda r, ks: {k: r.get(k) for k in ks}
    rk = ("t", "score3", "eta_c", "face_chord_deg_01_05", "front_x01_rel", "hood_area", "gap_max", "gap_max_is_lower_bound",
          "lip_thick_mid", "back_angle_07_09_deg", "width07_silhouette")
    out = dict(name=meta.get("name", os.path.basename(path)), meta=meta,
               paper_measures=pick(s, ("t_overturn", "x_c_overturn", "eta_c_overturn", "eta_c_max", "t_touchdown", "td_by",
                                       "x_c_touchdown", "x_tip_touchdown", "eta_c_touchdown", "A_O", "A_J", "jet_width",
                                       "A_O_over_Htd2", "A_J_over_Htd2", "jet_width_over_Htd", "A_O_over_Hov2", "A_J_over_Hov2",
                                       "A_O_over_Hmax2", "A_J_over_Hmax2", "theta_O_deg", "W_over_L", "aspect_moment", "note")),
               ruler_best=pick(b, rk), ruler_touchdown=pick(td, rk), ruler_n_frames=d["ruler"]["n_frames"])
    return out


def main(out, paths):
    rows = [row(p) for p in paths]
    json.dump(dict(paper_feddersen2024=PAPER, cases=rows), open(out, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    f = lambda v, n=3: ("%.*f" % (n, v)) if isinstance(v, (int, float)) and v is not None else "—"
    print("| 算例 | 段 | 着水 t | 頂 x（着水） | 先 x（着水） | 頂の高さ（着水） | A_O/H² | A_J/H² | W/L | θ_O | 噴流の幅/H |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        p = r["paper_measures"]
        print("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["name"], r["meta"].get("level", "—"), f(p.get("t_touchdown"), 2), f(p.get("x_c_touchdown"), 2), f(p.get("x_tip_touchdown"), 2),
            f(p.get("eta_c_touchdown")), f(p.get("A_O_over_Htd2")), f(p.get("A_J_over_Htd2")), f(p.get("W_over_L")),
            f(abs(p["theta_O_deg"]) if p.get("theta_O_deg") is not None else None, 1), f(p.get("jet_width_over_Htd"))))
    print()
    print("| 算例 | 段 | score3 最小（t） | 前の面の弦 | 前の足 | 覆いの面積 | 唇の下の空気 | 唇の厚み | 背の角 | 0.7 η_c の幅 | 着水の score3 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        b = r["ruler_best"]; td = r["ruler_touchdown"]
        print("| %s | %s | %s（%s） | %s° | %s | %s | %s | %s | %s° | %s | %s |" % (
            r["name"], r["meta"].get("level", "—"), f(b.get("score3"), 2), f(b.get("t"), 2), f(b.get("face_chord_deg_01_05"), 1),
            f(b.get("front_x01_rel")), f(b.get("hood_area")), f(b.get("gap_max")), f(b.get("lip_thick_mid")),
            f(b.get("back_angle_07_09_deg"), 1), f(b.get("width07_silhouette"), 2), f(td.get("score3"), 2)))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
