# -*- coding: utf-8 -*-
"""Q20 final K*': design -> near-shoulder height prefit -> image-space warp rounds (nearest correspondences, 3-D
locality) -> surface-domain (sigma, c) rounds -> cross-row relaxation of the hidden surface -> surface re-lock.
The generator never reads the reference model.
usage: py -3.10 fin_pipeline.py fin_params.json out_rows.npz"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import fin2_design as D
import fin2_warp as W
import candA_swarp as SW
import candA_prefit as PF


def run(prm_path, out, log=print, cfg=None):
    prm = json.load(open(prm_path, encoding="utf-8"))
    cfg = dict(prm.get("pipeline", {}), **(cfg or {}))
    loc = cfg.get("loc", 8.0)
    c, A0, Y0, P = D.build(prm)
    pt = W.Painting()
    sc = PF.prefit(pt, c, A0, Y0)
    log("prefit scale near rows: min %.3f max %.3f" % (sc.min(), sc.max()))
    Y0 = Y0 * sc[:, None]
    A, Y = A0.copy(), Y0.copy()
    info = []
    for k, lam in enumerate(cfg.get("img_rounds", [1000.0, 300.0, 100.0])):
        A, Y, moved, inf = W.warp_round(pt, c, A, Y, lam, "nearest", local3d=loc, far_att=cfg.get("far_att"))
        inf.pop("landmarks_cand", None); inf.update(round=k, lam=lam, local3d_m=loc); info.append(inf); log(json.dumps(inf))
    for k in range(cfg.get("nsurf", 6)):
        A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=cfg.get("falloff", 2.0))
        inf.update(round="surf%d" % k); info.append(inf); log(json.dumps(inf))
    for k in range(cfg.get("nfine", 4)):
        A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=1.2, maxd=12.0, cell=0.25)
        inf.update(round="fine%d" % k); info.append(inf); log(json.dumps(inf))
    # relaxation loops: round crests (F02 curvature floor), smooth across rows (F11), light silhouette re-lock
    import fin2_relax as RX
    H = Y.max(1); H0 = H[int(np.argmin(np.abs(c)))]
    big_near = [r for r in range(len(c)) if H[r] >= 0.45 * H0 and -6.5 <= c[r] <= 7.5]
    big_sh = [r for r in range(len(c)) if H[r] >= 0.45 * H0 and c[r] < -6.5]
    for it in range(cfg.get("relax_loops", 2)):
        A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75))
        A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15))
        sg = cfg.get("relax_sigma", 0.0)
        if cfg.get("relax_sigma_c"):
            tab = cfg["relax_sigma_c"]; sg = np.interp(c, [t[0] for t in tab], [t[1] for t in tab])
        if np.any(np.asarray(sg) > 0):
            w = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0) * np.clip(Y.max(1) / 1.5, 0.0, 1.0)[:, None]
            A, Y = RX.cross_rows(A, Y, c, sg, weight=w)
        for k in range(cfg.get("relock", 2)):
            A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=cfg.get("relock_falloff", 1.6), maxd=12.0, cell=0.3)
            inf.update(round="relax%d_%d" % (it, k)); info.append(inf); log(json.dumps(inf))
    if cfg.get("final_floor", True):
        A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75))
        A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15))
    # final gate-driven lock: a local image round (3-D locality 3 m) + curvature floor, until the painting gate
    # (78/130/131/132 max <= K* + 0.5 px, 72 p95 <= 4 px) holds with a small margin
    lim = {"78": 1.87, "130": 2.30, "131": 1.97, "132": 1.90}
    V1 = pt.V1
    def gate(A_, Y_):
        g = V1.preview_metrics(pt.fr, pt.tgt, pt.fr.world(c, A_, Y_), V1.triangles(A_.shape[1], A_.shape[0]),
                               os.path.splitext(out)[0] + "_lockgate.png", "lock")
        return g, all(g[k]["max_px"] <= lim[k] - cfg.get("lock_margin", 0.08) for k in lim) and g["72"]["p95_px"] <= 3.5
    for it in range(cfg.get("max_lock", 6)):
        g, ok = gate(A, Y)
        info.append({"round": "lockcheck%d" % it, "gate": {k: g[k]["max_px"] for k in g}, "ok": bool(ok)}); log(json.dumps(info[-1]))
        if ok:
            # mesh hygiene: untangle local 3-D self-intersections (in-plane smoothing of the touching vertices only)
            A2, Y2, hist, mv = V1.fix_self_intersections(pt.fr, c, A, Y, max_iter=40, win=cfg.get("untangle_win", 12))
            info.append({"round": "untangle%d" % it, "history": hist, "move_max_m": mv}); log(json.dumps(info[-1]))
            if mv < 1e-9:
                break
            A, Y = A2, Y2
            g, ok = gate(A, Y)
            info.append({"round": "lockcheck%d_post" % it, "gate": {k: g[k]["max_px"] for k in g}, "ok": bool(ok)}); log(json.dumps(info[-1]))
            if ok:
                break
        A, Y, moved, inf = W.warp_round(pt, c, A, Y, cfg.get("lock_lam", 30.0), "nearest", local3d=cfg.get("lock_loc", 3.0), far_att=cfg.get("far_att"))
        inf.pop("landmarks_cand", None); inf.update(round="lock%d" % it); info.append(inf); log(json.dumps(inf))
        A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75) - 0.1)
        A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15) - 0.05)
    if cfg.get("tail_taper"):
        # loop 2: the hidden far tail runs into the sea by the last row (the cross-row averages lift the last rows;
        # an affine y-scale per row keeps each row free of self-crossings and varies smoothly along the crest)
        t0, t1 = cfg["tail_taper"]
        f = np.where(c > t0, C.smoothstep((t1 - c) / (t1 - t0)), 1.0)
        if cfg.get("tail_unfold", "none") == "mono":
            # blend a toward the row's monotone version (a flattened curl would lie on itself)
            jj = np.arange(A.shape[1]) * 1e-4
            Am = np.maximum.accumulate(A, axis=1) + jj[None, :]
            A = f[:, None] * A + (1 - f[:, None]) * Am
        Y = Y * f[:, None]
    mag = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0, warp_mag=mag, prefit_scale=sc,
                        **{"p_" + k: v for k, v in P.items()})
    json.dump({"rounds": info, "warp_mag_max_m": float(mag.max()), "warp_mag_p95_m": float(np.percentile(mag[Y0 > 0.5], 95)),
               "warp_mag_p50_m": float(np.percentile(mag[Y0 > 0.5], 50)), "local3d_m": loc, "cfg": cfg},
              open(os.path.splitext(out)[0] + "_warp.json", "w"), indent=1, default=float)
    log("warp max %.2f p95 %.2f" % (mag.max(), np.percentile(mag[Y0 > 0.5], 95)))
    return out


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
