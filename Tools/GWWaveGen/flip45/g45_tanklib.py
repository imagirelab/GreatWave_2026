# -*- coding: utf-8 -*-
"""FLIP45：3D の水槽（Houdini/FLIP45/g45_tank.hiplc）の VEX。g45_build_tank.py と煙の試しの道具が使う。
FLIP44 の g44_tanklib.py（Tools/GWWaveGen/flip44、変えていない）を写して 3D に直した（計画 plan_ja.md §3・§3.1・§4.1・§10.1）。
風と礁の部分は持ち込まない。VEX は CTRL の値と入口の表（OUT_TABLE の体積 eta・U・V）だけを読む。計算ごとにコードを書き換えない。

座標：Houdini の中は計画の座標を o = (ox, oy, oz)（CTRL）だけずらした所に置く（Houdini = 計画 + o。g45_common.box、読み方 R1）。
  VEX は始めに計画の座標 pl = @P − o に戻し、帯・表・深さは全部計画の座標で読む：x＝波の進む向き、y＝上（静かな水面 0、箱の底 −20 m が海底）、
  z＝横（z = 0 が対称の面、閉じた壁）。
入口の表（g45_inlet_table.py が作り、g45_run.py が bgeo の体積にする）：体積の軸 X = x、Y = 時刻 t（s）、Z = 横 z。
  水面 eta と水平の流速。流速は深さごとの表（U0..・V0..、Ω の深さの形で割った値。CTRL の tab_levels・tab_dz）か、水面の高さの U・V
  （狭い帯の近似、tab_levels ≤ 1）。どちらも Ω の深さの形 cosh(k0 (z' + h))/cosh(k0 h) を掛ける。z' = h (y − η)/(h + η) を −h〜0 に切る
  （水面より上は水面の値。FLIP44 の groupwave と同じ伸ばし）。
帯（計画 §3.1。寄せるのは水平の二つの流速 vel.x・vel.z だけ。縦の流速と水面は寄せない）：
  入口の帯 in0〜in1（in0 は箱の上流の壁）：FLIP42 の重み relaxw(χ)（χ は内の縁で 0、壁で 1）を小刻みの長さに合わせ、表の目標へ寄せる。
    in_tgt = 0 なら目標は 0（煙の試し S3b）。
  横の帯 sd0〜sd1（sd1 は横の外の壁）：x ≤ sd_gen は入口と同じ重みで表の目標へ寄せて波を起こす。x ≥ sd_sw は有限の速さ σ χ^p で
    静かな水（0）へ寄せて吸う。sd_gen〜sd_sw は、s = smooth01((x − sd_gen)/(sd_sw − sd_gen)) で、目標に (1 − s) を掛け、重みを
    起こす重みから吸う重みへ s でつなぐ（計画の読み方 R5。record_ja.md）。
  出口の帯 ex0〜ex1（ex1 は箱の下流の壁）：ex_mode 0 は σ χ^p で 0 へ寄せる（吸う）。ex_mode 1 は表の目標へ FLIP42 の重みで寄せる
    （煙の試し S3b だけ。下流の壁から上流へ向かう波を起こす）。
  帯が重なる角は、重みは大きい方、目標の掛け数は掛け算（入口と横の起こす所は同じ目標、出口と横の吸う所は 0）。
  目標に掛ける E（計画 §3.1、見直し H2）＝ smooth01((x − x0)/L_w) × smooth01((W − z)/L_w)。x0 は箱の上流の壁、W は横の外の壁、
    L_w = wall_taper_m（帯の厚さの 1/4）。横の帯がない時（sd_on 0、2D の板の試し）は横のなだらかさを掛けない。ex_mode 1 の時は
    下流の壁の近くにも smooth01((ex1 − x)/L_w) を掛ける。始めのなだらかさ（FLIP44 の rampT）はない（表が立ち上げ tanh(t/T) を持つ）。
  amp_gain：目標の全体に掛ける数（静かな水の試しは 0。本番は 1。入口の利得は表の中に横の形ごとに入っている）。
時刻：t = f@Time + t_off（コマ f の時刻は t_off + (f − 1)/24。造波板から解く窓は t_off = −2 s）。
小刻みの記録：粒子の Geometry の detail に、そのコマの小刻みの数 ss_n と最後の小刻みの長さ ss_dt を書く（FLIP42・44 と同じ）。
"""

CT = "/obj/G45_SETUP/CTRL/"
TABF = "op:/obj/G45_SETUP/OUT_TABLE"

VEX_HEAD = r'''
#define CT "%s"
#define TABF "%s"
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
float smooth01(float c0) { float c = clamp(c0, 0.0, 1.0); return c*c*(3.0 - 2.0*c); }
// 目標（表の線形の場）。gm は全部の掛け数（amp_gain・E・帯の切り替え）。返り値の vel は水平の二つ（x, 0, z）
// 表の流速：tab_levels ≥ 2 なら深さごとの表（Ω の深さの形で割った値 U0..・V0..、深さ 0, −tab_dz, −2 tab_dz, ...）を z' で線形に補う。
// 1 以下なら水面の高さの U・V（狭い帯の近似）。どちらも最後に Ω の深さの形を掛ける。
void target(float x; float yv; float zl; float t; float gm; float eta; vector vel) {
    vector tp = set(x, t, zl);
    eta = gm*volumesample(TABF, "eta", tp);
    float h = chf(CT+"h0");
    float k0 = chf(CT+"k0");
    float ye = clamp(h*(yv - eta)/(h + eta), -h, 0.0);
    float prof = cosh(k0*(ye + h))/cosh(k0*h);
    int nl = int(chf(CT+"tab_levels") + 0.5);
    float U = 0.0; float V = 0.0;
    if (nl >= 2) {
        float f = clamp(-ye/chf(CT+"tab_dz"), 0.0, nl - 1.0);
        int k = min(int(floor(f)), nl - 2);
        float w = f - k;
        U = lerp(volumesample(TABF, sprintf("U%%d", k), tp), volumesample(TABF, sprintf("U%%d", k + 1), tp), w);
        V = lerp(volumesample(TABF, sprintf("V%%d", k), tp), volumesample(TABF, sprintf("V%%d", k + 1), tp), w);
    } else {
        U = volumesample(TABF, "U", tp);
        V = volumesample(TABF, "V", tp);
    }
    vel = set(gm*U*prof, 0.0, gm*V*prof);
}
// 壁のなだらかさ E（計画 §3.1）
float wallE(float x; float zl) {
    float Lw = chf(CT+"wall_taper_m");
    if (Lw <= 0.0) return 1.0;
    float e = smooth01((x - chf(CT+"x0"))/Lw);
    if (chf(CT+"sd_on") > 0.5) e *= smooth01((chf(CT+"W") - zl)/Lw);
    if (chf(CT+"ex_mode") > 0.5) e *= smooth01((chf(CT+"ex1") - x)/Lw);
    return e;
}
// 帯ごとの目標の掛け数（in_gain：入口の帯、sd_gain：横の帯。既定は 1。入口の利得を帯ごとに掛ける案のため。読み方 R17）
float bandgain(float x; float zl) {
    if (chf(CT+"in_on") > 0.5 && x < chf(CT+"in1")) return chf(CT+"in_gain");
    if (chf(CT+"sd_on") > 0.5 && zl > chf(CT+"sd0")) return chf(CT+"sd_gain");
    return 1.0;
}
// 帯の重み（この小刻みで寄せる割合 wdt）と目標の掛け数 ftg。帯の外なら wdt = 0
void bands(float x; float zl; float dts; float wdt; float ftg) {
    float dt0 = chf(CT+"dt0"); float rg = chf(CT+"relax_g");
    float sig = chf(CT+"abs_sigma"); float pw = chf(CT+"abs_pow");
    wdt = 0.0; ftg = 1.0;
    if (chf(CT+"in_on") > 0.5) {
        float a = chf(CT+"in0"); float b = chf(CT+"in1");
        if (x < b) {
            float chi = clamp((b - x)/(b - a), 0.0, 1.0);
            float w = clamp(relaxw(chi)*rg, 0.0, 1.0);
            wdt = max(wdt, 1.0 - pow(1.0 - w, dts/dt0));
            if (chf(CT+"in_tgt") < 0.5) ftg = 0.0;
        }
    }
    if (chf(CT+"sd_on") > 0.5) {
        float a = chf(CT+"sd0"); float b = chf(CT+"sd1");
        if (zl > a) {
            float chi = clamp((zl - a)/(b - a), 0.0, 1.0);
            float g0 = chf(CT+"sd_gen"); float g1 = chf(CT+"sd_sw");
            float s = smooth01((x - g0)/max(g1 - g0, 1e-6));
            float wg = 1.0 - pow(1.0 - clamp(relaxw(chi)*rg, 0.0, 1.0), dts/dt0);
            float wa = 1.0 - exp(-sig*pow(chi, pw)*dts);
            wdt = max(wdt, lerp(wg, wa, s));
            ftg *= (1.0 - s);
        }
    }
    {
        float a = chf(CT+"ex0"); float b = chf(CT+"ex1");
        if (x > a) {
            float chi = clamp((x - a)/(b - a), 0.0, 1.0);
            if (chf(CT+"ex_mode") < 0.5) {
                wdt = max(wdt, 1.0 - exp(-sig*pow(chi, pw)*dts));
                ftg = 0.0;
            } else {
                float w = clamp(relaxw(chi)*rg, 0.0, 1.0);
                wdt = max(wdt, 1.0 - pow(1.0 - w, dts/dt0));
            }
        }
    }
}
''' % (CT, TABF)

BODIES = {
    # 帯（格子の流速 vel。面に置いた場は成分ごとに、その面の位置 @P で呼ばれる）
    "/obj/G45_SIM/relax_zones": r'''
vector pl = @P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));      // 計画の座標（Houdini = 計画 + o）
float x = pl.x; float yv = pl.y; float zl = pl.z;
float wdt; float ftg;
bands(x, zl, f@TimeInc, wdt, ftg);
if (wdt > 0.0) {
    float t = f@Time + chf(CT+"t_off");
    float gm = chf(CT+"amp_gain")*ftg*wallE(x, zl)*bandgain(x, zl);
    float eta = 0.0; vector tv = {0, 0, 0};
    if (gm != 0.0 && chf(CT+"tab_on") > 0.5) target(x, yv, zl, t, gm, eta, tv);
    v@vel = set(lerp(v@vel.x, tv.x, wdt), v@vel.y, lerp(v@vel.z, tv.z, wdt));   // 水平の二つだけ寄せる
}
''',
    # 小刻みの数の記録（FLIP42・44 と同じ。粒子の Geometry の detail。Particle Velocity の入口で毎小刻み 1 回）
    "/obj/G45_SIM/substep_count": r'''
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
    # 煙の試し S4：SOP の点で、帯の VEX と同じ関数の値を読む（点の属性 t・wdt_dt を入力に、eta・tv・wdt・ftg・E を書く）
    "/obj/G45_SETUP/s4_probe": r'''
vector pl = @P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
float wdt; float ftg;
bands(pl.x, pl.z, f@dts, wdt, ftg);
float gm = chf(CT+"amp_gain")*ftg*wallE(pl.x, pl.z)*bandgain(pl.x, pl.z);
float eta = 0.0; vector tv = {0, 0, 0};
if (gm != 0.0 && chf(CT+"tab_on") > 0.5) target(pl.x, pl.y, pl.z, f@t, gm, eta, tv);
f@eta_t = eta; v@vel_t = tv; f@wdt = wdt; f@ftg = ftg; f@E = wallE(pl.x, pl.z); f@gm = gm;
f@raw_eta = volumesample(TABF, "eta", set(pl.x, f@t, pl.z));
''',
}


def snippet(path):
    return VEX_HEAD + BODIES[path]
