# -*- coding: utf-8 -*-
"""FLIP54 K54: the 2D CONCAVE-BED STRIP SCREEN for the big hollow (user 10/18 evening: "最关键的问题我觉得还是卷不出大空洞").
Constants and helpers shared by the K54 tools (numpy only at import; read by hython and by py -3.10 -B).

2026-10-18 written new (Claude, FLIP54 builder K) by ADAPTING the campaign-B strip tools of FLIP49 (Tools/GWWaveGen/flip49/g49_common.py,
g49_pcfg.py, g49_planB.py; FROZEN, not edited, read / imported only) to the D19B tank of DFG-2B (h0 19 m, 1:10 from x 160.25 m) with the
FLIP49 two-slope bed term (pg_hL / pg_s2 / shelf_h; the term flip52b2 used for DFGB3) and an exit sponge. The adapted copies are:
  g54_common.py  <- g49_common.py   (this file: constants, beds, bed_selfcheck for 6-7.5 m shelves, Fenton helpers re-exported, H rules)
  g54_pcfg.py    <- g49_pcfg.py     (make / precheck of the K54 strip cfgs; dry build)
  g54_plan.py    <- g49_planB.py    (the frozen plan K54 with the registered pass bar; freeze refuses once a K54 run exists)
  g54_run.py     <- g49_run.py      (byte copy with 6 named edits, written by g54_mkcopy.py: import g54_common, outputs Unity/Build/FLIP54,
                                     the Fenton depth check sf.h == h0 instead of the fixed 17 m)
  g54_chain.py   <- g49_chain.py    (byte copy with named edits by g54_mkcopy.py: g54_run, FLIP54 paths, build_check54.json)
  x54_check.py   (new, hython): the scene check of Houdini/FLIP49/g49_tank.hiplc (READ ONLY, never saved) with every K54 bed / box / table
  g54_ana.py     (new): the pv53 ruler on every frame of the judged breakers, the K54 metrics, the H calibration, the verdict, sheet and mp4
The Houdini scene is FLIP49's g49_tank.hiplc, unchanged (its CTRL carries h0, the two-slope bed, the stream-function inlet band and the
exit sponge abs_on / xa0 / abs_sigma / abs_pow; campaign-B strips ran in it). No new VEX term: the bed of every arm is CTRL numbers only.

Coordinates as FLIP48-52: plan x = wave direction (x = 0 upstream wall), y = lateral (strip half width 6 m, y = 0 symmetry plane),
z = up (still level 0). Houdini: up = y, lateral = z, Houdini = plan + o.
Tags in comments and records: [measured] FLIP records, [computed] formulas / screens, [literature], [guess], [chosen], [calibrated].
"""
import os, sys, math, json, hashlib, re

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS49 = REPO + "/Tools/GWWaveGen/flip49"
TOOLS48 = REPO + "/Tools/GWWaveGen/flip48"
TOOLS47 = REPO + "/Tools/GWWaveGen/flip47"
TOOLS54 = REPO + "/Tools/GWWaveGen/flip54"
TOOLS = TOOLS54
for _p in (TOOLS48, TOOLS49):
    if _p not in sys.path:
        sys.path.append(_p)           # appended: flip54 names are found first
import g49_common as GC49              # noqa: E402  read only (never patched by this module)
from g49_common import (HY, FFMPEG, G, FPS, is_binary_exact, check_dp, sha256_file, rup, box48, frames_for, t_of_frame,   # noqa: E402,F401
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb,
                        bed_z, bed_grad, bed_sdf, bed_spec, bed_parms, bed_record, bed_kind, bed_formula, is_new, count_particles,
                        sf_solve, sf_tab_string, sf_from_table, sf_vel, sf_target, envelope, set_env, smooth01, sfwave_mod, tag,
                        NEW_DEFAULTS, foot_x, edge_x)

# ------------------------------------------------------------------ places
B54 = REPO + "/Unity/Build/FLIP54"
K54 = B54 + "/k54"
PLAN_DIR = K54 + "/plan"
PLAN = PLAN_DIR + "/plan_K54_frozen.json"
PLAN_REL = "Unity/Build/FLIP54/k54/plan/plan_K54_frozen.json"
CALIB = PLAN_DIR + "/calibration_K0.json"          # the once-only H calibration (written by g54_ana.py calib after the pilot)
OUT_ROOT = "k54/strips"                             # cfg out_root (relative to B54): runs land in Unity/Build/FLIP54/k54/strips/<run_id>
RUNS_ROOT = B54 + "/" + OUT_ROOT
READY = RUNS_ROOT + "/ready"
VERDICT_DIR = K54 + "/verdict"
LOG_DIR = B54 + "/_logs"
BUILD_CHECK = LOG_DIR + "/build_check54.json"      # x54_check.py (hython) writes it; g54_chain.py starts only if all_ok and the hip sha holds
TABLE_DIR = K54 + "/tables"                         # Fenton tables solved under py -3.10 (hython has no scipy)
SCRATCH = B54 + "/_scratch"
TMP_HOUDINI = B54 + "/tmp_houdini"
IDEAS = B54 + "/ideas"
# the scene: FLIP49's, unchanged and never saved by any K54 tool
HIP = REPO + "/Houdini/FLIP49/g49_tank.hiplc"
HIP_REL = "Houdini/FLIP49/g49_tank.hiplc"
HIP_SHA256 = "b358ee3857fe4de3b3faa22c4dc37dd5a48fba5c608c960b4dc464773a80a1a3"   # = Unity/Build/FLIP49/_logs/build_check.json hip_sha256 [measured]
BUILD_CHECK49 = REPO + "/Unity/Build/FLIP49/_logs/build_check.json"
CT_NODE = "/obj/G49_SETUP/CTRL"
SET = "K54"

# ------------------------------------------------------------------ the strip tank (D19B axis + two-slope term + exit sponge)
H0 = 19.0                      # flat depth = DFG-2B's D19B [chosen in FLIP50]
X_TOE = 160.25                 # toe of the 1:10 (D19B) [chosen in FLIP50]
SLOPE_S = 10.0                 # 1:10 (D19B)
LX = 412.0                     # box length = D19B [chosen in FLIP50]
ZB = -19.0                     # box48 zb = the flat bed (D19B; floor pad 2 cells below)
Z_TOP = 17.0                   # box48 top (fixed there) [chosen in FLIP48]
W_STRIP = 6.0                  # quasi-2D strip half width (FLIP49 / FLIP50 strips)
DP = 0.5                       # particle size (grid 1 m) = DFG-2B
IN_X1 = 100.0                  # inlet band 0-100 m (FLIP49 / D19B)
WALL_TAPER = 20.0              # upstream-wall taper of the inlet target (FLIP49)
X_P = 80.0                     # target phase reference x_p (FLIP49)
XA0 = 332.0                    # exit sponge 332-412 m (80 m = flip52b2's DFGB3 sponge band) [chosen]
EX_SIGMA = 1.41                # sponge sigma_max 1/s, rate = sigma chi^2 (FLIP49 EX_SIGMA; 1D reflection below) [chosen in FLIP49]
EX_POW = 2.0
VOL_X = (110.0, XA0 - 5.0)     # drift stage A window (outside both bands; FLIP49 stage A rule: after the inlet band, 5 m before the sponge)
VOL_TAU, VOL_DMAX, VOL_TCAP, VOL_MEASURE = GC49.VOL_TAU, GC49.VOL_DMAX, GC49.VOL_TCAP, GC49.VOL_MEASURE
HOLD_X = GC49.HOLD_X
HOLD_TI = GC49.HOLD_TI         # stage B only (not used by K54; g54_run reads it as g49_run did)
LEVEL_GUARD_M = GC49.LEVEL_GUARD_M
GAUGE_X = (110.0, 128.0, 160.0)   # FLIP49 gauges (Goda & Suzuki pair 110 / 128 m); 160 m < toe 160.25 m
GAUGE_Y = (0.5,)
P1_X_MAX = XA0 - 5.0           # breakers are searched up to 327 m (5 m before the sponge; FLIP49 plan-A rule)
SF_N = 40
T_MAIN = 28.0 / 3.0            # 9.3333 s = DFG-2's T 9.33 s layer (P 28 s / 3) [chosen by the task]
T_A12 = 12.0                   # DM1A anchor period [chosen by the task]
T_WAVE = T_MAIN                # g54_run's fallback when a cfg sf has no T (every K54 cfg has one)
T_END = 90.0                   # strip length (s) [chosen by the task]
JUDGED_K = (2, 3, 4)           # judged breakers: k2-k4 of the FLIP49 event rule (k1 = the first breaker after the ramp) [chosen by the task]
RAMP_PERIODS = 2.0             # inlet ramp = 2 T (FLIP49 RAMP_S 24 s = 2 x 12 s) [chosen in FLIP49]
LEVEL_REGIONS = [
    ("band_core", 20.0, 95.0, 0.0, 1e9),
    ("probe_c", 100.0, 110.0, 0.0, 1e9),
    ("flat", 110.0, 160.0, 0.0, 1e9),
    ("window", VOL_X[0], VOL_X[1], 0.0, 1e9),
    ("slope", 200.0, 250.0, 0.0, 1e9),
    ("shelf_front", 285.0, 325.0, 0.0, 1e9),
    ("sponge_in", XA0, XA0 + 20.0, 0.0, 1e9),
]

# ------------------------------------------------------------------ the arms (bed numbers chosen by the task; landmarks computed below)
SHELF_RANGE = (6.0, 7.5)       # bed_selfcheck covers 6-7.5 m shelves (task)
ARMS = {
    # id: (pg_hL, pg_s2, shelf_h, T, role, label)
    "K0p": (0.0, 0.0, 7.0, T_MAIN, "pilot", "K0 pilot: straight 1:10 onto the 7.0 m shelf, H guess (calibration run, report only)"),
    "K0": (0.0, 0.0, 7.0, T_MAIN, "control", "K0 control: straight 1:10 onto the 7.0 m shelf, H calibrated once (break at h 8.4-9.0 m) and frozen"),
    "K1": (14.0, 8.0, 7.0, T_MAIN, "arm", "K1: 1:10 to h 14 m, then 1:8 onto the 7.0 m shelf"),
    "K2": (14.0, 7.0, 7.0, T_MAIN, "arm", "K2: 1:10 to h 14 m, then 1:7 onto the 7.0 m shelf"),
    "K3": (14.0, 6.0, 7.0, T_MAIN, "arm", "K3: 1:10 to h 14 m, then 1:6 onto the 7.0 m shelf"),
    "K4": (12.5, 7.0, 7.5, T_MAIN, "arm", "K4: 1:10 to h 12.5 m, then 1:7 onto the 7.5 m shelf"),
    "K5": (14.0, 7.0, 6.0, T_MAIN, "bracket", "K5 (wall-side bracket): 1:10 to h 14 m, then 1:7 onto the 6.0 m shelf"),
    "A12": (0.0, 0.0, 7.0, T_A12, "anchor", "A12 (DM1A anchor, validity): straight 1:10 onto the 7.0 m shelf, T 12 s"),
}
ARM_ORDER = ("K0p", "K0", "A12", "K4", "K2", "K1", "K3", "K5")   # launch order: control, validity, the fallback arm K4 first [chosen]
TEST_ARMS = ("K1", "K2", "K3", "K4")                              # arms that can be recommended; K5 is a bracket (report), A12 the validity anchor

# ------------------------------------------------------------------ H rules (registered in the plan)
H_TARGET_HB = 8.7              # centre of the break band h_b 8.4-9.0 m (task) [chosen]
H_BAND_HB = (8.4, 9.0)
H_GUESS = 7.8                  # pilot H at h0 19 m, T 9.33 s [computed, see h_guess_note()]
H_EXP = 1.0 / 0.69             # H ~ h_b^(1/0.69): campaign-B strips BS0 / BS1 (realized H 7.15 / 9.43 m -> h_b 8.07 / 9.78 m) [measured]
H_CLAMP = (0.85, 1.15)         # the calibrated H stays within these factors of the pilot H [chosen]
Q_MAX = 0.85                   # H / Hmax(h0, T) of the Fenton table (FLIP49 kept 0.9; campaign B 0.95) [chosen]


def h_guess_note():
    return ("H_GUESS 7.8 m [computed]: campaign-B 2D strips (h0 17 m, T 12 s, 1:10, dp 0.5) realized H 7.15 m -> h_b 8.07 m and 9.43 m -> 9.78 m "
            "[measured, Unity/Build/FLIP49/strips/BS0*/BS1* pana/planB_ana.json] give h_b ~ H^0.69, so h_b 8.7 m at T 12 needs a realized H of "
            "about 7.97 m; Goda's (2010) breaker index at h_b 8.7 m on 1:10 (T 9.33 / 12 s: Hb 9.24 / 10.17 m) and linear shoaling (19 -> 8.7 m "
            "x1.10 at T 9.33 s; 17 -> 8.7 m x1.13 at T 12 s) carry it to a realized 7.42 m at T 9.33 s, h0 19 m; the FLIP49 inlet realized "
            "0.953 of the input over x 110-160 m [measured, BS0] -> input 7.8 m")


def kdisp(T, h):
    """linear dispersion k(T, h) (Newton)."""
    om = 2.0 * math.pi / float(T)
    k = max(om * om / G, om / math.sqrt(G * float(h)))
    for _ in range(200):
        th = math.tanh(k * h)
        dk = (G * k * th - om * om) / (G * th + G * k * h * (1.0 - th * th))
        k -= dk
        if abs(dk) < 1e-15 * k:
            break
    return k


def cg_lin(T, h):
    k = kdisp(T, h)
    om = 2.0 * math.pi / T
    return 0.5 * (om / k) * (1.0 + 2.0 * k * h / math.sinh(2.0 * k * h))


def goda_hb(T, hb, slope=1.0 / SLOPE_S, A=0.17):
    """Goda (2010) breaker index: Hb = A L0 {1 - exp[-1.5 pi hb / L0 (1 + 15 tan^(4/3) beta)]} [literature]."""
    L0 = G * T * T / (2.0 * math.pi)
    return A * L0 * (1.0 - math.exp(-1.5 * math.pi * hb / L0 * (1.0 + 15.0 * slope ** (4.0 / 3.0))))


def goda_ratio(T_from, T_to, hb=H_TARGET_HB, h0=H0):
    """H(T_to) / H(T_from) at the generation depth h0 for the SAME break depth hb: Goda index over linear shoaling (h0 -> hb) [computed]."""
    def h_in(T):
        return goda_hb(T, hb) / math.sqrt(cg_lin(T, h0) / cg_lin(T, hb))
    return h_in(T_to) / h_in(T_from)


def h_calibrated(H_pilot, hb_measured):
    """the ONCE-only calibration of K0 (registered): H_K0 = H_pilot (8.7 / h_b)^(1/0.69), clamped to [0.85, 1.15] x H_pilot, rounded to
    0.01 m; returns (H, why). No rerun if h_b is already inside 8.4-9.0 m (then H_K0 = H_pilot and the pilot IS K0)."""
    if hb_measured is None or not math.isfinite(float(hb_measured)):
        return None, "no break depth measured"
    hb = float(hb_measured)
    if H_BAND_HB[0] - 1e-9 <= hb <= H_BAND_HB[1] + 1e-9:
        return round(float(H_pilot), 2), "h_b %.2f m inside %.1f-%.1f m: the pilot is K0 (no rerun)" % (hb, H_BAND_HB[0], H_BAND_HB[1])
    f = (H_TARGET_HB / hb) ** H_EXP
    fc = min(max(f, H_CLAMP[0]), H_CLAMP[1])
    return round(float(H_pilot) * fc, 2), "h_b %.2f m outside %.1f-%.1f m: H x (8.7/h_b)^(1/0.69) = x%.4f%s" % (
        hb, H_BAND_HB[0], H_BAND_HB[1], f, "" if fc == f else " clamped to x%.2f" % fc)


def h_a12(H_K0):
    """A12's H (registered): K0's frozen H x goda_ratio(T 9.33 -> 12 s) at h_b 8.7 m (equal predicted break depth) [computed]."""
    return round(float(H_K0) * goda_ratio(T_MAIN, T_A12), 2)


# ------------------------------------------------------------------ beds
SPEC_D19B = dict(k=0.0, x_toe=X_TOE, s=SLOPE_S, h0=H0, on=True, shelf_h=0.0, k_end=None, xk1=240.0, xk2=296.0,
                 ch_y0=55.0, ch_w=4.0, ch_h=0.0, ch_x0=150.0, ch_lx=40.0, s1=0.0, dL=0.0, s2=0.0, **NEW_DEFAULTS)   # = g50_common.SPEC_D19B


def arm_bed(arm):
    hL, s2, sh, T, role, lab = ARMS[arm]
    return float(hL), float(s2), float(sh)


def spec_for(arm):
    """bed_z spec of an arm: D19B with shelf_h and (if any) the FLIP49 two-slope term. K0 / K0p / A12: plain path (k 0, shelf_h 7: the
    FLIP48 plain formula depth = max(shelf_h, h0 - R)); K1-K5: the FLIP49 two-slope path (pgon true)."""
    hL, s2, sh = arm_bed(arm)
    sp = dict(SPEC_D19B)
    sp.update(shelf_h=sh)
    if hL > 0:
        sp.update(pg_hL=hL, pg_s2=s2)
    return sp


def landmarks(arm):
    hL, s2, sh = arm_bed(arm)
    if hL > 0:
        xf = X_TOE + (H0 - hL) * SLOPE_S
        xe = xf + (hL - sh) * s2
    else:
        xf = None
        xe = X_TOE + (H0 - sh) * SLOPE_S
    return dict(x_toe=X_TOE, x_foot=xf, x_edge=xe, h_foot=hL if hL > 0 else None, shelf_h=sh, s2=s2 if hL > 0 else None,
                shelf_len_to_sponge_m=XA0 - xe)


def bed_depth(x, arm):
    """analytic depth of an arm (vectorised), written with the operations of g49_common._rise2 / bed_z (k 0: sech^2 = 1)."""
    import numpy as np
    hL, s2, sh = arm_bed(arm)
    x = np.asarray(x, dtype=np.float64)
    u = x - X_TOE
    if hL > 0:
        uL = (H0 - hL) * SLOPE_S
        R = np.where(u <= 0, 0.0, np.where(u <= uL, u / SLOPE_S, (H0 - hL) + (u - uL) / s2))
    else:
        R = np.maximum(u, 0.0) / SLOPE_S
    return np.maximum(sh, H0 - R)


def d19b_depth(x):
    import numpy as np
    x = np.asarray(x, dtype=np.float64)
    return H0 - np.maximum(x - X_TOE, 0.0) / SLOPE_S


VEX_LINES_PG = ("int pgon() { return (chf(CT+\"pg_hL\") > 0.0 || chf(CT+\"b_end\") > 0.0 || chf(CT+\"lag_xb\") < 1e8) ? 1 : 0; }",
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
VEX_LINES_PLAIN = ("else d = h0 - (x - xt)*sh*sh/chf(CT+\"ridge_s\");",
                   "if (hs > 0.0) d = max(d, hs);",
                   "else { float s = chf(CT+\"ridge_s\"); R = set((x - xt)/s, 1.0/s); }",
                   "if (hs > 0.0 && d <= hs) { d = hs; ddx = 0.0; ddy = 0.0; }")


def vex_text():
    """the VEX source the FLIP49 scene compiled (flip49/g49_tanklib.py VEX head), read as text only."""
    p = TOOLS49 + "/g49_tanklib.py"
    return open(p, encoding="utf8").read() if os.path.exists(p) else ""


def vex_bed_py(x, zl, P):
    """line-by-line Python transliteration of the VEX bedy() / bedgrad() branches used by K54 (k 0, no taper, no channel, no lagoon, no
    flat top, ledge_s1 0): the two-slope branch (pgon: pg_hL > 0) and the plain branch (pg_hL 0, shelf_h > 0). Returns (bed, dbed/dx, dbed/dy)."""
    h0 = P["h0"]
    if P["ridge_on"] < 0.5:
        return -h0, 0.0, 0.0
    hr = P["shelf_h"]
    xt = P["ridge_x0"]
    pgon = (P["pg_hL"] > 0.0 or P["b_end"] > 0.0 or P["lag_xb"] < 1e8)
    k = P["ridge_k"]
    sh = 1.0 / math.cosh(k * abs(zl) / h0)
    S = sh * sh
    if pgon:
        u = x - xt
        if u <= 0.0:
            Rx, Ry = 0.0, 0.0
        else:
            s1 = P["ridge_s"]; hL = P["pg_hL"]; s2 = P["pg_s2"]
            if s2 > 0.0 and hL > hr:
                uL = (h0 - hL) * s1
                Rx, Ry = (u / s1, 1.0 / s1) if u <= uL else ((h0 - hL) + (u - uL) / s2, 1.0 / s2)
            else:
                Rx, Ry = u / s1, 1.0 / s1
        d = max(hr, h0 - Rx * S)
        dd = h0 - Rx * S
        ddx = -(Ry * S - 0.0); ddy = 0.0
        if dd <= hr:
            ddx = 0.0; ddy = 0.0
        return -d, -ddx, -ddy
    d = h0; ddx = 0.0; ddy = 0.0
    if x > xt:
        s = P["ridge_s"]
        d = h0 - (x - xt) * S / s
        dd = d
        if hr > 0.0:
            d = max(d, hr)
        ddx = -(1.0 / s * S - 0.0)
        if hr > 0.0 and dd <= hr:
            ddx = 0.0; ddy = 0.0
    return -d, -ddx, -ddy


def bed_selfcheck(arm):
    """[computed] numpy only, for one arm (extended from flip52b2 g52b2_common.bed_selfcheck to the 6-7.5 m shelves and the plain path):
    (1) the shelf lies in 6-7.5 m; (2) g49_common.bed_z with spec_for(arm) equals the analytic bed to 1e-12 m on the W 6 m strip, laterally
    uniform; (3) upstream of the steep part (x <= x_foot, or x <= x_edge for the plain path) the bed IS DFG-2B's D19B bed; (4) bed_grad =
    (1/10, 0) on the 1:10, (1/s2, 0) on the steep part, (0, 0) on the flat and the shelf; (5) bed_sdf = (z - bed)/sqrt(1 + gx^2); (6) the VEX
    transliteration equals numpy and the VEX source text still contains every line it transliterates; (7) the path (two-slope / plain) is the
    intended one (k 0, no taper, no channel, no flat top, no lagoon); (8) landmarks (foot, edge, edge rule of g49_common.edge_x)."""
    import numpy as np
    hL, s2, sh = arm_bed(arm)
    sp = spec_for(arm)
    lm = landmarks(arm)
    xf, xe = lm["x_foot"], lm["x_edge"]
    out = dict(arm=arm, shelf_h=sh, pg_hL=hL, pg_s2=s2, landmarks=lm)
    out["shelf_in_range_6_7p5"] = bool(SHELF_RANGE[0] - 1e-12 <= sh <= SHELF_RANGE[1] + 1e-12)
    pts = [0.0, X_TOE - 1e-9, X_TOE, X_TOE + 1e-9, 200.0, xe - 1e-9, xe, xe + 1e-9, 300.0, XA0, LX]
    if xf is not None:
        pts += [xf - 1e-9, xf, xf + 1e-9]
    xq = np.union1d(np.arange(0.0, LX + 1e-9, 0.37), pts)
    yq = np.array([0.0, 0.25, 0.5, 1.7, 3.0, 4.25, 5.5, 5.75, 6.0])
    zq = bed_z(xq[None, :], yq[:, None], **sp)
    ana = -bed_depth(xq, arm)
    dz = float(np.abs(zq - ana[None, :]).max())
    out["max_abs_dz_vs_analytic_m"] = dz
    out["equals_analytic_1e12"] = bool(dz < 1e-12)
    out["laterally_uniform"] = bool(np.all(zq == zq[0:1, :]))
    up = xq <= ((xf if xf is not None else xe) + 1e-12)
    out["d19b_upstream_of_steep_part_equal"] = bool(np.allclose(bed_depth(xq[up], arm), d19b_depth(xq[up]), rtol=0, atol=1e-12))
    gx, gy = bed_grad(xq[None, :], yq[:, None], **sp)
    if xf is not None:
        beach = (xq > X_TOE) & (xq <= xf)
        face = (xq > xf) & (xq < xe)
        gref = np.where(beach, 1.0 / SLOPE_S, np.where(face, 1.0 / s2, 0.0))
    else:
        gref = np.where((xq > X_TOE) & (xq < xe), 1.0 / SLOPE_S, 0.0)
    # at the exact kink / edge points the one-sided slopes are both admissible; compare away from them (1e-6 m)
    away = np.ones_like(xq, bool)
    for xk in [X_TOE, xe] + ([xf] if xf is not None else []):
        away &= np.abs(xq - xk) > 1e-6
    out["grad_ok"] = bool(np.allclose(gx[:, away], np.broadcast_to(gref[away], gx[:, away].shape), rtol=0, atol=1e-12) and np.all(gy == 0.0))
    zz = np.array([-21.0, -19.0, -11.0, -7.0, -5.0, 0.0, 3.0])
    sd = bed_sdf(xq[None, :], zz[:, None], 0.0 * zz[:, None], **sp)
    sref = (zz[:, None] - ana[None, :]) / np.sqrt(1.0 + gx[0][None, :] ** 2)
    out["sdf_ok"] = bool(np.allclose(sd, sref, rtol=0, atol=1e-12))
    P = dict(bed_parms(sp)); P["h0"] = H0
    vx = np.array([vex_bed_py(float(x), float(y), P) for y in (0.0, 2.7, 5.5) for x in xq]).reshape(3, len(xq), 3)
    out["vex_transliteration_max_abs_dz_m"] = float(np.abs(vx[..., 0] - ana[None, :]).max())
    out["vex_transliteration_grad_ok"] = bool(np.allclose(vx[:, away, 1], np.broadcast_to(gref[away], vx[:, away, 1].shape), rtol=0, atol=1e-12)
                                              and np.all(vx[..., 2] == 0.0))
    txt = vex_text()
    lines = VEX_LINES_PG if hL > 0 else VEX_LINES_PLAIN
    out["vex_text_has_lines"] = {ln: (ln in txt) for ln in lines}
    common = (sp.get("k_end") is None and float(sp["k"]) == 0.0 and float(sp.get("ch_h") or 0.0) == 0.0 and float(sp.get("s1") or 0.0) == 0.0
              and float(sp.get("b_end") or 0.0) == 0.0 and float(sp.get("x_back", 1e9)) >= 1e8 and float(sp["shelf_h"]) == sh)
    if hL > 0:
        out["path"] = "two-slope (pgon)"
        out["path_ok"] = bool(common and is_new(sp) and float(sp["pg_hL"]) == hL and float(sp["pg_s2"]) == s2 and bed_kind(sp) == "pg_reef_axis_strip")
    else:
        out["path"] = "plain (g48 formula, shelf)"
        out["path_ok"] = bool(common and not is_new(sp) and float(sp.get("pg_hL") or 0.0) == 0.0)
    out["parms"] = {k: P[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h", "h0", "ridge_kend", "ch_h", "ledge_s1", "pg_hL",
                                      "pg_s2", "b_end", "lag_xb")}
    out["x_foot_rule_m"] = foot_x(sp)
    out["x_edge_rule_m"] = float(edge_x(sp))          # first x with depth <= shelf_h + 0.05 m (u3 rule)
    exp_edge_rule = xe - 0.05 * (s2 if hL > 0 else SLOPE_S)
    out["landmarks_ok"] = bool((xf is None or abs(out["x_foot_rule_m"] - xf) < 1e-9) and abs(out["x_edge_rule_m"] - exp_edge_rule) < 0.051)
    dmin, dmax = float(bed_depth(xq, arm).min()), float(bed_depth(xq, arm).max())
    out["depth_min_max_m"] = [dmin, dmax]
    out["depth_range_ok"] = bool(abs(dmin - sh) < 1e-12 and abs(dmax - H0) < 1e-12)
    out["sponge_over_shelf"] = bool(XA0 >= xe + 30.0)
    out["ok"] = bool(out["shelf_in_range_6_7p5"] and out["equals_analytic_1e12"] and out["laterally_uniform"] and out["d19b_upstream_of_steep_part_equal"]
                     and out["grad_ok"] and out["sdf_ok"] and out["vex_transliteration_max_abs_dz_m"] < 1e-12 and out["vex_transliteration_grad_ok"]
                     and all(out["vex_text_has_lines"].values()) and out["path_ok"] and out["landmarks_ok"] and out["depth_range_ok"]
                     and out["sponge_over_shelf"])
    out["tag"] = "computed (numpy)"
    return out


def iribarren(arm, T=None, H_ref=None):
    """report only [computed]: the local slope over the 15 m before the 1:10 onset point of the bedscreen model is not recomputed here; this
    gives xi = tan(beta_steep) / sqrt(H/L0) with H = the pilot H (deep-water steepness proxy) for the steep part and for 1:10."""
    hL, s2, sh = arm_bed(arm)
    T = T or ARMS[arm][3]
    H = H_ref or H_GUESS
    L0 = G * T * T / (2.0 * math.pi)
    tb = (1.0 / s2) if hL > 0 else (1.0 / SLOPE_S)
    return dict(slope=tb, xi0=tb / math.sqrt(H / L0), H_ref_m=H, T_s=T, L0_m=L0, tag="computed (report only)")


# ------------------------------------------------------------------ sponge reflection (1D theory, flip45 r45_gen_numbers.reflection copied)
def sponge_kr(T, h, band=None, sigma=EX_SIGMA, p=EX_POW, dx=0.25):
    """reflection |B/A| of the exit sponge (rate sigma chi^p, wall behind) for a normally incident linear wave of period T at depth h:
    Peric & Abdel-Maksoud (2018) 1D model as in flip45 r45_gen_numbers.reflection (mode 'normal', theta 0) [computed]."""
    import numpy as np
    band = float(band if band is not None else LX - XA0)
    k = kdisp(T, h); om = 2.0 * math.pi / T
    n = max(1, int(round(band / dx)))
    chi = (np.arange(n) + 0.5) / n
    rate = sigma * chi ** p
    ks = []
    for r in rate:
        kj = np.sqrt(k * k * (1 + 1j * r / om) + 0j)
        if kj.imag < 0:
            kj = -kj
        ks.append(kj)
    rr = -1.0 + 0j
    d = band / n
    for j in range(len(ks) - 1, -1, -1):
        kj = ks[j]
        rr = rr * np.exp(2j * kj * d)
        Yv = (1 + rr) / (1j * kj * (1 - rr))
        kprev = ks[j - 1] if j > 0 else k + 0j
        rr = (1j * kprev * Yv - 1) / (1j * kprev * Yv + 1)
    return float(abs(rr))


# ------------------------------------------------------------------ names, paths
def run_id(arm, H, T=None):
    hL, s2, sh = arm_bed(arm)
    T = T or ARMS[arm][3]
    bed = ("s10h%s" % tag(sh)) if hL <= 0 else ("hL%ss%sh%s" % (tag(hL), tag(s2), tag(sh)))
    return "K54_%s_%s_T%s_H%s_dp0p5" % (arm, bed, tag(round(T, 2)), tag(round(float(H), 2)))


def run_dir(rid):
    return RUNS_ROOT + "/" + rid


def cfg_path(rid):
    return READY + "/" + rid + ".json"


def table_file(T, H):
    return TABLE_DIR + "/sf_h19_T%s_H%s.json" % (tag(round(T, 4)), tag(round(float(H), 3)))


def module_shas():
    out = {}
    for nm in ("g54_common.py", "g54_pcfg.py", "g54_plan.py", "g54_run.py", "g54_chain.py", "g54_mkcopy.py", "x54_check.py", "g54_ana.py"):
        p = os.path.join(TOOLS54, nm)
        out["flip54/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g49_common.py", "g49_tanklib.py", "g49_run.py", "g49_chain.py", "g49_build_tank.py", "g49_pcfg.py", "g49_planB.py", "g49_periodic_ana.py"):
        p = os.path.join(TOOLS49, nm)
        out["flip49/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    for nm in ("g48_common.py", "g48_analyze.py", "g48_peak_metrics.py"):
        p = os.path.join(TOOLS48, nm)
        out["flip48/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    p = os.path.join(TOOLS47, "g47_sfwave.py")
    out["flip47/g47_sfwave.py"] = sha256_file(p)[:16] if os.path.exists(p) else None
    return out


def guard_out(path, allow_scratch=True):
    """never write outside Unity/Build/FLIP54."""
    o = os.path.abspath(path).replace("\\", "/")
    if not (o.lower() + "/").startswith(B54.lower() + "/"):
        raise SystemExit("output %s is outside Unity/Build/FLIP54; not written" % o)
    os.makedirs(o, exist_ok=True)
    return o


def clean(o):
    import numpy as np
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return None if not math.isfinite(v) else v
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def jdump(o, p):
    guard_out(os.path.dirname(p))
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)


def jload(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def plan_sha_ok():
    sp = PLAN + ".sha256"
    if not (os.path.exists(PLAN) and os.path.exists(sp)):
        return False
    return open(sp, encoding="utf8").read().split()[0] == sha256_file(PLAN)


def runs_exist():
    """K54 strip runs that have started (a run_c*.json or a chain.log in a run folder)."""
    import glob
    out = []
    for d in sorted(glob.glob(RUNS_ROOT + "/K54_*")):
        if os.path.isdir(d) and (glob.glob(d + "/run_c*.json") or os.path.exists(d + "/chain.log")):
            out.append(os.path.basename(d))
    return out
