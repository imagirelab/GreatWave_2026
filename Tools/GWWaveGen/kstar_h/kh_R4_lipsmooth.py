# -*- coding: utf-8 -*-
"""K*′ 精修 R4：唇の頭の移動（lip_shift / lip_drop）を c の方向にガウスでならし、鍵へ戻す（py -3.10）。唇の縁の波打ち（評審の must-fix）を
なくすための段。ならした曲線を 1 m おきの鍵の B-spline へ最小二乗で当て直す（曲線がなめらかなので鍵の間隔は波打ちを作らない）。
関門（kh_gate_lfR4：132 は σ 12 px、72 は σ 24 px の大きな輪郭）と、唇の縁のなめらかさ（先の線の ±2 m の 2 次式からの残差、bump4）を出す。
usage: py -3.10 kh_R4_lipsmooth.py in.json out.json --sig 1.0 [--c0 -12] [--c1 15] [--keep-far 9.5]
  --keep-far c：c より奥（管の口の輪郭 72 の下の部分を描く奥の行）はならさない（なめらかに移す）。--keep-near c：c より手前（132 の唇の頭を描く行）もならさない。
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import kh_designR4 as D  # noqa: E402


def smooth_c(c, v, sig):
    """Gaussian smoothing along c by distance (non-uniform rows), ends held."""
    W = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig) ** 2) * np.gradient(c)[None, :]
    return (W @ v) / W.sum(1)


def tipline_residual(c, A, Y, c0=-9.0, c1=12.0, j=200, half=2.0):
    """the judges' measure: residual of the tip line (col j, world) from a local quadratic over +-half m (p99, max, m)."""
    X = D.world_u(c, A, Y)[:, j, :]
    res = []
    for cc in np.arange(c0, c1 + 1e-9, 0.2):
        m = np.abs(c - cc) <= half
        if m.sum() < 7:
            continue
        t = c[m] - cc
        M = np.c_[np.ones_like(t), t, t * t]
        for q in range(3):
            co, *_ = np.linalg.lstsq(M, X[m, q], rcond=None)
        P = X[m]
        co_all = np.linalg.lstsq(M, P, rcond=None)[0]
        r = np.linalg.norm(P - M @ co_all, axis=1)
        k = int(np.argmin(np.abs(t)))
        res.append(r[k])
    res = np.array(res)
    return {"p99": round(float(np.percentile(res, 99)), 3), "max": round(float(res.max()), 3)}


def main():
    a = sys.argv[1:]
    din, dout = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    sig, c0, c1, keep_far = opt("--sig", 1.0), opt("--c0", -12.0), opt("--c1", 15.0), opt("--keep-far", 99.0)
    keep_near = opt("--keep-near", -99.0)
    kw = [float(x) for x in opt("--keep-win", "99,99").split(",")]
    d = D.Design.load(din)
    c = D.c_rows()
    kc = [-12.0] + [float(x) for x in np.arange(-11.0, 14.01, 1.0)] + [15.5]
    B = np.stack([D.bspline_ramp(kc, np.eye(len(kc))[i], c) for i in range(len(kc))], 1)
    m = (c >= c0 - 3) & (c <= c1 + 1)
    for n in ("lip_shift", "lip_drop"):
        v = D.bspline_ramp(d.keys[n][0], d.keys[n][1], c) if len(d.keys[n][0]) > 1 else np.full(len(c), d.keys[n][1][0])
        vs = smooth_c(c, v, sig)
        wf = D.smoothstep((keep_far - c) / 1.5) * D.smoothstep((c - keep_near) / 1.5)   # 1 between keep_near and keep_far
        wf = wf * (1.0 - D.smoothstep((c - kw[0] + 0.75) / 0.75) * D.smoothstep((kw[1] + 0.75 - c) / 0.75))   # R4: keep a window
        vs = wf * vs + (1 - wf) * v
        th, *_ = np.linalg.lstsq(B[m], vs[m], rcond=None)
        th[0] = 0.0; th[-1] = 0.0
        d.keys[n] = (list(kc), [round(float(x), 5) for x in th])
    j = d.to_json()
    j["lipsmooth"] = {"sigma_m": sig, "keep_far_c": keep_far, "keep_near_c": keep_near, "keys": kc}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    if "--measure" in a:
        import kh_gate_lfR4 as KG
        import kh_R1_quick as Q1
        cc, A, Y, P = D.build_pre_sculpt(d)
        g = KG.LFGate()
        r, _ = g.measure_rows(cc, A, Y)
        og = Q1.official_gate(cc, A, Y)
        import kh_fitA as KF
        b = KF.bump4(cc, A, Y)
        print(json.dumps({"sig": sig, "keep_far": keep_far, "keep_near": keep_near, "78/130/131": [og[k]["max"] for k in ("78", "130", "131")],
                          "132lf_max": round(r["132"]["max_px"], 2), "72lf24_p95": round(r["72"]["p95_px"], 2), "72lf24_max": round(r["72"]["max_px"], 2),
                          "tipline": tipline_residual(cc, A, Y), "bump4_d1_p99": round(float(np.percentile(b["d1"], 99)), 3)}), flush=True)


if __name__ == "__main__":
    main()
