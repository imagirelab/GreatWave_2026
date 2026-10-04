# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：主役波 K*′ AS05A の行を、見本04 の AS04F の写しから作る（Q33・targets.json の L・K）。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_hero.py [design.json]

順：
  A-1 左の唇を引っ込める（行 c −23〜−13）：見本04 の平らな唇の舌（頂より 7〜8.5 m 前）を、頂より lip_ahead m 前までに短くする
      （見本04 の shape_ops.shorten_row をそのまま使う。切る長さは行ごとに「外の面が頂の a + lip_ahead を越える所」から唇の先まで）。
      ③ の新しい波（shapeA_l3.py）の後ろの鞍がこの短い肩へ続く。
  A-2 ② の縁の頂（行 c −13.4〜−9.6）：背の頂（列 J0 まで、動かさない）→ 溝（② の頂より groove_m 低い）→ ② の頂（原画の ② の爪の上の縁の
      射線の上、カメラから d2 m）→ 短い唇の前の縁 → 唇の下で後ろへ返る面（引っ込み）→ 垂れの下の端 → 元の巻きの面（列 Jjoin）へつなぐ。
      列 J0〜200 を「背の頂 → 唇の前の縁」、列 200〜Jjoin を「唇の下 → つなぎ」の上に並べ直す（列 200 は唇の先の目印のまま）。
  境の輪（行 0・239、列 0・399）と行 c ≥ −8 m（いちばん高い峰、K-top）は動かさない。
行の c・格子 400 × 240・目印の列は変えない。参照モデル・写真は読まない。原画のカメラは ② の頂を置く射線にだけ使う。
"""
import json
import os
import sys
import time

import numpy as np
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import shape_ops as O  # noqa: E402

S = C.SC
DESIGN = {
    "lip": {"lip_ahead": 2.0, "full": [-20.8, -14.6], "blend": [-23.4, -13.0], "sigma_rows": 1.5,
            "shorten": {"jA": 95, "jK": 300, "k_in_min": 0.3, "cap_k": 1.0, "t_nose": 1.2, "d_lift": 10.0, "nose_up": 0.1,
                        "kn0": 0.8, "kn1": 0.8, "cut_full_m": 7.0}},
    "step2": {"full": [-12.4, -8.9], "blend": [-14.8, -8.3], "sigma_rows": 1.5, "J0": 104, "Jjoin": 282, "d2": 48.5,
              "crest_px": [[640, 968], [700, 962], [780, 950], [930, 930], [1050, 925], [1150, 940], [1220, 1000], [1270, 1060], [1300, 1095]],
              "groove_m": 1.35, "groove_frac": 0.5, "dip": [-10.0, -9.2, 0.435], "lip_front": [1.1, -0.7],
              "under": [[0.4, -1.4], [-1.0, -2.2], [-1.4, -3.3], [-1.6, -4.0]]},
    "keep_c_min": -8.0,
}


def retract_left(c, A, Y, p):
    w = C.wwin(c, p["full"], p["blend"])
    dA = np.zeros_like(A); dY = np.zeros_like(Y); info = []
    for i in np.nonzero(w > 1e-3)[0]:
        a, y = A[i], Y[i]
        jc = int(np.argmax(y[18:201])) + 18
        ac = a[jc]
        s = S.arclen(a, y)
        k = np.nonzero(a[jc:201] >= ac + p["lip_ahead"])[0]
        if not len(k):
            continue
        j1 = jc + int(k[0])
        # 外の面が頂の a + lip_ahead を越える所の弧長（列の間は直線で補う）
        t = (ac + p["lip_ahead"] - a[j1 - 1]) / max(a[j1] - a[j1 - 1], 1e-9)
        s_t = s[j1 - 1] + t * (s[j1] - s[j1 - 1])
        cut = max(s[200] - s_t, 0.0) * w[i]
        if cut < 0.05:
            continue
        a2, y2, inf = O.shorten_row(a, y, cut, p["shorten"])
        g = float(C.ss(min(cut / 0.6, 1.0)))       # 小さく切る行は並べ直しの差もならす（行の向きに段を作らない）
        dA[i] = g * (a2 - a); dY[i] = g * (y2 - y)
        info.append({"row": int(i), "c": round(float(c[i]), 2), "cut_m": round(cut, 2), "lip_before_m": round(float(a[jc:201].max() - ac), 2)})
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    return A + dA, Y + dY, info


def crest2_table(p):
    """② の頂の線：原画の ② の爪の上の縁の画素の射線の、カメラから d2 m の点（a, y, c）。c の順。"""
    pts = np.array([C.ray_point(x, y, p["d2"]) for x, y in p["crest_px"]])
    return pts[np.argsort(pts[:, 2])]


def catmull(P, n_per=60):
    """点の並び P (k, 2) を通る中心 Catmull–Rom（α = 0.5）の折れ線。"""
    P = np.asarray(P, float)
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        t0 = 0.0
        t1 = t0 + np.linalg.norm(p1 - p0) ** 0.5 + 1e-9
        t2 = t1 + np.linalg.norm(p2 - p1) ** 0.5 + 1e-9
        t3 = t2 + np.linalg.norm(p3 - p2) ** 0.5 + 1e-9
        t = np.linspace(t1, t2, n_per, endpoint=False)[:, None]
        A1 = (t1 - t) / (t1 - t0) * p0 + (t - t0) / (t1 - t0) * p1
        A2 = (t2 - t) / (t2 - t1) * p1 + (t - t1) / (t2 - t1) * p2
        A3 = (t3 - t) / (t3 - t2) * p2 + (t - t2) / (t3 - t2) * p3
        B1 = (t2 - t) / (t2 - t0) * A1 + (t - t0) / (t2 - t0) * A2
        B2 = (t3 - t) / (t3 - t1) * A2 + (t - t1) / (t3 - t1) * A3
        out.append((t2 - t) / (t2 - t1) * B1 + (t - t1) / (t2 - t1) * B2)
    out.append(P[-1][None])
    return np.vstack(out)


def place(a, y, j0, j1, curve):
    """列 j0..j1 を curve の上へ、元の弧長の割合と一様の割合の半々で並べる。"""
    s0 = S.arclen(a[j0:j1 + 1], y[j0:j1 + 1])
    f = 0.5 * s0 / max(s0[-1], 1e-9) + 0.5 * np.linspace(0, 1, j1 - j0 + 1)
    sl = S.arclen(curve[:, 0], curve[:, 1])
    return np.interp(f * sl[-1], sl, curve[:, 0]), np.interp(f * sl[-1], sl, curve[:, 1])


def step2(c, A, Y, p):
    tab = crest2_table(p)
    w = C.wwin(c, p["full"], p["blend"])
    dA = np.zeros_like(A); dY = np.zeros_like(Y); info = []
    J0, JJ = p["J0"], p["Jjoin"]
    for i in np.nonzero(w > 1e-3)[0]:
        a, y = A[i].copy(), Y[i].copy()
        a2 = float(np.interp(c[i], tab[:, 2], tab[:, 0]))
        y2 = float(np.interp(c[i], tab[:, 2], tab[:, 1]))
        # 表の左右の外は端の値（左の端は高さを少し下げる）
        if c[i] < tab[0, 2]:
            y2 -= 0.6 * (tab[0, 2] - c[i])
        # 右の端の窪み（② の頂の線を c dip_c で dip_y·H0 まで下げる）：② の頂から右（① の側）へ行く道の最も高い鞍を、
        # 後ろの溝より低くする（② の鍵の鞍を後ろの溝にする。L1-2・L2-2）。原画視点では S8 の輪の下の縁よりさらに下へ写る
        if "dip" in p:
            d0, d1, dy = p["dip"]
            t = C.ss((c[i] - d0) / max(d1 - d0, 1e-6))
            y2 = y2 + t * (min(dy * C.H0, y2) - y2)
        ar, yr = a[J0], y[J0]
        ag = ar + p["groove_frac"] * (a2 - ar)
        yg = y2 - p["groove_m"]
        # 背の頂の側の始まりの向きを保つ：列 J0 の少し前の点を 1 つ足す
        tdir = np.array([a[J0 + 2] - a[J0 - 2], y[J0 + 2] - y[J0 - 2]]); tdir /= max(np.linalg.norm(tdir), 1e-9)
        p_r1 = np.array([ar, yr]) + tdir * 0.35 * max(ag - ar, 0.4)
        lf = np.array([a2 + p["lip_front"][0], y2 + p["lip_front"][1]])
        outer = catmull([[ar, yr], p_r1, [ag, yg], [a2, y2], lf], 80)
        und = [lf] + [[a2 + d, y2 + h] for d, h in p["under"]]
        # 元の面のつなぎ（列 JJ とその先の向き）
        pj = np.array([a[JJ], y[JJ]]); pj1 = np.array([a[JJ + 6], y[JJ + 6]])
        under = catmull(und + [list(pj - 0.0 * (pj1 - pj)), list(pj1)], 80)
        # under の最後（pj1）は使わず、pj までで切る
        k = int(np.argmin(np.hypot(under[:, 0] - pj[0], under[:, 1] - pj[1])))
        under = under[:k + 1]
        na1, ny1 = place(a, y, J0, 200, outer)
        na2, ny2 = place(a, y, 200, JJ, under)
        an = a.copy(); yn = y.copy()
        an[J0:201] = na1; yn[J0:201] = ny1
        an[200:JJ + 1] = na2; yn[200:JJ + 1] = ny2
        dA[i] = w[i] * (an - a); dY[i] = w[i] * (yn - y)
        info.append({"row": int(i), "c": round(float(c[i]), 2), "w": round(float(w[i]), 3), "crest2": [round(a2, 2), round(y2 / C.H0, 3)],
                     "ridge": [round(float(ar), 2), round(float(yr / C.H0), 3)], "groove": [round(float(ag), 2), round(float(yg / C.H0), 3)]})
    sig = p.get("sigma_rows", 0)
    if sig > 0:
        dA = gaussian_filter1d(dA, sig, axis=0, mode="nearest"); dY = gaussian_filter1d(dY, sig, axis=0, mode="nearest")
    return A + dA, Y + dY, info, tab


def build(design):
    c, A, Y = S.load_rows(C.ROWS04F)
    A0, Y0 = A.copy(), Y.copy()
    log = {}
    A, Y, log["lip"] = retract_left(c, A, Y, design["lip"])
    A, Y, log["step2"], tab = step2(c, A, Y, design["step2"])
    log["crest2_table_aYc"] = [[round(float(v), 3) for v in r] for r in tab]
    keep = c >= design["keep_c_min"]
    A[keep] = A0[keep]; Y[keep] = Y0[keep]
    for M, M0 in ((A, A0), (Y, Y0)):
        M[0] = M0[0]; M[-1] = M0[-1]; M[:, 0] = M0[:, 0]; M[:, -1] = M0[:, -1]
    log["K_top_max_disp_m"] = round(float(np.max(np.hypot(A[keep] - A0[keep], Y[keep] - Y0[keep]))), 4)
    return c, A, Y, log


def main():
    design = DESIGN
    if len(sys.argv) > 1:
        design = json.load(open(sys.argv[1], encoding="utf-8"))
    t0 = time.time()
    c, A, Y, log = build(design)
    os.makedirs(os.path.dirname(C.CAND), exist_ok=True)
    C.jdump(C.OUT + "/hero/design_AS05A.json", design)
    prov = {"route": "美術の見本05 のやり方 A Tools/GWWaveGen/as05/shapeA_hero.py（numpy、行の断面の作り直し：左の唇を引っ込め、② の縁の頂と溝）",
            "base": "K*′ AS04F (%s, sha256 %s)" % (C.ROWS04F.replace(C.REPO + "/", ""), C.sha(C.ROWS04F)),
            "design": design, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
    C.K.write_candidate(C.CAND, c, A, Y, prov)
    C.jdump(C.CAND + "_build_log.json", {"design": design, "log": log, "seconds": round(time.time() - t0, 1)})
    print("SHAPEA_HERO_DONE", C.CAND, log["K_top_max_disp_m"], round(time.time() - t0, 1))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
