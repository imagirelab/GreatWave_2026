# -*- coding: utf-8 -*-
"""仕上げ30：仮置き M1_Revision_LeftSupport（左奥の船 boat_left を載せた平らなクリーム色の板）の置き換え。

名前の付いた美術の誘導 pl30_left_swell：左奥の船の船底の線の下に、船と同じ向きの細長い水の盛り上がり（船を載せる二次のうねり）を置く。
- 形：船底（Unity の場面の boat_left の網の、船の軸に沿う最も低い点の線を直線で当てはめたもの）＋ 喫水 0.55 m の高さを、船の幅の 1.1 m の内は保ち、
  その外は 4 m で cos² で 0 へ落とす。船首の先は 5 m、船尾の先は 3 m で 0 へ。底は y = 0（周りは主役波の管の床 0〜0.8 m）。
- 時間：盛り上がりの高さ = m(τ)·形、m は τ −2.6 → 0 s で 0 → 1（smootherstep）。左奥の船は (m − 1)·lift_m だけ下げる（t* で 0。前は平らな海に近い高さ）。
  （設計43 の限界 9：t* より前に浮く・沈む左奥の船の食い違いを、仮置きの板の代わりに水の盛り上がりの上がり方で受ける）
- 色：周りの海と同じ材質（PL30 Ukiyoe Sea Keypose、kind 2＝小波の白の頂の閾値と房）。面の座標は頂点ごとの 20 個（修正01。pl30_sea_attr.py と同じ並び。作る部は 12 個）。
入力：Unity/Build/Polish/30/dump/pl30_scene_dump.json（PL30Dump が場面から書いた boat_left の網と仮置きの頂点。数値だけ）
出力：<out>/pl30_left_swell.json（頂点・三角形・面の座標・m(τ)・船の下げ）
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pl30_sea as S  # noqa: E402

REPO = S.REPO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default="Unity/Build/Polish/30/dump/pl30_scene_dump.json")
    ap.add_argument("--out", default="Unity/Build/Polish/30/left_swell")
    ap.add_argument("--draft", type=float, default=0.55)
    ap.add_argument("--flat", type=float, default=1.1)
    ap.add_argument("--fall", type=float, default=4.0)
    ap.add_argument("--bow-ext", type=float, default=5.0)
    ap.add_argument("--stern-ext", type=float, default=3.0)
    ap.add_argument("--tau0", type=float, default=-2.6)
    args = ap.parse_args()
    d = S.load_json(os.path.join(REPO, args.dump))
    bl = [o for o in d["objects"] if o["name"].endswith("boat_left")][0]
    V = np.array(bl["worldVertices"], np.float64).reshape(-1, 3)
    xz = V[:, [0, 2]]
    c0 = xz.mean(0)
    _, _, vt = np.linalg.svd(xz - c0)
    ax = vt[0]
    if ax[0] < 0:
        ax = -ax
    lat = np.array([-ax[1], ax[0]])
    pr = (xz - c0) @ ax
    pl = (xz - c0) @ lat
    s0, s1 = float(pr.min()), float(pr.max())
    beam = float(max(abs(pl.min()), abs(pl.max())))
    # 船底の線：軸に沿う 0.5 m の帯ごとの最も低い点に直線を当てる
    qs = np.linspace(s0 + 0.3, s1 - 0.3, 15)
    yb = np.array([V[np.abs(pr - q) < 0.5, 1].min() for q in qs])
    k, b = np.polyfit(qs, yb, 1)
    bow_is_low_s = k > 0      # 高い側が船首
    # 網
    ext_lo = args.stern_ext if bow_is_low_s else args.bow_ext
    ext_hi = args.bow_ext if bow_is_low_s else args.stern_ext
    ss = np.linspace(s0 - ext_lo, s1 + ext_hi, 61)
    ll = np.linspace(-(args.flat + args.fall + 0.2), args.flat + args.fall + 0.2, 31)
    SS, LL = np.meshgrid(ss, ll, indexing="ij")
    H = k * np.clip(SS, s0, s1) + b + args.draft
    endw = np.ones_like(SS)
    endw = np.where(SS < s0, np.cos(0.5 * math.pi * np.clip((s0 - SS) / ext_lo, 0, 1)) ** 2, endw)
    endw = np.where(SS > s1, np.cos(0.5 * math.pi * np.clip((SS - s1) / ext_hi, 0, 1)) ** 2, endw)
    latw = np.where(np.abs(LL) <= args.flat, 1.0, np.cos(0.5 * math.pi * np.clip((np.abs(LL) - args.flat) / args.fall, 0, 1)) ** 2)
    Y = H * endw * latw
    P = np.zeros(SS.shape + (3,))
    P[..., 0] = c0[0] + SS * ax[0] + LL * lat[0]
    P[..., 2] = c0[1] + SS * ax[1] + LL * lat[1]
    P[..., 1] = Y
    R, C = SS.shape
    r, c = np.meshgrid(np.arange(R - 1), np.arange(C - 1), indexing="ij")
    a_ = (r * C + c).ravel(); b_ = ((r + 1) * C + c).ravel(); c_ = (r * C + c + 1).ravel(); d_ = ((r + 1) * C + c + 1).ravel()
    tris = np.stack([np.stack([a_, b_, c_], 1), np.stack([c_, b_, d_], 1)], 1).reshape(-1, 3)
    # 上を向くように（外積の y が負なら並びを逆に）
    fn = np.cross(P.reshape(-1, 3)[tris[:, 1]] - P.reshape(-1, 3)[tris[:, 0]], P.reshape(-1, 3)[tris[:, 2]] - P.reshape(-1, 3)[tris[:, 0]])
    if (fn[:, 1] < 0).mean() > 0.5:
        tris = tris[:, [0, 2, 1]]
    # 法線
    dr = np.gradient(P, axis=0); dc = np.gradient(P, axis=1)
    n = np.cross(dc, dr)
    n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    n = np.where(n[..., 1:2] < 0, -n, n)
    hcr = np.maximum(H * endw, 0.0)
    # 面の座標：修正01 の 20 個の並び（pl30_sea_attr.py と同じ。稜の系として船の軸に平行な溝を描き、白にはしない）
    A = np.zeros(SS.shape + (20,), np.float32)
    A[..., 0] = LL                         # qR：船の軸からの横の距離（溝は船の軸に平行）
    A[..., 1] = SS * 1.0 + 300.0           # uR：軸に沿う弧長
    A[..., 2] = hcr                        # hR：その断面の頂の高さ
    A[..., 3] = 0.4                        # wR（< 0.5：白にしない。船を載せる藍のうねり。溝の重みには効く）
    A[..., 4] = 50.0; A[..., 5] = 50.0     # 小波の系の座標（遠い＝属さない）
    A[..., 6] = 0.0; A[..., 7] = 0.0
    A[..., 8:11] = n
    A[..., 11] = 0.0
    A[..., 12] = np.abs(LL) + 20.0         # s
    A[..., 13] = SS * 1.0 + 300.0          # along（周期で閉じない網なので弧長のまま）
    A[..., 14] = 1.0e3; A[..., 15] = 0.0   # 谷の縁の座標（属さない）
    A[..., 16] = np.where(hcr > 1e-3, Y / np.maximum(hcr, 1e-3), 0.0)
    A[..., 17] = 0.0; A[..., 18] = 0.0; A[..., 19] = 0.0
    taus = np.linspace(-12.0, 0.0, 241)
    x = np.clip((taus - args.tau0) / (0.0 - args.tau0), 0.0, 1.0)
    m = x * x * x * (x * (6 * x - 15) + 10)
    lift = float(np.mean(k * qs + b) - 0.3)     # 船を下げる量（m = 0 で船底の平均が y 0.3 m 付近）
    rec = dict(schema="GreatWave.PL30.left_swell/1", number="仕上げ30", name="pl30_left_swell",
               note_ja=__doc__.split("\n\n")[0].strip() if __doc__ else "",
               boat=bl["name"], boat_axis_xz=ax.tolist(), boat_center_xz=c0.tolist(), boat_s_range=[s0, s1], boat_half_beam_m=beam,
               keel_fit=dict(slope=float(k), intercept=float(b), samples_s=qs.tolist(), samples_y=yb.tolist()),
               params=dict(draft=args.draft, flat=args.flat, fall=args.fall, bow_ext=args.bow_ext, stern_ext=args.stern_ext, tau0=args.tau0),
               rows=R, cols=C, floats_per_vertex=20, vertices_flat=P.reshape(-1).round(5).tolist(), triangles=tris.reshape(-1).tolist(),
               attr=A.reshape(-1).round(5).tolist(), tau=taus.tolist(), m=m.round(6).tolist(), boat_lift_m=lift,
               y_max_m=float(Y.max()), footprint_m2=float(((latw * endw) > 0.01).mean() * (ss[-1] - ss[0]) * (ll[-1] - ll[0])))
    out = os.path.join(REPO, args.out)
    os.makedirs(out, exist_ok=True)
    p = os.path.join(out, "pl30_left_swell.json")
    S.save_json(p, rec, indent=None)
    print("left swell", p, "rows", R, "cols", C, "ymax %.2f" % Y.max(), "lift %.2f" % lift, "keel slope %.3f" % k, "footprint %.1f m2" % rec["footprint_m2"], S.sha256_file(p))


if __name__ == "__main__":
    main()
