# -*- coding: utf-8 -*-
"""FLIP49：周期の波の 3D の水槽（Houdini/FLIP49/g49_tank.hiplc）の VEX と Python SOP のコード。g49_build_tank.py が使う。
2026-10-15 新しく書いた（周期の波の計画を実装する役）。元にした物（どれも変えていない。写した）：
  g48_tanklib.py（flip48）：海底の VEX（kofx・dkofx・rise・chanw・bedy・bedgrad・bedsdf_out）、孤立波の表の PYSOP と sol_eta・sol_vel
    （場面の作りを g48 とそろえるため。FLIP49 は静かな水から始めるので wave_on 0 で使う）、小刻みの数。
  g47_tanklib.py（flip47）：relaxw・walltaper・rampT・sf_setenv・sfwave・sf_chch・sf_shch・流れ関数の表 sf_table・PYSOP_VOLDIV（ファイルを時刻で読む）。
    smooth01 は g48 の物を 1 つだけ（二度定義しない）。
足した物：
  1. 海底の新しい項（g49_common.bed_z・bed_grad と同じ式。U3 の u3_beds.depth の式）：頂の平ら b(x) と db/dx、2 段の上り rise2（1:s で
     水深 pg_hL まで、その先 1:pg_s2 が軸の外でも続く）、礁湖 max(d, min(h_lag, h_r + (x − x_back)/s_back))。
     CTRL の pg_hL > 0・b_end > 0・lag_xb < 1e8 のどれも無ければ、bedy・bedgrad は g48 の式を同じ順に計算する（R0〜R4・C3 と同じ）。
  2. 入口と出口の帯 relax_apply（3D、横に一様）：入口の帯 x < xg_end で vel.x を E·u_SF へ、横の vel.z を 0 へ、FLIP42 の重み relaxw(χ)
     を小刻みの長さに合わせて寄せる（1 − (1 − w)^(dt/dt0)）。縦の流速と水面は決して寄せない（FLIP47 の relax_w 1 は 30 s で帯へ +2.80 m の
     水を引き込んだ【測定】）。E = in_gain × walltaper × rampT × sf_setenv。段 C（duabs_on 1）は Sommerfeld の項 du_abs（OUT_VOLDIV の
     detail、g49_run.py が書く）を walltaper を掛けて目標の u に足す。出口の帯 x > xa0 は vel.x・vel.z を 1 − exp(−σ χ^p dt) で 0 へ（FLIP45 の ex_mode 0）。
     DOP の relax_zones と、確かめの SOP（relax_probe）は同じ関数を呼ぶ。
  3. 水の量の直しの目標の発散 vc_div：段 A は vol_x0〜vol_x1 の窓だけに OUT_VOLDIV の vol_div、段 B（hold_on 1）は hold_x0〜hold_x1 に vol_div_band を足す。
  4. 組の包絡の遅れた時刻（set_cg > 0 の時だけ。2 段目の組のため）：τ = t − (x − x_p)/set_cg。既定 0 は g47 と同じ。
座標：VEX は始めに計画の座標 pl = @P − o に戻す：x＝波の進む向き、y＝上（静かな水面 0）、z＝横（z = 0 が対称の面）。
2026-10-15 方案 A（海底 SC37 = spur_channel_drop、g49_common.SPEC_A）：VEX の式は足していない。CTRL の pg_hL 0・b_end 0・lag_xb 353.25 で
  pgon() が真になり bedy_pg・bedgrad_pg を通る（rise2 は 1:s だけ、bofx 0、溝、礁湖への下り）。この 3 つを同時に使う道は PG12s では
  通っていなかったので、g49_build_tank.py の確かめ A_3d（海底の点と SDF を numpy と比べる）で確かめる。
"""

CT = "/obj/G49_SETUP/CTRL/"
TABF = "1"        # 孤立波の表（OUT_SOL）は SOP の wrangle の 2 つ目の入力（g48 と同じ。FLIP49 は wave_on 0）
SFT = "op:/obj/G49_SETUP/OUT_SF"
VDT = "op:/obj/G49_SETUP/OUT_VOLDIV"

VEX_HEAD = r'''
#define CT "%s"
#define TABF %s
#define SFT "%s"
#define VDT "%s"
vector plan(vector P) { return P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz")); }
// ---------------------------------------------------------------- 海底（g48_tanklib と同じ。R3 の先細り・溝・段）
float kofx(float x) {
    float k = chf(CT+"ridge_k");
    float ke = chf(CT+"ridge_kend");
    if (ke < 0.0) return k;
    float x1 = chf(CT+"ridge_xk1"); float x2 = chf(CT+"ridge_xk2");
    return k + (ke - k)*clamp((x - x1)/(x2 - x1), 0.0, 1.0);
}
float dkofx(float x) {
    float ke = chf(CT+"ridge_kend");
    if (ke < 0.0) return 0.0;
    float x1 = chf(CT+"ridge_xk1"); float x2 = chf(CT+"ridge_xk2");
    float r = (x - x1)/(x2 - x1);
    if (r <= 0.0 || r >= 1.0) return 0.0;
    return (ke - chf(CT+"ridge_k"))/(x2 - x1);
}
vector2 rise(float x) {
    float u = x - chf(CT+"ridge_x0");
    if (u <= 0.0) return {0, 0};
    float s1 = chf(CT+"ledge_s1");
    if (s1 <= 0.0) { float s = chf(CT+"ridge_s"); return set(u/s, 1.0/s); }
    float dl = chf(CT+"ledge_dl"); float s2 = chf(CT+"ledge_s2");
    float uL = (chf(CT+"h0") - chf(CT+"shelf_h") - dl)*s1;
    if (u <= uL) return set(u/s1, 1.0/s1);
    if (u <= uL + dl*s2) return set(uL/s1 + (u - uL)/s2, 1.0/s2);
    return set(uL/s1 + dl + (u - uL - dl*s2)/s1, 1.0/s1);
}
float chanw(float x; float zl) {
    return 0.5*(1.0 + tanh((abs(zl) - chf(CT+"ch_y0"))/chf(CT+"ch_w")))*clamp((x - chf(CT+"ch_x0"))/chf(CT+"ch_lx"), 0.0, 1.0);
}
// ---------------------------------------------------------------- FLIP49 の新しい項（g49_common.bed_z・bed_grad と同じ式）
int pgon() { return (chf(CT+"pg_hL") > 0.0 || chf(CT+"b_end") > 0.0 || chf(CT+"lag_xb") < 1e8) ? 1 : 0; }
float bofx(float x) {
    float be = chf(CT+"b_end");
    if (be <= 0.0) return 0.0;
    float x1 = chf(CT+"b_x1"); float x2 = chf(CT+"b_x2");
    return be*clamp((x - x1)/max(x2 - x1, 1e-9), 0.0, 1.0);
}
float dbofx(float x) {
    float be = chf(CT+"b_end");
    if (be <= 0.0) return 0.0;
    float x1 = chf(CT+"b_x1"); float x2 = chf(CT+"b_x2");
    float r = (x - x1)/max(x2 - x1, 1e-9);
    if (r <= 0.0 || r >= 1.0) return 0.0;
    return be/max(x2 - x1, 1e-9);
}
// 2 段の上り（u3_beds._rise）：1:s で水深 pg_hL まで、その先 1:pg_s2 がずっと続く
vector2 rise2(float x) {
    float u = x - chf(CT+"ridge_x0");
    if (u <= 0.0) return {0, 0};
    float s1 = chf(CT+"ridge_s"); float hL = chf(CT+"pg_hL"); float s2 = chf(CT+"pg_s2");
    float h0 = chf(CT+"h0");
    if (s2 > 0.0 && hL > chf(CT+"shelf_h")) {
        float uL = (h0 - hL)*s1;
        if (u <= uL) return set(u/s1, 1.0/s1);
        return set((h0 - hL) + (u - uL)/s2, 1.0/s2);
    }
    return set(u/s1, 1.0/s1);
}
float bedy_pg(float x; float zl) {
    float h0 = chf(CT+"h0");
    if (chf(CT+"ridge_on") < 0.5) return -h0;
    float hr = chf(CT+"shelf_h");
    float ye = max(abs(zl) - bofx(x), 0.0);
    float sh = 1.0/cosh(kofx(x)*ye/h0);
    vector2 R = rise2(x);
    float d = max(hr, h0 - R.x*sh*sh);
    float chh = chf(CT+"ch_h");
    if (chh > 0.0) { float w = chanw(x, zl); d = d*(1.0 - w) + max(d, chh)*w; }
    float xb = chf(CT+"lag_xb");
    if (xb < 1e8 && x > xb) { float lag = min(chf(CT+"lag_h"), hr + max(x - xb, 0.0)/chf(CT+"lag_s")); d = max(d, lag); }
    return -d;
}
vector2 bedgrad_pg(float x; float zl) {
    float h0 = chf(CT+"h0");
    if (chf(CT+"ridge_on") < 0.5) return {0, 0};
    float hr = chf(CT+"shelf_h");
    float b = bofx(x); float az = abs(zl);
    float o = (az > b) ? 1.0 : 0.0;
    float ye = max(az - b, 0.0);
    float dyex = -dbofx(x)*o; float dyey = sign(zl)*o;
    float k = kofx(x); float a = k*ye/h0;
    float sh = 1.0/cosh(a); float S = sh*sh; float th = tanh(a);
    vector2 R = rise2(x);
    float d = h0 - R.x*S;
    float dax = (dkofx(x)*ye + k*dyex)/h0; float day = k*dyey/h0;
    float ddx = -(R.y*S - 2.0*R.x*S*th*dax);
    float ddy = 2.0*R.x*S*th*day;
    if (d <= hr) { d = hr; ddx = 0.0; ddy = 0.0; }
    float chh = chf(CT+"ch_h");
    if (chh > 0.0) {
        float cw = chf(CT+"ch_w"); float lx = chf(CT+"ch_lx");
        float tq = tanh((abs(zl) - chf(CT+"ch_y0"))/cw);
        float g = 0.5*(1.0 + tq);
        float r = (x - chf(CT+"ch_x0"))/lx;
        float rc = clamp(r, 0.0, 1.0);
        float rp = (r > 0.0 && r < 1.0) ? 1.0/lx : 0.0;
        float w = g*rc; float wx = g*rp; float wy = 0.5*(1.0 - tq*tq)/cw*sign(zl)*rc;
        float D2 = max(d, chh);
        float D2x = (d > chh) ? ddx : 0.0; float D2y = (d > chh) ? ddy : 0.0;
        float nx = ddx*(1.0 - w) + D2x*w + (D2 - d)*wx;
        float ny = ddy*(1.0 - w) + D2y*w + (D2 - d)*wy;
        d = d*(1.0 - w) + D2*w;
        ddx = nx; ddy = ny;
    }
    float xb = chf(CT+"lag_xb");
    if (xb < 1e8 && x > xb) {
        float lh = chf(CT+"lag_h"); float ls = chf(CT+"lag_s");
        float raw = hr + max(x - xb, 0.0)/ls;
        float lag = min(lh, raw);
        if (lag > d) { ddx = (raw < lh) ? 1.0/ls : 0.0; ddy = 0.0; d = lag; }
    }
    return set(-ddx, -ddy);
}
// 海底の高さ（計画の座標。x：進む向き、zl：横）。新しい項が無ければ g48 と同じ式を同じ順に
float bedy(float x; float zl) {
    if (pgon()) return bedy_pg(x, zl);
    float h0 = chf(CT+"h0");
    float xt = chf(CT+"ridge_x0");
    if (chf(CT+"ridge_on") < 0.5) return -h0;
    float d = h0;
    if (x > xt) {
        float sh = 1.0/cosh(kofx(x)*zl/h0);
        if (chf(CT+"ledge_s1") > 0.0) { vector2 R = rise(x); d = h0 - R.x*sh*sh; }
        else d = h0 - (x - xt)*sh*sh/chf(CT+"ridge_s");
        float hs = chf(CT+"shelf_h");
        if (hs > 0.0) d = max(d, hs);
    }
    float chh = chf(CT+"ch_h");
    if (chh > 0.0) {
        float w = chanw(x, zl);
        d = d*(1.0 - w) + max(d, chh)*w;
    }
    return -d;
}
vector2 bedgrad(float x; float zl) {
    if (pgon()) return bedgrad_pg(x, zl);
    float h0 = chf(CT+"h0");
    float xt = chf(CT+"ridge_x0");
    if (chf(CT+"ridge_on") < 0.5) return {0, 0};
    float d = h0; float ddx = 0.0; float ddy = 0.0;
    if (x > xt) {
        float k = kofx(x);
        float a = k*zl/h0;
        float sh = 1.0/cosh(a); float S = sh*sh; float th = tanh(a);
        vector2 R;
        if (chf(CT+"ledge_s1") > 0.0) R = rise(x);
        else { float s = chf(CT+"ridge_s"); R = set((x - xt)/s, 1.0/s); }
        d = h0 - R.x*S;
        ddx = -(R.y*S - 2.0*R.x*S*th*dkofx(x)*zl/h0);
        ddy = 2.0*R.x*S*th*k/h0;
        float hs = chf(CT+"shelf_h");
        if (hs > 0.0 && d <= hs) { d = hs; ddx = 0.0; ddy = 0.0; }
    }
    float chh = chf(CT+"ch_h");
    if (chh > 0.0) {
        float cw = chf(CT+"ch_w"); float lx = chf(CT+"ch_lx");
        float tq = tanh((abs(zl) - chf(CT+"ch_y0"))/cw);
        float g = 0.5*(1.0 + tq);
        float r = (x - chf(CT+"ch_x0"))/lx;
        float rc = clamp(r, 0.0, 1.0);
        float rp = (r > 0.0 && r < 1.0) ? 1.0/lx : 0.0;
        float w = g*rc; float wx = g*rp; float wy = 0.5*(1.0 - tq*tq)/cw*sign(zl)*rc;
        float D2 = max(d, chh);
        float D2x = (d > chh) ? ddx : 0.0; float D2y = (d > chh) ? ddy : 0.0;
        float nx = ddx*(1.0 - w) + D2x*w + (D2 - d)*wx;
        float ny = ddy*(1.0 - w) + D2y*w + (D2 - d)*wy;
        ddx = nx; ddy = ny;
    }
    return set(-ddx, -ddy);
}
// 海底の SDF（海底の外で正。Static Object の collision）。side_pad は g48 と同じ
float bedsdf_out(float x; float y; float zl) {
    vector2 gr = bedgrad(x, zl);
    float d = (y - bedy(x, zl))/sqrt(1.0 + gr.x*gr.x + gr.y*gr.y);
    if (chf(CT+"side_pad") > 0.5) d = min(d, zl);
    return d;
}
float smooth01(float c0) { float c = clamp(c0, 0.0, 1.0); return c*c*(3.0 - 2.0*c); }
// 孤立波の表（g48 と同じ。FLIP49 は wave_on 0 で静かな水）
float sol_eta(float x) {
    if (chf(CT+"wave_on") < 0.5) return 0.0;
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    return volumesample(TABF, "eta", set(xq, 0.0, 0.0));
}
vector sol_vel(float x; float yv) {
    if (chf(CT+"wave_on") < 0.5) return {0, 0, 0};
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    float e = volumesample(TABF, "eta", set(xq, 0.0, 0.0));
    float zq = clamp(min(yv, e), detail(TABF, "z_lo", 0), detail(TABF, "z_hi", 0));
    return set(volumesample(TABF, "u", set(xq, zq, 0.0)), volumesample(TABF, "w", set(xq, zq, 0.0)), 0.0);
}
// ---------------------------------------------------------------- g47_tanklib の帯の道具（写した）
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
float walltaper(float x) {
    float L = chf(CT+"wall_taper_m");
    if (L <= 0.0) return 1.0;
    return smooth01((x - chf(CT+"x0"))/L);
}
float rampT(float t; float R) {
    if (R <= 0.0) return 1.0;
    float c = clamp(t/R, 0.0, 1.0);
    return 0.5 - 0.5*cos(PI*c);
}
float sf_chch(float a; float b) { return (exp(a - b) + exp(-a - b))/(1.0 + exp(-2.0*b)); }
float sf_shch(float a; float b) { return (exp(a - b) - exp(-a - b))/(1.0 + exp(-2.0*b)); }
// 組の包絡（set_P 0 なら 1）。FLIP49：set_cg > 0 なら遅れた時刻 t − (x − x_p)/set_cg で読む（2 段目の組の時だけ。既定 0 は g47 と同じ）
float sf_setenv(float t; float x) {
    float P = chf(CT+"set_P");
    if (P <= 0.0) return 1.0;
    float cg = chf(CT+"set_cg");
    float tr = (cg > 0.0) ? t - (x - chf(CT+"x_p"))/cg : t;
    float up = chf(CT+"set_up"); float fl = chf(CT+"set_flat"); float dn = chf(CT+"set_down");
    float tau = tr - P*floor(tr/P);
    if (tau < up) return 0.5 - 0.5*cos(PI*tau/up);
    if (tau < up + fl) return 1.0;
    if (tau < up + fl + dn) return 0.5 + 0.5*cos(PI*(tau - up - fl)/dn);
    return 0.0;
}
// 流れ関数の波（OUT_SF の表。g47_tanklib.sfwave と同じ式）
void sfwave(float x; float y; float t; float E; float eta; vector vel) {
    float B[] = detail(SFT, "sfB"); float Ec[] = detail(SFT, "sfE");
    float k = detail(SFT, "sfk", 0); float c = detail(SFT, "sfc", 0); float h = detail(SFT, "sfh", 0); float Ub = detail(SFT, "sfUb", 0);
    float X = x - chf(CT+"x_p") - c*t;
    float e = 0.0;
    for (int j = 0; j < len(Ec); j++) e += Ec[j]*cos(j*k*X);
    float Y = max(min(y, e) + h, 0.0);
    float u = c - Ub; float w = 0.0;
    for (int j = 1; j <= len(B); j++) {
        float a = j*k*Y; float b = j*k*h;
        u += j*k*B[j - 1]*sf_chch(a, b)*cos(j*k*X);
        w += j*k*B[j - 1]*sf_shch(a, b)*sin(j*k*X);
    }
    vel = E*set(u, w, 0.0);
    eta = E*e;
}
// ---------------------------------------------------------------- FLIP49 の帯（入口：流れ関数の波へ x、横は 0。出口：スポンジ）
vector relax_apply(vector pl; vector vel; float t; float dts) {
    vector v = vel;
    float x = pl.x;
    float xg = chf(CT+"xg_end");
    if (chf(CT+"relax_on") > 0.5 && x < xg && chf(CT+"relax_g") > 0.0) {
        float x0 = chf(CT+"x0");
        float w = clamp(relaxw((xg - x)/max(xg - x0, 1e-6))*chf(CT+"relax_g"), 0.0, 1.0);
        float wdt = 1.0 - pow(1.0 - w, dts/chf(CT+"dt0"));
        float wt = walltaper(x);
        float E = chf(CT+"in_gain")*wt*rampT(t, chf(CT+"ramp_s"))*sf_setenv(t, x);
        float eta = 0.0; vector tv = {0, 0, 0};
        if (chf(CT+"sf_on") > 0.5) sfwave(x, pl.y, t, E, eta, tv);
        float ux = tv.x;
        if (chf(CT+"duabs_on") > 0.5) ux += wt*detail(VDT, "du_abs", 0);
        v = set(lerp(v.x, ux, wdt), v.y, lerp(v.z, 0.0, wdt));      // 縦の流速は寄せない
    }
    float xa0 = chf(CT+"xa0"); float x1 = chf(CT+"x0") + chf(CT+"Lx");
    if (chf(CT+"abs_on") > 0.5 && x > xa0) {
        float chi = clamp((x - xa0)/max(x1 - xa0, 1e-6), 0.0, 1.0);
        float w2 = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*dts);
        v = set(lerp(v.x, 0.0, w2), v.y, lerp(v.z, 0.0, w2));
    }
    return v;
}
// 水の量の直しの目標の発散（段 A：窓 vol_x0〜vol_x1、段 B：帯の芯 hold_x0〜hold_x1）
float vc_divergence(vector pl) {
    float d = 0.0;
    if (chf(CT+"volcorr_on") > 0.5) {
        float xa = chf(CT+"vol_x0"); float xb = chf(CT+"vol_x1");
        if (xb <= xa || (pl.x >= xa && pl.x <= xb)) d = detail(VDT, "vol_div", 0);
    }
    if (chf(CT+"hold_on") > 0.5 && pl.x >= chf(CT+"hold_x0") && pl.x <= chf(CT+"hold_x1")) d += detail(VDT, "vol_div_band", 0);
    return d;
}
''' % (CT, TABF, SFT, VDT)

BODIES = {
    # 小刻みの数の記録（FLIP45・48 と同じ）
    "/obj/G49_SIM/substep_count": r'''
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
    "/obj/G49_SETUP/bed_height": r'''
vector pl = plan(@P);
@P.y = bedy(pl.x, pl.z) + chf(CT+"oy");
''',
    "/obj/G49_SETUP/bed_sdf_value": r'''
vector pl = plan(@P);
f@collision = bedsdf_out(pl.x, pl.y, pl.z);
''',
    "/obj/G49_SETUP/vel_value": r'''
vector pl = plan(@P);
v@vel = sol_vel(pl.x, pl.y);
''',
    # 流れ関数の表（CTRL の sf_tab「h k c Ub N B1..BN E0..EN」→ 64 ビットの detail。g47_tanklib と同じ）
    "/obj/G49_SETUP/sf_table": r'''
string s[] = split(chs(CT+"sf_tab"), " ");
f@sfh = 0.0; f@sfk = 0.0; f@sfc = 0.0; f@sfUb = 0.0; i@sfN = 0;
float B[]; float E[];
if (len(s) >= 5) {
    f@sfh = atof(s[0]); f@sfk = atof(s[1]); f@sfc = atof(s[2]); f@sfUb = atof(s[3]);
    int N = atoi(s[4]);
    if (len(s) == 5 + N + N + 1) {
        resize(B, N); resize(E, N + 1);
        for (int i = 0; i < N; i++) B[i] = atof(s[5 + i]);
        for (int i = 0; i <= N; i++) E[i] = atof(s[5 + N + i]);
        i@sfN = N;
    } else {
        i@sfN = -1;
    }
}
f[]@sfB = B; f[]@sfE = E;
''',
    # 帯（格子の流速 vel。面に置いた場は成分ごとに、その面の位置 @P で呼ばれる。FLIP45・47 と同じ使い方）
    "/obj/G49_SIM/relax_zones": r'''
vector pl = plan(@P);
v@vel = relax_apply(pl, v@vel, f@Time + chf(CT+"t_off"), f@TimeInc);
''',
    # 水の量の直し（FLIP の物体の divergence。圧力を解く前に目標の発散として入る）
    "/obj/G49_SIM/vc_div": r'''
f@divergence = vc_divergence(plan(@P));
''',
    # 確かめ：点の属性 x・y・t（計画の座標）で流れ関数の波を E = 1 で（64 ビット）
    "/obj/G49_SETUP/sf_probe": r'''
float eta; vector tv;
sfwave(f@px, f@py, f@pt, 1.0, eta, tv);
f@eta_v = eta; f@u_v = tv.x; f@w_v = tv.y;
''',
    # 確かめ：点の属性 px・py・pz（計画の座標）・v0（流速）・pt・dts で帯の関数（DOP の relax_zones と同じ relax_apply）と発散
    "/obj/G49_SETUP/relax_probe": r'''
vector pl = set(f@px, f@py, f@pz);
v@v1 = relax_apply(pl, v@v0, f@pt, f@dts);
f@div = vc_divergence(pl);
''',
}

# 孤立波の表を作る Python SOP（g48_tanklib.PYSOP をそのまま使う。wave_on 0 なら 0 の表）
import importlib.util as _ilu, os as _os
_spec = _ilu.spec_from_file_location("g48_tanklib_ro", _os.path.join(r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip48", "g48_tanklib.py"))
_g48t = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_g48t)
PYSOP = _g48t.PYSOP

# 目標の発散・Sommerfeld の項のファイル（g49_run.py が <記録>/volcorr/vd_<コマ>.txt に「vol_div vol_div_band du_abs」を書く）を時刻で読む
PYSOP_VOLDIV = r'''
import os, math
import hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
for nm in ("vol_div", "vol_div_band", "du_abs"):
    geo.addAttrib(hou.attribType.Global, nm, 0.0)
geo.addAttrib(hou.attribType.Global, "vol_frame", 0)
geo.addAttrib(hou.attribType.Global, "vol_src", "")
fr = node.evalParm("fr")
d = node.evalParm("vdir")
f = int(math.ceil(fr - 1e-6))
vals = [0.0, 0.0, 0.0]; src = "none"
if d:
    p = os.path.join(d, "vd_%05d.txt" % f)
    if os.path.exists(p):
        try:
            q = open(p).read().split()
            for i in range(min(3, len(q))):
                vals[i] = float(q[i])
            src = p
        except Exception as e:
            src = "error %r" % (e,)
geo.setGlobalAttribValue("vol_div", float(vals[0]))
geo.setGlobalAttribValue("vol_div_band", float(vals[1]))
geo.setGlobalAttribValue("du_abs", float(vals[2]))
geo.setGlobalAttribValue("vol_frame", f)
geo.setGlobalAttribValue("vol_src", src)
'''


def snippet(path):
    return VEX_HEAD + BODIES[path]
