# -*- coding: utf-8 -*-
"""設計29：表示用サーフェスの numpy の図（Unity の描画ではない）。

  fig_ds29_sections.png  峰の行（源の行 192）と主断面（行 159）の断面の唇の付近を、密度ごと（列）× τ（行）に拡大して描く。
                         灰の細線 = 源（設計28 の既定のパッケージ）、色の線と点 = 表示の網の頂点。
  fig_ds29_lip_wire.png  唇〜管の天井（源の行 170〜200）の網の辺を斜めの正射影で描く（源と表示の網、t* と τ −1.33 s）。
                         行の間の対応（K* の唇先・rim の列の割り付けの跳び）が見える。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/ds29/ds29_figures.py [--names half_120x200,full_240x400,double_480x800] [--root Unity/Build/Design/29/r01]
出力：Docs/Evidence/Design/29/
"""
import argparse
import math
import os
import sys
from types import SimpleNamespace

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds29_surface as S  # noqa: E402
import ds27_gates as GT  # noqa: E402

REPO = S.REPO
ROOT = [os.path.join(REPO, "Unity", "Build", "Design", "29")]
FONT = "C:/Windows/Fonts/YuGothM.ttc"
COLS = [(200, 60, 40), (30, 110, 200), (20, 150, 90), (150, 60, 170)]


def font(sz):
    return ImageFont.truetype(FONT, sz)


def load(name, ks):
    if name == "src":
        d = os.path.join(REPO, "Unity", "Build", "Design", "28", "art_on")
        pk = GT.Package(d, SimpleNamespace(nv=240, nu=400))
        return pk, np.arange(240, dtype=float), None
    d = os.path.join(ROOT[0], name)
    pk = GT.Package(d, SimpleNamespace(nv=0, nu=0))
    M = np.load(os.path.join(d, "ds29_map.npz"))
    return pk, M["rho"], M


def sections(names, ks, out):
    taus = [-3.0, -2.25, -1.333, 0.0]
    W, H = 330, 250
    img = Image.new("RGB", (60 + W * len(names), 40 + H * len(taus)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    src = load("src", ks)
    for j, nm in enumerate(names):
        d.text((60 + j * W + 6, 8), "設計28 の源 240×400" if nm == "src" else nm, fill=(0, 0, 0), font=font(15))
    for i, tau in enumerate(taus):
        d.text((4, 40 + i * H + H // 2), "τ %+.2f" % tau, fill=(0, 0, 0), font=font(13))
        Xs = src[0].world(tau)
        As = (Xs - ks.O) @ ks.t
        Ys = Xs[..., 1]
        for j, nm in enumerate(names):
            pk, rho, M = src if nm == "src" else load(nm, ks)
            X = pk.world(tau)
            A = (X - ks.O) @ ks.t
            Y = X[..., 1]
            x0, y0 = 60 + j * W, 40 + i * H
            d.rectangle([x0 + 2, y0 + 2, x0 + W - 3, y0 + H - 3], outline=(200, 200, 200))
            for rr, col in ((192, COLS[0]), (159, COLS[1])):
                ca = As[rr, int(np.argmax(np.where(np.arange(400) <= ks.crest_hi[rr], Ys[rr], -np.inf)))]
                xr = (ca - 4.0, ca + 14.0)
                yr = (Ys[rr].max() - 17.0, Ys[rr].max() + 1.5)
                s = min((W - 10) / (xr[1] - xr[0]), (H - 10) / (yr[1] - yr[0]))

                def P(a, y):
                    return (x0 + 5 + (a - xr[0]) * s, y0 + H - 5 - (y - yr[0]) * s)
                if rr == 159:
                    continue
                k = int(np.argmin(np.abs(rho - rr)))
                # 源の面の、表示の行と同じ c の切り口（源の列の辺と対角線との交点）
                r0 = min(int(np.floor(rho[k])), 238)
                fr = rho[k] - r0
                jj = np.sort(np.concatenate([np.arange(400.0), np.arange(399.0) + 1.0 - fr]))
                idx, w = S.bary(np.full(jj.shape, rho[k]), jj, 240, 400)
                Cw = S.gather(Xs.reshape(-1, 3), idx, w)
                d.line([P(a, y) for a, y in zip((Cw - ks.O) @ ks.t, Cw[:, 1]) if xr[0] - 3 < a < xr[1] + 3], fill=(170, 170, 170), width=3)
                pts = [P(a, y) for a, y in zip(A[k], Y[k]) if xr[0] - 3 < a < xr[1] + 3]
                d.line(pts, fill=col, width=1)
                for p in pts:
                    d.ellipse([p[0] - 1.5, p[1] - 1.5, p[0] + 1.5, p[1] + 1.5], fill=col)
            d.text((x0 + 6, y0 + 5), "峰の行の付近 ρ = %.2f（灰 = 源の同じ c の切り口）" % rho[int(np.argmin(np.abs(rho - 192)))], fill=(90, 90, 90), font=font(11))
    img.save(out)


def wire(names, ks, out):
    """唇〜管の天井の網を、行ごとの弧長（頂の目印から、m）× 波峰線の位置 c（5 倍に拡大）に広げて描く。青 = 行の辺、橙 = 行の間の辺（3 列おき）。
    行の間の辺が斜めに長く寝る所が、行の間の対応がずれている所（P13 (5d)）。"""
    taus = [-1.333, 0.0]
    W, H = 640, 330
    img = Image.new("RGB", (W * len(taus), 30 + H * len(names)), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for i, tau in enumerate(taus):
        d.text((i * W + 8, 6), "τ %+.2f s：源の行 176〜196（c +2.6〜+4.2 m）の唇〜管の天井。横 = 頂からの弧長 m、縦 = c（5 倍）" % tau, fill=(0, 0, 0), font=font(12))
    for j, nm in enumerate(names):
        pk, rho, M = load(nm, ks)
        if nm == "src":
            rows = np.arange(176, 197)
            c0s = np.array([ks.cq[r]["jt"] if r in ks.cq else 87 for r in rows])
            c1 = 347
        else:
            rows = np.nonzero((rho >= 176) & (rho <= 196))[0]
            k = M["k_seg"]
            c0s = np.full(len(rows), int(k[2]))
            c1 = int(k[4])
        cc = np.interp(rho[rows], np.arange(240), ks.c)
        for i, tau in enumerate(taus):
            X = pk.local(tau) + pk.origin(0.0)[0]
            A = (X - ks.O) @ ks.t
            Y = X[..., 1]
            x0, y0 = i * W, 30 + j * H
            s_lo, s_hi = -1.0, 40.0
            c_lo, c_hi = 2.5, 4.3
            sx = (W - 20) / (s_hi - s_lo)
            sy = (H - 40) / (c_hi - c_lo)

            def P(sv, cv):
                return (x0 + 10 + (sv - s_lo) * sx, y0 + H - 10 - (cv - c_lo) * sy)
            S_ = []
            for q, r in enumerate(rows):
                seg = np.hypot(np.diff(A[r, c0s[q]:c1 + 1]), np.diff(Y[r, c0s[q]:c1 + 1]))
                S_.append(np.concatenate([np.zeros(c0s[q]), [0.0], np.cumsum(seg)]))
            for q in range(len(rows) - 1):
                n_ = min(len(S_[q]), len(S_[q + 1]))
                for c in range(max(c0s[q], c0s[q + 1]), n_, 3):
                    d.line([P(S_[q][c], cc[q]), P(S_[q + 1][c], cc[q + 1])], fill=(215, 120, 60), width=1)
            for q in range(len(rows)):
                d.line([P(v, cc[q]) for v in S_[q][c0s[q]:]], fill=(40, 80, 170), width=1)
            d.text((x0 + 10, y0 + 4), ("設計28 の源 240×400" if nm == "src" else nm) + "（橙 = 行の間の辺、3 列おき）", fill=(0, 0, 0), font=font(13))
    img.save(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", default="half_120x200,full_240x400,double_480x800")
    ap.add_argument("--out", default=os.path.join(REPO, "Docs", "Evidence", "Design", "29"))
    ap.add_argument("--root", default=ROOT[0])
    a = ap.parse_args()
    ROOT[0] = os.path.abspath(a.root)
    ks = GT.KStar()
    names = ["src"] + [n for n in a.names.split(",") if n]
    os.makedirs(a.out, exist_ok=True)
    sections(names, ks, os.path.join(a.out, "fig_ds29_sections.png"))
    wire(["src", "full_240x400"], ks, os.path.join(a.out, "fig_ds29_lip_wire.png"))
    print("DONE")


if __name__ == "__main__":
    main()
