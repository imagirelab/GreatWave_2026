# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）の 3：Houdini で造形した t* の鍵の形（key_tstar_mesh.npz）を、指ごとの中心線に結び付けて全コマへ動かし、
設計34 の爪の層の書式（GreatWave.DS33.claw_layout/1）で書き出す（numpy）。

結び付け（pl33r01h_bind）：鍵の形の各頂点を、その指の t* の立つ中心線（22 点の折れ線）の一番近い所（区間 j・割合 t）へ結び、
  回転の少ない座標系（根元で T と根元の円の法線 N、以後は平行移動）での差を、そこの半径で割って持つ。
各コマ（pl33r01h_follow）：そのコマの爪の帯（仕上げ33 の採用の並び）から面の上の中心線・半幅・根元の円を取り、houdini_common.stand2
  （Houdini の stand の wrangle と同じ式、同じランプの標本）で立つ中心線と半径を作り、v = S(j,t) + [T N B](j,t)·o·R(j,t) と置く。
  根元が白くなる前（帯が根元の点に潰れている）は半径 0・中心線が根元の 1 点なので、指も帯の粒も根元の点に潰れて面積 0（描かれない）。
  伸びる間は、中心線が伸び（帯の伸び）、半径が太り（帯の幅）、立ち上がりが伸びの割合で高くなり、先の巻き戻しは伸びの 60% から入る。
頂点の属性（vattr、float32 × 4）：UV2 =（陰の段 x、根元 0 → 先 1）、UV3 =（縁の線の根元からの位置、0）。
  陰の段 x = clip(n·N + SHADE_BIAS, −0.40, 1)（n は t* の頂点の法線、N は指の上の向き＝根元の円の法線。PL29 Claw Shade の段で x > 0.30 が白、
  それ以下が水色の版。藍中の段（≤ −0.45）は使わない）。帯の粒の側（根元より後ろ、または半径の 1.6 倍より外）は白（x = 1）で縁の線なし（−1）。
原画カメラからの投影の色は使わない（Q28）。
"""
import argparse
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import houdini_common as H  # noqa: E402

G_RATE = 0.04       # 伸びの割合の 1 コマの変化の上限
CURL_SHADE = 1.4    # 曲がりの内側の水色の版の強さ
CURL_K0, CURL_K1 = 0.6, 2.0   # 曲率（1/m）：CURL_K0 から効き始め CURL_K1 で全部
BUD_G = 0.35        # 伸びの割合がこれ未満の芽は、太さも割合に合わせて細くする
SHADE_BIAS = 0.60   # 陰の段 x = n·N + SHADE_BIAS（x > 0.30 で白）：指の下の側（N と逆の 3 割ほど）だけ水色の版


def frames_rmf(P, NO):
    """P (n,22,3) の折れ線ごとの回転の少ない座標系 T, N, B (n,22,3)。根元で N = NO を T に直交させる。"""
    n, m, _ = P.shape
    # 接線は前後 2 点の差（根元の点と最初の輪の中心がほとんど重なる爪で、向きがコマごとに揺れないように）。1 mm 未満の差は隣の向きを使う
    lo = np.clip(np.arange(m) - 2, 0, m - 1); hi = np.clip(np.arange(m) + 2, 0, m - 1)
    D = P[:, hi] - P[:, lo]
    ln = np.linalg.norm(D, axis=2, keepdims=True)
    T = np.where(ln > 1e-3, D / np.maximum(ln, 1e-12), 0.0)
    for k in range(1, m):
        bad = ln[:, k, 0] <= 1e-3
        T[bad, k] = T[bad, k - 1]
    for k in range(m - 2, -1, -1):
        bad = np.linalg.norm(T[:, k], axis=1) < 0.5
        T[bad, k] = T[bad, k + 1]
    bad = np.linalg.norm(T[:, 0], axis=1) < 0.5
    T[bad] = np.array([0.0, 1.0, 0.0])
    N = np.zeros_like(P)
    n0 = NO - (NO * T[:, 0]).sum(1, keepdims=True) * T[:, 0]
    nn = np.linalg.norm(n0, axis=1, keepdims=True)
    alt = np.cross(T[:, 0], np.array([0.0, 0.0, 1.0]))
    n0 = np.where(nn > 1e-6, n0 / np.maximum(nn, 1e-12), alt / np.maximum(np.linalg.norm(alt, axis=1, keepdims=True), 1e-12))
    N[:, 0] = n0
    for k in range(1, m):
        # 平行移動：前の N を、前の T から今の T への回転で運ぶ（ダブル・リフレクションの簡単な版：射影して正規化）
        v = N[:, k - 1] - (N[:, k - 1] * T[:, k]).sum(1, keepdims=True) * T[:, k]
        vn = np.linalg.norm(v, axis=1, keepdims=True)
        N[:, k] = np.where(vn > 1e-9, v / np.maximum(vn, 1e-12), N[:, k - 1])
    B = np.cross(T, N)
    return T, N, B


def side_ref(C, UP):
    """回転の少ない座標系の始めの向き（pl33r01h_side_frame）：面の上の中心線の根元の接線と面の法線（帯の上）の外積＝面の中で中心線に直交する横の向き。
    立ち上げた指の根元の接線（面の接線と射線の混ざり）とほぼ直交するので、根元の法線を使うより向きが揺れない。"""
    t = C[:, 2] - C[:, 0]
    w = np.cross(UP[:, 0], t)
    n = np.linalg.norm(w, axis=1, keepdims=True)
    return np.where(n > 1e-9, w / np.maximum(n, 1e-12), np.array([1.0, 0.0, 0.0]))


def frames_ray(P, NO, kind):
    """原画の爪・添え指（kind 0・1）は、断面の軸を原画のカメラへの射線を断面の面へ写した向き a にそろえる（pl33r01h_ray_frame。
    Houdini の depth_section と同じ軸なので、伸ばした断面がコマごとに捻じれない）。冠の爪と、射線が中心線に沿う所は回転の少ない座標系。"""
    T, N, B = frames_rmf(P, NO)
    ray = P - H.CAM_U[None, None, :]
    ray = ray / np.maximum(np.linalg.norm(ray, axis=2, keepdims=True), 1e-9)
    a = ray - (ray * T).sum(2, keepdims=True) * T
    la = np.linalg.norm(a, axis=2, keepdims=True)
    ok = (la[:, :, 0] > 0.05) & (kind[:, None] != 2)
    a = a / np.maximum(la, 1e-12)
    # a はいつもカメラから離れる向き（固定のカメラなので、コマの間で符号が変わらない）
    N2 = np.where(ok[:, :, None], a, N)
    B2 = np.cross(T, N2)
    return T, N2, B2


def nearest_on_polyline(V, S):
    """V (k,3) の各点に一番近い S (22,3) の上の点の区間 j と割合 t（両端は延長：最初の区間で t < 0、最後の区間で t > 1 を許す）。"""
    A = S[:-1]; Bv = S[1:]
    AB = Bv - A
    L2 = np.maximum((AB * AB).sum(1), 1e-12)
    t = ((V[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None]      # (k, 21)
    tc = np.clip(t, 0.0, 1.0)
    Q = A[None] + tc[:, :, None] * AB[None]
    d2 = ((V[:, None, :] - Q) ** 2).sum(2)
    j = np.argmin(d2, axis=1)
    tt = t[np.arange(len(V)), j]
    tt = np.where((j == 0) & (tt < 0), tt, np.where((j == len(S) - 2) & (tt > 1), tt, np.clip(tt, 0, 1)))
    tt = np.clip(tt, -50.0, 50.0)
    return j, tt, np.sqrt(d2[np.arange(len(V)), j])


def lerp_at(X, fidv, j, t):
    """X (n,22,...) を頂点ごとの (指, 区間 j, 割合 t) で補間する（両端の延長は端の値）。"""
    tc = np.clip(t, 0.0, 1.0)
    a = X[fidv, j]; b = X[fidv, j + 1]
    if a.ndim == 1:
        return a + (b - a) * tc
    return a + (b - a) * tc[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default=H.OUT + "/key")
    ap.add_argument("--prep", default=H.OUT + "/prep")
    ap.add_argument("--out", default=H.OUT + "/claws")
    ap.add_argument("--no-webs", dest="webs", action="store_false", help="仕上げ33 の鉤の内の膜を足さない")
    ap.add_argument("--houdini-crowns", dest="crown33", action="store_false", help="冠の爪も Houdini の丸い管にする（既定は仕上げ33 の帯）")
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    K = np.load(a.key + "/key_tstar_mesh.npz")
    ramps = json.load(open(a.key + "/ramps.json", encoding="utf-8"))
    S = np.load(a.prep + "/frames_spines.npz")
    FJ = json.load(open(a.prep + "/fingers_tstar.json", encoding="utf-8"))
    ids = [f["id"] for f in FJ["fingers"]]
    nfing = len(ids)
    U_star = S["U_star"].astype(np.float64); Hh = S["H"].astype(np.float64); kind = S["kind"]; sgn = S["sgn"].astype(np.float64)
    A_star = S["A_star"].astype(np.float64)
    CF, UF, WF, RF = S["C"], S["UP"], S["HW"], S["RC"]
    nf = CF.shape[0]

    # 鍵の形（Unity の座標へ）。指ごとに頂点をまとめて並べ直す
    Pk = H.h2u(K["P_h"].astype(np.float64)); tris = K["tris"].astype(np.int64); fid = K["fid"].astype(np.int64)
    order = np.argsort(fid, kind="stable")
    inv = np.empty_like(order); inv[order] = np.arange(len(order))
    Pk = Pk[order]; fid = fid[order]; tris = inv[tris]
    # 三角形も指の順に
    tf = fid[tris[:, 0]]
    tord = np.argsort(tf, kind="stable"); tris = tris[tord]; tf = tf[tord]
    present = np.unique(fid)

    # t* の立つ中心線（numpy）と Houdini の stand の結果の比べ
    f = H.K_STAR
    Cs, Us, Ws, Rs = (CF[f].astype(np.float64), UF[f].astype(np.float64), WF[f].astype(np.float64), RF[f].astype(np.float64))
    A_now = H.arclen(Cs)
    Pst, Rst, NOs = H.stand2(Cs, Us, Ws, Rs, U_star, Hh, kind, sgn, A_now, A_star, ramps)
    sp = H.h2u(K["stand_P_h"].astype(np.float64)); sfid = K["stand_fid"]; spad = K["stand_ispad"]; sR = K["stand_R"]
    hp = np.zeros_like(Pst); hr = np.zeros_like(Rst)
    for i in range(nfing):
        m = (sfid == i) & (spad == 0)
        hp[i] = sp[m]; hr[i] = sR[m]
    err_P = float(np.abs(hp - Pst).max()); err_R = float(np.abs(hr - Rst).max())

    # 結び付け
    # 横の向きをコマの順に作る（芽の間は前の向きを持ち越し、向きの符号を前のコマにそろえる）。t* の結び付けも同じ向きを使う
    W_hold = side_ref(Cs, Us)
    W_all = np.zeros((nf, len(ids), 3))
    for f_ in range(nf):
        Cf_ = CF[f_].astype(np.float64)
        W = side_ref(Cf_, UF[f_].astype(np.float64))
        short = np.linalg.norm(Cf_[:, 2] - Cf_[:, 0], axis=1) < 0.03
        W[short] = W_hold[short]
        flip = (W * W_hold).sum(1) < 0
        W[flip] = -W[flip]
        W_hold = W.copy()
        W_all[f_] = W
    T0, N0, B0 = frames_rmf(Pst, W_all[H.K_STAR])
    nv = len(Pk)
    J = np.zeros(nv, np.int64); TT = np.zeros(nv); OL = np.zeros((nv, 3)); DIST = np.zeros(nv)
    for i in present:
        m = np.where(fid == i)[0]
        j, t, d = nearest_on_polyline(Pk[m], Pst[i])
        J[m] = j; TT[m] = t; DIST[m] = d
    tc = np.clip(TT, 0.0, 1.0)
    seg = Pst[fid, J + 1] - Pst[fid, J]
    S0 = Pst[fid, J] + seg * tc[:, None]
    Tn = lerp_at(T0, fid, J, TT); Nn = lerp_at(N0, fid, J, TT)
    Tn /= np.maximum(np.linalg.norm(Tn, axis=1, keepdims=True), 1e-12)
    Nn = Nn - (Nn * Tn).sum(1, keepdims=True) * Tn; Nn /= np.maximum(np.linalg.norm(Nn, axis=1, keepdims=True), 1e-12)
    Bn = np.cross(Tn, Nn)
    Rraw0 = lerp_at(Rst, fid, J, TT)
    R0 = np.maximum(Rraw0, 0.02)
    dv = Pk - S0
    OL[:, 0] = (dv * Tn).sum(1) / R0; OL[:, 1] = (dv * Nn).sum(1) / R0; OL[:, 2] = (dv * Bn).sum(1) / R0

    # 頂点の法線（t*）と陰の段・線の印
    Vn = np.zeros_like(Pk)
    fn = np.cross(Pk[tris[:, 1]] - Pk[tris[:, 0]], Pk[tris[:, 2]] - Pk[tris[:, 0]])
    for k in range(3):
        np.add.at(Vn, tris[:, k], fn)
    Vn /= np.maximum(np.linalg.norm(Vn, axis=1, keepdims=True), 1e-12)
    ushape = np.clip((J + tc) / (H.NPT - 1), 0.0, 1.0)
    u_arc = lerp_at(U_star, fid, J, TT)
    ellv = np.array([f_.get("ell", 1.0) for f_ in FJ["fingers"]])[fid]
    padside = ((J == 0) & (TT <= 0.02)) | ((np.sqrt(OL[:, 1] ** 2 + OL[:, 2] ** 2) > 1.4 * ellv) & (u_arc < 0.3))
    # pl33r01h_curl_shade：指の中心線の曲がりの内側（曲がりの中心を向く面）を水色の版にする（鉤の内の陰。中心線の曲率だけで決まり、視点によらない）
    Kc = np.zeros_like(Pst)
    Kc[:, 1:-1] = Pst[:, 2:] - 2 * Pst[:, 1:-1] + Pst[:, :-2]
    seg_l = np.maximum(np.linalg.norm(np.diff(Pst, axis=1), axis=2).mean(1), 1e-4)
    Kc = Kc - (Kc * T0).sum(2, keepdims=True) * T0
    kap = np.linalg.norm(Kc, axis=2) / seg_l[:, None] ** 2          # 曲率（1/m）
    Kh = Kc / np.maximum(np.linalg.norm(Kc, axis=2, keepdims=True), 1e-12)
    Kv = lerp_at(Kh, fid, J, TT); kv = lerp_at(kap, fid, J, TT)
    wk = np.clip((kv - CURL_K0) / (CURL_K1 - CURL_K0), 0.0, 1.0)
    Upn = NOs[fid] - (NOs[fid] * Tn).sum(1, keepdims=True) * Tn      # 指の上の向き（根元の円の法線を接線に直交させた向き）
    Upn /= np.maximum(np.linalg.norm(Upn, axis=1, keepdims=True), 1e-12)
    shade = np.clip((Vn * Upn).sum(1) + SHADE_BIAS - CURL_SHADE * wk * np.maximum(0.0, (Vn * Kv).sum(1)), -0.40, 1.0)
    shade = np.where(padside, 1.0, shade)
    line = np.where(padside, -1.0, u_arc)
    vattr = np.stack([shade, u_arc, line, np.zeros(nv)], axis=1).astype(np.float32)

    # 伸びの割合 g = 弧長 ÷ t* の弧長 を、コマの間で 1 コマ G_RATE より速く変えない（pl33r01h_grow_rate。仕上げ33 の添え指の倍率の
    # 切り替えで弧長が速く変わる所でも、立ち上がり（g に比例）が跳ばないように）。t* では g = 1 のまま（鍵の形と同じ）
    A_all = np.linalg.norm(np.diff(CF.astype(np.float64), axis=2), axis=3).sum(axis=2)
    g_raw = np.clip(A_all / np.maximum(A_star, 1e-9)[None], 0.0, 1.0)
    g_s = g_raw.copy()
    for f in range(1, nf):
        g_s[f] = np.clip(g_raw[f], g_s[f - 1] - G_RATE, g_s[f - 1] + G_RATE)
    g_s[H.K_STAR:] = g_raw[H.K_STAR:]
    for f in range(H.K_STAR - 1, -1, -1):     # t* へ向けても速さを抑える（後ろから）
        g_s[f] = np.clip(g_s[f], g_s[f + 1] - G_RATE, g_s[f + 1] + G_RATE)
    # 全部のコマ
    frames = np.zeros((nf, nv, 3), np.float32)
    jump_max = 0.0; nan = 0; jumps = []
    prev = None
    sk_alive = np.zeros((nf, nfing), bool)
    for f in range(nf):
        C, UPf, HWf, RCf = (CF[f].astype(np.float64), UF[f].astype(np.float64), WF[f].astype(np.float64), RF[f].astype(np.float64))
        A_now = g_s[f] * A_star
        Pf, Rf, NOf = H.stand2(C, UPf, HWf, RCf, U_star, Hh, kind, sgn, A_now, A_star, ramps)
        Tf, Nf, Bf = frames_rmf(Pf, W_all[f])
        segf = Pf[fid, J + 1] - Pf[fid, J]
        Sf = Pf[fid, J] + segf * tc[:, None]
        Tv = lerp_at(Tf, fid, J, TT); Nv = lerp_at(Nf, fid, J, TT)
        Tv /= np.maximum(np.linalg.norm(Tv, axis=1, keepdims=True), 1e-12)
        Nv = Nv - (Nv * Tv).sum(1, keepdims=True) * Tv; Nv /= np.maximum(np.linalg.norm(Nv, axis=1, keepdims=True), 1e-12)
        Bv = np.cross(Tv, Nv)
        Rv = lerp_at(Rf, fid, J, TT)
        # 半径の比（そのコマの半径 ÷ t* の半径）で、頂点の差を縮める（t* では R0 のまま＝鍵の形そのもの）
        Rr = R0 * np.clip(Rv / np.maximum(Rraw0, 1e-4), 0.0, 3.0)
        # pl33r01h_bud：伸び始め（g < BUD_G）は指の太さと頂の帯も g に合わせて小さくする（短い中心線に全部の太さが載って、
        # 座標系の揺れで頂点が跳ぶのを防ぐ。仕上げ32 の pl32f_bud_width と同じ考え方）
        Rr = Rr * np.clip(g_s[f] / BUD_G, 0.0, 1.0)[fid]
        V = Sf + (Tv * OL[:, :1] + Nv * OL[:, 1:2] + Bv * OL[:, 2:3]) * Rr[:, None]
        alive = Rf.max(axis=1) > 1e-6
        sk_alive[f] = alive
        dead = ~alive[fid]
        V[dead] = C[fid[dead], 0]
        nan += int(np.isnan(V).sum())
        V = np.nan_to_num(V)
        if prev is not None:
            # 根元に対するコマの間の動き
            r_now = C[fid, 0]; r_prev = prevroot[fid]
            jm = np.linalg.norm((V - r_now) - (prev - r_prev), axis=1)
            jump_max = max(jump_max, float(jm.max()))
            fm = np.zeros(nfing); np.maximum.at(fm, fid, jm)
            for i in np.where(fm > 0.25)[0]:
                jumps.append((round(float(fm[i]), 3), f, ids[i]))
        prev = V; prevroot = C[:, 0].copy()
        frames[f] = V.astype(np.float32)
    err_key = float(np.abs(frames[H.K_STAR].astype(np.float64) - Pk).max())

    # pl33r01h_crown33：冠の爪（K…、原画視点で隠れる頂の裏の鉤）は、Houdini の丸い管にすると後ろ 65°・回り台で粒に見えたので（v6 の試し）、
    # 仕上げ33 の帯（面から 55° で立ち上がる鉤の房）をそのまま使う。Houdini の冠の爪の頂点は落とす
    if a.crown33:
        keepv = kind[fid] != 2
        newi = -np.ones(nv, np.int64); newi[keepv] = np.arange(int(keepv.sum()))
        tk = keepv[tris].all(1)
        tris = newi[tris[tk]]
        frames = frames[:, keepv]
        fid = fid[keepv]; vattr = vattr[keepv]; shade = shade[keepv]; padside = padside[keepv]
        tf = fid[tris[:, 0]]
        nv = int(keepv.sum())
    # pl33r01h_keep_webs：仕上げ33 の鉤の内の水色の膜（W…、pl33_hook_web・pl33f2_white_clip。帯の頂点だけで決まる 3D の薄い膜）を
    # そのまま足す（原画視点の爪の律動の水色。色は水色の版の段、縁の線なし）。指は膜の上（手前）に立つ
    web_rep = None
    wi = []
    if a.webs or a.crown33:
        L33, F33 = H.load_layout()
        wi = [c for c in L33["claws"] if (a.webs and c["id"].startswith("W")) or (a.crown33 and c["id"].startswith("K"))]
        widx = np.concatenate([np.arange(c["vert_offset"], c["vert_offset"] + c["vert_count"]) for c in wi])
        t33 = np.fromfile(H.SRC_CLAWS + "/" + L33["files"]["tris"]["file"], np.int32).reshape(-1, 3)
        a33 = np.fromfile(H.SRC_CLAWS + "/" + L33["files"]["tri_attr"]["file"], np.uint16).reshape(-1, 2)
        wset = np.array([c["index"] for c in wi])
        tm = np.isin(a33[:, 0], wset)
        remap = -np.ones(L33["vertices"], np.int64); remap[widx] = nv + np.arange(len(widx))
        wt = remap[t33[tm]]
        assert (wt >= 0).all()
        wframes = np.stack([np.asarray(F33[f])[widx] for f in range(nf)])
        frames = np.concatenate([frames, wframes.astype(np.float32)], axis=1)
        del wframes
        vl = []
        for c in wi:
            n_ = c["vert_count"]
            v = np.zeros((n_, 4), np.float32)
            if c["id"].startswith("W"):
                v[:, 2] = -1.0                                   # 膜：水色の版、線なし（PL33ClawLook と同じ）
            else:
                st = (n_ - 11) // 8                              # 帯：PL29ClawShade と PL32ClawLook の決まり（輪の並び）
                v[0] = (1, 0, 0, 0)
                for s_ in range(st):
                    for q in range(8):
                        v[1 + s_ * 8 + q] = (np.sin(np.radians(q * 45.0)), s_ / max(1, st - 1), s_ / max(1, st - 1), 1 if 1 <= q <= 3 else (2 if q >= 5 else 0))
                v[1 + st * 8] = (0, 1, 1, 0)
                v[2 + st * 8:] = (0.0, 0, -1, 0)
            vl.append(v)
        vattr_w = np.vstack(vl)
        web_rep = {"webs": sum(1 for c in wi if c["id"].startswith("W")), "crowns33": sum(1 for c in wi if c["id"].startswith("K")),
                   "appended_vertices": int(len(widx)), "appended_triangles": int(tm.sum()), "src": H.SRC_CLAWS}

    # 書き出し（設計34 の書式）
    vc = np.bincount(fid, minlength=nfing)
    vo = np.concatenate([[0], np.cumsum(vc)[:-1]])
    claws = []
    for i in range(nfing):
        if vc[i] == 0:
            continue
        claws.append({"id": "H" + ids[i], "src_id": ids[i], "index": len(claws), "vert_offset": int(vo[i]), "vert_count": int(vc[i]),
                      "stations": 0, "type": FJ["fingers"][i]["type"] or ("crown" if kind[i] == 2 else ""), "kind": int(kind[i])})
    tri_type = np.where(shade[tris].mean(1) > 0.30, 0, 1)
    cidx = np.array([0] * nfing); m = {c["src_id"]: c["index"] for c in claws}
    for i in range(nfing):
        cidx[i] = m.get(ids[i], 0)
    attr = np.stack([cidx[tf], tri_type], axis=1).astype(np.uint16)
    if web_rep is not None:
        # 膜と冠の爪（仕上げ33）の頂点は指の後ろに続ける（項目ごとにまとめた並びのまま）
        off = nv
        for c in wi:
            claws.append({"id": c["id"], "src_id": c["id"], "index": len(claws), "vert_offset": int(off), "vert_count": int(c["vert_count"]),
                          "stations": c.get("stations", 0), "type": "web" if c["id"].startswith("W") else "crown33", "kind": 3 if c["id"].startswith("W") else 4})
            off += c["vert_count"]
        base = len(claws) - len(wi)
        wmap = {c["index"]: base + k for k, c in enumerate(wi)}
        wcl = np.array([wmap[int(x)] for x in a33[tm, 0]])
        tris = np.vstack([tris, wt])
        attr = np.vstack([attr, np.stack([wcl, a33[tm, 1]], axis=1).astype(np.uint16)])
        vattr = np.vstack([vattr, vattr_w])
        nv = nv + len(vattr_w)
    fp = a.out + "/ds33_claw_frames_f32.bin"; frames.tofile(fp)
    tp = a.out + "/ds33_claw_tris_i32.bin"; tris.astype(np.int32).tofile(tp)
    ap_ = a.out + "/ds33_claw_tri_attr_u16.bin"; attr.tofile(ap_)
    vp = a.out + "/pl33r01h_vattr_f32.bin"; vattr.tofile(vp)
    lay = {"schema": "GreatWave.DS33.claw_layout/1", "frames": int(nf), "hz": 30, "vertices": int(nv), "triangles": int(len(tris)),
           "clock_ja": "コマ k は t = k/30 s（仕上げ33 の採用の爪の並びと同じ時計）",
           "claws": claws,
           "files": {"frames": {"file": os.path.basename(fp), "layout_ja": "float32、コマ × 頂点 × 3（ワールドの m）", "sha256": H.sha256(fp), "bytes": os.path.getsize(fp)},
                     "tris": {"file": os.path.basename(tp), "layout_ja": "int32、三角形 × 3", "sha256": H.sha256(tp), "bytes": os.path.getsize(tp)},
                     "tri_attr": {"file": os.path.basename(ap_), "layout_ja": "uint16、三角形 × 2（指の番号、0 白・1 水色の版の側）", "sha256": H.sha256(ap_), "bytes": os.path.getsize(ap_)},
                     "vattr": {"file": os.path.basename(vp), "layout_ja": "float32、頂点 × 4（UV2.x 陰の段、UV2.y 根元 0 → 先 1、UV3.x 縁の線の位置（−1 線なし）、UV3.y 0）",
                               "sha256": H.sha256(vp), "bytes": os.path.getsize(vp)}},
           "vertex_order_ja": "指ごとにまとめた Houdini の鍵の形の頂点（帯の輪の並びではない）",
           "pl33r01h": {"note_ja": "仕上げ33修正01（Houdini の変種）：立つ白い爪の指。Houdini（VDB の滑らかな和）で t* の鍵の形を作り、指の中心線へ結び付けて全コマへ動かした。",
                        "key": a.key, "key_sha256": H.sha256(a.key + "/key_tstar_mesh.npz"), "ramps_sha256": H.sha256(a.key + "/ramps.json"),
                        "prep_sha256": H.sha256(a.prep + "/fingers_tstar.json"), "src_claws": H.SRC_CLAWS}}
    json.dump(lay, open(a.out + "/ds33_claw_layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    birth = np.argmax(sk_alive, axis=0)
    rep = {"vertices": int(nv), "triangles": int(len(tris)), "fingers": len(claws),
           "by_kind": {k: int(sum(1 for c in claws if c["kind"] == v)) for k, v in (("C", 0), ("S", 1), ("K_houdini", 2), ("W_pl33", 3), ("K_pl33", 4))},
           "err_stand_vs_houdini_m": err_P, "err_radius_vs_houdini_m": err_R, "err_key_frame_vs_houdini_mesh_m": err_key,
           "nan": nan, "jump_max_rel_root_m": jump_max, "jumps_over_0p25m": len(jumps), "jumps_top": sorted(jumps, reverse=True)[:20],
           "jumps_over_0p5m": int(sum(1 for j in jumps if j[0] > 0.5)), "frames_bytes": os.path.getsize(fp),
           "shade_white_frac": float((shade > 0.30).mean()), "padside_frac": float(padside.mean()),
           "webs": web_rep, "vertices_total": int(nv), "triangles_total": int(len(tris)),
           "birth_frame_pct": np.percentile(birth[sk_alive.any(0)], [0, 10, 50, 90, 100]).tolist(),
           "seconds": round(time.time() - t0, 1)}
    json.dump(rep, open(a.out + "/deform_report.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(json.dumps(rep, ensure_ascii=False))


if __name__ == "__main__":
    main()
