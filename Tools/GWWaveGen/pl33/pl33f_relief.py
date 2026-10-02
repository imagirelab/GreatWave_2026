# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：原画の爪の帯（仕上げ32 修正の回 1）を、面に沿う低い浮き彫りにし、帯の断面の向き・急な折れの幅・鉤の内の膜を直す（numpy）。

自己評審の指摘（作る部の pl33_ray_relief：帯の弧長 × 0.35、最大 0.8 m の立ち上げ）：
  - 座席・座席から波の方向・HMD の t* で、立ち上がった帯が唇で角の四角い線の箱に、藍の壁の上で浮いた白い三日月に見えた。
  - t 10.5 s の原画視点で、唇の下に淡い真っ直ぐな破片（牙）と、輪郭を越えて空へ出る長い鉤が出た。座席から波の方向で水色の小石・破片が散った。
    原因：立ち上げの向きは t* の原画の射線を根元の座標系で運んだもので、t* の前のコマでは射線と合わず、帯が原画視点で横へずれ、面から離れた。
  - 膜の輪の中心が面より 5 cm 以上下（t* 47 輪、最深 0.20 m）。

名前の付いた美術の誘導（どれも帯の頂点の並びだけで決まり、原画カメラからの投影の色は使わない。Q28）：
  - pl33f_low_relief（低い浮き彫り）：立ち上げを h(a) = H_REL × L × prof(a)（上限 H_MAX）× ρ(τ) にする。H_REL 0.12・H_MAX 0.22 m（作る部 0.35・0.8 m）、
    prof の先の戻り 0.75（先は面の近くへ戻る）。帯は面から最大 22 cm の低い浮き彫りで、指は面に沿って付いたまま。
  - pl33f_relief_ramp（立ち上げの時刻）：ρ(τ) = smoothstep((τ − τ_r)/(0 − τ_r))、τ_r = −0.6 s（t ≈ 10.3 s）。t* の前は帯がほぼ仕上げ32 の面に沿う位置
    （t 10.5 s で ρ = 0.16）で、t* へ向けてゆっくり浮く（最大 0.22 m を 1.7 s）。t* の射線の上の動きは t* でだけ正しいので、射線から外れるコマでは小さく保つ。
  - pl33f_section_turn（断面の向きの連続。計画 §5.3 の行 5・204）：t*（コマ 360）を基準に、コマの前後へ、輪の上面の向き（頂点 2 − 6）が
    隣のコマと逆（内積 < 0）になる輪を 180° 回す（頂点の番号を 4 つずらす。楕円の断面は左右対称なので形は同じ、白い上面が同じ側に残る）。
    同じコマの隣の輪の間でも、t* で決めた輪から根元・先の両側へ同じことをする。
  - pl33f_bend_width（急な折れの所の幅。計画 §5.3 の行 6）：t* で、帯の縁（頂点 0・4）の 1 歩が中心線の 1 歩と逆を向く（内側の縁の折れ返り）輪の組の
    幅を 0.85 倍ずつ（最小 0.45 倍）縮め、隣の輪へ半分を広げる。輪ごとの倍率は時刻によらない（全コマ同じ）。t* の原画視点では折れの内側の縁だけが細る。
  - 膜（pl33_hook_web の式のまま、帯の幅 × WEB_REL）：下げ dd = clip(0.5 h, 0.01, 0.12)。b区域は pl33f_tuft_web（WEB_REL_B 倍、既定 3.0。
    ［利用者の言葉］Q16・Q21：房の付け根の水色の塊）。
  - pl33f_web_floor（膜が面に入らない）：主役波の面の t 9〜14 s の 6 コマおき（＋t 10.5 s・t*）で、膜の輪の外の縁と中心の、近い頂点の法線の高さが
    −2 cm より下の輪の幅を 0.7 倍ずつ（最大 8 回）縮める（時刻によらない輪ごとの倍率。膜は帯の縁へ寄るので面の上へ戻る）。

入力（Git 対象外）：Unity/Build/Polish/32/fix01/claws。出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/fix01/relief）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_relief.py
"""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import pl33_common as Q  # noqa: E402
import ds31_white as W31  # noqa: E402
from pl33_claw_relief import root_frames, prof  # noqa: E402

U = Q.U
SRC = REPO + "/Unity/Build/Polish/32/fix01/claws"
OUT = REPO + "/Unity/Build/Polish/33/fix01/relief"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
K_STAR = 360
RING = 8
HZ = 30.0


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def taus_of(F):
    wt, wtau = W31.load_warp(Q.WARP)
    tk = np.arange(F) / HZ
    return np.where(tk >= 12.0 - 1e-9, 0.0, np.interp(tk, wt, wtau))


def section_turn(Rg):
    """Rg：(F, st, 8, 3) の輪。t* を基準に、コマの間と輪の間の上面の向きの裏返りを 180° 回して直す。返り値（直した輪、回した輪の数）。"""
    F, st = Rg.shape[:2]
    R = Rg.copy()
    n_turn = 0

    def up(A):
        return A[..., 2, :] - A[..., 6, :]

    def nz(v):
        return np.linalg.norm(v, axis=-1) > 1e-4
    # t* の中で、真ん中の輪から根元・先へ
    for f in [K_STAR]:
        u = up(R[f])
        mid = st // 2
        for j in list(range(mid + 1, st)) + list(range(mid - 1, -1, -1)):
            jn = j - 1 if j > mid else j + 1
            if nz(u[j]) and nz(u[jn]) and (u[j] @ u[jn]) < 0:
                R[f, j] = np.roll(R[f, j], 4, axis=0)
                u[j] = -u[j]
                n_turn += 1
    # コマの前後へ（同じ輪の前のコマの向きに合わせる）
    for rng_ in (range(K_STAR + 1, F), range(K_STAR - 1, -1, -1)):
        for f in rng_:
            fp = f - 1 if f > K_STAR else f + 1
            u = up(R[f]); up_ = up(R[fp])
            ok = nz(u) & nz(up_)
            bad = ok & ((u * up_).sum(-1) < 0)
            if bad.any():
                R[f, bad] = np.roll(R[f, bad], 4, axis=1)
                n_turn += int(bad.sum())
            # 前のコマで潰れていた輪は、同じコマの隣の輪に合わせる
            u = up(R[f])
            for j in range(1, st):
                if nz(u[j]) and nz(u[j - 1]) and not ok[j] and (u[j] @ u[j - 1]) < 0:
                    R[f, j] = np.roll(R[f, j], 4, axis=0)
                    u[j] = -u[j]
                    n_turn += 1
    return R, n_turn


def orient_clamp(Rg, max_deg=25.0):
    """pl33f_section_clamp：断面の上面の軸（頂点 2 − 6）の 1 コマの回りを max_deg 以下にする。t*（コマ 360）から前のコマへたどり、
    前のコマ（t* に近い側）の軸から max_deg を超えて回る輪は、その向きへ max_deg だけ回した軸に替え、輪の面（幅の軸 × 上面の軸）の中で
    幅の軸を作り直して輪を作り直す（楕円の輪：中心 ＋ 幅/2·cos φ·b ＋ 厚み/2·sin φ·n）。速い回りは数コマに分かれ、1 コマの跳びにならない。
    t* とその後は元のまま。返り値（直した輪、回りを抑えた輪×コマの数）。"""
    F, st = Rg.shape[:2]
    out = Rg.copy()
    ctr = Rg.mean(2)
    phi = 2 * np.pi * np.arange(RING) / RING
    cmax = np.cos(np.radians(max_deg))
    n_cl = 0
    for j in range(st):
        prev = None
        for f in range(K_STAR, -1, -1):
            R = out[f, j]
            b = R[0] - ctr[f, j]; n = R[2] - ctr[f, j]
            w = np.linalg.norm(b); th = np.linalg.norm(n)
            if w < 1e-5 or th < 1e-6:
                prev = None
                continue
            bu, nu = b / w, n / th
            if prev is not None and f < K_STAR:
                c = float(nu @ prev)
                if c < cmax:
                    T = np.cross(bu, nu); T /= max(np.linalg.norm(T), 1e-12)
                    ang = np.arccos(np.clip(c, -1, 1))
                    ax = nu - c * prev
                    ax /= max(np.linalg.norm(ax), 1e-12)
                    a = np.radians(max_deg)
                    n2 = np.cos(a) * prev + np.sin(a) * ax
                    n2 = n2 - (n2 @ T) * T
                    n2 /= max(np.linalg.norm(n2), 1e-12)
                    b2 = np.cross(n2, T)
                    out[f, j] = ctr[f, j] + (w * np.cos(phi))[:, None] * b2[None, :] + (th * np.sin(phi))[:, None] * n2[None, :]
                    nu = n2
                    n_cl += 1
            prev = nu
    return out, n_cl


def shape_blend(rings, tip, root, Rf, ok, keep_from=354, thr=0.03):
    """pl33f_shape_blend：帯の形（輪と先。根元の座標系で見た根元からの位置）の 1 コマの跳び（隣のコマの跳びの 3 倍より大きく 3 cm 超）を、
    跳びの前後 2〜3 コマ（f−2 → f+3）の形の間を smoothstep で移す 5 コマの移り変わりに替える（仕上げ32 の帯の、中心線が 1 コマで曲がり直す所。C021 のコマ 339 など）。
    根元の点と根元の円は動かさない。t* の付近（keep_from 以降）は変えない。返り値（輪、先、直した跳びの数）。"""
    F, st = rings.shape[:2]
    P = np.concatenate([rings.reshape(F, st * RING, 3), tip[:, None, :]], axis=1)
    Q = np.einsum("fji,fkj->fki", Rf, P - root[:, None, :])
    stp = np.linalg.norm(np.diff(Q, axis=0), axis=2).max(1)
    n_fix = 0
    for f in range(2, min(F - 4, keep_from - 4)):
        if not ok[f - 2:f + 4].all():
            continue
        nb = max(stp[f - 1], stp[f + 1])
        if stp[f] > thr and stp[f] > 3 * nb:
            for k in range(f - 1, f + 3):
                a = sm((k - (f - 2)) / 5.0)
                Q[k] = (1 - a) * Q[f - 2] + a * Q[f + 3]
            n_fix += 1
            stp = np.linalg.norm(np.diff(Q, axis=0), axis=2).max(1)
    if n_fix:
        P2 = root[:, None, :] + np.einsum("fij,fkj->fki", Rf, Q)
        rings = np.where(ok[:, None, None, None], P2[:, :st * RING].reshape(F, st, RING, 3), rings)
        tip = np.where(ok[:, None], P2[:, -1], tip)
    return rings, tip, n_fix


def onscreen_birth(rings, tip, root, Rf, ok, pcam, margin=20.0):
    """pl33f_onscreen_birth（計画 §5.3 の行 8：成長の時刻、画面の外で伸び始める爪）：原画視点の画面（1920×1080 の内側 margin px）の外で
    伸び始める爪は、根元が画面に入るコマ fe まで伸び始めを遅らせ、t* までの伸びを [fe, t*] に縮めて移す（根元の座標系で見た形を、
    g(f) = fb + (f − fe)(t* − fb)/(t* − fe) のコマの形から線形に補間）。根元の点と根元の円（泡の胴の付け根）は動かさない。返り値（輪、先、(fb, fe) または None）。"""
    F, st = rings.shape[:2]
    P = np.concatenate([rings.reshape(F, st * RING, 3), tip[:, None, :]], axis=1)
    ext = np.linalg.norm(P - root[:, None, :], axis=2).max(1)
    on = np.nonzero(ext > 1e-3)[0]
    if not len(on):
        return rings, tip, None
    fb = int(on[0])
    xy, z = pcam.project(root)
    ins = (z > 0) & (xy[:, 0] >= margin) & (xy[:, 0] < 1920 - margin) & (xy[:, 1] >= margin) & (xy[:, 1] < 1080 - margin)
    if ins[fb]:
        return rings, tip, None
    cand = np.nonzero(ins[fb:K_STAR])[0]
    if not len(cand):
        return rings, tip, None
    fe = fb + int(cand[0])
    if fe <= fb or not ok[fb:K_STAR + 1].all():
        return rings, tip, None
    Q = np.einsum("fji,fkj->fki", Rf, P - root[:, None, :])
    Q2 = Q.copy()
    for f in range(fb, K_STAR + 1):
        if f < fe:
            Q2[f] = 0.0
            continue
        g = fb + (f - fe) * (K_STAR - fb) / float(K_STAR - fe)
        g0 = int(np.floor(g)); a = g - g0
        g1 = min(g0 + 1, K_STAR)
        Q2[f] = (1 - a) * Q[g0] + a * Q[g1]
    P2 = root[:, None, :] + np.einsum("fij,fkj->fki", Rf, Q2)
    return P2[:, :st * RING].reshape(F, st, RING, 3), P2[:, -1], (fb, fe)


def bend_scale(Rk, ctr):
    """t* の輪 Rk（st, 8, 3）と中心 ctr（st, 3）。内側の縁の折れ返りがなくなるまで輪の幅の倍率（st,）を縮める。"""
    st = Rk.shape[0]
    sc = np.ones(st)
    for it in range(12):
        Rs = ctr[:, None, :] + sc[:, None, None] * (Rk - ctr[:, None, :])
        seg = np.diff(ctr, axis=0)
        bad = np.zeros(st - 1, bool)
        for e in (0, 4):
            es = np.diff(Rs[:, e], axis=0)
            bad |= (es * seg).sum(1) < 0
        if not bad.any():
            break
        for j in np.nonzero(bad)[0]:
            for k in (j, j + 1):
                sc[k] = max(0.45, sc[k] * 0.85)
            for k in (j - 1, j + 2):
                if 0 <= k < st:
                    sc[k] = max(0.45, sc[k] * 0.93)
    return sc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--h-rel", type=float, default=0.12)
    ap.add_argument("--h-max", type=float, default=0.22)
    ap.add_argument("--a-rise", type=float, default=0.45)
    ap.add_argument("--tip-drop", type=float, default=0.75)
    ap.add_argument("--tau-ramp", type=float, default=-0.6)
    ap.add_argument("--web-rel", type=float, default=1.0)
    ap.add_argument("--web-rel-b", type=float, default=3.0)
    ap.add_argument("--no-turn", action="store_true")
    ap.add_argument("--no-bend", action="store_true")
    ap.add_argument("--no-onscreen", action="store_true")
    a = ap.parse_args()
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    fr_path = os.path.join(a.src, lay["files"]["frames"]["file"])
    X = np.fromfile(fr_path, dtype=np.float32).reshape(F, V, 3).astype(np.float64)
    cam = np.array(json.load(open(TRUTH, encoding="utf-8"))["painting_cam"]["position"], dtype=np.float64)
    taus = taus_of(F)
    rho = sm((taus - a.tau_ramp) / (0.0 - a.tau_ramp))
    Y = X.copy()
    rowof = {c["id"]: c.get("row") for c in json.load(open(INV, encoding="utf-8"))["claws"]}
    hero = Q.U.K.Pkg(Q.HERO)
    dep = Q.TStarDepth(hero.world(0.0))
    per, webs = [], []
    tot_turn, n_bend, n_onscreen = 0, 0, 0
    # 膜の床の検査に使う主役波のコマ（t 9 s〜、6 コマおき＋t 10.5 s・t*）
    floor_frames = sorted(set(list(range(270, F, 6)) + [315, K_STAR]))
    sheets = {}
    for f in floor_frames:
        Xs = hero.world(float(taus[f]))
        dr = np.gradient(Xs, axis=0); dc = np.gradient(Xs, axis=1)
        nrm = np.cross(dr, dc); nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)
        Vf = Xs.reshape(-1, 3)
        sheets[f] = (cKDTree(Vf), Vf, nrm.reshape(-1, 3))
    print("sheets ready", round(time.time() - t0, 1), flush=True)
    for c in lay["claws"]:
        o, cnt, st = c["vert_offset"], c["vert_count"], c["stations"]
        ring_idx = o + 1 + np.arange(st * RING).reshape(st, RING)
        tip_i = o + 1 + st * RING
        cen_i = tip_i + 1
        circ_i = cen_i + 1 + np.arange(RING)
        root = X[:, o, :]
        rings = X[:, ring_idx, :]
        rec = {"id": c["id"], "type": c.get("type")}
        if not a.no_turn:
            rings, nt = section_turn(rings)
            tot_turn += nt
            rec["section_turns"] = nt
            rings, ncl = orient_clamp(rings)
            rec["section_clamped"] = ncl
        tip = X[:, tip_i, :]
        R, area = root_frames(X[:, cen_i, :], X[:, circ_i, :])
        ok = area > 1e-8
        if not a.no_turn:
            rings, tip, nfx = shape_blend(rings, tip, root, R, ok)
            rec["shape_blend_fixes"] = nfx
        if not a.no_onscreen:
            rings, tip, be = onscreen_birth(rings, tip, root, R, ok, dep.cam)
            if be is not None:
                rec["onscreen_birth_frames"] = list(be)
                n_onscreen += 1
        ctr = rings.mean(2)
        if not a.no_bend:
            bs = bend_scale(rings[K_STAR], ctr[K_STAR])
            if (bs < 0.999).any():
                n_bend += 1
                rec["bend_width_scale_min"] = round(float(bs.min()), 3)
            rings = ctr[:, :, None, :] + bs[None, :, None, None] * (rings - ctr[:, :, None, :])
        P = np.concatenate([root[:, None, :], ctr, tip[:, None, :]], axis=1)
        L = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
        Pk = P[K_STAR, 1:]
        d = cam[None, :] - Pk
        D = np.linalg.norm(d, axis=1)
        d /= D[:, None]
        if not ok[K_STAR]:
            Y[:, ring_idx, :] = rings
            Y[:, tip_i, :] = tip
            rec["skipped_ja"] = "t* で根元の円が潰れている（立ち上げなし、断面の向きと幅だけ直した）"
            per.append(rec)
            continue
        dl = d @ R[K_STAR]
        dirs = np.einsum("fij,kj->fki", R, dl)
        av = np.concatenate([np.linspace(0, 1, st), [1.0]])
        pr = prof(av, a.a_rise, a.tip_drop)
        h = np.minimum(a.h_rel * L[:, None] * pr[None, :], a.h_max) * rho[:, None]
        h[~ok] = 0.0
        off = h[:, :, None] * dirs
        kscale = 1.0 - h[:, :st] / D[None, :st]
        Yr = ctr[:, :, None, :] + kscale[:, :, None, None] * (rings - ctr[:, :, None, :]) + off[:, :st, None, :]
        Y[:, ring_idx, :] = Yr
        Y[:, tip_i, :] = tip + off[:, st, :]
        rec.update({"L_tstar_m": round(float(L[K_STAR]), 4), "h_max_tstar_m": round(float(h[K_STAR].max()), 4)})
        wrel = a.web_rel_b if rowof.get(c["id"]) == "b区域" else a.web_rel
        wv, info = hook_web_f(Y[:, o, :], Yr, h[:, :st], dep, wrel, st, sheets)
        info["web_rel"] = wrel
        info["row"] = rowof.get(c["id"])
        if wv is not None:
            # 膜も同じ規則で 1 コマの跳びを移り変わりに替える（親の帯の速い回りが膜の幅で大きくなるため。閾値 5 cm）
            wr = wv[:, 1:1 + st * RING].reshape(F, st, RING, 3)
            wr, wt_, nfw = shape_blend(wr, wv[:, 1 + st * RING], wv[:, 0], R, ok, thr=0.05)
            wv[:, 1:1 + st * RING] = wr.reshape(F, st * RING, 3)
            wv[:, 1 + st * RING] = wt_
            info["shape_blend_fixes"] = nfw
            webs.append((c, wv))
        rec["web"] = info
        per.append(rec)
    print("claws done", round(time.time() - t0, 1), flush=True)
    os.makedirs(a.out, exist_ok=True)
    for k, v in lay["files"].items():
        if k != "frames":
            shutil.copyfile(os.path.join(a.src, v["file"]), os.path.join(a.out, v["file"]))
    out_fr = os.path.join(a.out, lay["files"]["frames"]["file"])
    nbase = len(lay["claws"])
    tris = [np.fromfile(os.path.join(a.src, lay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)]
    att = [np.fromfile(os.path.join(a.src, lay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)]
    sk = np.fromfile(os.path.join(a.src, lay["files"]["skel"]["file"]), dtype=np.float32).reshape(F, nbase, 36)
    off_v = V
    add = []
    for i, (c, wv) in enumerate(webs):
        nv = wv.shape[1]
        Tt, kd = Q.layout_tris(c["stations"], off_v)
        tris.append(Tt.astype(np.int32))
        att.append(np.stack([np.full(len(kd), nbase + i), np.ones(len(kd), np.int64)], 1).astype(np.uint16))
        lay["claws"].append({"id": "W" + c["id"], "index": nbase + i, "vert_offset": off_v, "vert_count": nv, "stations": c["stations"],
                             "type": "W", "pl33_web_of": c["id"]})
        add.append(wv.astype(np.float32))
        off_v += nv
    Yall = np.concatenate([Y.astype(np.float32)] + add, axis=1)
    T_all = np.concatenate(tris)
    A_all = np.concatenate(att)
    T_all.tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
    A_all.tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
    np.concatenate([sk, np.zeros((F, len(webs), 36), np.float32)], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
    Yall.tofile(out_fr)
    lay["vertices"] = off_v
    lay["triangles"] = int(len(T_all))
    for k in ("frames", "tris", "tri_attr", "skel"):
        pth = os.path.join(a.out, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = Q.sha(pth)
        lay["files"][k]["bytes"] = os.path.getsize(pth)
    lay["pl33_relief"] = {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33/pl33f_relief.py", "src": os.path.relpath(a.src, REPO).replace("\\", "/"),
                          "src_frames_sha256": Q.sha(fr_path), "h_rel": a.h_rel, "h_max_m": a.h_max, "a_rise": a.a_rise, "tip_drop": a.tip_drop,
                          "tau_ramp_s": a.tau_ramp, "k_star": K_STAR, "camera": cam.tolist(), "web_rel": a.web_rel, "web_rel_b": a.web_rel_b,
                          "webs": len(webs), "section_turn": not a.no_turn, "bend_width": not a.no_bend}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # t* の投影の変化（輪の中心と先）
    spec = json.load(open(TRUTH, encoding="utf-8"))["painting_cam"]
    xy1, _ = dep.cam.project(Y[K_STAR, :V])
    xy0, _ = dep.cam.project(X[K_STAR])
    dpx = np.linalg.norm(xy1 - xy0, axis=1)
    hs = np.array([p["h_max_tstar_m"] for p in per if "h_max_tstar_m" in p])
    summ = {"claws": len(per), "tstar_projection_shift_px_max": round(float(np.nanmax(dpx)), 4), "tstar_projection_shift_px_p99": round(float(np.nanpercentile(dpx, 99)), 4),
            "tstar_relief_m": {"min": round(float(hs.min()), 3), "median": round(float(np.median(hs)), 3), "max": round(float(hs.max()), 3)},
            "rho_at_t9_t105_t11": [round(float(rho[270]), 3), round(float(rho[315]), 3), round(float(rho[330]), 3)],
            "section_turns_total": tot_turn, "shape_blend_fixes_total": int(sum(p.get("shape_blend_fixes", 0) for p in per)), "claws_bend_width_scaled": n_bend, "claws_onscreen_birth_delayed": n_onscreen, "webs": len(webs),
            "web_rings_floor_shrunk": int(sum(p.get("web", {}).get("floor_rings_shrunk", 0) for p in per)),
            "painting_cam": spec["position"], "elapsed_s": round(time.time() - t0, 1)}
    json.dump({"summary": summ, "claws": per}, open(os.path.join(a.out, "pl33f_relief_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False))


def hook_web_f(root, Yr, hr, dep, web_rel, st, sheets):
    """pl33_claw_relief.hook_web と同じ膜（巻きの内側、帯の下）に、下げの範囲の変更と pl33f_web_floor を足したもの。"""
    F = Yr.shape[0]
    cY = Yr.mean(2)
    E0, E4 = Yr[:, :, 0], Yr[:, :, 4]
    Nn = Yr[:, :, 2] - Yr[:, :, 6]
    Nn = Nn / np.maximum(np.linalg.norm(Nn, axis=2, keepdims=True), 1e-12)
    w = np.linalg.norm(E0 - E4, axis=2)
    xy, _ = dep.cam.project(cY[K_STAR])
    b2, _ = dep.cam.project(E0[K_STAR])
    dd2 = np.diff(xy, axis=0)
    if len(dd2) < 3 or not np.all(np.isfinite(xy)):
        return None, {"made": False, "why_ja": "t* の中心線が短い"}
    turn = float(np.sum(dd2[:-1, 0] * dd2[1:, 1] - dd2[:-1, 1] * dd2[1:, 0]))
    mid = len(dd2) // 2
    bvec = b2[mid] - xy[mid]
    side = float(dd2[mid, 0] * bvec[1] - dd2[mid, 1] * bvec[0])
    use0 = (turn > 0) == (side > 0)
    E = E0 if use0 else E4
    lat = E - cY
    lat = lat / np.maximum(np.linalg.norm(lat, axis=2, keepdims=True), 1e-12)
    av = np.linspace(0, 1, st)
    pw = Q.sm(av / 0.25) * (1.0 - 0.6 * Q.sm((av - 0.6) / 0.4))
    ww = web_rel * w * pw[None, :]
    dd = np.clip(0.5 * hr, 0.05, 0.12)

    def edges_at(f, scv):
        P1k = E[f] - (0.03 * scv)[:, None] * Nn[f]
        P2k = E[f] + (ww[f] * scv)[:, None] * lat[f] - (dd[f] * scv)[:, None] * Nn[f]
        return P1k, P2k
    sc = np.where(dep.inside(E[K_STAR]), 1.0, 0.0)
    for it in range(10):
        P1k, P2k = edges_at(K_STAR, sc)
        ins = dep.inside(P1k) & dep.inside(P2k)
        if ins.all():
            break
        sc = np.where(ins, sc, sc * 0.7)
    P1k, P2k = edges_at(K_STAR, sc)
    sc = np.where(dep.inside(P1k) & dep.inside(P2k), sc, 0.0)
    sc = np.minimum(sc, np.minimum(np.r_[sc[1:], sc[-1]], np.r_[sc[0], sc[:-1]]))
    # pl33f_web_floor
    sc0 = sc.copy()
    for f, (tree, Vf, nrm) in sheets.items():
        if np.linalg.norm(cY[f, -1] - cY[f, 0]) < 1e-3:
            continue
        for it in range(8):
            P1k, P2k = edges_at(f, sc)
            Mk = 0.5 * (P1k + P2k)
            low = np.zeros(st, bool)
            for Pq in (P2k, Mk):
                _, ii = tree.query(Pq)
                e = Pq - Vf[ii]
                hh = (e * nrm[ii]).sum(1)
                tang = np.linalg.norm(e - hh[:, None] * nrm[ii], axis=1)
                low |= (hh < -0.02) & (tang < 0.3)
            low &= sc > 1e-6
            if not low.any():
                break
            sc = np.where(low, sc * 0.7, sc)
    sc = np.minimum(sc, np.minimum(np.r_[sc[1:], sc[-1]], np.r_[sc[0], sc[:-1]]))
    P1 = E - (0.03 * sc)[None, :, None] * Nn
    P2 = E + (ww * sc[None, :])[:, :, None] * lat - (dd * sc[None, :])[:, :, None] * Nn
    M = 0.5 * (P1 + P2)
    A = 0.5 * (P2 - P1)
    phi = 2 * np.pi * np.arange(RING) / RING
    ring = M[:, :, None, :] + np.cos(phi)[None, None, :, None] * A[:, :, None, :] + np.sin(phi)[None, None, :, None] * (0.004 * Nn)[:, :, None, :]
    out = np.empty((F, RING * st + 11, 3))
    out[:, 0] = root
    out[:, 1:1 + st * RING] = ring.reshape(F, st * RING, 3)
    out[:, 1 + st * RING] = M[:, -1]
    out[:, 2 + st * RING:] = root[:, None, :]
    info = {"made": True, "inner_edge": "phi0" if use0 else "phi180", "width_scale_min": round(float(sc.min()), 3),
            "rings_shrunk": int((sc < 0.999).sum()), "floor_rings_shrunk": int((sc < sc0 - 1e-9).sum()),
            "width_tstar_m_max": round(float((ww[K_STAR] * sc).max()), 3)}
    return out, info


if __name__ == "__main__":
    main()
