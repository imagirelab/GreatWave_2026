# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：新しい主役波 K*′ AS04 の t* の、AS04 Flat Smooth の材質が読む頂点の属性つきの静止のメッシュを作る。

1. 白の境 whiteSD（m、+ が白）を新しい形で作り直す：白と藍の区域は見本03 の白の印 v2（shared/white_mask_f32.bin）を頂点の番号で引き継ぎ
   （格子は AS02C と 1 対 1）、境からの距離だけを新しい面の上で測り直す（格子の辺の長さで Dijkstra。境の辺の上の 0 の点から）。
   唇を短くした所（頂の前の鼻）や左の下げた所で面が縮んでも、帯の始まり・白い点の現れ（−whiteSD で決まる）が面の上の m のまま。
   白の境の細かい帯の格子（white_mask_band）は使わない（形が変わったので、帯の格子の位置が合わない）。
   低い行（頂 < 0.22 H0、左の尾を海へ下ろした所）は白にしない（白の境を頂の高さの差だけ藍の側へ寄せる）。
2. 見本03 の surf_relief.py（変えない）を --flat で呼ぶ。入力のパス（包み・.gwb・meta・行・12 個の属性）だけを AS04 のものへ替える。
   q・gq・Lq・λ・whiteOn はそこで出る（属性の約束は Build/Polish/sample04/mat/README.md）。
使い方：py -3.10 -B Tools/GWWaveGen/as04/shape_mesh.py
出力（Git 対象外）：Build/Polish/sample04/shape/mesh/hero_smooth_as04.bin・.json・_report.json、shape/mesh/white_mask_as04_f32.bin
"""
import json
import os
import sys

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as03")
import surf_common as SC  # noqa: E402
import surf_relief as R  # noqa: E402

SH = REPO + "/Unity/Build/Polish/sample04/shape"
CAND = SH + "/final/cand/kstarAS04_a45"
WM_OLD = REPO + "/Unity/Build/Polish/sample03/shared/white_mask_f32.bin"
NAME = "hero_smooth_as04"
H0 = 20.752853190871733
LOW_H0 = 0.22      # 頂がこれより低い行は白を持たない（0.22 H0 = 4.6 m）
LOW_K = 1.0


def resigned_distance(P, sd_old):
    """格子 P（R×C×3）の上で、sd_old の符号の境（0 の線）からの面の上の距離を測り直し、元の符号を付けて返す。"""
    Rr, Cc = sd_old.shape
    idx = np.arange(Rr * Cc).reshape(Rr, Cc)
    V = P.reshape(-1, 3)
    s = sd_old.reshape(-1)
    pairs = [(idx[:, :-1], idx[:, 1:]), (idx[:-1, :], idx[1:, :]), (idx[:-1, :-1], idx[1:, 1:]), (idx[:-1, 1:], idx[1:, :-1])]
    I = np.concatenate([p[0].ravel() for p in pairs]); J = np.concatenate([p[1].ravel() for p in pairs])
    L = np.linalg.norm(V[I] - V[J], axis=1) + 1e-6
    n = len(s)
    # 境の辺：符号が変わる辺。0 の点の位置は元の値の比で辺の上に置く
    cross = (s[I] > 0) != (s[J] > 0)
    ti = np.abs(s[I[cross]]) / np.maximum(np.abs(s[I[cross]]) + np.abs(s[J[cross]]), 1e-9)
    d0 = np.full(n, np.inf)
    np.minimum.at(d0, I[cross], ti * L[cross])
    np.minimum.at(d0, J[cross], (1 - ti) * L[cross])
    # 仮の始点（番号 n）から境の点へ d0 の辺
    src = np.nonzero(np.isfinite(d0))[0]
    Gi = np.r_[I, J, np.full(len(src), n)]; Gj = np.r_[J, I, src]; Gw = np.r_[L, L, d0[src]]
    G = sp.csr_matrix((Gw, (Gi, Gj)), shape=(n + 1, n + 1))
    dist = dijkstra(G, directed=True, indices=n)[:n]
    dist = np.where(np.isfinite(dist), dist, np.abs(s))
    return (np.where(s > 0, 1.0, -1.0) * dist).reshape(Rr, Cc)


def main():
    meta = json.load(open(CAND + "_meta.json", encoding="utf-8"))
    nr, nc = 240, 400
    # 1. 白の境を新しい面で測り直す
    import ds33_common as U  # noqa: F401  （surf_common が sys.path に入れる）
    SC.HERO_PKG = SH + "/hero_pkg_AS04"
    Pb = SC.load_hero_world()
    sd_old = np.fromfile(WM_OLD, np.float32).astype(np.float64).reshape(nr, nc)
    sd_new = resigned_distance(Pb, sd_old)
    # 低い行（左の尾を海へ下ろした所）は白にしない：行の頂の高さ H(c) が LOW_H0·H0 より低い分だけ、白の境を藍の側へ寄せる
    # （S9：主役波は左へ白い尾を延ばさない。海へ潰した行が白い線として海の上に残らない）
    Hrow = Pb[:, 18:201, 1].max(1)
    cap = (Hrow - LOW_H0 * H0) * LOW_K
    sd_new = np.minimum(sd_new, cap[:, None])
    os.makedirs(SH + "/mesh", exist_ok=True)
    wm = SH + "/mesh/white_mask_as04_f32.bin"
    sd_new.astype(np.float32).tofile(wm)
    wrep = {"source_mask": WM_OLD, "source_sha256": SC.sha(WM_OLD), "out": wm, "out_sha256": SC.sha(wm),
            "white_vertices_same_as_source": bool(((sd_new > 0) == (sd_old > 0)).all()),
            "white_vertices_source_new": [int((sd_old > 0).sum()), int((sd_new > 0).sum())],
            "low_rows_rule": {"LOW_H0": LOW_H0, "LOW_K": LOW_K, "rows_capped": int((cap < sd_new.max()).sum())},
            "abs_change_m": {"p50": float(np.median(np.abs(sd_new - sd_old))), "p99": float(np.percentile(np.abs(sd_new - sd_old), 99))},
            "note_ja": "白・藍の区域は見本03 の白の印 v2 を頂点の番号で引き継ぎ、境からの距離だけを AS04 の面の上で測り直した。"}
    # 2. surf_relief --flat（入力のパスだけ替える）
    SC.GWB = CAND + ".gwb"
    SC.META = CAND + "_meta.json"
    SC.ROWS = CAND + "_rows.npz"
    SC.ATTR = SH + "/attr/a/s01a_hero_attr_v2_f32.bin"
    SC.OUT = SH
    R.S = SC
    sys.argv = ["surf_relief.py", "--name", NAME, "--flat", "--white-mask", wm]
    R.main()
    rep = json.load(open(SH + "/mesh/" + NAME + "_report.json", encoding="utf-8"))
    rep["as04_white_mask"] = wrep
    rep["as04_inputs"] = {"hero_pkg": SC.HERO_PKG, "gwb": SC.GWB, "meta": SC.META, "rows": SC.ROWS, "attr": SC.ATTR}
    with open(SH + "/mesh/" + NAME + "_report.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=float)
    print(json.dumps(wrep, ensure_ascii=False))


if __name__ == "__main__":
    main()
