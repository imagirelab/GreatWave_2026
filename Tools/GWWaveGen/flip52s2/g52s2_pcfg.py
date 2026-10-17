# -*- coding: utf-8 -*-
"""FLIP52S2 plan DFG-S-E140: run configurations (cfg.json) with their prechecks, the consistency check of every constant against the frozen
plan, and a dry copy of the g52s2_chain start gate (py -3.10 -B). 2026-10-18 written new (Claude) by adapting flip52s/g52s_pcfg.py (DFG-S,
frozen, not edited). Reads only the frozen plan, the FLIP52S2 table and the DFG-S 0.5 m cfg (Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/
cfg.json, read only: every DFG-S-E140 parm must equal it except the named differences W, sd0, dir_tf). Writes only
Unity/Build/FLIP52S2/<pcheck|runs>/ready/<run_id>.json and plan/precheck_DFGS2.json.

Presets (plan_DFGS2_frozen.json; nothing here is tuned). NO 1.0 m smoke (dp 1.0 damps the 5.6 s layer: DFG-2 smoke n5 0.43, DFG-2B-E smoke
n5 0.46).
  main    DFGS2E_step3h6_xf145_W140_dp0p5   dp 0.5, 0-110 s (frames 1-2641), the judged run; r4 and r5 every 3rd frame in the three group
                                            windows [t_fn - 8, t_fn + 6] s (t_fn 48 / 76 / 104 s); max_hours 2.5 per chain (auto_DFGS2.py resumes a
                                            max_hours stop from the last checkpoint), launches of <= 1740 s, checkpoints every 48 frames
  pcheck  PDFGS2E_step3h6_W140_dp0p5_t10    dp 0.5, 0-10 s, PIPELINE CHECK ONLY (never shape-judged); optional (auto_DFGS2.py --pcheck), not
                                            run by default: the bed, VEX, seeding and code path are DFG-S's, whose identical 0.5 m 10 s check
                                            passed (2026-10-18 01:56); the W 140 box, bands and table are covered by the hython build check
Every cfg: DFG-S's 0.5 m parms except W 140 (box), sd0 110 (side band 110-140 m generating to x 180 m / absorbing from 210 m), dir_tf 48 s;
the surface crop stays x 90-200 m, y 0-70 m (= DFG-S); the energy-matched N-layer table (a_sum 10.640186 m, y 0-140 m).
usage:
  py -3.10 -B g52s2_pcfg.py check [--dry]           plan consistency + precheck of pcheck and main (writes plan/precheck_DFGS2.json; --dry: nothing)
  py -3.10 -B g52s2_pcfg.py cfg pcheck|main|all     write <root>/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B g52s2_pcfg.py gate <cfg.json>         the g52s2_chain start gate, dry (reads only) -> json
  py -3.10 -B g52s2_pcfg.py show pcheck|main        print the cfg (not written)
Tags: [measured] [computed] [guess] [chosen].
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "4")
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52s2_common as GC            # noqa: E402
import g52s2_table as TB             # noqa: E402

REF_CFG = GC.DFGS_CFG                # read only [the DFG-S parms that ran at 0.5 m, 2026-10-18 01:56-03:05]
PRESETS = {"pcheck": 0.5, "main": 0.5}
T_END = {"pcheck": 10.0, "main": GC.FOCI[-1] + GC.GROUP_WIN[1]}       # 110 s
MAX_H = {"pcheck": 0.4, "main": 2.5}
PCHECK_WIN = (6.0, 10.0)
PART_LIMIT_M = 7.0
PARMS_DIFFER_FROM_DFGS = ("W", "sd0", "dir_tf")   # half width 140, side band 110-140 m, the focus time by the arrival rule on the W 140 layout
# run-time model [measured: DFG-2 0.5 m launches (same tank code, VEX and records) and DFG-S (measured 1.147 h for 2521 frames at 3.28 Mp peak,
# its estimate was 0.87-1.22 h); guess: breaking substeps (energy-matched sea: more breaking, x 2.0 in the window for the high end), relaunch]
RATE_MP_S = (0.300, 0.330)
SURF_S = 1.98                        # s per r5 frame (crop x 90-200 m, y 0-70 m = DFG-S) [measured x guess]
BREAK_FACTOR = (1.0, 2.0)            # window frames with breaking [guess]
RELAUNCH_S = (60.0, 150.0)           # per relaunch (scene load + checkpoint read) [guess]
GROWTH = 3276925.0 / 2828400.0       # FLIP particles / seeded model particles: DFG-S 0.5 m peak 3.276925 M [measured] over its count_particles
                                     # model 2.8284 M [computed] = 1.159 (DFG-2: 1.102)
DIR_CHECK = dict(x=[10.0, 30.0, 45.0, 100.0, 130.0, 150.0, 195.0, 230.0], y=[-15.0, -8.0, -2.0])


# ====================================================================== the cfg
def parms_DFGS2(dp):
    GC.check_dp(dp, smoke=False)
    b = GC.box52(dp)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=GC.R4_X[0], crop_x1=GC.R4_X[1], crop_z1=GC.CROP_Z1,
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=1.0, sf_on=0.0, dir_on=1.0, dir_tf=GC.T_F, ret_on=1.0, sd_on=1.0, sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW,
             sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW, sd_taper_m=GC.SD_TAPER, sd_gain=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=GC.RAMP_S,
             wall_taper_m=GC.WALL_TAPER, in_gain=1.0, x_p=80.0, xg_end=GC.IN_X1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=0.0,
             volcorr_on=1.0, vol_x0=GC.VOL_X[0], vol_x1=GC.VOL_X[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(GC.SPEC_STEP))
    return p, b


def drift_stage_A():
    return dict(stage="A", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE, window_m=list(GC.VOL_X),
                amendment="plan tank.bands.volume stage A (AM-D18 rule of FLIP50; = DFG-2 / DFG-S)",
                rule="FLIP49 stage A: whole-tank column volume held by a target divergence in x %g-%g m (tau %g s, cap %g /s)"
                     % (GC.VOL_X[0], GC.VOL_X[1], GC.VOL_TAU, GC.VOL_DMAX))


def windows_for(preset, t_end):
    if preset == "pcheck":
        return [list(PCHECK_WIN)]
    return [[t + GC.GROUP_WIN[0], t + GC.GROUP_WIN[1]] for t in GC.FOCI if t + GC.GROUP_WIN[1] <= t_end + 1e-9]


def records(preset, t_end):
    return dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
                r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=GC.R4_Z[0], y1=GC.R4_Z[1], clip_vox=6.0, t0=0.0, every=3),
                r5=dict(t0=0.0, every=3), windows=windows_for(preset, t_end))


_ENERGY = None


def energy_block():
    """the Q84 energy statement carried by every cfg (and copied by g52s2_ana into the judge and the co-equal verdict)."""
    global _ENERGY
    if _ENERGY is None:
        E = TB.energy_in_tank()
        C = GC.components()
        _ENERGY = dict(statement=GC.sea_text(), basis="equal spectral energy (Q84): energy density 0.5 rho g sum a^2 of the incoming components at "
                                                         "the generation depth (h0 20 m here, 19 m for DM1A)",
                       sum_a2_m2=float(np.sum(C["a"] ** 2)), DM1A_sum_a2_m2=GC.DM1A_SUM_A2, scale_vs_DFGS=GC.E_SCALE, a_sum_m=GC.A_SUM,
                       a_max_component_m=float(C["a"].max()), DM1A_a_j_m=GC.DM1A_AJ,
                       in_tank=dict(inlet_variance_over_DM1A=E["DFGS2E"].get("inlet_variance_over_DM1A"),
                                    interior_power_over_DM1A=E["DFGS2E"].get("interior_power_over_DM1A"),
                                    inlet_Hm0_equiv_m=E["DFGS2E"]["inlet_band_Hm0_equiv_m"], DM1A_inlet_Hm0_equiv_m=(E.get("DM1A") or {}).get("inlet_band_Hm0_equiv_m"),
                                    power_into_interior_MW=E["DFGS2E"]["power_into_interior_MW"],
                                    DM1A_power_into_interior_MW=(E.get("DM1A") or {}).get("power_into_interior_MW"),
                                    DFGB_E_for_reference=dict(inlet_variance_over_DM1A=(E.get("DFGB_E") or {}).get("inlet_variance_over_DM1A"),
                                                              interior_power_over_DM1A=(E.get("DFGB_E") or {}).get("interior_power_over_DM1A")),
                                    rule="g52s2_table.energy_in_tank (AM-DFGB1b rule on each tank's own layout) [computed]"),
                       statement_in_tank=E["statement_en"])
    return _ENERGY


def make(preset, dry=False):
    dp = PRESETS[preset]
    pc = preset == "pcheck"
    p, b = parms_DFGS2(dp)
    vox = b["vox"]
    t_end = T_END[preset]
    f_end = GC.frames_for(0.0, t_end)
    tb = TB.table_record(dry=dry)
    rid = GC.run_id(preset)
    root = GC.root_of(preset)
    lr = tb["linear_refs"]
    g0 = lr["G2f_gauges"]["A_n"]["y0.5"]
    H_ref = 2.0 * sum(math.hypot(*v) for v in g0.values())
    en = energy_block()
    c = dict(
        run_id=rid, out_root=root, stage="FLIP52S2", kind=("pcheck" if pc else "3d"),
        case=dict(name="FLIP52S2_%s_DFGS2E_step3h6_W140_dp%s" % (preset, GC.tag(dp)), plan_frozen=GC.PLAN_REL,
                  plan="Unity/Build/FLIP52S2/plan/plan_DFGS2_frozen.json (energy-matched sea, W 140 tank + DFG-S step, records, co-equal criteria with the "
                       "print-like-instant convergence co-requirement, gates, decision, honesty)", campaign="FLIP52S2-DFGS2E",
                  preset=preset, set=GC.SET, role=("PIPELINE CHECK ONLY (0.5 m, 0-10 s; never shape-judged)" if pc else "the judged DFG-S-E140 run"),
                  judged=(not pc), pipeline_check_only=bool(pc),
                  label="DFG-S with ENERGY-MATCHED amplitudes (x %.6f, a_sum %.6f m, sum a^2 = DM1A's: equal spectral energy, Q84) in a W 140 m half "
                        "tank (side band 110-140 m), 1:3 step (toe 108 m, edge 150 m, shelf 6 m), focus (%.0f, 0) at t = %.0f + 28 m s"
                        % (GC.E_SCALE, GC.A_SUM, GC.X_F, GC.T_F),
                  reference_cfg="Unity/Build/FLIP52S/runs/DFGS_step3h6_xf145_dp0p5/cfg.json (parms equal except %s)" % ", ".join(PARMS_DIFFER_FROM_DFGS),
                  a_sum_tag="a_sum = DFG-S's 6.331240 m x %.6f = %.6f m: equal spectral energy with DM1A (user Q84) [computed]" % (GC.E_SCALE, GC.A_SUM)),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_STEP, b),
        sf=GC.sf_descriptor(H_ref=H_ref, note="FLIP52S2: the inflow is the N-layer table cfg dir (P 28 s, n 3/4/5); this descriptor (T 7 s, h0 20 m) "
                                               "is for T, L, c, k only; H = 2 x the sum of the linear per-frequency amplitudes at (60, 0.5) m"),
        dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear periodic multi-frequency directional sea (WKB over the DFG-S step): %d components (3 harmonics of P = 28 s x %d "
                       "directions), phases 0 at (x_f, 0) at t = t_f + 28 m, ENERGY-MATCHED to DM1A (Q84)" % (tb["n_components"], len(tb["theta_deg"])),
                  P_s=GC.P_S, harmonics=list(GC.HARMONICS), T_s=tb["T"], freq_weights=tb["freq_weights"], theta_deg=tb["theta_deg"],
                  dir_weights=tb["dir_weights"], dspec=list(GC.DSPEC), a_sum_m=tb["a_sum"], a_component_max_m=tb["a_max_component"],
                  amp_per_freq_m=tb["amp_per_freq"], x_f_m=GC.X_F, h_f_m=GC.h_of(GC.X_F), t_f_s=GC.T_F, foci_s=list(GC.FOCI), in_gain=1.0, sd_gain=1.0,
                  ramp_s=GC.RAMP_S, focal_crest_linear_m=lr["design_crest_xf_m"], energy=en,
                  chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and weights, a_sum %.6f m (= DFG-S x %.6f: "
                                  "equal spectral energy with DM1A, Q84), focus (%.0f, 0) at t = %.0f + 28 m s, the W 140 tank (side band 110-140 m), "
                                  "the step (toe 108 m, 1:3, shelf 6 m) [chosen]; computed by FLIP: propagation, dispersion, refraction, shoaling, "
                                  "focusing, reflection, the crest's growth, breaking, any jet / plume / bore" % (GC.A_SUM, GC.E_SCALE, GC.X_F, GC.T_F),
                  tags=dict(P="chosen", harmonics="chosen", weights="chosen", directions="chosen", a_sum="computed (energy-matched, Q84)",
                            x_f="chosen (DFG-S screen S7)", t_f="computed (ray arrival on the W 140 layout + 3.9 s)", step="chosen (DFG-S screen S7)",
                            W="chosen (G4 validity, design (a))", table="computed (WKB DirField per harmonic, g52s2_table)")),
        drift=drift_stage_A(), solver=dict(veltransfer="flip", donarrowband=0), records=records(preset, t_end),
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_52S2],
        dir_check=dict(every=(48 if pc else 120), x=list(DIR_CHECK["x"]), y=list(DIR_CHECK["y"]), zl=[0.5 * vox, 40.0, 75.0, 90.0, 120.0]),
        ckpt_on=(0 if pc else 1), ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M,
        disk_stop_free_gb=25.0, max_hours=MAX_H[preset], level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_STILL_X), n1_window=[0.5, 1.5],
        shore_x=GC.X_SHORE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP52S2 DFG-S-E140 %s: 3D dp %g, half tank W 140 m (side band 110-140 m, inlet 0-50 m, flat 20 m, Lx 290 m, exit sponge 210-290 m) "
              "with a laterally uniform 1:3 step (toe 108 m, edge 150 m, 6 m shelf to the end), periodic three-harmonic directional sea P 28 s "
              "(T 9.33 / 7 / 5.6 s), X2 directions, a_sum %.6f m (equal spectral energy with DM1A, Q84), focus (%.0f, 0) (h %.2f m) at t = %s s, "
              "ramp 14 s, stage A, 0-%g s. %s"
              % (preset, dp, GC.A_SUM, GC.X_F, GC.h_of(GC.X_F), " / ".join("%g" % t for t in GC.FOCI if t <= t_end), t_end,
                 "PIPELINE CHECK ONLY (0.5 m, never shape-judged); records hf/r2/r3 every frame, r4 + r5 every 3rd frame in 6-10 s, no checkpoints"
                 if pc else "Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in the three group windows [t_fn - 8, t_fn + 6] s")),
        layout="DFG",
        analysis=dict(layout="DFG", plan_frozen=GC.PLAN_REL, interior_x=list(GC.INTERIOR_X), interior_y=GC.INTERIOR_Y, scan_x=list(GC.SCAN_X),
                      onset_x=list(GC.ONSET_X), foci_s=list(GC.FOCI), P_s=GC.P_S, group_window_s=list(GC.GROUP_WIN), x_toe_m=GC.X_TOE,
                      x_edge_m=GC.X_EDGE, h_top_m=GC.H_TOP, slope_1_in=GC.SLOPE_S, x_f_m=GC.X_F, W_m=GC.W_MAIN, sd0_m=GC.SD0,
                      tool="Tools/GWWaveGen/flip52s2/g52s2_ana.py"))
    c["precheck"] = precheck(c)
    return c


# ====================================================================== checks
def plan_consistency():
    if not os.path.exists(GC.PLAN):
        return dict(ok=False, checks=dict(plan_exists=False))
    pl = GC.plan()
    T = pl["tank"]; S = pl["sea"]; R = pl["records"]
    ck = {}
    ck["plan_sha256"] = GC.plan_sha_ok()
    ck["tank"] = bool(T["h0_m"] == GC.H0 and T["Lx_m"] == GC.LX and T["W_m"] == GC.W_MAIN and T["z_bed_m"] == GC.ZB and T["z_top_m"] == GC.Z_TOP
                      and T["solver"]["gridscale"] == 2.0 and T["solver"]["cfl"] == 1.0 and T["solver"]["maxsub"] == 8 and T["solver"]["pcfl"] == 0.75)
    st = T["step"]
    ck["step"] = bool(st["x_toe_m"] == GC.X_TOE and st["slope_1_in"] == GC.SLOPE_S and st["h_top_m"] == GC.H_TOP and st["x_edge_m"] == GC.X_EDGE
                      and st["ctrl"] == {k: GC.bed_parms(GC.SPEC_STEP)[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h")})
    B = T["bands"]
    ck["bands"] = bool(B["inlet"]["xg_end"] == GC.IN_X1 and B["inlet"]["wall_taper_m"] == GC.WALL_TAPER and B["side"]["sd0"] == GC.SD0
                       and B["side"]["sd_gen"] == GC.SD_GEN and B["side"]["sd_sw"] == GC.SD_SW and B["side"]["sd_sigma"] == GC.SD_SIGMA
                       and B["side"]["sd_pow"] == GC.SD_POW and B["side"]["sd_taper_m"] == GC.SD_TAPER and B["side"]["y_m"] == [GC.SD0, GC.W_MAIN]
                       and B["exit_sponge"]["abs_on"] == 1 and B["exit_sponge"]["xa0"] == GC.XA0 and B["exit_sponge"]["abs_sigma"] == GC.ABS_SIGMA
                       and B["exit_sponge"]["abs_pow"] == GC.ABS_POW and B["ret_on"] == 1 and B["dir_on"] == 1 and B["volume"]["vol_x_m"] == list(GC.VOL_X))
    ck["parms_differ_named"] = bool(T["parms_differ_from_DFGS"] == list(PARMS_DIFFER_FROM_DFGS))
    ck["crop_as_DFGS"] = bool(T.get("surface_crop_z1_m") == GC.CROP_Z1)
    C = GC.components()
    ck["sea_P_harmonics"] = bool(S["P_s"] == GC.P_S and S["harmonics_n"] == list(GC.HARMONICS) and S["ramp_s"] == GC.RAMP_S)
    ck["sea_focus"] = bool(S["focus"]["x_m"] == GC.X_F and S["focus"]["y_m"] == 0.0 and S["focus"]["t_f_s"] == GC.T_F
                           and S["focus"]["times_s"] == list(GC.FOCI))
    ck["sea_set_bit_for_bit"] = bool([round(float(v), 6) for v in C["th"]] == S["directions_deg"] and [round(float(v), 6) for v in C["wd"]] == S["dir_weights"]
                                     and [round(float(v), 6) for v in C["wf"]] == S["freq_weights"] and C["a"].size == S["n_components"])
    ck["sea_a_sum"] = bool(abs(C["a_sum"] - S["a_sum_m"]) < 1e-6 and round(float(C["a"].max()), 6) == S["a_max_component_m"]
                           and [round(float(C["a_sum"] * v), 6) for v in C["wf"]] == S["amp_per_freq_m"])
    ck["energy_equals_DM1A"] = bool(abs(float(np.sum(C["a"] ** 2)) - GC.DM1A_SUM_A2) < 1e-9 and abs(S["sum_a2_m2"] - round(GC.DM1A_SUM_A2, 6)) < 1e-9
                                    and S["energy"]["basis"].startswith("equal spectral energy (Q84)"))
    try:
        import g52_common as G52
        th2, wd2 = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
        C2 = G52.components("DFG2")
        ck["sea_equals_DFG2_set_x_scale"] = bool(np.array_equal(th2, C["th"]) and np.array_equal(wd2, C["wd"])
                                                 and np.allclose(C2["a"] * GC.E_SCALE, C["a"], rtol=1e-14, atol=0)
                                                 and abs(G52.A_SUM * GC.E_SCALE - C["a_sum"]) < 1e-12 and list(G52.HARMONICS) == list(GC.HARMONICS)
                                                 and G52.P_S == GC.P_S)
    except Exception as e:
        ck["sea_equals_DFG2_set_x_scale"] = False
        ck["dfg2_error"] = repr(e)[:200]
    am = GC.am_dfgb1_sea()
    ck["sea_equals_AM_DFGB1_registered"] = bool(am and abs(am["a_sum_m"] - C["a_sum"]) < 1e-8 and am["a_max_component_m"] == round(float(C["a"].max()), 6)
                                                and am["amp_per_freq_m"] == [round(float(C["a_sum"] * v), 6) for v in C["wf"]]
                                                and am["sum_a2_m2"] == round(float(np.sum(C["a"] ** 2)), 6) and abs(am["scale"] - GC.E_SCALE) < 1e-8)
    ck["records"] = bool(R["t_end_s"] == {"main": T_END["main"], "pcheck": T_END["pcheck"]} and R["group_window_s"] == list(GC.GROUP_WIN)
                         and R["r4_x_m"] == list(GC.R4_X) and "every 48 frames" in R["checkpoints"] and R["pcheck_window_s"] == list(PCHECK_WIN))
    ck["max_hours"] = bool(pl["cost"]["max_hours"] == MAX_H)
    ok = all(v for k, v in ck.items() if isinstance(v, bool))
    return dict(ok=bool(ok), checks=ck)


def time_estimate(n, c):
    """DFG-2-measured rates scaled by this cfg's particle count (see the constants above)."""
    nf = int(c["f_end"]) - int(c.get("f_start", 1)) + 1
    Mp = n * GROWTH / 1e6
    wins = c["records"]["windows"]
    ev = int((c["records"].get("r5") or {}).get("every", 3))
    heavy = [f for f in range(int(c.get("f_start", 1)), int(c["f_end"]) + 1) if any(a - 1e-9 <= (f - 1) / GC.FPS <= b + 1e-9 for a, b in wins)]
    r5 = sum(1 for f in heavy if (f - 1) % ev == 0)
    light = nf - len(heavy)
    lo = RATE_MP_S[0] * Mp * nf + SURF_S * r5
    hi = RATE_MP_S[1] * Mp * (light + BREAK_FACTOR[1] * len(heavy)) + SURF_S * r5
    nl_lo = max(1, math.ceil(lo / c["wall_limit_s"])); nl_hi = max(1, math.ceil(hi / c["wall_limit_s"]))
    lo += (nl_lo - 1) * RELAUNCH_S[0] + 60.0
    hi += nl_hi * RELAUNCH_S[1] + 60.0
    dfgs_scaled = 1.147 * (Mp / 3.276925) * (nf / 2521.0)
    return dict(frames=nf, frames_window=len(heavy), r5_frames=r5, particles_M=Mp, launches=[nl_lo, nl_hi + 1], est_h=[lo / 3600.0, hi / 3600.0],
                DFGS_measured_scaled_h=dfgs_scaled,
                rule="DFG-2 0.5 m rates: %.3f-%.3f s per Mp per frame, r5 %.2f s per frame (crop x 90-200 m, y 0-70 m), window frames x %.1f for "
                     "breaking substeps (high), %g-%g s per relaunch, 60 s scene load [measured rates, guessed margins]; beside it DFG-S's measured "
                     "1.147 h scaled by particles and frames" % (RATE_MP_S[0], RATE_MP_S[1], SURF_S, BREAK_FACTOR[1], RELAUNCH_S[0], RELAUNCH_S[1]))


def precheck(c):
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", wall="computed (DFG-2 measured rates)"))
    ck = out["checks"]
    pc = plan_consistency()
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    dp = float(P["dp"])
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    Vstep = float(np.sum(GC.step_depth(np.arange(0.0, GC.LX, 0.25) + 0.125)) * 0.25 * GC.W_MAIN)
    out.update(particles_model=int(n), water_m3=float(V), water_m3_step_analytic=Vstep, particles_DFGS_model=2828400,
               volume_ratio_vs_DFGS=float(V) / (Vstep * GC.W_DFGS / GC.W_MAIN), particles_peak_M=[n * GROWTH / 1e6, n * GROWTH * 1.03 / 1e6],
               particles_peak_rule="model x %.4f (DFG-S's measured peak / model) [measured ratio], high x 1.03 for breaking [guess]" % GROWTH)
    ck["particles_le_limit"] = bool(n * GROWTH * 1.03 / 1e6 <= PART_LIMIT_M)
    ck["water_volume_is_step"] = bool(abs(float(V) / Vstep - 1.0) < 0.01)
    b = c["box"]
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["W"]) == GC.W_MAIN and float(P["zb"]) == GC.ZB and float(P["Hz"]) == GC.Z_TOP - GC.ZB
                     and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0 and b["z_top"] == GC.Z_TOP and float(P["gridscale"]) == 2.0
                     and float(P["W"]) == 140.0 and c["level_box"] == [0.0, GC.LX, 0.0, 140.0])
    bs = GC.bed_selfcheck()
    out["bed_selfcheck"] = {k: v for k, v in bs.items() if k not in ("note",)}
    ck["bed_is_step"] = bool(bs["ok"] and not GC.is_new(spec) and spec.get("k_end") is None and float(spec["x_toe"]) == GC.X_TOE
                             and float(spec["s"]) == GC.SLOPE_S and float(spec["shelf_h"]) == GC.H_TOP and float(spec["k"]) == 0.0
                             and float(c["bed"].get("max_depth_m", -1)) == GC.H0 and float(c["bed"].get("min_depth_m", -1)) == GC.H_TOP)
    try:
        ref = json.load(open(REF_CFG, encoding="utf8"))["parms"]
        diff = sorted(k for k in set(ref) | set(P) if k not in PARMS_DIFFER_FROM_DFGS and (k not in ref or k not in P or float(ref[k]) != float(P[k])))
        ck["parms_equal_DFGS_except_named"] = bool(not diff)
        out["parms_diff_vs_DFGS"] = diff
        out["named_differences"] = {k: dict(DFGS=ref.get(k), DFGS2E=P.get(k)) for k in PARMS_DIFFER_FROM_DFGS}
    except Exception as e:
        ck["parms_equal_DFGS_except_named"] = False
        out["parms_diff_vs_DFGS"] = repr(e)[:200]
    ck["bands"] = bool(float(P["relax_on"]) == 1.0 and float(P["sd_on"]) == 1.0 and float(P["abs_on"]) == 1.0 and float(P["dir_on"]) == 1.0
                       and float(P["ret_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and float(P["xg_end"]) == GC.IN_X1 and float(P["wall_taper_m"]) == GC.WALL_TAPER
                       and float(P["sd0"]) == GC.SD0 and float(P["sd0"]) == 110.0 and float(P["sd_gen"]) == GC.SD_GEN and float(P["sd_sw"]) == GC.SD_SW
                       and float(P["sd_sigma"]) == GC.SD_SIGMA and float(P["sd_pow"]) == GC.SD_POW and float(P["sd_taper_m"]) == GC.SD_TAPER
                       and float(P["xa0"]) == GC.XA0 and float(P["abs_sigma"]) == GC.ABS_SIGMA and float(P["abs_pow"]) == GC.ABS_POW
                       and float(P["in_gain"]) == 1.0 and float(P["sd_gain"]) == 1.0 and float(P["relax_g"]) == 1.0
                       and float(P["ramp_s"]) == GC.RAMP_S and float(P["dir_tf"]) == GC.T_F and float(P["set_P"]) == 0.0 and float(P["crop_z1"]) == GC.CROP_Z1)
    D = c["drift"]
    ck["drift_stage_A"] = bool(D["stage"] == "A" and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0 and float(P["hold_on"]) == 0.0
                               and float(P["vol_x0"]) == GC.VOL_X[0] and float(P["vol_x1"]) == GC.VOL_X[1] and D.get("V_measure") == GC.VOL_MEASURE)
    ck["solver"] = bool(float(P["cfl"]) == 1.0 and float(P["maxsub"]) == 8.0 and float(P["minsub"]) == 1.0 and float(P["pcfl"]) == 0.75
                        and c["solver"].get("veltransfer") == "flip")
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
                    and float(info["x1"]) >= GC.SD_SW and info.get("bed") == GC.BED_DF
                    and info.get("content_sha256") == (GC.plan().get("table_npz") or {}).get("content_sha256"))
    except Exception as e:
        out["table_error"] = repr(e)[:200]
    ck["table_is_plan_set"] = ok_t
    tc = GC.PLAN_DIR + "/table_check_DFGS2.json"
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    ck["table_G1_checked"] = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256"))
    en = (c.get("wave") or {}).get("energy") or {}
    ck["energy_statement"] = bool(en.get("statement", "").startswith("equal spectral energy (Q84)") and abs(float(en.get("sum_a2_m2", 0.0)) - GC.DM1A_SUM_A2) < 1e-9
                                  and (en.get("in_tank") or {}).get("interior_power_over_DM1A") is not None)
    ck["sf_descriptor"] = bool((c.get("sf") or {}).get("descriptor") is True and float(c["sf"]["T"]) == GC.T_WAVE and float(c["sf"]["h"]) == GC.H0)
    rec = c["records"]
    preset = (c.get("case") or {}).get("preset")
    wins = rec.get("windows") or []
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and (rec.get("r4") or {}).get("x") == list(GC.R4_X) and (rec.get("r4") or {}).get("z1") == GC.R4_Y1
                                     and wins == windows_for(preset, c["t_end_s"]) and len(wins) == (1 if preset == "pcheck" else 3)
                                     and (rec.get("r5") or {}).get("every") == 3)
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in wins))
    ck["t_end_frames"] = bool(c["t_end_s"] == T_END[preset] and int(c["f_end"]) == GC.frames_for(0.0, T_END[preset]))
    ck["gauges"] = bool(c["gauges"]["x"][0] == 60.0 and c["gauges"]["y"] == list(GC.GAUGE_Y) and max(c["gauges"]["y"]) < GC.SD0)
    regs = c.get("level_regions") or []
    ck["level_regions"] = bool(all(0.0 <= r[1] < r[2] <= float(P["Lx"]) for r in regs) and all(nm in [r[0] for r in regs] for nm in ("band_core", "probe_c", "window",
                                                                                                                                   "face", "shelf")))
    ck["checkpoints"] = bool(c["ckpt_every"] == 48 and c["wall_limit_s"] == 1740 and c["ckpt_on"] == (0 if preset == "pcheck" else 1))
    ck["out_root_absolute_FLIP52S2"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(GC.B52S2 + "/")
                                            and os.path.join(GC.B52S2, c["out_root"]).replace("\\", "/") == c["out_root"].replace("\\", "/"))
    ck["plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == GC.PLAN_REL and (c.get("analysis") or {}).get("plan_frozen") == GC.PLAN_REL)
    te = time_estimate(n, c)
    out["time"] = te
    ck["time_within_max_hours"] = bool(te["est_h"][1] <= float(c["max_hours"]))
    ck["max_hours_is_plan_cap"] = bool(float(c["max_hours"]) == MAX_H[preset])
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
    """dry copy of the g52s2_chain.py start gate (same conditions; reads only)."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if not os.path.exists(GC.BUILD_CHECK):
        bad.append("build_check52s2.json missing (py -3.10 x52s2_build.py)")
    else:
        bc = json.load(open(GC.BUILD_CHECK, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check52s2 all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check52s2")
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
    rd = os.path.join(GC.B52S2, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP52S2=rd.startswith(GC.B52S2 + "/"), hip=GC.HIP,
                hip_sha256=GC.sha256_file(GC.HIP) if os.path.exists(GC.HIP) else None)


def check_all(dry=False):
    out = dict(plan=GC.PLAN_REL, plan_consistency=plan_consistency(), presets={})
    for pr in ("pcheck", "main"):
        c = make(pr, dry=dry)
        out["presets"][pr] = dict(run_id=c["run_id"], precheck=c["precheck"], cfg_sha16=GC.sha16_json(c))
    out["ok"] = bool(out["plan_consistency"]["ok"] and all(v["precheck"]["ok"] for v in out["presets"].values()))
    if not dry:
        GC.jdump(out, GC.PLAN_DIR + "/precheck_DFGS2.json")
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
                                                        time_DFGS_scaled=v["precheck"]["time"]["DFGS_measured_scaled_h"],
                                                        parms_diff_vs_DFGS=v["precheck"].get("parms_diff_vs_DFGS"))
                                                for k, v in o["presets"].items()})), ensure_ascii=False))
    elif a[0] in ("cfg", "show") and len(a) >= 2:
        names = ["pcheck", "main"] if a[1] == "all" else [a[1]]
        for pr in names:
            if pr not in PRESETS:
                print(__doc__); sys.exit(1)
            c = make(pr, dry=(a[0] == "show"))
            if a[0] == "show":
                print(json.dumps(GC.clean(c), ensure_ascii=False, indent=1)); continue
            if not c["precheck"]["ok"]:
                print(json.dumps(dict(preset=pr, written=None, precheck_ok=False, reason=c["precheck"]["reason"]), ensure_ascii=False)); continue
            p = write(c)
            print(json.dumps(GC.clean(dict(preset=pr, run_id=c["run_id"], written=p, sha256=GC.sha256_file(p), precheck_ok=True,
                                           particles=c["precheck"]["particles_model"], time_h=c["precheck"]["time"]["est_h"])), ensure_ascii=False))
    elif a[0] == "gate" and len(a) >= 2:
        print(json.dumps(gate(a[1]), ensure_ascii=False))
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
