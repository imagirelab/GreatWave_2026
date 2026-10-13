# -*- coding: utf-8 -*-
"""FLIP45：3D の水槽の場面を作り、Houdini/FLIP45/g45_tank.hiplc に保存する（hython 22.0.466。数十秒）。
FLIP44 の g44_build_tank.py（Tools/GWWaveGen/flip44、変えていない）を写して 3D に直した。FLIP44 と同じにした所：
  粒子の置き方（粒子の狭い帯なしで水の全体。格子の中心の列に dp ごと、0.2 dp の揺らぎ）、閉じたメッシュから作る初めの水面の VDB、
  FLIP Solver 2.0・APIC・格子 = 粒子 × 2・圧力の前処理 IC、帯は水平の流速だけを寄せる、帯の重みを小刻みの長さに合わせる、
  各コマの小刻みの数を記録する Geometry Wrangle、帯の wrangle は 64 ビット、CTRL の値は parm.set で入れる（既定値は 6 桁に丸められる）。
変えた所（計画 plan_ja.md §3・§3.1・§5・§10.1）：
  - 3D の箱：x は x0 から Lx、上は −20 m から Hz（どれも格子の倍数）、横は z 0〜W。z = 0（対称の面）と x の両端・横の外の壁・底は閉じた壁、
    上は開く。海底は箱の底（閉じた壁）で、海底の SDF と Static Object は使わない（見直し M3）。Use Waterline は使わない。
    Houdini の場の格子の中心は世界の原点から格子の倍数に並ぶので、壁を格子の面に置くため、Houdini の中では全部を計画の座標から
    o = (ox, oy, oz)（CTRL）だけずらす（Houdini = 計画 + o。静かな水面は Houdini の y = oy、対称の面は z = oz。読み方 R1）。
  - 帯の目標は入口の表（体積 eta・U・V、軸 X = x・Y = t・Z = 横）を File SOP で読む（CTRL の table_file。g45_run.py が書く）。
  - 粒子は、列の点（detail の wrangle）から点ごとの wrangle で縦に足す（多くの粒子を速く作るため。置く位置は FLIP44 と同じ決まり）。
  - 面（記録 R5）を作る SOP の道 G45_SURF：DOP の粒子 → 水面から surf_layer_m より深い粒子を除く（0 なら除かない）→ z < mirror_m の
    粒子を z → −z に写して足す → Particle Fluid Surface（particlesep = dp、voxelsize = surf_vox_scale、Adaptivity 0.005、v を移す）
    → z = 0 で切る → 三角形 → 点の法線 → 切り出しの範囲（crop）の外と底の近くの面を除く。
  - 読み取り G45_READ：水面の場（surface）と流速の場（vel）。
使い方：hython g45_build_tank.py
"""
import hou, os, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45")
import importlib, g45_tanklib as L
importlib.reload(L)

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP45/g45_tank.hiplc"
CT = L.CT

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G45_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    # 箱と解き方（既定は L1・粒子 0.5 m。g45_run.py が cfg の parms で上書きする）
    ("dp", 0.5, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("x0", 0.0, "箱の上流の壁 x0 (m)"),
    ("Lx", 340.0, "箱の長さ x (m)（格子の倍数）"),
    ("W", 108.0, "箱の横の幅 z 0〜W (m)（格子の倍数）"),
    ("zb", -20.0, "箱の底（海底）(m)"),
    ("Hz", 36.0, "箱の高さ（底から）(m)（格子の倍数）"),
    ("h0", 20.0, "水深 h (m)"),
    ("k0", 0.08723286892394641, "深さの形の波数 k0 (1/m)（Ω の波数）"),
    ("maxsub", 8.0, "FLIP の最大小刻み"),
    ("minsub", 1.0, "FLIP の最小小刻み"),
    ("cfl", 1.0, "CFL Condition（cflcond）"),
    ("pcfl", 0.75, "Particle Advection CFL（partcflcond）"),
    ("t_off", -2.0, "コマ 1 の時刻 (s)"),
    # 帯
    ("in_on", 1.0, "入口の帯（1 で使う）"),
    ("in0", 0.0, "入口の帯の壁の側 x (m)"),
    ("in1", 36.0, "入口の帯の内の縁 x (m)"),
    ("in_tgt", 1.0, "入口の帯の目標（1 = 表、0 = 静かな水）"),
    ("sd_on", 1.0, "横の帯（1 で使う）"),
    ("sd0", 72.0, "横の帯の内の縁 z (m)"),
    ("sd1", 108.0, "横の帯の外の壁 z (m)"),
    ("sd_gen", 200.0, "横の帯が起こす所の終わり x (m)"),
    ("sd_sw", 230.0, "横の帯の切り替えの終わり x (m)（これより先は吸う）"),
    ("ex0", 304.0, "出口の帯の内の縁 x (m)"),
    ("ex1", 340.0, "出口の帯の壁 x (m)"),
    ("ex_mode", 0.0, "出口の帯（0 = 吸う、1 = 表の目標へ寄せる：煙の試し S3b だけ）"),
    ("relax_g", 1.0, "起こす帯の強さ（FLIP42 の重みに掛ける）"),
    ("dt0", 1.0 / 24.0, "帯の重みの基準の刻み dt0 (s)"),
    ("abs_sigma", 2.37, "吸う帯の速さ σ (1/s)"),
    ("abs_pow", 2.0, "吸う帯の強さの増え方 χ^p の p"),
    ("wall_taper_m", 9.0, "壁のなだらかさの長さ L_w (m)（帯の厚さの 1/4）"),
    ("amp_gain", 1.0, "目標の全体に掛ける数（静かな水の試しは 0）"),
    ("in_gain", 1.0, "入口の帯の目標に掛ける数（既定 1。入口の利得を帯ごとに掛ける案。読み方 R17）"),
    ("sd_gain", 1.0, "横の帯の目標に掛ける数（既定 1）"),
    ("tab_on", 1.0, "表を読む（0 なら目標は 0）"),
    ("tab_levels", 6.0, "表の流速の深さの数（2 以上で深さごとの表 U0..・V0..。1 以下は水面の U・V）"),
    ("tab_dz", 4.0, "表の流速の深さの間隔 (m)"),
    ("ox", 0.5, "Houdini の x = 計画の x + ox（壁を格子の面に置くずらし。g45_common.box）"),
    ("oy", 0.5, "Houdini の上 y = 計画の z + oy（静かな水面は Houdini の y = oy）"),
    ("oz", 0.5, "Houdini の横 z = 計画の y + oz（対称の面は Houdini の z = oz）"),
    # 面（R5）
    ("surf_layer_m", 0.0, "面を作る粒子：水面からこの深さより下を除く (m)（0 なら水の全体）"),
    ("mirror_m", 1.0, "対称の面から写す粒子の幅 (m)"),
    ("surf_vox_scale", 1.0, "Particle Fluid Surface の Voxel Scale"),
    ("crop_x0", 36.0, "面を切り出す x の始め (m)"),
    ("crop_x1", 304.0, "面を切り出す x の終わり (m)"),
    ("crop_z1", 72.0, "面を切り出す横の終わり (m)"),
    ("surf_ycut", -12.0, "これより下の面（底・壁）を除く y (m)"),
    ("surf_keep_vox", 1.0, "FLIP の水面の場からこの格子の数より離れた三角形を除く"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("table_file", "入口の表（bgeo の体積 eta・U・V）", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/tmp/table_none.bgeo.sc",)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP45/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(240,)))
ctrl.setParmTemplateGroup(ptg)
for nm, dv, lb in PARMS:
    ctrl.parm(nm).set(dv)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

# ---------------------------------------------------------------- 入口の表
tf = setup.createNode("file", "table_file")
tf.parm("file").set('`chs("%stable_file")`' % CT)
tf.parm("missingframe").set(1)
tabout = setup.createNode("null", "OUT_TABLE")
tabout.setInput(0, tf)

# ---------------------------------------------------------------- 初めの粒子（水の全体、静かな水、流速 0）
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
pts0.parm("class").set(2)       # points
pts0.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float zb = ch(CT+"zb");
int c = i@col;
float ytop = -0.5*dp;
float ybot = zb + 0.5*dp;
for (float y = ytop; y >= ybot - 1e-6; y -= dp) {
    vector jit = (set(rand(c*7919 + y*13.1), rand(c*104729 + y*7.7), rand(c*1299709 + y*3.3)) - 0.5)*0.2*dp;
    int p = addpoint(0, set(@P.x, y + chf(CT+"oy"), @P.z) + jit);
    setpointattrib(0, "v", p, {0, 0, 0});
}
removepoint(0, @ptnum);
""")
pclean = setup.createNode("attribdelete", "drop_col")
pclean.setInput(0, pts0)
pclean.parm("ptdel").set("col")
ptsout = setup.createNode("null", "OUT_PARTICLES")
ptsout.setInput(0, pclean)

# 水の塊の閉じたメッシュ（上の面 y = 0）→ VDB の SDF（FLIP44 と同じ）
wmesh0 = setup.createNode("attribwrangle", "water_mesh")
wmesh0.parm("class").set(0)
wmesh0.parm("snippet").set(r"""
#define CT "%s"
float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float W = ch(CT+"W"); float zb = ch(CT+"zb");
float vox = ch(CT+"dp")*ch(CT+"gridscale");
float ox = ch(CT+"ox"); float oy = ch(CT+"oy"); float oz = ch(CT+"oz");
float xa = x0 - 3.0*vox + ox; float xb = x0 + Lx + 3.0*vox + ox; float za = -3.0*vox + oz; float zc = W + 3.0*vox + oz;
float yb = zb - 6.0*vox + oy; float yt = oy;
int b00 = addpoint(0, set(xa, yb, za)); int b10 = addpoint(0, set(xb, yb, za));
int b11 = addpoint(0, set(xb, yb, zc)); int b01 = addpoint(0, set(xa, yb, zc));
int t00 = addpoint(0, set(xa, yt, za)); int t10 = addpoint(0, set(xb, yt, za));
int t11 = addpoint(0, set(xb, yt, zc)); int t01 = addpoint(0, set(xa, yt, zc));
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

BOXC = dict(sx='ch("%sLx")' % CT, sy='ch("%sHz")' % CT, sz='ch("%sW")' % CT,
            tx='ch("%sx0") + 0.5*ch("%sLx") + ch("%sox")' % (CT, CT, CT), ty='ch("%szb") + 0.5*ch("%sHz") + ch("%soy")' % (CT, CT, CT),
            tz='0.5*ch("%sW") + ch("%soz")' % (CT, CT))
vv = setup.createNode("volume", "vol_vel")
vv.parm("name").set("vel")
vv.parm("rank").set("vector")
vv.parm("uniformsamples").set("size")
vv.parm("divsize").setExpression(VOXE)
vv.parm("sizex").setExpression(BOXC["sx"]); vv.parm("sizey").setExpression(BOXC["sy"]); vv.parm("sizez").setExpression(BOXC["sz"])
vv.parm("tx").setExpression(BOXC["tx"]); vv.parm("ty").setExpression(BOXC["ty"]); vv.parm("tz").setExpression(BOXC["tz"])
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vv)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G45_SIM")
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
fo.parm("surfacetype").set("4")  # Narrow Band の入力（帯なしの計算では g45_run.py が donarrowband を 0 にする。FLIP44 と同じ）
fo.parm("soppath").set("/obj/G45_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G45_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G45_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet("/obj/G45_SIM/relax_zones"))
relax.parm("exportlist").set("vel")
relax.parm("vex_precision").set("64")

ssc = dop.createNode("geometrywrangle", "substep_count")
ssc.parm("bindclass").set("detail")
ssc.parm("snippet").set(L.BODIES["/obj/G45_SIM/substep_count"])
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
fs.parm("usewaterline").set(0)
fs.parm("useboundarylayer").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").set(1000.0)
fs.parm("dosurfacetension").set(0)
# 2026-10-12 の確かめ（煙の試しの前の probe_box）：FLIP の場の格子の中心は世界の原点から格子の大きさの倍数に並び、Volume Limits の箱の中に
# 中心がある格子だけが場に入る。閉じた壁は場の端の格子の面にある。計画の壁（x0・横 0・底 −20 m）が格子の面に来るように、Houdini の中では
# 全部を o = (ox, oy, oz) だけずらして置く（g45_common.box。読み方 R1）。Volume Limits の箱は、ずらした計画の箱そのもの。
fs.parm("limit_sizex").setExpression(BOXC["sx"])
fs.parm("limit_sizey").setExpression(BOXC["sy"])
fs.parm("limit_sizez").setExpression(BOXC["sz"])
fs.parm("limit_tx").setExpression(BOXC["tx"])
fs.parm("limit_ty").setExpression(BOXC["ty"])
fs.parm("limit_tz").setExpression(BOXC["tz"])

gr = dop.createNode("gravity", "gravity")
gr.setInput(0, fs)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り（水面の場、流速の場）
rd = obj.createNode("geo", "G45_READ")
for c in rd.children():
    c.destroy()
for nm in ("surface", "vel"):
    fi = rd.createNode("dopimportfield::2.0", nm + "_field")
    fi.parm("doppath").set("/obj/G45_SIM")
    fi.parm("fields").set(1)
    fi.parm("objname1").set("water")
    fi.parm("fieldname1").set(nm)
rd.layoutChildren()

# ---------------------------------------------------------------- 面（記録 R5）
sf = obj.createNode("geo", "G45_SURF")
for c in sf.children():
    c.destroy()
di = sf.createNode("dopimport", "particles")
di.parm("doppath").set("/obj/G45_SIM")
di.parm("objpattern").set("water")
sfield = sf.createNode("object_merge", "surface_field")
sfield.parm("objpath1").set("/obj/G45_READ/surface_field")
layer = sf.createNode("attribwrangle", "layer_and_mirror")
layer.setInput(0, di)
layer.setInput(1, sfield)
layer.parm("class").set(2)
layer.parm("snippet").set(r"""
#define CT "%s"
float lm = ch(CT+"surf_layer_m");
if (lm > 0.0) {
    // 薄い層：水面のすぐ近く（SDF > −格子の半分）でない粒子は、上へ格子ごとに L まで見て、どこにも空気（SDF > 0）がなければ除く。
    // FLIP の水面の場は水の深い所で値が切られている（煙の試し S6、2026-10-12）ので、SDF の値ではなく、上の空気の有無で決める（読み方 R20）
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
if (@P.z - oz < ch(CT+"mirror_m")) {          // 対称の面（Houdini の z = oz）から mirror_m の中の粒子を写す
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
crop.parm("class").set(1)       # primitives
crop.parm("snippet").set(r"""
#define CT "%s"
int pts[] = primpoints(0, @primnum);
vector c = 0;
foreach (int p; pts) c += point(0, "P", p);
c /= max(1, len(pts));
// FLIP の水面の場から格子 surf_keep_vox 個より離れた三角形（薄い層の下の面、箱の底・壁）を除く（煙の試し S6、2026-10-12。読み方 R20）
float sdfc = volumesample(1, "surface", c);
float vox = ch(CT+"dp")*ch(CT+"gridscale");
vector cp = c - set(ch(CT+"ox"), ch(CT+"oy"), ch(CT+"oz"));      // 計画の座標
if (len(pts) != 3 || cp.x < ch(CT+"crop_x0") || cp.x > ch(CT+"crop_x1") || cp.z > ch(CT+"crop_z1") || cp.y < ch(CT+"surf_ycut")
    || abs(sdfc) > ch(CT+"surf_keep_vox")*vox)
    removeprim(0, @primnum, 1);
""" % CT)
nrm = sf.createNode("normal", "point_normals")
nrm.setInput(0, crop)
nrm.parm("type").set(0)  # points
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

for n in (cols, pts0, wmesh0, wvdb):
    try:
        n.cook(force=True)
    except Exception as e:
        print("COOK ERROR", n.path(), str(e)[:400])
    if n.errors():
        print("ERR", n.path(), n.errors())
print("gravity", [(p.name(), p.eval()) for p in gr.parms() if p.name().startswith("force")])
g = ptsout.geometry()
print("particles", g.intrinsicValue("pointcount") if g else None, "bbox", g.boundingBox() if g else None)
print("solver inputs", fs.inputLabels())
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
print("saved", HIP)
