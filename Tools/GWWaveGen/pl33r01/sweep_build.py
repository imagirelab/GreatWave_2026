# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：低い浮き彫りの爪を、頂・唇・b区域から立つ 3D の白い指（掃引の管）に置き換える（numpy。Unity の描画ではない）。

名前の付いた美術の誘導（どれも爪の並びの頂点だけで決まる。色は PL29 Claw Shade の段（白・水色の版）と設計38 の縁の線。原画カメラからの投影の色は使わない。Q28）：
  - pl33r01s_ray_stand（射線の上で立てる）：爪ごとに、一覧（仕上げ32）の中心線（t* の帯の中心線の原画視点の投影）を根元のまわりに S2 倍した 2 次元の道を、
    原画のカメラ（PaintingCam v1）の射線の上に置き、射線の上の深さを、シートからの高さ（最も近いシートの頂点との符号付きの距離）が大きくなるように動的計画法で選ぶ。
    原画視点の投影は 2 次元の道のまま（原画のカメラは、形を決める射線と、主役波に隠れないことの検査にだけ使う）。指の 3D の長さは L3 = K3 × 2 次元の道の長さ（m）
    （L3_MIN〜L3_MAX）までにし、1 歩の 3D の長さを STEP_MAX × L3 / 段の数 以下にする。高さの上限は H_CAP × L3 × s^0.8（根元から立ち、先で高さを保つ）。
    原画のカメラに向く面の爪は面からカメラの側へ立ち、輪郭の上の爪（空を背にする所）は奥へも立てる。
  - pl33r01s_tube（管）：断面は少し平たい楕円（厚み FLAT × 幅）、幅は根元 W_REL × L3（W_MIN〜W_MAX）から先 TIP_W まで細る。
    輪の 8 頂点の角度を不揃いにし（−82, −50, 90, 230, 262, 266, 270, 274°）、PL29 Claw Shade の段（輪の番号 q の sin(45°q)）で、
    外側（シートの法線と曲がりの外の側）の約 9 割を白（下から見上げても白い指に読めるように）、内側（水に向く側・巻きの内側）を水色の版にする。
  - pl33r01s_grow（育ち）：t* の指を根元の局所の座標系（主役波のシートの frame_at）で持ち、コマ f では、仕上げ33 修正の回 2 の帯の長さの割合 g（根元が白くなってから伸びる時刻、
    画面の外で伸び始めない遅らせを含む）だけ伸ばす。幅 0.35 → 1（g 0〜0.3）、巻き（t* の指と真っ直ぐな指の間）0 → 1（g 0.55〜1）。g = 0 は根元の点に潰す。
  - pl33r01s_branch（支）：一覧の支（C089・C093・C210・C222）は、親の指の σ の所から生える（親の指に付いて動く）。
  - 冠の爪（K…、仕上げ33 の pl33f_crown）はそのまま残す。鉤の内の膜（W…）と b区域の添え指（S…）は、この変種では作らない（指そのものが房と陰を担う）。
入力（Git 対象外）：仕上げ33 修正の回 2 の爪の並び Unity/Build/Polish/33/fix02/claws、仕上げ32 修正の回 1 の rig（sheet_rc・型・支）、
  主役波 Unity/Build/Polish/32/white/hero_pkg、時間曲線 Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33r01/sweep/claws）。ds33_claw_layout.json と同じ書式（GreatWave.DS33.claw_layout/1）。
使い方（リポジトリの根で。重い numpy の処理と同時に回さない）：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_build.py
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
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import ds33_common as U  # noqa: E402
import ds31_white as W31  # noqa: E402
from pl33_common import TStarDepth, layout_tris, sha  # noqa: E402

B = REPO + "/Unity/Build/Polish"
SRC = B + "/33/fix02/claws"
RIG = B + "/32/fix01/claws/ds33_claw_rig.json"
HERO = B + "/32/white/hero_pkg"
WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
OUT = B + "/33r01/sweep/claws"
INV = B + "/32/fix01/list/ds32_claw_inventory.json"
RING = 8
HZ = 30.0
K_STAR = 360
Q_ANG = np.radians([-82.0, -50.0, 90.0, 230.0, 262.0, 266.0, 270.0, 274.0])   # 輪の頂点 q の断面の角度（q=2 が白の中心、q=6 が水色の版の中心）

P = dict(S2=1.6, K3=2.2, L3_MIN=1.2, L3_MAX=4.0, STEP_MAX=1.30, H_CAP=0.75, RISE_S=0.75, CURL_DROP=0.20, KZ=97, MU=0.02, VIS_TOL=0.06, ROOT_TOL=0.25,
         H_MIN=0.03, W_REL=0.16, W_MIN=0.18, W_MAX=0.50, TIP_W=0.08, FLAT=0.70, TAPER=0.8, SMOOTH=1.0, N_UP=0.35, N_CURL=0.6,
         G_W0=0.35, G_W1=0.30, G_C0=0.55, S2_STEPS=(1.5, 1.25, 1.0), W_STEPS=(0.75, 0.55, 0.4), INSIDE_MIN=0.985, ALLOW_DIL=5)


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def arclen(Q):
    d = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    return np.r_[0.0, np.cumsum(d)]


def resample_curve(Q, u):
    """折れ線 Q を弧長の割合 u（0〜1）で取り直す。"""
    s = arclen(Q)
    if s[-1] < 1e-9:
        return np.repeat(Q[:1], len(u), axis=0)
    t = np.clip(u, 0, 1) * s[-1]
    return np.stack([np.interp(t, s, Q[:, k]) for k in range(3)], -1)


class Sheet:
    """t* の主役波（本体の列）の頂点・法線の KD 木。h(P) = 最も近い頂点からの、その頂点の法線（空気の側）の向きの符号付きの距離。"""

    def __init__(self, X0):
        b0, b1 = U.BODY
        R = X0.shape[0]
        rr, cc = np.meshgrid(np.arange(R, dtype=np.float64), np.arange(b0, b1 + 1, dtype=np.float64), indexing="ij")
        Fr = U.frame_at(X0, rr, cc)
        self.V = X0[:, b0:b1 + 1].reshape(-1, 3)
        self.N = Fr[..., 2, :].reshape(-1, 3)
        self.tree = cKDTree(self.V)

    def height(self, Q):
        sh = Q.shape[:-1]
        Qf = Q.reshape(-1, 3)
        d, j = self.tree.query(Qf)
        s = np.sign(((Qf - self.V[j]) * self.N[j]).sum(-1))
        s[s == 0] = 1.0
        return (s * d).reshape(sh)


def ray_points(cam, xy, z):
    """表示の画素 xy（n×2）の射線の上で、カメラの前向きの深さ z（n×K）の点（n×K×3）。"""
    d = cam.ray(xy[:, 0], xy[:, 1])
    t = z / (d @ cam.f)[:, None]
    return cam.pos[None, None, :] + d[:, None, :] * t[..., None]


def stand_spine(cam, dep, sheet, xy, z0, L3, fixed_root=True):
    """pl33r01s_ray_stand：2 次元の道 xy（段 n+1 個、0 が根元）の各段の深さを動的計画法で選ぶ。戻り値は 3D の点（n+1×3）と記録。"""
    n = len(xy) - 1
    K = P["KZ"]
    dz = np.linspace(-L3, L3, K)
    Z = z0 + dz[None, :].repeat(n + 1, 0)
    Q = ray_points(cam, xy, Z)                                    # (n+1)×K×3
    h = sheet.height(Q)
    vis = dep.visible(Q.reshape(-1, 3), P["VIS_TOL"]).reshape(n + 1, K)
    s = np.arange(n + 1) / n
    # 目標の高さ：根元から立ち（RISE_S まで）、先で CURL_DROP だけ面の側へ巻き戻る（奥行きの向きの巻き。原画視点の投影は変えない）
    ht = P["H_CAP"] * L3 * (np.sin(0.5 * np.pi * np.minimum(1.0, s / P["RISE_S"])) - P["CURL_DROP"] * sm((s - P["RISE_S"]) / (1 - P["RISE_S"])))
    score = -np.abs(h - ht[:, None])
    ok = vis & (h >= P["H_MIN"] * np.minimum(1.0, s * 4)[:, None] - 0.02)
    ok[:2] |= dep.visible(Q[:2].reshape(-1, 3), P["ROOT_TOL"]).reshape(2, K) & (h[:2] > -0.10)
    score = np.where(ok, score, -1e6)
    step = P["STEP_MAX"] * L3 / n
    k0 = int(np.argmin(np.abs(dz)))
    acc = np.full(K, -1e9)
    acc[k0] = 0.0
    back = np.zeros((n + 1, K), np.int64)
    for j in range(1, n + 1):
        D = np.linalg.norm(Q[j][:, None, :] - Q[j - 1][None, :, :], axis=-1)   # K（今）× K（前）
        tr = acc[None, :] - P["MU"] * ((dz[:, None] - dz[None, :]) / step) ** 2
        tr = np.where(D <= step, tr, -1e12)
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
    # 均したあと隠れた段はカメラの側へ寄せる
    pushed = 0
    for j in range(1, n + 1):
        for it in range(20):
            if dep.visible(pts[j:j + 1], P["VIS_TOL"])[0] and sheet.height(pts[j:j + 1])[0] >= -0.01:
                break
            zz[j] -= 0.05
            pts[j] = ray_points(cam, xy[j:j + 1], zz[j:j + 1, None])[0, 0]
            pushed += 1
    hh = sheet.height(pts)
    return pts, dict(z=zz.tolist(), h_max=float(hh.max()), h_tip=float(hh[-1]), len3d=float(arclen(pts)[-1]), pushed=pushed,
                     dp_score=float(acc.max()), invalid=bool(acc.max() < -1e5))


def ring_frames(pts, o_ref, up):
    """断面の向き：T（接線）、N（白の向き＝シートの法線と曲がりの外の側と上の混ぜ、T に直交、段ごとに均す）、Bv = N × T。"""
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
    Bv = np.cross(N, T)
    return T, N, Bv


def tube(pts, N, Bv, w, t):
    """輪（段 n × 8）と先：pts は n+1 個（最後が先）。"""
    n = len(pts) - 1
    c, s = np.cos(Q_ANG), np.sin(Q_ANG)
    ring = (pts[:n, None, :] + Bv[:n, None, :] * (0.5 * w[:n, None] * c[None, :])[..., None]
            + N[:n, None, :] * (0.5 * t[:n, None] * s[None, :])[..., None])
    return ring, pts[n]


def widths(n, wr, gw=1.0):
    a = np.arange(n + 1) / n
    w = wr * gw * (1 - (1 - P["TIP_W"]) * a ** P["TAPER"])
    return w, P["FLAT"] * w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--s2", type=float, default=P["S2"])
    ap.add_argument("--k3", type=float, default=P["K3"])
    ap.add_argument("--w-rel", type=float, default=P["W_REL"])
    ap.add_argument("--w-max", type=float, default=P["W_MAX"])
    ap.add_argument("--l3-min", type=float, default=P["L3_MIN"])
    ap.add_argument("--l3-max", type=float, default=P["L3_MAX"])
    ap.add_argument("--w-min", type=float, default=P["W_MIN"])
    ap.add_argument("--curl-drop", type=float, default=P["CURL_DROP"])
    ap.add_argument("--rise-s", type=float, default=P["RISE_S"])
    ap.add_argument("--taper", type=float, default=P["TAPER"])
    ap.add_argument("--crown-src", default=None, help="冠の爪（K…）を写す並び（既定は --src。sweep_crown.py の出力を渡すと作り直した冠の爪を使う）")
    ap.add_argument("--inside-min", type=float, default=P["INSIDE_MIN"])
    ap.add_argument("--allow-dil", type=int, default=P["ALLOW_DIL"])
    ap.add_argument("--no-crown", action="store_true")
    a = ap.parse_args()
    P["S2"], P["K3"], P["W_REL"], P["W_MAX"] = a.s2, a.k3, a.w_rel, a.w_max
    P["S2_STEPS"] = tuple(sorted(set([a.s2] + [x for x in (1.25, 1.0) if x < a.s2]), reverse=True))
    P["L3_MIN"], P["L3_MAX"], P["W_MIN"] = a.l3_min, a.l3_max, a.w_min
    P["CURL_DROP"], P["RISE_S"], P["TAPER"] = a.curl_drop, a.rise_s, a.taper
    P["INSIDE_MIN"], P["ALLOW_DIL"] = a.inside_min, a.allow_dil
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V0 = lay["frames"], lay["vertices"]
    fr_src = np.memmap(os.path.join(a.src, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V0, 3))
    rig = {c["id"]: c for c in json.load(open(RIG, encoding="utf-8"))["claws"]}
    hero = U.K.Pkg(HERO)
    wt, wtau = W31.load_warp(WARP)
    tk = np.arange(F) / HZ
    taus = np.where(tk >= 12.0 - 1e-9, 0.0, np.interp(tk, wt, wtau))
    X0 = hero.world(0.0)
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    cam = U.CamWH(spec, 1920, 1080)
    dep = TStarDepth(X0)
    sheet = Sheet(X0)
    up = np.array([0.0, 1.0, 0.0])
    claws = [c for c in lay["claws"] if c["id"].startswith("C")]
    csrc = a.crown_src or a.src
    clay = lay if csrc == a.src else json.load(open(os.path.join(csrc, "ds33_claw_layout.json"), encoding="utf-8"))
    crowns = [c for c in clay["claws"] if c["id"].startswith("K")] if not a.no_crown else []
    cfr = fr_src if csrc == a.src else np.memmap(os.path.join(csrc, clay["files"]["frames"]["file"]), dtype=np.float32, mode="r",
                                                  shape=(clay["frames"], clay["vertices"], 3))
    print("claws", len(claws), "crowns", len(crowns), round(time.time() - t0, 1), "s", flush=True)

    # ---- 帯（仕上げ33 修正の回 2）の中心線と、コマごとの長さの割合
    band = {}
    for c in claws:
        o, nv = c["vert_offset"], c["vert_count"]
        n = (nv - 11) // 8
        blk = np.asarray(fr_src[:, o:o + nv, :], np.float64)          # F × nv × 3
        cen = np.concatenate([blk[:, 1:1 + n * 8].reshape(F, n, 8, 3).mean(2), blk[:, 1 + n * 8][:, None]], axis=1)  # F × (n+1) × 3
        L = np.linalg.norm(np.diff(cen, axis=1), axis=2).sum(1)
        g = np.clip(L / max(L[K_STAR], 1e-9), 0.0, 1.0)
        g[L < 1e-6] = 0.0
        band[c["id"]] = dict(n=n, cen=cen, g=g, root=blk[:, 0], circ=blk[:, 2 + n * 8:], o=o, nv=nv)
    print("bands read", round(time.time() - t0, 1), "s", flush=True)

    # ---- pl33r01s_footprint：原画視点の t* の指の投影（輪の頂点と先）が入ってよい所＝主役波（本体の列）の z バッファの所（1 px 広げる）と、
    #      一覧（仕上げ32）の全部の爪の領域（2 px 広げる）。ここを出る指は S2 を下げ、それでも出れば幅を細くする（原画視点の主役波の輪郭 132・72 を守る）
    inv = json.load(open(INV, encoding="utf-8"))
    allow = np.zeros((1080, 1920), np.uint8)
    for ci in inv["claws"]:
        poly = ci.get("region_polygon_ref") or ci.get("polygon_ref_af29")
        if poly:
            cv2.fillPoly(allow, [np.round(U.to_disp(np.array(poly, np.float64))).astype(np.int32)], 1)
    allow = cv2.dilate(allow, np.ones((P["ALLOW_DIL"], P["ALLOW_DIL"]), np.uint8)) | cv2.dilate(dep.mask.astype(np.uint8), np.ones((3, 3), np.uint8))
    allow = allow.astype(bool)

    def inside_frac(pts, N, wr, ws):
        n_ = len(pts) - 1
        T_ = np.gradient(pts, axis=0)
        T_ /= np.maximum(np.linalg.norm(T_, axis=1, keepdims=True), 1e-12)
        Bv_ = np.cross(N, T_)
        w_, t_ = widths(n_, wr * ws)
        ring_, tip_ = tube(pts, N, Bv_, w_, t_)
        Q = np.concatenate([ring_.reshape(-1, 3), tip_[None, :]])
        q, _ = cam.project(Q)
        xi = np.round(q[:, 0]).astype(int)
        yi = np.round(q[:, 1]).astype(int)
        ok = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080)
        ins = np.zeros(len(Q), bool)
        ins[ok] = allow[yi[ok], xi[ok]]
        return float(ins.mean())

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
        best = None
        cands = [(s2, 1.0) for s2 in P["S2_STEPS"]] + [(P["S2_STEPS"][-1], ws) for ws in P["W_STEPS"]]
        for s2, ws in cands:
            if par and par in fing:
                pf = fing[par]
                sig = float(rg["attach_sigma"])
                # 親の 2 次元の道の σ の所へ根元を移し、そこを中心に s2 倍
                pxy = pf["xy2"]
                sp = arclen(np.c_[pxy, np.zeros(len(pxy))])
                rxy = np.array([np.interp(sig * sp[-1], sp, pxy[:, 0]), np.interp(sig * sp[-1], sp, pxy[:, 1])])
                xy2 = rxy[None, :] + s2 * (xy - xy[0])
                p3 = resample_curve(pf["pts"], np.array([sig]))[0]
                _, z0 = cam.project(p3[None, :])
                z0 = float(z0[0])
                anchor = dict(kind="parent", parent=par, sigma=sig)
            else:
                xy2 = xy[0][None, :] + s2 * (xy - xy[0])
                z0 = float(zc[0])
                anchor = dict(kind="sheet", rc=[float(v) for v in rg["sheet_rc"]])
            # 一覧の大きさの道の長さ（根元の深さの m）
            px_m = z0 * 2.0 * cam.t / 1080.0
            l2 = float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum() * px_m)
            L3 = float(np.clip(P["K3"] * l2, P["L3_MIN"], P["L3_MAX"]))
            if par:
                L3 = float(np.clip(P["K3"] * l2, 0.6 * P["L3_MIN"], 0.6 * fing[par]["L3"] if par in fing else P["L3_MAX"]))
            pts, info = stand_spine(cam, dep, sheet, xy2, z0, L3)
            info["fallback"] = None
            if info["invalid"]:
                # pl33r01s_fallback：この道で立てられない指（主役波に隠れる・画面の外）は、長さを 0.6 倍にして立て直し、それも無理なら仕上げ33 の帯の中心線のまま
                pts1, info1 = stand_spine(cam, dep, sheet, xy2, z0, max(0.6 * L3, P["L3_MIN"] * 0.6))
                if not info1["invalid"]:
                    pts, info, L3 = pts1, info1, max(0.6 * L3, P["L3_MIN"] * 0.6)
                    info["fallback"] = "short"
                else:
                    pts = cen.copy()
                    xy2 = xy.copy()
                    info = dict(info1, fallback="band", h_max=float(sheet.height(pts).max()), len3d=float(arclen(pts)[-1]), pushed=0)
                    L3 = float(arclen(pts)[-1])
            if anchor["kind"] == "sheet":
                pts[0] = bd["root"][K_STAR]
            else:
                pts[0] = resample_curve(fing[par]["pts"], np.array([anchor["sigma"]]))[0]
            # pl33r01s_uniform（修正の回 1）：背骨を弧長で等間隔に取り直す（同じ 3D の折れ線の上の点なので、原画視点の投影の道は変わらない）。
            # 各コマの指はこの背骨の弧長の割合で作るので、t* とその前後のコマで段の点が背骨に沿って滑らない（跳び・瞬間移動をなくす）
            p0 = pts[0].copy()
            pts = resample_curve(pts, np.linspace(0.0, 1.0, len(pts)))
            pts[0] = p0
            r_, c_ = (anchor["rc"] if anchor["kind"] == "sheet" else rig[par]["sheet_rc"])
            Fr = U.frame_at(X0, float(r_), float(c_))
            o_ref = Fr[2]
            T, N, Bv = ring_frames(pts, o_ref, up)
            wr = float(np.clip(P["W_REL"] * L3, P["W_MIN"], P["W_MAX"]))
            if par:
                wr = min(wr, 0.7 * fing[par]["wr"])
            fr_in = inside_frac(pts, N, wr, ws)
            info.update(s2=s2, w_scale=ws, inside_frac=round(fr_in, 4))
            best = dict(pts=pts, xy2=xy2, L3=L3, l2=l2, wr=wr * ws, anchor=anchor, Fr=Fr, N=N, info=info, n=n, root_rc=(float(r_), float(c_)))
            if fr_in >= P["INSIDE_MIN"]:
                break
        fing[cid] = best
    st = {}
    for f in fing.values():
        k = "%.2f_%.2f" % (f["info"]["s2"], f["info"]["w_scale"])
        st[k] = st.get(k, 0) + 1
    print("footprint steps", st, "inside<min", sum(1 for f in fing.values() if f["info"]["inside_frac"] < P["INSIDE_MIN"]), flush=True)
    print("t* fingers", len(fing), round(time.time() - t0, 1), "s", flush=True)

    # ---- コマごと
    NVs = {cid: f["n"] * 8 + 11 for cid, f in fing.items()}
    offs, cur = {}, 0
    for c in claws:
        offs[c["id"]] = cur
        cur += NVs[c["id"]]
    Vc = cur
    Vk = sum(k["vert_count"] for k in crowns)
    Y = np.zeros((F, Vc + Vk, 3), np.float32)
    loc = {}
    for cid, f in fing.items():
        Fr = f["Fr"]
        base = f["pts"][0]
        loc[cid] = dict(P=(f["pts"] - base) @ Fr.T, N=f["N"] @ Fr.T)
    prevNs = {}
    for fi in range(F):
        tau = float(taus[fi])
        Xf = X0 if abs(tau) < 1e-12 else hero.world(tau)
        now = {}
        for c in order:
            cid = c["id"]
            f = fing[cid]
            bd = band[cid]
            n = f["n"]
            o_ = offs[cid]
            g = float(bd["g"][fi])
            if f["anchor"]["kind"] == "sheet":
                Fr = f["Fr"] if fi == K_STAR else U.frame_at(Xf, *f["root_rc"])
                root = bd["root"][fi]
            else:
                par = f["anchor"]["parent"]
                Fr = now[par]["Fr"]
                pp = now[par]
                Lp = arclen(pp["pts"])[-1]
                sig = f["anchor"]["sigma"]
                gp = pp["g"]
                # pl33r01s_branch_grow（修正の回 1）：支は親の指が σ を越えてから、親の伸びに比例して伸びる（現れる時の跳びをなくす）
                g = min(g, float(np.clip((gp - sig) / max(1.0 - sig, 1e-6), 0.0, 1.0)))
                if Lp < 1e-6 or gp <= sig:
                    root = pp["pts"][-1] if Lp > 0 else bd["root"][fi]
                else:
                    root = resample_curve(pp["pts"], np.array([sig / gp]))[0]
            lp = loc[cid]
            if g <= 1e-6:
                Y[fi, o_:o_ + NVs[cid]] = root
                now[cid] = dict(Fr=Fr, pts=np.repeat(root[None, :], n + 1, 0), g=0.0)
                continue
            u = np.arange(n + 1) / n
            curved = resample_curve(lp["P"], u * g)
            d0 = resample_curve(lp["P"], np.array([min(1.0, 0.35 * g + 1e-3)]))[0]
            d0 = d0 / max(np.linalg.norm(d0), 1e-12)
            Lg = arclen(lp["P"])[-1] * g
            straight = u[:, None] * Lg * d0[None, :]
            kc = sm((g - P["G_C0"]) / (1.0 - P["G_C0"]))
            Pl = (1 - kc) * straight + kc * curved
            pts = root[None, :] + Pl @ Fr
            Nl = resample_curve(lp["N"], u * g) @ Fr
            T = np.gradient(pts, axis=0)
            T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
            # pl33r01s_section_cont（修正の回 1）：断面の白の向き N を、接線に直交させたあと、段の間（前の段と逆なら前の段から運ぶ）と
            # コマの間（前のコマの同じ段と逆なら裏返す）で続ける（輪の間のねじれ・コマの間の裏返りをなくす）
            Nn = Nl - (Nl * T).sum(1, keepdims=True) * T
            nrm = np.linalg.norm(Nn, axis=1)
            prevN = prevNs.get(cid)
            for j in range(n + 1):
                if nrm[j] < 0.25:
                    ref = Nn[j - 1] if j > 0 else (prevN[0] if prevN is not None else np.cross(T[j], [0.0, 1.0, 0.0]))
                    Nn[j] = ref - (ref @ T[j]) * T[j]
                Nn[j] /= max(np.linalg.norm(Nn[j]), 1e-12)
            if prevN is not None and (Nn * prevN).sum() < 0:
                Nn = -Nn
            for j in range(1, n + 1):
                if Nn[j] @ Nn[j - 1] < 0.5:
                    ref = Nn[j - 1] - (Nn[j - 1] @ T[j]) * T[j]
                    ref /= max(np.linalg.norm(ref), 1e-12)
                    Nn[j] = ref if Nn[j] @ Nn[j - 1] < 0 else 0.5 * (Nn[j] + ref)
                    Nn[j] = Nn[j] - (Nn[j] @ T[j]) * T[j]
                    Nn[j] /= max(np.linalg.norm(Nn[j]), 1e-12)
            prevNs[cid] = Nn.copy()
            Bv = np.cross(Nn, T)
            gw = P["G_W0"] + (1 - P["G_W0"]) * sm(g / P["G_W1"])
            w, t = widths(n, f["wr"], gw)
            ring, tip = tube(pts, Nn, Bv, w, t)
            Y[fi, o_] = pts[0]
            Y[fi, o_ + 1:o_ + 1 + n * 8] = ring.reshape(-1, 3)
            Y[fi, o_ + 1 + n * 8] = tip
            if f["anchor"]["kind"] == "sheet":
                Y[fi, o_ + 2 + n * 8:o_ + NVs[cid]] = bd["circ"][fi]
            else:
                Y[fi, o_ + 2 + n * 8:o_ + NVs[cid]] = pts[0]
            now[cid] = dict(Fr=Fr, pts=pts, g=g)
        if fi % 60 == 0:
            print("frame", fi, "tau", round(tau, 3), round(time.time() - t0, 1), "s", flush=True)
    # ---- 冠の爪（そのまま）
    ko = Vc
    kmap = {}
    for k in crowns:
        Y[:, ko:ko + k["vert_count"]] = cfr[:, k["vert_offset"]:k["vert_offset"] + k["vert_count"]]
        kmap[k["id"]] = ko
        ko += k["vert_count"]
    # ---- 三角形
    tris, att, out_claws = [], [], []
    idx = 0
    for c in claws:
        cid = c["id"]
        Tt, kd = layout_tris(fing[cid]["n"], offs[cid])
        tris.append(Tt)
        att.append(np.stack([np.full(len(kd), idx), kd], 1))
        out_claws.append({"id": cid, "index": idx, "vert_offset": offs[cid], "vert_count": NVs[cid], "stations": fing[cid]["n"],
                          "type": rig[cid]["type"], "pl33r01_sweep": True})
        idx += 1
    tri_src = np.fromfile(os.path.join(csrc, clay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)
    att_src = np.fromfile(os.path.join(csrc, clay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)
    for k in crowns:
        m = att_src[:, 0] == k["index"]
        tt = tri_src[m].astype(np.int64) - k["vert_offset"] + kmap[k["id"]]
        tris.append(tt)
        att.append(np.stack([np.full(int(m.sum()), idx), att_src[m, 1].astype(np.int64)], 1))
        out_claws.append({"id": k["id"], "index": idx, "vert_offset": kmap[k["id"]], "vert_count": k["vert_count"], "stations": k["stations"],
                          "type": k["type"], "pl33_crown": True, "pl33f_tuft": k.get("pl33f_tuft")})
        idx += 1
    tris = np.concatenate(tris).astype(np.int32)
    att = np.concatenate(att).astype(np.uint16)
    assert np.isfinite(Y).all()
    os.makedirs(a.out, exist_ok=True)
    fn = dict(frames="ds33_claw_frames_f32.bin", tris="ds33_claw_tris_i32.bin", tri_attr="ds33_claw_tri_attr_u16.bin")
    Y.tofile(os.path.join(a.out, fn["frames"]))
    tris.tofile(os.path.join(a.out, fn["tris"]))
    att.tofile(os.path.join(a.out, fn["tri_attr"]))
    # 骨格の表（設計33 の書式。この変種の指は 0 で埋める。冠の爪の道具 pl33f_crown が読むので置く）
    fn["skel"] = "ds33_claw_skel_f32.bin"
    np.zeros((F, idx, 36), np.float32).tofile(os.path.join(a.out, fn["skel"]))
    files = {}
    for k, v in fn.items():
        p = os.path.join(a.out, v)
        lj = lay["files"][k]["layout_ja"] if k in lay["files"] else "float32、コマ × 爪 × 36（この変種の指は 0）"
        files[k] = {"file": v, "layout_ja": lj, "sha256": sha(p), "bytes": os.path.getsize(p)}
    out = {"schema": "GreatWave.DS33.claw_layout/1", "frames": F, "hz": lay["hz"], "vertices": int(Vc + Vk), "triangles": int(len(tris)),
           "clock_ja": lay["clock_ja"], "timewarp": lay["timewarp"], "claws": out_claws, "files": files,
           "vertex_order_ja": lay["vertex_order_ja"] + "。仕上げ33修正01 SWEEP：輪の頂点 q の断面の角度は −82, −50, 90, 230, 262, 266, 270, 274°（q=2 が白の中心）",
           "pl33r01_sweep": {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33r01/sweep_build.py", "params": P,
                             "src": os.path.relpath(a.src, REPO).replace("\\", "/"), "src_frames_sha256": lay["files"]["frames"]["sha256"],
                             "rig": os.path.relpath(RIG, REPO).replace("\\", "/"), "rig_sha256": sha(RIG), "hero_pkg": os.path.relpath(HERO, REPO).replace("\\", "/"),
                             "warp_sha256": sha(WARP), "fingers": len(claws), "crowns_kept": len(crowns),
                             "crown_src": os.path.relpath(csrc, REPO).replace("\\", "/"), "crown_src_frames_sha256": clay["files"]["frames"]["sha256"], "webs_dropped": 184, "tufts_dropped": 114}}
    json.dump(out, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if crowns and os.path.exists(os.path.join(csrc, "pl33_crown.json")):
        # 冠の爪の記録（根元のシートの (行, 列)・生まれる時刻）を、検査の道具（pl33f_measure.py）が読む置き場所へ写す
        shutil.copyfile(os.path.join(csrc, "pl33_crown.json"), os.path.join(a.out, "pl33_crown.json"))
    rep = {cid: dict(L3=f["L3"], l2d_m=f["l2"], w_root=f["wr"], anchor=f["anchor"], **{k: v for k, v in f["info"].items() if k != "z"}) for cid, f in fing.items()}
    L3s = np.array([f["L3"] for f in fing.values()])
    hmx = np.array([f["info"]["h_max"] for f in fing.values()])
    summ = dict(fingers=len(fing), L3_pct=np.percentile(L3s, [0, 10, 50, 90, 100]).round(3).tolist(),
                hmax_pct=np.percentile(hmx, [0, 10, 50, 90, 100]).round(3).tolist(),
                invalid=int(sum(f["info"]["invalid"] for f in fing.values())), pushed=int(sum(f["info"]["pushed"] for f in fing.values())),
                vertices=int(Vc + Vk), triangles=int(len(tris)), elapsed_s=round(time.time() - t0, 1), params=P)
    json.dump(dict(summary=summ, fingers=rep), open(os.path.join(a.out, "sweep_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SWEEP_BUILD_DONE", json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
