# -*- coding: utf-8 -*-
"""Holes (open boundary loops) of the FLIP50 surface records and whether the FLIP3D cameras see through them (py -3.10 -B; numpy + scipy).
2026-10-17 written new (Claude). READ ONLY: reads the run's surf/s_FFFFF.gw45s and r4_*.npz, the clips' manifest.json / bed.f32 and the
existing Unity captures' frames.csv; writes only <out>/ (default Unity/Build/FLIP3D/holes_DM1Ar_k4_r24/).

Why: from the new front seats a round sky-blue 'opening' appears in the wave face around touchdown. It is a hole in the recorded surface
mesh (the surfacing rules surf_layer_m 2.5 / surf_keep_vox 1 drop triangles), not a gap in the water (r4 SDF says water). The water
shader culls back faces, so through the hole the viewer sees past the mesh. This tool counts the holes and tests visibility.

Per record (plan coordinates x / up / lateral = Unity x / y / z; the player draws the record and its mirror z -> -z):
  boundary edges = edges used by exactly one triangle; loops = connected components of the boundary-edge graph.
  class: domain   (touches the crop box: x < 1 or > 411, lateral > 94, up < -14; the outer rim of the record),
         bed      (>= half of the loop's vertices within 1 m of the bed: the surf_bed_vox cut along the bed),
         bedlayer (the loop's surface lies mostly within 2 m of the bed: a submerged layer ~1 m above the bed, under the free surface),
         hole     (other loops on a surface of >= 2000 triangles: an opening in the free surface / wave body),
         fragment (other loops on a smaller surface: the rim of a detached sheet or piece, or an opening in it).
         'seam' = the loop touches lateral < 0.3 m (the symmetry cut); with the mirror copy such an opening is twice as wide. A loop that
         only runs along the seam (the cut itself, closed by the mirror copy) is also in domain or seam-only (no area off the seam).
  size: |vector area| = 0.5 |sum a x b| over the loop's directed boundary edges (area of the opening projected on its mean plane),
        d_eq = 2 sqrt(A / pi), perimeter, extent (bbox diagonal). water: r4 SDF (1 m grid, negative = liquid) at the loop centroid.
What the cameras see (loop window records only; seat A / B / C = each seat clip's manifest pose with the per-record eye position of the
existing seat capture capture_DM1Ar_k4_r24_seat<L>/seat/frames.csv (blend 0); print = the manifest cam_print_* pose, same for all seats):
  one ray per 4 x 4 pixel block of the 1920 x 1080 frame (480 x 270 rays, Unity's vertical fov and 16:9) against both copies of the record
  (outward normal = the stored vertex normals = -(b-a)x(c-a); front = outward normal toward the camera). Per ray:
    back_only   no front face on the ray but a back face: the current shader (Cull Back) shows what is behind the mesh (the sky if the ray
                goes up, the bed / sea if down); a double-sided render shows the back face as water. A closed surface seen from outside can
                not give this, so these rays enter the water through an opening of the mesh (a hole, or an open rim).
    back_front  a back face before the first front face: double-sided changes which water is shown.
    open_both_sides  no face at all, but the ray passes through water by the r4 SDF (< -0.25 m) within 150 m: an opening through both
                sides, which double-sided can not close (checked only near water pixels).
  The masks are saved (pixel_masks_480x270.npz, np.packbits per camera / record) to compare with the Unity captures.
Tags in the outputs: 【測定】 counts / areas / rays on the records, 【選び】 thresholds (0.3 m seam, 1 / 2 m bed, 2000 triangles, --amin,
480 x 270 rays, -0.25 m).

  py -3.10 -B f3d50_holes.py [--first 1729] [--last 2071] [--amin 0.1] [--out <dir>]
"""
import os, sys, json, csv, struct, glob, time
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.ndimage import map_coordinates, binary_dilation

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
RUN = "DM1Ar_D19B_T12_th80_dp0p5_c1728_t86p25"
RR = REPO + "/Unity/Build/FLIP50/runs/" + RUN
B3D = REPO + "/Unity/Build/FLIP3D"
HEAD = struct.Struct("<8sIIdiIIffffffff")
SEATS = "ABC"
SEAM_M, BED_M, BEDLAYER_M, BIG_TRIS, EPS = 0.3, 1.0, 2.0, 2000, 0.3     # 【選び】


def surf(f):
    """positions (plan, float64), stored vertex normals (outward), triangles, time. Same decoding as FLIP3DClip.DecodeInto (no index swap:
    the plan winding is kept; outward = the stored normals = -(b-a)x(c-a), counted per record in winding_sign_mismatch_tris)."""
    b = open(RR + "/surf/s_%05d.gw45s" % f, "rb").read()
    magic, ver, hb, t, fr, nv, nt, x0, y0, z0, x1, y1, z1, off, _ = HEAD.unpack_from(b, 0)
    if magic != b"GW45SRF1" or fr != f:
        raise SystemExit("bad record %d" % f)
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(nv, 3); o += nv * 6
    nq = np.frombuffer(b, np.uint16, nv * 2, o).reshape(nv, 2).astype(np.float64); o += nv * 4 + nv * 6
    T = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3).astype(np.int64)
    lo = np.array([x0, y0, z0], np.float64); hi = np.array([x1, y1, z1], np.float64)
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    x = nq[:, 0] / 65535.0 * 2 - 1; y = nq[:, 1] / 65535.0 * 2 - 1; z = 1 - np.abs(x) - np.abs(y); tt = np.maximum(-z, 0)
    x = np.where(x >= 0, x - tt, x + tt); y = np.where(y >= 0, y - tt, y + tt)
    N = np.stack([x, y, z], 1); N /= np.linalg.norm(N, axis=1, keepdims=True)
    return P, N, T, t


class Bed:
    def __init__(self, cdir):
        m = json.load(open(cdir + "/manifest.json", encoding="utf8"))
        self.h = np.fromfile(cdir + "/" + m["bed_file"], np.float32).reshape(m["bed_nz"], m["bed_nx"]).astype(np.float64)
        self.x0, self.z0, self.dx = m["bed_x0"], m["bed_z0"], m["bed_dx"]

    def at(self, x, lat):
        return map_coordinates(self.h, np.stack([(np.abs(lat) - self.z0) / self.dx, (x - self.x0) / self.dx]), order=1, mode="nearest")


class R4:
    def __init__(self):
        self.where = {}
        for p in sorted(glob.glob(RR + "/r4_c*_b*.npz")):
            with np.load(p) as d:
                for i, f in enumerate(d["frames"].tolist()):
                    self.where[int(f)] = (p, i)
        self.cur = None

    def sdf(self, f, Q):
        if f not in self.where or len(Q) == 0:
            return np.full(len(Q), np.nan)
        p, i = self.where[f]
        if self.cur is None or self.cur[0] != p:
            with np.load(p) as d:
                self.cur = (p, d["sdf"].astype(np.float32), json.loads(str(d["meta"])))
        S, m = self.cur[1][i], self.cur[2]
        ix = (Q[:, 0] - m["x0"]) / m["dx"]; iy = (Q[:, 1] - m["y0"]) / m["dy"]; iz = (np.abs(Q[:, 2]) - m["z0"]) / m["dz"]
        inb = (ix >= 0) & (ix <= m["nx"] - 1) & (iy >= 0) & (iy <= m["ny"] - 1) & (iz >= -0.5) & (iz <= m["nz"] - 1)
        v = map_coordinates(S, np.stack([np.maximum(iz, 0), iy, ix]), order=1, mode="nearest")
        return np.where(inb, v, np.nan)


def loops(P, N, T, bed):
    nv = len(P)
    E = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    key = np.minimum(E[:, 0], E[:, 1]) * (nv + 1) + np.maximum(E[:, 0], E[:, 1])
    _, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    bd = E[cnt[inv] == 1]
    n_nonmanifold = int((cnt > 2).sum())
    if len(bd) == 0:
        return [], dict(boundary_edges=0, nonmanifold_edges=n_nonmanifold)
    g = coo_matrix((np.ones(len(bd)), (bd[:, 0], bd[:, 1])), shape=(nv, nv))
    _, lab = connected_components(g, directed=False)
    ce = lab[bd[:, 0]]
    u, ci = np.unique(ce, return_inverse=True)
    k = len(u)
    a, b = P[bd[:, 0]], P[bd[:, 1]]
    seg = np.linalg.norm(b - a, axis=1)
    cr = np.cross(a, b)
    va = np.stack([np.bincount(ci, cr[:, j], k) for j in range(3)], 1) * 0.5
    ne = np.bincount(ci, minlength=k)
    per = np.bincount(ci, seg, k)
    cen = np.stack([np.bincount(ci, a[:, j], k) for j in range(3)], 1) / ne[:, None]
    nm = np.stack([np.bincount(ci, N[bd[:, 0], j], k) for j in range(3)], 1)
    nm /= np.maximum(np.linalg.norm(nm, axis=1, keepdims=True), 1e-12)
    order = np.argsort(ci, kind="stable"); starts = np.r_[0, np.cumsum(ne)[:-1]]
    aa = a[order]
    mn = np.minimum.reduceat(aa, starts, axis=0); mx = np.maximum.reduceat(aa, starts, axis=0)
    gap = aa[:, 1] - bed.at(aa[:, 0], aa[:, 2])
    nearbed = np.add.reduceat((gap < BED_M).astype(np.int64), starts) / ne
    offseam = np.add.reduceat((aa[:, 2] >= SEAM_M).astype(np.int64), starts)
    # the surface (triangle component) each loop belongs to, and how much of that surface lies on the bed (a submerged layer about 1 m
    # above the bed, under the free surface: the surfacing keeps it because it is within surf_keep_vox of the FLIP surface field there)
    gt = coo_matrix((np.ones(2 * len(T)), (np.r_[T[:, 0], T[:, 1]], np.r_[T[:, 1], T[:, 2]])), shape=(nv, nv))
    _, vl = connected_components(gt, directed=False)
    tl = vl[T[:, 0]]
    tsize = np.bincount(tl, minlength=vl.max() + 1)
    Gt = P[T].mean(1)
    onbed = np.bincount(tl, (Gt[:, 1] - bed.at(Gt[:, 0], Gt[:, 2]) < BEDLAYER_M).astype(np.float64), vl.max() + 1) / np.maximum(tsize, 1)
    lc = vl[bd[order[starts], 0]]
    comp_tris, comp_onbed = tsize[lc], onbed[lc]
    out = []
    for j in range(k):
        A = float(np.linalg.norm(va[j]))
        seam = bool(mn[j, 2] < SEAM_M)
        if mn[j, 0] < 1.0 or mx[j, 0] > 411.0 or mx[j, 2] > 94.0 or mn[j, 1] < -14.0:
            cls = "domain"
        elif seam and offseam[j] == 0:
            cls = "seam-only"
        elif nearbed[j] >= 0.5:
            cls = "bed"
        elif comp_onbed[j] >= 0.5:
            cls = "bedlayer"
        else:
            cls = "hole" if comp_tris[j] >= BIG_TRIS else "fragment"
        out.append(dict(cls=cls, seam=seam, edges=int(ne[j]), perim_m=float(per[j]), area_m2=A, d_eq_m=2 * np.sqrt(A / np.pi),
                        extent_m=float(np.linalg.norm(mx[j] - mn[j])), cen=cen[j], n=nm[j], lo=mn[j], hi=mx[j],
                        sense=float(va[j] @ nm[j] / max(A, 1e-9)), comp_tris=int(comp_tris[j]), comp_onbed=float(comp_onbed[j]),
                        nearbed=float(nearbed[j])))
    return out, dict(boundary_edges=int(len(bd)), nonmanifold_edges=n_nonmanifold)


def camera_basis(pos, look):
    fw = np.asarray(look, float) - np.asarray(pos, float); fw /= np.linalg.norm(fw)
    rt = np.array([fw[2], 0.0, -fw[0]]); rt /= np.linalg.norm(rt)       # Unity LookRotation(forward, up): right = cross(up, forward)
    up = np.cross(fw, rt)
    return fw, rt, up


class Scene:
    """both copies (record + mirror z -> -z) of one record, as the player draws them"""
    def __init__(self, P, T):
        Pm = P * np.array([1, 1, -1.0])
        self.V = [np.concatenate([P[T[:, k]], Pm[T[:, k]]]) for k in range(3)]
        n = -np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        self.n = np.concatenate([n, n * np.array([1, 1, -1.0])])          # outward (mirroring keeps it outward: the player mirrors by scale)


def raycast(sc, C0, fw, rt, up, fov, W, H):
    """one ray per pixel centre of a W x H frame (16:9, vertical fov as Unity), against both copies. Returns per pixel: t of the first front
    face (inf if none), t of the first face of either side, and the ray directions. Triangles are binned to the pixels their screen box covers
    (a small rasteriser); triangles with a corner within 0.3 m of the camera plane are skipped (the near clip plane is 0.3 m)."""
    tv = np.tan(np.radians(fov) / 2); asp = 16.0 / 9.0
    cam = [np.stack([(v - C0) @ rt, (v - C0) @ up, (v - C0) @ fw], 1) for v in sc.V]
    dz = np.minimum(np.minimum(cam[0][:, 2], cam[1][:, 2]), cam[2][:, 2])
    keep = dz > 0.3
    px = [((c[:, 0] / np.maximum(c[:, 2], 1e-6)) / (tv * asp) + 1) * 0.5 * W - 0.5 for c in cam]
    py = [(1 - (c[:, 1] / np.maximum(c[:, 2], 1e-6)) / tv) * 0.5 * H - 0.5 for c in cam]
    x0 = np.ceil(np.minimum(np.minimum(px[0], px[1]), px[2])).clip(0, W); x1 = np.floor(np.maximum(np.maximum(px[0], px[1]), px[2])).clip(-1, W - 1)
    y0 = np.ceil(np.minimum(np.minimum(py[0], py[1]), py[2])).clip(0, H); y1 = np.floor(np.maximum(np.maximum(py[0], py[1]), py[2])).clip(-1, H - 1)
    keep &= (x1 >= x0) & (y1 >= y0)
    ti_all = np.nonzero(keep)[0]
    tf = np.full(W * H, np.inf); ta = np.full(W * H, np.inf)
    cnt_all = ((x1[ti_all] - x0[ti_all] + 1) * (y1[ti_all] - y0[ti_all] + 1)).astype(np.int64)
    cuts = np.searchsorted(np.cumsum(cnt_all), np.arange(300000, cnt_all.sum() + 300000, 300000))
    for ti in np.split(ti_all, np.unique(cuts[cuts < len(ti_all)])):       # about 0.3 M (triangle, pixel) pairs at a time: small memory
        if len(ti) == 0:
            continue
        nx = (x1[ti] - x0[ti] + 1).astype(np.int64); ny = (y1[ti] - y0[ti] + 1).astype(np.int64)
        cnt = nx * ny
        tp = np.repeat(ti, cnt)
        k = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
        nxr = np.repeat(nx, cnt)
        ix = np.repeat(x0[ti].astype(np.int64), cnt) + k % nxr
        iy = np.repeat(y0[ti].astype(np.int64), cnt) + k // nxr
        xn = (ix + 0.5) / W * 2 - 1; yn = 1 - (iy + 0.5) / H * 2
        d = fw[None, :] + rt[None, :] * (xn * tv * asp)[:, None] + up[None, :] * (yn * tv)[:, None]
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        A = sc.V[0][tp]; e1 = sc.V[1][tp] - A; e2 = sc.V[2][tp] - A
        h = np.cross(d, e2); a = (e1 * h).sum(1)
        good = np.abs(a) > 1e-12
        f = np.where(good, 1.0 / np.where(good, a, 1.0), 0.0)
        s_ = C0 - A; u = f * (s_ * h).sum(1)
        q = np.cross(s_, e1); v = f * (q * d).sum(1); t = f * (e2 * q).sum(1)
        hit = good & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 0.3)
        front = (sc.n[tp] * d).sum(1) < 0
        pix = iy * W + ix
        np.minimum.at(tf, pix[hit & front], t[hit & front])
        np.minimum.at(ta, pix[hit], t[hit])
    jj, ii = np.mgrid[0:H, 0:W]
    xn = (ii.ravel() + 0.5) / W * 2 - 1; yn = 1 - (jj.ravel() + 0.5) / H * 2
    D = fw[None, :] + rt[None, :] * (xn * tv * asp)[:, None] + up[None, :] * (yn * tv)[:, None]
    D /= np.linalg.norm(D, axis=1, keepdims=True)
    return tf.reshape(H, W), ta.reshape(H, W), D.reshape(H, W, 3)


def ray_water(r4, f, C0, D, tmax=150.0, dt=0.5):
    """for rays that hit no face: does the ray pass through water by the r4 SDF (sdf < -0.25 m, i.e. clearly inside)? (an opening through
    both sides of the water, which a double-sided render cannot close)"""
    if len(D) == 0:
        return np.zeros(0, bool)
    ts = np.arange(1.0, tmax, dt)
    out = np.zeros(len(D), bool)
    for i0 in range(0, len(D), 500):                  # in chunks (small memory: the machine also runs the hero simulation)
        Dc = D[i0:i0 + 500]
        Q = C0[None, None, :] + ts[None, :, None] * Dc[:, None, :]
        s = r4.sdf(f, Q.reshape(-1, 3)).reshape(len(Dc), len(ts))
        out[i0:i0 + 500] = np.nan_to_num(s, nan=9.0).min(1) < -0.25
    return out


def pixel_classes(sc, r4, f, C0, fw, rt, up, fov, W, H):
    tf, ta, D = raycast(sc, C0, fw, rt, up, fov, W, H)
    water_old = np.isfinite(tf)
    back_only = ~water_old & np.isfinite(ta)                     # the current render shows the background here; double-sided shows water
    back_front = water_old & (ta < tf - 1e-6)                    # a back face in front of a front face: double-sided changes the water seen
    none = ~np.isfinite(ta)
    upw = D[..., 1] > 0
    nw = np.zeros_like(none)
    idx = np.nonzero((none & binary_dilation(~none, iterations=6)).ravel())[0]       # only near water pixels (an opening is framed by water)
    if len(idx):
        nw.ravel()[idx] = ray_water(r4, f, C0, D.reshape(-1, 3)[idx])
    return dict(back_only=back_only, back_only_sky=back_only & upw, back_only_down=back_only & ~upw, back_front=back_front,
                none_through_water=nw, water_old=water_old)


def cams_for(first, last):
    """camera per record: seats from the existing seat captures (eye moves with the heave), print fixed. {name: (record->pos, fw, rt, up, fov)}"""
    cams = {}
    for L_ in SEATS:
        cdir = B3D + "/clip_DM1Ar_k4_r24_seat%s" % L_
        man = json.load(open(cdir + "/manifest.json", encoding="utf8"))
        rows = list(csv.DictReader(open(B3D + "/capture_DM1Ar_k4_r24_seat%s/seat/frames.csv" % L_, encoding="utf8")))
        pos = {}
        for r in rows:
            if float(r["blend"]) == 0.0:
                pos[int(r["sim_frame"])] = np.array([float(r["cx"]), float(r["cy"]), float(r["cz"])])
        base = np.array([man["seat_x"], man["still_offset_m"] + man["seat_eye_m"], man["seat_z"]])
        fw, rt, up = camera_basis(base, man["cam_seat_look_at"])
        cams["seat" + L_] = (pos, fw, rt, up, float(man["cam_seat_fov_v"]))
    man = json.load(open(B3D + "/clip_DM1Ar_k4_r24_seatA/manifest.json", encoding="utf8"))
    fw, rt, up = camera_basis(man["cam_print_pos"], man["cam_print_look_at"])
    pp = np.array(man["cam_print_pos"], float)
    cams["print"] = ({f: pp for f in range(first, last + 1)}, fw, rt, up, float(man["cam_print_fov_v"]))
    return cams, man


def origin(out):
    """where the see-through rays enter the water (--origin, after the main pass): for every back_only ray of the saved masks, the first
    point along the ray inside the water by the r4 SDF (sdf < 0, 0.25 m steps). 'seam' = it enters within 1 m of the symmetry plane
    (lateral |z| < 1: the record's cut at y = 0 does not meet its mirror there), else 'interior' (a hole of the free surface)."""
    W, H = 480, 270
    masks = np.load(out + "/pixel_masks_480x270.npz")
    cams, man = cams_for(1729, 2071)
    r4 = R4()
    ts = np.arange(0.5, 150.0, 0.25)
    res = {}
    for key in sorted(k for k in masks.files if k.endswith("_back_only")):
        cname, f = key.split("_")[0], int(key.split("_")[1])
        bo = np.unpackbits(masks[key])[:W * H].reshape(H, W).astype(bool)
        if not bo.any():
            continue
        posmap, fw, rt, up, fov = cams[cname]
        C0 = posmap[f]
        tv = np.tan(np.radians(fov) / 2)
        jj, ii = np.nonzero(bo)
        xn = (ii + 0.5) / W * 2 - 1; yn = 1 - (jj + 0.5) / H * 2
        D = fw[None, :] + rt[None, :] * (xn * tv * 16 / 9)[:, None] + up[None, :] * (yn * tv)[:, None]
        D /= np.linalg.norm(D, axis=1, keepdims=True)
        ent = np.full((len(D), 3), np.nan)
        for i0 in range(0, len(D), 200):
            Dc = D[i0:i0 + 200]
            Q = C0[None, None, :] + ts[None, :, None] * Dc[:, None, :]
            s = np.nan_to_num(r4.sdf(f, Q.reshape(-1, 3)).reshape(len(Dc), len(ts)), nan=9.0)
            inside = s < 0
            has = inside.any(1); k = inside.argmax(1)
            e = Q[np.arange(len(Dc)), k]
            e[~has] = np.nan
            ent[i0:i0 + 200] = e
        lat = np.abs(ent[:, 2])
        seam = lat < 1.0
        ok = np.isfinite(lat)
        r = res.setdefault(cname, dict(px=0, seam_px=0, interior_px=0, no_water_px=0, frames=[]))
        r["px"] += int(len(D)); r["seam_px"] += int((seam & ok).sum()); r["interior_px"] += int((~seam & ok).sum()); r["no_water_px"] += int((~ok).sum())
        r["frames"].append(dict(frame=f, px=int(len(D)), seam_px=int((seam & ok).sum()), interior_px=int((~seam & ok).sum()), no_water_px=int((~ok).sum()),
                                entry_median=[round(float(v), 1) for v in np.nanmedian(ent, 0)] if ok.any() else None))
    json.dump(dict(tool="Tools/GWWaveGen/flip50g2/f3d50_holes.py --origin", rule=origin.__doc__, cameras=res),
              open(out + "/see_through_origin.json", "w", encoding="utf8"), ensure_ascii=False, indent=0)
    for c, r in res.items():
        print(c, {k: v for k, v in r.items() if k != "frames"}, "frames with see-through", len(r["frames"]))


def main(a):
    if "--origin" in a:
        return origin(a[a.index("--out") + 1] if "--out" in a else B3D + "/holes_DM1Ar_k4_r24")
    first = int(a[a.index("--first") + 1]) if "--first" in a else 1729
    last = int(a[a.index("--last") + 1]) if "--last" in a else 2071
    amin = float(a[a.index("--amin") + 1]) if "--amin" in a else 0.1
    W, H = 480, 270
    out = a[a.index("--out") + 1] if "--out" in a else B3D + "/holes_DM1Ar_k4_r24"
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    bed = Bed(B3D + "/clip_DM1Ar_k4_r24_seatA")
    r4 = R4()
    cams, man = cams_for(first, last)
    win = (int(man["frame_first"]), int(man["frame_last"]))
    frows, hrows, masks = [], [], {}
    sign_bad = 0
    classes = ("domain", "seam-only", "bed", "bedlayer", "hole", "fragment")
    for f in range(first, last + 1):
        P, N, T, t = surf(f)
        g = np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]])
        sign_bad += int(((g * N[T].mean(1)).sum(1) > 0).sum())
        L, st = loops(P, N, T, bed)
        cls_n = {c: sum(1 for x in L if x["cls"] == c) for c in classes}
        cand = [x for x in L if x["cls"] in ("hole", "fragment") and x["area_m2"] >= amin]
        sd = r4.sdf(f, np.array([x["cen"] for x in cand]).reshape(-1, 3))
        for x, s_ in zip(cand, sd):
            hrows.append(dict(frame=f, t=round(t, 4), cls=x["cls"], seam=x["seam"], area_m2=round(x["area_m2"], 3), d_eq_m=round(x["d_eq_m"], 2),
                              perim_m=round(x["perim_m"], 2), extent_m=round(x["extent_m"], 2), edges=x["edges"],
                              x=round(x["cen"][0], 2), up=round(x["cen"][1], 2), lat=round(x["cen"][2], 2),
                              x_lo=round(x["lo"][0], 1), x_hi=round(x["hi"][0], 1), up_lo=round(x["lo"][1], 1), up_hi=round(x["hi"][1], 1),
                              lat_lo=round(x["lo"][2], 1), lat_hi=round(x["hi"][2], 1),
                              nx=round(x["n"][0], 2), nup=round(x["n"][1], 2), nlat=round(x["n"][2], 2), comp_tris=x["comp_tris"],
                              sdf_cen_m=None if not np.isfinite(s_) else round(float(s_), 2)))
        holes = [x for x in cand if x["cls"] == "hole"]
        row = dict(frame=f, t=round(t, 4), nv=len(P), nt=len(T), **st, **{"n_" + c.replace("-", "_"): n for c, n in cls_n.items()},
                   n_hole_ge_amin=len(holes), hole_area_m2=round(sum(x["area_m2"] for x in holes), 2),
                   max_hole_d_eq_m=round(max([x["d_eq_m"] for x in holes], default=0.0), 2),
                   n_fragment_ge_amin=len(cand) - len(holes), fragment_area_m2=round(sum(x["area_m2"] for x in cand if x["cls"] == "fragment"), 2))
        if win[0] <= f <= win[1]:
            sc = Scene(P, T)
            for cname, (posmap, fw, rt, up, fov) in cams.items():
                C0 = posmap.get(f)
                if C0 is None:
                    continue
                pc = pixel_classes(sc, r4, f, C0, fw, rt, up, fov, W, H)
                bo = pc["back_only"]
                row.update({"%s_back_only_px" % cname: int(bo.sum()), "%s_back_only_sky_px" % cname: int(pc["back_only_sky"].sum()),
                            "%s_back_only_down_px" % cname: int(pc["back_only_down"].sum()), "%s_back_front_px" % cname: int(pc["back_front"].sum()),
                            "%s_open_both_sides_px" % cname: int(pc["none_through_water"].sum())})
                if bo.any():
                    yy, xx = np.nonzero(bo)
                    row["%s_back_only_bbox" % cname] = "%d-%d,%d-%d" % (xx.min() * 4, xx.max() * 4 + 3, yy.min() * 4, yy.max() * 4 + 3)
                masks["%s_%05d_back_only" % (cname, f)] = np.packbits(bo)
                masks["%s_%05d_back_front" % (cname, f)] = np.packbits(pc["back_front"])
                masks["%s_%05d_open_both" % (cname, f)] = np.packbits(pc["none_through_water"])
        frows.append(row)
        if (f - first) % 25 == 0:
            print(f, cls_n, "holes>=amin", len(holes), {c: row.get("%s_back_only_px" % c) for c in cams}, "%.0f s" % (time.time() - t0), flush=True)
    keys = []
    for r in frows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(out + "/holes_per_record.csv", "w", newline="", encoding="utf8") as fo:
        w = csv.DictWriter(fo, keys); w.writeheader(); w.writerows(frows)
    np.savez_compressed(out + "/pixel_masks_480x270.npz", **masks)
    json.dump(dict(tool="Tools/GWWaveGen/flip50g2/f3d50_holes.py", run=RUN, records=[first, last], loop_window=list(win), amin_m2=amin,
                   pixel_grid=[W, H], pixel_grid_note="one ray per 4 x 4 block of the 1920 x 1080 frame (multiply counts by 16 for full-frame pixels)",
                   thresholds=dict(seam_m=SEAM_M, bed_m=BED_M, bedlayer_m=BEDLAYER_M, big_tris=BIG_TRIS),
                   winding_sign_mismatch_tris=sign_bad,
                   cameras={k: dict(fw=v[1].round(4).tolist(), fov_v=v[4]) for k, v in cams.items()}, loops=hrows),
              open(out + "/holes.json", "w", encoding="utf8"), ensure_ascii=False, indent=0, default=float)
    print("done", out, "records", len(frows), "loops >= amin", len(hrows), "winding mismatches", sign_bad, "%.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main(sys.argv[1:])
