# -*- coding: utf-8 -*-
"""仕上げ33（設計33 爪の造形）：爪の帯を、根元を面に付けたまま面から立ち上がる「白い指」にする（numpy。Unity の描画ではない）。

名前の付いた美術の誘導（どれも帯の頂点の並びだけで決まり、主役波の色・材質と原画カメラからの投影の色は使わない。Q28）：

  - pl33_ray_relief（射線の向きの立ち上がり）：仕上げ32 修正の回 1 の帯（Build/Polish/32/fix01/claws）は面に沿って貼られ（面から 8.5 cm）、
    原画視点以外では白い面の上の白い帯で、側面・後ろ・真上・回り台から爪が読めなかった（仕上げ29 の限界 1、仕上げ32 の第 4 節）。
    そこで、輪の中心と先端を、t*（コマ 360）でその点から原画のカメラ（PaintingCam v1）へ向かう射線の向きへ h だけ動かす。
    射線の上を動くので、t* の原画視点の投影は変わらない（帯の幅は奥行きの比 (D − h)/D で縮めて、投影の幅も保つ）。原画視点で見える面の点から
    カメラへの射線は何にも遮られないので、t* で帯が面に刺さることはない。
    h(a) = H_REL × L × prof(a)（a は輪の位置 0 根元 → 1 先、L はそのコマの帯の弧長、上限 H_MAX）。
    prof(a) = smoothstep(a / A_RISE) × (1 − TIP_DROP × smoothstep((a − 0.6)/0.4))：根元から立ち上がり、先は少し面の側へ戻る（鉤）。
    L は成長とともに伸びるので、芽（短い帯）はほとんど立たず、伸びるにつれて立ち上がる（129・136・139 の成長の順は変えない）。
  - pl33_root_frame（根元の座標系で運ぶ）：射線の向きは t* の根元の白の円（面に付いた 9 点）の座標系 [e1 e2 n] で持ち、
    ほかのコマではそのコマの根元の円の座標系で向きを作り直す（面が回れば立ち上がりの向きも一緒に回る。138）。
    根元の円が潰れたコマ（見えない爪）は動かさない。
  - pl33_root_fixed：根元の点と根元の円は動かさない（105・137 の根元の値は仕上げ32 修正の回 1 と同じ）。
  - pl33_hook_web（鉤の内の水色の版）：原画の爪は、指の巻きの内側（鉤の内）を水色の版が埋め、白い指と墨版の線と水色が交互に並ぶ律動を作る
    （摺りの工程の調べ：爪の陰は水色の版。仕上げ32）。各爪の巻きの内側（t* の原画視点の中心線の曲がる側）の帯の縁から、内へ WEB_REL × 帯の幅
    （根元と先で細る）だけ広がる薄い膜を、帯の下（面の側へ帯の立ち上がりの半分）に置く。膜は帯と同じ並び（輪 × 8 ＋ 先 ＋ 根元の円）の別の項目
    （id は W ＋ 爪の id）で、PL33ClawLook が水色の版の段にし、縁の線を描かない。t* で膜の外の縁が原画視点の主役波の外（空）へ出る輪は、
    出なくなるまで幅を 0.7 倍ずつ縮める（原画視点の輪郭の関門を変えない）。帯の頂点だけで決まり、原画カメラからの投影の色は使わない。
  - pl33_tuft_web（b区域の房の水色の塊。［利用者の言葉］Q16・Q21）：b区域の爪（一覧の row b区域）だけ、膜の幅を WEB_REL_B 倍にして、
    隣り合う指の膜が重なって房ごとの水色の塊になるようにする（原画の b区域は、5〜10 本の指が同じ向きに巻き、指の間を水色の版が埋める）。

入力（Git 対象外）：Unity/Build/Polish/32/fix01/claws（ds33_claw_layout.json と同じ名前のファイル一式）
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/claws）。三角形・面の種類・骨格は入力の写し、コマの表だけを作り直し、並びの SHA-256 を書き直す。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl33/pl33_claw_relief.py [--h-rel 0.35] [--h-max 1.2] [--out ...]
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import time

import numpy as np

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/pl33")
import pl33_common as Q  # noqa: E402

REPO = "G:/Unity/GreatWave_2026_Fresh"
SRC = REPO + "/Unity/Build/Polish/32/fix01/claws"
OUT = REPO + "/Unity/Build/Polish/33/claws"
TRUTH = REPO + "/Tools/PaintingTruth/painting_truth.json"
K_STAR = 360
RING = 8


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def prof(a, a_rise, tip_drop):
    return smooth(a / a_rise) * (1.0 - tip_drop * smooth((a - 0.6) / 0.4))


def root_frames(C0, Q):
    """C0：(F,3) 根元の円の中心、Q：(F,8,3) 円。返り値 R：(F,3,3)（列が e1 e2 n）と、円の面積の目安 (F,)。"""
    v = Q - C0[:, None, :]
    cr = np.cross(v, np.roll(v, -1, axis=1)).sum(1)
    area = np.linalg.norm(cr, axis=1)
    n = cr / np.maximum(area, 1e-12)[:, None]
    e1 = v[:, 0, :] - (v[:, 0, :] * n).sum(1)[:, None] * n
    e1 /= np.maximum(np.linalg.norm(e1, axis=1), 1e-12)[:, None]
    e2 = np.cross(n, e1)
    R = np.stack([e1, e2, n], axis=2)
    return R, area


WEB_LIFT_SHARE = 0.5     # 膜の外の縁を帯の立ち上がりの何割だけ面の側へ下げるか
WEB_DD = (0.02, 0.40)    # その下げの範囲（m）


def hook_web(root, Yr, hr, dep, web_rel, st):
    """帯の輪 Yr（F, st, 8, 3。立ち上がりの後）から、巻きの内側の膜の頂点（F, 8·st + 11, 3）を作る。"""
    F = Yr.shape[0]
    cY = Yr.mean(2)
    E0, E4 = Yr[:, :, 0], Yr[:, :, 4]
    Nn = Yr[:, :, 2] - Yr[:, :, 6]
    Nn = Nn / np.maximum(np.linalg.norm(Nn, axis=2, keepdims=True), 1e-12)
    w = np.linalg.norm(E0 - E4, axis=2)
    # 巻きの内側：t* の原画視点の中心線の曲がる側
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
    dd = np.clip(WEB_LIFT_SHARE * hr, WEB_DD[0], WEB_DD[1])
    # t* で外の縁が原画視点の主役波の外へ出る輪は縮める
    # 膜の輪の外の縁 P2 と内の縁 P1 が、どちらも原画視点の主役波の中（5×5 の縮め）に入るまで、幅と下げを 0.7 倍ずつ縮める。
    # 帯の縁 E そのものが主役波の外（唇の縁で空へ出る爪）なら、その輪の膜は潰す（膜が空へはみ出して原画視点の輪郭を変えないため）
    def edges(scv):
        P1k = E[K_STAR] - (0.03 * scv)[:, None] * Nn[K_STAR]
        P2k = E[K_STAR] + (ww[K_STAR] * scv)[:, None] * lat[K_STAR] - (dd[K_STAR] * scv)[:, None] * Nn[K_STAR]
        return P1k, P2k
    sc = np.where(dep.inside(E[K_STAR]), 1.0, 0.0)
    for it in range(10):
        P1k, P2k = edges(sc)
        ins = dep.inside(P1k) & dep.inside(P2k)
        if ins.all():
            break
        sc = np.where(ins, sc, sc * 0.7)
    P1k, P2k = edges(sc)
    sc = np.where(dep.inside(P1k) & dep.inside(P2k), sc, 0.0)
    sc = np.minimum(sc, np.minimum(np.r_[sc[1:], sc[-1]], np.r_[sc[0], sc[:-1]]))   # 隣の輪と 3 点の最小（膜の縁のぎざぎざを防ぐ）
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
            "rings_shrunk": int((sc < 0.999).sum()), "width_tstar_m_max": round(float((ww[K_STAR] * sc).max()), 3)}
    return out, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--h-rel", type=float, default=0.35, help="立ち上がりの高さ／帯の弧長")
    ap.add_argument("--h-max", type=float, default=1.2, help="立ち上がりの上限（m）")
    ap.add_argument("--a-rise", type=float, default=0.55, help="立ち上がりが満ちる輪の位置")
    ap.add_argument("--tip-drop", type=float, default=0.25, help="先が面の側へ戻る割合")
    ap.add_argument("--web-rel", type=float, default=1.0, help="鉤の内の膜の幅／帯の幅（0 で膜を作らない）")
    ap.add_argument("--web-rel-b", type=float, default=1.8, help="b区域の爪の膜の幅／帯の幅（pl33_tuft_web：房の水色の塊）")
    ap.add_argument("--inv", default=REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json")
    a = ap.parse_args()
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    fr_path = os.path.join(a.src, lay["files"]["frames"]["file"])
    X = np.fromfile(fr_path, dtype=np.float32).reshape(F, V, 3).astype(np.float64)
    cam = np.array(json.load(open(TRUTH, encoding="utf-8"))["painting_cam"]["position"], dtype=np.float64)
    Y = X.copy()
    per = []
    webs = []
    rowof = {c["id"]: c.get("row") for c in json.load(open(a.inv, encoding="utf-8"))["claws"]}
    dep = None
    if a.web_rel > 0:
        hero = Q.U.K.Pkg(Q.HERO)
        dep = Q.TStarDepth(hero.world(0.0))
    for c in lay["claws"]:
        o, cnt, st = c["vert_offset"], c["vert_count"], c["stations"]
        assert cnt == RING * st + 11, c["id"]
        ring_idx = o + 1 + np.arange(st * RING).reshape(st, RING)
        tip_i = o + 1 + st * RING
        cen_i = tip_i + 1
        circ_i = cen_i + 1 + np.arange(RING)
        root = X[:, o, :]
        rings = X[:, ring_idx, :]                      # (F, st, 8, 3)
        ctr = rings.mean(2)                            # (F, st, 3)
        tip = X[:, tip_i, :]
        R, area = root_frames(X[:, cen_i, :], X[:, circ_i, :])
        ok = area > 1e-8
        # 弧長（根元 → 輪の中心 → 先）
        P = np.concatenate([root[:, None, :], ctr, tip[:, None, :]], axis=1)
        seg = np.linalg.norm(np.diff(P, axis=1), axis=2)
        L = seg.sum(1)                                 # (F,)
        # t* の射線の向き（カメラへ）を根元の座標系で持つ
        Pk = P[K_STAR, 1:]                             # 輪の中心と先 (st+1, 3)
        d = cam[None, :] - Pk
        D = np.linalg.norm(d, axis=1)
        d /= D[:, None]
        if not ok[K_STAR]:
            per.append({"id": c["id"], "skipped_ja": "t* で根元の円が潰れている"})
            continue
        dl = d @ R[K_STAR]                             # 局所の成分 (st+1, 3)：d = R dl → dl = R^T d
        dirs = np.einsum("fij,kj->fki", R, dl)         # (F, st+1, 3)
        av = np.concatenate([np.linspace(0, 1, st), [1.0]])
        pr = prof(av, a.a_rise, a.tip_drop)            # (st+1,)
        h = np.minimum(a.h_rel * L[:, None] * pr[None, :], a.h_max)   # (F, st+1)
        h[~ok] = 0.0
        off = h[:, :, None] * dirs
        kscale = 1.0 - h[:, :st] / D[None, :st]        # 奥行きの比で幅を縮める
        Y[:, ring_idx, :] = ctr[:, :, None, :] + kscale[:, :, None, None] * (rings - ctr[:, :, None, :]) + off[:, :st, None, :]
        Y[:, tip_i, :] = tip + off[:, st, :]
        rec = {"id": c["id"], "type": c.get("type"), "L_tstar_m": round(float(L[K_STAR]), 4),
               "h_max_tstar_m": round(float(h[K_STAR].max()), 4), "h_tip_tstar_m": round(float(h[K_STAR, -1]), 4)}
        if dep is not None:
            wrel = a.web_rel_b if rowof.get(c["id"]) == "b区域" else a.web_rel
            wv, info = hook_web(Y[:, o, :], Y[:, ring_idx, :], h[:, :st], dep, wrel, st)
            info["web_rel"] = wrel
            info["row"] = rowof.get(c["id"])
            if wv is not None:
                webs.append((c, wv))
            rec["web"] = info
        per.append(rec)
    os.makedirs(a.out, exist_ok=True)
    for k, v in lay["files"].items():
        if k != "frames":
            shutil.copyfile(os.path.join(a.src, v["file"]), os.path.join(a.out, v["file"]))
    out_fr = os.path.join(a.out, lay["files"]["frames"]["file"])
    nbase = len(lay["claws"])
    if webs:
        tris = [np.fromfile(os.path.join(a.src, lay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)]
        att = [np.fromfile(os.path.join(a.src, lay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)]
        sk = np.fromfile(os.path.join(a.src, lay["files"]["skel"]["file"]), dtype=np.float32).reshape(F, nbase, 36)
        off = V
        add = []
        for i, (c, wv) in enumerate(webs):
            nv = wv.shape[1]
            Tt, kd = Q.layout_tris(c["stations"], off)
            tris.append(Tt.astype(np.int32))
            att.append(np.stack([np.full(len(kd), nbase + i), np.ones(len(kd), np.int64)], 1).astype(np.uint16))
            lay["claws"].append({"id": "W" + c["id"], "index": nbase + i, "vert_offset": off, "vert_count": nv, "stations": c["stations"],
                                 "type": "W", "pl33_web_of": c["id"]})
            add.append(wv.astype(np.float32))
            off += nv
        Y = np.concatenate([Y.astype(np.float32)] + add, axis=1)
        T_all = np.concatenate(tris)
        A_all = np.concatenate(att)
        T_all.tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
        A_all.tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
        np.concatenate([sk, np.zeros((F, len(webs), 36), np.float32)], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
        lay["vertices"] = off
        lay["triangles"] = int(len(T_all))
        for k in ("tris", "tri_attr", "skel"):
            pth = os.path.join(a.out, lay["files"][k]["file"])
            lay["files"][k]["sha256"] = sha(pth)
            lay["files"][k]["bytes"] = os.path.getsize(pth)
    Y.astype(np.float32).tofile(out_fr)
    lay["files"]["frames"]["sha256"] = sha(out_fr)
    lay["files"]["frames"]["bytes"] = os.path.getsize(out_fr)
    lay["pl33_relief"] = {"note_ja": __doc__.strip().split("\n\n")[0], "src": os.path.relpath(a.src, REPO).replace("\\", "/"),
                          "src_frames_sha256": sha(fr_path), "h_rel": a.h_rel, "h_max_m": a.h_max, "a_rise": a.a_rise, "tip_drop": a.tip_drop,
                          "k_star": K_STAR, "camera": cam.tolist(), "web_rel": a.web_rel, "web_rel_b": a.web_rel_b, "webs": len(webs),
                          "web_note_ja": "pl33_hook_web：鉤の内の水色の版の膜（id W＋爪の id、type W）。PL33ClawLook が水色の版の段にし、縁の線を描かない"}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 記録：t* の投影の変化（輪の中心と先、表示の px）と立ち上がり
    spec = json.load(open(TRUTH, encoding="utf-8"))["painting_cam"]
    fwd = np.array(spec["target"]) - cam
    fwd /= np.linalg.norm(fwd)
    right = np.cross([0, 1, 0], fwd)
    right /= np.linalg.norm(right)
    up = np.cross(fwd, right)
    f = 540.0 / np.tan(np.radians(spec["vertical_fov_deg"]) / 2)

    def proj(p):
        q = p - cam
        z = q @ fwd
        return np.stack([960 + f * (q @ right) / z, 540 - f * (q @ up) / z], -1)
    dpx = np.linalg.norm(proj(Y[K_STAR, :V].astype(np.float64)) - proj(X[K_STAR]), axis=1)
    hs = np.array([p["h_max_tstar_m"] for p in per if "h_max_tstar_m" in p])
    summ = {"claws": len(per), "tstar_projection_shift_px_max": round(float(dpx.max()), 4), "tstar_projection_shift_px_p99": round(float(np.percentile(dpx, 99)), 4),
            "tstar_relief_m": {"min": round(float(hs.min()), 3), "median": round(float(np.median(hs)), 3), "max": round(float(hs.max()), 3)},
            "root_and_circle_unchanged": bool(np.allclose(Y[:, [c["vert_offset"] for c in lay["claws"][:nbase]]], X[:, [c["vert_offset"] for c in lay["claws"][:nbase]]], atol=1e-6)),
            "webs": len(webs),
            "elapsed_s": round(time.time() - t0, 1)}
    json.dump({"summary": summ, "claws": per}, open(os.path.join(a.out, "pl33_relief_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main()
