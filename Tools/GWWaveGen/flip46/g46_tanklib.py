# -*- coding: utf-8 -*-
"""FLIP46：3D の尾根の水槽（Houdini/FLIP46/g46_tank.hiplc）の VEX と、孤立波の npz を読む Python SOP のコード。g46_build_tank.py が使う。
FLIP45 の g45_tanklib.py（Tools/GWWaveGen/flip45、変えていない）を写して直した。持ち込まない物：入口の表・入口の帯・横の帯・出口の帯
（閉じた水槽で、孤立波を初めの状態に置くだけ。BigWave_Recipes_ja.md §5.2）。足した物：尾根の海底（FLIP44 の bedy と同じ考えを 3D に）、
孤立波の解の表（OUT_SOL の体積 eta・u・w）を読む関数。

座標：Houdini の中は計画の座標を o = (ox, oy, oz)（CTRL）だけずらした所に置く（Houdini = 計画 + o。FLIP45 と同じ）。
  VEX は始めに計画の座標 pl = @P − o に戻す：x＝波の進む向き、y＝上（静かな水面 0、平らな海底 −17 m）、z＝横（z = 0 が対称の面）。
解の表（Python SOP solution_table が npz から作り、OUT_SOL を表を使う wrangle の 2 つ目の入力につなぐ。軸は計画の座標のまま）：
  eta：体積の X = x（縦と横は 1 個）。u・w：X = x、Y = 上 z。水面より上は列のいちばん上の値で埋めてある。
  detail に x_lo・x_hi・z_lo・z_hi（表の格子の中心の端）と c・x0・h0・src（npz のパスと SHA-256 の頭）。x は表の端で止める（外へは伸ばさない）。
尾根（CTRL の ridge_on・ridge_x0・ridge_k・ridge_s）：x ≤ ridge_x0 は −h0。先は −(h0 − (x − ridge_x0) sech²(ridge_k zl/h0)/ridge_s)。
  衝突の SDF（Static Object の体積 collision）は (y − bedy)/√(1 + |∇bedy|²)（海底の中で負）。
"""

CT = "/obj/G46_SETUP/CTRL/"
TABF = "1"        # 解の表は SOP の wrangle の 2 つ目の入力（OUT_SOL をつなぐ。op: の参照より確かに読み直される）

VEX_HEAD = r'''
#define CT "%s"
#define TABF %s
// 尾根の海底の高さ（計画の座標。x：進む向き、zl：横）
float bedy(float x; float zl) {
    float h0 = chf(CT+"h0");
    float xt = chf(CT+"ridge_x0");
    if (chf(CT+"ridge_on") < 0.5 || x <= xt) return -h0;
    float sh = 1.0/cosh(chf(CT+"ridge_k")*zl/h0);
    return -(h0 - (x - xt)*sh*sh/chf(CT+"ridge_s"));
}
// 海底の勾配（d bedy/dx、d bedy/dzl）
vector2 bedgrad(float x; float zl) {
    float h0 = chf(CT+"h0");
    float xt = chf(CT+"ridge_x0");
    if (chf(CT+"ridge_on") < 0.5 || x <= xt) return {0, 0};
    float k = chf(CT+"ridge_k"); float s = chf(CT+"ridge_s");
    float a = k*zl/h0;
    float sh = 1.0/cosh(a);
    return set(sh*sh/s, (x - xt)/s*(-2.0*sh*sh*tanh(a)*k/h0));
}
// 海底の SDF（海底の外で正。Static Object の collision）
// side_pad > 0（2026-10-12 統合の役）：対称の面 y = 0 も SDF の壁にする（箱の横の下の端は side_pad 格子だけ外へ）。
//   APIC の箱の低い側の壁（Houdini の −z）で、平らな海底の孤立波の頂の近くに y = 0 へ向かう偽の横流れが出た（粒子 1 m で 4 s に −0.33 m/s、
//   0.5 m で 3 s に −0.085 m/s。高い側の壁 y = W には出ない。FLIP の受け渡しでは出ない）。その切り分けの選び
float bedsdf_out(float x; float y; float zl) {
    vector2 gr = bedgrad(x, zl);
    float d = (y - bedy(x, zl))/sqrt(1.0 + gr.x*gr.x + gr.y*gr.y);
    if (chf(CT+"side_pad") > 0.5) d = min(d, zl);
    return d;
}
float smooth01(float c0) { float c = clamp(c0, 0.0, 1.0); return c*c*(3.0 - 2.0*c); }
// 孤立波の水面（wave_on 0 なら静かな水）
float sol_eta(float x) {
    if (chf(CT+"wave_on") < 0.5) return 0.0;
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    return volumesample(TABF, "eta", set(xq, 0.0, 0.0));
}
// 孤立波の流速（Houdini の向き：x、上、横 0）。水面より上は水面の値（表の中で列のいちばん上の値で埋めてある）
vector sol_vel(float x; float yv) {
    if (chf(CT+"wave_on") < 0.5) return {0, 0, 0};
    float xq = clamp(x, detail(TABF, "x_lo", 0), detail(TABF, "x_hi", 0));
    float e = volumesample(TABF, "eta", set(xq, 0.0, 0.0));
    float zq = clamp(min(yv, e), detail(TABF, "z_lo", 0), detail(TABF, "z_hi", 0));
    return set(volumesample(TABF, "u", set(xq, zq, 0.0)), volumesample(TABF, "w", set(xq, zq, 0.0)), 0.0);
}
''' % (CT, TABF)

BODIES = {
    # 小刻みの数の記録（FLIP45 と同じ）
    "/obj/G46_SIM/substep_count": r'''
if (f@ss_acc >= 1.0/24.0 - 1e-6) { f@ss_acc = 0.0; i@ss_n = 0; }
f@ss_acc += f@TimeInc;
i@ss_n += 1;
f@ss_dt = f@TimeInc;
''',
    # 海底の面（表示と Static Object の形。衝突は体積で）
    "/obj/G46_SETUP/bed_height": r'''
vector o = set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
vector pl = @P - o;
@P.y = bedy(pl.x, pl.z) + o.y;
''',
    # 海底の SDF の値（Static Object の proxy volume。海底の中で負）
    "/obj/G46_SETUP/bed_sdf_value": r'''
vector pl = @P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
f@collision = bedsdf_out(pl.x, pl.y, pl.z);
''',
    # 初めの格子の流速（FLIP37 の誤り：深い格子の流速が 0 から始まらないように、解の値を入れる）
    "/obj/G46_SETUP/vel_value": r'''
vector pl = @P - set(chf(CT+"ox"), chf(CT+"oy"), chf(CT+"oz"));
v@vel = sol_vel(pl.x, pl.y);
''',
}

# 解の表を作る Python SOP（npz → 体積 eta・u・w。u_ext・w_ext があればそれを使う。並びが [x, z] でも [z, x] でも受ける。等間隔でなければ等間隔に直す。
# 無次元の npz（h0 = 1）なら、長さを CTRL の h0 倍、流速を √(g h0) 倍にする）
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
    """a の座標 v（増える向き）を等間隔に直し、値の配列 v（axis の向き）を線形に補う。"""
    d = np.diff(a)
    if np.allclose(d, d[0], rtol=1e-6, atol=1e-9):
        return a, v
    h = float(np.min(d)); n = int(round((a[-1] - a[0])/h)) + 1
    a2 = a[0] + h*np.arange(n)
    v2 = np.apply_along_axis(lambda c: np.interp(a2, a, c), axis, v)
    return a2, v2


def put(nm, arr, bb):
    arr = np.ascontiguousarray(arr.astype(np.float32))
    nz_, ny_, nx_ = arr.shape                                 # (横, 上, x)：x が最も速い
    vol = geo.createVolume(nx_, ny_, nz_, bb)
    vol.setAttribValue("name", nm)
    vol.setAllVoxelsFromString(arr.tobytes())


if on:
    if not os.path.exists(p):
        raise hou.NodeError("孤立波の npz がない: %s" % p)
    d = np.load(p)
    x = np.asarray(d["x"], dtype=np.float64).ravel(); z = np.asarray(d["z"], dtype=np.float64).ravel()
    eta = np.asarray(d["eta"], dtype=np.float64).ravel()
    ext = "u_ext" in d.files and "w_ext" in d.files       # 水面より上を水面の厳密な値で埋めた物があればそれを使う（g46_solitary.py。水面の近くの補いの誤差 1〜3 cm/s → 2〜4 mm/s）
    u = np.asarray(d["u_ext" if ext else "u"], dtype=np.float64); w = np.asarray(d["w_ext" if ext else "w"], dtype=np.float64)
    if u.shape == (len(x), len(z)) and len(x) != len(z):
        u = u.T; w = w.T
    if u.shape != (len(z), len(x)) or w.shape != u.shape or eta.shape != x.shape:
        raise hou.NodeError("npz の形が違う: x %s z %s eta %s u %s w %s" % (x.shape, z.shape, eta.shape, u.shape, w.shape))
    h0f = float(d["h0"]) if "h0" in d.files else H0C
    sl = sv = 1.0
    if abs(h0f - 1.0) < 1e-9:                                  # 無次元
        sl = H0C; sv = (9.80665*H0C) ** 0.5
    x = x*sl; z = z*sl; eta = eta*sl; u = u*sv; w = w*sv
    c = float(d["c"])*sv if "c" in d.files else 0.0
    x0 = float(d["x0"])*sl if "x0" in d.files else 0.0
    nf = int((~np.isfinite(u)).sum() + (~np.isfinite(w)).sum())
    for a in (u, w):                                           # 水面より上（NaN）は列のいちばん上の値、下の NaN はいちばん下の値で埋める
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
