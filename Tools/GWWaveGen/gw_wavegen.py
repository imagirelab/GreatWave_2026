# -*- coding: utf-8 -*-
"""gw_wavegen v0（編号24「最初の画面：主役波 v0」）。

原画の包絡輪郭（爪なし）を PaintingCam の光線に沿って鉛直の主断面へ逆投影し、
その断面を波峰線方向へ掃引した固定位相の水面シート（既定 320×200 = 64,000 頂点、UV 付き）を作る。
形成は断面の転角補間 θ = s·θ*（唇は位相遅れ）で、K0（平らな海）→ K*（t* = 12.0 s）。

使い方（リポジトリ根で）:
    設計確認（t* だけ）: py -3.10 Tools/GWWaveGen/gw_wavegen.py --preview
    全フレーム出力:     py -3.10 Tools/GWWaveGen/gw_wavegen.py --export

出力（既定 Unity/Build/ArtFirst/24/wave、Git 対象外の /Unity/Build/ の下）:
    wave_v0.gwb           位相（UV・UV2・三角形）と 30 Hz 全フレームの頂点位置（float32）
    wave_v0_meta.json     頂点数・フレーム対応・主断面・入力の SHA-256
    continuity.json       逐フレームの連続性検査（頂点数・添字・NaN・法線反転・最大変位・断面の自己交差）
    preview/              numpy ラスタライズによる t* の設計確認（Unity 描画ではない）

numpy と OpenCV だけを使う（matplotlib・scipy は使わない）。座標は Unity のワールド座標（左手系、Y 上、m）。
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
import truthlib as T  # noqa: E402

DEFAULT_PARAMS = os.path.join(HERE, "params_v0.json")
DEFAULT_OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "24", "wave")
MAGIC = b"GWW0"
FORMAT_VERSION = 1


# ---------------------------------------------------------------- 補助
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smootherstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


def arclen(P):
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    return np.concatenate([[0.0], np.cumsum(d)])


def resample(P, n):
    """折れ線を弧長一様に n 点へ（両端を含む）。"""
    s = arclen(P)
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], -1)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- カメラ
class PaintingCam:
    """PaintingCam v1（painting_truth.json）。truthlib と同じ規約。"""

    def __init__(self, spec):
        c = spec["painting_cam"]
        self.pos, self.r, self.u, self.f = T.cam_basis(spec)
        self.t = math.tan(math.radians(c["vertical_fov_deg"]) / 2.0)
        self.asp = float(c["aspect"])
        self.W = int(spec["display_frame"]["width"])
        self.H = int(spec["display_frame"]["height"])

    def rays(self, xy):
        """表示 px（画素中心が整数）→ ワールドの光線方向（正規化しない）。"""
        xy = np.asarray(xy, np.float64)
        vx = (xy[:, 0] + 0.5) / self.W
        vy = 1.0 - (xy[:, 1] + 0.5) / self.H
        px = (2.0 * vx - 1.0) * self.t * self.asp
        py = (2.0 * vy - 1.0) * self.t
        return self.f[None, :] + px[:, None] * self.r[None, :] + py[:, None] * self.u[None, :]

    def project(self, P):
        """ワールド → (x, y, 奥行き)。表示 px。"""
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        vx = 0.5 + 0.5 * (cx / cz) / (self.t * self.asp)
        vy = 0.5 + 0.5 * (cy / cz) / self.t
        return np.stack([vx * self.W - 0.5, (1.0 - vy) * self.H - 0.5, cz], -1)


def intersect_plane(origin, dirs, p0, n):
    s = ((p0 - origin) @ n) / (dirs @ n)
    return origin[None, :] + s[:, None] * dirs


# ---------------------------------------------------------------- 主断面
class MainPlane:
    """PaintingCam の水平前方 h に垂直な鉛直面。原点 O は右船の直下（海面 y=0）。"""

    def __init__(self, cam, through):
        up = np.array([0.0, 1.0, 0.0])
        h = cam.f.copy()
        h[1] = 0.0
        self.h = h / np.linalg.norm(h)
        ea = np.cross(up, self.h)
        self.ea = ea / np.linalg.norm(ea)
        self.up = up
        self.O = np.array([through[0], 0.0, through[2]], np.float64)
        self.depth_from_cam = float((self.O - cam.pos) @ self.h)

    def to_plane(self, P):
        d = P - self.O
        return np.stack([d @ self.ea, P[:, 1]], -1)

    def to_world(self, c, a, y):
        """c: (nv,) 波峰線方向の距離、a/y: (nv, nu) 断面内座標 → (nv, nu, 3)。"""
        return (self.O[None, None, :] + c[:, None, None] * self.h[None, None, :]
                + a[..., None] * self.ea[None, None, :] + y[..., None] * self.up[None, None, :])


# ---------------------------------------------------------------- 断面（K* の中央断面）
class Profile:
    def __init__(self, params, spec, cam, plane):
        pp = params["profile"]
        env = T.load_json(T.repo_abs(params["inputs"]["envelope"]))
        segs = {s["id"]: np.array(s["points_display"], np.float64) for s in env["segments"]}
        order = ["78", "130", "131", "132", "72"]
        pts, seg_start = [], {}
        for sid in order:
            P = segs[sid]
            if pts and np.allclose(pts[-1][-1], P[0]):
                P = P[1:]
            seg_start[sid] = sum(len(p) for p in pts)
            pts.append(P)
        disp = np.vstack(pts)
        self.visible_display = disp
        W = intersect_plane(cam.pos, cam.rays(disp), plane.O, plane.h)
        Q = plane.to_plane(W)  # (a, y) m
        sq = arclen(Q)
        sd = arclen(disp)
        # 目印（逆投影した密な折れ線の弧長）
        i_crest = seg_start["132"]
        i_tip = seg_start["72"]
        seg72 = disp[i_tip:]
        upper = np.nonzero(seg72[:, 1] < 0.5 * (seg72[0, 1] + seg72[-1, 1]))[0]
        i_corner = i_tip + int(upper[np.argmin(seg72[upper, 0])])
        self.landmarks_display = {"crest_132_start": disp[i_crest].tolist(), "lip_tip": disp[i_tip].tolist(),
                                  "roof_corner": disp[i_corner].tolist(), "left_edge": disp[0].tolist(), "inner_bottom": disp[-1].tolist()}

        V = resample(Q, pp["visible_samples"])
        # 左端・右端の接線（表示 px で一定距離の点から）
        k0 = int(np.searchsorted(sd, pp["ext_right_tangent_samples_px"]))
        th_left = math.atan2(Q[k0, 1] - Q[0, 1], Q[k0, 0] - Q[0, 0])
        k1 = int(np.searchsorted(sd, sd[-1] - pp["ext_right_tangent_samples_px"]))
        th_right = math.atan2(Q[-1, 1] - Q[k1, 1], Q[-1, 0] - Q[k1, 0])

        # 左の延長：海面（水平）から V[0] まで上る。θ(u) = θL·smoothstep(u) + bump·sin²(πu)。
        # 原画左端の輪郭は右下がりで始まるため、画面外に背後の山を置く。長さを固定し、bump を二分法で決める。
        nxl = pp["ext_left_samples"]
        u = (np.arange(nxl) + 0.5) / nxl
        Lxl = float(pp["ext_left_m"])
        lo, hi = 0.0, math.radians(85.0)
        for _ in range(80):
            mid = 0.5 * (lo + hi)
            g = Lxl * np.sin(th_left * smoothstep(u) + mid * np.sin(math.pi * u) ** 2).mean()
            lo, hi = (mid, hi) if g < V[0, 1] else (lo, mid)
        bump = 0.5 * (lo + hi)
        thx = th_left * smoothstep(u) + bump * np.sin(math.pi * u) ** 2
        if V[0, 1] <= 0 or abs(Lxl * np.sin(thx).mean() - V[0, 1]) > 1e-6:
            raise RuntimeError("左の延長を作れません")
        self.ext_left_bump_deg = math.degrees(bump)
        dl = Lxl / nxl
        segv = np.stack([np.cos(thx), np.sin(thx)], -1) * dl
        ext_l = V[0][None, :] - np.cumsum(segv[::-1], axis=0)[::-1]  # nxl 点、先頭が海面
        ext_l[0, 1] = 0.0

        # 右の延長：V[-1] から海面まで下る。θ(u) = θR·(1 - smoothstep(u))
        nxr = pp["ext_right_samples"]
        u = (np.arange(nxr) + 0.5) / nxr
        thr = th_right * (1.0 - smoothstep(u))
        drop = -np.sin(thr).mean()
        if V[-1, 1] <= 0 or drop <= 0:
            raise RuntimeError("右の延長を作れません")
        Lxr = V[-1, 1] / drop
        dr = Lxr / nxr
        segr = np.stack([np.cos(thr), np.sin(thr)], -1) * dr
        ext_r = V[-1][None, :] + np.cumsum(segr, axis=0)  # nxr 点、末尾が海面（アンカー）
        ext_r[-1, 1] = 0.0

        nfl, nfr = pp["flat_left_samples"], pp["flat_right_samples"]
        fl = ext_l[0][None, :] + np.stack([-np.arange(nfl, 0, -1) * pp["flat_left_m"] / nfl, np.zeros(nfl)], -1)
        fr = ext_r[-1][None, :] + np.stack([np.arange(1, nfr + 1) * pp["flat_right_m"] / nfr, np.zeros(nfr)], -1)
        P = np.vstack([fl, ext_l, V, ext_r, fr])
        self.nu = len(P)
        if self.nu != params["grid"]["nu"]:
            raise RuntimeError("断面点数 %d が grid.nu %d と違います" % (self.nu, params["grid"]["nu"]))
        self.P = P
        self.j_extl = nfl                     # 左の延長の始点（海面）
        self.j_v0 = nfl + nxl                 # 原画輪郭の始点（左端）
        self.j_v1 = self.j_v0 + len(V) - 1    # 原画輪郭の終点（72 の下端）
        self.j_anchor = self.j_v1 + nxr       # 右の延長の終点（海面）＝アンカー
        d = np.diff(P, axis=0)
        self.seglen = np.linalg.norm(d, axis=1)
        self.theta = np.unwrap(np.arctan2(d[:, 1], d[:, 0]))
        self.sigma = arclen(P)
        self.sigma_mid = 0.5 * (self.sigma[:-1] + self.sigma[1:])
        # 目印の弧長（逆投影折れ線上 → 断面の弧長）
        off = self.sigma[self.j_v0]
        scale = (self.sigma[self.j_v1] - off) / sq[-1]
        self.sig_crest = off + sq[i_crest] * scale
        self.sig_tip = off + sq[i_tip] * scale
        self.sig_corner = off + sq[i_corner] * scale
        self.ext_left_len = Lxl
        self.ext_right_len = Lxr
        self.th_left_deg = math.degrees(th_left)
        self.th_right_deg = math.degrees(th_right)
        # 主断面の各点の画面位置（t* の中央断面は原画の包絡へ戻るはず）
        self.visible_dense_plane = Q

    def lip_weight(self, tl):
        s = self.sigma_mid
        up = smoothstep((s - (self.sig_crest - tl["lip_ramp_before_crest_m"])) /
                        (tl["lip_ramp_before_crest_m"] + tl["lip_ramp_after_crest_m"]))
        down = 1.0 - smoothstep((s - self.sig_corner) / tl["lip_ramp_after_corner_m"])
        return up * down


# ---------------------------------------------------------------- 掃引とフレーム
class Sheet:
    """固定位相の水面シート。行 = 波峰線方向の断面（c）、列 = 断面の弧長方向（σ）。

    K*（t*）の各断面は次の順で作る（PaintingCam から見て原画の水域の内側へ入る向きの変形だけを使う）。
      1. 中央断面（原画包絡の逆投影）を出発点にする。
      2. 残す割合 D(c) が 1 未満なら、唇（稜線 → 唇先端 → 天井の角）を引き込む（r(D)）。
         段階1で唇の上側と下側を同じ横位置の中点へ鉛直に寄せて厚みを潰し、段階2で稜線と角を結ぶ弦の中点 Q へ縮める。
      3. D が D1 未満なら、高さだけを海面へ潰す（横位置は変えない。s(D)）。
      4. PaintingCam を中心に相似変形（k = 1 + c/d0）。D=1 の断面は原画の同じ輪郭へ投影される。
      5. カメラ側（c<0）だけ、唇以外を海面の高さへ下げる（下げる向きは水域の内側）。
    形成（K0 → K*）は各断面自身の K* 形状の転角補間 θ = s·θ*_c（唇は位相遅れ）。アンカーは断面の前側の海面点。
    """

    def __init__(self, params, spec, layout):
        self.params = params
        self.spec = spec
        self.cam = PaintingCam(spec)
        boat = [b for b in layout["boats"] if b["name"] == params["main_plane"]["through_boat_name"]][0]
        self.boat_pos = np.array([boat["position"][k] for k in "xyz"], np.float64)
        self.plane = MainPlane(self.cam, self.boat_pos)
        self.prof = Profile(params, spec, self.cam, self.plane)
        g, sw, tl = params["grid"], params["sweep"], params["timeline"]
        self.nu, self.nv = g["nu"], g["nv"]
        nn = sw["rows_near"]
        nf = self.nv - nn - 1
        c_near = sw["c_near_m"] + (0.0 - sw["c_near_m"]) * np.arange(nn) / nn
        c_far = sw["c_far_m"] * np.arange(1, nf + 1) / nf
        self.c = np.concatenate([c_near, [0.0], c_far])
        self.v_main = nn
        # 減衰 D(c)：c ∈ [-plateau_near, plateau_far] で 1、外側で exp(-(Δc/σ)^p)
        pn, pf = sw["plateau_near_m"], sw["plateau_far_m"]
        dn = np.maximum(-self.c - pn, 0.0)
        df = np.maximum(self.c - pf, 0.0)
        self.D = np.where(self.c < 0, np.exp(-(dn / sw["envelope_near_sigma_m"]) ** sw["envelope_near_power"]),
                          np.exp(-(df / sw["envelope_far_sigma_m"]) ** sw["envelope_far_power"]))
        self.D[self.v_main] = 1.0
        d1 = sw["squash_below_D"]
        self.r = smoothstep((self.D - d1) / (1.0 - d1))
        self.s = smoothstep(self.D / d1)
        d0 = self.plane.depth_from_cam
        self.k = 1.0 + self.c / d0
        if (self.k <= 0.05).any():
            raise RuntimeError("カメラ側の断面がカメラに近すぎます")
        self.a_cam = float((self.cam.pos - self.plane.O) @ self.plane.ea)
        self.y_cam = float(self.cam.pos[1])
        self.w_lip = self.prof.lip_weight(tl)
        self.tl = tl
        self._kstar_rows()
        # 位相
        iu, iv = np.meshgrid(np.arange(self.nu - 1), np.arange(self.nv - 1))
        a = (iv * self.nu + iu).ravel()
        b = ((iv + 1) * self.nu + iu).ravel()
        cidx = (iv * self.nu + iu + 1).ravel()
        d = ((iv + 1) * self.nu + iu + 1).ravel()
        # Unity の表面は時計回り＝cross(b-a, c-a) が表。平らな海で上（+Y）が表になる順。
        self.tris = np.stack([np.stack([a, b, cidx], -1), np.stack([cidx, b, d], -1)], 1).reshape(-1, 3).astype(np.int32)
        self.uv = np.stack(np.meshgrid(self.prof.sigma / self.prof.sigma[-1], np.linspace(0.0, 1.0, self.nv)), -1).reshape(-1, 2)
        self._bands()

    def _kstar_rows(self):
        pr = self.prof
        P = pr.P
        # 唇の範囲（稜線 → 唇先端 → 天井の角）の引き込み。原画の水域の内側だけを通る2段階にする。
        #  段階1（r: 1 → 0.5）: 唇の上側（132）と下側（天井）を、同じ横位置の反対側との中点へ鉛直に寄せる（唇の厚みを潰す）。
        #  段階2（r: 0.5 → 0）: 潰した唇（中線）を、稜線と角を結ぶ弦の中点 Q へ縮める（r=0 で 稜線→Q→角 の2線分）。
        ja = int(np.searchsorted(pr.sigma, pr.sig_crest))
        jb = int(np.searchsorted(pr.sigma, pr.sig_corner))
        # 天井の角は「72 の上半分で表示 x が最小の点」。断面へ逆投影して再標本化すると、透視と標本位置のため、
        # 角の直後に a が減る（左へ戻る）短い線分が残ることがある。唇を潰した奥の行では、これが平らな海の中の
        # 小さな折り返しになり、形成の途中で頂点法線が反転する。角を断面の a の局所最小まで進めて折り返しを除く。
        self.corner_index_display = jb
        while jb + 1 < pr.j_v1 and P[jb + 1, 0] < P[jb, 0]:
            jb += 1
        jt = int(np.searchsorted(pr.sigma, pr.sig_tip))
        self.lip_range = (ja, jb)
        Q = 0.5 * (P[ja] + P[jb])
        self.lip_root = Q
        yT = P[:, 1].copy()
        upper = [(k, k + 1) for k in range(ja, jt)]
        lower = [(k, k + 1) for k in range(jt, jb)] + [("cb", "ca")]
        pt = lambda k: P[k] if not isinstance(k, str) else (P[jb] if k == "cb" else P[ja])
        for j in range(ja + 1, jb):
            aj, yj = P[j]
            edges = lower if j <= jt else upper + [("cb", "ca")]
            best = None
            for e0, e1 in edges:
                p0, p1 = pt(e0), pt(e1)
                if (p0[0] - aj) * (p1[0] - aj) > 0 or p0[0] == p1[0]:
                    continue
                t = (aj - p0[0]) / (p1[0] - p0[0])
                yc = p0[1] + t * (p1[1] - p0[1])
                if (j <= jt and yc < yj - 1e-6) or (j > jt and yc > yj + 1e-6):
                    if best is None or abs(yc - yj) < abs(best - yj):
                        best = yc
            if best is not None:
                yT[j] = 0.5 * (yj + best)
        self.lip_mid_y = yT
        # 段階1は厚みの 85% までに止め、上側と下側が重ならないようにする（段階2の縮小でも交わらない）。
        rho1 = float(self.params["sweep"]["lip_collapse_max"]) * np.clip((1.0 - self.r) / 0.5, 0.0, 1.0)[:, None]
        rho2 = np.clip(self.r / 0.5, 0.0, 1.0)[:, None]
        A = np.repeat(P[None, :, 0], self.nv, 0).copy()
        Y = np.repeat(P[None, :, 1], self.nv, 0).copy()
        sl = slice(ja + 1, jb)
        Y[:, sl] = Y[:, sl] + rho1 * (yT[None, sl] - Y[:, sl])
        A[:, sl] = Q[0] + rho2 * (A[:, sl] - Q[0])
        Y[:, sl] = Q[1] + rho2 * (Y[:, sl] - Q[1])
        # 高さを海面へ潰す（横位置は変えない。r=0 の断面は横方向に単調なので、平らにしても折り返さない）
        s = self.s[:, None]
        Y = s * Y
        k = self.k[:, None]
        A = self.a_cam + k * (A - self.a_cam)
        Y = self.y_cam + k * (Y - self.y_cam)
        # カメラ側：唇（引き込み分を除く）以外を海面まで下げる
        drop = np.where(self.c < 0, self.y_cam * (1.0 - self.k), 0.0)[:, None]
        wl = np.concatenate([self.w_lip, [0.0]])
        wv = np.maximum(wl, np.concatenate([[0.0], self.w_lip]))  # 頂点の唇重み
        m = 1.0 - wv[None, :] * self.r[:, None]
        Y = Y - drop * m
        self.kstar_a, self.kstar_y = A, Y
        self.flat_level = Y[:, 0].copy()
        dA, dY = np.diff(A, axis=1), np.diff(Y, axis=1)
        self.seglen = np.hypot(dA, dY)
        raw = np.arctan2(dY, dA)
        # 転角の枝は、中央断面（列方向に unwrap）から外側の行へ、隣の行に最も近い枝を選んで決める。
        # 長さ 0 の線分（唇を Q へ縮めた点どうし）は隣の行の角度を引き継ぐ（形には影響しない）。
        th = np.zeros_like(raw)
        vm = self.v_main
        th[vm] = np.unwrap(raw[vm])
        order = list(range(vm + 1, self.nv)) + list(range(vm - 1, -1, -1))
        for v in order:
            ref = th[v - 1] if v > vm else th[v + 1]
            d = (raw[v] - ref + np.pi) % (2.0 * np.pi) - np.pi
            th[v] = np.where(self.seglen[v] > 1e-9, ref + d, ref)
        self.theta = th
        self.anchor_a = A[:, pr.j_anchor].copy()
        self.anchor_y = Y[:, pr.j_anchor].copy()
        self.h_star = (Y - self.flat_level[:, None]).max(1)

    def _bands(self):
        """仮の平塗り帯の座標。UV2.x：白帯（稜線から唇・天井の角まで）からの弧長距離（中央断面、m）。
        UV2.y：行の帯係数。D(c) に、カメラ側の断面を海面へ下げた割合（1 − k）を掛けて小さくする
        （原画視点で、輪郭から内側へ投影される断面ほど暗い帯になる）。"""
        s = self.prof.sigma
        lo = self.prof.sig_crest - 1.0
        hi = self.prof.sig_corner
        self.band_dist = np.where(s < lo, lo - s, np.where(s > hi, s - hi, 0.0))
        self.band_row = self.D * np.clip(1.0 - 3.0 * np.maximum(1.0 - self.k, 0.0), 0.0, 1.0)

    # ---- 形成率
    def progress(self, t):
        tl = self.tl
        tau = (t - tl["pre_roll_s"]) / tl["formation_s"]
        pb = float(smootherstep(tau))
        lag = tl["lip_phase_lag"]
        pl = float(smootherstep((tau - lag) / (1.0 - lag)))
        return pb, pl

    def frame(self, t, rows=None):
        """時刻 t の頂点位置 (nv, nu, 3) と断面内座標。"""
        pb, pl = self.progress(t)
        return self.pose(pb, pl, rows)

    def pose(self, pb, pl, rows=None):
        pr = self.prof
        rows = np.arange(self.nv) if rows is None else np.asarray(rows)
        S = ((1.0 - self.w_lip)[None, :] * pb + self.w_lip[None, :] * pl)
        ang = S * self.theta[rows]
        L = self.seglen[rows]
        sx, sy = L * np.cos(ang), L * np.sin(ang)
        ja = pr.j_anchor
        nr = len(rows)
        a = np.zeros((nr, self.nu))
        y = np.zeros((nr, self.nu))
        a[:, ja] = self.anchor_a[rows]
        y[:, ja] = self.anchor_y[rows]
        a[:, ja + 1:] = a[:, ja:ja + 1] + np.cumsum(sx[:, ja:], axis=1)
        y[:, ja + 1:] = y[:, ja:ja + 1] + np.cumsum(sy[:, ja:], axis=1)
        rev_x = np.cumsum(sx[:, :ja][:, ::-1], axis=1)[:, ::-1]
        rev_y = np.cumsum(sy[:, :ja][:, ::-1], axis=1)[:, ::-1]
        a[:, :ja] = a[:, ja:ja + 1] - rev_x
        y[:, :ja] = y[:, ja:ja + 1] - rev_y
        # 左の延長の転角を行ごとに β 倍し、左の平らな海を K* と同じ高さへ戻す
        j0, j1 = pr.j_extl, pr.j_v0
        need = y[:, j1] - self.flat_level[rows]
        angx = ang[:, j0:j1]
        Lx = L[:, j0:j1]
        beta = np.ones(nr)
        lim = math.radians(80.0)
        for _ in range(40):
            q = np.clip(beta[:, None] * angx, -lim, lim)
            f = (Lx * np.sin(q)).sum(1) - need
            df = (Lx * np.cos(q) * angx).sum(1)
            ok = np.abs(df) > 1e-12
            step = np.where(ok, f / np.where(ok, df, 1.0), 0.0)
            beta = beta - np.clip(step, -2.0, 2.0)
        q = np.clip(beta[:, None] * angx, -lim, lim)
        exs, eys = Lx * np.cos(q), Lx * np.sin(q)
        rx = np.cumsum(exs[:, ::-1], axis=1)[:, ::-1]
        ry = np.cumsum(eys[:, ::-1], axis=1)[:, ::-1]
        a[:, j0:j1] = a[:, j1:j1 + 1] - rx
        y[:, j0:j1] = y[:, j1:j1 + 1] - ry
        resid = np.abs(y[:, j0] - self.flat_level[rows])
        y[:, j0] = self.flat_level[rows]
        a[:, :j0] = a[:, j0:j0 + 1] - np.cumsum(sx[:, :j0][:, ::-1], axis=1)[:, ::-1]
        y[:, :j0] = y[:, j0:j0 + 1] - np.cumsum(sy[:, :j0][:, ::-1], axis=1)[:, ::-1]
        # 転角補間は巻きがほどけた途中で K* より高くなる。行ごとに高さを K* の最大高さまでに抑える（海面を中心に縦だけ縮める）。
        h = (y - self.flat_level[rows][:, None]).max(1)
        cap = np.where(h > self.h_star[rows], self.h_star[rows] / np.maximum(h, 1e-12), 1.0)
        y = self.flat_level[rows][:, None] + cap[:, None] * (y - self.flat_level[rows][:, None])
        X = self.plane.to_world(self.c[rows], a, y)
        return X, a, y, {"height_cap_min": float(cap.min()), "beta_min": float(beta.min()), "beta_max": float(beta.max()), "left_resid_max_m": float(resid.max())}


# ---------------------------------------------------------------- 検査
def vertex_normals(X, tris):
    V = X.reshape(-1, 3)
    a, b, c = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    fn = np.cross(b - a, c - a)
    n = np.zeros_like(V)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-20), ln[:, 0]


def self_intersections(a, y):
    """断面折れ線の非隣接線分どうしの交差数（行ごと）。"""
    out = []
    for r in range(a.shape[0]):
        P = np.stack([a[r], y[r]], -1)
        p, q = P[:-1], P[1:]
        d = q - p
        n = len(p)
        # 線分 i と j の交差（|i-j|>=2）
        dx = d[:, None, :]
        ex = d[None, :, :]
        w = p[None, :, :] - p[:, None, :]
        den = dx[..., 0] * ex[..., 1] - dx[..., 1] * ex[..., 0]
        with np.errstate(divide="ignore", invalid="ignore"):
            s = (w[..., 0] * ex[..., 1] - w[..., 1] * ex[..., 0]) / den
            t = (w[..., 0] * dx[..., 1] - w[..., 1] * dx[..., 0]) / den
        hit = (np.abs(den) > 1e-12) & (s > 1e-9) & (s < 1 - 1e-9) & (t > 1e-9) & (t < 1 - 1e-9)
        ii, jj = np.nonzero(np.triu(hit, 2))
        out.append(int(len(ii)))
    return out


# ---------------------------------------------------------------- 設計確認（numpy ラスタライズ）
def rasterize_cover(cam, X, tris, ss=2):
    """PaintingCam で三角形を塗った被覆率（1920×1080、ss×ss 超標本化）。Unity 描画ではない。"""
    Pp = cam.project(X.reshape(-1, 3))
    if (Pp[:, 2] <= 0.1).any():
        raise RuntimeError("カメラの後ろに頂点があります")
    W, H = cam.W * ss, cam.H * ss
    xy = (Pp[:, :2] + 0.5) * ss - 0.5
    sh = 4
    ip = np.round(xy * (1 << sh)).astype(np.int32)
    img = np.zeros((H, W), np.uint8)
    polys = ip[tris]
    # fillPoly は複数多角形を偶奇規則で塗るため重なりが抜ける。三角形ごとに塗る。
    for tri in polys:
        cv2.fillConvexPoly(img, tri, 255, lineType=cv2.LINE_8, shift=sh)
    cov = (img > 0).astype(np.float64).reshape(cam.H, ss, cam.W, ss).mean((1, 3))
    return cov, Pp


def sea_horizon_cover(cam, spec):
    """M1 の平らな参照海面（上面 y=-0.07、z ≤ 600）が覆う範囲の近似（画面 y が水平線より下）。"""
    far = np.array([[0.0, -0.07, 600.0]])
    yh = cam.project(far)[0, 1]
    yy = np.arange(cam.H)[:, None] * np.ones((1, cam.W))
    return (yy > yh).astype(np.float64), float(yh)


def preview(sheet, out_dir, name="preview_tstar"):
    sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
    import evaluate as E
    cam = sheet.cam
    X, a, y, info = sheet.frame(sheet.tl["t_star_s"])
    cov, Pp = rasterize_cover(cam, X, sheet.tris)
    seacov, yh = sea_horizon_cover(cam, sheet.spec)
    other = np.maximum(cov, seacov)
    truth = E.Truth()
    reg = {"sky": 1.0 - other, "boat_left": np.zeros_like(cov), "boat_mid": np.zeros_like(cov), "boat_fg": np.zeros_like(cov)}
    m, det, rp = E.evaluate_core(truth, truth.disp_rgb, reg, versions=("envelope",), contour_judged=True)
    os.makedirs(out_dir, exist_ok=True)
    img = truth.disp_rgb.copy()
    img = (img * 0.5 + np.dstack([other * 60, other * 90, other * 140]) * 0.5).astype(np.uint8)
    E.overlay_png(truth, img, det, rp, os.path.join(out_dir, name + "_overlay.png"),
                  "24 gw_wavegen v0 numpy preview at t*=12.0s (not Unity)", ("envelope",))
    res = {}
    for k in ("78", "130", "131", "132", "72", "71"):
        for me in m["items"].get(k, {}).get("measures", []):
            if me.get("version") == "envelope":
                res[k] = {"max": me["value_max_px"], "p95": me["p95_px"], "worst": me.get("worst_display_xy")}
    T.imwrite(os.path.join(out_dir, name + "_cover.png"), (np.dstack([other, cov, cov]) * 255).astype(np.uint8))
    T.save_json(os.path.join(out_dir, name + "_contours.json"), {"note_ja": "numpy ラスタライズの設計確認。Unity 描画ではない。", "contours": res, "pose_info": info, "horizon_y": yh})
    return res, info


# ---------------------------------------------------------------- 出力
def export(sheet, out_dir, log=print):
    tl = sheet.tl
    fps = tl["fps"]
    nfr = tl["frames"]
    tstar_f = int(round(tl["t_star_s"] * fps))
    os.makedirs(out_dir, exist_ok=True)
    N = sheet.nu * sheet.nv
    uv = sheet.uv.astype(np.float32)
    # UV2: x = 白帯からの弧長距離（m）、y = 行の帯係数（唇の列は減衰 D(c)。ほかの列はカメラ側を海面まで下げた量に応じて小さくする）
    lipcol = np.tile(sheet.band_dist <= 0.0, sheet.nv)
    rowcoef = np.where(lipcol, np.repeat(sheet.D, sheet.nu), np.repeat(sheet.band_row, sheet.nu))
    uv2 = np.stack([np.tile(sheet.band_dist, sheet.nv), rowcoef], -1).astype(np.float32)
    tris = sheet.tris.astype(np.int32)
    path = os.path.join(out_dir, "wave_v0.gwb")
    cont = {"frames": [], "limits": sheet.params["continuity_limits"]}
    prevX, prevN = None, None
    h = hashlib.sha256()
    t0 = time.time()
    rows_si = sorted(set([0, 40, 80, 110, sheet.v_main - 10, sheet.v_main, sheet.v_main + 10, sheet.v_main + 30, sheet.nv - 1]))
    Xstar = None
    with open(path, "wb") as fo:
        hdr = MAGIC + struct.pack("<iiiifii", FORMAT_VERSION, sheet.nu, sheet.nv, nfr, float(fps), tstar_f, len(tris))
        fo.write(hdr)
        h.update(hdr)
        for arr in (uv, uv2, tris):
            b = np.ascontiguousarray(arr).tobytes()
            fo.write(b)
            h.update(b)
        for i in range(nfr):
            t = i / fps
            X, a, y, info = sheet.frame(t)
            Xf = X.reshape(-1, 3)
            nan = int(np.count_nonzero(~np.isfinite(Xf)))
            nrm, area = vertex_normals(X, sheet.tris)
            rec = {"i": i, "t": round(t, 6), "nan": nan, "vertex_count": int(Xf.shape[0]), "index_count": int(tris.size)}
            if prevX is not None:
                disp = np.linalg.norm(Xf - prevX, axis=1)
                valid = (area > 1e-12) & (prev_area > 1e-12)
                dots = np.einsum("ij,ij->i", nrm, prevN)
                rec["max_step_m"] = float(disp.max())
                rec["max_step_vertex"] = int(disp.argmax())
                rec["max_step_contour_cols_m"] = float(disp.reshape(sheet.nv, sheet.nu)[:, sheet.prof.j_v0:sheet.prof.j_v1 + 1].max())
                rec["flipped_normals"] = int(np.count_nonzero(valid & (dots < 0.0)))
                rec["degenerate_normals"] = int(np.count_nonzero(~valid))
                rec["min_normal_dot"] = float(dots[valid].min()) if valid.any() else 1.0
            if i % 5 == 0 or i == tstar_f:
                rec["self_intersections_rows"] = dict(zip([str(r) for r in rows_si], self_intersections(a[rows_si], y[rows_si])))
            rec["beta_range"] = [round(info["beta_min"], 5), round(info["beta_max"], 5)]
            rec["left_resid_max_m"] = info["left_resid_max_m"]
            cont["frames"].append(rec)
            b = Xf.astype(np.float32).tobytes()
            fo.write(b)
            h.update(b)
            prevX, prevN, prev_area = Xf, nrm, area
            if i == tstar_f:
                Xstar = Xf.copy()
                a_star, y_star = a, y
            if i % 60 == 0:
                log("  frame %d/%d (%.1fs)" % (i, nfr, time.time() - t0))
    # t* での全行の自己交差
    si_all = self_intersections(a_star, y_star)
    fr = cont["frames"]
    steps = [r["max_step_m"] for r in fr if "max_step_m" in r]
    flips = [r["flipped_normals"] for r in fr if "flipped_normals" in r]
    si = [sum(r["self_intersections_rows"].values()) for r in fr if "self_intersections_rows" in r]
    kstar = sheet.frame(sheet.tl["t_star_s"])[0].reshape(-1, 3)
    summary = {
        "frames": nfr, "fps": fps, "t_star_frame": tstar_f,
        "vertex_count_constant": all(r["vertex_count"] == N for r in fr),
        "index_count_constant": all(r["index_count"] == tris.size for r in fr),
        "nan_total": int(sum(r["nan"] for r in fr)),
        "flipped_normals_total": int(sum(flips)),
        "min_normal_dot": float(min(r["min_normal_dot"] for r in fr if "min_normal_dot" in r)),
        "max_step_m": float(max(steps)), "max_step_frame": int(1 + int(np.argmax(steps))),
        "max_step_contour_cols_m": float(max(r["max_step_contour_cols_m"] for r in fr if "max_step_contour_cols_m" in r)),
        "max_step_note_ja": "max_step_m は全頂点（画面外の左右の平らな海を含む）。max_step_contour_cols_m は原画輪郭に対応する列（j_v0..j_v1）だけの最大。",
        "degenerate_normals_max": int(max(r.get("degenerate_normals", 0) for r in fr)),
        "self_intersections_sampled_total": int(sum(si)),
        "self_intersections_all_rows_tstar": int(sum(si_all)),
        "tstar_vs_Kstar_max_m": float(np.abs(Xstar - kstar).max()),
        "hold_static_after_tstar": bool(max([r.get("max_step_m", 0) for r in fr[tstar_f + 1:]] or [0]) == 0.0),
        "pre_roll_static": bool(max([r.get("max_step_m", 0) for r in fr[1:int(sheet.tl["pre_roll_s"] * fps) + 1]] or [0]) == 0.0),
    }
    cont["summary"] = summary
    T.save_json(os.path.join(out_dir, "continuity.json"), cont)
    return path, h.hexdigest(), summary, uv2


def build_meta(sheet, params_path, gwb_path, gwb_sha, summary):
    pr = sheet.prof
    cam = sheet.cam
    Xs, a, y, info = sheet.frame(sheet.tl["t_star_s"], rows=[sheet.v_main])
    main = Xs[0]
    proj = cam.project(main)
    B = cam.project(sheet.boat_pos[None, :])[0]
    inputs = [params_path, T.SPEC_PATH, T.repo_abs(sheet.params["inputs"]["envelope"]), T.repo_abs(sheet.params["inputs"]["layout"]),
              os.path.join(HERE, "gw_wavegen.py"), os.path.join(REPO, "Tools", "PaintingTruth", "truthlib.py")]
    return {
        "schema": "GreatWave.GWWaveGen.meta/1",
        "generator": "gw_wavegen v0",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "file": os.path.basename(gwb_path), "sha256": gwb_sha, "bytes": os.path.getsize(gwb_path),
        "format_ja": "先頭 32 バイト = 'GWW0' + int32 版, nu, nv, フレーム数, float32 fps, int32 t* フレーム, 三角形数。続いて UV (N×2 float32)、UV2 (N×2 float32)、三角形 (M×3 int32)、各フレームの頂点位置 (N×3 float32、Unity ワールド座標 m)。N = nu×nv、頂点添字 = 行×nu + 列。",
        "nu": sheet.nu, "nv": sheet.nv, "vertex_count": sheet.nu * sheet.nv, "triangle_count": int(len(sheet.tris)),
        "frames": sheet.tl["frames"], "fps": sheet.tl["fps"], "t_star_s": sheet.tl["t_star_s"],
        "t_star_frame": int(round(sheet.tl["t_star_s"] * sheet.tl["fps"])),
        "main_row": sheet.v_main,
        "main_plane": {"origin_world": sheet.plane.O.tolist(), "normal_h": sheet.plane.h.tolist(), "axis_a": sheet.plane.ea.tolist(),
                       "depth_from_paintingcam_m": sheet.plane.depth_from_cam, "through_boat": sheet.boat_pos.tolist(),
                       "boat_display_px": [float(B[0]), float(B[1])]},
        "profile": {"arc_length_m": float(pr.sigma[-1]), "ext_left_m": pr.ext_left_len, "ext_right_m": pr.ext_right_len,
                    "tangent_left_deg": pr.th_left_deg, "tangent_right_deg": pr.th_right_deg,
                    "sigma_crest_m": pr.sig_crest, "sigma_lip_tip_m": pr.sig_tip, "sigma_roof_corner_m": pr.sig_corner,
                    "anchor_index": pr.j_anchor, "visible_index_range": [pr.j_v0, pr.j_v1],
                    "landmarks_display": pr.landmarks_display,
                    "main_row_tstar_world_min": main.min(0).tolist(), "main_row_tstar_world_max": main.max(0).tolist(),
                    "crest_height_m": float(y[0].max()),
                    "lip_tip_world": main[pr.j_v0 + int(round((pr.sig_tip - pr.sigma[pr.j_v0]) / (pr.sigma[pr.j_v1] - pr.sigma[pr.j_v0]) * (pr.j_v1 - pr.j_v0)))].tolist()},
        "sweep": {"c_range_m": [float(sheet.c.min()), float(sheet.c.max())], "D_main": 1.0, "lip_range_index": list(sheet.lip_range),
                  "lip_corner_index_before_refine": sheet.corner_index_display, "lip_root_plane_ay": sheet.lip_root.tolist()},
        "continuity_summary": summary,
        "inputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in inputs},
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--export", action="store_true")
    a = ap.parse_args()
    params = T.load_json(a.params)
    spec = T.load_spec()
    layout = T.load_json(T.repo_abs(params["inputs"]["layout"]))
    t0 = time.time()
    sheet = Sheet(params, spec, layout)
    print("sheet: nu=%d nv=%d arc=%.2fm depth=%.3fm extL=%.2fm extR=%.2fm thL=%.1f thR=%.1f (%.2fs)" % (
        sheet.nu, sheet.nv, sheet.prof.sigma[-1], sheet.plane.depth_from_cam, sheet.prof.ext_left_len,
        sheet.prof.ext_right_len, sheet.prof.th_left_deg, sheet.prof.th_right_deg, time.time() - t0))
    if a.preview or not a.export:
        res, info = preview(sheet, os.path.join(a.out, "preview"))
        print("preview t*:", json.dumps(res, ensure_ascii=False), info)
    if a.export:
        path, sha, summary, _ = export(sheet, a.out)
        meta = build_meta(sheet, os.path.abspath(a.params), path, sha, summary)
        T.save_json(os.path.join(a.out, "wave_v0_meta.json"), meta)
        print("EXPORT_DONE", path, sha, json.dumps(summary, ensure_ascii=False))
    print("total %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
