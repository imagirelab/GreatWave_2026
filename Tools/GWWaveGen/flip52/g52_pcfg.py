# -*- coding: utf-8 -*-
"""FLIP52 plan DFG-2: run configurations (cfg.json) with their prechecks, the consistency check of every constant against the frozen plan,
and a dry copy of the g52_chain start gate (py -3.10 -B). 2026-10-17 written new (Claude). Reads only the frozen plan, the flip52 tables and
(for the comparison of the direction set) flip52/dfg52_screen.dirset. Writes only <FLIP52 root>/ready/<run_id>.json and plan/precheck_DFG.json.

Presets (plan_DFG_frozen.json; nothing here is tuned):
  smoke   S52DFG2_flat20_P28_dp1p0   dp 1.0, 0-90 s (frames 1-2161), PIPELINE CHECK ONLY (not shape-judged); records hf, r2, r3 every frame,
                                     r4 every 3rd frame in [t_fn - 6, t_fn + 4] for t_fn 44 / 72 s; no r5; max_hours 0.75
  main    DFG2_flat20_P28_dp0p5      dp 0.5, 0-105 s (frames 1-2521), the judged run; r4 and r5 every 3rd frame in the three group windows
                                     [t_fn - 6, t_fn + 4] (t_fn 44 / 72 / 100 s); max_hours 3.3 (hard cap), launches of <= 1740 s, checkpoints / 48
  B2, B1  the frozen follow-up branches at dp 0.5 (decision_after_first_0p5 step 4; written only when asked, run at most one, never by default)
Every cfg: half tank W 100 m (side band 70-100 m), flat 20 m bed (x_toe 1000 m), Lx 290 m, z -20 .. +20 m, inlet band 0-50 m (taper 12.5 m),
side band generating to x 180 m, absorbing from 210 m, exit sponge x 210-290 m (sigma 1.0, pow 2), dir_on 1 (N-layer table), ret_on 1,
ramp 14 s, dir_tf 44 s, drift stage A (volume window x 60-205 m), gravity only, solver dp / grid 2 dp / cfl 1 / maxsub 8 (plan tank.solver).
usage:
  py -3.10 -B g52_pcfg.py check [--dry]               plan consistency + precheck of smoke and main (writes plan/precheck_DFG.json;
                                                      --dry: writes nothing, the tables must exist)
  py -3.10 -B g52_pcfg.py cfg smoke|main|B2|B1|all    write <root>/ready/<run_id>.json (precheck inside; not written if it fails; 'all' = smoke, main)
  py -3.10 -B g52_pcfg.py gate <cfg.json>             the g52_chain start gate, dry (reads only) -> json
  py -3.10 -B g52_pcfg.py show smoke|main             print the cfg (not written)
Tags: [measured] [computed] [guess] [chosen].
"""
import os, sys, json, math, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                   # noqa: E402
import g52_common as GC              # noqa: E402
import g52_table as TB               # noqa: E402

PRESETS = {"smoke": ("DFG2", 1.0), "main": ("DFG2", 0.5), "B2": ("B2", 0.5), "B1": ("B1", 0.5)}
T_END = {1.0: 90.0, 0.5: 105.0}
MAX_H = {1.0: 0.75, 0.5: 3.3}
PART_LIMIT_M = 7.0
# run-time model (plan cost; [measured] rates of FLIP45 V1 and SMOKE50DA, [guess] relaunch overhead)
RATE_PRE = 0.378                     # s per Mp per frame before 25 s (V1 launch 1) [measured]
RATE_LATE = (0.62, 0.74)             # s per Mp per frame after 25 s (V1 launches 2-4 minus r5) [measured]
GROWTH = (1.05, 1.16)                # particle growth [measured scale]
R5_S = 2.4                           # s per r5 frame [measured]
RELAUNCH_S = 144.0                   # per relaunch [guess]
SMOKE_RATE = 0.567                   # s per Mp per frame (SMOKE50DA) [measured]
SMOKE_GROWTH = (1.1, 1.3)
SMOKE_SUB = 1.6
SEED_DENSITY_X2 = 7.929              # particles per m^3 measured in the X2 0.5 m run (plan cost) [measured]
DIR_CHECK = dict(x=[10.0, 30.0, 45.0, 100.0, 150.0, 195.0, 230.0], y=[-15.0, -8.0, -2.0])


# ====================================================================== the cfg
def parms_DFG(dp, set_name="DFG2"):
    smoke = float(dp) == 1.0
    GC.check_dp(dp, smoke=smoke)
    b = GC.box52(dp)
    p = dict(dp=b["dp"], gridscale=2.0, x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], h0=GC.H0,
             ox=b["ox"], oy=b["oy"], oz=b["oz"], maxsub=8.0, minsub=1.0, cfl=1.0, pcfl=0.75, t_off=0.0,
             bed_gap=0.5, floor_pad=2.0, side_pad=0.0, wave_on=0.0,
             surf_layer_m=2.5, mirror_m=1.0, surf_vox_scale=1.0, crop_x0=GC.R4_X[0], crop_x1=GC.R4_X[1], crop_z1=GC.SD0,
             surf_ycut=-15.0, surf_keep_vox=1.0, surf_bed_vox=0.5,
             relax_on=1.0, abs_on=1.0, sf_on=0.0, dir_on=1.0, dir_tf=GC.T_F, ret_on=1.0, sd_on=1.0, sd0=GC.SD0, sd_gen=GC.SD_GEN, sd_sw=GC.SD_SW,
             sd_sigma=GC.SD_SIGMA, sd_pow=GC.SD_POW, sd_taper_m=GC.SD_TAPER, sd_gain=1.0, relax_g=1.0, dt0=1.0 / 24.0, ramp_s=GC.RAMP_S,
             wall_taper_m=GC.WALL_TAPER, in_gain=1.0, x_p=80.0, xg_end=GC.IN_X1, xa0=GC.XA0, abs_sigma=GC.ABS_SIGMA, abs_pow=GC.ABS_POW,
             set_P=0.0, set_up=0.0, set_flat=0.0, set_down=0.0, set_cg=0.0, duabs_on=0.0,
             volcorr_on=1.0, vol_x0=GC.VOL_X[0], vol_x1=GC.VOL_X[1], hold_on=0.0, hold_x0=GC.HOLD_X[0], hold_x1=GC.HOLD_X[1])
    p.update(GC.bed_parms(GC.SPEC_FLAT20))
    return p, b


def drift_stage_A():
    return dict(stage="A", tau_s=GC.VOL_TAU, dmax=GC.VOL_DMAX, tcap_s=GC.VOL_TCAP, V_measure=GC.VOL_MEASURE, window_m=list(GC.VOL_X),
                amendment="plan tank.bands.volume stage A (AM-D18 rule of FLIP50)",
                rule="FLIP49 stage A: whole-tank column volume held by a target divergence in x %g-%g m (tau %g s, cap %g /s)"
                     % (GC.VOL_X[0], GC.VOL_X[1], GC.VOL_TAU, GC.VOL_DMAX))


def windows_for(t_end):
    return [[t - 6.0, t + 4.0] for t in GC.FOCI if t + 4.0 <= t_end + 1e-9]


def records(dp, t_end):
    smoke = float(dp) == 1.0
    return dict(r2=True, r3_z=GC.R3_Y, block=120, r4_block=24, preg_every=24,
                r4=dict(x=list(GC.R4_X), z1=GC.R4_Y1, y0=GC.R4_Z[0], y1=GC.R4_Z[1], clip_vox=6.0, t0=0.0, every=3),
                r5=(None if smoke else dict(t0=0.0, every=3)), windows=windows_for(t_end))


def make(preset, dry=False):
    """the cfg of a preset (dry: the table must already exist; nothing is written)."""
    set_name, dp = PRESETS[preset]
    smoke = dp == 1.0
    p, b = parms_DFG(dp, set_name)
    vox = b["vox"]
    t_end = T_END[dp]
    f_end = GC.frames_for(0.0, t_end)
    tb = TB.table_record(set_name, dry=dry)
    S = GC.SETS[set_name]
    rid = GC.run_id(set_name, dp)
    root = GC.SMOKE_ROOT if smoke else GC.RUNS_ROOT
    th = np.asarray(tb["theta_deg"]); wd = np.asarray(tb["dir_weights"])
    c = dict(
        run_id=rid, out_root=root, stage="FLIP52", kind=("smoke" if smoke else "3d"),
        case=dict(name="FLIP52_%s_%s_flat20_dp%s" % (preset, set_name, GC.tag(dp)), plan_frozen=GC.PLAN_REL, plan="Unity/Build/FLIP52/plan/plan_DFG_frozen.json "
                  "(sea, tank, records, gates A/B, decision, honesty)", campaign="FLIP52-DFG2", preset=preset, set=set_name, role=S["role"],
                  label=S["label"], judged=(not smoke), pipeline_check_only=bool(smoke), a_sum_tag=S["tag"]),
        f_start=1, f_first=1, f_end=int(f_end), t_end_s=float(t_end), parms=p, box=b, bed=GC.bed_record(GC.SPEC_FLAT20, b),
        sf=GC.sf_descriptor(note="FLIP52: the inflow is the N-layer table cfg dir (P 28 s, n 3/4/5); this descriptor (T 7 s) is for T, L, c, k only"),
        dir=dict(tb, ret_on=1.0),
        wave=dict(kind="linear periodic multi-frequency directional sea on a flat 20 m bed: %d components (3 harmonics of P = 28 s x %d directions), "
                       "phases 0 at (x_f, 0) at t = t_f + m P" % (tb["n_components"], len(th)),
                  P_s=GC.P_S, harmonics=list(GC.HARMONICS), T_s=tb["T"], freq_weights=tb["freq_weights"], theta_deg=tb["theta_deg"],
                  dir_weights=tb["dir_weights"], dspec=list(S["dspec"]), a_sum_m=tb["a_sum"], a_component_max_m=tb["a_max_component"],
                  amp_per_freq_m=tb["amp_per_freq"], x_f_m=GC.X_F, t_f_s=GC.T_F, foci_s=list(GC.FOCI), in_gain=1.0, sd_gain=1.0, ramp_s=GC.RAMP_S,
                  focal_crest_linear_m=tb["linear_refs"]["design_crest_m"],
                  chosen_at_inlet="P 28 s, harmonics 3/4/5, equal frequency weights, the %d directions and weights (%s), a_sum %.6f m (%s), focus (150, 0) "
                                  "at t = 44 + 28 m s, the flat 20 m bed and the band / sponge layout [chosen]; computed by FLIP: propagation, dispersion, "
                                  "focusing, the crest's growth, breaking, any jet / plume" % (len(th), S["dspec"], tb["a_sum"], S["tag"]),
                  tags=dict(P="chosen", harmonics="chosen", weights="chosen", directions="chosen", a_sum=S["tag"], x_f="chosen", t_f="chosen",
                            table="computed (g52_table, exact flat-bed sums)")),
        drift=drift_stage_A(), solver=dict(veltransfer="flip", donarrowband=0), records=records(dp, t_end),
        gauges=dict(x=list(GC.GAUGE_X), y=list(GC.GAUGE_Y)), level_regions=[list(r) for r in GC.LEVEL_REGIONS_52],
        dir_check=dict(every=(48 if smoke else 120), x=list(DIR_CHECK["x"]), y=list(DIR_CHECK["y"]), zl=[0.5 * vox, 40.0, 75.0, 90.0]),
        ckpt_on=1, ckpt_every=48, ckpt_list=[96, 72, 48, 24, 12], wall_limit_s=1740, level_guard_m=GC.LEVEL_GUARD_M, disk_stop_free_gb=25.0,
        max_hours=MAX_H[dp], level_box=[0.0, b["Lx"], 0.0, b["W"]], n1_x=list(GC.N1_STILL_X), n1_window=[0.5, 1.5], shore_x=GC.X_SHORE,
        fieldbox_frames=[2], pstats_frames=[1, 2, int(f_end)],
        note=("FLIP52 DFG-2 %s (%s): 3D dp %g, half tank W 100 m (side band 70-100 m), flat 20 m bed, Lx 290 m with an exit sponge 210-290 m, "
              "periodic three-harmonic directional sea P 28 s, %s, a_sum %.6f m (%s), focus (150, 0) at t = 44 / 72 / 100 s, ramp 14 s, stage A, "
              "0-%g s. %s" % (preset, set_name, dp, S["label"], tb["a_sum"], S["tag"], t_end,
                              "PIPELINE CHECK ONLY (not shape-judged); records hf/r2/r3 every frame, r4 every 3rd frame in the group windows, no r5" if smoke else
                              "Records hf/r2/r3 every frame, r4 and r5 every 3rd frame in the three group windows")),
        layout="DFG", analysis=dict(plan_frozen=GC.PLAN_REL, interior_x=list(GC.INTERIOR_X), interior_y=GC.INTERIOR_Y, focal_x=list(GC.FOCAL_X),
                                    focal_y=GC.FOCAL_Y, foci_s=list(GC.FOCI), P_s=GC.P_S, tool="Tools/GWWaveGen/flip52/g52_ana.py"))
    c["precheck"] = precheck(c)
    return c


# ====================================================================== checks
def expected_set(set_name):
    """the direction / frequency set and a_sum each preset must carry, read from the FROZEN plan (not from g52_common)."""
    pl = GC.plan()
    sea = pl["sea"]
    out = dict(th=[float(v) for v in sea["directions_deg"]], wd=[float(v) for v in sea["dir_weights"]], wf=[float(v) for v in sea["freq_weights"]],
               P=float(sea["P_s"]), harmonics=[int(v) for v in sea["harmonics_n"]], a_sum=float(sea["a_sum_m"]), x_f=float(sea["focus"]["x_m"]),
               t_f=float(sea["focus"]["t_f_s"]), foci=[float(v) for v in sea["focus"]["times_s"]], ramp=float(sea["ramp_s"]))
    if set_name == "B2":
        out["a_sum"] = float(pl["decision_after_first_0p5"]["branch_screens"]["B2"]["a_sum_m"])
    if set_name == "B1":                                   # 'lobes 65 deg / sigma 25' (one change): the hyb rule with centre 65, sigma 25
        th, wd = GC.dirset(("hyb", 65.0, 25.0, 85.0, 17))
        out["th"] = [round(float(v), 6) for v in th]; out["wd"] = [round(float(v), 6) for v in wd]
        out["B1_rule_in_plan"] = bool("65 deg / sigma 25" in " ".join(pl["decision_after_first_0p5"]["steps"]))
    return out


def plan_consistency():
    """every constant of g52_common against the frozen plan (equal, or within the stated tolerance)."""
    pl = GC.plan()
    T = pl["tank"]; B = T["bands"]; S = pl["sea"]; R = pl["records"]
    ck = {}
    ck["plan_sha256"] = GC.plan_sha_ok()
    ck["tank"] = bool(T["h0_m"] == GC.H0 and T["Lx_m"] == GC.LX and T["W_m"] == GC.W_MAIN and T["z_bed_m"] == GC.ZB and T["z_top_m"] == GC.Z_TOP
                      and T["solver"]["gridscale"] == 2.0 and T["solver"]["cfl"] == 1.0 and T["solver"]["maxsub"] == 8 and T["solver"]["pcfl"] == 0.75)
    ck["inlet"] = bool(B["inlet"]["x_m"] == [0.0, GC.IN_X1] and B["inlet"]["xg_end"] == GC.IN_X1 and B["inlet"]["wall_taper_m"] == GC.WALL_TAPER
                       and B["inlet"]["in_gain"] == 1.0 and B["inlet"]["relax_g"] == 1.0)
    sd = B["side"]
    ck["side"] = bool(sd["sd0"] == GC.SD0 and sd["sd_gen"] == GC.SD_GEN and sd["sd_sw"] == GC.SD_SW and sd["sd_sigma"] == GC.SD_SIGMA
                      and sd["sd_pow"] == GC.SD_POW and sd["sd_taper_m"] == GC.SD_TAPER and sd["sd_gain"] == 1.0 and sd["y_m"] == [GC.SD0, GC.W_MAIN])
    ex = B["exit_sponge"]
    ck["exit_sponge"] = bool(ex["abs_on"] == 1 and ex["xa0"] == GC.XA0 and ex["abs_sigma"] == GC.ABS_SIGMA and ex["abs_pow"] == GC.ABS_POW
                             and ex["length_m"] == GC.LX - GC.XA0)
    ck["ret_dir_volume"] = bool(B["ret_on"] == 1 and B["dir_on"] == 1 and B["volume"]["vol_x_m"] == list(GC.VOL_X) and B["volume"]["stage"].startswith("A"))
    ck["interior"] = bool(T["interior"]["x_m"] == list(GC.INTERIOR_X) and T["interior"]["y_abs_max_m"] == GC.INTERIOR_Y
                          and T["interior"]["focal_window_x_m"] == list(GC.FOCAL_X) and T["interior"]["focal_window_y_abs_m"] == GC.FOCAL_Y)
    C = GC.components("DFG2")
    ck["sea_P_harmonics"] = bool(S["P_s"] == GC.P_S and S["harmonics_n"] == list(GC.HARMONICS) and S["ramp_s"] == GC.RAMP_S)
    ck["sea_focus"] = bool(S["focus"]["x_m"] == GC.X_F and S["focus"]["y_m"] == 0.0 and S["focus"]["t_f_s"] == GC.T_F
                           and S["focus"]["times_s"] == list(GC.FOCI))
    ck["sea_set_bit_for_bit"] = bool([round(float(v), 6) for v in C["th"]] == S["directions_deg"] and [round(float(v), 6) for v in C["wd"]] == S["dir_weights"]
                                     and [round(float(v), 6) for v in C["wf"]] == S["freq_weights"] and len(C["th"]) * len(C["wf"]) == S["n_components"])
    ck["sea_a_sum"] = bool(round(C["a_sum"], 9) == S["a_sum_m"] and round(float(C["a"].max()), 6) == S["a_max_component_m"]
                           and round(float(np.sum(C["a"] ** 2)), 6) == S["sum_a2_m2"]
                           and [round(float(C["a_sum"] * v), 6) for v in C["wf"]] == S["amp_per_freq_m"])
    ck["sea_omega"] = bool([round(float(v), 6) for v in C["om"]] == S["omega_rad_s"])
    kd = [abs(float(a) / float(b) - 1.0) for a, b in zip(C["k"], S["k_n"])]
    ck["sea_k_within_1e-3"] = bool(max(kd) < 1e-3)
    try:
        sys.path.insert(0, HERE)
        import dfg52_screen as D52                      # the screen that chose the set (py -3.10 only: scipy)
        th2, wd2 = D52.dirset(("hyb", 60.0, 28.0, 85.0, 17))
        ck["dirset_equals_screen_bitwise"] = bool(np.array_equal(th2, C["th"]) and np.array_equal(wd2, C["wd"]))
        th3, wd3 = D52.dirset(("hyb", 65.0, 25.0, 85.0, 17)); t4, w4 = GC.dirset(("hyb", 65.0, 25.0, 85.0, 17))
        ck["B1_dirset_equals_screen_bitwise"] = bool(np.array_equal(th3, t4) and np.array_equal(wd3, w4))
    except Exception as e:
        ck["dirset_equals_screen_bitwise"] = False
        ck["dirset_error"] = repr(e)[:200]
    ck["records"] = bool(R["t_end_s"] == {"dp0p5": T_END[0.5], "dp1p0": T_END[1.0]} and "every 48 frames" in R["checkpoints"])
    ck["G2f_gauges"] = bool("x 60 m, y 0.5 / 15 / 30 / 45 / 60 m" in R["gauges"] and list(GC.GAUGE_Y) == [0.5, 15.0, 30.0, 45.0, 60.0])
    notes = dict(k_n_rel_diff_vs_plan=kd, k_n_note="the screen used g = 9.81 m/s^2 (flip51/dfg51_screen.G); the table uses g = 9.80665 m/s^2 "
                                                   "(g50_dirfield.G, the Houdini gravity); k_n differ by <= %.1e [computed]" % max(kd))
    ok = all(v for k, v in ck.items() if isinstance(v, bool))
    return dict(ok=bool(ok), checks=ck, notes=notes)


def time_estimate(n, c):
    """plan cost rule. dp 0.5: frames before 25 s at RATE_PRE, later at RATE_LATE x growth, r5 frames x 2.4 s, relaunches x 144 s.
    dp 1.0: SMOKE50DA rate x growth 1.1-1.3 x substeps up to 1.6."""
    P = c["parms"]; dp = float(P["dp"])
    f0 = int(c.get("f_start", 1)); f1 = int(c["f_end"])
    nf = f1 - f0 + 1
    Mp = n / 1e6
    if dp == 1.0:
        lo = SMOKE_RATE * Mp * SMOKE_GROWTH[0] * nf / 3600.0
        hi = SMOKE_RATE * Mp * SMOKE_GROWTH[1] * nf * SMOKE_SUB / 3600.0
        return dict(frames=nf, est_h=[lo, hi], rule="SMOKE50DA %.3f s per Mp per frame x growth 1.1-1.3 x substeps up to 1.6 [measured rate, guessed growth]"
                    % SMOKE_RATE)
    fb = int(round(25.0 * GC.FPS)) + 1
    n_pre = max(0, min(f1, fb - 1) - f0 + 1); n_late = nf - n_pre
    heavy = heavy_frames(c)
    lo_s = RATE_PRE * Mp * n_pre + RATE_LATE[0] * Mp * GROWTH[0] * n_late + R5_S * heavy
    hi_s = RATE_PRE * Mp * GROWTH[0] * n_pre + RATE_LATE[1] * Mp * GROWTH[1] * n_late + R5_S * heavy
    nl_lo = math.ceil(lo_s / c["wall_limit_s"]); nl_hi = math.ceil(hi_s / c["wall_limit_s"])
    lo_s += (nl_lo - 1) * RELAUNCH_S; hi_s += nl_hi * RELAUNCH_S
    return dict(frames=nf, frames_pre25=n_pre, frames_late=n_late, r5_frames=heavy, est_h=[lo_s / 3600.0, hi_s / 3600.0], launches=[nl_lo, nl_hi + 1],
                rule="plan cost: %.3f s/Mp/frame before 25 s, %.2f-%.2f s/Mp/frame after (growth %.2f-%.2f), r5 %.1f s/frame, relaunch %g s "
                     "[measured rates, guessed relaunch]" % (RATE_PRE, RATE_LATE[0], RATE_LATE[1], GROWTH[0], GROWTH[1], R5_S, RELAUNCH_S))


def heavy_frames(c):
    rec = c["records"]
    if not rec.get("r5"):
        return 0
    ev = int(rec["r5"].get("every", 1))
    n = 0
    for f in range(int(c.get("f_start", 1)), int(c["f_end"]) + 1):
        t = (f - 1) / GC.FPS
        if any(a - 1e-9 <= t <= b + 1e-9 for a, b in rec["windows"]) and (f - 1) % ev == 0:
            n += 1
    return n


def precheck(c):
    P = c["parms"]; spec = GC.bed_spec(c)
    out = dict(checks={}, tags=dict(particles="computed (numpy, the scene's seeding rule)", wall="computed (plan cost rule)"))
    ck = out["checks"]
    pc = plan_consistency()
    out["plan_consistency"] = pc
    ck["plan_consistency"] = bool(pc["ok"])
    dp = float(P["dp"])
    n, V = GC.count_particles(spec, float(P["Lx"]), float(P["W"]), dp, zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))
    out.update(particles_model=int(n), water_m3=float(V), water_m3_box=float(P["Lx"]) * float(P["W"]) * GC.H0,
               particles_peak_M=[n * GROWTH[0] / 1e6, n * GROWTH[1] / 1e6], particles_from_X2_seed_density_M=GC.LX * GC.W_MAIN * GC.H0 * SEED_DENSITY_X2 / 1e6
               if dp == 0.5 else None)
    ck["particles_le_limit"] = bool(n * GROWTH[1] / 1e6 <= PART_LIMIT_M)
    ck["particles_exact_columns"] = bool(n == int(round(GC.LX / dp)) * int(round(GC.W_MAIN / dp)) * int(round(GC.H0 / dp)))
    b = c["box"]
    ck["box"] = bool(float(P["Lx"]) == GC.LX and float(P["W"]) == GC.W_MAIN and float(P["zb"]) == GC.ZB and float(P["Hz"]) == GC.Z_TOP - GC.ZB
                     and float(P["floor_pad"]) == 2.0 and float(P["h0"]) == GC.H0 and b["z_top"] == GC.Z_TOP and float(P["gridscale"]) == 2.0)
    ck["bed_flat_20"] = bool(not GC.is_new(spec) and spec.get("k_end") is None and float(spec["x_toe"]) >= 2 * GC.LX and float(spec["k"]) == 0.0
                             and float(c["bed"].get("max_depth_m", -1)) == GC.H0 and float(c["bed"].get("min_depth_m", -1)) == GC.H0)
    ck["bands"] = bool(float(P["relax_on"]) == 1.0 and float(P["sd_on"]) == 1.0 and float(P["abs_on"]) == 1.0 and float(P["dir_on"]) == 1.0
                       and float(P["ret_on"]) == 1.0 and float(P["sf_on"]) == 0.0 and float(P["xg_end"]) == GC.IN_X1 and float(P["wall_taper_m"]) == GC.WALL_TAPER
                       and float(P["sd0"]) == GC.SD0 and float(P["sd_gen"]) == GC.SD_GEN and float(P["sd_sw"]) == GC.SD_SW
                       and float(P["sd_sigma"]) == GC.SD_SIGMA and float(P["sd_pow"]) == GC.SD_POW and float(P["sd_taper_m"]) == GC.SD_TAPER
                       and float(P["xa0"]) == GC.XA0 and float(P["abs_sigma"]) == GC.ABS_SIGMA and float(P["abs_pow"]) == GC.ABS_POW
                       and float(P["in_gain"]) == 1.0 and float(P["sd_gain"]) == 1.0 and float(P["relax_g"]) == 1.0
                       and float(P["ramp_s"]) == GC.RAMP_S and float(P["dir_tf"]) == GC.T_F and float(P["set_P"]) == 0.0)
    D = c["drift"]
    ck["drift_stage_A"] = bool(D["stage"] == "A" and float(P["volcorr_on"]) == 1.0 and float(P["duabs_on"]) == 0.0 and float(P["hold_on"]) == 0.0
                               and float(P["vol_x0"]) == GC.VOL_X[0] and float(P["vol_x1"]) == GC.VOL_X[1] and float(P["vol_x0"]) >= float(P["xg_end"])
                               and float(P["vol_x1"]) <= float(P["xa0"]) and D.get("V_measure") == GC.VOL_MEASURE)
    ck["solver"] = bool(float(P["cfl"]) == 1.0 and float(P["maxsub"]) == 8.0 and float(P["minsub"]) == 1.0 and float(P["pcfl"]) == 0.75
                        and c["solver"].get("veltransfer") == "flip")
    # the table: file, sha, content = the G1-checked table, info = the set the plan froze (bit for bit after rounding to the plan's 6 digits)
    dr = c.get("dir") or {}
    set_name = (c.get("case") or {}).get("set")
    ok_file = bool(os.path.exists(dr.get("npz") or "") and GC.sha256_file(dr["npz"]) == dr.get("npz_sha256"))
    ck["table_file_sha"] = ok_file
    ex = expected_set(set_name)
    ok_t = False; why_t = None
    try:
        info = json.loads(str(np.load(dr["npz"], allow_pickle=False)["info"]))
        ok_t = bool(info.get("set") == set_name and float(info["P"]) == ex["P"] and info["harmonics"] == ex["harmonics"]
                    and [round(float(v), 6) for v in info["theta_deg"]] == ex["th"] and [round(float(v), 6) for v in info["dir_weights"]] == ex["wd"]
                    and [round(float(v), 6) for v in info["freq_weights"]] == ex["wf"] and abs(float(info["a_sum"]) - ex["a_sum"]) < 1e-8
                    and float(info["x_f"]) == ex["x_f"] and float(info["t_f"]) == ex["t_f"] and [float(v) for v in info["foci"]] == ex["foci"]
                    and info.get("content_sha256") == dr.get("content_sha256") and int(info["n_layers"]) == len(ex["harmonics"])
                    and float(P["ramp_s"]) == ex["ramp"] and float(P["dir_tf"]) == ex["t_f"] and float(info["h"]) == GC.H0
                    and abs(float(info["y1"]) - float(P["W"])) < 1e-9 and float(info["x1"]) >= GC.SD_SW)
        if set_name == "B1":
            ok_t = ok_t and bool(ex.get("B1_rule_in_plan"))
    except Exception as e:
        why_t = repr(e)[:200]
    ck["table_is_plan_set_bit_for_bit"] = ok_t
    if why_t:
        out["table_error"] = why_t
    tc = GC.PLAN_DIR + "/table_check_%s.json" % set_name
    tcj = GC.jload(tc) if os.path.exists(tc) else {}
    ck["table_G1_checked"] = bool(tcj.get("all_ok") and tcj.get("content_sha256") == dr.get("content_sha256"))
    ck["sf_descriptor"] = bool((c.get("sf") or {}).get("descriptor") is True and float(c["sf"]["T"]) == GC.T_WAVE and float(c["sf"]["h"]) == GC.H0)
    # records
    rec = c["records"]
    smoke = c["kind"] == "smoke"
    wins = rec.get("windows") or []
    ck["records_as_designed"] = bool(rec.get("r2") and rec.get("r3_z") == GC.R3_Y and (rec.get("r4") or {}).get("every") == 3
                                     and (rec.get("r4") or {}).get("x") == list(GC.R4_X) and (rec.get("r4") or {}).get("z1") == GC.R4_Y1
                                     and wins == windows_for(c["t_end_s"]) and len(wins) == (2 if smoke else 3)
                                     and ((rec.get("r5") is None) == smoke) and (smoke or (rec["r5"].get("every") == 3)))
    ck["windows_inside_run"] = bool(all(0.0 <= a < b <= c["t_end_s"] + 1e-9 for a, b in wins))
    ck["t_end_frames"] = bool(c["t_end_s"] == T_END[dp] and int(c["f_end"]) == GC.frames_for(0.0, T_END[dp]))
    ck["gauges"] = bool(c["gauges"]["x"][0] == 60.0 and c["gauges"]["y"] == list(GC.GAUGE_Y) and max(c["gauges"]["y"]) < GC.SD0)
    regs = c.get("level_regions") or []
    ck["level_regions"] = bool(all(0.0 <= r[1] < r[2] <= float(P["Lx"]) for r in regs) and all(nm in [r[0] for r in regs] for nm in ("band_core", "probe_c", "window")))
    ck["checkpoints"] = bool(c["ckpt_every"] == 48 and c["ckpt_on"] == 1 and c["wall_limit_s"] == 1740)
    ck["out_root_absolute_FLIP52"] = bool(os.path.isabs(c["out_root"]) and c["out_root"].replace("\\", "/").startswith(GC.B52 + "/")
                                          and os.path.join(GC.B52, c["out_root"]).replace("\\", "/") == c["out_root"].replace("\\", "/"))
    ck["plan_named"] = bool((c.get("case") or {}).get("plan_frozen") == GC.PLAN_REL and (c.get("analysis") or {}).get("plan_frozen") == GC.PLAN_REL)
    te = time_estimate(n, c)
    out["time"] = te
    ck["time_within_max_hours"] = bool(te["est_h"][1] <= float(c["max_hours"]))
    ck["max_hours_is_plan_cap"] = bool(float(c["max_hours"]) == MAX_H[dp])
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
    """dry copy of the g52_chain.py start gate (same conditions; reads only) plus the plan / table-check items."""
    cfg = json.load(open(cfgp, encoding="utf8"))
    bad = []
    pc = cfg.get("precheck")
    if not isinstance(pc, dict) or pc.get("ok") is not True:
        bad.append("precheck not ok: %s" % (pc or {}).get("reason"))
    if not os.path.exists(GC.BUILD_CHECK):
        bad.append("build_check52.json missing (py -3.10 x52_build.py)")
    else:
        bc = json.load(open(GC.BUILD_CHECK, encoding="utf8"))
        if not bc.get("all_ok"):
            bad.append("build_check52 all_ok false")
        if not os.path.exists(GC.HIP):
            bad.append("hip missing")
        elif bc.get("hip_sha256") != GC.sha256_file(GC.HIP):
            bad.append("hip sha differs from build_check52")
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
    rd = os.path.join(GC.B52, cfg.get("out_root", "runs"), cfg["run_id"]).replace("\\", "/")
    return dict(gate_ok=not bad, reasons=bad, run_dir=rd, run_dir_in_FLIP52=rd.startswith(GC.B52 + "/"), hip=GC.HIP,
                hip_sha256=GC.sha256_file(GC.HIP) if os.path.exists(GC.HIP) else None)


def check_all(dry=False):
    out = dict(plan=GC.PLAN_REL, plan_consistency=plan_consistency(), presets={})
    for pr in ("smoke", "main"):
        c = make(pr, dry=dry)
        out["presets"][pr] = dict(run_id=c["run_id"], precheck=c["precheck"], cfg_sha16=GC.sha16_json(c))
    out["ok"] = bool(out["plan_consistency"]["ok"] and all(v["precheck"]["ok"] for v in out["presets"].values()))
    if not dry:
        GC.jdump(out, GC.PLAN_DIR + "/precheck_DFG.json")
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
        print(json.dumps(GC.clean(dict(ok=o["ok"], plan_consistency=o["plan_consistency"]["ok"],
                                       presets={k: dict(run_id=v["run_id"], ok=v["precheck"]["ok"], reason=v["precheck"]["reason"],
                                                        particles=v["precheck"]["particles_model"], time=v["precheck"]["time"]["est_h"])
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
