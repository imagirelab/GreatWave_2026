# -*- coding: utf-8 -*-
"""番号23 評価器 v0。1920×1080 の描画 PNG を原画基準（targets/）と比べる。

使い方（リポジトリ根で）:
    評価:     py -3.10 Tools/PaintingTruth/evaluate.py --render R.png [--ids ID.png --idmap idmap.json] --out-dir DIR
    自己テスト: py -3.10 Tools/PaintingTruth/evaluate.py --selftest --out-dir DIR

出力:
    DIR/metrics.json        backlog 項目番号 → 値 → pass / fail / record-only
    DIR/<name>_overlay.png  偏差の重ね図（緑 ≤2 px、黄 ≤4 px、赤 >4 px）
    DIR/selftest.json       （--selftest のとき）較正門の自己テスト結果

輪郭は t* の 1 枚だけを判定する前提。色区は真値マスクを 3 px 収縮した内側の中央値で比べる。
ID 画像は各領域を単色で塗った PNG（1920×1080 または 3840×2160）。idmap.json は
{"classes": {"sky": [r,g,b], "boat_left": [...], "boat_mid": [...], "boat_fg": [...]}} の形。
ID 画像がなければ、原画と同じ色規則（extract の空抽出）で描画から領域を取る（色モード）。
"""
import argparse
import datetime
import json
import math
import os
import platform
import sys

import cv2
import numpy as np

import truthlib as T

CONTOUR_ITEMS = [
    # id, backlog, family, judged
    ("78", [78], "sky", True),
    ("130", [130], "sky", True),
    ("131", [131], "sky", True),
    ("132", [132], "sky", True),
    ("72", [72], "sky", True),
    ("71", [71], "sky", True),
    ("fuji_ridge", [74, 161], "sky", False),
    ("sky_dark", [76], "sky_dark", True),
    ("sky_transition", [213], "sky_dark", True),
    ("boat_fg", [75], "boat_fg", False),
    ("boat_left", [157], "boat_left", False),
    ("boat_mid", [159], "boat_mid", False),
]
COLOR_ITEMS = [
    # palette 名, backlog, judged
    ("sky_bottom", [76], True),
    ("sky_top", [212], True),
    ("mizuiro", [265], False),
    ("ai_mid", [265], False),
    ("fuji_snow", [162], False),
    ("fuji_slope", [162], False),
    ("white", [], False),
    ("ai_dark", [], False),
    ("boat_ochre", [213], False),
]
MAIN_SEGS = ["78", "130", "131", "132", "72"]
# 較正門の結果（番号23 第2部の gate_part2.py が書く）。全項目合格で、かつ門の後に真値が変わっていなければ、評価の判定を暫定扱いしない。
GATE_REL = "Docs/Evidence/ArtFirst/23/23_gate.json"
MANIFEST_PATH = os.path.join(T.TARGET_DIR, "truth_manifest.json")
# 真値の完全性の記録（記録のみ）。claw_zone の中で「白い水」「水色（淡い青灰の爪体など）」とみなす色（平滑 L*・a*・b*）の規則。
# 長さ・面積は旧参照 px（1200×807）の値で書き、reference.px_per_legacy_ref_px で高解像度 px に換算する（v0.2）。
WHITE_RULE = {"blur_sigma_legacy_ref_px": 1.0, "L_min": 95.0, "a_max": -0.5, "b_max": 9.0, "min_component_legacy_ref_px2": 20}
MIZUIRO_RULE = {"blur_sigma_legacy_ref_px": 1.0, "L_min": 70.0, "L_below": 95.0, "a_max": -4.5, "b_max": 8.0, "min_component_legacy_ref_px2": 20,
                "note_ja": "修正2回目で追加。調色板の水色（L* 83.0、a* −8.7、b* 3.9）の周り。外の空（a* ≈ 0、b* ≈ 12〜20）と白は含まない。"
                           "高解像度の claw_zone で 67,605 px が当たり、真値の空の中は 12 px だった（試算）。"}


def gate_status():
    """較正門の状態。門の全項目合格に加え、門を回した時の真値（truth_manifest.json と painting_truth.json）が今と同じことを求める。"""
    p = T.repo_abs(GATE_REL)
    if not os.path.exists(p):
        return {"path": GATE_REL, "exists": False, "all_pass": False, "gate_all_pass": False,
                "refused_ja": "較正門の記録がない。"}
    G = T.load_json(p)
    now = {"truth_manifest_sha256": T.sha256_file(MANIFEST_PATH), "painting_truth_sha256": T.sha256_file(T.SPEC_PATH)}
    at_gate = {k: G.get(k) for k in now}
    same = all(at_gate[k] is not None and at_gate[k] == now[k] for k in now)
    st = {"path": GATE_REL, "exists": True, "sha256": T.sha256_file(p), "gate_all_pass": bool(G.get("all_pass")),
          "gate_complete": bool(G.get("gate_complete")), "truth_at_gate": at_gate, "truth_now": now,
          "truth_unchanged_since_gate": bool(same), "all_pass": bool(G.get("all_pass")) and bool(same)}
    if not same:
        st["refused_ja"] = ("較正門を回した後に真値（targets/truth_manifest.json または painting_truth.json）が変わった"
                            "（または門に真値の SHA-256 がない）。較正門を回し直すまで判定は暫定。")
    elif not G.get("all_pass"):
        st["refused_ja"] = "較正門に不合格の項目がある。"
    return st


# ---------------------------------------------------------------- 真値
class Truth:
    def __init__(self):
        self.spec = T.load_spec()
        self.fmap = T.FrameMap(self.spec)
        td = T.TARGET_DIR
        self.regions = T.load_json(os.path.join(td, "regions.json"))
        self.palette = T.load_json(os.path.join(td, "palette.json"))
        self.outline = {v: T.load_json(os.path.join(td, "main_wave_outline_%s.json" % v)) for v in ("envelope", "claws")}
        m = self.regions["masks"]
        self.cov = {
            "sky_envelope": T.load_cov_png(os.path.join(td, m["sky_envelope"])),
            "sky_claws": T.load_cov_png(os.path.join(td, m["sky_claws"])),
            "sky_dark": T.load_cov_png(os.path.join(td, m["sky_dark"])),
            "boat_left": T.load_cov_png(os.path.join(td, m["boat_left"])),
            "boat_mid": T.load_cov_png(os.path.join(td, m["boat_mid"])),
            "boat_fg": T.load_cov_png(os.path.join(td, m["boat_fg"])),
        }
        data = np.fromfile(os.path.join(td, m["palette_regions"]), np.uint8)
        self.label_img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
        self.line_width_profile = T.load_json(os.path.join(td, "line_width_profile.json"))
        self.L_mid = float(self.regions["L_mid"])
        self.ref_rgb, self.disp_rgb = T.painting_display(self.spec, self.fmap)
        self.lab_disp = T.srgb8_to_lab(self.disp_rgb)
        self._families()

    def _families(self):
        fm = self.fmap
        P = self.regions["polygons_display"]
        self.fam = {}
        for ver in ("envelope", "claws"):
            pts = T.boundary_points(self.cov["sky_" + ver], self.spec, fm)
            lab = np.array(["other"] * len(pts), dtype=object)
            segpts, segid = [], []
            for s in self.outline[ver]["segments"]:
                Q = T.resample_polyline(np.array(s["points_display"]), 0.25)
                segpts.append(Q)
                segid += [s["id"]] * len(Q)
            segpts = np.vstack(segpts)
            segid = np.array(segid, dtype=object)
            d, i = T.nearest(pts, segpts)
            near = d <= 1.0
            lab[near] = segid[i[near]]
            fz = T.point_in_poly(pts, P["fuji_zone"], 0.0)
            lab[(lab == "other") & fz] = "fuji_ridge"
            sel71 = T.point_in_poly(pts, P["region71_clip"], 1.0)
            self.fam["sky_" + ver] = {"pts": pts, "label": lab, "sel": {**{k: lab == k for k in MAIN_SEGS + ["fuji_ridge"]}, "71": sel71}}
        dk = T.boundary_points(self.cov["sky_dark"], self.spec, fm)
        d, _ = T.nearest(dk, self.fam["sky_claws"]["pts"])
        self.fam["sky_dark"] = {"pts": dk, "sel": {"sky_dark": np.ones(len(dk), bool), "sky_transition": d > 1.0}}
        for b in ("boat_left", "boat_mid", "boat_fg"):
            bp = T.boundary_points(self.cov[b], self.spec, fm)
            self.fam[b] = {"pts": bp, "sel": {b: np.ones(len(bp), bool)}}


# ---------------------------------------------------------------- 描画側の領域
def render_regions_colour(truth, rgb):
    """色モード: 描画を参照解像度へ戻し、原画と同じ空抽出・黄土抽出をかける。"""
    fm, ex = truth.fmap, truth.spec["extraction"]
    ref = fm.warp_to_ref(rgb, cv2.INTER_LINEAR)
    lab_ref = T.srgb8_to_lab(ref)
    sky = T.segment_sky(lab_ref, ex["sky"], ())
    ochre = T.ochre_mask(lab_ref, sky, ex["ochre"])
    polys = truth.regions["polygons_ref"]
    out = {"sky": T.ref_mask_to_cov(sky, fm)}
    for b in ("boat_left", "boat_mid", "boat_fg"):
        out[b] = T.ref_mask_to_cov(T.boat_mask(ochre, polys[b + "_roi"]), fm)
    return out


def render_regions_ids(truth, ids_rgb, idmap):
    H, W = truth.fmap.H, truth.fmap.W
    if ids_rgb.shape[:2] == (2 * H, 2 * W):
        f = 2
    elif ids_rgb.shape[:2] == (H, W):
        f = 1
    else:
        raise ValueError("ID 画像は 1920×1080 か 3840×2160: %s" % (ids_rgb.shape,))
    out = {}
    for name in ("sky", "boat_left", "boat_mid", "boat_fg"):
        c = idmap["classes"].get(name)
        if c is None:
            out[name] = np.zeros((H, W))
            continue
        m = np.all(ids_rgb == np.array(c, np.uint8)[None, None, :], axis=-1).astype(np.float64)
        out[name] = m.reshape(H, f, W, f).mean((1, 3)) if f == 2 else m
    return out


# ---------------------------------------------------------------- 評価
def evaluate_core(truth, rgb, reg, versions=("envelope", "claws"), judged_version="envelope", contour_judged=True):
    """rgb: 1920×1080 RGB。reg: {'sky' or 'sky_<ver>', 'boat_*'} の被覆率。"""
    spec, fm = truth.spec, truth.fmap
    lab = T.srgb8_to_lab(rgb)
    thr = float(spec["scoring"]["contour"]["pass_max_px"])
    cthr = float(spec["scoring"]["color"]["pass_max"])
    er = int(spec["scoring"]["color"]["erosion_px"])
    sky_claws_r = reg.get("sky_claws", reg.get("sky"))
    rpts = {}
    for ver in versions:
        rpts["sky_" + ver] = T.boundary_points(reg.get("sky_" + ver, reg.get("sky")), spec, fm)
    dark_r = T.sky_dark_mask(lab, sky_claws_r, truth.L_mid, spec["extraction"]["sky_dark"], fm)
    rpts["sky_dark"] = T.boundary_points(dark_r, spec, fm)
    for b in ("boat_left", "boat_mid", "boat_fg"):
        rpts[b] = T.boundary_points(reg[b], spec, fm)

    items = {}
    detail = {}
    for ver in versions:
        judged_ver = ver == judged_version
        for tid, backlog, family, judged in CONTOUR_ITEMS:
            fam_key = "sky_" + ver if family == "sky" else family
            if family != "sky" and ver != versions[0]:
                continue
            if tid == "fuji_ridge" and ver != "claws" and "claws" in versions:
                continue
            F = truth.fam[fam_key]
            res, assign, worst = T.labelled_hausdorff(F["pts"], F["sel"][tid], rpts[fam_key])
            required = judged and (judged_ver or family != "sky")
            is_judged = contour_judged and required
            versioned = family == "sky" and tid != "fuji_ridge"
            v = res.get("max_px")
            verdict = "not-judged（色モード）" if (required and not contour_judged) else "record-only"
            if is_judged and v is not None:
                verdict = "pass" if v <= thr else "fail"
            entry = {"target": tid, "family": fam_key, "metric": "labelled Hausdorff (display px)",
                     "value_max_px": _r(v), "p95_px": _r(res.get("p95_px")), "p50_px": _r(res.get("p50_px")),
                     "max_truth_to_render": _r(res.get("max_truth_to_render")), "max_render_to_truth": _r(res.get("max_render_to_truth")),
                     "n_truth": res.get("n_truth"), "n_render_assigned": res.get("n_render_assigned"),
                     "threshold_px": thr, "verdict": verdict, "version": ver if family == "sky" else None}
            if "error" in res:
                entry["error"] = res["error"]
            if worst is not None:
                entry["worst_display_xy"] = [round(float(worst[0]), 2), round(float(worst[1]), 2)]
            if tid == "71":
                clip = T.poly_mask((fm.H, fm.W), truth.regions["polygons_display"]["region71_clip"])
                a = (truth.cov["sky_" + ver] > 0.5) & clip
                b = (reg.get("sky_" + ver, reg.get("sky")) > 0.5) & clip
                entry["iou"] = _r(float((a & b).sum()) / max(1.0, float((a | b).sum())), 5)
            for bl in backlog:
                key = "%s_%s" % (bl, ver) if (versioned and not judged_ver) else str(bl)
                items.setdefault(key, {"backlog": bl, "measures": []})["measures"].append(entry)
            detail[(fam_key, tid)] = (assign, entry)

    colors = {}
    for name, backlog, judged in COLOR_ITEMS:
        p = truth.palette["palette"][name]
        m = T.erode(truth.label_img == p["label_value"], er)
        med = T.median_lab(lab, m)
        if med is None:
            dE = None
        else:
            dE = float(T.ciede2000(med, np.array(p["lab"])))
        verdict = "record-only"
        if judged and dE is not None:
            verdict = "pass" if dE <= cthr else "fail"
        entry = {"target": name, "metric": "CIEDE2000 of region median (3 px erosion)", "value": _r(dE),
                 "render_lab": None if med is None else [round(float(x), 3) for x in med], "truth_lab": p["lab"],
                 "pixels": int(m.sum()), "threshold": cthr, "verdict": verdict}
        colors[name] = entry
        for bl in backlog:
            items.setdefault(str(bl), {"backlog": bl, "measures": []})["measures"].append(entry)

    lw = line_width(truth, lab, reg.get("sky_envelope", reg.get("sky")))
    items.setdefault("line_width", {"backlog": None, "measures": []})["measures"].append(lw)
    for k, it in items.items():
        vs = [m.get("verdict") for m in it["measures"]]
        if "fail" in vs:
            it["verdict"] = "fail"
        elif any(str(v).startswith("not-judged") for v in vs):
            it["verdict"] = "incomplete"
        elif "pass" in vs:
            it["verdict"] = "pass"
        else:
            it["verdict"] = "record-only"
    return {"items": items, "colors": colors}, detail, rpts


def _r(v, n=4):
    if v is None:
        return None
    if isinstance(v, float) and (math.isinf(v) or math.isnan(v)):
        return str(v)
    return round(float(v), n)


def line_width(truth, lab, sky_cov):
    """外周（78/130/131、claw_zone の外で包絡版と爪入り版が同じ所）に沿った藍の輪郭線の幅（記録のみ）。

    修正2回目で、真値の線幅プロファイル（targets/line_width_profile.json、高解像度の半深さ全幅）と同じ点・同じ測り方
    （truthlib.line_width_profile、表示 px）に揃えた。法線は描画の空の被覆率から水側へ向ける。区間の中央値を真値の区間中央値と比べる。
    """
    L = lab[..., 0].astype(np.float32)
    prof = truth.line_width_profile
    p = prof["params_display_px"]
    segs = {}
    allw = []
    for s in prof["segments"]:
        if s["id"] not in ("78", "130", "131"):
            continue
        P = np.array(s["points_display"])
        nrm = T.outline_normals(P, sky_cov, 2.0)
        r = T.line_width_profile(L, P, nrm, p)
        w = r["width"][np.isfinite(r["width"])]
        tw = np.array([v for v in s["width_ref_px"] if v is not None]) * truth.fmap.s
        tm = float(np.median(tw)) if len(tw) else None
        rm = float(np.median(w)) if len(w) else None
        segs[s["id"]] = {"n_points": int(len(P)), "n_measured": int(len(w)), "median_display_px": _r(rm),
                         "truth_median_display_px": _r(tm), "ratio_minus_1": _r(rm / tm - 1.0) if (rm and tm) else None}
        allw.append(w)
    w = np.concatenate(allw) if allw else np.zeros(0)
    return {"target": "outline_line_width", "metric": "藍の輪郭線の半深さ全幅（表示 px、真値の線幅プロファイルと同じ点・同じ測り方）",
            "median_display_px": _r(float(np.median(w))) if len(w) else None,
            "p10_display_px": _r(float(np.percentile(w, 10))) if len(w) else None,
            "p90_display_px": _r(float(np.percentile(w, 90))) if len(w) else None,
            "median_ref_px": _r(float(np.median(w)) / truth.fmap.s) if len(w) else None,
            "n_samples": int(len(w)), "segments": segs, "tolerance": truth.spec["scoring"]["line_width"]["tolerance"],
            "verdict": "record-only"}


# ---------------------------------------------------------------- 重ね図
def overlay_png(truth, rgb, detail, rpts, path, title, versions=("envelope",)):
    img = (rgb.astype(np.float32) * 0.45).astype(np.uint8)
    fm = truth.fmap
    img[:, :fm.x0] //= 8
    img[:, fm.x1 + 1:] //= 8
    for (fam_key, tid), (assign, entry) in detail.items():
        if entry.get("version") not in (None,) + tuple(versions):
            continue
        F = truth.fam[fam_key]
        tp = F["pts"][F["sel"][tid]]
        for q in tp[::2]:
            img[int(round(q[1])) % fm.H, int(round(q[0])) % fm.W] = (0, 255, 255)
        if assign is None:
            continue
        d_all, assigned = assign
        rp = rpts[fam_key][assigned]
        dd = d_all[assigned]
        col = np.where(dd[:, None] <= 2.0, np.array([[60, 230, 60]]),
                       np.where(dd[:, None] <= 4.0, np.array([[255, 220, 0]]), np.array([[255, 40, 40]])))
        xi = np.clip(np.round(rp[:, 0]).astype(int), 0, fm.W - 1)
        yi = np.clip(np.round(rp[:, 1]).astype(int), 0, fm.H - 1)
        img[yi, xi] = col
        w = entry.get("worst_display_xy")
        if w is not None and entry.get("value_max_px") not in (None,):
            c = (255, 60, 60) if entry["verdict"] == "fail" else (255, 255, 255)
            cv2.circle(img, (int(w[0]), int(w[1])), 9, c, 1, cv2.LINE_AA)
            txt = "%s %.2f" % (tid, entry["value_max_px"]) if isinstance(entry["value_max_px"], float) else tid
            cv2.putText(img, txt, (int(w[0]) + 10, int(w[1]) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(img, txt, (int(w[0]) + 10, int(w[1]) - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 1, cv2.LINE_AA)
    cv2.putText(img, title, (170, 1066), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(img, "cyan=truth  green<=2px  yellow<=4px  red>4px (render boundary, display px)", (170, 1040),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    T.save_png_reserved(path, img, [(0, 255, 255), (60, 230, 60), (255, 220, 0), (255, 40, 40), (255, 60, 60),
                                    (255, 255, 255), (0, 0, 0)])


# ---------------------------------------------------------------- 自己テスト
def shift_img(a, dx, dy):
    M = np.array([[1.0, 0.0, dx], [0.0, 1.0, dy]])
    return cv2.warpAffine(a, M, (a.shape[1], a.shape[0]), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def truth_regs(truth, f=lambda a: a):
    return {"sky_envelope": f(truth.cov["sky_envelope"]), "sky_claws": f(truth.cov["sky_claws"]),
            "boat_left": f(truth.cov["boat_left"]), "boat_mid": f(truth.cov["boat_mid"]), "boat_fg": f(truth.cov["boat_fg"])}


def union_max(metrics, ids, ver):
    vals = []
    for k, it in metrics["items"].items():
        for m in it["measures"]:
            if m.get("target") in ids and m.get("version") == ver and isinstance(m.get("value_max_px"), float):
                vals.append(m["value_max_px"])
    return max(vals) if vals else None


def union_hausdorff(truth, ver, rp, ids):
    """主浪 5 区間をまとめた集合の Hausdorff。"""
    F = truth.fam["sky_" + ver]
    sel = np.zeros(len(F["pts"]), bool)
    for i in ids:
        sel |= F["sel"][i]
    res, _, _ = T.labelled_hausdorff(F["pts"], sel, rp)
    return res


def selftest(truth, out_dir):
    spec, fm = truth.spec, truth.fmap
    R = {"schema": "GreatWave.PaintingTruth.selftest/1", "generated_utc": _now(),
         "tools": _tools(), "truth_manifest_sha256": T.sha256_file(os.path.join(T.TARGET_DIR, "truth_manifest.json"))}
    # 1) Sharma 2005
    S = np.array(T.SHARMA2005)
    d = T.ciede2000(S[:, 0:3], S[:, 3:6])
    d2 = T.ciede2000(S[:, 3:6], S[:, 0:3])
    err = np.abs(d - S[:, 6])
    R["sharma2005_ciede2000"] = {
        "n_pairs": int(len(S)), "max_abs_error": float(err.max()), "max_abs_error_swapped": float(np.abs(d2 - S[:, 6]).max()),
        "threshold": 1e-4, "pass": bool(err.max() < 1e-4 and np.abs(d2 - S[:, 6]).max() < 1e-4),
        "pairs": [{"i": i + 1, "expected": float(S[i, 6]), "computed": round(float(d[i]), 6)} for i in range(len(S))],
        "source_ja": "Sharma, Wu, Dalal (2005) Color Res. Appl. 30(1) 表1 の 34 組（表の値は小数 4 桁）。",
    }
    # 2) カメラ照合（Unity 記録値との支持的照合。Unity 5 点標識の門は第2部）
    pl = T.load_json(T.repo_abs("Docs/Evidence/M1/12_placement.json"))
    eu = T.cam_euler_deg(spec)
    ue = [pl["comparisonRotation"][k] for k in ("x", "y", "z")]
    x, y, z, vx, vy = T.project_world(spec, [37.0, -0.1 + 2 * 8.0, 420.0])
    fx = pl["fujiApexViewport"]["x"] * fm.W - 0.5
    fy = (1 - pl["fujiApexViewport"]["y"]) * fm.H - 0.5
    rev = T.load_json(T.repo_abs("Docs/Evidence/M1/Revision01/15_revision_layout.json"))
    same_rev = (np.allclose([rev["comparisonCameraPosition"][k] for k in "xyz"], spec["painting_cam"]["position"], atol=1e-5)
                and np.allclose([rev["comparisonCameraTarget"][k] for k in "xyz"], spec["painting_cam"]["target"], atol=1e-5))
    view, proj = T.cam_matrices(spec)
    R["camera_crosscheck"] = {
        "euler_numpy_deg": [round(v, 6) for v in eu], "euler_unity_12_placement": ue,
        "euler_max_diff_deg": float(max(abs(((a - b + 180) % 360) - 180) for a, b in zip(eu, ue))),
        "fuji_apex_world": [37.0, 15.9, 420.0],
        "fuji_apex_world_note_ja": "M1CompositionBuilder.cs 169-170 行の position (37,-0.1,420)・scale 2 と、12_placement の fujiImportedSize 高さ 8 から頂点 = position + 2*(0,8,0) と推定。",
        "fuji_apex_numpy_display_px": [round(x, 4), round(y, 4)], "fuji_apex_unity_display_px": [round(fx, 4), round(fy, 4)],
        "fuji_apex_diff_px": float(math.hypot(x - fx, y - fy)), "fuji_depth_numpy": round(z, 5), "fuji_depth_unity": pl["fujiApexViewport"]["z"],
        "revision01_layout_camera_matches_spec": bool(same_rev),
        "world_to_camera_matrix": np.round(view, 8).tolist(), "projection_matrix": np.round(proj, 8).tolist(),
        "pass": bool(max(abs(((a - b + 180) % 360) - 180) for a, b in zip(eu, ue)) < 1e-3 and math.hypot(x - fx, y - fy) < 0.05 and same_rev),
        "note_ja": "Unity の既存記録との照合で、Unity 上の 5 点標識による ≤0.5 px 較正門（第2部）の代わりにはしない。",
    }
    # 3) 原画と自身（真値マスクを描画側に与える）
    m0, det0, rp0 = evaluate_core(truth, truth.disp_rgb, truth_regs(truth))
    vals = []
    for it in m0["items"].values():
        for m in it["measures"]:
            v = m.get("value_max_px", m.get("value"))
            if isinstance(v, float):
                vals.append(v)
    R["self_zero"] = {"max_over_all_contours_and_colors": float(max(vals)), "n_measures": len(vals),
                      "pass": bool(max(vals) == 0.0), "metrics": m0["items"]}
    overlay_png(truth, truth.disp_rgb, det0, rp0, os.path.join(out_dir, "23_selftest_self_overlay.png"),
                "23 selftest: painting vs itself (truth masks), envelope targets", ("envelope",))
    # 4) 3.0 px 平行移動
    shifts = {}
    for dx, dy in ((3.0, 0.0), (0.0, 3.0), (2.1213203436, 2.1213203436)):
        rgb_s = shift_img(truth.disp_rgb, dx, dy)
        regs = truth_regs(truth, lambda a: shift_img(a, dx, dy))
        ms, dets, rps = evaluate_core(truth, rgb_s, regs)
        key = "dx%.4f_dy%.4f" % (dx, dy)
        shifts[key] = {
            "main_wave_union_envelope": T_round(union_hausdorff(truth, "envelope", rps["sky_envelope"], MAIN_SEGS)),
            "main_wave_union_claws": T_round(union_hausdorff(truth, "claws", rps["sky_claws"], MAIN_SEGS)),
            "per_target_envelope": {t: union_max(ms, [t], "envelope") for t in MAIN_SEGS + ["71"]},
        }
        if (dx, dy) == (3.0, 0.0):
            overlay_png(truth, rgb_s, dets, rps, os.path.join(out_dir, "23_selftest_shift3px_overlay.png"),
                        "23 selftest: painting shifted +3.0 px in x (truth masks shifted), envelope targets", ("envelope",))
    # 合成円（サブピクセル）
    H, W = fm.H, fm.W
    yy, xx = np.mgrid[0:H * 4, 0:W * 4]

    def disk(cx, cy, r):
        m = ((xx + 0.5) / 4 - 0.5 - cx) ** 2 + ((yy + 0.5) / 4 - 0.5 - cy) ** 2 <= r * r
        return m.reshape(H, 4, W, 4).mean((1, 3))
    A = disk(960.3, 540.2, 200.0)
    B = disk(960.3 + 2.1213203436, 540.2 + 2.1213203436, 200.0)
    pa, pb = T.boundary_points(A, spec, fm), T.boundary_points(B, spec, fm)
    rd, _, _ = T.labelled_hausdorff(pa, np.ones(len(pa), bool), pb)
    shifts["synthetic_disk_r200_diag3px_supersampled4x"] = T_round(rd)
    checks = [shifts["dx3.0000_dy0.0000"]["main_wave_union_envelope"]["max_px"],
              shifts["dx0.0000_dy3.0000"]["main_wave_union_envelope"]["max_px"],
              shifts["dx3.0000_dy0.0000"]["main_wave_union_claws"]["max_px"],
              shifts["dx0.0000_dy3.0000"]["main_wave_union_claws"]["max_px"],
              shifts["synthetic_disk_r200_diag3px_supersampled4x"]["max_px"]]
    R["synthetic_shift"] = {"expected_px": 3.0, "tolerance_px": 0.1, "checked": checks,
                            "pass": bool(all(abs(c - 3.0) <= 0.1 for c in checks)), "cases": shifts,
                            "note_ja": "判定は x・y 方向の整数 3 px 移動（主浪 5 区間の和集合、包絡・爪入り）と、4×4 超標本化した円の斜め 3.0 px 移動。原画マスクの斜め移動は記録のみ（区間ごとの値は法線の向きで 3 px 未満になる）。"}
    # 5) 平塗り色区の読み戻し
    flat = np.full((H, W, 3), 128, np.uint8)
    for name, p in truth.palette["palette"].items():
        flat[truth.label_img == p["label_value"]] = p["srgb8"]
    mf, _, _ = evaluate_core(truth, flat, truth_regs(truth), versions=("envelope",))
    fd = {k: v["value"] for k, v in mf["colors"].items()}
    R["flat_patch"] = {"deltaE00": fd, "threshold": 0.5, "pass": bool(all(v is not None and v < 0.5 for v in fd.values())),
                       "note_ja": "各色区を調色板の 8bit sRGB で平塗りした合成画像を読み戻した ΔE00（8bit 量子化の誤差のみ）。"}
    # 6) Canny 支持率
    R["canny_support"] = canny_support(truth)
    # 7) 色モードの往復（記録のみ）
    mc, detc, rpc = evaluate_core(truth, truth.disp_rgb, render_regions_colour(truth, truth.disp_rgb))
    R["colour_mode_roundtrip_record"] = {
        "note_ja": "ID 画像なしで原画の表示フレーム画像そのものを色モードで評価した値（表示→参照→表示の再標本化の影響）。記録のみ。",
        "contours": {k: [(m["target"], m.get("version"), m.get("value_max_px"), m.get("p95_px")) for m in it["measures"] if "value_max_px" in m]
                     for k, it in mc["items"].items()}}
    # 8) ID モードの往復（記録のみ）: 真値の包絡版を 3840×2160 の単色 ID 画像にして読み戻す
    idmap = {"classes": {"sky": [200, 220, 255], "boat_left": [255, 0, 0], "boat_mid": [0, 255, 0], "boat_fg": [0, 0, 255]}}
    ids = np.zeros((2 * H, 2 * W, 3), np.uint8)
    for name, key in (("sky", "sky_envelope"), ("boat_left", "boat_left"), ("boat_mid", "boat_mid"), ("boat_fg", "boat_fg")):
        hi = cv2.resize(truth.cov[key], (2 * W, 2 * H), interpolation=cv2.INTER_LINEAR) > 0.5
        ids[hi] = idmap["classes"][name]
    mi, _, _ = evaluate_core(truth, truth.disp_rgb, render_regions_ids(truth, ids, idmap), versions=("envelope",))
    R["id_mode_roundtrip_record"] = {
        "note_ja": "真値の被覆率を 2 倍に拡大・0.5 で二値化した 3840×2160 の ID 画像を、ID モードで読み戻した値。ID 経路の量子化誤差の目安（記録のみ）。",
        "contours": {k: [(m["target"], m.get("value_max_px"), m.get("p95_px")) for m in it["measures"] if "value_max_px" in m]
                     for k, it in mi["items"].items()}}
    # 9) 真値の完全性（記録のみ）
    R["truth_completeness_record"] = truth_completeness(truth)
    R["unity_markers"] = {"status": "not_in_selftest", "note_ja": "Unity の世界標識 5 点と numpy 投影の差 ≤0.5 px、Unity の平塗り色区の読み戻しは第2部の gate_part2.py で測る（23_gate.json）。この自己テスト（Python のみ）では測らない。"}
    R["gate_part1_pass"] = bool(all(R[k]["pass"] for k in ("sharma2005_ciede2000", "camera_crosscheck", "self_zero", "synthetic_shift", "flat_patch", "canny_support")))
    R["gate_complete"] = False
    R["gate_complete_note_ja"] = "自己テストは第1部の項目だけで、これ単独では較正門を閉じない。較正門全体の判定は 23_gate.json（gate_part2.py）。"
    T.save_json(os.path.join(out_dir, "selftest.json"), R)
    write_step23_metrics(truth, R, out_dir)
    return R


def write_step23_metrics(truth, R, out_dir):
    """番号23 第1部の証拠 metrics.json と run.json。"""
    spec = truth.spec
    env_path = os.path.join(T.TARGET_DIR, "main_wave_outline_envelope.json")
    claws_path = os.path.join(T.TARGET_DIR, "main_wave_outline_claws.json")
    view, proj = T.cam_matrices(spec)
    seg_env = {s["id"]: s for s in truth.outline["envelope"]["segments"]}
    ok = lambda b: "pass" if b else "fail"
    items = {
        "def11_reference_crop": {"value": {"path": spec["reference"]["path"], "sha256": spec["reference"]["sha256"],
                                           "size": [spec["reference"]["width"], spec["reference"]["height"]],
                                           "scale": spec["display_frame"]["scale"], "offset_x": spec["display_frame"]["offset_x"],
                                           "scored_columns": spec["display_frame"]["scored_columns"],
                                           "legacy_reference": {k: spec["legacy_reference"][k] for k in ("path", "sha256", "width", "height")},
                                           "shift_from_v0_1_ja": spec["display_frame"]["shift_from_v0_1_ja"]},
                                 "verdict": "fixed",
                                 "note_ja": "定義シート第11行の『原画ファイル・裁切』を固定。修正2回目（v0.2）で利用者が承認した高解像度原画へ移した。裁切は旧原画と同じ（23_registration.json）。"},
        "def11_frame_t_star": {"value": spec["timeline"], "verdict": "fixed（暫定 t*）"},
        "def11_painting_cam_v1": {"value": {k: spec["painting_cam"][k] for k in ("position", "target", "up", "vertical_fov_deg", "aspect", "near", "far")},
                                  "verdict": "fixed（Unity 5 点標識の照合は第2部）"},
        "gate_sharma2005_ciede2000": {"value": R["sharma2005_ciede2000"]["max_abs_error"], "threshold": 1e-4,
                                      "verdict": ok(R["sharma2005_ciede2000"]["pass"])},
        "gate_self_zero_px": {"value": R["self_zero"]["max_over_all_contours_and_colors"], "threshold": 0.0,
                              "verdict": ok(R["self_zero"]["pass"])},
        "gate_synthetic_shift_3px": {"value": R["synthetic_shift"]["checked"], "expected": 3.0, "tolerance": 0.1,
                                     "verdict": ok(R["synthetic_shift"]["pass"])},
        "gate_flat_patch_dE00": {"value": max(R["flat_patch"]["deltaE00"].values()), "threshold": 0.5,
                                 "verdict": ok(R["flat_patch"]["pass"])},
        "gate_canny_support": {"value": R["canny_support"]["overall_claws_ratio"], "threshold": 0.95,
                               "distance_threshold": "1 旧参照 px（= %.4f 高解像度 px）" % R["canny_support"]["threshold_ref_px"],
                               "record_le_1_ref_px": R["canny_support"]["overall_claws_ratio_le_1_ref_px_record"],
                               "verdict": ok(R["canny_support"]["pass"])},
        "support_camera_vs_unity_records": {"value": {"euler_max_diff_deg": R["camera_crosscheck"]["euler_max_diff_deg"],
                                                      "fuji_apex_diff_px": R["camera_crosscheck"]["fuji_apex_diff_px"]},
                                            "verdict": ok(R["camera_crosscheck"]["pass"]),
                                            "note_ja": "既存の Unity 記録（12_placement.json）との照合。較正門の Unity 5 点標識の代わりではない。"},
        "gate_unity_markers_0p5px": {"value": None, "verdict": "not-run（第2部）"},
        "baseline_gap_M1_Revision01": {"value": None, "verdict": "not-run（第2部）"},
        "truth_completeness_record": {
            "value": {case: {"water_coverage_of_white": R["truth_completeness_record"][case]["white"]["water_coverage"],
                             "water_coverage_of_mizuiro": R["truth_completeness_record"][case]["mizuiro"]["water_coverage"],
                             "sky_components_area_ref_px_white": R["truth_completeness_record"][case]["white"]["sky_components_area_ref_px"],
                             "sky_components_area_ref_px_mizuiro": R["truth_completeness_record"][case]["mizuiro"]["sky_components_area_ref_px"]}
                      for case in ("truth", "control_without_manual_barriers", "control_without_gap_closing_and_barriers")},
            "verdict": "record-only",
            "note_ja": "較正門は真値の精度（折れ線が原画のエッジに乗るか）を見るが、完全性（水の面を漏れなく含むか）は見ない。完全性はこの記録のみの値で見る。詳細は selftest.json。"},
    }
    for sid in MAIN_SEGS:
        s = seg_env[sid]
        items[sid] = {"backlog": int(sid), "value": {"target": "main_wave_outline_envelope." + sid, "n_points": s["n_points"],
                                                     "length_display_px": s["length_display_px"], "source": s["source"]},
                      "verdict": "record-only（目標を定義。描画の判定はまだ）"}
    for k, v in (("71", "region71_clip ∩ 空"), ("76", "sky_dark（L* < L_mid）"), ("213", "sky_dark の明暗移行線"),
                 ("212", "palette.sky_top"), ("74", "fuji_zone 内の空境界"), ("161", "fuji_zone 内の空境界"),
                 ("75", "boat_fg マスク"), ("157", "boat_left マスク"), ("159", "boat_mid マスク"),
                 ("162", "palette.fuji_snow / fuji_slope"), ("265", "palette.mizuiro / ai_mid（対応は未確定）")):
        items[k] = {"backlog": int(k), "value": {"target": v}, "verdict": "record-only（目標を定義。描画の判定はまだ）"}
    lwp = os.path.join(out_dir, "23_line_width.json")
    if os.path.exists(lwp):
        LW = T.load_json(lwp)
        items["line_width_profile"] = {
            "backlog": [195, 198],
            "value": {"segments": {k: {"median_display_px": v["width_display_px"]["median"], "p10_display_px": v["width_display_px"]["p10"],
                                       "p90_display_px": v["width_display_px"]["p90"], "median_ref_px": v["width_ref_px"]["median"],
                                       "n_measured": v["n_measured_ref"], "n_points": v["n_points"]} for k, v in LW["segments"].items()},
                      "feasibility": {k: v for k, v in LW["feasibility"].items() if k != "criteria_ja"}},
            "verdict": "record-only",
            "note_ja": "高解像度原画の線幅プロファイル（半深さ全幅、targets/line_width_profile.json）。±20% は判定しない（painting_truth.json の "
                       "scoring.line_width.judged = false）。判定の可否は 23_line_width.json の feasibility。"}
    rgp = os.path.join(out_dir, "23_registration.json")
    if os.path.exists(rgp):
        RG = T.load_json(rgp)
        items["registration_hires_to_legacy"] = {
            "value": {"pixel_centre_model": RG["pixel_centre_model"],
                      "ecc_affine_max_corner_displacement_legacy_px": RG["ecc_area_resized_vs_legacy"]["affine"]["max_corner_displacement_legacy_px"],
                      "ecc_affine_correlation": RG["ecc_area_resized_vs_legacy"]["affine"]["correlation"],
                      "sift_similarity_residual_rms_legacy_px": RG["features_sift_ransac"]["similarity"]["residual_rms_legacy_px"],
                      "sift_similarity_rotation_deg": RG["features_sift_ransac"]["similarity"]["rotation_deg"],
                      "display_shift_v0_2_minus_v0_1_px": RG["display_mapping"]["shift_v0_2_minus_v0_1_display_px"]},
            "verdict": "record-only", "note_ja": RG["conclusion_ja"]}
    cam = {k: spec["painting_cam"][k] for k in ("id", "position", "target", "up", "vertical_fov_deg", "aspect", "near", "far")}
    cam.update({"source": [s["path"] for s in spec["painting_cam"]["source"]], "euler_deg": [round(v, 6) for v in T.cam_euler_deg(spec)],
                "world_to_camera_matrix": np.round(view, 8).tolist(), "projection_matrix": np.round(proj, 8).tolist(),
                "display": [spec["display_frame"]["width"], spec["display_frame"]["height"]], "t_star_s": spec["timeline"]["t_star_s"]})
    M = {
        "schema": "GreatWave.Step23.metrics/1",
        "number": "23（第1部：原画基準と評価器 v0、Python のみ）",
        "revision_ja": "修正2回目（2026-09-26）：真値を高解像度原画 Met_JP1847_DP130155.jpg（3859×2594）へ移した（真値 %s）。" % spec["version"],
        "truth_version": spec["version"],
        "generated_utc": _now(),
        "evidence_kind_ja": "文書準備と numpy/OpenCV 計算の結果。Unity 描画・PC ビルド・HMD の結果は含まない。",
        "gate_part1_pass": R["gate_part1_pass"],
        "gate_complete": False,
        "gate_complete_ja": "Unity 5 点標識（≤0.5 px）と M1 基線差の報告は第2部。較正門はまだ閉じていない。",
        "painting_cam_v1": cam,
        "envelope_polyline": {"path": T.repo_rel(env_path), "sha256": T.sha256_file(env_path)},
        "claws_polyline": {"path": T.repo_rel(claws_path), "sha256": T.sha256_file(claws_path)},
        "palette": {k: {"lab": v["lab"], "srgb8": v["srgb8"]} for k, v in truth.palette["palette"].items()},
        "L_mid_sky": truth.L_mid,
        "items": items,
    }
    # 第2部（gate_part2.py）の実行記録は run.json の part2 にある。第1部を作り直しても消さないよう先に読んでおく。
    prev_run = os.path.join(out_dir, "run.json")
    prev_part2 = T.load_json(prev_run).get("part2") if os.path.exists(prev_run) else None
    T.save_json(os.path.join(out_dir, "metrics.json"), M)
    ins = [T.repo_abs(spec["reference"]["path"]), T.repo_abs(spec["legacy_reference"]["path"]), T.SPEC_PATH, T.MANUAL_PATH]
    ins += [os.path.join(T.HERE, f) for f in ("truthlib.py", "register.py", "extract.py", "evaluate.py")]
    ins += [T.repo_abs("Docs/Evidence/M1/12_placement.json"), T.repo_abs("Docs/Evidence/M1/Revision01/15_revision_layout.json")]
    outs = _step23_outputs(out_dir)
    tools = _tools()
    tools.update({"pillow": __import__("PIL").__version__, "os": platform.platform()})
    run = {
        "schema": "GreatWave.Step23.run/1",
        "generated_utc": _now(),
        "commands": ["py -3.10 Tools/PaintingTruth/register.py --evidence Docs/Evidence/ArtFirst/23",
                     "py -3.10 Tools/PaintingTruth/extract.py --evidence Docs/Evidence/ArtFirst/23",
                     "py -3.10 Tools/PaintingTruth/evaluate.py --selftest --out-dir Docs/Evidence/ArtFirst/23"],
        "cwd": "リポジトリ根（G:/Unity/GreatWave_2026_Fresh）",
        "tools": tools,
        "unity": None, "houdini": None, "blender": None,
        "inputs": {T.repo_rel(p): T.sha256_file(p) for p in ins},
        "outputs": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "not_committed": {T.repo_rel(os.path.join(T.BUILD_DIR, "painting_display.png")):
                          T.sha256_file(os.path.join(T.BUILD_DIR, "painting_display.png"))},
        "not_committed_ja": "表示フレームの原画（約 3 MB）は extract.py で決定的に再生成できるため Git に入れない。",
        "reference_ja": "原画は Docs/References/Met_JP1847_DP130155.jpg（2,342,637 bytes、利用者が D3 で承認したダウンロード）。旧原画 Met_JP1847.jpg は履歴として残し、位置合わせと v0.1 との比較にだけ読む。",
    }
    T.save_json(os.path.join(out_dir, "run.json"), run)
    if os.path.exists(os.path.join(out_dir, "23_gate.json")) and prev_part2 is not None:
        merge_step23_part2(out_dir, prev_part2)


def _step23_outputs(out_dir):
    outs = sorted([os.path.join(dp, f) for dp, _, fs in os.walk(T.TARGET_DIR) for f in fs])
    outs += sorted([os.path.join(out_dir, f) for f in os.listdir(out_dir) if f != "run.json"])
    return outs


def merge_step23_part2(out_dir, run_part2):
    """第2部（較正門の Unity 項目と M1 Revision01 基線差）を番号23 の metrics.json と run.json へ入れる。"""
    G = T.load_json(os.path.join(out_dir, "23_gate.json"))
    bp = os.path.join(out_dir, "23_baseline_M1R01_metrics.json")
    B = T.load_json(bp) if os.path.exists(bp) else None
    mp = os.path.join(out_dir, "metrics.json")
    M = T.load_json(mp)
    gi = G["items"]
    ok = lambda b: "pass" if b else "fail"
    M["number"] = "23（第1部：原画基準と評価器 v0／第2部：Unity 較正門と M1 Revision01 基線差）"
    M["evidence_kind_ja"] = ("第1部は文書準備と numpy/OpenCV 計算。第2部は Unity Editor（batchmode）の PC オフスクリーン描画と、"
                             "その PNG の numpy/OpenCV 測定。PC ビルド・HMD 実機の結果は含まない。")
    M["gate_complete"] = bool(G["gate_complete"])
    M["gate_all_pass"] = bool(G["all_pass"])
    M["gate_complete_ja"] = ("較正門の全項目（第1部 5 項目＋第2部 Unity 2 項目）を実施し、%s。" %
                             ("すべて合格した。番号26 の前提を満たす" if G["all_pass"] else "不合格の項目がある。番号26 は開始できない"))
    M["gate_scope_ja"] = G.get("scope_ja")
    M["gate"] = {"path": T.repo_rel(os.path.join(out_dir, "23_gate.json")), "items": {k: v["pass"] for k, v in gi.items()},
                 "all_pass": G["all_pass"], "truth_manifest_sha256": G.get("truth_manifest_sha256"),
                 "painting_truth_sha256": G.get("painting_truth_sha256")}
    it = M["items"]
    um, uf = gi["unity_markers_0p5px"], gi["unity_flat_patch_dE00"]
    it["gate_unity_markers_0p5px"] = {"value": um["value_max_px"], "threshold": um["threshold_px"],
                                      "per_marker_px": {m["id"]: m["diff_px"] for m in um["per_marker"]},
                                      "verdict": ok(um["pass"]), "note_ja": um["note_ja"]}
    it["gate_unity_flat_patch_dE00"] = {"value": uf["value_max"], "threshold": uf["threshold"],
                                        "per_patch": {p["name"]: p["dE00_vs_reference"] for p in uf["per_patch"]},
                                        "verdict": ok(uf["pass"]), "note_ja": uf["note_ja"]}
    if um["pass"]:
        it["def11_painting_cam_v1"]["verdict"] = "fixed（Unity 5 点標識で照合済み）"
    if B is not None:
        summ = {}
        for k, v in B["items"].items():
            ms = [{"target": m.get("target"), "version": m.get("version"),
                   "value_max_px": m.get("value_max_px"), "p95_px": m.get("p95_px"), "value_dE00": m.get("value"),
                   "median_display_px": m.get("median_display_px"), "evaluator_verdict": m.get("verdict")} for m in v["measures"]]
            ms = [{a: b for a, b in m.items() if b is not None} for m in ms]
            summ[k] = {"backlog": v.get("backlog"), "evaluator_verdict": v.get("verdict"), "measures": ms}
            if k in it and isinstance(it[k], dict) and it[k].get("backlog") is not None:
                it[k]["baseline_M1R01"] = {"evaluator_verdict": v.get("verdict"), "measures": ms}
        it["baseline_gap_M1_Revision01"] = {
            "value": summ, "verdict": "record-only（基線。M1 Revision01 は旧い仮置きで、判定の対象ではない）",
            "metrics": T.repo_rel(bp), "provisional": B.get("provisional"),
            "note_ja": "M1 Revision01 の構図シーン（旧い静止の仮形状、未変更）を PaintingCam v1 から描き、評価器 v0 の ID モードで測った差。"
                       "evaluator_verdict は評価器がこの描画に出した判定で、番号23 の合否ではない。"}
    rc = (run_part2 or {}).get("recheck24")
    if rc and rc.get("status") == "done":
        it["recheck_24_tstar"] = {
            "backlog": [78, 130, 131, 132, 72, 71], "value": rc["values"], "truth_version": rc["truth_version"],
            "metrics": T.repo_rel(os.path.join(out_dir, "23_recheck24_metrics.json")),
            "verdict": "record-only（番号24 はプレビュー。合否は採らない）", "note_ja": rc["note_ja"]}
    M["part2"] = {"gate_path": T.repo_rel(os.path.join(out_dir, "23_gate.json")),
                  "baseline_metrics": T.repo_rel(bp) if B is not None else None,
                  "unity": G.get("unity")}
    T.save_json(mp, M)
    rp = os.path.join(out_dir, "run.json")
    run = T.load_json(rp)
    run["part2"] = run_part2
    run["unity"] = G.get("unity")
    run["generated_utc"] = _now()
    run["outputs"] = {T.repo_rel(p): T.sha256_file(p) for p in _step23_outputs(out_dir)}
    T.save_json(rp, run)


def T_round(res):
    return {k: (_r(v) if isinstance(v, float) else v) for k, v in res.items()}


def canny_support(truth):
    """目標折れ線（爪入り版）から Canny エッジまでの距離が 1 旧参照 px 以内の割合（較正門）。

    v0.2 では参照画像が高解像度（3859×2594）になったので、Canny の平滑 σ・閾値と距離のしきい値を、凍結時（旧参照 px）と
    物理的に同じ大きさへ換算する（σ 0.8 → 0.8k、閾値 40/120 → 40/k・120/k、1 旧参照 px → k 高解像度 px、k = px_per_legacy_ref_px）。
    ≤ 1 高解像度 px の割合は記録のみ。
    """
    fm = truth.fmap
    k = float(truth.spec["reference"]["px_per_legacy_ref_px"])
    gray = cv2.cvtColor(truth.ref_rgb, cv2.COLOR_RGB2GRAY)
    sg, lo, hi = 0.8 * k, 40.0 / k, 120.0 / k
    edges = cv2.Canny(cv2.GaussianBlur(gray, (0, 0), sg), lo, hi, L2gradient=True)
    dist = cv2.distanceTransform((edges == 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    zone = T.poly_mask(dist.shape, T.load_manual()["polygons_ref"]["claw_zone"]["points"])
    thr = 1.0 * k
    out = {"canny": {"gaussian_sigma_ref_px": round(sg, 4), "low": round(lo, 4), "high": round(hi, 4), "L2gradient": True,
                     "image": "参照画像（高解像度）の 8bit グレー",
                     "conversion_ja": "凍結時（旧参照 px）の σ 0.8・閾値 40/120 を、k = %.4f で物理的に同じ大きさへ換算した。" % k},
           "threshold_legacy_ref_px": 1.0, "threshold_ref_px": round(thr, 4), "threshold_display_px": round(thr * fm.s, 4),
           "required_ratio": 0.95, "segments": {}}
    allv = []
    for ver in ("claws", "envelope"):
        for s in truth.outline[ver]["segments"]:
            P = np.array(s["points_ref"])
            v = cv2.remap(dist, P[:, 0].astype(np.float32).reshape(1, -1), P[:, 1].astype(np.float32).reshape(1, -1),
                          cv2.INTER_LINEAR).ravel()
            inz = zone[np.clip(np.round(P[:, 1]).astype(int), 0, dist.shape[0] - 1), np.clip(np.round(P[:, 0]).astype(int), 0, dist.shape[1] - 1)]
            if ver == "envelope":
                v = v[~inz]  # 包絡の形態処理部分は原画のエッジに沿わない（設計どおり）
                if len(v) == 0:
                    continue
            out["segments"]["%s_%s" % (ver, s["id"])] = {"ratio": round(float((v <= thr).mean()), 4),
                                                        "ratio_le_1_ref_px_record": round(float((v <= 1.0).mean()), 4),
                                                        "n": int(len(v)), "p95_ref_px": round(float(np.percentile(v, 95)), 3)}
            if ver == "claws":
                allv.append(v)
    allv = np.concatenate(allv)
    out["overall_claws_ratio"] = round(float((allv <= thr).mean()), 4)
    out["overall_claws_ratio_le_1_ref_px_record"] = round(float((allv <= 1.0).mean()), 4)
    out["pass"] = bool(out["overall_claws_ratio"] >= 0.95)
    out["note_ja"] = ("判定は爪入り版（原画の空境界そのもの）の全区間で、しきい値は 1 旧参照 px（= %.4f 高解像度 px = %.4f 表示 px）。"
                      "包絡版は claw_zone 外の点だけ参考記録。ratio_le_1_ref_px_record は ≤ 1 高解像度 px の割合（記録のみ）。" % (thr, thr * fm.s))
    return out


def _colour_mask(lab_s, rule, zone):
    L, a, b = lab_s[..., 0], lab_s[..., 1], lab_s[..., 2]
    m = (L >= rule["L_min"]) & (a <= rule["a_max"]) & (b <= rule["b_max"]) & zone
    if "L_below" in rule:
        m &= L < rule["L_below"]
    return m


def truth_completeness(truth):
    """真値の完全性（記録のみ）：claw_zone の中の「白い水」「水色」の色の画素のうち、爪入り版の真値で水側に入っている割合。

    較正門の Canny 支持率は「真値の折れ線が原画のエッジに乗っているか」（精度）しか見ない。空が藍線の途切れから
    水の面へ流れ込んでも、流れ込んだ先の境界も藍線に沿うので支持率は下がらない（v0 で実際に起きた）。
    そこで、色だけで決めた白い水・水色の画素が空側に入っていないかを数える（水色は修正2回目で追加。v0.1 の波頭上部の爪の
    漏れは淡い水色の爪体に入っており、白だけでは見落とした）。右上の淡い空や爪の鉤の中の小さな白など、色だけでは空と
    区別できない所も数に入るので、合否には使わない。対照として、手動の障壁を外した空と、途切れの閉じも外した空でも同じ値を出す。
    """
    fm, spec = truth.fmap, truth.spec
    k = float(spec["reference"]["px_per_legacy_ref_px"])
    man = T.load_manual()
    lab_ref = T.srgb8_to_lab(truth.ref_rgb).astype(np.float32)
    zone = T.poly_mask(lab_ref.shape[:2], man["polygons_ref"]["claw_zone"]["points"])
    sky_truth = fm.warp_to_ref(truth.cov["sky_claws"].astype(np.float32), cv2.INTER_LINEAR) > 0.5
    polys = man["polygons_ref"]
    fills = [polys["sky_fill_cartouche"]["points"], polys["sky_fill_signature"]["points"]]
    sky_ctrl = T.segment_sky(lab_ref, spec["extraction"]["sky"], fills)
    sky_ctrl0 = T.segment_sky(lab_ref, dict(spec["extraction"]["sky"], barrier_dilate_ref_px=0), fills)
    rules = {"white": WHITE_RULE, "mizuiro": MIZUIRO_RULE}
    masks = {}
    for name, r in rules.items():
        sg = float(r["blur_sigma_legacy_ref_px"]) * k
        Ls = np.stack([cv2.GaussianBlur(lab_ref[..., c], (0, 0), sg) for c in range(3)], -1)
        masks[name] = _colour_mask(Ls, r, zone)
    min_area = int(round(20 * k * k))

    def measure(sky):
        res = {}
        for name, m in masks.items():
            leak = m & sky
            lo = cv2.morphologyEx(leak.astype(np.uint8), cv2.MORPH_OPEN, T.disk(int(round(k))))
            n, _, st, cen = cv2.connectedComponentsWithStats(lo, connectivity=8)
            comps = [{"area_ref_px": int(st[i, 4]), "area_legacy_ref_px2": round(float(st[i, 4]) / (k * k), 1),
                      "bbox_ref_xywh": [int(v) for v in st[i, :4]],
                      "centroid_ref": [round(float(c), 1) for c in cen[i]],
                      "centroid_legacy_ref": [round((float(c) + 0.5) / k - 0.5, 1) for c in cen[i]],
                      "centroid_display": [round(float(c), 1) for c in fm.ref_to_disp(cen[i])]}
                     for i in range(1, n) if st[i, 4] >= min_area]
            comps.sort(key=lambda c: -c["area_ref_px"])
            res[name] = {"px_in_water": int((m & ~sky).sum()), "px_in_sky": int(leak.sum()),
                         "water_coverage": round(float((m & ~sky).sum()) / max(1, int(m.sum())), 4),
                         "sky_components_ge_min": len(comps), "sky_components_area_ref_px": int(sum(c["area_ref_px"] for c in comps)),
                         "largest_sky_components": comps[:8]}
        both = masks["white"] | masks["mizuiro"]
        res["white_or_mizuiro_water_coverage"] = round(float((both & ~sky).sum()) / max(1, int(both.sum())), 4)
        # 以前の記録と同じ名前の値（白だけ）
        res["water_coverage_of_white"] = res["white"]["water_coverage"]
        res["sky_components_area_ref_px"] = res["white"]["sky_components_area_ref_px"] + res["mizuiro"]["sky_components_area_ref_px"]
        return res
    return {
        "verdict": "record-only",
        "zone": "claw_zone（manual_annotations.json）", "frame": "参照画像（高解像度 3859×2594）",
        "rules": {"white": WHITE_RULE, "mizuiro": MIZUIRO_RULE, "px_per_legacy_ref_px": k,
                  "min_component_ref_px": min_area, "opening_radius_ref_px": int(round(k))},
        "px_in_zone": {name: int(m.sum()) for name, m in masks.items()},
        "truth": measure(sky_truth),
        "control_without_manual_barriers": measure(sky_ctrl),
        "control_without_gap_closing_and_barriers": measure(sky_ctrl0),
        "note_ja": "白い水（平滑 L*≥95、a*≤−0.5、b*≤9）と水色（70≤L*<95、a*≤−4.5、b*≤8）の色の画素のうち、真値（爪入り版）で水側にある割合と、"
                   "空側に入った塊（開き 1 旧参照 px 後、20 旧参照 px² 以上）の一覧。塊には右上の淡い空のように色だけでは空と区別できないものが入るので、"
                   "合否には使わない。control_without_manual_barriers は手動の障壁 4 本を外した空、control_without_gap_closing_and_barriers は途切れの閉じも"
                   "外した空（v0 と同じく、主浪の水の面へ流れ込む）。",
    }


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _tools():
    return {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__}


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--render")
    ap.add_argument("--ids")
    ap.add_argument("--idmap")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--name", default="render")
    ap.add_argument("--judged-version", default="envelope", choices=["envelope", "claws"])
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    out_dir = os.path.abspath(a.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    truth = Truth()
    if a.selftest:
        R = selftest(truth, out_dir)
        print("SELFTEST gate_part1_pass=%s" % R["gate_part1_pass"])
        for k in ("sharma2005_ciede2000", "camera_crosscheck", "self_zero", "synthetic_shift", "flat_patch", "canny_support"):
            print(" ", k, R[k]["pass"])
        return 0 if R["gate_part1_pass"] else 1
    if not a.render:
        ap.error("--render か --selftest が必要です")
    rgb = T.imread_rgb(a.render)
    if rgb.shape[:2] != (truth.fmap.H, truth.fmap.W):
        raise SystemExit("描画は 1920×1080 が必要です: %s" % (rgb.shape,))
    if a.ids:
        reg = render_regions_ids(truth, T.imread_rgb(a.ids), T.load_json(a.idmap))
        mode = "ids"
    else:
        reg = render_regions_colour(truth, rgb)
        mode = "colour"
    # 色モードの輪郭は再標本化で細い輪郭線が切れて漏れることがある（自己テストの記録参照）。輪郭の合否は ID 画像でだけ出す。
    m, det, rp = evaluate_core(truth, rgb, reg, judged_version=a.judged_version, contour_judged=(mode == "ids"))
    gate = gate_status()
    # 記録するコマンドは、リポジトリ内の絶対パスをリポジトリ根からの相対パスにする（根の外はそのまま）。
    cmd_args = [T.repo_rel(s) if os.path.isabs(s) else s.replace("\\", "/") for s in sys.argv[1:]]
    out = {
        "schema": "GreatWave.PaintingTruth.metrics/1",
        "generated_utc": _now(),
        "tools": _tools(),
        "command": " ".join(["py -3.10 Tools/PaintingTruth/evaluate.py"] + cmd_args),
        "input": {"render": T.repo_rel(a.render), "render_sha256": T.sha256_file(a.render), "mode": mode,
                  "ids": T.repo_rel(a.ids) if a.ids else None, "ids_sha256": T.sha256_file(a.ids) if a.ids else None},
        "truth": {"version": truth.spec["version"], "manifest_sha256": T.sha256_file(os.path.join(T.TARGET_DIR, "truth_manifest.json")),
                  "judged_version": a.judged_version},
        "t_star_s": truth.spec["timeline"]["t_star_s"],
        "provisional": not gate["all_pass"],
        "gate": gate,
        "provisional_ja": ("番号23 の較正門（%s）は全項目合格で、門の後に真値は変わっていない。判定は暫定扱いしない。"
                           "描画が t* の PaintingCam v1 画像であることは呼び出し側の責任。" % GATE_REL)
        if gate["all_pass"] else
        ("判定は暫定：%s（較正門 %s）。描画が t* の PaintingCam v1 画像であることは呼び出し側の責任。" % (gate.get("refused_ja", ""), GATE_REL)),
        "items": m["items"],
    }
    T.save_json(os.path.join(out_dir, "metrics.json"), out)
    overlay_png(truth, rgb, det, rp, os.path.join(out_dir, a.name + "_overlay.png"),
                "23 evaluate v0: %s (%s mode, judged=%s)" % (a.name, mode, a.judged_version), (a.judged_version,))
    print("EVALUATE_DONE", os.path.join(out_dir, "metrics.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
