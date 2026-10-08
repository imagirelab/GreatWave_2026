# -*- coding: utf-8 -*-
"""FLIP41 確かめ（verify）：断面の水槽の場面（Houdini/FLIP41/v_tank.hiplc）の VEX。v_build_tank.py が使う。
VEX は CTRL の値だけを読む（計算ごとにコードを書き換えない。場面のファイルは計算で変わらない）。

水槽：x＝波の進む向き、y＝上、z＝板の厚さ（格子 4 個）。静かな水面 y = 0。1 単位 = 1 m。
海底：平ら（水深 h0）、または x ≥ xs0 で 1:slope_n で上り、水深 h1 で平ら。
造波（wm_mode）：
  1 = 緩和の帯（FLIP39 と同じ形）：x < xg_end で、格子の水平の流速だけを目標の線形の波（Airy、水深 h0）の流速へ寄せる。
      重みは Jacobsen ら 2012 の形（壁の側で 1）。縦の流速と水面は寄せない（FLIP37 P0 の直し 2）。
  2 = ピストン板：x = xp0 + X(t) の動く壁。衝突の場 collision（固体の中で正）と、衝突の速さ collisionvel を毎刻み書く。
      X(t) = r(t)·(S/2)·sin(ωt)、r は始めのなだらかさ。S/2 は v_run.py が Biésel の式から決める。
吸う帯：x > xa0 で、水平の流速を 0 へ寄せるなだらかなスポンジ（σ = abs_sigma·χ^abs_pow、FLIP39 と同じ）。
風（p_mode）：水面の圧力の場 surfacepressure（FLIP Solver の Surface Tension を入れると作られ、圧力の計算が水面の値として使う）に書く。
  1 = 動かない圧力 p = r(t)·(p0u + p0c·cos(pk·x))（単位と符号の確かめ T1）
  2 = 波の斜面と同じ位相の圧力 p = −r(t)·P0·(n·x̂)（n は水面の外向きの向き。小さな斜面では P0·∂η/∂x。Miles・Jeffreys の形）
  接線の応力 tau（Pa）：水面のすぐ下の 1 格子の層の水平の流速に τ/(ρ Δ)·dt を足す（Large & Pond の τ = ρa Cd U10²）。
"""

CT = "/obj/V_SETUP/CTRL/"

VEX_HEAD = r'''
#define CT "%s"
float bedy(float x) {
    float h0 = chf(CT+"h0"); float n = chf(CT+"slope_n");
    float y = -h0;
    if (n > 0.0) y = -h0 + max(0.0, x - chf(CT+"xs0"))/n;
    return min(y, -chf(CT+"h1"));
}
float bedslope(float x) {
    float n = chf(CT+"slope_n");
    if (n <= 0.0) return 0.0;
    float y = -chf(CT+"h0") + max(0.0, x - chf(CT+"xs0"))/n;
    return (x > chf(CT+"xs0") && y < -chf(CT+"h1")) ? 1.0/n : 0.0;
}
float bedsdf(float x; float y) {   // 海底の中で正（FLIP の collision の場と同じ向き）
    float s = bedslope(x);
    return (bedy(x) - y)/sqrt(1.0 + s*s);
}
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
float smooth01(float c0) { float c = clamp(c0, 0.0, 1.0); return c*c*(3.0 - 2.0*c); }
float walltaper(float x) {
    float L = chf(CT+"wall_taper_m");
    if (L <= 0.0) return 1.0;
    return smooth01(x/L);
}
float rampT(float t; float R) {
    if (R <= 0.0) return 1.0;
    float c = clamp(t/R, 0.0, 1.0);
    return 0.5 - 0.5*cos(PI*c);
}
float drampT(float t; float R) {
    if (R <= 0.0 || t <= 0.0 || t >= R) return 0.0;
    return 0.5*PI/R*sin(PI*t/R);
}
float windtaper(float x) {
    float x0 = chf(CT+"pw_x0"); float x1 = chf(CT+"pw_x1"); float L = max(chf(CT+"pw_tap"), 1e-3);
    return smooth01((x - x0)/L)*smooth01((x1 - x)/L);
}
// 目標の線形の波（Airy、水深 h0）。水面より上は水面の値へ伸ばす（FLIP39 と同じ）
void wave(float x; float y; float t; float E; float eta; vector vel) {
    float a = chf(CT+"wa")*E; float om = chf(CT+"wom"); float k = chf(CT+"wk"); float h = chf(CT+"h0");
    float th = k*x - om*t;
    eta = a*cos(th);
    float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
    float sh = sinh(k*h);
    vel = set(a*om*cosh(k*(ye + h))/sh*cos(th), a*om*sinh(k*(ye + h))/sh*sin(th), 0.0);
}
float pistonX(float t) {
    float R = chf(CT+"ramp_s"); float om = chf(CT+"wom");
    return chf(CT+"xp0") + rampT(t, R)*chf(CT+"pS2")*sin(om*t);
}
float pistonU(float t) {
    float R = chf(CT+"ramp_s"); float om = chf(CT+"wom"); float s2 = chf(CT+"pS2");
    return drampT(t, R)*s2*sin(om*t) + rampT(t, R)*s2*om*cos(om*t);
}
''' % CT

BODIES = {
    "/obj/V_SETUP/bed_height": r'''
@P.y = bedy(@P.x);
''',
    "/obj/V_SETUP/bed_sdf_value": r'''
f@collision = -bedsdf(@P.x, @P.y);   // Static Object の代わりの体積：海底の中で負
''',
    # 造波の帯・吸う帯・接線の応力（格子の流速 vel）
    "/obj/V_SIM/relax_zones": r'''
float x = @P.x;
float t = f@Time;
int wm = chi(CT+"wm_mode");
float xg = chf(CT+"xg_end");
if (wm == 1 && x < xg && chf(CT+"relax_g") > 0.0) {
    float w = clamp(relaxw((xg - x)/xg)*chf(CT+"relax_g"), 0.0, 1.0);
    float E = walltaper(x)*rampT(t, chf(CT+"ramp_s"));
    float eta; vector tv;
    wave(x, @P.y, t, E, eta, tv);
    v@vel = set(lerp(v@vel.x, tv.x, w), v@vel.y, v@vel.z);   // 水平だけ寄せる
}
float xa0 = chf(CT+"xa0"); float Lx = chf(CT+"Lx");
if (x > xa0) {
    float chi = clamp((x - xa0)/(Lx - xa0), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc);
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
float tau = chf(CT+"tau");
if (tau > 0.0) {
    float vox = chf(CT+"dp")*chf(CT+"gridscale");
    float s = f@surface;
    if (s < 0.0 && s > -vox) {
        float acc = tau/(chf(CT+"rho_w")*vox);
        v@vel.x += acc*f@TimeInc*rampT(t, chf(CT+"p_ramp"))*windtaper(x);
    }
}
''',
    # ピストン板：衝突の場（固体の中で正）
    "/obj/V_SIM/piston_coll": r'''
float t = f@Time;
float xp = pistonX(t);
f@collision = max(bedsdf(@P.x, @P.y), xp - @P.x);
''',
    # ピストン板：衝突の速さ
    "/obj/V_SIM/piston_cvel": r'''
float t = f@Time;
float xp = pistonX(t);
float vox = chf(CT+"dp")*chf(CT+"gridscale");
if (@P.x < xp + 2.0*vox) v@collisionvel = set(pistonU(t), 0.0, 0.0);
else v@collisionvel = set(0.0, 0.0, 0.0);
''',
    # 風の圧力（水面の圧力の場）
    "/obj/V_SIM/wind_pressure": r'''
float t = f@Time;
int pm = chi(CT+"p_mode");
float R = rampT(t, chf(CT+"p_ramp"));
if (pm == 1) {
    f@surfacepressure = R*(chf(CT+"p0u") + chf(CT+"p0c")*cos(chf(CT+"pk")*@P.x));
} else if (pm == 2) {
    vector g = volumegradient(0, 0, @P);
    float gl = length(g);
    float nx = gl > 1e-6 ? g.x/gl : 0.0;
    f@surfacepressure = -R*windtaper(@P.x)*chf(CT+"P0")*nx;
} else {
    f@surfacepressure = 0.0;
}
''',
}


def snippet(path):
    return VEX_HEAD + BODIES[path]
