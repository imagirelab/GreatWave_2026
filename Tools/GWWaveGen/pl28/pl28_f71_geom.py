# -*- coding: utf-8 -*-
"""仕上げ28：F7-1（t 9〜11.5 s の波頭の模様の 1 コマだけの跳び）の原因の切り分けのうち、動き（包みの位置・精度の層・τ(t)）の側を数える。

描画を使わず、包み（ds27_pos_rgba16.bin ＋ 精度の層 ds27_pos_lo_rgba8.bin、再生器と同じ Hermite）と時間曲線 τ(t) から、
動画と同じ 30 fps のコマ（t = i/30）の頂点の位置を作り、原画のカメラ（kh_common.project_unity。Unity の DS27 painting と同じ）へ写して、
画面の上の頂点の動きがコマごとに滑らかか（行ったり戻ったりしないか）を数える。

数えるもの（コマ f、d_f = p_f − p_{f−1}（画面の px））：
  速さ |d_f|（px／コマ）の分布。
  向きの反転：cos(d_f, d_{f+1}) < 0 かつ |d_f|・|d_{f+1}| がどちらも 0.1 px より大きい頂点の数（画面の上の往復）。
  加速の比：|d_{f+1} − d_f| / max(|d_f|, 0.1 px) の p99（滑らかな動きなら小さい）。
  位置の段：1 コマの 2 階差分 |d_{f+1} − d_f|（px）の p99・最大。
  τ の段：r_f = (τ_f − τ_{f−1})·30 と、その差 |r_{f+1} − r_f|（τ(t) の折れ）。
対象の頂点：t* までに白になる頂点（T_white < 1e8。模様の白と淡い水色の縁がある所）のうち、画面の中にあり、粗い奥行きの格子（8 px の升目の
最も近い奥行き + 0.5 m 以内）で見えるもの。比べの窓は t 2〜9 s（跳びがほとんどない区間）と t 9〜11.5 s（F7-1 の区間）。
精度の層の分：同じ数を 16 bit だけの位置でも数え、差を書く（--no-fine を比べる代わりに両方を 1 回で）。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/pl28/pl28_f71_geom.py --package <包みの art_on> --warp <timewarp.json> --out <json> [--label 名前]
numpy だけを使う。重い処理と同時に回さない（包みを float32 で 2 通り持つので約 0.6 GB）。
"""
import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds27"))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "kstar_h"))
import ds27_gates as DG  # noqa: E402  hermite_weights（再生器と同じ式）
import kh_common as KC  # noqa: E402  原画のカメラ（Unity の DS27 painting と同じ）


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def absrepo(p):
    return p if os.path.isabs(p) else os.path.join(REPO, p)


def rel(p):
    return os.path.relpath(os.path.abspath(p), REPO).replace("\\", "/")


class Pkg:
    """ds27 の包み（16 bit と、あれば精度の層）。位置は波の枠の局所座標 ＋ 枠の原点 O(τ)（240 Hz 以上の標本の線形補間）。"""

    def __init__(self, d):
        self.dir = absrepo(d)
        J = json.load(open(os.path.join(self.dir, "ds27_keypose.json"), encoding="utf-8"))
        self.J = J
        L, nv, nu = int(J["layers"]), int(J["rows"]), int(J["cols"])
        self.L, self.nv, self.nu = L, nv, nu
        raw = np.fromfile(os.path.join(self.dir, "ds27_pos_rgba16.bin"), "<u2").reshape(L, nv * nu, 4)[..., :3]
        lo = np.asarray(J["bbox_min"], float)
        sz = np.asarray(J["bbox_size"], float)
        self.P16 = (lo + raw.astype(np.float64) / 65535.0 * sz).astype(np.float32)
        self.fine = False
        self.Pf = self.P16
        if J.get("pos_lo_file"):
            lo8 = np.fromfile(os.path.join(self.dir, J["pos_lo_file"]), np.uint8).reshape(L, nv * nu, 4)[..., :3]
            self.Pf = (self.P16.astype(np.float64) + (lo8.astype(np.float64) / 255.0 - 0.5) / 65535.0 * sz).astype(np.float32)
            self.fine = True
            del lo8
        del raw
        self.knots = np.asarray(J["knot_tau"], float)
        self.ftau = np.asarray(J["frame"]["tau"], float)
        self.forg = np.asarray(J["frame"]["origin"], float).reshape(-1, 3)
        self.tw = np.fromfile(os.path.join(self.dir, J.get("twhite_file", "ds27_twhite_r32f.bin")), "<f4").astype(np.float64)
        self.pos_sha = J.get("pos_sha256")

    def world(self, tau, fine=True):
        P = self.Pf if fine else self.P16
        idx, w = DG.hermite_weights(self.knots, [tau], 0)
        out = np.zeros((P.shape[1], 3))
        for q in range(4):
            if w[0, q] != 0.0:
                out += w[0, q] * P[idx[0, q]]
        o = np.array([np.interp(tau, self.ftau, self.forg[:, k]) for k in range(3)])
        return out + o


def visible_mask(sc, cell=8, tol=0.5):
    """粗い奥行きの格子：8 px の升目ごとの最も近い奥行きから tol m 以内の頂点を見えるとする（点の標本なので概算）。"""
    x, y, z = sc[:, 0], sc[:, 1], sc[:, 2]
    ins = (x >= 0) & (x < KC.CAM_W) & (y >= 0) & (y < KC.CAM_H) & (z > 0.1)
    cx = np.clip((x // cell).astype(np.int64), 0, KC.CAM_W // cell)
    cy = np.clip((y // cell).astype(np.int64), 0, KC.CAM_H // cell)
    key = cy * (KC.CAM_W // cell + 1) + cx
    zmin = np.full((KC.CAM_H // cell + 1) * (KC.CAM_W // cell + 1), np.inf)
    np.minimum.at(zmin, key[ins], z[ins])
    return ins & (z <= zmin[key] + tol)


def stats(v):
    v = np.asarray(v, float)
    if v.size == 0:
        return None
    return dict(n=int(v.size), p50=round(float(np.percentile(v, 50)), 4), p95=round(float(np.percentile(v, 95)), 4),
                p99=round(float(np.percentile(v, 99)), 4), max=round(float(v.max()), 4))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--warp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--t0", type=float, default=2.0)
    ap.add_argument("--t1", type=float, default=12.0)
    a = ap.parse_args()
    t_start = time.time()
    pk = Pkg(a.package)
    W = json.load(open(absrepo(a.warp), encoding="utf-8"))
    wt, wtau = np.asarray(W["t"], float), np.asarray(W["tau"], float)
    n0, n1 = int(round(a.t0 * a.fps)), int(round(a.t1 * a.fps))
    frames = np.arange(n0 - 1, n1 + 2)
    ts = frames / a.fps
    taus = np.interp(ts, wt, wtau)
    white = pk.tw < 1e8
    res = dict(schema="GreatWave.Polish28.f71_geom/1", label=a.label, package=rel(pk.dir), pos_sha256=pk.pos_sha, fine_layer=pk.fine,
               warp=rel(absrepo(a.warp)), warp_sha256=sha256_file(absrepo(a.warp)), fps=a.fps, frames=[int(frames[0]), int(frames[-1])],
               camera=dict(pos=KC.CAM_POS_U.tolist(), target=KC.CAM_TGT_U.tolist(), vfov_deg=KC.CAM_VFOV, w=KC.CAM_W, h=KC.CAM_H),
               white_vertices=int(white.sum()))
    per = {}
    for mode in ("fine", "hi16"):
        if mode == "hi16" and not pk.fine:
            continue
        S, V = [], []
        for tau in taus:
            sc = KC.project_unity(pk.world(float(tau), fine=(mode == "fine")))
            S.append(sc[:, :2].astype(np.float64))
            V.append(visible_mask(sc))
        S = np.stack(S)
        V = np.stack(V)
        d = np.diff(S, axis=0)                      # d[k] = S[k+1] − S[k]
        rows = []
        for k in range(1, len(frames) - 1):          # コマ f = frames[k]：d_f = d[k-1]、d_{f+1} = d[k]
            m = white & V[k - 1] & V[k] & V[k + 1]
            d0, d1 = d[k - 1][m], d[k][m]
            s0, s1 = np.linalg.norm(d0, axis=1), np.linalg.norm(d1, axis=1)
            both = (s0 > 0.1) & (s1 > 0.1)
            cos = np.einsum("ij,ij->i", d0, d1) / np.maximum(s0 * s1, 1e-12)
            acc = np.linalg.norm(d1 - d0, axis=1)
            rows.append(dict(frame=int(frames[k]), t=round(float(ts[k]), 4), tau=round(float(taus[k]), 5), n=int(m.sum()),
                             speed_p50=float(np.median(s0)) if s0.size else 0.0, speed_p95=float(np.percentile(s0, 95)) if s0.size else 0.0,
                             reversals=int((both & (cos < 0)).sum()), rev_gt_05px=int((both & (cos < 0) & (np.minimum(s0, s1) > 0.5)).sum()),
                             acc_p99=float(np.percentile(acc, 99)) if acc.size else 0.0, acc_max=float(acc.max()) if acc.size else 0.0,
                             acc_ratio_p99=float(np.percentile(acc / np.maximum(s0, 0.1), 99)) if acc.size else 0.0))
        per[mode] = rows
        del S, V, d
    # τ(t) の段
    r = np.diff(taus) * a.fps
    res["tau_rate"] = dict(t=[round(float(x), 4) for x in ts[1:]], r=[round(float(x), 5) for x in r],
                           max_step=round(float(np.abs(np.diff(r)).max()), 5), monotone=bool(np.all(np.diff(taus) >= -1e-12)))

    def window(rows, lo, hi):
        rr = [x for x in rows if lo <= x["t"] < hi]
        if not rr:
            return None
        return dict(t=[lo, hi], frames=len(rr), vertices_mean=round(float(np.mean([x["n"] for x in rr])), 1),
                    speed_p50_px=stats([x["speed_p50"] for x in rr]), speed_p95_px=stats([x["speed_p95"] for x in rr]),
                    reversals_sum=int(sum(x["reversals"] for x in rr)), reversals_max=int(max(x["reversals"] for x in rr)),
                    reversals_gt_05px_sum=int(sum(x["rev_gt_05px"] for x in rr)),
                    reversal_rate=round(float(sum(x["reversals"] for x in rr)) / max(1.0, float(sum(x["n"] for x in rr))), 6),
                    acc_p99_px=stats([x["acc_p99"] for x in rr]), acc_max_px=round(float(max(x["acc_max"] for x in rr)), 4),
                    acc_ratio_p99=stats([x["acc_ratio_p99"] for x in rr]))
    res["windows"] = {m: dict(t2_9=window(rows, 2.0, 9.0), t9_11p5=window(rows, 9.0, 11.5), t11p5_12=window(rows, 11.5, 12.0))
                      for m, rows in per.items()}
    res["per_frame"] = {m: [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in x.items()} for x in rows] for m, rows in per.items()}
    res["seconds"] = round(time.time() - t_start, 1)
    res["code_sha256"] = sha256_file(os.path.abspath(__file__))
    os.makedirs(os.path.dirname(absrepo(a.out)), exist_ok=True)
    with open(absrepo(a.out), "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res["windows"], ensure_ascii=False, indent=1))
    print("tau_rate max_step", res["tau_rate"]["max_step"], "seconds", res["seconds"])


if __name__ == "__main__":
    main()
