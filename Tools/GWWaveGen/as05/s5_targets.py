# -*- coding: utf-8 -*-
"""美術の見本05 の調べ（Q33）：三つの層 ①②③ を形で分けるための「測れる目標」と、候補を測る道具。

  py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py baseline
      見本04（主役波 AS04F ＋ wave4 fix1、層の印は既定の c の帯）を測り、Unity/Build/Polish/sample05/study/baseline_sample04.json を書く。
  py -3.10 -B Tools/GWWaveGen/as05/s5_targets.py measure <cand.json> <out.json>
      候補を測る。cand.json の形：
        {"name": "AS05A",
         "rows": "<主役波の行の npz（c・A・Y、240×400）>",
         "row_labels": "<任意：行の格子と同じ形の int の npy（0 なし・1 ①・2 ②・3 ③）。無ければ既定の c の帯>",
         "meshes": [{"path": "<静止のメッシュの json（w4_common.read_static の形）>", "role": "wave4 | layer3 | ...",
                     "layer": 0〜3（そのメッシュの全部の頂点の層。0 は層でない）, "vertex_labels": "<任意：頂点ごとの int の npy>"}],
         "render_dir": "<任意：Unity の原画視点の描画のフォルダー（views/painting_t120_claws.png・painting_t120_clawfree.png）>"}
測る物（targets.json の L・P・K の番号と同じ）：
  L1 峰と突出：上から見た高さの場 h(a, c)（主役波の行＋メッシュの点、0.25 m の格子）の峰のうち、原画のカメラで区域 ②・③ の多角形（±40 原画画素）に
     入る峰の最大の突出（自分より高い所へ行く道の最も高い鞍まで、m）。① は全体の最大。
  L2 鞍より前：その峰の a − 鞍の a（m）。鞍が峰の後ろ（主の体の側）にあり、峰が前へ出ているか。
  L3 高さ：峰の高さ（H0 = 20.75 m）と、層の間の差。
  L4 原画のカメラからの奥行き：峰の点の距離。③ が ② より、② が ① より手前。
  L5 前の縁の下の引っ込み：峰の c ± 0.5 m の点で、峰の近くの前の縁から 0.08〜0.25 H0 下の面の前の端が、前の縁よりどれだけ後ろか（m）。唇の長さ（前の縁 − 峰の a）も記録。
  L6 15 視点の分かれ（見本04 の S11 と同じ決めごと）と、原画視点の印の整合（区域 k の中の主役波・メッシュの画素のうち層 k の印の割合）。
  P1・P2 原画視点の見え方（Unity の描画があれば）：③・② の帯ごとの藍・水色・白の割合と、8 画素の升の藍の割合の原画との差・相関。
  K-T5・K-T6 白い粒の数・内の縁の白（Unity の描画があれば）。
関門（G2）・S4・S8・S9・S10 は見本04 の道具（Tools/GWWaveGen/as04/asm4_rules.py の g2・s4・s8・s9・s10）で測る（ここでは測らない）。
原画の色は面へ写さない（Q28）。原画のカメラは測りにだけ使う。参照モデルの OBJ は読まない。
"""
import json
import os
import sys
import time

os.environ.setdefault("AS04_FIX", "fix1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_common as S  # noqa: E402
import asm4_common as A  # noqa: E402

VIEWS15 = ["side_left", "side_right", "top"] + ["tt%d" % a for a in range(0, 360, 30)]
LAYER_C = {1: (-2.0, 8.0), 2: (-15.5, -11.5), 3: (-23.0, -17.0)}     # 見本04 の既定の c の帯（shape_eval.LAYERS）
LAYER_YMIN = {1: 0.25, 2: 0.25, 3: 0.12}                             # 層の面の下の端（H0）。③ は低いので 0.12 H0（見本05 の決めごと）
T0 = time.time()


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


# ---------------------------------------------------------------- 候補の読み込み
def load_cand(cand):
    c, Ar, Yr = S.load_rows(cand["rows"])
    if cand.get("row_labels"):
        RL = np.load(cand["row_labels"]).astype(np.int16)
    else:
        RL = np.zeros(Ar.shape, np.int16)
        J = np.arange(Ar.shape[1])[None, :]
        for k, (c0, c1) in LAYER_C.items():
            m = (c[:, None] >= c0) & (c[:, None] <= c1) & (J >= S.J_TOP) & (J <= S.J_FACEBOT) & (Yr >= LAYER_YMIN[k] * S.H0)
            RL[m] = k
    meshes = []
    for m in cand.get("meshes", []):
        ch, tri, _ = S.W4.read_static(m["path"])
        P = ch["position"].astype(np.float64)
        if m.get("vertex_labels"):
            vl = np.load(m["vertex_labels"]).astype(np.int16)
        else:
            k = int(m.get("layer", 0))
            vl = np.zeros(len(P), np.int16)
            if k:
                vl[S.K.sec(P)[:, 1] >= LAYER_YMIN[k] * S.H0] = k
        meshes.append({"P": P, "tri": tri.astype(np.int64), "vl": vl, "role": m.get("role", "")})
    return c, Ar, Yr, RL, meshes


def scene(c, Ar, Yr, RL, meshes, with_sea=True):
    """(tris, lab)：lab = 1・2・3（層）、4 主役波のほかの前（列 ≥ 頂）、8 背、5 層でないメッシュ、6 近い海。"""
    X = S.K.world(c, Ar, Yr)
    R, C = X.shape[:2]
    r, k = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    keep = (k >= S.J_B) & (k < 394)
    r, k = r[keep], k[keep]
    a = r * C + k; b = (r + 1) * C + k; d = r * C + k + 1; e = (r + 1) * C + k + 1
    T = np.concatenate([np.stack([a, b, d], 1), np.stack([d, b, e], 1)])
    rr = np.concatenate([r, r]); kk = np.concatenate([k, k])
    lab = RL[rr, kk].copy()
    lab[(lab == 0) & (kk >= S.J_TOP)] = 4
    lab[lab == 0] = 8
    sea_mask = kk > S.J_FACEBOT
    lab[sea_mask & (lab >= 4)] = 6
    tris = [X.reshape(-1, 3)[T]]; labs = [lab]
    for m in meshes:
        tl = m["vl"][m["tri"]]
        l = np.where((tl == tl[:, :1]).all(1), tl[:, 0], 0).astype(np.int16)
        l[l == 0] = 5
        tris.append(m["P"][m["tri"]]); labs.append(l)
    if with_sea:
        st = A.sea_tris()
        tris.append(st); labs.append(np.full(len(st), 6, np.int16))
    return np.concatenate(tris), np.concatenate(labs)


# ---------------------------------------------------------------- L1〜L5
def geometry(c, Ar, Yr, meshes):
    Q = [S.rows_points(c, Ar, Yr, up=3)]
    for m in meshes:
        Q.append(S.mesh_points(m["P"], m["tri"], sub=2))
    Q = np.concatenate(Q)
    h, g = S.heightfield(Q)
    pk = S.crest_layers(h, g)
    out = {"all_peaks": pk}
    best = {}
    gm = [p for p in pk if p["prominence_m"] == "global_max"][0]
    best[1] = gm
    for k, r in ((2, "r2"), (3, "r3")):
        cand = [p for p in pk if r in p["regions"] and p["prominence_m"] != "global_max"]
        best[k] = max(cand, key=lambda p: p["prominence_m"]) if cand else None
    cam = S.CAM_SEC
    lay = {}
    for k, p in best.items():
        if p is None:
            lay[str(k)] = None
            continue
        P = np.array([p["a"], p["y"], p["c"]])
        dist = float(np.linalg.norm(S.K.world(np.array([P[2]]), np.array([[P[0]]]), np.array([[P[1]]])).reshape(3) - S.K.CAM_POS_U))
        rec = {"crest": {"a": p["a"], "y": p["y"], "y_over_H0": p["y_over_H0"], "c": p["c"]}, "prominence_m": p["prominence_m"],
               "crest_ahead_of_saddle_a_m": p.get("crest_ahead_of_saddle_a_m"), "saddle": p.get("saddle"), "dist_to_painting_cam_m": S.rnd(dist, 2)}
        # L5：峰の c ± 0.5 m の点で前の縁と、その下の面の前の端
        sl = Q[np.abs(Q[:, 2] - P[2]) < 0.5]
        near = sl[(sl[:, 1] >= P[1] - 0.2 * S.H0) & (sl[:, 1] <= P[1] + 0.05 * S.H0) & (sl[:, 0] >= P[0] - 2.0) & (sl[:, 0] <= P[0] + 14.0)]
        if len(near):
            F = near[np.argmax(near[:, 0])]
            lo = sl[(sl[:, 1] <= F[1] - 0.08 * S.H0) & (sl[:, 1] >= F[1] - 0.25 * S.H0) & (sl[:, 0] <= F[0] + 0.5) & (sl[:, 0] >= P[0] - 14.0)]
            if len(lo):
                yb = np.round(lo[:, 1] / 0.25)
                front = np.array([lo[yb == q, 0].max() for q in np.unique(yb)])
                rec["front_edge"] = {"a": S.rnd(F[0], 2), "y_over_H0": S.rnd(F[1] / S.H0)}
                rec["lip_ahead_of_crest_m"] = S.rnd(F[0] - P[0], 2)
                rec["undercut_m"] = S.rnd(F[0] - front.max(), 2)
        lay[str(k)] = rec
    steps = {}
    if lay.get("1") and lay.get("2"):
        steps["H1_minus_H2_over_H0"] = S.rnd(lay["1"]["crest"]["y_over_H0"] - lay["2"]["crest"]["y_over_H0"])
        steps["dist1_minus_dist2_m"] = S.rnd(lay["1"]["dist_to_painting_cam_m"] - lay["2"]["dist_to_painting_cam_m"], 2)
    if lay.get("2") and lay.get("3"):
        steps["H2_minus_H3_over_H0"] = S.rnd(lay["2"]["crest"]["y_over_H0"] - lay["3"]["crest"]["y_over_H0"])
        steps["dist2_minus_dist3_m"] = S.rnd(lay["2"]["dist_to_painting_cam_m"] - lay["3"]["dist_to_painting_cam_m"], 2)
    out["layers"] = lay
    out["steps"] = steps
    # 頂の高さ H(c)（S4 の目安。正式の S4 は asm4_rules.s4）：c 0.5 m の帯ごとの最大
    cb = np.arange(-40.0, 16.01, 0.5)
    k = np.clip(np.round((Q[:, 2] + 40.0) / 0.5).astype(int), 0, len(cb) - 1)
    Hc = np.full(len(cb), 0.0); np.maximum.at(Hc, k, Q[:, 1])
    im = int(np.argmax(Hc))
    left = Hc[:im + 1]; right = Hc[im:]
    dent = max(float((np.maximum.accumulate(left) - left).max()), float((np.maximum.accumulate(right[::-1]) - right[::-1]).max()))
    out["Hc_proxy_dent_m"] = S.rnd(dent, 3)
    return out


# ---------------------------------------------------------------- L6
def layer_view_metrics(L, D):
    H, W_ = L.shape
    vis = {k: int((L == k).sum()) for k in (1, 2, 3)}
    occ, cont = {}, {}
    for dy, dx in ((0, 1), (1, 0)):
        a, b = L[:H - dy, :W_ - dx], L[dy:, dx:]
        da, db = D[:H - dy, :W_ - dx], D[dy:, dx:]
        both = np.isfinite(da) & np.isfinite(db)
        near = np.minimum(np.where(both, da, 1e9), np.where(both, db, 1e9))
        jump = both & (np.abs(np.where(both, da - db, 0.0)) > np.maximum(0.5, 0.03 * near))
        for p, q in ((1, 2), (2, 3), (1, 3)):
            pair = ((a == p) & (b == q)) | ((a == q) & (b == p))
            occ[(p, q)] = occ.get((p, q), 0) + int((pair & jump).sum())
            cont[(p, q)] = cont.get((p, q), 0) + int((pair & ~jump).sum())
    front = np.isin(L, (1, 2, 3, 4))
    e = A.occl_edges(np.where(np.isfinite(D), D, np.inf))
    reg = (front & ~e).astype(np.uint8)
    n, comp = cv2.connectedComponents(reg, connectivity=4)
    conn = {}
    for p, q in ((1, 2), (2, 3), (1, 3)):
        cp = np.bincount(comp[(L == p) & (reg > 0)], minlength=n); cq = np.bincount(comp[(L == q) & (reg > 0)], minlength=n)
        cp[0] = 0; cq[0] = 0
        conn[(p, q)] = int(np.minimum(cp, cq)[(cp >= 50) & (cq >= 50)].sum())
    return vis, occ, cont, conn


def separation(tris, lab, save_dir=None):
    views = {}
    for vn in VIEWS15:
        cam = A.view_cam(vn)
        _, D, L = A.raster(cam, tris, lab)
        vis, occ, cont, conn = layer_view_metrics(L, D)
        pr = {}
        for (p, q) in ((1, 2), (2, 3), (1, 3)):
            both = vis[p] >= 200 and vis[q] >= 200
            sep = both and (occ[(p, q)] >= 20 or conn[(p, q)] == 0) and cont[(p, q)] == 0
            pr["%d-%d" % (p, q)] = {"occlusion_edge_px": occ[(p, q)], "continuous_contact_px": cont[(p, q)], "same_front_sheet_px": conn[(p, q)],
                                     "separated": bool(sep) if both else None}
        views[vn] = {"visible_px": {str(k): v for k, v in vis.items()}, "pairs": pr}
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            cv2.imwrite(save_dir + "/%s.png" % vn, A.tint(L, np.where(np.isfinite(D), D, np.inf))[..., ::-1])
        log("視点", vn, vis, {k: v["separated"] for k, v in pr.items()})
    summ = {}
    for pk in ("1-2", "2-3", "1-3"):
        arr = [v["pairs"][pk]["separated"] for v in views.values() if v["pairs"][pk]["separated"] is not None]
        summ[pk] = {"views_both_visible": len(arr), "separated_views": int(sum(arr)), "separated_share": S.rnd(sum(arr) / len(arr)) if arr else None}
    vis3 = [v["visible_px"]["3"] for v in views.values()]
    summ["layer3_views_with_2000px"] = int(sum(1 for x in vis3 if x >= 2000))
    return views, summ


def painting_consistency(tris, lab):
    cam = A.painting_cam(1)
    _, D, L = A.raster(cam, tris, lab)
    out = {}
    for k, r in ((1, "r1"), (2, "r2"), (3, "r3")):
        m = S.poly_mask(A.ref_to_px(S.REG[r]), cam.W, cam.H)
        surf = m & np.isin(L, (1, 2, 3, 4, 5, 8))
        out[r] = {"surface_px": int(surf.sum()), "share_label_k": S.rnd((L[surf] == k).mean()) if surf.any() else None,
                  "share_by_label": {str(q): S.rnd((L[surf] == q).mean()) for q in (1, 2, 3, 4, 5, 8)} if surf.any() else None}
    hero = np.isin(L, (1, 2, 3, 4, 8))
    return out, hero, L


# ---------------------------------------------------------------- P1・P2・T5・T6
R3_BANDS = {"top_1110_1300": (1110, 1300), "mid_1300_1560": (1300, 1560)}
R2_BANDS = {"top_880_1180": (880, 1180), "low_1180_1420": (1180, 1420)}


def painting_disp():
    P = np.array(Image.open(S.PAINT).convert("RGB"))
    Ps = cv2.resize(P, None, fx=S.S4.A_DISP, fy=S.S4.A_DISP, interpolation=cv2.INTER_AREA)
    M = np.array([[1.0, 0, S.S4.OFFX], [0, 1.0, 0]], np.float64)
    return cv2.warpAffine(Ps, M, (1920, 1080), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))


def band_mask(poly_ref, y0, y1):
    m = S.poly_mask(A.ref_to_px(poly_ref), 1920, 1080)
    yy = np.arange(1080)[:, None]
    ya, yb = A.ref_to_px([[0, y0], [0, y1]])[:, 1]
    return m & (yy >= ya) & (yy < yb)


def fracs(cls, m):
    n = max(int(m.sum()), 1)
    return {"indigo": S.rnd((cls[m] == 1).sum() / n), "mizuiro": S.rnd((cls[m] == 2).sum() / n), "white": S.rnd((cls[m] == 3).sum() / n),
            "boat": S.rnd((cls[m] == 4).sum() / n)}


def cell_agreement(cp, cr, m, cell=8):
    H, W = m.shape
    fp, fr = [], []
    for y in range(0, H, cell):
        for x in range(0, W, cell):
            mm = m[y:y + cell, x:x + cell]
            if mm.sum() < cell * cell * 0.6:
                continue
            p = cp[y:y + cell, x:x + cell][mm]; r = cr[y:y + cell, x:x + cell][mm]
            vp = np.isin(p, (1, 2, 3)); vr = np.isin(r, (1, 2, 3))
            if vp.sum() < 10 or vr.sum() < 10:
                continue
            fp.append((p[vp] == 1).mean()); fr.append((r[vr] == 1).mean())
    fp, fr = np.array(fp), np.array(fr)
    if len(fp) < 5:
        return None
    return {"cells": int(len(fp)), "indigo_share_mae": S.rnd(np.abs(fp - fr).mean()), "pearson_r": S.rnd(np.corrcoef(fp, fr)[0, 1])}


def appearance(render_dir, hero_mask):
    cp = S.color_classes(painting_disp())
    out = {}
    imgs = {}
    for tag in ("claws", "clawfree"):
        p = render_dir + "/views/painting_t120_%s.png" % tag
        if not os.path.isfile(p):
            continue
        R = np.array(Image.open(p).convert("RGB"))
        imgs[tag] = (R, S.color_classes(R))
    if "claws" not in imgs:
        return None
    cr = imgs["claws"][1]
    for k, bands in (("r3", R3_BANDS), ("r2", R2_BANDS)):
        d = {bn: {"painting": fracs(cp, band_mask(S.REG[k], *yy)), "candidate": fracs(cr, band_mask(S.REG[k], *yy))} for bn, yy in bands.items()}
        y0 = min(v[0] for v in bands.values()); y1 = max(v[1] for v in bands.values())
        d["cell_agreement_indigo"] = cell_agreement(cp, cr, band_mask(S.REG[k], y0, y1))
        out[k] = d
    # T5：原画視点の爪なしの描画で、主役波の藍の面に囲まれた白・水色の小さな塊（2〜400 画素）の数
    if "clawfree" in imgs:
        crf = imgs["clawfree"][1]
        pale = np.isin(crf, (2, 3)).astype(np.uint8)
        n, labm, st, _ = cv2.connectedComponentsWithStats(pale, connectivity=8)
        ind_d = cv2.dilate((crf == 1).astype(np.uint8), np.ones((5, 5), np.uint8))
        small = 0
        for i in range(1, n):
            a = st[i, cv2.CC_STAT_AREA]
            if 2 <= a <= 400:
                x, y, w, h = st[i, :4]
                blob = (labm[y:y + h, x:x + w] == i)
                ring = cv2.dilate(np.pad(blob, 1).astype(np.uint8), np.ones((3, 3), np.uint8))[1:-1, 1:-1].astype(bool) & ~blob
                if ring.any() and ind_d[y:y + h, x:x + w][ring].mean() > 0.9 and hero_mask[y + h // 2, x + w // 2]:
                    small += 1
        out["T5_small_white_blobs_on_hero_indigo"] = int(small)
    x0, y0, x1, y1 = S.T6_CROP_DISP
    sub = cr[y0:y1, x0:x1]; hero = hero_mask[y0:y1, x0:x1]
    band = np.zeros_like(sub, bool)
    for yy in range(sub.shape[0]):
        xs = np.nonzero(sub[yy] == 1)[0]
        if len(xs):
            band[yy, xs.max() + 1:min(xs.max() + 17, sub.shape[1])] = True
    sel = band & hero
    out["T6_inner_edge_band_pale_share"] = S.rnd(np.isin(sub[sel], (2, 3)).mean()) if sel.any() else 0.0
    out["T6_band_hero_px"] = int(sel.sum())
    return out


# ---------------------------------------------------------------- まとめ
def measure(cand, out_path, save_views=True):
    log("読み込み", cand.get("name"))
    c, Ar, Yr, RL, meshes = load_cand(cand)
    res = {"name": cand.get("name"), "candidate": cand, "inputs_sha256": {"rows": S.sha(cand["rows"])}}
    for m in cand.get("meshes", []):
        res["inputs_sha256"][m["path"]] = S.sha(m["path"])
    log("L1〜L5")
    res["geometry"] = geometry(c, Ar, Yr, meshes)
    tris, lab = scene(c, Ar, Yr, RL, meshes)
    log("原画視点の印")
    res["painting_label_consistency"], hero_mask, _ = painting_consistency(tris, lab)
    log("15 視点")
    vd = os.path.join(os.path.dirname(out_path), "views_" + (cand.get("name") or "cand")) if save_views else None
    res["separation_views"], res["separation_summary"] = separation(tris, lab, vd)
    if cand.get("render_dir"):
        log("原画視点の見え方")
        res["appearance"] = appearance(cand["render_dir"], hero_mask)
    res["seconds"] = round(time.time() - T0, 1)
    S.jdump(out_path, res)
    log("書いた", out_path)
    return res


def baseline():
    cand = {"name": "sample04_AS04F", "rows": S.ROWS04F, "row_labels": None,
            "meshes": [{"path": S.WAVE4_F1, "role": "wave4", "layer": 0}], "render_dir": S.RENDER_F1}
    return measure(cand, S.OUT + "/baseline_sample04.json")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if sys.argv[1] == "baseline":
        baseline()
    elif sys.argv[1] == "measure":
        measure(json.load(open(sys.argv[2], encoding="utf-8")), sys.argv[3])
