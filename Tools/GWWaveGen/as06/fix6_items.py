# -*- coding: utf-8 -*-
"""美術の見本06 の直しの回（段の行 R8 → R9）：批評の直しの項目（順位の順）ごとに、目標と R8・R9 の数を一つの表にする（読むだけ）。
出力：Build/Polish/sample06/fix/measure/fix_items.json（fix6_sheets.py の図 8 と記録が読む）。
数の出どころ：断面と折れ角（fix6_prof.py の prof_R8.json・prof_R9.json）、素早い測り（rows_quick.py の quick.json）、S11 の目標（targets_*.json）、
規則（rules_check_rows_before_fix.json・rules_check_rows.json）、細い白の切れ端（fix6_slivers.py の slivers.json）、爪の置き直しの試し（claw057.json）。
「届いた」は数の目標に届いたかだけで、美術の判定ではない（利用者が決める。Q30）。
使い方：py -3.10 -B Tools/GWWaveGen/as06/fix6_items.py
"""
import json
import os
import sys

P = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish"
PF = P + "/sample06/fix"


def jl(p):
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def sec(prof, c):
    for s in prof["sections"]:
        if abs(s["c"] - c) < 0.3:
            return s
    return {}


def tiers(prof, lo, hi):
    return [s for s in prof["sections"] if lo - 0.01 <= s["c"] <= hi + 0.01]


def main():
    pr = {"R8": jl(PF + "/measure/prof_R8.json"), "R9": jl(PF + "/measure/prof_R9.json")}
    qk = {"R8": jl(P + "/sample06/rows/measure/quick_R8/quick.json"), "R9": jl(PF + "/measure/quick_R9/quick.json")}
    tg = {"R8": jl(P + "/sample06/assemble/measure/targets_R8A.json"), "R9": jl(PF + "/measure/targets_R9.json")}
    ru = {"R8": jl(P + "/sample06/rules_check_rows_before_fix.json"), "R9": jl(P + "/sample06/rules_check_rows.json")}
    sl = jl(PF + "/measure/slivers.json")
    cl = jl(PF + "/measure/claw057.json")
    V = {}
    for k in ("R8", "R9"):
        p, q, t, r = pr[k], qk[k], tg[k], ru[k]
        L = q["geometry"]["layers"]
        hd = [sec(p, -19.42).get("head_0.5_m"), sec(p, -13.6).get("head_0.5_m")]
        ratio = min(s.get("mid_thick_over_protrusion", 9) for s in tiers(p, -21.6, -10.6))
        lean = [s.get("lower_half_chord_deg") for s in tiers(p, -21.1, -10.6)]
        led = p.get("left_end_descent", {})
        md = p.get("mesh_dihedral", {})
        ap = t["appearance"]
        V[k] = {
            "head_m_c-19.42_-13.6": hd, "mid_thick_over_protrusion_min": round(ratio, 3),
            "L5_2_3": [L["2"].get("undercut_m"), L["3"].get("undercut_m")],
            "lower_half_chord_deg_max_c-21_-10.6": max(x for x in lean if x is not None),
            "g1_bad_tri": None, "S8_p95": q["S8"]["dev_from_inner_face_m"]["p95"],
            "back_minus_lip_min_H0_c_le_-21": led.get("back_minus_tier_min_H0_c_le_-21"),
            "lip_crest_max_slope_deg_left_end": led.get("tier_crest_max_slope_deg"), "back_crest_max_slope_deg": led.get("back_crest_max_slope_deg"),
            "left_walls_m2_gt60_gt75": [md.get("left_end_walls", {}).get("area_left_facing_slope_gt60_m2"), md.get("left_end_walls", {}).get("area_left_facing_slope_gt75_m2")],
            "slivers_total": sl["runs"][k]["total"] if sl and k in sl["runs"] else None,
            "P2_top_indigo": ap["r2"]["top_880_1180"]["candidate"]["indigo"],
            "L6_label": {kk: vv["share_label_k"] for kk, vv in t["painting_label_consistency"].items()},
            "dihedral_flank3": [md.get("flank3_c-21_-17", {}).get("n_over_30"), md.get("flank3_c-21_-17", {}).get("max_deg")],
            "dihedral_under2": [md.get("under2_c-12.5_-10", {}).get("n_over_30"), md.get("under2_c-12.5_-10", {}).get("max_deg")],
            "sep_12_23": [t["separation_summary"]["1-2"]["separated_share"], t["separation_summary"]["2-3"]["separated_share"]],
            "L2_3": L["3"].get("crest_ahead_of_saddle_a_m"),
            "P1_top": ap["r3"]["top_1110_1300"]["candidate"], "P1_mid": ap["r3"]["mid_1300_1560"]["candidate"],
            "claw057_visible": None,
        }
        if r:
            g = r.get("fix_checks", r.get("assemble_checks", {})).get("g1_stretch_same_tool", {})
            gk = g.get(k) or g.get(k + "A")
            V[k]["g1_bad_tri"] = gk.get("bad_tri") if gk else None
            for c_ in r.get("claws_per_claw", []):
                if c_["user_id"] == "claw057":
                    V[k]["claw057_visible"] = c_.get("painting_visible_S04", {}).get("visible_frac")
            gg = r["rules"]["G2"]["gates"]
            V[k]["gates"] = [round(gg["78"]["claws"], 2), round(gg["130"]["claws"], 2), round(gg["131"]["claws"], 2), round(gg["132_s12"]["claws"], 2), round(gg["72_s12_p95"]["claws"], 2)]

    def ok(b):
        return "届いた" if b else "届かない"
    a, b = V["R8"], V["R9"]

    def p1(x):
        return "藍 %.3f・水色 %.3f・白 %.3f" % (x["indigo"], x["mizuiro"], x["white"])
    items = [
        {"rank": 1, "item": "唇が棒・管に見える（頭を太く、出に対して細くしない）",
         "target": "頭の厚さ ≥ 1.6 m（c −19.4・−13.6）、厚さ/出 ≥ 1/3、L5 ≥ 2.0・1.5 m",
         "R8": "頭 %s m、厚さ/出 最小 %.2f、L5 %s" % (a["head_m_c-19.42_-13.6"], a["mid_thick_over_protrusion_min"], a["L5_2_3"]),
         "R9": "頭 %s m、厚さ/出 最小 %.2f、L5 %s" % (b["head_m_c-19.42_-13.6"], b["mid_thick_over_protrusion_min"], b["L5_2_3"]),
         "status": ok(min(b["head_m_c-19.42_-13.6"]) >= 1.6 and b["mid_thick_over_protrusion_min"] >= 1 / 3 and b["L5_2_3"][0] >= 2.0 and b["L5_2_3"][1] >= 1.5) + "（数の目標）。回り台 0° の見え方は図で"},
        {"rank": 2, "item": "段の体の下の面を前へ傾ける（塊 LB2 の脛・足）",
         "target": "下の半分の弦の角 ≤ 65°（c −21〜−10.6）、G1 0、S8 p95 0、関門は同じ",
         "R8": "最大 %.1f°、G1 %s、S8 %.2f" % (a["lower_half_chord_deg_max_c-21_-10.6"], a["g1_bad_tri"], a["S8_p95"]),
         "R9": "最大 %.1f°、G1 %s、S8 %.2f、関門 %s" % (b["lower_half_chord_deg_max_c-21_-10.6"], b["g1_bad_tri"], b["S8_p95"], b.get("gates")),
         "status": ok(b["lower_half_chord_deg_max_c-21_-10.6"] <= 65 and (b["g1_bad_tri"] or 0) == 0 and b["S8_p95"] <= 0.0)},
        {"rank": 3, "item": "③ の左の端の台・崖をなくす",
         "target": "c ≤ −21 で唇が背の頂より ≥ 0.04 H0 低い、左の端は ≤ 45° で海と wave4 へ、S9 は同じ",
         "R8": "差の最小 %s H0、縁の下がり最大 %s°、左向きの壁 >60°・>75° %s m²" % (a["back_minus_lip_min_H0_c_le_-21"], a["lip_crest_max_slope_deg_left_end"], a["left_walls_m2_gt60_gt75"]),
         "R9": "差の最小 %s H0、縁の下がり最大 %s°（背の頂 %s°）、壁 %s m²" % (b["back_minus_lip_min_H0_c_le_-21"], b["lip_crest_max_slope_deg_left_end"], b["back_crest_max_slope_deg"], b["left_walls_m2_gt60_gt75"]),
         "status": "一部（≤ 45° は背の頂が約 58° で下がるので届かない）"},
        {"rank": 4, "item": "横から見た白い棒・旗をなくす",
         "target": "細い白の切れ端 0（回り台 12・7 視点）、P2-top 藍 0.10〜0.40、L6-label r2 ≥ 0.6",
         "R8": "切れ端 %s、P2-top 藍 %.3f、r2 %.3f" % (a["slivers_total"], a["P2_top_indigo"], a["L6_label"]["r2"]),
         "R9": "切れ端 %s、P2-top 藍 %.3f、r2 %.3f" % (b["slivers_total"], b["P2_top_indigo"], b["L6_label"]["r2"]),
         "status": "一部（P2-top・r2 は届いた。切れ端は 0 にならない）"},
        {"rank": 5, "item": "硬い折れをなくす（③ の脇・② の唇の下）",
         "target": "隣の面の角 ≤ 30°、G1 0",
         "R8": "③ の脇 %s 辺（最大 %s°）、② の下 %s 辺（%s°）" % (a["dihedral_flank3"][0], a["dihedral_flank3"][1], a["dihedral_under2"][0], a["dihedral_under2"][1]),
         "R9": "③ の脇 %s 辺（最大 %s°）、② の下 %s 辺（%s°）" % (b["dihedral_flank3"][0], b["dihedral_flank3"][1], b["dihedral_under2"][0], b["dihedral_under2"][1]),
         "status": ok(b["dihedral_flank3"][0] == 0 and b["dihedral_under2"][0] == 0) + "（② の右の端 c −10.6〜−10.0 に残る）"},
        {"rank": 6, "item": "15 視点の分かれに余裕を", "target": "①②・②③ とも ≥ 0.55（L2-3 ≥ 3.5 m で）",
         "R8": "%s・%s、L2-3 %s m" % (a["sep_12_23"][0], a["sep_12_23"][1], a["L2_3"]),
         "R9": "%s・%s、L2-3 %s m" % (b["sep_12_23"][0], b["sep_12_23"][1], b["L2_3"]),
         "status": "一部（②③ は届いた、①② は基準ちょうど）" if b["sep_12_23"][1] >= 0.55 and b["sep_12_23"][0] < 0.55 else ok(min(b["sep_12_23"]) >= 0.55)},
        {"rank": 7, "item": "原画視点の ③ の白を減らす（P1-top）", "target": "P1-top 藍 ≥ 0.10、P1-mid は合のまま、L6-label r3 ≥ 0.6",
         "R8": "上 %s、中 %s、r3 %.3f" % (p1(a["P1_top"]), p1(a["P1_mid"]), a["L6_label"]["r3"]),
         "R9": "上 %s、中 %s、r3 %.3f" % (p1(b["P1_top"]), p1(b["P1_mid"]), b["L6_label"]["r3"]),
         "status": ok(b["P1_top"]["indigo"] >= 0.1 and 0.4 <= b["P1_mid"]["indigo"] <= 0.8 and b["L6_label"]["r3"] >= 0.6)},
        {"rank": 8, "item": "claw057 を ② の段の面へ置き直す", "target": "原画視点で見える割合 ≥ 0.80、根元 ≤ 0.15 m、IoU p10 ≥ 0.875",
         "R8": "見える割合 %s" % a["claw057_visible"],
         "R9": "見える割合 %s%s" % (b["claw057_visible"], ("。相似の試し：%s" % cl["note_ja"]) if cl else ""),
         "status": "届かない（動かしていない。理由は記録）"},
    ]
    out = {"tool": "Tools/GWWaveGen/as06/fix6_items.py", "values": V, "items": items,
           "note_ja": "「届いた」は数の目標に届いたかだけ。目標の値は批評（サブエージェント）の言葉から取ったもので、利用者の言葉ではない"}
    json.dump(out, open(PF + "/measure/fix_items.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for it in items:
        print(it["rank"], it["status"], "|", it["R8"], "|", it["R9"])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
