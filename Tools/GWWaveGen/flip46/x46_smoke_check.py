# -*- coding: utf-8 -*-
"""FLIP46：煙の試しの数を読む（py -3.10。numpy だけ）。結果は smoke/<run_id>/smoke_check.json と標準出力。
  SA（静かな水）：平均の水面（箱の全部と 5 つの所。2 コマ目からの動き。1 コマ目は初めの網なので比べない：FLIP44 の読み方 3）、
     自由落下の見張り、海底の中への漏れ（y − 海底 < −格子/4 の粒子の数）、粒子の数の増え、粒子の速さの最大。
  SB（孤立波）：初めのコマの格子の流速（頂の真下の深さ h0/2 ほか。g46_run.py の info.init_check）と解の値の比、
     頂の x の動き（R1 の一番上の水面の、対称の面の格子の列と横の真ん中の列。頂の x は η > 0.5 η_max の部分の重心）から速さ、
     頂の高さ（静かな水面のずれを引いた値）、平均の水面の動き、漏れ。
使い方：py -3.10 x46_smoke_check.py <run_dir> [<run_dir> ...]
"""
import sys, os, json, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC


def load_hf(rd):
    best = {}
    for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz"))):
        d = np.load(p)
        meta = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            best[int(f)] = (d["eta"][i], meta, float(d["t"][i]))
    return best


def crest_x(eta_row, x0, dx, xmin=None):
    e = np.where(np.isfinite(eta_row), eta_row, -1e9)
    xs = x0 + dx * np.arange(len(e))
    if xmin is not None:
        e = np.where(xs >= xmin, e, -1e9)
    i = int(np.argmax(e))
    if 0 < i < len(e) - 1:
        a, b, c = e[i - 1], e[i], e[i + 1]
        den = a - 2 * b + c
        sh = 0.5 * (a - c) / den if den < 0 else 0.0
        return float(xs[i] + sh * dx), float(b - 0.25 * (a - c) * sh)
    return float(xs[i]), float(e[i])


def crest_centroid(eta_row, x0, dx, frac=0.5):
    """頂の x を、η > frac × η_max の部分の重心で（孤立波は頂が平らなので、最大の点より揺れが小さい）。"""
    e = np.where(np.isfinite(eta_row), eta_row, 0.0)
    xs = x0 + dx * np.arange(len(e))
    i = int(np.argmax(e)); thr = frac * e[i]
    lo = i
    while lo > 0 and e[lo - 1] > thr:
        lo -= 1
    hi = i
    while hi < len(e) - 1 and e[hi + 1] > thr:
        hi += 1
    w = np.clip(e[lo:hi + 1] - thr, 0, None)
    return float((xs[lo:hi + 1] * w).sum() / max(w.sum(), 1e-12))


def check(rd):
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    run = json.load(open(os.path.join(rd, "run_c00001.json"), encoding="utf8"))
    info = run.get("info", {})
    r6 = np.load(os.path.join(rd, "r6_c00001.npz"))
    fr = r6["frames"]; t = r6["t"]; lvl = r6["lvl"]; lreg = r6["lvl_reg"]; npts = r6["npts"]
    off = (run.get("still_offset") or {}).get("value")
    out = dict(run_id=run["run_id"], dp=cfg["parms"]["dp"], wave_on=cfg["parms"]["wave_on"], frames=int(fr[-1]), t_end=float(t[-1]),
               stopped=run.get("stopped"), s_per_frame=run.get("wall_per_frame_median_s"), wall_total_s=run.get("wall_total_s"),
               substeps=run.get("substeps_min_max"), rss_gb=run.get("rss_peak_gb"), still_offset_m=off,
               particles=dict(first=int(npts[0]), f2=int(npts[1]) if len(npts) > 1 else None, last=int(npts[-1]),
                              growth_pct_from_f2=float(100 * (npts[-1] / npts[1] - 1)) if len(npts) > 1 else None))
    k2 = 1                                  # 2 コマ目
    dl = lvl[k2:] - lvl[k2]
    out["mean_level_all"] = dict(f2=float(lvl[k2]), last=float(lvl[-1]), max_abs_change_from_f2_m=float(np.max(np.abs(dl))),
                                 drift_m_per_s=float(np.polyfit(t[k2:], lvl[k2:], 1)[0]) if len(t) > 3 else None)
    names = [str(v) for v in r6["regions"]]
    out["mean_level_regions"] = {names[j]: dict(f2=float(lreg[k2, j]), last=float(lreg[-1, j]),
                                                max_abs_change_from_f2_m=float(np.nanmax(np.abs(lreg[k2:, j] - lreg[k2, j]))))
                                 for j in range(lreg.shape[1])}
    out["leak"] = info.get("leak")
    out["pstats"] = {k: {kk: v[kk] for kk in ("n", "speed_max", "speed_max_at", "n_below_bed", "gap_min", "ymin_all")} for k, v in (info.get("pstats") or {}).items()}
    if cfg["parms"]["wave_on"] > 0.5:
        # 初めのコマの流速
        rows = []
        for ic in info.get("init_check", []):
            for r in ic["rows"]:
                rr = dict(frame=ic["frame"], dx=r["dx"], x=round(r["x"], 3), y=r["y"], zl=r["zl"], u_ana=r["u_ana"], u_grid=r["u_grid"],
                          u_part=r.get("u_part"), w_ana=r["w_ana"], w_grid=r["w_grid"], w_part=r.get("w_part"), n_part=r["n_part"])
                rr["u_grid_over_ana"] = r["u_grid"] / r["u_ana"] if r["u_grid"] is not None and abs(r["u_ana"]) > 1e-6 else None
                rows.append(rr)
        out["init_check"] = rows
        out["init_check_errors"] = info.get("init_check_errors")
        key = [r for r in rows if r["dx"] == 0.0 and abs(r["y"] + 0.5 * GC.H0) < 1e-6]
        out["init_mid_depth_crest"] = [dict(frame=r["frame"], zl=r["zl"], u_ana=round(r["u_ana"], 3), u_grid=round(r["u_grid"], 3) if r["u_grid"] is not None else None,
                                            u_part=round(r["u_part"], 3) if r.get("u_part") is not None else None) for r in key]
        # 頂の動き
        hf = load_hf(rd)
        trk = {}
        for lab, zl in (("zl_first", 0.5 * cfg["box"]["vox"]), ("zl_mid", 0.5 * cfg["box"]["W"])):
            xs_, ts_, hs_ = [], [], []
            for f in sorted(hf):
                eta, meta, tt = hf[f]
                iz = int(round((zl - meta["z0"]) / meta["dz"]))       # 1 コマ目は格子が違う（初めの VDB）ので、毎コマの meta で選ぶ
                xc, hc = crest_x(eta[iz], meta["x0"], meta["dx"])
                row = eta[iz] - (off or 0.0) if f > 1 else eta[iz]        # 1 コマ目は初めの網（ずれなし）
                xs_.append(crest_centroid(row, meta["x0"], meta["dx"])); ts_.append(tt); hs_.append(hc - ((off or 0.0) if f > 1 else 0.0))
            xs_ = np.array(xs_); ts_ = np.array(ts_); hs_ = np.array(hs_)
            m = (ts_ >= 0.25) & (ts_ <= ts_[-1] + 1e-9)
            c_fit = float(np.polyfit(ts_[m], xs_[m], 1)[0]) if m.sum() > 3 else None
            seg = []
            for a_, b_ in ((0.25, 1.0), (1.0, 2.0), (2.0, 3.0)):
                mm = (ts_ >= a_ - 1e-9) & (ts_ <= b_ + 1e-9)
                if mm.sum() > 3:
                    xm = float(np.mean(xs_[mm]))
                    hloc = -float(GC.bed_z(xm, zl))
                    seg.append(dict(t=[a_, b_], c_m_s=float(np.polyfit(ts_[mm], xs_[mm], 1)[0]), x_mean=xm, local_depth_m=hloc,
                                    crest_height_mean_m=float(np.mean(hs_[mm]))))
            trk[lab] = dict(c_fit_m_s=c_fit, segments=seg, x_first=float(xs_[0]), x_last=float(xs_[-1]),
                            crest_h_first_m=float(hs_[0]), crest_h_f2_m=float(hs_[1]), crest_h_last_m=float(hs_[-1]),
                            series=[[round(float(a), 4), round(float(b), 3), round(float(c), 3)] for a, b, c in zip(ts_[::6], xs_[::6], hs_[::6])])
        out["crest_track"] = trk
        out["c_GN_flat_m_s"] = float(np.sqrt(GC.G * GC.H0 * (1 + GC.A0)))
    json.dump(out, open(os.path.join(rd, "smoke_check.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        o = check(rd)
        s = dict(o)
        s.pop("init_check", None)
        print(json.dumps(s, indent=1, ensure_ascii=False)[:6000])
