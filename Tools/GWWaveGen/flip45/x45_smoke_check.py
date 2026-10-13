# -*- coding: utf-8 -*-
"""FLIP45：煙の試しの判定（py -3.10。計画 plan_ja.md §10.2 の判定。走らせる前に決めた幅のまま）。記録を読むだけで、計算はしない。
使い方：py -3.10 x45_smoke_check.py S1 [S2b S2a S3 S3b S5 S6 S10 ...]   → Unity/Build/FLIP45/smoke/smoke_results.json に足す
"""
import sys, os, json, glob, math, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import g45_common as GC

SM = GC.B45 + "/smoke"
RES = SM + "/smoke_results.json"


def load_run(rid):
    rd = os.path.join(SM, rid)
    recs = [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(rd, "run_c*.json")))]
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    return rd, cfg, recs


def series(rd, kind="hf"):
    """記録のブロックを読み、コマの順に並べる（同じコマは後の起動の物）。"""
    best = {}
    for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
        c0 = int(os.path.basename(p).split("_c")[1].split("_")[0])
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f not in best or best[f][0] <= c0:
                best[f] = (c0, p, i)
    return best


def r6(rd):
    out = {}
    for p in sorted(glob.glob(os.path.join(rd, "r6_c*.npz"))):
        d = np.load(p)
        for i, f in enumerate(d["frames"]):
            out[int(f)] = {k: float(d[k][i]) for k in ("t", "wall", "npts", "lvl", "ss_n", "rss", "surf_s") if k in d.files}
    return out


def r1b_still_cost():
    """FLIP42 R1b（2D の板、粒子 0.5 m）の 2〜48 コマ（ほとんど静かな水）の 1 粒子 1 コマの µs。"""
    p = GC.REPO + "/Unity/Build/FLIP42/runs/R1b/hf_c0001.npz"
    d = np.load(p)
    w = d["wall"][1:48]; n = d["npts"][1:48]
    n = np.where(n > 0, n, np.nan)
    nn = np.nanmax(d["npts"][:48])
    return dict(wall_median_s=float(np.median(w)), particles=float(nn), us_per_particle=float(np.median(w) / nn * 1e6))


def check_S1(rid):
    rd, cfg, recs = load_run(rid)
    r = recs[0]
    info = r["info"]
    vox = 2 * cfg["parms"]["dp"]
    o = r.get("offset_o", [0, 0, 0])
    ps2 = info["pstats"]["2"]
    vy = abs(ps2["vy_mean_mid"])
    R6 = r6(rd)
    lv = np.array([R6[f]["lvl"] for f in sorted(R6) if f >= 2])
    dl = float(np.max(np.abs(lv - lv[0])))
    # 場の箱（Houdini の座標）：中心に置いた場は同じ端、面に置いた場はその向きに格子の半分ずつ外へ
    fb = info["fieldbox"]["2"]
    ref = fb["surface"][0]
    bad = []
    for nm, lst in fb.items():
        if not lst:
            continue
        for e in lst:
            ax = {"x": 0, "y": 1, "z": 2}.get((e["name"] or "").split(".")[-1]) if "." in (e["name"] or "") else None
            for j in range(3):
                lo = float(e["bmin"][j]); hi = float(e["bmax"][j])
                rlo = float(ref["bmin"][j]); rhi = float(ref["bmax"][j])
                if ax == j:
                    rlo -= 0.5 * vox; rhi += 0.5 * vox
                if lo != rlo or hi != rhi:
                    bad.append([nm, e["name"], j, lo, rlo, hi, rhi])
    bottom_plan = float(ref["bmin"][1]) - o[1]
    walls_plan = dict(x_min=float(ref["bmin"][0]) - o[0], z_min=float(ref["bmin"][2]) - o[2], y_min=bottom_plan,
                      x_max=float(ref["bmax"][0]) - o[0], z_max=float(ref["bmax"][2]) - o[2])
    # 壁の層と内側の静かな水面（0.5〜2.0 s）
    hb = series(rd, "hf")
    fr = [f for f in sorted(hb) if 0.5 - 1e-9 <= (f - 1) / 24.0 <= 2.0 + 1e-9]
    meta = json.loads(str(np.load(hb[fr[0]][1])["meta"]))
    zs = meta["z0"] + meta["dz"] * np.arange(meta["res"][2])
    wall_l, inner = [], []
    for f in fr:
        e = np.load(hb[f][1])["eta"][hb[f][2]]
        wall_l.append(np.nanmedian(e[0])); inner.append(np.nanmedian(e[zs > 10.0]))
    off = float(np.median(inner))
    dwall = float(np.median(wall_l) - np.median(inner))
    walls = [f for f in sorted(R6) if f >= 2]
    wpf = float(np.median([R6[f]["wall"] for f in walls]))
    npts = max(R6[f]["npts"] for f in R6)
    out = dict(rid=rid, dp=cfg["parms"]["dp"], frames=len(R6), vy_mean_frame2=ps2["vy_mean_mid"], vy_ok=bool(vy <= 0.001),
               level_move_max_m=dl, level_ok=bool(dl <= 0.05), fieldbox_mismatch=bad, fieldbox_ok=not bad,
               walls_plan=walls_plan, bottom_ok=bool(bottom_plan == -20.0 and walls_plan["z_min"] == 0.0 and walls_plan["x_min"] == cfg["parms"]["x0"]),
               still_offset_m=off, wall_minus_interior_m=dwall, wall_layer_ok=bool(abs(dwall) <= 0.02),
               s_per_frame=wpf, particles=npts, particles_per_m3=npts / (cfg["box"]["Lx"] * cfg["box"]["W"] * 20.0),
               us_per_particle_frame=wpf / npts * 1e6, rss_peak_gb=r["rss_peak_gb"], substeps=r["substeps_min_max"])
    out["pass"] = bool(out["vy_ok"] and out["level_ok"] and out["fieldbox_ok"] and out["bottom_ok"] and out["wall_layer_ok"])
    return out


# ------------------------------------------------------------------ 波の試し（S2b・S2a・S2c・S3・S3b）
OM = GC.OM; K0 = GC.K0; T = GC.T


_GCACHE = {}


def eta_series(rd, x, y, t_lo=None, t_hi=None):
    """一番上の水面の高さ（計画の座標）を点 (x, 横 y) で時系列に（格子の中心の間は x・横の線形の補間）。返り値 (t, η)。
    同じ計算の点は g45_analyze.gauges で一度に読んで覚える（prefetch）。"""
    key = (rd, float(x), float(y))
    if key in _GCACHE:
        t, e = _GCACHE[key]
        m = np.ones(len(t), bool)
        if t_lo is not None:
            m &= t >= t_lo - 1e-9
        if t_hi is not None:
            m &= t <= t_hi + 1e-9
        return t[m], e[m]
    return _eta_series_slow(rd, x, y, t_lo, t_hi)


def prefetch(rd, pts):
    import g45_analyze as GA
    R1 = GA.Reader(rd, "hf", "eta")
    t, E = GA.gauges(R1, pts)
    for i, (x, y) in enumerate(pts):
        _GCACHE[(rd, float(x), float(y))] = (t, E[i])


def _eta_series_slow(rd, x, y, t_lo=None, t_hi=None):
    """一番上の水面の高さ（計画の座標）を点 (x, 横 y) で時系列に（格子の中心の間は x・横の線形の補間）。返り値 (t, η)。"""
    hb = series(rd, "hf")
    tt, ee = [], []
    cache = {}
    for f in sorted(hb):
        c0, pth, i = hb[f]
        if pth not in cache:
            d = np.load(pth)
            cache = {pth: (d["eta"], d["t"], json.loads(str(d["meta"])))}
        E, ts, meta = cache[pth]
        t = float(ts[i])
        if (t_lo is not None and t < t_lo - 1e-9) or (t_hi is not None and t > t_hi + 1e-9):
            continue
        xs = meta["x0"] + meta["dx"] * np.arange(meta["res"][0]); zs = meta["z0"] + meta["dz"] * np.arange(meta["res"][2])
        fx = np.clip((x - xs[0]) / meta["dx"], 0, len(xs) - 1.000001); ix = int(fx); wx = fx - ix
        fz = np.clip((y - zs[0]) / meta["dz"], 0, len(zs) - 1.000001); iz = int(fz); wz = fz - iz
        e = E[i]
        v = (1 - wz) * ((1 - wx) * e[iz, ix] + wx * e[iz, ix + 1]) + wz * ((1 - wx) * e[iz + 1, ix] + wx * e[iz + 1, ix + 1])
        tt.append(t); ee.append(float(v))
    return np.array(tt), np.array(ee)


def fit_omega(t, e, om=OM):
    """η ≈ m + a cos(ωt) + b sin(ωt) の最小二乗。返り値 (振幅, 位相 φ（η = A cos(ωt − φ)）, 平均)。"""
    M = np.stack([np.ones_like(t), np.cos(om * t), np.sin(om * t)], 1)
    c, *_ = np.linalg.lstsq(M, e, rcond=None)
    return float(math.hypot(c[1], c[2])), float(math.atan2(c[2], c[1])), float(c[0])


def check_S2b(suffix=""):
    out = {}
    for dp in GC.PLAN_DP:
        rid = "S2b_dp%s" % repr(dp).replace(".", "p") + suffix
        rd = os.path.join(SM, rid)
        if not os.path.exists(os.path.join(rd, "run.json")):
            continue
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        r = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
        W = cfg["box"]["W"]
        amps = {}
        for x in (40.0, 56.0):
            t, e = eta_series(rd, x, 0.5 * W, 21.0, 42.0)
            A, ph, m = fit_omega(t, e)
            amps[str(x)] = dict(amp=A, phase=ph, mean=m, ratio=A / 2.0, n=len(t))
        rr = [amps[k]["ratio"] for k in amps]
        o = dict(rid=rid, dp=dp, points=amps, r0=float(np.mean(rr)), spread=float(max(rr) - min(rr)), stopped=r.get("stopped"),
                 f_end_done=r.get("f_end_done"), s_per_frame=r.get("wall_per_frame_median_s"), particles=r.get("particles_max"),
                 minutes=round(r.get("wall_launch_s", 0) / 60.0, 1), substeps=r.get("substeps_min_max"))
        o["pass"] = bool(0.85 <= o["r0"] <= 1.05 and o["spread"] <= 0.02 and not o["stopped"])
        out[repr(dp)] = o
    out["note_ja"] = "S2b：x 40・56 m の 21〜42 s（3 T）で周期 7 s の振幅 ÷ 2 m。r0 は 2 点の平均。判定 0.85 ≤ r0 ≤ 1.05、2 点の差 ≤ 0.02（計画 §10.2）"
    return out


def two_gauge(rd, x1, x2, t_lo, t_hi, y):
    """2 点で +x へ進む波と −x へ進む波を分ける（周期 7 s の成分）。返り値 (+x の振幅, −x の振幅)。"""
    Z = []
    for x in (x1, x2):
        t, e = eta_series(rd, x, y, t_lo, t_hi)
        M = np.stack([np.ones_like(t), np.cos(OM * t), np.sin(OM * t)], 1)
        c, *_ = np.linalg.lstsq(M, e, rcond=None)
        Z.append(complex(c[1], -c[2]))          # a cos ωt + b sin ωt = Re[(a − i b) e^{iωt}]
    # η(x) = Re[(I e^{−ikx} + R e^{+ikx}) e^{iωt}]
    A = np.array([[np.exp(-1j * K0 * x1), np.exp(1j * K0 * x1)], [np.exp(-1j * K0 * x2), np.exp(1j * K0 * x2)]])
    I, R = np.linalg.solve(A, np.array(Z))
    return abs(I), abs(R)


def check_S3():
    out = {}
    th = {"36": 0.037, "72": 0.018}
    thb = {"36": 0.327, "72": 0.127}
    for kind in ("S3", "S3b"):
        for band in ("36", "72"):
            rid = "%s_b%s" % (kind, band)
            rd = os.path.join(SM, rid)
            if not os.path.exists(os.path.join(rd, "run.json")):
                continue
            cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
            r = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))
            W = cfg["box"]["W"]
            if kind == "S3":
                x1, x2 = 80.0, 98.0
            else:
                x1, x2 = (80.0, 98.0) if band == "36" else (116.0, 134.0)
            t_hi = 80.0; t_lo = t_hi - 4 * T
            I, R = two_gauge(rd, x1, x2, t_lo, t_hi, 0.5 * W)
            if kind == "S3":
                cr = R / I; lim = 1.5 * th[band]
            else:
                cr = I / R; lim = 1.5 * thb[band]        # S3b：入る波は −x、跳ね返りは +x
            out[rid] = dict(gauges=[x1, x2], window=[t_lo, t_hi], amp_plus_x=I, amp_minus_x=R, CR=cr, theory=(th if kind == "S3" else thb)[band],
                            limit=lim, passed=bool(cr <= lim and not r.get("stopped")), stopped=r.get("stopped"),
                            minutes=round(r.get("wall_launch_s", 0) / 60.0, 1), particles=r.get("particles_max"))
    out["note_ja"] = ("S3：吸う帯（σχ²、σ 2.37/s）の跳ね返りが理論の 1.5 倍以下（36 m で 5.6 %、72 m で 2.7 %）。S3b：起こす帯（FLIP42 の重み、目標 0）の"
                      "跳ね返りが理論（36 m 33 %、72 m 13 %）の 1.5 倍以下。2 点で +x・−x の波を分ける（周期 7 s の成分、80 s で終わる 4 T の窓）")
    return out


def check_S2a(kind="S2a", suffix="", win=(24.0, 45.0)):
    out = {}
    for thv in (30, 45):
        rid = "%s_th%d" % (kind, thv) + suffix
        rd = os.path.join(SM, rid)
        recs = sorted(glob.glob(os.path.join(rd, "run_c*.json")))
        if not recs:
            continue
        cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        last = json.load(open(recs[-1], encoding="utf8"))
        th = math.radians(thv); p = K0 * math.sin(th)
        gain = 1.0
        if cfg["table"].get("gain_file"):
            tab_info = json.loads(str(np.load(cfg["table"]["npz"])["info"]))
            gain = float(tab_info.get("gain_scalar", 1.0))
        pts = [(72.0, 0.0), (72.0, 18.0), (108.0, 0.0), (108.0, 18.0)]
        prefetch(rd, pts + [(72.0, 66.0)] + [(90.0, float(y)) for y in np.arange(0.5, 70.0, 1.0)])
        res = []
        for (x, y) in pts:
            t, e = eta_series(rd, x, max(y, 0.0), win[0], win[1])
            A, ph, m = fit_omega(t, e)
            tgt = 2.0 * 1.0 * abs(math.cos(p * y))             # 線形の目標の振幅（利得なし）
            phase_t = (K0 * math.cos(th) * x) % (2 * math.pi)   # 目標：η = 2a cos(p y) cos(k cosθ x − Ωt) = A cos(Ωt − k cosθ x)
            dph = (ph - phase_t + math.pi) % (2 * math.pi) - math.pi
            res.append(dict(x=x, y=y, amp=A, target=tgt, ratio=A / tgt, phase_diff_rad=dph, mean=m))
        rr = [q["ratio"] for q in res]
        tc, ec = eta_series(rd, 72.0, 66.0, win[0], win[1])
        Ac, _, _ = fit_omega(tc, ec)
        corner = Ac / (2.0 * abs(math.cos(p * 66.0)))
        ys = np.arange(0.5, 70.0, 1.0)
        amp_y = []
        for y in ys:
            t, e = eta_series(rd, 90.0, y, win[0], win[1])
            amp_y.append(fit_omega(t, e)[0])
        amp_y = np.array(amp_y)
        best = None
        for pp in np.linspace(0.3 * p, min(K0 * 0.99, 2.0 * p), 2001):
            cosv = np.abs(np.cos(pp * ys))
            c = float(np.dot(cosv, amp_y) / max(np.dot(cosv, cosv), 1e-12))
            err = float(np.sum((amp_y - c * cosv) ** 2))
            if best is None or err < best[0]:
                best = (err, pp, c)
        th_fit = math.degrees(math.asin(min(best[1] / K0, 1.0)))
        o = dict(rid=rid, theta=thv, window=list(win), gain_in_table=gain, band_gains=dict(in_gain=cfg["parms"].get("in_gain", 1.0), sd_gain=cfg["parms"].get("sd_gain", 1.0)), points=res, mean_ratio=float(np.mean(rr)), spread=float(max(rr) - min(rr)),
                 corner_ratio=corner, corner_rel=corner / float(np.mean(rr)) - 1.0, theta_fit_deg=th_fit, theta_err_deg=th_fit - thv,
                 lateral_amp_scale=best[2], lateral_profile=dict(y=ys.tolist(), amp=amp_y.tolist()),
                 stopped=last.get("stopped"), f_end_done=last.get("f_end_done"))
        if kind == "S2a":
            o["pass"] = bool(o["spread"] <= 0.05 and abs(o["corner_rel"]) <= 0.05 and abs(o["theta_err_deg"]) <= 3.0)
        else:
            o["pass"] = bool(all(abs(q["ratio"] - 1.0) <= 0.05 and abs(q["phase_diff_rad"]) <= 0.10 for q in res) and abs(o["theta_err_deg"]) <= 3.0)
        out[str(thv)] = o
    out["note_ja"] = ("S2a：x 72・108 m × y 0・18 m の 24〜45 s の周期 7 s の振幅の比 r(θ)。4 点の差 ≤ 0.05、角 (72, 66) が 4 点の平均の ±5 %、向き ±3°。"
                      "S2c（利得あり）：4 点で振幅が目標の ±5 %、位相 ±0.10 rad、向き ±3°（計画 §10.2）")
    return out


def save(key, val):
    R = json.load(open(RES, encoding="utf8")) if os.path.exists(RES) else {}
    R[key] = val
    R["_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    json.dump(R, open(RES, "w", encoding="utf8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    for k in sys.argv[1:]:
        if k == "S1":
            res = {}
            for rid in ("S1_dp0p5", "S1_dp0p34375", "S1_dp0p25", "S1_dp0p1767578125"):
                if os.path.exists(os.path.join(SM, rid, "run.json")):
                    res[rid] = check_S1(rid)
            res["R1b_still_cost"] = r1b_still_cost()
            res["note_ja"] = ("S1：2 コマ目の縦の速さの平均の大きさ ≤ 0.001 m/s、2 コマ目からの水面の平均の動き ≤ 0.05 m、2 コマ目の場の箱の端が全部同じ"
                              "（面に置いた場は格子の半分外）、場の箱の下の端が −20 m ちょうど（計画の座標）、y = 0 の壁の層と内側の静かな水面の差 ≤ 0.02 m")
            save("S1", res)
            print(json.dumps(res, ensure_ascii=False, indent=1))
        elif k == "S2b":
            res = check_S2b(); save("S2b_x180_first", res); print(json.dumps(res, ensure_ascii=False, indent=1))
        elif k == "S2b_x252":
            res = check_S2b("_x252"); save("S2b", res); print(json.dumps(res, ensure_ascii=False, indent=1))
        elif k == "S3":
            res = check_S3(); save("S3_S3b", res); print(json.dumps(res, ensure_ascii=False, indent=1))
        elif k == "S2a":
            res = check_S2a("S2a", "_x228"); save("S2a", res)
            res2 = check_S2a("S2a", "_x228", (35.0, 45.5)); save("S2a_late_window_35_45p5", res2)
            print(json.dumps(res, ensure_ascii=False, indent=1))
        elif k == "S2c":
            res = check_S2a("S2c", "_x256", (37.0, 58.0)); save("S2c", res); print(json.dumps(res, ensure_ascii=False, indent=1))
