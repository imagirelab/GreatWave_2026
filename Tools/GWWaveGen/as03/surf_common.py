# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2（彫りの面とシェーダー 2 つ）の共通の道具（numpy。Unity の描画ではない）。

- 主役波は見本02 の K*′ AS02C の t*（keypose の包み hero_pkg_AS02C の τ = 0。Unity が描く位置そのもの）。
- 面の座標は見本02 の属性（s01a v2：A = (F, hrel, u, w)、B = (gw, hrow, Ls, X·L̂)、C = (t* の法線, 0)）。
- 稜（彫りの溝）の並びと断面の式 groove_h は、シェーダー AS03Common.cginc の AS03GrooveH と同じ式（どちらかを変えたら両方を変える）。
- 数は調べ S1 の sculpture_spec.json（彫刻の写真と参照モデルから測った数）から取り、生成器は参照モデルの OBJ も写真も読まない（F13-1）。
- 原画カメラの投影は使わない（Q28）。色・模様は面の座標・高さ・ワールドに固定した光で決まる。
"""
import hashlib
import json
import os
import sys

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/ds33", "Tools/GWWaveGen/pl33", "Tools/GWWaveGen/sample01"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)

S02 = REPO + "/Unity/Build/Polish/sample02/fix01"
HERO_PKG = S02 + "/assemble/hero_pkg_AS02C"
GWB = S02 + "/back/final/cand/kstarAS02C_a45.gwb"
META = S02 + "/back/final/cand/kstarAS02C_a45_meta.json"
ROWS = S02 + "/back/final/cand/kstarAS02C_a45_rows.npz"
ATTR = S02 + "/assemble/attr_pin/a/s01a_hero_attr_v2_f32.bin"
S03 = REPO + "/Unity/Build/Polish/sample03"
OUT = S03 + "/surface"
SHARED = S03 + "/shared"
SPEC = S03 + "/study/sculpture_spec.json"
NR, NC = 240, 400

# 固定の光（ワールド、光の来る向き）。見本01・02 の _LightDir と同じ
LIGHT = np.array([-0.45, 0.75, -0.5]) / np.linalg.norm([-0.45, 0.75, -0.5])


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def unit(v, eps=1e-12):
    l = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(l, eps)


def load_hero_world():
    """keypose の包みの τ = 0（t*）のワールドの位置（行 × 列 × 3）。Unity の DS27WorldPosition と同じ復号。"""
    import ds33_common as U
    pk = U.K.Pkg(HERO_PKG)
    return np.asarray(pk.world(0.0), np.float64)


def grid_normals(P):
    """格子の 6 つの三角形の和の法線（DS27Normal と同じ）。P は 行 × 列 × 3。"""
    n = np.zeros_like(P)
    a, b, c_, d = P[:-1, :-1], P[1:, :-1], P[:-1, 1:], P[1:, 1:]
    t1 = np.cross(b - a, c_ - a)
    t2 = np.cross(b - c_, d - c_)
    n[:-1, :-1] += t1; n[1:, :-1] += t1; n[:-1, 1:] += t1
    n[:-1, 1:] += t2; n[1:, :-1] += t2; n[1:, 1:] += t2
    return unit(n)


def grid_tris(R, C):
    r, c = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a = (r * C + c).ravel(); b = ((r + 1) * C + c).ravel(); cc = (r * C + c + 1).ravel(); d = ((r + 1) * C + c + 1).ravel()
    return np.stack([np.stack([a, b, cc], 1), np.stack([cc, b, d], 1)], 1).reshape(-1, 3)


def surface_grad(P, f):
    """格子の上のスカラー f の面の勾配（ワールドのベクトル、1/m）。行・列の中心差分と計量で求める。"""
    Pr = np.gradient(P, axis=0); Pc = np.gradient(P, axis=1)
    fr = np.gradient(f, axis=0); fc = np.gradient(f, axis=1)
    E = (Pr * Pr).sum(-1); Fm = (Pr * Pc).sum(-1); G = (Pc * Pc).sum(-1)
    det = np.maximum(E * G - Fm * Fm, 1e-12)
    # ∇f = (G fr − F fc)/det · Pr + (E fc − F fr)/det · Pc
    a = (G * fr - Fm * fc) / det
    b = (E * fc - Fm * fr) / det
    return a[..., None] * Pr + b[..., None] * Pc


# ---------------------------------------------------------------- 見本02 の白の境（シェーダーの _WhiteSrc = 0 と同じ式）
BACKB = (0.42, 0.02, 16.0, 0.0)
CAPF = (1.6, 2.6, 0.9, 1.0)
MINROWH = 0.08


def hash1(x):
    v = np.sin(np.float32(x) * np.float32(127.1) + np.float32(311.7)) * np.float32(43758.5453)
    return v - np.floor(v)


def cap_edge(w):
    P = CAPF[1]
    ws = w + 0.22 * P * np.sin(2 * np.pi * w / (3.7 * P)) + 0.12 * P * np.sin(2 * np.pi * w / (1.9 * P) + 1.1)
    fi = np.floor(ws / P)
    s = ws / P - fi
    x = (s - 0.5) / 0.42
    prof = np.sqrt(np.clip(1.0 - x * x, 0.0, 1.0))
    ln = CAPF[2] * (0.65 + 0.7 * hash1(fi * 1.37 + 2.9))
    return CAPF[0] + ln * prof - 0.35 * CAPF[2]


def white_sd_s02(F, hrel, u, w, hrow, H0):
    """見本02 の白の境からの、おおよその面に沿った符号付きの距離（m、+ が白）。前（u ≥ 0）は u の差、背は高さの差を面の長さに直した目安。"""
    bb = BACKB[0] + BACKB[1] * np.sin(2 * np.pi * w / BACKB[2])
    sd_back = (hrel - bb) * np.maximum(hrow, 0.05) * H0 * 1.3
    sd_cap = cap_edge(w) - u
    sd = np.where(u < 0.0, sd_back, sd_cap)
    sd = np.minimum(sd, (F + 0.25) * 10.0)
    sd = np.minimum(sd, (hrow - MINROWH) * H0)
    return sd


# ---------------------------------------------------------------- 稜（彫りの溝）の式
class GrooveParams:
    """稜の数（S1 から）。lam_* は面の上の周期 m、depth は山と谷の差 m、gfrac は淡い水色の溝の幅／周期。"""

    def __init__(self, H0, spec=None):
        self.H0 = H0
        # S1 3_carved_face：周期 0.035 H（冠のすぐ下）・0.045 H（中ほど）・0.056 H（下の面）、淡い水色の幅／周期 0.244、深さ／周期 ≈ 0.1（0.05〜0.25）
        self.per_top, self.per_mid, self.per_low = 0.035, 0.045, 0.056
        self.gfrac = 0.244
        self.depth_over_period = 0.12     # S1 の深さ／周期 ≈ 0.1（0.05〜0.25）より少し深め（太い稜。回 1 の 0.15 は彫刻の写真より強い縞になった）
        self.bead = 0.18                  # 溝の中の細い玉縁（深さの割合）
        self.pexp = 2.0                   # 稜の断面の超楕円の指数（2 = 楕円）
        self.lod = (0.22, 0.48)           # 子の溝が親から分かれて間に着くまでの段の端数（見本 A と同じ）
        self.fade_len = 2.5               # 白の境から溝が現れきるまでの面の長さ m（冠の下で溝が陰に入って消える）
        self.lod_smooth_m = 1.2           # 本数の段を平らにする半径 m（2.0 では前の面の Y 字が 4 か所で S1 の「線 3〜4 本に 1 つ」より少なかった。1.2 で 6 か所）
        if spec is not None:
            cf = spec["3_carved_face"]
            rel = cf["groove_period_over_H"]["rel"]
            self.per_top, self.per_mid, self.per_low = rel["upper_just_below_crown"], rel["mid_height"], rel["lower_face"]
            self.gfrac = cf["light_blue_width_over_period"]["value"]

    def lam(self, y):
        """高さ y（m、海面 0）での周期 m。0.25 H・0.5 H・0.75 H で S1 の下の面・中ほど・冠の下の値を通る 2 次の曲線を、
        なめらかに飽和させた高さ ts = 0.5 + 0.3 tanh((t − 0.5)/0.3) の上で取る（折れ線にすると、線の座標 q = w／λ の等値線が
        折れ目の高さで曲がった。回 3 の座席から波の方向の左上のぎざぎざ）。シェーダーの AS03Lam と同じ式。"""
        t = np.asarray(y, np.float64) / self.H0
        ts = 0.5 + 0.3 * np.tanh((t - 0.5) / 0.3)
        a, b, c = self.per_low, self.per_mid, self.per_top
        x = (ts - 0.5) / 0.25
        val = b + 0.5 * (c - a) * x + 0.5 * (a - 2 * b + c) * x * x
        return val * self.H0

    def as_dict(self):
        return {k: getattr(self, k) for k in ("H0", "per_top", "per_mid", "per_low", "gfrac", "depth_over_period", "bead", "pexp", "lod", "fade_len", "lod_smooth_m")}


def groove_h(q, Lq, gq, lam, depth, gfrac, bead, pexp, lod=(0.22, 0.48)):
    """稜の高さ h（m、面の法線の向き、山 +depth/2・溝の底 −depth/2）と、近い溝の中心からの距離 d（m）、溝の半幅 gh（m）。
    q：線の座標（段 0 では整数の q に溝）、Lq：本数の段（平らにした値。端数で子の溝が Y 字に分かれる）、gq = |∇q|（1/m）、lam：その場所の周期 m。
    AS03Common.cginc の AS03GrooveH と同じ式。"""
    q = np.asarray(q, np.float64)
    L0 = np.round(Lq)
    fr = Lq - L0
    P0 = np.exp2(-L0)
    x = q / P0
    g = x - np.floor(x)
    km = smooth(lod[0], lod[1], fr)
    s = 0.5 * km
    has = km > 1e-4
    inA = has & (g < s)
    a = np.where(inA, 0.0, np.where(has, s, 0.0))
    b = np.where(inA, s, 1.0)
    igq = 1.0 / np.maximum(gq, 1e-4)
    G = (b - a) * P0 * igq
    d = np.minimum(g - a, b - g) * P0 * igq
    gh = 0.5 * gfrac * lam
    R = 0.5 * G - gh
    Rn = np.maximum(0.5 * lam - gh, 1e-4)
    xg = np.clip(d / np.maximum(gh, 1e-6), 0.0, 1.0)
    hg = -0.5 * depth + bead * depth * (1.0 - xg * xg)
    xr = np.clip((0.5 * G - d) / np.maximum(R, 1e-5), 0.0, 1.0)
    amp = depth * np.clip(R / Rn, 0.0, 1.0)
    hr = -0.5 * depth + amp * np.power(np.clip(1.0 - np.power(xr, pexp), 0.0, 1.0), 1.0 / pexp)
    groove = (d < gh) | (R <= 0.0)
    h = np.where(groove, hg, hr)
    return h, d, gh, km, G
