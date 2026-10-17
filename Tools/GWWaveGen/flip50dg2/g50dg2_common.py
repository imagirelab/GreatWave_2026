# -*- coding: utf-8 -*-
"""FLIP50 after DG1 (AM-D22): what the DG2 tools share (numpy only; read by hython and by py -3.10). 2026-10-17 written new (Claude).

DG2 exists only as an OPT-IN round after a DG1 Q80 failure (AM-D22, Unity/Build/FLIP50/plan/dg2_frozen.json): the user must say yes in
words (optin.json), the model-validity gate (g50dg2_gate.py) must hold, and it is the last shape round (no DG3). Its bed is the DG1 groove
formula with other CTRL values on the SAME groove hip Houdini/FLIP50/g50_tank_g.hiplc (the VEX reads all eight CTRL gr_* through chf; no
rebuild, the hip is never saved):
    dz = D (1 - exp(-(y/b)^2)) exp(-(y/Y)^2) S((x-x1)/(x2-x1)) (1 - S((x-x3)/(x4-x3)))        [chosen bed, not a measured site]
    L12   : D 3.0, b 8, Y 25, x1 250, x2 274, x3 320, x4 350   (DG1 with the ramp 12 m shoreward: ONE change from DG1)
    H     : D 2.5, b 6, Y 25, x1 250, x2 274, x3 320, x4 350   (shallower groove, inner wall in, ramp 12 m shoreward: three changes)
    L12D4 : D 4.0, b 8, Y 25, x1 250, x2 274, x3 320, x4 350   (deeper + later: the 'deeper groove' dg1_frozen 'never' names)
No file of flip46-flip50, flip50g, flip50g2, the hips, build_check*.json, dg1_frozen.json, plan_D_frozen.json, the tables or any ready
cfg is edited. The DG1 tools are reused in memory (the flip50g / flip50g2 precedent):
  install(GG)  g50g_common.cfg_groove_ok also accepts the DG2 ids of dg2_frozen.json (their own gr_* values, bed.groove, case.dg2_frozen sha)
               and DG2 re-record ids; g50g_common.chain_gate_extra adds the DG2 gate items (dg2_frozen + AM-D22, DG1 finished with Q80 not
               met, the user's opt-in, the hython bed check at the DG2 values, the DG2 smoke gates for the main run); module_shas add the
               flip50dg2 files; g50g_common.CORE_BOX = the variant's groove core box (smoke gate b).
Tags: 【測定】 measured, 【計算】 computed, 【推測】 guess, 【選び】 chosen.
"""
import os, sys, json, math, time, hashlib, copy

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
T50G = REPO + "/Tools/GWWaveGen/flip50g"
T50G2 = REPO + "/Tools/GWWaveGen/flip50g2"
for _p in (HERE, T50G):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import numpy as np                 # noqa: E402
import g50g_common as GG           # noqa: E402  read only (attributes re-bound in memory by install, never the file)

GC = GG.patch_modules()
B50 = GG.B50
LOGS = GG.LOGS
POST = B50 + "/_scratch/post_dg1"
PENDING = POST + "/ready_pending"        # cfgs generated before / while DG1 runs (never launched from here)
READY_POST = POST + "/ready"             # DD3 / re-record cfgs copied here after DG1 (never runs/ready: DD3 keeps the run's own id)
DG2_SCR = POST + "/dg2"                  # gate, opt-in, bed check, self-checks
DG2_FROZEN = GC.PLAN_DIR + "/dg2_frozen.json"
DG2_FROZEN_REL = "Unity/Build/FLIP50/plan/dg2_frozen.json"
AMENDMENT = "AM-D22"
AMENDMENTS = GC.PLAN_DIR + "/amendments.jsonl"
DM1A_ID = "DM1A_D19B_T12_th80_dp0p5"
DG1_ID = GG.RUN_MAIN
DG1_RUN = B50 + "/runs/" + DG1_ID
DM1A_RUN = B50 + "/runs/" + DM1A_ID
DG1_READY = B50 + "/runs/ready/" + DG1_ID + ".json"
DG1_READY_SHA16 = "9adfebecb9b509df"            # 【測定】 2026-10-17 09:57 (the cfg DG1 was launched with)
SMOKE_DG1_READY = B50 + "/smoke/ready/" + GG.RUN_SMOKE + ".json"
SMOKE_DG1_READY_SHA16 = "95b4a694879e0deb"
AUTO_DG1_STATUS = LOGS + "/auto_DG1_status.txt"
OPTIN = DG2_SCR + "/optin.json"
GATE_OUT = DG2_SCR + "/gate_dg2.json"

GR_KEYS = GG.GR_KEYS
CTRL_KEYS = GG.CTRL_KEYS
VARIANTS = {                                    # 【選び】 (post_dg1 row-model / U3 screens; dg2_frozen.json variants)
    "L12": dict(D=3.0, b=8.0, Y=25.0, x1=250.0, x2=274.0, x3=320.0, x4=350.0),
    "H": dict(D=2.5, b=6.0, Y=25.0, x1=250.0, x2=274.0, x3=320.0, x4=350.0),
    "L12D4": dict(D=4.0, b=8.0, Y=25.0, x1=250.0, x2=274.0, x3=320.0, x4=350.0),
}
CORE_BOXES = {                                  # smoke gate b core box: full depth x 274-320 m, the deep lateral band 【選び】
    "L12": dict(x=(280.0, 310.0), y=(9.0, 16.0)),
    "H": dict(x=(280.0, 310.0), y=(7.0, 14.0)),
    "L12D4": dict(x=(280.0, 310.0), y=(9.0, 16.0)),
}
FAR_Y95_MAX_M = 1e-5        # 【選び】 side band y >= 95 m untouched (DG1 used < 2e-6 at D 3; D 4 gives 2.2e-6, still 0.002 mm)
FAR_Y70_MAX_M = 2e-3        # as DG1 (P4a band y >= 70 m)
EXPECT_D19B = {0.5: 5383840, 1.0: 665000}


def main_id(v):
    return "DG2%s_D19Bgr_T12_th80_dp0p5" % v


def smoke_id(v):
    return "SMOKE50DG2%s_D19Bgr_T12_dp1p0" % v


def variant_of(run_id):
    """(variant, kind) for a DG2 id: kind 'main' / 'smoke' / 'rr' (re-record 'DG2<v>r_...'), else (None, None)."""
    rid = run_id or ""
    for v in sorted(VARIANTS, key=len, reverse=True):
        if rid == main_id(v):
            return v, "main"
        if rid == smoke_id(v):
            return v, "smoke"
        if rid.startswith("DG2%sr_" % v):
            return v, "rr"
    return None, None


def params(v):
    return dict(VARIANTS[v])


def ctrl(v):
    g = VARIANTS[v]
    return dict([("gr_on", 1.0)] + [("gr_" + k, float(g[k])) for k in GR_KEYS])


def sha256_file(p):
    return GC.sha256_file(p)


def sha16(p):
    return sha256_file(p)[:16] if os.path.exists(p) else None


# ====================================================================== closed forms (independent of the code under test) 【計算】
def closed_form(g):
    """max of D L(y) and where (L = (1 - e^{-y^2/b^2}) e^{-y^2/Y^2}: dL/du = 0 at e^{-u/b^2} = b^2/(b^2+Y^2), u = y^2), and the added water
    of the half tank: int r dx = (x2 - x1)/2 + (x3 - x2) + (x4 - x3)/2 (smoothstep ramps), int_0^inf L dy = sqrt(pi)/2 (Y - bY/sqrt(b^2+Y^2))."""
    b, Y, D = g["b"], g["Y"], g["D"]
    q = b * b / (b * b + Y * Y)
    y_star = b * math.sqrt(math.log(1.0 / q))
    L_star = q ** (b * b / (Y * Y)) * (1.0 - q)
    ir = (g["x2"] - g["x1"]) / 2.0 + (g["x3"] - g["x2"]) + (g["x4"] - g["x3"]) / 2.0
    iL = math.sqrt(math.pi) / 2.0 * (Y - b * Y / math.sqrt(b * b + Y * Y))
    return dict(dz_max_m=D * L_star, y_dz_max_m=y_star, int_r_dx_m=ir, int_L_dy_m=iL, added_water_half_m3=D * ir * iL)


# ====================================================================== numpy self-checks of a DG2 variant (DG1's T0G list, generic)
def self_checks(v, light=False):
    """the DG1 T0G numpy self-checks (g50g_common.self_checks) for the variant's gr_* values, with closed-form targets instead of DG1's
    tabulated numbers. light=True skips the dp 0.5 particle model count."""
    t0 = time.time()
    g = params(v)
    D19 = dict(GC.SPEC_D19B)
    SG = dict(D19, **ctrl(v))
    oz = GG.orig_fn("g49_common", "bed_z"); og = GG.orig_fn("g49_common", "bed_grad")
    cf = closed_form(g)
    out = dict(variant=v, params=g, closed_form=cf)
    xs = np.arange(0.0, 412.0001, 0.5)
    out["dz_y0_exact_zero"] = bool(np.all(GG.gr_dz(xs, 0.0, g) == 0.0))
    yf = np.arange(0.0, 60.0001, 0.0005)
    xm = np.arange(g["x2"], g["x3"] + 1e-9, 0.5)
    dzf = GG.gr_dz(xm[None, :], yf[:, None], g)
    i = np.unravel_index(int(np.argmax(dzf)), dzf.shape)
    out["dz_max_m"] = float(dzf.max()); out["dz_max_at_y_m"] = float(yf[i[0]])
    ys2 = np.arange(0.0, 140.0001, 0.05)
    dz2 = GG.gr_dz(xs[None, :], ys2[:, None], g)
    out["dz_max_ok"] = bool(abs(out["dz_max_m"] - cf["dz_max_m"]) <= 1e-6 and abs(out["dz_max_at_y_m"] - cf["y_dz_max_m"]) <= 0.002
                            and dz2.max() <= dzf.max() + 1e-12)
    ya = np.arange(-6.0, 146.0001, 0.25)
    xo = np.concatenate([np.arange(0.0, g["x1"] + 1e-9, 0.25), np.arange(g["x4"], 412.0001, 0.25)])
    out["dz_zero_outside_x1_x4"] = bool(np.all(GG.gr_dz(xo[None, :], ya[:, None], g) == 0.0))
    out["bed_equals_D19B_bit_outside"] = bool(np.array_equal(GC.bed_z(xo[None, :], ya[:, None], **SG), oz(xo[None, :], ya[:, None], **D19)))
    out["bed_equals_D19B_bit_on_axis"] = bool(np.array_equal(GC.bed_z(xs, 0.0 * xs, **SG), oz(xs, 0.0 * xs, **D19)))
    out["dz_max_y_ge_70_m"] = float(GG.gr_dz(xs[None, :], np.arange(70.0, 140.0001, 0.05)[:, None], g).max())
    out["dz_max_y_ge_95_m"] = float(GG.gr_dz(xs[None, :], np.arange(95.0, 140.0001, 0.05)[:, None], g).max())
    out["far_field_ok"] = bool(out["dz_max_y_ge_70_m"] < FAR_Y70_MAX_M and out["dz_max_y_ge_95_m"] < FAR_Y95_MAX_M)
    rng = np.random.default_rng(20261017)
    xp = rng.uniform(225.0, 365.0, 4000); yp = rng.uniform(-70.0, 70.0, 4000)
    h = 1e-5
    gx, gy = GC.bed_grad(xp, yp, **SG)
    fx = (GC.bed_z(xp + h, yp, **SG) - GC.bed_z(xp - h, yp, **SG)) / (2 * h)
    fy = (GC.bed_z(xp, yp + h, **SG) - GC.bed_z(xp, yp - h, **SG)) / (2 * h)
    kink = np.abs(xp - GC.X_TOE) < 2 * h
    out["grad_fd_max_abs"] = float(max(np.abs(gx - fx)[~kink].max(), np.abs(gy - fy)[~kink].max()))
    out["grad_ok"] = bool(out["grad_fd_max_abs"] < 1e-6)
    zp = rng.uniform(-20.0, 3.0, 4000)
    sd = GC.bed_sdf(xp, zp, yp, **SG)
    bz = GC.bed_z(xp, yp, **SG)
    ref = (zp - bz) / np.sqrt(1.0 + gx * gx + gy * gy)
    out["sdf_max_abs_dev"] = float(np.abs(sd - ref).max())
    out["sdf_ok"] = bool(np.all(np.sign(sd) == np.sign(zp - bz)) and out["sdf_max_abs_dev"] < 1e-12)
    # the hip default (gr_on 0) and D = 0 stay D19B bit for bit: the same switch as DG1 (bed, grad)
    xg = np.arange(150.0, 412.0001, 0.37); yg = np.arange(-6.0, 146.0001, 0.41)
    X, Y = np.meshgrid(xg, yg)
    sw = {}
    for nm, sp in (("gr_on_0", dict(D19, **dict(ctrl(v), gr_on=0.0))), ("gr_D_0", dict(D19, **dict(ctrl(v), gr_D=0.0)))):
        g1, g2 = GC.bed_grad(X, Y, **sp); h1, h2 = og(X, Y, **D19)
        sw[nm] = dict(bed=bool(np.array_equal(GC.bed_z(X, Y, **sp), oz(X, Y, **D19))), grad=bool(np.array_equal(g1, h1) and np.array_equal(g2, h2)))
    out["switch_off"] = sw
    out["switch_off_ok"] = bool(all(all(d.values()) for d in sw.values()))
    # added water: trapezoid against the closed form; particle model (quadrature as AM-D21 'quadrature' reading) and lattice counts
    xx = np.arange(200.0, 360.0001, 0.01); yv = np.arange(0.0, 140.0001, 0.01)
    trap = getattr(np, "trapezoid", None) or np.trapz
    v2 = float(trap(GG.gr_r(xx, g), xx) * trap(g["D"] * GG.gr_L(yv, g), yv))
    out["added_water_m3"] = v2
    out["added_water_ok"] = bool(abs(v2 - cf["added_water_half_m3"]) <= 0.05)
    pc = {}
    for dp in ((1.0,) if light else (1.0, 0.5)):
        xs_ = (np.arange(int(round(GC.LX / dp))) + 0.5) * dp
        ys_ = (np.arange(int(round(GC.W_MAIN / dp))) + 0.5) * dp
        quad = float(GG.gr_dz(xs_[None, :], ys_[:, None], g).sum() * dp * dp / dp ** 3)
        n_g = GC.count_particles(SG, GC.LX, GC.W_MAIN, dp, zb=GC.ZB)[0]
        n_0 = GC.count_particles(D19, GC.LX, GC.W_MAIN, dp, zb=GC.ZB)[0]
        exp_n = cf["added_water_half_m3"] / dp ** 3
        key = "dp%s" % ("1p0" if dp == 1.0 else "0p5")
        pc[key] = dict(model_groove=int(n_g), model_D19B=int(n_0), added_lattice=int(n_g - n_0), quadrature=quad, expected_closed_form=exp_n,
                       quadrature_rel_err=quad / exp_n - 1.0, lattice_rel_err=(n_g - n_0) / exp_n - 1.0,
                       quadrature_ok=bool(abs(quad / exp_n - 1.0) <= 0.005 and n_0 == EXPECT_D19B[dp]))
    out["particles"] = pc
    out["particles_ok"] = bool(all(p["quadrature_ok"] for p in pc.values()))
    keys = ["dz_y0_exact_zero", "dz_max_ok", "dz_zero_outside_x1_x4", "bed_equals_D19B_bit_outside", "bed_equals_D19B_bit_on_axis",
            "far_field_ok", "grad_ok", "sdf_ok", "switch_off_ok", "added_water_ok", "particles_ok"]
    out["ok"] = bool(all(out[k] for k in keys))
    out["failed"] = [k for k in keys if not out[k]]
    cb = CORE_BOXES[v]
    xb = np.arange(cb["x"][0], cb["x"][1] + 1e-9, 0.5); yb = np.arange(cb["y"][0], cb["y"][1] + 1e-9, 0.25)
    dzb = GG.gr_dz(xb[None, :], yb[:, None], g)
    out["core_box"] = dict(box=cb, dz_min_m=float(dzb.min()), dz_max_m=float(dzb.max()),
                           note="smoke gate b reads the lowest particle per seeding column in this box (the 'model' reading of AM-D21)")
    out["cpu_s"] = round(time.time() - t0, 2)
    out["tags"] = "【計算】 numpy; closed-form targets; thresholds as dg1_frozen pre_run_gates_T0G except the y >= 95 m far field (1e-5 m) 【選び】"
    return out


# ====================================================================== the frozen DG2 file and AM-D22
def frozen_dg2():
    """dg2_frozen.json after checking its sha256 against the .sha256 side file; None if absent."""
    if not os.path.exists(DG2_FROZEN):
        return None
    sh = sha256_file(DG2_FROZEN)
    side = open(DG2_FROZEN + ".sha256", encoding="utf8").read().split()[0] if os.path.exists(DG2_FROZEN + ".sha256") else None
    if side != sh:
        raise SystemExit("dg2_frozen.json sha256 %s differs from its .sha256 file %s: the frozen DG2 rules changed" % (sh[:16], str(side)[:16]))
    return json.load(open(DG2_FROZEN, encoding="utf8"))


def amendment():
    """the AM-D22 line of amendments.jsonl, or None."""
    for e in GG.amendments():
        if e.get("id") == AMENDMENT and e.get("plan") == GC.PLAN_D_REL:
            return e
    return None


def expect_particles(v, dp):
    fz = frozen_dg2()
    if fz is None:
        return None
    return int(fz["variants"][v]["particles_model"]["dp%s" % ("1p0" if float(dp) == 1.0 else "0p5")])


# ====================================================================== status of DG1 (read only)
def status_lines(p=AUTO_DG1_STATUS):
    if not os.path.exists(p):
        return []
    return open(p, encoding="utf8", errors="replace").read().splitlines()


def dg1_q80(rd=DG1_RUN):
    p = os.path.join(rd, "pana", "q80_DG1.json")
    return json.load(open(p, encoding="utf8")) if os.path.exists(p) else None


def dg1_finished_not_met():
    L = status_lines()
    done = any(" DG1 ANA_DONE" in l or " DG1 FINISHED" in l for l in L)
    q = dg1_q80()
    return dict(ok=bool(done and q is not None and q.get("Q80_met") is False), dg1_done=done,
                q80_met=None if q is None else q.get("Q80_met"))


# ====================================================================== the in-memory DG2 acceptance (cfg_groove_ok / chain_gate_extra)
def dg2_cfg_bad(cfg, v, kind):
    """the DG2 analogue of g50g_common.cfg_groove_ok."""
    bad = []
    P = cfg.get("parms") or {}
    want = ctrl(v)
    if any(P.get(k) != want[k] for k in CTRL_KEYS):
        bad.append("cfg parms gr_* %s differ from DG2-%s %s" % ({k: P.get(k) for k in CTRL_KEYS}, v, want))
    gd = (cfg.get("bed") or {}).get("groove") or {}
    if any(gd.get(k) != VARIANTS[v][k] for k in GR_KEYS):
        bad.append("cfg bed.groove %s differs from DG2-%s %s" % (gd, v, VARIANTS[v]))
    cs = cfg.get("case") or {}
    if cs.get("dg1_frozen_sha256") != GG.DG1_SHA256 or cs.get("dg1_frozen") != GG.DG1_FROZEN_REL:
        bad.append("cfg case.dg1_frozen / dg1_frozen_sha256 differ from AM-D20 (the S0-S4 criteria are dg1_frozen's)")
    cur = sha256_file(DG2_FROZEN) if os.path.exists(DG2_FROZEN) else None
    if cs.get("dg2_frozen") != DG2_FROZEN_REL or cs.get("dg2_frozen_sha256") != cur or cur is None:
        bad.append("cfg case.dg2_frozen / dg2_frozen_sha256 differ from the current %s (%s)" % (DG2_FROZEN_REL, str(cur)[:16]))
    if cs.get("dg2_variant") != v or cs.get("am") != AMENDMENT:
        bad.append("cfg case.dg2_variant / am differ (%s / %s)" % (cs.get("dg2_variant"), cs.get("am")))
    if cfg.get("hip") != GG.HIP_G_REL or cfg.get("build_check") != GG.BUILD_CHECK_G_REL:
        bad.append("cfg hip / build_check keys are not the groove hip %s / %s" % (GG.HIP_G_REL, GG.BUILD_CHECK_G_REL))
    rid = cfg.get("run_id") or ""
    if kind == "rr":
        if (cfg.get("restart") or {}).get("src_run") != main_id(v):
            bad.append("re-record %s: restart.src_run %s is not %s" % (rid, (cfg.get("restart") or {}).get("src_run"), main_id(v)))
    elif rid not in (main_id(v), smoke_id(v)):
        bad.append("run_id %s is neither %s nor %s" % (rid, main_id(v), smoke_id(v)))
    return bad


def optin_for(v):
    """the user's opt-in record (written by auto_post_dg1 or the main session from the user's own words)."""
    if not os.path.exists(OPTIN):
        return dict(ok=False, why="no %s (DG2 runs only after the user says yes in words)" % OPTIN)
    d = json.load(open(OPTIN, encoding="utf8"))
    ok = bool(d.get("variant") == v and str(d.get("user_words") or "").strip())
    return dict(ok=ok, record=d, why=None if ok else "opt-in record names %s / user_words %r" % (d.get("variant"), d.get("user_words")))


def bedcheck_ok(v):
    p = DG2_SCR + "/bedcheck_%s.json" % v
    if not os.path.exists(p):
        return False, "hython bed check at the DG2-%s values missing (%s; py -3.10 -B g50dg2_pcfg.py bedcheck %s)" % (v, p, v)
    d = json.load(open(p, encoding="utf8"))
    cur = sha256_file(GG.HIP_G) if os.path.exists(GG.HIP_G) else None
    if d.get("ok") is not True:
        return False, "the DG2-%s hython bed check failed: %s" % (v, d.get("failed"))
    if d.get("hip_sha256") != cur:
        return False, "the DG2-%s bed check ran on hip %s, the current hip is %s" % (v, str(d.get("hip_sha256"))[:16], str(cur)[:16])
    return True, None


def smoke_dg2_ok(v):
    p = os.path.join(B50, "smoke", smoke_id(v), "pana", "smoke_DG2.json")
    if not os.path.exists(p):
        return False, "DG2 smoke gates not read yet (%s missing; py -3.10 -B g50dg2_ana.py smoke ...)" % p
    d = json.load(open(p, encoding="utf8"))
    if d.get("ok") is not True:
        return False, "the DG2-%s smoke gates failed: %s" % (v, [k for k, x in (d.get("gates") or {}).items() if x is not True])
    sm = (d.get("validity") or {}).get("hip_sha256") or []
    cur = sha256_file(GG.HIP_G) if os.path.exists(GG.HIP_G) else None
    if not (len(sm) == 1 and sm[0] == cur):
        return False, "the DG2-%s smoke ran on another hip sha %s (current %s)" % (v, [str(s)[:16] for s in sm], str(cur)[:16])
    return True, None


def dg2_gate_extra(cfg, v, kind):
    """DG2 launch-gate items added to g50g_common.chain_gate_extra (dg2_frozen.json run.launch_gate)."""
    bad = []
    try:
        fz = frozen_dg2()
    except SystemExit as e:
        return [str(e)]
    if fz is None:
        return ["%s missing" % DG2_FROZEN]
    am = amendment()
    if am is None or am.get("dg2_frozen_sha256") != sha256_file(DG2_FROZEN):
        bad.append("AM-D22 missing in amendments.jsonl or its dg2_frozen_sha256 differs from the file")
    if kind in ("main", "smoke"):
        st = dg1_finished_not_met()
        if not st["ok"]:
            bad.append("DG2 runs only after DG1 finished with Q80 not met (DG1 done %s, Q80_met %s)" % (st["dg1_done"], st["q80_met"]))
        oi = optin_for(v)
        if not oi["ok"]:
            bad.append("no opt-in for DG2-%s: %s" % (v, oi["why"]))
        ok, why = bedcheck_ok(v)
        if not ok:
            bad.append(why)
        sc = self_checks(v, light=True)
        if not sc["ok"]:
            bad.append("DG2-%s numpy self-checks failed: %s" % (v, sc["failed"]))
    if kind == "main":
        ok, why = smoke_dg2_ok(v)
        if not ok:
            bad.append(why)
    if kind == "rr":
        q = os.path.join(B50, "runs", main_id(v), "pana", "q80_DG2.json")
        if not os.path.exists(q):
            bad.append("re-record of DG2-%s before its q80_DG2.json exists" % v)
    return bad


def install(gg=None):
    """in memory only (idempotent): DG2 ids accepted by g50g_common.cfg_groove_ok; DG2 gate items added to chain_gate_extra; module_shas
    add the flip50dg2 files. Every DG1 / DG1r item stays the unchanged original."""
    gg = gg or GG
    if getattr(gg, "_dg2_installed", False):
        return gg
    orig_ok = gg.cfg_groove_ok
    orig_extra = gg.chain_gate_extra

    def cfg_groove_ok(cfg):
        v, kind = variant_of(cfg.get("run_id"))
        if v is None:
            return orig_ok(cfg)
        return dg2_cfg_bad(cfg, v, kind)

    def chain_gate_extra(cfg, order_ok=None):
        bad = orig_extra(cfg, order_ok)
        v, kind = variant_of(cfg.get("run_id"))
        if v is not None:
            bad = bad + dg2_gate_extra(cfg, v, kind)
        return bad
    cfg_groove_ok.__doc__ = "flip50dg2 in-memory wrapper of g50g_common.cfg_groove_ok (+ DG2 ids of dg2_frozen.json)"
    chain_gate_extra.__doc__ = "flip50dg2 in-memory wrapper of g50g_common.chain_gate_extra (+ DG2 gate items)"
    gg.cfg_groove_ok = cfg_groove_ok
    gg.chain_gate_extra = chain_gate_extra
    orig_ms = gg.module_shas_g

    def module_shas_dg2():
        out = orig_ms()
        for nm in sorted(os.listdir(HERE)):
            if nm.endswith(".py"):
                out["flip50dg2/" + nm] = sha256_file(os.path.join(HERE, nm))[:16]
        return out
    gg.module_shas_g = module_shas_dg2
    if getattr(gg.GC50, "module_shas", None) is orig_ms:
        gg.GC50.module_shas = module_shas_dg2
    gg._dg2_installed = True
    return gg


def set_core_box(v):
    """smoke gate b reads g50g_common.CORE_BOX (module global, read at call time): the variant's box."""
    GG.CORE_BOX = dict(CORE_BOXES[v])
    return GG.CORE_BOX
