# -*- coding: utf-8 -*-
"""Independent C5/C6 for the fine source from the saved Unity exports (verify/fine/unity_editor, unity_player) and the fine bake.
C5: Unity-decoded points vs (1-a)A+aB computed here in float64; normals vs own normals; Editor vs player byte identity; landmarks.
C6: boat heave/pitch from own code on the baked curve (before K) and from an own per-frame table (after K) vs Unity's values;
    own per-frame table also from the stored phi contours (not the bake) to see the bake's effect; clip end (overturned water on hull).
Usage: py -3.10 q_c5c6.py"""
import json, hashlib, time
import numpy as np
import q_lib as Q

T0 = time.time()
V = Q.ROOT + "/Unity/Build/RT48/verify/fine"
OFF = Q.still_offset_fine()
man = json.load(open(Q.DATA + "/fine/manifest.json", encoding="utf8"))
pairs = np.memmap(Q.DATA + "/fine/pairs.bin", dtype="<f4", mode="r", shape=(570, 2, 8192, 2))
HULL = np.array([-6.0, -4.5, -3.0, -1.5, 0.0, 1.5, 3.0, 4.5, 6.0])
res = {}


def sha(fn):
    h = hashlib.sha256()
    with open(fn, "rb") as fp:
        for b in iter(lambda: fp.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


# ---- Editor vs player identity
for nm in ("curves.bin", "holdout_out.bin"):
    a = sha(V + "/unity_editor/" + nm); b = sha(V + "/unity_player/" + nm)
    res["identical_" + nm] = (a == b)
ie = json.load(open(V + "/unity_editor/index.json", encoding="utf8"))
ip = json.load(open(V + "/unity_player/index.json", encoding="utf8"))
res["index_curves_same"] = ie["curves"] == ip["curves"]
res["player_isEditor"] = ip.get("isEditor")
print("identity", res)

# ---- C5 positions and normals (editor export)
cur = np.memmap(V + "/unity_editor/curves.bin", dtype="<f4", mode="r")
tol = 1e-4
mx = {"all": 0.0, "x200_825": 0.0}
mx_rel = 0.0; nmax = 0.0; nmax_inner = 0.0; nfail = 0
groups = {}
taper_seen = 0.0
for e in ie["curves"]:
    p = e["pair"]; a = e["alpha"]; seat = e["seatX"]
    U = np.array(cur[e["offsetFloats"]:e["offsetFloats"] + 8192 * 4], dtype=np.float64).reshape(8192, 4)
    A = np.array(pairs[p, 0], dtype=np.float64); B = np.array(pairs[p, 1], dtype=np.float64)
    E = (1 - a) * A + a * B
    EX = E[:, 0] + Q.X0B - seat
    xr = E[:, 0] + Q.X0B
    inner = (xr >= 200) & (xr <= 825)
    dpos = np.hypot(U[:, 0] - EX, U[:, 1] - E[:, 1])
    # float32 spacing allowance as in the plan: max(1e-4, 4 ulp of |X|)
    ulp4 = 4 * np.spacing(np.abs(U[:, 0]).astype(np.float32)).astype(np.float64)
    allow = np.maximum(tol, ulp4)
    g = groups.setdefault(e["group"], dict(n=0, max_pos_inner=0.0, max_pos_taper=0.0, max_norm_deg_inner=0.0, n_fail=0))
    g["n"] += 1
    g["max_pos_inner"] = max(g["max_pos_inner"], float(dpos[inner].max()))
    g["max_pos_taper"] = max(g["max_pos_taper"], float(dpos[~inner].max()))
    g["n_fail"] += int((dpos[inner] > allow[inner]).any())
    # normals: perpendicular of central difference (one-sided at the ends), pointing up-ish (left of the direction of increasing index)
    T = np.empty_like(E)
    T[1:-1] = E[2:] - E[:-2]; T[0] = E[1] - E[0]; T[-1] = E[-1] - E[-2]
    Nn = np.stack([-T[:, 1], T[:, 0]], 1); Nn /= np.linalg.norm(Nn, axis=1)[:, None]
    Un = U[:, 2:4] / np.linalg.norm(U[:, 2:4], axis=1)[:, None]
    ang = np.degrees(np.arccos(np.clip((Nn * Un).sum(1), -1, 1)))
    g["max_norm_deg_inner"] = max(g["max_norm_deg_inner"], float(ang[inner].max()))
res["C5_positions"] = groups
print("C5", json.dumps(groups))

# ---- C5 landmarks: own onset/contact/lip from q_c2 output vs Unity export at those frames (alpha 0 of pair frame-3319)
c2 = json.load(open(Q.OUT + "/q_c2.json"))
lm = {}
for name, f, xy in (("lip_3744", 3744, (c2["bde_fine"]["lip_max"]["x_tip"], c2["bde_fine"]["lip_max"]["y_tip"])),):
    e = [c for c in ie["curves"] if c["pair"] == f - 3319 and c["alpha"] == 0.0 and c["seatX"] == 556.0][0]
    U = np.array(cur[e["offsetFloats"]:e["offsetFloats"] + 8192 * 4], dtype=np.float64).reshape(8192, 4)
    X = U[:, 0] + 556.0
    m = np.abs(X - xy[0]) < 3
    d = np.hypot(X[m] - xy[0], U[m, 1] - xy[1])
    lm[name] = dict(own=xy, unity_nearest_point_dist=float(d.min()))
res["C5_landmarks"] = lm
print("landmarks", lm)

# ---- C6
def top_at(curve, xq):
    """highest intersection of vertical lines x=xq with polyline curve (X, Y)."""
    X = curve[:, 0]; Y = curve[:, 1]
    out = np.full(len(xq), np.nan)
    for n, x in enumerate(xq):
        s = (X[:-1] - x) * (X[1:] - x) <= 0
        s &= X[:-1] != X[1:]
        i = np.where(s)[0]
        if len(i):
            y = Y[i] + (Y[i + 1] - Y[i]) * (x - X[i]) / (X[i + 1] - X[i])
            out[n] = y.max()
    return out


def boat(curve_xrel, seat):
    xq = seat + HULL
    h = top_at(curve_xrel, xq)
    heave = float(h.mean())
    slope = np.polyfit(HULL, h, 1)[0]
    return heave, float(np.degrees(np.arctan(slope)))


# own per-frame table from the baked frame curves (A of pair f; the last frame from B of the last pair)
def frame_curve_bake(f):
    if f < 3889:
        C = np.array(pairs[f - 3319, 0], dtype=np.float64)
    else:
        C = np.array(pairs[569, 1], dtype=np.float64)
    C[:, 0] += Q.X0B
    return C


tabs = {}
for seat in (556.0, 574.0):
    tb = np.array([boat(frame_curve_bake(f), seat) for f in range(3319, 3890)])
    tc = []
    for f in range(3319, 3890):
        phi, xs, ys = Q.load_phi(f)
        tc.append(boat(Q.main_curve(phi, xs, ys - OFF), seat))
    tc = np.array(tc)
    mb = man["boat"][str(int(seat))]
    hm = np.array(mb["heave_m"]); pm = np.array(mb["pitch_deg"])
    end = mb["clip_end_frame"]
    sl = slice(0, end - 3319 + 1)
    tabs[seat] = tb
    res.setdefault("C6_table", {})[str(int(seat))] = dict(
        bake_vs_manifest_max_dh=float(np.abs(tb[:, 0] - hm).max()), bake_vs_manifest_max_dp=float(np.abs(tb[:, 1] - pm).max()),
        contour_vs_bake_max_dh_to_end=float(np.abs(tc[sl, 0] - tb[sl, 0]).max()), contour_vs_bake_max_dp_to_end=float(np.abs(tc[sl, 1] - tb[sl, 1]).max()),
        heave_range_to_end=[float(tb[sl, 0].min()), float(tb[sl, 0].max())], pitch_range_to_end=[float(tb[sl, 1].min()), float(tb[sl, 1].max())],
        pitch_rate_max_degps=float(np.abs(np.diff(tb[sl, 1])).max() * 24), heave_rate_max_mps=float(np.abs(np.diff(tb[sl, 0])).max() * 24),
        pitch_rate_max_degps_contour=float(np.abs(np.diff(tc[sl, 1])).max() * 24))
print("C6 table", json.dumps(res["C6_table"]))

# Unity boat records
rows = []
K = man["playback"]["K"]
for b in ie["boats"]:
    seat = b["seatX"]; t = b["t"]
    if b["mode"] == "curve":
        p = b["pair"]; w = b["w"]
        C = (1 - w) * np.array(pairs[p, 0], dtype=np.float64) + w * np.array(pairs[p, 1], dtype=np.float64)
        C[:, 0] += Q.X0B
        h, pdg = boat(C, seat)
    else:
        fr = (t - Q.t_of(3319)) * 24.0
        i0 = int(np.floor(fr + 1e-9)); u = fr - i0
        tb = tabs[seat]
        i1 = min(i0 + 1, len(tb) - 1)
        h = (1 - u) * tb[i0, 0] + u * tb[i1, 0]; pdg = (1 - u) * tb[i0, 1] + u * tb[i1, 1]
    rows.append(dict(seat=seat, t=t, mode=b["mode"], dh=abs(h - b["heave"]), dp=abs(pdg - b["pitchDeg"]),
                     droot=abs(b["rootY"] - b["heave"]), drot=abs(b["rootRollZDeg"] - b["pitchDeg"])))
res["C6_unity"] = dict(n=len(rows), max_dh=max(r["dh"] for r in rows), max_dp=max(r["dp"] for r in rows),
                       max_dh_curve=max(r["dh"] for r in rows if r["mode"] == "curve"), max_dh_lerp=max([r["dh"] for r in rows if r["mode"] != "curve"] or [0]),
                       max_root_minus_heave=max(r["droot"] for r in rows), max_rot_minus_pitch=max(r["drot"] for r in rows))
print("C6 unity", res["C6_unity"])


# ---- clip end: first frame after first contact with a multi-valued column (>=2 water/air changes above -10 m) within seat +-6 m
def overturned_frame(seat):
    for f in range(3745, 3890):
        phi, xs, ys = Q.load_phi(f)
        yh = ys - OFF
        F = phi[yh >= -10.0]
        m = np.abs(xs - seat) <= 6.0
        n = np.abs(np.diff((F[:, m] < 0).astype(np.int8), axis=0)).sum(0)
        if (n >= 2).any():
            return f
    return None


res["clip_end"] = {str(int(s)): dict(overturned_on_hull=overturned_frame(s), manifest=man["boat"][str(int(s))]["overturned_on_hull_frame"]) for s in (556.0, 574.0)}
print("clip end", res["clip_end"])
res["seconds"] = round(time.time() - T0, 1)
json.dump(res, open(Q.OUT + "/q_c5c6.json", "w"), indent=1, default=float)
