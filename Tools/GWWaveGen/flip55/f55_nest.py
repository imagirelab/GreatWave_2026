# -*- coding: utf-8 -*-
"""FLIP55 option C2: the one-way dp 0.25 m NEST of group 1 inside DFG-2B-V (export / run / gates / analyse / amend / selftest), plus the
hython side of its launches (modes 'hyrun' / 'hyckpt'). 2026-10-19 written new (Claude); one of the two nest tools registered BY NAME in
f55_common.NEST_TOOLS (the other one is x55_nest_build.py: the nest scene Houdini/FLIP55/f55_nest.hiplc and its build check). Nothing here
edits a frozen file: g52b3_run.py (the runner), g52b3_chain.py (the chain), g49_restart.py (seed / compare), g52b3_ana.py / g52_ana.py
(judge pieces), pv53.py, f55_hollow.py and f55_common / f55_pcfg are used UNCHANGED (sha checked where the plan froze them).

The design (frozen in plan_F55_frozen.json, option C2; the cfgs come from f55_pcfg.make('C2' | 'C2ID'); nothing tuned here):
  parent   DFG-2B-V rerun from its OWN checkpoint v.1056 (t 43.958 s) to frame 1657 = run F55P_DFGBV_c1056_export in Unity/Build/FLIP55/runs:
           the cfg is DFG-2B-V's launched cfg (its run folder's cfg.json) with ONLY the restart keys changed (run_id, out_root, f_start,
           f_first, f_end, still_offset_m; case labels, restart, f55, note), seeded by g49_restart.seed (v.1056, volcorr ref.json, vd_01056,
           vd_01057, state rows f <= 1056; its dirs() replaced in memory so the new folder is under FLIP55), run by g52b3_chain.py with exactly
           three counted text replacements made in memory (the launched script = this file in mode 'hyrun', the Houdini temp folder = FLIP55's)
           and, inside hython, the FROZEN g52b3_run.py executed unchanged by runpy (sha checked) with ONE read-only hook: hou.setFrame is
           wrapped so that, BEFORE the runner moves to frame f + 1, the fields the runner itself already cooked at frame f
           (/obj/G52_READ/surface_field, /obj/G52_READ/vel_field) are copied to an npz. The hook sets no parm, creates no node, cooks
           nothing new (it reads cached SOP geometry of the current frame) and calls the original hou.setFrame with the same argument in the
           same order, so the DOP simulation sees exactly the calls of a normal launch. PROOF by measurement: g49_restart.compare against the
           judged run on every frame 1057-1657 (hf, r2, r3 all keys, r4 and surf bytes on the common frames, volcorr rows) must be
           bit-identical in a COMPLETE overlap (strict rule of flip52b3h/h52b3_long.py), otherwise the export is refused (ok false).
           Frame 1056 (the nest's initial state) is read by a SEPARATE hython process ('hyckpt') that loads the DFG-2B-V scene with its
           explicit cache pointed at a copy of v.1056.sim and reads the same two fields at frame 1056 (no frame of the rerun is touched).
  export   per frame (1056-1657) one npz x_<f>.npz in <export run>/export: the parent's surface SDF (float32) and vel.x / vel.y / vel.z (float16)
           on the parent's own grid (1 m cells, centres at k + 0.5 m; the vel components on their own face grids, cropped by index, never
           resampled) in box xb = x 178-199 m, y 0-140 m (all y) and box yb = y 41-62 m, x 180-356 m, full height (= the frozen cfg text
           nest.parent.export); frame 1056 also carries box nb = the whole nest box x 178-358, y 0-62 m (the reseeding needs the parent's
           surface and velocity everywhere); ~2-3 MB / frame compressed [computed]. Alignment check: the top surface recomputed from the exported SDF with
           the runner's R1 rule equals the judged run's hf record of the same frame within 1e-3 m on every exported column (and differs from
           the neighbour frames).
  nest     scene Houdini/FLIP55/f55_nest.hiplc (x55_nest_build.py): DFG-2B-V's scene graph (same node names, VEX head, solver, records path) on
           the box x 180-356, y 0-60, z -19..17 m; y = 0 symmetry plane kept (closed free-slip face, surface mirror as the parent); the DOP
           network starts at frame 1 like the parent's ($SF = $F: checkpoint names are global frames, as the frozen chain's resume needs)
           and the FLIP / static objects are created at frame sim_f0 = 1056 (global frames, not solved on creation) from the reseeded
           particles, so frames 1-1055 hold no object; frames 1057-1657 run by the FROZEN g52b3_run.py (g52b3_common.HIP replaced in memory
           by the nest scene; the chain's build check / scene sha by the nest's), so every record (hf, r2, r4, r5, volcorr state, r6) has
           DFG-2B-V's format.
  bands    x 180-195 (inlet-band rule of DFG-2B-V's VEX bands50 over the band from x 195; FIX F2: the nest's copy nest_bands with the
           weight per frame w = chi, linear, band_lin 1) and y 45-60 (side-band rule, generating
           over the whole nest x): grid velocity relaxed per substep toward the parent's velocity (horizontal components, as the parent's
           inlet band) with NO wall taper (parms.wall_taper_m 15 -> 0, a registered override: the frozen 15 m taper made the x band a sponge
           toward u = 0, review 2026-10-19 B1), and the SURFACE relaxed by particles once per frame (delete band particles that are not the
           parent's water; seed parent-water lattice points where the nest holds fewer than half the full-water particle count within
           1.5 dp; each with the band weight over one frame as the probability). The parent's water is tgt_water: below its PARTICLE level
           (its SDF zero sits s_off = 0.0759846568107605 m [measured, its still offset] above the level its particles fill, review B3) or,
           within bed_trust_m 1 m of the bed, below its top surface - s_off (its SDF reads air in some near-bed cells, review M4). The
           parent's water volume in the nest box varies from -0.69 % to +2.51 % over frames 1057-1657 [measured, hf column rule], so a
           mass-closed nest could not pass GN3 (+-2 %) and its 15 m band would sag by up to ~2.4 m [computed].
           Target = the parent's fields linear in time between frames fa = ceil(ff) - 1 and fb = ceil(ff) (ff = the DOP substep frame),
           trilinear in space (volumesample on the parent's grid; one ghost cell on every side, mirrored at y = 0, so no sample reaches the
           volume border, review B2), assembled by the Python SOP OUT_TARGET from the two npz files.
  init     C2ID (FIX F7, 2026-10-19): the PARENT'S OWN particles at t 43.958 s inside the box (p_01056.npz, step 'pinit': a separate hython
           'hypart' loads DFG-2B-V's scene with its explicit cache on the checkpoint copy, exactly as hyckpt, and saves P / v of the water
           object; validated against the hyckpt particle count, the parent's SDF and grid velocity). C2 (dp 0.25, no parent particles at that
           spacing): lattice x0 + (i + 1/2) dp, (j + 1/2) dp, zb + (k + 1/2) dp (the scene's seeding rule), kept where the lattice point is
           the parent's water BY THE MARGIN init_lvl_m (tgt_water) and above bed + 0.5 dp, jitter 0.2 dp, velocity = the parent's grid
           velocity; init_lvl_m = the level step (the rise of the nest's level after creation) of a 48-frame still-water calibration
           (step 'calib C2', CALIB_RULE_TEXT; 'run C2' runs it first when it is missing or stale); the band water rule (band_kill /
           band_seed) is shifted by the same init_lvl_m (physics review 2026-10-19 B1), so C2 is the calibrated still state translated by
           the step; C2's own reading offset (calib analysis.offset_at_creation_m) is reported, not subtracted (physics review M5).
  fix      2026-10-19 after the first C2ID failed GN1-GN3 (Hc -18 %, GN2 0.64 m, GN3 2.7 % [measured]): F1 the band surface wrangles bind
           Input 1 = self (their reads saw nothing: band_cand 0 in every smoke frame [measured]) + counters; F2 the nest-only linear band
           weight (band_lin 1); F7 above. Gates GN1-GN3 unchanged. AM-F55-NEST is re-registered (amend --write) only after the new build
           check + smoke pass.
  end      the closed face x 356 m stays closed (frozen 'outflow: none'). The parent's swash passes it (wet to x 386.5 m, <= 402 m3 = 0.46 %
           beyond it [measured]), so an OPTIONAL end band (end_on, default 0) is built and probed but OFF; the export always carries box eb
           (x 339-358 m) so switching it on (its own amendment) needs no new parent rerun.
  volume   no own controller: the parent's stage-A target divergence d(f) (vd_<f>.txt of the judged run, copied to <export>/vd) is applied in
           the nest window x 195-356 m (vol_x0 / vol_x1 of the frozen cfg), all y, all depth (rep_on; vc_divergence's window rule).
  gates    GN1 / GN2 / GN3 of the plan on C2ID (the 0.5 m identity nest), computed here with the rules written in GN_RULES (registered by
           AM-F55-NEST before any nest run); the reading itself is f55_hollow.py verdict C2 vs C2ID (unchanged).
The cfg keys a LAUNCH adds to the frozen design cfg (f55_pcfg.make; its sha16 is checked against the plan) are exactly DERIVED_KEYS
(parms of the nest scene, dir = DFG-2B-V's table block so the frozen runner's table check passes (dir_on 0: never read), still_offset_m
= the parent's) plus ONE overridden design value, OVERRIDE_PARMS parms.wall_taper_m 15 -> 0 (review 2026-10-19 B1, registered with its
reason); everything else is the design cfg canonically equal. AM-F55-NEST registers this rule and the tool sha256 before any nest run.

usage (py -3.10 -B; every step prints ONE final json line with "ok", as auto_F55.py's C2 path expects):
  f55_nest.py export   [--simulate]          parent rerun + export (seed, hyckpt f1056, chain, strict compare, validation) -> export.json
  f55_nest.py pinit    [--simulate]          F7: the parent's frame-1056 particles in the C2ID box (hython hypart) -> export/p_01056.npz +
                                             pinit_01056.json (skipped when ok and unchanged)
  f55_nest.py calib    C2 [--simulate]        C2's still-water calibration of the level step (hython x55_nest_build.py --hython-calib) ->
                                             _logs/calib55_C2.json ('run C2' runs it first when missing / stale)
  f55_nest.py run      C2ID|C2 [--simulate]   launch cfg (design cfg + DERIVED_KEYS) -> chain (resumes from checkpoints, <= 2 extra chains)
  f55_nest.py gates    C2ID [--simulate]      judge-like group 1, pv53 (--no-unity), f55_hollow measure, GN1-GN3 -> <C2ID>/f55/gates_GN.json
  f55_nest.py analyse  C2 [--simulate]        judge-like group 1, pv53 (Unity, retry --no-unity), f55_hollow measure of C2 (+ GN2/GN3 report)
  f55_nest.py amend    [--write]             AM-F55-NEST: always writes plan/AM-F55-NEST.draft.json; --write appends to plan/amendments.jsonl
                                             ONLY if _logs/build_check55_nest.json is all_ok (smoke included) for this hip and these tools
  f55_nest.py status                         what exists (export, build check, amendment, runs) -> json
  f55_nest.py selftest                       numpy / static checks (no Houdini): shas, chain patch, cfgs, hook order, target assembly, bands,
                                             GN rules on synthetic data
  f55_nest.py standin  [--hollow]            the parent's own records cropped to the nest box (Unity/Build/FLIP55/_scratch/nest_standin):
                                             GN1-GN3 parent vs stand-in must be an exact identity; judge-like group vs the parent's judge;
                                             --hollow: pv53 scan + the frozen R0 ruler on the stand-in vs the frozen baseline
  f55_nest.py archive  C2ID|C2 [--simulate]  move a finished / failed nest run folder and its launch cfg to runs/_archived/<rid>__<time> (needed
                                             before a rerun after an amendment; refused while its chain runs)
Every real step (export, run, x55_nest_build.py) first passes entry_guard: no other pipeline process / hython / Unity batch / foreign
auto_F55 lock, free commit >= the plan's need (export: C2's 11.46 GB as auto_F55; C2ID 8.18 GB; C2 11.46 GB) and G: >= its disk need on 2
polls (waits up to --wait-min, default 20 min). Each chain runs under a watchdog (free commit < 3 GB on 2 polls or the brake file
Unity/Build/FLIP55/_logs/auto_F55_STOP -> <run>/STOP; the chain stops before its next launch, nothing is killed).
internal: f55_nest.py chain export|nest <cfg>   (py -3.10; the patched chain)   hython f55_nest.py hyrun <launch cfg> | hyckpt <cfg> |
          hypart <export cfg>
Tags: [measured] records, [computed] derived, [chosen] design choices, [guess] judgement.
"""
import os, sys, json, time, glob, math, hashlib, shutil, subprocess, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
T52B3 = TOOLS + "/flip52b3"
T52 = TOOLS + "/flip52"
T49 = TOOLS + "/flip49"
T51 = TOOLS + "/flip51"
T53 = TOOLS + "/flip53"
SELF = HERE + "/f55_nest.py"
TOOL_REL = "Tools/GWWaveGen/flip55/f55_nest.py"
BUILD_TOOL = HERE + "/x55_nest_build.py"
B55 = REPO + "/Unity/Build/FLIP55"
B52B3 = REPO + "/Unity/Build/FLIP52B3"
RUNS_ROOT = B55 + "/runs"
READY = RUNS_ROOT + "/ready"
LOG_DIR = B55 + "/_logs"
PLAN_DIR = B55 + "/plan"
TMP_HOUDINI = B55 + "/tmp_houdini"
SIM_DIR = B55 + "/_scratch/sim_nest"
STANDIN_ROOT = B55 + "/_scratch/nest_standin"

# ------------------------------------------------------------------ frozen tools used unchanged (sha = plan_F55_frozen.json code_sha256_frozen_used)
RUNNER = T52B3 + "/g52b3_run.py"
RUNNER_SHA = "b7bafce1bf090467cb8b5560577c58e8a82b36c87a67808ca1993096850682e7"
CHAIN = T52B3 + "/g52b3_chain.py"
CHAIN_SHA = "2ccf005200a28f024a74ec14750e8c4dc171d491a732fc97eb0bb7195daed444"
G49R = T49 + "/g49_restart.py"
G49R_SHA = "ddd15f5565916e16a58191a7ded44d20cea34826ff7286d2504cf2d1e5728755"     # the seed / compare of the bit-identical hero re-record [measured]
PV53 = T53 + "/pv53.py"
HOLLOW = HERE + "/f55_hollow.py"

# ------------------------------------------------------------------ the parent and the nest
DFGBV_RID = "DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"
DFGBV_RUN = B52B3 + "/runs/" + DFGBV_RID
DFGBV_HIP = REPO + "/Houdini/FLIP52B3/g52b3_tank.hiplc"
DFGBV_HIP_SHA = "9fa07e66f930e92316278e29ed0b3ea3269c5fee044ca4c3a5d297ee898412c5"
STILL_OFFSET = 0.0759846568107605          # DFG-2B-V run_c*.json info.still_offset_online [measured]
NEST_HIP = REPO + "/Houdini/FLIP55/f55_nest.hiplc"
NEST_BUILD_CHECK = LOG_DIR + "/build_check55_nest.json"
CKPT = 1056                                 # = f55_common.NEST_CKPT
F0 = CKPT + 1                               # 1057 (= f55_common.NEST_F0)
F_END = 1657                                # = f55_common.F_END_G1
FPS = 24.0
EXPORT_RID = "F55P_DFGBV_c1056_export"      # = f55_common.RID['C2P']
EXPORT_RD = RUNS_ROOT + "/" + EXPORT_RID
EXPORT_DIR = EXPORT_RD + "/export"
EXPORT_JSON = EXPORT_DIR + "/export.json"
REPLAY_DIR = EXPORT_DIR + "/vd"
CKPT_LOAD_DIR = EXPORT_RD + "/ckpt_1056"
EXPORT_CFG = READY + "/" + EXPORT_RID + ".json"
AMEND_ID = "AM-F55-NEST"
AMEND_DRAFT = PLAN_DIR + "/AM-F55-NEST.draft.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
NODE_SURF = "/obj/G52_READ/surface_field"
NODE_VEL = "/obj/G52_READ/vel_field"
FIELDS = (("s", "surface"), ("vx", "vel.x"), ("vy", "vel.y"), ("vz", "vel.z"))      # Houdini axes: x = plan x, y = up, z = lateral (plan y)
CAP_CHAINS = 2                              # extra chains after a max_hours / crash stop (= auto_F55 rules)
POP_TOP = ("hip_sha256", "module_shas_at_chain_start", "precheck")
EXPORT_TOP_ALLOWED = {"run_id", "out_root", "f_start", "f_first", "f_end", "still_offset_m", "note", "restart", "f55", "precheck"}
EXPORT_CASE_ALLOWED = {"judged", "role", "restart_of", "restart_ckpt_frame", "f55_export"}
PHYS_KEYS = ("stage", "kind", "layout", "parms", "box", "bed", "sf", "dir", "wave", "drift", "solver", "gauges", "level_regions", "dir_check",
             "level_guard_m", "level_box", "n1_x", "n1_window", "shore_x", "fieldbox_frames", "analysis", "disk_stop_free_gb")   # = h52b3_long
DISK_MARGIN_GB = 20.0
HYCKPT_MAX_COOK_S = 300.0                   # loading v.1056 + one surface cook [guess: < 2 min]; a from-scratch cook of 1056 frames takes ~37 min
HYCKPT_TIMEOUT_S = 1200.0                   # hip load + checkpoint load + export, generous; a from-scratch cook is killed here
WATCH_MARK = "F55 nest watchdog"
COMMIT_LOW_GB = 3.0                         # = auto_F55 (plan execution rule: free commit < 3 GB on 2 polls -> <run>/STOP)
BRAKE = LOG_DIR + "/auto_F55_STOP"          # = auto_F55's brake file
AUTO_LOCK = LOG_DIR + "/auto_F55.lock"
CAP_CRASH = 2                               # crash / stale / watchdog resumes (= auto_F55 max_resumes)
CAP_MAX_HOURS = 2                           # max_hours resumes (= auto_F55 --cap-resumes default)
STALE_MIN, STALE_MIN_NO_PS = 45.0, 90.0     # = auto_F55
SLOT_WAIT_H = 6.0                           # how long a relaunch waits for its free commit before giving up
NEED_OPTION = dict(export="C2", C2ID="C2ID", C2="C2", pinit="C2", calib="C2")   # the plan's commit / disk need used by each step (export,
                                                                                # pinit (the parent scene) and calib (the C2 box): C2's)
WAIT_MIN = 20.0                             # entry guard: minutes to wait for a free machine (--wait-min)

# F7: the parent's own frame-1056 particles inside the C2ID box (hython 'hypart' from the checkpoint copy, the hyckpt path)
PINIT_NPZ = EXPORT_DIR + "/p_%05d.npz" % CKPT
PINIT_JSON = EXPORT_DIR + "/pinit_%05d.json" % CKPT
HYPART_JSON = EXPORT_DIR + "/hypart_%05d.json" % CKPT
PINIT_RULES = dict(above_sdf_frac_max=0.10, density_range=(6.0, 12.0), mean_dv_grid_max=0.5, top_minus_eta_median_range=(-0.6, 0.1))
# sanity bounds [chosen]: the top particle of a 1 m column sits about s_off (0.076 m) + up to dp below the parent's top surface
# C2 (dp 0.25): the lattice + a 48-frame still-water calibration of the level step (x55_nest_build.py --hython-calib)
CALIB_FRAMES = 48
CALIB_DIR = B55 + "/_scratch/nest_calib_C2"
CALIB_TGT = CALIB_DIR + "/still_export"
CALIB_JSON = LOG_DIR + "/calib55_C2.json"
CALIB_TIMEOUT_S = 3 * 3600.0
CALIB_RULES = dict(region=dict(x=(200.0, 300.0), y=(0.0, 20.0)), interior=dict(x=(200.0, 340.0), y=(0.0, 40.0)), last_n=12,
                   step_abs_max_m=0.3, settle_max_m=0.05)
CALIB_RULE_TEXT = ("48 frames (1056-1104) of the nest scene at C2's box and launch parms (dp 0.25, lattice, bands, band_lin 1) against a STILL "
                   "synthetic parent (SDF zero at its still offset 0.0759846568107605 m above its particle level 0, v = 0; no replay; "
                   "init_lvl_m 0); level L(f) = mean of the nest's R1 surface over the GN1 region x 200-300 m, y 0-20 m; level step = mean L "
                   "of the last 12 frames - L(1056) (the rise after creation; the dp 0.25 reading offset L(1056) - 0.076 m is reported, not "
                   "subtracted, as physics review M5); ok iff all 49 frames finite, |step| <= 0.3 m and the last 12 frames settled within "
                   "0.05 m (the level slope over the last 24 frames reported); C2 then fills its lattice AND runs its band water rule "
                   "(band_kill / band_seed) at the parent's particle level minus the step (parms.init_lvl_m): the calibrated still state "
                   "translated by the step, so its level after the rise = the parent's particle level")

# the nest-scene parms a launch adds (x55_nest_build.NEST_PARMS defines them on CTRL) [chosen; registered by AM-F55-NEST]
LAUNCH_PARMS = dict(nest_on=1.0, band_surf=1.0, rep_on=1.0, sim_f0=float(CKPT), relax_vert=0.0, kill_margin_dp=0.0, seed_margin_dp=0.0,
                    seed_depth_m=2.0, seed_r_dp=1.5, seed_fill_frac=0.5, w_min=1e-3, seed_once_per_frame=1.0, end_on=0.0, end_band_m=15.0,
                    s_off=STILL_OFFSET, bed_trust_m=1.0, band_lin=1.0, init_src=1.0, init_lvl_m=0.0)
LAUNCH_STR_PARMS = dict(tgt_dir=EXPORT_DIR, rep_dir=REPLAY_DIR, pinit_npz=PINIT_NPZ)
# per option (F7): C2ID starts from the parent's own particles; C2 (dp 0.25) from the lattice with the calibrated level step (None = read
# from CALIB_JSON at launch)
OPTION_PARMS = dict(C2ID=dict(init_src=1.0, init_lvl_m=0.0), C2=dict(init_src=0.0, init_lvl_m=None))
OPTION_STR_PARMS = dict(C2ID=dict(pinit_npz=PINIT_NPZ), C2=dict(pinit_npz=""))
PREVIOUS_REGISTRATION = dict(date="2026-10-19 06:05:51", code_sha256={
    "Tools/GWWaveGen/flip55/x55_nest_build.py": "9ac821577b1428a24c0946ced39e9aa185b500514f5068a73b4f6a026752cf36",
    "Tools/GWWaveGen/flip55/f55_nest.py": "67e130fdcc9ad0a59e595d7359a973d09fd53317b0a4fe52c62689d45511e841"},
    hip_sha256="8675f37ba65e450b32c344477dc396acc14668ad17a4b1d7260908e1a780a4fc")
# ONE design value overridden by the launch (review 2026-10-19 B1; registered by AM-F55-NEST before any nest run)
OVERRIDE_PARMS = dict(wall_taper_m=0.0)
OVERRIDE_FROM = dict(wall_taper_m=15.0)          # = the frozen design cfg (f55_pcfg.make_N: wall_taper_m = the x band width)
DERIVED_KEYS = ("parms." + k for k in list(LAUNCH_PARMS) + list(LAUNCH_STR_PARMS) + list(OVERRIDE_PARMS))
DERIVED_KEYS = tuple(DERIVED_KEYS) + ("dir", "still_offset_m", "precheck", "f55")
DERIVED_WHY = {
    "parms.wall_taper_m 15 -> 0 (OVERRIDE of the design value)": (
        "the frozen 15 m wall taper (f55_pcfg: wall_taper_m = the x band width, copied from the parent's inlet band, where the target must "
        "vanish at the generating wall) multiplies the nest's x-band velocity target by smooth01((x - 180)/15): 0 at the closed face x 180 m "
        "where the relaxation weight is 1, 0.18 at 4 m where it is 0.23 [computed], so the band relaxes u toward ~0 (a sponge) and waves "
        "enter only through the particle surface rule. [computed, physics review 2026-10-19: 1D linear shallow-water model of the band, h 17 m, "
        "closed wall at 180 m, the relaxw weights, per-frame surface relaxation with its dead band] amplitude reaching x 196.5-300 m relative to "
        "the parent 0.53 / 0.54 / 0.55 at T 9.33 / 7 / 5.6 s with the taper, 0.968 / 0.977 / 0.987 without it (phase error < 0.01 rad; 3 m "
        "taper 0.915, 5 m 0.85; no taper and no dead band 1.000). The y band already has none (sd_taper_m 0 in the design)"),
    "parms.nest_on / band_surf / rep_on / sim_f0": "switch the nest scene's parent-driven bands, the particle surface relaxation and the d(t) replay on; the "
                                                   "FLIP and static objects are created at frame 1056 (= the parent's checkpoint; the DOP network "
                                                   "itself starts at frame 1 like the parent's, so $SF = $F and checkpoint names are global frames)",
    "parms.relax_vert 0": "horizontal velocity only, as DFG-2B-V's inlet band (relax_apply never relaxes the vertical velocity)",
    "parms.s_off 0.0759846568107605": ("the parent's still offset [measured]: its surface SDF zero sits this far above the level its particles "
                                       "fill, so the nest's water (init, band kill / seed) is 'SDF + s_off < 0', the parent's PARTICLE level; "
                                       "filling to the SDF zero raised the C2ID level by +0.057 m (+0.67 % of the box water, +0.7 % of Hc) and "
                                       "C2's by +0.075 m [computed, physics review B3], half of GN1 / GN3's 2 %"),
    "parms.bed_trust_m 1": ("within 1 m (one parent cell) of the bed the parent's top surface decides water (y < e - s_off): the parent's SDF "
                            "stays positive 0.02-0.19 m above the bed on average in x 180-195 (max 0.46 m) and 15-34 % of columns read air at "
                            "bed + 0.125 m [measured, review M4], which made band_kill delete near-bed particles every frame and init skip "
                            "~60 m3 (C2ID) / ~165 m3 (C2) [computed]"),
    "parms.kill_margin_dp 0, seed_margin_dp 0, seed_r_dp 1.5, seed_fill_frac 0.5, seed_depth_m 2.0, w_min 1e-3, seed_once_per_frame 1":
        "the particle surface relaxation: delete band particles that are not the parent's water; seed parent-water lattice points where fewer "
        "than half the full-water count (4/3 pi 1.5^3 = 14.1) of nest particles lie within 1.5 dp (a local fill fraction); candidates down to "
        "2 m below the parent's top surface, band weight > 1e-3, once per frame (first substep), probability = the band weight over one frame. "
        "seed_margin_dp 0 (was 0.5) with s_off: the band level lives in about +-0.1 m of the parent's instead of [-0.34, +0.08] m (mean -0.095 m) "
        "for C2ID [computed, physics review M2]; a seed is a copy of its nearest nest particle (every attribute) with its own P, v and a fresh id",
    "parms.tgt_dir / rep_dir": "the parent export folder and its copied vd files",
    "parms.band_lin 1 (F2, 2026-10-19 fix)": (
        "nest-only band weight per FRAME w = chi (linear: 1 at the closed face, 0 at the band's inner edge 15 m in) instead of bands50's "
        "relaxw(chi) = (exp(chi^3.5) - 1)/(e - 1), for the velocity (per substep 1 - (1 - w)^(dts/dt0)) and the particle surface relaxation "
        "(probability per frame); nest_bands = a copy of bands50 with relaxw -> nest_prof (band_lin 0 = bands50 exactly, probed); the "
        "parent family's bands50 / relax_apply are not edited. [computed, diag_gn1/band_predict.json, linear 2-D band model] Hc_rel "
        "+0.005 and GN2 0.06-0.13 m for L15_linear vs +0.052 / 0.15-0.19 m for the relaxw design and -0.189 / 0.62-0.63 m as run"),
    "parms.init_src / pinit_npz (F7, 2026-10-19 fix)": (
        "C2ID (dp 0.5 = the parent's spacing) is created from the PARENT'S OWN frame-1056 particles inside the box (p_01056.npz, read by "
        "f55_nest.py pinit from DFG-2B-V's checkpoint copy v.1056.sim through the hyckpt path): the failed C2ID's lattice held 7.7 "
        "particles / m3 vs the parent's 8.9 [measured, diag_gn1] and FLIP reseeding raised its volume +2 % in 9 frames [measured, smoke]; "
        "C2 (dp 0.25, no parent particles at that spacing) keeps the lattice (init_src 0, pinit_npz '')"),
    "parms.init_lvl_m (C2 calibration, 2026-10-19 fix)": (
        "C2's lattice is filled to, and its band water rule (band_kill / band_seed) runs at, the parent's particle level minus the level "
        "step measured by f55_nest.py calib C2 (the rise of the nest's level after creation in still water; rule CALIB_RULE_TEXT; "
        "calib55_C2.json, tied to this hip / these tools / this build check): shifting the lattice alone would leave the bands at the "
        "unshifted level, a sink / source that undoes the shift in ~3-13 s at c = 13.7 m/s [computed, physics review 2026-10-19 B1]; "
        "C2's dp 0.25 reading offset is reported, not subtracted (physics review M5); C2ID 0"),
    "parms.end_on 0 / end_band_m 15": ("the OPTIONAL end band at the closed face x 356 m stays OFF (= the frozen design 'outflow: none'). It exists "
                                       "because the parent's swash reaches x 386.5 m (y <= 60) and is 0.1-0.64 m deep (mean over y) at x 355.5 m "
                                       "in frames 1057-1657, at most 402 m3 (0.46 % of the box) beyond x 356 m [measured, hf]: the closed face "
                                       "reflects it (GN3 is not at risk, GN1 may be). Switching it on is a design change that needs its own "
                                       "amendment; the export always carries its box eb; when on, its target is the parent's velocity with "
                                       "no taper toward the face (the B1 reason, review M7)"),
    "dir": "DFG-2B-V's table block (+ the design's parent_only / note): only so the frozen runner's OUT_DIRTAB check passes and pv53 reads the run as "
           "the FLIP52 family; dir_on 0 in the frozen parms: the table is never read by the nest's VEX",
    "still_offset_m": "DFG-2B-V's still offset 0.0759846568107605 m [measured]: the nest has no t 0.5-1.5 s window; records (r5 header) and the "
                      "pv53 / R0 rulers then use the parent's still level",
    "precheck / f55": "the launch precheck and the launch record replace the design cfg's (its precheck must be ok and its sha16 = the plan's)"}

# GN rules as computed here (registered verbatim by AM-F55-NEST; the plan's text is gates_nest GN1-GN3)
GN_RULES = dict(
    common=("parent = the JUDGED DFG-2B-V run (records every frame; the export rerun is bit-identical to it); both sides read with the same code: "
            "hf eta minus the still offset 0.0759846568107605 m (parent: its run records; nest: cfg still_offset_m), group 1 window "
            "[t_fn - 8, t_fn + 6] = [55, 69] s"),
    GN1=("region x 200-300 m, |y| <= 20 m: per hf frame Hc = max of e51 median3(eta) - eta0 in the region and its (x, y); the first r2 lips with "
         "g52_ana.r2_lips in x 200-335 m (AM-DFG1 test); 'conv' = g52b3_ana.pick_conv (largest Hc in [t_fn - 8, min(t_fn + 2, t_lip1)), t_lip1 = "
         "the first lip at t >= t_fn - 6.9 s); PASS iff |Hc_nest / Hc_parent - 1| <= 0.02 AND |x_nest - x_parent| <= 1.5 m AND |t_conv| diff "
         "<= 0.25 s AND both have t_lip1 with |diff| <= 0.25 s AND R0 hood_max and air_max of group 1 (f55_hollow measure of the nest, its own "
         "judge-like group and pv53 picks) within +-20 % of the frozen baseline hollow_baseline_DFGBV.json group 1"),
    GN2=("band inner edges on the parent's hf cells: A = x in [195, 197] m (cells 195.5, 196.5) with y <= 45 m, B = y in [43, 45] m (cells 43.5, "
         "44.5) with x >= 195 m; nest hf interpolated (bilinear) to those cell centres; frames 1057 .. f(lip1 of the parent's judge) - 1 (t < "
         "61.375 s); cells NaN on either side excluded (counted); PASS iff the pooled rms of (eta_nest - eta_parent) <= 0.05 x the parent's "
         "converged Hc of its frozen judge (judge_DFGB4.json group 1 conv Hc 8.046846 m -> 0.402 m)"),
    GN3=("column volume V = sum over hf cells with centres in x 180-356, y 0-60 m of max(eta - bed, 0) x cell area (NaN = dry = 0), each side on its "
         "own hf grid; PASS iff |V_nest / V_parent - 1| <= 0.02 on EVERY frame 1057-1657 present on both sides and both sides have all 601 frames"),
    order="GN1-GN3 on C2ID must all pass before C2 runs (auto_F55 stops otherwise: no reading; fallback A375)")
GN_TOL = dict(Hc_rel=0.02, x_m=1.5, t_s=0.25, hollow_rel=0.20, gn2_frac=0.05, gn3_rel=0.02)
GN1_REGION = dict(x=(200.0, 300.0), y=20.0)
GN2_EDGES = dict(A=dict(x=(195.0, 197.0), y_max=45.0), B=dict(y=(43.0, 45.0), x_min=195.0))
GN3_BOX = dict(x=(180.0, 356.0), y=(0.0, 60.0))
LIP_X = (200.0, 335.0)
T_FN = 63.0


# ====================================================================== small helpers (stdlib only: also used inside hython)
def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jtry(p):
    try:
        return jload(p)
    except Exception:
        return None


def canon(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=float)


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    try:
        import numpy as np
        if isinstance(o, np.floating):
            v = float(o)
            return v if math.isfinite(v) else None
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return clean(o.tolist())
    except ImportError:
        pass
    return o


def under(p, root):
    a = os.path.abspath(p).replace("\\", "/").lower().rstrip("/") + "/"
    return a.startswith(root.lower().rstrip("/") + "/")


def guard(p):
    """every file this tool writes lies under Unity/Build/FLIP55 (the nest scene: x55_nest_build.py only)."""
    if not under(p, B55):
        raise SystemExit("refused to write %s: outside Unity/Build/FLIP55" % p)
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    return p


def jdump(o, p):
    guard(p)
    tmp = p + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p


def rel(p):
    p = str(p).replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO + "/") else p


def no_temp(o):
    s = json.dumps(o, ensure_ascii=False, default=str).lower().replace("\\\\", "/").replace("\\", "/")
    return not ("appdata" in s or "/temp/" in s or "/tmp/" in s.replace("tmp_houdini", ""))


def final(d):
    """the ONE final json line auto_F55 reads (last line that starts with '{')."""
    d = clean(d)
    print(json.dumps(d, ensure_ascii=False, default=str), flush=True)
    return 0 if d.get("ok") else 1


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


def frames_of(f0, f1):
    return list(range(int(f0), int(f1) + 1))


# ====================================================================== hython side: the read-only export of the parent's fields
def crop_volume(np, vol, o, box):
    """one Houdini volume -> (array [lat, up, x] cropped by INDEX to the plan box, p0 plan (Houdini axis order x, up, lat), d). box =
    dict(x=[a, b], y=[a, b]) in plan metres (y = lateral = Houdini z); the full height is kept. Nothing is resampled."""
    r = vol.resolution()
    q0 = vol.indexToPos((0, 0, 0))
    q1 = vol.indexToPos((1, 1, 1))
    p0 = [float(q0[i]) - float(o[i]) for i in range(3)]
    d = [float(q1[i]) - float(q0[i]) for i in range(3)]

    def rng(axis, lo, hi):
        i0 = int(math.ceil((lo - p0[axis]) / d[axis] - 1e-6))
        i1 = int(math.floor((hi - p0[axis]) / d[axis] + 1e-6))
        return max(i0, 0), min(i1, int(r[axis]) - 1)
    ix0, ix1 = rng(0, float(box["x"][0]), float(box["x"][1]))
    iz0, iz1 = rng(2, float(box["y"][0]), float(box["y"][1]))
    if ix1 < ix0 or iz1 < iz0:
        raise ValueError("empty crop %s of a volume res %s p0 %s" % (box, list(r), p0))
    a = np.frombuffer(vol.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0])
    c = np.ascontiguousarray(a[iz0:iz1 + 1, :, ix0:ix1 + 1])
    return c, [p0[0] + ix0 * d[0], p0[1], p0[2] + iz0 * d[2]], d


def export_frame(hou, spec, f, out_dir, t=None):
    """read the two cooked fields of the CURRENT frame and write <out_dir>/x_<f>.npz (atomic). Returns a small record."""
    import numpy as np
    t0 = time.time()
    sg = hou.node(spec.get("surf_node", NODE_SURF)).geometry()
    vg = hou.node(spec.get("vel_node", NODE_VEL)).geometry()
    vols = {}
    for g in (sg, vg):
        if g is None:
            continue
        for p in g.prims():
            try:
                nm = p.attribValue("name")
            except Exception:
                nm = None
            if nm:
                vols[nm] = p
    o = spec["o"]
    arrs, meta = {}, dict(frame=int(f), t=(int(f) - 1) / FPS if t is None else float(t), o_parent=o, boxes=spec["boxes"], keys={},
                          tool=TOOL_REL, kind="F55 parent export (read-only)")
    for bname, box in spec["boxes"].items():
        for key, hname in FIELDS:
            if hname not in vols:
                raise ValueError("field %s missing at frame %d (have %s)" % (hname, f, sorted(vols)))
            c, p0, d = crop_volume(np, vols[hname], o, box)
            dt = np.float32 if key == "s" else np.float16
            arrs["%s_%s" % (bname, key)] = c.astype(dt)
            meta["keys"]["%s_%s" % (bname, key)] = dict(p0=p0, d=d, shape=list(c.shape), dtype=np.dtype(dt).name, field=hname)
    os.makedirs(out_dir, exist_ok=True)
    p = os.path.join(out_dir, "x_%05d.npz" % int(f)).replace("\\", "/")
    tmp = p + ".part"
    with open(tmp, "wb") as fh:
        np.savez_compressed(fh, meta=np.array(json.dumps(meta)), **arrs)
    os.replace(tmp, p)
    return dict(frame=int(f), bytes=os.path.getsize(p), s=round(time.time() - t0, 3))


class ExportHook:
    """wraps hou.setFrame: before the runner sets frame f + 1, the fields of frame f (cooked by the runner itself) are exported. The original
    setFrame is called with the same argument; nothing else of hou is touched."""

    def __init__(self, hou, spec, out_dir, log_path):
        self.hou, self.spec, self.out_dir, self.log_path = hou, spec, out_dir, log_path
        self.lo, self.hi = int(spec["frames"][0]), int(spec["frames"][1])
        self.real = hou.setFrame
        self.last = None
        self.done, self.rows, self.errors = set(), [], []
        self.t_export = 0.0
        self.calls = 0

    def install(self):
        self.hou.setFrame = self.set_frame
        return self

    def set_frame(self, f):
        self.calls += 1
        if self.last is not None and self.last not in self.done:
            self.export(self.last)
        self.last = int(round(float(f)))
        return self.real(f)

    def export(self, f):
        if not (self.lo <= f <= self.hi):
            return
        t0 = time.time()
        try:
            self.rows.append(export_frame(self.hou, self.spec, f, self.out_dir))
            self.done.add(f)
        except Exception as e:
            if len(self.errors) < 50:
                self.errors.append("%d %r" % (f, e))
        self.t_export += time.time() - t0

    def finish(self, extra=None):
        try:
            if self.last is not None and self.last not in self.done:
                self.export(self.last)
        finally:
            self.hou.setFrame = self.real
        rec = dict(date=now(), tool=TOOL_REL, kind="export hook log (one launch)", frames_exported=sorted(self.done), n=len(self.done),
                   setframe_calls=self.calls, errors=self.errors, export_s=round(self.t_export, 1), rows_tail=self.rows[-3:])
        if extra:
            rec.update(extra)
        try:
            os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
            with open(self.log_path, "w", encoding="utf-8") as fh:
                json.dump(rec, fh, indent=1, ensure_ascii=False, default=str)
        except Exception:
            pass
        return rec


def hy_run(cpath):
    """hython f55_nest.py hyrun <launch cfg> (started by the patched chain): the FROZEN g52b3_run.py, unchanged, by runpy, with either the
    read-only export hook (mode export) or g52b3_common.HIP = the nest scene (mode nest)."""
    import hou
    import runpy
    cfg = jload(cpath)
    f5 = cfg.get("f55") or {}
    mode = f5.get("mode")
    rs = sha(RUNNER)
    if rs != RUNNER_SHA:
        print("F55NEST refused: g52b3_run.py sha %s differs from the frozen %s" % (rs, RUNNER_SHA), flush=True)
        sys.exit(3)
    hook = None
    if mode == "export":
        spec = f5["export"]
        out = os.path.join(B55, "runs", cfg["run_id"], "export").replace("\\", "/")
        if not under(out, B55):
            sys.exit(3)
        hook = ExportHook(hou, spec, out, os.path.join(out, "hook_c%05d.json" % int(cfg["f_start"]))).install()
    elif mode == "nest":
        for p in (T52, TOOLS + "/flip48", T49, T52B3):          # the runner's own sys.path order (its first lines), so the module is the same
            if p not in sys.path:
                sys.path.insert(0, p)
        import g52b3_common as GCR
        hs = sha(NEST_HIP)
        if hs != f5.get("nest_hip_sha256"):
            print("F55NEST refused: nest scene sha %s differs from the launch cfg %s" % (hs, f5.get("nest_hip_sha256")), flush=True)
            sys.exit(3)
        GCR.HIP = NEST_HIP
    else:
        print("F55NEST refused: cfg f55.mode %r" % mode, flush=True)
        sys.exit(3)
    sys.argv = [RUNNER, cpath]
    code = 0
    try:
        runpy.run_path(RUNNER, run_name="__main__")
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        if hook is not None:
            hook.finish(dict(runner=rel(RUNNER), runner_sha256=rs, cfg=rel(cpath)))
    sys.exit(code)


def hy_ckpt(cpath):
    """hython f55_nest.py hyckpt <export cfg>: frame 1056 of the parent from its own checkpoint (a COPY of v.1056.sim in ckpt_1056), read-only."""
    import hou
    cfg = jload(cpath)
    spec = (cfg.get("f55") or {})["export"]
    rec = dict(date=now(), tool=TOOL_REL, kind="frame-1056 export from DFG-2B-V's checkpoint copy (separate hython; the rerun is not touched)")
    hs = sha(DFGBV_HIP)
    rec["hip_sha256"] = hs
    if hs != DFGBV_HIP_SHA:
        rec["error"] = "DFG-2B-V scene sha differs"
    else:
        hou.hipFile.load(DFGBV_HIP, suppress_save_prompt=True, ignore_load_warnings=True)
        ctrl = hou.node("/obj/G52_SETUP/CTRL")
        for k, v in cfg.get("parms", {}).items():
            if ctrl.parm(k) is not None:
                ctrl.parm(k).set(v)
        fs = hou.node("/obj/G52_SIM/flipsolver")
        sv = cfg.get("solver", {})
        fs.parm("veltransfer").set(sv.get("veltransfer", "flip"))
        fs.parm("donarrowband").set(int(sv.get("donarrowband", 0)))
        ctrl.parm("ckpt").set(CKPT_LOAD_DIR)
        ctrl.parm("ckpt_on").set(1)
        ctrl.parm("ckpt_every").set(int(cfg.get("ckpt_every", 48)))
        dop = hou.node("/obj/G52_SIM")
        want = (CKPT_LOAD_DIR + "/v.%04d.sim" % CKPT).replace("\\", "/")
        try:
            got = dop.parm("explicitcachename").evalAtFrame(CKPT).replace("\\", "/")
        except Exception as e:
            got = "eval error %r" % e
        # informational only ($SF may not expand outside a DOP cook); the proof is validate_export's R1 alignment of frame 1056 against the
        # judged run's hf record of frame 1056
        rec.update(cache_name=got, cache_name_as_expected=bool(got == want), ckpt_parm=ctrl.parm("ckpt").evalAsString(),
                   ckpt_present=os.path.exists(want), ckpt_sha256=sha(want))
        if not os.path.exists(want) or ctrl.parm("ckpt").evalAsString().replace("\\", "/") != CKPT_LOAD_DIR:
            rec["error"] = "the checkpoint copy %s is missing or CTRL ckpt does not point at its folder" % want
        else:
            hou.setSimulationEnabled(True)
            t0 = time.time()
            hou.setFrame(CKPT)
            g = hou.node(NODE_SURF).geometry()
            rec["cook_s"] = round(time.time() - t0, 2)
            try:
                rec["particles"] = int(dop.simulation().findObject("water").geometry().intrinsicValue("pointcount"))
            except Exception as e:
                rec["particles_error"] = repr(e)[:200]
            rec["surface_prims"] = len(g.prims()) if g is not None else 0
            if rec["cook_s"] > HYCKPT_MAX_COOK_S:
                # a cook this long simulated from frame 1 instead of loading v.1056; hyckpt sets only the float parms (not the generator
                # table dir_npz, vol_dir, sf_tab the runner sets), so that state is NOT DFG-2B-V's: refuse (review M6 / code M1)
                rec["error"] = ("frame %d cooked in %.0f s > %.0f s: the DOP did not load the checkpoint copy (a from-scratch cook lacks the "
                                "runner's tables); nothing exported" % (CKPT, rec["cook_s"], HYCKPT_MAX_COOK_S))
            else:
                spec_c = dict(spec, boxes=dict(spec["boxes"], **(spec.get("boxes_ckpt_extra") or {})))
                rec["export"] = export_frame(hou, spec_c, CKPT, EXPORT_DIR)
            rec["ckpt_sha256_after"] = sha(want)
    p = EXPORT_DIR + "/hyckpt_%05d.json" % CKPT
    os.makedirs(EXPORT_DIR, exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, ensure_ascii=False, default=str)
    print("F55NEST hyckpt", json.dumps(rec, default=str)[:600], flush=True)
    sys.exit(0 if not rec.get("error") else 2)


def pinit_box(C=None):
    """the C2ID nest box in plan metres (x0 .. x0 + Lx, lateral 0 .. W) = f55_common.OPTIONS['C2ID'] through f55_common.box."""
    for p in (T52, TOOLS + "/flip48", T49, T52B3):          # g52b3_common's own imports (also inside hython)
        if p not in sys.path:
            sys.path.append(p)
    C = C or C_()
    o = C.OPTIONS["C2ID"]
    b = C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"])
    return dict(x0=float(b["x0"]), Lx=float(b["Lx"]), W=float(b["W"]))


def hy_part(cpath):
    """hython f55_nest.py hypart <export cfg> (F7): the PARTICLES of DFG-2B-V at frame 1056 from its own checkpoint (the copy v.1056.sim in
    ckpt_1056, loaded exactly as hyckpt loads it), read-only: P (Houdini, float32) and v of the water object inside the C2ID box ->
    p_01056.npz (atomic) + hypart_01056.json. Nothing of the export is rewritten."""
    import hou
    import numpy as np
    cfg = jload(cpath)
    spec = (cfg.get("f55") or {})["export"]
    rec = dict(date=now(), tool=TOOL_REL, kind="frame-1056 PARTICLES of DFG-2B-V from its checkpoint copy (separate hython, read-only; F7: the "
                                               "C2ID nest's initial state)")
    hs = sha(DFGBV_HIP)
    rec["hip_sha256"] = hs
    if hs != DFGBV_HIP_SHA:
        rec["error"] = "DFG-2B-V scene sha differs"
    else:
        hou.hipFile.load(DFGBV_HIP, suppress_save_prompt=True, ignore_load_warnings=True)
        ctrl = hou.node("/obj/G52_SETUP/CTRL")
        for k, v in cfg.get("parms", {}).items():
            if ctrl.parm(k) is not None:
                ctrl.parm(k).set(v)
        fs = hou.node("/obj/G52_SIM/flipsolver")
        sv = cfg.get("solver", {})
        fs.parm("veltransfer").set(sv.get("veltransfer", "flip"))
        fs.parm("donarrowband").set(int(sv.get("donarrowband", 0)))
        ctrl.parm("ckpt").set(CKPT_LOAD_DIR)
        ctrl.parm("ckpt_on").set(1)
        ctrl.parm("ckpt_every").set(int(cfg.get("ckpt_every", 48)))
        dop = hou.node("/obj/G52_SIM")
        want = (CKPT_LOAD_DIR + "/v.%04d.sim" % CKPT).replace("\\", "/")
        rec.update(ckpt_parm=ctrl.parm("ckpt").evalAsString(), ckpt_present=os.path.exists(want), ckpt_sha256=sha(want))
        if not os.path.exists(want) or ctrl.parm("ckpt").evalAsString().replace("\\", "/") != CKPT_LOAD_DIR:
            rec["error"] = "the checkpoint copy %s is missing or CTRL ckpt does not point at its folder" % want
        else:
            hou.setSimulationEnabled(True)
            t0 = time.time()
            hou.setFrame(CKPT)
            wobj = dop.simulation().findObject("water")
            rec["cook_s"] = round(time.time() - t0, 2)
            if rec["cook_s"] > HYCKPT_MAX_COOK_S or wobj is None:
                rec["error"] = ("frame %d cooked in %.0f s > %.0f s or no water object: the DOP did not load the checkpoint copy; nothing "
                                "exported" % (CKPT, rec["cook_s"], HYCKPT_MAX_COOK_S))
            else:
                g = wobj.geometry()
                n = int(g.intrinsicValue("pointcount"))
                P = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3)
                V = np.frombuffer(g.pointFloatAttribValuesAsString("v"), dtype=np.float32).reshape(-1, 3)
                o = np.array(spec["o"], np.float64)
                bx = pinit_box()
                pl = P.astype(np.float64) - o
                keep = (pl[:, 0] >= bx["x0"]) & (pl[:, 0] <= bx["x0"] + bx["Lx"]) & (pl[:, 2] >= 0.0) & (pl[:, 2] <= bx["W"])
                names = sorted(a.name() for a in g.pointAttribs())
                ps = None
                if "pscale" in names:
                    pa = np.array(g.pointFloatAttribValues("pscale"))
                    ps = [float(pa.min()), float(pa.max())]
                meta = dict(frame=CKPT, t=(CKPT - 1) / FPS, o_parent=[float(c) for c in o], box=bx, n_total=n, n_box=int(keep.sum()),
                            point_attribs=names, pscale_min_max=ps, ckpt=rel(want), ckpt_sha256=rec["ckpt_sha256"], hip_sha256=hs, tool=TOOL_REL,
                            kind="F55 parent particles at frame 1056 inside the C2ID box (read-only; f55_nest.py hypart)",
                            rule="P_h = the parent's Houdini positions (float32, unchanged), v = its particle velocity; kept where plan x0 <= x <= "
                                 "x0 + Lx and 0 <= lateral <= W (plan = P_h - o_parent)")
                guard(PINIT_NPZ)
                tmp = PINIT_NPZ + ".part"
                with open(tmp, "wb") as fh:
                    np.savez_compressed(fh, P_h=np.ascontiguousarray(P[keep]), v=np.ascontiguousarray(V[keep]), meta=np.array(json.dumps(meta)))
                os.replace(tmp, PINIT_NPZ)
                rec.update(n_total=n, n_box=int(keep.sum()), point_attribs=names, pscale_min_max=ps, file=rel(PINIT_NPZ),
                           bytes=os.path.getsize(PINIT_NPZ), sha256=sha(PINIT_NPZ))
            rec["ckpt_sha256_after"] = sha(want)
    with open(guard(HYPART_JSON), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, ensure_ascii=False, default=str)
    print("F55NEST hypart", json.dumps(rec, default=str)[:600], flush=True)
    sys.exit(0 if not rec.get("error") else 2)


# ====================================================================== the chain: g52b3_chain.py with three counted replacements, in memory
CHAIN_REPL = (
    ('RUN = GC.TOOLS52B3 + "/g52b3_run.py"', 'RUN = %r' % SELF, 1),
    ("subprocess.run([GC.HY, RUN, cpath],", 'subprocess.run([GC.HY, RUN, "hyrun", cpath],', 1),
    ('TMP = GC.B52B3 + "/tmp_houdini"', 'TMP = %r' % TMP_HOUDINI, 1),
)


def chain_source():
    raw = open(CHAIN, "rb").read()
    h = hashlib.sha256(raw).hexdigest()
    if h != CHAIN_SHA:
        raise SystemExit("g52b3_chain.py sha256 %s differs from the frozen %s: not run" % (h, CHAIN_SHA))
    s = raw.decode("utf-8")
    counts = {}
    for old, new, n in CHAIN_REPL:
        k = s.count(old)
        counts[old[:40]] = k
        if k != n:
            raise SystemExit("chain replacement %r: %d matches, expected %d" % (old[:60], k, n))
        s = s.replace(old, new)
    return s, counts


def cmd_chain(mode, cfgp):
    """py -3.10 -B f55_nest.py chain export|nest <cfg>: executes the patched chain as __main__ (its own gate, resume, launches, ledger)."""
    cfg = jload(cfgp)
    if (cfg.get("f55") or {}).get("mode") != mode:
        raise SystemExit("cfg f55.mode %r is not %r" % ((cfg.get("f55") or {}).get("mode"), mode))
    src, _ = chain_source()
    for p in (TOOLS + "/flip46", T49, T52B3):
        if p not in sys.path:
            sys.path.insert(0, p)
    import g52b3_common as GCC
    if mode == "nest":
        GCC.HIP = NEST_HIP                       # the chain's gate checks the nest scene against the nest build check
        GCC.BUILD_CHECK = NEST_BUILD_CHECK
    sys.argv = [CHAIN, cfgp]
    ns = dict(__name__="__main__", __file__=CHAIN, __builtins__=__builtins__)
    exec(compile(src, CHAIN + " [3 counted replacements in memory by flip55/f55_nest.py]", "exec"), ns)
    return 0


# ====================================================================== chain state (as auto_F55 / h52b3_long)
def chain_segment(ls):
    if not ls:
        return dict(state="absent", max_hours_stop=False, last="")
    ends = [i for i, l in enumerate(ls) if " chain end " in l]
    starts = [i for i, l in enumerate(ls) if " chain start " in l]
    gates = [i for i, l in enumerate(ls) if "gate failed" in l]
    if gates and gates[-1] > max(ends + starts + [-1]):
        return dict(state="gate_failed", max_hours_stop=False, last=ls[-1])
    if not ends or (starts and starts[-1] > ends[-1]):
        return dict(state="running", max_hours_stop=False, last=ls[-1])
    seg = ls[(starts[-1] if starts else 0):]
    done = any(" stopped None " in (l + " ") for l in seg if " chunk " in l)
    mh = any("max_hours exceeded" in l for l in seg)
    return dict(state="complete" if done else "incomplete", max_hours_stop=bool(mh and not done), last=ls[-1])


def frames_done(rd):
    best = 0
    for p in glob.glob(os.path.join(rd, "run_c*.json")):
        try:
            best = max(best, int((jtry(p) or {}).get("f_end_done") or 0))
        except Exception:
            pass
    return best


def run_state(rd, f_end):
    ls = open(rd + "/chain.log", encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(rd + "/chain.log") else []
    seg = chain_segment(ls)
    fd = frames_done(rd)
    seg["frames_done"] = fd
    seg["complete"] = bool(fd >= f_end and seg["state"] == "complete")
    return seg


import re                                       # noqa: E402
import threading                                # noqa: E402
BUSY_RE = re.compile(r"(\w+_chain\.py|\w+_run\.py|x5\w*_build\.py|x54_check\.py|r54_xcheck\.py|pv53\.py|h52b\w*_(?:hero|long)\.py|p52bh_preview\.py|"
                     r"f55_nest\.py)", re.I)                 # = auto_F55.BUSY_RE
UNITY_BATCH_RE = re.compile(r"unity\.exe.*-batchmode", re.I)


def processes():
    """[(pid, ppid, name, command line)] of the python / py / hython / Unity processes, or None when the scan fails."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='py.exe' or Name='hython.exe' or Name='pythonw.exe' or "
                            "Name='Unity.exe'\" | ForEach-Object { \"$($_.ProcessId) $($_.ParentProcessId) $($_.Name) $($_.CommandLine)\" }"],
                           capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return None
        out = []
        for ln in (r.stdout or "").splitlines():
            q = ln.strip().split(" ", 3)
            if len(q) >= 3 and q[0].isdigit() and q[1].isdigit():
                out.append((int(q[0]), int(q[1]), q[2], q[3] if len(q) > 3 else ""))
        return out
    except Exception:
        return None


def ancestors(procs, pid=None):
    """this process and its ancestors among procs (the py launcher, an auto_F55 that called us): never 'busy' for ourselves."""
    me = os.getpid()
    pid = me if pid is None else pid
    par = {p: pp for p, pp, _, _ in procs}
    seen = {pid}
    if pid == me:
        try:
            seen.add(os.getppid())
        except Exception:
            pass
    for q in list(seen):                     # up the parent chain while it stays among the scanned (python / py / hython / Unity) processes
        for _ in range(32):
            pq = par.get(q)
            if pq is None or pq in seen or pq not in par:
                break
            seen.add(pq)
            q = pq
    return seen


def busy_scan(procs, mine=None):
    """the other pipeline processes (auto_F55.BUSY_RE), hython, Unity batch, excluding this process, its ancestors and its OWN descendants
    (never its siblings: a chain started from the same shell or by the same auto_F55 counts as busy)."""
    if procs is None:
        return None
    mine = set(mine or ancestors(procs))
    me = os.getpid()
    kids = {p for p, pp, _, _ in procs if pp == me}
    for _ in range(8):                                  # descendants (a chain this process launched)
        more = {p for p, pp, _, _ in procs if pp in kids and p not in kids}
        if not more:
            break
        kids |= more
    skip = mine | kids
    other = [(p, n, c) for p, pp, n, c in procs if p not in skip]
    return dict(pipeline=[c[:160] for p, n, c in other if BUSY_RE.search(c)], hython=[p for p, n, c in other if n.lower() == "hython.exe"],
                unity_batch=[c[:120] for p, n, c in other if UNITY_BATCH_RE.search(c)])


def auto_lock_foreign(procs):
    """True when a LIVE auto_F55 holds its lock and is not our caller (an auto_F55 run of C2 calls this tool: then it is an ancestor)."""
    try:
        pid = int(open(AUTO_LOCK, encoding="utf-8").read().split()[0])
    except Exception:
        return False
    if procs is None:
        return True
    live = any(p == pid for p, _, _, _ in procs)
    return bool(live and pid not in ancestors(procs))


def need_of(step):
    C = C_()
    st = (((jtry(C.PLAN) or {}).get("options") or {}).get(NEED_OPTION[step]) or {}).get("stages", {}).get("g1") or {}
    return float(st.get("commit_need_gb") or 99.0), float(st.get("disk_need_gb") or 999.0)


def free_commit():
    return C_().commit_gb()[0]


def entry_guard(what, step, wait_min=20.0, poll=60.0, confirm=2, scan=None, commit=None, disk=None, sleep=time.sleep):
    """the machine is free for a real step: no other pipeline process / hython / Unity batch, no foreign live auto_F55 lock, no brake file,
    free commit >= the plan's need of the step and G: >= its disk need, on `confirm` polls in a row; waits up to wait_min minutes. The
    functions scan / commit / disk can be replaced (selftest)."""
    C = C_()
    scan = scan or processes
    commit = commit or free_commit
    disk = disk or (lambda: C.free_disk_gb("G:/"))
    need, dneed = need_of(step)
    t0, streak, last = time.time(), 0, {}
    while True:
        procs = scan()
        b = busy_scan(procs)
        fc, fd = commit(), disk()
        why = []
        if b is None:
            why.append("process scan failed")
        else:
            if b["pipeline"]:
                why.append("pipeline busy: %s" % "; ".join(b["pipeline"][:2]))
            if b["hython"]:
                why.append("hython running (pid %s)" % b["hython"][:3])
            if b["unity_batch"]:
                why.append("Unity batch running")
        if auto_lock_foreign(procs):
            why.append("a live auto_F55 holds %s and is not the caller" % rel(AUTO_LOCK))
        if os.path.exists(BRAKE):
            why.append("brake file %s" % rel(BRAKE))
        if fc is None or fc < need:
            why.append("free commit %s GB < %.2f GB" % (None if fc is None else round(fc, 1), need))
        if fd is None or fd < dneed:
            why.append("G: free %s GB < %.0f GB" % (None if fd is None else round(fd, 0), dneed))
        last = dict(what=what, step=step, need_commit_gb=need, need_disk_gb=dneed, free_commit_gb=fc, free_disk_gb=fd, busy=b, why=why)
        streak = streak + 1 if not why else 0
        if streak >= confirm:
            return dict(last, ok=True, why=None, waited_s=round(time.time() - t0, 1))
        if os.path.exists(BRAKE) or time.time() - t0 > wait_min * 60.0:
            return dict(last, ok=False, why="; ".join(why) or "not confirmed", waited_s=round(time.time() - t0, 1))
        sleep(poll)


class NestWatch(threading.Thread):
    """the plan's execution rule during a chain (= auto_F55.Watch): free commit < 3 GB on 2 polls, or the brake file -> <run>/STOP with the
    marker WATCH_MARK (the chain reads STOP before each launch; nothing is killed)."""

    def __init__(self, rd, poll=60.0, commit=None, brake=BRAKE):
        super().__init__(daemon=True)
        self.rd, self.poll, self.ev, self.brake = rd, poll, threading.Event(), brake
        self.commit = commit or free_commit
        self.reason, self.min_free, self.low = None, None, 0

    def run(self):
        while not self.ev.wait(self.poll):
            self.tick()

    def tick(self):
        fr = self.commit()
        if fr is not None:
            self.min_free = fr if self.min_free is None else min(self.min_free, fr)
            self.low = (self.low + 1) if fr < COMMIT_LOW_GB else 0
        why = None
        if self.reason is None and self.low >= 2:
            why = "commit"
        elif self.reason is None and os.path.exists(self.brake):
            why = "brake"
        if why:
            self.reason = why
            try:
                with open(guard(self.rd + "/STOP"), "w", encoding="utf-8") as fh:
                    fh.write("%s %s: %s\n" % (now(), WATCH_MARK, ("free commit %.1f GB < %.0f GB on 2 polls" % (fr, COMMIT_LOW_GB))
                                              if why == "commit" else "brake file %s" % self.brake))
            except Exception:
                pass
        return why

    def stop(self):
        self.ev.set()


def clear_own_stop(rd):
    """remove <run>/STOP only when this watchdog wrote it (a STOP written by a person or another tool stays)."""
    p = rd + "/STOP"
    try:
        if os.path.exists(p) and WATCH_MARK in open(p, encoding="utf-8", errors="replace").read():
            os.remove(p)
            return True
    except Exception:
        pass
    return False


def chain_alive(rid, procs=None):
    """True / False, or None when the process scan fails (then the caller treats the chain as possibly alive)."""
    procs = processes() if procs is None else procs
    if procs is None:
        return None
    me = ancestors(procs)
    return any(rid in c and ("f55_nest.py" in c or "g52b3_run.py" in c) and p not in me for p, _, _, c in procs)


def newest_age_min(rd):
    ts = []
    for p in glob.glob(rd + "/*") + glob.glob(rd + "/ckpt/*"):
        try:
            ts.append(os.path.getmtime(p))
        except OSError:
            pass
    return (time.time() - max(ts)) / 60.0 if ts else 1e9


def wait_slot(step, log, max_h=SLOT_WAIT_H, poll=60.0):
    """before a (re)launch: no brake file, free commit >= the plan's need on 2 polls (the watchdog's own STOP is removed once it is)."""
    need, _ = need_of(step)
    t0, streak, n = time.time(), 0, 0
    while True:
        if os.path.exists(BRAKE):
            return "brake"
        fc = free_commit()
        streak = streak + 1 if (fc is not None and fc >= need) else 0
        if streak >= 2:
            return "ok"
        if n % 15 == 0:
            log("waiting for free commit >= %.2f GB (now %s GB)" % (need, None if fc is None else round(fc, 1)))
        n += 1
        if time.time() - t0 > max_h * 3600.0:
            return "timeout"
        time.sleep(poll)


def drive_chain(mode, cfgp, rid, f_end, log, step, launch=None, sleep=time.sleep, rd=None):
    """run the patched chain until the run reaches f_end, with auto_F55.run_stage's rules: a running chain is adopted, never a second one (a
    chain with no live process and no file change for 45 min, 90 min when the process scan fails, is stale); resumes from the last
    checkpoint after a crash / stale / guard / watchdog stop up to CAP_CRASH and after a max_hours stop up to CAP_MAX_HOURS; a gate failure, a
    foreign STOP file or the brake stops at once. Every launch first waits for its free commit (wait_slot) and runs under NestWatch.
    `launch` / `rd` replace the chain launch and the run folder (selftest)."""
    rd = rd or RUNS_ROOT + "/" + rid
    hist = []
    n_crash = n_mh = launched = 0
    stop = None
    for _ in range(CAP_CRASH + CAP_MAX_HOURS + 400):
        st = run_state(rd, f_end)
        if st["complete"]:
            break
        if st["state"] == "gate_failed":
            stop = "the chain's start gate refused (read %s/STOPPED_PRECHECK.txt)" % rel(rd)
            break
        alive = None
        for _k in range(3):                              # a failed scan is retried before it counts as unknown
            alive = chain_alive(rid)
            if alive is not None:
                break
        if alive or st["state"] == "running":
            age = newest_age_min(rd)
            if alive is True or (alive is False and age <= STALE_MIN) or (alive is None and age <= STALE_MIN_NO_PS):
                if launched == 0 and not hist:
                    log("a chain of %s is running (process %s); adopted, never a second chain" % (rid, "alive" if alive else alive))
                sleep(60)
                continue
            if n_crash >= CAP_CRASH:
                stop = "chain stale (process %s, no file change %.0f min) and %d resumes used" % (alive, age, n_crash)
                break
            n_crash += 1
            log("chain of %s stale (process %s, no file change %.0f min): resume %d/%d" % (rid, alive, age, n_crash, CAP_CRASH))
        elif st["state"] == "absent":
            if launched:
                stop = "the chain left no chain.log after a launch (see _logs/nest_chain_%s.txt)" % rid
                break
        elif st.get("max_hours_stop"):
            if n_mh >= CAP_MAX_HOURS:
                stop = "max_hours stop and %d max_hours resumes used" % n_mh
                break
            n_mh += 1
            log("max_hours stop of %s (not an error): resume %d/%d from the last checkpoint" % (rid, n_mh, CAP_MAX_HOURS))
        else:
            if n_crash >= CAP_CRASH:
                stop = "stopped below f_end %d (state %s) and %d resumes used" % (f_end, st["state"], n_crash)
                break
            n_crash += 1
            log("chain of %s stopped below f_end %d (crash / guard / watchdog): resume %d/%d" % (rid, f_end, n_crash, CAP_CRASH))
        w = wait_slot(step, log) if launch is None else "ok"
        if w != "ok":
            stop = "no slot (%s)" % w
            break
        clear_own_stop(rd)
        if os.path.exists(rd + "/STOP"):
            stop = "a STOP file not written by this watchdog is in %s (a person or another tool stopped the run)" % rel(rd)
            break
        wd = NestWatch(rd)
        if launch is None:
            wd.start()
        log("chain launch %d for %s (state %s, frames done %d)" % (launched + 1, rid, st["state"], st["frames_done"]))
        try:
            if launch is None:
                with open(guard(LOG_DIR + "/nest_chain_%s.txt" % rid), "a", encoding="utf-8") as lf:
                    rc = subprocess.run(["py", "-3.10", "-B", SELF, "chain", mode, cfgp], cwd=REPO, stdin=subprocess.DEVNULL, stdout=lf,
                                        stderr=subprocess.STDOUT).returncode
            else:
                rc = launch(wd)
        finally:
            wd.stop()
        launched += 1
        st = run_state(rd, f_end)
        hist.append(dict(chain=launched, rc=rc, state=st["state"], frames_done=st["frames_done"], max_hours_stop=st["max_hours_stop"],
                         watchdog=wd.reason, min_free_commit_gb=None if wd.min_free is None else round(wd.min_free, 2), last=str(st.get("last"))[:200]))
        if wd.reason == "brake":
            stop = "brake file %s (the chain stopped at a launch boundary)" % rel(BRAKE)
            break
    else:
        stop = stop or "too many loops"
    st = run_state(rd, f_end)
    st.update(stop=stop, resumes_crash=n_crash, resumes_max_hours=n_mh, launches=launched)
    return st, hist


def wait_no_hython(log):
    sys.path.insert(0, T52B3)
    import g52b3_common as GCC
    return GCC.wait_no_hython(log=log)


def hython_env():
    os.makedirs(TMP_HOUDINI, exist_ok=True)
    return dict(os.environ, HOUDINI_TEMP_DIR=TMP_HOUDINI, TEMP=TMP_HOUDINI, TMP=TMP_HOUDINI)


def hython_path():
    sys.path.insert(0, T52B3)
    import g52b3_common as GCC
    return GCC.HY


# ====================================================================== the export cfg (DFG-2B-V's launched cfg + the restart keys)
def C_():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import f55_common as C
    return C


def export_spec(C=None):
    C = C or C_()
    o = C.OPTIONS["C2"]
    b = C.box(o["dp"], o["x0"], o["Lx"], o["W"], o["zb"])
    x1 = b["x0"] + b["Lx"]
    pc = jload(C.DFGBV_READY)["parms"]
    return dict(boxes=dict(xb=dict(x=[o["relax_x"][0] - 2.0, o["relax_x"][1] + 4.0], y=[0.0, float(pc["W"])]),
                           yb=dict(x=[b["x0"], x1], y=[o["relax_y"][0] - 4.0, min(o["relax_y"][1] + 2.0, float(pc["W"]))]),
                           eb=dict(x=[x1 - 17.0, x1 + 2.0], y=[0.0, b["W"] + 2.0])),
                boxes_ckpt_extra=dict(nb=dict(x=[b["x0"] - 2.0, x1 + 2.0], y=[0.0, b["W"] + 2.0])),
                boxes_note=("xb / yb = the frozen cfg text (the two relaxation bands + margins); eb = x 339-358 m, y 0-62 m: the OPTIONAL end "
                            "band's target (end_on, default 0), exported now so switching it on later needs no new parent rerun"),
                boxes_ckpt_note="frame 1056 (the nest's initial state) also carries the WHOLE nest box nb (the reseeding needs the parent's surface "
                                "and velocity everywhere in the box); frames 1057-1657 only the band boxes xb / yb",
                frames=[F0, F_END], frame_ckpt=CKPT, o=[float(pc["ox"]), float(pc["oy"]), float(pc["oz"])], surf_node=NODE_SURF, vel_node=NODE_VEL,
                fields=dict(FIELDS), dtype=dict(s="float32", v="float16"), out_dir=rel(EXPORT_DIR),
                rule=("the parent's own grid (cells 1 m, centres at k + 0.5 m; vel.x / vel.y / vel.z on their own face grids), cropped by index to the "
                      "boxes (plan x, plan y = lateral; full height), never resampled; surface float32, vel float16 [chosen]"))


def source_diff(c0, c):
    def paths(a, b, pre=""):
        if isinstance(a, dict) and isinstance(b, dict):
            out = []
            for k in sorted(set(a) | set(b)):
                p = (pre + "." + k) if pre else k
                if k not in a:
                    out.append(("added", p))
                elif k not in b:
                    out.append(("removed", p))
                else:
                    out += paths(a[k], b[k], p)
            return out
        return [] if canon(a) == canon(b) else [("changed", pre)]
    d = paths(c0, c)
    bad = []
    for kind, p in d:
        top = p.split(".")[0]
        if top in EXPORT_TOP_ALLOWED or (kind == "removed" and p in POP_TOP):
            continue
        if top == "case" and len(p.split(".")) >= 2 and p.split(".")[1] in EXPORT_CASE_ALLOWED:
            continue
        bad.append("%s %s" % (kind, p))
    return dict(ok=not bad, changed=["%s %s" % x for x in d if not x[1].startswith("precheck")], unexpected=bad,
                rule="DFG-2B-V's launched cfg.json canonically equal except %s, the case labels %s and the removed chain-written keys %s"
                     % (sorted(EXPORT_TOP_ALLOWED), sorted(EXPORT_CASE_ALLOWED), list(POP_TOP)))


def export_cfg():
    C = C_()
    rd0 = C.DFGBV_RUN
    c0 = jload(rd0 + "/cfg.json")
    if c0.get("run_id") != DFGBV_RID or (c0.get("dir") or {}).get("set") != "DFGB4" or c0.get("kind") != "3d" or c0.get("restart"):
        raise SystemExit("the export reruns DFG-2B-V (%s) only, not %s" % (DFGBV_RID, c0.get("run_id")))
    sys.path.insert(0, T52)
    import g52_ana as GA52
    off, off_src = GA52.still_offset(rd0)
    c = copy.deepcopy(c0)
    for k in POP_TOP:
        c.pop(k, None)
    spec = export_spec(C)
    c.update(run_id=EXPORT_RID, out_root=C.RUNS_ROOT, f_start=F0, f_first=F0, f_end=F_END, still_offset_m=off)
    c["case"].update(judged=False, role=("FLIP55 C2 parent export: DFG-2B-V recomputed from its own checkpoint v.%04d with the frozen runner and a "
                                         "read-only field export (NOT judged; bit-identical to the judged run is REQUIRED)" % CKPT),
                     restart_of=c0["run_id"], restart_ckpt_frame=CKPT, f55_export=True)
    ck = rd0 + "/ckpt/v.%04d.sim" % CKPT
    c["restart"] = dict(src_run=c0["run_id"], src_dir=rd0, ckpt_frame=CKPT, ckpt_t_s=(CKPT - 1) / FPS, ckpt_file=ck,
                        ckpt_bytes=os.path.getsize(ck) if os.path.exists(ck) else None, still_offset_m=off, still_offset_source=off_src,
                        seed="py -3.10 -B Tools/GWWaveGen/flip55/f55_nest.py export (g49_restart.seed, dirs() replaced in memory)",
                        compare="g49_restart.compare (strict, h52b3_long rule) inside f55_nest.py export")
    c["f55"] = dict(mode="export", option="C2P", export=spec, runner=rel(RUNNER), runner_sha256=RUNNER_SHA, chain=rel(CHAIN), chain_sha256=CHAIN_SHA,
                    hook="hou.setFrame wrapped: fields of frame f (cooked by the runner) exported before frame f + 1; original call unchanged",
                    tool=TOOL_REL)
    c["note"] = ("FLIP55 C2 parent export (f55_nest.py, 2026-10-19): DFG-2B-V %s recomputed from v.%04d (%.3f s) to frame %d with its own launched "
                 "cfg (only the restart keys changed), the frozen g52b3_run.py and a read-only export hook; physics unchanged (bit-identity "
                 "against the judged run checked on every frame)" % (c0["run_id"], CKPT, (CKPT - 1) / FPS, F_END))
    c["precheck"] = precheck_export(c, c0, off)
    return c, c0


def precheck_export(c, c0, off):
    C = C_()
    sys.path.insert(0, T52B3)
    import g52b3_common as GCC
    import g52b3_pcfg as PCF
    pc = PCF.precheck(c)
    ck = pc["checks"]
    replace = {"blocks_equal_DFGBE": "f_start / f_first / f_end are the restart keys of this rerun (1057 / 1057 / 1657); every other block is "
                                     "checked equal to DFG-2B-V's own launched cfg by export_selfcheck_vs_source",
               "out_root_absolute_FLIP52B3": "the rerun writes into Unity/Build/FLIP55/runs (export_out_root_FLIP55); FLIP52B3 is read only"}
    for nm, why in replace.items():
        if nm in ck:
            pc.setdefault("replaced", {})[nm] = dict(value=ck.pop(nm), why=why)
    rd0 = C.DFGBV_RUN
    ckp = rd0 + "/ckpt/v.%04d.sim" % CKPT
    others = [os.path.getsize(p) for p in glob.glob(rd0 + "/ckpt/v.*.sim")]
    import statistics
    ck["export_source_is_DFGBV"] = bool(c0["run_id"] == DFGBV_RID and (c0.get("case") or {}).get("plan_frozen") == GCC.PLAN_REL)
    J = jtry(rd0 + "/g52b3/judge_DFGB4.json") or {}
    ck["export_source_judged_valid"] = bool(J.get("valid") is True and not J.get("failed_gates"))
    ck["export_ckpt_exists_full_size"] = bool(os.path.exists(ckp) and others and os.path.getsize(ckp) >= 0.5 * statistics.median(others))
    ls = open(rd0 + "/chain.log", encoding="utf-8", errors="replace").read().splitlines() if os.path.exists(rd0 + "/chain.log") else []
    ck["export_source_chain_complete"] = bool(chain_segment(ls)["state"] == "complete" and frames_done(rd0) >= int(c0["f_end"]))
    launch = [rd0 + "/cfg.json"] + sorted(glob.glob(rd0 + "/cfg_c*.json"))
    same = [all(canon((jtry(p) or {}).get(k)) == canon(c.get(k)) for k in PHYS_KEYS) for p in launch]
    ck["export_physics_same_as_run_all_launches"] = bool(same and all(same))
    ck["export_hip_same_as_run"] = bool(sha(DFGBV_HIP) == c0.get("hip_sha256") == DFGBV_HIP_SHA)
    m_now, m_run = GCC.module_shas(), c0.get("module_shas_at_chain_start") or {}
    mdiff = {k: [m_run.get(k), m_now.get(k)] for k in sorted(set(m_run) | set(m_now)) if m_now.get(k) != m_run.get(k)}
    ck["export_runtime_modules_same_as_source_chain"] = bool(m_run and not mdiff)
    pl = jtry(C.PLAN) or {}
    fu = pl.get("code_sha256_frozen_used") or {}
    ck["export_runner_chain_frozen"] = bool(sha(RUNNER) == RUNNER_SHA == fu.get("Tools/GWWaveGen/flip52b3/g52b3_run.py")
                                            and sha(CHAIN) == CHAIN_SHA == fu.get("Tools/GWWaveGen/flip52b3/g52b3_chain.py") and sha(G49R) == G49R_SHA)
    ck["export_still_offset_from_run"] = bool(off is not None and float(off) == STILL_OFFSET)
    vdir = rd0 + "/volcorr"
    rows = set()
    for ln in open(vdir + "/state.jsonl", encoding="utf-8"):
        try:
            rows.add(int(json.loads(ln)["f"]))
        except Exception:
            pass
    nT = int(round(float(c0["sf"]["T"]) * FPS))
    ck["export_volcorr_state_ready"] = bool(os.path.exists(vdir + "/ref.json") and os.path.exists(vdir + "/vd_%05d.txt" % CKPT)
                                            and os.path.exists(vdir + "/vd_%05d.txt" % F0) and all(f in rows for f in range(CKPT - nT + 1, CKPT + 1)))
    ck["export_records_equal_source"] = bool(canon(c0["records"]) == canon(c["records"]))
    ck["export_out_root_FLIP55"] = bool(c["out_root"] == C.RUNS_ROOT and under(c["out_root"], B55))
    sd = source_diff(c0, c)
    ck["export_selfcheck_vs_source"] = bool(sd["ok"])
    est_gb = (F_END - CKPT + 1) * 3.0e-3 + 1.6 * (F_END - F0 + 1) / 3001.0 + 13 * 0.2      # export + records + checkpoints [computed]
    free = GCC.free_gb()
    ck["export_disk_ok"] = bool(free - est_gb >= float(c.get("disk_stop_free_gb", 25.0)) + DISK_MARGIN_GB)
    rd = RUNS_ROOT + "/" + EXPORT_RID
    ran = glob.glob(rd + "/run_c*.json") or os.path.exists(rd + "/chain.log")
    if ran:
        old = jtry(rd + "/cfg.json") or {}
        strip = lambda d: {k: v for k, v in d.items() if k not in ("precheck", "hip_sha256", "module_shas_at_chain_start")}
        ck["export_existing_run_is_this_cfg"] = bool(canon(strip(old)) == canon(strip(c)))
    ck["export_no_temp_paths"] = no_temp(c)
    pc["ok"] = bool(all(ck.values()))
    pc["reason"] = None if pc["ok"] else "failed: " + ", ".join(k for k, v in ck.items() if not v)
    pc["export"] = dict(date=now(), source_diff=sd, runtime_modules_changed=mdiff, est_gb=round(est_gb, 2), free_gb=round(free, 1),
                        launches_compared=[os.path.basename(p) for p in launch])
    return pc


def write_cfg_once(c, p):
    """a new file, or KEEP an existing one equal apart from its precheck (a chain may have used it); a different one stops."""
    if os.path.exists(p):
        old = jtry(p) or {}
        if canon({k: v for k, v in old.items() if k != "precheck"}) != canon({k: v for k, v in c.items() if k != "precheck"}):
            raise SystemExit("%s exists with other content: look before replacing it" % p)
        return p, "kept"
    jdump(c, p)
    return p, "written"


# ====================================================================== seed / compare: g49_restart unchanged, its dirs() replaced in memory
def restart_module():
    if T49 not in sys.path:
        sys.path.insert(0, T49)
    if sha(G49R) != G49R_SHA:
        raise SystemExit("g49_restart.py changed (sha %s)" % sha(G49R))
    import g49_restart as RS

    def dirs(c):
        R = c.get("restart") or {}
        if R.get("src_run") != DFGBV_RID:
            raise SystemExit("not a DFG-2B-V restart cfg")
        src = DFGBV_RUN
        dst = os.path.join(RUNS_ROOT, c["run_id"]).replace("\\", "/")
        if not under(dst, B55) or under(dst, B52B3):
            raise SystemExit("the new folder %s is not under Unity/Build/FLIP55" % dst)
        return R, src, dst
    RS.dirs = dirs
    return RS


def strict_compare(c, rc):
    """[computed] the h52b3_long strict rule: g49 compares only the COMMON frames, so every count must also be COMPLETE."""
    f0, f1 = int(c["f_start"]), int(c["f_end"])
    eq = lambda kind, key: [((rc.get(kind) or {}).get(key) or {}).get("n_bit_equal"), ((rc.get(kind) or {}).get(key) or {}).get("n_frames")]
    n = f1 - f0 + 1
    n_src_surf = len([p for p in glob.glob(DFGBV_RUN + "/surf/s_*.gw45s") if f0 <= int(os.path.basename(p)[2:7]) <= f1])
    n_src_r4 = int((rc.get("r4") or {}).get("n_src") or 0)
    s = dict(hf_eta=eq("hf", "eta"), r2_sdf=eq("r2", "sdf"), r2_u=eq("r2", "u"), r2_w=eq("r2", "w"), r3_sdf=eq("r3", "sdf"), r3_u=eq("r3", "u"),
             r3_v=eq("r3", "v"), r3_w=eq("r3", "w"), r4_sdf=eq("r4", "sdf"),
             r5_bytes_equal=[(rc.get("r5") or {}).get("n_bytes_equal"), (rc.get("r5") or {}).get("n_common")],
             volcorr_equal=[(rc.get("volcorr") or {}).get("n_equal"), (rc.get("volcorr") or {}).get("n_common")],
             expected=dict(frames=n, surf=n_src_surf, r4=n_src_r4))
    s["counts_as_expected"] = bool(n > 0 and n_src_surf > 0 and n_src_r4 > 0
                                   and all(s[k] == [n, n] for k in ("hf_eta", "r2_sdf", "r2_u", "r2_w", "r3_sdf", "r3_u", "r3_v", "r3_w", "volcorr_equal"))
                                   and s["r5_bytes_equal"] == [n_src_surf, n_src_surf] and s["r4_sdf"] == [n_src_r4, n_src_r4])
    s["all_bit_identical_g49"] = rc.get("all_bit_identical")
    s["ok"] = bool(rc.get("all_bit_identical") is True and s["counts_as_expected"])
    return s


# ====================================================================== export validation (numpy)
def r1_eta(np, a, y0, dy):
    """the runner's R1 rule on an SDF [lat, up, x]: the top water surface per column (NaN where no water)."""
    ny = a.shape[1]
    neg = a < 0
    has = neg.any(axis=1)
    jtop = ny - 1 - np.argmax(neg[:, ::-1, :], axis=1)
    jtop = np.clip(jtop, 0, ny - 2)
    iz, ix = np.meshgrid(np.arange(a.shape[0]), np.arange(a.shape[2]), indexing="ij")
    vj = a[iz, jtop, ix].astype(np.float64)
    vj1 = a[iz, jtop + 1, ix].astype(np.float64)
    frac = np.where(vj1 - vj > 1e-9, -vj / np.maximum(vj1 - vj, 1e-9), 0.0)
    yc = y0 + dy * np.arange(ny)
    return np.where(has, yc[jtop] + dy * np.clip(frac, 0.0, 1.0), np.nan)


def load_x(np, p):
    with np.load(p, allow_pickle=False) as d:
        meta = json.loads(str(d["meta"]))
        arrs = {k: np.array(d[k]) for k in d.files if k != "meta"}
    return meta, arrs


class HF:
    """hf frames of a run (later launch wins), the generic g52_ana reader."""

    def __init__(self, rd):
        sys.path.insert(0, T52)
        import g52_ana as GA52
        self.B = GA52.Blocks(rd, "hf", "eta")

    def frames(self):
        return self.B.frames()

    def get(self, f):
        return self.B.get(f)


def eta_at(np, e, meta, xq, yq):
    """bilinear value of an hf frame e [lat, x] at plan points (x, y) (arrays)."""
    xs0, dx, ys0, dy = float(meta["x0"]), float(meta["dx"]), float(meta["z0"]), float(meta["dz"])
    fx = (np.asarray(xq, float) - xs0) / dx
    fy = (np.asarray(yq, float) - ys0) / dy
    ix = np.clip(np.floor(fx).astype(int), 0, e.shape[1] - 2)
    iy = np.clip(np.floor(fy).astype(int), 0, e.shape[0] - 2)
    wx = np.clip(fx - ix, 0.0, 1.0)
    wy = np.clip(fy - iy, 0.0, 1.0)
    term = lambda w, v: np.where(w == 0.0, 0.0, w * v)          # a zero-weight neighbour never brings its NaN (dry cell) in
    return (term((1 - wx) * (1 - wy), e[iy, ix]) + term(wx * (1 - wy), e[iy, ix + 1]) + term((1 - wx) * wy, e[iy + 1, ix])
            + term(wx * wy, e[iy + 1, ix + 1]))


def validate_export(log=print, frames=None):
    import numpy as np
    spec = export_spec()
    frames = frames or frames_of(CKPT, F_END)
    H = HF(DFGBV_RUN)
    missing, bad, align, nbytes = [], [], [], 0
    worst = dict(dmax=0.0, frame=None)
    for f in frames:
        p = EXPORT_DIR + "/x_%05d.npz" % f
        if not os.path.exists(p):
            missing.append(f)
            continue
        nbytes += os.path.getsize(p)
        try:
            meta, A = load_x(np, p)
        except Exception as e:
            bad.append("%d unreadable %r" % (f, e))
            continue
        bx = dict(spec["boxes"], **((spec.get("boxes_ckpt_extra") or {}) if f == CKPT else {}))
        need = ["%s_%s" % (b, k) for b in bx for k, _ in FIELDS]
        if sorted(need) != sorted(A) or int(meta.get("frame", -1)) != f:
            bad.append("%d keys %s frame %s" % (f, sorted(A), meta.get("frame")))
            continue
        if not all(np.isfinite(A[k].astype(np.float64)).all() for k in A):
            bad.append("%d non-finite" % f)
            continue
        s = A["xb_s"]
        m = meta["keys"]["xb_s"]
        et = r1_eta(np, s, m["p0"][1], m["d"][1])
        xs = m["p0"][0] + m["d"][0] * np.arange(s.shape[2])
        ys = m["p0"][2] + m["d"][2] * np.arange(s.shape[0])
        e, hm = H.get(f)
        if e is None:
            bad.append("%d no hf record in the judged run" % f)
            continue
        X, Y = np.meshgrid(xs, ys)
        eh = eta_at(np, e, hm, X, Y)
        ok = np.isfinite(et) & np.isfinite(eh)
        dmax = float(np.abs(et[ok] - eh[ok]).max()) if ok.any() else float("inf")
        nan_mis = int((np.isfinite(et) != np.isfinite(eh)).sum())
        neigh = []
        for g in (f - 1, f + 1):
            e2, hm2 = H.get(g)
            if e2 is not None:
                e2i = eta_at(np, e2, hm2, X, Y)
                ok2 = np.isfinite(et) & np.isfinite(e2i)
                neigh.append(float(np.abs(et[ok2] - e2i[ok2]).max()) if ok2.any() else float("inf"))
        row = dict(frame=f, dmax=dmax, nan_mismatch=nan_mis, neighbour_dmax=min(neigh) if neigh else None, n=int(ok.sum()))
        align.append(row)
        if dmax > worst["dmax"]:
            worst = dict(dmax=dmax, frame=f)
    al_ok = bool(align and len(align) == len(frames) - len(missing) - len(bad)
                 and all(r["dmax"] <= 1e-3 and r["nan_mismatch"] == 0 and (r["neighbour_dmax"] is None or r["neighbour_dmax"] > r["dmax"]) for r in align))
    return dict(frames=[frames[0], frames[-1]], n_expected=len(frames), missing=missing[:50], n_missing=len(missing), bad=bad[:20], n_bad=len(bad),
                alignment_ok=al_ok, alignment_worst=worst, alignment_tol_m=1e-3, gb=round(nbytes / 1e9, 3),
                alignment_rule=("top surface recomputed from the exported xb SDF with the runner's R1 rule vs the JUDGED run's hf record of the same "
                                "frame (bilinear at the column centres): max |diff| <= 1e-3 m, no NaN mismatch, and smaller than against frames f +- 1"),
                ok=bool(not missing and not bad and al_ok))


def copy_replay(log=print):
    """the parent's stage-A d(f): vd_<f>.txt of the JUDGED run (what its scene read for the step to frame f), f = 1057 .. 1658, copied; the
    rerun's own files must be byte-identical (a rerun that is bit-identical writes the same d)."""
    os.makedirs(REPLAY_DIR, exist_ok=True)
    rows, diff, miss = 0, [], []
    for f in range(F0, F_END + 2):
        sp = DFGBV_RUN + "/volcorr/vd_%05d.txt" % f
        if not os.path.exists(sp):
            miss.append(f)
            continue
        b = open(sp, "rb").read()
        dp = guard(REPLAY_DIR + "/vd_%05d.txt" % f)
        if not os.path.exists(dp) or open(dp, "rb").read() != b:
            with open(dp, "wb") as fh:
                fh.write(b)
        rows += 1
        rp = EXPORT_RD + "/volcorr/vd_%05d.txt" % f
        if os.path.exists(rp) and open(rp, "rb").read() != b:
            diff.append(f)
    return dict(n=rows, missing=miss, rerun_differs=diff[:20], ok=bool(not miss and not diff), dir=rel(REPLAY_DIR))


# ====================================================================== export (py -3.10)
def cmd_export(sim=False):
    t0 = time.time()
    lines = []

    def log(*a):
        msg = now() + " " + " ".join(str(x) for x in a)
        lines.append(msg)
        print(msg, flush=True)
        if not sim:
            with open(guard(LOG_DIR + "/f55_nest_export.log"), "a", encoding="utf-8") as fh:
                fh.write(msg + "\n")
    done = jtry(EXPORT_JSON) or {}
    if done.get("ok") and not sim:
        v = validate_export(log, frames=[CKPT, (CKPT + F_END) // 2, F_END])
        return final(dict(ok=bool(v["ok"]), step="export", skipped="export.json exists and is ok", export=rel(EXPORT_JSON), spot_check=v))
    c, c0 = export_cfg()
    pc = c["precheck"]
    log("export cfg", EXPORT_RID, "precheck ok", pc["ok"], pc.get("reason") or "")
    src, counts = chain_source()
    compile(src, "patched chain", "exec")
    hy = hython_path()
    plan = [("seed", "g49_restart.seed (v.%04d, volcorr ref.json, vd_%05d, vd_%05d, state rows f <= %d) -> %s" % (CKPT, CKPT, F0, CKPT, rel(EXPORT_RD))),
            ("hyckpt", '"%s" "%s" hyckpt "%s"   (frame %d from a copy of v.%04d in %s)' % (hy, SELF, EXPORT_CFG, CKPT, CKPT, rel(CKPT_LOAD_DIR))),
            ("chain", "py -3.10 -B %s chain export %s  (g52b3_chain.py, replacements %s -> hython %s hyrun <cfg_c*.json> -> g52b3_run.py "
                      "unchanged + hook)" % (SELF, EXPORT_CFG, counts, SELF)),
            ("compare", "g49_restart.compare (strict): frames %d-%d vs %s" % (F0, F_END, rel(DFGBV_RUN))),
            ("validate", "all x_<f>.npz %d-%d, R1 alignment vs the judged hf, vd copy -> %s" % (CKPT, F_END, rel(EXPORT_JSON)))]
    if sim:
        for k, v in plan:
            log("[simulate]", k, v)
        o = dict(ok=bool(pc["ok"]), step="export", simulate=True, precheck=dict(ok=pc["ok"], reason=pc.get("reason"), checks=pc["checks"],
                                                                                 replaced=list((pc.get("replaced") or {}).keys())),
                 source_diff=pc["export"]["source_diff"], chain_replacements=counts, plan=plan, spec=c["f55"]["export"])
        jdump(dict(o, cfg=c), SIM_DIR + "/export_plan.json")
        return final(o)
    if not pc["ok"]:
        return final(dict(ok=False, step="export", why="export cfg precheck: %s" % pc.get("reason")))
    if not chain_alive(EXPORT_RID):
        eg = entry_guard("export", "export", wait_min=WAIT_MIN)
        log("entry guard", "ok" if eg["ok"] else eg["why"])
        if not eg["ok"]:
            return final(dict(ok=False, step="export", why="entry guard: %s" % eg["why"], guard=eg))
    p, how = write_cfg_once(c, EXPORT_CFG)
    log("cfg", rel(p), how)
    rec = dict(date=now(), tool=TOOL_REL, tool_sha256=sha(SELF), cfg=rel(p), cfg_sha256=sha(p), run=rel(EXPORT_RD), spec=c["f55"]["export"])
    # 1. seed
    RS = restart_module()
    if not (glob.glob(EXPORT_RD + "/run_c*.json") or os.path.exists(EXPORT_RD + "/chain.log")):
        sd = RS.seed(p)
        ok_seed = all(v.get("dst_sha256") in (v.get("src_sha256"), v.get("src_sha256_of_rows")) for v in sd["files"].values())
        rec["seed"] = dict(ok=ok_seed, files={k: {kk: v.get(kk) for kk in ("bytes", "rows", "frames")} for k, v in sd["files"].items()})
        log("seed ok", ok_seed)
        if not ok_seed:
            return final(dict(ok=False, step="export", why="seed sha mismatch", seed=rec["seed"]))
    else:
        rec["seed"] = dict(ok=True, skipped="the folder already holds this cfg's chain")
    # 2. frame 1056 from the checkpoint copy (separate hython; before the chain writes checkpoints)
    x0p = EXPORT_DIR + "/x_%05d.npz" % CKPT
    if not os.path.exists(x0p):
        os.makedirs(CKPT_LOAD_DIR, exist_ok=True)
        cp = CKPT_LOAD_DIR + "/v.%04d.sim" % CKPT
        srcck = DFGBV_RUN + "/ckpt/v.%04d.sim" % CKPT
        if sha(cp) != sha(srcck):
            shutil.copyfile(srcck, guard(cp))
        wait_no_hython(log)
        log("hyckpt: frame %d from %s" % (CKPT, rel(cp)))
        try:
            with open(guard(LOG_DIR + "/f55_nest_hyckpt.txt"), "a", encoding="utf-8") as lf:
                r = subprocess.run([hy, SELF, "hyckpt", p], cwd=REPO, env=hython_env(), stdin=subprocess.DEVNULL, timeout=HYCKPT_TIMEOUT_S,
                                   stdout=lf, stderr=subprocess.STDOUT)
            rc_h = r.returncode
        except subprocess.TimeoutExpired:
            rc_h = "timeout %.0f s (the DOP was cooking from frame 1, not loading v.%04d)" % (HYCKPT_TIMEOUT_S, CKPT)
        rec["hyckpt"] = dict(rc=rc_h, record=jtry(EXPORT_DIR + "/hyckpt_%05d.json" % CKPT))
        # frame 1056 must equal the judged run's frame 1056 (R1 alignment) BEFORE the 0.6 h rerun; a bad file is removed so a later
        # 'export' retries instead of failing on it forever (code review M1)
        v0 = validate_export(log, frames=[CKPT]) if os.path.exists(x0p) else dict(ok=False, why="no x_%05d.npz" % CKPT)
        rec["hyckpt"]["validation"] = v0
        if rc_h != 0 or not v0.get("ok"):
            if os.path.exists(x0p):
                os.remove(guard(x0p))
            return final(dict(ok=False, step="export", why="hyckpt failed (rc %s, frame-%d validation %s); x_%05d.npz removed" % (
                rc_h, CKPT, v0.get("ok"), CKPT), hyckpt=rec["hyckpt"]))
    else:
        rec["hyckpt"] = dict(skipped="x_%05d.npz exists" % CKPT, record=jtry(EXPORT_DIR + "/hyckpt_%05d.json" % CKPT),
                             validation=validate_export(log, frames=[CKPT]))
        if not rec["hyckpt"]["validation"].get("ok"):
            os.remove(guard(x0p))
            return final(dict(ok=False, step="export", why="the existing x_%05d.npz does not match the judged run's frame %d (removed; rerun "
                                                           "export)" % (CKPT, CKPT), hyckpt=rec["hyckpt"]))
    # 3. the rerun with the hook
    st, hist = drive_chain("export", p, EXPORT_RID, F_END, log, "export")
    rec["chain"] = dict(state=st, history=hist)
    if not st["complete"]:
        return final(dict(ok=False, step="export", why="the rerun did not reach frame %d (%s; %s)" % (F_END, st["state"], st.get("stop")),
                          chain=rec["chain"]))
    # 4. bit-identity (strict)
    rc = RS.compare(p)
    s = strict_compare(c, rc)
    rec["compare"] = s
    log("compare strict ok", s["ok"], json.dumps({k: s[k] for k in ("hf_eta", "r2_sdf", "r4_sdf", "r5_bytes_equal", "volcorr_equal")}))
    # 5. export files, alignment, replay files
    v = validate_export(log)
    rec["validation"] = v
    rp = copy_replay(log)
    rec["replay"] = rp
    hooks = [jtry(q) for q in sorted(glob.glob(EXPORT_DIR + "/hook_c*.json"))]
    rec["hooks"] = [dict((k, h.get(k)) for k in ("n", "errors", "export_s", "setframe_calls")) for h in hooks if h]
    rec["ok"] = bool(s["ok"] and v["ok"] and rp["ok"] and not any((h or {}).get("errors") for h in hooks))
    rec["seconds"] = round(time.time() - t0, 1)
    rec["tags"] = dict(compare="measured (record to record)", alignment="measured", sizes="measured")
    jdump(rec, EXPORT_JSON)
    return final(dict(ok=rec["ok"], step="export", export=rel(EXPORT_JSON), compare_ok=s["ok"], validation_ok=v["ok"], replay_ok=rp["ok"],
                      gb=v.get("gb"), seconds=rec["seconds"]))


# ====================================================================== F7: the parent's own frame-1056 particles (py -3.10 + hython 'hypart')
def union_sampler(np, U, key):
    """clamped trilinear on an f55_union field (= volumesample on the padded OUT_TARGET volume)."""
    S, p0, d = U[key]

    def tri(x, y, z):
        fx = (np.asarray(x, float) - p0[0]) / d[0]; fy = (np.asarray(y, float) - p0[1]) / d[1]; fz = (np.asarray(z, float) - p0[2]) / d[2]
        i = np.clip(np.floor(fx).astype(int), 0, S.shape[2] - 2); j = np.clip(np.floor(fy).astype(int), 0, S.shape[1] - 2)
        k = np.clip(np.floor(fz).astype(int), 0, S.shape[0] - 2)
        wx, wy, wz = np.clip(fx - i, 0, 1), np.clip(fy - j, 0, 1), np.clip(fz - k, 0, 1)
        c = 0.0
        for dk in (0, 1):
            for dj in (0, 1):
                for di in (0, 1):
                    c = c + S[k + dk, j + dj, i + di] * (wx if di else 1 - wx) * (wy if dj else 1 - wy) * (wz if dk else 1 - wz)
        return c
    return tri


def validate_pinit(np, p_path=PINIT_NPZ, hy=None, x_path=None, v_box=None, n_total_expect=None, box=None):
    """the particle file against the parent's own frame-1056 records: finite, all inside the C2ID box, the counts of the hython record, the
    total = the hyckpt record's particle count (same checkpoint), density (particles / m3 of the parent's hf column volume in the box),
    the fraction above the parent's SDF zero and |v - the parent's grid velocity| (sanity bounds PINIT_RULES [chosen])."""
    XB = xb_mod()
    nsp = {}
    exec(compile(XB.PINIT_PURE, "PINIT_PURE", "exec"), nsp)
    out = dict(file=rel(p_path), sha256=sha(p_path), rules=PINIT_RULES)
    if not os.path.exists(p_path):
        return dict(out, ok=False, why="no %s" % rel(p_path))
    box = box or pinit_box()
    with np.load(p_path, allow_pickle=False) as d:
        Ph = np.array(d["P_h"], np.float32); V = np.array(d["v"], np.float32); meta = json.loads(str(d["meta"]))
    o = np.array(meta["o_parent"], np.float64)
    pl = Ph.astype(np.float64) - o
    inb = (pl[:, 0] >= box["x0"]) & (pl[:, 0] <= box["x0"] + box["Lx"]) & (pl[:, 2] >= 0.0) & (pl[:, 2] <= box["W"])
    ck = {}
    ck["n_positive"] = bool(len(Ph) > 0)
    ck["finite"] = bool(np.isfinite(Ph).all() and np.isfinite(V).all())
    ck["all_in_box"] = bool(inb.all())
    ck["meta_count"] = bool(int(meta.get("n_box", -1)) == len(Ph))
    if hy is not None:
        ck["hython_record"] = bool(not hy.get("error") and int(hy.get("n_box", -1)) == len(Ph) and hy.get("sha256") == out["sha256"])
        # the checkpoint copy stayed the hyckpt source while hypart read it (code review M6)
        ck["ckpt_copy_unchanged"] = bool(hy.get("ckpt_sha256") and hy.get("ckpt_sha256_after") == hy.get("ckpt_sha256"))
    if n_total_expect is not None:
        ck["total_as_checkpoint"] = bool(int(meta.get("n_total", -1)) == int(n_total_expect))
    if v_box is None:
        C = C_()
        e, m = HF(DFGBV_RUN).get(CKPT)
        v_box, _, _ = column_volume(np, e, m, C.bed_z)
    dens = len(Ph) / float(v_box) if v_box else None
    out.update(n=int(len(Ph)), n_total=meta.get("n_total"), v_box_m3=v_box, density_per_m3=dens)
    ck["density"] = bool(dens is not None and PINIT_RULES["density_range"][0] <= dens <= PINIT_RULES["density_range"][1])
    x_path = x_path or (EXPORT_DIR + "/x_%05d.npz" % CKPT)
    try:
        C = C_()
        mx, A = load_x(np, x_path)
        ns = {}
        exec(compile(XB.TARGET_PURE, "TARGET_PURE", "exec"), ns)
        U = ns["f55_union"](mx, A, float(box["W"]) + 2.0, C.bed_z)
        sel = np.arange(0, len(pl), max(1, len(pl) // 200000))
        q = pl[sel]
        s = union_sampler(np, U, "s")(q[:, 0], q[:, 1], q[:, 2])
        above = float(np.mean(s > 0.0))
        vg = np.stack([union_sampler(np, U, k)(q[:, 0], q[:, 1], q[:, 2]) for k in ("vx", "vy", "vz")], 1)
        dv = np.linalg.norm(V[sel].astype(np.float64) - vg, axis=1)
        # the top particle of every parent cell column vs the parent's own top surface (R1 of the same frame's SDF): about -(s_off + up to
        # dp) for the parent's particles; a vertical frame / offset error moves it by its size
        E, pe, de = U["eta"]
        ix = np.rint((pl[:, 0] - pe[0]) / de[0]).astype(int); iz = np.rint((pl[:, 2] - pe[2]) / de[2]).astype(int)
        okc = (ix >= 0) & (ix < E.shape[1]) & (iz >= 0) & (iz < E.shape[0])
        cid = iz[okc] * E.shape[1] + ix[okc]
        top = np.full(E.size, -np.inf)
        np.maximum.at(top, cid, pl[okc, 1])
        cnt = np.bincount(cid, minlength=E.size)
        ef = E.reshape(-1).astype(np.float64)
        use = (cnt >= 4) & np.isfinite(ef) & np.isfinite(top)
        dtop = top[use] - ef[use]
        out.update(above_sdf_zero_frac=above, above_particle_level_frac=float(np.mean(s + STILL_OFFSET > 0.0)), mean_abs_dv_grid=float(dv.mean()),
                   p99_abs_dv_grid=float(np.percentile(dv, 99)), mean_speed=float(np.linalg.norm(V[sel], axis=1).mean()), n_sampled=int(len(sel)),
                   top_minus_eta_median_m=float(np.median(dtop)) if len(dtop) else None,
                   top_minus_eta_p10_p90_m=[float(np.percentile(dtop, 10)), float(np.percentile(dtop, 90))] if len(dtop) else None,
                   top_cells=int(use.sum()))
        lo, hi = PINIT_RULES["top_minus_eta_median_range"]
        ck["top_particle_vs_parent_surface"] = bool(len(dtop) > 0 and lo <= float(np.median(dtop)) <= hi)
        ck["level_vs_parent_sdf"] = bool(above <= PINIT_RULES["above_sdf_frac_max"])
        ck["velocity_vs_parent_grid"] = bool(dv.mean() <= PINIT_RULES["mean_dv_grid_max"])
    except Exception as e:
        out["sample_error"] = repr(e)[:300]
        ck["top_particle_vs_parent_surface"] = False
        ck["level_vs_parent_sdf"] = False
        ck["velocity_vs_parent_grid"] = False
    out["checks"] = ck
    out["ok"] = bool(all(ck.values()))
    return out


def pinit_state():
    """ok iff pinit_01056.json is ok and the particle file on disk is the one it validated."""
    r = jtry(PINIT_JSON) or {}
    why = []
    if not r.get("ok"):
        why.append("%s missing or not ok" % rel(PINIT_JSON))
    elif r.get("sha256") != sha(PINIT_NPZ):
        why.append("%s changed after its validation" % rel(PINIT_NPZ))
    return dict(ok=not why, why="; ".join(why) or None, file=rel(PINIT_NPZ), sha256=sha(PINIT_NPZ) if os.path.exists(PINIT_NPZ) else None,
                n=r.get("n"), density_per_m3=r.get("density_per_m3"))


def pinit_core(sim=False):
    """the parent's frame-1056 particles in the C2ID box (F7) -> p_01056.npz + pinit_01056.json; returns its record (cmd_pinit prints it,
    'run C2ID' calls it first when the particles are missing)."""
    import numpy as np
    st = pinit_state()
    if st["ok"] and not sim:
        return (dict(ok=True, step="pinit", skipped="pinit_01056.json exists, ok, file unchanged", file=st["file"], n=st["n"],
                          density_per_m3=st["density_per_m3"]))
    hy = hython_path()
    cmd = [hy, SELF, "hypart", EXPORT_CFG]
    ex = jtry(EXPORT_JSON) or {}
    cp = CKPT_LOAD_DIR + "/v.%04d.sim" % CKPT
    pre = dict(export_ok=bool(ex.get("ok")), export_cfg=os.path.exists(EXPORT_CFG), ckpt_copy=os.path.exists(cp),
               ckpt_copy_is_source=bool(os.path.exists(cp) and sha(cp) == ((jtry(EXPORT_DIR + "/hyckpt_%05d.json" % CKPT) or {}).get("ckpt_sha256"))))
    if sim:
        return (dict(ok=bool(all(pre.values())), step="pinit", simulate=True, pre=pre, would_run=" ".join(cmd), writes=[rel(PINIT_NPZ), rel(HYPART_JSON),
                                                                                                                     rel(PINIT_JSON)], box=pinit_box()))
    if not all(pre.values()):
        return (dict(ok=False, step="pinit", why="preconditions: %s" % ", ".join(k for k, v in pre.items() if not v), pre=pre))
    eg = entry_guard("pinit", "pinit", wait_min=WAIT_MIN)
    if not eg["ok"]:
        return (dict(ok=False, step="pinit", why="entry guard: %s" % eg["why"], guard=eg))
    wait_no_hython(lambda *a: print(now(), *a, flush=True))
    try:
        with open(guard(LOG_DIR + "/f55_nest_hypart.txt"), "a", encoding="utf-8") as lf:
            lf.write("\n=== %s %s\n" % (now(), " ".join(cmd)))
            lf.flush()
            r = subprocess.run(cmd, cwd=REPO, env=hython_env(), stdin=subprocess.DEVNULL, timeout=HYCKPT_TIMEOUT_S, stdout=lf, stderr=subprocess.STDOUT)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "timeout %.0f s" % HYCKPT_TIMEOUT_S
    hyr = jtry(HYPART_JSON) or {}
    hk = jtry(EXPORT_DIR + "/hyckpt_%05d.json" % CKPT) or {}
    v = validate_pinit(np, PINIT_NPZ, hy=hyr, n_total_expect=hk.get("particles"))
    rec = dict(date=now(), tool=TOOL_REL, tool_sha256=sha(SELF), rc=rc, hython=hyr, **v)
    rec["ok"] = bool(rc == 0 and v["ok"])
    rec["tags"] = dict(counts="measured", density="measured (particles / hf column volume)", bounds="chosen")
    jdump(rec, PINIT_JSON)
    return (dict(ok=rec["ok"], step="pinit", file=rel(PINIT_NPZ), json=rel(PINIT_JSON), rc=rc, n=v.get("n"), n_total=v.get("n_total"),
                      density_per_m3=v.get("density_per_m3"), above_sdf_zero_frac=v.get("above_sdf_zero_frac"),
                      above_particle_level_frac=v.get("above_particle_level_frac"), top_minus_eta_median_m=v.get("top_minus_eta_median_m"),
                      mean_abs_dv_grid=v.get("mean_abs_dv_grid"), checks=v.get("checks")))


def cmd_pinit(sim=False):
    """py -3.10 -B f55_nest.py pinit (prints ONE json line)."""
    return final(pinit_core(sim))


def xb_mod():
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    import x55_nest_build as XB
    return XB


# ====================================================================== C2: the still-water calibration of the level step (py -3.10 + hython)
def calib_analyse(np, eta_files, s_ref=STILL_OFFSET, frames_expected=None):
    """CALIB_RULE_TEXT on the nest's per-frame R1 surfaces (eta_files {frame: npz path with eta [lat, x] and meta x0 / dx / z0 / dz}).
    step_m = the rise after creation (mean L of the last 12 frames - L(first frame)); C2's reading offset at creation (L(first) - s_ref)
    and the level vs the parent's hf level (last - s_ref) are reported, not subtracted (code review B1 / physics review M5)."""
    reg, inn, n_last = CALIB_RULES["region"], CALIB_RULES["interior"], CALIB_RULES["last_n"]
    fr = sorted(int(f) for f in eta_files)
    rows, bins, bins0 = [], {}, {}
    for f in fr:
        with np.load(eta_files[f] if f in eta_files else eta_files[str(f)]) as dd:
            e = np.array(dd["eta"], np.float64); m = json.loads(str(dd["meta"]))
        xs = float(m["x0"]) + float(m["dx"]) * np.arange(e.shape[1]); ys = float(m["z0"]) + float(m["dz"]) * np.arange(e.shape[0])

        def mean_in(rg):
            sx = (xs >= rg["x"][0]) & (xs <= rg["x"][1]); sy = (ys >= rg["y"][0]) & (ys <= rg["y"][1])
            a = e[np.ix_(sy, sx)]
            return float(np.nanmean(a)) if np.isfinite(a).any() else float("nan"), int(np.isfinite(a).sum())
        L, nL = mean_in(reg)
        Li, nLi = mean_in(inn)
        rows.append(dict(frame=f, level_m=L, n=nL, level_interior_m=Li))
        if f == fr[0] or f in fr[-n_last:]:
            for x0 in range(int(inn["x"][0]), int(inn["x"][1]), 20):
                v_ = mean_in(dict(x=(x0, x0 + 20.0), y=inn["y"]))[0]
                if f == fr[0]:
                    bins0[x0] = v_
                if f in fr[-n_last:]:
                    bins.setdefault(x0, []).append(v_)
    out = dict(rule=CALIB_RULE_TEXT, s_ref_m=s_ref, frames=[fr[0], fr[-1]] if fr else None, n_frames=len(fr), rows=rows)
    lv = np.array([r["level_m"] for r in rows], float)
    if len(lv) < n_last or not np.isfinite(lv).all():
        return dict(out, ok=False, why="fewer than %d frames or a non-finite level" % n_last)
    last = lv[-n_last:]
    step = float(last.mean() - lv[0])
    settle = float(last.max() - last.min())
    li = np.array([r["level_interior_m"] for r in rows], float)
    n24 = min(24, len(lv))
    tt = (np.array(fr[-n24:], float) - fr[-n24]) / FPS
    slope = float(np.polyfit(tt, lv[-n24:], 1)[0]) if n24 >= 3 else None
    out.update(step_m=step, settle_m=settle, level_creation_m=float(lv[0]), offset_at_creation_m=float(lv[0] - s_ref),
               step_vs_parent_hf_m=float(last.mean() - s_ref), step_interior_m=float(np.nanmean(li[-n_last:]) - li[0]),
               slope_last24_m_per_s=slope,
               step_per_20m_x={str(k): float(np.nanmean(v) - bins0.get(k, float("nan"))) for k, v in sorted(bins.items())},
               reading_note=("step_m (the rise after creation) is what C2 subtracts (init_lvl_m); offset_at_creation_m = C2's dp 0.25 reading "
                             "offset vs the parent's 0.076 m (a reading bias, reported with any Hc comparison, not a level change); "
                             "slope_last24_m_per_s and step_per_20m_x (each 20 m bin's rise vs its own creation level) reported only"))
    ck = dict(frames_complete=bool(frames_expected is None or len(fr) == frames_expected), step_bounded=bool(abs(step) <= CALIB_RULES["step_abs_max_m"]),
              settled=bool(settle <= CALIB_RULES["settle_max_m"]))
    out["checks"] = ck
    out["ok"] = bool(all(ck.values()))
    return out


def calib_state():
    """ok iff calib55_C2.json is ok and was made with THIS nest hip, THESE tools and THIS build check (the C2 launch uses its step)."""
    r = jtry(CALIB_JSON) or {}
    why = []
    if not r.get("ok"):
        why.append("%s missing or not ok" % rel(CALIB_JSON))
    else:
        if r.get("hip_sha256") != sha(NEST_HIP):
            why.append("the nest scene changed after the calibration")
        if r.get("build_check_sha256") != sha(NEST_BUILD_CHECK):
            why.append("the build check changed after the calibration")
        if r.get("tool_sha256") != {p: sha(REPO + "/" + p) for p in C_().NEST_TOOLS}:
            why.append("the nest tools changed after the calibration")
    return dict(ok=not why, why="; ".join(why) or None, step_m=r.get("lvl_step_m") if not why else None, file=rel(CALIB_JSON),
                sha256=sha(CALIB_JSON) if os.path.exists(CALIB_JSON) else None)


def calib_cfg(C=None):
    """the calibration's hython cfg: C2's launch parms with the still synthetic parent as the target, no replay, the lattice unshifted."""
    C = C or C_()
    L, _ = launch_cfg("C2", for_smoke=True)
    parms = dict(L["parms"])
    parms.update(tgt_dir=CALIB_TGT, rep_dir="", rep_on=0.0, init_src=0.0, init_lvl_m=0.0, pinit_npz="")
    return dict(kind="F55 C2 still-water calibration of the level step (x55_nest_build.py --hython-calib)", option="C2", parms=parms,
                solver=L.get("solver"), frames=[CKPT, CKPT + CALIB_FRAMES], out_dir=CALIB_DIR, hip_sha256=sha(NEST_HIP),
                build_check_sha256=sha(NEST_BUILD_CHECK), tool_sha256={p: sha(REPO + "/" + p) for p in C.NEST_TOOLS}, s_ref_m=STILL_OFFSET,
                rule=CALIB_RULE_TEXT, date=now())


def calib_core(sim=False, log=print):
    """the calibration (returns its record; cmd_calib prints it). Needs the CHECKED scene (build check all_ok + smoke_ok for this hip and these
    tools) and the registered tools (AM-F55-NEST with these sha256)."""
    import numpy as np
    C = C_()
    XB = xb_mod()
    bc = jtry(NEST_BUILD_CHECK) or {}
    cur = {p: sha(REPO + "/" + p) for p in C.NEST_TOOLS}
    pre = dict(build_check_ok=bool(bc.get("all_ok") and bc.get("smoke_ok")), hip_as_build_check=bool(bc.get("hip_sha256") == sha(NEST_HIP)),
               tools_as_build_check=bool((bc.get("tool_sha256") or {}) == cur), tools_registered=bool(C.nest_tools_state().get("ok")))
    cfg = calib_cfg(C)
    cmd = [hython_path(), BUILD_TOOL, "--hython-calib", CALIB_DIR + "/calib_cfg.json"]
    if sim:
        return dict(ok=True, step="calib", simulate=True, pre=pre, would_run=" ".join(cmd), cfg=cfg, rule=CALIB_RULE_TEXT,
                    note="pre items become true after x55_nest_build.py --smoke and amend --write")
    if not all(pre.values()):
        return dict(ok=False, step="calib", why="preconditions: %s" % ", ".join(k for k, v in pre.items() if not v), pre=pre)
    eg = entry_guard("calib C2", "calib", wait_min=WAIT_MIN)
    if not eg["ok"]:
        return dict(ok=False, step="calib", why="entry guard: %s" % eg["why"], guard=eg)
    guard(CALIB_DIR + "/x")
    for p in glob.glob(CALIB_DIR + "/eta/eta_*.npz") + glob.glob(CALIB_TGT + "/x_*.npz") + [CALIB_DIR + "/calib_raw.json"]:
        if os.path.exists(p):
            os.remove(guard(p))
    XB.write_synth_export(CALIB_TGT, frames=tuple(range(CKPT, CKPT + CALIB_FRAMES + 2)), full_at=CKPT,
                          fields_fn=lambda f: XB.still_fields(STILL_OFFSET))
    jdump(cfg, CALIB_DIR + "/calib_cfg.json")
    wait_no_hython(log)
    t0 = time.time()
    try:
        with open(guard(LOG_DIR + "/f55_nest_calib.txt"), "a", encoding="utf-8") as lf:
            lf.write("\n=== %s %s\n" % (now(), " ".join(cmd)))
            lf.flush()
            r = subprocess.run(cmd, cwd=REPO, env=hython_env(), stdin=subprocess.DEVNULL, timeout=CALIB_TIMEOUT_S, stdout=lf, stderr=subprocess.STDOUT)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = "timeout %.0f s" % CALIB_TIMEOUT_S
    raw = jtry(CALIB_DIR + "/calib_raw.json") or {}
    an = calib_analyse(np, {int(k): v for k, v in (raw.get("eta_files") or {}).items()}, STILL_OFFSET, frames_expected=CALIB_FRAMES + 1)
    rec = dict(date=now(), tool=TOOL_REL, kind="F55 C2 still-water calibration of the level step", rc=rc, seconds=round(time.time() - t0, 1),
               cfg=rel(CALIB_DIR + "/calib_cfg.json"), cfg_sha256=sha(CALIB_DIR + "/calib_cfg.json"), hip_sha256=cfg["hip_sha256"],
               build_check_sha256=cfg["build_check_sha256"], tool_sha256=cfg["tool_sha256"], raw_ok=raw.get("ok"), raw_error=raw.get("error"),
               frames_raw=[{k: r_.get(k) for k in ("frame", "particles", "ss_n", "band_tgt", "band_cand", "band_added", "band_kills",
                                                   "band_kills_np", "finite")}
                           for r_ in (raw.get("frames") or [])], analysis=an, lvl_step_m=an.get("step_m"),
               tags=dict(level_step="measured (the nest's R1 surface level: last 12 frames vs its creation frame)",
                         offset_at_creation="measured (the nest's creation level vs the still parent's hf level 0.076 m), reported only",
                         bounds="chosen"))
    rec["ok"] = bool(rc == 0 and raw.get("ok") and an.get("ok"))
    jdump(rec, CALIB_JSON)
    return dict(ok=rec["ok"], step="calib", option="C2", file=rel(CALIB_JSON), lvl_step_m=rec["lvl_step_m"], settle_m=an.get("settle_m"),
                offset_at_creation_m=an.get("offset_at_creation_m"), step_vs_parent_hf_m=an.get("step_vs_parent_hf_m"),
                slope_last24_m_per_s=an.get("slope_last24_m_per_s"), checks=an.get("checks"), rc=rc, seconds=rec["seconds"])


def cmd_calib(option="C2", sim=False):
    if option != "C2":
        return final(dict(ok=False, step="calib", why="calib C2 (C2ID starts from the parent's particles: no calibration)"))
    return final(calib_core(sim))


# ====================================================================== the launch cfg of a nest run (frozen design cfg + DERIVED_KEYS)
def launch_cfg(option, for_smoke=False):
    C = C_()
    import f55_pcfg as PC
    d = PC.make(option, "g1")
    pl = jtry(C.PLAN) or {}
    frozen16 = (((pl.get("options") or {}).get(option) or {}).get("stages") or {}).get("g1", {}).get("cfg_sha16")
    sha16 = PC.sha16({k: v for k, v in d.items() if k not in ("precheck", "f55")})
    parent = jload(C.DFGBV_READY)
    L = copy.deepcopy(d)
    L["parms"].update(LAUNCH_PARMS)
    L["parms"].update(LAUNCH_STR_PARMS)
    L["parms"].update(OVERRIDE_PARMS)
    # F7 / C2 calibration: the per-option initial state (C2ID: the parent's particles; C2: the lattice minus the calibrated level step)
    op = dict(OPTION_PARMS[option])
    cs = calib_state() if option == "C2" else None
    pst = pinit_state() if option == "C2ID" else None
    if op.get("init_lvl_m") is None:
        op["init_lvl_m"] = float(cs["step_m"]) if (cs and cs["ok"] and cs.get("step_m") is not None) else 0.0
    L["parms"].update(op)
    L["parms"].update(OPTION_STR_PARMS[option])
    L["dir"] = dict(copy.deepcopy(parent["dir"]), parent_only=True, note=d["dir"].get("note"),
                    nest_note="DFG-2B-V's table block for the frozen runner's OUT_DIRTAB check only; dir_on 0: never read by the nest")
    L["still_offset_m"] = STILL_OFFSET
    bc = jtry(NEST_BUILD_CHECK) or {}
    ex = jtry(EXPORT_JSON) or {}
    ns = C.nest_tools_state()
    L["f55"] = dict(mode="nest", option=option, stage="g1", design_cfg=rel(PC.cfg_path(option, "g1")), design_cfg_sha16=sha16, frozen_cfg_sha16=frozen16,
                    derived_keys=list(DERIVED_KEYS), derived_why=DERIVED_WHY, overrides={k: dict(design=OVERRIDE_FROM[k], launch=v) for k, v in
                                                                                       OVERRIDE_PARMS.items()},
                    case_note=("case.runnable false / the design note 'NOT runnable' are inherited from the design cfg (its sha16 must stay the "
                               "plan's); f55.mode 'nest' and this launch precheck make the launch"),
                    nest_hip=rel(NEST_HIP), nest_hip_sha256=sha(NEST_HIP), x55_sha256=sha(BUILD_TOOL),
                    build_check=rel(NEST_BUILD_CHECK), build_check_sha256=sha(NEST_BUILD_CHECK), export=rel(EXPORT_JSON),
                    export_sha256=sha(EXPORT_JSON), nest_tools=ns, cost=d["f55"].get("cost"), tool=TOOL_REL, tool_sha256=sha(SELF),
                    init=dict(init_src=L["parms"]["init_src"], init_lvl_m=L["parms"]["init_lvl_m"], pinit=pst, calib=cs,
                              rule=("C2ID: the parent's own frame-1056 particles in the box (f55_nest.py pinit)" if option == "C2ID" else
                                    "C2: the lattice and the band water rule at the parent's particle level minus the calibrated level step "
                                    "(f55_nest.py calib C2: "
                                    + CALIB_RULE_TEXT + ")")))
    ck = {}
    ck["design_precheck_ok"] = bool(d["precheck"]["ok"])
    ck["design_cfg_sha16_as_frozen"] = bool(frozen16 is not None and sha16 == frozen16)
    ck["plan_sha_ok"] = bool(C.plan_sha_ok())
    strip = {k: v for k, v in L.items() if k not in ("precheck", "f55", "dir", "still_offset_m")}
    strip["parms"] = {k: v for k, v in L["parms"].items() if k not in LAUNCH_PARMS and k not in LAUNCH_STR_PARMS and k not in OVERRIDE_PARMS}
    dstrip = {k: v for k, v in d.items() if k not in ("precheck", "f55", "dir", "still_offset_m")}
    dstrip["parms"] = {k: v for k, v in d["parms"].items() if k not in OVERRIDE_PARMS}
    ck["only_derived_keys_differ"] = bool(canon(strip) == canon(dstrip) and "still_offset_m" not in d
                                          and not (set(LAUNCH_PARMS) | set(LAUNCH_STR_PARMS)) & set(d["parms"]))
    ck["overrides_as_registered"] = bool(all(float(d["parms"].get(k, float("nan"))) == float(OVERRIDE_FROM[k]) and float(L["parms"][k]) == float(v)
                                             for k, v in OVERRIDE_PARMS.items()))
    ck["dir_on_off"] = bool(float(L["parms"]["dir_on"]) == 0.0 and float(L["parms"]["volcorr_on"]) == 0.0)
    ck["parent_table_file"] = bool(os.path.exists(L["dir"].get("npz") or "") and sha(L["dir"]["npz"]) == L["dir"].get("npz_sha256"))
    ck["export_ok"] = bool(ex.get("ok") and os.path.isdir(EXPORT_DIR) and os.path.isdir(REPLAY_DIR))
    ck["build_check_all_ok"] = bool(bc.get("all_ok") and bc.get("smoke_ok"))
    ck["hip_sha_as_build_check"] = bool(sha(NEST_HIP) is not None and bc.get("hip_sha256") == sha(NEST_HIP))
    ck["nest_tools_registered"] = bool(ns.get("ok"))
    ck["out_root_FLIP55"] = bool(under(L["out_root"], B55))
    ck["no_temp_paths"] = no_temp(L)
    ck["init_as_registered"] = bool(float(L["parms"]["band_lin"]) == 1.0 and float(L["parms"]["init_src"]) == float(OPTION_PARMS[option]["init_src"])
                                    and L["parms"]["pinit_npz"] == OPTION_STR_PARMS[option]["pinit_npz"])
    if option == "C2ID":
        ck["pinit_ok"] = bool(pst and pst["ok"])
    else:
        ck["calib_ok"] = bool(cs and cs["ok"] and abs(float(L["parms"]["init_lvl_m"]) - float(cs["step_m"])) < 1e-12)
    if for_smoke:
        for k in ("export_ok", "build_check_all_ok", "hip_sha_as_build_check", "nest_tools_registered", "pinit_ok", "calib_ok"):
            ck.pop(k, None)
    L["precheck"] = dict(ok=bool(all(ck.values())), checks=ck, reason=None if all(ck.values()) else "failed: " + ", ".join(k for k, v in ck.items() if not v),
                         design_precheck=dict(ok=d["precheck"]["ok"], reason=d["precheck"].get("reason"), checks=d["precheck"]["checks"]),
                         kind="F55 nest launch precheck (design cfg + DERIVED_KEYS)", date=now())
    return L, d


def launch_path(option):
    C = C_()
    return READY + "/%s__g1_launch.json" % C.RID[option]


def cmd_run(option, sim=False):
    C = C_()
    if option not in ("C2", "C2ID"):
        raise SystemExit("run C2ID | C2")
    L, d = launch_cfg(option)
    pc = L["precheck"]
    rid = C.RID[option]
    rd = RUNS_ROOT + "/" + rid
    if sim:
        o = dict(ok=bool(pc["checks"]["design_precheck_ok"] and pc["checks"]["design_cfg_sha16_as_frozen"] and pc["checks"]["only_derived_keys_differ"]
                         and pc["checks"]["overrides_as_registered"]),
                 step="run", option=option, simulate=True, precheck=pc, run_dir=rel(rd), launch_cfg=rel(launch_path(option)),
                 c2_tied_to_c2id=c2_tied_to_c2id(C) if option == "C2" else None, slot_need_gb=need_of(option),
                 would_run="py -3.10 -B %s chain nest %s (patched g52b3_chain.py; hython %s hyrun -> g52b3_run.py with HIP = %s)" % (
                     SELF, launch_path(option), SELF, rel(NEST_HIP)),
                 note="precheck items export_ok / build_check_all_ok / hip_sha_as_build_check / nest_tools_registered become true only after the "
                      "post-A375 Houdini steps (export, x55_nest_build.py --smoke, amend --write)")
        jdump(dict(o, cfg=L), SIM_DIR + "/run_%s_plan.json" % option)
        return final(o)
    if option == "C2":
        tie = c2_tied_to_c2id(C)
        if not tie["ok"]:
            return final(dict(ok=False, step="run", option=option, why="C2 is not run: %s" % "; ".join(tie["why"]), tie=tie))
        cs = calib_state()
        if not cs["ok"] and not os.path.exists(launch_path(option)):
            # the level step of C2's lattice is measured first (48 still-water frames at dp 0.25, CALIB_RULE_TEXT); then the launch cfg
            print(now(), "C2 calibration first (%s)" % cs["why"], flush=True)
            cr = calib_core(log=lambda *a: print(now(), *a, flush=True))
            if not cr.get("ok"):
                return final(dict(ok=False, step="run", option=option, why="C2 calibration failed: %s" % (cr.get("why") or cr.get("checks")), calib=cr))
            L, d = launch_cfg(option)
            pc = L["precheck"]
    if option == "C2ID" and not pinit_state()["ok"] and not os.path.exists(launch_path(option)):
        # F7: the parent's own frame-1056 particles first (hython hypart, ~1 min); then the launch cfg
        print(now(), "C2ID: the parent's particles first (%s)" % pinit_state()["why"], flush=True)
        pr = pinit_core()
        if not pr.get("ok"):
            return final(dict(ok=False, step="run", option=option, why="pinit failed: %s" % (pr.get("why") or pr.get("checks")), pinit=pr))
        L, d = launch_cfg(option)
        pc = L["precheck"]
    if not pc["ok"]:
        return final(dict(ok=False, step="run", option=option, why="launch precheck: %s" % pc["reason"]))
    if not chain_alive(rid):
        eg = entry_guard("run %s" % option, option, wait_min=WAIT_MIN)
        if not eg["ok"]:
            return final(dict(ok=False, step="run", option=option, why="entry guard: %s" % eg["why"], guard=eg))
    p, how = write_cfg_once(L, launch_path(option))
    lines = []

    def log(*a):
        msg = now() + " " + " ".join(str(x) for x in a)
        lines.append(msg)
        print(msg, flush=True)
        with open(guard(LOG_DIR + "/f55_nest_run_%s.log" % option), "a", encoding="utf-8") as fh:
            fh.write(msg + "\n")
    log("launch cfg", rel(p), how)
    st, hist = drive_chain("nest", p, rid, int(L["f_end"]), log, option)
    return final(dict(ok=bool(st["complete"]), step="run", option=option, run_dir=rel(rd), state=st["state"], frames_done=st["frames_done"],
                      stop=st.get("stop"), history=hist))


def c2_tied_to_c2id(C=None):
    """C2 runs only against the C2ID that passed the GN gates with THIS scene and THESE tools (code review M2): gates_GN.json ok, written by
    the current f55_nest.py; the C2ID launch cfg's nest scene / build check / x55 sha = the current ones; the registered amendment's
    code_sha256 = the current tools."""
    C = C or C_()
    rd0 = RUNS_ROOT + "/" + C.RID["C2ID"]
    g = jtry(rd0 + "/f55/gates_GN.json") or {}
    L0 = jtry(launch_path("C2ID")) or {}
    f0 = L0.get("f55") or {}
    am = [a for a in C.amendments() if a.get("id") == AMEND_ID]
    cs = (am[-1].get("code_sha256") or {}) if am else {}
    why = []
    if not g.get("ok"):
        why.append("GN1-GN3 on C2ID have not passed (%s)" % rel(rd0 + "/f55/gates_GN.json"))
    if g and g.get("tool_sha256") != sha(SELF):
        why.append("gates_GN.json was written by another f55_nest.py")
    if not f0:
        why.append("C2ID has no launch cfg (%s)" % rel(launch_path("C2ID")))
    else:
        if f0.get("nest_hip_sha256") != sha(NEST_HIP):
            why.append("the nest scene changed after C2ID was launched")
        if f0.get("build_check_sha256") != sha(NEST_BUILD_CHECK):
            why.append("the build check changed after C2ID was launched")
        if f0.get("x55_sha256") != sha(BUILD_TOOL) or f0.get("tool_sha256") != sha(SELF):
            why.append("x55_nest_build.py / f55_nest.py changed after C2ID was launched")
    if g and g.get("x55_sha256") != sha(BUILD_TOOL):
        why.append("x55_nest_build.py changed after C2ID was gated")
    if not cs or any(cs.get(p_) != sha(REPO + "/" + p_) for p_ in C.NEST_TOOLS):
        why.append("the registered AM-F55-NEST code_sha256 differs from the current tools")
    return dict(ok=not why, why=why, gates=rel(rd0 + "/f55/gates_GN.json"), c2id_launch=rel(launch_path("C2ID")))


# ====================================================================== analysis pieces (numpy; frozen readers)
def ana_mods():
    for p in (T52B3, T52, T51):
        if p not in sys.path:
            sys.path.insert(0, p)
    import g52_ana as GA52
    import g52b3_ana as GA
    import e51_metrics as EM
    return GA52, GA, EM


def eta0_of(rd):
    cfg = jtry(rd + "/cfg.json") or {}
    if cfg.get("still_offset_m") is not None:
        return float(cfg["still_offset_m"]), "cfg still_offset_m"
    GA52, _, _ = ana_mods()
    return GA52.still_offset(rd)


def group1_core(rd, frames=None):
    """GN1 core quantities of one run (the same code for the parent and the nest)."""
    import numpy as np
    GA52, GA, EM = ana_mods()
    eta0, src = eta0_of(rd)
    H = GA52.Blocks(rd, "hf", "eta")
    R2 = GA52.Blocks(rd, "r2", "sdf")
    a_t, b_t = T_FN - 8.0, T_FN + 6.0
    fr = [f for f in H.frames() if a_t - 1e-9 <= (f - 1) / FPS <= b_t + 1e-9]
    if frames is not None:
        fr = [f for f in fr if f in set(frames)]
    t, Hc, X, Y = [], [], [], []
    key = None
    for f in fr:
        a, meta = H.get(f)
        e = EM.median3(a) - eta0
        xs, yh = GA52.axes(meta, e.shape)
        if key != (e.shape, float(meta["x0"]), float(meta["z0"])):
            key = (e.shape, float(meta["x0"]), float(meta["z0"]))
            msk = (yh <= GN1_REGION["y"] + 1e-9)[:, None] & ((xs >= GN1_REGION["x"][0]) & (xs <= GN1_REGION["x"][1]))[None, :]
        v = np.where(msk, e, np.nan)
        t.append((f - 1) / FPS)
        if np.isfinite(v).any():
            j = int(np.nanargmax(v)); iy, ix = np.unravel_index(j, v.shape)
            Hc.append(float(v[iy, ix])); X.append(float(xs[ix])); Y.append(float(yh[iy]))
        else:
            Hc.append(np.nan); X.append(np.nan); Y.append(np.nan)
    t = np.asarray(t); Hc = np.asarray(Hc)
    lips = GA52.r2_lips(R2, eta0, fr, LIP_X[0], LIP_X[1])
    lips_t = [(f_ - 1) / FPS for f_, _ in lips]
    i, rule, lip1 = GA.pick_conv(t, Hc, T_FN, lips_t)
    out = dict(run=rel(rd), eta0=eta0, eta0_source=src, n_frames=len(fr), frames=[fr[0], fr[-1]] if fr else None, lip1_t=lip1,
               lips_first3=[dict(f=f_, t=(f_ - 1) / FPS, x=x_) for f_, x_ in lips[:3]], rule=rule)
    if i is not None:
        out.update(conv=dict(t=float(t[i]), f=int(fr[i]), Hc=float(Hc[i]), x=float(X[i]), y=float(Y[i])))
    return out


def gn1(parent_rd, nest_rd, nest_hollow=None, base_hollow=None):
    P = group1_core(parent_rd)
    N = group1_core(nest_rd)
    ck, val = {}, {}
    if P.get("conv") and N.get("conv"):
        val["Hc_rel"] = N["conv"]["Hc"] / P["conv"]["Hc"] - 1.0
        val["x_m"] = N["conv"]["x"] - P["conv"]["x"]
        val["t_conv_s"] = N["conv"]["t"] - P["conv"]["t"]
        ck["Hc"] = abs(val["Hc_rel"]) <= GN_TOL["Hc_rel"] + 1e-12
        ck["x_pk"] = abs(val["x_m"]) <= GN_TOL["x_m"] + 1e-9
        ck["t_conv"] = abs(val["t_conv_s"]) <= GN_TOL["t_s"] + 1e-9
    else:
        ck["conv_found"] = False
    if P.get("lip1_t") is not None and N.get("lip1_t") is not None:
        val["t_lip1_s"] = N["lip1_t"] - P["lip1_t"]
        ck["t_lip1"] = abs(val["t_lip1_s"]) <= GN_TOL["t_s"] + 1e-9
    else:
        ck["t_lip1"] = False
    if nest_hollow is not None and base_hollow is not None:
        for k in ("hood_max", "air_max"):
            a, b = (nest_hollow or {}).get(k), (base_hollow or {}).get(k)
            if a is None or b is None or b == 0:
                ck[k] = False
                val[k + "_rel"] = None
            else:
                val[k + "_rel"] = a / b - 1.0
                ck[k] = abs(val[k + "_rel"]) <= GN_TOL["hollow_rel"] + 1e-12
    else:
        ck["hollow_measured"] = False
    return dict(ok=bool(ck and all(ck.values())), checks=ck, values=val, parent=P, nest=N, rule=GN_RULES["GN1"], tol=GN_TOL)


def edge_cells():
    import numpy as np
    xa = np.arange(195.5, 197.0, 1.0)
    ya = np.arange(0.5, GN2_EDGES["A"]["y_max"], 1.0)
    yb = np.arange(43.5, 45.0, 1.0)
    xb = np.arange(195.5, 356.0, 1.0)
    pts = set((float(x), float(y)) for x in xa for y in ya) | set((float(x), float(y)) for x in xb for y in yb)
    pts = sorted(pts)
    return np.array([p[0] for p in pts]), np.array([p[1] for p in pts])


def gn2(parent_rd, nest_rd, f_lip1=None, Hc_ref=None):
    import numpy as np
    J = jtry(parent_rd + "/g52b3/judge_DFGB4.json") or {}
    g1 = [g for g in (J.get("groups") or []) if int(g.get("n", 0)) == 1]
    if Hc_ref is None:
        Hc_ref = float(g1[0]["conv"]["Hc"]) if g1 else None
    if f_lip1 is None:
        lt = ((g1[0].get("lip1") or {}).get("t")) if g1 else None
        f_lip1 = int(round(float(lt) * FPS)) + 1 if lt is not None else None
    if Hc_ref is None or f_lip1 is None:
        return dict(ok=False, why="the parent's judge has no group-1 conv Hc / lip1")
    e0p, _ = eta0_of(parent_rd)
    e0n, _ = eta0_of(nest_rd)
    HP, HN = HF(parent_rd), HF(nest_rd)
    xq, yq = edge_cells()
    sq, n, nanm, per = 0.0, 0, 0, []
    fr = [f for f in range(F0, f_lip1) if f in set(HP.frames()) and f in set(HN.frames())]
    for f in fr:
        ep, mp = HP.get(f)
        en, mn = HN.get(f)
        a = eta_at(np, ep, mp, xq, yq) - e0p
        b = eta_at(np, en, mn, xq, yq) - e0n
        ok = np.isfinite(a) & np.isfinite(b)
        nanm += int((np.isfinite(a) != np.isfinite(b)).sum())
        d = b[ok] - a[ok]
        sq += float((d * d).sum()); n += int(ok.sum())
        per.append(float(np.sqrt((d * d).mean())) if ok.any() else None)
    rms = math.sqrt(sq / n) if n else None
    tol = GN_TOL["gn2_frac"] * Hc_ref
    expected = f_lip1 - F0
    return dict(ok=bool(rms is not None and rms <= tol + 1e-12 and len(fr) == expected), rms_m=rms, tol_m=tol, Hc_ref=Hc_ref, f_lip1=f_lip1,
                frames=len(fr), frames_expected=expected, cells=int(len(xq)), pairs=n, nan_mismatch=nanm,
                per_frame_rms_max=max([p for p in per if p is not None] or [None]) if per else None, rule=GN_RULES["GN2"])


def column_volume(np, e, meta, bed_fn, box=GN3_BOX):
    xs0, dx, ys0, dy = float(meta["x0"]), float(meta["dx"]), float(meta["z0"]), float(meta["dz"])
    xs = xs0 + dx * np.arange(e.shape[1])
    ys = ys0 + dy * np.arange(e.shape[0])
    sx = (xs >= box["x"][0]) & (xs <= box["x"][1])
    sy = (ys >= box["y"][0]) & (ys <= box["y"][1])
    bed = bed_fn(xs[sx][None, :], ys[sy][:, None])
    col = np.nan_to_num(np.clip(e[np.ix_(sy, sx)].astype(np.float64) - bed, 0.0, None), nan=0.0)
    return float(col.sum()) * dx * dy, int(sx.sum()), int(sy.sum())


def gn3(parent_rd, nest_rd):
    import numpy as np
    C = C_()
    HP, HN = HF(parent_rd), HF(nest_rd)
    fp, fn = set(HP.frames()), set(HN.frames())
    want = frames_of(F0, F_END)
    worst = dict(rel=0.0, frame=None)
    rows, n_bad = [], 0
    for f in want:
        if f not in fp or f not in fn:
            continue
        ep, mp = HP.get(f)
        en, mn = HN.get(f)
        vp, nxp, nyp = column_volume(np, ep, mp, C.bed_z)
        vn, nxn, nyn = column_volume(np, en, mn, C.bed_z)
        r = vn / vp - 1.0
        rows.append((f, vp, vn, r))
        if abs(r) > abs(worst["rel"]):
            worst = dict(rel=r, frame=f, V_parent=vp, V_nest=vn)
        n_bad += int(abs(r) > GN_TOL["gn3_rel"] + 1e-12)
    complete = bool(len(rows) == len(want))
    return dict(ok=bool(complete and n_bad == 0), frames=len(rows), frames_expected=len(want), n_outside=n_bad, worst=worst, tol=GN_TOL["gn3_rel"],
                V_parent_first=rows[0][1] if rows else None, V_nest_first=rows[0][2] if rows else None,
                rel_series_every_24=[[f, round(r, 5)] for f, _, _, r in rows[::24]], rule=GN_RULES["GN3"])


# ------------------------------------------------------------------ judge-like group 1 of a nest run (pv53 / R0 read <run>/g52/judge_DFG.json)
def nest_judge(rd, write=True):
    """group 1 of a nest run by g52b3_ana.group_rows (the function that made DFG-2B-V's judge groups, unchanged) on the nest's own records."""
    GA52, GA, EM = ana_mods()
    sys.path.insert(0, T52B3)
    import g52b3_common as GCC
    eta0, src = eta0_of(rd)
    H = GA52.Blocks(rd, "hf", "eta")
    R2 = GA52.Blocks(rd, "r2", "sdf")
    R4 = GA52.Blocks(rd, "r4", "sdf")
    t_end = (max(H.frames()) - 1) / FPS
    PF = GA.pass_frames(H, eta0, T_FN - 14.0, T_FN + 14.0, GCC.kp())
    rows = GA.group_rows(rd, H, R2, R4, PF, eta0, t_end, [T_FN])
    J = dict(kind="F55 nest judge-like groups (g52b3_ana.group_rows on the nest's own records; NOT a DFGB4 judge; gates not applied)",
             run_id=os.path.basename(rd), run_dir=rel(rd), tool=TOOL_REL, tool_sha256=sha(SELF), date=now(), eta0=eta0, eta0_source=src,
             groups=rows, valid=None, failed_gates=None, decision=dict(outcomes=None), median={}, core_miss_median=None, red_instant=None,
             eligibility=None, t_record_end=t_end)
    if write:
        jdump(J, rd + "/g52/judge_DFG.json")
        jdump(J, rd + "/f55/judge_nest.json")
    return J


def run_tool(args, log_name, timeout):
    r = subprocess.run(["py", "-3.10", "-B"] + args, cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, stdin=subprocess.DEVNULL)
    with open(guard(LOG_DIR + "/" + log_name), "a", encoding="utf-8") as fh:
        fh.write("\n=== %s %s\n%s\n%s\n" % (now(), " ".join(args), r.stdout[-20000:], r.stderr[-20000:]))
    j = None
    for ln in reversed((r.stdout or "").splitlines()):
        ln = ln.strip()
        if ln.startswith("{") and ln.endswith("}"):
            try:
                j = json.loads(ln)
                break
            except ValueError:
                continue
    return r.returncode, j


def pv53_and_hollow(rd, unity, log):
    rid = os.path.basename(rd)
    pvj = REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (rid, rid)
    out = {}
    args = [PV53, "run", rd] + (["--lockwait", "120"] if unity else ["--no-unity"])
    rc, j = run_tool(args, "f55_nest_pv53_%s.txt" % rid, 3 * 3600)
    if unity and (rc != 0 or not os.path.exists(pvj)):
        log("pv53 with Unity rc %s: retry --no-unity" % rc)
        rc, j = run_tool([PV53, "run", rd, "--no-unity"], "f55_nest_pv53_%s.txt" % rid, 3600)
    out["pv53"] = dict(rc=rc, json=rel(pvj), exists=os.path.exists(pvj), unity_ok=(j or {}).get("unity_ok"), most_print_like=(j or {}).get("most_print_like"))
    rc, j = run_tool([HOLLOW, "measure", rd, "--groups=1"], "f55_nest_hollow_%s.txt" % rid, 3600)
    hp = rd + "/f55/hollow_F55.json"
    out["hollow"] = dict(rc=rc, file=rel(hp), exists=os.path.exists(hp), groups=(j or {}).get("groups"))
    return out


def cmd_gates(option="C2ID", sim=False):
    C = C_()
    if option != "C2ID":
        raise SystemExit("the GN gates are decided on C2ID (the plan); C2 gets them as a report in analyse")
    rd = RUNS_ROOT + "/" + C.RID["C2ID"]
    if sim:
        sd = STANDIN_ROOT + "/" + standin_rid("C2ID")
        o = dict(ok=True, step="gates", option=option, simulate=True, run_dir=rel(rd), rules=GN_RULES,
                 would_run=["judge-like group 1 -> %s/g52/judge_DFG.json" % rel(rd), "py -3.10 -B %s run %s --no-unity" % (rel(PV53), rel(rd)),
                            "py -3.10 -B %s measure %s --groups=1" % (rel(HOLLOW), rel(rd)), "GN1 / GN2 / GN3 vs %s" % rel(DFGBV_RUN)])
        if os.path.isdir(sd) and glob.glob(sd + "/hf_c*.npz"):
            o["standin_gates"] = dict(GN1_core=gn1(DFGBV_RUN, sd)["values"], GN2=gn2(DFGBV_RUN, sd)["rms_m"], GN3=gn3(DFGBV_RUN, sd)["worst"])
        return final(o)
    st = run_state(rd, F_END)
    if not st["complete"]:
        return final(dict(ok=False, step="gates", why="C2ID is not complete (%s, frames done %d)" % (st["state"], st["frames_done"])))
    logs = []
    log = lambda *a: (logs.append(" ".join(str(x) for x in a)), print(now(), *a, flush=True))
    J = nest_judge(rd)
    ph = pv53_and_hollow(rd, unity=False, log=log)
    hn = (jtry(rd + "/f55/hollow_F55.json") or {}).get("groups", {}).get("1")
    hb = (jtry(C.BASELINE) or {}).get("groups", {}).get("1")
    g1 = gn1(DFGBV_RUN, rd, hn, hb)
    g2 = gn2(DFGBV_RUN, rd)
    g3 = gn3(DFGBV_RUN, rd)
    res = dict(date=now(), tool=TOOL_REL, tool_sha256=sha(SELF), x55_sha256=sha(BUILD_TOOL), nest_hip_sha256=sha(NEST_HIP),
               build_check_sha256=sha(NEST_BUILD_CHECK), launch_cfg_sha256=sha(launch_path("C2ID")), option=option, run=rel(rd),
               parent=rel(DFGBV_RUN), GN1=g1, GN2=g2, GN3=g3,
               judge_like=dict(groups=[{k: g.get(k) for k in ("n", "f", "t", "x_pk", "Hc", "conv", "lip1", "complete")} for g in J["groups"]]),
               analysis=ph, order=GN_RULES["order"], baseline=rel(C.BASELINE), baseline_sha256=C.sha(C.BASELINE),
               amendment=AMEND_ID, tags=dict(numbers="measured (records) with the registered rules"))
    res["ok"] = bool(g1["ok"] and g2["ok"] and g3["ok"])
    jdump(res, rd + "/f55/gates_GN.json")
    return final(dict(ok=res["ok"], step="gates", option=option, GN1=g1["ok"], GN2=g2["ok"], GN3=g3["ok"], GN1_values=g1["values"],
                      GN2_rms_m=g2.get("rms_m"), GN2_tol_m=g2.get("tol_m"), GN3_worst=g3.get("worst"), file=rel(rd + "/f55/gates_GN.json")))


def cmd_analyse(option="C2", sim=False):
    C = C_()
    if option != "C2":
        raise SystemExit("analyse C2")
    rd = RUNS_ROOT + "/" + C.RID["C2"]
    rid0 = RUNS_ROOT + "/" + C.RID["C2ID"]
    if sim:
        return final(dict(ok=True, step="analyse", option=option, simulate=True,
                          would_run=["judge-like group 1 -> %s/g52/judge_DFG.json" % rel(rd), "py -3.10 -B %s run %s --lockwait 120 (retry --no-unity)"
                                     % (rel(PV53), rel(rd)), "py -3.10 -B %s measure %s --groups=1" % (rel(HOLLOW), rel(rd)),
                                     "GN2 / GN3 of C2 vs the parent (report only)",
                                     "then auto_F55: f55_hollow.py verdict %s --stage=g1 --base=%s/f55/hollow_F55.json" % (rel(rd), rel(rid0))]))
    st = run_state(rd, F_END)
    if not st["complete"]:
        return final(dict(ok=False, step="analyse", why="C2 is not complete (%s, frames done %d)" % (st["state"], st["frames_done"])))
    logs = []
    log = lambda *a: (logs.append(" ".join(str(x) for x in a)), print(now(), *a, flush=True))
    J = nest_judge(rd)
    ph = pv53_and_hollow(rd, unity=True, log=log)
    rep = dict(GN2_report=gn2(DFGBV_RUN, rd), GN3_report=gn3(DFGBV_RUN, rd), GN1_core_report=gn1(DFGBV_RUN, rd)["values"])
    base_ok = os.path.exists(rid0 + "/f55/hollow_F55.json")
    res = dict(date=now(), tool=TOOL_REL, tool_sha256=sha(SELF), option=option, run=rel(rd), analysis=ph, report_only=rep,
               judge_like=dict(groups=[{k: g.get(k) for k in ("n", "f", "t", "x_pk", "Hc", "conv", "lip1", "complete")} for g in J["groups"]]),
               base_hollow=rel(rid0 + "/f55/hollow_F55.json"), base_hollow_exists=base_ok,
               reading_note=("C2 is read with the parent's still offset 0.076 m (dp 0.5); its own is probably ~0.04 m [guess]: C2's eta / Hc read "
                             "~0.04 m low against C2ID; the hollow +25 % reading does not depend on it (physics review M5)"))
    res["ok"] = bool(ph["hollow"]["exists"] and base_ok)
    jdump(res, rd + "/f55/analyse_C2.json")
    return final(dict(ok=res["ok"], step="analyse", option=option, hollow=ph["hollow"]["file"], base=res["base_hollow"], pv53_unity=ph["pv53"]["unity_ok"],
                      GN2_report_rms_m=rep["GN2_report"].get("rms_m"), GN3_report_worst=rep["GN3_report"].get("worst"),
                      file=rel(rd + "/f55/analyse_C2.json")))


# ====================================================================== the amendment AM-F55-NEST
def amendment_record():
    C = C_()
    bc = jtry(NEST_BUILD_CHECK) or {}
    shas = {p: C.sha(REPO + "/" + p) for p in C.NEST_TOOLS}
    return dict(
        id=AMEND_ID, plan=C.PLAN_REL, plan_sha256=C.sha(C.PLAN), date=now(), by="main session (Claude), after the nest build check passed",
        what=("registers the C2 nest tools (written 2026-10-19 after Q88) and their rules BEFORE any nest run; RE-REGISTERED after the first "
              "C2ID failed its identity gates (fix_2026_10_19_after_C2ID: F1 Input 1 = self + counters, F2 linear nest band weight, F7 C2ID "
              "from the parent's own particles, C2 lattice with a calibrated level step); the plan's cfgs, gates and reading do not change"),
        code_sha256=shas,
        frozen_used=dict(runner=dict(path=rel(RUNNER), sha256=RUNNER_SHA), chain=dict(path=rel(CHAIN), sha256=CHAIN_SHA, in_memory_replacements=[
            [a, b] for a, b, _ in CHAIN_REPL]), restart=dict(path=rel(G49R), sha256=G49R_SHA, note="dirs() replaced in memory (new folder under FLIP55)")),
        parent_export=dict(run=EXPORT_RID, cfg_rule=("DFG-2B-V's launched cfg.json with only %s changed (and the case labels %s); records equal; "
                                                     "the seed of h52b3_long / g49_restart") % (sorted(EXPORT_TOP_ALLOWED), sorted(EXPORT_CASE_ALLOWED)),
                           hook="read-only: hou.setFrame wrapped, fields of frame f (already cooked by the runner) copied before frame f + 1",
                           frame_1056="separate hython 'hyckpt' from a copy of v.1056.sim", spec=export_spec(C),
                           acceptance="strict bit-identity vs the judged run on frames 1057-1657 + R1 alignment <= 1e-3 m + vd files identical"),
        launch_rule=dict(derived_keys=list(DERIVED_KEYS), why=DERIVED_WHY, parms=LAUNCH_PARMS, str_parms={k: rel(v) for k, v in LAUNCH_STR_PARMS.items()},
                         per_option=dict(parms=OPTION_PARMS, str_parms={o: {k: rel(v) for k, v in d.items()} for o, d in OPTION_STR_PARMS.items()},
                                         note="these values replace LAUNCH_PARMS / LAUNCH_STR_PARMS per option; C2 init_lvl_m None = the calibrated "
                                              "level step (calib55_C2.json, " + CALIB_RULE_TEXT + ")"),
                         overrides={k: dict(design=OVERRIDE_FROM[k], launch=v) for k, v in OVERRIDE_PARMS.items()},
                         rule="launch cfg = f55_pcfg.make(option, 'g1') (sha16 = the plan's) + DERIVED_KEYS, with the ONE registered override "
                              "parms.wall_taper_m 15 -> 0; everything else canonically equal",
                         case_note="the launch cfg inherits the design cfg's case.runnable false and its 'NOT runnable' note (the design sha16 "
                                   "must stay the plan's); f55.mode 'nest' and the launch precheck make the launch (code review M11)"),
        design_deviation=dict(
            what="parms.wall_taper_m 15 -> 0 for both nest runs (C2ID and C2): the ONLY change of a frozen design cfg value",
            why=DERIVED_WHY["parms.wall_taper_m 15 -> 0 (OVERRIDE of the design value)"],
            registered="before any nest run, with the build check that probes it (band_probe against the numpy mirror with wall_taper_m 0)"),
        review_fixes_2026_10_19=dict(
            B1_sponge="wall_taper_m 0 (above)",
            B2_border=("OUT_TARGET volumes carry one ghost cell on every side (edge copy = Streak; even mirror at y = 0 for cell-centred fields, odd "
                       "for the vel.z face grid) and the 2-D e volumes are 2 voxels tall: no sample inside the data reaches Houdini's constant-0 "
                       "border (the first 0.5 m beside the plane read 0.625-0.875 x; hou.Volume has no setBorder in this Houdini [measured, "
                       "hou.py], the volumeborder intrinsic is also set to streak where writable); probed at lateral 0.02-0.48 m"),
            B3_level=("s_off = the parent's still offset 0.0759846568107605 m: the nest's water is 'SDF + s_off < 0' (the parent's particle "
                      "level) at init and in band kill / seed (+0.057 m C2ID / +0.075 m C2 level bias removed [computed])"),
            M1_seed_attributes="a seed is addpoint(0, nearest nest particle) (all attributes), then its P, v and a fresh id (nextid when present)",
            M2_dead_band="seed_margin_dp 0.5 -> 0 (band level +-0.1 m instead of [-0.34, +0.08] m for C2ID [computed])",
            M3_dry_columns="dry columns of the target's top surface = the bed height (not -1000)",
            M4_near_bed="bed_trust_m 1: within 1 m of the bed the parent's top surface decides water (its SDF reads air there)",
            M6_hyckpt="hyckpt refuses a cook > 300 s, is killed after 1200 s, and frame 1056 is validated (R1 alignment) before the rerun",
            M7_end_band="the optional end band's target has no taper either",
            start_frame=("the DOP network keeps DFG-2B-V's start frame 1 ($SF = $F; explicit-cache names must use $SF [Houdini help, measured]) "
                         "and the objects are created at 1056; a DOP start frame of 1056 would have named the checkpoints by simulation "
                         "frames and broken the frozen chain's resume"),
            ops=("watchdog per chain (free commit < 3 GB on 2 polls or the brake file -> <run>/STOP), entry guard (no other pipeline / "
                 "hython / Unity batch / foreign auto_F55, free commit and disk >= the plan's need), C2 tied to the gated C2ID's scene and tools")),
        nest_scene=dict(hip=rel(NEST_HIP), hip_sha256=bc.get("hip_sha256"), build_check=rel(NEST_BUILD_CHECK),
                        build_check_sha256=sha(NEST_BUILD_CHECK) if os.path.exists(NEST_BUILD_CHECK) else None,
                        build_check_all_ok=bc.get("all_ok"), smoke_ok=bc.get("smoke_ok"), built_with_tool_sha256=bc.get("tool_sha256"),
                        build_check_matches_these_tools=bool((bc.get("tool_sha256") or {}) == shas),
                        smoke_surface_activity_ok=((bc.get("smoke_py") or {}).get("surface_activity") or {}).get("ok"),
                        smoke_volume_tracking_ok=((bc.get("smoke_py") or {}).get("volume_tracking") or {}).get("ok"),
                        note="the build check on disk when this record was written; amend --write appends only when it was made with these "
                             "tools and this hip and its smoke passed"),
        parent_particles=dict(pinit_state(), json=rel(PINIT_JSON)),
        bands=("x 180-195 and y 45-60 with the nest-only LINEAR band weight per frame w = chi (band_lin 1; nest_bands = bands50 with relaxw -> "
               "chi; corner = max), velocity per substep toward the parent's (horizontal, no wall taper, as relax_apply otherwise; per substep "
               "1 - (1 - w)^(dts/dt0)), surface per frame by particles (band_count / band_kill / band_seed with Input 1 = Myself: delete band "
               "particles that are not the parent's water; seed parent-water lattice points where fewer than half the full-water count of "
               "nest particles lie within 1.5 dp; probability = the band weight over one frame; all counters reset in band_count after the "
               "once-per-frame gate, band_tgt = tgt_ok()); the parent's water = below its particle level minus init_lvl_m (SDF + s_off < "
               "-init_lvl_m; C2ID 0, C2 the calibrated step) or, within 1 m of the bed, below its top surface - s_off - init_lvl_m; target linear in time (fa = ceil(ff) - 1, fb = "
               "ceil(ff)), trilinear in space on the parent's 1 m grid (ghost cells, mirrored at y = 0)"),
        init=("C2ID: the PARENT'S OWN frame-1056 particles inside the box (p_01056.npz from DFG-2B-V's checkpoint copy v.1056.sim, read by "
              "f55_nest.py pinit through the hyckpt path: P and v unchanged; validated against the hyckpt particle count, the parent's SDF and "
              "grid velocity); C2 (dp 0.25): the lattice at dp kept where it is the parent's water BY THE MARGIN init_lvl_m = the calibrated "
              "level step (" + CALIB_RULE_TEXT + ") and above bed + 0.5 dp, jitter 0.2 dp, velocity = the parent's grid velocity; for C2 the "
              "lattice AND the band water rule (band_kill margin init_lvl_m - kill_margin_dp dp, band_seed margin seed_margin_dp dp + "
              "init_lvl_m and candidates e - init_lvl_m - 2 m .. e - init_lvl_m) are shifted by init_lvl_m (physics review 2026-10-19 B1: "
              "otherwise the bands would hold the unshifted level and act as a sink / source that undoes the shift in ~3-13 s [computed]); "
              "DOP network start frame 1 (as the parent), FLIP / static objects created at 1056"),
        reading_note=("C2 (dp 0.25) keeps the parent's water: its lattice and band water rule are shifted by the calibrated rise after "
                      "creation (calib55_C2.json analysis.step_m), not by its reading offset. C2 is read with the parent's still offset 0.076 m "
                      "(dp 0.5); its own is probably ~0.04 m [guess]: C2's eta / Hc read ~0.04 m low against C2ID (offset measured: "
                      "calib55_C2.json analysis.offset_at_creation_m; reported with any Hc comparison C2 vs C2ID together with "
                      "step_per_20m_x and slope_last24_m_per_s); the hollow +25 % reading does not depend on it (physics review M5). With "
                      "the linear band weights the side strip y 45-60 m is forced over its whole width toward the parent's 0.5 m solution "
                      "(w per frame 0.33 at y 50 m instead of 0.013 [computed], breaking included); the GN1 / hollow region y 0-20 m stays "
                      ">= 25 m away (physics review M3)"),
        fix_2026_10_19_after_C2ID=dict(
            supersedes=dict(PREVIOUS_REGISTRATION, why="the registered C2ID failed GN1-GN3; this record replaces it (the last AM-F55-NEST "
                                                        "line is the one f55_common.nest_tools_state and c2_tied_to_c2id read)"),
            failed_C2ID=dict(GN1="Hc -18.1 %, x +7.0 m, t_lip1 +2.92 s (tolerances 2 %, 1.5 m, 0.25 s)", GN2="0.639 m vs 0.402 m",
                             GN3="worst +2.73 % (frame 1445) vs 2 %", tag="measured (gates_GN.json of the archived C2ID run)"),
            diagnosis=("Unity/Build/FLIP55/diag_gn1 (workflow, 2026-10-19; the pre-fix build check, raw smoke record, smoke cfg / eta / p1056, "
                       "hip and pv53 kept in Unity/Build/FLIP55/runs/_archived/prefix_build_C2ID_20261019 by nest_fix_test.sh before the "
                       "new smoke: build_raw55_nest.json there): band_cand 0 in all 24 smoke frames [measured]: the surface relaxation "
                       "never ran, most likely because band_kill / band_seed Input 1 was 'none' (the saved hip: bindinputmenu1 \"none\" on both "
                       "[measured, static read]) so detail(0, 'ss_n') read 0 and the once-per-frame gate returned [computed, not verified in "
                       "Houdini]; a velocity-only relaxation with a closed wall reproduces Hc -19 % and GN2 0.63 m [computed, band_lin.py]; the "
                       "x 180 face passes 0.25-0.71 of the parent flux, anti-phase at the wall [computed]; the lattice init 7.7 / m3 vs the "
                       "parent's 8.9 / m3 + FLIP reseeding raised the volume +2 % in 9 frames [measured, smoke]"),
            F1=("band_count (new, detail) / band_kill / band_seed: bindinputmenu1 = 'self' (Myself) [menu token measured by a static read of "
                "the Geometry Wrangle DialogScript in OPlibDop.hda of the pipeline's Houdini Indie 22.0.466 and of Houdini 21.0.729: tokens "
                "none / sop / dopdata / self / first / second / third / fourth / selfraw, default none]; ALL counters reset in band_count after "
                "the once-per-frame gate and before the target test (band_tgt = tgt_ok(); a failed target never shows the previous frame's "
                "counts, review M1); band_kills (setdetailattrib add) and band_kills_np (point count before - after band_kill); a seed's "
                "pprevious = its own position; the smoke needs band_tgt 1 and band_cand > 0 on every frame, kills > 0 summed over the "
                "1-substep frames (all frames when none has 1 substep; per-frame kills reported: with F7 the nest starts as the parent's "
                "own particles, so single frames may have none, code review M1) and std(V_nest) / std(V_parent) > 0.8 over the smoke frames"),
            F2="band_lin 1: w = chi (linear) over the 15 m bands, nest only (DERIVED_WHY 'parms.band_lin 1')",
            F7=("C2ID from the parent's own particles (init_src 1, pinit_npz; pinit also checks that the checkpoint copy is unchanged); C2 "
                "keeps the lattice with the calibrated level step (init_src 0, init_lvl_m from f55_nest.py calib C2, run automatically by "
                "'run C2' before its launch cfg is written): step = the rise of the nest's level after creation (code review B1: C2's dp "
                "0.25 reading offset is reported, not subtracted, physics review M5), applied to the lattice AND the band water rule "
                "(physics review B1)"),
            gates="GN1-GN3 unchanged (GN_RULES, GN_TOL)",
            order=("copy of the pre-fix evidence -> f55_nest.py selftest -> pinit -> x55_nest_build.py --smoke (build check + smoke) -> "
                   "archive C2ID -> amend --write -> "
                   "run C2ID -> gates C2ID (G:/research/Wave Simulation/_tools/nest_fix_test.sh); C2 (with its calibration) only when the "
                   "main session decides")),
        volume="replay of the judged run's vd_<f>.txt (stage A d) in x 195-356 m; no own controller",
        end_band=("OFF (end_on 0 = the frozen 'outflow: none'). Built and probed (build check band_probe.end_band) because the parent's swash "
                  "passes the nest's closed face x 356 m; switching it on needs its own amendment (the export already carries box eb)"),
        measured_facts=dict(
            parent_volume_in_nest_box="-0.69 % .. +2.51 % of 86,974 m3 over frames 1057-1657 (hf column rule, y <= 60 m) [measured]: a mass-closed "
                                      "nest cannot pass GN3, hence the particle surface relaxation in the bands",
            parent_swash="wet to x 386.5 m (y <= 60 m) from frame 1077; mean depth 0.1-0.64 m at x 355.5 m; at most 402 m3 (0.46 %) beyond x 356 m "
                         "[measured]: the closed face reflects it (GN1 risk, not GN3)",
            standin=("DFG-2B-V's records cropped to the nest box: GN1 core / GN2 / GN3 exact zeros, the judge-like group = the judged group 1 "
                     "(f 1412, x 227.5 m, Hc 8.046846 m, lip 61.375 s), pv53 + the R0 ruler = the frozen baseline group 1 to its rounding "
                     "[measured, f55_nest.py standin --hollow]")),
        gates=GN_RULES, gate_tolerances=GN_TOL,
        honesty="engineering after the user's Q88 (finer 3D trial without waiting for the supervisor); C2 is the frozen design except the one "
                "registered override (wall_taper_m 0, design_deviation) and the band / init rules written here; GN gates decide whether the "
                "nest is clean before any reading")


def cmd_amend(write=False):
    C = C_()
    rec = amendment_record()
    jdump(dict(rec, status="DRAFT (not appended)" if not write else "appending"), AMEND_DRAFT)
    if not write:
        return final(dict(ok=True, step="amend", draft=rel(AMEND_DRAFT), appended=False, code_sha256=rec["code_sha256"],
                          note="append with --write after x55_nest_build.py --smoke passes (build_check55_nest.json all_ok + smoke_ok)"))
    bc = jtry(NEST_BUILD_CHECK) or {}
    why = []
    if not (bc.get("all_ok") and bc.get("smoke_ok")):
        why.append("build check all_ok / smoke_ok false")
    if bc.get("hip_sha256") != sha(NEST_HIP):
        why.append("the nest scene changed after its build check")
    if (bc.get("tool_sha256") or {}) != rec["code_sha256"]:
        why.append("the tools changed after the build check (rebuild and recheck)")
    if not (jtry(EXPORT_JSON) or {}).get("ok"):
        why.append("the parent export is not ok")
    if not pinit_state()["ok"]:
        why.append("the parent's particles (f55_nest.py pinit) are not ok: %s" % pinit_state()["why"])
    if [a for a in C.amendments() if a.get("id") == AMEND_ID and a.get("code_sha256") == rec["code_sha256"]]:
        return final(dict(ok=True, step="amend", appended=False, why="already registered with these sha256"))
    if why:
        return final(dict(ok=False, step="amend", appended=False, why=why))
    rec["status"] = "REGISTERED"
    with open(guard(AMENDMENTS), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(clean(rec), ensure_ascii=False) + "\n")
    return final(dict(ok=True, step="amend", appended=True, amendments=rel(AMENDMENTS), state=C.nest_tools_state()))


def cmd_status():
    C = C_()
    out = dict(step="status", export=jtry(EXPORT_JSON) and dict((k, (jtry(EXPORT_JSON) or {}).get(k)) for k in ("ok", "seconds")),
               build_check=dict((k, (jtry(NEST_BUILD_CHECK) or {}).get(k)) for k in ("all_ok", "smoke_ok", "hip_sha256", "date")),
               nest_tools=C.nest_tools_state(), amendment_draft=os.path.exists(AMEND_DRAFT), pinit=pinit_state(), calib_C2=calib_state(),
               runs={o: dict(run_state(RUNS_ROOT + "/" + C.RID[o], F_END), last=None) for o in ("C2P", "C2ID", "C2")},
               gates=(jtry(RUNS_ROOT + "/" + C.RID["C2ID"] + "/f55/gates_GN.json") or {}).get("ok"))
    out["ok"] = True
    return final(out)


def cmd_archive(option, sim=False):
    """move runs/<rid> and ready/<rid>__g1_launch.json of a nest run to runs/_archived/<rid>__<time>/ (a rerun after an amendment needs a
    clean folder: run_state would read the old chain as complete and write_cfg_once refuses a changed launch cfg). Refused while its chain
    runs or when the process scan fails. Nothing is deleted."""
    C = C_()
    if option not in ("C2ID", "C2"):
        return final(dict(ok=False, step="archive", why="archive C2ID | C2 (the parent export is never archived by this tool)"))
    rid = C.RID[option]
    rd = RUNS_ROOT + "/" + rid
    lp = launch_path(option)
    dst = RUNS_ROOT + "/_archived/%s__%s" % (rid, time.strftime("%Y%m%d_%H%M%S"))
    have = [p for p in (rd, lp) if os.path.exists(p)]
    alive = chain_alive(rid)
    o = dict(step="archive", option=option, move=[rel(p) for p in have], to=rel(dst), chain_alive=alive)
    if sim:
        return final(dict(o, ok=True, simulate=True))
    if alive is not False:
        return final(dict(o, ok=False, why="its chain is running or the process scan failed (%s): nothing moved" % alive))
    if not have:
        return final(dict(o, ok=True, why="nothing to archive"))
    guard(dst + "/archived.json")
    for p in have:
        guard(p)
        shutil.move(p, dst + "/" + os.path.basename(p))
    jdump(dict(o, date=now(), tool=TOOL_REL, tool_sha256=sha(SELF)), dst + "/archived.json")
    return final(dict(o, ok=True))


# ====================================================================== stand-in (the parent's own records cropped to the nest box)
def standin_rid(option):
    return "F55S_standin_" + option


def make_standin(option="C2ID", log=print):
    """a folder with DFG-2B-V's hf / r2 / r4 records of frames 1057-1657 cropped to the nest box (x 180-356, y 0-60; r4 to x >= 195, y <= 45),
    cfg.json = the launch cfg of option, one run record: an exact copy of what a perfect nest would record on the parent's grid."""
    import numpy as np
    rd = STANDIN_ROOT + "/" + standin_rid(option)
    guard(rd + "/x")
    L, _ = launch_cfg(option, for_smoke=True)
    L = copy.deepcopy(L)
    L["run_id"] = standin_rid(option)
    L["out_root"] = STANDIN_ROOT
    L["case"]["stand_in"] = "DFG-2B-V records cropped to the nest box (f55_nest.py standin); NOT a FLIP run"
    jdump(L, rd + "/cfg.json")
    out = {}
    for kind, keys in (("hf", ("eta",)), ("r2", ("sdf", "u", "w")), ("r4", ("sdf",))):
        where = {}
        for p in sorted(glob.glob(DFGBV_RUN + "/%s_c*_b*.npz" % kind)):
            c_ = int(os.path.basename(p).split("_c")[1][:5])
            with np.load(p, allow_pickle=True) as d:
                fr = np.array(d["frames"])
            for i, f in enumerate(fr):
                f = int(f)
                if F0 <= f <= F_END and (f not in where or where[f][0] < c_):
                    where[f] = (c_, p, i)
        frames = sorted(where)
        blocks, cur, cache = [], [], {}
        for f in frames:
            if not cur or len(cur) >= (24 if kind == "r4" else 120) or (kind == "r4" and f - cur[-1] > 3):
                if cur:
                    blocks.append(cur)
                cur = []
            cur.append(f)
        if cur:
            blocks.append(cur)
        nf = 0
        for blk in blocks:
            arrs = {k: [] for k in keys}
            meta_out = None
            for f in blk:
                c_, p, i = where[f]
                if p not in cache:
                    cache.clear()
                    with np.load(p, allow_pickle=True) as d:
                        cache[p] = ({k: np.array(d[k]) for k in keys if k in d.files}, json.loads(str(d["meta"])))
                A, meta = cache[p]
                if kind == "hf":
                    xs = meta["x0"] + meta["dx"] * np.arange(meta["res"][0]); zs = meta["z0"] + meta["dz"] * np.arange(A["eta"].shape[1])
                    sx = np.where((xs >= 180.0) & (xs <= 356.0))[0]; sz = np.where((zs >= 0.0) & (zs <= 60.0))[0]
                    arrs["eta"].append(A["eta"][i][np.ix_(sz, sx)])
                    meta_out = dict(meta, res=[int(len(sx)), meta["res"][1], int(len(sz))], x0=float(xs[sx[0]]), z0=float(zs[sz[0]]))
                elif kind == "r2":
                    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"])
                    sx = np.where((xs >= 180.0) & (xs <= 356.0))[0]
                    arrs["sdf"].append(A["sdf"][i][:, sx])
                    vel_out = {}
                    for k, vn in (("u", "vel.x"), ("w", "vel.y")):          # each component on its own (face) x grid
                        vm = (meta.get("vel") or {}).get(vn)
                        if vm is None or k not in A:
                            continue
                        xv = vm["p0"][0] + vm["d"][0] * np.arange(A[k][i].shape[1])
                        sv = np.where((xv >= 180.0 - 1e-9) & (xv <= 356.0 + 1e-9))[0]
                        arrs[k].append(A[k][i][:, sv])
                        vel_out[vn] = dict(vm, p0=[float(xv[sv[0]])] + list(vm["p0"][1:]), res=[int(len(sv))] + list(vm["res"][1:]))
                    meta_out = dict(meta, x0=float(xs[sx[0]]), nx=int(len(sx)), res=[int(len(sx)), meta["res"][1], meta["res"][2]], vel=vel_out)
                else:
                    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"]); zl = meta["z0"] + meta["dz"] * np.arange(meta["nz"])
                    sx = np.where((xs >= 195.0) & (xs <= 335.0))[0]; sz = np.where(zl <= 45.0)[0]
                    arrs["sdf"].append(A["sdf"][i][np.ix_(sz, np.arange(A["sdf"].shape[2]), sx)])
                    meta_out = dict(meta, x0=float(xs[sx[0]]), nx=int(len(sx)), nz=int(len(sz)))
            save = {k: np.array(v, dtype=(np.float32 if k == "eta" else np.float16)) for k, v in arrs.items() if v}
            pth = guard(rd + "/%s_c%05d_b%05d.npz" % (kind, F0, blk[0]))
            np.savez_compressed(pth, frames=np.array(blk), t=np.array([(f - 1) / FPS for f in blk]), meta=json.dumps(meta_out), **save)
            nf += len(blk)
        out[kind] = nf
    r0 = jtry(DFGBV_RUN + "/run_c01441.json") or {}
    hf0 = HF(rd)
    _, m0 = hf0.get(F0)
    rec = dict(stage="FLIP52B3", run_id=standin_rid(option), stand_in=True, f_start=F0, f_end_req=F_END, f_end_done=F_END, stopped=None,
               fps=24.0, t_off=0.0, grid=m0, parms=r0.get("parms"), info=dict(still_offset_online=None), still_offset=dict(value=STILL_OFFSET, source="cfg"),
               note="stand-in record (f55_nest.py standin): DFG-2B-V's records cropped to the nest box; not a FLIP run")
    jdump(rec, rd + "/run_c%05d.json" % F0)
    jdump(rec, rd + "/run.json")
    out["dir"] = rel(rd)
    return rd, out


def cmd_standin(hollow=False):
    t0 = time.time()
    rd, made = make_standin("C2ID")
    C = C_()
    J = nest_judge(rd)
    P = jtry(DFGBV_RUN + "/g52b3/judge_DFGB4.json") or {}
    pg = [g for g in P.get("groups", []) if int(g["n"]) == 1][0]
    sg = [g for g in J["groups"] if int(g["n"]) == 1][0]
    jl = dict(parent=dict(f=pg.get("f"), x_pk=pg.get("x_pk"), Hc=pg.get("Hc"), conv=pg.get("conv"), lip1=pg.get("lip1")),
              standin=dict(f=sg.get("f"), x_pk=sg.get("x_pk"), Hc=sg.get("Hc"), conv=sg.get("conv"), lip1=sg.get("lip1"), complete=sg.get("complete")))
    jl["same_instant"] = bool(sg.get("f") == pg.get("f") and sg.get("x_pk") == pg.get("x_pk"))
    g1 = gn1(DFGBV_RUN, rd)
    g2 = gn2(DFGBV_RUN, rd)
    g3 = gn3(DFGBV_RUN, rd)
    ident = bool(g1["values"].get("Hc_rel") == 0.0 and g1["values"].get("x_m") == 0.0 and g1["values"].get("t_conv_s") == 0.0
                 and g1["values"].get("t_lip1_s") == 0.0 and g2.get("rms_m") == 0.0 and g2["ok"] and g3["worst"]["rel"] == 0.0 and g3["ok"])
    res = dict(date=now(), tool=TOOL_REL, standin=rel(rd), made=made, judge_like=jl, GN1_core=dict(checks=g1["checks"], values=g1["values"],
                                                                                                 parent=g1["parent"].get("conv"), nest=g1["nest"].get("conv")),
               GN2=dict((k, g2.get(k)) for k in ("ok", "rms_m", "tol_m", "frames", "frames_expected", "pairs", "nan_mismatch")),
               GN3=dict((k, g3.get(k)) for k in ("ok", "frames", "frames_expected", "n_outside", "worst", "V_parent_first")),
               identity_exact=ident)
    if hollow:
        sys.path.insert(0, T53)
        scan = subprocess.run(["py", "-3.10", "-B", PV53, "scan", rd], cwd=REPO, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=3600)
        lines = [l for l in (scan.stdout or "").splitlines() if l.strip().startswith("{")]
        res["pv53_scan_rc"] = scan.returncode
        if lines:
            sj = json.loads(lines[-1])
            pvp = guard(rd + "/f55/pv53_scan.json")
            jdump(dict(periods=sj.get("periods"), verdict=sj.get("verdict"), run=sj.get("run")), pvp)
            sys.path.insert(0, HERE)
            import f55_hollow as FH
            m = FH.measure_run(rd, pv=pvp, groups="1", out_dir=rd + "/f55", tag="F55S_" + os.path.basename(rd))
            m.pop("r0_groups", None)
            jdump(m, rd + "/f55/hollow_F55.json")
            b = (jtry(C.BASELINE) or {}).get("groups", {}).get("1") or {}
            q = m["groups"].get(1) or m["groups"].get("1") or {}
            res["hollow"] = {k: dict(standin=q.get(k), baseline=b.get(k), rel=(q.get(k) / b.get(k) - 1.0) if (q.get(k) is not None and b.get(k)) else None)
                             for k in ("air_max", "hood_max", "hood78", "chord_at_hood_max", "hi_air", "best_score3", "n_alive")}
        else:
            res["pv53_scan_error"] = (scan.stderr or "")[-1500:]
    res["seconds"] = round(time.time() - t0, 1)
    jdump(res, rd + "/f55/standin_result.json")
    return final(dict(ok=bool(ident and sg.get("complete")), step="standin", file=rel(rd + "/f55/standin_result.json"), identity_exact=ident,
                      judge_like_same_instant=jl["same_instant"], GN2_rms=g2.get("rms_m"), GN3_worst=g3["worst"],
                      hollow=res.get("hollow"), seconds=res["seconds"]))


# ====================================================================== selftest (numpy / static; no Houdini)
class FakeHou:
    """a stand-in for hou in the hook test: setFrame records the order; node().geometry() is never called because export is stubbed."""

    def __init__(self):
        self.calls = []

    def setFrame(self, f):
        self.calls.append(("real", int(f)))


def selftest():
    import numpy as np
    C = C_()
    ok = {}
    det = {}
    # 1. frozen shas + the chain patch
    pl = jtry(C.PLAN) or {}
    fu = pl.get("code_sha256_frozen_used") or {}
    ok["runner_sha_as_plan"] = bool(sha(RUNNER) == RUNNER_SHA == fu.get("Tools/GWWaveGen/flip52b3/g52b3_run.py"))
    ok["chain_sha_as_plan"] = bool(sha(CHAIN) == CHAIN_SHA == fu.get("Tools/GWWaveGen/flip52b3/g52b3_chain.py"))
    ok["g49_restart_sha"] = bool(sha(G49R) == G49R_SHA)
    src, counts = chain_source()
    compile(src, "patched chain", "exec")
    ok["chain_patch_counts"] = bool(all(v == 1 for v in counts.values()) and src.count(SELF) == 1 and src.count('"hyrun"') == 1)
    ok["runner_single_setframe"] = bool(open(RUNNER, encoding="utf-8").read().count("hou.setFrame(") == 1)
    # 2. hook order with a fake hou (export stubbed)
    fh = FakeHou()
    hk = ExportHook(fh, dict(frames=[1057, 1060]), SIM_DIR + "/hooktest", SIM_DIR + "/hooktest/hook.json")
    seq = []
    hk.export = lambda f: (seq.append(("export", f, fh.calls[-1][1] if fh.calls else None)), hk.done.add(f))
    hk.install()
    for f in (1057, 1058, 1059, 1060):
        fh.setFrame(f)
    hk.finish()
    ok["hook_order"] = bool([s[1] for s in seq] == [1057, 1058, 1059, 1060] and all(s[2] == s[1] for s in seq)
                            and [c[1] for c in fh.calls] == [1057, 1058, 1059, 1060] and fh.setFrame.__func__ is FakeHou.setFrame)
    det["hook_seq"] = seq
    # 3. export cfg + its precheck
    try:
        c, c0 = export_cfg()
        ok["export_cfg_precheck"] = bool(c["precheck"]["ok"])
        det["export_precheck"] = dict(reason=c["precheck"].get("reason"), replaced=list((c["precheck"].get("replaced") or {}).keys()),
                                      changed=c["precheck"]["export"]["source_diff"]["changed"])
    except SystemExit as e:
        ok["export_cfg_precheck"] = False
        det["export_cfg_error"] = str(e)
    # 4. launch cfgs: design sha16 as frozen, only the derived keys differ
    for opt in ("C2ID", "C2"):
        L, d = launch_cfg(opt, for_smoke=True)
        ok["launch_%s_design_frozen" % opt] = bool(L["precheck"]["checks"]["design_cfg_sha16_as_frozen"] and L["precheck"]["checks"]["design_precheck_ok"])
        ok["launch_%s_only_derived" % opt] = bool(L["precheck"]["checks"]["only_derived_keys_differ"])
        ok["launch_%s_override_wall_taper_0" % opt] = bool(L["precheck"]["checks"]["overrides_as_registered"] and float(L["parms"]["wall_taper_m"]) == 0.0
                                                           and float(d["parms"]["wall_taper_m"]) == 15.0 and float(L["parms"]["s_off"]) == STILL_OFFSET)
        det["launch_%s" % opt] = L["precheck"]["checks"]
    # 4b. operations: watchdog, entry guard, chain driver, main's json on errors (fakes; no process is started)
    ok.update(ops_selftest())
    # 5. the scene code (x55_nest_build): target assembly on synthetic files, band mirror, VEX text
    sys.path.insert(0, HERE)
    import x55_nest_build as XB
    st = XB.selftest_numpy(SIM_DIR + "/xb_selftest")
    ok["scene_numpy_selftest"] = bool(st["ok"])
    det["scene_numpy_selftest"] = st
    # 6. GN rules on synthetic hf data (identity passes, a +3 % volume / 0.6 m edge offset fails)
    ok.update(gn_synthetic(np))
    # 7. no temp paths in what a launch writes
    L, _ = launch_cfg("C2", for_smoke=True)
    ok["no_temp_paths"] = bool(no_temp(L) and no_temp(export_spec(C)))
    # 8. the export round trip with a fake hou (DFG-2B-V's grids, face-sampled velocity) -> the target SOP's own assembly
    rt = fake_export_roundtrip(np, XB)
    ok.update({"roundtrip_" + k: v for k, v in rt["checks"].items()})
    det["roundtrip"] = rt["detail"]
    # 9. the patched chain's own gate(), dry: the export cfg passes; a nest launch cfg is refused until the nest build check exists
    g = chain_gate_dry()
    ok["chain_gate_export_passes"] = bool(g["export"] == [])
    # the nest gate passes exactly when the nest build check is all_ok for the hip on disk; otherwise it refuses for build / scene reasons
    # only (state-independent form of the former 'waits for the build check', which assumed no build check existed yet)
    bc_now = jtry(NEST_BUILD_CHECK) or {}
    bc_good = bool(bc_now.get("all_ok") and os.path.exists(NEST_HIP) and bc_now.get("hip_sha256") == sha(NEST_HIP))
    ok["chain_gate_nest_consistent"] = bool((g["nest"] == []) if bc_good else (g["nest"] and all(("build" in r or "scene" in r or "場面" in r)
                                                                                                 for r in g["nest"])))
    det["chain_gate"] = dict(g, build_check_good=bc_good)
    # 10. the fix (2026-10-19): per-option initial state, linear bands launched, the calibration rule, the particle validation
    ok.update(fix_selftest(np, XB, det))
    res = dict(ok=bool(all(ok.values())), checks=ok, detail=det)
    jdump(res, SIM_DIR + "/selftest_f55_nest.json")
    return final(dict(ok=res["ok"], step="selftest", checks=ok, file=rel(SIM_DIR + "/selftest_f55_nest.json")))


def fix_selftest(np, XB, det):
    """the 2026-10-19 fix without Houdini: launch parms per option (F2 / F7 / calibration), the calibration rule on synthetic surfaces, the
    particle validation on a synthetic file, the smoke's activity / tracking rules on synthetic rows, the amendment text."""
    out = {}
    L1, _ = launch_cfg("C2ID", for_smoke=True)
    L2, _ = launch_cfg("C2", for_smoke=True)
    p1, p2 = L1["parms"], L2["parms"]
    out["fix_C2ID_from_parent_particles"] = bool(p1["init_src"] == 1.0 and p1["pinit_npz"] == PINIT_NPZ and p1["init_lvl_m"] == 0.0
                                                 and p1["band_lin"] == 1.0 and L1["precheck"]["checks"].get("init_as_registered"))
    cs = calib_state()
    out["fix_C2_lattice_with_calibrated_step"] = bool(p2["init_src"] == 0.0 and p2["pinit_npz"] == "" and p2["band_lin"] == 1.0
                                                      and L2["precheck"]["checks"].get("init_as_registered")
                                                      and p2["init_lvl_m"] == (float(cs["step_m"]) if cs["ok"] else 0.0))
    out["fix_derived_keys_cover_new_parms"] = bool(all(("parms." + k) in DERIVED_KEYS for k in ("band_lin", "init_src", "init_lvl_m", "pinit_npz"))
                                                   and set(LAUNCH_PARMS) <= set(n for n, _, _ in XB.NEST_PARMS)
                                                   and set(LAUNCH_STR_PARMS) <= set(n for n, _, _ in XB.NEST_STR_PARMS))
    # the full precheck asks for the particles (C2ID) / the calibration (C2) when not for the smoke
    Lf1, _ = launch_cfg("C2ID")
    Lf2, _ = launch_cfg("C2")
    out["fix_precheck_needs_pinit_and_calib"] = bool("pinit_ok" in Lf1["precheck"]["checks"] and "calib_ok" in Lf2["precheck"]["checks"]
                                                     and Lf1["precheck"]["checks"]["pinit_ok"] == pinit_state()["ok"]
                                                     and Lf2["precheck"]["checks"]["calib_ok"] == calib_state()["ok"])
    # the calibration rule on synthetic nest surfaces (the C2 eta layout: 0.5 m cells): settled at s_off + 0.05 -> step 0.05; unsettled fails
    base = SIM_DIR + "/calibtest"
    if os.path.isdir(base):
        shutil.rmtree(guard(base))
    files_a, files_b, files_c = {}, {}, {}
    xs0, zs0 = 180.25, 0.25
    for k, f in enumerate(range(CKPT, CKPT + CALIB_FRAMES + 1)):
        lv = STILL_OFFSET + 0.05 * (1.0 - math.exp(-k / 4.0))
        e = np.full((120, 352), lv, np.float32)
        e[:, :8] = lv + 0.3                                    # the x band (outside the region) does not count
        meta = json.dumps(dict(x0=xs0, dx=0.5, z0=zs0, dz=0.5))
        pa = guard(base + "/a/eta_%05d.npz" % f)
        np.savez_compressed(pa, eta=e, meta=meta)
        files_a[f] = pa
        pb = guard(base + "/b/eta_%05d.npz" % f)
        np.savez_compressed(pb, eta=(e + 0.006 * k).astype(np.float32), meta=meta)       # still drifting: 0.066 m over the last 12 frames
        files_b[f] = pb
        # code review B1: C2's own reading offset at creation (-0.04 m vs the parent's 0.076 m) must NOT enter the step
        pc_ = guard(base + "/c/eta_%05d.npz" % f)
        np.savez_compressed(pc_, eta=(e - 0.04).astype(np.float32), meta=meta)
        files_c[f] = pc_
    A = calib_analyse(np, files_a, STILL_OFFSET, frames_expected=CALIB_FRAMES + 1)
    B = calib_analyse(np, files_b, STILL_OFFSET, frames_expected=CALIB_FRAMES + 1)
    Cc = calib_analyse(np, files_c, STILL_OFFSET, frames_expected=CALIB_FRAMES + 1)
    exp_a = float(np.mean([0.05 * (1.0 - math.exp(-k / 4.0)) for k in range(CALIB_FRAMES + 1)][-CALIB_RULES["last_n"]:]))
    out["calib_rule_step"] = bool(A["ok"] and abs(A["step_m"] - exp_a) < 1e-6 and A["settle_m"] < 0.01 and abs(A["offset_at_creation_m"]) < 1e-6)
    out["calib_step_is_rise_after_creation"] = bool(Cc["ok"] and abs(Cc["step_m"] - exp_a) < 1e-6 and abs(Cc["offset_at_creation_m"] + 0.04) < 1e-6
                                                    and abs(Cc["step_vs_parent_hf_m"] - (exp_a - 0.04)) < 1e-6
                                                    and abs(Cc["step_interior_m"] - exp_a) < 1e-6
                                                    and all(abs(v - exp_a) < 1e-6 for v in Cc["step_per_20m_x"].values())
                                                    and Cc["slope_last24_m_per_s"] is not None and abs(Cc["slope_last24_m_per_s"]) < 0.01
                                                    and abs(B["slope_last24_m_per_s"] - 0.006 * FPS) < 1e-3
                                                    and "frames - L(1056) (the rise after creation" in CALIB_RULE_TEXT
                                                    and "(the still parent's hf level)" not in CALIB_RULE_TEXT)
    out["calib_rule_refuses_unsettled"] = bool(not B["ok"] and B["checks"]["settled"] is False)
    det["calib_synthetic"] = dict(step=A.get("step_m"), expected=exp_a, settle=A.get("settle_m"), unsettled_settle=B.get("settle_m"),
                                  offset_case=dict(step=Cc.get("step_m"), offset_at_creation=Cc.get("offset_at_creation_m"),
                                                   step_vs_parent_hf=Cc.get("step_vs_parent_hf_m"), slope=Cc.get("slope_last24_m_per_s")),
                                  drifting_slope=B.get("slope_last24_m_per_s"))
    cc = calib_cfg()
    out["calib_cfg_still_target"] = bool(cc["parms"]["tgt_dir"] == CALIB_TGT and cc["parms"]["rep_on"] == 0.0 and cc["parms"]["init_lvl_m"] == 0.0
                                         and cc["parms"]["init_src"] == 0.0 and cc["parms"]["dp"] == 0.25 and cc["parms"]["band_lin"] == 1.0
                                         and cc["frames"] == [CKPT, CKPT + CALIB_FRAMES] and no_temp(cc) and under(cc["out_dir"], B55))
    # the still synthetic parent: the nest's water rule fills to level 0 (SDF zero at s_off), v = 0
    sd = base + "/still"
    XB.write_synth_export(sd, frames=(CKPT, CKPT + 1), full_at=CKPT, fields_fn=lambda f: XB.still_fields(STILL_OFFSET))
    nsx = {}
    exec(compile(XB.TARGET_PURE, "TARGET_PURE", "exec"), nsx)
    Rs = nsx["f55_pair"](sd, CKPT + 0.5, 62.0)
    es = Rs["A"]["eta"][0][1:-1, 1:-1]                          # frame 1056 carries the whole box nb (later frames only the bands)
    eb = Rs["B"]["eta"]
    xb_ = eb[1][0] + eb[2][0] * np.arange(eb[0].shape[1]); zb_ = eb[1][2] + eb[2][2] * np.arange(eb[0].shape[0])
    band = ((xb_[None, :] <= 199.0) | (zb_[:, None] >= 41.0)) & (xb_[None, :] >= 178.0) & (zb_[:, None] >= 0.0) & (zb_[:, None] <= 62.0)
    out["calib_still_target"] = bool(Rs["ok"] == 1 and np.allclose(es, STILL_OFFSET, atol=1e-5) and np.allclose(eb[0][band], STILL_OFFSET, atol=1e-5)
                                     and all(float(np.abs(Rs[t][k][0]).max()) == 0.0 for t in ("A", "B") for k in ("vx", "vy", "vz")))
    # the particle validation on a synthetic, consistent file (particles below the synthetic SDF zero, velocity = the synthetic field)
    F = XB.synth_fields(CKPT)
    rng = np.random.RandomState(9)
    # a parent-like particle block: x 180-230, lateral 0-20, a 0.5 m lattice (jittered 0.05 m) from 4 m below to its particle level
    # (the SDF zero - s_off), as the parent's particles fill a column
    gx, gz = np.meshgrid(180.25 + 0.5 * np.arange(100), 0.25 + 0.5 * np.arange(40), indexing="ij")
    gx, gz = gx.ravel(), gz.ravel()
    cols = []
    for k in range(8):
        y_ = F["eta"](gx, gz) - STILL_OFFSET - 0.05 - 0.5 * k - 0.25 * ((gx * 7 + gz * 3) % 1.0)
        cols.append(np.stack([gx, y_, gz], 1))
    pl = np.concatenate(cols, 0) + rng.uniform(-0.05, 0.05, (len(gx) * 8, 3))
    n = len(pl)
    x, y, z = pl[:, 0], pl[:, 1], pl[:, 2]
    vv = np.stack([F["vx"](x, y, z), F["vy"](x, y, z), F["vz"](x, y, z)], 1)
    xd = base + "/pinit_x"
    XB.write_synth_export(xd, frames=(CKPT,), full_at=CKPT)
    pp = guard(base + "/p_synth_valid.npz")
    meta = dict(frame=CKPT, o_parent=[0.5, 0.5, 0.5], n_total=n + 7, n_box=n)
    np.savez_compressed(pp, P_h=(pl + 0.5).astype(np.float32), v=vv.astype(np.float32), meta=np.array(json.dumps(meta)))
    hy = dict(n_box=n, sha256=sha(pp), ckpt_sha256="b7" * 32, ckpt_sha256_after="b7" * 32)
    v_ok = validate_pinit(np, pp, hy=hy, x_path=xd + "/x_%05d.npz" % CKPT, v_box=n / 8.9, n_total_expect=n + 7)
    v_ck = validate_pinit(np, pp, hy=dict(hy, ckpt_sha256_after="c0" * 32), x_path=xd + "/x_%05d.npz" % CKPT, v_box=n / 8.9, n_total_expect=n + 7)
    pb = guard(base + "/p_synth_bad.npz")
    np.savez_compressed(pb, P_h=(pl + np.array([0.5, 6.0, 0.5])).astype(np.float32), v=vv.astype(np.float32), meta=np.array(json.dumps(meta)))
    v_bad = validate_pinit(np, pb, hy=dict(n_box=n, sha256=sha(pb), ckpt_sha256="b7" * 32, ckpt_sha256_after="b7" * 32),
                           x_path=xd + "/x_%05d.npz" % CKPT, v_box=n / 8.9, n_total_expect=n + 7)
    out["pinit_validation_passes_consistent"] = bool(v_ok["ok"])
    out["pinit_validation_refuses_changed_ckpt_copy"] = bool(not v_ck["ok"] and v_ck["checks"]["ckpt_copy_unchanged"] is False
                                                             and all(v for k, v in v_ck["checks"].items() if k != "ckpt_copy_unchanged"))
    out["pinit_validation_refuses_shifted"] = bool(not v_bad["ok"] and v_bad["checks"]["level_vs_parent_sdf"] is False)
    det["pinit_synthetic"] = dict(ok=v_ok.get("checks"), above=v_ok.get("above_sdf_zero_frac"), dv=v_ok.get("mean_abs_dv_grid"),
                                  bad_above=v_bad.get("above_sdf_zero_frac"))
    out["pinit_box_is_C2ID"] = bool(pinit_box() == dict(x0=180.0, Lx=176.0, W=60.0))
    # the smoke rules (x55_nest_build): activity and tracking on synthetic rows
    rows_ok = [dict(frame=CKPT + 1 + i, band_cand=900, band_kills=3, band_kills_np=3, band_np0=10000, band_tgt=1, ss_n=1 if i % 2 else 2)
               for i in range(24)]
    rows_dead = [dict(r, band_cand=0, band_kills=0, band_kills_np=0) for r in rows_ok]
    rows_1sub_nokill = [dict(r, band_kills=0, band_kills_np=0) if r["ss_n"] == 1 else r for r in rows_ok]
    # code review M1: kills on only a few frames still prove band_kill runs (F7: the nest starts as the parent's own particles)
    rows_sparse = [dict(r, band_kills=0, band_kills_np=0) if r["frame"] != CKPT + 6 else r for r in rows_ok]
    rows_no1sub = [dict(r, ss_n=2, band_kills=(3 if r["frame"] == CKPT + 9 else 0), band_kills_np=(3 if r["frame"] == CKPT + 9 else 0)) for r in rows_ok]
    rows_no1sub_dead = [dict(r, band_kills=0, band_kills_np=0) for r in rows_no1sub]
    # physics review M1: a frame whose target failed (band_tgt 0) or whose counters are missing fails
    rows_tgt0 = [dict(r, band_tgt=0) if r["frame"] == CKPT + 12 else r for r in rows_ok]
    rows_notgt = [{k: v for k, v in r.items() if k != "band_tgt"} for r in rows_ok]
    sa = XB.surface_activity
    out["smoke_activity_rule"] = bool(sa(rows_ok)["ok"] and not sa(rows_dead)["ok"] and not sa(rows_1sub_nokill)["ok"] and not sa([])["ok"]
                                      and sa(rows_sparse)["ok"] and sa(rows_sparse)["frames_with_kills"] == 1
                                      and sa(rows_no1sub)["ok"] and not sa(rows_no1sub_dead)["ok"]
                                      and not sa(rows_tgt0)["ok"] and not sa(rows_notgt)["ok"]
                                      and sa(rows_ok)["kills_counter_agrees_report_only"] is True
                                      and sa([dict(r, band_kills=2) for r in rows_ok])["ok"]
                                      and sa([dict(r, band_kills=2) for r in rows_ok])["kills_counter_agrees_report_only"] is False)
    vp = 86966.0 + 20.0 * np.arange(25.0) + 3.0 * np.sin(np.arange(25.0))
    out["smoke_tracking_rule"] = bool(XB.volume_tracking(vp, vp * 1.001)["ok"] and not XB.volume_tracking(vp, np.full(25, 87000.0) + 0.1 * np.arange(25.0))["ok"])
    # the amendment draft text names the fix and the superseded registration
    rec = amendment_record()
    fx = rec.get("fix_2026_10_19_after_C2ID") or {}
    out["amendment_names_fix"] = bool(fx.get("supersedes", {}).get("code_sha256") == PREVIOUS_REGISTRATION["code_sha256"] and "F1" in fx and "F2" in fx
                                      and "F7" in fx and rec["code_sha256"] != PREVIOUS_REGISTRATION["code_sha256"] and no_temp(rec))
    # review fixes in the registered text: C2's lattice AND band water rule shifted by init_lvl_m (physics B1); the step = the rise after
    # creation, the reading offset reported (code B1 / physics M5); the activity rule as the smoke applies it (code M1, physics M1)
    out["amendment_names_review_fixes"] = bool("lattice AND the band water rule" in rec["init"] and "offset_at_creation_m" in rec["reading_note"]
                                               and "not by its reading offset" in rec["reading_note"] and "physics review M5" in rec["reading_note"]
                                               and "kills > 0 summed over the" in fx["F1"] and "band_tgt" in fx["F1"]
                                               and "rise of the nest's level after creation" in fx["F7"]
                                               and "prefix_build_C2ID_20261019" in fx["diagnosis"])
    out["steps_known"] = bool(all(s in STEPS for s in ("pinit", "calib")) and NEED_OPTION.get("pinit") == "C2" and NEED_OPTION.get("calib") == "C2")
    return out


def ops_selftest():
    """watchdog / entry guard / chain driver / json-on-error with fakes (files only under _scratch/sim_nest/ops)."""
    out = {}
    base = SIM_DIR + "/ops"
    if os.path.isdir(base):
        shutil.rmtree(guard(base))
    rd = base + "/run"
    os.makedirs(rd, exist_ok=True)
    # watchdog: 2 low polls -> STOP with the marker; brake -> STOP; only its own STOP is removed
    seq = [5.0, 2.5, 2.9, 2.0]
    wd = NestWatch(rd, commit=lambda: seq.pop(0) if seq else 5.0, brake=base + "/no_brake")
    r1, r2, r3 = wd.tick(), wd.tick(), wd.tick()
    out["watch_commit_two_polls"] = bool(r1 is None and r2 is None and r3 == "commit" and os.path.exists(rd + "/STOP")
                                         and WATCH_MARK in open(rd + "/STOP", encoding="utf-8").read() and abs(wd.min_free - 2.5) < 1e-12)
    out["watch_clears_only_own_stop"] = bool(clear_own_stop(rd) and not os.path.exists(rd + "/STOP"))
    with open(rd + "/STOP", "w", encoding="utf-8") as fh:
        fh.write("stopped by a person\n")
    out["watch_keeps_foreign_stop"] = bool(not clear_own_stop(rd) and os.path.exists(rd + "/STOP"))
    os.remove(rd + "/STOP")
    open(base + "/brake", "w").close()
    wb = NestWatch(rd, commit=lambda: 10.0, brake=base + "/brake")
    out["watch_brake"] = bool(wb.tick() == "brake" and WATCH_MARK in open(rd + "/STOP", encoding="utf-8").read())
    clear_own_stop(rd)
    # entry guard: our own process tree never counts; another pipeline process / low commit refuses; a free machine passes on 2 polls
    me, pp = os.getpid(), os.getppid()
    mine = [(me, pp, "python.exe", "py -3.10 -B f55_nest.py export"), (pp, 1, "py.exe", "py -3.10 -B f55_nest.py export")]
    other = [(99991, 1, "python.exe", "py -3.10 g52b3_chain.py x.json"), (99992, 1, "hython.exe", "hython g52b3_run.py c.json")]
    nosleep = lambda s: None
    need, dneed = need_of("C2ID")
    g_free = entry_guard("t", "C2ID", wait_min=0.0, scan=lambda: list(mine), commit=lambda: need + 1, disk=lambda: dneed + 1, sleep=nosleep)
    g_ok2 = entry_guard("t", "C2ID", wait_min=1.0, scan=lambda: list(mine), commit=lambda: need + 1, disk=lambda: dneed + 1, sleep=nosleep)
    g_busy = entry_guard("t", "C2ID", wait_min=0.0, scan=lambda: mine + other, commit=lambda: need + 1, disk=lambda: dneed + 1, sleep=nosleep)
    g_mem = entry_guard("t", "C2ID", wait_min=0.0, scan=lambda: list(mine), commit=lambda: need - 0.1, disk=lambda: dneed + 1, sleep=nosleep)
    g_scan = entry_guard("t", "C2ID", wait_min=0.0, scan=lambda: None, commit=lambda: need + 1, disk=lambda: dneed + 1, sleep=nosleep)
    out["guard_needs_two_polls"] = bool(not g_free["ok"] and g_ok2["ok"])
    out["guard_refuses_other_pipeline_and_hython"] = bool(not g_busy["ok"] and "pipeline busy" in g_busy["why"] and "hython" in g_busy["why"])
    out["guard_refuses_low_commit"] = bool(not g_mem["ok"] and "free commit" in g_mem["why"])
    out["guard_refuses_failed_scan"] = bool(not g_scan["ok"] and "scan failed" in g_scan["why"])
    out["guard_own_tree_excluded"] = bool(busy_scan(mine)["pipeline"] == [] and busy_scan(mine + other)["hython"] == [99992])
    out["guard_needs_from_plan"] = bool(abs(need_of("C2")[0] - 11.462502) < 1e-6 and abs(need_of("C2ID")[0] - 8.182244) < 1e-6
                                        and need_of("export") == need_of("C2"))
    # chain driver: absent -> launch; max_hours stop -> resume (cap 2); crash -> resume (cap 2); complete -> done; a foreign STOP stops
    script = [("max_hours", 1200), ("crash", 1300), ("done", F_END)]

    def fake_launch(wd):
        kind, fd = script.pop(0)
        with open(rd + "/chain.log", "a", encoding="utf-8") as fh:
            fh.write("2026-10-19 00:00:00 chain start T\n")
            fh.write("2026-10-19 00:00:01 T chunk 1057 ckpt_every 48 done to %d stopped %s wall 1\n" % (fd, "None" if kind == "done" else "wall_limit"))
            if kind == "max_hours":
                fh.write("2026-10-19 00:00:02 max_hours exceeded (1.0 h > 1.0 h); stop\n")
            fh.write("2026-10-19 00:00:03 chain end T elapsed_h 0.1\n")
        jdump(dict(f_end_done=fd), rd + "/run_c%05d.json" % (1057 + len(script)))
        return 0
    logs = []
    st, hist = drive_chain("nest", "x.json", "F55T_ops_selftest_rid", F_END, logs.append, "C2ID", launch=fake_launch, sleep=nosleep, rd=rd)
    out["chain_driver_resumes"] = bool(st["complete"] and len(hist) == 3 and st["resumes_max_hours"] == 1 and st["resumes_crash"] == 1
                                       and st["stop"] is None)
    rd2 = base + "/run2"
    os.makedirs(rd2, exist_ok=True)
    with open(rd2 + "/STOP", "w", encoding="utf-8") as fh:
        fh.write("stopped by a person\n")
    st2, hist2 = drive_chain("nest", "x.json", "F55T_ops_selftest_rid2", F_END, logs.append, "C2ID", launch=lambda wd: 0, sleep=nosleep, rd=rd2)
    out["chain_driver_foreign_stop"] = bool(not st2["complete"] and not hist2 and "STOP" in str(st2["stop"]))
    # main: an error inside a step still prints one json line with ok false
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = main(["run", "BAD_OPTION"])                 # raises SystemExit("run C2ID | C2") inside the step
    lines = [ln for ln in buf.getvalue().splitlines() if ln.startswith("{")]
    out["main_json_on_error"] = bool(rc == 2 and lines and json.loads(lines[-1]).get("ok") is False and "C2ID" in json.loads(lines[-1]).get("why", ""))
    return out


class _FVol:
    """a fake hou.Volume on a regular grid (Houdini coordinates) holding fn(plan x, plan up, plan lat)."""

    def __init__(self, np, name, p0_h, res, fn, o):
        self.np, self.name, self.p0, self.res, self.fn, self.o = np, name, p0_h, res, fn, o

    def resolution(self):
        return tuple(self.res)

    def indexToPos(self, ijk):
        return tuple(self.p0[a] + ijk[a] * 1.0 for a in range(3))

    def attribValue(self, nm):
        return self.name

    def allVoxelsAsString(self):
        np = self.np
        xs = self.p0[0] - self.o[0] + np.arange(self.res[0]); ys = self.p0[1] - self.o[1] + np.arange(self.res[1])
        zs = self.p0[2] - self.o[2] + np.arange(self.res[2])
        Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
        return np.ascontiguousarray(self.fn(X, Y, Z), dtype=np.float32).tobytes()


class _FGeo:
    def __init__(self, prims):
        self._p = prims

    def prims(self):
        return self._p


class _FNode:
    def __init__(self, geo):
        self._g = geo

    def geometry(self):
        return self._g


class _FHou:
    def __init__(self, nodes):
        self.nodes, self.calls = nodes, []

    def node(self, p):
        return self.nodes[p]

    def setFrame(self, f):
        self.calls.append(int(f))


def fake_export_roundtrip(np, XB):
    """export_frame + ExportHook on fake volumes of the parent's exact grids (surface cells, vel.x / vel.y / vel.z faces, o = 0.5) holding the
    synthetic analytic fields of x55_nest_build.synth_fields; the files are then assembled by the target SOP's own code (TARGET_PURE)."""
    out_dir = SIM_DIR + "/roundtrip"
    for p in glob.glob(out_dir + "/x_*.npz"):
        os.remove(p)
    spec = export_spec()
    o = spec["o"]
    grids = {"surface": ((0.5, -20.5, 0.5), (412, 38, 140)), "vel.x": ((0.0, -20.5, 0.5), (413, 38, 140)),
             "vel.y": ((0.5, -21.0, 0.5), (412, 39, 140)), "vel.z": ((0.5, -20.5, 0.0), (412, 38, 141))}
    key = {"surface": "s", "vel.x": "vx", "vel.y": "vy", "vel.z": "vz"}
    state = {}

    def make(f):
        F = XB.synth_fields(f)
        vols = {nm: _FVol(np, nm, tuple(p0[a] + o[a] for a in range(3)), res, F[key[nm]], o) for nm, (p0, res) in grids.items()}
        state["hou"].nodes = {NODE_SURF: _FNode(_FGeo([vols["surface"]])), NODE_VEL: _FNode(_FGeo([vols["vel.x"], vols["vel.y"], vols["vel.z"]]))}
    fh = _FHou({})
    state["hou"] = fh
    spec_c = dict(spec, boxes=dict(spec["boxes"], **spec["boxes_ckpt_extra"]))
    make(1056)
    export_frame(fh, spec_c, 1056, out_dir)                     # hyckpt's call (frame 1056, with the whole nest box)
    # the runner's order: setFrame(f) moves the scene to frame f (make(f)); the hooked setFrame(f + 1) first exports frame f
    fh2 = _FHou({})
    state["hou"] = fh2
    hk = ExportHook(fh2, dict(spec, frames=[1057, 1058]), out_dir, out_dir + "/hook_test.json").install()
    for f in (1057, 1058):
        fh2.setFrame(f)
        make(f)
    hk.finish()
    ns = {}
    exec(compile(XB.TARGET_PURE, "TARGET_PURE", "exec"), ns)
    ck, det = {}, {}
    files = sorted(os.path.basename(p) for p in glob.glob(out_dir + "/x_*.npz"))
    ck["files"] = bool(files == ["x_01056.npz", "x_01057.npz", "x_01058.npz"])
    R = ns["f55_pair"](out_dir, 1057.5, 62.0)
    R0 = ns["f55_pair"](out_dir, 1056.0, 62.0)
    errs = {}
    for tag, f, U in (("a", 1057, R["A"]), ("b", 1058, R["B"]), ("init", 1056, R0["B"])):
        F = XB.synth_fields(f)
        for k in ("s", "vx", "vy", "vz"):
            arr, p0, d = U[k]
            arr = arr[1:-1, 1:-1, 1:-1]                         # the data cells (OUT_TARGET adds one ghost cell on every side)
            q0 = [p0[i] + d[i] for i in range(3)]
            xs = q0[0] + d[0] * np.arange(arr.shape[2]); ys = q0[1] + d[1] * np.arange(arr.shape[1]); zs = q0[2] + d[2] * np.arange(arr.shape[0])
            Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
            m = ((X <= 199.0) | (Z >= 41.0)) if tag != "init" else np.ones(X.shape, bool)
            ref = F[k](X, Y, Z)
            errs["%s_%s" % (tag, k)] = float(np.abs(arr[m] - ref[m]).max() / max(1.0, float(np.abs(ref[m]).max())))
        e, pe, de = U["eta"]
        e = e[1:-1, 1:-1]
        xs = pe[0] + de[0] * (1 + np.arange(e.shape[1])); zs = pe[2] + de[2] * (1 + np.arange(e.shape[0]))
        Xe, Ze = np.meshgrid(xs, zs)
        m = ((Xe <= 199.0) | (Ze >= 41.0)) if tag != "init" else np.ones(Xe.shape, bool)
        errs["%s_eta" % tag] = float(np.abs(e[m] - F["eta"](Xe, Ze)[m]).max())
        det["%s_p0" % tag] = {k: [U[k][1][i] + U[k][2][i] for i in range(3)] for k in ("s", "vx", "vy", "vz")}     # first data cell
    ck["values"] = bool(all(v < (1e-5 if k.endswith("_s") or k.endswith("_eta") else 2e-3) for k, v in errs.items()))
    ck["face_grids_kept"] = bool(abs(det["a_p0"]["vx"][0] - 178.0) < 1e-9 and abs(det["a_p0"]["s"][0] - 178.5) < 1e-9
                                 and abs(det["a_p0"]["vy"][1] + 21.0) < 1e-9 and abs(det["a_p0"]["vz"][2]) < 1e-9)
    ck["init_full_box"] = bool(R0["ok"] == 1 and R0["fa"] == R0["fb"] == 1056.0 and det["init_p0"]["s"][0] <= 180.0
                               and R0["B"]["s"][0].shape[2] >= 176)
    ck["hook_frames"] = bool(sorted(hk.done) == [1057, 1058] and fh2.calls == [1057, 1058] and not hk.errors)
    det["errors"] = errs
    det["files"] = files
    return dict(checks=ck, detail=det)


def chain_gate_dry():
    """the patched chain's gate() executed alone (its top level, which would create folders and launch, is not run)."""
    import ast
    import types
    src, _ = chain_source()
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "gate"]
    for p in (TOOLS + "/flip46", T49, T52B3):
        if p not in sys.path:
            sys.path.insert(0, p)
    import g52b3_common as GCC
    out = {}
    c, _ = export_cfg()
    ns = dict(cfg=c, GC=GCC, os=os, json=json)
    exec(compile(ast.Module(body=fn, type_ignores=[]), CHAIN + " [gate only]", "exec"), ns)
    out["export"] = ns["gate"]()
    L, _ = launch_cfg("C2ID", for_smoke=True)
    L["precheck"]["ok"] = True                    # the gate's own scene / build-check / table / plan items are what is tested here
    shim = types.SimpleNamespace(BUILD_CHECK=NEST_BUILD_CHECK, HIP=NEST_HIP, sha256_file=GCC.sha256_file, REPO=GCC.REPO)
    ns = dict(cfg=L, GC=shim, os=os, json=json)
    exec(compile(ast.Module(body=fn, type_ignores=[]), CHAIN + " [gate only]", "exec"), ns)
    out["nest"] = ns["gate"]()
    return out


def gn_synthetic(np):
    """GN2 / GN3 arithmetic on synthetic frames (column volume, edge rms) without files."""
    out = {}
    meta = dict(x0=180.5, dx=1.0, z0=0.5, dz=1.0)
    xs = 180.5 + np.arange(176); ys = 0.5 + np.arange(60)
    bed = lambda x, y: np.broadcast_to(-(19.0 - np.maximum(x - 160.25, 0.0) / 10.0), np.broadcast(x, y).shape)
    e = np.broadcast_to(0.3 * np.sin(xs / 7.0)[None, :], (60, 176)).copy()
    v0, nx, ny = column_volume(np, e, meta, bed)
    ana = float(np.clip(e - bed(xs[None, :], ys[:, None]), 0, None).sum())
    out["gn3_column_volume_rule"] = bool(abs(v0 - ana) < 1e-9 and nx == 176 and ny == 60)
    v1, _, _ = column_volume(np, e + 0.02 * (e - bed(xs[None, :], ys[:, None])), meta, bed)
    out["gn3_detects_2pct"] = bool(abs(v1 / v0 - 1.0 - 0.02) < 1e-9)
    xq, yq = edge_cells()
    out["gn2_edge_cells"] = bool(len(xq) == 2 * 45 + 2 * 161 - 2 * 2 and np.all(xq >= 195.0) and np.all(yq <= 45.0))
    a = eta_at(np, e, meta, xq, yq)
    b = eta_at(np, e + 0.6, meta, xq, yq)
    out["gn2_bilinear_identity"] = bool(np.allclose(a, np.interp(xq, xs, e[0]), atol=1e-12))
    out["gn2_offset_fails"] = bool(abs(float(np.sqrt(np.mean((b - a) ** 2))) - 0.6) < 1e-9 and 0.6 > GN_TOL["gn2_frac"] * 8.046846)
    return out


# ====================================================================== main
STEPS = ("export", "pinit", "calib", "run", "gates", "analyse", "amend", "status", "selftest", "standin", "archive")


def main(argv):
    global WAIT_MIN
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if not argv:
        print(__doc__)
        return 1
    cmd = argv[0]
    pos, o = opts(argv[1:])
    sim = "simulate" in o
    if cmd == "hyrun":                       # hython modes and the chain keep their own exit codes (the frozen chain reads them)
        hy_run(pos[0])
        return 0
    if cmd == "hyckpt":
        hy_ckpt(pos[0])
        return 0
    if cmd == "hypart":
        hy_part(pos[0])
        return 0
    if cmd == "chain":
        return cmd_chain(pos[0], pos[1])
    if cmd not in STEPS:
        print(__doc__)
        return 1
    try:
        WAIT_MIN = float(o.get("wait-min", WAIT_MIN))
    except ValueError:
        pass
    try:                                     # every step ends with ONE json line with "ok", also when it stops on an error (code review M5)
        if cmd == "export":
            return cmd_export(sim)
        if cmd == "pinit":
            return cmd_pinit(sim)
        if cmd == "calib":
            return cmd_calib(pos[0] if pos else "C2", sim)
        if cmd == "run":
            return cmd_run(pos[0] if pos else "C2ID", sim)
        if cmd == "gates":
            return cmd_gates(pos[0] if pos else "C2ID", sim)
        if cmd == "analyse":
            return cmd_analyse(pos[0] if pos else "C2", sim)
        if cmd == "amend":
            return cmd_amend("write" in o)
        if cmd == "status":
            return cmd_status()
        if cmd == "selftest":
            return selftest()
        if cmd == "standin":
            return cmd_standin("hollow" in o)
        if cmd == "archive":
            return cmd_archive(pos[0] if pos else "", sim)
    except KeyboardInterrupt:
        raise
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            raise
        final(dict(ok=False, step=cmd, why=str(e.code)[:800]))
        return 2
    except Exception as e:
        import traceback
        final(dict(ok=False, step=cmd, why="%s: %s" % (type(e).__name__, str(e)[:600]), traceback=traceback.format_exc()[-1500:]))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
