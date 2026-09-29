# -*- coding: utf-8 -*-
"""設計28修正01 試行D：依頼の目標（M1〜M4）を、パッケージ（Unity の再生器と同じ Hermite）から測り、試行C の C1 と並べる検査器。

生成器のコードは読まない（パッケージ・時間曲線・K* のフォルダーだけ）。K* は版ごとに ds28r01d_gates.patch_kstar で差し替えて読む。
測るもの（行 159＝主断面、192＝峰の行。t は画面の時刻（その版の既定の時間曲線）、τ は物理の時刻）：
  M1 小山→C 字：前面の回りの角 Θ が 45° を越える画面の時刻から、張り出し Lo が 0.15H を越える画面の時刻まで（Q17 の原型の定義、作業場所
     q17/pace/secmetrics.py と同じ式。前の足の列は K* の j_E）。形の変わる速さ vdef_up（0.3H より上の頂点の、相似の動きを除いた速さの
     RMS）の最大と、その立ち上がり（d vdef_up/dt の最大＝速さの段）。上昇：頂の高さ H(τ) の C1 との差の最大（物理の時刻）、画面の
     0.4 → 0.8 Hf の時間。唇の見える始まり：試行B と同じ（唇先が運びの始まりから前へ 0.5 m、かつ Lo ≥ 0.1H が t* まで続く）の H/Hf。
  M2 唇（巻きの行の jt+1..rim）と管の天井（rim+1..ja−1）のすべての点：自分の頂点（最高点）の後の再上昇（その後の最小からの上がりの最大）と、
     0.25 s の二次の当てはめの上下の加速度の最大（物理の時刻と、画面＝既定の時間曲線、止めるための区間の前まで）。0.05 m/s² を超える点の数。
     試行C の巻き下がりの検査（ds28r01c_curl.row_curl：伸び出しと巻き下がりが一緒か、押し下げが後ろに寄っていないか）。
  M3 前の谷：行 100・130・159・192・214 の、足（列 j_E）から前 30 m の中の最低点の深さ D(τ)（0.1 s おき、τ −8〜0）、t* の D/H、底の足からの距離、
     半分の深さの幅、背後の谷、Spearman ρ(H, D)、D(t*)/max D、D(−3)/D(t*)。台座：t* で前の足の列の組 Δa < 0.05 m・Δy > 0.5 m の数、
     y < 4 m の前面の傾きの最大。座席の船：t* の竜骨の線の下の面の高さと水線（竜骨＋喫水）の差（記録）。
  M4 行の間のジグザグ J1（隣の行と符号が交互の凸凹の割合）と行の間の法線の角の p95（J3）。τ −6〜0。量子化の刻み。背の保持：頂の角 θc の
     τ −1.5〜0 の最小と θc(−1) − θc(0)（行 159・192）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds28r01d/ds28r01d_review.py --tags C1,D --out Unity/Build/Design/28R01D/review/review_D.json
  版は TAGS の表（パッケージ・時間曲線・K*）か --tag-spec 'D2=<pkg>|<warp>|<kstar>|<carry_start_sigma>' で足す。
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for sub in ("ds27", "ds28", "ds28r01b", "ds28r01c"):
    p = os.path.join(REPO, "Tools", "GWWaveGen", sub)
    if p not in sys.path:
        sys.path.insert(0, p)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds27_gates as DG  # noqa: E402
import ds28r01d_gates as DGW  # noqa: E402
import ds28r01d_kstar as KS  # noqa: E402
import ds28r01b_review as RB  # noqa: E402
import ds28r01c_curl as CC  # noqa: E402

RB.HZ = 240
KSTAR_OLD = "Unity/Build/ArtFirst/26修正01/kstar"
TAGS = {
    "C1": dict(pkg="Unity/Build/Design/28R01C/C1/art_on", warp="Tools/GWWaveGen/ds28r01c/timewarp_default_C1.json", kstar=KSTAR_OLD, carry_sigma=-3.45),
    "D": dict(pkg="Unity/Build/Design/28R01D/D/art_on", warp="Tools/GWWaveGen/ds28r01d/timewarp_default_D.json",
              kstar="Unity/Build/Design/28R01D/kstar_foot", carry_sigma=-3.7),
}
ROWS = (159, 192)
TIP = {159: 199, 192: 223}
TROUGH_ROWS = (100, 130, 159, 192, 214)


def r3(x, nd=3):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    return None if not math.isfinite(x) else round(x, nd)


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def open_pkg(spec):
    d = DGW.patch_kstar(spec["kstar"])
    ks = DG.KStar(d)
    pk = DG.Package(absrepo(spec["pkg"]), ks)
    W = json.load(open(absrepo(spec["warp"]), encoding="utf-8"))
    return ks, pk, np.asarray(W["t"], float), np.asarray(W["tau"], float)


def sections_at(pk, ks, taus, rows):
    """行 rows の断面 (nt, nr, nu) の A, Y（局所）。"""
    vidx = np.concatenate([np.arange(r * ks.nu, (r + 1) * ks.nu) for r in rows])
    Xg = pk.sub(np.asarray(taus, float), vidx, 0) - pk.origin(np.asarray(taus, float))[:, None, :]
    Xl = Xg + ks.O[None, None, :]
    A, Y, _ = ks.section(Xl)
    return A.reshape(len(taus), len(rows), ks.nu), Y.reshape(len(taus), len(rows), ks.nu)


# ---------------------------------------------------------------- M1：断面の指標（q17/pace/secmetrics.py と同じ式、前の足の列だけ K* の j_E）
def _gauss(x, sig):
    if sig < 0.5:
        return x
    r = int(np.ceil(3 * sig))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sig) ** 2)
    k /= k.sum()
    xp = np.concatenate([2 * x[0] - x[1:r + 1][::-1], x, 2 * x[-1] - x[-r - 1:-1][::-1]])
    return np.convolve(xp, k, mode="valid")


def _resample(P, ds):
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(d)])
    n = max(int(s[-1] / ds), 2)
    u = np.linspace(0.0, s[-1], n + 1)
    return np.stack([np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])], 1)


def sec_metrics(a, y, jB, jE, jt):
    A = a[jB:jE + 1]
    Y = y[jB:jE + 1]
    jc = int(np.argmax(Y))
    H = float(Y[jc])
    ac = float(A[jc])
    Fa, Fy = A[jc:], Y[jc:]
    ok = Fy > 0.05 * H
    ra = np.maximum.accumulate(np.where(ok, Fa, -1e9))
    Lo = float(np.max(np.where(ok, ra - Fa, 0.0)))
    P = np.stack([Fa, Fy], 1)
    last = np.flatnonzero(Fy > 0.1 * H)
    P = P[: last[-1] + 1] if len(last) else P[:2]
    R = _resample(P, max(H / 300.0, 0.02))
    sig = 0.03 * H / max(H / 300.0, 0.02)
    xs = _gauss(R[:, 0], sig)
    ys = _gauss(R[:, 1], sig)
    phi = np.unwrap(np.arctan2(np.gradient(ys), np.gradient(xs)))
    phi = phi - 2 * np.pi * np.round(phi[0] / (2 * np.pi))
    Theta = float(-np.degrees(phi.min()))
    return dict(H=H, Lo=Lo, Theta=Theta, tip_dx=float(a[jt]) - ac)


def cross(t, x, thr):
    i = np.flatnonzero((x[:-1] < thr) & (x[1:] >= thr))
    if not len(i):
        return None
    i = i[0]
    return float(t[i] + (thr - x[i]) / (x[i + 1] - x[i]) * (t[i + 1] - t[i]))


def pace(ks, pk, wt, wtau, fps=60.0):
    ts = np.arange(int(round(12.4 * fps)) + 1) / fps
    taus = np.interp(ts, wt, wtau)
    A, Y = sections_at(pk, ks, taus, ROWS)
    out = {}
    jB, jE = 18, int(ks.j_E)
    for k, r in enumerate(ROWS):
        M = [sec_metrics(A[n, k], Y[n, k], jB, jE, TIP[r]) for n in range(len(ts))]
        D = {q: np.array([m[q] for m in M]) for q in M[0]}
        P = np.stack([A[:, k, jB:jE + 1], Y[:, k, jB:jE + 1]], -1)
        V = np.gradient(P, 1.0 / fps, axis=0)
        Pc = P - P.mean(1, keepdims=True)
        Vc = V - V.mean(1, keepdims=True)
        sc = (Pc * Vc).sum((1, 2)) / np.maximum((Pc * Pc).sum((1, 2)), 1e-9)
        Rz = Vc - sc[:, None, None] * Pc
        up = P[..., 1] > 0.3 * D["H"][:, None]
        vdef = np.sqrt(np.where(up, (Rz ** 2).sum(-1), 0).sum(-1) / np.maximum(up.sum(-1), 1))
        H = D["H"]
        Hf = H[-1]
        ev = {}
        for nm, x, thr in (("Theta45", D["Theta"], 45), ("Theta90", D["Theta"], 90), ("Lo0.15H", D["Lo"] / H, 0.15), ("H0.4Hf", H / Hf, 0.4),
                           ("H0.8Hf", H / Hf, 0.8)):
            tc = cross(ts, x, thr)
            ev[nm] = None if tc is None else dict(t=r3(tc), tau=r3(float(np.interp(tc, ts, taus))))
        m = (ts >= 2.0) & (ts <= 11.5)
        dv = np.gradient(vdef, 1.0 / fps)
        e45, e15 = ev["Theta45"], ev["Lo0.15H"]
        out[str(r)] = dict(events=ev, hump_to_C_s=r3(e15["t"] - e45["t"]) if e45 and e15 else None,
                           rise_04_08_s=r3(ev["H0.8Hf"]["t"] - ev["H0.4Hf"]["t"]) if ev["H0.8Hf"] and ev["H0.4Hf"] else None,
                           vdef_up_max_mps=r3(vdef[m].max()), vdef_up_max_t=r3(ts[m][np.argmax(vdef[m])], 2),
                           vdef_up_rise_max_mps2=r3(dv[m].max()), tau_at_t0=r3(taus[0]),
                           _series=dict(t=ts[::2].tolist(), Theta=D["Theta"][::2].tolist(), Lo_over_H=(D["Lo"] / H)[::2].tolist(),
                                        vdef=vdef[::2].tolist(), H_over_Hf=(H / Hf)[::2].tolist()))
    return out


def rise_curve(ks, pk):
    taus = np.round(np.arange(-9.0, 1e-9, 1.0 / 60), 9)
    A, Y = sections_at(pk, ks, taus, ROWS)
    out = {}
    for k, r in enumerate(ROWS):
        rm = [DG.row_metrics(A[n, k:k + 1], Y[n, k:k + 1], ks.crest_hi[[r]], ks.j_E) for n in range(len(taus))]
        out[str(r)] = np.array([float(q["H"][0]) for q in rm])
    return taus, out


# ---------------------------------------------------------------- M2
def sg2(n_half, h):
    k = np.arange(-n_half, n_half + 1) * h
    Xd = np.stack([np.ones_like(k), k, k * k], 1)
    return 2.0 * np.linalg.pinv(Xd)[2]


def stop_end(wt, wtau):
    HZ = 240
    tg = np.arange(0, 12.0 + 1e-9, 1.0 / HZ)
    tq = np.interp(tg, wt, wtau)
    rate = np.gradient(tq, tg)
    kstar = int(np.nonzero(tq >= -1e-9)[0][0])
    k = kstar
    while k > 0 and rate[k] < 0.02:
        k -= 1
    rd = np.gradient(np.convolve(rate, np.ones(4) / 4, mode="same"), tg)
    while k > 0 and rd[k] < -0.01:
        k -= 1
    return max(min(float(tg[k]), float(tg[kstar])), float(tg[kstar]) - 0.5)


def no_rebound(ks, pk, wt, wtau, tau0=-3.6, fit_s=0.25):
    HZ = 240
    tg = np.arange(0, 12.0 + 1e-9, 1.0 / HZ)
    tq = np.interp(tg, wt, wtau)
    t_end = stop_end(wt, wtau)
    taus = np.round(np.arange(tau0, 1e-9, 1.0 / HZ), 9)
    taus[-1] = 0.0
    w = sg2(int(round(fit_s * HZ / 2)), 1.0 / HZ)
    nh = len(w) // 2
    res = dict(lip=dict(n=0, rerise_gt_1cm=0, rerise_max_m=0.0, accp_gt_005=0, accp_max=-9.0, accs_gt_005=0, accs_gt_05=0, accs_max=-9.0),
               tube=dict(n=0, rerise_gt_1cm=0, rerise_max_m=0.0, accp_gt_005=0, accp_max=-9.0, accs_gt_005=0, accs_gt_05=0, accs_max=-9.0))
    worst = {}
    rows = list(ks.curled)
    for c0 in range(0, len(rows), 16):
        part = rows[c0:c0 + 16]
        vidx, meta = [], []
        for q in part:
            for j in range(q["jt"] + 1, q["ja"]):
                vidx.append(q["r"] * ks.nu + j)
                meta.append((q["r"], j, "lip" if j <= q["rim"] else "tube"))
        vidx = np.array(vidx)
        Yp = pk.sub(taus, vidx, 0)[..., 1]
        Ys = pk.sub(np.clip(tq, tau0, 0.0), vidx, 0)[..., 1]
        Ap = np.stack([np.convolve(Yp[:, i], w[::-1], mode="same") for i in range(Yp.shape[1])], 1)
        As = np.stack([np.convolve(Ys[:, i], w[::-1], mode="same") for i in range(Ys.shape[1])], 1)
        for i, m in enumerate(meta):
            R = res[m[2]]
            R["n"] += 1
            y = Yp[:, i]
            ka = int(np.argmax(y))
            if ka >= len(taus) - 3:
                continue
            aft = y[ka:]
            rr = float(np.max(aft - np.minimum.accumulate(aft)))
            seg = Ap[ka + nh + 1:len(taus) - nh, i]
            ap_ = float(seg.max()) if len(seg) else -9.0
            ta = float(taus[ka])
            ts_a = float(np.interp(ta, tq, tg)) if ta > tq[0] else 0.0
            ms = (tq >= ta) & (tq >= tau0 + 0.05) & (tg <= t_end - nh / HZ) & (np.arange(len(tg)) >= nh) & (tg >= ts_a + nh / HZ)
            as_ = float(As[ms, i].max()) if ms.any() else -9.0
            R["rerise_gt_1cm"] += int(rr > 0.01)
            R["accp_gt_005"] += int(ap_ > 0.05)
            R["accs_gt_005"] += int(as_ > 0.05)
            R["accs_gt_05"] += int(as_ > 0.5)
            for key, v in (("rerise_max_m", rr), ("accp_max", ap_), ("accs_max", as_)):
                if v > R[key]:
                    R[key] = v
                    worst["%s_%s" % (m[2], key)] = dict(row=m[0], col=m[1], apex_tau=r3(ta), value=r3(v))
    for k in res:
        for kk in list(res[k]):
            res[k][kk] = r3(res[k][kk], 4)
    res["worst"] = worst
    res["reading_ja"] = "0.25 s の二次の当てはめ（Savitzky–Golay、240 Hz）。画面は既定の時間曲線、止めるための区間の前まで（P16 と同じ）。許容 0.05 m/s²"
    return res


# ---------------------------------------------------------------- M3
def trough(ks, pk, seat_json="Tools/GWContext/seat_v1.json"):
    taus = np.round(np.arange(-8.0, 1e-9, 0.1), 4)
    A, Y = sections_at(pk, ks, taus, TROUGH_ROWS)
    jE = int(ks.j_E)
    out = {}
    for k, r in enumerate(TROUGH_ROWS):
        Ds, Hs = [], []
        for n in range(len(taus)):
            a, y = A[n, k], Y[n, k]
            af = a[jE] if True else 0.0
            m = np.arange(len(a)) >= jE
            m &= (a <= af + 30.0)
            Ds.append(float(-min(y[m].min(), 0.0)))
            Hs.append(float(y[:jE + 1].max()))
        Ds, Hs = np.array(Ds), np.array(Hs)
        a, y = A[-1, k], Y[-1, k]
        yt = y[jE:]
        at = a[jE:]
        kb = int(np.argmin(yt))
        half = yt <= 0.5 * yt[kb]
        rk = lambda v: np.argsort(np.argsort(v)).astype(float)   # noqa: E731
        rho = float(np.corrcoef(rk(Hs), rk(Ds))[0, 1]) if Ds.std() > 0 else None
        i3 = int(np.argmin(np.abs(taus + 3.0)))
        # 台座（t* と τ −6〜0 の最悪）：前面の頂〜j_E で、隣の列の組 Δa < 0.05 m・Δy > 0.5 m
        def plinth(a_, y_):
            cj = int(np.argmax(y_[:jE + 1]))
            da = np.abs(np.diff(a_[cj:jE + 1]))
            dy = np.abs(np.diff(y_[cj:jE + 1]))
            yl = 0.5 * (y_[cj:jE] + y_[cj + 1:jE + 1])
            low = (yl < 4.0) & (yl > 0.0)
            ang = np.degrees(np.arctan2(dy, np.maximum(da, 1e-9)))
            return int(((da < 0.05) & (dy > 0.5)).sum()), float(ang[low].max()) if low.any() else None
        pl_t, ang_t = plinth(a, y)
        pl_all = max(plinth(A[n, k], Y[n, k])[0] for n in range(len(taus)) if taus[n] >= -6.0)
        back = Y[-1, k, :19]
        out[str(r)] = dict(H_tstar=r3(Hs[-1]), D_tstar_m=r3(Ds[-1]), D_over_H_tstar=r3(Ds[-1] / max(Hs[-1], 1e-9)),
                           bottom_ahead_of_foot_m=r3(at[kb] - at[0]), width_half_depth_m=r3(at[half].max() - at[half].min()) if half.sum() > 1 else 0.0,
                           back_D_tstar_m=r3(-min(back.min(), 0.0)), spearman_H_D=r3(rho), D_tstar_over_maxD=r3(Ds[-1] / max(Ds.max(), 1e-9)),
                           D_m3_over_D_tstar=r3(Ds[i3] / max(Ds[-1], 1e-9)),
                           D_series={("%+.1f" % t): r3(v) for t, v in zip(taus[::10], Ds[::10])},
                           plinth_pairs_tstar=pl_t, plinth_pairs_max_tau_m6_0=pl_all, face_below_4m_max_angle_deg_tstar=r3(ang_t))
    # 座席の船：t* の竜骨の線の下の面の高さ（最も近い頂点）と水線（竜骨＋喫水）
    try:
        meta = json.load(open(KS.find_files(DG.KSTAR_DIR)["meta"], encoding="utf-8"))
        fp = KS.seat_footprint(meta, seat_json)
        Xl = pk.local(0.0) + ks.O
        Ak, Yk, Ck = ks.section(Xl)
        s = np.linspace(fp["s0"], fp["s1"], 9)
        rec = []
        for sv in s:
            a0, c0 = fp["a0"] + fp["da"] * sv, fp["c0"] + fp["dc"] * sv
            d = (Ak - a0) ** 2 + (Ck - c0) ** 2
            i = np.unravel_index(int(np.argmin(d)), d.shape)
            rec.append(dict(s=r3(sv, 2), a=r3(a0, 2), c=r3(c0, 2), surface_y=r3(Yk[i]), waterline_y=r3(fp["keel"](sv) + fp["draft"]),
                            surface_minus_waterline_m=r3(Yk[i] - fp["keel"](sv) - fp["draft"]), nearest_vertex_dist_m=r3(math.sqrt(d[i]))))
        out["seat_boat_tstar"] = rec
    except Exception as e:
        out["seat_boat_error"] = repr(e)
    return out


# ---------------------------------------------------------------- M4
def spatial(ks, pk):
    R, C = ks.nv, ks.nu
    r_, c_ = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a_ = (r_ * C + c_).ravel()
    b_ = ((r_ + 1) * C + c_).ravel()
    cc = (r_ * C + c_ + 1).ravel()
    d_ = ((r_ + 1) * C + c_ + 1).ravel()
    tris = np.concatenate([np.stack([a_, b_, cc], 1), np.stack([cc, b_, d_], 1)])

    def normals(P):
        V = P.reshape(-1, 3)
        fn = np.cross(V[tris[:, 1]] - V[tris[:, 0]], V[tris[:, 2]] - V[tris[:, 0]])
        n = np.zeros_like(V)
        for k in range(3):
            np.add.at(n, tris[:, k], fn)
        return (n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)).reshape(R, C, 3)
    out = {}
    for tau in (-6.0, -4.0, -3.0, -2.5, -2.0, -1.5, -1.0, -0.5, 0.0):
        L = pk.local(tau).astype(np.float64)
        N = normals(L)
        ang = np.degrees(np.arccos(np.clip((N[1:] * N[:-1]).sum(-1), -1, 1)))
        y = L[..., 1]
        mv = y > 0.3
        mr = mv[1:] & mv[:-1]
        d2 = L[2:] - 2 * L[1:-1] + L[:-2]
        comp = (d2 * N[1:-1]).sum(-1)
        zz = (np.sign(comp[1:]) != np.sign(comp[:-1])) & (np.abs(comp[1:]) > 0.01) & (np.abs(comp[:-1]) > 0.01)
        mz = mv[2:-1] & mv[1:-2]
        out["%+.1f" % tau] = dict(J1_zigzag_frac=r3(float(zz[mz].mean()), 4), J3_row_normal_angle_p95_deg=r3(float(np.percentile(ang[mr], 95)), 2),
                                  row_edges_gt10deg=int((ang[mr] > 10).sum()))
    return out


def crest_angle(ks, pk):
    taus = np.round(np.arange(-1.5, 1e-9, 1.0 / 60), 9)
    A, Y = sections_at(pk, ks, taus, ROWS)
    out = {}
    for k, r in enumerate(ROWS):
        th = np.array([float(DG.row_metrics(A[n, k:k + 1], Y[n, k:k + 1], ks.crest_hi[[r]], ks.j_E)["theta"][0]) for n in range(len(taus))])
        i1 = int(np.argmin(np.abs(taus + 1.0)))
        out[str(r)] = dict(theta_min_deg=r3(np.nanmin(th), 1), theta_at_m1_deg=r3(th[i1], 1), theta_tstar_deg=r3(th[-1], 1),
                           sharpen_last_1s_deg=r3(th[i1] - th[-1], 1), theta_at={("%+.2f" % t): r3(th[int(np.argmin(np.abs(taus - t)))], 1)
                                                                            for t in (-1.5, -1.0, -0.75, -0.5, -0.25, 0.0)})
    return out


def curl_c1_checks(ks, pk, spec, wt, wtau):
    """試行C の巻き下がりの検査（ds28r01c_curl.row_curl と同じ式）。唇の動きの始まりは版の運びの始まり σ。"""
    cond, _ = DG.load_conditions()
    Tc = CC.DX.calib_onset(ks, cond)
    on = float(spec["carry_sigma"]) + (abs(cond["tau0"]) - Tc)
    W = CC.Warp(absrepo(spec["warp"]))
    S = RB.series(pk, ks, list(ROWS), t0=-4.6)
    out = {}
    for j, r in enumerate(ROWS):
        e, _ = CC.row_curl(S, j, float(on[r]), {"default": W})
        out[str(r)] = {k: e[k] for k in ("tau_on", "visible", "H_over_Hf_at_top", "h_at_visible_m", "h_at_top_m", "h_at_tstar_m", "drop_total_m",
                                          "share_before_top", "share_last_1s_physical", "monotone_max_rise_m", "monotone_ok",
                                          "rel_descent_speed_max_mps", "tip_apex_tau", "tip_max_up_accel_after_apex_mps2")}
        out[str(r)]["screen"] = e["screen"]["default"]
    return out


def draw_fig(res, out_png):
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 20)
    f2 = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 26)
    tags = [t for t in res if isinstance(res[t], dict) and "pace" in res[t]]
    col = {tags[0]: (120, 120, 120)}
    for k, t in enumerate(tags[1:]):
        col[t] = [(20, 90, 200), (220, 110, 0), (20, 150, 60)][k % 3]
    qs = [("Theta", "前面の回りの角 Θ [°]（45° = 小山が傾き始める）", 0, 200, [45, 90, 135, 180]),
          ("Lo_over_H", "張り出し Lo/H（0.15 = はっきりした C 字）", 0, 0.45, [0.05, 0.15, 0.25, 0.35]),
          ("vdef", "形の変わる速さ vdef_up [m/s]", 0, 5.5, [1, 2, 3, 4, 5]),
          ("H_over_Hf", "頂の高さ H/Hf（上昇）", 0, 1.05, [0.4, 0.6, 0.8, 1.0])]
    W, ph = 1900, 260
    img = Image.new("RGB", (W, 90 + 2 * len(qs) * (ph + 16)), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 14), "設計28修正01 試行D：画面の時刻 t（各版の既定の時間曲線）での断面の指標。灰 = C1（前回）、青 = %s（今回）。縦の線 = Θ 45° と Lo 0.15H の時刻" % ",".join(tags[1:]), font=f2, fill=(0, 0, 0))
    y0 = 70
    x0, x1 = 120, W - 40
    for r in ("159", "192"):
        for q, lab, v0, v1, ticks in qs:
            ya, yb = y0, y0 + ph
            X = lambda t: x0 + (t - 0.0) / 12.4 * (x1 - x0)          # noqa: E731
            Y = lambda v: yb - (min(max(v, v0), v1) - v0) / (v1 - v0) * (yb - ya)   # noqa: E731
            d.rectangle([x0, ya, x1, yb], outline=(0, 0, 0))
            for tt in range(0, 13):
                d.line([(X(tt), ya), (X(tt), yb)], fill=(228, 228, 228))
                d.text((X(tt) - 6, yb + 2), str(tt), font=f, fill=(0, 0, 0))
            for v in ticks:
                d.line([(x0, Y(v)), (x1, Y(v))], fill=(215, 215, 215))
                d.text((x0 - 60, Y(v) - 10), "%g" % v, font=f, fill=(0, 0, 0))
            d.text((x0 + 8, ya + 4), "行 %s — %s" % (r, lab), font=f, fill=(0, 0, 0))
            for t in tags:
                S = res[t]["pace"][r]["_series"]
                pts = [(X(a), Y(b)) for a, b in zip(S["t"], S[q]) if b == b]
                d.line(pts, fill=col[t], width=3)
                ev = res[t]["pace"][r]["events"]
                for k in ("Theta45", "Lo0.15H"):
                    if ev.get(k):
                        d.line([(X(ev[k]["t"]), ya), (X(ev[k]["t"]), yb)], fill=col[t], width=2)
            y0 += ph + 30
    img.save(out_png, optimize=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", default="C1,D")
    ap.add_argument("--tag-spec", action="append", default=[])
    ap.add_argument("--out", default="Unity/Build/Design/28R01D/review/review_D.json")
    ap.add_argument("--skip", default="", help="省く項目（pace,rise,m2,trough,spatial,theta,curl）")
    a = ap.parse_args()
    for s in a.tag_spec:
        k, v = s.split("=", 1)
        pkg, warp, kst, cs = v.split("|")
        TAGS[k] = dict(pkg=pkg, warp=warp, kstar=kst, carry_sigma=float(cs))
    skip = set(x for x in a.skip.split(",") if x)
    res = {}
    rise = {}
    for tag in a.tags.split(","):
        t0 = time.time()
        spec = TAGS[tag]
        ks, pk, wt, wtau = open_pkg(spec)
        e = dict(spec=spec, pos_sha256=pk.pos_sha, layers=int(pk.L), quant_step_mm=r3(float(np.max(np.array(pk.meta["bbox_size"]))) / 65535 * 1000, 3),
                 gpu_estimate=pk.meta.get("gpu_estimate"), landmarks=dict(j_corner=int(ks.j_corner), j_E=int(ks.j_E)))
        if "pace" not in skip:
            e["pace"] = pace(ks, pk, wt, wtau)
        if "rise" not in skip:
            taus, Hs = rise_curve(ks, pk)
            rise[tag] = (taus, Hs)
        if "curl" not in skip:
            e["curl"] = curl_c1_checks(ks, pk, spec, wt, wtau)
        if "m2" not in skip:
            e["no_rebound"] = no_rebound(ks, pk, wt, wtau)
        if "trough" not in skip:
            e["trough"] = trough(ks, pk)
        if "spatial" not in skip:
            e["spatial"] = spatial(ks, pk)
        if "theta" not in skip:
            e["crest_angle"] = crest_angle(ks, pk)
        e["seconds"] = round(time.time() - t0, 1)
        res[tag] = e
        print("done", tag, e["seconds"], flush=True)
        del pk
    if "C1" in rise:
        for tag in rise:
            if tag == "C1":
                continue
            taus, Hs = rise[tag]
            tc, Hc = rise["C1"]
            res[tag]["rise_vs_C1"] = {r: dict(max_abs_dH_m=r3(np.max(np.abs(Hs[r] - Hc[r]))), max_abs_dH_over_Hf=r3(np.max(np.abs(Hs[r] - Hc[r])) / Hc[r][-1], 4))
                                      for r in Hs}
    try:
        draw_fig(res, os.path.join(os.path.dirname(absrepo(a.out)), "fig_" + os.path.splitext(os.path.basename(a.out))[0] + ".png"))
    except Exception as e:
        print("fig error", repr(e))
    for tag in res:
        for r in (res[tag].get("pace") or {}):
            res[tag]["pace"][r].pop("_series", None)
    res["_definitions_ja"] = __doc__
    out = absrepo(a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1, default=lambda o: r3(o) if isinstance(o, (np.floating, float)) else (int(o) if isinstance(o, np.integer) else str(o)))
    print(out)


if __name__ == "__main__":
    main()
