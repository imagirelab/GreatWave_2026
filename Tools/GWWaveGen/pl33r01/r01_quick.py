# -*- coding: utf-8 -*-
"""仕上げ33修正01 修正の回 1：試しの版ごとの速い数（numpy・OpenCV。記録の補助。本番の数は r01_measure.py と各道具）。

  - 原画視点 t* の律動：一覧の爪の領域（13×13 に太らせた所）と b区域の、白い地の上の水色の版の割合と暗い線（pl33f_measure.py と同じ式）
  - 一覧との重なり：sweep_overlay.measure（再現・精度・中心線の離れと先の伸び）
  - 爪の項目の頂点の高さ（評審 judge_geo と同じ式：全部の列の頂点の法線、接線の離れ 0.3 m 未満、u > 0.3 で 5 cm より下）と、
    加速度 > 0.15 m/コマ² の出来事（根元に対する）
使い方：py -3.10 -B Tools/GWWaveGen/pl33r01/r01_quick.py --run <描画> --claws <爪の並び> [--out <json>] [--no-geo]
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33r01")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
import pl33f_measure as PM  # noqa: E402
import pl32f_measure as M  # noqa: E402
import sweep_overlay as OV  # noqa: E402
import sweep_build as SB  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402


def rhythm(run):
    P = M.paint_disp()
    im = cv2.imread(os.path.join(run, "views", "painting_t120_asis.png"))
    out = {}
    for nm, Z in (("claw_zone", PM.claw_zone()), ("bregion", M.zone_mask())):
        out[nm] = dict(mizuiro=M.mizuiro_frac(im, Z), **M.dark_lines(im, Z))
        out[nm + "_painting"] = dict(mizuiro=M.mizuiro_frac(P, Z), **M.dark_lines(P, Z))
    return out


def kind_of(cid):
    return cid[0]


def geo(claws):
    lay = json.load(open(os.path.join(claws, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    Y = np.memmap(os.path.join(claws, lay["files"]["frames"]["file"]), dtype=np.float32, mode="r", shape=(F, V, 3))
    u = np.zeros(V, np.float32)
    kind = np.empty(V, "U1")
    ent = np.zeros(V, np.int32)
    root = np.zeros(len(lay["claws"]), np.int64)
    for e, c in enumerate(lay["claws"]):
        o, nv, n = c["vert_offset"], c["vert_count"], c["stations"]
        kind[o:o + nv] = kind_of(c["id"])
        ent[o:o + nv] = e
        uu = np.zeros(nv, np.float32)
        uu[1:1 + n * 8] = np.repeat(np.arange(n) / n, 8)
        uu[1 + n * 8] = 1.0
        u[o:o + nv] = uu
        root[e] = o
    ids = [c["id"] for c in lay["claws"]]
    hero = SB.U.K.Pkg(SB.HERO)
    wt, wtau = SB.W31.load_warp(SB.WARP)
    res = {}
    E = len(lay["claws"])
    for f in (270, 315, 360):
        tk = f / 30.0
        tau = 0.0 if tk >= 12.0 - 1e-9 else float(np.interp(tk, wt, wtau))
        Xs = hero.world(tau)
        nrm = np.cross(np.gradient(Xs, axis=0), np.gradient(Xs, axis=1))
        nrm = (nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)).reshape(-1, 3)
        Vf = Xs.reshape(-1, 3)
        tree = cKDTree(Vf)
        P = np.asarray(Y[f], np.float64)
        rd = np.linalg.norm(P - P[root[ent]], axis=1)
        ext = np.zeros(E)
        np.maximum.at(ext, ent, rd)
        alive = ext[ent] > 1e-3
        _, ii = tree.query(P)
        e_ = P - Vf[ii]
        h = (e_ * nrm[ii]).sum(1)
        tang = np.linalg.norm(e_ - h[:, None] * nrm[ii], axis=1)
        for k in sorted(set(kind.tolist())):
            m = (kind == k) & alive & (tang < 0.3)
            b = m & (u > 0.3) & (h < -0.05)
            res["%s_t%03d" % (k, round(f / 3))] = dict(v=int(b.sum()), entries=len(set(ent[b].tolist())),
                                                      deepest=round(float(h[b].min()), 3) if b.any() else 0.0,
                                                      ids=sorted(set(ids[x] for x in ent[b].tolist()))[:10])
    # 加速度の出来事
    Dp2 = Dp = None
    ev = {}
    for f in range(F):
        P = np.asarray(Y[f], np.float64)
        D = P - P[root[ent]]
        if Dp2 is not None:
            a = np.linalg.norm(D - 2 * Dp + Dp2, axis=1)
            ae = np.zeros(E)
            np.maximum.at(ae, ent, a)
            for e in np.where(ae > 0.15)[0]:
                ev.setdefault(ids[e][0], []).append((f, ids[e], round(float(ae[e]), 3)))
        Dp2, Dp = Dp, D
    res["accel_events"] = {k: dict(n=len(v), entries=len(set(x[1] for x in v)), top=sorted(v, key=lambda x: -x[2])[:8]) for k, v in ev.items()}
    res["vertices"] = V
    res["triangles"] = lay["triangles"]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default=None)
    ap.add_argument("--claws", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-geo", action="store_true")
    ap.add_argument("--geo-only", action="store_true")
    a = ap.parse_args()
    if a.geo_only:
        r = dict(geo=geo(a.claws))
        print("R01_QUICK", json.dumps(r, ensure_ascii=False))
        if a.out:
            json.dump(r, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    inv = json.load(open(OV.INV, encoding="utf-8"))
    spec = json.load(open(OV.U.TRUTH, encoding="utf-8"))
    cam = OV.U.CamWH(spec, 1920, 1080)
    ov = OV.measure(a.run, a.claws, inv, cam)[0]
    r = dict(rhythm=rhythm(a.run), overlay=ov)
    if not a.no_geo:
        r["geo"] = geo(a.claws)
    s = json.dumps(r, ensure_ascii=False)
    print("R01_QUICK", s)
    if a.out:
        json.dump(r, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
