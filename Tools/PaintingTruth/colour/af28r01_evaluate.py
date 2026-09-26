# -*- coding: utf-8 -*-
"""番号28修正01：新しい K*（番号26修正01）に焼き直した色面の評価、証拠の図、metrics.json・run.json。

使い方（リポジトリの根で実行。py -3.10、numpy・OpenCV・PIL だけ）:
    py -3.10 Tools/PaintingTruth/colour/af28r01_evaluate.py

入力：
    Unity/Build/ArtFirst/28修正01/render/*.png      Unity の描画（AF28R01NprScene.Render）。色区 ID は主役波だけ（原画視点 3840×2160、座席 1920×1080）
    Unity/Build/ArtFirst/28修正01/bake/*.json, *.bin 焼いたテクスチャと集計（AF28R01ProjectionBaker、外挿 r01＝採用・rule28＝比較）
    Unity/Build/ArtFirst/28/partA/stage_a.npz        番号28 第A部の色区の地図（SHA-256 を第A部の記録と照合）
    Tools/PaintingTruth/colour/colour_truth.json・colour_polylines.json・colour_annotations.json（番号28 第A部の正解）
    比較用（読むだけ）：Docs/Evidence/ArtFirst/28/metrics.json、Unity/Build/ArtFirst/28/render/a45/、Unity/Build/ArtFirst/CP1/render/a45/
出力：
    Docs/Evidence/ArtFirst/28R01/28R01_*.png、metrics.json、run.json
評価の約束（番号28 と同じ。関数は af28_evaluate.py を読み込んで使う）：
    ・t* = 12.0 s の PaintingCam v1、表示フレーム 1920×1080。色区 ID（3840×2160）を 2×2 平均して色区ごとの被覆率にし、
      番号23 の評価器と同じく σ 1 px で平滑して 0.5 の等値線の点にする（採点列 157〜1762）。
    ・主役波以外（前景の波、船、右の海など。原画で主役波の外の画素）は、原画の色区の地図の値で置き換えて比べる
      （番号39・40 の範囲の遮蔽物を原画のものにした合成の評価）。空との境（主役波の輪郭）は描画のままにする。
    ・項目の境界：第A部の折れ線から表示 1.5 px 以内の真値の境界点を、その項目の対象とする（ラベル付き対称 Hausdorff）。
    ・266／267 は原画視点と、D7 で決まった座席 v1（Tools/GWContext/seat_v1.json）の 2 つの向き（既定の向き＝唇へ、唇の方位の仰角 20°）で測る。
"""
import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PT))
sys.path.insert(0, PT)
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import colour_truth as CT  # noqa: E402
import af28_evaluate as E  # noqa: E402  番号28 の評価の関数（ClassBoundary・band_widths・lower_sequence など）

PARAMS_REL = "Tools/PaintingTruth/colour/af28r01_params.json"
CT_REL = E.CT_REL
POLY_REL = E.POLY_REL
ANN_REL = E.ANN_REL
STAGE_REL = E.STAGE_REL
ENV_REL = E.ENV_REL
SKY_ENV_REL = E.SKY_ENV_REL
M28_REL = "Docs/Evidence/ArtFirst/28/metrics.json"
R28_DIR_REL = "Unity/Build/ArtFirst/28/render/a45"
CP1_DIR_REL = "Unity/Build/ArtFirst/CP1/render/a45"
LAYOUT_REL = "Unity/Build/ArtFirst/26修正01/kstar/kstar_a45_uv_layout.json"
CLASSES = E.CLASSES
CLS_VAL = E.CLS_VAL
ID_RGB = E.ID_RGB
PASS_PX = E.PASS_PX
W, H = E.W, E.H
PAL8 = np.array([[248, 243, 223], [198, 215, 203], [44, 105, 147], [35, 64, 97]], np.uint8)   # 白・淡い水色・藍中・藍濃（第A部の中央値の 8bit）

sha256, rel, r3, jl = E.sha256, E.rel, E.r3, E.jl


def save_png(path, rgb):
    ok, buf = cv2.imencode(".png", np.ascontiguousarray(rgb[..., ::-1]), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    if not ok:
        raise IOError("PNG に書けません: " + path)
    buf.tofile(path)


def classify_palette(rgb):
    """描画の色を調色板の 4 色へ最も近い色で分ける（RGB の距離）。空など 4 色から遠い画素は −1。"""
    d = ((rgb[..., None, :].astype(np.int32) - PAL8[None, None].astype(np.int32)) ** 2).sum(-1)
    k = d.argmin(-1)
    k[d.min(-1) > 30 ** 2] = -1
    return k


def bars(img, boxes, a=0.55):
    """文字の下地（半透明の暗い帯）。boxes = [(x, y, w, h)]。"""
    o = img.copy()
    for x, y, w, h in boxes:
        o[y:y + h, x:x + w] = (o[y:y + h, x:x + w].astype(np.float32) * (1 - a)).astype(np.uint8)
    return o


def interior_line_px(path, ex=4.0):
    """外殻線の ID 画像（3840×2160）で、描画の空から ex px より内側にある線の画素（表示 px、被覆率 0.5 以上、採点列の中）。
    原画にない折れ目の線（線マスクは番号36）の量の記録。"""
    if not os.path.exists(path):
        return None
    ids = T.imread_rgb(path)
    f = ids.shape[0] // H
    line = np.all(ids == np.array(ID_RGB["line"], np.uint8), -1).astype(np.float64).reshape(H, f, W, f).mean((1, 3)) >= 0.5
    sky = np.all(ids == np.array(ID_RGB["sky"], np.uint8), -1).astype(np.float64).reshape(H, f, W, f).mean((1, 3)) >= 0.5
    d = E.dist_to(sky)
    m = line & (d > ex)
    m[:, :157] = False
    m[:, 1763:] = False
    return int(m.sum())


def run_evaluator23(rdir, render_png, ids_png, kind, out_root):
    """番号23 の評価器（ID モード）に通す。idmap は空＝白（255,255,255）だけ（番号28 と同じ）。記録のみ。"""
    out = os.path.join(out_root, "eval23_" + kind)
    os.makedirs(out, exist_ok=True)
    idm = os.path.join(out, "idmap_sky.json")
    T.save_json(idm, {"classes": {"sky": [255, 255, 255]}, "note_ja": "番号28修正01 の ID 画像の空（白）だけ。船は描いていない。"})
    cmd = [sys.executable, os.path.join(PT, "evaluate.py"), "--render", os.path.join(rdir, render_png), "--ids", os.path.join(rdir, ids_png),
           "--idmap", idm, "--out-dir", out, "--name", "af28r01_" + kind]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return {"error": r.stderr[-800:]}
    m = jl(os.path.join(out, "metrics.json"))
    res = {}
    for s_ in ("78", "130", "131", "132", "72", "71"):
        if s_ in m["items"]:
            ms = m["items"][s_].get("measures", [{}])[0]
            res[s_] = {"max_px": ms.get("value_max_px"), "p95_px": ms.get("p95_px"), "verdict": m["items"][s_].get("verdict")}
    return res


def uv_preview(bake_dir, suffix, title):
    """焼き込み（4096²）を 960×540 の図へ：左に色区、右に埋め方（カテゴリ）。"""
    N = 4096
    sdf = np.fromfile(os.path.join(bake_dir, "af28r01_uvsdf_a45%s.bin" % suffix), np.uint8).reshape(N, N, 4)
    cat = np.fromfile(os.path.join(bake_dir, "af28r01_uvcat_a45%s.bin" % suffix), np.uint8).reshape(N, N)
    img = PAL8[sdf.argmax(-1)][::-1]
    cc = np.array([[0, 0, 0], [240, 240, 240], [20, 20, 120], [230, 150, 40], [60, 170, 90], [40, 60, 80],
                   [200, 60, 200], [200, 60, 200], [255, 0, 0], [120, 190, 230], [255, 120, 160], [150, 230, 60], [255, 255, 0]], np.uint8)
    cimg = cc[cat][::-1]
    a = cv2.resize(img, (420, 420), interpolation=cv2.INTER_AREA)
    b = cv2.resize(cimg, (420, 420), interpolation=cv2.INTER_NEAREST)
    out = np.full((540, 960, 3), 30, np.uint8)
    out[40:460, 20:440] = a
    out[40:460, 500:920] = b
    out = E.put(out, [(20, 8, title, (255, 255, 255)),
                      (20, 464, "左：色区（白・淡い水色・藍中・藍濃）　右：埋め方", (220, 220, 220)),
                      (20, 486, "白 直接　黄 継ぎ目（r01）　紺 内側の藍濃　橙 u 方向　水 u 方向（藍だけ）　桃 v 方向の藍（r01）", (220, 220, 220)),
                      (20, 506, "緑 v 方向（画面外）　灰 海面　黄緑 残り（同じ列を先に、r01）　紫 残り（同じ行、番号28）", (220, 220, 220)),
                      (20, 522, "焼き込み用 UV（UV3）：横 u′（後ろの海→頂→唇→内壁→前の海）、縦 v′（下が手前の肩、上が奥の尾）", (180, 180, 180))], 14)
    return out


def main():
    t0 = time.time()
    started = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    P = jl(os.path.join(REPO, PARAMS_REL))
    Ev = P["eval"]
    ct = jl(os.path.join(REPO, CT_REL))
    poly = jl(os.path.join(REPO, POLY_REL))
    ann = jl(os.path.join(REPO, ANN_REL))
    spec = T.load_spec()
    sigma = float(spec["scoring"]["contour"]["boundary_smoothing_sigma_px"])
    build = os.path.join(REPO, P["build_dir"])
    rdir = os.path.join(build, "render")
    bdir = os.path.join(build, "bake")
    evid = os.path.join(REPO, P["evidence_dir"])
    os.makedirs(evid, exist_ok=True)
    stage = os.path.join(REPO, STAGE_REL)
    parta = jl(os.path.join(REPO, "Docs/Evidence/ArtFirst/28/partA_run.json"))
    want = None
    for k_, v_ in parta.items():
        if isinstance(v_, dict) and STAGE_REL in v_:
            want = v_[STAGE_REL]
    stage_sha = sha256(stage)
    if want is not None and want != stage_sha:
        raise SystemExit("第A部の中間物の SHA-256 が記録と違います")
    z, fr, cov_t, lab_t = E.truth_maps(stage)
    regs = list(z["regs"])
    comp_id = z["comp_id"]
    lab_of = {r["id"]: i + 1 for i, r in enumerate(regs)}
    feats = poly["features"]
    painting_disp = CT.Frame(fr.W, fr.H).disp_image(T.imread_rgb(T.repo_abs(spec["reference"]["path"])))
    pal = jl(os.path.join(build, "bake_input", "af28_bake_input_record.json"))["palette"]
    render_rep = jl(os.path.join(build, "af28r01_render_report.json"))
    build_rep = jl(os.path.join(build, "af28r01_build_report.json"))
    key = "a45"

    # ---- 項目の対象（真値の折れ線）：番号28 と同じ
    bad_nb = {"sky", "outside", "99", "-1"}
    def fl(kind, item=None, cond=lambda f: True):
        return [f["points_display"] for f in feats if f["kind"] == kind and (item is None or item in f.get("items", [])) and cond(f)]
    white_items = {it: fl("white_part", it, lambda f: str(f.get("neighbour")) not in bad_nb) for it in (79, 133, 134)}
    inner_lines = fl("inner_face_boundary", None, lambda f: str(f.get("neighbour")) not in bad_nb)
    main_bands = sorted({b for m in ct["stripes"]["main_stripes_118"] for b in m["bands"]})
    lines118 = fl("stripe_edge", None, lambda f: f.get("stripe") in main_bands)
    lower_run = np.asarray(ct["stripes"]["lower_side"]["run_display"], np.float64)
    sl_edges = fl("stripe_edge", None, lambda f: str(f.get("stripe", "")).startswith("SL"))
    lines120 = fl("boundary_120")
    lines270 = fl("boundary_270_ai_mid")
    lines270m = fl("boundary_270_mizuiro")
    r175 = [r for r in poly["regions"] if r.get("in_white_range_175")]
    lower_end = np.asarray(ct["inner_face"]["lower_end_display"], np.float64)
    upper_end = np.asarray(ct["inner_face"]["upper_end_display"], np.float64)
    a001 = fr.hi_to_disp_cov(comp_id == lab_of["A001"]) >= 0.5
    w001 = fr.hi_to_disp_cov(comp_id == lab_of["W001"]) >= 0.5
    zone_mask = {}
    for zk in ("79", "133"):
        m = np.zeros((H, W), np.uint8)
        cv2.fillPoly(m, [np.round(np.array(ann["white_item_zones_display"][zk]["points"]) * 8).astype(np.int32)], 1, shift=3)
        zone_mask[zk] = m > 0
    env = jl(os.path.join(REPO, ENV_REL))
    seg = {s["id"]: np.asarray(s["points_display"], np.float64) for s in env["segments"]}
    env_sky = T.load_cov_png(os.path.join(REPO, SKY_ENV_REL)) >= 0.5

    # ---- 色区の境界（番号28 の評価と同じ手順）
    ids_path = os.path.join(rdir, "af28r01_class_ids.png")
    ids, cov_raw, cov_r, lab_r, unknown = E.render_maps(ids_path, cov_t)
    dsky_t = E.dist_to(cov_t["sky"] >= 0.5)
    dsky_r = E.dist_to(cov_r["sky"] >= 0.5)
    CB = {k: E.ClassBoundary(k, cov_t, cov_r, sigma, dsky_t, dsky_r, Ev["silhouette_exclude_px"]) for k in CLASSES}
    items = {}
    assigned_viz = []

    def judge(name, k, lines, extra_sel=None):
        sel = CB[k].select(lines, Ev["item_select_px"])
        if extra_sel is not None:
            sel &= extra_sel(CB[k].tp)
        res, asg = CB[k].hausdorff(sel)
        res["class"] = k
        res["verdict_boundary"] = "pass" if res.get("max_px", np.inf) <= PASS_PX else "fail"
        assigned_viz.append((k, sel, asg, name))
        return res

    items["79"] = {"boundary": judge("79", "white", white_items[79])}
    items["133"] = {"boundary": judge("133", "white", white_items[133])}
    wm = (lab_r == 1).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(wm, 8)
    L = w001 & zone_mask["79"]; U = w001 & zone_mask["133"]
    best = (0, 0.0, 0.0)
    for c in range(1, n):
        fl_ = float((cc[L] == c).mean()) if L.any() else 0.0
        fu_ = float((cc[U] == c).mean()) if U.any() else 0.0
        if min(fl_, fu_) > min(best[1], best[2]):
            best = (c, fl_, fu_)
    items["133"]["continuity"] = {"left_cover": round(best[1], 4), "upper_cover": round(best[2], 4), "pass": bool(best[1] >= 0.5 and best[2] >= 0.5),
                                  "ja": "描画の白の連結成分（8 近傍）のうち最も両方を覆うものが、W001 の左側（79 の区域）と上側（133 の区域）の画素をそれぞれ何割覆うか"}
    items["134"] = {"boundary": judge("134", "white", white_items[134])}
    wt, smt, ordt, okt, P132 = E.band_widths(lab_t, seg["132"], env_sky, Ev["band_blue_min_area_display_px2"])
    wr, smr, ordr, okr, _ = E.band_widths(lab_r, seg["132"], lab_r == 9, Ev["band_blue_min_area_display_px2"])
    dfrac = max(abs(a["arc_fraction"] - b["arc_fraction"]) for a, b in zip(ordt, ordr))
    corr = float(np.corrcoef(smt, smr)[0, 1]) if np.std(smt) > 0 and np.std(smr) > 0 else None
    items["134"]["width_order"] = {"truth": ordt, "render": ordr, "truth_order_ok": bool(okt), "render_order_ok": bool(okr),
                                   "max_arc_fraction_shift": round(dfrac, 3), "median_abs_width_diff_px": round(float(np.median(np.abs(smt - smr))), 2),
                                   "corr_smoothed": r3(corr), "pass": bool(okt and okr and dfrac <= 0.1),
                                   "ja": "番号28 と同じ：132（包絡版）の外輪郭から内向きの白い帯の幅の狭→広→狭の順と位置（弧長の割合の差 ≤0.1）"}
    items["73"] = {"boundary": judge("73", "ai_mid", inner_lines)}
    lower_zone = lambda tp: tp[:, 1] >= lower_end[1] - 60
    items["263"] = {"boundary_lower": judge("263", "ai_mid", inner_lines, lower_zone)}
    am = (lab_r == 3).astype(np.uint8)
    n, cc, st, _ = cv2.connectedComponentsWithStats(am, 8)
    cov_a = [(c, float((cc[a001] == c).mean())) for c in range(1, n)]
    cbest = max(cov_a, key=lambda x: x[1]) if cov_a else (0, 0.0)
    ys, xs = np.nonzero(cc == cbest[0])
    if len(ys) and cbest[0] > 0:
        pts = np.stack([xs, ys], 1).astype(np.float64)
        low = pts[np.argmax(pts[:, 1])]
        d_low = float(np.linalg.norm(pts - lower_end, axis=1).min())
        d_up = float(np.linalg.norm(pts - upper_end, axis=1).min())
    else:
        low, d_low, d_up = None, np.inf, np.inf
    items["263"]["continuity"] = {"component_cover_of_A001": round(cbest[1], 4), "render_lowest_point": r3(low),
                                  "dist_truth_lower_end_px": round(d_low, 3), "dist_truth_upper_end_px": round(d_up, 3),
                                  "pass": bool(cbest[1] >= 0.9 and d_low <= PASS_PX and d_up <= PASS_PX),
                                  "ja": "番号28 と同じ：内側の帯 A001 を最も覆う藍中の成分（≥0.9）が真値の上端と下端の両方から 4 px 以内に届くか"}
    items["120"] = {"boundary": judge("120", "ai_mid", lines120)}
    items["118"] = {"boundary": judge("118", "ai_mid", lines118), "main_stripes": [m["id"] + ":" + "+".join(m["bands"]) for m in ct["stripes"]["main_stripes_118"]]}
    near_lower = lambda tp: T.nearest(tp, T.resample_polyline(lower_run, 0.5))[0] <= Ev["lower_end_zone_px"]
    items["77"] = {"lower_ends": judge("77", "ai_mid", sl_edges, near_lower)}
    seq_t, nb_t, nd_t, Ps, Ns = E.lower_sequence(lab_t, lower_run, Ev["lower_side_strip_px"])
    seq_r, nb_r, nd_r, _, _ = E.lower_sequence(lab_r, lower_run, Ev["lower_side_strip_px"])
    same, dmax = E.compare_sequences(seq_t, seq_r)
    strip = E.strip_mask(lower_run, np.isin(lab_t, [1, 2, 3, 4]), Ev["lower_side_strip_px"])
    strip &= (dsky_t > Ev["silhouette_exclude_px"]) & (dsky_r > Ev["silhouette_exclude_px"])
    comp77 = {}
    ok77 = True
    for nm, cl in (("band_ai_mid", 3), ("dark_ai_dark", 4)):
        ct_ = E.strip_components(lab_t, strip, lower_run, cl, Ev["strip_min_area_px"])
        cr_ = E.strip_components(lab_r, strip, lower_run, cl, Ev["strip_min_area_px"])
        pairs, miss, extra, order_ok = E.match_components(ct_, cr_)
        comp77[nm] = {"truth_n": len(ct_), "render_n": len(cr_), "matched": len(pairs), "order_preserved": bool(order_ok),
                      "missing_in_render": miss, "extra_in_render": extra,
                      "max_end_shift_along_side_px": max([p_[2] for p_ in pairs]) if pairs else None}
        if cl == 3:
            ok77 &= (len(miss) == 0 and len(extra) == 0 and order_ok)
    items["77"]["strip_components"] = {**comp77, "pass": bool(ok77),
                                       "ja": "番号28 と同じ：下側から内側 3〜12 px の帯状の範囲の藍中の帯の本数と並び順（過不足 0、順序が同じ）。藍濃は記録"}
    items["77"]["sequence_record"] = {"truth_n_band_runs": nb_t, "render_n_band_runs": nb_r, "same_kinds_in_order": bool(same), "max_run_edge_shift_px": dmax,
                                      "ja": "記録のみ（番号28 と同じ多数決の並び）"}
    items["270"] = {"boundary": judge("270", "white", lines270)}
    items["270"]["record_mizuiro_reading"] = judge("270m", "white", lines270m)
    # 175
    ret = []
    by_cls = {k: [] for k in ("mizuiro", "ai_mid", "ai_dark")}
    for r in r175:
        m = np.zeros((H, W), np.uint8)
        for ring in r["rings"]:
            pts = np.round(np.asarray(ring["points_display"]) * 8).astype(np.int32)
            cv2.fillPoly(m, [pts], 0 if ring["hole"] else 1, shift=3)
        q = m > 0
        if not q.any():
            c = np.round(np.asarray(r["centroid_display"])).astype(int)
            q[c[1], c[0]] = True
        frac = float((lab_r[q] == CLS_VAL[r["class"]]).mean())
        qi = q & (dsky_t > Ev["silhouette_exclude_px"])
        frac_i = float((lab_r[qi] == CLS_VAL[r["class"]]).mean()) if qi.any() else None
        same_i = int((lab_r[qi] == CLS_VAL[r["class"]]).sum())
        ret.append((r["id"], r["class"], frac, float(r["area_display_px2"]), frac_i, int(q.sum()), int(qi.sum()),
                    r3(r["centroid_display"]), round(float(dsky_t[q].min()), 2), same_i))
        by_cls[r["class"]] += [ring["points_display"] for ring in r["rings"]]
    kept = [x for x in ret if x[2] >= Ev["retain_min_fraction"]]
    lost = [x for x in ret if x[2] < Ev["retain_min_fraction"]]
    kept_i = [x for x in ret if x[6] == 0 or x[9] >= Ev["retain_min_px"]]
    lost_i = [x for x in ret if x[6] > 0 and x[9] < Ev["retain_min_px"]]
    b175 = {k: judge("175_" + k, k, by_cls[k]) for k in by_cls if by_cls[k]}
    mx175 = max(v.get("max_px", 0) for v in b175.values())
    lost_ids = {x[0] for x in lost_i} | {x[0] for x in ret if x[6] == 0 and x[9] == 0 and x[2] == 0}
    by_cls_x = {k: [] for k in by_cls}
    for r in r175:
        if r["id"] not in lost_ids:
            by_cls_x[r["class"]] += [ring["points_display"] for ring in r["rings"]]
    b175x = {k: CB[k].hausdorff(CB[k].select(by_cls_x[k], Ev["item_select_px"]))[0] for k in by_cls_x if by_cls_x[k]}

    def lost_rec(xs):
        return [{"id": x[0], "class": x[1], "fraction_all": round(x[2], 3), "fraction_interior": None if x[4] is None else round(x[4], 3),
                 "same_class_px_interior": x[9], "area_display_px2": x[3], "n_px": x[5], "n_px_interior": x[6], "centroid_display": x[7],
                 "min_dist_to_truth_sky_px": x[8]} for x in xs]
    items["175"] = {"regions_total": len(ret), "regions_retained": len(kept_i), "regions_retained_all_pixels": len(kept),
                    "lost": lost_rec(lost_i), "lost_all_pixels_rule": lost_rec(lost),
                    "retain_rule_ja": "番号28 と同じ：色区の多角形の画素のうち、真値の空から 2 px より内側の画素に描画の同じ色区の画素が 3 px 以上あれば『残る』",
                    "boundary_by_class": b175, "boundary_max_px": round(mx175, 3),
                    "record_excluding_lost_regions": {"excluded": sorted(lost_ids), "boundary_by_class": b175x,
                                                      "boundary_max_px": round(max(v.get("max_px", 0) for v in b175x.values()), 3),
                                                      "ja": "記録のみ：残らなかった色区（輪郭に接する）を除いた境界"},
                    "verdict_boundary": "pass" if mx175 <= PASS_PX else "fail"}

    it = items
    verdict = {}
    def v_of(ok):
        return "pass" if ok else "fail"
    verdict["73"] = v_of(it["73"]["boundary"]["verdict_boundary"] == "pass")
    verdict["77"] = v_of(it["77"]["lower_ends"]["verdict_boundary"] == "pass" and it["77"]["strip_components"]["pass"])
    verdict["79"] = v_of(it["79"]["boundary"]["verdict_boundary"] == "pass")
    verdict["118"] = v_of(it["118"]["boundary"]["verdict_boundary"] == "pass")
    verdict["120"] = v_of(it["120"]["boundary"]["verdict_boundary"] == "pass")
    verdict["133"] = v_of(it["133"]["boundary"]["verdict_boundary"] == "pass" and it["133"]["continuity"]["pass"])
    verdict["134"] = v_of(it["134"]["boundary"]["verdict_boundary"] == "pass" and it["134"]["width_order"]["pass"])
    verdict["175"] = v_of(it["175"]["verdict_boundary"] == "pass" and it["175"]["regions_retained"] == it["175"]["regions_total"])
    verdict["263"] = v_of(it["263"]["boundary_lower"]["verdict_boundary"] == "pass" and it["263"]["continuity"]["pass"])
    verdict["270"] = v_of(it["270"]["boundary"]["verdict_boundary"] == "pass")

    # ---- 265・266・267（色）
    er = int(Ev["colour_erode_px"])
    lab_pk = E.lab_img(os.path.join(rdir, "af28r01_painting_kstar.png"))
    target265 = np.asarray(ct["item_targets"]["265"]["lab"], np.float64)
    m265 = cv2.erode(a001.astype(np.uint8), CT.disk(er)) > 0
    med265 = np.median(lab_pk[m265], 0)
    de265 = float(T.ciede2000(med265, target265))
    col = {"265": {"target_lab_inner_face": r3(target265), "render_lab_median": r3(med265), "n_px": int(m265.sum()), "dE00": round(de265, 3),
                   "verdict": v_of(de265 <= 5.0), "ja": "番号28 と同じ：内側の帯 A001 を 3 px 縮めた範囲で、主役波だけの原画視点の描画の Lab 中央値と原画の中央値の ΔE00"}}
    seat_views = ["seat", "seat_low"]
    seat_lab = {sv: E.lab_img(os.path.join(rdir, "af28r01_%s_kstar.png" % sv)) for sv in seat_views}
    seat_ids = {sv: T.imread_rgb(os.path.join(rdir, "af28r01_%s_class_ids.png" % sv)) for sv in seat_views}
    views = {}
    for k in CLASSES:
        mt = cv2.erode((lab_t == CLS_VAL[k]).astype(np.uint8), CT.disk(er)) > 0
        sp = E.region_stats(lab_pk, mt, pal[k]["lab"])
        rec = {"painting_view": sp}
        for sv in seat_views:
            mb = cv2.erode(np.all(seat_ids[sv] == np.array(ID_RGB[k], np.uint8), -1).astype(np.uint8), CT.disk(er)) > 0
            sb = E.region_stats(seat_lab[sv], mb, pal[k]["lab"])
            cross = round(float(T.ciede2000(np.asarray(sp["lab_median"]), np.asarray(sb["lab_median"]))), 3) if sp and sb else None
            rec[sv + "_view"] = sb
            rec["dE00_%s_vs_painting_median" % sv] = cross
        views[k] = rec

    def flat_ok(k):
        v = views[k]
        if not v["painting_view"] or v["painting_view"]["dE00_to_median_std"] >= 1.0 or v["painting_view"]["bands_ge_20px"] != 0:
            return False
        for sv in seat_views:
            s_ = v[sv + "_view"]
            if not s_ or s_["dE00_to_median_std"] >= 1.0 or s_["bands_ge_20px"] != 0 or v["dE00_%s_vs_painting_median" % sv] > 5.0:
                return False
        return True
    seat_json = jl(os.path.join(REPO, P["seat_json"]))
    seat_note = ("D7 で決まった座席 v1（%s、目 %s、既定の向きの注視点 %s・縦画角 %s°、唇の方位の仰角 20° の注視点 %s）。"
                 % (P["seat_json"], seat_json["seat"]["eye_world"], seat_json["view"]["target_world"], seat_json["view"]["vertical_fov_deg"],
                    seat_json["view"]["qa_hemisphere_look_world"]))
    col["266"] = {"class_default": "ai_mid", "views": {"ai_mid": views["ai_mid"], "mizuiro_record": views["mizuiro"]}, "verdict": v_of(flat_ok("ai_mid")),
                  "seat": seat_note,
                  "ja": "『水色』は番号28 第A部の既定（藍中、既定値・利用者未回答）。原画視点（真値の色区を 3 px 縮めた範囲）と、座席 v1 の 2 つの向き（描画の色区 ID を 3 px 縮めた範囲）の全部で、各画素の色と範囲の中央値の ΔE00 の標準偏差 <1、1 ΔE00 を超える画素が 20 px 以上まとまった帯 0、座席と原画視点の中央値の差 ≤5。淡い水色は記録。番号28 では D7 が未決で旧い座席（手前の船）で測った"}
    col["267"] = {"class": "white", "views": {"white": views["white"]}, "verdict": v_of(flat_ok("white")), "seat": seat_note,
                  "ja": "白について 266 と同じ手順（原画にない灰色の帯＝1 ΔE00 を超える 20 px 以上のまとまり 0）"}
    col["palette_all_classes_record"] = views

    # ---- 空のテクセル（焼き込みの集計）
    bake = {"r01": jl(os.path.join(bdir, "af28r01_bake_a45.json")), "rule28": jl(os.path.join(bdir, "af28r01_bake_a45_rule28.json"))}
    empty = {k: {"emptyAfterFill": bake[k]["emptyAfterFill"], "notRasterised": bake[k]["notRasterised"], "noPositiveClass": bake[k]["noPositiveClass"]} for k in bake}
    verdict_empty = v_of(bake["r01"]["emptyAfterFill"] == 0 and bake["r01"]["notRasterised"] == 0)

    # ---- 142・143（外殻線の位置の事前検査、記録のみ）
    line = E.line_precheck(os.path.join(rdir, "af28r01_line_ids.png"), seg, cov_t)

    interior = {"r01": interior_line_px(os.path.join(rdir, "af28r01_line_ids.png")),
                "number28_old_kstar": interior_line_px(os.path.join(REPO, R28_DIR_REL, "28_a45_line_ids.png")),
                "ja": "外殻線 v0 の ID 画像で、描画の空から 4 px より内側（採点列の中）にある線の画素の数（表示 px）。原画にない面の折れ目の線（主断面の折れ、唇の上など）の量。線マスクは番号36。記録のみ"}
    # ---- 輪郭の照合（番号23 の評価器、ID モード。26修正01 の値の再現の確認、記録のみ）
    sil = run_evaluator23(rdir, "af28r01_painting_kstar.png", "af28r01_class_ids.png", "class_ids", build)
    sil_line = run_evaluator23(rdir, "af28r01_painting_kstar.png", "af28r01_line_ids.png", "line_ids", build)
    m26 = jl(os.path.join(REPO, "Docs/Evidence/ArtFirst/26R01/metrics.json"))

    # ---- 画面の左端の近くの外挿の副作用（番号28 の限界 2）
    lay = jl(os.path.join(REPO, LAYOUT_REL))
    c_of_row = np.asarray(lay["c_of_row_m"], np.float64)
    warp = jl(os.path.join(bdir, "af28r01_uvwarp_a45.json"))
    vw = np.asarray(warp["vWarp"], np.float64)
    N = 4096
    cat28 = np.fromfile(os.path.join(bdir, "af28r01_uvcat_a45_rule28.bin"), np.uint8).reshape(N, N)
    catr = np.fromfile(os.path.join(bdir, "af28r01_uvcat_a45.bin"), np.uint8).reshape(N, N)
    ri = np.clip(np.searchsorted(vw, (np.arange(N) + 0.5) / N) - 1, 0, len(vw) - 1)
    rows6 = np.unique(ri[(cat28 == 6).any(1)])
    rows10 = np.unique(ri[(catr == 10).any(1)])
    # 原画視点の左下（番号28 で白い縦の筋と暗い階段状の塊が出た範囲）の白の画素：番号28（旧い K*、M1 Revision01 の場面）・CP1（旧い K*、番号27 の場面）・28修正01
    box = (200, 780, 300, 960)   # x0, y0, x1, y1（表示 px。番号28 の記録 x ≈ 230〜270・y ≈ 800〜930 を囲む）

    def white_in_box(path):
        if not os.path.exists(path):
            return None
        im = T.imread_rgb(path)[box[1]:box[3], box[0]:box[2]]
        k = classify_palette(im)
        return {"white_px": int((k == 0).sum()), "mizuiro_px": int((k == 1).sum()), "box_px": int(k.size)}
    left_box = {"number28_old_kstar_m1_scene": white_in_box(os.path.join(REPO, R28_DIR_REL, "28_a45_painting.png")),
                "cp1_old_kstar_context27": white_in_box(os.path.join(REPO, CP1_DIR_REL, "cp1_a45_painting.png")),
                "r01_rule28": white_in_box(os.path.join(rdir, "af28r01_painting_rule28.png")),
                "r01_adopted": white_in_box(os.path.join(rdir, "af28r01_painting.png"))}
    diff_views = {}
    for v in ["painting", "seat", "seat_low", "seat_left", "side_left", "back"]:
        a = T.imread_rgb(os.path.join(rdir, "af28r01_%s.png" % v)).astype(np.int32)
        b = T.imread_rgb(os.path.join(rdir, "af28r01_%s_rule28.png" % v)).astype(np.int32)
        dm = np.abs(a - b).sum(-1) > 30
        ka = classify_palette(a.astype(np.uint8)); kb = classify_palette(b.astype(np.uint8))
        diff_views[v] = {"changed_px": int(dm.sum()), "rule28_white_to_blue_px": int((dm & (kb <= 1) & (ka >= 2)).sum()),
                         "rule28_dark_to_mid_px": int((dm & (kb == 3) & (ka == 2)).sum())}
    left = {
        "texels": {k: {kk: bake[k][kk] for kk in ("occludedVisible", "occludedFilledNonBlue", "occludedFilledBlue", "leftoverU", "leftoverV", "leftoverDefault",
                                                   "vFillBlueOccluded", "leftoverVFirst", "seam")} for k in bake},
        "rule28_leftover_rows": {"rows": [int(rows6.min()), int(rows6.max())] if len(rows6) else None, "n_rows": int(len(rows6)),
                                 "c_m": [round(float(c_of_row[rows6.min()]), 2), round(float(c_of_row[rows6.max()]), 2)] if len(rows6) else None},
        "r01_vfill_rows": {"rows": [int(rows10.min()), int(rows10.max())] if len(rows10) else None, "n_rows": int(len(rows10)),
                           "c_m": [round(float(c_of_row[rows10.min()]), 2), round(float(c_of_row[rows10.max()]), 2)] if len(rows10) else None},
        "painting_left_box_display": {"box_x0_y0_x1_y1": list(box), "counts": left_box},
        "render_diff_r01_vs_rule28": diff_views,
        "ja": ("番号28 の限界 2（原画視点の左下 x ≈ 230〜270・y ≈ 800〜930 の白い縦の筋と暗い階段状の塊）の確かめ。"
               "texels：原画の遮蔽物に隠れた見えるテクセル（occludedVisible）のうち白・淡い水色で埋まった数（occludedFilledNonBlue、白い筋の元）と、残り（leftoverU＝カテゴリ 6、暗い塊の元）。"
               "rule28_leftover_rows：番号28 の規則で残りが出た格子の行と、その行の波峰線に沿った位置 c（m、主断面 0、正が奥）。"
               "painting_left_box_display：原画視点の描画（場面全体）の箱の中で、調色板の白・淡い水色に近い画素の数。"
               "render_diff_r01_vs_rule28：同じ視点の r01 と rule28 の描画の差の画素数"),
    }

    # ---- 図
    figs = make_figures(evid, rdir, bdir, painting_disp, CB, assigned_viz, items, verdict, col, line, left)

    # ---- 番号28 との比較
    m28 = jl(os.path.join(REPO, M28_REL))
    cmp28 = {}
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        v28 = m28["items"][k_]["value"]
        cmp28[k_] = {"number28_max_px": round(E.item_max(v28), 3), "r01_max_px": round(E.item_max(items[k_]), 3)}
    cmp28["265"] = {"number28_dE00": m28["items"]["265"]["value"]["dE00"], "r01_dE00": col["265"]["dE00"]}

    # ---- metrics.json
    status = E.gate_status_safe()
    names = {"73": "内側の水色（藍中）の色区の境界", "77": "下側から始まる縞の本数・並び順と下側端", "79": "左側の白の境界", "118": "主要な縞の両側の境界",
             "120": "唇の白と内側の水色の境", "133": "左側から上側へ続く白と上側の境界", "134": "白帯の両側の境界と幅の広狭", "175": "白の中の藍・水色の色区が全部残る",
             "263": "内側から下方へ続く水色", "270": "白と水色の境"}
    items_out = {}
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        items_out[k_] = {"name_ja": names[k_], "criterion": "境界 ≤4 px（表示 px、最大）" + ("＋並び" if k_ == "77" else "＋連続" if k_ in ("133", "263") else "＋広狭の順" if k_ == "134" else "＋全部残る" if k_ == "175" else ""),
                         "value": items[k_], "verdict": verdict[k_]}
    items_out["175"]["handling_ja"] = ("作業計画 4.2 の 28修正01 の受入：輪郭に接する小さな色区が残らない場合は、番号28 の選択肢(1)（判定の規則は変えず、"
                                       "輪郭と爪（番号29・33）ができた後に判定し直す）で扱う（既定値・利用者未回答）。")
    items_out["265"] = {"name_ja": "内側の水色の表示色", "criterion": "ΔE00 ≤5（領域の中央値）", "value": col["265"], "verdict": col["265"]["verdict"]}
    items_out["266"] = {"name_ja": "水色の平塗り（照明の帯 0）", "criterion": "領域内の ΔE00 の標準偏差 <1、帯 0、座席と原画視点の差 ≤5（原画視点と座席 v1 の 2 つの向き）", "value": col["266"], "verdict": col["266"]["verdict"]}
    items_out["267"] = {"name_ja": "白の平塗り（灰色の帯 0）", "criterion": "同上", "value": col["267"], "verdict": col["267"]["verdict"]}
    items_out["uv_no_empty_texels"] = {"name_ja": "UV テクスチャに空のテクセルがない", "criterion": "外挿の後に未設定 0、UV で描かれないテクセル 0（採用の r01）", "value": empty, "verdict": verdict_empty}
    items_out["142"] = {"name_ja": "左側の外周線（事前検査）", "criterion": "記録のみ（正式な判定は番号36）", "value": line["142"], "verdict": "record-only"}
    items_out["143"] = {"name_ja": "上側から船側の端までの外周線（事前検査）", "criterion": "記録のみ（正式な判定は番号36）", "value": line["143"], "verdict": "record-only"}
    items_out["outline_interior_record"] = {"name_ja": "外殻線 v0 の内側の線（原画にない折れ目の線）", "criterion": "記録のみ（線マスクは番号36）", "value": interior, "verdict": "record-only"}
    items_out["178"] = {"name_ja": "縞の枝分かれ", "criterion": "計画の損切りどおり記録のみ（延期）", "value": {"partA_branch_candidates": len(ct["stripes"]["branches_178"])}, "verdict": "record-only"}
    items_out["left_edge_extrapolation"] = {"name_ja": "画面の左端の近くの外挿の副作用（番号28 の限界 2）", "criterion": "記録のみ（見えない面の配色の判定は番号41）", "value": left, "verdict": "record-only"}
    M = {
        "schema": "GreatWave.AF28R01.metrics/1", "number": "28修正01",
        "t_star_s": spec["timeline"]["t_star_s"], "camera": spec["painting_cam"]["id"], "frame": [W, H],
        "key": key, "key_ja": P["preferred_ja"],
        "kstar": {"gwb": P["kstar_dir"] + "/kstar_a45.gwb", "gwb_sha256": bake["r01"]["gwbSha256"], "vertex_count": render_rep.get("vertexCount")},
        "fill_rule_adopted": P["fill_rule_adopted"], "fill_rule_r01_ja": P["fill_rule_r01_ja"],
        "evidence_kind_ja": "Unity 6000.4.3f1 Editor の batchmode による PC のオフスクリーン描画（RTX 3080、Direct3D11、Linear 色空間）と、その画像の numpy・OpenCV の測定。HMD 実機の結果ではない。",
        "evaluator": {"method_ja": __doc__.split("評価の約束（番号28 と同じ。関数は af28_evaluate.py を読み込んで使う）：")[1].strip(),
                      "truth": "番号28 第A部の色区の正解 v0（colour_truth.json）と番号23 の真値 v0.2",
                      "gate23": {"all_pass": status.get("all_pass"), "truth_unchanged_since_gate": status.get("truth_unchanged_since_gate")},
                      "provisional": not bool(status.get("all_pass")),
                      "structural_note_ja": "t* の原画視点の境界と色は、投影ベイクにより構造上ほぼ一致する（テクセルは自分の投影先の原画の値を持つ）。これは完成を意味しない。船上・側面・背面の見え方と、形成の途中の配色は別に確かめる（作業計画 31 の注意、R11）。"},
        "items": items_out,
        "compare_number28": {"values": cmp28, "ja": "番号28（旧い K*、80,000 頂点）の値と、28修正01（26修正01 の K*、96,000 頂点）の値。判定の手順は同じ"},
        "silhouette_crosscheck_evaluator23": {"class_ids": sil, "with_outline_shell": sil_line,
                                               "number26R01_same_items": {e_["item"]: {"max_px": e_.get("r01"), "p95_px": e_.get("r01_p95")} for e_ in m26.get("evaluator_compare", [])
                                                                          if isinstance(e_, dict) and e_.get("item") in ("78", "130", "131", "132", "72", "71")},
                                               "ja": "番号23 の評価器（ID モード、包絡版）に、この番号の色区 ID 画像（空＝白）を通した値（記録のみ）。形は 26修正01 の K* のままなので、78〜132・72 は 26修正01 の値に近いはず"},
        "bake": {k: {kk: bake[k][kk] for kk in ("direct", "innerDark", "uFill", "uFillBlue", "vFillBlueOccluded", "vFill", "sea", "leftoverVFirst", "leftoverU", "leftoverV",
                                               "leftoverDefault", "seam", "emptyAfterFill", "noPositiveClass", "onScreen", "visible", "classCountsDirect", "classCountsAll",
                                               "depthRowsFlipped", "uvRowsFlipped", "depthCheckMatchNormal", "depthCheckMatchFlipped", "outSdfSha256")} for k in bake},
        "uv3_warp": jl(os.path.join(build, "bake_input", "af28_bake_input_record.json"))["kstar"]["a45"]["uv3_warp"],
        "palette_srgb8": {k: pal[k]["srgb8"] for k in CLASSES},
        "seat": {"source": P["seat_json"], "eye_world": seat_json["seat"]["eye_world"], "target_world": seat_json["view"]["target_world"],
                 "low_target_world": seat_json["view"]["qa_hemisphere_look_world"], "vertical_fov_deg": seat_json["view"]["vertical_fov_deg"],
                 "unity_marker_to_eye_m": build_rep.get("seatMarkerToEyeM")},
        "shader_v1": {"unlit_palette_linear_check": {k: {"painting_view_dE00_median_to_palette": (views[k]["painting_view"] or {}).get("dE00_median_to_palette"),
                                                         "seat_view_dE00_median_to_palette": (views[k]["seat_view"] or {}).get("dE00_median_to_palette"),
                                                         "seat_low_view_dE00_median_to_palette": (views[k]["seat_low_view"] or {}).get("dE00_median_to_palette")} for k in CLASSES},
                      "id_mode_unknown_px": unknown,
                      "shaders_unchanged_from_28_ja": "NPR v1・外殻線 v0・焼き込みのシェーダーとマテリアルは番号28 のものを読むだけで変えていない（Unity の保護ファイルの SHA-256 が前後で一致。run.json の inputs_sha256）。立体視のコンパイルの確認は番号28 の af28_spi_compile.json のまま"},
        "summary_verdicts": {**verdict, "265": col["265"]["verdict"], "266": col["266"]["verdict"], "267": col["267"]["verdict"], "uv_no_empty_texels": verdict_empty},
        "figures": figs,
    }
    T.save_json(os.path.join(evid, "metrics.json"), M)

    # ---- run.json
    ins = [PARAMS_REL, "Tools/PaintingTruth/colour/af28_params.json", CT_REL, POLY_REL, ANN_REL, ENV_REL, SKY_ENV_REL, E.LW_REL, "Tools/PaintingTruth/painting_truth.json",
           "Tools/PaintingTruth/colour/af28r01_bake_input.py", "Tools/PaintingTruth/colour/af28_bake_input.py", "Tools/PaintingTruth/colour/af28r01_evaluate.py",
           "Tools/PaintingTruth/colour/af28_evaluate.py", "Tools/PaintingTruth/colour/run_af28r01.ps1", "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/evaluate.py",
           P["seat_json"], LAYOUT_REL, P["kstar_dir"] + "/kstar_a45_meta.json",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF28R01ProjectionBaker.cs", "Unity/Assets/GreatWave/ArtFirst/Editor/AF28R01NprScene.cs",
           "Unity/Assets/GreatWave/ArtFirst/Editor/AF28ProjectionBaker.cs", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF28NprWave.cs",
           "Unity/Assets/GreatWave/ArtFirst/Scripts/AF26KStarMesh.cs", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_Bake.shader",
           "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_NPR.shader", "Unity/Assets/GreatWave/ArtFirst/Shaders/AF28_Outline.shader",
           "Unity/Assets/GreatWave/ArtFirst/Materials/AF28_NPR.mat", "Unity/Assets/GreatWave/ArtFirst/Materials/AF28_Outline.mat",
           "Unity/Assets/GreatWave/ArtFirst/Prefabs/AF27R01_Context.prefab", "Unity/Assets/GreatWave/Scenes/Tests/AF28R01_NPR.unity"]
    build_files = []
    for d, _, fs in os.walk(build):
        for f_ in fs:
            build_files.append(os.path.join(d, f_))
    run = {
        "schema": "GreatWave.AF28R01.run/1", "number": "28修正01", "started_utc": started,
        "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "commands": ["powershell -NoProfile -ExecutionPolicy Bypass -File Tools/PaintingTruth/colour/run_af28r01.ps1",
                     "py -3.10 Tools/PaintingTruth/colour/af28r01_bake_input.py",
                     "E:/6000.4.3f1/Editor/Unity.exe -batchmode -projectPath G:/Unity/GreatWave_2026_Fresh/Unity -executeMethod GreatWave.ArtFirst.EditorTools.AF28R01NprScene.BakeBuildAndRender -logFile Unity/Build/ArtFirst/28修正01/unity_af28r01.log -quit",
                     "py -3.10 Tools/PaintingTruth/colour/af28r01_evaluate.py"],
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": __import__("PIL").__version__, "unity": render_rep.get("unity"), "device": render_rep.get("device"),
                  "graphics_api": render_rep.get("graphicsApi"), "color_space": render_rep.get("colorSpace"), "os": platform.platform()},
        "unity_lock_ja": "Unity は Unity/Build/unity.lock を排他的に作ってから 1 プロセスだけ動かし、終わったら消した（run_af28r01.ps1）。",
        "inputs_sha256": {r_: sha256(os.path.join(REPO, r_)) for r_ in ins if os.path.exists(os.path.join(REPO, r_))},
        "stage_a_sha256": stage_sha,
        "kstar_gwb_sha256": bake["r01"]["gwbSha256"],
        "unity_build_report": {"sceneSha256": build_rep.get("sceneSha256"), "protectedUnchanged": build_rep.get("protectedUnchanged"),
                               "protectedFiles": build_rep.get("protectedFiles")},
        "unity_render_report": {"protectedUnchanged": render_rep.get("protectedUnchanged"), "passed": render_rep.get("passed"), "totalSeconds": render_rep.get("totalSeconds")},
        "outputs_sha256": {rel(os.path.join(evid, f_)): sha256(os.path.join(evid, f_)) for f_ in sorted(os.listdir(evid))
                           if f_.startswith("28R01_") or f_ == "metrics.json"},
        "not_committed_sha256": {rel(p_): sha256(p_) for p_ in sorted(build_files) if not p_.endswith(".log") and os.sep + "eval23_" not in p_},
        "not_committed_ja": "Unity/Build/ArtFirst/28修正01/ は Git 対象外（/Unity/Build/）。焼いたテクスチャ（各 64 MB、r01 と rule28）・原画側の入力（80 MB と 10 MB、番号28 と同じ bytes）・描画・ID 画像・焼き込みの集計。同じコマンドで作り直せる。",
        "elapsed_evaluate_s": round(time.time() - t0, 1),
        "bake_seconds": {k: round(float(bake[k]["secondsTotal"]), 2) for k in bake},
        "render_seconds": render_rep.get("totalSeconds"),
    }
    T.save_json(os.path.join(evid, "run.json"), run)
    print("AF28R01_EVALUATE_DONE", M["summary_verdicts"], round(time.time() - t0, 1), "s")
    return 0


def make_figures(evid, rdir, bdir, paint, CB, assigned_viz, items, verdict, col, line, left):
    figs = []
    rd = lambda name: T.imread_rgb(os.path.join(rdir, name))
    rgb = rd("af28r01_painting.png")
    # 1 原画視点（場面全体、外殻線あり）
    p = os.path.join(evid, "28R01_painting.png")
    save_png(p, rgb)
    figs.append(rel(p))
    # 2 原画 50% 重ね
    ov = (0.5 * rgb.astype(np.float32) + 0.5 * paint.astype(np.float32)).astype(np.uint8)
    ov = E.put(ov, [(170, 1040, "28修正01：NPR v1（26修正01 の K*、45°、t*、PaintingCam v1）と原画の 50% 重ね（確認用の図。測定には使わない）", (255, 255, 255))], 20)
    p = os.path.join(evid, "28R01_overlay50.png")
    E.quant_save(p, ov)
    figs.append(rel(p))
    # 3 境界の偏差図
    img = E.dimmed(paint, 0.4)
    for k, sel, asg, name in assigned_viz:
        cb = CB[k]
        tp = cb.tp[sel]
        for q in tp[::2]:
            img[int(round(q[1])) % H, int(round(q[0])) % W] = (0, 255, 255)
        if asg is None:
            continue
        rp = cb.rp[asg]
        dd = cb.d_rt[asg]
        c = np.where(dd[:, None] <= 2.0, np.array([[60, 230, 60]]), np.where(dd[:, None] <= 4.0, np.array([[255, 220, 0]]), np.array([[255, 40, 40]])))
        xi = np.clip(np.round(rp[:, 0]).astype(int), 0, W - 1); yi = np.clip(np.round(rp[:, 1]).astype(int), 0, H - 1)
        img[yi, xi] = c
    rows = []
    for k_ in ["73", "77", "79", "118", "120", "133", "134", "175", "263", "270"]:
        v = items[k_]
        b = v.get("boundary") or v.get("boundary_lower") or v.get("lower_ends")
        mx = E.item_max(v)
        p95 = b.get("p95_px") if b else None
        rows.append("%s: 最大 %.2f px%s  %s" % (k_, mx, (" / p95 %.2f" % p95) if p95 is not None else "", "合格" if verdict[k_] == "pass" else "不合格"))
        cand = [v.get("boundary"), v.get("boundary_lower"), v.get("lower_ends")] + list(v.get("boundary_by_class", {}).values())
        for bb in cand:
            if bb and bb.get("max_px", 0) > PASS_PX and bb.get("worst_display_xy"):
                w_ = bb["worst_display_xy"]
                cv2.circle(img, (int(round(w_[0])), int(round(w_[1]))), 12, (255, 40, 40), 2, cv2.LINE_AA)
    rows.append("265: ΔE00 %.2f  %s" % (col["265"]["dE00"], "合格" if col["265"]["verdict"] == "pass" else "不合格"))
    items_txt = [(1400, 60 + 26 * i, r_, (255, 255, 255)) for i, r_ in enumerate(rows)]
    img = E.put(img, [(170, 1010, "色区の境界（28修正01、45°、t*）：シアン＝真値の項目の境界、描画の境界点 緑 ≤2 px・黄 ≤4 px・赤 >4 px、赤丸＝4 px を超えた所", (255, 255, 255)),
                      (170, 1040, "主役波の外（前景の波・船など）は原画の値で置き換えた合成の評価。空との境 2 px 以内は輪郭の項目（78〜132・72）の対象として除いた。表示 px", (255, 255, 255))] + items_txt, 19)
    p = os.path.join(evid, "28R01_boundaries.png")
    E.quant_save(p, img)
    figs.append(rel(p))

    def tile(name, s=(960, 540)):
        return cv2.resize(rd(name), s, interpolation=cv2.INTER_AREA)
    # 4 座席 v1（D7）
    v4 = np.concatenate([np.concatenate([tile("af28r01_seat.png"), tile("af28r01_seat_low.png")], 1),
                         np.concatenate([tile("af28r01_seat_waveonly.png"), tile("af28r01_seat_low_waveonly.png")], 1)], 0)
    v4 = bars(v4, [(0, 0, 960, 34), (960, 0, 960, 34), (0, 540, 960, 34), (960, 540, 960, 34), (0, 1010, 1920, 70)])
    s266 = col["266"]["views"]["ai_mid"]; s267 = col["267"]["views"]["white"]
    def sd(v, k):
        return "—" if not v.get(k) else "%.3f" % v[k]["dE00_to_median_std"]
    v4 = E.put(v4, [(12, 8, "座席 v1（右船、D7）：既定の向き（唇へ、縦画角 80°）、場面全体", (255, 255, 255)), (972, 8, "座席 v1：唇の方位・仰角 20°、場面全体", (255, 255, 255)),
                    (12, 548, "同じ向き：主役波・空・海だけ（船・富士・仮置きを描画の間だけ隠した確認図）", (255, 255, 255)), (972, 548, "同じ向き：主役波・空・海だけ", (255, 255, 255)),
                    (12, 1018, "唇の奥（主断面より奥の錐の行）は原画で見えず、内側の藍濃と、輪郭の縁で深度の検査を通った少数の直接のテクセルが行ごとに並び、白と藍濃の細い横縞（櫛の歯）に見える（番号41）", (255, 255, 255)),
                    (12, 1050, "266 藍中の ΔE00 の標準偏差 原画視点 %s・座席 %s・仰角 20° %s ／ 267 白 %s・%s・%s（<1 で合格）。PC のオフスクリーン描画、HMD ではない" % (
                        sd(s266, "painting_view"), sd(s266, "seat_view"), sd(s266, "seat_low_view"), sd(s267, "painting_view"), sd(s267, "seat_view"), sd(s267, "seat_low_view")), (255, 255, 255))], 20)
    p = os.path.join(evid, "28R01_seat.png")
    E.quant_save(p, v4)
    figs.append(rel(p))
    # 5 側面・背面
    v4 = np.concatenate([np.concatenate([tile("af28r01_side_left.png"), tile("af28r01_back.png")], 1),
                         np.concatenate([tile("af28r01_seat_left.png"), tile("af28r01_back_waveonly.png")], 1)], 0)
    v4 = bars(v4, [(0, 0, 960, 34), (960, 0, 960, 34), (0, 540, 960, 34), (960, 540, 960, 34), (0, 1040, 1920, 40)])
    v4 = E.put(v4, [(12, 8, "左の側面（−90, 30, −14）、場面全体", (255, 255, 255)), (972, 8, "背面（−45, 30, 60）、場面全体", (255, 255, 255)),
                    (12, 548, "座席 v1 から左（手前の肩）、場面全体", (255, 255, 255)), (972, 548, "背面：主役波・空・海だけ", (255, 255, 255)),
                    (12, 1050, "原画で見えない面は外挿の色（見えない内側は藍濃、ほかは u 方向・v 方向に延ばした色）。見えない面の配色の判定は番号41", (255, 255, 255))], 20)
    p = os.path.join(evid, "28R01_side.png")
    E.quant_save(p, v4)
    figs.append(rel(p))
    # 6 画面の左端の近くの外挿（番号28 の限界 2）：番号28・CP1（旧い K*）と 28修正01（rule28・r01）
    crops = []
    x0, y0, x1, y1 = 120, 650, 520, 1000
    for label, path in (("番号28（旧い K*、M1 の場面）", os.path.join(REPO, R28_DIR_REL, "28_a45_painting.png")),
                        ("CP1（旧い K*、番号27 の場面）", os.path.join(REPO, CP1_DIR_REL, "cp1_a45_painting.png")),
                        ("28修正01（番号28 の規則）", os.path.join(rdir, "af28r01_painting_rule28.png")),
                        ("28修正01（r01、採用）", os.path.join(rdir, "af28r01_painting.png"))):
        im = T.imread_rgb(path)[y0:y1, x0:x1] if os.path.exists(path) else np.zeros((y1 - y0, x1 - x0, 3), np.uint8)
        im = cv2.resize(im, (480, 420), interpolation=cv2.INTER_NEAREST)
        crops.append((label, im))
    top = np.concatenate([c for _, c in crops], 1)
    sl_a = rd("af28r01_seat_left.png")[400:980, 1340:1920]; sl_b = rd("af28r01_seat_left_rule28.png")[400:980, 1340:1920]
    bk_a = rd("af28r01_back.png"); bk_b = rd("af28r01_back_rule28.png")
    bk_a = bk_a[250:830, 600:1180]; bk_b = bk_b[250:830, 600:1180]
    bot = np.concatenate([cv2.resize(x, (480, 480), interpolation=cv2.INTER_AREA) for x in (sl_b, sl_a, bk_b, bk_a)], 1)
    fig = np.concatenate([top, bot, np.full((1080 - 900, 1920, 3), 30, np.uint8)], 0)
    tx = left["texels"]
    txt = [(8 + 480 * i, 6, lab_, (255, 255, 255)) for i, (lab_, _) in enumerate(crops)]
    fig = bars(fig, [(0, 0, 1920, 30), (0, 420, 1920, 30)])
    txt += [(8, 426, "座席から左：番号28 の規則", (255, 255, 255)), (488, 426, "座席から左：r01", (255, 255, 255)),
            (968, 426, "背面：番号28 の規則", (255, 255, 255)), (1448, 426, "背面：r01", (255, 255, 255))]
    lb = left["painting_left_box_display"]["counts"]
    def wb(k):
        return "—" if lb.get(k) is None else str(lb[k]["white_px"])
    txt += [(12, 906, "上段：原画視点の左下（表示 x 120〜520・y 650〜1000 を拡大）。番号28 の白い縦の筋と暗い階段状の塊は、26修正01 の K* では外挿の規則によらず出ない", (255, 255, 255)),
            (12, 930, "（箱 x 200〜300・y 780〜960 の白の画素：番号28 %s・CP1 %s → 28修正01 番号28 の規則 %s・r01 %s）" % (
                wb("number28_old_kstar_m1_scene"), wb("cp1_old_kstar_context27"), wb("r01_rule28"), wb("r01_adopted")), (255, 255, 255)),
            (12, 956, "原画の遮蔽物に隠れた見えるテクセルのうち白・淡い水色で埋まった数：番号28 の規則 %d → r01 %d。残り（同じ行に直接のテクセルがない行、カテゴリ 6）：%d → %d" % (
                tx["rule28"]["occludedFilledNonBlue"], tx["r01"]["occludedFilledNonBlue"], tx["rule28"]["leftoverU"], tx["r01"]["leftoverU"]), (255, 255, 255)),
            (12, 982, "番号28 の規則の残りは奥の尾（c %s m、原画視点で主断面に隠れる行）にあり、同じ行の海面の藍濃が写って暗い面と細い線になる。r01 は同じ列で最も近い行の色を写す（下段）" % (
                "〜".join("%.1f" % v for v in (left["rule28_leftover_rows"]["c_m"] or [0, 0]))), (255, 255, 255)),
            (12, 1008, "原画視点の描画の差 %d px（主断面の継ぎ目の点線が r01 で消えた所）。座席・側面・背面の差：%s" % (
                left["render_diff_r01_vs_rule28"]["painting"]["changed_px"],
                "、".join("%s %d px" % (k, v["changed_px"]) for k, v in left["render_diff_r01_vs_rule28"].items() if k != "painting")), (255, 255, 255)),
            (12, 1034, "座席・側面・背面の差はどちらも原画で見えない面の外挿で、見えない面の配色の判定は番号41。PC のオフスクリーン描画", (200, 200, 200))]
    fig = E.put(fig, txt, 18)
    p = os.path.join(evid, "28R01_leftedge.png")
    E.quant_save(p, fig)
    figs.append(rel(p))
    # 7 UV の焼き込み（r01 と rule28）
    uv = np.concatenate([uv_preview(bdir, "", "焼き込み（r01、採用）"), uv_preview(bdir, "_rule28", "焼き込み（番号28 の規則、比較）")], 1)
    uv = np.concatenate([uv, np.full((540, 1920, 3), 30, np.uint8)], 0)
    ctab = left["texels"]
    fig = E.put(uv, [(20, 560, "焼き込み用 UV（UV3）：26修正01 の K*（400 列 × 240 行）を 4096² へ。下が手前の肩（c −60 m）、上が奥の尾（c +15 m）", (255, 255, 255)),
                               (20, 590, "未設定のテクセル 0、UV で描かれないテクセル 0（どちらの規則も）。r01 で変わるのは原画で見えない面と継ぎ目だけ（カテゴリ 10・11・12）", (255, 255, 255)),
                               (20, 620, "r01：継ぎ目 %d テクセル、v 方向の藍（原画の遮蔽物の下で同じ行に藍がない）%d、残り（同じ列を先に）%d、残り（同じ行）%d" % (
                                   ctab["r01"]["seam"], ctab["r01"]["vFillBlueOccluded"], ctab["r01"]["leftoverVFirst"], ctab["r01"]["leftoverU"]), (255, 255, 255)),
                               (20, 650, "番号28 の規則：残り（同じ行）%d テクセル" % ctab["rule28"]["leftoverU"], (255, 255, 255))], 18)
    p = os.path.join(evid, "28R01_uv.png")
    E.quant_save(p, fig)
    figs.append(rel(p))
    # 8 CP1（旧い K*）との並べ図：原画視点と座席
    cp1p = os.path.join(REPO, CP1_DIR_REL, "cp1_a45_painting.png")
    cp1s = os.path.join(REPO, CP1_DIR_REL, "cp1_a45_seatmid.png")
    if os.path.exists(cp1p) and os.path.exists(cp1s):
        a = np.concatenate([cv2.resize(T.imread_rgb(cp1p), (960, 540), interpolation=cv2.INTER_AREA), tile("af28r01_painting.png")], 1)
        b = np.concatenate([cv2.resize(T.imread_rgb(cp1s), (960, 540), interpolation=cv2.INTER_AREA), tile("af28r01_seat.png")], 1)
        fig = np.concatenate([a, b], 0)
        fig = bars(fig, [(0, 0, 1920, 34), (0, 540, 1920, 34), (0, 1040, 1920, 40)])
        fig = E.put(fig, [(12, 8, "CP1：番号26 の K*（45°）＋番号28 の焼き込み、原画視点", (255, 255, 255)), (972, 8, "28修正01：26修正01 の K*＋焼き直し、原画視点", (255, 255, 255)),
                          (12, 548, "CP1：座席の候補 (a) 右船（番号27 の置き方、注視点は主役波の中ほど）", (255, 255, 255)),
                          (972, 548, "28修正01：座席 v1（27修正01 で右船を置き直した座席、既定の向き）", (255, 255, 255)),
                          (12, 1050, "左右で座席の位置と向きが違う（CP1 の候補は置き直す前の右船）。どちらも PC のオフスクリーン描画", (255, 255, 255))], 20)
        p = os.path.join(evid, "28R01_compare_cp1.png")
        E.quant_save(p, fig)
        figs.append(rel(p))
    return figs


if __name__ == "__main__":
    sys.exit(main())
