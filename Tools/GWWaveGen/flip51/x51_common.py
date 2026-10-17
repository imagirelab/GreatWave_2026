# -*- coding: utf-8 -*-
"""FLIP51 plan E ('crossing screens'): constants and the three direction sets (numpy only; read by py -3.10 and importable from hython).
2026-10-17 written new (Claude). Nothing in flip45-flip50 is edited; flip50 modules are imported READ ONLY (g50_common, g50_dirfield).

Why (user, 2026-10-17 ~17:10): the big wave is 'not converged enough'; the target picture shows ONE tall wave converging upward into a
sharp peak with the surrounding sea much lower. The FLIP50 option-D fan (+-80 deg, T 12/10 s) gave a crest about 6-9 Hc wide at 50 %.
Plan E screens, in the SAME D19B tank and FLIP50 pipeline (directional table + band VEX, hip Houdini/FLIP50/g50_tank.hiplc used unchanged),
a shorter period T 7 s (kh 1.2-1.75: steepness-limited, not depth-limited) and two crossing direction sets:
  U7  uniform +-80 deg, 30 components (DM1A with the period alone changed; control and T 7 pipeline check)
  X2  'isolated hybrid crossing': +-linspace(2, 85, 17) deg, Gaussian weights about +-60 deg (sigma 28 deg), 34 components
  X1  'pure crossing': +-{45, 48, ..., 75} deg, equal amplitudes, 22 components
All three: a_sum 6.331240 m at h0 = the DM1A input sum [chosen], focus (220.25, 0) at t = 7n s [chosen], ramp 14 s (2T, D rule).
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
import g50_common as GC50            # noqa: E402  read only
import g50_dirfield as DF            # noqa: E402  read only

B51 = REPO + "/Unity/Build/FLIP51"
PLAN_DIR = B51 + "/plan"
PLAN_E = PLAN_DIR + "/plan_E_frozen.json"
PLAN_E_REL = "Unity/Build/FLIP51/plan/plan_E_frozen.json"
TABLE_DIR = B51 + "/tables"
SMOKE_ROOT = B51 + "/smoke"          # 1.0 m screens (cfg out_root is this ABSOLUTE path: g50_chain/g50_run join it onto Build/FLIP50 -> it wins)
RUNS_ROOT = B51 + "/runs"            # 0.5 m promoted runs
LOG_DIR = B51 + "/_logs"
PLAN_D_FROZEN = GC50.PLAN_FROZEN_D   # read only (D smoke gate numbers for the report-only D analysis)
SCRATCH_PREFIX = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP51/_scratch/"   # test outputs on FLIP50 runs may only go here (never into FLIP50); 2026-10-17 moved out of the session temp folder after round E2

T7 = 7.0
RAMP7 = 14.0                         # 2T (D rule) [chosen]
T_END = 75.0                         # periods n = 6-10 judged in t 38.5-73.5 s [chosen]
A_SUM = float(GC50.CASES["DM1"]["a_sum"])   # 6.331240146143423 m = DM1A input sum [chosen]
X_F = GC50.X_F                       # 220.25 m
T_F = 0.0
W = GC50.W_MAIN                      # 140 m half width
SD0 = GC50.SD0                       # 95 m: side band inner edge
REC_WINDOW = (35.0, T_END)           # r4 (and r5 at 0.5 m) records [chosen]


def _gauss_lobes(th0, sg, n, lo=2.0, cap=85.0):
    """the X2 set exactly as Tools/GWWaveGen/flip51/cross/c51_sweepD.gauss_lobes(60, 28, n=17, cap=85): th1 = linspace(max(th0 - 2.5 sg, 2),
    min(th0 + 2.5 sg, cap), n), w1 = exp(-0.5 ((th1 - th0)/sg)^2), mirrored."""
    th1 = np.linspace(max(th0 - 2.5 * sg, lo), min(th0 + 2.5 * sg, cap), n)
    w1 = np.exp(-0.5 * ((th1 - th0) / sg) ** 2)
    th = np.concatenate([-th1[::-1], th1]); w = np.concatenate([w1[::-1], w1])
    return th, w / w.sum()


def _lobes(th0, dl, n):
    th1 = np.linspace(th0 - dl, th0 + dl, n)
    th = np.concatenate([-th1[::-1], th1]); w = np.ones_like(th)
    return th, w / w.sum()


CASES = {
    "U7": dict(label="uniform +-80 deg, 30 components (DM1A with T 12 -> 7 s only)", short="u80", role="control and T 7 pipeline check",
               set_rule="g50_dirfield.components(80, 30, 'uniform')", Hc_pred_central=6.5, Hc_pred_range=[5.8, 7.2],
               miss_pred_central=3.0, miss_pred_range=[2.1, 3.8], W50_pred=5.5),
    "X2": dict(label="isolated hybrid crossing: +-linspace(2, 85, 17) deg, w ~ exp(-(|th| - 60)^2 / (2 28^2)), 34 components", short="g60s28",
               role="deliverable candidate", set_rule="c51_sweepD.gauss_lobes(60, 28, n=17, cap=85)", Hc_pred_central=6.0, Hc_pred_range=[5.4, 6.6],
               miss_pred_central=2.6, miss_pred_range=[1.65, 3.47], W50_pred=4.9, design_crest_pred=5.41),
    "X1": dict(label="pure crossing: +-{45, 48, ..., 75} deg, equal amplitudes, 22 components", short="l60d15", role="bracket and jet chance",
               set_rule="lobes(60, 15, 11) (c51_predict.lobes)", Hc_pred_central=6.1, Hc_pred_range=[5.5, 6.7],
               miss_pred_central=1.88, miss_pred_range=[0.82, 2.87], W50_pred=4.1, design_crest_pred=5.48),
}
ORDER = ("U7", "X2", "X1")           # screen order [chosen in the plan]
TIE_ORDER = ("X2", "X1", "U7")       # promotion tie order (isolation first, then the crossing-jet argument)


def components(case):
    """(theta_deg, w) with sum(w) = 1; symmetric +-pairs (the half tank mirror at y = 0)."""
    if case == "U7":
        return DF.components(80.0, 30, "uniform")
    if case == "X2":
        return _gauss_lobes(60.0, 28.0, 17)
    if case == "X1":
        return _lobes(60.0, 15.0, 11)
    raise KeyError(case)


def run_id(case, dp):
    return "S51%s_D19B_T7_%s_dp%s" % (case, CASES[case]["short"], ("%.1f" % float(dp)).replace(".", "p"))     # dp1p0 / dp0p5


def run_dir(case, dp):
    return (SMOKE_ROOT if float(dp) == 1.0 else RUNS_ROOT) + "/" + run_id(case, dp)


def cfg_path(case, dp):
    return (SMOKE_ROOT if float(dp) == 1.0 else RUNS_ROOT) + "/ready/" + run_id(case, dp) + ".json"


def sha256_file(p):
    return GC50.sha256_file(p)


def sha16_json(o):
    return hashlib.sha256(json.dumps(o, sort_keys=True, ensure_ascii=False, default=float).encode("utf8")).hexdigest()[:16]


def kdisp(om, h):
    return DF.kdisp(om, h)


def bed_h(x):
    """D19B still depth (flat 19 m, 1:10 from x 160.25 m)."""
    return GC50.H0 - np.maximum(np.asarray(x, float) - GC50.X_TOE, 0.0) / GC50.SLOPE_S


def guard_out(path, allow_scratch=False):
    """write only under Unity/Build/FLIP51 (or the session scratchpad for tests on read-only FLIP50 runs)."""
    o = os.path.abspath(path).replace("\\", "/")
    ok = (o.lower() + "/").startswith(B51.lower() + "/")
    if allow_scratch and o.lower().startswith(SCRATCH_PREFIX.lower()):
        ok = True
    if not ok:
        raise SystemExit("output %s is outside Unity/Build/FLIP51%s; not written" % (o, " or the scratchpad" if allow_scratch else ""))
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
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def jdump(o, p):
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)


def code_files():
    """the code the frozen plan registers (sha256): plan E tools and the frozen e51 ruler."""
    fs = ["x51_common.py", "x51_table.py", "x51_pcfg.py", "x51_ana.py", "x51_video.py", "x51_plan.py", "e51_metrics.py"]
    return {"Tools/GWWaveGen/flip51/" + f: TOOLS51 + "/" + f for f in fs}
