# -*- coding: utf-8 -*-
"""FLIP51 crossing screen, sweep D (2026-10-17, Claude): isolation of ONE peak. For lobes at +-theta0 (uniform half width delta or Gaussian
sigma), linear steepness map k|A| (T 7 s, D19B bed, focus 220.25 m) -> hot-zone length along the axis, highest lattice side spot relative to
the centre, inlet/side band steepness; plus the predicted central metrics (c51_predict rule, f_H 0.86, f_W 1.12)."""
import sys, json, math, time
sys.dont_write_bytecode = True
sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip51/cross")
import numpy as np
import c51_screen as C, c51_predict as P

A_D = 6.331240146143423


def gauss_lobes(th0, sg, n=15, cap=85.0):
    th1 = np.linspace(max(th0 - 2.5 * sg, 2.0), min(th0 + 2.5 * sg, cap), n)
    w1 = np.exp(-0.5 * ((th1 - th0) / sg) ** 2)
    th = np.concatenate([-th1[::-1], th1]); w = np.concatenate([w1[::-1], w1])
    return th, w / w.sum()


def iso(F, s):
    x, y = F.x, F.y
    kA = F.df.k[:, None] * np.abs(s * F.A1)
    X, Y = np.meshgrid(x, y, indexing="ij")
    core = (X >= 150) & (X <= 250)
    ax = kA[:, 0].copy(); ax[(x < 150) | (x > 250)] = 0
    im = int(np.argmax(ax)); kmax = ax[im]
    run = np.where(ax >= 0.8 * kmax)[0]
    # side spots: max kA in the core region at |y| >= 20 m outside the central blob (kA < 0.5 kmax along the connecting row)
    side = core & (Y >= 20) & (Y <= 95)
    j = np.unravel_index(np.argmax(np.where(side, kA, 0)), kA.shape)
    sb = (Y >= 95) & (X <= 180.25); ib = (X >= 20) & (X <= 100) & (Y <= 95)
    return dict(kA_axis_max=float(kmax), x_axis_max=float(x[im]), hot_len80_m=float(x[run.max()] - x[run.min()]) if len(run) else 0.0,
                hot_x80=[float(x[run.min()]), float(x[run.max()])], side_max_rel=float(kA[j] / kmax), side_at=[float(x[j[0]]), float(y[j[1]])],
                kA_side_band=float(kA[sb].max()), kA_inlet_band=float(kA[ib].max()))


def main():
    t0 = time.time()
    rows = []
    cands = [("U80", None)]
    for th0 in (55.0, 60.0, 65.0):
        for dl in (15.0, 25.0):
            cands.append(("L%gd%g" % (th0, dl), ("u", th0, dl)))
        for sg in (8.0, 12.0, 16.0):
            cands.append(("G%gs%g" % (th0, sg), ("g", th0, sg)))
    x = np.arange(0.0, 290.25, 1.0); y = np.arange(0.0, 140.0 + 1e-9, 1.0)
    for nm, spec in cands:
        if spec is None:
            th, w = C.DF.components(80.0, 30, "uniform")
        elif spec[0] == "u":
            th, w = P.lobes(spec[1], spec[2], 11)
        else:
            th, w = gauss_lobes(spec[1], spec[2])
        F = C.Field(7.0, th, w, 220.25, x, y)
        r = dict(name=nm, **iso(F, A_D))
        # central predicted metrics at the hot spot (window around the axis maximum)
        xc = r["x_axis_max"]
        xwin = (xc - 60.0, xc + 35.0); tg = np.linspace(-2.1, 2.1, 43)
        sel = (F.x >= xwin[0]) & (F.x <= xwin[1])
        Hs = max(float(F.eta(A_D, t, 2)[sel].max()) for t in tg)
        s = P.solve_s(F, 0.86 * Hs, xwin, tg, A_D)
        m = P.stretch_metrics(F, s, 1.12, xwin, tg)
        r.update(Hc_2nd=Hs, pred=m)
        rows.append(r)
        print("%-9s axis kA max %.2f at x %.0f, hot80 %3.0f m [%3.0f-%3.0f] side %.2f at (%3.0f,%3.0f) | sideband %.2f inlet %.2f | Hc %.2f W50 %.2f W80 %.2f K %.2f S2 %.2f ring %.2f Lx50 %.2f A50 %.2f miss %.2f"
              % (nm, r["kA_axis_max"], r["x_axis_max"], r["hot_len80_m"], r["hot_x80"][0], r["hot_x80"][1], r["side_max_rel"], r["side_at"][0], r["side_at"][1],
                 r["kA_side_band"], r["kA_inlet_band"], m["Hc"], m["W50"], m["W80"], m["K"], m["S2"], m.get("ring_max", float("nan")), m["Lx50"], m["A50"], m["target_miss"]))
    json.dump(dict(rows=rows, cpu_s=time.time() - t0), open(C.OUT + "/screen_D.json", "w", encoding="utf8"), indent=1, default=float)
    print("cpu %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
