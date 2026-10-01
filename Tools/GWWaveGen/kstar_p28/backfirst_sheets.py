# -*- coding: utf-8 -*-
"""仕上げ28 第1回（back-first）：R4 と候補を同じ視点で並べた図（1920×1080 の PNG）を作る（py -3.10）。
usage: py -3.10 backfirst_sheets.py V2_DIR
  入力：V2_DIR/candidate/kstarP28bf_a45_rows.npz、V2_DIR/eval/renders（kh_eval の 9 視点・利用者の失敗の視点・回り台）、
        V2_DIR/renders_back（後ろの 3 視点）、R4 の行（Unity/Build/Design/28R01F/kstar_final）
  出力：V2_DIR/sheets/*.png（すべて 1920×1080）
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import numpy as np  # noqa: E402
import cv2  # noqa: E402

R4_ROWS = os.path.join(REPO, "Unity", "Build", "Design", "28R01F", "kstar_final", "kstarR4_a45_rows.npz")
W, H = 1920, 1080


def fit(im, w, h, bg=(255, 255, 255)):
    s = min(w / im.shape[1], h / im.shape[0])
    r = cv2.resize(im, (max(1, int(im.shape[1] * s)), max(1, int(im.shape[0] * s))), interpolation=cv2.INTER_AREA)
    out = np.full((h, w, 3), bg, np.uint8)
    y0 = (h - r.shape[0]) // 2; x0 = (w - r.shape[1]) // 2
    out[y0:y0 + r.shape[0], x0:x0 + r.shape[1]] = r
    return out


def label(im, t, pos=(10, 28), sc=0.75):
    cv2.putText(im, t, pos, cv2.FONT_HERSHEY_SIMPLEX, sc, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(im, t, pos, cv2.FONT_HERSHEY_SIMPLEX, sc, (255, 255, 255), 1, cv2.LINE_AA)
    return im


def grid(cells, ncol, title, path):
    """cells: list of (image, label). 1920×1080 with a 40 px title bar."""
    nrow = int(np.ceil(len(cells) / ncol))
    cw, ch = W // ncol, (H - 40) // nrow
    out = np.full((H, W, 3), 255, np.uint8)
    cv2.putText(out, title, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    for i, (im, lab) in enumerate(cells):
        r, cc = divmod(i, ncol)
        t = fit(im, cw - 4, ch - 4) if im is not None else np.full((ch - 4, cw - 4, 3), 200, np.uint8)
        label(t, lab, sc=0.6)
        out[40 + r * ch:40 + r * ch + t.shape[0], cc * cw:cc * cw + t.shape[1]] = t
    cv2.imwrite(path, out)
    return path


def sections(rows, labels, colors, cs, path, title):
    tiles = []
    for cc in cs:
        tw, th = 470, 300
        im = np.full((th, tw, 3), 255, np.uint8)
        def px(a, y):
            return (int(tw / 2 + a * 8.5), int(th - 45 - y * 10.5))
        for gx in range(-25, 26, 5):
            cv2.line(im, px(gx, -4), px(gx, 23), (235, 235, 235), 1)
        for gy in range(0, 23, 5):
            cv2.line(im, px(-27, gy), px(27, gy), (235, 235, 235), 1)
        txt = "c=%+.1f" % cc
        for (c, A, Y), lab, col in zip(rows, labels, colors):
            r = int(np.argmin(np.abs(c - cc)))
            pts = np.array([px(a, y) for a, y in zip(A[r], Y[r])], np.int32)
            cv2.polylines(im, [pts.reshape(-1, 1, 2)], False, col, 2, cv2.LINE_AA)
            txt += "  %s H=%.1f" % (lab, Y[r].max())
        cv2.putText(im, txt, (6, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append((im, ""))
    return grid(tiles, 4, title, path)


def main():
    v2 = sys.argv[1]
    out = os.path.join(v2, "sheets"); os.makedirs(out, exist_ok=True)
    rd = os.path.join(v2, "eval", "renders"); bd = os.path.join(v2, "renders_back")
    made = []
    def rim(d, lab, vn):
        p = os.path.join(d, "%s__%s.png" % (lab, vn))
        return cv2.imread(p) if os.path.isfile(p) else None
    # 1 back views (the Q21 dome check): R4 | P28bf | K* 26R01
    cells = []
    for vn in ("b1_back_p65", "b2_back_0", "b3_back_m65"):
        for lab in ("R4", "P28bf", "Kstar26R01"):
            cells.append((rim(bd, lab, vn), "%s  %s" % (lab, vn)))
    made.append(grid(cells, 3, "Polish 28 round 1 back-first: back views (65 deg toward the far end / straight back / 65 deg toward the near tail)  R4 | candidate | K* 26R01",
                     os.path.join(out, "sheet_back_views_R4_P28bf_Kstar.png")))
    # 2 user-failure views
    cells = []
    for vn in ("u11_v9zoom_crest_bulge", "u12a_v5_back_three_quarter", "u13_v8zoom_b_region", "u10_foot_zoom"):
        for lab in ("R4", "P28bf"):
            cells.append((rim(rd, lab, vn), "%s  %s" % (lab, vn)))
    made.append(grid(cells, 4, "Polish 28 round 1: the user's Q21 failure views  (R4 | candidate, pairs)", os.path.join(out, "sheet_user_failure_views_R4_P28bf.png")))
    # 3/4 standard views
    std = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
           "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]
    for k, part in enumerate((std[:5], std[5:])):
        cells = []
        for vn in part:
            for lab in ("R4", "P28bf"):
                cells.append((rim(rd, lab, vn), "%s  %s" % (lab, vn)))
        made.append(grid(cells, 4, "Polish 28 round 1: standard views %d/2  (R4 | candidate, pairs)" % (k + 1),
                         os.path.join(out, "sheet_views_std%d_R4_P28bf.png" % (k + 1))))
    # 5 turntable stills
    cells = []
    for lab in ("R4", "P28bf"):
        sd = os.path.join(rd, "turntable_" + lab)
        fs = sorted(f for f in os.listdir(sd) if f.endswith(".png"))[:12] if os.path.isdir(sd) else []
        for f in fs[::2]:
            cells.append((cv2.imread(os.path.join(sd, f)), "%s  %s" % (lab, f[:-4])))
    made.append(grid(cells, 6, "Polish 28 round 1: turntable (every 60 deg; top R4, bottom candidate)", os.path.join(out, "sheet_turntable_R4_P28bf.png")))
    # 6 painting-view gate overlays and the tube zoom
    import backfirst_eval as BE
    zc = np.load(os.path.join(v2, "candidate", "kstarP28bf_a45_rows.npz")); z4 = np.load(R4_ROWS)
    ov = {}
    for lab, z in (("R4", z4), ("P28bf", zc)):
        p = os.path.join(out, "_gate_overlay_%s.png" % lab)
        ov[lab] = BE.overlay(z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float), p, lab)
    a = cv2.imread(os.path.join(out, "_gate_overlay_R4.png")); b = cv2.imread(os.path.join(out, "_gate_overlay_P28bf.png"))
    za = a[280:780, 700:1160]; zb = b[280:780, 700:1160]
    cells = [(a, "R4: 78/130/131 max, 132 s12 max, 72 s12 p95 = %.2f/%.2f/%.2f, %.2f, %.2f" % (ov["R4"]["78"]["max"], ov["R4"]["130"]["max"], ov["R4"]["131"]["max"], ov["R4"]["132lf"]["max"], ov["R4"]["72lf"]["p95"])),
             (b, "candidate: %.2f/%.2f/%.2f, %.2f, %.2f" % (ov["P28bf"]["78"]["max"], ov["P28bf"]["130"]["max"], ov["P28bf"]["131"]["max"], ov["P28bf"]["132lf"]["max"], ov["P28bf"]["72lf"]["p95"])),
             (za, "R4 tube / lip zoom"), (zb, "candidate tube / lip zoom")]
    made.append(grid(cells, 2, "Polish 28 round 1: painting-camera outlines (white = candidate coverage; red 78, orange 130, yellow 131, green 132, magenta 72, cyan = s12 large form)",
                     os.path.join(out, "sheet_gate_painting_R4_P28bf.png")))
    # 7 sections
    rows = [(z4["c"], z4["A"], z4["Y"]), (zc["c"], zc["A"], zc["Y"])]
    made.append(sections(rows, ["R4", "cand"], [(160, 160, 160), (0, 0, 220)], [-24, -18, -14, -10, -6, -2, 0, 3, 6, 9, 11, 13],
                         os.path.join(out, "sheet_sections_R4_grey_P28bf_red.png"), "Polish 28 round 1: sections (constant c, 5 m grid): grey = R4, red = candidate"))
    # 8 dome maps (judges' R6 residual)
    tiles = []
    for lab, z in (("R4", z4), ("P28bf", zc)):
        c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
        r = BE.dome(c, A, Y, 1, 2)
        M = BE._C["dome_map_R6"]
        rr = np.nonzero(np.abs(c) <= 16)[0]
        V = M[rr][:, 18:201]
        img = np.clip(np.nan_to_num(V, nan=0) / 1.0, 0, 1)
        col = cv2.applyColorMap((img * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
        col[np.isnan(V)] = (60, 60, 60)
        col = cv2.resize(col, (col.shape[1] * 4, col.shape[0] * 3), interpolation=cv2.INTER_NEAREST)
        for cc in range(-16, 17, 4):
            y = int(np.searchsorted(c[rr], cc)) * 3; cv2.putText(col, "c%+d" % cc, (2, y + 4), 0, 0.4, (255, 255, 255), 1)
        for j in range(20, 201, 20):
            cv2.putText(col, str(j), ((j - 18) * 4, 12), 0, 0.4, (0, 255, 0), 1)
        tiles.append((col, "%s  R6 residual 0..1 m (x: col 18..200, y: c -16..+16)  p99 %.3f  regions %s" % (lab, r["R6"]["p99"], json.dumps(r["R6"]["regions_p99"]))))
    made.append(grid(tiles, 2, "Polish 28 round 1: judges' dome measure (local quadric residual, 6 m) R4 | candidate", os.path.join(out, "sheet_dome_maps_R4_P28bf.png")))
    print("\n".join(made))


if __name__ == "__main__":
    main()
