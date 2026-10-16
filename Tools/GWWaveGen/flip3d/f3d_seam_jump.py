# -*- coding: utf-8 -*-
"""FLIP3D：繰り返しの継ぎ目で、画面に実際に出る跳び（最後の記録 → 最初の記録）を測る（py -3.10 -B、numpy・scipy）。
2026-10-16 確かめのサブエージェントが足した。f3d_loop_ana.py の「継ぎ目の違い」は τ と τ + 12 s の面の違い（計算なら次に来る面との違い）で、
画面で見える跳び（τ + 12 s − 0.125 s の記録から τ の記録へ戻る）とは別の量。こちらは後者を、f3d_loop_ana.py と同じ物差しで測る。
  (a) 面と面の距離：片方の面の点で、もう片方の SDF（記録 r4、格子 1 m）を読んだ |d| の両向き（f3d_loop_ana.mesh_dist と同じ式・同じ箱）
  (b) 上の水面の高さの差 Δη（記録 hf）の RMS（崩れの所 x 225〜362 m）
  比べの物差し：窓の中のふつうの 1 歩（0.125 s）95 個の同じ値。
使い方：py -3.10 -B f3d_seam_jump.py   → Unity/Build/FLIP3D/loop/seam_jump.json（数の印：どれも【測定】）
"""
import os, sys, json, time
import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f3d_common as C   # noqa: E402
from f3d_loop_ana import mesh_dist, eta_stats   # noqa: E402


def main():
    man = json.load(open(C.OUT + "/clip_DA3_k5/manifest.json", encoding="utf8"))
    fr = man["source_frames"]
    r4 = C.Rec("r4"); hf = C.Rec("hf")
    meta = r4.meta
    lo = np.array([meta["x0"], meta["y0"], meta["z0"]])
    hi = lo + np.array([meta["dx"] * (meta["nx"] - 1), meta["dy"] * (meta["ny"] - 1), meta["dz"] * (meta["nz"] - 1)])
    xs, zs = C.axes_hf(hf.meta)
    MB = np.broadcast_to(((xs >= 225.0) & (xs <= 362.0))[None, :], (len(zs), len(xs)))
    P, S, E = {}, {}, {}

    def get(f):
        if f not in P:
            Q = C.read_surf(f)["P"]
            P[f] = Q[np.all((Q >= lo) & (Q <= hi), axis=1)].astype(np.float64)
            S[f] = r4.get(f)
            E[f] = hf.get(f)
        return P[f], S[f], E[f]

    def pair(a, b):
        Pa, Sa, Ea = get(a); Pb, Sb, Eb = get(b)
        return dict(frames=[a, b], t=[C.t_of(a), C.t_of(b)], mesh=mesh_dist(Pb, Sa, Pa, Sb, meta), eta_break=eta_stats(Ea, Eb, MB))

    last, first = fr[-1], fr[0]
    nxt = last + man["record_step_frames"]
    jump = pair(last, first)
    natural = pair(last, nxt)
    mismatch = pair(first, nxt)
    steps = [pair(a, b) for a, b in zip(fr[:-1], fr[1:])]
    sm = np.array([[s["mesh"]["median"], s["mesh"]["p95"], s["mesh"]["max"], s["eta_break"]["rms"]] for s in steps])
    res = dict(
        created=time.strftime("%Y-%m-%d %H:%M:%S"), tag="測定", run=C.RUN,
        meaning_ja=("jump：画面で見える継ぎ目の跳び（最後の記録 %.3f s → 最初の記録 %.3f s）。natural_step：計算どおりなら出る 1 歩（%.3f s → %.3f s）。"
                    "mismatch：f3d_loop_ana の「継ぎ目の違い」（%.3f s と %.3f s の面の違い）。steps：窓の中のふつうの 1 歩 %d 個" % (
                        C.t_of(last), C.t_of(first), C.t_of(last), C.t_of(nxt), C.t_of(first), C.t_of(nxt), len(steps))),
        jump=jump, natural_step=natural, mismatch=mismatch,
        steps_summary=dict(n=len(steps), mesh_median_median=float(np.median(sm[:, 0])), mesh_p95_median=float(np.median(sm[:, 1])),
                           mesh_p95_min=float(sm[:, 1].min()), mesh_p95_max=float(sm[:, 1].max()), mesh_max_max=float(sm[:, 2].max()),
                           eta_rms_median=float(np.median(sm[:, 3])), eta_rms_max=float(sm[:, 3].max()),
                           n_steps_p95_ge_jump=int((sm[:, 1] >= jump["mesh"]["p95"]).sum()),
                           n_steps_median_ge_jump=int((sm[:, 0] >= jump["mesh"]["median"]).sum()),
                           n_steps_eta_rms_ge_jump=int((sm[:, 3] >= jump["eta_break"]["rms"]).sum())))
    out = C.OUT + "/loop/seam_jump.json"
    C.write_json(out, res)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("written", out)
    for k in ("jump", "natural_step", "mismatch"):
        m, e = res[k]["mesh"], res[k]["eta_break"]
        print("%-13s mesh median %.3f p95 %.3f max %.3f m | eta RMS %.3f m" % (k, m["median"], m["p95"], m["max"], e["rms"]))
    print("steps", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in res["steps_summary"].items()})


if __name__ == "__main__":
    main()
