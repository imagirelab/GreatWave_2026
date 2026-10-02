# -*- coding: utf-8 -*-
"""仕上げ33修正01 修正の回 1：採った変種 SWEEP（立つ 3D の指）を、評審の直すべき 11 の指摘に合わせて作り直す（numpy。Unity の描画ではない）。

SWEEP（sweep_build.py）からの変更（名前の付いた美術の誘導。どれも爪の並びの頂点だけで決まる。色は PL29 Claw Shade の段と設計38 の縁の線。
原画カメラからの投影の色は使わない。原画のカメラは、形を決める射線と、主役波に隠れないこと・一覧の領域に収まることの検査にだけ使う。Q28）：
  - pl33r01f_list_path（指摘 4・7）：原画視点の 2 次元の道を一覧の中心線そのもの（S2 = 1.0）にする。3D の長さ（L3 = K3 × 2 次元の長さ）は奥行きで保つ。
  - pl33r01f_fan_curl（指摘 2）：射線の上の深さを、−|シートからの高さ − ht| − BETA × |深さ − 目標の 3D の指の深さ| が最も大きくなるよう動的計画法で選ぶ。
    目標の高さ ht は H_CAP × L3 × ρ（ρ＝根元の法線と原画のカメラへの向きの内積の平方根）で RISE_S まで立ち上がり、先で CURL_DROP だけ面の側へ巻き戻る。
    面が射線に寝る頂の稜（ρ が小さい）では高さを追わず、目標の指の向き＝外向きの法線へ扇に開く（SWEEP は稜の指も射線の向きへ長く伸ばし、箒に見えた）。
    目標の指は、根元のシートの法線に 2 次元の道の向きを少し混ぜた向き D から出て、道の弦の向き C の側へ THETA1 まで巻く
    （P*(s) = 根元 + L3 ∫ (cos θ D + sin θ C)、θ = THETA1 s^CURL_P）。原画視点の投影は 2 次元の道のまま。
  - pl33r01f_tube_clear（指摘 8）：高さは評審 judge_geo と同じ式（主役波の全部の列の頂点と np.gradient の法線）で測る。動的計画法の可否に、輪の中心でなく
    管の頂点の高さ（半径＝幅の半分 ＋ CLEAR）を入れる。さらにコマごとに、輪の頂点がシートより CLEAR_F 上にない輪を、原画のカメラの射線に沿ってカメラの側へ寄せる
    （原画視点の投影は変わらない）。寄せの大きさは根元から先へ累積の最大を取って駅の間で均し（駅ごとにばらばらに寄せると管が潰れ、背骨が折れた）、
    コマの間は前後 PUSH_WIN コマの最大を σ PUSH_SIG コマで均し、生まれたばかり（g < PUSH_G）は弱める。
  - pl33r01f_web（指摘 1・9）：指ごとに、鉤の内の側（背骨から根元 → 先の弦へ向く側）の管の面から、水色の版の膜（id WF…、2 面の薄い帯）を指に付けて立てる。
    幅は管の幅 × WEB_W（b区域は WEB_WB）× 鐘（背骨の u WEB_U0〜1）× 巻き kc で、弦までの離れが管の幅 × WEB_DSCL より近い所は細くする。内の向きは t* の形で決め、
    根元の座標系で運ぶ（コマごとに測り直すと向きが跳んだ）。t* の原画視点で一覧の爪の領域（WEB_DIL px の窓で広げた所）を出ない幅までに縮め、コマごとに外の縁を
    シートより WEB_CLEAR 上に保つ縮めを、前後 WEB_WIN コマの最小を σ PUSH_SIG コマで均してから使う。色は PL33ClawLook が W… の全部の頂点を水色の版にする（線なし）。
  - pl33r01f_web33（指摘 1・9）：仕上げ33 修正の回 2 の鉤の内の膜（WC…、面に沿う低い浮き彫り）も、指の根元の陰として戻す（消した指の膜は除く）。
  - pl33r01f_bold（指摘 5）：根元の幅を W_REL × L3（W_MIN〜W_MAX）、先の幅を TIP_W 倍に太くし、頂と唇の主役の指（一覧で輪郭の上の長い爪の上位 HERO_N 本）は
    幅を HERO_W 倍にし、そのうち稜の指（ρ ≤ HERO_RHO か、原画視点の道が主役波の輪郭の外へ RIM_OUT を超えて出る指）だけ 3D の長さを HERO_K 倍にする
    （奥行きで伸ばすので原画視点の道は変わらない）。面がカメラを向き輪郭にかからない指（ρ > FACE_RHO）は 3D の長さを L3_FACE_MAX までにする
    （射線の向きに 5〜6 m 伸びた C080 などが座席から平行な棒に見えた）。冠の爪は断面を CROWN_THICK 倍（先へ CROWN_TIP 倍）に太らせる
    （pl33r01f_crown_bold。原画のカメラから隠れたまま）。
  - pl33r01f_cull（指摘 3）：立てられない指（主役波に隠れる・射線の上にシートより上の点がない）は、仕上げ33 の帯の中心線に戻さず、根元の点に潰す（消す）。
  - pl33r01f_crown_low（指摘 3）：後ろ 65° と回り台 180〜240° でドームの白の上に平たく見えた鉤の群れは、SWEEP の冠の爪の低い房（K027〜K029・K037〜K040 など。
    評審の読みの「立てられない 10 本の指」ではなかった）だった。根元の高さ（房の平均）が CROWN_Y_MIN 未満の房は、頂の稜の外に立たないので消す。
  - pl33r01f_smooth（指摘 10）：帯の長さの割合 g を時間で単調にして均し（σ G_SIG コマ）、背骨の根元に対する位置を t* の前のコマで時間に均す（σ T_SIG コマ、
    t* に向けて重みを 0 へ）。冠の爪（K…、SWEEP の sweep_crown の出力）も同じ式で根元に対する位置を時間に均す。
  - pl33r01f_section（指摘 6）：断面の白の向きは、根元で t* の白の向きを接線に直交させ、背骨に沿って平行に運ぶ（回転の少ない枠）。深さの道は σ SMOOTH 駅で均す
    （深さの折り返しが 1 駅で起きると背骨が 140° 折れた）。測り直しは r01_measure.py（輪の中心＝頂点 2 と 6 の中点）。
入力（Git 対象外）：仕上げ33 修正の回 2 の爪の並び Unity/Build/Polish/33/fix02/claws（帯＝成長の割合と根元）、仕上げ32 修正の回 1 の rig、一覧、
  主役波 Unity/Build/Polish/32/white/hero_pkg、時間曲線 G_p28rec、SWEEP の冠の爪 Unity/Build/Polish/33r01/sweep/crown。
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33r01/fix01/claws）。ds33_claw_layout.json の書式（GreatWave.DS33.claw_layout/1）。
使い方（リポジトリの根で。重い numpy の処理と同時に回さない）：py -3.10 -B Tools/GWWaveGen/pl33r01/r01_build.py [--out …] [引数]
"""
import argparse
import json
import os
import shutil
import sys
import time

import cv2
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
import sweep_build as SB  # noqa: E402

U, W31 = SB.U, SB.W31
from pl33_common import TStarDepth, layout_tris, sha  # noqa: E402

B = REPO + "/Unity/Build/Polish"
SRC = SB.SRC
RIG = SB.RIG
HERO = SB.HERO
WARP = SB.WARP
INV = SB.INV
CROWN = B + "/33r01/sweep/crown"
OUT = B + "/33r01/fix01/claws"
K_STAR = SB.K_STAR
HZ = SB.HZ
Q_ANG = SB.Q_ANG
WEB_ANG = np.radians(np.arange(8) * 45.0)

P = dict(S2=1.0, K3=4.0, L3_MIN=1.2, L3_MAX=5.0, STEP_MAX=1.35, KZ=121, MU=0.02, VIS_TOL=0.06, ROOT_TOL=0.25,
         H_MIN=0.03, CLEAR=0.04, FAN_P=0.35, THETA1=130.0, CURL_P=1.4, H_CAP=0.75, RISE_S=0.6, CURL_DROP=0.35, BETA=0.35, RHO_P=0.5,
         W_REL=0.20, W_MIN=0.34, W_MAX=0.80, TIP_W=0.22, FLAT=0.70, TAPER=1.3, SMOOTH=3.0, N_UP=0.35, N_CURL=0.6,
         G_W0=0.35, G_W1=0.30, G_C0=0.45, W_STEPS=(0.8, 0.65, 0.5), INSIDE_MIN=0.99, ALLOW_DIL=5,
         HERO_N=24, HERO_K=1.4, HERO_W=1.25, HERO_L3_MAX=6.5, HERO_RHO=0.8, FACE_RHO=0.8, L3_FACE_MAX=3.5, RIM_OUT=0.05,
         CLEAR_F=0.03, PUSH_MAX=0.9, PUSH_G=0.3, PUSH_WIN=9, PUSH_RAMP=0, PUSH_SIG=3.0, G_SIG=5.0, T_SIG=3.0, T_RAMP=24, CROWN_Y_MIN=12.0,
         WEB_W=3.5, WEB_WB=6.0, WEB_U0=0.10, WEB_DSCL=0.15, WEB_WIN=9, CROWN_THICK=1.4, CROWN_TIP=2.2, WEB33=1, WEB_N=12, WEB_TH=0.03, WEB_CLEAR=0.03, WEB_DIL=9)


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


arclen = SB.arclen
resample_curve = SB.resample_curve
ray_points = SB.ray_points


def target_curve(R, D, C, L, s):
    """pl33r01f_fan_curl の目標の指 P*(s)：根元 R から向き D で出て、C の側へ THETA1 まで巻く（長さ L）。"""
    ss = np.linspace(0.0, 1.0, 241)
    th = np.radians(P["THETA1"]) * ss ** P["CURL_P"]
    t = np.cos(th)[:, None] * D[None, :] + np.sin(th)[:, None] * C[None, :]
    seg = 0.5 * (t[1:] + t[:-1]) * np.diff(ss)[:, None]
    cum = np.vstack([np.zeros(3), np.cumsum(seg, axis=0)])
    return R[None, :] + L * np.stack([np.interp(s, ss, cum[:, k]) for k in range(3)], -1)


def stand_spine(cam, dep, sheet, xy, z0, L3, R, D, C, wj, rho, relax=1.0):
    """深さの動的計画法。score＝−|シートからの高さ − 目標の高さ ht| − BETA × |深さ − 目標の指 P* の深さ|。
    目標の高さは H_CAP × L3 × ρ（ρ＝根元の法線と原画のカメラへの向きの内積の平方根：面が射線に寝る稜では 0 に近く、指は P* の向き＝外向きの法線へ扇に開く）で、
    RISE_S まで立ち上がり、先で CURL_DROP だけ面の側へ巻き戻る（3D の巻き）。可否＝原画のカメラから見える・管の頂点がシートより上（下の頂点＝厚みの半分 ＋ CLEAR）。"""
    n = len(xy) - 1
    K = P["KZ"]
    dz = np.linspace(-L3, L3, K)
    Z = z0 + dz[None, :].repeat(n + 1, 0)
    Q = ray_points(cam, xy, Z)
    h = sheet.height(Q)
    vis = dep.visible(Q.reshape(-1, 3), P["VIS_TOL"]).reshape(n + 1, K)
    s = np.arange(n + 1) / n
    Pt = target_curve(R, D, C, L3, s)
    zP = (Pt - cam.pos) @ cam.f
    ht = P["H_CAP"] * L3 * rho * (np.sin(0.5 * np.pi * np.minimum(1.0, s / P["RISE_S"])) - P["CURL_DROP"] * sm((s - P["RISE_S"]) / (1 - P["RISE_S"])))
    score = -np.abs(h - ht[:, None]) - P["BETA"] * np.abs(Z - zP[:, None])
    need = P["H_MIN"] * np.minimum(1.0, s * 4) + relax * (0.5 * wj + P["CLEAR"]) * sm((s - 0.15) / 0.25)
    ok = vis & (h >= need[:, None] - 0.02)
    ok[:2] |= dep.visible(Q[:2].reshape(-1, 3), P["ROOT_TOL"]).reshape(2, K) & (h[:2] > -0.10)
    score = np.where(ok, score, -1e6)
    step = P["STEP_MAX"] * L3 / n
    k0 = int(np.argmin(np.abs(dz)))
    acc = np.full(K, -1e9)
    acc[k0] = 0.0
    back = np.zeros((n + 1, K), np.int64)
    for j in range(1, n + 1):
        Dd = np.linalg.norm(Q[j][:, None, :] - Q[j - 1][None, :, :], axis=-1)
        tr = acc[None, :] - P["MU"] * ((dz[:, None] - dz[None, :]) / step) ** 2
        tr = np.where(Dd <= step, tr, -1e12)
        b = np.argmax(tr, axis=1)
        acc = tr[np.arange(K), b] + score[j]
        back[j] = b
    k = int(np.argmax(acc))
    path = [k]
    for j in range(n, 0, -1):
        k = int(back[j, k])
        path.append(k)
    path = np.array(path[::-1])
    zz = z0 + dz[path]
    if P["SMOOTH"] > 0:
        zs = gaussian_filter1d(zz, P["SMOOTH"], mode="nearest")
        zs[0] = z0
        zz = zs
    pts = ray_points(cam, xy, zz[:, None])[:, 0]
    pushed = 0
    for j in range(1, n + 1):
        for it in range(24):
            if dep.visible(pts[j:j + 1], P["VIS_TOL"])[0] and sheet.height(pts[j:j + 1])[0] >= need[j] - 0.02:
                break
            zz[j] -= 0.05
            pts[j] = ray_points(cam, xy[j:j + 1], zz[j:j + 1, None])[0, 0]
            pushed += 1
    hh = sheet.height(pts)
    return pts, dict(z=zz.tolist(), h_max=float(hh.max()), h_tip=float(hh[-1]), len3d=float(arclen(pts)[-1]), pushed=pushed,
                     dp_score=float(acc.max()), invalid=bool(acc.max() < -1e5),
                     target_dev_m=float(np.median(np.linalg.norm(pts - Pt, axis=1))))


def widths(n, wr, gw=1.0):
    a = np.arange(n + 1) / n
    w = wr * gw * (1 - (1 - P["TIP_W"]) * a ** P["TAPER"])
    return w, P["FLAT"] * w


def ring_frames(pts, o_ref, up):
    T = np.gradient(pts, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    kap = np.gradient(T, axis=0)
    kn = np.linalg.norm(kap, axis=1, keepdims=True)
    curl_out = -kap / np.maximum(kn, 1e-9) * np.minimum(1.0, kn * 4.0)
    raw = o_ref[None, :] + P["N_CURL"] * curl_out + P["N_UP"] * up[None, :]
    N = raw - (raw * T).sum(1, keepdims=True) * T
    nn = np.linalg.norm(N, axis=1, keepdims=True)
    for j in range(len(N)):
        if nn[j, 0] < 1e-6:
            N[j] = N[j - 1] if j > 0 else np.cross(T[j], [1.0, 0.0, 0.0])
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    for j in range(1, len(N)):
        if (N[j] * N[j - 1]).sum() < 0:
            N[j] = -N[j]
    N = gaussian_filter1d(N, 1.0, axis=0, mode="nearest")
    N = N - (N * T).sum(1, keepdims=True) * T
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return T, N, np.cross(N, T)


def tube(pts, N, Bv, w, t, ang=Q_ANG):
    n = len(pts) - 1
    c, s = np.cos(ang), np.sin(ang)
    ring = (pts[:n, None, :] + Bv[:n, None, :] * (0.5 * w[:n, None] * c[None, :])[..., None]
            + N[:n, None, :] * (0.5 * t[:n, None] * s[None, :])[..., None])
    return ring, pts[n]


class JSheet:
    """動的計画法の高さ：t* の主役波の全部の列の頂点と np.gradient の法線（評審 judge_geo と同じ式。SWEEP の Sheet は本体の列と frame_at の法線）。"""

    def __init__(self, X0):
        self.fs = FrameSheet(X0)

    def height(self, Q):
        return self.fs.h(Q)[0]


class FrameSheet:
    """コマの主役波の全部の列の頂点と法線（評審 judge_geo と同じ式：np.gradient の外積）。"""

    def __init__(self, Xs):
        nrm = np.cross(np.gradient(Xs, axis=0), np.gradient(Xs, axis=1))
        self.N = (nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)).reshape(-1, 3)
        self.V = Xs.reshape(-1, 3)
        self.tree = cKDTree(self.V)

    def h(self, Q):
        sh = Q.shape[:-1]
        Qf = Q.reshape(-1, 3)
        _, ii = self.tree.query(Qf)
        e = Qf - self.V[ii]
        hh = (e * self.N[ii]).sum(1)
        return hh.reshape(sh), self.N[ii].reshape(sh + (3,))


def time_smooth(A, sig, ramp_end, ramp_len):
    """A（F × …）の時間に均した値。コマ ramp_end − ramp_len から ramp_end へ重みを 1 → 0 にし、ramp_end 以後は元のまま（t* の形を変えない）。"""
    if sig <= 0:
        return A
    S = gaussian_filter1d(A, sig, axis=0, mode="nearest")
    F = A.shape[0]
    f = np.arange(F, dtype=np.float64)
    w = 1.0 - sm((f - (ramp_end - ramp_len)) / ramp_len)
    w[f >= ramp_end] = 0.0
    return A + w.reshape((F,) + (1,) * (A.ndim - 1)) * (S - A)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--crown-src", default=CROWN)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--set", action="append", default=[], help="P の値を KEY=VALUE で上書き（試し用）")
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--debug-ids", default="", help="調べ用：この爪の背骨・寄せ・g を --out の r01_debug.npz へ")
    a = ap.parse_args()
    for kv in a.set:
        k, v = kv.split("=", 1)
        P[k] = type(P[k])(float(v)) if not isinstance(P[k], tuple) else tuple(float(x) for x in v.split(","))
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V0 = lay["frames"], lay["vertices"]
    fr_src = np.memmap(os.path.join(a.src, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V0, 3))
    rig = {c["id"]: c for c in json.load(open(RIG, encoding="utf-8"))["claws"]}
    inv = json.load(open(INV, encoding="utf-8"))
    invd = {c["id"]: c for c in inv["claws"]}
    hero = U.K.Pkg(HERO)
    wt, wtau = W31.load_warp(WARP)
    tk = np.arange(F) / HZ
    taus = np.where(tk >= 12.0 - 1e-9, 0.0, np.interp(tk, wt, wtau))
    X0 = hero.world(0.0)
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    cam = U.CamWH(spec, 1920, 1080)
    dep = TStarDepth(X0)
    sheet = JSheet(X0)
    up = np.array([0.0, 1.0, 0.0])
    claws = [c for c in lay["claws"] if c["id"].startswith("C")]
    clay = json.load(open(os.path.join(a.crown_src, "ds33_claw_layout.json"), encoding="utf-8"))
    crowns = [c for c in clay["claws"] if c["id"].startswith("K")]
    cfr = np.memmap(os.path.join(a.crown_src, clay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(clay["frames"], clay["vertices"], 3))
    print("claws", len(claws), "crowns", len(crowns), round(time.time() - t0, 1), "s", flush=True)

    # ---- 帯（仕上げ33 修正の回 2）の中心線・根元と、成長の割合 g（pl33r01f_smooth：単調にして時間に均す）
    band = {}
    for c in claws:
        o, nv = c["vert_offset"], c["vert_count"]
        n = (nv - 11) // 8
        blk = np.asarray(fr_src[:, o:o + nv, :], np.float64)
        cen = np.concatenate([blk[:, 1:1 + n * 8].reshape(F, n, 8, 3).mean(2), blk[:, 1 + n * 8][:, None]], axis=1)
        L = np.linalg.norm(np.diff(cen, axis=1), axis=2).sum(1)
        g = np.clip(L / max(L[K_STAR], 1e-9), 0.0, 1.0)
        g[L < 1e-6] = 0.0
        g_raw = g.copy()
        gm = np.maximum.accumulate(np.where(np.arange(F) <= K_STAR, g, 1.0))
        birth = int(np.argmax(gm > 0)) if (gm > 0).any() else F
        gs = gaussian_filter1d(gm, P["G_SIG"], mode="nearest")
        gs[:birth] = 0.0
        gs = np.maximum.accumulate(np.clip(gs, 0, 1))
        gs[K_STAR:] = 1.0
        band[c["id"]] = dict(n=n, cen=cen, g=gs, g_raw=g_raw, root=blk[:, 0], circ=blk[:, 2 + n * 8:], birth=birth)
    print("bands read", round(time.time() - t0, 1), "s", flush=True)

    # ---- 原画視点で指・膜が入ってよい所（一覧の全部の爪の領域を広げた所と主役波）
    regs = np.zeros((1080, 1920), np.uint8)
    for ci in inv["claws"]:
        poly = ci.get("region_polygon_ref") or ci.get("polygon_ref_af29")
        if poly:
            cv2.fillPoly(regs, [np.round(U.to_disp(np.array(poly, np.float64))).astype(np.int32)], 1)
    allow = (cv2.dilate(regs, np.ones((P["ALLOW_DIL"], P["ALLOW_DIL"]), np.uint8))
             | cv2.dilate(dep.mask.astype(np.uint8), np.ones((3, 3), np.uint8))).astype(bool)
    allow_web = cv2.dilate(regs, np.ones((P["WEB_DIL"], P["WEB_DIL"]), np.uint8)).astype(bool)

    def inside(Q, mask):
        q, _ = cam.project(Q)
        xi = np.round(q[..., 0]).astype(int)
        yi = np.round(q[..., 1]).astype(int)
        ok = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080)
        ins = np.zeros(q.shape[:-1], bool)
        ins[ok] = mask[yi[ok], xi[ok]]
        return ins

    # ---- 主役の指（pl33r01f_bold）：一覧で輪郭の上（silhouette）の、根元から立つ（親のない）爪のうち 2 次元の道の長い上位 HERO_N 本
    cand = []
    for c in claws:
        cid = c["id"]
        if rig[cid]["parent"] or not invd.get(cid, {}).get("silhouette"):
            continue
        xy, _ = cam.project(band[cid]["cen"][K_STAR])
        cand.append((float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum()), cid))
    heroes = set(cid for _, cid in sorted(cand, reverse=True)[:int(P["HERO_N"])])
    print("heroes", len(heroes), sorted(heroes), flush=True)

    # ---- t* の指（親から先に）
    order = sorted(claws, key=lambda c: 1 if rig[c["id"]]["parent"] else 0)
    fing = {}
    for c in order:
        cid = c["id"]
        rg = rig[cid]
        bd = band[cid]
        n = bd["n"]
        cen = bd["cen"][K_STAR]
        xy, zc = cam.project(cen)
        par = rg["parent"]
        if par and fing.get(par, {}).get("culled"):
            par = None
        best = None
        hero_k = P["HERO_K"] if cid in heroes else 1.0
        for ws in (1.0,) + tuple(P["W_STEPS"]):
            if par and par in fing:
                pf = fing[par]
                sig = float(rg["attach_sigma"])
                pxy = pf["xy2"]
                sp = arclen(np.c_[pxy, np.zeros(len(pxy))])
                rxy = np.array([np.interp(sig * sp[-1], sp, pxy[:, 0]), np.interp(sig * sp[-1], sp, pxy[:, 1])])
                xy2 = rxy[None, :] + P["S2"] * (xy - xy[0])
                Rr = resample_curve(pf["pts"], np.array([sig]))[0]
                _, z0 = cam.project(Rr[None, :])
                z0 = float(z0[0])
                anchor = dict(kind="parent", parent=par, sigma=sig)
                r_, c_ = rig[par]["sheet_rc"]
            else:
                xy2 = xy[0][None, :] + P["S2"] * (xy - xy[0])
                z0 = float(zc[0])
                Rr = bd["root"][K_STAR].astype(np.float64)
                anchor = dict(kind="sheet", rc=[float(v) for v in rg["sheet_rc"]])
                r_, c_ = rg["sheet_rc"]
            px_m = z0 * 2.0 * cam.t / 1080.0
            l2 = float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum() * px_m)
            # ρ（根元の法線と原画のカメラへの向きの内積の平方根）：面がカメラを向く所ほど 1。主役の指の長さを伸ばすのは ρ ≤ HERO_RHO（頂と唇の稜）だけにし、
            # 面がカメラを向く所（ρ > FACE_RHO）の指は 3D の長さを L3_FACE_MAX までにする（射線の向きに長く伸びた指が座席から平行な棒に見えた）
            Fr0 = U.frame_at(X0, float(r_), float(c_))
            rdir0 = Rr - cam.pos
            rdir0 /= max(np.linalg.norm(rdir0), 1e-9)
            rho0 = float(np.clip(Fr0[2] @ (-rdir0), 0.0, 1.0) ** P["RHO_P"])
            # 原画視点の道が主役波の輪郭の外へ出る指（輪郭にかかる指）は稜の指として扱う（短くすると先が唇の面に寄り、輪郭の線を白で欠いて 132 σ12 が 4.99 px になった）
            rim = float(1.0 - dep.inside(ray_points(cam, xy2, np.full((len(xy2), 1), z0))[:, 0]).mean()) > P["RIM_OUT"]
            hk = hero_k if (rho0 <= P["HERO_RHO"] or rim) else 1.0
            L3 = float(np.clip(P["K3"] * l2 * hk, P["L3_MIN"], P["HERO_L3_MAX"] if (cid in heroes and hk > 1.0) else P["L3_MAX"]))
            if rho0 > P["FACE_RHO"] and not rim:
                L3 = min(L3, P["L3_FACE_MAX"])
            if par:
                L3 = float(np.clip(P["K3"] * l2, 0.6 * P["L3_MIN"], 0.6 * fing[par]["L3"]))
            Fr = U.frame_at(X0, float(r_), float(c_))
            nrm = Fr[2]
            # 目標の向き：法線＋2 次元の道の出だしの向き（根元の深さの面の上の 3D）、巻きの側：道の弦
            q1 = ray_points(cam, xy2[[0, min(2, n), n]], np.full((3, 1), z0))[:, 0]
            p0 = q1[1] - q1[0]
            p0 = p0 / max(np.linalg.norm(p0), 1e-9)
            Dd = nrm + P["FAN_P"] * p0
            Dd /= max(np.linalg.norm(Dd), 1e-9)
            ch = q1[2] - q1[0]
            Cc = ch - (ch @ Dd) * Dd
            if np.linalg.norm(Cc) < 1e-6:
                Cc = np.cross(Dd, cam.f)
            Cc /= max(np.linalg.norm(Cc), 1e-9)
            wr = float(np.clip(P["W_REL"] * L3, P["W_MIN"], P["W_MAX"])) * (P["HERO_W"] if cid in heroes else 1.0)
            if par:
                wr = min(wr, 0.7 * fing[par]["wr"])
            wj, _ = widths(n, wr * ws)
            rdir = Rr - cam.pos
            rdir /= max(np.linalg.norm(rdir), 1e-9)
            rho = float(np.clip(nrm @ (-rdir), 0.0, 1.0) ** P["RHO_P"])
            pts, info = stand_spine(cam, dep, sheet, xy2, z0, L3, Rr, Dd, Cc, wj, rho)
            info["fallback"] = None
            # 立てられない時：長さ 0.6 倍 → 管の下の頂点の許しを 0.3 倍（コマごとの寄せに任せる）→ 両方 → 消す（pl33r01f_cull）
            for fb, L3s, rl in (("short", max(0.6 * L3, 0.6 * P["L3_MIN"]), 1.0), ("relax", L3, 0.3), ("short_relax", max(0.6 * L3, 0.6 * P["L3_MIN"]), 0.3)):
                if not info["invalid"]:
                    break
                pts1, info1 = stand_spine(cam, dep, sheet, xy2, z0, L3s, Rr, Dd, Cc, wj, rho, rl)
                if not info1["invalid"]:
                    pts, info, L3 = pts1, dict(info1, fallback=fb), L3s
                else:
                    info = dict(info1, fallback="cull")
            info["rho"] = round(rho, 3)
            info["rim"] = bool(rim)
            if info["fallback"] == "cull":
                best = dict(culled=True, pts=np.repeat(Rr[None, :], n + 1, 0), xy2=xy2, L3=0.0, l2=l2, wr=0.0, anchor=anchor, Fr=Fr,
                            N=np.tile(nrm, (n + 1, 1)), info=dict(info, s2=P["S2"], w_scale=0.0, inside_frac=None), n=n, root_rc=(float(r_), float(c_)),
                            hero=cid in heroes)
                break
            pts[0] = Rr
            p0_ = pts[0].copy()
            pts = resample_curve(pts, np.linspace(0.0, 1.0, len(pts)))
            pts[0] = p0_
            T, N, Bv = ring_frames(pts, nrm, up)
            w_, t_ = widths(n, wr * ws)
            ring_, tip_ = tube(pts, N, Bv, w_, t_)
            fr_in = float(inside(np.concatenate([ring_.reshape(-1, 3), tip_[None, :]]), allow).mean())
            info.update(s2=P["S2"], w_scale=ws, inside_frac=round(fr_in, 4))
            best = dict(culled=False, pts=pts, xy2=xy2, L3=L3, l2=l2, wr=wr * ws, anchor=anchor, Fr=Fr, N=N, info=info, n=n,
                        root_rc=(float(r_), float(c_)), hero=cid in heroes, D=Dd, C=Cc)
            if fr_in >= P["INSIDE_MIN"]:
                break
        fing[cid] = best
    culled = sorted(cid for cid, f in fing.items() if f["culled"])
    st = {}
    for f in fing.values():
        k = "cull" if f["culled"] else "%.2f" % f["info"]["w_scale"]
        st[k] = st.get(k, 0) + 1
    print("t* fingers", len(fing), "width steps", st, "culled", culled, round(time.time() - t0, 1), "s", flush=True)

    # ---- 1 回目：コマごとの背骨（根元の局所の座標系で育てる）と断面の白の向き
    loc = {}
    for cid, f in fing.items():
        base = f["pts"][0]
        loc[cid] = dict(P=(f["pts"] - base) @ f["Fr"].T, N=f["N"] @ f["Fr"].T)
    SP = {cid: np.zeros((F, f["n"] + 1, 3)) for cid, f in fing.items()}
    GG = {cid: np.zeros(F) for cid in fing}
    for fi in range(F):
        tau = float(taus[fi])
        Xf = X0 if abs(tau) < 1e-12 else hero.world(tau)
        now = {}
        for c in order:
            cid = c["id"]
            f = fing[cid]
            bd = band[cid]
            n = f["n"]
            g = float(bd["g"][fi])
            if f["anchor"]["kind"] == "sheet":
                Fr = f["Fr"] if fi == K_STAR else U.frame_at(Xf, *f["root_rc"])
                root = bd["root"][fi]
            else:
                par = f["anchor"]["parent"]
                pp = now[par]
                Fr = pp["Fr"]
                Lp = arclen(pp["pts"])[-1]
                sig = f["anchor"]["sigma"]
                gp = pp["g"]
                g = min(g, float(sm((gp - sig) / max(1.0 - sig, 1e-6))))
                if Lp < 1e-6 or gp <= sig:
                    root = pp["pts"][-1] if Lp > 0 else bd["root"][fi]
                else:
                    root = resample_curve(pp["pts"], np.array([sig / gp]))[0]
            GG[cid][fi] = g
            if f["culled"] or g <= 1e-6:
                SP[cid][fi] = root
                now[cid] = dict(Fr=Fr, pts=np.repeat(root[None, :], n + 1, 0), g=0.0 if f["culled"] else g)
                continue
            lp = loc[cid]
            u = np.arange(n + 1) / n
            curved = resample_curve(lp["P"], u * g)
            d0 = resample_curve(lp["P"], np.array([min(1.0, 0.35 * g + 1e-3)]))[0]
            d0 = d0 / max(np.linalg.norm(d0), 1e-12)
            Lg = arclen(lp["P"])[-1] * g
            straight = u[:, None] * Lg * d0[None, :]
            kc = sm((g - P["G_C0"]) / (1.0 - P["G_C0"]))
            Pl = (1 - kc) * straight + kc * curved
            pts = root[None, :] + Pl @ Fr
            SP[cid][fi] = pts
            now[cid] = dict(Fr=Fr, pts=pts, g=g)
        if fi % 60 == 0:
            print("pass1 frame", fi, round(time.time() - t0, 1), "s", flush=True)

    # ---- pl33r01f_smooth：根元に対する背骨を、t* の前のコマで時間に均す
    for cid, f in fing.items():
        if f["culled"]:
            continue
        A = SP[cid]
        rel = A - A[:, :1]
        rel = time_smooth(rel, P["T_SIG"], K_STAR, P["T_RAMP"])
        A[:, 1:] = A[:, :1] + rel[:, 1:]
        # 生まれる前（g = 0）は根元に潰したまま
        z = GG[cid] <= 1e-6
        A[z] = A[z][:, :1]

    # ---- 膜（pl33r01f_web）の形：背骨の u WEB_U0〜1 の駅で、管の内の側（弦へ向く向き e）の面から、管の幅 × WEB_W（b区域 WEB_WB）× 鐘 × 巻き kc の帯。
    #      弦までの離れが管の幅の半分より小さい所（真っ直ぐな指）は細くする。
    def web_geom(spine, wspine, kc, wmul, cap=None, ed=None):
        """ed＝None は t* の形（弦から内の向き e と弦までの離れを測る）。ed＝(e, dist) はコマの形（t* の e を根元の座標系で運んだもの）。"""
        uu = np.linspace(P["WEB_U0"], 1.0, int(P["WEB_N"]) + 1)
        a0 = resample_curve(spine, uu)
        ww = np.interp(uu, np.linspace(0, 1, len(wspine)), wspine)
        Tw = np.gradient(a0, axis=0)
        Tw /= np.maximum(np.linalg.norm(Tw, axis=1, keepdims=True), 1e-12)
        if ed is None:
            chord = spine[0][None, :] + uu[:, None] * (spine[-1] - spine[0])[None, :]
            e = chord - a0
            e = e - (e * Tw).sum(1, keepdims=True) * Tw
            dist = np.linalg.norm(e, axis=1)
        else:
            # コマの形：t* の e を根元の座標系で運んだまま使う（今の接線に直交させると、接線と e が近い所で向きが跳ぶ）
            e, dist = ed
        nrm_e = np.linalg.norm(e, axis=1)
        e = e.copy()
        for j in range(len(uu)):
            if nrm_e[j] < 1e-4:
                e[j] = e[j - 1] if j > 0 else np.cross(Tw[j], up)
            e[j] /= max(np.linalg.norm(e[j]), 1e-12)
        bell = np.sin(np.pi * np.clip((uu - P["WEB_U0"]) / (1.0 - P["WEB_U0"]), 0, 1)) ** 0.6
        wd = wmul * ww * bell * kc * np.minimum(1.0, dist / np.maximum(P["WEB_DSCL"] * ww, 1e-6))
        wd[-1] = 0.0
        if cap is not None:
            wd = np.minimum(wd, cap)
        a_ = a0 + (0.45 * ww)[:, None] * e
        b_ = a_ + wd[:, None] * e
        return uu, a_, b_, wd, e, Tw, dist

    def web_ed(cid, g, Fr):
        """t* の内の向き e（根元の座標系）と弦までの離れを、今の指の駅（全体の u = uu × g）へ写す。"""
        uu = np.linspace(P["WEB_U0"], 1.0, int(P["WEB_N"]) + 1)
        el, dl = webdir[cid]
        uf = np.clip(uu * g, P["WEB_U0"], 1.0)
        e = np.stack([np.interp(uf, uu, el[:, k]) for k in range(3)], -1) @ Fr
        return e, np.interp(uf, uu, dl)

    webcap = {}
    webdir = {}
    if not a.no_web:
        for cid, f in fing.items():
            if f["culled"]:
                continue
            wmul = P["WEB_WB"] if rig[cid].get("b_region_q16") else P["WEB_W"]
            wsp, _ = widths(f["n"], f["wr"])
            uu, a_, b_, wd, e, _, dist = web_geom(SP[cid][K_STAR], wsp, 1.0, wmul)
            webdir[cid] = (e @ f["Fr"].T, dist)
            cap = np.zeros(len(uu))
            fr = np.linspace(0, 1, 9)[1:]
            for j in range(len(uu)):
                if wd[j] <= 1e-6:
                    continue
                Qs = a_[j][None, :] + (fr * wd[j])[:, None] * e[j][None, :]
                ok = inside(Qs, allow_web) & dep.visible(Qs, 0.3)
                bad = np.where(~ok)[0]
                cap[j] = wd[j] * (fr[bad[0] - 1] if len(bad) and bad[0] > 0 else (0.0 if len(bad) else 1.0))
            cap = np.minimum(cap, gaussian_filter1d(cap, 0.8, mode="nearest") + 0.03)
            webcap[cid] = cap

    # ---- 2 回目（a）：コマごとに輪と断面の白の向きを作り、管の頂点の高さで足りない分の寄せ（射線に沿ってカメラの側へ）を測る（pl33r01f_tube_clear）
    def make_ring(f, cid, fi, pts, g, Fr, prevN):
        n = f["n"]
        u = np.arange(n + 1) / n
        # pl33r01f_section（指摘 6）：断面の白の向きは、根元で t* の白の向き（シートの法線・巻きの外・上の混ぜ）を接線に直交させ、
        # 背骨に沿って平行に運ぶ（回転の少ない枠）。輪の間のねじれが起きず、コマの間も根元の向きと背骨が滑らかなら滑らかに変わる
        T = np.gradient(pts, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
        N0 = loc[cid]["N"][0] @ Fr
        N0 = N0 - (N0 @ T[0]) * T[0]
        if np.linalg.norm(N0) < 0.25:
            ref = prevN[0] if prevN is not None else Fr[2]
            N0 = ref - (ref @ T[0]) * T[0]
            if np.linalg.norm(N0) < 1e-6:
                N0 = np.cross(T[0], [1.0, 0.0, 0.0])
        Nn = np.zeros((n + 1, 3))
        Nn[0] = N0 / max(np.linalg.norm(N0), 1e-12)
        for j in range(1, n + 1):
            v = Nn[j - 1] - (Nn[j - 1] @ T[j]) * T[j]
            if np.linalg.norm(v) < 1e-6:
                v = Nn[j - 1]
            Nn[j] = v / max(np.linalg.norm(v), 1e-12)
        if prevN is not None and Nn[0] @ prevN[0] < 0:
            Nn = -Nn
        Bv = np.cross(Nn, T)
        gw = P["G_W0"] + (1 - P["G_W0"]) * sm(g / P["G_W1"])
        w, t = widths(n, f["wr"], gw)
        ring, tip = tube(pts, Nn, Bv, w, t)
        return ring, tip, Nn, w

    def frame_of(f, fi, Xs):
        return f["Fr"] if (fi == K_STAR or f["anchor"]["kind"] != "sheet") else U.frame_at(Xs, *f["root_rc"])

    live_ids = [c["id"] for c in claws if not fing[c["id"]]["culled"]]
    NN = {cid: np.zeros((F, fing[cid]["n"] + 1, 3)) for cid in live_ids}
    PU = {cid: np.zeros((F, fing[cid]["n"], 3)) for cid in live_ids}
    prevNs = {}
    push_stats = dict(rings_pushed=0, max_push_raw_m=0.0, frames_with_push=0)
    for fi in range(F):
        tau = float(taus[fi])
        Xs = X0 if abs(tau) < 1e-12 else hero.world(tau)
        fs = FrameSheet(Xs)
        any_push = False
        for cid in live_ids:
            f = fing[cid]
            n = f["n"]
            pts = SP[cid][fi].copy()
            g = GG[cid][fi]
            if g <= 1e-6 or np.linalg.norm(pts[-1] - pts[0]) < 1e-6:
                continue
            ring, tip, Nn, _ = make_ring(f, cid, fi, pts, g, frame_of(f, fi, Xs), prevNs.get(cid))
            prevNs[cid] = Nn.copy()
            NN[cid][fi] = Nn
            u = np.arange(n + 1) / n
            need = P["CLEAR_F"] * sm((u[:n] - 0.15) / 0.2)
            act = u[:n] > 0.15
            tot = np.zeros((n, 3))
            for it in range(2):
                hh, nn_ = fs.h(ring + tot[:, None, :])
                imin = np.argmin(hh, axis=1)
                hmin = hh[np.arange(n), imin]
                deficit = np.where(act, np.maximum(0.0, need - hmin), 0.0)
                if not (deficit > 1e-4).any():
                    break
                # 寄せの向きは原画のカメラの射線に沿ってカメラの側（原画視点の投影を変えない）。大きさは根元から先へ向けて累積の最大を取り
                # （寄せた駅より先は少なくとも同じだけ寄せる）、駅の間で均す。駅ごとにばらばらに寄せると、射線の向きに走る背骨の駅が重なって管が潰れ、
                # 背骨がぎざぎざに折れた。輪ごとの最も近い頂点の法線の向きは、唇の折れの所でコマの間に向きが跳ぶので使わない
                cen_ = 0.5 * (ring[:, 2] + ring[:, 6]) + tot
                rdir = cen_ - cam.pos
                rdir /= np.maximum(np.linalg.norm(rdir, axis=1, keepdims=True), 1e-12)
                nmin = nn_[np.arange(n), imin]
                rate = (nmin * (-rdir)).sum(1)
                mag = np.minimum(deficit / np.maximum(rate, 0.3), P["PUSH_MAX"])
                mag = gaussian_filter1d(np.maximum.accumulate(mag), 1.5, mode="nearest")
                dvec = -rdir * mag[:, None]
                tot = tot + dvec
                tn = np.linalg.norm(tot, axis=1, keepdims=True)
                tot = tot * np.minimum(1.0, P["PUSH_MAX"] / np.maximum(tn, 1e-12))
                push_stats["rings_pushed"] += int((deficit > 1e-4).sum())
                any_push = True
            PU[cid][fi] = tot
            push_stats["max_push_raw_m"] = max(push_stats["max_push_raw_m"], float(np.linalg.norm(tot, axis=1).max()))
        push_stats["frames_with_push"] += int(any_push)
        if fi % 60 == 0:
            print("pass2a frame", fi, "tau", round(tau, 3), round(time.time() - t0, 1), "s", flush=True)

    # ---- 2 回目（b）：寄せを時間に均す（大きさは前後 PUSH_WIN コマの最大を取ってから σ PUSH_SIG で均す。向きは寄せの和を均したもの）
    from scipy.ndimage import maximum_filter1d
    for cid in live_ids:
        A = PU[cid]
        mag = np.linalg.norm(A, axis=2)
        if not (mag > 1e-6).any():
            continue
        ms = gaussian_filter1d(maximum_filter1d(mag, int(P["PUSH_WIN"]), axis=0, mode="nearest"), P["PUSH_SIG"], axis=0, mode="nearest")
        ms = np.maximum(ms, mag)
        ds = gaussian_filter1d(A, P["PUSH_SIG"], axis=0, mode="nearest")
        dn = np.linalg.norm(ds, axis=2, keepdims=True)
        dirs = np.where(dn > 1e-9, ds / np.maximum(dn, 1e-12), 0.0)
        # 生まれたばかりの小さな指は寄せない（根元が面の上にあるので寄せると浮いて跳ぶ）。g 0〜PUSH_G で 0 → 1
        # PUSH_RAMP > 0 のときは t* の形を動的計画法のままにする（寄せを t* の PUSH_RAMP コマ前から 0 へ）。既定 0：射線に沿う寄せは原画視点の投影を変えないので t* でも寄せる
        fr_ = np.arange(F, dtype=np.float64)
        wt_ = np.ones(F)
        if P["PUSH_RAMP"] > 0:
            wt_ = 1.0 - sm((fr_ - (K_STAR - P["PUSH_RAMP"])) / P["PUSH_RAMP"])
            wt_[fr_ >= K_STAR] = 0.0
        PU[cid] = dirs * (ms * sm(GG[cid] / P["PUSH_G"])[:, None] * wt_[:, None])[..., None]
    push_stats["max_push_m"] = float(max((np.linalg.norm(PU[c], axis=2).max() for c in live_ids), default=0.0))

    if a.debug_ids:
        dbg = {}
        for cid in a.debug_ids.split(","):
            if cid in PU:
                dbg[cid + "_sp"] = SP[cid]
                dbg[cid + "_pu"] = PU[cid]
                dbg[cid + "_g"] = GG[cid]
        os.makedirs(a.out, exist_ok=True)
        np.savez(os.path.join(a.out, "r01_debug.npz"), **dbg)

    # ---- 2 回目（c）：輪・先・根元の円を書き、膜の幅（外の縁をシートより WEB_CLEAR 上に保つ縮め）をコマごとに測る
    NVs = {cid: f["n"] * 8 + 11 for cid, f in fing.items()}
    NW = int(P["WEB_N"]) * 8 + 11
    webs = [cid for cid in (c["id"] for c in claws) if cid in webcap]
    offs, cur = {}, 0
    for c in claws:
        offs[c["id"]] = cur
        cur += NVs[c["id"]]
    woffs = {}
    for cid in webs:
        woffs[cid] = cur
        cur += NW
    Vc = cur
    Vk = sum(k["vert_count"] for k in crowns)
    # pl33r01f_web33（指摘 1・9）：仕上げ33 修正の回 2 の鉤の内の膜（WC…、面に沿う低い浮き彫りの水色の版の膜）も、指が立った後に残る指の根元の陰として戻す。
    # 原画視点の 2 次元の道が一覧の中心線（S2 = 1）なので、膜は仕上げ33 と同じく鉤の内に入る。消した指の膜は戻さない
    webs33 = [] if (a.no_web or not P["WEB33"]) else [c for c in lay["claws"] if c["id"].startswith("W") and c.get("pl33_web_of") in fing
                                                       and not fing[c["pl33_web_of"]]["culled"]]
    w33off = {}
    cur3 = Vc + Vk
    for c in webs33:
        w33off[c["id"]] = cur3
        cur3 += c["vert_count"]
    Vk = cur3 - Vc
    Y = np.zeros((F, Vc + Vk, 3), np.float32)
    for c in webs33:
        Y[:, w33off[c["id"]]:w33off[c["id"]] + c["vert_count"]] = fr_src[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
    SPP = {cid: np.zeros((F, fing[cid]["n"] + 1, 3)) for cid in webs}
    WD = {cid: np.zeros((F, int(P["WEB_N"]) + 1)) for cid in webs}
    WW = {cid: np.zeros((F, fing[cid]["n"] + 1)) for cid in webs}
    FRS = {cid: np.zeros((F, 3, 3)) for cid in webs}
    web_shrunk = 0
    for fi in range(F):
        tau = float(taus[fi])
        Xs = X0 if abs(tau) < 1e-12 else hero.world(tau)
        fs = FrameSheet(Xs) if webs else None
        for c in claws:
            cid = c["id"]
            f = fing[cid]
            bd = band[cid]
            n = f["n"]
            o_ = offs[cid]
            pts = SP[cid][fi].copy()
            g = GG[cid][fi]
            if f["culled"] or g <= 1e-6 or np.linalg.norm(pts[-1] - pts[0]) < 1e-6:
                Y[fi, o_:o_ + NVs[cid]] = pts[0]
                if cid in SPP:
                    SPP[cid][fi] = pts[0]
                continue
            Nn = NN[cid][fi]
            T = np.gradient(pts, axis=0)
            T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
            Bv = np.cross(Nn, T)
            gw = P["G_W0"] + (1 - P["G_W0"]) * sm(g / P["G_W1"])
            w, t = widths(n, f["wr"], gw)
            ring, tip = tube(pts, Nn, Bv, w, t)
            pu = PU[cid][fi]
            ring = ring + pu[:, None, :]
            pts[:n] = pts[:n] + pu
            tip = tip + pu[-1]
            pts[n] = tip
            Y[fi, o_] = pts[0]
            Y[fi, o_ + 1:o_ + 1 + n * 8] = ring.reshape(-1, 3)
            Y[fi, o_ + 1 + n * 8] = tip
            if f["anchor"]["kind"] == "sheet":
                Y[fi, o_ + 2 + n * 8:o_ + NVs[cid]] = bd["circ"][fi]
            else:
                Y[fi, o_ + 2 + n * 8:o_ + NVs[cid]] = pts[0]
            if cid in SPP:
                SPP[cid][fi] = pts
                WW[cid][fi] = w
                wmul = P["WEB_WB"] if rig[cid].get("b_region_q16") else P["WEB_W"]
                kc = float(sm((g - P["G_C0"]) / (1.0 - P["G_C0"])))
                Frf = frame_of(f, fi, Xs)
                FRS[cid][fi] = Frf
                uu, a_, b_, wd, e, Tw, _ = web_geom(pts, w, kc, wmul, webcap[cid], web_ed(cid, g, Frf))
                ha, _ = fs.h(a_)
                hb, _ = fs.h(b_)
                low = hb < P["WEB_CLEAR"]
                if low.any():
                    fr_ = np.clip((ha - P["WEB_CLEAR"]) / np.maximum(ha - hb, 1e-6), 0.0, 1.0)
                    wd = np.where(low, wd * fr_, wd)
                    web_shrunk += int(low.sum())
                WD[cid][fi] = wd
        if fi % 60 == 0:
            print("pass2c frame", fi, "tau", round(tau, 3), round(time.time() - t0, 1), "s", flush=True)

    # ---- 2 回目（d）：膜の幅を時間に均し（前後 WEB_WIN コマの最小を取ってから σ PUSH_SIG）、膜を書く
    from scipy.ndimage import minimum_filter1d
    for cid in webs:
        A = WD[cid]
        Am = gaussian_filter1d(minimum_filter1d(A, int(P["WEB_WIN"]), axis=0, mode="nearest"), P["PUSH_SIG"], axis=0, mode="nearest")
        WD[cid] = np.minimum(Am, webcap[cid][None, :])
    for fi in range(F):
        for cid in webs:
            f = fing[cid]
            wo = woffs[cid]
            pts = SPP[cid][fi]
            g = GG[cid][fi]
            if g <= 1e-6 or np.linalg.norm(pts[-1] - pts[0]) < 1e-6:
                Y[fi, wo:wo + NW] = pts[0]
                continue
            wmul = P["WEB_WB"] if rig[cid].get("b_region_q16") else P["WEB_W"]
            kc = float(sm((g - P["G_C0"]) / (1.0 - P["G_C0"])))
            uu, a_, b_, wd, e, Tw, _ = web_geom(pts, WW[cid][fi], kc, wmul, webcap[cid], web_ed(cid, g, FRS[cid][fi]))
            wd = WD[cid][fi]
            b_ = a_ + wd[:, None] * e
            e2 = np.cross(Tw, e)
            e2n = np.linalg.norm(e2, axis=1, keepdims=True)
            e2 = np.where(e2n > 0.2, e2 / np.maximum(e2n, 1e-12), 0.0)
            cw = 0.5 * (a_ + b_)
            nw = len(uu) - 1
            wring = (cw[:nw, None, :] + e[:nw, None, :] * (0.5 * wd[:nw, None] * np.cos(WEB_ANG)[None, :])[..., None]
                     + e2[:nw, None, :] * (0.5 * P["WEB_TH"] * np.minimum(1.0, wd[:nw] / 0.05)[:, None] * np.sin(WEB_ANG)[None, :])[..., None])
            Y[fi, wo] = a_[0]
            Y[fi, wo + 1:wo + 1 + nw * 8] = wring.reshape(-1, 3)
            Y[fi, wo + 1 + nw * 8] = a_[-1]
            Y[fi, wo + 2 + nw * 8:wo + NW] = a_[0]

    # ---- 冠の爪（SWEEP の sweep_crown の出力）：根元に対する位置を t* の前のコマで時間に均す（pl33r01f_smooth）。
    #      根元の高さ（房の平均）が CROWN_Y_MIN 未満の房は、頂の稜の外に立たず、どの視点からも白い面の上の線に見えるので消す（pl33r01f_crown_low）
    crown_rep = json.load(open(os.path.join(a.crown_src, "pl33_crown.json"), encoding="utf-8")) if os.path.exists(os.path.join(a.crown_src, "pl33_crown.json")) else {"crowns": []}
    tuft_y = {}
    for cr in crown_rep["crowns"]:
        tuft_y.setdefault(cr["tuft"], []).append(cr["y"])
    crown_cull = sorted(cr["id"] for cr in crown_rep["crowns"] if np.mean(tuft_y[cr["tuft"]]) < P["CROWN_Y_MIN"])
    ko = Vc
    kmap = {}
    for k in crowns:
        A = np.asarray(cfr[:, k["vert_offset"]:k["vert_offset"] + k["vert_count"]], np.float64)
        r0 = A[:, :1]
        if k["id"] in crown_cull:
            Y[:, ko:ko + k["vert_count"]] = np.repeat(r0, k["vert_count"], axis=1).astype(np.float32)
        else:
            rel = time_smooth(A - r0, P["T_SIG"], K_STAR, P["T_RAMP"])
            # pl33r01f_crown_bold（指摘 5）：冠の爪の断面を、輪の中心（頂点 2 と 6 の中点）のまわりに CROWN_THICK 倍（先へ向けて CROWN_TIP 倍）に太らせる。
            # 冠の爪は原画のカメラから隠れる（太らせた後も検査する）ので、原画視点は変わらない
            ns = int(k["stations"])
            rg = rel[:, 1:1 + ns * 8].reshape(F, ns, 8, 3)
            cen = 0.5 * (rg[:, :, 2] + rg[:, :, 6])
            sc = P["CROWN_THICK"] + (P["CROWN_TIP"] - P["CROWN_THICK"]) * (np.arange(ns) / max(ns - 1, 1)) ** 1.5
            rg = cen[:, :, None, :] + sc[None, :, None, None] * (rg - cen[:, :, None, :])
            rel[:, 1:1 + ns * 8] = rg.reshape(F, ns * 8, 3)
            Y[:, ko:ko + k["vert_count"]] = (r0 + rel).astype(np.float32)
        kmap[k["id"]] = ko
        ko += k["vert_count"]
    print("crowns culled (low tufts)", crown_cull, flush=True)

    # ---- 三角形
    tris, att, out_claws = [], [], []
    idx = 0
    for c in claws:
        cid = c["id"]
        Tt, kd = layout_tris(fing[cid]["n"], offs[cid])
        tris.append(Tt)
        att.append(np.stack([np.full(len(kd), idx), kd], 1))
        out_claws.append({"id": cid, "index": idx, "vert_offset": offs[cid], "vert_count": NVs[cid], "stations": fing[cid]["n"],
                          "type": rig[cid]["type"], "pl33r01_fix01": True, "culled": bool(fing[cid]["culled"]), "hero": bool(fing[cid]["hero"])})
        idx += 1
    for cid in webs:
        Tt, kd = layout_tris(int(P["WEB_N"]), woffs[cid])
        tris.append(Tt)
        att.append(np.stack([np.full(len(kd), idx), kd], 1))
        out_claws.append({"id": "WF" + cid, "index": idx, "vert_offset": woffs[cid], "vert_count": NW, "stations": int(P["WEB_N"]),
                          "type": "W", "pl33r01_web_of": cid})
        idx += 1
    tri_src = np.fromfile(os.path.join(a.crown_src, clay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)
    att_src = np.fromfile(os.path.join(a.crown_src, clay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)
    for k in crowns:
        m = att_src[:, 0] == k["index"]
        tt = tri_src[m].astype(np.int64) - k["vert_offset"] + kmap[k["id"]]
        tris.append(tt)
        att.append(np.stack([np.full(int(m.sum()), idx), att_src[m, 1].astype(np.int64)], 1))
        out_claws.append({"id": k["id"], "index": idx, "vert_offset": kmap[k["id"]], "vert_count": k["vert_count"], "stations": k["stations"],
                          "type": k["type"], "pl33_crown": True, "pl33f_tuft": k.get("pl33f_tuft")})
        idx += 1
    if webs33:
        tri_33 = np.fromfile(os.path.join(a.src, lay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)
        att_33 = np.fromfile(os.path.join(a.src, lay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)
        for c in webs33:
            m = att_33[:, 0] == c["index"]
            tris.append(tri_33[m].astype(np.int64) - c["vert_offset"] + w33off[c["id"]])
            att.append(np.stack([np.full(int(m.sum()), idx), att_33[m, 1].astype(np.int64)], 1))
            out_claws.append({"id": c["id"], "index": idx, "vert_offset": w33off[c["id"]], "vert_count": c["vert_count"], "stations": c["stations"],
                              "type": "W", "pl33_web_of": c["pl33_web_of"], "pl33r01_from_pl33": True})
            idx += 1
    tris = np.concatenate(tris).astype(np.int32)
    att = np.concatenate(att).astype(np.uint16)
    assert np.isfinite(Y).all()
    os.makedirs(a.out, exist_ok=True)
    fn = dict(frames="ds33_claw_frames_f32.bin", tris="ds33_claw_tris_i32.bin", tri_attr="ds33_claw_tri_attr_u16.bin")
    Y.tofile(os.path.join(a.out, fn["frames"]))
    tris.tofile(os.path.join(a.out, fn["tris"]))
    att.tofile(os.path.join(a.out, fn["tri_attr"]))
    fn["skel"] = "ds33_claw_skel_f32.bin"
    np.zeros((F, idx, 36), np.float32).tofile(os.path.join(a.out, fn["skel"]))
    files = {}
    for k, v in fn.items():
        p = os.path.join(a.out, v)
        lj = lay["files"][k]["layout_ja"] if k in lay["files"] else "float32、コマ × 爪 × 36（この版の指は 0）"
        files[k] = {"file": v, "layout_ja": lj, "sha256": sha(p), "bytes": os.path.getsize(p)}
    Pj = {k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()}
    out = {"schema": "GreatWave.DS33.claw_layout/1", "frames": F, "hz": lay["hz"], "vertices": int(Vc + Vk), "triangles": int(len(tris)),
           "clock_ja": lay["clock_ja"], "timewarp": lay["timewarp"], "claws": out_claws, "files": files,
           "vertex_order_ja": lay["vertex_order_ja"] + "。仕上げ33修正01：指の輪の頂点 q の断面の角度は −82, −50, 90, 230, 262, 266, 270, 274°（q=2 が白の中心）。"
                                                        "膜（W…）は 2 面の薄い帯で、輪の 8 頂点は膜の幅の向きの 0, 45, …, 315°",
           "pl33r01_fix01": {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33r01/r01_build.py", "params": Pj,
                             "src": os.path.relpath(a.src, REPO).replace("\\", "/"), "src_frames_sha256": lay["files"]["frames"]["sha256"],
                             "rig": os.path.relpath(RIG, REPO).replace("\\", "/"), "rig_sha256": sha(RIG), "hero_pkg": os.path.relpath(HERO, REPO).replace("\\", "/"),
                             "warp_sha256": sha(WARP), "fingers": len(claws), "webs": len(webs), "webs33": len(webs33), "crowns_kept": len(crowns) - len(crown_cull), "crowns_culled_low": crown_cull, "culled": culled,
                             "heroes": sorted(heroes), "crown_src": os.path.relpath(a.crown_src, REPO).replace("\\", "/"),
                             "crown_src_frames_sha256": clay["files"]["frames"]["sha256"]}}
    json.dump(out, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if os.path.exists(os.path.join(a.crown_src, "pl33_crown.json")):
        shutil.copyfile(os.path.join(a.crown_src, "pl33_crown.json"), os.path.join(a.out, "pl33_crown.json"))
    rep = {cid: dict(L3=f["L3"], l2d_m=f["l2"], w_root=f["wr"], anchor=f["anchor"], culled=f["culled"], hero=f["hero"],
                     birth_frame=int(band[cid]["birth"]), **{k: v for k, v in f["info"].items() if k != "z"}) for cid, f in fing.items()}
    live = [f for f in fing.values() if not f["culled"]]
    L3s = np.array([f["L3"] for f in live])
    hmx = np.array([f["info"]["h_max"] for f in live])
    dev = np.array([f["info"]["target_dev_m"] for f in live])
    summ = dict(fingers=len(fing), culled=len(culled), webs=len(webs), webs33=len(webs33), heroes=len(heroes), crowns_culled_low=len(crown_cull),
                L3_pct=np.percentile(L3s, [0, 10, 50, 90, 100]).round(3).tolist(),
                hmax_pct=np.percentile(hmx, [0, 10, 50, 90, 100]).round(3).tolist(),
                target_dev_pct=np.percentile(dev, [10, 50, 90]).round(3).tolist(),
                width_steps=st, fallbacks={k: int(sum(1 for f in live if f["info"]["fallback"] == k)) for k in ("short", "relax", "short_relax")},
                pushed_dp=int(sum(f["info"]["pushed"] for f in live)), frame_push=push_stats, web_stations_shrunk=web_shrunk,
                vertices=int(Vc + Vk), triangles=int(len(tris)), elapsed_s=round(time.time() - t0, 1))
    json.dump(dict(summary=summ, params=Pj, fingers=rep), open(os.path.join(a.out, "r01_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("R01_BUILD_DONE", json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
