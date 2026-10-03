# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2）組み立て：背を直した候補 K*′ AS02B の見本 A の面の座標を、形の変わらない頂点で前（P28R2rec）と同じ値に留める。

AS02B は原画カメラから見える頂点（と周りの帯）を動かしていない。ところが面の座標 u・w（s01_param.py）は面全体の 1 回の解なので、
背が変わると、動いていない前面の w も p50 0.09 m・p99 0.46 m ずれ、原画視点の溝の位置が周期の一部だけずれる（形は同じなのに模様が変わる）。
見本の比べ（原画視点の前と今）を形の違いだけにするため、次のように作る（どれも頂点の値、原画カメラの投影は使わない）：
  1. 動いていない頂点（AS02B と P28R2rec の t* の位置の差 ≤ --tol m）：u・w・F・X は前の値のまま。
  2. 動いた頂点：今の解の値に、ずれ δ = 前 − 今 を動いていない頂点から調和に延ばした値（面の上の余接ラプラシアン K = Gᵀ diag(A) G の
     ディリクレ問題）を足す。δ は滑らかなので、溝の間隔（|∇w|）はほとんど変わらない（記録に |∇w| の変化を書く）。
  3. gu・gw は直した u・w から s01_param.py と同じ式（三角形の勾配の大きさを面積で重みを付けて頂点へ平均）で作り直す。
     q は前の値（行の頂の高さで決まり、AS02B は H(c) を変えない）。法線と hrel・hrow・c などのほかの属性は今（AS02B）の値。
出力は s01_param.py・pl29_hero_attr.py と同じ並びの 2 つのファイル。続けて s01a_attr.py --v2 --gwb <AS02B> で見本 A の属性を作る。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_asm_attr_pin.py --gwb-old <P28R2rec .gwb> --gwb-new <AS02B .gwb>
    --param-old <s01_param_f32.bin> --param-new <…> --attr-old <pl29_hero_attr_f32.bin> --attr-new <…> --out <dir>
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/sample01")
from s01_param import load_gwb, grad_operator  # noqa: E402


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def vgrad(G, A, tri, N, f):
    g = np.linalg.norm((G @ f).reshape(-1, 3), axis=1)
    acc = np.zeros(N); acc_a = np.zeros(N)
    for k in range(3):
        np.add.at(acc, tri[:, k], g * A); np.add.at(acc_a, tri[:, k], A)
    return acc / np.maximum(acc_a, 1e-30)


def main():
    ap = argparse.ArgumentParser()
    for k in ("gwb-old", "gwb-new", "param-old", "param-new", "attr-old", "attr-new", "out"):
        ap.add_argument("--" + k, required=True)
    ap.add_argument("--tol", type=float, default=1e-3)
    a = ap.parse_args()
    nu, nv, _, _, tri, P0 = load_gwb(a.gwb_old)
    nu1, nv1, _, _, tri1, P1 = load_gwb(a.gwb_new)
    if (nu, nv) != (nu1, nv1) or not np.array_equal(tri, tri1):
        raise ValueError("格子か三角形が違う")
    N = nu * nv
    po = np.fromfile(a.param_old, np.float32).reshape(N, 8).astype(np.float64)
    pn = np.fromfile(a.param_new, np.float32).reshape(N, 8).astype(np.float64)
    ao = np.fromfile(a.attr_old, np.float32).reshape(N, 12)
    an = np.fromfile(a.attr_new, np.float32).reshape(N, 12)
    mv = np.linalg.norm(P1 - P0, axis=1)
    fixed = mv <= a.tol
    m = np.nonzero(~fixed)[0]; f = np.nonzero(fixed)[0]
    G, A, _ = grad_operator(P1, tri)
    K = (G.T @ sp.diags(np.repeat(A, 3)) @ G).tocsr()
    Kmm = K[m][:, m].tocsc(); Kmf = K[m][:, f]
    lu = spla.splu(Kmm)

    def pin(old, new):
        d = old - new
        out = old.copy()
        dm = lu.solve(-(Kmf @ d[f]))
        out[m] = new[m] + dm
        return out, dm

    u, du = pin(po[:, 0], pn[:, 0])
    w, dw = pin(po[:, 1], pn[:, 1])
    gu = vgrad(G, A, tri, N, u)
    gw = vgrad(G, A, tri, N, w)
    gw_new_raw = vgrad(G, A, tri, N, pn[:, 1])
    X = po[:, 4:7].copy(); X[m] = pn[m, 4:7]
    q = po[:, 7]
    outp = np.stack([u, w, gu, gw, X[:, 0], X[:, 1], X[:, 2], q], -1).astype(np.float32)
    F, dF = pin(ao[:, 0].astype(np.float64), an[:, 0].astype(np.float64))
    outa = an.copy(); outa[:, 0] = F.astype(np.float32)
    for name, arr in (("param", outp), ("attr", outa)):
        if not np.all(np.isfinite(arr)):
            raise ValueError("NaN／Inf: " + name)
    os.makedirs(a.out, exist_ok=True)
    pp = os.path.join(a.out, "s01_param_f32.bin"); outp.tofile(pp)
    pa = os.path.join(a.out, "pl29_hero_attr_f32.bin"); outa.tofile(pa)
    # 記録
    ratio = gw[m] / np.maximum(gw_new_raw[m], 1e-9)
    rec = {
        "schema": "GreatWave.AS02.asm_attr_pin/1",
        "noteJa": __doc__.strip().split("\n")[0],
        "methodJa": __doc__.strip(),
        "inputs": {k: {"path": getattr(a, k.replace("-", "_")).replace("\\", "/"), "sha256": sha256(getattr(a, k.replace("-", "_")))}
                   for k in ("gwb-old", "gwb-new", "param-old", "param-new", "attr-old", "attr-new")},
        "tol_m": a.tol,
        "vertices": {"total": int(N), "fixed": int(fixed.sum()), "moved": int(m.size), "moved_max_m": float(mv.max())},
        "fixed_vertices_equal_old": {"u_w_maxabs": float(max(np.abs(outp[f, 0] - po[f, 0]).max(), np.abs(outp[f, 1] - po[f, 1]).max())),
                                     "gw_maxabs_vs_old": float(np.abs(gw[f] - po[f, 3]).max()),
                                     "gw_p99abs_vs_old": float(np.percentile(np.abs(gw[f] - po[f, 3]), 99))},
        "delta_on_moved_m": {"u_absmax": float(np.abs(du).max()), "w_absmax": float(np.abs(dw).max()), "w_p50abs": float(np.median(np.abs(dw))),
                             "F_absmax": float(np.abs(dF).max())},
        "gw_moved_ratio_vs_unpinned_p1_p50_p99": [float(np.percentile(ratio, 1)), float(np.median(ratio)), float(np.percentile(ratio, 99))],
        "projection_used": False,
        "outputs": {"param": {"path": pp.replace("\\", "/"), "sha256": sha256(pp)}, "attr": {"path": pa.replace("\\", "/"), "sha256": sha256(pa)}},
    }
    with open(os.path.join(a.out, "as02_asm_attr_pin.json"), "w", encoding="utf-8", newline="\n") as fo:
        json.dump(rec, fo, ensure_ascii=False, indent=1)
    print(json.dumps({k: rec[k] for k in ("vertices", "fixed_vertices_equal_old", "delta_on_moved_m", "gw_moved_ratio_vs_unpinned_p1_p50_p99")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
