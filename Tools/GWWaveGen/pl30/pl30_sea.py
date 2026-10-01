# -*- coding: utf-8 -*-
"""仕上げ30：周りの海の式と地形の誘導（設計30 の ds30_sea.py を写して直したもの）。

README
======
- 設計30 の ds30_sea.py と同じ式（主役波と同じ交差うねりと搬送波、静める係数、行ごとの搬送波の振幅 A_c）を、
  仕上げ28 の採用の主役波（K*′ P28R2rec・動き G_p28rec のパッケージ）の値で使う。
- 地形の誘導は、t* の形 F(a, c) を (a, c) の格子（raster、既定 0.25 m）に一度だけ作り、各節点で双線形に読む
  （右の高い波の稜・肩の稜は折れ線からの距離で決めるので、頂点ごとに毎回計算すると重い）。
- 右の高い波：設計30 の稜の表（c → a・高さ）を PCHIP で滑らかにした曲線（折れ線の折れ＝稜線の段と尖りの扇の一因をなくす）。
  断面は設計30 と同じ（後ろ・前で幅の違うガウス）。
- 肩の稜（pl30_shoulder_ridge）：大波の右の端から 60° の交差の稜で右の高い波の頂へ上る（Q16 の波頭の稜の連続）。
  右の高い波とは滑らかな max（smooth_max_m）で合わせる。
- 育つ係数：手前の小波・谷の続きは主役波の頂の高さの比 g(τ)（設計30 と同じ）、右の高い波・肩の稜・船の支えは g_r(τ) = g(τ)·L(τ)
  （名前の付いた美術の誘導 pl30_right_lag）。
- 参照モデルは読まない（F13-1）。numpy・scipy だけ。
"""
import hashlib
import json
import math
import os

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PARAMS = os.path.join(HERE, "pl30_params.json")


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
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (6.0 * x - 15.0) + 10.0)


# ---------------------------------------------------------------- 主役波のパッケージ
class Hero:
    def __init__(self, P):
        self.dir = os.path.join(REPO, P["hero"]["package"])
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
        self.meta_path = os.path.join(REPO, P["hero"]["kstar_meta"])
        meta = load_json(self.meta_path)
        self.e = np.array(meta["frame"]["e_crest"], np.float64)
        self.t = np.array(meta["frame"]["t_travel"], np.float64)
        self.row_c = np.array(meta["rows"]["c_m"], np.float64)
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
        return dict(json=sha256_file(self.jp), pos=self.k["pos_sha256"], pos_lo=self.k["pos_lo_sha256"], kstar_meta=sha256_file(self.meta_path))


# ---------------------------------------------------------------- 海の式（設計30 と同じ）
class Sea:
    def __init__(self, hero, P):
        self.h = hero
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


# ---------------------------------------------------------------- 地形の誘導（t* の形を格子に作る）
def _dist_to_polyline(pa, pc, A, C):
    """点 (A, C) から折れ線 (pa, pc) までの距離・最も近い所の弧長の割合 u・折れ線の左右（+：a の増える側）。"""
    best = np.full(A.shape, np.inf)
    ub = np.zeros(A.shape)
    sg = np.ones(A.shape)
    seg = np.hypot(np.diff(pa), np.diff(pc))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    Ltot = cum[-1]
    for i in range(len(pa) - 1):
        a0, c0, a1, c1 = pa[i], pc[i], pa[i + 1], pc[i + 1]
        da, dc = a1 - a0, c1 - c0
        L2 = da * da + dc * dc
        t = np.clip(((A - a0) * da + (C - c0) * dc) / L2, 0.0, 1.0)
        qa, qc = a0 + t * da, c0 + t * dc
        d = np.hypot(A - qa, C - qc)
        m = d < best
        best = np.where(m, d, best)
        ub = np.where(m, (cum[i] + t * math.sqrt(L2)) / Ltot, ub)
        # 左右：折れ線の向き (da, dc) に対し、法線 (dc, −da) 側（c が増える向きの右手＝a の増える側）を +
        side = (A - qa) * dc - (C - qc) * da
        sg = np.where(m, np.where(side >= 0, 1.0, -1.0), sg)
    return best, ub, sg


class Features:
    def __init__(self, hero, P):
        self.h = hero
        self.P = P
        self.F = P["features"]
        rs = P["raster"]
        self.ra = np.arange(rs["a"][0], rs["a"][1] + 1e-9, rs["step_m"])
        self.rc = np.arange(rs["c"][0], rs["c"][1] + 1e-9, rs["step_m"])
        self.small = self._small_apex()
        self.keel = self._keel()
        self._build_raster()

    # ---- 育つ係数
    def set_growth(self, hmax_knots):
        h = np.asarray(hmax_knots, np.float64)
        g = np.clip((h - h[0]) / (h[-1] - h[0]), 0.0, 1.0)
        if self.P["growth"].get("monotone", True):
            g = np.maximum.accumulate(g)
        g[-1] = 1.0
        self.growth_knots = g
        self.hmax_knots = h
        lag = self.P["growth"].get("right_lag", {})
        if lag.get("on", False):
            Lf = PchipInterpolator(np.array(lag["tau"], np.float64), np.array(lag["L"], np.float64), extrapolate=True)
            L = np.clip(Lf(self.h.knots), 0.0, 1.0)
        else:
            L = np.ones_like(g)
        L[-1] = 1.0
        self.lag_knots = L
        self.growth_right_knots = np.maximum.accumulate(g * L)
        self.growth_right_knots[-1] = 1.0
        # 修正02：肩の稜の上り口を高くした足し分（shoulder_raise）だけの育ちの遅れ pl30_shoulder_lag（pl30_right_lag と同じ形：τ の PCHIP の L_sh(τ)、g_sh = g·L_sh）
        sl = self.P["growth"].get("shoulder_lag", {})
        if sl.get("on", False):
            Lf2 = PchipInterpolator(np.array(sl["tau"], np.float64), np.array(sl["L"], np.float64), extrapolate=True)
            L2 = np.clip(Lf2(self.h.knots), 0.0, 1.0)
        else:
            L2 = L.copy()
        L2[-1] = 1.0
        self.lag_shoulder_knots = L2
        self.growth_shoulder_knots = np.maximum.accumulate(g * L2)
        self.growth_shoulder_knots[-1] = 1.0

    def g(self, tau):
        return float(np.interp(tau, self.h.knots, self.growth_knots))

    def g_r(self, tau):
        return float(np.interp(tau, self.h.knots, self.growth_right_knots))

    def _small_apex(self):
        s = self.F["ds30_small_wave"]
        spec = load_json(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json"))
        cam = np.array(spec["painting_cam"]["position"], np.float64)
        ph = np.array([-6.8, 6.3, -13.0])   # 仮置き M1_ForegroundSwell_Static の頂（設計30 と同じ）
        d = ph - cam
        O = self.h.origin(0.0)
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
        O = self.h.origin(0.0)
        return dict(s=s, xz=pts[:, [0, 2]], y=y, draft=float(w["draft_m"]), a=(pts - O) @ self.h.t, c=(pts - O) @ self.h.e,
                    axis=ax, p_ref=pr, s_min=float(w["s_min"]), s_max=float(w["s_max"]), y0=float(w["y0"]), slope=float(w["slope_dy_ds"]))

    # ---- t* の形を格子に作る（右・肩・小波・谷、船の支えの重みと高さ）
    def _build_raster(self):
        A, C = np.meshgrid(self.ra, self.rc, indexing="ij")
        R = self.F["ds30_right_wave"]
        out = {}
        if R["on"]:
            if R.get("smooth") == "pchip":
                cs = np.linspace(R["crest_c"][0], R["crest_c"][-1], 1201)
                hfun = PchipInterpolator(R["crest_c"], R["crest_h"])
                afun = PchipInterpolator(R["crest_a_c"], R["crest_a"], extrapolate=True)
            else:
                hfun = lambda x: np.interp(x, R["crest_c"], R["crest_h"])  # noqa: E731
                afun = lambda x: np.interp(x, R["crest_a_c"], R["crest_a"])  # noqa: E731
            cc = np.clip(C, R["crest_c"][0], R["crest_c"][-1])
            h = np.clip(hfun(cc), 0.0, None)
            h = np.where((C < R["crest_c"][0]) | (C > R["crest_c"][-1]), 0.0, h)
            acr = afun(cc)
            wb = R["back_width_m"] + (R["back_width_far_m"] - R["back_width_m"]) * smoothstep((C - R["far_from_c"]) / 20.0)
            u = A - acr
            prof = np.where(u < 0, np.exp(-(u / wb) ** 2), np.exp(-(u / R["front_width_m"]) ** 2))
            right = h * prof
            self.right_crest = dict(c=np.linspace(R["crest_c"][0], R["crest_c"][-1], 400))
            self.right_crest["a"] = afun(self.right_crest["c"])
            self.right_crest["h"] = np.clip(hfun(self.right_crest["c"]), 0, None)
            # 修正01：面の座標（材質）のための、右の高い波の稜の連続な座標。形の断面と同じ「a − a_crest(c)」を、稜の傾きで割って
            # 稜に垂直な距離の見当にする（折れ線への最も近い点を使わない＝曲がりの内側で最も近い点が跳ぶ所がない）。u は c だけの関数の稜の弧長。
            cg = np.linspace(R["crest_c"][0] - 40.0, R["crest_c"][-1] + 40.0, 4001)
            ag = afun(np.clip(cg, R["crest_a_c"][0], R["crest_a_c"][-1]))
            dag = np.gradient(ag, cg)
            ug = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(ag), np.diff(cg)))])
            ug -= np.interp(R["crest_c"][0], cg, ug)
            sl = np.interp(C, cg, np.sqrt(1.0 + dag ** 2))
            self.attr_right = dict(q=(A - np.interp(C, cg, ag)) / sl, u=np.interp(C, cg, ug), h=h)
            self.right_u_of_c = (cg, ug)
        else:
            right = np.zeros_like(A)
        SR = self.F.get("pl30_shoulder_ridge", {"on": False})
        if SR.get("on"):
            pa, pc, ph = (np.array(SR[k], np.float64) for k in ("path_a", "path_c", "path_h"))
            seg = np.hypot(np.diff(pa), np.diff(pc))
            uk = np.concatenate([[0.0], np.cumsum(seg)]) / seg.sum()
            uu = np.linspace(0, 1, 201)
            fa, fc, fh = PchipInterpolator(uk, pa), PchipInterpolator(uk, pc), PchipInterpolator(uk, ph)
            qa, qc, qh = fa(uu), fc(uu), np.clip(fh(uu), 0, None)
            d, ub, sg = _dist_to_polyline(qa, qc, A, C)
            hh = np.interp(ub, uu, qh)
            w = np.where(sg < 0, SR["back_width_m"], SR["front_width_m"])
            # 端（u = 0・1）の外は丸い端（距離はそのまま）。u = 1 の外は右の高い波へ任せる（高さは同じ）
            sh = hh * np.exp(-(d / w) ** 2)
            k = float(SR.get("smooth_max_m", 1.0))
            dd = np.abs(right - sh)
            bump = np.where(dd < k, (k - dd) ** 2 / (4 * k), 0.0)
            # 修正01：滑らかな max の足し分 (k − |x − y|)²/4k は、両方が 0 の所でも k/4 = 0.25 m を足していた（格子の全部で海が 0.25 m 上がり、
            # 原画視点の手前の船の船底を隠した。格子の外との境に 0.25 m の段）。両方が k より小さい所では足し分を 0 へ落とす。
            if SR.get("smooth_max_floor", True):
                bump = bump * smoothstep(np.minimum(right, sh) / k)
            out["right_only"] = right.copy()
            right = np.maximum(right, sh) + bump
            # 修正02：上り口を高くする案（raise.path_h。作る部・修正01 の path_h との差だけ）を、別の育ちの遅れ（growth.shoulder_lag）で足す。
            # t* の形は「元の肩の稜 + 足し分」（足し分は上り口の近くだけで、右の高い波との滑らかな max の所には届かない）。
            RS = SR.get("raise", {"on": False})
            if RS.get("on"):
                fh2 = PchipInterpolator(uk, np.array(RS["path_h"], np.float64))
                qh2 = np.clip(fh2(uu), 0, None)
                dsh = np.clip(np.interp(ub, uu, qh2) - hh, 0.0, None) * np.exp(-(d / w) ** 2)
                out["right_lagbase"] = right.copy()
                out["shoulder_raise"] = dsh
                right = right + dsh
                sh = sh + dsh
                qh = np.maximum(qh2, qh)
            self.shoulder_path = dict(a=qa, c=qc, h=qh)
            out["shoulder"] = sh
            # 修正01：肩の稜の連続な座標。両端を直線で延ばした稜の曲線（PCHIP を密に取った折れ線）への符号付きの距離と弧長
            # （端の丸い帽子の外で符号が反転する所をなくす。肩の稜はほぼ直線なので、曲がりの内側の跳びは遠い）。
            Ls = float(np.sum(np.hypot(np.diff(qa), np.diff(qc))))
            ea0 = np.array([qa[0] - qa[1], qc[0] - qc[1]]); ea0 /= np.linalg.norm(ea0)
            ea1 = np.array([qa[-1] - qa[-2], qc[-1] - qc[-2]]); ea1 /= np.linalg.norm(ea1)
            xa = np.concatenate([[qa[0] + 200 * ea0[0]], qa, [qa[-1] + 200 * ea1[0]]])
            xc = np.concatenate([[qc[0] + 200 * ea0[1]], qc, [qc[-1] + 200 * ea1[1]]])
            d2, ub2, sg2 = _dist_to_polyline(xa, xc, A, C)
            L2tot = float(np.sum(np.hypot(np.diff(xa), np.diff(xc))))
            us = ub2 * L2tot - 200.0                                   # 肩の稜の始め（大波の右の端）で 0、合流の所で Ls
            self.attr_shoulder = dict(q=sg2 * d2, u=us, h=np.interp(np.clip(us / Ls, 0, 1), uu, qh), L=Ls)
        S = self.F["ds30_small_wave"]
        if S["on"]:
            da = A - self.small["a"]
            dc = C - self.small["c"]
            ra = np.where(da < 0, da / S["radius_back_m"], da / S["radius_front_m"])
            r = np.sqrt(ra ** 2 + (dc / S["radius_side_m"]) ** 2)
            r0 = S["apex_round"]
            re = np.sqrt(r ** 2 + r0 ** 2) - r0
            re = re / (math.sqrt(1 + r0 ** 2) - r0)
            small = self.small["h"] * np.clip(1.0 - re, 0.0, 1.0) ** S["power"]
        else:
            small = np.zeros_like(A)
        T = self.F["ds30_trough_continue"]
        if T["on"]:
            D = np.interp(C, T["c"], T["depth_m"])
            D = np.where((C < T["c"][0]) | (C > T["c"][-1]), 0.0, D)
            at = np.interp(C, T["a_c"], T["a"])
            trough = -D * np.exp(-((A - at) / T["width_m"]) ** 2)
        else:
            trough = np.zeros_like(A)
        # 船の支えの平面図の重みと、竜骨 + 喫水の高さ
        B = self.F["ds30_boat_support"]
        k = self.keel
        pa_, pc_ = k["a"], k["c"]
        A0, C0, A1, C1 = pa_[0], pc_[0], pa_[-1], pc_[-1]
        L2 = (A1 - A0) ** 2 + (C1 - C0) ** 2
        uq = ((A - A0) * (A1 - A0) + (C - C0) * (C1 - C0)) / L2
        uc = np.clip(uq, 0.0, 1.0)
        qa_, qc_ = A0 + uc * (A1 - A0), C0 + uc * (C1 - C0)
        dk = np.sqrt((A - qa_) ** 2 + (C - qc_) ** 2)
        wd = 1.0 - smoothstep((dk - B["inner_m"]) / (B["outer_m"] - B["inner_m"]))
        ext = np.maximum(-uq, uq - 1.0) * math.sqrt(L2)
        we = 1.0 - smoothstep(np.maximum(ext, 0.0) / B["end_fade_m"])
        boat_w = (wd * we) if B["on"] else np.zeros_like(A)
        boat_y = k["y"][0] + uc * (k["y"][-1] - k["y"][0]) + k["draft"]
        self.r = dict(right=right, small=small, trough=trough, boat_w=boat_w, boat_y=boat_y, **out)
        if hasattr(self, "attr_right"):
            self.r.update(aR_q=self.attr_right["q"], aR_u=self.attr_right["u"], aR_h=self.attr_right["h"])
        if hasattr(self, "attr_shoulder"):
            self.r.update(aS_q=self.attr_shoulder["q"], aS_u=self.attr_shoulder["u"], aS_h=self.attr_shoulder["h"])
        self.boat_dk = dk
        self.r["boat_dk"] = dk

    def sample_clamped(self, a, c, name):
        """格子の値を双線形に読む（格子の外は端の値。面の座標の連続な場のため）。"""
        return self._bilinear(self.r[name], a, c)[0]

    def _bilinear(self, Z, a, c):
        a = np.asarray(a, np.float64)
        c = np.asarray(c, np.float64)
        fa = (a - self.ra[0]) / (self.ra[1] - self.ra[0])
        fc = (c - self.rc[0]) / (self.rc[1] - self.rc[0])
        inside = (fa >= 0) & (fa <= len(self.ra) - 1) & (fc >= 0) & (fc <= len(self.rc) - 1)
        fa = np.clip(fa, 0, len(self.ra) - 1.000001)
        fc = np.clip(fc, 0, len(self.rc) - 1.000001)
        i0 = np.floor(fa).astype(np.int64)
        j0 = np.floor(fc).astype(np.int64)
        u = fa - i0
        v = fc - j0
        z = (Z[i0, j0] * (1 - u) * (1 - v) + Z[i0 + 1, j0] * u * (1 - v) + Z[i0, j0 + 1] * (1 - u) * v + Z[i0 + 1, j0 + 1] * u * v)
        return z, inside

    def sample(self, a, c, name):
        """格子の値を双線形に読む（格子の外は 0）。"""
        Z = self.r[name]
        a = np.asarray(a, np.float64)
        c = np.asarray(c, np.float64)
        fa = (a - self.ra[0]) / (self.ra[1] - self.ra[0])
        fc = (c - self.rc[0]) / (self.rc[1] - self.rc[0])
        inside = (fa >= 0) & (fa <= len(self.ra) - 1) & (fc >= 0) & (fc <= len(self.rc) - 1)
        fa = np.clip(fa, 0, len(self.ra) - 1.000001)
        fc = np.clip(fc, 0, len(self.rc) - 1.000001)
        i0 = np.floor(fa).astype(np.int64)
        j0 = np.floor(fc).astype(np.int64)
        u = fa - i0
        v = fc - j0
        z = (Z[i0, j0] * (1 - u) * (1 - v) + Z[i0 + 1, j0] * u * (1 - v) + Z[i0, j0 + 1] * (1 - u) * v + Z[i0 + 1, j0 + 1] * u * v)
        if name == "boat_y":
            return z
        return np.where(inside, z, 0.0)

    def total(self, a, c, knot):
        """節点 knot の地形の誘導の高さ（船の支えは含まない。帯の後で当て布として当てる）。"""
        g = self.growth_knots[knot]
        gr = self.growth_right_knots[knot]
        if "shoulder_raise" in self.r:
            gs = self.growth_shoulder_knots[knot]
            return gr * self.sample(a, c, "right_lagbase") + gs * self.sample(a, c, "shoulder_raise") \
                + g * (self.sample(a, c, "small") + self.sample(a, c, "trough"))
        return gr * self.sample(a, c, "right") + g * (self.sample(a, c, "small") + self.sample(a, c, "trough"))

    def total_tstar(self, a, c):
        return self.sample(a, c, "right") + self.sample(a, c, "small") + self.sample(a, c, "trough")


def sea_eta(hero, sea, feat, x, z, tau):
    """設計43 の船が読む海面の高さ（主役波のシートの外。船の支えの当て布と遠い海の弱めは含まない）。"""
    O = hero.origin(tau)
    a = (np.asarray(x) - O[0]) * hero.t[0] + (np.asarray(z) - O[2]) * hero.t[2]
    c = (np.asarray(x) - O[0]) * hero.e[0] + (np.asarray(z) - O[2]) * hero.e[2]
    kn = hero.knots
    i = int(np.clip(np.searchsorted(kn, tau) - 1, 0, len(kn) - 2))
    s = (tau - kn[i]) / (kn[i + 1] - kn[i])
    f0 = feat.total(a, c, i)
    f1 = feat.total(a, c, i + 1)
    return sea.eta(x, z, tau) + (1 - s) * f0 + s * f1
