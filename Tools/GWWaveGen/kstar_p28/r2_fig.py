# -*- coding: utf-8 -*-
"""仕上げ28 第2回（r2）：図を作る（py -3.10、cv2・PIL・numpy）。
  sheets/sheet_before_after_R4_P28R2_1920x1080.png   同じ視点・同じ時刻（t*）の前後の図：左 = R4、右 = P28R2（8 視点）
  sheets/sheet_back_views_1920x1080.png               後ろの 4 視点 × 4 候補（R4・P28R1・P28R2・K* 26R01）
  sheets/sheet_user_failure_1920x1080.png             利用者の失敗の視点 u10〜u13 × 4 候補
  sheets/sheet_std_views_1920x1080.png                標準の 9 視点 × 3 候補（R4・P28R1・P28R2）
  sheets/sheet_turntable_back_1920x1080.png           回り台の後ろ側のコマ（f120〜f220）R4 と P28R2
  sheets/sheet_ablation_1920x1080.png                 試した案（A1〜A6）と P28R2 の後ろ・b区域・原画視点
  figs/fig_sections_1920x1080.png                     断面（灰 = R4、青 = P28R1、赤 = P28R2）
  figs/fig_keepout_rows_1920x1080.png                 原画の空の射線の禁止域（青）と P28R2 の断面（なぜ管の奥と奥の行を動かせないか）
  figs/fig_b_band_1920x1080.png                       b区域の帯：原画の目標（赤 = 上の縁 top_raw、橙 = 下の縁）と候補の像
usage: py -3.10 r2_fig.py <r2 dir>
"""
import os
import sys
import json

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_common as R  # noqa: E402
REPO = R.REPO
for p in (os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.append(p)

B = os.path.join(REPO, "Unity", "Build")
ROWS = {"R4": os.path.join(B, "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz"),
        "P28R1": os.path.join(B, "Polish", "28", "r1_rays", "cand", "kstarP28R1_a45_rows.npz"),
        "P28R2": os.path.join(B, "Polish", "28", "r2", "cand", "kstarP28R2_a45_rows.npz"),
        "Kstar_26R01": os.path.join(B, "ArtFirst", "26修正01", "kstar", "kstar_a45_rows.npz")}
FONT = "C:/Windows/Fonts/arial.ttf"


def font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def tile(path, w, h, label):
    im = cv2.imread(path)
    if im is None:
        im = np.full((h, w, 3), 90, np.uint8)
    ih, iw = im.shape[:2]
    s = min(w / iw, h / ih)
    im = cv2.resize(im, (max(1, int(iw * s)), max(1, int(ih * s))), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), 255, np.uint8)
    y0 = (h - im.shape[0]) // 2; x0 = (w - im.shape[1]) // 2
    out[y0:y0 + im.shape[0], x0:x0 + im.shape[1]] = im
    cv2.rectangle(out, (0, 0), (min(w - 1, 9 * len(label) + 12), 22), (0, 0, 0), -1)
    cv2.putText(out, label, (5, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    return out


def grid(tiles, cols, W=1920, H=1080, title=None):
    rows = (len(tiles) + cols - 1) // cols
    th = 34 if title else 0
    tw, tht = W // cols, (H - th) // rows
    canvas = np.full((H, W, 3), 255, np.uint8)
    if title:
        cv2.putText(canvas, title, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (0, 0, 0), 1, cv2.LINE_AA)
    for k, (p, lab) in enumerate(tiles):
        r, cc = divmod(k, cols)
        canvas[th + r * tht: th + (r + 1) * tht, cc * tw:(cc + 1) * tw] = tile(p, tw, tht, lab)
    return canvas


def sheets(d):
    rd = os.path.join(d, "renders")
    sd = os.path.join(d, "sheets"); os.makedirs(sd, exist_ok=True)
    # 前後の図（R4 → P28R2）
    views = ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight", "b115_back_minus_c",
             "u11_v9zoom_crest_bulge", "u13_v8zoom_b_region", "v1_painting", "v6_top_down"]
    t = []
    for v in views:
        t += [(os.path.join(rd, "R4__%s.png" % v), "R4 before | " + v), (os.path.join(rd, "P28R2__%s.png" % v), "P28R2 after | " + v)]
    cv2.imwrite(os.path.join(sd, "sheet_before_after_R4_P28R2_1920x1080.png"),
                grid(t, 4, title="Polish 28 round 2: same views, t* (final frame K*'), Blender clay. Pairs: left = R4 (before), right = P28R2 (after)."))
    labs = ["R4", "P28R1", "P28R2", "Kstar_26R01"]
    back = ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight", "b115_back_minus_c"]
    t = [(os.path.join(rd, "%s__%s.png" % (l, v)), "%s | %s" % (l, v)) for v in back for l in labs]
    cv2.imwrite(os.path.join(sd, "sheet_back_views_1920x1080.png"),
                grid(t, 4, title="Back views (rows) x candidates (cols): R4 | P28R1 (round 1 best) | P28R2 (round 2) | K* 26R01 (CP1)"))
    user = ["u10_foot_zoom", "u11_v9zoom_crest_bulge", "u12a_v5_back_three_quarter", "u13_v8zoom_b_region"]
    t = [(os.path.join(rd, "%s__%s.png" % (l, v)), "%s | %s" % (l, v)) for v in user for l in labs]
    cv2.imwrite(os.path.join(sd, "sheet_user_failure_1920x1080.png"), grid(t, 4, title="User failure views u10-u13 (rows) x candidates (cols)"))
    std = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
           "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
    t = [(os.path.join(rd, "%s__%s.png" % (l, v)), "%s | %s" % (l, v[:14])) for v in std for l in ("R4", "P28R1", "P28R2")]
    cv2.imwrite(os.path.join(sd, "sheet_std_views_1920x1080.png"), grid(t, 6, title="Standard 9 views: R4 | P28R1 | P28R2 (two views per row)"))
    t = []
    for fs in ((120, 140, 160), (180, 200, 220)):
        for lab in ("R4", "P28R2"):
            for f in fs:
                t.append((os.path.join(rd, "turntable_%s" % lab, "f_%04d.png" % f), "%s turntable f%d (%.1f s)" % (lab, f, f / 30.0)))
    cv2.imwrite(os.path.join(sd, "sheet_turntable_back_1920x1080.png"),
                grid(t, 3, title="Turntable frames facing the back (30 fps, 240 frames): rows 1/3 = R4, rows 2/4 = P28R2 (same frames)"))
    ad = os.path.join(d, "ablation", "renders")
    ab = ["P28R2", "A1", "A2", "A3", "A4", "A5", "A6"]
    av = ["b65_back65_clay", "b90_back_straight", "u13_v8zoom_b_region", "v1_painting"]
    t = [(os.path.join(ad, "%s__%s.png" % (l, v)), "%s | %s" % (l, v)) for v in av for l in ab]
    cv2.imwrite(os.path.join(sd, "sheet_ablation_1920x1080.png"),
                grid(t, 7, title="Ablations: P28R2 | A1 core (tube+back+tail) | A2 no b-lobes | A3 knob softened | A4 crest ramp | A5 crest sharpen | A6 back 56 deg"))


def fig_sections(d):
    from PIL import Image as I
    sys.path.insert(0, os.path.join(d, "work"))
    cs = [-30, -24, -18, -14, -10, -6, -3, -1.5, 0, 2, 4, 6, 8, 10, 11, 12]
    cols, cw, ch = 4, 480, 250
    im = I.new("RGB", (1920, 1080), "white"); dr = ImageDraw.Draw(im)
    xlim, ylim = (-26, 16), (-6, 24)
    sets = []
    for lab, rgb, w in (("R4", (150, 150, 150), 1), ("P28R1", (60, 110, 230), 1), ("P28R2", (220, 30, 30), 2)):
        z = np.load(ROWS[lab]); sets.append((lab, z["c"], z["A"], z["Y"], rgb, w))
    s = min((cw - 16) / (xlim[1] - xlim[0]), (ch - 26) / (ylim[1] - ylim[0]))
    top = 40
    dr.text((10, 8), "Sections (a forward = right, y up), t*: grey = R4, blue = P28R1, red = P28R2. Dots: cols 18 (back foot), 90 (top), 200 (lip tip), 314 (tube corner).", fill=(0, 0, 0), font=font(18))
    for k, cc in enumerate(cs):
        ox, oy = (k % cols) * cw, top + (k // cols) * ch

        def P(a, y):
            return (ox + 8 + (a - xlim[0]) * s, oy + ch - 8 - (y - ylim[0]) * s)
        for g in range(-25, 16, 5):
            dr.line([P(g, ylim[0]), P(g, ylim[1])], fill=(235, 235, 235))
        for g in range(-5, 25, 5):
            dr.line([P(xlim[0], g), P(xlim[1], g)], fill=(235, 235, 235))
        dr.line([P(xlim[0], 0), P(xlim[1], 0)], fill=(160, 160, 255))
        for (lab, c, A, Y, rgb, w) in sets:
            i = int(np.argmin(abs(c - cc)))
            dr.line([P(a, y) for a, y in zip(A[i], Y[i])], fill=rgb, width=w)
            for j in (18, 90, 200, 314):
                x, y = P(A[i, j], Y[i, j]); dr.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=rgb)
        dr.text((ox + 10, oy + 4), "c = %.1f m" % cc, fill=(0, 0, 0), font=font(16))
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    im.save(os.path.join(d, "figs", "fig_sections_1920x1080.png"))


def fig_keepout(d):
    from PIL import Image as I
    c, A, Y = R.load_rows(ROWS["P28R2"])
    c0, A0, Y0 = R.load_rows(ROWS["P28R1"])
    G0 = R.keepout_grids(c, 0, 2, cache=os.path.join(R.OUT, "cache", "keepout_d0.npz"))
    cs = [-10, -6, -3, -1.6, 0.0, 1.6, 4.0, 8.0]
    cols, cw, ch = 4, 480, 500
    canvas = I.new("RGB", (1920, 1080), "white"); dr = ImageDraw.Draw(canvas)
    dr.text((10, 8), "Blue = where rays through the painted sky (incl. the curl opening) cross this row plane: the surface may not enter it. "
                     "Black = P28R1, red = P28R2. Rows c -1.6..+4 are locked by the painted top and the opening.", fill=(0, 0, 0), font=font(16))
    xl, yl = (-22.0, 16.0), (-6.0, 26.0)
    s = min((cw - 10) / (xl[1] - xl[0]), (ch - 40) / (yl[1] - yl[0]))
    for k, cc in enumerate(cs):
        i = int(np.argmin(abs(c - cc)))
        ox, oy = (k % cols) * cw, 36 + (k // cols) * ch
        g = G0[i]
        ia0, ia1 = int((xl[0] - R.GA0) / R.GRES), int((xl[1] - R.GA0) / R.GRES)
        iy0, iy1 = int((yl[0] - R.GY0) / R.GRES), int((yl[1] - R.GY0) / R.GRES)
        sub = g[iy0:iy1, ia0:ia1][::-1]
        img = np.full(sub.shape + (3,), 255, np.uint8); img[sub] = (170, 200, 255)
        tw, th = int((xl[1] - xl[0]) * s), int((yl[1] - yl[0]) * s)
        canvas.paste(I.fromarray(img).resize((tw, th), I.NEAREST), (ox + 5, oy + 20))

        def P(a, y):
            return (ox + 5 + (a - xl[0]) * s, oy + 20 + (yl[1] - y) * s)
        for gy in range(-5, 26, 5):
            dr.line([P(xl[0], gy), P(xl[1], gy)], fill=(225, 225, 225))
        for ga in range(-20, 17, 5):
            dr.line([P(ga, yl[0]), P(ga, yl[1])], fill=(225, 225, 225))
        dr.line([P(a, y) for a, y in zip(A0[i], Y0[i])], fill=(0, 0, 0), width=1)
        dr.line([P(a, y) for a, y in zip(A[i], Y[i])], fill=(220, 30, 30), width=2)
        dr.text((ox + 8, oy + 22), "c = %.1f" % c[i], fill=(0, 0, 0), font=font(16))
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    canvas.save(os.path.join(d, "figs", "fig_keepout_rows_1920x1080.png"))


def fig_band(d):
    import candA_common as C
    import candA4_checks as CK
    V1, tgt, fr = C.painting_frame()
    im = Image.open(os.path.join(REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png")).convert("RGB")
    dr = ImageDraw.Draw(im)
    bt = json.load(open(os.path.join(REPO, "Tools", "GWWaveGen", "kstar3", "candA4_band_targets.json"), encoding="utf-8"))
    dr.line([tuple(p) for p in bt["top_raw"]], fill=(255, 0, 0), width=3)
    dr.line([tuple(p) for p in bt["bottom_raw"]], fill=(255, 140, 0), width=3)
    res = {}
    for lab, rgb in (("R4", (120, 120, 120)), ("P28R1", (0, 90, 255)), ("P28R2", (0, 170, 0))):
        z = np.load(ROWS[lab]); c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
        sil, grown, cov = CK.silhouette_band(c, A, Y, V1, fr)
        bd = CK.band_check(c, A, Y, cov)
        t = [tuple(q) for q in bd["candidate_top_curve"]]
        b = [tuple(q) for q in bd["candidate_bottom_curve"]]
        if len(t) > 1:
            dr.line(t, fill=rgb, width=3)
        if len(b) > 1:
            dr.line(b, fill=rgb, width=1)
        res[lab] = {k: bd[k] for k in ("top_vs_top_raw", "top_vs_top_smooth", "bottom_vs_bottom_raw", "bottom_vs_bottom_smooth")}
    crop = im.crop((170, 330, 800, 685)).resize((1920, 1082))
    crop = crop.crop((0, 0, 1920, 1080))
    dr2 = ImageDraw.Draw(crop)
    f = font(26)
    y = 1080 - 8 * 36 - 10
    for lab, rgb in (("painting target: band top (top_raw)", (255, 0, 0)), ("painting target: claw edge (bottom_raw)", (255, 140, 0)),
                     ("R4", (120, 120, 120)), ("P28R1", (0, 90, 255)), ("P28R2", (0, 170, 0))):
        dr2.rectangle([10, y, 1100, y + 32], fill=(255, 255, 255)); dr2.text((16, y + 2), lab, fill=rgb, font=f); y += 36
    for lab in ("R4", "P28R1", "P28R2"):
        v = res[lab]["top_vs_top_smooth"]; v2 = res[lab]["top_vs_top_raw"]
        dr2.rectangle([10, y, 1600, y + 32], fill=(255, 255, 255))
        dr2.text((16, y + 2), "%s band top vs smooth: median %.1f / p90 %.1f / max %.1f px (%d/46); vs raw: %.1f / %.1f / %.1f" % (
            lab, v["median_px"], v["p90_px"], v["max_px"], v["covered_samples"], v2["median_px"], v2["p90_px"], v2["max_px"]), fill=(0, 0, 0), font=font(22))
        y += 36
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    crop.save(os.path.join(d, "figs", "fig_b_band_1920x1080.png"))
    R.jdump(res, os.path.join(d, "figs", "fig_b_band_values.json"))


if __name__ == "__main__":
    d = sys.argv[1]
    what = sys.argv[2].split(",") if len(sys.argv) > 2 else ["sheets", "sections", "keepout", "band"]
    if "sheets" in what:
        sheets(d)
    if "sections" in what:
        fig_sections(d)
    if "keepout" in what:
        fig_keepout(d)
    if "band" in what:
        fig_band(d)
    print("done")
