# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S3：見本02 の描画（as03_s3_render.sh の出力）を視点ごとに数える（読み取りのみ。写真・参照モデルは読まない）。

視点ごと（原画視点・座席・座席から波・左右の側面・後ろ 65°・真上・波頭の回り台 8 方位）に、
  主役波の画素（主役波の印 hero_claws0 のアルファ 128）、色区（id_claws0：白・淡い水色・藍中・藍濃）、波頭の帯（列 80〜140＝頂 j_top 90 の前後）の白の割合、
  爪の画素（id_claws1 と id_claws0 の差）と、その塊の数・大きさ、
  空を地にした輪郭の上の縁の出っ張り（指）の数（波頭の回り台だけ。爪あり）、
  色の描画の明るさの広がり（白・藍濃の色区の中の p5・p50・p95）、白の基の色より明るい画素（艶の光）の数、
  縁の線の色の画素（白の縁の線 (71,80,95)、爪の縁の線 (31,60,94)）
を数える。
使い方：py -3.10 -B Tools/GWWaveGen/as03/as03_s3_measure.py <描画のフォルダー（views・crest・diag を持つ）> [<波頭の回り台のフォルダー>] <出力 json>
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.signal import find_peaks

VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
CLS = {"white": (255, 0, 0), "mizuiro": (0, 255, 0), "aimid": (0, 0, 255), "aidark": (255, 255, 0)}
SKY = (0, 255, 255)


def rgba(p):
    return np.asarray(Image.open(p).convert("RGBA"))


def lum(a):
    a = a[..., :3].astype(float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def eq(a, c):
    return (a[..., 0] == c[0]) & (a[..., 1] == c[1]) & (a[..., 2] == c[2])


def near(a, c, tol):
    d = np.abs(a[..., :3].astype(int) - np.array(c)[None, None, :]).max(-1)
    return d <= tol


def one(col_png, hero_png, id0_png, id1_png, crest_view):
    col = rgba(col_png)
    hero = rgba(hero_png)
    id0 = rgba(id0_png)
    id1 = rgba(id1_png)
    hm = hero[..., 3] == 128
    hrow = hero[..., 0].astype(int)
    hcol = hero[..., 1].astype(int) + 256 * hero[..., 2].astype(int)
    out = {"hero_px": int(hm.sum())}
    if hm.sum() == 0:
        return out
    cls = {k: eq(id0, v) & hm for k, v in CLS.items()}
    out["hero_class_frac"] = {k: round(float(m.sum()) / float(hm.sum()), 4) for k, m in cls.items()}
    band = hm & (hcol >= 80) & (hcol <= 140)
    out["crest_band_px"] = int(band.sum())
    if band.sum() > 0:
        out["crest_band_white_frac"] = round(float((cls["white"] & band).sum()) / float(band.sum()), 4)
    # 爪の画素：爪ありと爪なしの ID の差
    cm = (np.abs(id1[..., :3].astype(int) - id0[..., :3].astype(int)).max(-1) > 0)
    out["claw_px"] = int(cm.sum())
    lab, n = ndimage.label(cm, structure=np.ones((3, 3), int))
    if n:
        sz = np.bincount(lab.ravel())[1:]
        sz = sz[sz >= 4]
        out["claw_blobs"] = int(len(sz))
        if len(sz):
            out["claw_blob_px_p50_p90_max"] = [int(np.percentile(sz, 50)), int(np.percentile(sz, 90)), int(sz.max())]
    # 明るさの広がり（色区の境から 2 画素の内側）
    L = lum(col)
    for k in ("white", "aidark"):
        m = ndimage.binary_erosion(cls[k], iterations=2)
        if m.sum() > 50:
            v = L[m]
            out["lum_%s_p5_p50_p95" % k] = [round(float(np.percentile(v, q)), 1) for q in (5, 50, 95)]
    # 艶の光：白の基の色（248,243,223 の明るさ ≈ 243）より明るい画素
    wb = 0.2126 * 248 + 0.7152 * 243 + 0.0722 * 223
    out["specular_px"] = int(((L > wb + 6) & hm).sum())
    # 縁の線の色
    out["edge_line_px"] = int((near(col, (71, 80, 95), 14) & hm).sum())
    out["claw_line_px"] = int(near(col, (31, 60, 94), 10).sum())
    # 波頭の回り台：空を地にした上の縁の出っ張り
    if crest_view:
        fg = ~eq(id1, SKY)
        H, W = fg.shape
        top = np.full(W, H, float)
        has = fg.any(0)
        top[has] = np.argmax(fg[:, has], axis=0)
        prof = -top  # 上ほど大きい
        valid = has & (top > 2)
        pv = np.where(valid, prof, np.nan)
        x = np.where(valid)[0]
        if len(x) > 20:
            s = np.interp(np.arange(W), x, pv[x])
            pk, pr = find_peaks(s, prominence=0.005 * H, width=(None, 80))
            out["silhouette_protrusions"] = int(len(pk))
            out["silhouette_prominence_px_max"] = round(float(pr["prominences"].max()), 1) if len(pk) else 0.0
            # 輪郭の上の縁の滑らかさ：2 階差分の絶対値の p95（画素）
            out["silhouette_d2_p95_px"] = round(float(np.percentile(np.abs(np.diff(s[x.min():x.max()], 2)), 95)), 2)
    return out


def main():
    a = sys.argv[1:]
    rdir = a[0]
    cdir = a[1] if len(a) == 3 else a[0]
    outp = a[-1]
    res = {"render_dir": rdir.replace("\\", "/"), "crest_dir": cdir.replace("\\", "/"), "views": {}, "crest": {}}
    for v in VIEWS:
        res["views"][v] = one(f"{rdir}/views/{v}_t120_claws.png", f"{rdir}/diag/{v}_t120_hero_claws0.png",
                              f"{rdir}/diag/{v}_t120_id_claws0.png", f"{rdir}/diag/{v}_t120_id_claws1.png", False)
    for az in range(0, 360, 45):
        s = "t120_az%03d" % az
        res["crest"]["az%03d" % az] = one(f"{cdir}/crest/{s}_claws.png", f"{cdir}/diag/crest_{s}_hero_claws0.png",
                                          f"{cdir}/diag/crest_{s}_id_claws0.png", f"{cdir}/diag/crest_{s}_id_claws1.png", True)
    json.dump(res, open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for k in ("views", "crest"):
        for v, d in res[k].items():
            print(k, v, json.dumps(d, ensure_ascii=False))


if __name__ == "__main__":
    main()
