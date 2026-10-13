# -*- coding: utf-8 -*-
"""FLIP44 煙の試しの判定（計画 plan_ja.md §6 と record_ja.md の「計画の読み方」・「計画から変えた所」1 の決まりのとおり）。
py -3.10 x44_smoke_check.py [S1 S2f S2 S2b S3 S4 S4b S5 S7 S8 cost]  → Unity/Build/FLIP44/smoke/smoke_results.json（あれば足して書き直す）
"""
import sys, os, json, glob
import numpy as np

B = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP44"
SM = B + "/smoke"
R42 = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs"
PLAN = json.load(open(B + "/plan/plan_numbers.json", encoding="utf-8"))
CR = PLAN["criteria"]["smoke"]
FPS = 24.0


def load_hf(rd):
    files = sorted(glob.glob(os.path.join(rd, "hf_c*.npz")), key=lambda p: int(os.path.basename(p)[4:8]))
    F, E, W, N, SS, WC = [], [], [], [], [], []
    x = z = None
    for p in files:
        d = np.load(p)
        fr = list(d["frames"])
        if not fr:
            continue
        if F:
            keep = [i for i, f in enumerate(F) if f < fr[0]]
            F = [F[i] for i in keep]; E = [E[i] for i in keep]; W = [W[i] for i in keep]; N = [N[i] for i in keep]
            SS = [SS[i] for i in keep]; WC = [WC[i] for i in keep]
        F += fr; E += list(d["eta"]); W += list(d["wall"]); N += list(d["npts"]); SS += list(d["ss_n"])
        WC += list(d["wind_calls"]) if "wind_calls" in d.files else [-1] * len(fr)
        x = d["x"]; z = d["z"]
    return dict(frames=np.array(F), t=(np.array(F) - 1) / FPS, x=x, z=z, eta=np.array(E, np.float64), wall=np.array(W), npts=np.array(N),
                ss_n=np.array(SS), wind_calls=np.array(WC))


def load_sec(rd):
    best = {}
    for p in glob.glob(os.path.join(rd, "sec_c*_b*.npz")):
        f0 = int(os.path.basename(p)[5:9]); d = np.load(p)
        for i, f in enumerate(d["frames"]):
            f = int(f)
            if f >= f0 and (f not in best or best[f][0] < f0):
                best[f] = (f0, p, i)
    out = {}
    cache = {}
    for f, (f0, p, i) in sorted(best.items()):
        if p not in cache:
            cache[p] = np.load(p)["sdf"]
        out[f] = cache[p][i]
    return out


def still_offset(D, xp, x_hi=930.0):
    m = (D["t"] >= 0.5) & (D["t"] <= 2.0)
    xm = (D["x"] >= xp) & (D["x"] <= xp + x_hi)
    e = D["eta"][m][:, 2, :][:, xm] if D["eta"].shape[1] >= 3 else D["eta"][m][:, 0, :][:, xm]
    return float(np.nanmedian(e))


def zmean(D):
    nz = D["eta"].shape[1]
    zz = slice(1, nz - 1) if nz >= 3 else slice(0, nz)
    with np.errstate(all="ignore"):
        return np.nanmean(D["eta"][:, zz, :], axis=1)


def runrec(name):
    out = {}
    for p in sorted(glob.glob(os.path.join(SM, name, "run_c*.json"))):
        out[os.path.basename(p)] = json.load(open(p, encoding="utf8"))
    return out


def fieldbox_ok(fb, vox):
    """読み方 4（2026-10-12 03:19 に直した。record_ja.md の「計画から変えた所」2）：成分 1 つの場（surface・pressure・collision・massdensity・
    surfacepressure）の箱の端（x・y の bmin・bmax）が文字のまま全部同じ。成分 3 つの面の場（vel・collisionweights）は、x 成分は x の向きに、
    y 成分は y の向きに格子の半分ちょうど外へ出た値で、ほかの向きは成分 1 つの場と文字のまま同じ。"""
    scal = {}; stag = {}
    for nm, v in fb.items():
        if not v or isinstance(v, dict):
            continue
        if len(v) == 1:
            b = v[0]; scal[nm] = (b["bmin"][0], b["bmin"][1], b["bmax"][0], b["bmax"][1])
        else:
            stag[nm] = v
    vals = set(scal.values())
    ok = len(vals) == 1
    ref = list(vals)[0] if len(vals) == 1 else None
    st_ok = {}
    if ref:
        bx0, by0, bx1, by1 = (float(s) for s in ref)
        h = 0.5 * vox
        for nm, v in stag.items():
            c0, c1, c2 = v[0], v[1], v[2]
            e0 = (float(c0["bmin"][0]) == bx0 - h and float(c0["bmax"][0]) == bx1 + h and c0["bmin"][1] == ref[1] and c0["bmax"][1] == ref[3])
            e1 = (float(c1["bmin"][1]) == by0 - h and float(c1["bmax"][1]) == by1 + h and c1["bmin"][0] == ref[0] and c1["bmax"][0] == ref[2])
            e2 = (c2["bmin"][0] == ref[0] and c2["bmax"][0] == ref[2] and c2["bmin"][1] == ref[1] and c2["bmax"][1] == ref[3])
            st_ok[nm] = bool(e0 and e1 and e2)
    return dict(scalars=scal, scalars_same=bool(ok), staggered_ok=st_ok,
                staggered={nm: [[c["bmin"][:2], c["bmax"][:2]] for c in v] for nm, v in stag.items()},
                ok=bool(ok and st_ok and all(st_ok.values())))


def frames_contiguous(D, f_lo, f_hi):
    fr = list(map(int, D["frames"]))
    return bool(fr == list(range(f_lo, f_hi + 1)))


# ---------------------------------------------------------------- 試しごと
def S1():
    D = load_hf(os.path.join(SM, "S1"))
    R = load_hf(os.path.join(R42, "R1b"))
    n = 240
    a = D["eta"][:n]; b = R["eta"][:n]
    both = np.isfinite(a) & np.isfinite(b)
    one = np.isfinite(a) ^ np.isfinite(b)
    d = np.abs(a - b)[both]
    xp = PLAN["tank"]["x_p"]
    o1, o2 = still_offset(D, xp), still_offset(R, xp)
    rr = runrec("S1")["run_c0001.json"]
    w1 = float(np.median(D["wall"][1:n])); w2 = float(np.median(R["wall"][1:n]))
    res = dict(frames=[int(D["frames"][0]), int(D["frames"][n - 1])], max_abs_diff_top_m=float(d.max()), mean_abs_diff_m=float(d.mean()),
               nan_mismatch=int(one.sum()), bit_identical=bool(np.array_equal(np.nan_to_num(a, nan=-999), np.nan_to_num(b, nan=-999))),
               still_offset_S1=o1, still_offset_R1b=o2, still_offset_diff=o1 - o2,
               particles_S1=[int(v) for v in D["npts"][:n] if v >= 0][:3], particles_R1b=[int(v) for v in R["npts"][:n] if v >= 0][:3],
               s_per_frame_S1=w1, s_per_frame_R1b=w2, speed_ratio=w1 / w2, substeps=rr.get("substeps_hist"), priority=rr.get("priority"),
               frames_contiguous=frames_contiguous(D, 1, 240))
    res["pass"] = bool(res["max_abs_diff_top_m"] <= CR["S1"]["max_top_surface_diff_m"] and abs(res["still_offset_diff"]) <= CR["S1"]["still_offset_diff_m"]
                       and res["nan_mismatch"] == 0)
    return res


def pst(rr, f):
    for r in rr.values():
        p = r.get("info", {}).get("pstats", {}).get(str(f))
        if p:
            return p
    return None


def fb_of(rr, f=2):
    for r in rr.values():
        p = r.get("info", {}).get("fieldbox", {}).get(str(f))
        if p:
            return p
    return None


def S2f():
    rr = runrec("S2f")
    D = load_hf(os.path.join(SM, "S2f"))
    r0 = list(rr.values())[0]
    lv = zmean(D)
    p2, p120 = pst(rr, 2), pst(rr, 120)
    Lx = r0["parms"]["Lx"]
    xm = (D["x"] > 0.2 * Lx) & (D["x"] < 0.6 * Lx)
    lev = np.array([np.nanmean(e[:, xm]) for e in D["eta"]])
    i2 = list(D["frames"]).index(2)
    res = dict(vy_mean_f2=p2["vy_mean_mid"], speed_max_f120=p120["speed_max"], speed_max_f120_at=p120["speed_max_at"],
               level_change_max_m=float(np.max(np.abs(lev[i2:] - lev[i2]))), level_series=[float(lev[0]), float(lev[i2]), float(lev[-1])],
               particles=p2["n"], s_per_frame=r0["wall_per_frame_median_s"], substeps=r0["substeps_hist"], stopped=r0["stopped"],
               fieldbox=fieldbox_ok(fb_of(rr), 2 * 0.34375))
    res["pass"] = bool(abs(res["vy_mean_f2"]) <= CR["S2"]["frame2_mean_vy_abs_max_m_s"] and r0["stopped"] is None)
    return res


def S2(base_speed):
    rr = runrec("S2")
    D = load_hf(os.path.join(SM, "S2"))
    lv = np.array([r for r in D["eta"].mean(axis=1)[:, :]]) if False else None
    lvls = []
    for r in rr.values():
        pass
    # 水面の平均（0.2〜0.6 Lx、z の節の平均）：g44_run の見張りと同じ量を hf から出し直す
    Lx = list(rr.values())[0]["parms"]["Lx"]
    xm = (D["x"] > 0.2 * Lx) & (D["x"] < 0.6 * Lx)
    lev = np.array([np.nanmean(e[:, xm]) for e in D["eta"]])
    p2, p120 = pst(rr, 2), pst(rr, 120)
    bc = None
    for r in rr.values():
        if r.get("info", {}).get("bedcheck"):
            bc = r["info"]["bedcheck"]
    r1, r2 = rr.get("run_c0001.json"), rr.get("run_c0061.json")
    # 読み方 3 を 03:19 に直した：1 コマ目は初めの水面の網（y = 0 ちょうど）で、2 コマ目からは粒子から作る水面（静かな水面のずれ N1 を含む）。
    # 動きは 2 コマ目からの最大で見る（record_ja.md の「計画から変えた所」2）。1 コマ目からの値も記録する
    i2 = list(D["frames"]).index(2)
    res = dict(vy_mean_f2=p2["vy_mean_mid"], level_change_max_m=float(np.max(np.abs(lev[i2:] - lev[i2]))), level_change_from_f1_m=float(np.max(np.abs(lev - lev[0]))),
               level_series=[float(lev[0]), float(lev[i2]), float(lev[-1])],
               speed_max_f120=p120["speed_max"], speed_max_f120_at=p120["speed_max_at"], speed_limit=base_speed + CR["S2"]["speed_max_over_flat_baseline_plus_m_s"],
               fieldbox=fieldbox_ok(fb_of(rr), 2 * 0.34375), bedcheck=bc, bed_all_ok=bool(bc and all(b.get("ok") for b in bc)),
               frames_contiguous=frames_contiguous(D, 1, 120), launches=[(k, v["f_start"], v["f_end_done"], v["stopped"]) for k, v in rr.items()],
               priority=[v.get("priority") for v in rr.values()], particles=p2["n"], particles_plan_million=PLAN["runs"]["PR1"]["N_million"],
               s_per_frame=[v["wall_per_frame_median_s"] for v in rr.values()], substeps=[v["substeps_hist"] for v in rr.values()],
               ckpt_gb=[v["ckpt_gb"] for v in rr.values()], rss_peak_gb=[v["rss_peak_gb"] for v in rr.values()])
    res["pass"] = bool(abs(res["vy_mean_f2"]) <= CR["S2"]["frame2_mean_vy_abs_max_m_s"] and res["level_change_max_m"] <= CR["S2"]["mean_level_change_m"]
                       and res["speed_max_f120"] <= res["speed_limit"] and res["fieldbox"]["ok"] and res["bed_all_ok"] and res["frames_contiguous"]
                       and all(v["stopped"] is None for v in rr.values()) and all((v.get("priority") or {}).get("below_normal") for v in rr.values()))
    return res


def S2b():
    rr = runrec("S2b"); r0 = list(rr.values())[0]
    p2, p24 = pst(rr, 2), pst(rr, 24)
    res = dict(vy_mean_f2=p2["vy_mean_mid"], vy_mean_f24=p24["vy_mean_mid"], level_min=r0["level_min_m"], level_start=r0["level_start_m"],
               stopped=r0["stopped"], fieldbox=fieldbox_ok(fb_of(rr), 0.5), particles=p2["n"], particles_plan_million=PLAN["runs"]["SH"]["N_million"],
               s_per_frame=r0["wall_per_frame_median_s"], substeps=r0["substeps_hist"], rss_peak_gb=r0["rss_peak_gb"], wall_launch_s=r0["wall_launch_s"])
    res["pass"] = bool(r0["stopped"] is None and res["fieldbox"]["ok"] and (r0["level_start_m"] - r0["level_min_m"]) < PLAN["criteria"]["level_guard_m"])
    return res


def S4(v=""):
    ni, nii = "S4i" + v, "S4ii" + v
    a = load_hf(os.path.join(SM, ni)); b = load_hf(os.path.join(SM, nii)); s1 = load_hf(os.path.join(SM, "S1"))
    sa = load_sec(os.path.join(SM, ni)); sb = load_sec(os.path.join(SM, nii)); s1s = load_sec(os.path.join(SM, "S1"))
    ri = list(runrec(ni).values())[0]; rii = list(runrec(nii).values())[0]
    same_hf = bool(np.array_equal(np.nan_to_num(a["eta"], nan=-999), np.nan_to_num(b["eta"], nan=-999)))
    same_sec = bool(sorted(sa) == sorted(sb) and all(np.array_equal(sa[f], sb[f]) for f in sa))
    same_n = bool(np.array_equal(a["npts"], b["npts"])); same_ss = bool(np.array_equal(a["ss_n"], b["ss_n"]))
    d_ab = float(np.nanmax(np.abs(a["eta"] - b["eta"])))
    # (i) と S1 の 121〜168 コマ（S1 は 240 コマまで走った）
    i1 = [list(s1["frames"]).index(f) for f in a["frames"] if f in list(s1["frames"])]
    same_s1 = bool(np.array_equal(np.nan_to_num(a["eta"], nan=-999), np.nan_to_num(s1["eta"][i1], nan=-999))) if len(i1) == len(a["frames"]) else None
    same_s1_sec = bool(all(np.array_equal(sa[f], s1s[f]) for f in sa if f in s1s))
    res = dict(frames=[int(a["frames"][0]), int(a["frames"][-1])], i_stopped=ri["stopped"], ii_stopped=rii["stopped"], ii_runs=rii["f_end_done"] == 168,
               bit_identical_hf=same_hf, bit_identical_sec=same_sec, same_particle_counts=same_n, same_substeps=same_ss, max_abs_diff_top_m=d_ab,
               ii_wind_calls_eq_substeps=rii.get("wind_calls_equal_substeps"), ii_solver_parms=rii.get("solver_parms"),
               i_vs_S1_bit_identical_hf=same_s1, i_vs_S1_bit_identical_sec=same_s1_sec)
    res["B0_needed"] = not (same_hf and same_sec and same_n and same_ss)
    res["pass"] = bool(res["ii_runs"] and rii["stopped"] is None)       # 判定は「(ii) が走りきること」。B0 を走らせるかは B0_needed
    return res


def S4b(v=""):
    rr = runrec("S4b" + v); r0 = list(rr.values())[0]
    D = load_hf(os.path.join(SM, "S4b" + v))
    off = float(np.nanmedian(D["eta"][(D["t"] >= 0.5) & (D["t"] <= 2.0)][:, 2, :]))
    EX = zmean(D) - off
    om = None
    g = 9.80665; h = 42.0; lam = 40.0; k = 2 * np.pi / lam
    T = 2 * np.pi / np.sqrt(g * k * np.tanh(k * h))
    m = (D["t"] >= 10.0) & (D["t"] <= 10.0 + 2 * T)
    eb = np.nanmean(EX[m], axis=0)
    x = D["x"]; L = float(x[-1] - x[0])
    c = 2.0 / L * np.trapezoid(eb * np.cos(2 * np.pi * x / lam), x)
    ratio = c / (-2000.0 / (1000.0 * g))
    fb = fieldbox_ok(fb_of(rr), 1.0)
    rc = list(runrec("S4bc" + v).values())[0] if runrec("S4bc" + v) else None
    Dc = load_hf(os.path.join(SM, "S4bc" + v)) if rc else None
    calls = dict(S4b=dict(equal=r0.get("wind_calls_equal_substeps"), substeps=r0.get("substeps_hist"),
                          pairs=sorted(set((int(s), int(w)) for s, w in zip(D["ss_n"], D["wind_calls"]) if w >= 0))))
    if rc:
        calls["S4bc"] = dict(equal=rc.get("wind_calls_equal_substeps"), substeps=rc.get("substeps_hist"),
                             pairs=sorted(set((int(s), int(w)) for s, w in zip(Dc["ss_n"], Dc["wind_calls"]) if w >= 0)))
    has_sp = "surfacepressure" in fb["scalars"]
    res = dict(natural_period_s=T, window_s=[10.0, 10.0 + 2 * T], still_offset=off, cos_component_m=c, expected_m=-2000.0 / (1000.0 * g),
               ratio=ratio, fieldbox=fb, surfacepressure_box_present=has_sp, calls=calls, stopped=r0["stopped"], s_per_frame=r0["wall_per_frame_median_s"])
    calls_ok = bool(calls["S4b"]["equal"] and (rc is None or (calls["S4bc"]["equal"] and min(p[0] for p in calls["S4bc"]["pairs"]) >= 3)))
    res["pass"] = bool(0.9 <= ratio <= 1.1 and fb["ok"] and has_sp and calls_ok and r0["stopped"] is None)
    return res


def S8():
    rr = runrec("S8")
    r0 = rr["run_c0001.json"]; rlast = rr[sorted(rr)[-1]]
    D = load_hf(os.path.join(SM, "S8"))
    xp = PLAN["tank"]["x_p"]
    off = still_offset(D, xp, 400.0)
    EX = zmean(D) - off
    x = D["x"]
    i200 = int(np.argmin(np.abs(x - (xp + 200.0))))
    ser = EX[:, i200]
    # 頂：上へ 0 を切ってから下へ切るまでの最大（静かな水面から）
    crests = []
    up = None
    for j in range(1, len(ser)):
        if ser[j - 1] <= 0 < ser[j]:
            up = j
        elif up is not None and ser[j - 1] > 0 >= ser[j]:
            crests.append(float(np.nanmax(ser[up:j]))); up = None
    reef = (x >= xp + 170.0) & (x <= xp + 230.0)
    allfin = bool(np.isfinite(D["eta"][:, :, reef]).all())
    depth_min = float(np.nanmin(D["eta"][:, :, reef] + 12.0))
    fb = fieldbox_ok(fb_of(rr), 1.0)
    big = [c for c in crests if c >= 0.5]
    f_last = int(D["frames"][-1])
    res = dict(frames_done=rlast["f_end_done"], launches=[(k, v["f_start"], v["f_end_done"], v["stopped"]) for k, v in sorted(rr.items())],
               stopped=[v["stopped"] for v in rr.values()], frames_contiguous=frames_contiguous(D, 1, f_last), still_offset=off,
               crests_at_200m=crests, n_crests_ge_0p5=len(big), reef_top_all_finite=allfin, min_depth_over_reef_top_m=depth_min,
               fieldbox=fb, substeps=r0["substeps_hist"], s_per_frame=r0["wall_per_frame_median_s"], particles_max=r0["particles_max"],
               max_eta_over_reef=float(np.nanmax(EX[:, reef])), wall_total_s=r0["wall_total_s"])
    res["pass"] = bool(all(v["stopped"] is None for v in rr.values()) and res["frames_contiguous"] and len(big) >= 2 and allfin and depth_min > 2.0 and fb["ok"])
    return res


def S9(v=""):
    """記録の「計画から変えた所」3 の判定。"""
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip44")
    import g44_analyze as A, g44_wind_check as WC
    rd = os.path.join(SM, "S9" + v)
    cfg = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
    r0 = list(runrec("S9" + v).values())[0]
    D8 = load_hf(os.path.join(SM, "S8"))
    xp = PLAN["tank"]["x_p"]
    off = still_offset(D8, xp, 400.0)
    SR = A.SecReader(rd)
    cbf = {}
    for f in SR.frames:
        cr, _ = A.frame_crests(SR.get(f), SR.meta, off, 1.0, PLAN["tank"]["Lc"], cfg["parms"])
        if cr:
            c = max(cr, key=lambda r: r["eta"])
            cbf[f] = (c["xc"], c["eta"])
    # 計画から変えた所 5：S9 の波はなだらか（|n_x| < 0.2）なので、点は造波板から 10〜390 m の全部の露出した水面から、|n_x| ≥ 0.02 で選ぶ
    w = WC.w6(rd, cfg, off, cbf, nx_min=0.02, xwin_rel=(10.0, 390.0))
    q = cfg["parms"]["wind_q"]
    pmax = max((r["p_max_abs"] for r in w["rows"]), default=None)
    D9 = load_hf(rd)
    w9 = float(np.median(D9["wall"][1:]))
    i8 = [list(D8["frames"]).index(f) for f in D9["frames"] if f in list(D8["frames"])]
    w8 = float(np.median(D8["wall"][i8][1:]))
    res = dict(frames_done=r0["f_end_done"], stopped=r0["stopped"], wind_calls_equal_substeps=r0.get("wind_calls_equal_substeps"),
               substeps=r0.get("substeps_hist"), W6_pass=w["pass_"], W6_frames=w["frames"], W6_bad=w["frames_bad"][:20],
               W6_max_rel_err=max((r["max_rel_err"] or 0) for r in w["rows"]) if w["rows"] else None,
               W6_min_exposed=min((r["n_exposed"] for r in w["rows"]), default=None), W6_covered_total=sum(r["n_covered"] for r in w["rows"]),
               thin_cols_total=sum(r["thin_cols"] for r in w["rows"]), p_max_abs=pmax, q=q, s_per_frame=w9, s_per_frame_S8_same_frames=w8,
               cost_ratio=w9 / w8, touchdown_online=r0.get("info", {}).get("touchdown_online"), crest_frames=len(cbf))
    res["pass"] = bool(r0["f_end_done"] == 624 and r0["stopped"] is None and r0.get("wind_calls_equal_substeps") and w["pass_"]
                       and pmax is not None and pmax <= q * (1 + 1e-6))
    json.dump(w, open(os.path.join(rd, "w6.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return res


def cost():
    """record_ja.md の計画の読み方 12 と計画から変えた所 4・7：煙の試しで本番の時間の見込みを直す（記録）。"""
    import datetime as dt
    R = {}
    for r, n in (("R1b", 240), ("R2", 120), ("R3", 120)):
        d = np.load(os.path.join(R42, r, "hf_c0001.npz"))
        R[r] = dict(med=float(np.median(d["wall"][1:n])), n24=int(d["npts"][list(d["frames"]).index(24)]))
    R["R2"]["max"] = 5753252; R["R3"]["max"] = 11269961        # FLIP42 の ana.json（計画の flip42_records）の粒子の最大
    s1 = load_hf(os.path.join(SM, "S1")); s1b = load_hf(os.path.join(SM, "S1b"))
    m_s1 = float(np.median(s1["wall"][1:240])); m_s1b = float(np.median(s1b["wall"][1:120]))
    c = {}
    for f in glob.glob(os.path.join(SM, "S1c", "cost_*_*.json")):
        d = json.load(open(f, encoding="utf8")); c[os.path.basename(f)] = d["median_2_n"]
    ab = sorted(c.items())
    v44 = [v for k, v in ab if k.startswith("cost_44")]; v42 = [v for k, v in ab if k.startswith("cost_42")]
    scene = (min(v44) / v42[0]) if v44 and v42 else None
    load_now = [m_s1b / R["R3"]["med"]] + [v / float(np.median(np.load(os.path.join(R42, "R3", "hf_c0001.npz"))["wall"][1:36])) for v in v42 + v44]
    rr2 = runrec("S2"); rr2b = runrec("S2b")
    n2 = rr2["run_c0061.json"]["info"]["pstats"]["120"]["n"]; n2b = list(rr2b.values())[0]["info"]["pstats"]["24"]["n"]
    nmax_034 = n2 / (R["R2"]["n24"] / R["R2"]["max"]); nmax_025 = n2b / (R["R3"]["n24"] / R["R3"]["max"])
    runs = PLAN["runs"]
    order = [k for k in PLAN["order"] if k != "B0"]
    tot = {q: sum(runs[k]["hours"][q] for k in order) for q in ("lo", "rec", "hi")}
    lo_f, hi_f = min(load_now), max(load_now)
    gaps = PLAN["totals"]["human_gaps_h"]
    start = dt.datetime(2026, 10, 13, 19, 0)
    end_lo = start + dt.timedelta(hours=tot["hi"] * lo_f + gaps); end_hi = start + dt.timedelta(hours=tot["hi"] * hi_f + gaps)
    return dict(s1_over_R1b=m_s1 / R["R1b"]["med"], s1b_over_R3=m_s1b / R["R3"]["med"], S1c=dict(ab), scene_factor_44_over_42=scene,
                load_factor_now_range=[lo_f, hi_f], particles=dict(S2_f120=n2, S2b_f24=n2b, projected_max_034375=nmax_034, projected_max_025=nmax_025,
                                                                   plan_034375=runs["PR1"]["N_million"] * 1e6, plan_025=runs["SH"]["N_million"] * 1e6),
                ckpt_GB=dict(S2_each=rr2["run_c0061.json"]["ckpt_gb"] / 2, note_ja="S2 の 60・120 コマの途中保存 2 個の和の半分"),
                plan_hours_without_B0=tot, hours_hi_with_load=[tot["hi"] * lo_f, tot["hi"] * hi_f],
                end_if_start_1013_1900=[end_lo.strftime("%m/%d %H:%M"), end_hi.strftime("%m/%d %H:%M")])


def jres(name, fn):
    p = os.path.join(SM, name, fn)
    if not os.path.exists(p):
        return None
    d = json.load(open(p, encoding="utf8"))
    return {k: v for k, v in d.items() if k not in ("rows", "programs", "exposed_20", "runs")} | ({"programs": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in d["programs"].items()}} if "programs" in d else {})


if __name__ == "__main__":
    outp = os.path.join(SM, "smoke_results.json")
    res = json.load(open(outp, encoding="utf8")) if os.path.exists(outp) else {}
    want = sys.argv[1:] or ["S1", "S2f", "S2", "S2b", "S3", "S4", "S4b", "S5", "S7", "S8"]
    for w in want:
        v = ""
        if "@" in w:
            w, v = w.split("@"); v = "_" + v
        try:
            if w == "S1":
                res["S1"] = S1()
            elif w == "S2f":
                res["S2f"] = S2f()
            elif w == "S2":
                base = res.get("S2f", {}).get("speed_max_f120")
                if base is None:
                    base = S2f()["speed_max_f120"]
                res["S2"] = S2(base)
            elif w == "S2b":
                res["S2b"] = S2b()
            elif w == "S3":
                res["S3"] = jres("S3", "s3.json")
            elif w == "S4":
                res["S4" + v] = S4(v)
            elif w == "S4b":
                res["S4b" + v] = S4b(v)
            elif w == "S5":
                res["S5"] = jres("S5", "s5.json")
            elif w == "S7":
                res["S7"] = jres("S7", "s7.json")
            elif w == "S8":
                res["S8"] = S8()
            elif w == "S9":
                res["S9" + v] = S9(v)
            elif w == "cost":
                res["cost"] = cost(); res["cost"]["pass"] = True
        except Exception as e:
            import traceback
            res[w + v] = {"error": repr(e)[:300], "trace": traceback.format_exc()[-800:]}
    json.dump(res, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    for k in want:
        k = k.replace("@", "_")
        v = res.get(k) or {}
        print(k, "PASS" if v.get("pass") else ("FAIL" if "pass" in v else "?"), json.dumps({kk: vv for kk, vv in v.items() if kk not in ("fieldbox", "trace", "bedcheck", "priority", "ii_solver_parms", "calls", "covered_nonzero")}, ensure_ascii=False, default=float)[:900])
