# -*- coding: utf-8 -*-
"""FLIP50 after DG1 (AM-D22): the next-run cfgs of every post-DG1 branch, their prechecks and the DG2 checks (py -3.10 -B; numpy, no
Houdini except `bedcheck`, which runs a READ-ONLY hython extraction after every other hython has ended). 2026-10-17 written new (Claude).

No file of flip46-flip50, flip50g, flip50g2, the hips, build_check*.json, dg1_frozen.json, plan_D_frozen.json, the tables or any ready cfg is
edited. Cfgs are written to Unity/Build/FLIP50/_scratch/post_dg1/ready_pending/ (before / while DG1 runs) and copied into a ready folder
only after DG1 has finished (`promote`; auto_post_dg1.py does this for the branch it runs):
  DG2 cfgs (new run ids)            -> runs/ready/ and smoke/ready/ (new files; an existing different file is never overwritten)
  DD3 / re-record cfgs (flip50g2)   -> _scratch/post_dg1/ready/ (never runs/ready: a DD3 cfg keeps the run's own id and would replace the
                                       cfg that run was launched with)

  py -3.10 -B g50dg2_pcfg.py freeze [--force=1]        dg2_frozen.json (+ .sha256) from the registry and the numpy self-checks
  py -3.10 -B g50dg2_pcfg.py cfg <L12|H|L12D4|all>     DG2 main + smoke cfgs -> ready_pending/
  py -3.10 -B g50dg2_pcfg.py promote <variant>         ready_pending -> runs/ready + smoke/ready (only after DG1 finished; regenerated and
                                                        compared byte for byte first)
  py -3.10 -B g50dg2_pcfg.py dd3 --run=<run> [--max_hours=2.6] [--to=pending|ready]
                                                        flip50g2/g50g2_cont.py dd3 in memory (DG1 unchanged; DG2 runs with the DG2
                                                        precheck) -> ready_pending/ (default) or _scratch/post_dg1/ready/
  py -3.10 -B g50dg2_pcfg.py rr --run=<run> --tau=<frame> [--to=pending|ready]    flip50g2 re-record cfg, same routing
  py -3.10 -B g50dg2_pcfg.py bedcheck <variant>        hython g50dg2_bedcheck_h.py (read only) + bedcheck-eval -> _scratch/post_dg1/dg2/
  py -3.10 -B g50dg2_pcfg.py bedcheck-eval <variant> <npz>
  py -3.10 -B g50dg2_pcfg.py check                     everything above that needs no Houdini, into ready_pending/ + check_dg2.json
Tags: 【測定】 measured, 【計算】 computed, 【推測】 guess, 【選び】 chosen.
"""
import os, sys, json, copy, time, hashlib, subprocess, shutil

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import numpy as np                 # noqa: E402
import g50dg2_common as D          # noqa: E402

GG = D.GG
GC = D.GC
D.install(GG)
import g50g_pcfg as GGP            # noqa: E402  flip50g (unchanged): g50_pcfg imported on the patched g50_common
PC = GGP.PC
if D.T50G2 not in sys.path:
    sys.path.append(D.T50G2)
import g50g2_cont as G2            # noqa: E402  flip50g2 (unchanged): DD3 and re-record cfgs

ALLOWED_TOP = {"run_id", "case", "parms", "bed", "note", "precheck"}
ALLOWED_CASE = {"name", "queue_id", "d_round", "amendment", "dg2_frozen", "dg2_frozen_sha256", "dg2_variant", "am", "dg2_previous_round",
                "dg2_changes_from_DG1"}
ALLOWED_BED = {"kind", "formula", "max_depth_m", "min_depth_m", "groove"}
CHANGES = dict(L12="the groove ramp moved 12 m shoreward (gr_x1 238 -> 250, gr_x2 262 -> 274): one change from DG1",
               H="shallower groove with the inner wall moved in and the ramp 12 m shoreward (gr_D 3 -> 2.5, gr_b 8 -> 6, gr_x1 238 -> 250, "
                 "gr_x2 262 -> 274): three changes from DG1 (the outcome cannot be attributed to one of them)",
               L12D4="deeper groove and the ramp 12 m shoreward (gr_D 3 -> 4, gr_x1 238 -> 250, gr_x2 262 -> 274): the 'deeper groove' that "
                     "dg1_frozen 'never' names; two changes from DG1")


def dumps_file(c):
    return json.dumps(c, indent=1, ensure_ascii=False, default=float).replace("\n", os.linesep).encode("utf8")


def load_base(p, s16):
    raw = open(p, "rb").read()
    got = hashlib.sha256(raw).hexdigest()[:16]
    if got != s16:
        raise SystemExit("base cfg %s sha256_16 %s differs from %s" % (p, got, s16))
    return json.loads(raw.decode("utf8"))


# ====================================================================== precheck (g50_pcfg.precheck under the groove patch, DG2 items)
def precheck_dg2(c, v):
    o = PC.precheck(c)
    P = c["parms"]
    spec = GC.bed_spec(c)
    dp = float(P["dp"])
    n = o["particles_model"]
    n0 = GC.count_particles({k: x for k, x in spec.items() if not k.startswith("gr_")}, float(P["Lx"]), float(P["W"]), dp,
                            zb=float(P["zb"]), bed_gap=float(P["bed_gap"]))[0]
    new = {}
    for k, x in o["checks"].items():
        if k == "bed_is_D19B":
            new["bed_is_D19B_plus_dg2_groove"] = bool(
                all((spec.get(kk) == vv) if not isinstance(vv, float) else abs(float(spec.get(kk)) - vv) < 1e-12 for kk, vv in GC.SPEC_D19B.items())
                and not GC.is_new(spec) and spec.get("k_end") is None and GG.groove_of(spec) == D.params(v)
                and (c.get("bed") or {}).get("groove") == D.params(v) and GG.cfg_groove_ok(c) == [])
        elif k == "particles_as_designed":
            new[k] = bool(D.expect_particles(v, dp) == n and D.EXPECT_D19B.get(dp) == n0)
        else:
            new[k] = x
    new["dg1_frozen_sha"] = bool(GG.sha256_file(GG.DG1_FROZEN) == GG.DG1_SHA256)
    new["dg2_frozen_sha"] = bool(os.path.exists(D.DG2_FROZEN) and (c.get("case") or {}).get("dg2_frozen_sha256") == D.sha256_file(D.DG2_FROZEN))
    o["checks"] = new
    o["particles_model_D19B"] = int(n0)
    o["particles_added_by_groove"] = int(n - n0)
    o["cfg_groove_bad"] = GG.cfg_groove_ok(c)
    o["tags"] = dict(o.get("tags") or {}, particles="【計算】 numpy, the scene's seeding rule, D19B + the DG2-%s groove (g50g_common patch)" % v)
    o["ok"] = bool(all(new.values()))
    o["reason"] = None if o["ok"] else "failed: " + ", ".join(k for k, x in new.items() if not x)
    return o


# ====================================================================== DG2 cfgs
def amendment_text(v, main):
    return ("AM-D22 (Unity/Build/FLIP50/plan/amendments.jsonl; rules in %s sha256 %s): DG2-%s = an OPT-IN round after a DG1 Q80 failure, "
            "only on the user's explicit yes (dg1_frozen 'never'); %s; the last shape round (no DG3); S0-S4 of dg1_frozen.json against DM1A "
            "unchanged; drift stage A of AM-D18 kept" % (D.DG2_FROZEN_REL, D.sha256_file(D.DG2_FROZEN)[:16], v,
                                                        CHANGES[v] if main else "smoke of the same bed (dp 1.0, never judged)"))


def build_cfg(v, which):
    if not os.path.exists(D.DG2_FROZEN):
        raise SystemExit("%s missing (py -3.10 -B g50dg2_pcfg.py freeze)" % D.DG2_FROZEN)
    D.frozen_dg2()
    main = which == "main"
    b0 = load_base(D.DG1_READY, D.DG1_READY_SHA16) if main else load_base(D.SMOKE_DG1_READY, D.SMOKE_DG1_READY_SHA16)
    c = copy.deepcopy(b0)
    c["run_id"] = D.main_id(v) if main else D.smoke_id(v)
    cs = c["case"]
    cs["name"] = ("FLIP50_3d_D19Bgr_DG2%s" if main else "FLIP50_smoke_D19Bgr_DG2%s") % v
    cs["queue_id"] = ("DG2%s" if main else "SMOKE50DG2%s") % v
    if main:
        cs["d_round"] = 4                      # beyond max_rounds_in_D 3: decide_D treats it exactly as round 3 (partial = stop and show)
        cs["dg2_previous_round"] = D.DG1_ID
    cs["amendment"] = amendment_text(v, main)
    cs["dg2_frozen"] = D.DG2_FROZEN_REL
    cs["dg2_frozen_sha256"] = D.sha256_file(D.DG2_FROZEN)
    cs["dg2_variant"] = v
    cs["am"] = D.AMENDMENT
    cs["dg2_changes_from_DG1"] = CHANGES[v]
    c["parms"].update(D.ctrl(v))
    spec = dict(GC.SPEC_D19B, **D.ctrl(v))
    c["bed"] = GC.bed_record(spec, c["box"])
    g = D.params(v)
    gtxt = ("D19B minus a CHOSEN pair of shallow grooves beside the axis (DG1 formula, DG2-%s values: D %g m, b %g m, Y %g m, smoothstep ramp "
            "x %g-%g m, fade x %g-%g m; max %.2f m at |y| %.1f m, 0 on the axis; a rip-channel / spur-and-groove analogue, not a measured site "
            "[chosen])" % (v, g["D"], g["b"], g["Y"], g["x1"], g["x2"], g["x3"], g["x4"], D.closed_form(g)["dz_max_m"], D.closed_form(g)["y_dz_max_m"]))
    if main:
        c["note"] = ("FLIP50 option D DG2-%s (AM-D22, opt-in after a DG1 Q80 failure; the last shape round): DG1 unchanged (3D dp 0.5, W 140, "
                     "directional sea T 12 s, +-80 deg, a_sum 6.331 m, focus (220.25, 0), stage A, 92 s, heavy records from 44 s every 3 frames) "
                     "except the groove values: %s. %s. Same groove hip %s (no rebuild; CTRL gr_*); S0-S4 of %s vs DM1A; rules %s"
                     % (v, CHANGES[v], gtxt, GG.HIP_G_REL, GG.DG1_FROZEN_REL, D.DG2_FROZEN_REL))
    else:
        c["note"] = ("FLIP50 option D DG2-%s smoke (never judged): SMOKE50DG1 unchanged (3D dp 1.0, W 140, 0-50 s, one launch) except the groove "
                     "values: %s. Gates as the DG1 smoke (dg1_frozen smoke) with the DG2-%s core box %s and the CTRL gr_* of %s"
                     % (v, gtxt, v, D.CORE_BOXES[v], D.DG2_FROZEN_REL))
    c.pop("precheck", None)
    c["precheck"] = precheck_dg2(c, v)
    diff = key_diff(b0, c, v)
    return c, b0, diff


def key_diff(b0, c, v):
    """against the DG1 cfg: only the run id, case labels, the gr_* parms that differ, the bed record, note and precheck may change."""
    top_changed = sorted(k for k in set(b0) | set(c) if b0.get(k, None) != c.get(k, None))
    cs0, cs1 = b0["case"], c["case"]
    case_changed = sorted(k for k in set(cs0) | set(cs1) if cs0.get(k, "\0") != cs1.get(k, "\0"))
    p0, p1 = b0["parms"], c["parms"]
    parms_changed = sorted(k for k in set(p0) | set(p1) if p0.get(k, "\0") != p1.get(k, "\0"))
    bd0, bd1 = b0["bed"], c["bed"]
    bed_changed = sorted(k for k in set(bd0) | set(bd1) if bd0.get(k, "\0") != bd1.get(k, "\0"))
    want_parms = sorted(k for k in D.CTRL_KEYS if b0["parms"].get(k) != D.ctrl(v)[k])
    d = dict(top_changed=top_changed, case_changed=case_changed, parms_changed=parms_changed, parms_expected=want_parms, bed_changed=bed_changed,
             order_kept=bool(list(c) == list(b0) and list(p1) == list(p0)))
    bad = []
    if set(top_changed) - ALLOWED_TOP:
        bad.append("top-level keys changed outside the rule: %s" % sorted(set(top_changed) - ALLOWED_TOP))
    if set(case_changed) - ALLOWED_CASE:
        bad.append("case keys changed outside the rule: %s" % sorted(set(case_changed) - ALLOWED_CASE))
    if parms_changed != want_parms:
        bad.append("parms changed %s, expected exactly %s" % (parms_changed, want_parms))
    if set(bed_changed) - ALLOWED_BED or "groove" not in bed_changed:
        bad.append("bed keys changed outside the rule: %s" % bed_changed)
    if not d["order_kept"]:
        bad.append("key order changed")
    d["ok"] = not bad
    d["bad"] = bad
    if bad:
        raise SystemExit("DG2-%s cfg key diff: %s" % (v, bad))
    return d


def pending_path(c):
    return os.path.join(D.PENDING, c["run_id"] + ".json").replace("\\", "/")


def ready_path(c):
    return os.path.join(GC.B50, c["out_root"], "ready", c["run_id"] + ".json").replace("\\", "/")


def write_pending(c):
    os.makedirs(D.PENDING, exist_ok=True)
    p = pending_path(c)
    b = dumps_file(c)
    how = "written"
    if os.path.exists(p):
        how = "unchanged" if open(p, "rb").read() == b else "replaced (regenerated)"
    if how != "unchanged":
        with open(p, "wb") as fh:
            fh.write(b)
    return p, how


def dg1_finished():
    L = D.status_lines()
    return any(" DG1 FINISHED" in l or " DG1 ANA_DONE" in l for l in L)


def promote(v):
    """ready_pending -> runs/ready + smoke/ready, only after DG1 finished; each cfg is regenerated and must equal the pending bytes."""
    if not dg1_finished():
        raise SystemExit("DG1 has not finished (no 'DG1 ANA_DONE' / 'DG1 FINISHED' in %s): not promoted" % D.AUTO_DG1_STATUS)
    out = {}
    for which in ("smoke", "main"):
        c, b0, diff = build_cfg(v, which)
        if not c["precheck"]["ok"]:
            raise SystemExit("DG2-%s %s precheck failed: %s" % (v, which, c["precheck"]["reason"]))
        b = dumps_file(c)
        pp = pending_path(c)
        if not os.path.exists(pp) or open(pp, "rb").read() != b:
            raise SystemExit("%s differs from the regenerated cfg (frozen file or code changed since it was written?): not promoted" % pp)
        rp = ready_path(c)
        rd = os.path.join(GC.B50, c["out_root"], c["run_id"])
        if os.path.exists(os.path.join(rd, "chain.log")):
            raise SystemExit("%s already has a chain record: not promoted" % rd)
        if os.path.exists(rp):
            if open(rp, "rb").read() != b:
                raise SystemExit("%s exists with other content: not overwritten" % rp)
            out[which] = (rp, "unchanged")
            continue
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "wb") as fh:
            fh.write(b)
        out[which] = (rp, "written")
    return out


# ====================================================================== DD3 / re-record through flip50g2 (in memory)
_ORIG_TF = G2.tools_for


def tools_for_dg2(c):
    v, kind = D.variant_of(c.get("run_id"))
    if v is None:
        return _ORIG_TF(c)
    D.install(GG)
    return PC, (lambda cc: precheck_dg2(cc, v)), GG


G2.tools_for = tools_for_dg2


def g2_call(fn, o, to="pending"):
    """run flip50g2 dd3 / rr with its cfg folder set to ready_pending (default) or _scratch/post_dg1/ready; returns the printed JSON."""
    G2.CFG_DIR = D.PENDING if to == "pending" else D.READY_POST
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fn(o)
    s = buf.getvalue()
    i = s.find("{")
    return json.loads(s[i:]) if i >= 0 else dict(raw=s)


# ====================================================================== the hython bed check at the DG2 values
def bedcheck(v):
    mp = os.path.join(GC.B50, "runs", "ready", D.main_id(v) + ".json")
    sp = os.path.join(GC.B50, "smoke", "ready", D.smoke_id(v) + ".json")
    if not (os.path.exists(mp) and os.path.exists(sp)):
        mp, sp = os.path.join(D.PENDING, D.main_id(v) + ".json"), os.path.join(D.PENDING, D.smoke_id(v) + ".json")
    os.makedirs(D.DG2_SCR, exist_ok=True)
    npz = D.DG2_SCR + "/bedcheck_%s.npz" % v
    logp = D.DG2_SCR + "/bedcheck_%s.log" % v
    with open(logp, "a", encoding="utf8") as fh:
        fh.write("%s waiting for other hython\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
    GC.wait_no_hython(log=lambda *a: None)
    tmp = GC.B50 + "/tmp_houdini"
    os.makedirs(tmp, exist_ok=True)
    env = dict(os.environ, HOUDINI_TEMP_DIR=tmp, PYTHONDONTWRITEBYTECODE="1")
    with open(logp, "a", encoding="utf8", errors="ignore") as fh:
        r = subprocess.run([GC.HY, HERE + "/g50dg2_bedcheck_h.py", mp, sp, npz], stdout=fh, stderr=subprocess.STDOUT, env=env, stdin=subprocess.DEVNULL)
    return bedcheck_eval(v, npz, rc=r.returncode)


def bedcheck_eval(v, npz, rc=None):
    """numpy comparison of the hython extraction (thresholds of dg1_frozen pre_run_gates_T0G: DG1_3d bed < 1 cm and SDF < 2 cm near the bed
    with no sign mismatch; groove box depth Houdini vs numpy < 1 cm; dp 1.0 particles = model within 0.2 %, none below the bed, x_max <=
    shoreline + 0.5 m) -> _scratch/post_dg1/dg2/bedcheck_<v>.json."""
    rec = json.load(open(npz + ".json", encoding="utf8")) if os.path.exists(npz + ".json") else dict(error="no extraction record")
    out = dict(variant=v, date=time.strftime("%Y-%m-%d %H:%M:%S"), hython_rc=rc, extraction=dict((k, rec.get(k)) for k in
               ("date", "hip_sha256_before", "hip_sha256_after", "hip_unchanged", "main_parms", "smoke_parms", "sdf_res", "n", "wall_s", "error")),
               hip_sha256=rec.get("hip_sha256_before"))
    failed = []
    if rec.get("error") or not os.path.exists(npz):
        out.update(ok=False, failed=["extraction: %s" % rec.get("error")])
        json.dump(out, open(D.DG2_SCR + "/bedcheck_%s.json" % v, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
        return out
    A = np.load(npz)
    want = D.ctrl(v)
    mp = rec.get("main_parms") or {}
    sp_ = rec.get("smoke_parms") or {}
    out["ctrl_main_ok"] = bool(all(abs(float(mp.get(k, -1e9)) - want[k]) < 1e-9 for k in D.CTRL_KEYS))
    out["ctrl_smoke_ok"] = bool(all(abs(float(sp_.get(k, -1e9)) - want[k]) < 1e-9 for k in D.CTRL_KEYS))
    spec = dict(GC.SPEC_D19B, **want)
    D19 = dict(GC.SPEC_D19B)
    P = A["bedP"]
    zb = GC.bed_z(P[:, 0], P[:, 2], **spec)
    d = P[:, 1] - zb
    out["bed"] = dict(points=int(len(P)), max_abs_dz_m=float(np.abs(d).max()), lt_1cm=bool(np.abs(d).max() < 0.01), lt_1mm=bool(np.abs(d).max() < 1e-3))
    m = (P[:, 0] >= 230.0) & (P[:, 0] <= 360.0) & (np.abs(P[:, 2]) <= 60.0)
    dzh = GC.bed_z(P[m, 0], P[m, 2], **D19) - P[m, 1]
    dzn = GG.gr_dz(P[m, 0], P[m, 2], D.params(v))
    cf = D.closed_form(D.params(v))
    out["groove_depth"] = dict(houdini_max_m=float(dzh.max()), numpy_max_m=float(dzn.max()), closed_form_max_m=cf["dz_max_m"],
                               ok=bool(abs(float(dzh.max()) - float(dzn.max())) < 0.01 and float(dzn.max()) > 0.9 * cf["dz_max_m"]))
    a = A["sdf"].astype(np.float64)
    xs, ys, zs = A["sdf_xs"], A["sdf_ys"], A["sdf_zs"]
    Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
    ref = GC.bed_sdf(X, Y, Z, **spec)
    near = np.abs(ref) < 3.0
    far = np.abs(ref) > 0.05
    out["sdf"] = dict(voxels=int(a.size), max_abs_diff_near_m=float(np.abs(a - ref)[near].max()) if near.any() else None,
                      sign_mismatch_frac=float(np.mean(np.sign(a[far]) != np.sign(ref[far]))) if far.any() else None)
    out["sdf"]["ok"] = bool(out["sdf"]["max_abs_diff_near_m"] is not None and out["sdf"]["max_abs_diff_near_m"] < 0.02 and out["sdf"]["sign_mismatch_frac"] == 0.0)
    Pp = A["parts"]
    sps = dict(GC.SPEC_D19B, **want)
    gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **sps)
    n_model = GC.count_particles(sps, float(sp_.get("Lx", GC.LX)), float(sp_.get("W", GC.W_MAIN)), float(sp_.get("dp", 1.0)),
                                 zb=float(sp_.get("zb", GC.ZB)), bed_gap=float(sp_.get("bed_gap", 0.5)))[0]
    out["particles"] = dict(n=int(len(Pp)), model=int(n_model), ratio=float(len(Pp)) / max(n_model, 1), n_below_bed=int((gap < 0).sum()),
                            x_max_m=float(Pp[:, 0].max()), expect_frozen=D.expect_particles(v, 1.0))
    out["particles"]["ok"] = bool(out["particles"]["n_below_bed"] == 0 and abs(out["particles"]["ratio"] - 1.0) < 0.002
                                  and out["particles"]["x_max_m"] <= GC.X_SHORE + 0.5)
    bc = json.load(open(GG.BUILD_CHECK_G, encoding="utf8")) if os.path.exists(GG.BUILD_CHECK_G) else {}
    out["hip_unchanged_and_built"] = bool(rec.get("hip_unchanged") and rec.get("hip_sha256_before") == bc.get("hip_sha256"))
    items = dict(ctrl_main=out["ctrl_main_ok"], ctrl_smoke=out["ctrl_smoke_ok"], bed=out["bed"]["lt_1cm"], groove_depth=out["groove_depth"]["ok"],
                 sdf=out["sdf"]["ok"], particles=out["particles"]["ok"], hip=out["hip_unchanged_and_built"])
    out["items"] = items
    out["failed"] = [k for k, x in items.items() if not x]
    out["ok"] = bool(not out["failed"])
    json.dump(out, open(D.DG2_SCR + "/bedcheck_%s.json" % v, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=float)
    return out


# ====================================================================== freeze dg2_frozen.json
def freeze(force=False):
    if os.path.exists(D.DG2_FROZEN) and not force:
        raise SystemExit("%s exists (not rewritten without --force=1)" % D.DG2_FROZEN)
    if D.amendment() is not None:
        raise SystemExit("AM-D22 is already registered: dg2_frozen.json is not rewritten")
    st = D.status_lines()
    chl = open(D.DG1_RUN + "/chain.log", encoding="utf8", errors="replace").read().splitlines() if os.path.exists(D.DG1_RUN + "/chain.log") else []
    import glob
    reg = dict(auto_DG1_status_last_line=st[-1] if st else None, dg1_chain_log_last_line=chl[-1] if chl else None,
               dg1_run_records=len(glob.glob(D.DG1_RUN + "/run_c*.json")), dg1_pana_exists=os.path.isdir(D.DG1_RUN + "/pana"),
               dg1_q80_exists=os.path.exists(D.DG1_RUN + "/pana/q80_DG1.json"), time=time.strftime("%Y-%m-%d %H:%M:%S"))
    variants = {}
    for v in ("L12", "H", "L12D4"):
        sc = D.self_checks(v)
        if not sc["ok"]:
            raise SystemExit("self-checks of %s failed: %s" % (v, sc["failed"]))
        cf = sc["closed_form"]
        variants[v] = dict(
            params=D.params(v), ctrl=D.ctrl(v), run_id=D.main_id(v), smoke_id=D.smoke_id(v), changes_from_DG1=CHANGES[v],
            geometry=dict(dz_max_m=round(cf["dz_max_m"], 4), y_dz_max_m=round(cf["y_dz_max_m"], 3), added_water_half_tank_m3=round(cf["added_water_half_m3"], 1),
                          dz_y_ge_70_max_m=sc["dz_max_y_ge_70_m"], dz_y_ge_95_max_m=sc["dz_max_y_ge_95_m"]),
            particles_model=dict(dp1p0=sc["particles"]["dp1p0"]["model_groove"], dp0p5=sc["particles"]["dp0p5"]["model_groove"],
                                 added_lattice_dp0p5=sc["particles"]["dp0p5"]["added_lattice"], added_quadrature_dp0p5=round(sc["particles"]["dp0p5"]["quadrature"], 1),
                                 note="the lattice difference is not the quadrature by construction (AM-D21); the precheck compares the lattice count"),
            core_box=dict(D.CORE_BOXES[v], dz_min_m=round(sc["core_box"]["dz_min_m"], 3), dz_max_m=round(sc["core_box"]["dz_max_m"], 3)))
    variants["L12"]["expected_if_run"] = dict(
        curl_maxov_over_Hc="about 2.2 [1.8, 3.0] unconditional; GIVEN that DG1 failed the curl clause the same row model passes L12 in 4/19 "
                           "F1a-band cases, so P(S1) about 0.2 【計算+推測】",
        H_front="DG1 x 1.00 [0.985, 1.015] (U3 ramp-timing term unresolved; extrapolated: no U3 record later than x1 238) 【推測】",
        P_Q80="about 0.1 in F1a, about 0.04 in F13 【推測】")
    variants["H"]["expected_if_run"] = dict(
        H_front="DG1 x 1.011 [0.99, 1.03] (U3 depth term; b term unresolved +-1.3 %) 【計算+推測】",
        curl="DM1A rows sigma 0/2/3/4.5: 1.53/1.77/2.04/2.17 Hc 【計算】", P_Q80="about 0.1 or less 【推測】",
        caveat="three changes from DG1: a result cannot be attributed to one of them")
    variants["L12D4"]["expected_if_run"] = dict(
        H_front="DG1 x 0.977 [0.961, 1.0] (extrapolated 1 m beyond the U3 depth range) 【推測】",
        curl="the most robust in the row model (20/13 of 32 passes, DM1A/DM1 rows; 14/19 given a DG1 curl failure) 【計算】",
        allowed_only_if="DG1 S3 margin >= 2.5 % (H_front >= 10.54 m), and it is the 'deeper groove' dg1_frozen names: the user's explicit yes")
    fz = dict(
        id="DG2_FROZEN", status="registered before any DG1 main-run result (DG1 main chain running); OPT-IN ONLY",
        made_at=time.strftime("%Y-%m-%d %H:%M:%S"), tool="Tools/GWWaveGen/flip50dg2/g50dg2_pcfg.py freeze", amendment=D.AMENDMENT,
        plan=GC.PLAN_D_REL, plan_sha256=GC.sha256_file(GC.REPO + "/" + GC.PLAN_D_REL),
        dg1_frozen=dict(path=GG.DG1_FROZEN_REL, sha256=GG.DG1_SHA256),
        authority=dict(
            Q80_user_words_verbatim="DF1A 之后试一轮 DG1：破碎点两侧加浅沟，让卷起变窄，保住方案 D 的剖面。冻结规则，不行就停。",
            Q73_user_words_verbatim="按冻结规则自己连续跑：每轮发视频和数字，不等我回复就继续；同一方向连续 2 轮没进步就停下来问我。",
            user_2026_10_17_verbatim="在保证质量的情况下，继续提升工作效率，另外如果我没给你及时的反馈 就先按照你的推荐去执行任务，时间很紧任务不能停",
            reading="【選び】 dg1_frozen 'never' says a deeper groove, a wider or earlier ramp or any other bed is a new round that needs the user; "
                    "Q80 says 不行就停. So DG2 is never a default and never runs on 'no answer': it runs only after the user says yes in words "
                    "(optin.json carries the words). The 10/17 'tasks must not stop' is met by the delivery work, which is the no-answer default."),
        registered_before=reg,
        base_cfgs=dict(main=dict(path="Unity/Build/FLIP50/runs/ready/%s.json" % D.DG1_ID, sha256_16=D.DG1_READY_SHA16),
                       smoke=dict(path="Unity/Build/FLIP50/smoke/ready/%s.json" % GG.RUN_SMOKE, sha256_16=D.SMOKE_DG1_READY_SHA16),
                       rule="DG1's cfg with only run_id, case labels, the differing gr_* parms, the bed record, note and precheck changed "
                            "(g50dg2_pcfg.key_diff asserts it); same groove hip, no rebuild"),
        formula="dz = D (1 - exp(-(y/b)^2)) exp(-(y/Y)^2) S((x-x1)/(x2-x1)) (1 - S((x-x3)/(x4-x3))), S = smoothstep (the DG1 formula; chosen bed, "
                "not a measured site; only gravity, the bed and the incoming waves act; a_sum unchanged; no force toward a shape)",
        variants=variants,
        model_validity_gate=dict(
            code="Tools/GWWaveGen/flip50dg2/g50dg2_gate.py (sha256 in AM-D22)", rows="Unity/Build/FLIP50/_scratch/post_dg1/cw_flip_DM1A.json",
            rows_sha256=D.sha256_file(D.POST + "/cw_flip_DM1A.json"),
            grid=dict(sigma_m=[0, 1, 2, 3, 4.5, 6, 7.5, 9], scale=[1.0, 0.75], hc=[1.0, 0.96]), E_max_Hc=0.5, E_tie_Hc=0.05, n_min=3,
            dH=dict(L12=0.0, H=0.011, L12D4=-0.023), L12D4_needs_DG1_S3_margin=0.025,
            rule="fit the DM1A-row model to DG1's judged per-breaker curl/Hc at max overturn; the model holds only if the median |error| <= 0.5 Hc; "
                 "a candidate passes only if >= 3 consecutive breakers have curl <= 2.5 Hc at every grid point within 0.05 Hc of the best fit; "
                 "pick the passing allowed candidate with the largest predicted S3 margin; none -> no DG2; the user may still name a variant "
                 "explicitly (DG2:<v>), which is recorded as the user's choice against the gate"),
        eligible_modes=["F1a-CURL", "F13-CURL+HEIGHT", "F1c-PERIODIC-OTHER", "F2-SECTION"],
        eligible_also_needs="DG1 S0 ok, no analysis fault, DG1 H_front median >= 10.0 m",
        pre_run_gates=dict(
            numpy_self_checks="g50dg2_common.self_checks: dz exactly 0 on the axis; max dz and its |y| = closed form (1e-6 m, 0.002 m); dz = 0 and "
                              "the bed = D19B bit for bit outside x1..x4 and on the axis; dz < 2e-3 m for y >= 70 m and < 1e-5 m for y >= 95 m; "
                              "gradient vs finite differences < 1e-6; SDF sign and value; gr_on 0 / D 0 = D19B bit for bit; added water = closed "
                              "form within 0.05 m3; particle quadrature = closed form within 0.5 % (dp 1.0 and 0.5)",
            hython_bed_check="g50dg2_bedcheck_h.py (read only, the hip is never saved, sha before = after = build_check_g) + bedcheck-eval: CTRL gr_* "
                             "= the variant; OUT_BED vs numpy < 1 cm at every point; groove depth Houdini vs numpy < 1 cm and > 0.9 x the closed "
                             "form; SDF near the bed < 2 cm with no sign mismatch in the groove box x 230-360 m, |y| <= 60 m; dp 1.0 particles = "
                             "model within 0.2 %, none below the bed, x_max <= 350.75 m",
            smoke="as dg1_frozen smoke (gates_as_before + inlet 0.945 / 0.930 +- 0.03 + hip / CTRL gr_* (the variant) + frame-1 particles a, b, c "
                  "with the AM-D21 readings) with the variant's core box; one launch <= 29 min",
            launch_gate="g50g_chain's DG1 gate (precheck, table, plan, build_check_g, dg1_frozen sha, untouched, DF1A/DM1A order) with the DG2 cfg "
                        "accepted for its own gr_*; plus dg2_frozen sha = .sha256 = AM-D22, DG1 finished with Q80 not met, optin.json for the "
                        "variant with the user's words, the hython bed check ok on the current hip, the numpy self-checks, and for the main run "
                        "the DG2 smoke gates (pana/smoke_DG2.json ok on the current hip)"),
        run=dict(what="DG1 with the variant's gr_*: dp 0.5, 0-92 s (f_end 2209), stage A, chained launches <= 29 min, max_hours 3.0, resumed from "
                      "the last checkpoint after a max_hours stop up to 2 times; about 3.6 h 【計算】", d_round=4),
        criteria=dict(same_as="dg1_frozen.json criteria.Q80_met_requires_all S0-S4 against DM1A (q80 test of flip50g/g50g_ana.py, run in memory "
                              "with the variant's validity) -> pana/q80_DG2.json",
                      report_only="Q73 against DG1 (the previous round) beside S2 against DM1A; any S3 pass by < 1.5 % is reported 'within run "
                                  "noise' (DM1 vs DM1A 0.14 m, U3 rms 1.5 %)"),
        decision_after_DG2=[
            "S0 false -> not judged: read-only diagnosis; ask; no answer -> delivery by the rule without DG2",
            "Q80 met and verdict PASS -> DD3 of DG2 (+48 s) then its every-frame re-record; show the user",
            "Q80 met (partial) -> show the user; no answer -> DG2's every-frame re-record (delivery)",
            "Q80 not met -> Q73 stop (two groove rounds without meeting Q80): the shape search ends; ask; no answer -> delivery by the rule"],
        end_of_search="after DG2's verdict the shape search ends whatever the result: no DG3, no new bed family, no retune",
        delivery_rule=dict(
            among="DM1A, DG1 and DG2 (if run) with S0 ok",
            tiers=["1: Q80 met (two: the smaller median curl/Hc)",
                   "2: S1 true, S2 true and H_front >= 10.0 m (Q77): the smallest median curl/Hc, ties the higher back_best; this lowers the "
                   "height floor from S3 10.283 to Q77 10.0 and the run 'did not meet Q80'",
                   "3: DM1A (healthy, periodic every ~12 s at x 253-260, the best measured D section; curl 6.0 Hc); DA3 is the narrow alternative"],
            user="the user judges print-likeness from the compare mp4s of the top two; default (no prompt answer) = the rule's pick",
            set_when="after DM1A and DF1A were seen, before DG1's result"),
        never="no threshold, criterion, gate, decision rule, variant value or the delivery rule changes after any DG1 or DG2 result",
        tags="【測定】 measured, 【計算】 computed, 【推測】 guess, 【選び】 chosen")
    os.makedirs(os.path.dirname(D.DG2_FROZEN), exist_ok=True)
    raw = json.dumps(fz, indent=1, ensure_ascii=False).encode("utf8")
    with open(D.DG2_FROZEN, "wb") as fh:
        fh.write(raw)
    sh = hashlib.sha256(raw).hexdigest()
    open(D.DG2_FROZEN + ".sha256", "w", encoding="utf8").write("%s  dg2_frozen.json\n" % sh)
    return D.DG2_FROZEN, sh


# ====================================================================== check (no Houdini)
def check():
    t0 = time.time()
    out = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), tool="flip50dg2/g50dg2_pcfg.py check")
    fz = D.frozen_dg2()
    out["dg2_frozen"] = dict(present=fz is not None, sha256=D.sha256_file(D.DG2_FROZEN) if fz else None)
    out["am_d22_present"] = D.amendment() is not None
    out["untouched"] = GG.check_untouched()
    out["self_checks"] = {}
    out["cfgs"] = {}
    for v in ("L12", "H", "L12D4"):
        sc = D.self_checks(v)
        out["self_checks"][v] = dict(ok=sc["ok"], failed=sc["failed"], dz_max_m=sc["dz_max_m"], y=sc["dz_max_at_y_m"],
                                     particles={k: p["model_groove"] for k, p in sc["particles"].items()})
        for which in ("smoke", "main"):
            c, b0, diff = build_cfg(v, which)
            p, how = write_pending(c)
            out["cfgs"][c["run_id"]] = dict(path=p, how=how, sha16=D.sha16(p), precheck_ok=c["precheck"]["ok"], reason=c["precheck"]["reason"],
                                            particles=c["precheck"]["particles_model"], added=c["precheck"]["particles_added_by_groove"],
                                            diff={k: x for k, x in diff.items() if k not in ("ok", "bad")},
                                            time={k: x for k, x in (c["precheck"].get("time") or {}).items() if k in ("total_h_lo", "total_h_hi", "bound_h", "est_h")})
    # the launch gate of each DG2 cfg, dry (no run folder, nothing launched): expected refusals now = DG1 not finished, no opt-in, no bed check
    gates = {}
    for rid, x in out["cfgs"].items():
        r = subprocess.run([sys.executable, "-B", HERE + "/g50dg2_chain.py", x["path"], "--dry"], capture_output=True, text=True, encoding="utf8")
        try:
            gates[rid] = json.loads(r.stdout[r.stdout.find("{"):])
        except Exception:
            gates[rid] = dict(rc=r.returncode, stdout=r.stdout[-1500:], stderr=r.stderr[-1500:])
    out["dry_gates"] = gates
    # DD3 of DG1 (pass branch) from the run's current cfg.json, and the DM1A re-record (delivery default) with the measured-window tau 1759
    out["dd3_DG1"] = g2_call(G2.dd3, {"run": D.DG1_ID, "max_hours": "2.6"}) if os.path.exists(D.DG1_RUN + "/cfg.json") else "DG1 cfg.json missing"
    out["rr_DM1A"] = g2_call(G2.rr, {"run": D.DM1A_ID, "tau": "1759"})
    out["cpu_s"] = round(time.time() - t0, 1)
    p = D.PENDING + "/check_dg2.json"
    json.dump(out, open(p, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
    return out, p


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


def main(argv):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    pos, o = opts(argv)
    if not pos:
        print(__doc__); return 1
    cmd = pos[0]
    if cmd == "freeze":
        p, sh = freeze(force=bool(int(o.get("force", "0"))))
        print("frozen", p, sh)
    elif cmd == "cfg":
        vs = ["L12", "H", "L12D4"] if (len(pos) < 2 or pos[1] == "all") else [pos[1]]
        for v in vs:
            for which in ("smoke", "main"):
                c, b0, diff = build_cfg(v, which)
                if not c["precheck"]["ok"]:
                    print("NOT WRITTEN", c["run_id"], c["precheck"]["reason"]); continue
                p, how = write_pending(c)
                print(how, p, "sha16", D.sha16(p), "particles", c["precheck"]["particles_model"], "parms changed", diff["parms_changed"])
    elif cmd == "promote":
        print(json.dumps(promote(pos[1]), ensure_ascii=False))
    elif cmd in ("dd3", "rr"):
        r = g2_call(G2.dd3 if cmd == "dd3" else G2.rr, o, to=o.get("to", "pending"))
        print(json.dumps(r, ensure_ascii=False, indent=1, default=float))
        if not r.get("precheck_ok"):
            return 2
    elif cmd == "bedcheck":
        r = bedcheck(pos[1])
        print(json.dumps(dict(ok=r["ok"], failed=r.get("failed")), ensure_ascii=False))
        return 0 if r["ok"] else 2
    elif cmd == "bedcheck-eval":
        r = bedcheck_eval(pos[1], pos[2])
        print(json.dumps(dict(ok=r["ok"], failed=r.get("failed")), ensure_ascii=False))
        return 0 if r["ok"] else 2
    elif cmd == "check":
        r, p = check()
        print("check ->", p, "cpu_s", r["cpu_s"])
        print(" dg2_frozen", r["dg2_frozen"], "AM-D22", r["am_d22_present"], "untouched ok", r["untouched"]["ok"])
        for v, x in r["self_checks"].items():
            print(" self", v, x)
        for rid, x in r["cfgs"].items():
            print(" cfg", rid, x["how"], x["sha16"], "precheck", x["precheck_ok"], x["reason"], "particles", x["particles"], "added", x["added"],
                  "parms", x["diff"]["parms_changed"], "time", x["time"])
        for rid, g in r["dry_gates"].items():
            print(" gate", rid, g.get("gate_ok"), g.get("reasons"))
        for k in ("dd3_DG1", "rr_DM1A"):
            x = r[k]
            print(" %s" % k, x if isinstance(x, str) else {kk: x.get(kk) for kk in ("cfg", "run_id", "precheck_ok", "reason", "f_resume_est", "f_end", "frames")})
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
