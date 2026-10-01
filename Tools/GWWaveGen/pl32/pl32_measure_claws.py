# -*- coding: utf-8 -*-
"""仕上げ32：バックログ 95〜98・122〜128・144・145・261 を、t* の原画視点で爪ごとに測る（numpy。Unity の描画ではない。記録のみの項目を含む）。

出典：美術優先の作業計画の番号33 の受入（95〜98 船側中央の爪、123〜126 代表10形の長短・幅・先端の向き・左右の輪郭 ≤4 px・順序、122/127/128 各列の根元と先端 ≤4 px、
その他の爪ごとの ≤4 px（144/145/261）は記録のみ）。バックログの文言はリポジトリの外（バックログ_価値優先版.xlsx）なので、この計画の書き方で数える。

やり方：爪の帯のメッシュの t* のコマ（コマ 360）の頂点を PaintingCam v1 で表示の画素へ投影し、爪ごとに三角形を塗った影（爪の画素。主役波の面による隠れは数えない）を作る。
  - 根元・先端の差（122/127/128）：帯の根元の点と先端の点の投影と、一覧の root_display・tip_display の距離。
  - 輪郭（123〜126 の左右の輪郭、144/145/261）：爪の影の外周と、一覧の領域の多角形（D25 を決め直した定義）の外周の、中心線の左右それぞれの対称 Hausdorff（表示 px）。
  - 長さ：帯の骨格（関節を通る曲線）の投影の長さと、一覧の中心線の長さ（表示 px）。代表10形の長短の順序（一覧の長さの順との Spearman）。
  - 幅：影の中心線の上の幅の中央値（距離変換 × 2）と、一覧の領域の同じ読みの比。根元の幅（根元から 10〜30%）と先端の近くの幅（70〜90%）。
  - 先端の向き：中心線の先端の 20% の向き（画面の角度。0° 右、90° 下）の、帯と一覧の差。
  - 船側中央の爪（D8 の第一候補 C095）：95 根元が先より広い、97 先が下へ曲がる（先端の向き 30〜150°）、98 根元から下側へ延びる（根元 → 先端の弦の向き 30〜150°）。96 は文言が手元にないので記録しない。
前（--before）と後（--after）の爪の並びを同じ読みで測る。
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

A_DISP, X_OFF = 0.416345, 156.66153
REPS = ["C028", "C015", "C044", "C006", "C011", "C075", "C064", "C106", "C111", "C092"]
CENTRE = "C095"


def r2d(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + X_OFF, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


def cumlen(C):
    C = np.asarray(C, np.float64)
    return np.r_[0.0, np.cumsum(np.hypot(*np.diff(C, axis=0).T))]


def resample(C, n):
    s = cumlen(C)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, C[:, 0]), np.interp(t, s, C[:, 1])], 1)


def side_hausdorff(maskA, polyB, cl, off, scale):
    """マスク A の外周と多角形 B の外周の、中心線の左右それぞれの対称 Hausdorff（表示 px）。scale 倍の格子で数える。"""
    H, W = maskA.shape
    B = np.zeros((H, W), np.uint8)
    cv2.fillPoly(B, [np.round((np.asarray(polyB) - off) * scale).astype(np.int32)], 1)
    res = {}
    edges = []
    for M in (maskA.astype(np.uint8), B):
        e = M - cv2.erode(M, np.ones((3, 3), np.uint8))
        edges.append(np.argwhere(e > 0)[:, ::-1].astype(np.float64))
    if len(edges[0]) == 0 or len(edges[1]) == 0:
        return None
    clp = (np.asarray(cl) - off) * scale
    t = np.gradient(clp, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)

    def side(P):
        d = np.linalg.norm(P[:, None, :] - clp[None, :, :], axis=-1)
        k = d.argmin(1)
        v = P - clp[k]
        return np.sign(t[k, 0] * v[:, 1] - t[k, 1] * v[:, 0])
    sA, sB = side(edges[0]), side(edges[1])
    for nm, sg in (("left", -1), ("right", 1)):
        a_, b_ = edges[0][sA == sg], edges[1][sB == sg]
        if len(a_) == 0 or len(b_) == 0:
            res[nm] = None
            continue
        dab = np.sqrt(((a_[:, None, :] - b_[None, :, :]) ** 2).sum(-1))
        res[nm] = float(max(dab.min(1).max(), dab.min(0).max()) / scale)
    return res


def measure(claw_dir, inv_path, frame=360, scale=4):
    lay = json.load(open(os.path.join(claw_dir, "ds33_claw_layout.json"), encoding="utf-8"))
    nv = lay["vertices"]
    V = np.memmap(os.path.join(claw_dir, lay["files"]["frames"]["file"]), dtype="<f4", mode="r", shape=(lay["frames"], nv, 3))[frame].astype(np.float64)
    T = np.fromfile(os.path.join(claw_dir, lay["files"]["tris"]["file"]), "<i4").reshape(-1, 3)
    At = np.fromfile(os.path.join(claw_dir, lay["files"]["tri_attr"]["file"]), "<u2").reshape(-1, 2)
    nc = len(lay["claws"])
    SK = np.memmap(os.path.join(claw_dir, lay["files"]["skel"]["file"]), dtype="<f4", mode="r", shape=(lay["frames"], nc, 36))[frame].astype(np.float64)
    rig = json.load(open(os.path.join(claw_dir, "ds33_claw_rig.json"), encoding="utf-8"))
    segs = {c["id"]: c["segments"] for c in rig["claws"]}
    spec = U.jload(U.TRUTH)
    cam = U.C27.Cam(spec)
    q, _ = cam.project(V)
    inv = {c["id"]: c for c in json.load(open(inv_path, encoding="utf-8"))["claws"]}
    out = {}
    for i, ce in enumerate(lay["claws"]):
        cid = ce["id"]
        c = inv.get(cid)
        if c is None:
            continue
        o, n = ce["vert_offset"], ce["vert_count"]
        tri = T[(At[:, 0] == i) & (At[:, 1] != 2)]
        P = q[tri]  # m × 3 × 2
        lo = np.floor(np.minimum(P.reshape(-1, 2).min(0), r2d(np.asarray(c["region_polygon_ref"])).min(0))) - 6
        hi = np.ceil(np.maximum(P.reshape(-1, 2).max(0), r2d(np.asarray(c["region_polygon_ref"])).max(0))) + 6
        W_, H_ = int((hi[0] - lo[0]) * scale), int((hi[1] - lo[1]) * scale)
        if W_ <= 0 or H_ <= 0 or W_ * H_ > 4e6:
            continue
        M = np.zeros((H_, W_), np.uint8)
        for t3 in P:
            cv2.fillConvexPoly(M, np.round((t3 - lo) * scale).astype(np.int32), 1)
        root_q, tip_q = q[o], q[o + n - 10]
        e_root = float(np.hypot(*(root_q - np.asarray(c["root_display"]))))
        e_tip = float(np.hypot(*(tip_q - np.asarray(c["tip_display"]))))
        nj = segs[cid] + 1
        J = SK[i, 0:3 * nj].reshape(nj, 3)
        Pd, _ = U.catmull_rom(J, 16)
        sk2, _ = cam.project(Pd)
        cl_inv = r2d(np.asarray(c["centerline_ref"]))
        L3 = float(cumlen(sk2)[-1]); Li = float(cumlen(cl_inv)[-1])
        hd = side_hausdorff(M, r2d(np.asarray(c["region_polygon_ref"])), cl_inv, lo, scale)
        # 幅：中心線の上の距離変換 × 2（爪の影と一覧の領域）
        DT = cv2.distanceTransform(M, cv2.DIST_L2, 5) / scale
        Bm = np.zeros_like(M)
        cv2.fillPoly(Bm, [np.round((r2d(np.asarray(c["region_polygon_ref"])) - lo) * scale).astype(np.int32)], 1)
        DTb = cv2.distanceTransform(Bm, cv2.DIST_L2, 5) / scale
        cls = resample(cl_inv, 41)
        qi = np.clip(np.round((cls - lo) * scale).astype(int), 0, [W_ - 1, H_ - 1])
        wa = 2 * DT[qi[:, 1], qi[:, 0]]
        wb = 2 * DTb[qi[:, 1], qi[:, 0]]
        sel = (np.linspace(0, 1, 41) >= 0.1) & (np.linspace(0, 1, 41) <= 0.9)
        wr = float(np.median(wa[sel]) / max(np.median(wb[sel]), 1e-6))

        def tipdir(C):
            s = cumlen(C)
            k = np.searchsorted(s, 0.8 * s[-1])
            v = C[-1] - C[min(k, len(C) - 2)]
            return math.degrees(math.atan2(v[1], v[0]))
        da = (tipdir(sk2) - tipdir(cl_inv) + 180) % 360 - 180
        chord = cl_inv[-1] - cl_inv[0]
        rw_a = float(np.median(wa[(np.linspace(0, 1, 41) >= 0.1) & (np.linspace(0, 1, 41) <= 0.3)]))
        tw_a = float(np.median(wa[(np.linspace(0, 1, 41) >= 0.7) & (np.linspace(0, 1, 41) <= 0.9)]))
        out[cid] = dict(row=c["row"], root_px=round(e_root, 3), tip_px=round(e_tip, 3), len_px=round(L3, 2), len_inv_px=round(Li, 2),
                        outline_left_px=None if not hd else (round(hd["left"], 2) if hd["left"] is not None else None),
                        outline_right_px=None if not hd else (round(hd["right"], 2) if hd["right"] is not None else None),
                        width_ratio=round(wr, 3), root_width_px=round(rw_a, 2), tip_width_px=round(tw_a, 2),
                        tip_dir_deg=round(tipdir(sk2), 1), tip_dir_inv_deg=round(tipdir(cl_inv), 1), tip_dir_diff_deg=round(float(da), 1),
                        chord_dir_deg=round(math.degrees(math.atan2(chord[1], chord[0])), 1))
    return out


def summarize(m):
    rows = {}
    for r_ in sorted(set(v["row"] for v in m.values())):
        vs = [v for v in m.values() if v["row"] == r_]
        rp = np.array([v["root_px"] for v in vs]); tp = np.array([v["tip_px"] for v in vs])
        ol = np.array([max(v["outline_left_px"] or 0, v["outline_right_px"] or 0) for v in vs])
        wr = np.array([v["width_ratio"] for v in vs])
        rows[r_] = dict(claws=len(vs), root_le4=int((rp <= 4).sum()), tip_le4=int((tp <= 4).sum()), root_max=round(float(rp.max()), 2),
                        tip_max=round(float(tp.max()), 2), outline_le4=int((ol <= 4).sum()), outline_p50=round(float(np.median(ol)), 2),
                        outline_p90=round(float(np.percentile(ol, 90)), 2), width_ratio_p50=round(float(np.median(wr)), 3))
    reps = {k: m[k] for k in REPS if k in m}
    li = [reps[k]["len_inv_px"] for k in REPS if k in reps]; la = [reps[k]["len_px"] for k in REPS if k in reps]
    sp = float(np.corrcoef(np.argsort(np.argsort(li)), np.argsort(np.argsort(la)))[0, 1]) if len(li) > 2 else None
    c = m.get(CENTRE)
    centre = None
    if c:
        centre = dict(id=CENTRE, b95_root_wider_than_tip=bool(c["root_width_px"] > c["tip_width_px"]),
                      b97_tip_downward=bool(30 <= c["tip_dir_deg"] <= 150), b98_chord_downward=bool(30 <= c["chord_dir_deg"] <= 150),
                      root_width_px=c["root_width_px"], tip_width_px=c["tip_width_px"], tip_dir_deg=c["tip_dir_deg"], chord_dir_deg=c["chord_dir_deg"],
                      outline_left_px=c["outline_left_px"], outline_right_px=c["outline_right_px"], root_px=c["root_px"], tip_px=c["tip_px"])
    allo = np.array([max(v["outline_left_px"] or 0, v["outline_right_px"] or 0) for v in m.values()])
    return dict(rows=rows, reps=dict(ids=REPS, per_claw=reps, length_order_spearman=None if sp is None else round(sp, 3),
                                     outline_le4=int(sum(1 for v in reps.values() if max(v["outline_left_px"] or 0, v["outline_right_px"] or 0) <= 4)),
                                     tip_dir_diff_abs_max=round(float(max(abs(v["tip_dir_diff_deg"]) for v in reps.values())), 1),
                                     width_ratio=[reps[k]["width_ratio"] for k in REPS if k in reps]),
                centre=centre, all_outline=dict(claws=len(allo), le4=int((allo <= 4).sum()), p50=round(float(np.median(allo)), 2), p90=round(float(np.percentile(allo, 90)), 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-claws", default=REPO + "/Unity/Build/Design/33/claws")
    ap.add_argument("--before-inv", default=REPO + "/Unity/Build/Design/32/list+ids/ds32_claw_inventory.json")
    ap.add_argument("--after-claws", default=REPO + "/Unity/Build/Polish/32/claws")
    ap.add_argument("--after-inv", default=REPO + "/Unity/Build/Polish/32/list/ds32_claw_inventory.json")
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/32/measure/pl32_measure_claws.json")
    a = ap.parse_args()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    res = {}
    for tag, cd, iv in (("before", a.before_claws, a.before_inv), ("after", a.after_claws, a.after_inv)):
        m = measure(cd, iv)
        res[tag] = dict(summary=summarize(m), per_claw=m, claws_dir=cd.replace(REPO + "/", ""), inventory=iv.replace(REPO + "/", ""))
        print(tag, json.dumps(res[tag]["summary"]["rows"], ensure_ascii=False))
        print(tag, "reps", res[tag]["summary"]["reps"]["length_order_spearman"], res[tag]["summary"]["reps"]["outline_le4"],
              res[tag]["summary"]["reps"]["tip_dir_diff_abs_max"], "centre", res[tag]["summary"]["centre"], "all", res[tag]["summary"]["all_outline"])
    res["note_ja"] = __doc__
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
