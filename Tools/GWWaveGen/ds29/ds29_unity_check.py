# -*- coding: utf-8 -*-
"""設計29：Unity の描画（DS29Render）の照合と、t* の輪郭の差（117）。

1. GPU の読み戻し：DS29Render が設計27 の DS27KeyposeCapture.compute（頂点シェーダーと同じ関数）で書いた全頂点の位置を、
   同じパッケージの numpy の Hermite（ds29_qa.PackageSurface。包みの約束から独立に書いた読み方）と比べる。
   t* のコマは、パッケージの tstar/kstar_a45.gwb（表示の格子の t* の面、量子化の前）とも比べる。
2. t* の輪郭の差（117「減面前との輪郭の差 ≤ 4 px、穴・切断 0」）：色区 ID の画像（主役波だけ、空は白）から主役波の範囲を取り、
   2 つの描画の輪郭（範囲の縁の画素）の間の距離（各縁の画素から相手の縁の最も近い画素まで、両向きの最大。1920 × 1080 の px）。
   原画視点は 2 倍の ID（3840 × 2160）を半分の px に直す。距離は半径 R_MAX px まで調べ、それを超えたら R_MAX 超と書く。
3. t* の色の画像の画素の差（基準の組との比較。記録）。

使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds29/ds29_unity_check.py --runs src_d28=Unity/Build/Design/29/unity/src_d28 full=Unity/Build/Design/29/unity/full_r02 ...
      --packages src_d28=Unity/Build/Design/28/art_on full=Unity/Build/Design/29/r02/full_240x400 ... --ref src_d28 --lod half:full
出力：--out（既定 Unity/Build/Design/29/unity/ds29_unity_check.json）。numpy と Pillow だけ。
"""
import argparse
import json
import os
import struct
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import ds29_qa as QA  # noqa: E402  包みの Hermite（独立の読み方）

R_MAX = 12


def read_gwb_positions(path):
    b = open(path, "rb").read()
    ver, nu, nv, fr = struct.unpack("<iiii", b[4:20])
    nt = struct.unpack("<i", b[28:32])[0]
    n = nu * nv
    o = 32 + n * 16 + nt * 12
    return np.frombuffer(b, np.float32, n * 3, o).reshape(n, 3).astype(np.float64)


def gpu_check(run_dir, pkg_dir):
    cj = os.path.join(run_dir, "gpu_capture", "ds29_gpu_capture.json")
    if not os.path.exists(cj):
        return None
    C = json.load(open(cj, encoding="utf-8"))
    P = QA.PackageSurface(pkg_dir)
    out = []
    worst = 0.0
    for c in C["captures"]:
        g = np.fromfile(os.path.join(run_dir, "gpu_capture", c["file"]), "<f4").reshape(-1, 6).astype(np.float64)
        X = P.world(float(c["tau"]))
        d = float(np.linalg.norm(g[:, :3] - X, axis=1).max())
        nrm = np.linalg.norm(g[:, 3:], axis=1)
        rec = dict(tau=round(float(c["tau"]), 6), max_m=round(d, 6), normal_len_min=round(float(nrm.min()), 4), nan=int(np.isnan(g).sum()))
        if abs(float(c["tau"])) < 1e-12:
            gwb = os.path.join(pkg_dir, "tstar", "kstar_a45.gwb")
            if not os.path.exists(gwb):
                gwb = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26修正01", "kstar", "kstar_a45.gwb")
            T = read_gwb_positions(gwb)
            rec["tstar_vs_gwb_max_m"] = round(float(np.linalg.norm(g[:, :3] - T, axis=1).max()), 6)
            rec["tstar_gwb"] = os.path.relpath(gwb, REPO).replace("\\", "/")
        worst = max(worst, d)
        out.append(rec)
    return dict(captures=len(out), rows=C.get("rows"), cols=C.get("cols"), max_m=round(worst, 6), per_tau=out,
                note_ja="GPU（頂点シェーダーと同じ関数のコンピュート）と numpy の Hermite（ds29_qa.PackageSurface）のワールドの位置の差の最大")


def wave_mask(path, half=False):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.int16)
    m = ~((a[..., 0] == 255) & (a[..., 1] == 255) & (a[..., 2] == 255))
    return m


def edge(m):
    e = np.zeros_like(m)
    e[1:-1, 1:-1] = m[1:-1, 1:-1] & ~(m[:-2, 1:-1] & m[2:, 1:-1] & m[1:-1, :-2] & m[1:-1, 2:])
    return e


def dist_to(eA, eB, rmax):
    """eA の各画素から eB の最も近い画素までのユークリッド距離（rmax を超えたら inf）。"""
    H, W = eA.shape
    ys, xs = np.nonzero(eA)
    if len(ys) == 0:
        return np.array([])
    dA = np.full(len(ys), np.inf)
    offs = [(dy, dx) for dy in range(-rmax, rmax + 1) for dx in range(-rmax, rmax + 1) if dy * dy + dx * dx <= rmax * rmax]
    offs.sort(key=lambda t: t[0] * t[0] + t[1] * t[1])
    pad = np.zeros((H + 2 * rmax, W + 2 * rmax), bool)
    pad[rmax:rmax + H, rmax:rmax + W] = eB
    for dy, dx in offs:
        hit = pad[ys + rmax + dy, xs + rmax + dx]
        r = np.hypot(dy, dx)
        upd = hit & (dA > r)
        dA[upd] = r
        if np.all(np.isfinite(dA)):
            break
    return dA


def outline_diff(pa, pb, scale):
    ma, mb = wave_mask(pa), wave_mask(pb)
    ea, eb = edge(ma), edge(mb)
    d1 = dist_to(ea, eb, R_MAX)
    d2 = dist_to(eb, ea, R_MAX)
    d = np.concatenate([d1, d2]) * scale
    fin = d[np.isfinite(d)]
    over = int((~np.isfinite(d)).sum())
    return dict(max_px=(round(float(fin.max()), 3) if over == 0 else ">%d" % int(R_MAX * scale)), p99_px=round(float(np.percentile(fin, 99)), 3),
                edge_pixels=[int(ea.sum()), int(eb.sum())], beyond_rmax=over, area_px=[int(ma.sum()), int(mb.sum())],
                area_ratio=round(float(mb.sum()) / max(1, int(ma.sum())), 5))


def pixel_diff(pa, pb):
    a = np.asarray(Image.open(pa).convert("RGB")).astype(np.int16)
    b = np.asarray(Image.open(pb).convert("RGB")).astype(np.int16)
    d = np.abs(a - b).max(-1)
    return dict(differing=int((d > 0).sum()), differing_gt24=int((d > 24).sum()), fraction_gt24=round(float((d > 24).mean()), 5), max=int(d.max()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", required=True, help="名前=Unity の出力のフォルダー")
    ap.add_argument("--packages", nargs="+", required=True, help="名前=パッケージ")
    ap.add_argument("--ref", default="src_d28")
    ap.add_argument("--lod", nargs="*", default=[], help="軽い網:基準の網（117 の減面前との輪郭の差）")
    ap.add_argument("--out", default=os.path.join(REPO, "Unity", "Build", "Design", "29", "unity", "ds29_unity_check.json"))
    a = ap.parse_args()
    runs = dict(x.split("=", 1) for x in a.runs)
    pk = dict(x.split("=", 1) for x in a.packages)
    res = dict(schema="GreatWave.DS29.unity_check/1", number="設計29", runs={k: os.path.relpath(os.path.join(REPO, v), REPO).replace("\\", "/") for k, v in runs.items()},
               gpu={}, outline_vs_ref={}, outline_lod={}, pixel_vs_ref={}, r_max_px=R_MAX)
    for k, d in runs.items():
        d = os.path.join(REPO, d)
        print("GPU の照合", k, flush=True)
        res["gpu"][k] = gpu_check(d, os.path.join(REPO, pk[k]))
    views = [("painting", "af28r01_class_ids.png", 0.5), ("seat", "af28r01_seat_class_ids.png", 1.0), ("seat_low", "af28r01_seat_low_class_ids.png", 1.0)]
    rd = os.path.join(REPO, runs[a.ref], "t28", "render")
    for k, d in runs.items():
        if k == a.ref:
            continue
        dd = os.path.join(REPO, d, "t28", "render")
        res["outline_vs_ref"][k] = {v: outline_diff(os.path.join(rd, f), os.path.join(dd, f), s) for v, f, s in views}
        res["pixel_vs_ref"][k] = {v: pixel_diff(os.path.join(rd, "af28r01_%s.png" % v), os.path.join(dd, "af28r01_%s.png" % v)) for v in ("painting", "seat", "seat_low", "painting_kstar")}
    for pair in a.lod:
        lo, hi = pair.split(":")
        dl, dh = os.path.join(REPO, runs[lo], "t28", "render"), os.path.join(REPO, runs[hi], "t28", "render")
        res["outline_lod"][lo + "_vs_" + hi] = {v: outline_diff(os.path.join(dh, f), os.path.join(dl, f), s) for v, f, s in views}
    res["note_ja"] = ("輪郭の差：色区 ID の画像（t*、主役波だけ、空は白）で主役波の範囲の縁の画素どうしの距離（両向きの最大）。原画視点は 2 倍の ID を半分にして"
                      " 1920 × 1080 の px。117 の基準は減面前との輪郭の差 ≤ 4 px（仕上げの判定は番号41、ここでは表示用サーフェスの軽量版と原版の差）。")
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(dict(gpu={k: (v or {}).get("max_m") for k, v in res["gpu"].items()},
                          outline_vs_ref={k: {vv: x["max_px"] for vv, x in v.items()} for k, v in res["outline_vs_ref"].items()},
                          outline_lod={k: {vv: x["max_px"] for vv, x in v.items()} for k, v in res["outline_lod"].items()}), ensure_ascii=False))


if __name__ == "__main__":
    main()
