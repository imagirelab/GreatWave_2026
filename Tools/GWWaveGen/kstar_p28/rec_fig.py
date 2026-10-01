# -*- coding: utf-8 -*-
"""仕上げ28 の回復（rec）：粘土（Blender）と numpy の図を作る（py -3.10、cv2・PIL・numpy）。
  sheets/sheet_rec_back_views_1920x1080.png     後ろの 4 視点（行）× R4｜P28R2｜P28R2rec（列）。t*、Blender の粘土
  sheets/sheet_rec_front_views_1920x1080.png    原画視点・b区域の拡大・足元の拡大・座席（行）× 同じ 3 つ
  sheets/sheet_rec_turntable_back_1920x1080.png 回り台の後ろ側のコマ f120〜f220：R4｜P28R2｜P28R2rec
  figs/fig_rec_sections_1920x1080.png           断面（灰 = R4、赤 = P28R2、青 = P28R2rec）。管を前へ出した行と、戻した行
  figs/fig_rec_painting_numpy_1920x1080.png     原画視点の numpy の読み：新しい線（赤、R4 の設計38 の印のまま）と、段階9 で船・手前の海が見える画素で
                                                主役波が 1 m 以上手前に来た画素（橙）。R4｜P28R2｜P28R2rec
入力：R4・P28R2 の粘土は r2/renders（第2回で描いたもの）、P28R2rec は rec/renders（rays_bl.py、同じ視点の一覧）。
usage: py -3.10 rec_fig.py <rec dir>
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rec_common as RC  # noqa: E402
import r2_fig as F2  # noqa: E402

REPO = RC.REPO
R2 = os.path.join(RC.P28, "r2")
LABS = [("R4", os.path.join(R2, "renders"), "R4 (stage 9)"), ("P28R2", os.path.join(R2, "renders"), "P28R2 (round 2)"),
        ("P28R2rec", None, "P28R2rec (recovery, adopted)")]
ROWS = {"R4": RC.ROWS["R4"], "P28R2": RC.ROWS["P28R2"],
        "P28R2rec": os.path.join(RC.P28, "kstar_p28rec", "kstarP28R2rec_a45_rows.npz")}


def sheets(d):
    rd = os.path.join(d, "renders")
    sd = os.path.join(d, "sheets"); os.makedirs(sd, exist_ok=True)
    labs = [(l, p or rd, t) for l, p, t in LABS]
    back = ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight", "b115_back_minus_c"]
    t = [(os.path.join(p, "%s__%s.png" % (l, v)), "%s | %s" % (tt, v)) for v in back for l, p, tt in labs]
    cv2.imwrite(os.path.join(sd, "sheet_rec_back_views_1920x1080.png"),
                F2.grid(t, 3, title="Polish 28 recovery: back views (rows) x R4 | P28R2 | P28R2rec (cols). t*, Blender clay. The dome/hood from behind is unchanged."))
    front = ["v1_painting", "u13_v8zoom_b_region", "u10_foot_zoom", "v2_seat"]
    t = [(os.path.join(p, "%s__%s.png" % (l, v)), "%s | %s" % (tt, v)) for v in front for l, p, tt in labs]
    cv2.imwrite(os.path.join(sd, "sheet_rec_front_views_1920x1080.png"),
                F2.grid(t, 3, title="Polish 28 recovery: painting view, b region, foot, seat (rows) x R4 | P28R2 | P28R2rec (cols). t*, Blender clay."))
    t = []
    for fs in ((120, 160, 200), (140, 180, 220)):
        for l, p, tt in labs:
            for f in fs:
                t.append((os.path.join(p, "turntable_%s" % l, "f_%04d.png" % f), "%s turntable f%d" % (tt, f)))
    cv2.imwrite(os.path.join(sd, "sheet_rec_turntable_back_1920x1080.png"),
                F2.grid(t, 3, title="Turntable frames facing the back (same frames): rows R4 | P28R2 | P28R2rec, twice"))


def fig_sections(d):
    cs = [-20, -17, -15, -13, -11, -9, -7, -5, -4, -3, -2, -1, 0, 2, -30, -24]
    cols, cw, ch = 4, 480, 250
    im = Image.new("RGB", (1920, 1080), "white"); dr = ImageDraw.Draw(im)
    xlim, ylim = (-26, 16), (-6, 24)
    sets = []
    for lab, rgb, w in (("R4", (150, 150, 150), 1), ("P28R2", (220, 30, 30), 2), ("P28R2rec", (30, 90, 230), 2)):
        z = np.load(ROWS[lab]); sets.append((lab, z["c"], z["A"], z["Y"], rgb, w))
    s = min((cw - 16) / (xlim[1] - xlim[0]), (ch - 26) / (ylim[1] - ylim[0]))
    top = 40
    dr.text((10, 8), "Sections at t* (a forward = right, y up): grey = R4, red = P28R2 (tube moved forward up to 6 m), blue = P28R2rec (tube kept where the painting view sees boats/near sea). Dots: cols 18, 90, 200, 314.",
            fill=(0, 0, 0), font=F2.font(16))
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
        dr.text((ox + 10, oy + 4), "c = %.1f m" % cc, fill=(0, 0, 0), font=F2.font(16))
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    im.save(os.path.join(d, "figs", "fig_rec_sections_1920x1080.png"))


def fig_painting_numpy(d):
    import rec_score as RS
    S9 = RC.stage9_classes(2)
    panes = []
    for lab in ("R4", "P28R2", "P28R2rec"):
        r, o = RS.score(ROWS[lab], 2, lab)
        c, A, Y = RC.load_rows(ROWS[lab])
        z, _ = RC.zbuf(c, A, Y, 2)
        img = np.full(z.shape + (3,), 245, np.uint8)
        img[S9["sky"]] = (240, 228, 205)
        img[np.isfinite(z)] = (150, 110, 60)
        prot = S9["boat_left"] | S9["boat_mid"] | S9["boat_fg"]
        img[prot & ~np.isfinite(z)] = (120, 180, 230)
        ln = cv2.dilate(o["ln"].astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        img[ln] = (40, 40, 40)
        cl = o["closer"] & (np.abs(z - RS.ref_state(2)[2]) > 1.0)
        img[cl] = (0, 140, 255)
        new = cv2.dilate(o["new"].astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        img[new] = (0, 0, 230)
        img = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
        cv2.putText(img, "%s: new lines %d px, surface >=1 m closer over boats/near sea %d px (ss=2)" % (lab, r["new_line_px"], r["protected_closer_px_1m"]),
                    (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        panes.append(img)
    leg = np.full((540, 960, 3), 255, np.uint8)
    for k, (t, col) in enumerate((("brown = hero surface (numpy z-buffer, t*)", (150, 110, 60)),
                                  ("dark = outline shell lines (design 38 mask of R4)", (40, 40, 40)),
                                  ("red = lines new vs R4 (dilated)", (0, 0, 230)),
                                  ("orange = over stage-9 boats/near sea, surface >= 1 m closer than R4", (0, 140, 255)),
                                  ("light blue = boats not covered", (120, 180, 230)))):
        cv2.rectangle(leg, (20, 40 + 60 * k), (60, 70 + 60 * k), col, -1)
        cv2.putText(leg, t, (75, 62 + 60 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    top = np.hstack(panes[:2]); bot = np.hstack([panes[2], leg])
    cv2.imwrite(os.path.join(d, "figs", "fig_rec_painting_numpy_1920x1080.png"), np.vstack([top, bot]))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = sys.argv[1]
    what = sys.argv[2:] or ["sheets", "sections", "numpy"]
    if "sections" in what:
        fig_sections(d)
    if "numpy" in what:
        fig_painting_numpy(d)
    if "sheets" in what:
        sheets(d)
    print("REC_FIG_DONE")
