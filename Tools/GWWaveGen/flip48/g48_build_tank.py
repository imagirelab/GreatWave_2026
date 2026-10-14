# -*- coding: utf-8 -*-
"""FLIP48：3D の尾根と棚の水槽（A 字の盛り上がりの試し。Docs/Progress/FLIP48_3D_Peak_Setup_ja.md）の場面を作り、
Houdini/FLIP48/g48_tank.hiplc に保存する（hython。数十秒。重い計算と重ならないよう x48_build.py から起動する）。
2026-10-15 FLIP46 の g46_build_tank.py（Tools/GWWaveGen/flip46、変えていない）を写して直した。変えた所：
  - 読む道具を g48_tanklib（bedy・bedgrad に棚 shelf_h を足した VEX）と g48_common（置き場所・定数・numpy の bed_z）に。
  - 保存先 Houdini/FLIP48/g48_tank.hiplc。FLIP46 の場面（Houdini/FLIP46/g46_tank.hiplc）には触れない。
  - CTRL の既定：尾根の始まり 143 m、勾配 1:10、k 0（準 2D の板 R0）、棚 shelf_h 1.7 m を足した。箱は x 0〜360 m、横 0〜6 m（R0 の板。
    作った後の確かめの煮込みが軽いように。g48_run.py が cfg の parms で上書きする）。
  - 既定の孤立波：Build/FLIP48/solitary/tanaka_a0p3_x107.npz（g48_cfg.py ready が書く。Tanaka の厳密な解、H0/h0 0.3、頂 x 107 m）。
  - 作った後の確かめを足した：OUT_BED の点の高さと海底の SDF の符号を numpy の g48_common.bed_z・bed_sdf と全部の点で比べる
    （R0 の板 k 0・横 6 m と、R1 の k 0.35・横 85 m の両方）。粒子の数と海底より下の粒子の数も出す。結果は Build/FLIP48/_logs/build_check.json。
  - 2026-10-15 R3 の試し：CTRL に先細り（ridge_kend・ridge_xk1・ridge_xk2）・溝（ch_h・ch_y0・ch_w・ch_x0・ch_lx）・段（ledge_s1・ledge_dl・
    ledge_s2）を足した（既定は無し）。確かめに 2 つ足した：R3 の spur_channel（先細り＋溝、箱の底 −25 m、横 85 m。粒子は 1.0 m で数え、
    numpy の数え方 g48_cfg.count_particles と比べる。谷のある波の表があればそれで）と、G0c の段の板（横 6 m、粒子 0.5 m）。
    確かめの後は CTRL を全部、作った時の既定（R0 の板）に戻してから保存する。
節の名前（G46_SETUP・G46_SIM・G46_READ・G46_SURF）は FLIP46 のまま（g48_run.py との差を小さくするため）。
使い方：py -3.10 x48_build.py（ほかの hython が終わるまで待ってから hython g48_build_tank.py を起動する）
以下は g46_build_tank.py の説明のまま：
FLIP46：3D の尾根の水槽（Guyenne & Grilli 2006 を実物の大きさで。BigWave_Recipes_ja.md §5.2 E1b）の場面を作り、
Houdini/FLIP46/g46_tank.hiplc に保存する（hython 22.0.466。数十秒）。
FLIP45 の g45_build_tank.py（Tools/GWWaveGen/flip45、変えていない）を写して直した。FLIP45 と同じにした所：
  粒子の置き方（粒子の狭い帯なしで水の全体。格子の中心の列に dp ごと、0.2 dp の揺らぎ）、閉じたメッシュから作る初めの水面の VDB、
  FLIP Solver 2.0・APIC・格子 = 粒子 × 2・圧力の前処理 IC、各コマの小刻みの数を記録する Geometry Wrangle、CTRL の値は parm.set で入れる、
  壁は格子の面（Houdini = 計画 + o）、上は開く、面（R5）を作る SOP の道、読み取りの道。
変えた所：
  - 帯を全部外した（入口の帯・横の帯・出口の帯。閉じた水槽で、孤立波を初めの状態に置くだけ）。入口の表も外した。
  - 海底：FLIP44 の g44_build_tank.py と同じ作り（海底の SDF を Static Object の体積 collision で、merge の左＝入力 0 に seabed、
    右＝入力 1 に FLIP Solver）。形は尾根（g46_tanklib.bedy）。平らな所（x ≤ 88.825 m）は −17 m。箱の底（閉じた壁）は CTRL の floor_pad
    格子だけ下げる（既定 2：FLIP44 と同じく海底を全部 SDF で。0 では尾根の始まりの海底が箱の底から格子 1 個以内の所で粒子が海底の下へ入った。
    2026-10-12 の煙の試し）。
  - 初めの状態：孤立波の解の npz（CTRL の sol_npz。既定は Tanaka の厳密な解 solitary/tanaka_a0p6.npz、GN は選び）を Python SOP solution_table が体積 eta・u・w にする（OUT_SOL）。
    粒子は海底（＋ bed_gap × dp）と水面 η(x) の間だけに置き、解の流速を持たせる。初めの水面の VDB は η(x) の閉じたメッシュから。
    初めの格子の流速（OUT_VEL）にも解の流速を入れる（FLIP37 の誤り：深い格子の流速が 0 から始まった）。wave_on 0 なら静かな水。
使い方：hython g46_build_tank.py
"""
import hou, os, sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip46")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48")
import importlib, numpy as np, g48_tanklib as L, g48_common as GC
importlib.reload(L); importlib.reload(GC)

HIP = GC.HIP
CT = L.CT
B0 = GC.box(0.5, Lx=GC.LX, W=GC.W_STRIP, floor_pad=2)      # R0 の板（作った後の確かめの煮込みが軽い）

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G46_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    # 箱と解き方（既定は粒子 0.5 m の下見。g46_run.py が cfg の parms で上書きする）
    ("dp", 0.5, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("x0", 0.0, "箱の上流の壁 x0 (m)"),
    ("Lx", B0["Lx"], "箱の長さ x (m)（格子の倍数）"),
    ("W", B0["W"], "箱の横の幅 z 0〜W (m)（格子の倍数）"),
    ("zb", GC.Z_BOTTOM, "箱の底（平らな所の海底）(m)"),
    ("Hz", B0["Hz"], "箱の高さ（底から）(m)（格子の倍数）"),
    ("h0", GC.H0, "水深 h0 (m)"),
    ("maxsub", 8.0, "FLIP の最大小刻み"),
    ("minsub", 1.0, "FLIP の最小小刻み"),
    ("cfl", 1.0, "CFL Condition（cflcond）"),
    ("pcfl", 0.75, "Particle Advection CFL（partcflcond）"),
    ("t_off", 0.0, "コマ 1 の時刻 (s)"),
    ("ox", B0["ox"], "Houdini の x = 計画の x + ox（壁を格子の面に置くずらし。g46_common.box）"),
    ("oy", B0["oy"], "Houdini の上 y = 計画の z + oy（静かな水面は Houdini の y = oy）"),
    ("oz", B0["oz"], "Houdini の横 z = 計画の y + oz（対称の面は Houdini の z = oz）"),
    # 尾根と初めの波
    ("ridge_on", 1.0, "尾根（1 で置く、0 で平らな海底）"),
    ("ridge_x0", GC.RIDGE_X0, "尾根の始まり x (m)（FLIP48 は 143 m）"),
    ("ridge_k", 0.0, "尾根の横の変化 sech²(k y') の k（既定 0 = 横に一様な準 2D の板 R0。R1 は 0.35）"),
    ("ridge_s", GC.RIDGE_S, "真ん中の断面の勾配 1:s の s（FLIP48 は 10）"),
    ("shelf_h", GC.SHELF_H, "棚の水深 m（水深をこれより浅くしない。0 なら FLIP46 の尾根。FLIP48 は 1.7 = 0.1 h0）"),
    # R3 の試し（plan/campaign_R3_judge.json）の選び。既定は全部「無し」（R0〜R2b と同じ海底）
    ("ridge_kend", -1.0, "R3：尾根の k の先細りの終わりの k（< 0 で無し。R3 は 1.0）"),
    ("ridge_xk1", 240.0, "R3：先細りの始まり x (m)"),
    ("ridge_xk2", 296.0, "R3：先細りの終わり x (m)"),
    ("ch_h", 0.0, "R3：横の遠くの溝の水深 m（0 で無し。R3 は 25）"),
    ("ch_y0", 55.0, "R3：溝の壁の真ん中の横の位置 |y| (m)"),
    ("ch_w", 4.0, "R3：溝の壁の tanh の幅 (m)"),
    ("ch_x0", 150.0, "R3：溝が始まる x (m)"),
    ("ch_lx", 40.0, "R3：溝が深くなりきるまでの x の長さ (m)"),
    ("ledge_s1", 0.0, "G0c・R3L：段の前後の勾配 1:s1 の s1（0 で段無し。G0c は 11.2）"),
    ("ledge_dl", 0.0, "G0c・R3L：段の高さ dL (m)（G0c は 2.8）"),
    ("ledge_s2", 0.0, "G0c・R3L：段の勾配 1:s2 の s2（G0c は 4）"),
    ("bed_gap", 0.5, "海底の上の粒子を置かない厚さ（dp の倍数。FLIP44 と同じ 0.5）"),
    ("floor_pad", 2.0, "箱の底を平らな海底 zb より何格子下げるか（0 = 箱の底が海底：FLIP45 と同じ。2 = FLIP44 と同じく海底を全部 SDF で。既定 2）"),
    ("wave_on", 1.0, "孤立波（1 で npz の解、0 で静かな水）"),
    ("side_pad", 0.0, "対称の面 y = 0 を SDF の壁にし、箱の横の下の端をこの格子の数だけ外へ（0 = 箱の壁：前の作り。2026-10-12 統合の役の選び）"),
    # 面（R5）
    ("surf_layer_m", 2.5, "面を作る粒子：水面からこの深さより下を除く (m)（0 なら水の全体）"),
    ("mirror_m", 1.0, "対称の面から写す粒子の幅 (m)"),
    ("surf_vox_scale", 1.0, "Particle Fluid Surface の Voxel Scale"),
    ("crop_x0", 0.0, "面を切り出す x の始め (m)"),
    ("crop_x1", B0["Lx"], "面を切り出す x の終わり (m)"),
    ("crop_z1", B0["W"], "面を切り出す横の終わり (m)"),
    ("surf_ycut", -15.0, "これより下の面（底・壁）を除く y (m)"),
    ("surf_keep_vox", 1.0, "FLIP の水面の場からこの格子の数より離れた三角形を除く"),
    ("surf_bed_vox", 0.5, "海底からこの格子の数より近い三角形を除く（海底に沿う面。0 で除かない。2026-10-12 統合の役）"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
# 既定の孤立波：Tanaka の厳密な解（g46_solitary.write_grid）。なければ GN の代わり。GN は cfg の solitary_npz（g46_cfg.py --wave gn）で選べる
# （2026-10-12 統合の役。g46_run.py は cfg の solitary_npz をここに入れるので、既定は場面を手で開いた時の物）
SOL_DEFAULT = GC.SOL_DEFAULT          # FLIP48：Tanaka の厳密な解 H0/h0 0.3、頂 x 107 m（g48_cfg.py ready が書く。なければ確かめの煮込みで止まる）
ptg.append(hou.StringParmTemplate("sol_npz", "孤立波の解の npz（x・z・eta・u・w・c・x0・h0）", 1, default_value=(SOL_DEFAULT,)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(GC.B48 + "/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(240,)))
ctrl.setParmTemplateGroup(ptg)
for nm, dv, lb in PARMS:
    ctrl.parm(nm).set(dv)
ctrl.parm("sol_npz").set(SOL_DEFAULT)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

# ---------------------------------------------------------------- 孤立波の解の表（npz → 体積 eta・u・w）
sol = setup.createNode("python", "solution_table")
sptg = sol.parmTemplateGroup()
sptg.append(hou.StringParmTemplate("npz", "npz", 1, default_value=("",)))
sptg.append(hou.FloatParmTemplate("wave_on", "wave_on", 1, default_value=(1.0,)))
sptg.append(hou.FloatParmTemplate("h0", "h0", 1, default_value=(GC.H0,)))
sol.setParmTemplateGroup(sptg)
sol.parm("npz").set('`chs("%ssol_npz")`' % CT)
sol.parm("wave_on").setExpression('ch("%swave_on")' % CT)
sol.parm("h0").setExpression('ch("%sh0")' % CT)
sol.parm("python").set(L.PYSOP)
solout = setup.createNode("null", "OUT_SOL")
solout.setInput(0, sol)

# ---------------------------------------------------------------- 海底（表示と静的物体の形。衝突は下の SDF で）
PADE = 'ch("%sfloor_pad")*%s' % (CT, VOXE)          # 箱の底の下げ (m)
SPADE = 'ch("%sside_pad")*%s' % (CT, VOXE)          # 箱の横の下の端の外し (m)（side_pad。0 なら前と同じ）
BOXC = dict(sx='ch("%sLx")' % CT, sy='ch("%sHz") + %s' % (CT, PADE), sz='ch("%sW") + %s' % (CT, SPADE),
            tx='ch("%sx0") + 0.5*ch("%sLx") + ch("%sox")' % (CT, CT, CT),
            ty='ch("%szb") - %s + 0.5*(ch("%sHz") + %s) + ch("%soy")' % (CT, PADE, CT, PADE, CT),
            tz='0.5*(ch("%sW") - %s) + ch("%soz")' % (CT, SPADE, CT))
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)               # ZX（水平）
bgrid.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bgrid.parm("sizey").setExpression('ch("%sW") + 12' % CT)
bgrid.parm("rows").setExpression('int(ch("%sLx") + 20) + 1' % CT)
bgrid.parm("cols").setExpression('int(ch("%sW") + 12) + 1' % CT)
bgrid.parm("tx").setExpression(BOXC["tx"])
bgrid.parm("ty").setExpression('ch("%soy")' % CT)
bgrid.parm("tz").setExpression(BOXC["tz"])
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(L.snippet("/obj/G46_SETUP/bed_height"))
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
bsdfw.parm("snippet").set(L.snippet("/obj/G46_SETUP/bed_sdf_value"))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- 初めの粒子（海底と孤立波の水面の間の全部。解の流速）
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
pts0.parm("class").set(2)       # points
pts0.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float zb = ch(CT+"zb");
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
int c = i@col;
vector pc = @P - o;                                   // 列の計画の座標（x, 0, 横）
float e = sol_eta(pc.x);
float ylo = bedy(pc.x, pc.z) + chf(CT+"bed_gap")*dp;  // 海底の上 bed_gap × dp より上だけ（FLIP44 と同じ）
for (int k = 0; k < 100000; k++) {
    float y = zb + (k + 0.5)*dp;                      // 格子の中心の段（静かな水なら −0.5 dp がいちばん上。FLIP45 と同じ段）
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

# 水の塊の閉じたメッシュ（上の面 = 孤立波の水面 η(x)。格子の半分ごと）→ VDB の SDF
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
vvw.parm("snippet").set(L.snippet("/obj/G46_SETUP/vel_value"))
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G46_SIM")
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
fo.parm("surfacetype").set("4")  # Narrow Band の入力（g46_run.py が donarrowband を 0 にする。FLIP44・45 と同じ）
fo.parm("soppath").set("/obj/G46_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G46_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G46_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/G46_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/G46_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

ssc = dop.createNode("geometrywrangle", "substep_count")
ssc.parm("bindclass").set("detail")
ssc.parm("snippet").set(L.BODIES["/obj/G46_SIM/substep_count"])
ssc.parm("exportlist").set("ss_acc ss_n ss_dt")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(1, ssc)
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
fs.parm("limit_sizex").setExpression(BOXC["sx"])
fs.parm("limit_sizey").setExpression(BOXC["sy"])
fs.parm("limit_sizez").setExpression(BOXC["sz"])
fs.parm("limit_tx").setExpression(BOXC["tx"])
fs.parm("limit_ty").setExpression(BOXC["ty"])
fs.parm("limit_tz").setExpression(BOXC["tz"])

mg = dop.createNode("merge", "merge")        # 海底を merge の左（FLIP40〜44 と同じ順）
mg.setInput(0, so)
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り（水面の場、流速の場、衝突の場）
rd = obj.createNode("geo", "G46_READ")
for c in rd.children():
    c.destroy()
for nm in ("surface", "vel", "collision"):
    fi = rd.createNode("dopimportfield::2.0", nm + "_field")
    fi.parm("doppath").set("/obj/G46_SIM")
    fi.parm("fields").set(1)
    fi.parm("objname1").set("water")
    fi.parm("fieldname1").set(nm)
rd.layoutChildren()

# ---------------------------------------------------------------- 面（記録 R5。FLIP45 と同じ道）
sf = obj.createNode("geo", "G46_SURF")
for c in sf.children():
    c.destroy()
di = sf.createNode("dopimport", "particles")
di.parm("doppath").set("/obj/G46_SIM")
di.parm("objpattern").set("water")
sfield = sf.createNode("object_merge", "surface_field")
sfield.parm("objpath1").set("/obj/G46_READ/surface_field")
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
# 2026-10-12 統合の役：海底に沿う面（尾根の上で、海底のすぐ上の粒子が面を作る層に残り、海底に沿って閉じた面ができていた。粒子 0.5 m の
# 3 s で三角形の 43 % が海底から −0.3〜+0.25 m）を、海底から surf_bed_vox 格子より近い三角形として除く（R5 を水面だけにする）
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

# ---------------------------------------------------------------- 作った物を一度だけ確かめる（粒子 0.5 m の既定で）
for n in (sol, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
    try:
        n.cook(force=True)
    except Exception as e:
        print("COOK ERROR", n.path(), str(e)[:400])
    if n.errors():
        print("ERR", n.path(), n.errors())
print("gravity", [(p.name(), p.eval()) for p in gr.parms() if p.name().startswith("force")])
g = solout.geometry()
print("solution", g.attribValue("src") if g else None, [(a.name(), g.attribValue(a.name())) for a in g.globalAttribs()][:12] if g else None)
g = bedout.geometry()
print("bed bbox", g.boundingBox() if g else None)
g = ptsout.geometry()
print("particles", g.intrinsicValue("pointcount") if g else None, "bbox", g.boundingBox() if g else None)
g = vvout.geometry()
print("vel prims", [(p.attribValue("name"), p.resolution()) for p in g.prims()] if g else None)
g = bsdfout.geometry()
print("bed sdf prims", [(p.attribValue("name"), p.resolution()) for p in g.prims()] if g else None)
print("solver inputs", fs.inputLabels())


# ---------------------------------------------------------------- FLIP48：海底を numpy の式と比べる（g48_common.bed_z・bed_sdf）
def ctrl_floats():
    return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}


def bed_check(tag):
    """OUT_BED の点の高さと、SDF（collision）の符号・値を numpy と比べる。CTRL の今の値で（R3 の先細り・溝・段も g48_common.bed_spec で読む）。"""
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
    out["bed_points"] = int(len(Pp)); out["bed_max_abs_dz_m"] = float(np.abs(d).max()); out["bed_ok"] = bool(np.abs(d).max() < 0.01)
    out["bed_min_depth_m"] = float(-zb.max()); out["bed_max_depth_m"] = float(-zb.min()); out["bed_x_range"] = [float(Pp[:, 0].min()), float(Pp[:, 0].max())]
    out["box_floor_m"] = float(P_["zb"]) - float(P_["floor_pad"]) * float(P_["dp"]) * float(P_["gridscale"])
    out["deepest_bed_above_box_floor_m"] = float(zb.min()) - out["box_floor_m"]
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
        out["sdf_y_range"] = [float(ys[0]), float(ys[-1])]
        Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
        ref = GC.bed_sdf(X, Y, Z, **spec)
        if float(P_.get("side_pad", 0.0)) > 0.5:
            ref = np.minimum(ref, Z)
        near = np.abs(ref) < 3.0
        out["sdf_res"] = list(r); out["sdf_max_abs_diff_near_m"] = float(np.abs(a - ref)[near].max()) if near.any() else None
        out["sdf_sign_mismatch_frac"] = float(np.mean(np.sign(a[np.abs(ref) > 0.05]) != np.sign(ref[np.abs(ref) > 0.05])))
        out["sdf_ok"] = bool(out["sdf_max_abs_diff_near_m"] is not None and out["sdf_max_abs_diff_near_m"] < 0.02 and out["sdf_sign_mismatch_frac"] == 0.0)
        # 箱の底（zb − floor_pad 格子）より下まで SDF の体積があるか（溝の海底 −25 m の下にも 2 格子の固い所）
        out["sdf_covers_box_floor"] = bool(ys[0] <= out["box_floor_m"] + 1e-6)
    return out


def particle_check(rec, spec, eta_fn=None):
    """OUT_PARTICLES を煮込み、粒子の数・海底より下の粒子・numpy の数え方（g48_cfg.count_particles）との比を rec に足す。"""
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
    rec["gap_min_m"] = float(gap.min()); rec["z_min_m"] = float(Pp[:, 1].min()); rec["z_max_m"] = float(Pp[:, 1].max())
    rec["sol_npz"] = ctrl.parm("sol_npz").evalAsString()
    sg = solout.geometry()
    rec["sol_src"] = sg.attribValue("src") if sg is not None else None
    try:
        import g48_cfg as CF
        ef = eta_fn or CF.eta_from_npz(rec["sol_npz"])
        n_model, V = CF.count_particles(spec, float(P_["Lx"]), float(P_["W"]), float(P_["dp"]), ef, zb=float(P_["zb"]),
                                        bed_gap=float(P_["bed_gap"]))
        rec["particles_model"] = int(n_model); rec["particles_ratio_houdini_over_model"] = float(len(Pp)) / max(n_model, 1)
        # 古い数え方（箱の底 −17 m）で数えると溝の −17 m より下の粒子を落とす（count_particles に zb を渡す理由の確かめ）
        n17, _ = CF.count_particles(spec, float(P_["Lx"]), float(P_["W"]), float(P_["dp"]), ef, zb=GC.Z_BOTTOM, bed_gap=float(P_["bed_gap"]))
        rec["particles_model_if_zb_minus17"] = int(n17)
    except Exception as e:
        rec["particles_model_error"] = repr(e)[:300]
    return rec


CHK = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=HIP, houdini=hou.applicationVersionString(), module_shas=GC.module_shas())
DEFAULT_CTRL = ctrl_floats()
DEFAULT_SOL = ctrl.parm("sol_npz").evalAsString()


def set_ctrl(d):
    for nm, v in d.items():
        ctrl.parm(nm).set(v)


def restore_ctrl():
    set_ctrl(DEFAULT_CTRL)
    ctrl.parm("sol_npz").set(DEFAULT_SOL)


try:
    CHK["default_R0"] = bed_check("R0 の板（k 0・横 6 m・棚 1.7 m）")
    g = ptsout.geometry()
    if g is not None:
        Pp = np.frombuffer(g.pointFloatAttribValuesAsString("P"), dtype=np.float32).reshape(-1, 3).astype(np.float64) - np.array(
            [ctrl.parm("ox").eval(), ctrl.parm("oy").eval(), ctrl.parm("oz").eval()])
        sp_ = CHK["default_R0"]["spec"]
        gap = Pp[:, 1] - GC.bed_z(Pp[:, 0], Pp[:, 2], **sp_)
        CHK["default_R0"]["particles"] = int(len(Pp)); CHK["default_R0"]["n_below_bed"] = int((gap < 0).sum())
        CHK["default_R0"]["gap_min_m"] = float(gap.min()); CHK["default_R0"]["z_max_m"] = float(Pp[:, 1].max())
    b85 = GC.box48(0.5, Lx=GC.LX, W=GC.W_MAIN, floor_pad=2)
    set_ctrl(dict(ridge_k=GC.RIDGE_K, W=b85["W"], crop_z1=b85["W"]))
    CHK["R1"] = bed_check("R1（k 0.35・横 85 m・棚 1.7 m）")
    restore_ctrl()
    # R3 の spur_channel：先細り k 0.35 → 1.0（x 240〜296 m）＋横の遠くの溝（|y| ≳ 55 m を 25 m、x 150〜190 m）、箱の底 −25 m
    sp3 = dict(GC.bed_spec(parms=DEFAULT_CTRL), k=GC.RIDGE_K, **GC.TAPER_R3, **GC.CHANNEL_R3)
    b3 = GC.box48(0.5, Lx=GC.LX, W=GC.W_MAIN, zb=GC.ZB_DEEP, floor_pad=2)
    set_ctrl(dict(ridge_k=GC.RIDGE_K, W=b3["W"], crop_z1=b3["W"], zb=b3["z_bottom"], Hz=b3["Hz"], ox=b3["ox"], oy=b3["oy"], oz=b3["oz"],
                  **GC.bed_parms(sp3)))
    CHK["R3_spur_channel"] = bed_check("R3 spur_channel（先細り k 0.35→1.0・溝 25 m・横 85 m・箱の底 −25 m、粒子 0.5 m の格子で）")
    CHK["R3_spur_channel"]["box48"] = {k: b3[k] for k in ("Lx", "W", "z_bottom", "z_top", "Hz", "z_floor", "cells", "ox", "oy", "oz")}
    # 粒子は 1.0 m で数える（0.5 m の 500 万粒は確かめには重い）。谷のある波の表があればそれで（solution_table が読めるかの確かめも兼ねる）
    b3s = GC.box48(1.0, Lx=GC.LX, W=GC.W_MAIN, zb=GC.ZB_DEEP, floor_pad=2)
    set_ctrl(dict(dp=1.0, Lx=b3s["Lx"], W=b3s["W"], crop_x1=b3s["Lx"], crop_z1=b3s["W"], Hz=b3s["Hz"], ox=b3s["ox"], oy=b3s["oy"], oz=b3s["oz"]))
    nw = GC.nwave_path()
    if os.path.exists(nw):
        ctrl.parm("sol_npz").set(nw)
    CHK["R3_spur_channel_particles_dp1"] = particle_check(dict(box48={k: b3s[k] for k in ("Lx", "W", "z_bottom", "Hz", "ox", "oy", "oz")}),
                                                          GC.bed_spec(parms=ctrl_floats()))
    restore_ctrl()
    # G0c の段の板：1:11.2 で 4.5 m（x 283.0）、1:4 の段 2.8 m で棚 1.7 m（x 294.2）、k 0、横 6 m、粒子 0.5 m
    set_ctrl(dict(ridge_k=0.0, ledge_s1=GC.LEDGE_G0C["s1"], ledge_dl=GC.LEDGE_G0C["dL"], ledge_s2=GC.LEDGE_G0C["s2"]))
    CHK["G0c_ledge_strip"] = bed_check("G0c の段の板（k 0・横 6 m・1:11.2 → 1:4 の段 2.8 m → 棚 1.7 m）")
    spL = GC.bed_spec(parms=ctrl_floats())
    CHK["G0c_ledge_strip"]["axis_depth_at"] = {str(x_): float(-GC.bed_z(x_, 0.0, **spL)) for x_ in (143.0, 200.0, 283.0, 290.0, 294.2, 300.0)}
    CHK["G0c_ledge_strip"]["shelf_x_axis"] = GC.shelf_x(spL, 0.0)
    particle_check(CHK["G0c_ledge_strip"], spL)
    restore_ctrl()
    bw.cook(force=True); bsdfw.cook(force=True)
    for n in (sol, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and ctrl.parm("sol_npz").evalAsString() == DEFAULT_SOL)
except Exception as e:
    import traceback
    CHK["error"] = repr(e)[:400]
    CHK["traceback"] = traceback.format_exc()[-2000:]
    try:
        restore_ctrl()
    except Exception:
        pass
KEYS = ("default_R0", "R1", "R3_spur_channel", "G0c_ledge_strip")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") for k in KEYS)
                     and (CHK.get("R3_spur_channel") or {}).get("sdf_covers_box_floor")
                     and (CHK.get("R3_spur_channel_particles_dp1") or {}).get("n_below_bed") == 0
                     and (CHK.get("G0c_ledge_strip") or {}).get("n_below_bed") == 0
                     and CHK.get("restored_ctrl_equal_default"))
print("BED_CHECK", json.dumps(CHK, ensure_ascii=False, default=str))
os.makedirs(GC.B48 + "/_logs", exist_ok=True)
json.dump(CHK, open(GC.B48 + "/_logs/build_check.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
print("saved", HIP)
