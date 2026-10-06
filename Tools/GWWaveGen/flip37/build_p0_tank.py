# -*- coding: utf-8 -*-
"""P0 水槽の確かめ：断面の水槽（幅 8 m の薄い板）を作り、Houdini/FLIP37/p0_tank.hiplc に保存する。

hython 22.0.459 で実行する。キャッシュは入れない（シーンは小さいまま）。
- 座標：x＝波の進む向き、y＝上、z＝板の幅。静かな水面 y = 0。1 単位 = 1 m。
- 水槽：波を起こす帯 → 平らな助走（水深 60 m）→ 斜面 1:4 → 岩棚（水深 26 m）→ 波を吸う帯。
- 波を起こす帯：relaxation zone（Jacobsen ら 2012 の重み）で、格子の流速 vel を
  線形の式の波（Airy、有限水深）へ少しずつ寄せる。FLIP Solver DOP の Volume Velocity 入力。
- 波を吸う帯：同じ重みで流速を 0（静かな水）へ寄せる。
- 計算の始め（hot start）：帯と助走を同じ式の波で満たす（粒子・surface・vel）。
- 粒子は水面近くの帯だけ（narrow band）。帯の厚さは CTRL の band_vox（格子の数）。
数値はすべて /obj/P0_SETUP/CTRL の予備パラメータにあり、ch() で参照する。

FLIP37（Q37 の試作）での直し 1（2026-10-06）：FLIP36 の版では静かな水が自由落下した。原因は 2 つ。
- 水面の場（surface）と流速（vel）を Houdini の普通のボリュームで渡すと、FLIP の圧力の計算が行われなかった
  （pressure の場が 1×1×1 のまま）。VDB（surface は SDF、vel はベクトル）に変えて渡す。
- 海底（Static Object）が merge の右側にあり、「左が右に作用する」の既定で水に作用していなかった
  （collision の場が全部 -2.8 ＝衝突物なし）。海底を merge の左（入力 0）へ移す。
- 上の 2 つを直しても、長い水槽（x 方向 1152 格子、z 方向 11 格子）では圧力の計算が行われなかった
  （短い水槽 100 m では行われた）。圧力の解き方の前処理を Multigrid から Incomplete Cholesky に替えると解けた。

直し 2（2026-10-06）：直し 1 の後の静かな水（T1_still_b3_fix1）では、波を起こす帯・吸う帯の水面が 2〜3 m 上がり、
その乱れが水槽の中へ広がった（平らな所で 0.69 m）。帯の中で流速を 3 成分とも目標（静かな水では 0）へ寄せると、
その小刻みの重力の分が消え、帯の中の圧力が静水圧にならず、外から水が押し込まれるため。
帯の中では水平の流速（x と z）だけを寄せ、縦の流速は圧力の計算に任せる（縦は連続の式から決まる）。
"""
import hou, os, sys

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p0_tank.hiplc"
CT = "/obj/P0_SETUP/CTRL/"

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "P0_SETUP")
for c in setup.children():
    c.destroy()

# ---------------------------------------------------------------- CTRL
ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    # name, default, label
    ("dp", 0.35, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("W", 8.0, "板の幅 (m)"),
    ("Lx", 806.0, "水槽の長さ (m)"),
    ("h0", 60.0, "沖の水深 (m)"),
    ("hr", 26.0, "岩棚の水深 (m)"),
    ("slope_n", 4.0, "斜面 1:n の n"),
    ("xs0", 420.0, "斜面の始まり x (m)"),
    ("xg_end", 140.0, "波を起こす帯の終わり x (m)"),
    ("xa0", 706.0, "波を吸う帯の始まり x (m)"),
    ("ytop", 12.0, "箱の天井 y (m)"),
    ("T", 14.0, "周期 T (s)"),
    ("H", 3.0, "波の高さ H (m)（0 で静かな水）"),
    ("ph0", 0.0, "位相 (rad)"),
    ("xhot", 420.0, "hot start の波の前端 x (m)"),
    ("hot_w", 30.0, "hot start の前端のなだらかさ (m)"),
    ("band_vox", 3.0, "narrow band の厚さ（格子の数）"),
    ("relax_g", 1.0, "波を起こす帯の強さ（倍率）"),
    ("relax_a", 1.0, "波を吸う帯の強さ（倍率）"),
    ("maxsub", 2.0, "FLIP の最大小刻み"),
    ("abs_mode", 1.0, "波を吸う帯の形（0＝FLIP36 の重み relaxw を小刻みごとに掛ける、1＝なだらかなスポンジ 1-exp(-σ χ^p dt)）"),
    ("abs_sigma", 0.4, "スポンジの最も強い所の減衰の速さ σmax (1/s)"),
    ("abs_pow", 2.0, "スポンジの強さの増え方 χ^p の p"),
    ("p_init", 0.0, "最初の小刻みで圧力に静水圧を入れる（1＝入れる、0＝入れない）。試したが効かなかったので既定は 0"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
# 直し（途中保存の名前）：FLIP36 では CTRL にファイル名を $SF4 ごと置き、dopnet から chs() で読んだため、
# $SF4 が CTRL（SOP）の中で空に展開され、全部の途中保存が同じ「p0..sim」に上書きされた。
# CTRL にはフォルダーだけを置き、$SF4 は dopnet の側で展開する。
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P0/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(48,)))
ctrl.setParmTemplateGroup(ptg)

# 共通の VEX 関数（式の波と海底）
VEXLIB = r'''
#define GG 9.80665
#define CT "%s"
float kdisp(float om; float h) {
    float k = om*om/GG;
    for (int i = 0; i < 50; i++) {
        float th = tanh(k*h);
        float f = GG*k*th - om*om;
        float df = GG*th + GG*k*h*(1.0 - th*th);
        k -= f/df;
    }
    return k;
}
float bedy(float x) {
    float h0 = chf(CT+"h0"); float hr = chf(CT+"hr"); float xs0 = chf(CT+"xs0"); float n = chf(CT+"slope_n");
    float y = -h0 + max(0.0, x - xs0)/n;
    return min(y, -hr);
}
// 線形の進行波（水深 h0 の平らな所の式）。E は振幅の掛け目。
void airy(float x; float y; float t; float E; float eta; vector vel) {
    float T = chf(CT+"T"); float H = chf(CT+"H"); float h0 = chf(CT+"h0"); float ph0 = chf(CT+"ph0");
    float om = 2.0*PI/T; float k = kdisp(om, h0); float a = 0.5*H*E;
    float th = k*x - om*t + ph0;
    eta = a*cos(th);
    float ye = clamp(y, -h0, 0.0);
    float s = sinh(k*h0);
    vel = set(a*om*cosh(k*(ye + h0))/s*cos(th), a*om*sinh(k*(ye + h0))/s*sin(th), 0.0);
}
float hotE(float x) {
    return 0.5*(1.0 - tanh((x - chf(CT+"xhot"))/chf(CT+"hot_w")));
}
float relaxw(float chi) { // Jacobsen ら 2012。chi=1 で外の端（式に完全に合わせる）、0 で計算の領域との境
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
''' % CT

# ---------------------------------------------------------------- 海底
bed = setup.createNode("attribwrangle", "bed_profile")
bed.parm("class").set(0)  # detail
bed.parm("snippet").set(VEXLIB + r'''
float Lx = chf(CT+"Lx"); float h0 = chf(CT+"h0"); float hr = chf(CT+"hr");
float xs0 = chf(CT+"xs0"); float n = chf(CT+"slope_n"); float W = chf(CT+"W");
float zb = -0.5*W - 10.0;
float xe = xs0 + (h0 - hr)*n;
vector pts[] = array(set(-20, -h0-10, zb), set(-20, -h0, zb), set(xs0, -h0, zb), set(xe, -hr, zb),
                     set(Lx+20, -hr, zb), set(Lx+20, -h0-10, zb));
int prim = addprim(0, "poly");
for (int i = 0; i < len(pts); i++) { int p = addpoint(0, pts[i]); addvertex(0, prim, p); }
''')
ext = setup.createNode("polyextrude::2.0", "bed_extrude")
ext.setInput(0, bed)
ext.parm("dist").setExpression('ch("%sW") + 20' % CT)
ext.parm("outputback").set(1)
ctr = setup.createNode("attribwrangle", "bed_center_z")
ctr.setInput(0, ext)
ctr.parm("snippet").set("@P.z -= getbbox_center(0).z;")
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, ctr)
# 海底の符号付き距離（下が負＝固体の中）。式で直接作る（多角形の向きに左右されない）
bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression('ch("%sdp")*ch("%sgridscale")' % (CT, CT))
bsdf.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bsdf.parm("sizey").setExpression('ch("%sytop") + ch("%sh0") + 12' % (CT, CT))
bsdf.parm("sizez").setExpression('ch("%sW") + 4' % CT)
bsdf.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
bsdf.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 12)' % (CT, CT))
bsdf.parm("tz").set(0)
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.parm("snippet").set(VEXLIB + r'''
float yb = bedy(@P.x);
float n = chf(CT+"slope_n");
f@collision = (@P.y - yb)/sqrt(1.0 + 1.0/(n*n)) ;  // 斜面では距離に近づける。平らな所では少し小さめ（安全側）
''')
bsdf = bsdfw
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdf)

# ---------------------------------------------------------------- 初めの粒子（帯だけ）
pts = setup.createNode("attribwrangle", "init_particles")
pts.parm("class").set(0)
pts.parm("snippet").set(VEXLIB + r'''
float dp = chf(CT+"dp"); float Lx = chf(CT+"Lx"); float W = chf(CT+"W");
float vox = dp*chf(CT+"gridscale");
float bandm = (chf(CT+"band_vox") + 1.0)*vox;
int nx = int(floor(Lx/dp)); int nz = int(floor(W/dp));
addpointattrib(0, "v", {0,0,0});
for (int ix = 0; ix < nx; ix++) {
    float x = (ix + 0.5)*dp;
    float E = hotE(x);
    float eta; vector vv;
    airy(x, 0.0, 0.0, E, eta, vv);
    float yb = bedy(x);
    float ytop = eta - 0.5*dp;
    float ybot = max(yb + 0.5*dp, eta - bandm);
    for (float y = ytop; y >= ybot; y -= dp) {
        float e2; vector v2;
        airy(x, y, 0.0, E, e2, v2);
        for (int iz = 0; iz < nz; iz++) {
            float z = -0.5*W + (iz + 0.5)*dp;
            vector jit = (set(rand(ix*7919 + iz*31 + y*13.1), rand(ix*104729 + iz*17 + y*7.7), rand(ix*1299709 + iz*3 + y*3.3)) - 0.5)*0.2*dp;
            int p = addpoint(0, set(x, y, z) + jit);
            setpointattrib(0, "v", p, v2);
        }
    }
}
''')
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
    v.parm("sizez").setExpression('ch("%sW")' % CT)
    v.parm("tx").setExpression('0.5*ch("%sLx")' % CT)
    v.parm("ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 2)' % (CT, CT))
    v.parm("tz").set(0)
    return v

vs = make_volume("surface", "scalar")
vsw = setup.createNode("volumewrangle", "init_surface")
vsw.setInput(0, vs)
vsw.parm("snippet").set(VEXLIB + r'''
float eta; vector vv;
airy(@P.x, 0.0, 0.0, hotE(@P.x), eta, vv);
f@surface = @P.y - eta;
''')
vsout = setup.createNode("null", "OUT_SURFACE")
vsout.setInput(0, vsw)
# 直し 1：VDB の SDF にする。普通のボリュームを convertvdb で変えると内外の符号が逆になったので、
# 水の塊の閉じたメッシュ（上の面＝式の波の水面、下は海底より深い所、x と z は水槽の外まで）から
# VDB from Polygons（内側を埋める）で作る（Houdini の説明書の narrow band の初期化と同じ道）。
wmesh = setup.createNode("attribwrangle", "water_mesh")
wmesh.parm("class").set(0)
wmesh.parm("snippet").set(VEXLIB + r'''
float Lx = chf(CT+"Lx"); float W = chf(CT+"W"); float h0 = chf(CT+"h0");
float vox = chf(CT+"dp")*chf(CT+"gridscale");
float x0 = -3.0*vox; float x1 = Lx + 3.0*vox; float zh = 0.5*W + 3.0*vox; float yb = -h0 - 6.0*vox;
int n = int(ceil((x1 - x0)/(0.5*vox)));
int tm[], tp[], bm[], bp[];
for (int i = 0; i <= n; i++) {
    float x = x0 + (x1 - x0)*i/n;
    float eta; vector vv;
    airy(x, 0.0, 0.0, hotE(x), eta, vv);
    push(tm, addpoint(0, set(x, eta, -zh))); push(tp, addpoint(0, set(x, eta, zh)));
    push(bm, addpoint(0, set(x, yb, -zh))); push(bp, addpoint(0, set(x, yb, zh)));
}
for (int i = 0; i < n; i++) {
    addprim(0, "poly", tm[i], tp[i], tp[i+1], tm[i+1]);   // 上（水面）
    addprim(0, "poly", bm[i], bm[i+1], bp[i+1], bp[i]);   // 下
    addprim(0, "poly", tp[i], bp[i], bp[i+1], tp[i+1]);   // z+
    addprim(0, "poly", tm[i], tm[i+1], bm[i+1], bm[i]);   // z-
}
addprim(0, "poly", tm[0], bm[0], bp[0], tp[0]);
addprim(0, "poly", tm[n], tp[n], bp[n], bm[n]);
''')
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
vvw.parm("snippet").set(VEXLIB + r'''
float eta; vector vel;
airy(@P.x, @P.y, 0.0, hotE(@P.x), eta, vel);
v@vel = vel;
''')
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)
# 直し 1：VDB のベクトル（vel）にする
vvcv = setup.createNode("convertvdb", "vel_to_vdb")
vvcv.setInput(0, vvout)
vvcv.parm("conversion").set("vdb")
vvmg = setup.createNode("vdbvectormerge", "vel_merge")
vvmg.setInput(0, vvcv)
vvvdb = setup.createNode("null", "OUT_VEL_VDB")
vvvdb.setInput(0, vvmg)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "P0_SIM")
dop.parm("cachemaxsize").set(1500)
dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
dop.parm("explicitcachename").set('`chs("%sckpt")`/p0.$SF4.sim' % CT)
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
fo.parm("soppath").set("/obj/P0_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/P0_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/P0_SETUP/OUT_VEL_VDB")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/P0_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/P0_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(VEXLIB + r'''
// 波を起こす帯と波を吸う帯：格子の流速を目標へ寄せる（毎小刻み）
float x = @P.x;
float xg = chf(CT+"xg_end"); float xa0 = chf(CT+"xa0"); float Lx = chf(CT+"Lx");
if (x < xg) {
    float w = relaxw((xg - x)/xg)*chf(CT+"relax_g");
    float eta; vector tv;
    airy(x, @P.y, f@Time, 1.0, eta, tv);
    w = clamp(w, 0.0, 1.0);
    // 直し 2：水平（x, z）だけを寄せる。縦（y）は圧力の計算に任せる
    v@vel = set(lerp(v@vel.x, tv.x, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
if (x > xa0) {
    float chi = clamp((x - xa0)/(Lx - xa0), 0.0, 1.0);
    float w = clamp(relaxw(chi)*chf(CT+"relax_a"), 0.0, 1.0);
    // 吸う帯の直し 1（2026-10-06）：T2 で吸う帯（300 m＝1.1 波長）からの跳ね返りが 13〜15 % あった。
    // relaxw は帯の終わりの 3 割に強さが集まり、終わりでは小刻みごとに流速を 0 にする（壁に近い）。
    // なだらかなスポンジ（減衰の速さ σ = σmax χ^p を時間で積む）に替える。
    if (chf(CT+"abs_mode") > 0.5)
        w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc*chf(CT+"relax_a"));
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''')

# 直し（圧力の初期値）：水槽が x 方向に 1286 格子までは圧力が解けたが、1429 格子（Lx 1000 m）では
# 前処理を何に替えても解けず（IC・なし・OpenCL・adaptive）、水が自由落下した。z を 22 格子に増やした 2.7M 格子では解けたので、
# 格子の総数ではなく長さに効く（反復の上限に当たっているとみる）。最初の小刻みで、圧力の場に静水圧を入れて
# 「Use Pressure to Warm Start Solver」の初めの推定にする。圧力の場の単位は ρ g 深さ × 小刻みの時間（T1 で 1 m あたり 409 ＝ 1000×9.80665/24）。
# 結果：圧力の場に値は入ったが、流速は自由落下のままで、効かなかった（diag17）。その後の切り分けで、失敗は長さだけでは決まらず
# （Lx 1000・吸う帯 700 からは解け、Lx 950・700 や Lx 1000・730 では解けない。diag18〜20）、原因は分かっていない。既定は 0（入れない）。
pmatch = dop.createNode("gasmatchfield", "pressure_match")
pmatch.parm("field").set("pressure")
pmatch.parm("reffield").set("surface")
pmatch.parm("rank").set("scalar")
pwarm = dop.createNode("gasfieldwrangle", "pressure_warm")
pwarm.setInput(0, pmatch)
pwarm.parm("snippet").set(VEXLIB + r'''
if (chf(CT+"p_init") > 0.5 && f@Time <= 2.01*f@TimeInc) {
    float eta; vector vv;
    airy(@P.x, 0.0, f@Time, hotE(@P.x), eta, vv);
    f@pressure = 1000.0*GG*max(0.0, eta - @P.y)*f@TimeInc;
}
''')
relax.setInput(0, pwarm)

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(2, relax)
fs.parm("veltransfer").set("apic")
# 直し 1：細長い水槽では Multigrid の前処理で圧力が解かれなかった（pressure の場が 1×1×1 のまま）。IC に替える
fs.parm("usemgpreconditioner").set(0)
fs.parm("usepreconditioner").set(1)
fs.parm("minimumsubsteps").set(1)
fs.parm("substeps").setExpression('ch("%smaxsub")' % CT)
fs.parm("dynamicresize").set(0)
fs.parm("donarrowband").set(1)
fs.parm("narrowbandwidth").setExpression('ch("%sband_vox")' % CT)
fs.parm("limit_sizex").setExpression('ch("%sLx")' % CT)
fs.parm("limit_sizey").setExpression('ch("%sytop") + ch("%sh0") + 2' % (CT, CT))
fs.parm("limit_sizez").setExpression('ch("%sW")' % CT)
fs.parm("limit_tx").setExpression('0.5*ch("%sLx")' % CT)
fs.parm("limit_ty").setExpression('0.5*(ch("%sytop") - ch("%sh0") - 2)' % (CT, CT))
fs.parm("limit_tz").set(0)

mg = dop.createNode("merge", "merge")
mg.setInput(0, so)   # 直し 1：衝突物（海底）を左に置く（左が右に作用する）
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り
rd = obj.createNode("geo", "P0_READ")
for c in rd.children():
    c.destroy()
fi = rd.createNode("dopimportfield::2.0", "surface_field")
fi.parm("doppath").set("/obj/P0_SIM")
fi.parm("fields").set(1)
fi.parm("objname1").set("water")
fi.parm("fieldname1").set("surface")
rd.layoutChildren()

# 確かめ：VDB の値（深い所が負、空気が正）と vel の名前
gsv = vsvdb.geometry()
pv = [p for p in gsv.prims()][0]
print("surface vdb", pv.type(), pv.attribValue("name") if gsv.findPrimAttrib("name") else "?",
      [round(pv.sample(hou.Vector3(300, y, 0)), 3) for y in (-55, -30, -10, -2, 0.5, 5)])
gvv = vvvdb.geometry()
print("vel vdb", [(p.type(), p.attribValue("name") if gvv.findPrimAttrib("name") else "?") for p in gvv.prims()])
hou.hipFile.save(HIP)
print("saved", HIP)
