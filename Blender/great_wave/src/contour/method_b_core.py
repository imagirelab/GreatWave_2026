"""輪郭線に基づく方法Bの基準輪郭処理。docs/records/step1_contour_b.md を参照。

処理段階
--------
A  墨のマスク（青みと輝度のブラックトップハット）から隙間を閉じた空の領域を得る。
   空の領域は塗りのためではなく、輪郭の外縁の順番を求めるために使う。
B  爪を含む元の輪郭線を、空の領域の順序付き画素間境界として求める。
C  波本体側から半径 R の球を転がす（オープニング）。幅が 2R 未満の突起を爪とみなす。
   結果の点を元の輪郭上の 'traced' と爪の根元をまたぐ橋に分け、橋を根元間の弦で置き換える。
D  'traced' の点を局所法線方向に1画素未満の精度で合わせ、墨の輪郭の外縁を求める。
E  平滑化（traced は σ=3 px、橋は σ=10 px）、特徴点、内側の弧の終端、
   Z=0 への補完、区間分け、2 px の等間隔再標本化。
"""
import math

import numpy as np

from . import method_b_lib as L

TRACED, BRIDGE, COMPLETED_OCCLUDED, COMPLETED_OTHER = 0, 1, 2, 3
SOURCE_NAMES = {TRACED: "traced", BRIDGE: "claw_root_bridge",
                COMPLETED_OCCLUDED: "completed_occluded", COMPLETED_OTHER: "completed_other"}


def P(cfg, name):
    return cfg[name]["value"]


# ------------------------------------------------------------------ 段階 A
def build_masks(rgb_roi, cfg, log=None):
    """作業領域の uint8 画像 rgb_roi (h, w, 3) から各種マスクを求める。

    D と Lm（ぼかした特徴量）、ink、sky（隙間を閉じた連結空領域）、
    W (= ~sky) を含む辞書を返す。
    """
    r = int(P(cfg, "pre_blur_r"))
    D = L.box_blur(L.blueness(rgb_roi), r)
    Lm = L.box_blur(L.luma(rgb_roi), r)
    bth = L.black_tophat(Lm, int(P(cfg, "ink_tophat_k")))
    bg = L.box_blur(Lm, int(P(cfg, "ink_tophat_bg_blur_r")))
    ink = (D > P(cfg, "ink_blueness_thr")) | ((bth > P(cfg, "ink_tophat_thr")) & (bg > P(cfg, "ink_tophat_bg_min")))
    cand = ~ink
    g = int(P(cfg, "gap_close_px"))
    dist = L.edt_capped(cand, g + 2)
    seed = tuple(int(v) for v in P(cfg, "sky_seed_xy"))
    core, n_it = L.flood_fill(dist > g, [seed])
    sky = L.geodesic_dilate(core, cand, g + 2)
    if log:
        log("stage A: flood iterations %d, sky px %d" % (n_it, int(sky.sum())))
    a = rgb_roi.astype(np.float32)
    GR = L.box_blur(a[:, :, 1] - a[:, :, 0], r)      # G - R: 明るい青緑の筋は +22、白波は -4、空は -13。
    return {"D": D, "Lm": Lm, "GR": GR, "ink": ink, "sky": sky, "W": ~sky}


def left_edge_start(region_sky):
    """空を左に置く境界追跡の開始角を返す。

    0列目の上端から連結する空画素の最下点、その下の頂点を選ぶ。
    """
    col = region_sky[:, 0]
    if not col[0]:
        raise RuntimeError("column 0 does not start in the sky")
    yb = int(np.argmin(col)) - 1 if not col.all() else len(col) - 1
    return (0, yb + 1)


def cut_at_stop(path, stop_xy):
    idx = np.nonzero((path[:, 0] > stop_xy[0]) & (path[:, 1] > stop_xy[1]))[0]
    if len(idx) == 0:
        raise RuntimeError("trace never reached the stop box %r" % (stop_xy,))
    return path[:idx[0] + 1]


def raw_silhouette(masks, cfg):
    sky = masks["sky"]
    loop = L.trace_cracks(sky, left_edge_start(sky), 0)
    return cut_at_stop(loop, P(cfg, "raw_trace_stop_xy"))


# ------------------------------------------------------------------ 段階 C
def opened_boundary(masks, radius, cfg):
    """本体側から半径 `radius` の球を転がしてオープニングを求める。

    境界の整数頂点列 path (N, 2) と、各段階の空側画素から真の空までの距離
    dev (N-1,) を返す。
    """
    W = masks["W"]
    pad = int(math.ceil(radius)) + 3
    # 枠の端を波の境界と誤認しないよう、端を複製して余白を設ける。
    Wo = L.opening(np.pad(W, pad, mode="edge"), radius)[pad:-pad, pad:-pad]
    so = ~Wo
    loop = L.trace_cracks(so, left_edge_start(so), 0)
    path = cut_at_stop(loop, P(cfg, "raw_trace_stop_xy"))
    d_sky = L.edt_capped(W, int(math.ceil(radius)) + 2)        # 空画素は 0。
    left = L.crack_left_pixels(path)
    h, w = W.shape
    lx = np.clip(left[:, 0], 0, w - 1)
    ly = np.clip(left[:, 1], 0, h - 1)
    return path, d_sky[ly, lx]


def _runs(flags):
    """一次元真偽配列の連続区間を (始点, 排他的終点, 値) で返す。"""
    out = []
    n = len(flags)
    i = 0
    while i < n:
        j = i
        while j < n and flags[j] == flags[i]:
            j += 1
        out.append((i, j, bool(flags[i])))
        i = j
    return out


def label_and_bridge(path, dev, cfg):
    """開いた境界の各頂点へ TRACED / BRIDGE ラベルを付け、橋を爪の根元間の弦に置換する。

    折れ線 pts (M, 2)、labels (M,)、橋の情報を含む辞書のリストを返す。
    """
    tol = P(cfg, "traced_tol_px")
    minor = P(cfg, "minor_bridge_max_dev_px")
    step_traced = dev <= tol
    n = len(path)
    vt = np.zeros(n, bool)
    vt[:-1] |= step_traced
    vt[1:] |= step_traced
    # 小さな橋は追跡済みとして再分類する。
    for a, b, val in _runs(vt):
        if not val:
            lo, hi = max(a - 1, 0), min(b, len(dev))
            if dev[lo:hi].max() <= minor:
                vt[a:b] = True
    pts, labels, bridges = [], [], []
    runs = _runs(vt)
    for k, (a, b, val) in enumerate(runs):
        if val:
            pts.append(path[a:b].astype(np.float64))
            labels.append(np.full(b - a, TRACED, np.int8))
        else:
            if a == 0 or b == n:
                # 経路の端の橋は、開いた境界そのものを残す。
                pts.append(path[a:b].astype(np.float64))
                labels.append(np.full(b - a, BRIDGE, np.int8))
                continue
            p0 = path[a - 1].astype(np.float64)
            p1 = path[b].astype(np.float64)
            length = float(np.hypot(*(p1 - p0)))
            m = max(int(round(length)) - 1, 0)
            if m > 0:
                t = (np.arange(1, m + 1) / float(m + 1))[:, None]
                pts.append(p0[None] * (1 - t) + p1[None] * t)
                labels.append(np.full(m, BRIDGE, np.int8))
            lo, hi = max(a - 1, 0), min(b, len(dev))
            bridges.append({"root_a_px": [float(p0[0]), float(p0[1])], "root_b_px": [float(p1[0]), float(p1[1])],
                            "chord_px": length, "opened_arc_px": int(b - a),
                            "max_depth_px": float(dev[lo:hi].max())})
    return np.vstack(pts), np.concatenate(labels), bridges


def resample_labelled(p, lab, spacing):
    """ラベルを引き継ぎながら弧長を等間隔で再標本化する。

    両隣の入力点がともに TRACED の場合だけ新しい点も TRACED とし、
    それ以外では二点のラベルコードの大きい方を採用する。
    """
    s = L.arclength(p)
    keep = np.concatenate([[True], np.diff(s) > 1e-9])
    p, lab, s = p[keep], lab[keep], s[keep]
    total = s[-1]
    n = int(math.floor(total / spacing + 1e-9))
    t = np.arange(n + 1) * spacing
    if total - t[-1] > 1e-6:
        t = np.concatenate([t, [total]])
    q = np.stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])], axis=1)
    j = np.clip(np.searchsorted(s, t, side="right") - 1, 0, len(s) - 2)
    on_node = np.abs(s[j] - t) < 1e-9
    lab_new = np.where(on_node, lab[j], np.maximum(lab[j], lab[j + 1]))
    lab_new[-1] = lab[-1]
    return q, lab_new.astype(np.int8)


# ------------------------------------------------------------------ 段階 D
def running_median(a, win):
    win = int(win) | 1
    r = win // 2
    p = np.pad(a, r, mode="edge")
    idx = np.arange(len(a))[:, None] + np.arange(win)[None, :]
    return np.median(p[idx], axis=1)


def refine_traced(pts, labels, masks, cfg, field_sign=+1.0):
    """TRACED の点を画素未満の精度で輪郭の外縁に合わせる。

    白い本体の変種では field_sign = -1 を使う（左の青から右の白への境界）。
    補正した点、情報辞書、法線を返す。
    """
    sig = P(cfg, "stair_sigma_px")
    q = L.gaussian_smooth_open(pts, sig, 1.0)
    normals, _ = L.local_normals(q, int(P(cfg, "normal_half_window_px")))
    kw = dict(search=P(cfg, "refine_search_px"), step=P(cfg, "refine_step_px"),
              outer=tuple(P(cfg, "refine_outer_px")), inner_max=P(cfg, "refine_inner_max_px"),
              level=P(cfg, "refine_level"), min_contrast=P(cfg, "refine_min_contrast"))
    Lm, D = masks["Lm"], masks["D"]
    if field_sign > 0:
        # 局所的な空の輝度で使用する特徴量を選ぶ。
        o0, o1 = P(cfg, "refine_outer_px")
        offs = np.arange(o0, o1 + 1e-9, 1.0)
        xs = q[:, 0][:, None] - normals[:, 0][:, None] * offs[None]
        ys = q[:, 1][:, None] - normals[:, 1][:, None] * offs[None]
        sky_l = np.median(L.bilinear(Lm, xs, ys), axis=1)
        use_l = sky_l >= P(cfg, "refine_luma_sky_min")
        rl, okl, shl, cl = L.refine_edge(255.0 - Lm, q, normals, **kw)
        rd, okd, shd, cd = L.refine_edge(D, q, normals, **kw)
        ok = np.where(use_l, okl, okd)
        shift = np.where(use_l, shl, shd)
    else:
        rd, ok, shift, cd = L.refine_edge(-D, q, normals, **kw)
        use_l = np.zeros(len(q), bool)
    traced = labels == TRACED
    good = ok & traced
    shift_f = np.zeros(len(q))
    if good.sum() >= 2:
        idx = np.arange(len(q))
        shift_i = np.interp(idx, idx[good], shift[good])
        shift_i = running_median(shift_i, P(cfg, "refine_shift_median_win"))
        shift_f = np.where(traced, shift_i, 0.0)
    out = q + normals * shift_f[:, None]
    # 橋は補正した隣接点間の直線弦にする。
    for a, b, val in _runs(labels != TRACED):
        if val and a > 0 and b < len(out):
            p0, p1 = out[a - 1], out[b]
            t = (np.arange(1, b - a + 1) / float(b - a + 1))[:, None]
            out[a:b] = p0[None] * (1 - t) + p1[None] * t
    info = {"n_traced": int(traced.sum()), "n_refined_ok": int(good.sum()),
            "frac_luma_field": float(use_l[traced].mean()) if traced.any() else 0.0,
            "shift_mean_px": float(shift_f[traced].mean()) if traced.any() else 0.0,
            "shift_abs_mean_px": float(np.abs(shift_f[traced]).mean()) if traced.any() else 0.0,
            "shift_abs_max_px": float(np.abs(shift_f[traced]).max()) if traced.any() else 0.0}
    return out, info, normals


# ------------------------------------------------------------------ 段階 E
def final_smooth(pts, labels, cfg):
    """1 px 間隔の点を、追跡部の弱い平滑化と橋の強い平滑化を混ぜて処理する。"""
    st, sb, sl = P(cfg, "sigma_traced_px"), P(cfg, "sigma_bridge_px"), P(cfg, "sigma_label_blend_px")
    a = L.gaussian_smooth_open(pts, st, 1.0)
    b = L.gaussian_smooth_open(pts, sb, 1.0)
    ind = (labels == BRIDGE).astype(np.float64)
    w = L.gaussian_smooth_open(np.stack([ind, ind], axis=1), sl, 1.0, fix_ends=False)[:, 0]
    w = np.clip(w, 0.0, 1.0)[:, None]
    out = a * (1 - w) + b * w
    out[0], out[-1] = pts[0], pts[-1]
    return out


def plateau_midpoint(pts, values, i_ext, tol, sign):
    """i_ext の周囲で sign*(values - values[i_ext]) <= tol を満たす連続区間を求める。

    弧長上の中点 i_mid と区間の両端 i_a、i_b を返す。
    """
    n = len(values)
    ref = values[i_ext]
    a = i_ext
    while a > 0 and sign * (values[a - 1] - ref) <= tol:
        a -= 1
    b = i_ext
    while b < n - 1 and sign * (values[b + 1] - ref) <= tol:
        b += 1
    s = L.arclength(pts[a:b + 1])
    i_mid = a + int(np.argmin(np.abs(s - 0.5 * s[-1])))
    return i_mid, a, b


def inner_arc_end(pts, normals_in, i_from, masks, cfg):
    """i_from 以降で、境界の波側に青色が連続して現れなくなる最初の番号を返す。

    連続標本数は inner_end_min_run_px で指定する。
    """
    offs = np.asarray(P(cfg, "inner_end_inside_offsets_px"), dtype=np.float64)
    xs = pts[:, 0][:, None] + normals_in[:, 0][:, None] * offs[None]
    ys = pts[:, 1][:, None] + normals_in[:, 1][:, None] * offs[None]
    blue = np.median(L.bilinear(masks["D"], xs, ys), axis=1) > P(cfg, "ink_blueness_thr")
    run = int(P(cfg, "inner_end_min_run_px"))
    n = len(pts)
    i = i_from
    while i < n - run:
        if not blue[i:i + run].any():
            return i, blue
        i += 1
    return n - 1, blue


def end_tangent(pts, fit_len):
    """約 1 px 間隔の折れ線の終端で単位接線を求める。

    最後の fit_len px について x(s)、y(s) を二次式で最小二乗近似し、s = 0 の導関数を使う。
    """
    s = L.arclength(pts)
    sel = s >= s[-1] - fit_len
    ss = s[sel] - s[-1]
    cx = np.polyfit(ss, pts[sel, 0], 2)
    cy = np.polyfit(ss, pts[sel, 1], 2)
    t = np.array([cx[1], cy[1]])
    return t / np.hypot(*t)


def parabola_to_level(p0, t0, y_level, spacing=1.0, run_frac=1.0):
    """二次ベジェ曲線 P0 - C - P1 を y_level まで引く。

    C は P0 を通る接線と y = y_level の交点、P1 は
    C + (run_frac * |C - P0|, 0)。P0 の接線は t0、P1 では水平となる。
    run_frac = 1 で対称な放物線となり、小さい値ほど接線に近い経路から
    谷の高さへ急に向きを変える。
    """
    if t0[1] <= 0.05 or p0[1] >= y_level:
        raise RuntimeError("parabola_to_level: end tangent does not descend towards the level")
    lam = (y_level - p0[1]) / t0[1]
    c = p0 + lam * t0
    p1 = np.array([c[0] + run_frac * lam, y_level])
    n = max(8, int(4 * lam / spacing))
    t = np.linspace(0.0, 1.0, n + 1)[:, None]
    curve = (1 - t) ** 2 * p0[None] + 2 * (1 - t) * t * c[None] + t ** 2 * p1[None]
    q, _ = L.resample_uniform(curve, spacing)
    return q, c, p1


def hidden_completion(p0, t0, y_level, sky, fracs, skip_px=8.0):
    """補完曲線が見えている空へ入らない最大の run_frac を `fracs` から選ぶ。

    曲線は近くの波に隠れるか谷の水面にある想定。曲線、制御点 c、終点 p1、
    run_frac、選択した曲線の空領域に入った標本数を返す。
    """
    h, w = sky.shape
    best = None
    for f in fracs:
        curve, c, p1 = parabola_to_level(p0, t0, y_level, 1.0, f)
        s = L.arclength(curve)
        q = curve[s >= skip_px]
        xi = np.clip(np.floor(q[:, 0]).astype(np.int64), 0, w - 1)
        yi = np.clip(np.floor(q[:, 1]).astype(np.int64), 0, h - 1)
        n_sky = int(sky[yi, xi].sum())
        if best is None or n_sky < best[4]:
            best = (curve, c, p1, float(f), n_sky)
        if n_sky == 0:
            break
    return best


def overhang_axis(contour, i_deep, i_tip, shape_hw, polygon_mask_fn):
    """波が張り出した部分の主軸を求める。

    内側の弧の最深点より右かつ上にある基準輪郭の領域を、その点を通る鉛直線で閉じる。
    方向（度、0 は +X、負は水平より下向き）、重心（画素）、多角形、
    伸長率 sqrt(l1 / l2)、領域の画素数を返す。
    """
    xd = contour[i_deep, 0]
    top = contour[:i_tip + 1, 0]
    cross = np.nonzero((top[:-1] < xd) & (top[1:] >= xd))[0]
    if len(cross) == 0:
        raise RuntimeError("overhang_axis: the top side never crosses the plumb line of the deepest point")
    i0 = int(cross[-1])
    a, b = contour[i0], contour[i0 + 1]
    t = (xd - a[0]) / (b[0] - a[0])
    start = a + t * (b - a)
    poly = np.vstack([start[None], contour[i0 + 1:i_deep + 1]])
    mask = polygon_mask_fn(shape_hw, poly)
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs + 0.5, ys + 0.5], axis=1)
    c = pts.mean(axis=0)
    cov = np.cov((pts - c).T)
    evals, evecs = np.linalg.eigh(cov)
    v = evecs[:, 1]
    if v[0] < 0:
        v = -v
    ang = float(np.degrees(np.arctan2(-v[1], v[0])))
    return ang, c, poly, float(np.sqrt(evals[1] / max(evals[0], 1e-9))), int(mask.sum())


def slope_profile(back_pts, sigma_px):
    """平滑化した背面に沿う傾斜角を度数で測る（正は頂上へ上昇）。

    back_pts は約 1 px 間隔。弧長 s、線分の中点での角度、平滑化した点を返す。
    """
    q = L.gaussian_smooth_open(back_pts, sigma_px, 1.0)
    s = L.arclength(q)
    ang = L.tangent_angles_deg(q)
    return 0.5 * (s[1:] + s[:-1]), ang, q


def signed_turn_deg(pts, i0, i1, stride):
    """標本 i0 から i1 までの符号付き接線旋回角を累積して返す（弦の間隔は `stride`）。"""
    idx = np.arange(i0, i1 + 1, stride)
    if len(idx) < 3:
        return 0.0
    ang = L.tangent_angles_deg(pts[idx])
    return float(L.wrap_deg(np.diff(ang)).sum())
