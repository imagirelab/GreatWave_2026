# -*- coding: utf-8 -*-
"""R4 の左の輪郭（78・130・131）を作る点を調べる（py -3.10）。
原画視点の上側の包絡（x の 1 px ごとに最も上に写る頂点）を取り、その頂点の行・列・断面座標と、
射線の向きを記録する。出力：r1_rays/analysis/r4_silhouette.json と図。"""
import os
import sys
import json

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rays_common as RC  # noqa: E402


def upper_envelope(c, A, Y, x0=150, x1=780, sub=4):
    """格子を列・行方向に sub 倍で線形に細かくして写し、x の 1 px ごとに最も上（表示 y 最小）の点を返す。"""
    nv, nu = A.shape
    X = RC.world(c, A, Y)
    # 細分（双線形）
    u = np.linspace(0, nu - 1, (nu - 1) * sub + 1)
    v = np.linspace(0, nv - 1, (nv - 1) * sub + 1)
    iu = np.clip(np.floor(u).astype(int), 0, nu - 2); fu = u - iu
    iv = np.clip(np.floor(v).astype(int), 0, nv - 2); fv = v - iv
    out = {}
    best_y = np.full(x1 - x0 + 1, np.inf); best = [None] * (x1 - x0 + 1)
    for k in range(len(v)):
        r0, t = iv[k], fv[k]
        Xr = X[r0] * (1 - t) + X[r0 + 1] * t
        Xs = Xr[iu] * (1 - fu[:, None]) + Xr[iu + 1] * fu[:, None]
        P = RC.project(Xs)
        xi = np.round(P[:, 0]).astype(int)
        m = (xi >= x0) & (xi <= x1) & (P[:, 2] > 0)
        for j in np.nonzero(m)[0]:
            b = xi[j] - x0
            if P[j, 1] < best_y[b]:
                best_y[b] = P[j, 1]; best[b] = (float(v[k]), float(u[j]), Xs[j].tolist())
    for b in range(len(best)):
        if best[b] is not None:
            out[x0 + b] = {"y_px": float(best_y[b]), "row_f": best[b][0], "col_f": best[b][1], "X": best[b][2]}
    return out


def main():
    c, A, Y = RC.load_r4()
    env = upper_envelope(c, A, Y)
    import truthlib  # noqa
    d = json.load(open(os.path.join(RC.REPO, "Tools", "PaintingTruth", "targets", "main_wave_outline_envelope.json"), encoding="utf-8"))
    seg = {s["id"]: np.array(s["points_display"], float) for s in d["segments"]}
    rows = []
    for x, e in sorted(env.items()):
        S = RC.sec(np.array(e["X"]))[0]
        lab = None
        for k in ("78", "130", "131", "132"):
            P = seg[k]
            if P[:, 0].min() <= x <= P[:, 0].max():
                lab = k; ty = float(np.interp(x, P[:, 0], P[:, 1]) if np.all(np.diff(P[:, 0]) >= 0) else P[np.argmin(np.abs(P[:, 0] - x)), 1])
                break
        rd = RC.ray_dir_sec(np.array(e["X"]))
        rows.append({"x": x, "y": e["y_px"], "seg": lab, "truth_y": ty if lab else None, "row_f": e["row_f"], "col_f": e["col_f"],
                     "a": float(S[0]), "yh": float(S[1]), "c": float(S[2]), "ray_sec": rd.tolist()})
    os.makedirs(os.path.join(RC.OUT, "analysis"), exist_ok=True)
    RC.jdump(rows, os.path.join(RC.OUT, "analysis", "r4_silhouette.json"))
    for r in rows[::20]:
        print("x %4d y %7.1f seg %4s truth %s  row %6.1f col %6.1f  a %6.2f y %6.2f c %6.2f  ray(da,dy,dc) %s" % (
            r["x"], r["y"], r["seg"], None if r["truth_y"] is None else round(r["truth_y"], 1), r["row_f"], r["col_f"], r["a"], r["yh"], r["c"],
            np.round(r["ray_sec"], 3)))


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(RC.REPO, "Tools", "PaintingTruth"))
    main()
