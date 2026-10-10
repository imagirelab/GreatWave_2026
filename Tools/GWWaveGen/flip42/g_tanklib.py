# -*- coding: utf-8 -*-
"""FLIP42：集まる波の群の断面の水槽（Houdini/FLIP42/g_tank.hiplc）の VEX。g_build_tank.py が使う。
FLIP41 の v_tanklib.py（Tools/GWWaveGen/flip41、変えていない）を写して直した。VEX は CTRL の値だけを読む
（計算ごとにコードを書き換えない。場面のファイルは計算で変わらない）。

水槽：x＝波の進む向き、y＝上、z＝板の厚さ（格子 4 個）。静かな水面 y = 0。1 単位 = 1 m。海底は平ら（水深 h0）。
造波（緩和の帯、計画 §4）：x < xg_end（= x_p）で、格子の水平の流速だけを、32 成分の線形の重ね合わせの流速へ寄せる。
  η = Σ a cos(k_i (x − x_p − x_b) − ω_i (t − t_b))。周波数は fc(1 − dff/2)〜fc(1 + dff/2) に等しい間隔で ncomp 個、
  k_i は水深 h0 の分散の関係（g = 9.80665）、振幅はどの成分も a = S / Σ k_i（Rapp & Melville の作り方、Derakhti 2013 式 2.33）。
  水面より上の流速は、全成分を足した η で伸ばす（Wheeler の形：ye = h (y − η)/(h + η)、水面より上は水面の値）。
  重みは Jacobsen ら 2012 の形（壁の側で 1）で、小刻みの長さに合わせる：w_dt = 1 − (1 − w)^(dt/dt0)、dt0 = 1/24 s（計画 §4）。
  縦の流速と水面は寄せない（FLIP41 と同じ）。目標は壁の近く（wall_taper_m）で 0 へ落とし、始めの ramp_s 秒でなだらかに上げる。
吸う帯：x > xa0 で、水平と厚さの向きの流速を 0 へ寄せるスポンジ（σ = abs_sigma·χ^abs_pow、FLIP41 と同じ）。
力は重力だけ（風の圧力・形を作る力は入れない）。
小刻みの記録：粒子の Geometry の detail に、そのコマの小刻みの数 ss_n と最後の小刻みの長さ ss_dt を書く。
"""

CT = "/obj/G_SETUP/CTRL/"

VEX_HEAD = r'''
#define CT "%s"
float bedy(float x) { return -chf(CT+"h0"); }
float bedsdf(float x; float y) { return bedy(x) - y; }   // 海底の中で正
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
float kofom(float om; float h) {
    float g = 9.80665;
    float k = max(om*om/g, om/sqrt(g*h));
    for (int it = 0; it < 60; it++) {
        float th = tanh(k*h);
        float f = g*k*th - om*om;
        float df = g*th + g*k*h*(1.0 - th*th);
        float dk = f/df;
        k -= dk;
        if (abs(dk) < 1e-12*k) break;
    }
    return k;
}
// 32 成分の線形の重ね合わせ（水深 h0）。E は壁の近くと始めのなだらかさの掛け算
void groupwave(float x; float y; float t; float E; float eta; vector vel) {
    int N = chi(CT+"ncomp");
    float h = chf(CT+"h0"); float fc = chf(CT+"fc"); float dff = chf(CT+"dff");
    float fa = fc*(1.0 - 0.5*dff); float fb = fc*(1.0 + 0.5*dff);
    float xr = x - chf(CT+"x_p") - chf(CT+"x_b");
    float tr = t - chf(CT+"t_b");
    float om[]; float kk[]; resize(om, N); resize(kk, N);
    float sk = 0.0;
    for (int i = 0; i < N; i++) {
        float f = (N > 1) ? fa + (fb - fa)*i/(N - 1.0) : fc;
        om[i] = 2.0*PI*f; kk[i] = kofom(om[i], h); sk += kk[i];
    }
    float a = E*chf(CT+"S")/sk;
    eta = 0.0;
    for (int i = 0; i < N; i++) eta += a*cos(kk[i]*xr - om[i]*tr);
    float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
    float u = 0.0; float v = 0.0;
    for (int i = 0; i < N; i++) {
        float th = kk[i]*xr - om[i]*tr;
        float sh = sinh(kk[i]*h);
        u += a*om[i]*cosh(kk[i]*(ye + h))/sh*cos(th);
        v += a*om[i]*sinh(kk[i]*(ye + h))/sh*sin(th);
    }
    vel = set(u, v, 0.0);
}
''' % CT

BODIES = {
    "/obj/G_SETUP/bed_height": r'''
@P.y = bedy(@P.x);
''',
    "/obj/G_SETUP/bed_sdf_value": r'''
f@collision = -bedsdf(@P.x, @P.y);   // Static Object の代わりの体積：海底の中で負
''',
    # 造波の帯・吸う帯（格子の流速 vel）
    "/obj/G_SIM/relax_zones": r'''
float x = @P.x;
float t = f@Time;
float xg = chf(CT+"xg_end");
if (x < xg && chf(CT+"relax_g") > 0.0) {
    float w = clamp(relaxw((xg - x)/xg)*chf(CT+"relax_g"), 0.0, 1.0);
    float wdt = 1.0 - pow(1.0 - w, f@TimeInc/chf(CT+"dt0"));   // 小刻みの長さに合わせる（計画 §4）
    float E = walltaper(x)*rampT(t, chf(CT+"ramp_s"));
    float eta; vector tv;
    groupwave(x, @P.y, t, E, eta, tv);
    v@vel = set(lerp(v@vel.x, tv.x, wdt), v@vel.y, v@vel.z);   // 水平だけ寄せる
}
float xa0 = chf(CT+"xa0"); float Lx = chf(CT+"Lx");
if (x > xa0) {
    float chi = clamp((x - xa0)/(Lx - xa0), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc);
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''',
    # 小刻みの数の記録（粒子の Geometry の detail。Particle Velocity の入口で毎小刻み 1 回）
    "/obj/G_SIM/substep_count": r'''
// 1 コマ（1/24 s）分の刻みが積もったら数え直す（f@Time の意味によらない形。2026-10-09 の試しで、
// f@Time から作った鍵では最小小刻み 2 でも 1 と数えたため、積み上げに替えた）
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
}


def snippet(path):
    return VEX_HEAD + BODIES[path]
