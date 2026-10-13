# -*- coding: utf-8 -*-
"""FLIP47：煙の試しの記録を読んで数を出す（py -3.10。numpy だけ）。<run>/smoke_check.json に書き、要点を表示する。
  静かな水（wave_on 0）：平均の水面（hf の lvl）の 1 コマ目・2 コマ目・2 コマ目からの幅・最後の 1 s の動き、静かな水面のずれ、所ごとの平均、
    海底の中の粒子（leak）、粒子の速さの最大、粒子の数。
  孤立波：初めのコマの確かめ（init_check。格子・粒子・GN の式・表の流速）、頂の高さと速さ（hf の真ん中の 2 層の平均の水面で、
    η > 0.5 η_max の部分の重心の動き）、平均の水面の動き、粒子の数の増え、漏れ。
使い方：py -3.10 x47_smoke_check.py <run のフォルダー> [...]
"""
import sys, os, json, glob
import numpy as np


def load_hf(rd):
    fs = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")))
    out = {}
    for p in fs:
        d = np.load(p)
        for k in ("eta", "frames", "t", "lvl", "npts", "crest_x", "crest_eta", "wall", "ss_n"):
            out.setdefault(k, []).append(d[k])
        out["x"] = d["x"]
    return {k: (np.concatenate(v) if isinstance(v, list) else v) for k, v in out.items()}


def crest_track(H, t0=0.25):
    e = H["eta"]
    nz = e.shape[1]
    em = np.nanmean(e[:, [nz // 2 - 1, nz // 2], :], axis=1)
    x = H["x"]; t = H["t"]
    xs, ts, hs = [], [], []
    for i in range(len(t)):
        row = em[i]
        if not np.isfinite(row).any():
            continue
        mx = np.nanmax(row)
        m = np.isfinite(row) & (row > 0.5 * mx)
        xc = float(np.sum(x[m] * row[m]) / np.sum(row[m]))
        xs.append(xc); ts.append(float(t[i])); hs.append(float(mx))
    xs, ts, hs = np.array(xs), np.array(ts), np.array(hs)
    k = ts >= t0
    c = float(np.polyfit(ts[k], xs[k], 1)[0]) if k.sum() >= 3 else None
    seg = []
    for a, b in ((0.25, 1.0), (1.0, 2.0), (2.0, 3.0)):
        q = (ts >= a - 1e-9) & (ts <= b + 1e-9)
        if q.sum() >= 3:
            seg.append(dict(t=[a, b], c=float(np.polyfit(ts[q], xs[q], 1)[0])))
    return dict(c_fit=c, segments=seg, x_first=float(xs[0]), x_last=float(xs[-1]), t_last=float(ts[-1]),
                eta_max_first=float(hs[0]), eta_max_max=float(hs.max()), t_of_max=float(ts[int(np.argmax(hs))]), eta_max_last=float(hs[-1]),
                eta_series=[[round(float(a), 3), round(float(b), 3)] for a, b in zip(ts[::6], hs[::6])])


def check(rd):
    r = json.load(open(os.path.join(rd, "run_c0001.json"), encoding="utf8"))
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    H = load_hf(rd)
    info = r["info"]
    lvl = H["lvl"]; t = H["t"]
    out = dict(run_id=r["run_id"], stopped=r["stopped"], f_end_done=r["f_end_done"], wall_total_s=r["wall_total_s"],
               s_per_frame=r["wall_per_frame_median_s"], substeps=r["substeps_min_max"], rss_peak_gb=r["rss_peak_gb"],
               particles_first=int(H["npts"][0]), particles_last=int(H["npts"][-1]),
               particles_growth_pct=100.0 * (H["npts"][-1] / H["npts"][0] - 1.0), res_changes=info.get("res_changes"),
               still_offset=r.get("still_offset"))
    out["level"] = dict(f1=float(lvl[0]), f2=float(lvl[1]), min_from_f2=float(lvl[1:].min()), max_from_f2=float(lvl[1:].max()),
                        range_from_f2=float(lvl[1:].max() - lvl[1:].min()), end=float(lvl[-1]),
                        last_1s_change=float(lvl[-1] - lvl[t >= t[-1] - 1.0 - 1e-9][0]))
    lk = info.get("leak", [])
    out["leak"] = dict(max_below_bed=max(l["n_below_bed"] for l in lk) if lk else None,
                       min_gap_m=min(l["gap_min"] for l in lk) if lk else None,
                       max_out_x=max(l["n_out_x"] for l in lk) if lk else None, max_out_z=max(l["n_out_z"] for l in lk) if lk else None,
                       frames=[l["frame"] for l in lk])
    out["pstats"] = info.get("pstats")
    x = H["x"]
    bed = cfg["bed"]
    fe = H["eta"][-1]
    regions = [(0.0, 570.0, "flat"), (570.0, 742.45, "slope"), (742.45, 1130.0, "shelf")]
    out["level_regions_end"] = {nm: float(np.nanmean(fe[:, (x >= a) & (x < b)])) for a, b, nm in regions if ((x >= a) & (x < b)).any()}
    if float(cfg["parms"]["wave_on"]) > 0.5:
        out["crest"] = crest_track(H)
        sol = cfg.get("solitary", {})
        out["c_gn"] = sol.get("c_gn")
        rows = []
        for ic in info.get("init_check", []):
            for row in ic["rows"]:
                rows.append(dict(frame=ic["frame"], t=ic["t"], dx=row["dx"], x=round(row["x"], 3), y=row["y"],
                                 u_grid=row.get("u_grid"), u_gn=row["u_gn"], u_table=row["u_table"], u_part=row.get("u_part"),
                                 w_grid=row.get("w_grid"), w_gn=row["w_gn"], w_table=row["w_table"], w_part=row.get("w_part"),
                                 n_part=row["n_part"], bed_y=row["bed_y"], eta_gn=row["eta_gn"],
                                 du_grid=(row["u_grid"] - row["u_gn"]) if row.get("u_grid") is not None else None,
                                 dw_grid=(row["w_grid"] - row["w_gn"]) if row.get("w_grid") is not None else None))
        out["init_check"] = rows
        f1 = [q for q in rows if q["frame"] == 1]
        if f1:
            out["init_check_f1_max_abs_du"] = max(abs(q["du_grid"]) for q in f1 if q["du_grid"] is not None)
            out["init_check_f1_max_abs_dw"] = max(abs(q["dw_grid"]) for q in f1 if q["dw_grid"] is not None)
        out["init_check_errors"] = info.get("init_check_errors")
    json.dump(out, open(os.path.join(rd, "smoke_check.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    for rd in sys.argv[1:]:
        o = check(rd)
        print("==", o["run_id"], "stopped", o["stopped"], "frames", o["f_end_done"], "s/frame", o["s_per_frame"], "sub", o["substeps"],
              "pts %d -> %d (%+.2f %%)" % (o["particles_first"], o["particles_last"], o["particles_growth_pct"]))
        print("  level", json.dumps(o["level"]), "offset", o["still_offset"])
        print("  regions end", json.dumps(o["level_regions_end"]))
        print("  leak", json.dumps(o["leak"]))
        if "crest" in o:
            c = o["crest"]
            print("  crest c_fit %.3f (GN %.3f) seg %s eta first %.3f max %.3f at %.2f s last %.3f" % (
                c["c_fit"], o["c_gn"], [(s["t"], round(s["c"], 3)) for s in c["segments"]], c["eta_max_first"], c["eta_max_max"],
                c["t_of_max"], c["eta_max_last"]))
            print("  frame  dx    y      u_grid  u_gn    u_part  | w_grid  w_gn    w_part  n")
            for q in o["init_check"]:
                print("  %d  %+5.0f  %6.1f  %7.3f %7.3f %7s | %7.3f %7.3f %7s %d" % (
                    q["frame"], q["dx"], q["y"], q["u_grid"], q["u_gn"], "%.3f" % q["u_part"] if q["u_part"] is not None else "-",
                    q["w_grid"], q["w_gn"], "%.3f" % q["w_part"] if q["w_part"] is not None else "-", q["n_part"]))
            print("  f1 max |du| %.4f  max |dw| %.4f" % (o["init_check_f1_max_abs_du"], o["init_check_f1_max_abs_dw"]))
