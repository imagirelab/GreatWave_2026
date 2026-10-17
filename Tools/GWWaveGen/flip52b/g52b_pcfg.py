# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: run configurations (cfg.json) with their prechecks, the consistency check of every constant against the frozen plan,
and a dry copy of the g52b_chain start gate (py -3.10 -B). 2026-10-17 written new (Claude). Reads only the frozen plan, the FLIP52B table,
the plan E X2 0.5 m cfg (Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/cfg.json, read only: the D19B parms every DFG-2B parm must equal
except the named differences). Writes only Unity/Build/FLIP52B/<smoke|runs>/ready/<run_id>.json and plan/precheck_DFGB.json.

Presets (plan_DFGB_frozen.json; nothing here is tuned):
  smoke  S52BDFG2_D19B_xf272p25_dp1p0  dp 1.0, 0 - (t_f1 + 6) s, PIPELINE CHECK ONLY (never shape-judged); records hf, r2, r3 every frame, r4 every
                                      3rd frame in the group-1 window; no r5; max_hours 0.5
  main   DFG2B_D19B_xf272p25_dp0p5     dp 0.5, 0 - (t_f3 + 6) s, the judged run; r4 and r5 every 3rd frame in the three group windows
                                      [t_fn - 8, t_fn + 6] s; max_hours 3.0 (hard cap), launches of <= 1740 s, checkpoints every 48 frames
Every cfg: the plan E X2 D19B parms (half tank W 140 m, side band 95-140 m generating to 180.25 m / absorbing from 210.25 m, inlet band
0-100 m, taper 20 m, no exit sponge, D19B bed, Lx 412 m, z -19 .. +17 m, drift stage A x 110-400 m, ramp 14 s, crop / surface parms) with
dir_tf = t_f1 and the N-layer DFG-2B table (dir_on 1, ret_on 1).
usage:
  py -3.10 -B g52b_pcfg.py check [--dry]           plan consistency + precheck of smoke and main (writes plan/precheck_DFGB.json; --dry: nothing)
  py -3.10 -B g52b_pcfg.py cfg smoke|main|all      write <root>/ready/<run_id>.json (precheck inside; not written if it fails)
  py -3.10 -B g52b_pcfg.py gate <cfg.json>         the g52b_chain start gate, dry (reads only) -> json
  py -3.10 -B g52b_pcfg.py show smoke|main         print the cfg (not written)
Tags: [measured] [computed] [guess] [chosen].
2026-10-18 (Claude) AM-DFGB1 (user Q84): with G52B_SEA=E (g52b_common) the same presets write the energy-matched cfgs S52BDFGB2E_D19B_xf272p25_dp1p0 /
DFGB2E_D19B_xf272p25_dp0p5 (set DFG2BE, table DFGBE_*, a_sum = 1.680585 x 6.331240 m: sum a^2 = DM1A's), checked against the AM-DFGB1 sea
numbers (g52b_common.plan_sea) and against DM1A's own cfg (energy_equals_DM1A); precheck file plan/precheck_DFGBE.json. G52B_SEA unset: as frozen.
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52b_common as GC             # noqa: E402
import g52b_table as TB              # noqa: E402

X2_CFG = GC.REPO + "/Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/cfg.json"     # read only [the D19B parms that ran at 0.5 m]
DM1A_CFG = GC.REPO + "/Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json"   # read only (AM-DFGB1 energy check)
PRESETS = {"smoke": 1.0, "main": 0.5}
T_END = {1.0: GC.T_F + GC.GROUP_WIN[1], 0.5: GC.FOCI[-1] + GC.GROUP_WIN[1]}
MAX_H = {1.0: 0.5, 0.5: 3.0}
# run-time model [measured: plan E X2 0.5 m launches, same tank and records; X2 1.0 m smoke]
RATE_LIGHT_S = 1.954                 # s per frame outside the r4 / r5 windows (X2 launch 1: 891 frames in 1741 s, 6.04 M particles) [measured]
RATE_HEAVY_S = 3.00                  # s per frame inside the windows (X2 launches 2-3: 941 frames in 2824 s, r4 + r5 every 3rd frame) [measured]
RELAUNCH_FRAMES = 26                 # frames recomputed per relaunch (X2: launch 2 started at 865 after 891 done) [measured]
SMOKE_RATE_S = 0.319                 # s per frame at dp 1.0 (X2 smoke: 1801 frames in 575 s, 0.82 M particles) [measured]
PART_LIMIT_M = 7.0
DIR_CHECK = dict(every=120, x=[10.0, 40.0, 70.0, 95.0, 150.0, 200.0], y=[-15.0, -8.0, -2.0], zl=[0.5, 50.0, 100.0, 120.0])   # = X2 cfg
PARMS_DIFFER_FROM_X2 = ("dir_tf", "dp", "ox", "oy", "oz")       # dir_tf = t_f1 (X2: 0 = t_f mod 7 s); dp / offsets follow dp


# ====================================================================== the cfg
def parms_D(dp):
    smoke = float(dp) == 1.0
    GC.check_dp(dp, smoke=smoke)
    b = GC.box52(dp)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=0.0, crop_x1=b["Lx"], crop_z1=GC.SD0,
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=0.0, sf_on=0.0, dir_on=1.0, dir_tf=GC.T_F, ret_on=1.0, sd_on=1.0, sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW,
             sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW, sd_taper_m=GC.SD_TAPER, sd_gain=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=GC.RAMP_S,
             wall_taper_m=GC.WALL_TAPER, in_gain=1.0, x_p=80.0, xg_end=GC.IN_X1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=0.0,
             volcorr_on=1.0, vol_x0=GC.VOL_X[0], vol_x1=GC.VOL_X[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(GC.SPEC_BED))
    return p, b


def drift_stage_A():
    return dict(stage="A", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE, window_m=list(GC.VOL_X),
                amendment="AM-D18 (as plan E X2)",
                rule="FLIP49 stage A: whole-tank column volume held by a target divergence in x %g-%g m (tau %g s, cap %g /s)"
                     % (GC.VOL_X[0], GC.VOL_X[1], GC.VOL_TAU, GC.VOL_DMAX))


def windows_for(t_end):
    return [[t + GC.GROUP_WIN[0], t + GC.GROUP_WIN[1]] for t in GC.FOCI if t + GC.GROUP_WIN[1] <= t_end + 1e-9]


def records(dp, t_end):
    smoke = float(dp) == 1.0
    return dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
                r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=GC.R4_Z[0], y1=GC.R4_Z[1], clip_vox=6.0, t0=0.0, every=3),
                r5=(None if smoke else dict(t0=0.0, every=3)), windows=windows_for(t_end))


def make(preset, dry=False):
    dp = PRESETS[preset]
    smoke = dp == 1.0
    p, b = parms_D(dp)
    t_end = T_END[dp]
    f_end = GC.frames_for(0.0, t_end)
    tb = TB.table_record(dry=dry)
    rid = GC.run_id(dp)
    root = GC.SMOKE_ROOT if smoke else GC.RUNS_ROOT
    lr = tb["linear_refs"]
    g0 = lr["G2f_gauges"]["A_n"]["y0.5"]
    H_ref = 2.0 * sum(math.hypot(*v) for v in g0.values())
    c = dict(
        run_id=rid, out_root=root, stage="FLIP52B", kind=("smoke" if smoke else "3d"),
        case=dict(name="FLIP52B_%s_%s_D19B_dp%s" % (preset, GC.SET, GC.tag(dp)), plan_frozen=GC.PLAN_REL, plan="Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json "
                  "(sea, tank, records, co-equal criteria: print view + print ruler + convergence, gates, decision, honesty)", campaign="FLIP52B-DFG2B",
                  preset=preset, set=GC.SET, **({"amendment": GC.AMENDMENT_ID} if GC.SEA == "E" else {}), role=("pipeline check only (never shape-judged)" if smoke else "the judged DFG-2B run"),
                  judged=(not smoke), pipeline_check_only=bool(smoke), P1_x_max_m=330.0, dir_case="DFG2B",
                  label=("DFG-2 sea (P 28 s, T 9.33/7/5.6 s, X2 directions, %s) in the D19B tank, focus (%.2f, 0) on the 1:10 slope"
                         % ("total energy = DM1A (AM-DFGB1)" if GC.SEA == "E" else "a_sum = DM1A", GC.X_F)),
                  reference_cfg="Unity/Build/FLIP51/runs/S51X2_D19B_T7_g60s28_dp0p5/cfg.json (parms equal except %s)" % ", ".join(PARMS_DIFFER_FROM_X2),
                  a_sum_tag=GC.sea_text() + " [chosen]"),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_BED, b),
        sf=GC.sf_descriptor(H_ref=H_ref, note="FLIP52B: the inflow is the N-layer table cfg dir (P 28 s, n 3/4/5); this descriptor (T 7 s, h0 19 m) "
                                               "is for T, L, c, k only; H = 2 x the sum of the linear per-frequency amplitudes at (110, 0.5) m"),
        dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear periodic multi-frequency directional sea (WKB over D19B): %d components (3 harmonics of P = 28 s x %d directions), "
                       "phases 0 at (x_f, 0) at t = t_f + 28 m" % (tb["n_components"], len(tb["theta_deg"])),
                  P_s=GC.P_S, harmonics=list(GC.HARMONICS), T_s=tb["T"], freq_weights=tb["freq_weights"], theta_deg=tb["theta_deg"],
                  dir_weights=tb["dir_weights"], dspec=list(GC.DSPEC), a_sum_m=tb["a_sum"], a_component_max_m=tb["a_max_component"],
                  amp_per_freq_m=tb["amp_per_freq"], x_f_m=GC.X_F, h_f_m=GC.h_of(GC.X_F), t_f_s=GC.T_F, foci_s=list(GC.FOCI), in_gain=1.0, sd_gain=1.0,
                  ramp_s=GC.RAMP_S, focal_crest_linear_m=lr["design_crest_xf_m"],
                  chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the 34 X2 directions and weights, %s, "
                                  "focus (%.2f, 0) at t = %.0f + 28 m s, the D19B tank and its option-D bands [chosen]; computed by FLIP: propagation, "
                                  "dispersion, refraction, shoaling, focusing, the crest's growth, breaking, any jet / plume"
                                  % (("a_sum %.6f m (total wave energy = DM1A, AM-DFGB1)" % GC.A_SUM) if GC.SEA == "E"
                                     else "a_sum 6.331240 m (= DM1A, not enlarged)", GC.X_F, GC.T_F),
                  tags=dict(P="chosen", harmonics="chosen", weights="chosen", directions="chosen",
                            a_sum=("chosen (total energy = DM1A, AM-DFGB1)" if GC.SEA == "E" else "chosen (= DM1A)"), x_f="chosen by the screen rule",
                            t_f="computed (ray arrival + 3.9 s)", table="computed (WKB DirField per harmonic, g52b_table)")),
        drift=drift_stage_A(), solver=dict(veltransfer="flip", donarrowband=0), records=records(dp, t_end),
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_52B],
        dir_check=copy.deepcopy(DIR_CHECK), ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740,
        level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0, max_hours=MAX_H[dp], level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_STILL_X),
        n1_window=[0.5, 1.5], shore_x=GC.X_SHORE, fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP52B DFG-2B%s %s: 3D dp %g, the D19B tank of plan E X2 (half tank W 140 m, side band 95-140 m, h0 19 m, 1:10 beach from x 160.25 m, "
              "Lx 412 m, no exit sponge), periodic three-harmonic directional sea P 28 s (T 9.33 / 7 / 5.6 s), X2 directions, %s, "
              "focus (%.2f, 0) (h %.2f m) at t = %s s, ramp 14 s, stage A, 0-%g s. %s"
              % (" (energy-matched, AM-DFGB1)" if GC.SEA == "E" else "", preset, dp,
                 (GC.sea_text() if GC.SEA == "E" else "a_sum 6.331240 m (= DM1A)"), GC.X_F, GC.h_of(GC.X_F),
                 " / ".join("%g" % t for t in GC.FOCI if t <= t_end), t_end,
                 "PIPELINE CHECK ONLY (never shape-judged); records hf/r2/r3 every frame, r4 every 3rd frame in the group window, no r5" if smoke else
                 "Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in the three group windows [t_fn - 8, t_fn + 6] s")),
        layout="D",
        analysis=dict(layout="D", p1_x_max_m=330.0, crest_x_min_m=150.0, crest_window="centre_half_L", side_band_m=[70.0, 84.0], vol_x_m=list(GC.VOL_X),
                      report_levels=["break_front", "inner_surf", "swash", "side_surf"], setup_region="swash", plan_frozen=GC.PLAN_REL,
                      x_toe_m=GC.X_TOE, x_f_m=GC.X_F, x_break_target_m=281.5, x_shore_m=GC.X_SHORE, yfar_m=90.0, dir_case="DFG2B",
                      foci_s=list(GC.FOCI), P_s=GC.P_S, group_window_s=list(GC.GROUP_WIN), tool="Tools/GWWaveGen/flip52b/g52b_ana.py"))
    c["precheck"] = precheck(c)
    return c


# ====================================================================== checks
def plan_consistency():
    if not os.path.exists(GC.PLAN):
        return dict(ok=False, checks=dict(plan_exists=False))
    pl = GC.plan()
    T = pl["tank"]; S = GC.plan_sea(); R = pl["records"]          # AM-DFGB1: S carries the E a_sum numbers when G52B_SEA=E
    ck = {}
    ck["plan_sha256"] = GC.plan_sha_ok()
    ck["tank"] = bool(T["h0_m"] == GC.H0 and T["Lx_m"] == GC.LX and T["W_m"] == GC.W_MAIN and T["z_bed_m"] == GC.ZB and T["z_top_m"] == GC.Z_TOP
                      and T["x_toe_m"] == GC.X_TOE and T["slope_1_in"] == GC.SLOPE_S and T["solver"]["gridscale"] == 2.0 and T["solver"]["cfl"] == 1.0
                      and T["solver"]["maxsub"] == 8 and T["solver"]["pcfl"] == 0.75)
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
    try:
        import g52_common as G52
        th2, wd2 = G52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
        a_ref = G52.A_SUM * (GC.E_SCALE if GC.SEA == "E" else 1.0)
        ck["dirset_equals_DFG2"] = bool(np.array_equal(th2, C["th"]) and np.array_equal(wd2, C["wd"]) and abs(a_ref - C["a_sum"]) < 1e-12 * max(a_ref, 1.0))
    except Exception as e:
        ck["dirset_equals_DFG2"] = False
        ck["dirset_error"] = repr(e)[:200]
    if GC.SEA == "E":                     # AM-DFGB1: sum a^2 at h0 = DM1A's, from DM1A's own cfg (n, a_j), and the registered set name
        try:
            dm = json.load(open(DM1A_CFG, encoding="utf8"))["dir"]
            s_dm = float(int(dm["n"]) * float(dm["a_j"]) ** 2)
            ck["energy_equals_DM1A"] = bool(abs(float(np.sum(C["a"] ** 2)) / s_dm - 1.0) < 1e-9 and abs(float(S["sum_a2_m2"]) / s_dm - 1.0) < 1e-5
                                            and S.get("set") == GC.SET)
        except Exception as e:
            ck["energy_equals_DM1A"] = False
            ck["energy_error"] = repr(e)[:200]
    ck["records"] = bool(R["t_end_s"] == {"dp0p5": T_END[0.5], "dp1p0": T_END[1.0]} and R["group_window_s"] == list(GC.GROUP_WIN)
                         and "every 48 frames" in R["checkpoints"])
    ok = all(v for k, v in ck.items() if isinstance(v, bool))
    return dict(ok=bool(ok), checks=ck)


def time_estimate(c):
    P = c["parms"]; dp = float(P["dp"])
    nf = int(c["f_end"]) - int(c.get("f_start", 1)) + 1
    if dp == 1.0:
        s = SMOKE_RATE_S * nf
        return dict(frames=nf, est_h=[s / 3600.0, 1.3 * s / 3600.0], rule="X2 1.0 m smoke 0.319 s per frame (0.82 M particles) x 1.0-1.3 [measured rate]")
    wins = c["records"]["windows"]
    heavy = sum(1 for f in range(1, int(c["f_end"]) + 1) if any(a - 1e-9 <= (f - 1) / GC.FPS <= b + 1e-9 for a, b in wins))
    light = nf - heavy
    s = RATE_LIGHT_S * light + RATE_HEAVY_S * heavy
    nl = int(math.ceil(s / c["wall_limit_s"]))
    s_lo = s + (nl - 1) * RELAUNCH_FRAMES * RATE_HEAVY_S
    s_hi = 1.12 * s + nl * (RELAUNCH_FRAMES * RATE_HEAVY_S + 60.0)
    return dict(frames=nf, frames_heavy=heavy, frames_light=light, launches=[nl, nl + 1], est_h=[s_lo / 3600.0, s_hi / 3600.0],
                rule="plan E X2 0.5 m (same tank): %.3f s/frame outside the r4/r5 windows, %.2f s/frame inside, %d frames redone per relaunch; "
                     "high = x 1.12 + 60 s per launch [measured rates, guessed margin]" % (RATE_LIGHT_S, RATE_HEAVY_S, RELAUNCH_FRAMES))


def precheck(c):
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", wall="computed (measured X2 rates)"))
    ck = out["checks"]
    pc = plan_consistency()
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    dp = float(P["dp"])
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V))
    ck["particles_le_limit"] = bool(n * 1.16 / 1e6 <= PART_LIMIT_M)
    b = c["box"]
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["W"]) == GC.W_MAIN and float(P["zb"]) == GC.ZB and float(P["Hz"]) == GC.Z_TOP - GC.ZB
                     and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0 and b["z_top"] == GC.Z_TOP and float(P["gridscale"]) == 2.0)
    ck["bed_is_D19B"] = bool(not GC.is_new(spec) and float(spec["x_toe"]) == GC.X_TOE and float(spec["s"]) == GC.SLOPE_S and float(spec["k"]) == 0.0
                             and float(c["bed"].get("max_depth_m", -1)) == GC.H0)
    # the parms equal the plan E X2 0.5 m cfg except the named differences (dp and the offsets follow dp; dir_tf = t_f1)
    try:
        x2 = json.load(open(X2_CFG, encoding="utf8"))["parms"]
        diff = sorted(k for k in set(x2) | set(P) if k not in PARMS_DIFFER_FROM_X2 and (k not in x2 or k not in P or float(x2[k]) != float(P[k])))
        ck["parms_equal_X2_except_named"] = bool(not diff)
        out["parms_diff_vs_X2"] = diff
    except Exception as e:
        ck["parms_equal_X2_except_named"] = False
        out["parms_diff_vs_X2"] = repr(e)[:200]
    ck["bands"] = bool(float(P["relax_on"]) == 1.0 and float(P["sd_on"]) == 1.0 and float(P["abs_on"]) == 0.0 and float(P["dir_on"]) == 1.0
                       and float(P["ret_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and float(P["dir_tf"]) == GC.T_F and float(P["ramp_s"]) == GC.RAMP_S
                       and float(P["in_gain"]) == 1.0 and float(P["sd_gain"]) == 1.0 and float(P["set_P"]) == 0.0)
    ck["drift_stage_A"] = bool(c["drift"]["stage"] == "A" and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0 and float(P["hold_on"]) == 0.0)
    dr = c.get("dir") or {}
    ck["table_file_sha"] = bool(os.path.exists(dr.get("npz") or "") and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ok_t = False
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        S = GC.plan_sea()
        ok_t = bool(info.get("set") == GC.SET and float(info["P"]) == S["P_s"] and info["harmonics"] == S["harmonics_n"]
                    and [round(float(v), 6) for v in info["theta_deg"]] == S["directions_deg"] and [round(float(v), 6) for v in info["dir_weights"]] == S["dir_weights"]
                    and [round(float(v), 6) for v in info["freq_weights"]] == S["freq_weights"] and abs(float(info["a_sum"]) - S["a_sum_m"]) < 1e-6
                    and float(info["x_f"]) == S["focus"]["x_m"] and float(info["t_f"]) == S["focus"]["t_f_s"]
                    and [float(v) for v in info["foci"]] == S["focus"]["times_s"] and info.get("content_sha256") == dr.get("content_sha256")
                    and int(info["n_layers"]) == 3 and float(info["h0"]) == GC.H0 and abs(float(info["y1"]) - float(P["W"])) < 1e-9
                    and float(info["x1"]) >= GC.SD_SW)
    except Exception as e:
        out["table_error"] = repr(e)[:200]
    ck["table_is_plan_set"] = ok_t
    tc = GC.TABLE_CHECK
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    ck["table_G1_checked"] = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256"))
    rec = c["records"]
    smoke = c["kind"] == "smoke"
    wins = rec.get("windows") or []
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and (rec.get("r4") or {}).get("x") == list(GC.R4_X) and wins == windows_for(c["t_end_s"])
                                     and len(wins) == (1 if smoke else 3) and ((rec.get("r5") is None) == smoke) and (smoke or rec["r5"].get("every") == 3))
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in wins))
    ck["gauges"] = bool(c["gauges"]["x"][0] == 110.0 and c["gauges"]["y"] == list(GC.GAUGE_Y) and max(c["gauges"]["y"]) < GC.SD0)
    ck["checkpoints"] = bool(c["ckpt_every"] == 48 and c["ckpt_on"] == 1 and c["wall_limit_s"] == 1740)
    ck["out_root_absolute_FLIP52B"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(GC.B52B + "/"))
    ck["plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == GC.PLAN_REL and (c.get("analysis") or {}).get("plan_frozen") == GC.PLAN_REL)
    te = time_estimate(c)
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
    """dry copy of the g52b_chain.py start gate (same conditions; reads only)."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if not os.path.exists(GC.BUILD_CHECK):
        bad.append("build_check52b.json missing (py -3.10 x52b_build.py)")
    else:
        bc = json.load(open(GC.BUILD_CHECK, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check52b all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check52b")
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
    rd = os.path.join(GC.B52B, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP52B=rd.startswith(GC.B52B + "/"), hip=GC.HIP,
                hip_sha256=GC.sha256_file(GC.HIP) if os.path.exists(GC.HIP) else None)


def check_all(dry=False):
    out = dict(plan=GC.PLAN_REL, sea=GC.SET, amendment=GC.AMENDMENT_ID, plan_consistency=plan_consistency(), presets={})
    for pr in ("smoke", "main"):
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
                                                        parms_diff_vs_X2=v["precheck"].get("parms_diff_vs_X2"))
                                                for k, v in o["presets"].items()})), ensure_ascii=False))
    elif a[0] in ("cfg", "show") and len(a) >= 2:
        names = ["smoke", "main"] if a[1] == "all" else [a[1]]
        for pr in names:
            if pr not in PRESETS:
                print(__doc__); sys.exit(1)
            c = make(pr)
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
