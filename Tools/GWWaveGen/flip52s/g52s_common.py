# -*- coding: utf-8 -*-
"""FLIP52S plan DFG-S: constants and helpers shared by the FLIP52S tools (numpy only; read by hython and by py -3.10).
2026-10-18 written new (Claude). Nothing in flip45-flip52b is edited; read only (imported):
  g50_common (flip50) -> g49_common / g48_common: hython / ffmpeg paths, dp checks, the bed path (bed_z, bed_grad, bed_sdf, bed_spec,
    bed_parms, bed_record: the DFG-S step goes through the FLIP48 PLAIN path, k 0, slope 1:3 from the toe x 108 m, shelf_h 6 m),
    count_particles (the scene's seeding rule), process helpers.
  g50_dirfield (flip50): kdisp, DirField with kind 'shelf' (the WKB field over the step).
  g52_common (flip52): the DFG-2 sea (P 28 s, harmonics 3/4/5, equal weights, the plan E X2 direction set, a_sum = DM1A input sum),
    the DFG-2 tank (flat 20 m, Lx 290 m, half width 100 m, bands, exit sponge), box52 (box48 with the top as a parameter).
The frozen plan is Unity/Build/FLIP52S/plan/plan_DFGS_frozen.json (+ .sha256); g52s_pcfg.py checks every number here against it.

DFG-S in one line (design candidate S7 of flip52s/dfgs_screen.py [chosen]): DFG-2's sea, tank and bands unchanged, plus a LATERALLY UNIFORM
step over the full width: flat 20 m to the toe x 108 m, a 1:3 face up to the edge x 150 m, a 6.0 m shelf to the tank end (under the exit
sponge). The N-layer table is re-phased by WKB over the step (DirField kind 'shelf'): every component has phase 0 at (145, 0) at
t = 43 + 28 m s. The bed needs NO new VEX term: the FLIP48 plain bed path (VEX bedy / bedgrad of flip49/g49_tanklib.py, read by
flip52/g52_tanklib.py) with ridge_on 1, ridge_k 0, ridge_x0 108, ridge_s 3, shelf_h 6 is exactly this step, and its numpy mirror
g49_common.bed_z / bed_grad / bed_sdf too (bed_selfcheck below; the hython build checks OUT_BED and the SDF against numpy).
Coordinates as FLIP48-52: plan x = wave direction (x = 0 upstream wall), y = lateral (y = 0 symmetry plane), z = up (still level 0).
Houdini: up = y, lateral = z, Houdini = plan + o. The FLIP52S scene keeps the FLIP52 node names (G52_SETUP / G52_SIM / G52_READ / G52_SURF) so
that the N-layer VEX of flip52/g52_tanklib.py is used unchanged; it is a separate file Houdini/FLIP52S/g52s_tank.hiplc.
Tags used in comments and records: [measured] [computed] [literature] [guess] [chosen].
"""
import os, sys, math, json, hashlib

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS49 = REPO + "/Tools/GWWaveGen/flip49"
TOOLS50 = REPO + "/Tools/GWWaveGen/flip50"
TOOLS51 = REPO + "/Tools/GWWaveGen/flip51"
TOOLS52 = REPO + "/Tools/GWWaveGen/flip52"
TOOLS52S = REPO + "/Tools/GWWaveGen/flip52s"
for _p in (TOOLS50, TOOLS52):
    if _p not in sys.path:
        sys.path.append(_p)           # appended: flip52s names are found first
import numpy as np                     # noqa: E402
import g50_common as GC50              # noqa: E402  read only
import g50_dirfield as DF50            # noqa: E402  read only (kdisp, DirField, bed_h)
import g52_common as GC52              # noqa: E402  read only (the DFG-2 sea and tank)
from g50_common import (HY, FFMPEG, G, FPS, is_binary_exact, check_dp, sha256_file, rup, frames_for, t_of_frame,   # noqa: E402,F401
                        unthrottle_self, rss_gb, hython_running, wait_no_hython, keep_awake, free_gb,
                        bed_z, bed_grad, bed_sdf, bed_spec, bed_parms, bed_record, bed_kind, bed_formula, is_new, count_particles,
                        sf_tab_string, sf_target, smooth01, tag, NEW_DEFAULTS)

TOOLS = TOOLS52S
B52S = REPO + "/Unity/Build/FLIP52S"
HIP = REPO + "/Houdini/FLIP52S/g52s_tank.hiplc"
HIP_REL = "Houdini/FLIP52S/g52s_tank.hiplc"
PLAN_DIR = B52S + "/plan"
PLAN = PLAN_DIR + "/plan_DFGS_frozen.json"
PLAN_REL = "Unity/Build/FLIP52S/plan/plan_DFGS_frozen.json"
AMENDMENTS = PLAN_DIR + "/amendments.jsonl"
TABLE_DIR = B52S + "/tables"
LOG_DIR = B52S + "/_logs"
SCREEN_DIR = B52S + "/screens"
BUILD_CHECK = LOG_DIR + "/build_check52s.json"
BUILD_INPUTS = LOG_DIR + "/build_inputs52s.json"
PCHECK_ROOT = B52S + "/pcheck"         # the short 0.5 m pipeline check (no 1.0 m smoke: dp 1.0 damps the 5.6 s layer, AM-DFG3)
RUNS_ROOT = B52S + "/runs"             # the judged 0.5 m run
CT_NODE = "/obj/G52_SETUP/CTRL"
SCRATCH_PREFIX = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52S/_scratch/"

# ------------------------------------------------------------------ the tank (DFG-2's, unchanged: flip52/g52_common)
H0 = GC52.H0                   # 20 m
LX = GC52.LX                   # 290 m
W_MAIN = GC52.W_MAIN           # 100 m
W_STRIP = GC52.W_STRIP         # 6 m (build checks only)
ZB = GC52.ZB                   # -20 m
Z_TOP = GC52.Z_TOP             # +20 m
X_SHORE = LX                   # no shoreline in the box (particle checks use the box end)
IN_X1 = GC52.IN_X1             # inlet band end 50 m
WALL_TAPER = GC52.WALL_TAPER   # 12.5 m
SD0 = GC52.SD0                 # side band inner edge 70 m
SD_BAND = GC52.SD_BAND         # 30 m
SD_GEN = GC52.SD_GEN           # 180 m
SD_SW = GC52.SD_SW             # 210 m
SD_SIGMA = GC52.SD_SIGMA       # 1.41
SD_POW = GC52.SD_POW           # 2
SD_TAPER = GC52.SD_TAPER       # 7.5 m (the target tapers to 0 at the outer side wall y = 100 m)
SD_CORE_Y1 = W_MAIN - SD_TAPER # 92.5 m: the side-band core ends where the wall taper starts (G4 lesson of DFG-2)
XA0 = GC52.XA0                 # exit sponge 210-290 m (over the 6 m shelf)
ABS_SIGMA = GC52.ABS_SIGMA     # 1.0
ABS_POW = GC52.ABS_POW         # 2
RAMP_S = GC52.RAMP_S           # 14 s
VOL_X = GC52.VOL_X             # stage A window (60, 205) m
HOLD_X = GC52.HOLD_X
VOL_TAU, VOL_DMAX, VOL_TCAP, VOL_MEASURE = GC52.VOL_TAU, GC52.VOL_DMAX, GC52.VOL_TCAP, GC52.VOL_MEASURE
HOLD_TI = GC52.HOLD_TI
LEVEL_GUARD_M = GC52.LEVEL_GUARD_M
INTERIOR_X = GC52.INTERIOR_X   # (60, 205) m
INTERIOR_Y = GC52.INTERIOR_Y   # 65 m (rows y > 65 m NaN in the metrics, = DFG-2)
N1_STILL_X = GC52.N1_STILL_X   # (60, 205) m online still offset window
T_WAVE = 7.0                   # descriptor period = the middle harmonic
TP = 7.0

# ------------------------------------------------------------------ the step (design candidate S7) [chosen]
X_TOE = 108.0                  # toe of the face (depth 20 m)
SLOPE_S = 3.0                  # face 1:3
H_TOP = 6.0                    # shelf depth (m)
X_EDGE = X_TOE + SLOPE_S * (H0 - H_TOP)        # 150.0 m: the crest line (edge) of the step
SPEC_STEP = dict(GC52.SPEC_FLAT20)
SPEC_STEP.update(x_toe=X_TOE, s=SLOPE_S, shelf_h=H_TOP)   # k 0, k_end None, ch_h 0, s1 0, no FLIP49 terms -> the FLIP48 plain path
BED_DF = dict(h0=H0, x_toe=X_TOE, s=SLOPE_S, kind="shelf", h_s=H_TOP)   # the same bed for g50_dirfield (= dfgs_screen.bed_spec(108, 3, 6))

# ------------------------------------------------------------------ records / windows of the analysis
R3_Y = GC52.R3_Y               # far vertical section y 40 m
R4_X = (90.0, 200.0)           # r4 per-y sections and the r5 surface crop (DFG-2 90-190 m; +10 m for a breaker / bore on the shelf)
R4_Y1 = INTERIOR_Y             # r4 lateral extent 0-65 m
R4_Z = GC52.R4_Z               # (-10, 18) m
SCAN_X = (90.0, 200.0)         # 'conv' scan window (converged crest predicted x 127.5 m, onset x 144.5-149.5 m [computed, screen])
ONSET_X = (90.0, 205.0)        # r2 lip search for the onset (the exit sponge starts at 210 m)
GAUGE_X = (60.0, 100.0, 145.0, 190.0)          # run gauges (report): G2f line, 8 m before the toe, the design focus, the shelf
GAUGE_Y = GC52.GAUGE_Y         # (0.5, 15, 30, 45, 60) m (G2f at x 60 m)
GROUP_WIN = (-8.0, 6.0)        # per-group window around t_fn (s): converged t_fn - 1.5, onset t_fn + 0 .. 0.75, lip / bore later [screen]

LEVEL_REGIONS_52S = [
    ("band_core", WALL_TAPER, IN_X1, 0.0, SD0),
    ("probe_c", IN_X1, 60.0, 0.0, SD0),
    ("flat", INTERIOR_X[0], X_TOE - 3.0, 0.0, INTERIOR_Y),
    ("face", X_TOE, X_EDGE, 0.0, INTERIOR_Y),
    ("shelf", X_EDGE, INTERIOR_X[1], 0.0, INTERIOR_Y),
    ("window", VOL_X[0], VOL_X[1], 0.0, 1e9),
    ("focus", 135.0, 155.0, 0.0, 10.0),
    ("side_gen", INTERIOR_X[0], SD_GEN, SD0, 1e9),
    ("exit_entry", 190.0, XA0, 0.0, INTERIOR_Y),
    ("sponge", XA0, LX, 0.0, 1e9),
    ("asym_centre", 60.0, 105.0, 0.0, 10.0),
    ("asym_side", 60.0, 105.0, 55.0, 65.0),
]

# ------------------------------------------------------------------ the sea (DFG-2, unchanged) and the DFG-S focus
P_S = GC52.P_S                 # 28 s
HARMONICS = GC52.HARMONICS     # (3, 4, 5)
A_SUM = GC52.A_SUM             # 6.331240146143423 m = DM1A input sum, NOT enlarged
DSPEC = ("hyb", 60.0, 28.0, 85.0, 17)                # the plan E X2 set (= DFG-2)
X_F = 145.0                    # design focus x (on the upper face, h 7.67 m) [chosen, screen S7]
T_F = 43.0                     # first focus time (s) = ceil(t_full 38.7 + 3.9) [computed by the screen's ray arrival rule]
N_GROUPS = 3
FOCI = tuple(T_F + P_S * m for m in range(N_GROUPS))      # 43, 71, 99 s
TABLE_X = (0.0, 214.0)
TABLE_Y = (0.0, W_MAIN)
TABLE_DX = 1.0
FIELDS_LAYER = GC52.FIELDS_LAYER
FIELDS_SHARED = GC52.FIELDS_SHARED
MAX_LAYERS = GC52.MAX_LAYERS


def h_of(x):
    """still-water depth of the step (plan x, m)."""
    return max(H_TOP, H0 - max(float(x) - X_TOE, 0.0) / SLOPE_S)


def step_depth(x):
    """the analytic step, vectorised: max(h_top, h0 - max(x - x_toe, 0) / s)."""
    x = np.asarray(x, float)
    return np.maximum(H_TOP, H0 - np.maximum(x - X_TOE, 0.0) / SLOPE_S)


def dirset(spec=DSPEC):
    return GC52.dirset(spec)


def freqset(P=P_S, ns=HARMONICS, fw="eq"):
    return GC52.freqset(P, ns, fw)


def components(a_sum=A_SUM):
    """the inlet components at the generation depth h0 20 m: a_nj = a_sum wf_n wd_j (bit for bit DFG-2's)."""
    om, wf = freqset()
    th, wd = dirset()
    a = float(a_sum) * np.outer(wf, wd)
    k = np.asarray(DF50.kdisp(om, H0), float)
    return dict(P=P_S, harmonics=list(HARMONICS), om=om, wf=wf, k=k, th=th, wd=wd, a=a, a_sum=float(a_sum), h0=H0, x_f=X_F, t_f=T_F)


def kdisp(om, h):
    return np.asarray(DF50.kdisp(om, h), float)


def kp(h=H0):
    return float(kdisp(2 * math.pi / TP, h))


def box52(dp, Lx=LX, W=W_MAIN, x0=0.0, zb=ZB, z_top=Z_TOP, floor_pad=2, side_pad=0):
    """the DFG-2 box (flip52 g52_common.box52: box48 with the top +20 m as a parameter)."""
    return GC52.box52(dp, Lx=Lx, W=W, x0=x0, zb=zb, z_top=z_top, floor_pad=floor_pad, side_pad=side_pad)


# ------------------------------------------------------------------ the bed: numpy path, analytic step and the VEX text it relies on
VEX_LINES = ("float bedy(float x; float zl) {",
             "if (pgon()) return bedy_pg(x, zl);",
             "else d = h0 - (x - xt)*sh*sh/chf(CT+\"ridge_s\");",
             "if (hs > 0.0) d = max(d, hs);",
             "vector2 bedgrad(float x; float zl) {",
             "else { float s = chf(CT+\"ridge_s\"); R = set((x - xt)/s, 1.0/s); }",
             "if (hs > 0.0 && d <= hs) { d = hs; ddx = 0.0; ddy = 0.0; }",
             "float d = (y - bedy(x, zl))/sqrt(1.0 + gr.x*gr.x + gr.y*gr.y);")


def _vex_text():
    """the VEX source the FLIP52 scene compiles (flip50/g50_tanklib.VEX_HEAD, itself flip49/g49_tanklib's head), read as text only."""
    out = []
    for p in (TOOLS49 + "/g49_tanklib.py", TOOLS50 + "/g50_tanklib.py"):
        if os.path.exists(p):
            out.append(open(p, encoding="utf8").read())
    return "\n".join(out)


def vex_bedy_py(x, zl, P):
    """a line-by-line Python transliteration of the VEX bedy() / bedgrad() plain branch (pgon() false, ledge_s1 0, ch_h 0, k(x) = ridge_k)
    for the CTRL parms P; returns (bed height, d bed/dx, d bed/dy). Used only to show, before Houdini is free, that the existing VEX text
    gives the step; the hython build compares the real VEX output with numpy (build_check52s.json)."""
    h0 = P["h0"]; xt = P["ridge_x0"]; s = P["ridge_s"]; hs = P["shelf_h"]; k = P["ridge_k"]
    if P["ridge_on"] < 0.5:
        return -h0, 0.0, 0.0
    d = h0
    if x > xt:
        sh = 1.0 / math.cosh(k * zl / h0)
        d = h0 - (x - xt) * sh * sh / s
        if hs > 0.0:
            d = max(d, hs)
    zb_ = -d
    d = h0; ddx = 0.0; ddy = 0.0
    if x > xt:
        a = k * zl / h0
        sh = 1.0 / math.cosh(a); S = sh * sh; th = math.tanh(a)
        Rx, Ry = (x - xt) / s, 1.0 / s
        d = h0 - Rx * S
        ddx = -(Ry * S - 2.0 * Rx * S * th * 0.0 * zl / h0)
        ddy = 2.0 * Rx * S * th * k / h0
        if hs > 0.0 and d <= hs:
            d = hs; ddx = 0.0; ddy = 0.0
    return zb_, -ddx, -ddy


def bed_selfcheck():
    """[computed] numpy only: (1) the g49 / g48 plain path with SPEC_STEP equals the analytic step bit for bit on a grid that contains the
    toe and the edge, laterally uniform; (2) bed_grad = (1/3, 0) on the open face, (0, 0) elsewhere; (3) bed_sdf = (z - bed)/sqrt(1 + gx^2);
    (4) g50_dirfield.bed_h with BED_DF = the same depths; (5) the VEX transliteration on the CTRL parms of the cfg equals numpy and the VEX
    source text still contains every line it transliterates; (6) the plain path is used (no FLIP49 term, no ledge, no channel, no taper)."""
    sp = dict(SPEC_STEP)
    out = {}
    xq = np.union1d(np.arange(0.0, LX + 1e-9, 0.37), [0.0, X_TOE - 1e-9, X_TOE, X_TOE + 1e-9, 129.0, X_EDGE - 1e-9, X_EDGE, X_EDGE + 1e-9, LX])
    yq = np.array([0.0, 0.5, 13.7, 50.0, 69.5, 92.5, 99.5, 100.0])
    zq = bed_z(xq[None, :], yq[:, None], **sp)
    ana = -step_depth(xq)
    out["equals_analytic_bit"] = bool(np.array_equal(zq, np.broadcast_to(ana, zq.shape)))
    out["laterally_uniform"] = bool(np.all(zq == zq[0:1, :]))
    gx, gy = bed_grad(xq[None, :], yq[:, None], **sp)
    face = (xq > X_TOE) & (xq < X_EDGE)
    gref = np.where(face, 1.0 / SLOPE_S, 0.0)
    out["grad_ok"] = bool(np.allclose(gx, np.broadcast_to(gref, gx.shape), rtol=0, atol=1e-15) and np.all(gy == 0.0))
    zz = np.array([-21.0, -19.0, -7.0, -5.0, 0.0, 3.0])
    sd = bed_sdf(xq[None, :], zz[:, None], 0.0 * zz[:, None], **sp)
    sref = (zz[:, None] - ana[None, :]) / np.sqrt(1.0 + gref[None, :] ** 2)
    out["sdf_ok"] = bool(np.allclose(sd, sref, rtol=0, atol=1e-12))
    out["dirfield_bed_h_ok"] = bool(np.allclose(DF50.bed_h(xq, BED_DF), step_depth(xq), rtol=0, atol=1e-12))
    P = dict(bed_parms(sp)); P["h0"] = H0
    vx = np.array([vex_bedy_py(float(x), float(y), P) for y in (0.0, 47.3, 99.5) for x in xq]).reshape(3, len(xq), 3)
    out["vex_transliteration_max_abs_dz_m"] = float(np.abs(vx[..., 0] - ana[None, :]).max())
    out["vex_transliteration_grad_ok"] = bool(np.allclose(vx[..., 1], gref[None, :], rtol=0, atol=1e-15) and np.all(vx[..., 2] == 0.0))
    txt = _vex_text()
    out["vex_text_has_lines"] = {ln: (ln in txt) for ln in VEX_LINES}
    out["plain_path"] = bool(not is_new(sp) and sp.get("k_end") is None and float(sp["k"]) == 0.0 and float(sp.get("ch_h") or 0.0) == 0.0
                             and float(sp.get("s1") or 0.0) == 0.0 and bed_kind(sp) == "ridge_shelf")
    out["parms"] = {k: P[k] for k in ("ridge_on", "ridge_x0", "ridge_k", "ridge_s", "shelf_h", "h0", "ridge_kend", "ch_h", "ledge_s1", "pg_hL",
                                      "b_end", "lag_xb")}
    out["x_edge_m"] = X_EDGE
    out["depth_min_max_m"] = [float(step_depth(xq).min()), float(step_depth(xq).max())]
    out["ok"] = bool(out["equals_analytic_bit"] and out["laterally_uniform"] and out["grad_ok"] and out["sdf_ok"] and out["dirfield_bed_h_ok"]
                     and out["vex_transliteration_max_abs_dz_m"] < 1e-12 and out["vex_transliteration_grad_ok"]
                     and all(out["vex_text_has_lines"].values()) and out["plain_path"]
                     and out["depth_min_max_m"] == [H_TOP, H0] and abs(X_EDGE - 150.0) < 1e-12)
    out["note"] = ("no new VEX bed term: the FLIP48 plain branch of bedy / bedgrad / bedsdf_out (flip49/g49_tanklib.py VEX head, unchanged) with "
                   "ridge_x0 108, ridge_s 3, shelf_h 6, ridge_k 0 IS the step; hython checks the compiled VEX (OUT_BED heights, the collision SDF, "
                   "the particle seeding) against numpy in build_check52s.json")
    return out


# ------------------------------------------------------------------ run ids and paths
RID = {"pcheck": "PDFGS_step3h6_dp0p5_t10", "main": "DFGS_step3h6_xf145_dp0p5"}


def run_id(kind):
    return RID[kind]


def root_of(kind):
    return PCHECK_ROOT if kind == "pcheck" else RUNS_ROOT


def run_dir(kind):
    return root_of(kind) + "/" + RID[kind]


def cfg_path(kind):
    return root_of(kind) + "/ready/" + RID[kind] + ".json"


# ------------------------------------------------------------------ small helpers
def guard_out(path, allow_scratch=False):
    o = os.path.abspath(path).replace("\\", "/")
    ok = (o.lower() + "/").startswith(B52S.lower() + "/")
    if allow_scratch and o.lower().startswith(SCRATCH_PREFIX.lower()):
        ok = True
    if not ok:
        raise SystemExit("output %s is outside Unity/Build/FLIP52S%s; not written" % (o, " or the scratchpad" if allow_scratch else ""))
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


CODE_FILES = ("g52s_common.py", "g52s_table.py", "g52s_mkcopy.py", "g52s_build_tank.py", "x52s_build.py", "g52s_run.py", "g52s_chain.py",
              "g52s_pcfg.py", "g52s_ana.py", "g52s_video.py", "dfgs_screen.py", "dfgs_plan.py")


def module_shas():
    out = {}
    for nm in CODE_FILES:
        p = os.path.join(TOOLS52S, nm)
        out["flip52s/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
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
    """cfg['sf']: a LINEAR DESCRIPTOR at the middle harmonic T 7 s and h0 20 m (T, L, c, k for the analysis tools; NOT a forcing table)."""
    om = 2 * math.pi / T_WAVE
    k = float(kdisp(om, H0))
    L = 2 * math.pi / k
    return dict(descriptor=True, kind="linear descriptor at the middle harmonic T 7 s, h0 20 m (NOT a forcing table; sf_on 0)",
                h=H0, T=T_WAVE, H=(None if H_ref is None else float(H_ref)), N=1, k=k, L=L, c=L / T_WAVE, Ubar=0.0, B=[0.0], E=[0.0, 0.0],
                P_sea=P_S, harmonics=list(HARMONICS), note=note or "")
