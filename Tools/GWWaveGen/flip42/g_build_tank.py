# -*- coding: utf-8 -*-
"""FLIP42：集まる波の群の断面の水槽の場面を作り、Houdini/FLIP42/g_tank.hiplc に保存する（hython 22.0.459）。
FLIP41 の v_build_tank.py（Tools/GWWaveGen/flip41、変えていない）を写して直した。同じにした所：
  粒子の置き方（水面の帯だけ、帯なしでは水の全体）、閉じたメッシュから作る初めの水面の VDB、海底の SDF を Static Object の体積で、
  FLIP Solver 2.0・APIC・格子 = 粒子 × 2・圧力の前処理 IC、造波の帯は水平の流速だけを寄せる、吸う帯はスポンジ。
変えた所（計画 plan_ja.md §4・§7.3）：造波の目標を 32 成分の重ね合わせに（VEX は g_tanklib.py）、帯の重みを小刻みの長さに合わせた、
  最大小刻みと CFL の値を CTRL に出した（cflcond・partcflcond。名前は x_introspect_fs.py で確かめた）、
  各コマの小刻みの数を記録する Geometry Wrangle を Particle Velocity の入口に足した、ピストン板と風の圧力のノードは作らない（風なしの基準）。
"""
import hou, os, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import importlib, g_tanklib as L
importlib.reload(L)

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP42/g_tank.hiplc"
CT = L.CT

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    ("dp", 0.5, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("Lz", 4.0, "板の厚さ z (m)（格子 4 個）"),
    ("Lx", 1202.0, "水槽の長さ (m)"),
    ("h0", 42.0, "水深 (m)"),
    ("ytop", 18.0, "箱の天井 y (m)"),
    ("band_vox", 4.0, "narrow band の厚さ（格子の数）。帯なしでは 1000（粒子を水の全体に置く）"),
    ("maxsub", 8.0, "FLIP の最大小刻み"),
    ("minsub", 1.0, "FLIP の最小小刻み"),
    ("cfl", 1.0, "CFL Condition（cflcond）"),
    ("pcfl", 0.75, "Particle Advection CFL（partcflcond）"),
    ("ncomp", 32.0, "成分の数"),
    ("fc", 0.105179, "中心の周波数 fc (Hz)"),
    ("dff", 0.73, "帯域の幅 Δf/fc"),
    ("S", 0.352, "全体の険しさ S = Σ a k"),
    ("x_p", 135.463, "造波板の位置（帯の出口）x_p (m)"),
    ("x_b", 592.2, "線形の焦点（造波板から）x_b (m)"),
    ("t_b", 171.515, "線形の焦点の時刻 t_b (s)"),
    ("ramp_s", 9.5075, "始めのなだらかさ (s)"),
    ("xg_end", 135.463, "造波の帯の終わり x (m)"),
    ("relax_g", 1.0, "造波の帯の強さ（0 で使わない）"),
    ("dt0", 1.0 / 24.0, "帯の重みの基準の刻み dt0 (s)"),
    ("wall_taper_m", 33.866, "造波の目標を壁の近くで 0 へ落とす長さ (m)"),
    ("xa0", 1066.32, "波を吸う帯の始まり x (m)"),
    ("abs_sigma", 0.8, "スポンジの σmax (1/s)"),
    ("abs_pow", 2.0, "スポンジの強さの増え方 χ^p の p"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(240,)))
ctrl.setParmTemplateGroup(ptg)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

# ---------------------------------------------------------------- 海底（表示と静的物体の形。衝突は下の SDF で）
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)
bgrid.parm("sizex").setExpression('ch("%sLx") + 40' % CT)
bgrid.parm("sizey").setExpression('ch("%sLz") + 8' % CT)
bgrid.parm("rows").setExpression('int((ch("%sLx") + 40)/2) + 1' % CT)
bgrid.parm("cols").set(3)
bgrid.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(L.snippet("/obj/G_SETUP/bed_height"))
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, bw)

bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression(VOXE)
bsdf.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bsdf.parm("sizey").setExpression('ch("%sytop") + ch("%sh0") + 12' % (CT, CT))
bsdf.parm("sizez").setExpression('ch("%sLz") + 8' % CT)
bsdf.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
bsdf.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 12)' % (CT, CT))
bsdf.parm("tz").set(0)
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.parm("snippet").set(L.snippet("/obj/G_SETUP/bed_sdf_value"))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- 初めの粒子（水面の帯だけ。帯なしでは水の全体。静かな水、流速 0）
pts0 = setup.createNode("attribwrangle", "init_particles")
pts0.parm("class").set(0)
pts0.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float Lx = ch(CT+"Lx"); float Lz = ch(CT+"Lz");
float vox = dp*ch(CT+"gridscale");
float bandm = (ch(CT+"band_vox") + 1.0)*vox;
int nx = int(floor(Lx/dp)); int nz = int(floor(Lz/dp));
int c = 0;
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++) {
        float x = (ix + 0.5)*dp; float z = -0.5*Lz + (iz + 0.5)*dp;
        float yb = bedy(x);
        float ytop = -0.5*dp;
        float ybot = max(yb + 0.5*dp, -bandm);
        for (float y = ytop; y >= ybot; y -= dp) {
            vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
            int p = addpoint(0, set(x, y, z) + jit);
            setpointattrib(0, "v", p, {0, 0, 0});
        }
        c++;
    }
""")
ptsout = setup.createNode("null", "OUT_PARTICLES")
ptsout.setInput(0, pts0)

# 水の塊の閉じたメッシュ（上の面 y = 0）→ VDB の SDF（FLIP41 と同じ）
wmesh0 = setup.createNode("attribwrangle", "water_mesh")
wmesh0.parm("class").set(0)
wmesh0.parm("snippet").set(r"""
#define CT "%s"
float Lx = ch(CT+"Lx"); float Lz = ch(CT+"Lz"); float h0 = ch(CT+"h0");
float vox = ch(CT+"dp")*ch(CT+"gridscale");
float x0 = -3.0*vox;
float x1 = Lx + 3.0*vox; float z0 = -0.5*Lz - 3.0*vox; float z1 = 0.5*Lz + 3.0*vox;
float yb = -h0 - 6.0*vox; float yt = 0.0;
int b00 = addpoint(0, set(x0, yb, z0)); int b10 = addpoint(0, set(x1, yb, z0));
int b11 = addpoint(0, set(x1, yb, z1)); int b01 = addpoint(0, set(x0, yb, z1));
int t00 = addpoint(0, set(x0, yt, z0)); int t10 = addpoint(0, set(x1, yt, z0));
int t11 = addpoint(0, set(x1, yt, z1)); int t01 = addpoint(0, set(x0, yt, z1));
addprim(0, "poly", t00, t01, t11, t10);
addprim(0, "poly", b00, b10, b11, b01);
addprim(0, "poly", b00, t00, t10, b10);
addprim(0, "poly", b10, t10, t11, b11);
addprim(0, "poly", b11, t11, t01, b01);
addprim(0, "poly", b01, t01, t00, b00);
""" % CT)
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
vv.parm("sizex").setExpression('ch("%sLx")' % CT)
vv.parm("sizey").setExpression('ch("%sytop") + ch("%sh0") + 2' % (CT, CT))
vv.parm("sizez").setExpression('ch("%sLz")' % CT)
vv.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
vv.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 2)' % (CT, CT))
vv.parm("tz").set(0)
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vv)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G_SIM")
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
fo.parm("surfacetype").set("4")  # Narrow Band（帯なしの計算では g_run.py が donarrowband を 0 にする）
fo.parm("soppath").set("/obj/G_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/G_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/G_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet("/obj/G_SIM/relax_zones"))
relax.parm("exportlist").set("vel")
relax.parm("vex_precision").set("64")

ssc = dop.createNode("geometrywrangle", "substep_count")
ssc.parm("bindclass").set("detail")
ssc.parm("snippet").set(L.BODIES["/obj/G_SIM/substep_count"])
ssc.parm("exportlist").set("ss_acc ss_n ss_dt")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(1, ssc)
fs.setInput(2, relax)
fs.parm("veltransfer").set("apic")
fs.parm("usemgpreconditioner").set(0)
fs.parm("usepreconditioner").set(1)
fs.parm("minimumsubsteps").setExpression('ch("%sminsub")' % CT)
fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
fs.parm("cflcond").setExpression('ch("%scfl")' % CT)
fs.parm("partcflcond").setExpression('ch("%spcfl")' % CT)
fs.parm("dynamicresize").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").setExpression('ch("%sband_vox")' % CT)
fs.parm("dosurfacetension").set(0)
fs.parm("limit_sizex").setExpression('ch("%sLx")' % CT)
fs.parm("limit_sizey").setExpression('ch("%sytop") + ch("%sh0") + 2' % (CT, CT))
fs.parm("limit_sizez").setExpression('ch("%sLz")' % CT)
fs.parm("limit_tx").setExpression('0.5*ch("%sLx")' % CT)
fs.parm("limit_ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 2)' % (CT, CT))
fs.parm("limit_tz").set(0)

mg = dop.createNode("merge", "merge")
mg.setInput(0, so)
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り（水面の場）
rd = obj.createNode("geo", "G_READ")
for c in rd.children():
    c.destroy()
fi = rd.createNode("dopimportfield::2.0", "surface_field")
fi.parm("doppath").set("/obj/G_SIM")
fi.parm("fields").set(1)
fi.parm("objname1").set("water")
fi.parm("fieldname1").set("surface")
rd.layoutChildren()

for n in (bw, bedout, bsdfw, pts0, wmesh0, wvdb):
    try:
        n.cook(force=True)
    except Exception as e:
        print("COOK ERROR", n.path(), str(e)[:400])
    if n.errors():
        print("ERR", n.path(), n.errors())
print("gravity", [(p.name(), p.eval()) for p in gr.parms() if p.name().startswith("force")])
g = bedout.geometry()
print("bed bbox", g.boundingBox() if g else None)
g = ptsout.geometry()
print("particles", g.intrinsicValue("pointcount") if g else None)
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
print("saved", HIP)
