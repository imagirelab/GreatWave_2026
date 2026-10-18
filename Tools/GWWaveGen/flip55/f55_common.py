# -*- coding: utf-8 -*-
"""FLIP55: the 3D RESOLUTION run of the hero wave DFG-2B-V, PREPARED 2026-10-19 (Claude) after R54 found RESOLUTION_MATTERS in 2D.
Constants, options, the memory / time / disk model and the machine probes shared by the FLIP55 tools (numpy only; py -3.10 -B).
NOTHING here starts Houdini. The run itself is reserved for after the SUPERVISOR's approval (user decisions Q57 / Q64): the launcher
G:/research/Wave Simulation/_tools/auto_F55.py does nothing until Unity/Build/FLIP55/_logs/APPROVED_BY_USER.txt exists (written only by the main
session from the user's own words).

Why: R54 (2D strips, half width 6 m, T 9.33 s, H 7 m) halved the particles 0.5 -> 0.25 m with everything else identical and the cavity air under
the hood grew +174 % (straight 1:10) / +113 % (K4), hood max +59 % / +71 %: RESOLUTION_MATTERS by the frozen R54 rule [measured,
Unity/Build/FLIP54/r54/verdict/verdict_R54.json]. The 3D hero DFG-2B-V ran at dp 0.5 m, so its small hollow is very likely resolution-limited.

Options (costed in the FLIP55 design, 2026-10-19; the plan freezes them):
  C2    RECOMMENDED: dp 0.25 m ONE-WAY NEST of group 1 inside DFG-2B-V (box x 180-356 m, y 0-60 m, z -19..17 m; relaxation bands x 180-195 and
        y 45-60 toward the parent's fields; started at the parent's own checkpoint v.1056 (t 43.96 s); the 0.5 m identity nest C2ID first, gates
        GN1-GN3). Its Houdini-side tools (parent field export, nest scene, reseeding, relax-to-parent target) are NOT written: they are the
        1.5-2.5 days of engineering scheduled AFTER approval. The cfg / precheck / gates / reading are frozen now; the launcher refuses C2 until
        the nest tools exist and are registered by an amendment (see NEST_TOOLS).
  A375  FALLBACK, runnable now with ZERO new Houdini code: dp 0.375 m, the full DFG-2B-V tank, the frozen flip52b3 runner (g52b3_run.py) and a
        path-only copy of its chain (f55_chain.py). Resolution-tied consequences (all registered, see A375_TIED): the voxel 0.75 m does not divide
        W 140 m -> W 140.25 m (side band chi over 45.25 m instead of 45 m; the table target is clamped at y 140 m) and Lx 412 -> 412.5 m (dry beach);
        19 m / 0.375 m = 50.67 particle layers is not whole, so with the box bottom at -19 m the seeded still level would sit +0.125 m above the
        band target (a level step at the inlet band) -> the box bottom zb is set to -19.125 m (= -51 x 0.375) so the layers tile 0 .. -19 m as at
        0.5 m (the bed is the bed formula with h0 19 m, unchanged; the box floor is 0.125 m lower under the flat bed, inside the floor pad);
        records (hf / r2 / r3 / r4 / r5) on the 0.75 m grid.
Tags: [measured] FLIP / machine records, [computed] formulas from measured anchors, [guess] judgement, [chosen] design choices.
"""
import os, sys, json, math, glob, hashlib, time, copy

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
T52B3 = REPO + "/Tools/GWWaveGen/flip52b3"
for _p in (HERE, T52B3):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                     # noqa: E402

B55 = REPO + "/Unity/Build/FLIP55"
B52B3 = REPO + "/Unity/Build/FLIP52B3"
PLAN_DIR = B55 + "/plan"
PLAN = PLAN_DIR + "/plan_F55_frozen.json"
PLAN_REL = "Unity/Build/FLIP55/plan/plan_F55_frozen.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
PRECHECK = PLAN_DIR + "/precheck_F55.json"
BASELINE = PLAN_DIR + "/hollow_baseline_DFGBV.json"
RUNS_ROOT = B55 + "/runs"
READY = RUNS_ROOT + "/ready"
LOG_DIR = B55 + "/_logs"
SCRATCH = B55 + "/_scratch"
TMP_HOUDINI = B55 + "/tmp_houdini"
APPROVAL = LOG_DIR + "/APPROVED_BY_USER.txt"
STATUS = LOG_DIR + "/auto_F55_status.txt"
STOPF = LOG_DIR + "/auto_F55_STOP"
AUTO = "G:/research/Wave Simulation/_tools/auto_F55.py"

# ------------------------------------------------------------------ the parent DFG-2B-V (frozen, read only)
DFGBV_RID = "DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"
DFGBV_RUN = B52B3 + "/runs/" + DFGBV_RID
DFGBV_READY = B52B3 + "/runs/ready/" + DFGBV_RID + ".json"
DFGBV_HERO_RUN = B52B3 + "/hero/runs/DFGBVr_D19B_xf272p25_in5c0p6_tp3_dp0p5_c1152_t125_long"
DFGBV_PV53 = REPO + "/Unity/Build/FLIP53/pv53/%s/pv53_%s.json" % (DFGBV_RID, DFGBV_RID)
DFGB4_PLAN = B52B3 + "/plan/plan_DFGB4_frozen.json"
DFGB4_PLAN_SHA256 = "9e9e6709126ba8cff7c71b054bdf198e418574404c946568ee79110c85f20b8a"      # its .sha256 [measured 2026-10-19]
DFGB4_BUILD_CHECK = B52B3 + "/_logs/build_check52b3.json"
DFGB4_HIP = REPO + "/Houdini/FLIP52B3/g52b3_tank.hiplc"
DFGB4_HIP_SHA256 = "9fa07e66f930e92316278e29ed0b3ea3269c5fee044ca4c3a5d297ee898412c5"       # byte copy of DFG-2B-E's scene [measured]
R54_VERDICT = REPO + "/Unity/Build/FLIP54/r54/verdict/verdict_R54.json"
R0_DIR = REPO + "/Unity/Build/FLIP54/r0"
R0_TOOL = R0_DIR + "/r0_hollow.py"
R0_JSON = R0_DIR + "/r0_hollow.json"
R0_RULE = R0_DIR + "/r0_rule_registered.json"
PV53 = REPO + "/Tools/GWWaveGen/flip53/pv53.py"

# frozen tools used unchanged (sha checked by the plan / launcher)
FROZEN_USED = ("Tools/GWWaveGen/flip52b3/g52b3_run.py", "Tools/GWWaveGen/flip52b3/g52b3_chain.py", "Tools/GWWaveGen/flip52b3/g52b3_common.py",
               "Tools/GWWaveGen/flip52b3/g52b3_ana.py", "Tools/GWWaveGen/flip52b3/g52b3_video.py", "Tools/GWWaveGen/flip52b3/g52b3_table.py",
               "Tools/GWWaveGen/flip53/pv53.py", "Unity/Build/FLIP54/r0/r0_hollow.py", "Unity/Build/FLIP54/r0/r0_rule_registered.json",
               "Tools/GWWaveGen/flip51/e51_metrics.py", "Tools/GWWaveGen/flip46/g46_ckpt.py")
CODE_FILES = ("f55_common.py", "f55_pcfg.py", "f55_mkcopy.py", "f55_chain.py", "f55_ana.py", "f55_hollow.py", "f55_plan.py")

# ------------------------------------------------------------------ frames
FPS = 24
T_F1 = 63.0
GROUP_WIN = (-8.0, 6.0)
FOCI = (63.0, 91.0, 119.0)


def frames_for(t0, t1):
    return int(round((t1 - t0) * FPS)) + 1


F_END_G1 = frames_for(0.0, FOCI[0] + GROUP_WIN[1])        # 1657 (t 69 s)
F_END_FULL = frames_for(0.0, FOCI[-1] + GROUP_WIN[1])     # 3001 (t 125 s)
NEST_CKPT = 1056                                          # the parent's checkpoint v.1056 (t 43.96 s) [measured: DFGBV ckpt/v.1056.sim]
NEST_F0 = NEST_CKPT + 1

# ------------------------------------------------------------------ options
RID = {"A375": "F55A_D19B_xf272p25_in5c0p6_tp3_dp0p375",
       "C2": "F55N_D19B_x180y60_dp0p25_c1056",
       "C2ID": "F55N_D19B_x180y60_dp0p5_c1056",
       "C2P": "F55P_DFGBV_c1056_export"}
OPTIONS = {
    "A375": dict(role="fallback (runnable now, zero new Houdini code)", kind="full_tank", dp=0.375, zb=-19.125, x0=0.0, Lx=412.0, W=140.0,
                 stages=("g1", "full"), runner="Tools/GWWaveGen/flip52b3/g52b3_run.py (frozen, unchanged)",
                 chain="Tools/GWWaveGen/flip55/f55_chain.py (generated: g52b3_chain.py with its Houdini temp folder moved to FLIP55)"),
    "C2": dict(role="RECOMMENDED (needs the nest tools: post-approval engineering)", kind="nest", dp=0.25, zb=-19.0, x0=180.0, Lx=176.0, W=60.0,
               relax_x=(180.0, 195.0), relax_y=(45.0, 60.0), f_start=NEST_F0, f_end=F_END_G1, baseline="C2ID", stages=("g1",)),
    "C2ID": dict(role="the 0.5 m identity nest (gate GN1, baseline of C2)", kind="nest", dp=0.5, zb=-19.0, x0=180.0, Lx=176.0, W=60.0,
                 relax_x=(180.0, 195.0), relax_y=(45.0, 60.0), f_start=NEST_F0, f_end=F_END_G1, stages=("g1",)),
}
# the C2 nest tools (names registered now; written after approval; an amendment AM-F55-NEST must register their sha256 before any nest run)
NEST_TOOLS = ("Tools/GWWaveGen/flip55/x55_nest_build.py", "Tools/GWWaveGen/flip55/f55_nest.py")
NEST_BUILD_CHECK = LOG_DIR + "/build_check55_nest.json"

# A375: the keys that change with the particle size (everything else in the cfg must equal DFG-2B-V's launched cfg)
A375_TIED = {
    "parms.dp": "0.5 -> 0.375 m (the option)",
    "parms.zb": "-19 -> -19.125 m: particle layers zb + (k + 1/2) dp end exactly at the still level 0 (19 / 0.375 = 50.67 is not whole; with zb -19 the "
                "seeded still level would be +0.125 m above the band target); the bed is the h0 = 19 m formula, unchanged",
    "parms.Hz": "36 -> 36.75 m (rup(17 - zb, 0.75): the box top 17.625 m, air)",
    "parms.Lx": "412 -> 412.5 m (whole 0.75 m voxels; the extra 0.5 m is dry beach beyond the shoreline 350.25 m)",
    "parms.W": "140 -> 140.25 m (whole 0.75 m voxels; the side band's relaxation chi runs over 95-140.25 m (45.25 m, +0.56 %); the table target is "
               "clamped at its y1 = 140 m in the extra 0.25 m)",
    "parms.ox": "0.5 -> 0.375 (g46 box rule: grid faces on the walls)", "parms.oy": "0.5 -> 0.0 (same rule with zb -19.125)",
    "parms.oz": "0.5 -> 0.375 (same rule)", "parms.crop_x1": "= Lx", "level_box": "[0, Lx, 0, W]",
    "box": "the g46 / box48 box at dp 0.375, zb -19.125 (voxel 0.75 m, cells, offsets, floor)",
}
A375_EXEC = {"max_hours": "3.0 -> 6.0 h per chain (execution only: the measured-rate estimate of group 1 is 3.4-4.7 h; a max_hours stop is resumed "
                          "from the last checkpoint by auto_F55)",
             "f_end / t_end_s / records.windows / pstats_frames": "group-1 stage f_end 1657 (t 69 s, window [55, 69] s only); full stage = DFG-2B-V's "
                                                                  "3001 frames and three windows (the same run folder, resumed from the last checkpoint)"}
A375_NAMES = ("run_id", "out_root", "stage", "case", "note", "precheck", "analysis.plan_frozen", "analysis.tool", "analysis.dir_case", "f55")

# ------------------------------------------------------------------ measured anchors
DFGBV_PART_F1 = 5383840               # model = the f1 count [measured, precheck_at_freeze + run.json]
DFGBV_PART_PEAK = 6129890             # chain.log chunk 2017 pts [measured]
DFGBV_GROWTH = DFGBV_PART_PEAK / float(DFGBV_PART_F1)      # 1.1386
DFGBV_RSS_GB = (5.8, 6.38, 6.88, 6.96, 6.72)               # PeakWorkingSet per launch (g46 rss_gb) [measured]; NOT commit (PrivateUsage not logged)
DFGBV_WALL_FULL_S = 2.348 * 3600.0    # chain.log elapsed 2.348 h for 3001 frames incl. relaunch overlap [measured]
DFGBV_WALL_G1_S = 1740.9 + 1742.6 + (F_END_G1 - 1441 + 1) * (1740.2 / (2043 - 1441 + 1))   # chunks 1, 865 and frames 1441-1657 of chunk 1441 [computed]
DFGBV_S_PER_FRAME_NEST_SPAN = 1742.6 / (1524 - 865 + 1)    # 2.64 s / frame around t 36-63 s (incl. r5 surfaces in the window) [measured]
DFGBV_CKPT_GB = 7.2 / 40.0            # 40 checkpoints, 7.2 GB [measured du] -> 0.18 GB at ~6.1 M particles
DFGBV_RECORDS_GB = 1.6                # run folder without ckpt [measured du]
CKPT_B_PER_PARTICLE = DFGBV_CKPT_GB * 1e9 / DFGBV_PART_PEAK          # ~29 B / particle [computed]
R54_PP_FACTOR_HALVING = 1.66          # s per particle-frame at 0.25 / at 0.5 (R54 strips: wall/frame x11.7 for particles x7-8) [measured]
WS_BASE_GB, WS_PER_M_GB = 4.4, 0.42   # working set model WS = 4.4 + 0.42 GB / M particles (fit of the measured 3D runs; the 3000 MB DOP cache is inside) [computed]
WS_PROP_GB_PER_M = 1.135              # pessimistic: WS proportional to particles (6.96 GB / 6.13 M) [computed]
COMMIT_OVER_WS = (1.0, 1.3)           # private commit / working set [guess]
COMMIT_MARGIN_GB = 2.0                # [chosen]
COMMIT_LOW_GB = 3.0                   # watchdog: free commit below this on 2 polls -> the run's STOP file [chosen]
DISK_STOP_GB = 25.0                   # the chain's own G: stop line (cfg disk_stop_free_gb, = DFG-2B-V)
ANCHORS_TEXT = ("DFG-2B-V 0.5 m: 5.38 M particles at f1, 6.13 M peak, PeakWorkingSet 5.8-6.96 GB per launch, 2.348 h for 3001 frames (group 1 ~1.14 h), "
                "40 checkpoints 7.2 GB + records 1.6 GB [measured]; FLIP49 PROBE025 3D dp 0.25: 8.4 M particles 6.4-8.0 GB [measured]; R54 strips "
                "0.5 -> 0.25 m: particles x8.0 (f1) / x7.0 (peak), wall per frame x11.7, per particle x1.66, substeps 1-2 -> 1-6 [measured]")


def tag(v):
    return ("%g" % float(v)).replace(".", "p").replace("-", "m")


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sha(p):
    return sha256_file(p) if os.path.exists(p) else None


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def jtry(p):
    try:
        return jload(p)
    except Exception:
        return None


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if not math.isfinite(v) else round(v, 6)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def guard_out(path):
    o = os.path.abspath(path).replace("\\", "/")
    if not (o.lower() + "/").startswith(B55.lower() + "/"):
        raise SystemExit("output %s is outside Unity/Build/FLIP55; not written" % o)
    os.makedirs(o, exist_ok=True)
    return o


def jdump(o, p):
    guard_out(os.path.dirname(p))
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)


def rel(p):
    p = str(p).replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO + "/") else p


def no_temp_paths(o):
    s = json.dumps(o, ensure_ascii=False, default=str).lower().replace("\\\\", "/").replace("\\", "/")
    return not ("appdata" in s or "/temp/" in s or "/tmp/" in s.replace("tmp_houdini", ""))


def plan_sha_ok():
    sp = PLAN + ".sha256"
    if not (os.path.exists(PLAN) and os.path.exists(sp)):
        return False
    return open(sp, encoding="utf-8").read().split()[0] == sha256_file(PLAN)


def runs_exist():
    """FLIP55 run folders that already hold a chain / run record (the plan refuses to refreeze then)."""
    out = []
    for d in sorted(glob.glob(RUNS_ROOT + "/F55*")):
        if os.path.isdir(d) and (glob.glob(d + "/run_c*.json") or os.path.exists(d + "/chain.log")):
            out.append(os.path.basename(d))
    return out


def amendments():
    out = []
    if os.path.exists(AMENDMENTS):
        for ln in open(AMENDMENTS, encoding="utf-8"):
            if ln.strip():
                out.append(json.loads(ln))
    return out


def nest_tools_state():
    """C2 needs the nest tools AND an amendment 'AM-F55-NEST' whose code_sha256 equals them (written by the main session after the
    engineering and its smoke, before any nest run). Returns dict(ok, missing, amendment, sha_ok)."""
    miss = [p for p in NEST_TOOLS if not os.path.exists(REPO + "/" + p)]
    am = [a for a in amendments() if a.get("id") == "AM-F55-NEST"]
    sha_ok = False
    if am and not miss:
        cs = am[-1].get("code_sha256") or {}
        sha_ok = bool(all(cs.get(p) == sha(REPO + "/" + p) for p in NEST_TOOLS))
    bc = jtry(NEST_BUILD_CHECK) or {}
    return dict(ok=bool(not miss and am and sha_ok and bc.get("all_ok")), missing=miss, amendment=bool(am), sha_ok=sha_ok,
                build_check_all_ok=bool(bc.get("all_ok")), build_check=rel(NEST_BUILD_CHECK))


# ------------------------------------------------------------------ the box and the particle count (numpy, the scene's seeding rule)
def box(dp, x0=0.0, Lx=412.0, W=140.0, zb=-19.0, floor_pad=2):
    """the g46 box rule (flip46 box + flip48 box48): every extent rounded UP to whole voxels (2 dp), offsets o = (vox/2 - origin) mod vox, the
    top at +17 m rounded up, floor pad 2 voxels; offsets and extents must be binary exact."""
    import g52b3_common as GC                    # read only (box48 via g50_common)
    b = GC.box52(float(dp), Lx=float(Lx), W=float(W), x0=float(x0), zb=float(zb), floor_pad=floor_pad)
    return b


def bed_z(x, y):
    import g52b3_common as GC
    return GC.bed_z(x, y, **GC.SPEC_BED)


def count_particles(dp, x0, Lx, W, zb, bed_gap=0.5, eta=0.0):
    """the init_particles rule of the scene (g52_build_tank): columns at x0 + (i + 1/2) dp, (j + 1/2) dp; layers zb + (k + 1/2) dp with
    bed + bed_gap dp <= layer < eta (still water, eta 0). Returns (n, V m^3)."""
    xs = float(x0) + (np.arange(int(round(Lx / dp))) + 0.5) * dp
    ys = (np.arange(int(round(W / dp))) + 0.5) * dp
    n = 0
    for j0 in range(0, len(ys), 64):
        yy = ys[j0:j0 + 64]
        bed = np.broadcast_to(bed_z(xs[None, :], yy[:, None]), (len(yy), len(xs)))
        k_lo = np.ceil((bed + bed_gap * dp - zb) / dp - 0.5 - 1e-9)
        k_hi = np.ceil((eta - zb) / dp - 0.5 - 1e-9)
        n += int(np.maximum(k_hi - np.maximum(k_lo, 0), 0).sum())
    return n, n * dp ** 3


def seeded_still_level(dp, zb):
    """the top of the highest particle layer (centre < 0) on still water: k_hi dp + zb (0.0 when the layers tile 0 .. zb exactly)."""
    k_hi = math.ceil((0.0 - zb) / dp - 0.5 - 1e-9)
    return zb + k_hi * dp


# ------------------------------------------------------------------ the memory / time / disk model [computed from the measured anchors]
def ws_gb(n_peak):
    """(fit, proportional) working set GB at a peak particle count."""
    m = n_peak / 1e6
    return WS_BASE_GB + WS_PER_M_GB * m, WS_PROP_GB_PER_M * m


def commit_need_gb(n_peak):
    """free commit the launcher waits for: 1.3 x the fitted working set + 2 GB margin [computed + chosen]."""
    return COMMIT_OVER_WS[1] * ws_gb(n_peak)[0] + COMMIT_MARGIN_GB


def cost(option, stage="g1"):
    """particles, memory, time, disk of one option / stage."""
    o = OPTIONS[option]
    dp = o["dp"]
    b = box(dp, o["x0"], o["Lx"], o["W"], o["zb"])
    n0, V = count_particles(dp, o["x0"], b["Lx"], b["W"], b["z_bottom"])
    out = dict(option=option, stage=stage, dp=dp, box=dict(x0=b["x0"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], cells=b["cells"],
                                                           vox=b["vox"], ox=b["ox"], oy=b["oy"], oz=b["oz"]),
               particles_model=n0, water_m3=V, seeded_still_level_m=seeded_still_level(dp, b["z_bottom"]))
    if o["kind"] == "full_tank":
        growth = (DFGBV_GROWTH, DFGBV_GROWTH)
        ratio = n0 / float(DFGBV_PART_F1)
        refine = 0.5 / dp
        ppf = (R54_PP_FACTOR_HALVING ** math.log2(refine), R54_PP_FACTOR_HALVING)          # 1.23 (log-interpolated) .. 1.66 (full halving step) [computed]
        base = DFGBV_WALL_G1_S if stage == "g1" else DFGBV_WALL_FULL_S
        t_h = [base * ratio * f * 1.05 / 3600.0 for f in ppf]                            # +5 % for longer checkpoint loads [guess]
        frames = F_END_G1 if stage == "g1" else F_END_FULL
        n_ck = (26 if stage == "g1" else 40)                                             # DFG-2B-V kept 40 for 3001 frames (every 48, then 96) [measured]
        rec_gb = DFGBV_RECORDS_GB * (frames / 3001.0) * (refine ** 2)
        time_rule = ("DFG-2B-V's measured wall (group 1 %.2f h / full %.2f h, incl. relaunch overlap) x particle ratio %.3f x per-particle factor %.2f-%.2f "
                     "(R54 1.66 per halving, log-interpolated to x%.3f refinement .. the full 1.66) x 1.05 [computed]"
                     % (DFGBV_WALL_G1_S / 3600.0, DFGBV_WALL_FULL_S / 3600.0, ratio, ppf[0], ppf[1], refine))
    else:
        growth = (DFGBV_GROWTH, 1.25)                                                   # 1.14 [measured parent] .. 1.25 [guess: breaking inside the nest]
        refine = 0.5 / dp
        frames = (o["f_end"] - o["f_start"] + 1) if stage == "g1" else (F_END_FULL - o["f_start"] + 1)
        ppf = (R54_PP_FACTOR_HALVING ** math.log2(refine), R54_PP_FACTOR_HALVING ** math.log2(refine) * 1.3) if refine > 1 else (1.0, 1.0)
        ratio_pk = n0 * growth[1] / float(DFGBV_PART_PEAK)
        t_nest = [frames * DFGBV_S_PER_FRAME_NEST_SPAN * (n0 * g / float(DFGBV_PART_PEAK)) * f / 3600.0 for g, f in zip(growth, ppf)]
        t_parent = frames * DFGBV_S_PER_FRAME_NEST_SPAN * 1.1 / 3600.0                  # export rerun of the parent 1057 .. f_end (+10 % export I/O) [computed]
        t_h = [t_nest[0], t_nest[1]]
        n_ck = int(math.ceil(frames / 48.0))
        rec_gb = DFGBV_RECORDS_GB * (frames / 3001.0) * (b["Lx"] * b["W"] / (412.0 * 140.0)) * refine ** 2
        out["parent_export_h"] = t_parent
        out["parent_export_gb"] = frames * 2.0e-3                                        # ~2 MB / frame (band fields, 1 m) [computed]
        time_rule = ("frames %d x DFG-2B-V's %.2f s / frame in that span x particle ratio (peak %.3f) x per-particle factor %.2f-%.2f (R54 1.66 per halving; "
                     "upper +30 %% for 3D breaking substeps) [computed]; the parent export rerun adds %.2f h" % (frames, DFGBV_S_PER_FRAME_NEST_SPAN, ratio_pk,
                                                                                                      ppf[0], ppf[1], t_parent))
    n_pk = (n0 * growth[0], n0 * growth[1])
    ws = [ws_gb(n) for n in n_pk]
    out.update(particles_peak=[n_pk[0], n_pk[1]], growth=list(growth),
               ws_fit_gb=[ws[0][0], ws[1][0]], ws_prop_gb=[ws[0][1], ws[1][1]],
               commit_gb=[COMMIT_OVER_WS[0] * ws[0][0], COMMIT_OVER_WS[1] * ws[1][0]],
               commit_need_gb=commit_need_gb(n_pk[1]),
               time_h=t_h, time_rule=time_rule,
               ckpt_gb_each=CKPT_B_PER_PARTICLE * n_pk[1] / 1e9, n_ckpt=n_ck,
               disk_gb=CKPT_B_PER_PARTICLE * n_pk[1] / 1e9 * n_ck + rec_gb + out.get("parent_export_gb", 0.0),
               frames=frames)
    out["disk_need_gb"] = out["disk_gb"] + DISK_STOP_GB
    return out


# ------------------------------------------------------------------ machine probes (read only)
def commit_gb():
    """(free commit GiB, commit limit GiB, free physical GiB) by GlobalMemoryStatusEx, or (None, None, None)."""
    try:
        import ctypes
        from ctypes import wintypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return None, None, None
        return m.ullAvailPageFile / 2.0 ** 30, m.ullTotalPageFile / 2.0 ** 30, m.ullAvailPhys / 2.0 ** 30
    except Exception:
        return None, None, None


def free_disk_gb(drive="G:/"):
    import shutil
    try:
        return shutil.disk_usage(drive).free / 1e9
    except Exception:
        return None


# ------------------------------------------------------------------ the hollow quantities and the reading rule (pure; f55_hollow + auto_F55 --test-rules)
GAIN = 0.25                                  # +25 % (= R54's frozen gain)
GAIN_KEYS = ("air_max", "hood_max")          # = R54's gain keys (air_max_pre, hood_max) measured with the R0 / pv53 ruler on the centre section r2
REPORT_KEYS = ("hood78", "chord_at_hood_max", "lip_at_hood_max", "lip_at_hood_max_m", "eta_at_hood_max", "hi_air", "hi_air_m2", "hi_lip", "hi_lip_m",
               "hi_chord", "best_score3", "best_lip", "n_alive")


def rel_change(v1, v0):
    if v1 is None or v0 is None:
        return None
    v0 = float(v0); v1 = float(v1)
    if not (math.isfinite(v0) and math.isfinite(v1)) or abs(v0) < 1e-12:
        return None
    return (v1 - v0) / abs(v0)


def reading(new, base, groups, gain=GAIN, gain_keys=GAIN_KEYS):
    """new / base: {group n: quantities dict or None}; groups: the judged groups of this stage ((1,) or (1, 2, 3)).
    RESOLUTION_MATTERS_3D iff for at least one gain key: one group -> that group's change >= +25 %; three groups -> the MEDIAN over the groups of
    the change >= +25 % AND >= 2 groups individually >= +25 %. NOT_SHOWN otherwise; INCOMPLETE when a group lacks a value on either side."""
    miss = [n for n in groups if not (new.get(n) and base.get(n) and all(new[n].get(k) is not None and base[n].get(k) is not None for k in gain_keys))]
    if miss:
        return dict(verdict="INCOMPLETE", missing_groups=miss, text="a judged group has no measured gain quantity on one side: no reading")
    ch = {k: {n: rel_change(new[n][k], base[n][k]) for n in groups} for k in gain_keys}
    res = {}
    for k in gain_keys:
        vals = [ch[k][n] for n in groups if ch[k][n] is not None]
        med = float(np.median(vals)) if vals else None
        n_ok = sum(1 for v in vals if v >= gain - 1e-12)
        ok = bool(med is not None and med >= gain - 1e-12 and (len(groups) == 1 or n_ok >= 2))
        res[k] = dict(per_group=ch[k], median=med, n_groups_ge_gain=n_ok, ok=ok, decrease=bool(med is not None and med <= -gain + 1e-12))
    hits = [k for k in gain_keys if res[k]["ok"]]
    rep = {}
    for k in REPORT_KEYS:
        rep[k] = {n: dict(new=(new.get(n) or {}).get(k), base=(base.get(n) or {}).get(k),
                          rel=rel_change((new.get(n) or {}).get(k), (base.get(n) or {}).get(k))) for n in groups}
    return dict(verdict="RESOLUTION_MATTERS_3D" if hits else "NOT_SHOWN", gain_quantities=hits, gains=res, report=rep,
                text=(("resolution matters for the 3D hollow: %s" % "; ".join("%s %+.0f %% (median over groups %s)" % (k, 100 * res[k]["median"], list(groups))
                                                                             for k in hits))
                      if hits else "not shown: neither cavity air nor hood max grew >= +%d %% (report only; a NOT_SHOWN at a 1.33x step does not refute "
                                   "R54's 2x result)" % round(gain * 100)))


def option_of_approval(text):
    """parse the approval file: a line 'OPTION: A375|C2' (required), 'SCOPE: group1|full' (default group1), 'USER_WORDS: ...' (required,
    non-empty: the user's own words the main session wrote it from). Returns (dict or None, why)."""
    if text is None:
        return None, "no approval file"
    kv = {}
    for ln in text.splitlines():
        if ":" in ln:
            k, v = ln.split(":", 1)
            k = k.strip().upper()
            if k in ("OPTION", "SCOPE", "USER_WORDS", "DATE", "BY"):
                kv.setdefault(k, v.strip())
    opt = (kv.get("OPTION") or "").upper()
    if opt not in ("A375", "C2"):
        return None, "OPTION must be A375 or C2 (found %r)" % kv.get("OPTION")
    scope = (kv.get("SCOPE") or "group1").lower()
    if scope not in ("group1", "full"):
        return None, "SCOPE must be group1 or full (found %r)" % kv.get("SCOPE")
    if not kv.get("USER_WORDS"):
        return None, "USER_WORDS (the user's own words) missing"
    return dict(option=opt, scope=scope, user_words=kv["USER_WORDS"], date=kv.get("DATE"), by=kv.get("BY")), None
