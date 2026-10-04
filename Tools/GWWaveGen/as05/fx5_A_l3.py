# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：③ 最左側の小区域を、主役波の左前の別の小さな砕け波（静止のメッシュ layer3）として numpy で作る。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_l3.py

形（断面の座標 a・y・c。参照モデル・写真は読まない。原画のカメラは頂を置く射線にだけ使う）：
1. 頂の線：原画の ③ の爪の群れの上の縁（原画の画素 x 0〜630、y 1075〜1120、進行役の読み）の射線の上、原画のカメラから D3 m。
   画の左の外（c < c0）は頂を余弦で下げて C_L で海へ、右（c > c1）は Hermite で C_R で 0 へ（② の行へは届かない）。
2. 断面：頂の高さ Yc で縮む型（前：頂 → 短い唇 → 唇の下で後ろへ返る小さな巻き（引っ込み）→ 下の面 → 谷の海の下。
   後ろ：頂 → 鞍（0.65·Yc、主役波の短くした唇の鼻との間の 55 %）→ 主役波の鼻の上の高さへ上がって、主役波の肩の面の下へ降りる）。
3. 地面の上に載せる（wave4 と同じ w4_common.softmax_above、eps 6 cm・k 0.8 m）。地面 = 主役波 AS05A の一番上の面と近い海。
   3 頂点ともちょうど地面 + eps の三角形は捨てる（主役波・海と交わらない、縁は地面の 6 cm 上）。
属性（AS04 Flat Smooth、Build/Polish/sample04/mat/README.md の 3 節の約束、_AS03Src 1）：u = 断面の上の頂からの弧長（前 +）、w = c、
F = 2 + 2u/15、hrow = Yc/H0、q = u/λ（前）・w/λ（背）、λ = 0.045 H0、whiteOn 1。whiteSD：頂の白の帯（u WB0〜WB1）だけ白（+）、ほかは藍（−）。
層の印：頂点の属性とは別に、頂点ごとの int（3）を layer3_labels.npy に書く。
直しの回 fix1（fx5_A_l3.py）：shapeA_l3.py（変えない）の写し。白の帯を c ≥ TAIL_C（既定 −21 m、TAIL_W m でなめらかに）の行だけにした
  （批評の A1：③ の頂の線が c −21〜−24 で 0.35 → 0 H0 へ下がる尾の白が、原画の枠の左の外へ白い鎌として長く出ていた）。
  右の端（c > RIGHT_C、② の唇の下へ潜る所）の白も外す（原画視点で ③ の白が ② の白と一本の横の帯につながったため）。fx5_A_run.py から呼ぶ。
出力（元、Git 対象外）：Unity/Build/Polish/sample05/shapeA/l3/layer3.json/.bin、layer3_grid.npz、layer3_labels.npy、layer3_build_report.json
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402
import w4_common as W  # noqa: E402

K = C.K
D3 = 41.5                           # 原画のカメラから ③ の頂までの距離（m）。② の頂（48.5 m）より 7 m 手前（L4-23）
CREST_PX = [(0, 1190), (25, 1120), (70, 1090), (120, 1080), (230, 1080), (380, 1090), (500, 1108), (600, 1118), (630, 1122)]
C_L, C_R = -23.6, -14.4
BEHIND, SINK = 2.2, 1.4
DIP_Y, DIP_T = 0.325, 0.55   # 右の端の鞍：高さ 0.325 H0、巻き戻しの 55 % の所   # 右の端：頂を主役波の鼻の a − BEHIND、鼻の高さ − SINK へ（唇の下へ潜る）
WRAP = 2.6        # 右の端（c > c1）で頂の線を後ろ（−a）へ巻き戻す傾き（m/m）。主役波の鼻へ近づいて、肩と一続きになる
LAM = 0.045 * C.H0
EPS, KS = 0.06, 0.8
# 断面の型（頂の高さ YREF のとき、m）。d = a − 頂の a。前の巻きの部分。後ろの部分は行ごとに主役波の鼻まで作る（back_profile）
YREF = 8.6
FRONT = [(0.0, 8.6), (0.65, 8.5), (1.25, 8.2), (1.6, 7.85), (1.55, 7.4), (1.15, 6.95), (0.55, 6.6), (-0.15, 6.2), (-0.5, 5.5),
         (-0.65, 4.7), (-0.6, 3.8), (-0.4, 3.0), (-0.15, 2.45), (0.45, 1.95), (1.5, 1.4), (2.7, 0.7), (3.9, 0.05), (4.9, -0.5), (5.7, -0.9)]
TAIL_C, TAIL_W = -21.0, 0.8           # 直しの回 fix1：白の帯は c ≥ TAIL_C だけ（TAIL_W m でなめらかに 0 へ）
RIGHT_C = float(os.environ.get("FX5_L3_RIGHT_C", "-16.0"))   # 直しの回 fix1：右の端（② の唇の下へ潜る所）の白も外す（c ≤ RIGHT_C、TAIL_W m でなめらかに）。② の白と原画視点でつながらないように
WB = (-1.7, 2.35)                   # 白の帯の u（m）：背の側 −1.7 m から、唇を回って唇の下 2.35 m まで


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def crest_line():
    pts = np.array([C.ray_point(x, y, D3) for x, y in CREST_PX])     # (a, y, c)
    o = np.argsort(pts[:, 2])
    return pts[o]


class Crest:
    """頂の線 a_c(c)・Yc(c) と、唇の巻きの大きさ rc(c)。画の中は原画の射線の点（a は 2 次でならし、Yc は点を結んでならす）。
    左（c < c0）は頂を余弦で C_L で 0 へ。右（c > c1）は頂の線を主役波の鼻の後ろ（鼻の a − BEHIND）へ巻き戻し、頂を鼻の高さ − SINK まで下げて、
    主役波の短くした唇の下へ潜らせる（右の端を縦の壁で切らない）。"""

    def __init__(self, pts, nose_c, nose_a, nose_y):
        self.c_in, self.a_in, self.y_in = pts[:, 2], pts[:, 0], pts[:, 1]
        self.c0, self.c1 = float(self.c_in[0]), float(self.c_in[-1])
        self.pa = np.polyfit(self.c_in, self.a_in, 2)
        self.nc, self.na, self.ny = nose_c, nose_a, nose_y

    def _in(self, c):
        cc = np.clip(c, self.c0, self.c1)
        a = np.polyval(self.pa, cc)
        y = np.interp(cc, self.c_in, self.y_in)
        return a, y

    def a_c(self, c):
        c = np.asarray(c, float)
        a, _ = self._in(c)
        a0 = np.polyval(self.pa, self.c0); da0 = np.polyval(np.polyder(self.pa), self.c0)
        a = np.where(c < self.c0, a0 - da0 * 0.8 * (1 - np.exp(-(self.c0 - c) / 0.8)), a)
        a1 = np.polyval(self.pa, self.c1); da1 = np.polyval(np.polyder(self.pa), self.c1)
        aend = float(np.interp(C_R, self.nc, self.na)) - BEHIND
        L = C_R - self.c1
        t = np.clip((c - self.c1) / L, 0, 1)
        ah = a1 * (2 * t ** 3 - 3 * t ** 2 + 1) + da1 * L * (t ** 3 - 2 * t ** 2 + t) + aend * (-2 * t ** 3 + 3 * t ** 2)
        return np.where(c > self.c1, ah, a)

    def Yc(self, c):
        c = np.asarray(c, float)
        _, y = self._in(c)
        y0 = float(self.y_in[0]); y1 = float(self.y_in[-1])
        t = (c - C_L) / (self.c0 - C_L)
        y = np.where(c < self.c0, y0 * (0.5 - 0.5 * np.cos(np.pi * np.clip(t, 0, 1))), y)
        yend = float(np.interp(C_R, self.nc, self.ny)) - SINK
        # 右の端：頂の線を巻き戻しながら鞍（DIP_Y·H0、巻き戻しの DIP_T の所）まで下げ、その先で主役波の鼻の下へ上がって潜る。
        # ③ の頂から主役波へ行く道の最も高い鞍をここに置く（③ の峰の突出 L1-3 と、鞍が頂より後ろ L2-3）
        tt = np.clip((c - self.c1) / (C_R - self.c1), 0, 1)
        ydip = DIP_Y * C.H0
        y_a = y1 + (ydip - y1) * smooth(tt / DIP_T)
        y_b = ydip + (yend - ydip) * smooth((tt - DIP_T) / (1 - DIP_T))
        y = np.where(c > self.c1, np.where(tt < DIP_T, y_a, y_b), y)
        return np.maximum(y, 0.0)

    def rc(self, c):
        """唇の巻きの大きさ（型の倍率）：画の中 1、左は頂と同じ割合、右の端で 0.45 へ。"""
        c = np.asarray(c, float)
        r = np.ones_like(c)
        r = np.where(c < self.c0, np.clip(self.Yc(c) / max(float(self.y_in[0]), 1e-3), 0, 1), r)
        r = np.where(c > self.c1, 1 - 0.55 * smooth((c - self.c1) / (C_R - self.c1)), r)
        return r


def hero_nose(rows_path):
    """行ごとの主役波の唇の先（列 95〜200 で a が最大の点）の a・y と、頂の a・y。"""
    c, A, Y = C.SC.load_rows(rows_path)
    j = np.argmax(A[:, 95:201], 1) + 95
    r = np.arange(len(c))
    jc = np.argmax(Y[:, 18:201], 1) + 18
    return c, A[r, j], Y[r, j], A[r, jc], Y[r, jc]


def resample_poly(P, n):
    P = np.asarray(P, float)
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])], -1)


def section(yc, ac, nose_a, nose_y, rc=1.0, n_back=70, n_front=110):
    """1 行の断面（a, y）。前の型は、唇の巻き（頂から下 YREF − 2.45 m まで）を r = rc·yc/YREF で縮め、その下の面は
    巻きの下の端から海の下（−0.9 m）までを高さの比で並べる。後ろは 頂 → 鞍 → 主役波の鼻の上 → 肩の下（地面の下）。"""
    r = max(rc * min(yc / YREF, 1.0) if rc < 1 else yc / YREF, 1e-3)
    Ft = np.array(FRONT)
    F = np.zeros_like(Ft)
    curl = Ft[:, 1] >= 2.45
    F[curl, 0] = Ft[curl, 0] * r
    F[curl, 1] = yc + (Ft[curl, 1] - YREF) * r
    yub = yc + (2.45 - YREF) * r
    low = ~curl
    F[low, 0] = Ft[low, 0] * max(r, 0.35)
    F[low, 1] = -0.9 + (Ft[low, 1] + 0.9) / (2.45 + 0.9) * (yub + 0.9)
    g = max(ac - nose_a, 2.5)                     # ③ の頂と主役波の鼻の間（m）
    ys = 0.65 * yc                                 # 鞍の高さ
    yn = max(min(nose_y - 0.3, yc * 1.3), ys + 0.3)  # 主役波の鼻の高さの 0.3 m 下まで上がる（鼻の上へかぶさらない。鼻が低い行では頂の 1.3 倍まで）
    back = [(-0.0, yc), (-0.45 * g * 0.5, yc - 0.18 * (yc - ys)), (-0.55 * g, ys), (-0.8 * g, ys + 0.45 * (yn - ys)),
            (-1.0 * g, yn), (-1.0 * g - 1.5, yn - 0.6), (-1.0 * g - 3.0, yn - 2.0)]
    back = [(ac + d, y) for d, y in back][::-1]
    front = [(ac + d, y) for d, y in F]
    import shapeA_hero as H
    cb = H.catmull(back, 40)
    cf = H.catmull(front, 40)
    pb = resample_poly(cb, n_back)
    pf = resample_poly(cf, n_front)
    P = np.vstack([pb[:-1], pf])
    return P, n_back - 1


def build(rows_path=None, nr=397):
    rows_path = rows_path or C.ROWS05A
    ground = W.Ground(rows_path)
    pts = crest_line()
    hc, nose_a, nose_y, hca, hcy = hero_nose(rows_path)
    cr = Crest(pts, hc, nose_a, nose_y)
    cs = np.linspace(C_L, C_R, nr)
    ac = cr.a_c(cs); yc = cr.Yc(cs)
    na = np.interp(cs, hc, nose_a); ny = np.interp(cs, hc, nose_y)
    rcs = cr.rc(cs)
    secs = []
    for i in range(nr):
        P, j0 = section(max(yc[i], 0.05), ac[i], na[i], ny[i], float(rcs[i]))
        secs.append(P)
    Aw = np.stack([s[:, 0] for s in secs]); Yw = np.stack([s[:, 1] for s in secs])
    # 左右の端の行（頂が 0.4 m より低い）は海の下へ
    low = yc < 0.4
    Yw[low] = -0.6
    Cg = np.broadcast_to(cs[:, None], Aw.shape)
    G = ground(Aw.ravel(), Cg.ravel()).reshape(Aw.shape)
    Yf = W.softmax_above(Yw, G, EPS, KS)
    return dict(c=cs, A=Aw, Yw=Yw, G=G, Y=Yf, ac=ac, yc=yc, j0=j0, nose_a=na, nose_y=ny, crest_pts=pts, cr=cr)


def mesh_from_grid(g):
    nr, ncol = g["A"].shape
    tri = K.triangles(ncol, nr).astype(np.int64)
    x = (g["Yw"] - g["G"] - EPS).ravel()
    keep = (x > -KS)[tri].any(1)
    # 主役波の鼻（唇の先）の崖で、地面へ貼り付いた頂点と浮いた頂点が 1 m 以上の段でつながる三角形は捨てる
    # （第 6 版の回り台 0°・300° で、鼻の下に垂れる細い幕＝つららに見えた）。捨てた所は鼻の張り出しの下に隠れる縁になる
    Yv = g["Y"].ravel()
    snapped = (x <= -KS)[tri]
    dy = Yv[tri].max(1) - Yv[tri].min(1)
    keep &= ~(snapped.any(1) & (dy > 1.0))
    tri = tri[keep]
    used = np.unique(tri)
    remap = -np.ones(nr * ncol, np.int64)
    remap[used] = np.arange(len(used))
    P = K.world(g["c"], g["A"], g["Y"]).reshape(-1, 3)
    return P, tri, used, remap


def attributes(g):
    nr, ncol = g["A"].shape
    A, Y = g["A"], g["Y"]
    j0 = g["j0"]
    seg = np.hypot(np.diff(A, axis=1), np.diff(Y, axis=1))
    s = np.concatenate([np.zeros((nr, 1)), np.cumsum(seg, 1)], 1)
    u = s - s[:, j0:j0 + 1]
    wv = np.broadcast_to(g["c"][:, None], (nr, ncol))
    F = np.clip(2.0 + 2.0 * u / 15.0, -0.5, 4.5)
    hrow = np.broadcast_to((g["yc"] / C.H0)[:, None], (nr, ncol))
    q = wv / LAM          # 帯は c 一定の線（頂から谷へ流れる筋。主役波の前の面の帯と同じ向き）。見本05 の第 1 版の u/λ（頂に平行な横の筋）は段の重なりに見えた
    # 白の帯：頂の高さで帯の長さを縮める（端の低い所で消える）
    r = np.clip(g["yc"] / YREF, 0, 1)[:, None]
    r = r * smooth((g["c"][:, None] - (TAIL_C - TAIL_W)) / TAIL_W)      # 直しの回 fix1：尾（c < TAIL_C）の白を外す
    r = r * smooth(((RIGHT_C + TAIL_W) - g["c"][:, None]) / TAIL_W)     # 直しの回 fix1：右の端（c > RIGHT_C）の白を外す
    wb0, wb1 = WB[0] * r, WB[1] * r
    dd = np.minimum(u - wb0, wb1 - u)                 # 帯の中で +（境からの距離）
    wsd = np.where(dd >= 0, dd, np.maximum(dd, -2.0))
    wsd = np.where(r > 0.25, wsd, -np.abs(wsd) - 0.05)
    return dict(u=u, w=wv, F=F, hrow=hrow, q=q, wsd=wsd)


def channels(g, at, used, normals):
    def f(x):
        return np.asarray(x, np.float64).ravel()[used]
    n = len(used)
    hrel = f(g["Y"] / np.maximum(g["yc"][:, None], 1e-3))
    return {"position": None, "normal": normals, "tangent": np.tile(np.array([[0, 0, 0, 1.0]]), (n, 1)),
            "uv3": np.stack([f(at["F"]), hrel, f(at["u"]), f(at["w"])], -1),
            "uv4": np.stack([np.full(n, 1.0 / LAM), f(at["hrow"]), np.zeros(n), f(at["q"])], -1),
            "uv5": np.stack([np.ones(n), np.ones(n), f(at["wsd"]), np.zeros(n)], -1),
            "uv6": np.stack([np.full(n, 254.0), np.full(n, 4094.0), np.full(n, LAM), np.ones(n)], -1)}


def main():
    out = C.OUT + "/l3"
    os.makedirs(out, exist_ok=True)
    g = build()
    P, tri_all, used, remap = mesh_from_grid(g)
    at = attributes(g)
    tri = remap[tri_all]
    Pv = P[used]
    nrm = W.vertex_normals(Pv, tri)
    ch = channels(g, at, used, nrm)
    ch["position"] = Pv
    h = W.write_static(out + "/layer3.json", ch, tri, {"note_ja": "見本05 やり方 A：③ 最左側の小区域の別の小さな砕け波（layer3）。AS04 Flat Smooth の属性（_AS03Src 1）。",
                                                       "hero_rows": C.ROWS05A, "hero_rows_sha256": C.sha(C.ROWS05A)})
    np.save(out + "/layer3_labels.npy", np.full(len(Pv), 3, np.int16))
    np.savez_compressed(out + "/layer3_grid.npz", c=g["c"], A=g["A"], Y=g["Y"], Yw=g["Yw"], G=g["G"], ac=g["ac"], yc=g["yc"], u=at["u"],
                        wsd=at["wsd"], used=used)
    Q = K.sec(Pv)
    gb = W.Ground(C.ROWS05A)(Q[:, 0], Q[:, 2])
    clr = Q[:, 1] - gb
    rep = {"schema": "GreatWave.AS05A.layer3_build/1", "mesh": out + "/layer3.json", "mesh_bin_sha256": h, "vertices": int(len(Pv)),
           "triangles": int(len(tri)), "D3_m": D3, "crest_px_ref": CREST_PX, "front_template_m": FRONT, "YREF_m": YREF, "white_band_u_m": WB, "fix1_white_tail_c_min": [TAIL_C, TAIL_W], "fix1_white_right_c_max": [RIGHT_C, TAIL_W],
           "crest_by_c": {"%.1f" % c: {"a": C.rnd(float(np.interp(c, g["c"], g["ac"]))), "Yc_over_H0": C.rnd(float(np.interp(c, g["c"], g["yc"])) / C.H0),
                                       "hero_nose_a": C.rnd(float(np.interp(c, g["c"], g["nose_a"]))), "hero_nose_y_over_H0": C.rnd(float(np.interp(c, g["c"], g["nose_y"])) / C.H0)}
                          for c in (-24, -23, -22, -21, -20, -19, -18, -17, -16, -15)},
           "clearance_above_ground_m": {"min": C.rnd(float(clr.min()), 4), "p01": C.rnd(float(np.percentile(clr, 1)), 4)},
           "height_max_m": C.rnd(float(Q[:, 1].max())), "a_range": [C.rnd(float(Q[:, 0].min())), C.rnd(float(Q[:, 0].max()))],
           "c_range": [C.rnd(float(Q[:, 2].min())), C.rnd(float(Q[:, 2].max()))],
           "dist_crest_to_painting_cam_m": D3, "reference_model_read_by_generator": False, "photos_read_by_generator": False}
    C.jdump(out + "/layer3_build_report.json", rep)
    print(json.dumps({k: rep[k] for k in ("vertices", "triangles", "clearance_above_ground_m", "height_max_m", "a_range", "c_range", "crest_by_c")}, ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
