# -*- coding: utf-8 -*-
"""Q20 candidate B: comparison figures (work products under Unity/Build/Q20/candB)."""
import sys, os, json
import numpy as np, cv2
from candB_common import *
from candB_plot import Canvas

VIEWS = ["v1_painting", "v2_seat", "v3_side_along_crest_cam_side", "v4_true_side_perp_crest_front", "v5_back_three_quarter",
         "v6_top_down", "v7_user6_az330_el10", "v8_user7_az290_el5", "v9_user8_az030_el25"]


def label(im, s):
    cv2.rectangle(im, (0, 0), (im.shape[1], 30), (255, 255, 255), -1)
    cv2.putText(im, s, (8, 22), 0, 0.62, (0, 0, 0), 2, cv2.LINE_AA)
    return im


def views_sheet(out, sel, W=620):
    rows = []
    for v in sel:
        ims = []
        for who, f in (("K* 26R01 (now)", os.path.join(RUBRIC, "renders", "kstar__%s.png" % v)),
                       ("candidate B (K*'_B)", os.path.join(OUT, "renders", "candB__%s.png" % v)),
                       ("reference model (scan of another artist's work, form reference only)", os.path.join(RUBRIC, "renders", "ref__%s.png" % v))):
            im = cv2.imread(f)
            im = np.zeros((360, 640, 3), np.uint8) if im is None else im
            im = cv2.resize(im, (W, int(W * im.shape[0] / im.shape[1])), interpolation=cv2.INTER_AREA)
            ims.append(label(im, "%s | %s" % (v, who)))
        h = max(i.shape[0] for i in ims)
        ims = [np.vstack([i, np.full((h - i.shape[0], W, 3), 255, np.uint8)]) for i in ims]
        rows.append(np.hstack([np.hstack([i, np.full((h, 6, 3), 255, np.uint8)]) for i in ims]))
    cv2.imwrite(out, np.vstack([np.vstack([r, np.full((6, r.shape[1], 3), 255, np.uint8)]) for r in rows]))


def sections_sheet(out, A, Y, c, A0, Y0, c0, cs):
    ims = []
    for cq in cs:
        r = int(np.argmin(np.abs(c - cq))); r0 = int(np.argmin(np.abs(c0 - cq)))
        cv = Canvas(-22, 20, -6, 24, st=0.05); cv.allowed(c[r])
        cv.poly(A0[r0], Y0[r0], (150, 150, 150), 2); cv.poly(A[r], Y[r], (0, 0, 210), 3)
        cv.text("c %+.1f m  (grey K* row %d, red K*'_B row %d)" % (c[r], r0, r), (10, 36), (0, 0, 0), 0.9)
        ims.append(cv2.resize(cv.img, None, fx=0.42, fy=0.42, interpolation=cv2.INTER_AREA))
    while len(ims) % 4:
        ims.append(np.full_like(ims[0], 255))
    rows = [np.hstack(ims[i:i + 4]) for i in range(0, len(ims), 4)]
    img = np.vstack(rows)
    head = np.full((50, img.shape[1], 3), 255, np.uint8)
    cv2.putText(head, "Sections c = const (K* 26R01 section frame, grid 5 m). Light = region hidden in the painting view (the painting silhouette), dark = painted sky.", (10, 32), 0, 0.7, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imwrite(out, np.vstack([head, img]))


def crestline_fig(out, A, Y, c, A0, Y0, c0):
    import rubric_measure as RM
    W, Hh = 1400, 700
    img = np.full((Hh, W, 3), 255, np.uint8)
    def ptp(cx, v, v0, v1, top, h):
        x = int(60 + (cx + 30) / 50 * (W - 100)); y = int(top + h - (v - v0) / (v1 - v0) * h)
        return x, y
    for (AA, YY, cc, col, nm) in ((A0, Y0, c0, (150, 150, 150), "K*"), (A, Y, c, (0, 0, 210), "K*'_B")):
        H = YY.max(1); m = (cc >= -30) & (cc <= 20) & (H > 2)
        at = []
        for r in np.nonzero(m)[0]:
            s = RM.section_metrics(RM.poly_to_segs(AA[r], YY[r]), 0.0, 20.75, open_w=0.0) or {}
            at.append((cc[r], s.get("a_top", np.nan), H[r], s.get("a_tip", np.nan)))
        at = np.array(at)
        P = [ptp(x, v, -10, 10, 40, 260) for x, v in zip(at[:, 0], at[:, 1])]
        cv2.polylines(img, [np.array(P, np.int32)], False, col, 2)
        P = [ptp(x, v, -10, 20, 40, 260) for x, v in zip(at[:, 0], at[:, 3]) if np.isfinite(v)]
        if len(P) > 1:
            cv2.polylines(img, [np.array(P, np.int32)], False, tuple(int(0.6 * k) for k in col), 1)
        P = [ptp(x, v, 0, 25, 360, 300) for x, v in zip(at[:, 0], at[:, 2])]
        cv2.polylines(img, [np.array(P, np.int32)], False, col, 2)
    cv2.putText(img, "plan: crest a_top(c) (thick) and lip tip a(c) (thin); grey K*, red K*'_B", (60, 30), 0, 0.6, (0, 0, 0), 1)
    cv2.putText(img, "elevation: crest height H(c)", (60, 350), 0, 0.6, (0, 0, 0), 1)
    for cx in range(-30, 21, 5):
        x, _ = ptp(cx, 0, 0, 1, 0, 1); cv2.line(img, (x, 40), (x, 660), (225, 225, 225), 1); cv2.putText(img, "%d" % cx, (x - 8, 690), 0, 0.45, (0, 0, 0), 1)
    cv2.imwrite(out, img)


if __name__ == "__main__":
    z = np.load(os.path.join(OUT, "kstarB_a45_rows.npz")); A, Y, c = z["A"], z["Y"], z["c"]
    A0, Y0, c0 = load_kstar()
    views_sheet(os.path.join(OUT, "fig_views_a_kstar_candB_ref.png"), VIEWS[:5])
    views_sheet(os.path.join(OUT, "fig_views_b_kstar_candB_ref.png"), VIEWS[5:])
    sections_sheet(os.path.join(OUT, "fig_sections_kstar_vs_candB.png"), A, Y, c, A0, Y0, c0, [-16, -12, -9, -6, -3, -1.4, 0, 1, 2, 3, 4, 4.4])
    crestline_fig(os.path.join(OUT, "fig_crestline_kstar_vs_candB.png"), A, Y, c, A0, Y0, c0)
    # turntable contact sheet
    tt = os.path.join(OUT, "turntable")
    fr = sorted(f for f in os.listdir(tt) if f.endswith(".png"))[::6]
    ims = [cv2.resize(cv2.imread(os.path.join(tt, f)), (480, 270)) for f in fr]
    while len(ims) % 4:
        ims.append(np.full_like(ims[0], 255))
    cv2.imwrite(os.path.join(OUT, "fig_turntable_contact.png"), np.vstack([np.hstack(ims[i:i + 4]) for i in range(0, len(ims), 4)]))
    print("figs done")
