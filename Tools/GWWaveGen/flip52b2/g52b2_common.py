# -*- coding: utf-8 -*-
"""FLIP52B2 plan DFGB3 (DFG-2B round 2): constants and helpers shared by the FLIP52B2 tools (numpy only; read by hython and by py -3.10).
2026-10-18 written new (Claude) by adapting flip52b/g52b_common.py (DFG-2B / DFG-2B-E, FROZEN, not edited). Nothing in flip45-flip52s2 is edited;
read only (imported): g50_common (flip50) -> g49 / g48 common (hython / ffmpeg paths, dp checks, the bed path: the two-slope bed goes through the
FLIP49 'new term' path pg_hL / pg_s2 = VEX pgon() / rise2() / bedy_pg() / bedgrad_pg(), unchanged since PG12s), g50_dirfield (kdisp, DirField),
g52_common (the DFG-2 sea: P 28 s, harmonics 3/4/5, equal weights, the plan E X2 direction set).
The frozen plan is Unity/Build/FLIP52B2/plan/plan_DFGB3_frozen.json (+ .sha256); g52b2_pcfg.py checks every number here against it.

DFGB3 in one line (round-2 design (c) + (b), chosen 2026-10-18): DFG-2B-E unchanged (energy-matched DFG-2 sea x 1.680585, the 34 X2 directions,
P 28 s, T 9.33 / 7 / 5.6 s, design focus phase reference (272.25, 0) at t = 63 + 28 m s, the D19B tank with its option-D bands, 0.5 m, stage A)
EXCEPT
  (c) the BED (the one physical change): the 1:10 beach from the toe x 160.25 m down to depth 11.5 m at x 235.25 m (= the measured median
      converged x 235.5 m of DFG-2B-E), then a 1:3 face up to a 6 m shelf at x 251.75 m; the shelf runs to the box end x 412 m.
      Because the shelf keeps the water to the end wall, an exit sponge sits on the shelf from x 332 m (80 m; DFG-S's abs_sigma 1.0, abs_pow 2)
      and the stage A volume window ends 5 m before it (110-327 m: 'outside the bands', the layout A rule) - infrastructure, not shaping;
  (b) a generator CALIBRATION (not a force): every table layer n is multiplied by exp(-i phi_n), phi = DFG-2B-E's measured G2f phase errors
      (n3 -0.060788, n4 +0.279111, n5 +0.513994 rad [measured, judge_DFGB.json]); |factor| = 1, so sum a^2 = DM1A's 1.336153 m^2 (Q84) is
      unchanged and the period-mean in-tank power is unchanged. G2f compares the realised wave with the DESIGN target (= DFG-2B-E's table).
Coordinates as FLIP48-52B: plan x = wave direction (x = 0 upstream wall), y = lateral (y = 0 symmetry plane), z = up (still level 0).
Houdini: up = y, lateral = z, Houdini = plan + o. The FLIP52B2 scene keeps the FLIP52 node names (G52_SETUP / G52_SIM / G52_READ / G52_SURF) so
that the N-layer VEX of flip52/g52_tanklib.py is used unchanged; it is a separate file Houdini/FLIP52B2/g52b2_tank.hiplc.
Tags used in comments and records: [measured] [computed] [calibrated] [literature] [guess] [chosen].
"""
import os, sys, math, json, hashlib

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS49 = REPO + "/Tools/GWWaveGen/flip49"
TOOLS50 = REPO + "/Tools/GWWaveGen/flip50"
TOOLS51 = REPO + "/Tools/GWWaveGen/flip51"
TOOLS52 = REPO + "/Tools/GWWaveGen/flip52"
TOOLS52B = REPO + "/Tools/GWWaveGen/flip52b"          # DFG-2B tools: READ ONLY (the compare video source; nothing imported at run time)
TOOLS52B2 = REPO + "/Tools/GWWaveGen/flip52b2"
for _p in (TOOLS50, TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)           # appended: flip52b2 names are found first
import numpy as np                     # noqa: E402
import g50_common as GC50              # noqa: E402  read only
import g50_dirfield as DF50            # noqa: E402  read only (kdisp, DirField, bed_h)
import g52_common as GC52              # noqa: E402  read only (the DFG-2 sea)
from g50_common import (HY, FFMPEG, G, FPS, is_binary_exact, check_dp, sha256_file, rup, frames_for, t_of_frame,   # noqa: E402,F401
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb,
                        bed_z, bed_grad, bed_sdf, bed_spec, bed_parms, bed_record, bed_kind, bed_formula, is_new, count_particles,
                        sf_tab_string, sf_target, smooth01, tag, NEW_DEFAULTS, box48)
import g49_common as GC49              # noqa: E402  read only (edge_x, foot_x)

TOOLS = TOOLS52B2
B52B2 = REPO + "/Unity/Build/FLIP52B2"
HIP = REPO + "/Houdini/FLIP52B2/g52b2_tank.hiplc"
HIP_REL = "Houdini/FLIP52B2/g52b2_tank.hiplc"
PLAN_DIR = B52B2 + "/plan"
PLAN = PLAN_DIR + "/plan_DFGB3_frozen.json"
PLAN_REL = "Unity/Build/FLIP52B2/plan/plan_DFGB3_frozen.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
TABLE_DIR = B52B2 + "/tables"
LOG_DIR = B52B2 + "/_logs"
DIAG_DIR = B52B2 + "/diag"
BUILD_CHECK = LOG_DIR + "/build_check52b2.json"
BUILD_INPUTS = LOG_DIR + "/build_inputs52b2.json"
RUNS_ROOT = B52B2 + "/runs"
CT_NODE = "/obj/G52_SETUP/CTRL"
SCRATCH_PREFIX = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B2/_scratch/"
SET = "DFGB3"                          # table / cfg set name (starts with 'DFG': pv53 reads the run as FLIP52 family, <run>/g52/judge_DFG.json)
TAG = "DFGB3"
TABLE_CHECK = PLAN_DIR + "/table_check_DFGB3.json"
PRECHECK = PLAN_DIR + "/precheck_DFGB3.json"

# ------------------------------------------------------------------ DFG-2B-E (frozen, read only): the parent run, its plan, table and results
DFGB_PLAN = REPO + "/Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json"
DFGB_AMEND = REPO + "/Unity/Build/FLIP52B/plan/amendments.jsonl"
DFGBE_RUN = REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5"
DFGBE_CFG = DFGBE_RUN + "/cfg.json"
DFGBE_JUDGE = DFGBE_RUN + "/g52b/judge_DFGB.json"
DFGBE_COEQ = DFGBE_RUN + "/g52b/coequal_DFGB.json"
DFGBE_PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json"
DFGBE_TABLE = REPO + "/Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz"
DFGBE_TABLE_CONTENT = "d40220b3cb7fd7bd538ab7b9582c7e61ebc0b2902730670f36dcb6db3ade5ffc"     # AM-DFGB1a G1 [measured]
DM1A_TABLE = REPO + "/Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz"
DM1A_CFG = REPO + "/Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json"

# ------------------------------------------------------------------ the D19B tank (g50_common, unchanged; = DFG-2B-E)
H0 = GC50.H0                   # 19 m
LX = GC50.LX                   # 412 m
W_MAIN = GC50.W_MAIN           # 140 m
W_STRIP = GC50.W_STRIP         # 6 m (build checks only)
ZB = GC50.ZB                   # -19 m
Z_TOP = 17.0                   # box48 top (fixed there) [chosen in FLIP48]
X_TOE = GC50.X_TOE             # 160.25 m: toe of the 1:10 part
SLOPE_S = GC50.SLOPE_S         # 1:10
IN_X1 = GC50.IN_X1             # inlet band end 100 m
WALL_TAPER = GC50.WALL_TAPER   # 20 m
SD0 = GC50.SD0                 # 95 m
SD_BAND = GC50.SD_BAND         # 45 m
SD_GEN = GC50.SD_GEN           # 180.25 m
SD_SW = GC50.SD_SW             # 210.25 m
SD_SIGMA = GC50.SD_SIGMA       # 1.41
SD_POW = GC50.SD_POW           # 2
SD_TAPER = GC50.SD_TAPER       # 11.25 m
RAMP_S = 14.0                  # DFG-2 ramp (= DFG-2B-E)
HOLD_X = GC50.HOLD_X
VOL_TAU, VOL_DMAX, VOL_TCAP, VOL_MEASURE = GC50.VOL_TAU, GC50.VOL_DMAX, GC50.VOL_TCAP, GC50.VOL_MEASURE
HOLD_TI = GC50.HOLD_TI
LEVEL_GUARD_M = GC50.LEVEL_GUARD_M
GAUGE_X = GC50.GAUGE_X         # (110, 128, 160)
GAUGE_Y = GC50.GAUGE_Y         # (0.5, 20, 40, 60, 80)
R3_Y = GC50.R3_Y               # 77 m
R4_X = (190.0, 335.0)          # = DFG-2B-E (converged crest ~228-238 m, face 235-252 m, shelf)
R4_Y1 = SD0
R4_Z = (-10.0, 16.0)
N1_STILL_X = list(GC50.N1_X)   # (110, 340) online still offset window (still water: the sponge does not act at rest)
INTERIOR_X = (110.0, 340.0)    # = DFG-2B-E N1 window
INTERIOR_Y = 95.0              # = DFG-2B-E (rows y > 95 m NaN in the judge metrics; pv53 uses 65 m for the FLIP52 family)
SCAN_X = (150.0, 300.0)        # = DFG-2B-E 'conv' scan window
T_WAVE = 7.0
TP = 7.0

# ------------------------------------------------------------------ (c) the bed: 1:10 to h 11.5 m, then 1:3 to a 6 m shelf [chosen, round-2 design]
H_L = 11.5                     # foot of the steep part (depth, m): x_foot = 160.25 + (19 - 11.5) x 10 = 235.25 m
S2 = 3.0                       # steep part 1:3
H_TOP = 6.0                    # shelf depth (m)
X_FOOT = X_TOE + (H0 - H_L) * SLOPE_S          # 235.25 m [computed]
X_EDGE = X_FOOT + (H_L - H_TOP) * S2           # 251.75 m [computed]
X_SHORE = LX                   # no shoreline in the box: the particle checks use the box end (as DFG-S)
SPEC_D19B = dict(GC50.SPEC_D19B)               # the DFG-2B-E bed (read only)
SPEC_BED = dict(GC50.SPEC_D19B)
SPEC_BED.update(shelf_h=H_TOP, pg_hL=H_L, pg_s2=S2)   # k 0, k_end None, ch_h 0, s1 0, b_end 0, x_back 1e9 -> the FLIP49 two-slope path (pgon true)
BED_DF_DESIGN = dict(h0=H0, x_toe=X_TOE, s=SLOPE_S, kind="beach")   # the DirField bed of the DESIGN phase reference (= DFG-2B-E's; x <= 235.25 m equal)

# ------------------------------------------------------------------ exit sponge on the shelf (infrastructure: the end wall would reflect bores)
ABS_ON = 1.0
XA0 = 332.0                    # sponge 332-412 m (80 m, as DFG-S's 210-290 m) [chosen]
ABS_SIGMA = 1.0                # DFG-S's [chosen]
ABS_POW = 2.0
VOL_X = (110.0, 327.0)         # stage A window: outside the bands (layout A rule: 5 m before the sponge) [chosen]; DFG-2B-E 110-400 m (no sponge)
VOL_X_DFGBE = tuple(GC50.VOL_X)

LEVEL_REGIONS_52B2 = [
    ("band_core", 20.0, 95.0, 0.0, 95.0),
    ("probe_c", 100.0, 110.0, 0.0, 95.0),
    ("flat", 110.0, 160.0, 0.0, 95.0),
    ("window", VOL_X[0], VOL_X[1], 0.0, 95.0),
    ("break_front", 225.0, 255.0, 0.0, 10.0),
    ("face", X_FOOT, X_EDGE, 0.0, 10.0),
    ("shelf_front", X_EDGE, 290.0, 0.0, 10.0),
    ("inner_surf", 290.0, 330.0, 0.0, 10.0),
    ("swash", 330.0, 360.0, 0.0, 10.0),          # name kept for the D-layout readers (pv53 / Ctx49 'setup_region'); now inside the sponge
    ("side_surf", 290.0, 330.0, 60.0, 84.0),
    ("sponge", XA0, LX, 0.0, 95.0),
    ("asym_centre", 110.0, 160.0, 0.0, 10.0),
    ("asym_side", 110.0, 160.0, 75.0, 95.0),
]

# ------------------------------------------------------------------ the sea: DFG-2B-E's (AM-DFGB1 energy-matched DFG-2 sea), bit for bit
P_S = GC52.P_S                 # 28 s
HARMONICS = GC52.HARMONICS     # (3, 4, 5)
DSPEC = ("hyb", 60.0, 28.0, 85.0, 17)                # the plan E X2 set (= DFG-2 / DFG-2B-E)
A_SUM_FROZEN = GC52.A_SUM      # 6.331240146143423 m = the DM1A input SUM (DFG-2 / DFG-2B)
DM1A_N = 30                                     # DM1A cfg dir: n 30, uniform +-80 deg, T 12 s, h0 19 m [measured]
DM1A_AJ = 0.21104133820478077                   # DM1A cfg dir a_j [measured]
DM1A_SUM_A2 = DM1A_N * DM1A_AJ ** 2             # 1.336153 m^2
SUM_A2_FROZEN = float(A_SUM_FROZEN ** 2 * np.sum(GC52.freqset(P_S, HARMONICS, "eq")[1] ** 2) * np.sum(GC52.dirset(DSPEC)[1] ** 2))   # 0.473081 m^2
E_SCALE = math.sqrt(DM1A_SUM_A2 / SUM_A2_FROZEN)  # 1.680585 [computed] (= flip52b g52b_common.E_SCALE, AM-DFGB1)
A_SUM = A_SUM_FROZEN * E_SCALE                  # 10.640186 m [computed]
AM_DFGB1_SEA = dict(a_sum_m=10.640186271, a_max_component_m=0.159163, amp_per_freq_m=[3.546729, 3.546729, 3.546729], sum_a2_m2=1.336153,
                    scale=1.68058485)          # registered in Unity/Build/FLIP52B/plan/amendments.jsonl AM-DFGB1 'sea' (checked against it, read only)
X_F = 272.25                   # design focus = the GENERATOR's phase reference (on the old 1:10 beach, as DFG-2B-E); on the DFGB3 bed x 272.25 m
                               # lies on the 6 m shelf: the converged crest is expected upstream of the foot (x 228-238 m [measured DFG-2B-E])
T_F = 63.0                     # first focus time (s) = DFG-2B-E's (ray arrival rule + 3.9 s, amplitude-free)
N_GROUPS = 3
FOCI = tuple(T_F + P_S * m for m in range(N_GROUPS))      # 63, 91, 119 s
TABLE_X = (0.0, 214.0)
TABLE_Y = (0.0, W_MAIN)
TABLE_DX = 1.0
X_FULL_END = 300.0             # the DirField grid must contain x_f (its phase reference); the table keeps x <= 214 m
FIELDS_LAYER = GC52.FIELDS_LAYER
FIELDS_SHARED = GC52.FIELDS_SHARED
MAX_LAYERS = GC52.MAX_LAYERS
GROUP_WIN = (-8.0, 6.0)        # per-group window around t_fn (s) (= DFG-2B-E)

# ------------------------------------------------------------------ (b) the generator calibration: phase pre-compensation per layer
PHI_COMP = {3: -0.060788, 4: 0.279111, 5: 0.513994}       # rad = DFG-2B-E judge G2f per_n phase_err_rad [measured; 6 decimals as stored]
PHI_RULE = ("table layer n x exp(-i phi_n), phi_n = the G2f phase error measured on DFG-2B-E (x 110 m, y 0.5-80 m, t 49-105 s; same sea, table "
            "convention, VEX, dp and inlet band): the realised layer lagged its target by phi_n (eta_n = Re(A e^{-i w (t - t_f)}): a positive phi = "
            "a later arrival), so the target is advanced by phi_n / w_n (n3 -0.090 s, n4 +0.311 s, n5 +0.458 s; a negative value = a delay); |factor| = 1 [calibrated]")


def phase_factor(n_index):
    """the complex factor of table layer n_index (0, 1, 2 -> harmonics 3, 4, 5)."""
    return complex(np.exp(-1j * PHI_COMP[int(HARMONICS[n_index])]))


def h_of(x):
    """still-water depth of the DFGB3 bed on the axis (plan x, m)."""
    x = float(x)
    if x <= X_TOE:
        return H0
    if x <= X_FOOT:
        return H0 - (x - X_TOE) / SLOPE_S
    return max(H_TOP, H_L - (x - X_FOOT) / S2)


def bed_depth(x):
    """the analytic two-slope bed, vectorised, written with the same operations as g49_common._rise2 / bed_z (k 0: sech^2 = 1)."""
    x = np.asarray(x, dtype=np.float64)
    u = x - X_TOE
    uL = (H0 - H_L) * SLOPE_S
    R = np.where(u <= 0, 0.0, np.where(u <= uL, u / SLOPE_S, (H0 - H_L) + (u - uL) / S2))
    return np.maximum(H_TOP, H0 - R)


def dfgbe_depth(x):
    """DFG-2B-E's D19B bed depth (report / comparison)."""
    x = np.asarray(x, dtype=np.float64)
    return H0 - np.maximum(x - X_TOE, 0.0) / SLOPE_S


def dirset(spec=DSPEC):
    return GC52.dirset(spec)


def freqset(P=P_S, ns=HARMONICS, fw="eq"):
    return GC52.freqset(P, ns, fw)


def components(a_sum=A_SUM):
    """the inlet components at the generation depth h0 19 m: a_nj = a_sum wf_n wd_j (= DFG-2B-E's)."""
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
    """the D19B box = flip48 box48 (top +17 m), floor pad 2 cells (as FLIP50 / plan E / DFG-2B-E)."""
    return box48(dp, Lx=Lx, W=W, x0=x0, zb=zb, floor_pad=floor_pad, side_pad=side_pad)


def sea_text():
    """the one-line energy statement every cfg / judge / report carries (Q84 honesty; the in-tank numbers are in the plan's sea.energy)."""
    return ("equal spectral energy (Q84): every component = %.6f x DFG-2B's frozen value (= DFG-2B-E's), a_sum %.6f m, sum a^2 %.6f m^2 at the "
            "generation depth h0 19 m = DM1A's %.6f m^2 (energy density 0.5 rho g sum a^2); the round-2 phase pre-compensation has |factor| 1 "
            "(energy unchanged); NOT equal in-tank energy (AM-DFGB1b caveat: the incoming waves inside the tank carry less than DM1A's, see the plan's "
            "sea.energy.in_tank)" % (E_SCALE, A_SUM, float(A_SUM ** 2 * np.sum(GC52.freqset(P_S, HARMONICS, "eq")[1] ** 2)
                                                          * np.sum(GC52.dirset(DSPEC)[1] ** 2)), DM1A_SUM_A2))


# ------------------------------------------------------------------ the bed: numpy path, analytic bed and the VEX text it relies on
VEX_LINES = ("int pgon() { return (chf(CT+\"pg_hL\") > 0.0 || chf(CT+\"b_end\") > 0.0 || chf(CT+\"lag_xb\") < 1e8) ? 1 : 0; }",
             "vector2 rise2(float x) {",
             "if (s2 > 0.0 && hL > chf(CT+\"shelf_h\")) {",
             "if (u <= uL) return set(u/s1, 1.0/s1);",
             "return set((h0 - hL) + (u - uL)/s2, 1.0/s2);",
             "float bedy_pg(float x; float zl) {",
             "float d = max(hr, h0 - R.x*sh*sh);",
             "vector2 bedgrad_pg(float x; float zl) {",
             "if (d <= hr) { d = hr; ddx = 0.0; ddy = 0.0; }",
             "if (pgon()) return bedy_pg(x, zl);",
             "if (pgon()) return bedgrad_pg(x, zl);",
             "float d = (y - bedy(x, zl))/sqrt(1.0 + gr.x*gr.x + gr.y*gr.y);")


def _vex_text():
    """the VEX source the FLIP52 scene compiles (flip50/g50_tanklib.VEX_HEAD, itself flip49/g49_tanklib's head), read as text only."""
    out = []
    for p in (TOOLS49 + "/g49_tanklib.py", TOOLS50 + "/g50_tanklib.py"):
        if os.path.exists(p):
            out.append(open(p, encoding="utf8").read())
    return "\n".join(out)


def vex_bedy_pg_py(x, zl, P):
    """a line-by-line Python transliteration of the VEX bedy_pg() / rise2() / bedgrad_pg() for this bed's parms (k 0, b_end 0, ch_h 0, no lagoon);
    returns (bed height, d bed/dx, d bed/dy)."""
    h0 = P["h0"]
    if P["ridge_on"] < 0.5:
        return -h0, 0.0, 0.0
    hr = P["shelf_h"]
    u = x - P["ridge_x0"]
    if u <= 0.0:
        Rx, Ry = 0.0, 0.0
    else:
        s1 = P["ridge_s"]; hL = P["pg_hL"]; s2 = P["pg_s2"]
        if s2 > 0.0 and hL > hr:
            uL = (h0 - hL) * s1
            Rx, Ry = (u / s1, 1.0 / s1) if u <= uL else ((h0 - hL) + (u - uL) / s2, 1.0 / s2)
        else:
            Rx, Ry = u / s1, 1.0 / s1
    k = P["ridge_k"]
    sh = 1.0 / math.cosh(k * abs(zl) / h0)
    d = max(hr, h0 - Rx * sh * sh)
    zb_ = -d
    S = sh * sh
    dd = h0 - Rx * S
    ddx = -(Ry * S - 0.0)
    ddy = 0.0
    if dd <= hr:
        ddx = 0.0; ddy = 0.0
    return zb_, -ddx, -ddy


def bed_selfcheck():
    """[computed] numpy only: (1) the g49 two-slope path with SPEC_BED equals the analytic bed (bed_depth) to 1e-12 m, laterally uniform; (2)
    bed_grad = (1/10, 0) on the beach part, (1/3, 0) on the face, (0, 0) on the flat and the shelf; (3) bed_sdf = (z - bed)/sqrt(1 + gx^2);
    (4) the DESIGN DirField bed (D19B beach) equals this bed for x <= x_foot 235.25 m (the table grid ends at 214 m; the bands end at 210.25 m);
    (5) the VEX transliteration equals numpy and the VEX source text still contains every line it transliterates; (6) the FLIP49 two-slope path is
    used (pg_hL 11.5, pg_s2 3, shelf_h 6; k 0, no taper, no channel, no flat top, no lagoon); (7) foot / edge positions."""
    sp = dict(SPEC_BED)
    out = {}
    xq = np.union1d(np.arange(0.0, LX + 1e-9, 0.37), [0.0, X_TOE - 1e-9, X_TOE, X_TOE + 1e-9, 200.0, X_FOOT - 1e-9, X_FOOT, X_FOOT + 1e-9,
                                                       245.0, X_EDGE - 1e-9, X_EDGE, X_EDGE + 1e-9, 300.0, XA0, LX])
    yq = np.array([0.0, 0.5, 13.7, 50.0, 77.0, 94.5, 95.5, 110.5, 128.75, 139.5, 140.0])
    zq = bed_z(xq[None, :], yq[:, None], **sp)
    ana = -bed_depth(xq)
    dz = float(np.abs(zq - ana[None, :]).max())
    out["max_abs_dz_vs_analytic_m"] = dz
    out["equals_analytic_bit"] = bool(np.array_equal(zq, np.broadcast_to(ana, zq.shape)))
    out["equals_analytic_1e12"] = bool(dz < 1e-12)
    out["laterally_uniform"] = bool(np.all(zq == zq[0:1, :]))
    gx, gy = bed_grad(xq[None, :], yq[:, None], **sp)
    beach = (xq > X_TOE) & (xq <= X_FOOT)
    face = (xq > X_FOOT) & (xq < X_EDGE)
    gref = np.where(beach, 1.0 / SLOPE_S, np.where(face, 1.0 / S2, 0.0))
    out["grad_ok"] = bool(np.allclose(gx, np.broadcast_to(gref, gx.shape), rtol=0, atol=1e-15) and np.all(gy == 0.0))
    zz = np.array([-21.0, -19.0, -11.0, -7.0, -5.0, 0.0, 3.0])
    sd = bed_sdf(xq[None, :], zz[:, None], 0.0 * zz[:, None], **sp)
    sref = (zz[:, None] - ana[None, :]) / np.sqrt(1.0 + gref[None, :] ** 2)
    out["sdf_ok"] = bool(np.allclose(sd, sref, rtol=0, atol=1e-12))
    up = xq <= X_FOOT + 1e-12
    out["design_dirfield_bed_equal_upstream_of_foot"] = bool(np.allclose(DF50.bed_h(xq[up], BED_DF_DESIGN), bed_depth(xq[up]), rtol=0, atol=1e-12))
    out["dfgbe_bed_equal_upstream_of_foot"] = bool(np.allclose(dfgbe_depth(xq[up]), bed_depth(xq[up]), rtol=0, atol=1e-12))
    P = dict(bed_parms(sp)); P["h0"] = H0
    vx = np.array([vex_bedy_pg_py(float(x), float(y), P) for y in (0.0, 47.3, 94.5, 139.5) for x in xq]).reshape(4, len(xq), 3)
    out["vex_transliteration_max_abs_dz_m"] = float(np.abs(vx[..., 0] - ana[None, :]).max())
    out["vex_transliteration_grad_ok"] = bool(np.allclose(vx[..., 1], gref[None, :], rtol=0, atol=1e-15) and np.all(vx[..., 2] == 0.0))
    txt = _vex_text()
    out["vex_text_has_lines"] = {ln: (ln in txt) for ln in VEX_LINES}
    out["two_slope_path"] = bool(is_new(sp) and sp.get("k_end") is None and float(sp["k"]) == 0.0 and float(sp.get("ch_h") or 0.0) == 0.0
                                 and float(sp.get("s1") or 0.0) == 0.0 and float(sp.get("b_end") or 0.0) == 0.0 and float(sp.get("x_back", 1e9)) >= 1e8
                                 and float(sp["pg_hL"]) == H_L and float(sp["pg_s2"]) == S2 and float(sp["shelf_h"]) == H_TOP
                                 and bed_kind(sp) == "pg_reef_axis_strip")
    out["parms"] = {k: P[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h", "h0", "ridge_kend", "ch_h", "ledge_s1", "pg_hL",
                                      "pg_s2", "b_end", "lag_xb")}
    out["x_foot_m"] = float(GC49.foot_x(sp))
    out["x_edge_rule_m"] = float(GC49.edge_x(sp))          # first x with depth <= shelf_h + 0.05 m (u3 rule): 251.6 m
    out["depth_min_max_m"] = [float(bed_depth(xq).min()), float(bed_depth(xq).max())]
    out["ok"] = bool(out["equals_analytic_1e12"] and out["laterally_uniform"] and out["grad_ok"] and out["sdf_ok"]
                     and out["design_dirfield_bed_equal_upstream_of_foot"] and out["dfgbe_bed_equal_upstream_of_foot"]
                     and out["vex_transliteration_max_abs_dz_m"] < 1e-12 and out["vex_transliteration_grad_ok"]
                     and all(out["vex_text_has_lines"].values()) and out["two_slope_path"]
                     and out["depth_min_max_m"] == [H_TOP, H0] and abs(out["x_foot_m"] - 235.25) < 1e-12 and abs(X_EDGE - 251.75) < 1e-12)
    out["note"] = ("no new VEX bed term: the FLIP49 two-slope branch (pgon / rise2 / bedy_pg / bedgrad_pg of flip49/g49_tanklib.py VEX head, "
                   "unchanged since PG12s, through g50_tanklib into g52_tanklib) with ridge_x0 160.25, ridge_s 10, pg_hL 11.5, pg_s2 3, shelf_h 6, "
                   "ridge_k 0 IS this bed; hython checks the compiled VEX (OUT_BED heights, the collision SDF, the particle seeding) against numpy on "
                   "the W 6 m strip and the W 140 m box in build_check52b2.json")
    return out


# ------------------------------------------------------------------ run ids and paths
RID = {"main": "DFGB3_D19Bs3h6_xf272p25_dp0p5"}


def run_id(kind="main"):
    return RID[kind]


def run_dir(kind="main"):
    return RUNS_ROOT + "/" + RID[kind]


def cfg_path(kind="main"):
    return RUNS_ROOT + "/ready/" + RID[kind] + ".json"


# ------------------------------------------------------------------ small helpers
def guard_out(path, allow_scratch=False):
    o = os.path.abspath(path).replace("\\", "/")
    ok = (o.lower() + "/").startswith(B52B2.lower() + "/")
    if allow_scratch and o.lower().startswith(SCRATCH_PREFIX.lower()):
        ok = True
    if not ok:
        raise SystemExit("output %s is outside Unity/Build/FLIP52B2%s; not written" % (o, " or its _scratch" if allow_scratch else ""))
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


def am_dfgb1_sea():
    """the AM-DFGB1 'sea' block registered for DFG-2B-E (read only), or None."""
    try:
        for ln in open(DFGB_AMEND, encoding="utf8"):
            if ln.strip():
                e = json.loads(ln)
                if e.get("id") == "AM-DFGB1" and e.get("sea"):
                    return e["sea"]
    except Exception:
        return None
    return None


def dfgbe_g2f_phases():
    """[measured, read only] DFG-2B-E's G2f per-frequency phase errors from its judge (the calibration source)."""
    try:
        g = jload(DFGBE_JUDGE)["G2f"]["per_n"]
        return {int(k[1:]): float(v["phase_err_rad"]) for k, v in g.items()}
    except Exception:
        return None


CODE_FILES = ("g52b2_common.py", "g52b2_table.py", "g52b2_mkcopy.py", "g52b2_build_tank.py", "x52b2_build.py", "g52b2_run.py", "g52b2_chain.py",
              "g52b2_pcfg.py", "g52b2_ana.py", "g52b2_video.py", "g52b2_plan.py")


def module_shas():
    out = {}
    for nm in CODE_FILES:
        p = os.path.join(TOOLS52B2, nm)
        out["flip52b2/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g52b_ana.py", "g52b_video.py", "g52b_table.py", "g52b_common.py"):
        p = os.path.join(TOOLS52B, nm)
        out["flip52b/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g52_common.py", "g52_table.py", "g52_tanklib.py", "g52_build_tank.py", "g52_run.py", "g52_chain.py", "g52_ana.py"):
        p = os.path.join(TOOLS52, nm)
        out["flip52/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g50_common.py", "g50_table.py", "g50_tanklib.py", "g50_dirfield.py"):
        p = os.path.join(TOOLS50, nm)
        out["flip50/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g49_common.py", "g49_tanklib.py"):
        p = os.path.join(TOOLS49, nm)
        out["flip49/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
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
