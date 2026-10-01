# -*- coding: utf-8 -*-
"""仕上げ28 第1回（背から先に作る案、back-first）の診断（py -3.10）。
行の npz（A, Y, c）を読み、(1) 原画の上に各行の頂・背の点の像と原画の輪郭 78/130/131/132/72 を重ねた図、
(2) 平面図（c ごとの頂の a、背の a（y 3/6/10/15 m）、前面の a）、(3) H(c) の図 を書く。参照モデルは読まない。
usage: py -3.10 backfirst_diag.py OUT_DIR label=rows.npz ...
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"), os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"),
          os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import cv2  # noqa: E402
import kh_common as KC  # noqa: E402


def truth_segments():
    import evaluate as E
    tr = E.Truth()
    return {s["id"]: np.array(s["points_display"], float) for s in tr.outline["envelope"]["segments"]}


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    seg = truth_segments()
    plate = cv2.imread(os.path.join(REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png"))
    cols = {"78": (0, 0, 255), "130": (0, 160, 255), "131": (0, 255, 255), "132": (0, 255, 0), "72": (255, 0, 255)}
    for arg in sys.argv[2:]:
        lab, p = arg.split("=", 1)
        z = np.load(p)
        A, Y, c = z["A"].astype(float), z["Y"].astype(float), z["c"].astype(float)
        X = KC.world(c, A, Y)
        img = (plate * 0.5).astype(np.uint8)
        for k, P in seg.items():
            cv2.polylines(img, [np.round(P).astype(np.int32).reshape(-1, 1, 2)], False, cols.get(k, (200, 200, 200)), 2, cv2.LINE_AA)
            m = P[len(P) // 2]
            cv2.putText(img, k, (int(m[0]) + 6, int(m[1])), cv2.FONT_HERSHEY_SIMPLEX, 0.6, cols.get(k, (200, 200, 200)), 2)
        top = Y.argmax(1)
        for r in range(0, len(c), 2):
            if Y[r].max() < 0.5:
                continue
            P = KC.project_unity(X[r])
            # row polyline thin grey, crest dot white
            cv2.polylines(img, [np.round(P[:, :2]).astype(np.int32).reshape(-1, 1, 2)], False, (90, 90, 90), 1, cv2.LINE_AA)
            q = P[top[r]]
            col = (255, 255, 255) if c[r] <= 0 else (255, 200, 120)
            cv2.circle(img, (int(q[0]), int(q[1])), 2, col, -1)
            if r % 16 == 0:
                cv2.putText(img, "%+.0f" % c[r], (int(q[0]) - 30, int(q[1]) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, col, 1)
        cv2.imwrite(os.path.join(out, "diag_painting_%s.png" % lab), img)
        # plan view + H(c)
        W, Hh = 1600, 900
        pv = np.full((Hh, W, 3), 255, np.uint8)
        def to_px(cc, aa):
            return (int(80 + (cc + 62) / 80.0 * (W - 120)), int(Hh / 2 - aa * 12))
        for i in range(-60, 21, 5):
            x, _ = to_px(i, 0); cv2.line(pv, (x, 0), (x, Hh), (230, 230, 230), 1); cv2.putText(pv, str(i), (x + 2, Hh - 6), 0, 0.4, (120, 120, 120), 1)
        for a in range(-30, 31, 5):
            _, y = to_px(0, a); cv2.line(pv, (0, y), (W, y), (230, 230, 230), 1); cv2.putText(pv, str(a), (2, y - 2), 0, 0.4, (120, 120, 120), 1)
        H = Y.max(1)
        series = {"a_top": (A[np.arange(len(c)), top], (0, 0, 0))}
        for h, col in ((3, (0, 140, 0)), (6, (0, 0, 200)), (10, (200, 0, 0)), (15, (160, 0, 160))):
            ab, af = np.full(len(c), np.nan), np.full(len(c), np.nan)
            for r in range(len(c)):
                if H[r] < h + 0.2:
                    continue
                j = np.nonzero(Y[r, :top[r] + 1] >= h)[0]
                if len(j):
                    j = j[0]
                    if j > 0:
                        t = (h - Y[r, j - 1]) / (Y[r, j] - Y[r, j - 1]); ab[r] = A[r, j - 1] + t * (A[r, j] - A[r, j - 1])
                # front: the lowest col after the tip crossing y=h going down on the face (cols 314..394)
                jf = np.nonzero(Y[r, 314:395] >= h)[0]
                if len(jf):
                    af[r] = A[r, 314 + jf[-1]]
            series["back_y%d" % h] = (ab, col)
            series["face_y%d" % h] = (af, tuple(int(v * 0.6) for v in col))
        for nm, (v, col) in series.items():
            pts = [to_px(cc, aa) for cc, aa in zip(c, v) if np.isfinite(aa)]
            if len(pts) > 1:
                cv2.polylines(pv, [np.array(pts, np.int32).reshape(-1, 1, 2)], False, col, 2 if nm == "a_top" else 1, cv2.LINE_AA)
                cv2.putText(pv, nm, pts[-1], 0, 0.4, col, 1)
        # H(c) along the bottom as a strip
        pts = [(to_px(cc, 0)[0], int(Hh - 40 - hh * 8)) for cc, hh in zip(c, H)]
        cv2.polylines(pv, [np.array(pts, np.int32).reshape(-1, 1, 2)], False, (0, 120, 200), 2, cv2.LINE_AA)
        cv2.putText(pv, "%s plan: a (up = travel direction +T) vs c; orange = H(c) x8 px/m" % lab, (10, 20), 0, 0.6, (0, 0, 0), 1)
        cv2.imwrite(os.path.join(out, "diag_plan_%s.png" % lab), pv)
        print(lab, "written", flush=True)


if __name__ == "__main__":
    main()
