# -*- coding: utf-8 -*-
"""FLIP47：2D の板の水槽（海底は折れ線、孤立波を初めの状態に置く）の場面を作り、Houdini/FLIP47/g47_tank.hiplc に保存する（hython。数十秒）。
計画：BigWave_Recipes_ja.md §5.1 E1a（Feddersen ら 2024 を h0 19 m に）。FLIP44 の g44_build_tank.py（板の水槽）と FLIP46 の g46_build_tank.py
（孤立波の熱い始め）を写して直した（どちらも変えていない）。同じにした所：
  板の厚さは格子 4 個、両面は閉じた壁（滑る）、上は開く。FLIP Solver 2.0・APIC・格子 = 粒子 × 2・圧力の前処理 IC、粒子の狭い帯なし（水の全体）、
  海底の SDF を Static Object の体積 collision で（merge の左＝入力 0 に seabed、右＝入力 1 に FLIP Solver）、箱の底はいちばん深い所より
  floor_pad 格子下（既定 2）、各コマの小刻みの数の Geometry Wrangle、CTRL の値は parm.set で入れる（既定値は 6 桁に丸められる）、
  壁を格子の面に置くずらし o（Houdini = 計画 + o。FLIP45 の読み方 R1）。
変えた所：
  - 海底：折れ線（CTRL の bed_prof → OUT_BEDTAB）。衝突の SDF は折れ線への本当の距離。
  - 初めの状態：孤立波の解の npz（CTRL の sol_npz）→ Python SOP solution_table → 体積 eta・u・w（OUT_SOL）。粒子は海底（＋ bed_gap × dp）と
    水面 η(x) の間だけに、解の流速を持たせて置く（列ごとに dp の段、段は −hmax + (k + ½) dp、0.2 dp の揺らぎ）。初めの水面の VDB は η(x) の
    閉じたメッシュから。初めの格子の流速（OUT_VEL）にも解の流速を入れる（FLIP37 の誤り：深い格子の流速が 0 から始まった）。wave_on 0 なら静かな水。
  - 入口の帯（FLIP44 の入口の表に寄せる緩和）・吸う帯（スポンジ）は場面に入れ、CTRL の relax_on・abs_on（既定 0）で切ってある。
  - 風の道具・表面張力は入れない（重力だけ）。
使い方：hython g47_build_tank.py
  2026-10-13 周期の波の実験の役が足した（引数なしなら前と同じ物を g47_tank.hiplc に作る）：
  hython g47_build_tank.py --periodic [--out=<hiplc>]   周期の波の場面（既定 Houdini/FLIP47/g47_tank_periodic.hiplc）。前の場面に、
     CTRL の sf_on（既定 0）・relax_w（0）・set_P（0）・set_up・set_flat・set_down（0）・文字の sf_tab、流れ関数の表 sf_table → OUT_SF、
     入口の帯の wrangle を relax_zones_sf（sf_on 0 なら relax_zones と同じ式）にした物。--periodic のとき g47_tank.hiplc には書かない。
"""
import hou, os, sys
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip47")
import importlib, g47_tanklib as L, g47_common as GC
importlib.reload(L); importlib.reload(GC)

PERIODIC = "--periodic" in sys.argv[1:]
_outs = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--out=")]
HIP = _outs[0] if _outs else (GC.REPO + "/Houdini/FLIP47/g47_tank_periodic.hiplc" if PERIODIC else GC.HIP)
if PERIODIC and os.path.abspath(HIP).lower() == os.path.abspath(GC.HIP).lower():
    raise SystemExit("--periodic の場面を g47_tank.hiplc に書かない（ほかの役が使う）")
CT = L.CT
B0 = GC.box(0.5, 0.0, GC.X_END_FULL, GC.BED_E1A)

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G47_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
PARMS = [
    # 箱と解き方（既定は E1a の全部の領域・粒子 0.5 m。g47_run.py が cfg の parms で上書きする）
    ("dp", 0.5, "粒子の間隔 dp (m)"),
    ("gridscale", 2.0, "Grid Scale（格子 = dp × これ）"),
    ("x0", B0["x0"], "箱の上流の壁 x0 (m)"),
    ("Lx", B0["Lx"], "箱の長さ x (m)（格子の倍数）"),
    ("Lz", B0["Lz"], "板の厚さ (m)（格子 4 個。z −Lz/2〜+Lz/2）"),
    ("y_floor", B0["y_floor"], "箱の底 y (m)（いちばん深い所より floor_pad 格子下）"),
    ("Hy", B0["Hy"], "箱の高さ（底から）(m)（格子の倍数）"),
    ("h0", GC.H0, "沖の水深 h0 (m)（解の表の無次元の倍率・入口の帯の水深）"),
    ("hmax", B0["hmax"], "いちばん深い水深 (m)（粒子の段の基準 −hmax）"),
    ("maxsub", 8.0, "FLIP の最大小刻み"),
    ("minsub", 1.0, "FLIP の最小小刻み"),
    ("cfl", 1.0, "CFL Condition（cflcond）"),
    ("pcfl", 0.75, "Particle Advection CFL（partcflcond）"),
    ("t_off", 0.0, "コマ 1 の時刻 (s)（記録だけ。Houdini の時刻はコマ 1 が 0）"),
    ("ox", B0["ox"], "Houdini の x = 計画の x + ox"),
    ("oy", B0["oy"], "Houdini の y = 計画の y + oy（静かな水面は Houdini の y = oy）"),
    ("oz", B0["oz"], "Houdini の z = 計画の z + oz（板の真ん中は Houdini の z = oz）"),
    ("bed_gap", 0.5, "海底の上の粒子を置かない厚さ（dp の倍数。FLIP44・46 と同じ 0.5）"),
    ("floor_pad", 2.0, "箱の底をいちばん深い所より何格子下げたか（記録。箱は y_floor・Hy で決まる）"),
    ("wave_on", 1.0, "孤立波（1 で npz の解、0 で静かな水）"),
    # 入口の帯・吸う帯（FLIP44 と同じ式。既定は切る）
    ("relax_on", 0.0, "入口の帯（1 で入口の表へ寄せる。既定 0）"),
    ("abs_on", 0.0, "吸う帯（1 でスポンジ。既定 0）"),
    ("x_p", 0.0, "造波板の位置 x_p (m)（入口の表の位相の基準）"),
    ("xg_end", 0.0, "入口の帯の終わり x (m)"),
    ("relax_g", 1.0, "入口の帯の強さ"),
    ("dt0", 1.0 / 24.0, "帯の重みの基準の刻み dt0 (s)"),
    ("ramp_s", 10.0, "始めのなだらかさ (s)"),
    ("wall_taper_m", 30.0, "入口の目標を上流の壁の近くで 0 へ落とす長さ (m)"),
    ("amp_gain", 1.0, "入口の振幅に掛ける数"),
    ("rep_P", 0.0, "繰り返しの入口の周期 P (s)。0 なら t をそのまま"),
    ("xa0", 1e9, "吸う帯の始まり x (m)"),
    ("abs_sigma", 0.8, "スポンジの σmax (1/s)"),
    ("abs_pow", 2.0, "スポンジの強さの増え方 χ^p の p"),
]
if PERIODIC:      # 周期の波の場面だけ（既定は前と同じ式になる値）
    PARMS += [
        ("sf_on", 0.0, "入口の帯の目標を流れ関数の波に（1）。0 なら入口の表（groupwave）"),
        ("relax_w", 0.0, "鉛直の流速も寄せる（1）。0 なら水平だけ（前と同じ）"),
        ("set_P", 0.0, "組の周期 P (s)。0 なら包絡なし（1）"),
        ("set_up", 0.0, "組の上り (s)（余弦）"),
        ("set_flat", 0.0, "組の満ち (s)"),
        ("set_down", 0.0, "組の下り (s)（余弦）"),
        ("volcorr_on", 0.0, "水の体積の直し（1）。0 なら目標の発散なし（前と同じ）"),
        ("vol_tau", 4.0, "体積の直しの時定数 (s)"),
        ("vol_dmax", 0.002, "目標の発散の上限 (1/s)"),
        ("vol_tcap", 1.5, "体積の基準 V0 を取る時刻 (s)（この時刻までの V）"),
        ("vol_mode", 0.0, "体積の直しの形：0 水の全部の体積を V0 に、1 帯の時間の平均の水面を静かな水面に（vol_x0〜vol_x1 だけに発散）"),
        ("vol_x0", 0.0, "直しの発散を置く範囲の始め x (m)（vol_x1 > vol_x0 の時だけ使う）"),
        ("vol_x1", 0.0, "直しの発散を置く範囲の終わり x (m)"),
        ("vol_avg_s", 14.0, "vol_mode 1：平均の水面の動く平均の長さ (s)"),
        ("vol_ti", 30.0, "vol_mode 1：積分の時定数 (s)"),
    ]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
if PERIODIC:
    ptg.append(hou.StringParmTemplate("sf_tab", "流れ関数の表（h k c Ub N B1..BN E0..EN）", 1, default_value=("",)))
    ptg.append(hou.StringParmTemplate("vol_dir", "体積の直しの目標の発散のファイルの置き場所（g47_run.py が書く。空なら 0）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("bed_prof", "海底の折れ線（x0 d0 x1 d1 ...、d は水深 m）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("sol_npz", "孤立波の解の npz（x・z・eta・u・w・c・x0・h0）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("inlet_tab", "入口の表（成分ごとに f a φ k）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1, default_value=(GC.B47 + "/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(240,)))
ctrl.setParmTemplateGroup(ptg)
for nm, dv, lb in PARMS:          # 既定値は 6 桁に丸められるので、値は set で入れる
    ctrl.parm(nm).set(dv)
ctrl.parm("bed_prof").set(GC.bed_string(GC.BED_E1A))
_default_sol = GC.SOL_DIR + "/gn_a0.60_h19_x285_d0.25.npz"
ctrl.parm("sol_npz").set(_default_sol)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)
BOXC = dict(sx='ch("%sLx")' % CT, sy='ch("%sHy")' % CT, sz='ch("%sLz")' % CT,
            tx='ch("%sx0") + 0.5*ch("%sLx") + ch("%sox")' % (CT, CT, CT),
            ty='ch("%sy_floor") + 0.5*ch("%sHy") + ch("%soy")' % (CT, CT, CT),
            tz='ch("%soz")' % CT)

# ---------------------------------------------------------------- 海底の表・解の表・入口の表
btab = setup.createNode("attribwrangle", "bed_table")
btab.parm("class").set(0)
btab.parm("vex_precision").set("64")
btab.parm("snippet").set(L.snippet("/obj/G47_SETUP/bed_table"))
btabout = setup.createNode("null", "OUT_BEDTAB")
btabout.setInput(0, btab)

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

itab = setup.createNode("attribwrangle", "inlet_table")
itab.parm("class").set(0)
itab.parm("vex_precision").set("64")
itab.parm("snippet").set(L.snippet("/obj/G47_SETUP/inlet_table"))
itabout = setup.createNode("null", "OUT_INLET")
itabout.setInput(0, itab)
if PERIODIC:
    sftab = setup.createNode("attribwrangle", "sf_table")
    sftab.parm("class").set(0)
    sftab.parm("vex_precision").set("64")
    sftab.parm("snippet").set(L.snippet_sf("/obj/G47_SETUP/sf_table"))
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

# ---------------------------------------------------------------- 海底（表示と静的物体の形。衝突は下の SDF で）
bgrid = setup.createNode("grid", "bed_grid")
bgrid.parm("orient").set(2)               # ZX（水平）。FLIP44 と同じ置き方
bgrid.parm("sizex").setExpression('ch("%sLx") + 20' % CT)
bgrid.parm("sizey").setExpression('ch("%sLz") + 8' % CT)
bgrid.parm("rows").setExpression('int((ch("%sLx") + 20)/0.5) + 1' % CT)
bgrid.parm("cols").set(3)
bgrid.parm("tx").setExpression(BOXC["tx"])
bgrid.parm("ty").setExpression('ch("%soy")' % CT)
bgrid.parm("tz").setExpression(BOXC["tz"])
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.setInput(2, btabout)
bw.parm("snippet").set(L.snippet("/obj/G47_SETUP/bed_height"))
bedout = setup.createNode("null", "OUT_BED")
bedout.setInput(0, bw)

bsdf = setup.createNode("volume", "bed_sdf")
bsdf.parm("name").set("collision")
bsdf.parm("rank").set("scalar")
bsdf.parm("uniformsamples").set("size")
bsdf.parm("divsize").setExpression(VOXE)
bsdf.parm("sizex").setExpression('ch("%sLx") + 12*%s' % (CT, VOXE))
bsdf.parm("sizey").setExpression('ch("%sHy") + 12*%s' % (CT, VOXE))
bsdf.parm("sizez").setExpression('ch("%sLz") + 12*%s' % (CT, VOXE))
bsdf.parm("tx").setExpression(BOXC["tx"])
bsdf.parm("ty").setExpression(BOXC["ty"])
bsdf.parm("tz").setExpression(BOXC["tz"])
bsdfw = setup.createNode("volumewrangle", "bed_sdf_value")
bsdfw.setInput(0, bsdf)
bsdfw.setInput(2, btabout)
bsdfw.parm("snippet").set(L.snippet("/obj/G47_SETUP/bed_sdf_value"))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- 初めの粒子（海底と孤立波の水面の間の全部。解の流速）
cols = setup.createNode("attribwrangle", "particle_columns")
cols.parm("class").set(0)
cols.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float Lz = ch(CT+"Lz");
int nx = int(floor(Lx/dp + 1e-6)); int nz = int(floor(Lz/dp + 1e-6));
for (int iz = 0; iz < nz; iz++)
    for (int ix = 0; ix < nx; ix++) {
        int p = addpoint(0, set(x0 + (ix + 0.5)*dp + chf(CT+"ox"), 0.0, -0.5*Lz + (iz + 0.5)*dp + chf(CT+"oz")));
        setpointattrib(0, "col", p, iz*nx + ix);
    }
""")
pts0 = setup.createNode("attribwrangle", "init_particles")
pts0.setInput(0, cols)
pts0.setInput(1, solout)
pts0.setInput(2, btabout)
pts0.parm("class").set(2)
pts0.parm("snippet").set(L.VEX_HEAD + r"""
float dp = ch(CT+"dp"); float hmax = ch(CT+"hmax");
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
int c = i@col;
vector pc = @P - o;                                   // 列の計画の座標（x, 0, z）
float e = sol_eta(pc.x);
float ylo = bedy(pc.x) + chf(CT+"bed_gap")*dp;        // 海底の上 bed_gap × dp より上だけ（FLIP44・46 と同じ）
for (int k = 0; k < 1000000; k++) {
    float y = -hmax + (k + 0.5)*dp;                   // 段（静かな水なら −0.5 dp がいちばん上）
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
wmesh0.setInput(2, btabout)
wmesh0.parm("snippet").set(L.VEX_HEAD + r"""
float x0 = ch(CT+"x0"); float Lx = ch(CT+"Lx"); float Lz = ch(CT+"Lz");
float vox = ch(CT+"dp")*ch(CT+"gridscale");
float ox = ch(CT+"ox"); float oy = ch(CT+"oy"); float oz = ch(CT+"oz");
float xa = x0 - 3.0*vox; float xb = x0 + Lx + 3.0*vox; float za = -0.5*Lz - 3.0*vox; float zc = 0.5*Lz + 3.0*vox;
float yb = ch(CT+"y_floor") - 6.0*vox;
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
vvw.setInput(2, btabout)
vvw.parm("snippet").set(L.snippet("/obj/G47_SETUP/vel_value"))
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G47_SIM")
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
fo.parm("surfacetype").set("4")  # Narrow Band の入力（g47_run.py が donarrowband を 0 にする。FLIP44・46 と同じ）
fo.parm("soppath").set("/obj/G47_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G47_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G47_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/G47_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/G47_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet_sf("/obj/G47_SIM/relax_zones_sf") if PERIODIC else L.snippet("/obj/G47_SIM/relax_zones"))
relax.parm("exportlist").set("vel")
relax.parm("vex_precision").set("64")
en_r = dop.createNode("enablesolver", "enable_zones")
en_r.setInput(0, relax)
en_r.parm("enable").setExpression('ch("%srelax_on") > 0.5 || ch("%sabs_on") > 0.5' % (CT, CT))

ssc = dop.createNode("geometrywrangle", "substep_count")
ssc.parm("bindclass").set("detail")
ssc.parm("snippet").set(L.BODIES["/obj/G47_SIM/substep_count"])
ssc.parm("exportlist").set("ss_acc ss_n ss_dt")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(1, ssc)
fs.setInput(2, en_r)
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

if PERIODIC:      # 水の体積の直し（volcorr_on 0 なら Enable Solver ごと止まり、FLIP の物体も発散の場を持たない）
    fo.parm("adddivergence").setExpression('ch("%svolcorr_on") > 0.5' % CT)
    # 目標の発散は g47_run.py がコマの終わりの surface から測った体積で決め、OUT_VOLDIV（ファイルを時刻で読む Python SOP）で渡す
    vcd = dop.createNode("gasfieldwrangle", "vc_div")
    vcd.parm("snippet").set(L.snippet_vc("/obj/G47_SIM/vc_div_ext"))
    vcd.parm("exportlist").set("divergence")
    vcd.parm("vex_precision").set("64")
    en_vc = dop.createNode("enablesolver", "enable_volcorr")
    en_vc.setInput(0, vcd)
    en_vc.parm("enable").setExpression('ch("%svolcorr_on") > 0.5' % CT)
    # multisolver は FLIP の Volume Velocity の入力に「型が違う」で繋がらない（2026-10-13 試した）。Enable Solver（常に 1）で 2 つを束ねる
    msv = dop.createNode("enablesolver", "volume_velocity")
    msv.setInput(0, en_r)
    msv.setInput(1, en_vc)
    msv.parm("enable").set(1)
    fs.setInput(2, msv)
mg = dop.createNode("merge", "merge")        # 海底を merge の左（FLIP40〜46 と同じ順）
mg.setInput(0, so)
mg.setInput(1, fs)
gr = dop.createNode("gravity", "gravity")
gr.setInput(0, mg)
out = dop.createNode("output", "output")
out.setInput(0, gr)
out.setDisplayFlag(True)
dop.layoutChildren()

# ---------------------------------------------------------------- 読み取り（水面の場、流速の場、衝突の場）
rd = obj.createNode("geo", "G47_READ")
for c in rd.children():
    c.destroy()
for nm in ("surface", "vel", "collision"):
    fi = rd.createNode("dopimportfield::2.0", nm + "_field")
    fi.parm("doppath").set("/obj/G47_SIM")
    fi.parm("fields").set(1)
    fi.parm("objname1").set("water")
    fi.parm("fieldname1").set(nm)
rd.layoutChildren()

# ---------------------------------------------------------------- 作った物を一度だけ確かめる（既定：E1a の全部の領域・粒子 0.5 m）
for n in (btab, sol, itab, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw) + ((sftab,) if PERIODIC else ()):
    try:
        n.cook(force=True)
    except Exception as e:
        print("COOK ERROR", n.path(), str(e)[:400])
    if n.errors():
        print("ERR", n.path(), n.errors())
print("gravity", [(p.name(), p.eval()) for p in gr.parms() if p.name().startswith("force")])
g = btabout.geometry()
print("bed table", g.attribValue("bx"), g.attribValue("bd"))
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
if PERIODIC:
    g = sftabout.geometry()
    print("sf table (empty by default)", [(a.name(), g.attribValue(a.name())) for a in g.globalAttribs()] if g else None)
    print("relax snippet has sfwave", "sfwave(" in relax.parm("snippet").eval())
    print("volume velocity input", fs.inputs()[2].path() if fs.inputs()[2] else None, "errors", [str(e)[:120] for e in fs.errors()])
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
print("saved", HIP)
