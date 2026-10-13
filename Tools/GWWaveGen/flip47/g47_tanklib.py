# -*- coding: utf-8 -*-
"""FLIP47：2D の板の水槽（Houdini/FLIP47/g47_tank.hiplc）の VEX と、孤立波の npz を読む Python SOP のコード。g47_build_tank.py が使う。
FLIP44 の g44_tanklib.py と FLIP46 の g46_tanklib.py（どちらも変えていない）を写して直した。
  FLIP44 から：板の水槽、入口の表と入口の帯（緩和）・吸う帯（スポンジ）の VEX、小刻みの数の記録。風の道具は持ち込まない（重力だけ）。
  FLIP46 から：Houdini = 計画 + o のずらし、孤立波の解の表（OUT_SOL の体積 eta・u・w）を読む sol_eta・sol_vel、npz を読む Python SOP。
  変えた所：海底を折れ線（CTRL の bed_prof「x0 d0 x1 d1 ...」→ OUT_BEDTAB の detail の 64 ビットの配列 bx・bd）にした。両端の外は端の水深で平ら。
    衝突の SDF は折れ線（両端の外へ水平に延ばす）への本当の距離（海底の外で正）。FLIP44 の鉛直の距離・FLIP46 の傾きで割る近似は、
    折れ目（斜面の足・棚の始め）で距離を間違えるため。
  入口の帯・吸う帯は CTRL の relax_on・abs_on（既定 0）で切ってある（孤立波だけの計算。Enable Solver が wrangle ごと止める）。
座標：VEX は始めに計画の座標 pl = @P − o に戻す。x＝進む向き、y＝上（静かな水面 0）、z＝板の厚さ（真ん中 0）。
wrangle の入力の約束：入力 1 に OUT_SOL（解の表）、入力 2 に OUT_BEDTAB（海底の表）。DOP の帯の wrangle は入口の表を op: の参照で読む。
"""

CT = "/obj/G47_SETUP/CTRL/"
TABF = "1"        # 解の表（OUT_SOL）は SOP の wrangle の 2 つ目の入力
BEDF = "2"        # 海底の表（OUT_BEDTAB）は 3 つ目の入力
INL = "op:/obj/G47_SETUP/OUT_INLET"

VEX_HEAD = r'''
#define CT "%s"
#define TABF %s
#define BEDF %s
#define INL "%s"
vector plan(vector P) { return P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz")); }
// 海底の高さ（計画の y）。折れ線の線形の補い、両端の外は端の水深
float bedy(float x) {
    float bx[] = detail(BEDF, "bx"); float bd[] = detail(BEDF, "bd");
    int n = len(bx);
    if (n == 0) return -chf(CT+"h0");
    if (x <= bx[0]) return -bd[0];
    if (x >= bx[n - 1]) return -bd[n - 1];
    for (int i = 0; i < n - 1; i++) {
        if (x <= bx[i + 1]) {
            float L = bx[i + 1] - bx[i];
            float t = (L > 0.0) ? (x - bx[i])/L : 1.0;
            return -lerp(bd[i], bd[i + 1], t);
        }
    }
    return -bd[n - 1];
}
// 海底の SDF（海底の外で正）：折れ線（両端の外へ水平に延ばす）への本当の距離。符号は bedy との上下
float bedsdf_out(float x; float y) {
    float bx[] = detail(BEDF, "bx"); float bd[] = detail(BEDF, "bd");
    int n = len(bx);
    if (n == 0) return y + chf(CT+"h0");
    vector2 p = set(x, y);
    float d = 1e30;
    if (x <= bx[0]) d = min(d, abs(y + bd[0])); else d = min(d, length(p - set(bx[0], -bd[0])));
    if (x >= bx[n - 1]) d = min(d, abs(y + bd[n - 1])); else d = min(d, length(p - set(bx[n - 1], -bd[n - 1])));
    for (int i = 0; i < n - 1; i++) {
        vector2 a = set(bx[i], -bd[i]); vector2 b = set(bx[i + 1], -bd[i + 1]);
        vector2 ab = b - a;
        float L2 = dot(ab, ab);
        float t = (L2 > 0.0) ? clamp(dot(p - a, ab)/L2, 0.0, 1.0) : 0.0;
        d = min(d, length(p - (a + t*ab)));
    }
    return (y >= bedy(x)) ? d : -d;
}
// 孤立波の水面（wave_on 0 なら静かな水）
float sol_eta(float x) {
    if (chf(CT+"wave_on") < 0.5) return 0.0;
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    return volumesample(TABF, "eta", set(xq, 0.0, 0.0));
}
// 孤立波の流速（Houdini の向き：x、上、厚さ 0）。水面より上は水面の値（表の中で列のいちばん上の値で埋めてある）
vector sol_vel(float x; float yv) {
    if (chf(CT+"wave_on") < 0.5) return {0, 0, 0};
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    float e = volumesample(TABF, "eta", set(xq, 0.0, 0.0));
    float zq = clamp(min(yv, e), detail(TABF, "z_lo", 0), detail(TABF, "z_hi", 0));
    return set(volumesample(TABF, "u", set(xq, zq, 0.0)), volumesample(TABF, "w", set(xq, zq, 0.0)), 0.0);
}
float relaxw(float chi) {
    float c = clamp(chi, 0.0, 1.0);
    return (exp(pow(c, 3.5)) - 1.0)/(exp(1.0) - 1.0);
}
float smooth01(float c0) { float c = clamp(c0, 0.0, 1.0); return c*c*(3.0 - 2.0*c); }
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
// 入口の表の成分の線形の重ね合わせ（水深 h0。FLIP44 と同じ）。E は壁の近くと始めのなだらかさの掛け算
void groupwave(float x; float y; float t; float E; float eta; vector vel) {
    float fr[] = detail(INL, "freq"); float am[] = detail(INL, "amp");
    float ph[] = detail(INL, "phase"); float kk[] = detail(INL, "k");
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
''' % (CT, TABF, BEDF, INL)

BODIES = {
    # 海底の表（CTRL の bed_prof → 64 ビットの detail の配列）
    "/obj/G47_SETUP/bed_table": r'''
string s[] = split(chs(CT+"bed_prof"), " ");
int n = len(s)/2;
float bx[]; float bd[];
resize(bx, n); resize(bd, n);
for (int i = 0; i < n; i++) { bx[i] = atof(s[2*i]); bd[i] = atof(s[2*i + 1]); }
f[]@bx = bx; f[]@bd = bd;
i@nbed = n;
''',
    # 海底の面（表示と Static Object の形。衝突は体積で）
    "/obj/G47_SETUP/bed_height": r'''
vector pl = plan(@P);
@P.y = bedy(pl.x) + chf(CT+"oy");
''',
    # 海底の SDF の値（Static Object の proxy volume。海底の中で負）
    "/obj/G47_SETUP/bed_sdf_value": r'''
vector pl = plan(@P);
f@collision = bedsdf_out(pl.x, pl.y);
''',
    # 初めの格子の流速（FLIP37 の誤り：深い格子の流速が 0 から始まらないように、解の値を入れる）
    "/obj/G47_SETUP/vel_value": r'''
vector pl = plan(@P);
v@vel = sol_vel(pl.x, pl.y);
''',
    # 入口の表（CTRL の inlet_tab「f a φ k」を成分の数だけ並べた文字）→ 64 ビットの detail の配列（FLIP44 と同じ）
    "/obj/G47_SETUP/inlet_table": r'''
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
    # 入口の帯・吸う帯（格子の流速 vel。FLIP44 と同じ式を計画の座標で。relax_on・abs_on が 0 なら Enable Solver ごと止まる）
    "/obj/G47_SIM/relax_zones": r'''
vector pl = plan(@P);
float x = pl.x;
float t = f@Time;                       // Houdini の時刻（コマ 1 が 0 s）
float xg = chf(CT+"xg_end");
if (chf(CT+"relax_on") > 0.5 && x < xg && chf(CT+"relax_g") > 0.0) {
    float x0 = chf(CT+"x0");
    float w = clamp(relaxw((xg - x)/max(xg - x0, 1e-6))*chf(CT+"relax_g"), 0.0, 1.0);
    float wdt = 1.0 - pow(1.0 - w, f@TimeInc/chf(CT+"dt0"));   // 小刻みの長さに合わせる（FLIP42・44 と同じ）
    float E = walltaper(x)*rampT(t, chf(CT+"ramp_s"));
    float eta; vector tv;
    groupwave(x, pl.y, t, E, eta, tv);
    v@vel = set(lerp(v@vel.x, tv.x, wdt), v@vel.y, v@vel.z);   // 水平だけ寄せる
}
float xa0 = chf(CT+"xa0"); float x1 = chf(CT+"x0") + chf(CT+"Lx");
if (chf(CT+"abs_on") > 0.5 && x > xa0) {
    float chi = clamp((x - xa0)/max(x1 - xa0, 1e-6), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc);
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''',
    # 小刻みの数の記録（FLIP42・44・46 と同じ。粒子の Geometry の detail。Particle Velocity の入口で毎小刻み 1 回）
    "/obj/G47_SIM/substep_count": r'''
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
}

# 解の表を作る Python SOP（g46_tanklib.PYSOP の写し。npz → 体積 eta・u・w。u_ext・w_ext があればそれを使う。並びが [x, z] でも [z, x] でも受ける。
# 等間隔でなければ等間隔に直す。無次元の npz（h0 = 1）なら、長さを CTRL の h0 倍、流速を √(g h0) 倍にする）
PYSOP = r'''
import os, json, hashlib
import numpy as np
import hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
p = node.evalParm("npz")
on = node.evalParm("wave_on") > 0.5
H0C = node.evalParm("h0")
geo.addAttrib(hou.attribType.Prim, "name", "")
for nm in ("x_lo", "x_hi", "z_lo", "z_hi", "c", "x0", "h0", "dx", "dz", "scale_len", "scale_vel"):
    geo.addAttrib(hou.attribType.Global, nm, 0.0)
geo.addAttrib(hou.attribType.Global, "src", "")
geo.addAttrib(hou.attribType.Global, "nan_filled", 0)


def uniform(a, v, axis):
    d = np.diff(a)
    if np.allclose(d, d[0], rtol=1e-6, atol=1e-9):
        return a, v
    h = float(np.min(d)); n = int(round((a[-1] - a[0])/h)) + 1
    a2 = a[0] + h*np.arange(n)
    v2 = np.apply_along_axis(lambda c: np.interp(a2, a, c), axis, v)
    return a2, v2


def put(nm, arr, bb):
    arr = np.ascontiguousarray(arr.astype(np.float32))
    nz_, ny_, nx_ = arr.shape
    vol = geo.createVolume(nx_, ny_, nz_, bb)
    vol.setAttribValue("name", nm)
    vol.setAllVoxelsFromString(arr.tobytes())


if on:
    if not os.path.exists(p):
        raise hou.NodeError("孤立波の npz がない: %s" % p)
    d = np.load(p)
    x = np.asarray(d["x"], dtype=np.float64).ravel(); z = np.asarray(d["z"], dtype=np.float64).ravel()
    eta = np.asarray(d["eta"], dtype=np.float64).ravel()
    ext = "u_ext" in d.files and "w_ext" in d.files
    u = np.asarray(d["u_ext" if ext else "u"], dtype=np.float64); w = np.asarray(d["w_ext" if ext else "w"], dtype=np.float64)
    if u.shape == (len(x), len(z)) and len(x) != len(z):
        u = u.T; w = w.T
    if u.shape != (len(z), len(x)) or w.shape != u.shape or eta.shape != x.shape:
        raise hou.NodeError("npz の形が違う: x %s z %s eta %s u %s w %s" % (x.shape, z.shape, eta.shape, u.shape, w.shape))
    h0f = float(d["h0"]) if "h0" in d.files else H0C
    sl = sv = 1.0
    if abs(h0f - 1.0) < 1e-9:
        sl = H0C; sv = (9.80665*H0C) ** 0.5
    x = x*sl; z = z*sl; eta = eta*sl; u = u*sv; w = w*sv
    c = float(d["c"])*sv if "c" in d.files else 0.0
    x0 = float(d["x0"])*sl if "x0" in d.files else 0.0
    nf = int((~np.isfinite(u)).sum() + (~np.isfinite(w)).sum())
    for a in (u, w):
        for j in range(a.shape[1]):
            col = a[:, j]; ok = np.isfinite(col)
            if not ok.any():
                col[:] = 0.0; continue
            i = np.where(ok)[0]
            col[:i[0]] = col[i[0]]; col[i[-1] + 1:] = col[i[-1]]
            bad = ~np.isfinite(col)
            if bad.any():
                col[bad] = np.interp(np.where(bad)[0], i, col[i])
    x, eta = uniform(x, eta, 0)
    xs_u = np.asarray(d["x"], dtype=np.float64).ravel()*sl
    _, u = uniform(xs_u, u, 1); _, w = uniform(xs_u, w, 1)
    zs_u = z
    z, u = uniform(zs_u, u, 0); _, w = uniform(zs_u, w, 0)
    dx = float(x[1] - x[0]); dz = float(z[1] - z[0])
    put("eta", eta[None, None, :], hou.BoundingBox(x[0] - 0.5*dx, -0.5, -0.5, x[-1] + 0.5*dx, 0.5, 0.5))
    bb = hou.BoundingBox(x[0] - 0.5*dx, z[0] - 0.5*dz, -0.5, x[-1] + 0.5*dx, z[-1] + 0.5*dz, 0.5)
    put("u", u[None, :, :], bb); put("w", w[None, :, :], bb)
    hsh = hashlib.sha256(open(p, "rb").read()).hexdigest()
    for k, v in dict(x_lo=x[0], x_hi=x[-1], z_lo=z[0], z_hi=z[-1], c=c, x0=x0, h0=h0f*sl, dx=dx, dz=dz, scale_len=sl, scale_vel=sv).items():
        geo.setGlobalAttribValue(k, float(v))
    geo.setGlobalAttribValue("src", "%s sha256 %s%s" % (p, hsh[:16], " (u_ext, w_ext)" if ext else ""))
    geo.setGlobalAttribValue("nan_filled", nf)
else:
    bb = hou.BoundingBox(-0.5, -0.5, -0.5, 1.5, 1.5, 0.5)
    for nm in ("eta", "u", "w"):
        put(nm, np.zeros((1, 2, 2)), bb)
    for k, v in dict(x_lo=0.0, x_hi=1.0, z_lo=0.0, z_hi=1.0, h0=H0C, dx=1.0, dz=1.0, scale_len=1.0, scale_vel=1.0).items():
        geo.setGlobalAttribValue(k, float(v))
    geo.setGlobalAttribValue("src", "none (wave_on 0)")
'''


def snippet(path):
    return VEX_HEAD + BODIES[path]


def inlet_tab_string(freqs, amps, phases, ks):
    """入口の表の文字（成分ごとに「f a φ k」、repr の桁で 64 ビットのまま渡す。FLIP44 と同じ）。"""
    out = []
    for f, a, p, k in zip(freqs, amps, phases, ks):
        out += [repr(float(f)), repr(float(a)), repr(float(p)), repr(float(k))]
    return " ".join(out)


# ====================================================================== 2026-10-13 周期の波の実験の役（Claude）が足した物
# 流れ関数の規則波（g47_sfwave.py の解。periodic_design_ja.md §7）を入口の帯の目標にする枝と、組（セット）の包絡。
# 使うのは周期の波の場面（Houdini/FLIP47/g47_tank_periodic.hiplc、g47_build_tank.py --periodic で作る）だけ。上の VEX_HEAD・BODIES は変えていない
# （g47_tank.hiplc と同じ文字のまま）。CTRL の sf_on 0（既定）なら、relax_zones_sf は上の relax_zones と同じ式（groupwave、水平だけ寄せる）。
SFT = "op:/obj/G47_SETUP/OUT_SF"

VEX_SF = r'''
#define SFT "%s"
// sinh(a)/cosh(b)・cosh(a)/cosh(b)（a, b ≥ 0。桁あふれを避ける。g47_sfwave._sh_over_ch・_ch_over_ch と同じ式）
float sf_chch(float a; float b) { return (exp(a - b) + exp(-a - b))/(1.0 + exp(-2.0*b)); }
float sf_shch(float a; float b) { return (exp(a - b) - exp(-a - b))/(1.0 + exp(-2.0*b)); }
// 組の包絡（set_P 0 なら 1）：周期 P の中で、上り set_up（余弦）、満ち set_flat、下り set_down（余弦）、残りは 0
float sf_setenv(float t) {
    float P = chf(CT+"set_P");
    if (P <= 0.0) return 1.0;
    float up = chf(CT+"set_up"); float fl = chf(CT+"set_flat"); float dn = chf(CT+"set_down");
    float tau = t - P*floor(t/P);
    if (tau < up) return 0.5 - 0.5*cos(PI*tau/up);
    if (tau < up + fl) return 1.0;
    if (tau < up + fl + dn) return 0.5 + 0.5*cos(PI*(tau - up - fl)/dn);
    return 0.0;
}
// 流れ関数の波（OUT_SF の表）。X = x − x_p − c t、η = Σ E_j cos(j k X)、Y = max(min(y, η) + h, 0)（水面より上は水面の値、伸ばしなし）、
// u = c − Ū + Σ j k B_j cosh(j k Y)/cosh(j k h) cos(j k X)、w = Σ j k B_j sinh(j k Y)/cosh(j k h) sin(j k X)。E を流速と η に掛ける
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
''' % SFT

BODIES_SF = {
    # 流れ関数の表（CTRL の sf_tab「h k c Ub N B1..BN E0..EN」→ 64 ビットの detail。inlet_table と同じ作り）
    "/obj/G47_SETUP/sf_table": r'''
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
        i@sfN = -1;             // 数が合わない（g47_run.py が止める）
    }
}
f[]@sfB = B; f[]@sfE = E;
''',
    # 入口の帯・吸う帯（sf_on 1 なら流れ関数の目標と組の包絡、relax_w 1 なら鉛直の流速も寄せる。sf_on 0 なら relax_zones と同じ）
    "/obj/G47_SIM/relax_zones_sf": r'''
vector pl = plan(@P);
float x = pl.x;
float t = f@Time;                       // Houdini の時刻（コマ 1 が 0 s）
float xg = chf(CT+"xg_end");
if (chf(CT+"relax_on") > 0.5 && x < xg && chf(CT+"relax_g") > 0.0) {
    float x0 = chf(CT+"x0");
    float w = clamp(relaxw((xg - x)/max(xg - x0, 1e-6))*chf(CT+"relax_g"), 0.0, 1.0);
    float wdt = 1.0 - pow(1.0 - w, f@TimeInc/chf(CT+"dt0"));
    float E = walltaper(x)*rampT(t, chf(CT+"ramp_s"));
    float eta; vector tv;
    if (chf(CT+"sf_on") > 0.5) {
        E *= sf_setenv(t);
        sfwave(x, pl.y, t, E, eta, tv);
        float vy = (chf(CT+"relax_w") > 0.5) ? lerp(v@vel.y, tv.y, wdt) : v@vel.y;
        v@vel = set(lerp(v@vel.x, tv.x, wdt), vy, v@vel.z);
    } else {
        groupwave(x, pl.y, t, E, eta, tv);
        v@vel = set(lerp(v@vel.x, tv.x, wdt), v@vel.y, v@vel.z);   // 水平だけ寄せる
    }
}
float xa0 = chf(CT+"xa0"); float x1 = chf(CT+"x0") + chf(CT+"Lx");
if (chf(CT+"abs_on") > 0.5 && x > xa0) {
    float chi = clamp((x - xa0)/max(x1 - xa0, 1e-6), 0.0, 1.0);
    float w = 1.0 - exp(-chf(CT+"abs_sigma")*pow(chi, chf(CT+"abs_pow"))*f@TimeInc);
    v@vel = set(lerp(v@vel.x, 0.0, w), v@vel.y, lerp(v@vel.z, 0.0, w));
}
''',
}


def snippet_sf(path):
    """周期の波の場面の VEX（VEX_HEAD ＋ VEX_SF ＋ 本体）。"""
    body = BODIES_SF.get(path, BODIES.get(path))
    return VEX_HEAD + VEX_SF + body


def sf_tab_string(sf):
    """cfg の sf（g47_sfwave.table の形：h・k・c・Ubar・B・E）→ CTRL の sf_tab（repr の桁で 64 ビットのまま）。"""
    B = [float(v) for v in sf["B"]]; E = [float(v) for v in sf["E"]]
    if len(E) != len(B) + 1:
        raise ValueError("sf の E は B より 1 つ多い（E0..EN）：B %d、E %d" % (len(B), len(E)))
    head = [repr(float(sf["h"])), repr(float(sf["k"])), repr(float(sf["c"])), repr(float(sf["Ubar"])), str(len(B))]
    return " ".join(head + [repr(v) for v in B] + [repr(v) for v in E])


# ====================================================================== 2026-10-13 周期の波の実験の役：水の体積の直し（周期の波の場面だけ。CTRL の volcorr_on 既定 0）
# SM1（平ら 19 m、粒子 0.5 m、流れ関数の波 120 s）で、FLIP の水の体積が 40 s までに +0.18 m（箱の平均の水面）増え、その後 −0.28 m まで減った
# （海底の中・箱の外の粒子 0、水の柱の中の空気 0。帯と波の所の数の上の吸い込み）【測った】。本当の水は閉じた水槽で増えも減りもしない。
# そこで、圧力を解く前に、水の中の全部の格子へ同じ小さな発散（目標の発散、1/s）を与えて、体積を始めの値に戻す（力ではなく、数の誤差の直し）：
#   V ＝ Σ（surface を SDF として重みにした 1）× 格子の体積（Gas Reduce）、V0 ＝ vol_tcap 秒（既定 1.5 s、始めの落ち着きの後）までの V、
#   divergence ＝ clamp((V0 − V)/V0 / vol_tau, −vol_dmax, +vol_dmax)（vol_tcap より前は 0）。
BODIES_VC = {
    "/obj/G47_SIM/vc_one": r'''
f@vc_one = 1.0;
''',
    "/obj/G47_SIM/vc_div": r'''
float t = f@Time;
if (t <= chf(CT+"vol_tcap")) f@vc_n0 = f@vc_n;
float n0 = f@vc_n0; float n = f@vc_n;
float d = 0.0;
if (chf(CT+"volcorr_on") > 0.5 && t > chf(CT+"vol_tcap") && n0 > 0.0)
    d = clamp((n0 - n)/n0/max(chf(CT+"vol_tau"), 1e-3), -chf(CT+"vol_dmax"), chf(CT+"vol_dmax"));
f@divergence = d;
''',
}


def snippet_vc(path):
    return VEX_HEAD + BODIES_VC[path]


# 2026-10-13（同じ役、試しの後）：Gas Reduce で測った V（Volume Velocity の段の surface）は、コマの終わりの surface の体積と合わない
# （直しを 0 にした試しで、38 s で前者 +2.7 %、後者 −0.3〜+0.5 %。粒子の数 +44 % と共に前者だけが増える）【測った】。そこで V はコマの終わりの
# surface（解析と同じ場）から g47_run.py が測り、次のコマの目標の発散をファイルに書く。場面は時刻で読む Python SOP（OUT_VOLDIV）でそれを読み、
# DOP の wrangle は detail で受ける（パラメーターを変えないので、計算の途中保存を消さない）。
VDT = "op:/obj/G47_SETUP/OUT_VOLDIV"
BODIES_VC["/obj/G47_SIM/vc_div_ext"] = r'''
float d = 0.0;
if (chf(CT+"volcorr_on") > 0.5) {
    d = detail("%s", "vol_div", 0);
    float xa = chf(CT+"vol_x0"); float xb = chf(CT+"vol_x1");
    if (xb > xa) {                       // vol_x1 > vol_x0 の時はその x の範囲だけ（帯の平均の水面を保つ形）。既定 0・0 は水の全部
        vector pl = plan(@P);
        if (pl.x < xa || pl.x > xb) d = 0.0;
    }
}
f@divergence = d;
''' % VDT
# 2026-10-13（SM2b の後）：帯の平均の水面を保つ形（CTRL の vol_mode 1、vol_x0〜vol_x1）。S2 の浅い平らに崩れた波が水を運び上げ（時間の平均で
# +3.3〜+3.9 m）、閉じた水槽なので沖の平均の水面が −1.0〜−1.7 m 下がり、崩れる所が 30 m 沖へ動いた【測った】。本当の海では沖の平均の水面は
# 外の海が保つ。そこで帯（外の海につながる所の代わり）の中だけに目標の発散を置き、帯の時間の平均の水面を静かな水面に保つ（g47_run.py が決める）。

PYSOP_VOLDIV = r'''
import os, math
import hou
node = hou.pwd()
geo = node.geometry()
geo.clear()
geo.addAttrib(hou.attribType.Global, "vol_div", 0.0)
geo.addAttrib(hou.attribType.Global, "vol_frame", 0)
geo.addAttrib(hou.attribType.Global, "vol_src", "")
fr = node.evalParm("fr")
d = node.evalParm("vdir")
f = int(math.ceil(fr - 1e-6))
v = 0.0; src = "none"
if d:
    p = os.path.join(d, "vd_%05d.txt" % f)
    if os.path.exists(p):
        try:
            v = float(open(p).read().split()[0]); src = p
        except Exception as e:
            src = "error %r" % (e,)
geo.setGlobalAttribValue("vol_div", float(v))
geo.setGlobalAttribValue("vol_frame", f)
geo.setGlobalAttribValue("vol_src", src)
'''
