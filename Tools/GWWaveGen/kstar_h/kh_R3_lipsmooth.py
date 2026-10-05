# -*- coding: utf-8 -*-
"""K*′ 精修 R3：唇の頭の移動（lip_shift / lip_drop）の正則化（py -3.10）。唇の縁の波打ち（評審 R2 の must-fix 3）を、原画の関門を守る範囲で
いちばん強くならす。
方法：lip_shift・lip_drop の ramp（R2 の 1 m おきの鍵）を c の方向にガウス（σ SIG m）でならした曲線を、鍵の間隔 STEP m の新しい鍵へ
最小二乗で置き直し（ならした版）、区間ごと（REGIONS）に「元 → ならした版」の混ぜ率 t を、関門（78/130/131 最大 ≤ 4、132 大きな輪郭の最大
≤ LIM、72 大きな輪郭の p95 ≤ LIM）を満たす最大の値へ二分法で決める。関門の測り方は評価器と同じ（kh_R1_snap.Snap = 公式の包絡版と
大きな輪郭の線）。ほかの鍵は動かさない。
usage: py -3.10 kh_R3_lipsmooth.py in.json out.json [--sig 1.5] [--step 1.5] [--lim 3.95] [--lim132 3.95]
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")
import sys
import json
import time
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"),
          os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import kh_designR3 as D  # noqa: E402
import kh_R1_snap as SN  # noqa: E402

NAMES = ("lip_shift", "lip_drop")
REGIONS = ((-12.0, -4.0), (-4.0, 1.0), (1.0, 6.0), (6.0, 10.0), (10.0, 15.5))


def main():
    a = sys.argv[1:]
    din, dout = a[0], a[1]
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    sig, step, lim = opt("--sig", 1.5), opt("--step", 1.5), opt("--lim", 3.95)
    lim132 = opt("--lim132", lim)                   # R3: separate limits (the lip smoothing must leave a margin on 72 for the Houdini float32 bridge)
    d0 = D.Design.load(din)
    c = D.c_rows()
    S = SN.Snap()
    if step > 0:
        kc = [-12.0] + [float(x) for x in np.arange(-12.0 + step, 15.0 - 0.5 * step, step)] + [15.0]
    else:                                   # --step 0: keep the input keys (t = 0 reproduces the input exactly)
        kc = list(d0.keys["lip_shift"][0])
        assert list(d0.keys["lip_drop"][0]) == kc
    n = len(kc)
    B = np.stack([D.bspline_ramp(kc, np.eye(n)[i], c) for i in range(n)], 1)
    dense = (c >= -19.0)
    dc = 0.2
    k = np.exp(-0.5 * (np.arange(-int(4 * sig / dc), int(4 * sig / dc) + 1) * dc / sig) ** 2); k /= k.sum()
    cur, smo = {}, {}
    for nm in NAMES:
        v = D.bspline_ramp(d0.keys[nm][0], d0.keys[nm][1], c)
        cur[nm] = v
        vs = v.copy()
        r = len(k) // 2
        vs[dense] = np.convolve(np.pad(v[dense], (r, r), mode="edge"), k, "valid")
        smo[nm] = vs
    # region weights along c (smooth partition of unity)
    cc = np.asarray(c)
    W = []
    for lo, hi in REGIONS:
        W.append(np.clip((cc - lo + 0.75) / 1.5, 0, 1) * np.clip((hi - cc + 0.75) / 1.5, 0, 1))
    W = np.array(W); W /= np.maximum(W.sum(0, keepdims=True), 1e-9)
    t = np.zeros(len(REGIONS))
    log = []

    def design_for(tv):
        d = D.Design.from_json(d0.to_json())
        wt = (tv[:, None] * W).sum(0)
        for nm in NAMES:
            target = (1 - wt) * cur[nm] + wt * smo[nm]
            v, *_ = np.linalg.lstsq(B, target, rcond=None)
            v[0] = v[-1] = 0.0
            d.keys[nm] = (list(kc), [float(x) for x in v])
        return d

    def gate(tv):
        d = design_for(tv)
        c_, A, Y, P = D.build(d, c)
        out, met = S.fixed(c_, A, Y)
        ok = all(met[i]["max"] <= 4.0 for i in ("78", "130", "131")) and met["132"]["max"] <= lim132 and met["72"]["p95"] <= lim
        rec = {"t": [round(x, 3) for x in tv], "132": round(met["132"]["max"], 3), "72p95": round(met["72"]["p95"], 3),
               "130": round(met["130"]["max"], 3), "ok": bool(ok)}
        log.append(rec); print(json.dumps(rec), flush=True)
        return ok, d
    t0 = time.time()
    ok0, dbest = gate(t)
    if not ok0:
        print("the start does not pass the gate at lim %.2f" % lim, flush=True)
    for it in range(2):                      # two sweeps over the regions
        for i in range(len(REGIONS)):
            lo, hi = t[i], 1.0
            tt = t.copy(); tt[i] = hi
            ok, dd = gate(tt)
            if ok:
                t = tt; dbest = dd; continue
            for _ in range(4):
                mid = 0.5 * (lo + hi)
                tt = t.copy(); tt[i] = mid
                ok, dd = gate(tt)
                if ok:
                    lo = mid; dbest = dd
                else:
                    hi = mid
            t[i] = lo
    dbest = design_for(t)
    j = dbest.to_json()
    j["lipsmooth_log"] = {"sigma_m": sig, "key_step_m": step, "limit_px": lim, "limit_132_px": lim132, "regions": REGIONS, "t": t.tolist(), "evals": log,
                          "seconds": round(time.time() - t0)}
    json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("FINAL t", t.tolist(), round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
