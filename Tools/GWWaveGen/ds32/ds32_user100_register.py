# -*- coding: utf-8 -*-
"""設計32（爪の一覧の修正、計画 第6節の3）：利用者の爪100本（G:/research/爪形分析、読み取りのみ）を
高解像度原画 DP130155（Docs/References/Met_JP1847_DP130155.jpg、3859×2594）へテンプレート照合で位置合わせする。

利用者の切り抜きは別のデジタル画像（README の記録では Tsunami_by_hokusai_19th_century.jpg）から、爪ごとに違う倍率で
切り出されている（倍率の揃いは README でも未確認）。そこで切り抜きごとに倍率を探す：
  1. 粗：原画を 0.5 倍にした灰色画像で、倍率 s（0.08〜0.70、等比 40 段）ごとに正規化相互相関（TM_CCOEFF_NORMED）の最大を取る。
  2. 細：原画の等倍で、粗の位置の ±24 px、倍率 s×(0.90〜1.10、21 段) の最大。
  3. ECC（cv2.findTransformECC、アフィン、σ 1 px の平滑）で細の相似変換から詰める。
残差（合わせの残差）として、照合の NCC、ECC の後の NCC、ECC のアフィンと細の相似変換の差（切り抜きの四隅での px）、
2 番目の峰（最良の位置から 30 px 以上離れた最大）との差を記録する。

出力（Git 対象外、Unity/Build/Design/32/list+ids/）：ds32_user100_registration.json
  利用者の爪ごと：切り抜き→原画の 2×3 変換、倍率、残差、利用者の構造点（S〜T、弧長の順）を原画の px へ写した点。
  画像・マスクは書き出さない（D14/D23：派生した数値と出典のパス・SHA-256 だけ）。マスクはメモリの中で重なりの計算に使うだけ。
"""
import csv
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
USER = "G:/research/爪形分析"
CROPS = USER + "/final_100_claws_centerlines_from_fill_masks_v3"
POINTS = USER + "/final_100_claw_structural_points_v2/final_points_long.csv"
OUT = REPO + "/Unity/Build/Design/32/list+ids"
SEARCH = (600, 0, 3859, 2250)  # x0, y0, x1, y1（原画 px）。主浪と右側の波を含む


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def imread_u(p, flag):
    return cv2.imdecode(np.fromfile(p, np.uint8), flag)


def match(img, tpl):
    r = cv2.matchTemplate(img, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, ml = cv2.minMaxLoc(r)
    return float(mx), ml, r


def ncc(a, b, m=None):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    if m is not None:
        a, b = a[m], b[m]
    a = a - a.mean()
    b = b - b.mean()
    d = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def register_one(G, G2, tpl):
    x0, y0, x1, y1 = SEARCH
    sub2 = G2[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
    best = (-2, None, None)
    for s in np.geomspace(0.08, 0.70, 40):
        ts = cv2.resize(tpl, None, fx=s * 0.5, fy=s * 0.5, interpolation=cv2.INTER_AREA)
        if min(ts.shape) < 10:
            continue
        mx, ml, _ = match(sub2, ts)
        if mx > best[0]:
            best = (mx, s, ml)
    _, s0, ml = best
    cx, cy = x0 + ml[0] * 2, y0 + ml[1] * 2
    fine = (-2, None, None, None)
    for f in np.linspace(0.90, 1.10, 21):
        s = s0 * f
        ts = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        h, w = ts.shape
        X0, Y0 = max(0, cx - 24), max(0, cy - 24)
        win = G[Y0:min(G.shape[0], cy + 24 + h), X0:min(G.shape[1], cx + 24 + w)]
        if win.shape[0] < h or win.shape[1] < w:
            continue
        mx, l, r = match(win, ts)
        if mx > fine[0]:
            fine = (mx, s, (X0 + l[0], Y0 + l[1]), (ts.shape, r, X0, Y0))
    mx_f, s_f, (tx, ty), (tshape, _, _, _) = fine
    # 2 番目の峰：粗の画像で、同じ倍率の相関から最良の位置の周り 30 px（原画）を除いた最大
    ts2 = cv2.resize(tpl, None, fx=s_f * 0.5, fy=s_f * 0.5, interpolation=cv2.INTER_AREA)
    _, _, r2 = match(sub2, ts2)
    bx, by = (tx - x0) / 2.0, (ty - y0) / 2.0
    yy, xx = np.mgrid[0:r2.shape[0], 0:r2.shape[1]]
    r2m = np.where(np.hypot(xx - bx, yy - by) > 15, r2, -2)
    second = float(r2m.max())
    # 相似変換（回転なし）：原画 = s·切り抜き + t（画素中心：切り抜きの (u+0.5)·s − 0.5 + t）
    A0 = np.array([[s_f, 0, tx + 0.5 * s_f - 0.5], [0, s_f, ty + 0.5 * s_f - 0.5]], np.float64)
    # ECC：切り抜きの座標で原画を引く（原画→切り抜きへの逆写像を詰める）
    Ainv0 = cv2.invertAffineTransform(A0).astype(np.float32)
    tplf = cv2.GaussianBlur(tpl.astype(np.float32), (0, 0), 1.0)
    Gf = cv2.GaussianBlur(G.astype(np.float32), (0, 0), max(1.0, s_f))
    # ECC は「テンプレート＝切り抜き、入力＝原画」で、warp は切り抜き→原画（WARP_INVERSE_MAP で原画を切り抜きへ引く）
    warp = A0.astype(np.float32).copy()
    ecc_ok = True
    try:
        cc, warp = cv2.findTransformECC(tplf, Gf, warp, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
    except cv2.error:
        ecc_ok = False
        cc = float("nan")
    A1 = warp.astype(np.float64) if ecc_ok else A0
    h, w = tpl.shape
    corners = np.array([[0, 0, 1], [w - 1, 0, 1], [0, h - 1, 1], [w - 1, h - 1, 1]], np.float64)
    dev = np.hypot(*((corners @ A1.T) - (corners @ A0.T)).T)
    back = cv2.warpAffine(G, A1, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    ncc_after = ncc(back, tpl)
    back0 = cv2.warpAffine(G, A0, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
    ncc_before = ncc(back0, tpl)
    # ECC が似た変換から大きく外れたら（四隅で 0.25·切り抜きの原画での大きさ超）相似変換を採る
    size_dp = s_f * max(h, w)
    use_ecc = ecc_ok and float(dev.max()) <= 0.25 * size_dp and ncc_after >= ncc_before
    return {
        "coarse_ncc": round(float(best[0]), 4), "coarse_scale": round(float(s0), 5),
        "ncc_template": round(mx_f, 4), "scale": round(float(s_f), 5),
        "second_peak_ncc": round(second, 4), "peak_margin": round(mx_f - second, 4),
        "ecc_cc": None if not ecc_ok else round(float(cc), 4),
        "ncc_similarity": round(ncc_before, 4), "ncc_after_ecc": round(ncc_after, 4),
        "ecc_vs_similarity_corner_px": [round(float(v), 2) for v in dev],
        "ecc_used": bool(use_ecc),
        "A_crop_to_ref": [[round(float(v), 6) for v in row] for row in (A1 if use_ecc else A0)],
        "A_similarity": [[round(float(v), 6) for v in row] for row in A0],
        "crop_size_px": [int(w), int(h)],
        "size_in_ref_px": round(size_dp, 1),
    }


def main():
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    G = cv2.cvtColor(imread_u(PAINT, cv2.IMREAD_COLOR), cv2.COLOR_BGR2GRAY)
    G2 = cv2.resize(G, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    pts = {}
    with open(POINTS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pts.setdefault(r["claw_id"], []).append(r)
    ids = sorted(d for d in os.listdir(CROPS) if d.startswith("claw") and os.path.isdir(os.path.join(CROPS, d)))
    rec, srcs = [], {"painting": {"path": PAINT, "sha256": sha(PAINT)}, "points_csv": {"path": POINTS, "sha256": sha(POINTS)},
                     "index_csv": {"path": CROPS + "/index.csv", "sha256": sha(CROPS + "/index.csv")}}
    files = {}
    for cid in ids:
        po = CROPS + "/" + cid + "/original.png"
        pm = CROPS + "/" + cid + "/fill_mask.png"
        files[cid] = {"original_png_sha256": sha(po), "fill_mask_png_sha256": sha(pm)}
        tpl = imread_u(po, cv2.IMREAD_GRAYSCALE)
        r = register_one(G, G2, tpl)
        A = np.array(r["A_crop_to_ref"], np.float64)
        P = sorted(pts.get(cid, []), key=lambda q: int(q["point_order"]))
        lab = [q["label"] for q in P]
        xy = np.array([[float(q["x"]), float(q["y"])] for q in P], np.float64) if P else np.zeros((0, 2))
        xy_ref = (np.c_[xy, np.ones(len(xy))] @ A.T) if len(xy) else xy
        # 利用者のマスク（メモリの中だけ）の原画での重心と面積
        m = imread_u(pm, cv2.IMREAD_GRAYSCALE) > 127
        ys, xs = np.nonzero(m)
        cen = (np.array([[xs.mean(), ys.mean(), 1.0]]) @ A.T)[0] if len(xs) else np.array([np.nan, np.nan])
        r.update({
            "user_id": cid,
            "labels": lab,
            "points_ref": [[round(float(a), 2), round(float(b), 2)] for a, b in xy_ref],
            "root_ref": [round(float(v), 2) for v in xy_ref[0]] if len(xy_ref) else None,
            "tip_ref": [round(float(v), 2) for v in xy_ref[-1]] if len(xy_ref) else None,
            "mask_centroid_ref": [round(float(v), 2) for v in cen],
            "mask_area_ref_px": round(float(m.sum()) * abs(np.linalg.det(A[:, :2])), 1),
        })
        rec.append(r)
        print(cid, r["scale"], r["ncc_template"], r["ncc_after_ecc"], r["peak_margin"], r["ecc_used"], r["root_ref"], r["tip_ref"], flush=True)
    out = {
        "schema": "GreatWave.DS32.user100_registration/1",
        "number": "設計32",
        "note_ja": "利用者の爪100本（G:/research/爪形分析 の final_100_claws_centerlines_from_fill_masks_v3 と final_100_claw_structural_points_v2）を"
                   "高解像度原画 DP130155 へテンプレート照合で合わせた派生の数値。画像とマスクは複製していない（読み取りのみ、D14/D23）。"
                   "points_ref は利用者の構造点（弧長の順、最初＝S 根元、最後＝先端の側）を A_crop_to_ref で原画の px（画素中心の整数系）へ写したもの。"
                   "照合の相手は別のデジタル画像（別の摺り・別の撮影の可能性がある）なので、NCC は 1 に届かない。",
        "method_ja": __doc__,
        "search_ref": SEARCH,
        "sources": srcs,
        "user_files_sha256": files,
        "claws": rec,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT + "/ds32_user100_registration.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("done", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
