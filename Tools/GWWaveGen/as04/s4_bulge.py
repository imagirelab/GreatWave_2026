# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S の 2（Q32・要求書 S8）：利用者の 1 枚目の切り出しの出っ張り（原画視点で唇の左の面の中ほど）が、
主役波 AS02C のどの部分で、内側の面の弧からどれだけ出ているか、なぜ出るかを測る。

- 原画のカメラの射線を、出っ張りの多角形の中で 4 表示画素おきに当て、主役波のすべての交点（層）を近い順に求める。
  1 枚目の層（見えている面）と 2 枚目の層（その奥）の行・列・距離の差を数える。
- 行ごとの断面（a, y）を描き、出っ張りの列と、カメラからの射線の向きを重ねる。
- 「内側の面の弧」：同じ行の内の面（列 200〜314、唇の下〜角）を、原画の内の面が見える行（c −4〜+2）の弧の形で、
  出っ張りの行へなめらかに続けたもの。行ごとに、見えている出っ張りの点の、その弧からの距離（m）を測る。
使い方：py -3.10 -B Tools/GWWaveGen/as04/s4_bulge.py
出力：Unity/Build/Polish/sample04/map/s4_bulge.json、s4_bulge_sections.png
"""
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S  # noqa: E402
import s4_rays as RY  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

FONT = "C:/Windows/Fonts/msgothic.ttc"


def band(j):
    return "背" if j < 90 else ("唇の外（頂〜唇の先）" if j < 200 else ("唇の下〜角（内の面）" if j < 314 else "前の面"))


def main():
    t0 = time.time()
    X0 = S.load_hero()
    hero = S.CC.Hero(X0)
    SX = S.hero_sec(X0)
    cm = S.rows_c()
    cam = S.CC.painting_cam()
    TH = RY.TileHits(cam, hero.V, hero.Tg, tile=16)
    poly = np.array(S.BULGE_DISP, float)
    m = np.zeros((1080, 1920), np.uint8)
    cv2.fillPoly(m, [np.round(poly).astype(np.int32)], 1)
    ys, xs = np.nonzero(m)
    sel = (ys % 4 == 0) & (xs % 4 == 0)
    ys, xs = ys[sel], xs[sel]
    recs = []
    for x, y in zip(xs, ys):
        h = RY.merge_layers(TH.hits(float(x), float(y)))
        if not h:
            continue
        L = []
        for s_, t, u, v in h[:4]:
            r_, c_ = S.U.tri_to_rc(np.array([t]), np.array([u]), np.array([v]), hero.b1 - hero.b0, hero.b0)
            L.append((float(s_), float(r_[0]), float(c_[0])))
        recs.append((x, y, L))
    n = len(recs)
    first_col = np.array([L[0][2] for _, _, L in recs])
    first_row = np.array([L[0][1] for _, _, L in recs])
    has2 = np.array([len(L) > 1 for _, _, L in recs])
    gap = np.array([L[1][0] - L[0][0] if len(L) > 1 else np.nan for _, _, L in recs])
    sec_col = np.array([L[1][2] if len(L) > 1 else np.nan for _, _, L in recs])
    sec_row = np.array([L[1][1] if len(L) > 1 else np.nan for _, _, L in recs])
    nlay = np.array([len(L) for _, _, L in recs])

    def st(v):
        v = v[np.isfinite(v)]
        return None if not len(v) else {k: S.rnd(f(v)) for k, f in (("min", np.min), ("p10", lambda a: np.percentile(a, 10)), ("p50", np.median),
                                                                        ("p90", lambda a: np.percentile(a, 90)), ("max", np.max))}
    bands_first = {}
    for j in first_col:
        bands_first[band(j)] = bands_first.get(band(j), 0) + 1
    bands_second = {}
    for j in sec_col[np.isfinite(sec_col)]:
        bands_second[band(j)] = bands_second.get(band(j), 0) + 1
    res = {"schema": "GreatWave.ArtSample04.study_bulge/1", "rays": int(n),
           "layers_per_ray": {str(k): int((nlay == k).sum()) for k in range(1, 6)},
           "first_layer": {"row": st(first_row), "c_m": st(np.interp(first_row, np.arange(len(cm)), cm)), "col": st(first_col),
                           "col_band_count": bands_first},
           "second_layer": {"row": st(sec_row), "c_m": st(np.interp(sec_row[np.isfinite(sec_row)], np.arange(len(cm)), cm)), "col": st(sec_col),
                            "col_band_count": bands_second, "gap_along_ray_m": st(gap)}}

    # ---------------------------------------------------------------- 内側の面の弧からの出（行ごと）
    # 見えている出っ張りの点（1 枚目の層の (r, 列)）。行ごとに、その行の内の面（列 200..314）の点の列と、
    # 出っ張りの点（唇の外の列）の位置を (a, y) で比べる。弧：内の面の点列を、頂（列 90）の下で巻きの中心を囲む円に当てる。
    rows_b = np.unique(np.round(first_row).astype(int))
    per_row = []
    for i in rows_b:
        a = SX[i, :, 0]; y = SX[i, :, 1]
        cols_vis = first_col[np.round(first_row).astype(int) == i]
        jv = np.unique(np.round(cols_vis).astype(int))
        # 内の面の弧：唇の下 200..300 の点に円を当てる（最小二乗）
        jj = np.arange(205, 300)
        A_ = np.c_[2 * a[jj], 2 * y[jj], np.ones(len(jj))]
        b_ = a[jj] ** 2 + y[jj] ** 2
        sol, *_ = np.linalg.lstsq(A_, b_, rcond=None)
        ca, cy = sol[0], sol[1]
        rad = np.sqrt(sol[2] + ca ** 2 + cy ** 2)
        fit_res = np.abs(np.hypot(a[jj] - ca, y[jj] - cy) - rad)
        dv = np.hypot(a[jv] - ca, y[jv] - cy) - rad      # + は円の外（巻きの中心から遠い = 内の面の弧より外へ出る）
        per_row.append({"row": int(i), "c_m": S.rnd(cm[i]), "visible_cols": [int(jv.min()), int(jv.max())],
                        "inner_arc_center_a_y": S.rnd([ca, cy]), "inner_arc_radius_m": S.rnd(rad), "inner_arc_fit_rms_m": S.rnd(np.sqrt((fit_res ** 2).mean())),
                        "bulge_offset_from_inner_arc_m": {"p50": S.rnd(np.median(dv)), "max": S.rnd(dv.max()), "min": S.rnd(dv.min())},
                        "lip_tip_a_y": S.rnd([a[200], y[200]]), "crest_a_y": S.rnd([a[90], y[90]])})
    res["per_row_inner_arc"] = per_row
    res["note_ja"] = ("1 枚目の層は原画視点で見えている面。2 枚目の層はその奥の面。gap_along_ray_m は射線の上の 1 枚目と 2 枚目の距離。"
                      "inner_arc は、その行の唇の下〜角（列 205〜299）の点に当てた円（巻きの内の面の弧）。bulge_offset は見えている出っ張りの点の、その円からの距離（+ は円の外）。")
    S.jdump(S.OUT + "/s4_bulge.json", res)
    print("rays", n, "first", res["first_layer"], "second", res["second_layer"], flush=True)
    for p in per_row[::3]:
        print(p["row"], p["c_m"], p["visible_cols"], p["inner_arc_radius_m"], p["bulge_offset_from_inner_arc_m"])
    np.save(S.TMP + "/s4_bulge_hits.npy", np.array([(x, y, L[0][1], L[0][2], (L[1][1] if len(L) > 1 else -1), (L[1][2] if len(L) > 1 else -1),
                                                      L[0][0], (L[1][0] if len(L) > 1 else -1)) for x, y, L in recs]))
    sections(SX, cm, first_row, first_col, sec_row, sec_col)
    print("done", round(time.time() - t0, 1))


def sections(SX, cm, fr, fc, sr, sc):
    """行ごとの断面（a, y）。藍：唇の外の列、緑：唇の下〜角、灰：背と前の面。出っ張りで見えている列は赤、その奥の 2 枚目は橙。"""
    cam_ay = (45.605789147052896, 3.0)
    rows = [101, 107, 113, 118, 122, 126, 130, 134, 140, 150, 164]
    W, H = 2400, 1500
    img = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(FONT, 26)
    fs = ImageFont.truetype(FONT, 20)
    d.text((20, 12), "出っ張り（S8）の行の断面（a = 進行方向・右が前、y = 高さ）。赤 = 原画視点で出っ張りとして見えている点、橙 = その奥の面（射線の 2 枚目）", font=f, fill=(20, 20, 20))
    d.text((20, 46), "藍 = 唇の外（頂〜唇の先、列 90〜200）、緑 = 唇の下〜角（内の面、列 200〜314）、灰 = 背・前の面。細い線 = 原画のカメラからの射線の向き（断面へ写した向き）", font=fs, fill=(60, 60, 60))
    ncol = 4
    pw, ph = W // ncol, (H - 90) // 3
    sc_ = 17.0
    fri = np.round(fr).astype(int)
    sri = np.round(np.nan_to_num(sr, nan=-9)).astype(int)
    for k, i in enumerate(rows):
        ox, oy = (k % ncol) * pw, 90 + (k // ncol) * ph
        d.rectangle([ox + 4, oy + 4, ox + pw - 4, oy + ph - 4], outline=(190, 190, 190))

        def P(a, y):
            return (ox + pw * 0.42 + a * sc_, oy + ph - 40 - y * sc_)
        d.line([P(-20, 0), P(18, 0)], fill=(170, 170, 170), width=1)
        a, y = SX[i, :, 0], SX[i, :, 1]
        for j0, j1, col in ((18, 90, (150, 150, 150)), (90, 200, (40, 60, 150)), (200, 314, (40, 150, 60)), (314, 394, (150, 150, 150))):
            pts = [P(a[j], y[j]) for j in range(j0, j1 + 1)]
            d.line(pts, fill=col, width=3)
        jv = np.unique(np.round(fc[fri == i]).astype(int))
        for j in jv:
            x_, y_ = P(a[j], y[j]); d.ellipse([x_ - 4, y_ - 4, x_ + 4, y_ + 4], fill=(220, 30, 30))
            # 射線の向き（カメラ → 点）
            va, vy = a[j] - cam_ay[0], y[j] - cam_ay[1]
            nrm = np.hypot(va, vy)
            x2, y2 = P(a[j] - va / nrm * 6, y[j] - vy / nrm * 6)
            if j == jv[len(jv) // 2]:
                d.line([P(a[j], y[j]), (x2, y2)], fill=(120, 120, 120), width=1)
        js = np.unique(np.round(sc[(fri == i) & (sri == i)]).astype(int)) if np.any((fri == i) & (sri == i)) else []
        for j in js:
            x_, y_ = P(a[j], y[j]); d.ellipse([x_ - 3, y_ - 3, x_ + 3, y_ + 3], fill=(240, 150, 30))
        d.text((ox + 12, oy + 10), "行 %d　c = %.1f m　頂 %.1f m" % (i, cm[i], y[18:200].max()), font=f, fill=(20, 20, 20))
        for jl, nm in ((90, "頂"), (200, "唇の先"), (314, "角")):
            x_, y_ = P(a[jl], y[jl]); d.text((x_ + 4, y_ - 22), nm, font=fs, fill=(80, 80, 80))
    img.save(S.OUT + "/s4_bulge_sections.png")


if __name__ == "__main__":
    os.makedirs(S.TMP, exist_ok=True)
    main()
