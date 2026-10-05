# -*- coding: utf-8 -*-
"""Q20 loop 3 cand A4: 2-D initialisation of the far part (c > 0) against the painting view, one section plane at a time.

In the painting view the sky under the lip (the tube opening, bounded by outline 72) is a tunnel of camera rays that
recedes about 1 m in a per 1 m in c.  In each plane c the section must stay out of that tunnel and out of the sky above
the outline (the 'allowed' region of fin_allowed: the painted wave, below the horizon or outside the scored frame), and
its barrel should hug the tunnel (so that the barrel walls form 72).  Per far site we solve a small least-squares problem
on the row parameters (crest top, barrel centre/radius, lip chain): penetration into the forbidden region (strong),
gap between the barrel wall/roof and the tunnel (touch), and regularisation toward the proportions (shell thickness
0.23-0.31 H, barrel radius 0.3-0.46 H).  No rendering and no reference-model data.
usage: py -3.10 candA4_farinit.py design_in.json design_out.json
"""
import os
for _k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_k, "1")      # one BLAS thread: keeps the commit charge of the parallel workers small
import sys, json, math
import numpy as np
import cv2
from scipy.optimize import least_squares
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA4_model as M
import fin_allowed as FA

RES = 0.05
# designed lip-tip line of the far part (plan): recedes ~1.9 m per m of c until the lip is behind the tube-opening
# tunnel's near edge (~c +10.5), then follows that edge while the curl closes
TIP_C = [0.0, 2.0, 3.5, 5.0, 6.5, 8.0, 9.5, 11.0, 12.5, 13.5]
TIP_A = [8.7, 8.3, 5.3, 2.3, -1.2, -4.5, -9.8, -12.3, -14.0, -15.0]
FREE = ["H", "bx", "by", "rR", "e2c", "e2s", "r1", "t1", "r2", "t2", "t3", "t4", "t5", "phj"]
SC = {"H": 1.0, "aT": 1.0, "bx": 0.03, "by": 0.03, "rR": 0.03, "e2c": 0.04, "e2s": 0.04, "r1": 0.03, "t1": 6, "r2": 0.08,
      "t2": 6, "t3": 8, "t4": 10, "t5": 8, "phj": 8}


class Plane:
    def __init__(self, fr, tgt, c0):
        aa, yy, ok, s = FA.allowed_grid(fr, tgt, c0, a_rng=(-30.0, 25.0), y_rng=(-6.0, 28.0), res=RES)
        self.aa, self.yy, self.ok = aa, yy, ok
        bad = (~ok).astype(np.uint8)
        self.pen = cv2.distanceTransform(bad, cv2.DIST_L2, 5) * RES          # depth inside the forbidden region (m)
        self.gap = cv2.distanceTransform(1 - bad, cv2.DIST_L2, 5) * RES      # distance to the forbidden region (m)

    def sample(self, img, P):
        x = (P[:, 0] - self.aa[0]) / RES; y = (P[:, 1] - self.yy[0]) / RES
        x = np.clip(x, 0, img.shape[1] - 1.001); y = np.clip(y, 0, img.shape[0] - 1.001)
        x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int); fx = x - x0; fy = y - y0
        return (img[y0, x0] * (1 - fx) * (1 - fy) + img[y0, x0 + 1] * fx * (1 - fy) + img[y0 + 1, x0] * (1 - fx) * fy + img[y0 + 1, x0 + 1] * fx * fy)


def fit_site(pl, p0, ref, log=None, c0=0.0, tip_target=None):
    names = FREE
    x0 = np.array([p0[n] for n in names])

    def build(x):
        p = dict(p0); p.update({n: v for n, v in zip(names, x)})
        S, inf = M.section(p)
        return p, S

    def res(x):
        p, S = build(x)
        H = p["H"]
        pen = pl.sample(pl.pen, S[18:394])
        r = [8.0 * pen / 0.1]
        inner = S[214:372]
        m = inner[:, 1] > 3.2
        g = pl.sample(pl.gap, inner)
        wt = float(np.clip((c0 - 2.5) / 2.5, 0.0, 1.0)) * float(c0 < 8.6)   # main rows keep the deep barrel (F07); closing rows need not hug
        r.append(wt * np.where(m, g, 0.0) / 0.25)
        if tip_target is not None:
            r.append(np.array([(S[200, 0] - tip_target) / 0.3]))
        # the tip must stay outside the barrel circle (no loop of the underside)
        cen = np.array([p["aT"] + p["bx"] * max(H, 1.2), p["by"] * max(H, 1.2)])
        dtip = np.linalg.norm(S[200] - cen) - p["rR"] * max(H, 1.2)
        r.append(np.array([max(0.0, 0.6 - dtip) / 0.1]))
        # regularisation toward the proportions / previous design
        r.append(np.array([(x[k] - ref[n]) / SC[n] for k, n in enumerate(names)]) * 0.6)
        # shell: the barrel rearmost point must stay >= 0.22 H in front of the back at that height
        a, y = S[:, 0], S[:, 1]
        yw = y[314]
        back = a[18:91]; yb = y[18:91]
        ab = np.interp(yw, yb, back) if yb.min() <= yw <= yb.max() else back.min()
        r.append(np.array([max(0.0, 0.22 * H - (a[314] - ab)) / 0.1, max(0.0, (a[314] - ab) - 0.34 * H) / 0.3]))
        return np.concatenate(r)
    lo = np.array([{"H": 4, "aT": -20, "bx": -0.2, "by": 0.0, "rR": 0.12, "e2c": -0.15, "e2s": -0.15, "r1": 0.06, "t1": 5, "r2": 0.1,
                    "t2": 0, "t3": 0, "t4": 0, "t5": 0, "phj": 20}[n] for n in names])
    hi = np.array([{"H": 23, "aT": 4, "bx": 0.7, "by": 0.8, "rR": 0.55, "e2c": 0.15, "e2s": 0.15, "r1": 0.5, "t1": 70, "r2": 1.6,
                    "t2": 70, "t3": 90, "t4": 140, "t5": 110, "phj": 110}[n] for n in names])
    x0 = np.clip(x0, lo + 1e-6, hi - 1e-6)
    sol = least_squares(res, x0, bounds=(lo, hi), x_scale=np.array([SC[n] for n in names]), max_nfev=400, diff_step=1e-3)
    p, S = build(sol.x)
    pen = pl.sample(pl.pen, S[18:394])
    return p, S, float(pen.max()), float(sol.cost)


def main(din, dout):
    V1, tgt, fr = C.painting_frame()
    d = M.load_design(din)
    sites = d.sites["H"]
    ref = {n: d.vals[n].copy() for n in M.PARAMS}
    far = [i for i, s in enumerate(sites) if 1.9 <= s <= 12.6]   # the crest line aT(c) is designed, not fitted here
    out = []
    for i in far:
        c0 = sites[i]
        pl = Plane(fr, tgt, c0)
        P = d.eval(np.array([c0]))
        p0 = {n: float(P[n][0]) for n in M.PARAMS}
        refp = dict(p0)
        tip_t = float(np.interp(c0, TIP_C, TIP_A)) if 1.9 <= c0 <= 9.6 else None
        p, S, penmax, cost = fit_site(pl, p0, refp, c0=c0, tip_target=tip_t)
        for n in FREE:
            d.vals[n][i] = p[n]
        out.append((c0, penmax, cost, {n: round(p[n], 3) for n in ("H", "aT", "bx", "by", "rR")}))
        print("site c %+5.1f pen max %.2f m cost %.1f %s" % (c0, penmax, cost, out[-1][3]), flush=True)
    js = d.to_json(); js["farinit_log"] = [list(map(str, o)) for o in out]
    json.dump(js, open(dout, "w", encoding="utf-8"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
