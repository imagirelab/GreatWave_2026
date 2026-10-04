# -*- coding: utf-8 -*-
"""美術の見本04 の作り W4（Q32、S9）：左端の別の小さな青い波（④）を numpy で作る。

形（断面の座標 a・y・c で決める。参照モデル・写真は読まない）：
1. 頂の線：原画の輪郭の区間 78 の x 0〜360（利用者の黄色の線 ④）の射線の上。深さは調べ S の勧め（今の主役波の頂より 5 m 奥）から始め、
   頂の高さ Yc(c) が左へ単調に下がるように（背の一つの山 S4）右から見た最小へそろえる。原画の画の外の左（c < −15.5 m）は
   滑らかに下げて c −28 m で海の高さ、右（c > −10.3 m）は同じ傾きで続け、主役波の背の下へ沈む（主役波に溶ける）。
2. 断面：y = Yc(c)·sech²(d / L)（d = a − 頂の a、前 L = 3.5 m、背 L = 9 m。背の裾は d −18〜−25 m で 0 へ、前は d +5〜+7 m で 0 へ）。
3. 地面の上に載せる：x = y_w − G − eps、y = G + eps + (x ≥ k なら x、x ≤ −k なら 0、間は (x + k)²/4k)（G = 主役波の一番上の面と海の大きい方、eps 6 cm、k 0.8 m）。
   3 頂点とも x ≤ −k（ちょうど地面 + eps）の三角形は捨てる → 縁はどこもちょうど地面の 6 cm 上にあり、主役波と交わらず、海へ段なく下りる。
4. 原画視点で頂の輪郭が区間 78 に合うように、描いた頂の縁と真値の差で Yc を 2 回直す。
属性（AS04 Flat Smooth、Build/Polish/sample04/mat/README.md の 3 節の約束）：
- u = 断面の上の頂からの弧長（前 +）、w = c、q = u／λ（前：帯は頂に平行な筋、原画の楔の筋の向き）・w／λ（背：頂から下へ流れる筋）、
  切り替えは頂の背の側の細い白い線の中（u −0.42 m）、λ = 0.045 H0、F = 2 + 2u/15、hrow = Yc/H0、whiteOn 1。
- whiteSD（白の印）は原画の楔の色の帯の境（w4_paint.py の測り：頂の藍の線・水色の帯・下の淡い筋）を、原画のカメラの射線が波の面に当たる所の u で決め、
  c に沿ってならした値。正の帯の中は 0.3〜0.5（材質の水色の帯の範囲。白は境の 3 cm だけ）、藍の側は −3·距離（深さ 2 m まで）。
  原画の色は面へ写さない（境の位置だけを面の u の値として持つ）。
出力（Git 対象外）：Unity/Build/Polish/sample04/wave4/mesh/wave4.json/.bin、wave4_grid.npz、wave4_build_report.json
使い方：py -3.10 -B Tools/GWWaveGen/as04/w4_build.py [--hero-rows <主役波の行の npz>]（既定は仮の主役波 standin_rows.npz）
"""
import argparse
import json
import os

import numpy as np

import w4_common as W

S, K, CC = W.S, W.K, W.CC
LAM = 0.045 * W.H0
LF, LB = 3.5, 9.0
TB1, TB2 = 2.0, 2.8      # 背の裾：t = |d|/LB が TB1〜TB2 で 0 へ
TF1, TF2 = 1.25, 1.7     # 前の裾
C_L, C_R = -29.0, -2.0
LR = 8.0      # 右（主役波の頂の線の後ろ）で頂を 0 へ下ろす長さ（m）。4.6 m では主役波の背へ沈む所が 60〜75° の折れになった
LA = 0.8      # 画の外の頂の線の a の曲がりの長さ（m）。2.0 では左の端の頂が主役波の尾の頂の 1 m 後ろまで前へ出て、前の面が尾の唇に掛かった
PLAT = 2.2    # 画の左の縁の外で頂を同じ高さに保つ長さ（m）
Q_SWITCH = -0.42   # 帯の線の座標 q：これより前（頂の白い線の中で切り替える）は u/λ（頂に平行な筋）、背は w/λ（頂から下へ流れる筋。主役波の背と同じ向き）
EPS, KS = 0.06, 0.8   # 地面の上に載せる：eps 6 cm（3 cm では主役波の静止のメッシュ（行より細かい）との隙が 6 mm まで縮んだ）、つなぎの幅 k 0.8 m（0.25 m では右の端で主役波の背へ沈む所が 75° の折れになった）
X_IN = np.arange(4, 361, 4)
CREST_LINE = (-0.55, -0.30)   # 頂の背の側の細い白い線の u の範囲（m）。None で出さない
OUTD = W.OUT + "/mesh"


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def painting_cam(scale=1):
    spec = json.load(open(S.CC.U.TRUTH, encoding="utf-8"))
    return S.CC.U.CamWH(spec, 1920 * scale, 1080 * scale)


def ref_to_px(xr, yr, scale):
    d = S.ref_to_disp(np.stack([np.asarray(xr, float), np.asarray(yr, float)], -1))
    return scale * (d[..., 0] + 0.5) - 0.5, scale * (d[..., 1] + 0.5) - 0.5


# ---------------------------------------------------------------- 1. 頂の線
def crest_line():
    cam = painting_cam(1)
    seg = S.outline_segments()["78"]
    M = json.load(open(S.OUT + "/s4_map.json", encoding="utf-8"))
    cols4 = {e["x_ref"]: e for e in M["region4"]["columns"] if "hero_depth_m" in e}
    rows = []
    for x in X_IN:
        yr = float(np.interp(x, seg[:, 0], seg[:, 1]))
        xd, yd = S.ref_to_disp(np.array([x, yr], float))
        d = cam.ray(np.array([xd]), np.array([yd]))[0]
        e = cols4.get(int(x))
        hd = e["hero_depth_m"] / float(d @ cam.f)
        s5 = hd + 5.0
        P = cam.pos + s5 * d
        q = K.sec(P[None])[0]
        dy = K.sec((cam.pos + (s5 + 1.0) * d)[None])[0][1] - q[1]
        rows.append(dict(x=float(x), y_ref=yr, d=d, s5=s5, y5=q[1], dyds=dy))
    y5 = np.array([r["y5"] for r in rows])
    ytar = np.minimum.accumulate(y5[::-1])[::-1]          # 右から見た最小：左へ単調に下がる
    pts = []
    for r, yt in zip(rows, ytar):
        s = r["s5"] + (yt - r["y5"]) / r["dyds"]
        q = K.sec((cam.pos + s * r["d"])[None])[0]
        pts.append((r["x"], s, q[0], q[1], q[2]))
    return np.array(pts), cam   # x, s, a, y, c


class Crest:
    """頂の線 a_c(c)・Yc(c)（画の中は射線の点の多項式、左右は滑らかにのばす）と、Yc の直し dY(c)。"""

    def __init__(self, pts):
        x, s, a, y, c = pts.T
        o = np.argsort(c)
        self.c_in = c[o]; self.a_in = a[o]; self.y_in = y[o]
        self.c0, self.c1 = float(self.c_in[0]), float(self.c_in[-1])
        self.pa = np.polyfit(self.c_in, self.a_in, 3)
        self.py = np.polyfit(self.c_in, self.y_in, 5)   # 5 次：画の右の端（x 300〜360）で輪郭が急に上がるのに付いていく
        self.corr_c = np.array([self.c0, self.c1]); self.corr_v = np.zeros(2)

    def a_c(self, c):
        # 画の外は傾きを続けながら LA m で平らにする（頂の線に折れを作らない）
        c = np.asarray(c, float)
        cc = np.clip(c, self.c0, self.c1)
        a = np.polyval(self.pa, cc)
        dp = np.polyder(self.pa)
        da0, da1 = np.polyval(dp, self.c0), np.polyval(dp, self.c1)
        a = np.where(c < self.c0, np.polyval(self.pa, self.c0) - da0 * LA * (1 - np.exp(-(self.c0 - c) / LA)), a)
        a = np.where(c > self.c1, np.polyval(self.pa, self.c1) + da1 * LA * (1 - np.exp(-(c - self.c1) / LA)), a)
        return a

    def Yc(self, c):
        c = np.asarray(c, float)
        cc = np.clip(c, self.c0, self.c1)
        y = np.polyval(self.py, cc) + np.interp(cc, self.corr_c, self.corr_v)
        y0 = np.polyval(self.py, self.c0) + np.interp(self.c0, self.corr_c, self.corr_v)
        y1 = np.polyval(self.py, self.c1) + np.interp(self.c1, self.corr_c, self.corr_v)
        dy1 = np.polyval(np.polyder(self.py), self.c1)
        # 左（原画の画の外）：PLAT m は同じ高さ（原画の輪郭が画の左の縁でまだ左上へ上がっているのを、縁で折らずに受ける）、その先 C_L で海の高さへ
        t = (c - C_L) / (self.c0 - PLAT - C_L)
        y = np.where(c < self.c0, y0 * smooth(t), y)
        # 右（主役波の頂の線の後ろ）：同じ傾きで続けながら LR m で 0 へ下ろす（主役波の背の後ろで終わる）
        # 3 次の Hermite（c1 で高さと傾きを続け、c1 + LR で 0・傾き 0）。前の版（直線 × smoothstep）は c1 の先で頂が持ち上がった
        tt = np.clip((c - self.c1) / LR, 0, 1)
        yh = y1 * (2 * tt ** 3 - 3 * tt ** 2 + 1) + dy1 * LR * (tt ** 3 - 2 * tt ** 2 + tt)
        y = np.where(c > self.c1, yh, y)
        return np.maximum(y, 0.0)


# ---------------------------------------------------------------- 2・3. 面
def build_surface(cr, ground, nr=541, ncol=301):   # 行 541（c 0.05 m おき）：221 行では横から見た頂の縁がのこぎりの歯になった
    cs = np.linspace(C_L, C_R, nr)
    sgrid = np.linspace(-1.0, 1.0, ncol)
    # 頂の近くを細かく（|s|^1.7）。背は −TB2·LB、前は +TF2·LF まで
    dgrid = np.where(sgrid < 0, -(np.abs(sgrid) ** 1.7) * TB2 * LB, (np.abs(sgrid) ** 1.7) * TF2 * LF)
    ac = cr.a_c(cs)
    yc = cr.Yc(cs)
    # 頂の低い所（左右の端）ほど幅を狭める：足もとが頂の線に沿う長円になり、上から見て四角い布にならない
    fw = 0.35 + 0.65 * np.clip(yc / 12.5, 0, 1) ** 0.7
    # 画の外の左（c < c0 − 0〜1 m）は、頂の線を主役波の尾の頂（背の側）より後ろへ下げる：別の波の前の面が主役波の頂より手前の背に降りる距離
    # g = LF·fw·arcsech(√((H − 0.5)/Yc))（2.2 m 以上）。画の中の頂は原画の射線の上のまま動かさない
    hca = np.interp(cs, ground.c, ground.crest_a)
    hcy = np.interp(cs, ground.c, ground.crest_y)
    ratio = np.clip((hcy - 0.5) / np.maximum(yc, 1e-3), 0.02, 0.999)
    greq = LF * fw * np.arccosh(1.0 / np.sqrt(ratio))
    need = np.where(hcy > 1.0, hca - np.maximum(greq, 2.2), np.nan)
    okn = np.isfinite(need)
    need = np.interp(cs, cs[okn], need[okn]) if okn.any() else np.full_like(cs, 1e9)   # 尾が海へ下りた行は、近い行の値のまま（左の端で頂の線が折れ返らないように）
    wl = smooth((cr.c0 - cs) / 1.0)
    ac_adj = ac - wl * np.maximum(ac - need, 0.0)
    k = np.exp(-0.5 * (np.arange(-15, 16) * (cs[1] - cs[0]) / 0.6) ** 2); k /= k.sum()
    ac_s = np.convolve(np.pad(ac_adj, 15, mode="edge"), k, mode="valid")
    ac = np.where(wl > 0, np.minimum(ac_s, ac_adj) * wl + ac * (1 - wl), ac)
    D = dgrid[None, :] * fw[:, None]
    A = ac[:, None] + D
    t = np.where(D < 0, -D / (LB * fw[:, None]), D / (LF * fw[:, None]))
    win = np.where(D < 0, 1 - smooth((t - TB1) / (TB2 - TB1)), 1 - smooth((t - TF1) / (TF2 - TF1)))
    # 裾の外は海より 0.6 m 下へ（地面の上に載せる時に裾がちょうど地面 + eps になり、縁が浮かない）
    endw = (smooth((cs - C_L) / 1.2) * smooth((C_R - cs) / 1.2))[:, None]   # 格子の左右の端の行も海の下へ（端の縁を浮かせない）
    Yw = yc[:, None] / np.cosh(t) ** 2 * win - 0.6 * (1 - win * endw)
    C = np.broadcast_to(cs[:, None], (nr, ncol))
    G = ground(A.ravel(), C.ravel()).reshape(nr, ncol)
    # 地面の崖（主役波の唇の先などで、隣の格子点の間に地面が 0.5 m 以上落ちる所）より外は使わない：
    # 崖を越えて裾を延ばすと、唇の先から海へ垂れる幕の三角形ができる（AS04 の主役波の左の尾 c −22〜−21 で起きた）
    jc0 = int(np.argmin(np.abs(dgrid)))
    dG = np.diff(G, axis=1)
    steepG = np.abs(dG) > 4.0 * np.maximum(np.abs(np.diff(A, axis=1)), 1e-6)   # 76° より急（主役波の背の斜面は崖としない）
    fwd = np.zeros((nr, ncol), bool)
    fwd[:, jc0 + 1:] = np.cumsum((dG[:, jc0:] < -0.5) & steepG[:, jc0:], axis=1) > 0
    bwd = np.zeros((nr, ncol), bool)
    bwd[:, :jc0] = (np.cumsum(((dG[:, :jc0] > 0.5) & steepG[:, :jc0])[:, ::-1], axis=1) > 0)[:, ::-1]
    # 主役波の頂より前（+a）へは延ばさない（頂の 0.3 m 先まで）。主役波の頂が 1 m より低い行（海へ下ろした尾）は縛らない。
    # 唇の先の向こうへ裾が出ると、唇の上から海へ垂れる幕ができる（AS04 の主役波の左の尾 c −24〜−22 で起きた。行の間で唇の先の位置が変わるので、上の崖の見分けだけでは捕まらない）
    # 前（+a）は主役波の頂（背の側）の 0.4 m 先より外へ出さない（上で頂の線を下げたので、ふつうは頂より手前で主役波の背に降りる。これは安全の網）。
    # 主役波の頂が 1 m より低い行（海へ下ろした尾）は縛らない。唇の先の向こうへ裾が出ると、唇の上から海へ垂れる幕ができる
    #（AS04 の主役波の左の尾 c −24〜−22 で起きた。行の間で唇の先の位置が変わるので、上の崖の見分けだけでは捕まらない）
    cap = np.where(hcy > 1.0, np.maximum(hca + 0.4, ac + 1.0), 1e9)[:, None]
    over = (D > 0) & (A > cap)
    cliff = fwd | bwd | over
    Yw = np.where(cliff, -0.6, Yw)
    Y = W.softmax_above(Yw, G, EPS, KS)
    return dict(c=cs, d=dgrid, A=A, Yw=Yw, G=G, Y=Y, ac=ac, yc=yc, fw=fw, cliff_cells=int(cliff.sum()))


def mesh_from_grid(g):
    # 三角形は、頂点のどれかが地面から浮いている（x = y_w − G − eps > −k）物だけ残す。捨てた三角形の頂点はどれも x ≤ −k で
    # ちょうど地面 + eps にあるので、残した面の縁（捨てた三角形と共有する辺）はどこも地面の 3 cm 上になる
    nr, ncol = g["A"].shape
    tri = K.triangles(ncol, nr).astype(np.int64)
    x = (g["Yw"] - g["G"] - EPS).ravel()
    ok_v = x > -KS
    keep = ok_v[tri].any(1)
    tri = tri[keep]
    used = np.unique(tri)
    remap = -np.ones(nr * ncol, np.int64)
    remap[used] = np.arange(len(used))
    P = K.world(g["c"], g["A"], g["Y"]).reshape(-1, 3)
    return P, tri, used, remap


# ---------------------------------------------------------------- 4. 原画視点の頂の縁
def render_ids(cam, P, tri):
    tris = P[tri]
    ids = np.arange(1, len(tri) + 1)
    idb, zb = S.U.raster(cam, tris, ids)
    return idb.reshape(cam.H, cam.W), zb.reshape(cam.H, cam.W)


def top_edge(idb):
    m = idb > 0
    has = m.any(0)
    top = np.where(has, np.argmax(m, 0), -1)
    return top


def silhouette_error(cam, scale, top, xs=X_IN):
    seg = S.outline_segments()["78"]
    out = []
    for x in xs:
        yr = float(np.interp(x, seg[:, 0], seg[:, 1]))
        px, py = ref_to_px(x, yr, scale)
        col = int(round(float(px)))
        if 0 <= col < cam.W and top[col] >= 0:
            out.append((x, float(top[col]) - 0.5 - float(py)))     # 正 = 描いた縁が真値より下
        else:
            out.append((x, np.nan))
    return np.array(out)


# ---------------------------------------------------------------- 属性
def attributes(g, cr, bands):
    nr, ncol = g["A"].shape
    A, Y = g["A"], g["Y"]
    j0 = int(np.argmin(np.abs(g["d"])))
    seg = np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1))
    s = np.concatenate([np.zeros((nr, 1)), np.cumsum(seg, 1)], 1)
    u = s - s[:, j0:j0 + 1]
    cs = g["c"]
    wv = np.broadcast_to(cs[:, None], (nr, ncol))
    F = np.clip(2.0 + 2.0 * u / 15.0, -0.5, 4.5)
    hrow = np.broadcast_to((cr.Yc(cs) / W.H0)[:, None], (nr, ncol))
    q = np.where(u >= Q_SWITCH, u / LAM, wv / LAM)
    # 白の印
    ub, um, us0, us1 = [np.interp(cs, bands["c"], bands[k])[:, None] for k in ("u_b", "u_m", "u_s0", "u_s1")]
    ws = np.interp(cs, bands["c"], bands["streak_on"])[:, None]
    # 頂が低くなる所（画の外の左の下り、右の主役波の背へ沈む所。Yc 8 → 4 m）では水色の帯と淡い筋を細くして消す
    #（前の版では、左の端で頂が海へ下りる所に帯が縦の縞として残り、左の側面からリボンのように見えた）
    fb = np.clip((cr.Yc(cs)[:, None] - 4.0) / 4.0, 0, 1)
    um = ub + (um - ub) * fb
    smid, shw = 0.5 * (us0 + us1), 0.5 * (us1 - us0) * fb
    us0, us1 = smid - shw, smid + shw

    # 正の帯（水色）の中は 0.31〜0.51（材質の水色の範囲 0.3〜0.3+W、W ≥ 0.25）。境のすぐ外は −30·距離（上限あり）で急に下げる：
    # 頂点の間の線形の補いで 0〜0.3 の白が細い白い線として出ないように（見本の前の版では境に白い髪の毛の線が出た）
    def strip(lo, hi):
        dd = np.minimum(u - lo, hi - u)
        return dd, 0.31 + np.clip(dd, 0, 0.2)

    def steep(x, cap):
        return -np.maximum(np.minimum(30.0 * x, cap), np.where(x > cap, x, 0.0))
    d1, p1 = strip(ub, um)
    d2, p2 = strip(us0, us1)
    has2 = (ws > 0.5) & (us1 - us0 > 0.04)
    live1 = um - ub > 0.03
    # 前の藍：近い方の帯からの距離。深さは 0.8 m まで（材質の白い点は深さ 0.8 m から現れるので、この波の前の面には出さない。点は原画の 3 つだけ）
    dfront = np.where(has2, np.minimum(np.abs(u - um), np.abs(u - us0)), u - um)
    dfront = np.where(has2 & (u > us1), u - us1, dfront)
    dfront = np.where(live1, dfront, np.abs(u - ub))
    wsd = np.where(u < ub, steep(ub - u, 0.6), -np.minimum(30.0 * np.abs(dfront), 0.8))
    wsd = np.where(live1 & (d1 >= 0), p1, wsd)
    wsd = np.where(has2 & (d2 >= 0), p2, wsd)
    # 頂の背の側の細い白い線（u −0.55〜−0.30 m。原画のカメラからは頂の向こうで見えない。横・後ろ・上から頂の線を読ませる）。
    # 頂の低い所（Yc 8 → 4 m）では細くして消す（Yc < 5 m では材質が裾の色へ寄せるので、q の切り替えの継ぎ目は目立たない）
    if CREST_LINE:
        # 帯の線の座標 q の切り替え（u = Q_SWITCH）の前後は、白い線が細い・無い所でも帯を描かない（−0.1：材質は白の境から 0.15 m より浅い所に帯を描かない）
        gap = (u >= CREST_LINE[0]) & (u <= CREST_LINE[1])
        wsd = np.where(gap, np.maximum(wsd, -0.1), wsd)
        wl = CREST_LINE[1] - CREST_LINE[0]
        on = np.clip((np.broadcast_to((cr.Yc(cs))[:, None], u.shape) - 4.0) / 4.0, 0, 1)
        lo = CREST_LINE[0] + 0.5 * wl * (1 - on); hi = CREST_LINE[1] - 0.5 * wl * (1 - on)
        d3 = np.minimum(u - lo, hi - u)
        live = hi - lo > 0.02
        wsd = np.where(live & (d3 >= 0), np.minimum(d3 * 10.0, 0.25), np.where(live, np.maximum(wsd, d3), wsd))
    # 藍の上の白い点（原画の楔の点の位置と大きさ。角のある欠片：正 n 角形の縁の距離）。境に材質の藍の線が付く
    for ch in bands.get("chips", []):
        du_ = (u - ch["u"]) / max(ch["r_u_m"], 0.03)
        dw_ = (wv - ch["c"]) / max(ch["r_w_m"], 0.03)
        e = np.hypot(du_, dw_)
        th = np.arctan2(du_, dw_) - ch["phase"]
        seg_ = 2 * np.pi / ch["nside"]
        am = th - seg_ * np.floor(th / seg_) - 0.5 * seg_
        poly = np.cos(0.5 * seg_) / np.maximum(np.cos(am), 0.2)
        dm = (poly - e) * min(ch["r_u_m"], ch["r_w_m"])
        wsd = np.where(dm >= 0, np.minimum(dm * 10.0, 0.25), np.where(dm > -0.3, np.maximum(wsd, dm), wsd))
    return dict(u=u, w=wv, F=F, hrow=hrow, q=q, wsd=wsd)


def channels(g, at, used, normals):
    def f(x):
        return np.asarray(x, np.float64).ravel()[used]
    n = len(used)
    hrel = f(g["Y"] / np.maximum(g["yc"][:, None], 1e-3))
    ch = {"position": None, "normal": normals,
          "tangent": np.tile(np.array([[0, 0, 0, 1.0]]), (n, 1)),
          "uv3": np.stack([f(at["F"]), hrel, f(at["u"]), f(at["w"])], -1),
          "uv4": np.stack([np.full(n, 1.0 / LAM), f(at["hrow"]), np.zeros(n), f(at["q"])], -1),
          "uv5": np.stack([np.ones(n), np.ones(n), f(at["wsd"]), np.zeros(n)], -1),
          "uv6": np.stack([np.full(n, 255.0), np.full(n, 4095.0), np.full(n, LAM), np.ones(n)], -1)}
    return ch


# ---------------------------------------------------------------- 帯の境（原画の測り → u）
def measure_bands(g, P, tri, used, remap, u_full, scale=2):
    cam = painting_cam(scale)
    idb, zb = render_ids(cam, P, tri)
    pb = json.load(open(W.OUT + "/meas/w4_paint_bands.json", encoding="utf-8"))["columns"]
    uv = np.asarray(u_full).ravel()
    cv = np.broadcast_to(g["c"][:, None], g["A"].shape).ravel()
    ut = uv[tri].mean(1)
    ct = cv[tri].mean(1)

    def hit(x, yr):
        px, py = ref_to_px(x, yr, scale)
        ix, iy = int(round(float(px))), int(round(float(py)))
        if not (0 <= ix < cam.W and 0 <= iy < cam.H):
            return None
        t = idb[iy, ix]
        if t <= 0:
            return None
        return float(ct[t - 1]), float(ut[t - 1])
    recs = []
    for e in pb:
        x = e["x_ref"]
        if e.get("mizuiro_top") is None or x > 360:
            continue
        r = {"x": x}
        h0, h1 = hit(x, e["mizuiro_top"][0]), hit(x, e["mizuiro_top"][1])
        if h0 is None or h1 is None:
            continue
        r["c"], r["u_b"] = h0
        r["u_m"] = h1[1]
        lo = e.get("mizuiro_low")
        if lo is not None and x <= 124 and 1005 <= lo[0] <= 1040:
            a0, a1 = hit(x, lo[0]), hit(x, lo[1])
            if a0 is not None and a1 is not None:
                r["u_s0"], r["u_s1"] = a0[1], a1[1]
        recs.append(r)
    chips = []
    for k, ch in enumerate(json.load(open(W.OUT + "/meas/w4_paint_bands.json", encoding="utf-8")).get("chips", [])):
        if ch["r_px"] < 4.0:
            continue
        x, y = ch["x_ref"], ch["y_ref"]
        h0, hx, hy = hit(x, y), hit(x + 20, y), hit(x, y + 20)
        if h0 is None or hx is None or hy is None:
            continue
        r = ch["r_px"]
        dw = np.hypot(hx[0] - h0[0], hx[1] - h0[1]) / 20.0    # 原画の 1 画素あたりの面の上の m（横）
        du = np.hypot(hy[0] - h0[0], hy[1] - h0[1]) / 20.0    # （縦）
        if max(r * dw, r * du) > 0.4 or max(dw, du) > 3.0 * max(min(dw, du), 1e-6):
            continue   # 射線の差が別の所へ当たった（面の向きが測れない）
        chips.append({"x_ref": x, "y_ref": y, "c": h0[0], "u": h0[1], "r_w_m": r * dw, "r_u_m": r * du, "nside": 4 + (k % 3), "phase": 1.3 * k})
    return recs, cam, idb, chips


def bands_from_recs(recs, cr):
    c = np.array([r["c"] for r in recs]); o = np.argsort(c)
    c = c[o]
    ub = np.array([r["u_b"] for r in recs])[o]
    um = np.array([r["u_m"] for r in recs])[o]
    # ならし（c に沿って 3 次）と、左（画の外）は左端の幅のまま、右は 0 へ
    pb = np.polyfit(c, ub, 2); wm = np.polyfit(c, np.maximum(um - ub, 0), 2)
    cg = np.linspace(C_L, C_R, 541)
    cl = np.clip(cg, c[0], c[-1])
    UB = np.polyval(pb, cl)
    WM = np.maximum(np.polyval(wm, cl), 0)
    WM = np.where(cg > c[-1], WM[cg <= c[-1]][-1] * np.clip(1 - (cg - c[-1]) / 0.8, 0, 1), WM)
    srec = [r for r in recs if "u_s0" in r]
    if srec:
        cs_ = np.array([r["c"] for r in srec]); oo = np.argsort(cs_)
        s0 = np.array([r["u_s0"] for r in srec])[oo]; s1 = np.array([r["u_s1"] for r in srec])[oo]
        cs_ = cs_[oo]
        S0 = np.interp(cg, cs_, s0); S1 = np.interp(cg, cs_, s1)
        # 原画の筋は x ≈ 130 で切れる：その c から右は 0.6 m で細くなって消える
        cend = cs_[-1]
        on = np.where(cg <= cend, 1.0, np.clip(1 - (cg - cend) / 0.6, 0, 1))
        mid = 0.5 * (S0 + S1); hw = 0.5 * (S1 - S0) * on
        S0, S1 = mid - hw, mid + hw
    else:
        S0 = S1 = np.zeros_like(cg); on = np.zeros_like(cg)
    return dict(c=cg, u_b=UB, u_m=UB + WM, u_s0=S0, u_s1=S1, streak_on=(on > 0.05).astype(float))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hero-rows", default=W.OUT + "/standin/standin_rows.npz")
    ap.add_argument("--out", default=OUTD)
    ap.add_argument("--iters", type=int, default=3)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ground = W.Ground(a.hero_rows)
    pts, cam1 = crest_line()
    cr = Crest(pts)
    log = []
    cam2 = painting_cam(2)
    for it in range(a.iters + 1):
        g = build_surface(cr, ground)
        P, tri_all, used, remap = mesh_from_grid(g)
        idb, zb = render_ids(cam2, P, tri_all)
        err = silhouette_error(cam2, 2, top_edge(idb))
        ok = np.isfinite(err[:, 1])
        e4 = err[err[:, 0] <= 340, 1]   # x ≤ 340：別の波が輪郭を作る所（その右は主役波の頂の線が受け持つ）
        worst = err[np.nanargmax(np.abs(err[:, 1]))]
        log.append({"iter": it, "err_px2_mean": W.rnd(np.nanmean(err[:, 1])), "err_px2_absmax": W.rnd(np.nanmax(np.abs(err[:, 1]))),
                    "err_disp_px_absmax": W.rnd(np.nanmax(np.abs(err[:, 1])) / 2), "worst_x_ref": W.rnd(worst[0], 0),
                    "err_disp_px_absmax_x_le_340": W.rnd(np.nanmax(np.abs(e4)) / 2)})
        print(log[-1])
        if it == a.iters:
            break
        # 直し：表示の画素の差 → 高さ（深さ s の 1 画素 = s·2tan(fov/2)/H）。c は頂の点の c。直しは足し合わせ、5 点でならす
        xs, s_, _, _, c_ = pts.T
        pxm = s_ * 2.0 * cam2.t / cam2.H
        dY = np.where(ok, err[:, 1] * pxm, 0.0)
        o = np.argsort(c_)
        dYs = np.convolve(np.pad(dY[o], 4, mode="edge"), np.ones(9) / 9, mode="valid")   # 9 点（約 1.5 m）でならす：頂の線に小さな波打ちを作らない
        if len(cr.corr_c) != len(o):
            cr.corr_c = c_[o]; cr.corr_v = np.zeros(len(o))
        cr.corr_v = cr.corr_v + dYs
    # 帯の境
    u_full = attributes(g, cr, dict(c=np.array([C_L, C_R]), u_b=np.zeros(2), u_m=np.zeros(2), u_s0=np.zeros(2), u_s1=np.zeros(2),
                                    streak_on=np.zeros(2)))["u"]
    recs, cam_m, idb_m, chips = measure_bands(g, P, tri_all, used, remap, u_full)
    bands = bands_from_recs(recs, cr)
    bands["chips"] = chips
    at = attributes(g, cr, bands)
    tri = remap[tri_all]
    Pv = P[used]
    nrm = W.vertex_normals(Pv, tri)
    ch = channels(g, at, used, nrm)
    ch["position"] = Pv
    h = W.write_static(a.out + "/wave4.json", ch, tri, {"note_ja": "見本04 W4：左端の別の小さな青い波（④）。AS04 Flat Smooth の属性（_AS03Src 1）。",
                                                          "hero_rows": a.hero_rows, "hero_rows_sha256": W.sha(a.hero_rows)})
    np.savez_compressed(a.out + "/wave4_grid.npz", c=g["c"], d=g["d"], fw=g["fw"], A=g["A"], Y=g["Y"], Yw=g["Yw"], G=g["G"], ac=g["ac"], yc=g["yc"],
                        u=at["u"], wsd=at["wsd"], used=used)
    # ---- 検査
    rel = (g["Y"] - g["G"]).ravel()[used]
    Q = K.sec(Pv)
    gb = ground(Q[:, 0], Q[:, 2])
    clr = Q[:, 1] - gb
    # 縁（境の辺）の頂点の、地面からの高さ
    e = np.sort(np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]]), 1)
    ue, cnt = np.unique(e, axis=0, return_counts=True)
    bv = np.unique(ue[cnt == 1].ravel())
    yt = Q[tri, 1]
    hz = np.max(np.linalg.norm(Q[tri][:, :, [0, 2]] - Q[tri][:, [1, 2, 0]][:, :, [0, 2]], axis=2), 1)
    steep_n = int(((yt.max(1) - yt.min(1) > 0.5) & ((yt.max(1) - yt.min(1)) / np.maximum(hz, 1e-6) > 3)).sum())
    rep = {"schema": "GreatWave.AS04.w4_build/1", "hero_rows": a.hero_rows, "hero_rows_sha256": W.sha(a.hero_rows),
           "mesh": a.out + "/wave4.json", "mesh_bin_sha256": h, "vertices": int(len(Pv)), "triangles": int(len(tri)),
           "params": {"LF_m": LF, "LB_m": LB, "back_taper_t": [TB1, TB2], "front_taper_t": [TF1, TF2], "c_range_m": [C_L, C_R], "eps_m": EPS, "k_m": KS,
                      "lambda_m": W.rnd(LAM), "profile": "sech^2"},
           "crest_in_frame": [{"x_ref": W.rnd(p[0], 1), "dist_m": W.rnd(p[1]), "a": W.rnd(p[2]), "y": W.rnd(p[3]), "c": W.rnd(p[4])} for p in pts[::5]],
           "crest_by_c": {"%.1f" % c: {"a": W.rnd(float(np.interp(c, g["c"], g["ac"]))), "Yc": W.rnd(float(np.interp(c, g["c"], g["yc"])))}
                          for c in (-28, -26, -24, -22, -20, -18, -16, -15, -14, -13, -12, -11, -10, -9, -8, -7, -6, -5, -4)},
           "silhouette_iterations": log,
           "clearance_above_ground_m": {"min": W.rnd(float(clr.min()), 4), "p01": W.rnd(float(np.percentile(clr, 1)), 4)},
           "boundary_vertices": int(len(bv)), "boundary_height_above_ground_m": {"min": W.rnd(float(clr[bv].min()), 4), "max": W.rnd(float(clr[bv].max()), 4)},
           "bands_measured": recs, "chips": chips, "bands_by_c": {"%.1f" % c: {k: W.rnd(float(np.interp(c, bands["c"], bands[k]))) for k in ("u_b", "u_m", "u_s0", "u_s1", "streak_on")}
                                                 for c in (-24, -20, -17, -16, -15, -14, -13, -12, -11, -10)},
           "steep_triangles_dy_gt_0p5_slope_gt_3": int(steep_n), "cliff_cells": g["cliff_cells"],
           "height_max_m": W.rnd(float(Q[:, 1].max())), "a_range": [W.rnd(float(Q[:, 0].min())), W.rnd(float(Q[:, 0].max()))],
           "c_range": [W.rnd(float(Q[:, 2].min())), W.rnd(float(Q[:, 2].max()))]}
    W.jdump(a.out + "/wave4_build_report.json", rep)
    print(json.dumps({k: rep[k] for k in ("vertices", "triangles", "clearance_above_ground_m", "boundary_height_above_ground_m", "height_max_m", "a_range", "c_range", "crest_by_c")}, ensure_ascii=False))
    print("bands", json.dumps(rep["bands_by_c"]))


if __name__ == "__main__":
    main()
