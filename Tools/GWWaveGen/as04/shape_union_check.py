# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：主役波 AS04 と、別の作業の青い波（wave4、④ を作る）を原画視点で重ねた時の確かめ（読むだけ。青い波は変えない）。

- 原画視点の z バッファで、主役波だけ・青い波だけ・両方を描き、
  (1) 輪郭 78 の真値の点から、合わせた形（主役波 ∪ 青い波）の空との境までの距離（表示の画素。x < 360 と x ≥ 360 に分ける）、
  (2) 青い波が主役波より手前に出る画素の数（主役波の上に青い波が見える所。④ の外で出ていれば、青い波が主役波を隠している）、
  (3) 主役波の頂の線の上（c −22〜−10）で、青い波の頂が主役波の頂より高く、かつ前（+a）にある所の数（後ろ 65° などで二つ目の山・鰭に見えうる所）
  を数える。
使い方：py -3.10 -B shape_union_check.py <wave4.json> <out.json>
"""
import json
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402


def load_static(js):
    meta = json.load(open(js, encoding="utf-8"))
    n = meta["vertices"]
    raw = np.fromfile(os.path.join(os.path.dirname(js), meta["bin"]), np.float32)
    off = 0
    ch = {}
    for nm, k in meta["channels"]:
        ch[nm] = raw[off:off + n * k].reshape(n, k).astype(np.float64); off += n * k
    tris = raw[off:].view(np.uint32).reshape(-1, 3).astype(np.int64)
    return ch["position"], tris, meta


def main():
    wjs, out = sys.argv[1], sys.argv[2]
    Pw, Tw, meta = load_static(wjs)
    z = np.load(S.OUT + "/final/cand/kstarAS04_a45_rows.npz")
    c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    cam = S.paint_cam()
    X = S.world(c, A, Y)
    idh, zh, T = S.zbuf(cam, X, S.J_B, 394)
    idw, zw = S.U.raster(cam, Pw[Tw], np.arange(1, len(Tw) + 1))
    hero = idh > 0; wave = idw > 0
    union = hero | wave
    wave_front = wave & (~hero | (zw > zh))           # 1/z が大きい ＝ 近い
    env = json.load(open(S.REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json", encoding="utf-8"))
    P78 = np.array([s["points_ref"] for s in env["segments"] if s["id"] == "78"][0], float)
    D = S.ref_to_disp(P78)

    def edge_dist(cov):
        e = np.zeros_like(cov)
        e[1:, :] |= cov[1:, :] != cov[:-1, :]; e[:, 1:] |= cov[:, 1:] != cov[:, :-1]
        ys, xs = np.nonzero(e)
        d, _ = cKDTree(np.c_[xs, ys].astype(float)).query(D)
        return d
    res = {"wave4_mesh": wjs, "wave4_sha256": S.sha(os.path.join(os.path.dirname(wjs), meta["bin"])), "hero_rows_sha256": S.sha(S.OUT + "/final/cand/kstarAS04_a45_rows.npz")}
    for lab, cov in (("hero_only", hero), ("union", union)):
        d = edge_dist(cov)
        m4 = P78[:, 0] < 360
        res["outline78_" + lab] = {"x_lt_360": {"max": S.rnd(d[m4].max()), "p95": S.rnd(np.percentile(d[m4], 95))},
                                   "x_ge_360": {"max": S.rnd(d[~m4].max()), "p95": S.rnd(np.percentile(d[~m4], 95))}}
    # 青い波が主役波の上（手前）に見える画素：④ の多角形（表示）の中と外
    m4 = np.zeros(hero.shape, np.uint8)
    cv2.fillPoly(m4, [np.round(S.ref_to_disp(np.array(S.REG4, float))).astype(np.int32)], 1)
    wf_on_hero = wave_front & hero
    res["wave4_in_front_of_hero_px"] = {"inside_region4": int((wf_on_hero & (m4 > 0)).sum()), "outside_region4": int((wf_on_hero & (m4 == 0)).sum())}
    res["wave4_visible_px"] = int((wave & ~hero).sum() + wf_on_hero.sum())
    # 3D：c −22〜−10 で青い波の頂（各 c の帯の最も高い点）が主役波の頂より高い所
    sw = S.sec(Pw)
    rows = []
    Hh = Y[:, S.J_B:S.J_TIP + 1].max(1)
    for c0 in np.arange(-24.0, -9.9, 1.0):
        m = np.abs(sw[:, 2] - c0) < 0.5
        if not m.any():
            continue
        k = np.argmax(sw[m, 1]); yw = sw[m, 1][k]; aw = sw[m, 0][k]
        i = int(np.argmin(np.abs(c - c0))); jt = S.J_B + int(np.argmax(Y[i, S.J_B:S.J_TIP + 1]))
        rows.append({"c": float(c0), "wave4_crest_y": S.rnd(yw, 2), "wave4_crest_a": S.rnd(aw, 2), "hero_crest_y": S.rnd(Hh[i], 2), "hero_crest_a": S.rnd(A[i, jt], 2),
                     "wave4_higher_m": S.rnd(yw - Hh[i], 2), "wave4_in_front_m": S.rnd(aw - A[i, jt], 2)})
    res["crest_compare_by_c"] = rows
    S.jdump(out, res)
    print(json.dumps({k: v for k, v in res.items() if k != "crest_compare_by_c"}, ensure_ascii=False))
    for r in rows:
        print(r)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
