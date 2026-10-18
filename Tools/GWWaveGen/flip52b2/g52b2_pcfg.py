# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3: the run configuration (cfg.json) with its precheck, the consistency check of every constant against the frozen plan,
and a dry copy of the g52b2_chain start gate (py -3.10 -B). 2026-10-18 written new (Claude) by adapting flip52b/g52b_pcfg.py (DFG-2B, frozen,
not edited). Reads only the frozen plan, the FLIP52B2 table, DFG-2B-E's launched cfg (Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json,
read only: every DFGB3 parm must equal it except the NAMED differences below) and DM1A's cfg (energy check). Writes only
Unity/Build/FLIP52B2/runs/ready/<run_id>.json and plan/precheck_DFGB3.json.

Preset (plan_DFGB3_frozen.json; nothing here is tuned):
  main   DFGB3_D19Bs3h6_xf272p25_dp0p5  dp 0.5, 0 - (t_f3 + 6) = 125 s, the judged run; r4 and r5 every 3rd frame in the three group windows
                                       [t_fn - 8, t_fn + 6] s; max_hours 3.5 per chain (a stop at max_hours is resumed from the last checkpoint by
                                       auto_DFGB3.py, up to 2 times), launches of <= 1740 s, checkpoints every 48 frames
The cfg = DFG-2B-E's launched cfg (half tank W 140 m, side band 95-140 m generating to 180.25 m / absorbing from 210.25 m, inlet band 0-100 m,
taper 20 m, Lx 412 m, z -19 .. +17 m, ramp 14 s, dir_tf 63 s, crop / surface parms, solver) with the named differences
  bed (the one physical change): shelf_h 0 -> 6, pg_hL 0 -> 11.5, pg_s2 0 -> 3 (1:10 to h 11.5 m at x 235.25 m, 1:3 to the 6 m shelf at 251.75 m)
  exit sponge (infrastructure, the shelf keeps water to the end wall): abs_on 0 -> 1, xa0 1e9 -> 332 m, abs_sigma 1.41 -> 1.0 (DFG-S's)
  stage A window: vol_x1 400 -> 327 m (outside the bands: 5 m before the sponge, the layout A rule)
and the DFGB3 generator table (DFG-2B-E's x exp(-i phi_n), calibration (b); dir_on 1, ret_on 1).
usage:
  py -3.10 -B g52b2_pcfg.py check [--dry]      plan consistency + precheck of main (writes plan/precheck_DFGB3.json; --dry: nothing)
  py -3.10 -B g52b2_pcfg.py cfg main           write runs/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B g52b2_pcfg.py gate <cfg.json>    the g52b2_chain start gate, dry (reads only) -> json
  py -3.10 -B g52b2_pcfg.py show main          print the cfg (not written)
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52b2_common as GC            # noqa: E402
import g52b2_table as TB             # noqa: E402

DFGBE_READY = GC.REPO + "/Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json"    # read only [the parms that ran DFG-2B-E]
PRESETS = {"main": 0.5}
T_END = {0.5: GC.FOCI[-1] + GC.GROUP_WIN[1]}
MAX_H = {0.5: 3.5}                   # hard cap per chain [chosen: the measured-rate estimate 2.6-3.0 h; DFG-2B-E took 2.38 h]
# run-time model [measured: DFG-2B-E 0.5 m, same tank, records and code: 5 launches, 8551 s for 3001 frames incl. relaunch overlap, model 5.384 M]
DFGBE_WALL_S = 8551.2
DFGBE_FRAMES = 3001
DFGBE_PART_MODEL = 5383840
PART_LIMIT_M = 7.0
DIR_CHECK = dict(every=120, x=[10.0, 40.0, 70.0, 95.0, 150.0, 200.0], y=[-15.0, -8.0, -2.0], zl=[0.5, 50.0, 100.0, 120.0])   # = DFG-2B-E cfg
PARMS_DIFFER_FROM_DFGBE = {"shelf_h": 6.0, "pg_hL": 11.5, "pg_s2": 3.0, "abs_on": 1.0, "xa0": 332.0, "abs_sigma": 1.0, "vol_x1": 327.0}
_ENERGY = None


# ====================================================================== the cfg
def parms_D(dp):
    GC.check_dp(dp, smoke=False)
    b = GC.box52(dp)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=GC.SD0,
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=GC.ABS_ON, sf_on=0.0, dir_on=1.0, dir_tf=GC.T_F, ret_on=1.0, sd_on=1.0, sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW,
             sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW, sd_taper_m=GC.SD_TAPER, sd_gain=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=GC.RAMP_S,
             wall_taper_m=GC.WALL_TAPER, in_gain=1.0, x_p=80.0, xg_end=GC.IN_X1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=0.0,
             volcorr_on=1.0, vol_x0=GC.VOL_X[0], vol_x1=GC.VOL_X[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(GC.SPEC_BED))
    return p, b


def drift_stage_A():
    return dict(stage="A", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE, window_m=list(GC.VOL_X),
                amendment="AM-D18 (as plan E X2 / DFG-2B-E); window 110-327 m (outside the exit sponge 332-412 m, the layout A rule)",
                rule="FLIP49 stage A: whole-tank column volume held by a target divergence in x %g-%g m (tau %g s, cap %g /s)"
                     % (GC.VOL_X[0], GC.VOL_X[1], GC.VOL_TAU, GC.VOL_DMAX))


def windows_for(t_end):
    return [[t + GC.GROUP_WIN[0], t + GC.GROUP_WIN[1]] for t in GC.FOCI if t + GC.GROUP_WIN[1] <= t_end + 1e-9]


def records(dp, t_end):
    return dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
                r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=GC.R4_Z[0], y1=GC.R4_Z[1], clip_vox=6.0, t0=0.0, every=3),
                r5=dict(t0=0.0, every=3), windows=windows_for(t_end))


def energy_block():
    """the Q84 energy statement carried by the cfg (and copied by g52b2_ana into the judge and the co-equal verdict)."""
    global _ENERGY
    if _ENERGY is None:
        E = TB.energy_in_tank()
        C = GC.components()
        D = E.get("DM1A") or {}
        _ENERGY = dict(statement=GC.sea_text(), basis="equal spectral energy (Q84): energy density 0.5 rho g sum a^2 of the incoming components at "
                                                         "the generation depth h0 19 m (= DM1A's generation depth)",
                       sum_a2_m2=float(np.sum(C["a"] ** 2)), DM1A_sum_a2_m2=GC.DM1A_SUM_A2, spectral_ratio=E["spectral"]["ratio"],
                       scale_vs_DFGB_frozen=GC.E_SCALE, a_sum_m=GC.A_SUM, a_max_component_m=float(C["a"].max()), DM1A_a_j_m=GC.DM1A_AJ,
                       phase_compensation="|exp(-i phi_n)| = 1: spectral energy and the period-mean in-tank power are DFG-2B-E's",
                       in_tank=dict(inlet_variance_over_DM1A=E["DFGB3"].get("inlet_variance_over_DM1A"),
                                    interior_power_over_DM1A=E["DFGB3"].get("interior_power_over_DM1A"),
                                    inlet_Hm0_equiv_m=E["DFGB3"]["inlet_band_Hm0_equiv_m"], DM1A_inlet_Hm0_equiv_m=D.get("inlet_band_Hm0_equiv_m"),
                                    power_into_interior_MW=E["DFGB3"]["power_into_interior_MW"], DM1A_power_into_interior_MW=D.get("power_into_interior_MW"),
                                    equals_DFGB_E=E.get("DFGB3_equals_DFGB_E_power"), reproduces_AM_DFGB1b=(E.get("reproduces_AM_DFGB1b") or {}).get("ok"),
                                    rule="g52b2_table.energy_in_tank (the AM-DFGB1b rule on the D19B layout: x 100 m, y 95 m, side band to 180.25 m) [computed]"),
                       statement_in_tank=E["statement_en"])
    return _ENERGY


def time_estimate(c, n_model):
    nf = int(c["f_end"]) - int(c.get("f_start", 1)) + 1
    s = DFGBE_WALL_S * (nf / float(DFGBE_FRAMES)) * (float(n_model) / DFGBE_PART_MODEL)
    nl = int(math.ceil(s / c["wall_limit_s"]))
    return dict(frames=nf, launches=[nl, nl + 1], est_h=[s / 3600.0, (1.12 * s + 60.0 * (nl + 1)) / 3600.0],
                rule="DFG-2B-E 0.5 m (same tank, records, code; %.0f s for %d frames incl. relaunch overlap) x frames x particle ratio %.4f (the shelf "
                     "adds water); high = x 1.12 + 60 s per launch [measured rate, guessed margin]" % (DFGBE_WALL_S, DFGBE_FRAMES, float(n_model) / DFGBE_PART_MODEL))


def make(preset="main", dry=False):
    dp = PRESETS[preset]
    p, b = parms_D(dp)
    t_end = T_END[dp]
    f_end = GC.frames_for(0.0, t_end)
    tb = TB.table_record(dry=dry)
    rid = GC.run_id("main")
    lr = tb["linear_refs"]
    g0 = lr["G2f_gauges"]["A_n"]["y0.5"]
    H_ref = 2.0 * sum(math.hypot(*v) for v in g0.values())
    en = energy_block()
    c = dict(
        run_id=rid, out_root=GC.RUNS_ROOT, stage="FLIP52B2", kind="3d",
        case=dict(name="FLIP52B2_main_%s_D19Bs3h6_dp%s" % (GC.SET, GC.tag(dp)), plan_frozen=GC.PLAN_REL,
                  plan="Unity/Build/FLIP52B2/plan/plan_DFGB3_frozen.json (sea, calibration, tank, bed, records, co-equal criteria incl. 3b / 3c, gates, "
                       "decision, honesty)", campaign="FLIP52B2-DFGB3", preset=preset, set=GC.SET, role="the judged DFGB3 run (DFG-2B round 2)",
                  judged=True, pipeline_check_only=False, P1_x_max_m=330.0, dir_case="DFGB3",
                  label=("DFG-2B-E sea (P 28 s, T 9.33/7/5.6 s, X2 directions, spectral energy = DM1A) with the generator phase calibration, on the "
                         "DFGB3 bed: 1:10 to h 11.5 m at x %.2f m, 1:3 to a 6 m shelf at x %.2f m; design phase reference (%.2f, 0)" % (GC.X_FOOT, GC.X_EDGE, GC.X_F)),
                  reference_cfg="Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json (parms equal except %s)" % ", ".join(
                      "%s %g" % kv for kv in PARMS_DIFFER_FROM_DFGBE.items()),
                  a_sum_tag=GC.sea_text() + " [chosen]"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_BED, b),
        sf=GC.sf_descriptor(H_ref=H_ref, note="FLIP52B2: the inflow is the N-layer table cfg dir (P 28 s, n 3/4/5); this descriptor (T 7 s, h0 19 m) "
                                               "is for T, L, c, k only; H = 2 x the sum of the linear per-frequency DESIGN amplitudes at (110, 0.5) m"),
        dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear periodic multi-frequency directional sea (WKB over D19B, = DFG-2B-E's) with a per-layer generator phase calibration: "
                       "%d components (3 harmonics of P = 28 s x %d directions), design phases 0 at (x_f, 0) at t = t_f + 28 m; generator layer n x "
                       "exp(-i phi_n)" % (tb["n_components"], len(tb["theta_deg"])),
                  P_s=GC.P_S, harmonics=list(GC.HARMONICS), T_s=tb["T"], freq_weights=tb["freq_weights"], theta_deg=tb["theta_deg"],
                  dir_weights=tb["dir_weights"], dspec=list(GC.DSPEC), a_sum_m=tb["a_sum"], a_component_max_m=tb["a_max_component"],
                  amp_per_freq_m=tb["amp_per_freq"], x_f_m=GC.X_F, h_f_design_m=tb["h_f_design"], h_f_bed_m=GC.h_of(GC.X_F), t_f_s=GC.T_F,
                  foci_s=list(GC.FOCI), in_gain=1.0, sd_gain=1.0, ramp_s=GC.RAMP_S, focal_crest_linear_m=lr["design_crest_xf_m"],
                  phase_comp_rad=dict(GC.PHI_COMP), phase_comp_rule=GC.PHI_RULE, energy=en,
                  chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and weights, a_sum %.6f m (spectral energy "
                                  "= DM1A, AM-DFGB1), the design phase reference (%.2f, 0) at t = %.0f + 28 m s, the generator phase calibration phi "
                                  "%s rad (measured on DFG-2B-E), the D19B tank and its option-D bands, the DFGB3 bed and the exit sponge [chosen]; "
                                  "computed by FLIP: propagation, dispersion, refraction, shoaling, focusing, reflection at the face, the crest's growth, "
                                  "breaking, any jet / plume" % (GC.A_SUM, GC.X_F, GC.T_F, GC.PHI_COMP),
                  tags=dict(P="chosen", harmonics="chosen", weights="chosen", directions="chosen", a_sum="chosen (spectral energy = DM1A, AM-DFGB1)",
                            x_f="chosen (= DFG-2B-E's design phase reference)", t_f="computed (ray arrival + 3.9 s, = DFG-2B-E)",
                            phase_comp="calibrated (DFG-2B-E G2f phases)", bed="chosen (round-2 design (c))", table="computed (g52b2_table)")),
        drift=drift_stage_A(), solver=dict(veltransfer="flip", donarrowband=0), records=records(dp, t_end),
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_52B2],
        dir_check=copy.deepcopy(DIR_CHECK), ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740,
        level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0, max_hours=MAX_H[dp], level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_STILL_X),
        n1_window=[0.5, 1.5], shore_x=GC.X_EDGE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP52B2 DFGB3 (DFG-2B round 2) main: 3D dp %g, the D19B tank of DFG-2B-E (half tank W 140 m, side band 95-140 m, h0 19 m) with the "
              "DFGB3 bed (1:10 from x 160.25 m to h 11.5 m at x %.2f m, then 1:3 to a 6 m shelf at x %.2f m, shelf to x 412 m) and an exit sponge "
              "332-412 m; the DFG-2B-E sea (%s) with the generator phase calibration phi %s rad; design phase reference (%.2f, 0) at t = %s s; ramp "
              "14 s, stage A (110-327 m), 0-%g s. Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in the three group windows [t_fn - 8, "
              "t_fn + 6] s" % (dp, GC.X_FOOT, GC.X_EDGE, GC.sea_text(), GC.PHI_COMP, GC.X_F, " / ".join("%g" % t for t in GC.FOCI), t_end)),
        layout="D",
        analysis=dict(layout="D", p1_x_max_m=330.0, crest_x_min_m=150.0, crest_window="centre_half_L", side_band_m=[70.0, 84.0], vol_x_m=list(GC.VOL_X),
                      report_levels=["break_front", "inner_surf", "swash", "side_surf"], setup_region="swash", plan_frozen=GC.PLAN_REL,
                      x_toe_m=GC.X_TOE, x_foot_m=GC.X_FOOT, x_edge_m=GC.X_EDGE, x_f_m=GC.X_F, x_shore_m=None, yfar_m=90.0, dir_case="DFGB3",
                      foci_s=list(GC.FOCI), P_s=GC.P_S, group_window_s=list(GC.GROUP_WIN), tool="Tools/GWWaveGen/flip52b2/g52b2_ana.py"))
    c["precheck"] = precheck(c)
    return c


# ====================================================================== checks
def plan_consistency():
    if not os.path.exists(GC.PLAN):
        return dict(ok=False, checks=dict(plan_exists=False))
    pl = GC.plan()
    T = pl["tank"]; S = pl["sea"]; R = pl["records"]; K = pl["calibration"]
    ck = {}
    ck["plan_sha256"] = GC.plan_sha_ok()
    Bd = T["bed"]
    ck["tank"] = bool(T["h0_m"] == GC.H0 and T["Lx_m"] == GC.LX and T["W_m"] == GC.W_MAIN and T["z_bed_m"] == GC.ZB and T["z_top_m"] == GC.Z_TOP
                      and T["solver"]["gridscale"] == 2.0 and T["solver"]["cfl"] == 1.0 and T["solver"]["maxsub"] == 8 and T["solver"]["pcfl"] == 0.75)
    ck["bed"] = bool(Bd["x_toe_m"] == GC.X_TOE and Bd["slope1_1_in"] == GC.SLOPE_S and Bd["h_foot_m"] == GC.H_L and Bd["slope2_1_in"] == GC.S2
                     and Bd["shelf_h_m"] == GC.H_TOP and Bd["x_foot_m"] == GC.X_FOOT and Bd["x_edge_m"] == GC.X_EDGE)
    B = T["bands"]
    ck["bands"] = bool(B["inlet"]["xg_end"] == GC.IN_X1 and B["inlet"]["wall_taper_m"] == GC.WALL_TAPER and B["side"]["sd0"] == GC.SD0
                       and B["side"]["sd_gen"] == GC.SD_GEN and B["side"]["sd_sw"] == GC.SD_SW and B["side"]["sd_sigma"] == GC.SD_SIGMA
                       and B["side"]["sd_pow"] == GC.SD_POW and B["side"]["sd_taper_m"] == GC.SD_TAPER and B["exit_sponge"]["abs_on"] == 1
                       and B["exit_sponge"]["xa0_m"] == GC.XA0 and B["exit_sponge"]["abs_sigma"] == GC.ABS_SIGMA and B["exit_sponge"]["abs_pow"] == GC.ABS_POW
                       and B["ret_on"] == 1 and B["dir_on"] == 1 and B["volume"]["vol_x_m"] == list(GC.VOL_X))
    C = GC.components()
    ck["sea_P_harmonics"] = bool(S["P_s"] == GC.P_S and S["harmonics_n"] == list(GC.HARMONICS) and S["ramp_s"] == GC.RAMP_S)
    ck["sea_focus"] = bool(S["focus"]["x_m"] == GC.X_F and S["focus"]["y_m"] == 0.0 and S["focus"]["t_f_s"] == GC.T_F
                           and S["focus"]["times_s"] == list(GC.FOCI))
    ck["sea_set_bit_for_bit"] = bool([round(float(v), 6) for v in C["th"]] == S["directions_deg"] and [round(float(v), 6) for v in C["wd"]] == S["dir_weights"]
                                     and [round(float(v), 6) for v in C["wf"]] == S["freq_weights"] and C["a"].size == S["n_components"])
    ck["sea_a_sum"] = bool(abs(C["a_sum"] - S["a_sum_m"]) < 1e-6 and round(float(C["a"].max()), 6) == S["a_max_component_m"]
                           and [round(float(C["a_sum"] * v), 6) for v in C["wf"]] == S["amp_per_freq_m"])
    am = GC.am_dfgb1_sea() or {}
    ck["sea_equals_AM_DFGB1"] = bool(am and abs(float(am["a_sum_m"]) - C["a_sum"]) < 1e-6 and abs(float(am["sum_a2_m2"]) - float(np.sum(C["a"] ** 2))) < 1e-5
                                     and [float(v) for v in am["amp_per_freq_m"]] == S["amp_per_freq_m"])
    try:
        dm = json.load(open(GC.DM1A_CFG, encoding="utf8"))["dir"]
        s_dm = float(int(dm["n"]) * float(dm["a_j"]) ** 2)
        ck["energy_equals_DM1A"] = bool(abs(float(np.sum(C["a"] ** 2)) / s_dm - 1.0) < 1e-9 and abs(float(S["energy"]["sum_a2_m2"]) / s_dm - 1.0) < 1e-5)
    except Exception as e:
        ck["energy_equals_DM1A"] = False
        ck["energy_error"] = repr(e)[:200]
    meas = GC.dfgbe_g2f_phases() or {}
    ck["calibration_phi"] = bool({int(k): float(v) for k, v in K["phi_rad"].items()} == GC.PHI_COMP
                                 and all(abs(meas.get(k, 99.0) - v) < 1e-9 for k, v in GC.PHI_COMP.items()))
    ck["records"] = bool(R["t_end_s"] == T_END[0.5] and R["group_window_s"] == list(GC.GROUP_WIN) and "every 48 frames" in R["checkpoints"])
    tn = pl.get("table_npz") or {}
    try:
        p_, sha_, ch_, _ = TB.write(dry=True)
        ck["table_content_as_frozen"] = bool(tn.get("content_sha256") == ch_)
    except Exception as e:
        ck["table_content_as_frozen"] = False
        ck["table_error"] = repr(e)[:200]
    ok = all(v for k, v in ck.items() if isinstance(v, bool))
    return dict(ok=bool(ok), checks=ck)


def precheck(c):
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", wall="computed (measured DFG-2B-E rate)"))
    ck = out["checks"]
    pc = plan_consistency()
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    dp = float(P["dp"])
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V), particles_model_DFGBE=DFGBE_PART_MODEL, particles_ratio_vs_DFGBE=float(n) / DFGBE_PART_MODEL)
    ck["particles_le_limit"] = bool(n * 1.16 / 1e6 <= PART_LIMIT_M)
    b = c["box"]
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["W"]) == GC.W_MAIN and float(P["zb"]) == GC.ZB and float(P["Hz"]) == GC.Z_TOP - GC.ZB
                     and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0 and b["z_top"] == GC.Z_TOP and float(P["gridscale"]) == 2.0)
    ck["bed_is_DFGB3"] = bool(GC.is_new(spec) and float(spec["x_toe"]) == GC.X_TOE and float(spec["s"]) == GC.SLOPE_S and float(spec["k"]) == 0.0
                              and float(spec["pg_hL"]) == GC.H_L and float(spec["pg_s2"]) == GC.S2 and float(spec["shelf_h"]) == GC.H_TOP
                              and float(spec.get("b_end") or 0.0) == 0.0 and float(spec.get("x_back", 1e9)) >= 1e8
                              and float(c["bed"].get("max_depth_m", -1)) == GC.H0 and float(c["bed"].get("min_depth_m", -1)) == GC.H_TOP
                              and abs(float(c["bed"].get("x_foot_axis_m") or 0.0) - GC.X_FOOT) < 1e-9)
    bs = GC.bed_selfcheck()
    ck["bed_numpy_selfcheck"] = bool(bs["ok"])
    # the parms equal DFG-2B-E's launched cfg except the named differences (bed, exit sponge, stage A window end)
    try:
        ref = json.load(open(DFGBE_READY, encoding="utf8"))["parms"]
        diff = sorted(k for k in set(ref) | set(P) if k not in PARMS_DIFFER_FROM_DFGBE and (k not in ref or k not in P or float(ref[k]) != float(P[k])))
        named = {k: (ref.get(k), P.get(k)) for k in PARMS_DIFFER_FROM_DFGBE}
        ck["parms_equal_DFGBE_except_named"] = bool(not diff and all(float(P[k]) == v for k, v in PARMS_DIFFER_FROM_DFGBE.items()))
        out["parms_diff_vs_DFGBE"] = diff
        out["parms_named_differences"] = named
    except Exception as e:
        ck["parms_equal_DFGBE_except_named"] = False
        out["parms_diff_vs_DFGBE"] = repr(e)[:200]
    ck["bands"] = bool(float(P["relax_on"]) == 1.0 and float(P["sd_on"]) == 1.0 and float(P["abs_on"]) == 1.0 and float(P["xa0"]) == GC.XA0
                       and float(P["dir_on"]) == 1.0 and float(P["ret_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and float(P["dir_tf"]) == GC.T_F
                       and float(P["ramp_s"]) == GC.RAMP_S and float(P["in_gain"]) == 1.0 and float(P["sd_gain"]) == 1.0 and float(P["set_P"]) == 0.0)
    ck["drift_stage_A"] = bool(c["drift"]["stage"] == "A" and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0 and float(P["hold_on"]) == 0.0
                               and float(P["vol_x1"]) <= float(P["xa0"]) - 5.0)
    dr = c.get("dir") or {}
    ck["table_file_sha"] = bool(os.path.exists(dr.get("npz") or "") and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_t = False
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        S = GC.plan()["sea"]
        ok_t = bool(info.get("set") == GC.SET and float(info["P"]) == S["P_s"] and info["harmonics"] == S["harmonics_n"]
                    and [round(float(v), 6) for v in info["theta_deg"]] == S["directions_deg"] and [round(float(v), 6) for v in info["dir_weights"]] == S["dir_weights"]
                    and [round(float(v), 6) for v in info["freq_weights"]] == S["freq_weights"] and abs(float(info["a_sum"]) - S["a_sum_m"]) < 1e-6
                    and float(info["x_f"]) == S["focus"]["x_m"] and float(info["t_f"]) == S["focus"]["t_f_s"]
                    and [float(v) for v in info["foci"]] == S["focus"]["times_s"] and info.get("content_sha256") == dr.get("content_sha256")
                    and int(info["n_layers"]) == 3 and float(info["h0"]) == GC.H0 and abs(float(info["y1"]) - float(P["W"])) < 1e-9
                    and float(info["x1"]) >= GC.SD_SW and {int(k): float(v) for k, v in info["phase_comp_rad"].items()} == GC.PHI_COMP)
    except Exception as e:
        out["table_error"] = repr(e)[:200]
    ck["table_is_plan_set"] = ok_t
    tc = GC.TABLE_CHECK
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    ck["table_G1_checked"] = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256"))
    G2 = ((dr.get("linear_refs") or {}).get("G2f_gauges") or {}).get("A_n") or {}
    try:
        ref_tc = json.load(open(GC.REPO + "/Unity/Build/FLIP52B/plan/table_check_DFGBE.json", encoding="utf8"))["linear_refs"]["G2f_gauges"]["A_n"]
        ck["G2f_reference_is_DFGBE_design"] = bool(all(abs(complex(*G2[yk][nk]) - complex(*ref_tc[yk][nk])) < 1e-6 for yk in ref_tc for nk in ref_tc[yk]))
    except Exception as e:
        ck["G2f_reference_is_DFGBE_design"] = False
        out["G2f_ref_error"] = repr(e)[:200]
    en = (c.get("wave") or {}).get("energy") or {}
    ck["energy_block"] = bool(en and abs(float(en.get("spectral_ratio") or 0.0) - 1.0) < 1e-9 and (en.get("in_tank") or {}).get("equals_DFGB_E")
                              and (en.get("in_tank") or {}).get("reproduces_AM_DFGB1b"))
    rec = c["records"]
    wins = rec.get("windows") or []
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and (rec.get("r4") or {}).get("x") == list(GC.R4_X) and wins == windows_for(c["t_end_s"])
                                     and len(wins) == 3 and (rec.get("r5") or {}).get("every") == 3)
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in wins))
    ck["gauges"] = bool(c["gauges"]["x"][0] == 110.0 and c["gauges"]["y"] == list(GC.GAUGE_Y) and max(c["gauges"]["y"]) < GC.SD0)
    ck["checkpoints"] = bool(c["ckpt_every"] == 48 and c["ckpt_on"] == 1 and c["wall_limit_s"] == 1740)
    ck["out_root_absolute_FLIP52B2"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(GC.B52B2 + "/"))
    ck["plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == GC.PLAN_REL and (c.get("analysis") or {}).get("plan_frozen") == GC.PLAN_REL)
    te = time_estimate(c, n)
    out["time"] = te
    ck["time_within_max_hours"] = bool(te["est_h"][1] <= float(c["max_hours"]))
    out["ok"] = bool(all(ck.values()))
    out["reason"] = None if out["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    return out


def write(c):
    p = os.path.join(c["out_root"], "ready", c["run_id"] + ".json").replace("\\", "/")
    GC.guard_out(os.path.dirname(p))
    with open(p, "w", encoding="utf8") as fh:
        json.dump(c, fh, indent=1, ensure_ascii=False, default=float)
    return p


def gate(cfgp):
    """dry copy of the g52b2_chain.py start gate (same conditions; reads only)."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if not os.path.exists(GC.BUILD_CHECK):
        bad.append("build_check52b2.json missing (py -3.10 x52b2_build.py)")
    else:
        bc = json.load(open(GC.BUILD_CHECK, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check52b2 all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check52b2")
    dr = cfg.get("dir") or {}
    if not os.path.exists(dr.get("npz") or ""):
        bad.append("table missing")
    elif GC.sha256_file(dr["npz"]) != dr.get("npz_sha256"):
        bad.append("table sha differs")
    pf = (cfg.get("case") or {}).get("plan_frozen")
    p = pf if os.path.isabs(pf) else os.path.join(GC.REPO, pf)
    if not (os.path.exists(p) and os.path.exists(p + ".sha256")):
        bad.append("frozen plan or .sha256 missing: %s" % p)
    elif open(p + ".sha256", encoding="utf8").read().split()[0] != GC.sha256_file(p):
        bad.append("frozen plan sha differs from .sha256")
    rd = os.path.join(GC.B52B2, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP52B2=rd.startswith(GC.B52B2 + "/"), hip=GC.HIP,
                hip_sha256=GC.sha256_file(GC.HIP) if os.path.exists(GC.HIP) else None)


def check_all(dry=False):
    out = dict(plan=GC.PLAN_REL, sea=GC.SET, plan_consistency=plan_consistency(), presets={})
    for pr in PRESETS:
        c = make(pr, dry=dry)
        out["presets"][pr] = dict(run_id=c["run_id"], precheck=c["precheck"], cfg_sha16=GC.sha16_json(c))
    out["ok"] = bool(out["plan_consistency"]["ok"] and all(v["precheck"]["ok"] for v in out["presets"].values()))
    if not dry:
        GC.jdump(out, GC.PRECHECK)
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = [v for v in sys.argv[1:] if not v.startswith("--")]
    if not a:
        print(__doc__); sys.exit(1)
    if a[0] == "check":
        o = check_all(dry="--dry" in sys.argv)
        print(json.dumps(GC.clean(dict(ok=o["ok"], plan_consistency=o["plan_consistency"],
                                       presets={k: dict(run_id=v["run_id"], ok=v["precheck"]["ok"], reason=v["precheck"]["reason"],
                                                        particles=v["precheck"]["particles_model"], time=v["precheck"]["time"]["est_h"],
                                                        parms_diff_vs_DFGBE=v["precheck"].get("parms_diff_vs_DFGBE"))
                                                for k, v in o["presets"].items()})), ensure_ascii=False))
    elif a[0] in ("cfg", "show") and len(a) >= 2:
        pr = a[1]
        if pr not in PRESETS:
            print(__doc__); sys.exit(1)
        c = make(pr)
        if a[0] == "show":
            print(json.dumps(GC.clean(c), ensure_ascii=False, indent=1)); return
        if not c["precheck"]["ok"]:
            print(json.dumps(dict(preset=pr, written=None, precheck_ok=False, reason=c["precheck"]["reason"]), ensure_ascii=False)); return
        p = write(c)
        print(json.dumps(GC.clean(dict(preset=pr, run_id=c["run_id"], written=p, sha256=GC.sha256_file(p), precheck_ok=True,
                                       particles=c["precheck"]["particles_model"], time_h=c["precheck"]["time"]["est_h"])), ensure_ascii=False))
    elif a[0] == "gate" and len(a) >= 2:
        print(json.dumps(gate(a[1]), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
