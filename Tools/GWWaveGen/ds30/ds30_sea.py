# -*- coding: utf-8 -*-
"""設計30：周りの海の式（主役波と同じ交差うねりと搬送波）と、地形の誘導（右の高い波・手前の小波・谷の続き・船の支え）。

README
======
- 主役波のパッケージ（Unity/Build/Design/28R01F/F_final/art_on、DS27 の書式と精度の層）を読み、節点・波の枠・海の成分・行ごとの
  搬送波の振幅 A_c（ds27_sea.npz の Ac_knots）を同じ値で使う。主役波のシートの外の海面の高さは
      η(x, z, τ) = κ_c(τ)·A_c(c, τ)·C(x, z, τ) + κ_s(τ)·S(x, z, τ) + g(τ)·F(a, c)
  C・S は主役波と同じ成分の和 Σ amp·cos(kx·(x − Ox) + kz·(z − Oz) − ω·τ + φ)、(Ox, Oz) は焦点。c = (P − O)·e、a = (P − O(τ))·t。
  F は地形の誘導（ds30_params.json の features、波の枠とともに動く）、g(τ) は主役波の頂の高さの比で育つ係数。
- 設計43 の船は sea_eta(x, z, τ) で読む（主役波のシートの内側では式ではなくシートを読む）。
- 参照モデルは読まない（F13-1）。numpy だけ。
"""
import hashlib
import json
import math
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARAMS = os.path.join(HERE, "ds30_params.json")


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


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smootherstep(x):
    """C2 の 0→1（6x⁵ − 15x⁴ + 10x³）。接続帯の重みに使う（継ぎ目で高さ・傾き・曲がりが主役波と同じ）。"""
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


# ---------------------------------------------------------------- 主役波のパッケージ
class Hero:
    def __init__(self, pkg=None):
        P = load_json(PARAMS)
        self.dir = os.path.join(REPO, pkg or P["hero"]["package"])
        self.jp = os.path.join(self.dir, "ds27_keypose.json")
        k = load_json(self.jp)
        self.k = k
        self.L, self.R, self.C = k["layers"], k["rows"], k["cols"]
        self.bmin = np.array(k["bbox_min"], np.float64)
        self.bsz = np.array(k["bbox_size"], np.float64)
        self.knots = np.array(k["knot_tau"], np.float64)
        self.ft = np.array(k["frame"]["tau"], np.float64)
        self.fo = np.array(k["frame"]["origin"], np.float64)
        self.hi = np.memmap(os.path.join(self.dir, k["pos_file"]), dtype="<u2", mode="r", shape=(self.L, self.R, self.C, 4))
        self.lo = np.memmap(os.path.join(self.dir, k["pos_lo_file"]), dtype="u1", mode="r", shape=(self.L, self.R, self.C, 4))
        meta = load_json(os.path.join(REPO, P["hero"]["kstar_meta"]))
        self.e = np.array(meta["frame"]["e_crest"], np.float64)
        self.t = np.array(meta["frame"]["t_travel"], np.float64)
        sm = k["sea_model"]
        self.focus = np.array(sm["focus_world"], np.float64)
        self.sea_model = sm

    def layer(self, i, fine=True):
        q = self.hi[i, :, :, :3].astype(np.float64)
        if fine:
            q = q + self.lo[i, :, :, :3].astype(np.float64) / 255.0 - 0.5
        return self.bmin + q / 65535.0 * self.bsz

    def origin(self, tau):
        tau = np.asarray(tau, np.float64)
        return np.stack([np.interp(tau, self.ft, self.fo[:, j]) for j in range(3)], -1)

    def sha(self):
        return dict(json=sha256_file(self.jp), pos=self.k["pos_sha256"], pos_lo=self.k["pos_lo_sha256"])


# ---------------------------------------------------------------- 海の式
class Sea:
    def __init__(self, hero):
        self.h = hero
        P = load_json(PARAMS)
        sm = hero.sea_model

        def comp(c):
            return dict(kx=np.array(c["kx"]), kz=np.array(c["kz"]), om=np.array(c["omega"]), amp=np.array(c["amp"]), ph=np.array(c["phase"]))
        self.car = comp(sm["carrier"])
        self.swl = comp(sm["swell"])
        cl = sm["calm"]
        self.calm_s = cl["swell_calm_tau_s"] if cl["ds_swell_calm"] else None
        self.calm_c = cl["sea_calm_painting_tau_s"] if cl["ds_sea_calm_painting"] else None
        z = np.load(os.path.join(hero.dir, "ds27_sea.npz"))
        self.row_c = np.array(z["c"], np.float64)
        self.Ac_knots = np.array(z["Ac_knots"], np.float64)
        assert np.allclose(np.array(z["knot_tau"]), hero.knots)
        self.Ac_taper = float(P["sea"]["Ac_lateral_taper_m"])
        self.sea_npz_sha = sha256_file(os.path.join(hero.dir, "ds27_sea.npz"))

    def calm(self, tau):
        ks = 1.0 if self.calm_s is None else 1.0 - float(smoothstep((tau - self.calm_s[0]) / (self.calm_s[1] - self.calm_s[0])))
        kc = 1.0 if self.calm_c is None else 1.0 - float(smoothstep((tau - self.calm_c[0]) / (self.calm_c[1] - self.calm_c[0])))
        return kc, ks

    def field(self, comp, x, z, tau):
        O = self.h.focus
        X = np.asarray(x, np.float64).reshape(-1) - O[0]
        Z = np.asarray(z, np.float64).reshape(-1) - O[2]
        out = np.empty(X.shape[0])
        c0 = comp["om"] * tau - comp["ph"]
        n = 16384
        for i in range(0, X.shape[0], n):
            ph = X[i:i + n, None] * comp["kx"][None, :] + Z[i:i + n, None] * comp["kz"][None, :] - c0[None, :]
            out[i:i + n] = np.cos(ph) @ comp["amp"]
        return out.reshape(np.shape(x))

    def Ac_at(self, c, tau=None, knot=None):
        """行ごとの搬送波の振幅を c（m）で補う。knot を与えれば節点の表、そうでなければ τ で線形に補う。"""
        if knot is not None:
            row = self.Ac_knots[knot]
        else:
            kn = self.h.knots
            tau = float(np.clip(tau, kn[0], kn[-1]))
            i = int(np.clip(np.searchsorted(kn, tau) - 1, 0, len(kn) - 2))
            s = (tau - kn[i]) / (kn[i + 1] - kn[i])
            row = (1 - s) * self.Ac_knots[i] + s * self.Ac_knots[i + 1]
        c = np.asarray(c, np.float64)
        cc = np.clip(c, self.row_c[0], self.row_c[-1])
        A = np.interp(cc, self.row_c, row)
        d = np.abs(c - cc)
        return A * np.exp(-(d / self.Ac_taper) ** 2)

    def eta(self, x, z, tau, knot=None):
        """周りの海（搬送波 + うねり）。地形の誘導は含まない。"""
        kc, ks = self.calm(tau)
        x = np.asarray(x, np.float64)
        z = np.asarray(z, np.float64)
        c = (x - self.h.focus[0]) * self.h.e[0] + (z - self.h.focus[2]) * self.h.e[2]
        out = np.zeros(np.shape(x))
        if kc > 0:
            out = out + kc * self.Ac_at(c, tau, knot) * self.field(self.car, x, z, tau)
        if ks > 0:
            out = out + ks * self.field(self.swl, x, z, tau)
        return out


# ---------------------------------------------------------------- 地形の誘導
def interp_table(x, xs, ys):
    return np.interp(np.asarray(x, np.float64), np.asarray(xs, np.float64), np.asarray(ys, np.float64))


class Features:
    def __init__(self, hero, params=None):
        self.h = hero
        self.P = params or load_json(PARAMS)
        F = self.P["features"]
        self.F = F
        self.growth_knots = None
        self.small = self._small_apex()
        self.keel = self._keel()

    # 育つ係数 g(τ)：主役波の本体の最も高い点の比（節点ごと、単調）
    def set_growth(self, hmax_knots):
        h = np.asarray(hmax_knots, np.float64)
        g = np.clip((h - h[0]) / (h[-1] - h[0]), 0.0, 1.0)
        if self.P["growth"].get("monotone", True):
            g = np.maximum.accumulate(g)
        g[-1] = 1.0
        self.growth_knots = g
        self.hmax_knots = h

    def g(self, tau):
        return float(np.interp(tau, self.h.knots, self.growth_knots))

    def _small_apex(self):
        s = self.F["ds30_small_wave"]
        spec = load_json(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"))
        cam = np.array(spec["painting_cam"]["position"], np.float64)
        ph = np.array([-6.8, 6.3, -13.0])   # 仮置き M1_ForegroundSwell_Static の頂（Unity/Build/ArtFirst/27/dump/foam_static.bin）
        d = ph - cam
        O = self.h.focus
        a_cam = (cam - O) @ self.h.t
        lam = (s["apex_a"] - a_cam) / (d @ self.h.t)
        p = cam + lam * d
        return dict(world=p, a=float((p - O) @ self.h.t), c=float((p - O) @ self.h.e), h=float(p[1]),
                    ray_from=cam.tolist(), ray_through=ph.tolist(), lam=float(lam))

    def _keel(self):
        seat = load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
        w = seat["water_contact"]
        ax = np.array(w["axis_h"], np.float64)
        pr = np.array(w["p_ref"], np.float64)
        s = np.linspace(w["s_min"], w["s_max"], 11)
        pts = pr[None, :] + s[:, None] * ax[None, :]
        y = w["y0"] + w["slope_dy_ds"] * s
        O = self.h.focus
        return dict(s=s, xz=pts[:, [0, 2]], y=y, draft=float(w["draft_m"]), a=(pts - O) @ self.h.t, c=(pts - O) @ self.h.e,
                    axis=ax, p_ref=pr, s_min=float(w["s_min"]), s_max=float(w["s_max"]), y0=float(w["y0"]), slope=float(w["slope_dy_ds"]))

    def shape(self, a, c):
        """t* の形 F(a, c)（育つ係数を掛ける前）と、内訳。"""
        a = np.asarray(a, np.float64)
        c = np.asarray(c, np.float64)
        out = {}
        # 右の高い波
        R = self.F["ds30_right_wave"]
        if R["on"]:
            h = np.clip(interp_table(c, R["crest_c"], R["crest_h"]), 0.0, None)
            h = np.where((c < R["crest_c"][0]) | (c > R["crest_c"][-1]), 0.0, h)
            acr = interp_table(c, R["crest_a_c"], R["crest_a"])
            wb = R["back_width_m"] + (R["back_width_far_m"] - R["back_width_m"]) * smoothstep((c - R["far_from_c"]) / 20.0)
            u = a - acr
            prof = np.where(u < 0, np.exp(-(u / wb) ** 2), np.exp(-(u / R["front_width_m"]) ** 2))
            out["right"] = h * prof
        else:
            out["right"] = np.zeros_like(a)
        # 手前の小波（富士形）
        S = self.F["ds30_small_wave"]
        if S["on"]:
            da = a - self.small["a"]
            dc = c - self.small["c"]
            ra = np.where(da < 0, da / S["radius_back_m"], da / S["radius_front_m"])
            r = np.sqrt(ra ** 2 + (dc / S["radius_side_m"]) ** 2)
            r0 = S["apex_round"]
            re = np.sqrt(r ** 2 + r0 ** 2) - r0
            re = re / (math.sqrt(1 + r0 ** 2) - r0)
            out["small"] = self.small["h"] * np.clip(1.0 - re, 0.0, 1.0) ** S["power"]
        else:
            out["small"] = np.zeros_like(a)
        # 谷の続き
        T = self.F["ds30_trough_continue"]
        if T["on"]:
            D = interp_table(c, T["c"], T["depth_m"])
            D = np.where((c < T["c"][0]) | (c > T["c"][-1]), 0.0, D)
            at = interp_table(c, T["a_c"], T["a"])
            out["trough"] = -D * np.exp(-((a - at) / T["width_m"]) ** 2)
        else:
            out["trough"] = np.zeros_like(a)
        f = out["right"] + out["small"] + out["trough"]
        # 座席の船の支え（t* の水面 = 竜骨 + 喫水）
        B = self.F["ds30_boat_support"]
        if B["on"]:
            k = self.keel
            pa, pc = k["a"], k["c"]
            A0, C0 = pa[0], pc[0]
            A1, C1 = pa[-1], pc[-1]
            L2 = (A1 - A0) ** 2 + (C1 - C0) ** 2
            u = ((a - A0) * (A1 - A0) + (c - C0) * (C1 - C0)) / L2
            uc = np.clip(u, 0.0, 1.0)
            qa, qc = A0 + uc * (A1 - A0), C0 + uc * (C1 - C0)
            d = np.sqrt((a - qa) ** 2 + (c - qc) ** 2)
            L = math.sqrt(L2)
            wd = 1.0 - smoothstep((d - B["inner_m"]) / (B["outer_m"] - B["inner_m"]))
            ext = np.maximum(-u, u - 1.0) * L
            we = 1.0 - smoothstep(np.maximum(ext, 0.0) / B["end_fade_m"])
            w = wd * we
            yk = k["y"][0] + uc * (k["y"][-1] - k["y"][0]) + k["draft"]
            f = (1.0 - w) * f + w * yk
            out["boat_w"] = w
        out["total"] = f
        return out


def sea_eta(hero, sea, feat, x, z, tau):
    """設計43 の船が読む海面の高さ（主役波のシートの外）。x, z はワールド（m）、τ は物理の時刻。"""
    O = hero.origin(tau)
    a = (np.asarray(x) - O[0]) * hero.t[0] + (np.asarray(z) - O[2]) * hero.t[2]
    c = (np.asarray(x) - O[0]) * hero.e[0] + (np.asarray(z) - O[2]) * hero.e[2]
    return sea.eta(x, z, tau) + feat.g(tau) * feat.shape(a, c)["total"]
