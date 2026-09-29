# -*- coding: utf-8 -*-
"""K*′ 精修 R4：b 区域（左肩の第二の波頭）の母数の試し（py -3.10）。設計の json に鍵の倍率・上書きを掛けて、
b 区域の帯（candA4_checks.band_check：稜の差の中央値・p90・最大・覆う点の数）、肩の唇の上面の膨らみ（R6・R4、c −17〜−4、列 120〜190）、
原画の関門（132・72 の R4 の大きな輪郭、78・130・131）を出す。
usage: py -3.10 kh_R4_bregion.py in.json [out.json] [--width 1.0] [--amp 1.0] [--lobe 1.0] [--lobed 1.0] [--valley 0.5] [--no-gate]
"""
import os
import sys
import json
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = r"G:\Unity\GreatWave_2026_Fresh"
for p in (HERE, os.path.join(REPO, "Tools", "GWWaveGen", "kstar3"), os.path.join(REPO, "Tools", "PaintingTruth"), os.path.join(REPO, "Tools", "GWWaveGen")):
    if p not in sys.path:
        sys.path.insert(0, p)
import numpy as np  # noqa: E402
import kh_designR4 as D  # noqa: E402

E_ = np.array([0.6798348938056157, 0.0, 0.733365200404483]); T_ = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
O_ = np.array([-7.227685896240013, 0.0, -2.7131699203121187])


def bulge_region(c, A, Y, Rm, c0=-17.0, c1=-4.0, j0=120, j1=189):
    X = O_[None, None, :] + A[..., None] * T_ + Y[..., None] * np.array([0, 1.0, 0]) + c[:, None, None] * E_
    nv, nu = A.shape
    s = np.concatenate([np.zeros((nv, 1)), np.cumsum(np.linalg.norm(np.diff(X, axis=1), axis=-1), 1)], 1)
    rows = [r for r in range(nv) if abs(c[r]) <= 16 and c0 <= c[r] <= c1][::2]
    vals = []
    for r0 in rows:
        rs = np.nonzero(np.abs(c - c[r0]) <= Rm)[0][::2]
        for jc in range(j0, j1, 3):
            if Y[r0, jc] < 0.5 or jc > 188:
                continue
            pts = []
            for r in rs:
                jj = np.nonzero((np.abs(s[r] - s[r, jc]) <= Rm) & (np.arange(nu) <= 192))[0][::2]
                pts.append(X[r, jj])
            P = np.concatenate(pts)
            P = P[np.linalg.norm(P - X[r0, jc], axis=1) <= Rm]
            if len(P) < 30:
                continue
            mu = P.mean(0); _, _, Vt = np.linalg.svd(P - mu, full_matrices=False)
            Q = P - X[r0, jc]; u = Q @ Vt[0]; v = Q @ Vt[1]; w = Q @ Vt[2]
            co, *_ = np.linalg.lstsq(np.c_[np.ones_like(u), u, v, u * u, u * v, v * v], w, rcond=None)
            vals.append(abs(co[0]))
    v = np.array(vals)
    return round(float(np.percentile(v, 99)), 3), int((v > (0.6 if Rm > 5 else 0.31)).sum())


def main():
    a = sys.argv[1:]
    din = a[0]
    dout = a[1] if len(a) > 1 and a[1].endswith(".json") else None
    opt = lambda k, d: type(d)(a[a.index(k) + 1]) if k in a else d  # noqa: E731
    d = D.Design.load(din)
    for n, f in (("ledge_width", opt("--width", 1.0)), ("ledge_amp", opt("--amp", 1.0)), ("ledge_lobe", opt("--lobe", 1.0)), ("ledge_lobe_depth", opt("--lobed", 1.0))):
        cs, vs = d.keys[n]
        d.keys[n] = (cs, [v * f for v in vs])
    D.LEDGE_VALLEY = opt("--valley", 0.5)
    for x in a:
        if x.startswith("key:"):
            n, v = x[4:].split("=", 1)
            cs, vs = zip(*[tuple(float(t) for t in kv.split(":")) for kv in v.split(",")])
            d.keys[n] = (list(cs), list(vs))
    c, A, Y, P = D.build(d)
    import candA_common as C
    import candA4_checks as CK
    V1, tgt, fr = C.painting_frame()
    X = fr.world(c, A, Y)
    cov = V1.rasterize(fr.cam, X, V1.triangles(A.shape[1], A.shape[0]))
    b = CK.band_check(c, A, Y, cov)
    t = b["top_vs_top_smooth"]; bb = b["bottom_vs_bottom_smooth"]
    out = {"band_top": [round(t["median_px"], 1), round(t["p90_px"], 1), round(t["max_px"], 1), t["covered_samples"]],
           "band_bot": [round(bb["median_px"], 1), round(bb["p90_px"], 1), round(bb["max_px"], 1), bb["covered_samples"]],
           "R6_shoulder_lip": bulge_region(c, A, Y, 6.0), "R4_shoulder_lip": bulge_region(c, A, Y, 4.0)}
    if "--no-gate" not in a:
        import kh_gate_lfR4 as KG
        import kh_R1_quick as Q1
        r, _ = KG.LFGate().measure_rows(c, A, Y)
        og = Q1.official_gate(c, A, Y)
        out["gate"] = [og[k]["max"] for k in ("78", "130", "131")] + [round(r["132"]["max_px"], 2), round(r["72"]["p95_px"], 2)]
    out["args"] = " ".join(x for x in a[1:] if not x.endswith(".json"))
    print(json.dumps(out), flush=True)
    if dout:
        D.LEDGE_VALLEY = 0.5
        j = d.to_json(); j["bregion_trial"] = out
        json.dump(j, open(dout, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
