# -*- coding: utf-8 -*-
"""Q20 loop 3, candidate A3: fit to the smoothed reference model (+ secondary design) -> ONLY what the painting
constrains: near-shoulder height pre-fit -> painting-image TPS warp rounds with 3-D locality (only the surface near the
silhouette-forming vertices moves, so the barrel behind the outline survives) -> cross-row relaxation / crest
curvature floor -> gate lock (78/130/131/132 <= K* + 0.5 px, 72 p95 <= 4 px) -> local self-intersection untangle.
The warp stages are those of the loop-2 K*' pipeline (fin2_warp / candA_swarp / fin2_relax / candA_prefit).

The design reads the TEMPORARY smoothed model volume (built outside the repo; see candA3_vol.py).
usage: py -3.10 candA3_pipeline.py vol.npz candA3_params.json out_rows.npz
"""
import sys, os, json
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C
import candA3_vol as CV
import candA3_fit as FT
import fin2_warp as W
import candA_swarp as SW
import candA_prefit as PF
import fin2_relax as RX


def run(vol_path, prm_path, out, log=print, cfg=None, design=None):
    prm = json.load(open(prm_path, encoding="utf-8"))
    cfg = dict(prm.get("pipeline", {}), **(cfg or {}))
    loc = cfg.get("loc", 4.0)
    if design is None:
        vol = CV.Vol(vol_path)
        c, A0, Y0, info = FT.build(vol, prm, log=log)
        if cfg.get("post_design"):
            import candA3_design as DS
            c, A0, Y0 = DS.post(c, A0, Y0, prm, vol, log=log)
    else:
        z = np.load(design); c, A0, Y0 = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    np.savez_compressed(os.path.splitext(out)[0] + "_pre.npz", A=A0, Y=Y0, c=c)
    pt = W.Painting()
    if cfg.get("prefit", True):
        sc = PF.prefit(pt, c, A0, Y0, c0=cfg.get("prefit_c0", -17.5), c1=cfg.get("prefit_c1", -0.3))
    else:
        sc = np.ones(len(c))
    log("prefit scale near rows: min %.3f max %.3f" % (sc.min(), sc.max()))
    Y0 = Y0 * sc[:, None]
    A, Y = A0.copy(), Y0.copy()
    rounds = []
    for k, lam in enumerate(cfg.get("img_rounds", [1000.0, 300.0, 100.0, 50.0, 30.0])):
        A, Y, moved, inf = W.warp_round(pt, c, A, Y, lam, "nearest", local3d=loc, far_att=cfg.get("far_att"))
        inf.pop("landmarks_cand", None); inf.update(round=k, lam=lam, local3d_m=loc); rounds.append(inf); log(json.dumps(inf))
    for k in range(cfg.get("pre_snap", 0)):
        A, Y, inf = W.snap_round(pt, c, A, Y, band=cfg.get("snap_band", 1.0), target_s=cfg.get("snap_target", -0.5),
                                 cap=cfg.get("snap_cap", 0.5), sig=cfg.get("snap_sig", 2.5), comp=False)
        inf.update(round="presnap%d" % k); rounds.append(inf); log(json.dumps(inf))
    for k in range(cfg.get("nsurf", 0)):
        A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=cfg.get("falloff", 2.0))
        inf.update(round="surf%d" % k); rounds.append(inf); log(json.dumps(inf))
    H = Y.max(1); H0 = H[int(np.argmin(np.abs(c)))]
    big_near = [r for r in range(len(c)) if H[r] >= 0.45 * H0 and -6.5 <= c[r] <= 7.5]
    big_sh = [r for r in range(len(c)) if H[r] >= 0.45 * H0 and c[r] < -6.5]
    for it in range(cfg.get("relax_loops", 2)):
        A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75))
        A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15))
        tab = cfg.get("relax_sigma_c")
        sg = np.interp(c, [t[0] for t in tab], [t[1] for t in tab]) if tab else cfg.get("relax_sigma", 0.4)
        w = np.clip((np.abs(Y) - 0.02) / 0.3, 0.0, 1.0) * np.clip(Y.max(1) / 1.5, 0.0, 1.0)[:, None]
        A, Y = RX.cross_rows(A, Y, c, sg, weight=w)
        for k in range(cfg.get("relock", 2)):
            A, Y, inf = SW.surface_round(pt, c, A, Y, falloff=cfg.get("relock_falloff", 1.6), maxd=12.0, cell=0.3)
            inf.update(round="relax%d_%d" % (it, k)); rounds.append(inf); log(json.dumps(inf))
    A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75))
    A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15))
    lim = {"78": 1.87, "130": 2.30, "131": 1.97, "132": 1.90}
    V1 = pt.V1

    def gate(A_, Y_):
        g = V1.preview_metrics(pt.fr, pt.tgt, pt.fr.world(c, A_, Y_), V1.triangles(A_.shape[1], A_.shape[0]),
                               os.path.splitext(out)[0] + "_lockgate.png", "lock")
        return g, all(g[k]["max_px"] <= lim[k] - cfg.get("lock_margin", 0.08) for k in lim) and g["72"]["p95_px"] <= 3.5
    for it in range(cfg.get("max_lock", 8)):
        g, ok = gate(A, Y)
        rounds.append({"round": "lockcheck%d" % it, "gate": {k: g[k]["max_px"] for k in g}, "p95_72": g["72"]["p95_px"], "ok": bool(ok)}); log(json.dumps(rounds[-1]))
        if ok:
            A2, Y2, hist, mv = V1.fix_self_intersections(pt.fr, c, A, Y, max_iter=40, win=cfg.get("untangle_win", 12))
            rounds.append({"round": "untangle%d" % it, "history": hist, "move_max_m": mv}); log(json.dumps(rounds[-1]))
            if mv < 1e-9:
                break
            A, Y = A2, Y2
            g, ok = gate(A, Y)
            rounds.append({"round": "lockcheck%d_post" % it, "gate": {k: g[k]["max_px"] for k in g}, "ok": bool(ok)}); log(json.dumps(rounds[-1]))
            if ok:
                break
        A, Y, moved, inf = W.warp_round(pt, c, A, Y, cfg.get("lock_lam", 30.0), "nearest", local3d=cfg.get("lock_loc", 3.0), far_att=cfg.get("far_att"))
        inf.pop("landmarks_cand", None); inf.update(round="lock%d" % it); rounds.append(inf); log(json.dumps(inf))
        for k in range(cfg.get("lock_snap", 0)):
            # spill removal (painting sky inside the silhouette, e.g. the window under the lip): the vertices seen in the
            # sky move along their row's in-plane normal onto the painted region, spread smoothly over the surface
            A, Y, inf = W.snap_round(pt, c, A, Y, band=cfg.get("snap_band", 1.0), target_s=cfg.get("snap_target", -0.5),
                                     cap=cfg.get("snap_cap", 0.5), sig=cfg.get("snap_sig", 2.5), comp=False)
            inf.update(round="snap%d_%d" % (it, k)); rounds.append(inf); log(json.dumps(inf))
        A, Y = RX.crest_floor(A, Y, c, big_near, cfg.get("rmin_near", 1.75) - 0.1)
        A, Y = RX.crest_floor(A, Y, c, big_sh, cfg.get("rmin_sh", 1.15) - 0.05)
    if cfg.get("tail_taper"):
        t0, t1 = cfg["tail_taper"]
        f = np.where(c > t0, C.smoothstep((t1 - c) / (t1 - t0)), 1.0)
        if cfg.get("tail_unfold", "none") == "mono":
            jj = np.arange(A.shape[1]) * 1e-4
            Am = np.maximum.accumulate(A, axis=1) + jj[None, :]
            A = f[:, None] * A + (1 - f[:, None]) * Am
        Y = Y * f[:, None]
    mag = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0 / sc[:, None]), axis=-1)
    mag_after_prefit = np.linalg.norm(C.world(c, A, Y) - C.world(c, A0, Y0), axis=-1)
    np.savez_compressed(out, A=A, Y=Y, c=c, A_pre=A0, Y_pre=Y0 / sc[:, None], warp_mag=mag, warp_mag_after_prefit=mag_after_prefit, prefit_scale=sc)
    m = (Y0 > 0.5)
    json.dump({"rounds": rounds, "warp_mag_max_m": float(mag.max()), "warp_mag_p95_m": float(np.percentile(mag[m], 95)),
               "warp_mag_p50_m": float(np.percentile(mag[m], 50)),
               "warp_mag_after_prefit_p95_m": float(np.percentile(mag_after_prefit[m], 95)), "local3d_m": loc, "cfg": cfg,
               "prefit_scale_min_max": [float(sc.min()), float(sc.max())]},
              open(os.path.splitext(out)[0] + "_warp.json", "w"), indent=1, default=float)
    log("warp max %.2f p95 %.2f p50 %.2f" % (mag.max(), np.percentile(mag[m], 95), np.percentile(mag[m], 50)))
    return out


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2], sys.argv[3])
