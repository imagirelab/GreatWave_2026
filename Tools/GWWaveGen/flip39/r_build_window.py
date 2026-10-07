# -*- coding: utf-8 -*-
"""FLIP39 R 主役の範囲の水槽（hython 22.0.459）：E の場の一番 E3_dir20_lens（粒子 1 m）の主役の範囲だけを細かい粒子で計算し直す。
FLIP37 P3 の箱（Tools/GWWaveGen/flip37/build_p3_window.py）を写し、次だけを替えた：
- 海底：E3 と同じ e_tanklib の bedy3（斜面 1:4・岩棚 26 m・盛り上がり lg1）。z は E と同じく ±Lz/2 に切り詰める。
- 箱の z の低い側（wz0 = −120 m）は E3 の壁（対称の面）そのもの。境界の帯を置かず（padz0 = 0）、閉じた滑る壁のままにする。
  ほかの 3 つの側（x の両側、z の高い側）は P3 と同じく境界の帯（厚さ pad）で粗い計算の水面と流速を毎コマ渡す。
- 粗い場は R/C3_export/fields（r_export_coarse.py）。初めの流速は P3 の直し 2 と同じく vel.x/vel.y/vel.z の volume をそのまま渡す。
- 圧力は P3 の本番と同じ Multigrid ＋適応の升目（P3 の T0d で粒子 1 m で形を変えないと確かめた設定）。
- 使わない「動く壁」の部品（P3 の 23:22 の案）は入れない。
計算の中に力・速さは足さない。箱の境界で渡すのは粗い計算（境界の造波と海底だけで起きた波）の水面と流速だけである。
保存先：Houdini/FLIP39/r_window.hiplc。座標・単位は E と同じ（x 波の進む向き、y 上、z 峰に沿う向き、静かな水面 y=0、1 = 1 m）。
DOP の始まりのコマ = F0（コマ番号は E3 と同じ。計算の時刻 t = (F−1)/24、群の時刻 = t + 35 s）。
"""
import hou, os, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip37")
import p3_nothrottle
print("nothrottle", p3_nothrottle.off())

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP39/r_window.hiplc"
CT = "/obj/R_SETUP/CTRL/"
CDIR = r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/C3_export/fields"

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "R_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    ("dp", 0.3, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("wx0", 300.0, "主役の範囲 x の始まり (m)"),
    ("wx1", 570.0, "主役の範囲 x の終わり (m)"),
    ("wz0", -120.0, "主役の範囲 z の始まり (m)（E3 の壁＝対称の面）"),
    ("wz1", -20.0, "主役の範囲 z の終わり (m)"),
    ("ytop", 32.0, "箱の天井 y (m)"),
    ("pad", 4.0, "境界の帯（Boundary Layer）の厚さ (m)：x の両側と z の高い側"),
    ("padz0", 0.0, "z の低い側の境界の帯の厚さ (m)（0＝閉じた壁のまま。E3 の対称の面）"),
    ("use_bnd", 1.0, "境界の帯を使う"),
    ("applybound", 1.0, "境界の帯の中の流速を粗い流速に置き換える"),
    ("F0", 961.0, "始まりのコマ（E3 のコマ番号）"),
    ("cf_min", 937.0, "粗い場の書き出しの最初のコマ"),
    ("cf_max", 1272.0, "粗い場の書き出しの最後のコマ"),
    ("band_vox", 8.0, "narrow band の厚さ（格子の数）"),
    ("maxsub", 2.0, "FLIP の最大小刻み"),
    ("mgpre", 1.0, "圧力の前処理（0＝Incomplete Cholesky、1＝Multigrid［P3 の本番と同じ］）"),
    ("adapt", 1.0, "圧力を適応の升目で解く（Solve Pressure with Adaptivity）"),
    # 海底（E3 の値。e_tanklib の bedy3 と同じ意味）
    ("Lz", 240.0, "粗い水槽の幅 z (m)（海底の式の z の切り詰め）"),
    ("h0", 60.0, "沖の水深 (m)"),
    ("hr", 26.0, "岩棚の水深 (m)（中央）"),
    ("slope_n", 4.0, "斜面 1:n の n"),
    ("xs0", 420.0, "斜面の始まり x (m)"),
    ("lens_A", 0.0, "レンズ：両側の斜面の始まりを岸へ下げる量 (m)"),
    ("lens_zl", 60.0, "レンズの広がり z (m)"),
    ("lens_dh", 0.0, "レンズ：両側の岩棚を深くする量 (m)"),
    ("lens_z0", 0.0, "レンズの中心 z (m)"),
    ("obl_deg", 0.0, "等深線の斜め (°)"),
    ("lg1_d", 26.0, "盛り上がり 1：頂の水深 (m)"),
    ("lg1_x", 350.0, "盛り上がり 1：中心 x"),
    ("lg1_z", -120.0, "盛り上がり 1：中心 z"),
    ("lg1_sx", 60.0, "盛り上がり 1：広がり x"),
    ("lg1_sz", 110.0, "盛り上がり 1：広がり z"),
    ("lg2_d", 0.0, "盛り上がり 2：頂の水深 (m)（0 で使わない）"),
    ("lg2_x", 560.0, "盛り上がり 2：中心 x"),
    ("lg2_z", -95.0, "盛り上がり 2：中心 z"),
    ("lg2_sx", 25.0, "盛り上がり 2：広がり x"),
    ("lg2_sz", 10.0, "盛り上がり 2：広がり z"),
    # 網目
    ("m_vox", 1.0, "網目：Voxel Scale（粒子の間隔に対する升の大きさ）"),
    ("m_inf", 3.0, "網目：Influence Scale"),
    ("m_smooth", 1.0, "網目：最後のなめらかにする回数（0＝しない）"),
    ("m_adapt", 0.02, "網目：Adaptivity"),
    ("my0", -14.0, "網目を切る y の下 (m)"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("cdir", "粗い場のフォルダー", 1, default_value=(CDIR,)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP39/R/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(12,)))
ctrl.setParmTemplateGroup(ptg)

# 海底の式：e_tanklib.VEX_BED の bedy3 と同じ（z は ±Lz/2 に切り詰める）
VEXLIB = r'''
#define CT "%s"
float lensw(float z) { float zl = chf(CT+"lens_zl"); float zz = z - chf(CT+"lens_z0"); return 1.0 - exp(-(zz*zz)/(zl*zl)); }
float xsz(float z) {
    return chf(CT+"xs0") + chf(CT+"lens_A")*lensw(z) + tan(radians(chf(CT+"obl_deg")))*(z + 0.5*chf(CT+"Lz"));
}
float hrz(float z) { return chf(CT+"hr") + chf(CT+"lens_dh")*lensw(z); }
float bedy3(float x; float z0) {
    float z = clamp(z0, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz"));
    float h0 = chf(CT+"h0"); float n = chf(CT+"slope_n");
    float y = -h0 + max(0.0, x - xsz(z))/n;
    y = min(y, -hrz(z));
    for (int K = 1; K <= 2; K++) {
        string s = "lg" + itoa(K) + "_";
        float d = chf(CT+s+"d");
        if (d > 0.0) {
            float g = exp(-pow((x - chf(CT+s+"x"))/chf(CT+s+"sx"), 2.0) - pow((z - chf(CT+s+"z"))/chf(CT+s+"sz"), 2.0));
            y = max(y, -h0 + (h0 - d)*g);
        }
    }
    return y;
}
''' % CT

YB = 'ch("%sh0") + 2' % CT


def box_parms(node, pre="", margin_vox=0):
    m = '%d*ch("%sdp")*ch("%sgridscale")' % (margin_vox, CT, CT)
    node.parm(pre + "sizex").setExpression('ch("%swx1") - ch("%swx0") + 2*%s' % (CT, CT, m))
    node.parm(pre + "sizey").setExpression('ch("%sytop") + %s + 2*%s' % (CT, YB, m))
    node.parm(pre + "sizez").setExpression('ch("%swz1") - ch("%swz0") + 2*%s' % (CT, CT, m))
    node.parm(pre + "tx").setExpression('0.5*(ch("%swx0") + ch("%swx1"))' % (CT, CT))
    node.parm(pre + "ty").setExpression('0.5*(ch("%sytop") - (%s))' % (CT, YB))
    node.parm(pre + "tz").setExpression('0.5*(ch("%swz0") + ch("%swz1"))' % (CT, CT))


# ---------------------------------------------------------------- 海底
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)
bgrid.parm("sizex").setExpression('ch("%swx1") - ch("%swx0") + 20' % (CT, CT))
bgrid.parm("sizey").setExpression('ch("%swz1") - ch("%swz0") + 20' % (CT, CT))
bgrid.parm("rows").setExpression('int((ch("%swx1") - ch("%swx0") + 20)/2) + 1' % (CT, CT))
bgrid.parm("cols").setExpression('int((ch("%swz1") - ch("%swz0") + 20)/2) + 1' % (CT, CT))
bgrid.parm("tx").setExpression('0.5*(ch("%swx0") + ch("%swx1"))' % (CT, CT))
bgrid.parm("tz").setExpression('0.5*(ch("%swz0") + ch("%swz1"))' % (CT, CT))
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(VEXLIB + '@P.y = bedy3(@P.x, @P.z);\n')
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, bw)

bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
box_parms(bsdf, margin_vox=4)
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.parm("snippet").set(VEXLIB + r'''
float yb = bedy3(@P.x, @P.z);
float e = 0.25;
float gx = (bedy3(@P.x + e, @P.z) - bedy3(@P.x - e, @P.z))/(2.0*e);
float gz = (bedy3(@P.x, @P.z + e) - bedy3(@P.x, @P.z - e))/(2.0*e);
f@collision = (@P.y - yb)/sqrt(1.0 + gx*gx + gz*gz);
''')
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)


# ---------------------------------------------------------------- 粗い場（初めのコマ F0 と、境界のコマの間の線形）
def cfile(name, frame_expr):
    fl = setup.createNode("file", name)
    fl.parm("file").setExpression(
        'chs("%scdir") + "/c_" + padzero(4, clamp(%s, ch("%scf_min"), ch("%scf_max"))) + ".bgeo.sc"' % (CT, frame_expr, CT, CT),
        language=hou.exprLanguage.Hscript)
    return fl


c0 = cfile("coarse_F0", 'ch("%sF0")' % CT)
c0out = setup.createNode("null", "OUT_COARSE_F0")
c0out.setInput(0, c0)
cA = cfile("coarse_A", "floor($FF)")
cB = cfile("coarse_B", "floor($FF) + 1")
cl = setup.createNode("volumewrangle", "coarse_lerp")
cl.setInput(0, cA); cl.setInput(1, cB)
cl.parm("snippet").set(r'''
float w = clamp(@Frame - floor(@Frame), 0.0, 1.0);
f@surface = lerp(f@surface, volumesample(1, "surface", @P), w);
v@vel = lerp(v@vel, volumesamplev(1, "vel", @P), w);
''')
bsurf = setup.createNode("blast", "bnd_surface_only")
bsurf.setInput(0, cl); bsurf.parm("group").set("@name=surface"); bsurf.parm("negate").set(1)
bsurfo = setup.createNode("null", "OUT_BND_SURFACE")
bsurfo.setInput(0, bsurf)
bvel = setup.createNode("blast", "bnd_vel_only")
bvel.setInput(0, cl); bvel.parm("group").set("@name=vel.*"); bvel.parm("negate").set(1)
bvelo = setup.createNode("null", "OUT_BND_VEL")
bvelo.setInput(0, bvel)

# ---------------------------------------------------------------- 初めの粒子（水面の帯だけ、粗い計算のコマ F0 から）
cols = setup.createNode("attribwrangle", "init_columns")
cols.parm("class").set(0)
cols.parm("snippet").set(r"""
float dp = ch("%sdp");
float x0 = ch("%swx0"); float x1 = ch("%swx1"); float z0 = ch("%swz0"); float z1 = ch("%swz1");
int nx = int(floor((x1 - x0)/dp)); int nz = int(floor((z1 - z0)/dp));
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++)
        addpoint(0, set(x0 + (ix + 0.5)*dp, 0.0, z0 + (iz + 0.5)*dp));
""" % (CT, CT, CT, CT, CT))
colw = setup.createNode("attribwrangle", "column_eta")
colw.setInput(0, cols); colw.setInput(1, c0out)
colw.parm("snippet").set(VEXLIB + r"""
// 粗い SDF を上から 0.5 m おきに下へたどり、最初に水（< 0）になる所を線形に求める（F0 は崩れる前なので一番上の水面だけでよい）
float ytop = chf(CT+"ytop");
float yb = bedy3(@P.x, @P.z);
float sprev = volumesample(1, "surface", set(@P.x, ytop, @P.z));
float eta = yb;
for (float y = ytop - 0.5; y >= yb; y -= 0.5) {
    float s = volumesample(1, "surface", set(@P.x, y, @P.z));
    if (s < 0.0) { eta = y + 0.5*s/(s - sprev); break; }
    sprev = s;
}
f@eta = eta;
f@yb = yb;
""")
pts0 = setup.createNode("attribwrangle", "init_particles")
pts0.setInput(0, colw)
pts0.parm("snippet").set(r"""
float dp = ch("%sdp");
float vox = dp*ch("%sgridscale");
float bandm = (ch("%sband_vox") + 1.0)*vox;
float ytop = f@eta - 0.5*dp;
float ybot = max(f@yb + 0.5*dp, f@eta - bandm);
int c = @ptnum;
for (float y = ytop; y >= ybot; y -= dp) {
    vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
    addpoint(0, set(@P.x, y, @P.z) + jit);
}
removepoint(0, @ptnum);
""" % (CT, CT, CT))
pclean = setup.createNode("attribdelete", "drop_col_attribs")
pclean.setInput(0, pts0)
pclean.parm("ptdel").set("eta yb")
pts = setup.createNode("attribwrangle", "particle_vel")
pts.setInput(0, pclean); pts.setInput(1, c0out)
pts.parm("snippet").set('v@v = volumesamplev(1, "vel", @P);\n')
ptsout = setup.createNode("null", "OUT_PARTICLES")
ptsout.setInput(0, pts)

# narrow band の初めの水面：上の面＝粗い計算のコマ F0 の一番上の水面 η(x, z)、底は海底より下の閉じたメッシュ → VDB（内側を埋める）（P3 の直し 1）
wmesh0 = setup.createNode("attribwrangle", "water_mesh")
wmesh0.parm("class").set(0)
wmesh0.parm("snippet").set(r"""
float vox = ch("%sdp")*ch("%sgridscale"); float h0 = ch("%sh0");
float x0 = ch("%swx0") - 3.0*vox; float x1 = ch("%swx1") + 3.0*vox; float z0 = ch("%swz0") - 3.0*vox; float z1 = ch("%swz1") + 3.0*vox;
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
""" % ((CT,) * 7))
wmesh = setup.createNode("attribwrangle", "water_mesh_top")
wmesh.setInput(0, wmesh0); wmesh.setInput(1, c0out)
wmesh.parm("group").set("top")
wmesh.parm("snippet").set(VEXLIB + r"""
float ytop = chf(CT+"ytop");
float yb = bedy3(@P.x, @P.z);
float sprev = volumesample(1, "surface", set(@P.x, ytop, @P.z));
float eta = yb;
for (float y = ytop - 0.5; y >= yb; y -= 0.5) {
    float s = volumesample(1, "surface", set(@P.x, y, @P.z));
    if (s < 0.0) { eta = y + 0.5*s/(s - sprev); break; }
    sprev = s;
}
@P.y = eta;
""")
wvdb = setup.createNode("vdbfrompolygons", "init_surface_vdb")
wvdb.setInput(0, wmesh)
wvdb.parm("voxelsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
wvdb.parm("builddistance").set(1)
wvdb.parm("distancename").set("surface")
wvdb.parm("exteriorbandvoxels").set(6)
wvdb.parm("interiorbandvoxels").set(6)
wvdb.parm("fillinterior").set(1)
s0o = setup.createNode("null", "OUT_SURFACE_VDB")
s0o.setInput(0, wvdb)
v0 = setup.createNode("blast", "init_vel_only")
v0.setInput(0, c0out); v0.parm("group").set("@name=vel.*"); v0.parm("negate").set(1)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "R_SIM")
dop.parm("startframe").setExpression('ch("%sF0")' % CT)
dop.parm("cachemaxsize").set(8000)
dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
dop.parm("explicitcachename").set('`chs("%sckpt")`/r.$SF4.sim' % CT)
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
fo.parm("soppath").set("/obj/R_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/R_SETUP/OUT_SURFACE_VDB")
# 初めの流速は粗い場の vel.x/vel.y/vel.z（Houdini の volume）をそのまま渡す（P3 の直し 2、E §4.2 と同じ。VDB Vector Merge は使わない）
fo.parm("import_nbvelocity").set("/obj/R_SETUP/init_vel_only")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/R_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/R_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.parm("veltransfer").set("apic")
fs.parm("usemgpreconditioner").setExpression('ch("%smgpre")' % CT)
fs.parm("usepreconditioner").setExpression('1 - ch("%smgpre")' % CT)
fs.parm("useadaptivepressure").setExpression('ch("%sadapt")' % CT)
fs.parm("minimumsubsteps").set(1)
fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
fs.parm("dynamicresize").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").setExpression('ch("%sband_vox")' % CT)
box_parms(fs, pre="limit_")
fs.parm("useboundarylayer").setExpression('ch("%suse_bnd")' % CT)
fs.parm("applybound").setExpression('ch("%sapplybound")' % CT)
fs.parm("tankcollision").setExpression('1 - ch("%suse_bnd")' % CT)
fs.parm("boundary_lowerpaddingx").setExpression('ch("%spad")' % CT)
fs.parm("boundary_upperpaddingx").setExpression('ch("%spad")' % CT)
fs.parm("boundary_lowerpaddingz").setExpression('ch("%spadz0")' % CT)
fs.parm("boundary_upperpaddingz").setExpression('ch("%spad")' % CT)
fs.parm("boundary_surface").set("/obj/R_SETUP/OUT_BND_SURFACE")
fs.parm("boundary_velocity").set("/obj/R_SETUP/OUT_BND_VEL")
mg = dop.createNode("merge", "merge")
mg.setInput(0, so)
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り（水面の場、粒子、網目）
rd = obj.createNode("geo", "R_READ")
for c in rd.children():
    c.destroy()
fi = rd.createNode("dopimportfield::2.0", "surface_field")
fi.parm("doppath").set("/obj/R_SIM")
fi.parm("fields").set(1)
fi.parm("objname1").set("water")
fi.parm("fieldname1").set("surface")
dpi = rd.createNode("dopimport", "particles")
dpi.parm("doppath").set("/obj/R_SIM")
dpi.parm("objpattern").set("water")
pdeep = rd.createNode("attribwrangle", "drop_deep_particles")
pdeep.setInput(0, dpi)
pdeep.parm("snippet").set('if (@P.y < chf("%smy0") - 3.0) removepoint(0, @ptnum);' % CT)
mgr = rd.createNode("merge", "parts_and_surface")
mgr.setInput(0, pdeep); mgr.setInput(1, fi)
pfs = rd.createNode("particlefluidsurface::2.0", "fluid_surface")
pfs.setInput(0, mgr)
pfs.parm("particlesep").setExpression('ch("%sdp")' % CT)
pfs.parm("voxelsize").setExpression('ch("%sm_vox")' % CT)
pfs.parm("influenceradius").setExpression('ch("%sm_inf")' % CT)
pfs.parm("dosurfunion").set(1)
pfs.parm("dofinalsmooth").setExpression('ch("%sm_smooth") > 0' % CT)
pfs.parm("finalsmoothiterations").setExpression('ch("%sm_smooth")' % CT)
pfs.parm("adaptivity").setExpression('ch("%sm_adapt")' % CT)
pfs.parm("dotransferattribs").set(0)
pfs.parm("conversion").set("poly")
cut = rd.createNode("attribwrangle", "crop_box")
cut.setInput(0, pfs)
cut.parm("class").set(1)  # prims
cut.parm("snippet").set(r'''
vector c = v@P;
float p = chf("%spad");
if (c.x < chf("%swx0") + p || c.x > chf("%swx1") - p || c.z < chf("%swz0") + chf("%spadz0") || c.z > chf("%swz1") - p || c.y < chf("%smy0"))
    removeprim(0, @primnum, 1);
''' % (CT, CT, CT, CT, CT, CT, CT))
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

hou.hipFile.save(HIP)
print("saved", HIP)
# 確かめ（粗い場のコマ F0 ができていれば）
F0 = int(ctrl.parm("F0").eval())
if os.path.isfile(CDIR + "/c_%04d.bgeo.sc" % F0):
    import numpy as np
    hou.setFrame(F0)
    gc = colw.geometry()
    eta = np.array(gc.pointFloatAttribValues("eta"))
    print("eta stats", eta.min(), eta.max(), eta.mean())
    g = ptsout.geometry()
    print("init particles", g.intrinsicValue("pointcount"), g.boundingBox())
    gs = s0o.geometry()
    pv = gs.prims()[0]
    print("surface vdb", pv.type(), [round(pv.sample(hou.Vector3(402, y, -80)), 3) for y in (-58, -40, -10, 0, 5, 12, 15)])
    gv = v0.geometry()
    print("init vel", [(p.attribValue("name"), p.resolution()) for p in gv.prims()])
    gb = bvelo.geometry()
    print("bnd vel", [p.attribValue("name") for p in gb.prims()])
for nm in ("boundary_lowerpaddingx", "boundary_lowerpaddingy", "boundary_upperpaddingy", "boundary_lowerpaddingz", "boundary_upperpaddingz"):
    p = fs.parm(nm)
    print(nm, p.eval() if p else None)
