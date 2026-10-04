# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S2（原画の波頭の解剖）：原画 DP130155 の画素と、t* の主役波 K*' AS02C の面の点を結ぶ表を作る（測るためだけ）。

- 原画のカメラ（PaintingCam v1）を、原画の画素 1 つ ＝ 描画の画素 1 つの細かさ（表示の 1/A_DISP 倍）で、原画の左上の範囲
  （原画の x 0..W、y 0..H）に当てた z バッファを作り、画素ごとに最初に当たる面（主役波の本体／近い海）の点を求める。
- 画素ごとに：面（1 主役波・2 近い海・0 なし）、主役波のシートの (r, c)、深さ [m]、|n·v|、見本02 の面の座標 u・w [m]
  （attr_pin の s01_param、u は巻きの向きの弧長、w は頂に並ぶ向き）、世界の xyz。
- 原画の色は面へ写さない（Q28）。この表は、原画の上で測った長さ・数を、主役波の上の m へ直すためだけに使う。生成器はこの表を読まない。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as03/s2_map.py
出力（Git 対象外）：Unity/Build/Polish/sample03/study/tmp/s2_map.npz
"""
import json
import os
import sys
import time

import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402

U = CC.U
B = REPO + "/Unity/Build/Polish/sample02/fix01/assemble"
HERO = B + "/hero_pkg_AS02C"
PARAM = B + "/attr_pin/s01_param_f32.bin"
SEA_NEAR = REPO + "/Unity/Build/Polish/30/sea/near/ds30_tstar.gwb"
OUT = REPO + "/Unity/Build/Polish/sample03/study/tmp/s2_map.npz"
QW, QH = 2450, 2594          # 原画の画素の範囲（x 0..QW、y 0..QH。高さは原画の全部）


def main():
    t0 = time.time()
    CC.HERO = HERO
    X0 = CC.load_hero()
    hero = CC.Hero(X0)
    R, C = hero.R, hero.C
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/kstar_h")
    import kh_common as K
    g = K.read_gwb(SEA_NEAR)
    sV, sF = g["X"], g["tris"].astype(np.int64)
    cam0 = CC.painting_cam()
    A = U.A_DISP
    offx = 156.66152659984573
    # 原画の画素 (qx, qy) → 描画の画素 (qx, qy)：CropCam(x0 = offx, y0 = 0, s = 1/A)
    cam = U.CropCam(cam0, offx, 0.0, 1.0 / A, QW, QH)
    tri_h = hero.V[hero.Tg]
    tri_s = sV[sF]
    nh = len(hero.Tg)
    idb, zb = U.raster(cam, np.concatenate([tri_h, tri_s]), np.arange(1, nh + len(sF) + 1))
    print("raster", time.time() - t0, flush=True)
    del zb
    surf = np.zeros((QH, QW), np.uint8)
    rr = np.full((QH, QW), np.nan, np.float32)
    cc = np.full((QH, QW), np.nan, np.float32)
    dep = np.full((QH, QW), np.nan, np.float32)
    ndv = np.full((QH, QW), np.nan, np.float32)
    P3 = np.full((QH, QW, 3), np.nan, np.float32)
    ys, xs = np.nonzero(idb > 0)
    par = np.fromfile(PARAM, np.float32).reshape(R, C, 8)
    uu = np.full((QH, QW), np.nan, np.float32)
    ww = np.full((QH, QW), np.nan, np.float32)
    step = 400_000
    for s0 in range(0, len(ys), step):
        y = ys[s0:s0 + step]; x = xs[s0:s0 + step]
        t = idb[y, x].astype(np.int64) - 1
        d = cam.ray(x.astype(np.float64), y.astype(np.float64))
        ish = t < nh
        # 主役波
        if ish.any():
            th = t[ish]
            tv = hero.V[hero.Tg[th]]
            s_, u_, v_ = U.ray_tri_many(cam.pos, d[ish], tv[:, 0], tv[:, 1], tv[:, 2])
            r_, c_ = U.tri_to_rc(th, u_, v_, hero.b1 - hero.b0, hero.b0)
            P = cam.pos + s_[:, None] * d[ish]
            n = U.normal_at(hero.X, r_, c_)
            yy, xx = y[ish], x[ish]
            surf[yy, xx] = 1
            rr[yy, xx] = r_; cc[yy, xx] = c_
            dep[yy, xx] = (P - cam.pos) @ cam.f
            ndv[yy, xx] = np.abs((n * d[ish]).sum(-1))
            P3[yy, xx] = P
            # 面の座標 u・w（シートの双線形）
            q = U.bilin(par[..., :2].astype(np.float64), r_, c_)
            uu[yy, xx] = q[:, 0]; ww[yy, xx] = q[:, 1]
        iss = ~ish
        if iss.any():
            ts = t[iss] - nh
            tv = sV[sF[ts]]
            s_, u_, v_ = U.ray_tri_many(cam.pos, d[iss], tv[:, 0], tv[:, 1], tv[:, 2])
            P = cam.pos + s_[:, None] * d[iss]
            nn = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
            nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-12)
            yy, xx = y[iss], x[iss]
            surf[yy, xx] = 2
            dep[yy, xx] = (P - cam.pos) @ cam.f
            ndv[yy, xx] = np.abs((nn * d[iss]).sum(-1))
            P3[yy, xx] = P
    del idb
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    np.savez_compressed(OUT, surf=surf, r=rr, c=cc, depth=dep, ndv=ndv, P=P3, u=uu, w=ww,
                        meta=json.dumps(dict(QW=QW, QH=QH, A_DISP=A, offx=offx, hero=HERO, param=PARAM, sea=SEA_NEAR,
                                             hero_rows=R, hero_cols=C, body=[hero.b0, hero.b1],
                                             fov_deg=26.0, px_rad=float(2 * cam0.t / cam0.H * A))))
    print("hero px", int((surf == 1).sum()), "sea px", int((surf == 2).sum()), "s", round(time.time() - t0, 1), flush=True)


if __name__ == "__main__":
    main()
