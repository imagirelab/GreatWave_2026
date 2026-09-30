# -*- coding: utf-8 -*-
"""仕上げ27：採用の動き（28修正01 の F_final など、ds27 の包み）の関門 P2・P3・P13 の不合格の場所を調べる（記録のみ）。

設計27 の関門の検査器 ds27_gates.py の関数（KStar・Package・row_metrics・row_areas・tri_normals）と、試行D の包み
ds28r01d_gates.py の K*′ の差し替えをそのまま使い、判定の値は変えない。検査器が「最悪の 1 か所」だけを書く所を、
行・列・時刻の分布として数え直す。
  P2：225 m の窓が周りの海の標本（--sea の a の範囲）に収まるコマと収まらないコマを分けて比の最大を出す。
      --ext-a-min を渡すと、生成器（ds28r01f_model.Generator）の sea_outside で標本の範囲を広げた海でも測る（生成器は作るだけで、包みは変えない）。
  P3：巻きの行ごとの値（検査器と同じ式。噴流の始まりは検査器の出力の onset_tau_by_row を読む）。
  P13：(2) 地面の二階差分、(5b) 行の方向の辺、(5c) 行の方向の伸びの比、(5g) 面の反転 の違反を、行・列・時刻で数える（30 Hz、物理の時刻）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl27/pl27_diag.py --package Unity/Build/Design/28R01F/F_final/art_on \
      --kstar Unity/Build/Design/28R01F/kstar_F_final --gates-json Unity/Build/Design/28R01F/F_final/gates/default_ds27.json \
      --out Unity/Build/Polish/27/diag/diag_F_final.json [--ext-a-min -460]
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
GW = os.path.abspath(os.path.join(HERE, ".."))
REPO = os.path.abspath(os.path.join(GW, "..", ".."))
for sub in ("ds27", "ds28", "ds28r01", "ds28r01d", "ds28r01e", "ds28r01f"):
    p = os.path.join(GW, sub)
    if p not in sys.path:
        sys.path.insert(0, p)
import ds27_gates as DG  # noqa: E402
import ds28r01d_gates as DGW  # noqa: E402


def ab(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def hist(vals, top=12):
    u, c = np.unique(np.asarray(vals), return_counts=True)
    o = np.argsort(-c)[:top]
    return {str(int(u[i])): int(c[i]) for i in o}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--kstar", required=True)
    ap.add_argument("--sea", default=None, help="既定は <包み>/ds27_sea.npz")
    ap.add_argument("--gates-json", required=True, help="検査器の出力（onset_tau_by_row を読む）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ext-a-min", type=float, default=None)
    ap.add_argument("--ext-a-max", type=float, default=None)
    ap.add_argument("--hz", type=int, default=60)
    a = ap.parse_args()
    t0 = time.time()
    kd = DGW.patch_kstar(ab(a.kstar))
    ks = DG.KStar(kd)
    pk = DG.Package(ab(a.package), ks)
    seap = ab(a.sea) if a.sea else os.path.join(ab(a.package), "ds27_sea.npz")
    sea = dict(np.load(seap))
    GJ = json.load(open(ab(a.gates_json), encoding="utf-8"))
    onset = np.full(ks.nv, np.nan)
    for k, v in GJ["onset_tau_by_row"].items():
        if v is not None:
            onset[int(k)] = float(v)
    rows_k = ks.curled_idx
    half = DG.TH["P2_window_half_m"]
    # ---- 標本の範囲を広げた海（任意）
    ext = None
    if a.ext_a_min is not None:
        import ds28r01f_model as MF
        tg = time.time()
        g = MF.Generator(kstar_dir=ab(a.kstar), defer_no_rebound=True, log=None)
        a_hi = a.ext_a_max if a.ext_a_max is not None else float(sea["a"][-1])
        ae = np.arange(a.ext_a_min, a_hi + 1e-9, 1.0)
        ee = np.zeros((len(sea["tau"]), ks.nv, len(ae)), np.float32)
        for k, t in enumerate(sea["tau"]):
            ee[k] = g.sea_outside(float(t), sea["Ac"][k].astype(np.float64), ae).astype(np.float32)
        # 重なる範囲で元の標本と同じか（生成器の式の確かめ）
        ov = (ae >= sea["a"][0]) & (ae <= sea["a"][-1])
        io = np.searchsorted(sea["a"], ae[ov])
        err = float(np.abs(ee[:, :, ov] - sea["eta"][:, :, io]).max())
        ext = dict(tau=sea["tau"], a=ae, eta=ee)
        ext_info = dict(a_range=[float(ae[0]), float(ae[-1])], overlap_max_abs_diff_m=err, build_s=round(time.time() - tg, 1))
        print("広げた海：a %.0f〜%.0f、元の標本との差の最大 %.2e m（%.0f s）" % (ae[0], ae[-1], err, time.time() - tg), flush=True)
    else:
        ext_info = None
    # ---- P2・P3（60 Hz。検査器と同じ時刻の格子）
    tau0 = float(pk.knots[0])
    K = int(math.floor(-tau0 * a.hz + 1e-6))
    taus = -np.arange(K, -1, -1) / a.hz
    nt = len(taus)
    nr = len(rows_k)
    An = np.full((nt, nr), np.nan)
    Ap = np.full((nt, nr), np.nan)
    cov = np.zeros((nt, nr), bool)
    AnE = np.full((nt, nr), np.nan)
    ApE = np.full((nt, nr), np.nan)
    covE = np.zeros((nt, nr), bool)
    ca_main = np.zeros(nt)
    for k, tau in enumerate(taus):
        X = pk.world(tau)
        A, Y, C = ks.section(X)
        rm = DG.row_metrics(A, Y, ks.crest_hi, ks.j_E)
        ca_main[k] = rm["ca"][ks.main_row]
        for src, (AnX, ApX, cvX) in (((sea, (An, Ap, cov)),) + (((ext, (AnE, ApE, covE)),) if ext is not None else ())):
            es_all, as_ = DG.sea_rows_interp(src, tau)
            for i, r in enumerate(rows_k):
                a_cr = rm["ca"][r]
                w0, w1 = a_cr - half, a_cr + half
                mb = (as_ >= w0) & (as_ < A[r, 0])
                mf = (as_ > A[r, -1]) & (as_ <= w1)
                pa = np.concatenate([as_[mb], A[r], as_[mf]])[None]
                py = np.concatenate([es_all[r][mb], Y[r], es_all[r][mf]])[None]
                anw, apw = DG.row_areas(pa, py)
                AnX[k, i], ApX[k, i] = float(anw[0]), float(apw[0])
                cvX[k, i] = (w0 >= A[r, 0] or as_[0] <= w0 + 1.0) and (w1 <= A[r, -1] or as_[-1] >= w1 - 1.0)
        if k % 120 == 0:
            print("  P2/P3 %d/%d τ=%.2f（%.0f s）" % (k, nt, tau, time.time() - t0), flush=True)
    judge = taus <= DG.TH["P2_calm_painting_from_tau"] + 1e-9

    def p2_summary(AnX, ApX, cvX):
        R = np.where(ApX >= 1.0, np.abs(AnX) / np.maximum(ApX, 1e-9), np.nan)
        Rj = np.where(judge[:, None], R, np.nan)
        out = {}
        for nm, m in (("all", np.ones_like(cvX)), ("window_covered", cvX), ("window_not_covered", ~cvX)):
            Rm = np.where(m, Rj, np.nan)
            if np.isfinite(Rm).any():
                i = np.unravel_index(int(np.nanargmax(Rm)), Rm.shape)
                bad = np.isfinite(Rm) & (Rm > DG.TH["P2_ratio"])
                bk, bi = np.nonzero(bad)
                out[nm] = dict(max=round(float(Rm[i]), 4), at=dict(row=int(rows_k[i[1]]), c_m=round(float(ks.c[rows_k[i[1]]]), 2), tau=round(float(taus[i[0]]), 3)),
                               row_frames_over_0p2=int(bad.sum()),
                               rows_over_0p2=sorted({int(rows_k[j]) for j in bi}),
                               tau_range_over_0p2=[round(float(taus[bk.min()]), 3), round(float(taus[bk.max()]), 3)] if len(bk) else None)
            else:
                out[nm] = None
        mi = list(rows_k).index(ks.main_row)
        out["main_row_max_covered"] = round(float(np.nanmax(np.where(cvX[:, mi] & judge, R[:, mi], np.nan))), 4) if (cvX[:, mi] & judge).any() else None
        out["frames_not_covered_tau_max"] = round(float(taus[np.nonzero((~cvX).any(1))[0].max()]), 3) if (~cvX).any() else None
        # 行ごとの最大（窓が収まるコマ、判定の区間）
        Rc = np.where(cvX & judge[:, None], R, np.nan)
        per_row = np.nanmax(np.where(np.isfinite(Rc), Rc, -1), 0)
        out["per_row_max_covered_top"] = {str(int(rows_k[j])): round(float(per_row[j]), 4) for j in np.argsort(-per_row)[:15]}
        # 時刻ごとの最大（窓が収まるコマ）
        tm = np.nanmax(np.where(np.isfinite(Rc), Rc, -1), 1)
        out["per_tau_max_covered"] = {("%.2f" % taus[k]): round(float(tm[k]), 4) for k in range(0, nt, 30) if judge[k]}
        return out, R

    def p3_summary(AnX, ApX):
        res = {}
        worst = (0.0, None)
        for i, r in enumerate(rows_k):
            if not np.isfinite(onset[r]):
                continue
            m_all = taus >= onset[r] - 1e-9
            m = m_all & judge
            k0 = int(np.nonzero(m_all)[0][0])
            den = max(ApX[-1, i], 1e-9)
            if not m.any():
                continue
            dv = np.abs(AnX[m, i] - AnX[k0, i]) / den
            j = int(np.argmax(dv))
            res[int(r)] = dict(dev=round(float(dv.max()), 4), at_tau=round(float(taus[m][j]), 3), onset=round(float(onset[r]), 3),
                               Anet_onset=round(float(AnX[k0, i]), 2), Anet_at=round(float(AnX[m, i][j]), 2), Apos_tstar=round(float(ApX[-1, i]), 2),
                               c_m=round(float(ks.c[r]), 2))
            if dv.max() > worst[0]:
                worst = (float(dv.max()), int(r))
        top = sorted(res.items(), key=lambda kv: -kv[1]["dev"])[:12]
        return dict(max=round(worst[0], 4), worst_row=worst[1], over_0p1_rows=sorted([r for r, v in res.items() if v["dev"] > DG.TH["P3_frac"]]),
                    top={str(r): v for r, v in top})

    rep = dict(schema="GreatWave.pl27.diag/1", package=DG.rel(ab(a.package)), pos_sha256=pk.pos_sha, kstar=DG.rel(kd), sea=DG.rel(seap),
               sea_sha256=DG.sha256_file(seap), sea_a_range=[float(sea["a"][0]), float(sea["a"][-1])], gates_json=DG.rel(ab(a.gates_json)),
               hz=a.hz, main_row=int(ks.main_row), peak_row=int(ks.peak_row), curled_rows=int(nr),
               crest_a_main_row_range=[round(float(ca_main.min()), 2), round(float(ca_main.max()), 2)])
    rep["P2"], R0 = p2_summary(An, Ap, cov)
    rep["P3"] = p3_summary(An, Ap)
    if ext is not None:
        rep["ext_sea"] = ext_info
        rep["P2_ext"], _ = p2_summary(AnE, ApE, covE)
        rep["P3_ext"] = p3_summary(AnE, ApE)
    print("P2/P3 終わり（%.0f s）" % (time.time() - t0), flush=True)
    # ---- P13（30 Hz、物理の時刻）
    HZO = DG.HZ_OUT
    K3 = int(math.floor(-tau0 * HZO + 1e-6))
    t3 = -np.arange(K3, -1, -1) / HZO
    thr_e = np.minimum(DG.TH["P13_row_edge_m"], ks.Lrow_K - 2 * pk.q_max)
    q2 = 2 * pk.q_max
    acc_list, e_list, c_list, f_list = [], [], [], []
    prev_g = []
    ref_n = ref_ok = None
    lim_acc = DG.TH["P13_acc_g"] * DG.G / HZO ** 2
    for k, tau in enumerate(t3):
        X = pk.world(tau)
        Xg = X[rows_k]
        prev_g.append(Xg)
        if len(prev_g) == 3:
            d2 = np.linalg.norm(prev_g[2] - 2 * prev_g[1] + prev_g[0], axis=-1)
            ii, jj = np.nonzero(d2 > lim_acc)
            for i_, j_ in zip(ii, jj):
                acc_list.append((int(rows_k[i_]), int(j_), round(float(tau) - 1.0 / HZO, 4), float(d2[i_, j_])))
            prev_g.pop(0)
        nrm = DG.tri_normals(X)
        nl = np.linalg.norm(nrm, axis=-1)
        ar = 0.5 * nl
        region3 = np.broadcast_to(ks.tri_mask[..., None], ar.shape)
        un_ = nrm / np.maximum(nl[..., None], 1e-15)
        valid = ar > 1e-10
        if ref_n is not None:
            dots = (un_ * ref_n).sum(-1)
            bad = valid & ref_ok & (dots <= 0)
            br = bad & (ks.tri_resolvable | region3)
            for i_, j_, t_ in zip(*np.nonzero(br)):
                f_list.append((int(i_), int(j_), int(t_), round(float(tau), 4)))
            ref_n = np.where(valid[..., None], un_, ref_n)
            ref_ok = ref_ok | valid
        else:
            ref_n = un_.copy()
            ref_ok = valid.copy()
        Lr = np.linalg.norm(np.diff(X, axis=1), axis=-1)
        mg = np.where(ks.row_edge_mask, Lr - thr_e, np.inf)
        for i_, j_ in zip(*np.nonzero(mg < 0)):
            e_list.append((int(i_), int(j_), round(float(tau), 4), float(Lr[i_, j_]), float(ks.Lrow_K[i_, j_])))
        lo_ = (Lr + q2) / np.maximum(ks.Lrow_K, 1e-9)
        hi_ = np.maximum(Lr - q2, 0) / np.maximum(ks.Lrow_K, 1e-9)
        bl = ks.row_edge_mask & ((lo_ < DG.TH["P13_stretch_lo"]) | (hi_ > DG.TH["P13_stretch_hi"]))
        for i_, j_ in zip(*np.nonzero(bl)):
            c_list.append((int(i_), int(j_), round(float(tau), 4), float(Lr[i_, j_]), float(ks.Lrow_K[i_, j_]), "lo" if lo_[i_, j_] < DG.TH["P13_stretch_lo"] else "hi"))
        if k % 60 == 0:
            print("  P13 %d/%d τ=%.2f（%.0f s）" % (k, len(t3), tau, time.time() - t0), flush=True)

    def summ(lst, has_val=True):
        if not lst:
            return dict(count=0)
        r_ = [v[0] for v in lst]
        c_ = [v[1] for v in lst]
        t_ = [v[2] if len(v) < 4 or isinstance(v[2], float) else v[3] for v in lst]
        return dict(count=len(lst), rows=hist(r_), cols=hist(c_), row_range=[min(r_), max(r_)], col_range=[min(c_), max(c_)],
                    tau_range=[min(t_), max(t_)], frames=len(set(t_)))

    # 行・列ごとの K* の目印（頂 jt・唇先 jtip・rim・錨 ja）
    lm = {str(q["r"]): dict(jt=q["jt"], jtip=q["jtip"], rim=q["rim"], ja=q["ja"], H=round(q["H"], 2), c=round(q["c"], 2)) for q in ks.curled}
    acc_s = summ(acc_list)
    if acc_list:
        w = max(acc_list, key=lambda v: v[3])
        acc_s["max"] = dict(row=w[0], col=w[1], tau=w[2], d2_m=round(w[3], 5))
        acc_s["limit_m"] = round(lim_acc, 5)
        acc_s["by_tau"] = hist([int(round(v[2] * 30)) for v in acc_list])
    e_s = summ(e_list)
    if e_list:
        w = min(e_list, key=lambda v: v[3])
        e_s["min"] = dict(row=w[0], col=w[1], tau=w[2], len_m=round(w[3], 5), K_len_m=round(w[4], 5))
    c_s = summ(c_list)
    if c_list:
        lo = [v for v in c_list if v[5] == "lo"]
        hi = [v for v in c_list if v[5] == "hi"]
        c_s["lo_count"], c_s["hi_count"] = len(lo), len(hi)
        if lo:
            w = min(lo, key=lambda v: v[3] / max(v[4], 1e-9))
            c_s["lo_min"] = dict(row=w[0], col=w[1], tau=w[2], len_m=round(w[3], 5), K_len_m=round(w[4], 5), ratio=round(w[3] / w[4], 4))
            c_s["lo_rows"] = hist([v[0] for v in lo], 20)
            c_s["lo_cols"] = hist([v[1] for v in lo], 20)
            c_s["lo_K_len_m_median"] = round(float(np.median([v[4] for v in lo])), 4)
            c_s["lo_len_m_median"] = round(float(np.median([v[3] for v in lo])), 4)
            # 列の位置を目印に対して（jt からの列の差）
            rel_ = [v[1] - lm[str(v[0])]["jt"] for v in lo if str(v[0]) in lm]
            c_s["lo_col_minus_jt"] = hist(rel_, 20)
            rel2 = [v[1] - lm[str(v[0])]["jtip"] for v in lo if str(v[0]) in lm]
            c_s["lo_col_minus_jtip"] = hist(rel2, 20)
        if hi:
            w = max(hi, key=lambda v: v[3] / max(v[4], 1e-9))
            c_s["hi_max"] = dict(row=w[0], col=w[1], tau=w[2], len_m=round(w[3], 5), K_len_m=round(w[4], 5), ratio=round(w[3] / w[4], 4))
    f_s = summ(f_list)
    if f_list:
        f_s["first"] = dict(row=f_list[0][0], col=f_list[0][1], tri=f_list[0][2], tau=f_list[0][3])
        f_s["by_tau"] = hist([int(round(v[3] * 30)) for v in f_list], 20)
    rep["P13"] = dict(hz=HZO, acc_2=acc_s, edge_5b=e_s, stretch_5c=c_s, flips_5g=f_s,
                      landmarks_sample={k: lm[k] for k in list(lm)[:: max(1, len(lm) // 12)]})
    rep["P13"]["landmarks_rows_of_interest"] = {str(r): lm.get(str(r)) for r in sorted({v[0] for v in (acc_list[:1] + e_list[:1] + c_list[:1])})}
    rep["runtime_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(ab(a.out)), exist_ok=True)
    with open(ab(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    np.savez_compressed(os.path.splitext(ab(a.out))[0] + "_series.npz", taus=taus, rows=rows_k, An=An, Ap=Ap, cov=cov,
                        AnE=AnE, ApE=ApE, covE=covE,
                        acc=np.array([v[:3] + (v[3],) for v in acc_list], float).reshape(-1, 4),
                        edge=np.array([v[:5] for v in e_list], float).reshape(-1, 5),
                        stretch=np.array([v[:5] + ((0.0 if v[5] == "lo" else 1.0),) for v in c_list], float).reshape(-1, 6),
                        flips=np.array(f_list, float).reshape(-1, 4))
    print("DONE %.0f s → %s" % (time.time() - t0, DG.rel(ab(a.out))), flush=True)


if __name__ == "__main__":
    main()
