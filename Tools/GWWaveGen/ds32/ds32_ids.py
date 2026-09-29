# -*- coding: utf-8 -*-
"""設計32：爪・白の帯・飛沫の群の ID と、主役波のシートに結び付けた ID ごとの履歴（numpy。Unity の描画ではない）。

入力（読むだけ。SHA-256 を記録する）：
  - 修正した爪の一覧 Unity/Build/Design/32/list+ids/ds32_claw_inventory.json（ds32_claw_list.py の出力）
  - 主役波の動き（採用）：Unity/Build/Design/31/white/hero_pkg（F_final の位置＋設計31 の T_white）。最後の層（τ = 0）が K*′ R4
  - 時間曲線 Unity/Build/Design/28R01F/F_final/timewarp_F_final.json（t → τ、DS27TimeWarp.TauAt と同じ線形補間）
  - 29修正01 の色面（頂点の色区。白の帯の群を作る）、設計31 の飛沫（ds31_spray_table.json・ds31_spray_frames.bin）
  - PaintingCam v1（Tools/PaintingTruth/painting_truth.json）

結び付け（爪）：
  - t*（τ = 0）の主役波の本体（列 18〜394）を PaintingCam v1 で z バッファに描き、爪の根元の表示の画素を通る射線が最初に当たる三角形との交点から、
    シートの連続の座標 (行 r, 列 c) を求める（当たらなければ 12 px 以内の最も近いシートの画素へ寄せ、寄せた距離を記録）。
    sheet_uv = (c/(C−1), r/(R−1))、uv3 = 29修正01 の (uWarp(c), vWarp(r))。
  - 先端と中心線の点：その画素の射線が根元のカメラの深さ ±1.5 m でシートに当たればその点、当たらなければ根元のカメラの深さの面との交点。
    根元の局所の座標系 (e1 = ∂P/∂c の向き、n = (∂P/∂r)×(∂P/∂c) の向き＝空気の側、e2 = n × e1) での t* の差を「局所のずれ」とする。
  - 履歴：root(τ) = シートの (r, c) の双線形、tip(τ) = root(τ) + g(τ)·[e1 e2 n](τ)·ずれ。
    g(τ)（仮の成長、設計33 で置き換える）＝ smoothstep((τ − τ_b)/(0 − τ_b))、τ_b＝根元の T_white（設計31、周りの 2×2 の有限の値の最小）。
    τ < τ_b では見えない（visible 0）。t* の後は τ = 0 のまま（静止）。
群：
  - 爪の群（房）：列（上側・途中・船側・b区域・右側）ごとに、t* の根元のワールドの位置の単連結（しきい値＝その列の最近傍の距離の中央値の 2.5 倍）。
  - 白の帯の群：t* の色区が白の頂点（本体の列）の 4 連結の成分（40 頂点以上）。頂点ごとの重み w = smoothstep((τ − T_white)/0.25 s)。
  - 飛沫の群：設計31 の 186 粒のうち、放出の点と時刻が近い粒の単連結（|Δp_e| ≤ 0.8 m かつ |Δτ_e| ≤ 0.06 s）。重み＝半径 / 最大の半径。
検査（ds32_id_checks.json）：
  - 瞬間移動 0：ID と群の重心の 30 Hz のコマの間の動きが、(a) そのコマのシートの頂点・飛沫の粒の動きの最大の 1.5 倍 + 2 cm を超えない、
    (b) 前後のコマの動きの大きい方の 4 倍 + 5 cm を超える突出がない。群は両方のコマで見える粒（共通の粒）の重心で測る（見える粒の重み付きの重心は記録のみ）。
  - 意図しない点滅 0：見える → 見えないの変化（t* までに消えるもの）が 0。群の見える粒の集合から粒が抜けるコマ（瞬間的な置き換え、129）が 0。
  - t* の再投影：根元・先端を PaintingCam v1 へ戻したときの一覧の表示の画素とのずれ。
出力（Git 対象外、Unity/Build/Design/32/list+ids/）：ds32_ids.json、ds32_claw_hist_f32.bin、ds32_group_hist_f32.bin、ds32_id_checks.json。
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds30")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import ds30_checks as K  # noqa: E402
import ds31_white as W31  # noqa: E402

C27 = K.C27
OUT = REPO + "/Unity/Build/Design/32/list+ids"
HERO = REPO + "/Unity/Build/Design/31/white/hero_pkg"
WARP = REPO + "/Unity/Build/Design/28R01F/F_final/timewarp_F_final.json"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
SPRAY = REPO + "/Unity/Build/Design/31/spray"
UVW = W31.UVW
FPS, NFR = 30, 421
BODY = (18, 394)
P = dict(snap_px=12.0, tip_depth_window_m=1.5, band_min_vertices=40, band_ramp_s=0.25, band_tile=[16, 16],
         claw_group_nn_factor=2.5, spray_link_m=0.8, spray_link_s=0.06, teleport_factor=1.5, teleport_abs_m=0.02,
         spike_factor=4.0, spike_abs_m=0.05, centerline_points=12,
         prominent_min={"claw": 3, "white_band": 120, "spray": 4})


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _np(o):
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def jdump(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)


def rnd(v, k=4):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    return None if v is None else round(float(v), k)


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def to_disp(q):
    q = np.asarray(q, np.float64)
    return np.stack([0.416345 * (q[..., 0] + 0.5) - 0.5 + 156.66153, 0.416345 * (q[..., 1] + 0.5) - 0.5], -1)


def bilin(X, r, c):
    """X：R×C×3、(r, c) 浮動 → 双線形。"""
    R, C = X.shape[:2]
    r0 = np.clip(np.floor(r).astype(int), 0, R - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, C - 2)
    fr, fc = (r - r0)[..., None], (c - c0)[..., None]
    return (X[r0, c0] * (1 - fr) * (1 - fc) + X[r0 + 1, c0] * fr * (1 - fc) + X[r0, c0 + 1] * (1 - fr) * fc + X[r0 + 1, c0 + 1] * fr * fc)


def frame_at(X, r, c):
    """(r, c) の局所の座標系：e1 = ∂P/∂c、n = (∂P/∂r) × (∂P/∂c)（空気の側）、e2 = n × e1。"""
    h = 0.5
    R, C = X.shape[:2]
    rp, rm = np.clip(r + h, 0, R - 1), np.clip(r - h, 0, R - 1)
    cp, cm = np.clip(c + h, 0, C - 1), np.clip(c - h, 0, C - 1)
    dr = (bilin(X, rp, c) - bilin(X, rm, c)) / np.maximum(rp - rm, 1e-9)[..., None]
    dc = (bilin(X, r, cp) - bilin(X, r, cm)) / np.maximum(cp - cm, 1e-9)[..., None]
    e1 = dc / np.maximum(np.linalg.norm(dc, axis=-1, keepdims=True), 1e-12)
    n = np.cross(dr, dc)
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)
    e2 = np.cross(n, e1)
    return np.stack([e1, e2, n], -2)  # … × 3（基底）× 3


def ray_tri(o, d, A, B, Cc):
    """射線 o + s·d と三角形の交点（Möller–Trumbore）。戻り値 s, u, v（交点 = A + u(B−A) + v(C−A)）。"""
    e1, e2 = B - A, Cc - A
    p = np.cross(d, e2)
    det = e1 @ p
    if abs(det) < 1e-14:
        return None
    inv = 1.0 / det
    tv = o - A
    u = (tv @ p) * inv
    q = np.cross(tv, e1)
    v = (d @ q) * inv
    s = (e2 @ q) * inv
    return s, u, v


def union_find_groups(pts, thr):
    n = len(pts)
    par = list(range(n))

    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            if np.linalg.norm(pts[i] - pts[j]) <= thr:
                a, b = f(i), f(j)
                if a != b:
                    par[max(a, b)] = min(a, b)
    lab = [f(i) for i in range(n)]
    uniq = sorted(set(lab), key=lambda x: min(k for k in range(n) if lab[k] == x))
    return [uniq.index(l) for l in lab]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()
    t0 = time.time()
    out = args.out
    spec = json.load(open(TRUTH, encoding="utf-8"))
    cam = C27.Cam(spec)
    hero = K.Pkg(HERO)
    R, C = hero.R, hero.C
    inv = json.load(open(out + "/ds32_claw_inventory.json", encoding="utf-8"))
    warp = json.load(open(WARP, encoding="utf-8"))
    wt, wtau = np.array(warp["t"]), np.array(warp["tau"])
    tfr = np.arange(NFR) / FPS
    taus = np.interp(tfr, wt, wtau)
    tw = np.fromfile(HERO + "/" + hero.k["twhite_file"], "<f4").reshape(R, C).astype(np.float64)
    tw = np.where(tw > 1e8, np.inf, tw)

    # ---- t* の z バッファ（本体の三角形の番号）
    X0 = hero.world(0.0)
    Tb = K.grid_tris(R, C, BODY[0], BODY[1])
    V0 = X0.reshape(-1, 3)
    tris = V0[Tb]
    idb, zb = K.raster_ids(cam, tris, np.arange(1, len(Tb) + 1))
    ncol = BODY[1] - BODY[0]
    print("zbuffer %.1fs" % (time.time() - t0), flush=True)

    def bind_pixel(xd, yd, depth_ref=None, window=None):
        """表示の画素 → シートの (r, c) と t* のワールドの点。戻り値 dict か None。"""
        xi, yi = int(round(xd)), int(round(yd))
        snap = 0.0
        if not (0 <= xi < K.W and 0 <= yi < K.H) or idb[yi, xi] == 0:
            if depth_ref is not None:
                return None
            ys, xs = np.nonzero(idb[max(0, yi - 13):yi + 14, max(0, xi - 13):xi + 14])
            if not len(xs):
                return None
            xs = xs + max(0, xi - 13); ys = ys + max(0, yi - 13)
            k = int(np.argmin((xs - xd) ** 2 + (ys - yd) ** 2))
            snap = float(math.hypot(xs[k] - xd, ys[k] - yd))
            if snap > P["snap_px"]:
                return None
            xd, yd, xi, yi = float(xs[k]), float(ys[k]), int(xs[k]), int(ys[k])
        d = cam.ray(np.array(xd), np.array(yd))
        best = None
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                y2, x2 = yi + dy, xi + dx
                if not (0 <= x2 < K.W and 0 <= y2 < K.H):
                    continue
                t_ = idb[y2, x2]
                if t_ == 0:
                    continue
                t = t_ - 1
                A, B, Cc = tris[t]
                h = ray_tri(cam.pos, d, A, B, Cc)
                if h is None:
                    continue
                s, u, v = h
                err = max(0.0, -u, -v, u + v - 1)
                if best is None or err < best[0] or (err == best[0] and s < best[1]):
                    best = (err, s, u, v, t)
        if best is None:
            return None
        err, s, u, v, t = best
        u, v = min(max(u, 0.0), 1.0), min(max(v, 0.0), 1.0)
        if u + v > 1:
            u, v = u / (u + v), v / (u + v)
        cell, half = divmod(t, 2)
        r0, c0 = divmod(cell, ncol)
        c0 += BODY[0]
        if half == 0:   # a=(r,c) b=(r+1,c) cc=(r,c+1)
            rr, cc = r0 + u, c0 + v
        else:           # cc=(r,c+1) b=(r+1,c) d=(r+1,c+1)
            rr, cc = r0 + u + v, c0 + 1 - u
        p = bilin(X0, np.array(rr), np.array(cc))
        dep = float(cam.depth(p))
        if depth_ref is not None and abs(dep - depth_ref) > window:
            return None
        return dict(r=float(rr), c=float(cc), p=p, depth=dep, snap_px=snap, bary_err=err)

    # ---- 爪の結び付け
    uvw = json.load(open(UVW, encoding="utf-8"))
    uW, vW = np.array(uvw["uWarp"]), np.array(uvw["vWarp"])
    claws = inv["claws"]
    recs = []
    for c in claws:
        rd = c["root_display"]
        b = bind_pixel(rd[0], rd[1])
        rec = dict(id=c["id"], row=c["row"], origin=c["origin"], b_region_q16=c["b_region_q16"])
        if b is None:
            rec["bound"] = False
            recs.append(rec)
            continue
        F0 = frame_at(X0, np.array(b["r"]), np.array(b["c"]))

        def place_pt(qd):
            h = bind_pixel(qd[0], qd[1], b["depth"], P["tip_depth_window_m"])
            if h is not None:
                return h["p"], "sheet"
            d = cam.ray(np.array(qd[0]), np.array(qd[1]))
            s = (b["depth"]) / float(d @ cam.f)
            return cam.pos + s * d, "depth_plane"
        tip_p, tip_how = place_pt(c["tip_display"])
        clr = np.asarray(c["centerline_ref"], np.float64)
        k = np.linspace(0, len(clr) - 1, min(P["centerline_points"], len(clr))).round().astype(int)
        cld = to_disp(clr[k])
        cl_p = [place_pt(q)[0] for q in cld]
        off_tip = F0 @ (tip_p - b["p"])
        off_cl = [F0 @ (q - b["p"]) for q in cl_p]
        r_, c_ = b["r"], b["c"]
        # T_white（根元の周りの 2×2 の有限の値の最小。無ければ 5×5）
        r0, c0 = int(np.clip(math.floor(r_), 0, R - 2)), int(np.clip(math.floor(c_), 0, C - 2))
        blk = tw[r0:r0 + 2, c0:c0 + 2]
        fin = blk[np.isfinite(blk)]
        tb_how = "2x2"
        if not len(fin):
            blk = tw[max(0, r0 - 2):r0 + 4, max(0, c0 - 2):c0 + 4]
            fin = blk[np.isfinite(blk)]
            tb_how = "5x5"
        if len(fin):
            tau_b = float(fin.min())
        else:
            tau_b = -0.5
            tb_how = "既定 −0.5 s（周りに白くなる頂点がない）"
        tau_b = min(tau_b, -1e-3)
        rec.update(bound=True, sheet_rc=[rnd(r_, 4), rnd(c_, 4)], sheet_uv=[rnd(c_ / (C - 1), 6), rnd(r_ / (R - 1), 6)],
                   uv3=[rnd(np.interp(c_, np.arange(C), uW), 6), rnd(np.interp(r_, np.arange(R), vW), 6)],
                   root_snap_display_px=rnd(b["snap_px"], 2), root_world_tstar=rnd(b["p"], 4), root_cam_depth_m=rnd(b["depth"], 3),
                   tip_world_tstar=rnd(tip_p, 4), tip_placement=tip_how, tip_local_offset_m=rnd(off_tip, 4),
                   length_tstar_m=rnd(float(np.linalg.norm(tip_p - b["p"])), 3),
                   centerline_local_offsets_m=rnd(off_cl, 4), tau_birth=rnd(tau_b, 4), tau_birth_from=tb_how,
                   t_birth=rnd(W31.t_of_tau(tau_b, wt, wtau), 4))
        rec["_rc"] = (r_, c_)
        rec["_off"] = off_tip
        recs.append(rec)
    bound = [r for r in recs if r.get("bound")]
    print("bound %d/%d  %.1fs" % (len(bound), len(recs), time.time() - t0), flush=True)

    # ---- 爪の群（房）
    by_row = {}
    for r in bound:
        by_row.setdefault(r["row"], []).append(r)
    claw_groups = []
    for row, rs in by_row.items():
        pts = np.array([r["root_world_tstar"] for r in rs])
        if len(rs) >= 2:
            D = np.linalg.norm(pts[:, None] - pts[None], axis=-1) + np.eye(len(rs)) * 1e9
            thr = P["claw_group_nn_factor"] * float(np.median(D.min(1)))
        else:
            thr = 1.0
        lab = union_find_groups(pts, thr)
        base = len(claw_groups)
        for g in sorted(set(lab)):
            mem = [rs[i]["id"] for i in range(len(rs)) if lab[i] == g]
            gid = "GC%02d" % (len(claw_groups) + 1)
            claw_groups.append(dict(id=gid, kind="claw", row=row, members=mem, link_threshold_m=rnd(thr, 3)))
            for r in rs:
                if r["id"] in mem:
                    r["group"] = gid

    # ---- 白の帯の群（t* の色区が白の頂点、本体の列）
    vcls, _ = W31.vertex_class(R, C)
    vcls = vcls.reshape(R, C)
    white = (vcls == 0) & np.isfinite(tw)
    white[:, :BODY[0]] = False
    white[:, BODY[1] + 1:] = False
    import cv2
    n_, lab_ = cv2.connectedComponents(white.astype(np.uint8), connectivity=4)
    comps = []
    TR, TC = P["band_tile"]
    labg = lab_.reshape(R, C)
    for k in range(1, n_):
        m = labg == k
        if m.sum() < P["band_min_vertices"]:
            continue
        # 大きな白の面は、行 16 × 列 16 の区画で切り、区画の中の 4 連結の片を群にする（群をまとまった大きさにする）
        for r0 in range(0, R, TR):
            for c0 in range(0, C, TC):
                sub = m[r0:r0 + TR, c0:c0 + TC]
                if sub.sum() < P["band_min_vertices"]:
                    continue
                n2, l2 = cv2.connectedComponents(sub.astype(np.uint8), connectivity=4)
                for q in range(1, n2):
                    yy, xx = np.nonzero(l2 == q)
                    if len(yy) >= P["band_min_vertices"]:
                        comps.append(((yy + r0) * C + (xx + c0)).astype(np.int64))
    comps.sort(key=lambda a: (float(tw.ravel()[a].min()), int(a.min())))
    band_groups = []
    for k, idx in enumerate(comps):
        rr, cc = np.divmod(idx, C)
        band_groups.append(dict(id="GW%03d" % (k + 1), kind="white_band", vertices=len(idx), rows=[int(rr.min()), int(rr.max())],
                                cols=[int(cc.min()), int(cc.max())], tau_first_white=rnd(float(tw.ravel()[idx].min()), 4),
                                tau_all_white=rnd(float(tw.ravel()[idx].max()), 4), _idx=idx))

    # ---- 飛沫の群
    stab = json.load(open(SPRAY + "/ds31_spray_table.json", encoding="utf-8"))["particles"]
    sfr = json.load(open(SPRAY + "/ds31_spray_frames.json", encoding="utf-8"))
    S = np.fromfile(SPRAY + "/" + sfr["file"], "<f4").reshape(sfr["frames"], sfr["count"], 4).astype(np.float64)
    # 飛沫の群：放出の点と時刻が近い粒（|Δp_e| ≤ 0.8 m かつ |Δτ_e| ≤ 0.06 s の単連結）。一緒に出て一緒に飛ぶ粒の群
    pe = np.array([p["p_e"] for p in stab]); te = np.array([p["tau_e"] for p in stab])
    npart = len(stab)
    par = list(range(npart))

    def fnd(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    for i in range(npart):
        for j in range(i + 1, npart):
            if np.linalg.norm(pe[i] - pe[j]) <= P["spray_link_m"] and abs(te[i] - te[j]) <= P["spray_link_s"]:
                a_, b_ = fnd(i), fnd(j)
                if a_ != b_:
                    par[max(a_, b_)] = min(a_, b_)
    roots_ = sorted(set(fnd(i) for i in range(npart)), key=lambda x: (te[x], x))
    spray_groups = []
    for g, rt in enumerate(roots_):
        idx = [i for i in range(npart) if fnd(i) == rt]
        spray_groups.append(dict(id="GS%03d" % (g + 1), kind="spray", members=[stab[i]["dot_id"] for i in idx],
                                 tau_e=[rnd(te[idx].min(), 3), rnd(te[idx].max(), 3)], _idx=idx))
    print("groups claw %d band %d spray %d  %.1fs" % (len(claw_groups), len(band_groups), len(spray_groups), time.time() - t0), flush=True)

    # ---- 履歴（30 Hz × 421 コマ）
    nb = len(bound)
    rc = np.array([r["_rc"] for r in bound])
    offs = np.array([r["_off"] for r in bound])
    taub = np.array([r["tau_birth"] for r in bound])
    H = np.zeros((NFR, nb, 8), np.float32)   # root xyz, tip xyz, g, visible
    GB = np.zeros((NFR, len(band_groups), 4), np.float32)   # 重心 xyz, 重みの和
    DB = np.zeros((NFR, len(band_groups)))   # 共通の粒の重心の動き（コマ f−1 → f）
    VB = np.zeros((NFR, len(band_groups)), bool)
    dsheet = np.zeros(NFR)
    Xprev = None
    Xfprev = None
    tau_prev = None
    for f, tau in enumerate(taus):
        X = hero.world(float(tau))
        Xb = X[:, BODY[0]:BODY[1] + 1]
        if Xprev is not None:
            dsheet[f] = float(np.linalg.norm(Xb - Xprev, axis=-1).max())
        Xprev = Xb
        root = bilin(X, rc[:, 0], rc[:, 1])
        Fm = frame_at(X, rc[:, 0], rc[:, 1])
        g = np.where(tau >= taub, smoothstep((tau - taub) / (0.0 - taub)), 0.0)
        tip = root + g[:, None] * np.einsum("nij,ni->nj", Fm, offs)
        H[f, :, 0:3] = root
        H[f, :, 3:6] = tip
        H[f, :, 6] = g
        H[f, :, 7] = (tau >= taub).astype(np.float32)
        Xf = X.reshape(-1, 3)
        for k, bg in enumerate(band_groups):
            twk = tw.ravel()[bg["_idx"]]
            vis_now = tau >= twk
            VB[f, k] = vis_now.any()
            if Xfprev is not None:
                com = vis_now & (tau_prev >= twk)
                if com.any():
                    DB[f, k] = float(np.linalg.norm(Xf[bg["_idx"][com]].mean(0) - Xfprev[bg["_idx"][com]].mean(0)))
            w = smoothstep((tau - twk) / P["band_ramp_s"])
            sw = float(w.sum())
            GB[f, k, 3] = sw
            if sw > 0:
                GB[f, k, 0:3] = (Xf[bg["_idx"]] * w[:, None]).sum(0) / sw
        Xfprev = Xf.copy()
        tau_prev = tau
    print("history %.1fs" % (time.time() - t0), flush=True)

    # 爪の群の重心（重み g）
    GC = np.zeros((NFR, len(claw_groups), 4), np.float32)
    idpos = {r["id"]: i for i, r in enumerate(bound)}
    for k, cg in enumerate(claw_groups):
        ii = [idpos[m] for m in cg["members"]]
        w = H[:, ii, 6].astype(np.float64)
        sw = w.sum(1)
        cen = (H[:, ii, 0:3] * w[..., None]).sum(1) / np.maximum(sw, 1e-12)[:, None]
        GC[:, k, 0:3] = np.where(sw[:, None] > 0, cen, 0)
        GC[:, k, 3] = sw
    # 飛沫の群
    GS = np.zeros((NFR, len(spray_groups), 4), np.float32)
    rmax = max(S[..., 3].max(), 1e-9)
    dspray = np.zeros(NFR)
    dspray[1:] = np.where((S[1:, :, 3] > 0) & (S[:-1, :, 3] > 0), np.linalg.norm(S[1:, :, :3] - S[:-1, :, :3], axis=-1), 0).max(1)
    for k, sg in enumerate(spray_groups):
        w = S[:, sg["_idx"], 3] / rmax
        sw = w.sum(1)
        cen = (S[:, sg["_idx"], :3] * w[..., None]).sum(1) / np.maximum(sw, 1e-12)[:, None]
        GS[:, k, 0:3] = np.where(sw[:, None] > 0, cen, 0)
        GS[:, k, 3] = sw

    # ---- 検査
    bound_f = np.maximum(dsheet, dspray) * P["teleport_factor"] + P["teleport_abs_m"]

    def teleports(Ptr, vis, name_list, kind):
        """Ptr：NFR × n × 3、vis：NFR × n（見える）。戻り値：瞬間移動の一覧。"""
        res = []
        d = np.linalg.norm(Ptr[1:] - Ptr[:-1], axis=-1)   # (NFR−1) × n、コマ f → f+1
        both = vis[1:] & vis[:-1]
        over = both & (d > bound_f[1:, None])
        dn = np.zeros_like(d)
        dn[1:-1] = np.maximum(d[:-2], d[2:])
        dn[0] = d[1]
        dn[-1] = d[-2]
        spike = both & (d > P["spike_factor"] * dn + P["spike_abs_m"])
        for f_, i_ in zip(*np.nonzero(over | spike)):
            res.append(dict(kind=kind, id=name_list[i_], frame=int(f_ + 1), move_m=rnd(d[f_, i_], 4), bound_m=rnd(bound_f[f_ + 1], 4),
                            neighbours_m=rnd(dn[f_, i_], 4), rule="a" if over[f_, i_] else "b"))
        return res, float(np.where(both, d, 0).max()) if both.any() else 0.0

    ids_b = [r["id"] for r in bound]
    visH = H[:, :, 7] > 0.5
    tele, stats = [], {}
    r1, m1 = teleports(H[:, :, 0:3].astype(np.float64), visH, ids_b, "claw_root"); tele += r1; stats["claw_root_max_move_m"] = m1
    r2, m2 = teleports(H[:, :, 3:6].astype(np.float64), visH, ids_b, "claw_tip"); tele += r2; stats["claw_tip_max_move_m"] = m2
    r5, m5 = teleports(S[:, :, 0:3], S[:, :, 3] > 0, [p["dot_id"] for p in stab], "spray_particle"); tele += r5; stats["spray_max_move_m"] = m5

    def common_motion(Pm, Vm):
        """群の動き：コマ f−1 と f の両方で見える粒（共通の粒）の重心の動き。"""
        D = np.zeros(NFR)
        V = Vm.any(1)
        for f_ in range(1, NFR):
            com = Vm[f_] & Vm[f_ - 1]
            if com.any():
                D[f_] = float(np.linalg.norm(Pm[f_, com].mean(0) - Pm[f_ - 1, com].mean(0)))
        return D, V

    def group_tele(Dg, Vg, names, kind):
        res = []
        both = Vg[1:] & Vg[:-1]
        d = Dg[1:]
        dn = np.zeros_like(d)
        dn[1:-1] = np.maximum(d[:-2], d[2:]); dn[0] = d[1]; dn[-1] = d[-2]
        over = both & (d > bound_f[1:, None])
        spike = both & (d > P["spike_factor"] * dn + P["spike_abs_m"])
        for f_, i_ in zip(*np.nonzero(over | spike)):
            res.append(dict(kind=kind, id=names[i_], frame=int(f_ + 1), move_m=rnd(d[f_, i_], 4), bound_m=rnd(bound_f[f_ + 1], 4),
                            neighbours_m=rnd(dn[f_, i_], 4), rule="a" if over[f_, i_] else "b"))
        return res, float(np.where(both, d, 0).max()) if both.any() else 0.0
    DC = np.zeros((NFR, len(claw_groups))); VC = np.zeros((NFR, len(claw_groups)), bool)
    for k, cg in enumerate(claw_groups):
        ii = [idpos[m] for m in cg["members"]]
        DC[:, k], VC[:, k] = common_motion(H[:, ii, 0:3].astype(np.float64), visH[:, ii])
    DS = np.zeros((NFR, len(spray_groups))); VS = np.zeros((NFR, len(spray_groups)), bool)
    for k, sg in enumerate(spray_groups):
        DS[:, k], VS[:, k] = common_motion(S[:, sg["_idx"], 0:3], S[:, sg["_idx"], 3] > 0)
    r3, m3 = group_tele(DC, VC, [g["id"] for g in claw_groups], "claw_group"); tele += r3; stats["claw_group_max_move_m"] = m3
    r4, m4 = group_tele(DB, VB, [g["id"] for g in band_groups], "white_band_group"); tele += r4; stats["band_group_max_move_m"] = m4
    r6, m6 = group_tele(DS, VS, [g["id"] for g in spray_groups], "spray_group"); tele += r6; stats["spray_group_max_move_m"] = m6
    # 記録のみ：見える粒の重み付きの重心（新しい粒の出現で動く分を含む）
    rec_w = {}
    for nm, G_ in (("claw_group", GC), ("white_band_group", GB), ("spray_group", GS)):
        vv = G_[:, :, 3] > 0
        dd = np.linalg.norm(G_[1:, :, 0:3] - G_[:-1, :, 0:3], axis=-1)
        both = vv[1:] & vv[:-1]
        dd = np.where(both, dd, 0)
        rec_w[nm] = dict(max_move_m=rnd(float(dd.max()) if dd.size else 0.0, 4),
                         frames_over_rule_a=int((dd > bound_f[1:, None]).sum()),
                         groups_over_rule_a=int((dd > bound_f[1:, None]).any(0).sum()))

    def flicker(vis, names, kind):
        res = []
        dv = np.diff(vis.astype(int), axis=0)
        for i in range(vis.shape[1]):
            off_ = np.nonzero(dv[:, i] < 0)[0]
            on_ = np.nonzero(dv[:, i] > 0)[0]
            if len(off_) or len(on_) > 1:
                res.append(dict(kind=kind, id=names[i], off_frames=[int(x + 1) for x in off_], on_frames=[int(x + 1) for x in on_]))
        return res
    flk = []
    flk += flicker(visH, ids_b, "claw")
    flk += flicker(GC[:, :, 3] > 0, [g["id"] for g in claw_groups], "claw_group")
    flk += flicker(GB[:, :, 3] > 0, [g["id"] for g in band_groups], "white_band_group")
    flk += flicker(S[:, :, 3] > 0, [p["dot_id"] for p in stab], "spray_particle")
    flk += flicker(GS[:, :, 3] > 0, [g["id"] for g in spray_groups], "spray_group")
    # 成長の単調（g が減らない）
    gdec = int(((H[1:, :, 6] - H[:-1, :, 6]) < -1e-6).sum())
    # 群の見える粒の集合から粒が抜けるコマ（瞬間的な置き換え）
    repl = []
    for kind, groups, visf in (("claw_group", claw_groups, lambda g: visH[:, [idpos[m] for m in g["members"]]]),
                               ("spray_group", spray_groups, lambda g: S[:, g["_idx"], 3] > 0),
                               ("white_band_group", band_groups, None)):
        for g in groups:
            if visf is None:
                v = np.stack([taus[:, None] >= tw.ravel()[g["_idx"]][None, :]], 0)[0]
            else:
                v = visf(g)
            lost = np.nonzero((v[:-1] & ~v[1:]).any(1))[0]
            if len(lost):
                repl.append(dict(kind=kind, id=g["id"], frames=[int(x + 1) for x in lost[:10]]))
    # t* の再投影
    ftar = NFR - 1
    rp, _ = cam.project(H[ftar, :, 0:3].astype(np.float64))
    tp, _ = cam.project(H[ftar, :, 3:6].astype(np.float64))
    byid = {c["id"]: c for c in claws}
    e_root = np.array([np.hypot(*(rp[i] - byid[ids_b[i]]["root_display"])) for i in range(nb)])
    e_tip = np.array([np.hypot(*(tp[i] - byid[ids_b[i]]["tip_display"])) for i in range(nb)])
    snaps = np.array([r["root_snap_display_px"] for r in bound])
    checks = dict(
        schema="GreatWave.DS32.id_checks/1",
        frames=NFR, hz=FPS, t_star_frame=int(round(12.0 * FPS)),
        bound=len(bound), unbound=[r["id"] for r in recs if not r.get("bound")],
        weighted_centroid_record_only=rec_w,
        weighted_centroid_note_ja="記録のみ：群の見える粒の重み付きの重心は、新しい粒（爪の成長 g、白の帯の 0.25 s の立ち上がり、飛沫の半径の 0.08 s の立ち上がり）が加わる所で動く。これは群の中の成長で、同じ粒の動きではないので、瞬間移動の判定には共通の粒の重心を使う",
        teleport_rule_ja="ID（爪の根元・先端、飛沫の粒）：(a) コマの間の動き > max(シートの頂点の動きの最大, 飛沫の粒の動きの最大)×%.1f + %.2f m、(b) 前後のコマの動きの大きい方の %.0f 倍 + %.2f m を超える突出。"
                         "両方のコマで見えるものだけ。群（爪の房・白の帯・飛沫）：両方のコマで見える粒（共通の粒）の重心の動きに同じ (a)・(b)" % (P["teleport_factor"], P["teleport_abs_m"], P["spike_factor"], P["spike_abs_m"]),
        teleports=tele, teleport_count=len(tele),
        flicker_rule_ja="見える → 見えないの変化（どの ID も t* までに消えない約束）と、2 回目の出現",
        flickers=flk, flicker_count=len(flk),
        group_member_lost=repl, group_member_lost_count=len(repl),
        growth_decreasing_samples=gdec,
        max_moves_m={k_: rnd(v_, 4) for k_, v_ in stats.items()},
        sheet_max_vertex_move_m=rnd(float(dsheet.max()), 4), spray_max_particle_move_m=rnd(float(dspray.max()), 4),
        reprojection_tstar_display_px=dict(root_max=rnd(e_root.max(), 3), root_p95=rnd(np.percentile(e_root, 95), 3),
                                           tip_max=rnd(e_tip.max(), 3), tip_p95=rnd(np.percentile(e_tip, 95), 3),
                                           root_snapped=int((snaps > 0).sum()), root_snap_max_px=rnd(snaps.max(), 2),
                                           note_ja="寄せた根元はその距離だけずれる。先端は射線の上に置くので 0 に近い（精度の層を含む t* の復号の丸め）"),
        pass_teleport_0=len(tele) == 0, pass_flicker_0=len(flk) == 0, pass_129_replace_0=len(repl) == 0,
        elapsed_s=round(time.time() - t0, 1),
    )
    jdump(out + "/ds32_id_checks.json", checks)

    H.tofile(out + "/ds32_claw_hist_f32.bin")
    G = np.concatenate([GC, GB, GS.astype(np.float32)], 1)
    G.tofile(out + "/ds32_group_hist_f32.bin")
    for g in claw_groups:
        g["prominent"] = len(g["members"]) >= P["prominent_min"]["claw"]
    for g in band_groups:
        g["prominent"] = g["vertices"] >= P["prominent_min"]["white_band"]
    for g in spray_groups:
        g["prominent"] = len(g["members"]) >= P["prominent_min"]["spray"]
    groups_all = [dict((k, v) for k, v in g.items() if not k.startswith("_")) for g in claw_groups + band_groups + spray_groups]
    for g in band_groups:
        pass
    ids = dict(
        schema="GreatWave.DS32.ids/1",
        number="設計32",
        note_ja=__doc__,
        params=P,
        sheet=dict(package=HERO.replace(REPO + "/", ""), rows=R, cols=C, body_cols=list(BODY), tstar_layer=hero.k["t_star_layer"],
                   pos_sha256=hero.k["pos_sha256"], pos_lo_sha256=hero.k["pos_lo_sha256"], twhite_sha256=sha(HERO + "/" + hero.k["twhite_file"]),
                   kstar_ja="最後の層（τ = 0）は K*′ R4（28R01F/kstar_final）。主役波の動きは F_final（DS27 ＋ 精度の層）",
                   uv_ja="sheet_rc = (行, 列) の連続の座標。sheet_uv = (列/(C−1), 行/(R−1))。uv3 = 29修正01 の色面の UV（uWarp(列), vWarp(行)）"),
        clock=dict(hz=FPS, frames=NFR, t0=0.0, timewarp=WARP.replace(REPO + "/", ""), timewarp_sha256=sha(WARP),
                   note_ja="コマ k は体験の時刻 t = k/30 s、τ = τ(t)（線形補間）。t ≥ 12 s は τ = 0（t* の保持）"),
        inputs=dict(claw_inventory=dict(path=(out + "/ds32_claw_inventory.json").replace(REPO + "/", ""), sha256=sha(out + "/ds32_claw_inventory.json")),
                    spray_table=dict(path=(SPRAY + "/ds31_spray_table.json").replace(REPO + "/", ""), sha256=sha(SPRAY + "/ds31_spray_table.json")),
                    spray_frames=dict(path=(SPRAY + "/" + sfr["file"]).replace(REPO + "/", ""), sha256=sfr["sha256"]),
                    colour_uvwarp=dict(path=UVW.replace(REPO + "/", ""), sha256=sha(UVW)),
                    painting_truth=dict(path=TRUTH.replace(REPO + "/", ""), sha256=sha(TRUTH))),
        claw_hist=dict(file="ds32_claw_hist_f32.bin", layout_ja="float32 リトルエンディアン、コマ × 爪（claws の順）× 8（根元 xyz、先端 xyz、g、見える 0/1）。ワールドの m",
                       count=nb, bytes=int(H.nbytes), sha256=sha(out + "/ds32_claw_hist_f32.bin")),
        group_hist=dict(file="ds32_group_hist_f32.bin", layout_ja="float32、コマ × 群（groups の順）× 4（重み付きの重心 xyz、重みの和。和 0 は見えない）",
                        count=len(groups_all), bytes=int(G.nbytes), sha256=sha(out + "/ds32_group_hist_f32.bin")),
        unbound_ja="右側の爪（C129〜C153）は右側の波（主役波のシートの外。設計30 の右の波は仮置きの静止形）にあるので結び付けない。低優先・未修正（ブラッシュアップの最後）",
        groups=groups_all,
        prominent_rule_ja="目立つ群（prominent）：爪の房は 3 本以上、白の帯は 120 頂点以上、飛沫は 4 粒以上。群の ID はすべての群に付け、設計33〜35 は目立つ群から使う",
        group_counts={k: dict(total=sum(1 for g in groups_all if g["kind"] == k), prominent=sum(1 for g in groups_all if g["kind"] == k and g["prominent"]))
                      for k in ("claw", "white_band", "spray")},
        band_vertex_members=dict(file="ds32_band_members_i32.bin", layout_ja="int32、群ごとに [頂点の数, 頂点の番号（行×列）…]、groups の白の帯の順"),
        spray_ids_ja="飛沫の粒の ID は設計31 の dot_id（ds31_spray_table.json の particles の順と同じ）",
        claws=[dict((k, v) for k, v in r.items() if not k.startswith("_")) for r in recs],
    )
    with open(out + "/ds32_band_members_i32.bin", "wb") as f:
        for bg in band_groups:
            np.array([len(bg["_idx"])], np.int32).tofile(f)
            bg["_idx"].astype(np.int32).tofile(f)
    jdump(out + "/ds32_ids.json", ids)
    np.save(out + "/_hist_meta.npy", np.array([taus, dsheet, dspray, bound_f]))
    print(json.dumps({k: v for k, v in checks.items() if k not in ("teleports", "flickers", "group_member_lost")}, ensure_ascii=False, default=_np)[:1500])
    print("teleports sample", tele[:5])
    print("flickers sample", flk[:5])
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
