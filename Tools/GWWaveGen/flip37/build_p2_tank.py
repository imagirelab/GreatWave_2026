# -*- coding: utf-8 -*-
"""P2 粗い 3D の岩棚の探索の水槽：P1 の水槽（build_p1_tank.py）を複製し、幅（z）を 240 m にして、
岩棚を上から見た形と、交わる二つの波の列を足し、Houdini/FLIP37/p2_tank.hiplc に保存する（hython 22.0.459）。

P1 から変えたこと（2026-10-06）：
- 板（幅 W）→ 3D の箱（幅 Lz、z = -Lz/2 〜 +Lz/2、両側は閉じた壁）。
- 海底 bedy(x, z)：
    斜面の始まり xs(z) = xs0 + lens_A (1 - exp(-(z/lens_zl)^2)) + tan(obl_deg) (z + Lz/2)
      （lens_A > 0：中央が沖へ張り出した岬の形＝中央の集まるレンズ。obl_deg：等深線を峰に対して斜めにする＝入る向きの角度と同じ働き）
    岩棚の水深 hr(z) = hr + lens_dh (1 - exp(-(z/lens_zl)^2))（両側を深くする）
    低い棚（盛り上がり）2 つ：中心 (lgK_x, lgK_z)、頂の水深 lgK_d、広がり lgK_sx・lgK_sz（K=1,2。lgK_d <= 0 で使わない）
  どれも xs(z) >= xs0（P1 で解けた並びより左へ斜面を出さない）。
- 波：wave_mode 0（2 次 Stokes の周期波の先頭、P1 と同じ）に、交わる二つの列 cross_deg（> 0 で ±cross_deg の 2 列の線形の重ね。
  z 方向の波数は保たれ（Snell）、x 方向の位相はその場の水深で積む（WKB）。H は z=0 での山から谷）を足した。
- 静かな水の確かめの代わりに、見張り（水槽全体の平均の水面が 1 m 下がったら止める）を run_p2.py で使う。
- 水面の網目を書き出す読み取りの鎖（P2_READ/OUT_MESH）：surface の場 → convertvolume（等値 0）→ 箱で切る → 三角形 → 頂点の点番号。
版 3（2026-10-06 18:45）：lens_z0・cross_z0（レンズと交わる模様の中心 z）と mirror_z（解析だけの印）を足した。
  既定の 0 では版 2 と同じ計算。z=-Lz/2 の壁（滑る壁＝対称の面）に中心を置き、cross_deg を asin(π/(Lz k0)) にすると、
  交わる二つの列が水路のちょうどの形（cos(π(z+Lz/2)/Lz)、両方の壁で横の流速が 0）になり、壁での食い違いがなくなる（T14・Lz 240 で 34.29°）。
圧力が解けない失敗（P0 §3.4）への直しはしていない。水の塊の作り方・merge・前処理は P0/P1 のまま。

以下は P1 の説明（要約）：座標 x＝波の進む向き、y＝上、z＝峰に沿う向き。静かな水面 y = 0。1 単位 = 1 m。
水槽：平らな助走（水深 60 m）→ 斜面 1:n → 岩棚 → 波を吸う帯（xa0 から、なだらかなスポンジ σmax）。
hot start：頂を x=xc0 に置いた 2 次 Stokes の周期波の先頭（斜面の上は WKB・線形の浅水変形・Wheeler の伸ばし）、前端 xhot、後ろの端 xback。
粒子は水面近くの帯だけ（narrow band、band_vox 格子）。直し 1（VDB の初め、海底を merge の左、IC の前処理）・直し 2（帯は水平だけ寄せる）を含む。
"""
import hou, os, sys

HIP = r"G:/Unity/GreatWave_2026_Fresh/Houdini/FLIP37/p2_tank.hiplc"
CT = "/obj/P2_SETUP/CTRL/"

hou.hipFile.clear(suppress_save_prompt=True)
obj = hou.node("/obj")
setup = obj.createNode("geo", "P2_SETUP")
for c in setup.children():
    c.destroy()

# ---------------------------------------------------------------- CTRL
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
    ("xs0", 420.0, "斜面の始まり x (m)（中央・いちばん沖）"),
    ("lens_A", 0.0, "レンズ：両側の斜面の始まりを岸へ下げる量 (m)（中央が張り出す）"),
    ("lens_zl", 60.0, "レンズの広がり z (m)"),
    ("lens_dh", 0.0, "レンズ：両側の岩棚を深くする量 (m)"),
    ("lens_z0", 0.0, "レンズの中心 z (m)（版 3。-Lz/2 で壁が対称の面）"),
    ("obl_deg", 0.0, "等深線の斜め (°)（+z の側ほど岸へ下げる）"),
    ("lg1_d", 0.0, "低い棚 1：頂の水深 (m)（0 で使わない）"),
    ("lg1_x", 560.0, "低い棚 1：中心 x"),
    ("lg1_z", -50.0, "低い棚 1：中心 z"),
    ("lg1_sx", 30.0, "低い棚 1：広がり x"),
    ("lg1_sz", 15.0, "低い棚 1：広がり z"),
    ("lg2_d", 0.0, "低い棚 2：頂の水深 (m)（0 で使わない）"),
    ("lg2_x", 560.0, "低い棚 2：中心 x"),
    ("lg2_z", -95.0, "低い棚 2：中心 z"),
    ("lg2_sx", 25.0, "低い棚 2：広がり x"),
    ("lg2_sz", 10.0, "低い棚 2：広がり z"),
    ("xg_end", 140.0, "波を起こす帯の終わり x (m)"),
    ("xa0", 706.0, "波を吸う帯の始まり x (m)"),
    ("ytop", 32.0, "箱の天井 y (m)"),
    ("T", 14.0, "周期 T (s)"),
    ("H", 3.0, "波の高さ H (m)（0 で静かな水）"),
    ("wave_mode", 0.0, "波の種類（0＝周期波の列 2 次 Stokes）"),
    ("cross_deg", 0.0, "交わる二つの列の角度 ±θ (°)（0＝一つの列）"),
    ("cross_z0", 0.0, "交わる列の模様の中心 z (m)（版 3。-Lz/2 で壁が対称の面）"),
    ("mirror_z", 0.0, "記録だけ：1＝z=-Lz/2 の壁を対称の面として、解析で鏡に映して全体の波とする"),
    ("stokes2", 1.0, "2 次の項を入れる（一つの列の時だけ）"),
    ("xc0", 330.0, "t=0 で破れる波の頂を置く x (m)"),
    ("ph0", 0.0, "位相 (rad)"),
    ("xhot", 480.0, "hot start の波の前端 x (m)"),
    ("hot_w", 30.0, "hot start の前端のなだらかさ (m)"),
    ("xback", 120.0, "hot start の後ろの端 x (m)（0＝使わない）"),
    ("band_vox", 6.0, "narrow band の厚さ（格子の数）"),
    ("relax_g", 0.0, "波を起こす帯の強さ（P1・P2 は 0）"),
    ("relax_a", 1.0, "波を吸う帯の強さ（倍率）"),
    ("maxsub", 2.0, "FLIP の最大小刻み"),
    ("abs_mode", 1.0, "波を吸う帯の形（1＝なだらかなスポンジ）"),
    ("abs_sigma", 0.8, "スポンジの σmax (1/s)"),
    ("abs_pow", 2.0, "スポンジの強さの増え方 χ^p の p"),
    ("mx0", 380.0, "網目を切る箱 x の始まり"),
    ("mx1", 706.0, "網目を切る箱 x の終わり"),
    ("my0", -14.0, "網目を切る箱 y の下"),
]
for nm, dv, lb in PARMS:
    ptg.append(hou.FloatParmTemplate(nm, lb, 1, default_value=(dv,)))
ptg.append(hou.StringParmTemplate("ckpt", "途中保存のフォルダー", 1,
                                  default_value=(r"G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP37/P2/ckpt_default",)))
ptg.append(hou.IntParmTemplate("ckpt_on", "途中保存する", 1, default_value=(0,)))
ptg.append(hou.IntParmTemplate("ckpt_every", "途中保存の間隔（コマ）", 1, default_value=(48,)))
ctrl.setParmTemplateGroup(ptg)

VEXLIB = r'''
#define GG 9.80665
#define CT "%s"
float kdisp(float om; float h) {
    float k = om*om/GG/sqrt(tanh(om*om*h/GG));
    for (int i = 0; i < 20; i++) {
        float th = tanh(k*h);
        float f = GG*k*th - om*om;
        float df = GG*th + GG*k*h*(1.0 - th*th);
        k -= f/df;
    }
    return k;
}
float lensw(float z) { float zl = chf(CT+"lens_zl"); float zz = z - chf(CT+"lens_z0"); return 1.0 - exp(-(zz*zz)/(zl*zl)); }
float xsz(float z) {
    return chf(CT+"xs0") + chf(CT+"lens_A")*lensw(z) + tan(radians(chf(CT+"obl_deg")))*(z + 0.5*chf(CT+"Lz"));
}
float hrz(float z) { return chf(CT+"hr") + chf(CT+"lens_dh")*lensw(z); }
float bedy3(float x; float z) {
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
float hloc3(float x; float z) { return max(-bedy3(x, z), 0.5); }
float kshoal(float om; float h) {
    float k = kdisp(om, h); float kh = k*h;
    float n = 0.5*(1.0 + 2.0*kh/sinh(2.0*kh));
    return 1.0/sqrt(n*tanh(kh));
}
// x 方向の位相の積み（z ごと。kz は保たれる＝Snell）。斜面の始まり xsz(z) より沖は平ら
float thetax3(float x; float z; float om; float kz) {
    float k0 = kdisp(om, chf(CT+"h0"));
    float kx0 = sqrt(max(k0*k0 - kz*kz, 1e-8));
    float xs = min(xsz(z), x);
    float acc = kx0*xs;
    if (x <= xs) return kx0*x;
    int N = 16; float dx = (x - xs)/N;
    for (int i = 0; i < N; i++) {
        float kk = kdisp(om, hloc3(xs + (i + 0.5)*dx, z));
        acc += sqrt(max(kk*kk - kz*kz, 1e-8))*dx;
    }
    return acc;
}
void airy(float x; float y; float z; float t; float E; float eta; vector vel) {
    float h0 = chf(CT+"h0");
    float T = chf(CT+"T"); float H = chf(CT+"H"); float ph0 = chf(CT+"ph0");
    float hr = chf(CT+"hr");
    float om = 2.0*PI/T;
    float h = hloc3(x, z);
    float k0 = kdisp(om, h0);
    float k = kdisp(om, h);
    float cr = radians(chf(CT+"cross_deg"));
    if (cr > 1e-4) {
        // 交わる二つの列 ±cr：eta = 2a cos(kz z) cos(Θx - ωt - φ)
        float kz = k0*sin(cr);
        float kx0 = k0*cos(cr);
        float a = 0.25*H*E*kshoal(om, h)/kshoal(om, h0);
        float th = thetax3(x, z, om, kz) - om*t - kx0*chf(CT+"xc0") + ph0;
        float zr = z - chf(CT+"cross_z0");
        eta = 2.0*a*cos(kz*zr)*cos(th);
        float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
        float s = sinh(k*h);
        float kx = sqrt(max(k*k - kz*kz, 1e-8));
        float C = cosh(k*(ye + h))/s; float S = sinh(k*(ye + h))/s;
        vel = set(2.0*a*om*C*(kx/k)*cos(kz*zr)*cos(th), 2.0*a*om*S*cos(kz*zr)*sin(th), -2.0*a*om*C*(kz/k)*sin(kz*zr)*sin(th));
        return;
    }
    float a = 0.5*H*E*kshoal(om, h)/kshoal(om, h0);
    float th = thetax3(x, z, om, 0.0) - om*t - k0*chf(CT+"xc0") + ph0;
    float s2w = chf(CT+"stokes2")*pow(clamp((h - hr)/max(h0 - hr, 1e-3), 0.0, 1.0), 2.0);
    float sh0 = sinh(k0*h0);
    float e2c = 0.25*k0*cosh(k0*h0)*(2.0 + cosh(2.0*k0*h0))/(sh0*sh0*sh0);
    eta = a*cos(th) + s2w*e2c*a*a*cos(2.0*th);
    float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
    float s = sinh(k*h);
    vector v1 = set(a*om*cosh(k*(ye + h))/s*cos(th), a*om*sinh(k*(ye + h))/s*sin(th), 0.0);
    float ye0 = clamp(h0*(y - eta)/(h0 + eta), -h0, 0.0);
    float c2 = 0.75*a*a*om*k0/(sh0*sh0*sh0*sh0);
    vector v2 = set(c2*cosh(2.0*k0*(ye0 + h0))*cos(2.0*th), c2*sinh(2.0*k0*(ye0 + h0))*sin(2.0*th), 0.0);
    vel = v1 + s2w*v2;
}
float hotE(float x) {
    float E = 0.5*(1.0 - tanh((x - chf(CT+"xhot"))/chf(CT+"hot_w")));
    if (chf(CT+"xback") > 0.0) E *= 0.5*(1.0 + tanh((x - chf(CT+"xback"))/chf(CT+"hot_w")));
    return E;
}
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
''' % CT

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
bw.parm("snippet").set(VEXLIB + r'''
@P.y = bedy3(@P.x, clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz")));
''')
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
bsdfw.parm("snippet").set(VEXLIB + r'''
float zc = clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz"));
float yb = bedy3(@P.x, zc);
float e = 0.5;
float gx = (bedy3(@P.x + e, zc) - bedy3(@P.x - e, zc))/(2.0*e);
float gz = (bedy3(@P.x, zc + e) - bedy3(@P.x, zc - e))/(2.0*e);
f@collision = (@P.y - yb)/sqrt(1.0 + gx*gx + gz*gz);
''')
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
colw.parm("snippet").set(VEXLIB + r"""
float eta; vector vv;
airy(@P.x, 0.0, @P.z, 0.0, hotE(@P.x), eta, vv);
f@eta = eta;
f@yb = bedy3(@P.x, @P.z);
""")
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
pts.parm("snippet").set(VEXLIB + r"""
float e2; vector v2;
airy(@P.x, @P.y, @P.z, 0.0, hotE(@P.x), e2, v2);
v@v = v2;
""")
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
wmesh.parm("snippet").set(VEXLIB + r"""
float Lz = chf(CT+"Lz");
float eta; vector vv;
airy(@P.x, 0.0, clamp(@P.z, -0.5*Lz, 0.5*Lz), 0.0, hotE(@P.x), eta, vv);
@P.y = eta;
""")
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
airy(@P.x, @P.y, @P.z, 0.0, hotE(@P.x), eta, vel);
v@vel = vel;
''')
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
dop = obj.createNode("dopnet", "P2_SIM")
dop.parm("cachemaxsize").set(3000)
dop.parm("explicitcache").setExpression('ch("%sckpt_on")' % CT)
dop.parm("explicitcachename").set('`chs("%sckpt")`/p2.$SF4.sim' % CT)
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
fo.parm("soppath").set("/obj/P2_SETUP/OUT_PARTICLES")
fo.parm("import_nbsurface").set("/obj/P2_SETUP/OUT_SURFACE_VDB")
fo.parm("import_nbvelocity").set("/obj/P2_SETUP/OUT_VEL_VDB")
fo.parm("jitterscale").set(0.0)

so = dop.createNode("staticobject", "seabed")
so.parm("object_name").set("seabed")
so.parm("soppath").set("/obj/P2_SETUP/OUT_BED")
so.parm("usevolume").set(1)
so.parm("mode").set("volume")
so.parm("proxyvolume").set("/obj/P2_SETUP/OUT_BED_SDF")
so.parm("collisiondetection").set("volume")

relax = dop.createNode("gasfieldwrangle", "relax_zones")
relax.parm("snippet").set(VEXLIB + r'''
float x = @P.x;
float xa0 = chf(CT+"xa0"); float Lx = chf(CT+"Lx");
if (x > xa0) {
    float chi = clamp((x - xa0)/(Lx - xa0), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc*chf(CT+"relax_a"));
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''')

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
rd = obj.createNode("geo", "P2_READ")
for c in rd.children():
    c.destroy()
fi = rd.createNode("dopimportfield::2.0", "surface_field")
fi.parm("doppath").set("/obj/P2_SIM")
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
