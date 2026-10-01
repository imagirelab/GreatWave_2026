# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：なぜ形がそうなるかを示す図（py -3.10、cv2）。
  fig_sections_R4_FS1.png：肩の行の断面（灰 R4、黒 FS1）と、その行の面を原画カメラの左の外輪郭の射線が通る跡（水色、78→131、黄 132）。
                           ● = 行の最も高い点。FS1 では輪郭の射線に接する所が頂（列 90）から前の唇の上面へ移る。
  fig_far_lock.png        ：奥の行（c > +2）の断面と、原画視点で空に見える画素（管の口・唇の上の空）の射線の跡（桃色）。
                           奥の行の唇先は空の射線に接していて、前へ動かす余地がない（奥の端の後ろへの引きは原画から決まる）。
  fig_crestline.png       ：行の最も高い点の高さ H(c) と位置 a_top(c)、背の足の位置 a(列 18)（R4 と FS1）。後ろから見た輪郭はこの列で決まる。
usage: py -3.10 faceswap_figs.py <out_dir> R4=<rows.npz> FS1=<rows.npz>"""
import os
import sys

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
import faceswap_build as FB  # noqa: E402
KC = F.KC


def canvas(imgs, ncol, title):
    import cv2
    G = F.grid_images(imgs, ncol)
    top = np.full((44, G.shape[1], 3), 255, np.uint8)
    cv2.putText(top, title, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    G = np.vstack([top, G])
    s = min(1920 / G.shape[1], 1080 / G.shape[0])
    G = cv2.resize(G, (int(G.shape[1] * s), int(G.shape[0] * s)), interpolation=cv2.INTER_AREA)
    out = np.full((1080, 1920, 3), 255, np.uint8)
    out[:G.shape[0], :G.shape[1]] = G
    return out


def main():
    import cv2
    out = sys.argv[1]
    items = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    (l0, p0), (l1, p1) = list(items.items())[:2]
    z0, z1 = np.load(p0), np.load(p1)
    c = z0["c"].astype(float)
    A0, Y0, A1, Y1 = z0["A"], z0["Y"], z1["A"], z1["Y"]
    seg = F.outline_segments()
    L = np.vstack([seg["78"], seg["130"][1:], seg["131"][1:]])
    L132 = seg["132"]
    ims = []
    for c0 in (-20, -17, -14, -12, -10, -8, -6, -4, -2.5, -1.2, 1, 3):
        r = int(np.argmin(abs(c - c0)))
        tr, _ = F.ray_row_trace(L, c[r]); t2, _ = F.ray_row_trace(L132, c[r])
        p = F.Plot((-22, 16), (-1, 23), 560, 340, "c = %.2f   H %s %.2f -> %s %.2f" % (c[r], l0, Y0[r].max(), l1, Y1[r].max()))
        p.line(A0[r], Y0[r], (170, 170, 170), 2)
        p.line(A1[r], Y1[r], (0, 0, 0), 1)
        p.line(tr[:, 0], tr[:, 1], (200, 160, 0), 2)
        p.line(t2[:, 0], t2[:, 1], (0, 190, 230), 2)
        for AA, YY, col in ((A0, Y0, (150, 150, 150)), (A1, Y1, (0, 0, 220))):
            jm = int(np.argmax(YY[r, :200]))
            p.dot(AA[r, jm], YY[r, jm], col, 5)
        ims.append(p.img)
    cv2.imwrite(os.path.join(out, "fig_sections_%s_%s.png" % (l0, l1)),
                canvas(ims, 4, "Shoulder sections: grey %s, black %s; light-blue = painting rays of 78/130/131 through this row plane, cyan = 132; dot = row top" % (l0, l1)))
    # far lock
    B = FB.Builder({"steps": []})
    px = B.sky_rays_px()
    ims = []
    for c0 in (2, 3.5, 5, 6.5, 8, 9.5, 11, 12.4):
        r = int(np.argmin(abs(c - c0)))
        ts, _ = F.ray_row_trace(px, c[r])
        p = F.Plot((-30, 20), (-1, 26), 560, 340, "far row c = %.2f (H %.2f)" % (c[r], Y1[r].max()))
        for q in ts[::2]:
            if -30 < q[0] < 20 and -1 < q[1] < 26:
                p.dot(q[0], q[1], (200, 200, 255), 1)
        p.line(A0[r], Y0[r], (170, 170, 170), 2)
        p.line(A1[r], Y1[r], (0, 0, 0), 1)
        p.dot(A1[r, 200], Y1[r, 200], (255, 0, 0), 4)
        ims.append(p.img)
    cv2.imwrite(os.path.join(out, "fig_far_lock.png"),
                canvas(ims, 4, "Far rows: pink = where the painting's sky rays (tube mouth and sky above the lip) cross the row plane; blue dot = lip tip (touches the sky)"))
    # crest line
    p = F.Plot((-45, 15), (0, 22), 1800, 460, "row top height H(c) [m]: grey %s, black %s" % (l0, l1))
    p.line(c, Y0.max(1), (150, 150, 150), 3); p.line(c, Y1.max(1), (0, 0, 0), 2)
    q = F.Plot((-45, 15), (-25, 10), 1800, 460, "a of the row top (solid) and of the back foot col 18 (thin) [m]: grey %s, black %s" % (l0, l1))
    for AA, YY, col, th in ((A0, Y0, (150, 150, 150), 3), (A1, Y1, (0, 0, 0), 2)):
        at = np.array([AA[r, int(np.argmax(YY[r, :200]))] for r in range(len(c))])
        q.line(c, at, col, th); q.line(c, AA[:, 18], col, 1)
    img = np.vstack([np.full((60, 1800, 3), 255, np.uint8), p.img, np.full((20, 1800, 3), 255, np.uint8), q.img])
    cv2.putText(img, "Crest line along c (x axis: c [m], left = near end toward the painting camera)", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2, cv2.LINE_AA)
    outi = np.full((1080, 1920, 3), 255, np.uint8)
    outi[:img.shape[0], 60:60 + img.shape[1]] = img
    cv2.imwrite(os.path.join(out, "fig_crestline.png"), outi)
    print("figs written", out)


if __name__ == "__main__":
    main()
