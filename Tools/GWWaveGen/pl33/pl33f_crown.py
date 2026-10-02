# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：頂の裏の冠の爪を、稜に沿う房（4〜6 本の指の束）に作り直し、形成の途中も原画視点で隠す（numpy）。

自己評審の指摘（作る部の pl33_crown）：
  - 冠の爪は t* でだけ隠れを確かめていた。原画視点で t 9 s に頂の上へ硬い棘の列、t 10.5 s に輪郭の外の爪の画素が出た（輪郭の外 t 9 s 75 → 2,140 px）。
  - 側面・後ろ・回り台で、ドームの面に離れた小さな閉じた輪（米粒・歯）が散った（根元を稜から 4.5 m までの帯に Poisson で置いたため）。
  - 後ろ 65°・回り台 210〜270° で、稜の右半分が爪で縁取られていない。

名前の付いた美術の誘導（どれも帯の頂点の並びだけで決まり、色は PL29 Claw Shade の段。原画カメラからの投影の色は使わない。Q28）：
  - pl33f_crown_ridge（稜）：t* の主役波を、後ろ 65° と回り台（方位 60〜300°、30° おき）のカメラから描いたときの上の縁（空・海との境で、上が主役波でない画素）
    に当たるシートの頂点の集まりを「稜」とする（置き場所を決めるためだけに使う。色は作らない）。冠の爪の根元は、白の範囲・本体の列・高さ 6 m 以上・
    T_white < −0.3 s・t* で原画のカメラから隠れた面（pl33_crown と同じ z バッファと折れの決まり）で、稜から 3D の距離 D_RIDGE（1.4 m）以内の頂点に限る。
  - pl33f_crown_tuft（房）：房の中心を間隔 TUFT_SP（2.6 m）の Poisson 円盤で稜に近い順に置き、房ごとに 4〜6 本の指を、稜の向き（近くの稜の点の主成分）に
    0.55 m おきに並べる。指は原画のカメラから離れる向き（接平面へ射影）へ、面から 55° で立ち上がり先で −45° まで巻く鉤。房の中で巻く向きは同じで、扇に ±10°×k 開く。
    長さは房の長さ L_T（2.0〜3.0 m）× (1 − 0.3|k|/k_max)（真ん中が長い）、幅は長さ × 0.22（0.28〜0.55 m）、先は幅の 0.10 まで細る（尖った指）。厚みは幅の 0.40。
  - pl33f_crown_hidden_t：t* だけでなく、生まれてから t* まで 9 コマ（0.3 s）おきの主役波の z バッファで、そのコマの成長の形の全部の頂点が原画のカメラから
    隠れることを確かめる。見えるコマがあれば生まれる時刻をそのコマの 0.1 s 後へ遅らせて確かめ直す（6 回まで）。伸びる時間が 0.45 s に満たない指は作らない。
  - 成長：生まれる時刻 τ_b（根元の T_white と隠れの遅らせの遅い方）から t* まで、長さ 0.15 → 1、幅 0.45 → 1、巻き 0 → 1（巻きは成長の半ばで終わる：
    立った真っ直ぐな棘の時間を短くする）。τ_b より前は根元の点に潰す。t* の後は保持。

入力（Git 対象外）：--relief（pl33f_relief.py の出力。既定 Unity/Build/Polish/33/fix01/relief）、主役波 Unity/Build/Polish/32/white/hero_pkg、
  時間曲線 Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json、白の範囲 Unity/Build/Polish/32/white/pl31_zone_vertex.npy
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/fix01/claws）。ds33_claw_layout.json と同じ書式（原画の爪 184 ＋ 膜 184 ＋ 冠の爪、id は K001〜）。
使い方（リポジトリの根で。重い numpy の処理と同時に回さない）：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_crown.py
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import ds33_common as U  # noqa: E402
import ds31_white as W31  # noqa: E402
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
from pl33_common import layout_tris, sha  # noqa: E402

B = REPO + "/Unity/Build/Polish"
HERO = B + "/32/white/hero_pkg"
WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
ZONE = B + "/32/white/pl31_zone_vertex.npy"
RELIEF = B + "/33/fix01/relief"
OUT = B + "/33/fix01/claws"
RING = 8
N_ST = 20
PHI = 2 * np.pi * np.arange(RING) / RING
HZ = 30.0
K_STAR = 360
E_DIR = np.array([0.6798348938056157, 0.0, 0.733365200404483])
T_DIR = np.array([0.7333652004044829, 0.0, -0.6798348938056156])

P = dict(D_RIDGE=1.4, D_RIDGE_PAINT=3.0, Y_MIN=11.0, HID_M=0.5, TW_MAX=-0.3, TUFT_SP=2.0, FING_SP=0.55, N_MIN=4, N_MAX=6, LT_MIN=2.3, LT_MAX=3.3,
         W_REL=0.24, W_MIN=0.30, W_MAX=0.60, TH_REL=0.40, TIP_W=0.10, THETA0=55.0, THETA1=-45.0, CURL_POW=1.3, FAN_DEG=14.0,
         TWIST_DEG=15.0, TW_FLOOR=-0.3, SEED=331, FOLD_M=1.0, FOLD_PX=6, HID_STEP=9, MIN_GROW_S=0.45, SEAT_HID_M=0.3, TUFT_MIN=3, TT_AZ=(150, 180, 210, 240, 270, 300), JIT=0.15)


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def centerline(root, u, n, L, th0, th1):
    a = np.linspace(0, 1, N_ST + 1)
    th = np.radians(th0 + (th1 - th0) * a ** P["CURL_POW"])
    d = np.cos(th)[:, None] * u[None, :] + np.sin(th)[:, None] * n[None, :]
    seg = 0.5 * (d[1:] + d[:-1]) * (L / N_ST)
    pts = root[None, :] + np.concatenate([np.zeros((1, 3)), np.cumsum(seg, axis=0)], axis=0)
    return pts, th, d


def band(pts, th, d, u, n, w0, thick_rel):
    T = d / np.linalg.norm(d, axis=1, keepdims=True)
    N = -np.sin(th)[:, None] * u[None, :] + np.cos(th)[:, None] * n[None, :]
    Bv = np.cross(N, T)
    Bv /= np.maximum(np.linalg.norm(Bv, axis=1, keepdims=True), 1e-12)
    Nn = np.cross(T, Bv)
    a = np.linspace(0, 1, N_ST + 1)
    w = w0 * (1 - (1 - P["TIP_W"]) * a ** 1.3)
    t = thick_rel * w
    ring = (pts[:N_ST, None, :] + Bv[:N_ST, None, :] * (0.5 * w[:N_ST, None] * np.cos(PHI)[None, :])[..., None]
            + Nn[:N_ST, None, :] * (0.5 * t[:N_ST, None] * np.sin(PHI)[None, :])[..., None])
    return ring, pts[N_ST], w, t


def growth(s):
    return 0.03 + 0.97 * sm(s / 0.8), 0.25 + 0.75 * sm(s / 0.4), sm(s / 0.5)


class Depth:
    """原画のカメラからの主役波の z バッファと、隠れの判定（pl33_crown と同じ：5×5 の最も手前より HID_M 奥、3×3 の縮めの中、折れの 6 px の内は除く）。"""

    def __init__(self, cam, Xs, R, C, b0, b1):
        Tg = U.K.grid_tris(R, C, b0, b1)
        Vf = Xs.reshape(-1, 3)
        idb, zb = U.raster(cam, Vf[Tg], np.arange(1, len(Tg) + 1))
        self.cam = cam
        self.zb = zb
        self.znear = cv2.dilate(zb.astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.float64)
        zfar = cv2.erode(zb.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.float64)
        zz = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 0.0).astype(np.float32)
        zmax = cv2.dilate(zz, np.ones((5, 5), np.uint8))
        zmin = cv2.erode(np.where(zb > 0, zz, 1e6).astype(np.float32), np.ones((5, 5), np.uint8))
        fold = ((zmax - zmin) > P["FOLD_M"]) | (zb <= 0)
        k = 2 * P["FOLD_PX"] + 1
        fold = cv2.dilate(fold.astype(np.uint8), np.ones((k, k), np.uint8)).astype(bool)
        self.zfar = np.where(fold, 0.0, zfar)

    def hidden(self, Q):
        xy, z = self.cam.project(Q)
        xi = np.round(xy[..., 0]).astype(int); yi = np.round(xy[..., 1]).astype(int)
        inb = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080) & np.isfinite(xy[..., 0])
        xi = np.clip(xi, 0, 1919); yi = np.clip(yi, 0, 1079)
        zs = np.where(self.znear[yi, xi] > 0, 1.0 / np.maximum(self.znear[yi, xi], 1e-9), np.inf)
        return inb & (self.zfar[yi, xi] > 0) & (z > zs + P["HID_M"])


class SeatDepth:
    """pl33f_crown_seat：座席の目（seat_v1 の eye_world）からの主役波の z バッファ（広い画角 110°、主役波の中心へ向ける）。座席と座席から波の方向は同じ目なので、
    隠れはこの 1 つで決まる。座席から主役波の面の上（藍の壁・白い面の前）に見える冠の爪は作らない（作る部の t 10.5 s の「藍の上の白い扇」）。
    画面の外と、主役波の上の縁より上（空を背にした頂の指の縁取り）は許す。"""

    def __init__(self, spec, eye, Xs, o, R, C, b0, b1):
        self.cam = U.look_cam(spec, eye, o + np.array([0.0, 10.0, 0.0]), 110.0, 1920, 1080)
        Tg = U.K.grid_tris(R, C, b0, b1)
        idb, zb = U.raster(self.cam, Xs.reshape(-1, 3)[Tg], np.arange(1, len(Tg) + 1))
        self.zb = zb
        self.znear = cv2.dilate(zb.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.float64)
        m = zb > 0
        top = np.where(m.any(0), np.argmax(m, axis=0), 1080)
        self.top = top

    def hidden(self, Q):
        """座席の目から、主役波の面の上に見えない（面の裏、画面の外、または主役波の上の縁より上＝空を背にした指）なら真。"""
        xy, z = self.cam.project(Q)
        ok = np.isfinite(xy[..., 0]) & (z > 0)
        xi = np.round(np.nan_to_num(xy[..., 0], nan=-1)).astype(int); yi = np.round(np.nan_to_num(xy[..., 1], nan=-1)).astype(int)
        inb = ok & (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080)
        xi = np.clip(xi, 0, 1919); yi = np.clip(yi, 0, 1079)
        zs = np.where(self.znear[yi, xi] > 0, 1.0 / np.maximum(self.znear[yi, xi], 1e-9), np.inf)
        sky = yi < self.top[xi] - 2
        return (~inb) | (z > zs + P["SEAT_HID_M"]) | sky


def view_cams(spec, o):
    cams = {}
    a = np.radians(-65.0)
    pos = o + 90 * (np.cos(a) * E_DIR + np.sin(a) * T_DIR) + np.array([0, 18, 0])
    cams["back65"] = U.look_cam(spec, pos, o + np.array([0, 8, 0]), 26.0, 1920, 1080)
    c0 = o + np.array([0, 9, 0])
    pc = np.array([0.0, 3.0, -62.0]) - c0
    az0 = np.arctan2(pc[2], pc[0])
    el = np.radians(16.0)
    for azd in P["TT_AZ"]:
        az = az0 + np.radians(azd)
        eye = c0 + 72 * np.array([np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)])
        cams["tt%03d" % azd] = U.look_cam(spec, eye, c0, 34.0, 1920, 1080)
    return cams


def claw_geom(Xs, r, c, ul, L, th1, w0, gl=1.0, gw=1.0, gc=1.0):
    Fr = U.frame_at(Xs, float(r), float(c))
    n = Fr[2]
    u = Fr.T @ np.asarray(ul)
    u = u - (u @ n) * n
    u /= max(np.linalg.norm(u), 1e-12)
    root = Xs[r, c]
    th1e = P["THETA0"] + (th1 - P["THETA0"]) * gc
    pts, th, d = centerline(root, u, n, L * gl, P["THETA0"], th1e)
    ring, tip, w, t = band(pts, th, d, u, n, w0 * gw, P["TH_REL"])
    return root, n, u, pts, ring, tip, w, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relief", default=RELIEF)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(P["SEED"])
    hero = U.K.Pkg(HERO)
    wt, wtau = W31.load_warp(WARP)
    lay = json.load(open(os.path.join(a.relief, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V0 = lay["frames"], lay["vertices"]
    tk = np.arange(F) / HZ
    taus = np.where(tk >= 12.0 - 1e-9, 0.0, np.interp(tk, wt, wtau))
    X0 = hero.world(0.0)
    o = hero.origin(0.0)
    R, C = X0.shape[:2]
    tw = np.fromfile(HERO + "/ds27_twhite_r32f.bin", dtype="<f4").reshape(R, C).astype(np.float64)
    zone = np.load(ZONE).reshape(R, C)
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    pcam = U.CamWH(spec, 1920, 1080)
    cam_pos = np.array(spec["painting_cam"]["position"], np.float64)
    b0, b1 = U.BODY
    Tg = U.K.grid_tris(R, C, b0, b1)
    Vf = X0.reshape(-1, 3)
    dep0 = Depth(pcam, X0, R, C, b0, b1)
    hid = dep0.hidden(Vf).reshape(R, C)
    # ---- 稜（後ろ 65° と回り台の上の縁）
    ridge = np.zeros(R * C, bool)
    ridge_by = {}
    for nm, cm in view_cams(spec, o).items():
        idb, zb = U.raster(cm, Vf[Tg], np.arange(1, len(Tg) + 1))
        m = idb > 0
        up = np.zeros_like(m); up[3:] = m[:-3]
        top = m & ~up
        ids = idb[top] - 1
        vi = np.unique(Tg[ids].reshape(-1))
        ridge[vi] = True
        ridge_by[nm] = int(len(vi))
    ridge = ridge.reshape(R, C)
    cols = np.zeros((R, C), bool); cols[:, b0:b1 + 1] = True
    rp = X0[ridge & cols]
    tree_r = cKDTree(rp)
    dr, _ = tree_r.query(Vf)
    dr = dr.reshape(R, C)
    # pl33f_crown_behind_outline：稜のうち原画のカメラから見える所（原画の輪郭そのもの）は隠れた爪を載せられないので、その裏（3.0 m 以内）の隠れた面も候補にする
    xy_, z_ = pcam.project(Vf)
    xi_ = np.clip(np.round(xy_[:, 0]).astype(int), 0, 1919); yi_ = np.clip(np.round(xy_[:, 1]).astype(int), 0, 1079)
    zs_ = np.where(dep0.zb[yi_, xi_] > 0, 1.0 / np.maximum(dep0.zb[yi_, xi_], 1e-9), np.inf)
    vis_p = (z_ <= zs_ + 0.2).reshape(R, C)
    rpv = X0[ridge & cols & vis_p]
    if len(rpv):
        dpv, _ = cKDTree(rpv).query(Vf)
        dpv = dpv.reshape(R, C)
    else:
        dpv = np.full((R, C), np.inf)
    near_r = (dr <= P["D_RIDGE"]) | (dpv <= P["D_RIDGE_PAINT"])
    dr = np.minimum(dr, np.maximum(0.0, dpv - (P["D_RIDGE_PAINT"] - P["D_RIDGE"])))
    cand = zone & hid & cols & (tw < P["TW_MAX"]) & near_r & (X0[..., 1] >= P["Y_MIN"])
    rr, cc = np.nonzero(cand)
    print("ridge vertices", int(ridge.sum()), ridge_by, "candidates", len(rr), round(time.time() - t0, 1), "s", flush=True)
    cand_pts = X0[rr, cc]
    tree_c = cKDTree(cand_pts)
    # ---- 房の中心（稜に近い順、少しの乱数）
    order = np.argsort(dr[rr, cc] + rng.uniform(0, 0.25, len(rr)))
    centers = []
    for k in order:
        p = cand_pts[k]
        if all(np.linalg.norm(p - cand_pts[q]) >= P["TUFT_SP"] for q in centers):
            centers.append(k)
    print("tuft centres", len(centers), flush=True)
    fingers = []
    for ti, k in enumerate(centers):
        r0, c0 = rr[k], cc[k]
        p0 = X0[r0, c0]
        Fr = U.frame_at(X0, float(r0), float(c0))
        n0 = Fr[2]
        near = rp[tree_r.query_ball_point(p0, 2.5)]
        if len(near) >= 3:
            q = near - near.mean(0)
            g = np.linalg.svd(q, full_matrices=False)[2][0]
        else:
            g = Fr[0]
        g = g - (g @ n0) * n0
        g /= max(np.linalg.norm(g), 1e-12)
        away = p0 - cam_pos
        away = away - (away @ n0) * n0
        away /= max(np.linalg.norm(away), 1e-12)
        nf = int(rng.integers(P["N_MIN"], P["N_MAX"] + 1))
        ks = np.arange(nf) - 0.5 * (nf - 1)
        kmax = max(1e-6, np.abs(ks).max())
        LT = rng.uniform(P["LT_MIN"], P["LT_MAX"])
        psi = np.radians(rng.uniform(-P["TWIST_DEG"], P["TWIST_DEG"]))
        for kk in ks:
            tgt = p0 + kk * P["FING_SP"] * (1.0 + rng.uniform(-0.2, 0.2)) * g
            dq, jq = tree_c.query(tgt)
            if dq > 0.4:
                continue
            r, c = int(rr[jq]), int(cc[jq])
            if any(fg["r"] == r and fg["c"] == c for fg in fingers):
                continue
            Frf = U.frame_at(X0, float(r), float(c))
            n = Frf[2]
            ang = psi + np.radians(P["FAN_DEG"] * kk + rng.uniform(-5.0, 5.0))
            u = away - (away @ n) * n
            u /= max(np.linalg.norm(u), 1e-12)
            u = np.cos(ang) * u + np.sin(ang) * np.cross(n, u)
            L = LT * (1.0 - 0.3 * abs(kk) / kmax) * (1.0 + rng.uniform(-P["JIT"], P["JIT"]))
            fingers.append(dict(tuft=ti, k=float(kk), r=r, c=c, u=u, L=L, Fr=Frf))
    print("finger candidates", len(fingers), flush=True)
    # ---- t* の隠れと面の上
    kept = []
    drop = {"hidden_tstar": 0, "clear": 0, "hidden_formation": 0, "short_growth": 0}
    ang8 = 2 * np.pi * np.arange(RING) / RING
    for fg in fingers:
        r, c, u, Frf = fg["r"], fg["c"], fg["u"], fg["Fr"]
        n = Frf[2]
        root = X0[r, c]
        made = None
        for flip in (1.0, -1.0):
            uu = flip * u
            L = fg["L"]
            th1 = P["THETA1"]
            for it in range(5):
                pts, th, d = centerline(root, uu, n, L, P["THETA0"], th1)
                w0 = float(np.clip(P["W_REL"] * L, P["W_MIN"], P["W_MAX"]))
                ring, tip, w, t = band(pts, th, d, uu, n, w0, P["TH_REL"])
                e2 = np.cross(n, uu)
                rc_c = 0.55 * w0
                circ = root[None, :] + rc_c * (np.cos(ang8)[:, None] * uu[None, :] * np.where(np.cos(ang8) < 0, 1.35, 1.0)[:, None] + np.sin(ang8)[:, None] * e2[None, :])
                Qp = np.concatenate([ring.reshape(-1, 3), tip[None, :], circ, 0.5 * (ring + np.roll(ring, -1, axis=1)).reshape(-1, 3)])
                h_ok = dep0.hidden(Qp).all()
                rcs = np.tile([[float(r), float(c)]], (N_ST, 1))
                _, _, hh, _ = U.project_to_sheet(X0, pts[1:N_ST + 1], rcs)
                clear = bool(np.all(hh > 0.25 * t[1:N_ST + 1]))
                if h_ok and clear:
                    made = (L, th1, w0, flip)
                    break
                if not clear:
                    th1 += 20.0
                else:
                    L *= 0.88
                    if L < 0.7 * fg["L"]:
                        break
            if made is not None:
                break
        if made is None:
            drop["hidden_tstar" if clear else "clear"] += 1
            continue
        uu = made[3] * u
        rc_c = 0.55 * made[2]
        e2 = np.cross(n, uu)
        circ = root[None, :] + rc_c * (np.cos(ang8)[:, None] * uu[None, :] * np.where(np.cos(ang8) < 0, 1.35, 1.0)[:, None] + np.sin(ang8)[:, None] * e2[None, :])
        cr, ccq, _, _ = U.project_to_sheet(X0, circ, np.tile([[float(r), float(c)]], (RING, 1)))
        kept.append(dict(tuft=fg["tuft"], k=fg["k"], r=r, c=c, ul=(Frf @ uu).tolist(), L=float(made[0]), th1=float(made[1]), w0=float(made[2]),
                         flip=made[3], tw=float(tw[r, c]), circ_rc=np.stack([cr, ccq], 1).tolist(), d_ridge_m=float(dr[r, c]), y=float(root[1])))
    print("kept after t*", len(kept), drop, round(time.time() - t0, 1), "s", flush=True)
    # ---- 形成の途中の隠れ（9 コマおきの z バッファ）
    tw_min = min(min(k_["tw"], P["TW_FLOOR"]) for k_ in kept) if kept else -1.0
    f_first = int(np.argmax(taus >= tw_min - 1e-9))
    samp = list(range(f_first - (f_first % P["HID_STEP"]), K_STAR, P["HID_STEP"])) + [K_STAR]
    samp = [f for f in samp if f >= 0]
    deps, sheets, seats = {}, {}, {}
    seat_eye = np.array(json.load(open(REPO + "/Tools/GWContext/seat_v1.json", encoding="utf-8"))["seat"]["eye_world"], np.float64)
    for f in samp:
        Xs = X0 if f == K_STAR else hero.world(float(taus[f]))
        sheets[f] = Xs
        deps[f] = dep0 if f == K_STAR else Depth(pcam, Xs, R, C, b0, b1)
        seats[f] = SeatDepth(spec, seat_eye, Xs, hero.origin(float(taus[f])), R, C, b0, b1)
    print("formation depth buffers", len(samp), round(time.time() - t0, 1), "s", flush=True)
    crowns = []
    for kc in kept:
        twr = min(kc["tw"], P["TW_FLOOR"])
        tb = twr
        ok = False
        for it in range(7):
            bad_tau = None
            for f in samp:
                tau = float(taus[f])
                if tau < tb - 1e-9:
                    continue
                s = float(np.clip((tau - tb) / (0.0 - tb), 0.0, 1.0)) if tb < 0 else 1.0
                gl, gw, gc = growth(s)
                root, n, u, pts, ring, tip, w, t = claw_geom(sheets[f], kc["r"], kc["c"], kc["ul"], kc["L"], kc["th1"], kc["w0"], gl, gw, gc)
                Qp = np.concatenate([ring.reshape(-1, 3), tip[None, :]])
                if not (deps[f].hidden(Qp).all() and seats[f].hidden(Qp).all()):
                    bad_tau = tau
            if bad_tau is None:
                ok = True
                break
            tb = bad_tau + 0.1
            if -tb < P["MIN_GROW_S"]:
                break
        if not ok:
            drop["short_growth" if -tb < P["MIN_GROW_S"] else "hidden_formation"] += 1
            continue
        kc["tau_birth"] = tb
        kc["delayed_s"] = round(tb - twr, 3)
        crowns.append(kc)
    # pl33f_crown_tuft_min：生き残った指が TUFT_MIN 本に満たない房は作らない（ドームの面に離れて残る 1〜2 本の指を出さない）
    from collections import Counter
    cnt = Counter(k_["tuft"] for k_ in crowns)
    small = sum(1 for k_ in crowns if cnt[k_["tuft"]] < P["TUFT_MIN"])
    drop["tuft_too_small"] = small
    crowns = [k_ for k_ in crowns if cnt[k_["tuft"]] >= P["TUFT_MIN"]]
    for i, kc in enumerate(crowns):
        kc["id"] = "K%03d" % (i + 1)
    print("crowns", len(crowns), "dropped", drop, "tufts", len(set(k_["tuft"] for k_ in crowns)), round(time.time() - t0, 1), "s", flush=True)
    # ---- コマごとの帯
    NV = RING * N_ST + 11
    nC = len(crowns)
    Yc = np.zeros((F, nC * NV, 3), np.float32)
    skel = np.zeros((F, nC, 36), np.float32)
    tri_all, att_all = [], []
    for i in range(nC):
        Tt, kd = layout_tris(N_ST, V0 + i * NV)
        tri_all.append(Tt)
        att_all.append(np.stack([np.full(len(kd), len(lay["claws"]) + i), kd], 1))
    for f in range(F):
        tau = taus[f]
        Xf = X0 if abs(tau) < 1e-12 else hero.world(float(tau))
        for i, cw in enumerate(crowns):
            r, c = cw["r"], cw["c"]
            o_ = i * NV
            root = Xf[r, c]
            tb = cw["tau_birth"]
            if tau < tb - 1e-9:
                Yc[f, o_:o_ + NV] = root
                continue
            s = float(np.clip((tau - tb) / (0.0 - tb), 0.0, 1.0))
            gL, gw, gc = growth(s)
            root, n, u, pts, ring, tip, w, t = claw_geom(Xf, r, c, cw["ul"], cw["L"], cw["th1"], cw["w0"], gL, gw, gc)
            cr = np.array(cw["circ_rc"])
            cp = U.tri_eval(Xf, cr[:, 0], cr[:, 1]) + 0.004 * U.normal_at(Xf, cr[:, 0], cr[:, 1])
            cp = root[None, :] + gw * (cp - root[None, :])
            Yc[f, o_] = root
            Yc[f, o_ + 1:o_ + 1 + N_ST * RING] = ring.reshape(-1, 3)
            Yc[f, o_ + 1 + N_ST * RING] = tip
            Yc[f, o_ + 2 + N_ST * RING] = root + 0.004 * n
            Yc[f, o_ + 3 + N_ST * RING:o_ + NV] = cp
            js = pts[[0, 5, 10, 15, 20]]
            skel[f, i, :15] = js.reshape(-1)
            skel[f, i, 15:30] = np.tile(n, 5)
            skel[f, i, 30:36] = [s, gL, 0.0, gw, 1.0, float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())]
        if f % 60 == 0:
            print("frame", f, "tau", round(float(tau), 3), round(time.time() - t0, 1), "s", flush=True)
    os.makedirs(a.out, exist_ok=True)
    src = lambda k: os.path.join(a.relief, lay["files"][k]["file"])  # noqa: E731
    Xr = np.fromfile(src("frames"), dtype=np.float32).reshape(F, V0, 3)
    Yall = np.concatenate([Xr, Yc], axis=1)
    del Xr
    Yall.tofile(os.path.join(a.out, lay["files"]["frames"]["file"]))
    tris0 = np.fromfile(src("tris"), dtype=np.int32).reshape(-1, 3)
    att0 = np.fromfile(src("tri_attr"), dtype=np.uint16).reshape(-1, 2)
    tris = np.concatenate([tris0] + [t_.astype(np.int32) for t_ in tri_all]) if nC else tris0
    att = np.concatenate([att0] + [x.astype(np.uint16) for x in att_all]) if nC else att0
    tris.astype(np.int32).tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
    att.astype(np.uint16).tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
    sk0 = np.fromfile(src("skel"), dtype=np.float32).reshape(F, len(lay["claws"]), 36)
    np.concatenate([sk0, skel], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
    for k in ("frames", "tris", "tri_attr", "skel"):
        p = os.path.join(a.out, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = sha(p)
        lay["files"][k]["bytes"] = os.path.getsize(p)
    for i, cw in enumerate(crowns):
        lay["claws"].append({"id": cw["id"], "index": len(lay["claws"]), "vert_offset": V0 + i * NV, "vert_count": NV, "stations": N_ST,
                             "type": "T6", "pl33_crown": True, "pl33f_tuft": int(cw["tuft"])})
    lay["vertices"] = V0 + nC * NV
    lay["triangles"] = int(len(tris))
    Pj = {k: (list(v) if isinstance(v, tuple) else v) for k, v in P.items()}
    lay["pl33_crown"] = {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33/pl33f_crown.py", "params": Pj, "crowns": nC,
                         "tufts": len(set(k_["tuft"] for k_ in crowns)), "dropped": drop,
                         "relief_src": os.path.relpath(a.relief, REPO).replace("\\", "/"), "hero_pkg": os.path.relpath(HERO, REPO).replace("\\", "/"),
                         "zone_sha256": sha(ZONE), "warp_sha256": sha(WARP)}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for cw in crowns:
        cw["u_local"] = cw.pop("ul")
    json.dump({"params": Pj, "crowns": crowns, "ridge_vertices": int(ridge.sum()), "ridge_by_view": ridge_by, "candidates": int(len(rr)),
               "tuft_centres": len(centers), "finger_candidates": len(fingers), "dropped": drop, "formation_check_frames": samp,
               "elapsed_s": round(time.time() - t0, 1)}, open(os.path.join(a.out, "pl33_crown.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F_CROWN_DONE crowns", nC, "vertices", lay["vertices"], "triangles", lay["triangles"], round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
