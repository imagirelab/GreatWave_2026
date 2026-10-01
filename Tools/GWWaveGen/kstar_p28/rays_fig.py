# -*- coding: utf-8 -*-
"""仕上げ28 第1回（射線の案）：図を作る（py -3.10、cv2 だけ）。
  fig_spine_rays_1920x1080.png   背骨（各行の頂の点、列 90）の上から見た位置 a(c)・後ろから見た高さ H(c)、
                                 原画の左の輪郭の射線の円錐の法線から決まる「射線に接する点で面が持つべき横の傾き」
  sheet_vs_R4_1920x1080.png      同じ視点の前後の図（左 = R4、右 = 第1回の候補）8 視点
usage: py -3.10 rays_fig.py <r1_rays dir>
"""
import os
import sys
import json
import math

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import rays_common as RC  # noqa: E402
import rays_build as RB  # noqa: E402
import rays_plot as RP  # noqa: E402
KC = RC.KC


def cone_slopes():
    """原画の外輪郭 78・130・131 の各点の射線と、隣の射線で張る円錐の法線 N（断面座標 a, y, c）。
    射線に接する点では面の法線 = N なので、面の横（c 方向、a 一定）の傾き ∂y/∂c = −N_c/N_y と、
    断面の傾き（a 方向）∂y/∂a = −N_a/N_y は、奥行きの選び方に関係なく決まる。"""
    xs, ys = RB.truth_outline()
    P = np.stack([xs, ys], 1)
    D = RB.rays_through(P)
    from scipy.ndimage import gaussian_filter1d
    Ds = gaussian_filter1d(D, 8, axis=0); Ds /= np.linalg.norm(Ds, axis=1, keepdims=True)
    tg = np.gradient(Ds, axis=0)
    N = np.cross(Ds, tg); N /= np.linalg.norm(N, axis=1, keepdims=True)
    Ns = np.stack([N @ KC.T, N[:, 1], N @ KC.E], 1)
    Ns *= np.sign(Ns[:, 1:2])
    return xs, -Ns[:, 2] / Ns[:, 1], -Ns[:, 0] / Ns[:, 1]


def spine_of(rows):
    z = np.load(rows)
    c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    return c, A[:, 90], Y[:, 90], Y.max(1)


def fig_spine(out_dir, cands):
    W, H = 1920, 1080
    img = np.full((H, W, 3), 255, np.uint8)
    p1 = RP.Plot(960, 520, (-40, 15), (-16, 4), "top view of the crest spine a(c) at col 90 (m); T up = forward", gx=5, gy=2)
    p2 = RP.Plot(960, 520, (-40, 15), (0, 24), "seen from behind: crest height H(c) = y at col 90 (m)", gx=5, gy=2)
    for k, (lab, rows) in enumerate(cands):
        c, a, y, hmax = spine_of(rows)
        p1.line(c, a, k, lab, 2)
        p2.line(c, y, k, lab, 2)
    # 左の輪郭の射線が a = 0 の面を通る高さ（頂を a = 0 に置いた時の頂の高さの上限）
    xs, ys = RB.truth_outline()
    D = RB.rays_through(np.stack([xs, ys], 1))
    C0 = KC.sec(KC.CAM_POS_U)[0]
    Ds = np.stack([D @ KC.T, D[:, 1], D @ KC.E], 1)
    t = (0.0 - C0[0]) / Ds[:, 0]
    S = C0 + t[:, None] * Ds
    p2.line(S[:, 2], S[:, 1], 10, "rays of 78/130/131 at a=0", 1, col=(0, 0, 0))
    img[0:520, 0:960] = p1.finish()
    img[0:520, 960:1920] = p2.finish()
    xs, lat, sec_s = cone_slopes()
    p3 = RP.Plot(960, 540, (150, 770), (-0.6, 1.8), "slopes the surface must have where it touches the ray (painting x px)", gx=50, gy=0.2)
    p3.line(xs, lat, 3, "lateral dy/dc (fixed by the painting)", 2)
    p3.line(xs, sec_s, 0, "section dy/da at the rim", 2)
    p3.line([150, 770], [0, 0], 7, None, 1)
    for xb in (357.1, 487.1):
        p3.line([xb, xb], [-0.6, 1.8], 7, None, 1)
    cv2.putText(p3.img, "78", tuple(p3.px(240, 1.6).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    cv2.putText(p3.img, "130", tuple(p3.px(400, 1.6).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    cv2.putText(p3.img, "131", tuple(p3.px(600, 1.6).astype(int)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
    img[540:1080, 0:960] = p3.finish()
    # 右下：短い説明（英語、cv2 の字）
    txt = ["Polish 28 round 1 (RAYS): depth of the left-outline rims re-assigned along the painting rays.",
           "The cone normal of the ray bundle fixes the surface slope at every rim, whatever the depth:",
           "lateral dy/dc = %.2f .. %.2f on outline 130 (x 357..487), i.e. a %.0f-%.0f deg flank." % (
               float(np.percentile(lat[(xs > 357) & (xs < 487)], 5)), float(np.percentile(lat[(xs > 357) & (xs < 487)], 95)),
               math.degrees(math.atan(float(np.percentile(lat[(xs > 357) & (xs < 487)], 5)))),
               math.degrees(math.atan(float(np.percentile(lat[(xs > 357) & (xs < 487)], 95))))),
           "Moving a rim deeper along its ray moves it back (-a) about 1.7 m per 1 m of c and up 0.35-0.47 m.",
           "So depth can only trade the lateral rise for a crest swept forward/back in top view.",
           "The search (Nelder-Mead on 6 depth knots, objective: back-view monotone spine, 3-D and",
           "top-view curvature, fast R6 dome measure, outline) kept the rims within 1 m of R4",
           "when the top view is penalised; the free optimum (A4) sweeps the shoulder 2.5 m forward",
           "and breaks the b region (ridge median 22 px). The painted 78 dip at x~230 leaves",
           "a 0.2 m notch in H(c) at c~-16 that no depth assignment at a~0 removes."]
    y0 = 580
    for k, s in enumerate(txt):
        cv2.putText(img, s, (975, y0 + 26 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(os.path.join(out_dir, "fig_spine_rays_1920x1080.png"), img)


def sheet_vs_r4(out_dir, rd, lab_after="P28R1", lab_before="R4"):
    views = ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight", "b115_back_minus_c",
             "u11_v9zoom_crest_bulge", "u13_v8zoom_b_region", "v1_painting", "v6_top_down"]
    W, H = 1920, 1080
    img = np.full((H, W, 3), 255, np.uint8)
    head = 24
    cw, ch = 480, 264
    for i, v in enumerate(views):
        col, row = i % 2, i // 2
        x0 = col * 960; y0 = head + row * ch
        for k, lab in enumerate((lab_before, lab_after)):
            im = cv2.imread(os.path.join(rd, "%s__%s.png" % (lab, v)))
            if im is None:
                continue
            s = min(cw / im.shape[1], ch / im.shape[0])
            im = cv2.resize(im, (int(im.shape[1] * s), int(im.shape[0] * s)), interpolation=cv2.INTER_AREA)
            xx = x0 + k * cw + (cw - im.shape[1]) // 2; yy = y0 + (ch - im.shape[0]) // 2
            img[yy:yy + im.shape[0], xx:xx + im.shape[1]] = im
            cv2.putText(img, "%s  %s" % (lab, v), (x0 + k * cw + 6, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 200), 1, cv2.LINE_AA)
    cv2.putText(img, "Polish 28 round 1 (RAYS): left = %s (before), right = %s (after). Same views, t* (final frame), Blender clay." % (lab_before, lab_after),
                (8, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(os.path.join(out_dir, "sheet_vs_%s_1920x1080.png" % lab_before), img)


def main():
    d = sys.argv[1]
    cands = [("R4", RC.R4_ROWS), ("P28R1", os.path.join(d, "cand", "kstarP28R1_a45_rows.npz")),
             ("A2_sweep", os.path.join(d, "ablation", "A2_sweep", "kstar_A2_sweep_rows.npz")),
             ("A4_search_free", os.path.join(d, "ablation", "A4_search_free", "kstar_A4_search_free_rows.npz")),
             ("A5_crest_ramp", os.path.join(d, "ablation", "A5_crest_ramp", "kstar_A5_crest_ramp_rows.npz")),
             ("Kstar_26R01", os.path.join(RC.REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45_rows.npz"))]
    fig_spine(os.path.join(d, "figs"), cands)
    sheet_vs_r4(os.path.join(d, "figs"), os.path.join(d, "renders"))
    sheet_vs_r4(os.path.join(d, "figs"), os.path.join(d, "renders"), lab_after="A5_crest_ramp", lab_before="R4")
    os.replace(os.path.join(d, "figs", "sheet_vs_R4_1920x1080.png"), os.path.join(d, "figs", "sheet_A5_crest_ramp_vs_R4_1920x1080.png"))
    sheet_vs_r4(os.path.join(d, "figs"), os.path.join(d, "renders"))
    print("ok")


if __name__ == "__main__":
    os.makedirs(os.path.join(sys.argv[1], "figs"), exist_ok=True)
    main()
