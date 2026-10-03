# -*- coding: utf-8 -*-
"""美術の見本01・見本 A（彫刻のような刻み）：材質 S01A Groove Keypose が読む、頂点ごとの 12 個の属性を作る。

入力は、仕上げ29 の面の座標（pl29_hero_attr.py --param arc の出力：F・hrel・hrow・c・t* の法線）と、
美術の見本01 の面の座標（s01_param.py の出力：巻きの向きの弧長 u・頂に並ぶ向きの座標 w・|∇w|・|∇u|・使ってよさ q）。
原画カメラの投影は使わない。参照モデルの OBJ は読まない。
出力（PL29UkiyoeHero がそのまま読める 12 個／頂点の並び。UV3 = A、UV4 = B、UV5 = C）：
  A = (F 流れの座標, hrel 行の相対の高さ, u 巻きの向きの弧長 [m], w 頂に並ぶ向きの座標 [m])
  B = (gw |∇w|, hrow 行の頂の高さ／H0, X.x, X.y)
  C = (t* の法線 xyz, X.z)      X は t* の頂に並ぶ向き（波の枠＝ワールド、単位。溝の壁の向きと固定の光から、視点によらない陰の側を決める）
使い方：py -3.10 -B Tools/GWWaveGen/sample01/s01a_attr.py --attr <pl29_hero_attr_f32.bin> --param <s01_param_f32.bin> --out <dir>

v2（a7、--v2 --gwb <.gwb> を付ける。出力 s01a_hero_attr_v2_f32.bin。材質の _AttrV2 = 1 で読む）：
  B = (gw, hrow, Ls 溝の本数の段, X·L̂)、C = (t* の法線 xyz, 0)
  Ls：log2(1/gw) を面の上で半径 R（--lod-smooth-m、既定 2 m）の重みで平らにしたもの（有限要素の (M + R² K) Ls = M log2(1/gw)）。
      生の gw で本数を変えると、gw が閾値をわずかに下回る小さな島ごとに溝が生まれては消え、Y 字の股が目の形の輪になった（a6 の原画視点の左の胴）。
      平らにすると、本数の変わる所が少数のまとまった帯になる。溝の幅（3 次元で一定に保つ）は生の gw のまま。
  X·L̂：X（頂に並ぶ向き）と、材質の固定の光の向き L̂（--light、既定は値の表の _LightDir (−0.45, 0.75, −0.5)）の内積。
      材質は溝の陰の縁の側をこの符号だけで決める（X は内積の符号にしか使っていなかったので、2 つの席を空けた）。
"""
import argparse
import hashlib
import json
import os

import numpy as np


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--attr", required=True)
    ap.add_argument("--param", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--v2", action="store_true")
    ap.add_argument("--gwb", default="Unity/Build/Polish/28/kstar_p28rec/kstarP28R2rec_a45.gwb")
    ap.add_argument("--lod-smooth-m", type=float, default=2.0)
    ap.add_argument("--light", default="-0.45,0.75,-0.5")
    a = ap.parse_args()
    at = np.fromfile(a.attr, np.float32).reshape(-1, 12)
    pr = np.fromfile(a.param, np.float32).reshape(-1, 8)
    if at.shape[0] != pr.shape[0]:
        raise ValueError("頂点の数が違う")
    F, hrel, hrow = at[:, 0], at[:, 1], at[:, 3]
    c = at[:, 5]
    n = at[:, 8:11]
    u, w, gu, gw, q = pr[:, 0], pr[:, 1], pr[:, 2], pr[:, 3], pr[:, 7]
    X = pr[:, 4:7]
    extra = {}
    if a.v2:
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla
        from s01_param import load_gwb, grad_operator
        nu, nv, _uv, _uv2, tri, pos = load_gwb(a.gwb)
        if nu * nv != at.shape[0]:
            raise ValueError(".gwb の頂点の数が違う")
        G, A, _nt = grad_operator(pos, tri)
        K = (G.T @ sp.diags(np.repeat(A, 3)) @ G).tocsc()
        mv = np.zeros(nu * nv); np.add.at(mv, tri.reshape(-1), np.repeat(A / 3.0, 3)); mv = np.maximum(mv, 1e-12)
        lv = np.log2(1.0 / np.maximum(gw.astype(np.float64), 1e-3))
        R = a.lod_smooth_m
        Ls = spla.splu((sp.diags(mv) + R * R * K).tocsc()).solve(mv * lv) if R > 0 else lv
        L = np.array([float(x) for x in a.light.split(",")]); L = L / np.linalg.norm(L)
        xl = X.astype(np.float64) @ L
        out = np.stack([F, hrel, u, w, gw, hrow, Ls, xl, n[:, 0], n[:, 1], n[:, 2], np.zeros_like(F)], -1).astype(np.float32)
        extra = {"v2": True, "gwb": a.gwb.replace("\\", "/"), "gwb_sha256": sha256(a.gwb), "lod_smooth_m": R, "light_unit": [round(float(x), 6) for x in L],
                 "Ls_range": [float(Ls.min()), float(Ls.max())], "lv_range": [float(lv.min()), float(lv.max())]}
    else:
        out = np.stack([F, hrel, u, w, gw, hrow, X[:, 0], X[:, 1], n[:, 0], n[:, 1], n[:, 2], X[:, 2]], -1).astype(np.float32)
    if not np.all(np.isfinite(out)):
        raise ValueError("NaN／Inf がある")
    os.makedirs(a.out, exist_ok=True)
    bp = os.path.join(a.out, "s01a_hero_attr_v2_f32.bin" if a.v2 else "s01a_hero_attr_f32.bin")
    out.tofile(bp)
    rec = {
        "schema": "GreatWave.Sample01.texA.hero_attr/1",
        "noteJa": __doc__.strip().split("\n")[0],
        "layoutJa": ("頂点ごとの float32 × 12：A = (F, hrel, u, w)、B = (gw, hrow, Ls 溝の本数の段, X·L̂)、C = (t* の法線 xyz, 0)。UV3 = A、UV4 = B、UV5 = C。材質の _AttrV2 = 1"
                     if a.v2 else "頂点ごとの float32 × 12：A = (F, hrel, u, w)、B = (gw, hrow, X.x, X.y)、C = (t* の法線 xyz, X.z)。UV3 = A、UV4 = B、UV5 = C"),
        "v2": extra,
        "inputs": {"attr": a.attr.replace("\\", "/"), "attr_sha256": sha256(a.attr), "param": a.param.replace("\\", "/"), "param_sha256": sha256(a.param)},
        "projection_used": False,
        "output": {"path": bp.replace("\\", "/"), "sha256": sha256(bp), "bytes": os.path.getsize(bp), "vertices": int(out.shape[0]), "floats_per_vertex": 12},
    }
    with open(os.path.join(a.out, "s01a_hero_attr_v2.json" if a.v2 else "s01a_hero_attr.json"), "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(rec["output"]["sha256"])


if __name__ == "__main__":
    main()
