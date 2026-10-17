# -*- coding: utf-8 -*-
"""FLIP51 X2B' (idea X2B, design 2026-10-17 ~22:40): constants shared by the X2B tools (numpy only; py -3.10 -B).
2026-10-17 written new (Claude). Nothing in flip45-flip53 is edited: x51_common / g50_common are imported READ ONLY; the X2B case record is
added to x51_common.CASES only IN MEMORY (register_case) by the analysis wrappers that need it.

X2B' = X2 (S51X2_D19B_T7_g60s28_dp0p5: T 7 s, +-linspace(2, 85, 17) deg Gaussian lobes about +-60 deg sigma 28 deg, 34 components,
a_sum 6.331240 m = the DM1A input sum, D19B tank, hip Houdini/FLIP50/g50_tank.hiplc unchanged) with TWO changes:
  1. the focus point x_f 220.25 -> 275.25 m (h_f 7.5 m), t_f 0 kept (crest at x_f at t = 7n s), and the directional table built for it;
  2. the side band generates further shoreward: sd_gen 180.25 -> 210.25 m, sd_sw 210.25 -> 240.25 m (cfg parms -> CTRL; the VEX reads them),
     and the table covers x 0-244 m (was 0-214 m) so it reaches past the new blend end 240.25 m.
Why the second change [computed, x51b_screen.py supplyfix / detail, Unity/Build/FLIP51/_scratch/x2b/]: with the X2 bands the rays of the
65-85 deg components to a shoreward focus leave the side band where it already absorbs; the supplied focal crest falls as fast as the depth
(supply 0.99 -> 0.67 for x_f 220 -> 280, Hc/h_f 0.42 -> 0.53) and no x_f in 240-300 m breaks at the focus. With the band extended the
supply returns (0.985 at x_f 275.25) and the converged crest is predicted to reach ~0.82 h at x ~282 m (h_b 6.9 m, Hc 5.6 m).
Tags: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, math, json, hashlib

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS51 = REPO + "/Tools/GWWaveGen/flip51"
TOOLS50 = REPO + "/Tools/GWWaveGen/flip50"
for _p in (TOOLS50, TOOLS51):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                   # noqa: E402
import x51_common as XC              # noqa: E402  read only
import g50_common as GC              # noqa: E402  read only

CASE = "X2B"
BASE_CASE = "X2"
SHORT = "g60s28_xf275"
B51 = XC.B51
PLAN_DIR = XC.PLAN_DIR
LOGS = XC.LOG_DIR
TABLE_DIR = XC.TABLE_DIR
RUNS_ROOT = XC.RUNS_ROOT

# ------------------------------------------------------------------ the two changes [chosen in the design, numbers computed by x51b_screen.py]
X_F = 275.25                         # focus x (still depth 7.5 m) [chosen]
T_F = 0.0                            # focus time: crest at x_f at t = 7n s (the X2 judge windows n 6-10 stay) [chosen]
SD_GEN = 210.25                      # side band generates for x <= sd_gen (was 180.25) [chosen]
SD_SW = 240.25                       # side band absorbs for x >= sd_sw, smooth01 blend between (was 210.25) [chosen]
TABLE_X = (0.0, 244.0)               # table x range (covers the blend end 240.25 m with the same 3.75 m margin as 214 / 210.25) [chosen]
DF_END = 300.0                       # DirField grid end (must contain x_f; the table is cut at TABLE_X[1]) [chosen]
H_F = GC.H0 - (X_F - GC.X_TOE) / GC.SLOPE_S      # 7.5 m [computed]

# ------------------------------------------------------------------ run, files
DP = 0.5
RUN_ID = "S51X2B_D19B_T7_%s_dp0p5" % SHORT
RUN_DIR = RUNS_ROOT + "/" + RUN_ID
CFG = RUNS_ROOT + "/ready/" + RUN_ID + ".json"
PLAN = PLAN_DIR + "/plan_X2B_frozen.json"
PLAN_REL = "Unity/Build/FLIP51/plan/plan_X2B_frozen.json"
TABLE_CHECK = PLAN_DIR + "/table_check_X2B.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
OUT_DIR = RUN_DIR + "/x2b"           # every X2B analysis output of the run (judge copy, side band check, view, report)
STATUS = LOGS + "/auto_X2B_status.txt"
AUTO = "G:/research/Wave Simulation/_tools/auto_X2B.py"
R5_EVERY_DEFAULT = 1                 # surface meshes every frame in 35-75 s (superset of X2's every 3rd; every period at 24/s for Unity) [chosen]

# references (read only)
X2_RUN = RUNS_ROOT + "/S51X2_D19B_T7_g60s28_dp0p5"
X2_CFG = RUNS_ROOT + "/ready/S51X2_D19B_T7_g60s28_dp0p5.json"
X2_JUDGE = X2_RUN + "/e51/judge_E05.json"
X2_PV53 = REPO + "/Unity/Build/FLIP53/pv53/S51X2_D19B_T7_g60s28_dp0p5/pv53_S51X2_D19B_T7_g60s28_dp0p5.json"
DM1A_RUN = REPO + "/Unity/Build/FLIP50/runs/DM1A_D19B_T12_th80_dp0p5"
DM1A_PV53 = REPO + "/Unity/Build/FLIP53/pv53/DM1A_D19B_T12_th80_dp0p5/pv53_DM1A_D19B_T12_th80_dp0p5.json"
BASELINE = B51 + "/target/baseline.json"
PV53 = REPO + "/Tools/GWWaveGen/flip53/pv53.py"
X2VIEW = B51 + "/_scratch/x2view"

# the X2B case record (x51_ana reads Hc_pred_central for G6; the others are the registered predictions, also in the frozen plan)
CASE_REC = dict(label="X2B': X2 direction set (+-linspace(2, 85, 17) deg, Gaussian +-60 deg sigma 28 deg, 34 components), x_f 275.25 m, "
                      "side band generating to 210.25 m (blend to 240.25 m)", short=SHORT, role="print-match probe of the converged wave",
                set_rule="c51_sweepD.gauss_lobes(60, 28, n=17, cap=85) (= X2)", Hc_pred_central=5.6, Hc_pred_range=[5.2, 5.95],
                miss_pred_central=1.9, miss_pred_range=[1.0, 2.7], W50_pred=4.4, design_crest_pred=None)


def components():
    """(theta_deg, w) = the X2 set exactly (x51_common.components('X2'))."""
    return XC.components(BASE_CASE)


def register_case():
    """add X2B to x51_common.CASES IN MEMORY (never the file) so the read-only x51_ana / x51_video find its prediction and set."""
    if CASE not in XC.CASES:
        XC.CASES[CASE] = dict(CASE_REC)
    return XC.CASES[CASE]


def bed_h(x):
    return XC.bed_h(x)


def sha256_file(p):
    return GC.sha256_file(p)


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def jload(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def jdump(o, p):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    XC.jdump(o, p)


def guard(path):
    """write only under Unity/Build/FLIP51 (X2B outputs) - x51_common.guard_out."""
    return XC.guard_out(path)


def code_files():
    """the code the X2B plan registers (sha256). Blocking: the X2B tools, the driver and the read-only modules they import whose
    behaviour decides the numbers (x51_ana / e51_metrics / x51_common / x51_pcfg / x51_table / x51_video). pv53 is registered separately as
    NON-blocking (another workflow maintains it; a change after freezing is reported, its frozen DM1A reference numbers are copied here)."""
    own = ["x51b_common.py", "x51b_table.py", "x51b_pcfg.py", "x51b_plan.py", "x51b_ana.py", "x51b_view.py"]
    ro = ["x51_common.py", "x51_table.py", "x51_pcfg.py", "x51_ana.py", "x51_video.py", "e51_metrics.py", "f3d51_export_e51.py"]
    out = {"Tools/GWWaveGen/flip51/" + f: TOOLS51 + "/" + f for f in own + ro}
    out["_tools/auto_X2B.py (G:/research/Wave Simulation)"] = AUTO
    return out


def view_files():
    """the X2 view tools reused read-only (imported by x51b_view): registered with their sha (blocking: they measure the section ruler)."""
    return {"Unity/Build/FLIP51/_scratch/x2view/x2_section.py": X2VIEW + "/x2_section.py",
            "Unity/Build/FLIP51/_scratch/x2view/cam_x2.py": X2VIEW + "/cam_x2.py"}
