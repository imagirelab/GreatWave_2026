# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：最後の一コマ K*′ の作り直し（py -3.10、numpy だけ）。

考え方（Q21「在固定角度应该是海浪的两侧边缘去匹配」）
  R1〜R4 では、左の外輪郭 78・130・131 を肩の行の頂（列 90 付近、背のいちばん上）が描いていた。頂は原画カメラの射線の上でしか
  動かせず、背がその頂へ向けて盛り上がるので、後ろから見て中ほどのドーム（レモン形）になった。
  FACE-SWAP では、左の外輪郭を描く面を「背の頂」から「前の唇の上面（前へ出た面）」へ替える：
    1. 背の殻をならす（行の向き c に沿ったガウスのならし。行ごとの折れ・襞・こぶを消す）。
    2. 肩の行の頂（背の上端）を、原画カメラの射線の面（視錐の跡）より m だけ下げ、少し後ろへ引く。
    3. 前の唇の上面を持ち上げて、各行がその行の視錐の跡に前の側で接する（輪郭を描く）ようにする。
       視錐の跡は前へ行くほど高い（肩の行）ので、接する点は頂より前・上になり、背の頂は射線の面の下に隠れる。
    4. 奥の端（c > +3）の背と管の口をならす（原画視点では唇の陰）。
    5. 列の目印（j_top = 行の最も高い点）を保つため、行の中で列を弧長に沿って滑らせる（トポロジー・UV の並びは同じ）。
  入力は K*′ R4 の行（kstar_final の rows npz）だけ。参照モデル（他者の作品）の網は読まない（F13-1）。
usage: py -3.10 faceswap_build.py <design.json> <out_prefix>   （design.json は名前の付いた値。既定は faceswap_design_default.json）
"""
import os
import sys
import json
import time
import math

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def ramp(c, lo0, lo1, hi1, hi0):
    """0 below lo0, 1 between lo1 and hi1, 0 above hi0 (smoothstep ramps)."""
    c = np.asarray(c, float)
    up = smoothstep((c - lo0) / max(lo1 - lo0, 1e-9))
    dn = 1.0 - smoothstep((c - hi1) / max(hi0 - hi1, 1e-9))
    return up * dn


def col_window(nu, j0, j1, j2, j3):
    j = np.arange(nu, dtype=float)
    return ramp(j, j0, j1, j2, j3)


def smooth_along_c(c, V, sigma, w_rows, w_cols):
    """V (nv, nu): 行の向き c に沿ったガウスのならし（c の距離で重み。端は正規化）。結果を重み w_rows × w_cols で混ぜる。"""
    dc = c[:, None] - c[None, :]
    K = np.exp(-0.5 * (dc / sigma) ** 2)
    # 不等間隔の行：各行の担う c の幅で重みを付ける
    width = np.gradient(c)
    K = K * width[None, :]
    K /= K.sum(1, keepdims=True)
    S = K @ V
    W = w_rows[:, None] * w_cols[None, :]
    return V * (1 - W) + S * W


def row_trace_bound(tr_pts, a_query):
    """行の面の視錐の跡（射線の交点の列、原画の線の順）から、a ごとの上限 y を作る（跡のない a は +inf）。
    跡が a について単調でない所は、重なる枝の低い方を採る（どの射線より上にも出ない）。"""
    a, y = tr_pts[:, 0], tr_pts[:, 1]
    out = np.full(len(a_query), np.inf)
    for k in range(len(a) - 1):
        a0, a1 = a[k], a[k + 1]
        lo, hi = min(a0, a1), max(a0, a1)
        m = (a_query >= lo) & (a_query <= hi)
        if not m.any():
            continue
        if abs(a1 - a0) < 1e-9:
            yy = np.full(m.sum(), min(y[k], y[k + 1]))
        else:
            t = (a_query[m] - a0) / (a1 - a0)
            yy = y[k] + t * (y[k + 1] - y[k])
        out[m] = np.minimum(out[m], yy)
    return out


def inside_any(poly, pts):
    """偶奇の規則の点の多角形の内外（numpy）。pts のどれかが poly の中なら True。"""
    if len(pts) == 0:
        return False
    x, y = pts[:, 0], pts[:, 1]
    xmin, ymin = poly.min(0); xmax, ymax = poly.max(0)
    m = (x >= xmin) & (x <= xmax) & (y >= ymin) & (y <= ymax)
    if not m.any():
        return False
    x, y = x[m], y[m]
    inside = np.zeros(len(x), bool)
    x0, y0 = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x0, -1), np.roll(y0, -1)
    for k in range(len(poly)):
        cond = (y0[k] > y) != (y1[k] > y)
        if not cond.any():
            continue
        xi = x0[k] + (y - y0[k]) * (x1[k] - x0[k]) / (y1[k] - y0[k] + 1e-30)
        inside ^= cond & (x < xi)
    return bool(inside.any())


class Builder:
    def __init__(self, design):
        self.d = design
        self.c, self.A0, self.Y0 = F.load_r4()
        seg = F.outline_segments()
        self.seg = seg
        L = [seg["78"], seg["130"][1:], seg["131"][1:]]
        self.left_px = np.vstack(L)               # 78 → 130 → 131（左の外輪郭）
        self.lead_px = np.vstack(L + [seg["132"][1:]])
        self.log = []

    def say(self, *a):
        s = " ".join(str(x) for x in a)
        self.log.append(s)
        print(s, flush=True)

    # ------------------------------------------------------------ 1. 背の殻をならす
    def shell_smooth(self, A, Y):
        p = self.d["shell_smooth"]
        c = self.c
        wr = ramp(c, *p["rows_ramp_c"])
        out_A, out_Y = A.copy(), Y.copy()
        for it in range(int(p.get("passes", 1))):
            wc = col_window(A.shape[1], *p["cols_ramp"])
            out_A = smooth_along_c(c, out_A, p["sigma_c_m"], wr, wc)
            out_Y = smooth_along_c(c, out_Y, p["sigma_c_m"], wr, wc)
        self.say("shell_smooth: sigma %.2f m, rows %s, cols %s, max |dY| %.3f m" % (
            p["sigma_c_m"], p["rows_ramp_c"], p["cols_ramp"], float(np.abs(out_Y - Y).max())))
        return out_A, out_Y

    # ------------------------------------------------------------ 2+3. 顔の入れ替え（肩の行）
    def face_swap(self, A, Y):
        p = self.d["face_swap"]
        c = self.c
        nu = A.shape[1]
        W = ramp(c, *p["rows_ramp_c"])
        j = np.arange(nu, dtype=float)
        wcrest = np.exp(-0.5 * ((j - p["crest_col"]) / p["crest_width_cols"]) ** 2)
        wcrest[j <= 18] = 0.0
        wcrest *= smoothstep((j - 18) / 20.0)
        rec = []
        A1, Y1 = A.copy(), Y.copy()
        lam = np.zeros(len(c)); dlt = np.zeros(len(c)); sh = np.zeros(len(c)); jl = np.zeros(len(c))
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            tr, _ = F.ray_row_trace(self.lead_px, c[r])
            a, y = A[r].copy(), Y[r].copy()
            tipc = int(p["tip_col"])
            ub = row_trace_bound(tr, a)
            # 唇の上面の持ち上げの窓：頂の少し前から唇先の手前まで（列）
            j_l = p["lip_col"]
            wl = np.exp(-0.5 * ((j - j_l) / p["lip_width_cols"]) ** 2) * (j > p["crest_col"] - 8) * (j < tipc)
            wl *= 1.0 - smoothstep((j - (tipc - p["tip_keep_cols"])) / p["tip_keep_cols"])
            # 頂を下げる量：頂の帯が視錐の跡より margin 下になるまで
            crest_band = (j >= p["crest_col"] - 20) & (j <= p["crest_col"] + 8) & np.isfinite(ub)
            gap_c = (ub - y)[crest_band]
            need = p["crest_margin_m"] - (gap_c.min() if len(gap_c) else 1e9)
            delta = float(np.clip(need, 0.0, p["crest_drop_max_m"])) if len(gap_c) else 0.0
            delta = max(delta, p.get("crest_drop_min_m", 0.0))
            # 後ろへ引く量（列の帯を a の負の向きへ）
            shift = p["crest_back_m"]
            y2 = y - W[r] * delta * wcrest
            a2 = a - W[r] * shift * wcrest
            ub2 = row_trace_bound(tr, a2)
            # 唇を持ち上げる量：唇の窓の中で、ちょうど視錐の跡に接するまで
            m = (wl > 0.25) & np.isfinite(ub2)
            if m.any():
                lam_r = float(np.min((ub2[m] - y2[m]) / wl[m]))
                lam_r = float(np.clip(lam_r, p["lift_min_m"], p["lift_max_m"]))
            else:
                lam_r = 0.0
            lam[r], dlt[r], sh[r], jl[r] = lam_r, W[r] * delta, W[r] * shift, j_l
        # 行の間でならす（行ごとの解の揺れを消す）
        def sm(v, s):
            if s <= 0:
                return v
            dc = c[:, None] - c[None, :]
            K = np.exp(-0.5 * (dc / s) ** 2) * np.gradient(c)[None, :]
            m_ = (W > 1e-4).astype(float)
            return (K @ (v * m_)) / np.maximum(K @ m_, 1e-9) * m_
        lam_s = sm(lam, p["param_smooth_c_m"])
        if p.get("lift_envelope", False):
            # ならした値がどの行でもその行の接する値を超えない（はみ出さない）ように、ならす→min を繰り返す
            for _ in range(20):
                lam_s = np.minimum(sm(lam_s, p["param_smooth_c_m"]), lam)
        dlt_s = sm(dlt, p["param_smooth_c_m"])
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            j_l = p["lip_col"]
            tipc = int(p["tip_col"])
            wl = np.exp(-0.5 * ((j - j_l) / p["lip_width_cols"]) ** 2) * (j > p["crest_col"] - 8) * (j < tipc)
            wl *= 1.0 - smoothstep((j - (tipc - p["tip_keep_cols"])) / p["tip_keep_cols"])
            # 持ち上げは唇の法線の向きではなく鉛直（上面を上へ）。前へは lip_forward_m だけ運ぶ
            Y1[r] = Y[r] - dlt_s[r] * wcrest + W[r] * lam_s[r] * wl * p.get("lift_gain", 1.0)
            A1[r] = A[r] - sh[r] * wcrest + W[r] * p["lip_forward_m"] * wl
            rec.append((float(c[r]), round(float(dlt_s[r]), 3), round(float(W[r] * lam_s[r]), 3)))
        self.fs_record = {"rows": rec}
        self.say("face_swap: rows %d, crest drop max %.3f m, lip lift min/max %.3f/%.3f m" % (
            len(rec), float(dlt_s.max()), float((W * lam_s).min()), float((W * lam_s).max())))
        return A1, Y1

    # ------------------------------------------------------------ 5. 列を滑らせて j_top を行の最も高い点へ
    def reslide_top(self, A, Y):
        p = self.d.get("reslide_top", {})
        if not p.get("enabled", False):
            return A, Y
        A1, Y1 = A.copy(), Y.copy()
        nmove = 0
        jB, jT, jP = KC.LM["j_B"], KC.LM["j_top"], KC.LM["j_tip"]
        for r in range(A.shape[0]):
            a, y = A[r], Y[r]
            if y.max() < 1.0:
                continue
            jm = int(np.argmax(y[jB:jP])) + jB
            if abs(jm - jT) <= 1:
                continue
            s = KC.arclen(a, y)
            # 旧の目印の弧長での相対の位置を保ったまま、[jB, jT] と [jT, jP] を新しい頂の弧長へ写す
            sB, sT0, sP = s[jB], s[jT], s[jP]
            # 新しい頂：なめらかにした曲率ではなく、最も高い点を二次で補う
            if 0 < jm < len(y) - 1:
                y0, y1_, y2_ = y[jm - 1], y[jm], y[jm + 1]
                den = y0 - 2 * y1_ + y2_
                t = 0.5 * (y0 - y2_) / den if abs(den) > 1e-12 else 0.0
                t = float(np.clip(t, -1, 1))
            else:
                t = 0.0
            sT = np.interp(jm + t, np.arange(len(s)), s)
            u1 = (s[jB:jT + 1] - sB) / (sT0 - sB)
            u2 = (s[jT:jP + 1] - sT0) / (sP - sT0)
            snew = s.copy()
            snew[jB:jT + 1] = sB + u1 * (sT - sB)
            snew[jT:jP + 1] = sT + u2 * (sP - sT)
            A1[r] = np.interp(snew, s, a)
            Y1[r] = np.interp(snew, s, y)
            nmove += 1
        self.say("reslide_top: rows moved %d" % nmove)
        return A1, Y1

    def build(self):
        A, Y = self.A0.copy(), self.Y0.copy()
        steps = self.d["steps"]
        for st in steps:
            if st == "shell_smooth":
                A, Y = self.shell_smooth(A, Y)
            elif st == "face_swap":
                A, Y = self.face_swap(A, Y)
            elif st == "far_smooth":
                A, Y = self.far_smooth(A, Y)
            elif st == "reslide_top":
                A, Y = self.reslide_top(A, Y)
            elif st.startswith("apex_round"):
                A, Y = self.apex_round(A, Y, self.d[st], st)
            elif st == "face_swap_arc":
                A, Y = self.face_swap_arc(A, Y)
            elif st == "face_swap_round":
                A, Y = self.face_swap_round(A, Y)
            elif st == "face_swap_lean":
                A, Y = self.face_swap_lean(A, Y)
            elif st == "untangle_lip":
                A, Y = self.untangle_lip(A, Y)
            elif st == "uncross_lip":
                A, Y = self.uncross_lip(A, Y)
            elif st == "tail_round":
                A, Y = self.tail_round(A, Y)
            elif st == "wall_guard":
                A, Y = self.wall_guard(A, Y)
            elif st == "back_shell":
                A, Y = self.back_shell(A, Y)
            elif st == "far_shift":
                A, Y = self.far_shift(A, Y)
            elif st == "far_slim":
                A, Y = self.far_slim(A, Y)
            elif st.startswith("bsfit"):
                A, Y = self.bsfit(A, Y, self.d[st], st)
            elif st.startswith("edgefit"):
                A, Y = self.edgefit(A, Y, self.d[st])
            elif st.startswith("col_smooth"):
                A, Y = self.col_smooth(A, Y, self.d[st], st)
            elif st.startswith("region_smooth"):
                A, Y = self.region_smooth(A, Y, self.d[st], st)
            else:
                raise ValueError(st)
        return self.c, A, Y

    # ------------------------------------------------------------ 2+3（第1回の採用の形）：顔の入れ替えを広い傾きで行う
    def face_swap_lean(self, A, Y):
        """肩の行の上の部分（列 30〜200、唇先の手前で 0 へ）を、頂（列 90）を中心に前へ傾ける：
             Δy(j) = w(j)·(−δ(c) + k(c)·(a_j − a_c))
        δ で背の頂を下げ（射線の面より下へ）、k（前へ 1 m あたりの上がり）で前の唇の上面を持ち上げ、その行の視錐の跡に前の側で接させる。
        k は行ごとに「唇の上面（頂より 1 m 以上前）がちょうど跡に接する」値を解き、c に沿ってならす。幅の広い傾きなので、
        6 m の局所の当てはめ（評審の膨らみの測り）に新しいこぶを作らない。"""
        p = self.d["face_swap_lean"]
        c = self.c
        nu = A.shape[1]
        j = np.arange(nu, dtype=float)
        W = ramp(c, *p["rows_ramp_c"])
        w = col_window(nu, *p["cols_ramp"])
        jc = int(p["crest_col"])
        k_row = np.zeros(len(c)); d_row = W * p["crest_drop_m"]
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            tr, _ = F.ray_row_trace(self.lead_px, c[r])
            a, y = A[r], Y[r]
            ac = a[jc]
            y2 = y - w * d_row[r]
            ub = row_trace_bound(tr, a)
            sel = (j > jc) & (j < p["lip_search_cols"][1]) & (j >= p["lip_search_cols"][0]) & (a > ac + 1.0) & np.isfinite(ub) & (w > 0.3)
            if not sel.any():
                continue
            kk = (ub[sel] - y2[sel]) / (w[sel] * (a[sel] - ac))
            k_row[r] = float(np.clip(kk.min(), p["k_min"], p["k_max"]))
        # ならす
        dc = c[:, None] - c[None, :]
        K = np.exp(-0.5 * (dc / p["param_smooth_c_m"]) ** 2) * np.gradient(c)[None, :]
        m_ = (W > 1e-4).astype(float)
        k_s = (K @ (k_row * m_)) / np.maximum(K @ m_, 1e-9) * m_
        A1, Y1 = A.copy(), Y.copy()
        rec = []
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            a = A[r]; ac = a[jc]
            Y1[r] = Y[r] + w * (-d_row[r] + W[r] * k_s[r] * (a - ac))
            rec.append((round(float(c[r]), 3), round(float(d_row[r]), 3), round(float(W[r] * k_s[r]), 4)))
        self.fs_record = {"rows_c_drop_k": rec, "note": "face_swap_lean: dy = w(j) (-drop + k (a - a_crest))"}
        self.say("face_swap_lean: rows %d, drop max %.2f m, k min/max %.3f/%.3f" % (len(rec), float(d_row.max()), float((W * k_s).min()), float((W * k_s).max())))
        return A1, Y1

    # ------------------------------------------------------------ 唇の断面の自己交差を消す（網の衛生。交差した行だけ、唇の領域を R4 へ戻す）
    @staticmethod
    def row_crossings(a, y, r1, r2):
        """断面の折れ線の区間 r1 と r2（列の範囲）の線分どうしの交差の数（端を共有する組は除く）。"""
        P = np.stack([a, y], -1)
        i1 = np.arange(r1[0], r1[1]); i2 = np.arange(r2[0], r2[1])
        A0, A1_ = P[i1][:, None, :], P[i1 + 1][:, None, :]
        B0, B1 = P[i2][None, :, :], P[i2 + 1][None, :, :]
        def orient(p, q, r):
            return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
        o1 = orient(A0, A1_, B0); o2 = orient(A0, A1_, B1); o3 = orient(B0, B1, A0); o4 = orient(B0, B1, A1_)
        hit = (o1 * o2 < 0) & (o3 * o4 < 0)
        adj = np.abs(i1[:, None] - i2[None, :]) <= 1
        return int((hit & ~adj).sum())

    def uncross_lip(self, A, Y):
        """各行の唇の上面（列 r1）と下面・管（列 r2）の断面の交差を数え、交差のある行（と前後 ±pad_m）だけ、唇の領域（列 cols）を
        R4 へ向けて混ぜ戻す（混ぜの重みは交差がなくなる最小を二分法で。列の端はなめらかに）。"""
        p = self.d["uncross_lip"]
        c = self.c
        r1, r2 = tuple(p["top_cols"]), tuple(p["under_cols"])
        wc = col_window(A.shape[1], *p["cols_ramp"])
        bad = [r for r in range(len(c)) if Y[r].max() > 1.0 and self.row_crossings(A[r], Y[r], r1, r2) > 0]
        A1, Y1 = A.copy(), Y.copy()
        wrow = np.zeros(len(c))
        for r in bad:
            lo, hi = 0.0, 1.0
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                a_ = A[r] + mid * wc * (self.A0[r] - A[r]); y_ = Y[r] + mid * wc * (self.Y0[r] - Y[r])
                if self.row_crossings(a_, y_, r1, r2) > 0:
                    lo = mid
                else:
                    hi = mid
            wrow[r] = min(1.0, hi + p.get("extra", 0.1))
        if len(bad):
            dcm = c[:, None] - c[None, :]
            K = np.exp(-0.5 * (dcm / p["pad_m"]) ** 2)
            ws = np.clip((K * wrow[None, :]).max(1), 0, 1)
            ws = np.maximum(ws, wrow)
            A1 = A + ws[:, None] * wc[None, :] * (self.A0 - A)
            Y1 = Y + ws[:, None] * wc[None, :] * (self.Y0 - Y)
        left = [r for r in range(len(c)) if Y1[r].max() > 1.0 and self.row_crossings(A1[r], Y1[r], r1, r2) > 0]
        self.uncross_record = {"rows_with_crossing": [int(r) for r in bad], "c": [round(float(c[r]), 2) for r in bad],
                               "blend_to_R4": [round(float(wrow[r]), 3) for r in bad], "rows_left": left}
        self.say("uncross_lip: rows with crossing %d %s, blend max %.2f, rows left %d" % (len(bad), [round(float(c[r]), 1) for r in bad][:12],
                                                                                        float(wrow.max()) if len(bad) else 0.0, len(left)))
        return A1, Y1

    # ------------------------------------------------------------ 唇の上面が管の天井（唇の下面）を突き抜けないようにする（網の衛生）
    def untangle_lip(self, A, Y):
        """各行で、唇の上面（列 j1a..j1b）の各点が、唇の下面・管の天井（列 j2a..j2b）の水の側に t_min 以上あるようにする。
        足りない所は、上面の点を断面の外向きの法線の向きへ押し出す（押し出す量は列の向き σ 3 列、行の向き σ 0.4 m でならす）。
        原画の輪郭は、この後の小さな edgefit で合わせ直す。"""
        from scipy.ndimage import gaussian_filter1d
        p = self.d["untangle_lip"]
        c = self.c
        j1a, j1b, j2a, j2b = p["top_cols"][0], p["top_cols"][1], p["under_cols"][0], p["under_cols"][1]
        tmin = p["t_min_m"]
        A1, Y1 = A.copy(), Y.copy()
        tot = 0
        for it in range(int(p.get("iters", 3))):
            push = np.zeros(A.shape)
            nrow = 0
            for r in range(len(c)):
                a, y = A1[r], Y1[r]
                if y.max() < 1.0:
                    continue
                P1 = np.stack([a[j1a:j1b + 1], y[j1a:j1b + 1]], -1)
                P2 = np.stack([a[j2a:j2b + 1], y[j2a:j2b + 1]], -1)
                t2 = np.gradient(P2, axis=0); t2 /= np.maximum(np.linalg.norm(t2, axis=1, keepdims=True), 1e-12)
                n2 = np.stack([-t2[:, 1], t2[:, 0]], -1)                       # 下面の外向き（管の空気の側）
                t1 = np.gradient(P1, axis=0); t1 /= np.maximum(np.linalg.norm(t1, axis=1, keepdims=True), 1e-12)
                n1 = np.stack([-t1[:, 1], t1[:, 0]], -1)                       # 上面の外向き
                d = np.linalg.norm(P1[:, None, :] - P2[None, :, :], axis=-1)
                # 唇先（列 200）の継ぎ目の近くは、上面と下面がもともと近い：断面に沿って arc_gap_m より近い組は見ない
                sfull = KC.arclen(a, y)
                s1 = sfull[j1a:j1b + 1]; s2 = sfull[j2a:j2b + 1]
                d = np.where(np.abs(s1[:, None] - s2[None, :]) < p.get("arc_gap_m", 3.0), np.inf, d)
                k = np.argmin(d, axis=1)
                sd = -((P1 - P2[k]) * n2[k]).sum(-1)                            # + = 上面の点が下面の水の側
                deficit = np.clip(tmin - sd, 0, None)
                deficit[~np.isfinite(d[np.arange(len(k)), k]) | (d[np.arange(len(k)), k] > 2.0)] = 0.0   # 離れた所は見ない
                if deficit.max() > 0:
                    nrow += 1
                    gain = np.maximum((n1 * n2[k] * -1).sum(-1), 0.3)          # 上面の法線で押したときに離れる割合
                    push[r, j1a:j1b + 1] = deficit / gain
            if push.max() <= 0:
                break
            ps = gaussian_filter1d(push, 3.0, axis=1)
            ps = np.maximum(ps, push)
            dcm = c[:, None] - c[None, :]
            K = np.exp(-0.5 * (dcm / 0.4) ** 2) * np.gradient(c)[None, :]
            K /= K.sum(1, keepdims=True)
            ps = np.maximum(K @ ps, ps)
            ta = np.gradient(A1, axis=1); ty = np.gradient(Y1, axis=1)
            L = np.maximum(np.hypot(ta, ty), 1e-12)
            A1 = A1 + ps * (-ty / L); Y1 = Y1 + ps * (ta / L)
            tot = max(tot, nrow)
            self.say("untangle_lip it %d: rows %d, max push %.3f m" % (it, nrow, float(push.max())))
        return A1, Y1

    # ------------------------------------------------------------ 手前の尾の行を丸いうねりにする（Q17：t* の手前の尾の頂も弧）
    def tail_round(self, A, Y):
        """手前の尾（c ≤ c1。原画の枠の外：原画視点の x < −160 px）の行を、同じ高さ H・同じ頂の位置 a_m の cos² のうねり
            y = H·cos²(π (a − a_m) / (2 w))（|a − a_m| < w）
        に置き換える。w は元の半幅と、頂から断面に沿って ±2 m の弦の角が chord_min 度以上になる幅の大きい方
            w = π x / (2 asin(sqrt(d / H)))、d = 2 sin((180 − θ)/2)、x = 2 cos((180 − θ)/2)（θ = chord_min）。
        列は元の行の弧長の割合のまま置く（目印の順を保つ）。c1..c0 で元の行へなめらかに戻す。"""
        p = self.d["tail_round"]
        c = self.c
        W = 1.0 - smoothstep((c - p["c_full"]) / (p["c_end"] - p["c_full"]))
        th = np.radians(p["chord_min_deg"])
        dd = 2 * math.sin((math.pi - th) / 2); xx = 2 * math.cos((math.pi - th) / 2)
        A1, Y1 = A.copy(), Y.copy()
        n = 0
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            a, y = A[r], Y[r]
            H = float(y.max())
            if H < 0.3:
                continue
            jm = int(np.argmax(y))
            am = float(a[jm])
            nz = np.nonzero(y > 0.02)[0]
            w0 = 0.5 * float(a[nz[-1]] - a[nz[0]])
            wn = math.pi * xx / (2 * math.asin(min(math.sqrt(min(dd / H, 1.0)), 1.0))) if H > dd else w0
            w = max(w0, wn) * p.get("width_gain", 1.0)
            if "width_ramp_c" in p:
                # 幅は c に沿ってなめらかに広げる（背の足の線にくびれの段を作らない）
                ww = smoothstep((p["width_ramp_c"][1] - c[r]) / (p["width_ramp_c"][1] - p["width_ramp_c"][0]))
                w = w0 + (w - w0) * ww
            ta = np.linspace(min(a[0], am - w - 1), max(a[-1], am + w + 1), 2001)
            u = (ta - am) / w
            ty = np.where(np.abs(u) < 1, H * np.cos(0.5 * np.pi * u) ** 2, 0.0)
            if p.get("keep_flanks", False):
                # 元の行の上側の包絡（各 a で最も高い点）となめらかな max を取る：頂は丸いうねり、裾は元の背と前の位置のまま（背の足の線に段を作らない）
                env = np.zeros_like(ta)
                for k in range(len(a) - 1):
                    lo, hi = min(a[k], a[k + 1]), max(a[k], a[k + 1])
                    mm = (ta >= lo) & (ta <= hi)
                    if mm.any():
                        t_ = (ta[mm] - a[k]) / (a[k + 1] - a[k]) if a[k + 1] != a[k] else 0.0
                        env[mm] = np.maximum(env[mm], y[k] + t_ * (y[k + 1] - y[k]))
                if p.get("cap_only_frac", 0.0) > 0:
                    f0 = p["cap_only_frac"]
                    ty = ty * smoothstep((ty - f0 * H) / (0.25 * H))       # うねりは上の部分だけ（裾は元の行）
                kk = float(p.get("smoothmax_k", 4.0))
                ty = np.logaddexp(kk * ty, kk * env) / kk - np.log(2.0) / kk * np.exp(-kk * np.abs(ty - env))
                ty = np.clip(ty, 0.0, None)
            ts = KC.arclen(ta, ty)
            s0 = KC.arclen(a, y)
            frac = s0 / s0[-1]
            na = np.interp(frac * ts[-1], ts, ta); ny = np.interp(frac * ts[-1], ts, ty)
            if W[r] < 1.0 - 1e-6:
                # 移り変わりの行：頂を揃えて（頂からの符号付きの弧長が同じ点どうし）混ぜる。頂が二つにならない
                sb = ts - np.interp(am, ta, ts)            # うねりの頂からの弧長
                so = s0 - s0[jm]                            # 元の行の頂からの弧長
                qa = np.interp(so, sb, ta - am); qy = np.interp(so, sb, ty)
                ba = am + W[r] * qa + (1 - W[r]) * (a - am)
                by = W[r] * qy + (1 - W[r]) * y
                A1[r], Y1[r] = ba, by
            else:
                A1[r] = na
                Y1[r] = ny
            n += 1
        self.say("tail_round: rows %d (c <= %.1f, blend to %.1f), chord >= %.0f deg" % (n, p["c_full"], p["c_end"], p["chord_min_deg"]))
        return A1, Y1

    # ------------------------------------------------------------ 壁の厚みの守り（管が背を突き抜けない）
    def wall_guard(self, A, Y):
        """背（列 18〜90）が管の内側の壁より前へ出すぎた所を後ろへ戻す。守る厚み = min(R4 の厚み, τ·H) − 0.05 m（R4 より薄くしない所と、
        τ·H を守る所の小さい方）。戻す量は列と行の向きにならし、背の形を折らない。"""
        import faceswap_wall as FW
        p = self.d["wall_guard"]
        c = self.c
        nu = A.shape[1]
        A1 = A.copy()
        corr = np.zeros(A.shape)
        for r in range(len(c)):
            w1 = FW.wall_thickness(A[r], Y[r])
            w0 = FW.wall_thickness(self.A0[r], self.Y0[r])
            if w1 is None or w0 is None:
                continue
            hs, back, wall, t = w1
            _, _, _, t0 = w0
            H = float(Y[r, 90])
            need = np.minimum(np.nan_to_num(t0, nan=1e9), p["tau"] * H) - 0.05
            deficit = np.where(np.isfinite(t), need - t, 0.0)
            deficit = np.clip(deficit, 0, None)
            if deficit.max() <= 0:
                continue
            # 列ごとの高さで不足を読み、背の列（18..90）を後ろへ
            yb = Y[r, 18:91]
            d = np.interp(yb, hs, deficit, left=deficit[0], right=0.0)
            corr[r, 18:91] = d
        if corr.max() > 0:
            # ならす（行の向き σ 0.8 m、列の向き 4 列）。最大は保つように、ならした後に元の値との max を取る
            from scipy.ndimage import gaussian_filter1d
            cs = gaussian_filter1d(corr, 4.0, axis=1)
            dcm = c[:, None] - c[None, :]
            K = np.exp(-0.5 * (dcm / 0.8) ** 2) * np.gradient(c)[None, :]
            K /= K.sum(1, keepdims=True)
            cs = K @ cs
            cs = np.maximum(cs, corr)
            cs = gaussian_filter1d(cs, 2.0, axis=1)
            cs[:, :18] = cs[:, 18:19]
            cs[:, 91:] = 0.0
            # 頂（列 80..90）へ向けて 0 へ（頂は動かさない）
            j = np.arange(nu)
            cs *= (1.0 - smoothstep((j - 70) / 20.0))[None, :]
            A1 = A - cs
        self.say("wall_guard: tau %.2f, max push back %.3f m (rows %d)" % (p["tau"], float(corr.max()), int((corr.max(1) > 0).sum())))
        return A1, Y

    # ------------------------------------------------------------ 背の殻（原画視点から見えない背を、行に共通のなめらかな凸の殻にする）
    def back_shell(self, A, Y):
        """背（列 18〜90）を、行に共通の S 字の型 y = H·f(u)、a = a_c − L·(1 − u) に置き換える（u = 0 足、1 頂）。
          f(u) = u^m (1 + m (1 − u))：f(0)=0, f(1)=1, f'(0)=f'(1)=0、傾きの最大は u = (m−1)/m（m > 2 で頂の側、足は長い凹）。
          L(c) = max(κ·H(c), 壁の厚みを守る最小の長さ)。壁の厚み：どの高さでも、背は管の内側の壁（列 200〜379 の、その高さの最も後ろの点）
          より t_min = τ·H 以上後ろにある（管が背を突き抜けない。F03 の殻 0.20〜0.34 H）。L は c に沿ってならした上側の包絡。
          列は元の行の弧長の割合のまま型の上に置く（列の並び・UV の割合を保つ）。列 0〜17 の平らな海は元の列 0 から新しい足まで等分。
        背は原画視点では輪郭（頂のすぐ後ろ）を除いて見えないので、後の edgefit で輪郭だけを合わせ直す（Q21 の側の縁）。"""
        p = self.d["back_shell"]
        c = self.c
        nu = A.shape[1]
        W = ramp(c, *p["rows_ramp_c"])
        jB, jc = KC.LM["j_B"], int(p["crest_col"])
        m = float(p["m"])
        H = Y[:, jc].copy()
        ac = A[:, jc].copy()
        L0 = ac - A[:, jB]
        uu = np.linspace(0, 1, 801)
        fu = uu ** m * (1 + m * (1 - uu))
        tau = float(p["wall_tau"])
        Lneed = np.zeros(len(c))
        for r in range(len(c)):
            if W[r] <= 1e-4 or H[r] < 0.3:
                continue
            # 管の内側の壁：列 200..379 のうち、各高さでの最も後ろの a
            ta_, ty_ = A[r, 200:380], Y[r, 200:380]
            hs = np.linspace(0.05 * H[r], 0.97 * H[r], 40)
            wall = np.full(len(hs), np.inf)
            for k in range(len(ta_) - 1):
                y0, y1 = ty_[k], ty_[k + 1]
                lo, hi = min(y0, y1), max(y0, y1)
                mm = (hs >= lo) & (hs <= hi) & (hi > lo)
                if mm.any():
                    t = (hs[mm] - y0) / (y1 - y0)
                    wall[mm] = np.minimum(wall[mm], ta_[k] + t * (ta_[k + 1] - ta_[k]))
            tmin = tau * H[r]
            # 型の背の各高さの a：a = ac − L (1 − u(y))、u(y) は f の逆
            ui = np.interp(hs / H[r], fu, uu)
            ok = np.isfinite(wall)
            if ok.any():
                # ac − L(1−u) ≤ wall − tmin  →  L ≥ (ac − wall + tmin)/(1 − u)
                need = (ac[r] - wall[ok] + tmin) / np.maximum(1 - ui[ok], 0.03)
                Lneed[r] = float(max(need.max(), 0.0))
        Lt = np.maximum(np.clip(p["kappa"] * H, p["L_min_m"], p["L_max_m"]), Lneed)
        dcm = c[:, None] - c[None, :]
        K = np.exp(-0.5 * (dcm / p["smooth_c_m"]) ** 2) * np.gradient(c)[None, :]
        K /= K.sum(1, keepdims=True)
        Ls = Lt.copy()
        for _ in range(30):          # ならした上側の包絡（どの行でも Lt 以上）
            Ls = np.maximum(K @ Ls, Lt)
        Ls = K @ Ls
        Ls = np.maximum(Ls, Lt)
        A1, Y1 = A.copy(), Y.copy()
        for r in range(len(c)):
            if W[r] <= 1e-4 or H[r] < 0.3:
                continue
            L = Ls[r]
            ta = ac[r] - L * (1 - uu); ty = H[r] * fu
            ts = KC.arclen(ta, ty)
            s0 = KC.arclen(A[r, jB:jc + 1], Y[r, jB:jc + 1])
            frac = s0 / s0[-1]
            na = np.interp(frac * ts[-1], ts, ta)
            ny = np.interp(frac * ts[-1], ts, ty)
            a0 = A[r, 0]
            sea_a = np.linspace(min(a0, na[0] - 0.5), na[0], jB + 1)
            newA = A[r].copy(); newY = Y[r].copy()
            newA[:jB + 1] = sea_a; newY[:jB + 1] = 0.0
            newA[jB:jc + 1] = na; newY[jB:jc + 1] = ny
            A1[r] = W[r] * newA + (1 - W[r]) * A[r]
            Y1[r] = W[r] * newY + (1 - W[r]) * Y[r]
        self.back_shell_record = [(round(float(c[r]), 2), round(float(L0[r]), 2), round(float(Lneed[r]), 2), round(float(Ls[r]), 2), round(float(H[r]), 2))
                                  for r in range(0, len(c), 4) if W[r] > 1e-4]
        i0 = int(np.argmin(abs(c)))
        self.say("back_shell: m %.2f kappa %.2f tau %.2f, L old/need/new at c=0: %.2f / %.2f / %.2f, rows %s" % (
            m, p["kappa"], tau, float(L0[i0]), float(Lneed[i0]), float(Ls[i0]), p["rows_ramp_c"]))
        return A1, Y1

    # ------------------------------------------------------------ 奥の端の後ろへの引きを減らす（Q21 の「真上から見て後ろへ引かれたふくらみ」）
    def sky_rays_px(self, step=4, box=(640, 0, 1762, 800)):
        if getattr(self, "_skypx", None) is None:
            import kh_gate_lf as KG
            g = KG.LFGate()
            sky = g.truth.cov["sky_envelope"]
            ys, xs = np.mgrid[box[1]:box[3]:step, box[0]:box[2]:step]
            m = sky[ys, xs] > 0.5
            self._skypx = np.stack([xs[m], ys[m]], -1).astype(float)
        return self._skypx

    def far_shift(self, A, Y):
        """奥の行（c > +1.5）を、原画視点の空（管の口と唇の上の空）の射線に触れない範囲で前（+a）へ動かす。
        行ごとに許される最大の量を探し（空の射線の交点が行の水の多角形に入らない、余裕 margin）、c に沿ってならした下側の包絡を採る。"""
        p = self.d["far_shift"]
        c = self.c
        W = ramp(c, *p["rows_ramp_c"])
        px = self.sky_rays_px()
        allowed = np.zeros(len(c))
        for r in range(len(c)):
            if W[r] <= 1e-4 or Y[r].max() < 0.3:
                continue
            tr, _ = F.ray_row_trace(px, c[r])
            ok = (tr[:, 1] > 0.05) & (tr[:, 1] < 30) & (tr[:, 0] > -60) & (tr[:, 0] < 60)
            q = tr[ok]
            poly = np.stack([A[r], Y[r]], -1)
            poly = np.vstack([poly, [[A[r, -1], -0.01], [A[r, 0], -0.01]]])
            best = 0.0
            for d in np.arange(0.0, p["max_m"] + 1e-9, 0.25):
                test = poly + np.array([d + p["margin_m"], 0.0])
                if inside_any(test, q) or inside_any(poly + np.array([d, 0.0]), q + np.array([0.0, -p["margin_m"]])):
                    break
                best = d
            allowed[r] = best
        # 下側の包絡をならす：ならした値が許される値を超えないように、ならす→min を繰り返す
        tgt = np.minimum(allowed, p["max_m"]) * (W > 1e-4)
        dcm = c[:, None] - c[None, :]
        K = np.exp(-0.5 * (dcm / p["smooth_c_m"]) ** 2) * np.gradient(c)[None, :]
        K /= K.sum(1, keepdims=True)
        v = tgt.copy()
        for _ in range(30):
            v = np.minimum(K @ v, tgt)
        shift = W * v * p.get("gain", 1.0)
        A1 = A + shift[:, None]
        self.far_shift_record = [(round(float(c[r]), 3), round(float(allowed[r]), 2), round(float(shift[r]), 3)) for r in range(len(c)) if W[r] > 1e-4]
        self.say("far_shift: max allowed %.2f m, applied max %.2f m (c %.1f)" % (float(allowed.max()), float(shift.max()), float(c[int(np.argmax(shift))])))
        return A1, Y

    # ------------------------------------------------------------ 頂を丸め直す（顔の入れ替えの後。頂の位置と高さはそのまま、折れを消す）
    def apex_round(self, A, Y, p=None, name="apex_round"):
        """各行（W(c)）で、列 j0〜j1 を、2 本の 3 次エルミート曲線（列 j0 の点と接線 → 今の頂（その行の最も高い点、接線は水平）→ 列 j1 の点と接線）で
        置き直す。頂の位置と高さは変えないので原画視点の輪郭はほぼそのまま（残りは edgefit）、頂の尖り（稜の線の折れ）だけを消す（Q17）。"""
        p = p or self.d["apex_round"]
        c = self.c
        W = ramp(c, *p["rows_ramp_c"])
        j0, j1 = int(p["j0"]), int(p["j1"])
        ts_ = float(p["tan_scale"])
        A1, Y1 = A.copy(), Y.copy()

        def herm(Pa, Ta, Pb, Tb, n):
            L = np.linalg.norm(Pb - Pa)
            t = np.linspace(0, 1, n)[:, None]
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
            return h00 * Pa + h10 * L * ts_ * Ta + h01 * Pb + h11 * L * ts_ * Tb
        n = 0
        for r in range(len(c)):
            if W[r] <= 1e-4 or Y[r].max() < 1.0:
                continue
            a, y = A[r], Y[r]
            jm = j0 + 2 + int(np.argmax(y[j0 + 2:j1 - 2]))
            # 二次で頂を補う
            y0_, y1_, y2_ = y[jm - 1], y[jm], y[jm + 1]
            den = y0_ - 2 * y1_ + y2_
            t = float(np.clip(0.5 * (y0_ - y2_) / den, -1, 1)) if abs(den) > 1e-12 else 0.0
            am = float(np.interp(jm + t, np.arange(len(a)), a)); ym = y1_ - 0.25 * (y0_ - y2_) * t
            P0 = np.array([a[j0], y[j0]]); P1 = np.array([a[j1], y[j1]])
            T0 = np.array([a[j0 + 1] - a[j0 - 1], y[j0 + 1] - y[j0 - 1]]); T0 /= np.linalg.norm(T0)
            T1 = np.array([a[j1 + 1] - a[j1 - 1], y[j1 + 1] - y[j1 - 1]]); T1 /= np.linalg.norm(T1)
            Pf = np.array([am, ym])
            cur = np.vstack([herm(P0, T0, Pf, np.array([1.0, 0.0]), 300), herm(Pf, np.array([1.0, 0.0]), P1, T1, 300)[1:]])
            cs = KC.arclen(cur[:, 0], cur[:, 1])
            s0 = KC.arclen(a[j0:j1 + 1], y[j0:j1 + 1])
            frac = s0 / s0[-1]
            na = np.interp(frac * cs[-1], cs, cur[:, 0]); ny = np.interp(frac * cs[-1], cs, cur[:, 1])
            A1[r, j0:j1 + 1] = W[r] * na + (1 - W[r]) * a[j0:j1 + 1]
            Y1[r, j0:j1 + 1] = W[r] * ny + (1 - W[r]) * y[j0:j1 + 1]
            n += 1
        self.say("%s: rows %d, cols %d..%d, tan_scale %.2f, max |dY| %.3f" % (name, n, j0, j1, ts_, float(np.abs(Y1 - Y).max())))
        return A1, Y1

    # ------------------------------------------------------------ 第1回の採用の形：頂の弧を組み直して、輪郭を描く点を前の唇の上面へ移す
    def face_swap_arc(self, A, Y):
        """肩の行（W(c)）で、列 j0〜j1（背の上部 → 頂 → 唇の上面の前半。b区域の谷と稜より手前）を、
        2 本の 3 次エルミート曲線（列 j0 の点と接線 → 新しい頂（接線は水平）→ 列 j1 の点と接線）で組み直す。
          新しい頂の a：a_f(c) = a_c(c) + fwd(c)（fwd = W(c)·fwd_m）。
          新しい頂の高さ：組み直した曲線が、その行の視錐の跡（原画の射線の面）に下から接する高さ（行ごとに 1 次元で解く）。
        頂は丸い弧のまま（折れを作らない。Q17）前へ出て、左の外輪郭 78・130・131 はこの前の頂（唇の上面）が描く。元の背の頂（列 90 の辺り）は
        新しい曲線の上り坂の途中になり、射線の面より下に隠れる（FACE-SWAP）。列は元の行の弧長の割合のまま置き直す（列の並びと UV の割合を保つ）。
        跡のない行（原画の枠の外）は高さを元のまま（c に沿って内挿）。頂の高さの列は c に沿って「ならす → 各行の接する高さとの min」を繰り返し、
        どの行も射線の面を越えないようにする。"""
        p = self.d["face_swap_arc"]
        c = self.c
        W = ramp(c, *p["rows_ramp_c"])
        j0, j1, jc = int(p["j0"]), int(p["j1"]), int(p["crest_col"])
        fwd = W * p["fwd_m"]
        H0 = Y[:, jc].copy()
        ts_ = float(p["tan_scale"])

        def herm(Pa, Ta, Pb, Tb, n):
            L = np.linalg.norm(Pb - Pa)
            t = np.linspace(0, 1, n)[:, None]
            h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
            return h00 * Pa + h10 * L * ts_ * Ta + h01 * Pb + h11 * L * ts_ * Tb

        def curve(r, yf):
            a, y = A[r], Y[r]
            P0 = np.array([a[j0], y[j0]]); P1 = np.array([a[j1], y[j1]])
            T0 = np.array([a[j0 + 1] - a[j0 - 1], y[j0 + 1] - y[j0 - 1]]); T0 /= np.linalg.norm(T0)
            T1 = np.array([a[j1 + 1] - a[j1 - 1], y[j1 + 1] - y[j1 - 1]]); T1 /= np.linalg.norm(T1)
            Pf = np.array([a[jc] + fwd[r], yf])
            seg1 = herm(P0, T0, Pf, np.array([1.0, 0.0]), 300)
            seg2 = herm(Pf, np.array([1.0, 0.0]), P1, T1, 300)
            return np.vstack([seg1, seg2[1:]])

        ytouch = np.full(len(c), np.nan)
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            tr, _ = F.ray_row_trace(self.lead_px, c[r])
            if not p.get("solve_touch", True):
                u_ = row_trace_bound(tr, np.array([A[r, jc] + fwd[r]]))[0]
                if np.isfinite(u_):
                    ytouch[r] = u_ - p["margin_m"]
                continue
            yf = H0[r] + 1.5
            got = False
            for it in range(8):
                cur = curve(r, yf)
                ub = row_trace_bound(tr, cur[:, 0])
                m = np.isfinite(ub)
                if not m.any():
                    break
                viol = float((cur[m, 1] - ub[m]).max())
                got = True
                if abs(viol) < 0.005:
                    break
                yf -= viol
            if got:
                ytouch[r] = yf - p["margin_m"]
        ok = np.isfinite(ytouch) & (W > 1e-4)
        # 高さそのものではなく、元の頂からの差 δ = y_touch − H0 を c に沿ってならす（1 回）。ならした値は各行の接する差を超えない（min）。
        delta = np.zeros(len(c))
        if ok.sum() >= 2:
            delta = np.interp(c, c[ok], (ytouch - H0)[ok])
        dcm = c[:, None] - c[None, :]
        K = np.exp(-0.5 * (dcm / p["smooth_c_m"]) ** 2) * np.gradient(c)[None, :]
        K /= K.sum(1, keepdims=True)
        ds = K @ delta
        ds = np.where(ok, np.minimum(ds, ytouch - H0), ds)
        yfs = H0 + ds
        A1, Y1 = A.copy(), Y.copy()
        rec = []
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            a, y = A[r], Y[r]
            # 頂の高さ：W で元の頂へ戻す
            yf = W[r] * yfs[r] + (1 - W[r]) * H0[r]
            cur = curve(r, yf)
            cs = KC.arclen(cur[:, 0], cur[:, 1])
            s0 = KC.arclen(a[j0:j1 + 1], y[j0:j1 + 1])
            frac = s0 / s0[-1]
            A1[r, j0:j1 + 1] = np.interp(frac * cs[-1], cs, cur[:, 0])
            Y1[r, j0:j1 + 1] = np.interp(frac * cs[-1], cs, cur[:, 1])
            rec.append((round(float(c[r]), 2), round(float(fwd[r]), 2), round(float(H0[r]), 3), round(float(yf), 3),
                        None if not ok[r] else round(float(ytouch[r]), 3)))
        if p.get("smooth_disp_c_m", 0) > 0:
            # 行ごとの組み直しの細かい揺れ（行と行の間の縞）を消す：変位（新 − 元）を c に沿って σ、列に沿って σ_j でならす
            from scipy.ndimage import gaussian_filter1d
            DA, DY = A1 - A, Y1 - Y
            Kd = np.exp(-0.5 * (dcm / p["smooth_disp_c_m"]) ** 2) * np.gradient(c)[None, :]
            Kd /= Kd.sum(1, keepdims=True)
            DA = gaussian_filter1d(Kd @ DA, p.get("smooth_disp_cols", 3.0), axis=1)
            DY = gaussian_filter1d(Kd @ DY, p.get("smooth_disp_cols", 3.0), axis=1)
            A1, Y1 = A + DA, Y + DY
        self.fs_record = {"rows_c_fwd_H0_apex_touch": rec, "method": "face_swap_arc (Hermite apex, touching the painting ray sheet from below)"}
        d_ = [x[3] - x[2] for x in rec]
        self.say("face_swap_arc: rows %d, fwd max %.2f m, apex - old crest min/max %.2f/%.2f m" % (len(rec), float(fwd.max()), min(d_), max(d_)))
        return A1, Y1

    # ------------------------------------------------------------ 第1回の採用の形：丸いまま頂を前へ送る顔の入れ替え
    def face_swap_round(self, A, Y):
        """肩の行で、背の頂の帯を下げ（δ）、頂より前の唇の上面をなめらかな傾き k·s(a − a_c) で持ち上げる：
             Δy(j) = W(c)·[ −δ(c)·wc(j) + k(c)·s(a_j − a_c)·wl(j) ]、 s(x) = (x + sqrt(x² + b²))/2
        s は頂の後ろで 0、前で x に近づくなめらかな関数（曲率 ≤ 2/b² の上向きだけを足す）なので、頂は弧のまま前へ移る（Q17：直角にしない）。
        k は行ごとに「唇の上面が、その行の視錐の跡（原画の射線の面）にちょうど接する」値を解いて c に沿ってならす。
        δ は背の頂の帯が射線の面より margin 下になる値（上限つき）。以後、左の外輪郭 78・130・131 を描くのは前の唇の上面になり、
        背の頂は射線の面の下へ隠れる（FACE-SWAP）。"""
        p = self.d["face_swap_round"]
        c = self.c
        nu = A.shape[1]
        j = np.arange(nu, dtype=float)
        W = ramp(c, *p["rows_ramp_c"])
        wc = col_window(nu, *p["crest_cols_ramp"])
        wl = col_window(nu, *p["lift_cols_ramp"])
        jc = int(p["crest_col"])
        b = float(p["soft_b_m"])
        k_row = np.zeros(len(c)); d_row = np.zeros(len(c))
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            tr, _ = F.ray_row_trace(self.lead_px, c[r])
            a, y = A[r], Y[r]
            ac = a[jc]
            ub = row_trace_bound(tr, a)
            band = (j >= jc - 25) & (j <= jc + 5) & np.isfinite(ub)
            d = 0.0
            if band.any():
                d = float(np.clip(p["crest_margin_m"] - (ub - y)[band].min(), 0.0, p["crest_drop_max_m"]))
            d_row[r] = d
            y2 = y - d * wc
            sx = 0.5 * ((a - ac) + np.sqrt((a - ac) ** 2 + b * b))
            sel = (j > jc) & (j <= p["lip_search_cols"][1]) & (j >= p["lip_search_cols"][0]) & np.isfinite(ub) & (wl * sx > 0.3)
            if sel.any():
                kk = (ub[sel] - y2[sel]) / (wl[sel] * sx[sel])
                k_row[r] = float(np.clip(kk.min(), p["k_min"], p["k_max"]))
        dcm = c[:, None] - c[None, :]
        K = np.exp(-0.5 * (dcm / p["param_smooth_c_m"]) ** 2) * np.gradient(c)[None, :]
        m_ = (W > 1e-4).astype(float)
        k_s = (K @ (k_row * m_)) / np.maximum(K @ m_, 1e-9) * m_
        d_s = (K @ (d_row * m_)) / np.maximum(K @ m_, 1e-9) * m_
        A1, Y1 = A.copy(), Y.copy()
        rec = []
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            a = A[r]; ac = a[jc]
            sx = 0.5 * ((a - ac) + np.sqrt((a - ac) ** 2 + b * b))
            Y1[r] = Y[r] + W[r] * (-d_s[r] * wc + k_s[r] * sx * wl)
            rec.append((round(float(c[r]), 3), round(float(W[r] * d_s[r]), 3), round(float(W[r] * k_s[r]), 4)))
        self.fs_record = {"rows_c_drop_k": rec, "formula": "dy = W(c) [ -drop wc(j) + k s(a - a_crest) wl(j) ], s(x) = (x + sqrt(x^2 + b^2))/2"}
        self.say("face_swap_round: rows %d, drop max %.2f m, k max %.3f" % (len(rec), float((W * d_s).max()), float((W * k_s).max())))
        return A1, Y1

    # ------------------------------------------------------------ 奥の端を細くする（背を頂の側へ寄せる）
    def far_slim(self, A, Y):
        """奥の行（c > +2）の背（列 18〜90）を、頂の a へ向けて係数 s(c) で縮める（背の足が前へ来る。高さはそのまま）。
        F04（横の厚み・奥の体積）と、後ろから見た奥の端の太い塊を減らす。列 0〜18 の平らな海は足の新しい位置へ付け直す。"""
        p = self.d["far_slim"]
        c = self.c
        nu = A.shape[1]
        W = ramp(c, *p["rows_ramp_c"])
        s = 1.0 - (1.0 - p["factor"]) * W
        jc = int(p["crest_col"])
        A1 = A.copy()
        jb = KC.LM["j_B"]
        for r in range(len(c)):
            if W[r] <= 1e-4:
                continue
            ac = A[r, jc]
            # 列 jb..jc：頂からの距離を縮める。頂の近く（列 jc-10..jc）は滑らかに 1 へ戻す
            jj = np.arange(0, jc + 1)
            t = smoothstep((jc - jj) / 12.0)          # 0 at crest, 1 from 12 cols behind
            fac = 1.0 - (1.0 - s[r]) * t
            A1[r, :jc + 1] = ac + (A[r, :jc + 1] - ac) * fac
        self.say("far_slim: factor %.2f rows %s" % (p["factor"], p["rows_ramp_c"]))
        return A1, Y

    # ------------------------------------------------------------ 原画視点の輪郭を側の縁で合わせる（faceswap_edgefit）
    def edgefit(self, A, Y, p):
        import faceswap_edgefit as EF
        if not hasattr(self, "_ef"):
            self._ef = EF.EdgeFit()
        c = self.c
        rows_mask = None
        if "rows_c" in p:
            rows_mask = (c >= p["rows_c"][0]) & (c <= p["rows_c"][1])
        cols_mask = None
        if "cols" in p:
            j = np.arange(A.shape[1])
            cols_mask = np.broadcast_to(((j >= p["cols"][0]) & (j <= p["cols"][1])).astype(float), A.shape).copy()
        A, Y = self._ef.run(c, A, Y, p["segments"], iters=int(p["iters"]), log=self.say, sigma_c=p.get("sigma_c", 0.9),
                            sigma_s=p.get("sigma_s", 0.9), damp=p.get("damp", 0.7), max_move=p.get("max_move", 0.4),
                            tang_max=p.get("tang_max", 0.45), rows_mask=rows_mask, cols_mask=cols_mask, weights=p.get("weights"),
                            seg_kw=p.get("seg_kw"))
        return A, Y

    # ------------------------------------------------------------ 行の中（列の向き）のならし：頂を丸く保つ（Q17）
    def col_smooth(self, A, Y, p, name):
        from scipy.ndimage import gaussian_filter1d
        c = self.c
        wr = ramp(c, *p["rows_ramp_c"])
        wc = col_window(A.shape[1], *p["cols_ramp"])
        A1, Y1 = A.copy(), Y.copy()
        for it in range(int(p.get("passes", 1))):
            As = gaussian_filter1d(A1, p["sigma_cols"], axis=1, mode="nearest")
            Ys = gaussian_filter1d(Y1, p["sigma_cols"], axis=1, mode="nearest")
            Wm = wr[:, None] * wc[None, :]
            A1 = A1 * (1 - Wm) + As * Wm
            Y1 = Y1 * (1 - Wm) + Ys * Wm
        self.say("%s: sigma %.1f cols, rows %s, cols %s, max |dY| %.3f" % (name, p["sigma_cols"], p["rows_ramp_c"], p["cols_ramp"], float(np.abs(Y1 - Y).max())))
        return A1, Y1

    # ------------------------------------------------------------ 原画視点の輪郭を、なめらかな B スプラインの場で合わせる（faceswap_bsfit）
    def bsfit(self, A, Y, p, name):
        import faceswap_bsfit as BS
        import faceswap_edgefit as EF
        if not hasattr(self, "_ef"):
            self._ef = EF.EdgeFit()
        fit = BS.BSFit(self._ef, self.c, A, Y, p["rows_c"], p["cols"], p["n_c"], p["n_j"], p["segments"], p.get("weights"))
        A1, Y1, th, hist = fit.solve(iters=p.get("iters", 5), lam=p.get("lam", 2.0), smooth=p.get("smooth", 4.0), log=self.say,
                                     max_step_m=p.get("max_step_m", 0.8))
        setattr(self, "bsfit_record_" + name, {"theta_shape": list(fit.shape), "theta": th.round(4).tolist(), "history": hist})
        self.say("%s: params %d, max |phi| %.3f m" % (name, th.size, float(np.abs(th).max())))
        return A1, Y1

    # ------------------------------------------------------------ 領域のならし（背・奥の端など）
    def region_smooth(self, A, Y, p, name):
        c = self.c
        wr = ramp(c, *p["rows_ramp_c"])
        wc = col_window(A.shape[1], *p["cols_ramp"])
        A1, Y1 = A, Y
        for it in range(int(p.get("passes", 1))):
            A1 = smooth_along_c(c, A1, p["sigma_c_m"], wr, wc)
            Y1 = smooth_along_c(c, Y1, p["sigma_c_m"], wr, wc)
        self.say("%s: sigma %.2f m rows %s cols %s passes %d, max |dY| %.3f" % (name, p["sigma_c_m"], p["rows_ramp_c"], p["cols_ramp"],
                                                                         int(p.get("passes", 1)), float(np.abs(Y1 - Y).max())))
        return A1, Y1

    # ------------------------------------------------------------ 4. 奥の端
    def far_smooth(self, A, Y):
        p = self.d["far_smooth"]
        c = self.c
        wr = ramp(c, *p["rows_ramp_c"])
        wc = col_window(A.shape[1], *p["cols_ramp"])
        A1, Y1 = A, Y
        for it in range(int(p.get("passes", 1))):
            A1 = smooth_along_c(c, A1, p["sigma_c_m"], wr, wc)
            Y1 = smooth_along_c(c, Y1, p["sigma_c_m"], wr, wc)
        self.say("far_smooth: sigma %.2f m rows %s cols %s, max |dY| %.3f" % (p["sigma_c_m"], p["rows_ramp_c"], p["cols_ramp"], float(np.abs(Y1 - Y).max())))
        return A1, Y1


def load_design(path):
    """設計（名前の付いた値）を読む：.json か、DESIGN という辞書を持つ .py（リポジトリに置く設計は faceswap_design_r1.py）。"""
    if path.endswith(".py"):
        import importlib.util
        spec = importlib.util.spec_from_file_location("fs_design", path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return json.loads(json.dumps(m.DESIGN))
    return json.load(open(path, encoding="utf-8"))


def main():
    dpath, pref = sys.argv[1], sys.argv[2]
    d = load_design(dpath)
    t0 = time.time()
    B = Builder(d)
    c, A, Y = B.build()
    os.makedirs(os.path.dirname(pref), exist_ok=True)
    prov = {"generator": "Tools/GWWaveGen/kstar_p28/faceswap_build.py", "design": os.path.abspath(dpath),
            "design_sha256": KC.sha256(dpath), "input_rows": F.R4_ROWS, "input_rows_sha256": KC.sha256(F.R4_ROWS),
            "reference_model_read": False, "log": B.log}
    meta = KC.write_candidate(pref, c, A, Y, prov)
    rec = {"design_file": os.path.abspath(dpath), "design": d, "log": B.log,
           "face_swap": getattr(B, "fs_record", None), "uncross_lip": getattr(B, "uncross_record", None),
           "bsfit": {k[len("bsfit_record_"):]: v for k, v in B.__dict__.items() if k.startswith("bsfit_record_")},
           "seconds": round(time.time() - t0, 1)}
    json.dump(rec, open(pref + "_build_record.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print("written", pref, "%.1fs" % (time.time() - t0), meta["files"]["gwb_sha256"][:12])


if __name__ == "__main__":
    main()
