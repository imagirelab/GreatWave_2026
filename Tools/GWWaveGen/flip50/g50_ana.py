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
usage:
  py -3.10 -B g50_ana.py all <run>        periodic_ana all (events, per-breaker P1-P5, PERIODIC, best_frames.json) + the D report
  py -3.10 -B g50_ana.py report <run>     the D report only (after all)
  py -3.10 -B g50_ana.py smoke <run>      SMOKE_D check (never judged): pipeline, leak, table loaded, pattern at x 160 m vs the linear target
                                          (complex correlation over |y| <= 95 m >= 0.9), generation ratios, dir_check -> pana/smoke_D.json
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
    """the frozen D decision rules (plan_D_frozen.json decision_rules.after_DM1 / after_DF1), applied as written (the orchestrator and the
    user decide)."""
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


def report(rd, opt=None):
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
    bad = [dict(t=e["on_t"], x=e["on_x"], depth=e.get("depth_on")) for e in evs if e["on_x"] < GC50.X_TOE or (e.get("depth_on") or 0.0) > 14.0]
    rep["health_D"] = dict(onset_on_flat_or_deep=bool(bad), events=bad, swash_setup=(pa.get("periodic_A") or {}).get("reef_top_setup"),
                           rule="diagnose first: onset on the flat (x < 160.25 m) or at h_b > 14 m; swash set-up > 3 m; generation band failure; volume/leak")
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
        rep["next_by_frozen_rules_D"] = next_D(rows, pa.get("periodic_A") or {}, pa.get("health") or {}, cfg, rep)
    od = GC50.guard_out50(os.path.join(rd, "pana"))
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
    L += ["## 健康（方案 D の診断の決まり）", "", "- 平らの上（x < 160.25 m）か水深 14 m より深い所の巻き始め：%s %s" % (hd["onset_on_flat_or_deep"], hd["events"]),
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
    L += ["", "## 凍らせた方案 D の決まりを当てはめた次の手", "", "- " + "；".join(rep.get("next_by_frozen_rules_D") or []), ""]
    return "\n".join(L) + "\n"


# ====================================================================== smoke
def smoke(rd):
    rd = os.path.abspath(rd).replace("\\", "/")
    cfg = PA.load_cfg(rd)
    recs = PA.run_recs(rd)
    out = dict(run_id=cfg.get("run_id"), date=time.strftime("%Y-%m-%d %H:%M:%S"), judged=False, checks={})
    ck = out["checks"]
    last = max(recs, key=lambda r: int(r.get("f_end_done") or 0)) if recs else {}
    ck["finished"] = bool(last and int(last.get("f_end_done") or 0) >= int(cfg["f_end"]) and not last.get("stopped"))
    dt = (recs[0].get("info") or {}).get("dir_table") if recs else None
    out["dir_table"] = dt
    ck["table_loaded"] = bool(dt and int(dt.get("d_nfield") or 0) == len(GC50.TABLE_FIELDS))
    leaks = [l for r in recs for l in ((r.get("info") or {}).get("leak") or [])]
    pmax = max([r.get("particles_max") or 0 for r in recs] or [1])
    lm = max([l.get("n_below_bed") or 0 for l in leaks] or [0])
    out["leak_max_frac"] = lm / max(pmax, 1)
    ck["leak"] = bool(out["leak_max_frac"] < 1e-4)
    errs = {k: v for r in recs for k, v in (r.get("info") or {}).items() if k.endswith("_errors") or k == "error"}
    out["errors"] = errs
    ck["no_errors"] = not errs
    off = PA.still_off(recs)
    T = float((cfg.get("sf") or {}).get("T", 12.0)); om = 2 * math.pi / T
    H = PM.load_hf(rd)
    xs, ys, tt = H["xs"], H["ys"], H["t"]
    t1 = float(tt[-1]); t0 = t1 - T
    m = (tt >= t0 - 1e-9) & (tt <= t1 + 1e-9)
    ix = int(np.argmin(np.abs(xs - 160.0)))
    E = H["eta"][m][:, :, ix].astype(np.float64) - off               # [frames, y]
    jy = ys <= 95.0
    Am = 2.0 * np.nanmean((E - np.nanmean(E, axis=0)) * np.exp(1j * om * tt[m])[:, None], axis=0)
    case = (cfg.get("dir") or {}).get("case", "DM1")
    df = TB.dirfield(case)
    i160 = int(np.argmin(np.abs(df.x - 160.0)))
    Al = df.complex_amp(ys)[i160]
    a, b = Am[jy], Al[jy]
    corr = float(abs(np.sum(a * np.conj(b))) / math.sqrt(float(np.sum(np.abs(a) ** 2) * np.sum(np.abs(b) ** 2))))
    inner = ys <= 40.0
    out["pattern_x160"] = dict(window_s=[t0, t1], complex_corr_y_le_95=corr, amp_ratio_y_le_40=float(np.mean(np.abs(Am[inner])) / np.mean(np.abs(Al[inner]))),
                               amp_ratio_y_60_80=float(np.mean(np.abs(Am[(ys >= 60) & (ys <= 80)])) / np.mean(np.abs(Al[(ys >= 60) & (ys <= 80)]))),
                               ys=[float(v) for v in ys[jy]], abs_meas=[round(float(v), 3) for v in np.abs(a)], abs_lin=[round(float(v), 3) for v in np.abs(b)],
                               note="first harmonic over the last period; dp 1.0 damps more than dp 0.5 (amplitude reported, correlation judged)")
    ck["pattern_corr_ge_0p9"] = bool(corr >= 0.9)
    dcs = [d for r in recs for d in ((r.get("info") or {}).get("dir_check") or [])]
    if dcs:
        dl = dcs[-1]
        rr = [q for q in dl["rows"] if q.get("g", 0) > 0.5 and q.get("u_grid") is not None]
        out["dir_check_last"] = dict(frame=dl["frame"], t=dl["t"], n=len(rr),
                                     max_abs_du=float(max([abs(q["u_grid"] - q["u_tgt"]) for q in rr] or [0.0])),
                                     max_abs_dv=float(max([abs((q.get("v_grid") or 0.0) - q["v_tgt"]) for q in rr] or [0.0])),
                                     note="band points with band factor > 0.5: grid velocity vs target (the relaxation never reaches the target exactly)")
    out["volume"] = (PA.health(rd, cfg, PA.load_r6(rd), off, recs).get("volume"))
    out["ok"] = bool(all(ck.values()))
    od = GC50.guard_out50(os.path.join(rd, "pana"))
    json.dump(A46._clean(out), open(os.path.join(od, "smoke_D.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    return out


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
        print("SMOKE_D ok %s (never judged)" % o["ok"], json.dumps(A46._clean(o["checks"])), "corr %.3f amp(|y|<=40) %.3f" % (
            o["pattern_x160"]["complex_corr_y_le_95"], o["pattern_x160"]["amp_ratio_y_le_40"]))
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
