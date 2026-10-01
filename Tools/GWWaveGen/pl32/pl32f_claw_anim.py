# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1：pl32_claw_anim.py（設計33 の ds33_claw_anim.py の写しに pl32_band_lift を足したもの）を写し、審査の指摘に対する
名前の付いた決まりを足したもの（numpy。Unity の描画ではない）。

  - pl32f_lift_facing（試して採らなかった。下限 FACING_MIN = 1.0 で λ_f = 1、pl32_band_lift のまま）：持ち上げを、根元の面が原画のカメラへ向く度合い
    f = n·v で λ_f = clip((0.85 − f) / 0.5, 下限, 1) 倍にする案。下限 0 と 0.5 を試したが、正面の面（b区域の背）でも帯の下の側の縁の線が面に隠れて
    原画視点の爪の線が細く薄くなり（線の画素 12,151 → 7,897・10,159）、座席から背の稜を見た時の帯のはみ出しは消えなかった（試しの描画 fix01/test1〜7）。
    座席の稜の「線の箱」は、縁の線の材質の pl32f_edge_box（PL32 Claw Outline）で減らした。
  - pl32f_width_fit：t*（τ = 0、s = 1）の帯を原画のカメラへ投影し、輪ごとに、投影した中心線に直交する向きの帯の幅を、一覧の領域（D25）の
    同じ所の断面の幅（左右の境までの距離の和、表示の px）に合わせる倍率を、輪ごとに求めて全部のコマの幅と厚みに掛ける（2 回まわす。
    倍率は 0.35〜3、隣の輪と 3 点でならす。先端の閉じ（設計33 の clos）と、ワールドの半幅の上限 0.5 m は保つ）。
    設計33 の幅（領域の距離変換の幅を型の先細りに収め、面の傾きの見積もりで割ったもの）は、投影すると領域の 0.54〜0.69 倍で、
    代表10形の左右の輪郭 ≤4 px が 3／10 だった（123〜126、審査の指摘）。帯の断面の形・折れ・こぶは仕上げ33。
  - pl32f_frame_stable：帯の輪の向き（接線は面へ載せ直す前のなめらかな曲線から、法線は関節の補間と半々に混ぜて 3 点でならし、
    法線と B はコマの間で向きをそろえる）。幅を領域に合わせて帯が広くなったので、伸び始めの短い帯で輪が半回転して頂点が 0.45 m 跳んだ（C104）のを防ぐ。
  - pl32f_bud_width：伸び始めの芽の幅を長さに合わせる（幅 × clip(g / 0.45, 0.25, 1)）。
  - pl32f_tuft_base の根元の円を、根元の輪の幅の倍率 × 1.3（1〜3 倍）で広げる。
  - 動きの検査を足す（judge_motion）：根元に対する帯の頂点のコマの間の動きの最大と、弧長の 1 コマの跳び（前後のコマの増えの 3 倍を超え、0.1 m を超える増え）。

── 以下は写した pl32_claw_anim.py の説明 ──
仕上げ32：設計33 の ds33_claw_anim.py を写し、名前の付いた美術の誘導 pl32_band_lift を足したもの（numpy。Unity の描画ではない）。

pl32_band_lift：設計33 の帯は「下の縁を面へ厚みの 0.25 だけ沈める」。設計33 の爪は段階9 の K*′ R4 に結び付けたままで、仕上げ28 の P28R2rec の面から
浮いていたので、爪の縁の線（設計38 の反転シェル）が全周で見えていた。仕上げ32 で結び付け直すと帯が面に沿い、反転シェルの下の側が主役波の面に隠れて、
原画視点の爪の線が細く薄くなった（試しの描画 Unity/Build/Polish/32/test1）。そこで、輪と先端を、根元の関節の法線（面の法線）の向きへ
λ(s) ×（LIFT_M ＋ 厚みの 0.25）だけ持ち上げる。LIFT_M = 0.085 m は、原画視点の爪の根元の深さの最大 64.8 m（pl32 の ds32_ids.json）での設計38 の線幅
（64.8 × 0.0012866 rad）。λ(s) = smoothstep((s − 0.2)/0.55)：芽（根元が白くなる段 s < 0.2）は面に沿ったまま（持ち上げると芽の線が閉じた輪になり、
原画視点 t 9 s の頂に小さな黒い輪が並んだ。test2）、伸びる段で持ち上げ、s ≥ 0.75 で全部。根元から 3 つ目の輪までは 0 → 1 になめらかに増やす。
根元の点と根元の白の円は面の上のまま（105 は変わらない）。向きは帯全体で同じ（輪ごとの向きだと曲がりの変化でコマの間の動きが増える）で、
根元から原画のカメラ（PaintingCam v1 の位置）への向き。原画視点では射線に沿って手前へ動かすだけなので、画面の上の爪の形・輪郭（132・72 の爪あり）は
持ち上げのない時と同じ（面の法線の向きに持ち上げた版は、唇の先の C085 の先が輪郭の外へ出て 132 σ12 の爪ありが 3.56 → 4.46 px になった）。

── 以下は写した設計33 の説明 ──
設計33（爪の部）：爪の帯のメッシュを全コマ（30 Hz × 421）で作り、受入の検査をする（numpy。Unity の描画ではない）。

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

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl32")
import pl32f_claw_rig as G  # noqa: E402
import cv2  # noqa: E402

K = U.K
RING = 8
PHI = 2 * np.pi * np.arange(RING) / RING
LIFT_M = 0.085                  # 原画視点の爪の根元の深さの最大 64.8 m × 設計38 の線の角幅 0.0012866 rad
LIFT_RAMP_RINGS = 3
LIFT_S = (0.20, 0.75)           # λ(s) が 0 → 1 になる成長の区間（設計33 の 3 段の標準曲線の「伸びる」段）
FACING_HI, FACING_SPAN, FACING_MIN = 0.85, 0.5, 1.0   # pl32f_lift_facing は試して採らなかった（下限 1.0 で λ_f = 1、pl32_band_lift のまま）
BUD_G, BUD_MIN = 0.45, 0.25          # pl32f_bud_width
SKIRT_GAIN = 1.3                     # pl32f_tuft_base の根元の円の広げ


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


_PREV_N = {}
_PREV_B = {}


def sweep(J, N, w, th, n_st, cfrac, snap=None, lift=0.0, lift_dir=None, key=None):
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
    St_pre = St.copy()
    Ns_pre = Ns.copy()
    if snap is not None:
        spar = np.interp(tq, sfrac, par)
        sseg = np.clip(np.floor(spar).astype(int), 0, nj - 2)
        sfr = np.clip(spar - sseg, 0, 1)
        St, Ns = snap(St, Ns, sseg, sfr)
        L = float(np.linalg.norm(np.diff(St, axis=0), axis=1).sum())
    # pl32f_frame_stable：短い帯（伸び始め）では、面へ載せ直した輪の中心のずれ（mm）が輪の間隔と同じ程度になり、接線が 1 つの輪で裏返って
    # 輪が半回転した（C104 のコマ 287・289 で頂点が 0.45 m 跳んだ）。接線は面へ載せ直す前のなめらかな曲線（Catmull-Rom）から取り、
    # 輪の法線の面へ射影する。さらに前の輪の向きにそろえて 3 点でならす
    # 面へ載せ直した輪の法線が、巻いた面の別の側に載って裏返るのを防ぐ（関節の法線の補間と向きをそろえる。C021 のコマ 340）
    flip = (Ns * Ns_pre).sum(1) < 0
    Ns = np.where(flip[:, None], -Ns, Ns)
    # 面へ載せ直した所の法線は三角形ごとに段があるので、関節の法線の補間と半々に混ぜ、輪の間で 3 点でならす
    Ns = Ns + Ns_pre
    if len(Ns) >= 3:
        Np = np.r_[Ns[:1], Ns, Ns[-1:]]
        Ns = Np[:-2] + 2 * Np[1:-1] + Np[2:]
    Ns /= np.maximum(np.linalg.norm(Ns, axis=1, keepdims=True), 1e-12)
    # コマの間でも向きをそろえる（直前のコマの同じ輪の法線と逆向きなら裏返す。key = 爪の番号）
    if key is not None:
        pv = _PREV_N.get(key)
        if pv is not None and pv.shape == Ns.shape:
            Ns = np.where(((Ns * pv).sum(1) < 0)[:, None], -Ns, Ns)
        _PREV_N[key] = Ns.copy()
    T = np.gradient(St_pre, axis=0)
    T = T - (T * Ns).sum(1, keepdims=True) * Ns
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    for j in range(1, len(T)):
        if T[j] @ T[j - 1] < 0:
            T[j] = -T[j]
    if len(T) >= 3:
        Tp = np.r_[T[:1], T, T[-1:]]
        T = Tp[:-2] + 2 * Tp[1:-1] + Tp[2:]
        T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    B = np.cross(Ns, T)
    mag = np.linalg.norm(B, axis=1)
    B /= np.maximum(mag[:, None], 1e-12)
    # 帯が面の法線の向きへ立つ所（T ∥ N）では B が決まらず、コマごとに向きが変わった（C021 のコマ 340）。直前のコマの B を T に直交させて使い、
    # どの輪も直前のコマの B と同じ向きにそろえる（key = 爪の番号）
    if key is not None:
        pb = _PREV_B.get(key)
        if pb is not None and pb.shape == B.shape:
            pbt = pb - (pb * T).sum(1, keepdims=True) * T
            pbt /= np.maximum(np.linalg.norm(pbt, axis=1, keepdims=True), 1e-12)
            B = np.where((mag < 0.35)[:, None], pbt, B)
            B = np.where(((B * pb).sum(1) < 0)[:, None], -B, B)
        _PREV_B[key] = B.copy()
    Nn = np.cross(T, B)
    hw = 0.5 * w[:, None]
    ctr = cfrac * th[:, None]
    ring = (St[:n_st, None, :] + B[:n_st, None, :] * (hw * np.cos(PHI)[None, :])[..., None]
            + Nn[:n_st, None, :] * (ctr + 0.5 * th[:, None] * np.sin(PHI)[None, :])[..., None])
    tip = St[n_st]
    if lift_dir is not None and lift > 0:
        # pl32_band_lift
        ramp = U.smoothstep(np.arange(n_st) / float(LIFT_RAMP_RINGS))
        amt = lift * (LIFT_M + 0.25 * np.asarray(th, np.float64)[:n_st]) * ramp
        ring = ring + lift_dir[None, None, :] * amt[:, None, None]
        tip = tip + lift_dir * (lift * LIFT_M)
    return ring, tip, L, (T, B, Nn, St)


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
    CAMPOS = np.asarray(cam.pos, np.float64)
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
    # ---- pl32f_lift_facing と pl32f_width_fit（t* の帯で決める）
    X0 = hero.world(0.0)
    inv0 = U.jload(U.D32 + "/ds32_claw_inventory.json")
    byid0 = {c["id"]: c for c in inv0["claws"]}
    lamf = np.zeros(nc)
    fit_rec = []

    def tstar_band(i, scale):
        d = data[i]
        RCs = d["RC"][-1].copy(); Es = d["E"][-1]
        RCs[0] = rc0[i]
        ref = d["ref"]
        S = U.tri_eval(X0, RCs[ref, 0], RCs[ref, 1])
        F = U.frame_at(X0, RCs[ref, 0], RCs[ref, 1])
        J = S + np.einsum("kji,kj->ki", F, Es)
        J[0] = U.tri_eval(X0, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
        Nj = np.einsum("kji,kj->ki", F, d["NL"])
        kb = d["bound"]

        def snap(St, Ns, sseg, sfr, X=X0, RCs=RCs, kb=kb, hang=d["hanging"]):
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
        return sweep(J, Nj, d["W"] * scale, d["TH"] * scale, d["n_st"], cfrac, snap)

    for i, c in enumerate(claws):
        root0 = U.tri_eval(X0, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
        n0 = U.normal_at(X0, np.array(rc0[i, 0]), np.array(rc0[i, 1]))
        v0 = CAMPOS - root0
        f = float(n0 @ (v0 / np.linalg.norm(v0)))
        lamf[i] = float(np.clip((FACING_HI - f) / FACING_SPAN, FACING_MIN, 1.0))
        d = data[i]
        n_st = d["n_st"]
        reg = U.to_disp(np.asarray(byid0[c["id"]]["region_polygon_ref"], np.float64))
        ss = 4.0
        bx0, by0 = np.floor(reg.min(0)) - 50
        bx1, by1 = np.ceil(reg.max(0)) + 50
        Mw, Mh = int((bx1 - bx0) * ss) + 1, int((by1 - by0) * ss) + 1
        M = np.zeros((Mh, Mw), np.uint8)
        cv2.fillPoly(M, [np.round((reg - [bx0, by0]) * ss).astype(np.int32)], 1)
        sj = np.arange(n_st) / n_st
        clos = np.sqrt(np.clip(1 - U.smoothstep((sj - 0.72) / 0.28), 0, 1))
        scale = np.ones(n_st)
        tgt = meas = None
        for it in range(2):
            ring, tip, L, (T_, B_, Nn_, St_) = tstar_band(i, scale[:, None][:, 0])
            qc, _ = cam.project(St_[:n_st])
            qr, _ = cam.project(ring.reshape(-1, 3))
            qr = qr.reshape(n_st, RING, 2)
            qall, _ = cam.project(np.concatenate([St_[:n_st], tip[None, :]], 0))
            tq = np.gradient(qall, axis=0)[:n_st]
            tq /= np.maximum(np.linalg.norm(tq, axis=1, keepdims=True), 1e-9)
            nq = np.stack([-tq[:, 1], tq[:, 0]], 1)
            proj = ((qr - qc[:, None, :]) * nq[:, None, :]).sum(-1)
            meas = proj.max(1) - proj.min(1)
            tgt = np.zeros(n_st)
            for j in range(n_st):
                tot = 0.0
                for sg in (-1.0, 1.0):
                    dist = 0.0
                    for k in range(1, 161):
                        p = (qc[j] + sg * nq[j] * (k * 0.25) - [bx0, by0]) * ss
                        xi, yi = int(round(p[0])), int(round(p[1]))
                        if not (0 <= xi < Mw and 0 <= yi < Mh) or not M[yi, xi]:
                            break
                        dist = k * 0.25
                    tot += dist
                tgt[j] = tot
            base = d["W"] * scale
            ok = (tgt > 0.5) & (meas > 0.2)
            new = np.where(ok, tgt * np.maximum(clos, 0.15) / np.maximum(meas, 0.2), 1.0)
            new = np.clip(new, 0.35, 3.0)
            new = np.convolve(np.r_[new[0], new, new[-1]], np.ones(3) / 3, mode="valid")
            scale = np.clip(scale * new, 0.35, 3.0)
            scale = np.minimum(scale, 1.0 / np.maximum(d["W"] / 1.0, 1e-6))   # 半幅 ≤ 0.5 m（幅 ≤ 1 m）
        d["W"] = d["W"] * scale
        d["TH"] = d["TH"] * scale
        # 根元の円（pl32f_tuft_base）も根元の輪の幅の倍率で広げる（泡の胴の側の水色の版の雲。半径は rig の上限 0.45 m の 1.4 倍まで）
        d["SK"] = d["SK"] * float(np.clip(scale[0] * SKIRT_GAIN, 1.0, 3.0))
        ring, tip, L, (T_, B_, Nn_, St_) = tstar_band(i, 1.0)
        qc, _ = cam.project(St_[:n_st]); qr, _ = cam.project(ring.reshape(-1, 3)); qr = qr.reshape(n_st, RING, 2)
        proj = ((qr - qc[:, None, :]) * nq[:, None, :]).sum(-1)
        after = proj.max(1) - proj.min(1)
        fit_rec.append(dict(id=c["id"], facing=round(f, 3), lift_facing=round(float(lamf[i]), 3), scale=U.rnd(scale, 3),
                            target_px=U.rnd(tgt, 2), after_px=U.rnd(after, 2),
                            ratio_after_median=round(float(np.median(after[tgt > 0.5] / np.maximum(tgt[tgt > 0.5], 1e-6))) if (tgt > 0.5).any() else 0.0, 3)))
    print("width fit + facing %.1fs" % (time.time() - t0), flush=True)
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
        # pl32f_bud_width：伸び始めの芽の幅を長さに合わせる（幅 × clip(g / 0.45, 0.25, 1)）。幅を領域に合わせた（pl32f_width_fit）ので、
        # 設計33 の「幅は s 0.2 で全部」のままだと、長さ 0.1 m の芽が幅 0.6 m の平たい塊になり、原画視点 t 10.5 s で閉じた輪（米粒）に見え、向きも揺れた
        w_all = w_all * np.clip(g_all / BUD_G, BUD_MIN, 1.0)
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
            lam = float(U.smoothstep((s_all[i] - LIFT_S[0]) / (LIFT_S[1] - LIFT_S[0])))
            v0 = CAMPOS - root
            n0 = v0 / max(float(np.linalg.norm(v0)), 1e-12)   # 根元から原画のカメラへの向き（原画視点の画面の上の形は変わらない）
            ring, tip, L, _ = sweep(J, Nj, d["W"] * w_all[i], d["TH"] * w_all[i], d["n_st"], cfrac, snap, lift=lam * lamf[i], lift_dir=n0, key=i)
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
    # judge_motion：根元に対する帯の頂点のコマの間の動きと、弧長の 1 コマの跳び
    relmv = np.zeros((U.NFR, nc))
    for i in range(nc):
        o, n = offs[i]
        rel = V[:, o:o + n].astype(np.float64) - V[:, o:o + 1].astype(np.float64)
        relmv[1:, i] = np.linalg.norm(np.diff(rel, axis=0), axis=2).max(1)
    relmv = np.where(np.r_[np.zeros((1, nc), bool), both], relmv, 0.0)
    da = np.diff(arcl, axis=0)
    jumps = []
    for i in range(nc):
        for f in range(1, U.NFR - 2):
            if not (visM[f, i] and visM[f + 1, i] and visM[f - 1, i]):
                continue
            g = da[f, i]
            nb = max(abs(da[f - 1, i]), abs(da[f + 1, i]), 0.01)
            if g > 0.1 and g > 3.0 * nb:
                jumps.append((ids[i], f + 1, round(float(g), 4)))
    jm = dict(rule_ja="根元に対する帯の頂点の 30 Hz のコマの間の動きの最大（見えるコマ）と、弧長の 1 コマの跳び（増え > 0.1 m かつ前後のコマの増えの 3 倍超）",
              rel_move_max_m=float(relmv.max()), rel_move_argmax=[ids[int(np.argmax(relmv.max(0)))], int(np.argmax(relmv.max(1)))],
              rel_move_p99_m=float(np.percentile(relmv[relmv > 0], 99)) if (relmv > 0).any() else 0.0,
              top=sorted([(ids[i], int(np.argmax(relmv[:, i])), round(float(relmv[:, i].max()), 4)) for i in range(nc)], key=lambda x: -x[2])[:10],
              growth_jumps=jumps, growth_jump_count=len(jumps))
    print("judge_motion", {k: v for k, v in jm.items() if k not in ("rule_ja",)}, flush=True)
    chk = dict(
        schema="GreatWave.DS33.claw_checks/1", number="仕上げ32 修正の回 1（設計33 の爪の部の写し）", frames=U.NFR, hz=U.FPS, claws=nc,
        judge_motion=jm, width_fit=dict(rule_ja="pl32f_width_fit", per_claw=fit_rec,
                                       ratio_after_median=dict(p10=float(np.percentile([r["ratio_after_median"] for r in fit_rec], 10)),
                                                               p50=float(np.median([r["ratio_after_median"] for r in fit_rec])),
                                                               p90=float(np.percentile([r["ratio_after_median"] for r in fit_rec], 90)))),
        lift_facing=dict(rule_ja="pl32f_lift_facing：λ_f = clip((%.2f − n·v) / %.2f, %.2f, 1)" % (FACING_HI, FACING_SPAN, FACING_MIN),
                         at_min=int((lamf <= FACING_MIN + 1e-9).sum()), one=int((lamf >= 1).sum()), partial=int(((lamf > FACING_MIN + 1e-9) & (lamf < 1)).sum())),
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
