# -*- coding: utf-8 -*-
"""仕上げ33：爪の層（Build/Polish/33/claws）の幾何の検査（numpy。記録）。生成器と別の式で、出力のコマの表だけから数える。

項目（バックログ・計画 §5.3 の行）：
  - 全部の項目：NaN、根元に対する頂点のコマの間の動きの最大（瞬間移動の検査：> 0.5 m）、帯の弧長の 1 コマの跳び（> 0.3 m）。
  - 105・137（冠の爪）：根元の点とシートの頂点 (行, 列) の距離（全コマのうち 30 コマおき＋t*）。原画の爪の根元は仕上げ32 修正の回 1 と同じ（バイトで比べる）。
  - t* の原画視点：原画の爪の頂点の投影の変化（射線の上を動かした。表示の px）、冠の爪の頂点のうち原画視点で見えるもの（z バッファ）、
    膜の頂点のうち主役波の外で見えるもの。
  - 99（記録）：船側中央の爪 C095 の輪ごとの側面の厚み／正面の幅（t*）。全部の原画の爪の中央値も。
  - 204（記録）：帯の輪の上面の向き（φ 90° − 270° の向き）がコマの間で裏返る数と、伸びる間の幅が最初と最後の幅の範囲に収まるか。
  - 面への刺さり（記録）：t 9・10.5・12 s で、帯の輪の中心の、主役波のシートからの法線の高さが −5 cm より下の輪の割合（原画の爪・冠の爪）。
出力：Unity/Build/Polish/33/measure/pl33_checks.json
"""
import json
import os
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_common as Q  # noqa: E402

U = Q.U
CL = REPO + "/Unity/Build/Polish/33/claws"
SRC = REPO + "/Unity/Build/Polish/32/fix01/claws"
OUT = REPO + "/Unity/Build/Polish/33/measure"
RING = 8
K_STAR = 360


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    lay = json.load(open(CL + "/ds33_claw_layout.json", encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    X = np.memmap(CL + "/" + lay["files"]["frames"]["file"], dtype=np.float32, mode="r", shape=(F, V, 3))
    lay0 = json.load(open(SRC + "/ds33_claw_layout.json", encoding="utf-8"))
    X0 = np.memmap(SRC + "/" + lay0["files"]["frames"]["file"], dtype=np.float32, mode="r", shape=(F, lay0["vertices"], 3))
    kinds = {"C": [], "W": [], "K": []}
    for c in lay["claws"]:
        kinds["W" if c["id"].startswith("W") else ("K" if c["id"].startswith("K") else "C")].append(c)
    res = {"counts": {k: len(v) for k, v in kinds.items()}, "vertices": V, "triangles": lay["triangles"]}
    # 全部：NaN、瞬間移動、弧長の跳び
    mv = {}
    for k, cs in kinds.items():
        worst, worst_id, jumps, nan = 0.0, None, 0, 0
        arc_jump, arc_id = 0.0, None
        for c in cs:
            o, n, st = c["vert_offset"], c["vert_count"], c["stations"]
            A = np.asarray(X[:, o:o + n, :], dtype=np.float64)
            nan += int(np.isnan(A).sum())
            rel = A - A[:, :1, :]
            d = np.linalg.norm(np.diff(rel, axis=0), axis=2).max(1)
            if d.max() > worst:
                worst, worst_id = float(d.max()), c["id"]
            jumps += int((d > 0.5).sum())
            ctr = A[:, 1:1 + st * RING].reshape(F, st, RING, 3).mean(2)
            L = np.linalg.norm(np.diff(ctr, axis=1), axis=2).sum(1)
            dl = np.abs(np.diff(L))
            if dl.max() > arc_jump:
                arc_jump, arc_id = float(dl.max()), c["id"]
        mv[k] = {"nan": nan, "max_rel_move_m": round(worst, 4), "worst_id": worst_id, "teleports_gt_0p5m": jumps,
                 "max_arc_jump_m": round(arc_jump, 4), "arc_worst_id": arc_id}
    res["motion"] = mv
    # 原画の爪の根元・根元の円は仕上げ32 修正の回 1 と同じか
    same = True
    for c, c0 in zip(kinds["C"], lay0["claws"]):
        o, n, st = c["vert_offset"], c["vert_count"], c["stations"]
        a = np.asarray(X[:, [o] + list(range(o + 2 + st * RING, o + n))])
        b = np.asarray(X0[:, [c0["vert_offset"]] + list(range(c0["vert_offset"] + 2 + st * RING, c0["vert_offset"] + n))])
        same &= bool(np.array_equal(a, b))
    res["C_root_and_circle_identical_to_pl32fix01"] = same
    # 冠の爪の根元とシート
    hero = U.K.Pkg(Q.HERO)
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
    import ds31_white as W31
    wt, wtau = W31.load_warp(Q.WARP)
    crown = json.load(open(CL + "/pl33_crown.json", encoding="utf-8"))["crowns"]
    frames = sorted(set(list(range(0, F, 30)) + [K_STAR]))
    rd = 0.0
    taus = {}
    for f in frames:
        t = f / 30.0
        tau = 0.0 if t >= 12 - 1e-9 else float(np.interp(t, wt, wtau))
        taus[f] = tau
        Xs = hero.world(tau)
        for c, cw in zip(kinds["K"], crown):
            rd = max(rd, float(np.linalg.norm(np.asarray(X[f, c["vert_offset"]], np.float64) - Xs[cw["r"], cw["c"]])))
    res["crown_root_to_sheet_vertex_max_m"] = rd
    # t* の原画視点
    XS = hero.world(0.0)
    dep = Q.TStarDepth(XS)
    Y = np.asarray(X[K_STAR], np.float64)
    Y0 = np.asarray(X0[K_STAR], np.float64)
    xyC, _ = dep.cam.project(Y[:lay0["vertices"]])
    xy0, _ = dep.cam.project(Y0)
    res["C_tstar_projection_shift_px_max"] = round(float(np.linalg.norm(xyC - xy0, axis=1).max()), 5)
    kv = []
    for c in kinds["K"]:
        P = Y[c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
        kv.append(int(dep.visible(P, 0.05).sum()))
    res["crown_tstar_vertices_visible_from_painting_cam"] = {"total": int(sum(kv)), "claws_with_any": int(sum(1 for v in kv if v > 0))}
    wv = []
    for c in kinds["W"]:
        P = Y[c["vert_offset"]:c["vert_offset"] + c["vert_count"]]
        vis = dep.visible(P, 0.05)
        out = ~dep.inside(P)
        wv.append(int((vis & out).sum()))
    res["web_tstar_vertices_visible_and_outside_wave"] = {"total": int(sum(wv)), "webs_with_any": int(sum(1 for v in wv if v > 0)),
                                                         "note_ja": "潰した輪（帯の縁が主役波の外の輪は膜の幅 0 にした）の頂点は帯の縁の上の 1 点に集まり、面積を持たない"}
    # 99：C095 の厚み／幅
    def thick_ratio(c, f=K_STAR):
        o, st = c["vert_offset"], c["stations"]
        R = np.asarray(X[f, o + 1:o + 1 + st * RING], np.float64).reshape(st, RING, 3)
        w = np.linalg.norm(R[:, 0] - R[:, 4], axis=1)
        th = np.linalg.norm(R[:, 2] - R[:, 6], axis=1)
        return th / np.maximum(w, 1e-9), w
    c95 = [c for c in kinds["C"] if c["id"] == "C095"]
    r95, w95 = thick_ratio(c95[0])
    allr = np.concatenate([thick_ratio(c)[0][:-2] for c in kinds["C"]])
    res["99_C095_side_thickness_over_front_width"] = {"rings_min": round(float(r95[:-2].min()), 4), "rings_max": round(float(r95[:-2].max()), 4),
                                                      "median": round(float(np.median(r95[:-2])), 4), "all_C_claws_median": round(float(np.median(allr)), 4),
                                                      "all_C_claws_p5_p95": [round(float(np.percentile(allr, 5)), 4), round(float(np.percentile(allr, 95)), 4)],
                                                      "note_ja": "先の 2 輪（閉じ）を除く。仕上げ33 は帯の断面（幅と厚みの比）を変えていない（立ち上げは輪をそのまま動かし、奥行きの比で一様に縮めた）"}
    crown_r = np.concatenate([thick_ratio(c)[0][:-2] for c in kinds["K"]])
    res["crown_thickness_over_width_median"] = round(float(np.median(crown_r)), 4)
    # 204：上面の向きの裏返りと、幅の範囲
    flips, outside = 0, 0
    flips_by = {"C": 0, "K": 0}
    flip_ids = {}
    for c in kinds["C"] + kinds["K"]:
        o, st = c["vert_offset"], c["stations"]
        R = np.asarray(X[:, o + 1:o + 1 + st * RING], np.float64).reshape(F, st, RING, 3)
        up = R[:, :, 2] - R[:, :, 6]
        nrm = np.linalg.norm(up, axis=2)
        ok = (nrm[1:] > 1e-4) & (nrm[:-1] > 1e-4)
        dots = (up[1:] * up[:-1]).sum(2)
        nf = int(((dots < 0) & ok).sum())
        flips += nf
        flips_by["K" if c["id"].startswith("K") else "C"] += nf
        if nf:
            flip_ids[c["id"]] = nf
        w = np.linalg.norm(R[:, :, 0] - R[:, :, 4], axis=2).max(1)
        vis = w > 1e-4
        if vis.sum() > 2:
            wv_ = w[vis]
            lo, hi = min(wv_[0], wv_[-1]), max(wv_[0], wv_[-1])
            outside += int(((wv_ > hi * 1.02 + 1e-3) | (wv_ < lo * 0.98 - 1e-3)).sum())
    res["204_ring_up_flips_between_frames"] = flips
    res["204_ring_up_flips_by_kind"] = flips_by
    res["204_ring_up_flips_ids"] = flip_ids
    # 計画 §5.3：シートに一部が隠れる爪（原画視点 t* で輪の中心が見える割合 < 0.8）。前（仕上げ32 修正の回 1）と後
    vf = {}
    for nm, XX, cs in (("before", X0, lay0["claws"]), ("after", X, kinds["C"])):
        low = []
        for c in cs:
            o, st = c["vert_offset"], c["stations"]
            A = np.asarray(XX[K_STAR, o + 1:o + 1 + st * RING], np.float64).reshape(st, RING, 3)
            top = A[:, 2]
            fr = float(dep.visible(top, 0.10).mean())
            if fr < 0.8:
                low.append((c["id"], round(fr, 3)))
        vf[nm] = {"claws_visible_fraction_lt_0p8": len(low), "ids": low[:40]}
    res["claws_partly_hidden_by_sheet_tstar"] = vf
    res["204_frames_width_outside_first_last_range"] = outside
    # 面への刺さり
    Vs = XS.reshape(-1, 3)
    tree = cKDTree(Vs)
    pen = {}
    for f in (270, 315, 360):
        tau = taus.get(f)
        if tau is None:
            t = f / 30.0
            tau = 0.0 if t >= 12 - 1e-9 else float(np.interp(t, wt, wtau))
        Xs = hero.world(tau)
        Rr, Cc = Xs.shape[:2]
        treef = cKDTree(Xs.reshape(-1, 3))
        for k in ("C", "K"):
            below, tot = 0, 0
            for c in kinds[k]:
                o, st = c["vert_offset"], c["stations"]
                A = np.asarray(X[f, o + 1:o + 1 + st * RING], np.float64).reshape(st, RING, 3).mean(1)
                if np.linalg.norm(A[-1] - A[0]) < 1e-4:
                    continue
                _, i0 = treef.query(np.asarray(X[f, o], np.float64))
                rc0 = np.tile([[i0 // Cc, i0 % Cc]], (st, 1)).astype(np.float64)
                _, _, hh, tang = U.project_to_sheet(Xs, A, rc0)
                okp = tang < 0.3
                below += int(((hh < -0.05) & okp).sum())
                tot += int(okp.sum())
            pen["%s_t%03d" % (k, int(round(f / 3)))] = {"rings_below_surface": below, "rings_checked": tot,
                                                        "fraction": round(below / max(1, tot), 4)}
    res["penetration_ring_centres"] = pen
    res["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(res, open(OUT + "/pl33_checks.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
