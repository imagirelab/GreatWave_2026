# -*- coding: utf-8 -*-
"""美術の見本05 の調べ（Q33）：見本04 の形で、三つの層 ①②③（とくに ③）が読めない理由を数で示し、診断の図を作る。

読むもの（どれも読み取りのみ。形・材質は変えない）：
  - 見本04 の最後の形：主役波 K*′ AS04F の行（fix1）、wave4（fix1）、近い海（Polish/30）。見本03 の形 AS02C（比べるため）。
  - 見本04 の Unity の描画（assemble/render/FX1）と、測る規則の結果（sample04/rules_check.json の S11）。
  - 原画 DP130155（色の区分を測るだけ。面へは写さない）。
  - 参照モデルの数（s5_obj.py の出力 s5_obj_numbers.json。数だけ）。
測るもの：
  1. 原画視点の区域（①②③）ごとに、見えている面の行・列・a・y・c・カメラからの距離（行の格子を numpy の z バッファで描く）。
  2. 上から見た高さの場の峰と突出・鞍（s5_common.crest_layers）。見本04・見本03 の形・参照の数。
  3. 断面（c ごと）：頂・唇の前の縁・その下の引っ込み、空の射線の禁止域と船・手前の海の射線の禁止域（仕上げ28 の格子）。
  4. 原画と見本04 の描画の色の区分（藍・水色・白・船）を、区域 ②③ の帯ごとに比べる。T5（白い粒）・T6（内の縁の白）の今の値。
  5. 15 視点の層の分かれ（見本04 の S11 の値）と、座席からの層の見え方。
出力：Unity/Build/Polish/sample05/study/diag.json と diag_1〜4 の図（Git 対象外）。
使い方：py -3.10 -B Tools/GWWaveGen/as05/s5_diag.py
"""
import json
import os
import sys
import time

os.environ.setdefault("AS04_FIX", "fix1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s5_common as S  # noqa: E402
import asm4_common as A  # noqa: E402

FONT = "C:/Windows/Fonts/meiryo.ttc"
OUT = S.OUT
T0 = time.time()


def font(n):
    return ImageFont.truetype(FONT, n)


def log(*a):
    print("[%5.1fs]" % (time.time() - T0), *a, flush=True)


# 進行役が目で読んだ層の頂（爪の群れの上の縁）の線。原画の画素。図に描くだけで、測りには使わない。
READ_CREST = {"r1": [(880, 640), (1000, 450), (1150, 320), (1400, 250), (1650, 260), (1900, 330), (2150, 520)],
              "r2": [(650, 1010), (780, 950), (930, 930), (1060, 935), (1180, 930), (1300, 960), (1400, 1010)],
              "r3": [(20, 1270), (100, 1120), (230, 1080), (380, 1090), (500, 1110), (600, 1150)]}
COL = {"r1": (214, 52, 40), "r2": (40, 150, 60), "r3": (20, 160, 200), "r4": (230, 180, 0)}
R3_BANDS = {"top_1110_1300": (1110, 1300), "mid_1300_1560": (1300, 1560), "low_1560_1849": (1560, 1849)}
R2_BANDS = {"top_900_1180": (880, 1180), "low_1180_1420": (1180, 1420)}


# ---------------------------------------------------------------- 1. 原画視点の区域 → 3D
def painting_scene(c, Arows, Yrows):
    X = S.K.world(c, Arows, Yrows)
    R, C = X.shape[:2]
    r, k = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    keep = (k >= S.J_B) & (k < 394)
    r, k = r[keep], k[keep]
    a = r * C + k; b = (r + 1) * C + k; d = r * C + k + 1; e = (r + 1) * C + k + 1
    T = np.concatenate([np.stack([a, b, d], 1), np.stack([d, b, e], 1)])
    rows = np.concatenate([r, r]); cols = np.concatenate([k, k])
    tris = [X.reshape(-1, 3)[T]]
    ch, tri, _ = S.W4.read_static(S.WAVE4_F1)
    tw = ch["position"].astype(np.float64)[tri.astype(np.int64)]
    st = A.sea_tris()
    tris = np.concatenate([tris[0], tw, st])
    kind = np.concatenate([np.ones(len(T), np.int16), np.full(len(tw), 5, np.int16), np.full(len(st), 6, np.int16)])
    return tris, kind, rows, cols


def region_map(c, Arows, Yrows, scale=1):
    cam = A.painting_cam(scale)
    tris, kind, rows, cols = painting_scene(c, Arows, Yrows)
    idb, zb = S.U.raster(cam, tris, np.arange(1, len(tris) + 1, dtype=np.int64))
    idb = idb.reshape(cam.H, cam.W); zb = zb.reshape(cam.H, cam.W)
    nh = len(rows)
    out, masks = {}, {}
    for k in ("r1", "r2", "r3"):
        poly = A.ref_to_px(S.REG[k], scale)
        m = S.poly_mask(poly, cam.W, cam.H)
        ids = idb[m]
        hero = (ids > 0) & (ids <= nh)
        n = int(m.sum())
        rec = {"pixels": n, "share_hero": S.rnd(hero.sum() / n), "share_wave4": S.rnd(((ids > nh) & (kind[np.maximum(ids - 1, 0)] == 5)).sum() / n),
               "share_sea": S.rnd(((ids > 0) & (kind[np.maximum(ids - 1, 0)] == 6)).sum() / n), "share_sky": S.rnd((ids == 0).sum() / n)}
        hi = ids[hero] - 1
        rr, cc = rows[hi], cols[hi]
        aa, yy = Arows[rr, cc], Yrows[rr, cc]
        cv = c[rr]
        dist = 1.0 / zb[m][hero]
        part = np.select([cc < S.J_TOP, cc <= S.J_TIP, cc <= S.J_CORNER], ["背", "頂〜唇の先の外", "唇の下・内の面"], "前の面")
        rec.update({"c_p10_p50_p90": S.rnd(np.percentile(cv, [10, 50, 90]), 2), "a_p10_p50_p90": S.rnd(np.percentile(aa, [10, 50, 90]), 2),
                    "y_over_H0_p10_p50_p90": S.rnd(np.percentile(yy, [10, 50, 90]) / S.H0), "depth_p10_p50_p90_m": S.rnd(np.percentile(dist, [10, 50, 90]), 2),
                    "part_share": {p: S.rnd((part == p).mean()) for p in ("背", "頂〜唇の先の外", "唇の下・内の面", "前の面")}})
        out[k] = rec
        mm = np.zeros(Arows.shape, bool); mm[rr, cc] = True
        masks[k] = mm
    return out, masks


# ---------------------------------------------------------------- 2. 色の区分の比べ
def painting_disp():
    """原画を原画視点の描画（1920×1080）の画素へ移した画（ref_to_disp の相似：縮めて x を OFFX ずらす）。"""
    P = np.array(Image.open(S.PAINT).convert("RGB"))
    Ps = cv2.resize(P, None, fx=S4A, fy=S4A, interpolation=cv2.INTER_AREA)
    M = np.array([[1.0, 0, S4O], [0, 1.0, 0]], np.float64)
    return cv2.warpAffine(Ps, M, (1920, 1080), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0))


S4A, S4O = S.S4.A_DISP, S.S4.OFFX


def band_mask(poly_ref, y0, y1):
    m = S.poly_mask(A.ref_to_px(poly_ref), 1920, 1080)
    yy = np.arange(1080)[:, None]
    ya, yb = A.ref_to_px([[0, y0], [0, y1]])[:, 1]
    return m & (yy >= ya) & (yy < yb)


def class_fracs(cls, m):
    n = max(int(m.sum()), 1)
    return {S.CLS_JA[k]: S.rnd((cls[m] == k).sum() / n) for k in (1, 2, 3, 4, 0)}


def cell_agreement(cp, cr, m, cell=8):
    """区域の中を cell 画素の升に分け、藍の割合（藍・水色・白の中で）を原画と描画で比べる。"""
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
    return {"cells": int(len(fp)), "indigo_share_mae": S.rnd(np.abs(fp - fr).mean()), "pearson_r": S.rnd(np.corrcoef(fp, fr)[0, 1]),
            "painting_indigo_mean": S.rnd(fp.mean()), "render_indigo_mean": S.rnd(fr.mean())}


def colour_compare():
    pd = painting_disp()
    cp = S.color_classes(pd)
    res = {}
    imgs = {}
    for tag, fn in (("claws", "painting_t120_claws.png"), ("clawfree", "painting_t120_clawfree.png")):
        R = np.array(Image.open(S.RENDER_F1 + "/views/" + fn).convert("RGB"))
        cr = S.color_classes(R)
        imgs[tag] = (R, cr)
        rr = {}
        for k, bands in (("r3", R3_BANDS), ("r2", R2_BANDS)):
            d = {}
            for bn, (y0, y1) in bands.items():
                m = band_mask(S.REG[k], y0, y1)
                d[bn] = {"painting": class_fracs(cp, m), "sample04": class_fracs(cr, m)}
            mall = S.poly_mask(A.ref_to_px(S.REG[k]), 1920, 1080)
            d["cell_agreement_indigo"] = cell_agreement(cp, cr, mall)
            rr[k] = d
        res[tag] = rr
    return res, pd, cp, imgs


def t5_t6(imgs, idmask_hero):
    """T5：主役波の面の上の白い小さな塊の数（爪なしの描画、原画視点）。T6：利用者の切り出しの内の縁の帯の白・水色の割合。"""
    R, cr = imgs["clawfree"]
    pale = np.isin(cr, (2, 3)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(pale, connectivity=8)
    ind = (cr == 1).astype(np.uint8)
    ind_d = cv2.dilate(ind, np.ones((5, 5), np.uint8))
    small = 0
    for i in range(1, n):
        a = st[i, cv2.CC_STAT_AREA]
        if 2 <= a <= 400:
            x, y, w, h = st[i, :4]
            ring = cv2.dilate((lab[y:y + h, x:x + w] == i).astype(np.uint8), np.ones((3, 3), np.uint8)) - (lab[y:y + h, x:x + w] == i)
            if ring.sum() and (ind_d[y:y + h, x:x + w][ring > 0].mean() > 0.9) and idmask_hero[y + h // 2, x + w // 2]:
                small += 1
    x0, y0, x1, y1 = S.T6_CROP_DISP
    Rc, cc = imgs["claws"]
    sub = cc[y0:y1, x0:x1]
    hero = idmask_hero[y0:y1, x0:x1]
    # 藍の面の右の縁（行ごとに、左から続く藍の最も右）から右へ 16 画素の帯の、主役波の画素のうち白・水色の割合
    band, n_b, n_pale = np.zeros_like(sub, bool), 0, 0
    for yy in range(sub.shape[0]):
        row = sub[yy] == 1
        if not row.any():
            continue
        xs = np.nonzero(row)[0]
        xe = xs.max()
        band[yy, xe + 1:min(xe + 17, sub.shape[1])] = True
    sel = band & hero
    t6 = S.rnd(np.isin(sub[sel], (2, 3)).mean()) if sel.any() else None
    return {"T5_small_white_blobs_on_indigo_painting_view_clawfree": int(small), "T6_inner_edge_band_pale_share_on_hero": t6,
            "T6_band_hero_pixels": int(sel.sum())}


# ---------------------------------------------------------------- 3. 断面
def sections(c, Arows, Yrows, masks):
    G = np.unpackbits(np.load(S.P + "/28/r2/cache/keepout_d3.npz")["G"], axis=-1)
    Gp = np.unpackbits(np.load(S.P + "/28/rec/cache/protect_grids.npz")["G"], axis=-1)
    sys.path.insert(0, S.REPO + "/Tools/GWWaveGen/kstar_p28")
    import r2_common as R2
    G = G[..., :R2.NA].astype(bool); Gp = Gp[..., :R2.NA].astype(bool)
    out = []
    for cc in (-23, -20, -17, -14, -11, -8, -5, -1):
        i = int(np.argmin(np.abs(c - cc)))
        a, y = Arows[i], Yrows[i]
        jt = S.J_B + int(np.argmax(y[S.J_B:S.J_TIP + 1]))
        m = (np.arange(400) >= 90) & (np.arange(400) <= 300) & (y >= 0.2 * S.H0)
        jf = int(np.argmax(np.where(m, a, -1e9)))
        # 前の縁の下 0.08〜0.25 H0 の外の面の前の端
        lo = (y <= y[jf] - 0.08 * S.H0) & (y >= y[jf] - 0.25 * S.H0) & (np.arange(400) > jf) & (np.arange(400) <= S.J_FACEBOT)
        rec_a = float(a[lo].max()) if lo.any() else None
        # 前の縁より前（a > a_jf）で、高さ 0.15〜0.45 H0 にある、禁止域でない升の割合（③ を前へ出す余地）
        ia0 = int(np.round((a[jf] - R2.GA0) / R2.GRES))
        iy0, iy1 = int(np.round((0.15 * S.H0 - R2.GY0) / R2.GRES)), int(np.round((0.45 * S.H0 - R2.GY0) / R2.GRES))
        fill = R2.section_fill(a, y)
        front = np.zeros_like(fill); front[iy0:iy1, ia0:] = True
        free = front & ~G[i] & ~Gp[i] & ~fill
        out.append({"c": S.rnd(c[i], 2), "row": i, "crest": {"a": S.rnd(a[jt], 2), "y_over_H0": S.rnd(y[jt] / S.H0)},
                    "front_edge": {"a": S.rnd(a[jf], 2), "y_over_H0": S.rnd(y[jf] / S.H0), "ahead_of_crest_m": S.rnd(a[jf] - a[jt], 2)},
                    "outer_face_front_0.08_0.25H0_below_edge_a": S.rnd(rec_a, 2), "undercut_m": S.rnd(a[jf] - rec_a, 2) if rec_a is not None else None,
                    "free_cells_ahead_0.15_0.45H0_share": S.rnd(free.sum() / max(front.sum(), 1)),
                    "visible_in_painting_regions_cols": {k: [int(x) for x in np.nonzero(masks[k][i])[0][[0, -1]]] if masks[k][i].any() else None for k in masks}})
    return out, G, Gp, R2


# ---------------------------------------------------------------- 4. 座席からの層の見え方
def seat_layers():
    tris, lab, _ = A.scene("S04", with_claws=False)
    res = {}
    for vn in ("seat", "seat_toward_wave", "side_left", "back65"):
        try:
            cam = A.view_cam(vn)
        except Exception:
            continue
        _, D, L = A.raster(cam, tris, lab)
        res[vn] = {"visible_px": {str(k): int((L == k).sum()) for k in (1, 2, 3, 5)}}
        cv2.imwrite(S.TMP + "/views_%s.png" % vn, A.tint(L, D)[..., ::-1])
    return res


# ---------------------------------------------------------------- 図
def sheet_painting(cmp, pd, cp, imgs):
    W, H = 1920, 1080
    C = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(C)
    d.text((20, 10), "調べ 1：原画の三つの層の読み（進行役の目の読み）と、見本04 の原画視点の同じ所", font=font(30), fill=(20, 20, 20))
    d.text((20, 52), "線：赤 ① 浪尖・緑 ② b区域・水色 ③ 最左側の小区域（利用者が確かめた多角形）・黄 ④。太い線 = 進行役が読んだ各層の頂（爪の群れの上の縁）。",
           font=font(18), fill=(60, 60, 60))
    P = Image.open(S.PAINT).convert("RGB")
    dp = ImageDraw.Draw(P)
    for k in ("r1", "r2", "r3", "r4"):
        pts = [tuple(p) for p in S.REG[k].tolist()]
        dp.line(pts + [pts[0]], fill=COL[k], width=8)
    for k, L in READ_CREST.items():
        dp.line(L, fill=COL[k], width=22)
    pc = P.crop((0, 200, 2400, 2000)); pc.thumbnail((930, 700))
    C.paste(pc, (20, 90))
    R = Image.fromarray(imgs["claws"][0])
    dr = ImageDraw.Draw(R)
    for k in ("r1", "r2", "r3", "r4"):
        pts = [tuple(p) for p in A.ref_to_px(S.REG[k]).tolist()]
        dr.line(pts + [pts[0]], fill=COL[k], width=3)
    x0, y0 = A.ref_to_px([[0, 200]])[0]; x1, y1 = A.ref_to_px([[2400, 2000]])[0]
    rc = R.crop((int(x0), int(y0), int(x1), int(min(y1, 1079)))); rc.thumbnail((930, 700))
    C.paste(rc, (970, 90))
    d.text((20, 795), "原画 DP130155", font=font(18), fill=(40, 40, 40)); d.text((970, 795), "見本04 の原画視点（Unity、爪あり）", font=font(18), fill=(40, 40, 40))
    # 区分の地図（③ の箱のまわり）
    pal = np.array([[150, 150, 150], [36, 60, 100], [150, 205, 200], [250, 246, 230], [225, 190, 140]], np.uint8)
    bx0, by0 = A.ref_to_px([[0, 1050]])[0]; bx1, by1 = A.ref_to_px([[1450, 1849]])[0]
    sl = (slice(int(by0), int(by1)), slice(int(bx0), int(bx1)))
    for j, (img, lab) in enumerate(((cp, "原画の色の区分"), (imgs["claws"][1], "見本04 の色の区分"))):
        im = Image.fromarray(pal[img[sl]]).resize((int((bx1 - bx0) * 0.6), int((by1 - by0) * 0.6)), Image.NEAREST)
        C.paste(im, (20 + j * 470, 826))
        d.text((20 + j * 470, 826 + im.size[1] + 2), lab + "（藍・水色・白・船）", font=font(14), fill=(40, 40, 40))
    t = cmp["claws"]["r3"]
    lines = ["③ の箱の帯ごとの割合（原画 → 見本04、爪あり）：藍 / 水色 / 白 / 船"]
    for bn in R3_BANDS:
        p, s = t[bn]["painting"], t[bn]["sample04"]
        lines.append("  %s：%.2f / %.2f / %.2f / %.2f → %.2f / %.2f / %.2f / %.2f" % (bn, p["藍（濃・中）"], p["水色"], p["白・紙"], p["船の生成り"],
                                                                         s["藍（濃・中）"], s["水色"], s["白・紙"], s["船の生成り"]))
    ca = t["cell_agreement_indigo"]
    if ca:
        lines.append("  8 画素の升ごとの藍の割合：原画と見本04 の差の平均 %.2f、相関 %.2f（升 %d）" % (ca["indigo_share_mae"], ca["pearson_r"], ca["cells"]))
    t2 = cmp["claws"]["r2"]
    for bn in R2_BANDS:
        p, s = t2[bn]["painting"], t2[bn]["sample04"]
        lines.append("② %s：藍 %.2f → %.2f、水色 %.2f → %.2f、白 %.2f → %.2f" % (bn, p["藍（濃・中）"], s["藍（濃・中）"], p["水色"], s["水色"], p["白・紙"], s["白・紙"]))
    for i, s in enumerate(lines):
        d.text((960, 840 + 26 * i), s, font=font(16), fill=(20, 20, 20))
    d.text((20, 1052), "原画の色は面へ写さない（Q28）。色の区分は測りだけ。見本04 は Unity 6000.4.3f1 の PC 描画（HMD ではない）。", font=font(14), fill=(90, 90, 90))
    C.save(OUT + "/diag_1_painting_reading.png")


def sheet_sections(c, Arows, Yrows, secs, G, Gp, R2, masks):
    W, H = 1920, 1080
    C = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(C)
    d.text((20, 10), "調べ 2：見本04（AS04F）の断面。①②③ は一つの頂の線（a ≈ 0）から出る長い唇で、層ごとの頂・面がない", font=font(28), fill=(20, 20, 20))
    d.text((20, 50), "赤 = 断面（緑・水色の太い所 = 原画視点で ②・③ の区域に見えている所）。灰 = 原画の空の射線の禁止域、橙 = 船・手前の海の射線の禁止域。"
           "矢印 = 原画のカメラの射線の向き。○ 頂、△ 唇の前の縁。数は m・H0", font=font(16), fill=(60, 60, 60))
    ch, tri, _ = S.W4.read_static(S.WAVE4_F1)
    Q4 = S.K.sec(ch["position"].astype(np.float64))
    pw, ph = 470, 480
    for n, s in enumerate(secs):
        i = s["row"]
        px0, py0 = 20 + (n % 4) * (pw + 4), 84 + (n // 4) * (ph + 6)
        img = np.full((ph, pw, 3), 255, np.uint8)
        sc = 13.0
        ox, oy = pw * 0.42, ph - 40

        def P(a, y):
            return int(ox + a * sc), int(oy - y * sc)
        aa = R2.GA0 + np.arange(R2.NA) * R2.GRES
        yy = R2.GY0 + np.arange(G.shape[1]) * R2.GRES
        for gy in range(0, G.shape[1], 2):
            for msk, colr in ((G[i], (215, 215, 215)), (Gp[i], (120, 190, 250))):
                xs = np.nonzero(msk[gy])[0]
                for x in xs[::2]:
                    p = P(aa[x], yy[gy])
                    if 0 <= p[0] < pw and 0 <= p[1] < ph:
                        img[p[1], p[0]] = colr
        for g in range(-30, 31, 5):
            cv2.line(img, P(g, -1), P(g, 0), (120, 120, 120), 1)
        cv2.line(img, P(-35, 0), P(35, 0), (170, 170, 170), 1)
        m4 = np.abs(Q4[:, 2] - c[i]) < 0.12
        for a_, y_ in Q4[m4][::3, :2]:
            cv2.circle(img, P(a_, y_), 1, (40, 90, 160), -1)
        pts = np.array([P(a_, y_) for a_, y_ in zip(Arows[i, S.J_B:S.J_FACEBOT + 1], Yrows[i, S.J_B:S.J_FACEBOT + 1])], np.int32)
        cv2.polylines(img, [pts], False, (40, 40, 210), 2)
        for k, colr in (("r2", (60, 150, 40)), ("r3", (200, 160, 20))):
            js = np.nonzero(masks[k][i])[0]
            for j in js:
                cv2.circle(img, P(Arows[i, j], Yrows[i, j]), 3, colr, -1)
        cr = s["crest"]; fe = s["front_edge"]
        cv2.circle(img, P(cr["a"], cr["y_over_H0"] * S.H0), 6, (0, 0, 0), 2)
        q = P(fe["a"], fe["y_over_H0"] * S.H0)
        cv2.drawMarker(img, q, (0, 0, 0), cv2.MARKER_TRIANGLE_UP, 12, 2)
        # 射線の向き（原画のカメラから頂へ）
        cam = S.CAM_SEC
        v = np.array([cr["a"] - cam[0], cr["y_over_H0"] * S.H0 - cam[1]]); v /= np.linalg.norm(v)
        cv2.arrowedLine(img, (pw - 60, 70), (int(pw - 60 + 40 * v[0]), int(70 - 40 * v[1])), (90, 90, 90), 2, tipLength=0.3)
        im = Image.fromarray(img[..., ::-1])
        C.paste(im, (px0, py0))
        dd = ImageDraw.Draw(C)
        txt = "c %.1f m：頂 %.2f H0（a %.1f）、唇の先 a %.1f（頂の %.1f m 前・%.2f H0）" % (s["c"], cr["y_over_H0"], cr["a"], fe["a"], fe["ahead_of_crest_m"], fe["y_over_H0"])
        dd.text((px0 + 6, py0 + 4), txt, font=font(13), fill=(20, 20, 20))
        dd.text((px0 + 6, py0 + 22), "唇の下の引っ込み %s m　前の空き（0.15〜0.45 H0）%s" % (s["undercut_m"], s["free_cells_ahead_0.15_0.45H0_share"]), font=font(13), fill=(20, 20, 20))
    d.text((20, 1052), "numpy で描いた断面（Unity の描画ではない）。茶の点 = wave4 のその c の点。禁止域は仕上げ28 の格子（keepout_d3・protect_grids）。", font=font(14), fill=(90, 90, 90))
    C.save(OUT + "/diag_2_sections.png")


def sheet_plan(h, g, crest04, masks, c, Arows, Yrows, ref_peaks):
    W, H = 1920, 1080
    C = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(C)
    d.text((20, 10), "調べ 3：上から見た高さの場（見本04 = 主役波 AS04F ＋ wave4）。峰と突出。②③ に自分の峰がない", font=font(28), fill=(20, 20, 20))
    d.text((20, 50), "横 = a（右が前・原画のカメラの側）、縦 = c（下が +c・原画視点の右奥）。等高線 0.05 H0 おき。点 = 原画視点で各区域に見えている面（赤 ①・緑 ②・水色 ③）。"
           "★ = 峰（数 = 突出 m）。◇ = 参照モデルの峰の位置（数だけ、整列 B）", font=font(15), fill=(60, 60, 60))
    box = (-14.0, 18.0, -32.0, 10.0)
    ia0 = int((box[0] - g["a0"]) / g["res"]); ia1 = int((box[1] - g["a0"]) / g["res"])
    ic0 = int((box[2] - g["c0"]) / g["res"]); ic1 = int((box[3] - g["c0"]) / g["res"])
    sub = h[ic0:ic1, ia0:ia1]
    v = np.clip(sub / S.H0, 0, 1)
    img = cv2.applyColorMap((255 - v * 200).astype(np.uint8), cv2.COLORMAP_BONE)
    for lv in np.arange(0.05, 1.0, 0.05):
        m = (sub >= lv * S.H0).astype(np.uint8)
        cnt, _ = cv2.findContours(m, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(img, cnt, -1, (60, 60, 60) if abs(lv * 10 - round(lv * 10)) < 1e-6 else (150, 150, 150), 1)
    s = 7
    img = cv2.resize(img, None, fx=5, fy=5, interpolation=cv2.INTER_NEAREST)
    fx = img.shape[1] / (ia1 - ia0); fy = img.shape[0] / (ic1 - ic0)

    def Pp(a, cc):
        return int((a - box[0]) / g["res"] * fx), int((cc - box[2]) / g["res"] * fy)
    for k, colr in (("r1", (40, 52, 214)), ("r2", (60, 150, 40)), ("r3", (200, 160, 20))):
        rr, cc = np.nonzero(masks[k])
        for r_, c_ in zip(rr[::7], cc[::7]):
            cv2.circle(img, Pp(Arows[r_, c_], c[r_]), 1, colr, -1)
    for pk in crest04:
        p = Pp(pk["a"], pk["c"])
        cv2.drawMarker(img, p, (0, 0, 220), cv2.MARKER_STAR, 16, 2)
        lab = "max" if pk["prominence_m"] == "global_max" else "%.2f" % pk["prominence_m"]
        cv2.putText(img, lab, (p[0] + 8, p[1] - 4), 0, 0.5, (0, 0, 180), 1)
    for pk in ref_peaks:
        p = Pp(pk["a"], pk["c"])
        cv2.drawMarker(img, p, (160, 0, 160), cv2.MARKER_DIAMOND, 12, 2)
        if pk["prominence_m"] != "global_max":
            cv2.putText(img, "%.2f" % pk["prominence_m"], (p[0] + 8, p[1] + 14), 0, 0.45, (160, 0, 160), 1)
    for a_ in range(-12, 19, 4):
        p = Pp(a_, box[2]); cv2.putText(img, "a%d" % a_, (p[0], 14), 0, 0.45, (0, 0, 0), 1)
    for c_ in range(-30, 11, 4):
        p = Pp(box[0], c_); cv2.putText(img, "c%d" % c_, (2, p[1] + 4), 0, 0.45, (0, 0, 0), 1)
    im = Image.fromarray(img[..., ::-1])
    if im.size[1] > 960:
        im = im.resize((int(im.size[0] * 960 / im.size[1]), 960))
    C.paste(im, (20, 84))
    x = 40 + im.size[0]
    lines = ["峰（見本04）：", ]
    for pk in crest04:
        lines.append(" c %.1f・a %.1f・%.2f H0 区域 %s 突出 %s" % (pk["c"], pk["a"], pk["y_over_H0"], ",".join(pk["regions"]) or "なし", pk["prominence_m"]))
    lines += ["", "参照モデルの峰（数だけ）："]
    for pk in ref_peaks[:8]:
        lines.append(" c %.1f・a %.1f・高さ %.1f m 突出 %s" % (pk["c"], pk["a"], pk["y"], pk["prominence_m"]))
    for i, t in enumerate(lines):
        d.text((x, 90 + 22 * i), t, font=font(14), fill=(20, 20, 20))
    d.text((20, 1052), "numpy の高さの場（0.25 m の格子、面の点の高さの最大）。参照モデルは数だけで、形は描かない。", font=font(14), fill=(90, 90, 90))
    C.save(OUT + "/diag_3_plan.png")


def sheet_views(s11, seat):
    W, H = 1920, 1080
    C = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(C)
    d.text((20, 10), "調べ 4：見本04 の層の色づけ（赤 ①・緑 ②・水色 ③・青 wave4・灰 ほかの前の面・濃い灰 背、黒線 = 遮る縁）", font=font(26), fill=(20, 20, 20))
    names = ["side_left", "top", "tt0", "tt30", "tt60", "tt90", "tt240", "tt270", "tt300", "tt330"]
    tw, th = 372, 210
    for n, vn in enumerate(names):
        p = S.P4 + "/assemble/measure_fix1/s11/S04_%s.png" % vn
        if not os.path.isfile(p):
            continue
        im = Image.open(p).convert("RGB"); im = im.resize((tw, th))
        x, y = 20 + (n % 5) * (tw + 6), 60 + (n // 5) * (th + 50)
        C.paste(im, (x, y))
        v = s11.get(vn, {})
        vp = v.get("visible_px", {})
        pr = v.get("pairs", {})
        t = "%s　①%s ②%s ③%s" % (vn, vp.get("1"), vp.get("2"), vp.get("3"))
        t2 = "①② %s・②③ %s" % ({True: "分かれる", False: "続く", None: "片方なし"}[pr.get("1-2", {}).get("separated")],
                               {True: "分かれる", False: "続く", None: "片方なし"}[pr.get("2-3", {}).get("separated")])
        d.text((x, y + th + 2), t, font=font(13), fill=(20, 20, 20)); d.text((x, y + th + 20), t2, font=font(13), fill=(20, 20, 20))
    for n, vn in enumerate(("seat", "seat_toward_wave", "back65")):
        p = S.TMP + "/views_%s.png" % vn
        if not os.path.isfile(p):
            continue
        im = Image.open(p).convert("RGB").resize((tw, th))
        x, y = 20 + n * (tw + 6), 60 + 2 * (th + 50)
        C.paste(im, (x, y))
        vp = seat.get(vn, {}).get("visible_px", {})
        d.text((x, y + th + 2), "%s　①%s ②%s ③%s wave4 %s" % (vn, vp.get("1"), vp.get("2"), vp.get("3"), vp.get("5")), font=font(13), fill=(20, 20, 20))
    d.text((20, 1052), "numpy の z バッファの粘土（Unity の描画ではない）。層の印は見本04 の測り（c の帯 ① −2〜+8、② −15.5〜−11.5、③ −23〜−17、頂より前で 0.25 H0 以上）。",
           font=font(14), fill=(90, 90, 90))
    C.save(OUT + "/diag_4_views.png")


def main():
    os.makedirs(S.TMP, exist_ok=True)
    c, Ar, Yr = S.load_rows(S.ROWS04F)
    log("区域 → 3D")
    rmap, masks = region_map(c, Ar, Yr)
    c2, A2, Y2 = S.load_rows(S.ROWS02C)
    rmap03, _ = region_map(c2, A2, Y2)
    log("高さの場")
    Q = S.rows_points(c, Ar, Yr, up=3)
    ch, tri, _ = S.W4.read_static(S.WAVE4_F1)
    h, g = S.heightfield(np.concatenate([Q, S.mesh_points(ch["position"])]))
    crest04 = S.crest_layers(h, g)
    hh = S.heightfield(np.concatenate([Q]))[0]
    crest04_hero = S.crest_layers(hh, g)
    h03, _ = S.heightfield(S.rows_points(c2, A2, Y2, up=3))
    crest03 = S.crest_layers(h03, g)
    ref = json.load(open(OUT + "/s5_obj_numbers.json", encoding="utf-8")) if os.path.isfile(OUT + "/s5_obj_numbers.json") else {"peaks": []}
    ref_left = [p for p in ref["peaks"] if p["c"] <= -2.0 or p["prominence_m"] == "global_max"]
    log("断面")
    secs, G, Gp, R2 = sections(c, Ar, Yr, masks)
    log("色")
    cmp, pd, cp, imgs = colour_compare()
    cam = A.painting_cam(1)
    tris, kind, rows, cols = painting_scene(c, Ar, Yr)
    idb, _ = S.U.raster(cam, tris, np.arange(1, len(tris) + 1, dtype=np.int64))
    idb = idb.reshape(cam.H, cam.W)
    hero_mask = (idb > 0) & (idb <= len(rows))
    t56 = t5_t6(imgs, hero_mask)
    log("視点")
    rc = json.load(open(S.P4 + "/rules_check.json", encoding="utf-8"))["rules"]["S11"]
    s11v = rc["views"]["AS04_union"]
    seat = seat_layers()
    res = {"inputs": {"rows_AS04F": S.ROWS04F.replace(S.REPO + "/", ""), "rows_AS04F_sha256": S.sha(S.ROWS04F),
                      "wave4_fix1": S.WAVE4_F1.replace(S.REPO + "/", ""), "wave4_fix1_sha256": S.sha(S.WAVE4_F1),
                      "render_FX1_painting": "Unity/Build/Polish/sample04/assemble/render/FX1/views/painting_t120_claws.png",
                      "render_FX1_painting_sha256": S.sha(S.RENDER_F1 + "/views/painting_t120_claws.png"),
                      "painting_sha256": S.sha(S.PAINT), "reference_numbers": "s5_obj_numbers.json（数だけ）"},
           "region_to_3d_AS04F": rmap, "region_to_3d_AS02C_sample03": rmap03,
           "crests_AS04F_union": crest04, "crests_AS04F_hero_only": crest04_hero, "crests_AS02C_sample03": crest03,
           "crests_reference_left": ref_left,
           "sections_AS04F": secs, "colour_compare": cmp, "T5_T6_baseline": t56,
           "S11_sample04": {"summary": rc["summary"]["AS04_union"], "geometry_steps": rc["geometry_steps"]["AS04"]}, "seat_and_other_views": seat,
           "read_crest_lines_painting_px": READ_CREST, "seconds": round(time.time() - T0, 1)}
    S.jdump(OUT + "/diag.json", res)
    log("図")
    sheet_painting(cmp, pd, cp, imgs)
    sheet_sections(c, Ar, Yr, secs, G, Gp, R2, masks)
    sheet_plan(h, g, crest04, masks, c, Ar, Yr, ref_left)
    sheet_views(s11v, seat)
    log("おわり")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
