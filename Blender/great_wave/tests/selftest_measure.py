"""合成波を使ったシルエット・輪郭測定ライブラリの自己検証。無画面で実行する。
対象は gw.raster、gw.silhouette、gw.profile_metrics。

  & ".../tools/run_blender.ps1" tests/selftest_measure.py [-ScriptArgs '--quick'|'--skip-cycles'|'--skip-perf']

出力：results/step1_prepare/measure/ に報告JSON、重ね合わせ、局所拡大、失敗例、定義図を保存する。
全項目が合格した場合のみ終了コード0。
"""
import argparse
import math
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
_FIX = os.path.join(_HERE, "fixtures")
if _FIX not in sys.path:
    sys.path.insert(0, _FIX)

from gw import bootstrap, paths, frame, imgio, draw, plot, raster, silhouette, profile_metrics as pm  # noqa: E402
import make_synthetic_wave as msw  # noqa: E402

log = bootstrap.log
OUT = paths.step1_dir("measure")
CHECKS = []
REPORT = {"checks": CHECKS}

TOL_POS_PCT_H = 0.2      # task requirement: 0.2 % of image height
TOL_ANG_DEG = 1.0        # task requirement: 1 degree


def check(name, ok, detail=""):
    CHECKS.append({"name": name, "pass": bool(ok), "detail": str(detail)})
    log("%s %s %s" % ("ok  " if ok else "FAIL", name, detail))
    return bool(ok)


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


# ============================================================================ A. rasteriser
def test_rasteriser():
    rng = np.random.default_rng(7)
    w, h = 113, 71
    worst = 0
    cases = ["random", "integer vertices", "vertices on pixel centres", "degenerate + repeated",
             "slivers", "huge", "tiny"]
    for ci, label in enumerate(cases):
        tri = rng.uniform(-25, 140, size=(80, 3, 2))
        if ci == 1:
            tri = np.round(tri)
        elif ci == 2:
            tri = np.round(tri) + 0.5
        elif ci == 3:
            tri[:25, 2] = tri[:25, 0] + 0.37 * (tri[:25, 1] - tri[:25, 0])
            tri[25:40, 1] = tri[25:40, 0]
            tri[40:45] = tri[40:45, :1]
        elif ci == 4:
            tri = rng.uniform(5, 100, size=(80, 1, 2)) + rng.uniform(-15, 15, size=(80, 3, 2)) * [1.0, 0.12]
        elif ci == 5:
            tri = rng.uniform(-3000, 3000, size=(80, 3, 2))
        elif ci == 6:
            tri = rng.uniform(5, 100, size=(80, 1, 2)) + rng.uniform(-0.8, 0.8, size=(80, 3, 2))
        a = raster.rasterize_triangles(tri, w, h)
        b = raster.brute_force_mask(tri, w, h)
        nd = int((a != b).sum())
        worst = max(worst, nd)
        check("ラスターと総当たりが一致［%s］" % label, nd == 0, "相違 %d px、集合 %d px" % (nd, int(a.sum())))
    # 辺を共有すれば、頂点順が混在し内部頂点が揺れても裂け目は生じない。
    gx, gy = np.meshgrid(np.linspace(3.3, 190.7, 40), np.linspace(2.1, 140.9, 30))
    gx = gx + rng.uniform(-1.5, 1.5, gx.shape)
    gy = gy + rng.uniform(-1.5, 1.5, gy.shape)
    gx[:, 0], gx[:, -1], gy[0, :], gy[-1, :] = 3.3, 190.7, 2.1, 140.9
    P = np.stack([gx, gy], -1)
    t1 = np.stack([P[:-1, :-1], P[:-1, 1:], P[1:, 1:]], 2).reshape(-1, 3, 2)
    t2 = np.stack([P[:-1, :-1], P[1:, 1:], P[1:, :-1]], 2).reshape(-1, 3, 2)
    m = raster.rasterize_triangles(np.concatenate([t1, t2[:, ::-1]]), 200, 150)
    xs, ys = np.arange(200) + 0.5, np.arange(150) + 0.5
    ref = ((xs >= 3.3) & (xs <= 190.7))[None, :] & ((ys >= 2.1) & (ys <= 140.9))[:, None]
    check("辺を共有する三角形に裂け目がない", int((m != ref).sum()) == 0, "相違 %d px" % int((m != ref).sum()))
    # 有限でない入力、空入力、真横から見るシート
    tri = rng.uniform(0, 100, size=(10, 3, 2))
    tri[3, 1, 0] = np.nan
    tri[5, 0, 1] = np.inf
    m, info = raster.rasterize_triangles(tri, w, h, return_info=True)
    check("有限でない三角形を除外する", info["n_nonfinite"] == 2 and np.isfinite(m.sum()), str(info))
    m = raster.rasterize_triangles(np.zeros((0, 3, 2)), w, h)
    check("空の三角形一覧", m.shape == (h, w) and not m.any())
    sheet = np.array([[[10.2, 10.0], [90.7, 50.0], [50.45, 30.0]]])          # exactly collinear = edge-on
    m0 = raster.rasterize_triangles(sheet, w, h)
    m1 = raster.rasterize_triangles(sheet, w, h, thin="line")
    check("真横から見た三角形：thin='skip' は無描画、thin='line' は線を描く",
          int(m0.sum()) <= 2 and 60 < int(m1.sum()) < 200, "skip %d px, line %d px" % (int(m0.sum()), int(m1.sum())))
    # 決定性
    tri = rng.uniform(0, 100, size=(500, 3, 2))
    a = raster.rasterize_triangles(tri, w, h)
    b = raster.rasterize_triangles(tri[::-1, ::-1], w, h, max_spans=300)
    check("決定性（順序・頂点方向・分割に依存しない）", np.array_equal(a, b))
    # 厳密な境界交点：円盤の細かい三角形扇形と解析的な円を比較
    cx, cy, R = 50.23, 35.71, 30.3
    a = np.linspace(0, 2 * np.pi, 1441)
    ring = np.stack([cx + R * np.cos(a), cy + R * np.sin(a)], 1)
    fan = np.stack([np.repeat([[cx, cy]], 1440, 0), ring[:-1], ring[1:]], 1)
    md, ed, _inf = raster.rasterize_exact(fan, w, h)
    errs = []
    for j in range(h):
        cols = np.nonzero(md[j])[0]
        if cols.size:
            half = math.sqrt(max(R * R - (j + 0.5 - cy) ** 2, 0.0))
            errs.append(abs(ed.crossing("right", j, int(cols[-1])) - (cx + half)))
            errs.append(abs(ed.crossing("left", j, int(cols[0])) - (cx - half)))
    for i in range(w):
        rws = np.nonzero(md[:, i])[0]
        if rws.size:
            half = math.sqrt(max(R * R - (i + 0.5 - cx) ** 2, 0.0))
            errs.append(abs(ed.crossing("top", int(rws[0]), i) - (cy - half)))
            errs.append(abs(ed.crossing("bottom", int(rws[-1]), i) - (cy + half)))
    check("rasterize_exact：円盤の境界交点は厳密で、±0.5 px に丸めない", max(errs) < 2e-3,
          "max |error| %.2e px over %d crossings (float32 storage + 1440-gon chord error)" % (max(errs), len(errs)))
    # 画素中心を覆わなくても、被覆領域に接する細片は交点を延長する。
    tri2 = np.array([[[10.0, 10.0], [20.6, 10.0], [10.0, 30.0]], [[20.6, 10.0], [20.6, 30.0], [10.0, 30.0]],
                     [[20.6, 10.0], [20.9, 10.0], [20.6, 30.0]], [[20.9, 10.0], [20.9, 30.0], [20.6, 30.0]]])
    m2_, e2_, _ = raster.rasterize_exact(tri2, 40, 40)
    c_ = e2_.crossing("right", 20, 20)
    check("rasterize_exact：二つの画素中心の間の細片も連結する", abs(c_ - 20.9) < 1e-4, "交点 %.4f（期待値 20.9）" % c_)
    # 水面板の規則
    mm = np.zeros((10, 4), bool)
    raster.fill_below(mm, 6.5)
    check("fill_below：中心が y 以上の行を充填する", mm[:, 0].tolist() == [False] * 6 + [True] * 4)


# ============================================================================ B. mask utilities
def test_mask_utils():
    rng = np.random.default_rng(3)
    mm = rng.uniform(size=(60, 80)) > 0.55
    for conn in (4, 8):
        comp = raster.label_components(mm, conn)
        lab = -np.ones(mm.shape, int)
        k = 0
        for j in range(mm.shape[0]):
            for i in range(mm.shape[1]):
                if mm[j, i] and lab[j, i] < 0:
                    st = [(j, i)]
                    lab[j, i] = k
                    while st:
                        y, x = st.pop()
                        for dy in (-1, 0, 1):
                            for dx in (-1, 0, 1):
                                if (dy or dx) and (conn == 8 or dy == 0 or dx == 0):
                                    yy, xx = y + dy, x + dx
                                    if 0 <= yy < mm.shape[0] and 0 <= xx < mm.shape[1] and mm[yy, xx] and lab[yy, xx] < 0:
                                        lab[yy, xx] = k
                                        st.append((yy, xx))
                    k += 1
        li = comp.label_image()
        pairs = set(zip(li[mm].tolist(), lab[mm].tolist()))
        areas_ok = all(int(comp.area[a - 1]) == int((lab == b).sum()) for a, b in pairs)
        check("連結成分（%d 近傍）が塗りつぶしと一致" % conn, len(pairs) == k == comp.n and areas_ok,
              "n=%d" % comp.n)
    big = np.zeros((400, 600), bool)
    big[250:, :] = True
    big[60:250, 100:400] = True
    big[100:150, 150:250] = False          # hole 50 x 100
    big[5:8, 5:8] = True                   # speck
    lc, inf = raster.largest_component(big)
    filled, holes, hinf = raster.fill_holes(lc)
    check("最大成分の抽出で微小領域を除く", inf["n_components"] == 2 and inf["removed_area_px"] == 9, str(inf))
    check("fill_holes は囲まれた穴を検出する", hinf["n_holes"] == 1 and hinf["hole_area_px"] == 5000
          and hinf["largest_hole_bbox"] == [150, 100, 250, 150], str(hinf))


# ============================================================================ C. metrics on analytic curves
def clipped_reference_curve(t, F, ds=2e-4):
    """密な解析的主断面を原画の画角で切り、静水面に沿う区間を追加する。
    理想的な輪郭抽出が返す形に相当する。"""
    dense, _ids, info = msw.profile_points(t, dense_ds=ds)
    C = pm.Curve(dense)
    x = C.pts[:, 0]
    i0 = int(np.nonzero(x >= F.x_left)[0][0])
    s_left = float(np.interp(F.x_left, x[i0 - 1:i0 + 1], C.s[i0 - 1:i0 + 1])) if i0 > 0 else 0.0
    # 右端：最深点以後の前面は X に単調。画面右端で切る。
    s_right = C.length
    beyond = np.nonzero((x > F.x_right) & (C.s > s_left))[0]
    if beyond.size:
        j = int(beyond[0])
        s_right = float(np.interp(F.x_right, x[j - 1:j + 1], C.s[j - 1:j + 1]))
    pts = C.slice_pts(s_left, s_right)
    if pts[-1, 0] < F.x_right - 1e-6:
        xs = np.arange(pts[-1, 0] + ds, F.x_right, 5 * ds)
        pts = np.concatenate([pts, np.stack([xs, np.zeros_like(xs)], 1), [[F.x_right, 0.0]]])
    return pts, info


def test_metrics_analytic(F):
    # 直線：傾斜と theta
    xs = np.linspace(-0.8, 0.0, 400)
    back = np.stack([xs, 1.0 + xs * math.tan(math.radians(30.0))], 1)
    xf = np.linspace(0.0, 1.0 / math.tan(math.radians(50.0)), 400)[1:]
    front = np.stack([xf, 1.0 - xf * math.tan(math.radians(50.0))], 1)
    run = np.stack([np.linspace(front[-1, 0], 1.39, 100)[1:], np.zeros(99)], 1)
    m = pm.measure_profile(np.concatenate([back, front, run]))
    check("三角波：theta=50、波背傾斜=30、張り出しなし、o=0",
          abs(m["theta"] - 50.0) < 1e-6 and abs(m["S4"]["mid_max_deg"] - 30.0) < 1e-6
          and abs(m["S4"]["left_end_deg"] - 30.0) < 1e-6 and not m["overhanging"] and m["o"] == 0.0,
          "theta %.4f slope %.4f" % (m["theta"], m["S4"]["mid_max_deg"]))
    check("三角波：波頂の 100 度の角を S8 が全位相で検出",
          m["S8"]["max_tangent_diff_deg"] > 39.9 and m["S4"]["top_is_round_no_corner"] is False,
          "max %.2f deg (corner 80 deg turn, spread over <= 2 junctions)" % m["S8"]["max_tangent_diff_deg"])
    # 円弧：S8 接合値は標本間隔／半径
    R = 0.4
    a = np.linspace(math.radians(150), math.radians(30), 2000)
    arc = np.stack([R * np.cos(a), 0.6 + R * np.sin(a)], 1)
    C = pm.Curve(arc)
    s8 = pm.s8_smoothness(C, C.length / 2, None, C.length)
    expect = math.degrees(float(pm.pct_h_to_H(1.0)) / R)
    check("円の S8：1 %% 間隔での転角は間隔／半径", abs(s8["max_tangent_diff_deg"] - expect) < 0.01,
          "%.4f vs %.4f deg" % (s8["max_tangent_diff_deg"], expect))
    # 最終の解析的姿勢：特徴点の厳密値
    dense, _ids, info = msw.profile_points(1.0, dense_ds=1e-4)
    m = pm.measure_profile(dense)
    lmk = m["landmarks"]

    def dpct(p, q):
        return float(pm.H_to_pct_h(math.hypot(p[0] - q[0], p[1] - q[1])))
    d_c, d_t, d_d = dpct(lmk["crest"]["H"], info["crest"]), dpct(lmk["head_tip"]["H"], info["head_tip"]), \
        dpct(lmk["inner_deepest"]["H"], info["inner_deepest"])
    check("密な解析的最終姿勢：波頂・先端・最深点が解析式と一致", max(d_c, d_t, d_d) < TOL_POS_PCT_H,
          "crest %.4f tip %.4f deepest %.4f %% of image height (definition bias of the robust extremum)" % (d_c, d_t, d_d))
    check("密な解析的最終姿勢：phi=-b、theta=b+kappa、o が厳密値と一致",
          abs(m["phi_deg"] - info["phi_exact_deg"]) < 1e-6 and abs(m["theta"] - info["theta_pointwise_deg"]) < 1e-6
          and float(pm.H_to_pct_h(abs(m["o"] - info["o"]))) < 0.05,
          "phi %.6f theta %.6f o %.6f (exact %.6f)" % (m["phi_deg"], m["theta"], m["o"], info["o"]))
    check("密な解析的最終姿勢：S8 の判定最大値は 15 度未満、先端転角は kappa",
          m["S8"]["max_tangent_diff_deg"] < 15.0 and abs(m["S8"]["tip_turn_deg"] - info["params"]["kappa"]) < 0.5,
          "max %.2f (unexcluded %.2f), tip turn %.2f" % (m["S8"]["max_tangent_diff_deg"], m["S8"]["max_unexcluded_deg"],
                                                         m["S8"]["tip_turn_deg"]))
    REPORT["analytic_final"] = {"info": info, "metrics": m}
    # 輪郭自身と、移動した写しに対する S7
    doc = msw.export_contour_json()
    bc = pm.load_base_contour(msw.SYNTHETIC_CONTOUR_JSON)
    poly = pm.base_contour_polyline(bc)
    ref, _ = clipped_reference_curve(1.0, F)
    dev0 = pm.s7_deviation(ref, bc)
    worst0 = max(dev0[k]["p95_dev_pct_h"] for k in ("back", "head", "inner_arc"))
    check("解析的曲線と自己の JSON の S7 はほぼ 0", worst0 < 0.02, "最大 p95 %.4f %%" % worst0)
    shift = float(pm.pct_h_to_H(1.0))
    dev1 = pm.s7_deviation(ref + [0.0, shift], bc)
    ok = all(abs(dev1[k]["mean_dev_pct_h"] - e) < t for k, e, t in (("back", 0.85, 0.2), ("head", 0.8, 0.25)))
    check("1 % 上げた写しの S7：波背と頭部の平均偏差は 1 %×cos(傾斜) に近い", ok,
          "back %.3f head %.3f inner %.3f" % (dev1["back"]["mean_dev_pct_h"], dev1["head"]["mean_dev_pct_h"],
                                              dev1["inner_arc"]["mean_dev_pct_h"]))
    n_excl = int((~poly["in_S7"]).sum())
    check("JSON の in_S7=false の点は S7 から除外される", dev0["n_base_excluded"] == n_excl and n_excl > 0
          and dev0["inner_arc"]["model_to_base"]["n_skipped_not_in_S7"] > 0,
          "%d base points flagged; %d model samples skipped" % (n_excl, dev0["inner_arc"]["model_to_base"]["n_skipped_not_in_S7"]))
    bm = pm.measure_base_contour(bc)
    bm2 = pm.measure_base_contour(bc, use_json_segmentation=False)
    check("基準輪郭 JSON の phi 定義が接合点指定と再検出で一致",
          abs(bm["phi_deg"] - info["phi_exact_deg"]) < 0.05 and abs(bm2["phi_deg"] - info["phi_exact_deg"]) < 0.05,
          "json joints %.4f, re-detected %.4f, exact %.4f" % (bm["phi_deg"], bm2["phi_deg"], info["phi_exact_deg"]))
    pc = pm.position_checks(m, bc, bm)
    check("位置検査：自己輪郭に対する S5 はほぼ 0、S6 の胴体右端は爪より左",
          pc["S5"]["pos_pct_h"] < 0.05 and abs(pc["S5"]["dir_deg"]) < 0.05 and pc["S6"]["body_rightmost_left_pct"] < 59.2,
          "S5 pos %.4f dir %.4f ; S6 left %.2f %%" % (pc["S5"]["pos_pct_h"], pc["S5"]["dir_deg"], pc["S6"]["body_rightmost_left_pct"]))
    REPORT["synthetic_contour_json"] = {"path": paths.norm(msw.SYNTHETIC_CONTOUR_JSON),
                                        "n_points": {s["name"]: len(s["points_H"]) for s in doc["segments"]},
                                        "landmarks": doc["landmarks"]}
    return bc


# ============================================================================ C2. head-tip rule, segmentation check, report-only widths
def lobed_test_polyline():
    """原画に似せ、頭部が脇より下へ垂れる手製の張り出し折線。各直線片の座標は H 単位。
    波頂 (0,1)→先端 (0.45,0.65)→頭部最下点 (0.40,0.40)→脇 (0.10,0.60)→
    空洞最深点 (0.03,0.43)→先端より右の足 (0.50,0)→静水面に沿って画面右端。"""
    knots = np.array([[-0.80, 0.30], [0.0, 1.0], [0.45, 0.65], [0.40, 0.40], [0.10, 0.60], [0.03, 0.43], [0.50, 0.0], [1.39, 0.0]])
    out = [knots[:1]]
    for a, b in zip(knots[:-1], knots[1:]):
        n = max(2, int(math.ceil(math.hypot(*(b - a)) / 5e-4)))
        out.append(a + (b - a) * (np.arange(1, n + 1) / n)[:, None])
    return np.concatenate(out), knots


def test_tip_rule_and_widths(F):
    # (a) single-nosed heads: 'max_reversal' == legacy 'first_reversal' on the whole fixture motion
    worst, n_over, onset = 0.0, 0, None
    for t in np.linspace(0.0, 1.0, 61):
        pts, _info = clipped_reference_curve(float(t), F, ds=5e-4)
        a = pm.measure_profile(pts)
        b = pm.measure_profile(pts, {"tip_rule": "first_reversal"})
        if a["overhanging"] != b["overhanging"]:
            worst = float("inf")
            break
        if a["overhanging"]:
            n_over += 1
            onset = t if onset is None else onset
            ta, tb = a["landmarks"]["head_tip"], b["landmarks"]["head_tip"]
            da, db = a["landmarks"]["inner_deepest"], b["landmarks"]["inner_deepest"]
            worst = max(worst, math.hypot(ta["H"][0] - tb["H"][0], ta["H"][1] - tb["H"][1]),
                        math.hypot(da["H"][0] - db["H"][0], da["H"][1] - db["H"][1]), abs(a["o"] - b["o"]),
                        abs((a["phi_deg"] or 0.0) - (b["phi_deg"] or 0.0)))
    check("単一先端の形状で新旧の先端規則が 61 姿勢の先端・最深点・o・phi・張り出し開始について一致",
          worst == 0.0 and n_over > 10, "max difference %.3g (H / deg) on %d overhanging poses, first overhang at t = %.3f" % (worst, n_over, onset or -1))
    # (b) ripples / lobes on the final pose: the tip must not move, the legacy rule is truncated once a reversal exceeds 0.3 %
    pts, _info = clipped_reference_curve(1.0, F, ds=2e-4)
    m0 = pm.measure_profile(pts)
    C = pm.Curve(pts)
    lm0 = m0["landmarks"]
    s_c, s_t, s_d = lm0["crest"]["s"], lm0["head_tip"]["s"], lm0["inner_deepest"]["s"]
    pct = float(pm.pct_h_to_H(1.0))
    d = np.gradient(C.pts, C.s, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= np.maximum(np.hypot(nrm[:, 0], nrm[:, 1]), 1e-12)[:, None]
    win = ((C.s > s_c + 2 * pct) & (C.s < s_d - 2 * pct) & (np.abs(C.s - s_t) > 3 * pct)).astype(float)
    rows = []
    for amp, wl in ((0.3, 3.0), (1.0, 5.0), (2.0, 8.0), (3.0, 10.0)):
        q = C.pts + nrm * (amp * pct * np.sin(2 * np.pi * (C.s - s_c) / (wl * pct)) * win)[:, None]
        a = pm.measure_profile(q)
        b = pm.measure_profile(q, {"tip_rule": "first_reversal"})
        off = lambda mm: float("inf") if not mm["overhanging"] else float(pm.H_to_pct_h(math.hypot(  # noqa: E731
            mm["landmarks"]["head_tip"]["H"][0] - lm0["head_tip"]["H"][0], mm["landmarks"]["head_tip"]["H"][1] - lm0["head_tip"]["H"][1])))
        rows.append((amp, wl, a["head_lobes"]["n_lobes"], off(a), off(b), a["head_lobes"]["onset_to_tip_pct_h"]))
    check("頭部上下の 0.3～3 % の細波で先端が動かない",
          max(r[3] for r in rows) < 1e-6 and max(r[4] for r in rows) > 3.0 and rows[-1][2] > 1,
          "; ".join("amp %.1f %%: lobes %d, new %.4f %%, legacy %.2f %%" % (r[0], r[2], r[3], r[4]) for r in rows))
    REPORT["tip_rule_ripples"] = [{"amp_pct_h": r[0], "wavelength_pct_h": r[1], "n_lobes": r[2], "tip_shift_new_pct_h": r[3],
                                   "tip_shift_legacy_pct_h": r[4], "onset_to_tip_pct_h": r[5]} for r in rows]
    # (c) drooping head, toe further right than the tip, run along the water to the right frame edge
    lp, knots = lobed_test_polyline()
    ml = pm.measure_profile(lp)
    lk = ml["landmarks"]
    x_c_l = lk["crest"]["H"][0]                # robust crest X of a sharp asymmetric corner: a few 1e-4 H off the corner by definition
    ok = (ml["overhanging"] and abs(lk["head_tip"]["H"][0] - 0.45) < 1e-9 and abs(lk["head_tip"]["H"][1] - 0.65) < 2e-3
          and abs(lk["inner_deepest"]["H"][0] - 0.03) < 1e-9 and abs(lk["trough_end"]["H"][0] - 0.50) < 0.01
          and abs(ml["o"] - (0.45 - x_c_l)) < 1e-9 and abs(x_c_l) < 1e-3 and abs(ml["cavity_depth"] - 0.42) < 1e-9)
    check("垂れた頭部：足 X=0.50 と水面 X=1.39 が先端 X=0.45 より右でも特徴点と空洞深さが厳密値と一致",
          ok, "tip %s deepest %s trough end %s o %.4f crest X %.2e" % (lk["head_tip"]["H"], lk["inner_deepest"]["H"], lk["trough_end"]["H"], ml["o"], x_c_l))
    check("波頂から先端への向き（報告専用）= atan2(-0.35, 0.45)", abs(ml["crest_to_tip_deg"] - math.degrees(math.atan2(-0.35, 0.45))) < 0.2,
          "%.3f deg" % ml["crest_to_tip_deg"])
    # (d) report-only widths: closed forms on straight-line shapes
    W = ml["W"]["sections"]
    z50, z75 = W["z50"], W["z75"]
    xb50 = -0.8 + (0.5 - 0.3) / 0.7 * 0.8
    e50 = (abs(z50["x_back_H"] - xb50), abs(z50["x_front_H"] - 0.42), abs(z50["x_inner_H"] - (0.10 - 0.07 * (0.1 / 0.17))),
           abs(z50["cavity_gap_H"] - (0.25 - (0.10 - 0.07 * (0.1 / 0.17)))), abs(z50["width_body_H"] - (0.10 - 0.07 * (0.1 / 0.17) - xb50)))
    xf75 = 0.45 * (0.25 / 0.35)
    e75 = (abs(z75["x_front_H"] - xf75), abs(z75["back_from_crest_H"] - (0.25 / 0.7 * 0.8 + x_c_l)), abs(z75["width_full_H"] - (xf75 + 0.25 / 0.7 * 0.8)))
    check("垂れた頭部の幅（報告専用）：Z=0.5 H は張り出しの 3 交点、Z=0.75 H は張り出しなし",
          z50["overhung"] and z50["n_front_crossings"] == 3 and z50["inner_on_segment"] == "inner_arc" and not z75["overhung"]
          and max(e50 + e75) < 1e-9 and not z50["back_clipped_at_frame_edge"] and W["z25"]["back_clipped_at_frame_edge"],
          "max |error| %.2e H; z50: back %.4f inner %.4f front %.4f; z25 back clipped at the frame edge: %s"
          % (max(e50 + e75), z50["x_back_H"], z50["x_inner_H"], z50["x_front_H"], W["z25"]["back_clipped_at_frame_edge"]))
    # 面積：ライブラリの靴紐公式と同じ多角形の独立な画素計数を比較（1000 px／H）
    i_e = int(np.argmin(np.abs(lp[:, 0] - 0.50) + np.abs(lp[:, 1])))
    poly = np.concatenate([lp[:i_e + 1], [[0.50, 0.0], [-0.80, 0.0]]])
    S = 1000.0
    msk = draw.polygon_mask((1100, 1500), np.stack([(poly[:, 0] + 0.9) * S, (1.05 - poly[:, 1]) * S], 1))
    a_px = float(msk.sum()) / S / S
    a_lib = ml["W"]["area_above_still_water_H2"]
    check("静水面より上の面積（報告専用）：靴紐公式と独立の画素計数が一致", abs(a_lib - a_px) / a_px < 2e-3,
          "library %.5f H^2, pixel count %.5f H^2 (cavity excluded in both)" % (a_lib, a_px))
    xs = np.linspace(-0.8, 0.0, 400)
    tri = np.concatenate([np.stack([xs, 1.0 + xs * math.tan(math.radians(30.0))], 1),
                          np.stack([np.linspace(0.0, 1.0 / math.tan(math.radians(50.0)), 400)[1:], 1.0 - np.linspace(0.0, 1.0 / math.tan(math.radians(50.0)), 400)[1:] * math.tan(math.radians(50.0))], 1),
                          [[1.39, 0.0]]])
    mt = pm.measure_profile(tri)
    z0 = 1.0 - 0.8 * math.tan(math.radians(30.0))
    te = mt["landmarks"]["trough_end"]["H"]        # the area ends at the trough end (first sample within trough_tol of Z = 0), not at the toe itself
    a_tri = 0.5 * (z0 + 1.0) * 0.8 + 0.5 / math.tan(math.radians(50.0)) - 0.5 * te[1] * (1.0 / math.tan(math.radians(50.0)) - te[0])
    w75 = 0.25 / math.tan(math.radians(30.0)) + 0.25 / math.tan(math.radians(50.0))
    check("三角波：面積と 0.75 H の幅が解析式と一致し、0.5 H では波背が画面外で切られる",
          abs(mt["W"]["area_above_still_water_H2"] - a_tri) < 1e-6 and abs(mt["W"]["sections"]["z75"]["width_full_H"] - w75) < 1e-6
          and mt["W"]["sections"]["z50"]["back_clipped_at_frame_edge"] and mt["W"]["sections"]["z50"]["back_from_crest_H"] is None,
          "area %.6f (exact %.6f), w75 %.6f (exact %.6f)" % (mt["W"]["area_above_still_water_H2"], a_tri, mt["W"]["sections"]["z75"]["width_full_H"], w75))
    rows_w = pm.compare_width_metrics(pm.measure_profile(lp * [1.05, 1.0])["W"], ml["W"])
    byw = {r["name"]: r for r in rows_w}
    check("幅指標の比較：X=0 を中心に 5 % 広げると o、空洞深さ、波頂鉛直線からの距離も +5 %",
          all(abs(byw[k]["diff_pct_of_target"] - 5.0) < 0.1 for k in ("o_H", "cavity_depth_H", "z75.front_from_crest_H", "z75.back_from_crest_H",
                                                                      "z50.front_from_crest_H", "z50.inner_from_crest_H"))
          and abs(byw["cavity_depth_H"]["diff_pct_of_target"] - 5.0) < 1e-6,
          ", ".join("%s %+.3f %%" % (k, byw[k]["diff_pct_of_target"]) for k in ("o_H", "z75.width_full_H", "z50.width_body_H", "area_above_still_water_H2")))
    # (e) segmentation check of a base contour: consistent on the fixture's own json, NOT consistent when the tip joint is moved
    bc = pm.load_base_contour(msw.SYNTHETIC_CONTOUR_JSON)
    sc = pm.measure_base_contour(bc)["segmentation_check"]
    check("分段検査：合成輪郭の JSON 接合点と検出値が画像高さの 0.2 % 以内で一致",
          sc["consistent"] and sc["max_dist_pct_h"] < 0.05, "max %.5f %% (%s)" % (sc["max_dist_pct_h"], sc["worst"]))
    bad = shifted_tip_joint(bc, 40)
    sc2 = pm.measure_base_contour(bad)["segmentation_check"]
    check("分段検査：先端接合点を 40 標本（80 px＝3.1 %）移すと不一致になり、距離を報告",
          (not sc2["consistent"]) and sc2["worst"] == "head_tip" and 2.5 < sc2["max_dist_pct_h"] < 3.5,
          "head_tip distance %.3f %% of image height" % sc2["items"]["head_tip"]["dist_pct_h"])
    det = pm.detect_landmarks(pm.base_contour_polyline(bad)["pts_H"])
    check("特徴点検出は先端を頭部の最右点へ戻す", abs(det["head_tip"]["H"][0] - bc["landmarks"]["head_tip"]["H"][0]) < 1e-5,
          "detected %s, analytic %s" % (det["head_tip"]["H"], bc["landmarks"]["head_tip"]["H"]))


def shifted_tip_joint(bc, n_pts):
    """基準輪郭を複製し、形状は変えず頭部と内側弧の接合点を頭部側へ n_pts 標本だけ戻す。"""
    import copy
    out = copy.deepcopy(bc)
    by = {s["name"]: s for s in out["segments"]}
    head, inner = by["head"], by["inner_arc"]
    for key in ("points_px", "points_H", "source", "in_S7"):
        if key in head:
            moved = head[key][-(n_pts + 1):]
            head[key] = head[key][:-n_pts]
            inner[key] = moved + inner[key][1:]
    return out


# ============================================================================ D. fixture through Blender
def measure_frame(obj_or_arrays, rect, water_z=0.0, exact=True):
    t = {}
    t0 = time.perf_counter()
    if isinstance(obj_or_arrays, tuple):
        verts, tris = obj_or_arrays
        mask, info = silhouette.mask_from_triangles(verts, tris, rect, water_z, exact=exact)
        t["get_mesh"] = 0.0
    else:
        mask, info = silhouette.silhouette_mask(obj_or_arrays, rect=rect, water_z=water_z, exact=exact)
        t["get_mesh"] = info["seconds_get_mesh"]
    t["rasterize"] = info["seconds_rasterize"]
    t1 = time.perf_counter()
    prof = silhouette.extract_profile(mask, rect, edges=info.pop("edges", None))
    t["extract"] = time.perf_counter() - t1
    t2 = time.perf_counter()
    met = pm.measure_profile(prof["H"])
    t["measure"] = time.perf_counter() - t2
    t["total"] = time.perf_counter() - t0
    return mask, info, prof, met, t


def compare_with_analytic(met, ref_met, info, label):
    """-> dict of errors (pct_h / deg); entries are None when not applicable."""
    def dpct(p, q):
        return float(pm.H_to_pct_h(math.hypot(p[0] - q[0], p[1] - q[1])))
    lm = met["landmarks"]
    e = {"crest_pct_h": dpct(lm["crest"]["H"], info["crest"]),
         "h_pct_h": float(pm.H_to_pct_h(abs(met["h"] - info["crest"][1]))),
         "x_c_pct_h": float(pm.H_to_pct_h(abs(met["x_c"] - info["crest"][0]))),
         "theta_deg": abs(met["theta"] - ref_met["theta"]),
         "theta_vs_pointwise_deg": abs(met["theta"] - info["theta_pointwise_deg"]),
         "tip_pct_h": None, "deepest_pct_h": None, "o_pct_h": None, "phi_deg": None}
    if info["overhanging"] and met["overhanging"]:
        e["tip_pct_h"] = dpct(lm["head_tip"]["H"], info["head_tip"])
        e["deepest_pct_h"] = dpct(lm["inner_deepest"]["H"], info["inner_deepest"])
        e["o_pct_h"] = float(pm.H_to_pct_h(abs(met["o"] - info["o"])))
        if met["phi_deg"] is not None and ref_met["phi_deg"] is not None:
            e["phi_deg"] = abs(met["phi_deg"] - ref_met["phi_deg"])
    return e


def test_fixture(F, bc, quick):
    import bpy
    scene = bootstrap.reset_scene()
    H = F.H
    obj, sw = msw.build_object(scene, msw.N_FRAMES_DEFAULT, "clip", H)
    me = obj.data
    check("テスト用メッシュ：固定格子、UV レイヤー、crest_rim グループ、シェイプキー",
          len(me.vertices) == sw.n_u * sw.n_v and len(me.polygons) == len(sw.faces) and len(me.uv_layers) == 1
          and "crest_rim" in obj.vertex_groups and len(me.shape_keys.key_blocks) == sw.n_frames,
          "%d x %d = %d verts, %d quads, %d shape keys" % (sw.n_u, sw.n_v, len(me.vertices), len(me.polygons),
                                                          len(me.shape_keys.key_blocks)))
    cam, rect_full, camchk = silhouette.setup_cam_print(scene, H)
    check("setup_cam_print：Blender カメラの投影が ViewRect の画素格子と一致", camchk["max_err_px"] < 0.01,
          "max err %.5f px" % camchk["max_err_px"])
    # 全フレームで裾は静水面上。評価済みメッシュと NumPy 頂点が一致。
    worst_hem, worst_dv = 0.0, 0.0
    for fr in range(1, sw.n_frames + 1, 5):
        scene.frame_set(fr)
        v, tris, _i = silhouette.mesh_world_triangles(obj)
        vn = sw.vertices(fr)
        worst_dv = max(worst_dv, float(np.abs(v - vn).max()))
        g = vn.reshape(sw.n_v, sw.n_u, 3)
        border = np.concatenate([g[0, :, 2], g[-1, :, 2], g[:, 0, 2], g[:, -1, 2]])
        worst_hem = max(worst_hem, float(np.abs(border).max()))
    check("テスト形状：評価済みシェイプキーの網目が解析的頂点と一致", worst_dv < 2e-5 * H, "最大 |dv| %.2e m" % worst_dv)
    check("テスト形状：全フレームで裾の外周が静水面上にある", worst_hem < 1e-9,
          "max |Z| %.2e m" % worst_hem)

    frames = [1, 7, 13, 19, 25, 31] if not quick else [1, 19, 31]
    results = {}
    final_pack = None
    for mode, sc in (("exact", 1.0), ("exact", 0.5), ("exact", 0.25), ("pixel", 1.0), ("pixel", 0.5), ("pixel", 0.25)):
        rect = silhouette.ViewRect.from_cam_print(H=H, scale=sc)
        per_frame = []
        tag = "%s_%.2f" % (mode, sc)
        for fr in frames:
            scene.frame_set(fr)
            mask, info, prof, met, tms = measure_frame(obj, rect, exact=(mode == "exact"))
            ref_pts, ainfo = clipped_reference_curve(msw.frame_to_t(fr), F)
            ref_met = pm.measure_profile(ref_pts)
            err = compare_with_analytic(met, ref_met, ainfo, "f%d" % fr)
            cav = (ainfo["head_tip"][0] - ainfo["inner_deepest"][0]) if ainfo["overhanging"] else 0.0
            per_frame.append({"frame": fr, "errors": err, "timing_s": tms, "n_tris": info["n_triangles"],
                              "n_spans": info["n_spans"], "holes": prof["holes"], "complete": prof["complete"],
                              "n_cracks_without_exact_data": prof["n_cracks_without_exact_data"],
                              "overhanging_measured": met["overhanging"], "overhanging_analytic": ainfo["overhanging"],
                              "analytic_cavity_depth_pct_h": float(pm.H_to_pct_h(cav)),
                              "measured": {k: met[k] for k in ("h", "x_c", "theta", "o", "phi_deg")},
                              "reference": {"h": ainfo["crest"][1], "x_c": ainfo["crest"][0], "theta": ref_met["theta"],
                                            "o": ainfo["o"], "phi_deg": ref_met["phi_deg"]}})
            if tag == "exact_1.00" and fr == frames[-1]:
                final_pack = (mask, info, prof, met, rect)
            if tag == "exact_1.00":
                save_frame_overlay(mask, prof, met, fr, F)
        results[tag] = per_frame
        # この解像度における精度の集計
        pos_items = [(v, k, pf["frame"]) for pf in per_frame for k, v in pf["errors"].items()
                     if k.endswith("pct_h") and v is not None]
        ang_items = [(pf["errors"][k], k, pf["frame"]) for pf in per_frame for k in ("theta_deg", "phi_deg")
                     if pf["errors"][k] is not None]
        wp, wa = max(pos_items), max(ang_items)
        tt = [pf["timing_s"]["total"] for pf in per_frame]
        log("%s 倍率 %.2f（%d×%d）：最大位置誤差は画像高さの %.4f %%（%s、フレーム %d）、最大角度誤差 %.3f 度（%s、フレーム %d）、%.2f 秒／フレーム"
            % (mode, sc, rect.width_px, rect.height_px, wp[0], wp[1], wp[2], wa[0], wa[1], wa[2], float(np.mean(tt))))
        results["summary_" + tag] = {"mode": mode, "scale": sc, "resolution": [rect.width_px, rect.height_px],
                                     "max_pos_err_pct_h": wp[0], "max_pos_err_what": "%s frame %d" % (wp[1], wp[2]),
                                     "max_angle_err_deg": wa[0], "max_angle_err_what": "%s frame %d" % (wa[1], wa[2]),
                                     "mean_seconds_per_frame": float(np.mean(tt)),
                                     "mean_timing_s": {k: float(np.mean([pf["timing_s"][k] for pf in per_frame]))
                                                       for k in per_frame[0]["timing_s"]}}
        if sc == 1.0:
            check("%s、フル解像度：波頂・先端・最深点・h・x_c・o が画像高さの %.1f %% 以内" % (mode, TOL_POS_PCT_H),
                  wp[0] < TOL_POS_PCT_H, "max %.4f %% (%s, frame %d)" % wp)
            check("%s、フル解像度：theta・phi が解析的曲線の %.0f 度以内" % (mode, TOL_ANG_DEG),
                  wa[0] < TOL_ANG_DEG, "max %.3f deg (%s, frame %d)" % wa)
        if tag == "exact_1.00":
            check("フル解像度：全輪郭が左右端までつながり、マスクに穴がなく、全交点に厳密データがある",
                  all(pf["complete"] for pf in per_frame) and all(pf["holes"]["n_holes"] == 0 for pf in per_frame)
                  and all(pf["n_cracks_without_exact_data"] == 0 for pf in per_frame),
                  "holes: %s, cracks without exact data: %s" % ([pf["holes"]["n_holes"] for pf in per_frame],
                                                               [pf["n_cracks_without_exact_data"] for pf in per_frame]))
            check("フル解像度：張り出し検出が解析的な状態と一致",
                  all(pf["overhanging_measured"] == pf["overhanging_analytic"] for pf in per_frame
                      if not (0.0 < pf["analytic_cavity_depth_pct_h"] < 1.0)))
    REPORT["fixture_accuracy"] = results

    # ---- final frame: S7 against the analytic contour json, S8, position checks, overlays
    mask, info, prof, met, rect = final_pack
    dev = pm.s7_deviation(prof["H"], bc, met)
    worst_mean = max(dev[k]["mean_dev_pct_h"] for k in ("back", "head", "inner_arc"))
    worst_p95 = max(dev[k]["p95_dev_pct_h"] for k in ("back", "head", "inner_arc"))
    check("最終フレーム：自己の解析的輪郭に対する S7 偏差 < %.1f %%" % TOL_POS_PCT_H,
          worst_p95 < TOL_POS_PCT_H, "worst mean %.4f %%, worst p95 %.4f %%" % (worst_mean, worst_p95))
    pc = pm.position_checks(met, bc)
    REPORT["final_frame"] = {"metrics": met, "S7": dev, "position_checks": pc, "mask_info": info,
                             "profile": {k: prof[k] for k in ("complete", "end_border", "n_trace_steps", "components", "holes")}}
    check("最終フレーム：S8 判定最大値 < 15 度。先端転角は別に報告",
          met["S8"]["max_tangent_diff_deg"] < 15.0 and met["S8"]["tip_turn_deg"] is not None,
          "max %.2f deg at %s, unexcluded max %.1f, tip turn %.1f" % (
              met["S8"]["max_tangent_diff_deg"], met["S8"]["max_at"]["segment"], met["S8"]["max_unexcluded_deg"],
              met["S8"]["tip_turn_deg"]))
    # NumPy 経路と Blender 経路の一致
    scene.frame_set(frames[-1])
    m2, _i2 = silhouette.mask_from_triangles(sw.vertices(frames[-1]), sw.triangles, rect, 0.0, exact=False)
    cmpm = silhouette.compare_masks(mask, m2)
    check("Blender 評価済みメッシュと NumPy 頂点のマスクが一致", cmpm["n_disagree"] <= 20,
          "%d px differ (float32 mesh coordinates)" % cmpm["n_disagree"])
    save_final_crops(mask, prof, met, bc, F)
    # 自作と反転した矩形（-X へ進む参照形状で必要になる）
    r0 = silhouette.ViewRect.from_cam_print(H=H, scale=0.25)
    vm = sw.vertices(frames[-1]) * [-1.0, 1.0, 1.0]
    rm = silhouette.ViewRect(-r0.x_max, -r0.x_min, r0.z_min, r0.z_max, r0.width_px, r0.height_px, mirror_x=True, H=H)
    _mk, _ik, _pk, met_m, _tk = measure_frame((vm, sw.triangles), rm)
    _mk, _ik, _pk, met_0, _tk = measure_frame((sw.vertices(frames[-1]), sw.triangles), r0)
    dm = max(abs(met_m[k] - met_0[k]) for k in ("h", "x_c", "theta", "o", "phi_deg"))
    check("mirror_x の矩形：-X へ進む波でも同じ指標になる", dm < 1e-6, "最大差 %.2e" % dm)
    rb = silhouette.ViewRect.from_bounds(-9.0, 15.0, -1.0, 12.5, px_per_unit=40.0, H=H, name="custom")
    _mk, _ik, _pk, met_b, _tk = measure_frame((sw.vertices(frames[-1]), sw.triangles), rb)
    db = max(abs(met_b[k] - met_0[k]) for k in ("h", "x_c", "theta", "o", "phi_deg"))
    check("自作の矩形（from_bounds、40 px/m）が CAM_print の矩形と同じ指標になる", db < 2e-3,
          "max difference %.2e (H units / deg); rect %dx%d px" % (db, rb.width_px, rb.height_px))
    return scene, obj, sw, final_pack


def save_frame_overlay(mask, prof, met, fr, F):
    ttl = "synthetic fixture frame %d: h=%.3f x_c=%.3f theta=%.1f o=%.3f phi=%s" % (
        fr, met["h"], met["x_c"], met["theta"], met["o"], "n/a" if met["phi_deg"] is None else "%.1f" % met["phi_deg"])
    img = silhouette.draw_overlay(mask, prof, met, title=ttl)
    imgio.save_png(os.path.join(OUT, "overlay_frame_%03d.png" % fr), img)


def save_final_crops(mask, prof, met, bc, F):
    rect = prof["rect"]
    poly = pm.base_contour_polyline(bc)
    ref_px = np.array([silhouette._rect_H_to_px(rect, p) for p in poly["pts_H"]])
    extra = [{"px": ref_px, "color": "lime", "width": 1.5, "dash": (6, 6)}]
    for key, half, name in (("crest", 170, "crest"), ("head_tip", 110, "tip"), ("inner_deepest", 170, "deepest")):
        c = silhouette._rect_H_to_px(rect, met["landmarks"][key]["H"])
        box = (c[0] - half, c[1] - half * 0.7, c[0] + half, c[1] + half * 0.7)
        img = silhouette.draw_overlay(mask, prof, met, title="final frame, %s (green dashes = analytic contour)" % name,
                                      crop_px=box, crop_scale=min(8.0, 1500.0 / (2 * half)), extra_polylines=extra)
        imgio.save_png(os.path.join(OUT, "crop_final_%s.png" % name), img)
    # 頭部領域を 2 倍で表示
    t = silhouette._rect_H_to_px(rect, met["landmarks"]["head_tip"]["H"])
    box = (t[0] - 700, t[1] - 330, t[0] + 60, t[1] + 200)
    img = silhouette.draw_overlay(mask, prof, met, title="final frame, head region", crop_px=box, crop_scale=2.0,
                                  extra_polylines=extra)
    imgio.save_png(os.path.join(OUT, "crop_final_head.png"), img)


# ============================================================================ E. failure demos
def test_failure_demos(F):
    H = F.H
    rect = silhouette.ViewRect.from_cam_print(H=H, scale=1.0)
    fr = msw.FRAME_START + msw.N_FRAMES_DEFAULT - 1
    ref_pts, ainfo = clipped_reference_curve(1.0, F)
    ref_px = rect.pts_H_to_px(ref_pts)
    extra = [{"px": ref_px, "color": "lime", "width": 2.0, "dash": (10, 8)}]
    out = {}
    # 1. z-scale taper: smaller end sections block the concavity
    sw = msw.SyntheticWave(taper="zscale", H=H)
    mask, info = silhouette.mask_from_triangles(sw.vertices(fr), sw.triangles, rect, 0.0, exact=False)
    prof = silhouette.extract_profile(mask, rect)
    met = pm.measure_profile(prof["H"])
    ttl = "FAILURE DEMO taper=zscale: end sections block the concavity (green = true main section)"
    imgio.save_png(os.path.join(OUT, "failure_zscale_taper.png"),
                   silhouette.draw_overlay(mask, prof, met, title=ttl, extra_polylines=extra))
    d = None
    if met["landmarks"]["inner_deepest"] is not None:
        p, q = met["landmarks"]["inner_deepest"]["H"], ainfo["inner_deepest"]
        d = float(pm.H_to_pct_h(math.hypot(p[0] - q[0], p[1] - q[1])))
    mask_ok, _ = silhouette.mask_from_triangles(msw.SyntheticWave(taper="clip", H=H).vertices(fr), sw.triangles, rect, 0.0, exact=False)
    blocked = int((mask & ~mask_ok).sum())
    out["zscale"] = {"overhanging_measured": met["overhanging"], "deepest_error_pct_h": d, "o": met["o"],
                     "theta": met["theta"], "cavity_px_blocked": blocked,
                     "blocked_frac_of_true_sky_under_head": None}
    check("失敗例（zscale 先細り）：空洞が塞がれ、指標にも現れる",
          blocked > 20000 and (d is None or d > 2.0),
          "%d px of the true concavity are covered; deepest-point error %s %% of image height; overhanging=%s"
          % (blocked, "n/a" if d is None else "%.2f" % d, met["overhanging"]))
    # zscale 事例の空洞を切り抜く
    c = rect.pts_H_to_px(np.array([ainfo["inner_deepest"]]))[0]
    box = (c[0] - 250, c[1] - 650, c[0] + 850, c[1] + 450)
    imgio.save_png(os.path.join(OUT, "failure_zscale_taper_crop.png"),
                   silhouette.draw_overlay(mask, prof, met, title="zscale taper: cavity region", crop_px=box,
                                           crop_scale=1.4, extra_polylines=extra))
    # 2. no taper: edge-on sheet
    sw0 = msw.SyntheticWave(taper="none", H=H)
    m_skip, i_skip = silhouette.mask_from_triangles(sw0.vertices(fr), sw0.triangles, rect, 0.0, exact=False)
    m_line, i_line = silhouette.mask_from_triangles(sw0.vertices(fr), sw0.triangles, rect, 0.0, thin="line", exact=False)
    rep = raster.hole_report(m_line)
    out["none"] = {"mesh_area_px_skip": i_skip["mesh_area_px"], "mesh_area_px_line": i_line["mesh_area_px"],
                   "hole_report_line": {k: rep[k] for k in ("n_holes", "hole_area_px", "hole_area_frac", "largest_hole_bbox")}}
    check("非立体の失敗例（先細りなし）：真横のシートは面積ゼロで、thin='line' と穴の報告が検出する",
          i_skip["mesh_area_px"] == 0 and rep["n_holes"] >= 1 and rep["hole_area_frac"] > 0.1,
          "skip: %d px; line: %d px, holes %d, hole area = %.1f %% of the filled silhouette"
          % (i_skip["mesh_area_px"], i_line["mesh_area_px"], rep["n_holes"], 100 * rep["hole_area_frac"]))
    prof_l = silhouette.extract_profile(m_line, rect, keep_mask=True)
    img = draw.canvas(rect.height_px, rect.width_px)
    draw.overlay_mask(img, m_line, "blue", 0.6)
    draw.overlay_mask(img, prof_l["holes_mask"], "red", 0.45)
    img = draw.fit_width(img, 1600)
    draw.text(img, 6, 6, "NON-SOLID DEMO taper=none, thin='line': blue = mask, red = un-filled interior hole (hole_report)",
              "black", 2, bg="white")
    imgio.save_png(os.path.join(OUT, "failure_no_taper_holes.png"), img)
    REPORT["failure_demos"] = out


# ============================================================================ F. Cycles cross-check
def test_cycles(scene, obj, final_pack, F):
    mask, info, prof, met, rect = final_pack
    scene.frame_set(msw.FRAME_START + msw.N_FRAMES_DEFAULT - 1)
    png = os.path.join(OUT, "cycles_mask_final.png")
    cm, cinfo = silhouette.render_mask_cycles(obj, rect, png, water_z=0.0, scene=scene)
    cmpm = silhouette.compare_masks(mask, cm)
    REPORT["cycles_crosscheck"] = {"render": cinfo, "compare": cmpm, "resolution": [rect.width_px, rect.height_px]}
    check("Cycles CPU の 1 標本発光マスクと NumPy マスクは境界でのみ異なる",
          cmpm["frac_disagree"] < 2e-4 and cmpm["n_disagree_far"] == 0,
          "%d of %d px differ (%.5f %%), %d on the boundary ring, %d within 2 px, %d farther; render %.1f s"
          % (cmpm["n_disagree"], cmpm["n_px"], 100 * cmpm["frac_disagree"], cmpm["n_disagree_on_boundary_px"],
             cmpm["n_disagree_within_2px"], cmpm["n_disagree_far"], cinfo["seconds"]))
    # 頭部周囲の差分画像
    img = draw.canvas(rect.height_px, rect.width_px)
    draw.overlay_mask(img, mask, "blue", 0.3)
    d = mask != cm
    ys, xs = np.nonzero(d)
    for x, y in list(zip(xs, ys))[:4000]:
        draw.circle(img, (x + 0.5, y + 0.5), 4, "red")
    img = draw.fit_width(img, 1600)
    draw.text(img, 6, 6, "numpy mask (blue) vs Cycles mask: red dots = disagreeing pixels (%d)" % cmpm["n_disagree"],
              "black", 2, bg="white")
    imgio.save_png(os.path.join(OUT, "cycles_vs_numpy.png"), img)


# ============================================================================ G. performance
def test_performance(F):
    H = F.H
    out = {}
    sw = msw.SyntheticWave(H=H, u_mult=5)
    fr = msw.FRAME_START + msw.N_FRAMES_DEFAULT - 1
    verts = sw.vertices(fr)
    tris = sw.triangles
    # Houdini キャッシュと同様の、頂点を共有しない三角形集合
    soup_v = verts[tris.ravel()]
    soup_t = np.arange(soup_v.shape[0]).reshape(-1, 3)
    for mode in ("exact", "pixel"):
        for sc in (1.0, 0.5, 0.25):
            rect = silhouette.ViewRect.from_cam_print(H=H, scale=sc)
            _m, _i, prof, met, tms = measure_frame((soup_v, soup_t), rect, exact=(mode == "exact"))
            out["dense_fixture_%s_%.2f" % (mode, sc)] = {"n_vertices": int(soup_v.shape[0]), "n_triangles": int(soup_t.shape[0]),
                                                         "n_spans": _i["n_spans"], "timing_s": tms}
            log("密なテスト用形状の性能（頂点 %d、三角形 %d）%s、倍率 %.2f：描画 %.2f 秒、抽出 %.2f 秒、測定 %.2f 秒"
                % (soup_v.shape[0], soup_t.shape[0], mode, sc, tms["rasterize"], tms["extract"], tms["measure"]))
    # 大きな三角形のランダム集合。区間数にとって厳しい条件で、204k 個・約 25 px。
    rng = np.random.default_rng(11)
    n = 203958
    rect = silhouette.ViewRect.from_cam_print(H=H, scale=1.0)
    c = np.stack([rng.uniform(rect.x_min, rect.x_max, n), np.zeros(n), rng.uniform(0.0, 0.9 * H, n)], 1)
    v = (c[:, None, :] + rng.uniform(-0.08, 0.08, size=(n, 3, 3)) * [1, 0, 1]).reshape(-1, 3)
    t0 = time.perf_counter()
    m, i = silhouette.mask_from_triangles(v, np.arange(3 * n).reshape(-1, 3), rect, 0.0)
    t1 = time.perf_counter()
    out["random_soup_204k_full"] = {"n_triangles": n, "n_spans": i["n_spans"], "seconds_rasterize": t1 - t0}
    log("ランダムな大三角形 204k 個、フル解像度の性能：%.2f 秒（%d 区間）" % (t1 - t0, i["n_spans"]))
    check("性能：頂点 600k 個の三角形集合をフル解像度で数秒以内にラスター化",
          out["dense_fixture_exact_1.00"]["timing_s"]["rasterize"] < 20.0 and (t1 - t0) < 20.0,
          "dense fixture %.2f s, random soup %.2f s" % (out["dense_fixture_exact_1.00"]["timing_s"]["rasterize"], t1 - t0))
    REPORT["performance"] = out


# ============================================================================ H. --profile-json mode
def test_profile_json(F, bc):
    H = F.H
    rect = silhouette.ViewRect.from_cam_print(H=H, scale=0.5)
    sw = msw.SyntheticWave(H=H, profile_json=msw.SYNTHETIC_CONTOUR_JSON)
    fr_last = msw.FRAME_START + sw.n_frames - 1
    res = {}
    for fr in (1, 16, fr_last):
        mask, _i, prof, met, _t = measure_frame((sw.vertices(fr), sw.triangles), rect)
        res[fr] = {"h": met["h"], "theta": met["theta"], "o": met["o"], "holes": prof["holes"]["n_holes"],
                   "complete": prof["complete"]}
        if fr == fr_last:
            dev = pm.s7_deviation(prof["H"], bc, met)
            worst = max(dev[k]["p95_dev_pct_h"] for k in ("back", "head", "inner_arc"))
            res["final_S7_worst_p95_pct_h"] = worst
            imgio.save_png(os.path.join(OUT, "profile_json_mode_final.png"),
                           silhouette.draw_overlay(mask, prof, met, title="--profile-json mode (synthetic_contour.json swept), final frame, half res"))
    check("--profile-json モード：synthetic_contour.json の掃引で輪郭を再現（半解像度の S7 p95 < 0.3 %）",
          res["final_S7_worst_p95_pct_h"] < 0.3 and res[fr_last]["holes"] == 0,
          "worst p95 %.4f %%; frames 1/16/31: theta %.1f / %.1f / %.1f" % (res["final_S7_worst_p95_pct_h"],
                                                                         res[1]["theta"], res[16]["theta"], res[fr_last]["theta"]))
    REPORT["profile_json_mode"] = {str(k): v for k, v in res.items()}
    # 任意：正式な基準輪郭が作成済みなら使用する（報告専用）
    if os.path.isfile(paths.BASE_CONTOUR_JSON):
        try:
            real = pm.load_base_contour(paths.BASE_CONTOUR_JSON)
            swr = msw.SyntheticWave(H=H, profile_json=paths.BASE_CONTOUR_JSON)
            rect1 = silhouette.ViewRect.from_cam_print(H=H, scale=1.0)
            mask, _i, prof, met, _t = measure_frame((swr.vertices(fr_last), swr.triangles), rect1)
            dev = pm.s7_deviation(prof["H"], real, met)
            pc = pm.position_checks(met, real)
            REPORT["real_base_contour_sweep"] = {"S7": dev, "position_checks": pc, "holes": prof["holes"],
                                                 "metrics": {k: met[k] for k in ("h", "x_c", "theta", "o", "phi_deg")}}
            painting = imgio.load_painting_rgb()
            imgio.save_png(os.path.join(OUT, "real_base_contour_sweep.png"),
                           silhouette.draw_overlay(mask, prof, met, base=painting,
                                                   title="target/base_contour.json swept by the fixture (report only)"))
            log("実輪郭の掃引：S7 p95 背／頭／内側 = %s、穴 %d" % (
                [None if dev[k] is None else round(dev[k]["p95_dev_pct_h"], 3) for k in ("back", "head", "inner_arc")],
                prof["holes"]["n_holes"]))
        except Exception as ex:                                   # report only, never fails the self-test
            REPORT["real_base_contour_sweep"] = {"error": repr(ex)}
            log("実輪郭の掃引に失敗（報告専用）：%r" % (ex,))
    else:
        REPORT["real_base_contour_sweep"] = "target/base_contour.json does not exist yet"


# ============================================================================ I. motion series
def test_motion_series(scene, obj, sw, F):
    """全テストフレームを 1/4 解像度で測る（厳密な交点）。仕様第6.2節の曲線を解析的系列と比較し、
    M 検査に関わる測定雑音の下限を求める。"""
    frames = list(range(msw.FRAME_START, msw.FRAME_START + sw.n_frames))
    t0 = time.perf_counter()
    profs = silhouette.profiles_over_frames(obj, frames, scene=scene, H=F.H, scale=0.25)
    seq = pm.measure_sequence([p["H"] for p in profs])
    dt = time.perf_counter() - t0
    an = {"h": [], "x_c": [], "theta": [], "o": [], "phi": []}
    for fr in frames:
        ref_pts, ainfo = clipped_reference_curve(msw.frame_to_t(fr), F, ds=5e-4)
        rm = pm.measure_profile(ref_pts)
        an["h"].append(ainfo["crest"][1])
        an["x_c"].append(ainfo["crest"][0])
        an["theta"].append(rm["theta"])
        an["o"].append(rm["o"])
        an["phi"].append(np.nan if rm["phi_deg"] is None else rm["phi_deg"])
    nanify = lambda v: np.array([np.nan if q is None else q for q in v], dtype=np.float64)
    h, xc, th, o, ph = (nanify(seq[k]) for k in ("h", "x_c", "theta", "o", "phi_deg"))
    err = {"h_H": float(np.nanmax(np.abs(h - an["h"]))), "x_c_H": float(np.nanmax(np.abs(xc - an["x_c"]))),
           "theta_deg": float(np.nanmax(np.abs(th - an["theta"]))), "o_H": float(np.nanmax(np.abs(o - an["o"]))),
           "phi_deg": float(np.nanmax(np.abs(ph - np.array(an["phi"]))))}
    # 単調性の雑音下限：解析的な h は減らないので、測定上の減少は雑音。
    dh = np.diff(h)
    noise_h = float(max(0.0, -dh.min()))
    do = np.diff(o)
    noise_o = float(max(0.0, -(do[np.diff(np.array(an["o"])) >= 0]).min()))
    REPORT["motion_series"] = {"frames": frames, "seconds_total": dt, "seconds_per_frame": dt / len(frames),
                               "scale": 0.25, "max_abs_error_vs_analytic": err,
                               "h_largest_false_decrease_H": noise_h, "o_largest_false_decrease_H": noise_o,
                               "measured": {k: [None if (isinstance(v, float) and v != v) else v for v in seq[k]]
                                            for k in ("h", "x_c", "theta", "o", "phi_deg", "overhanging", "disp_max_H")},
                               "analytic": {k: [None if v != v else float(v) for v in an[k]] for k in an}}
    check("動作系列（31 フレーム、1/4 解像度、厳密）：h・x_c・o は画像高さの %.1f %% 以内、theta・phi は %.0f 度以内"
          % (TOL_POS_PCT_H, TOL_ANG_DEG),
          max(float(pm.H_to_pct_h(err[k])) for k in ("h_H", "x_c_H", "o_H")) < TOL_POS_PCT_H
          and max(err["theta_deg"], err["phi_deg"]) < TOL_ANG_DEG,
          "max |err|: h %.5f H, x_c %.5f H, o %.5f H, theta %.3f deg, phi %.3f deg; %.2f s / frame"
          % (err["h_H"], err["x_c_H"], err["o_H"], err["theta_deg"], err["phi_deg"], dt / len(frames)))
    check("動作系列：h(t) の偽の減少量（M2／M3 の雑音下限）が 1e-4 H 未満", noise_h < 1e-4,
          "largest measured decrease of h where the analytic h never decreases: %.2e H; same for o: %.2e H" % (noise_h, noise_o))
    t = np.array(frames, dtype=np.float64)
    plots = []
    for name, meas, ana, unit in (("h(t)", h, an["h"], "H"), ("x_c(t)", xc, an["x_c"], "H"), ("theta(t)", th, an["theta"], "deg"),
                                 ("o(t)", o, an["o"], "H"), ("phi(t)", ph, an["phi"], "deg")):
        plots.append({"series": [{"label": "analytic", "x": t, "y": np.array(ana, dtype=np.float64), "color": "gray", "width": 5},
                                 {"label": "measured", "x": t, "y": meas, "color": "red", "width": 2, "marker": "o", "marker_size": 3}],
                      "title": "synthetic fixture: %s  (mask 965x649, exact crossings)" % name, "xlabel": "frame",
                      "ylabel": unit, "size": (1500, 330)})
    imgio.save_png(os.path.join(OUT, "fixture_motion_curves.png"), plot.multi_plot(plots, ncols=1))


# ============================================================================ K. hardening 2026-09-20: polyline level (numpy only)
PCT_H = 100.0 / 66.0 / 100.0          # 1 % of image height in H units (frame_h = 100 / 66 H)
WIDE, LOW_PCT = 1.05, 1.9             # the sceptic's 'wide_low:5:1.9': 5 % wider about the crest plumb line AND 1.9 % of image height lower


def turtle_wave(F, kinks=None, tip_kink=0.0, ds_pct=0.025, psi0=35.0, x_start=-0.80):
    """鈍い頭部を持つ滑らかな波を、弧長に沿う接線角の積分で作る。長さは画像高さの %、
    回転率は 1 % 当たりの度数で、正は反時計回り。滑らかな区間は 1 % 当たり最大 8 度なので
    清浄な S8 は 8 度。kinks は片名・片内位置・角度を指定して鋭角を頂点に置く。
    tip_kink=K は先端周囲の滑らかな K 度を先端の角へ移す。先端は最右点のまま。
    輪郭は Z=0 で終わり、静水面に沿って画面右端へ続く。"""
    pieces = [("back", 30.0, 0.0), ("crest_bend", 85.0 / 8.0, -8.0), ("head_top", 8.0, 0.0), ("to_tip", 8.0, -(40.0 - 0.5 * tip_kink) / 8.0),
              ("after_tip", 16.0, -(80.0 - 0.5 * tip_kink) / 16.0), ("underside", 6.0, 0.0), ("armpit", 15.0, 6.0), ("wall", 30.0, 0.0),
              ("toe", 70.0 / 6.0, 6.0), ("run_out", 60.0, 0.0)]
    kinks = list(kinks or []) + ([("after_tip", 0.0, -float(tip_kink))] if tip_kink else [])
    pts, psi = [np.zeros(2)], float(psi0)
    for name, length, rate in pieces:
        n = max(1, int(round(length / ds_pct)))
        d = length / n
        ks = [(pos, ang) for nm, pos, ang in kinks if nm == name]
        for i in range(n):
            for pos, ang in ks:
                if i == int(round(pos / d)):                 # the corner sits on the vertex at the start of edge i
                    psi += ang
            mid = math.radians(psi + 0.5 * rate * d)
            pts.append(pts[-1] + d * PCT_H * np.array([math.cos(mid), math.sin(mid)]))
            psi += rate * d
    p = np.array(pts)
    p[:, 1] += 1.0 - p[:, 1].max()
    p[:, 0] += x_start - p[0, 0]
    ic = int(np.argmax(p[:, 1]))
    k = ic + int(np.nonzero(p[ic:, 1] <= 0.0)[0][0])
    a, b = p[k - 1], p[k]
    toe = a + a[1] / (a[1] - b[1]) * (b - a)
    return np.concatenate([p[:k], [toe], [[F.x_right, 0.0]]])


def points_in_polygon(pts, poly):
    """ライブラリに依存しない偶奇規則の射線判定。真偽値配列を返す。"""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    x0, y0 = poly[:, 0][None, :], poly[:, 1][None, :]
    x1, y1 = np.roll(poly[:, 0], -1)[None, :], np.roll(poly[:, 1], -1)[None, :]
    cond = (y0 > y) != (y1 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xi = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
    return (np.sum(cond & (x < xi), axis=1) % 2) == 1


def poly_as_base(pts):
    """順序付き折線を pm.s7_deviation 用の基準輪郭辞書へ変換する。接合点はライブラリが検出する。"""
    m = pm.measure_profile(pts)
    i_c, i_t, i_e = m["landmarks"]["crest"]["index"], m["landmarks"]["head_tip"]["index"], m["landmarks"]["trough_end"]["index"]
    p = np.asarray(pts, dtype=np.float64)[:i_e + 1]
    seg = np.where(np.arange(len(p)) <= i_c, 0, np.where(np.arange(len(p)) <= i_t, 1, 2))
    return {"pts_H": p, "seg_id": seg, "in_S7": np.ones(len(p), bool), "crest_index": int(i_c), "tip_index": int(i_t),
            "names": ["back", "head", "inner_arc"]}, m


def test_hardening_polyline(F):
    # ---------------------------------------------------------------- 6. get_params: only 'entry absent' is caught
    import json
    P0 = pm.get_params()
    check("get_params：本プロジェクトの設定は DEFAULT_PARAMS と一致し、変更一覧は空（measure_profile も同様）",
          P0["non_default_params"] == {} and pm.measure_profile(lobed_test_polyline()[0])["non_default_params"] == {},
          str(P0["non_default_params"]))
    P1 = pm.get_params({"s8_tip_exclusion_pct_h": 3.0, "tip_rule": "max_reversal"})
    P2 = pm.get_params(P1)                                                        # a flat dict is a valid override
    check("get_params：既定値と異なる上書きは値・既定値・出典を列挙し、同じ値なら列挙しない",
          list(P1["non_default_params"]) == ["s8_tip_exclusion_pct_h"] and P1["non_default_params"]["s8_tip_exclusion_pct_h"]
          == {"value": 3.0, "default": 0.0, "source": "override"} and P2["non_default_params"] == P1["non_default_params"],
          str(P1["non_default_params"]))
    real_params, tmp = paths.PARAMS_JSON, os.path.join(OUT, "tmp_selftest_params.json")
    got = {}

    def with_params(text):
        with open(paths.ensure_parent(tmp), "w", encoding="utf-8") as fh:
            fh.write(text)
        paths.PARAMS_JSON = tmp
        paths.clear_cache()
        try:
            return pm.get_params()
        finally:
            paths.PARAMS_JSON = real_params
            paths.clear_cache()
    try:
        for label, text in (("malformed", '{"S8_sample_spacing_pct": {"value": 1.0},,}'), ("not_a_dict", '{"measure_params": {"value": [1, 2]}}'),
                            ("unknown_name", '{"measure_params": {"value": {"s8_tip_exclusion_pct": 3.0}}}'),
                            ("bad_spacing", '{"S8_sample_spacing_pct": {"value": "one"}}')):
            try:
                with_params(text)
                got[label] = "no exception"
            except Exception as ex:                                   # noqa: BLE001  (the TYPE is what is checked)
                got[label] = type(ex).__name__
        absent = with_params('{"WAVE_HEIGHT_M": {"value": 11.0}}')
        changed = with_params('{"S8_sample_spacing_pct": {"value": 1.5}, "measure_params": {"value": {"comment": "x", "trough_tol_pct_h": {"value": 0.5}}}}')
    finally:
        paths.PARAMS_JSON = real_params
        paths.clear_cache()
        if os.path.isfile(tmp):
            os.remove(tmp)
    check("get_params：不正な params.json・型違い・未知名・数値でない間隔はいずれも例外",
          got == {"malformed": "JSONDecodeError", "not_a_dict": "TypeError", "unknown_name": "ValueError", "bad_spacing": "ValueError"}, str(got))
    check("get_params：項目の欠落だけは既定値で補い、変更の印を付けない",
          absent["s8_spacing_pct_h"] == 1.0 and absent["non_default_params"] == {} and absent["trough_tol_pct_h"] == 0.3, str(absent["non_default_params"]))
    nd = changed["non_default_params"]
    check("get_params：params.json で変更した値は出典付きで示す（S8 の間隔も含む）",
          sorted(nd) == ["s8_spacing_pct_h", "trough_tol_pct_h"] and nd["trough_tol_pct_h"] == {"value": 0.5, "default": 0.3, "source": "params.json"}
          and nd["s8_spacing_pct_h"]["value"] == 1.5 and pm.get_params()["non_default_params"] == {}, json.dumps(nd))

    # ---------------------------------------------------------------- 3. trough level / S3 from the model's own trough
    lp, _knots = lobed_test_polyline()
    m0 = pm.measure_profile(lp)
    pc0 = pm.position_checks(m0)
    lvl = 3.0 * PCT_H
    i_d = m0["landmarks"]["inner_deepest"]["index"]
    raised = lp.copy()
    raised[i_d:, 1] = np.maximum(raised[i_d:, 1], lvl)                 # the sea in front of the wave stands 3 % higher
    m1 = pm.measure_profile(raised)
    pc1 = pm.position_checks(m1)
    e0, e1 = pc0["S3_from_model_trough"], pc1["S3_from_model_trough"]
    check("谷水位：清浄な折線は静水面に達し、S3_from_model_trough == S3",
          m0["reached_still_water"] is True and abs(m0["trough_level_H"]) < 1e-12 and abs(e0["height_err_pct_h"] - pc0["S3"]["height_err_pct_h"]) < 1e-9,
          "trough_level_H %.6f, S3 %.4f, from model trough %.4f" % (m0["trough_level_H"], pc0["S3"]["height_err_pct_h"], e0["height_err_pct_h"]))
    check("谷水位：水面を画像高さの 3 % 上げると Z=0 起点の S3 は不変で、谷起点は S3-3.000、静水面到達は偽",
          m1["reached_still_water"] is False and abs(m1["trough_level_H"] - lvl) < 1e-12 and abs(pc1["S3"]["height_err_pct_h"] - pc0["S3"]["height_err_pct_h"]) < 1e-9
          and abs(e1["height_err_pct_h"] - (pc0["S3"]["height_err_pct_h"] - 3.0)) < 1e-9 and abs(e1["trough_level_above_still_pct_h"] - 3.0) < 1e-9
          and abs(pc1["S3"]["height_err_from_model_trough_pct_h"] - e1["height_err_pct_h"]) < 1e-12,
          "S3 %.4f, S3_from_model_trough %.4f, trough level %.5f H (tolerance for 'reached': %.2f %% of image height)"
          % (pc1["S3"]["height_err_pct_h"], e1["height_err_pct_h"], m1["trough_level_H"], m1["reached_still_water_tol_pct_h"]))
    def floor_at(pct):
        q = lp.copy()
        q[i_d:, 1] = np.maximum(q[i_d:, 1], pct * PCT_H)
        return pm.measure_profile(q)
    check("谷水位：Z=0 より 0.29 % 上なら到達扱い（許容 0.3 %）、0.31 % 上なら未到達",
          floor_at(0.29)["reached_still_water"] is True and floor_at(0.31)["reached_still_water"] is False)

    # ---------------------------------------------------------------- 4. 相殺されない形状指標と符号付き S7
    # 初回実行前の符号予測：波頂鉛直線を中心に WIDE 倍に拡幅し、画像高さの LOW_PCT % 下げる。
    # 長さ／自己高さは WIDE／(1 - LOW_PCT×PCT_H) - 1 = +8.11 %、S3 は -LOW_PCT。
    # 一方、絶対高さで測る W.z75 の幅は負（この折線の解析式では -4.3 %）。これが相殺の原因。
    low = 1.0 - LOW_PCT * PCT_H
    expect = 100.0 * (WIDE / low - 1.0)
    x_c0 = m0["x_c"]
    wl = np.stack([x_c0 + WIDE * (lp[:, 0] - x_c0), low * lp[:, 1]], 1)
    mw = pm.measure_profile(wl)
    rows = {r["name"]: r for r in pm.compare_shape_descriptors(mw["shape"], m0["shape"])}
    names = ("o_over_h", "cavity_depth_over_h", "aspect_ratio", "aspect_ratio_h75", "h50.width_full_over_h", "h50.width_body_over_h",
             "h50.inner_from_crest_over_h", "h50.back_from_crest_over_h", "h75.width_full_over_h", "h75.back_from_crest_over_h",
             "h75.front_from_crest_over_h")
    worst = max(abs(rows[k]["diff_pct_of_target"] - expect) for k in names)
    wrow = {r["name"]: r for r in pm.compare_width_metrics(mw["W"], m0["W"])}
    s3w = pm.position_checks(mw)["S3"]["height_err_pct_h"] - pc0["S3"]["height_err_pct_h"]
    check("形状指標（自己高さ、報告専用）：幅×1.05・高さ−1.9 %% は全項目で %+.3f %%、絶対高さの W.z75 幅は負" % expect,
          worst < 0.05 and all(rows[k]["comparable"] for k in names) and wrow["z75.width_full_H"]["diff_pct_of_target"] < -3.0 and abs(s3w + LOW_PCT) < 1e-6,
          "max |reading - %.3f| = %.4f %% over %d entries; W.z75.width_full_H %+.2f %% (closed form -4.3 %%); S3 %+.3f"
          % (expect, worst, len(names), wrow["z75.width_full_H"]["diff_pct_of_target"], s3w))
    hs = m0["shape"]["sections"]["h50"]
    check("形状指標：垂れた頭部の折線で aspect_ratio = width_full(0.5 h) / h が解析式と一致",
          abs(m0["shape"]["aspect_ratio"] - (0.42 - (-0.8 + (0.5 - 0.3) / 0.7 * 0.8)) / 1.0) < 1e-9 and hs["back_clipped_at_frame_edge"] is False
          and abs(m0["shape"]["o_over_h"] - m0["o"]) < 1e-12, "aspect %.6f, o/h %.6f" % (m0["shape"]["aspect_ratio"], m0["shape"]["o_over_h"]))
    base_poly, _mb = poly_as_base(lp)
    bp_ = base_poly["pts_H"]
    u0 = (bp_[1] - bp_[0]) / np.hypot(*(bp_[1] - bp_[0]))                   # the body continues to the left of the frame edge along the back
    body = np.concatenate([[bp_[0] - 0.5 * u0], bp_, [[bp_[-1, 0], -1.0], [bp_[0, 0] - 2.0, -1.0]]])                       # target body as a closed polygon
    worst_sign, rep = 0.0, []
    for label, mdl in (("wide only", np.stack([x_c0 + WIDE * (lp[:, 0] - x_c0), lp[:, 1]], 1)), ("low only", np.stack([lp[:, 0], low * lp[:, 1]], 1)),
                       ("wide + low", wl)):
        mm = pm.measure_profile(mdl)
        dev = pm.s7_deviation(mdl, base_poly, mm)
        Cm = pm.Curve(mdl)
        for seg in ("back", "head", "inner_arc"):
            smp = Cm.sub(mm["segments_s"][seg][0], mm["segments_s"][seg][1], float(pm.pct_h_to_H(0.25)))
            d_ref, _e = pm.point_polyline_distance(smp, base_poly["pts_H"])
            outside = ~points_in_polygon(smp, body)
            ref = float(pm.H_to_pct_h(np.where(outside, d_ref, -d_ref).mean()))   # 内外は独立の多角形内判定による
            worst_sign = max(worst_sign, abs(ref - dev[seg]["model_to_base"]["signed_mean_pct_h"]))
        rep.append((label, dev))
    sw_, sl_, swl = rep[0][1], rep[1][1], rep[2][1]
    check("符号付き S7（報告専用、正は目標浪体の外側）：拡幅のみでは波背・頭部・内側弧が全て正で、波背では符号なし平均と一致。"
          "降下のみでは波背と頭部上面が負。拡幅と降下を併用すると波背は目標を横切り（p05<0<p95）、符号付き平均の絶対値は符号なし平均より小さい",
          all(sw_[k]["signed_mean_dev_pct_h"] > 0 for k in ("back", "head", "inner_arc"))
          and abs(sw_["back"]["signed_mean_dev_pct_h"] - sw_["back"]["model_to_base"]["mean_pct_h"]) < 1e-9
          and sl_["back"]["signed_mean_dev_pct_h"] < 0 and abs(sl_["back"]["signed_mean_dev_pct_h"] + sl_["back"]["model_to_base"]["mean_pct_h"]) < 1e-9
          and sl_["head"]["signed_mean_dev_pct_h"] < 0
          and swl["back"]["model_to_base"]["signed_p05_pct_h"] < 0 < swl["back"]["model_to_base"]["signed_p95_pct_h"]
          and abs(swl["back"]["signed_mean_dev_pct_h"]) < 0.3 * swl["back"]["mean_dev_pct_h"] and swl["back"]["mean_dev_pct_h"] < 1.0,
          "wide: %+.3f / %+.3f / %+.3f; low: %+.3f / %+.3f / %+.3f; wide + low back: signed %+.3f, unsigned %.3f (spec limit 1), p05 %+.3f, p95 %+.3f"
          % (tuple(sw_[k]["signed_mean_dev_pct_h"] for k in ("back", "head", "inner_arc")) + tuple(sl_[k]["signed_mean_dev_pct_h"] for k in ("back", "head", "inner_arc"))
             + (swl["back"]["signed_mean_dev_pct_h"], swl["back"]["mean_dev_pct_h"], swl["back"]["model_to_base"]["signed_p05_pct_h"],
                swl["back"]["model_to_base"]["signed_p95_pct_h"])))
    check("符号付き S7：全モデル標本の内外が独立した多角形内判定と一致（区間と変形の 9 事例）",
          worst_sign < 0.02, "max |library - independent| signed mean = %.2e %% of image height (a wrong side would show as ~0.5 %%)" % worst_sign)
    REPORT["hardening_wide_low_polyline"] = {"expected_pct": expect, "shape_rows": [rows[k] for k in names], "W_z75_width_pct": wrow["z75.width_full_H"]["diff_pct_of_target"],
                                             "signed_S7": {lab: {k: dv[k]["signed_mean_dev_pct_h"] for k in ("back", "head", "inner_arc")} for lab, dv in rep}}

    # ---------------------------------------------------------------- 5. S8 across-tip enforcement and remaining blind spots
    res = {}
    for label, kw in (("smooth", {}), ("pointed tip 40 deg", {"tip_kink": 40.0}), ("back kink 17 deg between the phases", {"kinks": [("back", 10.125, 17.0)]}),
                      ("back kink 17 deg on a phase sample", {"kinks": [("back", 10.25, 17.0)]}),
                      ("kink 20 deg AGAINST the 8 deg / % crest bend", {"kinks": [("crest_bend", 5.125, 20.0)]})):
        s8 = pm.measure_profile(turtle_wave(F, **kw))["S8"]
        vw = s8["vertex_window_turn"]
        res[label] = {"judged": s8["max_tangent_diff_deg"], "unexcluded": s8["max_unexcluded_deg"], "unexcluded_old": s8["max_unexcluded_without_tip_junction_deg"],
                      "tip_junction": s8["tip_junction_deg"], "vw": s8["max_vertex_window_turn_deg"], "vw_outside": vw["max_outside_tip_exclusion_deg"],
                      "vw_across_tip": vw["across_tip_deg"], "vw_back": vw["per_segment"].get("back"),
                      "short": {str(w["window_pct_h"]): w["max_outside_tip_exclusion_deg"] for w in vw["short_windows"]}}
    a, b, c, d, e = (res[k] for k in res)
    check("滑らかで鈍い先端の S8（1 % 当たりの転角 <=8 度）：判定値と頂点窓は 8 度、先端接合点は 5 度",
          abs(a["judged"] - 8.0) < 0.01 and abs(a["vw"] - 8.0) < 0.25 and abs(abs(a["tip_junction"]) - 5.0) < 0.01 and a["unexcluded"] == a["unexcluded_old"],
          "判定 %.3f、頂点窓 %.3f、先端接合点 %.3f" % (a["judged"], a["vw"], a["tip_junction"]))
    check("尖った先端の S8（先端に 40 度の角）：判定値と先端をまたぐ頂点窓は 40 度超。"
          "先端接合点を除く旧最大値は 8 度のまま",
          b["judged"] > 40.0 and abs(b["judged"] - b["unexcluded"]) < 1e-9 and abs(b["unexcluded_old"] - 8.0) < 0.01 and b["vw_across_tip"] > 40.0
          and abs(b["vw_outside"] - a["vw_outside"]) < 1e-9,
          "判定 %.2f、除外なし旧 %.2f→新 %.2f、先端をまたぐ値 %.2f" % (b["judged"], b["unexcluded_old"], b["unexcluded"], b["vw_across_tip"]))
    check("S8 の盲点・弦による平滑化：位相標本の中間にある 17 度の折れは判定値 %.2f（15 未満で合格）。標本上なら 17 度。"
          "頂点窓の最大値はいずれも 17 度" % c["judged"],
          c["judged"] < 15.0 and abs(d["judged"] - 17.0) < 0.01 and abs(c["vw"] - 17.0) < 0.01 and abs(d["vw"] - 17.0) < 0.01 and abs(c["vw_back"] - 17.0) < 0.01,
          "位相間：判定 %.3f、頂点窓 %.3f。標本上：判定 %.3f、頂点窓 %.3f" % (c["judged"], c["vw"], d["judged"], d["vw"]))
    check("S8 の盲点・曲率と逆向きの折れ（20 度対 8 度／%）：判定と 1 % 窓は 12 度、短い窓は 0.5 % で 16 度、0.25 % で 18 度",
          e["judged"] < 13.0 and abs(e["vw_outside"] - 12.0) < 0.3 and abs(e["short"]["0.5"] - 16.0) < 0.3 and abs(e["short"]["0.25"] - 18.0) < 0.3
          and abs(a["short"]["0.25"] - 2.0) < 0.3,
          "判定 %.2f、窓 1／0.5／0.25 %%：%.2f／%.2f／%.2f（滑らかな輪郭：%.2f／%.2f／%.2f）"
          % (e["judged"], e["vw_outside"], e["short"]["0.5"], e["short"]["0.25"], a["vw_outside"], a["short"]["0.5"], a["short"]["0.25"]))
    # 3 頂点の角と 180 度超の渦に対する vertex_window_turns の解析式
    sq = np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.2], [0.8, 0.2]])
    _a, _b, t_all = pm.vertex_window_turns(sq, 0.0, 99.0, 99.0)
    _a, _b, t_w = pm.vertex_window_turns(sq, 0.0, 99.0, 1.0)
    check("vertex_window_turns：四角い渦は一窓で +360 度（折り返さない）。一辺長の窓には 90 度の角が二つ入る",
          abs(t_all[0] - 360.0) < 1e-9 and abs(np.abs(t_w).max() - 180.0) < 1e-9, "合計 %.1f、長さ 1 の窓での最大 %.1f" % (t_all[0], np.abs(t_w).max()))
    REPORT["hardening_S8_blind_spots"] = res


# ============================================================================ J. hardening 2026-09-20: mesh level
def test_hardening_mesh(F):
    H = F.H
    fr = msw.FRAME_START + msw.N_FRAMES_DEFAULT - 1
    sw = msw.SyntheticWave(H=H)
    verts, tris = sw.vertices(fr), sw.triangles
    rect = silhouette.ViewRect.from_cam_print(H=H, scale=1.0)
    mask0, info0 = silhouette.mask_from_triangles(verts, tris, rect, 0.0)
    prof0 = silhouette.extract_profile(mask0, rect, edges=info0.pop("edges"))
    met0 = pm.measure_profile(prof0["H"])
    c0 = prof0["components"]
    check("清浄な形状：有限でない頂点 0、除外三角形 0、除外成分 0、水面到達あり",
          info0["n_nonfinite_vertices"] == 0 and info0["n_dropped_triangles"] == 0 and c0["n_removed"] == 0 and c0["removed_area_px"] == 0
          and c0["removed"] == [] and met0["reached_still_water"] is True and abs(met0["trough_level_H"]) < 2e-3,
          "trough level %.5f H; speck limit %.2f px at full resolution" % (met0["trough_level_H"], c0["speck_max_area_px"]))

    # ---- 1. NaN vertex (numpy path): middle of the back on the centre row, like the sceptic's attack
    idx = (sw.n_v // 2) * sw.n_u + sw.n_u // 4
    vn = verts.copy()
    vn[idx] = np.nan
    n_expect = int((tris == idx).any(axis=1).sum())
    mask1, info1 = silhouette.mask_from_triangles(vn, tris, rect, 0.0)
    prof1 = silhouette.extract_profile(mask1, rect, edges=info1.pop("edges"))
    met1 = pm.measure_profile(prof1["H"])
    same = max(abs(met1[k] - met0[k]) for k in ("h", "x_c", "theta", "o", "phi_deg"))
    check("NaN 頂点（NumPy 経路）：有限でない頂点 1 個と使用三角形 %d 個を計数。通常指標は見逃す" % n_expect,
          info1["n_nonfinite_vertices"] == 1 and info1["n_dropped_triangles"] == n_expect and n_expect >= 4 and info1["nonfinite_vertex_indices"] == [idx]
          and info1["n_nonfinite"] == 0 and same < 1e-6,
          "mask differs in %d px, max metric difference %.2e (this is why the counts must be looked at)" % (int((mask1 != mask0).sum()), same))
    vi = verts.copy()
    vi[idx, 1] = np.inf                                                       # only Y is broken: X and Z would project fine
    _m, info_inf = silhouette.mask_from_triangles(vi, tris, rect.scaled(0.25), 0.0, exact=False)
    check("Y 座標だけの inf も計数される", info_inf["n_nonfinite_vertices"] == 1 and info_inf["n_dropped_triangles"] == n_expect)

    # ---- 2. detached island in the cavity + a rasterisation speck, full resolution and half resolution
    def quad(x0, x1, z0, z1):
        return np.array([[x0, 0.0, z0], [x1, 0.0, z0], [x1, 0.0, z1], [x0, 0.0, z1]]) * H
    isl, spk = (0.20, 0.27, 0.25, 0.35), (0.600, 0.602, 0.500, 0.502)          # H units; the speck is 3.4 x 3.4 px at full resolution
    v2 = np.concatenate([verts, quad(*isl), quad(*spk)])
    n0 = verts.shape[0]
    t2 = np.concatenate([tris, [[n0, n0 + 1, n0 + 2], [n0, n0 + 2, n0 + 3], [n0 + 4, n0 + 5, n0 + 6], [n0 + 4, n0 + 6, n0 + 7]]])
    out = {}
    for sc in (1.0, 0.5):
        r = rect if sc == 1.0 else silhouette.ViewRect.from_cam_print(H=H, scale=sc)
        mk, inf = silhouette.mask_from_triangles(v2, t2, r, 0.0)
        pf = silhouette.extract_profile(mk, r, edges=inf.pop("edges"))
        out[sc] = (pf["components"], pm.measure_profile(pf["H"]))
    comp, met2 = out[1.0]
    big = comp["removed"][0]
    px_H = 1.0 / float(F.px_per_H)
    area_expect = (isl[1] - isl[0]) * (isl[3] - isl[2]) * float(F.px_per_H) ** 2
    same2 = max(abs(met2[k] - met0[k]) for k in ("h", "x_c", "theta", "o", "phi_deg"))
    check("空洞内の分離物体と微小領域（フル解像度）：除外 2 件の面積・範囲を報告し、通常指標は見逃す",
          comp["n_removed"] == 2 and comp["n_removed_islands"] == 1 and comp["n_removed_specks"] == 1 and big["kind"] == "island"
          and comp["removed"][1]["kind"] == "speck" and abs(big["area_px"] - area_expect) / area_expect < 0.02
          and max(abs(u - v) for u, v in zip(big["bbox_H"], (isl[0], isl[2], isl[1], isl[3]))) < 1.01 * px_H
          and comp["removed_area_px"] == big["area_px"] + comp["removed"][1]["area_px"] and comp["removed_islands_area_px"] == big["area_px"]
          and abs(comp["speck_max_area_px"] - 25.0) < 1e-6 and 0 < comp["removed"][1]["area_px"] < 25 and same2 < 1e-6,
          "island %d px (expected %.0f), bbox_H %s, bbox_px %s; speck %d px; limit %.1f px; max metric difference %.2e"
          % (big["area_px"], area_expect, [round(v, 4) for v in big["bbox_H"]], big["bbox_px"], comp["removed"][1]["area_px"], comp["speck_max_area_px"], same2))
    comp_h = out[0.5][0]
    check("微小領域の上限は解像度に比例（半解像度で 25/4 px）。同じ分離物体と小斑を区別する",
          abs(comp_h["speck_max_area_px"] - 6.25) < 0.02 and comp_h["n_removed_islands"] == 1 and comp_h["n_removed"] - comp_h["n_removed_specks"] == 1
          and abs(comp_h["removed"][0]["area_px"] - area_expect / 4.0) / (area_expect / 4.0) < 0.04,
          "limit %.3f px; removed %s" % (comp_h["speck_max_area_px"], [(c["kind"], c["area_px"]) for c in comp_h["removed"]]))

    # ---- 3. raised floor: the sea in front of the wave stands 3 % of image height above Z = 0 (the sceptic's 'Floor' object)
    v3 = np.concatenate([verts, quad(0.10, 1.60, -0.02, 3.0 * PCT_H)])
    t3 = np.concatenate([tris, [[n0, n0 + 1, n0 + 2], [n0, n0 + 2, n0 + 3]]])
    mk3, inf3 = silhouette.mask_from_triangles(v3, t3, rect, 0.0)
    pf3 = silhouette.extract_profile(mk3, rect, edges=inf3.pop("edges"))
    met3 = pm.measure_profile(pf3["H"])
    pc0, pc3 = pm.position_checks(met0), pm.position_checks(met3)
    check("水面を 3 % 上げる：Z=0 起点の S3 は不変、谷起点は -3.00、静水面未到達、成分除外なし",
          abs(pc3["S3"]["height_err_pct_h"] - pc0["S3"]["height_err_pct_h"]) < 0.01
          and abs(pc3["S3_from_model_trough"]["height_err_pct_h"] - (pc0["S3_from_model_trough"]["height_err_pct_h"] - 3.0)) < 0.05
          and met3["reached_still_water"] is False and abs(met3["trough_level_above_still_pct_h"] - 3.0) < 0.05 and pf3["components"]["n_removed"] == 0,
          "S3 %.3f -> %.3f; S3_from_model_trough %.3f -> %.3f; trough level %.3f %% of image height above Z = 0"
          % (pc0["S3"]["height_err_pct_h"], pc3["S3"]["height_err_pct_h"], pc0["S3_from_model_trough"]["height_err_pct_h"],
             pc3["S3_from_model_trough"]["height_err_pct_h"], met3["trough_level_above_still_pct_h"]))

    # ---- 4. wide + low variant of the fixture THROUGH mesh and mask (expected signs written before the first run, see group K)
    low = 1.0 - LOW_PCT * PCT_H
    expect = 100.0 * (WIDE / low - 1.0)
    v4 = verts * [WIDE, 1.0, low]                                              # the fixture's crest is on X = 0
    rh = silhouette.ViewRect.from_cam_print(H=H, scale=0.5)
    res = []
    for vv in (verts, v4):
        mk, inf = silhouette.mask_from_triangles(vv, tris, rh, 0.0)
        pf = silhouette.extract_profile(mk, rh, edges=inf.pop("edges"))
        res.append((pf, pm.measure_profile(pf["H"])))
    (pfa, ma), (pfb, mb) = res
    rows = {r["name"]: r for r in pm.compare_shape_descriptors(mb["shape"], ma["shape"])}
    names = [k for k in ("o_over_h", "cavity_depth_over_h", "aspect_ratio_h75", "h75.width_full_over_h", "h75.back_from_crest_over_h",
                         "h75.front_from_crest_over_h", "aspect_ratio", "h50.width_full_over_h", "h50.back_from_crest_over_h") if rows[k]["comparable"]]
    worst = max(abs(rows[k]["diff_pct_of_target"] - expect) for k in names)
    wz = {r["name"]: r for r in pm.compare_width_metrics(mb["W"], ma["W"])}["z75.width_full_H"]["diff_pct_of_target"]
    bc = pm.load_base_contour(msw.SYNTHETIC_CONTOUR_JSON)
    dev = pm.s7_deviation(pfb["H"], bc, mb)
    pcb = pm.position_checks(mb, bc)
    check("幅×1.05・高さ−1.9 %% の形状を網目とマスクで測る：自己高さ指標は %+.2f %%（±0.3）、S1.dz と S3 は -1.9、絶対高さの W.z75 幅は +5 未満" % expect,
          len(names) >= 6 and worst < 0.3 and abs(pcb["S3"]["height_err_pct_h"] + LOW_PCT) < 0.05 and abs(pcb["S1"]["vs_spec"]["dz_pct_h"] + LOW_PCT) < 0.05
          and wz < 4.0 and all(dev[k]["signed_mean_dev_pct_h"] is not None for k in ("back", "head", "inner_arc")),
          "max |reading - %.2f| = %.3f %% over %s; W.z75.width_full_H %+.2f %%; S3 %+.3f; signed S7 back / head / inner %+.3f / %+.3f / %+.3f (unsigned %.3f / %.3f / %.3f)"
          % (expect, worst, names, wz, pcb["S3"]["height_err_pct_h"], dev["back"]["signed_mean_dev_pct_h"], dev["head"]["signed_mean_dev_pct_h"],
             dev["inner_arc"]["signed_mean_dev_pct_h"], dev["back"]["mean_dev_pct_h"], dev["head"]["mean_dev_pct_h"], dev["inner_arc"]["mean_dev_pct_h"]))
    REPORT["hardening_mesh"] = {"nan_vertex": {k: info1[k] for k in ("n_nonfinite_vertices", "n_dropped_triangles", "nonfinite_vertex_indices")},
                                "island": comp, "island_half_res": comp_h, "raised_floor": pc3["S3_from_model_trough"],
                                "wide_low": {"expected_pct": expect, "rows": [rows[k] for k in names], "W_z75_width_pct": wz,
                                             "signed_S7": {k: dev[k]["signed_mean_dev_pct_h"] for k in ("back", "head", "inner_arc")}}}
    # 指標から見えない三欠陥（分離物体、微小領域、上げた水面）の重ね描き記録
    y_w = float(rect.world_to_px(0.0, 0.0)[1])
    extra = [{"px": np.array([[0.0, y_w], [float(rect.width_px), y_w]]), "color": "green", "width": 1.5, "dash": (10, 8)}]
    for rc in comp["removed"]:
        x0, y0, x1, y1 = rc["bbox_px"]
        pad = 0 if rc["kind"] == "island" else 14                                # the speck is 4 px: draw its box larger so that it can be seen
        extra.append({"px": np.array([[x0 - pad, y0 - pad], [x1 + pad, y0 - pad], [x1 + pad, y1 + pad], [x0 - pad, y1 + pad], [x0 - pad, y0 - pad]], dtype=np.float64),
                      "color": "red" if rc["kind"] == "island" else "orange", "width": 2.0})
    img = silhouette.draw_overlay(mk3 | out_mask_of(v2, t2, rect), pf3, met3, extra_polylines=extra,
                                  title="HARDENING DEMO: what the contour cannot show is REPORTED (island, speck, raised floor)")
    k = img.shape[1] / float(rect.width_px)
    big_, spk_ = comp["removed"][0], comp["removed"][1]
    draw.text(img, k * big_["bbox_px"][2] + 8, k * big_["bbox_px"][1], "ISLAND (red box = reported bbox): %d px, removed from the\ncontour, metrics unchanged -> components['n_removed_islands'] = %d"
              % (big_["area_px"], comp["n_removed_islands"]), "red", 2, bg="white")
    draw.text(img, k * 0.5 * (spk_["bbox_px"][0] + spk_["bbox_px"][2]), k * spk_["bbox_px"][3] + 16,
              "SPECK (orange box, enlarged): %d px < limit %.0f px" % (spk_["area_px"], comp["speck_max_area_px"]), "orange", 2, bg="white", anchor="ct")
    draw.text(img, img.shape[1] - 8, k * y_w + 6, "green dashes: Z = 0 (still water)", "green", 2, bg="white", anchor="rt")
    draw.text(img, img.shape[1] - 8, k * float(rect.world_to_px(0.0, 3.0 * PCT_H * H)[1]) - 8,
              "RAISED FLOOR: trough_level = %.2f %% of image height above Z = 0\nS3 from Z = 0: %+.2f   S3_from_model_trough: %+.2f"
              % (met3["trough_level_above_still_pct_h"], pc3["S3"]["height_err_pct_h"], pc3["S3_from_model_trough"]["height_err_pct_h"]), "blue", 2, bg="white", anchor="rb")
    imgio.save_png(os.path.join(OUT, "hardening_island_floor.png"), img)

    # ---- 1b. NaN vertex through Blender (shape key of the final frame), silhouette_mask + profiles_over_frames
    scene = bootstrap.reset_scene()
    obj, sw2 = msw.build_object(scene, 2, "clip", H)
    idx2 = (sw2.n_v // 2) * sw2.n_u + sw2.n_u // 4
    obj.data.shape_keys.key_blocks[-1].data[idx2].co = (float("nan"), float("nan"), float("nan"))
    scene.frame_set(2)
    rq = silhouette.ViewRect.from_cam_print(H=H, scale=0.25)
    _v, _t, minfo = silhouette.mesh_world_triangles(obj)
    _mk, binfo = silhouette.silhouette_mask(obj, rect=rq)
    seq = silhouette.profiles_over_frames(obj, [1, 2], scene=scene, rect=rq)
    check("NaN 頂点（Blender 評価済みシェイプキー）：三つの処理経路が全て報告（第1フレーム清浄、第2フレームに 1 頂点）",
          minfo["n_nonfinite_vertices"] == 1 and 4 <= minfo["n_dropped_triangles"] <= 8 and minfo["objects"][0]["n_nonfinite_vertices"] == 1
          and binfo["n_nonfinite_vertices"] == 1 and binfo["n_dropped_triangles"] == minfo["n_dropped_triangles"]
          and seq[0]["n_nonfinite_vertices"] == 0 and seq[0]["n_dropped_triangles"] == 0 and seq[1]["n_nonfinite_vertices"] == 1
          and seq[1]["n_dropped_triangles"] == minfo["n_dropped_triangles"] and not np.isnan(_v[_t]).any(),
          "vertex %d: %d triangles dropped of %d" % (idx2, minfo["n_dropped_triangles"], minfo["n_triangles"] + minfo["n_dropped_triangles"]))


def out_mask_of(verts, tris, rect):
    return silhouette.mask_from_triangles(verts, tris, rect, 0.0, exact=False)[0]


# ============================================================================ definition diagrams
def save_definition_diagrams(F):
    dense, _ids, info = msw.profile_points(1.0, dense_ds=2e-4)
    ref, _ = clipped_reference_curve(1.0, F)
    m = pm.measure_profile(ref)
    P = pm.get_params()
    C = pm.Curve(ref)

    def make(x0, x1, z0, z1, width, fname, zoom_labels):
        S = width / (x1 - x0)
        hpx = int(round((z1 - z0) * S))
        img = draw.canvas(hpx, width)
        to = lambda p: np.stack([(np.asarray(p)[..., 0] - x0) * S, (z1 - np.asarray(p)[..., 1]) * S], -1)
        draw.hline(img, to(np.array([0.0, 0.0]))[1], "cyan", 2)
        draw.vline(img, to(np.array([m["x_c"], 0.0]))[0], "lightgray", 2, dash=(8, 8))
        segs = m["segments_s"]
        s_t = m["landmarks"]["head_tip"]["s"]
        band = 13 if zoom_labels else 17
        # 帯を輪郭の下に先に描く：S8 除外域、phi 窓、S4 窓
        ex = float(pm.pct_h_to_H(P["s8_tip_exclusion_pct_h"]))
        draw.polyline(img, to(C.slice_pts(s_t - ex, s_t + ex)), "yellow", band + 8)
        ph = m["phi"]
        draw.polyline(img, to(C.slice_pts(*ph["window_s"])), "lime", band)
        b0, b1 = (float(pm.pct_h_to_H(v)) for v in P["s4_before_crest_window_pct_h"])
        s_c = m["landmarks"]["crest"]["s"]
        draw.polyline(img, to(C.slice_pts(s_c - b1, s_c - b0)), "cyan", band)
        draw.polyline(img, to(C.slice_pts(0.0, float(pm.pct_h_to_H(P["s4_left_window_pct_h"])))), "cyan", band)
        s_th = m["landmarks"]["theta_point"]["s"]
        wth = float(pm.pct_h_to_H(P["theta_window_pct_h"]))
        draw.polyline(img, to(C.slice_pts(s_th - wth / 2, s_th + wth / 2)), "pink", band)
        for nm, col in (("back", "red"), ("head", "orange"), ("inner_arc", "magenta"), ("trough_run", "blue")):
            if segs.get(nm):
                draw.polyline(img, to(C.slice_pts(*segs[nm])), col, 3)
        p1 = np.array(ph["p1_H"])
        dirv = np.array([math.cos(math.radians(ph["deg"])), math.sin(math.radians(ph["deg"]))])
        draw.line(img, to(p1), to(p1 + dirv * 0.12), "green", 2, dash=(6, 5))
        draw.line(img, *to(C.at(np.array([s_th - wth / 2, s_th + wth / 2]))), "brown", 2, dash=(5, 4))
        if m["S4"]["mid_max_at"]:
            draw.marker(img, to(np.array(m["S4"]["mid_max_at"]["H"])), "s", 6, "blue")
        for key, label, col, off in (("crest", "crest (S1): max Z; x from level-set bisectors", "red", (14, -30)),
                                     ("head_tip", "head tip (S5): right-most point", "green", (18, -8)),
                                     ("inner_deepest", "inner-arc deepest (S2): left-most point", "purple", (16, 0)),
                                     ("trough_end", "trough end", "navy", (-10, -34))):
            draw.label_point(img, to(np.array(m["landmarks"][key]["H"])), label if zoom_labels else label.split(" (")[0].split(":")[0],
                             col, 2, off)
        tip = np.array(m["landmarks"]["head_tip"]["H"])
        crest = np.array(m["landmarks"]["crest"]["H"])
        yo = to(tip)[1] + 46
        draw.line(img, (to(crest)[0], yo), (to(tip)[0], yo), "darkgray", 2)
        draw.text(img, 0.5 * (to(crest)[0] + to(tip)[0]), yo + 4, "o = X_tip - X_crest = %.3f H" % m["o"], "darkgray", 2, anchor="ct")
        legend = ["contour: red = back | orange = head | magenta = inner arc | blue = run along the water",
                  "lime band = phi window (%.0f..%.0f %% H of arc length before the tip); green dashes = phi = %.1f deg"
                  % (100 * P["phi_skip_H"], 100 * (P["phi_skip_H"] + P["phi_len_H"]), m["phi_deg"]),
                  "yellow band = S8 exclusion zone around the tip (+-%.0f %% of image height of arc length)" % P["s8_tip_exclusion_pct_h"],
                  "pink band + brown dashes = chord with the steepest front inclination: theta = %.1f deg" % m["theta"],
                  "cyan bands = S4 windows (left end, before crest); blue square = steepest point of the back"]
        draw.text(img, 8, hpx - 8, "\n".join(legend), "black", 2, bg="white", anchor="lb", bg_alpha=0.9)
        imgio.save_png(os.path.join(OUT, fname), img)

    make(F.x_left, 1.0, -0.22, 1.1, 1600, "definitions_overview.png", True)
    make(0.10, 0.50, 0.56, 0.92, 1500, "definitions_head_zoom.png", False)


# ============================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--skip-cycles", action="store_true")
    ap.add_argument("--skip-perf", action="store_true")
    args = bootstrap.parse_args(ap)
    F = frame.get_frame()
    t_all = time.perf_counter()
    REPORT["environment"] = {"blender": bootstrap.blender_version(), "numpy": np.__version__,
                             "python": sys.version.split()[0], "frame": F.summary(), "measure_params": pm.get_params()}
    with bootstrap.Timer("A rasteriser unit tests"):
        test_rasteriser()
    with bootstrap.Timer("B mask utilities"):
        test_mask_utils()
    with bootstrap.Timer("C metrics on analytic curves"):
        bc = test_metrics_analytic(F)
    with bootstrap.Timer("C2 head-tip rule, segmentation check, report-only widths"):
        test_tip_rule_and_widths(F)
    with bootstrap.Timer("definition diagrams"):
        save_definition_diagrams(F)
    with bootstrap.Timer("D fixture through Blender"):
        scene, obj, sw, final_pack = test_fixture(F, bc, args.quick)
    with bootstrap.Timer("I motion series"):
        test_motion_series(scene, obj, sw, F)
    with bootstrap.Timer("E failure demos"):
        test_failure_demos(F)
    if not args.skip_cycles:
        with bootstrap.Timer("F Cycles cross-check"):
            test_cycles(scene, obj, final_pack, F)
    if not args.skip_perf:
        with bootstrap.Timer("G performance"):
            test_performance(F)
    with bootstrap.Timer("H profile-json mode"):
        test_profile_json(F, bc)
    with bootstrap.Timer("K hardening: get_params, trough level, shape descriptors, signed S7, S8 blind spots (polylines)"):
        test_hardening_polyline(F)
    with bootstrap.Timer("J hardening: NaN vertex, island / speck, raised floor, wide + low fixture (mesh and mask)"):
        test_hardening_mesh(F)
    n_fail = sum(1 for c in CHECKS if not c["pass"])
    REPORT["n_checks"] = len(CHECKS)
    REPORT["n_failed"] = n_fail
    REPORT["seconds_total"] = time.perf_counter() - t_all
    paths.write_json(os.path.join(OUT, "selftest_measure_report.json"), jsonable(REPORT))
    log("%d 件検証、%d 件失敗、%.1f 秒。報告：%s" % (len(CHECKS), n_fail, REPORT["seconds_total"],
                                                      paths.norm(os.path.join(OUT, "selftest_measure_report.json"))))
    bootstrap.finish(n_fail == 0, "selftest_measure")


if __name__ == "__main__":
    main()
