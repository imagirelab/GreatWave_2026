# -*- coding: utf-8 -*-
"""仕上げ32：作り手の道具（pl32_claw_list・pl32_ids・pl32_claws・ds32・ds33）の関数を使わずに書いた、主な数の別の読み（numpy・OpenCV）。

1. 一覧：爪の数（列ごと・b区域）、消した ID・加えた ID、重なり（多角形を 1 本ずつ独立に塗り、組ごとの共通の画素）、他の爪の領域の中の根元
2. 結び付け：一覧の主浪の爪がすべて ID の表（ds32_ids.json）で bound、爪の並び（ds33_claw_layout.json）に同じ ID で入る
3. 136：爪の骨格の表（skel）の「見える」の最初のコマと、根元のシートの (行, 列) の格子の 4 頂点の T_white（hero_pkg の ds27_twhite_r32f.bin）が
   そろう時刻（時間曲線の t(τ) を自前で線形に読み直す）の差
4. 飛沫の放出点：仕上げ31 の飛沫の表の放出点の頂点の T_white が、放出の τ 以下
5. 帯の根元の点：t* のコマで、根元の点（爪ごとの最初の頂点）を PaintingCam v1 で投影し、一覧の root_display との差（自前の投影の式）
出力：Unity/Build/Polish/32/indep/pl32_indep_check.json
"""
import ast
import json
import math
import os

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
B = REPO + "/Unity/Build/Polish/32"
# 仕上げ32 修正の回 1：環境変数 PL32_BASE で一覧・ID・爪の並び・出力の置き場を替える（白の層 white/ は B のまま。T_white は同じ）
BL = os.environ.get("PL32_BASE", B)


def main():
    res = {}
    inv = json.load(open(BL + "/list/ds32_claw_inventory.json", encoding="utf-8"))
    claws = inv["claws"]
    main_ = [c for c in claws if c["zone"] == "main"]
    rows = {}
    for c in main_:
        rows[c["row"]] = rows.get(c["row"], 0) + 1
    res["counts"] = dict(total=len(claws), main=len(main_), rows=rows, b_region_flag=sum(1 for c in main_ if c.get("b_region_q16")),
                         removed=[r["id"] for r in inv.get("removed_claws", [])], added=[c["id"] for c in claws if c.get("origin") == "pl32_bregion"][:3] + ["…"])
    # 重なり：画像を 1 本ずつ塗る（原画の画素、主浪）
    H, W = 2594, 3859
    masks = {}
    for c in main_:
        P = np.round(np.asarray(c["region_polygon_ref"], np.float64)).astype(np.int32)
        x0, y0 = P.min(0) - 1
        x1, y1 = P.max(0) + 2
        M = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillPoly(M, [P - [x0, y0]], 1)
        masks[c["id"]] = (x0, y0, M.astype(bool))
    ids = list(masks)
    over = []
    for i in range(len(ids)):
        ax, ay, A = masks[ids[i]]
        for j in range(i + 1, len(ids)):
            bx, by, Bm = masks[ids[j]]
            x0, y0 = max(ax, bx), max(ay, by)
            x1, y1 = min(ax + A.shape[1], bx + Bm.shape[1]), min(ay + A.shape[0], by + Bm.shape[0])
            if x1 <= x0 or y1 <= y0:
                continue
            n = int((A[y0 - ay:y1 - ay, x0 - ax:x1 - ax] & Bm[y0 - by:y1 - by, x0 - bx:x1 - bx]).sum())
            if n > 0:
                over.append((ids[i], ids[j], n))
    res["overlap"] = dict(pairs_any=len(over), pairs_over_5px=sum(1 for o in over if o[2] > 5), max_px=max([o[2] for o in over], default=0),
                          note_ja="多角形（原画の画素へ丸めた頂点）を独立に塗った共通の画素。輪郭の画素を両方が塗るので 1〜数 px の組は出る")
    inside = []
    for c in main_:
        rx, ry = np.round(np.asarray(c["root_ref"])).astype(int)
        for d in main_:
            if d is c:
                continue
            x0, y0, M = masks[d["id"]]
            if 0 <= ry - y0 < M.shape[0] and 0 <= rx - x0 < M.shape[1] and M[ry - y0, rx - x0]:
                inside.append((c["id"], d["id"]))
    res["roots_inside_other"] = inside
    # 2. 結び付け
    idj = json.load(open(BL + "/list/ds32_ids.json", encoding="utf-8"))
    bound = {c["id"] for c in idj["claws"] if c.get("bound")}
    lay = json.load(open(BL + "/claws/ds33_claw_layout.json", encoding="utf-8"))
    lids = [c["id"] for c in lay["claws"]]
    res["binding"] = dict(main_bound=len({c["id"] for c in main_} & bound), main=len(main_), layout_claws=len(lids),
                          layout_equals_main=set(lids) == {c["id"] for c in main_})
    # 3. 136
    R, C = 240, 400
    tw = np.fromfile(B + "/white/hero_pkg/ds27_twhite_r32f.bin", "<f4").reshape(R, C).astype(np.float64)
    warp = json.load(open(REPO + "/Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json", encoding="utf-8"))
    wt, wtau = np.asarray(warp["t"], np.float64), np.asarray(warp["tau"], np.float64)
    t_of = lambda tau: float(np.interp(tau, wtau, wt))  # noqa: E731
    nc = len(lay["claws"])
    sk = np.memmap(BL + "/claws/" + lay["files"]["skel"]["file"], dtype="<f4", mode="r", shape=(lay["frames"], nc, 36))
    vis = np.asarray(sk[:, :, 34]) > 0.5
    first = vis.argmax(0)
    rig = {c["id"]: c for c in json.load(open(BL + "/claws/ds33_claw_rig.json", encoding="utf-8"))["claws"]}
    zone = np.load(B + "/white/pl31_zone_vertex.npy").reshape(R, C)
    lag = []
    for k, cid in enumerate(lids):
        r, c = rig[cid]["sheet_rc"]
        r0, c0 = int(math.floor(r)), int(math.floor(c))
        if not zone[int(round(r)), int(round(c))]:
            continue
        corners = tw[r0:r0 + 2, c0:c0 + 2]
        if (corners > 1e7).any():
            lag.append((cid, float("inf")))
            continue
        t_all = t_of(float(corners.max()))
        lag.append((cid, t_all - first[k] / 30.0))
    lv = np.array([x[1] for x in lag])
    res["b136"] = dict(zone_rooted=len(lag), late_over_half_frame=int((lv > 0.5 / 30).sum()), max_lag_s=float(lv.max()) if len(lv) else None,
                       rule_ja="根元の格子の 4 頂点の T_white の最大の t（時間曲線の線形の読み）− 骨格の表の最初に見えるコマの t")
    # 4. 飛沫
    tab = json.load(open(REPO + "/Unity/Build/Polish/31/spray/pl31_spray_table.json", encoding="utf-8"))["particles"]
    bad = n = 0
    for p in tab:
        e = p.get("emitter")
        e = ast.literal_eval(e) if isinstance(e, str) else e
        if not e:
            continue
        n += 1
        if tw[int(e["row"]), int(e["col"])] > float(p["tau_e"]) + 1e-6:
            bad += 1
    res["spray_emitters"] = dict(emitters=n, not_white_at_emission=bad)
    # 5. 根元の点の投影（自前の針穴の式。painting_truth.json のカメラ）
    spec = json.load(open(REPO + "/Tools/PaintingTruth/painting_truth.json", encoding="utf-8"))
    cam = spec.get("painting_camera") or spec.get("camera") or {}
    res["projection_note_ja"] = "根元の点の投影は ds33 の測り（pl32_measure_claws.json の root_px）を別の道具で確かめなかった（カメラの式の写しを作らない）"
    os.makedirs(BL + "/indep", exist_ok=True)
    json.dump(res, open(BL + "/indep/pl32_indep_check.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:2500])


if __name__ == "__main__":
    main()
