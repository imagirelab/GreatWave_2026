# -*- coding: utf-8 -*-
"""美術の見本01（Q29）爪の部：t* の主役波に、2 つの区域の爪を作る（numpy。Unity の描画ではない。静止、t* だけ）。

利用者の選択（2026-10-02 の対話。Production_Workflow_ja.md の Q29）：
  区域 1（頂と唇）：彫刻のような立体の白い指（太く、丸く、外へ扇に開き、先が巻く）。原画のカメラから見て、その輪郭が原画の爪の輪に並ぶように置く。
  区域 2（波の面の内側）：原画のような白い爪の鉤（内の巻きは水色、縁は藍の線）を、面の上の厚い板として作る。

名前の付いた美術の誘導（as01_*。どれも爪の頂点だけで決まり、色は PL29 Claw Shade の段（白・水色の版）と設計38 の縁の線。原画カメラからの投影の色は使わない。
原画のカメラは、区域 2 の根元（射線の当たり）と向き（原画の爪の 2 次元の向き）、区域 1・2 の振り分け（原画の爪の一覧の根元の列）、
冠が隠れることと区域 1 の爪が原画の空へ深く出ないことの検査にだけ使う。Q28）。v11（2026-10-03）から：
  - 区域 1（頂と唇）は claws_rim.py の列（as01_claw_rows：L0 唇の櫛・L1・R1 爪の輪・R2・R3。爪は as01_claw_hand＝掌＋扇の指 3、
    唇の櫛は 1 本の指、爪の下の水色の膜 as01_claw_shadow、原画の空の検査 as01_paint_silhouette）。--fams で列を選ぶ（見本 B は L0,L1,R1）。
    原画の爪の一覧のうち、根元が c_tip − 90 〜 c_tip + 8（行 127 から先は + 25）の帯の爪は、この列が受け持つ（1 本ずつは写さない）。
  - as01_crown（区域 1、原画のカメラから隠れる所）：頂の稜の背の側に、稜から立って前へ巻く指を等間隔に置く（彫刻の頂の指の冠）。
    隠れの検査は管の太さを入れる（v11）。太さ CROWN_R 0.62、長さ CROWN_L 3.4。
  - as01_claw_sheet（区域 2、make_claw_sheet）：帯の外の原画の爪ごとに、面に寝る厚い板の「爪」（体 1 ＋ 面の中で巻く指 3 ＋ 真ん中の指の内の水色の膜）。
    形は面の上で決める（投影しない）。長さは原画の爪の面の上の長さ × CS_K（CS_MIN 以上）。
  - make_hand（v10 の as01_hand）・make_hook（v10 の 1 本の鉤）は使っていない（v10 の記録のために残す。原画の射線を使う手は座席で箒になり、
    1 本の鉤は小さな J の字が散らばって見えた）。P の HOOK_K・HOOK_W・TAL_*・FAN などはその名残り（HOOK_T・HOOK_LIFT・WEB_* は区域 2 が使う）。
入力（Git 対象外）：主役波 Unity/Build/Polish/32/white/hero_pkg（t* の形）、仕上げ32 の一覧 Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json。
出力（Git 対象外）：--out（既定 Unity/Build/Polish/sample01/claws/mesh）に ds33_claw_layout.json の書式（GreatWave.DS33.claw_layout/1、コマ 1 つ＝t*）と
  OBJ（as01_claws.obj。区域ごとのグループ）、記録 as01_claws_report.json。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as01/claws_build.py [--out …] [--fams L0,L1,R1] [--zones rim,crown,hook]
"""
import argparse
import json
import math
import os
import sys
import time
import zlib

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402
import claws_rim as CR  # noqa: E402

U = CC.U
P = dict(RHO_RIM=0.60, CL_PX=40.0, CL_ANG=65.0, CL_MAX=4, L_K=1.7, L_MIN=1.1, L_MAX=2.6, R_K=0.20, R_MIN=0.20, R_MAX=0.45,
         KAPPA=(0.35, 0.7, 1.05, 1.4), CLEAR=0.6, ST_BODY=9, ST_TAL=10, S_BRANCH=0.55, FAN=28.0, TH_BODY=35.0, TH_TAL=170.0, CURL_IN=0.30,
         TAL_L=0.62, TAL_R=0.62, CAP=0.80, CROWN_DR=4, CROWN_L=3.4, CROWN_R=0.62, CROWN_KAPPA=1.0, CROWN_TH=170.0,
         HOOK_K=1.2, HOOK_MIN=0.55, HOOK_W=0.36, HOOK_WMIN=0.18, HOOK_T=0.18, HOOK_STRAIGHT=0.42, HOOK_TH=200.0, ST_HOOK=14, HOOK_LIFT=0.03,
         WEB_W=0.55, WEB_T=0.03,
         CS_K=1.8, CS_MIN=1.3, CS_W=0.32, CS_BODY=0.40, CS_BODY_TH=15.0, CS_FING=0.90, CS_FW=0.42, CS_OFF=0.30, CS_SPREAD=24.0, CS_TH=170.0)


def rot(v, axis, ang):
    axis = axis / np.linalg.norm(axis)
    return v * math.cos(ang) + np.cross(axis, v) * math.sin(ang) + axis * (axis @ v) * (1 - math.cos(ang))


def unit(v):
    return v / max(np.linalg.norm(v), 1e-12)


def jit(cid, k, a=1.0):
    """id の決まった乱数（−a〜a）。"""
    return a * (2.0 * ((zlib.crc32((cid + ":" + str(k)).encode()) % 10007) / 10006.0) - 1.0)


class PaintHit:
    """原画視点の z バッファ（主役波の本体）から、画素の射線とシートの当たり (r, c)・点を返す。"""

    def __init__(self, hero, cam):
        self.h, self.cam = hero, cam
        self.idb, self.zb = U.raster(cam, hero.V[hero.Tg], np.arange(1, len(hero.Tg) + 1))

    def hit(self, px):
        x, y = int(round(px[0])), int(round(px[1]))
        if not (0 <= x < 1920 and 0 <= y < 1080):
            return None
        t = int(self.idb[y, x]) - 1
        if t < 0:
            return None
        tv = self.h.V[self.h.Tg[t]]
        d = self.cam.ray(np.array([px[0]]), np.array([px[1]]))[0]
        s, u, v = U.ray_tri_many(self.cam.pos, d[None, :], tv[0][None], tv[1][None], tv[2][None])
        r, c = U.tri_to_rc(np.array([t]), u, v, self.h.b1 - self.h.b0, self.h.b0)
        return dict(P=self.cam.pos + s[0] * d, r=float(r[0]), c=float(c[0]))

    def depth_at(self, px):
        x, y = int(round(px[0])), int(round(px[1]))
        if not (0 <= x < 1920 and 0 <= y < 1080) or self.zb[y, x] <= 0:
            return np.inf
        return 1.0 / self.zb[y, x]


def img_dir3(cam, d2):
    """画面の向き d2（x 右・y 下）を、原画の射線に直交する面の 3D の向きへ。"""
    return unit(cam.r * d2[0] - cam.u * d2[1])


def tangent_lift(cam, Fr, d2):
    """画面の向き d2 に投影が重なる、接平面（Fr の e1, e2）の向き。"""
    e1, e2 = Fr[0], Fr[1]
    k1 = (e1 @ cam.r) * d2[1] + (e1 @ cam.u) * d2[0]
    k2 = (e2 @ cam.r) * d2[1] + (e2 @ cam.u) * d2[0]
    t = unit(-k2 * e1 + k1 * e2)
    if (t @ cam.r) * d2[0] - (t @ cam.u) * d2[1] < 0:
        t = -t
    return t


def curl_sign(q):
    """2 次元の中心線の巻きの向き（画面、y 下で時計回り ＝ +1）。"""
    a = unit(q[min(3, len(q) - 1)] - q[0])
    b = unit(q[-1] - q[max(len(q) - 4, 0)])
    s = a[0] * b[1] - a[1] * b[0]
    return 1.0 if s >= 0 else -1.0


def spine_curl(P0, D0, C0, L, th1, n, p=1.6, th0=0.0):
    """P(s) = P0 + L ∫ (cos θ D0 + sin θ C0)、θ = th0 + th1 s^p（度）。n+1 点。"""
    ss = np.linspace(0, 1, 8 * n + 1)
    th = np.radians(th0 + th1 * ss ** p)
    t = np.cos(th)[:, None] * D0[None, :] + np.sin(th)[:, None] * C0[None, :]
    seg = 0.5 * (t[1:] + t[:-1]) * np.diff(ss)[:, None]
    cum = np.vstack([np.zeros(3), np.cumsum(seg, 0)])
    s = np.linspace(0, 1, n + 1)
    return P0[None, :] + L * np.stack([np.interp(s, ss, cum[:, k]) for k in range(3)], -1)


def radius_profile(n, r0, r1, cap=0.80):
    """根元 r0 → r1 へ角（つの）のように細り（(1 − s)^1.3）、先の (1 − cap) を丸める（最後の点は 0）。"""
    s = np.linspace(0, 1, n + 1)
    r = r1 + (r0 - r1) * (1 - s) ** 1.3
    c = np.sqrt(np.clip(1 - np.clip((s - cap) / max(1 - cap, 1e-6), 0, 1) ** 2, 0, 1))
    return r * c


def build_entry(eid, pts, nref, rw, rt, qang, kind, root_disc=None, web=False):
    V, N = CC.tube_verts(pts, nref, rw, rt, qang, root_disc)
    n = len(pts) - 1
    T, kd = CC.layout_tris(n, 0)
    return dict(id=eid, V=V, T=T, kind=kd, n=n, up=CC.vert_up(n), web=web, zone=kind, spine=pts)


# ---------------------------------------------------------------- 区域 1：手（体 ＋ 鉤）
def make_hand(hid, hero, cam, ph, members, log):
    seed = members[0]
    roots = np.array([m["q"][0] for m in members])
    hit = ph.hit(seed["q"][0])
    if hit is None:
        return []
    P0 = hit["P"]
    Fr = hero.frame(np.array(hit["r"]), np.array(hit["c"]))
    n0 = Fr[2]
    z0 = (P0 - cam.pos) @ cam.f
    pxm = z0 * 2 * cam.t / 1080.0
    # 平均の 2 次元の向き（弦、長さで重み）
    chords = np.array([m["q"][-1] - m["q"][0] for m in members])
    lens = np.linalg.norm(chords, axis=1)
    d2 = unit((chords / lens[:, None] * lens[:, None]).sum(0))
    l3 = max(m["Lm"] for m in members)
    L = float(np.clip(P["L_K"] * l3 + 0.25 * np.ptp(roots @ np.array([d2[1], -d2[0]])) * pxm, P["L_MIN"], P["L_MAX"]))
    r0 = float(np.clip(P["R_K"] * L, P["R_MIN"], P["R_MAX"]))
    sgn = np.sign(sum(m["curl"] * m["len2"] for m in members)) or 1.0
    w = img_dir3(cam, d2)
    c2 = sgn * np.array([-d2[1], d2[0]])
    Cimg = img_dir3(cam, c2)
    best = None
    for kap in P["KAPPA"]:
        for lk in (1.0, 0.8, 0.65):
            D0 = unit(w + kap * n0)
            C0 = unit(Cimg - P["CURL_IN"] * n0)
            C0 = unit(C0 - (C0 @ D0) * D0)
            Lb = L * lk
            nb = P["ST_BODY"]
            body = spine_curl(P0 - 0.15 * r0 * n0, D0, C0, Lb * P["S_BRANCH"], P["TH_BODY"], nb)
            # 鉤：体の先から扇に開く
            Tb = unit(body[-1] - body[-2])
            Cb = unit(C0 - (C0 @ Tb) * Tb)
            ax = np.cross(Tb, Cb)
            ntal = int(np.clip(len(members), 2, 3))
            fans = [-P["FAN"], P["FAN"] * 0.15, P["FAN"]] if ntal == 3 else [-0.6 * P["FAN"], 0.6 * P["FAN"]]
            tals = []
            for k, fa in enumerate(fans):
                Dk = rot(Tb, ax, math.radians(fa + jit(hid, k, 6.0)))
                Ck = unit(Cb - (Cb @ Dk) * Dk)
                Lt = Lb * P["TAL_L"] * (1.0 if k == len(fans) // 2 else 0.82) * (1 + jit(hid, 10 + k, 0.12))
                tals.append(spine_curl(body[-1] - 0.25 * r0 * Tb, Dk, Ck, Lt, P["TH_TAL"] * (1 + jit(hid, 20 + k, 0.15)), P["ST_TAL"], p=1.5))
            allp = np.vstack([body[2:]] + [t[1:] for t in tals])
            h = hero.height(allp)
            ok = h.min() > P["CLEAR"] * r0 * 0.9
            score = h.min() / r0
            if best is None or score > best[0]:
                best = (score, kap, lk, body, tals, D0, C0)
            if ok:
                break
        if best[0] > P["CLEAR"] * 0.9:
            break
    score, kap, lk, body, tals, D0, C0 = best
    ents = []
    nb = len(body) - 1
    rb = radius_profile(nb, r0, 0.80 * r0, cap=1.0)
    rb[-1] = 0.78 * r0
    nref = np.repeat(n0[None, :], nb + 1, 0)
    # 体の白の向き：法線と巻きの外（−C0）の間（腹＝巻きの内側が水色）
    nref = unit_rows(nref - 0.8 * C0[None, :])
    disc = (P0 + 0.03 * n0, n0, 1.35 * r0)
    ents.append(build_entry("H%s_b" % hid, body, nref, rb, rb * 0.92, CC.Q_FINGER, "hand", root_disc=disc))
    for k, t in enumerate(tals):
        nt = len(t) - 1
        rt = radius_profile(nt, P["TAL_R"] * r0 * (1.0 if k == len(tals) // 2 else 0.85), 0.35 * r0, cap=P["CAP"])
        Tt = np.gradient(t, axis=0)
        Tt /= np.linalg.norm(Tt, axis=1, keepdims=True)
        # 白の向き：巻きの外（曲がりの外）
        kap_ = np.gradient(Tt, axis=0)
        out = -kap_ / np.maximum(np.linalg.norm(kap_, axis=1, keepdims=True), 1e-9)
        nr = unit_rows(out + 0.3 * n0[None, :])
        ents.append(build_entry("H%s_t%d" % (hid, k), t, nr, rt, rt * 0.9, CC.Q_FINGER, "hand"))
    log.append(dict(id="H" + hid, members=[m["id"] for m in members], L=round(L * lk, 3), r0=round(r0, 3), kappa=kap, len_k=lk,
                    clear_over_r=round(float(score), 3), talons=len(tals), root_rc=[round(hit["r"], 2), round(hit["c"], 2)], z0=round(float(z0), 2)))
    return ents


def unit_rows(A):
    return A / np.maximum(np.linalg.norm(A, axis=1, keepdims=True), 1e-12)


# ---------------------------------------------------------------- 区域 1：頂の稜の冠（原画のカメラから隠れる所だけ）
def make_crown(hero, cam, ph, log):
    """as01_crown：頂の稜の背の側（稜の列 − DC）から、上と背へ立ち、前（稜の上）へ巻く指。原画のカメラから全部の点が隠れる物だけ残す
    （長さと根元の列を段で試す）。彫刻の後ろ・上から見た頂の指の冠。"""
    X = hero.X
    ents = []
    R = hero.R
    b0, b1 = hero.b0, hero.b1
    k = 0
    for r in range(8, R - 8, P["CROWN_DR"]):
        prof = X[r, b0:b1 + 1]
        cy = int(np.argmax(prof[:, 1])) + b0
        eid = "K%03d" % r
        done = False
        for dc in (3, 8, 14, 20):
            for lk in (1.0, 0.75, 0.55):
                rr, cc = float(r), float(cy - dc)
                Fr = hero.frame(np.array(rr), np.array(cc))
                n0, tc, tr = Fr[2], Fr[0], Fr[1]
                P0 = hero.point(np.array(rr), np.array(cc))
                side = math.sin(r * 0.37 * 3.0)
                L = P["CROWN_L"] * lk * (1 + 0.25 * math.sin(r * 0.9) + jit(eid, 1, 0.1))
                D0 = unit(n0 * P["CROWN_KAPPA"] + 0.25 * tc + 0.45 * side * tr)
                C0 = unit(tc - (tc @ D0) * D0)
                sp = spine_curl(P0 - 0.05 * n0, D0, C0, L, P["CROWN_TH"], P["ST_TAL"], p=1.8)
                # v11：隠れの検査は管の太さを入れる（背骨の点だけでは、太らせた管の面が原画のカメラから見えた）
                r0t = P["CROWN_R"] * lk * (1 + 0.15 * math.sin(r * 1.7))
                radt = radius_profile(len(sp) - 1, r0t, 0.28 * r0t, cap=0.88)
                tow = unit_rows(cam.pos[None, :] - sp)
                probe = np.concatenate([sp + radt[:, None] * o for o in (tow, cam.u[None, :], -cam.u[None, :], cam.r[None, :], -cam.r[None, :])])
                q, z = cam.project(probe)
                if all(z[j] > ph.depth_at(q[j]) + 0.2 for j in range(len(probe))):
                    done = True
                    break
            if done:
                break
        if not done:
            continue
        r0 = P["CROWN_R"] * lk * (1 + 0.15 * math.sin(r * 1.7))
        n = len(sp) - 1
        rad = radius_profile(n, r0, 0.28 * r0, cap=0.88)
        Tt = np.gradient(sp, axis=0)
        Tt /= np.linalg.norm(Tt, axis=1, keepdims=True)
        kap_ = np.gradient(Tt, axis=0)
        out = -kap_ / np.maximum(np.linalg.norm(kap_, axis=1, keepdims=True), 1e-9)
        nr = unit_rows(out + 0.3 * n0[None, :])
        ents.append(build_entry(eid, sp, nr, rad, rad * 0.92, CC.Q_FINGER, "crown", root_disc=(P0 + 0.03 * n0, n0, 1.3 * r0)))
        k += 1
    log.append(dict(crown=k))
    return ents


# ---------------------------------------------------------------- 区域 2：面の上の厚い板の鉤
def walk_on_sheet(hero, r0, c0, t0, csgn, L, n_st, th_deg, straight):
    """面に沿って歩く背骨：始めの向き t0（接平面）から、straight まで真っ直ぐ、その後 th_deg だけ巻く（回る軸は面の法線、向きは csgn）。"""
    steps = 6 * n_st
    ds = L / steps
    r, c = float(r0), float(c0)
    Pp = hero.point(np.array(r), np.array(c))
    t = t0.copy()
    pts = [Pp]
    nrm = []
    Fr0 = hero.frame(np.array(r), np.array(c))
    nrm.append(Fr0[2])
    dth = math.radians(th_deg) / max(1, int(steps * (1 - straight)))
    for j in range(steps):
        Q = Pp + ds * t
        rr, cc, hh = hero.project(Q[None, :], np.array([[r, c]]))
        r, c = float(rr[0]), float(cc[0])
        Pn = hero.point(np.array(r), np.array(c))
        Fr = hero.frame(np.array(r), np.array(c))
        n = Fr[2]
        tn = Pn - Pp
        tn = tn - (tn @ n) * n
        if np.linalg.norm(tn) < 1e-9:
            tn = t - (t @ n) * n
        t = unit(tn)
        if j / steps >= straight:
            t = unit(rot(t, n, csgn * dth))
        pts.append(Pn)
        nrm.append(n)
        Pp = Pn
    pts = np.array(pts)
    nrm = np.array(nrm)
    idx = np.linspace(0, steps, n_st + 1).round().astype(int)
    return pts[idx], nrm[idx], (r, c)


def make_hook(cid, hero, cam, ph, cl, log):
    q = cl["q"]
    hit = ph.hit(q[0])
    if hit is None:
        return []
    Fr = hero.frame(np.array(hit["r"]), np.array(hit["c"]))
    d2 = unit(q[min(len(q) - 1, max(2, len(q) // 2))] - q[0])
    t0 = tangent_lift(cam, Fr, d2)
    sgn2 = cl["curl"]
    # 画面で時計回り（sgn2 > 0）の巻きを、面の法線のまわりの回りの向きに直す：n × t の投影が画面の右回りの側か
    n = Fr[2]
    side = np.cross(n, t0)
    sp2 = np.array([side @ cam.r, -(side @ cam.u)])
    want = sgn2 * np.array([-d2[1], d2[0]])
    csgn = 1.0 if sp2 @ want > 0 else -1.0
    L = max(P["HOOK_MIN"], P["HOOK_K"] * cl["Ls"])
    pts, nrm, _ = walk_on_sheet(hero, hit["r"], hit["c"], t0, csgn, L, P["ST_HOOK"], P["HOOK_TH"], P["HOOK_STRAIGHT"])
    w = max(P["HOOK_WMIN"], P["HOOK_W"] * L)
    th = P["HOOK_T"]
    nst = len(pts) - 1
    s = np.linspace(0, 1, nst + 1)
    rw = 0.5 * w * (1.0 - 0.55 * s) * np.sqrt(np.clip(1 - np.clip((s - 0.85) / 0.15, 0, 1) ** 2, 0, 1))
    rw[0] = 0.5 * w * 0.8
    rt = np.minimum(0.5 * th, rw)
    lift = (0.5 * th + P["HOOK_LIFT"])
    spine = pts + nrm * lift
    ents = [build_entry("F%s" % cid, spine, nrm, rw, rt, CC.Q_SHEET, "hook")]
    # 鉤の内の水色の膜：巻きの部分（s ≥ 0.45）を巻きの中心の側へ寄せた、低い板
    i0 = int(0.45 * nst)
    arc = pts[i0:]
    cen = arc.mean(0)
    inner = arc + 0.55 * (cen[None, :] - arc)
    wn = nrm[i0:]
    if len(inner) >= 4:
        m = len(inner) - 1
        sw = np.linspace(0, 1, m + 1)
        rwi = np.maximum(0.5 * P["WEB_W"] * w * np.sin(np.pi * np.clip(sw * 0.9 + 0.05, 0, 1)), 0.02)
        rti = np.full(m + 1, 0.5 * P["WEB_T"])
        ents.append(build_entry("WF%s" % cid, inner + wn * (P["WEB_T"] * 0.5 + 0.015), wn, rwi, rti, CC.Q_SHEET, "hook_web", web=True))
    log.append(dict(id="F" + cid, L=round(L, 3), w=round(w, 3), root_rc=[round(hit["r"], 2), round(hit["c"], 2)], curl=int(csgn)))
    return ents


def make_claw_sheet(cid, hero, cam, ph, cl, log):
    """as01_claw_sheet（区域 2、v11）：原画の爪 1 本ごとに、面に寝る厚い板の「爪」を面の上で作る（投影しない）。
    体（幅 CS_W × 長さの板、根元から原画の 2 次元の向きを接平面へ持ち上げた向きへ面に沿って歩く）の先で、指 3 本が板の幅に並んで出て、
    面の中で少し扇に開き（CS_SPREAD）、原画の爪と同じ回りに面の中で巻く（CS_TH）。真ん中の指の巻きの内に水色の版の膜（WF…）。
    v10 の 1 本の鉤（細い J の字が散らばって見えた）の代わり。長さは原画の爪の面の上の長さ × CS_K（CS_MIN 以上）。"""
    q = cl["q"]
    hit = ph.hit(q[0])
    if hit is None:
        return []
    Fr = hero.frame(np.array(hit["r"]), np.array(hit["c"]))
    d2 = unit(q[min(len(q) - 1, max(2, len(q) // 2))] - q[0])
    t0 = tangent_lift(cam, Fr, d2)
    n = Fr[2]
    side = np.cross(n, t0)
    sp2 = np.array([side @ cam.r, -(side @ cam.u)])
    want = cl["curl"] * np.array([-d2[1], d2[0]])
    csgn = 1.0 if sp2 @ want > 0 else -1.0
    L = max(P["CS_MIN"], P["CS_K"] * cl["Ls"])
    w = P["CS_W"] * L
    th = P["HOOK_T"]
    lift = 0.5 * th + P["HOOK_LIFT"]
    ents = []
    nb = 6
    pb, nbm, (rb, cb) = walk_on_sheet(hero, hit["r"], hit["c"], t0, csgn, P["CS_BODY"] * L, nb, P["CS_BODY_TH"], 0.0)
    s = np.linspace(0, 1, nb + 1)
    rwb = 0.5 * w * (0.70 + 0.30 * np.sin(np.pi * np.clip(0.5 + 0.5 * s, 0, 1)))
    rwb[0] = 0.5 * w * 0.55
    ents.append(build_entry("F%s_b" % cid, pb + nbm * lift, nbm, rwb, np.minimum(0.5 * th, rwb), CC.Q_SHEET, "hook"))
    tb = unit(pb[-1] - pb[-2])
    ne = nbm[-1]
    sd = unit(np.cross(ne, tb))
    fl = []
    for j, u in enumerate((-1.0, 0.0, 1.0)):
        Q = pb[-1] - 0.25 * w * tb + u * P["CS_OFF"] * w * sd
        rr, cc, _ = hero.project(Q[None, :], np.array([[rb, cb]]))
        dj = unit(rot(tb, ne, math.radians(u * P["CS_SPREAD"] * csgn)))
        Lf = P["CS_FING"] * L * (1.0 if u == 0 else 0.72) * (1 + jit(cid, 30 + j, 0.08))
        pf, nf_, _ = walk_on_sheet(hero, float(rr[0]), float(cc[0]), dj, csgn, Lf, P["ST_HOOK"], P["CS_TH"] * (1 + jit(cid, 40 + j, 0.08)), 0.35)
        m = len(pf) - 1
        sf = np.linspace(0, 1, m + 1)
        rwf = 0.5 * P["CS_FW"] * w * (1.0 - 0.6 * sf) * np.sqrt(np.clip(1 - np.clip((sf - 0.85) / 0.15, 0, 1) ** 2, 0, 1))
        rwf[0] = 0.5 * P["CS_FW"] * w
        ents.append(build_entry("F%s_f%d" % (cid, j), pf + nf_ * lift, nf_, rwf, np.minimum(0.5 * th, rwf), CC.Q_SHEET, "hook"))
        fl.append(round(float(Lf), 3))
        if u == 0:
            i0 = int(0.45 * m)
            arc = pf[i0:]
            cen = arc.mean(0)
            inner = arc + 0.55 * (cen[None, :] - arc)
            wn = nf_[i0:]
            if len(inner) >= 4:
                mm = len(inner) - 1
                sw = np.linspace(0, 1, mm + 1)
                rwi = np.maximum(0.5 * P["WEB_W"] * P["CS_FW"] * w * 1.6 * np.sin(np.pi * np.clip(sw * 0.9 + 0.05, 0, 1)), 0.02)
                rti = np.full(mm + 1, 0.5 * P["WEB_T"])
                ents.append(build_entry("WF%s" % cid, inner + wn * (P["WEB_T"] * 0.5 + 0.015), wn, rwi, rti, CC.Q_SHEET, "hook_web", web=True))
    log.append(dict(id="F" + cid, kind="claw_sheet", L=round(L, 3), w=round(w, 3), fingers=fl, root_rc=[round(hit["r"], 2), round(hit["c"], 2)], curl=int(csgn)))
    return ents


# ---------------------------------------------------------------- 一覧
def read_list(hero, cam, ph):
    inv = json.load(open(CC.INV, encoding="utf-8"))
    out = []
    rho_img = None
    for c in inv["claws"]:
        if c["zone"] != "main" or not c.get("centerline_ref"):
            continue
        q = U.to_disp(np.array(c["centerline_ref"], np.float64))
        hit = ph.hit(q[0])
        if hit is None:
            continue
        Fr = hero.frame(np.array(hit["r"]), np.array(hit["c"]))
        v = unit(hit["P"] - cam.pos)
        rho = float(Fr[2] @ v)
        z0 = float((hit["P"] - cam.pos) @ cam.f)
        len2 = float(np.linalg.norm(np.diff(q, axis=0), axis=1).sum())
        Lm = len2 * z0 * 2 * cam.t / 1080.0
        # 面の上の長さ（中心線の各点の射線の当たりを結ぶ。当たらない点は除く）
        hits = [ph.hit(p) for p in q[:: max(1, len(q) // 12)]]
        hp = np.array([h["P"] for h in hits if h is not None])
        Ls = float(np.linalg.norm(np.diff(hp, axis=0), axis=1).sum()) if len(hp) > 1 else Lm
        out.append(dict(id=c["id"], row=c["row"], q=q, rho=rho, z0=z0, len2=len2, Lm=Lm, Ls=min(Ls, 2.5 * Lm), curl=curl_sign(q), hit=hit))
    return out


def cluster(cls):
    """区域 1 の爪を、根元が近く（CL_PX）向きが揃う（CL_ANG）2〜4 本の手にまとめる（長い順の貪欲法）。"""
    order = sorted(range(len(cls)), key=lambda i: -cls[i]["len2"])
    used = set()
    groups = []
    for i in order:
        if i in used:
            continue
        g = [i]
        used.add(i)
        di = unit(cls[i]["q"][-1] - cls[i]["q"][0])
        cand = sorted([j for j in range(len(cls)) if j not in used], key=lambda j: np.linalg.norm(cls[j]["q"][0] - cls[i]["q"][0]))
        for j in cand:
            if len(g) >= P["CL_MAX"]:
                break
            if np.linalg.norm(cls[j]["q"][0] - cls[i]["q"][0]) > P["CL_PX"]:
                break
            dj = unit(cls[j]["q"][-1] - cls[j]["q"][0])
            if di @ dj < math.cos(math.radians(P["CL_ANG"])):
                continue
            g.append(j)
            used.add(j)
        groups.append([cls[k] for k in g])
    return groups


def write_layout(out, entries):
    os.makedirs(out, exist_ok=True)
    V, T, A, claws = [], [], [], []
    off = 0
    for k, e in enumerate(entries):
        nv = len(e["V"])
        assert nv == 8 * e["n"] + 11, (e["id"], nv)
        V.append(e["V"])
        T.append(e["T"] + off)
        A.append(np.stack([np.full(len(e["kind"]), k), e["kind"]], 1))
        claws.append({"id": e["id"], "index": k, "vert_offset": off, "vert_count": nv, "stations": e["n"], "type": e["zone"], "as01_zone": e["zone"]})
        off += nv
    Vv = np.concatenate(V).astype(np.float32)[None]
    Tt = np.concatenate(T).astype(np.int32)
    Aa = np.concatenate(A).astype(np.uint16)
    assert np.isfinite(Vv).all()
    fn = dict(frames="ds33_claw_frames_f32.bin", tris="ds33_claw_tris_i32.bin", tri_attr="ds33_claw_tri_attr_u16.bin", skel="ds33_claw_skel_f32.bin")
    Vv.tofile(os.path.join(out, fn["frames"]))
    Tt.tofile(os.path.join(out, fn["tris"]))
    Aa.tofile(os.path.join(out, fn["tri_attr"]))
    np.zeros((1, len(entries), 36), np.float32).tofile(os.path.join(out, fn["skel"]))
    files = {k: {"file": v, "sha256": CC.sha(os.path.join(out, v)), "bytes": os.path.getsize(os.path.join(out, v))} for k, v in fn.items()}
    files["frames"]["layout_ja"] = "float32、コマ 1 × 頂点 × 3（ワールドの m、t* の静止）"
    files["tris"]["layout_ja"] = "int32、三角形 × 3"
    files["tri_attr"]["layout_ja"] = "uint16、三角形 × 2（爪の番号、面の種類 0 上面・1 縁の側面と下面・2 根元の円）"
    files["skel"]["layout_ja"] = "float32、コマ × 爪 × 36（この見本は 0）"
    lay = {"schema": "GreatWave.DS33.claw_layout/1", "frames": 1, "hz": 30.0, "vertices": int(off), "triangles": int(len(Tt)),
           "clock_ja": "美術の見本01：コマ 1 つ（t* の静止）。DS34ClawPlayer はどの時刻でもこのコマを使う（Frames − 1 で止まる）",
           "timewarp": "なし（静止）", "claws": claws, "files": files,
           "vertex_order_ja": "爪ごとに 根元 1・輪 stations × 8・先 1・根元の円の中心 1・円 8（設計33 と同じ）。輪の頂点 q の色は PL29 Claw Shade（sin(45°·q) > 0.30 が白）",
           "as01": {"tool": "Tools/GWWaveGen/as01/claws_build.py", "params": P}}
    json.dump(lay, open(os.path.join(out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # OBJ（区域ごとのグループ）
    with open(os.path.join(out, "as01_claws.obj"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# 美術の見本01 爪（t* の静止、ワールドの m。Unity の左手系の座標をそのまま書く）\n")
        Vf = Vv[0]
        for v in Vf:
            f.write("v %.5f %.5f %.5f\n" % (v[0], v[1], v[2]))
        for zone in ("rim", "rim_shadow", "crown", "hook", "hook_web"):
            f.write("g as01_%s\n" % zone)
            for k, e in enumerate(entries):
                if e["zone"] != zone:
                    continue
                o = claws[k]["vert_offset"]
                for t in e["T"]:
                    f.write("f %d %d %d\n" % (t[0] + o + 1, t[1] + o + 1, t[2] + o + 1))
    return lay


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=CC.OUTD + "/mesh")
    ap.add_argument("--no-crown", action="store_true")
    ap.add_argument("--zones", default="rim,crown,hook")
    ap.add_argument("--fams", default="", help="区域 1 の列の名前（L0,L1,R1,R2,R3。空なら全部）。見本の案 B（輪だけ）は L0,L1,R1")
    a = ap.parse_args()
    t0 = time.time()
    X0 = CC.load_hero()
    hero = CC.Hero(X0)
    cam = CC.painting_cam()
    ph = PaintHit(hero, cam)
    cls = read_list(hero, cam, ph)
    # 区域 1 の帯（唇の先の列 c_tip(r) から外の巻きの面の L2 の少し奥まで、行 R0〜R1）の外の原画の爪を、区域 2 の面の鉤にする
    ct = CR.c_tip_rows(hero)
    def in_band(c):
        r, cc = c["hit"]["r"], c["hit"]["c"]
        k = int(round(np.clip(r, 0, hero.R - 1)))
        # v11：区域 1 は L0（c_tip − 2）・R1（− 50）・R2（− 74）の列が受け持つ帯（c_tip − 90 〜 唇の先の下。主の唇の下は櫛の巻きが覆うので + 25）
        return CR.RIM["R0"] <= r <= CR.RIM["R1"] and ct[k] - 90 <= cc <= ct[k] + (8 if r < 127 else 25)
    z1 = [c for c in cls if in_band(c)]
    z2 = [c for c in cls if not in_band(c)]
    print("list", len(cls), "zone1(band)", len(z1), "zone2", len(z2), round(time.time() - t0, 1), "s", flush=True)
    zones = set(a.zones.split(","))
    ents, log = [], []
    if "rim" in zones:
        ents += CR.make_rim(hero, sys.modules[__name__], log, fams=set(a.fams.split(",")) if a.fams else None)
        print("rim", sum(1 for e in ents if e["zone"] == "rim"), round(time.time() - t0, 1), "s", flush=True)
    if "crown" in zones and not a.no_crown:
        ents += make_crown(hero, cam, ph, log)
        print("crown done", round(time.time() - t0, 1), "s", flush=True)
    if "hook" in zones:
        for c in z2:
            ents += make_claw_sheet(c["id"], hero, cam, ph, c, log)
        print("hooks", len(z2), round(time.time() - t0, 1), "s", flush=True)
    lay = write_layout(a.out, ents)
    rep = dict(params=P, rim=dict(fams=a.fams or "all", RIM={k: v for k, v in CR.RIM.items()}), counts=dict(entries=len(ents), vertices=lay["vertices"], triangles=lay["triangles"],
                                     by_zone={z: sum(1 for e in ents if e["zone"] == z) for z in ("rim", "rim_shadow", "crown", "hook", "hook_web")},
                                     zone1_claws=len(z1), zone2_claws=len(z2)),
               log=log, hero_pkg=os.path.relpath(CC.HERO, REPO).replace("\\", "/"), inventory=os.path.relpath(CC.INV, REPO).replace("\\", "/"),
               inventory_sha256=CC.sha(CC.INV), elapsed_s=round(time.time() - t0, 1))
    CC.jdump(os.path.join(a.out, "as01_claws_report.json"), rep)
    np.save(os.path.join(a.out, "as01_entries.npy"), np.array([dict(id=e["id"], V=e["V"], T=e["T"], up=e["up"], web=e["web"], zone=e["zone"]) for e in ents], dtype=object), allow_pickle=True)
    print("AS01_CLAWS_DONE", json.dumps(rep["counts"], ensure_ascii=False), rep["elapsed_s"], "s")


if __name__ == "__main__":
    main()
