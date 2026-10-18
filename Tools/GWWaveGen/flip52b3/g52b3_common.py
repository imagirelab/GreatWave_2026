# -*- coding: utf-8 -*-
"""FLIP52B3 plan DFGB4 = DFG-2B-V (DFG-2B round 3, a VALIDATION RERUN of DFG-2B-E): constants and helpers shared by the FLIP52B3 tools
(numpy only; read by hython and by py -3.10). 2026-10-18 written new (Claude) by adapting flip52b2/g52b2_common.py (DFGB3, FROZEN, not edited)
back to DFG-2B-E's tank (flip52b/g52b_common.py, FROZEN, not edited). Nothing in flip45-flip52s2 / flip52b / flip52b2 / flip52bh is edited;
read only (imported): g50_common (flip50: the D19B tank, the bed path, process helpers), g50_dirfield (kdisp, DirField), g52_common (flip52:
the DFG-2 sea), g49_common (smooth01). The frozen plan is Unity/Build/FLIP52B3/plan/plan_DFGB4_frozen.json (+ .sha256); g52b3_pcfg.py checks
every number here against it.

DFG-2B-V in one line (round-3 design (d) with a minimal (c), chosen 2026-10-18): DFG-2B-E BIT FOR BIT (the energy-matched DFG-2 sea x 1.680585,
P 28 s, T 9.33 / 7 / 5.6 s, the 34 X2 directions, design phase reference (272.25, 0) at t = 63 + 28 m s, the D19B tank with the 1:10 beach from
x 160.25 m and no exit sponge, the option-D bands, the stage A window 110-400 m, dp 0.5, the solver, the records; the scene is a byte copy of
DFG-2B-E's Houdini/FLIP52B/g52b_tank.hiplc) EXCEPT two generator-table differences and the judge registrations:
  1. an INLET-ONLY calibration of layer n5 (T 5.6 s): factor exp(-i PHI5 b(x)), PHI5 = 0.6 x DFG-2B-E's measured G2f n5 phase 0.513994 =
     0.3083964 rad (a time advance of 0.2749 s), b(x) = 1 - smooth01((x - 80)/20): the whole inlet band to x 80 m (all y, incl. the corner
     y 95-140 m where the inlet and the side band relax toward the same target) is advanced, blended over the last 20 m of the inlet band
     (x 80-100 m; smooth01 over 20 m = the shape and length of the inlet band's wall taper), and the table is the DESIGN for x >= 100 m, so the
     side band beyond the inlet band stays at the design and its target is continuous at the x 100 m / y >= 95 m corner. n3 and n4 untouched.
     DFGB3's whole-table factor is dropped (it pushed the side band, already on time, off the design: G4 0.419).
  2. a 3 % SIDE-BAND amplitude taper at the G4 hot spot: gain g(x, y) = 1 - 0.03 clip((x - 140)/20, 0, 1) clip((125 - y)/20, 0, 1)
     smooth01((y - 75)/20); in the side band (y >= 95 m) this is exactly the Unity/Build/FLIP52B3/diag/g4map.json candidate
     'design + taper 3 %'; the smooth01 factor only keeps the unused interior (x > 100 m, y < 95 m: no band acts there) at the design.
     The return current mx, my (a period mean of A conj U) is scaled by g^2 so it still cancels the target's own mean mass flux.
  3. judge registrations frozen before the run (as DFGB3's R2): the G6 window [t_fn - 6.9, t_fn - 0.9] s, x 215-260 m, |y| <= 10 m,
     Hc >= 5.67 m; the pre-lip 'conv'; co-equal 3b / 3c with DFG-2B-E as the reference; and (new) 'keeps the curl'.
Coordinates as FLIP48-52B: plan x = wave direction (x = 0 upstream wall), y = lateral (y = 0 symmetry plane), z = up (still level 0).
Houdini: up = y, lateral = z, Houdini = plan + o. The scene keeps the FLIP52 node names (G52_SETUP / G52_SIM / G52_READ / G52_SURF).
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
TOOLS52B2 = REPO + "/Tools/GWWaveGen/flip52b2"        # DFGB3 tools: READ ONLY (nothing imported at run time)
TOOLS52B3 = REPO + "/Tools/GWWaveGen/flip52b3"
for _p in (TOOLS50, TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)           # appended: flip52b3 names are found first
import numpy as np                     # noqa: E402
import g50_common as GC50              # noqa: E402  read only
import g50_dirfield as DF50            # noqa: E402  read only (kdisp, DirField, bed_h)
import g52_common as GC52              # noqa: E402  read only (the DFG-2 sea)
from g50_common import (HY, FFMPEG, G, FPS, is_binary_exact, check_dp, sha256_file, rup, frames_for, t_of_frame,   # noqa: E402,F401
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb,
                        bed_z, bed_grad, bed_sdf, bed_spec, bed_parms, bed_record, bed_kind, bed_formula, is_new, count_particles,
                        sf_tab_string, sf_target, smooth01, tag, NEW_DEFAULTS, box48)

TOOLS = TOOLS52B3
B52B3 = REPO + "/Unity/Build/FLIP52B3"
HIP = REPO + "/Houdini/FLIP52B3/g52b3_tank.hiplc"
HIP_REL = "Houdini/FLIP52B3/g52b3_tank.hiplc"
# the scene: a BYTE COPY of DFG-2B-E's scene (read only; the bed and box are DFG-2B-E's, so no new scene is built)
HIP_SRC = REPO + "/Houdini/FLIP52B/g52b_tank.hiplc"
HIP_SRC_SHA256 = "9fa07e66f930e92316278e29ed0b3ea3269c5fee044ca4c3a5d297ee898412c5"   # = build_check52b.json hip_sha256 = every DFG-2B-E launch [measured]
SRC_BUILD_CHECK = REPO + "/Unity/Build/FLIP52B/_logs/build_check52b.json"
PLAN_DIR = B52B3 + "/plan"
PLAN = PLAN_DIR + "/plan_DFGB4_frozen.json"
PLAN_REL = "Unity/Build/FLIP52B3/plan/plan_DFGB4_frozen.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
TABLE_DIR = B52B3 + "/tables"
LOG_DIR = B52B3 + "/_logs"
DIAG_DIR = B52B3 + "/diag"
BUILD_CHECK = LOG_DIR + "/build_check52b3.json"
BUILD_INPUTS = LOG_DIR + "/build_inputs52b3.json"
RUNS_ROOT = B52B3 + "/runs"
CT_NODE = "/obj/G52_SETUP/CTRL"
SCRATCH_PREFIX = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B3/_scratch/"
SET = "DFGB4"                          # table / cfg set name (starts with 'DFG': pv53 reads the run as FLIP52 family, <run>/g52/judge_DFG.json)
TAG = "DFGB4"
NAME = "DFG-2B-V"
TABLE_CHECK = PLAN_DIR + "/table_check_DFGB4.json"
PRECHECK = PLAN_DIR + "/precheck_DFGB4.json"
G4MAP_NPZ = B52B3 + "/_scratch/g4map.npz"     # the per-cell FLIP / linear ratio map measured on DFG-2B-E (b3_g4map.py, design step; read only)
G4MAP_JSON = DIAG_DIR + "/g4map.json"

# ------------------------------------------------------------------ DFG-2B-E (frozen, read only): the parent run, its plan, table and results
DFGB_PLAN = REPO + "/Unity/Build/FLIP52B/plan/plan_DFGB_frozen.json"
DFGB_AMEND = REPO + "/Unity/Build/FLIP52B/plan/amendments.jsonl"
DFGBE_RUN = REPO + "/Unity/Build/FLIP52B/runs/DFGB2E_D19B_xf272p25_dp0p5"
DFGBE_CFG = DFGBE_RUN + "/cfg.json"
DFGBE_READY = REPO + "/Unity/Build/FLIP52B/runs/ready/DFGB2E_D19B_xf272p25_dp0p5.json"
DFGBE_JUDGE = DFGBE_RUN + "/g52b/judge_DFGB.json"
DFGBE_COEQ = DFGBE_RUN + "/g52b/coequal_DFGB.json"
DFGBE_PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB2E_D19B_xf272p25_dp0p5/pv53_DFGB2E_D19B_xf272p25_dp0p5.json"
DFGBE_TABLE = REPO + "/Unity/Build/FLIP52B/tables/DFGBE_P28_xf272p25_W140_d40220b3cb7f.npz"
DFGBE_TABLE_CONTENT = "d40220b3cb7fd7bd538ab7b9582c7e61ebc0b2902730670f36dcb6db3ade5ffc"     # AM-DFGB1a G1 [measured]
DFGBE_TABLE_CHECK = REPO + "/Unity/Build/FLIP52B/plan/table_check_DFGBE.json"
DFGB3_RUN = REPO + "/Unity/Build/FLIP52B2/runs/DFGB3_D19Bs3h6_xf272p25_dp0p5"
DFGB3_JUDGE = DFGB3_RUN + "/g52b2/judge_DFGB3.json"
DFGB3_PV53 = REPO + "/Unity/Build/FLIP53/pv53/DFGB3_D19Bs3h6_xf272p25_dp0p5/pv53_DFGB3_D19Bs3h6_xf272p25_dp0p5.json"
DM1A_TABLE = REPO + "/Unity/Build/FLIP50/tables/D_DM1_T12_W140_c5c22196af32.npz"
DM1A_CFG = REPO + "/Unity/Build/FLIP50/runs/ready/DM1A_D19B_T12_th80_dp0p5.json"

# ------------------------------------------------------------------ the D19B tank (g50_common, unchanged; = DFG-2B-E)
H0 = GC50.H0                   # 19 m
LX = GC50.LX                   # 412 m
W_MAIN = GC50.W_MAIN           # 140 m
ZB = GC50.ZB                   # -19 m
Z_TOP = 17.0                   # box48 top (fixed there) [chosen in FLIP48]
X_TOE = GC50.X_TOE             # 160.25 m: toe of the 1:10 beach
SLOPE_S = GC50.SLOPE_S         # 1:10
X_SHORE = GC50.X_SHORE         # 350.25 m still-water shoreline
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
R4_X = (190.0, 335.0)          # = DFG-2B-E
R4_Y1 = SD0
R4_Z = (-10.0, 16.0)
N1_STILL_X = list(GC50.N1_X)   # (110, 340)
INTERIOR_X = (110.0, 340.0)    # = DFG-2B-E N1 window
INTERIOR_Y = 95.0              # = DFG-2B-E (rows y > 95 m NaN in the judge metrics; pv53 uses 65 m for the FLIP52 family)
SCAN_X = (150.0, 300.0)        # = DFG-2B-E 'conv' scan window
T_WAVE = 7.0
TP = 7.0
SPEC_BED = dict(GC50.SPEC_D19B)                # the DFG-2B-E bed, unchanged (1:10 from x 160.25 m to the shore 350.25 m and beyond)
BED_DF_DESIGN = dict(h0=H0, x_toe=X_TOE, s=SLOPE_S, kind="beach")   # the DirField bed of the design (= DFG-2B-E's)
ABS_ON = 0.0                   # no exit sponge (= DFG-2B-E: the beach absorbs)
XA0 = 1e9
ABS_SIGMA = 1.41
ABS_POW = 2.0
VOL_X = tuple(GC50.VOL_X)      # (110, 400) = DFG-2B-E (AM-D18)
LEVEL_REGIONS_52B3 = list(GC50.LEVEL_REGIONS_D)  # = DFG-2B-E's cfg level_regions

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
X_F = 272.25                   # design focus = the generator's phase reference (= DFG-2B-E's, on the 1:10 beach, h 7.8 m)
T_F = 63.0                     # first focus time (s) = DFG-2B-E's
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

# ------------------------------------------------------------------ 1. the inlet-only n5 calibration [calibrated] (round-3 design (d))
PHI5_MEAS = 0.513994           # rad: DFG-2B-E judge G2f per_n n5 phase_err_rad [measured; 6 decimals as stored]
CAL_SCALE5 = 0.6               # [chosen, design]: CS1 (diag/cs1band_scan2.json s = (0, 0, 0.6)) gives n5 phase +0.178 rad, R 0.73, phase margin
                               # 0.088 (n4), R margin 0.026; a full 1.0 leaves the n5 R margin 0.002 (CS1 moves R down as the phase is advanced)
PHI5 = CAL_SCALE5 * PHI5_MEAS  # 0.3083964 rad
CAL_N = 5
CAL_X_FULL = 80.0              # b = 1 for x <= 80 m
CAL_X_ZERO = 100.0             # b = 0 for x >= 100 m (the inlet band end: the table is the design downstream)
CAL_RULE = ("inlet-only n5 calibration: table layer n5 x exp(-i PHI5 b(x)), PHI5 = 0.6 x 0.513994 = 0.3083964 rad (DFG-2B-E's measured G2f n5 "
            "phase: the realised layer lagged its target, so the target is advanced by PHI5 / w5 = 0.2749 s), b(x) = 1 - smooth01((x - 80)/20): "
            "the inlet band to x 80 m (all y) advanced, blended over its last 20 m (x 80-100 m, where the inlet relaxation weight is <= 0.002), "
            "the design for x >= 100 m (the side band beyond the inlet band unchanged; its target continuous at the x 100 m / y >= 95 m corner); "
            "n3, n4 untouched; |factor| = 1 [calibrated]")

# ------------------------------------------------------------------ 2. the side-band amplitude taper [calibrated] (round-3 design minimal (c))
TAPER_D = 0.03
TAPER_X = (140.0, 20.0)        # clip((x - 140)/20, 0, 1)
TAPER_Y = (125.0, 20.0)        # clip((125 - y)/20, 0, 1)
TAPER_YIN = (75.0, 20.0)       # smooth01((y - 75)/20): 1 for y >= 95 m (the whole side band), 0 for y <= 75 m (unused interior stays the design)
TAPER_RULE = ("side-band amplitude taper: every table layer (er/ei, ur/ui, vr/vi) x g(x, y), g = 1 - 0.03 clip((x - 140)/20, 0, 1) "
              "clip((125 - y)/20, 0, 1) smooth01((y - 75)/20): in the side band (y >= 95 m) exactly the diag/g4map.json candidate 'design + "
              "taper 3 % (x 140-180, y 95-125)' (G4 screen 0.387 [calibrated]); g = 1 in the inlet band (x <= 140 m) and for y <= 75 m; the return "
              "current mx, my x g^2 (it cancels the target's own mean mass flux); kk, hh unchanged")


def _s01(c):
    c = np.clip(np.asarray(c, float), 0.0, 1.0)
    return c * c * (3.0 - 2.0 * c)


def cal_b(x):
    """the n5 calibration weight b(x) (1 in the inlet band to 80 m, 0 from 100 m)."""
    return 1.0 - _s01((np.asarray(x, float) - CAL_X_FULL) / (CAL_X_ZERO - CAL_X_FULL))


def gain(x, y):
    """the side-band taper g(x, y) (broadcasting)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    return (1.0 - TAPER_D * np.clip((x - TAPER_X[0]) / TAPER_X[1], 0.0, 1.0) * np.clip((TAPER_Y[0] - y) / TAPER_Y[1], 0.0, 1.0)
            * _s01((y - TAPER_YIN[0]) / TAPER_YIN[1]))


def layer_factor(n_index, x, y):
    """the complex generator factor of table layer n_index (0, 1, 2 -> harmonics 3, 4, 5) at (x, y): phase (n5 only) x taper (all layers)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    ph = np.exp(-1j * PHI5 * cal_b(x)) if int(HARMONICS[n_index]) == CAL_N else np.ones(np.broadcast(x, y).shape, complex)
    return ph * gain(x, y)


def h_of(x):
    """still-water depth of the D19B bed on the axis (plan x, m) (= DFG-2B-E's; negative = dry beach above the still level)."""
    return H0 - max(float(x) - X_TOE, 0.0) / SLOPE_S


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
            "generation depth h0 19 m = DM1A's %.6f m^2 (energy density 0.5 rho g sum a^2); the inlet-only n5 phase calibration has |factor| 1; "
            "the 3 %% side-band taper lowers the generator target only in the side band at y 95-125 m, x >= 140 m (full from x 160 m through the "
            "generating band to x 180.25 m and on its fade-out to x 210.25 m) (not the spectrum); NOT equal "
            "in-tank energy (AM-DFGB1b caveat: the incoming waves inside the tank carry less than DM1A's, see the plan's sea.energy.in_tank)"
            % (E_SCALE, A_SUM, float(A_SUM ** 2 * np.sum(GC52.freqset(P_S, HARMONICS, "eq")[1] ** 2) * np.sum(GC52.dirset(DSPEC)[1] ** 2)), DM1A_SUM_A2))


def bed_selfcheck():
    """[computed] numpy only: the bed is DFG-2B-E's D19B bed (g50_common.SPEC_D19B, plain path k 0, no shelf): bed_z equals the analytic
    -(19 - max(x - 160.25, 0)/10), laterally uniform, and the DirField design bed equals it on the table grid."""
    sp = dict(SPEC_BED)
    xq = np.union1d(np.arange(0.0, LX + 1e-9, 0.37), [0.0, X_TOE - 1e-9, X_TOE, X_TOE + 1e-9, 235.25, 272.25, X_SHORE, LX])
    yq = np.array([0.0, 0.5, 13.7, 50.0, 77.0, 94.5, 95.5, 110.5, 128.75, 139.5, 140.0])
    zq = bed_z(xq[None, :], yq[:, None], **sp)
    ana = -(H0 - np.maximum(xq - X_TOE, 0.0) / SLOPE_S)
    dz = float(np.abs(zq - ana[None, :]).max())
    up = xq <= TABLE_X[1] + 1e-9
    out = dict(max_abs_dz_vs_analytic_m=dz, laterally_uniform=bool(np.all(zq == zq[0:1, :])),
               spec_equals_D19B=bool(sp == dict(GC50.SPEC_D19B)), bed_kind=bed_kind(sp),
               design_dirfield_bed_equal=bool(np.allclose(DF50.bed_h(xq[up], BED_DF_DESIGN), H0 - np.maximum(xq[up] - X_TOE, 0.0) / SLOPE_S, rtol=0, atol=1e-12)))
    out["ok"] = bool(dz < 1e-9 and out["laterally_uniform"] and out["spec_equals_D19B"] and out["design_dirfield_bed_equal"])
    return out


# ------------------------------------------------------------------ run ids and paths
RID = {"main": "DFGBV_D19B_xf272p25_in5c0p6_tp3_dp0p5"}


def run_id(kind="main"):
    return RID[kind]


def run_dir(kind="main"):
    return RUNS_ROOT + "/" + RID[kind]


def cfg_path(kind="main"):
    return RUNS_ROOT + "/ready/" + RID[kind] + ".json"


# ------------------------------------------------------------------ small helpers
def guard_out(path, allow_scratch=False):
    o = os.path.abspath(path).replace("\\", "/")
    ok = (o.lower() + "/").startswith(B52B3.lower() + "/")
    if allow_scratch and o.lower().startswith(SCRATCH_PREFIX.lower()):
        ok = True
    if not ok:
        raise SystemExit("output %s is outside Unity/Build/FLIP52B3%s; not written" % (o, " or its _scratch" if allow_scratch else ""))
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


CODE_FILES = ("g52b3_common.py", "g52b3_table.py", "g52b3_mkcopy.py", "x52b3_build.py", "g52b3_run.py", "g52b3_chain.py", "g52b3_pcfg.py",
              "g52b3_ana.py", "g52b3_video.py", "g52b3_plan.py")


def module_shas():
    out = {}
    for nm in CODE_FILES:
        p = os.path.join(TOOLS52B3, nm)
        out["flip52b3/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
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
