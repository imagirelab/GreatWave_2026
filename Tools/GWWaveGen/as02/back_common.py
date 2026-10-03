# -*- coding: utf-8 -*-
"""美術の見本02 の BACK（背を一つの山にする）の共通部。py -3.10（numpy・scipy）。

利用者の Q30-2「大浪的背面似乎是两边凸起中间凹陷…合理的大浪应该是中间隆起效果最为明显，两边效果逐渐平缓」と
美術の要求書の S4（背は中ほどがいちばん高く盛り上がり、両側へなだらかに下がる一つの山。へこみの深さ 0）を測るための道具。
座標は kh_common と同じ（a = 進行方向 T、y = 高さ、c = 波峰線 E）。行は c 一定の断面、列 0..399（目印 j_B 18・j_top 90・j_tip 200）。
参照モデルは読まない（F13-1）。出力はすべて Unity/Build/Polish/sample02/back/ の下（Git 対象外）。
"""
import os
import sys
import json
import math
import hashlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for _p in (os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar_p28")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import kh_common as KC  # noqa: E402

OUT = os.path.join(REPO, "Unity", "Build", "Polish", "sample02", "back")
BASE_DIR = os.path.join(REPO, "Unity", "Build", "Polish", "28", "kstar_p28rec")
BASE_ROWS = os.path.join(BASE_DIR, "kstarP28R2rec_a45_rows.npz")
BASE_GWB = os.path.join(BASE_DIR, "kstarP28R2rec_a45.gwb")
BASE_SHA = {"gwb": "a3bb1c81a79a15b7903729bd845a2d4b2660d3a06a417a218ae66f58eeb01e94",
            "rows": "c55e048d388e41e30289d075089066c481bf2f3b99d84727c655eea9e1a437a3"}
VIEWS_JSON = os.path.join(REPO, "Tools", "GWWaveGen", "kstar_p28", "rays_views.json")
H0 = 20.752853190871733
J_B, J_TOP, J_TIP = 18, 90, 200
LEVELS = (0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90)

BLENDER = r"G:\SteamLibrary\steamapps\common\Blender\blender.exe"
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"


def load_rows(p=BASE_ROWS):
    z = np.load(p)
    return z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)


def sha256(p, chunk=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def jdump(obj, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)


# ------------------------------------------------------------------ 1 次元の山の形の読み
def dip_profile(f):
    """水を張った時のへこみ：min(左からの最大, 右からの最大) − f。一つの山（単峰）なら全部 0。"""
    f = np.asarray(f, float)
    L = np.maximum.accumulate(f)
    R = np.maximum.accumulate(f[::-1])[::-1]
    return np.minimum(L, R) - f


def concave_hull_gap(x, f):
    """上に凸な包絡（上の凸包）と f の差。上に凸な一つの山（どこにも入り江がない）なら全部 0。"""
    x = np.asarray(x, float); f = np.asarray(f, float)
    hull = []
    for i in range(len(x)):
        while len(hull) >= 2:
            i0, i1 = hull[-2], hull[-1]
            # i1 が i0→i の線の下（上の凸包から外れる）なら捨てる
            if (f[i1] - f[i0]) * (x[i] - x[i0]) <= (f[i] - f[i0]) * (x[i1] - x[i0]):
                hull.pop()
            else:
                break
        hull.append(i)
    env = np.interp(x, x[hull], f[hull])
    return env - f


def shape_stats(x, f, mid_lo=None, mid_hi=None):
    d = dip_profile(f)
    g = concave_hull_gap(x, f)
    k = int(np.argmax(f))
    out = {"max": float(f[k]), "x_at_max": float(x[k]),
           "dip_depth": float(d.max()), "x_at_dip": float(x[int(np.argmax(d))]),
           "bay_depth": float(g.max()), "x_at_bay": float(x[int(np.argmax(g))])}
    if mid_lo is not None:
        out["max_in_middle"] = bool(mid_lo <= x[k] <= mid_hi)
    return out


# ------------------------------------------------------------------ 背の読み
def crest(A, Y):
    jt = np.argmax(Y[:, :J_TIP], 1)
    H = Y[np.arange(len(Y)), jt]
    at = A[np.arange(len(A)), jt]
    return H, jt, at


def back_level_a(A, Y, jt, y):
    """各行の背（列 J_B..頂）が高さ y を最初に越える所の a（越えない行は nan）。"""
    nv = len(A)
    out = np.full(nv, np.nan)
    for i in range(nv):
        yy = Y[i, J_B:jt[i] + 1]; aa = A[i, J_B:jt[i] + 1]
        k = np.nonzero(yy >= y)[0]
        if not len(k) or k[0] == 0:
            continue
        k = k[0]
        t = (y - yy[k - 1]) / max(yy[k] - yy[k - 1], 1e-12)
        out[i] = aa[k - 1] + t * (aa[k] - aa[k - 1])
    return out


def back_profiles(c, A, Y, levels=LEVELS):
    H, jt, at = crest(A, Y)
    prof = {}
    for f in levels:
        y = f * H0
        ab = back_level_a(A, Y, jt, y)
        prof["%.2f" % f] = {"y": y, "a_back": ab, "depth_behind_crest": at - ab}
    return H, jt, at, prof


def lateral_groove(c, d, sigma_m=0.6):
    """背の位置 d(c)（後ろへ大きいほど出っ張り）の c 方向の二階微分（なめらかにしてから）。正 ＝ 溝（へこみ）。"""
    ok = np.isfinite(d)
    if ok.sum() < 7:
        return np.full_like(d, np.nan)
    cc = c[ok]; dd = d[ok]
    # 等間隔に置き直してから
    xs = np.arange(cc.min(), cc.max() + 1e-9, 0.1)
    ds = np.interp(xs, cc, dd)
    from scipy.ndimage import gaussian_filter1d
    ds = gaussian_filter1d(ds, sigma_m / 0.1, mode="nearest")
    d2 = np.gradient(np.gradient(ds, xs), xs)
    out = np.full_like(d, np.nan)
    out[ok] = np.interp(cc, xs, d2)
    return out


# ------------------------------------------------------------------ カメラ（粘土の描画と同じ視点）
def load_views():
    v = json.load(open(VIEWS_JSON, encoding="utf-8"))
    out = {}
    for e in v["standard"] + v["user_failure"]:
        out[e["name"]] = e
    return out


def cam_axes(eye, tgt):
    eye = np.asarray(eye, float); tgt = np.asarray(tgt, float)
    f = tgt - eye; f /= np.linalg.norm(f)
    r = np.cross(np.array([0.0, 1.0, 0.0]), f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return eye, r, u, f


def project(P, eye, tgt, vfov, w, h):
    """Unity ワールド → 画素 (x 右, y 下, 奥行き)。縦の画角 vfov。"""
    e, r, u, f = cam_axes(eye, tgt)
    d = np.asarray(P, float) - e
    cx, cy, cz = d @ r, d @ u, d @ f
    t = math.tan(math.radians(vfov) / 2.0)
    asp = w / float(h)
    x = (0.5 + 0.5 * (cx / cz) / (t * asp)) * w
    y = (0.5 - 0.5 * (cy / cz) / t) * h
    return x, y, cz


def silhouette_top(c, A, Y, view, up=3):
    """視点の画で、各画素の列での波の一番上（画素 y）と、それを作る行の c。行の向きに up 倍に細かく補間して隙間をなくす。"""
    nv, nu = A.shape
    # 行の間を補間（c 方向）
    t = np.linspace(0, 1, up, endpoint=False)
    cc = (c[:-1, None] * (1 - t) + c[1:, None] * t).ravel()
    AA = (A[:-1, None, :] * (1 - t)[None, :, None] + A[1:, None, :] * t[None, :, None]).reshape(-1, nu)
    YY = (Y[:-1, None, :] * (1 - t)[None, :, None] + Y[1:, None, :] * t[None, :, None]).reshape(-1, nu)
    cc = np.r_[cc, c[-1]]; AA = np.r_[AA, A[-1:]]; YY = np.r_[YY, Y[-1:]]
    # 列の向きも 2 倍に
    AA = np.concatenate([AA, 0.5 * (AA[:, :-1] + AA[:, 1:])], 1)
    YY = np.concatenate([YY, 0.5 * (YY[:, :-1] + YY[:, 1:])], 1)
    X = KC.world(cc, AA, YY).reshape(-1, 3)
    C = np.broadcast_to(cc[:, None], AA.shape).ravel()
    w, h = int(view["w"]), int(view["h"])
    x, y, z = project(X, view["eye"], view["tgt"], view["vfov"], w, h)
    keep = (YY.ravel() > 0.05) & (z > 0)
    x, y, C = x[keep], y[keep], C[keep]
    xi = np.floor(x).astype(int)
    m = (xi >= 0) & (xi < w)
    xi, y, C = xi[m], y[m], C[m]
    top = np.full(w, np.inf)
    np.minimum.at(top, xi, y)
    ctop = np.full(w, np.nan)
    order = np.lexsort((y, xi))
    xs_sorted = xi[order]
    first = np.r_[True, xs_sorted[1:] != xs_sorted[:-1]]
    ctop[xs_sorted[first]] = C[order][first]
    return top, ctop
