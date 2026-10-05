# -*- coding: utf-8 -*-
"""Q20 cand A pipeline: design -> image-space warp (nearest correspondences, 3-D locality) -> smoothing of the warp
displacement along the crest -> sub-px snap -> rows npz (+ warp magnitude).  The generator never reads the model.
usage: py -3.10 candA_pipeline.py params.json out_rows.npz [--loc 6.0] [--smooth_c 0.45]"""
import sys, os, json
import numpy as np
from scipy.ndimage import gaussian_filter1d
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA_design as D
import candA_warp as W


def smooth_rows(F, c, sig_m):
    """Gaussian smoothing of a (nv, nu) field along the rows (c, non-uniform) with sigma in metres."""
    Wm = np.exp(-0.5 * ((c[:, None] - c[None, :]) / sig_m) ** 2)
    Wm /= Wm.sum(1, keepdims=True)
    return Wm @ F


def run(prm_path, out, loc=8.0, sig_c=0.0, nsnap=0, nsurf=6, falloff=2.0, nfine=4, log=print):
    prm = json.load(open(prm_path, encoding="utf-8"))
    c, A0, Y0, P = D.build(prm)
    pt = W.Painting()
    import candA_prefit as PF
    sc = PF.prefit(pt, c, A0, Y0)
    log("prefit scale near rows: min %.3f max %.3f" % (sc.min(), sc.max()))
    Y0 = Y0 * sc[:, None]
    A, Y = A0.copy(), Y0.copy()
    info = []
    rounds = [("nearest", 1000.0, loc), ("nearest", 300.0, loc), ("nearest", 100.0, loc)]
    for k, (mode, lam, lc) in enumerate(rounds):
        A, Y, moved, inf = W.warp_round(pt, c, A, Y, lam, mode, local3d=lc)
        inf.pop("landmarks_cand", None); inf.update(round=k, lam=lam, local3d_m=lc); info.append(inf); log(json.dumps(inf))
    if sig_c > 0:
        # smooth the warp displacement along the crest (rows), then re-lock with two gentle rounds
        dA = smooth_rows(A - A0, c, sig_c); dY = smooth_rows(Y - Y0, c, sig_c)
        dY *= C.smoothstep(Y0 / 2.5) * (Y0 > 0)
        A, Y = A0 + dA, Y0 + dY
        for k, lam in enumerate((30.0, 10.0)):
            A, Y, moved, inf = W.warp_round(pt, c, A, Y, lam, "nearest", local3d=loc)
            inf.pop("landmarks_cand", None); inf.update(round="relock%d" % k); info.append(inf); log(json.dumps(inf))
    # high-frequency remainder: surface-domain rounds (the move of each silhouette vertex is spread over its own
    # surface neighbourhood in (sigma, c), so the painting outline's small wiggles become smooth crest-line wiggles
    # along c instead of kinks inside a section)
    import candA_swarp as SW
    for k in range(nsurf):
        A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=falloff)
        inf.update(round="surf%d" % k); info.append(inf); log(json.dumps(inf))
    for k in range(nfine):
        A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=1.2, maxd=12.0, cell=0.25)
        inf.update(round="fine%d" % k); info.append(inf); log(json.dumps(inf))
    for k in range(nsnap):
        A, Y, inf = W.snap_round(pt, c, A, Y)
        inf.update(round="snap%d" % k); info.append(inf); log(json.dumps(inf))
    mag = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0, warp_mag=mag, prefit_scale=sc)
    json.dump({"rounds": info, "warp_mag_max_m": float(mag.max()), "warp_mag_p95_m": float(np.percentile(mag[Y0 > 0.5], 95)),
               "warp_mag_p50_m": float(np.percentile(mag[Y0 > 0.5], 50)), "smooth_c_sigma_m": sig_c, "local3d_m": loc},
              open(os.path.splitext(out)[0] + "_warp.json", "w"), indent=1, default=float)
    log("warp max %.2f p95 %.2f" % (mag.max(), np.percentile(mag[Y0 > 0.5], 95)))
    return out


if __name__ == "__main__":
    a = sys.argv
    loc = float(a[a.index("--loc") + 1]) if "--loc" in a else 8.0
    sgc = float(a[a.index("--smooth_c") + 1]) if "--smooth_c" in a else 0.0
    run(a[1], a[2], loc, sgc)
