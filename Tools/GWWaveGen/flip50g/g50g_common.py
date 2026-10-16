# -*- coding: utf-8 -*-
"""FLIP50 DG1 (option D round 3; AM-D20, Unity/Build/FLIP50/plan/dg1_frozen.json): what every flip50g tool shares (numpy only; read by
hython and by py -3.10). 2026-10-17 written new (Claude).

DG1 = DM1A with ONE change, the bed: z_b,DG1(x, y) = z_D19B(x) - dz(x, y),
    dz = D (1 - exp(-(y/b)^2)) exp(-(y/Y)^2) r(x),  r = S((x - x1)/(x2 - x1)) (1 - S((x - x3)/(x4 - x3))),  S = smoothstep,
    D 3 m, b 8 m, Y 25 m, x1 238, x2 262, x3 320, x4 350 m [chosen: a pair of shallow grooves beside the axis at the break, a rip-channel /
    spur-and-groove analogue, not a measured site; only gravity, the bed and the incoming waves act; a_sum unchanged].

No file of flip46-flip50 is edited (their sha256 are frozen in dg1_frozen.json 'untouched' and checked by every DG1 launch). The DG1 tools
run the unchanged flip50 code after an IN-MEMORY patch of the bed functions (patch_modules):
  g48_common.bed_spec  -> + the groove keys gr_on, gr_D, gr_b, gr_Y, gr_x1..gr_x4 (from cfg bed.groove, else from CTRL parms gr_*; none if absent)
  g48_common.bed_z / bed_grad, g49_common.bed_z / bed_grad -> the original function minus dz / grad dz when the spec carries gr_on 1
  g49_common.bed_parms / bed_kind / bed_formula / bed_record -> + the groove (CTRL parms, kind '+groove_DG1', formula, bed.groove)
  g50_common names imported from g49_common are re-bound to the patched functions; g49_common.bed_sdf and count_particles use the
  patched module globals (so the particle model, the SDF, the leak check, the column volume, h_b and the g46 sections all see the groove).
A spec WITHOUT gr_* keys (every existing cfg) goes through the original functions unchanged (g50g_pcfg.py check regenerates the six
existing cfgs under the patch and compares them byte for byte).
Tags: [measured] [computed] [literature] [guess] [chosen] (in Japanese records: 【測定】【計算】【文献】【推測】【選び】).
"""
import os, sys, json, math, time, hashlib

sys.dont_write_bytecode = True
TOOLS50G = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS50 = REPO + "/Tools/GWWaveGen/flip50"
TOOLS49 = REPO + "/Tools/GWWaveGen/flip49"
TOOLS48 = REPO + "/Tools/GWWaveGen/flip48"
TOOLS46 = REPO + "/Tools/GWWaveGen/flip46"
for _p in (TOOLS50, TOOLS49, TOOLS48):
    if _p not in sys.path:
        sys.path.append(_p)
import numpy as np                 # noqa: E402
import g50_common as GC50          # noqa: E402  read only (attributes re-bound in memory by patch_modules, never the file)
import g49_common as GC49          # noqa: E402
import g48_common as G48           # noqa: E402

B50 = GC50.B50
LOGS = B50 + "/_logs"
HIP_G = REPO + "/Houdini/FLIP50/g50_tank_g.hiplc"
HIP_G_REL = "Houdini/FLIP50/g50_tank_g.hiplc"
BUILD_CHECK_G = LOGS + "/build_check_g.json"
BUILD_CHECK_G_REL = "Unity/Build/FLIP50/_logs/build_check_g.json"
BUILD_INPUTS_G = LOGS + "/build_inputs_g.json"
BUILD_LOG_G = LOGS + "/build_g.log"
DG1_FROZEN = GC50.PLAN_DIR + "/dg1_frozen.json"
DG1_FROZEN_REL = "Unity/Build/FLIP50/plan/dg1_frozen.json"
DG1_SHA256 = "4f9d24be18a61003b02dc95c37b89019d5bd5422a84afa723ae5fbcbe45737a6"   # AM-D20 (amendments.jsonl)
AMENDMENT = "AM-D20"
SCRATCH = B50 + "/_scratch/dg1"
AUTO_STATUS = LOGS + "/auto_D_status.txt"

# the frozen groove (dg1_frozen.json geometry.parameters; frozen() asserts equality) [chosen]
GR = dict(D=3.0, b=8.0, Y=25.0, x1=238.0, x2=262.0, x3=320.0, x4=350.0)
GR_KEYS = ("D", "b", "Y", "x1", "x2", "x3", "x4")
CTRL_KEYS = ("gr_on",) + tuple("gr_" + k for k in GR_KEYS)
SPEC_GR_ON = dict([("gr_on", 1.0)] + [("gr_" + k, float(GR[k])) for k in GR_KEYS])
SPEC_GR_OFF = dict(SPEC_GR_ON, gr_on=0.0)          # the hip default: D19B (switch-off check of T0G)

# runs (dg1_frozen.json implementation.run_ids / cfg_rule)
RUN_SMOKE = "SMOKE50DG1_D19Bgr_T12_dp1p0"
RUN_MAIN = "DG1_D19Bgr_T12_th80_dp0p5"
BASE_MAIN = dict(path=B50 + "/runs/ready/DM1A_D19B_T12_th80_dp0p5.json", sha16="44e5846e46339a6f", run_id="DM1A_D19B_T12_th80_dp0p5")
BASE_SMOKE = dict(path=B50 + "/smoke/ready/SMOKE50DA_D19B_T12_dp1p0.json", sha16="5896358f10ffe228", run_id="SMOKE50DA_D19B_T12_dp1p0")
DM1A_RUN = B50 + "/runs/DM1A_D19B_T12_th80_dp0p5"
DF1A_ID = "DF1A_D19B_T10_th80_dp0p5"
DF1A_RUN = B50 + "/runs/" + DF1A_ID
SMOKE50DA_RUN = B50 + "/smoke/SMOKE50DA_D19B_T12_dp1p0"
SMOKE_RUN = B50 + "/smoke/" + RUN_SMOKE
MAIN_RUN = B50 + "/runs/" + RUN_MAIN
ONSET_ANCHOR = 256.5           # DM1 judged median centre onset x (m) [measured]; dm1a_applicability: DM1A median within +-10 m
ONSET_TOL = 10.0

FLIP50G_FILES = ("g50g_common.py", "g50g_tanklib.py", "g50g_build_tank.py", "x50g_build.py", "g50g_pcfg.py", "g50g_chain.py", "g50g_run.py",
                 "g50g_ana.py", "g50g_video.py")


# ====================================================================== the frozen file
def sha256_file(p):
    return GC50.sha256_file(p)


def frozen():
    """dg1_frozen.json after checking its sha256 against the .sha256 file and AM-D20, and the geometry against GR."""
    if not os.path.exists(DG1_FROZEN):
        raise SystemExit("missing %s" % DG1_FROZEN)
    sh = sha256_file(DG1_FROZEN)
    side = open(DG1_FROZEN + ".sha256", encoding="utf8").read().split()[0]
    if sh != DG1_SHA256 or side != DG1_SHA256:
        raise SystemExit("dg1_frozen.json sha256 %s (.sha256 file %s) differs from AM-D20 %s: the frozen rules changed" % (sh[:16], side[:16], DG1_SHA256[:16]))
    d = json.load(open(DG1_FROZEN, encoding="utf8"))
    gp = d["geometry"]["parameters"]
    if any(float(gp[k]) != GR[k] for k in GR_KEYS):
        raise SystemExit("dg1_frozen.json geometry.parameters %s differ from GR %s" % ({k: gp[k] for k in GR_KEYS}, GR))
    return d


def frozen_parameters():
    """geometry.parameters exactly as frozen (the cfg bed.groove sub-dict, cfg_rule)."""
    return dict(frozen()["geometry"]["parameters"])


def frozen_ref():
    return dict(path=DG1_FROZEN_REL, sha256=DG1_SHA256, amendment=AMENDMENT, parameters=dict(GR))


# ====================================================================== the groove (numpy)
def groove_of(spec):
    """the groove parameters carried by a bed spec (keys gr_*), or None when absent, switched off (gr_on < 0.5) or D = 0."""
    if not spec or "gr_on" not in spec:
        return None
    if float(spec["gr_on"]) < 0.5:
        return None
    g = {k: float(spec.get("gr_" + k, GR[k])) for k in GR_KEYS}
    if g["D"] == 0.0:
        return None
    return g


def _S(u):
    v = np.clip(u, 0.0, 1.0)
    return v * v * (3.0 - 2.0 * v)


def _Sp(u):
    return np.where((u > 0.0) & (u < 1.0), 6.0 * u * (1.0 - u), 0.0)


def gr_r(x, g):
    x = np.asarray(x, dtype=np.float64)
    return _S((x - g["x1"]) / (g["x2"] - g["x1"])) * (1.0 - _S((x - g["x3"]) / (g["x4"] - g["x3"])))


def gr_L(y, g):
    y = np.asarray(y, dtype=np.float64)
    return (1.0 - np.exp(-(y / g["b"]) ** 2)) * np.exp(-(y / g["Y"]) ** 2)


def gr_dz(x, y, g=None):
    """dz(x, y) >= 0 (m): how much deeper than D19B the groove bed is. Exactly 0 on y = 0, for x <= x1 and for x >= x4 [computed]."""
    g = g or GR
    return g["D"] * gr_L(y, g) * gr_r(x, g)


def gr_grad(x, y, g=None):
    """(d dz/dx, d dz/dy), the same expressions as the VEX gr_dz of g50g_tanklib."""
    g = g or GR
    x = np.asarray(x, dtype=np.float64); y = np.asarray(y, dtype=np.float64)
    u1 = (x - g["x1"]) / (g["x2"] - g["x1"]); u3 = (x - g["x3"]) / (g["x4"] - g["x3"])
    sa = _S(u1); sb = 1.0 - _S(u3)
    r = sa * sb
    rp = _Sp(u1) / (g["x2"] - g["x1"]) * sb - sa * _Sp(u3) / (g["x4"] - g["x3"])
    eb = np.exp(-(y / g["b"]) ** 2); eY = np.exp(-(y / g["Y"]) ** 2)
    Ly = (1.0 - eb) * eY
    Lp = 2.0 * y * (eb / (g["b"] * g["b"]) - (1.0 - eb) / (g["Y"] * g["Y"])) * eY
    return g["D"] * Ly * rp, g["D"] * Lp * r


def groove_keys_from(cfg=None, parms=None):
    """the gr_* spec keys of a cfg (bed.groove first, as bed_spec reads cfg bed first) or of CTRL parms; {} when the cfg has no groove."""
    b = (cfg or {}).get("bed") if isinstance((cfg or {}).get("bed"), dict) else None
    if b:
        gd = b.get("groove")
        if not isinstance(gd, dict):
            return {}
        out = {"gr_on": 1.0 if gd.get("on", True) else 0.0}
        out.update({"gr_" + k: float(gd[k]) for k in GR_KEYS})
        return out
    P = parms if parms is not None else ((cfg or {}).get("parms") or {})
    if "gr_on" not in P:
        return {}
    return {k: float(P.get(k, SPEC_GR_ON[k])) for k in CTRL_KEYS}


def _strip(spec):
    rest = {k: v for k, v in spec.items() if not k.startswith("gr_")}
    gr = {k: v for k, v in spec.items() if k.startswith("gr_")}
    return rest, gr


# ====================================================================== the in-memory patch
_ORIG = {}
_STATE = dict(patched=False, hip=False)


def _orig(mod, nm):
    key = (mod.__name__, nm)
    if key not in _ORIG:
        _ORIG[key] = getattr(mod, nm)
    return _ORIG[key]


def _mk_z(orig):
    def bed_z(x, y_lat=0.0, **spec):
        rest, gr = _strip(spec)
        z = orig(x, y_lat, **rest)
        g = groove_of(gr)
        if g is None:
            return z
        return z - gr_dz(x, y_lat, g)
    bed_z.__doc__ = "DG1 patch of %s.%s: original minus the groove dz when the spec carries gr_on 1 (g50g_common)" % (orig.__module__, orig.__name__)
    return bed_z


def _mk_grad(orig):
    def bed_grad(x, y_lat=0.0, **spec):
        rest, gr = _strip(spec)
        gx, gy = orig(x, y_lat, **rest)
        g = groove_of(gr)
        if g is None:
            return gx, gy
        dx, dy = gr_grad(x, y_lat, g)
        return gx - dx, gy - dy
    bed_grad.__doc__ = "DG1 patch of %s.%s: original minus grad dz (g50g_common)" % (orig.__module__, orig.__name__)
    return bed_grad


def _mk_spec(orig):
    def bed_spec(cfg=None, parms=None):
        sp = orig(cfg, parms)
        sp.update(groove_keys_from(cfg, parms))
        return sp
    bed_spec.__doc__ = "DG1 patch of %s.bed_spec: + gr_* from cfg bed.groove or CTRL parms gr_* (g50g_common)" % orig.__module__
    return bed_spec


def groove_formula(g):
    return ("groove (DG1, AM-D20, chosen): z_b <- z_b - dz, dz = D*(1-exp(-(y/b)^2))*exp(-(y/Y)^2)*S((x-x1)/(x2-x1))*(1-S((x-x3)/(x4-x3))), "
            "S(u) = 3v^2-2v^3, v = clamp(u,0,1); D %g m, b %g m, Y %g m, x1 %g, x2 %g, x3 %g, x4 %g m"
            % (g["D"], g["b"], g["Y"], g["x1"], g["x2"], g["x3"], g["x4"]))


def patch_modules(hip=False):
    """patch the bed functions of g48_common / g49_common / g50_common in memory (idempotent). hip=True also points g50_common.HIP to the
    groove hip Houdini/FLIP50/g50_tank_g.hiplc (chain, run, build). Returns the g50_common module."""
    if not _STATE["patched"]:
        o48z, o48g, o48s = _orig(G48, "bed_z"), _orig(G48, "bed_grad"), _orig(G48, "bed_spec")
        o49z, o49g = _orig(GC49, "bed_z"), _orig(GC49, "bed_grad")
        o49p, o49k, o49f, o49r = _orig(GC49, "bed_parms"), _orig(GC49, "bed_kind"), _orig(GC49, "bed_formula"), _orig(GC49, "bed_record")
        G48.bed_z = _mk_z(o48z)
        G48.bed_grad = _mk_grad(o48g)
        G48.bed_spec = _mk_spec(o48s)          # g49_common.bed_spec calls G48.bed_spec -> carries gr_* through
        GC49.bed_z = _mk_z(o49z)
        GC49.bed_grad = _mk_grad(o49g)

        def bed_parms(spec):
            p = o49p(spec)
            if any(k.startswith("gr_") for k in spec):
                p.update({k: float(spec.get(k, SPEC_GR_OFF[k])) for k in CTRL_KEYS})
            return p

        def bed_kind(spec):
            k = o49k(spec)
            return k + "+groove_DG1" if groove_of(spec) else k

        def bed_formula(spec):
            f = o49f(spec)
            g = groove_of(spec)
            return f + "; " + groove_formula(g) if g else f

        def bed_record(spec, box=None):
            d = o49r(spec, box)            # max/min depth through the patched module global bed_z
            g = groove_of(spec)
            if g:
                fp = frozen_parameters()
                d["groove"] = fp if all(float(fp[k]) == g[k] for k in GR_KEYS) else dict(g)
            return d
        GC49.bed_parms, GC49.bed_kind, GC49.bed_formula, GC49.bed_record = bed_parms, bed_kind, bed_formula, bed_record
        for nm in ("bed_z", "bed_grad", "bed_sdf", "bed_spec", "bed_parms", "bed_record", "bed_kind", "bed_formula", "count_particles"):
            setattr(GC50, nm, getattr(GC49, nm))      # g50_common imported these names from g49_common at its import
        _orig(GC50, "module_shas")
        GC50.module_shas = module_shas_g
        _STATE["patched"] = True
    if hip and not _STATE["hip"]:
        _orig(GC50, "HIP")
        GC50.HIP = HIP_G
        _STATE["hip"] = True
    return GC50


def orig_fn(mod_name, nm):
    """the original (unpatched) function, e.g. orig_fn('g49_common', 'bed_z')."""
    return _ORIG[(mod_name, nm)]


def module_shas_g():
    """g50_common.module_shas (flip47-flip50, unchanged) + the flip50g files."""
    out = _ORIG.get(("g50_common", "module_shas"), GC50.module_shas)
    if out is module_shas_g:
        raise RuntimeError("module_shas_g: original g50_common.module_shas not kept")
    out = out()
    for nm in FLIP50G_FILES:
        p = os.path.join(TOOLS50G, nm)
        out["flip50g/" + nm] = sha256_file(p)[:16] if os.path.exists(p) else None
    return out


# ====================================================================== untouched files (dg1_frozen.json 'untouched')
def check_untouched(fz=None):
    """every file the DM1A / DF1A runs and their chain gate depend on still has its frozen sha. Returns dict(ok, bad, n)."""
    fz = fz or frozen()
    u = fz["untouched"]
    bad = []
    n = 0
    for key in ("hip", "build_check", "plan"):
        p = os.path.join(REPO, u[key]["path"])
        n += 1
        if not os.path.exists(p) or sha256_file(p) != u[key]["sha256"]:
            bad.append(u[key]["path"])
    try:
        bc = json.load(open(os.path.join(REPO, u["build_check"]["path"]), encoding="utf8"))
        if bc.get("hip_sha256") != u["build_check"]["hip_sha256_inside"]:
            bad.append("build_check.json hip_sha256 inside")
    except Exception as e:
        bad.append("build_check.json unreadable %r" % e)
    for rel, sh in u["tables"].items():
        n += 1
        p = os.path.join(REPO, rel)
        if not os.path.exists(p) or sha256_file(p) != sh:
            bad.append(rel)
    for rel, s16 in u["cfgs"].items():
        n += 1
        p = os.path.join(REPO, rel)
        if not os.path.exists(p) or sha256_file(p)[:16] != s16:
            bad.append(rel)
    base = REPO + "/Tools/GWWaveGen/"
    for rel, s16 in u["module_sha256_16"].items():
        n += 1
        p = base + rel
        if not os.path.exists(p) or sha256_file(p)[:16] != s16:
            bad.append(rel)
    return dict(ok=not bad, bad=bad, n_files=n)


# ====================================================================== the start condition (dg1_frozen.json implementation.order 1)
def _status_lines():
    if not os.path.exists(AUTO_STATUS):
        return []
    return open(AUTO_STATUS, encoding="utf8", errors="replace").read().splitlines()


def dm1a_applicability():
    """geometry.dm1a_applicability: DM1A judged median centre onset x within 256.5 +- 10 m (pana/planD_ana.json medians_judged.x_on)."""
    p = os.path.join(DM1A_RUN, "pana", "planD_ana.json")
    if not os.path.exists(p):
        return dict(ok=False, why="DM1A pana/planD_ana.json is missing", path=p)
    d = json.load(open(p, encoding="utf8"))
    x = (d.get("medians_judged") or {}).get("x_on")
    ok = x is not None and math.isfinite(float(x)) and abs(float(x) - ONSET_ANCHOR) <= ONSET_TOL
    return dict(ok=bool(ok), x_on_median=x, anchor=ONSET_ANCHOR, tol=ONSET_TOL,
                why=None if ok else "DM1A median onset x %s outside %g +- %g m: stop and ask (geometry.dm1a_applicability)" % (x, ONSET_ANCHOR, ONSET_TOL))


def order_state():
    """implementation.order 1 + not_covered_ask_first: DF1A chain ended and analysed (auto_D_status.txt), DF1A not PASS and without a hard
    health item, DM1A applicability. Returns dict(ok, items, why[])."""
    L = _status_lines()
    why = []
    ended = [l for l in L if (DF1A_ID + " CHAIN_COMPLETE") in l or (DF1A_ID + " CHAIN_INCOMPLETE_GIVEUP") in l]
    ana = [l for l in L if (DF1A_ID + " ANA_DONE") in l or (DF1A_ID + " ANA_FAILED") in l]
    launched = [l for l in L if (DF1A_ID + " CHAIN_LAUNCHED") in l]
    noauto = [l for l in L if "NO_AUTO_NEXT" in l]
    dm1a_done = [l for l in L if ("DM1A_D19B_T12_th80_dp0p5 ANA_DONE" in l or "DM1A_D19B_T12_th80_dp0p5 ANA_FAILED" in l
                                  or "DM1A_D19B_T12_th80_dp0p5 CHAIN_INCOMPLETE_GIVEUP" in l)]
    if not launched and not dm1a_done and not noauto:
        why.append("DM1A has not been analysed yet, so DF1A has not launched (auto_D.py); wait for the DF1A chain")
    elif not launched:
        why.append("DF1A has not launched%s: if it never launches, stop and ask whether DG1 runs directly on DM1A (not_covered_ask_first[0])"
                   % ((" (auto_D: %s)" % noauto[-1][:200]) if noauto else ""))
    elif not ended:
        why.append("the DF1A chain has not ended yet (no CHAIN_COMPLETE / CHAIN_INCOMPLETE_GIVEUP line in %s)" % AUTO_STATUS)
    elif not ana and any((DF1A_ID + " CHAIN_INCOMPLETE_GIVEUP") in l for l in ended):
        # review 2026-10-17: auto_D.py does not analyse a chain it gave up on, so no ANA line will ever come; an incomplete DF1A is the
        # hard health item 'run incomplete' -> read-only diagnosis, ask the user (not_covered_ask_first[1]); behaviour unchanged (blocked)
        why.append("the DF1A chain gave up incomplete (CHAIN_INCOMPLETE_GIVEUP, never analysed by auto_D): hard health item 'run incomplete' -> "
                   "read-only diagnosis; DG1 Houdini steps wait for the user (not_covered_ask_first[1])")
    elif not ana:
        why.append("the DF1A analysis is not written yet (no ANA_DONE / ANA_FAILED line)")
    dfa = os.path.join(DF1A_RUN, "pana", "planD_ana.json")
    dec = None
    if ended and ana:
        if os.path.exists(dfa):
            dec = (json.load(open(dfa, encoding="utf8")).get("decision") or {})
            v = str(dec.get("verdict"))
            if v.startswith("health"):
                why.append("DF1A has a hard health item (%s): DG1 Houdini steps wait for the user (not_covered_ask_first[1])" % dec.get("next"))
            if v == "pass":
                why.append("DF1A PASS: DD3 first by the frozen pass rule, then DG1 (not_covered_ask_first[2])")
        else:
            why.append("DF1A pana/planD_ana.json is missing (ANA_FAILED?): read-only diagnosis, then ask")
    ap = dm1a_applicability()
    if not ap["ok"]:
        why.append(ap["why"])
    return dict(ok=not why, why=why, df1a_launched=bool(launched), df1a_ended=ended[-1] if ended else None, df1a_ana=ana[-1] if ana else None,
                df1a_decision=dec, dm1a_applicability=ap)


# ====================================================================== the DG1 launch gate (dg1_frozen.json run.launch_gate) added to g50_chain's
def cfg_groove_ok(cfg):
    """cfg parms gr_* = the frozen values with gr_on 1, cfg bed.groove = geometry.parameters, case dg1_frozen sha, hip / build_check keys."""
    P = cfg.get("parms") or {}
    bad = []
    if any(P.get(k) != SPEC_GR_ON[k] for k in CTRL_KEYS):
        bad.append("cfg parms gr_* %s differ from the frozen %s" % ({k: P.get(k) for k in CTRL_KEYS}, SPEC_GR_ON))
    gd = (cfg.get("bed") or {}).get("groove") or {}
    if any(gd.get(k) != GR[k] for k in GR_KEYS):
        bad.append("cfg bed.groove %s differs from geometry.parameters" % gd)
    cs = cfg.get("case") or {}
    if cs.get("dg1_frozen_sha256") != DG1_SHA256 or cs.get("dg1_frozen") != DG1_FROZEN_REL:
        bad.append("cfg case.dg1_frozen / dg1_frozen_sha256 differ from AM-D20")
    if cfg.get("hip") != HIP_G_REL or cfg.get("build_check") != BUILD_CHECK_G_REL:
        bad.append("cfg hip / build_check keys are not the groove hip %s / %s" % (HIP_G_REL, BUILD_CHECK_G_REL))
    if cfg.get("run_id") not in (RUN_SMOKE, RUN_MAIN):
        bad.append("run_id %s is neither %s nor %s" % (cfg.get("run_id"), RUN_SMOKE, RUN_MAIN))
    return bad


def smoke_passed():
    p = os.path.join(SMOKE_RUN, "pana", "smoke_DG1.json")
    if not os.path.exists(p):
        return False, "smoke gates not read yet (%s missing; py -3.10 -B g50g_ana.py smoke %s)" % (p, SMOKE_RUN)
    d = json.load(open(p, encoding="utf8"))
    if d.get("ok") is not True:
        return False, "the DG1 smoke gates failed: %s" % [k for k, v in (d.get("gates") or {}).items() if v is not True]
    # review 2026-10-17: the smoke must have run on the groove hip the main run will use (a rebuild after the smoke changes the sha)
    sm = (d.get("validity") or {}).get("hip_sha256") or []
    cur = sha256_file(HIP_G) if os.path.exists(HIP_G) else None
    bc = json.load(open(BUILD_CHECK_G, encoding="utf8")).get("hip_sha256") if os.path.exists(BUILD_CHECK_G) else None
    if not (len(sm) == 1 and sm[0] == cur == bc):
        return False, ("the DG1 smoke ran on groove hip sha %s but the current hip / build_check_g are %s / %s: rebuilt after the smoke -> "
                       "re-smoke before the main run" % ([str(s)[:16] for s in sm], str(cur)[:16], str(bc)[:16]))
    return True, None


def chain_gate_extra(cfg, order_ok=None):
    """extra gate items of a DG1 launch (list of reasons; empty = may start)."""
    bad = []
    try:
        fz = frozen()
    except SystemExit as e:
        return [str(e)]
    bad += cfg_groove_ok(cfg)
    u = check_untouched(fz)
    if not u["ok"]:
        bad.append("files the DM1A / DF1A runs depend on changed (dg1_frozen.json untouched): %s" % u["bad"][:8])
    if os.path.exists(BUILD_CHECK_G):
        c = json.load(open(BUILD_CHECK_G, encoding="utf8"))
        if (c.get("dg1") or {}).get("sha256") != DG1_SHA256:
            bad.append("build_check_g.json was not built against dg1_frozen.json %s" % DG1_SHA256[:16])
        if not ((c.get("DG1_switch") or {}).get("ok")):
            bad.append("build_check_g.json switch-off check not ok")
    else:
        bad.append("%s is missing (T0G: py -3.10 -B %s/x50g_build.py)" % (BUILD_CHECK_G, TOOLS50G))
    if not os.path.exists(HIP_G):
        bad.append("groove hip %s is missing" % HIP_G)
    st = order_state()
    if not st["ok"]:
        if order_ok:
            pass                      # recorded by the caller (the user's answer named in --order-ok)
        else:
            bad += ["order: " + w for w in st["why"]]
    if cfg.get("run_id") == RUN_MAIN:
        ok, why = smoke_passed()
        if not ok:
            bad.append(why)
    return bad


# ====================================================================== readings of two frozen gates (only a dated amendment changes them)
READINGS_DEFAULT = dict(particles_T0G="literal", smoke_b="literal_per_column")
READINGS_ALLOWED = dict(particles_T0G=("literal", "quadrature"), smoke_b=("literal_per_column", "medians", "model", "medians+model"))


def amendments():
    p = GC50.PLAN_DIR + "/amendments.jsonl"
    out = []
    if os.path.exists(p):
        for ln in open(p, encoding="utf8"):
            if ln.strip():
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    return out


def readings():
    """(readings, source amendment id). Default = the literal frozen text. A later dated amendment of plan_D_frozen.json (amendments.jsonl,
    id after AM-D20) with a dict 'dg1_readings' (keys particles_T0G / smoke_b, values in READINGS_ALLOWED) changes the reading; this code never
    decides it."""
    r = dict(READINGS_DEFAULT)
    src = None
    for e in amendments():
        dr_ = e.get("dg1_readings")
        if isinstance(dr_, dict) and e.get("id") not in (None, AMENDMENT) and e.get("plan") == GC50.PLAN_D_REL:
            for k, v in dr_.items():
                if k in READINGS_ALLOWED and v in READINGS_ALLOWED[k]:
                    r[k] = v
                    src = e.get("id")
    return r, src


def column_quadrature(dp):
    """sum over the seeding columns ((i + 1/2) dp, (j + 1/2) dp) of the half tank of dz / dp = the added water in particles without the
    vertical lattice [computed]."""
    xs = (np.arange(int(round(GC50.LX / dp))) + 0.5) * dp
    ys = (np.arange(int(round(GC50.W_MAIN / dp))) + 0.5) * dp
    return float(gr_dz(xs[None, :], ys[:, None]).sum() * dp * dp / dp ** 3)


# ====================================================================== numpy self-checks (dg1_frozen.json pre_run_gates_T0G.numpy_self_checks)
def self_checks(light=False):
    """the T0G numpy self-checks. light=True skips the dp 0.5 particle count (hython build: dp 1.0 only)."""
    patch_modules()
    t0 = time.time()
    fz = frozen()
    num = fz["geometry"]["numbers"]
    D19 = dict(GC50.SPEC_D19B)
    SG = dict(D19, **SPEC_GR_ON)
    oz = orig_fn("g49_common", "bed_z"); og = orig_fn("g49_common", "bed_grad")
    out = {}
    # 1. lateral landmarks
    xs = np.arange(0.0, 412.0001, 0.5)
    ys = np.arange(0.0, 140.0001, 0.05)
    dz2 = gr_dz(xs[None, :], ys[:, None])
    out["dz_y0_exact_zero"] = bool(np.all(gr_dz(xs, 0.0) == 0.0))
    out["dz_y0p5_max_m"] = float(gr_dz(xs, 0.5).max())
    out["dz_y0p5_le_0p0125"] = bool(out["dz_y0p5_max_m"] <= 0.0125)
    yf = np.arange(12.0, 12.7, 0.0005)
    xm = np.arange(262.0, 320.0001, 0.5)
    dzf = gr_dz(xm[None, :], yf[:, None])
    i = np.unravel_index(int(np.argmax(dzf)), dzf.shape)
    out["dz_max_m"] = float(dzf.max()); out["dz_max_at_y_m"] = float(yf[i[0]])
    out["dz_max_ok"] = bool(abs(out["dz_max_m"] - 2.134) <= 0.001 and 12.3 <= out["dz_max_at_y_m"] <= 12.4 and dz2.max() <= dzf.max() + 1e-12)
    tab = {float(k): v for k, v in num["dz_by_y_m"].items()}
    dev = max(abs(float(GR["D"] * gr_L(y, GR)) - v) for y, v in tab.items())
    out["dz_by_y_table_max_dev_m"] = dev; out["dz_by_y_table_ok"] = bool(dev <= 6e-5)
    rtab = {float(k): v for k, v in num["r_by_x"].items()}
    rdev = max(abs(float(gr_r(x, GR)) - v) for x, v in rtab.items())
    out["r_by_x_table_max_dev"] = rdev; out["r_by_x_table_ok"] = bool(rdev <= 6e-5)
    # 2. unchanged regions: dz = 0 for x <= 238 and x >= 350; bed bit for bit there; far field
    ya = np.arange(-6.0, 146.0001, 0.25)
    xo = np.concatenate([np.arange(0.0, 238.0001, 0.25), np.arange(350.0, 412.0001, 0.25)])
    out["dz_zero_outside_x238_350"] = bool(np.all(gr_dz(xo[None, :], ya[:, None]) == 0.0))
    out["bed_equals_D19B_bit_outside"] = bool(np.array_equal(GC50.bed_z(xo[None, :], ya[:, None], **SG), oz(xo[None, :], ya[:, None], **D19)))
    out["bed_equals_D19B_bit_on_axis"] = bool(np.array_equal(GC50.bed_z(xs, 0.0 * xs, **SG), oz(xs, 0.0 * xs, **D19)))
    yfar = np.arange(70.0, 140.0001, 0.05)
    out["dz_max_y_ge_70_m"] = float(gr_dz(xs[None, :], yfar[:, None]).max())
    yfar2 = np.arange(95.0, 140.0001, 0.05)
    out["dz_max_y_ge_95_m"] = float(gr_dz(xs[None, :], yfar2[:, None]).max())
    out["far_field_ok"] = bool(out["dz_max_y_ge_70_m"] < 2e-3 and out["dz_max_y_ge_95_m"] < 2e-6)
    # 3. gradient against central finite differences; SDF sign and value
    rng = np.random.default_rng(20261017)
    xp = rng.uniform(225.0, 365.0, 4000); yp = rng.uniform(-70.0, 70.0, 4000)
    h = 1e-5
    gx, gy = GC50.bed_grad(xp, yp, **SG)
    fx = (GC50.bed_z(xp + h, yp, **SG) - GC50.bed_z(xp - h, yp, **SG)) / (2 * h)
    fy = (GC50.bed_z(xp, yp + h, **SG) - GC50.bed_z(xp, yp - h, **SG)) / (2 * h)
    kink = np.abs(xp - GC50.X_TOE) < 2 * h
    out["grad_fd_max_abs"] = float(max(np.abs(gx - fx)[~kink].max(), np.abs(gy - fy)[~kink].max()))
    out["grad_ok"] = bool(out["grad_fd_max_abs"] < 1e-6)
    zp = rng.uniform(-20.0, 3.0, 4000)
    sd = GC50.bed_sdf(xp, zp, yp, **SG)
    bz = GC50.bed_z(xp, yp, **SG)
    ref = (zp - bz) / np.sqrt(1.0 + gx * gx + gy * gy)
    out["sdf_max_abs_dev"] = float(np.abs(sd - ref).max())
    out["sdf_sign_ok"] = bool(np.all(np.sign(sd) == np.sign(zp - bz)))
    out["sdf_ok"] = bool(out["sdf_sign_ok"] and out["sdf_max_abs_dev"] < 1e-12)
    # 4. switch-off and D = 0 give D19B bit for bit (bed, grad, sdf, particle count dp 1.0)
    xg = np.arange(150.0, 412.0001, 0.37); yg = np.arange(-6.0, 146.0001, 0.41)
    X, Y = np.meshgrid(xg, yg)
    Z = -10.0 + 0.0 * X
    sw = {}
    for nm, sp in (("gr_on_0", dict(D19, **SPEC_GR_OFF)), ("gr_D_0", dict(D19, **dict(SPEC_GR_ON, gr_D=0.0)))):
        a1 = np.array_equal(GC50.bed_z(X, Y, **sp), oz(X, Y, **D19))
        g1, g2 = GC50.bed_grad(X, Y, **sp); h1, h2 = og(X, Y, **D19)
        a2 = np.array_equal(g1, h1) and np.array_equal(g2, h2)
        sdf_ref = (np.asarray(Z, float) - oz(X, Y, **D19)) / np.sqrt(1.0 + h1 * h1 + h2 * h2)     # g49_common.bed_sdf with the original functions
        a3 = np.array_equal(GC50.bed_sdf(X, Z, Y, **sp), sdf_ref)
        sw[nm] = dict(bed=bool(a1), grad=bool(a2), sdf=bool(a3))
    n1_off = GC50.count_particles(dict(D19, **SPEC_GR_OFF), GC50.LX, GC50.W_MAIN, 1.0, zb=GC50.ZB)[0]
    n1_d19 = GC50.count_particles(D19, GC50.LX, GC50.W_MAIN, 1.0, zb=GC50.ZB)[0]
    sw["count_dp1_off_equals_D19B"] = bool(n1_off == n1_d19 == 665000)
    out["switch_off"] = sw
    out["switch_off_ok"] = bool(all(all(v.values()) for k, v in sw.items() if isinstance(v, dict)) and sw["count_dp1_off_equals_D19B"])
    # 5. particle model: the groove adds 8 x 3928 m3 particles at dp 0.5 and 1 x at dp 1.0 (within 0.5 %).
    #    literal reading (default): the lattice count difference count_particles_g - count_particles(D19B).
    #    'quadrature' reading (only if a dated amendment names it in dg1_readings.particles_T0G): the same column model without the
    #    vertical lattice, sum over the seeding columns of dz / dp (the added water the columns hold), against the same 0.5 %.
    vol = float(num["added_water_m3_half_tank"])
    rd, rsrc = readings()
    n1_g = GC50.count_particles(SG, GC50.LX, GC50.W_MAIN, 1.0, zb=GC50.ZB)[0]
    pc = dict(dp1_D19B=int(n1_d19), dp1_groove=int(n1_g), dp1_added=int(n1_g - n1_d19), dp1_expected=vol,
              dp1_added_rel_err=float((n1_g - n1_d19) / vol - 1.0), dp1_quadrature=column_quadrature(1.0))
    pc["dp1_lattice_ok"] = bool(abs(pc["dp1_added_rel_err"]) <= 0.005)
    pc["dp1_quadrature_ok"] = bool(abs(pc["dp1_quadrature"] / vol - 1.0) <= 0.005)
    if not light:
        n5_d = GC50.count_particles(D19, GC50.LX, GC50.W_MAIN, 0.5, zb=GC50.ZB)[0]
        n5_g = GC50.count_particles(SG, GC50.LX, GC50.W_MAIN, 0.5, zb=GC50.ZB)[0]
        pc.update(dp0p5_D19B=int(n5_d), dp0p5_groove=int(n5_g), dp0p5_added=int(n5_g - n5_d), dp0p5_expected=8.0 * vol,
                  dp0p5_added_rel_err=float((n5_g - n5_d) / (8.0 * vol) - 1.0), dp0p5_quadrature=column_quadrature(0.5))
        pc["dp0p5_lattice_ok"] = bool(abs(pc["dp0p5_added_rel_err"]) <= 0.005 and n5_d == 5383840)
        pc["dp0p5_quadrature_ok"] = bool(abs(pc["dp0p5_quadrature"] / (8.0 * vol) - 1.0) <= 0.005 and n5_d == 5383840)
    pc["reading"] = rd["particles_T0G"]; pc["reading_source"] = rsrc
    sel = "quadrature" if rd["particles_T0G"] == "quadrature" else "lattice"
    pc["dp1_ok"] = pc["dp1_%s_ok" % sel]
    if not light:
        pc["dp0p5_ok"] = pc["dp0p5_%s_ok" % sel]
    pc["note"] = ("the lattice count difference is not 8 x 3928 within 0.5 % by construction: the seeding lattice zb + (k + 1/2) dp quantizes "
                  "each column's added depth (phase of the 1:10 slope against the lattice; columns at the shoreline that had no particle); the "
                  "column quadrature sum(dz)/dp equals the frozen volume [computed]")
    out["particles"] = pc
    # added water (half tank) against the frozen number
    xx = np.arange(200.0, 360.0001, 0.01); yv = np.arange(0.0, 140.0001, 0.01)
    trap = getattr(np, "trapezoid", None) or np.trapz
    v2 = float(trap(gr_r(xx, GR), xx) * trap(GR["D"] * gr_L(yv, GR), yv))
    out["added_water_m3"] = v2; out["added_water_ok"] = bool(abs(v2 - vol) <= 0.1)
    keys = ["dz_y0_exact_zero", "dz_y0p5_le_0p0125", "dz_max_ok", "dz_by_y_table_ok", "r_by_x_table_ok", "dz_zero_outside_x238_350",
            "bed_equals_D19B_bit_outside", "bed_equals_D19B_bit_on_axis", "far_field_ok", "grad_ok", "sdf_ok", "switch_off_ok", "added_water_ok"]
    out["ok"] = bool(all(out[k] for k in keys) and pc["dp1_ok"] and (light or pc.get("dp0p5_ok")))
    out["failed"] = [k for k in keys if not out[k]] + ["particles." + k for k in ("dp1_ok", "dp0p5_ok") if k in pc and not pc[k]]
    out["cpu_s"] = round(time.time() - t0, 2)
    out["tags"] = "computed (numpy); thresholds of dg1_frozen.json pre_run_gates_T0G.numpy_self_checks"
    return out


def dg1_build_ok(CHK):
    """the DG1 items of build_check_g.json (pre_run_gates_T0G.hython_build_check_g + numpy self-checks). Returns (ok, items)."""
    g = lambda k: CHK.get(k) or {}
    items = dict(
        DG1_strip=bool(g("DG1_strip").get("bed_ok") and g("DG1_strip").get("sdf_ok") and g("DG1_strip").get("particles_ok")),
        DG1_3d=bool(g("DG1_3d").get("bed_ok") and g("DG1_3d").get("sdf_ok")),
        DG1_3d_groove_box=bool(g("DG1_3d_groove_box").get("ok")),
        DG1_3d_particles_dp1=bool(g("DG1_3d_particles_dp1").get("particles_ok")),
        DG1_switch=bool(g("DG1_switch").get("ok")),
        DG1_numpy=bool(g("DG1_numpy").get("ok")),
        untouched=bool(g("untouched_before_save").get("ok")),
        dg1_frozen=bool(g("dg1").get("sha256") == DG1_SHA256))
    return bool(all(items.values())), items


def switch_numbers(CHK):
    """switch-off: with gr_on 0 the groove hip gives D19B (bed < 1 mm vs numpy D19B) and 665,000 particles at dp 1.0."""
    b = CHK.get("D19B_3d") or {}
    p = CHK.get("D19B_3d_particles_dp1") or {}
    s = CHK.get("D19B_strip") or {}
    out = dict(bed_3d_lt_1mm=bool(b.get("bed_vex_numpy_lt_1mm")), bed_3d_max_abs_dz_m=b.get("bed_max_abs_dz_m"),
               strip_lt_1mm=bool(s.get("bed_vex_numpy_lt_1mm")), particles_dp1=p.get("particles"), particles_dp1_is_665000=bool(p.get("particles") == 665000),
               spec_gr_on=(b.get("spec") or {}).get("gr_on"))
    out["ok"] = bool(out["bed_3d_lt_1mm"] and out["strip_lt_1mm"] and out["particles_dp1_is_665000"] and out["spec_gr_on"] == 0.0)
    return out


# ====================================================================== source patching (exact, counted string replacements)
def read_source(path, rel_key=None):
    """the text of an unchanged flip50 tool after checking its sha256_16 against dg1_frozen.json untouched.module_sha256_16."""
    raw = open(path, "rb").read()
    if rel_key:
        want = frozen()["untouched"]["module_sha256_16"][rel_key]
        got = hashlib.sha256(raw).hexdigest()[:16]
        if got != want:
            raise SystemExit("%s sha256_16 %s differs from the frozen %s (dg1_frozen.json untouched): not patched" % (path, got, want))
    return raw.decode("utf8").replace("\r\n", "\n")


def apply_replacements(src, repl):
    """repl: list of (old, new, count). Each old string must occur exactly count times. Returns (text, info)."""
    info = []
    for old, new, cnt in repl:
        n = src.count(old)
        if n != cnt:
            raise SystemExit("source patch: %r found %d times, expected %d (the source changed?)" % (old[:80], n, cnt))
        src = src.replace(old, new)
        info.append(dict(old=old[:100], n=n))
    return src, info


# ====================================================================== the frame-1 seeding check of the groove (smoke gate b; numpy part)
CORE_BOX = dict(x=(270.0, 310.0), y=(9.0, 16.0))      # dz 1.89-2.13 m (dg1_frozen.json smoke.gates_added_for_DG1)


def lattice_low(bed, dp, zb=GC50.ZB, bed_gap=0.5):
    """the lowest seeding lattice height zb + (k + 1/2) dp >= bed + bed_gap dp (the init_particles rule; count_particles' k_lo)."""
    k = np.ceil((bed + bed_gap * dp - zb) / dp - 0.5 - 1e-9)
    return zb + (np.maximum(k, 0) + 0.5) * dp


def seed_core_stats(Pp, dp, spec_g, zb=GC50.ZB, bed_gap=0.5):
    """Pp: particles (plan x, up, lateral). Per seeding column of the core box: the lowest particle against the groove bed, the D19B bed and
    the seeding lattice of each bed (Houdini adds a jitter of +-0.1 dp). Returns dict (gate b numbers; both readings)."""
    x, z, y = Pp[:, 0], Pp[:, 1], Pp[:, 2]
    ix = np.floor(x / dp).astype(np.int64); iy = np.floor(y / dp).astype(np.int64)
    xc = (ix + 0.5) * dp; yc = (iy + 0.5) * dp
    m = (xc >= CORE_BOX["x"][0]) & (xc <= CORE_BOX["x"][1]) & (np.abs(yc) >= CORE_BOX["y"][0]) & (np.abs(yc) <= CORE_BOX["y"][1])
    if not m.any():
        return dict(n_columns=0, ok=False, why="no particle in the core box")
    key = ix[m] * 100000 + iy[m]
    o = np.lexsort((z[m], key))
    ks = key[o]; zs = z[m][o]
    first = np.r_[True, ks[1:] != ks[:-1]]
    kk = ks[first]; zlow = zs[first]
    cx = (kk // 100000 + 0.5) * dp; cy = (kk % 100000 + 0.5) * dp
    D19 = {k: v for k, v in spec_g.items() if not k.startswith("gr_")}
    bg = GC50.bed_z(cx, cy, **spec_g); b0 = GC50.bed_z(cx, cy, **D19)
    lg = lattice_low(bg, dp, zb, bed_gap); l0 = lattice_low(b0, dp, zb, bed_gap)
    gap = zlow - bg; below = b0 - zlow
    tol = 0.1 * dp + 1e-3
    out = dict(n_columns=int(len(kk)), dp=dp, box=CORE_BOX,
               gap_over_dp=dict(min=float((gap / dp).min()), median=float(np.median(gap / dp)), max=float((gap / dp).max()),
                                frac_gt_1p5=float(np.mean(gap > 1.5 * dp))),
               below_D19B_m=dict(min=float(below.min()), median=float(np.median(below)), max=float(below.max()), frac_ge_1p0=float(np.mean(below >= 1.0))),
               match_groove_lattice_frac=float(np.mean(np.abs(zlow - lg) <= tol)),
               match_D19B_lattice_frac=float(np.mean(np.abs(zlow - l0) <= tol)),
               dz_m=dict(min=float((b0 - bg).min()), max=float((b0 - bg).max())))
    # the readings (default literal per column; a dated amendment may name another, readings())
    out["literal_per_column_pass"] = bool(out["gap_over_dp"]["max"] <= 1.5 and out["below_D19B_m"]["min"] >= 1.0)
    out["medians_pass"] = bool(0.0 <= out["gap_over_dp"]["median"] <= 1.5 and out["below_D19B_m"]["median"] >= 1.0)
    out["model_pass"] = bool(out["match_groove_lattice_frac"] == 1.0 and out["gap_over_dp"]["min"] >= 0.4 - 1e-3 / dp)
    rd, src = readings()
    sel = rd["smoke_b"]
    out["reading"] = sel; out["reading_source"] = src or "default (literal frozen text)"
    out["ok"] = bool(dict(literal_per_column=out["literal_per_column_pass"], medians=out["medians_pass"], model=out["model_pass"],
                          **{"medians+model": out["medians_pass"] and out["model_pass"]})[sel])
    out["note"] = ("literal_per_column = every core-box column's lowest particle within 1.5 dp of bed_g and >= 1.0 m below D19B; medians = the "
                   "same two numbers as box medians; model = every column's lowest particle on the seeding lattice of the GROOVE bed (first "
                   "zb + (k + 1/2) dp >= bed_g + 0.5 dp, +-0.1 dp jitter + 1 mm), i.e. Houdini seeded against the numpy groove bed. The seeding lattice "
                   "puts the lowest particle 0.5-1.5 dp above the bed (+-0.1 dp jitter), not 0.5 +- 0.2 dp as the frozen text assumed, so at dp 1.0 "
                   "and dz 1.96-2.13 m about 41 % of the numpy model's columns lie less than 1.0 m below D19B (model median 1.025 m) whatever "
                   "Houdini does [computed]")
    return out
