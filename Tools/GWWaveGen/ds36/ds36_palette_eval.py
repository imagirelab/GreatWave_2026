# -*- coding: utf-8 -*-
"""設計36 第「調色板」部：Unity の描画（DS36Render）から、色票の表・爪の影の色の受入・200（根元の白）・谷の読み・回帰の表を作る（numpy/OpenCV、py -3.10）。

入力（Git 対象外）：Unity/Build/Design/36/palette/unity/（ds36_render_report.json、chart/、t28_*、ds30_tstar_regress.json、tstar_sym_*）、
  Unity/Build/Design/36/palette/prep/（ds36_claw_palette.json、ds36_palette_prep.json）、設計32 の爪の領域（_regions.npy、ds32_claw_inventory.json）、
  原画の色区（Tools/PaintingTruth/colour/masks/mw_colour_labels.png）、比べる前の値（設計29修正01・設計34）。
出力：Unity/Build/Design/36/palette/ds36_palette_metrics.json、ds36_colour_chart.csv、ds36_colour_chart_ja.txt、fig/*.png

爪の内側の影の色の受入（計画 §2.3 の設計36、§6 の爪の領域の定義 D25）：
  A) t* に背を向けた縁の側面と下面の色＝一覧の色区（Unity の報告の爪ごとの影の色 と ds36_claw_palette.json の shadow_class が 148/148 一致）。
  B) t* の原画視点で、各爪の領域（藍の輪郭線の内側）の中に描かれた爪の画素のうち、原画の色区が白でない（影の）画素で、描画の色区が原画の色区と
     同じ割合（全体）≥ 0.90、かつ影の画素が 20 px 以上ある爪で「描画の影の色区の最多」＝「一覧の色区」の爪の割合 ≥ 0.90。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds36/ds36_palette_eval.py
"""
import csv
import glob
import hashlib
import json
import os
import re

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
B36 = os.path.join(REPO, "Unity", "Build", "Design", "36", "palette")
U = os.path.join(B36, "unity")
PREP = os.path.join(B36, "prep")
FIG = os.path.join(B36, "fig")
LABELS = os.path.join(REPO, "Tools", "PaintingTruth", "colour", "masks", "mw_colour_labels.png")
REGIONS = os.path.join(REPO, "Unity", "Build", "Design", "32", "list+ids", "_regions.npy")
INVENTORY = os.path.join(REPO, "Unity", "Build", "Design", "32", "list+ids", "ds32_claw_inventory.json")
R29 = os.path.join(REPO, "Unity", "Build", "Design", "29R01", "unity")
D34 = os.path.join(REPO, "Unity", "Build", "Design", "34", "unity3", "main")
W, H = 1920, 1080
# 番号23 の表示フレーム：x_d = S·(x_r + 0.5) − 0.5 + OX、y_d = S·(y_r + 0.5) − 0.5（ds32_claw_inventory.json の coordinate_convention_ja）
S, OX = 0.416345, 156.66153
NAMES = ["white", "mizuiro", "ai_mid", "ai_dark"]
IDC = {(255, 0, 0): 0, (0, 255, 0): 1, (0, 0, 255): 2, (255, 255, 0): 3}
REGC = {"hero": (255, 0, 0), "sea_near": (0, 255, 0), "sea_far": (0, 0, 255), "claws": (255, 0, 255), "spray": (0, 255, 255), "sea_other_ds27": (255, 255, 0)}
EXACT = 6.0          # 調色板の値からの RGB の距離がこれ以下なら、その色（アンチエイリアスの混ざりはそれより遠い）


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def imread(p, flag=cv2.IMREAD_COLOR):
    im = cv2.imdecode(np.fromfile(p, np.uint8), flag)
    if im is None:
        raise FileNotFoundError(p)
    return im[..., ::-1].copy() if im.ndim == 3 else im


def imwrite(p, rgb):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cv2.imencode(".png", np.ascontiguousarray(rgb[..., ::-1]))[1].tofile(p)


def srgb_to_lab(rgb8):
    c = np.asarray(rgb8, np.float64) / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ M.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def palette_table(rep):
    ents = []
    for e in rep["heroPalette"] + [rep["lineColour"]]:
        rgb = [e["r8"], e["g8"], e["b8"]]
        lab = srgb_to_lab(np.array(rgb))
        ents.append({"name": e["name"], "srgb8": rgb, "hex": "#%02X%02X%02X" % tuple(rgb), "lab": [round(float(x), 2) for x in lab], "value_L": round(float(lab[0]), 2)})
    return ents


def classify(img, pal):
    """色の画像の各画素を、調色板（白・淡い水色・藍中・藍濃・線）の最も近い色へ。距離が EXACT を超える画素は −1（混ざり・調色板の外）。"""
    P = np.array([e["srgb8"] for e in pal], np.float32)
    d = np.linalg.norm(img[..., None, :].astype(np.float32) - P[None, None], axis=-1)
    k = d.argmin(-1)
    k[d.min(-1) > EXACT] = -1
    return k


def region_masks(reg):
    m = {}
    for n, c in REGC.items():
        m[n] = np.all(reg == np.array(c, np.uint8), -1)
    anym = np.zeros(reg.shape[:2], bool)
    for v in m.values():
        anym |= v
    m["other"] = ~anym           # 空・富士・船・背景
    return m


def chart(rep, pal):
    rows = []
    Lp = {e["name"]: e["value_L"] for e in pal}
    names = [e["name"] for e in pal]
    for cp in sorted(glob.glob(os.path.join(U, "chart", "ds36_colour_*.png"))):
        mt = re.match(r"ds36_colour_(.+)_t(\d+\.\d+)s\.png", os.path.basename(cp))
        view, t = mt.group(1), float(mt.group(2))
        rp = os.path.join(U, "chart", "ds36_region_%s_t%05.2fs.png" % (view, t))
        img = imread(cp)
        reg = imread(rp)
        k = classify(img, pal)
        lab = srgb_to_lab(img)
        for rn, m in region_masks(reg).items():
            n = int(m.sum())
            if n == 0:
                continue
            row = {"view": view, "t": t, "region": rn, "px": n, "frame_share_pct": round(100.0 * n / (W * H), 3)}
            for i, nm in enumerate(names):
                row["share_%s_pct" % nm] = round(100.0 * float((k[m] == i).sum()) / n, 3)
            row["share_off_palette_pct"] = round(100.0 * float((k[m] < 0).sum()) / n, 3)
            row["mean_L"] = round(float(lab[..., 0][m].mean()), 2)
            # 調色板の色だけの画素の明度（色区の面積で重みを付けた L*）
            on = k[m] >= 0
            row["palette_weighted_L"] = round(float(np.mean([Lp[names[j]] for j in k[m][on]])) if on.any() else float("nan"), 2)
            rows.append(row)
    return rows


def claw_regions_display(inv, ids):
    regs = np.load(REGIONS, allow_pickle=True)
    reg = {str(r[0]): r[1] for r in regs}
    cx, cy = inv["params"]["crop"][0], inv["params"]["crop"][1]
    out = {}
    for cid in ids:
        if cid not in reg or reg[cid] is None:
            continue
        x0, y0, M = reg[cid]
        x0 += cx; y0 += cy
        A = np.array([[S, 0, S * (x0 + 0.5) - 0.5 + OX], [0, S, S * (y0 + 0.5) - 0.5]], np.float64)
        md = cv2.warpAffine(M.astype(np.float32), A, (W, H), flags=cv2.INTER_LINEAR) > 0.5
        out[cid] = md
    return out


def ids_display(p):
    """3840×2160 の色区 ID を 1920×1080 へ（2×2 の左上でなく右下の画素＝表示の画素の中の点）。"""
    im = imread(p)
    im = im[1::2, 1::2]
    k = np.full(im.shape[:2], -1, np.int16)
    for c, v in IDC.items():
        k[np.all(im == np.array(c, np.uint8), -1)] = v
    return k


def claw_acceptance(rep, cp, inv):
    ids = rep["clawIds"]
    per_u = rep["clawShadowClassPerClaw"]
    js = {c["id"]: c["shadow_class"] for c in cp["claws"]}
    a_match = sum(1 for i, cid in enumerate(ids) if int(round(per_u[i])) == js.get(cid, -9))
    lab = imread(LABELS, cv2.IMREAD_UNCHANGED)
    rend = ids_display(os.path.join(U, "t28_claws", "t28", "render", "af28r01_class_ids.png"))
    regimg = imread(os.path.join(U, "chart", "ds36_region_painting_t12.00s.png"))
    claw_px = np.all(regimg == np.array(REGC["claws"], np.uint8), -1)
    regs = claw_regions_display(inv, ids)
    per = []
    tot_sh = tot_ok = 0
    tot_all = tot_all_ok = 0
    for cid in ids:
        if cid not in regs:
            per.append({"id": cid, "region": False})
            continue
        m = regs[cid] & claw_px
        lt = lab[m].astype(np.int16) - 1          # 0 白 … 3 藍濃（線・空・範囲の外は 4 以上か −1）
        rk = rend[m]
        valid = (lt >= 0) & (lt <= 3) & (rk >= 0)
        sh = valid & (lt >= 1)
        n_sh = int(sh.sum()); ok = int((sh & (rk == lt)).sum())
        tot_sh += n_sh; tot_ok += ok
        tot_all += int(valid.sum()); tot_all_ok += int((valid & (rk == lt)).sum())
        rsh = rk[(rk >= 1)]
        dom = int(np.bincount(rsh, minlength=4)[1:].argmax() + 1) if rsh.size else -1
        per.append({"id": cid, "region": True, "claw_px_in_region": int(m.sum()), "shadow_px_label": n_sh, "shadow_px_agree": ok,
                    "rendered_shadow_counts": np.bincount(rsh, minlength=4)[1:].tolist() if rsh.size else [0, 0, 0],
                    "rendered_shadow_dominant": dom, "list_shadow_class": js.get(cid), "dominant_matches_list": dom == js.get(cid)})
    judged = [p for p in per if p.get("region") and p["shadow_px_label"] >= 20]
    dm = sum(1 for p in judged if p["dominant_matches_list"])
    res = {
        "A_hidden_faces_list_class_match": {"match": a_match, "of": len(ids), "pass": a_match == len(ids)},
        "B_painting_tstar": {"shadow_px": tot_sh, "shadow_px_agree": tot_ok, "shadow_agree_frac": round(tot_ok / max(1, tot_sh), 4),
                             "all_px": tot_all, "all_agree_frac": round(tot_all_ok / max(1, tot_all), 4),
                             "claws_judged_ge20_shadow_px": len(judged), "claws_dominant_match": dm, "claws_dominant_match_frac": round(dm / max(1, len(judged)), 4),
                             "claws_with_region": sum(1 for p in per if p.get("region")),
                             "mismatch_ids": [p["id"] for p in judged if not p["dominant_matches_list"]]},
        "criterion_ja": "A：148/148。B：影の画素の一致 ≥ 0.90 かつ、影の画素 20 px 以上の爪で最多の影の色区＝一覧の色区が ≥ 0.90。",
        "per_claw": per,
    }
    b = res["B_painting_tstar"]
    res["pass"] = bool(res["A_hidden_faces_list_class_match"]["pass"] and b["shadow_agree_frac"] >= 0.90 and b["claws_dominant_match_frac"] >= 0.90)
    return res, regs, claw_px, rend, lab


def seat_claw_colours(pal):
    out = {}
    for v in ("seat", "seat_low", "seat_toward_wave", "painting"):
        for t in (10.0, 12.0):
            cp = os.path.join(U, "chart", "ds36_colour_%s_t%05.2fs.png" % (v, t))
            rp = os.path.join(U, "chart", "ds36_region_%s_t%05.2fs.png" % (v, t))
            if not os.path.exists(cp):
                continue
            img = imread(cp); reg = imread(rp)
            m = np.all(reg == np.array(REGC["claws"], np.uint8), -1)
            k = classify(img, pal)[m]
            n = int(m.sum())
            out["%s_t%.1f" % (v, t)] = {"claw_px": n, **{nm: round(float((k == i).sum()) / max(1, n), 4) for i, nm in enumerate(e["name"] for e in pal)},
                                        "off_palette": round(float((k < 0).sum()) / max(1, n), 4)}
    return out


def root_white(inv, ids, rend, lab):
    """200（根元の白、記録）：一覧の根元（root_ref）を表示の画素へ写し、半径 2 px の中の描画（t* の原画視点の色区 ID、爪あり）と原画の色区の白の割合。"""
    claws = {c["id"]: c for c in inv["claws"]}
    rows = []
    for cid in ids:
        c = claws.get(cid)
        if not c or not c.get("root_ref"):
            continue
        xr, yr = c["root_ref"]
        xd = S * (xr + 0.5) - 0.5 + OX; yd = S * (yr + 0.5) - 0.5
        xi, yi = int(round(xd)), int(round(yd))
        if not (2 <= xi < W - 2 and 2 <= yi < H - 2):
            continue
        rr = rend[yi - 2:yi + 3, xi - 2:xi + 3]; ll = lab[yi - 2:yi + 3, xi - 2:xi + 3]
        rows.append({"id": cid, "root_display": [round(xd, 1), round(yd, 1)], "render_white_frac": round(float((rr == 0).mean()), 3),
                     "painting_white_frac": round(float((ll == 1).mean()), 3)})
    rw = np.array([r["render_white_frac"] for r in rows]); pw = np.array([r["painting_white_frac"] for r in rows])
    return {"n": len(rows), "render_root_white_ge_0p5": int((rw >= 0.5).sum()), "painting_root_white_ge_0p5": int((pw >= 0.5).sum()),
            "both_white": int(((rw >= 0.5) & (pw >= 0.5)).sum()), "render_white_painting_not": int(((rw >= 0.5) & (pw < 0.5)).sum()),
            "painting_white_render_not": int(((rw < 0.5) & (pw >= 0.5)).sum()), "mean_abs_diff": round(float(np.abs(rw - pw).mean()), 4) if len(rows) else None,
            "note_ja": "記録のみ（仕上げ33）。一覧の根元の点の半径 2 px（5×5）の中の白の割合。3D の爪の根元の白の円は、t* に原画のカメラを向いていれば原画の色区で塗る（投影）。",
            "per_claw": rows}


def regress_summary():
    rp = os.path.join(U, "ds30_tstar_regress.json")
    if not os.path.exists(rp):
        return None
    r = load(rp)
    out = {"base_29r01": r["base_29r01"], "sets": {}}
    base_sym = load(os.path.join(R29, "tstar_sym", "tstar_sym.json"))
    base_v = load(os.path.join(R29, "f_final_kp", "ds29r01_tstar_verdict.json"))
    ref = {"29R01": {"265_dE00": base_v["colour_265_267"]["265"]["now"]["dE00"],
                     "267_white_bands_strict": base_sym["flat_painting_view_266_267"]["kp"]["white"]["strict"]["bands_ge_20px"],
                     "266_ai_mid_bands_sym": base_sym["flat_painting_view_266_267"]["kp"]["ai_mid"]["sym"]["bands_ge_20px"],
                     "266_mizuiro_bands_sym": base_sym["flat_painting_view_266_267"]["kp"]["mizuiro"]["sym"]["bands_ge_20px"],
                     "267_white_bands_sym": base_sym["flat_painting_view_266_267"]["kp"]["white"]["sym"]["bands_ge_20px"],
                     "verdicts_sym": base_sym["verdicts_kp_sym"]}}
    for tag, d in (("DS34_claws", os.path.join(D34, "tstar_sym_t28_claws")), ("DS34_white", os.path.join(D34, "tstar_sym_t28_white"))):
        sp = os.path.join(d, "tstar_sym.json")
        vp = os.path.join(D34, tag.split("_")[1].join(["t28_", ""]), "ds29r01_tstar_verdict.json")
        if os.path.exists(sp):
            sy = load(sp)
            v = load(vp) if os.path.exists(vp) else None
            ref[tag] = {"265_dE00": v["colour_265_267"]["265"]["now"]["dE00"] if v else None,
                        "266_ai_mid_bands_sym": sy["flat_painting_view_266_267"]["kp"]["ai_mid"]["sym"]["bands_ge_20px"],
                        "266_mizuiro_bands_sym": sy["flat_painting_view_266_267"]["kp"]["mizuiro"]["sym"]["bands_ge_20px"],
                        "267_white_bands_sym": sy["flat_painting_view_266_267"]["kp"]["white"]["sym"]["bands_ge_20px"],
                        "verdicts_sym": sy["verdicts_kp_sym"]}
    out["reference"] = ref
    for s, e in r["sets"].items():
        sy = load(os.path.join(U, "tstar_sym_" + s, "tstar_sym.json"))
        v = load(os.path.join(U, s, "ds29r01_tstar_verdict.json"))
        now = {"265_dE00": v["colour_265_267"]["265"]["now"]["dE00"], "265_verdict": v["colour_265_267"]["265"]["verdict_now"],
               "266_verdict": v["colour_265_267"]["266"]["verdict_now"],
               "266_ai_mid_bands_sym": sy["flat_painting_view_266_267"]["kp"]["ai_mid"]["sym"]["bands_ge_20px"],
               "266_mizuiro_bands_sym": sy["flat_painting_view_266_267"]["kp"]["mizuiro"]["sym"]["bands_ge_20px"],
               "267_white_bands_sym": sy["flat_painting_view_266_267"]["kp"]["white"]["sym"]["bands_ge_20px"],
               "verdicts_sym": sy["verdicts_kp_sym"], "rows_sym": sy["rows"],
               "lfgate": e["lfgate"], "silhouette_diff_vs_29r01_px": e["silhouette_diff_vs_29r01_px"], "lfgate_diff_vs_29r01_px": e["lfgate_diff_vs_29r01_px"],
               "sym_worst_diff_vs_29r01_px": e.get("sym", {}).get("worst_diff_vs_29r01_px"), "sym_diff_vs_29r01_over_0p5": e.get("sym", {}).get("diff_vs_29r01_over_0p5")}
        b = ref["29R01"]
        now["267_white_bands_strict"] = sy["flat_painting_view_266_267"]["kp"]["white"]["strict"]["bands_ge_20px"]
        now["266_mizuiro_bands_strict"] = sy["flat_painting_view_266_267"]["kp"]["mizuiro"]["strict"]["bands_ge_20px"]
        # 29修正01 が採った両側の読み：266・267 は「真値の色区を 3 px 縮め、描画の空から 2 px 以内を除いた範囲」の 20 px 以上の帯の数
        # （評価器の中の 267 の判定は定義のままの帯の数で、29修正01 でも 7 本で不合格。ここでは使わない）
        now["no_regression_265_266_267_vs_29r01"] = {
            "265": now["265_verdict"] == "pass" and now["265_dE00"] <= b["265_dE00"] + 0.5,
            "266": now["266_verdict"] == "pass" and now["266_ai_mid_bands_sym"] <= b["266_ai_mid_bands_sym"] and now["266_mizuiro_bands_sym"] <= b["266_mizuiro_bands_sym"],
            "267": now["267_white_bands_sym"] <= b["267_white_bands_sym"]}
        # 計画 §2.0 の回帰の項目（合格していたもの）
        lf = e["lfgate"]; bl = r["base_29r01"]["lfgate"]
        now["plan_2_0"] = {"78_130_131_diff_px": e["silhouette_diff_vs_29r01_px"],
                           "132_sigma12_max": round(lf["132_sigma12_max"], 4), "132_base": round(bl["132_sigma12_max"], 4),
                           "72_sigma24_p95": round(lf["72_sigma24_p95"], 4), "72_base": round(bl["72_sigma24_p95"], 4),
                           "sym_verdict_changes_vs_29r01": {k: [b["verdicts_sym"].get(k), now["verdicts_sym"].get(k)] for k in now["verdicts_sym"] if b["verdicts_sym"].get(k) != now["verdicts_sym"].get(k)}}
        out["sets"][s] = now
    return out


def trough(pal):
    """谷の読み（記録）：座席の 3 視点と原画視点の near の海の画素の色区の割合と、near の海の中の色の境の画素（4 近傍で色区が変わる）の割合。"""
    out = {}
    for v in ("seat", "seat_low", "seat_toward_wave", "painting"):
        for t in (8.0, 10.0, 12.0):
            cp = os.path.join(U, "chart", "ds36_colour_%s_t%05.2fs.png" % (v, t))
            if not os.path.exists(cp):
                continue
            img = imread(cp); reg = imread(os.path.join(U, "chart", "ds36_region_%s_t%05.2fs.png" % (v, t)))
            m = np.all(reg == np.array(REGC["sea_near"], np.uint8), -1)
            k = classify(img, pal)
            n = int(m.sum())
            if n == 0:
                continue
            edge = np.zeros_like(m)
            edge[:, 1:] |= (k[:, 1:] != k[:, :-1]) & (k[:, 1:] >= 0) & (k[:, :-1] >= 0)
            edge[1:, :] |= (k[1:, :] != k[:-1, :]) & (k[1:, :] >= 0) & (k[:-1, :] >= 0)
            out["%s_t%.1f" % (v, t)] = {"near_px": n, **{nm: round(float((k[m] == i).sum()) / n, 4) for i, nm in enumerate(e["name"] for e in pal)},
                                        "class_edge_px_per_1000": round(1000.0 * float((edge & m).sum()) / n, 2)}
    return out


def figures(pal, acc, regs, claw_px, rend, lab):
    os.makedirs(FIG, exist_ok=True)
    fs = []
    # 1) 前後（設計34 → 設計36）：原画視点 t*、座席から波の方向 t 10 s、座席の低い視点 t 12 s
    pairs = [(os.path.join(D34, "stills", "ds34_all_painting_t12.00s.png"), os.path.join(U, "chart", "ds36_colour_painting_t12.00s.png"), "painting t 12 s (t*)"),
             (os.path.join(D34, "stills", "ds34_all_seat_toward_wave_t10.00s.png"), os.path.join(U, "chart", "ds36_colour_seat_toward_wave_t10.00s.png"), "seat_toward_wave t 10 s"),
             (os.path.join(D34, "stills", "ds34_all_seat_low_t12.00s.png"), os.path.join(U, "chart", "ds36_colour_seat_low_t12.00s.png"), "seat_low t 12 s"),
             (os.path.join(D34, "stills", "ds34_all_painting_t08.00s.png"), os.path.join(U, "chart", "ds36_colour_painting_t08.00s.png"), "painting t 8 s")]
    rows = []
    for a, b, tt in pairs:
        if not (os.path.exists(a) and os.path.exists(b)):
            continue
        ia = cv2.resize(imread(a), (960, 540), interpolation=cv2.INTER_AREA); ib = cv2.resize(imread(b), (960, 540), interpolation=cv2.INTER_AREA)
        for im, lbl in ((ia, "DS34 (before) " + tt), (ib, "DS36 palette " + tt)):
            cv2.rectangle(im, (0, 0), (520, 30), (255, 255, 255), -1)
            cv2.putText(im, lbl, (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 1, cv2.LINE_AA)
        rows.append(np.hstack([ia, ib]))
    if rows:
        p = os.path.join(FIG, "fig_ds36_before_after.png"); imwrite(p, np.vstack(rows)); fs.append(p)
    # 2) 爪の影の色：左肩〜唇の切り抜き（原画の色区 ／ 描画の色区（爪あり） ／ 爪の画素と一致）
    x0, y0, x1, y1 = 560, 120, 1200, 520
    col = {0: (248, 243, 223), 1: (198, 215, 203), 2: (44, 105, 147), 3: (35, 64, 97)}
    def paint(k):
        o = np.full(k.shape + (3,), 255, np.uint8)
        for v, c in col.items():
            o[k == v] = c
        return o
    lt = lab.astype(np.int16) - 1
    lt[(lt < 0) | (lt > 3)] = -1
    A = paint(lt)[y0:y1, x0:x1]; Bm = paint(rend)[y0:y1, x0:x1]
    C = np.full(A.shape, 255, np.uint8)
    cm = claw_px[y0:y1, x0:x1]
    agree = (rend == lt)[y0:y1, x0:x1]
    sh = (lt >= 1)[y0:y1, x0:x1]
    C[cm & agree & sh] = (40, 160, 60); C[cm & ~agree & sh] = (220, 40, 40); C[cm & ~sh] = (200, 200, 200)
    big = np.hstack([A, Bm, C])
    big = cv2.resize(big, (big.shape[1] * 3 // 2, big.shape[0] * 3 // 2), interpolation=cv2.INTER_NEAREST)
    for i, lbl in enumerate(["painting labels", "render class IDs (claws on, t*)", "claw px: green shadow agrees / red differs / grey white"]):
        cv2.putText(big, lbl, (8 + i * big.shape[1] // 3, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    p = os.path.join(FIG, "fig_ds36_claw_shadow_tstar.png"); imwrite(p, big); fs.append(p)
    # 3) 色票（調色板の見本）
    sw = np.full((140, 5 * 200, 3), 255, np.uint8)
    for i, e in enumerate(pal):
        sw[10:100, i * 200 + 10:i * 200 + 190] = e["srgb8"]
        cv2.putText(sw, "%s %s L*%.1f" % (e["name"], e["hex"], e["value_L"]), (i * 200 + 8, 125), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    p = os.path.join(FIG, "fig_ds36_palette_swatches.png"); imwrite(p, sw); fs.append(p)
    # 4) 形成の全区間（原画視点と座席の低い視点、t 4〜12 s）
    rows = []
    for v in ("painting", "seat_low", "seat_toward_wave"):
        ims = []
        for t in (4.0, 6.0, 8.0, 10.0, 12.0):
            pth = os.path.join(U, "chart", "ds36_colour_%s_t%05.2fs.png" % (v, t))
            if os.path.exists(pth):
                im = cv2.resize(imread(pth), (384, 216), interpolation=cv2.INTER_AREA)
                cv2.putText(im, "%s t%.0f" % (v, t), (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                ims.append(im)
        if ims:
            rows.append(np.hstack(ims))
    if rows:
        p = os.path.join(FIG, "fig_ds36_formation_frames.png"); imwrite(p, np.vstack(rows)); fs.append(p)
    return fs


def main():
    rep = load(os.path.join(U, "ds36_render_report.json"))
    cp = load(os.path.join(PREP, "ds36_claw_palette.json"))
    prep = load(os.path.join(PREP, "ds36_palette_prep.json"))
    inv = load(INVENTORY)
    pal = palette_table(rep)
    rows = chart(rep, pal)
    acc, regs, claw_px, rend, lab = claw_acceptance(rep, cp, inv)
    res = {"schema": "GreatWave.DS36.palette_metrics/1", "palette": pal,
           "palette_note_ja": "主役波の材質の値（DS27 NPR White の _White・_Mizuiro・_AiMid・_AiDark）。海のシートはレンダラーの MaterialPropertyBlock で同じ値、爪は DS36 Claw Palette に同じ値、"
                              "飛沫は白（設計31 の JSON の (251,246,227) から調色板の白へ）。線は主役波の外殻線の材質の _LineColor（線は設計38）。",
           "spray_colour": rep["sprayColour"], "sheets": rep["sheets"],
           "claw_shadow_acceptance": {k: v for k, v in acc.items() if k != "per_claw"},
           "claw_colours_by_view": seat_claw_colours(pal),
           "root_white_200": root_white(inv, rep["clawIds"], rend, lab),
           "trough_record": trough(pal),
           "sea_prep": {k: {kk: vv for kk, vv in v.items() if kk not in ("uv3_file",)} for k, v in prep["sea"].items() if k in ("near", "far")},
           "sea_params": prep["params"],
           "face_check": rep.get("face"),
           "regression": regress_summary(),
           "colour_chart_rows": len(rows)}
    res["root_white_200"]["per_claw"] = res["root_white_200"]["per_claw"][:0]
    with open(os.path.join(B36, "ds36_claw_shadow_per_claw.json"), "w", encoding="utf-8") as f:
        json.dump(acc["per_claw"], f, ensure_ascii=False, indent=1)
    res["figures"] = figures(pal, acc, regs, claw_px, rend, lab)
    with open(os.path.join(B36, "ds36_colour_chart.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    res["colour_chart_csv"] = os.path.join(B36, "ds36_colour_chart.csv")
    res["inputs_sha256"] = {os.path.relpath(p, REPO): sha256(p) for p in (LABELS, REGIONS, INVENTORY, os.path.join(PREP, "ds36_claw_palette.json"),
                                                                           os.path.join(U, "ds36_render_report.json"))}
    res["code_sha256"] = sha256(os.path.abspath(__file__))
    with open(os.path.join(B36, "ds36_palette_metrics.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=float)
    # 読みやすい表（t* の原画視点と座席 v1、t 10 s の座席から波の方向）
    lines = ["設計36 第「調色板」部：色票の表（値は ds36_palette_metrics.json・ds36_colour_chart.csv が正）", "",
             "調色板：" + "、".join("%s %s (%d,%d,%d) L*%.1f" % (e["name"], e["hex"], *e["srgb8"], e["value_L"]) for e in pal), "",
             "視点\tt\t領域\t画面の割合%\t白%\t淡い水色%\t藍中%\t藍濃%\t線%\t調色板の外%\t平均 L*"]
    for r in rows:
        if (r["view"], r["t"]) in (("painting", 12.0), ("seat", 12.0), ("seat_low", 12.0), ("seat_toward_wave", 10.0), ("painting", 8.0)):
            lines.append("%s\t%.1f\t%s\t%.2f\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f\t%.1f" % (r["view"], r["t"], r["region"], r["frame_share_pct"], r["share_white_pct"], r["share_mizuiro_pct"],
                                                                                        r["share_ai_mid_pct"], r["share_ai_dark_pct"], r["share_line_pct"], r["share_off_palette_pct"], r["mean_L"]))
    with open(os.path.join(B36, "ds36_colour_chart_ja.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"claw": res["claw_shadow_acceptance"], "root": {k: v for k, v in res["root_white_200"].items() if k != "per_claw"},
                      "reference": (res["regression"] or {}).get("reference"), "regression": {s: {k: v for k, v in e.items() if k in ("265_dE00", "266_ai_mid_bands_sym", "266_mizuiro_bands_sym", "267_white_bands_sym", "267_white_bands_strict", "no_regression_265_266_267_vs_29r01", "plan_2_0")}
                                     for s, e in (res["regression"] or {}).get("sets", {}).items()}}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
