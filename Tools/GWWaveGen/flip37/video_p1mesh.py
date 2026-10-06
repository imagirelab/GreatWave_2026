# -*- coding: utf-8 -*-
"""P1（断面の計算）の粒子 snap_FFFF.npz → 動画の道具の網目 mesh_FFFF.npz（試験用）。py -3.10

断面の粒子（x, y）を升目にし（p1_analyze の raster・water_mask・main_component と同じ）、水の縁（外側と閉じた空洞）を
輪郭として取り、z = −zl〜+zl へ押し出す（峰に沿って同じ形の長い波）。P2・P3 の 3 次元の網目と同じ形式
（P float32、tri int32、t）で書くので、動画の道具をそのまま試せる。形は断面の計算のままで、峰に沿う変化はない。

使い方: py -3.10 video_p1mesh.py <P1 の run_dir> <out_mesh_dir> [t0] [t1] [--every 1] [--zl 120]
"""
import sys, os, glob, argparse
import numpy as np
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import p1_analyze as A1  # noqa: E402


def contours(x, y, xwin):
    cnt = A1.raster(x, y, xwin[0], xwin[1])
    water, closed = A1.water_mask(cnt)
    w = A1.main_component(water)
    # 閉じた空洞（巻き込みの筒）を穴として残すため、w をそのまま輪郭にする（RETR_CCOMP：外側と穴）
    img = w[::-1].astype(np.uint8)   # 行 0 を上へ（画像の向き）
    cs, hier = cv2.findContours(img, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    ny = img.shape[0]
    for c in cs:
        if len(c) < 12:
            continue
        p = c[:, 0, :].astype(np.float64)
        # 輪郭をなめらかに（升目の階段を消す。閉じた線として 5 点の移動平均を 2 回）
        for _ in range(2):
            p = (np.roll(p, 2, 0) + np.roll(p, 1, 0) + p + np.roll(p, -1, 0) + np.roll(p, -2, 0)) / 5.0
        X = xwin[0] + (p[:, 0] + 0.5) * A1.DX
        Y = A1.YMIN + (ny - p[:, 1] - 0.5) * A1.DX
        # 間引き（点の間を約 0.75 m に。押し出す行の数が多いので点を減らす）
        out.append(np.stack([X, Y], 1)[::3])
    return out


def extrude(polys, zl, dz=4.0):
    """閉じた輪郭を z へ押し出す。三角形の長さを dz（既定 4 m）に抑える（長い三角形はカメラの後ろへはみ出して
    p2_common.raster_mask で捨てられ、シルエットが欠けるため）。"""
    nz = int(round(2 * zl / dz)) + 1
    P = []; tri = []; base = 0
    zs = np.linspace(-zl, zl, nz)
    for pl in polys:
        n = len(pl)
        for z in zs:
            P.append(np.stack([pl[:, 0], pl[:, 1], np.full(n, z)], 1))
        for j in range(nz - 1):
            a = base + j * n + np.arange(n); b = base + j * n + (np.arange(n) + 1) % n
            c = a + n; d = b + n
            tri.append(np.stack([a, b, d], 1)); tri.append(np.stack([a, d, c], 1))
        base += n * nz
    return np.concatenate(P).astype(np.float32), np.concatenate(tri).astype(np.int32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir"); ap.add_argument("out_dir")
    ap.add_argument("t0", type=float, nargs="?", default=-1e9); ap.add_argument("t1", type=float, nargs="?", default=1e9)
    ap.add_argument("--every", type=int, default=1); ap.add_argument("--zl", type=float, default=120.0)
    ap.add_argument("--dz", type=float, default=4.0)
    ap.add_argument("--xwin", type=float, nargs=2, default=[380.0, 706.0])
    a = ap.parse_args()
    import json
    rj = json.load(open(os.path.join(a.run_dir, "run.json"), encoding="utf8"))
    A1.set_dx(rj["parms"])
    os.makedirs(a.out_dir, exist_ok=True)
    fs = sorted(glob.glob(os.path.join(a.run_dir, "snap_*.npz")))
    k = 0
    for f in fs:
        d = np.load(f)
        t = float(d["t"])
        if t < a.t0 - 1e-6 or t > a.t1 + 1e-6:
            continue
        k += 1
        if (k - 1) % a.every:
            continue
        polys = contours(d["x"].astype(np.float64), d["y"].astype(np.float64), a.xwin)
        P, tri = extrude(polys, a.zl, a.dz)
        fr = int(os.path.basename(f)[5:9])
        np.savez_compressed(os.path.join(a.out_dir, "mesh_%04d.npz" % fr), P=P, tri=tri, t=t,
                            source=os.path.abspath(f).replace("\\", "/"), note="P1 の断面を z へ押し出した試験用の網目")
        print("mesh_%04d t=%.3f polys=%d verts=%d tris=%d" % (fr, t, len(polys), len(P), len(tri)))


if __name__ == "__main__":
    main()
