# -*- coding: utf-8 -*-
"""Q20 candidate B: K*' by incremental fixes of K* 26修正01 (Q16/Q17 plans), in order of rising painting risk.

  py -3.10 candB_build.py [--steps 1,2,3,4,5,6] [--tag NAME]

Steps (each followed by a painting check: coverage diff vs K* and the envelope gate 78/130/131/132/72):
  1 far re-close  (rows c > 0 -> thin nested curls hidden behind the main section; peak at c ~ 0; open tube mouth)
  2 rounded back + blended top  (every row with a crest: back rebuilt from the painting-locked junction, G1 at the crest)
  3 foot / plinth -> front trough  (below the horizon only)
  4 second crest ledge (3 lobes A/B/C on the near shoulder, heights from the painting band)
  5 near-row lips thinned, tubes rounded (hidden parts only)
  6 row cleanup (cross-row smoothing of free vertices, fractional landmark columns, row spacing)
Outputs go to Unity/Build/Q20/candB (git-ignored).
"""
import sys, os, json, time, argparse
import numpy as np
from candB_common import *
from candB_geom import *
from candB_back import rebuild_back2, junction_heading
import candB_far as FAR
import candB_foot as FOOT
import candB_tube as TUBE
from candB_crestarc import crest_best
import candB_crest2 as CR2

LOG = []


def log(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.append(s)


# ------------------------------------------------------------------ parameters (named art directions / numeric conditions)
P = {
    # step 2 ds_kstar_back_round (art direction): heading program of the back (arc length in H/20.75 m, deg)
    "back_s": [0.0, 3.4, 5.0, 8.0, 14.0], "back_phi": [None, 38.0, 48.0, 66.0, 84.0], "back_conc": 1.0,
    "back_c_from": -60.0,            # rows with a crest (H > 2 m) and c >= this get the new back
    # step 1 ds_kstar_far_close (art direction)
    "far_c_end": 4.45, "far_shear": 1.0, "far_H_end_rel": None, "far_drop_c": 2.45,
    "smin_delta": 0.30, "smin_t_top": 0.5, "smin_t_bot": 1.3, "smin_tip_a": 9.0, "smin_shift_a": -0.2,
    # clamps
    "margin_px": 1.0, "lock_cap_m": 0.015,
    # step 3 ds_kstar_foot_trough (art direction)
    "foot_jf": 379, "trough_rel": 0.22,
    # step 5 ds_kstar_near_tube (art direction): round tube + hooked thin lip on the near rows
    "tube_c0": -2.2, "tube_c1": -0.3, "tube_r_rel": 0.46, "tube_th_tip": 48.0, "tube_Hmin": 4.0,
    "tube_r_rel_shoulder": 0.36, "tube_shoulder_c": (-12.0, -5.0),
    # step 4 ds_second_crest (art direction, deliberately against physics: Q16 point 5)
    "tier_c0": -17.5, "tier_c1": -8.0, "tier_prot0": 1.2, "tier_prot1": 1.1, "tier_tip_back": 1.2,
    "tier_step_min": 1.2, "tier_dip": 0.7,
    # step 6 kstar_row_clean (numeric condition)
    "clean_iters": 3, "clean_sigma_m": 0.35, "clean_sigma_cols": (0.6, 0.45, 1.1), "clean_reparam": False, "liptop_fair_c": (-8.0, 2.5), "liptop_fair_cap": 0.35, "min_row_gap": 0.03, "near_main_blend_c": -1.2, "clean_crest_win": (14, 30),
}


def gate_step(name, A, Y, c, cov0):
    cov = coverage(A, Y, c)
    md = mask_diff(cov0, cov)
    g = gate(A, Y, c, png=os.path.join(WORK, "gate_%s.png" % name), title="candB " + name)
    ok = gate_ok(g)
    log("[gate %s] 78 %.2f 130 %.2f 131 %.2f 132 %.2f 72 p95 %.2f (max %.2f) | sky diff: added %d removed %d px | %s" % (
        name, g["78"]["max_px"], g["130"]["max_px"], g["131"]["max_px"], g["132"]["max_px"], g["72"]["p95_px"], g["72"]["max_px"],
        md["added_px"], md["removed_px"], "PASS" if ok else "FAIL"))
    import cv2
    vis = np.dstack([md["rem"] * 255, (cov0 > 0.5) * 90, md["add"] * 255]).astype(np.uint8)
    cv2.imwrite(os.path.join(WORK, "diff_%s.png" % name), vis)
    return g, md, ok


# ------------------------------------------------------------------ step 2 helper: the back of one row
def row_back(a, y, cc, lock_r, prm):
    top = int(np.argmax(y[:200]))
    if y[top] < 2.0:
        return a, y, None
    # junction = first locked column (from the back side) within 14 columns of the top, else the top itself
    cand = [j for j in range(max(top - 14, 20), top + 1) if lock_r[j]]
    jL = cand[0] if cand else top
    try:
        a2, y2 = rebuild_back2(a, y, jL, prm["back_s"], prm["back_phi"], conc_shape=prm["back_conc"])
    except Exception as ex:
        return a, y, None
    free = ~lock_r.copy(); free[jL:] = False
    a3, y3, nb = clamp_row_dir(a2, y2, cc, free, margin=prm["margin_px"])
    return a3, y3, jL


def step2_back(A, Y, c, lock, prm, rows=None):
    A = A.copy(); Y = Y.copy(); info = {}
    rows = rows if rows is not None else [r for r in range(NV) if c[r] >= prm["back_c_from"] and c[r] <= 0.0]
    for r in rows:
        a3, y3, jL = row_back(A[r], Y[r], c[r], lock[r], prm)
        if jL is None:
            continue
        cap = np.where(lock[r], prm["lock_cap_m"], 0.6)
        cap[jL + 6:] = 0.0                       # only the back and the junction are faired; the lip keeps K*
        keep = np.zeros(NU, bool); keep[jL + 6:] = True
        a4, y4 = capped_fair(a3, y3, a3, y3, cap, iters=250, keep=keep)
        free = ~lock[r]; free[jL + 6:] = False
        a4, y4, nb = clamp_row_dir(a4, y4, c[r], free, margin=prm["margin_px"])
        # crest rounding from whichever side is free (G1 across the crest, under the painting silhouette)
        a4, y4 = round_crest(a4, y4, c[r], lock[r])
        A[r], Y[r] = a4, y4; info[r] = jL
    return A, Y, info


def round_crest(a, y, cc, lk, it=6):
    a = a.copy(); y = y.copy(); jt = int(np.argmax(y[:200]))
    win = np.zeros(NU, bool); win[max(jt - 10, 0):jt + 45] = True
    free = win & ~lk
    cap = np.where(free, 1.5, 0.0)
    for k in range(it):
        a, y = capped_fair(a, y, a, y, cap, iters=150, lam_=0.25, keep=~free)
        a, y, _ = clamp_row_dir(a, y, cc, free, margin=1.0)
        a, y = sanitize(a, y, keep=~free)
    return a, y


# ------------------------------------------------------------------ step 1: far rows
def step1_far(A, Y, c, prm):
    A = A.copy(); Y = Y.copy(); c = c.copy()
    main = int(np.argmin(np.abs(c)))
    aM, yM = A[main].copy(), Y[main].copy()
    S, info = FAR.build_smin5(aM, yM, prm["smin_delta"], prm["smin_t_top"], prm["smin_t_bot"])
    # move the thin shell back (straighter crest line in plan); the shift fades out toward the lip tip (a_eq 5 -> 8)
    S[:, 0] += prm["smin_shift_a"] * (1 - smoothstep((S[:, 0] - 5.0) / 3.0))
    # the lowest tube columns (painted inner wall bottom, above the horizon) must stay hidden: fall back toward the
    # main section (moved 0.3 m back into its body) where the round tube would show
    ref_a = aM - 0.3; ref_y = yM
    bad = ~row_inside(S[:, 0], S[:, 1], 0.0, prm["margin_px"]) & (S[:, 1] > 2.5)
    for t in np.linspace(0.9, 0.0, 10):
        if not bad.any():
            break
        S[bad, 0] = ref_a[bad] + t * (S[bad, 0] - ref_a[bad]); S[bad, 1] = ref_y[bad] + t * (S[bad, 1] - ref_y[bad])
        bad = ~row_inside(S[:, 0], S[:, 1], 0.0, prm["margin_px"]) & (S[:, 1] > 2.5)
    log("[far] S_min round tube: centre %s Ra %.2f Ry %.2f tip %.1f deg, crest(eq) %s, still-outside %d" % (
        info["C"], info["Ra"], info["Ry"], info["th_tip"], info["crest_eq"], int(bad.sum())))
    far = np.arange(main + 1, NV)
    c_end = prm["far_c_end"]
    cn = np.linspace(0, c_end, len(far) + 1)[1:]
    qs = np.linspace(0, 1, 201)
    secs = [((1 - q) * aM + q * S[:, 0], (1 - q) * yM + q * S[:, 1]) for q in qs]
    ytop = np.array([s[1][:200].max() for s in secs])
    Hend = 3 + lam(c_end, 0) * (ytop[-1] - 3)
    Ht = Hend + (yM.max() - Hend) * (1 - smoothstep(cn / prm["far_drop_c"]))
    a_main_top = aM[int(np.argmax(yM[:200]))]
    for i, (r, cc, h) in enumerate(zip(far, cn, Ht)):
        ye = 3 + (h - 3) / lam(cc, 0)
        q = float(np.interp(-ye, -ytop, qs))
        ae = (1 - q) * aM + q * S[:, 0]; yv = (1 - q) * yM + q * S[:, 1]
        # crest shear: bring the crest toward the straight crest line a = a_main_top (in 3D)
        jt = int(np.argmax(yv[:200]))
        a_eq_target = CAM_S[0] + (a_main_top - CAM_S[0]) / lam(cc, 0)
        d = (a_eq_target - ae[jt]) * prm["far_shear"]
        j = np.arange(NU)
        w = np.clip(np.minimum((j - 20) / max(jt - 20, 1), (185 - j) / max(185 - jt, 1)), 0, 1)
        w = w * w * (3 - 2 * w)
        ae2 = ae + d * w
        a3, y3 = FAR.to_plane(ae2, yv, cc)
        ok = row_inside(a3, y3, cc, prm["margin_px"]) | (y3 < 2.5)
        if not ok.all():
            # fall back toward the un-sheared section for the offending vertices
            a0_, y0_ = FAR.to_plane(ae, yv, cc)
            for t in np.linspace(0.9, 0.0, 10):
                bad = ~(row_inside(a3, y3, cc, prm["margin_px"]) | (y3 < 2.5))
                if not bad.any():
                    break
                a3[bad] = a0_[bad] + t * (a3[bad] - a0_[bad]); y3[bad] = y0_[bad] + t * (y3[bad] - y0_[bad])
        A[r], Y[r] = a3, y3; c[r] = cc
    log("[far] rows %d..%d -> c %.2f..%.2f; H %.2f -> %.2f; S_min crest (eq) %s" % (far[0], far[-1], cn[0], cn[-1], Ht[0], Ht[-1], info["crest_eq"]))
    return A, Y, c, S


def step3_foot(A, Y, c, prm):
    A = A.copy(); Y = Y.copy(); info = {}
    for r in range(NV):
        Hr = Y[r, :200].max()
        if Hr < 1.0:
            continue
        a2, y2, inf = FOOT.rebuild_foot(A[r], Y[r], c[r], jf=prm["foot_jf"], Hr=Hr, depth_rel=prm["trough_rel"],
                                        seat_w=FOOT.seat_weight(c[r]), a_end_min=A[r, -1])
        A[r], Y[r] = a2, y2; info[r] = inf
    return A, Y, info


def step5_tube(A, Y, c, prm):
    """near rows (c < tube_c1): thin hooked lip + round tube (cols 200..399) with circle parameters that vary
    smoothly along the crest (radius and tip angle solved per row, then Gaussian-smoothed in c), blended in by c."""
    from scipy.ndimage import gaussian_filter1d as g1
    A = A.copy(); Y = Y.copy()
    rows = [r for r in range(NV) if c[r] < prm["tube_c1"] and Y[r, :200].max() >= prm["tube_Hmin"]]
    if not rows:
        return A, Y, 0
    Hr = np.array([Y[r, :200].max() for r in rows]); cr = np.array([c[r] for r in rows])
    # shallower tube on the far shoulder, the full round tube near the main curl
    k = smoothstep((cr - prm["tube_shoulder_c"][0]) / (prm["tube_shoulder_c"][1] - prm["tube_shoulder_c"][0]))
    rrel = prm["tube_r_rel_shoulder"] + (prm["tube_r_rel"] - prm["tube_r_rel_shoulder"]) * k
    R = g1(rrel * Hr, 2.0, mode="nearest")
    th = np.array([TUBE.solve_th_tip(A[r], Y[r], R[i], prm["tube_th_tip"]) for i, r in enumerate(rows)])
    # smooth the tip angle but never below what each row needs (clearance)
    ths = th.copy()
    for _ in range(4):
        ths = np.maximum(g1(ths, 3.0, mode="nearest"), th)
    n = 0
    for i, r in enumerate(rows):
        cc = c[r]
        w = 1 - smootherstep((cc - prm["tube_c0"]) / (prm["tube_c1"] - prm["tube_c0"]))
        if w <= 0:
            continue
        qa, qy, C = TUBE.tube_section_fixed(A[r], Y[r], R[i], ths[i])
        a_old, y_old = A[r].copy(), Y[r].copy()
        a2 = A[r].copy(); y2 = Y[r].copy()
        a2[200:] = (1 - w) * A[r, 200:] + w * qa; y2[200:] = (1 - w) * Y[r, 200:] + w * qy
        lk = LOCK_NOW[r] if LOCK_NOW is not None else np.zeros(NU, bool)
        bad = ~row_inside(a2, y2, cc, prm["margin_px"]) & (y2 > 2.5)
        bad[:200] = False
        for t in np.linspace(0.9, 0.0, 10):
            if not bad.any():
                break
            a2[bad] = a_old[bad] + t * (a2[bad] - a_old[bad]); y2[bad] = y_old[bad] + t * (y2[bad] - y_old[bad])
            bad = ~row_inside(a2, y2, cc, prm["margin_px"]) & (y2 > 2.5); bad[:200] = False
        # painting-locked vertices of the lip top keep their place; locked tube vertices (the painted claw
        # cluster edge near the tip) follow the new tube only if the silhouette check below still passes
        keep = lk.copy(); keep[201:] = False
        a2[keep] = a_old[keep]; y2[keep] = y_old[keep]
        A[r], Y[r] = a2, y2; n += 1
    return A, Y, n


LOCK_NOW = None


def current_lock(A, Y, c):
    d = inside_px(world(A, Y, c))
    return (d <= LOCK_PX) & (Y > 2.0)


def reparam_top(a, y, jtop=90, jtip=200):
    """put the crest (highest point before the tip) exactly on column jtop, resampling along the same polyline."""
    jt = int(np.argmax(y[:jtip]))
    if jt < 25 or jt > jtip - 25:
        return a, y
    a, y = sanitize(a, y)
    P = np.stack([a, y], -1)
    sb = arclen(P[18:jt + 1, 0], P[18:jt + 1, 1])
    wb = 1.0 + 2.0 * np.exp(-(sb[-1] - sb) / 2.5)          # denser near the crest (~0.12 m like the painted front)
    b = resample_w(P[18:jt + 1], jtop - 18 + 1, wb)
    sf = arclen(P[jt:jtip + 1, 0], P[jt:jtip + 1, 1])
    wf = 1.0 + 1.0 * np.exp(-sf / 2.5)
    f = resample_w(P[jt:jtip + 1], jtip - jtop + 1, wf)
    a2 = a.copy(); y2 = y.copy()
    a2[18:jtop + 1], y2[18:jtop + 1] = b[:, 0], b[:, 1]
    a2[jtop:jtip + 1], y2[jtop:jtip + 1] = f[:, 0], f[:, 1]
    return a2, y2


def step6_clean(A, Y, c, prm, cov0):
    A = A.copy(); Y = Y.copy()
    main = int(np.argmin(np.abs(c)))
    lk0 = current_lock(A, Y, c)
    for r in range(NV):
        if Y[r, :200].max() > 2.0:
            jt = int(np.argmax(Y[r, :200]))
            if (not prm["clean_reparam"]) or lk0[r, jt:200].sum() >= 15 or c[r] > 0:
                continue
            A[r], Y[r] = reparam_top(A[r], Y[r])
    lk = current_lock(A, Y, c)
    # the dense rows next to the main section (c -1.2 .. 0, spacing 3-13 cm): their hidden backs are interpolated
    # column-wise between the row at c -1.2 and the main section, so neighbouring rows do not crease
    main = int(np.argmin(np.abs(c))); ra = int(np.argmin(np.abs(c - prm["near_main_blend_c"])))
    dpx0 = inside_px(world(A, Y, c))
    for r in range(ra + 1, main):
        u = (c[r] - c[ra]) / (c[main] - c[ra])
        jt = int(np.argmax(Y[r, :200]))
        fr = (np.arange(NU) < jt - 6) & (dpx0[r] > 6.0)
        tw = np.clip((jt - 6 - np.arange(NU)) / 10.0, 0, 1)            # taper toward the painted crest
        tgtA = (1 - u) * A[ra] + u * A[main]; tgtY = (1 - u) * Y[ra] + u * Y[main]
        a2 = np.where(fr, A[r] + tw * (tgtA - A[r]), A[r]); y2 = np.where(fr, Y[r] + tw * (tgtY - Y[r]), Y[r])
        ok = row_inside(a2, y2, c[r], prm["margin_px"]) | (y2 < 2.5)
        A[r] = np.where(ok, a2, A[r]); Y[r] = np.where(ok, y2, Y[r])
        A[r], Y[r] = sanitize(A[r], Y[r], keep=lk[r])
    # per-vertex blend weight: 0 on locked vertices and in the crest window, tapering over ~8 columns
    from scipy.ndimage import gaussian_filter1d as g1
    dpx = inside_px(world(A, Y, c))
    om = np.clip((dpx - 6.0) / 6.0, 0, 1) * (~lk)          # vertices near the painting silhouette are not moved
    om[Y < 2.0] = (~lk[Y < 2.0]).astype(float)
    om[c > 0] = 0.0                                          # the far family is smooth in c by construction
    om *= smoothstep((-0.12 - c) / 1.0)[:, None]             # the main section (far-family template) stays; taper
    for r in range(NV):                                      # rows keeping their painted lip top: back only
        jt = int(np.argmax(Y[r, :200]))
        if lk0[r, jt:200].sum() >= 15:
            om[r, jt - 14:201] = 0.0
        if abs(c[r]) <= 0.12:                                # the painted rows at the main section keep their front
            om[r, jt - 14:] = 0.0
    w0, w1 = prm["clean_crest_win"]
    om[:, 90 - w0:90 + w1] = 0.0
    om[:, :1] = 0; om[:, -1:] = 0
    om = np.minimum(om, np.clip(g1(om, 3.0, axis=1) * 1.6 - 0.3, 0, 1))
    for it in range(prm["clean_iters"]):
        A0_, Y0_ = A.copy(), Y.copy()
        As = A.copy(); Ys = Y.copy()
        for (j0, j1), sig in zip(((0, 90), (90, 200), (200, NU)), prm["clean_sigma_cols"]):
            for r in range(1, NV - 1):
                wts = np.exp(-0.5 * ((c - c[r]) / sig) ** 2); wts[np.abs(c - c[r]) > 3 * sig] = 0
                wts /= wts.sum()
                nz = np.nonzero(wts)[0]
                As[r, j0:j1] = wts[nz] @ A[nz, j0:j1]; Ys[r, j0:j1] = wts[nz] @ Y[nz, j0:j1]
        for r in range(NV):
            t = om[r].copy()
            for k in range(8):
                a_ = A0_[r] + t * (As[r] - A0_[r]); y_ = Y0_[r] + t * (Ys[r] - Y0_[r])
                bad = ~row_inside(a_, y_, c[r], prm["margin_px"]) & (y_ > 2.5)
                if not bad.any():
                    break
                t[bad] *= 0.5
                t = np.minimum(t, np.clip(g1(t, 2.0) , 0, 1))      # neighbours back off smoothly too
            bad = ~row_inside(a_, y_, c[r], prm["margin_px"]) & (y_ > 2.5)
            a_[bad] = A0_[r, bad]; y_[bad] = Y0_[r, bad]
            A[r], Y[r] = sanitize(a_, y_, keep=lk[r])
    # final crest-window rounding per row (after the cross-row pass)
    dpx = inside_px(world(A, Y, c))
    lk6 = (dpx <= 6.0) & (Y > 2.0)
    for r in range(NV):
        if Y[r, :200].max() > 2.0 and c[r] <= 0.0:
            jt = int(np.argmax(Y[r, :200]))
            lkr = lk6[r] if lk[r, jt:200].sum() >= 15 else lk[r]
            A[r], Y[r] = round_crest(A[r], Y[r], c[r], lkr)
            if Y[r, :200].max() > 0.3 * H0:
                A[r], Y[r] = crest_best(A[r], Y[r], c[r], lk[r])
    # lip-top fairing (hidden parts): the painted claw-envelope bumps stay only where they are the silhouette
    dpx = inside_px(world(A, Y, c))
    for r in range(NV):
        if not (prm["liptop_fair_c"][0] <= c[r] <= prm["liptop_fair_c"][1]) or Y[r, :200].max() < 5:
            continue
        jt = int(np.argmax(Y[r, :200]))
        keep = np.ones(NU, bool); keep[jt + 8:199] = False
        keep |= dpx[r] < 4.0
        cap = np.where(keep, 0.0, prm["liptop_fair_cap"])
        a0_, y0_ = A[r].copy(), Y[r].copy()
        a2, y2 = capped_fair(A[r], Y[r], a0_, y0_, cap, iters=300, lam_=0.25, keep=keep)
        bad = ~row_inside(a2, y2, c[r], prm["margin_px"]) & (y2 > 2.5) & ~keep
        for t in np.linspace(0.8, 0.0, 5):
            if not bad.any():
                break
            a2[bad] = a0_[bad] + t * (a2[bad] - a0_[bad]); y2[bad] = y0_[bad] + t * (y2[bad] - y0_[bad])
            bad = ~row_inside(a2, y2, c[r], prm["margin_px"]) & (y2 > 2.5) & ~keep
        A[r], Y[r] = sanitize(a2, y2, keep=keep)
    # the tier tips (hook of the second crest): an extra cross-row smoothing of the tip region (hidden vertices)
    dpx = inside_px(world(A, Y, c))
    A1, Y1 = A.copy(), Y.copy()
    tr = [r for r in range(1, NV - 1) if prm["tier_c0"] - 1.0 <= c[r] <= prm["tier_c1"] + 3.0]
    for r in tr:
        wts = np.exp(-0.5 * ((c - c[r]) / 0.5) ** 2); wts[np.abs(c - c[r]) > 1.5] = 0; wts /= wts.sum()
        nz = np.nonzero(wts)[0]
        js = np.arange(180, 221)
        m = dpx[r, js] > 3.0
        A1[r, js[m]] = wts[nz] @ A[nz][:, js[m]]; Y1[r, js[m]] = wts[nz] @ Y[nz][:, js[m]]
    for r in tr:
        ok = row_inside(A1[r], Y1[r], c[r], prm["margin_px"]) | (Y1[r] < 2.5)
        A[r] = np.where(ok, A1[r], A[r]); Y[r] = np.where(ok, Y1[r], Y[r])
    # tip loops (lip top and underside crossing near the tip after the smoothing): collapse them
    for r in range(NV):
        A[r], Y[r] = remove_tip_loops(A[r], Y[r], keep=lk[r])
    dpx = inside_px(world(A, Y, c))
    for r in range(NV):                            # any remaining small loop (incl. painted-tip ones): whole row
        A[r], Y[r] = remove_tip_loops(A[r], Y[r], j0=20, j1=NU - 2, keep=dpx[r] < 0.5)
    # consistent sheet edges (flat back sea from a = -49.21, flat front sea to a = 32.53, as in K*)
    A0k, Y0k, _ = load_kstar()
    for r in range(NV):
        jb = 18
        a_b = A[r, jb]
        if A[r, 0] > A0k[r, 0] + 1e-6 or True:
            A[r, :jb + 1] = np.linspace(min(A0k[r, 0], a_b - 5.0), a_b, jb + 1); Y[r, :jb] = 0.0
        # front: last columns flat at y = 0 up to at least the K* front edge
        jf = int(np.nonzero(np.abs(Y[r]) > 1e-4)[0].max()) + 1 if (np.abs(Y[r]) > 1e-4).any() else NU - 6
        jf = min(max(jf, 380), NU - 3)
        if A[r, -1] < A0k[r, -1]:
            A[r, jf:] = np.linspace(A[r, jf], A0k[r, -1], NU - jf); Y[r, jf:] = 0.0
    # rows closer than 3 cm (K* rows 158/159, 2.99 cm): move row 158 along PaintingCam rays to c = -0.035 m
    # (camera-centre scaling keeps its painting image exactly)
    c = c.copy()
    dc = np.diff(c)
    for i in np.nonzero(dc < prm["min_row_gap"])[0]:
        r = i if abs(c[i]) > abs(c[i + 1]) else i + 1
        nb = r - 1 if r == i else r + 1
        c_new = c[nb] - np.sign(c[nb] - c[r]) * (prm["min_row_gap"] + 1e-4)
        A[r], Y[r] = cam_scale_row(A[r], Y[r], c[r], c_new); c[r] = c_new
    dc = np.diff(c)
    return A, Y, c, {"min_row_gap_m": float(dc.min())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", default="1,2")
    ap.add_argument("--tag", default="dev")
    args = ap.parse_args()
    steps = [int(s) for s in args.steps.split(",")]
    os.makedirs(WORK, exist_ok=True)
    A, Y, c = load_kstar()
    cov0 = np.load(os.path.join(WORK, "cov_kstar.npy"))
    lock = kstar_lock(A, Y, c)
    log("K* locked vertices (painting silhouette within %.1f px): %d" % (LOCK_PX, int(lock.sum())))
    t0 = time.time()
    # the main row's back first (template of the far family)
    if 2 in steps:
        main = int(np.argmin(np.abs(c)))
        A, Y, inf = step2_back(A, Y, c, lock, P, rows=[main])
    if 1 in steps:
        A, Y, c, S = step1_far(A, Y, c, P)
        lock = kstar_lock_new = lock  # far rows had no locked vertex left that matters (cone copies of the main)
        lock[np.argmin(np.abs(c)) + 1:] = False
        gate_step("s1_far", A, Y, c, cov0)
    if 2 in steps:
        A, Y, inf = step2_back(A, Y, c, lock, P)
        log("[back] rows rebuilt: %d" % len(inf))
        gate_step("s2_back", A, Y, c, cov0)
    if 3 in steps:
        A, Y, inf = step3_foot(A, Y, c, P)
        Ds = [v["D"] / max(Y[r, :200].max(), 1) for r, v in inf.items() if Y[r, :200].max() > 0.5 * H0]
        log("[foot] rows %d, D/H median %.2f" % (len(inf), float(np.median(Ds)) if Ds else 0))
        gate_step("s3_foot", A, Y, c, cov0)
    global LOCK_NOW
    if 4 in steps:
        lk4 = current_lock(A, Y, c)
        A, Y, inf4 = CR2.step4_crest2(A, Y, c, lk4, P)
        s1, nb = CR2.s1_fraction(A, Y, c, P)
        log("[crest2] rows %d; S1 (band foam on the tier) %.2f of %d px" % (len(inf4), s1, nb))
        gate_step("s4_crest2", A, Y, c, cov0)
    if 5 in steps:
        LOCK_NOW = current_lock(A, Y, c)
        A, Y, n5 = step5_tube(A, Y, c, P)
        log("[tube] near rows rebuilt: %d" % n5)
        gate_step("s5_tube", A, Y, c, cov0)
    if 6 in steps:
        A, Y, c, inf6 = step6_clean(A, Y, c, P, cov0)
        log("[clean] %s" % inf6)
        gate_step("s6_clean", A, Y, c, cov0)
    save_rows(os.path.join(WORK, "rows_%s.npz" % args.tag), A, Y, c)
    json.dump(LOG, open(os.path.join(WORK, "log_%s.json" % args.tag), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    log("done %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
