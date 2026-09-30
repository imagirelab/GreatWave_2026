# -*- coding: utf-8 -*-
"""設計43：船用水面データの共通の道具（numpy）。

- DS27 形式のシート（主役波 F_final・設計30 の near・far）を、Unity の DS30SheetPlayer と同じ式で復号する
  （16 bit + 精度の層、不等間隔の節点の 3 次 Hermite の 4 層の重み DS27KeyposePlayer.Weights、枠の原点 O(τ) の線形補間）。
- 時間曲線 τ(t)（DS27TimeWarp.TauAt と同じ線形補間）。
- 鉛直の線とシートの三角形の交わり（表示面の高さ。主役波は本体の列 18〜394 だけ、far はすその四角を除く）。
- 設計30 の海の式 sea_eta に、far の半径方向の弱め（ds30_params.json の far_taper_start_m・far_taper_end_m）を足した式（設計43 で書き足す）。
座標：Unity の世界（m、Y 上）。τ は物理の時刻（t* = 0）、t は体験の時刻（t* = 12 s）。
"""
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DS30 = os.path.join(REPO, "Tools", "GWWaveGen", "ds30")
if DS30 not in sys.path:
    sys.path.insert(0, DS30)
import ds30_sea as S  # noqa: E402

HERO_DIR = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "art_on")
NEAR_DIR = os.path.join(REPO, "Unity", "Build", "Design", "30", "sea", "near")
FAR_DIR = os.path.join(REPO, "Unity", "Build", "Design", "30", "sea", "far")
TIMEWARP = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "F_final", "timewarp_F_final.json")
OUT = os.path.join(REPO, "Unity", "Build", "Design", "43", "boatwater")
PARAMS30 = os.path.join(DS30, "ds30_params.json")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, obj, indent=1):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)


# ---------------------------------------------------------------- 時間
class TimeWarp:
    def __init__(self, path=TIMEWARP):
        d = load_json(path)
        self.t = np.array(d["t"], np.float64)
        self.tau = np.array(d["tau"], np.float64)
        self.t_star = float(d["t_star_s"])

    def tau_at(self, t):
        return float(np.interp(t, self.t, self.tau))


def hermite_weights(tk, t):
    """DS27KeyposePlayer.Weights と同じ（4 層と重み）。"""
    n = len(tk)
    if n == 1 or t <= tk[0]:
        return (0, 0, 0, 0), (0.0, 1.0, 0.0, 0.0)
    if t >= tk[-1]:
        return (n - 1,) * 4, (0.0, 1.0, 0.0, 0.0)
    i1 = int(np.searchsorted(tk, t, side="right") - 1)
    i1 = min(max(i1, 0), n - 2)
    i2 = i1 + 1
    i0 = max(i1 - 1, 0)
    i3 = min(i2 + 1, n - 1)
    t1, t2 = tk[i1], tk[i2]
    D = t2 - t1
    s = (t - t1) / D
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    w0, w1, w2, w3 = 0.0, h00, h01, 0.0
    if i0 == i1:
        w2 += h10; w1 -= h10
    else:
        f = h10 * D / (t2 - tk[i0]); w2 += f; w0 -= f
    if i3 == i2:
        w2 += h11; w1 -= h11
    else:
        f = h11 * D / (tk[i3] - t1); w3 += f; w1 -= f
    return (i0, i1, i2, i3), (w0, w1, w2, w3)


# ---------------------------------------------------------------- シート
class Sheet:
    def __init__(self, d, name, col_range=None, drop_last_row_quads=False):
        self.dir, self.name = d, name
        k = load_json(os.path.join(d, "ds27_keypose.json"))
        self.k = k
        self.L, self.R, self.C = k["layers"], k["rows"], k["cols"]
        self.bmin = np.array(k["bbox_min"], np.float64)
        self.bsz = np.array(k["bbox_size"], np.float64)
        self.knots = np.array(k["knot_tau"], np.float64)
        self.ft = np.array(k["frame"]["tau"], np.float64)
        self.fo = np.array(k["frame"]["origin"], np.float64)
        self.hi = np.memmap(os.path.join(d, k["pos_file"]), dtype="<u2", mode="r", shape=(self.L, self.R, self.C, 4))
        self.lo = np.memmap(os.path.join(d, k["pos_lo_file"]), dtype="u1", mode="r", shape=(self.L, self.R, self.C, 4))
        # 描く四角の範囲（頂点の列 c0..c1 の間の四角）
        self.c0, self.c1 = (0, self.C - 1) if col_range is None else col_range
        self.r1 = self.R - 1 - (1 if drop_last_row_quads else 0)   # 四角の行 0..r1-1
        self._cache = {}

    def layer(self, i):
        if i in self._cache:
            return self._cache[i]
        q = self.hi[i, :, :, :3].astype(np.float64) + self.lo[i, :, :, :3].astype(np.float64) / 255.0 - 0.5
        X = self.bmin + q / 65535.0 * self.bsz
        if len(self._cache) > 8:
            self._cache.pop(next(iter(self._cache)))
        self._cache[i] = X
        return X

    def origin(self, tau):
        return np.array([np.interp(tau, self.ft, self.fo[:, j]) for j in range(3)])

    def world(self, tau):
        idx, w = hermite_weights(self.knots, tau)
        X = np.zeros((self.R, self.C, 3))
        for i, wi in zip(idx, w):
            if wi != 0.0:
                X += wi * self.layer(i)
        return X + self.origin(tau)[None, None, :]


def load_sheets():
    P = load_json(PARAMS30)
    jb, je = P["hero"]["body_cols"]
    hero = Sheet(HERO_DIR, "hero", col_range=(jb, je))
    near = Sheet(NEAR_DIR, "near")
    far = Sheet(FAR_DIR, "far", drop_last_row_quads=True)
    return hero, near, far


def vertical_hits(V, r1, c0, c1, Q, pad=0.0):
    """V: (R, C, 3) 世界の頂点。四角 (r, c)（r < r1、c0 ≤ c < c1）の 2 つの三角形と、点 Q (N, 2) の鉛直の線の交わり。
    戻り値：点ごとの [(y, r, c, tri), ...]（重複を含む。呼ぶ側で近い値をまとめる）。"""
    A = V[:r1, c0:c1]; B = V[1:r1 + 1, c0:c1]; Cc = V[:r1, c0 + 1:c1 + 1]; D = V[1:r1 + 1, c0 + 1:c1 + 1]
    xs = np.stack([A[..., 0], B[..., 0], Cc[..., 0], D[..., 0]], 0)
    zs = np.stack([A[..., 2], B[..., 2], Cc[..., 2], D[..., 2]], 0)
    xmin, xmax, zmin, zmax = xs.min(0), xs.max(0), zs.min(0), zs.max(0)
    out = [[] for _ in range(len(Q))]
    qx0, qx1 = Q[:, 0].min() - pad, Q[:, 0].max() + pad
    qz0, qz1 = Q[:, 1].min() - pad, Q[:, 1].max() + pad
    cand = np.nonzero((xmax >= qx0) & (xmin <= qx1) & (zmax >= qz0) & (zmin <= qz1))
    if len(cand[0]) == 0:
        return out
    rr, cc = cand
    for tri in (0, 1):
        if tri == 0:
            P0, P1, P2 = A[rr, cc], B[rr, cc], Cc[rr, cc]
        else:
            P0, P1, P2 = Cc[rr, cc], B[rr, cc], D[rr, cc]
        ex1 = P1[:, [0, 2]] - P0[:, [0, 2]]
        ex2 = P2[:, [0, 2]] - P0[:, [0, 2]]
        det = ex1[:, 0] * ex2[:, 1] - ex1[:, 1] * ex2[:, 0]
        ok = np.abs(det) > 1e-12
        for n in range(len(Q)):
            d = Q[n][None, :] - P0[:, [0, 2]]
            u = (d[:, 0] * ex2[:, 1] - d[:, 1] * ex2[:, 0]) / np.where(ok, det, 1.0)
            v = (ex1[:, 0] * d[:, 1] - ex1[:, 1] * d[:, 0]) / np.where(ok, det, 1.0)
            m = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9)
            if m.any():
                y = P0[m, 1] + u[m] * (P1[m, 1] - P0[m, 1]) + v[m] * (P2[m, 1] - P0[m, 1])
                for yy, r_, c_ in zip(y, rr[m], cc[m] + c0):
                    out[n].append((float(yy), int(r_), int(c_), tri))
    return out


def merge_hits(hits, tol=1e-4):
    ys = sorted(h[0] for h in hits)
    outv = []
    for y in ys:
        if not outv or y - outv[-1] > tol:
            outv.append(y)
    return outv


# ---------------------------------------------------------------- 海の式（設計30 の sea_eta ＋ far の半径方向の弱め）
class SeaFunction:
    def __init__(self):
        self.P = load_json(PARAMS30)
        self.hero = S.Hero()
        self.sea = S.Sea(self.hero)
        self.feat = S.Features(self.hero, self.P)
        nk = load_json(os.path.join(NEAR_DIR, "ds27_keypose.json"))
        self.feat.growth_knots = np.array(nk["growth_knots"], np.float64)
        G = self.P["grid"]
        AF, AB, CR, CL = G["stadium_a_front_m"], G["stadium_a_back_m"], G["stadium_c_right_m"], G["stadium_c_left_m"]
        self.cen_ac = np.array([0.5 * (AF + AB), 0.5 * (CR + CL)])
        self.r0, self.r1 = float(G["far_taper_start_m"]), float(G["far_taper_end_m"])

    def taper(self, x, z, tau):
        """far の半径方向の弱め：波の枠とともに動く競技場の中心から半径 r。w = 1 − smoothstep((r − 380)/(600 − 380))。"""
        O = self.hero.origin(tau)
        a = (np.asarray(x) - O[0]) * self.hero.t[0] + (np.asarray(z) - O[2]) * self.hero.t[2]
        c = (np.asarray(x) - O[0]) * self.hero.e[0] + (np.asarray(z) - O[2]) * self.hero.e[2]
        r = np.hypot(a - self.cen_ac[0], c - self.cen_ac[1])
        return 1.0 - S.smoothstep((r - self.r0) / (self.r1 - self.r0)), r

    def eta(self, x, z, tau, taper=True):
        O = self.hero.origin(tau)
        x = np.asarray(x, np.float64); z = np.asarray(z, np.float64)
        a = (x - O[0]) * self.hero.t[0] + (z - O[2]) * self.hero.t[2]
        c = (x - O[0]) * self.hero.e[0] + (z - O[2]) * self.hero.e[2]
        base = self.sea.eta(x, z, tau)
        if taper:
            w, _ = self.taper(x, z, tau)
            base = w * base
        return base + self.feat.g(tau) * self.feat.shape(a, c)["total"]
