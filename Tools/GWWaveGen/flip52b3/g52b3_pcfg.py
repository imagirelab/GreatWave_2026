# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 (DFG-2B-V): the run configuration (cfg.json) with its precheck, the consistency check of every constant against the frozen
plan, and a dry copy of the g52b3_chain start gate (py -3.10 -B). 2026-10-18 written new (Claude) by adapting flip52b2/g52b2_pcfg.py (DFGB3,
frozen, not edited). Reads only the frozen plan, the FLIP52B3 table, DFG-2B-E's launched cfg (Unity/Build/FLIP52B/runs/ready/
DFGB2E_D19B_xf272p25_dp0p5.json, read only: EVERY DFGB4 parm must equal it - no named parm difference) and DM1A's cfg (energy check). Writes
only Unity/Build/FLIP52B3/runs/ready/<run_id>.json and plan/precheck_DFGB4.json.

Preset (plan_DFGB4_frozen.json; nothing here is tuned):
  main   DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5  dp 0.5, 0 - (t_f3 + 6) = 125 s, the judged run; r4 and r5 every 3rd frame in the three group
                                               windows [t_fn - 8, t_fn + 6] s (= DFG-2B-E's judged layout); max_hours 3.0 per chain (= DFG-2B-E; a
                                               stop at max_hours is resumed from the last checkpoint by auto_DFGB4.py, up to 2 times), launches of
                                               <= 1740 s, checkpoints every 48 frames
The cfg = DFG-2B-E's launched cfg (parms, box, bed, drift, records, gauges, level regions, dir_check, checkpoints, analysis layout) with the
DFGB4 generator table (DFG-2B-E's design x the inlet-only n5 phase calibration x the 3 % side-band taper; dir_on 1, ret_on 1) as the only
difference that reaches the tank.
usage:
  py -3.10 -B g52b3_pcfg.py check [--dry]      plan consistency + precheck of main (writes plan/precheck_DFGB4.json; --dry: nothing)
  py -3.10 -B g52b3_pcfg.py cfg main           write runs/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B g52b3_pcfg.py gate <cfg.json>    the g52b3_chain start gate, dry (reads only) -> json
  py -3.10 -B g52b3_pcfg.py show main          print the cfg (not written)
Tags: [measured] [computed] [calibrated] [guess] [chosen].
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52b3_common as GC            # noqa: E402
import g52b3_table as TB             # noqa: E402

DFGBE_READY = GC.DFGBE_READY         # read only [the parms that ran DFG-2B-E]
PRESETS = {"main": 0.5}
T_END = {0.5: GC.FOCI[-1] + GC.GROUP_WIN[1]}
MAX_H = {0.5: 3.0}                   # hard cap per chain = DFG-2B-E's [measured: DFG-2B-E took 2.375 h, DFGB3 2.406 h on the same code path]
# run-time model [measured: DFG-2B-E 0.5 m, same tank, records and code: 8551 s for 3001 frames incl. relaunch overlap, model 5.384 M]
DFGBE_WALL_S = 8551.2
DFGBE_FRAMES = 3001
DFGBE_PART_MODEL = 5383840
PART_LIMIT_M = 7.0
DIR_CHECK = dict(every=120, x=[10.0, 40.0, 70.0, 95.0, 150.0, 200.0], y=[-15.0, -8.0, -2.0], zl=[0.5, 50.0, 100.0, 120.0])   # = DFG-2B-E cfg
PARMS_DIFFER_FROM_DFGBE = {}         # none: the tank, bands, bed, solver and stage A are DFG-2B-E's bit for bit
SAME_AS_DFGBE_KEYS = ("box", "bed", "gauges", "dir_check", "ckpt_on", "ckpt_every", "ckpt_list", "wall_limit_s", "level_guard_m", "disk_stop_free_gb",
                      "level_box", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "pstats_frames", "layout", "kind", "f_end", "t_end_s", "solver",
                      "level_regions", "f_start", "f_first", "max_hours")
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
                amendment="AM-D18 (as plan E X2 / DFG-2B-E)",
                rule="FLIP49 stage A: whole-tank column volume held by a target divergence in x %g-%g m (tau %g s, cap %g /s)"
                     % (GC.VOL_X[0], GC.VOL_X[1], GC.VOL_TAU, GC.VOL_DMAX))


def windows_for(t_end):
    return [[t + GC.GROUP_WIN[0], t + GC.GROUP_WIN[1]] for t in GC.FOCI if t + GC.GROUP_WIN[1] <= t_end + 1e-9]


def records(dp, t_end):
    return dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
                r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=GC.R4_Z[0], y1=GC.R4_Z[1], clip_vox=6.0, t0=0.0, every=3),
                r5=dict(t0=0.0, every=3), windows=windows_for(t_end))


def energy_block():
    """the Q84 energy statement carried by the cfg (and copied by g52b3_ana into the judge and the co-equal verdict)."""
    global _ENERGY
    if _ENERGY is None:
        E = TB.energy_in_tank()
        C = GC.components()
        D = E.get("DM1A") or {}
        EE = E.get("DFGB_E") or {}
        _ENERGY = dict(statement=GC.sea_text(), basis="equal spectral energy (Q84): energy density 0.5 rho g sum a^2 of the incoming components at "
                                                         "the generation depth h0 19 m (= DM1A's generation depth)",
                       sum_a2_m2=float(np.sum(C["a"] ** 2)), DM1A_sum_a2_m2=GC.DM1A_SUM_A2, spectral_ratio=E["spectral"]["ratio"],
                       scale_vs_DFGB_frozen=GC.E_SCALE, a_sum_m=GC.A_SUM, a_max_component_m=float(C["a"].max()), DM1A_a_j_m=GC.DM1A_AJ,
                       calibration="the inlet-only n5 phase factor has |factor| 1 (no energy); the 3 % side-band taper (y 95-125 m, x >= 140 m to the side band's "
                                   "fade-out end at 210.25 m) lowers "
                                   "the generator target there, not the incoming spectrum",
                       in_tank=dict(inlet_variance_over_DM1A=E["DFGB4"].get("inlet_variance_over_DM1A"),
                                    interior_power_over_DM1A=E["DFGB4"].get("interior_power_over_DM1A"),
                                    inlet_Hm0_equiv_m=E["DFGB4"]["inlet_band_Hm0_equiv_m"], DM1A_inlet_Hm0_equiv_m=D.get("inlet_band_Hm0_equiv_m"),
                                    power_into_interior_MW=E["DFGB4"]["power_into_interior_MW"], DM1A_power_into_interior_MW=D.get("power_into_interior_MW"),
                                    DFGB_E_interior_power_over_DM1A=EE.get("interior_power_over_DM1A"),
                                    vs_DFGB_E=E.get("DFGB4_vs_DFGB_E"), reproduces_AM_DFGB1b=(E.get("reproduces_AM_DFGB1b") or {}).get("ok"),
                                    rule="g52b3_table.energy_in_tank (the AM-DFGB1b rule on the D19B layout: x 100 m, y 95 m, side band to 180.25 m) [computed]"),
                       statement_in_tank=E["statement_en"])
    return _ENERGY


def time_estimate(c, n_model):
    nf = int(c["f_end"]) - int(c.get("f_start", 1)) + 1
    s = DFGBE_WALL_S * (nf / float(DFGBE_FRAMES)) * (float(n_model) / DFGBE_PART_MODEL)
    nl = int(math.ceil(s / c["wall_limit_s"]))
    return dict(frames=nf, launches=[nl, nl + 1], est_h=[s / 3600.0, (1.12 * s + 60.0 * (nl + 1)) / 3600.0],
                rule="DFG-2B-E 0.5 m (same tank, records, code; %.0f s for %d frames incl. relaunch overlap) x frames x particle ratio %.4f; high = x 1.12 "
                     "+ 60 s per launch [measured rate, guessed margin]" % (DFGBE_WALL_S, DFGBE_FRAMES, float(n_model) / DFGBE_PART_MODEL))


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
    ref = json.load(open(DFGBE_READY, encoding="utf8"))
    ana = dict(ref["analysis"])
    ana.update(plan_frozen=GC.PLAN_REL, dir_case="DFGB4", tool="Tools/GWWaveGen/flip52b3/g52b3_ana.py")
    c = dict(
        run_id=rid, out_root=GC.RUNS_ROOT, stage="FLIP52B3", kind="3d",
        case=dict(name="FLIP52B3_main_%s_D19B_dp%s" % (GC.SET, GC.tag(dp)), plan_frozen=GC.PLAN_REL,
                  plan="Unity/Build/FLIP52B3/plan/plan_DFGB4_frozen.json (sea, calibration, taper, tank, records, co-equal criteria incl. 3b / 3c / "
                       "keeps the curl, gates, decision, honesty)", campaign="FLIP52B3-DFGB4 (DFG-2B-V)", preset=preset, set=GC.SET,
                  role="the judged DFG-2B-V run (DFG-2B round 3: a validation rerun of DFG-2B-E)", judged=True, pipeline_check_only=False,
                  P1_x_max_m=330.0, dir_case="DFGB4",
                  label=("DFG-2B-E unchanged (sea P 28 s, T 9.33/7/5.6 s, X2 directions, spectral energy = DM1A; D19B 1:10 beach; design phase "
                         "reference (%.2f, 0)) with an inlet-only n5 phase calibration (%.4f rad) and a 3 %% side-band taper" % (GC.X_F, GC.PHI5)),
                  reference_cfg="Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json (every parm equal; only the table differs)",
                  a_sum_tag=GC.sea_text() + " [chosen]"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_BED, b),
        sf=GC.sf_descriptor(H_ref=H_ref, note="FLIP52B3: the inflow is the N-layer table cfg dir (P 28 s, n 3/4/5); this descriptor (T 7 s, h0 19 m) "
                                               "is for T, L, c, k only; H = 2 x the sum of the linear per-frequency DESIGN amplitudes at (110, 0.5) m"),
        dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear periodic multi-frequency directional sea (WKB over D19B, = DFG-2B-E's) with two generator maps: an inlet-only n5 "
                       "phase calibration and a 3 %% side-band taper: %d components (3 harmonics of P = 28 s x %d directions), design phases 0 at "
                       "(x_f, 0) at t = t_f + 28 m" % (tb["n_components"], len(tb["theta_deg"])),
                  P_s=GC.P_S, harmonics=list(GC.HARMONICS), T_s=tb["T"], freq_weights=tb["freq_weights"], theta_deg=tb["theta_deg"],
                  dir_weights=tb["dir_weights"], dspec=list(GC.DSPEC), a_sum_m=tb["a_sum"], a_component_max_m=tb["a_max_component"],
                  amp_per_freq_m=tb["amp_per_freq"], x_f_m=GC.X_F, h_f_m=GC.h_of(GC.X_F), t_f_s=GC.T_F,
                  foci_s=list(GC.FOCI), in_gain=1.0, sd_gain=1.0, ramp_s=GC.RAMP_S, focal_crest_linear_m=lr["design_crest_xf_m"],
                  calibration=tb["calibration"], taper=tb["taper"], energy=en,
                  chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and weights, a_sum %.6f m (spectral energy "
                                  "= DM1A, AM-DFGB1), the design phase reference (%.2f, 0) at t = %.0f + 28 m s, the D19B tank and its option-D bands "
                                  "(= DFG-2B-E) [chosen]; the inlet-only n5 phase calibration %.4f rad (0.6 x DFG-2B-E's measured G2f n5 phase) and the "
                                  "3 %% side-band taper at the G4 hot spot [calibrated]; computed by FLIP: propagation, dispersion, refraction, shoaling, "
                                  "focusing, the crest's growth, breaking, any jet / plume" % (GC.A_SUM, GC.X_F, GC.T_F, GC.PHI5),
                  tags=dict(P="chosen", harmonics="chosen", weights="chosen", directions="chosen", a_sum="chosen (spectral energy = DM1A, AM-DFGB1)",
                            x_f="chosen (= DFG-2B-E)", t_f="computed (ray arrival + 3.9 s, = DFG-2B-E)",
                            calibration="calibrated (0.6 x DFG-2B-E's G2f n5 phase; CS1 screen)", taper="calibrated (the per-cell G4 r-map of DFG-2B-E)",
                            table="computed (g52b3_table)")),
        drift=drift_stage_A(), solver=dict(veltransfer="flip", donarrowband=0), records=records(dp, t_end),
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_52B3],
        dir_check=copy.deepcopy(DIR_CHECK), ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740,
        level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0, max_hours=MAX_H[dp], level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_STILL_X),
        n1_window=[0.5, 1.5], shore_x=GC.X_SHORE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP52B3 DFGB4 = DFG-2B-V (DFG-2B round 3, a validation rerun of DFG-2B-E) main: 3D dp %g, the D19B tank of DFG-2B-E (half tank W 140 m, "
              "side band 95-140 m, h0 19 m, 1:10 beach from x 160.25 m, no exit sponge; the scene a byte copy of DFG-2B-E's); the DFG-2B-E sea (%s) "
              "with the inlet-only n5 phase calibration %.4f rad and the 3 %% side-band taper; design phase reference (%.2f, 0) at t = %s s; ramp "
              "14 s, stage A (110-400 m), 0-%g s. Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in the three group windows [t_fn - 8, "
              "t_fn + 6] s" % (dp, GC.sea_text(), GC.PHI5, GC.X_F, " / ".join("%g" % t for t in GC.FOCI), t_end)),
        layout="D", analysis=ana)
    c["precheck"] = precheck(c)
    return c


# ====================================================================== checks
def plan_consistency():
    if not os.path.exists(GC.PLAN):
        return dict(ok=False, checks=dict(plan_exists=False))
    pl = GC.plan()
    T = pl["tank"]; S = pl["sea"]; R = pl["records"]; K = pl["calibration"]; TP_ = pl["taper"]
    ck = {}
    ck["plan_sha256"] = GC.plan_sha_ok()
    Bd = T["bed"]
    ck["tank"] = bool(T["h0_m"] == GC.H0 and T["Lx_m"] == GC.LX and T["W_m"] == GC.W_MAIN and T["z_bed_m"] == GC.ZB and T["z_top_m"] == GC.Z_TOP
                      and T["solver"]["gridscale"] == 2.0 and T["solver"]["cfl"] == 1.0 and T["solver"]["maxsub"] == 8 and T["solver"]["pcfl"] == 0.75)
    ck["bed"] = bool(Bd["x_toe_m"] == GC.X_TOE and Bd["slope_1_in"] == GC.SLOPE_S and Bd["x_shore_m"] == GC.X_SHORE and Bd["spec"] == "g50_common.SPEC_D19B")
    B = T["bands"]
    ck["bands"] = bool(B["inlet"]["xg_end"] == GC.IN_X1 and B["inlet"]["wall_taper_m"] == GC.WALL_TAPER and B["side"]["sd0"] == GC.SD0
                       and B["side"]["sd_gen"] == GC.SD_GEN and B["side"]["sd_sw"] == GC.SD_SW and B["side"]["sd_sigma"] == GC.SD_SIGMA
                       and B["side"]["sd_pow"] == GC.SD_POW and B["side"]["sd_taper_m"] == GC.SD_TAPER and B["exit_sponge"]["abs_on"] == 0
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
    ck["calibration"] = bool(K["n"] == GC.CAL_N and abs(float(K["phi5_rad"]) - GC.PHI5) < 1e-6 and K["scale"] == GC.CAL_SCALE5
                             and K["phi5_measured_rad"] == GC.PHI5_MEAS and abs(meas.get(5, 99.0) - GC.PHI5_MEAS) < 1e-9
                             and K["x_full_m"] == GC.CAL_X_FULL and K["x_zero_m"] == GC.CAL_X_ZERO)
    ck["taper"] = bool(TP_["d"] == GC.TAPER_D and TP_["x"] == list(GC.TAPER_X) and TP_["y"] == list(GC.TAPER_Y) and TP_["y_in"] == list(GC.TAPER_YIN))
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
    ck["particles_equal_DFGBE"] = bool(int(n) == DFGBE_PART_MODEL)
    b = c["box"]
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["W"]) == GC.W_MAIN and float(P["zb"]) == GC.ZB and float(P["Hz"]) == GC.Z_TOP - GC.ZB
                     and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0 and b["z_top"] == GC.Z_TOP and float(P["gridscale"]) == 2.0)
    bs = GC.bed_selfcheck()
    ck["bed_numpy_selfcheck"] = bool(bs["ok"])
    # every parm equals DFG-2B-E's launched cfg; the other blocks too (only the table, the names and the texts differ)
    try:
        ref = json.load(open(DFGBE_READY, encoding="utf8"))
        rp = ref["parms"]
        diff = sorted(k for k in set(rp) | set(P) if (k not in rp or k not in P or float(rp[k]) != float(P[k])))
        ck["parms_equal_DFGBE"] = bool(not diff)
        out["parms_diff_vs_DFGBE"] = diff
        bdiff = [k for k in SAME_AS_DFGBE_KEYS if json.dumps(ref.get(k), sort_keys=True) != json.dumps(c.get(k), sort_keys=True)
                 and k != "max_hours"]
        out["blocks_diff_vs_DFGBE"] = bdiff
        ck["blocks_equal_DFGBE"] = bool(not bdiff)
        ck["max_hours_equal_DFGBE"] = bool(float(ref.get("max_hours")) == float(c["max_hours"]))
        rr, cr = ref["records"], c["records"]
        ck["records_equal_DFGBE"] = bool(json.dumps(rr, sort_keys=True) == json.dumps(cr, sort_keys=True))
        ck["drift_equal_DFGBE"] = bool(all(ref["drift"].get(k) == c["drift"].get(k) for k in ("stage", "tau_s", "dmax", "tcap_s", "V_measure", "window_m")))
        ra = dict(ref["analysis"]); ca = dict(c["analysis"])
        for k in ("plan_frozen", "dir_case", "tool"):
            ra.pop(k, None); ca.pop(k, None)
        ck["analysis_layout_equal_DFGBE"] = bool(ra == ca)
        rw, cw = ref["wave"], c["wave"]
        ck["wave_equal_DFGBE"] = bool(all(json.dumps(rw.get(k)) == json.dumps(cw.get(k)) for k in ("P_s", "harmonics", "T_s", "freq_weights", "theta_deg",
                                                                                                   "dir_weights", "dspec", "a_sum_m", "a_component_max_m",
                                                                                                   "amp_per_freq_m", "x_f_m", "h_f_m", "t_f_s", "foci_s",
                                                                                                   "in_gain", "sd_gain", "ramp_s")))
        ck["dir_sea_equal_DFGBE"] = bool(all(json.dumps(ref["dir"].get(k)) == json.dumps(c["dir"].get(k)) for k in
                                             ("P", "harmonics", "n_layers", "omega", "T", "k", "freq_weights", "theta_deg", "dir_weights", "dspec", "a_sum",
                                              "a_max_component", "amp_per_freq", "n_components", "x_f", "h_f", "t_f", "foci", "grid", "fields", "bed", "ret_on")))
    except Exception as e:
        ck["parms_equal_DFGBE"] = False
        out["parms_diff_vs_DFGBE"] = repr(e)[:200]
    ck["bands"] = bool(float(P["relax_on"]) == 1.0 and float(P["sd_on"]) == 1.0 and float(P["abs_on"]) == 0.0
                       and float(P["dir_on"]) == 1.0 and float(P["ret_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and float(P["dir_tf"]) == GC.T_F
                       and float(P["ramp_s"]) == GC.RAMP_S and float(P["in_gain"]) == 1.0 and float(P["sd_gain"]) == 1.0 and float(P["set_P"]) == 0.0)
    ck["drift_stage_A"] = bool(c["drift"]["stage"] == "A" and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0 and float(P["hold_on"]) == 0.0)
    dr = c.get("dir") or {}
    ck["table_file_sha"] = bool(os.path.exists(dr.get("npz") or "") and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_t = False
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        S = GC.plan()["sea"]
        Kp = GC.plan()["calibration"]
        ok_t = bool(info.get("set") == GC.SET and float(info["P"]) == S["P_s"] and info["harmonics"] == S["harmonics_n"]
                    and [round(float(v), 6) for v in info["theta_deg"]] == S["directions_deg"] and [round(float(v), 6) for v in info["dir_weights"]] == S["dir_weights"]
                    and [round(float(v), 6) for v in info["freq_weights"]] == S["freq_weights"] and abs(float(info["a_sum"]) - S["a_sum_m"]) < 1e-6
                    and float(info["x_f"]) == S["focus"]["x_m"] and float(info["t_f"]) == S["focus"]["t_f_s"]
                    and [float(v) for v in info["foci"]] == S["focus"]["times_s"] and info.get("content_sha256") == dr.get("content_sha256")
                    and int(info["n_layers"]) == 3 and float(info["h0"]) == GC.H0 and abs(float(info["y1"]) - float(P["W"])) < 1e-9
                    and float(info["x1"]) >= GC.SD_SW and abs(float(info["calibration"]["phi5_rad"]) - float(Kp["phi5_rad"])) < 1e-6
                    and float(info["taper"]["d"]) == GC.TAPER_D)
    except Exception as e:
        out["table_error"] = repr(e)[:200]
    ck["table_is_plan_set"] = ok_t
    tc = GC.TABLE_CHECK
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    ck["table_G1_checked"] = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256"))
    G2 = ((dr.get("linear_refs") or {}).get("G2f_gauges") or {}).get("A_n") or {}
    try:
        ref_tc = json.load(open(GC.DFGBE_TABLE_CHECK, encoding="utf8"))["linear_refs"]["G2f_gauges"]["A_n"]
        ck["G2f_reference_is_DFGBE_design"] = bool(all(abs(complex(*G2[yk][nk]) - complex(*ref_tc[yk][nk])) < 1e-6 for yk in ref_tc for nk in ref_tc[yk]))
    except Exception as e:
        ck["G2f_reference_is_DFGBE_design"] = False
        out["G2f_ref_error"] = repr(e)[:200]
    en = (c.get("wave") or {}).get("energy") or {}
    it = en.get("in_tank") or {}
    ck["energy_block"] = bool(en and abs(float(en.get("spectral_ratio") or 0.0) - 1.0) < 1e-9 and it.get("reproduces_AM_DFGB1b")
                              and isinstance(it.get("interior_power_over_DM1A"), float) and 0.2 < it["interior_power_over_DM1A"] < 0.24)
    rec = c["records"]
    wins = rec.get("windows") or []
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and (rec.get("r4") or {}).get("x") == list(GC.R4_X) and wins == windows_for(c["t_end_s"])
                                     and len(wins) == 3 and (rec.get("r5") or {}).get("every") == 3)
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in wins))
    ck["gauges"] = bool(c["gauges"]["x"][0] == 110.0 and c["gauges"]["y"] == list(GC.GAUGE_Y) and max(c["gauges"]["y"]) < GC.SD0)
    ck["checkpoints"] = bool(c["ckpt_every"] == 48 and c["ckpt_on"] == 1 and c["wall_limit_s"] == 1740)
    ck["out_root_absolute_FLIP52B3"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(GC.B52B3 + "/"))
    ck["plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == GC.PLAN_REL and (c.get("analysis") or {}).get("plan_frozen") == GC.PLAN_REL)
    ck["no_temp_paths"] = bool("appdata" not in json.dumps(c).lower() and "\\temp" not in json.dumps(c).lower() and "/temp/" not in json.dumps(c).lower())
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
    """dry copy of the g52b3_chain.py start gate (same conditions; reads only)."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if not os.path.exists(GC.BUILD_CHECK):
        bad.append("build_check52b3.json missing (py -3.10 x52b3_build.py)")
    else:
        bc = json.load(open(GC.BUILD_CHECK, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check52b3 all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check52b3")
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
    rd = os.path.join(GC.B52B3, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP52B3=rd.startswith(GC.B52B3 + "/"), hip=GC.HIP,
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
                                                        parms_diff_vs_DFGBE=v["precheck"].get("parms_diff_vs_DFGBE"),
                                                        blocks_diff_vs_DFGBE=v["precheck"].get("blocks_diff_vs_DFGBE"))
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
