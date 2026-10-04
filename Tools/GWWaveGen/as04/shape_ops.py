# -*- coding: utf-8 -*-
"""美術の見本04 の形づくりの操作（行ごとの断面 (a, y) の作り直し。行の c・格子・目印の列・境の輪は変えない）。

op_bulge（S8）：出っ張りの行（c −10.2〜−6.2 m）の唇を、頂から唇の先まで一つの凸の弧にし（外の面の棚・折れをなくす）、
  唇の下の面（内の面の弧の上の部分）をその弧の下 t m まで持ち上げて、薄い一枚の唇にする。原画視点で見える唇の外の面は、
  内の面の弧の t m 外の同じ弧の上に乗る（出っ張り・折り重なりがない）。頂（列 ≤ 100）と、関門 72 の行（≥ 130）の唇の先は動かさない。
op_left（S9・S10）：左の白（行 77〜101 の頂）を原画の青い楔の下の縁まで下げ、c −18 m から c −26 m で頂を海の高さへ下ろし、それより左を海にする。
op_layers（S11）：② 肩の房と ③ 小さな低い房を、高さと前後の段で分ける。
"""
import numpy as np
from scipy.ndimage import gaussian_filter1d

import shape_common as S


def resample_by(a, y, frac):
    """折れ線 (a, y) を弧長の割合 frac（0..1、単調）で置き直す。"""
    s = S.arclen(a, y)
    t = frac * s[-1]
    return np.interp(t, s, a), np.interp(t, s, y)


def hermite(P0, T0, P1, T1, n):
    t = np.linspace(0, 1, n)[:, None]
    h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t; h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
    return h00 * P0 + h10 * T0 + h01 * P1 + h11 * T1


def unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


def nearest_on(Pa, Py, qa, qy):
    """点 (qa, qy) の、折れ線 (Pa, Py) の上の最も近い点と、その点での左の法線（進む向きの左）。"""
    best = (1e18, 0, 0.0)
    for k in range(len(Pa) - 1):
        ax, ay = Pa[k], Py[k]; bx, by = Pa[k + 1], Py[k + 1]
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 < 1e-12 else min(max(((qa - ax) * dx + (qy - ay) * dy) / L2, 0.0), 1.0)
        px, py = ax + t * dx, ay + t * dy
        d2 = (qa - px) ** 2 + (qy - py) ** 2
        if d2 < best[0]:
            best = (d2, k, t)
    _, k, t = best
    dx, dy = Pa[k + 1] - Pa[k], Py[k + 1] - Py[k]
    L = max(np.hypot(dx, dy), 1e-12)
    return Pa[k] + t * dx, Py[k] + t * dy, -dy / L, dx / L, k + t


def lip_row(a, y, p):
    """1 行の唇の作り直し（op_bulge の中身）。p：jA（外の弧の始まりの列）、jT（唇の先の列）、t（唇の厚み m）、jR1・jR2（内の面を持ち上げる所 → 元へ戻す所）、
    tan0・tan1（弧の両端の接線の長さ ÷ 弦）。"""
    a = a.copy(); y = y.copy()
    jA, jT = p["jA"], p["jT"]
    PA = np.array([a[jA], y[jA]]); PT = np.array([a[jT], y[jT]])
    TA = unit(np.array([a[jA + 1] - a[jA - 1], y[jA + 1] - y[jA - 1]]))
    TT = unit(np.array([a[jT + 1] - a[jT - 3], y[jT + 1] - y[jT - 3]]))
    ch = np.linalg.norm(PT - PA)
    n = jT - jA + 1
    C = hermite(PA, TA * p["tan0"] * ch, PT, TT * p["tan1"] * ch, 400)
    # 元の列の弧長の割合で置き直す（列の間隔を保つ）
    s0 = S.arclen(a[jA:jT + 1], y[jA:jT + 1]); frac = s0 / s0[-1]
    na, ny = resample_by(C[:, 0], C[:, 1], frac)
    a[jA:jT + 1] = na; y[jA:jT + 1] = ny
    # 内の面（唇の下）を外の弧の下 t m へ持ち上げる（列 jT..jR1 は全部、jR1..jR2 で元へ戻す）
    Oa, Oy = C[:, 0], C[:, 1]
    jR1, jR2 = p["jR1"], p["jR2"]
    for j in range(jT + 1, jR2 + 1):
        qa, qy = a[j], y[j]
        pa_, py_, nla, nly, kk = nearest_on(Oa, Oy, qa, qy)
        # 外の弧の進む向きは頂 → 唇の先。その右（下側）が内
        ta_, ty_ = pa_ + nly * p["t"] * -1 * -1, py_ - nla * p["t"] * -1 * -1
        # 右の法線 = (dy, -dx)/L = (nly·?, ...)：左の法線 (−dy, dx) の反対
        ta_, ty_ = pa_ - nla * p["t"], py_ - nly * p["t"]
        lam = 1.0 if j <= jR1 else float(S.ss((jR2 - j) / max(jR2 - jR1, 1)))
        a[j] = qa + lam * (ta_ - qa); y[j] = qy + lam * (ty_ - qy)
    return a, y


def op_bulge(c, A, Y, p):
    """出っ張りの行の唇を作り直す。重み w(c)：c_full の中で 1、c_blend の外で 0。各行の結果を元と w で混ぜてから、
    行の向き（c）に σ でならした差を足す（行ごとの段・筋を作らない）。"""
    A2 = A.copy(); Y2 = Y.copy()
    cf0, cf1 = p["c_full"]; cb0, cb1 = p["c_blend"]
    w = S.ss((c - cb0) / (cf0 - cb0)) * S.ss((cb1 - c) / (cb1 - cf1))
    dA = np.zeros_like(A); dY = np.zeros_like(Y)
    for i in np.nonzero(w > 1e-4)[0]:
        na, ny = lip_row(A[i], Y[i], p)
        dA[i] = (na - A[i]) * w[i]; dY[i] = (ny - Y[i]) * w[i]
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    # 関門 72 の行（≥ row72）の唇の先の列（≥ 194）と、頂の列（≤ jA）は動かさない
    keep = np.zeros_like(A, bool)
    keep[:, :p["jA"] + 1] = True
    if p.get("row72") is not None:
        keep[p["row72"]:, 194:] = True
    dA[keep] = 0; dY[keep] = 0
    return A + dA, Y + dY, w


def lip_row_arc(a, y, p):
    """案 A：唇の外の面（列 jB..jT）を、内の面の弧（列 jT+jI..300 の折れ線）の t m 外へ置く（薄い一枚の唇が内の面の弧に沿う）。
    列 jA..jB は元から弧の上へなめらかに移す。唇の先の返り（列 jT..jT+jI）は弧の先の点へ丸く寄せる。内の面そのものは変えない。"""
    a = a.copy(); y = y.copy()
    jA, jB, jT, jI = p["jA"], p["jB"], p["jT"], p["jI"]
    ia = a[jT + jI:301][::-1]; iy = y[jT + jI:301][::-1]          # 弧：背の側（列 300）→ 唇の先の側（列 jT+jI）
    sI = S.arclen(ia, iy)
    # 外の点 jB の、弧の上の最も近い所
    _, _, _, _, kB = nearest_on(ia, iy, a[jB], y[jB])
    sB = np.interp(kB, np.arange(len(sI)), sI)
    sT = sI[-1]
    jj = np.arange(jB, jT + 1)
    s0 = S.arclen(a[jB:jT + 1], y[jB:jT + 1]); fr = s0 / max(s0[-1], 1e-9)
    sj = sB + fr * (sT - sB)
    pa = np.interp(sj, sI, ia); py = np.interp(sj, sI, iy)
    ga = np.gradient(ia); gy = np.gradient(iy)
    ta = np.interp(sj, sI, ga); ty = np.interp(sj, sI, gy)
    L = np.maximum(np.hypot(ta, ty), 1e-12)
    # 弧は背 → 唇の先へ進む。外（巻きの中心の反対）は進む向きの左（−ty, ta）
    nla, nly = -ty / L, ta / L
    tt = p["t"] + (p.get("t_root", p["t"]) - p["t"]) * (1 - S.ss(fr / max(p.get("t_root_frac", 0.3), 1e-6)))
    # 唇の先の丸み：先の 6 列は厚みを半円で 0 へ
    na = pa + nla * tt; ny = py + nly * tt
    a[jB:jT + 1] = na; y[jB:jT + 1] = ny
    # 列 jA..jB：元から新しい線へなめらかに（jB での差を、jA で 0 になるように）
    if jB > jA:
        dA0 = na[0] - a0 if False else None
    # 返り（列 jT+1 .. jT+jI-1）：外の先の点から弧の先の点へ直線で
    for k, j in enumerate(range(jT + 1, jT + jI)):
        t = (k + 1) / jI
        a[j] = (1 - t) * a[jT] + t * a[jT + jI]; y[j] = (1 - t) * y[jT] + t * y[jT + jI]
    return a, y


def op_bulge_arc(c, A, Y, p):
    A2 = A.copy(); Y2 = Y.copy()
    cf0, cf1 = p["c_full"]; cb0, cb1 = p["c_blend"]
    w = S.ss((c - cb0) / (cf0 - cb0)) * S.ss((cb1 - c) / (cb1 - cf1))
    dA = np.zeros_like(A); dY = np.zeros_like(Y)
    jA, jB = p["jA"], p["jB"]
    for i in np.nonzero(w > 1e-4)[0]:
        na, ny = lip_row_arc(A[i], Y[i], p)
        da = na - A[i]; dy = ny - Y[i]
        # 列 jA..jB：jB の差を jA へ向けて 0 へ（smoothstep）
        f = S.ss((np.arange(jA, jB + 1) - jA) / max(jB - jA, 1))
        da[jA:jB + 1] = f * da[jB]; dy[jA:jB + 1] = f * dy[jB]
        dA[i] = da * w[i]; dY[i] = dy * w[i]
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    keep = np.zeros_like(A, bool)
    keep[:, :jA + 1] = True
    if p.get("row72") is not None:
        keep[p["row72"]:, 194:] = True
    dA[keep] = 0; dY[keep] = 0
    return A + dA, Y + dY, w


def retract_row(a, y, p):
    """案 R：唇を頂の前へ縮め、内の面の弧を頂のすぐ下まで持ち上げる（巻きの始まりの、張り出しのない凹の面）。
    列 0..jA（背と頂）と列 jK..（巻きの奥の壁・角・前の面）はそのまま。列 jA..jK を一つのなめらかな線で作り直す：
      1. 外の面：頂の前 P(jA) から接線の向きに d_tip m 進んで唇の先（短い外の面、列 jA..jT）
      2. 唇の先の丸み（厚み t、列 jT..jT+jI の半円）
      3. 内の面：唇の先から頂の下を通って P(jK) へ戻る凹の弧（3 次のエルミート、P(jK) の接線に合わせる。列 jT+jI..jK）。
    """
    a = a.copy(); y = y.copy()
    jA, jT, jI, jK = p["jA"], p["jT"], p["jI"], p["jK"]
    PA = np.array([a[jA], y[jA]])
    TA = unit(np.array([a[jA + 2] - a[jA - 2], y[jA + 2] - y[jA - 2]]))
    # 唇の先：接線の向きに d_tip、少し下へ曲げる（dip）
    down = np.array([0.0, -1.0])
    PT = PA + TA * p["d_tip"] + down * p.get("tip_drop", 0.0)
    TT = unit(TA + down * p.get("tip_turn", 0.6))
    C1 = hermite(PA, TA * p["d_tip"], PT, TT * p["d_tip"], 120)
    s0 = S.arclen(a[jA:jT + 1], y[jA:jT + 1]); fr = s0 / max(s0[-1], 1e-9)
    na, ny = resample_by(C1[:, 0], C1[:, 1], fr)
    a[jA:jT + 1] = na; y[jA:jT + 1] = ny
    # 丸み：唇の先の外の点から、内側（右の法線）へ t の半円
    nr = np.array([TT[1], -TT[0]])          # 進む向きの右 = 下・内
    ctr = PT + nr * (p["t"] * 0.5)
    for k, j in enumerate(range(jT + 1, jT + jI + 1)):
        th = np.pi * (k + 1) / jI
        v = -nr * np.cos(th) + TT * np.sin(th)
        q = ctr + v * (p["t"] * 0.5)
        a[j], y[j] = q
    # 内の面：P(jT+jI) から P(jK) へ。始まりの接線は −TT（戻る向き）、終わりは元の P(jK) の接線
    P0 = np.array([a[jT + jI], y[jT + jI]]); P1 = np.array([a[jK], y[jK]])
    T1 = unit(np.array([a[jK + 2] - a[jK - 2], y[jK + 2] - y[jK - 2]]))
    L = np.linalg.norm(P1 - P0)
    C3 = hermite(P0, -TT * L * p.get("k0", 0.9), P1, T1 * L * p.get("k1", 0.9), 300)
    s0 = S.arclen(a[jT + jI:jK + 1], y[jT + jI:jK + 1]); fr = s0 / max(s0[-1], 1e-9)
    na, ny = resample_by(C3[:, 0], C3[:, 1], fr)
    a[jT + jI:jK + 1] = na; y[jT + jI:jK + 1] = ny
    return a, y


def op_retract(c, A, Y, p):
    cf0, cf1 = p["c_full"]; cb0, cb1 = p["c_blend"]
    w = S.ss((c - cb0) / (cf0 - cb0)) * S.ss((cb1 - c) / (cb1 - cf1))
    dA = np.zeros_like(A); dY = np.zeros_like(Y)
    for i in np.nonzero(w > 1e-4)[0]:
        na, ny = retract_row(A[i], Y[i], p)
        dA[i] = (na - A[i]) * w[i]; dY[i] = (ny - Y[i]) * w[i]
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    keep = np.zeros_like(A, bool)
    keep[:, :p["jA"] + 1] = True
    if p.get("row72") is not None:
        keep[p["row72"]:, 194:] = True
    dA[keep] = 0; dY[keep] = 0
    return A + dA, Y + dY, w


def bend_row(a, y, phi, jA, jB, jC, jK):
    """唇を頂のまわりに φ（ラジアン、+ で唇の先が上がる）だけ曲げる。列 jA で 0 → jB で全部 → jC まで全部 → jK で 0。"""
    a = a.copy(); y = y.copy()
    j = np.arange(len(a))
    g = np.zeros(len(a))
    g[(j > jA) & (j < jB)] = S.ss((j[(j > jA) & (j < jB)] - jA) / (jB - jA))
    g[(j >= jB) & (j <= jC)] = 1.0
    m = (j > jC) & (j < jK)
    g[m] = S.ss((jK - j[m]) / (jK - jC))
    ca, cy = a[jA], y[jA]
    th = phi * g
    da, dy = a - ca, y - cy
    a2 = ca + np.cos(th) * da - np.sin(th) * dy
    y2 = cy + np.sin(th) * da + np.cos(th) * dy
    return a2, y2


def op_bend(c, A, Y, p):
    """唇の垂れを減らす（出っ張りの行で唇を上へ曲げる）。φ(c) は c_full で phi、c_blend の外で 0。"""
    cf0, cf1 = p["c_full"]; cb0, cb1 = p["c_blend"]
    w = S.ss((c - cb0) / (cf0 - cb0)) * S.ss((cb1 - c) / (cb1 - cf1))
    A2 = A.copy(); Y2 = Y.copy()
    for i in np.nonzero(w > 1e-4)[0]:
        A2[i], Y2[i] = bend_row(A[i], Y[i], np.radians(p["phi_deg"]) * w[i], p["jA"], p["jB"], p["jC"], p["jK"])
    return A2, Y2, w


def shorten_row(a, y, cut_out, p):
    """唇を短くする：外の面の唇の先から cut_out m（弧長）を切り、内の面の側は、切った外の点に最も近い内の点（列 200..jK）までを切って、
    その間を丸い先（エルミート）でつなぐ。列 jA..jK を新しい線の上へ、元の列の弧長の割合のまま並べ直す。"""
    a = a.copy(); y = y.copy()
    jA, jK, jT = p["jA"], p["jK"], 200
    s = S.arclen(a, y)
    s_out = s[jT] - cut_out
    if s_out <= s[jA] + 0.5:
        s_out = s[jA] + 0.5
    po = np.array([np.interp(s_out, s, a), np.interp(s_out, s, y)])
    # 内の側：列 jT..jK の点で、po に最も近く、かつ唇の先からの弧長が cut_out·k_in 以上
    jj = np.arange(jT, jK)
    d = np.hypot(a[jj] - po[0], y[jj] - po[1]) + p.get("in_bias", 0.0) * (s[jj] - s[jT])
    ok = (s[jj] - s[jT]) >= cut_out * p.get("k_in_min", 0.3)
    d = np.where(ok, d, 1e9)
    ji = jj[int(np.argmin(d))]
    s_in = s[ji]
    pi_ = np.array([a[ji], y[ji]])
    # 接線
    def tang(sq):
        e = 0.15
        return unit(np.array([np.interp(sq + e, s, a) - np.interp(sq - e, s, a), np.interp(sq + e, s, y) - np.interp(sq - e, s, y)]))
    To, Ti = tang(s_out), tang(s_in)
    gap = np.linalg.norm(pi_ - po)
    h = max(gap, 0.3) * p.get("cap_k", 1.6)
    cap = hermite(po, To * h, pi_, Ti * h, 80)
    # 新しい線：jA..s_out の元の線、丸い先、s_in..jK の元の線
    m1 = (s >= s[jA]) & (s <= s_out)
    seg1 = np.c_[np.r_[a[m1], po[0]], np.r_[y[m1], po[1]]]
    m3 = (s >= s_in) & (s <= s[jK])
    seg3 = np.c_[a[m3], y[m3]]
    tn = p.get("t_nose")
    if tn is not None and cut_out > 0.5:
        # 先の厚みを薄くする：丸い先の内の側の始まりを外の面の内側 t_nose の所に置き、そこから元の内の面の弧（先から d_lift m の所）へ、
        # 一つのなめらかな凹の弧（エルミート、始まりは外の面の逆の向き、終わりは元の内の面の向き）でつなぐ。
        # 持ち上げの量は切った長さに比例（行の向きに続くように）
        wcut = float(S.ss(cut_out / max(p.get("cut_full_m", cut_out), 1e-6)))
        s3 = S.arclen(seg3[:, 0], seg3[:, 1])
        dl = min(p.get("d_lift", 6.0), s3[-1] * 0.8)
        kj = int(np.searchsorted(s3, dl))
        PJ = seg3[kj]; TJ = unit(seg3[min(kj + 2, len(seg3) - 1)] - seg3[max(kj - 2, 0)])
        nin = np.array([To[1], -To[0]])                 # 外の面の進む向きの右 = 内
        PN = po + nin * tn
        L = np.linalg.norm(PJ - PN)
        Tn = unit(np.array([-1.0, p.get("nose_up", 0.15)])) if p.get("nose_dir", "back") == "back" else -To
        Cn = hermite(PN, Tn * L * p.get("kn0", 0.8), PJ, TJ * L * p.get("kn1", 0.8), 200)
        # seg3 の 0..kj を新しい弧で置き換え、元と wcut で混ぜる
        fr3 = s3[:kj + 1] / max(s3[kj], 1e-9)
        na, ny = resample_by(Cn[:, 0], Cn[:, 1], fr3)
        seg3[:kj + 1, 0] = seg3[:kj + 1, 0] + wcut * (na - seg3[:kj + 1, 0])
        seg3[:kj + 1, 1] = seg3[:kj + 1, 1] + wcut * (ny - seg3[:kj + 1, 1])
        pi_ = seg3[0].copy()
        Ti = unit(seg3[min(3, len(seg3) - 1)] - seg3[0])
        gap = np.linalg.norm(pi_ - po)
        h = max(gap, 0.3) * p.get("cap_k", 1.6)
        cap = hermite(po, To * h, pi_, Ti * h, 80)
    newc = np.concatenate([seg1, cap[1:-1], seg3])
    # 並べ直し：列 jA..jK の元の弧長の割合。ただし丸い先の付近の列が詰まりすぎないよう、元の割合と一様の割合を半々
    sl = S.arclen(newc[:, 0], newc[:, 1])
    f0 = (s[jA:jK + 1] - s[jA]) / (s[jK] - s[jA])
    f1 = np.linspace(0, 1, jK - jA + 1)
    fr = 0.5 * f0 + 0.5 * f1
    a[jA:jK + 1] = np.interp(fr * sl[-1], sl, newc[:, 0]); y[jA:jK + 1] = np.interp(fr * sl[-1], sl, newc[:, 1])
    return a, y, {"s_out": float(s_out), "ji": int(ji), "gap": float(gap)}


def op_shorten(c, A, Y, p):
    """出っ張りの行の唇を短くする。切る長さ L(c) = cut_m（c_full の中）→ 0（c_blend の外）。"""
    cf0, cf1 = p["c_full"]; cb0, cb1 = p["c_blend"]
    w = S.ss((c - cb0) / (cf0 - cb0)) * S.ss((cb1 - c) / (cb1 - cf1))
    A2 = A.copy(); Y2 = Y.copy(); info = []
    for i in np.nonzero(w > 1e-3)[0]:
        A2[i], Y2[i], inf = shorten_row(A[i], Y[i], p["cut_m"] * w[i], p)
        info.append({"row": int(i), "cut": round(float(p["cut_m"] * w[i]), 2), **{k: (round(v, 2) if isinstance(v, float) else v) for k, v in inf.items()}})
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(A2 - A, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(Y2 - Y, sig, axis=0, mode="nearest")
        A2 = A + dA; Y2 = Y + dY
    return A2, Y2, w, info


def op_left(c, A, Y, H_target, p):
    """左の白を下げ、尾を海へ下ろす（S9・S10）。行ごとの頂の高さ H(c)（列 18〜200 の最大）を H_target(c) まで下げる。
    行の断面を高さの向きに k = H_target/H(c) 倍にする（左の白は下へ押される）。k が小さい行は、断面を平らな海の線（列の a は足から前の足まで等間隔）
    へ寄せる（巻きを潰したときに重ならないように）。k ≥ 1 の行は変えない。"""
    A2 = A.copy(); Y2 = Y.copy()
    Hn = Y[:, S.J_B:S.J_TIP + 1].max(1)
    k = np.clip(H_target / np.maximum(Hn, 1e-6), 0.0, 1.0)
    k = np.where(H_target >= Hn - 1e-4, 1.0, k)
    js = p.get("sea_cols", 18)
    info = []
    for i in np.nonzero(k < 0.9999)[0]:
        a, y = A[i], Y[i]
        # 平らな線：列 js..379 を a[js]..a[379] の等間隔（足の外の海の帯はそのまま）
        jf = S.J_FACEBOT
        af = a.copy()
        af[js:jf + 1] = np.linspace(a[js], a[jf], jf - js + 1)
        f = float(S.ss(k[i] / p.get("k_flat", 0.45)))
        A2[i] = af + (a - af) * f
        y2 = y * k[i] - p.get("sink_m", 0.0) * (1.0 - f) * (np.arange(len(y)) >= js) * (np.arange(len(y)) <= jf)
        kt, km_ = p.get("k_top_only", 2.0), p.get("k_mix", 0.0)
        if p.get("shrink_to_foot") and km_ > 0 and kt - km_ < k[i] < kt + km_:
            # 切り替えの幅の中：両方の下げ方の結果を k で混ぜる
            pa = dict(p); pa["k_mix"] = 0.0
            Hn1 = np.array([Hn[i]]); Ht1 = np.array([H_target[i]])
            pA = dict(pa); pA["k_top_only"] = -1.0          # 頂だけ下げる（k ≥ k_top_only の道）
            pB = dict(pa); pB["k_top_only"] = 2.0           # 背の足へ縮める道
            aA, yA, _ = op_left(c[i:i + 1], A[i:i + 1], Y[i:i + 1], Ht1, dict(pA, sigma_rows=0.0))
            aB, yB, _ = op_left(c[i:i + 1], A[i:i + 1], Y[i:i + 1], Ht1, dict(pB, sigma_rows=0.0))
            wm = float(S.ss((k[i] - (kt - km_)) / (2 * km_)))
            A2[i] = aB[0] + wm * (aA[0] - aB[0]); Y2[i] = yB[0] + wm * (yA[0] - yB[0])
            info.append({"row": int(i), "c": round(float(c[i]), 2), "k": round(float(k[i]), 3), "mode": "mix", "w_top_only": round(wm, 3)})
            continue
        if p.get("shrink_to_foot") and k[i] < p.get("k_top_only", 2.0):
            # 下げが大きい行：断面を背の足（列 js、海の高さ）のまわりに k 倍に縮める（全ての点が後ろ・下へ動く。原画のカメラの側＝前へは出ない）。
            # 前の海の帯（列 jf..399）は、列 399 を止めて比例で並べ直す
            kk = max(float(k[i]), p.get("k_min", 0.03))
            af_ = a[js]
            a2 = a.copy(); y2 = y.copy()
            a2[js:jf + 1] = af_ + kk * (a[js:jf + 1] - af_)
            y2[js:jf + 1] = kk * y[js:jf + 1] - p.get("sink_m", 0.0) * (1.0 - kk)
            kf = p.get("k_flat_foot", 0.15)
            if kk < kf:
                # ほとんど潰れた行：背の足から前の足まで平らな線（海の下 sink_m）へ寄せる（小さく縮めた巻きの輪が、海の帯と交わらないように）
                fl = float(S.ss(kk / kf))
                n_ = jf - js + 1
                fa = np.linspace(a2[js], af_ + max(kk, 0.25) * (a[jf] - af_), n_)
                a2[js:jf + 1] = fa + fl * (a2[js:jf + 1] - fa)
                y2[js:jf + 1] = -p.get("sink_m", 0.0) + fl * (y2[js:jf + 1] + p.get("sink_m", 0.0))
                y2[js] = y[js]
                # 前の海の帯も平らな線の高さへ（帯の谷が平らな線と交わらないように。列 399 は止める）
                y2[jf + 1:-1] = -p.get("sink_m", 0.0) + fl * (y[jf + 1:-1] + p.get("sink_m", 0.0))
            gfr = (a[jf:] - a[-1]) / min(a[jf] - a[-1], -1e-9)
            a2[jf:] = a[-1] + gfr * (a2[jf] - a[-1])
            if not (kk < kf):
                y2[jf + 1:] = y[jf + 1:]
            A2[i] = a2; Y2[i] = y2
            info.append({"row": int(i), "c": round(float(c[i]), 2), "H_now": round(float(Hn[i]), 2), "H_target": round(float(H_target[i]), 2), "k": round(float(k[i]), 3), "mode": "foot"})
            continue
        if k[i] >= p.get("k_top_only", 2.0):
            # 下げが小さい行：頂の側だけを下げる（高さ y0 = top_y0·H より下の唇・前の面は動かさない。原画視点の船・手前の海の前へ出ない）
            Hn_ = Hn[i]; D = Hn_ - H_target[i]
            tc = p.get("top_cols")
            if tc and p.get("fin_guard_m") is not None:
                # 鰭を作らない：下げない唇（列 ≥ tc[1]）の一番上より、下げた頂が fin_guard_m 以上高いままにする
                lipmax = float(y[tc[1]:S.J_FACEBOT].max())
                D = max(0.0, min(D, Hn_ - lipmax - p["fin_guard_m"]))
            y0 = p.get("top_y0", 0.55) * Hn_
            g_ = S.ss((y - y0) / max(Hn_ - y0, 1e-6))
            tc = p.get("top_cols")
            if tc:
                # 列の向きの重み：背と頂（列 ≤ tc[0]）は全部、唇（列 ≥ tc[1]）は下げない（② の房の唇を船・手前の海の射線へ下ろさない）
                jj_ = np.arange(len(y))
                g_ = g_ * (1.0 - S.ss((jj_ - tc[0]) / max(tc[1] - tc[0], 1)))
            y2 = y - D * g_
            A2[i] = a
        y2[:js] = y[:js]
        y2[-1] = y[-1]
        # 前の足の外（列 > 379）と背の足の外（列 < 18）は海の帯：そのまま
        Y2[i] = y2
        info.append({"row": int(i), "c": round(float(c[i]), 2), "H_now": round(float(Hn[i]), 2), "H_target": round(float(H_target[i]), 2), "k": round(float(k[i]), 3), "flat_mix": round(1 - f, 3)})
    # 行の向きにならす（σ 行）。ならすのは差だけ
    sig = p.get("sigma_rows", 0.0)
    if sig > 0:
        A2 = A + gaussian_filter1d(A2 - A, sig, axis=0, mode="nearest"); Y2 = Y + gaussian_filter1d(Y2 - Y, sig, axis=0, mode="nearest")
    return A2, Y2, info


def op_lobe3(c, A, Y, p):
    """③ 最左側の小さな低い房（S11）：c −21〜−14 の行の唇（列 jl0〜jl1 で全部、外へ 0 へ）を、前へ da・下へ dy だけ動かして、
    ② より低く手前に出る房にする。重み w(c) は c_peak のまわりの余弦の窓（半幅 c_half）。"""
    A2 = A.copy(); Y2 = Y.copy()
    u = np.clip(np.abs(c - p["c_peak"]) / p["c_half"], 0, 1)
    w = 0.5 * (1 + np.cos(np.pi * u))
    j = np.arange(A.shape[1])
    j0, j1, j2, j3 = p["cols"]          # 0 → 1 の立ち上がり（j0..j1）、1 → 0 の戻り（j2..j3）
    g = np.zeros(len(j))
    m = (j > j0) & (j < j1); g[m] = S.ss((j[m] - j0) / (j1 - j0))
    g[(j >= j1) & (j <= j2)] = 1.0
    m = (j > j2) & (j < j3); g[m] = S.ss((j3 - j[m]) / (j3 - j2))
    for i in np.nonzero(w > 1e-3)[0]:
        A2[i] = A[i] + w[i] * g * p["da"]
        Y2[i] = Y[i] + w[i] * g * p["dy"]
    return A2, Y2, w


def op_shift3(c, A, Y, p):
    """③ 最左側の小さな低い房（S11）：c −21〜−14 の行の断面を、丸ごと前（+a）へ da・下へ dy（頂の高さの割合で）だけ動かして、
    ② より低く手前の房にする。重み w(c) は c_peak のまわりの余弦の窓（半幅 c_half）。列 0..js の背の海の帯は、列 0 を止めたまま
    新しい足までの間に比例で並べ直す（back_build と同じ）。前の海の帯（列 > 379）は、列 399 を止めたまま並べ直す。"""
    A2 = A.copy(); Y2 = Y.copy()
    u = np.clip(np.abs(c - p["c_peak"]) / p["c_half"], 0, 1)
    w = 0.5 * (1 + np.cos(np.pi * u))
    js, jf = p.get("sea_cols", 18), S.J_FACEBOT
    for i in np.nonzero(w > 1e-3)[0]:
        a, y = A[i].copy(), Y[i].copy()
        d = p["da"] * w[i]
        a2 = a.copy()
        a2[js:jf + 1] = a[js:jf + 1] + d
        # 背の海の帯：列 0 を止めて比例で
        f = (a[:js + 1] - a[0]) / max(a[js] - a[0], 1e-9)
        a2[:js + 1] = a[0] + f * (a2[js] - a[0])
        # 前の海の帯：列 399 を止めて比例で
        g = (a[jf:] - a[-1]) / min(a[jf] - a[-1], -1e-9)
        a2[jf:] = a[-1] + g * (a2[jf] - a[-1])
        H = y[js:S.J_TIP + 1].max()
        y2 = y.copy()
        y2[js:jf + 1] = y[js:jf + 1] * (1.0 - p.get("dy_frac", 0.0) * w[i])
        A2[i], Y2[i] = a2, y2
    return A2, Y2, w
