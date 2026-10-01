# -*- coding: utf-8 -*-
"""仕上げ28：F7-1 の切り分けの 2 つ目。無圧縮の静止画（Unity、原画視点、30 fps のコマ）で、1 コマだけの色の跳び
c(f−1) = c(f+1) ≠ c(f) を「画面に固定した点」と「面に付いて動く点（頂点）」の 2 通りで数える。

考え方：色区の模様は頂点ごとに固定の UV3 で面に貼られていて、白の時間場は τ に対して単調なので、面に付いた点の色は形成の間に
一度しか変わらない（跳ばない）。だから
  ・画面に固定した点では跳ぶが、面に付いて動く点では跳ばない → 跳びは「細かい模様が 1 コマの移動より速く動く」ことの標本化
    （動きは滑らかで、1 コマで模様の斑を飛び越す。動きの行き戻りや模様の座標のゆれではない）
  ・面に付いて動く点でも跳ぶ → 模様そのものがコマごとに揺れる（描画の標本化の揺れ、焼き込みの座標、見え隠れ）
面に付いた点は包みの頂点（pl28_f71_geom.Pkg、再生器と同じ Hermite ＋ 精度の層）を原画のカメラへ写した位置の画素で読む。
画素の丸め（最大 0.5 px）で色の境のすぐそばは跳んで見えるので、そのコマで 5×5 の画素が同じ色区の「内側」の点も別に数える。
色区の分け方は段階7確認の台本と同じ調色板（pl28_s7_video.classify。塗りの 4 色：白・淡い水色・藍中・藍濃）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_track.py --stills <PNG のフォルダー> --glob "ds29_painting_f*.png" --first 264
      --package <包み> --warp <時間曲線> --out <json>
"""
import argparse
import glob
import hashlib
import json
import os
import sys
import time

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import pl28_s7_video as S7  # noqa: E402
import pl28_f71_geom as GM  # noqa: E402

KC = GM.KC


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stills", required=True)
    ap.add_argument("--glob", default="*.png")
    ap.add_argument("--first", type=int, required=True)
    ap.add_argument("--package", required=True)
    ap.add_argument("--warp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=30.0)
    a = ap.parse_args()
    t0 = time.time()
    files = sorted(glob.glob(os.path.join(GM.absrepo(a.stills), a.glob)))
    n = len(files)
    frames = np.arange(a.first, a.first + n)
    C = []
    for f in files:
        C.append(S7.classify(np.asarray(Image.open(f).convert("RGB"))))    # 0 その他、1 白、2 淡い水色、3 藍中、4 藍濃、5 藍の線
    C = np.stack(C)
    H, W = C.shape[1:]
    fill = (C >= 1) & (C <= 4)
    # 5×5 が同じ色の「内側」
    same = np.ones_like(C, bool)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            sh = np.roll(np.roll(C, dy, axis=1), dx, axis=2)
            same &= (sh == C)
    pk = GM.Pkg(a.package)
    Wj = json.load(open(GM.absrepo(a.warp), encoding="utf-8"))
    wt, wtau = np.asarray(Wj["t"], float), np.asarray(Wj["tau"], float)
    taus = np.interp(frames / a.fps, wt, wtau)
    white = pk.tw < 1e8
    P, V = [], []
    for tau in taus:
        sc = KC.project_unity(pk.world(float(tau), fine=True))
        P.append(sc[:, :2])
        V.append(GM.visible_mask(sc))
    P = np.stack(P)
    V = np.stack(V)
    ix = np.clip(np.round(P[..., 0]).astype(np.int64), 0, W - 1)
    iy = np.clip(np.round(P[..., 1]).astype(np.int64), 0, H - 1)
    ins = (P[..., 0] >= 2) & (P[..., 0] < W - 2) & (P[..., 1] >= 2) & (P[..., 1] < H - 2)
    rows = []
    for k in range(1, n - 1):
        m = white & V[k - 1] & V[k] & V[k + 1] & ins[k - 1] & ins[k] & ins[k + 1]
        vid = np.nonzero(m)[0]
        # 面に付いて動く点
        c0 = C[k - 1][iy[k - 1, vid], ix[k - 1, vid]]
        c1 = C[k][iy[k, vid], ix[k, vid]]
        c2 = C[k + 1][iy[k + 1, vid], ix[k + 1, vid]]
        okf = (c0 >= 1) & (c0 <= 4) & (c1 >= 1) & (c1 <= 4) & (c2 >= 1) & (c2 <= 4)
        trk = okf & (c0 == c2) & (c1 != c0)
        inner = same[k][iy[k, vid], ix[k, vid]]
        # 同じ頂点の、そのコマの画素に固定した点
        g0 = C[k - 1][iy[k, vid], ix[k, vid]]
        g2 = C[k + 1][iy[k, vid], ix[k, vid]]
        okg = (g0 >= 1) & (g0 <= 4) & (c1 >= 1) & (c1 <= 4) & (g2 >= 1) & (g2 <= 4)
        fix = okg & (g0 == g2) & (c1 != g0)
        # 画面全体の固定の画素（塗りの 4 色）
        fullfix = fill[k - 1] & fill[k] & fill[k + 1] & (C[k - 1] == C[k + 1]) & (C[k] != C[k - 1])
        sp = np.linalg.norm(P[k, vid] - P[k - 1, vid], axis=1)
        rows.append(dict(frame=int(frames[k]), t=round(float(frames[k] / a.fps), 4), tau=round(float(taus[k]), 5), verts=int(len(vid)),
                         verts_fill=int(okf.sum()), tracked_flips=int(trk.sum()), tracked_flips_inner=int((trk & inner).sum()),
                         fixed_flips=int(fix.sum()), fixed_flips_inner=int((fix & inner).sum()), inner=int((okf & inner).sum()),
                         fullframe_fixed_flip_px=int(fullfix.sum()), speed_px_p50=round(float(np.median(sp)) if sp.size else 0.0, 3)))

    def win(lo, hi):
        rr = [r for r in rows if lo <= r["frame"] <= hi]
        if not rr:
            return None
        s = lambda k: int(sum(r[k] for r in rr))  # noqa: E731
        return dict(frames=[lo, hi], n_frames=len(rr), vertex_samples=s("verts_fill"), inner_samples=s("inner"),
                    tracked_flips=s("tracked_flips"), fixed_flips=s("fixed_flips"),
                    tracked_flip_rate=round(s("tracked_flips") / max(1, s("verts_fill")), 5), fixed_flip_rate=round(s("fixed_flips") / max(1, s("verts_fill")), 5),
                    tracked_flips_inner=s("tracked_flips_inner"), fixed_flips_inner=s("fixed_flips_inner"),
                    tracked_flip_rate_inner=round(s("tracked_flips_inner") / max(1, s("inner")), 5),
                    fixed_flip_rate_inner=round(s("fixed_flips_inner") / max(1, s("inner")), 5),
                    fullframe_fixed_flip_px=s("fullframe_fixed_flip_px"),
                    speed_px_p50_median=round(float(np.median([r["speed_px_p50"] for r in rr])), 3))
    res = dict(schema="GreatWave.Polish28.f71_track/1", stills=os.path.relpath(GM.absrepo(a.stills), REPO).replace("\\", "/"), png_count=n,
               first_frame=a.first, package=os.path.relpath(pk.dir, REPO).replace("\\", "/"), pos_sha256=pk.pos_sha,
               warp_sha256=sha256_file(GM.absrepo(a.warp)),
               windows=dict(t9_11p5=win(270, 345), all=win(int(frames[1]), int(frames[-2]))), per_frame=rows,
               code_sha256=sha256_file(os.path.abspath(__file__)), seconds=round(time.time() - t0, 1))
    os.makedirs(os.path.dirname(GM.absrepo(a.out)), exist_ok=True)
    with open(GM.absrepo(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res["windows"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
