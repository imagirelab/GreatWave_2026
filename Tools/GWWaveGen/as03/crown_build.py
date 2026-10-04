# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-1・B1-2・B1-4：波頭の立体の白い指の冠（OUT＝彫刻のように開く／IN＝原画視点の影を原画の白の冠・爪の区域に収める）。

- 主役波：t* の K*′ AS02C（見本02 修正の回 1）。指の根元は、共有の白の印（crown_whitemask.py）の前の白の地（region 2・3）の上だけ。
- 数（S1 の sculpture_spec.json、参照の彫刻の数を主役波の m へ当てた値）：手（掌＋指）、指の長さ・太さ・細り、分かれる所、手の中の指の数、
  指どうしの開き、根元の法線との角、曲がり（垂れ）、先の形（丸い・口の開いた・ふくらむ）、段（頂の縁・前の斜面・唇の縁／垂れる縁）。
- 利用者の爪（S2 の CREST_CROWN 48 本、見本02 修正の回 1 の 3D の爪）は指の先：OUT は根元の周りに回して面から起こし（根元と法線の角を
  彫刻の数へ）、IN は見本02 の置き方 A のまま。どちらも爪の下に指の体（短い掌）を置き、爪は手の 1 本の指になる。
- IN：手・指を作った後、原画のカメラ（PaintingCam v1）で各頂点を写し、原画の空（2 px より内）か、原画の白の冠・爪の区域の外（主役波の後ろに
  隠れない所）に出る手は、①射線の向き（奥）へ回す ②0.85 倍に縮める、を 4 回まで繰り返し、残れば外す。
- 根元は面の下へ 0.15 m 沈め、根元の 0.3 m で太さを広げ（1.7 倍まで）、面から 0.15 m までの頂点の法線を面の法線へなめらかに移す（台を作らない）。
- 面を突き抜ける指（根元の 0.25 m より先が面の下）と、別の手どうしの重なりは、回す・縮めるで直し、残れば外して記録する。
- 出力（Git 対象外）：Unity/Build/Polish/sample03/crown/<OUT|IN>/：as03_crown.bin・.json（shared/README.md の静止のメッシュの書式。
  position・normal・uv5 =（ao, keyVis, whiteSD = +10, kind 1）・uv3 =（f, 指の番号, 種類 0 手・1 指・2 利用者の爪, 0））、as03_crown.obj、
  as03_crown_layout.json（指ごと）、as03_crown_report.json（S1 の数との比べ・検査・頂点の数）。
原画の色は面へ写さない（Q28）。参照モデルの OBJ・写真は読まない（F13-1）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_build.py --mode OUT（または IN）
"""
import argparse
import json
import math
import os
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402
import crown_geom as GM  # noqa: E402
import crown_whitemask as WM  # noqa: E402

D = math.pi / 180.0
DOWN = np.array([0.0, -1.0, 0.0])


def lognorm(rng, med, sig, lo, hi):
    return float(np.clip(med * math.exp(rng.normal(0.0, sig)), lo, hi))


def spec_targets():
    sp = G.jload(G.SPEC)
    cc = sp["1_crest_crown"]
    t = {
        "digit_len_m": cc["length"]["digit_len_over_H"]["hero"],
        "hand_len_m": cc["length"]["hand_len_over_H"]["hero"],
        "digit_r_base": cc["thickness"]["digit_diam_base_over_H"]["hero"]["p50_m"] / 2,
        "digit_r_mid": cc["thickness"]["digit_diam_mid_over_H"]["hero"]["p50_m"] / 2,
        "digit_r_tip": cc["thickness"]["digit_diam_tip_over_H"]["hero"]["p50_m"] / 2,
        "hand_r_base": cc["thickness"]["hand_diam_base_over_H"]["hero"]["p50_m"] / 2,
        "taper_digit": cc["thickness"]["taper_law_digit"]["value"],
        "taper_hand": cc["thickness"]["taper_law_hand"]["value"],
        "branch_frac": cc["branching"]["branch_start_fraction_of_hand_length"]["value"],
        "angle_between_digits": cc["branching"]["angle_between_digits_same_hand_deg"]["value"],
        "angle_vs_normal": cc["direction"]["angle_digit_vs_root_normal_deg"]["value"],
        "overall_vs_up": cc["direction"]["angle_digit_overall_vs_up_deg"]["value"],
        "tip_vs_up": cc["direction"]["angle_digit_tip_vs_up_deg"]["value"],
        "frac_tips_down": cc["direction"]["frac_tips_pointing_down"]["value"],
        "frac_forward": cc["direction"]["frac_forward_over_lip"]["value"],
        "curl": cc["direction"]["curl_root_to_tip_deg"]["value"],
        "fingertips_hero": cc["counts"]["fingertips_per_m_of_L"]["hero"],
        "hands_hero": cc["counts"]["hands_per_m_of_L"]["hero"],
        "nearest_root_m": cc["layering"]["nearest_root_spacing_over_H"]["hero"]["p50_m"],
    }
    return t, G.sha(G.SPEC)


class Front:
    """前（頂の列より前）の点：行 r（小数）と、行に沿う頂からの弧長 s（m）から、位置・法線・列。"""

    def __init__(self, h, M):
        self.h, self.M = h, M

    def row_point(self, r, s):
        h = self.h
        j0 = int(h.top_col[r])
        arr = self.M.s[r, j0:]
        jf = float(np.interp(s, arr, np.arange(j0, h.C)))
        j = min(int(math.floor(jf)), h.C - 2)
        fj = jf - j
        P = h.X[r, j] * (1 - fj) + h.X[r, j + 1] * fj
        N = h.N[r, j] * (1 - fj) + h.N[r, j + 1] * fj
        return P, GM.nrm(N), jf

    def at(self, r, s):
        r0 = int(math.floor(r))
        r0 = min(max(r0, 0), self.h.R - 2)
        fr = r - r0
        P0, N0, j0 = self.row_point(r0, s)
        P1, N1, j1 = self.row_point(r0 + 1, s)
        return P0 * (1 - fr) + P1 * fr, GM.nrm(N0 * (1 - fr) + N1 * fr), j0 * (1 - fr) + j1 * fr


class Crown:
    def __init__(self, mode, seed):
        self.mode = mode
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        t0 = time.time()
        self.h = h = G.HeroData()
        self.M = WM.Mask(h, "for_crown")
        self.F = Front(h, self.M)
        self.sheet = GM.Sheet(h.X, h.N, rows=(40, 239), cols=(18, 394), sub=2)
        self.T, self.spec_sha = spec_targets()
        self.tubes = []          # dict(kind, hand, P, rad, aspect, side, tip, nseg)
        self.hands = []
        self.user = []
        self.dropped = []
        self.log = []
        self.rim_digits = None          # 頂の縁の手の指の数の分布（None なら S1 の写真の 2〜5 本）
        self.smooth_hands = False       # 手続きの手を距離の場のなめらかな和で 1 つの面にする（--smooth-hands）
        self.lip_hands = 0              # 唇の縁から垂れる手の数（--lip-hands）
        self.smooth_vox, self.smooth_k = 0.035, 0.045
        self.travel = GM.nrm(h.t)
        self.ecrest = GM.nrm(h.e)
        print("init", round(time.time() - t0, 1), "s", flush=True)

    # ------------------------------------------------------------ 向きの場
    def fwd_dir(self, n):
        """前（指が出る向きの水平の成分）：進む向き t を主にし、面の水平の法線を 25% 混ぜる。
        （水平の法線だけにすると、左の肩（行 97〜150）で面が −c へ傾くため、指が頂の線に沿って横（左）へ出て、背の輪郭に背びれのように並んだ。
        S1：指の 91% が唇の上へ前に出る）"""
        nh = n - (n @ GM.UP) * GM.UP
        a = np.linalg.norm(nh)
        if a < 1e-6:
            return self.travel
        return GM.nrm(0.75 * self.travel + 0.25 * GM.nrm(nh) * min(1.0, a / 0.5))

    def target_dir(self, n, elev_deg):
        f = self.fwd_dir(n)
        e = elev_deg * D
        return GM.nrm(f * math.cos(e) + GM.UP * math.sin(e))

    def initial_dir(self, n, target, theta_deg):
        ang = GM.angle(n, target)
        if ang <= 1e-3:
            return GM.nrm(target)
        t = min(1.0, theta_deg / ang)
        return GM.nrm(GM.slerp(n, target, t))

    def spine(self, P0, d0, L, curl_deg, n=24, pw=1.2, toward=None):
        toward = DOWN if toward is None else toward
        ax = np.cross(d0, toward)
        if np.linalg.norm(ax) < 1e-6:
            ax = np.cross(d0, self.ecrest)
        ax = GM.nrm(ax)
        f = np.linspace(0, 1, n)
        dirs = np.stack([GM.rot(d0, ax, curl_deg * D * (fi ** pw)) for fi in f])
        ds = L / (n - 1)
        P = np.zeros((n, 3))
        P[0] = P0
        for i in range(1, n):
            P[i] = P[i - 1] + 0.5 * (dirs[i - 1] + dirs[i]) * ds
        return P, dirs

    # ------------------------------------------------------------ 検査
    def collide_surface(self, P, rad, skip_len=0.25):
        L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        sel = L > skip_len
        if not sel.any():
            return 0.0
        hgt, _ = self.sheet.height(P[sel])
        need = rad[sel] * 0.6 + 0.02
        return float(np.max(need - hgt)) if len(hgt) else 0.0

    def core_ok(self, tubes):
        """指の芯（背骨）が根元の帯（掌 0.5 m・指 0.3 m）より先で面の上にあるか。"""
        for t in tubes:
            P = t["P"]
            L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
            sel = L > (0.5 if t["kind"] == 0 else 0.3)
            if sel.any():
                hh, _ = self.sheet.height(P[sel])
                if float(hh.min()) < 0.0:
                    return False
        return True

    def collide_tubes(self, P, rad, hand_id):
        pool = [t for t in self.tubes + getattr(self, "proxies", []) if t["hand"] != hand_id]
        if not pool:
            return 0.0
        pts = np.concatenate([t["P"] for t in pool])
        rr = np.concatenate([t["rad"] for t in pool])
        tree = cKDTree(pts)
        worst = 0.0
        for p, r in zip(P, rad):
            idx = tree.query_ball_point(p, r + 0.5)
            if not idx:
                continue
            d = np.linalg.norm(pts[idx] - p, axis=1)
            v = 0.85 * (r + rr[idx]) - d
            worst = max(worst, float(v.max()))
        return worst

    # ------------------------------------------------------------ 手（掌＋指）
    def make_hand(self, hid, root_r, root_s, tier, rng, rot_extra=None, scale=1.0, up_tip=False, digits_override=None,
                  claw_dirs=None, lift=1.0):
        P_s, n, jf = self.F.at(root_r, root_s)
        T = self.T
        # 段ごとの向き：1 頂の縁（一部は上へ）、2 前の斜面、3 唇の縁・垂れる縁（垂れる）
        if tier == 1:
            elev = rng.normal(15.0, 10.0) if up_tip else rng.normal(-16.0, 12.0)
        elif tier == 2:
            elev = rng.normal(-25.0, 10.0)
        elif tier == 4:
            elev = rng.normal(-72.0, 8.0)
        else:
            elev = rng.normal(-55.0, 12.0)
        tgt = self.target_dir(n, elev)
        # 参照の彫刻の冠の根元の面は前・下を向き、指は法線から 22° で出る。主役波の頂の前は上を向くので、法線の角はそのままでは
        # 指が上を向く。向きの数（全体 24° 下・先 33° 下・先の 9 割が下）を先にし、法線からの角は目標へ必要なだけ（70° まで）倒す。
        theta = float(np.clip(GM.angle(n, tgt) + rng.normal(0.0, 6.0), 8.0, 70.0)) * lift
        d0 = self.initial_dir(n, tgt, theta)
        if rot_extra is not None:
            d0 = GM.nrm(rot_extra(d0, n))
        # 上・外を向く指は短い（S1：写真 N05 で上を向く先 15〜20% は、どれも頂の輪郭の短い指）
        Lh = lognorm(rng, T["hand_len_m"]["p50"], 0.18, 1.0, 2.3) * scale * (0.6 if up_tip else 1.0)
        fb = float(np.clip(rng.normal(T["branch_frac"]["p50"], 0.08), 0.32, 0.55))
        curl_h = float(np.clip(rng.normal(T["curl"]["hand"]["p50"], 15.0), 15.0, 80.0)) * (0.35 if up_tip else 1.0) * (0.5 + 0.5 * lift)
        # 根元：面の下（掌の半径の 0.9 倍）から法線の向きに面を抜け、面の 0.15 半径の上で手の向き d0 へ曲がる（茎）。
        # 接線に近い向きの掌を面の上から直に出すと、凸の頂で根元の端が面の上に出て「切った円柱」に見えた（試し rim2）。
        k, p = T["taper_hand"]["k"], T["taper_hand"]["p"]
        R0 = T["hand_r_base"] * rng.uniform(0.85, 1.12) * scale ** 0.5
        sink = 0.9 * R0
        P0 = P_s - n * sink
        P1 = P_s + n * (0.15 * R0)
        nst = 5
        stem = np.stack([P0 + (P1 - P0) * t for t in np.linspace(0, 1, nst)])
        # 茎の上で、法線から d0 へなめらかに曲がる弧（半径 ≈ R0）
        bend = []
        for t in np.linspace(0.2, 1.0, 4):
            dd = GM.nrm(GM.slerp(n, d0, t))
            bend.append(dd)
        pts = [P1]
        for dd in bend:
            pts.append(pts[-1] + dd * (0.6 * R0 / 4))
        Pb = np.array(pts[1:])
        Lpalm = fb * Lh + 0.18
        Pm, dirs_m = self.spine(Pb[-1], d0, Lpalm, curl_h * (Lpalm / Lh), n=max(10, int(Lpalm / 0.06)))
        Pp = np.concatenate([stem, Pb, Pm[1:]], 0)
        dirs = np.concatenate([np.repeat(n[None], nst, 0), np.array(bend), dirs_m[1:]], 0)
        Lc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
        fpal = np.clip((Lc - sink) / Lh, 0, None)
        rad = R0 * (1 - k * np.clip(fpal, 0, 1) ** p)
        flare = 1 + 0.20 * (1 - G.sm(np.clip((Lc - sink) / 0.18, 0, 1)))
        rad = rad * flare
        side = GM.nrm(self.ecrest - (self.ecrest @ d0) * d0)
        asp = np.full(len(Pp), 1.45)
        tubes = [dict(kind=0, hand=hid, P=Pp, rad=rad, aspect=asp, side=side, tip="round", nseg=16, f0=0.0, f1=Lpalm / Lh)]
        # 指
        ib = int(np.searchsorted(Lc, fb * Lh + sink + 0.6 * R0))
        ib = min(max(ib, 1), len(Pp) - 2)
        pb = Pp[ib]
        db = dirs[ib]
        nd = digits_override if digits_override is not None else int(rng.choice([2, 3, 4, 5], p=[0.30, 0.45, 0.20, 0.05]))
        spread = T["angle_between_digits"]["p50"] * rng.uniform(0.75, 1.2)
        offs = (np.arange(nd) - (nd - 1) / 2.0) * spread if nd > 1 else np.zeros(1)
        offs = offs + rng.normal(0, 5.0, nd)
        palm_n = GM.nrm(np.cross(db, side))            # 掌の面の法線（指は掌の面の中で扇に開く）
        r_at_b = rad[ib]
        for di in range(nd):
            dd = GM.rot(db, palm_n, offs[di] * D)
            dd = GM.rot(dd, side, rng.normal(0, 8.0) * D)
            if claw_dirs is not None and di < len(claw_dirs):
                continue
            Ld = lognorm(rng, T["digit_len_m"]["p50"], 0.30, 0.45, 1.45) * scale * (0.6 if up_tip else 1.0)
            curl_d = float(np.clip(rng.normal(T["curl"]["digit"]["p50"], 10.0), 4.0, 45.0)) * (0.3 if up_tip else 1.0) * (0.5 + 0.5 * lift)
            start = pb - db * 0.10
            Pd, _ = self.spine(start, dd, Ld + 0.10, curl_d, n=max(10, int((Ld + 0.1) / 0.05)))
            Ld_c = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pd, axis=0), axis=1))]
            fd = Ld_c / Ld_c[-1]
            kd, pd = T["taper_digit"]["k"], T["taper_digit"]["p"]
            rb = min(T["digit_r_base"] * rng.uniform(1.0, 1.2) * scale ** 0.5, 0.95 * r_at_b)
            # 細り：S1 の径の p50（根元 0.448・中 0.332・先 0.214 m、先／根元 0.48）に合わせ k = 0.52（S1 の式 k 0.64 は先 0.36 で、先が細く尖って見えた）
            radd = rb * (1 - 0.52 * fd ** pd)
            tip = rng.choice(["round", "open", "bulb"], p=[0.90, 0.05, 0.05])
            tubes.append(dict(kind=1, hand=hid, P=Pd, rad=radd, aspect=np.ones(len(Pd)), side=side, tip=str(tip), nseg=12,
                              f0=fb, f1=1.0))
        info = dict(id=hid, tier=tier, root_r=round(float(root_r), 3), root_s=round(float(root_s), 3), root_col=round(float(jf), 2),
                    root_xyz=[round(float(v), 3) for v in P_s], normal=[round(float(v), 3) for v in n], theta_deg=round(theta, 1),
                    elev_target_deg=round(float(elev), 1), hand_len_m=round(Lh, 3), branch_frac=round(fb, 3), curl_hand_deg=round(curl_h, 1),
                    digits=nd, up_tip=bool(up_tip), scale=round(scale, 3))
        return tubes, info

    def accept_hand(self, hid, root_r, root_s, tier, up_tip=False, max_try=8, digits=None):
        rng_state = self.rng.bit_generator.state
        best = None
        for k in range(max_try):
            rng = np.random.default_rng(self.seed * 1000 + hid * 17 + (k % 2))
            scale = 1.0 if k < 4 else 0.85 ** (k - 3)
            lift = [1.0, 1.0, 0.7, 0.45, 0.45, 0.3, 0.3, 0.2][min(k, 7)]      # 面に当たる時は根元の向きを法線へ寄せ、垂れを弱める
            tubes, info = self.make_hand(hid, root_r, root_s, tier, rng, scale=scale, up_tip=up_tip, lift=lift, digits_override=digits)
            worst_s = max(self.collide_surface(t["P"], t["rad"], skip_len=0.65 if t["kind"] == 0 else 0.30) for t in tubes)
            worst_t = max(self.collide_tubes(t["P"], t["rad"], hid) for t in tubes)
            if worst_s <= 0.0 and worst_t <= 0.0 and self.core_ok(tubes):
                info["tries"] = k + 1
                self.tubes.extend(tubes)
                self.hands.append(info)
                return True
            if best is None or (worst_s + worst_t) < best[0]:
                best = (worst_s + worst_t, worst_s, worst_t)
        self.dropped.append(dict(id=hid, tier=tier, root_r=root_r, root_s=root_s, why_ja="面を突き抜ける（%.2f m）か別の手と重なる（%.2f m）" % (best[1], best[2])))
        self.rng.bit_generator.state = rng_state
        return False

    # ------------------------------------------------------------ 根元の場所
    def root_candidates(self, tier):
        """段 1＝頂の縁（頂から s 0.2〜2.2 m）、段 2＝前の上の斜面（2.2〜5.0 m）、段 3＝垂れる縁（白の境の 0.4〜1.6 m 上。白が唇を
        回り込む行は唇の縁＝列 185〜205）。彫刻の冠は頂の線の前の 0〜0.32 H（2〜3 段、最前列は縁から垂れる）。主役波の唇は彫刻より長いので、
        唇の中ほどの白い斜面（冠の泡の塊）には根元を置かず、頂の縁と縁（唇の先・白の境）へ集める。"""
        h, M = self.h, self.M
        out = []
        for r in range(69, 228):
            crest_y = h.X[r, h.top_col[r], 1]
            if crest_y < 0.30 * h.H0:
                continue
            sb = M.sb[r]
            s200 = M.s[r, 200]
            if tier == 1:
                lo, hi = 0.2, min(2.2, sb - 0.5)
            elif tier == 2:
                lo, hi = 2.2, min(5.0, sb - 0.8)
            else:
                if sb <= s200 + 0.2:          # 白の境が唇の先より手前（主の藍の面の上の縁・右の端）
                    lo, hi = max(1.5, sb - 1.6), sb - 0.4
                else:                          # 白が唇の先を回り込む行は利用者の爪が受け持つ
                    continue
            if hi <= lo:
                continue
            for sv in np.arange(lo, hi + 1e-6, 0.2):
                out.append((r, float(sv)))
        return out

    def place(self, n_hands):
        """段 1（頂の縁）：頂の線に沿って、ほぼ等しい間隔（ゆらぎ ±0.35 間隔）で並べ、根元は頂から 0.3〜1.3 m 前（冠の縁の房の列）。
        段 3（垂れる縁）：白の境が唇の先より手前の行（主の藍の面の上の縁・右の端）の、白の境の上に置く。唇の白い斜面は利用者の爪（冠の指の先）が受け持つ。"""
        h = self.h
        n3 = max(3, int(round(n_hands * 0.2)))
        nl = int(getattr(self, "lip_hands", 0))
        n1 = n_hands - n3 - nl
        hid = 1000
        roots_xyz = [np.array(u["root"]) for u in self.user]
        rows = [r for r in range(69, 228) if h.X[r, h.top_col[r], 1] >= 0.30 * h.H0]
        P = np.stack([h.X[r, h.top_col[r]] for r in rows])
        Lr = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        gap = Lr[-1] / n1
        got1 = 0
        for k in range(n1):
            for attempt in range(4):
                Lk = (k + 0.5) * gap + self.rng.uniform(-0.35, 0.35) * gap
                rf = float(np.interp(np.clip(Lk, 0, Lr[-1]), Lr, rows))
                sv = float(self.rng.uniform(0.3, 1.3))
                Pk, n, jf = self.F.at(rf, sv)
                if roots_xyz and min(np.linalg.norm(Pk - q) for q in roots_xyz) < 1.0:
                    continue
                up_tip = self.rng.random() < 0.20
                nd = int(self.rng.choice(self.rim_digits[0], p=self.rim_digits[1])) if self.rim_digits else None
                ok = self.accept_hand(hid, rf, sv, 1, up_tip=up_tip, digits=nd)
                hid += 1
                if ok:
                    roots_xyz.append(Pk)
                    got1 += 1
                    break
        cand = self.root_candidates(3)
        order = self.rng.permutation(len(cand))
        got3 = 0
        for oi in order:
            if got3 >= n3:
                break
            r, sv = cand[oi]
            Pk, n, jf = self.F.at(r, sv)
            if roots_xyz and min(np.linalg.norm(Pk - q) for q in roots_xyz) < 1.6:
                continue
            ok = self.accept_hand(hid, float(r), sv, 3)
            hid += 1
            if ok:
                roots_xyz.append(Pk)
                got3 += 1
        self.log.append("tier 1 (rim garland): %d / %d hands, spacing %.2f m along the rim %.1f m" % (got1, n1, gap, Lr[-1]))
        self.log.append("tier 3 (drip edge): %d / %d hands (candidates %d)" % (got3, n3, len(cand)))
        # 段 3 の唇の縁（彫刻：最前列は唇の縁から垂れる）：白が唇の先を回り込む行で、唇の先（列 200）の −0.5〜+1.0 m に、ほぼ等しい間隔で垂れる手
        if nl > 0:
            M = self.M
            rows_l = [r for r in range(69, 228) if M.sb[r] > M.s[r, 200] + 0.2 and h.X[r, h.top_col[r], 1] >= 0.30 * h.H0]
            if rows_l:
                Pl = np.stack([self.F.at(float(r), float(M.s[r, 200]))[0] for r in rows_l])
                Ll = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pl, axis=0), axis=1))]
                gapl = Ll[-1] / nl
                gotl = 0
                for k in range(nl):
                    for attempt in range(5):
                        Lk = (k + 0.5) * gapl + self.rng.uniform(-0.3, 0.3) * gapl
                        rf = float(np.interp(np.clip(Lk, 0, Ll[-1]), Ll, rows_l))
                        ri = int(round(rf))
                        sv = float(M.s[ri, 200] + self.rng.uniform(-0.5, 1.0))
                        Pk, n, jf = self.F.at(rf, sv)
                        if roots_xyz and min(np.linalg.norm(Pk - q) for q in roots_xyz) < 0.9:
                            continue
                        ok = self.accept_hand(hid, rf, sv, 4)
                        hid += 1
                        if ok:
                            roots_xyz.append(Pk)
                            gotl += 1
                            break
                self.log.append("tier 4 (lip edge, hanging): %d / %d hands, spacing %.2f m along the lip tip line %.1f m" % (gotl, nl, gapl, Ll[-1]))

    # ------------------------------------------------------------ 利用者の爪（CREST_CROWN）
    def load_user(self):
        lay = G.jload(G.CLAWD + "/ds33_claw_layout.json")
        V = np.fromfile(G.CLAWD + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3).astype(np.float64)
        Tr = np.fromfile(G.CLAWD + "/ds33_claw_tris_i32.bin", np.int32).reshape(-1, 3)
        roles = G.jload(G.ROLES)["claws"]
        by_uid = {c["user_id"]: c for c in lay["claws"]}
        tri_owner = np.searchsorted(np.array([c["vert_offset"] for c in lay["claws"]]), Tr[:, 0], side="right") - 1
        out = []
        for ro in roles:
            if ro["role"] != "CREST_CROWN":
                continue
            c = by_uid[ro["id"]]
            o, nvc, st = c["vert_offset"], c["vert_count"], c["stations"]
            Vc = V[o:o + nvc].copy()
            Fc = Tr[tri_owner == c["index"]] - o
            rings = Vc[1:1 + 8 * st].reshape(st, 8, 3)
            spine = np.concatenate([Vc[:1], rings.mean(1), Vc[1 + 8 * st:2 + 8 * st]], 0)
            out.append(dict(id=ro["id"], layout_id=c["id"], part=ro["crown_part"], V=Vc, F=Fc, spine=spine, stations=st,
                            root=Vc[0].copy(), tip=spine[-1].copy(), sugg=np.array(ro["finger_direction"]["suggest_vec_world"]),
                            width=np.linalg.norm(rings[:, 0] - rings[:, 4], axis=1)))
        return out, dict(layout_sha256=G.sha(G.CLAWD + "/ds33_claw_layout.json"), frames_sha256=G.sha(G.CLAWD + "/ds33_claw_frames_f32.bin"),
                         roles_sha256=G.sha(G.ROLES))

    def place_user(self):
        users, src = self.load_user()
        self.user_src = src
        # 根元が 0.9 m より近い爪を 1 つの手（房）にまとめる（S2：原画の爪の房 2〜4 本が彫刻の 1 本の手に当たる読み）
        R0 = np.stack([u["root"] for u in users])
        lab = np.arange(len(users))
        for i in range(len(users)):
            for j in range(i + 1, len(users)):
                if np.linalg.norm(R0[i] - R0[j]) < 0.9:
                    a_, b_ = lab[i], lab[j]
                    lab[lab == b_] = a_
        uniq = {v: k + 1 for k, v in enumerate(sorted(set(lab.tolist())))}
        self.proxies = []
        for ui, u in enumerate(users):
            hid = uniq[int(lab[ui])]
            Pn, Nn, rcn, dn = self.sheet.nearest(u["root"][None])
            n = GM.nrm(Nn[0])
            sp = u["spine"]
            Lsp = np.r_[0, np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))]
            kb = int(np.searchsorted(Lsp, min(0.25, 0.3 * Lsp[-1])))
            b0 = GM.nrm(sp[kb] - sp[0])
            ang0 = GM.angle(b0, n)
            Rm = np.eye(3)
            if self.mode == "OUT":
                elev = {"lip": -40.0, "crest_top": -20.0, "b_crest": -30.0}.get(u["part"], -30.0)
                best = None
                rng = np.random.default_rng(self.seed * 7 + ui)
                tgt = self.target_dir(n, elev)
                theta0 = float(np.clip(GM.angle(n, tgt) * rng.uniform(0.75, 1.0), 12.0, 70.0))
                for theta in (theta0, theta0 * 0.7, theta0 * 0.45, theta0 * 0.25, theta0 * 0.1):
                    d0 = self.initial_dir(n, tgt, theta)
                    # b0 → d0 の最小の回転、その後 d0 の周りのねじり（先が下・前へ垂れ、面に当たらない角を選ぶ）
                    ax = np.cross(b0, d0)
                    if np.linalg.norm(ax) < 1e-9:
                        R1 = np.eye(3)
                    else:
                        a1 = math.acos(float(np.clip(b0 @ d0, -1, 1)))
                        R1 = rotmat(ax, a1)
                    for psi in np.radians(np.arange(0, 360, 15)):
                        R = rotmat(d0, psi) @ R1
                        spt = (sp - u["root"]) @ R.T + u["root"]
                        chord = GM.nrm(spt[-1] - spt[0])
                        hgt, _ = self.sheet.height(spt[Lsp > 0.15])
                        pen = float(np.max(0.10 - hgt)) if len(hgt) else 0.0
                        score = (chord @ DOWN) * 1.0 + (chord @ self.fwd_dir(n)) * 0.6 - 30.0 * max(pen, 0.0)
                        if best is None or score > best[0]:
                            best = (score, R, pen)
                    if best[2] <= 0.0:
                        break
                Rm = best[1]
            Vt = (u["V"] - u["root"]) @ Rm.T + u["root"]
            spt = (sp - u["root"]) @ Rm.T + u["root"]
            b1 = GM.nrm(spt[kb] - spt[0])
            hgt, _ = self.sheet.height(spt[Lsp > 0.2])
            u.update(Vw=Vt, spine_w=spt, R=Rm, angle_normal_before=round(ang0, 1), angle_normal_after=round(GM.angle(b1, n), 1),
                     surface_pen_m=round(float(np.max(-hgt)) if len(hgt) else 0.0, 3), normal=n, hand=hid)
            # 爪の根元の側を包む太い袖（指の体）：爪の背骨に沿って、爪の長さの 45% まで。半径は根元 0.20 m から、爪の半幅の 0.75 倍へ
            # なめらかに細る（爪は太い指の先が細って鉤になった形に読める。円錐の台にしない）。根元は面の下 0.10 m から。
            Lt = Lsp[-1]
            kk = Lsp <= 0.50 * Lt
            sp_s = spt[kk]
            if len(sp_s) >= 3:
                P0 = u["root"] - n * 0.10
                Pp = np.concatenate([P0[None], sp_s], 0)
                Lc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
                hw = 0.5 * np.r_[u["width"][:1], u["width"]][:len(sp_s)]
                hw = np.r_[hw[:1], hw]
                tt = G.sm(np.clip(Lc / max(Lc[-1], 1e-6), 0, 1))
                rad = 0.24 * (1 - tt) + 0.75 * hw * tt
                side = GM.nrm(self.ecrest - (self.ecrest @ b1) * b1)
                self.tubes.append(dict(kind=0, hand=hid, P=Pp, rad=rad, aspect=np.full(len(Pp), 1.25), side=side, tip="round", nseg=14,
                                       f0=0.0, f1=0.50, user=u["id"]))
            # 当たりの検査の代わりの背骨（利用者の爪そのもの）
            wr = 0.5 * np.r_[u["width"][:1], u["width"], u["width"][-1:]][:len(spt)] * 0.8
            self.proxies.append(dict(hand=hid, P=spt, rad=wr))
            ex = next((x for x in self.hands if x["id"] == hid), None)
            if ex is None:
                self.hands.append(dict(id=hid, tier=0, user_claws=[u["id"]], part=u["part"], root_xyz=[round(float(v), 3) for v in u["root"]],
                                       normal=[round(float(v), 3) for v in n], digits=1))
            else:
                ex["user_claws"].append(u["id"])
                ex["digits"] += 1
            self.user.append(u)

    def place_user_palms(self):
        """利用者の爪の房ごとに、房の後ろ（頂の側）0.8 m から房へ向かう掌を置く（爪はこの手の指＝冠の指の先になる）。
        掌の太さ・細り・平たさは S1 の手の数。房の 5 割には手続きの指を 1 本足す。"""
        T = self.T
        by = {}
        for u in self.user:
            by.setdefault(u["hand"], []).append(u)
        n_ok = 0
        for hid, us in sorted(by.items()):
            C = np.mean([u["root"] for u in us], 0)
            Pn, Nn, _, _ = self.sheet.nearest(C[None])
            n = GM.nrm(Nn[0])
            bbar = GM.nrm(np.mean([GM.nrm(u["spine_w"][min(6, len(u["spine_w"]) - 1)] - u["spine_w"][0]) for u in us], 0))
            tdir = bbar - (bbar @ n) * n
            if np.linalg.norm(tdir) < 1e-6:
                tdir = self.fwd_dir(n) - (self.fwd_dir(n) @ n) * n
            tdir = GM.nrm(tdir)
            rng = np.random.default_rng(self.seed * 31 + hid)
            ok = False
            for back in (0.8, 0.55, 0.35):
                Pr0 = C - tdir * back
                Pr, Nr, _, _ = self.sheet.nearest(Pr0[None])
                Pr, nr = Pr[0], GM.nrm(Nr[0])
                tgt = C + n * 0.30
                L = float(np.linalg.norm(tgt - Pr)) + 0.25
                d0 = GM.nrm(tgt - Pr)
                sink = 0.10
                P0 = Pr - nr * sink
                npt = max(10, int((L + sink) / 0.06))
                Pp = np.stack([P0 + d0 * (L + sink) * t for t in np.linspace(0, 1, npt)])
                Lc = np.linspace(0, L + sink, npt)
                R0 = T["hand_r_base"] * rng.uniform(0.85, 1.05)
                k, pp = T["taper_hand"]["k"], T["taper_hand"]["p"]
                rad = R0 * (1 - 0.55 * np.clip(Lc / (L + sink), 0, 1) ** pp)
                side = GM.nrm(self.ecrest - (self.ecrest @ d0) * d0)
                tub = [dict(kind=0, hand=hid, P=Pp, rad=rad, aspect=np.full(npt, 1.6), side=side, tip="round", nseg=16, f0=0.0, f1=0.42)]
                if rng.random() < 0.5:
                    dd = GM.rot(d0, nr, rng.choice([-1, 1]) * rng.uniform(25, 50) * D)
                    Ld = lognorm(rng, T["digit_len_m"]["p50"], 0.30, 0.45, 1.3)
                    Pd, _ = self.spine(Pp[-3] - d0 * 0.05, dd, Ld, float(np.clip(rng.normal(T["curl"]["digit"]["p50"] + 10, 8), 5, 45)), n=max(10, int(Ld / 0.05)))
                    fd = np.linspace(0, 1, len(Pd))
                    rb = min(T["digit_r_base"] * rng.uniform(0.85, 1.1), 0.8 * rad[-3])
                    tub.append(dict(kind=1, hand=hid, P=Pd, rad=rb * (1 - T["taper_digit"]["k"] * fd ** T["taper_digit"]["p"]), aspect=np.ones(len(Pd)),
                                     side=side, tip=str(rng.choice(["round", "open", "bulb"], p=[0.9, 0.05, 0.05])), nseg=12, f0=0.42, f1=1.0))
                ws = max(self.collide_surface(t["P"], t["rad"], skip_len=0.65 if t["kind"] == 0 else 0.30) for t in tub)
                wt = max(self.collide_tubes(t["P"], t["rad"], hid) for t in tub)
                Lq = np.r_[0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
                hq, _ = self.sheet.height(Pp[Lq > 0.5]) if (Lq > 0.5).any() else (np.array([1.0]), None)
                if ws <= 0.05 and wt <= 0.0 and float(hq.min()) > 0.0:
                    ok = True
                    break
            if ok:
                self.tubes.extend(tub)
                ex = next(x for x in self.hands if x["id"] == hid)
                ex.update(palm_len_m=round(L, 3), palm_r_base_m=round(float(R0), 3), extra_digits=len(tub) - 1,
                          theta_deg=round(GM.angle(d0, nr), 1))
                ex["digits"] += len(tub) - 1
                n_ok += 1
        self.log.append("user-claw palms: %d / %d clusters" % (n_ok, len(by)))

    def place_band(self):
        """冠の泡の帯（彫刻の冠の「太く続く白い泡の帯」を、主役波の頂の前に自分で設計した形）：頂の前の 2 列（s ≈ 0.8 m・2.1 m）に、
        3〜7 m の切れの平たいでこぼこの管を、すき間（0.6〜2 m）をあけて並べる。断面は幅／厚み 2.0、半径 0.30〜0.45 m のでこぼこ、
        中心は面から半径の 0.15 倍だけ上（6 割ほど面に沈む低い畝）。指・手はこの帯の上と前から出る。"""
        h, M = self.h, self.M
        rng = np.random.default_rng(self.seed * 13 + 5)
        rows = [r for r in range(69, 228) if h.X[r, h.top_col[r], 1] >= 0.30 * h.H0]
        bands = []
        bid = 2000
        for lane_s, lane in ((0.8, 0), (2.1, 1)):
            r = rows[0] + int(rng.integers(0, 8))
            while r < rows[-1] - 5:
                nseg_rows = int(rng.integers(15, 36))
                rs = [rr for rr in range(r, min(r + nseg_rows, rows[-1]))]
                pts, nrs, rads = [], [], []
                ph1, ph2 = rng.uniform(0, 2 * np.pi, 2)
                per1, per2 = rng.uniform(1.0, 1.6), rng.uniform(2.2, 3.4)
                r0 = rng.uniform(0.30, 0.40) if lane == 0 else rng.uniform(0.26, 0.36)
                for k, rr in enumerate(rs):
                    sl = lane_s + 0.25 * math.sin(k * 0.2 * 2 * np.pi / 3.0 + ph1)
                    if sl > M.sb[rr] - 0.5:
                        break
                    P, n, _ = self.F.at(float(rr), sl)
                    rad = r0 * (1 + 0.22 * math.sin(k * 0.2 * 2 * np.pi / per1 + ph1) + 0.12 * math.sin(k * 0.2 * 2 * np.pi / per2 + ph2))
                    pts.append(P + n * 0.15 * rad)
                    nrs.append(n)
                    rads.append(rad)
                if len(pts) >= 8:
                    Pp = np.array(pts)
                    rad = np.array(rads)
                    # 両端を細らせて丸く閉じる
                    m = len(rad)
                    e = np.minimum(np.arange(m), np.arange(m)[::-1]) / 3.0
                    rad = rad * (0.45 + 0.55 * G.sm(np.clip(e, 0, 1)))
                    nmean = GM.nrm(np.mean(nrs, 0))
                    dir_band = GM.nrm(Pp[-1] - Pp[0])
                    side = GM.nrm(np.cross(nmean, dir_band))
                    bands.append(dict(kind=0, hand=bid, P=Pp, rad=rad, aspect=np.full(m, 2.0), side=side, tip="round", nseg=16, f0=0.0, f1=0.25,
                                      band=lane))
                    bid += 1
                r += nseg_rows + int(rng.integers(3, 10))
        self.bands = bands
        self.log.append("foam band ropes: %d (lanes 0/1: %d/%d)" % (len(bands), sum(1 for b in bands if b["band"] == 0), sum(1 for b in bands if b["band"] == 1)))

    # ------------------------------------------------------------ IN：原画の視点の制約
    def painting_masks(self):
        cam = G.painting_cam(1920, 1080)
        h = self.h
        g = G.read_gwb(G.SEA_NEAR)
        tri_h = h.V[h.Tg]
        tri_s = g["X"][g["tris"].astype(np.int64)]
        idb, zb = G.U.raster(cam, np.concatenate([tri_h, tri_s]), np.arange(1, len(h.Tg) + len(tri_s) + 1))
        # 原画の区域（S2 の原画の画素）を表示の画素へ
        z = np.load(WM.S2Z)
        cl = np.load(WM.S2C)
        A = G.U.A_DISP
        offx = 156.66152659984573
        QH, QW = z["face"].shape
        allowed_q = (z["z_crest_top"] | z["z_lip"] | z["z_b_crest"] | z["big_white"]).astype(np.uint8)
        sky_q = cl["sky"].astype(np.uint8)
        xs = (np.arange(1920) + 0.5 - offx) / A - 0.5
        ys = (np.arange(1080) + 0.5) / A - 0.5
        mx, my = np.meshgrid(xs.astype(np.float32), ys.astype(np.float32))
        allowed = cv2.remap(allowed_q * 255, mx, my, cv2.INTER_LINEAR, borderValue=0) > 127
        sky = cv2.remap(sky_q * 255, mx, my, cv2.INTER_LINEAR, borderValue=255) > 127
        # 表示の範囲の外（原画の切り出しの外）は空とみなさない（原画の右の外は x > QW）
        k = np.ones((5, 5), np.uint8)
        sky_in = cv2.erode(sky.astype(np.uint8), k) > 0          # 2 px より内の空
        allowed_d = cv2.dilate(allowed.astype(np.uint8), k) > 0
        self.pm = dict(cam=cam, zb=zb, idb=idb, sky_in=sky_in, allowed=allowed_d, sky=sky, allowed_raw=allowed)
        return self.pm

    def outside_px(self, V):
        pm = self.pm
        cam = pm["cam"]
        q, z = cam.project(V)
        x = np.rint(q[:, 0]).astype(int)
        y = np.rint(q[:, 1]).astype(int)
        ok = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080) & (z > 0.1)
        x, y, z = x[ok], y[ok], z[ok]
        hz = pm["zb"][y, x]
        hidden = (hz > 0) & (1.0 / np.maximum(hz, 1e-9) < z - 0.05)
        bad = pm["sky_in"][y, x] | (~hidden & ~pm["allowed"][y, x])
        return int(bad.sum()), int(len(x))

    def constrain_in(self):
        """手ごとに：その手の管の頂点が原画の空・白の区域の外に出るなら、①奥（射線の向き）へ回す ②0.85 倍、を 4 回まで。残れば外す。"""
        self.painting_masks()
        cam = self.pm["cam"]
        stats = dict(ok_first=0, fixed=0, dropped=0, user_bodies_dropped=0)
        new_tubes = []
        by_hand = {}
        for t in self.tubes:
            by_hand.setdefault(t["hand"], []).append(t)
        for hid, tl in by_hand.items():
            V = np.concatenate([t["P"] for t in tl])
            rr = np.concatenate([t["rad"] for t in tl])
            # 管の表面の代わりに、背骨の点と、背骨から 4 方向に半径だけ離れた点で測る
            Vs = surface_probe(tl)
            bad, nv = self.outside_px(Vs)
            if bad == 0:
                stats["ok_first"] += 1
                new_tubes.extend(tl)
                continue
            info = next((x for x in self.hands if x["id"] == hid), None)
            if hid >= 2000:            # 泡の帯：回さずに外す
                stats["dropped"] += 1
                stats["bands_dropped"] = stats.get("bands_dropped", 0) + 1
                self.dropped.append(dict(id=hid, why_ja="IN：泡の帯の切れが原画の視点で空か白の区域の外に出る", bad_vertices=bad))
                continue
            root = tl[0]["P"][0]
            ray = GM.nrm(root - cam.pos)
            fixed = False
            cur = tl
            k = -1
            is_user = any("user" in t for t in tl)
            if is_user:
                # 利用者の爪の房：①掌を外して袖だけ ②袖の根元を細く（爪の半幅へ）。爪そのものは見本02 の置き方 A のまま残す
                trials = [[t for t in tl if "user" in t],
                          [dict(t, rad=np.minimum(t["rad"], np.maximum(0.6 * t["rad"], t["rad"][-1]))) for t in tl if "user" in t]]
                for k, cur2 in enumerate(trials):
                    if not cur2:
                        continue
                    bad2, _ = self.outside_px(surface_probe(cur2))
                    if bad2 == 0:
                        cur, fixed = cur2, True
                        break
            else:
                # 手続きの手：①射線の向き（奥）へ 25° ずつ ②頂の後ろ・下へ 35° ずつ、どちらも 0.9 倍に縮めながら 4 回まで
                Pn0, Nn0, _, _ = self.sheet.nearest(root[None])
                fwd0 = self.fwd_dir(GM.nrm(Nn0[0]))
                behind = GM.nrm(-fwd0 - 0.6 * GM.UP)
                toward = GM.nrm(-ray * 0.8 + DOWN * 0.45)
                for mode_i, (tgt, step) in enumerate(((toward, 30.0), (ray, 25.0), (behind, 35.0))):
                    cur = tl
                    for kk in range(4):
                        cur2 = []
                        for t in cur:
                            P = t["P"]
                            d0 = GM.nrm(P[min(3, len(P) - 1)] - P[0])
                            ax = np.cross(d0, tgt)
                            ang = min(GM.angle(d0, tgt), step) * D
                            R = rotmat(ax, ang) if np.linalg.norm(ax) > 1e-9 else np.eye(3)
                            Pn = (P - root) @ R.T + root
                            Pn = root + (Pn - root) * 0.9
                            cur2.append(dict(t, P=Pn, rad=t["rad"] * 0.95))
                        hit_s = max(self.collide_surface(t["P"], t["rad"], skip_len=0.65 if t["kind"] == 0 else 0.30) for t in cur2)
                        bad2, _ = self.outside_px(surface_probe(cur2))
                        cur = cur2
                        k = mode_i * 4 + kk
                        if bad2 == 0 and hit_s <= 0.05 and self.core_ok(cur2) and max(self.collide_tubes(t["P"], t["rad"], hid) for t in cur2) <= 0.0:
                            fixed = True
                            break
                    if fixed:
                        break
                if not fixed and info is not None and "root_s" in info:
                    # ③ 同じ行のもっと前（s + 1.5 m・+3.0 m）に根元を移し、射線の奥の向き（法線へ 30° 寄せる）に立て直す
                    for ds_ in (-1.5, 1.5, -3.0, 3.0):
                        snew = info["root_s"] + ds_
                        if snew < 0.3 or snew > self.M.sb[int(round(info["root_r"]))] - 0.4:
                            continue
                        Pn1, n1, _ = self.F.at(info["root_r"], snew)
                        ray1 = GM.nrm(Pn1 - cam.pos)
                        dnew = GM.nrm(GM.slerp(-ray1, n1, 0.35))
                        cur2 = []
                        for t in tl:
                            P = t["P"]
                            d0 = GM.nrm(P[min(3, len(P) - 1)] - P[0])
                            ax = np.cross(d0, dnew)
                            ang = GM.angle(d0, dnew) * D
                            R = rotmat(ax, ang) if np.linalg.norm(ax) > 1e-9 else np.eye(3)
                            Pn = (P - root) @ R.T + root
                            Pn = Pn - root + (Pn1 - n1 * 0.10)
                            cur2.append(dict(t, P=Pn, rad=t["rad"] * 0.95))
                        hit_s = max(self.collide_surface(t["P"], t["rad"], skip_len=0.65 if t["kind"] == 0 else 0.30) for t in cur2)
                        wt = max(self.collide_tubes(t["P"], t["rad"], hid) for t in cur2)
                        bad2, _ = self.outside_px(surface_probe(cur2))
                        if bad2 == 0 and hit_s <= 0.05 and wt <= 0.0 and self.core_ok(cur2):
                            cur, fixed, k = cur2, True, 12
                            info["in_reroot_ds_m"] = ds_
                            break
            if fixed:
                stats["fixed"] += 1
                new_tubes.extend(cur)
                if info is not None:
                    info["in_fix_steps"] = k + 1
            else:
                stats["dropped"] += 1
                if info is not None:
                    info["in_dropped"] = True
                if any("user" in t for t in tl):
                    stats["user_bodies_dropped"] += 1
                self.dropped.append(dict(id=hid, why_ja="IN：原画の視点で空か白の区域の外に出る（射線の向き・頂の後ろへ回し、縮めても残る。利用者の房は掌・袖を外し、爪だけ残す）", bad_vertices=bad))
        self.tubes = new_tubes
        self.hands = [x for x in self.hands if not x.get("in_dropped")]
        # 利用者の爪そのもの（見本02 の置き方 A のまま）の外の頂点も数える（記録だけ）
        ub = [self.outside_px(u["Vw"])[0] for u in self.user]
        stats["user_claw_outside_vertices_total"] = int(sum(ub))
        stats["user_claws_with_outside"] = int(sum(1 for b in ub if b > 0))
        return stats

    # ------------------------------------------------------------ メッシュと属性
    def build_mesh(self):
        Vs, Fs, attrs = [], [], []
        off = 0
        fid = 0
        spine_pts, spine_r = [], []
        presetN = []
        smooth_ids = set()
        if getattr(self, "smooth_hands", False):
            # 手続きの手（掌＋指）を、距離の場のなめらかな和で 1 つの面にする（股に丸み）。利用者の袖と爪は管のまま
            by = {}
            for t in self.tubes:
                if t["hand"] >= 1000 and t["hand"] < 2000:
                    by.setdefault(t["hand"], []).append(t)
            for hid, tl in by.items():
                res = GM.hand_sdf_mesh(tl, vox=self.smooth_vox, k=self.smooth_k)
                if res is None:
                    continue
                V, F, Nn, own, fr, chains = res
                f0 = np.array([tl[i]["f0"] for i in own])
                f1 = np.array([tl[i]["f1"] for i in own])
                kind = np.array([tl[i]["kind"] for i in own])
                ff = f0 + (f1 - f0) * fr
                fids = fid + own
                for ti, t in enumerate(tl):
                    t["fid"] = fid + ti
                # AO・光の見通しの距離の場は、面を作った鎖（掌は横へずらした 2 本）と同じにする（中心の背骨と半径 r では平たい掌の面が「中」になり AO が 0 になった）
                for (Q, rr) in chains:
                    spine_pts.append(Q)
                    spine_r.append(rr)
                Vs.append(V)
                Fs.append(F + off)
                attrs.append(np.stack([ff, fids, kind, np.zeros(len(V))], -1))
                presetN.append((off, off + len(V), Nn))
                off += len(V)
                fid += len(tl)
                smooth_ids.add(hid)
        for t in self.tubes:
            if t["hand"] in smooth_ids:
                continue
            P, nsamp = t["P"], len(t["P"])
            # 輪の間隔 0.05 m を目安に背骨を細かくする
            L = np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1))
            n2 = max(8, int(L / 0.05) + 1)
            P2, _ = GM.resample(P, n2)
            Lo = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
            Ln = np.linspace(0, Lo[-1], n2)
            r2 = np.interp(Ln, Lo, t["rad"])
            a2 = np.interp(Ln, Lo, t["aspect"])
            V, F, fv, rid = GM.tube(P2, r2, t["nseg"], aspect=a2, side_hint=t["side"], tip=t["tip"])
            F = GM.orient_outward(V, F, P2)
            ff = t["f0"] + (t["f1"] - t["f0"]) * fv
            Vs.append(V)
            Fs.append(F + off)
            attrs.append(np.stack([ff, np.full(len(V), fid), np.full(len(V), t["kind"]), np.zeros(len(V))], -1))
            t["fid"] = fid
            spine_pts.append(P2)
            spine_r.append(r2)
            off += len(V)
            fid += 1
        for u in self.user:
            V = u["Vw"]
            F = u["F"]
            Lsp = np.r_[0, np.cumsum(np.linalg.norm(np.diff(u["spine_w"], axis=0), axis=1))]
            # 頂点の f：最も近い背骨の点の道のりの割合（掌の 0.3 から先 1.0 へ）
            tr = cKDTree(u["spine_w"])
            _, j = tr.query(V)
            fv = 0.3 + 0.7 * Lsp[j] / max(Lsp[-1], 1e-9)
            Vs.append(V)
            Fs.append(F + off)
            attrs.append(np.stack([fv, np.full(len(V), fid), np.full(len(V), 2), np.zeros(len(V))], -1))
            u["fid"] = fid
            spine_pts.append(u["spine_w"])
            spine_r.append(np.interp(Lsp, Lsp, 0.5 * np.r_[u["width"][:1], u["width"], u["width"][-1:]][:len(Lsp)]))
            off += len(V)
            fid += 1
        V = np.concatenate(Vs)
        F = np.concatenate(Fs).astype(np.int64)
        A3 = np.concatenate(attrs)
        N = GM.vertex_normals(V, F)
        for (a0, a1, Nn) in presetN:
            N[a0:a1] = Nn
        # 根元：面から 0.15 m までの頂点の法線を面の法線へなめらかに移す
        hgt, _ = self.sheet.height(V)
        Pn, Nn, _, _ = self.sheet.nearest(V)
        wgt = G.sm(np.clip(hgt / 0.15, 0, 1))[:, None]
        root_zone = (A3[:, 0] < 0.35)[:, None]
        N = np.where(root_zone, GM.nrm(Nn * (1 - wgt) + N * wgt), N)
        self.V, self.F, self.N, self.A3 = V, F, N, A3
        self.spine_pts = np.concatenate(spine_pts)
        self.spine_r = np.concatenate(spine_r)
        return V, F

    def sdf(self, Q):
        """冠の管（背骨と半径）と主役波の面（高さ）の和の距離の場（近似）。"""
        d_t, j = self.stree.query(Q, k=6)
        dt = (d_t - self.spine_r[j]).min(1)
        hs, _ = self.sheet.height(Q, k=2)
        return np.minimum(dt, hs)

    def ao_keyvis(self):
        V, N = self.V, self.N
        self.stree = cKDTree(self.spine_pts)
        ao = np.ones(len(V))
        occ = np.zeros(len(V))
        for d, w in ((0.08, 0.35), (0.16, 0.30), (0.32, 0.22), (0.64, 0.13)):
            s = self.sdf(V + N * d)
            occ += w * np.clip((d - np.clip(s, 0, None)) / d, 0, 1)
        ao = np.clip(1 - 1.1 * occ, 0, 1)
        # 固定の光の見通し（柔らかい影の行進）
        res = np.ones(len(V))
        tcur = np.full(len(V), 0.06)
        P0 = V + N * 0.03
        for _ in range(28):
            p = P0 + GM.LIGHT[None, :] * tcur[:, None]
            s = self.sdf(p)
            res = np.minimum(res, np.clip(6.0 * s / tcur, 0, 1))
            tcur = tcur + np.clip(s, 0.05, 0.8)
            if (tcur > 10).all():
                break
        # keyVis は落ちる影だけにする：光に背を向ける面（N·L ≤ 0.1）は自分の管の中を通るので 1 にする（陰はシェーダーの N·L が受け持つ）
        ndl = (N * GM.LIGHT[None, :]).sum(1)
        res = np.where(ndl <= 0.1, 1.0, res)
        return ao, res

    # ------------------------------------------------------------ 測る（S1 の数との比べ）
    def measure(self):
        T = self.T
        dig = [t for t in self.tubes if t["kind"] == 1]
        palms = [t for t in self.tubes if t["kind"] == 0 and "user" not in t]
        out = {}

        def tipinfo(P):
            d_all = GM.nrm(P[-1] - P[0])
            d_tip = GM.nrm(P[-1] - P[-3])
            return d_all, d_tip
        lens = [float(np.sum(np.linalg.norm(np.diff(t["P"], axis=0), axis=1)) - 0.10) for t in dig]
        rb = [float(t["rad"][0]) * 2 for t in dig]
        elev_all, elev_tip, down, fwd, ang_n = [], [], [], [], []
        for t in dig:
            da, dt = tipinfo(t["P"])
            elev_all.append(math.degrees(math.asin(np.clip(da @ GM.UP, -1, 1))))
            elev_tip.append(math.degrees(math.asin(np.clip(dt @ GM.UP, -1, 1))))
            down.append(dt @ GM.UP < 0)
            fwd.append(da @ self.travel > 0)
        for x in self.hands:
            if "theta_deg" in x:
                ang_n.append(x["theta_deg"])
        users = self.user
        u_tipdown = [GM.nrm(u["spine_w"][-1] - u["spine_w"][-4]) @ GM.UP < 0 for u in users]
        n_tips = len(dig) + len(users)
        rim = self.rim_length()
        n_uh = len(set(u["hand"] for u in users))
        hand_ids = set(t["hand"] for t in self.tubes if t["hand"] < 2000) | set(u["hand"] for u in users)
        n_proc = len([i for i in hand_ids if i >= 1000])
        n_bands = len([t for t in self.tubes if t["hand"] >= 2000])
        out["counts"] = dict(hands_procedural=n_proc, hands_user=n_uh, hands_total=len(hand_ids), band_ropes=n_bands,
                             digits_procedural=len(dig), user_claw_tips=len(users), fingertips_total=n_tips,
                             rim_length_m=round(rim, 2), fingertips_per_m=round(n_tips / rim, 3), hands_per_m=round(len(hand_ids) / rim, 3),
                             S1_target=dict(fingertips=T["fingertips_hero"], hands=T["hands_hero"]))
        out["digit_len_m"] = dict(ours=G.pct(lens), S1=T["digit_len_m"])
        out["digit_base_diam_m"] = dict(ours=G.pct(rb), S1_p50=round(2 * T["digit_r_base"], 3))
        out["digit_len_over_base_diam"] = dict(ours=G.pct(np.array(lens) / np.maximum(np.array(rb), 1e-6)), S1_mesh_p50=2.0, S1_photo_p50=3.5)
        out["digit_overall_below_horizontal_deg"] = dict(ours=G.pct(-np.array(elev_all)), S1_p50=round(T["overall_vs_up"]["p50"] - 90, 1))
        out["digit_tip_below_horizontal_deg"] = dict(ours=G.pct(-np.array(elev_tip)), S1_p50=round(T["tip_vs_up"]["p50"] - 90, 1))
        out["frac_tips_down"] = dict(ours=round(float(np.mean(down + u_tipdown)), 3) if (down or u_tipdown) else None, S1=T["frac_tips_down"])
        out["frac_forward"] = dict(ours=round(float(np.mean(fwd)), 3) if fwd else None, S1=T["frac_forward"])
        out["hand_theta_vs_normal_deg"] = dict(ours=G.pct(ang_n), S1=T["angle_vs_normal"])
        out["user_claw_angle_vs_normal_deg"] = dict(before=G.pct([u["angle_normal_before"] for u in users]),
                                                    after=G.pct([u["angle_normal_after"] for u in users]), S1_p50=T["angle_vs_normal"]["p50"])
        out["tiers"] = {str(k): sum(1 for x in self.hands if x.get("tier") == k) for k in (0, 1, 2, 3, 4)}
        out["tips"] = {k: sum(1 for t in dig if t["tip"] == k) for k in ("round", "open", "bulb")}
        # 根元の高さ（海面から、H0 の比）
        rh = [x["root_xyz"][1] / self.h.H0 for x in self.hands]
        out["root_height_over_H0"] = dict(ours=G.pct(rh), S1=G.jload(G.SPEC)["1_crest_crown"]["coverage"]["root_height_above_sea_over_H"]["value"])
        return out

    def rim_length(self):
        h = self.h
        rows = [r for r in range(69, 228) if h.X[r, h.top_col[r], 1] >= 0.30 * h.H0]
        P = np.stack([h.X[r, h.top_col[r]] for r in rows])
        return float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1)))

    def checks(self):
        """面を突き抜ける頂点（根元の 0.3 m より先で面の下 3 cm より深い）と、別の手の管どうしの重なり。"""
        V, A3 = self.V, self.A3
        hgt, _ = self.sheet.height(V)
        beyond = A3[:, 0] > 0.30
        pen = beyond & (hgt < -0.03)
        kinds = {0: "palm", 1: "digit", 2: "user_claw"}
        res = dict(vertices=int(len(V)), triangles=int(len(self.F)),
                   surface_penetrating_vertices=int(pen.sum()), surface_penetrating_fingers=int(len(np.unique(A3[pen, 1]))),
                   surface_penetrating_by_kind={kinds[k]: int(len(np.unique(A3[pen & (A3[:, 2] == k), 1]))) for k in (0, 1, 2)},
                   surface_penetration_depth_by_kind_m={kinds[k]: (round(float(-hgt[beyond & (A3[:, 2] == k)].min()), 3) if (beyond & (A3[:, 2] == k)).any() else None) for k in (0, 1, 2)},
                   min_height_beyond_root_m=round(float(hgt[beyond].min()), 3) if beyond.any() else None)
        # 指の芯（背骨）が面の下に入るか（根元の帯＝掌 0.5 m・指 0.3 m・利用者の爪 0.35 m より先）：指が波の体の中へ入る・面を突き抜ける
        core = []
        for t in self.tubes:
            P = t["P"]
            L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
            thr = 0.5 if t["kind"] == 0 else 0.3
            if t.get("hand", 0) >= 2000:
                thr = 0.0
            sel = L > thr
            if sel.any():
                hh, _ = self.sheet.height(P[sel])
                core.append((("user_sleeve" if "user" in t else "palm") if t["kind"] == 0 else "digit", float(hh.min()), t["hand"]))
        for u in self.user:
            sp = u["spine_w"]
            L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(sp, axis=0), axis=1))]
            sel = L > 0.35
            if sel.any():
                hh, _ = self.sheet.height(sp[sel])
                core.append(("user_claw", float(hh.min()), u["hand"]))
        res["finger_core_below_surface"] = {k: dict(n=sum(1 for c in core if c[0] == k and c[1] < 0), worst_m=round(-min([c[1] for c in core if c[0] == k] + [0.0]), 3))
                                            for k in ("palm", "digit", "user_sleeve", "user_claw")}
        res["finger_core_note_ja"] = "芯（背骨）の最も低い高さ。負なら指の芯が主役波の面の下（体の中）に入る。表面の頂点の数（surface_penetrating_*）は、平たい掌や利用者の爪の縁が面に沈む分（根元をつなぐための沈み）も数える"
        # 根元の継ぎ目：面との交わりの近く（|h| < 0.04 m）の頂点の法線と面の法線の角
        Pn, Nn, _, _ = self.sheet.nearest(V)
        seam = (np.abs(hgt) < 0.04) & (A3[:, 0] < 0.35)
        if seam.any():
            ang = np.degrees(np.arccos(np.clip((self.N[seam] * Nn[seam]).sum(1), -1, 1)))
            res["root_seam_normal_jump_deg"] = G.pct(ang, (50, 90, 99))
        # 別の手の管の重なり（背骨の距離 < 0.85 (r_i + r_j)）
        worst = []
        for t in self.tubes:
            v = self.collide_tubes_final(t)
            if v > 0:
                worst.append(v)
        res["tube_overlaps_other_hands"] = dict(n=len(worst), worst_m=round(max(worst), 3) if worst else 0.0)
        return res

    def collide_tubes_final(self, t):
        others = [o for o in self.tubes + getattr(self, "proxies", []) if o["hand"] != t["hand"]]
        if not others:
            return 0.0
        pts = np.concatenate([o["P"] for o in others])
        rr = np.concatenate([o["rad"] for o in others])
        tree = cKDTree(pts)
        worst = 0.0
        for p, r in zip(t["P"], t["rad"]):
            idx = tree.query_ball_point(p, r + 0.5)
            if idx:
                d = np.linalg.norm(pts[idx] - p, axis=1)
                worst = max(worst, float((0.85 * (r + rr[idx]) - d).max()))
        return worst


def surface_probe(tl):
    pts = []
    for t in tl:
        P = t["P"]
        T = GM.nrm(np.gradient(P, axis=0))
        a = GM.nrm(np.cross(T, GM.UP + 1e-3))
        b = np.cross(T, a)
        r = t["rad"][:, None]
        pts += [P, P + a * r, P - a * r, P + b * r, P - b * r, P[-1:] + T[-1:] * r[-1:]]
    return np.concatenate(pts)


def rotmat(axis, ang):
    k = GM.nrm(axis)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(ang) * K + (1 - math.cos(ang)) * (K @ K)


def write_static(out, name, V, N, uv5, uv3, F):
    os.makedirs(out, exist_ok=True)
    binp = os.path.join(out, name + ".bin")
    with open(binp, "wb") as f:
        for arr in (V, N, uv5, uv3):
            f.write(np.ascontiguousarray(arr, dtype="<f4").tobytes())
        f.write(np.ascontiguousarray(F, dtype="<u4").tobytes())
    js = {"schema": "GreatWave.AS03.static_mesh/1", "vertices": int(len(V)), "triangles": int(len(F)),
          "channels": [["position", 3], ["normal", 3], ["uv5", 4], ["uv3", 4]], "bin": name + ".bin", "sha256": G.sha(binp),
          "noteJa": "shared/README.md の B2 の書式。uv5 = (ao, keyVis, whiteSD（冠は全部白 = +10）, kind 1)、uv3 = (f 根元 0 → 先 1, 指の番号, 種類 0 手（掌）・1 指・2 利用者の爪, 0)。位置・法線は Unity の世界（m）、t* の静止。"}
    G.jdump(os.path.join(out, name + ".json"), js)
    return js


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["OUT", "IN"], required=True)
    ap.add_argument("--seed", type=int, default=3101)
    ap.add_argument("--hands", type=int, default=28, help="手続きで作る手の数（利用者の爪の手を除く）")
    ap.add_argument("--fast", action="store_true", help="AO と光の見通しを計算しない（試しの時だけ。値は 1）")
    ap.add_argument("--band", action="store_true", help="冠の泡の帯の管を足す（試し 6 で管に見えたので既定は入れない）")
    ap.add_argument("--user-palms", action="store_true", help="利用者の爪の房の下に掌を置く（試し rim2 で箱・円柱に見えたので既定は置かない。袖だけ）")
    ap.add_argument("--rim-many-digits", action="store_true", help="頂の縁の手を S1 の写真の 2〜5 本の指にする（既定は 1〜3 本・平均 1.7 本の手を密に並べ、冠の縁を続ける。試し rim2・rim3）")
    ap.add_argument("--out-suffix", default="", help="出力のフォルダー名に足す（比べの版）")
    ap.add_argument("--lip-hands", type=int, default=0, help="唇の縁から垂れる手（段 4）の数。頂の縁の手はその分減らす")
    ap.add_argument("--smooth-hands", action="store_true", help="手続きの手（掌＋指）を距離の場のなめらかな和（marching cubes）で 1 つの面にする")
    ap.add_argument("--smooth-vox", type=float, default=0.035)
    ap.add_argument("--smooth-k", type=float, default=0.045)
    a = ap.parse_args()
    t0 = time.time()
    C = Crown(a.mode, a.seed)
    if not a.rim_many_digits:
        C.rim_digits = ([1, 2, 3], [0.45, 0.40, 0.15])
    C.smooth_hands, C.smooth_vox, C.smooth_k = a.smooth_hands, a.smooth_vox, a.smooth_k
    C.lip_hands = a.lip_hands
    C.place_user()
    if a.user_palms:
        C.place_user_palms()
    print("user claws", len(C.user), round(time.time() - t0, 1), flush=True)
    C.place(a.hands)
    if a.band:
        C.place_band()
        C.tubes.extend(C.bands)
    print("hands", len(C.hands), "tubes", len(C.tubes), "dropped", len(C.dropped), round(time.time() - t0, 1), flush=True)
    in_stats = None
    if a.mode == "IN":
        in_stats = C.constrain_in()
        print("IN", in_stats, round(time.time() - t0, 1), flush=True)
    V, F = C.build_mesh()
    if a.fast:
        ao, kv = np.ones(len(V)), np.ones(len(V))
    else:
        ao, kv = C.ao_keyvis()
    print("mesh", len(V), len(F), round(time.time() - t0, 1), flush=True)
    out = os.path.join(G.OUT, a.mode + a.out_suffix)
    uv5 = np.stack([ao, kv, np.full(len(V), 10.0), np.ones(len(V))], -1)
    uv3 = C.A3
    js = write_static(out, "as03_crown", V, C.N, uv5, uv3, F)
    G.write_obj(os.path.join(out, "as03_crown.obj"), V, F, N=C.N, name="as03_crown_" + a.mode)
    np.save(os.path.join(out, "as03_crown_attr.npy"), np.concatenate([uv5, uv3], 1).astype(np.float32))
    meas = C.measure()
    chk = C.checks()
    lay = dict(schema="GreatWave.AS03.crown_layout/1", mode=a.mode, seed=a.seed, hands=C.hands,
               fingers=[dict(fid=t.get("fid"), hand=t["hand"], kind=t["kind"], tip=t["tip"], user=t.get("user"),
                             length_m=round(float(np.sum(np.linalg.norm(np.diff(t["P"], axis=0), axis=1))), 3),
                             r_base_m=round(float(t["rad"][0]), 3), r_tip_m=round(float(t["rad"][-1]), 3),
                             root=[round(float(v), 3) for v in t["P"][0]], tip_xyz=[round(float(v), 3) for v in t["P"][-1]]) for t in C.tubes],
               user_claws=[dict(id=u["id"], layout_id=u["layout_id"], part=u["part"], fid=u.get("fid"), hand=u["hand"],
                                angle_normal_before=u["angle_normal_before"], angle_normal_after=u["angle_normal_after"],
                                surface_pen_m=u["surface_pen_m"], rotation=[[round(float(x), 6) for x in row] for row in u["R"]]) for u in C.user],
               dropped=C.dropped)
    G.jdump(os.path.join(out, "as03_crown_layout.json"), lay)
    rep = dict(schema="GreatWave.AS03.crown_report/1", mode=a.mode, seed=a.seed, date=time.strftime("%Y-%m-%d %H:%M"),
               method_ja=__doc__.strip(), mesh=js, measure=meas, checks=chk, in_constraint=in_stats, log=C.log,
               attr_stats=dict(ao=G.pct(ao), keyVis=G.pct(kv)),
               inputs=dict(hero_gwb_sha256=G.sha(G.GWB), spec_sha256=C.spec_sha, user=C.user_src,
                           white_mask=dict(file=os.path.relpath(os.path.join(G.SHARED, "white_mask.json"), G.REPO).replace("\\", "/"),
                                           sha256=G.sha(os.path.join(G.SHARED, "white_mask.json")))),
               elapsed_s=round(time.time() - t0, 1))
    G.jdump(os.path.join(out, "as03_crown_report.json"), rep)
    print(json.dumps(dict(measure=meas["counts"], checks=chk), ensure_ascii=False)[:1500])
    print("CROWN_DONE", a.mode, round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
