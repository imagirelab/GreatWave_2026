# -*- coding: utf-8 -*-
"""美術の見本06 の段の行（B-ROWS）の断面の下見：行の断面を c ごとに並べて描く（形だけ。Unity の描画ではない）。
py -3.10 -B Tools/GWWaveGen/as06/rows_diag.py <out.png> <名前=行の npz> [<名前=行の npz> ...] [--c=-22,-20,...]

各図：灰 = 空の射線の禁止域（原画の輪郭の関門を守る所）、淡い青 = 船・手前の海の射線の禁止域（Q34 で形の制約から外した。参考に描く）、
細い灰の線 = 1 つ目の行、色の線 = 2 つ目以後の行。橙・紫の点の列 = 原画の ②・③ の層の頂の線（READ_CREST）の射線がその c の面を通る点
（その線の上に頂を置けば、原画視点で層の頂が原画の位置に写る）。
原画のカメラは測りにだけ使う（色は写さない）。参照モデル・写真は読まない。
"""
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as05")
import shapeB_common as B  # noqa: E402

CS = [-23.0, -21.5, -20.0, -18.5, -17.0, -15.5, -14.0, -12.5, -11.0, -9.5, -8.6, -7.0]
COLS = [(160, 160, 160), (200, 40, 40), (30, 140, 40), (40, 40, 200)]


def crest_section_points(key, cc, n=120):
    """READ_CREST[key] の画素の射線が c = cc の面を通る点 (a, y) の列。"""
    pts = np.array(B.READ_CREST[key], float)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    t = np.linspace(0, s[-1], n)
    xs = np.interp(t, s, pts[:, 0]); ys = np.interp(t, s, pts[:, 1])
    s0 = B.K.sec(B.K.CAM_POS_U[None])[0]
    out = []
    for x, y in zip(xs, ys):
        D = B.ray_dir(x, y)
        q1 = B.K.sec((B.K.CAM_POS_U + 1.0 * D)[None])[0] - s0      # 1 m 当たりの (a, y, c) の動き
        if abs(q1[2]) < 1e-6:
            continue
        tt = (cc - s0[2]) / q1[2]
        if tt <= 0:
            continue
        out.append((s0[0] + tt * q1[0], s0[1] + tt * q1[1], tt))
    return np.array(out)


def main():
    outp = sys.argv[1]
    items = [a for a in sys.argv[2:] if not a.startswith("--")]
    cs = CS
    for a in sys.argv[2:]:
        if a.startswith("--c="):
            cs = [float(x) for x in a[4:].split(",")]
    rows = []
    for it in items:
        nm, p = it.split("=", 1)
        rows.append((nm,) + B.load_rows(p))
    import r2_common as R
    zp = np.load(REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
    Gp = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    c = rows[0][1]
    Gs = R.keepout_grids(c, 3, 2, cache=REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    W, H = 520, 360
    ncol = 4
    nrow = (len(cs) + ncol - 1) // ncol
    img = np.full((H * nrow + 40, W * ncol, 3), 250, np.uint8)
    sc = 20.0
    for k, cc in enumerate(cs):
        i = int(np.argmin(np.abs(c - cc)))
        ox, oy = (k % ncol) * W, (k // ncol) * H + 40

        def P(a, y):
            return (int(ox + W * 0.45 + a * sc), int(oy + H - 24 - y * sc))
        for G, col in ((Gs[i], (215, 215, 215)), (Gp[i], (250, 215, 160))):
            ys, xs = np.nonzero(G[::2, ::2])
            a = R.GA0 + xs * 2 * R.GRES; y = R.GY0 + ys * 2 * R.GRES
            q = np.array([P(aa, yy) for aa, yy in zip(a, y)]) if len(a) else np.zeros((0, 2), int)
            if len(q):
                ok = (q[:, 0] >= ox) & (q[:, 0] < ox + W) & (q[:, 1] >= oy) & (q[:, 1] < oy + H)
                img[q[ok, 1], q[ok, 0]] = col
        cv2.line(img, P(-12, 0), P(14, 0), (120, 120, 120), 1)
        for yy in (0.36, 0.42, 0.52, 0.60):
            cv2.line(img, P(-12, yy * B.H0), P(-11.2, yy * B.H0), (0, 0, 0), 1)
            cv2.putText(img, "%.2f" % yy, P(-14.6, yy * B.H0 - 0.15), cv2.FONT_HERSHEY_SIMPLEX, 0.32, (0, 0, 0), 1, cv2.LINE_AA)
        for key, col in (("r2", (0, 140, 255)), ("r3", (200, 0, 200))):
            Q = crest_section_points(key, cc)
            for q in Q:
                pp = P(q[0], q[1])
                if ox <= pp[0] < ox + W and oy <= pp[1] < oy + H:
                    cv2.circle(img, pp, 1, col, -1)
        for r, (nm, cr, Ar, Yr) in enumerate(rows):
            ii = int(np.argmin(np.abs(cr - cc)))
            pts = np.array([P(Ar[ii, j], Yr[ii, j]) for j in range(0, 400)], np.int32)
            cv2.polylines(img, [pts], False, COLS[r % len(COLS)], 1 if r == 0 else 2, cv2.LINE_AA)
            for j, mk in ((90, 3), (200, 3)):
                cv2.circle(img, tuple(pts[j]), mk, COLS[r % len(COLS)], 1)
        cv2.putText(img, "c %.2f" % c[i], (ox + 6, oy + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.rectangle(img, (ox, oy), (ox + W - 1, oy + H - 1), (200, 200, 200), 1)
    x = 8
    for r, (nm, *_ ) in enumerate(rows):
        cv2.putText(img, nm, (x, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.7, COLS[r % len(COLS)], 2, cv2.LINE_AA)
        x += 20 + 14 * len(nm)
    cv2.putText(img, "grey=sky keepout  orange=boat/near-sea keepout(dropped Q34)  dots: painting crest rays r2(orange) r3(purple)",
                (x + 10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.imwrite(outp, img)
    print("DIAG_DONE", outp)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
