# -*- coding: utf-8 -*-
"""Independent recomputation of RT48 C2 (a)-(e) for the fine source (own code; only numpy/scipy/skimage).
Usage: py -3.10 q_c2.py"""
import json, time
import numpy as np
from scipy import ndimage
import q_lib as Q

T0 = time.time()
OFF = Q.still_offset_fine()
LC = 135.46329754326246
F0, F1 = 3319, 3889
frames = list(range(F0, F1 + 1))
SEC_LO, SEC_HI = 457.0 - Q.XP, 998.5 - Q.XP   # x_rel range of sec


def fine_main(f):
    phi, xs, ys = Q.load_phi(f)
    return Q.main_curve(phi, xs, ys - OFF)


def sec_crop(f):
    S, xs, ys = Q.load_sec(f)
    j0 = int(np.searchsorted(ys - Q.OFF_R3, -25.0))
    return S[j0:], xs, ys[j0:] - Q.OFF_R3


# ---- crest track on the fine main curve (own), and on the coarse manifest for comparison
crest = Q.track_crest(fine_main, frames, 261.53670245673754)
cm = json.load(open(Q.DATA + "/coarse/manifest.json", encoding="utf8"))
crest_coarse = {r["frame"]: r["crest_x"] for r in cm["frames"]}
dcrest = max(abs(crest[f][0] - crest_coarse[f]) for f in frames)
print("crest track: max |fine-own - coarse manifest| =", dcrest)

res = dict(tool="check_fine/q_c2.py", still_offset_fine=OFF, crest_track_max_diff_vs_coarse_manifest=dcrest)

# ---------------- (a)
rows = []
d_all = {"hf_node": [], "hf_interp_allcols": [], "sec_top": []}
worst = None
for f in frames:
    phi, xs, ys = Q.load_phi(f)
    hfin, nchg = Q.top_height(phi, ys - OFF)
    eta, xh = Q.load_hf(f)
    eta = eta - Q.OFF_R3
    slope = np.degrees(np.arctan(np.abs(np.gradient(eta, xh[1] - xh[0]))))
    S, sx, sy = sec_crop(f)
    hs, ns = Q.top_height(S, sy)
    xc = crest[f][0]
    # variant 1: fine columns on hf nodes (every 4th fine column is on a 0.5 m node)
    ii = np.rint((xs - xh[0]) / 0.5).astype(int)
    on_node = np.abs(xs - xh[ii]) < 1e-6
    ns_at = np.ones(len(xs), int)
    ins = (xs >= sx[0] - 1e-6) & (xs <= sx[-1] + 1e-6)
    js = np.clip(np.rint((xs - sx[0]) / 0.5).astype(int), 0, len(sx) - 1)
    ns_at[ins & on_node] = ns[js[ins & on_node]]
    ok = on_node & (np.abs(xs - xc) > 20.0) & (nchg == 1) & (ns_at == 1) & (slope[ii] < 30.0) & np.isfinite(hfin)
    d = np.abs(hfin[ok] - eta[ii[ok]])
    d_all["hf_node"].append(d)
    if len(d) and (worst is None or d.max() > worst[0]):
        k = int(np.argmax(d)); worst = (float(d.max()), f, float(xs[ok][k]))
    # variant 2: every fine column, hf interpolated linearly in x
    eta_i = np.interp(xs, xh, eta); sl_i = np.interp(xs, xh, slope)
    ok2 = (np.abs(xs - xc) > 20.0) & (nchg == 1) & (sl_i < 30.0) & np.isfinite(hfin)
    d_all["hf_interp_allcols"].append(np.abs(hfin[ok2] - eta_i[ok2]))
    # variant 3: solver height from sec top crossing (only inside sec), on nodes
    ok3 = ok & ins
    d_all["sec_top"].append(np.abs(hfin[ok3] - hs[js[ok3]]))
ra = {}
for k, v in d_all.items():
    v = np.concatenate(v)
    ra[k] = dict(n=int(len(v)), p99=float(np.percentile(v, 99)), max=float(v.max()), median=float(np.median(v)))
ra["worst_hf_node"] = worst
ra["ok_hf_node"] = bool(ra["hf_node"]["p99"] <= 0.10 and ra["hf_node"]["max"] <= 0.25)
res["a"] = ra
print("(a)", json.dumps(ra))


# ---------------- (b) onset, (d) first contact, (e) lip
def face_analysis(P, xc_hint, vox=0.5):
    """crest = highest point within +-40 m of hint; front face = curve after crest until y<=0 or |x-xc|>Lc;
    angle of 0.5 m chords; tip = first local x max followed by >= 0.5 m retreat (within crest+30 m)."""
    m = np.abs(P[:, 0] - xc_hint) <= 40.0
    ic = np.where(m)[0][int(np.argmax(P[m, 1]))]
    xc, yc = P[ic]
    fwd = P[ic:]
    end = len(fwd)
    for j in range(1, len(fwd)):
        if fwd[j, 1] <= 0.0 or abs(fwd[j, 0] - xc) > LC:
            end = j + 1
            break
    face = Q.resample_step(fwd[:end], 0.25 * vox * 2 / 2)  # 0.25 m spacing
    d = face[2:] - face[:-2]                                 # 0.5 m chord
    th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
    okm = (th >= 0) & (th <= 180)
    thmax = float(th[okm].max()) if okm.any() else float("nan")
    iv = np.where(okm & (th >= 90.0))[0]
    xv = float(face[iv[0] + 1, 0]) if len(iv) else None
    # lip tip on the raw vertices
    tip = None
    xx = fwd[:end, 0]
    for j in range(1, len(xx) - 1):
        if xx[j] - xc > 30.0:
            break
        if xx[j] >= xx[j - 1] and xx[j] > xx[j + 1]:
            # local max; retreat >= vox later (before the curve passes this x again going forward)
            rest = xx[j:]
            mn = np.minimum.accumulate(rest)
            if (xx[j] - mn).max() >= vox:
                tip = j
                break
    lip = None
    if tip is not None:
        under = fwd[tip:end]
        xb = float(under[:, 0].min())
        xt = float(fwd[tip, 0]); yt = float(fwd[tip, 1])
        xm = 0.5 * (xt + xb)
        def cross(seg, x):
            ys = []
            for a, b in zip(seg[:-1], seg[1:]):
                if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
                    ys.append(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))
            return ys
        up = cross(fwd[:tip + 1], xm); lo = cross(under, xm)
        thick = None
        if up and lo:
            u = max(up)
            lows = [v for v in lo if v < u]
            if lows:
                thick = u - max(lows)
        lip = dict(x_tip=xt, y_tip=yt, x_back=xb, reach=xt - xb, thick=thick)
    return dict(xc=float(xc), yc=float(yc), thmax=thmax, x_vertical=xv, lip=lip)


def cavities(F, xs, ys, xc, yc, win=30.0, amin=0.25):
    out = []
    m = (xs >= xc - win - 2) & (xs <= xc + win + 2)
    for P, ph, A in Q.closed_loops(F[:, m], xs[m], ys):
        if ph == 1 and A >= amin and P[:, 0].max() >= xc - win and P[:, 0].min() <= xc + win and P[:, 1].mean() < yc:
            out.append([float(P[:, 0].min()), float(P[:, 0].max()), float(A)])
    return out


def run_bde(kind):
    rows = []
    on = None; contact = None; lips = []
    for f in range(3680, 3801):
        if kind == "fine":
            phi, xs, ys = Q.load_phi(f)
            yh = ys - OFF
            sel = (xs >= SEC_LO - 1e-6) & (xs <= SEC_HI + 1e-6)
            F = phi[:, sel]; X = xs[sel]
        else:
            F, X, yh = sec_crop(f)
        P = Q.main_curve(F, X, yh)
        fa = face_analysis(P, crest[f][0])
        # eta_c: top crossing in the column nearest the crest
        ic = int(np.argmin(np.abs(X - fa["xc"])))
        h, _ = Q.top_height(F[:, ic:ic + 1], yh)
        fa["eta_c"] = float(h[0])
        fa["frame"] = f
        fa["cav"] = cavities(F, X, yh, crest[f][0], fa["yc"]) if f >= 3700 else []
        rows.append(fa)
        if on is None and np.isfinite(fa["thmax"]) and fa["thmax"] >= 90.0:
            on = dict(frame=f, x=fa["x_vertical"], eta_c=fa["eta_c"], thmax=fa["thmax"], xc=fa["xc"])
        elif on is not None and contact is None and fa["cav"]:
            contact = f
        if on is not None and contact is None and fa["lip"] is not None:
            lips.append((f, fa["lip"]))
    best = max(lips, key=lambda q: q[1]["reach"]) if lips else None
    return dict(onset=on, first_contact=contact, lip_max=dict(frame=best[0], **best[1]) if best else None,
                rows=[{k: r[k] for k in ("frame", "thmax", "x_vertical", "xc", "yc", "eta_c", "lip", "cav")} for r in rows])


for kind in ("fine", "solver"):
    r = run_bde(kind)
    res["bde_" + kind] = r
    print(kind, "onset", r["onset"], "contact", r["first_contact"], "lip", r["lip_max"])
    for row in r["rows"]:
        if 3704 <= row["frame"] <= 3716 or 3740 <= row["frame"] <= 3746:
            print("   ", row["frame"], round(row["thmax"], 1), row["x_vertical"], round(row["xc"], 2), round(row["eta_c"], 3),
                  None if not row["lip"] else (round(row["lip"]["reach"], 2), row["lip"]["thick"] and round(row["lip"]["thick"], 2)), row["cav"])

# ---------------- (c)
H = 0.125


def solver_water(f, X, Yh, shift):
    """solver water mask at points (X, Yh = height above fine still level + shift)"""
    S, sx, sy_abs = Q.load_sec(f)
    eta, xh = Q.load_hf(f)
    Ya = Yh + shift
    out = np.zeros(X.shape, bool)
    ins = (X >= sx[0]) & (X <= sx[-1])
    if ins.any():
        v = Q.bilinear(S, sx, sy_abs, X[ins], Ya[ins])
        out[ins] = v < 0
    if (~ins).any():
        out[~ins] = Ya[~ins] < np.interp(X[~ins], xh, eta)
    return out


def drop_small(mask, conn):
    st = ndimage.generate_binary_structure(2, conn)
    lab, n = ndimage.label(mask, structure=st)
    if n == 0:
        return mask, 0
    keep_bottom = set(np.unique(lab[0])) - {0}
    sizes = ndimage.sum(mask, lab, np.arange(1, n + 1)) * H * H
    drop = [i + 1 for i in range(n) if (i + 1) not in keep_bottom and sizes[i] < 0.25]
    if drop:
        mask = mask & ~np.isin(lab, drop)
    return mask, len(drop)


variants = {"own_level(+0.1168 abs vs +0.1457 abs)": (Q.OFF_R3 + 0.0, 1), "same_physical_y": (None, 1), "8-connected": (Q.OFF_R3, 2)}
rc = {}
for name, (shift, conn) in variants.items():
    rows_c = []; nd = [0, 0]
    for f in range(3319, 3797):
        phi, xs, ys = Q.load_phi(f)
        xc = crest[f][0]
        m = (xs >= xc - 20.0) & (xs <= xc + 20.0)
        Fw = phi[:, m] < 0
        Xg = np.broadcast_to(xs[m][None, :], Fw.shape)
        Yh = np.broadcast_to((ys - OFF)[:, None], Fw.shape)
        sh = shift if shift is not None else OFF   # same physical y: Ya = ys_abs
        Sw = solver_water(f, Xg, Yh, sh)
        Fw, a1 = drop_small(Fw, conn); Sw, a2 = drop_small(Sw, conn)
        nd[0] += a1; nd[1] += a2
        dS = ndimage.distance_transform_edt(~Sw) * H
        dF = ndimage.distance_transform_edt(~Fw) * H
        m1 = float(dS[Fw].max()) if Fw.any() else 0.0
        m2 = float(dF[Sw].max()) if Sw.any() else 0.0
        rows_c.append([f, m1, m2])
    arr = np.array(rows_c)
    over = arr[(arr[:, 1] > 0.5) | (arr[:, 2] > 0.5)]
    rc[name] = dict(max_fine_to_solver=float(arr[:, 1].max()), frame_max=int(arr[np.argmax(arr[:, 1]), 0]),
                    max_solver_to_fine=float(arr[:, 2].max()), n_frames_over=int(len(over)),
                    n_over_before_contact=int((over[:, 0] < 3745).sum()), frames_over_before_contact=[int(v) for v in over[over[:, 0] < 3745, 0]],
                    max_before_contact=float(arr[arr[:, 0] < 3745, 1:].max()), dropped=nd)
    print("(c)", name, json.dumps(rc[name]))
res["c"] = rc
res["seconds"] = round(time.time() - T0, 1)
json.dump(res, open(Q.OUT + "/q_c2.json", "w"), indent=1, default=float)
print("done", res["seconds"])
