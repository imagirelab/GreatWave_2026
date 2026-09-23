"""輪郭線に基づく基準輪郭の候補B。次の1コマンドで全出力を再生成できる:

  & "G:/Unity/GreatWave_2026/Blender/great_wave/tools/run_blender.ps1" src/contour/method_b_run.py

出力先
  target/candidates/b/base_contour.json                       （選択した back_left_variant）
  target/candidates/b/base_contour_alt_<other variant>.json   （左端の別の読み取り方）
  results/step1_prepare/contour_b/*.png, metrics_b.json
パラメーター: src/contour/method_b_params.json。全値に説明がある。
"""
import os
import sys
import math
import time

_SRC = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import numpy as np                                                   # noqa: E402
from gw import bootstrap, paths, frame, imgio, draw, plot            # noqa: E402
from contour import method_b_lib as L                                # noqa: E402
from contour import method_b_core as C                               # noqa: E402

log = bootstrap.log
HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = os.path.join(HERE, "method_b_params.json")
OUT_JSON_DIR = os.path.join(paths.CANDIDATES_DIR, "b")
OUT_IMG_DIR = os.path.join(paths.STEP1_DIR, "contour_b")

SEG_COLORS = {"back": "red", "head": "magenta", "inner_arc": "lime"}
COMPLETED_COLOR = "orange"
BRIDGE_COLOR = "black"
RAW_COLOR = "cyan"


# ------------------------------------------------------------------ 補助関数
def clip_start_to_x0(pts, lab):
    """折れ線の始点を左枠の x = 0 に正確に合わせる。"""
    if pts[0, 0] > 0:
        n = min(12, len(pts) - 1)
        d = pts[n] - pts[0]
        if d[0] <= 1e-6:
            raise RuntimeError("cannot extrapolate the start to x = 0")
        p = pts[0] - d * (pts[0, 0] / d[0])
        p[0] = 0.0
        return np.vstack([p[None], pts]), np.concatenate([[lab[0]], lab])
    i = int(np.argmax(pts[:, 0] >= 0))
    if i == 0:
        return pts, lab
    a, b = pts[i - 1], pts[i]
    t = (0.0 - a[0]) / (b[0] - a[0])
    p = a + t * (b - a)
    p[0] = 0.0
    return np.vstack([p[None], pts[i:]]), np.concatenate([[lab[i]], lab[i:]])


def resample_exact_labelled(p, lab, spacing):
    q, t = L.resample_uniform_exact(p, spacing)
    s = L.arclength(p)
    j = np.clip(np.searchsorted(s, t, side="right") - 1, 0, len(s) - 2)
    near = np.where(np.abs(s[j] - t) <= np.abs(s[j + 1] - t), j, j + 1)
    lab_new = np.maximum(lab[j], lab[j + 1])
    on = np.abs(s[near] - t) < 1e-6
    lab_new = np.where(on, lab[near], lab_new)
    lab_new[0], lab_new[-1] = lab[0], lab[-1]
    return q, lab_new.astype(np.int8), float(t[1] - t[0]) if len(t) > 1 else spacing


def pct(F, p):
    l, t = F.px_to_pct(p[0], p[1])
    return [float(l), float(t)]


def Hxy(F, p):
    X, Z = F.px_to_H(p[0], p[1])
    return [float(X), float(Z)]


def dpct_h(F, d_px):
    return float(F.px_to_pct_h(d_px))


def stats(d):
    d = np.asarray(d, dtype=np.float64)
    if len(d) == 0:
        return {"n": 0}
    return {"n": int(len(d)), "mean_px": float(d.mean()), "p95_px": float(np.percentile(d, 95)),
            "max_px": float(d.max())}


# ------------------------------------------------------------------ 一つの半径に対する処理工程
def contour_for_radius(masks, radius, cfg, refine=True):
    path, dev = C.opened_boundary(masks, radius, cfg)
    pts0, lab0, bridges = C.label_and_bridge(path, dev, cfg)
    pts1, lab1 = C.resample_labelled(pts0, lab0, 1.0)
    info = {}
    if refine:
        pts2, info, _ = C.refine_traced(pts1, lab1, masks, cfg)
    else:
        pts2 = L.gaussian_smooth_open(pts1, C.P(cfg, "stair_sigma_px"), 1.0)
    pts2, lab2 = clip_start_to_x0(pts2, lab1)
    pts3, lab3 = C.resample_labelled(pts2, lab2, 1.0)
    pts4 = C.final_smooth(pts3, lab3, cfg)
    return {"crack_path": path, "crack_dev": dev, "pts_pixel": pts0, "lab_pixel": lab0,
            "pts_refined": pts3, "pts": pts4, "lab": lab3, "bridges": bridges, "refine_info": info}


def landmarks_of(pts, cfg, F):
    """1 px 間隔の輪郭上で特徴点の番号を求める。

    峰と最深点はほぼ平坦な区間にあるため、landmark_sigma_pct_h で平滑化した
    写しの極値を採用する。画素雑音の影響を抑えつつ、最高点と最左点を表す。
    plateau_tol_pct_h 内の平坦区間と、平滑化前の厳密な極値も併記する。
    波頭の先端は明確に曲がっているため、x の厳密な最大値を用いる。
    """
    tol = float(F.pct_h_to_px(C.P(cfg, "plateau_tol_pct_h")))
    sm = L.gaussian_smooth_open(pts, float(F.pct_h_to_px(C.P(cfg, "landmark_sigma_pct_h"))), 1.0)
    i_top = int(np.argmin(pts[:, 1]))
    i_crest = int(np.argmin(sm[:, 1]))
    _, ca, cb = C.plateau_midpoint(pts, pts[:, 1], i_top, tol, +1.0)
    i_tip = i_crest + int(np.argmax(pts[i_crest:, 0]))
    i_dmin = i_tip + int(np.argmin(pts[i_tip:, 0]))
    i_deep = i_tip + int(np.argmin(sm[i_tip:, 0]))
    _, da, db = C.plateau_midpoint(pts, pts[:, 0], i_dmin, tol, +1.0)
    return {"i_crest": i_crest, "crest_argmin": i_top, "crest_plateau": (ca, cb),
            "i_tip": i_tip, "tip_argmax": i_tip,
            "i_deep": i_deep, "deep_argmin": i_dmin, "deep_plateau": (da, db)}


# ------------------------------------------------------------------ 左端を白い本体として読む変種
def white_body_back(masks, main_back, cfg):
    """左枠にある青帯の下縁を主となる背面輪郭につなぐ。

    約 1 px 間隔の点と情報辞書を返す。
    """
    thr = C.P(cfg, "ink_blueness_thr")
    blue = (masks["D"] > thr) | (masks["GR"] > thr)     # 濃い青、または帯の明るい青緑の筋。
    col = blue[:, 0]
    y_top = int(round(main_back[0, 1]))
    # 空の境界より下で青くない画素が30個以上続く最初の区間、その直前の 0 列目の青画素。
    y = y_top + 5
    h = len(col)
    y_low = None
    while y < h - 30:
        if not col[y:y + 30].any():
            y_low = y - 1
            break
        y += 1
    if y_low is None or not col[y_low] or col[y_low + 1]:
        raise RuntimeError("white_body_back: band lower edge not found in column 0")
    path = L.trace_cracks_open(blue, (0, y_low + 1), 0, 6000).astype(np.float64)
    lab = np.zeros(len(path), np.int8)
    p1, l1 = C.resample_labelled(path, lab, 1.0)
    p2, info, _ = C.refine_traced(p1, l1, masks, cfg, field_sign=-1.0)
    p2, l2 = clip_start_to_x0(p2, l1)
    p3, _ = C.resample_labelled(p2, l2, 1.0)
    p3 = L.gaussian_smooth_open(p3, C.P(cfg, "sigma_traced_px"), 1.0)
    s = L.arclength(p3)
    dist, seg, tt = L.point_polyline_distance(p3, main_back)
    cand = np.nonzero((s > 100.0) & (dist < C.P(cfg, "alt_join_dist_px")))[0]
    if len(cand) == 0:
        raise RuntimeError("white_body_back: the trace never joins the main back")
    j = int(cand[0])
    blend_len = C.P(cfg, "alt_blend_len_px")
    k = int(np.argmin(np.abs(s - (s[j] + blend_len))))
    proj = main_back[seg] + tt[:, None] * (main_back[seg + 1] - main_back[seg])
    u = np.clip((s[j:k + 1] - s[j]) / max(s[k] - s[j], 1e-9), 0.0, 1.0)
    w = (u * u * (3 - 2 * u))[:, None]
    blended = p3[j:k + 1] * (1 - w) + proj[j:k + 1] * w
    i_main = int(seg[k]) + 1
    out = np.vstack([p3[:j], blended, main_back[i_main:]])
    info.update({"band_lower_edge_at_left_frame_px": [float(p3[0, 0]), float(p3[0, 1])],
                 "join_px": [float(p3[j, 0]), float(p3[j, 1])],
                 "blend_end_px": [float(blended[-1, 0]), float(blended[-1, 1])]})
    return out, info


# ------------------------------------------------------------------ 測定
def back_slopes(back, sigma_pct_h, window_pct_h, cfg, F):
    sig = float(F.pct_h_to_px(sigma_pct_h))
    win = float(F.pct_h_to_px(window_pct_h))
    s_mid, ang, q = C.slope_profile(back, sig)
    total = s_mid[-1]

    def mean_in(a, b):
        sel = (s_mid >= a) & (s_mid <= b)
        return float(ang[sel].mean()) if sel.any() else float("nan")

    left_end = mean_in(0.0, win)
    i_max = int(np.argmax(ang))
    before = {}
    for d_pct in (1.0, 2.0, 3.0, 5.0, 8.0):
        d = float(F.pct_h_to_px(d_pct))
        before["%g_pct_h_before_crest" % d_pct] = mean_in(total - d - 0.5 * win, total - d + 0.5 * win)
    i_min = int(np.argmin(ang[:i_max + 1])) if i_max > 0 else 0
    after_max = ang[i_max:]
    # 最急点から峰までの傾斜角の増加の最大値。0 なら単調に緩くなる。
    run_min = np.minimum.accumulate(after_max)
    viol = float((after_max - run_min).max())
    px_per_pct = float(F.pct_h_to_px(1.0))
    table = []
    for x_target in (0, 100, 200, 300, 335, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400):
        i = int(np.argmin(np.abs(q[:-1, 0] - x_target)))
        sel = np.abs(s_mid - s_mid[i]) <= 0.5 * win
        table.append({"x_px": float(q[i, 0]), "y_px": float(q[i, 1]), "slope_deg": float(ang[sel].mean())})
    return {"smoothing_sigma_px": sig, "window_px": win,
            "left_end_deg": left_end,
            "left_end_definition": "mean tangent angle over the first %.0f px of arclength from the left frame edge" % win,
            "min_before_steepest_deg": float(ang[i_min]),
            "min_before_steepest_at_px": [float(q[i_min, 0]), float(q[i_min, 1])],
            "mid_max_deg": float(ang[i_max]),
            "mid_max_at_px": [float(q[i_max, 0]), float(q[i_max, 1])],
            "mid_max_at_pct": pct(F, q[i_max]),
            "before_crest_deg": before,
            "before_crest_definition": "mean tangent angle in a %.0f px window centred d before the crest (arclength)" % win,
            "mid_is_steepest": bool(ang[i_max] > left_end and ang[i_max] > before["3_pct_h_before_crest"]),
            "flattens_towards_crest_max_increase_deg": viol,
            "slope_table": table,
            "profile": {"s_pct_h": (s_mid / px_per_pct).tolist()[::10], "deg": ang.tolist()[::10]}}


def tip_direction_and_thickness(head, inner, cfg, F):
    """先端から同じ弧長だけ離れた上下の点で中心線の方向と厚さを求める。

    head は峰から先端へ、inner は先端から内側の弧へ向かい、ともに約 1 px 間隔。
    """
    Hpx = float(F.H_to_px_len(1.0))
    sh = L.arclength(head[::-1])          # 上面に沿って先端から後方へ進む距離。
    si = L.arclength(inner)               # 下面に沿って先端から進む距離。
    top = head[::-1]

    def at(poly, s, d):
        return np.array([np.interp(d, s, poly[:, 0]), np.interp(d, s, poly[:, 1])])

    thick = []
    for p_ in C.P(cfg, "thickness_arclength_pct_H"):
        d = p_ / 100.0 * Hpx
        a, b = at(top, sh, d), at(inner, si, d)
        chord = float(np.hypot(*(a - b)))
        dmin, _, _ = L.point_polyline_distance(a[None], inner)
        dmin2, _, _ = L.point_polyline_distance(b[None], top)
        thick.append({"arclength_behind_tip_pct_H": p_, "arclength_px": d,
                      "top_point_px": a.tolist(), "under_point_px": b.tolist(),
                      "pair_distance_pct_H": chord / Hpx * 100.0,
                      "top_point_to_underside_min_pct_H": float(dmin[0]) / Hpx * 100.0,
                      "under_point_to_topside_min_pct_H": float(dmin2[0]) / Hpx * 100.0})
    r0, r1 = [v / 100.0 * Hpx for v in C.P(cfg, "tip_direction_range_pct_H")]
    ds = np.arange(r0, r1 + 1e-9, 4.0)
    mids = np.array([0.5 * (at(top, sh, d) + at(inner, si, d)) for d in ds])
    # 中点群の主方向を求め、先端へ向かう向きに揃える。
    c = mids.mean(axis=0)
    u, s_, vt = np.linalg.svd(mids - c)
    v = vt[0]
    if np.dot(v, mids[0] - mids[-1]) < 0:
        v = -v
    direction = float(F.px_dir_to_deg(v[0], v[1]))
    return thick, direction, mids


def s8_report(seg_pts, spacing_px, F, limit=15.0):
    r = L.s8_profile(seg_pts, spacing_px)
    turn = r["turn_deg"]
    q = r["points"]
    over = np.nonzero(np.abs(turn) >= limit)[0]
    worst = np.argsort(-np.abs(turn))[:8]
    return {"n_samples": int(len(q)), "max_abs_turn_deg": r["max_abs_deg"],
            "n_vertices_ge_15deg": int(len(over)),
            "p95_abs_turn_deg": float(np.percentile(np.abs(turn), 95)) if len(turn) else 0.0,
            "worst": [{"px": [float(q[i + 1, 0]), float(q[i + 1, 1])], "pct": pct(F, q[i + 1]),
                       "turn_deg": float(turn[i])} for i in worst],
            "_points": q, "_turn": turn}


# ------------------------------------------------------------------ 描画
def draw_contour(view_img, to_view, segs, scale_w=1.0, raw=None):
    if raw is not None:
        draw.polyline(view_img, to_view(raw), RAW_COLOR, 1.0 * scale_w)
    for name, (pts, lab) in segs.items():
        draw.polyline(view_img, to_view(pts), SEG_COLORS[name], 2.6 * scale_w)
        for code, colr, wd in ((C.BRIDGE, BRIDGE_COLOR, 3.4), (C.COMPLETED_OCCLUDED, COMPLETED_COLOR, 2.6),
                               (C.COMPLETED_OTHER, COMPLETED_COLOR, 2.6)):
            sel = lab == code
            if sel.any():
                p = pts.copy()
                p[~sel] = np.nan
                draw.polyline(view_img, to_view(p), colr, wd * scale_w)
                if code == C.BRIDGE:        # segment colour as a thin core so the segment stays readable
                    draw.polyline(view_img, to_view(p), SEG_COLORS[name], 0.9 * scale_w)


def legend(img, x, y, scale=2):
    items = [("back (traced)", SEG_COLORS["back"]), ("head (traced)", SEG_COLORS["head"]),
             ("inner_arc (traced)", SEG_COLORS["inner_arc"]), ("claw_root_bridge (any segment)", BRIDGE_COLOR),
             ("completed (hidden)", COMPLETED_COLOR), ("raw silhouette with claws", RAW_COLOR)]
    w = max(draw.text_size(t, scale)[0] for t, _ in items) + 60
    hgt = len(items) * 11 * scale + 10
    draw.rect(img, x, y, x + w, y + hgt, "white", fill=True, alpha=0.85)
    for k, (t, c) in enumerate(items):
        yy = y + 6 + k * 11 * scale
        draw.line(img, (x + 6, yy + 4 * scale), (x + 40, yy + 4 * scale), c, 4)
        draw.text(img, x + 48, yy, t, "black", scale)


# ------------------------------------------------------------------ 主処理
def main():
    t_start = time.perf_counter()
    cfg = paths.read_json(PARAMS)
    F = frame.get_frame()
    painting_path = paths.painting_path()
    img_full = imgio.load_painting_rgb()
    x0, y0, x1, y1 = C.P(cfg, "roi_xyxy")
    if x0 != 0 or y0 != 0:
        raise ValueError("roi must start at (0, 0) so that ROI px = painting px")
    img = np.ascontiguousarray(img_full[:y1, :x1])
    paths.ensure_dir(OUT_JSON_DIR)
    paths.ensure_dir(OUT_IMG_DIR)
    spec_px = {k: np.array([float(v) for v in F.pct_to_px(*pc)]) for k, pc in frame.SPEC_LANDMARKS_PCT.items()}
    y_trough = float(F.H_to_px(0.0, 0.0)[1])
    px_per_pct = float(F.pct_h_to_px(1.0))
    Hpx = float(F.H_to_px_len(1.0))

    # ---- 段階 A、B。
    with bootstrap.Timer("stage A masks"):
        masks = C.build_masks(img, cfg, log)
    for name, (px, py) in {"back foam": (900, 600), "head foam": (2050, 900), "near wave": (1500, 1800)}.items():
        if masks["sky"][py, px]:
            raise RuntimeError("sky region leaks into '%s' -- gap closing failed" % name)
    raw = C.raw_silhouette(masks, cfg).astype(np.float64)
    log("stage B: raw silhouette %d crack vertices" % len(raw))

    # ---- 選択した半径で段階 C、D、E を実行。
    R = float(C.P(cfg, "open_radius_px"))
    with bootstrap.Timer("stage C-E (R=%g)" % R):
        res = contour_for_radius(masks, R, cfg, refine=True)
    pts, lab = res["pts"], res["lab"]
    lm = landmarks_of(pts, cfg, F)
    normals_in, _ = L.local_normals(pts, int(C.P(cfg, "normal_half_window_px")))
    i_end, blue_inside = C.inner_arc_end(pts, normals_in, lm["i_deep"], masks, cfg)
    log("landmarks: crest i=%d, tip i=%d, deepest i=%d, inner-arc end i=%d of %d" %
        (lm["i_crest"], lm["i_tip"], lm["i_deep"], i_end, len(pts)))
    seg_in = pts[lm["i_deep"]:i_end + 1]
    s_in = L.arclength(seg_in)
    sel_in = s_in >= s_in[-1] - C.P(cfg, "completion_tangent_chord_px")
    t_end = seg_in[sel_in][-1] - seg_in[sel_in][0]
    t_end = t_end / np.hypot(*t_end)
    tangent_alternatives = {}
    for fit_len in (100.0, 150.0, 250.0, 400.0):
        tq = C.end_tangent(seg_in, fit_len)
        tangent_alternatives["quadratic_fit_last_%g_px" % fit_len] = math.degrees(math.atan2(tq[1], tq[0]))
        s_ = L.arclength(seg_in)
        sel_ = s_ >= s_[-1] - fit_len
        ch = seg_in[sel_][-1] - seg_in[sel_][0]
        tangent_alternatives["chord_last_%g_px" % fit_len] = math.degrees(math.atan2(ch[1], ch[0]))
    fr0, fr1, frs = C.P(cfg, "completion_run_fracs")
    comp, comp_c, comp_p1, comp_frac, comp_nsky = C.hidden_completion(
        pts[i_end], t_end, y_trough, masks["sky"], np.arange(fr0, fr1 - 1e-9, -frs))
    log("completion: end tangent %.1f deg below horizontal, run_frac %.2f, samples in visible sky %d" %
        (math.degrees(math.atan2(t_end[1], t_end[0])), comp_frac, comp_nsky))
    log("completion: end tangent alternatives (deg below horizontal): %s" %
        {k: round(v, 1) for k, v in tangent_alternatives.items()})

    full = np.vstack([pts[:i_end + 1], comp[1:]])
    full_lab = np.concatenate([lab[:i_end + 1], np.full(len(comp) - 1, C.COMPLETED_OCCLUDED, np.int8)])
    i_c, i_t = lm["i_crest"], lm["i_tip"]
    seg_1px = {"back": (full[:i_c + 1], full_lab[:i_c + 1]),
               "head": (full[i_c:i_t + 1], full_lab[i_c:i_t + 1]),
               "inner_arc": (full[i_t:], full_lab[i_t:])}

    # ---- 左端のもう一つの読み取り方。
    alt_back, alt_info = white_body_back(masks, seg_1px["back"][0], cfg)
    alt_lab = np.zeros(len(alt_back), np.int8)
    # 共有部分のラベルは、主となる背面上の最近接点から引き継ぐ。
    d_, sg_, _ = L.point_polyline_distance(alt_back, seg_1px["back"][0])
    alt_lab = np.where(d_ < 0.5, seg_1px["back"][1][np.clip(sg_, 0, len(seg_1px["back"][1]) - 1)], 0).astype(np.int8)
    variants = {"sky_silhouette": seg_1px["back"], "white_body_outline": (alt_back, alt_lab)}
    selected = C.P(cfg, "back_left_variant")
    if selected not in variants:
        raise ValueError("unknown back_left_variant %r" % selected)

    # ---- 測定 -------------------------------------------------------------------
    metrics = {"params_file": paths.norm(PARAMS), "open_radius_px": R, "refine_info": res["refine_info"],
               "alt_refine_info": alt_info, "n_bridges": len(res["bridges"]),
               "completion": {"start_px": pts[i_end].tolist(), "start_pct": pct(F, pts[i_end]),
                              "end_tangent_deg_below_horizontal": math.degrees(math.atan2(t_end[1], t_end[0])),
                              "control_point_px": comp_c.tolist(), "end_px": comp_p1.tolist(), "end_H": Hxy(F, comp_p1),
                              "run_frac": comp_frac, "samples_in_visible_sky": comp_nsky,
                              "end_tangent_alternatives_deg_below_horizontal": tangent_alternatives,
                              "length_px": float(L.arclength(comp)[-1])}}
    crest, tip, deep = pts[i_c], pts[i_t], pts[lm["i_deep"]]

    # S1
    ca, cb = lm["crest_plateau"]
    s1 = {"spec_pct": list(frame.SPEC_LANDMARKS_PCT["S1_crest"]), "spec_px": spec_px["S1_crest"].tolist(),
          "measured_px": crest.tolist(), "measured_pct": pct(F, crest),
          "dx_pct_h": dpct_h(F, crest[0] - spec_px["S1_crest"][0]), "dy_pct_h": dpct_h(F, crest[1] - spec_px["S1_crest"][1]),
          "strict_highest_point_px": pts[lm["crest_argmin"]].tolist(),
          "plateau_within_0p1pct_px": [pts[ca].tolist(), pts[cb].tolist()],
          "plateau_within_0p1pct_pct": [pct(F, pts[ca]), pct(F, pts[cb])],
          "plateau_width_pct_h": dpct_h(F, pts[cb, 0] - pts[ca, 0]),
          "how": "highest point of the de-clawed, sub-pixel refined outer outline edge: argmin(y) of a copy smoothed with sigma = landmark_sigma_pct_h; the top is nearly flat, so the stretch within 0.1 % of image height of the strict top and the strict argmin are reported too"}
    tol2 = 2.0
    top_y = pts[lm["crest_argmin"], 1]
    sel2 = np.nonzero(pts[:i_t, 1] <= top_y + tol2)[0]
    s1["plateau_within_2px_x_range_px"] = [float(pts[sel2, 0].min()), float(pts[sel2, 0].max())]
    # S2
    da, db = lm["deep_plateau"]
    s2 = {"spec_pct": list(frame.SPEC_LANDMARKS_PCT["S2_inner_arc_deepest"]), "spec_px": spec_px["S2_inner_arc_deepest"].tolist(),
          "measured_px": deep.tolist(), "measured_pct": pct(F, deep), "measured_H": Hxy(F, deep),
          "dx_pct_h": dpct_h(F, deep[0] - spec_px["S2_inner_arc_deepest"][0]),
          "dy_pct_h": dpct_h(F, deep[1] - spec_px["S2_inner_arc_deepest"][1]),
          "dist_pct_h": dpct_h(F, np.hypot(*(deep - spec_px["S2_inner_arc_deepest"]))),
          "strict_leftmost_point_px": pts[lm["deep_argmin"]].tolist(),
          "plateau_within_0p1pct_px": [pts[da].tolist(), pts[db].tolist()],
          "plateau_height_pct_h": dpct_h(F, pts[db, 1] - pts[da, 1]),
          "how": "left-most point of the traced boundary between the blue concave face and the sky (outer edge of its outline): argmin(x) of a copy smoothed with sigma = landmark_sigma_pct_h; the boundary is nearly vertical there, so the stretch within 0.1 % of image height of the strict minimum is reported too"}
    # S3: 手前の波の右側に見える暗い海の上縁。
    xs_t = np.arange(2010, 2081)
    ys_t = []
    for xx in xs_t:
        colm = masks["sky"][1700:, xx]
        ys_t.append(1700 + int(np.argmin(colm)))
    ys_t = np.asarray(ys_t, dtype=np.float64)
    sea_top = float(np.median(ys_t))
    s3 = {"spec_height_pct": 66.0, "spec_trough_top_pct": frame.SPEC_TROUGH_TOP_PCT, "spec_trough_y_px": y_trough,
          "feature": "top edge (far edge / horizon) of the dark blue sea patch visible between the near wave flank and the boat bow, columns x = 2010..2080",
          "sea_top_edge_y_px": {"median": sea_top, "min": float(ys_t.min()), "max": float(ys_t.max())},
          "sea_top_edge_top_pct": float(sea_top / F.height_px * 100.0),
          "crest_top_pct_measured": s1["measured_pct"][1],
          "height_pct_if_sea_top_edge_is_trough": float((sea_top - crest[1]) / F.height_px * 100.0),
          "diff_from_spec_pct_h": float((sea_top - crest[1]) / F.height_px * 100.0 - 66.0),
          "reliable": False,
          "how": "first non-sky pixel below y = 1700 in every column of the gap-closed sky region. The trough floor itself is hidden by the near wave and the boat; the visible sea patch spans from this edge down to about y = 1990 (76.7 %), the spec level 74.7 % (y = 1937.7) lies inside the patch and cannot be tied to a drawn feature."}
    # 両変種の S4。
    s4 = {}
    for vname, (bp, _) in variants.items():
        s4[vname] = back_slopes(bp, C.P(cfg, "s4_smooth_sigma_pct_h"), C.P(cfg, "s4_window_pct_h"), cfg, F)
        s4[vname]["coarse_scale"] = back_slopes(bp, C.P(cfg, "s4_coarse_sigma_pct_h"),
                                                C.P(cfg, "s4_coarse_window_pct_h"), cfg, F)
    # S5 と厚さ。
    thick, centre_dir, mids = tip_direction_and_thickness(seg_1px["head"][0], seg_1px["inner_arc"][0], cfg, F)
    tipH = Hxy(F, tip)
    crest_to_tip_deg = float(F.px_dir_to_deg(tip[0] - crest[0], tip[1] - crest[1]))
    tip_dir, ov_centroid, ov_poly, ov_elong, ov_area = C.overhang_axis(
        pts, lm["i_deep"], i_t, masks["sky"].shape, draw.polygon_mask)
    head_pts = seg_1px["head"][0]
    sh_ = L.arclength(head_pts[::-1])
    top_tan = {}
    for p_ in (5.0, 10.0):
        d_ = p_ / 100.0 * Hpx
        a_ = np.array([np.interp(d_, sh_, head_pts[::-1][:, 0]), np.interp(d_, sh_, head_pts[::-1][:, 1])])
        top_tan["chord_last_%g_pct_H_of_top_side_deg" % p_] = float(F.px_dir_to_deg(tip[0] - a_[0], tip[1] - a_[1]))
    s5 = {"head_tip_px": tip.tolist(), "head_tip_pct": pct(F, tip), "head_tip_H": tipH,
          "strict_rightmost_px": pts[lm["tip_argmax"]].tolist(),
          "direction_deg": tip_dir,
          "direction_definition": "principal axis (largest second moment of area) of the OVERHANG = area enclosed by the base contour on the boat side of the vertical through the inner-arc deepest point (top side -> head tip -> underside -> inner arc down to the deepest point, closed by that vertical); 0 deg = +X, negative = pointing below the horizontal. Robust against lobes and claw-removal details because it uses the whole area.",
          "overhang_centroid_px": ov_centroid.tolist(), "overhang_area_px2": ov_area, "overhang_elongation": ov_elong,
          "direction_alternatives_deg": dict(top_tan, crest_to_tip=crest_to_tip_deg,
                                             centre_line_5_to_20_pct_H_behind_tip=centre_dir),
          "direction_alternatives_note": "The painted head (claws removed) is a thick blob whose right flank is nearly vertical; its right-most point sits at the UPPER end of that flank, so local definitions (top-side chord, centre line of equal-arclength pairs) give unstable, even upward values. They are listed for transparency only.",
          "crest_to_tip_direction_deg": crest_to_tip_deg,
          "overhang_pct_H": tipH[0] * 100.0 - Hxy(F, crest)[0] * 100.0,
          "tip_relative_to_S6_spec_pct_h": [dpct_h(F, tip[0] - spec_px["S6_claw_rightmost"][0]),
                                            dpct_h(F, tip[1] - spec_px["S6_claw_rightmost"][1])]}
    # S6: 爪を含む元の輪郭の最右点。
    sel_r = raw[:, 1] < 1400
    xr = raw[sel_r, 0].max()
    yr = float(raw[sel_r][raw[sel_r, 0] == xr][:, 1].mean())
    p6 = np.array([[xr - 1.0, yr]])
    r6, ok6, sh6, c6 = L.refine_edge(255.0 - masks["Lm"], p6, np.array([[-1.0, 0.0]]), search=4.0,
                                     step=0.25, outer=(3.0, 7.0), inner_max=3.5, level=0.5, min_contrast=12.0)
    claw = r6[0] if ok6[0] else np.array([xr, yr])
    s6 = {"spec_pct": list(frame.SPEC_LANDMARKS_PCT["S6_claw_rightmost"]), "spec_px": spec_px["S6_claw_rightmost"].tolist(),
          "measured_px": claw.tolist(), "measured_pct": pct(F, claw), "measured_H": Hxy(F, claw),
          "pixel_level_px": [float(xr), yr], "subpixel_ok": bool(ok6[0]),
          "dx_pct_h": dpct_h(F, claw[0] - spec_px["S6_claw_rightmost"][0]),
          "dy_pct_h": dpct_h(F, claw[1] - spec_px["S6_claw_rightmost"][1]),
          "overhang_pct_H_from_measured_crest": (Hxy(F, claw)[0] - Hxy(F, crest)[0]) * 100.0,
          "crest_to_claw_direction_deg": float(F.px_dir_to_deg(claw[0] - crest[0], claw[1] - crest[1])),
          "how": "right-most vertex of the ordered sky boundary WITH claws (y < 1400), refined to the half level of the outer outline edge on that row"}
    for vname in s4:
        s4[vname]["spec_deg"] = {"left_end": 25.0, "mid_max": 47.0, "before_crest": 8.0}
        s4[vname]["how"] = ("tangent angle of the back (outer outline edge) on a Gaussian-smoothed copy; 'fine' = sigma %g %% of image "
                            "height, window %g %%; 'coarse_scale' = sigma %g %%, window %g %%. The spec does not say where and over "
                            "which length its three angles were taken, so profiles and tables are given instead of one number."
                            % (C.P(cfg, "s4_smooth_sigma_pct_h"), C.P(cfg, "s4_window_pct_h"),
                               C.P(cfg, "s4_coarse_sigma_pct_h"), C.P(cfg, "s4_coarse_window_pct_h")))
    # 除いた爪のうち最長のもの: 最終輪郭から最も遠い元の輪郭点。
    sel_c = (raw[:, 1] < 1300) & (raw[:, 0] > 1500)
    rc = raw[sel_c][::2]
    d_c, _, _ = L.point_polyline_distance(rc, pts)
    k_c = int(np.argmax(d_c))
    metrics_claws = {"max_distance_raw_silhouette_to_base_contour_px": float(d_c[k_c]),
                     "max_distance_pct_h": dpct_h(F, d_c[k_c]), "max_distance_pct_H": float(d_c[k_c] / Hpx * 100.0),
                     "at_px": rc[k_c].tolist()}
    remeasure = {"S1": s1, "S2": s2, "S3": s3, "S4": s4[selected], "S6": s6}
    metrics.update({"S1": s1, "S2": s2, "S3": s3, "S4": s4, "S5": s5, "S6": s6, "head_thickness": thick,
                    "claws_removed": metrics_claws})

    # ---- 両変種の出力区間（2 px 間隔）------------------------------------------
    spacing = float(C.P(cfg, "sample_spacing_px"))
    s8_spacing = float(F.pct_h_to_px(paths.param("S8_sample_spacing_pct")))
    written = {}
    for vname, back_v in variants.items():
        segs_in = {"back": back_v, "head": seg_1px["head"], "inner_arc": seg_1px["inner_arc"]}
        segs_out, seg_json, spac = {}, [], {}
        for sname, jp in (("back", "\u80cc"), ("head", "\u6ce2\u982d"), ("inner_arc", "\u5185\u5074\u306e\u5f27")):
            q, ql, sp = resample_exact_labelled(segs_in[sname][0], segs_in[sname][1], spacing)
            segs_out[sname] = (q, ql)
            spac[sname] = sp
            seg_json.append({"name": sname, "jp": jp,
                             "points_px": np.round(q, 3).tolist(),
                             "points_H": np.round(F.pts_px_to_H(q), 6).tolist(),
                             "source": [C.SOURCE_NAMES[int(c)] for c in ql],
                             "in_S7": [bool(c in (C.TRACED, C.BRIDGE)) for c in ql],
                             "actual_spacing_px": sp})
        # 共有する端点は完全に一致させる。
        assert np.allclose(segs_out["back"][0][-1], segs_out["head"][0][0])
        assert np.allclose(segs_out["head"][0][-1], segs_out["inner_arc"][0][0])
        obj = {
            "schema": "gw.base_contour.v1",
            "candidate": "B (outline-based)",
            "variant": {"back_left_variant": vname, "selected_in_params": bool(vname == selected),
                        "note": "Two readings of the back left of x = 335 px exist; see docs/records/step1_contour_b.md. The user has to decide."},
            "image": {"path": painting_path, "width": F.width_px, "height": F.height_px},
            "frame": {"crest_left_pct": F.crest_left_pct, "crest_top_pct": F.crest_top_pct, "height_pct": F.height_pct,
                      "frame_h_H": round(F.frame_h, 6), "frame_w_H": round(F.frame_w, 6),
                      "x_left_H": round(F.x_left, 6), "z_top_H": round(F.z_top, 6)},
            "order": "left frame edge -> crest -> head tip -> inner arc -> trough",
            "sample_spacing_px": spacing,
            "contour_definition": "outer (sky side) edge of the ink outline at half level between sky and ink; claws removed with a rolling ball (R = %g px) from the body side, claw-root points joined by chords, then Gaussian smoothing (traced %g px, bridges %g px)" % (R, C.P(cfg, "sigma_traced_px"), C.P(cfg, "sigma_bridge_px")),
            "segments": seg_json,
            "landmarks": {
                "crest": {"px": crest.tolist(), "H": Hxy(F, crest), "pct": pct(F, crest),
                          "definition": "highest point of the base contour (argmin y of a copy smoothed with sigma 0.5 % of image height); flat top: see remeasure.S1 for the plateau"},
                "head_tip": {"px": tip.tolist(), "H": tipH, "pct": pct(F, tip), "direction_deg": tip_dir,
                             "direction_definition": s5["direction_definition"]},
                "inner_deepest": {"px": deep.tolist(), "H": Hxy(F, deep), "pct": pct(F, deep)},
                "trough_level": {"y_px": y_trough, "top_pct": frame.SPEC_TROUGH_TOP_PCT,
                                 "note": "Z = 0 of the frame definition (crest_top_pct + height_pct); NOT re-measured, see remeasure.S3"},
                "claw_rightmost": {"px": claw.tolist(), "H": Hxy(F, claw), "pct": pct(F, claw)},
                "inner_arc_visible_end": {"px": pts[i_end].tolist(), "H": Hxy(F, pts[i_end]), "pct": pct(F, pts[i_end]),
                                          "note": "last point where the wave side of the boundary is blue; beyond it the boundary belongs to the near wave"},
                "completion_end": {"px": comp_p1.tolist(), "H": Hxy(F, comp_p1)}
            },
            "remeasure": dict(remeasure, S4=s4[vname], S5=s5),
        }
        name = "base_contour.json" if vname == selected else "base_contour_alt_%s.json" % vname
        written[vname] = paths.write_json(os.path.join(OUT_JSON_DIR, name), obj)
        log("wrote %s (%s): back %d, head %d, inner_arc %d points" %
            (name, vname, len(segs_out["back"][0]), len(segs_out["head"][0]), len(segs_out["inner_arc"][0])))
        if vname == selected:
            segs_sel = segs_out
        # 各区間内で輪郭そのものの滑らかさを S8 方式で測る。
        s8 = {}
        for sname in ("back", "head", "inner_arc"):
            q, ql = segs_out[sname]
            r_all = s8_report(q, s8_spacing, F)
            r_vis = s8_report(q[np.isin(ql, (C.TRACED, C.BRIDGE))], s8_spacing, F)
            s8[sname] = {k: v for k, v in r_all.items() if not k.startswith("_")}
            s8[sname]["visible_part_only_max_abs_turn_deg"] = r_vis["max_abs_turn_deg"]
            if vname == selected:
                s8[sname]["_plot"] = (r_all["_points"], r_all["_turn"])
        metrics.setdefault("S8_own", {})[vname] = s8

    # 波頭の先端付近の旋回角（1 px 間隔の輪郭上）。
    turn_tip = {}
    for w_pct in (1.0, 2.0, 5.0, 10.0):
        w = int(round(w_pct * px_per_pct))
        turn_tip["%g_pct_h_each_side" % w_pct] = C.signed_turn_deg(full, max(i_t - w, 0), min(i_t + w, len(full) - 1), 4)
    metrics["head_tip_total_turn_deg"] = turn_tip

    # 低域通過の調査（統合処理向けの情報で、この輪郭自体には使わない）: 爪の領域だけで
    # S8 を満たすにはどれだけ平滑化が必要で、点がどれほど動くかを調べる。
    lowpass = {}
    seg_vis = {"back": full[:i_c + 1], "head": full[i_c:i_t + 1], "inner_arc_visible": full[i_t:i_end + 1]}
    for sg_pct in C.P(cfg, "lowpass_study_sigma_pct_h"):
        sg_px = float(F.pct_h_to_px(sg_pct))
        row = {}
        for sname, sp in seg_vis.items():
            lp = L.gaussian_smooth_open(sp, sg_px, 1.0)
            d_lp, _, _ = L.point_polyline_distance(sp[::4], lp)
            r_lp = L.s8_profile(lp, s8_spacing)
            row[sname] = {"own_S8_max_deg": r_lp["max_abs_deg"],
                          "n_ge_15deg": int((np.abs(r_lp["turn_deg"]) >= 15.0).sum()),
                          "shift_mean_pct_h": dpct_h(F, d_lp.mean()), "shift_p95_pct_h": dpct_h(F, np.percentile(d_lp, 95)),
                          "shift_max_pct_h": dpct_h(F, d_lp.max())}
        lowpass["sigma_%g_pct_h" % sg_pct] = row
    metrics["lowpass_study"] = lowpass

    # 元の輪郭から最終輪郭までの残差。
    resid = {}
    ref_tr = res["pts_refined"][res["lab"] == C.TRACED]
    pix_tr = res["pts_pixel"][res["lab_pixel"] == C.TRACED]
    for nm, rp in (("refined_unsmoothed_traced_vs_final", ref_tr), ("pixel_level_crack_vertices_vs_final", pix_tr)):
        d, sg, _ = L.point_polyline_distance(rp, pts)
        per = {}
        for sname, (a, b) in (("back", (0, i_c)), ("head", (i_c, i_t)), ("inner_arc", (i_t, i_end))):
            sel = (sg >= a) & (sg < b)
            per[sname] = stats(d[sel])
        resid[nm] = per
    # 橋: 除いた元の境界と最終輪郭の距離は残差ではないため、深さとして記録する。
    resid["bridges"] = {"n": len(res["bridges"]),
                        "max_removed_depth_px": float(max([b["max_depth_px"] for b in res["bridges"]] or [0.0])),
                        "sum_chord_px": float(sum(b["chord_px"] for b in res["bridges"]))}
    metrics["residuals"] = resid
    lab_counts = {}
    for sname in ("back", "head", "inner_arc"):
        ql = segs_sel[sname][1]
        lab_counts[sname] = {C.SOURCE_NAMES[c]: int((ql == c).sum()) for c in (0, 1, 2, 3)}
    metrics["point_counts_selected"] = lab_counts
    metrics["bridges"] = res["bridges"]

    # 球を転がす半径に対する感度。
    sens = {}
    alt_contours = {}
    for R2 in C.P(cfg, "open_radius_sensitivity_px"):
        r2 = contour_for_radius(masks, float(R2), cfg, refine=False)
        lm2 = landmarks_of(r2["pts"], cfg, F)
        tip2 = r2["pts"][lm2["i_tip"]]
        a_, b_ = lm2["i_crest"], lm2["i_deep"]
        d, _, _ = L.point_polyline_distance(r2["pts"][a_:b_], pts)
        sens["R=%g" % R2] = {"head_tip_px": tip2.tolist(), "head_tip_pct": pct(F, tip2),
                             "tip_shift_vs_selected_pct_h": [dpct_h(F, tip2[0] - tip[0]), dpct_h(F, tip2[1] - tip[1])],
                             "crest_to_deepest_distance_to_selected": stats(d),
                             "n_bridges": len(r2["bridges"])}
        alt_contours[R2] = r2["pts"][:lm2["i_deep"]]
    metrics["radius_sensitivity"] = sens

    # ---- 画像 -----------------------------------------------------------------------------
    lm_pts = [("crest", crest, (12, -34)), ("head tip", tip, (14, -30)), ("inner deepest", deep, (16, -10)),
              ("claw rightmost S6", claw, (14, 8)), ("inner arc visible end", pts[i_end], (16, -30)),
              ("completion end Z=0", comp_p1, (-10, 12))]
    spec_pts = [("S1 spec", spec_px["S1_crest"]), ("S2 spec", spec_px["S2_inner_arc_deepest"]),
                ("S6 spec", spec_px["S6_claw_rightmost"])]

    def annotate(v_img, to_view, lscale=2):
        for name_, p_, off in lm_pts:
            draw.label_point(v_img, to_view(p_), name_, "black", lscale, offset=off, kind="O", size=7, width=2.0, outline="white")
        for name_, p_ in spec_pts:
            draw.label_point(v_img, to_view(p_), name_, "navy", lscale, offset=(-12, 14), kind="x", size=8, width=2.0, outline="white")

    # 全体図（幅 1600 px の写しに描画）。
    ov_scale = 1600.0 / F.width_px
    ov = draw.resize(img_full, new_w=1600)
    tv = lambda p: np.asarray(p, dtype=np.float64) * ov_scale          # noqa: E731
    draw.hline(ov, y_trough * ov_scale, "orange", 1.5, dash=(10, 8))
    draw_contour(ov, tv, segs_sel, 1.0)
    altq, _ = L.resample_uniform(variants["white_body_outline" if selected == "sky_silhouette" else "sky_silhouette"][0][:420], 2.0)
    draw.polyline(ov, tv(altq), "purple", 2.0, dash=(8, 5))
    ax_v = np.array([math.cos(math.radians(tip_dir)), -math.sin(math.radians(tip_dir))])
    draw.line(ov, tv(ov_centroid - 420 * ax_v), tv(ov_centroid + 420 * ax_v), "black", 1.5, dash=(8, 6))
    draw.text(ov, tv(ov_centroid + 430 * ax_v)[0] + 6, tv(ov_centroid + 430 * ax_v)[1], "overhang axis %.1f deg" % tip_dir, "black", 2, bg="white")
    annotate(ov, tv, 2)
    draw.text(ov, tv((0, y_trough))[0] + 8, y_trough * ov_scale + 6, "Z=0 trough level of the frame (74.7%)", "orange", 2, bg="white")
    draw.text(ov, 8, 410, "purple dashed: other reading of the left end", "purple", 2, bg="white")
    legend(ov, 1150, 20, 2)
    imgio.save_png(os.path.join(OUT_IMG_DIR, "overlay_full_1600.png"), ov)

    crops = {
        "01_back_left_end": (0, 760, 560, 1110, 2), "02_back_mid": (450, 330, 1150, 830, 2),
        "03_crest": (1150, 150, 1750, 450, 2), "04_head_top_claws": (1550, 230, 2250, 830, 2),
        "05_head_tip": (1980, 640, 2380, 1140, 3), "06_head_underside": (1600, 800, 2300, 1200, 2),
        "07_inner_deepest": (1400, 950, 1800, 1450, 3), "08_inner_meets_near_wave": (1600, 1500, 2100, 1950, 3),
        "09_trough": (1750, 1700, 2450, 2050, 2), "10_armpit_underside_meets_inner_arc": (1560, 800, 1860, 1060, 4),
        "11_subpixel_check_crest": (1440, 205, 1520, 245, 16), "12_subpixel_check_inner_deepest": (1505, 1195, 1555, 1235, 16),
        "13_subpixel_check_gray_zone": (1665, 1585, 1745, 1625, 16),
    }
    other = "white_body_outline" if selected == "sky_silhouette" else "sky_silhouette"
    for cname, (cx0, cy0, cx1, cy1, sc) in crops.items():
        v = draw.View(img_full, cx0, cy0, cx1, cy1, scale=sc)
        m = 40

        def clipnan(p):
            p = np.asarray(p, dtype=np.float64).copy()
            out = (p[:, 0] < cx0 - m) | (p[:, 0] > cx1 + m) | (p[:, 1] < cy0 - m) | (p[:, 1] > cy1 + m)
            p[out] = np.nan
            return p

        tvv = lambda p, v=v: v.to_view(clipnan(np.atleast_2d(p))) if np.ndim(p) == 2 else v.to_view(p)   # noqa: E731
        draw.hline(v.img, v.to_view((0, y_trough))[1], "orange", 1.5, dash=(10, 8))
        draw_contour(v.img, tvv, segs_sel, 1.0, raw=raw)
        if cname.startswith("01"):
            draw.polyline(v.img, tvv(variants[other][0][:700]), "purple", 2.0, dash=(10, 6))
            draw.text(v.img, 10, v.img.shape[0] - 30, "purple dashed = other reading of the left end (%s)" % other, "purple", 2, bg="white")
        if cname.startswith("05") or cname.startswith("06"):
            draw.polyline(v.img, v.to_view(mids), "black", 1.5, dash=(6, 4))
            for tk in thick:
                draw.line(v.img, v.to_view(tk["top_point_px"]), v.to_view(tk["under_point_px"]), "blue", 1.5)
        if cname.startswith("04") or cname.startswith("05") or cname.startswith("06"):
            for b_ in res["bridges"]:
                for key in ("root_a_px", "root_b_px"):
                    p_ = np.array(b_[key])
                    if cx0 <= p_[0] <= cx1 and cy0 <= p_[1] <= cy1:
                        draw.marker(v.img, v.to_view(p_), "o", 3.5, "black")
        for name_, p_, off in lm_pts:
            if cx0 <= p_[0] <= cx1 and cy0 <= p_[1] <= cy1:
                draw.label_point(v.img, v.to_view(p_), name_, "black", 2, offset=off, kind="O", size=8, width=2.0, outline="white")
        for name_, p_ in spec_pts:
            if cx0 <= p_[0] <= cx1 and cy0 <= p_[1] <= cy1:
                draw.label_point(v.img, v.to_view(p_), name_, "navy", 2, offset=(-12, 14), kind="x", size=9, width=2.0, outline="white")
        draw.text(v.img, 10, 10, "%s  x=%d..%d y=%d..%d  x%d" % (cname, cx0, cx1, cy0, cy1, sc), "black", 2, bg="white")
        imgio.save_png(os.path.join(OUT_IMG_DIR, "crop_%s.png" % cname), v.img)

    # 診断用: 空の領域と墨。
    dbg = img.copy()
    draw.overlay_mask(dbg, masks["sky"], "red", 0.35)
    imgio.save_png(os.path.join(OUT_IMG_DIR, "debug_sky_region_1600.png"), draw.fit_width(dbg, 1600))
    # 診断用: 波頭における半径感度。
    v = draw.View(img_full, 1600, 230, 2400, 1230, scale=2)
    draw.polyline(v.img, v.to_view(raw), RAW_COLOR, 1.0)
    for R2, colr in zip(C.P(cfg, "open_radius_sensitivity_px"), ("green", "blue")):
        draw.polyline(v.img, v.to_view(alt_contours[R2]), colr, 1.5)
    draw.polyline(v.img, v.to_view(full[i_c:lm["i_deep"]]), "red", 2.0)
    draw.text(v.img, 10, 10, "rolling-ball radius: red = %g px (selected), green = %g, blue = %g, cyan = raw" %
              ((R,) + tuple(C.P(cfg, "open_radius_sensitivity_px"))), "black", 2, bg="white")
    imgio.save_png(os.path.join(OUT_IMG_DIR, "debug_radius_sensitivity_head.png"), v.img)

    # グラフ: 両変種の背面傾斜と独自の S8 旋回角。
    series = []
    for vname, colr in (("sky_silhouette", "red"), ("white_body_outline", "purple")):
        pr = s4[vname]["profile"]
        total = pr["s_pct_h"][-1]
        series.append({"label": vname + " fine", "x": [a - total for a in pr["s_pct_h"]], "y": pr["deg"], "color": colr, "width": 1.5})
        pr = s4[vname]["coarse_scale"]["profile"]
        total = pr["s_pct_h"][-1]
        series.append({"label": vname + " coarse", "x": [a - total for a in pr["s_pct_h"]], "y": pr["deg"], "color": colr,
                       "width": 3.0, "dash": (10, 6)})
    img_p = plot.line_plot(series, title="Back slope (S4) vs arclength before the crest", xlabel="arclength relative to crest [% of image height]",
                           ylabel="slope [deg]", size=(1400, 560),
                           hlines=[{"y": 25.0, "label": "spec 25"}, {"y": 47.0, "label": "spec 47"}, {"y": 8.0, "label": "spec 8"}])
    imgio.save_png(os.path.join(OUT_IMG_DIR, "plot_S4_back_slope.png"), img_p)
    series = []
    off = 0.0
    spans = []
    for sname in ("back", "head", "inner_arc"):
        q, turn = metrics["S8_own"][selected][sname].pop("_plot")
        xs = off + np.arange(1, len(turn) + 1) * (s8_spacing / px_per_pct)
        series.append({"label": sname, "x": xs.tolist(), "y": np.abs(turn).tolist(), "color": SEG_COLORS[sname] if sname != "inner_arc" else "green"})
        off = xs[-1] + 1.0 if len(xs) else off
    img_p = plot.line_plot(series, title="Own smoothness of candidate B (S8 style): |tangent change| per 1% step, within each segment",
                           xlabel="arclength [% of image height]", ylabel="|turn| [deg]", size=(1400, 560),
                           hlines=[{"y": 15.0, "label": "S8 limit 15"}])
    imgio.save_png(os.path.join(OUT_IMG_DIR, "plot_S8_own_turn.png"), img_p)

    metrics["written"] = written
    metrics["runtime_s"] = time.perf_counter() - t_start
    paths.write_json(os.path.join(OUT_IMG_DIR, "metrics_b.json"), metrics)

    # ---- コンソールの要約 ---------------------------------------------------------------------
    log("S1 crest px (%.1f, %.1f) pct (%.2f, %.2f)  d = (%+.2f, %+.2f) %% of image height; plateau x %.0f..%.0f" %
        (crest[0], crest[1], s1["measured_pct"][0], s1["measured_pct"][1], s1["dx_pct_h"], s1["dy_pct_h"],
         pts[ca, 0], pts[cb, 0]))
    log("S2 deepest px (%.1f, %.1f) pct (%.2f, %.2f)  d = (%+.2f, %+.2f), dist %.2f" %
        (deep[0], deep[1], s2["measured_pct"][0], s2["measured_pct"][1], s2["dx_pct_h"], s2["dy_pct_h"], s2["dist_pct_h"]))
    log("S3 sea top edge y = %.1f (%.2f %%), height if trough = %.2f %% (spec 66)" %
        (sea_top, s3["sea_top_edge_top_pct"], s3["height_pct_if_sea_top_edge_is_trough"]))
    for vname in variants:
        for scale_name, a in (("fine", s4[vname]), ("coarse", s4[vname]["coarse_scale"])):
            log("S4 [%s, %s sigma %.0f px] left end %.1f, min %.1f, max %.1f at x=%.0f, before crest %s, flatten-violation %.1f" %
                (vname, scale_name, a["smoothing_sigma_px"], a["left_end_deg"], a["min_before_steepest_deg"], a["mid_max_deg"],
                 a["mid_max_at_px"][0], {k: round(v, 1) for k, v in a["before_crest_deg"].items()},
                 a["flattens_towards_crest_max_increase_deg"]))
            log("     slope table: %s" % [(round(r_["x_px"]), round(r_["slope_deg"], 1)) for r_ in a["slope_table"]])
    log("S5 head tip px (%.1f, %.1f) pct (%.2f, %.2f) H (%.3f, %.3f) overhang-axis dir %.1f deg; alternatives %s" %
        (tip[0], tip[1], s5["head_tip_pct"][0], s5["head_tip_pct"][1], tipH[0], tipH[1], tip_dir,
         {k: round(v, 1) for k, v in s5["direction_alternatives_deg"].items()}))
    log("S6 claw rightmost px (%.1f, %.1f) pct (%.2f, %.2f)  d = (%+.2f, %+.2f)" %
        (claw[0], claw[1], s6["measured_pct"][0], s6["measured_pct"][1], s6["dx_pct_h"], s6["dy_pct_h"]))
    for tk in thick:
        log("thickness at %g %% H behind tip: pair %.1f %% H, min-dist %.1f / %.1f %% H" %
            (tk["arclength_behind_tip_pct_H"], tk["pair_distance_pct_H"], tk["top_point_to_underside_min_pct_H"],
             tk["under_point_to_topside_min_pct_H"]))
    for sname in ("back", "head", "inner_arc"):
        a = metrics["S8_own"][selected][sname]
        log("S8 own [%s] max %.1f deg, p95 %.1f, n>=15: %d of %d; worst at %s" %
            (sname, a["max_abs_turn_deg"], a["p95_abs_turn_deg"], a["n_vertices_ge_15deg"], a["n_samples"],
             [round(v) for v in a["worst"][0]["px"]] if a["worst"] else None))
    log("head tip total turn: %s" % {k: round(v, 1) for k, v in turn_tip.items()})
    for k_, row_ in lowpass.items():
        log("lowpass %s: %s" % (k_, {n_: (round(v_["own_S8_max_deg"], 1), v_["n_ge_15deg"], round(v_["shift_mean_pct_h"], 2),
                                         round(v_["shift_max_pct_h"], 2)) for n_, v_ in row_.items()}))
    for nm, per in resid.items():
        if nm != "bridges":
            log("residual %s: %s" % (nm, {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in per.items()}))
    log("bridges: %s" % resid["bridges"])
    log("claws removed: %s" % metrics_claws)
    log("radius sensitivity: %s" % {k: v["tip_shift_vs_selected_pct_h"] for k, v in sens.items()})
    log("alt (white body) left frame edge at %s, join %s" % (alt_info["band_lower_edge_at_left_frame_px"], alt_info["join_px"]))
    log("inner arc visible end px %s; completion end %s" % (np.round(pts[i_end], 1).tolist(), np.round(comp_p1, 1).tolist()))
    log("runtime %.1f s" % metrics["runtime_s"])
    bootstrap.finish(True, "method_b_run")


if __name__ == "__main__":
    main()
