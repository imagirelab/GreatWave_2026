# -*- coding: utf-8 -*-
"""仕上げ30 修正02（自己評審の修正の回 2）の numpy の検査（Unity の描画ではない）。

使い方（リポジトリの根で）:
    py -3.10 -B Tools/GWWaveGen/pl30/pl30_fix02_checks.py --sea Unity/Build/Polish/30/sea --out Unity/Build/Polish/30/fix02/checks_final [--attr-old Unity/Build/Polish/30/sea_f1]
測るもの:
  seam_all   継ぎ目の両側の法線の内積を全部の節点（251）で。2 つの読み：
               vertex：頂点の法線（隣の差の外積。pl30_checks.seam と同じ。主役波は本体の列の中、near は near の格子の中で求める）
               face  ：片側の面の法線（継ぎ目の辺 B_j→B_{j+1} と、主役波は内へ 1 つの頂点、near は行 1 の頂点で作る三角形の法線。向きは継ぎ目をはさんで反対に取って符号を合わせる）
             どちらも錐の点（主役波の行 0・最後の行）を除く。修正01 の記録の 0.858 は 5 節点おき＋t* の値（pl30_checks.seam）。
  white      形成の途中の偽の白（自己評審の修正の回 2 の 1）：材質の白の判定（稜の系）を numpy で写し、作る部・修正01 の読み（今の高さの比だけ）と
             修正02 の読み（今の高さの比を、今の育ち g_r(τ) × t* の高さの比 + 0.1 で上から抑える）で、白になる near の頂点の数と、そのうち t* の高さの比 < 0.7 の数を時刻ごとに数える。
             房の長さは最長（0.32）を仮に置いた上限の見当（材質の房は列ごとに短い）。q の上限（_CapQ）と肩の稜の細い線は数えない。
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402
from pl30_checks import Pkg, vnormals, timewarp  # noqa: E402

REPO = S.REPO


def seam_all(hero, near, idx):
    loop = np.array([[d["hero_row"], d["hero_col"]] for d in idx["loop"]])
    kinds = np.array([d["ray"] for d in idx["loop"]])
    NL = len(loop)
    jb, je = idx["body_cols"]
    inner = []
    for (r, j), k in zip(loop, kinds):
        if k == "front":
            inner.append((r, j - 1))
        elif k == "back":
            inner.append((r, j + 1))
        elif k == "fanL":
            inner.append((1, j))
        else:
            inner.append((hero.R - 2, j))
    inner = np.array(inner)
    good = ~((loop[:, 0] == 0) | (loop[:, 0] == hero.R - 1))
    goodseg = good & np.roll(good, -1)
    kn = hero.knots
    vmin = np.zeros(len(kn)); fmin = np.zeros(len(kn)); vcol = np.zeros(len(kn), int); fcol = np.zeros(len(kn), int)
    vbelow = np.zeros(len(kn), int); fbelow = np.zeros(len(kn), int)
    for i in range(len(kn)):
        Xh = hero.layer(i); Xn = near.layer(i, rows=slice(0, 3))
        nh = vnormals(Xh[:, jb:je + 1])
        nn = vnormals(near.layer(i))[0, :NL]
        hh = nh[loop[:, 0], loop[:, 1] - jb]
        d = (hh * nn).sum(-1)
        dv = np.where(good, d, 9.0)
        vmin[i] = dv.min(); vcol[i] = int(np.argmin(dv)); vbelow[i] = int((dv < 0.9).sum())
        B = Xh[loop[:, 0], loop[:, 1]]
        I = Xh[inner[:, 0], inner[:, 1]]
        N1 = Xn[1, :NL]
        e = np.roll(B, -1, axis=0) - B
        fh = np.cross(e, I - B); fn = np.cross(e, N1 - B)
        fh /= np.maximum(np.linalg.norm(fh, axis=-1, keepdims=True), 1e-12)
        fn /= np.maximum(np.linalg.norm(fn, axis=-1, keepdims=True), 1e-12)
        df = -(fh * fn).sum(-1)
        df = np.where(goodseg, df, 9.0)
        fmin[i] = df.min(); fcol[i] = int(np.argmin(df)); fbelow[i] = int((df < 0.9).sum())
    iv = int(np.argmin(vmin)); jf = int(np.argmin(fmin))
    every5 = sorted(set(list(range(0, len(kn), 5)) + [len(kn) - 1]))
    return dict(knots=len(kn),
                vertex=dict(min=float(vmin.min()), at_tau=float(kn[iv]), at_knot=iv, at_col=int(vcol[iv]), tstar_min=float(vmin[-1]),
                            min_every5=float(vmin[every5].min()), below09_max_per_knot=int(vbelow.max()), below09_tstar=int(vbelow[-1])),
                face=dict(min=float(fmin.min()), at_tau=float(kn[jf]), at_knot=jf, at_col=int(fcol[jf]), tstar_min=float(fmin[-1]),
                          min_every5=float(fmin[every5].min()), below09_max_per_knot=int(fbelow.max()), below09_tstar=int(fbelow[-1])),
                per_knot_vertex=[round(float(v), 4) for v in vmin], per_knot_face=[round(float(v), 4) for v in fmin],
                note_ja="全部の節点（%d）。vertex は頂点の法線（pl30_checks.seam と同じ）、face は継ぎ目の辺の両側の三角形の法線（主役波は内へ 1 つ、near は行 1）。"
                        "錐の点（主役波の行 0・最後の行）を除く。min_every5 は 5 節点おき＋t*（修正01 の記録の読み）。" % len(kn))


def white_gate(near, sd, feat, t_all, tau_all):
    A = np.fromfile(os.path.join(sd, "near", "pl30_sea_attr_f32.bin"), "<f4")
    A = A.reshape(near.R, near.C, A.size // (near.R * near.C)).astype(np.float64)
    hR, wR, hfR, mixR, boatw = A[..., 2], A[..., 3], A[..., 16], A[..., 17], A[..., 18]
    hcs = np.maximum(hR, 0.5)
    thr = 0.94 + (0.80 - 0.94) * np.clip(mixR, 0, 1)
    wr = wR * (1 - np.clip(boatw / 0.1, 0, 1))
    minY = np.minimum(2.6, 0.62 * hcs)
    out = []
    for t in [6.0, 7.0, 8.0, 9.0, 10.0, 10.5, 11.0, 12.0]:
        tau = float(np.interp(t, t_all, tau_all))
        y = near.world(tau)[..., 1]
        gR = float(np.interp(tau, feat.h.knots, feat.growth_right_knots))
        h_old = y / hcs
        h_new = np.minimum(h_old, gR * hfR + 0.1)
        base = (wr > 0.5) & (hR > 2.0) & (y > minY)
        rec = dict(t=t, tau=tau, g_r=gR)
        for nm, hh in (("old", h_old), ("new", h_new)):
            W0 = base & (hh > thr)
            W1 = base & (hh > thr - 0.32)
            rec[nm] = dict(white_no_claw=int(W0.sum()), white_max_claw=int(W1.sum()), white_max_claw_hf_below07=int((W1 & (hfR < 0.7)).sum()))
        out.append(rec)
    return dict(frames=out, note_ja="稜の系の白の判定の numpy の写し（材質の _CapQ・肩の稜の細い線・房の形は数えない）。old＝作る部・修正01（今の高さの比だけ）、new＝修正02（g_r(τ)·hf + 0.1 で上から抑える）。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sea", default="Unity/Build/Polish/30/sea")
    ap.add_argument("--out", default="Unity/Build/Polish/30/fix02/checks_final")
    ap.add_argument("--params", default=S.PARAMS)
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    skip = set(args.skip.split(",")) if args.skip else set()
    t0 = time.time()
    P = S.load_json(args.params)
    sd = os.path.join(REPO, args.sea)
    hero_s = S.Hero(P)
    hero = Pkg(hero_s.dir)
    near = Pkg(os.path.join(sd, "near"))
    idx = S.load_json(os.path.join(sd, "near", "ds30_ring0_index.json"))
    M = dict(number="仕上げ30 修正02", schema="GreatWave.PL30.fix02_checks/1", renderer_ja="numpy（Unity の描画ではない）", sea=args.sea)
    if "seam" not in skip:
        M["seam_all"] = seam_all(hero, near, idx)
        print("seam_all", json.dumps({k: v for k, v in M["seam_all"].items() if not k.startswith("per_knot")}, ensure_ascii=False))
    if "white" not in skip:
        feat = S.Features(hero_s, P)
        hmax = [float(hero.layer(i)[:, idx["body_cols"][0]:idx["body_cols"][1] + 1, 1].max()) for i in range(hero.L)]
        feat.set_growth(hmax)
        t_all, tau_all, _ = timewarp(P)
        M["white"] = white_gate(near, sd, feat, t_all, tau_all)
        for r in M["white"]["frames"]:
            print("white t %.1f g_r %.3f old %s new %s" % (r["t"], r["g_r"], r["old"], r["new"]))
    M["seconds"] = round(time.time() - t0, 1)
    os.makedirs(os.path.join(REPO, args.out), exist_ok=True)
    S.save_json(os.path.join(REPO, args.out, "pl30_fix02_checks.json"), M)
    print("done", M["seconds"], "s")


if __name__ == "__main__":
    main()
