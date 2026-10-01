# -*- coding: utf-8 -*-
# 仕上げ28：評審（数の判定）の j_dome.py の関数の部分の写し（ドーム・F04・弧の測り）。r2_metrics.py がこのファイルを読む。
# 元：Unity/Build/Polish/28/_judge/numbers/j_dome.py（Git 対象外の評審の作業場所、SHA-256 e3e131fb771df58ddce4b70e542de0d96c74bfd7e27ba4571f8f51daa2491de8）の「res = {}」より前をそのまま写した。
# 写した理由：コミットの一覧を依存で閉じるため（r2_metrics.py が Git 対象外のファイルを読んでいた）。中身は変えていない。
# independent numbers judge for Polish 28 round 1: dome / F04 / arcs measured on the DELIVERED gwb sheets
import sys, os, json, numpy as np
sys.dont_write_bytecode = True
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "rubric"))
import kh_common as KC
import kh_R1_quick as Q
import rubric_measure as RM
from scipy.ndimage import gaussian_filter1d
B = os.path.join(REPO, "Unity", "Build")
CAND = {"R4": B + r"\Design\28R01F\kstar_final\kstarR4_a45.gwb",
        "RAYS": B + r"\Polish\28\r1_rays\cand\kstarP28R1_a45.gwb",
        "FS1": B + r"\Polish\28\r1_faceswap\candidate\kstarFS1_a45.gwb",
        "BF": B + r"\Polish\28\r1_backfirst\v4\candidate\kstarP28bf_a45.gwb",
        "K26R01": B + r"\Polish\28\r1_backfirst\v4\eval\Kstar26R01\Kstar26R01_render.gwb"}
OUT = os.path.join(B, "Polish", "28", "_judge", "numbers")


def load(p):
    G = KC.read_gwb(p)
    S = KC.sec(G["X"]).reshape(G["nv"], G["nu"], 3)
    return S[..., 2].mean(1), S[..., 0], S[..., 1], G["X"].reshape(G["nv"], G["nu"], 3)


def pct(v, q):
    v = np.asarray(v, float); v = v[np.isfinite(v)]
    return round(float(np.percentile(v, q)), 3) if len(v) else None


def back_contours(c, A, Y, hs):
    nv = len(c); H = Y.max(1); top = Y.argmax(1); res = {}
    for h in hs:
        ab = np.full(nv, np.nan)
        for r in range(nv):
            if H[r] < h + 0.3:
                continue
            yy = Y[r, :top[r] + 1]; aa = A[r, :top[r] + 1]
            i = np.nonzero(yy >= h)[0]
            if len(i) == 0:
                continue
            i = i[0]
            if i == 0:
                ab[r] = aa[0]; continue
            t = (h - yy[i - 1]) / (yy[i] - yy[i - 1]); ab[r] = aa[i - 1] + t * (aa[i] - aa[i - 1])
        res[h] = ab
    return res


def chord_sag(c, v, cq, L):
    m = np.isfinite(v)
    if m.sum() < 5:
        return np.full(len(cq), np.nan)
    f = lambda x: np.interp(x, c[m], v[m], left=np.nan, right=np.nan)
    return 0.5 * (f(cq - L) + f(cq + L)) - f(cq)   # >0: the centre lies at a smaller value than the chord


def curv(c, X, sig=1.0):
    Xs = gaussian_filter1d(X, sig, axis=1)
    Xu = np.gradient(Xs, axis=1); Xv = np.gradient(Xs, c, axis=0); Xvv = np.gradient(Xv, c, axis=0)
    Xuu = np.gradient(Xu, axis=1); Xuv = np.gradient(Xu, c, axis=0)
    n = np.cross(Xu, Xv); n /= np.maximum(np.linalg.norm(n, axis=-1), 1e-12)[..., None]
    n = np.where(n[..., 1:2] < 0, -n, n)   # outward on the back = facing up
    kc = -(Xvv * n).sum(-1) / np.maximum((Xv * Xv).sum(-1), 1e-12)   # >0 convex along c (bulging out)
    E = (Xu * Xu).sum(-1); F = (Xu * Xv).sum(-1); G = (Xv * Xv).sum(-1)
    L = -(Xuu * n).sum(-1); M = -(Xuv * n).sum(-1); N = -(Xvv * n).sum(-1)
    K = (L * N - M * M) / np.maximum(E * G - F * F, 1e-12)
    Hm = (E * N - 2 * F * M + G * L) / np.maximum(2 * (E * G - F * F), 1e-12)
    area = np.sqrt(np.maximum(E * G - F * F, 0))
    return kc, K, Hm, area


def arcs(c, A, Y, s=2.0):
    out = []
    for r in range(len(c)):
        a, y = A[r], Y[r]
        if y.max() < 1.0:
            out.append(np.nan); continue
        j = int(np.argmax(y)); P = np.c_[a, y]
        d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        s0 = d[j]
        if s0 - s < 0 or s0 + s > d[-1]:
            out.append(np.nan); continue
        p1 = np.array([np.interp(s0 - s, d, a), np.interp(s0 - s, d, y)]); p2 = np.array([np.interp(s0 + s, d, a), np.interp(s0 + s, d, y)])
        v1 = p1 - P[j]; v2 = p2 - P[j]
        out.append(float(np.degrees(np.arccos(np.clip(v1 @ v2 / np.linalg.norm(v1) / np.linalg.norm(v2), -1, 1)))))
    return np.array(out)


