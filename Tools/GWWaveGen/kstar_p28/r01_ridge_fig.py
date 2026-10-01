# -*- coding: utf-8 -*-
"""仕上げ28修正01 の変種 RIDGE：図と動画を作る（py -3.10、cv2・PIL・numpy、ffmpeg）。出力は <ridge dir>/sheets・figs・videos。
  sheets/sheet_ridge_back_views_1920x1080.png       後ろ 65°・その拡大・真後ろ・c− 側（行）× P28R2rec｜A5｜RIDGE（列）。t*、Blender の粘土
  sheets/sheet_ridge_std_views_{1,2,3}_1920x1080.png 標準の 9 視点（3 枚に 3 視点ずつ。行）× P28R2rec｜RIDGE（列）
  sheets/sheet_ridge_user_views_1920x1080.png       利用者の失敗の視点 u10〜u13（行）× P28R2rec｜RIDGE
  sheets/sheet_ridge_turntable_1920x1080.png        回り台の 12 コマ：P28R2rec と RIDGE を上下に交互
  figs/fig_ridge_profile_1920x1080.png              立面の頂 H(c)（列 90）と平面の頂 a(c)、上げの上限、目標の稜、後ろから見た溝の深さ（高さごと）
  figs/fig_ridge_sections_1920x1080.png             断面（灰 = P28R2rec、青 = RIDGE、水色 = 原画の空の射線の禁止域）
  figs/fig_ridge_painting_numpy_1920x1080.png       原画視点の numpy の読み（新しい線・船の上で手前に来た面）P28R2rec｜RIDGE
  figs/fig_ridge_crease_1920x1080.png               背の c 方向の曲がり |d²a/dc²|（暗い = 縦の襞・溝）P28R2rec｜A5｜RIDGE
  videos/ridge_turntable_P28R2rec_vs_RIDGE.mp4       回り台の動画を左右に並べたもの（5 MB 以下）
usage: py -3.10 r01_ridge_fig.py <ridge dir> [sheets profile sections numpy crease video]
"""
import os
import sys
import json
import subprocess

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r01_ridge_common as RR  # noqa: E402
R2, RCm = RR.redirect_caches()
import r2_fig as F2  # noqa: E402

A5R = os.path.join(RR.P28, "r1_rays", "renders")


def rows_of(d):
    return {"P28R2rec": RR.BASE_ROWS, "A5": RR.ROWS["A5"], "RIDGE": os.path.join(d, "cand", "kstarP28R01RG_a45_rows.npz")}


def sheets(d):
    rd = os.path.join(d, "renders"); sd = os.path.join(d, "sheets"); os.makedirs(sd, exist_ok=True)
    back = ["b65_back65_clay", "b65z_back65_zoom", "b90_back_straight", "b115_back_minus_c"]
    labs = [("P28R2rec", rd, "P28R2rec (adopted, Polish 28)"), ("A5", rd, "RAYS A5 (round 1)"), ("RG", rd, "RIDGE (this variant)")]
    t = [(os.path.join(p, "%s__%s.png" % (l, v)), "%s | %s" % (tt, v)) for v in back for l, p, tt in labs]
    cv2.imwrite(os.path.join(sd, "sheet_ridge_back_views_1920x1080.png"),
                F2.grid(t, 3, title="Polish 28 fix 01 RIDGE: back views (rows) x P28R2rec | A5 | RIDGE (cols). t*, Blender clay (shape only)."))
    std = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
           "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
    for k in range(3):
        vv = std[3 * k:3 * k + 3]
        t = [(os.path.join(rd, "%s__%s.png" % (l, v)), "%s | %s" % (tt, v)) for v in vv for l, tt in (("P28R2rec", "P28R2rec"), ("RG", "RIDGE"))]
        cv2.imwrite(os.path.join(sd, "sheet_ridge_std_views_%d_1920x1080.png" % (k + 1)),
                    F2.grid(t, 2, title="Polish 28 fix 01 RIDGE: standard views %d-%d (rows) x P28R2rec | RIDGE (cols). t*, Blender clay." % (3 * k + 1, 3 * k + 3)))
    usr = ["u10_foot_zoom", "u11_v9zoom_crest_bulge", "u12a_v5_back_three_quarter", "u13_v8zoom_b_region"]
    t = [(os.path.join(rd, "%s__%s.png" % (l, v)), "%s | %s" % (tt, v)) for v in usr for l, tt in (("P28R2rec", "P28R2rec"), ("RG", "RIDGE"))]
    cv2.imwrite(os.path.join(sd, "sheet_ridge_user_views_1920x1080.png"),
                F2.grid(t, 2, title="Polish 28 fix 01 RIDGE: user failure views u10-u13 (rows) x P28R2rec | RIDGE (cols)."))
    fr = sorted(f for f in os.listdir(os.path.join(rd, "turntable_RG")) if f.endswith(".png"))
    t = []
    for half in (fr[:6], fr[6:12]):
        for l, tt in (("P28R2rec", "P28R2rec"), ("RG", "RIDGE")):
            for f in half:
                t.append((os.path.join(rd, "turntable_%s" % l, f), "%s %s" % (tt, f[:-4])))
    cv2.imwrite(os.path.join(sd, "sheet_ridge_turntable_1920x1080.png"),
                F2.grid(t, 6, title="Polish 28 fix 01 RIDGE: turntable (12 frames, 30 deg apart). Rows 1/3 = P28R2rec, rows 2/4 = RIDGE. Back side = frames 120-200."))


def plot_frame(dr, box, xr, yr, xt, yt, title):
    x0, y0, x1, y1 = box
    dr.rectangle(box, outline=(0, 0, 0))
    def P(x, y):
        y = min(max(y, yr[0]), yr[1]); x = min(max(x, xr[0]), xr[1])      # 枠の外は枠の縁に止める
        return (x0 + (x - xr[0]) / (xr[1] - xr[0]) * (x1 - x0), y1 - (y - yr[0]) / (yr[1] - yr[0]) * (y1 - y0))
    for g in xt:
        dr.line([P(g, yr[0]), P(g, yr[1])], fill=(230, 230, 230)); dr.text((P(g, yr[0])[0] - 8, y1 + 4), "%g" % g, fill=(0, 0, 0), font=F2.font(13))
    for g in yt:
        dr.line([P(xr[0], g), P(xr[1], g)], fill=(230, 230, 230)); dr.text((x0 - 40, P(xr[0], g)[1] - 7), "%g" % g, fill=(0, 0, 0), font=F2.font(13))
    dr.text((x0 + 6, y0 + 4), title, fill=(0, 0, 0), font=F2.font(16))
    return P


def fig_profile(d):
    R = rows_of(d)
    aux = np.load(os.path.join(d, "cand", "kstarP28R01RG_a45_build_aux.npz"))
    im = Image.new("RGB", (1920, 1080), "white"); dr = ImageDraw.Draw(im)
    dr.text((10, 8), "RIDGE: crest spine at t* (col 90). grey = P28R2rec, orange = RAYS A5, blue = RIDGE; dashed green = upper bound U (base + cap: sky / boat rays, Rmin guard), "
            "dotted = goal ridge. Painted top c -2.4..+0.2 is held by the painting outline.", fill=(0, 0, 0), font=F2.font(16))
    cols = {"P28R2rec": (150, 150, 150), "A5": (240, 140, 20), "RIDGE": (30, 90, 230)}
    data = {k: np.load(v) for k, v in R.items()}
    P = plot_frame(dr, (80, 50, 1180, 520), (-16, 15), (0, 24), range(-16, 16, 2), range(0, 25, 4), "Elevation H(c) of the crest (m) vs c (m) — seen from behind, c+ is the far end")
    c = data["RIDGE"]["c"]
    H0 = data["P28R2rec"]["Y"][:, 90]
    U = H0 + np.maximum(aux["cap"] - 0.03, 0.0)
    m = (c > -2.6) & (c < 13.8)
    pts = [P(x, y) for x, y in zip(c[m], np.minimum(U[m], 24))]
    for k in range(0, len(pts) - 1, 2):
        dr.line([pts[k], pts[k + 1]], fill=(40, 160, 60), width=2)
    g = aux["goal"]
    for k in range(0, int(m.sum()) - 1, 3):
        xx = c[m][k]; dr.ellipse([P(xx, g[m][k])[0] - 1.5, P(xx, g[m][k])[1] - 1.5, P(xx, g[m][k])[0] + 1.5, P(xx, g[m][k])[1] + 1.5], fill=(30, 90, 230))
    for lab, z in data.items():
        cc = z["c"]; mm = (cc >= -16) & (cc <= 15)
        dr.line([P(x, y) for x, y in zip(cc[mm], z["Y"][mm].max(1))], fill=cols[lab], width=3 if lab == "RIDGE" else 2)
    P2 = plot_frame(dr, (80, 580, 1180, 1040), (-16, 15), (-16, 2), range(-16, 16, 2), range(-16, 3, 2), "Plan a(c) of the crest (m, forward = up): the far rows already retreat; RIDGE moves the crest back up to 1.1 m (c 0..5) for headroom")
    for lab, z in data.items():
        cc = z["c"]; mm = (cc >= -16) & (cc <= 15)
        jt = z["Y"][mm, :200].argmax(1)
        dr.line([P2(x, y) for x, y in zip(cc[mm], z["A"][mm][np.arange(mm.sum()), jt])], fill=cols[lab], width=3 if lab == "RIDGE" else 2)
    # 溝の深さ
    mr = json.load(open(os.path.join(d, "final", "metrics_ridge.json"), encoding="utf-8"))
    P3 = plot_frame(dr, (1280, 50, 1880, 520), (0, 2.0), (3, 20), [0, 0.5, 1.0, 1.5, 2.0], range(4, 21, 2), "Vertical groove seen from behind: depth (m) by height y (m)")
    for lab, key in (("P28R2rec", "P28R2rec"), ("A5", "A5"), ("RIDGE", "RG")):
        gd = mr[key]["groove_depth_by_y"]
        dr.line([P3(v[1], v[0]) for v in gd], fill=cols[lab], width=3)
    yy = 560
    for lab, key in (("P28R2rec", "P28R2rec"), ("A5", "A5"), ("RIDGE", "RG")):
        r = mr[key]
        txt = "%s: groove max %.2f m (y %d, c %+.1f) | spine kappa max %.2f /m | crest low behind painted top %.2f m | H max %.2f at c %+.1f | top chord min %.0f deg" % (
            lab, r["groove_max"][1], r["groove_max"][0], r["groove_max"][2], r["spine3d"]["kappa_max_per_m"], r["H_dip_behind_painted_top_m"], r["H_max"], r["c_H_max"],
            r["top_chord_pm2m_min_deg_c-2_9"][0])
        parts = txt.split(" | ")
        dr.text((1230, yy), parts[0], fill=cols[lab], font=F2.font(15)); yy += 20
        for q in parts[1:]:
            dr.text((1250, yy), q, fill=cols[lab], font=F2.font(14)); yy += 18
        yy += 10
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    im.save(os.path.join(d, "figs", "fig_ridge_profile_1920x1080.png"))


def fig_sections(d):
    R = rows_of(d)
    cs = [-2.4, -0.8, 0.4, 1.4, 2.2, 3.4, 4.6, 5.8, 7.0, 8.2, 9.4, 10.6]
    cols, cw, ch = 4, 480, 340
    im = Image.new("RGB", (1920, 1080), "white"); dr = ImageDraw.Draw(im)
    xlim, ylim = (-25, 16), (-2, 25)
    zb = np.load(R["P28R2rec"]); zr = np.load(R["RIDGE"])
    c = zr["c"]
    G = R2.keepout_grids(c, 3, 2, cache=os.path.join(d, "cache", "keepout_d3.npz"))
    s = min((cw - 16) / (xlim[1] - xlim[0]), (ch - 26) / (ylim[1] - ylim[0]))
    top = 40
    dr.text((10, 8), "Sections at t* (a forward = right, y up): grey = P28R2rec, blue = RIDGE, light blue = painting-sky ray keep-out (3 px). Dots: cols 18, 90, 101, 185, 200.",
            fill=(0, 0, 0), font=F2.font(16))
    for k, cc in enumerate(cs):
        ox, oy = (k % cols) * cw, top + (k // cols) * ch
        i = int(np.argmin(abs(c - cc)))

        def P(a, y):
            return (ox + 8 + (a - xlim[0]) * s, oy + ch - 8 - (y - ylim[0]) * s)
        ys_, xs_ = np.nonzero(G[i][::2, ::2])
        for yy_, xx_ in zip(ys_, xs_):
            a = R2.GA0 + 2 * xx_ * R2.GRES; y = R2.GY0 + 2 * yy_ * R2.GRES
            if xlim[0] <= a <= xlim[1] and ylim[0] <= y <= ylim[1]:
                x, yv = P(a, y); dr.point((x, yv), fill=(170, 210, 250))
        for g in range(-25, 17, 5):
            dr.line([P(g, ylim[0]), P(g, ylim[1])], fill=(235, 235, 235))
        for g in range(0, 26, 5):
            dr.line([P(xlim[0], g), P(xlim[1], g)], fill=(235, 235, 235))
        for z, rgb, w in ((zb, (140, 140, 140), 1), (zr, (30, 90, 230), 2)):
            dr.line([P(a, y) for a, y in zip(z["A"][i], z["Y"][i])], fill=rgb, width=w)
            for j in (18, 90, 101, 185, 200):
                x, y = P(z["A"][i, j], z["Y"][i, j]); dr.ellipse([x - 2.5, y - 2.5, x + 2.5, y + 2.5], fill=rgb)
        dr.text((ox + 10, oy + 4), "c = %+.1f m  (H %.2f -> %.2f)" % (c[i], zb["Y"][i].max(), zr["Y"][i].max()), fill=(0, 0, 0), font=F2.font(16))
    os.makedirs(os.path.join(d, "figs"), exist_ok=True)
    im.save(os.path.join(d, "figs", "fig_ridge_sections_1920x1080.png"))


def fig_painting_numpy(d):
    import rec_score as RS
    import rec_common as RCc
    R = rows_of(d)
    S9 = RCc.stage9_classes(2)
    panes = []
    for lab in ("P28R2rec", "RIDGE"):
        r, o = RS.score(R[lab], 2, lab)
        c, A, Y = RCc.load_rows(R[lab])
        z, _ = RCc.zbuf(c, A, Y, 2)
        img = np.full(z.shape + (3,), 245, np.uint8)
        img[S9["sky"]] = (240, 228, 205)
        img[np.isfinite(z)] = (150, 110, 60)
        prot = S9["boat_left"] | S9["boat_mid"] | S9["boat_fg"]
        img[prot & ~np.isfinite(z)] = (120, 180, 230)
        ln = cv2.dilate(o["ln"].astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
        img[ln] = (40, 40, 40)
        cl = o["closer"] & (np.abs(z - RS.ref_state(2)[2]) > 1.0)
        img[cl] = (255, 140, 0)
        new = cv2.dilate(o["new"].astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        img[new] = (230, 0, 0)
        img = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
        cv2.putText(img, "%s: new lines vs R4 %d px, surface >=1 m closer over boats/near sea %d px, boat_left closer %d px (ss=2)" % (
            lab, r["new_line_px"], r["protected_closer_px_1m"], r["boat_left_closer_px_0p05m"]), (8, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
        panes.append((img, z))
    diff = np.full((540, 960, 3), 255, np.uint8)
    za, zb_ = panes[0][1], panes[1][1]
    dz = np.where(np.isfinite(za) & np.isfinite(zb_), np.abs(za - zb_), np.where(np.isfinite(za) ^ np.isfinite(zb_), 99.0, 0.0))
    dm = cv2.resize((dz > 0.01).astype(np.uint8) * 255, (960, 540), interpolation=cv2.INTER_NEAREST)
    diff[dm > 0] = (230, 0, 0)
    cv2.putText(diff, "pixels whose visible depth differs > 1 cm (RIDGE vs P28R2rec): %d (ss=2)" % int((dz > 0.01).sum()), (8, 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    leg = np.full((540, 960, 3), 255, np.uint8)
    for k, (t, col) in enumerate((("brown = hero surface (numpy z-buffer, painting camera, t*)", (150, 110, 60)),
                                  ("dark = outline shell lines (design 38 mask of R4)", (40, 40, 40)),
                                  ("red = lines new vs R4 (dilated; all of them were already in P28R2rec)", (230, 0, 0)),
                                  ("orange = over stage-9 boats/near sea, surface >= 1 m closer than R4", (255, 140, 0)),
                                  ("light blue = boats not covered", (120, 180, 230)))):
        cv2.rectangle(leg, (20, 40 + 60 * k), (60, 70 + 60 * k), col, -1)
        cv2.putText(leg, t, (75, 62 + 60 * k), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    out = np.vstack([np.hstack([panes[0][0], panes[1][0]]), np.hstack([diff, leg])])
    # 色は RGB で書いたので、cv2 の BGR へ直して書く（凡例の色名と画像の色を合わせる）
    cv2.imwrite(os.path.join(d, "figs", "fig_ridge_painting_numpy_1920x1080.png"), cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    return int((dz > 0.01).sum())


def fig_crease(d):
    R = rows_of(d)
    outs = []
    for lab in ("P28R2rec", "A5", "RIDGE"):
        z = np.load(R[lab]); c, A, Y = z["c"], z["A"], z["Y"]
        X = np.stack([A, Y], -1)
        d1 = (X[1:] - X[:-1]) / np.diff(c)[:, None, None]
        cm = 0.5 * (c[1:] + c[:-1])
        k = np.linalg.norm((d1[1:] - d1[:-1]) / np.diff(cm)[:, None, None], axis=-1)
        sel = (c[1:-1] > -12) & (c[1:-1] < 13)
        K = k[sel][:, :130]
        img = (255 * (1 - np.clip(K / 1.0, 0, 1))).astype(np.uint8)
        img = cv2.cvtColor(cv2.resize(img, (130 * 4, 960), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)
        rows = np.nonzero(sel)[0] + 1
        for cc in range(-12, 13, 2):
            r = int(np.argmin(abs(c[rows] - cc)) * 960 / len(rows))
            cv2.putText(img, "c %+d" % cc, (2, r + 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        for j in (18, 60, 90, 120):
            cv2.line(img, (j * 4, 0), (j * 4, 959), (200, 120, 0), 1)
        p99 = float(np.percentile(k[(c[1:-1] > -8) & (c[1:-1] < 12)][:, 18:86], 99))
        cv2.putText(img, "%s  p99 back %.2f" % (lab, p99), (150, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        outs.append(img)
    canvas = np.full((1080, 1920, 3), 255, np.uint8)
    cv2.putText(canvas, "Back surface curvature along c |d2(a,y)/dc2| (dark = vertical folds/grooves seen from behind). Columns 0..130 (blue: 18 foot, 60, 90 crest, 120 lip). Rows c -12..+13.",
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
    for k, o in enumerate(outs):
        canvas[80:80 + o.shape[0], 40 + k * 620:40 + k * 620 + o.shape[1]] = o
    cv2.imwrite(os.path.join(d, "figs", "fig_ridge_crease_1920x1080.png"), canvas)


def video(d):
    rd = os.path.join(d, "renders"); vd = os.path.join(d, "videos"); os.makedirs(vd, exist_ok=True)
    out = os.path.join(vd, "ridge_turntable_P28R2rec_vs_RIDGE.mp4")
    cmd = [RR.FFMPEG, "-y", "-loglevel", "error", "-i", os.path.join(rd, "turntable_P28R2rec.mp4"), "-i", os.path.join(rd, "turntable_RG.mp4"),
           # 左 = P28R2rec、右 = RIDGE（drawtext はこの ffmpeg の Windows 版で落ちるので文字は入れない）
           "-filter_complex", "[0:v]scale=960:540[a];[1:v]scale=960:540[b];[a][b]hstack=inputs=2[v]",
           "-map", "[v]", "-c:v", "libx264", "-crf", "26", "-preset", "slow", "-pix_fmt", "yuv420p", out]
    subprocess.run(cmd, check=True)
    return out, os.path.getsize(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    d = sys.argv[1]
    what = sys.argv[2:] or ["sheets", "profile", "sections", "numpy", "crease", "video"]
    res = {}
    if "sheets" in what:
        sheets(d)
    if "profile" in what:
        fig_profile(d)
    if "sections" in what:
        fig_sections(d)
    if "numpy" in what:
        res["painting_depth_diff_px_ss2"] = fig_painting_numpy(d)
    if "crease" in what:
        fig_crease(d)
    if "video" in what:
        res["video"] = video(d)
    print("RIDGE_FIG_DONE", json.dumps(res))
