# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4（Q32、S9）：左端の別の小さな青い波（④）の共通部。py -3.10（numpy・scipy・OpenCV）。

- 座標は主役波の断面の座標（kh_common：a = 進行方向 T、y = 高さ、c = 波峰線 E。+c は原画視点の右・奥）。
- 静止のメッシュの書式 GreatWave.AS03.static_mesh/1 の読み書き（見本03 の AS03StaticMesh が読む。チャンネルごとの平面の float32、続いて uint32 の三角形）。
- 「地面」G(a, c)：主役波の行（c 一定の断面）の一番上の面の高さと、近い海（設計30 の t* の ds30_tstar.gwb）の高さの大きい方。
  別の波はこの地面より上にだけ作る（主役波と交わらない、海へ段なくつながる）。
原画の色は面へ写さない（Q28）。原画のカメラは、輪郭の区間 78（④）の射線と、帯の境を測る射線にだけ使う。参照モデルの OBJ・写真は読まない。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/as04", "Tools/GWWaveGen/as01", "Tools/GWWaveGen/kstar_h"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import s4_common as S  # noqa: E402

K = S.K
CC = S.CC
H0 = S.H0
OUT = REPO + "/Unity/Build/Polish/sample04/wave4"
SHARED = REPO + "/Unity/Build/Polish/sample04/shared"
HERO_ROWS_AS02C = S.ROWS
HERO_MESH_AS02C = REPO + "/Unity/Build/Polish/sample04/mat/mesh/hero_smooth_as02c.json"
PLAN = REPO + "/Unity/Build/Polish/sample04/map/s4_plan.json"
CHANNELS = [["position", 3], ["normal", 3], ["tangent", 4], ["uv3", 4], ["uv4", 4], ["uv5", 4], ["uv6", 4]]


def sha(p):
    return S.sha(p)


def jdump(p, o):
    S.jdump(p, o)


def rnd(v, k=3):
    return S.rnd(v, k)


# ---------------------------------------------------------------- 静止のメッシュ
def read_static(json_path):
    j = json.load(open(json_path, encoding="utf-8"))
    n, m = int(j["vertices"]), int(j["triangles"])
    b = np.fromfile(os.path.join(os.path.dirname(json_path), j["bin"]), np.uint8)
    ch, off = {}, 0
    for name, k in j["channels"]:
        ch[name] = np.frombuffer(b, np.float32, n * k, off).reshape(n, k).copy()
        off += n * k * 4
    tri = np.frombuffer(b, np.uint32, m * 3, off).reshape(m, 3).copy()
    return ch, tri, j


def write_static(json_path, ch, tri, extra=None):
    """ch：チャンネル名 → (N, k) の配列（CHANNELS の順で書く）、tri：(M, 3)。戻り値は bin の SHA-256。"""
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    stem = os.path.splitext(os.path.basename(json_path))[0]
    binp = os.path.join(os.path.dirname(json_path), stem + ".bin")
    n = len(ch["position"])
    with open(binp, "wb") as f:
        for name, k in CHANNELS:
            a = np.ascontiguousarray(np.asarray(ch[name], np.float32).reshape(n, k))
            f.write(a.tobytes())
        f.write(np.ascontiguousarray(np.asarray(tri, np.uint32)).tobytes())
    h = sha(binp)
    j = {"schema": "GreatWave.AS03.static_mesh/1", "vertices": int(n), "triangles": int(len(tri)), "channels": CHANNELS,
         "bin": stem + ".bin", "sha256": h, "bytes": os.path.getsize(binp)}
    if extra:
        j.update(extra)
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(j, f, ensure_ascii=False, indent=1)
    return h


def vertex_normals(P, tri):
    n = np.zeros_like(P)
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    for k in range(3):
        np.add.at(n, tri[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


# ---------------------------------------------------------------- 主役波の行と地面
def load_rows(path):
    d = np.load(path)
    return d["c"].astype(np.float64), d["A"].astype(np.float64), d["Y"].astype(np.float64)


def row_top_profiles(A, Y, a_grid):
    """行ごとに、断面の折れ線の一番上の高さ y_top(a)（a_grid の上。折れ線が覆わない所は −inf）。"""
    R = A.shape[0]
    top = np.full((R, len(a_grid)), -np.inf)
    for r in range(R):
        a0, a1 = A[r, :-1], A[r, 1:]
        y0, y1 = Y[r, :-1], Y[r, 1:]
        lo, hi = np.minimum(a0, a1), np.maximum(a0, a1)
        for s0 in range(0, len(a_grid), 512):
            ag = a_grid[s0:s0 + 512]
            m = (ag[None, :] >= lo[:, None]) & (ag[None, :] <= hi[:, None])
            da = np.where(np.abs(a1 - a0) < 1e-9, 1e-9, a1 - a0)
            t = (ag[None, :] - a0[:, None]) / da[:, None]
            yy = np.where(m, y0[:, None] + t * (y1 - y0)[:, None], -np.inf)
            top[r, s0:s0 + 512] = yy.max(0)
    return top


class Ground:
    """地面 G(a, c) = max(主役波の一番上の面, 海)。主役波の行は c 一定の断面（c の順）。行の間は c で線形に補う。"""

    def __init__(self, rows_path, a_lo=-60.0, a_hi=20.0, da=0.05, sea=True):
        self.c, A, Y = load_rows(rows_path)
        # 行ごとの主役波の頂（背の根元 列 18 〜 唇の先 列 200 の一番高い点）の a と高さ
        # 背の側の頂（列 18〜120 の一番高い点。唇の先が頂より高い行でも背の頂を取る）
        jj = np.argmax(Y[:, 18:120], 1) + 18
        self.crest_a = A[np.arange(len(jj)), jj]
        self.crest_y = Y[np.arange(len(jj)), jj]
        self.a = np.arange(a_lo, a_hi + 1e-9, da)
        self.top = row_top_profiles(A, Y, self.a)
        self.sea = None
        if sea:
            from scipy.spatial import cKDTree
            sg = K.read_gwb(S.SEA_NEAR)
            Q = K.sec(sg["X"])
            self.sea_tree = cKDTree(Q[:, [0, 2]])
            self.sea_y = Q[:, 1]

    def hero(self, a, c):
        a = np.asarray(a, np.float64)
        c = np.asarray(c, np.float64)
        ia = np.clip((a - self.a[0]) / (self.a[1] - self.a[0]), 0, len(self.a) - 1.001)
        k0 = np.floor(ia).astype(int)
        fa = ia - k0
        ir = np.interp(c, self.c, np.arange(len(self.c)), left=-1, right=-1)
        out = np.full(a.shape, -np.inf)
        ok = ir >= 0
        r0 = np.clip(np.floor(ir).astype(int), 0, len(self.c) - 2)
        fr = np.clip(ir - r0, 0, 1)

        def g(r, k):
            return self.top[r, k]
        v00, v01 = g(r0, k0), g(r0, k0 + 1)
        v10, v11 = g(r0 + 1, k0), g(r0 + 1, k0 + 1)
        # 覆わない所（−inf）はそのまま（線形の補いで −inf が混ざれば −inf）
        with np.errstate(invalid="ignore"):
            v0 = np.where(np.isfinite(v00) & np.isfinite(v01), v00 * (1 - fa) + v01 * fa, np.maximum(v00, v01))
            v1 = np.where(np.isfinite(v10) & np.isfinite(v11), v10 * (1 - fa) + v11 * fa, np.maximum(v10, v11))
            v = np.where(np.isfinite(v0) & np.isfinite(v1), v0 * (1 - fr) + v1 * fr, np.maximum(v0, v1))
        out[ok] = v[ok]
        return out

    def sea_h(self, a, c):
        if self.sea is None and not hasattr(self, "sea_tree"):
            return np.zeros(np.shape(a))
        d, k = self.sea_tree.query(np.stack([np.ravel(a), np.ravel(c)], -1))
        y = np.where(d < 3.0, self.sea_y[k], 0.0)
        return y.reshape(np.shape(a))

    def __call__(self, a, c):
        h = self.hero(a, c)
        s = self.sea_h(a, c)
        return np.maximum(np.where(np.isfinite(h), h, -1e9), s)


def softmax_above(yw, g, eps=0.03, k=0.25):
    """yw を地面 g の上 eps に、なめらかに載せる。x = yw − g − eps が −k 以下ならちょうど g + eps、k 以上ならちょうど yw、
    その間は 2 次のつなぎ (x + k)²/(4k)（1 回微分まで続く。softplus と違い、遠くで k·ln2 の浮きが残らない）。"""
    x = yw - g - eps
    return g + eps + np.where(x >= k, x, np.where(x <= -k, 0.0, (x + k) ** 2 / (4 * k)))
