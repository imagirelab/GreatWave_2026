# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES：② b区域・③ 最左側の小区域を、陰関数の丸い塊（lobe）として主役波の左の体へ大きな丸みでつなぎ、
行の格子（240 × 400）へ戻す。説明は lobes_common.py の頭。

py -3.10 -B Tools/GWWaveGen/as06/lobes_build.py <out_prefix> <design.json>
出力：<out_prefix>_rows.npz（c・A・Y）、_labels.npy（層の印 0/1/2/3、行の格子）、_fields.npz（頂点での塊・体の距離）、_build_log.json。
design の write_candidate が真なら、K* の書き出し（.gwb・.obj・_meta.json）も作る（材質の属性の段へ渡す）。

行 c ≥ −8 m（いちばん高い峰、K-top）は見本04（= 見本05 B10）のまま。作り直すのは塊の重み > 0 の行だけ。
土台の行は見本04 AS04F（見本05 B10 の c ≥ −8 と同じ。c < −8 は B10 の狭い段を作る前の形）：B10 の狭い段の唇は塊の和で残ると板・つららになるので使わない。
"""
import json
import os
import sys
import time

import numpy as np
import cv2
from scipy.interpolate import CubicSpline
from scipy.ndimage import gaussian_filter1d, map_coordinates
from scipy.spatial import cKDTree
from skimage import measure

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lobes_common as L  # noqa: E402

B = L.B
# 陰関数の格子（断面の a, y）
FA0, FA1, FY0, FY1, FRES = -16.0, 30.0, -6.0, 22.0, 0.08
NA = int(round((FA1 - FA0) / FRES)) + 1
NY = int(round((FY1 - FY0) / FRES)) + 1
GA = FA0 + np.arange(NA) * FRES
GY = FY0 + np.arange(NY) * FRES
PIX = np.stack(np.meshgrid(GA, GY), -1).reshape(-1, 2)        # (NY*NA, 2) の (a, y)


def resample_poly(P, step=0.03, closed=False):
    P = np.asarray(P, float)
    if closed:
        P = np.r_[P, P[:1]]
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    n = max(int(d[-1] / step), 2)
    t = np.linspace(0, d[-1], n)
    return np.c_[np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])]


def sdf_poly(curve, fill_poly, closed=False):
    """curve（距離を測る折れ線）までの距離に、fill_poly（閉じた多角形）の内を − の符号を付けた場。
    面の近く（0.4 m 以内）の符号は、いちばん近い点の法線の向きで決める（格子の塗りの段々で 0 の線が行ごとに揺れ、縞になるのを防ぐ）。"""
    C = resample_poly(curve, 0.025, closed=closed)
    tree = cKDTree(C)
    dist, k = tree.query(PIX, k=1)
    inside = fill_mask(fill_poly).reshape(-1)
    # 法線：曲線の向きと、塗りの内の側から決める
    T = np.gradient(C, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    Nn = np.c_[-T[:, 1], T[:, 0]]
    # 向きの確かめ：法線の側の少し先の点が塗りの外なら外向き
    probe = C + 0.3 * Nn
    ia = np.clip(np.round((probe[:, 0] - FA0) / FRES).astype(int), 0, NA - 1)
    iy = np.clip(np.round((probe[:, 1] - FY0) / FRES).astype(int), 0, NY - 1)
    out_frac = 1.0 - inside.reshape(NY, NA)[iy, ia].mean()
    if out_frac < 0.5:
        Nn = -Nn
    v = PIX - C[k]
    sgn_n = np.sign((v * Nn[k]).sum(1))
    sgn = np.where(inside, -1.0, 1.0)
    near = dist < 0.4
    sgn = np.where(near & (sgn_n != 0), sgn_n, sgn)
    return (sgn * dist).reshape(NY, NA)


def fill_mask(poly):
    """閉じた多角形（a, y）の内の格子点（NY×NA の bool）。cv2 の塗り（1/16 画素の精度）。"""
    xs = (np.asarray(poly)[:, 0] - FA0) / FRES
    ys = (np.asarray(poly)[:, 1] - FY0) / FRES
    pts = np.round(np.c_[xs, ys] * 16).astype(np.int32)
    g = np.zeros((NY, NA), np.uint8)
    cv2.fillPoly(g, [pts], 1, lineType=cv2.LINE_8, shift=4)
    return g.astype(bool)


def base_sdf(a, y):
    """主役波の 1 行の断面（列 0..399）の距離。内（水）が −。海の下 −7.9 m で閉じる。"""
    poly = np.r_[np.c_[a, y], [[a[-1], -7.9], [a[0], -7.9]]]
    return sdf_poly(np.c_[a, y], poly)


def spline_closed(P, n=600):
    P = np.asarray(P, float)
    Q = np.r_[P, P[:1]]
    d = np.r_[0, np.cumsum(np.sqrt(np.hypot(*np.diff(Q, axis=0).T)))]   # 求心
    cs = CubicSpline(d, Q, bc_type="periodic", axis=0)
    t = np.linspace(0, d[-1], n, endpoint=False)
    return cs(t)


def rim_line(key, st):
    """rim_pts（[c, a, y] の並び、断面の座標で進行役が置く縁の頂の点）があれば、それを c の細かい並びへ PCHIP で延ばして返す。
    無ければ下の射線の作り方。"""
    if st.get("rim_pts"):
        from scipy.interpolate import PchipInterpolator
        rp = np.array(st["rim_pts"], float)
        rp = rp[np.argsort(rp[:, 0])]
        cc = np.linspace(rp[0, 0], rp[-1, 0], 200)
        return np.c_[PchipInterpolator(rp[:, 0], rp[:, 1])(cc), PchipInterpolator(rp[:, 0], rp[:, 2])(cc), cc]
    return rim_line_rays(key, st)


def rim_line_rays(key, st):
    """塊の縁の頂の線（a, y, c）を c の昇順で。原画の層の頂の線 READ_CREST の射線の上、原画のカメラから dist m（x で線形に変える）。
    c_min・c_max の外の射線の点は捨て、extra（[a, y, c] の並び、進行役が置く点）を足す。"""
    pts = np.array(B.READ_CREST[key], float)
    x0, x1 = pts[:, 0].min(), pts[:, 0].max()
    d0, d1 = st["dist_m"]
    dist = lambda x: d0 + (d1 - d0) * (x - x0) / max(x1 - x0, 1e-6)
    q, xs, ys = B.crest_curve(key, dist, n=160, dy_px=st.get("dy_px", 0.0))
    q[:, 1] += st.get("dy_m", 0.0)
    if st.get("c_max") is not None:
        q = q[q[:, 2] <= st["c_max"]]
    if st.get("c_min") is not None:
        q = q[q[:, 2] >= st["c_min"]]
    if st.get("extra"):
        ex = np.array(st["extra"], float)
        q = np.r_[q, ex]
    q = q[np.argsort(q[:, 2])]
    return q


def lobe_at(c, q, st):
    """行 c での縁の頂 R = (a, y)（縁の線を c で補間、外は端の値）と、塊の重み f（taper_c = [t0, t1, t2, t3] の滑らかな台形）。"""
    t0, t1, t2, t3 = st["taper_c"]
    f = float(L.ss((c - t0) / max(t1 - t0, 1e-6)) * L.ss((t3 - c) / max(t3 - t2, 1e-6)))
    if f <= 0:
        return None, 0.0
    # 縁の線は c について滑らかに（区分線形の折れを消す）
    cs = q[:, 2]
    w = np.exp(-0.5 * ((cs - c) / st.get("rim_sigma_c", 0.6)) ** 2)
    if c < cs[0] or c > cs[-1]:
        R = q[0] if c < cs[0] else q[-1]
        Rs = np.array([R[0], R[1]])
    else:
        Rs = np.array([np.interp(c, cs, q[:, 0]), np.interp(c, cs, q[:, 1])])
        if w.sum() > 1e-6:
            Rs = 0.5 * Rs + 0.5 * np.array([(w * q[:, 0]).sum() / w.sum(), (w * q[:, 1]).sum() / w.sum()])
    return Rs, f


BLOB = {"groove": [-2.4, -0.25], "nose": [1.0, -1.0], "utip": [1.0, -2.0], "rback": [0.9, -3.2], "rbot": [0.8, -5.0]}


def profile_points(R, f, Qroot, crest, p, g=1.0):
    """塊の断面の制御点（閉じた曲線）。R = 縁の頂、f = 重み、Qroot = 縮める先（体の中）、crest = 体の背の頂 (a, y)。
    p の点は縁の頂からのずれ (da, dy)（m）。back_top・bottom_back の a は体の頂からのずれ。shin・foot・bottom_back の y は絶対の高さ。"""
    ar, yr = R
    def rel(k):
        o = np.array(p[k], float)
        if k in BLOB and g < 1.0:
            o = np.array(p.get("blob", {}).get(k, BLOB[k]), float) + g * (o - np.array(p.get("blob", {}).get(k, BLOB[k]), float))
        return np.array([ar + o[0], yr + o[1]])
    P = [np.array([crest[0] + p["back_top"][0], yr + p["back_top"][1]]),     # 体の中（踏み面の奥）
         rel("tread"), rel("groove"), np.array([ar, yr]), rel("nose"), rel("utip"), rel("rback"), rel("rbot"), rel("bulge"),
         np.array([ar + p["shin"][0], p["shin"][1]]),
         np.array([ar + p["foot"][0], p["foot"][1]]),
         np.array([crest[0] + p["bottom_back"][0], p["bottom_back"][1]])]
    P = np.array(P)
    return Qroot[None, :] + f * (P - Qroot[None, :])


def inside_point(a, y, cand):
    """候補の点のうち、断面の塗りの内にある最初の点。"""
    poly = np.r_[np.c_[a, y], [[a[-1], -7.9], [a[0], -7.9]]].astype(np.float32).reshape(-1, 1, 2)
    for q in cand:
        if cv2.pointPolygonTest(poly, (float(q[0]), float(q[1])), False) > 0:
            return np.array(q, float)
    return np.array(cand[-1], float)


def fill_mask_row(a, y, yq, near=None):
    """断面の塗りの、高さ yq の水平線の上の内の区間のうち、背の頂の列の a に近い区間の中ほどの a。無ければ None。"""
    j = np.arange(len(a) - 1)
    y0, y1 = y[:-1], y[1:]
    m = ((y0 - yq) * (y1 - yq) < 0)
    xs = a[:-1][m] + (yq - y0[m]) / (y1[m] - y0[m]) * (a[1:][m] - a[:-1][m])
    xs = np.sort(xs)
    if len(xs) < 2:
        return None
    jc = 18 + int(np.argmax(y[18:106]))
    ac = a[jc] if near is None else near
    best = None
    for k in range(0, len(xs) - 1, 2):
        lo, hi = xs[k], xs[k + 1]
        d = 0.0 if lo <= ac <= hi else min(abs(ac - lo), abs(ac - hi))
        if best is None or d < best[0]:
            best = (d, 0.5 * (lo + hi))
    return best[1]


def field_sample(F, P):
    """場 F（NY×NA）を点 P（n×2 の a, y）で双一次に読む。格子の外は +9。"""
    ia = (P[:, 0] - FA0) / FRES
    iy = (P[:, 1] - FY0) / FRES
    v = map_coordinates(F, [iy, ia], order=1, mode="constant", cval=9.0)
    out = (ia < 0) | (ia > NA - 1) | (iy < 0) | (iy > NY - 1)
    v[out] = 9.0
    return v


def arclen(P):
    return np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]


def extract_path(D, PA, PB):
    """場 D の 0 の等値線のうち、PA から PB への上（前）側の道（a, y の並び）。"""
    Dp = np.pad(D, 2, constant_values=9.0)
    cs = measure.find_contours(Dp, 0.0)
    best = None
    for C in cs:
        Pc = np.c_[FA0 + (C[:, 1] - 2) * FRES, FY0 + (C[:, 0] - 2) * FRES]
        dA = np.hypot(Pc[:, 0] - PA[0], Pc[:, 1] - PA[1])
        if best is None or dA.min() < best[0]:
            best = (dA.min(), Pc)
    Pc = best[1]
    if np.hypot(*(Pc[0] - Pc[-1])) < 1e-6:
        Pc = Pc[:-1]
    iA = int(np.argmin(np.hypot(Pc[:, 0] - PA[0], Pc[:, 1] - PA[1])))
    iB = int(np.argmin(np.hypot(Pc[:, 0] - PB[0], Pc[:, 1] - PB[1])))
    n = len(Pc)
    fw = Pc[np.r_[iA:iA + ((iB - iA) % n) + 1] % n]
    bw = Pc[np.r_[iA:iA - ((iA - iB) % n) - 1:-1] % n]
    arc = fw if fw[:, 1].mean() > bw[:, 1].mean() else bw
    return arc, float(best[0])


def redistribute(a, y, D, jA, jB, eps=0.02, min_run=5, inner_anchors=False, w_uniform=0.0, feats=None):
    """列 jA..jB を新しい 0 の等値線の上へ並べ直す。新しい面の上にある元の点（|D| < eps が min_run 列以上続く所）は動かさず、
    その間の列は、元の行の弧長の割合のまま、新しい道の弧長へ写す。"""
    P = np.c_[a, y]
    arc, d0 = extract_path(D, P[jA], P[jB])
    s_arc = arclen(arc)
    tree = cKDTree(arc)
    dv = np.abs(field_sample(D, P[jA:jB + 1]))
    on = dv < eps
    # 短い連なりは外す
    keep = np.zeros_like(on)
    i = 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            if j - i >= min_run or i == 0 or j == len(on):
                keep[i:j] = True
            i = j
        else:
            i += 1
    keep[0] = keep[-1] = True
    if not inner_anchors:
        keep[1:-1] = False
    idx = np.nonzero(keep)[0]
    _, k_ = tree.query(P[jA + idx])
    s_anchor = s_arc[k_]
    # 弧長が単調でない錨は外す
    good = [0]
    for t in range(1, len(idx)):
        if s_anchor[t] > s_anchor[good[-1]] + 1e-4:
            good.append(t)
    idx = idx[good]; s_anchor = s_anchor[good]
    if idx[-1] != len(on) - 1:
        idx = np.r_[idx, len(on) - 1]; s_anchor = np.r_[s_anchor, s_arc[-1]]
    So = arclen(P[jA:jB + 1])
    na_, ny_ = a.copy(), y.copy()
    if feats and not inner_anchors:
        # 形の目印（塊の縁の頂・唇の下の先・凹みの底）を決まった列へ留める（重み w で、端では元の並びへ戻す）。
        # 行ごとに道の長さが変わっても、目印の所の列が面の上を滑らない（平らな陰影の縞を防ぐ）
        n = jB - jA
        cols = np.arange(n + 1)
        base_t = (1.0 - w_uniform) * So / max(So[-1], 1e-9) + w_uniform * np.linspace(0.0, 1.0, n + 1)
        S = s_arc[-1]
        ctrl = [(0.0, 0.0), (float(n), 1.0)]
        used = []
        # 優先の順（縁の頂 → 唇の下の先 → 凹みの底 → 脛）に入れ、先に入れた目印と順が食い違う目印は捨てる
        for (pt, jt, w, pr) in sorted(feats, key=lambda q: q[3]):
            dd, kk = tree.query(np.asarray(pt, float))
            if dd > 0.2 or w <= 1e-3:
                continue
            t_f = s_arc[kk] / S
            j_nat = float(np.interp(t_f, base_t, cols))
            j_t = j_nat + w * ((jt - jA) - j_nat)
            if all((j_t - q[0]) * (t_f - q[1]) > 0 and abs(j_t - q[0]) >= 3 for q in ctrl):
                ctrl.append((j_t, t_f)); used.append([int(jt), round(float(t_f), 4), round(float(dd), 3), round(float(w), 3)])
        ctrl.sort()
        cj = np.array(ctrl)
        bt_c = np.interp(cj[:, 0], cols, base_t)
        t = np.empty(n + 1)
        for q in range(len(cj) - 1):
            j0, j1 = int(round(cj[q, 0])), int(round(cj[q + 1, 0]))
            seg = np.arange(j0, j1 + 1)
            fr = (base_t[seg] - bt_c[q]) / max(bt_c[q + 1] - bt_c[q], 1e-9)
            t[seg] = cj[q, 1] + fr * (cj[q + 1, 1] - cj[q, 1])
        t = np.maximum.accumulate(t)
        js = np.arange(jA + 1, jB)
        na_[js] = np.interp(t[1:-1] * S, s_arc, arc[:, 0]); ny_[js] = np.interp(t[1:-1] * S, s_arc, arc[:, 1])
        return na_, ny_, {"moved_cols": int(len(js)), "anchors": used, "path_start_err_m": round(d0, 3)}
    moved = 0
    for t in range(len(idx) - 1):
        u0, u1 = idx[t], idx[t + 1]
        if u1 - u0 <= 1:
            continue
        fr = (So[u0:u1 + 1] - So[u0]) / max(So[u1] - So[u0], 1e-9)
        # 塊のある行では、元の行の弧長の割合（元の唇の作りに引きずられる）を、等間隔へ寄せる（行の間で列が面の上を滑らないように）
        fr = (1.0 - w_uniform) * fr + w_uniform * np.linspace(0.0, 1.0, u1 - u0 + 1)
        s = s_anchor[t] + fr * (s_anchor[t + 1] - s_anchor[t])
        js = np.arange(jA + u0 + 1, jA + u1)
        na_[js] = np.interp(s[1:-1], s_arc, arc[:, 0]); ny_[js] = np.interp(s[1:-1], s_arc, arc[:, 1])
        moved += len(js)
    return na_, ny_, {"moved_cols": int(moved), "anchors": int(len(idx)), "path_start_err_m": round(d0, 3)}


def build(design):
    c, A0, Y0 = B.load_rows(L.ROWS04F)
    A, Y = A0.copy(), Y0.copy()
    lobes = {}
    for key in ("r2", "r3"):
        st = design["lobes"][key]
        lobes[key] = {"st": st, "q": rim_line(key, st)}
    jA, jB = design.get("jA", 60), design.get("jB", 390)
    cut = design.get("cut", {})
    nr, nc = A.shape
    labels = np.zeros((nr, nc), np.int16)
    fields = {k: np.full((nr, nc), np.nan, np.float32) for k in ("base", "r2", "r3")}
    info = []
    ycut = np.full((nr, 2), 0.5)
    ytop3 = np.full(nr, 1e9)
    rows = [i for i in range(nr) if c[i] < L.C_KTOP - design.get("ktop_margin_m", 0.1)]
    for i in rows:
        a, y = A0[i].copy(), Y0[i].copy()
        jc = B.J_B + int(np.argmax(y[B.J_B:106]))
        crest = np.array([a[jc], y[jc]])
        rec = {"row": i, "c": round(float(c[i]), 3)}
        parts = {}
        for key, lb in lobes.items():
            R, f = lobe_at(c[i], lb["q"], lb["st"])
            if R is None or f <= 1e-3:
                continue
            p = lb["st"]["profile"]
            Qr = inside_point(a, y, [(crest[0] - 2.0, min(R[1], crest[1]) - 3.0), (crest[0] - 3.0, crest[1] - 3.5), (crest[0] - 2.5, 1.0)])
            # 端の縮める先：q_left・q_right（断面の座標の点）を与えた端では、その点へ縮める（次の段・① の体へ上る／下りる蹴込みにする）
            tc = lb["st"]["taper_c"]
            side = "q_left" if c[i] < 0.5 * (tc[1] + tc[2]) else "q_right"
            if lb["st"].get(side):
                Qr = np.array(lb["st"][side], float)
            gd = float(L.ss((f - lb["st"].get("detail_f", [0.35, 0.85])[0]) / (lb["st"].get("detail_f", [0.35, 0.85])[1] - lb["st"].get("detail_f", [0.35, 0.85])[0])))
            pp = dict(p)
            # 塊の後ろの縁（back_top）は、その高さの体の塗りの中ほど（背の面と前・内の面の間）へ置く（体と塊の間に裂け目を残さない・背へ出さない）
            ybt = R[1] + p["back_top"][1]
            row_in = fill_mask_row(a, y, ybt)
            if row_in is not None:
                pp["back_top"] = [row_in - crest[0], p["back_top"][1]]
            Pc = profile_points(R, f, Qr, crest, pp, gd)
            parts[key] = (Pc, f, R)
            rec[key] = {"R": [round(float(R[0]), 3), round(float(R[1]), 3)], "f": round(f, 3),
                        "P": [[round(float(u), 3), round(float(v), 3)] for u, v in Pc]}
        if not parts:
            continue
        Db = base_sdf(a, y)
        D = Db.copy()
        F = max(v[1] for v in parts.values())
        AA = PIX[:, 0].reshape(NY, NA); YY = PIX[:, 1].reshape(NY, NA)
        # 体の前の唇・巻きを、塊のある所だけ切る（塊が見本04 の唇の舌の上に板として残らないように）
        if cut:
            Fw = L.ss((F - cut.get("f0", 0.0)) / max(cut.get("f1", 0.6) - cut.get("f0", 0.0), 1e-6))
            a_cut = crest[0] + cut["ahead_m"] + (1.0 - Fw) * 30.0
            d_reg = L.smax(a_cut - AA, cut["y_lo"] - YY, cut.get("round_m", 1.0))      # 切る所（内が −）
            D = L.smax(D, -d_reg, cut.get("k_m", 0.8))
            rec["cut_a"] = round(float(a_cut), 2)
        Dbody = D.copy()
        Dl = {}
        for key, (Pc, f, R) in parts.items():
            Cv = spline_closed(Pc, 700)
            Dl[key] = sdf_poly(Cv, Cv, closed=True)
            k = lobes[key]["st"].get("k_m", 1.2)
            D = L.smin(D, Dl[key], k)
        # 体と塊の後ろの間の裂け目（体の前の面・巻きの内の面と、塊の後ろの縁の間の空き）を、高さごとに埋める。
        # 塊の中の空き（唇の下の凹み）や、手前の別の塊との間は埋めない（体の最後の内の点 〜 塊の最初の内の点の間だけ）。
        fill = design.get("fill")
        if fill and Dl:
            Mb = Dbody < 0
            ML = np.zeros_like(Mb)
            for key in Dl:
                ML |= Dl[key] < 0
            add = np.zeros_like(Mb)
            for iy in np.nonzero(GY >= fill["y0"])[0]:
                xl = np.nonzero(ML[iy])[0]
                if not len(xl):
                    continue
                xb = np.nonzero(Mb[iy, :xl[0]])[0]
                if len(xb) and xl[0] - xb[-1] > 1:
                    add[iy, xb[-1] + 1:xl[0]] = True
            if add.any():
                from scipy.ndimage import distance_transform_edt as edt
                dadd = np.where(add, -(edt(add) - 0.5), edt(~add) - 0.5) * FRES
                D = L.smin(D, dadd, fill.get("k_m", 0.5))
            rec["fill_cells"] = int(add.sum())
        tr = design.get("trough")
        if tr:
            for key, (Pc, f, R) in parts.items():
                p = lobes[key]["st"]["profile"]
                ca = R[0] + p["foot"][0] + tr["da"]
                dcirc = np.hypot(AA - ca, YY - tr["y"]) - tr["r"] * f
                D = L.smax(D, -dcirc, tr.get("k_m", 1.0))
        if design.get("blur_px", 0) > 0:
            from scipy.ndimage import gaussian_filter
            D = gaussian_filter(D, design["blur_px"])
        wu = float(L.ss(F / design.get("uniform_f", 0.6)))
        feats = []
        for key, (Pc, f, R) in parts.items():
            fc = lobes[key]["st"].get("feature_cols")
            if fc:
                alone = all(v[1] < 0.05 for k2, v in parts.items() if k2 != key)
                # Pc の並び：0 back_top, 1 tread, 2 groove, 3 rim, 4 nose, 5 utip, 6 rback, 7 rbot, 8 bulge, 9 shin, 10 foot, 11 bottom_back
                for nm, idx_, pr in (("rim", 3, 0), ("utip", 5, 1), ("rbot", 7, 2), ("shin", 9, 3)):
                    if nm in fc and (pr <= 1 or alone or key == "r3"):
                        feats.append((Pc[idx_], fc[nm], float(L.ss(f / design.get("anchor_f", 0.7))), pr + (0 if key == "r3" else 0.5)))
        na, ny, rinf = redistribute(a, y, D, jA, jB, inner_anchors=design.get("inner_anchors", False), w_uniform=wu, feats=feats)
        rec["w_uniform"] = round(wu, 3)
        rec.update(rinf)
        A[i], Y[i] = na, ny
        # 頂点での距離（層の印・白の印のため）
        Pn = np.c_[na, ny]
        fb = field_sample(Dbody, Pn)          # 切った後の体（唇の舌を外した体）。塊の凹みが元の唇の中で印を失わないように
        fields["base"][i] = fb
        # 層の印の下の端：② は、同じ行に ③ があれば ③ の縁の頂より label_gap_m 上まで（② の下の面が ③ の踏み面へ下りる所は印を空ける＝蹴込み）
        ycut[i, 0] = (parts["r3"][0][3][1] + design.get("label_gap_m", 0.8)) if ("r3" in parts and parts["r3"][1] > 0.05) else design.get("label_floor_m", 0.5)
        ycut[i, 1] = design.get("label_floor_m", 0.5)
        ytop3[i] = (parts["r3"][0][3][1] + design.get("label_top3_m", 0.3)) if "r3" in parts else 1e9
        # 端の細い所（重み f が小さい行）は印を付けない（② の左の端が ③ の踏み面へ、③ の右の端が ② の体へ消える所＝蹴込み）
        for kk, key in ((0, "r2"), (1, "r3")):
            if key not in parts or parts[key][1] < design.get("label_fmin", 0.35):
                ycut[i, kk] = 1e9
        for key in ("r2", "r3"):
            if key in Dl:
                fields[key][i] = field_sample(Dl[key], Pn)
        info.append(rec)
    # 行の向きのならし（作り直した行の動きだけ。K-top の行は 0）
    dA = A - A0; dY = Y - Y0
    sg = design.get("row_sigma", 0.8)
    if sg > 0:
        dA = gaussian_filter1d(dA, sg, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sg, axis=0, mode="nearest")
    dA[c >= L.C_KTOP] = 0; dY[c >= L.C_KTOP] = 0
    dA[:, :jA] = 0; dY[:, :jA] = 0
    A_s = A0 + dA; Y_s = Y0 + dY
    # ならしで断面の自己交差が増えた行は、ならす前の行へ戻す（層の境目で形の並びが違う行をまぜると折れ返るため）
    import r2_build as B2
    reverted = []
    for i in rows:
        if B2.seg_selfx(A_s[i], Y_s[i], 0, None) > B2.seg_selfx(A0[i], Y0[i], 0, None):
            if B2.seg_selfx(A[i], Y[i], 0, None) <= B2.seg_selfx(A0[i], Y0[i], 0, None):
                A_s[i], Y_s[i] = A[i], Y[i]
                reverted.append(round(float(c[i]), 2))
    A, Y = A_s, Y_s
    # 層の印：塊の距離が体の距離・ほかの塊より小さく、塊の面の近く（丸みの幅の中）の頂点
    for key, lab in (("r2", 2), ("r3", 3)):
        fk = fields[key]
        oth = fields["r3" if key == "r2" else "r2"]
        m = np.isfinite(fk) & (fk < np.nan_to_num(fields["base"], nan=9.0)) & (fk < np.nan_to_num(oth, nan=9.0)) & (fk < design.get("label_d_m", 0.6))
        m &= Y >= ycut[:, [0 if key == "r2" else 1]]
        if key == "r3":
            m &= Y <= ytop3[:, None]          # ③ の印は自分の縁の頂の少し上まで（その上の ② の体と印を離す）
        labels[m] = lab
    J = np.arange(nc)[None, :]
    lab1 = (c[:, None] >= L.C_KTOP) & (J >= B.J_TOP) & (J <= B.J_FACEBOT) & (Y >= 0.25 * L.H0)
    labels[lab1] = 1
    return c, A, Y, labels, fields, {"rows": info, "rims": {k: L.rnd(v["q"][::10], 3) for k, v in lobes.items()}, "smooth_reverted_rows_c": reverted}


def main():
    pre, dpath = sys.argv[1], sys.argv[2]
    design = json.load(open(dpath, encoding="utf-8"))
    t0 = time.time()
    c, A, Y, labels, fields, log = build(design)
    os.makedirs(os.path.dirname(pre), exist_ok=True)
    if design.get("write_candidate"):
        prov = {"route": "美術の見本06 B-LOBES Tools/GWWaveGen/as06/lobes_build.py（numpy・scipy・skimage、陰関数の塊 ② ③ を滑らかな和で体へつなぎ、行の格子へ戻す）",
                "base": "K*′ AS04F (%s, sha256 %s)" % (L.ROWS04F.replace(L.REPO + "/", ""), L.sha(L.ROWS04F)),
                "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
        B.SC.K.write_candidate(pre, c, A, Y, prov)
    else:
        np.savez(pre + "_rows.npz", c=c, A=A, Y=Y)
    np.save(pre + "_labels.npy", labels)
    np.savez_compressed(pre + "_fields.npz", **fields)
    L.jdump(pre + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("LOBES_BUILD_DONE", pre, round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
