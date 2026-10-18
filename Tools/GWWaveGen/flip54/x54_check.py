# -*- coding: utf-8 -*-
"""FLIP54 K54: the SCENE CHECK of the K54 strips (run with hython; the launcher auto_K54.py runs it once before the first strip).
2026-10-18 written new (Claude, FLIP54 builder K) from flip49/g49_build_tank.py's own checks (bed_check, particle_check, the sf probe and
relax_check; FROZEN, read only) - but it NEVER builds or saves a scene: it loads Houdini/FLIP49/g49_tank.hiplc (the scene every
campaign-B strip ran in), sets its CTRL to each K54 strip and compares the compiled VEX with numpy:
  beds       for every distinct K54 bed (K0 / K0p / A12 plain 1:10 onto 7.0 m; K1-K5 two-slope): OUT_BED heights and the collision SDF
             (OUT_BED_SDF) against g54_common.bed_z / bed_sdf (< 1 mm), the initial particles (OUT_PARTICLES: none below the bed, count
             within 0.2 % of g54_common.count_particles) on the D19B strip box (Lx 412 m, zb -19 m, W 6 m, dp 0.5 m)
  sf probe   the Fenton target at h0 19 m (T 9.33 s at the pilot H, and T 12 s at A12's pilot-rule H; tables from k54/tables) against
             numpy g54_common.sf_target (|du|, |dw| <= 1e-6 c, |deta| <= 1e-6 H)
  relax      the band functions (inlet relaxation, exit sponge 332-412 m, stage-A divergence window 110-327 m) at probe points against the
             numpy transliteration relax_np (as g49_build_tank.relax_check, layout K54)
  scene      the hip's sha256 before = after = the FLIP49 build check's (never saved)
Writes only Unity/Build/FLIP54/_logs/build_check54.json (+ the divergence test file in Unity/Build/FLIP54/_logs/vdtest54/).
usage: hython x54_check.py [<sf table T9.33 json> <sf table T12 json>]   (default: the tables of the pilot H written by g54_pcfg.py dry/cfg)
"""
import hou, sys, os, json, time, traceback
import numpy as np

sys.dont_write_bytecode = True
HERE = r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip54"
sys.path.insert(0, HERE)
import g54_common as C

HIP = C.HIP
SHA0 = C.sha256_file(HIP)
CHK = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=HIP, hip_sha256_before=SHA0, hip_expected=C.HIP_SHA256, module_shas=C.module_shas())
hou.hipFile.load(HIP, suppress_save_prompt=True, ignore_load_warnings=True)
CHK["houdini"] = hou.applicationVersionString()
S = "/obj/G49_SETUP/"
ctrl = hou.node(C.CT_NODE)
bw, bedout = hou.node(S + "bed_height"), hou.node(S + "OUT_BED")
bsdfw, bsdfout = hou.node(S + "bed_sdf_value"), hou.node(S + "OUT_BED_SDF")
sol, cols, pts0, ptsout = hou.node(S + "solution_table"), hou.node(S + "particle_columns"), hou.node(S + "init_particles"), hou.node(S + "OUT_PARTICLES")
sftab, sftabout = hou.node(S + "sf_table"), hou.node(S + "OUT_SF")
sfp, sfp_pts = hou.node(S + "sf_probe"), hou.node(S + "sf_probe_pts")
rlp, rlp_pts = hou.node(S + "relax_probe"), hou.node(S + "relax_probe_pts")
vdp, vdout = hou.node(S + "voldiv_table"), hou.node(S + "OUT_VOLDIV")
CHK["nodes_found"] = {n: (hou.node(S + n) is not None) for n in ("CTRL", "bed_height", "OUT_BED", "bed_sdf_value", "OUT_BED_SDF", "solution_table",
                                                                  "particle_columns", "init_particles", "OUT_PARTICLES", "sf_table", "OUT_SF",
                                                                  "sf_probe", "sf_probe_pts", "relax_probe", "relax_probe_pts", "voldiv_table", "OUT_VOLDIV")}


def ctrl_floats():
    return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}


def set_ctrl(d):
    for nm, v in d.items():
        ctrl.parm(nm).set(v)


DEFAULT_CTRL = ctrl_floats()
DEFAULT_STR = {nm: ctrl.parm(nm).evalAsString() for nm in ("sol_npz", "sf_tab", "vol_dir")}


def restore_ctrl():
    set_ctrl(DEFAULT_CTRL)
    for nm, v in DEFAULT_STR.items():
        ctrl.parm(nm).set(v)


def set_box(spec):
    b = C.box48(C.DP, Lx=C.LX, W=C.W_STRIP, zb=C.ZB, floor_pad=2)
    d = dict(dp=b["dp"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x1=b["Lx"], crop_z1=b["W"],
             floor_pad=2.0, x0=0.0, h0=C.H0)
    d.update(C.bed_parms(spec))
    set_ctrl(d)
    return b


def bed_check(tag, spec_want):
    """g49_build_tank.bed_check (copied) + the CTRL spec equals the arm's spec."""
    P_ = ctrl_floats()
    spec = C.bed_spec(parms=P_)
    o = np.array([P_["ox"], P_["oy"], P_["oz"]])
    out = dict(tag=tag, kind=C.bed_kind(spec), W=float(P_["W"]), Lx=float(P_["Lx"]), zb=float(P_["zb"]), Hz=float(P_["Hz"]), dp=float(P_["dp"]),
               o=[float(v) for v in o])
    out["ctrl_spec_equals_arm"] = bool(all((spec_want.get(k) is None and spec.get(k) is None) or (spec_want.get(k) is not None and spec.get(k) is not None
                                           and abs(float(spec_want[k]) - float(spec[k])) < 1e-9) for k in spec_want))
    bw.cook(force=True)
    g_ = bedout.geometry()
    Pp = np.frombuffer(g_.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
    zb = C.bed_z(Pp[:, 0], Pp[:, 2], **spec)
    d = Pp[:, 1] - zb
    out["bed_points"] = int(len(Pp)); out["bed_max_abs_dz_m"] = float(np.abs(d).max())
    out["bed_ok"] = bool(np.abs(d).max() < 0.01)
    out["bed_vex_numpy_lt_1mm"] = bool(np.abs(d).max() < 1e-3)
    out["bed_min_depth_m"] = float(-zb.max()); out["bed_max_depth_m"] = float(-zb.min())
    out["box_floor_m"] = float(P_["zb"]) - float(P_["floor_pad"]) * float(P_["dp"]) * float(P_["gridscale"])
    bsdfw.cook(force=True)
    gs = bsdfout.geometry()
    vols = [q for q in gs.prims() if q.type() in (hou.primType.Volume, hou.primType.VDB)]
    out["sdf_ok"] = False
    if vols:
        v = vols[0]
        r = v.resolution()
        a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0]).astype(np.float64)
        p0 = np.array([float(c) for c in v.indexToPos((0, 0, 0))]) - o
        p1 = np.array([float(c) for c in v.indexToPos((1, 1, 1))]) - o
        dd = p1 - p0
        xs = p0[0] + dd[0] * np.arange(r[0]); ys = p0[1] + dd[1] * np.arange(r[1]); zs = p0[2] + dd[2] * np.arange(r[2])
        Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
        ref = C.bed_sdf(X, Y, Z, **spec)
        near = np.abs(ref) < 3.0
        out["sdf_res"] = list(r); out["sdf_max_abs_diff_near_m"] = float(np.abs(a - ref)[near].max()) if near.any() else None
        out["sdf_vex_numpy_lt_1mm"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 1e-3)
        far = np.abs(ref) > 0.05
        out["sdf_sign_mismatch_frac"] = float(np.mean(np.sign(a[far]) != np.sign(ref[far])))
        out["sdf_ok"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 0.02 and out["sdf_sign_mismatch_frac"] == 0.0)
        out["sdf_covers_box_floor"] = bool(ys[0] <= out["box_floor_m"] + 1e-6)
    return out, spec


def particle_check(rec, spec):
    """g49_build_tank.particle_check (copied)."""
    P_ = ctrl_floats()
    o = np.array([P_["ox"], P_["oy"], P_["oz"]])
    hou.setFrame(1)
    for n in (sol, cols, pts0):
        n.cook(force=True)
    g = ptsout.geometry()
    if g is None:
        rec["particles_error"] = "no geometry"; rec["particles_ok"] = False
        return rec
    Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
    gap = Pp[:, 1] - C.bed_z(Pp[:, 0], Pp[:, 2], **spec)
    rec["particles"] = int(len(Pp)); rec["n_below_bed"] = int((gap < 0).sum())
    rec["gap_min_m"] = float(gap.min()); rec["z_max_m"] = float(Pp[:, 1].max())
    n_model, V = C.count_particles(spec, float(P_["Lx"]), float(P_["W"]), float(P_["dp"]), zb=float(P_["zb"]), bed_gap=float(P_["bed_gap"]))
    rec["particles_model"] = int(n_model); rec["particles_ratio_houdini_over_model"] = float(len(Pp)) / max(n_model, 1)
    rec["particles_ok"] = bool(rec["n_below_bed"] == 0 and abs(rec["particles_ratio_houdini_over_model"] - 1.0) < 0.002)
    return rec


def sf_probe(sfT, tag):
    """the g49_build_tank sf probe (copied) at h0 19 m: VEX sfwave vs numpy sf_target (E = 1)."""
    ctrl.parm("sf_tab").set(C.sf_tab_string(sfT))
    set_ctrl(dict(h0=C.H0, x_p=C.X_P))
    sftab.cook(force=True)
    sg = sftabout.geometry()
    sfinfo = {a_.name(): sg.attribValue(a_.name()) for a_ in sg.globalAttribs() if a_.name() in ("sfh", "sfk", "sfc", "sfUb", "sfN")}
    P_ = ctrl_floats()
    pts = []
    for x_ in (0.0, 20.0, 50.0, 80.0, 95.0, 130.0, 200.0):
        for t_ in (0.0, 3.1, 7.7, 11.9):
            e_ = float(C.sf_target(x_, 0.0, t_, sfT, P_, E=1.0)[3].ravel()[0])
            for y_ in (-18.5, -12.0, -6.0, -2.0, 0.5 * e_, e_ + 1.0):
                pts.append(dict(px=x_, py=y_, pt=t_))
    sfp_pts.parm("pts_json").set(json.dumps(pts))
    sfp.cook(force=True)
    g_ = sfp.geometry()
    ev = np.array(g_.pointFloatAttribValues("eta_v")); uv = np.array(g_.pointFloatAttribValues("u_v")); wv = np.array(g_.pointFloatAttribValues("w_v"))
    X_ = np.array([p["px"] for p in pts]); Y_ = np.array([p["py"] for p in pts]); T_ = np.array([p["pt"] for p in pts])
    _, un, wn, en, _ = C.sf_target(X_, Y_, T_, sfT, P_, E=1.0)
    c_ = float(sfT["c"]); H_ = float(sfT["H"])
    out = dict(tag=tag, n=len(pts), sf_table=sfinfo, sfN_ok=bool(int(sfinfo.get("sfN", -1)) == len(sfT["B"])),
               sfh_ok=bool(abs(float(sfinfo.get("sfh", -1)) - C.H0) < 1e-9),
               u_max_abs_over_c=float(np.abs(uv - un.ravel()).max() / c_), w_max_abs_over_c=float(np.abs(wv - wn.ravel()).max() / c_),
               eta_max_abs_over_H=float(np.abs(ev - en.ravel()).max() / H_), c=c_, H=H_, T=float(sfT["T"]), L=float(sfT["L"]), h=float(sfT["h"]))
    out["ok"] = bool(out["sfN_ok"] and out["sfh_ok"] and out["u_max_abs_over_c"] <= 1e-6 and out["w_max_abs_over_c"] <= 1e-6 and out["eta_max_abs_over_H"] <= 1e-6)
    sfp_pts.parm("pts_json").set("[]")
    return out


def relax_np(pl, v0, t, dts, P_, sf):
    """g49_build_tank.relax_np (copied): the band functions in numpy (du_abs given)."""
    x = pl[0]
    v = np.array(v0, float)
    if P_["relax_on"] > 0.5 and x < P_["xg_end"] and P_["relax_g"] > 0:
        chi = (P_["xg_end"] - x) / max(P_["xg_end"] - P_["x0"], 1e-6)
        c = min(max(chi, 0.0), 1.0)
        w = min(max((np.exp(c ** 3.5) - 1.0) / (np.e - 1.0) * P_["relax_g"], 0.0), 1.0)
        wdt = 1.0 - (1.0 - w) ** (dts / P_["dt0"])
        wt = float(C.smooth01((x - P_["x0"]) / P_["wall_taper_m"])) if P_["wall_taper_m"] > 0 else 1.0
        E = float(C.envelope(x, t, P_))
        ux = 0.0
        if P_["sf_on"] > 0.5:
            _, u, _, _, _ = C.sf_target(x, pl[1], t, sf, P_, E=E)
            ux = float(u.ravel()[0])
        if P_["duabs_on"] > 0.5:
            ux += wt * P_["_du_abs"]
        v = np.array([v[0] + (ux - v[0]) * wdt, v[1], v[2] + (0.0 - v[2]) * wdt])
    x1 = P_["x0"] + P_["Lx"]
    if P_["abs_on"] > 0.5 and x > P_["xa0"]:
        chi = min(max((x - P_["xa0"]) / max(x1 - P_["xa0"], 1e-6), 0.0), 1.0)
        w2 = 1.0 - np.exp(-P_["abs_sigma"] * chi ** P_["abs_pow"] * dts)
        v = np.array([v[0] * (1 - w2), v[1], v[2] * (1 - w2)])
    return v


def relax_check(spec, sfT):
    """g49_build_tank.relax_check (copied) with the K54 layout: box 412 m x zb -19 m, W 6 m, sponge 332-412 m (sigma 1.41), window 110-327 m."""
    vdt = C.LOG_DIR + "/vdtest54"
    os.makedirs(vdt, exist_ok=True)
    DV = (0.0013, -0.0007, 0.21)
    open(vdt + "/vd_00001.txt", "w").write("%r %r %r\n" % DV)
    set_box(spec)
    ctrl.parm("sf_tab").set(C.sf_tab_string(sfT))
    on = dict(relax_on=1.0, abs_on=1.0, sf_on=1.0, in_gain=1.07, xa0=C.XA0, abs_sigma=C.EX_SIGMA, abs_pow=C.EX_POW, duabs_on=1.0, volcorr_on=1.0,
              hold_on=1.0, vol_x0=C.VOL_X[0], vol_x1=C.VOL_X[1], ramp_s=2.0 * float(sfT["T"]), xg_end=C.IN_X1, x_p=C.X_P, wall_taper_m=C.WALL_TAPER,
              hold_x0=C.HOLD_X[0], hold_x1=C.HOLD_X[1])
    set_ctrl(on)
    ctrl.parm("vol_dir").set(vdt)
    hou.setFrame(1)
    vdp.cook(force=True)
    vg_ = vdout.geometry()
    vread = [vg_.attribValue(nm) for nm in ("vol_div", "vol_div_band", "du_abs")]
    P_ = ctrl_floats(); P_["_du_abs"] = DV[2]
    xs_ = (1.0, 19.0, 70.0, 99.0, 105.0, 150.0, 250.0, 326.0, 328.0, 331.0, 333.0, 360.0, 390.0, 411.5)
    rows = []
    for x_ in xs_:
        for y_ in (-12.0, -1.0):
            for t_, dts_ in ((0.0, 1.0 / 24.0), (13.3, 1.0 / 96.0), (40.0, 1.0 / 48.0)):
                rows.append(dict(px=x_, py=y_, pz=3.0, pt=t_, dts=dts_, v0=(0.7, -0.3, 0.4)))
    rlp_pts.parm("pts_json").set(json.dumps(rows))
    rlp.cook(force=True)
    g_ = rlp.geometry()
    v1 = np.array(g_.pointFloatAttribValues("v1")).reshape(-1, 3); dv_ = np.array(g_.pointFloatAttribValues("div"))
    ref = np.array([relax_np((r["px"], r["py"], r["pz"]), r["v0"], r["pt"], r["dts"], P_, sfT) for r in rows])
    volx = C.VOL_X
    dref = np.array([(DV[0] if volx[0] <= r["px"] <= volx[1] else 0.0) + (DV[1] if C.HOLD_X[0] <= r["px"] <= C.HOLD_X[1] else 0.0) for r in rows])
    vert_same = bool(np.allclose(v1[:, 1], -0.3, atol=1e-6))
    mid = np.array([C.IN_X1 + 5.0 <= r["px"] < C.XA0 - 1e-9 for r in rows])
    out = dict(n=len(rows), Lx=float(P_["Lx"]), xa0=float(P_["xa0"]), vol_x=[float(P_["vol_x0"]), float(P_["vol_x1"])], zb=float(P_["zb"]),
               voldiv_read=vread, voldiv_ok=bool(np.allclose(vread, DV, atol=1e-12)),
               v_max_abs_diff=float(np.abs(v1 - ref).max()), div_max_abs_diff=float(np.abs(dv_ - dref).max()),
               vertical_unchanged=vert_same, untouched_between_bands=bool(np.allclose(v1[mid], np.array([0.7, -0.3, 0.4]), atol=1e-6)),
               exit_band_damps=bool(np.all(np.abs(v1[np.array([r["px"] > C.XA0 + 1.0 for r in rows]), 0]) < 0.7)))
    out["tolerance_note"] = "point attributes are stored as float32: v within 1e-6 m/s, div within 1e-9 1/s"
    out["ok"] = bool(out["voldiv_ok"] and out["v_max_abs_diff"] < 1e-6 and out["div_max_abs_diff"] < 1e-9 and vert_same and out["untouched_between_bands"]
                     and out["exit_band_damps"])
    rlp_pts.parm("pts_json").set("[]")
    return out


def table(path_or_none, T, H):
    p = path_or_none or C.table_file(T, H)
    return json.load(open(p, encoding="utf8")), p


try:
    beds = {}
    for arm in C.ARMS:
        key = tuple(C.arm_bed(arm))
        beds.setdefault(key, []).append(arm)
    CHK["beds"] = {}
    for key, arms in beds.items():
        sp = C.spec_for(arms[0])
        set_box(sp)
        r, spec = bed_check("K54 %s (pg_hL %g, pg_s2 %g, shelf %g m; W 6 m, dp 0.5 m, box 412 m x zb -19 m)" % ("/".join(arms), key[0], key[1], key[2]), sp)
        particle_check(r, spec)
        r["arms"] = arms
        CHK["beds"]["/".join(arms)] = r
        print("BED", "/".join(arms), r.get("bed_ok"), r.get("sdf_ok"), r.get("particles_ok"), r.get("bed_max_abs_dz_m"), r.get("particles")); sys.stdout.flush()
    restore_ctrl()
    a1 = sys.argv[1] if len(sys.argv) > 1 else None
    a2 = sys.argv[2] if len(sys.argv) > 2 else None
    sf1, p1 = table(a1, C.T_MAIN, C.H_GUESS)
    sf2, p2 = table(a2, C.T_A12, C.h_a12(C.H_GUESS))
    CHK["sf_probe_T9p33"] = sf_probe(sf1, p1)
    CHK["sf_probe_T12"] = sf_probe(sf2, p2)
    restore_ctrl()
    CHK["relax_probe_K54"] = relax_check(C.spec_for("K1"), sf1)
    restore_ctrl()
except Exception as e:
    CHK["error"] = repr(e)[:400]
    CHK["traceback"] = traceback.format_exc()[-3000:]
    try:
        restore_ctrl()
    except Exception:
        pass
CHK["hip_sha256"] = C.sha256_file(HIP)
CHK["hip_unchanged"] = bool(CHK["hip_sha256"] == SHA0 == C.HIP_SHA256)
bk = CHK.get("beds") or {}
CHK["all_ok"] = bool(all(CHK["nodes_found"].values()) and len(bk) == len(set(tuple(C.arm_bed(a)) for a in C.ARMS))
                     and all(v.get("bed_ok") and v.get("sdf_ok") and v.get("particles_ok") and v.get("ctrl_spec_equals_arm") for v in bk.values())
                     and (CHK.get("sf_probe_T9p33") or {}).get("ok") and (CHK.get("sf_probe_T12") or {}).get("ok")
                     and (CHK.get("relax_probe_K54") or {}).get("ok") and CHK["hip_unchanged"] and not CHK.get("error"))
os.makedirs(C.LOG_DIR, exist_ok=True)
json.dump(CHK, open(C.BUILD_CHECK, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
print("BUILD_CHECK54", json.dumps(dict(all_ok=CHK["all_ok"], hip_unchanged=CHK["hip_unchanged"], error=CHK.get("error"),
                                       beds={k: [v.get("bed_ok"), v.get("sdf_ok"), v.get("particles_ok")] for k, v in bk.items()},
                                       sf=[(CHK.get(k) or {}).get("ok") for k in ("sf_probe_T9p33", "sf_probe_T12")],
                                       relax=(CHK.get("relax_probe_K54") or {}).get("ok")), ensure_ascii=False))
sys.stdout.flush()
