# -*- coding: utf-8 -*-
"""設計43：船底のサンプルで、船用水面データ（Unity の DS43BoatWater が返した高さ）と表示面（同じコマに GPU で描いた 3 枚のシートの頂点を
読み戻したもの）の高さの差、位置と時刻のずれ、座席の目が水の上にあるかを測る（numpy。Unity の読み手のコードは使わない）。

入力（Git 対象外）：Unity/Build/Design/43/boatwater/unity/ds43_frames.jsonl・gpu_{hero,near,far}.f32・ds43_unity_report.json
出力：Unity/Build/Design/43/boatwater/measure/ds43_measure.json・ds43_series.npz
使い方：py -3.10 -B Tools/GWWaveGen/ds43/ds43_measure.py
"""
import json
import os
import time

import numpy as np

import ds43_common as C

U = os.path.join(C.OUT, "unity")
M = os.path.join(C.OUT, "measure")


def hits_grad(V, r1, c0, c1, Q):
    """鉛直の線と三角形の交わり：点ごとに [(y, dy/dx, dy/dz), ...]。"""
    A = V[:r1, c0:c1]; B = V[1:r1 + 1, c0:c1]; Cc = V[:r1, c0 + 1:c1 + 1]; D = V[1:r1 + 1, c0 + 1:c1 + 1]
    xs = np.stack([A[..., 0], B[..., 0], Cc[..., 0], D[..., 0]], 0)
    zs = np.stack([A[..., 2], B[..., 2], Cc[..., 2], D[..., 2]], 0)
    xmin, xmax, zmin, zmax = xs.min(0), xs.max(0), zs.min(0), zs.max(0)
    out = [[] for _ in range(len(Q))]
    cand = np.nonzero((xmax >= Q[:, 0].min()) & (xmin <= Q[:, 0].max()) & (zmax >= Q[:, 1].min()) & (zmin <= Q[:, 1].max()))
    if len(cand[0]) == 0:
        return out
    rr, cc = cand
    for tri in (0, 1):
        P0, P1, P2 = (A[rr, cc], B[rr, cc], Cc[rr, cc]) if tri == 0 else (Cc[rr, cc], B[rr, cc], D[rr, cc])
        e1 = P1 - P0; e2 = P2 - P0
        det = e1[:, 0] * e2[:, 2] - e1[:, 2] * e2[:, 0]
        ok = np.abs(det) > 1e-12
        dsafe = np.where(ok, det, 1.0)
        # 面の傾き：y = y0 + gx (x − x0) + gz (z − z0)
        gx = (e1[:, 1] * e2[:, 2] - e2[:, 1] * e1[:, 2]) / dsafe
        gz = (e2[:, 1] * e1[:, 0] - e1[:, 1] * e2[:, 0]) / dsafe
        for n in range(len(Q)):
            dx = Q[n, 0] - P0[:, 0]; dz = Q[n, 1] - P0[:, 2]
            u = (dx * e2[:, 2] - dz * e2[:, 0]) / dsafe
            v = (e1[:, 0] * dz - e1[:, 2] * dx) / dsafe
            m = ok & (u >= -1e-7) & (v >= -1e-7) & (u + v <= 1 + 1e-7)
            if m.any():
                y = P0[m, 1] + u[m] * e1[m, 1] + v[m] * e2[m, 1]
                for a, b, c in zip(y, gx[m], gz[m]):
                    out[n].append((float(a), float(b), float(c)))
    return out


def display(Vs, wins, Q):
    """3 枚のシートの交わりをまとめ、点ごとに（高さの昇順の配列、最も低い交わりの傾き）を返す。"""
    allh = [[] for _ in range(len(Q))]
    for V, (r1, c0, c1) in zip(Vs, wins):
        for n, h in enumerate(hits_grad(V, r1, c0, c1, Q)):
            allh[n].extend(h)
    res = []
    for h in allh:
        h = sorted(h)
        ys, g = [], None
        for y, gx, gz in h:
            if not ys or y - ys[-1] > 1e-3:
                ys.append(y)
                if g is None:
                    g = (gx, gz)
        res.append((np.array(ys), g))
    return res


def main():
    t0 = time.time()
    os.makedirs(M, exist_ok=True)
    rep = C.load_json(os.path.join(U, "ds43_unity_report.json"))
    frames = [json.loads(l) for l in open(os.path.join(U, "ds43_frames.jsonl"), encoding="utf-8")]
    F = len(frames)
    hero, near, far = C.load_sheets()
    cnt = rep["sheetVertexCounts"]
    shapes = [(hero.R, hero.C), (near.R, near.C), (far.R, far.C)]
    gpu = [np.memmap(os.path.join(U, "gpu_%s.f32" % nm), dtype="<f4", mode="r", shape=(F, r * c, 3)) for nm, (r, c) in zip(("hero", "near", "far"), shapes)]
    wins = [(hero.r1, hero.c0, hero.c1), (near.r1, near.c0, near.c1), (far.r1, far.c0, far.c1)]

    def Vs_at(fi):
        return [gpu[s][fi].astype(np.float64).reshape(shapes[s][0], shapes[s][1], 3) for s in range(3)]

    keys = [b["key"] for b in frames[0]["boats"]]
    NS = len(frames[0]["boats"][0]["s"])
    hb = np.full((F, 3, NS), np.nan); hd = np.full((F, 3, NS), np.nan); nb = np.zeros((F, 3, NS), int); nd = np.zeros((F, 3, NS), int)
    gxz = np.full((F, 3, NS, 2), np.nan); P = np.zeros((F, 3, NS, 3))
    eye = np.zeros((F, 3)); eye_hits_b = []; eye_hits_d = []
    tau_play = np.array([f["tauPlay"] for f in frames]); tau_w = np.array([f["tauWater"] for f in frames]); tau_s = np.array([f["tauSheets"] for f in frames])
    tt = np.array([f["t"] for f in frames])
    wet = np.array([[b["wet"] for b in f["boats"]] for f in frames])
    pos = np.array([[b["pos"] for b in f["boats"]] for f in frames])
    for fi, f in enumerate(frames):
        Vs = Vs_at(fi)
        for bi, b in enumerate(f["boats"]):
            S = np.array([[np.nan if v is None else v for v in s] for s in b["s"]], np.float64)
            P[fi, bi] = S[:, :3]; hb[fi, bi] = S[:, 3]; nb[fi, bi] = S[:, 4].astype(int)
            res = display(Vs, wins, S[:, [0, 2]])
            for k, (ys, g) in enumerate(res):
                nd[fi, bi, k] = len(ys)
                if len(ys):
                    hd[fi, bi, k] = ys[0]; gxz[fi, bi, k] = g
            if "eye" in b:
                e = np.array(b["eye"]); eye[fi] = e
                eye_hits_b.append(b["eyeHits"])
                ys, _ = display(Vs, wins, e[None, [0, 2]])[0]
                eye_hits_d.append(ys.tolist())
        if fi % 60 == 0:
            print("frame %d / %d  %.1f s" % (fi, F, time.time() - t0), flush=True)
    diff = hb - hd
    single = (nd == 1) & (nb == 1)
    multi = (nd >= 2)
    out = dict(number="設計43", part="boatwater", frames=F, samples_per_boat=NS, boats=keys,
               sample_note_ja="船底のサンプル = 浮力点 10（設計42 の表の点）＋ 船底の平面（根の局所 y = 0）の 9 × 3 の格子（縦 ±0.42 L、横 ±0.3 B）。各コマの船の姿勢で世界へ写した点の xz で比べる",
               display_note_ja="表示面 = 同じコマに GPU で描いた 3 枚のシート（主役波は本体の列 18〜394 の四角、near は全部、far はすその四角を除く）の頂点（DS27KeyposeCapture の読み戻し）と、点の鉛直の線の交わり（numpy。Unity の読み手のコードは使わない）。一価 = 交わりが 1 つ、砕波域 = 交わりが 2 つ以上（唇・巻き込みの下）")
    per = {}
    for bi, k in enumerate(keys):
        d = diff[:, bi]; s1 = single[:, bi]; mu = multi[:, bi]
        per[k] = dict(
            nonbreaking_samples=int(s1.sum()),
            nonbreaking_absmax_m=float(np.nanmax(np.abs(d[s1]))) if s1.any() else None,
            nonbreaking_p99_m=float(np.nanpercentile(np.abs(d[s1]), 99)) if s1.any() else None,
            nonbreaking_rms_m=float(np.sqrt(np.nanmean(d[s1] ** 2))) if s1.any() else None,
            breaking_samples=int(mu.sum()),
            breaking_underside_absmax_m=float(np.nanmax(np.abs(d[mu]))) if mu.any() else None,
            breaking_frames=[int(v) for v in np.nonzero(mu.any(1))[0][[0, -1]]] if mu.any() else None,
            hit_count_mismatch=int((nd[:, bi] != nb[:, bi]).sum()),
            no_display_hit=int((nd[:, bi] == 0).sum()),
            wet_zero_frames=int((wet[:, bi] == 0).sum()),
            wet_zero_t=[float(tt[i]) for i in np.nonzero(wet[:, bi] == 0)[0][[0, -1]]] if (wet[:, bi] == 0).any() else None)
    out["per_boat"] = per
    allnb = np.abs(diff[single])
    out["acceptance_hull_vs_display"] = dict(criterion_m=0.05, nonbreaking_samples=int(single.sum()), absmax_m=float(np.nanmax(allnb)),
                                             p99_m=float(np.nanpercentile(allnb, 99)), pass_=bool(np.nanmax(allnb) <= 0.05))
    # 時刻のずれ
    dt_frame = np.abs(np.diff(tau_play)); dt_frame = np.where(dt_frame > 0, dt_frame, np.nan)
    off = np.abs(tau_w - tau_play)
    offs = np.abs(tau_s - tau_play[:, None])
    # 時刻を L コマずらした表示面との差（一価のコマ、浮力点 10 点）
    lag_rms = {}
    idx_ok = [fi for fi in range(3, F - 3) if single[fi, :, :10].all() and tau_play[fi] < 0 and tau_play[fi] > tau_play[0]]
    sub = idx_ok[::3]
    for L in (-3, -2, -1, 0, 1, 2, 3):
        errs = []
        for fi in sub:
            Vs = Vs_at(fi + L)
            for bi in range(3):
                Q = P[fi, bi, :10][:, [0, 2]]
                res = display(Vs, wins, Q)
                for k, (ys, _) in enumerate(res):
                    if len(ys):
                        errs.append(hb[fi, bi, k] - ys[0])
        e = np.array(errs)
        lag_rms[str(L)] = float(np.sqrt(np.mean(e ** 2)))
    best = min(lag_rms, key=lambda k: lag_rms[k])
    out["acceptance_time_offset"] = dict(
        criterion_frames=0,
        tau_water_minus_play_absmax_s=float(np.nanmax(off)), tau_sheets_minus_play_absmax_s=float(np.nanmax(offs)),
        frame_step_tau_median_s=float(np.nanmedian(dt_frame)),
        offset_frames_from_tau=float(np.nanmax(off) / np.nanmin(dt_frame[np.isfinite(dt_frame)])) if np.isfinite(dt_frame).any() else 0.0,
        lag_search_rms_m=lag_rms, lag_search_frames_used=len(sub), best_lag_frames=int(best), pass_=bool(np.nanmax(off) == 0.0 and np.nanmax(offs) == 0.0 and int(best) == 0),
        note_ja="τ は再生器（DS30SinglePlayback.Tau）・各シートが描いた τ（AppliedTau）・船用水面データが使った τ（TauUsed）をコマごとに記録。ずらしの探索は、浮力点の船用水面データの高さを、L コマずらした表示面と比べた二乗平均（一価で動いている区間、3 コマおき）")
    # 位置のずれ：Δh ≈ g·δ の最小二乗（一価のサンプル）
    g = gxz[single]; dh = diff[single]
    okg = np.isfinite(g).all(1) & np.isfinite(dh)
    Gm = g[okg]; y = dh[okg]
    if len(y) > 10 and np.linalg.matrix_rank(Gm) == 2:
        delta, *_ = np.linalg.lstsq(Gm, y, rcond=None)
    else:
        delta = np.array([np.nan, np.nan])
    out["position_offset"] = dict(delta_xz_m=[float(delta[0]), float(delta[1])], samples=int(okg.sum()),
                                  slope_abs_p95=float(np.percentile(np.hypot(Gm[:, 0], Gm[:, 1]), 95)) if len(Gm) else None,
                                  note_ja="表示面の傾き g（交わった三角形の面）から、船用水面データと表示面の高さの差を水平のずれ δ で説明できるかの最小二乗（δ ≈ 0 なら位置のずれなし）")
    # 座席の目
    eh = []
    for fi in range(F):
        ys = np.array(eye_hits_d[fi]); e = eye[fi, 1]
        above = int((ys > e).sum()); below = ys[ys <= e]
        in_water = (above % 2 == 1)
        eh.append((in_water, float(e - below.max()) if len(below) else np.nan, float(e - ys.min()) if len(ys) else np.nan, above))
    iw = np.array([v[0] for v in eh]); mg = np.array([v[1] for v in eh]); mu_ = np.array([v[2] for v in eh]); ab = np.array([v[3] for v in eh])
    out["seat_eye"] = dict(frames=F, in_water_frames=int(iw.sum()), margin_min_m=float(np.nanmin(mg)), margin_min_t=float(tt[int(np.nanargmin(mg))]),
                           frames_with_surface_above_eye=int((ab > 0).sum()), unity_vs_numpy_eye_hits_same=bool(all(len(a) == len(b) for a, b in zip(eye_hits_b, eye_hits_d))),
                           pass_=bool(iw.sum() == 0),
                           note_ja="目の水平の位置の鉛直の線と表示面の交わり（numpy）。目より上の交わりの数が奇数なら水の中。余裕 = 目 − 目の下の最も近い面")
    # 表示面の読み戻しと numpy の復号の照合（独立の経路）
    chk = []
    for fi in range(0, F, 30):
        tau = tau_play[fi]
        for s, sh in enumerate((hero, near, far)):
            Wn = sh.world(tau)
            d = np.abs(Wn - gpu[s][fi].reshape(sh.R, sh.C, 3)).max()
            chk.append(float(d))
    out["gpu_vs_numpy_decode_absmax_m"] = float(max(chk))
    out["seconds"] = round(time.time() - t0, 1)
    C.save_json(os.path.join(M, "ds43_measure.json"), out)
    np.savez_compressed(os.path.join(M, "ds43_series.npz"), t=tt, tau=tau_play, hb=hb, hd=hd, nb=nb, nd=nd, P=P, eye=eye, eye_margin=mg, eye_in_water=iw, pos=pos, wet=wet, keys=np.array(keys))
    print(json.dumps({k: v for k, v in out.items() if k not in ("sample_note_ja", "display_note_ja")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
