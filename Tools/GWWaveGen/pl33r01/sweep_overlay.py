# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：原画視点 t* の爪の輪郭を、爪の一覧（仕上げ32）と原画に重ねる図と数（numpy・OpenCV。記録のみ）。

爪の輪郭＝作品のまま（painting_t120_asis）と爪なし（painting_t120_clawfree）の差（最大のチャンネル > 12）を 3×3 で閉じたもの（Unity の PC 描画）。
一覧の爪の領域＝仕上げ32 の ds32_claw_inventory.json の region_polygon_ref（原画 DP130155 の画素）を表示の画素へ写したもの。
数（前＝仕上げ33 修正の回 2 と後＝SWEEP を同じ式で）：
  - 一覧の領域の再現：帯・指のある 184 本の領域の画素のうち、爪の輪郭に入る割合（全体と爪ごとの中央値）
  - 爪の輪郭の精度：爪の輪郭の画素のうち、一覧の全部の爪の領域（249 本）を 4 px／12 px 広げた所に入る割合
  - 中心線：一覧の中心線の点から、爪の層の t* の中心線（輪の中心と先、原画のカメラへ投影）までの距離（爪ごとの平均の中央値・p90）と、
    中心線の先が一覧の先より伸びた長さ（表示の px の中央値）
図：fig_pl33r01s_overlay_list.png（左：原画視点の後の描画に一覧の領域（緑の線）と後の中心線（赤）、右：原画の同じ所に後の爪の輪郭（赤の線））、
    fig_pl33r01s_overlay_ba.png（前｜後 の爪の輪郭と一覧の領域）
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_overlay.py --after-run … --after-claws … --out …
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
import ds33_common as U  # noqa: E402

B = REPO + "/Unity/Build/Polish"
INV = B + "/32/fix01/list/ds32_claw_inventory.json"
CROP = (380, 60, 1180, 620)


def claw_mask(run):
    a = cv2.imread(os.path.join(run, "views", "painting_t120_asis.png")).astype(np.int16)
    b = cv2.imread(os.path.join(run, "views", "painting_t120_clawfree.png")).astype(np.int16)
    m = (np.abs(a - b).max(2) > 12).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    return m.astype(bool), a.astype(np.uint8)


def centerlines(claws_dir, cam):
    lay = json.load(open(os.path.join(claws_dir, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    Y = np.memmap(os.path.join(claws_dir, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))[360]
    out = {}
    for c in lay["claws"]:
        if not c["id"].startswith("C"):
            continue
        o, n = c["vert_offset"], c["stations"]
        rg = np.asarray(Y[o + 1:o + 1 + n * 8], np.float64).reshape(n, 8, 3)
        cen = 0.5 * (rg[:, 2] + rg[:, 6])   # 輪の中心＝頂点 2 と 6 の中点（SWEEP の輪の角度は不揃い。仕上げ33 の帯は 8 頂点の平均と同じ）
        cen = np.vstack([cen, np.asarray(Y[o + 1 + n * 8], np.float64)[None]])
        xy, _ = cam.project(cen)
        out[c["id"]] = xy
    return out


def measure(run, claws_dir, inv, cam):
    m, img = claw_mask(run)
    H, W = m.shape
    regions = {}
    allreg = np.zeros((H, W), np.uint8)
    for c in inv["claws"]:
        poly = c.get("region_polygon_ref") or c.get("polygon_ref_af29")
        if not poly:
            continue
        q = np.round(U.to_disp(np.array(poly))).astype(np.int32)
        r = np.zeros((H, W), np.uint8)
        cv2.fillPoly(r, [q], 1)
        regions[c["id"]] = r.astype(bool)
        allreg |= r
    cl = centerlines(claws_dir, cam)
    ids = [i for i in cl if i in regions]
    cov = [float(m[regions[i]].mean()) for i in ids if regions[i].any()]
    tot = np.zeros((H, W), bool)
    for i in ids:
        tot |= regions[i]
    d4 = cv2.dilate(allreg, np.ones((9, 9), np.uint8)).astype(bool)
    d12 = cv2.dilate(allreg, np.ones((25, 25), np.uint8)).astype(bool)
    dists, over = [], []
    byid = {c["id"]: c for c in inv["claws"]}
    for i in ids:
        lc = U.to_disp(np.array(byid[i]["centerline_ref"], np.float64))
        sp = cl[i]
        # 中心線を細かく取り直す
        seg = np.linspace(0, 1, 8)[None, :, None]
        dense = (sp[:-1, None, :] * (1 - seg) + sp[1:, None, :] * seg).reshape(-1, 2)
        dd, _ = cKDTree(dense).query(lc)
        dists.append(float(dd.mean()))
        lt = np.linalg.norm(np.diff(lc, axis=0), axis=1).sum()
        ls = np.linalg.norm(np.diff(sp, axis=0), axis=1).sum()
        over.append(float(ls - lt))
    res = dict(claw_pixels=int(m.sum()), list_region_pixels=int(tot.sum()),
               list_recall=float(m[tot].mean()) if tot.any() else None,
               list_recall_per_claw_median=float(np.median(cov)) if cov else None,
               precision_4px=float(d4[m].mean()) if m.any() else None, precision_12px=float(d12[m].mean()) if m.any() else None,
               centerline_dist_px_median=float(np.median(dists)), centerline_dist_px_p90=float(np.percentile(dists, 90)),
               centerline_over_px_median=float(np.median(over)), centerline_over_px_p90=float(np.percentile(over, 90)), claws=len(ids))
    return res, m, img, regions, cl, allreg


def painting_disp():
    ref = cv2.imread(U.PAINT)
    A = U.A_DISP
    M = np.array([[A, 0, 0.5 * A - 0.5 + 156.66153], [0, A, 0.5 * A - 0.5]], np.float64)
    return cv2.warpAffine(ref, M, (1920, 1080), flags=cv2.INTER_AREA, borderValue=(230, 230, 230))


def draw_regions(im, regions, col):
    for r in regions.values():
        cs, _ = cv2.findContours(r.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(im, cs, -1, col, 1)


def put(im, txt, y=26):
    from PIL import Image, ImageDraw, ImageFont
    p = Image.fromarray(cv2.cvtColor(im, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(p)
    f = ImageFont.truetype("C:/Windows/Fonts/NotoSansJP-Bold.ttf", 20) if os.path.exists("C:/Windows/Fonts/NotoSansJP-Bold.ttf") else ImageFont.load_default()
    d.rectangle([0, y - 24, d.textlength(txt, font=f) + 16, y + 4], fill=(0, 0, 0))
    d.text((8, y - 24), txt, fill=(255, 255, 255), font=f)
    return cv2.cvtColor(np.asarray(p), cv2.COLOR_RGB2BGR)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-run", default=B + "/33/fix02/r_fix02")
    ap.add_argument("--before-claws", default=B + "/33/fix02/claws")
    ap.add_argument("--after-run", required=True)
    ap.add_argument("--after-claws", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    inv = json.load(open(INV, encoding="utf-8"))
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    cam = U.CamWH(spec, 1920, 1080)
    rb, mb, ib, regions, clb, allreg = measure(a.before_run, a.before_claws, inv, cam)
    ra, ma, ia, _, cla, _ = measure(a.after_run, a.after_claws, inv, cam)
    pdisp = painting_disp()
    x0, y0, x1, y1 = CROP
    # 図 1：後の描画に一覧の領域と後の中心線｜原画に後の爪の輪郭
    L = ia.copy()
    draw_regions(L, {k: v for k, v in regions.items()}, (40, 200, 40))
    for i, xy in cla.items():
        cv2.polylines(L, [np.round(xy).astype(np.int32)], False, (0, 0, 255), 1)
    R = pdisp.copy()
    cs, _ = cv2.findContours(ma.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    cv2.drawContours(R, cs, -1, (0, 0, 255), 1)
    Lc = cv2.resize(L[y0:y1, x0:x1], (956, 669), interpolation=cv2.INTER_CUBIC)
    Rc = cv2.resize(R[y0:y1, x0:x1], (956, 669), interpolation=cv2.INTER_CUBIC)
    Lc = put(Lc, "後（SWEEP）の原画視点 t*：緑＝一覧の爪の領域、赤＝指の中心線（t* の投影）")
    Rc = put(Rc, "原画 DP130155（表示の画素へ写した）：赤＝後の爪の輪郭（作品のまま − 爪なし）")
    top = np.hstack([Lc, np.full((669, 8, 3), 238, np.uint8), Rc])
    canvas = np.full((1080, 1920, 3), 238, np.uint8)
    canvas[0:669, 0:1920] = top[:, :1920]
    # 下の段：前と後の爪の輪郭の色分け（前だけ 青、後だけ 赤、両方 紫）を原画の上に
    ov = pdisp.copy()
    both = ma & mb
    ov[mb & ~ma] = (0.5 * ov[mb & ~ma] + 0.5 * np.array([255, 120, 0])).astype(np.uint8)
    ov[ma & ~mb] = (0.5 * ov[ma & ~mb] + 0.5 * np.array([0, 0, 255])).astype(np.uint8)
    ov[both] = (0.5 * ov[both] + 0.5 * np.array([200, 0, 200])).astype(np.uint8)
    draw_regions(ov, regions, (40, 160, 40))
    oc = cv2.resize(ov[y0:y1, x0:x1], (588, 411), interpolation=cv2.INTER_AREA)
    oc = put(oc, "原画に 前だけ 青・後だけ 赤・両方 紫、緑＝一覧", 26)
    bc = cv2.resize(ib[y0:y1, x0:x1], (588, 411), interpolation=cv2.INTER_AREA)
    bc = put(bc, "前（仕上げ33 修正の回 2）", 26)
    acr = cv2.resize(ia[y0:y1, x0:x1], (588, 411), interpolation=cv2.INTER_AREA)
    acr = put(acr, "後（SWEEP）", 26)
    row = np.hstack([bc, np.full((411, 8, 3), 238, np.uint8), acr, np.full((411, 8, 3), 238, np.uint8), oc])
    canvas[669:1080, 0:row.shape[1]] = row
    p1 = os.path.join(a.out, "fig_pl33r01s_overlay_list.png")
    cv2.imwrite(p1, canvas)
    res = dict(before=rb, after=ra, crop=CROP, inventory=os.path.relpath(INV, REPO).replace("\\", "/"), inventory_sha256=U.sha(INV),
               rule_ja=__doc__.strip().split("\n\n")[1])
    json.dump(res, open(os.path.join(a.out, "sweep_overlay.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SWEEP_OVERLAY", json.dumps(dict(before=rb, after=ra), ensure_ascii=False))


if __name__ == "__main__":
    main()
