# -*- coding: utf-8 -*-
"""FLIP46：横の 2 つの壁（y = 0 の対称の面と y = W の外の壁）の近くの食い違いを読む（py -3.10。numpy だけ。統合の役、2026-10-12）。
平らな海底の孤立波（煙の試し STF）は横に一様なので、y = 0 の層と y = W の層は同じになるはず。違えば数値の偏り。
  - 水面：R2（y = 0 の壁に接する格子の層）と R3（y = W の壁に接する層。cfg の r3_z が W − 格子/2 の時）の一番上の水面の差（頂のまわり ±40 m）
  - 頂：R1 の層ごとの頂の x（η > 0.5 η_max の部分の重心）と高さ（静かな水面のずれを引く）
  - 粒子の横の流速：init_fFFFFF.npz（g46_run.py の init_dump）の頂のまわり ±3 m の粒子を横 1 m ごとに、水面の近く（z > 5 m）の平均
尾根の計算（P05 など）では、y = 0 の層（wall0）とその隣の 3 層（next3、y ≤ 3.5 格子）の頂の x と高さの差が数値の偏りの目安（物理の差は小さい）。
使い方：py -3.10 x46_wallsym.py <run_dir> [<run_dir> ...]   → <run_dir>/wallsym.json と標準出力
"""
import sys, os, json, glob
import numpy as np


def load(rd, kind):
    best = {}
    for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
        d = np.load(p)
        meta = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            best[int(f)] = ({k: d[k][i] for k in d.files if k not in ("frames", "t", "meta")}, meta, float(d["t"][i]))
    return best


def top_of(s, ys):
    s = s.astype(np.float64)
    ny = s.shape[0]
    out = np.full(s.shape[1], np.nan)
    for i in range(s.shape[1]):
        jj = np.where(s[:, i] < 0)[0]
        if not len(jj):
            continue
        j = min(jj.max(), ny - 2)
        v0, v1 = s[j, i], s[j + 1, i]
        out[i] = ys[j] + (ys[1] - ys[0]) * np.clip(-v0 / max(v1 - v0, 1e-9), 0, 1)
    return out


def centroid(e, xs):
    e = np.where(np.isfinite(e), e, 0.0)
    i = int(np.argmax(e)); thr = 0.5 * e[i]
    lo = i
    while lo > 0 and e[lo - 1] > thr:
        lo -= 1
    hi = i
    while hi < len(e) - 1 and e[hi + 1] > thr:
        hi += 1
    w = np.clip(e[lo:hi + 1] - thr, 0, None)
    return float((xs[lo:hi + 1] * w).sum() / max(w.sum(), 1e-12)), float(e[i])


def check(rd):
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    off = (run.get("still_offset") or {}).get("value") or 0.0
    out = dict(run_id=run["run_id"], solver=run.get("solver"), still_offset_m=off, surf=[], rows=[], lateral_v=[])
    r2 = load(rd, "r2"); r3 = load(rd, "r3")
    for f in sorted(r2):
        if f == 1 or f not in r3 or (f - 1) % 24:
            continue
        a, m2, t = r2[f]; b, m3, _ = r3[f]
        xs = m2["x0"] + m2["dx"] * np.arange(m2["nx"]); ys = m2["y0"] + m2["dy"] * np.arange(m2["ny"])
        e2 = top_of(a["sdf"], ys); e3 = top_of(b["sdf"], ys)
        k = int(np.nanargmax(e3)); sel = np.abs(xs - xs[k]) < 40
        d = e2 - e3
        out["surf"].append(dict(t=t, x_crest=float(xs[k]), d_mean_abs=float(np.nanmean(np.abs(d[sel]))), d_min=float(np.nanmin(d[sel])),
                                d_max=float(np.nanmax(d[sel])), z_r2=m2.get("z"), z_r3=m3.get("z")))
    hf = load(rd, "hf")
    for f in sorted(hf):
        if (f - 1) % 24 or f == 1:
            continue
        a, m, t = hf[f]
        eta = a["eta"]
        xs = m["x0"] + m["dx"] * np.arange(eta.shape[1]); zs = m["z0"] + m["dz"] * np.arange(eta.shape[0])
        row = dict(t=t, y=[], x_c=[], h=[])
        for iz in range(eta.shape[0]):
            xc, h = centroid(eta[iz] - off, xs)
            row["y"].append(float(zs[iz])); row["x_c"].append(xc); row["h"].append(h)
        xc = np.array(row["x_c"]); hh = np.array(row["h"])
        inner = slice(2, -2)
        near = slice(1, 4)        # y = 0 の層の隣の 3 層（尾根でも sech² の変わりは y 3.5 m で 0.3 % なので、物理の差は小さい）
        row["summary"] = dict(x_wall0=float(xc[0]), x_wallW=float(xc[-1]), x_inner_mean=float(np.mean(xc[inner])),
                              h_wall0=float(hh[0]), h_wallW=float(hh[-1]), h_inner_mean=float(np.mean(hh[inner])),
                              x_near0_mean=float(np.mean(xc[near])), h_near0_mean=float(np.mean(hh[near])))
        out["rows"].append(row)
    for p in sorted(glob.glob(os.path.join(rd, "init_f*.npz"))):
        d = np.load(p)
        P = d["P"].astype(np.float64); V = d["v"].astype(np.float64)
        dxs = [float(v) for v in d["probe_dx"]]
        if 0.0 not in dxs:
            continue
        xc = float(d["probe_x"][dxs.index(0.0)])
        m = (np.abs(P[:, 0] - xc) < 3.0) & (P[:, 1] > 5.0)
        Q = P[m]; W = V[m]
        bins = np.arange(0.0, float(np.ceil(Q[:, 2].max())) + 1e-9, 1.0) if len(Q) else np.arange(0, 2.0)
        prof = []
        for lo in bins[:-1]:
            s = (Q[:, 2] >= lo) & (Q[:, 2] < lo + 1.0)
            prof.append([float(lo + 0.5), int(s.sum()), float(W[s, 2].mean()) if s.any() else None, float(Q[s, 1].max()) if s.any() else None])
        out["lateral_v"].append(dict(frame=int(d["frame"]), t=float(d["t"]), x_crest=xc, profile_y_n_vmean_ztop=prof,
                                     v_min=float(W[:, 2].min()) if len(W) else None, v_max=float(W[:, 2].max()) if len(W) else None))
    json.dump(out, open(os.path.join(rd, "wallsym.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        o = check(rd)
        print(o["run_id"], "solver", json.dumps(o["solver"]))
        for s in o["surf"]:
            print("  t %.2f  surface(y=0 layer) - surface(y=W layer) near crest: mean|d| %.3f  min %.3f  max %.3f" % (s["t"], s["d_mean_abs"], s["d_min"], s["d_max"]))
        for r in o["rows"]:
            s = r["summary"]
            print("  t %.2f  crest x: wall0 %.2f  next3 %.2f  inner %.2f  wallW %.2f | h: wall0 %.2f  next3 %.2f  inner %.2f  wallW %.2f" % (
                r["t"], s["x_wall0"], s["x_near0_mean"], s["x_inner_mean"], s["x_wallW"], s["h_wall0"], s["h_near0_mean"], s["h_inner_mean"], s["h_wallW"]))
        for lv in o["lateral_v"]:
            if lv["frame"] < 10:
                continue
            pr = lv["profile_y_n_vmean_ztop"]
            print("  frame %d  particle v (z>5 m, crest ±3 m) min %.3f max %.3f; y<8 m: %s; y>W-8: %s" % (
                lv["frame"], lv["v_min"], lv["v_max"], " ".join("%.3f" % q[2] for q in pr[:8] if q[2] is not None),
                " ".join("%.3f" % q[2] for q in pr[-8:] if q[2] is not None)))
