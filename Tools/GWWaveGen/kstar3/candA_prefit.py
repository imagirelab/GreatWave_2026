# -*- coding: utf-8 -*-
"""Q20 cand A: pre-fit of the near-shoulder crest heights to the painting outline (78 / 130 / 131) before the warp.
The painting's shoulder outline is formed by the contour generator on the camera side of each row's round crest,
not by the 3-D crest point, so the heights read off the outline at the design crest position are slightly off.
Here each row c in [-19, -0.3] is scaled vertically (about still water) so that its outermost vertex lands on the
target (sdf = target_s), the per-row scale is smoothed along the crest, and this is repeated a few times.
The scale is returned as a factor per row (recorded)."""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C


def prefit(pt, c, A, Y, c0=-17.5, c1=-0.3, rounds=4, target_s=0.2, sig=0.5):
    tgt, fr = pt.tgt, pt.fr
    nv, nu = A.shape
    scale = np.ones(nv)
    rows = np.nonzero((c >= c0) & (c <= c1))[0]
    for _ in range(rounds):
        X = fr.world(c, A * 1.0, Y * scale[:, None]).reshape(-1, 3)
        P = pt.project(X)
        s = tgt.sample(P[:, :2], comp=True).reshape(nv, nu)
        Pp = P.reshape(nv, nu, 3)
        inframe = (Pp[..., 0] >= tgt.x0) & (Pp[..., 0] <= tgt.x1)
        want = np.zeros(nv)
        ok = np.zeros(nv, bool)
        for r in rows:
            Ys = Y[r] * scale[r]
            m = (Ys > 0.6 * Ys.max()) & inframe[r]
            if m.sum() < 3:
                continue
            j = np.nonzero(m)[0][np.argmax(s[r, m])]
            # vertical derivative of the sdf at that vertex
            eps = 0.02
            X2 = fr.world(c[r:r + 1], A[r:r + 1, j:j + 1], np.array([[Ys[j] + eps]])).reshape(-1, 3)
            g = (tgt.sample(pt.project(X2)[:, :2], comp=True)[0] - s[r, j]) / eps
            if g < 5:
                continue
            dy = (target_s - s[r, j]) / g
            want[r] = (Ys[j] + dy) / Ys[j]
            ok[r] = True
        if not ok.any():
            break
        f = np.where(ok, want, np.nan)
        idx = np.nonzero(ok)[0]
        f = np.interp(np.arange(nv), idx, f[idx])
        Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig) ** 2)
        fs = (Wm @ f) / Wm.sum(1)
        # apply inside [c0, c1] with smooth ramps to 1 outside
        w = C.smoothstep((c - (c0 - 1.5)) / 1.5) * C.smoothstep(((c1 + 1.0) - c) / 1.0)
        scale = scale * (1.0 + (fs - 1.0) * w)
    return scale
