# -*- coding: utf-8 -*-
"""FLIP39 E：境界の造波で波の群を起こす水槽の場面を作り、Houdini/FLIP39/e_tank.hiplc に保存する（hython 22.0.459）。
FLIP37 P2 の水槽（Tools/GWWaveGen/flip37/build_p2_tank.py）を複製し、波の起こし方だけを替えた：
- 初めの波（hot start の 2 次 Stokes の周期波）をやめ、造波の帯（x < xg_end）で線形の成分の和（波の群）を起こす。
  成分の表は計算ごとに e_run.py が VEX の配列として書き込む（e_tanklib.py）。ここでは成分 0（静かな水）で作る。
- 途中から始める版（hot_on=1）：群の時刻 t_off の線形の場を x < xhot にだけ置く（遠くの造波板がすでに出した波）。
- 造波の帯の目標は、閉じた壁の近く（wall_taper_m）で 0 へなだらかに落とす（P0 §4.4・P1 §9 の 6 の壁ぎわの揺れへの手当て）。
水の塊の作り方（閉じたメッシュから VDB）、海底を merge の左、圧力の前処理 IC、帯の中は水平だけ寄せる、吸う帯（なだらかなスポンジ）は P0〜P2 のまま。
圧力が解けない失敗（P0 §3.4）への直しはしていない。新しい並びは静かな水の短い確かめと、見張り（水面の平均が 1 m 下がったら止める）で使う。
座標：x＝波の進む向き、y＝上、z＝峰に沿う向き（z = −Lz/2 の壁を向きの集中の対称の面に使う）。静かな水面 y = 0。1 単位 = 1 m。
"""
import hou, os, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
import importlib, e_tanklib as L
importlib.reload(L)

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP39/e_tank.hiplc"
CT = L.CT
EMPTY = L.comp_table({"A_f": 0.0}, {"h0": 60.0, "hr": 26.0, "slope_n": 4.0, "xs0": 420.0}, 240.0)

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "E_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    ("dp", 1.0, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("Lz", 240.0, "水槽の幅 z (m)"),
    ("Lx", 806.0, "水槽の長さ (m)"),
    ("h0", 60.0, "沖の水深 (m)"),
    ("hr", 26.0, "岩棚の水深 (m)（中央）"),
    ("slope_n", 4.0, "斜面 1:n の n"),
    ("xs0", 420.0, "斜面の始まり x (m)（平らな海は Lx より大きく）"),
    ("lens_A", 0.0, "レンズ：両側の斜面の始まりを岸へ下げる量 (m)"),
    ("lens_zl", 60.0, "レンズの広がり z (m)"),
    ("lens_dh", 0.0, "レンズ：両側の岩棚を深くする量 (m)"),
    ("lens_z0", 0.0, "レンズの中心 z (m)"),
    ("obl_deg", 0.0, "等深線の斜め (°)"),
    ("lg1_d", 0.0, "盛り上がり 1：頂の水深 (m)（0 で使わない）"),
    ("lg1_x", 560.0, "盛り上がり 1：中心 x"),
    ("lg1_z", -50.0, "盛り上がり 1：中心 z"),
    ("lg1_sx", 30.0, "盛り上がり 1：広がり x"),
    ("lg1_sz", 15.0, "盛り上がり 1：広がり z"),
    ("lg2_d", 0.0, "盛り上がり 2：頂の水深 (m)（0 で使わない）"),
    ("lg2_x", 560.0, "盛り上がり 2：中心 x"),
    ("lg2_z", -95.0, "盛り上がり 2：中心 z"),
    ("lg2_sx", 25.0, "盛り上がり 2：広がり x"),
    ("lg2_sz", 10.0, "盛り上がり 2：広がり z"),
    ("xg_end", 140.0, "造波の帯の終わり x (m)"),
    ("relax_g", 1.0, "造波の帯の強さ（0 で使わない）"),
    ("wall_taper_m", 40.0, "造波の目標を壁の近くで 0 へ落とす長さ (m)"),
    ("ramp_s", 10.0, "造波の始めのなだらかさ (s)（0 で使わない）"),
    ("ramp_t0", 0.0, "なだらかさの時刻のずれ (s)（途中から始める版は大きくして効かなくする）"),
    ("t_off", 0.0, "計算の時刻 0 に当たる群の時刻 (s)"),
    ("hot_on", 0.0, "途中から始める版：群の時刻 t_off の線形の場を初めに置く（1）"),
    ("xhot", 420.0, "初めの場の前端 x (m)"),
    ("hot_w", 30.0, "初めの場の前端のなだらかさ (m)"),
    ("xa0", 706.0, "波を吸う帯の始まり x (m)"),
    ("ytop", 32.0, "箱の天井 y (m)"),
    ("band_vox", 4.0, "narrow band の厚さ（格子の数）"),
    ("relax_a", 1.0, "波を吸う帯の強さ（倍率）"),
    ("maxsub", 2.0, "FLIP の最大小刻み"),
    ("abs_sigma", 0.8, "スポンジの σmax (1/s)"),
    ("abs_pow", 2.0, "スポンジの強さの増え方 χ^p の p"),
    ("mx0", 300.0, "網目を切る箱 x の始まり"),
    ("mx1", 706.0, "網目を切る箱 x の終わり"),
    ("my0", -14.0, "網目を切る箱 y の下"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/E/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(48,)))
ctrl.setParmTemplateGroup(ptg)

# ---------------------------------------------------------------- 海底（表示と静的物体の形。衝突は下の SDF で）
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)
bgrid.parm("sizex").setExpression('ch("%sLx") + 40' % CT)
bgrid.parm("sizey").setExpression('ch("%sLz") + 40' % CT)
bgrid.parm("rows").setExpression('int((ch("%sLx") + 40)/4) + 1' % CT)
bgrid.parm("cols").setExpression('int((ch("%sLz") + 40)/4) + 1' % CT)
bgrid.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(L.snippet("/obj/E_SETUP/bed_height", EMPTY))
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, bw)

bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
bsdf.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bsdf.parm("sizey").setExpression('ch("%sytop") + ch("%sh0") + 12' % (CT, CT))
bsdf.parm("sizez").setExpression('ch("%sLz") + 8' % CT)
bsdf.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
bsdf.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 12)' % (CT, CT))
bsdf.parm("tz").set(0)
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.parm("snippet").set(L.snippet("/obj/E_SETUP/bed_sdf_value", EMPTY))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- 初めの粒子（帯だけ）
# 速さのため 3 段に分けた（式の波の計算は並列の点の wrangle で）：列の点 → 列ごとの水面と海底 → 粒子を作る → 粒子の流速
cols = setup.createNode("attribwrangle", "init_columns")
cols.parm("class").set(0)
cols.parm("snippet").set(r"""
float dp = ch("%sdp"); float Lx = ch("%sLx"); float Lz = ch("%sLz");
int nx = int(floor(Lx/dp)); int nz = int(floor(Lz/dp));
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++)
        addpoint(0, set((ix + 0.5)*dp, 0.0, -0.5*Lz + (iz + 0.5)*dp));
""" % (CT, CT, CT))
colw = setup.createNode("attribwrangle", "column_eta")
colw.setInput(0, cols)
colw.parm("snippet").set(L.snippet("/obj/E_SETUP/column_eta", EMPTY))
pts0 = setup.createNode("attribwrangle", "init_particles")
pts0.setInput(0, colw)
pts0.parm("class").set(0)
pts0.parm("snippet").set(r"""
float dp = ch("%sdp");
float vox = dp*ch("%sgridscale");
float bandm = (ch("%sband_vox") + 1.0)*vox;
int nc = npoints(0);
for (int c = 0; c < nc; c++) {
    vector P0 = point(0, "P", c);
    float eta = point(0, "eta", c); float yb = point(0, "yb", c);
    float ytop = eta - 0.5*dp;
    float ybot = max(yb + 0.5*dp, eta - bandm);
    for (float y = ytop; y >= ybot; y -= dp) {
        vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
        addpoint(0, set(P0.x, y, P0.z) + jit);
    }
}
for (int c = 0; c < nc; c++) removepoint(0, c);
""" % (CT, CT, CT))
pts = setup.createNode("attribwrangle", "particle_vel")
pts.setInput(0, pts0)
pts.parm("snippet").set(L.snippet("/obj/E_SETUP/particle_vel", EMPTY))
ptsout = setup.createNode("null", "OUT_PARTICLES")
ptsout.setInput(0, pts)


def make_volume(name, rank):
    v = setup.createNode("volume", "vol_" + name)
    v.parm("name").set(name)
    v.parm("rank").set(rank)
    v.parm("uniformsamples").set("size")
    v.parm("divsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
    v.parm("sizex").setExpression('ch("%sLx")' % CT)
    v.parm("sizey").setExpression('ch("%sytop") + ch("%sh0") + 2' % (CT, CT))
    v.parm("sizez").setExpression('ch("%sLz")' % CT)
    v.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
    v.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 2)' % (CT, CT))
    v.parm("tz").set(0)
    return v


# 水の塊の閉じたメッシュ（上の面＝式の波の水面）→ VDB の SDF（直し 1）。上の面の高さは並列の点の wrangle で入れる
wmesh0 = setup.createNode("attribwrangle", "water_mesh")
wmesh0.parm("class").set(0)
wmesh0.parm("snippet").set(r"""
float Lx = ch("%sLx"); float Lz = ch("%sLz"); float h0 = ch("%sh0");
float vox = ch("%sdp")*ch("%sgridscale");
float x0 = -3.0*vox; float x1 = Lx + 3.0*vox; float z0 = -0.5*Lz - 3.0*vox; float z1 = 0.5*Lz + 3.0*vox;
float yb = -h0 - 6.0*vox;
int n = int(ceil((x1 - x0)/(0.5*vox)));
int m = int(ceil((z1 - z0)/(0.5*vox)));
int top[];
for (int j = 0; j <= m; j++) {
    float z = z0 + (z1 - z0)*j/m;
    for (int i = 0; i <= n; i++) {
        float x = x0 + (x1 - x0)*i/n;
        int p = addpoint(0, set(x, 0.0, z));
        setpointgroup(0, "top", p, 1);
        push(top, p);
    }
}
#define TI(i, j) top[(j)*(n + 1) + (i)]
for (int j = 0; j < m; j++)
    for (int i = 0; i < n; i++)
        addprim(0, "poly", TI(i, j), TI(i, j + 1), TI(i + 1, j + 1), TI(i + 1, j));
int b00 = addpoint(0, set(x0, yb, z0)); int b10 = addpoint(0, set(x1, yb, z0));
int b11 = addpoint(0, set(x1, yb, z1)); int b01 = addpoint(0, set(x0, yb, z1));
addprim(0, "poly", b00, b10, b11, b01);
int side[];
side = array(b00); for (int i = 0; i <= n; i++) push(side, TI(i, 0)); push(side, b10);
addprim(0, "poly", side);
side = array(b11); for (int i = n; i >= 0; i--) push(side, TI(i, m)); push(side, b01);
addprim(0, "poly", side);
side = array(b01); for (int j = m; j >= 0; j--) push(side, TI(0, j)); push(side, b00);
addprim(0, "poly", side);
side = array(b10); for (int j = 0; j <= m; j++) push(side, TI(n, j)); push(side, b11);
addprim(0, "poly", side);
""" % (CT, CT, CT, CT, CT))
wmesh = setup.createNode("attribwrangle", "water_mesh_top")
wmesh.setInput(0, wmesh0)
wmesh.parm("group").set("top")
wmesh.parm("snippet").set(L.snippet("/obj/E_SETUP/water_mesh_top", EMPTY))
wvdb = setup.createNode("vdbfrompolygons", "surface_vdb")
wvdb.setInput(0, wmesh)
wvdb.parm("voxelsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
wvdb.parm("builddistance").set(1)
wvdb.parm("distancename").set("surface")
wvdb.parm("exteriorbandvoxels").set(6)
wvdb.parm("interiorbandvoxels").set(6)
wvdb.parm("fillinterior").set(1)
vsvdb = setup.createNode("null", "OUT_SURFACE_VDB")
vsvdb.setInput(0, wvdb)

vv = make_volume("vel", "vector")
vvw = setup.createNode("volumewrangle", "init_vel")
vvw.setInput(0, vv)
vvw.parm("snippet").set(L.snippet("/obj/E_SETUP/init_vel", EMPTY))
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)
vvcv = setup.createNode("convertvdb", "vel_to_vdb")
vvcv.setInput(0, vvout)
vvcv.parm("conversion").set("vdb")
vvmg = setup.createNode("vdbvectormerge", "vel_merge")
vvmg.setInput(0, vvcv)
vvvdb = setup.createNode("null", "OUT_VEL_VDB")
vvvdb.setInput(0, vvmg)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP（P1 と同じ組み）
dop = obj.createNode("dopnet", "E_SIM")
dop.parm("cachemaxsize").set(3000)
dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
dop.parm("explicitcachename").set('`chs("%sckpt")`/e.$SF4.sim' % CT)
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
fo.parm("surfacetype").set("4")  # Narrow Band
fo.parm("soppath").set("/obj/E_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/E_SETUP/OUT_SURFACE_VDB")
# 直し（E、2026-10-07 21:15。FLIP37 P3 の直し 2 と同じ）：初めの流速は Houdini の volume（vel.x/vel.y/vel.z）をそのまま渡す。
# VDB へ変えて VDB Vector Merge した OUT_VEL_VDB は 1 成分の 0 の VDB になっていて（e_diag_vel の診断）、帯より深い所の流速が 0 から始まった
# （x 250 m で 2 コマ目に y −20・−35・−50 m の x の流速が線形の 53・24・7 %）。
fo.parm("import_nbvelocity").set("/obj/E_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/E_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/E_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet("/obj/E_SIM/relax_zones", EMPTY))

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(2, relax)
fs.parm("veltransfer").set("apic")
fs.parm("usemgpreconditioner").set(0)
fs.parm("usepreconditioner").set(1)
fs.parm("minimumsubsteps").set(1)
fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
fs.parm("dynamicresize").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").setExpression('ch("%sband_vox")' % CT)
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

# ---------------------------------------------------------------- 読み取り（水面の場と網目）
rd = obj.createNode("geo", "E_READ")
for c in rd.children():
    c.destroy()
fi = rd.createNode("dopimportfield::2.0", "surface_field")
fi.parm("doppath").set("/obj/E_SIM")
fi.parm("fields").set(1)
fi.parm("objname1").set("water")
fi.parm("fieldname1").set("surface")
cv = rd.createNode("convertvolume", "surface_mesh")
cv.setInput(0, fi)
cv.parm("iso").set(0.0)
cut = rd.createNode("attribwrangle", "crop_box")
cut.setInput(0, cv)
cut.parm("class").set(1)  # prims
cut.parm("snippet").set(r'''
vector c = v@P;
if (c.x < chf("%smx0") || c.x > chf("%smx1") || c.y < chf("%smy0")) removeprim(0, @primnum, 1);
''' % (CT, CT, CT))
dv = rd.createNode("divide", "tris")
dv.setInput(0, cut)
dv.parm("convex").set(1)
dv.parm("numsides").set(3)
vw = rd.createNode("attribwrangle", "vtx_pt")
vw.setInput(0, dv)
vw.parm("class").set(3)  # vertices
vw.parm("snippet").set("i@pt = vertexpoint(0, @vtxnum);")
mo = rd.createNode("null", "OUT_MESH")
mo.setInput(0, vw)
rd.layoutChildren()

gsv = vsvdb.geometry()
pv = [p for p in gsv.prims()][0]
print("surface vdb", pv.type(), [round(pv.sample(hou.Vector3(300, y, 0)), 3) for y in (-55, -30, -10, -2, 0.5, 5)])
gb = bedout.geometry()
print("bed bbox", gb.boundingBox())
hou.hipFile.save(HIP)
print("saved", HIP)
