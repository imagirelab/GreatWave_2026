# -*- coding: utf-8 -*-
"""仕上げ28：M10（側面 t 4〜6.5 s の平らな頂の塊）の直しの下調べ。生成器（試行F、G_final と同じ条件）を 1 つのプロセスで作り、
頂の帽子（ds27 の crest_cap、E の lean_with_height.cap_knots：背の頂の近くの下がりを縦に縮める。古い K* の尖った塔を丸めるために入れた）
の強さ ω を k 倍にした時の、形成の途中の形を数える（包みは作らない。試し）。
数えるもの：側面の包絡の塊の読み（pl28_loaf.loaf_metrics）、主断面・峰の行の頂の角 θc（ds27_gates.row_metrics）、全部の本体の行の
±2 m の弦の角（唇ができる前）の最小と 110° 以下の行の数。
使い方：py -3.10 -B Tools/GWWaveGen/pl28/pl28_probe_cap.py --package Unity/Build/Polish/28/G_final/art_on --k 1,0.5,0.25,0 --out <json>
"""
import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "ds28r01f"))
sys.path.insert(0, HERE)
import pl28_loaf as LF  # noqa: E402
import pl28_fr_motion_lib as FM  # noqa: E402


class Scaled:
    def __init__(self, f, k):
        self.f, self.k = f, float(k)

    def __call__(self, x):
        return self.k * self.f(x)


def setup(pkg):
    import ds28r01f_generate as GEN
    import ds28r01f_pkglog as PL
    L = json.load(open(os.path.join(pkg, "ds28r01f_generate_log.json"), encoding="utf-8"))["result"]
    work = os.path.join(pkg, "_work")
    sl = (L.get("scan") or {}).get("small_lip_body") or {}
    stage = dict(nr=os.path.join(work, "nr_cache_small_lip.npz") if sl.get("rows") else os.path.join(work, "nr_cache.npz"),
                 delip=tuple(sl.get("rows") or ()), gw=os.path.join(work, "guard_window.npz") if os.path.isfile(os.path.join(work, "guard_window.npz")) else None,
                 bridge=os.path.join(work, "bridge.npz") if os.path.isfile(os.path.join(work, "bridge.npz")) else None, layers=None)
    GEN._winit(os.path.join(REPO, L["kstar"]["dir"]), L.get("overrides"), PL.package_off(L))
    GEN._ensure(stage)
    return GEN._G, L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--k", default="1,0.5,0.25,0")
    ap.add_argument("--taus", default="-3.894,-3.49,-3.2,-2.95,-2.7,-2.45,-2.2,-1.95")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    pkg = a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package)
    g, L = setup(pkg)
    T = np.asarray(g.K.src["meta"]["frame"]["t_travel"], float) if hasattr(g.K, "src") and g.K.src.get("meta") else None
    if T is None:
        meta = json.load(open(os.path.join(REPO, L["kstar"]["dir"], [f for f in os.listdir(os.path.join(REPO, L["kstar"]["dir"])) if f.endswith("_meta.json")][0]), encoding="utf-8"))
        T = np.asarray(meta["frame"]["t_travel"], float)
    base = g.tab_cap
    taus = [float(x) for x in a.taus.split(",")]
    res = dict(package=os.path.relpath(pkg, REPO).replace("\\", "/"), taus=taus, cap_at_tau_main=None, k={})
    X0 = g.local(0.0)
    a0 = X0[164] @ T
    sign = 1.0 if a0[200] > a0[int(np.argmax(X0[164, 18:394, 1])) + 18] else -1.0
    for k in [float(x) for x in a.k.split(",")]:
        g.tab_cap = Scaled(base, k)
        rows = {}
        for tau in taus:
            X = g.local(tau)
            lm = LF.loaf_metrics(X, T, sign)
            A = (X @ T) * sign
            Y = X[..., 1]
            ch = np.asarray(FM.crest_chord(A, Y), float)
            lo = np.array([FM.lo_ratio(A, Y, r, 1.0) for r in range(A.shape[0])])
            H = Y[:, 18:395].max(1)
            body = (H > 3.0) & (lo < 0.05) & np.isfinite(ch)
            rows["%+.3f" % tau] = dict(loaf=lm, chord_main=round(float(ch[164]), 1), chord_peak=round(float(ch[183]), 1),
                                       chord_body_min=round(float(ch[body].min()), 1) if body.any() else None,
                                       chord_body_argmin=int(np.nonzero(body)[0][np.argmin(ch[body])]) if body.any() else None,
                                       rows_le110=int((body & (ch <= 110)).sum()), rows_le125=int((body & (ch <= 125)).sum()))
            print("k", k, "tau", tau, rows["%+.3f" % tau], flush=True)
        res["k"]["%.2f" % k] = rows
    g.tab_cap = base
    res["cap_omega_by_sigma"] = {"%.1f" % s: round(float(base(s)), 3) for s in (-6.0, -4.8, -4.0, -3.4, -2.4, -1.4, -0.5, 0.0)}
    res["sign"] = sign
    res["seconds"] = round(time.time() - t0, 1)
    out = a.out if os.path.isabs(a.out) else os.path.join(REPO, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
