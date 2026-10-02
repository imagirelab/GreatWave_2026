# -*- coding: utf-8 -*-
"""仕上げ33修正01 変種 SWEEP：指が「面に描いた模様」でなく「波から立つ白い指」として見えるかの数（numpy・OpenCV。記録のみ）。

画像（Unity の PC オフスクリーン描画、1920×1080、前＝仕上げ33 修正の回 2、後＝SWEEP、同じ視点・同じ時刻 t 9・10.5・12 s）：
  - 爪の画素：作品のまま（asis）と爪なし（clawfree）の差の最大のチャンネル > 12
  - 地ごとの爪の画素：爪なしの同じ画素が 空（明るさ ≥ 170 かつ 青 − 赤 < −40 の生成りの空と、明るさ 110〜200 で彩度 < 25 の灰色の空。主役波の白は 青 − 赤 ≈ −25・明るさ ≈ 238 なので白に入る）／藍（明るさ < 110）／白（それ以外）。
    空と藍の上の爪の画素は、主役波の輪郭の外か藍の面の前へ出た爪（立った指の読みの代わりの数）。白の上は白の面の上の線と陰。
  - 白い爪の画素：爪の画素のうち、明るさ ≥ 200 かつ 青 − 赤 > −45（白・生成り）の割合（線ばかりでなく白い体が見えるか）
幾何（爪の並びの t* のコマ）：指（C…）と冠の爪（K…）の輪の中心の、t* の主役波のシートからの高さ（最も近い頂点の法線の向き）の最大の分布と、
  1 m・2 m 以上立つ本数。3D の長さ（輪の中心と先の折れ線）。頂点・三角形の数。
出力：--out の sweep_measure.json
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/sweep_measure.py --after-run … --after-claws … --out …
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
import sweep_build as SB  # noqa: E402

U = SB.U
B = REPO + "/Unity/Build/Polish"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TS = ["t090", "t105", "t120"]


def stats(a, b):
    a = a.astype(np.int16)
    b = b.astype(np.int16)
    m = np.abs(a - b).max(2) > 12
    lum = b.mean(2)
    chroma = b.max(2) - b.min(2)
    sky = ((lum >= 170) & ((b[..., 0] - b[..., 2]) < -40)) | ((lum >= 110) & (lum < 200) & (chroma < 25))   # 生成りの空と、側面・後ろ・真上の灰色の空
    ind = lum < 110
    wht = ~sky & ~ind
    la = a.mean(2)
    white_body = m & (la >= 200) & ((a[..., 0] - a[..., 2]) > -45)
    return dict(claw=int(m.sum()), over_sky=int((m & sky).sum()), over_indigo=int((m & ind).sum()), over_white=int((m & wht).sum()),
                white_body=int(white_body.sum()))


def images(run):
    out = {}
    for v in VIEWS:
        for t in TS:
            pa = os.path.join(run, "views", "%s_%s_asis.png" % (v, t))
            pb = os.path.join(run, "views", "%s_%s_clawfree.png" % (v, t))
            if os.path.exists(pa) and os.path.exists(pb):
                out["%s_%s" % (v, t)] = stats(cv2.imread(pa), cv2.imread(pb))
    return out


def geometry(claws, sheet):
    lay = json.load(open(os.path.join(claws, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    Y = np.memmap(os.path.join(claws, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))[360]
    res = {}
    for pre in ("C", "K", "W", "S"):
        hs, ls = [], []
        for c in lay["claws"]:
            if not c["id"].startswith(pre):
                continue
            o, n = c["vert_offset"], c["stations"]
            rg = np.asarray(Y[o + 1:o + 1 + n * 8], np.float64).reshape(n, 8, 3)
            # 輪の中心＝頂点 2（白の中心、+N）と 6（水色の版の中心、−N）の中点（SWEEP の輪は角度が不揃いなので 8 頂点の平均は中心でない）
            cen = 0.5 * (rg[:, 2] + rg[:, 6]) if pre in ("C", "K") else rg.mean(1)
            cen = np.vstack([cen, np.asarray(Y[o + 1 + n * 8], np.float64)[None]])
            hs.append(float(sheet.height(cen).max()))
            ls.append(float(np.linalg.norm(np.diff(cen, axis=0), axis=1).sum()))
        if hs:
            hs, ls = np.array(hs), np.array(ls)
            res[pre] = dict(n=int(len(hs)), h_max_pct=np.percentile(hs, [10, 50, 90, 100]).round(3).tolist(),
                            stand_ge_1m=int((hs >= 1.0).sum()), stand_ge_2m=int((hs >= 2.0).sum()),
                            len3d_pct=np.percentile(ls, [10, 50, 90, 100]).round(3).tolist())
    # 貫通（pl33f_measure.py と同じ式：全部の列の頂点の法線、接線の離れ 0.3 m 未満の輪のうち 5 cm より下。輪の中心は頂点 2 と 6 の中点）
    hero = U.K.Pkg(SB.HERO)
    from scipy.spatial import cKDTree
    wt, wtau = SB.W31.load_warp(SB.WARP)
    pen = {}
    for f in (270, 315, 360):
        tk = f / 30.0
        tau = 0.0 if tk >= 12.0 - 1e-9 else float(np.interp(tk, wt, wtau))
        Xs = hero.world(tau)
        Vf = Xs.reshape(-1, 3)
        tree = cKDTree(Vf)
        nrm = np.cross(np.gradient(Xs, axis=0), np.gradient(Xs, axis=1))
        nrm = (nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)).reshape(-1, 3)
        Yf = np.memmap(os.path.join(claws, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))[f]
        for pre in ("C", "K", "W", "S"):
            below, tot, deep = 0, 0, 0.0
            for c in lay["claws"]:
                if not c["id"].startswith(pre):
                    continue
                o, n = c["vert_offset"], c["stations"]
                rg = np.asarray(Yf[o + 1:o + 1 + n * 8], np.float64).reshape(n, 8, 3)
                ctr = 0.5 * (rg[:, 2] + rg[:, 6])
                if np.linalg.norm(ctr[-1] - ctr[0]) < 1e-3:
                    continue
                _, ii = tree.query(ctr)
                e = ctr - Vf[ii]
                h = (e * nrm[ii]).sum(1)
                tang = np.linalg.norm(e - h[:, None] * nrm[ii], axis=1)
                ok = tang < 0.3
                tot += int(ok.sum())
                bb = ok & (h < -0.05)
                below += int(bb.sum())
                if bb.any():
                    deep = min(deep, float(h[bb].min()))
            if tot:
                pen["%s_t%03d" % (pre, int(round(f / 3)))] = dict(rings_below_5cm=below, rings_checked=tot, deepest_m=round(deep, 3))
    res["penetration_centre_v2v6"] = pen
    res["vertices"] = lay["vertices"]
    res["triangles"] = lay["triangles"]
    res["entries"] = len(lay["claws"])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before-run", default=B + "/33/fix02/r_fix02")
    ap.add_argument("--before-claws", default=B + "/33/fix02/claws")
    ap.add_argument("--after-run", required=True)
    ap.add_argument("--after-claws", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    hero = U.K.Pkg(SB.HERO)
    sheet = SB.Sheet(hero.world(0.0))
    res = dict(rule_ja=__doc__.strip().split("\n\n")[1],
               before=dict(run=os.path.relpath(a.before_run, REPO).replace("\\", "/"), images=images(a.before_run), geometry=geometry(a.before_claws, sheet)),
               after=dict(run=os.path.relpath(a.after_run, REPO).replace("\\", "/"), images=images(a.after_run), geometry=geometry(a.after_claws, sheet)))
    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(os.path.join(a.out, "sweep_measure.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in sorted(res["after"]["images"]):
        if k.endswith("t120") or k.endswith("t105"):
            print(k, "before", res["before"]["images"].get(k), "after", res["after"]["images"][k])
    print("geometry before", json.dumps(res["before"]["geometry"], ensure_ascii=False))
    print("geometry after", json.dumps(res["after"]["geometry"], ensure_ascii=False))


if __name__ == "__main__":
    main()
