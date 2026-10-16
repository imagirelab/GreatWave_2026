# -*- coding: utf-8 -*-
"""FLIP50 (option D): run configurations (cfg.json) with prechecks, the numpy check of the whole D set-up, and the plan freeze (py -3.10 -B).
2026-10-15 written new (Claude). flip45-flip49 files are read only (g49_common through g50_common, FLIP49 runs.jsonl for the DA1 rates).

  py -3.10 -B g50_pcfg.py check
        numpy checks (< 1 min) -> Unity/Build/FLIP50/plan/precheck_D.json: directional tables (g50_table.checks: focus vs theory, phase integral,
        continuity / volume flux, symmetry, interpolation, vertical profile, mean mass flux), constants = the design screen (s50_final.json),
        D19B bed (analytic bit for bit, laterally uniform, FLIP48 plain path), particle-count model, band numpy mirror behaviour, ray aperture,
        and the precheck of every preset (SMOKE_D, DM1, DF1, S2D_T12, S2D_T10) with the run-time estimate.
  py -3.10 -B g50_pcfg.py cfg SMOKE_D|DM1|DF1|S2D_T12|S2D_T10|all [--heavy=cont|screen] [--ret=1|0]
        write runs/ready/<id>.json (3D), smoke/ready/ (SMOKE_D), strips/ready/ (S2D) under Unity/Build/FLIP50, with the precheck inside;
        not written if the precheck fails (g50_chain.py also checks precheck.ok, the build check, the frozen plan sha256 and the table sha256).
        Writes the table npz (g50_table.write) when missing.
  py -3.10 -B g50_pcfg.py cfg DD3 --run=<DM1 or DF1 run folder>
        +48 s continuation (same run_id, resumes from the last checkpoint) when PERIODIC passes (frozen rule).
  py -3.10 -B g50_pcfg.py freezeD [--force=1 --reason=...]
        Unity/Build/FLIP50/plan/plan_D_frozen.json (+ .sha256) from plan_D_draft.json (g50_planD.py). Refuses to overwrite once a FLIP50 3D
        run has records, and needs --force with a reason to re-freeze before that.
Presets (reasons in plan_D_draft.json):
  SMOKE_D  3D dp 1.0, W 140, DM1 sea, 0-48 s (ramp 24 s + travel to x 160 m ~10 s + one full period), one launch, never judged.
  DM1      main: 3D dp 0.5, W 140, T 12 s, +-80 deg, 30 components, focus (220.25, 0), stage C, 92 s, heavy records 44 s..end every 3rd frame.
  DF1      fallback (frozen rule only): T 10 s, ramp 20 s, 86 s.
  S2D_T12 / S2D_T10   2D strips (W 6, dp 0.5) on the D19B axis: Fenton inlet at h0 19 m, H = 0.83 Hmax2D (S2D, optional).
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, json, math, time, glob, copy, shutil

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np                  # noqa: E402
import g50_common as GC             # noqa: E402
import g50_table as TB              # noqa: E402
import g50_dirfield as DF           # noqa: E402

EXPECT_PARTICLES = {("3d", 0.5): 5383840, ("3d", 1.0): 665000, ("strip", 0.5): 230736}    # [computed] count_particles, D19B, Lx 412, zb -19
HEAVY_CONT = dict(t0=44.0, every=3)       # heavy records (r4, r5) continuously from 44 s every 3rd frame [chosen: AM-A2 precedent of plan A;
                                          # break time uncertain by several s (onset x +-25 m), so screen windows could miss it]
SMOKE_T_END = 48.0
SMOKE_WINDOW = (36.0, 48.0)               # one full period at x 160 m after the ramp and the travel from the band [computed]
S2D_T_END = {12.0: 84.0, 10.0: 70.0}      # ramp + 5 periods (3-4 breakers at t >= 45 s for T 12) [chosen]
DD3_EXTRA_S = 48.0
STRIP_S_PER_FRAME = 0.29                  # FLIP49 S1 strip (dp 0.5, 0.30 M particles, substeps 1-2): 818 s / 2881 frames [measured]


# ====================================================================== run-time model
def da1_phases():
    """DA1 launches (FLIP49 runs.jsonl, read only): s per frame before the heavy window (launch 1) and in the breaking phase (later launches,
    heavy records every 3rd frame from 47 s, substeps up to 3). Per million particles with the launch's particles_max. [measured]"""
    rows = []
    if os.path.exists(GC.RUNS49_JSONL):
        for ln in open(GC.RUNS49_JSONL, encoding="utf8"):
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("run_id") == "DA1_SC37_T12H7p5_dp0p5" and r.get("f_end_done"):
                nf = int(r["f_end_done"]) - int(r["f_start"]) + 1
                rows.append(dict(f_start=int(r["f_start"]), f_end=int(r["f_end_done"]), frames=nf, wall_s=float(r["wall_total_s"]),
                                 s_per_frame=float(r["wall_total_s"]) / nf, particles_max=int(r["particles_max"]),
                                 s_per_Mp_frame=float(r["wall_total_s"]) / nf / (int(r["particles_max"]) / 1e6), substeps=r.get("substeps_min_max")))
    pre = [r for r in rows if r["f_end"] <= 1129]
    brk = [r for r in rows if r["f_start"] >= 1129 - 240]
    out = dict(launches=rows, source=GC.RUNS49_JSONL)
    if pre:
        out["pre_s_per_Mp_frame"] = float(np.mean([r["s_per_Mp_frame"] for r in pre]))
    if brk:
        out["break_s_per_Mp_frame"] = float(np.mean([r["s_per_Mp_frame"] for r in brk]))
    return out


def time_estimate(n, f_from, f_end, heavy, t_break=36.0):
    """[computed] (1) FLIP48 coefficient rule (as FLIP49): COEF x n x growth x frames + heavy x 1.8 s; (2) DA1 two-phase rule: frames before
    t_break at the DA1 pre-break rate, after it at the DA1 breaking-phase rate (which already contains its heavy records and extra substeps),
    both per million particles, growth 1.0-1.1 relative to DA1 [guess]."""
    nf = f_end - f_from + 1
    lo = GC.COEF_LO * n * GC.GROWTH_LO / 1e6 * nf / 3600.0
    hi = GC.COEF_HI * n * GC.GROWTH_HI / 1e6 * nf / 3600.0
    rec_h = heavy * GC.R5_S_PER_FRAME / 3600.0
    out = dict(frames=nf, heavy_frames=heavy, solve_h_lo=lo, solve_h_hi=hi, records_h=rec_h, total_h_lo=lo + rec_h, total_h_hi=hi + rec_h,
               coef=[GC.COEF_LO, GC.COEF_HI], growth=[GC.GROWTH_LO, GC.GROWTH_HI])
    d = da1_phases()
    if "pre_s_per_Mp_frame" in d and "break_s_per_Mp_frame" in d:
        fb = int(round(t_break * GC.FPS)) + 1
        n_pre = max(0, min(f_end, fb) - f_from + 1); n_brk = nf - n_pre
        base = n / 1e6 * (n_pre * d["pre_s_per_Mp_frame"] + n_brk * d["break_s_per_Mp_frame"]) / 3600.0
        out.update(da1_two_phase_h=[base, base * 1.1], da1_rates=dict(pre=d["pre_s_per_Mp_frame"], brk=d["break_s_per_Mp_frame"]), t_break_s=t_break)
    out["bound_h"] = max(out["total_h_hi"], (out.get("da1_two_phase_h") or [0, 0])[1])
    return out


# ====================================================================== cfg
def heavy_frames(c, f_from):
    rec = c["records"]
    ev = max(1, min(int((rec.get("r4") or {}).get("every", 1)), int((rec.get("r5") or {}).get("every", 1))))
    wins = rec.get("windows") or []
    n = 0
    for f in range(f_from, int(c["f_end"]) + 1):
        t = (f - 1) / 24.0
        if (not wins or any(a - 1e-9 <= t <= b + 1e-9 for a, b in wins)) and (f - 1) % ev == 0:
            n += 1
    return n


def table_for(case):
    p, sha, ch, info = TB.write(case)
    return dict(case=case, npz=p, npz_sha256=sha, content_sha256=ch, T=info["T"], omega=info["omega"], theta_max_deg=info["theta_max_deg"],
                n=info["n"], weight=info["weight"], a_sum=info["a_sum"], a_j=info["a_j"], x_f=info["x_f"], t_f=info["t_f"],
                grid=dict(x=[info["x0"], info["x1"]], y=[info["y0"], info["y1"]], d=info["dx"]), fields=info["fields"])


def gauges_lin(case):
    """linear target wave height 2|A| at the gauges (generation report) [computed]."""
    tab = TB.load(TB.write(case)[0])
    out = {}
    for xg in GC.GAUGE_X:
        for yg in GC.GAUGE_Y:
            a = complex(TB._bilinear(tab, "er", xg, yg), TB._bilinear(tab, "ei", xg, yg))
            out["x%g_y%g" % (xg, yg)] = dict(x=xg, y=yg, H_lin=2.0 * abs(a), phase_rad=float(np.angle(a)))
    return out


def parms_D(dp, W, ramp, smoke=False):
    GC.check_dp(dp, smoke=smoke)
    b = GC.box48(dp, Lx=GC.LX, W=W, zb=GC.ZB, floor_pad=2)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=min(b["W"], GC.SD0),
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=0.0, sf_on=0.0, dir_on=1.0, dir_tf=0.0, ret_on=1.0, sd_on=1.0, sd0=b["W"] - GC.SD_BAND, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW,
             sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW, sd_taper_m=GC.SD_TAPER, sd_gain=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=float(ramp),
             wall_taper_m=GC.WALL_TAPER, in_gain=1.0, x_p=GC.X_P, xg_end=GC.IN_X1, xa0=1e9, abs_sigma=GC.SD_SIGMA, abs_pow=2.0,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=1.0,
             volcorr_on=0.0, vol_x0=GC.VOL_X[0], vol_x1=GC.VOL_X[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(GC.SPEC_D19B))
    return p, b


def analysis_block(case=None, strip=False):
    a = dict(layout="D", p1_x_max_m=GC.X_P1_MAX, crest_x_min_m=GC.X_CREST_MIN, crest_window="centre_half_L", side_band_m=list(GC.SIDE_BAND),
             vol_x_m=list(GC.VOL_X), report_levels=list(GC.LAYOUT_D["report_levels"]), setup_region="swash", plan_frozen=GC.PLAN_D_REL,
             x_toe_m=GC.X_TOE, x_f_m=GC.X_F, x_break_target_m=GC.X_BREAK, x_shore_m=GC.X_SHORE,
             rip_sections=dict(centre="r2 (y 0)", side="r3 (y %g m)" % GC.R3_Y, x_m=[200.0, 230.0, 260.0, 300.0]),
             c_in_rule="c_in = lateral mean over |y| <= 95 m of the per-row incident crest at x 128 m in [t_on - T, t_on] (hf records)")
    if not strip:
        a["yfar_m"] = GC.YFAR          # g46 far row inside r4 (3D only; strips keep the default W - 1)
    if case and not strip:
        a["dir_case"] = case
    return a


def make_3d(run_id, case, dp, t_end, kind="3d", heavy="cont", ret=1.0, out_root="runs", judged=True, note="", windows=None):
    C = GC.CASES[case]
    p, b = parms_D(dp, GC.W_MAIN, C["ramp_s"], smoke=(kind == "smoke"))
    p["ret_on"] = float(ret)
    vox = b["vox"]
    f_end = GC.frames_for(0.0, t_end)
    if windows is None:
        windows = [[HEAVY_CONT["t0"], float(t_end)]]
    rec = dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
               r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=-10.0, y1=16.0, clip_vox=6.0, t0=0.0, every=HEAVY_CONT["every"]),
               r5=dict(t0=0.0, every=HEAVY_CONT["every"]), windows=windows)
    tb = table_for(case)
    gl = gauges_lin(case)
    H_ref = gl["x%g_y%g" % (GC.GAUGE_X[0], GC.GAUGE_Y[0])]["H_lin"]
    sf = GC.sf_descriptor(C["T"], H_ref, note="option D: the inflow is the directional table cfg dir; this descriptor is for T, L, c, k only")
    c = dict(
        run_id=run_id, out_root=out_root, stage="FLIP50", kind=kind,
        case=dict(name="FLIP50_%s_D19B_%s" % (kind, case), plan_frozen=GC.PLAN_D_REL,
                  plan="Unity/Build/FLIP50/plan/plan_D_frozen.json (design, criteria, decision_rules, honesty)", campaign="PER50-D",
                  queue_id=run_id.split("_")[0], judged=bool(judged), P1_x_max_m=GC.X_P1_MAX, dir_case=case),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_D19B, b),
        sf=sf, dir=dict(tb, ret_on=float(ret), gauges_lin=gl),
        wave=dict(kind="linear directional monochromatic sea: %d Airy components, +-%g deg, equal amplitudes, phases 0 at (x_f, 0) at t = t_f + nT"
                       % (C["n"], C["theta_max_deg"]),
                  T_s=C["T"], H_m=None, theta_max_deg=C["theta_max_deg"], n_components=C["n"], a_sum_m=C["a_sum"], a_component_m=C["a_sum"] / C["n"],
                  x_f_m=C["x_f"], t_f_s=C["t_f"], focal_crest_linear_m=None, in_gain=1.0, sd_gain=1.0, ramp_s=C["ramp_s"],
                  in_gain_source="1.0 [chosen; FLIP49 100 m inlet band measured -2.1 % at T 12 s]; checked, not tuned (SMOKE_D, DM1 generation report)",
                  tags=dict(T="chosen", theta_max="chosen", a_sum="computed from the chosen gamma_b rule", x_f="chosen", table="computed (g50_table)")),
        drift=dict(stage="C", tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE), solver=dict(veltransfer="flip", donarrowband=0), records=rec,
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_D],
        dir_check=dict(every=120, x=[10.0, 40.0, 70.0, 95.0, 150.0, 200.0], y=[-15.0, -8.0, -2.0], zl=[0.5 * vox, 50.0, 100.0, 120.0]),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0,
        max_hours=(GC.LIMIT_D_H if (kind == "3d" and dp == 0.5) else 0.75), level_box=[0.0, b["Lx"], 0.0, b["W"]],
        n1_x=list(GC.N1_X), n1_window=[0.5, 1.5], shore_x=GC.X_SHORE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)], note=note,
        layout="D", analysis=analysis_block(case))
    return c


def make_strip(run_id, T):
    import x50_build as XB
    p, b = parms_D(0.5, GC.W_STRIP, GC.RAMP_S[T])
    p.update(dir_on=0.0, ret_on=0.0, sd_on=0.0, sf_on=1.0, crop_z1=b["W"])
    sp, H = XB.sf_table_h19(T)
    sf = json.load(open(sp, encoding="utf8"))
    t_end = S2D_T_END[T]
    f_end = GC.frames_for(0.0, t_end)
    vox = b["vox"]
    rec = dict(r2=True, r3_z=b["W"] - 0.5 * vox, block=120, r4_block=24, preg_every=24,
               r4=dict(x=list(GC.R4_X), z1=b["W"], y0=-10.0, y1=16.0, clip_vox=6.0, t0=0.0), r5=dict(t0=0.0, every=1), windows=[[40.0, float(t_end)]])
    c = dict(
        run_id=run_id, out_root="strips", stage="FLIP50", kind="axis_strip",
        case=dict(name="FLIP50_axis_strip_D19B_T%g" % T, plan_frozen=GC.PLAN_D_REL, plan="Unity/Build/FLIP50/plan/plan_D_frozen.json", campaign="PER50-D",
                  queue_id="S2D", judged=False, P1_x_max_m=GC.X_P1_MAX,
                  s2d_rule="if T 12 s spills (chord < 55 deg on >= 2 breakers) and T 10 s does too, D is unlikely to give P5: show the user before DM1"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_D19B, b),
        sf=sf, dir=None,
        wave=dict(kind="stream-function regular wave (Fenton, zero mean mass flux) at h0 19 m", T_s=T, H_m=H, in_gain=1.0, x_p=GC.X_P, ramp_s=GC.RAMP_S[T],
                  in_gain_source="1.0 [chosen; not calibrated at h0 19 m: the gauges report H]", H_rule="0.83 Hmax2D [chosen in the plan]",
                  tags=dict(T="chosen", H="chosen", sf="computed (g47_sfwave)")),
        drift=dict(stage="C", tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE), solver=dict(veltransfer="flip", donarrowband=0), records=rec,
        gauges=dict(x=list(GC.GAUGE_X), y=[0.5]), level_regions=[list(r) for r in GC.LEVEL_REGIONS_STRIP],
        sf_check=dict(every=120, x=[10.0, 40.0, 70.0, 95.0], y=[-15.0, -8.0, -2.0], zl=[0.5 * vox]),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0,
        max_hours=0.5, level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_X), n1_window=[0.5, 1.5], shore_x=GC.X_SHORE,
        fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note="FLIP50 S2D: 2D strip on the D19B axis (1:10 beach, h0 19 m), Fenton inlet T %g s H %.3f m (0.83 Hmax2D). Checks whether the straight "
             "1:10 section plunges at this period (chord/lip/hood per breaker); not judged on P2-P4 (strip)" % (T, H),
        layout="D", analysis=analysis_block(strip=True))
    return c


def precheck(c):
    """precheck of a FLIP50 cfg (numpy only)."""
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", wall="computed (FLIP48 coefficients and DA1 launch rates)"))
    ck = out["checks"]
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), float(P["dp"]), zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V))
    strip = c["kind"] == "axis_strip"
    key = ("strip" if strip else "3d", float(P["dp"]))
    ck["particles_as_designed"] = bool(EXPECT_PARTICLES.get(key) == n)
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["zb"]) == GC.ZB and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0
                     and float(P["W"]) == (GC.W_STRIP if strip else GC.W_MAIN))
    ck["bed_is_D19B"] = bool(all((spec.get(k) == v) if not isinstance(v, float) else abs(float(spec.get(k)) - v) < 1e-12
                                 for k, v in GC.SPEC_D19B.items() if k in spec) and not GC.is_new(spec) and spec.get("k_end") is None)
    ck["bed_above_box_floor"] = bool(c["bed"].get("max_depth_m", 99.0) <= -float(P["zb"]) + 1e-6)
    gx = [float(v) for v in c["gauges"]["x"]]; gy = [float(v) for v in c["gauges"]["y"]]
    ck["inlet_before_gauges_before_toe"] = bool(float(P["xg_end"]) < min(gx) and max(gx) <= GC.X_TOE)
    ck["no_exit_band"] = bool(float(P["abs_on"]) == 0.0)
    ck["drift_stage_C"] = bool(c["drift"]["stage"] == "C" and float(P["duabs_on"]) == 1.0 and float(P["volcorr_on"]) == 0.0 and float(P["hold_on"]) == 0.0)
    regs = c.get("level_regions") or []
    ck["level_regions"] = bool(all(0.0 <= r[1] < r[2] <= float(P["Lx"]) for r in regs)
                               and all(nm in [r[0] for r in regs] for nm in ("band_core", "probe_c", "flat", "window", "swash", "asym_centre", "asym_side")))
    an = c.get("analysis") or {}
    ck["layout_D_named"] = bool(c.get("layout") == "D" and an.get("plan_frozen") == GC.PLAN_D_REL and (c.get("case") or {}).get("plan_frozen") == GC.PLAN_D_REL
                                and abs(float(an.get("p1_x_max_m", -1)) - GC.X_P1_MAX) < 1e-9 and abs(float((c.get("case") or {}).get("P1_x_max_m", -1)) - GC.X_P1_MAX) < 1e-9)
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in (c["records"].get("windows") or [])))
    if not strip:
        dr = c.get("dir") or {}
        ck["side_band"] = bool(float(P["sd_on"]) == 1.0 and abs(float(P["sd0"]) - (float(P["W"]) - GC.SD_BAND)) < 1e-9 and float(P["sd_gen"]) == GC.SD_GEN
                               and float(P["sd_sw"]) == GC.SD_SW and GC.SIDE_BAND[1] < float(P["sd0"]) and max(gy) < float(P["sd0"]))
        r4 = c["records"]["r4"]
        ck["r4_inside_interior"] = bool(float(r4["z1"]) <= float(P["sd0"]) + 1e-9 and GC.YFAR < float(r4["z1"]) and float(r4["x"][1]) >= GC.X_P1_MAX
                                        and float(r4["x"][0]) <= GC.X_F)
        ck["dir_on_sf_off"] = bool(float(P["dir_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and (c.get("sf") or {}).get("descriptor") is True)
        ok_tab = os.path.exists(dr.get("npz") or "") and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256")
        ck["table_file_sha"] = bool(ok_tab)
        C = GC.CASES.get(dr.get("case"), {})
        ck["table_is_case"] = bool(C and abs(dr.get("a_sum", 0) - C["a_sum"]) < 1e-12 and dr.get("T") == C["T"] and dr.get("x_f") == C["x_f"]
                                   and dr.get("n") == C["n"] and dr.get("theta_max_deg") == C["theta_max_deg"] and float(P["ramp_s"]) == C["ramp_s"])
        ck["table_covers_bands"] = bool(dr.get("grid", {}).get("x", [0, 0])[1] >= GC.SD_SW and dr.get("grid", {}).get("y", [0, 0])[1] >= float(P["W"]) - 1e-9)
        ck["sf_descriptor_T"] = bool(abs(float(c["sf"]["T"]) - float(dr.get("T", -1))) < 1e-12 and abs(float(c["sf"]["h"]) - GC.H0) < 1e-12)
    else:
        sf = c.get("sf") or {}
        ck["sf_depth_is_h0"] = bool(abs(float(sf.get("h", 0)) - float(P["h0"])) < 1e-9 and abs(float(sf.get("h", 0)) - GC.H0) < 1e-12)
        ck["sf_terms"] = bool(len(sf.get("E", [])) == len(sf.get("B", [])) + 1 and len(sf.get("B", [])) == GC.SF_N)
        ck["sf_below_0p9_Hmax"] = bool(float(sf.get("H_over_Hmax", 9.0)) <= 0.9)
        ck["strip_bands"] = bool(float(P["sf_on"]) == 1.0 and float(P["dir_on"]) == 0.0 and float(P["sd_on"]) == 0.0)
    f_from = int(c.get("f_resume_est", c.get("f_start", 1)))
    heavy = heavy_frames(c, f_from)
    if c["kind"] == "3d" and float(P["dp"]) == 0.5:
        te = time_estimate(n, f_from, int(c["f_end"]), heavy)
        out["time"] = te
        out["launches_est"] = "%d-%d launches of <= %d min" % (math.ceil(te["total_h_lo"] * 3600 / c["wall_limit_s"]),
                                                               math.ceil(te["bound_h"] * 3600 / c["wall_limit_s"]), round(c["wall_limit_s"] / 60))
        ck["wall_le_limit"] = bool(te["bound_h"] <= GC.LIMIT_D_H)
        out["limit_h"] = GC.LIMIT_D_H
        out["note_h_wall"] = "the frozen criteria (copied from plan A) still judge H_wall at 2.5 h; the cfg max_hours is the task budget 3.0 h"
    elif c["kind"] == "smoke":
        nf = int(c["f_end"]) - f_from + 1
        h = [GC.COEF_DP1 * n * g / 1e6 * nf / 3600.0 for g in (1.1, 1.3)]
        out["time"] = dict(frames=nf, est_h=h, rule="D0 dp 1.0 rate %.2f s per Mp per frame x growth 1.1-1.3 [measured rate, guessed growth]" % GC.COEF_DP1)
        ck["smoke_one_launch"] = bool(h[1] * 3600.0 <= c["wall_limit_s"])
    else:
        nf = int(c["f_end"]) - f_from + 1
        out["time"] = dict(frames=nf, est_h=[STRIP_S_PER_FRAME * nf / 3600.0 * 0.8, STRIP_S_PER_FRAME * nf / 3600.0 * 1.3],
                           rule="FLIP49 S1 strip %.2f s/frame x 0.8-1.3 [measured, scaled]" % STRIP_S_PER_FRAME)
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    return out


def preset(name, opt):
    heavy = opt.get("heavy", "cont")
    ret = float(opt.get("ret", "1"))
    sfx = "" if ret == 1.0 else "_ret0"
    if name == "SMOKE_D":
        c = make_3d("SMOKE50D_D19B_T12_dp1p0" + sfx, "DM1", 1.0, SMOKE_T_END, kind="smoke", ret=ret, out_root="smoke", judged=False,
                    windows=[list(SMOKE_WINDOW)],
                    note="FLIP50 option D smoke (never judged): 3D dp 1.0, W 140, D19B, DM1 sea (T 12 s, +-80 deg), 0-48 s, one launch. Checks the "
                         "pipeline (table load, side band, stage C files, records incl. heavy r4/r5 every 2nd frame in 36-48 s, dir_check), leaks, and "
                         "that the generated pattern at x 160 m correlates with the linear target >= 0.9 over |y| <= 95 m (g50_ana.py smoke)")
        c["records"]["r4"]["every"] = 2; c["records"]["r5"]["every"] = 2
        c["dir_check"]["every"] = 48
        c.update(max_hours=0.75)
    elif name in ("DM1", "DF1"):
        C = GC.CASES[name]
        win = None
        wsrc = "heavy records continuously from %g s to the end every %d frames (AM-A2 precedent)" % (HEAVY_CONT["t0"], HEAVY_CONT["every"])
        if heavy == "screen":
            scr = json.load(open(GC.SCREEN_FINAL, encoding="utf8"))["configs"][C["screen_key"]]["time"]
            ons = list(scr["judged_onsets_screen"])
            while ons[-1] + C["T"] + 4.0 <= C["t_end"]:
                ons.append(round(ons[-1] + C["T"], 3))
            win = [[round(t - 3.0, 3), round(min(t + 4.0, C["t_end"]), 3)] for t in ons]
            wsrc = "screen windows (U3 onsets %s, +T extrapolated) [-3, +4] s, every 2nd frame" % ons
        elif heavy != "cont":
            raise SystemExit("--heavy is cont (default) or screen")
        c = make_3d("%s_D19B_T%s_th80_dp0p5%s" % (name, GC.tag(C["T"]), sfx), name, 0.5, C["t_end"], kind="3d", ret=ret, windows=win,
                    note="FLIP50 option D %s (%s): 3D dp 0.5 (5.38 M), half tank W 140 with a 45 m side band, D19B (h0 19 m, 1:10 beach, toe 160.25 m), "
                         "directional sea T %g s, +-80 deg, 30 equal components, a_sum %.3f m, focus (220.25, 0), stage C, %g s. %s"
                         % (name, C["tag"], C["T"], C["a_sum"], C["t_end"], wsrc))
        c["case"]["heavy_rule"] = heavy
        c["case"]["windows_source"] = wsrc
        if heavy == "screen":
            c["records"]["r4"]["every"] = 2; c["records"]["r5"]["every"] = 2
    elif name in ("S2D_T12", "S2D_T10"):
        T = 12.0 if name.endswith("12") else 10.0
        c = make_strip("S2D_D19B_axis_T%s_H0p83max" % GC.tag(T), T)
    elif name == "DD3":
        rd = opt.get("run")
        if not rd or not os.path.exists(os.path.join(rd, "cfg.json")):
            raise SystemExit("DD3 needs --run=<DM1 or DF1 run folder with cfg.json>")
        c0 = json.load(open(os.path.join(rd, "cfg.json"), encoding="utf8"))
        if c0.get("layout") != "D" or c0.get("kind") != "3d":
            raise SystemExit("DD3 continues a FLIP50 option D 3D run only")
        c = copy.deepcopy(c0)
        for k_ in ("hip_sha256", "module_shas_at_chain_start", "precheck"):
            c.pop(k_, None)
        t3 = float(c0["t_end_s"]) + DD3_EXTRA_S
        c["f_resume_est"] = int(c0["f_end"]) + 1
        c["f_end"] = GC.frames_for(0.0, t3); c["t_end_s"] = t3
        w = c["records"].get("windows") or []
        if w and abs(w[-1][1] - float(c0["t_end_s"])) < 1e-9:
            w[-1][1] = t3
        else:
            w.append([float(c0["t_end_s"]), t3])
        c["records"]["windows"] = w
        c["case"]["queue_id"] = "DD3"; c["case"]["continuation_of"] = c0["run_id"]
        c["max_hours"] = 2.0          # +48 s at the DA1 breaking-phase rate (~4.7 s/frame) is ~1.5 h [measured rate]
        c["note"] = c0.get("note", "") + " | DD3: same settings resumed from the last checkpoint to %g s (+48 s = 4 T at 12 s); closed-tank drift after ~100 s is expected" % t3
        c["pstats_frames"] = sorted(set(c.get("pstats_frames", []) + [c["f_end"]]))
    else:
        raise SystemExit("cfg presets: SMOKE_D, DM1, DF1, S2D_T12, S2D_T10, DD3")
    c["precheck"] = precheck(c)
    return c


def write(c):
    p = os.path.join(GC.B50, c["out_root"], "ready", c["run_id"] + ".json").replace("\\", "/")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(c, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    return p


# ====================================================================== freeze
def freeze(force=False, reason=None):
    if not os.path.exists(GC.PLAN_DRAFT):
        raise SystemExit("no draft %s (py -3.10 -B g50_planD.py)" % GC.PLAN_DRAFT)
    runs = [p for p in glob.glob(os.path.join(GC.B50, "runs", "*", "run.json"))]
    if os.path.exists(GC.PLAN_FROZEN_D):
        if runs:
            raise SystemExit("plan_D_frozen.json exists and FLIP50 3D runs have records (%d): never re-frozen" % len(runs))
        if not force or not reason:
            raise SystemExit("plan_D_frozen.json exists; re-freeze only with --force=1 --reason=... before any FLIP50 3D run")
    d = json.load(open(GC.PLAN_DRAFT, encoding="utf8"))
    d["status"] = "FROZEN"
    d["frozen_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    d["frozen_from"] = dict(path="Unity/Build/FLIP50/plan/plan_D_draft.json", sha256=GC.sha256_file(GC.PLAN_DRAFT))
    if reason:
        d.setdefault("refrozen", []).append(dict(at=d["frozen_at"], reason=reason))
    json.dump(d, open(GC.PLAN_FROZEN_D, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    sha = GC.sha256_file(GC.PLAN_FROZEN_D)
    open(GC.PLAN_FROZEN_D + ".sha256", "w", encoding="utf8").write("%s  plan_D_frozen.json\n" % sha)
    return dict(frozen=GC.PLAN_FROZEN_D, sha256=sha)


# ====================================================================== numpy check of the whole set-up
def checks():
    t0 = time.time()
    o = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50/g50_pcfg.py check", module_shas=GC.module_shas())
    ok = {}
    # 1. tables
    for case in ("DM1", "DF1"):
        r = TB.checks(case)
        o["table_" + case] = r
        ok["table_" + case] = r["all_ok"]
    # 2. constants = the design screen and the design draft
    scr = json.load(open(GC.SCREEN_FINAL, encoding="utf8"))
    cons = {}
    for case, C in GC.CASES.items():
        w = scr["configs"][C["screen_key"]]["wave"]; t = scr["configs"][C["screen_key"]]["time"]
        cons[case] = dict(a_sum=bool(w["a_sum_m"] == C["a_sum"]), T=bool(w["T"] == C["T"]), theta=bool(w["theta_max_deg"] == C["theta_max_deg"]),
                          n=bool(w["n_components"] == C["n"]), x_f=bool(w["focus"]["x_f"] == C["x_f"]), ramp=bool(w["ramp_s"] == C["ramp_s"]),
                          t_end=bool(t["t_end_s"] == C["t_end"]))
    lay = scr["layout"]
    cons["layout"] = dict(Lx=bool(lay["Lx"] == GC.LX), W=bool(lay["W"] == GC.W_MAIN), side_band=bool(lay["side_band"] == GC.SD_BAND),
                          x_gen=bool(lay["x_gen"] == GC.SD_GEN), x_sw=bool(lay["x_sw"] == GC.SD_SW), inlet=bool(lay["inlet"] == [0.0, GC.IN_X1]),
                          wall_taper=bool(lay["wall_taper"] == GC.WALL_TAPER), shoreline=bool(lay["shoreline_x"] == GC.X_SHORE))
    cons["bed"] = dict(h0=bool(scr["bed"]["h0"] == GC.H0), x_toe=bool(scr["bed"]["x_toe"] == GC.X_TOE), s=bool(scr["bed"]["s"] == GC.SLOPE_S),
                       kind=bool(scr["bed"]["kind"] == "beach"))
    o["constants_vs_screen"] = cons
    ok["constants_vs_screen"] = bool(all(all(v.values()) for v in cons.values()))
    # 3. bed
    xq = np.arange(0.0, GC.LX, 0.37); yq = np.arange(0.0, GC.W_MAIN, 0.41)
    Z = GC.bed_z(xq[None, :], yq[:, None], **GC.SPEC_D19B)
    o["bed"] = dict(equals_analytic_bit=bool(np.array_equal(Z[0], -(GC.H0 - np.maximum(xq - GC.X_TOE, 0.0) / GC.SLOPE_S))),
                    laterally_uniform=bool(np.all(Z == Z[0][None, :])), g48_plain_path=bool(not GC.is_new(GC.SPEC_D19B)),
                    still_level_x=float(GC.X_TOE + GC.H0 * GC.SLOPE_S), top_at_Lx=float(GC.bed_z(GC.LX, 0.0, **GC.SPEC_D19B)),
                    grad_on_slope=[float(v) for v in GC.bed_grad(300.0, 10.0, **GC.SPEC_D19B)], kind=GC.bed_kind(GC.SPEC_D19B))
    ok["bed"] = bool(o["bed"]["equals_analytic_bit"] and o["bed"]["laterally_uniform"] and o["bed"]["g48_plain_path"]
                     and abs(o["bed"]["top_at_Lx"] - 6.175) < 1e-9 and abs(o["bed"]["grad_on_slope"][0] - 0.1) < 1e-12 and o["bed"]["grad_on_slope"][1] == 0.0)
    # 4. particle-count model
    pc = {}
    for (kind, dp), exp in EXPECT_PARTICLES.items():
        W = GC.W_STRIP if kind == "strip" else GC.W_MAIN
        b = GC.box48(dp, Lx=GC.LX, W=W, zb=GC.ZB, floor_pad=2)
        n, V = GC.count_particles(GC.SPEC_D19B, b["Lx"], b["W"], dp, zb=GC.ZB, bed_gap=0.5)
        # independent: per column count of layers zb + (k + 1/2) dp in [bed + dp/2, 0)
        xs = (np.arange(int(round(b["Lx"] / dp))) + 0.5) * dp
        bed = -(GC.H0 - np.maximum(xs - GC.X_TOE, 0.0) / GC.SLOPE_S)
        lay_ = GC.ZB + (np.arange(int(round((0.0 - GC.ZB) / dp)) + 1) + 0.5) * dp
        per = ((lay_[None, :] >= bed[:, None] + 0.5 * dp) & (lay_[None, :] < 0.0)).sum(1)
        n2 = int(per.sum()) * int(round(b["W"] / dp))
        pc["%s_dp%s" % (kind, GC.tag(dp))] = dict(model=n, independent=n2, expected=exp, W=b["W"], water_m3=V, box=dict(Lx=b["Lx"], W=b["W"], Hz=b["Hz"], oy=b["oy"]))
    o["particles"] = pc
    ok["particles"] = bool(all(v["model"] == v["independent"] == v["expected"] for v in pc.values()))
    # 5. band numpy mirror behaviour (the build check compares the VEX with this mirror point by point)
    tab = TB.load(TB.write("DM1")[0])
    P, b = parms_D(0.5, GC.W_MAIN, 24.0)
    beh = {}
    v0 = (0.7, -0.3, 0.4)
    pts = [(x, zl) for x in (1.0, 50.0, 99.9, 100.1, 150.0, 179.0, 195.0, 215.0, 300.0) for zl in (0.5, 50.0, 94.9, 95.1, 120.0, 139.9)]
    vs = {pt: TB.relax_np((pt[0], -3.0, pt[1]), v0, 40.0, 1.0 / 24.0, P, tab=tab, du_abs=0.0) for pt in pts}
    beh["vertical_unchanged"] = bool(all(abs(v[1] + 0.3) < 1e-15 for v in vs.values()))
    beh["interior_untouched"] = bool(all(np.allclose(vs[(x, zl)], v0) for (x, zl) in pts if x > 100.0 and zl < 95.0))
    beh["side_absorbs_beyond_sd_sw"] = bool(all(abs(vs[(x, zl)][2]) < 0.4 for (x, zl) in pts if x >= 215.0 and zl >= 120.0))
    w_in = [TB.bands_np(x, 10.0, 1.0 / 24.0, P)[0] for x in (99.0, 99.9, 99.99)]
    beh["inlet_weight_to_zero_at_edge"] = bool(w_in[0] > w_in[1] > w_in[2] >= 0.0 and w_in[2] < 1e-6)
    s_gen = [TB.bands_np(x, 130.0, 1.0 / 24.0, P)[1] for x in (180.0, 180.25, 195.25, 210.25, 211.0)]
    beh["side_factor_blend"] = dict(values=s_gen, ok=bool(abs(s_gen[0] - 1) < 1e-12 and abs(s_gen[1] - 1) < 1e-12 and abs(s_gen[2] - 0.5) < 1e-12
                                                          and s_gen[3] == 0.0 and s_gen[4] == 0.0))
    t0v = TB.relax_np((50.0, -3.0, 10.0), v0, 0.0, 1.0 / 24.0, P, tab=tab)
    beh["ramp_zero_at_t0_target_zero"] = bool(abs(t0v[0] - 0.7 * (1 - TB.bands_np(50.0, 10.0, 1.0 / 24.0, P)[0])) < 1e-12)
    wt, ws = TB.tapers_np(50.0, 139.0, P)
    beh["outer_wall_taper"] = dict(at_139=ws, at_128p75=TB.tapers_np(50.0, 128.75, P)[1], ok=bool(ws < 0.05 and TB.tapers_np(50.0, 128.75, P)[1] == 1.0))
    o["band_mirror_behaviour"] = beh
    ok["band_mirror_behaviour"] = bool(beh["vertical_unchanged"] and beh["interior_untouched"] and beh["side_absorbs_beyond_sd_sw"]
                                       and beh["inlet_weight_to_zero_at_edge"] and beh["side_factor_blend"]["ok"] and beh["ramp_zero_at_t0_target_zero"]
                                       and beh["outer_wall_taper"]["ok"])
    # 6. ray aperture (how much of the focal amplitude starts in a generating band) [computed]
    ap = {}
    for case in ("DM1", "DF1"):
        df = TB.dirfield(case)
        r = DF.aperture(df, GC.W_MAIN, GC.SD_BAND, GC.IN_X1, GC.SD_GEN, GC.SD_SW)
        ap[case] = dict(frac=r["frac"], n_side_generated=sum(1 for q in r["comps"] if q["x_cross_side"] is not None))
    o["aperture"] = ap
    ok["aperture"] = bool(all(v["frac"] >= 0.95 for v in ap.values()))
    # 7. presets (written nowhere here)
    pre = {}
    for nm in ("SMOKE_D", "DM1", "DF1", "S2D_T12", "S2D_T10"):
        c = preset(nm, {})
        pre[nm] = dict(run_id=c["run_id"], ok=c["precheck"]["ok"], reason=c["precheck"]["reason"], particles=c["precheck"]["particles_model"],
                       time=c["precheck"].get("time"), launches=c["precheck"].get("launches_est"), f_end=c["f_end"],
                       heavy=heavy_frames(c, 1), windows=c["records"].get("windows"))
    o["presets"] = pre
    ok["presets"] = bool(all(v["ok"] for v in pre.values()))
    o["da1_phases"] = da1_phases()
    o["ok"] = ok
    o["all_ok"] = bool(all(ok.values()))
    o["cpu_s"] = round(time.time() - t0, 1)
    os.makedirs(GC.PLAN_DIR, exist_ok=True)
    p = GC.PLAN_DIR + "/precheck_D.json"
    json.dump(o, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    o["path"] = p
    return o


def summary(o):
    L = ["FLIP50 precheck_D all_ok %s (%.1f s) -> %s" % (o["all_ok"], o["cpu_s"], o["path"]), "ok: %s" % o["ok"]]
    for nm, v in o["presets"].items():
        t = v.get("time") or {}
        L.append("  %-8s %-34s ok %s particles %d frames %d heavy %d time %s %s %s" % (
            nm, v["run_id"], v["ok"], v["particles"], v["f_end"], v["heavy"],
            ("coef %.2f-%.2f h, DA1 2-phase %s h, bound %.2f h" % (t["total_h_lo"], t["total_h_hi"],
                                                                    [round(x, 2) for x in t.get("da1_two_phase_h", [])], t["bound_h"])) if "bound_h" in t
            else ("est %s h" % [round(x, 2) for x in t.get("est_h", [])]), v.get("launches") or "", v["reason"] or ""))
    for case in ("DM1", "DF1"):
        tc = o["table_" + case]
        L.append("  table %s: focus |A| %.3f m (theory %.3f, rel %.1e), continuity flat %.1e, interp %.1e, mean flux w/o return %.0f m3/s (half tank), "
                 "inlet-band return max %.3f m/s" % (case, tc["focus"]["abs_A"], tc["focus"]["theory_sum"], tc["focus"]["rel_err_vs_theory"],
                                                    tc["continuity"]["max_rel_residual_flat"], max(tc["interpolation"]["max_rel_eta"], tc["interpolation"]["max_rel_U"]),
                                                    tc["mean_mass_flux"]["per_x"]["x100"]["M_without_return_m3s"], tc["mean_mass_flux"]["inlet_band_return_mps"]["max"]))
    L.append("  aperture %s" % o["aperture"])
    return "\n".join(L)


def parse(argv):
    opt = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    pos = [a for a in argv if not a.startswith("--")]
    return pos, opt


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, opt = parse(sys.argv[1:])
    if not pos:
        print(__doc__); sys.exit(1)
    if pos[0] == "check":
        print(summary(checks()))
    elif pos[0] == "freezeD":
        print(freeze(force=bool(int(opt.get("force", "0"))), reason=opt.get("reason")))
    elif pos[0] == "cfg":
        names = pos[1:] or ["all"]
        if names == ["all"]:
            names = ["SMOKE_D", "DM1", "DF1", "S2D_T12", "S2D_T10"]
        for nm in names:
            c = preset(nm, opt)
            if not c["precheck"]["ok"]:
                print("NOT WRITTEN", c["run_id"], c["precheck"]["reason"])
                continue
            print("written", write(c), "f_end", c["f_end"], "particles", c["precheck"]["particles_model"],
                  {k: (round(v, 3) if isinstance(v, float) else v) for k, v in (c["precheck"].get("time") or {}).items()
                   if k in ("total_h_lo", "total_h_hi", "bound_h", "est_h", "da1_two_phase_h")})
    else:
        print(__doc__); sys.exit(1)
