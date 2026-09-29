# -*- coding: utf-8 -*-
"""設計28修正01 試行F：生成器を作る時に決まる当て直し（ds_back_width_retarget・ds_anchor_retarget・ds_far_hook_early）の大きさ（P20）を、
生成の後に同じ条件の生成器で測る（記録）。--name で選ぶ（既定 back_width_retarget）。

生成（ds28r01f_generate.py）の P20 は、こまごとに切れる層（t*・隙間・橋渡し）と、唇の強さ・背の差し替えを測る。背の幅の表の当て直し
（ds_back_width_retarget、_shared の中の Lb′ = 1 + (Lb − 1)·ρ）はそこでは切っていない（記録では 0 と出るが、測っていない）。
この台本は、生成の記録（ds28r01f_generate_log.json）から同じ条件（num_no_rebound_after_apex の格子・small_lip_body の行・窓・橋渡し）を
読み、ρ を 1 に戻した形（水の釣り合いの山 ΔL の当てはめは入れた版のまま：近似）との頂点の差の最大を、生成の P20 と同じ時刻で測る。
使い方（リポジトリの根で）：
  py -3.10 -B Tools/GWWaveGen/ds28r01f/ds28r01f_p20.py --package Unity/Build/Design/28R01F/F_R2/art_on [--workers 12] [--name anchor_retarget]
出力：<パッケージ>/p20_<name>.json
ds_anchor_retarget：E の q_on に戻して始まりの時の管の天井の形などを作り直した形（num_no_rebound_after_apex の格子は入れた版のまま：近似）。
ds_far_hook_early：ψ_b を E の ease-in に戻した形。
"""
import os

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import multiprocessing as mp  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import ds28r01f_generate as GEN  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _t_width(args):
    tau, stage, name = args
    GEN._ensure(stage)
    g = GEN._G
    t = float(min(tau, 0.0))
    X1 = g.local(t)
    if name == "back_width_retarget":
        rho = g._rho_w
        g._rho_w = None
        try:
            X0 = g.local(t)
        finally:
            g._rho_w = rho
    elif name == "anchor_retarget":
        g.set_anchor_retarget(False)
        try:
            X0 = g.local(t)
        finally:
            g.set_anchor_retarget(True)
    elif name == "far_hook_early":
        hk = g._hook_on
        g._hook_on = False
        try:
            X0 = g.local(t)
        finally:
            g._hook_on = hk
    else:
        raise ValueError(name)
    d = np.linalg.norm(X1 - X0, axis=-1)
    k = int(np.argmax(d))
    return tau, float(d.max()), int(k // d.shape[1]), int(k % d.shape[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--package", required=True)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--name", default="back_width_retarget", choices=("back_width_retarget", "anchor_retarget", "far_hook_early"))
    a = ap.parse_args()
    import ds28r01f_proc
    ds28r01f_proc.opt_out()
    pkg = a.package if os.path.isabs(a.package) else os.path.join(REPO, a.package)
    L = json.load(open(os.path.join(pkg, "ds28r01f_generate_log.json"), encoding="utf-8"))
    R = L["result"]
    kdir = os.path.join(REPO, R["kstar"]["dir"])
    work = os.path.join(pkg, "_work")
    sl = (R.get("scan") or {}).get("small_lip_body") or {}
    nr = os.path.join(work, "nr_cache_small_lip.npz") if sl.get("rows") else os.path.join(work, "nr_cache.npz")
    gw = os.path.join(work, "guard_window.npz")
    br = os.path.join(work, "bridge.npz")
    stage = dict(nr=nr, delip=tuple(sl.get("rows") or ()), gw=gw if os.path.isfile(gw) else None, bridge=br if os.path.isfile(br) else None, layers=None)
    t0 = time.time()
    ptaus = [round(float(t), 9) for t in np.concatenate([np.arange(-9.5, -3.0 + 1e-9, 0.25), np.arange(-2.95, 1e-9, 0.05)])]
    with mp.get_context("spawn").Pool(a.workers, initializer=GEN._winit, initargs=(kdir, R.get("overrides"), R.get("off") or [])) as pool:
        res = list(pool.imap(_t_width, [(t, stage, a.name) for t in ptaus], chunksize=2))
    best = max(res, key=lambda x: x[1])
    notes = dict(back_width_retarget="ρ を 1 に戻した形（E の背の幅の表のまま。水の釣り合いの山 ΔL の当てはめは入れた版のまま＝近似）と、生成と同じ F の形との頂点の差（局所座標）",
                 anchor_retarget="内壁の錨の始まりの位置 q_on を E の min(q_帯, q*) に戻し、始まりの時の管の天井の形などを作り直した形（num_no_rebound_after_apex の格子・水の釣り合いの当てはめは入れた版のまま＝近似）と、生成と同じ F の形との頂点の差（局所座標）",
                 far_hook_early="上の前面の混ぜの重み ψ_b を E の ease-in（σ −3.4〜0）に戻した形と、生成と同じ F の形との頂点の差（局所座標）")
    out = dict(name="ds_" + a.name, kstar=R["kstar"]["dir"], stage={k: (os.path.relpath(v, REPO).replace("\\", "/") if isinstance(v, str) else v)
                                                                            for k, v in stage.items()},
               max_vertex_diff_m=best[1], at=dict(tau=best[0], row=best[2], col=best[3]),
               per_tau={"%+.2f" % t: round(m, 4) for t, m, _, _ in res}, seconds=round(time.time() - t0, 1),
               note_ja=notes[a.name])
    with open(os.path.join(pkg, "p20_%s.json" % a.name), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "per_tau"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
