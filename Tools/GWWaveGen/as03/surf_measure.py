# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：彫りの面の描画（surf_render.sh の views・crest・ids）を視点ごとに数え、調べ S1 の彫刻の数と比べる（読み取りのみ）。

主役波の画素（主役波の印のアルファ 128）の中で、色区 ID（赤 白・緑 白の陰・青 溝の線・黄 稜）ごとに：
  - 白の明るさの広がり p95−p5（色区の境から 2 画素の内側。S3 と同じ定義）。S1 の彫刻の写真 78〜83、見本02 0〜6
  - 艶の光の画素（S3 と同じ「白の基の色より明るい」L > 249.2 と、藍の上の光 L > 110）
  - 描いた線の画素（藍の線 (31,60,94) ± 10）
  - 色：各色区の明るさの上位 15%・中ほど 20%・下位 15% の平均の sRGB と L*（S1 の lit・mid・shadow と比べる）
  - 前の面（列 ≥ 201：唇の先より先＝管と前の面）で、溝の線（青）÷（青＋黄）＝溝の幅／周期（S1 0.244）
  - 唇の帯（列 111〜200）の白＋白の陰の割合（要求書 T4-4 の案 ≥ 0.6。白の境は B1 の白の印）
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_measure.py <描画のフォルダー> <出力 json>
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
CLS = {"white": (255, 0, 0), "white_shade": (0, 255, 0), "groove": (0, 0, 255), "ridge": (255, 255, 0)}
S1 = {"white": {"lit": [245, 245, 245], "mid": [218, 214, 212], "shadow": [145, 148, 149]},
      "groove": {"lit": [59, 92, 145], "mid": [45, 79, 132], "shadow": [37, 71, 121]},
      "ridge": {"lit": [35, 54, 87], "mid": [17, 20, 32], "shadow": [9, 11, 21]}}


def rgba(p):
    return np.asarray(Image.open(p).convert("RGBA"))


def lum(a):
    a = a[..., :3].astype(float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def lstar(rgb):
    c = np.asarray(rgb, float) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    Y = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    return np.where(Y > 0.008856, 116 * np.cbrt(Y) - 16, 903.3 * Y)


def eq(a, c):
    return (a[..., 0] == c[0]) & (a[..., 1] == c[1]) & (a[..., 2] == c[2])


def near(a, c, tol):
    return np.abs(a[..., :3].astype(int) - np.array(c)[None, None, :]).max(-1) <= tol


def tones(col, m):
    L = lum(col)[m]
    if len(L) < 200:
        return None
    rgb = col[..., :3][m].astype(float)
    o = np.argsort(L)
    n = len(o)
    sel = {"shadow": o[: int(0.15 * n)], "mid": o[int(0.40 * n): int(0.60 * n)], "lit": o[int(0.85 * n):]}
    out = {}
    for k, ix in sel.items():
        c = rgb[ix].mean(0)
        out[k] = {"srgb": [int(round(x)) for x in c], "Lstar": round(float(lstar(c)), 1)}
    return out


def one(col_png, hero_png, id_png):
    col = rgba(col_png); hero = rgba(hero_png); idm = rgba(id_png)
    hm = hero[..., 3] == 128
    hcol = hero[..., 1].astype(int) + 256 * hero[..., 2].astype(int)
    out = {"hero_px": int(hm.sum())}
    if hm.sum() < 500:
        return out
    cls = {k: eq(idm, v) & hm for k, v in CLS.items()}
    out["class_frac"] = {k: round(float(m.sum()) / float(hm.sum()), 4) for k, m in cls.items()}
    L = lum(col)
    wm = ndimage.binary_erosion(cls["white"] | cls["white_shade"], iterations=2)
    if wm.sum() > 50:
        v = L[wm]
        out["white_lum_p5_p50_p95"] = [round(float(np.percentile(v, q)), 1) for q in (5, 50, 95)]
        out["white_lum_spread"] = round(float(np.percentile(v, 95) - np.percentile(v, 5)), 1)
    am = ndimage.binary_erosion(cls["ridge"], iterations=1)
    if am.sum() > 50:
        v = L[am]
        out["ridge_lum_p5_p50_p95"] = [round(float(np.percentile(v, q)), 1) for q in (5, 50, 95)]
    out["specular_px_white"] = int(((L > 249.2) & (cls["white"] | cls["white_shade"])).sum())
    out["specular_px_ai"] = int(((L > 110) & (cls["ridge"] | cls["groove"])).sum())
    # 描いた線：藍の線の色 (31,60,94) ± 12 の画素のうち、白と藍の境の帯（両側 2 画素）にあるもの（FLAT の稜の藍濃は線の色に近いので、帯の外は数えない）
    wcls = cls["white"] | cls["white_shade"]
    band = ndimage.binary_dilation(wcls, iterations=2) & ndimage.binary_dilation(hm & ~wcls, iterations=2)
    out["drawn_line_px"] = int((near(col, (31, 60, 94), 12) & band & hm).sum())
    out["white_edge_band_px"] = int((band & hm).sum())
    face = hm & (hcol >= 201)
    fb = int((cls["groove"] & face).sum()); fy = int((cls["ridge"] & face).sum())
    if fb + fy > 1000:
        out["face_groove_frac"] = round(fb / float(fb + fy), 4)
    lip = hm & (hcol >= 111) & (hcol <= 200)
    if lip.sum() > 500:
        out["lip_white_frac"] = round(float(((cls["white"] | cls["white_shade"]) & lip).sum()) / float(lip.sum()), 4)
    out["tones"] = {k: tones(col, ndimage.binary_erosion(cls[k] | (cls["white_shade"] if k == "white" else False), iterations=1))
                    for k in ("white", "groove", "ridge")}
    return out


def main():
    rdir, outp = sys.argv[1], sys.argv[2]
    res = {"render_dir": rdir.replace("\\", "/"), "views": {}, "crest": {}, "S1_colours_wb": S1}
    for v in VIEWS:
        res["views"][v] = one(f"{rdir}/views/{v}_t120_clawfree.png", f"{rdir}/diag/{v}_t120_hero_claws0.png", f"{rdir}/diag/{v}_t120_id_claws0.png")
    for az in range(0, 360, 45):
        s = "t120_az%03d" % az
        res["crest"]["az%03d" % az] = one(f"{rdir}/crest/{s}_clawfree.png", f"{rdir}/diag/crest_{s}_hero_claws0.png", f"{rdir}/diag/crest_{s}_id_claws0.png")
    # まとめ
    def agg(key):
        vals = [d[key] for d in list(res["views"].values()) + list(res["crest"].values()) if key in d]
        return vals
    sp = agg("white_lum_spread")
    res["summary"] = {
        "white_lum_spread_min_max": [min(sp), max(sp)] if sp else None,
        "specular_px_white_total": int(sum(agg("specular_px_white"))),
        "specular_px_ai_total": int(sum(agg("specular_px_ai"))),
        "drawn_line_px_total": int(sum(agg("drawn_line_px"))),
        "face_groove_frac_views": {k: d.get("face_groove_frac") for k, d in res["views"].items()},
        "lip_white_frac_painting": res["views"]["painting"].get("lip_white_frac"),
    }
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    json.dump(res, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res["summary"], ensure_ascii=False))
    for v in VIEWS:
        d = res["views"][v]
        print(v, d.get("white_lum_spread"), d.get("specular_px_white"), d.get("specular_px_ai"), d.get("drawn_line_px"), d.get("face_groove_frac"), d.get("lip_white_frac"),
              {k: (t["lit"]["srgb"], t["mid"]["srgb"], t["shadow"]["srgb"]) if t else None for k, t in (d.get("tones") or {}).items()})


if __name__ == "__main__":
    main()
