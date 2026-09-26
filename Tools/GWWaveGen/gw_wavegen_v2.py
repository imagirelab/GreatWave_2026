# -*- coding: utf-8 -*-
"""gw_wavegen v2（番号26修正01「唇を波峰方向へ延ばし、波峰全体を巻かせる」、立体解釈 45° のみ）。

番号26 の v1（gw_wavegen_v1.py）と番号24 の v0 は変えずに、主断面・目標・逆畳み込み・投影固定・検査の関数を読み込んで使う。
v1 では唇が主断面の前後 1〜2 m にしかなく（手前の肩は唇を縮めた壁、奥は約 5 m で崖）、船上からは「長い壁の右端に唇」に見えた
（番号26 の限界 3）。v2 は行（波峰線方向の断面）の族を作り直し、波峰の全体に巻き（唇と管）を持たせる。

  行 c の断面 = 主断面 P0 に唇の変形（持ち上げ q、切り詰め m、手前の行だけ爪を除いて唇先を丸める β）を加え、頂の足（海面）を中心に
  s 倍した相似形（唇・管・壁の比率を保つ）を、断面の面内で頂が a = ac に来るように置いたもの（海面の近くだけ縦のずれ dy をなじませる）。
  前後の平らな海の外端は動かさない。すべての行の面は波峰線 e に垂直で平行（固定位相の格子のまま）。
  ・手前の肩（c < 0、原画視点で主断面より手前）：頂は 45° の波峰線 e の上（ac = 0）。s は唇を縮めた壁で原画の許容領域に収まる最大。
    唇は m = 1 のまま収まる最大の q を格子で探し（収まらない行だけ m を下げる）。画面の左端より外は海面へ下げ、唇を縮めてから縦に潰す。
  ・奥（c > 0、原画視点で主断面の後ろ）：主断面を PaintingCam の投影中心のまわりに λ = 1 + c/|c_cam| 倍した「錐」の行（像が主断面と
    同じで主断面に隠れ、唇も管も完全に巻く）。far_full_lip_until_m までは唇をそのまま、far_cone_until_m までは錐のまま唇を切り詰めて
    管を閉じ、その先は唇のない壁を後ろへ下げながら小さくして、縦に潰して海面へ下ろす。
  そのあと逆畳み込み（唇の列は主断面だけで包絡をとる）・投影固定と TPS（手前の行と主断面だけ、主断面以外の唇・内壁・谷は動かさない。
  奥の行は貼り付けた後の主断面から作り直す）・近くの三角形の交差と断面の小さな折り返しの解消を行う。
  主断面では、手前側の波峰線の接線が e（45°）、奥側は錐の向き（PaintingCam の射線、約 95°）になる（折れ目。Step_26_修正01_ja.md）。

使い方（リポジトリ根で）:
    py -3.10 Tools/GWWaveGen/gw_wavegen_v2.py [--params P] [--out DIR] [--explore]
出力（既定 Unity/Build/ArtFirst/26修正01/kstar、Git 対象外の /Unity/Build/ の下）:
    kstar_a45.gwb / .obj / _meta.json / _rows.npz / _uv_layout.json（番号26 と同じ書式・同じ UV の並び）、kstar_summary.json、preview/
numpy と OpenCV だけを使う。座標は Unity のワールド座標（左手系、Y 上、m）。
"""
import argparse
import datetime
import json
import math
import os
import platform
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import gw_wavegen as G0  # noqa: E402  番号24 の v0（変更しない）
import gw_wavegen_v1 as V1  # noqa: E402  番号26 の v1（変更しない）

DEFAULT_PARAMS = os.path.join(HERE, "params_v2_af26r01.json")
DEFAULT_OUT = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar")
smoothstep = V1.smoothstep


# ---------------------------------------------------------------- 行（断面の族）v2
class FamilyV2:
    """行 c の断面 = 主断面 P0 に v1 と同じ唇の変形（厚みを中線へ潰す κ、頂と角を結ぶ直線へ縮める m）を加え、
    頂の足（a = T_a, y = 0）を中心に s 倍した相似形を、頂が a = ac に来るように置いたもの。
    y' = s·y + dy·smoothstep(y / y_b)（dy は錐の行で投影中心のまわりの拡大に合わせる縦のずれ。海面 y = 0 は動かない）。
    前後の平らな海の外端は動かさず、足までを元の間隔の比で並べ直す。端の行は縦だけ Df 倍に潰す。"""

    def __init__(self, fr, prof, tgt, prm_rows, prm_fit):
        self.fr, self.prof, self.tgt = fr, prof, tgt
        self.pf = prm_fit
        nv, nn = prm_rows["nv"], prm_rows["rows_near"]
        nf = nv - nn - 1
        un = np.arange(nn) / nn
        c_near = prm_rows["c_min"] * (1.0 - un) ** prm_rows["near_pow"]
        if "far_segments" in prm_rows:
            # 奥の行は区間ごとの本数で並べる（唇を縮める区間を密にする：隣の行との差を小さくして、行の間の三角形が爪の凹凸を横切らないように）
            segs = prm_rows["far_segments"]
            if sum(n_ for _, n_ in segs) != nf:
                raise ValueError("far_segments の本数の合計が奥の行の数と違います")
            c_far, c0_ = [], 0.0
            for k_, (c1_, n_) in enumerate(segs):
                u_ = np.arange(1, n_ + 1) / n_
                if k_ == 0:
                    u_ = u_ ** prm_rows["far_pow"]
                c_far.append(c0_ + (c1_ - c0_) * u_)
                c0_ = c1_
            c_far = np.concatenate(c_far)
        else:
            uf = np.arange(1, nf + 1) / nf
            c_far = prm_rows["c_max"] * uf ** prm_rows["far_pow"]
        self.c = np.concatenate([c_near, [0.0], c_far])
        self.nv = nv
        self.v_main = nn
        self.near = self.c < 0
        self.far = self.c > 0
        self.s = np.ones(nv)
        self.m = np.ones(nv)
        self.kap = np.zeros(nv)
        self.ac = np.zeros(nv)
        self.dy = np.zeros(nv)
        self.q = np.ones(nv)
        self.Df = np.ones(nv)
        cp = fr.cam.pos
        self.cam_a = float((cp - fr.O0) @ fr.t)
        self.cam_y = float(cp[1])
        self.cam_c = float((cp - fr.O0) @ fr.e)
        # v1 の唇の変形（F, ymid, kap_w）を使うための v1 の行の族（行の値は使わない）
        v1fit = dict(V1_FIT_DEFAULTS)
        v1fit.update({k: v for k, v in prm_fit.items() if k in V1_FIT_DEFAULTS})
        self._v1 = V1.Family(fr, prof, tgt, {"nv": 3, "rows_near": 1, "c_min": -1.0, "c_max": 1.0, "near_pow": 1.0, "far_pow": 1.0}, v1fit)
        self.set_profile(prof.P)

    def set_profile(self, P):
        self.P = P
        self._v1.set_profile(P)
        self.T = P[self.prof.j_top].copy()
        self.yb = self.pf["lower_blend_ratio"] * self.T[1]
        self.P_dc = self.declaw(P)

    def declaw(self, P):
        """唇の下面（唇先〜角）の下向きの出っ張り（原画の爪の包絡）を、下面の点の上側の凸包まで持ち上げた断面（爪を除いた唇の下面）。
        主断面以外の手前の行は、主断面から離れるにつれてこの断面へ移す（主断面の爪の出っ張りを左へずらすと、内側の空域へはみ出すため）。"""
        pr = self.prof
        jp, jk = pr.j_tip, pr.j_corner
        D = P[jp:jk + 1]
        # 上側の凸包（a の昇順に並べた点の上側の鎖）
        order = np.argsort(D[:, 0], kind="stable")
        pts = D[order]
        hull = []
        for p_ in pts:
            while len(hull) >= 2:
                o, a_ = hull[-2], hull[-1]
                if (a_[0] - o[0]) * (p_[1] - o[1]) - (a_[1] - o[1]) * (p_[0] - o[0]) >= 0:
                    hull.pop()
                else:
                    break
            hull.append(p_)
        hull = np.array(hull)
        yh = np.interp(D[:, 0], hull[:, 0], hull[:, 1])
        out = P.copy()
        out[jp:jk + 1, 1] = np.maximum(D[:, 1], yh)
        # 唇先と角の近くは元の形へ戻す（唇先の形と角の位置を保つ）
        sa = V1.arclen(D)
        L = self.pf["declaw_end_taper_m"]
        wt = smoothstep(sa / L) * smoothstep((sa[-1] - sa) / L)
        out[jp:jk + 1, 1] = D[:, 1] + wt * (out[jp:jk + 1, 1] - D[:, 1])
        # 唇先の小さな鉤（原画の唇先の爪）を丸める（列方向の平滑化。唇の内側へ縮むので像ははみ出さない）。
        # 隣の行との差が鉤の太さより大きいと、行の間の帯が唇先で自分に重なるため
        # 凸包へ持ち上げた所と元の下面の境（とくに角の近く）にできる小さな折り返し（向きが 90° より大きく変わる点）を消す
        for _ in range(50):
            seg = out[jp:jk + 1]
            dd = np.diff(seg, axis=0)
            cosv = (dd[1:] * dd[:-1]).sum(1) / np.maximum(np.linalg.norm(dd[1:], axis=1) * np.linalg.norm(dd[:-1], axis=1), 1e-12)
            bad = np.nonzero(cosv < 0.0)[0] + 1 + jp
            if not len(bad):
                break
            for jb in bad:
                lo_, hi_ = max(jb - 2, jp + 1), min(jb + 2, jk - 1)
                for j_ in range(lo_, hi_ + 1):
                    out[j_] = 0.5 * out[j_] + 0.25 * (out[j_ - 1] + out[j_ + 1])
        r1, r2, it = int(self.pf["tip_round_cols"][0]), int(self.pf["tip_round_cols"][1]), int(self.pf["tip_round_iters"])
        lo, hi = max(jp - r1, pr.j_top + 2), min(jp + r2, jk - 2)
        for _ in range(it):
            seg = out[lo - 1:hi + 2].copy()
            out[lo:hi + 1] = 0.5 * seg[1:-1] + 0.25 * (seg[:-2] + seg[2:])
        return out

    def beta(self, idx):
        """行ごとの爪を除く割合（手前の行だけ。主断面から declaw_ramp_m で 0→1）。"""
        cc = self.c[np.atleast_1d(idx)]
        return np.where(cc < 0, smoothstep(-cc / self.pf["declaw_ramp_m"]), 0.0)

    def cone(self, c):
        """錐の行：主断面を PaintingCam の投影中心のまわりに λ = 1 + c/|c_cam| 倍（面 c へ写る。像は主断面と同じ）。"""
        lam = 1.0 + np.asarray(c, float) / abs(self.cam_c)
        ac = self.cam_a + lam * (self.T[0] - self.cam_a)
        dy = self.cam_y * (1.0 - lam)
        return ac, lam, dy

    def lip_weights(self, P):
        """唇の変形の列の重み。w：頂の直後 lift_ramp_cols 列で 0→1、唇（頂〜角）で 1、角から先は 0。
        w2（持ち上げ q 用）：w と同じだが、内壁では角から弧長 lift_wall_ramp_m で 1→0（角を持ち上げた分だけ内壁の上端を伸ばす）。
        rho：唇の縮めの中心を頂 T から角 K へ移す割合（唇先まで 0、唇先から角へ smoothstep で 1）。"""
        pr = self.prof
        nu = pr.nu
        jt, jp, jk = pr.j_top, pr.j_tip, pr.j_corner
        r = int(self.pf["lift_ramp_cols"])
        w = np.zeros(nu)
        w[jt:jk + 1] = 1.0
        w[jt:jt + r] = smoothstep(np.arange(r) / r)
        w2 = w.copy()
        sa = V1.arclen(P)
        L = self.pf["lift_wall_ramp_m"]
        w2[jk:] = 1.0 - smoothstep((sa[jk:] - sa[jk]) / L)
        rho = np.zeros(nu)
        rho[jp:jk + 1] = smoothstep((sa[jp:jk + 1] - sa[jp]) / max(sa[jk] - sa[jp], 1e-9))
        rho[jk:] = 1.0
        return w, w2, rho

    def lip(self, P, kap, m, q=None, beta=None):
        """唇の変形。(n, nu) を返す。
          κ：唇の厚みを中線へ潰す（v1 と同じ。唇が全く収まらない行の最後の手段）。
          m：唇の長さ（1 が主断面の唇）。唇の上面は頂から、下面は角から、それぞれの元の曲線に沿って m の割合だけ残し、
             残した上面の端と下面の端を唇先の近くの列（±cap_cols）で直線につなぐ（唇の先を切り詰める）。
             切り詰めた唇の像は元の唇の像の中に入る（原画の輪郭の爪の凹凸を横切らない）。m = 0 は頂と角を直線で結ぶ唇のない壁。
          q：唇を頂の高さへ向けて縦に縮める（唇先と唇の下面を持ち上げる。内壁の上端は角から lift_wall_ramp_m で元へ戻す）。"""
        f = self._v1
        pr = self.prof
        n = len(kap)
        A = np.repeat(P[None, :, 0], n, 0)
        Y = np.repeat(P[None, :, 1], n, 0)
        jt, jp, jk = pr.j_top, pr.j_tip, pr.j_corner
        sl = slice(jt, jk + 1)
        if beta is not None and (beta > 0).any():
            Pd = self.P_dc if P is self.P else self.declaw(P)
            A = A + beta[:, None] * (Pd[None, :, 0] - P[None, :, 0])
            Y = Y + beta[:, None] * (Pd[None, :, 1] - P[None, :, 1])
        if (kap > 0).any():
            ym = f.ymid if P is self.P else V1.lip_midline(P, jt, jp, jk)
            Y[:, sl] = Y[:, sl] + (kap[:, None] * f.kap_w[None, sl]) * (ym[None, sl] - Y[:, sl])
        tr = np.nonzero(m < 1.0 - 1e-9)[0]
        if len(tr):
            Wm = float(self.pf["trunc_window_m"])
            for r in tr:
                # 唇の上面は頂から m·Lu、下面は角から m·Ld を残し、残した上面の端と下面の端を直線（切り口）でつなぐ。
                # 列は、切り口の前後 trunc_window_m の窓の中だけを新しい道の上へ弧長の順に並べ直し、窓の外の列は動かさない
                # （m = 1 で元と一致。隣の行と m が少し違っても、窓の外は同じ位置、窓の中も少ししか動かない）。
                U = np.stack([A[r, jt:jp + 1], Y[r, jt:jp + 1]], -1)
                D = np.stack([A[r, jp:jk + 1], Y[r, jp:jk + 1]], -1)
                su = V1.arclen(U)
                sd = V1.arclen(D)
                Lu, Ld = su[-1], sd[-1]
                mr = float(np.clip(m[r], 0.0, 1.0))
                cu, cd_ = Lu * mr, (1.0 - mr) * Ld
                uc = np.array([np.interp(cu, su, U[:, 0]), np.interp(cu, su, U[:, 1])])
                dc = np.array([np.interp(cd_, sd, D[:, 0]), np.interp(cd_, sd, D[:, 1])])
                sig = np.concatenate([su, Lu + sd[1:]])
                path0 = np.vstack([U, D[1:]])
                # 新しい道（上面の残り + 切り口 + 下面の残り）とその弧長
                Un = np.vstack([U[su < cu - 1e-9], uc[None, :]])
                Dn = np.vstack([dc[None, :], D[sd > cd_ + 1e-9]])
                path = np.vstack([Un, Dn])
                sp = V1.arclen(path)
                chord = float(np.linalg.norm(dc - uc))
                r0, r1 = cu, Lu + cd_                     # 元の弧長で取り除く区間
                w0 = max(r0 - Wm, 0.0)
                w1 = min(r1 + Wm, sig[-1])
                n0 = w0                                   # 新しい道の弧長での窓の始まり（窓の前は同じ弧長）
                n1 = cu + chord + (w1 - r1)               # 新しい道の弧長での窓の終わり
                g = np.where(sig <= w0, sig, np.where(sig >= w1, sig - (r1 - r0) + chord,
                                                      n0 + (sig - w0) / max(w1 - w0, 1e-9) * (n1 - n0)))
                L = np.stack([np.interp(g, sp, path[:, 0]), np.interp(g, sp, path[:, 1])], -1)
                A[r, jt:jk + 1] = L[:, 0]
                Y[r, jt:jk + 1] = L[:, 1]
        if q is not None and (q < 1).any():
            w2 = self.lip_weights(P)[1]
            qe = 1.0 - (1.0 - q[:, None]) * w2[None, :]
            Ty = P[jt, 1]
            Y = Ty - qe * (Ty - Y)
        return A, Y

    def rows(self, idx, s=None, m=None, kap=None, ac=None, dy=None, Df=None, q=None, P=None):
        pr = self.prof
        idx = np.atleast_1d(idx)
        P = self.P if P is None else P

        def bc(v, d):
            return d[idx] if v is None else np.broadcast_to(v, idx.shape).astype(float)
        s, m, kap, ac, dy, Df, q = bc(s, self.s), bc(m, self.m), bc(kap, self.kap), bc(ac, self.ac), bc(dy, self.dy), bc(Df, self.Df), bc(q, self.q)
        A0, Y0 = self.lip(P, kap, m, q, self.beta(idx))
        Yb0 = P[None, :, 1]
        Ta = P[pr.j_top, 0]
        yb = self.pf["lower_blend_ratio"] * P[pr.j_top, 1]
        A = ac[:, None] + s[:, None] * (A0 - Ta)
        Y = s[:, None] * Y0 + dy[:, None] * smoothstep(Yb0 / yb)
        jb, je = pr.j_B, pr.j_E
        wA = (P[:jb + 1, 0] - P[0, 0]) / max(P[jb, 0] - P[0, 0], 1e-9)
        A[:, :jb + 1] = P[0, 0] + wA[None, :] * (A[:, jb:jb + 1] - P[0, 0])
        Y[:, :jb + 1] = 0.0
        wE = (P[je:, 0] - P[-1, 0]) / min(P[je, 0] - P[-1, 0], -1e-9)
        A[:, je:] = P[-1, 0] + wE[None, :] * (A[:, je:je + 1] - P[-1, 0])
        Y[:, je:] = 0.0
        Y = Y * Df[:, None]
        fl = smoothstep(Df / self.pf["flatten_monotone_below_D"])[:, None]
        if (fl < 1).any():
            Am = A.copy()
            for r in np.nonzero(fl[:, 0] < 1)[0]:
                Am[r, jb:] = V1.monotone_redistribute(A[r, jb:])
            A = Am + fl * (A - Am)
        return A, Y

    def project(self, idx, A, Y):
        X = self.fr.world(self.c[np.atleast_1d(idx)], A, Y)
        pp = self.fr.cam.project(X.reshape(-1, 3)).reshape(X.shape[0], X.shape[1], 3)
        return X, pp

    def sdf(self, idx, A, Y):
        X, pp = self.project(idx, A, Y)
        tg = self.tgt
        mg = self.pf["offframe_clamp_px"]
        valid = (Y > self.pf["check_min_y_m"]) & (pp[..., 2] > 1.0) & (pp[..., 0] >= tg.x0 - mg) & (pp[..., 0] <= tg.x1 + mg)
        s = tg.sample(pp[..., :2].reshape(-1, 2)).reshape(Y.shape)
        return np.where(valid, s, -1e9), pp

    def rowmax(self, idx, cols_from=None, **kw):
        A, Y = self.rows(idx, **kw)
        s, _ = self.sdf(idx, A, Y)
        if cols_from is not None:
            s = s[:, cols_from:]
        return s.max(1)

    def bisect(self, idx, key, lo, hi, want, fixed, iters):
        """行ごとの 1 変数の二分法（v1 と同じ）。want='max' は収まる最大値（収まる／収まらないの境が 1 つの前提）。
        返り値：値と、lo 側（max なら lo、min なら hi）で収まるかどうか。"""
        lo = np.broadcast_to(lo, idx.shape).astype(float).copy()
        hi = np.broadcast_to(hi, idx.shape).astype(float).copy()

        def ok(v):
            kw = dict(fixed)
            kw[key] = v
            return self.rowmax(idx, **kw) <= self.pf["fit_tol_px"]
        if want == "max":
            good_hi = ok(hi)
            good_lo = ok(lo)
            a, b = lo.copy(), hi.copy()
            for _ in range(iters):
                mid = 0.5 * (a + b)
                o = ok(mid)
                a = np.where(o, mid, a)
                b = np.where(o, b, mid)
            return np.where(good_hi, hi, a), good_lo
        good_lo = ok(lo)
        good_hi = ok(hi)
        a, b = lo.copy(), hi.copy()
        for _ in range(iters):
            mid = 0.5 * (a + b)
            o = ok(mid)
            b = np.where(o, mid, b)
            a = np.where(o, a, mid)
        return np.where(good_lo, lo, b), good_hi

    def fit(self):
        pf = self.pf
        it = pf["bisect_iters"]
        c = self.c
        near = np.nonzero(self.near)[0]
        far = np.nonzero(self.far)[0]
        nN = len(near)
        info = {}
        cn = c[near]
        # ---------------- 手前の肩：頂は 45° の波峰線の上（ac = 0）
        acN = np.zeros(nN)
        one, zero = np.ones(nN), np.zeros(nN)
        kmax = np.full(nN, pf["lip_collapse_max"])
        # (1) 高さ：唇を縮めた壁（v1 の手前の肩と同じ κ = κmax、m = 0）で収まる最大の s
        sfit, _ = self.bisect(near, "s", zero, one, "max", {"m": zero, "kap": kmax, "ac": acN, "dy": zero, "Df": one}, it)
        A1, Y1 = self.rows(near, s=sfit, m=zero, kap=kmax, ac=acN, dy=zero, Df=one)
        _, pj1 = self.project(near, A1, Y1)
        inframe = pj1[:, self.prof.j_top, 0] >= self.tgt.x0
        i_edge = int(np.nonzero(inframe)[0][0]) if inframe.any() else nN - 1
        c_edge = cn[i_edge]
        info["near_edge_row_c"] = float(c_edge)
        Dn = np.exp(-(np.maximum(c_edge - pf["offframe_gap_m"] - cn, 0.0) / pf["offframe_decay_m"]) ** 2)
        sN = np.where(cn < c_edge, np.minimum(sfit, np.maximum(sfit[i_edge] * Dn, pf["offframe_s_floor"])), sfit)
        DfOff = np.where(cn < c_edge, np.clip(Dn / max(pf["offframe_s_floor"] / max(sfit[i_edge], 1e-6), 1e-6), 0.0, 1.0), 1.0)
        for i in range(nN - 2, -1, -1):
            if cn[i] < c_edge:
                sN[i] = min(sN[i], sN[i + 1])
        sN = np.minimum(V1.gauss_rows(sN, pf["near_s_smooth_rows"]), sN)
        # (2) 巻き：その高さで、唇を縮めずに（m = 1）収まる最大の q（唇の持ち上げ。1 が主断面と同じ形）を格子で探す。
        #     どの q でも収まらない行は、q ごとに収まる最大の m を二分法で求め、m が最大の組を採る（κ = 0、唇は潰さない）。
        # 唇の当てはめだけは許容を lip_fit_tol_px にする（主断面の残差と爪の 1〜2 px の食い違いで唇が急に縮むのを避ける。
        # 輪郭の頂点はこの後の投影固定で目標の射線上へ貼り付ける）
        tol_saved = pf["fit_tol_px"]
        pf["fit_tol_px"] = pf["lip_fit_tol_px"]
        qgrid = np.linspace(1.0, pf["lift_q_min"], int(pf["lift_q_steps"]))
        jlip = self.prof.j_top + int(pf["lip_check_skip_cols"])   # 頂の近くの列（高さ s で決まる）は唇の当てはめでは見ない
        qN = np.full(nN, np.nan)
        for qv in qgrid:
            okq = self.rowmax(near, cols_from=jlip, s=sN, m=one, kap=zero, ac=acN, dy=zero, Df=one, q=np.full(nN, qv)) <= pf["fit_tol_px"]
            qN = np.where(np.isnan(qN) & okq, qv, qN)
        mN = np.where(np.isnan(qN), 0.0, 1.0)
        need = np.nonzero(np.isnan(qN))[0]
        kapN = np.zeros(nN)
        if len(need):
            # 唇を縮めずに（m = 1、q = 1）収まる高さ s を求め直し、壁で求めた高さからの低下が小さい（near_s_drop_max 以内）なら採る
            # （頂のすぐ前の唇の上面が、画面の上の平らな輪郭へ 1 px ほど出るだけの行が多いため）
            ni = near[need]
            s1, ok1 = self.bisect(ni, "s", np.full(len(ni), 0.3), sN[need], "max", {"m": np.ones(len(ni)), "kap": np.zeros(len(ni)), "ac": acN[need],
                                                                                   "dy": np.zeros(len(ni)), "Df": np.ones(len(ni)), "q": np.ones(len(ni))}, it)
            good = ok1 & (s1 >= sN[need] - pf["near_s_drop_max"])
            sN[need[good]] = s1[good]
            qN[need[good]] = 1.0
            mN[need[good]] = 1.0
            info["near_rows_lowered_for_lip"] = int(good.sum())
            need = need[~good]
        if len(need):
            # m = 1 で収まらない行：m を 1 から格子で下げ、各 m で q を格子で探し、最初に収まった組（m が最大、次に q が最大）を採る。
            # 切り詰めた唇の像は元の唇の像の中に入るが、爪の凹凸と切り口の直線で収まる／収まらないが m について単調とは限らないので、二分法は使わない
            ni = near[need]
            best_m = np.full(len(need), -1.0)
            best_q = np.full(len(need), 1.0)
            for mv in np.linspace(0.975, 0.0, 40):
                todo = best_m < 0
                if not todo.any():
                    break
                for qv in qgrid:
                    todo = best_m < 0
                    if not todo.any():
                        break
                    sub = ni[todo]
                    ok = self.rowmax(sub, cols_from=jlip, s=sN[need][todo], m=np.full(len(sub), mv), kap=np.zeros(len(sub)), ac=acN[need][todo], dy=np.zeros(len(sub)),
                                     Df=np.ones(len(sub)), q=np.full(len(sub), qv)) <= pf["fit_tol_px"]
                    ti = np.nonzero(todo)[0][ok]
                    best_m[ti] = mv
                    best_q[ti] = qv
            qN[need] = best_q
            mN[need] = np.maximum(best_m, 0.0)
            kapN[need[best_m < 0]] = pf["lip_collapse_max"]
        info["near_rows_lifted"] = int(np.count_nonzero(qN < 1 - 1e-9))
        info["near_rows_lip_retracted"] = int(len(need))
        info["near_rows_lip_collapsed"] = int(np.count_nonzero(kapN > 0))
        # 行ごとの揺れを和らげる（平滑化した値で収まらない行は元の値に戻す）
        qs = V1.gauss_rows(qN, pf["near_q_smooth_rows"])
        ms = np.minimum(V1.gauss_rows(mN, pf["near_m_smooth_rows"]), mN)
        oks = self.rowmax(near, cols_from=jlip, s=sN, m=ms, kap=kapN, ac=acN, dy=zero, Df=one, q=qs) <= pf["fit_tol_px"]
        qN = np.where(oks, qs, qN)
        mN = np.where(oks, ms, mN)
        info["near_rows_smoothing_reverted"] = int(np.count_nonzero(~oks))
        pf["fit_tol_px"] = tol_saved
        DfN = np.minimum(smoothstep(sN * self.T[1] / pf["flat_h_m"]), smoothstep(DfOff))
        # 端で縦に潰す行は、先に唇を縮める（潰した唇が海面の上に薄く重ならないように）
        mN = np.minimum(mN, smoothstep((DfN - 0.3) / 0.5))
        info["near_q_min"] = float(qN.min())
        info["near_m_min"] = float(mN.min())
        self.s[near], self.m[near], self.kap[near], self.ac[near], self.dy[near], self.Df[near], self.q[near] = sN, mN, kapN, acN, 0.0, DfN, qN
        # ---------------- 奥：錐（主断面に隠れる）で唇を保ち（c ≤ c_a）、錐のまま唇を縮めて管を閉じ（c_a〜c_b）、その先は唇のない壁を小さくして海面へ（尾）
        cf = c[far]
        nF = len(far)
        c_a, c_b = pf["far_full_lip_until_m"], pf["far_cone_until_m"]
        acC, lamC, dyC = self.cone(cf)
        acB, lamB, dyB = [float(np.asarray(v).ravel()[0]) for v in self.cone(np.array([c_b]))]
        c_end = pf["far_end_m"]
        cone = cf <= c_b
        mF = np.where(cf <= c_a, 1.0, 1.0 - smoothstep((cf - c_a) / max(c_b - c_a, 1e-6)))
        u = np.clip((cf - c_b) / max(c_end - c_b, 1e-6), 0.0, 1.0)
        shrink = 1.0 - pf["far_tail_shrink"] * smoothstep(u)
        # 唇を縮める区間は、縮めた唇が隠れる範囲で高さを錐から下げる（s の最小。下限は far_s_floor）
        sF = np.where(cone, lamC, lamB * shrink)
        dyF = np.where(cone, dyC, dyB * shrink)
        acF = acC - pf["far_tail_extra_slope"] * np.maximum(cf - c_b, 0.0) * smoothstep(u / 0.3)
        DfF = 1.0 - smoothstep((cf - pf["far_flatten_from_m"]) / max(c_end - pf["far_flatten_from_m"], 1e-6))
        kapF = np.zeros(nF)
        ret = np.nonzero((cf > c_a) & cone)[0]
        if len(ret) and pf.get("far_retract_lower", True):
            ri = far[ret]
            nR = len(ri)
            lo = np.minimum(np.full(nR, pf["far_s_floor"]), lamC[ret])
            smin, okhi = self.bisect(ri, "s", lo, lamC[ret], "min", {"m": mF[ret], "kap": np.zeros(nR), "ac": acC[ret], "dy": dyC[ret],
                                                                     "Df": DfF[ret], "q": np.ones(nR)}, it)
            smin = np.where(okhi, smin, lamC[ret])
            smin = np.maximum.accumulate(smin[::-1])[::-1] if False else smin
            sF[ret] = smin
            # 頂の高さは錐の高さに合わせて縦のずれも縮める（頂の射線から下がる）
            dyF[ret] = dyC[ret] * (smin - 1.0) / np.maximum(lamC[ret] - 1.0, 1e-9)
        # 尾の入口の高さを、唇を縮めた区間の終わりにそろえる
        if (~cone).any() and len(ret):
            sB = sF[ret][-1]
            dyB2 = dyF[ret][-1]
            sF = np.where(cone, sF, sB * shrink)
            dyF = np.where(cone, dyF, dyB2 * shrink)
        tail = np.nonzero(~cone)[0]
        if len(tail):
            ti = far[tail]
            nT = len(ti)
            okT = self.rowmax(ti, s=sF[tail], m=np.zeros(nT), kap=np.zeros(nT), ac=acF[tail], dy=dyF[tail], Df=DfF[tail], q=np.ones(nT)) <= pf["fit_tol_px"]
            mF[tail] = 0.0
            kapF[tail] = np.where(okT, 0.0, pf["lip_collapse_max"])
            info["far_tail_rows_lip_collapsed"] = int(np.count_nonzero(~okT))
        self.s[far], self.m[far], self.kap[far], self.ac[far], self.dy[far], self.Df[far], self.q[far] = sF, mF, kapF, acF, dyF, DfF, 1.0
        info["far_cone_lambda_at_c_b"] = lamB
        info["far_s_max"] = float(sF.max())
        v = self.v_main
        self.s[v], self.m[v], self.kap[v], self.ac[v], self.dy[v], self.Df[v], self.q[v] = 1.0, 1.0, 0.0, 0.0, 0.0, 1.0, 1.0
        info["cam_section_a_y_c"] = [self.cam_a, self.cam_y, self.cam_c]
        return info

    def all_rows(self, P=None):
        return self.rows(np.arange(self.nv), P=P)

    @property
    def h(self):
        return self.s * self.T[1] + self.dy


# v1 の Family を唇の変形だけに使うときの fit パラメータ（値は params_v1_kstar.json と同じ。v2 の params にあれば上書き）
V1_FIT_DEFAULTS = {"check_min_y_m": 0.1, "fit_tol_px": 0.0, "offframe_clamp_px": 400.0, "D_design_near_sigma_m": 40.0, "D_design_near_pow": 4.0,
                   "offframe_gap_m": 2.0, "offframe_decay_m": 8.0, "lip_collapse_max": 0.85, "tip_collapse_taper_m": 1.5, "retreat_max_m": 8.0,
                   "retreat_wall_frac": 0.8, "far_shrink_floor": 0.35, "flatten_monotone_below_D": 0.3, "far_D_design_delay_m": 1.2,
                   "far_D_design_sigma_m": 2.0, "lip_sigma_near_px": 44.0, "lip_sigma_far_px": 23.0, "retreat_beta_margin": 1.4,
                   "retreat_c0_m": 0.3, "smooth_rows": 3, "near_D_smooth_rows": 1.0, "bisect_iters": 22, "lip_row_fit": False}


def deconvolve_v2(fam, prm, log=print):
    """v1 の deconvolve と同じ（主断面の輪郭部分を断面内の法線方向へ少しずつ動かし、全行の像の包絡が補正後の目標に接するようにする）。
    違いは、唇の列（頂から lip_check_skip_cols 列より先）では主断面の行だけで包絡をとること。手前の行の唇は爪を除いて丸め、持ち上げ・切り詰めを
    別に当てはめているので、列ごとに主断面と対応しない（v1 のまま全行でとると、手前の行の丸めた唇先に合わせて主断面の唇先の爪が 18 px 内側へ引かれた）。"""
    pr = fam.prof
    P0 = fam.P.copy()
    n0 = V1.Profile.normals(P0)
    delta = np.zeros(pr.nu)
    drv = pr.driven
    idx = np.arange(fam.nv)
    eps = 0.02
    ker_sig = prm["smooth_sigma_samples"]
    jl = pr.j_top + int(fam.pf["lip_check_skip_cols"])
    hist = []
    best = (np.inf, delta.copy())
    for it in range(prm["iterations"]):
        P = P0 + delta[:, None] * n0
        A, Y = fam.rows(idx, P=P)
        s, _ = fam.sdf(idx, A, Y)
        s = s.copy()
        s[:, jl:] = -1e9
        s[fam.v_main, jl:] = fam.sdf(np.array([fam.v_main]), A[fam.v_main:fam.v_main + 1], Y[fam.v_main:fam.v_main + 1])[0][0, jl:]
        E = s.max(0)
        vs = s.argmax(0)
        A2, Y2 = fam.rows(idx, P=P + eps * n0)
        s2, _ = fam.sdf(idx, A2, Y2)
        ar = np.arange(pr.nu)
        g = (s2[vs, ar] - s[vs, ar]) / eps
        gm = (s2[fam.v_main, ar] - s[fam.v_main, ar]) / eps
        valid = (E > -1e8) & (g < -2.0) & (np.abs(g) >= 0.5 * np.maximum(np.abs(gm), 2.0))
        Ed = np.where(drv, E, np.maximum(E, 0.0))
        st = np.where(valid, prm["gain"] * Ed / np.abs(np.where(valid, g, -1.0)), 0.0)
        st = np.clip(st, -prm["max_step_m"], prm["max_step_m"])
        st = V1.gauss_rows(st, ker_sig)
        ev = E[drv & (E > -1e8)]
        score = max(float(np.abs(ev).max()), float(max(E[~drv].max(), 0.0)))
        if score < best[0]:
            best = (score, delta.copy())
        delta = np.clip(delta + st, -prm["delta_max_m"], prm["delta_max_m"])
        hist.append({"it": it, "E_driven_max_px": float(ev.max()), "E_driven_min_px": float(ev.min()),
                     "E_nondriven_max_px": float(E[~drv].max()), "delta_abs_max_m": float(np.abs(delta).max())})
    delta = best[1]
    for _ in range(60):
        P = P0 + delta[:, None] * n0
        hit = V1.section_crossings(P)
        if not hit:
            break
        for i, j in hit:
            for k in (i, j):
                lo, hi = max(k - 8, 0), min(k + 9, len(delta))
                delta[lo:hi] = V1.gauss_rows(delta[lo:hi], 2.0)
    hist.append({"best_score_px": best[0]})
    P = P0 + delta[:, None] * n0
    return P, delta, hist


class RowSubset:
    """行の族の一部（先頭から n 行）だけを v1 の投影固定・逆畳み込みの関数へ渡すための薄い包み。"""

    def __init__(self, fam, n):
        self.fam, self.nv = fam, n
        self.c = fam.c[:n]
        self.P, self.prof, self.tgt, self.pf, self.fr = fam.P, fam.prof, fam.tgt, fam.pf, fam.fr
        self.v_main = fam.v_main

    def sdf(self, idx, A, Y):
        return self.fam.sdf(np.atleast_1d(idx), A, Y)


def nearest_dist_2d(q, pts, chunk=256):
    """q (N,2) の各点から pts (M,2) の最も近い点までの距離（float32、小さな塊で。v1 の塊 2000 は行を増やすと数 GB になるため）。"""
    q = q.astype(np.float32)
    pts = pts.astype(np.float32)
    out = np.full(len(q), np.inf, np.float32)
    for k in range(0, len(pts), chunk):
        p = pts[k:k + chunk]
        d2 = (q[:, None, 0] - p[None, :, 0]) ** 2 + (q[:, None, 1] - p[None, :, 1]) ** 2
        out = np.minimum(out, d2.min(1))
    return np.sqrt(out)


def snap_tps_v2(fam, A, Y, prm, log=print):
    """v1 の snap_tps と同じ手順（シルエット頂点を目標の射線上へ貼り付け、移動を (σ, c) の TPS で内部へ広げる）。
    違いは、シルエット頂点からの距離の計算を小さな塊で行うことだけ（結果は同じ）。"""
    idx = np.arange(fam.nv)
    pr = fam.prof
    sig_u = V1.arclen(fam.P)
    stats = []
    tot = np.zeros(A.shape + (2,))
    rowh = np.maximum(Y.max(1), 1.0)
    Pm = fam.P
    dP = np.diff(Pm, axis=0)
    angP = np.degrees(np.abs((np.arctan2(dP[1:, 1], dP[1:, 0]) - np.arctan2(dP[:-1, 1], dP[:-1, 0]) + np.pi) % (2 * np.pi) - np.pi))
    sharp_cols = sorted(set((np.nonzero(angP >= prm.get("sharp_turn_deg", 35.0))[0] + 1).tolist() + list(pr.knot_cols) + [pr.j_tip]))
    for rnd in range(prm["rounds"]):
        s, pj = fam.sdf(idx, A, Y)
        Pn = np.stack([A, Y], -1)
        d = np.gradient(Pn, axis=1)
        d /= np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-12)
        n = np.stack([d[..., 1], -d[..., 0]], -1)
        eps = 0.01
        s2, _ = fam.sdf(idx, A + eps * n[..., 0], Y + eps * n[..., 1])
        g = (s2 - s) / eps
        inframe = (pj[..., 0] >= fam.tgt.x0 - 2) & (pj[..., 0] <= fam.tgt.x1 + 2) & (pj[..., 1] >= -2) & (pj[..., 1] <= 1081)
        gok = (s > -1e8) & (g < -prm.get("g_min_px_per_m", 10.0)) & inframe
        for kc in sharp_cols:
            gok[:, max(kc - 3, 0):kc + 4] = False
        gok[:, max(pr.j_tip - 6, 0):pr.j_tip + 7] = False
        sel = (s > -prm["band_px"]) & gok
        # 主断面以外の行は、唇先と唇の下面・内壁（唇先の手前 snap_nonmain_tip_margin 列から先）を貼り付けない。
        # 原画の内輪郭（72）と唇先は主断面がつくり、手前の行の唇はその内側にある（貼り付けると行ごとに唇が歪み、行の間で面が重なる）
        allow = np.ones_like(sel)
        allow[:, pr.j_tip - int(prm["snap_nonmain_tip_margin"]):] = False
        allow[fam.v_main, :] = True
        sel &= allow
        mainsel = np.zeros_like(sel)
        mainsel[fam.v_main, pr.driven] = True
        mainsel &= gok
        sel |= mainsel
        dd = np.where(sel, s / np.abs(np.where(sel, g, -1.0)), 0.0)
        cap = np.where(mainsel, prm.get("snap_main_max_m", 0.5), prm.get("snap_max_m", 0.1))
        dd = np.clip(dd, -cap, cap)
        disp = dd[..., None] * n
        vv, jj = np.nonzero(sel)
        gu, gv = prm["anchor_grid"]
        ju = np.linspace(0, pr.nu - 1, gu).round().astype(int)
        jv = np.linspace(0, fam.nv - 1, gv).round().astype(int)
        av, aj = np.meshgrid(jv, ju, indexing="ij")
        av, aj = av.ravel(), aj.ravel()
        far_ok = (s[av, aj] < -20.0) | (s[av, aj] < -1e8) | (av == 0) | (av == fam.nv - 1) | (aj == 0) | (aj == pr.nu - 1)
        av, aj = av[far_ok], aj[far_ok]
        cell = prm.get("ctrl_cell_m", 0.5)
        key = np.stack([np.floor(sig_u[jj] / cell), np.floor(fam.c[vv] / cell)], -1)
        _, first = np.unique(key, axis=0, return_index=True)
        vc, jc = vv[first], jj[first]
        ctrl = np.vstack([np.stack([sig_u[jc], fam.c[vc]], -1), np.stack([sig_u[aj], fam.c[av]], -1)])
        vals = np.vstack([disp[vc, jc], np.zeros((len(av), 2))])
        _, uidx = np.unique(np.round(ctrl / cell), axis=0, return_index=True)
        uidx = np.sort(uidx)
        ctrl, vals = ctrl[uidx], vals[uidx]
        if len(vv) == 0:
            stats.append({"round": rnd, "n_silhouette": 0})
            break
        reg = prm.get("tps_reg", 0.1)
        w, aff = V1.tps_solve(ctrl, vals, reg)
        q = np.stack(np.meshgrid(sig_u, fam.c), -1).reshape(-1, 2)
        field = V1.tps_eval(ctrl, w, aff, q).reshape(fam.nv, pr.nu, 2)
        sil_pts = np.stack([sig_u[jj], fam.c[vv]], -1)
        # 同じ (σ, c) のシルエット点は 1 つで足りる（0.1 m 格子で間引いてから距離をとる。落ち方は falloff_m ≈ 2 m）
        _, us = np.unique(np.round(sil_pts / 0.1), axis=0, return_index=True)
        dmin = nearest_dist_2d(q, sil_pts[us])
        fall = np.exp(-(dmin / prm.get("falloff_m", 2.0)) ** 2).reshape(fam.nv, pr.nu, 1)
        field = field * fall
        flat = Y <= fam.pf["check_min_y_m"]
        near_sil = (s > -prm.get("lock_px", 8.0)) & ~sel
        field[flat | near_sil] = 0.0
        # 主断面以外の行の唇・内壁・谷（唇先の手前 snap_nonmain_tip_margin 列から先）は TPS でも動かさない（貼り付けと同じ理由）
        field[~allow] = 0.0
        field[sel] = disp[sel]
        An = A + field[..., 0]
        Yn = Y + field[..., 1]
        undone = 0
        for v in range(fam.nv):
            if V1.section_crossings(np.stack([A[v], Y[v]], -1)):
                continue
            for _ in range(40):
                hit = V1.section_crossings(np.stack([An[v], Yn[v]], -1))
                if not hit:
                    break
                for i, j in hit:
                    for kk in (i, j):
                        lo, hi = max(kk - 3, 0), min(kk + 5, pr.nu)
                        An[v, lo:hi], Yn[v, lo:hi] = A[v, lo:hi], Y[v, lo:hi]
                        field[v, lo:hi] = 0.0
                        undone += hi - lo
            else:
                An[v], Yn[v] = A[v], Y[v]
                field[v] = 0.0
        A, Y = An, Yn
        tot += field
        ratio = np.linalg.norm(field, axis=-1) / rowh[:, None]
        stats.append({"round": rnd, "n_silhouette": int(sel.sum()), "n_ctrl": int(len(ctrl)),
                      "snap_abs_max_m": float(np.abs(dd[sel]).max()), "snap_abs_max_px": float(np.abs(s[sel]).max()),
                      "field_abs_max_m": float(np.linalg.norm(field, axis=-1).max()), "field_ratio_max": float(ratio.max()),
                      "vertices_undone_for_crossing": int(undone)})
        log("  snap round %d: %s" % (rnd, json.dumps(stats[-1])))
    total_ratio = np.linalg.norm(tot, axis=-1) / rowh[:, None]
    return A, Y, stats, float(np.linalg.norm(tot, axis=-1).max()), float(total_ratio.max())


def remove_reversals(A, Y, skip_row=None, max_iter=50):
    """断面の中で向きが 90° より大きく変わる点（小さな折り返し。Blender の検査では重なった面として数えられる）を、近くの列の平滑化で消す。
    skip_row（主断面）は動かさない。直した点の数を返す。"""
    nv, nu = A.shape
    fixed = 0
    for v in range(nv):
        if v == skip_row:
            continue
        for _ in range(max_iter):
            P = np.stack([A[v], Y[v]], -1)
            dd = np.diff(P, axis=0)
            nrm = np.linalg.norm(dd, axis=1)
            ok = nrm > 1e-9
            cosv = (dd[1:] * dd[:-1]).sum(1) / np.maximum(nrm[1:] * nrm[:-1], 1e-12)
            bad = np.nonzero((cosv < 0.0) & ok[1:] & ok[:-1])[0] + 1
            if not len(bad):
                break
            for jb in bad:
                for j_ in range(max(jb - 2, 1), min(jb + 2, nu - 2) + 1):
                    A[v, j_] = 0.5 * A[v, j_] + 0.25 * (A[v, j_ - 1] + A[v, j_ + 1])
                    Y[v, j_] = 0.5 * Y[v, j_] + 0.25 * (Y[v, j_ - 1] + Y[v, j_ + 1])
                fixed += 1
    return A, Y, fixed


def fix_si_fast(fr, c, A, Y, locked=None, max_rounds=60, win=6, pad=2, log=print):
    """v1 の fix_self_intersections と同じ平滑化で近くの三角形の交差を解く。毎回の検査は交差のあった行の前後 pad 行の帯だけにし、
    最初と最後だけ格子の全体を調べる（行を 240 に増やし、唇が波峰の全体にあるので、全体の検査を毎回すると遅いため）。"""
    nv, nu = A.shape
    A0, Y0 = A.copy(), Y.copy()
    bad = V1.local_self_intersections(fr.world(c, A, Y), win)
    hist = [len(bad)]
    if bad:
        rows_ = sorted(set(v for v, j in bad))
        cols_ = sorted(set(j for v, j in bad))
        log("  SI rows c=%s cols %s..%s" % ([round(float(c[v]), 2) for v in rows_][:30], cols_[:5], cols_[-5:]))
    for it in range(max_rounds):
        if not bad:
            break
        mark = np.zeros((nv, nu), bool)
        for v, j in bad:
            mark[max(v - 1, 0):v + 2, max(j - 2, 0):j + 3] = True
        mark[:, 0] = mark[:, -1] = False
        mark[0, :] = mark[-1, :] = False
        if locked is not None:
            mark &= ~locked
        An = A.copy()
        Yn = Y.copy()
        An[1:-1, 1:-1] = 0.5 * A[1:-1, 1:-1] + 0.125 * (A[:-2, 1:-1] + A[2:, 1:-1] + A[1:-1, :-2] + A[1:-1, 2:])
        Yn[1:-1, 1:-1] = 0.5 * Y[1:-1, 1:-1] + 0.125 * (Y[:-2, 1:-1] + Y[2:, 1:-1] + Y[1:-1, :-2] + Y[1:-1, 2:])
        A = np.where(mark, An, A)
        Y = np.where(mark, Yn, Y)
        rows = sorted(set(v for v, j in bad))
        blocks = []
        for v in rows:
            r0, r1 = max(v - pad, 0), min(v + pad + 1, nv - 1)
            if blocks and r0 <= blocks[-1][1] + 1:
                blocks[-1][1] = max(blocks[-1][1], r1)
            else:
                blocks.append([r0, r1])
        nb = set()
        for r0, r1 in blocks:
            Xs = fr.world(c[r0:r1 + 1], A[r0:r1 + 1], Y[r0:r1 + 1])
            nb |= {(v + r0, j) for v, j in V1.local_self_intersections(Xs, win)}
        bad = nb
        hist.append(len(bad))
    final = V1.local_self_intersections(fr.world(c, A, Y), win)
    hist.append("full:%d" % len(final))
    return A, Y, hist, float(np.hypot(A - A0, Y - Y0).max()), len(final)


# ---------------------------------------------------------------- 確認図（numpy、Unity 描画ではない）
def explore_png(fam, A, Y, path, every=6):
    tgt = fam.tgt
    sky = tgt.sdf > 0
    img = np.zeros(sky.shape + (3,), np.uint8)
    img[sky] = (232, 222, 196)
    img[~sky] = (96, 96, 96)
    X, pp = fam.project(np.arange(fam.nv), A, Y)
    for v in range(0, fam.nv, every):
        col = (255, 60, 60) if fam.c[v] > 0 else ((60, 200, 60) if fam.c[v] > -8 else (60, 120, 255))
        if v == fam.v_main:
            col = (0, 0, 0)
        Q = np.round((pp[v, :, :2] + 0.5) * 2 - 0.5).astype(np.int32)
        cv2.polylines(img, [Q], False, col, 1, cv2.LINE_AA)
    T.imwrite(path, img)


def sections_png(fam, A, Y, path, cs):
    W, H = 1600, 900
    img = np.full((H, W, 3), 255, np.uint8)
    S = lambda a, y: np.stack([700 + a * 22, 850 - y * 22], -1).astype(np.int32)
    for i, cc in enumerate(cs):
        v = int(np.argmin(np.abs(fam.c - cc)))
        col = tuple(int(x) for x in cv2.applyColorMap(np.array([[int(255 * i / max(len(cs) - 1, 1))]], np.uint8), cv2.COLORMAP_JET)[0, 0][::-1])
        cv2.polylines(img, [S(A[v], Y[v])], False, col, 2 if v == fam.v_main else 1, cv2.LINE_AA)
        cv2.putText(img, "c=%.1f h=%.1f s=%.2f m=%.2f q=%.2f ac=%.1f" % (fam.c[v], fam.h[v], fam.s[v], fam.m[v], fam.q[v], fam.ac[v]), (10, 20 + 18 * i),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
    T.imwrite(path, img)


def plan_png(fam, X, path):
    """平面図（真上から、x 右・z 上）。行ごとの頂と唇先、座席。"""
    W, H = 1400, 1000
    img = np.full((H, W, 3), 255, np.uint8)
    S = lambda p: np.stack([700 + (p[..., 0] + 5) * 14, 600 - (p[..., 2] + 5) * 14], -1).astype(np.int32)
    pr = fam.prof
    for v in range(0, fam.nv, 3):
        cv2.polylines(img, [S(X[v, pr.j_B:pr.j_E])], False, (200, 200, 200), 1)
    cv2.polylines(img, [S(X[:, pr.j_top])], False, (0, 0, 0), 2)
    cv2.polylines(img, [S(X[:, pr.j_tip])], False, (220, 0, 0), 2)
    cv2.polylines(img, [S(X[:, pr.j_corner])], False, (0, 0, 220), 1)
    try:
        seat = T.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
        e = np.array(seat["seat"]["eye_world"])
        cv2.circle(img, tuple(int(x) for x in S(e)), 6, (0, 160, 0), -1)
    except Exception:
        pass
    T.imwrite(path, img)


# ---------------------------------------------------------------- 1 案を作る
def build(key, params, tgt, out_dir, explore=False, log=print):
    t0 = time.time()
    alpha = float(params["alpha_deg"])
    fr = V1.Frame(tgt.spec, alpha, params["anchor"], tgt)
    prof = V1.Profile(fr, tgt, params["profile"])
    fam = FamilyV2(fr, prof, tgt, params["rows"], params["fit"])
    P_init = prof.P.copy()
    info1 = fam.fit()
    log("[%s] fit %.1fs %s" % (key, time.time() - t0, json.dumps(info1)))
    prev_dir = os.path.join(out_dir, "preview")
    os.makedirs(prev_dir, exist_ok=True)
    if explore:
        A, Y = fam.all_rows()
        explore_png(fam, A, Y, os.path.join(prev_dir, "explore_rows_fit1.png"))
        sections_png(fam, A, Y, os.path.join(prev_dir, "explore_sections_fit1.png"), [-24, -18, -12, -8, -5, -3, -1.5, -0.5, 0, 1, 2, 3, 5, 7, 9, 11])
        plan_png(fam, fr.world(fam.c, A, Y), os.path.join(prev_dir, "explore_plan_fit1.png"))
        np.savez(os.path.join(prev_dir, "explore_rows.npz"), c=fam.c, s=fam.s, m=fam.m, kap=fam.kap, ac=fam.ac, dy=fam.dy, Df=fam.Df, q=fam.q)
        s, _ = fam.sdf(np.arange(fam.nv), A, Y)
        log("explore: max sdf per row > 0: %s" % [(round(float(fam.c[v]), 2), round(float(s[v].max()), 2)) for v in range(fam.nv) if s[v].max() > 0][:40])
        return None
    # ---- v1 と同じ段：逆畳み込み（主断面の輪郭部分）→ 行を合わせ直す → 逆畳み込み
    P, delta, hist = deconvolve_v2(fam, params["deconvolution"], log)
    fam.set_profile(P)
    info2 = fam.fit()
    P, delta2, hist2 = deconvolve_v2(fam, params["deconvolution"], log)
    delta = delta + delta2
    fam.set_profile(P)
    info3 = fam.fit()
    log("[%s] deconvolution+refit %.1fs  best %.2f px  %s" % (key, time.time() - t0, hist2[-1]["best_score_px"], json.dumps(info3)))
    A, Y = fam.all_rows()
    A_fit, Y_fit = A.copy(), Y.copy()
    s_pre, _ = fam.sdf(np.arange(fam.nv), A, Y)
    # 投影固定と TPS は手前の行と主断面（原画視点の輪郭をつくる行）だけに行う。奥の錐の行は主断面に隠れる（像が主断面と同じ）ので、
    # 貼り付けた後の主断面から作り直す（投影中心のまわりの相似なので、隠れたまま）。
    nsub = fam.v_main + 1
    sub = RowSubset(fam, nsub)
    As, Ys, snap_stats, tps_max_m, tps_ratio = snap_tps_v2(sub, A[:nsub].copy(), Y[:nsub].copy(), params["snap_tps"], log)
    A[:nsub], Y[:nsub] = As, Ys
    P_snap = np.stack([A[fam.v_main], Y[fam.v_main]], -1)
    P_keep = fam.P
    fam.set_profile(P_snap)
    far_idx = np.arange(fam.v_main + 1, fam.nv)
    Af, Yf = fam.rows(far_idx)
    A[far_idx], Y[far_idx] = Af, Yf
    fam.set_profile(P_keep)
    log("[%s] snap (near+main) %.1fs; far rows rebuilt from the snapped main row" % (key, time.time() - t0))
    A0u, Y0u = A.copy(), Y.copy()
    A, Y, untangled = V1.untangle_rows(A, Y)
    locked = np.zeros_like(A, bool)
    locked[fam.v_main, prof.driven] = True
    si_hist, si_move = [], 0.0
    for rnd in range(4):
        A, Y, h_, mv_, nfin = fix_si_fast(fr, fam.c, A, Y, locked=locked, log=log)
        si_hist += h_
        si_move = max(si_move, mv_)
        A, Y, npoke = V1.push_in_pokes(fam, A, Y, locked, params["snap_tps"])
        si_hist.append("poke:%d" % npoke)
        log("[%s] SI round %d %s" % (key, rnd, h_))
        if npoke == 0 and nfin == 0:
            break
    A, Y, h_, mv_, nfin = fix_si_fast(fr, fam.c, A, Y, locked=locked)
    si_hist += h_
    si_move = max(si_move, mv_)
    if nfin > 0:
        A, Y, h_, mv_, nfin = fix_si_fast(fr, fam.c, A, Y, locked=None)
        si_hist += ["unlocked"] + h_
        si_move = max(si_move, mv_)
    A, Y, untangled2 = V1.untangle_rows(A, Y)
    untangled.update(untangled2)
    A, Y, n_rev = remove_reversals(A, Y, skip_row=fam.v_main)
    si_hist.append("reversals_fixed:%d" % n_rev)
    if n_rev:
        A, Y, h_, mv_, nfin = fix_si_fast(fr, fam.c, A, Y, locked=locked, log=log)
        si_hist += ["after_reversals"] + h_
    untangle_move = float(np.hypot(A - A0u, Y - Y0u).max())
    log("[%s] snap+TPS+untangle %.1fs  field max %.3f m (ratio %.4f)  local SI %s" % (key, time.time() - t0, tps_max_m, tps_ratio, si_hist))
    return finish(key, params, tgt, out_dir, fr, prof, fam, A, Y, A_fit, Y_fit, P_init, delta, hist2, info1, info3, snap_stats, tps_max_m, tps_ratio,
                  untangled, untangle_move, si_hist, s_pre, t0, log)


def plan_angle_deg(fr, d):
    """平面図の向き d（x, z）と画面の水平方向 ea のなす角（奥へ向かう側を正にとる、度）。"""
    ea = fr.ea[[0, 2]]
    hh = fr.h[[0, 2]]
    d = np.asarray(d, float)
    d = d / max(np.linalg.norm(d), 1e-12)
    return float(np.degrees(np.arctan2(d @ hh, d @ ea)))


def finish(key, params, tgt, out_dir, fr, prof, fam, A, Y, A_fit, Y_fit, P_init, delta, hist2, info1, info3, snap_stats, tps_max_m, tps_ratio,
           untangled, untangle_move, si_hist, s_pre, t0, log):
    nu, nv = prof.nu, fam.nv
    X = fr.world(fam.c, A, Y)
    tris = V1.triangles(nu, nv)
    s_u = V1.arclen(fam.P)
    uv = np.stack(np.meshgrid(s_u / s_u[-1], (fam.c - fam.c[0]) / (fam.c[-1] - fam.c[0])), -1).reshape(-1, 2)
    uv2 = np.stack(np.meshgrid(s_u, fam.c), -1).reshape(-1, 2)
    checks = V1.mesh_checks(X, tris, A, Y, nv, nu)
    s_fin, pj_fin = fam.sdf(np.arange(nv), A, Y)
    checks["final_vertex_sdf_max_px"] = float(s_fin.max())
    inf = (pj_fin[..., 0] >= tgt.x0) & (pj_fin[..., 0] <= tgt.x1) & (pj_fin[..., 1] >= 0) & (pj_fin[..., 1] <= 1079)
    checks["final_vertex_sdf_max_px_in_frame"] = float(np.where(inf, s_fin, -1e9).max())
    checks["rows_fit_before_snap_sdf_max_px"] = float(s_pre.max())
    checks["note_ja"] = "final_vertex_sdf_max_px は画面の外（採点列の左右 400 px まで、採点列の端の列で評価）も含む。in_frame は PaintingCam の画面内の頂点だけ。"
    # ---- 波峰線・巻き
    H = Y.max(1)
    peak = float(H.max())
    jt = prof.j_top
    crest = X[:, jt]
    seg = np.linalg.norm(np.diff(crest[:, [0, 2]], axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    above = H > 0.5 * peak
    ia = np.nonzero(above)[0]
    rat = []
    for v in range(nv):
        if H[v] < 2.0:
            rat.append(None)
            continue
        rat.append(V1.section_ratios(A[v], Y[v], prof, H[v]))

    def col(key_):
        return np.array([(r[key_] if (r and r[key_] is not None) else np.nan) for r in rat])
    ov = col("overhang_over_H")
    wl = col("wall_over_H")
    lt = col("lip_vertical_thickness_0p75m_behind_tip_m")
    thr = params["checks"]["curl_overhang_over_H_min"]
    curl = np.nan_to_num(ov, nan=-1.0) >= thr
    ic = np.nonzero(curl)[0]
    runs, cur = [], []
    for v in range(nv):
        if curl[v]:
            cur.append(v)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    best = max(runs, key=len) if runs else []
    curl_len = float(cum[best[-1]] - cum[best[0]]) if best else 0.0
    curl_above = [v for v in best if above[v]]
    jk = prof.j_corner
    jtip_row = jt + np.argmax(A[:, jt:jk + 1], axis=1)
    tipW = X[np.arange(nv), jtip_row]
    tseg = np.linalg.norm(np.diff(tipW, axis=0), axis=1)
    tip_len = float(tseg[best[0]:best[-1]].sum()) if best else 0.0

    def dir_between(c0, c1):
        i0 = int(np.argmin(np.abs(fam.c - c0)))
        i1 = int(np.argmin(np.abs(fam.c - c1)))
        return plan_angle_deg(fr, (crest[i1] - crest[i0])[[0, 2]])
    fp = params["fit"]
    angles = {"near_shoulder_c_-12_to_-2": dir_between(-12.0, -2.0), "near_side_at_main_c_-1_to_0": dir_between(-1.0, 0.0),
              "far_side_at_main_c_0_to_1": dir_between(0.0, 1.0), "far_cone_c_0_to_c_b": dir_between(0.0, fp["far_cone_until_m"]),
              "far_tail_c_b_to_end": dir_between(fp["far_cone_until_m"], fp["far_end_m"])}
    # ---- 座席 v1 との関係（記録）
    seat = T.load_json(os.path.join(REPO, "Tools", "GWContext", "seat_v1.json"))
    eye = np.array(seat["seat"]["eye_world"], float)
    lipW = X[:, jt:jk + 1].reshape(-1, 3)
    dh = np.linalg.norm((lipW - eye)[:, [0, 2]], axis=1)
    up = lipW[:, 1] - eye[1]
    elev = np.degrees(np.arctan2(up, dh))
    hi = up > 3.0
    i_near = int(np.argmin(np.where(hi, dh, np.inf)))
    tip_dh = np.linalg.norm((tipW - eye)[:, [0, 2]], axis=1)
    i_tip = int(np.argmin(np.where(tipW[:, 1] > eye[1] + 3, tip_dh, np.inf)))
    seat_rec = {"eye_world": eye.tolist(),
                "nearest_lip_point_above_3m": {"world": lipW[i_near].round(3).tolist(), "horizontal_m": float(dh[i_near]), "elevation_deg": float(elev[i_near])},
                "nearest_lip_tip": {"row_c": float(fam.c[i_tip]), "world": tipW[i_tip].round(3).tolist(), "horizontal_m": float(tip_dh[i_tip]),
                                    "elevation_deg": float(np.degrees(np.arctan2(tipW[i_tip, 1] - eye[1], tip_dh[i_tip])))},
                "lip_points_within_horizontal_m": {str(r): int(np.count_nonzero(hi & (dh <= r))) for r in (1.0, 2.0, 3.0, 4.0, 5.0)},
                "lip_elevation_max_deg": float(elev[hi].max()) if hi.any() else None,
                "note_ja": "唇（各行の頂〜角の列）の点で、目より 3 m 以上高い点との水平距離と仰角。記録のみ（108/109 は番号30 の範囲）。"}
    # ---- 書き出し
    os.makedirs(out_dir, exist_ok=True)
    gwb = os.path.join(out_dir, "kstar_%s.gwb" % key)
    obj = os.path.join(out_dir, "kstar_%s.obj" % key)
    V1.write_gwb(gwb, nu, nv, uv, uv2, tris, X)
    np.savez_compressed(os.path.join(out_dir, "kstar_%s_rows.npz" % key), A=A, Y=Y, c=fam.c, P=fam.P, P_init=P_init, A_fit=A_fit, Y_fit=Y_fit,
                        s=fam.s, m=fam.m, q=fam.q, kap=fam.kap, ac=fam.ac, dy=fam.dy, Df=fam.Df, beta=fam.beta(np.arange(nv)))
    V1.write_obj(obj, X, uv, tris, ["gw_wavegen v2 K* %s (26R01, alpha 45 deg), Unity world coordinates (left-handed, Y up, metres)" % key,
                                    "vertex index = row * %d + column; row = crest-line section (c), column = section arc (sigma)" % nu,
                                    "vt = (sigma / sigma_total, (c - c_min) / (c_max - c_min))"])
    idx = {"j_B": prof.j_B, "j_top": prof.j_top, "j_tip": prof.j_tip, "j_corner": prof.j_corner, "j_facebot": prof.j_facebot, "j_E": prof.j_E}
    regions = []
    names = [("flat_back_sea", 0, prof.j_B), ("back_slope", prof.j_B, prof.j_top), ("lip_upper", prof.j_top, prof.j_tip), ("lip_under", prof.j_tip, prof.j_corner),
             ("inner_wall", prof.j_corner, prof.j_facebot), ("trough", prof.j_facebot, prof.j_E), ("flat_front_sea", prof.j_E, nu - 1)]
    for nm, a_, b_ in names:
        regions.append({"name": nm, "col_from": int(a_), "col_to": int(b_), "u_from": float(s_u[a_] / s_u[-1]), "u_to": float(s_u[b_] / s_u[-1])})
    uvl = {"schema": "GreatWave.GWWaveGen.kstar_uv_layout/1", "number": "26修正01", "key": key, "nu": nu, "nv": nv,
           "uv0_ja": "UV0 = (σ/σ_total, (c − c_min)/(c_max − c_min))。σ は主断面 P0 の弧長（全行で同じ列は同じ u）。番号26 と同じ並び。",
           "uv2_ja": "UV2 = (σ [m], c [m])", "profile_index": idx, "u_of_column": np.round(s_u / s_u[-1], 7).tolist(),
           "column_regions": regions, "c_of_row_m": np.round(fam.c, 5).tolist(), "v_of_row": np.round((fam.c - fam.c[0]) / (fam.c[-1] - fam.c[0]), 7).tolist(),
           "main_row": fam.v_main}
    T.save_json(os.path.join(out_dir, "kstar_%s_uv_layout.json" % key), uvl)
    prev_dir = os.path.join(out_dir, "preview")
    os.makedirs(prev_dir, exist_ok=True)
    prev = V1.preview_metrics(fr, tgt, X, tris, os.path.join(prev_dir, "kstar_%s_numpy_overlay.png" % key),
                              "26R01 gw_wavegen v2 %s numpy preview at t* (not Unity)" % key)
    explore_png(fam, A, Y, os.path.join(prev_dir, "rows_final.png"))
    sections_png(fam, A, Y, os.path.join(prev_dir, "sections_final.png"), [-24, -18, -12, -8, -5, -3, -1.5, -0.5, 0, 1, 2, 3, 4, 5, 7, 10])
    plan_png(fam, X, os.path.join(prev_dir, "plan_final.png"))
    log("[%s] preview %s (%.1fs)" % (key, json.dumps({k: v["max_px"] for k, v in prev.items()}), time.time() - t0))
    central = [v for v in range(nv) if -12.0 <= fam.c[v] <= 4.0 and rat[v] is not None]
    meta = {
        "schema": "GreatWave.GWWaveGen.kstar_meta/1", "generator": "gw_wavegen v2", "number": "26修正01", "key": key,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "alpha_deg": float(params["alpha_deg"]), "interpretation_ja": params["interpretation_definition_ja"],
        "files": {"gwb": os.path.basename(gwb), "gwb_sha256": T.sha256_file(gwb), "gwb_bytes": os.path.getsize(gwb),
                  "obj": os.path.basename(obj), "obj_sha256": T.sha256_file(obj), "obj_bytes": os.path.getsize(obj),
                  "uv_layout": "kstar_%s_uv_layout.json" % key},
        "format_ja": "gwb は番号24・26 と同じ GWW0 書式（先頭 32 バイト = 'GWW0' + int32 版 1, nu, nv, フレーム数 1, float32 fps 30, int32 t* フレーム 0, 三角形数。続いて UV (N×2 float32)、UV2 (N×2 float32)、三角形 (M×3 int32)、頂点位置 (N×3 float32、Unity ワールド座標 m)）。N = nu×nv、頂点添字 = 行×nu + 列。",
        "uv_layout_ja": "UV0 = (σ/σ_total, (c − c_min)/(c_max − c_min))。σ は主断面 P0 の弧長（全行で同じ列は同じ σ）、c は波峰線方向の断面位置（m、負がカメラ側の手前の肩）。u は後ろの平らな海（0）→ 背面の坂 → 頂 → 唇の上側 → 唇先端 → 唇の下側 → 内壁 → 谷 → 前の平らな海（1）、v は手前の端（0）→ 奥の端（1）。UV2 = (σ [m], c [m])。番号26 と同じ並び（行の数だけ 200 → %d）。" % nv,
        "nu": nu, "nv": nv, "vertex_count": nu * nv, "triangle_count": int(len(tris)),
        "frame": {"e_crest": fr.e.tolist(), "t_travel": fr.t.tolist(), "h": fr.h.tolist(), "ea": fr.ea.tolist(),
                  "anchor_crest_top_world": fr.A.tolist(), "section_origin_world": fr.O0.tolist(), "H0_m": fr.H0,
                  "crest_top_display_px": fr.top_display.tolist(), "camera_in_section_a_y_c": [fam.cam_a, fam.cam_y, fam.cam_c]},
        "profile": {"index": idx, "a_back_foot_m": prof.a_bf, "a_face_at_half_H_m": prof.a_face_half,
                    "P0_final": np.round(fam.P, 5).tolist(), "P0_initial": np.round(P_init, 5).tolist(),
                    "deconvolution_delta_abs_max_m": float(np.abs(delta).max()), "deconvolution_delta_over_H0": float(np.abs(delta).max() / fr.H0)},
        "rows": {"c_m": np.round(fam.c, 5).tolist(), "s_scale": np.round(fam.s, 5).tolist(), "m_lip_length": np.round(fam.m, 5).tolist(),
                 "q_lip_lift": np.round(fam.q, 5).tolist(), "kappa_lip_collapse": np.round(fam.kap, 5).tolist(), "ac_crest_offset_m": np.round(fam.ac, 5).tolist(),
                 "dy_m": np.round(fam.dy, 5).tolist(), "Df_flatten": np.round(fam.Df, 5).tolist(), "beta_declaw": np.round(fam.beta(np.arange(nv)), 5).tolist(),
                 "main_row": fam.v_main, "fit_info": {"pass1": info1, "final": info3}},
        "crest_line": {"peak_height_m": peak, "peak_row_c": float(fam.c[int(np.argmax(H))]),
                       "above_half_peak_c_range_m": [float(fam.c[ia[0]]), float(fam.c[ia[-1]])] if len(ia) else None,
                       "above_half_peak_arc_length_m": float(cum[ia[-1]] - cum[ia[0]]) if len(ia) else 0.0,
                       "above_half_peak_arc_length_over_H0": float((cum[ia[-1]] - cum[ia[0]]) / fr.H0) if len(ia) else 0.0,
                       "plan_angle_to_screen_deg": angles,
                       "crest_world_every_10_rows": np.round(crest[::10], 3).tolist(),
                       "note_ja": "波峰線は各行の頂の列（主断面の頂 j_top）。弧長は平面図（x, z）で測る。角度は平面図の向きと画面の水平方向 ea のなす角。"},
        "curl": {"criterion_ja": "行の断面で、0.3H の高さの内壁から唇先までの張り出し（H は行の高さ）が %.2fH 以上なら「巻きのある行」とする。" % thr,
                 "curl_rows": int(len(ic)), "longest_curl_run_c_range_m": [float(fam.c[best[0]]), float(fam.c[best[-1]])] if best else None,
                 "longest_curl_run_crest_arc_m": curl_len, "longest_curl_run_crest_arc_over_H0": curl_len / fr.H0,
                 "longest_curl_run_lip_tip_line_m": tip_len,
                 "longest_curl_run_rows_above_half_peak": int(len(curl_above)),
                 "curl_above_half_peak_crest_arc_m": float(cum[curl_above[-1]] - cum[curl_above[0]]) if curl_above else 0.0,
                 "lip_thickness_min_over_curl_rows_m": float(np.nanmin(lt[curl])) if curl.any() else None,
                 "lip_thickness_min_row_c": float(fam.c[ic[int(np.nanargmin(lt[ic]))]]) if curl.any() else None,
                 "c_overhangH_wallH_lipthick_every_5_rows": [[round(float(fam.c[v]), 2), None if np.isnan(ov[v]) else round(float(ov[v]), 3),
                                                              None if np.isnan(wl[v]) else round(float(wl[v]), 3), None if np.isnan(lt[v]) else round(float(lt[v]), 3)]
                                                             for v in range(0, nv, 5)],
                 "lip_tip_world_every_5_rows": np.round(tipW[::5], 3).tolist()},
        "reference_ratios_self_check_record_only": {"main_row": rat[fam.v_main],
                                                    "central_rows_c_-12_to_4": {"wall_over_H_min_max": [float(np.nanmin(wl[central])), float(np.nanmax(wl[central]))],
                                                                                "overhang_over_H_min_max": [float(np.nanmin(ov[central])), float(np.nanmax(ov[central]))],
                                                                                "wall_over_H_median": float(np.nanmedian(wl[central])),
                                                                                "overhang_over_H_median": float(np.nanmedian(ov[central]))},
                                                    "targets_q5": params["reference_ratios_q5"]},
        "seat_v1_relation_record_only": seat_rec,
        "deconvolution_history_last": hist2[-2:],
        "snap_tps": {"rounds": snap_stats, "total_field_abs_max_m": tps_max_m, "total_field_over_local_size_max": tps_ratio,
                     "cap_ratio": params["snap_tps"]["cap_ratio"], "within_cap": bool(tps_ratio <= params["snap_tps"]["cap_ratio"])},
        "checks": checks, "untangle": {"rows_fixed": {str(k): v for k, v in untangled.items()}, "max_move_m": untangle_move,
                                       "local_self_intersection_vertices_per_iteration": si_hist},
        "numpy_preview_envelope": prev, "seconds": time.time() - t0,
    }
    T.save_json(os.path.join(out_dir, "kstar_%s_meta.json" % key), meta)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--params", default=DEFAULT_PARAMS)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--explore", action="store_true")
    a = ap.parse_args()
    params = T.load_json(a.params)
    tgt = V1.Target()
    meta = build("a45", params, tgt, a.out, explore=a.explore)
    if meta is None:
        return
    inputs = [os.path.abspath(a.params), T.SPEC_PATH, os.path.join(HERE, "gw_wavegen_v2.py"), os.path.join(HERE, "gw_wavegen_v1.py"),
              os.path.join(HERE, "gw_wavegen.py"), os.path.join(REPO, "Tools", "PaintingTruth", "truthlib.py"),
              os.path.join(REPO, "Tools", "GWContext", "seat_v1.json")] + [T.repo_abs(v) for k, v in params["inputs"].items()]
    summary = {"generator": "gw_wavegen v2", "number": "26修正01", "inputs_sha256": {T.repo_rel(p_): T.sha256_file(p_) for p_ in inputs},
               "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__},
               "a45": {"meta": "kstar_a45_meta.json", "gwb_sha256": meta["files"]["gwb_sha256"], "obj_sha256": meta["files"]["obj_sha256"],
                       "numpy_preview_envelope": meta["numpy_preview_envelope"]}}
    T.save_json(os.path.join(a.out, "kstar_summary.json"), summary)
    print("KSTAR_DONE", json.dumps({k: v["max_px"] for k, v in meta["numpy_preview_envelope"].items()}))


if __name__ == "__main__":
    main()
