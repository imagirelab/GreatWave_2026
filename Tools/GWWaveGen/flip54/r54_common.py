# -*- coding: utf-8 -*-
"""FLIP54 R54: the 2D RESOLUTION CHECK of the K54 strips (K0 and K4 rerun at dp 0.25 m; everything else identical). Constants and
helpers shared by the R54 tools (numpy only at import; read by hython and by py -3.10 -B).

2026-10-18 written new (Claude, FLIP54 builder R). Why: the user's priority is that the wave does not curl a BIG hollow; the K54 screen
(dp 0.5 m) found NONE_PASS (concave beds thicken the lip, but the hood forms only after the face passes vertical). Before the supervisor
decides on 0.25 m particles for the 3D wave, this check asks whether the 2D hollow itself depends on the particle size: FLIP47 E1a halved
the grid and got +37 % cavity with Hb unchanged [measured]. The reading rule is frozen in Unity/Build/FLIP54/r54/plan/plan_R54_frozen.json
(r54_plan.py) BEFORE any R54 run.

The K54 tools (g54_common, g54_pcfg, g54_plan, g54_run, g54_chain, g54_mkcopy, x54_check, g54_ana) are NOT edited: the R54 tools import
them and change, IN MEMORY of their own process only, the particle size g54_common.DP (0.5 -> 0.25 m; the grid follows through the
unchanged gridscale 2.0 -> 0.5 m) and the scene-check output path:
  r54_common.py  this file: places, the two arms, the K54 reference runs, the run id, the time / memory model, the reading thresholds
  r54_pcfg.py    the R54 cfg = g54_pcfg.make(arm) at dp 0.25 + R54 names; precheck = K54's items + "identical to the K54 cfg except the
                 dp-tied keys" + the chain-time estimate (replaces K54's one-launch estimate)
  r54_xcheck.py  (hython) x54_check.py at dp 0.25 into Unity/Build/FLIP54/r54/_check/build_check_r54.json (K54's build_check54.json untouched)
  r54_chain.py   g54_chain.py with its scene-check gate pointed at build_check_r54.json (it still launches the unchanged g54_run.py)
  r54_plan.py    the frozen plan (quantities, reading rule, references with sha256); refuses once an R54 run exists
  r54_ana.py     the comparison dp 0.5 vs dp 0.25 (g54_ana's measure, unchanged, gives every number), verdict, sheet, mp4
Tags in comments and records: [measured] FLIP records, [computed] formulas / screens, [chosen], [registered].
"""
import os, sys, math, json, glob, contextlib

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g54_common as C          # noqa: E402  (K54 constants; patched only inside patched_dp())

REPO = C.REPO
B54 = C.B54
R54 = B54 + "/r54"
PLAN_DIR = R54 + "/plan"
PLAN = PLAN_DIR + "/plan_R54_frozen.json"
PLAN_REL = "Unity/Build/FLIP54/r54/plan/plan_R54_frozen.json"
OUT_ROOT = "r54/strips"                    # cfg out_root (relative to B54): runs land in Unity/Build/FLIP54/r54/strips/<run_id>
RUNS_ROOT = B54 + "/" + OUT_ROOT
READY = RUNS_ROOT + "/ready"
VERDICT_DIR = R54 + "/verdict"
CHECK_DIR = R54 + "/_check"
BUILD_CHECK = CHECK_DIR + "/build_check_r54.json"   # r54_xcheck.py writes it; r54_chain.py gates on it
SCRATCH = C.SCRATCH
TMP_HOUDINI = C.TMP_HOUDINI

DP = 0.25                                  # the R54 particle size [chosen by the task]
DP_REF = 0.5                               # = g54_common.DP, the K54 particle size
GRIDSCALE = 2.0                            # unchanged (g54_pcfg.parms_for): grid 0.5 m at dp 0.25
ARMS = ("K0", "K4")                        # the K54 control and the K54 report-only best-score3 arm [chosen by the task]
ARM_ORDER = ("K0", "K4")

# K54 references (dp 0.5): read only
K54_RUNMAP = C.VERDICT_DIR + "/runmap.json"
K54_VERDICT = C.VERDICT_DIR + "/verdict_K54.json"
K54_CALIB = C.CALIB
K54_PLAN = C.PLAN
K54_STATUS = C.LOG_DIR + "/auto_K54_status.txt"
K54_TOOLS = ("g54_common.py", "g54_pcfg.py", "g54_plan.py", "g54_run.py", "g54_chain.py", "g54_mkcopy.py", "x54_check.py", "g54_ana.py")
R54_TOOLS = ("r54_common.py", "r54_pcfg.py", "r54_xcheck.py", "r54_chain.py", "r54_plan.py", "r54_ana.py")

# execution (not physics) [chosen]
MAX_HOURS = 5.0                            # per chain invocation (K54: 0.75 h for a 5.5-6.6 min strip); the estimate below is ~1.2-1.6 h
RESUMES = 2                                # launcher-level resumes of one strip (watchdog stop, chain timeout, max_hours with a projection that fits)
COMMIT_MIN_GB = 12.0                       # free commit before every chain launch / resume (task)
COMMIT_LOW_GB = 4.0                        # watchdog: free commit below this on 2 polls -> the run's STOP file (the chain stops before its next launch)

# reading thresholds [registered in the plan]
GAIN = 0.25                                # +25 % (task)
TIE = 0.10                                 # K4 vs K0 order: |K4 - K0| / max(|K4|, |K0|) < 0.10 is a tie (no order) [chosen]
GAIN_KEYS = ("air_max_pre", "hood_max")    # cavity air (max before touchdown), max hood before touchdown (median over judged k2-k4)
ORDER_KEYS = ("hood_max", "air_max_pre", "hood78", "best_score3")

# time / memory model [computed from measured records]
E1A_FACTOR = (1600.4 / (2907327 * 719)) / (265.3 / (719949 * 729))
#  = 1.515: s per particle-frame at dp 0.25 / at dp 0.5 in FLIP47 E1a_full (same scene, quasi-2D, grid halved; substeps 1-3 -> 1-6) [measured,
#    Unity/Build/FLIP47/runs/runs.jsonl]; R54 halves the grid in all three directions (the 6 m half width is kept), so particles x8 and the
#    per-particle cost x1.5
E1A_FACTOR_HI = 2.0                        # upper bound: the per-particle cost doubles (substeps x2, no other saving) [chosen]
LAUNCH_OVERHEAD_S = 150.0                  # per extra 1740-s launch: scene + checkpoint load and the frames redone after the last checkpoint [guess]
RSS_NOTE = ("hython peak working set ~5-6 GB: K54 dp 0.5 (0.37 M particles) 5.03 GB, FLIP47 E1a_full dp 0.25 (2.9 M) 5.01 GB, FLIP49 PROBE025 dp 0.25 "
            "(8.4 M, 3D) 6.4-8.0 GB [measured]; the task's 12 GB free-commit gate leaves >= 2x margin")


def tag(v):
    return C.tag(v)


def jload(p):
    return C.jload(p)


def sha(p):
    return C.sha256_file(p) if os.path.exists(p) else None


@contextlib.contextmanager
def patched_dp(dp=DP):
    """g54_common.DP := dp inside the block (this process only; g54_pcfg.parms_for / precheck and x54_check read it)."""
    old = C.DP
    C.DP = float(dp)
    try:
        yield C
    finally:
        C.DP = old


def run_id(arm, H, T=None):
    """R54_<arm>_<bed>_T.._H.._dp0p25 (the K54 name with the K54 prefix and the dp swapped)."""
    rid = C.run_id(arm, H, T)
    assert rid.startswith("K54_") and rid.endswith("_dp0p5"), rid
    return "R54_" + rid[4:-len("_dp0p5")] + "_dp" + tag(DP)


def run_dir(rid):
    return RUNS_ROOT + "/" + rid


def cfg_path(rid):
    return READY + "/" + rid + ".json"


def runs_exist():
    out = []
    for d in sorted(glob.glob(RUNS_ROOT + "/R54_*")):
        if os.path.isdir(d) and (glob.glob(d + "/run_c*.json") or os.path.exists(d + "/chain.log")):
            out.append(os.path.basename(d))
    return out


def plan_sha_ok():
    sp = PLAN + ".sha256"
    if not (os.path.exists(PLAN) and os.path.exists(sp)):
        return False
    return open(sp, encoding="utf8").read().split()[0] == C.sha256_file(PLAN)


def guard_out(path):
    return C.guard_out(path)


def jdump(o, p):
    C.jdump(o, p)


# ------------------------------------------------------------------ the K54 references
def k54_ref(arm):
    """the K54 dp-0.5 strip of an arm: run dir, ready cfg, analysis, run records (read only)."""
    rm = jload(K54_RUNMAP) or {}
    rd = rm.get(arm)
    out = dict(arm=arm, run_dir=rd, ok=False)
    if not rd or not os.path.isdir(rd):
        out["why"] = "no K54 run for %s in %s" % (arm, K54_RUNMAP)
        return out
    rid = os.path.basename(rd)
    out["run_id"] = rid
    out["ready_cfg"] = C.READY + "/" + rid + ".json"
    out["analysis"] = rd + "/k54/" + "k54_ana.json"
    recs = [jload(p) or {} for p in sorted(glob.glob(rd + "/run_c*.json"))]
    out["f_end_done"] = max([int(r.get("f_end_done") or 0) for r in recs] or [0])
    out["wall_total_s"] = float(sum(float(r.get("wall_total_s") or 0.0) for r in recs))
    out["particles_max"] = max([int(r.get("particles_max") or 0) for r in recs] or [0])
    out["rss_peak_gb"] = max([float(r.get("rss_peak_gb") or 0.0) for r in recs] or [0.0])
    out["stops"] = [os.path.basename(p) for p in glob.glob(rd + "/STOPPED_*.txt")]
    cfg = jload(out["ready_cfg"]) or {}
    out["f_end"] = int(cfg.get("f_end") or 0)
    out["particles_model"] = int(((cfg.get("precheck") or {}).get("particles_model")) or 0)
    out["H"] = (cfg.get("wave") or {}).get("H_m")
    out["T"] = (cfg.get("wave") or {}).get("T_s")
    out["analysis_sha256"] = sha(out["analysis"])
    out["ready_cfg_sha256"] = sha(out["ready_cfg"])
    out["ok"] = bool(cfg and out["f_end"] and out["f_end_done"] >= out["f_end"] and not out["stops"] and out["analysis_sha256"])
    return out


def wall_model(arm, n_model, frames):
    """[computed] R54 hython time of one strip from the measured K54 rate of the same arm (s per particle-frame at its max particle count) x
    the FLIP47 E1a dp-0.25 / dp-0.5 per-particle factor x the R54 model particles x the K54 growth x frames, + launch overheads."""
    ref = k54_ref(arm)
    if not ref.get("particles_max") or not ref.get("f_end_done"):
        return dict(error="no K54 record for %s" % arm)
    rate = ref["wall_total_s"] / (ref["particles_max"] * ref["f_end_done"])
    growth = ref["particles_max"] / max(1, ref["particles_model"])
    pmax = n_model * growth
    est = rate * E1A_FACTOR * pmax * frames
    hi = rate * E1A_FACTOR_HI * pmax * frames
    nl = max(1, int(math.ceil(est / (0.85 * 1740.0))))
    nl_hi = max(1, int(math.ceil(hi / (0.85 * 1740.0))))
    return dict(k54_rate_s_per_particle_frame=rate, k54_wall_s=ref["wall_total_s"], k54_particles_max=ref["particles_max"], growth=growth,
                particles_max_model=pmax, e1a_factor=E1A_FACTOR, compute_s=est, launches=nl, wall_est_s=est + (nl - 1) * LAUNCH_OVERHEAD_S,
                wall_hi_s=hi + (nl_hi - 1) * LAUNCH_OVERHEAD_S, launches_hi=nl_hi,
                rule="K54 %s rate %.4g s/(particle frame) [measured] x E1a factor %.3f [measured] x %d model particles x growth %.3f [measured K54] x %d "
                     "frames + %d x %.0f s launch overhead; high: factor %.1f" % (arm, rate, E1A_FACTOR, n_model, growth, frames, nl - 1, LAUNCH_OVERHEAD_S,
                                                                                 E1A_FACTOR_HI))


# ------------------------------------------------------------------ free commit (Windows GlobalMemoryStatusEx)
def commit_gb():
    """(free commit GiB, commit limit GiB) of the machine, or (None, None)."""
    try:
        import ctypes
        from ctypes import wintypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", wintypes.DWORD), ("dwMemoryLoad", wintypes.DWORD), ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = MS(); m.dwLength = ctypes.sizeof(MS)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
            return None, None
        return m.ullAvailPageFile / 2.0 ** 30, m.ullTotalPageFile / 2.0 ** 30          # GiB, as Windows reports the 64.8 GB commit limit
    except Exception:
        return None, None


# ------------------------------------------------------------------ the reading rule (pure; r54_ana.py and the launcher's --test-rules)
def rel(v1, v0):
    """(v1 - v0) / |v0|; None when either is missing or v0 is 0."""
    if v1 is None or v0 is None:
        return None
    v0 = float(v0); v1 = float(v1)
    if not (math.isfinite(v0) and math.isfinite(v1)) or abs(v0) < 1e-12:
        return None
    return (v1 - v0) / abs(v0)


def order(k4, k0, tie=TIE):
    """+1 if K4 > K0, -1 if K4 < K0, 0 if a tie (|K4 - K0| / max(|K4|, |K0|) < tie) or missing."""
    if k4 is None or k0 is None:
        return 0
    a, b = float(k4), float(k0)
    m = max(abs(a), abs(b))
    if m < 1e-12 or abs(a - b) / m < tie:
        return 0
    return 1 if a > b else -1


def reading(q, gain=GAIN, tie=TIE, gain_keys=GAIN_KEYS, order_keys=ORDER_KEYS):
    """q[(arm, dp_tag)] = medians dict (dp_tag '0p5' / '0p25') or None. Returns the registered reading (see plan_R54_frozen.json reading_rule)."""
    arms = ("K0", "K4")
    miss = [(a, d) for a in arms for d in ("0p5", "0p25") if not q.get((a, d))]
    if miss:
        return dict(verdict="INCOMPLETE", missing=["%s@%s" % m for m in miss],
                    text="an arm has no measured medians (fewer than 2 judged breakers or not run): no reading")
    g = {k: {a: rel(q[(a, "0p25")].get(k), q[(a, "0p5")].get(k)) for a in arms} for k in gain_keys}
    rule_b = {k: bool(all(g[k][a] is not None and g[k][a] >= gain - 1e-12 for a in arms)) for k in gain_keys}
    rule_a = {a: bool(any(g[k][a] is not None and g[k][a] >= gain - 1e-12 for k in gain_keys)) for a in arms}
    dec = {k: {a: bool(g[k][a] is not None and g[k][a] <= -gain + 1e-12) for a in arms} for k in gain_keys}
    od = {}
    for k in order_keys:
        o5 = order(q[("K4", "0p5")].get(k), q[("K0", "0p5")].get(k), tie)
        o25 = order(q[("K4", "0p25")].get(k), q[("K0", "0p25")].get(k), tie)
        od[k] = dict(order_dp0p5=o5, order_dp0p25=o25, flip=bool(o5 != 0 and o25 != 0 and o5 != o25),
                     emerged=bool(o5 == 0 and o25 != 0), vanished=bool(o5 != 0 and o25 == 0))
    flips = [k for k in order_keys if od[k]["flip"]]
    gains = [k for k in gain_keys if rule_b[k]]
    matters = bool(gains or flips)
    return dict(verdict="RESOLUTION_MATTERS" if matters else "NOT_SHOWN", gains=g, rule_same_quantity_both_arms=rule_b, gain_quantities=gains,
                ordering=od, flips=flips,
                report_rule_any_quantity_per_arm=dict(per_arm=rule_a, would_be=bool(all(rule_a.values()) or flips)),
                report_decreases=dec,
                text=("resolution matters for the hollow: %s" % ("; ".join(["%s >= +%d %% in K0 and K4" % (k, round(gain * 100)) for k in gains] +
                                                                           ["K4-vs-K0 order of %s flips" % k for k in flips])))
                if matters else ("not shown: no hollow quantity grew >= +%d %% in both arms and no K4-vs-K0 order flipped (report only)" % round(gain * 100)))
