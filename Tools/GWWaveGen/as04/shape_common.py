# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり（Q32・要求書 S8〜S11）の共通部。py -3.10（numpy・scipy・OpenCV）。

- 土台：見本02・03 の主役波 K*′ AS02C の t*（行 240 × 列 400。行 = c 一定の断面、列 = 背の根元 → 頂 90 → 唇の先 200 → 唇の下・内の面 → 角 314 → 前の面）。
- 断面の座標（kh_common）：a = 進行方向 T（+ が前・原画のカメラの側）、y = 高さ、c = 波峰線 E（+ が原画視点の右・奥）。
- 原画のカメラは、形の測り（出っ張りの区域・輪郭の近い値・層の深さ）にだけ使う。色は面へ写さない（Q28）。
- 参照モデルの OBJ・写真は読まない（F13-1）。数は調べ S（Build/Polish/sample04/map/s4_plan.json）から取る。
出力はすべて Git 対象外の Unity/Build/Polish/sample04/shape/ の下。
"""
import hashlib
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h", "Tools/GWWaveGen/as04", "Tools/GWWaveGen/as02"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import claws_common as CC  # noqa: E402
import kh_common as K  # noqa: E402

U = CC.U
OUT = REPO + "/Unity/Build/Polish/sample04/shape"
BASE_ROWS = REPO + "/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz"
BASE_GWB = REPO + "/Unity/Build/Polish/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb"
PLAN = REPO + "/Unity/Build/Polish/sample04/map/s4_plan.json"
H0 = 20.752853190871733
J_B, J_TOP, J_TIP, J_CORNER, J_FACEBOT = 18, 90, 200, 314, 379
A_DISP = 0.4163454124903624
OFFX = 156.66152659984573
# 利用者の区域（原画の画素。s4_common と同じ点）
REG1 = [(851, 700), (900, 420), (1150, 300), (1450, 250), (1900, 330), (2290, 700), (2297, 1130), (1950, 1134), (1700, 900),
        (1500, 700), (1300, 620), (1100, 760)]
REG2 = [(640, 960), (900, 900), (1180, 930), (1400, 1010), (1400, 1250), (1150, 1420), (850, 1400), (650, 1250)]
REG3 = [(2, 1110), (630, 1110), (630, 1849), (2, 1849)]
REG4 = [(0, 872), (97, 858), (233, 856), (360, 862), (350, 911), (214, 950), (97, 969), (0, 930)]
BULGE_DISP = [(551, 334), (624, 270), (720, 249), (840, 264), (891, 308), (865, 340), (789, 404), (739, 419), (662, 391), (586, 355)]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _np(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(type(o))


def jdump(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)


def rnd(v, k=3):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return None
    return round(float(v), k)


def ss(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ref_to_disp(P):
    P = np.asarray(P, np.float64)
    return np.stack([A_DISP * (P[..., 0] + 0.5) - 0.5 + OFFX, A_DISP * (P[..., 1] + 0.5) - 0.5], -1)


def disp_to_ref(P):
    P = np.asarray(P, np.float64)
    return np.stack([(P[..., 0] + 0.5 - OFFX) / A_DISP - 0.5, (P[..., 1] + 0.5) / A_DISP - 0.5], -1)


def load_rows(p=BASE_ROWS):
    z = np.load(p)
    return z["c"].astype(np.float64), z["A"].astype(np.float64), z["Y"].astype(np.float64)


def arclen(a, y):
    return np.r_[0.0, np.cumsum(np.hypot(np.diff(a), np.diff(y)))]


def grid_tris(R, C):
    """セル (r, c) ごとに 2 つ（番号 2·(r·(C−1)+c)+h）。"""
    r, c = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a = (r * C + c).ravel(); b = ((r + 1) * C + c).ravel(); cc = (r * C + c + 1).ravel(); d = ((r + 1) * C + c + 1).ravel()
    return np.stack([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)], 1).reshape(-1, 3)


def tri_cell(t, C):
    cell = t // 2
    return cell // (C - 1), cell % (C - 1)


def paint_cam(W=1920, H=1080):
    return CC.painting_cam() if (W, H) == (1920, 1080) else U.CamWH(json.load(open(U.TRUTH, encoding="utf-8")), W, H)


def zbuf(cam, X, c0=0, c1=None):
    """X (R, C, 3) の格子を描いた id（三角形の番号 + 1、0 は空）と 1/z。列 c0..c1 だけ。"""
    R, C = X.shape[:2]
    c1 = C - 1 if c1 is None else c1
    T = grid_tris(R, C)
    rr, cc = tri_cell(np.arange(len(T)), C)
    keep = np.nonzero((cc >= c0) & (cc < c1))[0]
    ids = keep + 1
    idb, zb = U.raster(cam, X.reshape(-1, 3)[T[keep]], ids)
    return idb, zb, T


def poly_mask(poly, W=1920, H=1080, step=1):
    m = np.zeros((H, W), np.uint8)
    cv2.fillPoly(m, [np.round(np.asarray(poly, float)).astype(np.int32)], 1)
    ys, xs = np.nonzero(m)
    sel = (ys % step == 0) & (xs % step == 0)
    return xs[sel], ys[sel]


def hit_points(cam, idb, zb, T, X, xs, ys):
    """画素 (xs, ys) の最初の当たりの三角形・ワールドの点・(行, 列) の小数。"""
    R, C = X.shape[:2]
    tid = idb[ys, xs] - 1
    ok = tid >= 0
    z = np.where(zb[ys, xs] > 0, 1.0 / np.maximum(zb[ys, xs], 1e-12), np.nan)
    d = cam.ray(xs.astype(float), ys.astype(float))
    P = cam.pos[None, :] + d * (z / (d @ cam.f))[:, None]
    r, c = tri_cell(np.maximum(tid, 0), C)
    # 三角形の中の重心座標で行・列の小数を出す
    V = X.reshape(-1, 3)
    Tt = T[np.maximum(tid, 0)]
    A_, B_, C_ = V[Tt[:, 0]], V[Tt[:, 1]], V[Tt[:, 2]]
    v0 = B_ - A_; v1 = C_ - A_; v2 = P - A_
    d00 = (v0 * v0).sum(1); d01 = (v0 * v1).sum(1); d11 = (v1 * v1).sum(1); d20 = (v2 * v0).sum(1); d21 = (v2 * v1).sum(1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-12)
    wb = (d11 * d20 - d01 * d21) / den; wc = (d00 * d21 - d01 * d20) / den; wa = 1 - wb - wc
    Ti = T[np.maximum(tid, 0)]
    ri, ci = np.divmod(Ti, C)
    rf = wa * ri[:, 0] + wb * ri[:, 1] + wc * ri[:, 2]
    cf = wa * ci[:, 0] + wb * ci[:, 1] + wc * ci[:, 2]
    return ok, P, rf, cf


def sec(P):
    return K.sec(P)


def world(c, A, Y):
    return K.world(c, A, Y)


# ---------------------------------------------------------------- 出っ張り（S8）の測り
def bulge_metric(c, A, Y, step=2, cam=None, idb=None, zb=None):
    """利用者の黄色の線の中の原画の射線の最初の当たりの点の、その行の内の面（列 205〜314、唇の下 → 巻きの奥 → 角）の線からの距離（m）。
    当たりが内の面そのもの（列 ≥ 200）なら 0。唇の外の面なら、その点から内の面の折れ線までの距離（＝ 唇の板の厚み）。
    参考に、見本04 の調べ S と同じ「列 205〜299 に当てた円からの距離」も返す。"""
    X = world(c, A, Y)
    cam = cam or paint_cam()
    if idb is None:
        idb, zb, T = zbuf(cam, X, J_B, 394)
    else:
        T = grid_tris(*X.shape[:2])
    xs, ys = poly_mask(BULGE_DISP, step=step)
    ok, P, rf, cf = hit_points(cam, idb, zb, T, X, xs, ys)
    S_ = sec(P)
    dev = np.full(len(xs), np.nan); dcirc = np.full(len(xs), np.nan)
    rows = np.round(rf).astype(int)
    for i in np.unique(rows[ok]):
        m = ok & (rows == i)
        a, y = A[i], Y[i]
        jj = np.arange(205, 315)
        pa, py = a[jj], y[jj]
        # 折れ線までの距離（細かく）
        sa = np.interp(np.linspace(0, len(jj) - 1, 8 * len(jj)), np.arange(len(jj)), pa)
        sy = np.interp(np.linspace(0, len(jj) - 1, 8 * len(jj)), np.arange(len(jj)), py)
        q = S_[m][:, :2]
        dd = np.sqrt(((q[:, None, 0] - sa[None]) ** 2 + (q[:, None, 1] - sy[None]) ** 2).min(1))
        inner = cf[m] >= 200.0
        dev[m] = np.where(inner, 0.0, dd)
        j2 = np.arange(205, 300)
        Am = np.c_[2 * a[j2], 2 * y[j2], np.ones(len(j2))]
        sol, *_ = np.linalg.lstsq(Am, a[j2] ** 2 + y[j2] ** 2, rcond=None)
        rad = np.sqrt(sol[2] + sol[0] ** 2 + sol[1] ** 2)
        dcirc[m] = np.hypot(q[:, 0] - sol[0], q[:, 1] - sol[1]) - rad
    v = dev[ok]
    out = {"rays": int(ok.sum()), "first_hit_inner_face_share": rnd(float((cf[ok] >= 200).mean())),
           "first_hit_cols": {k: rnd(np.percentile(cf[ok], p), 1) for k, p in (("p5", 5), ("p50", 50), ("p95", 95))},
           "first_hit_rows": {k: rnd(np.percentile(rf[ok], p), 1) for k, p in (("p5", 5), ("p50", 50), ("p95", 95))},
           "dev_from_inner_face_m": {k: rnd(np.percentile(v, p)) for k, p in (("p50", 50), ("p90", 90), ("p95", 95))} | {"max": rnd(v.max())},
           "dev_from_circle_s4_m": {k: rnd(np.percentile(np.abs(dcirc[ok]), p)) for k, p in (("p50", 50), ("p95", 95))}}
    return out


# ---------------------------------------------------------------- 原画視点の一番上の輪郭（近い値）
def top_outline(c, A, Y, cam=None):
    """表示の各列の一番上の画素 y（空との境）と、その画素の (行, 列)。"""
    X = world(c, A, Y)
    cam = cam or paint_cam()
    idb, zb, T = zbuf(cam, X, J_B, 394)
    cov = idb > 0
    H, W = cov.shape
    top = np.full(W, np.nan)
    has = cov.any(0)
    top[has] = np.argmax(cov[:, has], 0)
    return top, idb, zb, T


def band_extent(c, A, Y, H=20.27, fr=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    """高さの帯ごとの c の幅（行ごとの頂（列 18〜200 の最大）が f·H を越える行の c の範囲）。調べ S-3 と同じ読み。"""
    Hc = Y[:, J_B:J_TIP + 1].max(1)
    out = {}
    for f in fr:
        k = np.nonzero(Hc >= f * H)[0]
        if not len(k):
            out["%.1f" % f] = None
            continue
        # 端は行の間で直線に補う
        i0, i1 = k.min(), k.max()
        def cross(ia, ib):
            if ia < 0 or ib >= len(c):
                return c[max(min(ia, ib), 0)] if ia < 0 else c[min(max(ia, ib), len(c) - 1)]
            t = (f * H - Hc[ia]) / max(Hc[ib] - Hc[ia], 1e-9)
            return c[ia] + t * (c[ib] - c[ia])
        lo = cross(i0 - 1, i0) if i0 > 0 else c[0]
        hi = cross(i1 + 1, i1) if i1 < len(c) - 1 else c[-1]
        out["%.1f" % f] = {"c_lo": rnd(lo, 2), "c_hi": rnd(hi, 2), "width_m": rnd(hi - lo, 2)}
    return out


_GATE = {}


def gate_proxy(c, A, Y, overlay=None):
    """原画視点の輪郭の関門の近い値（評価基準 rubric_check --gate と同じ gw_wavegen_v1.preview_metrics。numpy の描画。
    Unity の描画の関門（sweep_gates）より 0.1〜0.35 px 小さく出る：AS02C で 78 2.439／130 3.230／131 3.355（Unity 2.741／3.582／3.442））。"""
    if not _GATE:
        sys.path.insert(0, REPO + "/Tools/PaintingTruth"); sys.path.insert(0, REPO + "/Tools/GWWaveGen")
        import truthlib as TL
        import gw_wavegen_v1 as V1
        params = TL.load_json(REPO + "/Tools/GWWaveGen/params_v2_af26r01.json")
        tgt = V1.Target(); fr = V1.Frame(tgt.spec, float(params["alpha_deg"]), params["anchor"], tgt)
        _GATE.update(V1=V1, tgt=tgt, fr=fr)
    V1, tgt, fr = _GATE["V1"], _GATE["tgt"], _GATE["fr"]
    nv, nu = A.shape
    Xw = fr.world(c, A, Y); tr_ = V1.triangles(nu, nv)
    outp = overlay or (OUT + "/tmp/_gate_overlay.png")
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        g = V1.preview_metrics(fr, tgt, Xw, tr_, outp, "AS04 shape")
    return {k: {"max": rnd(v["max_px"]), "p95": rnd(v["p95_px"])} for k, v in g.items() if k in ("78", "130", "131", "132", "72")}


def turn_check(a, y, j0, j1):
    """列 j0..j1 の折れ線の曲がり（左回り +）。右へ曲がる所（凸の膝）の最大の角（度/m）と、その列。"""
    da = np.diff(a[j0:j1 + 1]); dy = np.diff(y[j0:j1 + 1])
    ang = np.arctan2(dy, da)
    t = np.diff(np.unwrap(ang))
    L = 0.5 * (np.hypot(da[:-1], dy[:-1]) + np.hypot(da[1:], dy[1:]))
    k = np.degrees(t) / np.maximum(L, 1e-6)
    i = int(np.argmin(k))
    return float(k[i]), j0 + 1 + i
