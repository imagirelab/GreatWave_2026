# -*- coding: utf-8 -*-
"""FLIP39 E：水槽の場面（e_tank.hiplc）の VEX を作る部品。e_build_tank.py（場面を作る）と e_run.py（計算ごとに成分を書き込む）が使う。

波の起こし方（境界の造波だけ。水の中に力・速さを足さない）：
- 造波の帯（x < xg_end）：格子の水平の流速（x・z）を、目標の線形の波の群の流速へ寄せる（P0 の直し 2 と同じく縦は圧力に任せる）。
  目標は成分の和 η = Σ a_i cos(kz_i (z − zf)) cos(kx_i x − ω_i t + φ_i)。帯の中は平らな沖（水深 h0）。
  寄せる重みは Jacobsen ら 2012 の relaxw（壁の側で 1）。目標は壁の近くで 0 へなだらかに落とす（wall_taper_m。閉じた壁の隣で流速 0 でない目標へ寄せると、
  壁ぎわの水が上下に大きく揺れた：P0 §4.4、P1 §9 の 6）。
- 造波の始め（全部を造波で起こす時）：目標に時間のなだらかさ ramp_s をかける（静かな水から始める）。
- 途中から始める版（hybrid）：t_off 秒の時点の線形の場（同じ成分の和）を、x < xhot（なだらかさ hot_w）にだけ初めに置き、
  造波の帯はその続きを出す。遠くの造波板がすでに出した波が水槽に入っている状態に当たる（線形の場。大きな波を置くのではない。比 m1 で確かめる）。
時刻：計算の時刻 t（0 から）に t_off を足した「群の時刻」で式を計算する。焦点は群の時刻 tf、位置 xf（線形・WKB の設計）。
"""
import numpy as np

CT = "/obj/E_SETUP/CTRL/"

VEX_BED = r'''
#define GG 9.80665
#define CT "%s"
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
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
float walltaper(float x) {
    float L = chf(CT+"wall_taper_m");
    if (L <= 0.0) return 1.0;
    float c = clamp(x/L, 0.0, 1.0);
    return c*c*(3.0 - 2.0*c);
}
float hotE(float x) {
    float E = 0.5*(1.0 - tanh((x - chf(CT+"xhot"))/chf(CT+"hot_w")));
    return E*walltaper(x);
}
float rampT(float t) {
    float R = chf(CT+"ramp_s");
    if (R <= 0.0) return 1.0;
    float c = clamp(t/R, 0.0, 1.0);
    return 0.5 - 0.5*cos(PI*c);
}
''' % CT


def vex_group(comp):
    """成分の表（numpy の配列）から、群の水面と流速の VEX 関数を作る。帯と初めの場は平らな沖（水深 h0）で計算する。"""
    n = len(comp["a"])
    if n == 0:
        body = r'''
void grp(float x; float y; float z; float t; float E; float eta; vector vel) { eta = 0.0; vel = set(0, 0, 0); }
'''
        return body

    def arr(name, v):
        return "    float %s[] = {%s};\n" % (name, ", ".join("%.9g" % float(q) for q in v))
    h0 = float(comp["h0"])
    k = comp["k0"]
    s = "void grp(float x; float y; float z; float t; float E; float eta; vector vel) {\n"
    s += "    eta = 0.0; vel = set(0, 0, 0);\n    if (E < 1e-6) return;\n"
    s += arr("A", comp["a"]) + arr("OM", comp["om"]) + arr("KX", comp["kx0"]) + arr("KZ", comp["kz"]) + arr("K", k)
    s += arr("PH", comp["phi"]) + arr("SH", np.sinh(k * h0))
    s += "    float h = %.6f; float zr = z - %.6f;\n" % (h0, float(comp["zf"]))
    s += r'''    int NC = len(A);
    for (int i = 0; i < NC; i++) eta += A[i]*cos(KZ[i]*zr)*cos(KX[i]*x - OM[i]*t + PH[i]);
    eta *= E;
    float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
    for (int i = 0; i < NC; i++) {
        float th = KX[i]*x - OM[i]*t + PH[i];
        float C = cosh(K[i]*(ye + h))/SH[i]; float S = sinh(K[i]*(ye + h))/SH[i];
        float cz = cos(KZ[i]*zr); float sz = sin(KZ[i]*zr);
        float ct = cos(th); float st = sin(th);
        vel += A[i]*OM[i]*set(C*(KX[i]/K[i])*cz*ct, S*cz*st, -C*(KZ[i]/K[i])*sz*st);
    }
    vel *= E;
}
'''
    return s


BODIES = {
    # 列ごとの初めの水面（hybrid の時だけ 0 でない）
    "/obj/E_SETUP/column_eta": r'''
float eta; vector vv;
grp(@P.x, 0.0, @P.z, chf(CT+"t_off"), hotE(@P.x)*chf(CT+"hot_on"), eta, vv);
f@eta = eta;
f@yb = bedy3(@P.x, @P.z);
''',
    "/obj/E_SETUP/particle_vel": r'''
float e2; vector v2;
grp(@P.x, @P.y, @P.z, chf(CT+"t_off"), hotE(@P.x)*chf(CT+"hot_on"), e2, v2);
v@v = v2;
''',
    "/obj/E_SETUP/water_mesh_top": r'''
float Lz = chf(CT+"Lz");
float eta; vector vv;
grp(@P.x, 0.0, clamp(@P.z, -0.5*Lz, 0.5*Lz), chf(CT+"t_off"), hotE(@P.x)*chf(CT+"hot_on"), eta, vv);
@P.y = eta;
''',
    "/obj/E_SETUP/init_vel": r'''
float eta; vector vel;
grp(@P.x, @P.y, clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz")), chf(CT+"t_off"), hotE(@P.x)*chf(CT+"hot_on"), eta, vel);
v@vel = vel;
''',
    "/obj/E_SETUP/bed_height": r'''
@P.y = bedy3(@P.x, clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz")));
''',
    "/obj/E_SETUP/bed_sdf_value": r'''
float zc = clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz"));
float yb = bedy3(@P.x, zc);
float e = 0.5;
float gx = (bedy3(@P.x + e, zc) - bedy3(@P.x - e, zc))/(2.0*e);
float gz = (bedy3(@P.x, zc + e) - bedy3(@P.x, zc - e))/(2.0*e);
f@collision = (@P.y - yb)/sqrt(1.0 + gx*gx + gz*gz);
''',
    "/obj/E_SIM/relax_zones": r'''
float x = @P.x;
float xg = chf(CT+"xg_end"); float xa0 = chf(CT+"xa0"); float Lx = chf(CT+"Lx");
if (x < xg && chf(CT+"relax_g") > 0.0) {
    float w = clamp(relaxw((xg - x)/xg)*chf(CT+"relax_g"), 0.0, 1.0);
    float t = f@Time;
    float E = walltaper(x)*rampT(t + chf(CT+"ramp_t0"));
    float eta; vector tv;
    grp(x, @P.y, clamp(@P.z, -0.5*chf(CT+"Lz"), 0.5*chf(CT+"Lz")), t + chf(CT+"t_off"), E, eta, tv);
    // 水平（x, z）だけを寄せる。縦（y）は圧力の計算に任せる（P0 の直し 2）
    v@vel = set(lerp(v@vel.x, tv.x, w), v@vel.y, lerp(v@vel.z, tv.z, w));
}
if (x > xa0) {
    float chi = clamp((x - xa0)/(Lx - xa0), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc*chf(CT+"relax_a"));
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''',
}


def snippet(path, comp):
    return VEX_BED + vex_group(comp) + BODIES[path]


def comp_table(g, bedp, Lz):
    """g：群の設定（Tc, f_lo, f_hi, nf, A_f, sigma_deg, xf, tf）。bedp：海底（h0, hr, slope_n, xs0, flat）。
    戻り：成分の配列と、平らな沖での位相 φ_i（x の位相を 0 から x まで WKB で積んだ値の、焦点での値を引く）。"""
    import sys
    sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip39")
    from e_lin import Bed, make_components, kdisp, theta_x
    mound = None
    if float(bedp.get("lg1_d", 0.0)) > 0 and bool(g.get("phase_with_mound", False)):
        mound = (float(bedp["lg1_x"]), float(bedp["lg1_sx"]), float(bedp["lg1_d"]))
    bed = Bed(h0=bedp["h0"], hr=bedp["hr"], slope_n=bedp["slope_n"], xs0=bedp["xs0"], flat=bedp.get("flat", False), mound=mound)
    A_f = float(g.get("A_f", 0.0))
    zf = -0.5 * Lz
    if A_f <= 0:
        return dict(a=np.zeros(0), om=np.zeros(0), kx0=np.zeros(0), kz=np.zeros(0), k0=np.zeros(0), phi=np.zeros(0), h0=bed.h0, zf=zf, n=np.zeros(0))
    c = make_components(g["Tc"], g["f_lo"], g["f_hi"], int(g["nf"]), A_f, bed, sigma_deg=float(g.get("sigma_deg", 0.0)), W=Lz)
    om = c["om"]; kz = c["kz"]
    k0 = kdisp(om, bed.h0)
    kx0 = np.sqrt(np.maximum(k0 * k0 - kz * kz, 1e-12))
    phi = np.array([om[i] * g["tf"] - theta_x(bed, np.array([g["xf"]]), om[i], kz[i])[0] for i in range(len(om))])
    return dict(a=c["a"], om=om, kx0=kx0, kz=kz, k0=k0, phi=phi, h0=bed.h0, zf=zf, n=c["n"], f=c["f"])
