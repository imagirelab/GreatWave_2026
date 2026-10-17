# -*- coding: utf-8 -*-
"""FLIP52B plan DFG-2B: build the tank scene Houdini/FLIP52B/g52b_tank.hiplc (hython, a few min; launched by x52b_build.py, which waits for
every other hython first). GENERATED 2026-10-17 by flip52b/g52b_mkcopy.py from flip52/g52_build_tank.py (sha256 d4747657dcd50a8fc548af2f40fcc5d578202b94ef89b81da1cf70f51f05f2f7, not edited) by exact,
counted string replacements. The scene = the FLIP52 scene (same particle seeding, surface VDB, FLIP Solver 2.0, bed SDF, read / surface paths,
stage A/B/C nodes, node names G52_*, the N-layer VEX of flip52/g52_tanklib.py unchanged) on the D19B tank of FLIP50 / plan E:
  - constants from flip52b/g52b_common.py: box48 D19B (x 0-412 m, y 0-140 m, z -19 .. +17 m, floor pad 2 cells), the D19B bed (1:10 from
    x 160.25 m) through the FLIP48 plain path, bands as option D (inlet 0-100 m, taper 20 m, side band 95-140 m generating to x 180.25 m,
    absorbing from 210.25 m, taper 11.25 m), no exit sponge (the beach), ramp 14 s, dir_tf = the DFG-2B first focus time. Every band default is
    OFF (still water); g52b_run.py switches them on from the cfg parms.
Checks (Unity/Build/FLIP52B/_logs/build_check52b.json; all_ok false -> g52b_chain.py never starts):
  1. bed: OUT_BED heights and the bed SDF against numpy on the D19B strip (W 6 m) and the D19B 3D box (W 140 m) on the dp 0.5 grid; numpy
     D19B = the analytic -(19 - max(x - 160.25, 0)/10) bit for bit (the FLIP50 check).
  2. particles: Houdini seeding against count_particles: strip at dp 0.5, 3D at dp 1.0 (W 140 m); none below the bed.
  3. N-layer directional table: OUT_DIRTAB detail and dir_probe (VEX dirwave, g = 1) against the numpy mirror flip52/g52_table.dirwave_np
     (within 1e-5 of the scale).
  4. bands: relax_probe (VEX relax_apply + vc_divergence) against g52_table.relax_np on the D layout (the FLIP50 probe points; dir_on 1 with
     the N-layer table, ret_on 1, stage-C test file, in_gain 1.03 / sd_gain 0.97); vertical velocity unchanged, interior untouched, the side
     absorber damps; 'exit sponge damps' only when abs_on.
  5. the saved scene's CTRL equals the build defaults (still water, every band off).
usage: py -3.10 x52b_build.py  (writes the table, waits for other hython, runs hython g52b_build_tank.py)
"""
import hou, os, sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip52b")
import importlib, numpy as np, g52_tanklib as L, g52b_common as GC, g52_table as TB
importlib.reload(L); importlib.reload(GC); importlib.reload(TB)

HIP = GC.HIP
CT = L.CT
INPUTS = json.load(open(GC.BUILD_INPUTS, encoding="utf8"))       # x52_build.py: the DFG2 table npz (and the branch tables)
B0 = GC.box52(0.5, W=GC.W_STRIP)                                  # default: the flat strip (light cooks in the checks)
AX = dict(GC.SPEC_BED)

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G52_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
_bp = GC.bed_parms(AX)
PARMS = [
    ("dp", 0.5, "particle separation dp (m)"),
    ("gridscale", 2.0, "Grid Scale (grid = dp x this)"),
    ("x0", 0.0, "upstream wall x0 (m)"),
    ("Lx", B0["Lx"], "box length x (m)"),
    ("W", B0["W"], "box half width, lateral 0..W (m)"),
    ("zb", GC.ZB, "flat seabed / box zb (m)"),
    ("Hz", B0["Hz"], "box height from zb (m)"),
    ("h0", GC.H0, "flat depth h0 (m)"),
    ("maxsub", 8.0, "FLIP max substeps"),
    ("minsub", 1.0, "FLIP min substeps"),
    ("cfl", 1.0, "CFL Condition"),
    ("pcfl", 0.75, "Particle Advection CFL"),
    ("t_off", 0.0, "time of frame 1 (s)"),
    ("ox", B0["ox"], "Houdini x = plan x + ox"),
    ("oy", B0["oy"], "Houdini up y = plan z + oy"),
    ("oz", B0["oz"], "Houdini lateral z = plan y + oz"),
    # bed (g48 names; D19B = plain path k 0, toe 160.25 m, 1:10)
    ("ridge_on", _bp["ridge_on"], "bed on (0 = flat)"),
    ("ridge_x0", _bp["ridge_x0"], "slope toe x_toe (m) (D19B 160.25 m)"),
    ("ridge_k", _bp["ridge_k"], "lateral sech^2 k (0)"),
    ("ridge_s", _bp["ridge_s"], "slope 1:s"),
    ("shelf_h", _bp["shelf_h"], "shelf depth (m) (0 = none)"),
    ("ridge_kend", _bp["ridge_kend"], "taper end k (< 0 none)"),
    ("ridge_xk1", _bp["ridge_xk1"], "taper start x"),
    ("ridge_xk2", _bp["ridge_xk2"], "taper end x"),
    ("ch_h", _bp["ch_h"], "side channel depth (0 none)"),
    ("ch_y0", _bp["ch_y0"], "channel wall |y|"),
    ("ch_w", _bp["ch_w"], "channel wall width"),
    ("ch_x0", _bp["ch_x0"], "channel start x"),
    ("ch_lx", _bp["ch_lx"], "channel ramp length"),
    ("ledge_s1", 0.0, "g48 ledge 1:s1 (0)"),
    ("ledge_dl", 0.0, "g48 ledge dL"),
    ("ledge_s2", 0.0, "g48 ledge 1:s2"),
    ("pg_hL", _bp["pg_hL"], "FLIP49 ledge foot depth (0 none)"),
    ("pg_s2", _bp["pg_s2"], "FLIP49 ledge slope"),
    ("b_end", _bp["b_end"], "FLIP49 flat-top half width (0 none)"),
    ("b_x1", _bp["b_x1"], "FLIP49 flat-top start x"),
    ("b_x2", _bp["b_x2"], "FLIP49 flat-top end x"),
    ("lag_xb", _bp["lag_xb"], "FLIP49 lagoon x_back (>= 1e8 none)"),
    ("lag_s", _bp["lag_s"], "FLIP49 lagoon slope"),
    ("lag_h", _bp["lag_h"], "FLIP49 lagoon depth"),
    ("bed_gap", 0.5, "no particles within this x dp above the bed"),
    ("floor_pad", 2.0, "box floor this many cells below zb"),
    ("wave_on", 0.0, "solitary initial state (0: still water)"),
    ("side_pad", 0.0, "symmetry plane as SDF wall (0: box wall)"),
    # bands (all off by default)
    ("relax_on", 0.0, "inlet band on"),
    ("abs_on", 0.0, "exit sponge on"),
    ("sf_on", 0.0, "inlet target = Fenton wave (unused in FLIP52)"),
    ("dir_on", 0.0, "band target = N-layer directional table"),
    ("dir_tf", GC.T_F, "focus time t_f of the table phases (s)"),
    ("ret_on", 0.0, "add the zero-mean-mass-flux return current g^2 (mx, my)"),
    ("sd_on", 0.0, "side band on"),
    ("sd0", GC.SD0, "side band inner edge y (m); outer edge = W"),
    ("sd_gen", GC.SD_GEN, "side band generates for x <= sd_gen (m)"),
    ("sd_sw", GC.SD_SW, "side band absorbs for x >= sd_sw (m), smooth01 blend between"),
    ("sd_sigma", GC.SD_SIGMA, "side absorber sigma (1/s)"),
    ("sd_pow", GC.SD_POW, "side absorber chi power"),
    ("sd_taper_m", GC.SD_TAPER, "target taper to the outer side wall (m)"),
    ("sd_gain", 1.0, "side band target gain"),
    ("relax_g", 1.0, "band strength"),
    ("dt0", 1.0 / 24.0, "reference step dt0 of the band weight (s)"),
    ("ramp_s", GC.RAMP_S, "half-cosine ramp (s)"),
    ("wall_taper_m", GC.WALL_TAPER, "target taper to the upstream wall (m)"),
    ("in_gain", 1.0, "inlet band target gain"),
    ("x_p", 80.0, "Fenton phase reference x_p (m) (unused)"),
    ("xg_end", GC.IN_X1, "inlet band end x (m)"),
    ("xa0", GC.XA0, "exit sponge start x (m)"),
    ("abs_sigma", GC.ABS_SIGMA, "exit sponge sigma (1/s)"),
    ("abs_pow", GC.ABS_POW, "exit sponge power"),
    ("set_P", 0.0, "set period P (s), 0 none"),
    ("set_up", 0.0, "set rise (s)"),
    ("set_flat", 0.0, "set plateau (s)"),
    ("set_down", 0.0, "set fall (s)"),
    ("set_cg", 0.0, "set envelope retarded time speed (0 none)"),
    ("duabs_on", 0.0, "stage C: add the Sommerfeld term du_abs to the inlet x target"),
    # volume correction (off by default)
    ("volcorr_on", 0.0, "stage A: target divergence in vol_x0..vol_x1"),
    ("vol_x0", GC.VOL_X[0], "stage A window start x (m)"),
    ("vol_x1", GC.VOL_X[1], "stage A window end x (m)"),
    ("hold_on", 0.0, "stage B: band-core level hold"),
    ("hold_x0", GC.HOLD_X[0], "stage B start x (m)"),
    ("hold_x1", GC.HOLD_X[1], "stage B end x (m)"),
    # surface (R5)
    ("surf_layer_m", 2.5, "surface particles: drop below this depth (m)"),
    ("mirror_m", 1.0, "mirror width at the symmetry plane (m)"),
    ("surf_vox_scale", 1.0, "Particle Fluid Surface Voxel Scale"),
    ("crop_x0", 0.0, "surface crop x start (m)"),
    ("crop_x1", B0["Lx"], "surface crop x end (m)"),
    ("crop_z1", B0["W"], "surface crop lateral end (m)"),
    ("surf_ycut", -15.0, "drop surface below this height (m)"),
    ("surf_keep_vox", 1.0, "drop triangles farther than this many cells from the FLIP surface field"),
    ("surf_bed_vox", 0.5, "drop triangles closer than this many cells to the bed"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("sol_npz", "solitary npz (unused)", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("sf_tab", "Fenton table (unused in FLIP52)", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("vol_dir", "stage A/B/C file folder (g52_run.py writes; empty = 0)", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("dir_npz", "N-layer directional table npz (g52_table.py; empty = no table)", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("ckpt", "checkpoint folder", 1, default_value=(GC.B52B + "/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "write checkpoints", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "checkpoint spacing (frames)", 1, default_value=(48,)))
ctrl.setParmTemplateGroup(ptg)
for nm, dv, lb in PARMS:          # defaults are rounded to 6 digits; set the exact values
    ctrl.parm(nm).set(dv)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

# ---------------------------------------------------------------- tables (solitary unused, Fenton unused, stage files, N-layer directional)
sol = setup.createNode("python", "solution_table")
sptg = sol.parmTemplateGroup()
sptg.append(hou.StringParmTemplate("npz", "npz", 1, default_value=("",)))
sptg.append(hou.FloatParmTemplate("wave_on", "wave_on", 1, default_value=(0.0,)))
sptg.append(hou.FloatParmTemplate("h0", "h0", 1, default_value=(GC.H0,)))
sol.setParmTemplateGroup(sptg)
sol.parm("npz").set('`chs("%ssol_npz")`' % CT)
sol.parm("wave_on").setExpression('ch("%swave_on")' % CT)
sol.parm("h0").setExpression('ch("%sh0")' % CT)
sol.parm("python").set(L.PYSOP)
solout = setup.createNode("null", "OUT_SOL")
solout.setInput(0, sol)

sftab = setup.createNode("attribwrangle", "sf_table")
sftab.parm("class").set(0)
sftab.parm("vex_precision").set("64")
sftab.parm("snippet").set(L.snippet("/obj/G52_SETUP/sf_table"))
sftabout = setup.createNode("null", "OUT_SF")
sftabout.setInput(0, sftab)

vdp = setup.createNode("python", "voldiv_table")
vptg = vdp.parmTemplateGroup()
vptg.append(hou.FloatParmTemplate("fr", "fr", 1, default_value=(1.0,)))
vptg.append(hou.StringParmTemplate("vdir", "vdir", 1, default_value=("",)))
vdp.setParmTemplateGroup(vptg)
vdp.parm("fr").setExpression("$FF")
vdp.parm("vdir").set('`chs("%svol_dir")`' % CT)
vdp.parm("python").set(L.PYSOP_VOLDIV)
vdout = setup.createNode("null", "OUT_VOLDIV")
vdout.setInput(0, vdp)

dtab = setup.createNode("python", "dir_table")
dptg = dtab.parmTemplateGroup()
dptg.append(hou.StringParmTemplate("npz", "npz", 1, default_value=("",)))
dtab.setParmTemplateGroup(dptg)
dtab.parm("npz").set('`chs("%sdir_npz")`' % CT)
dtab.parm("python").set(L.PYSOP_DIRTAB52)
dtabout = setup.createNode("null", "OUT_DIRTAB")
dtabout.setInput(0, dtab)

# ---------------------------------------------------------------- bed (display / static object; collision through the SDF below)
PADE = 'ch("%sfloor_pad")*%s' % (CT, VOXE)
SPADE = 'ch("%sside_pad")*%s' % (CT, VOXE)
BOXC = dict(sx='ch("%sLx")' % CT, sy='ch("%sHz") + %s' % (CT, PADE), sz='ch("%sW") + %s' % (CT, SPADE),
            tx='ch("%sx0") + 0.5*ch("%sLx") + ch("%sox")' % (CT, CT, CT),
            ty='ch("%szb") - %s + 0.5*(ch("%sHz") + %s) + ch("%soy")' % (CT, PADE, CT, PADE, CT),
            tz='0.5*(ch("%sW") - %s) + ch("%soz")' % (CT, SPADE, CT))
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)
bgrid.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bgrid.parm("sizey").setExpression('ch("%sW") + 12' % CT)
bgrid.parm("rows").setExpression('int(2*(ch("%sLx") + 20)) + 1' % CT)
bgrid.parm("cols").setExpression('int(ch("%sW") + 12) + 1' % CT)
bgrid.parm("tx").setExpression(BOXC["tx"])
bgrid.parm("ty").setExpression('ch("%soy")' % CT)
bgrid.parm("tz").setExpression(BOXC["tz"])
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(L.snippet("/obj/G52_SETUP/bed_height"))
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, bw)

bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression(VOXE)
bsdf.parm("sizex").setExpression('ch("%sLx") + 12*%s' % (CT, VOXE))
bsdf.parm("sizey").setExpression('%s + 12*%s' % (BOXC["sy"], VOXE))
bsdf.parm("sizez").setExpression('ch("%sW") + 12*%s' % (CT, VOXE))
bsdf.parm("tx").setExpression(BOXC["tx"])
bsdf.parm("ty").setExpression(BOXC["ty"])
bsdf.parm("tz").setExpression(BOXC["tz"])
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.parm("snippet").set(L.snippet("/obj/G52_SETUP/bed_sdf_value"))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- initial particles (still water between the bed and the still level)
cols = setup.createNode("attribwrangle", "particle_columns")
cols.parm("class").set(0)
cols.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float W = ch(CT+"W");
int nx = int(floor(Lx/dp + 1e-6)); int nz = int(floor(W/dp + 1e-6));
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++) {
        int p = addpoint(0, set(x0 + (ix + 0.5)*dp + chf(CT+"ox"), 0.0, (iz + 0.5)*dp + chf(CT+"oz")));
        setpointattrib(0, "col", p, iz*nx + ix);
    }
""")
pts0 = setup.createNode("attribwrangle", "init_particles")
pts0.setInput(0, cols)
pts0.setInput(1, solout)
pts0.parm("class").set(2)
pts0.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float zb = ch(CT+"zb");
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
int c = i@col;
vector pc = @P - o;
float e = sol_eta(pc.x);
float ylo = bedy(pc.x, pc.z) + chf(CT+"bed_gap")*dp;
for (int k = 0; k < 100000; k++) {
    float y = zb + (k + 0.5)*dp;
    if (y >= e) break;
    if (y < ylo) continue;
    vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
    vector q = set(pc.x, y, pc.z) + jit;
    int p = addpoint(0, q + o);
    setpointattrib(0, "v", p, sol_vel(q.x, q.y));
}
removepoint(0, @ptnum);
""")
pclean = setup.createNode("attribdelete", "drop_col")
pclean.setInput(0, pts0)
pclean.parm("ptdel").set("col")
ptsout = setup.createNode("null", "OUT_PARTICLES")
ptsout.setInput(0, pclean)

wmesh0 = setup.createNode("attribwrangle", "water_mesh")
wmesh0.parm("class").set(0)
wmesh0.setInput(1, solout)
wmesh0.parm("snippet").set(L.VEX_HEAD + r"""
float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float W = ch(CT+"W"); float zb = ch(CT+"zb");
float vox = ch(CT+"dp")*ch(CT+"gridscale");
float ox = ch(CT+"ox"); float oy = ch(CT+"oy"); float oz = ch(CT+"oz");
float xa = x0 - 3.0*vox; float xb = x0 + Lx + 3.0*vox; float za = -3.0*vox; float zc = W + 3.0*vox;
float yb = zb - (6.0 + ch(CT+"floor_pad"))*vox;
float hx = 0.5*vox;
int n = int(ceil((xb - xa)/hx - 1e-6)) + 1;
int tA[]; int tC[]; int bA[]; int bC[];
resize(tA, n); resize(tC, n); resize(bA, n); resize(bC, n);
for (int i = 0; i < n; i++) {
    float x = min(xa + i*hx, xb);
    float e = sol_eta(x);
    tA[i] = addpoint(0, set(x + ox, e + oy, za + oz)); tC[i] = addpoint(0, set(x + ox, e + oy, zc + oz));
    bA[i] = addpoint(0, set(x + ox, yb + oy, za + oz)); bC[i] = addpoint(0, set(x + ox, yb + oy, zc + oz));
}
for (int i = 0; i < n - 1; i++) {
    addprim(0, "poly", tA[i], tC[i], tC[i + 1], tA[i + 1]);
    addprim(0, "poly", bA[i], bA[i + 1], bC[i + 1], bC[i]);
    addprim(0, "poly", bA[i], tA[i], tA[i + 1], bA[i + 1]);
    addprim(0, "poly", bC[i + 1], tC[i + 1], tC[i], bC[i]);
}
addprim(0, "poly", bC[0], tC[0], tA[0], bA[0]);
addprim(0, "poly", bA[n - 1], tA[n - 1], tC[n - 1], bC[n - 1]);
""")
wvdb = setup.createNode("vdbfrompolygons", "surface_vdb")
wvdb.setInput(0, wmesh0)
wvdb.parm("voxelsize").setExpression(VOXE)
wvdb.parm("builddistance").set(1)
wvdb.parm("distancename").set("surface")
wvdb.parm("exteriorbandvoxels").set(6)
wvdb.parm("interiorbandvoxels").set(6)
wvdb.parm("fillinterior").set(1)
vsvdb = setup.createNode("null", "OUT_SURFACE_VDB")
vsvdb.setInput(0, wvdb)

vv = setup.createNode("volume", "vol_vel")
vv.parm("name").set("vel")
vv.parm("rank").set("vector")
vv.parm("uniformsamples").set("size")
vv.parm("divsize").setExpression(VOXE)
vv.parm("sizex").setExpression(BOXC["sx"]); vv.parm("sizey").setExpression(BOXC["sy"]); vv.parm("sizez").setExpression(BOXC["sz"])
vv.parm("tx").setExpression(BOXC["tx"]); vv.parm("ty").setExpression(BOXC["ty"]); vv.parm("tz").setExpression(BOXC["tz"])
vvw = setup.createNode("volumewrangle", "vel_value")
vvw.setInput(0, vv)
vvw.setInput(1, solout)
vvw.parm("snippet").set(L.snippet("/obj/G52_SETUP/vel_value"))
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)

# ---------------------------------------------------------------- probe points (json -> points with float attributes) and probe wrangles
PTS_PY = r'''
import json, hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
rows = json.loads(node.evalParm("pts_json") or "[]")
keys = sorted(set(k for r in rows for k in r if k not in ("v0",)))
for k in keys:
    geo.addAttrib(hou.attribType.Point, k, 0.0)
geo.addAttrib(hou.attribType.Point, "v0", (0.0, 0.0, 0.0))
for r in rows:
    p = geo.createPoint()
    p.setPosition((0.0, 0.0, 0.0))
    for k in keys:
        p.setAttribValue(k, float(r.get(k, 0.0)))
    p.setAttribValue("v0", tuple(float(v) for v in r.get("v0", (0.0, 0.0, 0.0))))
'''


def probe_nodes(name, body_key):
    pn = setup.createNode("python", name + "_pts")
    t_ = pn.parmTemplateGroup()
    t_.append(hou.StringParmTemplate("pts_json", "pts_json", 1, default_value=("[]",)))
    pn.setParmTemplateGroup(t_)
    pn.parm("python").set(PTS_PY)
    w_ = setup.createNode("attribwrangle", name)
    w_.setInput(0, pn)
    w_.parm("class").set(2)
    w_.parm("vex_precision").set("64")
    w_.parm("snippet").set(L.snippet(body_key))
    return pn, w_


rlp_pts, rlp = probe_nodes("relax_probe", "/obj/G52_SETUP/relax_probe")
dpr_pts, dpr = probe_nodes("dir_probe", "/obj/G52_SETUP/dir_probe")
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G52_SIM")
dop.parm("cachemaxsize").set(3000)
dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
dop.parm("explicitcachename").set('`chs("%sckpt")`/v.$SF4.sim' % CT)
dop.parm("explicitcachecheckpointspacing").setExpression('ch("%sckpt_every")' % CT)
dop.parm("explicitcachensteps").set(0)
for c in dop.children():
    c.destroy()
fo = dop.createNode("flipobject", "water")
fo.parm("objname").set("water")
fo.parm("particlesep").setExpression('ch("%sdp")' % CT)
fo.parm("gridscale").setExpression('ch("%sgridscale")' % CT)
fo.parm("closedends").set(1)
for s in ("closexpos", "closexneg", "closeyneg", "closezpos", "closezneg"):
    fo.parm(s).set(1)
fo.parm("closeypos").set(0)
fo.parm("surfacetype").set("4")
fo.parm("soppath").set("/obj/G52_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G52_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G52_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)
fo.parm("adddivergence").setExpression('ch("%svolcorr_on") > 0.5 || ch("%shold_on") > 0.5' % (CT, CT))

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/G52_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/G52_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet("/obj/G52_SIM/relax_zones"))
relax.parm("exportlist").set("vel")
relax.parm("vex_precision").set("64")
en_r = dop.createNode("enablesolver", "enable_zones")
en_r.setInput(0, relax)
en_r.parm("enable").setExpression('ch("%srelax_on") > 0.5 || ch("%sabs_on") > 0.5 || ch("%ssd_on") > 0.5' % (CT, CT, CT))

vcd = dop.createNode("gasfieldwrangle", "vc_div")
vcd.parm("snippet").set(L.snippet("/obj/G52_SIM/vc_div"))
vcd.parm("exportlist").set("divergence")
vcd.parm("vex_precision").set("64")
en_vc = dop.createNode("enablesolver", "enable_volcorr")
en_vc.setInput(0, vcd)
en_vc.parm("enable").setExpression('ch("%svolcorr_on") > 0.5 || ch("%shold_on") > 0.5' % (CT, CT))
msv = dop.createNode("enablesolver", "volume_velocity")
msv.setInput(0, en_r)
msv.setInput(1, en_vc)
msv.parm("enable").set(1)

ssc = dop.createNode("geometrywrangle", "substep_count")
ssc.parm("bindclass").set("detail")
ssc.parm("snippet").set(L.BODIES["/obj/G52_SIM/substep_count"])
ssc.parm("exportlist").set("ss_acc ss_n ss_dt")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(1, ssc)
fs.setInput(2, msv)
fs.parm("veltransfer").set("flip")
fs.parm("usemgpreconditioner").set(0)
fs.parm("usepreconditioner").set(1)
fs.parm("minimumsubsteps").setExpression('ch("%sminsub")' % CT)
fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
fs.parm("cflcond").setExpression('ch("%scfl")' % CT)
fs.parm("partcflcond").setExpression('ch("%spcfl")' % CT)
fs.parm("dynamicresize").set(0)
fs.parm("usewaterline").set(0)
fs.parm("useboundarylayer").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").set(1000.0)
fs.parm("dosurfacetension").set(0)
fs.parm("limit_sizex").setExpression(BOXC["sx"])
fs.parm("limit_sizey").setExpression(BOXC["sy"])
fs.parm("limit_sizez").setExpression(BOXC["sz"])
fs.parm("limit_tx").setExpression(BOXC["tx"])
fs.parm("limit_ty").setExpression(BOXC["ty"])
fs.parm("limit_tz").setExpression(BOXC["tz"])

mg = dop.createNode("merge", "merge")
mg.setInput(0, so)
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- read
rd = obj.createNode("geo", "G52_READ")
for c in rd.children():
    c.destroy()
for nm in ("surface", "vel", "collision"):
    fi = rd.createNode("dopimportfield::2.0", nm + "_field")
    fi.parm("doppath").set("/obj/G52_SIM")
    fi.parm("fields").set(1)
    fi.parm("objname1").set("water")
    fi.parm("fieldname1").set(nm)
rd.layoutChildren()

# ---------------------------------------------------------------- surface (R5, the g48/g49/g50 path)
sf = obj.createNode("geo", "G52_SURF")
for c in sf.children():
    c.destroy()
di = sf.createNode("dopimport", "particles")
di.parm("doppath").set("/obj/G52_SIM")
di.parm("objpattern").set("water")
sfield = sf.createNode("object_merge", "surface_field")
sfield.parm("objpath1").set("/obj/G52_READ/surface_field")
layer = sf.createNode("attribwrangle", "layer_and_mirror")
layer.setInput(0, di)
layer.setInput(1, sfield)
layer.parm("class").set(2)
layer.parm("snippet").set(r"""
#define CT "%s"
float lm = ch(CT+"surf_layer_m");
if (lm > 0.0) {
    float vox = ch(CT+"dp")*ch(CT+"gridscale");
    float s = volumesample(1, "surface", @P);
    if (s < -0.5*vox) {
        int keep = 0;
        for (float h = vox; h <= lm + 1e-6; h += vox) {
            if (volumesample(1, "surface", @P + set(0, h, 0)) > 0.0) { keep = 1; break; }
        }
        if (!keep) { removepoint(0, @ptnum); return; }
    }
}
float oz = ch(CT+"oz");
if (@P.z - oz < ch(CT+"mirror_m")) {
    int p = addpoint(0, @ptnum);
    setpointattrib(0, "P", p, set(@P.x, @P.y, 2.0*oz - @P.z));
    setpointattrib(0, "v", p, set(v@v.x, v@v.y, -v@v.z));
}
""" % CT)
pfs = sf.createNode("particlefluidsurface", "fluid_surface")
pfs.setInput(0, layer)
pfs.parm("particlesep").setExpression('ch("%sdp")' % CT)
pfs.parm("voxelsize").setExpression('ch("%ssurf_vox_scale")' % CT)
pfs.parm("adaptivity").set(0.005)
pfs.parm("conversion").set("poly")
pfs.parm("dotransferattribs").set(1)
pfs.parm("transferattribs").set("v")
clip = sf.createNode("clip::2.0", "cut_symmetry")
clip.setInput(0, pfs)
clip.parm("clipop").set("above")
clip.parm("dirx").set(0.0); clip.parm("diry").set(0.0); clip.parm("dirz").set(1.0)
clip.parm("originz").setExpression('ch("%soz")' % CT)
tri = sf.createNode("divide", "triangles")
tri.setInput(0, clip)
tri.parm("convex").set(1)
tri.parm("numsides").set(3)
crop = sf.createNode("attribwrangle", "crop")
crop.setInput(0, tri)
crop.setInput(1, sfield)
crop.parm("class").set(1)
crop.parm("snippet").set(L.VEX_HEAD + r"""
int pts[] = primpoints(0, @primnum);
vector c = 0;
foreach (int p; pts) c += point(0, "P", p);
c /= max(1, len(pts));
float sdfc = volumesample(1, "surface", c);
float vox = ch(CT+"dp")*ch(CT+"gridscale");
vector cp = c - set(ch(CT+"ox"), ch(CT+"oy"), ch(CT+"oz"));
float gapb = cp.y - bedy(cp.x, cp.z);
if (len(pts) != 3 || cp.x < ch(CT+"crop_x0") || cp.x > ch(CT+"crop_x1") || cp.z > ch(CT+"crop_z1") || cp.y < ch(CT+"surf_ycut")
    || abs(sdfc) > ch(CT+"surf_keep_vox")*vox || gapb < ch(CT+"surf_bed_vox")*vox)
    removeprim(0, @primnum, 1);
""")
nrm = sf.createNode("normal", "point_normals")
nrm.setInput(0, crop)
nrm.parm("type").set(0)
idx = sf.createNode("attribwrangle", "tri_index")
idx.setInput(0, nrm)
idx.parm("class").set(1)
idx.parm("snippet").set(r"""
int pts[] = primpoints(0, @primnum);
i@a = pts[0]; i@b = pts[1]; i@c = pts[2];
""")
sout = sf.createNode("null", "OUT_SURF")
sout.setInput(0, idx)
sf.layoutChildren()

# ---------------------------------------------------------------- cook once
for n in (sol, sftab, vdp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
    try:
        n.cook(force=True)
    except Exception as e:
        print("COOK ERROR", n.path(), str(e)[:400])
    if n.errors():
        print("ERR", n.path(), n.errors())
print("gravity", [(p.name(), p.eval()) for p in gr.parms() if p.name().startswith("force")])
print("solver inputs", fs.inputLabels(), "volume velocity", fs.inputs()[2].path() if fs.inputs()[2] else None, "errors", [str(e)[:160] for e in fs.errors()])
for n_ in (relax, vcd, en_r, en_vc, msv, fo):
    if n_.errors():
        print("DOP ERR", n_.path(), [str(e)[:200] for e in n_.errors()])


# ======================================================================== checks
def ctrl_floats():
    return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}


def set_ctrl(d):
    for nm, v in d.items():
        ctrl.parm(nm).set(v)


def f32(v):
    return np.asarray(np.asarray(v, float).astype(np.float32), float)


def bed_check(tag):
    """OUT_BED heights and the bed SDF (collision) against numpy (g49_common / g48_common through g52_common), with the current CTRL."""
    P_ = ctrl_floats()
    spec = GC.bed_spec(parms=P_)
    o = np.array([P_["ox"], P_["oy"], P_["oz"]])
    out = dict(tag=tag, spec=spec, kind=GC.bed_kind(spec), W=float(P_["W"]), Lx=float(P_["Lx"]), zb=float(P_["zb"]), Hz=float(P_["Hz"]),
               dp=float(P_["dp"]), o=[float(v) for v in o])
    bw.cook(force=True)
    g_ = bedout.geometry()
    Pp = np.frombuffer(g_.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
    zb = GC.bed_z(Pp[:, 0], Pp[:, 2], **spec)
    d = Pp[:, 1] - zb
    out["bed_points"] = int(len(Pp)); out["bed_max_abs_dz_m"] = float(np.abs(d).max())
    out["bed_ok"] = bool(np.abs(d).max() < 0.01)
    out["bed_vex_numpy_lt_1mm"] = bool(np.abs(d).max() < 1e-3)
    out["bed_min_depth_m"] = float(-zb.max()); out["bed_max_depth_m"] = float(-zb.min())
    out["bed_flat_20m"] = bool(np.all(zb == -GC.H0))
    out["box_floor_m"] = float(P_["zb"]) - float(P_["floor_pad"]) * float(P_["dp"]) * float(P_["gridscale"])
    bsdfw.cook(force=True)
    gs = bsdfout.geometry()
    vols = [q for q in gs.prims() if q.type() in (hou.primType.Volume, hou.primType.VDB)]
    if vols:
        v = vols[0]
        r = v.resolution()
        a = np.frombuffer(v.allVoxelsAsString(), dtype=np.float32).reshape(r[2], r[1], r[0]).astype(np.float64)
        p0 = np.array([float(c) for c in v.indexToPos((0, 0, 0))]) - o
        p1 = np.array([float(c) for c in v.indexToPos((1, 1, 1))]) - o
        dd = p1 - p0
        xs = p0[0] + dd[0] * np.arange(r[0]); ys = p0[1] + dd[1] * np.arange(r[1]); zs = p0[2] + dd[2] * np.arange(r[2])
        ref = np.empty_like(a)
        for k0 in range(0, r[2], 16):
            Z, Y, X = np.meshgrid(zs[k0:k0 + 16], ys, xs, indexing="ij")
            ref[k0:k0 + 16] = GC.bed_sdf(X, Y, Z, **spec)
        near = np.abs(ref) < 3.0
        out["sdf_res"] = list(r); out["sdf_max_abs_diff_near_m"] = float(np.abs(a - ref)[near].max()) if near.any() else None
        out["sdf_vex_numpy_lt_1mm"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 1e-3)
        far = np.abs(ref) > 0.05
        out["sdf_sign_mismatch_frac"] = float(np.mean(np.sign(a[far]) != np.sign(ref[far])))
        out["sdf_ok"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 0.02 and out["sdf_sign_mismatch_frac"] == 0.0)
        out["sdf_covers_box_floor"] = bool(ys[0] <= out["box_floor_m"] + 1e-6)
    return out


def particle_check(rec, spec):
    P_ = ctrl_floats()
    o = np.array([P_["ox"], P_["oy"], P_["oz"]])
    for n in (sol, cols, pts0):
        n.cook(force=True)
    g = ptsout.geometry()
    if g is None:
        rec["particles_error"] = "no geometry"
        return rec
    Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - o
    gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **spec)
    rec["particles"] = int(len(Pp)); rec["n_below_bed"] = int((gap < 0).sum())
    rec["gap_min_m"] = float(gap.min()); rec["z_max_m"] = float(Pp[:, 1].max()); rec["x_max_m"] = float(Pp[:, 0].max())
    n_model, V = GC.count_particles(spec, float(P_["Lx"]), float(P_["W"]), float(P_["dp"]), zb=float(P_["zb"]), bed_gap=float(P_["bed_gap"]))
    rec["particles_model"] = int(n_model); rec["particles_ratio_houdini_over_model"] = float(len(Pp)) / max(n_model, 1)
    rec["particles_ok"] = bool(rec["n_below_bed"] == 0 and abs(rec["particles_ratio_houdini_over_model"] - 1.0) < 0.002
                               and rec["x_max_m"] <= GC.X_SHORE + 0.5)
    return rec


def set_box(dp, W, spec, zb=GC.ZB, Lx=GC.LX):
    b = GC.box52(dp, Lx=Lx, W=W, zb=zb)
    d = dict(dp=b["dp"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x1=b["Lx"], crop_z1=b["W"],
             h0=float(spec["h0"]))
    d.update(GC.bed_parms(spec))
    set_ctrl(d)
    return b


DIR_TOL = 1e-5                 # plan G1: VEX dir_probe vs the numpy mirror within 1e-5 of the scale over the 3 layers


def dir_check(npz):
    """OUT_DIRTAB detail and dir_probe (VEX dirwave, g = 1) against the numpy mirror g52_table.dirwave_np, ret_on 0 and 1."""
    tab = TB.load(npz)
    I = tab["info"]
    ctrl.parm("dir_npz").set(npz)
    dtab.cook(force=True)
    g_ = dtabout.geometry()
    dn = ("d_P", "d_nlayer", "d_n0", "d_n1", "d_n2", "d_n3", "d_om0", "d_om1", "d_om2", "d_om3", "d_x0", "d_x1", "d_y0", "d_y1", "d_tf",
          "d_nfield", "d_content")
    det = {nm: g_.attribValue(nm) for nm in dn}
    names = sorted(p.attribValue("name") for p in g_.prims())
    nl = int(I["n_layers"])
    harm_ok = all(float(det["d_n%d" % n]) == float(I["harmonics"][n]) for n in range(nl)) and all(float(det["d_n%d" % n]) == 0.0 for n in range(nl, 4))
    out = dict(npz=npz, detail=det, fields=names,
               detail_ok=bool(int(det["d_nfield"]) == len(I["fields"]) and int(round(det["d_nlayer"])) == nl and float(det["d_P"]) == float(I["P"])
                              and harm_ok and abs(det["d_x1"] - I["x1"]) < 1e-9 and abs(det["d_y1"] - I["y1"]) < 1e-9
                              and float(det["d_tf"]) == float(I["t_f"]) and sorted(I["fields"]) == names and det["d_content"] == I.get("content_sha256")))
    rows = []
    for x_ in (0.0, 3.3, 12.5, 20.0, 49.5, 50.5, 99.5, 150.0, 180.25, 200.0, 213.6, 214.0, 230.0):
        for z_ in (0.0, 0.4, 37.2, 69.5, 70.5, 95.5, 99.9, 100.0, 104.0):
            for yv_, t_ in ((-18.0, 0.0), (-9.5, 13.1), (-2.0, 30.75), (0.5, 44.0), (4.0, 57.9), (1.5, 72.25), (-5.5, 99.6), (2.5, 104.8)):
                rows.append(dict(px=x_, py=yv_, pz=z_, pt=t_))
    dpr_pts.parm("pts_json").set(json.dumps(rows))
    X_ = f32([r["px"] for r in rows]); Yv = f32([r["py"] for r in rows]); Z_ = f32([r["pz"] for r in rows]); T_ = f32([r["pt"] for r in rows])
    sc_e = max(float(np.max(np.hypot(tab["er%d" % n], tab["ei%d" % n]))) for n in range(nl))
    sc_e = max(sc_e, float(I["a_sum"]))
    sc_u = max(float(np.max(np.hypot(tab["ur%d" % n], tab["ui%d" % n]))) for n in range(nl))
    for ret in (0.0, 1.0):
        ctrl.parm("ret_on").set(ret)
        dpr.cook(force=True)
        gq = dpr.geometry()
        ev = np.array(gq.pointFloatAttribValues("eta_v")); uv = np.array(gq.pointFloatAttribValues("u_v")); vv_ = np.array(gq.pointFloatAttribValues("v_v"))
        en, un, vn = TB.dirwave_np(tab, X_, Yv, Z_, T_, 1.0, tf=float(ctrl.parm("dir_tf").eval()), ret_on=ret)
        out["ret%d" % int(ret)] = dict(n=len(rows), eta_max_rel=float(np.abs(ev - en).max() / sc_e), u_max_rel=float(np.abs(uv - un).max() / sc_u),
                                       v_max_rel=float(np.abs(vv_ - vn).max() / sc_u), eta_range=[float(en.min()), float(en.max())])
    ctrl.parm("ret_on").set(0.0)
    out["scale"] = dict(eta=sc_e, u=sc_u)
    out["tolerance"] = DIR_TOL
    out["tolerance_note"] = "float32 point attributes and float32 table voxels; the numpy mirror gets the same float32-rounded inputs"
    out["ok"] = bool(out["detail_ok"] and all(max(out["ret%d" % r]["eta_max_rel"], out["ret%d" % r]["u_max_rel"], out["ret%d" % r]["v_max_rel"]) < DIR_TOL
                                              for r in (0, 1)))
    return out


def relax_check(tag, W_, spec, on, xs_, zls_, tab=None):
    """relax_apply and vc_divergence at relax_probe points against g52_table.relax_np, with a test stage file (du_abs etc.)."""
    vdt = GC.LOG_DIR + "/vdtest"
    os.makedirs(vdt, exist_ok=True)
    DV = (0.0013, -0.0007, 0.21)
    open(vdt + "/vd_00001.txt", "w").write("%r %r %r\n" % DV)
    set_box(0.5, W_, spec)
    set_ctrl(on)
    ctrl.parm("vol_dir").set(vdt)
    hou.setFrame(1)
    vdp.cook(force=True)
    vg_ = vdout.geometry()
    vread = [vg_.attribValue(nm) for nm in ("vol_div", "vol_div_band", "du_abs")]
    P_ = ctrl_floats()
    rows = []
    for x_ in xs_:
        for zl_ in zls_:
            if zl_ > float(P_["W"]):
                continue
            for y_ in (-12.0, -1.0):
                for t_, dts_ in ((0.0, 1.0 / 24.0), (13.3, 1.0 / 96.0), (40.0, 1.0 / 48.0), (44.5, 1.0 / 72.0), (71.0, 1.0 / 24.0)):
                    rows.append(dict(px=x_, py=y_, pz=zl_, pt=t_, dts=dts_, v0=(0.7, -0.3, 0.4)))
    rlp_pts.parm("pts_json").set(json.dumps(rows))
    rlp.cook(force=True)
    g_ = rlp.geometry()
    v1 = np.array(g_.pointFloatAttribValues("v1")).reshape(-1, 3); dv_ = np.array(g_.pointFloatAttribValues("div"))
    ref = np.array([TB.relax_np((float(f32(r["px"])), float(f32(r["py"])), float(f32(r["pz"]))), f32(r["v0"]), float(f32(r["pt"])),
                                float(f32(r["dts"])), P_, tab=tab, du_abs=DV[2]) for r in rows])
    dref = np.array([(DV[0] if (P_["volcorr_on"] > 0.5 and P_["vol_x0"] <= r["px"] <= P_["vol_x1"]) else 0.0)
                     + (DV[1] if (P_["hold_on"] > 0.5 and P_["hold_x0"] <= r["px"] <= P_["hold_x1"]) else 0.0) for r in rows])
    vert_same = bool(np.allclose(v1[:, 1], -0.3, atol=1e-6))
    inner = np.array([P_["xg_end"] + 1.0 <= r["px"] and (P_["sd_on"] < 0.5 or r["pz"] <= P_["sd0"] - 1e-9)
                      and (P_["abs_on"] < 0.5 or r["px"] <= P_["xa0"] - 1e-9) for r in rows])
    absorb = np.array([P_["sd_on"] > 0.5 and r["px"] >= P_["sd_sw"] and r["pz"] > P_["sd0"] + 5.0 for r in rows])
    sponge = np.array([P_["abs_on"] > 0.5 and r["px"] >= P_["xa0"] + 20.0 for r in rows])
    out = dict(tag=tag, n=len(rows), W=float(P_["W"]), voldiv_read=vread, voldiv_ok=bool(np.allclose(vread, DV, atol=1e-12)),
               v_max_abs_diff=float(np.abs(v1 - ref).max()), div_max_abs_diff=float(np.abs(dv_ - dref).max()),
               vertical_unchanged=vert_same, untouched_interior=bool(np.allclose(v1[inner], np.array([0.7, -0.3, 0.4]), atol=1e-6)) if inner.any() else None,
               side_absorber_damps=bool(np.all(np.abs(v1[absorb, 2]) < 0.4)) if absorb.any() else None,
               exit_sponge_damps=bool(np.all(np.abs(v1[sponge, 0]) < 0.7) and np.all(np.abs(v1[sponge, 2]) < 0.4)) if sponge.any() else None,
               n_interior=int(inner.sum()), n_absorb=int(absorb.sum()), n_sponge=int(sponge.sum()),
               target_scale_mps=float(np.abs(ref[:, [0, 2]]).max()))
    out["tolerance_note"] = "point attributes are float32 (both sides get the same float32 inputs): v within 2e-6 m/s (VEX 64-bit), div within 1e-9 1/s"
    out["ok"] = bool(out["voldiv_ok"] and out["v_max_abs_diff"] < 2e-6 * max(1.0, out["target_scale_mps"]) and out["div_max_abs_diff"] < 1e-9 and vert_same
                     and out["untouched_interior"] is not False and out["side_absorber_damps"] is not False and out["exit_sponge_damps"] is not False
                     and out["n_interior"] > 0 and out["n_absorb"] > 0 and (out["n_sponge"] > 0 or P_["abs_on"] < 0.5))
    return out


CHK = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=HIP, houdini=hou.applicationVersionString(), module_shas=GC.module_shas(),
           vex_head_info=L.HEAD_INFO, inputs=INPUTS)
DEFAULT_CTRL = ctrl_floats()
DEFAULT_STR = {nm: ctrl.parm(nm).evalAsString() for nm in ("sol_npz", "sf_tab", "vol_dir", "dir_npz")}


def restore_ctrl():
    set_ctrl(DEFAULT_CTRL)
    for nm, v in DEFAULT_STR.items():
        ctrl.parm(nm).set(v)


try:
    SP = dict(GC.SPEC_BED)
    # 1-2: bed and particles (the FLIP50 D19B checks)
    set_box(0.5, GC.W_STRIP, SP)
    CHK["D19B_strip"] = bed_check("D19B strip (W 6 m, dp 0.5 m)")
    particle_check(CHK["D19B_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, SP)
    CHK["D19B_3d"] = bed_check("D19B 3D (W 140 m, dp 0.5 m grid)")
    set_box(1.0, GC.W_MAIN, SP)
    CHK["D19B_3d_particles_dp1"] = particle_check(dict(W=float(ctrl.parm("W").eval())), GC.bed_spec(parms=ctrl_floats()))
    xq = np.arange(0.0, GC.LX, 0.37); yq = np.arange(0.0, GC.W_MAIN, 0.41)
    CHK["D19B_numpy"] = dict(equals_analytic_bit=bool(np.array_equal(GC.bed_z(xq[None, :], yq[:, None], **SP)[0],
                                                                     -(GC.H0 - np.maximum(xq - GC.X_TOE, 0.0) / GC.SLOPE_S))),
                             laterally_uniform=bool(np.all(GC.bed_z(xq[None, :], yq[:, None], **SP) == GC.bed_z(xq[None, :], 0.0 * yq[:, None], **SP))),
                             g48_plain_path=bool(not GC.is_new(SP)), kind=GC.bed_kind(SP), x_toe=float(SP["x_toe"]))
    restore_ctrl()
    # 3: the N-layer directional table (D19B WKB table of g52b_table.py)
    CHK["dir_probe"] = dir_check(INPUTS["dir_npz"])
    # 4: bands on the D layout (W 140): dir_on (N-layer), side band, ret_on, stage C test file; no exit sponge (the beach)
    restore_ctrl()
    ctrl.parm("dir_npz").set(INPUTS["dir_npz"])
    tabD = TB.load(INPUTS["dir_npz"])
    onD = dict(relax_on=1.0, sd_on=1.0, dir_on=1.0, ret_on=1.0, sf_on=0.0, abs_on=0.0, in_gain=1.03, sd_gain=0.97, duabs_on=1.0,
               volcorr_on=1.0, hold_on=1.0, ramp_s=GC.RAMP_S, dir_tf=GC.T_F)
    CHK["relax_probe_D"] = relax_check("D layout: inlet 0-100 m + side band 95-140 m (generating to 180.25 m, absorbing from 210.25 m), no exit "
                                       "sponge, dir_on 1 (N-layer), ret_on 1", GC.W_MAIN, SP, onD,
                                       (1.0, 5.0, 19.0, 60.0, 99.0, 100.5, 150.0, 180.0, 195.0, 209.0, 211.0, 260.0, 400.0),
                                       (0.5, 40.0, 94.0, 96.0, 110.0, 128.0, 135.0, 139.5), tab=tabD)
    restore_ctrl()
    for n in (sol, sftab, vdp, dtab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    rlp_pts.parm("pts_json").set("[]"); dpr_pts.parm("pts_json").set("[]")
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).evalAsString() == v for k, v in DEFAULT_STR.items()))
    CHK["saved_scene_still_water_bands_off"] = bool(all(ctrl.parm(k).eval() == 0.0 for k in ("relax_on", "abs_on", "sf_on", "dir_on", "sd_on", "ret_on",
                                                                                          "volcorr_on", "hold_on", "duabs_on", "wave_on")))
    CHK["dop_errors"] = {n_.path(): [str(e)[:200] for e in n_.errors()] for n_ in (relax, vcd, en_r, en_vc, msv, fo, fs) if n_.errors()}
except Exception as e:
    import traceback
    CHK["error"] = repr(e)[:400]
    CHK["traceback"] = traceback.format_exc()[-3000:]
    try:
        restore_ctrl()
    except Exception:
        pass
BEDK = ("D19B_strip", "D19B_3d")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") for k in BEDK)
                     and all((CHK.get(k) or {}).get("particles_ok") for k in ("D19B_strip", "D19B_3d_particles_dp1"))
                     and all((CHK.get("D19B_numpy") or {}).get(k) for k in ("equals_analytic_bit", "laterally_uniform", "g48_plain_path"))
                     and (CHK.get("dir_probe") or {}).get("ok") and (CHK.get("relax_probe_D") or {}).get("ok")
                     and CHK.get("restored_ctrl_equal_default") and CHK.get("saved_scene_still_water_bands_off")
                     and not CHK.get("error"))          # dop_errors are recorded only (as FLIP49/50/52: some DOP nodes report before the first sim step)
print("BUILD_CHECK", json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list))})
                                 for k, v in CHK.items() if k not in ("module_shas", "traceback")}, ensure_ascii=False, default=str)[:6000])
os.makedirs(GC.LOG_DIR, exist_ok=True)
json.dump(CHK, open(GC.BUILD_CHECK, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
CHK["hip_sha256"] = GC.sha256_file(HIP)            # g52_chain.py starts only when the scene still has this sha256
json.dump(CHK, open(GC.BUILD_CHECK, "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
print("saved", HIP, CHK["hip_sha256"][:16])
