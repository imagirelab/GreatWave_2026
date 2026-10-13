# -*- coding: utf-8 -*-
"""FLIP46：孤立波の頂の高さと速さを、厳密な孤立波（g46_solitary）と比べる（py -3.10。統合の役、2026-10-12）。
R1（hf：一番上の水面の高さ η_top[横, x]）から、3 つの横の位置（対称の面の層 y = 格子/2、真ん中 y = W/2、外の壁の層 y = W − 格子/2）で
  - 頂の高さ：最大の点を放物線で補った高さ − 静かな水面のずれ（run.json の still_offset。1 コマ目は初めの網なので引かない）
  - 頂の x：η > 0.5 η_max の部分の重心（孤立波は頂が平らなので最大の点より揺れが小さい）
  - 速さ：頂の x の時刻への直線の当てはめ（t 0.25 s から終わりまで、と 1 s ごと）
  - 平らな海底（ridge_on 0）：同じ時刻の厳密な η(x − c t) との差の RMS（頂の ±60 m）と、厳密な頂の x との差
  - 尾根の上：頂の x のその所の水深（尾根の式）と H/h
使い方：py -3.10 x46_wave_track.py <run_dir> [...]   → <run_dir>/wave_track.json と標準出力
"""
import sys, os, json, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g46_common as GC
import g46_solitary as S


def load_hf(rd):
    best = {}
    for p in sorted(glob.glob(os.path.join(rd, "hf_c*_b*.npz"))):
        d = np.load(p)
        meta = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            best[int(f)] = (d["eta"][i], meta, float(d["t"][i]))
    return best


def peak(e, xs):
    e2 = np.where(np.isfinite(e), e, -1e9)
    i = int(np.argmax(e2))
    if 0 < i < len(e2) - 1:
        a, b, c = e2[i - 1], e2[i], e2[i + 1]
        den = a - 2 * b + c
        sh = 0.5 * (a - c) / den if den < 0 else 0.0
        return float(xs[i] + sh * (xs[1] - xs[0])), float(b - 0.25 * (a - c) * sh)
    return float(xs[i]), float(e2[i])


def centroid(e, xs, frac=0.5):
    e = np.where(np.isfinite(e), e, 0.0)
    i = int(np.argmax(e)); thr = frac * e[i]
    lo = i
    while lo > 0 and e[lo - 1] > thr:
        lo -= 1
    hi = i
    while hi < len(e) - 1 and e[hi + 1] > thr:
        hi += 1
    w = np.clip(e[lo:hi + 1] - thr, 0, None)
    return float((xs[lo:hi + 1] * w).sum() / max(w.sum(), 1e-12))


def track(rd, wave):
    run = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
    P = run["parms"]
    off = float((run.get("still_offset") or {}).get("value") or 0.0)
    vox = float(P["dp"]) * float(P["gridscale"]); W = float(P["W"])
    ridge = float(P.get("ridge_on", 1.0)) > 0.5
    hf = load_hf(rd)
    fr = sorted(hf)
    out = dict(run_id=run["run_id"], dp=float(P["dp"]), ridge_on=ridge, still_offset_m=off, wave_kind=None,
               exact=dict(c=wave.c, H=wave.a_over_h * wave.h0, x0=wave.x0), rows={})
    try:
        out["wave_kind"] = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8")).get("solitary_kind")
    except Exception:
        pass
    for lab, yl in (("y0_layer", 0.5 * vox), ("mid", 0.5 * W), ("outer_layer", W - 0.5 * vox)):
        ts, xc, xp, hp, rms, hloc = [], [], [], [], [], []
        for f in fr:
            eta, meta, t = hf[f]
            iz = int(round((yl - meta["z0"]) / meta["dz"]))
            iz = max(0, min(eta.shape[0] - 1, iz))
            xs = meta["x0"] + meta["dx"] * np.arange(eta.shape[1])
            e = eta[iz] - (off if f > 1 else 0.0)
            ts.append(t); xc.append(centroid(e, xs))
            a, b = peak(e, xs); xp.append(a); hp.append(b)
            hloc.append(-float(GC.bed_z(xc[-1], yl, on=ridge)))
            if not ridge:
                m = np.abs(xs - xc[-1]) < 60.0
                ex = wave.eta(xs[m], t=t)
                rms.append(float(np.sqrt(np.nanmean((e[m] - ex) ** 2))))
        ts = np.array(ts); xc = np.array(xc); hp = np.array(hp); hloc = np.array(hloc)
        m = ts >= 0.25 - 1e-9
        c_fit = float(np.polyfit(ts[m], xc[m], 1)[0]) if m.sum() > 3 else None
        seg = []
        t_end = float(ts[-1])
        a_ = 0.25
        while a_ < t_end - 0.5:
            b_ = min(t_end, np.floor(a_) + 1.0)
            mm = (ts >= a_ - 1e-9) & (ts <= b_ + 1e-9)
            if mm.sum() > 3:
                seg.append(dict(t=[a_, b_], c_m_s=float(np.polyfit(ts[mm], xc[mm], 1)[0]), x_mean=float(xc[mm].mean()),
                                h_local_m=float(hloc[mm].mean()), crest_H_mean_m=float(hp[mm].mean()),
                                H_over_h=float(hp[mm].mean() / hloc[mm].mean())))
            a_ = b_
        row = dict(y=yl, c_fit_m_s=c_fit, c_fit_err_pct=100.0 * (c_fit / wave.c - 1.0) if c_fit else None, segments=seg,
                   H_f1=float(hp[0]), H_f2=float(hp[1]) if len(hp) > 1 else None, H_end=float(hp[-1]),
                   H_max=float(hp[1:].max()) if len(hp) > 1 else None, H_min=float(hp[1:].min()) if len(hp) > 1 else None,
                   x_end=float(xc[-1]), x_end_exact=float(wave.x0 + wave.c * ts[-1]), t_end=t_end,
                   series_t_x_H_hloc=[[round(float(a), 3), round(float(b), 2), round(float(c), 3), round(float(d), 2)]
                                      for a, b, c, d in zip(ts[::6], xc[::6], hp[::6], hloc[::6])])
        row["H_end_err_pct"] = 100.0 * (row["H_end"] / out["exact"]["H"] - 1.0)
        if rms:
            row["profile_rms_m"] = dict(f2=rms[1] if len(rms) > 1 else None, end=rms[-1], max_after_f1=float(max(rms[1:])) if len(rms) > 1 else None)
            row["lag_end_m"] = row["x_end_exact"] - row["x_end"]
        out["rows"][lab] = row
    json.dump(out, open(os.path.join(rd, "wave_track.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


if __name__ == "__main__":
    wv = S.get_wave()
    for rd in sys.argv[1:]:
        o = track(rd, wv)
        print("%s dp %.2f %s wave %s  still offset %.3f m  (exact c %.3f m/s, H %.2f m)" % (
            o["run_id"], o["dp"], "ridge" if o["ridge_on"] else "FLAT", o["wave_kind"], o["still_offset_m"], wv.c, o["exact"]["H"]))
        for lab, r in o["rows"].items():
            s = "  %-11s c_fit %.3f m/s (%+.2f %%)  H f2 %.2f  min %.2f  max %.2f  end %.2f m (%+.1f %%)" % (
                lab, r["c_fit_m_s"], r["c_fit_err_pct"], r["H_f2"], r["H_min"], r["H_max"], r["H_end"], r["H_end_err_pct"])
            if "profile_rms_m" in r:
                s += "  | profile rms end %.3f m, lag at end %.2f m" % (r["profile_rms_m"]["end"], r["lag_end_m"])
            print(s)
            for sg in r["segments"]:
                print("      t %.2f-%.2f  c %.2f m/s  x %.1f  h_local %.2f m  H %.2f m  H/h %.2f" % (
                    sg["t"][0], sg["t"][1], sg["c_m_s"], sg["x_mean"], sg["h_local_m"], sg["crest_H_mean_m"], sg["H_over_h"]))
