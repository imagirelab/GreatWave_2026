# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の作る部の測り：視点によらない立体の材質（PL29 Ukiyoe Keypose）で描いた後（PL29Render の出力）を、前の点検（AUDIT、
pl29_audit_measure.py）と同じ数え方で数え、原画視点の評価器の値と並べる。

入力：
  --after <dir>   PL29Render の出力（views・diag・tt・t28_white・t28_claws・full・eval23・f71_count_pngseq.json・pl28u_regress.json）
  --audit <json>  前の点検の metrics_audit.json（同じ視点・同じ時刻の「前」の数）
  --rec <dir>     仕上げ28 の採用の Unity の描画（scene_rec。pl28u_regress.json と eval23/rec_*）
数える物（前の点検と同じ閾値。DFLAT 48 px、FLATMIN 2,000 px、CLAWMIN 40 px）：
  ・平らな面：主役波の画素で、色区の境（同じ面の隣の画素で色区が変わる所）と主役波の外から 48 px より離れた芯。芯の連結成分 ≥ 2,000 px を「平らな面」。
      同じ面の判定：前の点検は焼き込みの UV の差 ≤ 24 テクセル、後は主役波の行・列（_PL29Diag = 1 の印）の差 ≤ 3。
  ・溶けた爪：爪が主役波を隠す画素の成分（≥ 40 px）で、縁の 80% 以上が後ろの主役波と同じ色区。
  ・原画視点の色区の一致（記録）：原画の色区の地図（mw_colour_labels.png）と、原画視点 t* の ID の画像の、色区ごとの IoU・面積の割合・白／藍の一致。
  ・引き伸ばし・継ぎ目・外挿の帯は、焼き込みの投影の分類（uvcat）による数なので、後の材質には当てはまらない（数えない）。
    ［修正の回で直した読み］「投影がないので 0」は投影の引き伸ばしについてだけ言える。後の材質にも、面の座標（作る部は UV2 の s・行の c）が
    3 次元で伸び縮みする分の引き伸ばしがある（作る部の溝の間隔は p50 で 1.11〜1.21 倍、p95 で 2.2〜2.7 倍）。その数は pl29_stretch.py で別に数える。
出力：<out>/metrics_build.json
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_after_measure.py --after Unity/Build/Polish/29/after/p29b --audit Docs/Evidence/Polish/29/metrics_audit.json
         --rec Unity/Build/Polish/28/unity/scene_rec --out Unity/Build/Polish/29/after/p29b/measure
"""
import argparse
import glob
import hashlib
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

W, H = 1920, 1080
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TIMES = ["t060", "t090", "t105", "t120"]
DFLAT, FLATMIN, CLAWMIN, RCCONT = 48, 2000, 40, 3
CLS = ["白", "淡い水色", "藍中", "藍濃"]
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
LABELS = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels.png")
CP1 = {"78": 2.772, "130": 1.968, "131": 1.814, "132": 1.326, "72": 1.558}
R26 = {"78": 1.641, "130": 1.953, "131": 1.798, "132": 1.574, "72": 1.723}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rgba(p):
    return np.asarray(Image.open(p).convert("RGBA"))


def decode_id(p):
    a = rgba(p)[..., :3].astype(np.int32)
    cls = np.full(a.shape[:2], -1, np.int8)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hi, lo = 200, 50
    cls[(r > hi) & (g < lo) & (b < lo)] = 0
    cls[(r < lo) & (g > hi) & (b < lo)] = 1
    cls[(r < lo) & (g < lo) & (b > hi)] = 2
    cls[(r > hi) & (g > hi) & (b < lo)] = 3
    return cls


def decode_hero(p):
    a = rgba(p)
    hero = a[..., 3] == 128
    row = a[..., 0].astype(np.int32)
    col = a[..., 1].astype(np.int32) | (a[..., 2].astype(np.int32) << 8)
    return hero, row, col


def components(mask, minsize):
    lab, n = ndi.label(mask, structure=np.ones((3, 3), bool))
    if n == 0:
        return lab, []
    sizes = ndi.sum(np.ones_like(mask, dtype=np.int32), lab, index=np.arange(1, n + 1))
    objs = ndi.find_objects(lab)
    out = [{"label": i + 1, "area": int(s), "bbox": [int(sl[1].start), int(sl[0].start), int(sl[1].stop), int(sl[0].stop)]}
           for i, (s, sl) in enumerate(zip(sizes, objs)) if s >= minsize]
    out.sort(key=lambda d: -d["area"])
    return lab, out


def analyse(stem):
    hero0, row, col = decode_hero(stem + "_hero_claws0.png")
    hero1, _, _ = decode_hero(stem + "_hero_claws1.png")
    id0 = decode_id(stem + "_id_claws0.png")
    id1 = decode_id(stem + "_id_claws1.png")
    nhero = int(hero0.sum())
    res = {"heroPx": nhero}
    if nhero == 0:
        return res
    same_r = np.zeros_like(hero0); same_d = np.zeros_like(hero0)
    same_r[:, :-1] = hero0[:, :-1] & hero0[:, 1:] & (np.abs(row[:, :-1] - row[:, 1:]) <= RCCONT) & (np.abs(col[:, :-1] - col[:, 1:]) <= RCCONT)
    same_d[:-1, :] = hero0[:-1, :] & hero0[1:, :] & (np.abs(row[:-1, :] - row[1:, :]) <= RCCONT) & (np.abs(col[:-1, :] - col[1:, :]) <= RCCONT)
    c0 = id0
    ce_r = same_r & (c0 != np.roll(c0, -1, 1)) & (c0 >= 0) & (np.roll(c0, -1, 1) >= 0)
    ce_d = same_d & (c0 != np.roll(c0, -1, 0)) & (c0 >= 0) & (np.roll(c0, -1, 0) >= 0)
    edge_any = ce_r | ce_d
    edge_any[:, 1:] |= ce_r[:, :-1]
    edge_any[1:, :] |= ce_d[:-1, :]
    feat = edge_any | ~hero0
    dist = ndi.distance_transform_edt(~feat)
    core = hero0 & (dist > DFLAT)
    lab_core, flat_comps = components(core, FLATMIN)
    for fc in flat_comps:
        m = lab_core == fc["label"]
        cs = c0[m & (c0 >= 0)]
        fc["class"] = CLS[int(np.bincount(cs, minlength=4).argmax())] if cs.size else None
    cnt = np.bincount(c0[hero0 & (c0 >= 0)], minlength=4)
    res["classFrac"] = {CLS[k]: round(float(cnt[k] / max(cnt.sum(), 1)), 4) for k in range(4)}
    res["classEdgePx"] = int((ce_r | ce_d).sum())
    res["flat"] = {"corePx": int(core.sum()), "coreFracOfHero": round(float(core.sum() / nhero), 4), "regions": len(flat_comps),
                   "regionsList": [{"area": f["area"], "bbox": f["bbox"], "class": f["class"]} for f in flat_comps[:8]]}
    over = hero0 & ~hero1
    cl1 = id1
    claw_edge_all = np.zeros_like(over); claw_edge_diff = np.zeros_like(over)
    for sh, ax in ((1, 1), (-1, 1), (1, 0), (-1, 0)):
        nb_hero = np.roll(hero1, sh, ax); nb_cls = np.roll(cl1, sh, ax)
        e = over & nb_hero & (cl1 >= 0) & (nb_cls >= 0)
        claw_edge_all |= e
        claw_edge_diff |= e & (nb_cls != cl1)
    melted_edge = claw_edge_all & ~claw_edge_diff
    lab_cl, claw_comps = components(over, CLAWMIN)
    nmelt = 0
    for cc_ in claw_comps:
        m = lab_cl == cc_["label"]
        ea = int((claw_edge_all & m).sum()); em = int((melted_edge & m).sum())
        nmelt += bool(ea >= 10 and em / ea >= 0.8)
    res["claws"] = {"clawOverHeroPx": int(over.sum()), "clawEdgePx": int(claw_edge_all.sum()), "meltedEdgePx": int(melted_edge.sum()),
                    "meltedEdgeFrac": round(float(melted_edge.sum() / max(claw_edge_all.sum(), 1)), 4),
                    "whiteOnWhiteFrac": round(float((over & (cl1 == 0) & (id0 == 0)).sum() / max(over.sum(), 1)), 4),
                    "clawPieces": len(claw_comps), "clawPiecesMelted": int(nmelt)}
    return res


def painting_match(idp):
    L = np.asarray(Image.open(LABELS).convert("L"))
    C = decode_id(idp).astype(np.int16) + 1   # 1 白 … 4 藍濃
    m = (L >= 1) & (L <= 4)
    valid = m & (C >= 1)
    out = {}
    for k, n in [(1, "白"), (2, "淡い水色"), (3, "藍中"), (4, "藍濃")]:
        a = (C == k) & m; b = (L == k) & m
        out[n] = {"iou": round(float((a & b).sum() / max((a | b).sum(), 1)), 3), "render": round(float(a.sum() / m.sum()), 3), "painting": round(float(b.sum() / m.sum()), 3)}
    w1 = np.isin(C, [1, 2]); w2 = np.isin(L, [1, 2])
    out["白と藍の一致"] = round(float(((w1 == w2) & valid).sum() / valid.sum()), 3)
    out["色区の一致"] = round(float(((C == L) & valid).sum() / valid.sum()), 3)
    return out


def regress_table(after, rec):
    A = json.load(open(os.path.join(after, "pl28u_regress.json"), encoding="utf-8"))["sets"]
    R = json.load(open(os.path.join(rec, "pl28u_regress.json"), encoding="utf-8"))["sets"]
    gates, colour = {}, {}
    for st in ("t28_white", "t28_claws"):
        a, r = A[st], R[st]
        g = {}
        for k in ("78", "130", "131"):
            g[k] = {"after_px": a["strict"]["silhouettes_definition_reading"][k]["max_px"], "p28rec_px": r["strict"]["silhouettes_definition_reading"][k]["max_px"],
                    "cp1_px": CP1[k], "r26r01_px": R26[k], "gate_px": 4.0}
        g["132_s12_max"] = {"after_px": a["large_form"]["s12"]["132_max_px"], "p28rec_px": r["large_form"]["s12"]["132_max_px"], "cp1_px": CP1["132"], "r26r01_px": R26["132"], "gate_px": 4.0}
        g["72_s12_p95"] = {"after_px": a["large_form"]["s12"]["72_p95_px"], "p28rec_px": r["large_form"]["s12"]["72_p95_px"], "cp1_px": CP1["72"], "r26r01_px": R26["72"], "gate_px": 4.0}
        for k, v in g.items():
            v["pass"] = v["after_px"] <= v["gate_px"]
            v["regressVsP28rec_px"] = round(v["after_px"] - v["p28rec_px"], 4)
        gates[st] = g
        ci = {}
        for k, v in a["strict"]["colour_items"].items():
            rv = r["strict"]["colour_items"].get(k, {})
            ci[k] = {"after_px": v["max_now_px"], "after_verdict": v["verdict"], "p28rec_px": rv.get("max_now_px"), "p28rec_verdict": rv.get("verdict"),
                     "r28r01_px": v.get("r28r01_at_worst_px"), "worst_measure": v.get("worst_measure")}
        c265 = a["strict"]["colour_265_267"]; r265 = r["strict"]["colour_265_267"]
        ci["265_267"] = {"after": c265, "p28rec": r265}
        colour[st] = ci
    return gates, colour


def eval23(after, rec):
    out = {}
    for n in ("off_noline", "off_noline_noclaws", "off_line", "off_line_noclaws"):
        pa = glob.glob(os.path.join(after, "eval23", "*_" + n, "metrics.json"))
        pr = os.path.join(rec, "..", "eval23", "rec_" + n, "metrics.json")
        if not pa:
            continue
        a = json.load(open(pa[0], encoding="utf-8"))["items"]
        r = json.load(open(pr, encoding="utf-8"))["items"] if os.path.exists(pr) else {}
        rows = {}
        for k, v in a.items():
            rv = r.get(k, {})
            va = v.get("measures", [{}])[0] if v.get("measures") else {}
            vr = rv.get("measures", [{}])[0] if rv.get("measures") else {}
            rows[k] = {"after": v.get("verdict"), "p28rec": rv.get("verdict"), "after_max_px": va.get("value_max_px"), "p28rec_max_px": vr.get("value_max_px")}
        out[n] = {"items": rows, "after_pass": sum(1 for x in rows.values() if x["after"] == "pass"), "after_fail": sum(1 for x in rows.values() if x["after"] == "fail"),
                  "p28rec_pass": sum(1 for x in rows.values() if x["p28rec"] == "pass"), "p28rec_fail": sum(1 for x in rows.values() if x["p28rec"] == "fail"),
                  "changed": sorted([k for k, x in rows.items() if x["after"] != x["p28rec"]])}
    return out


def summarise(rows):
    s = {"images": len(rows), "heroPx": int(sum(r["heroPx"] for r in rows))}
    hp = max(s["heroPx"], 1)
    s["flatCoreFracOfHero"] = round(sum(r.get("flat", {}).get("corePx", 0) for r in rows) / hp, 4)
    s["flatRegions"] = int(sum(r.get("flat", {}).get("regions", 0) for r in rows))
    s["clawPieces"] = int(sum(r.get("claws", {}).get("clawPieces", 0) for r in rows))
    s["clawPiecesMelted"] = int(sum(r.get("claws", {}).get("clawPiecesMelted", 0) for r in rows))
    ce = sum(r.get("claws", {}).get("clawEdgePx", 0) for r in rows)
    s["clawMeltedEdgeFrac"] = round(sum(r.get("claws", {}).get("meltedEdgePx", 0) for r in rows) / max(ce, 1), 4)
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--after", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--rec", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    aud = json.load(open(a.audit, encoding="utf-8"))
    per, per_tt = {}, {}
    for v in VIEWS:
        for t in TIMES:
            st = os.path.join(a.after, "diag", v + "_" + t)
            if os.path.exists(st + "_hero_claws0.png"):
                per[v + "_" + t] = analyse(st)
    for t in TIMES:
        for az in range(0, 360, 30):
            st = os.path.join(a.after, "diag", "tt_%s_az%03d" % (t, az))
            if os.path.exists(st + "_hero_claws0.png"):
                per_tt["%s_az%03d" % (t, az)] = analyse(st)
    by_view = {}
    for v in VIEWS:
        rows = [per[k] for k in per if k.startswith(v + "_t")]
        bef = [aud["perImage"][k] for k in aud["perImage"] if k.startswith(v + "_t") and aud["perImage"][k].get("heroPx", 0) > 0 and "flatCoreFracOfHero" in aud["perImage"][k]]
        by_view[v] = {"after": summarise(rows),
                      "before": {"images": len(bef), "flatCoreFracOfHero": round(sum(b["flatCoreFracOfHero"] * b["heroPx"] for b in bef) / max(sum(b["heroPx"] for b in bef), 1), 4),
                                 "flatRegions": int(sum(b["flatRegions"] for b in bef)), "clawPieces": int(sum(b.get("clawPieces", 0) for b in bef)),
                                 "clawPiecesMelted": int(sum(b.get("clawPiecesMelted", 0) for b in bef)),
                                 "seamSegments": int(sum(b.get("seamSegments", 0) for b in bef)), "bands": int(sum(b.get("bands", 0) for b in bef)),
                                 "directFrac": round(sum(b["directFrac"] * b["heroPx"] for b in bef) / max(sum(b["heroPx"] for b in bef), 1), 4)}}
    tt_rows = list(per_tt.values())
    bef_tt = [b for b in aud["perTurntable"].values() if b.get("heroPx", 0) > 0 and "flatCoreFracOfHero" in b]
    by_view["turntable"] = {"after": summarise(tt_rows),
                            "before": {"images": len(bef_tt), "flatCoreFracOfHero": round(sum(b["flatCoreFracOfHero"] * b["heroPx"] for b in bef_tt) / max(sum(b["heroPx"] for b in bef_tt), 1), 4),
                                       "flatRegions": int(sum(b["flatRegions"] for b in bef_tt)), "clawPieces": int(sum(b.get("clawPieces", 0) for b in bef_tt)),
                                       "clawPiecesMelted": int(sum(b.get("clawPiecesMelted", 0) for b in bef_tt))}}
    nonp = [per[k] for k in per if not k.startswith("painting_")] + tt_rows
    gates, colour = regress_table(a.after, a.rec)
    pm = {}
    for nm, p in [("after_claws0", os.path.join(a.after, "diag", "painting_t120_id_claws0.png")), ("after_claws1", os.path.join(a.after, "diag", "painting_t120_id_claws1.png"))]:
        if os.path.exists(p):
            pm[nm] = painting_match(p)
    bdir = os.path.join(os.path.dirname(os.path.abspath(a.audit)))
    f71 = {}
    fp = os.path.join(a.after, "f71_count_pngseq.json")
    if os.path.exists(fp):
        d = json.load(open(fp, encoding="utf-8"))
        w = d["windows_video_frames"]["270_345"]
        f71 = {"window_270_345": {"M1b_sum_px": w["M1b_sum_px"], "M1b_max_px": w["M1b_max_px"], "M1_sum_px": w["M1_sum_px"]},
               "all": {"M2_line_off": d["all"]["M2_line_blink"]["off_clusters"], "M2_line_on": d["all"]["M2_line_blink"]["on_clusters"],
                       "M1b_big_blobs_ge20": d["all"]["M1b_fill_flicker"]["big_blobs_ge20"]},
               "before_window_270_345": aud["f71"]["windows"]["270_345"]}
    out = {"schema": "GreatWave.Polish29.build_measure/1", "noteJa": __doc__.strip().split("\n")[0],
           "inputs": {"after": a.after.replace("\\", "/"), "audit": a.audit.replace("\\", "/"), "audit_sha256": sha(a.audit), "rec": a.rec.replace("\\", "/")},
           "thresholds": {"DFLAT": DFLAT, "FLATMIN": FLATMIN, "CLAWMIN": CLAWMIN, "sameSurfaceRowColDiff": RCCONT},
           "summaryNonPainting": {"after": summarise(nonp), "before": aud["summaryNonPainting"]},
           "byView": by_view, "gates": gates, "colourItems": colour, "eval23": eval23(a.after, a.rec), "paintingMatch": pm, "f71": f71,
           "perImage": per, "perTurntable": per_tt}
    with open(os.path.join(a.out, "metrics_build.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({"summaryNonPainting": out["summaryNonPainting"]["after"], "byView": {k: v["after"] for k, v in by_view.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
