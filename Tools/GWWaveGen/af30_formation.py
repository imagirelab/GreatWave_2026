# -*- coding: utf-8 -*-
"""番号30「形成の動き K0→K*」：rig（af30_rig.json）から形成の全フレームを作り、keypose テクスチャへ書き出し、連続性の検査一式を走らせる。

K*（26修正01、gw_wavegen v2 の kstar_a45）の各行（波峰線に垂直な鉛直の断面、240 行 × 400 列）を、断面の面の中だけで動かす。
    ・頂（列 j_top）：高さ H(u)·y*、横は足跡の平行移動（船の側へ、t* でずれ 0）。
    ・背面の坂（j_B〜j_top）：K* の坂を頂を中心に横 Lb(u) 倍・縦 H(u) 倍（affine）。
    ・前面（j_top〜j_E：唇の上面・唇先・唇の下面・角・内壁・谷）：回転角補間 θ_j = s_j·θ*_j（s_j = κ((u − δ_j)/(1 − δ_j))、
      δ(w) は唇先ほど大きい位相遅れ）。線分の長さは唇部だけ伸び g(u) で短くし、向きは細部 D(u) で平滑した向きから K* の向きへ移す。
      頂から積み上げた曲線を、頂を中心に横 Lf(u) 倍、縦は前の足がちょうど海面に届く倍率 k にする（閉合）。
    ・前傾（横のずれ a += tan(前傾)·y）、唇先の重力の放物線（頂点から t* まで、縦の補正を唇の列へ配る）。
    ・前後の平らな海は外端を動かさず、足までの間隔を伸縮する。
t* = 12.0 s ですべての表が K* の値になり、フレームは K* と一致する。u は形成の進み (t − t0)/(t* − t0)。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/af30_formation.py [--rig R] [--out DIR] [--stage all|preview|keys|check|frames] [--frames 2,4,...]
出力（既定 Unity/Build/ArtFirst/30、Git 対象外の /Unity/Build/ の下）:
    keypose/af30_pos_rgba16.bin・af30_nrm_rg16.bin・af30_keypose.json（Unity の AF30KeyposeWave が読む）
    af30_continuity.json（連続性の検査一式とガードレール）、preview/（断面・唇先の軌跡の図）、frames/（Blender の検査用の頂点 .npy）
numpy と OpenCV だけを使う。座標は Unity のワールド座標（左手系、Y 上、m）。
"""
import argparse
import datetime
import hashlib
import json
import math
import os
import platform
import struct
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402  番号24 の v0（PaintingCam だけを使う。変更しない）

DEFAULT_RIG = os.path.join(HERE, "af30_rig.json")
DEFAULT_OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def clamped_pchip(pts):
    """[x, y] の組を、端の傾き 0 の単調な 3 次補間（Fritsch–Carlson）でつなぐ関数。x の範囲外は端の値。"""
    xs, ys = np.asarray(pts, np.float64).T
    h = np.diff(xs)
    d = np.diff(ys) / h
    m = np.zeros_like(ys)
    for i in range(1, len(xs) - 1):
        if d[i - 1] * d[i] > 0:
            w1 = 2 * h[i] + h[i - 1]
            w2 = h[i] + 2 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])

    def f(x):
        x = np.clip(np.asarray(x, np.float64), xs[0], xs[-1])
        i = np.clip(np.searchsorted(xs, x, side="right") - 1, 0, len(xs) - 2)
        t = (x - xs[i]) / h[i]
        return ((2 * t ** 3 - 3 * t ** 2 + 1) * ys[i] + (t ** 3 - 2 * t ** 2 + t) * h[i] * m[i]
                + (-2 * t ** 3 + 3 * t ** 2) * ys[i + 1] + (t ** 3 - t ** 2) * h[i] * m[i + 1])
    return f


# ---------------------------------------------------------------- K*
class KStar:
    """26修正01 の K*（kstar_a45.gwb・_meta.json・_rows.npz）。"""

    def __init__(self, kdir, want_sha=None):
        self.dir = kdir
        self.gwb = os.path.join(kdir, "kstar_a45.gwb")
        self.gwb_sha = sha256_file(self.gwb)
        if want_sha and self.gwb_sha != want_sha:
            raise SystemExit("K* の .gwb の SHA-256 が rig の記録と違います: " + self.gwb_sha)
        b = open(self.gwb, "rb").read()
        if b[:4] != b"GWW0":
            raise SystemExit("GWW0 ではありません")
        ver, nu, nv, nf = struct.unpack("<4i", b[4:20])
        ntri = struct.unpack("<i", b[28:32])[0]
        n = nu * nv
        o = 32
        self.uv = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
        self.uv2 = np.frombuffer(b, np.float32, n * 2, o).reshape(n, 2); o += n * 8
        self.tris = np.frombuffer(b, np.int32, ntri * 3, o).reshape(-1, 3).copy(); o += ntri * 12
        self.X = np.frombuffer(b, np.float32, n * 3, o).reshape(nv, nu, 3).astype(np.float64)
        self.nu, self.nv = nu, nv
        self.meta = T.load_json(os.path.join(kdir, "kstar_a45_meta.json"))
        fr = self.meta["frame"]
        self.e = np.array(fr["e_crest"], np.float64)
        self.t = np.array(fr["t_travel"], np.float64)
        self.O = np.array(fr["section_origin_world"], np.float64)
        z = np.load(os.path.join(kdir, "kstar_a45_rows.npz"))
        self.A, self.Y, self.c = z["A"].astype(np.float64), z["Y"].astype(np.float64), z["c"].astype(np.float64)
        self.main_row = int(self.meta["rows"]["main_row"])
        Xr = self.world(self.A, self.Y)
        self.recon_max_m = float(np.abs(Xr - self.X).max())
        self.tri_sha = hashlib.sha256(self.tris.astype("<i4").tobytes()).hexdigest()

    def world(self, A, Y, rows=None):
        c = self.c if rows is None else self.c[np.asarray(rows)]
        return (self.O[None, None, :] + c[:, None, None] * self.e[None, None, :]
                + A[..., None] * self.t[None, None, :] + Y[..., None] * np.array([0.0, 1.0, 0.0])[None, None, :])


# ---------------------------------------------------------------- rig
class Rig:
    def __init__(self, rig, ks):
        self.rig = rig
        self.ks = ks
        pc = rig["profile_columns"]
        self.jB, self.jT, self.jP, self.jK, self.jF, self.jE = (pc[k] for k in ("j_B", "j_top", "j_tip", "j_corner", "j_facebot", "j_E"))
        tl = rig["timeline"]
        self.t0, self.ts, self.tend = tl["t0_s"], tl["t_star_s"], tl["end_s"]
        self.fH = clamped_pchip(rig["H"]["table"])
        self.fLb = clamped_pchip(rig["L"]["back_table"])
        self.fLf = clamped_pchip(rig["L"]["front_table"])
        self.fK = clamped_pchip(rig["kappa"]["table"])
        self.fg = clamped_pchip(rig["lip_extension"]["table"])
        self.fD = clamped_pchip(rig["detail"]["table"])
        self.fLean = clamped_pchip(rig["lean"]["table_deg"])
        self.fTr = clamped_pchip(rig["footprint"]["table"])
        self.Dtr = float(rig["footprint"]["translation_m"])
        # 表の t* の値（K* に戻るか）を確かめる
        ends = {"H": self.fH(1.0), "Lb": self.fLb(1.0), "Lf": self.fLf(1.0), "kappa": self.fK(1.0), "g": self.fg(1.0),
                "D": self.fD(1.0), "lean": self.fLean(1.0), "Ftr": self.fTr(1.0)}
        want = {"H": 1, "Lb": 1, "Lf": 1, "kappa": 1, "g": 1, "D": 1, "lean": 0, "Ftr": 1}
        for k_ in ends:
            if abs(float(ends[k_]) - want[k_]) > 1e-12:
                raise SystemExit("rig の表の t* の値が K* と違います: %s = %r" % (k_, ends[k_]))
        A0, Y0 = ks.A, ks.Y
        jT, jE = self.jT, self.jE
        # 前面の線分（K*）
        dA = np.diff(A0[:, jT:jE + 1], axis=1)
        dY = np.diff(Y0[:, jT:jE + 1], axis=1)
        self.Ls = np.hypot(dA, dY)
        raw = np.arctan2(dY, dA)
        th = np.zeros_like(raw)
        for r in range(ks.nv):
            a = raw[r].copy()
            good = self.Ls[r] > 1e-9
            last = 0.0
            for j in range(len(a)):
                if not good[j]:
                    a[j] = last
                last = a[j]
            u_ = np.unwrap(a)
            u_ -= 2 * np.pi * np.round(u_[0] / (2 * np.pi))
            th[r] = u_
        self.th = th
        self.th_end_abs_max = float(np.abs(th[:, -1]).max())
        # 平滑した向き（細部 D(u) の出発点）
        sig = float(rig["detail"]["smooth_sigma_m"])
        ths = np.empty_like(th)
        for r in range(ks.nv):
            s = np.concatenate([[0.0], np.cumsum(self.Ls[r])])
            sm = 0.5 * (s[:-1] + s[1:])
            dd = sm[:, None] - sm[None, :]
            Wt = np.exp(-0.5 * (dd / sig) ** 2) * np.maximum(self.Ls[r][None, :], 1e-6)
            ths[r] = (Wt @ th[r]) / Wt.sum(1)
        self.ths = ths
        # 列の座標 w（主断面の弧長）と位相遅れ δ
        dl = rig["delta"]
        mr = ks.main_row
        s_main = np.concatenate([[0.0], np.cumsum(self.Ls[mr])])
        up = s_main[self.jP - jT]
        lo = s_main[self.jK - jT]
        segmid = 0.5 * (s_main[:-1] + s_main[1:])
        wc = float(dl["w_lower_at_corner"])
        self.w = np.where(segmid <= up, segmid / up,
                          np.where(segmid <= lo, 1.0 - (1.0 - wc) * (segmid - up) / (lo - up),
                                   wc * np.exp(-(segmid - lo) / float(dl["w_face_decay_m"]))))
        self.delta = float(dl["lag_max"]) * self.w ** float(dl["power"])
        # 唇の放物線の補正の重み（頂の列 0 → 唇先 1 → 角 0。頂点の列 jT..jK に対して）
        sv = s_main[:self.jK - jT + 1]
        self.omega = np.where(sv <= up, smoothstep(sv / up), 1.0 - smoothstep((sv - up) / (lo - up)))
        # 背面の坂の幅と、後ろの海の外端
        self.back_w = np.maximum(A0[:, jT] - A0[:, self.jB], 1e-6)
        self.margin = float(rig["L"]["back_foot_margin_m"])
        # 平らな海の間隔の比
        a0 = A0[:, 0]
        self.fb = (A0[:, :self.jB + 1] - a0[:, None]) / np.maximum(A0[:, self.jB] - a0, 1e-9)[:, None]
        a1 = A0[:, -1]
        self.ff = (A0[:, jE:] - A0[:, jE][:, None]) / np.maximum(a1 - A0[:, jE], 1e-9)[:, None]
        # 行の高さと巻き（放物線の対象）
        self.hstar = Y0.max(1)
        self.parab = None
        if rig["lip_parabola"]["enable"]:
            self._prepare_parabola()

    # ---- 時刻 → 進み
    def u_of(self, t):
        return float(np.clip((t - self.t0) / (self.ts - self.t0), 0.0, 1.0))

    def schedule(self, t):
        u = self.u_of(t)
        return {"u": u, "H": float(self.fH(u)), "Lb": float(self.fLb(u)), "Lf": float(self.fLf(u)), "g": float(self.fg(u)),
                "D": float(self.fD(u)), "lean_deg": float(self.fLean(u)), "Ftr": float(self.fTr(u)),
                "tip_s": float(self.fK(np.clip((u - self.delta.max()) / (1 - self.delta.max()), 0, 1)))}

    def natural(self, t, rows=None):
        """放物線の補正の前の断面 (A, Y)。"""
        ks = self.ks
        rows = np.arange(ks.nv) if rows is None else np.asarray(rows)
        jB, jT, jE = self.jB, self.jT, self.jE
        sc = self.schedule(t)
        u = sc["u"]
        A0, Y0 = ks.A[rows], ks.Y[rows]
        A = A0.copy()
        Y = Y0.copy()
        aT = A0[:, jT] - self.Dtr * (1.0 - sc["Ftr"])
        yT = sc["H"] * Y0[:, jT]
        Lb = np.minimum(sc["Lb"], np.maximum((aT - (A0[:, 0] + self.margin)) / self.back_w[rows], 1.0))
        A[:, jB:jT + 1] = aT[:, None] + Lb[:, None] * (A0[:, jB:jT + 1] - A0[:, jT][:, None])
        Y[:, jB:jT + 1] = sc["H"] * Y0[:, jB:jT + 1]
        S = np.maximum(self.fK(np.clip((u - self.delta) / (1.0 - self.delta), 0.0, 1.0)), 1e-4)
        thr = self.ths[rows] + sc["D"] * (self.th[rows] - self.ths[rows])
        ang = S[None, :] * thr
        L = self.Ls[rows] * (1.0 - self.w * (1.0 - sc["g"]))[None, :]
        x = np.concatenate([np.zeros((len(rows), 1)), np.cumsum(L * np.cos(ang), 1)], 1)
        z = np.concatenate([np.zeros((len(rows), 1)), np.cumsum(L * np.sin(ang), 1)], 1)
        zend = z[:, -1]
        ok = zend < -1e-12
        k = np.where(ok, -yT / np.where(ok, zend, -1.0), 0.0)
        A[:, jT:jE + 1] = aT[:, None] + sc["Lf"] * x
        Y[:, jT:jE + 1] = yT[:, None] + k[:, None] * z
        Y[:, jE] = 0.0
        Y[:, jB] = 0.0
        tl = math.tan(math.radians(sc["lean_deg"]))
        A[:, jB:jE + 1] += tl * Y[:, jB:jE + 1]
        # 平らな海：外端を動かさず、足までを K* の間隔の比で並べる
        A[:, :jB + 1] = A0[:, 0][:, None] + self.fb[rows] * (A[:, jB] - A0[:, 0])[:, None]
        Y[:, :jB + 1] = 0.0
        A[:, jE:] = A[:, jE][:, None] + self.ff[rows] * (A0[:, -1] - A[:, jE])[:, None]
        Y[:, jE:] = 0.0
        info = {"k_min": float(k.min()), "k_max": float(k.max()), "front_not_descending_rows": int(((~ok) & (yT > 1e-9)).sum()),
                "back_foot_gap_min_m": float((A[:, jB] - A0[:, 0]).min()), "front_foot_gap_min_m": float((A0[:, -1] - A[:, jE]).min())}
        return A, Y, info

    def _prepare_parabola(self):
        """行ごとの唇先の自然な軌跡から、頂点（最高点）と放物線の係数 G を決める。"""
        pr = self.rig["lip_parabola"]
        ks = self.ks
        n = int(pr["samples"])
        ts = np.linspace(self.t0, self.ts, n)
        tip = np.zeros((n, ks.nv, 2))
        for i, t in enumerate(ts):
            A, Y, _ = self.natural(t)
            tip[i, :, 0] = A[:, self.jP]
            tip[i, :, 1] = Y[:, self.jP]
        self.parab_ts = ts
        self.parab_tip = tip
        ap = tip[:, :, 1].argmax(0)
        a_ap = tip[ap, np.arange(ks.nv), 0]
        y_ap = tip[ap, np.arange(ks.nv), 1]
        a_st, y_st = ks.A[:, self.jP], ks.Y[:, self.jP]
        # 巻き（張り出し）：0.3H の内壁から唇先まで（26修正01 と同じ定義。ここでは唇先 − 内壁の 0.3H の点の a の差で近似）
        H = self.hstar
        over = np.zeros(ks.nv)
        for r in range(ks.nv):
            if H[r] < 0.5:
                continue
            seg = ks.Y[r, self.jK:self.jE + 1]
            aa = ks.A[r, self.jK:self.jE + 1]
            idx = np.nonzero(seg <= 0.3 * H[r])[0]
            if len(idx):
                over[r] = (a_st[r] - aa[idx[0]]) / H[r]
        f0, f1 = pr["fade_overhang_over_H"]
        wrow = smoothstep((over - f0) / max(f1 - f0, 1e-9))
        valid = (ap < n - 2) & (a_st - a_ap > 0.3) & (y_ap - y_st > 0.05)
        # 頂点から t* までの自然な a が単調に増える行だけ
        mono = np.zeros(ks.nv, bool)
        for r in range(ks.nv):
            if valid[r]:
                aa = tip[ap[r]:, r, 0]
                mono[r] = bool(np.all(np.diff(aa) > -1e-9))
        valid &= mono
        G = np.where(valid, (y_ap - y_st) / np.maximum(a_st - a_ap, 1e-9) ** 2, 0.0)
        self.parab = {"t_apex": ts[ap], "a_apex": a_ap, "y_apex": y_ap, "G": G, "w": np.where(valid, wrow, 0.0), "overhang_over_H": over,
                      "valid": valid}
        # 補正量を波峰線方向 c に平滑する行列（隣の行どうしで補正が食い違って、行の間の辺が伸びないように）
        sc_ = float(pr["row_smooth_sigma_m"])
        dc = ks.c[:, None] - ks.c[None, :]
        Kc = np.exp(-0.5 * (dc / sc_) ** 2)
        self.row_smooth = Kc / Kc.sum(1, keepdims=True)

    def parabola_dy(self, A, Y, t):
        """全行の唇先の縦の補正量（行ごとの放物線への差を、波峰線方向 c のガウスで平滑したもの）と、平滑前の値。"""
        p = self.parab
        nv = self.ks.nv
        if p is None or t >= self.ts:
            return np.zeros(nv), np.zeros(nv)
        act = (t > p["t_apex"]) & (p["w"] > 0)
        if not act.any():
            return np.zeros(nv), np.zeros(nv)
        a_n = A[:, self.jP]
        y_n = Y[:, self.jP]
        yt = p["y_apex"] - p["G"] * (a_n - p["a_apex"]) ** 2
        raw = np.where(act, (yt - y_n) * p["w"], 0.0)
        return self.row_smooth @ raw, raw

    def frame_AY(self, t, rows=None):
        rows_all = np.arange(self.ks.nv)
        A, Y, info = self.natural(t, rows_all)
        info["parabola_dy_abs_max_m"] = 0.0
        if self.parab is not None:
            dy, raw = self.parabola_dy(A, Y, t)
            Y[:, self.jT:self.jK + 1] += dy[:, None] * self.omega[None, :]
            info["parabola_dy_abs_max_m"] = float(np.abs(dy).max())
            info["parabola_raw_dy_abs_max_m"] = float(np.abs(raw).max())
        if rows is not None:
            rows = np.asarray(rows)
            A, Y = A[rows], Y[rows]
        return A, Y, info

    def frame(self, t, rows=None):
        A, Y, info = self.frame_AY(t, rows)
        return self.ks.world(A, Y, rows), A, Y, info


# ---------------------------------------------------------------- 幾何の検査
def vertex_normals(X, tris):
    V = X.reshape(-1, 3)
    a, b, c = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(V)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-20), fn


def section_self_intersections(A, Y, j0=0, j1=None):
    """行ごとの断面の折れ線の、隣り合わない線分どうしの交差の数。"""
    j1 = A.shape[1] if j1 is None else j1
    out = np.zeros(A.shape[0], np.int64)
    for r in range(A.shape[0]):
        P = np.stack([A[r, j0:j1], Y[r, j0:j1]], -1)
        p, q = P[:-1], P[1:]
        d = q - p
        # 外接箱の重なりで候補を絞る
        lo = np.minimum(p, q)
        hi = np.maximum(p, q)
        ov = (lo[:, None, 0] <= hi[None, :, 0]) & (lo[None, :, 0] <= hi[:, None, 0]) & (lo[:, None, 1] <= hi[None, :, 1]) & (lo[None, :, 1] <= hi[:, None, 1])
        ov = np.triu(ov, 2)
        ii, jj = np.nonzero(ov)
        if not len(ii):
            continue
        dx, ex = d[ii], d[jj]
        w = p[jj] - p[ii]
        den = dx[:, 0] * ex[:, 1] - dx[:, 1] * ex[:, 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (w[:, 0] * ex[:, 1] - w[:, 1] * ex[:, 0]) / den
            tt = (w[:, 0] * dx[:, 1] - w[:, 1] * dx[:, 0]) / den
        hit = (np.abs(den) > 1e-14) & (s > 1e-9) & (s < 1 - 1e-9) & (tt > 1e-9) & (tt < 1 - 1e-9)
        out[r] = int(hit.sum())
    return out


def octa_encode(n):
    n = n / np.maximum(np.abs(n).sum(-1, keepdims=True), 1e-20)
    x, y, z = n[..., 0], n[..., 1], n[..., 2]
    ox = np.where(z >= 0, x, (1.0 - np.abs(y)) * np.sign(np.where(x == 0, 1.0, x)))
    oy = np.where(z >= 0, y, (1.0 - np.abs(x)) * np.sign(np.where(y == 0, 1.0, y)))
    return np.stack([ox, oy], -1)


def octa_decode(e):
    x, y = e[..., 0], e[..., 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    tt = np.clip(-z, 0.0, None)
    x = x + np.where(x >= 0, -tt, tt)
    y = y + np.where(y >= 0, -tt, tt)
    n = np.stack([x, y, z], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ---------------------------------------------------------------- Catmull-Rom（非一様の節点。Unity の AF30KeyposeWave と同じ式）
def cr_weights(times, t):
    """時刻 t の補間に使う 4 つの key の添字と重み。times は昇順。範囲外は端の key。
    区間 [t1, t2]、s = (t − t1)/(t2 − t1)、Δ = t2 − t1。Hermite の傾き m1 = (p2 − p0)/(t2 − t0)、m2 = (p3 − p1)/(t3 − t1)
    （端では片側：m1 = (p2 − p1)/Δ、m2 = (p2 − p1)/Δ）。"""
    n = len(times)
    if t <= times[0]:
        return (0, 0, 0, 0), (0.0, 1.0, 0.0, 0.0)
    if t >= times[-1]:
        return (n - 1, n - 1, n - 1, n - 1), (0.0, 1.0, 0.0, 0.0)
    i1 = int(np.searchsorted(times, t, side="right") - 1)
    i2 = i1 + 1
    i0 = max(i1 - 1, 0)
    i3 = min(i2 + 1, n - 1)
    t1, t2 = times[i1], times[i2]
    D = t2 - t1
    s = (t - t1) / D
    h00 = 2 * s ** 3 - 3 * s ** 2 + 1
    h10 = s ** 3 - 2 * s ** 2 + s
    h01 = -2 * s ** 3 + 3 * s ** 2
    h11 = s ** 3 - s ** 2
    w = np.zeros(4)
    w[1] += h00
    w[2] += h01
    # m1
    if i0 == i1:
        w[2] += h10
        w[1] -= h10
    else:
        f = h10 * D / (t2 - times[i0])
        w[2] += f
        w[0] -= f
    # m2
    if i3 == i2:
        w[2] += h11
        w[1] -= h11
    else:
        f = h11 * D / (times[i3] - t1)
        w[3] += f
        w[1] -= f
    return (i0, i1, i2, i3), tuple(float(v) for v in w)


# ---------------------------------------------------------------- 本体
class Formation:
    def __init__(self, rig_path, out_dir, log=print):
        self.rig_path = rig_path
        self.rig = T.load_json(rig_path)
        self.out = out_dir
        self.log = log
        kdir = os.path.join(REPO, self.rig["inputs"]["kstar_dir"])
        self.ks = KStar(kdir, self.rig["inputs"]["kstar_gwb_sha256"])
        t0 = time.time()
        self.R = Rig(self.rig, self.ks)
        log("rig 準備 %.1f s（前面の向きの端の最大 %.2e rad、K* の再構成差 %.2e m）" % (time.time() - t0, self.R.th_end_abs_max, self.ks.recon_max_m))
        self.seat = T.load_json(os.path.join(REPO, self.rig["inputs"]["seat"]))

    def X(self, t):
        return self.R.frame(t)[0]

    # ---- key の作成（15 Hz ＋ 適応的な中点）
    def build_keys(self):
        kp = self.rig["keys"]
        base = np.round(np.arange(kp["t_from_s"], kp["t_to_s"] + 1e-9, 1.0 / kp["rate_hz"]), 9)
        times = list(base)
        cache = {}

        def fr(t):
            k = round(t, 9)
            if k not in cache:
                cache[k] = self.X(k).astype(np.float64)
            return cache[k]
        tol = float(kp["adaptive_tol_m"])
        hz = float(kp["adaptive_check_hz"])
        rounds = []
        for rnd in range(int(kp["adaptive_max_rounds"])):
            tk = np.array(times)
            add = []
            worst = 0.0
            for i in range(len(tk) - 1):
                a, b = tk[i], tk[i + 1]
                nchk = max(int(round((b - a) * hz)), 2)
                errmax = 0.0
                for s in np.arange(1, nchk) / nchk:
                    t = a + s * (b - a)
                    idx, w = cr_weights(tk, t)
                    P = sum(w[q] * fr(tk[idx[q]]) for q in range(4) if w[q] != 0.0)
                    e = float(np.linalg.norm(P - self.X(t), axis=-1).max())
                    errmax = max(errmax, e)
                worst = max(worst, errmax)
                if errmax > tol:
                    add.append(round(0.5 * (a + b), 9))
            rounds.append({"round": rnd, "keys": len(times), "worst_interp_err_m": worst, "added": len(add)})
            self.log("key 適応 %d 回目：key %d、補間の差の最大 %.4f m、追加 %d" % (rnd, len(times), worst, len(add)))
            if not add:
                break
            times = sorted(set(times) | set(add))
            # 追加した key の近くの cache は再利用される
            if len(cache) > 600:
                cache.clear()
        self.key_times = np.array(times)
        self.key_rounds = rounds
        return self.key_times

    def export_keypose(self):
        """key の頂点位置（RGBA16 UNORM、外接箱で正規化）と法線（RG16 UNORM、八面体）を書き出す。"""
        ks = self.ks
        kt = self.key_times
        nk = len(kt)
        kdir = os.path.join(self.out, "keypose")
        os.makedirs(kdir, exist_ok=True)
        Xs = np.empty((nk, ks.nv, ks.nu, 3), np.float64)
        Ns = np.empty((nk, ks.nv, ks.nu, 3), np.float64)
        for i, t in enumerate(kt):
            X = self.X(t)
            n, _ = vertex_normals(X, ks.tris)
            Xs[i] = X
            Ns[i] = n.reshape(ks.nv, ks.nu, 3)
        lo = Xs.reshape(-1, 3).min(0) - 0.01
        hi = Xs.reshape(-1, 3).max(0) + 0.01
        size = hi - lo
        q = np.clip(np.round((Xs - lo) / size * 65535.0), 0, 65535).astype("<u2")
        pos = np.concatenate([q, np.full(q.shape[:-1] + (1,), 65535, "<u2")], -1)
        e = octa_encode(Ns)
        qn = np.clip(np.round((e * 0.5 + 0.5) * 65535.0), 0, 65535).astype("<u2")
        ppos = os.path.join(kdir, "af30_pos_rgba16.bin")
        pnrm = os.path.join(kdir, "af30_nrm_rg16.bin")
        pos.tofile(ppos)
        qn.tofile(pnrm)
        deq = lo + q.astype(np.float64) / 65535.0 * size
        qerr = float(np.linalg.norm(deq - Xs, axis=-1).max())
        nd = octa_decode(qn.astype(np.float64) / 65535.0 * 2.0 - 1.0)
        nerr = float(np.degrees(np.arccos(np.clip((nd * Ns).sum(-1), -1, 1))).max())
        its = int(np.nonzero(np.abs(kt - self.R.ts) < 1e-9)[0][0])
        rec = {
            "schema": "GreatWave.AF30.keypose/1", "number": "30",
            "nu": ks.nu, "nv": ks.nv, "layers": nk, "key_times_s": [float(v) for v in kt], "t_star_layer": its,
            "t_star_s": self.R.ts, "end_s": self.R.tend,
            "bbox_min": lo.tolist(), "bbox_size": size.tolist(),
            "position_file": "af30_pos_rgba16.bin", "position_format": "RGBA16 UNORM（TextureFormat.RGBA64）、層ごとに 行 × 列 × 4、リトルエンディアン",
            "normal_file": "af30_nrm_rg16.bin", "normal_format": "RG16 UNORM（TextureFormat.RG32）、八面体符号化 e = n/|n|₁（z<0 は折り返し）、値 = (e·0.5 + 0.5)·65535",
            "position_bytes": os.path.getsize(ppos), "normal_bytes": os.path.getsize(pnrm),
            "position_sha256": sha256_file(ppos), "normal_sha256": sha256_file(pnrm),
            "quantization_max_err_m": qerr, "normal_quantization_max_err_deg": nerr,
            "index_sha256": ks.tri_sha, "kstar_gwb_sha256": ks.gwb_sha, "rig_sha256": sha256_file(self.rig_path),
            "interpolation_ja": "Catmull-Rom（非一様の節点。Hermite の傾き m1 = (p2 − p0)/(t2 − t0)、m2 = (p3 − p1)/(t3 − t1)、端は片側の差）。重みは CPU（AF30KeyposeWave）で計算し、頂点シェーダーは 4 層を読んで重みで足す。範囲外は端の層。",
            "adaptive_rounds": self.key_rounds,
        }
        T.save_json(os.path.join(kdir, "af30_keypose.json"), rec)
        self.keypose = rec
        self.deq_keys = deq
        self.log("keypose：%d 層、位置 %.1f MB・法線 %.1f MB、量子化の差の最大 %.2f mm・%.3f°" % (nk, rec["position_bytes"] / 2 ** 20, rec["normal_bytes"] / 2 ** 20, qerr * 1000, nerr))
        return rec

    def cr_eval(self, t, keys=None):
        keys = self.deq_keys if keys is None else keys
        idx, w = cr_weights(self.key_times, t)
        return sum(w[q] * keys[idx[q]] for q in range(4) if w[q] != 0.0)

    # ---- 連続性の検査一式
    def continuity(self, hz=30.0, si_every=1):
        R, ks = self.R, self.ks
        lim = self.rig["continuity_limits"]
        n = int(round(R.tend * hz)) + 1
        ts = np.arange(n) / hz
        Xp = Xpp = None
        Np = Fp = None
        step_max, step_at = 0.0, None
        d2_max, d2_at = 0.0, None
        ndot_min, ndot_at = 1.0, None
        fflip = 0
        fflip_frames = []
        si_total = 0
        si_frames = []
        crest_prev = None
        crest_nonmono = 0
        crest_drop_max = 0.0
        tip_rows = np.nonzero(R.parab["valid"])[0] if R.parab is not None else np.array([ks.main_row])
        tip_speed_max = 0.0
        tip_speed_at = None
        tipp = None
        ymin = 0.0
        edge_ratio_max = 0.0
        # 行の間の辺の基準（K* と K0 の長い方）
        eK = np.linalg.norm(np.diff(ks.X, axis=0), axis=-1)
        X0 = R.frame(0.0)[0]
        e0 = np.linalg.norm(np.diff(X0, axis=0), axis=-1)
        eref = np.maximum(np.maximum(eK, e0), 1e-3)
        per_frame = []
        par_dev_max = 0.0
        par_dev_main = 0.0
        info_max = {"parabola_dy_abs_max_m": 0.0, "k_max": 0.0, "back_foot_gap_min_m": 1e9, "front_foot_gap_min_m": 1e9, "front_not_descending_rows": 0}
        for i, t in enumerate(ts):
            X, A, Y, info = R.frame(t)
            info_max["parabola_dy_abs_max_m"] = max(info_max["parabola_dy_abs_max_m"], info["parabola_dy_abs_max_m"])
            info_max["k_max"] = max(info_max["k_max"], info["k_max"])
            info_max["back_foot_gap_min_m"] = min(info_max["back_foot_gap_min_m"], info["back_foot_gap_min_m"])
            info_max["front_foot_gap_min_m"] = min(info_max["front_foot_gap_min_m"], info["front_foot_gap_min_m"])
            info_max["front_not_descending_rows"] = max(info_max["front_not_descending_rows"], info["front_not_descending_rows"])
            nrm, fn = vertex_normals(X, ks.tris)
            ymin = min(ymin, float(Y.min()))
            er = float((np.linalg.norm(np.diff(X, axis=0), axis=-1) / eref).max())
            edge_ratio_max = max(edge_ratio_max, er)
            rec = {"t": round(float(t), 4)}
            if Xp is not None:
                d = np.linalg.norm(X - Xp, axis=-1)
                m = float(d.max())
                rec["step_max_m"] = m
                if m > step_max:
                    step_max, step_at = m, [float(t)] + [int(v) for v in np.unravel_index(d.argmax(), d.shape)]
                dots = (nrm * Np).sum(-1)
                dm = float(dots.min())
                rec["normal_dot_min"] = dm
                if dm < ndot_min:
                    ndot_min, ndot_at = dm, [float(t), int(dots.argmin())]
                fa = np.linalg.norm(fn, axis=1)
                fp = np.linalg.norm(Fp, axis=1)
                both = (fa > 1e-10) & (fp > 1e-10)
                fl = int(((fn * Fp).sum(1)[both] < 0).sum())
                if fl:
                    fflip += fl
                    fflip_frames.append([float(t), fl])
                if Xpp is not None:
                    d2 = np.linalg.norm(X - 2 * Xp + Xpp, axis=-1)
                    m2 = float(d2.max())
                    rec["second_diff_max_m"] = m2
                    if m2 > d2_max:
                        d2_max, d2_at = m2, [float(t)] + [int(v) for v in np.unravel_index(d2.argmax(), d2.shape)]
                tip = np.stack([A[tip_rows, R.jP], Y[tip_rows, R.jP]], -1)
                if tipp is not None:
                    sp = float(np.linalg.norm(tip - tipp, axis=-1).max() * hz)
                    if sp > tip_speed_max:
                        tip_speed_max, tip_speed_at = sp, float(t)
            tipp = np.stack([A[tip_rows, R.jP], Y[tip_rows, R.jP]], -1)
            if R.parab is not None and t < R.ts:
                pp = R.parab
                on = pp["valid"] & (t > pp["t_apex"]) & (pp["w"] >= 1.0)
                if on.any():
                    yt = pp["y_apex"] - pp["G"] * (A[:, R.jP] - pp["a_apex"]) ** 2
                    dev = np.abs(Y[:, R.jP] - yt)
                    par_dev_max = max(par_dev_max, float(dev[on].max()))
                    if on[ks.main_row]:
                        par_dev_main = max(par_dev_main, float(dev[ks.main_row]))
            crest = Y.max(1)
            if crest_prev is not None:
                drop = crest_prev - crest
                if (drop > 1e-6).any():
                    crest_nonmono += 1
                    crest_drop_max = max(crest_drop_max, float(drop.max()))
            crest_prev = crest
            if i % si_every == 0:
                si = section_self_intersections(A, Y)
                s_ = int(si.sum())
                rec["section_self_intersections"] = s_
                if s_:
                    si_total += s_
                    si_frames.append([float(t), s_, [int(v) for v in np.nonzero(si)[0][:10]]])
            per_frame.append(rec)
            Xpp, Xp, Np, Fp = Xp, X, nrm, fn
        Xs = R.frame(R.ts)[0]
        tstar_err = float(np.abs(Xs - ks.X).max())
        res = {
            "hz": hz, "frames": n, "t_from_s": 0.0, "t_to_s": float(ts[-1]),
            "index_sha256": ks.tri_sha, "vertex_count": ks.nu * ks.nv, "triangle_count": int(len(ks.tris)),
            "index_constant_ja": "全フレームで同じ三角形の添字（K* の .gwb の添字をそのまま使い、形成では頂点の位置だけを変える）",
            "step_max_m": step_max, "step_max_at_t_row_col": step_at, "step_limit_m": lim["max_step_m_30hz"],
            "second_diff_max_m": d2_max, "second_diff_at_t_row_col": d2_at, "second_diff_limit_m": lim["max_second_difference_m_30hz"],
            "normal_dot_min": ndot_min, "normal_dot_min_at": ndot_at, "face_flips": fflip, "face_flip_frames": fflip_frames[:20],
            "section_self_intersections_total": si_total, "section_self_intersection_frames": si_frames[:20], "si_every_frames": si_every,
            "tstar_vs_kstar_max_m": tstar_err, "tstar_limit_m": lim["tstar_vs_kstar_max_m"],
            "crest_height_nonmonotone_frames": crest_nonmono, "crest_height_drop_max_m": crest_drop_max,
            "lip_tip_speed_max_mps": tip_speed_max, "lip_tip_speed_at_t": tip_speed_at, "lip_tip_rows": int(len(tip_rows)), "lip_speed_limit_mps": lim["lip_speed_max_mps"],
            "lip_parabola_deviation_max_m_rows_full_weight": par_dev_max, "lip_parabola_deviation_main_row_m": par_dev_main,
            "lip_parabola_ja": "唇先（列 j_tip）の軌跡と、その行の放物線 y = y_apex − G·(a − a_apex)² の縦の差（頂点の後、t* まで）。補正を波峰線方向に平滑したぶんの差（放物線の重み 1 の行）。",
            "y_min_m": ymin, "edge_stretch_ratio_max": edge_ratio_max, "edge_stretch_limit": lim["edge_stretch_max"],
            "rig_info": info_max,
        }
        res["pass"] = {
            "index_constant": True,
            "step": step_max < lim["max_step_m_30hz"],
            "second_diff": d2_max <= lim["max_second_difference_m_30hz"],
            "normal_dot": ndot_min > lim["normal_dot_min"],
            "face_flips": fflip == 0,
            "section_self_intersection": si_total == 0,
            "tstar": tstar_err < lim["tstar_vs_kstar_max_m"],
            "crest_monotone": crest_nonmono == 0,
            "lip_speed": tip_speed_max <= lim["lip_speed_max_mps"],
            "below_sea_none": ymin >= -1e-6,
            "edge_stretch": edge_ratio_max <= lim["edge_stretch_max"],
        }
        res["all_pass"] = bool(all(res["pass"].values()))
        res["per_frame"] = per_frame
        return res


def preview_sections(F, path, rows=None, times=(2, 4, 6, 7, 8, 9, 9.5, 10, 10.5, 11, 11.5, 12)):
    ks, R = F.ks, F.R
    rows = [ks.main_row, 146, 120, 100, 185, 200] if rows is None else rows
    W, Hh = 1920, 1080
    img = np.full((Hh, W, 3), 255, np.uint8)
    cols = 4
    cw, ch = W // cols, (Hh - 40) // 3
    seat = np.array(F.seat["seat"]["eye_world"])
    sa = float((seat - ks.O) @ ks.t)
    palette = [(0, 0, 0), (200, 0, 0), (0, 150, 0), (0, 0, 200), (150, 0, 150), (0, 150, 150)]
    for i, t in enumerate(times):
        X, A, Y, info = R.frame(t, rows)
        ox, oy = (i % cols) * cw, 40 + (i // cols) * ch
        sc = 7.4

        def PP(a, y):
            return (int(ox + cw * 0.45 + a * sc), int(oy + ch - 16 - y * sc))
        for rr, col in zip(range(len(rows)), palette):
            pts = np.array([PP(a, y) for a, y in zip(A[rr], Y[rr])], np.int32)
            cv2.polylines(img, [pts], False, col, 1, cv2.LINE_AA)
            cv2.circle(img, PP(A[rr, R.jP], Y[rr, R.jP]), 3, col, -1)
        cv2.circle(img, PP(sa, seat[1]), 4, (0, 0, 255), -1)
        cv2.putText(img, "t=%.1f s  u=%.2f" % (t, R.u_of(t)), (ox + 6, oy + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.rectangle(img, (ox, oy), (ox + cw - 1, oy + ch - 1), (200, 200, 200), 1)
    cv2.putText(img, "AF30 formation sections (numpy, rows c = %s m; red dot = seat v1)" % ", ".join("%.1f" % ks.c[r] for r in rows),
                (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    T.imwrite(path, img[:, :, ::-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rig", default=DEFAULT_RIG)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--stage", default="all")
    ap.add_argument("--frames", default="0,2,4,6,7,8,9,9.5,10,10.5,11,11.5,11.75,12")
    ap.add_argument("--si-every", type=int, default=1)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t_start = time.time()
    F = Formation(a.rig, a.out)
    st = a.stage
    if st in ("all", "preview"):
        os.makedirs(os.path.join(a.out, "preview"), exist_ok=True)
        preview_sections(F, os.path.join(a.out, "preview", "af30_sections.png"))
    if st in ("all", "keys"):
        F.build_keys()
        F.export_keypose()
    if st in ("all", "check"):
        t1 = time.time()
        res = F.continuity(30.0, a.si_every)
        res["seconds"] = time.time() - t1
        res["generated_utc"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
        res["rig_sha256"] = sha256_file(a.rig)
        res["kstar_gwb_sha256"] = F.ks.gwb_sha
        T.save_json(os.path.join(a.out, "af30_continuity.json"), res)
        print("CONTINUITY", json.dumps({k: v for k, v in res.items() if k != "per_frame"}, ensure_ascii=False)[:3000])
    if st in ("all", "frames"):
        fd = os.path.join(a.out, "frames")
        os.makedirs(fd, exist_ok=True)
        np.save(os.path.join(fd, "tris.npy"), F.ks.tris)
        for t in [float(v) for v in a.frames.split(",")]:
            np.save(os.path.join(fd, "X_%06.3f.npy" % t), F.X(t).astype(np.float32).reshape(-1, 3))
    print("DONE %.1f s" % (time.time() - t_start))


if __name__ == "__main__":
    main()
