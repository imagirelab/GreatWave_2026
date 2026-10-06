# -*- coding: utf-8 -*-
"""P3 の主役の範囲の計算と、粗い計算 R18 の比べ（py -3.10）。
使い方: py -3.10 p3_compare_coarse.py <P3 の計算のフォルダー> [--fig]
- 一番上の水面 η(z, x)：R18 の hf.npz（2 m）を主役の範囲の升目へ線形に写し、境界の帯を除く内側で、コマごとの差（平均・RMS・最大）。
- 峰に沿う頂の高さ（z ごとの η の最大）と、その x：コマごと。
- 断面の出来事（sec/zXXX、P1 の解析）：R18 の同じ z の断面と並べる。
出力：<run_dir>/compare_R18.json（--fig で compare_R18.png）
"""
import sys, os, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
R18 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/R18_X30L120LG_H39"


def load_parts(rd):
    """hf_A.npz, hf_B.npz, … をつなぐ（同じコマは後の部分を使う）。"""
    parts = sorted(glob.glob(os.path.join(rd, "hf_*.npz")))
    E, S, F, T, L, N, W = [], [], [], [], [], [], []
    grid = None
    for p in parts:
        d = np.load(p)
        grid = json.loads(str(d["grid"]))
        E.append(d["eta"]); S.append(d["seg"]); F.append(d["frames"]); T.append(d["t"]); L.append(d["lvl"]); N.append(d["npts"]); W.append(d["wall"])
    F = np.concatenate(F); order = {}
    for i, f in enumerate(F):
        order[int(f)] = i
    idx = np.array([order[f] for f in sorted(order)])
    cat = lambda X: np.concatenate(X)[idx]
    return {"eta": cat(E).astype(np.float32), "seg": cat(S), "frames": F[idx], "t": cat(T), "lvl": cat(L), "npts": cat(N), "wall": cat(W), "grid": grid}


def load_r18():
    d = np.load(os.path.join(R18, "hf.npz"))
    g = json.loads(str(d["grid"]))
    eta = d["eta"].astype(np.float32)
    nf, nz, nx = eta.shape
    xs = g["x0"] + g["dx"] * np.arange(nx); zs = g["z0"] + g["dz"] * np.arange(nz)
    return {"eta": eta, "seg": d["seg"], "frames": d["frames"], "t": d["t"], "xs": xs, "zs": zs}


def interp2(E, xs, zs, X, Z):
    """E(z, x) を点 (X, Z) へ双線形に（NaN は近い値で埋めない：NaN のまま）。"""
    fx = np.clip((X - xs[0]) / (xs[1] - xs[0]), 0, len(xs) - 1.001); fz = np.clip((Z - zs[0]) / (zs[1] - zs[0]), 0, len(zs) - 1.001)
    i0 = np.floor(fx).astype(int); k0 = np.floor(fz).astype(int); a = fx - i0; b = fz - k0
    return ((1 - a) * (1 - b) * E[k0, i0] + a * (1 - b) * E[k0, i0 + 1] + (1 - a) * b * E[k0 + 1, i0] + a * b * E[k0 + 1, i0 + 1])


def main(rd, fig=False):
    W = load_parts(rd)
    R = load_r18()
    g = W["grid"]
    nf, nz, nx = W["eta"].shape
    xs = g["x0"] + g["dx"] * np.arange(nx); zs = g["z0"] + g["dz"] * np.arange(nz)
    wx0, wx1, wz0, wz1 = g["window"]; pad = g["pad"]
    ix = (xs > wx0 + pad + 2) & (xs < wx1 - pad - 2); iz = (zs > wz0 + pad + 2) & (zs < wz1 - pad - 2)
    X, Z = np.meshgrid(xs[ix], zs[iz])
    rows = []
    for k, f in enumerate(W["frames"]):
        j = np.where(R["frames"] == f)[0]
        if not len(j):
            continue
        er = interp2(R["eta"][j[0]], R["xs"], R["zs"], X, Z)
        ew = W["eta"][k][np.ix_(iz, ix)]
        d = ew - er
        ok = np.isfinite(d)
        # 峰に沿う頂の高さ
        cw = np.nanmax(np.where(np.isfinite(ew), ew, -99), axis=1); cr = np.nanmax(np.where(np.isfinite(er), er, -99), axis=1)
        jz0 = int(np.argmin(np.abs(zs[iz])))
        xw = X[0][int(np.nanargmax(np.where(np.isfinite(ew[jz0]), ew[jz0], -99)))]; xr = X[0][int(np.nanargmax(np.where(np.isfinite(er[jz0]), er[jz0], -99)))]
        rows.append({"frame": int(f), "t": float(W["t"][k]), "mean_diff_m": float(np.nanmean(d)), "rms_diff_m": float(np.sqrt(np.nanmean(d[ok] ** 2))),
                     "p99_absdiff_m": float(np.nanpercentile(np.abs(d[ok]), 99)), "max_absdiff_m": float(np.nanmax(np.abs(d[ok]))),
                     "crest_max_fine": float(cw.max()), "crest_max_R18": float(cr.max()),
                     "crest_z0_fine": float(cw[jz0]), "crest_z0_R18": float(cr[jz0]), "x_crest_z0_fine": float(xw), "x_crest_z0_R18": float(xr),
                     "crest_rms_diff_m": float(np.sqrt(np.mean((cw - cr) ** 2))), "npts": int(W["npts"][k]), "wall_s": float(W["wall"][k]),
                     "lvl": float(W["lvl"][k])})
    out = {"run_dir": rd, "frames": len(rows), "rows": rows}
    # 断面の出来事（あれば）
    try:
        import p1_analyze as A1
        ev = {}
        for sd in sorted(glob.glob(os.path.join(rd, "sec", "z*"))):
            nm = os.path.basename(sd)
            if not glob.glob(os.path.join(sd, "snap_*.npz")):
                continue
            r = A1.analyze(sd, quiet=True)
            rr = os.path.join(R18, "sec", nm)
            ref = None
            if os.path.isdir(rr) and os.path.isfile(os.path.join(rr, "analysis.json")):
                ref = json.load(open(os.path.join(rr, "analysis.json"), encoding="utf8")).get("events")
            ev[nm] = {"fine": r["events"], "R18": ref, "plunging": r.get("plunging")}
        out["section_events"] = ev
    except Exception as e:
        out["section_error"] = str(e)[:300]
    json.dump(out, open(os.path.join(rd, "compare_R18.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    for q in rows[:: max(1, len(rows) // 14)] + rows[-1:]:
        print("f=%d t=%.2f diff mean %+.3f rms %.3f p99 %.2f max %.2f | crest max %.2f/%.2f z0 %.2f/%.2f x %.0f/%.0f | crest rms %.2f | pts %d wall %.1f" % (
            q["frame"], q["t"], q["mean_diff_m"], q["rms_diff_m"], q["p99_absdiff_m"], q["max_absdiff_m"], q["crest_max_fine"], q["crest_max_R18"],
            q["crest_z0_fine"], q["crest_z0_R18"], q["x_crest_z0_fine"], q["x_crest_z0_R18"], q["crest_rms_diff_m"], q["npts"], q["wall_s"]))
    for nm, e in (out.get("section_events") or {}).items():
        def s(q):
            return "%.2f@%.0f" % (q["t"], q["x"]) if q else "-"
        fe, re_ = e["fine"], e["R18"] or {}
        print(nm, "fine onset/vert/tube", s(fe.get("breaking_onset_B085")), s(fe.get("face_past_vertical")), s(fe.get("tube_closed_or_nearly")),
              "| R18", s(re_.get("breaking_onset_B085")), s(re_.get("face_past_vertical")), s(re_.get("tube_closed_or_nearly")))
    if fig:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fr = [q["frame"] for q in rows]
        fig_, ax = plt.subplots(1, 3, figsize=(16, 4.5))
        t = [q["t"] for q in rows]
        ax[0].plot(t, [q["rms_diff_m"] for q in rows], label="RMS"); ax[0].plot(t, [q["p99_absdiff_m"] for q in rows], label="99%")
        ax[0].set_xlabel("t (s)"); ax[0].set_ylabel("|eta fine - eta R18| (m)"); ax[0].legend(); ax[0].grid(alpha=.3)
        ax[1].plot(t, [q["crest_z0_fine"] for q in rows], label="window z=0"); ax[1].plot(t, [q["crest_z0_R18"] for q in rows], "--", label="R18 z=0")
        ax[1].plot(t, [q["crest_max_fine"] for q in rows], label="window max"); ax[1].plot(t, [q["crest_max_R18"] for q in rows], "--", label="R18 max")
        ax[1].set_xlabel("t (s)"); ax[1].set_ylabel("crest (m)"); ax[1].legend(); ax[1].grid(alpha=.3)
        ax[2].plot(t, [q["x_crest_z0_fine"] for q in rows], label="window"); ax[2].plot(t, [q["x_crest_z0_R18"] for q in rows], "--", label="R18")
        ax[2].set_xlabel("t (s)"); ax[2].set_ylabel("crest x at z=0 (m)"); ax[2].legend(); ax[2].grid(alpha=.3)
        fig_.suptitle(os.path.basename(rd) + " vs R18 (physics only)")
        fig_.tight_layout(); fig_.savefig(os.path.join(rd, "compare_R18.png"), dpi=110)
    return out


if __name__ == "__main__":
    main(sys.argv[1], fig="--fig" in sys.argv)
