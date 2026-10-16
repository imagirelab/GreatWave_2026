# -*- coding: utf-8 -*-
"""FLIP50 (option D): read a FLIP50 calculation (py -3.10 -B; numpy, scipy, scikit-image, PIL). 2026-10-15 written new (Claude).
It runs g49_periodic_ana (flip49, read only, the tool that reads DA1) with in-memory adaptations only (no file is edited):
  - g50_common.redirect_gc49(): outputs inside Unity/Build/FLIP50 (guard_out49, A46.B46), g49_common.LAYOUTS['D'].
  - is_A(cfg) also for layout 'D' (plan from cfg case.plan_frozen = plan_D_frozen.json; crest window centre_half_L with cfg sf.L; side band,
    P1 limit, quiet window, report levels from the cfg).
  - Ctx: the g46 far row y_far = cfg analysis.yfar_m (90 m, inside the r4 lateral extent 0-95 m; the default W - 1 = 139 m lies in the side band).
  - periodic_A(): the D plan's criteria.periodic_D is passed as periodic_A (same PERIODIC rule, copied from plan A); the A next-step text is
    replaced by the frozen D rules (decision_rules.after_DM1 / after_DF1); 'reef_top_setup' is the swash set-up (setup_region 'swash').
  - PERIODIC_ja.md wording says option D.
Added (report only, never used to judge): pana/report_D.json + REPORT_D_ja.md
  - generation: first-harmonic H and zero-down H at each gauge (x 110/128/160 m x y 0.5/20/40/60/80 m) over the last 3 periods against the
    linear target 2|A| of the table (cfg dir.gauges_lin); the health rule 0.80-1.20 at x 160 m, |y| <= 40 m.
  - focus gain c0/c_in with the D definition (c_in = lateral mean over |y| <= 95 m of the per-row incident crest at x 128 m in [t_on - T, t_on]).
  - rip cell: period-mean mass transport (depth-integrated grid u over the water / still depth) on r2 (y 0) and r3 (y 77 m) at x 200/230/260/300 m.
  - health D: onsets on the flat (x < 160.25 m) or at h_b > 14 m; swash set-up > 3 m (from periodic_A); generation band failure.
  - onset x / Hc against the registered screen predictions (plan registered_screen_predictions).
  - S2D strips: chord / lip / hood per breaker and the S2D rule.
2026-10-16 freeze step (campaign B findings, plan_D_frozen.json; Claude):
  - the D verdict (pass / partial / fail) and the single next change are decided HERE (plan_d_numbers / decide_D) from the frozen
    decision_rules.after_DM1, because they need the campaign-B shape numbers; periodic_ana's own verdict text is kept only as the P1-P5 narrative.
  - per breaker, the campaign-B numbers read with the campaign-B code itself (flip49 g49_planB_ana.measure, read only): onset t/x, h_b, Hc,
    crest-to-front-trough H_front, crest-to-rear-trough H_rear, back 0.7-0.9 eta_c at incoming/pre-onset max/onset/best, width07 onset/best,
    lip, chord, hood, score3; plus q = H_rear/Hmax(h, T) along the crest track (toe, h 15/13 m, first depth with q >= 0.9/1.0, pre-onset max),
    the periodic/narrow numbers (c0/c_side, c0/c(4Hc), curl width/Hc at onset/max overturn/touchdown, onset x scatter, Hc CV), and the focusing
    gain (Hc, H_front, H_rear over the component amplitude a_j and over the linear focal design |A(x_on, 0)|, |A(x_f, 0)|; c0/c_in).
    -> pana/planD_ana.json, planD_table.txt, a section in REPORT_D_ja.md.
  - health D: hard failures (diagnose first) and the soft volume band 1-2 % (RV-D2), end-wall contact (RV-D1, report only).
  - smoke: the frozen smoke gates (plan smoke_gates) and a smoke mp4 (top view + axis section, red frame at the focus instants t = nT).
2026-10-17 (AM-D18, drift stage A runs DM1A / DF1A / SMOKE50DA): the volume item of a stage-A run is read as FLIP49 stage A (PA.health:
  max |V/V0 - 1| of the measured whole-tank column volume after 1.5 s) with the same frozen thresholds; health_50 adds report-only whole-tank,
  window (x 110-400 m) and raw period means. Stage C reading and wording unchanged.
usage:
  py -3.10 -B g50_ana.py all <run>        periodic_ana all (events, per-breaker P1-P5, PERIODIC, best_frames.json) + the D report + the D verdict
  py -3.10 -B g50_ana.py report <run>     the D report and the D verdict only (after all)
      --prev=<previous D run dir>         (round >= 2) also the Q73 test against the previous D round (its pana/planD_ana.json)
  py -3.10 -B g50_ana.py smoke <run>      SMOKE_D gates (never judged) -> pana/smoke_D.json, video/<run_id>_smoke.mp4
  py -3.10 -B g50_ana.py s2d <run>        S2D strip: periodic_ana all + chord/lip/hood per breaker and the S2D rule
"""
import os, sys, json, math, glob, time, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49", HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                 # noqa: E402
import g50_common as GC50          # noqa: E402
GC50.redirect_gc49()               # before g49_periodic_ana is imported (A46.B46 = GC.B49 at its import)
import g49_periodic_ana as PA      # noqa: E402
import g50_table as TB             # noqa: E402

A46 = PA.A46
A48 = PA.A48
PM = PA.PM
_ORIG_IS_A = PA.is_A
_ORIG_PERIODIC_A = PA.periodic_A
_ORIG_MD = PA.md


def is_D(cfg):
    return (cfg or {}).get("layout") == "D"


PA.is_A = lambda cfg: bool(_ORIG_IS_A(cfg) or is_D(cfg))
_ORIG_HEALTH = PA.health


def health_50(rd, cfg, R, off, recs):
    """2026-10-17 (AM-D18): PA.health (flip49, read only; replaced in memory like is_A) plus, for drift stage A only, report-only period means
    from the ramp end per period T: whole-tank V/V0 - 1 and window Vwin/Vwin0 - 1 (x vol_x0..vol_x1 = 110-400 m; V0, Vwin0 = means over
    1.0-1.5 s). The judged number stays PA.health's stage-A reading, as FLIP49 stage A: corrected_max_rel = max |V/V0 - 1| of the measured
    (corrected) whole-tank column volume after 1.5 s. Stage C output is unchanged."""
    out = _ORIG_HEALTH(rd, cfg, R, off, recs)
    vol = out.get("volume")
    if (cfg.get("drift") or {}).get("stage") == "A" and vol:
        P = cfg.get("parms") or {}
        vi = {nm: i for i, nm in enumerate(R["vnames"])}
        t = R["t"]
        ref = (t >= 1.0 - 1e-9) & (t <= 1.5 + 1e-9)
        T_ = float((cfg.get("sf") or {}).get("T", 12.0))
        t0_ = float(P.get("ramp_s", 24.0))
        n_ = int((t[-1] - t0_ + 1e-9) // T_)
        V = R["vol"][:, vi["V_m3"]]; Vw = R["vol"][:, vi["Vwin_m3"]]; cum = R["vol"][:, vi["cum_added_m3"]]
        V0 = float(np.nanmean(V[ref])); Vw0 = float(np.nanmean(Vw[ref]))
        vol["stage_A_whole_period_mean_rel"] = PA.period_means(t, V / V0 - 1.0, t0_, T_, n_)
        vol["stage_A_window_period_mean_rel"] = PA.period_means(t, Vw / Vw0 - 1.0, t0_, T_, n_)
        vol["stage_A_raw_whole_period_mean_rel"] = PA.period_means(t, (V - cum) / V0 - 1.0, t0_, T_, n_)
        vol["stage_A_window_m"] = [float(P.get("vol_x0", GC50.VOL_X[0])), float(P.get("vol_x1", GC50.VOL_X[1]))]
        vol["stage_A_periods_from_s"] = t0_
        vol["stage_A_reading"] = ("judged (AM-D18, as FLIP49 stage A): corrected_max_rel = max |V/V0 - 1| of the measured whole-tank column volume "
                                  "after 1.5 s; report only: whole-tank, window and raw (V - added) period means from the ramp end")
    return out


PA.health = health_50


class Ctx50(PA.Ctx49):
    """Ctx49 with the g46 far row inside the r4 extent (cfg analysis.yfar_m)."""

    def __init__(self, rd, opt=None):
        opt = dict(opt or {})
        cfg = PA.load_cfg(rd)
        yf = (cfg.get("analysis") or {}).get("yfar_m")
        if yf is not None:
            opt.setdefault("yfar", str(float(yf)))
        super().__init__(rd, opt)


PA.Ctx49 = Ctx50
A46.Ctx = Ctx50
A48.Ctx48 = Ctx50


def next_D(rows, out, hl, cfg, rep=None):
    """2026-10-16 freeze step: the D verdict and the next step need the campaign-B shape numbers, so they are decided after periodic_ana by
    plan_d_numbers() / decide_D() (pana/planD_ana.json) from plan_D_frozen.json decision_rules.after_DM1. This only points there."""
    return ["decided by g50_ana.py after the campaign-B numbers: pana/planD_ana.json (plan_D_frozen.json decision_rules.after_DM1)"]


def next_D_draft_rules(rows, out, hl, cfg, rep=None):
    """the 2026-10-15 DRAFT rules (superseded at the freeze step; kept for the record, never called)."""
    nxt = []
    J = lambda r: r.get("judge") or {}
    health = []
    if (out.get("reef_top_setup") or {}).get("diagnose"):
        health.append("swash set-up > 3 m")
    if (hl.get("judge") or {}).get("H_volume") is False:
        health.append("volume")
    if (hl.get("judge") or {}).get("H_bed_leak") is False:
        health.append("leak")
    if rep:
        if rep.get("health_D", {}).get("onset_on_flat_or_deep"):
            health.append("onset on the flat (x < 160.25 m) or at h_b > 14 m")
        if rep.get("generation", {}).get("band_failure"):
            health.append("generation at x 160 m, |y| <= 40 m outside 0.80-1.20 of the linear target")
    if health:
        nxt.append("health failure (%s) -> diagnose first" % ", ".join(health))
    case = (cfg.get("dir") or {}).get("case") or (cfg.get("case") or {}).get("dir_case")
    p5 = [r for r in rows if J(r).get("P5")]
    wfail = [r for r in rows if not (J(r).get("P2") and J(r).get("P3"))]
    chord_bad = [r for r in rows if r.get("chord_max") is not None and r["chord_max"] < 55.0]
    p4b = [r for r in rows if r.get("ratio_4Hc") is not None]
    full = any(w["all_P1_P5"] for w in out.get("windows", []) if w.get("periodic"))
    if case == "DF1":
        nxt.append("after_DF1: compare with DM1 - narrower curl widths with P5 kept -> keep DF1 and re-evaluate; P5 lost -> DM1 stays the D result (negative recorded)")
    if out.get("PERIODIC") and full:
        nxt.append("PERIODIC + P1-P5 on >= 3 consecutive -> 'full'; DD3 continuation (+48 s) and a seamless 12 s loop")
    elif len(p5) >= 2 and len(wfail) >= 2 and case != "DF1":
        nxt.append("P5 passes on >= 2 judged breakers but P2 or P3 fails on >= 2 -> DF1 (T 10 s, one change)")
    elif len(chord_bad) >= 2:
        nxt.append("P5 fails with chord < 55 deg on >= 2 judged breakers -> stop and show the user")
    elif p4b and all(r["ratio_4Hc"] < 1.3 for r in p4b):
        nxt.append("P4b < 1.3 on all judged breakers -> D negative (no narrowing); stop and show")
    elif out.get("PERIODIC"):
        nxt.append("PERIODIC passes; P1-P4 on >= 3 -> 'periodic narrow peak', else partial: stop and show the user")
    else:
        nxt.append("otherwise 'partial', breaker by breaker; stop and show the user")
    return nxt


def periodic_AD(rows, plan, R, off, T, per, hl, cfg):
    if not is_D(cfg):
        return _ORIG_PERIODIC_A(rows, plan, R, off, T, per, hl, cfg)
    plan2 = copy.deepcopy(plan)
    crit = plan2["criteria"]
    if "periodic_A" not in crit:
        crit["periodic_A"] = crit["periodic_D"]
    out = _ORIG_PERIODIC_A(rows, plan2, R, off, T, per, hl, cfg)
    out["rule_source"] = "plan_D_frozen.json criteria.periodic_D (= plan A PERIODIC, unchanged)"
    out["swash_setup"] = out.get("reef_top_setup")
    out["report_c0_over_c_in"]["note"] += " | plan A definition kept for comparison; the D definition (lateral mean at x 128 m) is in report_D.json"
    nxt = next_D(rows, out, hl, cfg)
    out["next_by_frozen_rules"] = nxt
    if out.get("judged", True):
        good = [w for w in out.get("windows", []) if w["periodic"]]
        full = [w for w in good if w["all_P1_P5"]]
        pnp = [w for w in good if w["all_P1_P4"]]
        if full:
            out["verdict"] = "full: breakers k = %s meet P1-P5 and PERIODIC (AI self-assessment; the user judges print-likeness; never 'steady state')" % full[0]["k"]
        elif pnp:
            out["verdict"] = "periodic narrow peak: PERIODIC and P1-P4 on k = %s (never 'steady state')" % max(pnp, key=lambda w: len(w["k"]))["k"]
        elif good:
            out["verdict"] = "PERIODIC passes (k = %s) but not P1-P4 on all of them: partial (see the per-breaker table)" % out["PERIODIC_k"]
        else:
            out["verdict"] = "partial: PERIODIC fails (see the per-breaker table). Next by the frozen D rules: %s" % "; ".join(nxt)
        # 2026-10-16 freeze step: this is the P1-P5 narrative of periodic_ana; the D verdict (pass / partial / fail) is in planD_ana.json
        out["verdict"] = "P1-P5 narrative (the D verdict pass/partial/fail is in pana/planD_ana.json): " + out["verdict"]
    return out


PA.periodic_A = periodic_AD


def md_D(o, cfg):
    s = _ORIG_MD(o, cfg)
    if not is_D(cfg):
        return s
    for a, b in (("# FLIP49 周期の波の読み", "# FLIP50 方案 D（方向のある周期の波、まっすぐな 1:10 の浜）の読み"),
                 ("## 方案 A の判定（PERIODIC、plan_A_frozen.json）", "## 方案 D の判定（PERIODIC、plan_D_frozen.json。決まりは方案 A と同じ）"),
                 ("礁の上の盛り上がり（1 周期の平均、> 3 m で診断）", "打ち上げ（x 330〜360 m）の盛り上がり（1 周期の平均、> 3 m で診断）"),
                 ("方案 A では報告だけ", "方案 D では報告だけ"), ("：報告だけ（方案 A）", "：報告だけ（方案 D）"),
                 ("x < 180 m で崩れた", "x < 180 m で崩れた（方案 D の平らは x < 160.25 m）")):
        s = s.replace(a, b)
    return s + "\n方案 D の報告だけの量（生成・c0/c_in・離岸流・予測との比べ）：pana/REPORT_D_ja.md・report_D.json。\n"


PA.md = md_D


# ====================================================================== D report-only items
def load_sec(rd, kind):
    """r2 (centre) or r3 (y = r3_z) sections: dict frame -> (t, sdf[ny, nx], u[ny_u, nx_u]) and the metas (later launches win)."""
    out = {}
    meta = None
    for p in sorted(glob.glob(os.path.join(rd, "%s_c*_b*.npz" % kind))):
        d = np.load(p)
        meta = json.loads(str(d["meta"]))
        for i, f in enumerate(d["frames"]):
            out[int(f)] = (float(d["t"][i]), d["sdf"][i].astype(np.float32), d["u"][i].astype(np.float32))
    return out, meta


def mass_transport(rd, cfg, kind, xs_q, T, t_from):
    """period-mean depth-integrated x flux Q (m^2/s) over the water of the section and Q/h (m/s, h = still depth), per period [measured]."""
    sec, meta = load_sec(rd, kind)
    if not sec or not meta or "vel.x" not in (meta.get("vel") or {}):
        return dict(error="no %s records with vel.x" % kind)
    vm = meta["vel"]["vel.x"]
    spec = GC50.bed_spec(cfg)
    ysec = float(meta.get("z", 0.0))
    fr = sorted(f for f in sec if sec[f][0] >= t_from - 1e-9)
    tt = np.array([sec[f][0] for f in fr])
    res = {}
    for xq in xs_q:
        ix = int(round((xq - meta["x0"]) / meta["dx"])); iu = int(round((xq - vm["p0"][0]) / vm["d"][0]))
        Q = []
        for f in fr:
            _, S, U = sec[f]
            yu = vm["p0"][1] + vm["d"][1] * np.arange(U.shape[0])
            js = np.clip(np.round((yu - meta["y0"]) / meta["dy"]).astype(int), 0, S.shape[0] - 1)
            wet = S[js, min(max(ix, 0), S.shape[1] - 1)] < 0.0
            col = U[:, min(max(iu, 0), U.shape[1] - 1)]
            Q.append(float(np.nansum(np.where(wet, col, 0.0)) * vm["d"][1]))
        Q = np.array(Q)
        h = float(-GC50.bed_z(xq, ysec, **spec))
        n = int((tt[-1] - t_from) // T) if len(tt) else 0
        pm = [float(np.mean(Q[(tt >= t_from + i * T) & (tt < t_from + (i + 1) * T)])) for i in range(n)]
        res["x%g" % xq] = dict(h_m=h, Q_period_mean_m2s=pm, U_mt_period_mean_mps=[q / h if h > 0.1 else None for q in pm])
    return dict(section=kind, y_m=ysec, t_from=t_from, T=T, stations=res,
                note="Eulerian grid u integrated over the wet cells of the section (sdf < 0), period means from t_from; + onshore, - offshore")


def generation(rd, cfg, T, off):
    R = PA.load_r6(rd)
    t = R["t"]; gl = (cfg.get("dir") or {}).get("gauges_lin") or {}
    om = 2 * math.pi / T
    t1 = float(t[-1]); t0 = t1 - 3 * T
    sel = (t >= t0 - 1e-9) & (t <= t1 + 1e-9)
    rows = {}
    for j, (xg, yg) in enumerate(R["gxy"]):
        e = R["gauge"][sel, j] - off; tt = t[sel]
        ok = np.isfinite(e)
        if ok.sum() < 10:
            continue
        a1 = abs(2.0 * np.mean((e[ok] - e[ok].mean()) * np.exp(1j * om * tt[ok])))
        ws, _ = PA.waves_zero_down(tt, e)
        Hz = float(np.mean([w["H"] for w in ws])) if ws else None
        key = "x%g_y%g" % (xg, yg)
        Hl = (gl.get(key) or {}).get("H_lin")
        rows[key] = dict(x=float(xg), y=float(yg), H1=2.0 * a1, H_zero_down=Hz, H_lin=Hl, H1_over_lin=(2.0 * a1 / Hl) if Hl else None,
                         Hzd_over_lin=(Hz / Hl) if (Hl and Hz) else None)
    band = [v["H1_over_lin"] for v in rows.values() if abs(v["x"] - 160.0) < 1e-6 and v["y"] <= 40.0 and v["H1_over_lin"] is not None]
    return dict(window_s=[t0, t1], rows=rows, x160_inner_ratios=band, band_failure=bool(band and any(r < 0.8 or r > 1.2 for r in band)),
                rule="health: generation at x 160 m, |y| <= 40 m outside 0.80-1.20 of the linear target (first harmonic, last 3 periods)",
                tag="measured (gauges) vs computed (linear target)")


def c_in_D(rd, rows, T, off):
    H = PM.load_hf(rd)
    xs, ys, tt = H["xs"], H["ys"], H["t"]
    ix = int(np.argmin(np.abs(xs - 128.0))); jy = ys <= 95.0
    out = []
    for r in rows:
        if r.get("t_on") is None or r.get("c0") is None:
            out.append(dict(k=r["k"], c_in=None)); continue
        m = (tt >= r["t_on"] - T) & (tt <= r["t_on"])
        if not m.any():
            out.append(dict(k=r["k"], c_in=None)); continue
        e = H["eta"][m][:, jy, ix].astype(np.float64)
        ci = float(np.nanmean(np.nanmax(e, axis=0)) - off)
        out.append(dict(k=r["k"], c0=r["c0"], c_in=ci, c0_over_c_in=r["c0"] / ci if ci > 0 else None))
    return dict(rows=out, rule="c_in = lateral mean over |y| <= 95 m of the per-row max of eta_top at x 128 m in [t_on - T, t_on]", tag="measured")


def predictions(cfg, rows, plan):
    rp = plan.get("registered_screen_predictions") or {}
    case = (cfg.get("dir") or {}).get("case")
    key = "main" if case == "DM1" else "fallback"
    lin = (rp.get("linear") or {}).get(key) or {}
    u3 = (rp.get("u3") or {}).get(key) or {}
    per = u3.get("periods") or []
    out = []
    for r in rows:
        if r.get("t_on") is None:
            continue
        near = min(per, key=lambda p: abs((p.get("t") or 1e9) - r["t_on"])) if per else None
        out.append(dict(k=r["k"], t_on=r["t_on"], x_on=r["x_on"], Hc=r["Hc"], linear_x_b=lin.get("x_b0"), linear_Hc=lin.get("Hc_est"),
                        u3_nearest=dict(t=near.get("t"), x_b=near.get("x_b"), c0=near.get("c0")) if near else None))
    return dict(rows=out, tag="FLIP measured vs screen computed (comparison only, never judging)")


def report(rd, opt=None, out_dir=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = PA.load_cfg(rd)
    pp = os.path.join(rd, "pana", "periodic_ana.json")
    if not os.path.exists(pp):
        raise SystemExit("run `g50_ana.py all %s` first" % rd)
    pa = json.load(open(pp, encoding="utf8"))
    plan = PA.load_plan(cfg)
    T = float((cfg.get("sf") or {}).get("T", 12.0)); off = float(pa.get("still_offset_m") or 0.0)
    rows = [w for w in (pa.get("waves") or []) if w.get("found_t", 0) >= GC50.T_JUDGE]
    strip = float(cfg["parms"]["W"]) <= 12.0
    rep = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50/g50_ana.py report", T=T, still_offset_m=off,
               plan=PA.plan_path(cfg), plan_sha256=GC50.sha256_file(PA.plan_path(cfg)))
    evs = (pa.get("events_found") or []) + (pa.get("events_secondary") or [])
    # 2026-10-16 freeze step: only an onset on the flat stays 'diagnose first'; an onset on the slope at h_b > 14 m is the focus-limited
    # regime campaign B points to (reported, never a failure)
    bad = [dict(t=e["on_t"], x=e["on_x"], depth=e.get("depth_on")) for e in evs if e["on_x"] < GC50.X_TOE]
    deep = [dict(t=e["on_t"], x=e["on_x"], depth=e.get("depth_on")) for e in evs if e["on_x"] >= GC50.X_TOE and (e.get("depth_on") or 0.0) > 14.0]
    bad_periods = sorted(set(int(round(b["t"] / T)) for b in bad if b["t"] >= GC50.T_JUDGE - 0.5 * T))
    rep["health_D"] = dict(onset_on_flat_or_deep=bool(len(bad_periods) >= 2), onset_on_flat=bad, onset_on_flat_judged_periods=bad_periods, events=bad,
                           onset_on_slope_deeper_than_14m_reported=deep, swash_setup=(pa.get("periodic_A") or {}).get("reef_top_setup"),
                           rule="diagnose first (hard): onset on the flat (x < 160.25 m) in >= 2 judged periods; swash set-up > 3 m; generation band "
                                "failure; volume > 2 % or leak (plan_D_frozen.json criteria.health). Onsets on the slope at h_b > 14 m: reported only")
    if strip:
        tab = [dict(k=w["k"], t_on=w["t_on"], x_on=w["x_on"], Hc=w["Hc"], chord_max=w["chord_max"], lip_max=w["lip_max"], hood_max=w["hood_max"],
                    P5=(w.get("judge") or {}).get("P5")) for w in rows]
        nbad = sum(1 for w in tab if w["chord_max"] is not None and w["chord_max"] < 55.0)
        rep["s2d"] = dict(breakers=tab, n_chord_lt_55=nbad, spills=bool(nbad >= 2), rule=(cfg.get("case") or {}).get("s2d_rule"),
                          T=T, H=(cfg.get("wave") or {}).get("H_m"))
    else:
        rep["generation"] = generation(rd, cfg, T, off)
        rep["c0_over_c_in_D"] = c_in_D(rd, rows, T, off)
        t_from = float(cfg["parms"].get("ramp_s", 24.0)) + T
        rep["rip_cell"] = dict(centre=mass_transport(rd, cfg, "r2", (200.0, 230.0, 260.0, 300.0), T, t_from),
                               side=mass_transport(rd, cfg, "r3", (200.0, 230.0, 260.0, 300.0), T, t_from))
        rep["predictions"] = predictions(cfg, rows, plan)
        rep["end_wall"] = end_wall(rd, cfg, T)
        od0 = out_dir or GC50.guard_out50(os.path.join(rd, "pana"))
        nums = plan_d_numbers(rd, cfg, pa, plan, rep, out_dir=od0, prev_dir=(opt or {}).get("prev"))
        rep["planD"] = dict(path=os.path.join(od0, "planD_ana.json").replace("\\", "/"), verdict=nums["decision"]["verdict"],
                            next=nums["decision"]["next"], q73_vs_DA3=nums["q73_vs_DA3"], targets=nums["targets"])
        rep["next_by_frozen_rules_D"] = [nums["decision"]["verdict"] + ": " + nums["decision"]["next"]]
    od = out_dir or GC50.guard_out50(os.path.join(rd, "pana"))
    json.dump(A46._clean(rep), open(os.path.join(od, "report_D.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    open(os.path.join(od, "REPORT_D_ja.md"), "w", encoding="utf8").write(report_md(rep, pa))
    return rep


def _n(v, f="%.2f"):
    return "—" if v is None else (f % v)


def report_md(rep, pa):
    L = ["# FLIP50 方案 D：報告だけの量 %s" % rep["run_id"], "",
         "> g50_ana.py（%s）。判定は PERIODIC_ja.md（凍らせた決まり）。ここは報告だけ。数は AI の読み、原画らしさは利用者が決める。" % rep["date"], "",
         "- 判定（periodic_ana）：%s" % pa.get("verdict"), ""]
    hd = rep["health_D"]
    L += ["## 健康（方案 D の診断の決まり）", "",
          "- 平らの上（x < 160.25 m）の巻き始め：%s（判定する周期 %s。2 周期以上で診断）" % (hd.get("onset_on_flat", hd["events"]), hd.get("onset_on_flat_judged_periods")),
          "- 斜面の上で水深 14 m より深い所の巻き始め（集まりで限界に達した崩れ。報告だけ）：%s" % hd.get("onset_on_slope_deeper_than_14m_reported"),
          "- 打ち上げの盛り上がり：%s" % json.dumps(hd.get("swash_setup"), ensure_ascii=False, default=str)[:300], ""]
    if "s2d" in rep:
        s = rep["s2d"]
        L += ["## S2D（2D の板、T %s s、H %s m）" % (_n(s["T"], "%g"), _n(s["H"])), "",
              "| k | t_on | x_on | Hc | 弦 最大 | 唇 | 覆い | P5 |", "|---|---|---|---|---|---|---|---|"]
        for w in s["breakers"]:
            L.append("| %s | %s | %s | %s | %s | %s | %s | %s |" % (w["k"], _n(w["t_on"]), _n(w["x_on"], "%.1f"), _n(w["Hc"]), _n(w["chord_max"], "%.1f"),
                                                             _n(w["lip_max"]), _n(w["hood_max"], "%.3f"), w["P5"]))
        L += ["", "- 弦 < 55° の崩れ %d（2 つ以上なら崩れ型が spilling 寄り）。決まり：%s" % (s["n_chord_lt_55"], s["rule"]), ""]
        return "\n".join(L) + "\n"
    g = rep["generation"]
    L += ["## 生成（最後の 3 周期、1 次の H ÷ 線形の目標 2|A|）【測定 ÷ 計算】", "",
          "| 波高計 | H1 (m) | H 0 下切り (m) | H_lin (m) | H1/H_lin |", "|---|---|---|---|---|"]
    for k, v in sorted(g["rows"].items(), key=lambda kv: (kv[1]["x"], kv[1]["y"])):
        L.append("| %s | %s | %s | %s | %s |" % (k, _n(v["H1"]), _n(v["H_zero_down"]), _n(v["H_lin"]), _n(v["H1_over_lin"], "%.3f")))
    L += ["", "- x 160 m・|y| ≤ 40 m の比 %s → 帯の失敗 %s（0.80〜1.20 の外で診断）" % ([round(v, 3) for v in g["x160_inner_ratios"]], g["band_failure"]), ""]
    ci = rep["c0_over_c_in_D"]
    L += ["## 集まりの利得 c0/c_in（方案 D の定義）【測定】", "", "- %s" % ", ".join("k%s %s（c0 %s、c_in %s）" % (r["k"], _n(r.get("c0_over_c_in")), _n(r.get("c0")), _n(r.get("c_in")))
                                                                    for r in ci["rows"]), "- 決まり：%s" % ci["rule"], ""]
    for nm in ("centre", "side"):
        mt = rep["rip_cell"][nm]
        L += ["## 1 周期の平均の質量の流れ（%s、%s）【測定】" % (nm, mt.get("section")), ""]
        for k, v in (mt.get("stations") or {}).items():
            L.append("- %s（水深 %s m）：U_mt %s m/s" % (k, _n(v["h_m"], "%.1f"), [None if q is None else round(q, 3) for q in v["U_mt_period_mean_mps"]]))
        L.append("")
    L += ["## 予測との比べ（比べるだけ）", ""]
    for r in rep["predictions"]["rows"]:
        L.append("- k%s：FLIP t %s s・x %s m・Hc %s m ／ 線形 x_b %s m・Hc %s m ／ U3 %s" % (r["k"], _n(r["t_on"]), _n(r["x_on"], "%.1f"), _n(r["Hc"]),
                                                                           _n(r["linear_x_b"], "%.1f"), _n(r["linear_Hc"]), r["u3_nearest"]))
    if rep.get("end_wall"):
        ew = rep["end_wall"]
        L += ["", "## 奥の壁（x 412 m、浜の上端 +6.175 m）に届く水（RV-D1、報告だけ）【測定】", "",
              "- 1 周期ごとの x ≥ 400 m の水面の最高 %s m、x ≥ 405 m に水があるコマの割合 %s" % (
                  [None if v is None else round(v, 2) for v in ew.get("max_eta_x400_per_period", [])],
                  [None if v is None else round(v, 3) for v in ew.get("wet_frac_x405_per_period", [])])]
    if rep.get("planD"):
        L += ["", "## 方案 D の判定（plan_D_frozen.json decision_rules.after_DM1）", "", "- %s" % rep["planD"]["verdict"], "- 次：%s" % rep["planD"]["next"],
              "- 崩れごとの数（方案 B と同じ物差し・集まりの利得・q）：pana/planD_table.txt・planD_ana.json"]
    L += ["", "## 凍らせた方案 D の決まりを当てはめた次の手", "", "- " + "；".join(rep.get("next_by_frozen_rules_D") or []), ""]
    return "\n".join(L) + "\n"


# ====================================================================== 2026-10-16 freeze step: campaign-B numbers, focusing gain, D verdict
def _planB_ana():
    """flip49 g49_planB_ana (read only): the campaign-B per-breaker measure, so D and DA3 / S0-S3 are read by the same code. Imported after
    redirect_gc49 (its module constants then point inside Build/FLIP50; measure() uses none of them and writes nothing)."""
    import g49_planB_ana as BA
    return BA


def _pcfg():
    import g50_pcfg as PC
    return PC


def _fin(v):
    return v is not None and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))


def _med(v):
    v = [float(x) for x in v if _fin(x)]
    return float(np.median(v)) if v else None


MED_KEYS_D = ("t_on", "x_on", "h_b", "Hc", "H_front", "H_rear", "back_inc", "back_pre_max", "back_on", "back_best", "w07_on", "w07_best", "w07_min",
              "lip_max", "chord_max", "hood_max", "best_chord", "best_lip", "best_hood", "best_front_foot", "best_hollow", "best_score3",
              "q_toe", "q_h15", "q_h13", "q_pre_max", "q_on", "h_q0.9", "h_q1.0",
              "c0_over_c_side", "c0_over_c4Hc", "curl_w_onset_over_Hc", "curl_w_maxov_over_Hc", "curl_w_td_over_Hc",
              "Hc_over_a_j", "H_front_over_a_j", "H_rear_over_a_j", "Hc_over_A_lin_on", "H_front_over_2A_lin_on", "H_rear_over_2A_lin_on",
              "Hc_over_A_lin_f", "H_front_over_2A_lin_f", "c0_over_c_in_D", "gain_c0_over_cin")


def end_wall(rd, cfg, T):
    """RV-D1 (report only): water reaching the closed end wall x = Lx (beach top +6.175 m). Per period from the ramp end: the highest top
    surface over x >= 400 m and the fraction of frames with water at x >= 405 m (hf record, interior rows y <= 95 m) [measured]."""
    try:
        H = PM.load_hf(rd)
    except SystemExit:
        return dict(error="no hf records")
    xs, tt = H["xs"], H["t"]
    m400 = xs >= 400.0
    m405 = xs >= 405.0
    if not m400.any():
        return dict(error="hf does not reach x 400 m (x max %.1f m)" % float(xs[-1]))
    t0 = float(cfg["parms"].get("ramp_s", 24.0))
    n = int((float(tt[-1]) - t0) // T)
    mx, wf = [], []
    for i in range(max(n, 0)):
        sel = (tt >= t0 + i * T) & (tt < t0 + (i + 1) * T)
        if not sel.any():
            mx.append(None); wf.append(None); continue
        e4 = H["eta"][sel][:, :, m400]
        mx.append(float(np.nanmax(e4)) if np.isfinite(e4).any() else None)
        e5 = H["eta"][sel][:, :, m405] if m405.any() else e4[:, :, :0]
        wf.append(float(np.mean(np.isfinite(e5).any(axis=(1, 2)))) if e5.size else 0.0)
    return dict(t0=t0, T=T, max_eta_x400_per_period=mx, wet_frac_x405_per_period=wf,
                beach_top_m=float(np.asarray(GC50.bed_z(np.array([GC50.LX - 1e-6]), np.array([0.0]), **GC50.SPEC_D19B)).ravel()[0]),
                rule="report only (RV-D1: Lx 412 m kept; the closed wall stands at the beach top)", tag="measured")


def q_track(row, hs, hm, x_toe):
    """q = H_rear / Hmax(h, T) along the centre-crest track of g49_planB_ana.measure (every 3rd frame; h = still depth under the crest; Hmax =
    steady Fenton fit, campaign B's q). Before onset: at the toe crossing, at h 15 and 13 m, the first depth with q >= 0.9 / 1.0 (from x_toe -
    20 m on), the maximum over onset - 3 s .. onset; at onset q_on = H_rear / Hmax(h_b) [measured H, computed Hmax]."""
    trk = sorted([dict(r) for r in (row.get("track") or []) if _fin(r.get("H_rear")) and _fin(r.get("depth")) and r["depth"] > 0.5
                  and _fin(r.get("xc")) and _fin(r.get("t"))], key=lambda r: r["t"])
    out = {"q_toe": None, "H_rear_toe": None, "q_h15": None, "q_h13": None, "q_pre_max": None, "q_on": None,
           "h_q0.9": None, "x_q0.9": None, "h_q1.0": None, "x_q1.0": None}
    hb = row.get("h_b")
    if _fin(row.get("H_rear")) and _fin(hb) and hb > 0.5:
        out["q_on"] = float(row["H_rear"]) / float(np.interp(hb, hs, hm))
    if not trk or row.get("t_on") is None:
        return out
    for r in trk:
        r["q"] = float(r["H_rear"]) / float(np.interp(r["depth"], hs, hm))
    pre = [r for r in trk if r["t"] < row["t_on"] - 1e-9]

    def near(key, val, tol):
        c = [r for r in pre if abs(r[key] - val) <= tol]
        return min(c, key=lambda r: abs(r[key] - val)) if c else None
    toe = near("xc", x_toe, 3.0)
    h15 = near("depth", 15.0, 0.75)
    h13 = near("depth", 13.0, 0.75)
    out.update(q_toe=toe["q"] if toe else None, H_rear_toe=toe["H_rear"] if toe else None, q_h15=h15["q"] if h15 else None,
               q_h13=h13["q"] if h13 else None, q_pre_max=max([r["q"] for r in pre if r["t"] >= row["t_on"] - 3.0], default=None))
    for lev in (0.9, 1.0):
        c = [r for r in pre if r["xc"] >= x_toe - 20.0 and r["q"] >= lev]
        out["h_q%.1f" % lev] = c[0]["depth"] if c else None
        out["x_q%.1f" % lev] = c[0]["xc"] if c else None
    return out


def focus_gain_setup(cfg):
    """the linear focal design on the axis for the run's directional case: |A(x, 0)| from the table code (g50_dirfield WKB) [computed]."""
    dr = cfg.get("dir") or {}
    case = dr.get("case")
    if case not in GC50.CASES:
        return None
    C = GC50.CASES[case]
    xg = np.union1d(np.arange(0.0, 340.0 + 1e-9, 0.5), [C["x_f"]])
    A = np.abs(TB.dirfield(case, x=xg).complex_amp(np.array([0.0]))[:, 0])
    return dict(case=case, xg=xg, A=A, a_j=C["a_sum"] / C["n"], a_sum=C["a_sum"], n=C["n"], x_f=C["x_f"], A_f=float(np.interp(C["x_f"], xg, A)))


def focus_gain(fg, r):
    """focusing gain of one breaker: Hc, H_front, H_rear over the component amplitude a_j and over the linear focal design (|A(x_on, 0)|,
    2|A(x_on, 0)|, and at the focus x_f) [measured / computed]. The a_j gain is large by construction (chosen phase-locking); the
    physically meaningful gains are c0/c_in (vs the incident sea) and the ratios to the linear design."""
    if not fg or r.get("x_on") is None:
        return {}
    A_on = float(np.interp(r["x_on"], fg["xg"], fg["A"]))

    def dv(a, b):
        return (float(a) / float(b)) if (_fin(a) and _fin(b) and b) else None
    return dict(a_j=fg["a_j"], a_sum=fg["a_sum"], A_lin_on=A_on, A_lin_f=fg["A_f"],
                Hc_over_a_j=dv(r.get("Hc"), fg["a_j"]), H_front_over_a_j=dv(r.get("H_front"), fg["a_j"]), H_rear_over_a_j=dv(r.get("H_rear"), fg["a_j"]),
                Hc_over_A_lin_on=dv(r.get("Hc"), A_on), H_front_over_2A_lin_on=dv(r.get("H_front"), 2.0 * A_on), H_rear_over_2A_lin_on=dv(r.get("H_rear"), 2.0 * A_on),
                Hc_over_A_lin_f=dv(r.get("Hc"), fg["A_f"]), H_front_over_2A_lin_f=dv(r.get("H_front"), 2.0 * fg["A_f"]), Hc_over_a_sum=dv(r.get("Hc"), fg["a_sum"]))


def health_D(rd, cfg, pa, rep, plan):
    """hard health failures (diagnose first, not a round) and soft items (reported beside the verdict) by plan criteria.health [measured]."""
    hc = plan["criteria"]["health"]
    hl = pa.get("health") or {}
    recs = PA.run_recs(rd)
    done = max([int(r.get("f_end_done") or 0) for r in recs] or [0])
    hard, soft = [], []
    leak = float((hl.get("bed_leak_max") or {}).get("frac", 0.0) or 0.0)
    if leak >= float(hc["bed_leak_frac_max"]):
        hard.append("bed leak %.2e >= %.0e" % (leak, hc["bed_leak_frac_max"]))
    if done < int(cfg["f_end"]):
        hard.append("run incomplete (%d of %d frames)" % (done, int(cfg["f_end"])))
    hd = rep.get("health_D") or {}
    if len(hd.get("onset_on_flat_judged_periods") or []) >= 2:
        hard.append("onset on the flat (x < 160.25 m) in judged periods %s" % hd["onset_on_flat_judged_periods"])
    if (rep.get("generation") or {}).get("band_failure"):
        hard.append("generation at x 160 m, |y| <= 40 m outside 0.80-1.20 of the linear target: %s" % rep["generation"].get("x160_inner_ratios"))
    if (hd.get("swash_setup") or {}).get("diagnose"):
        hard.append("swash set-up > 3 m (%s m)" % (hd["swash_setup"].get("max_m")))
    vol = (hl.get("volume") or {}).get("corrected_max_rel")
    st_A = (cfg.get("drift") or {}).get("stage") == "A"           # AM-D18: stage A is read as FLIP49 stage A (whole tank); same thresholds
    vlab = "stage-A whole-tank volume (max |V/V0 - 1|, AM-D18)" if st_A else "stage-C window volume"
    if vol is None:
        hard.append("volume not read")
    elif vol > float(hc["volume_hard_max"]):
        hard.append("%s %.2f %% > %.0f %%" % (vlab, 100 * vol, 100 * hc["volume_hard_max"]))
    elif vol >= float(hc["volume_drift_max"]):
        soft.append(("%s %.2f %% in the soft band %.0f-%.0f %% (diagnose before the next round)" % (vlab, 100 * vol, 100 * hc["volume_drift_max"],
                                                                                                   100 * hc["volume_hard_max"])) if st_A else
                    ("stage-C window volume %.2f %% in the soft band %.0f-%.0f %% (RV-D2: the beach set-up fed by stage C is the registered suspect; "
                     "diagnose before the next round)" % (100 * vol, 100 * hc["volume_drift_max"], 100 * hc["volume_hard_max"])))
    wh = hl.get("wall_h")
    if _fin(wh) and wh > float(hc["wall_max_h_per_coarse_3d_run"]):
        soft.append("H_wall %.2f h > %.1f h (reported)" % (wh, hc["wall_max_h_per_coarse_3d_run"]))
    off = hl.get("still_offset_m")
    if _fin(off) and abs(off) >= float(hc["still_offset_max_m"]):
        soft.append("still offset %.3f m (S0a known; reported)" % off)
    out = dict(hard=hard, soft=soft, frames_done=done, f_end=int(cfg["f_end"]), leak_frac=leak, volume_rel=vol, wall_h=wh, still_offset_m=off,
               rule=hc.get("hard_soft_rule"))
    if st_A:
        hv = hl.get("volume") or {}
        out.update(volume_measure=hv.get("stage_A_reading"), volume_whole_period_mean_rel=hv.get("stage_A_whole_period_mean_rel"),
                   volume_window_period_mean_rel=hv.get("stage_A_window_period_mean_rel"),
                   volume_raw_whole_period_mean_rel=hv.get("stage_A_raw_whole_period_mean_rel"))
    return out


def decide_D(nums, plan, cfg, prev=None):
    """the frozen decision rules after a 0.5 m D run (plan decision_rules.after_DM1, in this order; first match wins). prev: medians of the
    previous D round (Q73 between D rounds, round >= 2). Returns dict(verdict, next, rule)."""
    dr = plan["decision_rules"]
    mp = dr["partial_mapping"]
    cs = cfg.get("case") or {}
    case = (cfg.get("dir") or {}).get("case") or cs.get("dir_case")
    rnd = int(cs.get("d_round") or (1 if cs.get("queue_id") == "DM1" else 2))
    h = nums["health"]
    if h["hard"]:
        return dict(verdict="health: diagnose first", rule="after_DM1[0]", round=rnd,
                    next="diagnose first (not a round): %s. Fix and rerun; stop and ask if it cannot be diagnosed" % "; ".join(h["hard"]))
    if nums["n_judged_with_onset"] < int(dr["min_judged_breakers"]):
        return dict(verdict="fail", rule="after_DM1[1]", round=rnd,
                    next="stop and ask: fewer than %d judged breakers with an onset (PERIODIC and the medians cannot be read)" % dr["min_judged_breakers"])
    tg = nums["targets"]
    per = bool(nums["periodic"]["PERIODIC"])
    if per and tg["all_pass"]:
        return dict(verdict="pass", rule="after_DM1[2]", round=rnd,
                    next="DD3: +48 s continuation of this run with the same settings (py -3.10 -B g50_pcfg.py cfg DD3 --run=<run>) and a seamless 12 s "
                         "loop; then show the user (videos + numbers; the user judges print-likeness)")
    q = nums["q73_vs_DA3"]
    qp = nums.get("q73_vs_previous_round")
    if not q["improvement"]:
        return dict(verdict="fail", rule="after_DM1[4]", round=rnd,
                    next="stop and ask (Q73): no improvement on DA3 (d back_best %s deg, d width07_best %s, d H_front %s m; worse items %s)" % (
                        _n(q["d_back_best_deg"], "%+.1f"), _n(q["d_width07_best"], "%+.2f"), _n(q["d_H_front_m"], "%+.2f"),
                        [k for k, v in q["worse_items"].items() if v]))
    if rnd >= int(dr["max_rounds_in_D"]):
        return dict(verdict="partial", rule="after_DM1[3] + limits", round=rnd,
                    next="stop and show the user: round %d is the last D round before showing (limits.max_rounds_in_D)" % rnd)
    if rnd >= 2 and qp is not None and not qp["improvement"] and prev is not None and prev.get("improved_on_its_previous") is False:
        return dict(verdict="partial", rule="Q73 two rounds", round=rnd, next="stop and ask (Q73): two consecutive D rounds without improvement")
    used = set(cs.get("d_changes_used") or [])
    if case == "DF1":
        used.add("DF1")
    gen = nums.get("generation_x128_160_inner_median")
    a, b, c = mp[0], mp[1], mp[2]
    if gen is not None and gen < float(a["threshold"]) and "band_gain" not in used:
        nxt = "%s: in_gain = sd_gain = %.3f (= 1 / %.3f); a_sum and x_f unchanged. %s" % (a["id"], 1.0 / gen, gen, a["what"])
        return dict(verdict="partial", rule="after_DM1[3] mapping a", round=rnd, next=nxt, change=a["id"])
    each_ok = nums["periodic"].get("each_all_ok")
    if (not per) and each_ok and tg["all_pass"]:
        return dict(verdict="partial", rule="after_DM1[3] mapping b", round=rnd, next="%s: %s" % (b["id"], b["what"]), change=b["id"])
    if case != "DF1" and "DF1" not in used:
        return dict(verdict="partial", rule="after_DM1[3] mapping c", round=rnd, next="%s: %s" % (c["id"], c["what"]), change=c["id"])
    return dict(verdict="partial", rule="after_DM1[3] mapping exhausted", round=rnd,
                next="stop and ask: the frozen mapping has no further single change (DF1 already run)")


def q73_test(med, ref, rule):
    """Q73 improvement test on medians (rule = plan criteria.q73_vs_DA3 structure)."""
    def d(a, b):
        return (a - b) if (_fin(a) and _fin(b)) else None
    db = d(med.get("back_best"), ref.get("back_best_deg", ref.get("back_best")))
    dw = d(med.get("w07_best"), ref.get("width07_best", ref.get("w07_best")))
    dh = d(med.get("H_front"), ref.get("H_front_m", ref.get("H_front")))
    ia, nw = rule["improvement_any"], rule["nothing_worse"]
    imp = dict(back=bool(db is not None and db >= ia["back_best_deg"]), width07=bool(dw is not None and dw <= ia["width07_best"]))
    worse = dict(back=bool(db is not None and db < nw["back_deg"]), width07=bool(dw is not None and dw > nw["width07"]),
                 H_front=bool(dh is not None and dh < nw["H_front_m"]), missing=bool(db is None or dw is None or dh is None))
    return dict(d_back_best_deg=db, d_width07_best=dw, d_H_front_m=dh, improved_items=imp, worse_items=worse,
                improvement=bool(any(imp.values()) and not any(worse.values())))


def plan_d_numbers(rd, cfg, pa, plan, rep, out_dir, prev_dir=None):
    """the campaign-B numbers of a FLIP50 3D run, the D targets, Q73 vs DA3 and the D verdict -> out_dir/planD_ana.json + planD_table.txt."""
    BA = _planB_ana()
    PC = _pcfg()
    crit = plan["criteria"]
    bfp = os.path.join(rd, "pana", "best_frames.json")
    bf = {b["k"]: b for b in json.load(open(bfp, encoding="utf8"))["per_breaker"]} if os.path.exists(bfp) else {}
    rows, _cx = BA.measure(rd, pa, bf)
    T = float(pa["T"])
    hs, hm = PC.hmax_table(T)
    waves = {w["k"]: w for w in (pa.get("waves") or [])}
    gin = {r["k"]: r for r in ((rep.get("c0_over_c_in_D") or {}).get("rows") or [])}
    fg = focus_gain_setup(cfg)
    each = {e["k"]: e for e in ((pa.get("periodic_A") or {}).get("each") or [])}
    out_rows = []
    for r in rows:
        w = waves.get(r["k"], {})
        row = {k: v for k, v in r.items() if k not in ("ruler", "track")}
        row.update(q_track(r, hs, hm, GC50.X_TOE))
        row.update(c0=w.get("c0"), c_side=w.get("c_side"), c0_over_c_side=w.get("ratio_side"), c0_over_c4Hc=w.get("ratio_4Hc"),
                   curl_w_onset_over_Hc=w.get("w_onset_over_Hc"), curl_w_maxov_over_Hc=w.get("w_maxov_over_Hc"), curl_w_td_over_Hc=w.get("w_td_over_Hc"),
                   peel_deg=w.get("peel_deg"), judge_P1_P5=w.get("judge"), each_PERIODIC_ok=(each.get(r["k"]) or {}).get("ok"),
                   c_in_D=(gin.get(r["k"]) or {}).get("c_in"), c0_over_c_in_D=(gin.get(r["k"]) or {}).get("c0_over_c_in"))
        row.update(focus_gain(fg, r))
        row["judged"] = bool(r.get("t_on") is not None and r["t_on"] >= GC50.T_JUDGE - 1e-9)
        out_rows.append(row)
    jud = [r for r in out_rows if r["judged"]]
    meds = {k: _med([r.get(k) for r in jud]) for k in MED_KEYS_D}
    tg = crit["targets_D"]
    tp = dict(H_front=bool(_fin(meds["H_front"]) and meds["H_front"] >= tg["H_front_min_m"]),
              back_best=bool(_fin(meds["back_best"]) and meds["back_best"] >= tg["back_best_deg_min"]),
              width07_best=bool(_fin(meds["w07_best"]) and meds["w07_best"] <= tg["width07_best_max"]),
              lip=bool(_fin(meds["lip_max"]) and meds["lip_max"] >= tg["lip_min"]))
    targets = dict(medians=dict(H_front=meds["H_front"], back_best=meds["back_best"], width07_best=meds["w07_best"], lip=meds["lip_max"], Hc_reported=meds["Hc"]),
                   thresholds=tg, pass_items=tp, all_pass=bool(all(tp.values())))
    ref = crit["DA3_reference"]
    q73 = q73_test(meds, ref, crit["q73_vs_DA3"])
    prev = None
    q73p = None
    if prev_dir:
        pp = os.path.join(prev_dir, "pana", "planD_ana.json")
        if os.path.exists(pp):
            prev = json.load(open(pp, encoding="utf8"))
            q73p = q73_test(meds, prev["medians_judged"], crit["q73_vs_DA3"])
    pA = pa.get("periodic_A") or {}
    xo = np.array([r["x_on"] for r in jud if _fin(r.get("x_on"))], float)
    hc_ = np.array([r["Hc"] for r in jud if _fin(r.get("Hc"))], float)
    periodic = dict(PERIODIC=bool(pA.get("PERIODIC")), PERIODIC_k=pA.get("PERIODIC_k"), rule=(crit.get("periodic_D") or {}).get("PERIODIC", {}).get("text"),
                    windows=[dict(k=w["k"], x_dev=w.get("onset_x_max_dev"), Hc_cv=w.get("Hc_cv"), intervals_s=w.get("intervals_s"), periodic=w.get("periodic"))
                             for w in (pA.get("windows") or [])],
                    each_all_ok=bool(jud and all((each.get(r["k"]) or {}).get("ok") for r in jud)),
                    judged_onset_x_scatter_m=float(np.max(np.abs(xo - np.median(xo)))) if len(xo) else None,
                    judged_Hc_cv=float(hc_.std() / hc_.mean()) if len(hc_) >= 2 and hc_.mean() > 0 else None,
                    judged_intervals_s=[float(b["t_on"] - a["t_on"]) for a, b in zip(jud[:-1], jud[1:])])
    gen_rows = (rep.get("generation") or {}).get("rows") or {}
    gi = [v["H1_over_lin"] for v in gen_rows.values() if v.get("H1_over_lin") is not None and v["x"] in (128.0, 160.0) and v["y"] <= 40.0]
    nums = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50/g50_ana.py plan_d_numbers",
                plan=PA.plan_path(cfg), plan_sha256=GC50.sha256_file(PA.plan_path(cfg)), T=T, case=(cfg.get("dir") or {}).get("case"),
                judged_rule="centre onset t >= %g s (as campaign B 3D)" % GC50.T_JUDGE, judged_k=[r["k"] for r in jud],
                n_judged_with_onset=len([r for r in jud if _fin(r.get("x_on")) and r["x_on"] <= GC50.X_P1_MAX + 1e-9]),
                rows=out_rows, medians_judged=meds, targets=targets, q73_vs_DA3=q73, q73_vs_previous_round=q73p,
                previous_round=(prev or {}).get("run_id"), periodic=periodic, generation_x128_160_inner_median=_med(gi),
                health=health_D(rd, cfg, pa, rep, plan), end_wall=rep.get("end_wall"), DA3_reference=ref, print_reference=crit.get("print_reference"),
                focus_design=dict(case=fg["case"], a_j=fg["a_j"], a_sum=fg["a_sum"], n=fg["n"], x_f=fg["x_f"], A_lin_f=fg["A_f"]) if fg else None,
                tags=dict(shape="measured (FLIP + STUDY52 ruler through g49_planB_ana.measure, the campaign-B code; AI self-assessment)",
                          q="measured H_rear / computed Hmax (steady Fenton fit)", gain="measured / computed (linear WKB table)",
                          thresholds="chosen (frozen in plan_D_frozen.json before any 0.5 m D run)"))
    nums["decision"] = decide_D(nums, plan, cfg, prev=prev)
    nums["improved_on_its_previous"] = bool(q73p["improvement"]) if q73p is not None else bool(q73["improvement"])
    od = GC50.guard_out50(out_dir)
    json.dump(A46._clean(nums), open(os.path.join(od, "planD_ana.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    txt = planD_table(nums)
    open(os.path.join(od, "planD_table.txt"), "w", encoding="utf8").write(txt)
    print(txt)
    return nums


def planD_table(o):
    f = lambda v, p="%.2f": "-" if not _fin(v) else p % v
    L = ["%s  (%s)  plan %s  judged k %s" % (o["run_id"], o.get("case"), (o.get("plan_sha256") or "")[:12], o["judged_k"])]
    h = o["health"]
    L.append("health: hard %s | soft %s | volume %s | leak %s | frames %s/%s" % (h["hard"] or "none", h["soft"] or "none", f(h["volume_rel"], "%.4f"),
                                                                             f(h["leak_frac"], "%.1e"), h["frames_done"], h["f_end"]))
    L.append(" k  jud  t_on   x_on   h_b    Hc  Hfront Hrear | back inc  pre   on  best | w07 on best |  lip chord  hood   s3 | q toe  h15  h13  pre  on  h@0.9"
             " | c0/cs c0/c4 w_on w_mo w_td | Hc/aj Hc/Aon Hf/2Aon Hc/Af c0/cin")
    for r in o["rows"]:
        L.append("%2s  %-4s %6s %6s %5s %5s %6s %5s | %5s %5s %5s %5s | %4s %4s | %4s %5s %5s %4s | %4s %4s %4s %4s %4s %5s | %5s %5s %4s %4s %4s | %5s %5s %6s %5s %5s" % (
            r["k"], "yes" if r["judged"] else "rep", f(r.get("t_on")), f(r.get("x_on"), "%.1f"), f(r.get("h_b")), f(r.get("Hc")), f(r.get("H_front")),
            f(r.get("H_rear")), f(r.get("back_inc"), "%.1f"), f(r.get("back_pre_max"), "%.1f"), f(r.get("back_on"), "%.1f"), f(r.get("back_best"), "%.1f"),
            f(r.get("w07_on")), f(r.get("w07_best")), f(r.get("lip_max")), f(r.get("chord_max"), "%.0f"), f(r.get("hood_max"), "%.3f"), f(r.get("best_score3")),
            f(r.get("q_toe")), f(r.get("q_h15")), f(r.get("q_h13")), f(r.get("q_pre_max")), f(r.get("q_on")), f(r.get("h_q0.9"), "%.1f"),
            f(r.get("c0_over_c_side")), f(r.get("c0_over_c4Hc")), f(r.get("curl_w_onset_over_Hc")), f(r.get("curl_w_maxov_over_Hc")), f(r.get("curl_w_td_over_Hc")),
            f(r.get("Hc_over_a_j"), "%.1f"), f(r.get("Hc_over_A_lin_on")), f(r.get("H_front_over_2A_lin_on")), f(r.get("Hc_over_A_lin_f")), f(r.get("c0_over_c_in_D"))))
    m = o["medians_judged"]
    L.append("medians (judged): h_b %s Hc %s H_front %s H_rear %s | back inc %s pre %s on %s best %s | w07 on %s best %s | lip %s chord %s hood %s | "
             "q toe %s pre %s | c0/c_side %s c0/c4Hc %s curl w max-overturn %s touchdown %s | Hc/a_j %s Hc/A_lin(x_on) %s H_front/2A_lin(x_on) %s c0/c_in %s" % (
                 f(m["h_b"]), f(m["Hc"]), f(m["H_front"]), f(m["H_rear"]), f(m["back_inc"], "%.1f"), f(m["back_pre_max"], "%.1f"), f(m["back_on"], "%.1f"),
                 f(m["back_best"], "%.1f"), f(m["w07_on"]), f(m["w07_best"]), f(m["lip_max"]), f(m["chord_max"], "%.0f"), f(m["hood_max"], "%.3f"),
                 f(m["q_toe"]), f(m["q_pre_max"]), f(m["c0_over_c_side"]), f(m["c0_over_c4Hc"]), f(m["curl_w_maxov_over_Hc"]), f(m["curl_w_td_over_Hc"]),
                 f(m["Hc_over_a_j"], "%.1f"), f(m["Hc_over_A_lin_on"]), f(m["H_front_over_2A_lin_on"]), f(m["c0_over_c_in_D"])))
    p = o["periodic"]
    L.append("PERIODIC %s (k %s) | judged onset x scatter %s m | Hc CV %s | intervals %s" % (p["PERIODIC"], p["PERIODIC_k"], f(p["judged_onset_x_scatter_m"], "%.1f"),
                                                                                   f(p["judged_Hc_cv"], "%.3f"), [round(v, 2) for v in p["judged_intervals_s"]]))
    t = o["targets"]
    L.append("targets (medians): %s -> all %s" % ({k: (round(v, 3) if _fin(v) else None) for k, v in t["medians"].items()}, t["all_pass"]))
    q = o["q73_vs_DA3"]
    L.append("Q73 vs DA3: d back_best %s deg, d width07_best %s, d H_front %s m -> improvement %s (worse %s)" % (
        f(q["d_back_best_deg"], "%+.1f"), f(q["d_width07_best"], "%+.2f"), f(q["d_H_front_m"], "%+.2f"), q["improvement"], [k for k, v in q["worse_items"].items() if v]))
    if o.get("q73_vs_previous_round"):
        L.append("Q73 vs previous D round %s: %s" % (o.get("previous_round"), o["q73_vs_previous_round"]["improvement"]))
    d = o["decision"]
    L.append("D verdict: %s  (%s, round %s)" % (d["verdict"], d["rule"], d.get("round")))
    L.append("next: %s" % d["next"])
    return "\n".join(L) + "\n"


# ====================================================================== smoke (frozen smoke gates, plan_D_frozen.json smoke_gates)
def first_harmonic(E, tt, om):
    """complex first-harmonic amplitude 2 <(E - <E>) exp(i om t)> over axis 0 (time) [measured]."""
    import warnings
    E = np.asarray(E, np.float64)
    ph = np.exp(1j * om * np.asarray(tt, np.float64)).reshape((-1,) + (1,) * (E.ndim - 1))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # dry cells (all NaN) give NaN, as intended
        return 2.0 * np.nanmean((E - np.nanmean(E, axis=0)) * ph, axis=0)


def smoke_gauge_gates(gxy, G, tt, off, gl, T, sg):
    """band amplitude at the gauges over the last full period: H1 / H_lin (H_lin = 2|A| of the table); inlet band = mean over the gauges at
    sg['inlet_gauges_x']; side band = mean over sg['side_gauges_x'] x sg['side_gauges_y'] [measured / computed]."""
    om = 2 * math.pi / T
    t1 = float(tt[-1]); sel = (tt >= t1 - T - 1e-9)
    rows = {}
    for j, (xg, yg) in enumerate(gxy):
        key = "x%g_y%g" % (float(xg), float(yg))
        Hl = (gl.get(key) or {}).get("H_lin")
        e = np.asarray(G)[sel, j] - off
        if not np.isfinite(e).sum() >= 10 or not Hl:
            continue
        H1 = 2.0 * abs(first_harmonic(e[np.isfinite(e)], tt[sel][np.isfinite(e)], om))
        rows[key] = dict(x=float(xg), y=float(yg), H1=float(H1), H_lin=float(Hl), ratio=float(H1 / Hl))
    inl = [v["ratio"] for v in rows.values() if any(abs(v["x"] - x) < 1e-6 for x in sg["inlet_gauges_x"])]
    sid = [v["ratio"] for v in rows.values() if any(abs(v["x"] - x) < 1e-6 for x in sg["side_gauges_x"]) and any(abs(v["y"] - y) < 1e-6 for y in sg["side_gauges_y"])]
    lo, hi = sg["band_ratio"]
    r_in = float(np.mean(inl)) if inl else None
    r_sd = float(np.mean(sid)) if sid else None
    return dict(window_s=[t1 - T, t1], rows=rows, inlet_mean_ratio=r_in, side_mean_ratio=r_sd,
                inlet_ok=bool(r_in is not None and lo <= r_in <= hi), side_ok=bool(r_sd is not None and lo <= r_sd <= hi))


def smoke_focus_gates(xs, ys, tt, eta, x_f, T, A_lin_axis, C_lin, sg):
    """focal hot spot and recurrence from the hf top surface eta[t, y, x] (still offset removed), over the last full period:
    hot spot: the lateral contrast of the first harmonic C(x) = |A1(x, y_0)| / mean |A1(x, |y| in contrast_side_y)| (running mean over
      +- hot_smooth_m) peaks at x_hot; gate |x_hot - x_f| <= focus_dx_max_m and C(x_hot) >= contrast_min. For the designed linear field the
      same contrast peaks at x_f + ~5 m (5.1) while |A(x, 0)| itself is a plateau from the focus to the shore (shoaling), so the contrast,
      not the amplitude, marks the focus [computed];
    recurrence: strong maxima (>= recur_rel_min x the largest) of eta(x_hot, y_0, t) after recur_t_min_s are spaced T +- recur_tol_s, with
      >= recur_min_intervals intervals;
    reported (not gated): the centre-row crest nearest x_f at each designed focus instant t = nT (nonlinear crests may run ahead), and the
      realized first-harmonic amplitude on the axis over the linear design |A(x, 0)| [measured / computed]."""
    xs = np.asarray(xs, float); ys = np.asarray(ys, float); tt = np.asarray(tt, float)
    om = 2 * math.pi / T
    j0 = int(np.argmin(np.abs(ys)))
    t1 = float(tt[-1]); m = tt >= t1 - T - 1e-9
    A1 = np.abs(first_harmonic(eta[m], tt[m], om))                      # [ny, nx]
    side = (np.abs(ys) >= sg["contrast_side_y"][0]) & (np.abs(ys) <= sg["contrast_side_y"][1])
    dxg = float(np.median(np.diff(xs)))
    nh = max(0, int(round(sg["hot_smooth_m"] / dxg)))
    ker = np.ones(2 * nh + 1) / (2 * nh + 1)
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sid = np.nanmean(A1[side], axis=0)
    num = np.convolve(np.nan_to_num(A1[j0]), ker, mode="same")
    den = np.convolve(np.nan_to_num(sid), ker, mode="same")
    with np.errstate(divide="ignore", invalid="ignore"):
        Cx = np.where(den > 1e-6, num / den, np.nan)
    sel = (xs >= sg["hot_x_range"][0]) & (xs <= sg["hot_x_range"][1]) & np.isfinite(Cx)
    if sel.any():
        k = int(np.where(sel)[0][np.argmax(Cx[sel])])
        x_hot, c_hot = float(xs[k]), float(Cx[k])
    else:
        x_hot, c_hot = None, None
    xl = np.asarray(C_lin["x"], float)
    x_hot_lin = float(xl[int(np.argmax(C_lin["C"]))]) if len(xl) else None
    inst = []
    for n in range(1, 1000):
        tn = n * T
        if tn < sg["focus_t_min_s"] - 1e-9 or tn > t1 - sg["focus_t_margin_s"] + 1e-9:
            continue
        i = int(np.argmin(np.abs(tt - tn)))
        e = eta[i, j0, :]
        win = np.where((xs >= x_f - 60.0) & (xs <= x_f + 60.0))[0]
        cand = [q for q in win if 2 <= q < len(xs) - 2 and np.isfinite(e[q]) and e[q] > 0.0 and e[q] >= np.nanmax(e[max(q - 3, 0):q + 4])]
        if cand:
            q = min(cand, key=lambda q_: abs(xs[q_] - x_f))
            inst.append(dict(t=float(tt[i]), x_c=float(xs[q]), dx=float(xs[q] - x_f), eta_c=float(e[q])))
        else:
            inst.append(dict(t=float(tt[i]), x_c=None, dx=None, eta_c=None))
    ixh = int(np.argmin(np.abs(xs - (x_hot if x_hot is not None else x_f))))
    ee = eta[:, j0, ixh]
    mm = tt >= sg["recur_t_min_s"]
    tq, eq = tt[mm], ee[mm]
    half = max(1, int(round(0.25 * T / max(float(np.median(np.diff(tt))), 1e-6))))
    pk = [i for i in range(1, len(eq) - 1) if np.isfinite(eq[i]) and eq[i] >= np.nanmax(eq[max(i - half, 0):i + half + 1])]
    top = max([eq[i] for i in pk], default=None)
    strong = [i for i in pk if top is not None and eq[i] >= sg["recur_rel_min"] * top]
    tpk = [float(tq[i]) for i in strong]
    iv = [b - a for a, b in zip(tpk[:-1], tpk[1:])]
    rec_ok = bool(len(iv) >= sg["recur_min_intervals"] and all(abs(v - T) <= sg["recur_tol_s"] for v in iv))
    xa = np.asarray(A_lin_axis["x"], float); aa = np.asarray(A_lin_axis["A"], float)
    real = {}
    for xq in (160.0, x_f, 240.0):
        ix = int(np.argmin(np.abs(xs - xq)))
        al = float(np.interp(xq, xa, aa))
        real["x%g" % xq] = dict(A1_axis=float(A1[j0, ix]), A_lin=al, ratio=float(A1[j0, ix] / al) if al > 0 else None)
    return dict(window_s=[t1 - T, t1], x_hot=x_hot, contrast_at_hot=c_hot, x_hot_linear_design=x_hot_lin,
                contrast_linear_max=float(np.max(C_lin["C"])) if len(xl) else None,
                hot_ok=bool(x_hot is not None and abs(x_hot - x_f) <= sg["focus_dx_max_m"]),
                contrast_ok=bool(c_hot is not None and c_hot >= sg["contrast_min"]),
                contrast_profile=dict(x=[float(v) for v in xs[sel][::2]], C=[round(float(v), 3) for v in Cx[sel][::2]]),
                recurrence=dict(x_m=float(xs[ixh]), peak_t=tpk, intervals_s=iv, ok=rec_ok),
                crest_at_focus_instants_reported=inst, realized_axis_amplitude_reported=real, x_f=x_f,
                note="first harmonic A1 = 2 <(eta - <eta>) e^{i om t}> over the last full period: |A1| is the amplitude (crest of a linear wave)")


def linear_contrast(case, ys, sg):
    """the same contrast C(x) and the axis amplitude |A(x, 0)| for the designed linear field (reference for the smoke gates) [computed]."""
    C = GC50.CASES[case]
    xg = np.union1d(np.arange(140.0, 300.0 + 1e-9, 1.0), [C["x_f"]])
    df = TB.dirfield(case, x=xg)
    yy = np.asarray(ys, float)
    A = np.abs(df.complex_amp(np.abs(yy)))                              # [nx, ny]
    side = (np.abs(yy) >= sg["contrast_side_y"][0]) & (np.abs(yy) <= sg["contrast_side_y"][1])
    j0 = int(np.argmin(np.abs(yy)))
    Cx = A[:, j0] / np.maximum(A[:, side].mean(axis=1), 1e-9)
    return dict(x=xg, C=Cx), dict(x=xg, A=A[:, j0])


def smoke(rd, out_dir=None):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = PA.load_cfg(rd)
    plan = PA.load_plan(cfg)
    sg = plan["smoke_gates"]
    recs = PA.run_recs(rd)
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), judged=False, plan=PA.plan_path(cfg),
               plan_sha256=GC50.sha256_file(PA.plan_path(cfg)), gates={}, rule=sg.get("text"))
    ck = out["gates"]
    last = max(recs, key=lambda r: int(r.get("f_end_done") or 0)) if recs else {}
    ck["finished_in_one_launch"] = bool(last and int(last.get("f_end_done") or 0) >= int(cfg["f_end"]) and not last.get("stopped") and len(recs) == 1)
    out["launches"] = [dict(f_start=r.get("f_start"), f_end_done=r.get("f_end_done"), wall_s=r.get("wall_total_s"), stopped=r.get("stopped")) for r in recs]
    dt = (recs[0].get("info") or {}).get("dir_table") if recs else None
    out["dir_table"] = dt
    ck["table_loaded"] = bool(dt and int(dt.get("d_nfield") or 0) == len(GC50.TABLE_FIELDS))
    leaks = [l for r in recs for l in ((r.get("info") or {}).get("leak") or [])]
    pmax = max([r.get("particles_max") or 0 for r in recs] or [1])
    lm = max([l.get("n_below_bed") or 0 for l in leaks] or [0])
    out["leak_max_frac"] = lm / max(pmax, 1)
    ck["no_leak"] = bool(out["leak_max_frac"] < sg["leak_frac_max"])
    errs = {k: v for r in recs for k, v in (r.get("info") or {}).items() if k.endswith("_errors") or k == "error"}
    out["errors"] = errs
    ck["no_errors"] = not errs
    off = PA.still_off(recs)
    T = float((cfg.get("sf") or {}).get("T", 12.0)); om = 2 * math.pi / T
    R = PA.load_r6(rd)
    gg = smoke_gauge_gates(R["gxy"], R["gauge"], R["t"], off, (cfg.get("dir") or {}).get("gauges_lin") or {}, T, sg)
    out["gauges"] = gg
    ck["inlet_band_amplitude"] = gg["inlet_ok"]
    ck["side_band_amplitude"] = gg["side_ok"]
    H = PM.load_hf(rd)
    xs, ys, tt = H["xs"], H["ys"], H["t"]
    eta = H["eta"].astype(np.float64) - off
    case = (cfg.get("dir") or {}).get("case", "DM1")
    C_lin, A_lin = linear_contrast(case, ys, sg)
    fo = smoke_focus_gates(xs, ys, tt, eta, GC50.CASES[case]["x_f"], T, A_lin, C_lin, sg)
    out["focus"] = fo
    ck["focal_hot_spot_at_x_f"] = fo["hot_ok"]
    ck["focal_lateral_contrast"] = fo["contrast_ok"]
    ck["recurrence_T"] = fo["recurrence"]["ok"]
    t1 = float(tt[-1]); m = (tt >= t1 - T - 1e-9)
    ix = int(np.argmin(np.abs(xs - 160.0)))
    Am = first_harmonic(eta[m][:, :, ix], tt[m], om)
    jy = ys <= 95.0
    df = TB.dirfield(case)
    Al = df.complex_amp(ys)[int(np.argmin(np.abs(df.x - 160.0)))]
    a, b = Am[jy], Al[jy]
    corr = float(abs(np.sum(a * np.conj(b))) / math.sqrt(float(np.sum(np.abs(a) ** 2) * np.sum(np.abs(b) ** 2))))
    out["pattern_x160"] = dict(window_s=[t1 - T, t1], complex_corr_y_le_95=corr, ys=[float(v) for v in ys[jy]],
                               abs_meas=[round(float(v), 3) for v in np.abs(a)], abs_lin=[round(float(v), 3) for v in np.abs(b)])
    ck["pattern_corr_x160"] = bool(corr >= sg["pattern_corr_min"])
    try:
        cx = PA.Ctx49(rd, {})
        evs = A46.centre_events(cx, 0.0, t1, 5.0, GC50.X_TOE)
        flat = [dict(t=e["onset"]["t"], x=e["onset"]["xc"], eta_c=e["onset"]["eta_c"]) for e in evs if e.get("onset") and e["onset"]["eta_c"] >= 1.0
                and e["onset"]["xc"] < GC50.X_TOE]
        out["breaking_on_flat"] = dict(onsets=flat, rule="g46 centre_events on r2 (y 0): thmax >= 90 deg, crest >= 1 m, x 5-160.25 m, whole run")
        ck["no_breaking_on_flat"] = not flat
    except Exception as ex:
        out["breaking_on_flat"] = dict(error=repr(ex)[:300])
        ck["no_breaking_on_flat"] = False
    hl = PA.health(rd, cfg, R, off, recs)
    out["volume"] = hl.get("volume")
    vr = (hl.get("volume") or {}).get("corrected_max_rel")
    ck["volume_stage_A_whole" if (cfg.get("drift") or {}).get("stage") == "A" else "volume_stage_C"] = bool(vr is not None and vr < sg["volume_max"])
    out["ok"] = bool(all(ck.values()))
    out["next"] = ("all smoke gates pass -> launch DM1 (dp 0.5) by the frozen queue" if out["ok"] else
                   "smoke gate(s) failed (%s) -> diagnose and fix (code or preset), re-smoke (not a round); a fix that changes a frozen design number "
                   "needs a dated amendment before DM1; stop and ask if it cannot be diagnosed" % ", ".join(k for k, v in ck.items() if not v))
    od = GC50.guard_out50(out_dir or os.path.join(rd, "pana"))
    json.dump(A46._clean(out), open(os.path.join(od, "smoke_D.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    try:
        vd = GC50.guard_out50(out_dir or os.path.join(rd, "video"))
        out["video"] = smoke_video(xs, ys, tt, eta, cfg, fo, os.path.join(vd, "%s_smoke.mp4" % cfg.get("run_id")))
    except Exception as ex:
        out["video"] = dict(error=repr(ex)[:300])
    json.dump(A46._clean(out), open(os.path.join(od, "smoke_D.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


def smoke_video(xs, ys, tt, eta, cfg, fo, path, fps_out=8, step_s=0.25, hold_s=2.0, W=1600):
    """smoke mp4 (Q71 style): top view (colour = height above the still level, mirrored about y = 0, 1:1) and the centre section y = 0 over
    x 140-300 m (1:1) with the linear envelope +-|A(x, 0)| of the designed field; a thick RED frame and a hold at each designed focus instant
    t = nT (the phase-locked crest on the focus: the instant a smoke must show). Numbers are measured; the field and its focus are CHOSEN at
    the inlet (written on every frame)."""
    import subprocess
    from PIL import Image, ImageDraw, ImageFont
    font_p = "C:/Windows/Fonts/meiryo.ttc"
    _fc = {}

    def fnt(sz):
        if sz not in _fc:
            try:
                _fc[sz] = ImageFont.truetype(font_p, sz)
            except Exception:
                _fc[sz] = ImageFont.load_default()
        return _fc[sz]
    case = (cfg.get("dir") or {}).get("case", "DM1")
    C = GC50.CASES[case]
    fg = focus_gain_setup(cfg)
    xs = np.asarray(xs, float); ys = np.asarray(ys, float); tt = np.asarray(tt, float)
    x0, x1 = float(xs[0]), float(xs[-1])
    jy = ys <= 95.0 + 1e-9
    ymax = float(ys[jy][-1])
    j0 = int(np.argmin(np.abs(ys)))
    ph = 420
    pw = int(round(ph * (x1 - x0) / (2.0 * ymax)))
    if pw > W - 80:
        pw = W - 80; ph = int(round(pw * 2.0 * ymax / (x1 - x0)))
    PV = (40, 136, 40 + pw, 136 + ph)
    sx_top = pw / (x1 - x0)
    xs0, xs1, zlo, zhi = 140.0, 300.0, -10.0, 10.0
    sx = (W - 80) / (xs1 - xs0)
    SB = (40, PV[3] + 70, W - 40, PV[3] + 70 + int(round((zhi - zlo) * sx)))
    Hh = SB[3] + 40
    Hh += Hh % 2
    stops = np.array([-6.0, -2.0, 0.0, 2.0, 5.0, 9.0])
    cols = np.array([[20, 40, 110], [60, 110, 180], [200, 215, 230], [120, 190, 220], [245, 245, 245], [255, 120, 80]], float)

    def colour(z):
        z = np.nan_to_num(z, nan=-99.0)
        rgb = np.stack([np.interp(z, stops, cols[:, k]) for k in range(3)], -1)
        rgb[z < -98.0] = (235, 225, 200)
        return rgb.astype(np.uint8)

    def P(x, z):
        return (SB[0] + (x - xs0) * sx, SB[3] - (z - zlo) * sx)
    inst = fo.get("crest_at_focus_instants_reported") or []
    focus_t = [q["t"] for q in inst]
    times = list(np.arange(float(tt[0]), float(tt[-1]) + 1e-9, step_s))
    xb = np.linspace(xs0, xs1, 200)
    zb = np.asarray(GC50.bed_z(xb, np.zeros_like(xb), **GC50.SPEC_D19B), float)
    proc = subprocess.Popen([GC50.FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, Hh), "-r", str(fps_out),
                             "-i", "-", "-vcodec", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", path], stdin=subprocess.PIPE)
    n_written = 0
    for tq in times:
        i = int(np.argmin(np.abs(tt - tq)))
        img = Image.new("RGB", (W, Hh), (250, 250, 248))
        dr = ImageDraw.Draw(img)
        dr.text((40, 8), "FLIP50 %s  t = %.2f s（煙の試し・粒子 %g m・判定しない）" % (cfg.get("run_id"), tt[i], float(cfg["parms"]["dp"])), fill=(20, 20, 20), font=fnt(22))
        dr.text((40, 40), "選んだ物【選び】：方向のある波（T %g s・±%g°・%d 成分）と焦点 x %.2f m・時刻 t = nT、海底 D19B。計算した物：浅くなる・屈折・集まり・崩れ。力は重力だけ"
                % (C["T"], C["theta_max_deg"], C["n"], C["x_f"]), fill=(60, 60, 60), font=fnt(15))
        dr.text((40, 64), "上：上から（色＝静かな水面からの高さ、y = 0 で写して両側、縦横同じ縮尺）。下：真ん中の断面 x 140〜300 m（青、縦横同じ縮尺）と設計の線形の包絡 ±|A(x,0)|（灰）",
                fill=(60, 60, 60), font=fnt(14))
        dr.text((40, 86), "赤い枠＝焦点の時刻 t = nT（選んだ位相で頂が焦点に来る時刻）。数は【測定】", fill=(160, 0, 0), font=fnt(14))
        e = np.asarray(eta[i], float)[jy]
        full = np.concatenate([e[::-1], e], axis=0)
        top = Image.fromarray(colour(full)[::-1]).resize((pw, ph), Image.NEAREST)
        img.paste(top, (PV[0], PV[1]))
        dr.rectangle(PV, outline=(120, 120, 120))
        for xv, lab in ((GC50.X_TOE, "斜面の足"), (C["x_f"], "焦点 x_f"), (GC50.X_SHORE, "汀線")):
            px = PV[0] + (xv - x0) * sx_top
            dr.line([(px, PV[1]), (px, PV[3])], fill=(90, 90, 90), width=1)
            dr.text((px + 3, PV[1] - 27), lab, fill=(60, 60, 60), font=fnt(12))
        lx = PV[2] + 20
        for k_, (z, c_) in enumerate(zip(stops, cols)):
            dr.rectangle((lx, PV[1] + 22 * k_, lx + 18, PV[1] + 22 * k_ + 18), fill=tuple(int(v) for v in c_))
            dr.text((lx + 24, PV[1] + 22 * k_), "%+g m" % z, fill=(40, 40, 40), font=fnt(13))
        dr.rectangle(SB, outline=(150, 150, 150))
        dr.line([P(a, max(b, zlo)) for a, b in zip(xb, zb)], fill=(120, 90, 50), width=2)
        dr.line([P(xs0, 0.0), P(xs1, 0.0)], fill=(170, 170, 170), width=1)
        for xv in range(150, 301, 50):
            dr.text((P(xv, zlo)[0] - 12, SB[3] + 4), "%d m" % xv, fill=(60, 60, 60), font=fnt(12))
        if fg:
            mm = (fg["xg"] >= xs0) & (fg["xg"] <= xs1)
            dr.line([P(a, b) for a, b in zip(fg["xg"][mm], fg["A"][mm])], fill=(150, 150, 150), width=1)
            dr.line([P(a, -b) for a, b in zip(fg["xg"][mm], fg["A"][mm])], fill=(150, 150, 150), width=1)
        sec = np.asarray(eta[i], float)[j0]
        pts = [P(a, min(max(b, zlo), zhi)) for a, b in zip(xs, sec) if np.isfinite(b) and xs0 <= a <= xs1]
        if len(pts) > 1:
            dr.line(pts, fill=(30, 80, 200), width=2)
        px = P(C["x_f"], 0.0)[0]
        dr.line([(px, SB[1]), (px, SB[3])], fill=(90, 90, 90), width=1)
        hot = any(abs(tt[i] - ft) <= 0.5 * step_s + 1e-9 for ft in focus_t)
        if hot:
            for rr in (PV, SB):
                dr.rectangle((rr[0] - 6, rr[1] - 6, rr[2] + 6, rr[3] + 6), outline=(220, 0, 0), width=6)
            q = min(inst, key=lambda q: abs(q["t"] - tt[i]))
            dr.text((SB[0] + 10, SB[1] + 8), "焦点の時刻 t = %.2f s：真ん中の頂 x %s m（x_f との差 %s m）。最後の 1 周期の 1 次の波で、横の比の最大は x %s m（%s 倍、設計の線形 x %s m）【測定・計算】" % (
                q["t"], _n(q.get("x_c"), "%.1f"), _n(q.get("dx"), "%+.1f"), _n(fo.get("x_hot"), "%.1f"), _n(fo.get("contrast_at_hot"), "%.2f"),
                _n(fo.get("x_hot_linear_design"), "%.1f")), fill=(200, 0, 0), font=fnt(15))
        reps = int(round(hold_s * fps_out)) if hot else 1
        buf = np.asarray(img, np.uint8).tobytes()
        for _ in range(reps):
            proc.stdin.write(buf); n_written += 1
    proc.stdin.close(); proc.wait()
    return dict(path=path.replace("\\", "/"), frames=n_written, fps=fps_out, step_s=step_s, size=[W, Hh],
                ok=bool(proc.returncode == 0 and os.path.exists(path)))


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = PA.parse(sys.argv[1:])
    if len(pos) < 2:
        print(__doc__); sys.exit(1)
    rd = os.path.abspath(pos[1])
    if pos[0] in ("all", "s2d"):
        o = PA.main_all(rd, opt)
        print(o["verdict"])
        r = report(rd, opt)
        print(json.dumps(A46._clean({k: v for k, v in r.items() if k in ("health_D", "s2d", "next_by_frozen_rules_D")}), ensure_ascii=False)[:3000])
    elif pos[0] == "report":
        r = report(rd, opt)
        print(json.dumps(A46._clean({k: v for k, v in r.items() if k in ("health_D", "s2d", "next_by_frozen_rules_D")}), ensure_ascii=False)[:3000])
    elif pos[0] == "smoke":
        o = smoke(rd)
        print("SMOKE_D gates ok %s (never judged)" % o["ok"], json.dumps(A46._clean(o["gates"])), "| next:", o["next"], "| video:", o.get("video"))
    elif pos[0] in ("inlet", "events", "sup"):
        sys.argv = [sys.argv[0]] + sys.argv[1:]
        if pos[0] == "inlet":
            print(json.dumps(A46._clean({k: v for k, v in PA.inlet(rd, None).items() if k != "gauges"}), ensure_ascii=False, indent=1)[:3000])
        elif pos[0] == "events":
            evr, _ = PA.find_breakers(rd, PA.load_cfg(rd))
            PA.jdump(evr, os.path.join(PA.guard(os.path.join(rd, "pana")), "events.json"))
            for e in evr["events"]:
                print("k=%d t=%.2f x=%.1f eta=%.2f judged=%s %s" % (e["k"], e["on_t"], e["on_x"], e["on_eta"], e["judged"], e["why"]))
        else:
            PA.main_sup(rd, opt)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
