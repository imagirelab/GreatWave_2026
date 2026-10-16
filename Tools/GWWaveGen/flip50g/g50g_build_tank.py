# -*- coding: utf-8 -*-
"""FLIP50 DG1 (AM-D20): build the SEPARATE groove hip Houdini/FLIP50/g50_tank_g.hiplc and its check _logs/build_check_g.json (hython; launched
by x50g_build.py, which first checks the start condition and waits for every other hython). 2026-10-17 written new (Claude).
It runs the unchanged flip50/g50_build_tank.py text (sha256_16 checked against dg1_frozen.json untouched) after exact, counted string
replacements, so the scene, the bands, the probes and every FLIP50 check are those of g50_tank.hiplc; only these differ:
  - VEX head: g50g_tanklib (bedy / bedgrad = D19B minus the frozen groove; CTRL gr_on, gr_D, gr_b, gr_Y, gr_x1..gr_x4; default gr_on 0 = D19B)
  - numpy bed: g50g_common.patch_modules (g49_common / g50_common bed functions with the groove, in memory)
  - hip Houdini/FLIP50/g50_tank_g.hiplc, inputs _logs/build_inputs_g.json, check _logs/build_check_g.json, test folder _logs/vdtest_g
  - the D19B checks run with the groove switched off (gr_on 0): they are the switch-off check of T0G
  - added checks (dg1_frozen.json pre_run_gates_T0G): DG1_strip (W 6, dp 0.5: bed, SDF, particles), DG1_3d (W 140, dp 0.5 grid: bed, SDF),
    DG1_3d_groove_box (x 230-360 m, |y| <= 60 m: bed, SDF, the groove depth Houdini sees), DG1_3d_particles_dp1 (W 140, dp 1.0: count vs
    the groove particle model, none below the groove bed, x_max <= 350.75 m), DG1_switch (gr_on 0: D19B < 1 mm, 665,000 particles),
    DG1_numpy (g50g_common.self_checks), untouched_before_save (dg1_frozen.json 'untouched'), dg1 (frozen file sha) -> all_ok.
The old hip Houdini/FLIP50/g50_tank.hiplc and _logs/build_check.json are never opened for writing (the save path is checked).
usage: py -3.10 -B x50g_build.py   (never run this file directly while another hython runs)
"""
import hou, os, sys, json, time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import g50g_common as GG       # noqa: E402

SRC = GG.TOOLS50 + "/g50_build_tank.py"

PARMS_G = r'''    ("lag_h", _bp["lag_h"], "FLIP49 lagoon depth"),
    # DG1 (AM-D20, dg1_frozen.json): the chosen groove pair beside the axis; default OFF (gr_on 0 = D19B); the DG1 cfgs set gr_on 1
    ("gr_on", 0.0, "DG1 groove pair on (0 = D19B)"),
    ("gr_D", GG.GR["D"], "DG1 groove depth scale D (m)"),
    ("gr_b", GG.GR["b"], "DG1 inner width b (m)"),
    ("gr_Y", GG.GR["Y"], "DG1 outer width Y (m)"),
    ("gr_x1", GG.GR["x1"], "DG1 ramp start x1 (m)"),
    ("gr_x2", GG.GR["x2"], "DG1 full depth from x2 (m)"),
    ("gr_x3", GG.GR["x3"], "DG1 fade start x3 (m)"),
    ("gr_x4", GG.GR["x4"], "DG1 fade end x4 (m)"),
'''

BOX_FN = r'''
def bed_box_check(tag, spec, xr=(230.0, 360.0), ym=60.0):
    """DG1: OUT_BED and the bed SDF against numpy inside the groove box (x 230-360 m, |y| <= 60 m) with the current CTRL, and the groove
    depth Houdini's bed shows (numpy D19B minus OUT_BED)."""
    P_ = ctrl_floats()
    o = np.array([P_["ox"], P_["oy"], P_["oz"]])
    out = dict(tag=tag, box_x=list(xr), box_abs_y_max=ym, spec_gr={k: v for k, v in spec.items() if k.startswith("gr_")})
    bw.cook(force=True)
    g_ = bedout.geometry()
    Pp = np.frombuffer(g_.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
    m = (Pp[:, 0] >= xr[0]) & (Pp[:, 0] <= xr[1]) & (np.abs(Pp[:, 2]) <= ym)
    zb = GC.bed_z(Pp[m, 0], Pp[m, 2], **spec)
    d = Pp[m, 1] - zb
    D19 = {k: v for k, v in spec.items() if not k.startswith("gr_")}
    dzh = GC.bed_z(Pp[m, 0], Pp[m, 2], **D19) - Pp[m, 1]
    dzn = GG.gr_dz(Pp[m, 0], Pp[m, 2])
    out.update(bed_points=int(m.sum()), bed_max_abs_dz_m=float(np.abs(d).max()), bed_ok=bool(np.abs(d).max() < 0.01),
               bed_vex_numpy_lt_1mm=bool(np.abs(d).max() < 1e-3), houdini_groove_dz_max_m=float(dzh.max()), numpy_groove_dz_max_m=float(dzn.max()))
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
        ix = (xs >= xr[0]) & (xs <= xr[1]); kz = np.abs(zs) <= ym
        a = a[kz][:, :, ix]
        Z, Y, X = np.meshgrid(zs[kz], ys, xs[ix], indexing="ij")
        ref = GC.bed_sdf(X, Y, Z, **spec)
        near = np.abs(ref) < 3.0
        far = np.abs(ref) > 0.05
        out["sdf_voxels"] = int(a.size)
        out["sdf_max_abs_diff_near_m"] = float(np.abs(a - ref)[near].max()) if near.any() else None
        out["sdf_sign_mismatch_frac"] = float(np.mean(np.sign(a[far]) != np.sign(ref[far])))
        out["sdf_ok"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 0.02 and out["sdf_sign_mismatch_frac"] == 0.0)
    out["ok"] = bool(out["bed_ok"] and out["sdf_ok"] and abs(out["houdini_groove_dz_max_m"] - out["numpy_groove_dz_max_m"]) < 0.01
                     and out["numpy_groove_dz_max_m"] > 2.0)
    return out


'''

DG1_CHECKS = r'''    # ---- DG1 (AM-D20, dg1_frozen.json pre_run_gates_T0G): the groove on; the D19B checks above ran with gr_on 0 (switch-off)
    SPG = dict(GC.SPEC_D19B, **GG.SPEC_GR_ON)
    set_box(0.5, GC.W_STRIP, SPG)
    CHK["DG1_strip"] = bed_check("DG1 strip (W 6 m, dp 0.5 m, groove on)")
    particle_check(CHK["DG1_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, SPG)
    CHK["DG1_3d"] = bed_check("DG1 3D (W 140 m, dp 0.5 m grid, groove on)")
    CHK["DG1_3d_groove_box"] = bed_box_check("DG1 groove box x 230-360 m, |y| <= 60 m (dp 0.5 m grid)", GC.bed_spec(parms=ctrl_floats()))
    set_box(1.0, GC.W_MAIN, SPG)
    CHK["DG1_3d_particles_dp1"] = particle_check(dict(W=float(ctrl.parm("W").eval())), GC.bed_spec(parms=ctrl_floats()))
    CHK["DG1_switch"] = GG.switch_numbers(CHK)
    CHK["DG1_numpy"] = GG.self_checks()
    CHK["untouched_before_save"] = GG.check_untouched()
    restore_ctrl()
    # 3: Fenton probe at h0 19 m (S2D strips)
'''

REPL = [
    ("import importlib, numpy as np, g50_tanklib as L, g50_common as GC, g50_table as TB\n"
     "importlib.reload(L); importlib.reload(GC); importlib.reload(TB)\n",
     "import importlib, numpy as np, g50_table as TB\n"
     "import g50g_tanklib as L                        # DG1: the FLIP50 VEX with the groove bed head (g50g_tanklib)\n"
     "GC = GG.patch_modules(hip=True)                 # DG1: g50_common with the groove bed functions (in memory); GC.HIP = g50_tank_g.hiplc\n", 1),
    ('INPUTS = json.load(open(GC.B50 + "/_logs/build_inputs.json", encoding="utf8"))',
     'INPUTS = json.load(open(GG.BUILD_INPUTS_G, encoding="utf8"))', 1),
    ('    ("lag_h", _bp["lag_h"], "FLIP49 lagoon depth"),\n', PARMS_G, 1),
    ("    SP = dict(GC.SPEC_D19B)\n", "    SP = dict(GC.SPEC_D19B, **GG.SPEC_GR_OFF)          # DG1: D19B = the groove switched off (gr_on 0)\n", 1),
    ("    restore_ctrl()\n    # 3: Fenton probe at h0 19 m (S2D strips)\n", DG1_CHECKS, 1),
    ('vdt = GC.B50 + "/_logs/vdtest"', 'vdt = GC.B50 + "/_logs/vdtest_g"', 1),
    ("CHK = dict(date=time.strftime(", BOX_FN + "CHK = dict(date=time.strftime(", 1),
    ("vex_head_info=L.HEAD_INFO, inputs=INPUTS)", "vex_head_info=L.HEAD_INFO, inputs=INPUTS, dg1=GG.frozen_ref())", 1),
    ('and not CHK.get("error"))', 'and GG.dg1_build_ok(CHK)[0] and not CHK.get("error"))', 1),
    ('GC.B50 + "/_logs/build_check.json"', "GG.BUILD_CHECK_G", 2),
    ("hou.hipFile.save(HIP)",
     "CHK['DG1_items'] = GG.dg1_build_ok(CHK)[1]\n"
     "if os.path.normcase(os.path.abspath(HIP)) != os.path.normcase(os.path.abspath(GG.HIP_G)):\n"
     "    raise SystemExit('DG1 build: refusing to save %s (only %s)' % (HIP, GG.HIP_G))\n"
     "hou.hipFile.save(HIP)", 1),
]

if __name__ == "__main__":
    GG.frozen()
    src = GG.read_source(SRC, "flip50/g50_build_tank.py")
    src2, info = GG.apply_replacements(src, REPL)
    print("DG1 build: g50_build_tank.py patched", json.dumps(info, ensure_ascii=False)[:600])
    sys.stdout.flush()
    code = compile(src2, SRC + " [DG1: patched in memory by flip50g/g50g_build_tank.py]", "exec")
    exec(code, {"__name__": "__main__", "__file__": SRC, "GG": GG})
