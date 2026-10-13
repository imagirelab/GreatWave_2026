# -*- coding: utf-8 -*-
"""FLIP44：礁の断面の水槽（Houdini/FLIP44/g44_tank.hiplc）の VEX。g44_build_tank.py と煙の試しの道具が使う。
FLIP42 の g_tanklib.py（Tools/GWWaveGen/flip42、変えていない）を写して直した。風の圧力は FLIP41 の v_tanklib.py の
wind_pressure（p_mode 2）の繋ぎを元に、計画 plan_ja.md §4.1 の「はがれた流れの形（S）」に書き直した。
VEX は CTRL の値と入口の表（OUT_INLET の detail の配列）だけを読む。計算ごとにコードを書き換えない。

水槽：x＝波の進む向き、y＝上、z＝板の厚さ（格子 4 個）。静かな水面 y = 0。1 単位 = 1 m。
海底（計画 §2）：reef_on = 0 なら平ら（水深 h0）。reef_on = 1 なら、造波板からの距離 xr で
  rf_foot から 1:rf_slope_n で上り、水深 rf_h_top で平ら、rf_top_end から 1:rf_slope_n で下り h0 へ戻る。
  衝突の SDF は鉛直の距離（FLIP41・42 と同じ作り。1:5 で本当の距離の 1.02 倍）。
造波（緩和の帯、計画 §2・§3.1）：x < xg_end（= x_p）で、格子の水平の流速だけを、入口の表の成分の線形の重ね合わせの流速へ寄せる。
  η = Σ a_i cos(k_i (x − x_p) − ω_i t' + φ_i)、ω_i = 2π f_i、k_i は水深 h0 の波数（表に入れて渡す）。
  t' = t（rep_P = 0）か t mod rep_P（繰り返しの入口。f_i = m_i / P なので同じ値）。
  表は CTRL の inlet_tab（文字）を OUT_INLET が 64 ビットの配列 freq・amp・phase・k にしたもの。
  amp_gain で全体の振幅を掛ける（煙の試しの静かな水は 0）。
  水面より上の流速、帯の重み、壁の近くと始めのなだらかさは FLIP42 と同じ。
吸う帯：x > xa0 で、水平と厚さの向きの流速を 0 へ寄せるスポンジ（FLIP42 と同じ）。
風（計画 §4.1、wind_on = 1 の時だけ。0 なら風の道具は動かず、FLIP Solver の表面張力も切れる）：
  水面の圧力の場 surfacepressure（Pa）に書く。FLIP Solver の Volume Velocity の入口で、小刻みごとに呼ばれる。
  wind_mode 1 = はがれた流れの形（S）：露出した水面に p = q·n_x（n は水面の外向きの単位の向き）。上に水がある所は 0。
    「上に水がある」は、同じ列で上へ dp/2 ごとに水面の場を読み、厚さ thin_mult·dp 以上の水の区間がある時（しぶきの決まり）。
    時間は wind_t0 から wind_tramp 秒でなだらかに上げる（0.5 − 0.5 cos）。場所は wind_x0〜wind_x1 の両端 wind_tap m でなだらかに 0。
  wind_mode 2 = はがれのない流れの形（N）：まだ作っていない（煙の試し S6 の後。今は 0 を書く）。
  wind_mode 3 = 試しの形（煙の試し S4b）：p = r(t)·wt_p0·cos(2π x / wt_lam)、r は wt_ramp 秒で 0.5 − 0.5 cos。
  呼ばれた回数は、同じ入口の Geometry Wrangle（wind_count）が粒子の detail の wind_calls に数える（S4b）。
  圧力を書いた時の水面の場を windsurf に写す（Gas Match Field の wind_field が surface に合わせて作る）。記録の断面の水面の場は
  コマの終わりの物で、圧力を書いた時の物と違うため（煙の試し S9、record_ja.md の計画から変えた所 6）。
小刻みの記録：粒子の Geometry の detail に、そのコマの小刻みの数 ss_n と最後の小刻みの長さ ss_dt を書く（FLIP42 と同じ）。
"""

CT = "/obj/G44_SETUP/CTRL/"
TAB = "op:/obj/G44_SETUP/OUT_INLET"

VEX_HEAD = r'''
#define CT "%s"
#define TAB "%s"
float bedy(float x) {
    float h0 = chf(CT+"h0");
    if (chf(CT+"reef_on") < 0.5) return -h0;
    float xr = x - chf(CT+"x_p");
    float n = chf(CT+"rf_slope_n"); float ht = chf(CT+"rf_h_top");
    float df = h0 - (xr - chf(CT+"rf_foot"))/n;        // 前の斜面の水深
    float db = ht + (xr - chf(CT+"rf_top_end"))/n;     // 後ろの斜面の水深
    return -min(h0, max(ht, max(df, db)));
}
float bedsdf(float x; float y) { return bedy(x) - y; }   // 海底の中で正（鉛直の距離）
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
// 入口の表の成分の線形の重ね合わせ（水深 h0）。E は壁の近くと始めのなだらかさの掛け算
void groupwave(float x; float y; float t; float E; float eta; vector vel) {
    float fr[] = detail(TAB, "freq"); float am[] = detail(TAB, "amp");
    float ph[] = detail(TAB, "phase"); float kk[] = detail(TAB, "k");
    int N = len(fr);
    float h = chf(CT+"h0");
    float P = chf(CT+"rep_P");
    float tt = (P > 0.0) ? t - P*floor(t/P) : t;
    float xr = x - chf(CT+"x_p");
    float G = E*chf(CT+"amp_gain");
    float th[]; resize(th, N);
    eta = 0.0;
    for (int i = 0; i < N; i++) {
        th[i] = kk[i]*xr - 2.0*PI*fr[i]*tt + ph[i];
        eta += G*am[i]*cos(th[i]);
    }
    float ye = clamp(h*(y - eta)/(h + eta), -h, 0.0);
    float u = 0.0; float v = 0.0;
    for (int i = 0; i < N; i++) {
        float om = 2.0*PI*fr[i];
        float sh = sinh(kk[i]*h);
        u += G*am[i]*om*cosh(kk[i]*(ye + h))/sh*cos(th[i]);
        v += G*am[i]*om*sinh(kk[i]*(ye + h))/sh*sin(th[i]);
    }
    vel = set(u, v, 0.0);
}
// 風：時間のなだらかさ・場所のなだらかさ
float windramp(float t) {
    float t0 = chf(CT+"wind_t0"); float tr = chf(CT+"wind_tramp");
    if (t < t0 || t > chf(CT+"wind_t1")) return 0.0;
    if (tr <= 0.0) return 1.0;
    float c = clamp((t - t0)/tr, 0.0, 1.0);
    return 0.5 - 0.5*cos(PI*c);
}
float windtaper(float x) {
    float x0 = chf(CT+"wind_x0"); float x1 = chf(CT+"wind_x1"); float L = max(chf(CT+"wind_tap"), 1e-3);
    return smooth01((x - x0)/L)*smooth01((x1 - x)/L);
}
// しぶきの決まり：p0 から上へ dp/2 ごとに水面の場（入力 inp の 0 番の体積）を読み、厚さ thin_mult·dp 以上の水の区間があれば 1。
// 区間の厚さは、水へ入る所と出る所を前後の 2 点の一次の補間で出す。
int covered(int inp; vector p0; float ytop) {
    float dp = chf(CT+"dp"); float st = 0.5*dp;
    float need = chf(CT+"thin_mult")*dp*(1.0 - 1e-3);
    float sp = volumesample(inp, 0, p0);
    float yin = (sp < 0.0) ? p0.y : -1e9;
    float y = p0.y;
    while (y < ytop) {
        float yn = y + st;
        float s = volumesample(inp, 0, set(p0.x, yn, p0.z));
        if (sp >= 0.0 && s < 0.0) {
            yin = y + st*sp/(sp - s);
        } else if (sp < 0.0 && s >= 0.0) {
            float yout = y + st*sp/(sp - s);
            if (yout - yin >= need) return 1;
            yin = -1e9;
        }
        sp = s; y = yn;
    }
    if (sp < 0.0 && ytop - yin >= need) return 1;
    return 0;
}
// はがれた流れの形（S）の圧力（Pa）。pos は場の点、inp は水面の場の入力
float windS(int inp; vector pos; float t) {
    float R = windramp(t);
    if (R <= 0.0) return 0.0;
    float wt = windtaper(pos.x);
    if (wt <= 0.0) return 0.0;
    float dp = chf(CT+"dp");
    float vox = dp*chf(CT+"gridscale");
    float s = volumesample(inp, 0, pos);
    if (abs(s) >= chf(CT+"wind_band_vox")*vox) return 0.0;
    vector g = volumegradient(inp, 0, pos);
    float gl = length(g);
    if (gl < 1e-6) return 0.0;
    vector n = g/gl;
    vector ps = pos - n*s;              // いちばん近い水面の点
    vector p0 = ps + n*(0.5*dp);        // 水面から外へ dp/2
    if (covered(inp, p0, chf(CT+"ytop")) == 1) return 0.0;
    return R*wt*chf(CT+"wind_q")*n.x;
}
''' % (CT, TAB)

BODIES = {
    "/obj/G44_SETUP/bed_height": r'''
@P.y = bedy(@P.x);
''',
    "/obj/G44_SETUP/bed_sdf_value": r'''
f@collision = -bedsdf(@P.x, @P.y);   // Static Object の代わりの体積：海底の中で負
''',
    # 入口の表（CTRL の inlet_tab「f a φ k」を成分の数だけ並べた文字）→ 64 ビットの detail の配列
    "/obj/G44_SETUP/inlet_table": r'''
string s[] = split(chs(CT+"inlet_tab"), " ");
int n = len(s)/4;
float fr[]; float am[]; float ph[]; float kk[];
resize(fr, n); resize(am, n); resize(ph, n); resize(kk, n);
for (int i = 0; i < n; i++) {
    fr[i] = atof(s[4*i]); am[i] = atof(s[4*i + 1]); ph[i] = atof(s[4*i + 2]); kk[i] = atof(s[4*i + 3]);
}
f[]@freq = fr; f[]@amp = am; f[]@phase = ph; f[]@k = kk;
i@ncomp = n;
f@sum_a = sum(am);
''',
    # 造波の帯・吸う帯（格子の流速 vel）
    "/obj/G44_SIM/relax_zones": r'''
float x = @P.x;
float t = f@Time;
float xg = chf(CT+"xg_end");
if (x < xg && chf(CT+"relax_g") > 0.0) {
    float w = clamp(relaxw((xg - x)/xg)*chf(CT+"relax_g"), 0.0, 1.0);
    float wdt = 1.0 - pow(1.0 - w, f@TimeInc/chf(CT+"dt0"));   // 小刻みの長さに合わせる（FLIP42 と同じ）
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
    # 小刻みの数の記録（FLIP42 と同じ。粒子の Geometry の detail。Particle Velocity の入口で毎小刻み 1 回）
    "/obj/G44_SIM/substep_count": r'''
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
    # 風の圧力（水面の圧力の場）。入力 1 に同じ物の surface を結ぶ（FLIP41 と同じ）
    "/obj/G44_SIM/wind_pressure": r'''
float t = f@Time;
int mode = int(chf(CT+"wind_mode") + 0.5);
float p = 0.0;
if (mode == 3) {
    p = rampT(t, chf(CT+"wt_ramp"))*chf(CT+"wt_p0")*cos(2.0*PI*@P.x/chf(CT+"wt_lam"));
} else if (mode == 1) {
    p = windS(0, @P, t);
}
f@surfacepressure = p;
f@windsurf = volumesample(0, 0, @P);   // この時の水面の場の写し（W6 で、圧力を書いた時と同じ水面から式の値を出すため。2026-10-12 03:28 に足した）
''',
    # 風の VEX が呼ばれた回数（wind_pressure と同じ入口・同じ切り替えの下。1 コマで数え直す。S4b）
    "/obj/G44_SIM/wind_count": r'''
if (f@wc_acc >= 1.0/24.0 - 1e-6) { f@wc_acc = 0.0; i@wind_calls = 0; }
f@wc_acc += f@TimeInc;
i@wind_calls += 1;
''',
}


def snippet(path):
    return VEX_HEAD + BODIES[path]


def inlet_tab_string(freqs, amps, phases, ks):
    """入口の表の文字（成分ごとに「f a φ k」、repr の桁で 64 ビットのまま渡す）。"""
    out = []
    for f, a, p, k in zip(freqs, amps, phases, ks):
        out += [repr(float(f)), repr(float(a)), repr(float(p)), repr(float(k))]
    return " ".join(out)
