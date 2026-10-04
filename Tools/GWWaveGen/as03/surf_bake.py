# -*- coding: utf-8 -*-
"""美術の見本03 の作り B2：t* の主役波 AS02C の頂点ごとに、面の遮り（AO）と、ワールドに固定した光（_LightDir）からの見通し（keyVis）を焼く。

- 主役波の格子（行 240 × 列 400、keypose の包みの τ = 0）の面を、0.25 m の箱（ボクセル）に塗り、1 箱ぶん太らせる（薄い面を光線が抜けないように）。
- 頂点から法線の向きへ 0.6 m 離れた所から光線を進め、箱に当たるかを見る。
  AO：法線のまわりの半球の 32 本（余弦の重み）、10 m まで。keyVis：光の向きのまわり 3° の円錐の 8 本、60 m まで。
- 主役波のほか（海・船・冠）は遮らない（主役波だけの陰）。光は見本01・02 の固定の向き (−0.45, 0.75, −0.5)。視点によらない値。
- 出力（Git 対象外）：Build/Polish/sample03/surface/bake/hero_bake.npz（ao・kv、行 × 列）と .json。surf_relief.py --bake で静止のメッシュの UV5 へ入る。
原画カメラは使わない。参照モデルの OBJ・写真は読まない。
使い方：py -3.10 -B Tools/GWWaveGen/as03/surf_bake.py
"""
import os
import sys
import time

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surf_common as S  # noqa: E402


def main():
    t0 = time.time()
    P = S.load_hero_world()
    R, C = P.shape[:2]
    at = np.fromfile(S.ATTR, np.float32).reshape(R, C, 12).astype(np.float64)
    N = S.unit(at[..., 8:11])
    vox = 0.25
    lo = P.reshape(-1, 3).min(0) - 2.0
    hi = P.reshape(-1, 3).max(0) + 2.0
    dims = np.ceil((hi - lo) / vox).astype(int) + 1
    occ = np.zeros(dims, bool)
    # 面の点（各四角を 6 × 6 の双線形の点で）
    k = 6
    uu = (np.arange(k) + 0.5) / k
    for r in range(R - 1):
        a, b, c_, d = P[r, :-1], P[r + 1, :-1], P[r, 1:], P[r + 1, 1:]
        for s in uu:
            for t in uu:
                q = (1 - s) * (1 - t) * a + s * (1 - t) * b + (1 - s) * t * c_ + s * t * d
                ii = np.floor((q - lo) / vox).astype(int)
                occ[ii[:, 0], ii[:, 1], ii[:, 2]] = True
    for q in (P.reshape(-1, 3),):
        ii = np.floor((q - lo) / vox).astype(int)
        occ[ii[:, 0], ii[:, 1], ii[:, 2]] = True
    occ = ndimage.binary_dilation(occ, structure=np.ones((3, 3, 3), bool))
    rng = np.random.default_rng(31)
    # AO の方向（局所の半球、余弦の重み）
    nA = 32
    u1 = (np.arange(nA) + 0.5) / nA
    u2 = np.mod(np.arange(nA) * 0.6180339887, 1.0)
    rr_ = np.sqrt(u1); ph = 2 * np.pi * u2
    locd = np.stack([rr_ * np.cos(ph), rr_ * np.sin(ph), np.sqrt(1 - u1)], -1)
    # 光の円錐
    L = S.LIGHT
    nK = 8
    tmp = np.array([0.0, 0.0, 1.0]) if abs(L[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    e1 = S.unit(np.cross(L, tmp)); e2 = np.cross(L, e1)
    ang = np.radians(3.0)
    kd = [L]
    for i in range(nK - 1):
        th = 2 * np.pi * i / (nK - 1)
        kd.append(S.unit(L * np.cos(ang) + np.sin(ang) * (np.cos(th) * e1 + np.sin(th) * e2)))
    kd = np.array(kd)
    Pf = P.reshape(-1, 3); Nf = N.reshape(-1, 3)
    nv = Pf.shape[0]
    ao = np.ones(nv); kv = np.ones(nv)
    off = 0.6
    stepA, maxA = 0.25, 10.0
    stepK, maxK = 0.3, 60.0
    tA = np.arange(stepA, maxA, stepA)
    tK = np.arange(stepK, maxK, stepK)

    def hit(orig, dirs, ts):
        # orig: (B, 3)、dirs: (B, D, 3)、ts: (T,) → 当たったか (B, D)
        Bn, D = dirs.shape[:2]
        out = np.zeros((Bn, D), bool)
        for t0_ in range(0, len(ts), 16):
            tt = ts[t0_:t0_ + 16]
            pts = orig[:, None, None, :] + dirs[:, :, None, :] * tt[None, None, :, None]
            ii = np.floor((pts - lo) / vox).astype(np.int32)
            inside = np.all((ii >= 0) & (ii < dims), axis=-1)
            ii = np.clip(ii, 0, dims - 1)
            o = occ[ii[..., 0], ii[..., 1], ii[..., 2]] & inside
            out |= o.any(-1)
        return out

    B = 1500
    for b0 in range(0, nv, B):
        sl = slice(b0, min(nv, b0 + B))
        p = Pf[sl]; n = Nf[sl]
        # 局所の枠（頂点ごとにまわりの向きを少し回して縞を避ける）
        t1 = S.unit(np.cross(n, np.where(np.abs(n[:, 1:2]) < 0.9, np.array([[0.0, 1.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))))
        t2 = np.cross(n, t1)
        rot = rng.uniform(0, 2 * np.pi, size=(p.shape[0], 1))
        ca, sa = np.cos(rot), np.sin(rot)
        a1 = ca * t1 + sa * t2; a2 = -sa * t1 + ca * t2
        dirs = locd[None, :, 0:1] * a1[:, None, :] + locd[None, :, 1:2] * a2[:, None, :] + locd[None, :, 2:3] * n[:, None, :]
        orig = p + n * off
        hA = hit(orig, dirs, tA)
        ao[sl] = 1.0 - hA.mean(1)
        facing = (n @ L) > -0.05
        dK = np.broadcast_to(kd[None], (p.shape[0], nK, 3))
        hK = hit(orig, dK, tK)
        kv[sl] = np.where(facing, 1.0 - hK.mean(1), 0.0)
    ao = ao.reshape(R, C); kv = kv.reshape(R, C)
    # 格子の上で軽くならす（光線の数の粗さ）
    ao_s = ndimage.uniform_filter(ao, size=3, mode="nearest")
    kv_s = ndimage.uniform_filter(kv, size=3, mode="nearest")
    od = S.OUT + "/bake"
    os.makedirs(od, exist_ok=True)
    np.savez_compressed(od + "/hero_bake.npz", ao=ao_s.astype(np.float32), kv=kv_s.astype(np.float32))
    rec = {"schema": "GreatWave.AS03.surf_bake/1", "seconds": round(time.time() - t0, 1), "voxel_m": vox, "dims": dims.tolist(),
           "occupied": int(occ.sum()), "ao_rays": nA, "ao_max_m": maxA, "key_rays": nK, "key_cone_deg": 3.0, "key_max_m": maxK, "offset_m": off,
           "light": S.LIGHT.tolist(), "hero_pkg": S.HERO_PKG, "attr_sha256": S.sha(S.ATTR),
           "ao_pct": {q: float(np.percentile(ao_s, q)) for q in (5, 25, 50, 75, 95)},
           "kv_frac_lit": float((kv_s > 0.5).mean()), "npz_sha256": S.sha(od + "/hero_bake.npz"),
           "noteJa": "主役波だけの遮り（海・船・冠は入れていない）。視点によらない。原画カメラは使わない。"}
    S.jdump(od + "/hero_bake.json", rec)
    print(rec["seconds"], rec["ao_pct"], rec["kv_frac_lit"], dims)


if __name__ == "__main__":
    main()
