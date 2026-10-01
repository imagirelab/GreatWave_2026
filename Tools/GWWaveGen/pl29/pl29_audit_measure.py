# -*- coding: utf-8 -*-
"""仕上げ29（Q28）の前の点検（AUDIT）：今の採用の状態の Unity の描画（PL29Audit.cs）から、原画カメラからの投影の焼き込みが
破れる所を画素で数える。

入力（PL29Audit の出力 <before>/{views,diag,tt}）と、焼き込みのテクセルのカテゴリ（af28r01_uvcat_a45.bin、4096×4096）。
各視点・時刻（と回り台の各方位）で、主役波の見える画素（診断の uv 画像のアルファ 128）を次に分ける：

- カテゴリ（焼き込みがそのテクセルの色をどう決めたか。DS29R01ProjectionBaker の categoriesJa）
    直接（1）・継ぎ目の写し（12）＝原画カメラから見えた所の投影
    外挿の帯（3・9 u 方向、4・10 v 方向、11・6・7 残り）＝同じ行・列の色を写した帯
    平らな塗り（2 内側の藍濃、5 海面の藍濃、8 既定の藍濃）＝原画で見えない所の一色
- 引き伸ばし：直接の画素で、画面の画素あたりの原画の画素（K* の頂点の原画カメラへの投影、px・py 画像）のヤコビアンの
  特異値 σ1 ≥ σ2 から、異方性 σ1/σ2 ≥ ANISO（既定 4）を「引き伸ばし」とする（原画視点の t* では 1）。
- 継ぎ目：同じ面（隣の画素の UV の差 ≤ UVCONT テクセル）で表示の色区（id 画像）が変わる画素のうち、
  原画の座標が FOLD 画素より跳ぶ（投影の折り返し）か、直接と外挿・平らな塗りの境のもの。両側が直接で跳ばないものは原画の色区の境。
- 平らな面：主役波の画素で、色区の境と主役波の外から DFLAT 画素（既定 48）より離れた所（特徴のない芯）。芯の連結成分のうち
  面積 ≥ FLATMIN のものを「平らな面」と数える。
- 溶けた爪：爪が主役波を隠す画素（爪なしで主役波、爪ありで主役波でない）の縁で、爪の色区と隣の見える主役波の色区が同じ割合。
  連結成分（≥ 40 画素）ごとに縁の 80% 以上が同じ色区なら「溶けた爪（色区）」と数える（線（設計38）を切った ID 画像の読み）。
  作品のままの色の画像（線・飛沫あり）でも、爪のまわり 2 画素の輪のうち爪の色と L1 で 60 以上違う画素が 30% 未満なら「溶けた爪（色）」と数える。

出力：<out>/audit_metrics.json（視点・時刻ごとの数と、全体の表）、<out>/components.json（切り抜きの元の成分）。
数値の読み方・閾値は進行役の判断（Q24）で、この点検のために決めた。原画視点の評価器（評価器 23）の代わりではない。
使い方：py -3.10 -B Tools/GWWaveGen/pl29/pl29_audit_measure.py --before <dir> --cat <uvcat.bin> --out <dir>
"""
import argparse
import hashlib
import json
import os
import time

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

W, H, N = 1920, 1080, 4096
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TIMES = ["t060", "t090", "t105", "t120"]
ANISO = 4.0
UVCONT = 24
FOLD = 20.0
DFLAT = 48
FLATMIN = 2000
BANDMIN = 1500
CLAWMIN = 40
RING = 60
RINGFRAC = 0.3
CAT_DIRECT = (1, 12)
CAT_BAND = (3, 9, 4, 10, 11, 6, 7)
CAT_FLAT = (2, 5, 8)
CAT_NAMES = {0: "未設定", 1: "直接", 2: "内側の藍濃", 3: "u 方向（色）", 4: "v 方向（縞・画面外）", 5: "海面の藍濃", 6: "残り u", 7: "残り v",
             8: "残り既定の藍濃", 9: "u 方向（遮蔽物の陰・藍）", 10: "v 方向（遮蔽物の陰・藍）", 11: "残り（同じ列を先に）", 12: "継ぎ目の写し"}
CLS_NAMES = ["白", "淡い水色", "藍中", "藍濃"]


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_rgba(p):
    return np.asarray(Image.open(p).convert("RGBA"))


def dec24(a):
    return (a[..., 0].astype(np.int64) << 16) | (a[..., 1].astype(np.int64) << 8) | a[..., 2].astype(np.int64)


def decode_uv(p):
    a = load_rgba(p)
    hero = a[..., 3] == 128
    v24 = dec24(a)
    u = (v24 >> 12) & 4095
    v = v24 & 4095
    return hero, u.astype(np.int32), v.astype(np.int32)


def decode_p(p):
    a = load_rgba(p)
    v24 = dec24(a).astype(np.float64)
    ok = (a[..., 3] == 128) & (v24 > 0)
    return v24 / 1024.0 - 2048.0, ok


def decode_id(p):
    a = load_rgba(p)[..., :3].astype(np.int32)
    cls = np.full(a.shape[:2], -1, np.int8)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    hi, lo = 200, 50
    cls[(r > hi) & (g < lo) & (b < lo)] = 0
    cls[(r < lo) & (g > hi) & (b < lo)] = 1
    cls[(r < lo) & (g < lo) & (b > hi)] = 2
    cls[(r > hi) & (g > hi) & (b < lo)] = 3
    return cls


def pair_masks(hero, u, v):
    """右・下の隣が同じ面かどうか（両方が主役波で UV の差が UVCONT 以内）。"""
    same_r = np.zeros_like(hero)
    same_d = np.zeros_like(hero)
    same_r[:, :-1] = hero[:, :-1] & hero[:, 1:] & (np.abs(u[:, :-1] - u[:, 1:]) <= UVCONT) & (np.abs(v[:, :-1] - v[:, 1:]) <= UVCONT)
    same_d[:-1, :] = hero[:-1, :] & hero[1:, :] & (np.abs(u[:-1, :] - u[1:, :]) <= UVCONT) & (np.abs(v[:-1, :] - v[1:, :]) <= UVCONT)
    return same_r, same_d


def components(mask, minsize, structure=None):
    lab, n = ndi.label(mask, structure=structure if structure is not None else np.ones((3, 3), bool))
    if n == 0:
        return lab, []
    sizes = ndi.sum(np.ones_like(mask, dtype=np.int32), lab, index=np.arange(1, n + 1))
    objs = ndi.find_objects(lab)
    out = []
    for i, (s, sl) in enumerate(zip(sizes, objs)):
        if s >= minsize:
            out.append({"label": i + 1, "area": int(s), "bbox": [int(sl[1].start), int(sl[0].start), int(sl[1].stop), int(sl[0].stop)]})
    out.sort(key=lambda d: -d["area"])
    return lab, out


def analyse(stem_diag, cat, want_maps=False, colour=None):
    hero0, u0, v0 = decode_uv(stem_diag + "_uv_claws0.png")
    hero1, _, _ = decode_uv(stem_diag + "_uv_claws1.png")
    px, okx = decode_p(stem_diag + "_px_claws0.png")
    py, oky = decode_p(stem_diag + "_py_claws0.png")
    id0 = decode_id(stem_diag + "_id_claws0.png")
    id1 = decode_id(stem_diag + "_id_claws1.png")
    nhero = int(hero0.sum())
    res = {"heroPx": nhero}
    if nhero == 0:
        return res, None
    c = np.zeros(hero0.shape, np.uint8)
    c[hero0] = cat[v0[hero0] * N + u0[hero0]]
    direct = hero0 & np.isin(c, CAT_DIRECT)
    band = hero0 & np.isin(c, CAT_BAND)
    flat = hero0 & np.isin(c, CAT_FLAT)
    res["catPx"] = {CAT_NAMES[k]: int((hero0 & (c == k)).sum()) for k in range(13) if (hero0 & (c == k)).any()}
    res["directFrac"] = float(direct.sum() / nhero)
    res["bandFrac"] = float(band.sum() / nhero)
    res["flatFillFrac"] = float(flat.sum() / nhero)
    cls0 = np.where(hero0, id0, -1)
    res["classPx"] = {CLS_NAMES[k]: int((cls0 == k).sum()) for k in range(4)}
    # ---- 引き伸ばし（直接の画素。中心差分。4 近傍が同じ面で直接、折り返しなし）
    same_r, same_d = pair_masks(hero0, u0, v0)
    pok = okx & oky
    dpx_r = np.zeros_like(px); dpy_r = np.zeros_like(py); dpx_d = np.zeros_like(px); dpy_d = np.zeros_like(py)
    dpx_r[:, :-1] = px[:, 1:] - px[:, :-1]; dpy_r[:, :-1] = py[:, 1:] - py[:, :-1]
    dpx_d[:-1, :] = px[1:, :] - px[:-1, :]; dpy_d[:-1, :] = py[1:, :] - py[:-1, :]
    jump_r = np.hypot(dpx_r, dpy_r); jump_d = np.hypot(dpx_d, dpy_d)
    fold_r = same_r & direct & np.roll(direct, -1, 1) & pok & np.roll(pok, -1, 1) & (jump_r > FOLD)
    fold_d = same_d & direct & np.roll(direct, -1, 0) & pok & np.roll(pok, -1, 0) & (jump_d > FOLD)
    goodr = same_r & direct & np.roll(direct, -1, 1) & pok & np.roll(pok, -1, 1) & ~fold_r
    goodd = same_d & direct & np.roll(direct, -1, 0) & pok & np.roll(pok, -1, 0) & ~fold_d
    # 中心：左右・上下の両方の対がよい画素
    gx = goodr & np.roll(goodr, 1, 1)
    gy = goodd & np.roll(goodd, 1, 0)
    valid = gx & gy
    a = 0.5 * (dpx_r + np.roll(dpx_r, 1, 1)); cc = 0.5 * (dpy_r + np.roll(dpy_r, 1, 1))
    b = 0.5 * (dpx_d + np.roll(dpx_d, 1, 0)); d = 0.5 * (dpy_d + np.roll(dpy_d, 1, 0))
    S = a * a + b * b + cc * cc + d * d
    det = np.abs(a * d - b * cc)
    s1 = np.sqrt(np.maximum(0.5 * (S + np.sqrt(np.maximum(S * S - 4 * det * det, 0))), 1e-12))
    s2 = det / s1
    aniso = np.where(valid, s1 / np.maximum(s2, 1e-9), np.nan)
    stretch = valid & (aniso >= ANISO)
    nv = int(valid.sum())
    res["stretch"] = {
        "validPx": nv, "stretchPx": int(stretch.sum()), "stretchFracOfValid": float(stretch.sum() / max(nv, 1)),
        "stretchFracOfHero": float(stretch.sum() / nhero),
        "anisoP50": float(np.nanpercentile(aniso, 50)) if nv else None, "anisoP90": float(np.nanpercentile(aniso, 90)) if nv else None,
        "anisoP99": float(np.nanpercentile(aniso, 99)) if nv else None,
        "sigma2P50": float(np.percentile(s2[valid], 50)) if nv else None, "sigma2P10": float(np.percentile(s2[valid], 10)) if nv else None,
    }
    # ---- 継ぎ目（表示の色区が変わる同じ面の隣どうし）
    ce_r = same_r & (cls0 != np.roll(cls0, -1, 1)) & (cls0 >= 0) & (np.roll(cls0, -1, 1) >= 0)
    ce_d = same_d & (cls0 != np.roll(cls0, -1, 0)) & (cls0 >= 0) & (np.roll(cls0, -1, 0) >= 0)
    grp = np.zeros(hero0.shape, np.int8)
    grp[direct] = 1; grp[band] = 2; grp[flat] = 3
    fb_r = same_r & (grp != np.roll(grp, -1, 1)) & ((grp == 1) | (np.roll(grp, -1, 1) == 1))
    fb_d = same_d & (grp != np.roll(grp, -1, 0)) & ((grp == 1) | (np.roll(grp, -1, 0) == 1))
    both_direct_r = (grp == 1) & (np.roll(grp, -1, 1) == 1)
    both_direct_d = (grp == 1) & (np.roll(grp, -1, 0) == 1)
    seam_fold = (ce_r & fold_r) | (ce_d & fold_d)
    seam_fb = (ce_r & fb_r) | (ce_d & fb_d)
    band_edge = (ce_r & ~both_direct_r & ~fb_r) | (ce_d & ~both_direct_d & ~fb_d)
    paint_edge = (ce_r & both_direct_r & ~fold_r) | (ce_d & both_direct_d & ~fold_d)
    seam = seam_fold | seam_fb
    seam_d = ndi.binary_dilation(seam, iterations=2)
    _, seam_comps = components(seam_d, 30)
    res["seam"] = {
        "classEdgePx": int((ce_r | ce_d).sum()), "paintingEdgePx": int(paint_edge.sum()), "foldSeamPx": int(seam_fold.sum()),
        "fillBoundarySeamPx": int(seam_fb.sum()), "bandEdgePx": int(band_edge.sum()), "seamPx": int(seam.sum()),
        "seamSegments": len(seam_comps), "seamSegmentsLong": int(sum(1 for s in seam_comps if max(s["bbox"][2] - s["bbox"][0], s["bbox"][3] - s["bbox"][1]) >= 60)),
        "foldPairsNoColourChange": int(((fold_r | fold_d) & ~(ce_r | ce_d)).sum()),
    }
    # ---- 平らな面
    edge_any = np.zeros_like(hero0)
    edge_any |= ce_r | ce_d
    edge_any[:, 1:] |= ce_r[:, :-1]
    edge_any[1:, :] |= ce_d[:-1, :]
    feat = edge_any | ~hero0
    dist = ndi.distance_transform_edt(~feat)
    core = hero0 & (dist > DFLAT)
    lab_core, flat_comps = components(core, FLATMIN)
    for fc in flat_comps:
        m = lab_core == fc["label"]
        # 芯を DFLAT だけ広げた範囲（平らな面のおおよその広さ）のカテゴリの内訳
        x0, y0, x1, y1 = fc["bbox"]
        x0e, y0e, x1e, y1e = max(0, x0 - DFLAT), max(0, y0 - DFLAT), min(W, x1 + DFLAT), min(H, y1 + DFLAT)
        sub = ndi.binary_dilation(m[y0e:y1e, x0e:x1e], iterations=DFLAT) & hero0[y0e:y1e, x0e:x1e]
        cs = c[y0e:y1e, x0e:x1e][sub]
        fc["extentPx"] = int(sub.sum())
        fc["class"] = CLS_NAMES[int(np.bincount(cls0[y0e:y1e, x0e:x1e][sub & (cls0[y0e:y1e, x0e:x1e] >= 0)], minlength=4).argmax())] if (sub & (cls0[y0e:y1e, x0e:x1e] >= 0)).any() else None
        fc["directFrac"] = float(np.isin(cs, CAT_DIRECT).mean()) if cs.size else None
        fc["flatFillFrac"] = float(np.isin(cs, CAT_FLAT).mean()) if cs.size else None
        fc["bandFrac"] = float(np.isin(cs, CAT_BAND).mean()) if cs.size else None
    res["flat"] = {"corePx": int(core.sum()), "coreFracOfHero": float(core.sum() / nhero), "regions": len(flat_comps),
                   "regionsExtentPx": int(sum(f["extentPx"] for f in flat_comps)),
                   "regionsFromFill": int(sum(1 for f in flat_comps if (f["flatFillFrac"] or 0) + (f["bandFrac"] or 0) >= 0.5))}
    # ---- 外挿の帯
    _, band_comps = components(band, BANDMIN, structure=ndi.generate_binary_structure(2, 1))
    res["band"] = {"bandPx": int(band.sum()), "uFillPx": int((hero0 & np.isin(c, (3, 9))).sum()), "vFillPx": int((hero0 & np.isin(c, (4, 10))).sum()),
                   "leftoverPx": int((hero0 & np.isin(c, (11, 6, 7))).sum()), "bands": len(band_comps)}
    # ---- 溶けた爪
    over = hero0 & ~hero1
    cl1 = id1
    claw_edge_same = np.zeros_like(over); claw_edge_all = np.zeros_like(over)
    for sh, ax in ((1, 1), (-1, 1), (1, 0), (-1, 0)):
        nb_hero = np.roll(hero1, sh, ax)
        nb_cls = np.roll(cl1, sh, ax)
        e = over & nb_hero & (cl1 >= 0) & (nb_cls >= 0)
        claw_edge_all |= e
        claw_edge_same |= e & (nb_cls == cl1)
    # 縁の画素の判定：その画素のどの隣の主役波とも同じ色区なら「溶けた」
    claw_edge_diff = np.zeros_like(over)
    for sh, ax in ((1, 1), (-1, 1), (1, 0), (-1, 0)):
        nb_hero = np.roll(hero1, sh, ax); nb_cls = np.roll(cl1, sh, ax)
        claw_edge_diff |= over & nb_hero & (cl1 >= 0) & (nb_cls >= 0) & (nb_cls != cl1)
    melted_edge = claw_edge_all & ~claw_edge_diff
    lab_cl, claw_comps = components(over, CLAWMIN)
    nmelt = 0
    nmelt_c = 0
    col = np.asarray(Image.open(colour).convert("RGB")).astype(np.int32) if colour else None
    for cc_ in claw_comps:
        m = lab_cl == cc_["label"]
        ea = int((claw_edge_all & m).sum()); em = int((melted_edge & m).sum())
        cc_["edgePx"] = ea; cc_["meltedEdgePx"] = em
        cc_["meltedEdgeFrac"] = float(em / ea) if ea else None
        cc_["whiteOnWhiteFrac"] = float(((cl1 == 0) & (id0 == 0) & m).sum() / m.sum())
        cc_["melted"] = bool(ea >= 10 and em / ea >= 0.8)
        nmelt += cc_["melted"]
        if col is not None:
            # 作品のままの色の画像（線・飛沫あり）で、爪のまわり 2 画素の輪のうち爪の色（中央値）と L1 で RING 以上違う画素の割合
            x0, y0, x1, y1 = cc_["bbox"]
            x0e, y0e, x1e, y1e = max(0, x0 - 3), max(0, y0 - 3), min(W, x1 + 3), min(H, y1 + 3)
            mm = m[y0e:y1e, x0e:x1e]
            ring = ndi.binary_dilation(mm, iterations=2) & ~over[y0e:y1e, x0e:x1e]
            cs = col[y0e:y1e, x0e:x1e]
            inner = ndi.binary_erosion(mm, iterations=1)
            dom = np.median(cs[inner if inner.any() else mm], axis=0)
            diff = np.abs(cs[ring] - dom).sum(axis=1)
            cc_["ringPx"] = int(ring.sum())
            cc_["ringContrastFrac"] = float((diff >= RING).mean()) if ring.any() else None
            cc_["meltedColour"] = bool(ring.any() and (diff >= RING).mean() < RINGFRAC)
            nmelt_c += cc_["meltedColour"]
    res["claws"] = {
        "clawOverHeroPx": int(over.sum()), "clawEdgePx": int(claw_edge_all.sum()), "meltedEdgePx": int(melted_edge.sum()),
        "meltedEdgeFrac": float(melted_edge.sum() / max(claw_edge_all.sum(), 1)),
        "whiteOnWhitePx": int((over & (cl1 == 0) & (id0 == 0)).sum()),
        "whiteOnWhiteFrac": float((over & (cl1 == 0) & (id0 == 0)).sum() / max(over.sum(), 1)),
        "clawPieces": len(claw_comps), "clawPiecesMelted": int(nmelt),
        "clawPiecesMeltedColour": int(nmelt_c) if col is not None else None,
        "colourImage": os.path.basename(colour) if colour else None,
    }
    maps = None
    if want_maps:
        maps = {"hero": hero0, "stretch": stretch, "band": band, "flat": flat, "seam": seam, "core": core, "melted": melted_edge,
                "over": over, "lab_core": lab_core, "flat_comps": flat_comps, "band_comps": band_comps, "claw_comps": claw_comps,
                "seam_comps": seam_comps, "px": px, "py": py, "direct": direct}
    return res, maps


def identity_check(stem_diag):
    """原画視点の t*：K* の投影の座標と画面の画素の座標が一致するか（診断の読みの確かめ）。"""
    hero, _, _ = decode_uv(stem_diag + "_uv_claws0.png")
    px, okx = decode_p(stem_diag + "_px_claws0.png")
    py, oky = decode_p(stem_diag + "_py_claws0.png")
    yy, xx = np.nonzero(hero & okx & oky)
    ex = px[yy, xx] - (xx + 0.5)
    ey = py[yy, xx] - (H - 1 - yy + 0.5)
    e = np.hypot(ex, ey)
    return {"n": int(e.size), "medianPx": float(np.median(e)), "p95Px": float(np.percentile(e, 95)), "p99Px": float(np.percentile(e, 99))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--cat", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tt", type=int, default=12)
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    cat = np.fromfile(a.cat, np.uint8)
    assert cat.size == N * N
    # UV の空間でのカテゴリの割合（テクセルの数。面積ではない）
    uvfrac = {CAT_NAMES[k]: float((cat == k).mean()) for k in range(13) if (cat == k).any()}
    out = {"noteJa": __doc__.strip().split("\n")[0], "thresholds": {"ANISO": ANISO, "UVCONT": UVCONT, "FOLD": FOLD, "DFLAT": DFLAT, "FLATMIN": FLATMIN,
                                                                 "BANDMIN": BANDMIN, "CLAWMIN": CLAWMIN, "RING": RING, "RINGFRAC": RINGFRAC},
           "catFile": a.cat, "catSha256": sha(a.cat), "uvTexelCategoryFrac": uvfrac, "views": {}, "tt": {}}
    out["identityCheckPaintingT120"] = identity_check(os.path.join(a.before, "diag", "painting_t120"))
    comps = []
    for v in VIEWS:
        for t in TIMES:
            stem = os.path.join(a.before, "diag", f"{v}_{t}")
            r, m = analyse(stem, cat, want_maps=True, colour=os.path.join(a.before, "views", f"{v}_{t}_asis.png"))
            out["views"][f"{v}_{t}"] = r
            if m is not None:
                np.savez_compressed(os.path.join(a.out, f"maps_{v}_{t}.npz"), **{k: m[k] for k in ("hero", "stretch", "band", "flat", "seam", "core", "melted", "over", "direct")})
                for kind, lst in (("flat", m["flat_comps"]), ("band", m["band_comps"]), ("seam", m["seam_comps"]), ("claw", m["claw_comps"])):
                    for cpt in lst:
                        d = {k: vv for k, vv in cpt.items() if k != "label"}
                        d.update({"kind": kind, "view": v, "t": t})
                        comps.append(d)
                # 引き伸ばしの成分（引き伸ばしの画素を少し広げてまとめる）
                st = ndi.binary_dilation(m["stretch"], iterations=3)
                _, scomps = components(st, 800)
                for cpt in scomps:
                    d = {k: vv for k, vv in cpt.items() if k != "label"}
                    d.update({"kind": "stretch", "view": v, "t": t})
                    comps.append(d)
            print(v, t, r.get("heroPx"), round(r.get("directFrac", 0), 3), flush=True)
    for t in TIMES:
        for k in range(a.tt):
            az = int(round(k * 360 / a.tt))
            stem = os.path.join(a.before, "diag", f"tt_{t}_az{az:03d}")
            r, m = analyse(stem, cat, want_maps=True, colour=os.path.join(a.before, "tt", f"{t}_az{az:03d}_claws.png"))
            out["tt"][f"{t}_az{az:03d}"] = r
            if m is not None:
                np.savez_compressed(os.path.join(a.out, f"maps_tt_{t}_az{az:03d}.npz"), **{k2: m[k2] for k2 in ("hero", "stretch", "band", "flat", "seam", "core", "melted", "over", "direct")})
    # ---- 全体の表
    def agg(rs):
        rs = [r for r in rs if r.get("heroPx", 0) > 0]
        hp = sum(r["heroPx"] for r in rs)
        return {
            "images": len(rs), "heroPx": hp,
            "directFrac": sum(r["directFrac"] * r["heroPx"] for r in rs) / max(hp, 1),
            "bandFrac": sum(r["bandFrac"] * r["heroPx"] for r in rs) / max(hp, 1),
            "flatFillFrac": sum(r["flatFillFrac"] * r["heroPx"] for r in rs) / max(hp, 1),
            "stretchFracOfHero": sum(r["stretch"]["stretchPx"] for r in rs) / max(hp, 1),
            "seamPx": sum(r["seam"]["seamPx"] for r in rs), "seamSegments": sum(r["seam"]["seamSegments"] for r in rs),
            "seamSegmentsLong": sum(r["seam"]["seamSegmentsLong"] for r in rs),
            "flatRegions": sum(r["flat"]["regions"] for r in rs), "flatRegionsFromFill": sum(r["flat"]["regionsFromFill"] for r in rs),
            "flatCoreFracOfHero": sum(r["flat"]["corePx"] for r in rs) / max(hp, 1),
            "bands": sum(r["band"]["bands"] for r in rs),
            "clawOverHeroPx": sum(r["claws"]["clawOverHeroPx"] for r in rs),
            "clawMeltedEdgeFrac": sum(r["claws"]["meltedEdgePx"] for r in rs) / max(sum(r["claws"]["clawEdgePx"] for r in rs), 1),
            "clawPieces": sum(r["claws"]["clawPieces"] for r in rs), "clawPiecesMelted": sum(r["claws"]["clawPiecesMelted"] for r in rs),
            "clawPiecesMeltedColour": sum(r["claws"]["clawPiecesMeltedColour"] or 0 for r in rs),
        }
    out["summaryByView"] = {v: agg([out["views"][f"{v}_{t}"] for t in TIMES]) for v in VIEWS}
    out["summaryByView"]["turntable"] = agg(list(out["tt"].values()))
    out["summaryByTime"] = {t: agg([out["views"][f"{v}_{t}"] for v in VIEWS] + [out["tt"][f"{t}_az{int(round(k * 360 / a.tt)):03d}"] for k in range(a.tt)]) for t in TIMES}
    out["summaryNonPainting"] = agg([out["views"][f"{v}_{t}"] for v in VIEWS if v != "painting" for t in TIMES] + list(out["tt"].values()))
    out["summaryPainting"] = agg([out["views"][f"painting_{t}"] for t in TIMES])
    out["secondsTotal"] = time.time() - t0
    with open(os.path.join(a.out, "audit_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    with open(os.path.join(a.out, "components.json"), "w", encoding="utf-8") as f:
        json.dump(comps, f, ensure_ascii=False, indent=0)
    print("done", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
