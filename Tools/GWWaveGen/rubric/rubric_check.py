# -*- coding: utf-8 -*-
"""Q20 final-frame rubric: numeric checks F01-F08, F10-F13 on a K*-format grid (rows npz: A, Y, c; 400 cols x N rows,
K* 26修正01 section frame).  F09 (second crest) and F14 (visual review) are judged with the Q16 S-checks and the
review protocol in rubric_ja.md.

py -3.10 rubric_check.py <rows.npz> <out.json> [--gate] [--ref <ref_cache.npz>] [--jtip 200]
  --gate : run the painting-view envelope evaluator (gw_wavegen_v1.preview_metrics, items 78/130/131/132/72)
  --ref  : aligned reference-model cache (temporary, from bl_rubric_views.py) for the F13 proximity check

Every threshold is written next to its check (MUST = the frame is not accepted if it fails; TARGET = the aim).
The painting gate F01 has priority: if a MUST elsewhere can only be met by breaking F01, record it and ask.

2026-09-29 (Design 28R01, refine loop R3): this file is the repository copy of Unity/Build/Q20/rubric/tools/rubric_check.py
(SHA-256 49ce8eaf...431a before the change below; the R2 evaluation table was re-made with that copy and did not change,
Unity/Build/Q20H/final/_work/R3/rubric_repro_R2.json).  Then F03 was relaxed (coordinator decision under Q24): shell
thickness MUST <= 0.34 H -> <= 0.42 H and wall 0.5H MUST <= 0.36 -> <= 0.42, so that filling the plan-view waist of the
back (user Q21: no waist, full body) is not blocked by our own provisional numbers.  Targets unchanged.
"""
import sys, os, json, math
import numpy as np
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rubric_measure as RM

REPO = r"G:\Unity\GreatWave_2026_Fresh"
H0_REF = 20.75                     # K* 26修正01 main-section crest height (the painting scale; keep for K*')
SEAT = np.array([3.954, 1.832, -15.031])
UP = np.array([0, 1.0, 0])


# ------------------------------------------------------------------ helpers on one row polyline (a, y)
def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


def corner_q17(a, y, jmax):
    """Q17 definitions: top = highest vertex among columns < jmax; +-2 m chord angle; Rmin (0.1 m resample, 3-tap,
    within +-3 m of the top); fold = largest single-vertex turn within +-12 columns of the top."""
    jm = int(np.argmax(y[:jmax])); s = arclen(a, y); T0 = np.array([a[jm], y[jm]])
    def at(sq): return np.array([np.interp(sq, s, a), np.interp(sq, s, y)])
    pb, pf = at(s[jm] - 2.0), at(s[jm] + 2.0); vb, vf = pb - T0, pf - T0
    ch2 = math.degrees(math.acos(np.clip(vb @ vf / np.linalg.norm(vb) / np.linalg.norm(vf), -1, 1)))
    ss = np.arange(max(s[jm] - 3, 0), min(s[jm] + 3, s[-1]), 0.1)
    P = np.stack([np.interp(ss, s, a), np.interp(ss, s, y)], -1)
    d1 = np.gradient(P, 0.1, axis=0); d2 = np.gradient(d1, 0.1, axis=0)
    k = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-12)
    ks = np.convolve(k, np.ones(3) / 3, "same")
    rmin = 1.0 / max(-ks.min(), 1e-9)
    fold = 0.0
    for j in range(max(jm - 12, 1), min(jm + 13, len(a) - 1)):
        v0 = np.array([a[j] - a[j - 1], y[j] - y[j - 1]]); v1 = np.array([a[j + 1] - a[j], y[j + 1] - y[j]])
        if np.linalg.norm(v0) < 1e-9 or np.linalg.norm(v1) < 1e-9:
            continue
        fold = max(fold, abs(math.degrees(math.atan2(v0[0] * v1[1] - v0[1] * v1[0], v0 @ v1))))
    return {"top_col": jm, "chord2_deg": ch2, "Rmin_m": float(rmin), "fold_deg": float(fold)}


def longest_straight(a, y, lo, hi, tol=6.0):
    """longest arc (m) of the polyline section between heights lo..hi whose heading stays within tol degrees."""
    s = arclen(a, y)
    if s[-1] < 1:
        return 0.0
    ss = np.arange(0, s[-1], 0.05); aa = np.interp(ss, s, a); yy = np.interp(ss, s, y)
    aa, yy = gaussian_filter1d(aa, 2), gaussian_filter1d(yy, 2)
    h = np.degrees(np.unwrap(np.arctan2(np.gradient(yy), np.gradient(aa))))
    ok = (yy >= lo) & (yy <= hi)
    best = 0.0; j0 = 0
    for j1 in range(len(h)):
        if not ok[j1]:
            j0 = j1 + 1; continue
        while j0 < j1 and h[j0:j1 + 1].max() - h[j0:j1 + 1].min() > tol:
            j0 += 1
        best = max(best, ss[j1] - ss[j0])
    return float(best)


def section_area(a, y):
    """area of the water above y = 0 enclosed by the row polyline (the cavity under the lip is outside)."""
    yy = np.maximum(y, 0.0)
    return float(abs(0.5 * np.sum(a[:-1] * yy[1:] - a[1:] * yy[:-1])))


def foot_plinth(a, y, jtip):
    """front surface below 4 m (columns after the lip tip): steepest slope and vertical steps."""
    j = np.arange(jtip, len(a) - 1)
    m = (y[j] < 4.0) & (y[j + 1] < 4.0) & ((y[j] > 0.02) | (y[j + 1] > 0.02))
    da = np.abs(a[j + 1] - a[j]); dy = np.abs(y[j + 1] - y[j])
    sl = np.degrees(np.arctan2(dy, np.maximum(da, 1e-9)))
    steps = int(np.sum(m & (da < 0.05) & (dy > 0.5)))
    # a vertical run: accumulate consecutive segments steeper than 80 deg
    run = best = 0.0
    for q in np.nonzero(m)[0]:
        run = run + dy[q] if sl[q] > 80 else 0.0; best = max(best, run)
    return {"front_slope_max_deg_below_4m": float(sl[m].max()) if m.any() else None, "vertical_steps": steps,
            "vertical_run_m": float(best)}


def trough(a, y, jtip, H):
    """lowest point of the row in front of the lip tip column range (the front sea), relative to still water."""
    j = np.arange(jtip, len(a))
    front = j[(a[j] > a[jtip:].min())]
    ymin = float(y[jtip:].min())
    return {"trough_depth_m": float(-min(ymin, 0.0)), "trough_depth_over_H": float(-min(ymin, 0.0) / H)}


def back_inflections(a, y, jtip):
    """back contour of a row (crest backwards, 0.1H..0.97H): curvature sign changes (|kappa| > 0.005/m) and the
    roughness std(d kappa) x 1e3 on a 0.05 m re-sampling (sigma 0.5 m). 参照モデルの背は 3~5 回・10~26。"""
    jt = int(np.argmax(y[:jtip])); Hr = y[jt]
    m = (y[:jt + 1] > 0.1 * Hr) & (y[:jt + 1] < 0.97 * Hr)
    x, yy = a[:jt + 1][m], y[:jt + 1][m]
    if len(x) < 10:
        return None, None
    s = arclen(x, yy); ss = np.arange(0, s[-1], 0.05)
    xx = gaussian_filter1d(np.interp(ss, s, x), 10); y2 = gaussian_filter1d(np.interp(ss, s, yy), 10)
    dx, dy = np.gradient(xx), np.gradient(y2); ddx, ddy = np.gradient(dx), np.gradient(dy)
    kap = ((dx * ddy - dy * ddx) / np.maximum((dx * dx + dy * dy) ** 1.5, 1e-12))[20:-20]
    sg = np.sign(kap[np.abs(kap) > 0.005])
    return int(np.sum(sg[1:] != sg[:-1])), float(np.std(np.diff(kap)) * 1e3)


def grid_world(A, Y, c):
    X = RM.O[None, None, :] + A[..., None] * RM.T + Y[..., None] * UP + c[:, None, None] * RM.E
    nv, nu = A.shape; idx = np.arange(nv * nu).reshape(nv, nu)
    q = np.stack([idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]], -1).reshape(-1, 4)
    return X.reshape(-1, 3), np.r_[q[:, [0, 1, 2]], q[:, [0, 2, 3]]]


def seat_silhouette(X, tris, look_at, vfov=90, W=1440, H=1080):
    import cv2
    f = look_at - SEAT; f /= np.linalg.norm(f); r = np.cross(UP, f); r /= np.linalg.norm(r); u = np.cross(f, r)
    fp = (H / 2) / math.tan(math.radians(vfov / 2))
    P = X - SEAT; z = P @ f
    x = W / 2 + fp * (P @ r) / np.maximum(z, 1e-3); yv = H / 2 - fp * (P @ u) / np.maximum(z, 1e-3)
    ok = z > 0.2
    img = np.zeros((H * 2, W * 2), np.uint8)
    pts = np.round(np.stack([x, yv], -1) * 2 * 16).astype(np.int64)
    tv = ok[tris].all(1)
    tt = pts[tris[tv]]
    tt = tt[(np.abs(tt) < 2 ** 26).all((1, 2))].astype(np.int32)
    for tri in tt:
        cv2.fillConvexPoly(img, tri, 255, lineType=cv2.LINE_8, shift=4)
    m = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA) > 127
    cnts, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    def ang(p, q):
        v1 = np.array([p[0] - W / 2, p[1] - H / 2, fp]); v2 = np.array([q[0] - W / 2, q[1] - H / 2, fp])
        return math.degrees(math.acos(np.clip(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1)))
    onb = lambda s: s[0] <= 1 or s[1] <= 1 or s[0] >= W - 2 or s[1] >= H - 2
    longest = 0.0; corners = 0
    for cn in cnts:
        if len(cn) < 20:
            continue
        ap = cv2.approxPolyDP(cn, fp * math.radians(0.25), True)[:, 0, :].astype(float)
        for i in range(len(ap)):
            p, q, pr = ap[i], ap[(i + 1) % len(ap)], ap[i - 1]
            if onb(p) and onb(q):
                continue
            longest = max(longest, ang(p, q))
            d1, d2 = p - pr, q - p
            if not onb(p) and min(np.linalg.norm(d1), np.linalg.norm(d2)) > fp * math.radians(1.0):
                t = math.degrees(math.acos(np.clip(d1 @ d2 / np.linalg.norm(d1) / np.linalg.norm(d2), -1, 1)))
                corners += t > 60
    el = math.degrees(math.asin((look_at - SEAT)[1] / np.linalg.norm(look_at - SEAT)))
    return {"longest_straight_deg": float(longest), "corners_gt60": int(corners), "lip_tip_elevation_deg": float(el)}


# ------------------------------------------------------------------ the check
def check(rows_npz, gate=False, ref_cache=None, jtip=200):
    z = np.load(rows_npz); A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
    nv, nu = A.shape
    H = Y.max(1); main = int(np.argmin(np.abs(c))); H0 = float(H[main])
    R = {"input": rows_npz, "H0_main_m": H0, "checks": {}}
    C = R["checks"]
    def put(fid, name, value, must, target=None, ok_must=None, ok_target=None, note=""):
        C.setdefault(fid, []).append({"name": name, "value": value, "must": must, "target": target,
                                      "pass_must": ok_must, "pass_target": ok_target, "note": note})
    big = np.nonzero(H >= 0.5 * H0)[0]
    body = np.nonzero((H >= 0.75 * H0) & (c >= -5) & (c <= 4))[0]
    # ---- F02 top arc (every row with H >= 0.5 H0)
    cq = {int(r): corner_q17(A[r], Y[r], jtip) for r in big}
    th = {int(r): (RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}).get("theta_c_deg", np.nan) for r in big}
    zones = (("c -5~+3", [r for r in big if -5 <= c[r] <= 3]), ("奥 c > +3", [r for r in big if c[r] > 3]))
    for zn, rr in zones:
        if not rr:
            continue
        v = min(cq[r]["Rmin_m"] for r in rr); put("F02", "Rmin_m（%s の行の最小）" % zn, v, ">= 1.5", ">= 2.4（原画の弧の下限）", v >= 1.5, v >= 2.4, "Q17 の定義。K* 主断面 0.53")
        v = min(th[r] for r in rr); put("F02", "theta_c_deg（%s の最小）" % zn, v, ">= 110", ">= 115", v >= 110, v >= 115, "K* 主断面 101")
        v = min(cq[r]["chord2_deg"] for r in rr); put("F02", "chord_pm2m_deg（%s の最小）" % zn, v, ">= 125", ">= 130", v >= 125, v >= 130, "K* 主断面 111")
        v = max(cq[r]["fold_deg"] for r in rr); put("F02", "fold_deg（1 頂点の折れ、%s の最大）" % zn, v, "<= 13", "<= 11", v <= 13, v <= 11, "K* 主断面 31.7")
    shoulder = [r for r in big if c[r] < -5]
    if shoulder:
        v = min(cq[r]["Rmin_m"] for r in shoulder); put("F02", "Rmin_m（c < -5 の肩の行の最小）", v, ">= 1.0", ">= 2.4", v >= 1.0, v >= 2.4, "肩の背は原画の輪郭から 6~38 px")
        v = max(cq[r]["fold_deg"] for r in shoulder); put("F02", "fold_deg（c < -5 の肩の行の最大）", v, "<= 13", "<= 11", v <= 13, v <= 11)
    # ---- F03 back contour and shell (body rows)
    bs = {}
    for r in body:
        segs = RM.poly_to_segs(A[r], Y[r]); m = RM.section_metrics(segs, 0.0, H0, open_w=0.0)
        bs[int(r)] = dict(m, **RM.back_shape(segs, 0.0, m["H"], m["a_top"]))
    if bs:
        v = max(x["back_longest_straight_over_H"] for x in bs.values()); put("F03", "背の最長の直線 / H（向きの変化 < 6°）", v, "<= 0.35", "<= 0.25", v <= 0.35, v <= 0.25, "参照 0.18~0.35、K* 0.83")
        vs = [x["back_R_over_H"] for x in bs.values()]; put("F03", "背の円の当てはめ R / H（範囲）", [min(vs), max(vs)], "0.6~2.0", "0.8~1.5", min(vs) >= 0.6 and max(vs) <= 2.0, min(vs) >= 0.8 and max(vs) <= 1.5, "参照 0.7~1.4")
        sl = {}
        for r in body:
            a, y = A[r], Y[r]; jt = int(np.argmax(y[:jtip])); Hr = y[jt]
            ab = a[:jt + 1]; yb = gaussian_filter1d(y[:jt + 1], 1.0)
            g = np.degrees(np.arctan2(np.gradient(yb), np.gradient(ab)))
            for f in (0.9, 0.95):
                idx = np.nonzero((yb[:-1] - f * Hr) * (yb[1:] - f * Hr) <= 0)[0]
                sl.setdefault(f, []).append(float(g[idx[-1]]) if len(idx) else np.nan)
        v = float(np.nanmax(sl[0.9])); put("F03", "背の傾き 0.9H（度、最大）", v, "<= 50", "<= 40", v <= 50, v <= 40, "参照 30~44、K* 69~71")
        v = float(np.nanmax(sl[0.95])); put("F03", "背の傾き 0.95H（度、最大）", v, "<= 40", "<= 30", v <= 40, v <= 30, "参照 17~48、K* 65")
        vs = [x["shell_thick_normal_over_H"][1] for x in bs.values() if x.get("shell_thick_normal_over_H")]
        # 2026-09-29 R3（設計28修正01、進行役の決定 Q24 の記録）：殻の必須の上限を 0.34 → 0.42 H に緩めた。上の 0.34 は Q20 の評価基準を
        # 作った時の我々の暫定の数（参照の 0.23〜0.31 から置いた）で、利用者の決定ではない。R2 で、上から見たくびれを後ろから埋めると
        # （背の埋め back_fill）本体の行の殻が 0.37〜0.43 H になり、この必須とぶつかった。利用者の Q21 の要求（くびれ・中の膨らみがなく、
        # 満ちた量感）を優先し、殻の上限を 0.42 H にした。目標（0.22〜0.30）は変えない。緩める前の写しで R2 の表が変わらないことを
        # 確かめた（Unity/Build/Q20H/final/_work/R3/rubric_repro_R2.json）。
        put("F03", "殻の厚み（背の法線、中央値）/ H（範囲）", [min(vs), max(vs)], "0.20~0.42（2026-09-29 に 0.34 から緩めた）", "0.22~0.30", min(vs) >= 0.20 and max(vs) <= 0.42, min(vs) >= 0.22 and max(vs) <= 0.30, "参照 0.23~0.31、K* 0.37~0.39")
        inf = [back_inflections(A[r], Y[r], jtip) for r in body]
        v = max(i[0] for i in inf if i[0] is not None); put("F03", "背の S 字：曲率の符号の変わり目（数、最大）", v, "<= 1", "1（凹の足 -> 凸の上）", v <= 1, v == 1, "参照 3~5（彫りの波）、K* 1~3")
        v = max(i[1] for i in inf if i[1] is not None); put("F03", "背の曲率のざらつき std(dκ)×1e3（最大）", v, "<= 2.0", "<= 1.0", v <= 2.0, v <= 1.0, "参照 10~26 より滑らかに（意図した違い）、K* 0.5~0.8")
        vs = [x["wall_50_over_H"] for x in bs.values() if x.get("wall_50_over_H") is not None]
        # 2026-09-29 R3：壁 0.5H の必須の上限を 0.36 → 0.42 に緩めた（理由は上の殻と同じ。Q21 のくびれを埋めることを優先。目標 0.32 は変えない）。
        put("F03", "壁 0.5H（水平）/ H（最大）", max(vs), "<= 0.42（2026-09-29 に 0.36 から緩めた）", "<= 0.32", max(vs) <= 0.42, max(vs) <= 0.32, "参照 0.22~0.28、K* 0.28")
    # ---- F04 lateral thickness / volume / peak
    ipk = int(np.argmax(H)); put("F04", "最高点の c（m）", float(c[ipk]), "-1 ~ +3", None, -1 <= c[ipk] <= 3, None, "参照 c≈0、K* +5.5")
    v = float(H[ipk] / H0); put("F04", "最高点 / H0", v, "<= 1.045", None, v <= 1.045, None, "K1")
    wid = {}
    for f in (0.5, 0.75, 0.9):
        lo, hi = [], []
        for r in range(nv):
            if H[r] < f * H0:
                continue
            xs = RM.crossings(RM.poly_to_segs(A[r], Y[r]), f * H0)
            if len(xs) >= 2:
                lo.append(xs.min()); hi.append(xs.max())
        wid[f] = float(max(hi) - min(lo)) if lo else 0.0
    put("F04", "側面の影の幅 0.5H0（m、波峰に沿って見る）", wid[0.5], "<= 18.5", "<= 16.5", wid[0.5] <= 18.5, wid[0.5] <= 16.5, "参照 15.4、K* 29.4（Q16 K4）")
    put("F04", "側面の影の幅 0.9H0（m）", wid[0.9], "<= 9.5", "<= 8.0", wid[0.9] <= 9.5, wid[0.9] <= 8.0, "参照 7.3")
    ce = c[H >= 0.75 * H0]; v = float(ce.max() - ce.min()) if len(ce) else 0.0
    put("F04", "正面の影の幅 0.75H0 より上（m、c の長さ）", v, "<= 13", "<= 12", v <= 13, v <= 12, "参照 11.5~12.0（Q16 K5）")
    dc = np.gradient(c); vol = float(sum(section_area(A[r], Y[r]) * dc[r] for r in range(nv) if c[r] > 0))
    put("F04", "奥 c > 0 の水面より上の体積（m³）", vol, "<= 600", None, vol <= 600, None, "Q16 K6、K* 1,881")
    # ---- F05 far end: a curl, not a wall
    far = [r for r in big if c[r] > c[ipk]]
    ov = []; tipa = []
    for r in big:
        m = RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
        ov.append(m.get("overhang_over_H", 0.0) or 0.0); tipa.append(m.get("a_tip", np.nan))
    ov = np.array(ov); tipa = np.array(tipa)
    v = float(ov.min()); put("F05", "唇（巻き）の張り出し / H（H >= 0.5H0 の全行の最小）", v, ">= 0.15（唇のない壁 0）", ">= 0.30", v >= 0.15, v >= 0.30, "K* 奥の行 0")
    jump = float(np.nanmax(np.abs(np.diff(tipa)))) if len(tipa) > 1 else 0.0
    put("F05", "唇先の線の隣の行との差（m、最大）", jump, "<= 0.5", "<= 0.3", jump <= 0.5, jump <= 0.3, "K* は奥の c +3.2~+4.7 の 5 行で合計約 10 m 跳ぶ")
    ls = max(longest_straight(A[r], Y[r], 0.1 * H[r], 0.95 * H[r]) / H[r] for r in big)
    put("F05", "どの行の断面にも長い直線がない（最長 / H(c)）", float(ls), "<= 0.35", "<= 0.25", ls <= 0.35, ls <= 0.25, "平らな切り口・板の背を捕まえる")
    if far:
        w = []
        for r in far:
            if c[r] < c[ipk] + 4:
                continue
            xs = RM.crossings(RM.poly_to_segs(A[r], Y[r]), 0.5 * H[r])
            if len(xs) >= 2:
                w.append(float(xs[1] - xs[0]))
        v = max(w) if w else 0.0
        put("F05", "奥の端（最高点 + 4 m より奥）の 0.5H(c) の固まりの幅（m、最大）", v, "<= 3.0", "<= 2.0", v <= 3.0, v <= 2.0, "薄い巻きで終わる")
    # ---- F06 lip & hook (rows c -10..+4, H >= 0.75 H0)
    lipr = [r for r in big if -10 <= c[r] <= 3 and H[r] >= 0.75 * H0]
    l075, l2, curl = [], [], []
    for r in lipr:
        m = RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0) or {}
        if m.get("lip_thick_0p75_m") is not None: l075.append(m["lip_thick_0p75_m"])
        if m.get("lip_thick_2m_m") is not None: l2.append(m["lip_thick_2m_m"])
        a, y = A[r], Y[r]; jt = int(np.argmax(y[:jtip])); jc = min(jtip + 115, len(a) - 1)   # crest -> lip -> underside -> root (j_corner ~ 314)
        sa = arclen(a[jt:jc + 1], y[jt:jc + 1]); sq = np.arange(0, sa[-1], 0.05)
        pa = gaussian_filter1d(np.interp(sq, sa, a[jt:jc + 1]), 4); py_ = gaussian_filter1d(np.interp(sq, sa, y[jt:jc + 1]), 4)
        hd = np.degrees(np.unwrap(np.arctan2(np.gradient(py_), np.gradient(pa))))
        curl.append(float(hd[0] - hd.min()))
    if l075:
        v = max(l075); put("F06", "唇の厚み 先から 0.75 m（m、最大）", v, "<= 0.8", "<= 0.5", v <= 0.8, v <= 0.5, "参照 0.30~0.39、K* 1.2~1.5。原画の関門が優先")
    if l2:
        v = max(l2); put("F06", "唇の厚み 先から 2 m（m、最大）", v, "<= 1.6", "<= 1.0", v <= 1.6, v <= 1.0, "参照 0.40~0.53、K* 1.9~4.7")
    if curl:
        v = min(curl); put("F06", "唇の巻き：頂から唇の付け根まで面の向きが回る角（度、最小）", v, ">= 170", ">= 190", v >= 170, v >= 190, "鉤＝唇先で下へ、下面で後ろ・上へ戻る。K* 主断面 約 150、肩 約 185")
    # ---- F07 tube (rows c -6..+3, H >= 0.75 H0)
    tr = [r for r in big if -6 <= c[r] <= 3 and H[r] >= 0.75 * H0]
    tb = []
    for r in tr:
        segs = RM.poly_to_segs(A[r], Y[r]); m = RM.section_metrics(segs, 0.0, H0, open_w=0.0) or {}
        if "inner_wall_a_at_0p3H" in m and "a_tip" in m:
            tb.append(dict(m, **RM.tube_shape2(segs, 0.0, m["H"], m["inner_wall_a_at_0p3H"], m["a_tip"], m["y_tip"])))
    if tb:
        v = max(x["tube_fit_rms_over_R"] for x in tb); put("F07", "管の丸さ：円からのずれ rms/R（最大）", v, "<= 0.18", "<= 0.12", v <= 0.18, v <= 0.12, "参照 0.05~0.12、K* 0.25")
        v = max(x["tube_wall_turn_max_deg_per_m"] for x in tb); put("F07", "管の壁の曲がり（度/m、最大）＝角がない", v, "<= 50", "<= 35", v <= 50, v <= 35, "K* 80（下面と内壁の角・台座）")
        vs = [x["tube_R_over_H"] for x in tb]; put("F07", "管の円の半径 / H（範囲）", [min(vs), max(vs)], "0.38~0.52", "0.42~0.48", min(vs) >= 0.38 and max(vs) <= 0.52, min(vs) >= 0.42 and max(vs) <= 0.48, "参照 0.42~0.46")
        vs = [x["overhang_over_H"] for x in tb if x.get("overhang_over_H") is not None]; put("F07", "張り出し（内壁 0.3H → 唇先）/ H（最小）", min(vs), ">= 0.38", ">= 0.42", min(vs) >= 0.38, min(vs) >= 0.42, "参照 0.40~0.58、原画の視点 0.39")
    # ---- F08 foot & trough (rows with H >= 0.5 H0)
    fp = [foot_plinth(A[r], Y[r], jtip) for r in big]
    v = max(x["vertical_run_m"] for x in fp); put("F08", "前の足の鉛直の段（80° より急が続く高さ、m、最大）", v, "<= 0.5", "0", v <= 0.5, v <= 0.05, "K* 約 3 m（TR1）")
    v = sum(x["vertical_steps"] for x in fp); put("F08", "Δa < 0.05 m で Δy > 0.5 m の列の組（数）", v, "0", "0", v == 0, v == 0, "TR1")
    tdep = [trough(A[r], Y[r], jtip, H[r])["trough_depth_over_H"] for r in big]
    v = float(np.median(tdep)); put("F08", "前の谷の深さ D/H（本体の行の中央値、船の所を除く前提）", v, ">= 0.15", "0.20~0.30（<= 0.35）", v >= 0.15, 0.20 <= v <= 0.30, "K* 0（TR2）。船の所は船首の水線 -1.37 ± 0.3 m")
    # ---- F10 crest line
    at = np.array([RM.section_metrics(RM.poly_to_segs(A[r], Y[r]), 0.0, H0, open_w=0.0)["a_top"] for r in big]); cb = c[big]
    hd = np.degrees(np.arctan2(np.diff(at), np.diff(cb)))
    win = []
    for i in range(len(cb)):
        j = np.nonzero((cb > cb[i]) & (cb <= cb[i] + 2.0))[0]
        if len(j) and j.max() < len(hd) + 1 and i < len(hd):
            win.append(float(np.ptp(hd[i:j.max()])) if j.max() > i else 0.0)
    v = max(win) if win else 0.0; put("F10", "平面の頂の線：波峰 2 m あたりの向きの変化（度、最大）", v, "<= 10", "<= 6", v <= 10, v <= 6)
    farc = cb > 0
    sweep = float(np.max(np.abs(at[farc] - at[np.argmin(np.abs(cb))]) / np.maximum(cb[farc], 1.0))) if farc.any() else 0.0
    v = math.degrees(math.atan(sweep)); put("F10", "奥で頂の線が後ろへ流れる角（度）", v, "<= 20", "<= 12", v <= 20, v <= 12, "K* 約 63°")
    Hs = gaussian_filter1d(H, 1.0 / max(np.median(np.diff(c)), 1e-3))
    pk = []
    for i in range(1, nv - 1):
        if Hs[i] >= Hs[i - 1] and Hs[i] > Hs[i + 1] and Hs[i] > 0.5 * H0:
            left = Hs[:i]; right = Hs[i + 1:]
            lh = left[left > Hs[i]]; rh = right[right > Hs[i]]
            li = np.nonzero(left > Hs[i])[0]; ri = np.nonzero(right > Hs[i])[0]
            lmin = Hs[li.max() + 1:i].min() if len(li) else Hs[:i].min()
            rmin = Hs[i + 1:i + 1 + ri.min()].min() if len(ri) else Hs[i + 1:].min()
            if Hs[i] - max(lmin, rmin) >= 0.5:
                pk.append(float(c[i]))
    put("F10", "立面 H(c) の山（0.5H0 より上、際立ち 0.5 m 以上）の数", len(pk), "1", "1", len(pk) == 1, len(pk) == 1, "山の c：%s" % ",".join("%.1f" % x for x in pk))
    sl = np.abs(np.gradient(H, c)); farm = (c > c[ipk]) & (H > 0.05 * H0)
    v = float(sl[farm].max()) if farm.any() else 0.0
    put("F10", "奥の端の高さの落ち |dH/dc|（最大）", v, "<= 3.5", "<= 2.0", v <= 3.5, v <= 2.0, "Q16 K3（崖にしない）")
    d2 = np.abs(np.diff(H, 2)); v = float(d2[(H[1:-1] > 0.25 * H0)].max())
    put("F10", "高さの段（2 階差、m、最大）", v, "<= 0.10", "<= 0.05", v <= 0.10, v <= 0.05, "行ごとの段・筋")
    # ---- F11 creases
    Xg = np.stack([A, Y, np.broadcast_to(c[:, None], A.shape)], -1)
    du = Xg[:, 1:] - Xg[:, :-1]; dv = Xg[1:] - Xg[:-1]
    n = np.cross(du[:-1], dv[:, :-1]); n /= np.linalg.norm(n, axis=-1, keepdims=True) + 1e-12
    ang_r = np.degrees(np.arccos(np.clip((n[1:] * n[:-1]).sum(-1), -1, 1)))
    ang_c = np.degrees(np.arccos(np.clip((n[:, 1:] * n[:, :-1]).sum(-1), -1, 1)))
    cols = np.arange(nu - 1)[None, :]
    mr = (Y[1:-1, :-1] > 0.3) & ~((cols >= jtip - 10) & (cols <= jtip + 12)) & (np.abs(c[1:-1, None]) <= 16)
    mc = (Y[:-1, 1:-1] > 0.3) & ~((cols[:, :-1] >= jtip - 10) & (cols[:, :-1] <= jtip + 12)) & (np.abs(c[:-1, None]) <= 16)
    vr, vc = ang_r[mr], ang_c[mc]
    put("F11", "行をまたぐ面の折れ p99（度）", float(np.percentile(vr, 99)), "<= 25", "<= 15", np.percentile(vr, 99) <= 25, np.percentile(vr, 99) <= 15, "K* 58.8")
    put("F11", "行をまたぐ面の折れ > 30° の数", int((vr > 30).sum()), "<= 50", "0", (vr > 30).sum() <= 50, (vr > 30).sum() == 0, "K* 1,114（唇の上面・下面、肩）")
    put("F11", "断面に沿う面の折れ p99（度）", float(np.percentile(vc, 99)), "<= 25", "<= 15", np.percentile(vc, 99) <= 25, np.percentile(vc, 99) <= 15)
    put("F11", "行をまたぐ面の折れ p95（度）", float(np.percentile(vr, 95)), "<= 13.5", "<= 10", np.percentile(vr, 95) <= 13.5, np.percentile(vr, 95) <= 10, "Q16 J3 と同じ上限")
    # ---- F12 seat
    X, tris = grid_world(A, Y, c)
    lip = RM.O + A[main, jtip] * RM.T + Y[main, jtip] * UP + c[main] * RM.E
    ss = seat_silhouette(X, tris, lip)
    put("F12", "座席から見た影の最長の直線（視角 度）", ss["longest_straight_deg"], "<= 5", "<= 3", ss["longest_straight_deg"] <= 5, ss["longest_straight_deg"] <= 3, "K* 14.5（奥の切り口）")
    put("F12", "座席から見た影の 60° を超える角（数）", ss["corners_gt60"], "0", "0", ss["corners_gt60"] == 0, ss["corners_gt60"] == 0, "K* 3")
    put("F12", "唇先（主断面）の仰角（度）", ss["lip_tip_elevation_deg"], "45~70", "50~65", 45 <= ss["lip_tip_elevation_deg"] <= 70, 50 <= ss["lip_tip_elevation_deg"] <= 65)
    # ---- F01 painting gate
    if gate:
        sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth")); sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen"))
        import truthlib as TL
        import gw_wavegen_v1 as V1
        params = TL.load_json(os.path.join(REPO, "Tools", "GWWaveGen", "params_v2_af26r01.json"))
        tgt = V1.Target(); fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
        Xw = fr.world(c, A, Y); tr_ = V1.triangles(nu, nv)
        outp = os.path.splitext(R["input"])[0] + "_gate_overlay.png"
        if not os.access(os.path.dirname(outp) or ".", os.W_OK) or "Build\\ArtFirst" in outp or "Build/ArtFirst" in outp:
            outp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_tmp", "gate_overlay.png")
        g = V1.preview_metrics(fr, tgt, Xw, tr_, outp, "Q20 rubric F01")
        base = {"78": 1.37, "130": 1.80, "131": 1.47, "132": 1.40}
        for kk in ("78", "130", "131", "132"):
            v = g[kk]["max_px"]; put("F01", "輪郭 %s 最大（px）" % kk, v, "<= 4 かつ K* + 0.5（<= %.2f）" % (base[kk] + 0.5), None, v <= 4 and v <= base[kk] + 0.5, None)
        v = g["72"]["p95_px"]; put("F01", "輪郭 72 p95（px）", v, "<= 4", None, v <= 4, None, "最大は記録")
        R["gate_raw"] = g
    # ---- F13 proximity to the reference model (align B)
    if ref_cache:
        from scipy.spatial import cKDTree
        V = np.load(ref_cache)["V"].astype(float)
        msk = (Y.reshape(-1) > 1.0) & (np.abs(np.repeat(c, nu)) <= 16)
        dd, _ = cKDTree(V[::2]).query(X[msk], k=1)
        v = float((dd < 0.3).mean()); put("F13", "参照モデルの面から 0.3 m 以内の頂点の割合（解B）", v, "<= 0.25", "<= 0.15", v <= 0.25, v <= 0.15, "K* 0.057")
    # summary
    nm = sum(1 for L in C.values() for x in L if x["pass_must"] is False)
    nt = sum(1 for L in C.values() for x in L if x["pass_target"] is False)
    R["summary"] = {"must_fail": nm, "target_miss": nt, "n_checks": sum(len(L) for L in C.values())}
    return R


def to_table(R):
    lines = ["| 基準 | 測るもの | 値 | 必須 | 目標 | 必須 | 目標 | 注 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for fid in sorted(R["checks"]):
        for x in R["checks"][fid]:
            v = x["value"]
            vs = ("[%.2f, %.2f]" % tuple(v)) if isinstance(v, list) else (("%.2f" % v) if isinstance(v, float) else str(v))
            pm = {True: "合", False: "**否**", None: "—"}[x["pass_must"] if x["pass_must"] is None else bool(x["pass_must"])]
            pt = {True: "合", False: "否", None: "—"}[x["pass_target"] if x["pass_target"] is None else bool(x["pass_target"])]
            lines.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (fid, x["name"], vs, x["must"], x["target"] or "—", pm, pt, x["note"]))
    return "\n".join(lines)


if __name__ == "__main__":
    args = sys.argv[1:]
    rows_npz, outp = args[0], args[1]
    gate = "--gate" in args
    ref = args[args.index("--ref") + 1] if "--ref" in args else None
    jtip = int(args[args.index("--jtip") + 1]) if "--jtip" in args else 200
    R = check(rows_npz, gate, ref, jtip)
    json.dump(R, open(outp, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    open(os.path.splitext(outp)[0] + "_table.md", "w", encoding="utf-8").write(to_table(R) + "\n")
    sys.stdout.reconfigure(encoding='utf-8'); print(to_table(R)); print(R["summary"])
