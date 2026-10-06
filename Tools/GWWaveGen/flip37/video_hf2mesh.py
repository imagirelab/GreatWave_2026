# -*- coding: utf-8 -*-
"""P2 の計算の水面の高さの場（run_p2.py の hf.npz：一番上の水面 η(z, x)、毎コマ、2 m の格子の節）→ 網目 mesh_FFFF.npz。py -3.10

段階 Video で使う：P2 の網目（mesh/）は 6.0 s 以降・3 コマおきしかないので、
- P3 の始まり（2.96 s）より前のコマ（波が約 200 m 沖にいる t = 0 から）
- P3 の主役の範囲の外の海（毎コマ、時刻の差 0）
を、同じ P2 の計算の水面の場から作る。張り出し（巻いた唇）は高さの場では表せないが、主役の範囲の外（|z| > 67 m・x < 303 m・x > 637 m）では
t ≤ 9.54 s に張り出しはない（R18 の z ±60 m の巻き始めは 11.75 s）。

使い方:
  py -3.10 video_hf2mesh.py <P2 の run_dir> <out_mesh_dir> [f0] [f1] [--x x0 x1]
出力の形は run_p2.py の網目と同じ（P float32：x 進む向き・y 上・z 峰に沿う向き、tri int32、t 秒）。
"""
import os, sys, json
import numpy as np


def main():
    a = sys.argv[1:]
    xr = None
    if "--x" in a:
        k = a.index("--x"); xr = (float(a[k + 1]), float(a[k + 2])); a = a[:k] + a[k + 3:]
    rd, out = a[0], a[1]
    f0 = int(a[2]) if len(a) > 2 else 1
    f1 = int(a[3]) if len(a) > 3 else 10 ** 9
    d = np.load(os.path.join(rd, "hf.npz"))
    g = json.loads(str(d["grid"]))
    nx, _, nz = g["res"]
    eta_all = d["eta"]; frames = d["frames"]; ts = d["t"]
    nz_, nx_ = eta_all.shape[1:]
    xs = g["x0"] + g["dx"] * np.arange(nx_)
    zs = g["z0"] + g["dz"] * np.arange(nz_)
    ix = np.arange(nx_) if xr is None else np.where((xs >= xr[0] - 1e-6) & (xs <= xr[1] + 1e-6))[0]
    xs = xs[ix]
    X, Z = np.meshgrid(xs, zs)                       # (nz, nx)
    idx = np.arange(X.size).reshape(X.shape)
    a00 = idx[:-1, :-1].ravel(); a10 = idx[:-1, 1:].ravel(); a01 = idx[1:, :-1].ravel(); a11 = idx[1:, 1:].ravel()
    tri_all = np.concatenate([np.stack([a00, a01, a10], 1), np.stack([a10, a01, a11], 1)]).astype(np.int64)
    os.makedirs(out, exist_ok=True)
    n = 0
    for k, f in enumerate(frames):
        if f < f0 or f > f1:
            continue
        E = eta_all[k][:, ix].astype(np.float32)
        ok = np.isfinite(E).ravel()
        tri = tri_all[ok[tri_all].all(1)]
        used = np.unique(tri)
        remap = np.full(X.size, -1, np.int64); remap[used] = np.arange(len(used))
        P = np.stack([X.ravel()[used], E.ravel()[used], Z.ravel()[used]], 1).astype(np.float32)
        np.savez(os.path.join(out, "mesh_%04d.npz" % f), P=P, tri=remap[tri].astype(np.int32), t=np.float64(ts[k]),
                 src=np.array("hf.npz %s f%d" % (os.path.basename(os.path.normpath(rd)), f)))
        n += 1
    json.dump({"src": os.path.join(rd, "hf.npz").replace("\\", "/"), "grid": g, "frames": [int(f0), int(min(f1, frames.max()))],
               "x_range": [float(xs[0]), float(xs[-1])], "n": n,
               "note_ja": "P2 の水面の高さの場（一番上の水面、2 m の格子の節）から作った網目。張り出しは表せない"},
              open(os.path.join(out, "hf_mesh.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print("hf2mesh", n, "meshes ->", out)


if __name__ == "__main__":
    main()
