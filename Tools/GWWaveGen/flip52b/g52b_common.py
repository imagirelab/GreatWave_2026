# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: constants and helpers shared by the FLIP52B tools (numpy only; read by hython and by py -3.10).
2026-10-17 written new (Claude). Nothing in flip45-flip52 is edited; read only (imported):
  g50_common (flip50): the D19B tank (h0 19 m, 1:10 beach from x 160.25 m, Lx 412 m, half width W 140 m, side band 95-140 m, inlet band 0-100 m),
    the bed path (bed_z, bed_sdf, bed_spec, bed_parms, bed_record), box48, count_particles, process helpers, sf_descriptor.
  g52_common (flip52): the DFG-2 sea (P 28 s, harmonics 3/4/5, equal frequency weights, the plan E X2 direction set, a_sum = DM1A input sum),
    dirset / freqset, the N-layer field names.
The frozen plan is Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json (+ .sha256); g52b_pcfg.py checks every number here against it.

DFG-2B in one line: the DFG-2 sea (unchanged: same frequencies, P, direction set, a_sum) generated in the D19B tank of FLIP50 / plan E (bands as
option D, no exit sponge: the beach absorbs), with the design focus on the 1:10 slope at x_f = X_F (h_f = 19 - (X_F - 160.25)/10 m) at
t = T_F + 28 m s, chosen by flip52b/dfg52b_screen.py (WKB + local 2nd order, calibrated on X2 0.5 m and the D19B plunging breakers).
Coordinates as FLIP48-52: plan x = wave direction (x = 0 upstream wall), y = lateral (y = 0 symmetry plane), z = up (still level 0).
Houdini: up = y, lateral = z, Houdini = plan + o. The FLIP52B scene keeps the FLIP52 node names (G52_SETUP / G52_SIM / G52_READ / G52_SURF) so
that the N-layer VEX of flip52/g52_tanklib.py is used unchanged; it is a separate file Houdini/FLIP52B/g52b_tank.hiplc.
Tags used in comments and records: [measured] [computed] [literature] [guess] [chosen].
2026-10-18 (Claude) AM-DFGB1 (user Q84): the sea variant G52B_SEA=E (energy-matched to DM1A, run ids ...2E_...) added below; with G52B_SEA unset
every name, number and file of the frozen DFG-2B is unchanged.
"""
import os, sys, math, json, hashlib

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS50 = REPO + "/Tools/GWWaveGen/flip50"
TOOLS51 = REPO + "/Tools/GWWaveGen/flip51"
TOOLS52 = REPO + "/Tools/GWWaveGen/flip52"
TOOLS52B = REPO + "/Tools/GWWaveGen/flip52b"
for _p in (TOOLS50, TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)           # appended: flip52b names are found first
import numpy as np                     # noqa: E402
import g50_common as GC50              # noqa: E402  read only
import g50_dirfield as DF50            # noqa: E402  read only (kdisp, DirField)
import g52_common as GC52              # noqa: E402  read only (the DFG-2 sea)
from g50_common import (HY, FFMPEG, G, FPS, is_binary_exact, check_dp, sha256_file, rup, frames_for, t_of_frame,   # noqa: E402,F401
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb,
                        bed_z, bed_grad, bed_sdf, bed_spec, bed_parms, bed_record, bed_kind, bed_formula, is_new, count_particles,
                        sf_tab_string, sf_target, smooth01, tag, NEW_DEFAULTS, box48)

TOOLS = TOOLS52B
B52B = REPO + "/Unity/Build/FLIP52B"
HIP = REPO + "/Houdini/FLIP52B/g52b_tank.hiplc"
HIP_REL = "Houdini/FLIP52B/g52b_tank.hiplc"
PLAN_DIR = B52B + "/plan"
PLAN = PLAN_DIR + "/plan_DFGB_frozen.json"
PLAN_REL = "Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
TABLE_DIR = B52B + "/tables"
LOG_DIR = B52B + "/_logs"
SCREEN_DIR = B52B + "/screens"
BUILD_CHECK = LOG_DIR + "/build_check52b.json"
BUILD_INPUTS = LOG_DIR + "/build_inputs52b.json"
SMOKE_ROOT = B52B + "/smoke"
RUNS_ROOT = B52B + "/runs"
CT_NODE = "/obj/G52_SETUP/CTRL"
SCRATCH_PREFIX = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/_scratch/"

# ------------------------------------------------------------------ the D19B tank (g50_common, unchanged; the plan E X2 cfg parms)
H0 = GC50.H0                   # 19 m
LX = GC50.LX                   # 412 m
W_MAIN = GC50.W_MAIN           # 140 m
W_STRIP = GC50.W_STRIP         # 6 m (build checks only)
ZB = GC50.ZB                   # -19 m
Z_TOP = 17.0                   # box48 top (fixed there) [chosen in FLIP48; DM1A crests 7.9 m + lip]
X_TOE = GC50.X_TOE             # 160.25 m
SLOPE_S = GC50.SLOPE_S         # 1:10
X_SHORE = GC50.X_SHORE         # 350.25 m
SPEC_BED = dict(GC50.SPEC_D19B)
IN_X1 = GC50.IN_X1             # inlet band end 100 m
WALL_TAPER = GC50.WALL_TAPER   # 20 m
SD0 = GC50.SD0                 # 95 m
SD_BAND = GC50.SD_BAND         # 45 m
SD_GEN = GC50.SD_GEN           # 180.25 m
SD_SW = GC50.SD_SW             # 210.25 m
SD_SIGMA = GC50.SD_SIGMA       # 1.41
SD_POW = GC50.SD_POW           # 2
SD_TAPER = GC50.SD_TAPER       # 11.25 m
XA0 = 1.0e9                    # no exit sponge (the beach): abs_on 0 (X2 cfg xa0 1e9)
ABS_SIGMA = 1.41               # unused (X2 cfg value)
ABS_POW = 2.0
RAMP_S = 14.0                  # DFG-2 ramp (2 x the middle period 7 s; = plan E X2)
VOL_X = GC50.VOL_X             # stage A window (110, 400) (AM-D18)
HOLD_X = GC50.HOLD_X
VOL_TAU, VOL_DMAX, VOL_TCAP, VOL_MEASURE = GC50.VOL_TAU, GC50.VOL_DMAX, GC50.VOL_TCAP, GC50.VOL_MEASURE
HOLD_TI = GC50.HOLD_TI
LEVEL_GUARD_M = GC50.LEVEL_GUARD_M
LEVEL_REGIONS_52B = list(GC50.LEVEL_REGIONS_D)
GAUGE_X = GC50.GAUGE_X         # (110, 128, 160)
GAUGE_Y = GC50.GAUGE_Y         # (0.5, 20, 40, 60, 80)
R3_Y = GC50.R3_Y               # 77 m
R4_X = (190.0, 335.0)          # = X2 cfg (converged crest ~255 m, onset up to ~300 m, touchdown)
R4_Y1 = SD0
R4_Z = (-10.0, 16.0)           # = X2 cfg r4 vertical extent
N1_STILL_X = list(GC50.N1_X)   # (110, 340) online still offset window
INTERIOR_X = (110.0, 340.0)    # = plan E N1 window
INTERIOR_Y = 95.0              # = plan E (rows y > 95 m NaN in the metrics)
SCAN_X = (150.0, 300.0)        # = plan E per-period scan window
T_WAVE = 7.0                   # descriptor period = the middle harmonic
TP = 7.0

# ------------------------------------------------------------------ the sea (DFG-2, unchanged) and the DFG-2B focus (chosen by the screen)
P_S = GC52.P_S                 # 28 s
HARMONICS = GC52.HARMONICS     # (3, 4, 5)
A_SUM = GC52.A_SUM             # 6.331240146143423 m = DM1A input sum, NOT enlarged
DSPEC = ("hyb", 60.0, 28.0, 85.0, 17)                # the plan E X2 set (= DFG-2)
X_F = 272.25                   # design focus x (h 7.775 m) [chosen by the screen rule, see plan_DFGB_frozen.json sea.focus]
T_F = 63.0                     # first focus time (s) = ceil(t_full + 3.9 s) [computed by the screen]
N_GROUPS = 3
FOCI = tuple(T_F + P_S * m for m in range(N_GROUPS))
TABLE_X = (0.0, 214.0)
TABLE_Y = (0.0, W_MAIN)
TABLE_DX = 1.0
X_FULL_END = 300.0             # the DirField grid must contain x_f (its phase reference); the table keeps x <= 214 m
FIELDS_LAYER = GC52.FIELDS_LAYER
FIELDS_SHARED = GC52.FIELDS_SHARED
MAX_LAYERS = GC52.MAX_LAYERS
BED_DF = dict(h0=H0, x_toe=X_TOE, s=SLOPE_S, kind="beach")

# ------------------------------------------------------------------ AM-DFGB1 (user Q84, 2026-10-18 ~00:00, Unity/Build/FLIP52B/plan/amendments.jsonl):
# the sea VARIANT, chosen only by the environment variable G52B_SEA (auto_DFGB.py --sea=E sets it for every tool it starts and says so in its
# status lines; nothing else sets it). Unset / "": the frozen DFG-2B sea (a_sum = the DM1A input SUM 6.331240 m), every name and number as frozen.
# "E": the energy-matched DFG-2B sea: every component a_nj x E_SCALE so that sum a^2 at the generation depth h0 19 m = DM1A's (= equal energy
# density 0.5 rho g sum a^2, equal Hm0); P, harmonics, weights, the 34 X2 directions, focus, tank and bands unchanged. Run ids end in 'E'.
SEA = os.environ.get("G52B_SEA", "").strip().upper()
if SEA not in ("", "E"):
    raise SystemExit("G52B_SEA=%r unknown (allowed: unset = the frozen DFG-2B sea, E = the AM-DFGB1 energy-matched sea)" % SEA)
A_SUM_FROZEN = A_SUM
DM1A_N = 30                                     # DM1A cfg dir: n 30, uniform +-80 deg, T 12 s, h0 19 m [measured: Unity/Build/FLIP50/runs/ready/DM1A_...json]
DM1A_AJ = 0.21104133820478077                   # DM1A cfg dir a_j (= a_sum 6.331240146143423 / 30) [measured]
DM1A_SUM_A2 = DM1A_N * DM1A_AJ ** 2             # 1.336153 m^2
SUM_A2_FROZEN = float(A_SUM_FROZEN ** 2 * np.sum(GC52.freqset(P_S, HARMONICS, "eq")[1] ** 2) * np.sum(GC52.dirset(DSPEC)[1] ** 2))   # 0.473081 m^2
E_SCALE = math.sqrt(DM1A_SUM_A2 / SUM_A2_FROZEN)  # 1.680585 [computed]
if SEA == "E":
    A_SUM = A_SUM_FROZEN * E_SCALE              # 10.640186 m [computed, AM-DFGB1]
SET = "DFG2BE" if SEA == "E" else "DFG2B"
TAG = "DFGBE" if SEA == "E" else "DFGB"
AMENDMENT_ID = "AM-DFGB1" if SEA == "E" else None
TABLE_CHECK = PLAN_DIR + "/table_check_%s.json" % TAG
PRECHECK = PLAN_DIR + "/precheck_%s.json" % TAG


def sea_text():
    """the one-line a_sum statement every cfg / label carries (honesty: the energy-matched sea is NOT the DM1A input sum)."""
    if SEA == "E":
        return ("a_sum %.6f m = %.6f x the DM1A input sum: total wave energy (sum a^2 at h0 19 m) = DM1A's (AM-DFGB1, user Q84); "
                "largest component %.4f m < DM1A's %.4f m" % (A_SUM, E_SCALE, float(A_SUM * np.max(np.outer(GC52.freqset(P_S, HARMONICS, "eq")[1],
                                                                                                       GC52.dirset(DSPEC)[1]))), DM1A_AJ))
    return "a_sum = DM1A input sum 6.331240 m, not enlarged"
GROUP_WIN = (-8.0, 6.0)        # per-group window around t_fn (s): convergence at t_fn - 1, onset up to ~4 s later [screen]


def h_of(x):
    return H0 - max(float(x) - X_TOE, 0.0) / SLOPE_S


def dirset(spec=DSPEC):
    return GC52.dirset(spec)


def freqset(P=P_S, ns=HARMONICS, fw="eq"):
    return GC52.freqset(P, ns, fw)


def components(a_sum=A_SUM):
    """the inlet components at the generation depth h0 19 m: a_nj = a_sum wf_n wd_j."""
    om, wf = freqset()
    th, wd = dirset()
    a = float(a_sum) * np.outer(wf, wd)
    k = np.asarray(DF50.kdisp(om, H0), float)
    return dict(P=P_S, harmonics=list(HARMONICS), om=om, wf=wf, k=k, th=th, wd=wd, a=a, a_sum=float(a_sum), h0=H0, x_f=X_F, t_f=T_F)


def kdisp(om, h):
    return np.asarray(DF50.kdisp(om, h), float)


def kp(h=H0):
    return float(kdisp(2 * math.pi / TP, h))


def box52(dp, Lx=LX, W=W_MAIN, x0=0.0, zb=ZB, floor_pad=2, side_pad=0):
    """the D19B box = flip48 box48 (top +17 m), floor pad 2 cells (as FLIP50 / plan E)."""
    return box48(dp, Lx=Lx, W=W, x0=x0, zb=zb, floor_pad=floor_pad, side_pad=side_pad)


# ------------------------------------------------------------------ run ids and paths
def run_id(dp):
    d = ("%.1f" % float(dp)).replace(".", "p")
    if SEA == "E":                                      # AM-DFGB1: the energy-matched sea has its own run ids (suffix E)
        return ("S52BDFGB2E_D19B_xf%s_dp%s" % (tag(X_F), d)) if float(dp) == 1.0 else ("DFGB2E_D19B_xf%s_dp%s" % (tag(X_F), d))
    return ("S52BDFG2_D19B_xf%s_dp%s" % (tag(X_F), d)) if float(dp) == 1.0 else ("DFG2B_D19B_xf%s_dp%s" % (tag(X_F), d))


def run_dir(dp):
    return (SMOKE_ROOT if float(dp) == 1.0 else RUNS_ROOT) + "/" + run_id(dp)


def cfg_path(dp):
    return (SMOKE_ROOT if float(dp) == 1.0 else RUNS_ROOT) + "/ready/" + run_id(dp) + ".json"


# ------------------------------------------------------------------ small helpers
def guard_out(path, allow_scratch=False):
    o = os.path.abspath(path).replace("\\", "/")
    ok = (o.lower() + "/").startswith(B52B.lower() + "/")
    if allow_scratch and o.lower().startswith(SCRATCH_PREFIX.lower()):
        ok = True
    if not ok:
        raise SystemExit("output %s is outside Unity/Build/FLIP52B%s; not written" % (o, " or the scratchpad" if allow_scratch else ""))
    os.makedirs(o, exist_ok=True)
    return o


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if not np.isfinite(v) else round(v, 6)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def jdump(o, p):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)


def jload(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def sha16_json(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False, default=float).encode("utf8")).hexdigest()[:16]


def plan():
    return jload(PLAN)


def plan_sha_ok():
    sp = PLAN + ".sha256"
    if not (os.path.exists(PLAN) and os.path.exists(sp)):
        return False
    return open(sp, encoding="utf8").read().split()[0] == sha256_file(PLAN)


def amendments():
    out = []
    if os.path.exists(AMENDMENTS):
        for ln in open(AMENDMENTS, encoding="utf8"):
            if ln.strip():
                e = json.loads(ln)
                if e.get("plan") == PLAN_REL:
                    out.append(e)
    return out


def plan_sea():
    """the frozen plan's sea; with G52B_SEA=E the a_sum numbers of the REGISTERED amendment AM-DFGB1 replace a_sum_m, a_max_component_m,
    amp_per_freq_m, sum_a2_m2 (everything else stays the frozen plan's). No registered AM-DFGB1 -> SystemExit (no E table / cfg without it)."""
    S = dict(plan()["sea"])
    if SEA == "E":
        am = [a for a in amendments() if a.get("id") == "AM-DFGB1" and isinstance(a.get("sea"), dict)]
        if not am:
            raise SystemExit("G52B_SEA=E but no registered AM-DFGB1 (with 'sea') in %s: register it before any E table check / cfg" % AMENDMENTS)
        S.update({k: am[-1]["sea"][k] for k in ("a_sum_m", "a_max_component_m", "amp_per_freq_m", "sum_a2_m2")})
        S["set"] = am[-1]["sea"].get("set")
    return S


CODE_FILES = ("g52b_common.py", "g52b_table.py", "g52b_mkcopy.py", "g52b_build_tank.py", "x52b_build.py", "g52b_run.py", "g52b_chain.py",
              "g52b_pcfg.py", "g52b_ana.py", "g52b_video.py", "dfg52b_screen.py", "dfg52b_plan.py")


def module_shas():
    out = {}
    for nm in CODE_FILES:
        p = os.path.join(TOOLS52B, nm)
        out["flip52b/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g52_common.py", "g52_table.py", "g52_tanklib.py", "g52_build_tank.py", "g52_run.py", "g52_chain.py", "g52_ana.py"):
        p = os.path.join(TOOLS52, nm)
        out["flip52/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g50_common.py", "g50_table.py", "g50_tanklib.py", "g50_dirfield.py", "g50_ana.py"):
        p = os.path.join(TOOLS50, nm)
        out["flip50/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    p = os.path.join(TOOLS51, "e51_metrics.py")
    out["flip51/e51_metrics.py"] = sha256_file(p)[:16] if os.path.exists(p) else None
    return out


def sf_descriptor(H_ref=None, note=None):
    """cfg['sf']: a LINEAR DESCRIPTOR at the middle harmonic T 7 s and h0 19 m (T, L, c, k for the analysis tools; NOT a forcing table)."""
    om = 2 * math.pi / T_WAVE
    k = float(kdisp(om, H0))
    L = 2 * math.pi / k
    return dict(descriptor=True, kind="linear descriptor at the middle harmonic T 7 s, h0 19 m (NOT a forcing table; sf_on 0)",
                h=H0, T=T_WAVE, H=(None if H_ref is None else float(H_ref)), N=1, k=k, L=L, c=L / T_WAVE, Ubar=0.0, B=[0.0], E=[0.0, 0.0],
                P_sea=P_S, harmonics=list(HARMONICS), note=note or "")
