# -*- coding: utf-8 -*-
"""設計33（爪の部）：爪の帯のメッシュを全コマ（30 Hz × 421）で作り、受入の検査をする（numpy。Unity の描画ではない）。

入力：ds33_claw_rig.json・ds33_claw_rig.npz（ds33_claw_rig.py）、主役波のパッケージ（31/white/hero_pkg）、時間曲線 timewarp_F_final.json。
コマ k：t = k/30 s、τ = τ(t)（設計32 と同じ線形補間）。t ≥ 12 s は τ = 0（t* の保持）。
爪ごと：s = (τ − τ_start)/(0 − τ_start)（τ_start は根元の T_white、支は主爪が支の根元まで伸びた時）。s の成長の段の間を線形に補間した
  関節の結び付け（参照のシートの (行, 列) と、その点の局所の座標系 [e1 e2 n] でのずれ）から、そのコマのシートで関節を作り直す
  （= キーごと・コマごとに接線の座標系を作り直す）。根元の関節は設計32 の sheet_rc の、描画と同じ三角形の上の点（ずれ 0）。
帯：関節を通る centripetal Catmull-Rom を弧長で n_st 個の輪（8 頂点、扁平な楕円）と先端の 1 点に取り直す。両端の関節がシートに付く区間の輪の中心は、
  そのコマのシートへ射影して面の上へ載せ直す（面に沿う帯。関節の間で面がふくらんで帯が埋まるのを防ぐ）。輪の幅 = 型の幅 × ω(s)、
  厚み = 型の比 × 幅。輪の中心は骨格の線から法線の向きに厚みの 0.25 だけ上（下の縁は厚みの 0.25 だけシートに沈む）。
  法線：シートの上の爪は面の法線、空へ出る爪は t* で PaintingCam を向く面（参照の座標系で持つ）。
  根元の白の円（web への継ぎ）：根元のまわりのシートの (行, 列) の 8 点 ＋ 中心（面から 4 mm 上、半径は幅 × ω）。
頂点の並び（爪ごと）：根元の点 1、輪 n_st × 8、先端 1、円の中心 1、円 8。
出力（Git 対象外、Unity/Build/Design/33/claws/）：
  ds33_claw_frames_f32.bin（コマ × 全頂点 × 3、ワールドの m。見えないコマは根元の点に潰す）、ds33_claw_tris_i32.bin（三角形 × 3）、
  ds33_claw_tri_attr_u16.bin（三角形 × 2：爪の番号、面の種類 0 上面（φ 45〜135°、白）・1 縁の側面と下面（淡い水色）・2 根元の白の円）、
  ds33_claw_skel_f32.bin（コマ × 爪 × 36：関節 5 × xyz、関節の法線 5 × xyz、s、g、κ、ω、見える、弧長 m）、ds33_claw_layout.json、
  ds33_claw_checks.json（105・137・139・頂点数・瞬間移動・t* の再投影・web への継ぎ）。
"""
import argparse
import math
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ds33_common as U  # noqa: E402
import ds33_claw_rig as G  # noqa: E402

K = U.K
RING = 8
PHI = 2 * np.pi * np.arange(RING) / RING


def layout_tris(n_st, base):
    """爪 1 本の三角形（頂点の番号は base から）と面の種類。"""
    root = base
    ring = lambda j, i: base + 1 + j * RING + (i % RING)  # noqa: E731
    tip = base + 1 + n_st * RING
    skc = tip + 1
    sk = lambda i: skc + 1 + (i % RING)  # noqa: E731
    T, kind = [], []
    up = lambda i: 0 if (i % RING) in (1, 2) else 1  # noqa: E731   φ が 45〜135° の間（上面）が白、縁の側面と下面は淡い水色
    for i in range(RING):
        T.append((root, ring(0, i + 1), ring(0, i))); kind.append(1)
    for j in range(n_st - 1):
        for i in range(RING):
            T.append((ring(j, i), ring(j, i + 1), ring(j + 1, i + 1))); kind.append(up(i))
            T.append((ring(j, i), ring(j + 1, i + 1), ring(j + 1, i))); kind.append(up(i))
    for i in range(RING):
        T.append((ring(n_st - 1, i), ring(n_st - 1, i + 1), tip)); kind.append(up(i))
    for i in range(RING):
        T.append((skc, sk(i), sk(i + 1))); kind.append(2)
    return np.array(T, np.int64), np.array(kind, np.int64)


def sweep(J, N, w, th, n_st, cfrac, snap=None):
    """関節 J（m×3）と関節の法線 N を通る帯の輪と先端。snap(St, Ns, 区間, 区間の中の位置) は、シートに付く区間の輪の中心を面へ載せ直す。
    戻り値：輪の頂点（n_st×8×3）、先端、弧長、局所の軸。"""
    Pd, par = U.catmull_rom(J, 16)
    St, sfrac, L = U.resample_arc(Pd, n_st + 1)
    nj = len(J)
    seg = np.clip(np.floor(par).astype(int), 0, nj - 2)
    fr = np.clip(par - seg, 0, 1)
    Nd = N[seg] * (1 - fr)[:, None] + N[seg + 1] * fr[:, None]
    tq = np.linspace(0, 1, n_st + 1)
    Ns = np.stack([np.interp(tq, sfrac, Nd[:, k]) for k in range(3)], -1)
    if snap is not None:
        spar = np.interp(tq, sfrac, par)
        sseg = np.clip(np.floor(spar).astype(int), 0, nj - 2)
        sfr = np.clip(spar - sseg, 0, 1)
        St, Ns = snap(St, Ns, sseg, sfr)
        L = float(np.linalg.norm(np.diff(St, axis=0), axis=1).sum())
    T = np.gradient(St, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    B = np.cross(Ns, T)
    B /= np.maximum(np.linalg.norm(B, axis=1, keepdims=True), 1e-12)
    Nn = np.cross(T, B)
    hw = 0.5 * w[:, None]
    ctr = cfrac * th[:, None]
    ring = (St[:n_st, None, :] + B[:n_st, None, :] * (hw * np.cos(PHI)[None, :])[..., None]
            + Nn[:n_st, None, :] * (ctr + 0.5 * th[:, None] * np.sin(PHI)[None, :])[..., None])
    return ring, St[n_st], L, (T, B, Nn, St)


def point_tri_dist(p, A, B, C):
    """点 p（n×3）と三角形（n×m×3）の距離（n×m）。"""
    p = p[:, None, :]
    ab, ac, ap = B - A, C - A, p - A
    d1 = (ab * ap).sum(-1); d2 = (ac * ap).sum(-1)
    n = np.cross(ab, ac)
    nn = np.maximum((n * n).sum(-1), 1e-30)
    # 面の上への射影が三角形の中なら面との距離、外なら 3 辺との距離の最小
    t = (n * ap).sum(-1) / nn
    q = p - t[..., None] * n
    v0, v1, v2 = ac, ab, q - A
    d00 = (v0 * v0).sum(-1); d01 = (v0 * v1).sum(-1); d11 = (v1 * v1).sum(-1); d20 = (v2 * v0).sum(-1); d21 = (v2 * v1).sum(-1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
    u = (d11 * d20 - d01 * d21) / den
    v = (d00 * d21 - d01 * d20) / den
    inside = (u >= 0) & (v >= 0) & (u + v <= 1)
    dplane = np.abs(t) * np.sqrt(nn)

    def seg(P0, P1):
        e = P1 - P0
        tt = np.clip(((p - P0) * e).sum(-1) / np.maximum((e * e).sum(-1), 1e-30), 0, 1)
        return np.linalg.norm(p - (P0 + tt[..., None] * e), axis=-1)
    dedge = np.minimum(np.minimum(seg(A, B), seg(B, C)), seg(C, A))
    return np.where(inside, dplane, dedge)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=U.OUT)
    a = ap.parse_args()
    t0 = time.time()
    rig = U.jload(os.path.join(a.out, "ds33_claw_rig.json"))
    Z = np.load(os.path.join(a.out, "ds33_claw_rig.npz"))
    svals = Z["svals"]
    Ms = len(svals)
    P = rig["params"]
    cfrac = P["band_center_frac"]
    lift = P["skirt"]["lift_m"]
    claws = rig["claws"]
    nc = len(claws)
    hero = K.Pkg(U.HERO)
    R, C = hero.R, hero.C
    warp = U.jload(U.WARP)
    taus = np.interp(np.arange(U.NFR) / U.FPS, np.array(warp["t"]), np.array(warp["tau"]))
    spec = U.jload(U.TRUTH)
    cam = U.C27.Cam(spec)
    # 頂点・三角形の並び
    offs, tris, attr = [], [], []
    nv = 0
    for i, c in enumerate(claws):
        n_st = c["stations"]
        T, kd = layout_tris(n_st, nv)
        tris.append(T); attr.append(np.stack([np.full(len(T), i), kd], 1))
        offs.append((nv, c["n_vert"]))
        assert c["n_vert"] == 1 + n_st * RING + 1 + 1 + RING
        nv += c["n_vert"]
    tris = np.concatenate(tris); attr = np.concatenate(attr)
    V = np.zeros((U.NFR, nv, 3), np.float32)
    SK = np.zeros((U.NFR, nc, 36), np.float32)
    rc0 = np.array([c["sheet_rc"] for c in claws], np.float64)
    tau_s = np.array([c["tau_start"] for c in claws])
    data = []
    for c in claws:
        cid = c["id"]
        data.append(dict(RC=Z["RC_" + cid], E=Z["E_" + cid], NL=Z["NL_" + cid], W=Z["W_" + cid], TH=Z["TH_" + cid], SK=Z["SK_" + cid],
                         ref=np.array(c["joint_ref"]), n_st=c["stations"], bound=np.array([k == "sheet" for k in c["joint_kind"]]),
                         hanging=c["hanging"]))
    area = np.zeros((U.NFR, nc))
    arcl = np.zeros((U.NFR, nc))
    nan_count = 0
    Xprev = None
    dsheet = np.zeros(U.NFR)
    for f, tau in enumerate(taus):
        X = hero.world(float(tau))
        if Xprev is not None:
            dsheet[f] = float(np.linalg.norm(X[:, U.BODY[0]:U.BODY[1] + 1] - Xprev[:, U.BODY[0]:U.BODY[1] + 1], axis=-1).max())
        Xprev = X
        s_all = np.clip((tau - tau_s) / (0.0 - tau_s), 0.0, 1.0)
        vis = tau >= tau_s
        g_all, k_all, w_all = G.growth_curves(s_all)
        for i, c in enumerate(claws):
            d = data[i]
            o, n = offs[i]
            root = U.tri_eval(X, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
            if not vis[i]:
                V[f, o:o + n] = root
                SK[f, i, 34] = 0.0
                continue
            m = s_all[i] * (Ms - 1)
            m0 = int(min(math.floor(m), Ms - 2)); fm = m - m0
            RCs = d["RC"][m0] * (1 - fm) + d["RC"][m0 + 1] * fm       # nj × 2
            Es = d["E"][m0] * (1 - fm) + d["E"][m0 + 1] * fm
            RCs[0] = rc0[i]
            ref = d["ref"]
            rr, cc = RCs[ref, 0], RCs[ref, 1]
            S = U.tri_eval(X, rr, cc)
            F = U.frame_at(X, rr, cc)                                  # nj × 3 × 3（行が基底）
            J = S + np.einsum("kji,kj->ki", F, Es)
            J[0] = root
            Nj = np.einsum("kji,kj->ki", F, d["NL"])
            kb = d["bound"]

            def snap(St, Ns, sseg, sfr, X=X, RCs=RCs, kb=kb, hang=d["hanging"]):
                sel = kb[sseg] & kb[sseg + 1]
                sel[0] = False
                if not sel.any():
                    return St, Ns
                rc_i = RCs[sseg[sel]] * (1 - sfr[sel])[:, None] + RCs[sseg[sel] + 1] * sfr[sel][:, None]
                r_, c_, _, _ = U.project_to_sheet(X, St[sel], rc_i, iters=8, max_step=2.0)
                St = St.copy(); Ns = Ns.copy()
                St[sel] = U.tri_eval(X, r_, c_)
                if not hang:
                    Ns[sel] = U.normal_at(X, r_, c_)
                return St, Ns
            ring, tip, L, _ = sweep(J, Nj, d["W"] * w_all[i], d["TH"] * w_all[i], d["n_st"], cfrac, snap)
            # 根元の白の円
            drc = d["SK"] * w_all[i]
            rcs = rc0[i][None, :] + drc
            rcs[:, 0] = np.clip(rcs[:, 0], 0, R - 1); rcs[:, 1] = np.clip(rcs[:, 1], 0, C - 1)
            skp = U.tri_eval(X, rcs[:, 0], rcs[:, 1]) + lift * U.normal_at(X, rcs[:, 0], rcs[:, 1])
            vv = np.concatenate([root[None, :], ring.reshape(-1, 3), tip[None, :], skp], 0)
            if not np.all(np.isfinite(vv)):
                nan_count += 1
            V[f, o:o + n] = vv
            nj = len(J)
            SK[f, i, 0:3 * nj] = J.ravel()
            SK[f, i, 15:15 + 3 * nj] = Nj.ravel()
            SK[f, i, 30:36] = [s_all[i], g_all[i], k_all[i], w_all[i], 1.0, L]
            arcl[f, i] = L
        if f % 60 == 0:
            print("frame %d  %.1fs" % (f, time.time() - t0), flush=True)
    # 三角形の面積（爪ごと）
    for f in range(U.NFR):
        Vf = V[f].astype(np.float64)
        ar = 0.5 * np.linalg.norm(np.cross(Vf[tris[:, 1]] - Vf[tris[:, 0]], Vf[tris[:, 2]] - Vf[tris[:, 0]]), axis=1)
        area[f] = np.bincount(attr[:, 0], weights=ar * (attr[:, 1] != 2), minlength=nc)
    print("mesh %.1fs" % (time.time() - t0), flush=True)

    # ---------------------------------------------------------------- 書き出し
    V.tofile(os.path.join(a.out, "ds33_claw_frames_f32.bin"))
    tris.astype(np.int32).tofile(os.path.join(a.out, "ds33_claw_tris_i32.bin"))
    attr.astype(np.uint16).tofile(os.path.join(a.out, "ds33_claw_tri_attr_u16.bin"))
    SK.tofile(os.path.join(a.out, "ds33_claw_skel_f32.bin"))
    lay = dict(schema="GreatWave.DS33.claw_layout/1", frames=U.NFR, hz=U.FPS, vertices=int(nv), triangles=int(len(tris)),
               clock_ja="コマ k は t = k/30 s、τ = τ(t)（timewarp_F_final.json の線形補間）。t ≥ 12 s は τ = 0",
               timewarp=dict(path=U.rel(U.WARP), sha256=U.sha(U.WARP)),
               claws=[dict(id=c["id"], index=i, vert_offset=offs[i][0], vert_count=offs[i][1], stations=c["stations"], type=c["type"])
                      for i, c in enumerate(claws)],
               files=dict(frames=dict(file="ds33_claw_frames_f32.bin", layout_ja="float32、コマ × 頂点 × 3（ワールドの m）"),
                          tris=dict(file="ds33_claw_tris_i32.bin", layout_ja="int32、三角形 × 3（頂点の番号）"),
                          tri_attr=dict(file="ds33_claw_tri_attr_u16.bin", layout_ja="uint16、三角形 × 2（爪の番号、面の種類 0 上面（φ 45〜135°）・白、1 縁の側面と下面・淡い水色、2 根元の白の円）"),
                          skel=dict(file="ds33_claw_skel_f32.bin", layout_ja="float32、コマ × 爪 × 36（関節 5 × xyz（4 関節の爪は 5 番目が 0）、関節の法線 5 × xyz、s、g、κ、ω、見える 0/1、帯の弧長 m）")),
               vertex_order_ja="爪ごと：根元の点 1（シートの上、描画の三角形の上の点）、輪 stations × 8（φ = 0, 45, …, 315°。φ 90° が上＝法線の向き、φ 0° が B＝N×T の向き）、先端 1、根元の白の円の中心 1、円 8")
    for k in ("frames", "tris", "tri_attr", "skel"):
        pth = os.path.join(a.out, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = U.sha(pth); lay["files"][k]["bytes"] = os.path.getsize(pth)
    U.jdump(os.path.join(a.out, "ds33_claw_layout.json"), lay)
    print("written %.1fs" % (time.time() - t0), flush=True)

    # ---------------------------------------------------------------- 検査
    visM = SK[:, :, 34] > 0.5
    ids = [c["id"] for c in claws]
    # 105：根元の点と、そのコマのシートの三角形（根元のセルと周りの 8 セル）との距離
    d105 = np.zeros((U.NFR, nc))
    s137 = np.zeros((U.NFR, nc))
    prc137 = np.zeros((U.NFR, nc))
    rr0 = np.clip(np.floor(rc0[:, 0]).astype(int), 0, R - 2); cc0 = np.clip(np.floor(rc0[:, 1]).astype(int), 0, C - 2)
    cells = []
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            cells.append((np.clip(rr0 + dr, 0, R - 2), np.clip(cc0 + dc, 0, C - 2)))
    rootv = np.array([o for o, _ in offs])
    for f, tau in enumerate(taus):
        X = hero.world(float(tau))
        p = V[f, rootv].astype(np.float64)
        As, Bs, Cs = [], [], []
        for (r_, c_) in cells:
            a_, b_, cc_, d_ = X[r_, c_], X[r_ + 1, c_], X[r_, c_ + 1], X[r_ + 1, c_ + 1]
            As += [a_, cc_]; Bs += [b_, b_]; Cs += [cc_, d_]
        A3 = np.stack(As, 1); B3 = np.stack(Bs, 1); C3 = np.stack(Cs, 1)
        d105[f] = point_tri_dist(p, A3, B3, C3).min(1)
        # 137：根元の点がそのコマで乗っている三角形と重心座標から (行, 列) を読み直す（材料の座標）。生まれたコマの値との差を滑りとする
        rcf = np.full((nc, 2), np.nan)
        best = np.full(nc, np.inf)
        for q, (r_, c_) in enumerate(cells):
            for half in (0, 1):
                A_ = A3[:, 2 * q + half]; B_ = B3[:, 2 * q + half]; C_ = C3[:, 2 * q + half]
                e1, e2 = B_ - A_, C_ - A_
                nrm = np.cross(e1, e2)
                nn = np.maximum((nrm * nrm).sum(1), 1e-30)
                w_ = p - A_
                dpl = np.abs((w_ * nrm).sum(1)) / np.sqrt(nn)
                d00 = (e1 * e1).sum(1); d01 = (e1 * e2).sum(1); d11 = (e2 * e2).sum(1); d20 = (w_ * e1).sum(1); d21 = (w_ * e2).sum(1)
                den = np.maximum(d00 * d11 - d01 * d01, 1e-30)
                u_ = (d11 * d20 - d01 * d21) / den
                v_ = (d00 * d21 - d01 * d20) / den
                out = np.maximum.reduce([-u_, -v_, u_ + v_ - 1, np.zeros_like(u_)])
                score = dpl + out * 10.0
                better = score < best
                if half == 0:
                    rr_, ccc = r_ + u_, c_ + v_
                else:
                    rr_, ccc = r_ + u_ + v_, c_ + 1 - u_
                rcf[better] = np.stack([rr_, ccc], 1)[better]
                best[better] = score[better]
        prc137[f] = np.hypot(rcf[:, 0] - rc0[:, 0], rcf[:, 1] - rc0[:, 1])
        s137[f] = np.linalg.norm(U.tri_eval(X, rcf[:, 0], rcf[:, 1]) - U.tri_eval(X, rc0[:, 0], rc0[:, 1]), axis=1)
    d105v = np.where(visM, d105, 0.0)
    s137v = np.where(visM, s137, 0.0)
    # 139：成長の途中の欠落
    first = np.array([int(np.argmax(visM[:, i])) if visM[:, i].any() else -1 for i in range(nc)])
    gaps = [ids[i] for i in range(nc) if first[i] >= 0 and not visM[first[i]:, i].all()]
    never = [ids[i] for i in range(nc) if first[i] < 0]
    mono = {}
    for j, nm in ((30, "s"), (31, "g"), (32, "kappa"), (33, "omega")):
        x = SK[:, :, j]
        dec = (np.diff(x, axis=0) < -1e-6) & visM[1:] & visM[:-1]
        mono[nm] = int(dec.sum())
    zero_area = int(((area <= 1e-8) & visM).sum())
    arc_dec = (np.diff(arcl, axis=0) < -0.01 * np.maximum(arcl[:-1], 1e-6)) & visM[1:] & visM[:-1]
    # 瞬間移動（設計32 と同じ読み）：爪の頂点のコマの間の動きの最大 ≤ シートの頂点の動きの最大 × 1.5 + 2 cm ＋ 成長の分
    mv = np.zeros((U.NFR, nc))
    for f in range(1, U.NFR):
        dd = np.linalg.norm(V[f].astype(np.float64) - V[f - 1].astype(np.float64), axis=1)
        mv[f] = np.maximum.reduceat(dd, rootv)
    both = visM[1:] & visM[:-1]
    # 成長で頂点が伸びる分：弧長の増え ＋ 幅の増え（コマの間）
    grow = np.abs(np.diff(arcl, axis=0)) + np.array([np.abs(np.diff(SK[:, i, 33])) * float(np.max(data[i]["W"])) for i in range(nc)]).T
    bound_f = dsheet[1:, None] * 1.5 + 0.02 + 2.0 * grow
    tele = [(ids[i], int(f + 1), float(mv[f + 1, i]), float(bound_f[f, i])) for f, i in zip(*np.nonzero(both & (mv[1:] > bound_f)))]
    # t* の再投影（記録のみ、4 px）
    inv = U.jload(U.D32 + "/ds32_claw_inventory.json")
    byid = {c["id"]: c for c in inv["claws"]}
    rep = []
    Vt = V[-1].astype(np.float64)
    for i, c in enumerate(claws):
        nj = c["segments"] + 1
        J = SK[-1, i, 0:3 * nj].reshape(nj, 3).astype(np.float64)
        Pd, _ = U.catmull_rom(J, 16)
        q, _ = cam.project(Pd)
        cl = U.to_disp(np.asarray(byid[c["id"]]["centerline_ref"], np.float64))
        clr, _ = G.resample2(cl, 0.5)
        qq, _ = G.resample2(q, 0.5)
        dA = np.sqrt(((clr[:, None, :] - qq[None, :, :]) ** 2).sum(-1))
        h1, h2 = dA.min(1), dA.min(0)
        rq, _ = cam.project(Vt[offs[i][0]])
        rep.append(dict(id=c["id"], type=c["type"], row=c["row"], hausdorff_px=round(float(max(h1.max(), h2.max())), 3),
                        p95_px=round(float(np.percentile(np.r_[h1, h2], 95)), 3),
                        root_px=round(float(np.hypot(*(rq - np.asarray(byid[c["id"]]["root_display"])))), 3),
                        tip_px=round(float(np.hypot(*(q[-1] - np.asarray(byid[c["id"]]["tip_display"])))), 3)))
    hd = np.array([r["hausdorff_px"] for r in rep]); p95 = np.array([r["p95_px"] for r in rep])
    # web への継ぎ：根元の頂点の t* の色区と、最も近い白の頂点までの距離
    vcls, _ = U.W31.vertex_class(R, C)
    vcls = vcls.reshape(R, C)
    X0 = hero.world(0.0)
    tw = np.fromfile(U.HERO + "/" + hero.k["twhite_file"], "<f4").reshape(R, C)
    whiteV = X0[vcls == 0]
    names = {0: "白", 1: "淡い水色", 2: "藍中", 3: "藍濃"}
    web = []
    for i, c in enumerate(claws):
        r_, c_ = int(round(rc0[i, 0])), int(round(rc0[i, 1]))
        pr = U.tri_eval(X0, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
        dW = float(np.sqrt(((whiteV - pr) ** 2).sum(1)).min())
        web.append(dict(id=c["id"], root_class=names[int(vcls[r_, c_])], dist_to_white_vertex_m=round(dW, 4),
                        tau_start=c["tau_start"], root_twhite=round(float(tw[r_, c_]), 4) if tw[r_, c_] < 1e8 else None))
    import collections
    webc = collections.Counter(w["root_class"] for w in web)
    dws = np.array([w["dist_to_white_vertex_m"] for w in web])
    nvert = np.array([c["n_vert"] for c in claws])
    inst = {}
    for c in claws:
        key = c["parent"] if c["type"] == "branch" else c["id"]
        inst[key] = inst.get(key, 0) + c["n_vert"]
    chk = dict(
        schema="GreatWave.DS33.claw_checks/1", number="設計33（爪の部）", frames=U.NFR, hz=U.FPS, claws=nc,
        evidence_kind_ja="numpy の生成器の値（Unity の描画ではない。HMD 実機ではない）",
        item105=dict(rule_ja="根元の点（帯の根元の中心の頂点）と、そのコマの主役波のシートの三角形（描画と同じ分け方、根元のセルと周り 8 セル）の距離。見えるコマの全部",
                     max_m=float(d105v.max()), p99_m=float(np.percentile(d105v[visM], 99)), threshold_m=0.001, pass_=bool(d105v.max() <= 0.001)),
        item137=dict(rule_ja="根元の滑り：根元の (行, 列) は固定（設計32 の sheet_rc）。独立の読み：各コマで根元の頂点が乗る三角形（根元のセルと周り 8 セル）と重心座標から材料の座標 (行, 列) を読み直し、結び付けた (行, 列) との差（セル）と、そのコマのシートでのワールドの距離",
                     max_m=float(s137v.max()), max_param_cells=float(np.where(visM, prc137, 0).max()), threshold_m=0.001,
                     pass_=bool(s137v.max() <= 0.001)),
        item139=dict(rule_ja="成長の途中の欠落 0（使える水準）：生まれてから t* まで毎コマ見える（途切れ 0）、s・g・κ・ω が減らない、頂点に NaN がない、帯の面積が 0 のコマがない",
                     visibility_gaps=gaps, never_visible=never, decreasing_samples=mono, nan_frames=nan_count, zero_area_frames=zero_area,
                     arc_length_drop_over_1pct_frames_record_only=int(arc_dec.sum()),
                     arc_length_drop_ids_record_only=sorted(set(ids[i] for i in np.nonzero(arc_dec.any(0))[0])),
                     pass_=bool(not gaps and not never and all(v == 0 for v in mono.values()) and nan_count == 0 and zero_area == 0)),
        vertices=dict(per_claw_max=int(nvert.max()), per_type_instance_max=int(max(inst.values())), threshold=600,
                      total=int(nv), triangles=int(len(tris)), pass_=bool(nvert.max() <= 600 and max(inst.values()) <= 600)),
        teleport=dict(rule_ja="爪の頂点の 30 Hz のコマの間の動きの最大 ≤ そのコマのシートの頂点の動きの最大 × 1.5 + 2 cm ＋ 2 ×（弧長の増え＋幅の増え）",
                      count=len(tele), first=tele[:10], pass_=len(tele) == 0, max_move_m=float(np.where(np.r_[np.zeros((1, nc), bool), both], mv, 0).max()),
                      sheet_max_move_m=float(dsheet.max())),
        reprojection_tstar_record_only=dict(rule_ja="t* の骨格の曲線（関節を通る Catmull-Rom）を PaintingCam v1 へ投影し、一覧の中心線（表示の画素）との対称 Hausdorff。4 px は記録のみ（計画）",
                                            hausdorff_px=dict(p50=float(np.median(hd)), p95=float(np.percentile(hd, 95)), max=float(hd.max()),
                                                              le4=int((hd <= 4).sum())),
                                            p95_px=dict(p50=float(np.median(p95)), max=float(p95.max()), le4=int((p95 <= 4).sum())),
                                            root_px_max=float(max(r["root_px"] for r in rep)), tip_px_max=float(max(r["tip_px"] for r in rep)),
                                            worst=sorted(rep, key=lambda r: -r["hausdorff_px"])[:12], per_claw=rep),
        web_join=dict(rule_ja="波頭の白い帯（web）への継ぎ：根元はシートの色区（29修正01）の上にあり、根元の白の円が面に重なる。成長の開始は根元の T_white（白の帯がそこで白くなる時）",
                      root_class=dict(webc), dist_to_white_vertex_m=dict(p50=float(np.median(dws)), p95=float(np.percentile(dws, 95)), max=float(dws.max())),
                      per_claw=web),
        visible_frames_first=dict(zip(ids, [int(x) for x in first])),
        elapsed_s=round(time.time() - t0, 1))
    U.jdump(os.path.join(a.out, "ds33_claw_checks.json"), chk)
    for k in ("item105", "item137", "item139", "vertices", "teleport"):
        print(k, {kk: vv for kk, vv in chk[k].items() if kk not in ("rule_ja", "first")})
    print("reproj", chk["reprojection_tstar_record_only"]["hausdorff_px"], chk["reprojection_tstar_record_only"]["p95_px"])
    print("web", chk["web_join"]["root_class"], chk["web_join"]["dist_to_white_vertex_m"])
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
