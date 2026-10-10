# -*- coding: utf-8 -*-
"""RT48（計画 §2.3）：R3e の粒子から、板の真ん中（z = 0）の平面の上に、粒子から作った細かい面（Zhu & Bridson 2005、0.125 m）を作る（py -3.10）。
式：φ(x) = |x − x̄| − r̄、x̄ = Σ w_i p_i / Σ w_i、r̄ = Σ w_i r_i / Σ w_i、w_i = max(0, 1 − |x − p_i|²/R²)³、R = 0.5 m。
粒子は 3D の距離で数える（平面から R 以内の粒子が入る）。半径 R の中に粒子がない節は φ = +R（空気）。ならし・膨らまし・削りはしない。
節：x は場面の 0.125 m の倍数（造波板から 100.04〜924.91 m）、y は解く格子の y0 = −44 m から 0.125 m おき（静かな水面から 8 m 下より上、y = 18 m まで）。
帯（record の B13）：sec のある x（場面 457.0〜998.5 m）は解く格子の場を双一次で移した |φ₀.₅| ≤ 2 m、外は一番上の水面（hf の z = 0 の節）± 2 m の節の値を使い、
  帯の外は解く格子の面の符号で埋める（水 −1、空気 +1）。帯の端で符号が合わない列と、sec の外で 0 の線が 1 回だけ交わらない列は、その列の全部の節で計算した値を使う。
静かな水面のずれ：0.116838 m ＋（3319 コマ目の、傾き 10° 未満の列の「細かい面の一番上 − 解く格子の一番上」の中央値）。
使い方: py -3.10 r_surface.py <run_dir> [--records <dir>] [--frames 3319-3889] [--workers 6] [--out <dir>]
出力: <out>（既定 <run_dir>/fine）/phi_FFFF.npz（phi float32 (ny, nx)、x0_rel、dx、y0_abs、dy、computed（帯の中か全部を計算した節）の bool）、
      meta.json（格子、粒子の半径、ずれ、コマごとの数、ファイルの SHA-256）"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # 数値の部品のスレッドの予約（1 つの起動で約 0.6 GB）を小さくする
    _os.environ.setdefault(_v, "1")
import sys, os, json, glob, time, hashlib, argparse
import numpy as np
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L

H = 0.125
R = 0.5
GX0 = 235.5           # 場面の x（0.125 の倍数、x_rel 100.0367）
NX = 6600             # 〜 1060.375（x_rel 924.9117）
GY0 = -7.875          # 解く格子の y（−44 + 0.125 × 289。静かな水面から 8 m 下 −7.883 より上の最初の節）
GY1 = 18.0
NY = int(round((GY1 - GY0) / H)) + 1
BAND = 2.0
SEC_X = (457.0, 998.5)  # sec の場面の x の範囲


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def zb_phi(P, r, z0=0.0):
    """全部の節で φ を計算する（粒子ごとに半径 R の中の節へ重みを足す）。返り値 phi (NY, NX)、W（重みの和）"""
    z = P[:, 2].astype(np.float64) - z0
    m = np.abs(z) < R
    px = P[m, 0].astype(np.float64); py = P[m, 1].astype(np.float64); pz = z[m]
    rr = r[m].astype(np.float64) if np.ndim(r) else np.full(len(px), float(r))
    bi = np.rint((px - GX0) / H).astype(np.int64); bj = np.rint((py - GY0) / H).astype(np.int64)
    n = NX * NY
    W = np.zeros(n); WX = np.zeros(n); WY = np.zeros(n); WZ = np.zeros(n); WR = np.zeros(n)
    K = int(np.ceil(R / H))
    pz2 = pz * pz
    for di in range(-K, K + 1):          # x の向きの 1 列ずつ、y の向きの 9 個をまとめて足す
        ii = bi + di
        dx = (GX0 + ii * H) - px
        okx = (ii >= 0) & (ii < NX) & (np.abs(dx) < R)
        dx2 = dx * dx + pz2
        I, Wt, PX, PY, PZ, RR = [], [], [], [], [], []
        for dj in range(-K, K + 1):
            jj = bj + dj
            dy = (GY0 + jj * H) - py
            s2 = (dx2 + dy * dy) / (R * R)
            ok = okx & (jj >= 0) & (jj < NY) & (s2 < 1.0)
            if not ok.any():
                continue
            I.append(jj[ok] * NX + ii[ok]); Wt.append((1.0 - s2[ok]) ** 3)
            PX.append(px[ok]); PY.append(py[ok]); PZ.append(pz[ok]); RR.append(rr[ok])
        if not I:
            continue
        idx = np.concatenate(I); w = np.concatenate(Wt)
        W += np.bincount(idx, w, minlength=n)
        WX += np.bincount(idx, w * np.concatenate(PX), minlength=n)
        WY += np.bincount(idx, w * np.concatenate(PY), minlength=n)
        WZ += np.bincount(idx, w * np.concatenate(PZ), minlength=n)
        WR += np.bincount(idx, w * np.concatenate(RR), minlength=n)
    X = (GX0 + H * np.arange(NX))[None, :]; Y = (GY0 + H * np.arange(NY))[:, None]
    W = W.reshape(NY, NX)
    with np.errstate(invalid="ignore", divide="ignore"):
        xb = WX.reshape(NY, NX) / W; yb = WY.reshape(NY, NX) / W; zb = WZ.reshape(NY, NX) / W; rb = WR.reshape(NY, NX) / W
        phi = np.sqrt((X - xb) ** 2 + (Y - yb) ** 2 + zb ** 2) - rb
    phi = np.where(W > 0, phi, R).astype(np.float64)
    return phi, W, int(m.sum())


def bilinear(S, x0, dx, y0, dy, X, Y):
    fi = (X - x0) / dx; fj = (Y - y0) / dy
    i = np.clip(np.floor(fi).astype(int), 0, S.shape[1] - 2); j = np.clip(np.floor(fj).astype(int), 0, S.shape[0] - 2)
    a = fi - i; b = fj - j
    return (1 - a) * (1 - b) * S[j, i] + a * (1 - b) * S[j, i + 1] + (1 - a) * b * S[j + 1, i] + a * b * S[j + 1, i + 1]


def crossings_per_col(phi):
    s = phi < 0
    return np.abs(np.diff(s.astype(np.int8), axis=0)).sum(0)


def top_y(phi, ys):
    """各列の一番上の 0 の交わり（下が水・上が空気になる最も高い所）"""
    neg = phi < 0
    ny = phi.shape[0]
    has = neg.any(0)
    jt = ny - 1 - np.argmax(neg[::-1, :], axis=0)
    jt = np.clip(jt, 0, ny - 2)
    c = np.arange(phi.shape[1])
    v0 = phi[jt, c]; v1 = phi[jt + 1, c]
    fr = np.where(v1 - v0 > 1e-12, -v0 / np.maximum(v1 - v0, 1e-12), 0.0)
    return np.where(has, ys[jt] + (ys[1] - ys[0]) * np.clip(fr, 0, 1), np.nan)


def one(args):
    f, run_dir, rec_dir, out, rinfo = args
    t0 = time.time()
    P = np.load(os.path.join(run_dir, "particles", "p_%04d.npy" % f))
    rp = os.path.join(run_dir, "particles", "r_%04d.npy" % f)
    r = np.load(rp) if os.path.exists(rp) else float(rinfo[str(f)])
    rec = L.Records(rec_dir)
    S, xs_rel, ys_h, m = rec.sec(f, 0.0)            # ys_h はずれを引かない（解く格子の y）
    eh, xh_rel = rec.hf(f, 0.0)
    phi_c, W, n_used = zb_phi(P, r, z0=float(m["z"]))
    Xs = GX0 + H * np.arange(NX); Ys = GY0 + H * np.arange(NY)
    insec = (Xs >= SEC_X[0] - 1e-9) & (Xs <= SEC_X[1] + 1e-9)
    # 解く格子の面（符号と帯）
    XX, YY = np.meshgrid(Xs, Ys)
    ref = np.empty((NY, NX))
    ref[:, insec] = bilinear(S, m["x0"], m["dx"], m["y0"], m["dy"], XX[:, insec], YY[:, insec])
    et = np.interp(Xs, xh_rel + L.XP, eh)
    ref[:, ~insec] = (YY[:, ~insec] - et[None, ~insec])     # 一番上の水面からの高さ（符号が同じ）
    band = np.abs(ref) <= BAND
    fill = np.where(ref < 0, -1.0, 1.0)
    phi = np.where(band, phi_c, fill)
    # 帯の端の符号の食い違い（計算した節が、隣の埋めた節と符号が違う）
    sgn = phi < 0
    mis = np.zeros(NX, bool)
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        nb_band = np.roll(band, sh, axis=ax); nb_sgn = np.roll(sgn, sh, axis=ax)
        edge = band & ~nb_band & (sgn != nb_sgn)
        if ax == 0:
            edge[0 if sh == 1 else -1, :] = False
        else:
            edge[:, 0 if sh == 1 else -1] = False
        mis |= edge.any(0)
    nc = crossings_per_col(phi)
    multi_out = (~insec) & (nc != 1)
    full_cols = mis | multi_out
    phi[:, full_cols] = phi_c[:, full_cols]
    computed = band.copy(); computed[:, full_cols] = True
    nc2 = crossings_per_col(phi)
    sgn2 = phi < 0
    mis2 = 0
    for ax, sh in ((0, 1), (0, -1), (1, 1), (1, -1)):
        nb_c = np.roll(computed, sh, axis=ax); nb_s = np.roll(sgn2, sh, axis=ax)
        e = computed & ~nb_c & (sgn2 != nb_s)
        if ax == 0:
            e[0 if sh == 1 else -1, :] = False
        else:
            e[:, 0 if sh == 1 else -1] = False
        mis2 += int(e.sum())
    zero_w_band = int(((W <= 0) & band & (ref < 0)).sum())   # 帯の中の、解く格子では水なのに半径の中に粒子がない節
    p = os.path.join(out, "phi_%04d.npz" % f)
    np.savez_compressed(p, phi=phi.astype(np.float32), computed=computed, x0_rel=GX0 - L.XP, dx=H, y0_abs=GY0, dy=H, frame=f)
    st = dict(frame=f, n_particles=int(len(P)), n_slab=n_used, band_nodes=int(band.sum()), cols_edge_mismatch=int(mis.sum()),
              cols_multi_outside_sec=int(multi_out.sum()), cols_full=int(full_cols.sum()),
              cols_multi_outside_sec_after=int(((~insec) & (nc2 != 1)).sum()), edge_mismatch_nodes_after=mis2,
              band_nodes_no_particles=zero_w_band, radius=(float(r) if not np.ndim(r) else [float(r.min()), float(r.max())]),
              seconds=round(time.time() - t0, 2), sha256=sha(p))
    return st


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--records", default=None)
    ap.add_argument("--frames", default="%d-%d" % (L.F0, L.F1))
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run_dir = a.run_dir; rec_dir = a.records or run_dir
    out = a.out or os.path.join(run_dir, "fine")
    os.makedirs(out, exist_ok=True)
    if "," in a.frames:
        frames = [int(v) for v in a.frames.split(",")]
    else:
        f0, f1 = [int(v) for v in a.frames.split("-")]
        frames = list(range(f0, f1 + 1))
    # 粒子の半径（書き出しの記録から）
    rinfo, fop = {}, {}
    for pj in sorted(glob.glob(os.path.join(run_dir, "pexp_c*.json"))):
        d = json.load(open(pj, encoding="utf8"))
        fop = d.get("flip_object_parms", fop)
        for row in d["rows"]:
            if row.get("pscale_min") is not None:
                rinfo[str(row["frame"])] = row["pscale_min"]
    missing = [f for f in frames if not os.path.exists(os.path.join(run_dir, "particles", "r_%04d.npy" % f)) and str(f) not in rinfo]
    if missing:
        raise SystemExit("particle radius unknown for frames %s (pscale がない)" % missing[:5])
    T0 = time.time()
    jobs = [(f, run_dir, rec_dir, out, rinfo) for f in frames]
    if a.workers > 1:
        with Pool(a.workers) as pool:
            stats = pool.map(one, jobs, chunksize=1)
    else:
        stats = [one(j) for j in jobs]
    # 静かな水面のずれ（3319 コマ目）
    rec = L.Records(rec_dir)
    off_note = None
    if L.F0 in frames:
        z = np.load(os.path.join(out, "phi_%04d.npz" % L.F0))
        phi = z["phi"]; ys = float(z["y0_abs"]) + H * np.arange(phi.shape[0])
        tf = top_y(phi[:, ::4], ys)                      # hf の節に重なる列（4 列おき）
        eh, xh = rec.hf(L.F0, 0.0)
        xf = (GX0 + H * np.arange(NX))[::4] - L.XP
        ii = np.rint((xf - xh[0]) / (xh[1] - xh[0])).astype(int)
        et = eh[ii]
        slope = np.degrees(np.arctan(np.abs(np.gradient(eh, xh[1] - xh[0]))))[ii]
        ok = np.isfinite(tf) & np.isfinite(et) & (slope < 10.0)
        dmed = float(np.median(tf[ok] - et[ok]))
        off = L.OFF_R3 + dmed
        off_note = dict(frame=L.F0, n_cols=int(ok.sum()), median_fine_minus_solver=dmed, p05_p95=[float(np.percentile(tf[ok] - et[ok], 5)), float(np.percentile(tf[ok] - et[ok], 95))])
    else:
        mp = os.path.join(out, "meta.json")
        off = json.load(open(mp, encoding="utf8"))["still_offset_m"] if os.path.exists(mp) else None
    radii = sorted(set(json.dumps(s["radius"]) for s in stats))
    meta = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/rt48/r_surface.py", run_dir=run_dir, records=rec_dir,
                method="Zhu & Bridson 2005：φ = |x − x̄| − r̄、重み (1 − s²)³、R = %g m、節 %g m、z = 0 の平面、3D の距離" % (R, H),
                grid=dict(x0_scene=GX0, x0_rel=GX0 - L.XP, nx=NX, dx=H, y0_abs=GY0, ny=NY, dy=H, y1_abs=GY1),
                band=dict(m=BAND, sec_x_scene=SEC_X, fill=[-1.0, 1.0]), radius_values=radii, flip_object_parms=fop,
                still_offset_m=off, still_offset_note=off_note, frames=[frames[0], frames[-1]],
                totals=dict(cols_full_max=max(s["cols_full"] for s in stats), cols_full_sum=sum(s["cols_full"] for s in stats),
                            cols_edge_mismatch_sum=sum(s["cols_edge_mismatch"] for s in stats),
                            cols_multi_outside_sec_sum=sum(s["cols_multi_outside_sec"] for s in stats),
                            cols_multi_outside_sec_after_sum=sum(s["cols_multi_outside_sec_after"] for s in stats),
                            edge_mismatch_nodes_after_sum=sum(s["edge_mismatch_nodes_after"] for s in stats),
                            band_nodes_no_particles_max=max(s["band_nodes_no_particles"] for s in stats),
                            n_particles_min_max=[min(s["n_particles"] for s in stats), max(s["n_particles"] for s in stats)]),
                seconds=round(time.time() - T0, 1), per_frame=stats)
    json.dump(meta, open(os.path.join(out, "meta.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps({k: v for k, v in meta.items() if k != "per_frame"}, ensure_ascii=False, indent=1, default=float))


if __name__ == "__main__":
    main()
