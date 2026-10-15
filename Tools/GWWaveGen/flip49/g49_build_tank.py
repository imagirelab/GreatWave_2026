# -*- coding: utf-8 -*-
"""FLIP49：周期の波の 3D の水槽（PER49。入口の帯で流れ関数のうねり、出口のスポンジ、水の量の直し、海底 PG12s）の場面を作り、
Houdini/FLIP49/g49_tank.hiplc に保存する（hython。1〜3 分。重い計算と重ならないよう x49_build.py から起動する）。
2026-10-15 新しく書いた。g48_build_tank.py（flip48、変えていない）の作りを写し、g47_build_tank.py --periodic（flip47、変えていない）の
帯・流れ関数の表・水の量の直しの節を 3D にして足した。g48_tank.hiplc・flip45〜48 のファイルには触れない。
FLIP48 と同じにした所：粒子の置き方（格子の中心の列に dp ごと、0.2 dp の揺らぎ、海底 + 0.5 dp より上）、閉じたメッシュから作る初めの水面の VDB、
  FLIP Solver 2.0・格子 = 粒子 × 2・圧力の前処理 IC、海底の SDF を Static Object の体積 collision で（merge の左に seabed）、
  箱の底は floor_pad 格子下、壁は格子の面（Houdini = 計画 + o）、上は開く、面（R5）の道、読み取りの道。
足した所：
  - CTRL：海底の新しい項（pg_hL・pg_s2・b_end・b_x1・b_x2・lag_xb・lag_s・lag_h）、帯（relax_on・abs_on・sf_on・relax_g・dt0・ramp_s・
    wall_taper_m・in_gain・x_p・xg_end・xa0・abs_sigma・abs_pow・set_*・duabs_on）、水の量の直し（volcorr_on・vol_x0・vol_x1・hold_on・hold_x0・hold_x1）、
    文字の sf_tab・vol_dir。既定は全部「切る」（静かな水・帯なし。g49_run.py が cfg の parms で入れる）。
  - SOP：sf_table → OUT_SF（流れ関数の表）、voldiv_table → OUT_VOLDIV（ファイルを時刻で読む Python SOP）、確かめの sf_probe・relax_probe。
  - DOP：relax_zones（Gas Field Wrangle、vel、64 ビット）と vc_div（divergence）を Enable Solver で束ねて FLIP Solver の Volume Velocity の入力へ
    （g47 の作り。multisolver は型が違うと言われて繋がらない【g47 で試した】）。FLIP の物体の adddivergence は volcorr_on・hold_on の時だけ。
作った後の確かめ（Build/FLIP49/_logs/build_check.json。all_ok が偽なら計算を始めない）：
  1. 海底：OUT_BED の点の高さと SDF を numpy（g49_common.bed_z・bed_sdf）と全部の点で比べる（< 1 cm・< 2 cm・符号の違い 0。VEX と numpy の差の最大も
     「< 1 mm」の印で書く）：PG12s の 3D（W 85）、PG12s の軸の板（W 6）、平らな板、FLIP48 R4（g48 の式の道。箱の底 −25 m）。
  2. 粒子の数：軸の板・平らな板（粒子 0.5 m）と PG12s の 3D（粒子 1.0 m）を Houdini で数え、numpy の数え方（g49_common.count_particles）と比べる。
     海底より下の粒子 0。
  3. 流れ関数の波：sf_probe の 168 点（x 7 × y 6 × t 4）の η・u・w を numpy（g47_sfwave）と比べる（u・w ≤ 1e-6 c、η ≤ 1e-6 H）。
  4. 帯：relax_probe の点で relax_apply を numpy の写し（この道具の relax_np）と比べる（入口・出口・その間、縦の流速が変わらない、
     目標 0 で E = 0）。発散 vc_divergence と Sommerfeld の項 du_abs を試しのファイル（_logs/vdtest/vd_00001.txt）で確かめる。
  5. 保存する場面の CTRL が作った時の既定（静かな水・帯なし）に戻っている。
  2026-10-15 方案 A（SC37 = FLIP48 C3 の海底を +37.25 m、礁の上 20 m の先 1:2 で 6 m、箱 442 × 85 m・底 −25 m）を足した：
  6. A_3d：方案 A の海底と SDF を numpy と比べる（新しい項の道 pgon()：pg_hL 0・b_end 0・lag_xb 353.25。VEX の式は足していない。
     溝と礁湖への下りを同時に使う道を、ここで初めて Houdini で確かめる）。A_3d_particles_dp1：粒子 1.0 m（半幅 86 m）の数。
  7. relax_probe_A：方案 A の並び（出口の帯 362〜442 m、窓 110〜357 m）で帯の関数と発散。
  set_box は箱の長さ Lx を受ける（既定は PG12s の 360 m）。
使い方：py -3.10 x49_build.py（ほかの hython が終わるまで待ってから hython g49_build_tank.py を起動する）
"""
import hou, os, sys, json, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48")
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip49")
import importlib, numpy as np, g49_tanklib as L, g49_common as GC
importlib.reload(L); importlib.reload(GC)

HIP = GC.HIP
CT = L.CT
B0 = GC.box48(0.5, Lx=GC.LX, W=GC.W_STRIP, floor_pad=2)       # 既定：PG12s の軸の板（作った後の確かめの煮込みが軽い）
AX = GC.pg_axis()

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "G49_SETUP")
for c in setup.children():
    c.destroy()

ctrl = setup.createNode("null", "CTRL")
ptg = ctrl.parmTemplateGroup()
_bp = GC.bed_parms(AX)
PARMS = [
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
    ("ox", B0["ox"], "Houdini の x = 計画の x + ox"),
    ("oy", B0["oy"], "Houdini の上 y = 計画の z + oy（静かな水面は Houdini の y = oy）"),
    ("oz", B0["oz"], "Houdini の横 z = 計画の y + oz（対称の面は Houdini の z = oz）"),
    # 海底（g48 の名前）
    ("ridge_on", _bp["ridge_on"], "尾根（1 で置く、0 で平らな海底）"),
    ("ridge_x0", _bp["ridge_x0"], "尾根の始まり x_toe (m)（PG12s は 180.25）"),
    ("ridge_k", _bp["ridge_k"], "尾根の横の変化 sech²(k y'/h0) の k（既定 0 = 軸の板。PG12s の 3D は 0.35）"),
    ("ridge_s", _bp["ridge_s"], "真ん中の断面の 1 段目の勾配 1:s（PG12s は 10）"),
    ("shelf_h", _bp["shelf_h"], "棚（礁の上）の水深 m（PG12s は 1.7）"),
    ("ridge_kend", _bp["ridge_kend"], "先細りの終わりの k（< 0 で無し。PG12s の 3D は 1.0）"),
    ("ridge_xk1", _bp["ridge_xk1"], "先細りの始まり x (m)"),
    ("ridge_xk2", _bp["ridge_xk2"], "先細りの終わり x (m)"),
    ("ch_h", _bp["ch_h"], "横の遠くの溝の水深 m（0 で無し）"),
    ("ch_y0", _bp["ch_y0"], "溝の壁の真ん中の |y| (m)"),
    ("ch_w", _bp["ch_w"], "溝の壁の tanh の幅 (m)"),
    ("ch_x0", _bp["ch_x0"], "溝が始まる x (m)"),
    ("ch_lx", _bp["ch_lx"], "溝が深くなりきるまでの x の長さ (m)"),
    ("ledge_s1", 0.0, "g48 の段の 1:s1（FLIP49 では 0。新しい項と同時に使わない）"),
    ("ledge_dl", 0.0, "g48 の段の高さ dL (m)"),
    ("ledge_s2", 0.0, "g48 の段の 1:s2"),
    # FLIP49 の海底の新しい項（既定は PG12s の軸の値。無しは pg_hL 0・b_end 0・lag_xb 1e9）
    ("pg_hL", _bp["pg_hL"], "FLIP49：段の足の水深 m（1:s でここまで、その先 1:pg_s2。0 で無し）"),
    ("pg_s2", _bp["pg_s2"], "FLIP49：段の勾配 1:pg_s2（軸の外でも続く）"),
    ("b_end", _bp["b_end"], "FLIP49：頂の平らの半幅 m（0 で無し）"),
    ("b_x1", _bp["b_x1"], "FLIP49：頂の平らが広がり始める x (m)"),
    ("b_x2", _bp["b_x2"], "FLIP49：頂の平らが b_end になる x (m)"),
    ("lag_xb", _bp["lag_xb"], "FLIP49：礁湖へ下がり始める x_back (m)（1e9 以上で無し）"),
    ("lag_s", _bp["lag_s"], "FLIP49：礁湖への勾配 1:lag_s"),
    ("lag_h", _bp["lag_h"], "FLIP49：礁湖の水深 m"),
    ("bed_gap", 0.5, "海底の上の粒子を置かない厚さ（dp の倍数）"),
    ("floor_pad", 2.0, "箱の底を zb より何格子下げるか"),
    ("wave_on", 0.0, "孤立波の初めの状態（FLIP49 は 0 = 静かな水から）"),
    ("side_pad", 0.0, "対称の面 y = 0 を SDF の壁にする（0 = 箱の壁）"),
    # 帯（既定は切る）
    ("relax_on", 0.0, "入口の帯（1 で流れ関数の波へ寄せる）"),
    ("abs_on", 0.0, "出口の帯（1 でスポンジ）"),
    ("sf_on", 0.0, "入口の帯の目標を流れ関数の波に（0 なら目標 0）"),
    ("relax_g", 1.0, "入口の帯の強さ"),
    ("dt0", 1.0 / 24.0, "帯の重みの基準の刻み dt0 (s)"),
    ("ramp_s", GC.RAMP_S, "始めのなだらかさ（半余弦）(s)"),
    ("wall_taper_m", GC.WALL_TAPER, "入口の目標を上流の壁の近くで 0 へ落とす長さ (m)"),
    ("in_gain", 1.0, "入口の目標に掛ける数（S0b で一度だけ決める）"),
    ("x_p", GC.X_P, "入口の目標の位相の基準 x_p (m)"),
    ("xg_end", GC.IN_X1, "入口の帯の終わり x (m)"),
    ("xa0", 1e9, "出口の帯の始まり x (m)"),
    ("abs_sigma", GC.EX_SIGMA, "スポンジの σmax (1/s)"),
    ("abs_pow", GC.EX_POW, "スポンジの χ^p の p"),
    ("set_P", 0.0, "組の周期 P (s)。0 なら包絡なし（1）"),
    ("set_up", 0.0, "組の上り (s)"),
    ("set_flat", 0.0, "組の満ち (s)"),
    ("set_down", 0.0, "組の下り (s)"),
    ("set_cg", 0.0, "組の包絡を遅れた時刻 t − (x − x_p)/set_cg で読む（0 で t のまま）"),
    ("duabs_on", 0.0, "段 C：Sommerfeld の項 du_abs を入口の目標に足す（1）"),
    # 水の量の直し（既定は切る）
    ("volcorr_on", 0.0, "段 A：水の量の直し（1。目標の発散を vol_x0〜vol_x1 に）"),
    ("vol_x0", GC.VOL_X[0], "段 A の窓の始め x (m)"),
    ("vol_x1", GC.VOL_X[1], "段 A の窓の終わり x (m)"),
    ("hold_on", 0.0, "段 B：帯の芯の水面を保つ発散（1）"),
    ("hold_x0", GC.HOLD_X[0], "段 B の所の始め x (m)"),
    ("hold_x1", GC.HOLD_X[1], "段 B の所の終わり x (m)"),
    # 面（R5）
    ("surf_layer_m", 2.5, "面を作る粒子：水面からこの深さより下を除く (m)"),
    ("mirror_m", 1.0, "対称の面から写す粒子の幅 (m)"),
    ("surf_vox_scale", 1.0, "Particle Fluid Surface の Voxel Scale"),
    ("crop_x0", 0.0, "面を切り出す x の始め (m)"),
    ("crop_x1", B0["Lx"], "面を切り出す x の終わり (m)"),
    ("crop_z1", B0["W"], "面を切り出す横の終わり (m)"),
    ("surf_ycut", -15.0, "これより下の面を除く y (m)"),
    ("surf_keep_vox", 1.0, "FLIP の水面の場からこの格子の数より離れた三角形を除く"),
    ("surf_bed_vox", 0.5, "海底からこの格子の数より近い三角形を除く"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("sol_npz", "孤立波の解の npz（FLIP49 は使わない）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("sf_tab", "流れ関数の表（h k c Ub N B1..BN E0..EN）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("vol_dir", "目標の発散・du_abs のファイルの置き場所（g49_run.py が書く。空なら 0）", 1, default_value=("",)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1, default_value=(GC.B49 + "/runs/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(240,)))
ctrl.setParmTemplateGroup(ptg)
for nm, dv, lb in PARMS:          # 既定値は 6 桁に丸められるので、値は set で入れる
    ctrl.parm(nm).set(dv)

VOXE = 'ch("%sdp")*ch("%sgridscale")' % (CT, CT)

# ---------------------------------------------------------------- 表（孤立波・流れ関数・目標の発散）
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
sftab.parm("snippet").set(L.snippet("/obj/G49_SETUP/sf_table"))
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
bgrid.parm("rows").setExpression('int(2*(ch("%sLx") + 20)) + 1' % CT)      # FLIP49：0.5 m ごと（段 1:2.5・礁湖 1:2 の折れを点で拾う）
bgrid.parm("cols").setExpression('int(ch("%sW") + 12) + 1' % CT)
bgrid.parm("tx").setExpression(BOXC["tx"])
bgrid.parm("ty").setExpression('ch("%soy")' % CT)
bgrid.parm("tz").setExpression(BOXC["tz"])
bw = setup.createNode("attribwrangle", "bed_height")
bw.setInput(0, bgrid)
bw.parm("snippet").set(L.snippet("/obj/G49_SETUP/bed_height"))
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
bsdfw.parm("snippet").set(L.snippet("/obj/G49_SETUP/bed_sdf_value"))
bsdfout = setup.createNode("null", "OUT_BED_SDF")
bsdfout.setInput(0, bsdfw)

# ---------------------------------------------------------------- 初めの粒子（海底と静かな水面の間の全部。流速 0）
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
vvw.parm("snippet").set(L.snippet("/obj/G49_SETUP/vel_value"))
vvout = setup.createNode("null", "OUT_VEL")
vvout.setInput(0, vvw)

# ---------------------------------------------------------------- 確かめの点（json の文字 → 点と float の属性）と probe の wrangle
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


sfp_pts, sfp = probe_nodes("sf_probe", "/obj/G49_SETUP/sf_probe")
rlp_pts, rlp = probe_nodes("relax_probe", "/obj/G49_SETUP/relax_probe")
setup.layoutChildren()

# ---------------------------------------------------------------- DOP
dop = obj.createNode("dopnet", "G49_SIM")
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
fo.parm("soppath").set("/obj/G49_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/G49_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/G49_SETUP/OUT_VEL")
fo.parm("jitterscale").set(0.0)
fo.parm("adddivergence").setExpression('ch("%svolcorr_on") > 0.5 || ch("%shold_on") > 0.5' % (CT, CT))

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/G49_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/G49_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(L.snippet("/obj/G49_SIM/relax_zones"))
relax.parm("exportlist").set("vel")
relax.parm("vex_precision").set("64")
en_r = dop.createNode("enablesolver", "enable_zones")
en_r.setInput(0, relax)
en_r.parm("enable").setExpression('ch("%srelax_on") > 0.5 || ch("%sabs_on") > 0.5' % (CT, CT))

vcd = dop.createNode("gasfieldwrangle", "vc_div")
vcd.parm("snippet").set(L.snippet("/obj/G49_SIM/vc_div"))
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
ssc.parm("snippet").set(L.BODIES["/obj/G49_SIM/substep_count"])
ssc.parm("exportlist").set("ss_acc ss_n ss_dt")

fs = dop.createNode("flipsolver::2.0", "flipsolver")
fs.setInput(0, fo)
fs.setInput(1, ssc)
fs.setInput(2, msv)
fs.parm("veltransfer").set("flip")           # FLIP49：FLIP の受け渡し（APIC は y = 0 の側へ偽の横流れ【FLIP46 で測定】）
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

# ---------------------------------------------------------------- 読み取り
rd = obj.createNode("geo", "G49_READ")
for c in rd.children():
    c.destroy()
for nm in ("surface", "vel", "collision"):
    fi = rd.createNode("dopimportfield::2.0", nm + "_field")
    fi.parm("doppath").set("/obj/G49_SIM")
    fi.parm("fields").set(1)
    fi.parm("objname1").set("water")
    fi.parm("fieldname1").set(nm)
rd.layoutChildren()

# ---------------------------------------------------------------- 面（記録 R5。g48 と同じ道）
sf = obj.createNode("geo", "G49_SURF")
for c in sf.children():
    c.destroy()
di = sf.createNode("dopimport", "particles")
di.parm("doppath").set("/obj/G49_SIM")
di.parm("objpattern").set("water")
sfield = sf.createNode("object_merge", "surface_field")
sfield.parm("objpath1").set("/obj/G49_READ/surface_field")
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

# ---------------------------------------------------------------- 一度煮込む
for n in (sol, sftab, vdp, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
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


# ======================================================================== 確かめ
def ctrl_floats():
    return {p.name(): p.eval() for p in ctrl.parms() if p.parmTemplate().type() == hou.parmTemplateType.Float}


def set_ctrl(d):
    for nm, v in d.items():
        ctrl.parm(nm).set(v)


def bed_check(tag):
    """OUT_BED の点の高さと SDF（collision）の符号・値を numpy（g49_common）と比べる。CTRL の今の値で。"""
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
        Z, Y, X = np.meshgrid(zs, ys, xs, indexing="ij")
        ref = GC.bed_sdf(X, Y, Z, **spec)
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
    rec["gap_min_m"] = float(gap.min()); rec["z_max_m"] = float(Pp[:, 1].max())
    n_model, V = GC.count_particles(spec, float(P_["Lx"]), float(P_["W"]), float(P_["dp"]), zb=float(P_["zb"]), bed_gap=float(P_["bed_gap"]))
    rec["particles_model"] = int(n_model); rec["particles_ratio_houdini_over_model"] = float(len(Pp)) / max(n_model, 1)
    rec["particles_ok"] = bool(rec["n_below_bed"] == 0 and abs(rec["particles_ratio_houdini_over_model"] - 1.0) < 0.002)
    return rec


def set_box(dp, W, spec, zb=GC.Z_BOTTOM, Lx=GC.LX):
    b = GC.box48(dp, Lx=Lx, W=W, zb=zb, floor_pad=2)
    d = dict(dp=b["dp"], Lx=b["Lx"], W=b["W"], zb=b["z_bottom"], Hz=b["Hz"], ox=b["ox"], oy=b["oy"], oz=b["oz"], crop_x1=b["Lx"], crop_z1=b["W"])
    d.update(GC.bed_parms(spec))
    set_ctrl(d)
    return b


def relax_np(pl, v0, t, dts, P_, sf):
    """relax_apply の numpy の写し（確かめだけ）。du_abs は与えた値。"""
    x = pl[0]
    v = np.array(v0, float)
    if P_["relax_on"] > 0.5 and x < P_["xg_end"] and P_["relax_g"] > 0:
        chi = (P_["xg_end"] - x) / max(P_["xg_end"] - P_["x0"], 1e-6)
        c = min(max(chi, 0.0), 1.0)
        w = min(max((np.exp(c ** 3.5) - 1.0) / (np.e - 1.0) * P_["relax_g"], 0.0), 1.0)
        wdt = 1.0 - (1.0 - w) ** (dts / P_["dt0"])
        wt = float(GC.smooth01((x - P_["x0"]) / P_["wall_taper_m"])) if P_["wall_taper_m"] > 0 else 1.0
        E = float(GC.envelope(x, t, P_))
        ux = 0.0
        if P_["sf_on"] > 0.5:
            _, u, _, _, _ = GC.sf_target(x, pl[1], t, sf, P_, E=E)
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


def relax_check(W_, spec, zb_, Lx_, xa0_, volx, xs_, sfT):
    """帯の関数（relax_apply）と発散（vc_divergence）を relax_probe の点で numpy の写し（relax_np）と比べる。箱・出口の帯・窓は与えた並び。"""
    vdt = GC.B49 + "/_logs/vdtest"
    os.makedirs(vdt, exist_ok=True)
    DV = (0.0013, -0.0007, 0.21)
    open(vdt + "/vd_00001.txt", "w").write("%r %r %r\n" % DV)
    set_box(0.5, W_, spec, zb=zb_, Lx=Lx_)
    on = dict(relax_on=1.0, abs_on=1.0, sf_on=1.0, in_gain=1.07, xa0=xa0_, duabs_on=1.0, volcorr_on=1.0, hold_on=1.0, vol_x0=volx[0], vol_x1=volx[1])
    set_ctrl(on)
    ctrl.parm("vol_dir").set(vdt)
    hou.setFrame(1)
    vdp.cook(force=True)
    vg_ = vdout.geometry()
    vread = [vg_.attribValue(nm) for nm in ("vol_div", "vol_div_band", "du_abs")]
    P_ = ctrl_floats(); P_["_du_abs"] = DV[2]
    rows = []
    for x_ in xs_:
        for y_ in (-12.0, -1.0):
            for t_, dts_ in ((0.0, 1.0 / 24.0), (13.3, 1.0 / 96.0), (40.0, 1.0 / 48.0)):
                rows.append(dict(px=x_, py=y_, pz=3.0 if x_ < 200 else 70.0, pt=t_, dts=dts_, v0=(0.7, -0.3, 0.4)))
    rlp_pts.parm("pts_json").set(json.dumps(rows))
    rlp.cook(force=True)
    g_ = rlp.geometry()
    v1 = np.array(g_.pointFloatAttribValues("v1")).reshape(-1, 3); dv_ = np.array(g_.pointFloatAttribValues("div"))
    ref = np.array([relax_np((r["px"], r["py"], r["pz"]), r["v0"], r["pt"], r["dts"], P_, sfT) for r in rows])
    dref = np.array([(DV[0] if volx[0] <= r["px"] <= volx[1] else 0.0) + (DV[1] if GC.HOLD_X[0] <= r["px"] <= GC.HOLD_X[1] else 0.0) for r in rows])
    vert_same = bool(np.allclose(v1[:, 1], -0.3, atol=1e-6))
    mid = np.array([GC.IN_X1 + 5.0 <= r["px"] < xa0_ - 1e-9 for r in rows])
    out = dict(n=len(rows), Lx=float(P_["Lx"]), xa0=float(P_["xa0"]), vol_x=[float(P_["vol_x0"]), float(P_["vol_x1"])], zb=float(P_["zb"]),
               voldiv_read=vread, voldiv_ok=bool(np.allclose(vread, DV, atol=1e-12)),
               v_max_abs_diff=float(np.abs(v1 - ref).max()), div_max_abs_diff=float(np.abs(dv_ - dref).max()),
               vertical_unchanged=vert_same, untouched_between_bands=bool(np.allclose(v1[mid], np.array([0.7, -0.3, 0.4]), atol=1e-6)),
               exit_band_damps=bool(np.all(np.abs(v1[np.array([r["px"] > xa0_ + 1.0 for r in rows]), 0]) < 0.7)))
    # 目標 0（sf_on 0・du_abs 0）なら入口の帯は流速を 0 へ寄せるだけ（E = 0）
    set_ctrl(dict(sf_on=0.0, duabs_on=0.0))
    rlp.cook(force=True)
    v0z = np.array(rlp.geometry().pointFloatAttribValues("v1")).reshape(-1, 3)
    inb = np.array([r["px"] < GC.IN_X1 for r in rows])
    P_ = ctrl_floats(); P_["_du_abs"] = 0.0
    ref0 = np.array([relax_np((r["px"], r["py"], r["pz"]), r["v0"], r["pt"], r["dts"], P_, sfT) for r in rows])
    out["target0_max_abs_diff"] = float(np.abs(v0z - ref0).max())
    out["target0_toward_zero"] = bool(np.all(np.abs(v0z[inb, 0]) <= 0.7 + 1e-6) and np.all(np.abs(v0z[inb, 2]) <= 0.4 + 1e-6))   # 点の属性は 32 ビット
    # 点の属性（v1・div）は 32 ビットで残るので、差の上限は 1e-6 m/s・1e-9 /s（VEX の計算は 64 ビット）
    out["tolerance_note"] = "point attributes are stored as float32: v within 1e-6 m/s, div within 1e-9 1/s"
    out["ok"] = bool(out["voldiv_ok"] and out["v_max_abs_diff"] < 1e-6 and out["div_max_abs_diff"] < 1e-9 and vert_same and out["untouched_between_bands"]
                     and out["target0_max_abs_diff"] < 1e-6 and out["target0_toward_zero"] and out["exit_band_damps"])
    return out


CHK = dict(date=time.strftime("%Y-%m-%d %H:%M:%S"), hip=HIP, houdini=hou.applicationVersionString(), module_shas=GC.module_shas())
DEFAULT_CTRL = ctrl_floats()
DEFAULT_STR = {nm: ctrl.parm(nm).evalAsString() for nm in ("sol_npz", "sf_tab", "vol_dir")}


def restore_ctrl():
    set_ctrl(DEFAULT_CTRL)
    for nm, v in DEFAULT_STR.items():
        ctrl.parm(nm).set(v)


try:
    # 1・2：海底と粒子
    CHK["axis_strip_PG12s"] = bed_check("PG12s の軸の板（k 0・横 6 m、粒子 0.5 m）")
    particle_check(CHK["axis_strip_PG12s"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_STRIP, GC.flat_spec())
    CHK["flat_strip"] = bed_check("平らな板（17 m、横 6 m、粒子 0.5 m）")
    particle_check(CHK["flat_strip"], GC.bed_spec(parms=ctrl_floats()))
    set_box(0.5, GC.W_MAIN, GC.PG12S)
    CHK["PG12s_3d"] = bed_check("PG12s の 3D（横 85 m、粒子 0.5 m の格子）")
    set_box(1.0, GC.W_MAIN, GC.PG12S)
    CHK["PG12s_3d_particles_dp1"] = particle_check(dict(), GC.bed_spec(parms=ctrl_floats()))
    r4 = dict(GC.G48.bed_spec(parms=dict(ridge_on=1.0, ridge_x0=143.0, ridge_k=0.35, ridge_s=10.0, h0=17.0, shelf_h=1.7,
                                         **GC.G48.bed_parms(dict(GC.G48.BED_EXTRA_DEFAULTS, **GC.G48.TAPER_R3, **GC.G48.CHANNEL_R3)))), **GC.NEW_DEFAULTS)
    set_box(0.5, GC.W_MAIN, r4, zb=GC.G48.ZB_DEEP)
    CHK["R4_g48_path"] = bed_check("FLIP48 R4 の海底（g48 の式の道：先細り＋溝 25 m、箱の底 −25 m）")
    CHK["R4_g48_path"]["numpy_equals_g48_bit"] = bool(np.array_equal(GC.bed_z(np.arange(0, 360, 0.37)[None, :], np.arange(0, 85, 0.41)[:, None], **r4),
                                                                     GC.G48.bed_z(np.arange(0, 360, 0.37)[None, :], np.arange(0, 85, 0.41)[:, None],
                                                                                  **{k: r4[k] for k in GC.BED48_KEYS})))
    # 方案 A（SC37）の海底：箱 442 × 85 m、底 −25 m。粒子 0.5 m の格子で海底と SDF、粒子 1.0 m（半幅 86 m）で粒子の数
    LA = GC.LAYOUTS["A"]
    set_box(0.5, GC.W_MAIN, GC.SPEC_A, zb=LA["zb"], Lx=LA["Lx"])
    CHK["A_3d"] = bed_check("方案 A の海底 SC37（FLIP48 C3 を +37.25 m、礁の上 20 m の先 1:2 で 6 m。箱 442 × 85 m、底 −25 m、粒子 0.5 m の格子）")
    CHK["A_3d"]["pg_path"] = bool(GC.is_new(CHK["A_3d"]["spec"]) and GC.is_spur_drop(CHK["A_3d"]["spec"]))
    set_box(1.0, GC.W_MAIN, GC.SPEC_A, zb=LA["zb"], Lx=LA["Lx"])
    CHK["A_3d_particles_dp1"] = particle_check(dict(), GC.bed_spec(parms=ctrl_floats()))
    CHK["A_3d_particles_dp1"]["W"] = float(ctrl.parm("W").eval())
    restore_ctrl()
    # 3：流れ関数の波（168 点）
    sfT = json.load(open(GC.sf_table_file(), encoding="utf8"))      # x49_build.py が py -3.10 で解いた表（hython には scipy が無い）
    ctrl.parm("sf_tab").set(GC.sf_tab_string(sfT))
    sftab.cook(force=True)
    sg = sftabout.geometry()
    sfinfo = {a_.name(): sg.attribValue(a_.name()) for a_ in sg.globalAttribs() if a_.name() in ("sfh", "sfk", "sfc", "sfUb", "sfN")}
    pts = []
    xs_ = [0.0, 20.0, 50.0, 80.0, 95.0, 130.0, 200.0]
    ts_ = [0.0, 3.1, 7.7, 11.9]
    for x_ in xs_:
        for t_ in ts_:
            e_ = float(GC.sf_target(x_, 0.0, t_, sfT, DEFAULT_CTRL, E=1.0)[3].ravel()[0])
            for y_ in (-17.0, -12.0, -6.0, -2.0, 0.5 * e_, e_ + 1.0):
                pts.append(dict(px=x_, py=y_, pt=t_))
    sfp_pts.parm("pts_json").set(json.dumps(pts))
    sfp.cook(force=True)
    g_ = sfp.geometry()
    ev = np.array(g_.pointFloatAttribValues("eta_v")); uv = np.array(g_.pointFloatAttribValues("u_v")); wv = np.array(g_.pointFloatAttribValues("w_v"))
    X_ = np.array([p["px"] for p in pts]); Y_ = np.array([p["py"] for p in pts]); T_ = np.array([p["pt"] for p in pts])
    _, un, wn, en, _ = GC.sf_target(X_, Y_, T_, sfT, DEFAULT_CTRL, E=1.0)
    c_ = float(sfT["c"]); H_ = float(sfT["H"])
    CHK["sf_probe"] = dict(n=len(pts), sf_table=sfinfo, sfN_ok=bool(int(sfinfo.get("sfN", -1)) == len(sfT["B"])),
                           u_max_abs_over_c=float(np.abs(uv - un.ravel()).max() / c_), w_max_abs_over_c=float(np.abs(wv - wn.ravel()).max() / c_),
                           eta_max_abs_over_H=float(np.abs(ev - en.ravel()).max() / H_), c=c_, H=H_, T=float(sfT["T"]), L=float(sfT["L"]),
                           eta_crest=float(sfT["eta_crest"]), eta_trough=float(sfT["eta_trough"]), u1=float(sfT["u1_mean_current"]))
    CHK["sf_probe"]["ok"] = bool(CHK["sf_probe"]["sfN_ok"] and CHK["sf_probe"]["u_max_abs_over_c"] <= 1e-6 and CHK["sf_probe"]["w_max_abs_over_c"] <= 1e-6
                                 and CHK["sf_probe"]["eta_max_abs_over_H"] <= 1e-6)
    # 4：帯と発散（試しのファイル）。PG12s の並び（出口 290〜360 m）と方案 A の並び（出口 362〜442 m、窓 110〜357 m、箱の底 −25 m）
    CHK["relax_probe"] = relax_check(GC.W_MAIN, GC.PG12S, GC.Z_BOTTOM, GC.LX, GC.EX_X0, GC.VOL_X,
                                     (1.0, 5.0, 19.0, 40.0, 70.0, 99.0, 100.0, 105.0, 150.0, 200.0, 289.0, 291.0, 320.0, 359.5), sfT)
    LA = GC.LAYOUTS["A"]
    CHK["relax_probe_A"] = relax_check(GC.W_MAIN, GC.SPEC_A, LA["zb"], LA["Lx"], LA["ex_x0"], LA["vol_x"],
                                       (1.0, 19.0, 70.0, 99.0, 105.0, 150.0, 250.0, 356.0, 358.0, 361.0, 363.0, 380.0, 400.0, 441.5), sfT)
    restore_ctrl()
    for n in (sol, sftab, vdp, bw, bsdfw, cols, pts0, wmesh0, wvdb, vvw):
        n.cook(force=True)
    sfp_pts.parm("pts_json").set("[]"); rlp_pts.parm("pts_json").set("[]")
    CHK["restored_ctrl_equal_default"] = bool(ctrl_floats() == DEFAULT_CTRL and all(ctrl.parm(k).evalAsString() == v for k, v in DEFAULT_STR.items()))
    CHK["saved_scene_still_water_bands_off"] = bool(all(ctrl.parm(k).eval() == 0.0 for k in ("relax_on", "abs_on", "sf_on", "volcorr_on", "hold_on", "duabs_on", "wave_on")))
    CHK["dop_errors"] = {n_.path(): [str(e)[:200] for e in n_.errors()] for n_ in (relax, vcd, en_r, en_vc, msv, fo, fs) if n_.errors()}
except Exception as e:
    import traceback
    CHK["error"] = repr(e)[:400]
    CHK["traceback"] = traceback.format_exc()[-3000:]
    try:
        restore_ctrl()
    except Exception:
        pass
BEDK = ("axis_strip_PG12s", "flat_strip", "PG12s_3d", "R4_g48_path", "A_3d")
CHK["all_ok"] = bool(all((CHK.get(k) or {}).get("bed_ok") and (CHK.get(k) or {}).get("sdf_ok") for k in BEDK)
                     and all((CHK.get(k) or {}).get("particles_ok") for k in ("axis_strip_PG12s", "flat_strip", "PG12s_3d_particles_dp1", "A_3d_particles_dp1"))
                     and (CHK.get("R4_g48_path") or {}).get("numpy_equals_g48_bit") and (CHK.get("A_3d") or {}).get("pg_path")
                     and (CHK.get("sf_probe") or {}).get("ok") and (CHK.get("relax_probe") or {}).get("ok") and (CHK.get("relax_probe_A") or {}).get("ok")
                     and CHK.get("restored_ctrl_equal_default") and CHK.get("saved_scene_still_water_bands_off") and not CHK.get("error"))
print("BUILD_CHECK", json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if not isinstance(vv, (dict, list))})
                                 for k, v in CHK.items() if k not in ("module_shas", "traceback")}, ensure_ascii=False, default=str)[:6000])
os.makedirs(GC.B49 + "/_logs", exist_ok=True)
json.dump(CHK, open(GC.B49 + "/_logs/build_check.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
os.makedirs(os.path.dirname(HIP), exist_ok=True)
hou.hipFile.save(HIP)
CHK["hip_sha256"] = GC.sha256_file(HIP)            # g49_chain.py は場面がこの値と同じ時だけ始める（確かめた場面のまま）
json.dump(CHK, open(GC.B49 + "/_logs/build_check.json", "w", encoding="utf8"), indent=1, ensure_ascii=False, default=str)
print("saved", HIP, CHK["hip_sha256"][:16])
