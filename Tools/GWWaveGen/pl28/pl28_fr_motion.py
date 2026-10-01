# -*- coding: utf-8 -*-
# 仕上げ28：設計28修正01 の最終の評審（独立）が使った断面の走査（Unity/Build/Design/28R01F/_scratch/final_review/fr_motion.py、SHA-256 74738a2d…）を
# リポジトリへ写し、入出力の場所だけを引数にしたもの（計算は同じ）。60 Hz の断面の自己交差、体積の履歴（断面積 × Δc と側面の影の包み）、
# 唇ができる前の頂の ±2 m 弦角（M7）、張り出しを測る。F_final の値（motion_F_final.json）と同じ定義で G_final を測って比べる。
# 使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_fr_motion.py <tag> <包み> <時間曲線> [hz] [出力のフォルダー] [K*′ の meta.json] [主断面の行] [峰の行]
# (original) Final reviewer: own section scan (self-intersection, volume, envelope, crest chord angle) on a DS27 package.
import os, sys, json, time
os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["OMP_NUM_THREADS"] = "1"
sys.dont_write_bytecode = True
import numpy as np
import multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
REPO = r"G:\Unity\GreatWave_2026_Fresh"
B = os.path.join(REPO, "Unity", "Build", "Design", "28R01F")
KMETA_PATH = sys.argv[6] if len(sys.argv) > 6 else os.path.join(B, "kstar_final", "kstarR4_a45_meta.json")
KMETA = json.load(open(KMETA_PATH, encoding="utf-8"))
OUTD = sys.argv[5] if len(sys.argv) > 5 else HERE
ROW_MAIN = int(sys.argv[7]) if len(sys.argv) > 7 else 164
ROW_PEAK = int(sys.argv[8]) if len(sys.argv) > 8 else 183
E = np.array(KMETA["frame"]["e_crest"]); T = np.array(KMETA["frame"]["t_travel"])
CROW = np.array(KMETA["rows"]["c_m"], float)
jB, jE, jTIP = 18, 394, 200
NU = 400
I_, K_ = np.triu_indices(NU - 1, 2)   # segment pairs i<k-1

G = {"SF": 1.0}


def init(mm, sf=1.0):
    G["P"] = np.load(mm + "_P.npy", mmap_mode="r"); G["M"] = np.load(mm + "_M.npy", mmap_mode="r"); G["kt"] = np.load(mm + "_kt.npy")
    G["SF"] = sf


def herm(tau):
    kt, P, M = G["kt"], G["P"], G["M"]
    if tau <= kt[0]:
        return np.array(P[0], np.float64)
    if tau >= kt[-1]:
        return np.array(P[-1], np.float64)
    i = min(int(np.searchsorted(kt, tau, side="right") - 1), len(kt) - 2)
    h = kt[i + 1] - kt[i]; s = (tau - kt[i]) / h
    return ((2 * s**3 - 3 * s**2 + 1) * P[i] + (s**3 - 2 * s**2 + s) * h * M[i].astype(np.float64)
            + (-2 * s**3 + 3 * s**2) * P[i + 1] + (s**3 - s**2) * h * M[i + 1].astype(np.float64))


def sec(X):
    return X @ T, X[..., 1], X @ E


def orient(p, q, r):
    return (q[:, 0] - p[:, 0]) * (r[:, 1] - p[:, 1]) - (q[:, 1] - p[:, 1]) * (r[:, 0] - p[:, 0])


def selfx_rows(A, Y):
    """strict proper crossings between non-adjacent segments of each row polyline -> list of rows."""
    P = np.stack([A, Y], -1)
    hits = []
    for r0 in range(0, P.shape[0], 24):
        Q = P[r0:r0 + 24]
        a1, a2, b1, b2 = Q[:, I_], Q[:, I_ + 1], Q[:, K_], Q[:, K_ + 1]
        ok = ((np.minimum(a1[..., 0], a2[..., 0]) <= np.maximum(b1[..., 0], b2[..., 0])) &
              (np.minimum(b1[..., 0], b2[..., 0]) <= np.maximum(a1[..., 0], a2[..., 0])) &
              (np.minimum(a1[..., 1], a2[..., 1]) <= np.maximum(b1[..., 1], b2[..., 1])) &
              (np.minimum(b1[..., 1], b2[..., 1]) <= np.maximum(a1[..., 1], a2[..., 1])))
        rr, pp = np.nonzero(ok)
        if not len(rr):
            continue
        A1, A2, B1, B2 = a1[rr, pp], a2[rr, pp], b1[rr, pp], b2[rr, pp]
        o1, o2, o3, o4 = orient(A1, A2, B1), orient(A1, A2, B2), orient(B1, B2, A1), orient(B1, B2, A2)
        x = (o1 * o2 < 0) & (o3 * o4 < 0)
        if x.any():
            for r in np.unique(rr[x]):
                hits.append(int(r0 + r))
    return hits


def row_area(A, Y):
    return 0.5 * (np.sum(A[:, :-1] * Y[:, 1:] - A[:, 1:] * Y[:, :-1], 1) + (A[:, -1] * Y[:, 0] - A[:, 0] * Y[:, -1]))


def envelope_area(A, Y, da=0.1):
    """area under the upper envelope max_y(A) of each row (includes the cavity under the lip) = side-shadow area of the row."""
    out = np.zeros(A.shape[0])
    for r in range(A.shape[0]):
        a, y = A[r], Y[r]
        seg = np.hypot(np.diff(a), np.diff(y)); n = np.maximum(1, np.ceil(seg / (da * 0.5)).astype(int))
        tt = np.concatenate([np.arange(k) / k for k in n])
        idx = np.repeat(np.arange(len(seg)), n)
        aa = a[idx] + (a[idx + 1] - a[idx]) * tt; yy = y[idx] + (y[idx + 1] - y[idx]) * tt
        b = np.floor((aa - aa.min()) / da).astype(int)
        env = np.full(b.max() + 1, -np.inf); np.maximum.at(env, b, yy)
        env = env[np.isfinite(env)]
        out[r] = env.sum() * da
    return out


def crest_chord(A, Y, L=2.0):
    res = []
    for r in range(A.shape[0]):
        a, y = A[r, jB:jE + 1], Y[r, jB:jE + 1]
        jc = int(np.argmax(y)); s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(a), np.diff(y)))])
        sc = s[jc]
        if sc - L < 0 or sc + L > s[-1]:
            res.append(np.nan); continue
        pa = np.array([np.interp(sc - L, s, a), np.interp(sc - L, s, y)]); pb = np.array([np.interp(sc + L, s, a), np.interp(sc + L, s, y)])
        pc = np.array([a[jc], y[jc]]); u, v = pa - pc, pb - pc
        nu_, nv_ = np.linalg.norm(u), np.linalg.norm(v)
        if nu_ < 1e-9 or nv_ < 1e-9:
            res.append(np.nan); continue
        res.append(float(np.degrees(np.arccos(np.clip(u @ v / nu_ / nv_, -1, 1)))))
    return res


def lo_ratio(A, Y, r, SF):
    a, y = A[r, jB:jE + 1] * SF, Y[r, jB:jE + 1]
    jc = int(np.argmax(y)); H = y[jc]
    if H <= 0.05:
        return 0.0
    Fa, Fy = a[jc:], y[jc:]; ok = Fy > 0.05 * H
    ra = np.maximum.accumulate(np.where(ok, Fa, -1e9))
    return float(np.max(np.where(ok, ra - Fa, 0.0)) / H)


def work(tau):
    X = herm(tau)
    A, Y, Cc = sec(X)
    hits = selfx_rows(A, Y)
    ar = row_area(A, Y)
    env = envelope_area(A, Y)
    plan = float(np.abs(Cc - Cc.mean(1, keepdims=True)).max())
    cc = crest_chord(A, Y)
    Hr = Y[:, jB:jE + 1].max(1)
    lo = [lo_ratio(A, Y, r, G["SF"]) for r in range(A.shape[0])]
    return dict(tau=tau, hits=hits, area=ar.tolist(), env=env.tolist(), plan=plan, chord=cc, H=Hr.tolist(), lo=lo)


if __name__ == "__main__":
    from pl28_fr_pkg import Pkg, warp
    tag, pkgdir, warpf = sys.argv[1], sys.argv[2], sys.argv[3]
    hz = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
    t0 = time.time()
    pk = Pkg(pkgdir)
    os.makedirs(OUTD, exist_ok=True)
    mm = os.path.join(OUTD, "_mm_" + tag)
    np.save(mm + "_P.npy", pk.P); np.save(mm + "_M.npy", pk.M); np.save(mm + "_kt.npy", pk.kt)
    del pk
    init(mm)
    X0 = herm(0.0); A0, Y0, _ = sec(X0)
    r0 = ROW_MAIN
    jc = int(np.argmax(Y0[r0, jB:jE + 1])) + jB
    SF = 1.0 if A0[r0, jTIP] > A0[r0, jc] else -1.0
    wt, wtau, w = warp(warpf)
    taus = np.round(np.arange(-8.0, 1e-9, 1.0 / hz), 6)
    with mp.Pool(6, initializer=init, initargs=(mm, SF)) as pool:
        R = pool.map(work, list(taus), chunksize=4)
    G.clear()
    for f in ("_P.npy", "_M.npy", "_kt.npy"):
        try:
            os.remove(mm + f)
        except Exception as e:
            print("rm fail", e)
    area = np.array([r["area"] for r in R]); env = np.array([r["env"] for r in R])
    sg = 1.0 if area[-1, r0] > 0 else -1.0
    area *= sg
    dc = np.gradient(CROW)
    V = (area * dc).sum(1); Venv = (env * dc).sum(1)
    Hs = np.array([r["H"] for r in R]); lo = np.array([r["lo"] for r in R]); ch = np.array([r["chord"] for r in R], float)
    k = int(np.argmax(wtau)) + 1
    t_of = np.interp(taus, wtau[:k], wt[:k])
    out = dict(tag=tag, pkg=pkgdir, warp=warpf, hz=hz, frames=len(taus), SF=SF, area_sign=sg,
               selfx_frames=int(sum(1 for r in R if r["hits"])), selfx_examples=[(r["tau"], r["hits"][:10]) for r in R if r["hits"]][:20],
               planarity_max_m=float(max(r["plan"] for r in R)))

    def at(x, t):
        return float(np.interp(t, taus, x))
    TT = (-8, -6, -4, -3, -2.5, -2, -1.5, -1, -0.5, 0)
    out["V_m3"] = {("%+.1f" % t): round(at(V, t), 1) for t in TT}
    out["V_max"] = [round(float(V.max()), 1), float(taus[np.argmax(V)]), round(float(t_of[np.argmax(V)]), 3)]
    out["Venv_m3"] = {("%+.1f" % t): round(at(Venv, t), 1) for t in TT}
    out["Venv_max"] = [round(float(Venv.max()), 1), float(taus[np.argmax(Venv)])]
    out["A_main"] = {("%+.1f" % t): round(at(area[:, r0], t), 2) for t in TT}
    out["Aenv_main"] = {("%+.1f" % t): round(at(env[:, r0], t), 2) for t in TT}
    dV = np.abs(np.diff(V)); m2 = taus[1:] > -2.0; mb = (taus[1:] > -4.0) & (taus[1:] <= -2.0)
    out["V_step_last2s_max_before_max_ratio"] = [round(float(dV[m2].max()), 2), round(float(dV[mb].max()), 2), round(float(dV[m2].max() / dV[mb].max()), 3)]
    out["V_loss_frac_from_max"] = round(float(1 - V[-1] / V.max()), 3)
    out["Venv_loss_frac_from_max"] = round(float(1 - Venv[-1] / Venv.max()), 3)
    Hf = Hs[-1]; dt_screen = np.gradient(t_of)
    pre = (lo < 0.05) & (Hs >= 0.3 * Hf[None, :]) & np.isfinite(ch)
    body = Hf > 3.0
    rmin = np.where(pre, ch, np.inf).min(0)
    below110 = (np.where(pre & (ch <= 110), dt_screen[:, None], 0)).sum(0)
    below125 = (np.where(pre & (ch <= 125), dt_screen[:, None], 0)).sum(0)
    bm = body & np.isfinite(rmin)
    out["chord_pre_lip"] = dict(rows_body=int(body.sum()), rows_with_prelip=int(bm.sum()), min_deg=round(float(rmin[bm].min()), 1),
                                argmin_row=int(np.argmin(np.where(bm, rmin, np.inf))),
                                main_peak_min=[round(float(rmin[ROW_MAIN]), 1), round(float(rmin[ROW_PEAK]), 1)],
                                rows_le110_ge0p5s=int(((below110 >= 0.5) & body).sum()), rows_le110_any=int(((below110 > 0) & body).sum()),
                                rows_le125_ge0p5s=int(((below125 >= 0.5) & body).sum()),
                                tstar_chord_main_peak=[round(float(ch[-1, ROW_MAIN]), 1), round(float(ch[-1, ROW_PEAK]), 1)],
                                worst_rows=[(int(r), round(float(CROW[r]), 2), round(float(rmin[r]), 1), round(float(below110[r]), 2), round(float(below125[r]), 2), round(float(ch[-1, r]), 1))
                                            for r in np.argsort(np.where(bm, rmin, np.inf))[:10]])
    np.savez_compressed(os.path.join(OUTD, "motion_%s.npz" % tag), taus=taus, t=t_of, V=V, Venv=Venv, area=area, env=env, H=Hs, lo=lo, chord=ch)
    out["secs"] = round(time.time() - t0, 1)
    out["kstar_meta"] = KMETA_PATH
    json.dump(out, open(os.path.join(OUTD, "motion_%s.json" % tag), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False, indent=1))
