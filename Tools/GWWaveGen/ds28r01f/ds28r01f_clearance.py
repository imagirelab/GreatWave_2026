# -*- coding: utf-8 -*-
"""設計28修正01 試行F：num_sheet_clearance（数値の条件。水の面が自分を突き抜けない）の計算（numpy だけ）。

行ごとの断面の折れ線を、唇先の列 j_tip（K*′ の目印）で上の面 U（列 j_B+1〜j_tip−1：背・頂・唇の上面）と下の面 L（列 j_tip+1〜j_E−1：
唇の下面・管・内壁・前面）に分ける。列の番号の順に歩くと水はいつも右手にある（背を上り、唇の上面を先へ、唇先で折り返して下面・管の
天井・内壁・前面を下る）ので、U の頂点は L の右手（水の側）に、L の頂点は U の右手に、ある隙間 g 以上離れているのが正しい。
各頂点の、相手の折れ線までの符号付きの距離 c（最も近い点。全部の線分から正確に）を測り、c < g + w の頂点を、その頂点の面の外向きの
法線（水から離れる向き）へ、なめらかな下限 f(c) = g + w − w·tanh((g + w − c)/w)（c ≥ g + w では f = c、C2）との差だけ押す（3 回、押した後に
測り直す）。押す向きを相手の最も近い点の向きにすると、最も近い点が凹んだ角や節をまたぐ時に向きが跳ぶ（開発の試しで 120 Hz の二階差分
0.17〜3.3 m）ので、頂点そのものの法線にした。

押す量に掛ける重み（どれも形の連続な関数。こまの間で押す量が跳ばない）：
  向かい合い ρ：頂点から唇先を回って相手の最も近い点までの折れ線の道のり ÷ 2 点の距離。水を挟んで向かい合う組（背と内壁、薄い唇の
     上面と下面）では道のりが距離よりずっと長く、同じ面の上で隣り合うだけの組（唇ができる前の前面の唇先の近く）では道のりと距離が
     ほぼ同じ。w_face = smoothstep((ρ − ρ0)/(ρ1 − ρ0))。
  深さ：相手の裏側の遠い所（|c| が deep_full〜deep_zero）で 0 へ（符号が意味を持たない所）。
  分け方：背（U の列 < 頂の列 root）とそれに向かう L は背だけを動かす（内壁・管・前面を後ろへ戻さない。P18）。唇の上面と L は半分ずつ。
     境（root の前後 3 列）は smoothstep でつなぐ。
g と w は頂点ごとに、t* の K*′ の同じ頂点の隙間 c_K の割合で上限を置く（g = min(g0, αc_K)、w = min(w0, βc_K)、α + β ≤ 1）ので、
t* の K*′ では c = c_K ≥ g + w で何も動かない（t* = K*′ を保つ）。c_K ≤ 2 mm の頂点は押さない。
"""
import numpy as np


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def closest_on_polyline(P, S0, S1, soft_m=0.15):
    """点 P (n, 2) から折れ線（線分 S0→S1、(m, 2)）への最も近い点（全部の線分から）。
    戻り (距離 (n,), 最も近い点 (n, 2), 右手の法線 (n, 2), 線分の番号 (n,), 線分の中の割合 (n,))。
    closest_on_polyline.soft に、線分ごとの最も近い点を exp(−(d − d_min)/soft_m) で重み付けて平均した点（押す向き用。最も近い点が
    凹んだ角をまたいで跳ぶ時も連続）を置く。"""
    d = S1 - S0                                                   # (m, 2)
    L2 = np.maximum((d * d).sum(-1), 1e-24)
    w = P[:, None, :] - S0[None, :, :]                            # (n, m, 2)
    u = np.clip((w * d[None]).sum(-1) / L2[None], 0.0, 1.0)       # (n, m)
    q = S0[None] + u[..., None] * d[None]
    dist2 = ((P[:, None, :] - q) ** 2).sum(-1)
    T = np.argmin(dist2, 1)
    ii = np.arange(len(P))
    dd = np.sqrt(dist2)
    wgt = np.exp(-(dd - dd[ii, T][:, None]) / soft_m)
    closest_on_polyline.soft = (wgt[..., None] * q).sum(1) / wgt.sum(1)[:, None]
    U = u[ii, T]
    Q = q[ii, T]
    dist = np.sqrt(dist2[ii, T])
    ln = np.sqrt(L2)[:, None]
    nseg = np.stack([d[:, 1], -d[:, 0]], -1) / ln
    n = nseg[T].copy()
    m = len(S0)
    at0 = (U <= 1e-9) & (T > 0)
    at1 = (U >= 1 - 1e-9) & (T < m - 1)
    n[at0] = nseg[T[at0]] + nseg[T[at0] - 1]
    n[at1] = nseg[T[at1]] + nseg[T[at1] + 1]
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    return dist, Q, n, T, U


def _push_dir(P, Q, n, sgn, kappa=0.01):
    """押す向き：最も近い点から頂点への向き（距離の勾配。符号で水の側へ）。距離が 0 に近い所だけ面の法線を足す。
    （面の法線だけでは、最も近い点が折れ線の節と線分の中の間を移る時に向きが跳ぶ）"""
    v = sgn[:, None] * (P - Q) + kappa * n
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


def signed_clearance(A, Y, j_tip, j0, j1, k_tip=3):
    """1 行：U（列 j0+1..j_tip−k_tip）の各頂点の L への、L（j_tip+k_tip..j1−1）の各頂点の U への、符号付きの隙間 c と法線と向かい合い ρ。
    相手の折れ線は唇先の列まで含める。戻り ((iu, cU, nU, rhoU, colU), (il, cL, nL, rhoL, colL))。col は相手の最も近い点の列（小数）。"""
    P = np.stack([A, Y], -1)
    seg = np.hypot(np.diff(A), np.diff(Y))
    S = np.concatenate([[0.0], np.cumsum(seg)])                  # 折れ線の道のり（列 0 から）
    st = S[j_tip]
    # 押す向き：頂点そのものの面の外向きの法線（列の順の左手。水は右手）。形の連続な関数（相手の最も近い点の向きは、最も近い点が
    # 凹んだ角や節をまたぐ時に跳ぶので使わない）
    tg = np.gradient(P, axis=0)
    out_n = np.stack([-tg[:, 1], tg[:, 0]], -1)
    out_n /= np.maximum(np.linalg.norm(out_n, axis=-1, keepdims=True), 1e-12)
    iu = np.arange(j0 + 1, j_tip - k_tip + 1)
    il = np.arange(j_tip + k_tip, j1)
    Lp = P[j_tip:j1]
    Up = P[j0 + 1:j_tip + 1]
    dU, qU, nU, TU, UU = closest_on_polyline(P[iu], Lp[:-1], Lp[1:])
    sU = np.sign(((P[iu] - qU) * nU).sum(-1))
    sU[sU == 0] = 1.0
    nU = out_n[iu]
    colU = j_tip + TU + UU                                        # L の上の最も近い点の列（小数）
    sqU = S[j_tip + TU] + UU * seg[j_tip + TU]
    rhoU = ((st - S[iu]) + (sqU - st)) / np.maximum(dU, 1e-6)
    dL, qL, nL, TL, UL = closest_on_polyline(P[il], Up[:-1], Up[1:])
    sL = np.sign(((P[il] - qL) * nL).sum(-1))
    sL[sL == 0] = 1.0
    nL = out_n[il]
    colL = j0 + 1 + TL + UL                                       # U の上の最も近い点の列（小数）
    sqL = S[j0 + 1 + TL] + UL * seg[j0 + 1 + TL]
    rhoL = ((S[il] - st) + (st - sqL)) / np.maximum(dL, 1e-6)
    return (iu, sU * dU, nU, rhoU, colU), (il, sL * dL, nL, rhoL, colL)


def soft_floor(c, g, w):
    """f(c) = c（c ≥ g + w）、g + w − w·tanh((g + w − c)/w)（それ以下）。f ≥ g、C2。"""
    t = g + w
    x = np.maximum(t - c, 0.0) / np.maximum(w, 1e-12)
    return np.where(c >= t, c, t - w * np.tanh(x))


def gw_from_ref(cK, g0, w0, alpha, beta, c_min=0.002):
    """t* の隙間 c_K から、頂点ごとの g・w。c_K ≤ c_min（K*′ でも隙間がない）の頂点は押さない（g = w = 0）。"""
    ok = cK > c_min
    g = np.where(ok, np.minimum(g0, alpha * cK), 0.0)
    w = np.where(ok, np.minimum(w0, beta * cK), 0.0)
    return g, w


def push_amount(c, rho, g, w, prm):
    """押す量（≥ 0）＝ (f(c) − c) × 向かい合いの重み × 深さの重み。g + w = 0 の頂点は 0。"""
    act = (g + w) > 1e-9
    f = soft_floor(c, g, w)
    d1, d2 = float(prm["deep_full_m"]), float(prm["deep_zero_m"])
    deep = 1.0 - smoothstep((np.maximum(-c, 0.0) - d1) / (d2 - d1))
    r0, r1 = float(prm.get("face_rho0", 1.5)), float(prm.get("face_rho1", 3.0))
    face = smoothstep((rho - r0) / (r1 - r0))
    return np.where(act, (f - c) * deep * face, 0.0)


def apply_row(A, Y, j_tip, j0, j1, ref, prm, iters=None, root=None):
    """1 行の押し。ref = (gU, wU, gL, wL)（signed_clearance の iu・il の並び）。prm：share・deep_full_m・deep_zero_m・k_tip・iters・face_rho0/1。
    root（頂の列）を渡すと、背（U の列 < root）とそれに向かう L は背だけを動かす（境は 6 列の smoothstep）。
    戻り (A', Y', 押した量の最大, 押した頂点の数)。"""
    A = A.copy()
    Y = Y.copy()
    gU, wU, gL, wL = ref
    share = float(prm.get("share", 0.5))
    kt = int(prm.get("k_tip", 3))
    iters = int(prm.get("iters", 3)) if iters is None else iters
    moved = 0.0
    nmv = 0
    for _ in range(iters):
        (iu, cu, nu_, ru, colU), (il, cl, nl_, rl, colL) = signed_clearance(A, Y, j_tip, j0, j1, kt)
        if root is not None:
            back_u = 1.0 - smoothstep((iu - (root - 3.0)) / 6.0)          # 背の頂点ほど 1
            fU = share + (1.0 - share) * back_u
            fL = share * smoothstep((colL - (root - 3.0)) / 6.0)         # 背に向かう L は 0
        else:
            fU = np.full(len(iu), share)
            fL = np.full(len(il), share)
        du = fU * push_amount(cu, ru, gU, wU, prm)
        dl = fL * push_amount(cl, rl, gL, wL, prm)
        if not (np.any(du > 1e-12) or np.any(dl > 1e-12)):
            break
        A[iu] += du * nu_[:, 0]
        Y[iu] += du * nu_[:, 1]
        A[il] += dl * nl_[:, 0]
        Y[il] += dl * nl_[:, 1]      # nu_・nl_ は頂点の外向きの法線（水から離れる向き。相手から遠ざかる）
        moved = max(moved, float(du.max(initial=0.0)), float(dl.max(initial=0.0)))
        nmv = max(nmv, int((du > 1e-9).sum() + (dl > 1e-9).sum()))
    return A, Y, moved, nmv
