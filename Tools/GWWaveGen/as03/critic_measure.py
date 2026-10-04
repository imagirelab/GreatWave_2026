# -*- coding: utf-8 -*-
"""美術の見本03 の批評（CRITIC）で使った測り。描画（Unity の画と冠の ID の画）だけを読む。写真・OBJ は読まない。

測るもの（変種ごと、視点ごと）：
  crown_share   見える白のうち冠（ID の画で (13,55,255)）の割合。彫刻の前の側では白は冠だけ（調べ S1 §3）
  ring_white / ring_indigo  冠の指の周り（1〜5 px の輪）の白・藍の割合。彫刻の垂れる帯では藍 0.55〜0.75（S1 §2）
  white_lum     白の明るさ（RGB の平均、sRGB 0〜255）の p5/p25/p50/p75/p95
  dark_crown_blobs  白の中の小さく暗い冠の塊（面の下から出た芯など。8〜400 px、周りの 0.8 倍より暗い）
  protrusion    回り台：主役波の輪郭より上に出た冠の高さ（主役波の見える高さに対する比）の p50 と数
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/critic_measure.py
出力：Unity/Build/Polish/sample03/critic/critic_metrics.json
"""
import json
import os

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

ROOT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03"
RENDER = ROOT + "/assemble/render"
OUT = ROOT + "/critic/critic_metrics.json"


def load(p):
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float32)


def crown_of(m):
    return (np.abs(m[..., 0] - 13) < 6) & (np.abs(m[..., 1] - 55) < 8) & (m[..., 2] > 240)


def view_metrics(img_p, mask_p, crest_view):
    a = load(img_p)
    m = load(mask_p).astype(np.int32)
    crown = crown_of(m)
    lum = a.mean(-1)
    sat = a.max(-1) - a.min(-1)
    if crest_view:  # 波頭の回り台：灰の背景と空を除く
        bg = a[400, 1850]
        obj = np.abs(a - bg).sum(-1) > 12
        obj[:300] = False
    else:  # ほかの視点：ID の画で何か描かれた所
        obj = m.sum(-1) > 0
    white = obj & (lum > 120) & (sat < 30)
    share = float((crown & white).sum() / max(1, white.sum()))
    ring = ndi.binary_dilation(crown, iterations=5) & ~ndi.binary_dilation(crown, iterations=1)
    w2 = (lum > 140) & (sat < 30)
    ind = (a[..., 2] > a[..., 0] + 20) & (lum < 130)
    wl = lum[obj & (sat < 25) & (lum > 90)]
    lab, n = ndi.label(crown)
    idx = range(1, n + 1)
    sizes = ndi.sum(crown, lab, idx) if n else []
    means = ndi.mean(lum, lab, idx) if n else []
    labd = ndi.grey_dilation(lab, size=9)
    rr = ndi.binary_dilation(crown, iterations=4) & ~crown
    rmean = ndi.mean(lum, labd * rr, idx) if n else []
    blobs = []
    for i, (s, mu, rm) in enumerate(zip(sizes, means, rmean)):
        if 8 <= s <= 400 and mu < 0.8 * rm and rm > 130:
            ys, xs = np.nonzero(lab == i + 1)
            blobs.append([int(xs.mean()), int(ys.mean()), int(s), int(mu), int(rm)])
    return {
        "white_px": int(white.sum()),
        "crown_px": int(crown.sum()),
        "crown_share_of_white": round(share, 3),
        "ring_white": round(float(w2[ring].mean()), 3) if ring.any() else None,
        "ring_indigo": round(float(ind[ring].mean()), 3) if ring.any() else None,
        "white_lum_p5_25_50_75_95": [int(v) for v in np.percentile(wl, [5, 25, 50, 75, 95])] if wl.size else None,
        "dark_crown_blobs_in_white": blobs,
    }


def protrusion(mask_p):
    m = load(mask_p).astype(np.int32)
    crown = crown_of(m)
    hero = (m[..., 0] > 200) & (m[..., 1] < 60) & (m[..., 2] < 60)
    H, W = crown.shape
    top_h = np.full(W, H)
    top_c = np.full(W, H)
    for x in np.nonzero(hero.any(0))[0]:
        top_h[x] = np.argmax(hero[:, x])
    for x in np.nonzero(crown.any(0))[0]:
        top_c[x] = np.argmax(crown[:, x])
    prot = np.clip(top_h - top_c, 0, None)
    prot[top_h == H] = 0
    ys = np.nonzero(hero.any(1))[0]
    hh = int(ys.max() - ys.min()) if ys.size else 1
    lab, n = ndi.label(prot > 2)
    pk = np.array(ndi.maximum(prot, lab, range(1, n + 1))) if n else np.zeros(0)
    return {"visible_wave_h_px": hh, "protrusions": int(n),
            "peak_over_h_p50": round(float(np.median(pk) / hh), 3) if n else 0.0}


def main():
    res = {"note_ja": "批評の測り。描画だけを読む（写真・OBJ は読まない）。", "variants": {}}
    for V in ["V1", "V2", "V3"]:
        r = {"crest": {}, "views": {}, "turntable_protrusion": {}}
        for az in ["000", "045", "090", "135", "180", "225", "270", "315"]:
            p = f"{RENDER}/{V}/crest/t120_az{az}_claws.png"
            q = f"{RENDER}/{V}/crest/t120_az{az}_claws_crownmask.png"
            if os.path.exists(p) and os.path.exists(q):
                r["crest"][az] = view_metrics(p, q, True)
        for v in ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]:
            p = f"{RENDER}/{V}/views/{v}_t120_claws.png"
            q = f"{RENDER}/{V}/views/{v}_t120_claws_crownmask.png"
            if os.path.exists(p) and os.path.exists(q):
                r["views"][v] = view_metrics(p, q, False)
        for az in ["090", "120", "180", "210", "240", "270"]:
            q = f"{RENDER}/{V}/tt/t120_az{az}_claws_crownmask.png"
            if os.path.exists(q):
                r["turntable_protrusion"][az] = protrusion(q)
        res["variants"][V] = r
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for V, r in res["variants"].items():
        cs = {k: v["crown_share_of_white"] for k, v in r["crest"].items()}
        vs = {k: v["crown_share_of_white"] for k, v in r["views"].items()}
        print(V, "crest crown share", cs)
        print(V, "views crown share", vs)
        print(V, "protrusion p50", {k: v["peak_over_h_p50"] for k, v in r["turntable_protrusion"].items()})


if __name__ == "__main__":
    main()
