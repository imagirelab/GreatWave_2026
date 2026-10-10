# -*- coding: utf-8 -*-
"""3. コマの間の補間の誤差（計画 C4）を自分の線と自分の取り直しで測り直す。あわせて、Unity が書き出した取り置きの線
（holdout_out.bin、割合 0.5・1/3・2/3）を自分の R3 の線と比べる。
自分の取り直し：頂（と、両方のコマにあれば唇の先）を目印にし、区間ごとに二つのコマそれぞれの弧長で等しく点を置く。
点の数は区間の長さの平均で割り振る（合わせて NPTS）。窓は真ん中のコマの頂の ±30 m。距離は 0.01 m おきの点から相手の線分まで（正確）。
出力：out/k_interp.json"""
import time
import numpy as np
from k_lib import *

t0 = time.time()
my = MyFrames()
kr = jload(OUT + "/k_r3.json")
rows = {r["frame"]: r for r in kr["rows"]}
K = 3745
ONSET = kr["onset"]["frame"]

# 各コマの頂の番号と唇の先の番号（自分の線の上）
CI, TIP = {}, {}
xprev = 261.53670245673754
for f in range(F0, F1 + 1):
    P = my.main_of(f)
    ic = crest_index(P, xprev); xprev = P[ic, 0]
    CI[f] = ic
    lp = lip(P, ic)
    TIP[f] = lp["i_tip"] if lp is not None else None


def blend(fa, fb, alpha, npts):
    A, B = my.main_of(fa), my.main_of(fb)
    la, lb = [CI[fa]], [CI[fb]]
    if TIP[fa] is not None and TIP[fb] is not None:
        la.append(TIP[fa]); lb.append(TIP[fb])
    sa, sb = arclen(A), arclen(B)
    ka = [0.0] + [sa[i] for i in la] + [sa[-1]]
    kb = [0.0] + [sb[i] for i in lb] + [sb[-1]]
    Lavg = np.array([0.5 * ((ka[j + 1] - ka[j]) + (kb[j + 1] - kb[j])) for j in range(len(ka) - 1)])
    n = np.maximum(1, np.round((npts - 1) * Lavg / Lavg.sum()).astype(int))
    qa, qb = [], []
    for j in range(len(n)):
        ua = np.linspace(ka[j], ka[j + 1], n[j] + 1); ub = np.linspace(kb[j], kb[j + 1], n[j] + 1)
        if j > 0:
            ua, ub = ua[1:], ub[1:]
        qa.append(ua); qb.append(ub)
    PA = at_s(A, sa, np.concatenate(qa)); PB = at_s(B, sb, np.concatenate(qb))
    return (1 - alpha) * PA + alpha * PB, len(la)


def err(C, fm, center=None, half=30.0):
    M = my.main_of(fm)
    xc = M[CI[fm], 0] if center is None else center
    w = (xc - half, xc + half)
    Cd = densify(C, 0.01); Cd = Cd[(Cd[:, 0] >= w[0]) & (Cd[:, 0] <= w[1])]
    Md = densify(M, 0.01); Md = Md[(Md[:, 0] >= w[0]) & (Md[:, 0] <= w[1])]
    d1, u1 = SegTree([M]).dist(Cd)
    d2, u2 = SegTree([C]).dist(Md)
    d = np.concatenate([d1, d2])
    return float(d.max()), float(np.percentile(d, 99)), u1 + u2


res = {}
for npts in (8192, 40000):
    c4, c43, far = {}, {}, {}
    for k in range(F0, K - 2):            # k + 2 ≤ K − 1
        C, nl = blend(k, k + 2, 0.5, npts)
        mx, p99, u = err(C, k + 1)
        c4[k] = dict(max=mx, p99=p99, ok=(mx <= 0.25 and p99 <= 0.05), n_landmarks=nl, unsure=u)
        if npts == 8192 and (k - F0) % 4 == 0:
            xc = my.main_of(k + 1)[CI[k + 1], 0]
            if xc - 150 - 30 > 100:
                far[k] = err(C, k + 1, center=xc - 150.0)[:2]
    for k in range(F0, K - 3):            # k + 3 ≤ K − 1
        C1, _ = blend(k, k + 3, 1 / 3, npts); C2, _ = blend(k, k + 3, 2 / 3, npts)
        c43[k] = (err(C1, k + 1)[0], err(C2, k + 2)[0])
    mx2 = np.array([v["max"] for v in c4.values()])
    E2 = float(np.median(mx2))
    E3_pool = float(np.median(np.concatenate([[a, b] for a, b in c43.values()])))
    E3_mean = float(np.median([0.5 * (a + b) for a, b in c43.values()]))
    pp = lambda E3: float(np.log((9 / 8) * E3 / E2) / np.log(1.5))
    fails = [k for k, v in c4.items() if not v["ok"]]
    # 自分の C4 から、補間する組 [k, k+1] を決める：k−1 と k の両方の C4 が入り、k+1 ≤ K−1（最後は [K−2, K−1]）
    okset = {k for k, v in c4.items() if v["ok"]}
    tested = set(c4.keys())
    interp = [j for j in range(F0, K - 1) if all((i not in tested) or (i in okset) for i in (j - 1, j))]
    res[str(npts)] = dict(n=len(c4), n_fail=len(fails), n_fail_p99=sum(1 for v in c4.values() if v["p99"] > 0.05),
                          n_fail_max=sum(1 for v in c4.values() if v["max"] > 0.25),
                          max_of_max=float(mx2.max()), max_of_p99=float(max(v["p99"] for v in c4.values())),
                          median_max=E2, median_p99=float(np.median([v["p99"] for v in c4.values()])),
                          E2=E2, E3_pooled=E3_pool, p_pooled=pp(E3_pool), E3_mean=E3_mean, p_mean=pp(E3_mean),
                          far_window=dict(n=len(far), median_max=float(np.median([v[0] for v in far.values()])) if far else None,
                                          median_p99=float(np.median([v[1] for v in far.values()])) if far else None),
                          unsure=sum(v["unsure"] for v in c4.values()),
                          ok_k=sorted(okset), interp_pairs_from_mine=interp,
                          c4={str(k): v for k, v in c4.items()})
    print(npts, {k: v for k, v in res[str(npts)].items() if k not in ("c4", "ok_k", "interp_pairs_from_mine")}, f"{time.time()-t0:.1f}s")

# 焼き（manifest）の補間する組と比べる
pairs, man = load_pairs()
baked_interp = [p["k"] for p in man["pairs"] if p["interp"]]
mine = res["8192"]["interp_pairs_from_mine"]
res["baked_interp"] = baked_interp
res["interp_same_as_baked"] = (baked_interp == mine)
res["interp_only_baked"] = sorted(set(baked_interp) - set(mine)); res["interp_only_mine"] = sorted(set(mine) - set(baked_interp))
print("interp baked", len(baked_interp), "mine", len(mine), res["interp_only_baked"], res["interp_only_mine"])

# Unity の取り置きの線（Editor とプレイヤー）
for which in ("editor", "player"):
    D = RT + f"/verify/coarse/unity_{which}"
    ix = jload(D + "/index.json")
    ho = np.fromfile(D + "/" + ix["holdoutFile"], dtype="<f4")
    out = {}
    for c in ix["holdout"]:
        o = c["offsetFloats"]
        U = ho[o:o + 4 * 8192].reshape(8192, 4)[:, :2].astype(np.float64); U[:, 0] += c["seatX"]
        fa, fb, a = c["frameA"], c["frameB"], c["alpha"]
        fm = fa + int(round(a * (fb - fa)))
        mx, p99, u = err(U, fm)
        out[(fa, fb, round(a, 4))] = (mx, p99)
    h2 = {k: v for k, v in out.items() if k[1] - k[0] == 2}
    h3 = {k: v for k, v in out.items() if k[1] - k[0] == 3}
    fails = sorted(k[0] for k, v in h2.items() if not (v[0] <= 0.25 and v[1] <= 0.05))
    E2 = float(np.median([v[0] for v in h2.values()])); E3 = float(np.median([v[0] for v in h3.values()]))
    mine_fail = set(int(k) for k, v in res["8192"]["c4"].items() if not v["ok"])
    res["unity_" + which] = dict(n2=len(h2), n3=len(h3), n_fail=len(fails), n_fail_p99=sum(1 for v in h2.values() if v[1] > 0.05),
                                 n_fail_max=sum(1 for v in h2.values() if v[0] > 0.25), max_of_max=max(v[0] for v in h2.values()),
                                 max_of_p99=max(v[1] for v in h2.values()), median_max=E2, median_p99=float(np.median([v[1] for v in h2.values()])),
                                 E3_pooled=E3, p_pooled=float(np.log((9 / 8) * E3 / E2) / np.log(1.5)),
                                 differs_from_my_c4=sorted(set(fails) ^ mine_fail),
                                 near_threshold=sorted((k[0], round(v[1], 5)) for k, v in h2.items() if abs(v[1] - 0.05) < 0.002))
    print(which, {k: v for k, v in res["unity_" + which].items()}, f"{time.time()-t0:.1f}s")

jsave(OUT + "/k_interp.json", res)
print(f"done {time.time()-t0:.1f}s")
