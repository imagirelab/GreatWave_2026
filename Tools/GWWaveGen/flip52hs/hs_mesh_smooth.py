# -*- coding: utf-8 -*-
"""FLIP52HS hs_mesh_smooth: exporter-side smoothing test of the GW45SRF1 surface records (py -3.10 -B; numpy, scipy, PIL). 2026-10-18 written new (Claude).

Why (user 2026-10-18 ~16:35): the grid of the water surface is very visible in the video; if it is a precision problem, raise the precision
and show it again, keeping the big shape and the motion. This tool tests fix (B): smooth the EXISTING surface mesh of every record after
Houdini (no Houdini, no new simulation). The FLIP particles, the surface records and the judged runs are only READ. Smoothing is a
rendering / surfacing choice: it moves the drawn surface away from the particle surface by the amounts this tool measures and reports.

What it does per record (GW45SRF1, written by g52b_run.write_surface: positions uint16 over the bbox, oct normals, v half, triangles):
  topology     unique edges; boundary edges (used by one triangle); the symmetry seam = boundary vertices at lateral 0 (the mesh was clipped
               at y = 0 and Unity draws a mirrored copy); other boundary vertices (crop edges, holes, bed cut) are kept FIXED.
  Taubin       non-shrinking smoothing (Taubin 1995): per pair p += lam L(p), p += mu L(p), uniform (umbrella) Laplacian, lam 0.5,
               mu -0.53 (pass band k_pb = 1/lam + 1/mu = 0.113). Seam vertices use the MIRROR-SYMMETRIC one-ring (a non-seam neighbour
               counts twice, its mirror image has the same x / up) and keep lateral = 0, so no crease appears at the seam.
  normals      area-weighted vertex normals from the (smoothed) triangles, oriented like the stored Houdini normals; seam normals get
               lateral 0 (as write_surface does).
  normal-only  N3: positions unchanged (shape deviation 0), area-weighted normals then 3 passes of normal averaging over the one-ring.
  subdivision  S1 (optional): 1 level, red-green closure, in a crest box only (x_c - 25 .. x_c + 20 m, lateral <= 40 m, elevation >= 1 m):
               new edge vertices by the Loop edge rule (3/8, 3/8, 1/8, 1/8; boundary edges midpoint), then 1 Taubin pair on the refined mesh.
Variants (tags: 【選び】 chosen): orig (the record as is), N0 (normals recomputed), N3, T2, T5, T12 (Taubin pairs), T5S1 (T5 + crest subdivision),
  T2S1w (T2 + wide subdivision of the free surface x 180-320 m, lateral <= 60 m), T2S1wN2 (T2S1w + 2 normal averages).
Measurements (【測定】 on the records / outputs; 【計算】 derived):
  time per frame (smoothing + normals [+ subdivision]; write separately), vertex displacement |p' - p|, point-to-surface distance both ways
  (smoothed -> original and original -> smoothed, exact signed point-to-triangle), crest height change (centre-section crest eta_c and
  the 3D top of the crest region), the centre section (lateral 0.5 m, the r2 plane) as a 0.05 m water mask measured with the pv53 / D ruler
  (S52.measure_mask -> DS.pick -> g47_video.score3; the r2-record score3 of the same frame beside it), section Hausdorff / mean distance and
  mask symmetric difference, 0.5 m lattice share of the vertices (voxel-surfacing signature), stored normals vs the geometric normals,
  vertex-normal roughness (angle across edges), drawn normal vs the variant's own surface (shading-only change of N3 / N2),
  frame-to-frame consistency on 5 consecutive frames (geometric: second difference of the exact distances to the previous and next frame,
  regions crest / back face / front trough; image: second temporal difference of a numpy re-implementation of FLIP3DWater.shader in the
  print and seat views, fixed cameras), image grid energy (mean |Y - Gauss1.5px(Y)| on water pixels), the share of each record that is an
  under-water skin piece (connected pieces whose top is below -1 m; never seen through the opaque surface).
Renders are a NUMPY APPROXIMATION of the Unity view (FLIP3DWater.shader formula, FLIP3D_Water.mat colours, the batch sun, linear colour
space; no fog, flat sky): they compare variants with each other, they are not the Unity picture.
Writes only under Unity/Build/FLIP52B/hires/ (refuses other folders and never overwrites an existing record unless --force).
usage:
  py -3.10 -B hs_mesh_smooth.py test [--run <run_dir>] [--out <dir>] [--frames 2112,2149,1470] [--flicker 2147-2151] [--no-render]
  py -3.10 -B hs_mesh_smooth.py apply <run_dir> <out_surf_dir> --variant T5 [--from F] [--to F] [--force]   (batch for a later clip)
"""
import os, sys
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_k] = "2"
import json, math, time, struct, io, contextlib, glob

sys.dont_write_bytecode = True
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
HIRES = REPO + "/Unity/Build/FLIP52B/hires"
import numpy as np                       # noqa: E402
from scipy import sparse                 # noqa: E402
from scipy import ndimage as ndi         # noqa: E402
from scipy.spatial import cKDTree        # noqa: E402
from scipy.sparse.csgraph import connected_components   # noqa: E402
from PIL import Image, ImageDraw, ImageFont   # noqa: E402

TOOL = "Tools/GWWaveGen/flip52hs/hs_mesh_smooth.py"
RUN_DEF = REPO + "/Unity/Build/FLIP52B/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long"
CLIP_DEF = REPO + "/Unity/Build/FLIP3D/clip_DFGB2Er_f1153_3001_r24_seatA_ds"
OUT_DEF = HIRES + "/test_smooth"
LAM, MU = 0.5, -0.53
VARIANTS = {                                       # 【選び】
    "orig": dict(note="the record as written by Houdini (stored point normals)"),
    "N0": dict(normals_only=0, note="positions unchanged; area-weighted normals recomputed (no smoothing)"),
    "N3": dict(normals_only=3, note="positions unchanged; area-weighted normals + 3 one-ring normal averages"),
    "T2": dict(taubin=2, note="Taubin 2 pairs (lam 0.5, mu -0.53) + area-weighted normals"),
    "T5": dict(taubin=5, note="Taubin 5 pairs + area-weighted normals"),
    "T12": dict(taubin=12, note="Taubin 12 pairs + area-weighted normals"),
    "T5S1": dict(taubin=5, subdiv="crest", post=1, note="T5 + 1-level crest subdivision (Loop edge rule, red-green) + 1 Taubin pair + normals"),
    "T2S1w": dict(taubin=2, subdiv="wide", post=1, note="T2 + 1-level subdivision of the free surface in x 180-320 m, lateral <= 60 m (crest and seat A) + 1 Taubin pair + normals"),
    "T2S1wN2": dict(taubin=2, subdiv="wide", post=1, nsmooth=2, note="T2S1w + 2 one-ring normal averages on the refined mesh"),
}
CREST_BOX = dict(back=25.0, fwd=20.0, lat=40.0, emin=1.0)     # subdivision box around the section crest 【選び】
WIDE_BOX = dict(x0=180.0, x1=320.0, lat=60.0, emin=-3.0)      # wide subdivision box (crest + what seat A looks at) 【選び】
FLK_REG = {"crest": None, "back": (-40.0, -10.0, -2.0, 99.0), "front": (8.0, 40.0, -3.0, 2.0)}   # x rel. to crest, elevation range 【選び】
ZOOM = {"print_close": (240, 90, 640, 315), "seat": (120, 180, 520, 405)}                          # 2x crops of the 960x540 stills 【選び】
REG = dict(half_x=30.0, lat=30.0, emin=0.5)                     # crest region for the statistics 【選び】
LAT_SEC = 0.5                                                   # the r2 plane (lateral 0.5 m)
FINE = 0.05
LATTICE = dict(h=0.5, tol=0.0075)


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        o = float(o)
    if isinstance(o, float):
        return round(o, 6) if math.isfinite(o) else None
    return o


def low_priority():
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x00000040)       # IDLE_PRIORITY_CLASS ("Low")
        return "low (IDLE_PRIORITY_CLASS)"
    except Exception as e:
        return "not set: %r" % e


# ====================================================================== GW45SRF1 read / write (same layout as g52b_run.write_surface)
HEAD = struct.Struct("<8sIIdiIIffffffff")
HEAD_BYTES = 96


def oct_decode(n2):
    f = n2.astype(np.float64) / 65535.0 * 2.0 - 1.0
    x, y = f[:, 0], f[:, 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    t = np.clip(-z, 0, None)
    x = np.where(x >= 0, x - t, x + t); y = np.where(y >= 0, y - t, y + t)
    n = np.stack([x, y, z], 1)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def oct_encode(n):                                       # g52b_run.oct_encode, unchanged
    n = n / np.maximum(np.abs(n).sum(1, keepdims=True), 1e-12)
    x, y, z = n[:, 0], n[:, 1], n[:, 2]
    neg = z < 0
    xo = np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x)
    yo = np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y)
    return np.round((np.clip(np.stack([xo, yo], 1), -1, 1) * 0.5 + 0.5) * 65535).astype(np.uint16)


def read_srf(path):
    b = open(path, "rb").read()
    magic, ver, hb, t, fr, nv, nt, x0, y0, z0, x1, y1, z1, off, rsv = HEAD.unpack_from(b, 0)
    if magic != b"GW45SRF1":
        raise ValueError("not GW45SRF1: %s" % path)
    o = hb
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(nv, 3); o += nv * 6
    n2 = np.frombuffer(b, np.uint16, nv * 2, o).reshape(nv, 2); o += nv * 4
    v = np.frombuffer(b, np.float16, nv * 3, o).reshape(nv, 3); o += nv * 6
    tri = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3).astype(np.int64); o += nt * 12
    lo = np.array([x0, y0, z0], np.float64); hi = np.array([x1, y1, z1], np.float64)
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    return dict(t=float(t), frame=int(fr), off=float(off), rsv=float(rsv), P=P, N=oct_decode(n2), v=v.copy(), tri=tri, lo=lo, hi=hi,
                bytes=len(b), path=path)


def write_srf(path, d, P, N, v, tri, force=False):
    path = os.path.abspath(path).replace("\\", "/")
    if not path.startswith(HIRES + "/"):
        raise SystemExit("refused: outputs only under %s (got %s)" % (rel(HIRES), path))
    if os.path.exists(path) and not force:
        raise SystemExit("refused: %s exists (use --force for files this tool wrote)" % rel(path))
    seam = np.abs(P[:, 2]) < 1e-4
    N = N.copy(); N[seam, 2] = 0.0
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    lo = P.min(0); hi = P.max(0)
    q = np.round((P - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype(np.uint16)
    head = struct.pack("<8sIIdiIIffffffff", b"GW45SRF1", 1, HEAD_BYTES, float(d["t"]), int(d["frame"]), len(P), len(tri),
                       *[float(x) for x in lo], *[float(x) for x in hi], float(d["off"]), 0.0)
    head = head + b"\0" * (HEAD_BYTES - len(head))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(head); fh.write(q.tobytes()); fh.write(oct_encode(N).tobytes())
        fh.write(np.asarray(v, np.float16).tobytes()); fh.write(np.asarray(tri, np.uint32).tobytes())
    return path


def readback(path, P, tri):
    d = read_srf(path)
    ok_idx = bool(len(d["tri"]) == 0 or int(d["tri"].max()) < len(d["P"]))
    return dict(nv=len(d["P"]), nt=len(d["tri"]), bytes=d["bytes"], same_counts=bool(len(d["P"]) == len(P) and len(d["tri"]) == len(tri)),
                index_in_range=ok_idx, finite=bool(np.isfinite(d["P"]).all()),
                max_pos_err_m=float(np.abs(d["P"] - P).max()) if len(P) else 0.0,
                normal_unit_err=float(np.abs(np.linalg.norm(d["N"], axis=1) - 1).max()) if len(P) else 0.0,
                seam_max_lateral_m=float(np.abs(d["P"][np.abs(P[:, 2]) < 1e-4, 2]).max()) if (np.abs(P[:, 2]) < 1e-4).any() else None)


# ====================================================================== mesh topology and operators
def topo(P, tri):
    nv, nt = len(P), len(tri)
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    es = np.sort(e, 1)
    key = es[:, 0] * nv + es[:, 1]
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    E = np.stack([uk // nv, uk % nv], 1)
    te = inv.reshape(3, nt).T                                  # per triangle its unique edge ids (slots 01, 12, 20)
    bv = np.zeros(nv, bool); bv[E[cnt == 1].ravel()] = True
    A = sparse.coo_matrix((np.ones(2 * len(E)), (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(nv, nv)).tocsr()
    A.data[:] = 1.0
    seam = bv & (np.abs(P[:, 2]) < 1e-3)
    S = sparse.diags(seam.astype(float)); NS = sparse.diags((~seam).astype(float))
    Wm = (A + S @ A @ NS).tocsr()                              # seam rows: non-seam neighbours twice (their mirror images)
    deg = np.asarray(Wm.sum(1)).ravel()
    fixed = (bv & ~seam) | (deg == 0)
    return dict(E=E, cnt=cnt, te=te, bv=bv, seam=seam, fixed=fixed, Wm=Wm, deg=np.maximum(deg, 1.0), A=A,
                n_boundary_v=int(bv.sum()), n_seam_v=int(seam.sum()), n_fixed_v=int(fixed.sum()), n_nonmanifold_e=int((cnt > 2).sum()))


def taubin(P, T, pairs, lam=LAM, mu=MU):
    P = P.copy()
    mv = ~T["fixed"]
    for _ in range(int(pairs)):
        for c in (lam, mu):
            L = (T["Wm"] @ P) / T["deg"][:, None] - P
            L[~mv] = 0.0
            L[T["seam"], 2] = 0.0
            P += c * L
    P[T["seam"], 2] = 0.0
    return P


def orient_sign(P, tri, N):
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]])
    dots = (fn * (N[tri[:, 0]] + N[tri[:, 1]] + N[tri[:, 2]])).sum(1)
    s = 1.0 if dots.sum() >= 0 else -1.0
    return s, float(np.mean(np.sign(dots) == s))


def face_normals(P, tri, s):
    fn = np.cross(P[tri[:, 1]] - P[tri[:, 0]], P[tri[:, 2]] - P[tri[:, 0]]) * s
    return fn                                              # length = 2 x area


def awn(P, tri, s, seam):
    fn = face_normals(P, tri, s)
    N = np.zeros_like(P)
    idx = tri.ravel()
    for c in range(3):
        N[:, c] = np.bincount(idx, weights=np.repeat(fn[:, c], 3), minlength=len(P))
    N[seam, 2] = 0.0
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)


def smooth_normals(N, T, it):
    for _ in range(int(it)):
        N = N + (T["Wm"] @ N) / T["deg"][:, None]
        N[T["seam"], 2] = 0.0
        N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return N


def subdivide(P, V, tri, T, region):
    """1 level, red-green closure. region: bool per triangle. New edge vertices: Loop edge rule (interior), midpoint (boundary)."""
    te, E, cnt = T["te"], T["E"], T["cnt"]
    nE = len(E)
    marked = np.zeros(nE, bool)
    marked[te[region].ravel()] = True
    for _ in range(50):
        m = marked[te].sum(1)
        up = m == 2
        if not up.any():
            break
        marked[te[up].ravel()] = True
    opp = tri[:, [2, 0, 1]]                                  # vertex opposite to slot 01, 12, 20
    so = np.zeros((nE, 3))
    for c in range(3):
        so[:, c] = np.bincount(te.ravel(), weights=P[opp.ravel(), c], minlength=nE)
    a, b = P[E[:, 0]], P[E[:, 1]]
    loop = np.where((cnt == 2)[:, None], 0.375 * (a + b) + 0.125 * so, 0.5 * (a + b))
    ids = np.where(marked)[0]
    newid = -np.ones(nE, np.int64); newid[ids] = len(P) + np.arange(len(ids))
    P2 = np.vstack([P, loop[ids]])
    V2 = np.vstack([np.asarray(V, np.float32), (0.5 * (V[E[ids, 0]].astype(np.float32) + V[E[ids, 1]].astype(np.float32)))]).astype(np.float16)
    m = marked[te].sum(1)
    v0, v1, v2 = tri[:, 0], tri[:, 1], tri[:, 2]
    m01, m12, m20 = newid[te[:, 0]], newid[te[:, 1]], newid[te[:, 2]]
    out = [tri[m == 0]]
    r = m == 3
    out += [np.stack([v0[r], m01[r], m20[r]], 1), np.stack([v1[r], m12[r], m01[r]], 1), np.stack([v2[r], m20[r], m12[r]], 1),
            np.stack([m01[r], m12[r], m20[r]], 1)]
    g = m == 1
    for slot, (va, vb, vc, mm) in enumerate(((v0, v1, v2, m01), (v1, v2, v0, m12), (v2, v0, v1, m20))):
        s_ = g & marked[te[:, slot]]
        out += [np.stack([va[s_], mm[s_], vc[s_]], 1), np.stack([mm[s_], vb[s_], vc[s_]], 1)]
    tri2 = np.vstack(out).astype(np.int64)
    return P2, V2, tri2, dict(n_red=int(r.sum()), n_green=int(g.sum()), n_new_v=int(len(ids)))


# ====================================================================== the variants
def crest_x(P, tri, off, xr=(230.0, 300.0)):
    segs, _ = section_segments(P, tri, np.ones((len(tri), 3)))
    if not len(segs):
        return None
    pts = segs.reshape(-1, 2)
    sel = (pts[:, 0] >= xr[0]) & (pts[:, 0] <= xr[1])
    if not sel.any():
        return None
    k = np.argmax(np.where(sel, pts[:, 1], -1e9))
    return float(pts[k, 0]), float(pts[k, 1] - off)


def make_variant(name, d, T, s, xc, ec):
    spec = VARIANTS[name]
    P, N, V, tri = d["P"], d["N"], d["v"], d["tri"]
    info = {}
    t0 = time.perf_counter()
    if name == "orig":
        P2, N2, V2, tri2 = P, N, V, tri
    elif "normals_only" in spec:
        P2, V2, tri2 = P, V, tri
        N2 = smooth_normals(awn(P, tri, s, T["seam"]), T, spec["normals_only"])
    else:
        P2 = taubin(P, T, spec["taubin"])
        V2, tri2 = V, tri
        if spec.get("subdiv"):
            c = P2[tri].mean(1)
            if spec["subdiv"] == "wide":
                region = ((c[:, 0] >= WIDE_BOX["x0"]) & (c[:, 0] <= WIDE_BOX["x1"]) & (c[:, 2] <= WIDE_BOX["lat"])
                          & (c[:, 1] - d["off"] >= WIDE_BOX["emin"]))
            else:
                region = ((c[:, 0] >= xc - CREST_BOX["back"]) & (c[:, 0] <= xc + CREST_BOX["fwd"]) & (c[:, 2] <= CREST_BOX["lat"])
                          & (c[:, 1] - d["off"] >= CREST_BOX["emin"]))
            P2, V2, tri2, info = subdivide(P2, V, tri, T, region)
            info["region_tri"] = int(region.sum())
            T2 = topo(P2, tri2)
            P2 = taubin(P2, T2, spec.get("post", 1))
            N2 = awn(P2, tri2, s, T2["seam"])
            if spec.get("nsmooth"):
                N2 = smooth_normals(N2, T2, spec["nsmooth"])
        else:
            N2 = awn(P2, tri, s, T["seam"])
            if spec.get("nsmooth"):
                N2 = smooth_normals(N2, T, spec["nsmooth"])
    info["t_smooth_s"] = time.perf_counter() - t0
    return P2, N2, V2, tri2, info


# ====================================================================== measurements
def crest_region(P, xc, off):
    return (np.abs(P[:, 0] - xc) <= REG["half_x"]) & (P[:, 2] <= REG["lat"]) & (P[:, 1] - off >= REG["emin"])


class SurfRef:
    """exact signed point-to-triangle distance to a mesh (candidates: the K nearest triangle centroids; sign by the oriented face normal)."""
    K = 12

    def __init__(self, P, tri, s):
        self.P, self.tri = P, tri
        self.fn = face_normals(P, tri, s)
        self.tree = cKDTree(P[tri].mean(1))

    def dist(self, Q, chunk=40000):
        out = np.empty(len(Q))
        for i0 in range(0, len(Q), chunk):
            q = Q[i0:i0 + chunk]
            _, ii = self.tree.query(q, k=self.K)
            qq = np.repeat(q, self.K, 0); tt = ii.ravel()
            a, b, c = self.P[self.tri[tt, 0]], self.P[self.tri[tt, 1]], self.P[self.tri[tt, 2]]
            cp = closest_on_tri(qq, a, b, c)
            dv = qq - cp
            dd = np.linalg.norm(dv, axis=1).reshape(-1, self.K)
            k = np.argmin(dd, 1)
            sel = np.arange(len(q)) * self.K + k
            sg = np.sign((dv[sel] * self.fn[tt[sel]]).sum(1))
            out[i0:i0 + chunk] = dd[np.arange(len(q)), k] * np.where(sg == 0, 1.0, sg)
        return out


def closest_on_tri(p, a, b, c):
    """closest point on triangle abc to p (Ericson, Real-Time Collision Detection 5.1.5), vectorized."""
    ab, ac, ap = b - a, c - a, p - a
    dot = lambda u, v: (u * v).sum(1)
    d1, d2 = dot(ab, ap), dot(ac, ap)
    bp = p - b; d3, d4 = dot(ab, bp), dot(ac, bp)
    cp = p - c; d5, d6 = dot(ab, cp), dot(ac, cp)
    vc = d1 * d4 - d3 * d2; vb = d5 * d2 - d1 * d6; va = d3 * d6 - d5 * d4
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-300, 1e-300, den)
    out = a + ab * (vb / den)[:, None] + ac * (vc / den)[:, None]
    done = np.zeros(len(p), bool)

    def put(m, val):
        m = m & ~done
        out[m] = val[m]
        done[m] = True
    with np.errstate(divide="ignore", invalid="ignore"):
        put((d1 <= 0) & (d2 <= 0), a)
        put((d3 >= 0) & (d4 <= d3), b)
        put((vc <= 0) & (d1 >= 0) & (d3 <= 0), a + ab * np.nan_to_num(d1 / (d1 - d3))[:, None])
        put((d6 >= 0) & (d5 <= d6), c)
        put((vb <= 0) & (d2 >= 0) & (d6 <= 0), a + ac * np.nan_to_num(d2 / (d2 - d6))[:, None])
        put((va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0), b + (c - b) * np.nan_to_num((d4 - d3) / ((d4 - d3) + (d5 - d6)))[:, None])
    return out


def bad_normals(N_stored, N_geo, sel):
    ang = np.degrees(np.arccos(np.clip((N_stored * N_geo).sum(1), -1, 1)))[sel]
    if not len(ang):
        return None
    return dict(n=int(len(ang)), n_over30=int((ang > 30).sum()), n_over60=int((ang > 60).sum()), share_over30=float((ang > 30).mean()),
                median_deg=float(np.median(ang)), p99_deg=float(np.percentile(ang, 99)), max_deg=float(ang.max()))


def flk_region(P, xc, off, name):
    if FLK_REG[name] is None:
        return crest_region(P, xc, off)
    a, b, e0, e1 = FLK_REG[name]
    e = P[:, 1] - off
    return (P[:, 0] >= xc + a) & (P[:, 0] <= xc + b) & (P[:, 2] <= REG["lat"]) & (e >= e0) & (e <= e1)


def stats(a):
    a = np.asarray(a, float)
    if not len(a):
        return None
    b = np.abs(a)
    return dict(max=float(b.max()), mean=float(b.mean()), p99=float(np.percentile(b, 99)), mean_signed=float(a.mean()), n=int(len(a)))


def lattice_stats(P, h=LATTICE["h"], tol=LATTICE["tol"]):
    on = np.zeros((len(P), 3), bool)
    o = {}
    for a, nm in enumerate(("x", "up", "lateral")):
        ph = np.mod(P[:, a], h)
        hist, _ = np.histogram(ph, bins=100, range=(0.0, h))
        m = (np.argmax(hist) + 0.5) * h / 100.0
        dd = np.abs(np.mod(ph - m + 0.5 * h, h) - 0.5 * h)
        on[:, a] = dd <= tol
        o[nm] = dict(mode_phase_m=m, share_on=float(on[:, a].mean()))
    o["share_2plus_axes_on"] = float((on.sum(1) >= 2).mean())
    o["random_expect_per_axis"] = 2 * tol / h
    o["random_expect_2plus"] = float(3 * (2 * tol / h) ** 2 - 2 * (2 * tol / h) ** 3)
    return o


def normal_rough(P, N, E, sel_v):
    e = E[sel_v[E[:, 0]] & sel_v[E[:, 1]]]
    if not len(e):
        return None
    ang = np.degrees(np.arccos(np.clip((N[e[:, 0]] * N[e[:, 1]]).sum(1), -1, 1)))
    L = np.linalg.norm(P[e[:, 0]] - P[e[:, 1]], axis=1)
    return dict(edge_angle_deg_median=float(np.median(ang)), edge_angle_deg_p90=float(np.percentile(ang, 90)),
                edge_angle_deg_p99=float(np.percentile(ang, 99)), deg_per_m_median=float(np.median(ang / np.maximum(L, 1e-6))),
                edge_len_m_median=float(np.median(L)), edge_len_m_p10=float(np.percentile(L, 10)), edge_len_m_p90=float(np.percentile(L, 90)),
                n_edges=int(len(e)))


def section_segments(P, tri, fn, s0=LAT_SEC):
    """triangles cut by the plane lateral = s0 -> segments (m, 2, 2) in (x, up) and the face normals of those triangles."""
    l = P[:, 2] - s0
    l = np.where(np.abs(l) < 1e-7, 1e-7, l)
    sg = l[tri] > 0
    cut = sg.any(1) & ~sg.all(1)
    t = tri[cut]; sgc = sg[cut]
    pts = np.zeros((len(t), 3, 2)); fl = np.zeros((len(t), 3), bool)
    for k, (i, j) in enumerate(((0, 1), (1, 2), (2, 0))):
        a, b = t[:, i], t[:, j]
        fl[:, k] = sgc[:, i] != sgc[:, j]
        den = l[a] - l[b]
        w = l[a] / np.where(fl[:, k], den, 1.0)
        q = P[a] + w[:, None] * (P[b] - P[a])
        pts[:, k] = q[:, :2]
    order = np.argsort(~fl, axis=1, kind="stable")[:, :2]
    seg = np.take_along_axis(pts, order[:, :, None], axis=1)
    return seg, fn[cut]


def section_mask(seg, fns, X, Z, off, bed_raw, margin):
    """0.05 m water mask of the centre section. Column fill from below (water), the state above a crossing is set by the crossing's
    normal: up-facing -> air, down-facing -> water. Bed filled as in g46 r2_mask."""
    x0, e0 = seg[:, 0, 0], seg[:, 0, 1] - off
    x1, e1 = seg[:, 1, 0], seg[:, 1, 1] - off
    nup = fns[:, 1]
    xa = np.minimum(x0, x1); xb = np.maximum(x0, x1)
    ok = (xb - xa) > 1e-9
    dx = X[1] - X[0]
    i0 = np.ceil((xa - X[0]) / dx).astype(np.int64); i1 = np.ceil((xb - X[0]) / dx).astype(np.int64) - 1
    i0 = np.clip(i0, 0, len(X)); i1 = np.clip(i1, -1, len(X) - 1)
    n = np.where(ok, i1 - i0 + 1, 0); n = np.maximum(n, 0)
    rep = np.repeat(np.arange(len(seg)), n)
    k = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    col = i0[rep] + k
    w = (X[col] - x0[rep]) / (x1[rep] - x0[rep])
    zc = e0[rep] + w * (e1[rep] - e0[rep])
    air = nup[rep] > 0
    o = np.lexsort((zc, col))
    col, zc, air = col[o], zc[o], air[o]
    M = np.ones((len(Z), len(X)), bool)
    dz = Z[1] - Z[0]
    r = np.clip(np.ceil((zc - Z[0]) / dz).astype(np.int64), 0, len(Z))
    nxt = np.r_[r[1:], len(Z)]
    last = np.r_[col[1:] != col[:-1], True]
    nxt = np.where(last, len(Z), nxt)
    for c_, a_, b_, s_ in zip(col, r, nxt, air):
        if b_ > a_:
            M[a_:b_, c_] = not s_
    has = np.zeros(len(X), bool); has[col] = True
    M[:, ~has] = False                                         # no crossing: hole or outside the mesh -> air (reported)
    M |= (Z[:, None] + off) < (bed_raw[None, :] + margin)
    return M, int((~has).sum())


class Ruler:
    """pv53's D ruler (read only imports): Ctx49 of the run for off / Lc / bed; r2_mask for the r2-record reference."""
    def __init__(self, rd):
        sys.path.insert(0, TOOLS + "/flip53")
        import pv53 as PV                                      # noqa: E402  (read only)
        self.PV = PV
        with contextlib.redirect_stdout(io.StringIO()):
            self.cx = PV.PA.Ctx49(rd, {})
        self.off = float(self.cx.off); self.Lc = float(self.cx.Lc); self.margin = float(self.cx.margin)
        S, m, t = self.cx.R2.get(min(self.cx.R2.frames))
        self.xs0 = float(m["x0"]); self.xs1 = float(m["x0"]) + float(m["dx"]) * (S.shape[1] - 1)
        self.zs0 = float(m["y0"]) - self.off

    def row(self, M, X, Z):
        PV = self.PV
        mm = PV.A46.S52.measure_mask(M, X, Z, flip_extra=dict(Lc=self.Lc))
        row = PV.A46.DS.pick(mm)
        s3, parts = PV.GV.score3(row)
        g = lambda k: (float(row[k]) if isinstance(row.get(k), (int, float)) and not isinstance(row.get(k), bool) and math.isfinite(float(row[k])) else None)
        return dict(score3=s3, parts=parts, chord=g("face_chord_deg_01_05"), foot=g("front_x01_rel"), hood=g("hood_area"),
                    hollow=g("hood_wall_x_rel"), lip=g("lip_thick_mid"), gap=g("gap_max"), back=g("back_angle_07_09_deg"),
                    w07=g("width07_silhouette"), eta_c=g("eta_c"), x_c=g("x_c"))

    def r2(self, f, xg):
        PV = self.PV
        try:
            M, X, Z, t = PV.A46.r2_mask(self.cx, f, xg)
            return self.row(M, X, Z)
        except Exception as ex:
            return dict(error=repr(ex)[:200])

    def grid(self, xg, top):
        X = np.arange(max(xg - 60.0, self.xs0), min(xg + 60.0, self.xs1), FINE)
        Z = np.arange(max(-12.0, self.zs0), top + 1.5, FINE)
        return X, Z

    def mesh(self, P, tri, s, xg, X, Z):
        fs = free_surface_tris(P, tri, self.off)
        seg, fns = section_segments(P, tri[fs], face_normals(P, tri[fs], s))
        M, nempty = section_mask(seg, fns, X, Z, self.off, self.cx.bed_z(X, LAT_SEC), self.margin)
        M = self.PV.A46.DS.keep_bottom(M)
        try:
            r = self.row(M, X, Z)
        except Exception as ex:
            r = dict(error=repr(ex)[:200])
        r["empty_columns"] = nempty
        pts = seg.reshape(-1, 2)
        sel = np.abs(pts[:, 0] - xg) <= 0.5 * self.Lc
        r["section_top_m"] = float(pts[sel, 1].max() - self.off) if sel.any() else None
        return r, M, seg


FREE_EMAX = -1.0      # a connected piece of the record whose highest point is below this elevation is not the free surface 【選び】


def components(P, tri):
    nv = len(P)
    A = sparse.coo_matrix((np.ones(3 * len(tri)), (tri[:, [0, 1, 2]].ravel(), tri[:, [1, 2, 0]].ravel())), shape=(nv, nv))
    n, lab = connected_components(A, directed=False)
    return n, lab


def free_surface_tris(P, tri, off):
    """triangles of the connected pieces that reach above FREE_EMAX (the records also hold an under-water skin at -15 .. -3 m, a separate
    piece with up-facing normals near the bed; it is never seen through the opaque surface but would break the section fill)."""
    n, lab = components(P, tri)
    cmax = np.full(n, -1e9); np.maximum.at(cmax, lab, P[:, 1] - off)
    return cmax[lab[tri[:, 0]]] >= FREE_EMAX


def deep_share(P, tri, off):
    fs = free_surface_tris(P, tri, off)
    used = np.zeros(len(P), bool); used[tri[fs].ravel()] = True
    return dict(deep_tri_share=float(1 - fs.mean()), deep_vert_share=float(1 - used.mean()), n_free_tri=int(fs.sum()), n_free_vert=int(used.sum()))


def seg_points(seg, xg, off, half=30.0, emin=-2.0):
    mid = seg.mean(1)
    pts = np.vstack([seg[:, 0], seg[:, 1], mid])
    sel = (np.abs(pts[:, 0] - xg) <= half) & (pts[:, 1] - off >= emin)
    return pts[sel]


def sec_compare(sa, sb):
    if not len(sa) or not len(sb):
        return None
    da, _ = cKDTree(sb).query(sa); db, _ = cKDTree(sa).query(sb)
    return dict(hausdorff_m=float(max(da.max(), db.max())), mean_m=float(0.5 * (da.mean() + db.mean())),
                p95_m=float(np.percentile(np.r_[da, db], 95)))


# ====================================================================== numpy approximation of FLIP3DWater.shader
def srgb2lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin2srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)


MAT = dict(Deep=srgb2lin([0.012, 0.07, 0.1]), Lit=srgb2lin([0.11, 0.42, 0.45]), Hor=srgb2lin([0.5, 0.6, 0.68]), Top=srgb2lin([0.26, 0.4, 0.58]),
           F0=0.02, Wrap=0.0, SunPower=600.0, SunScale=3.0, LightC=srgb2lin([1.0, 0.96, 0.90]) * 1.15,
           L=-np.array([-0.55, -0.62, 0.45]) / np.linalg.norm([-0.55, -0.62, 0.45]))   # FLIP3D_Water.mat (repo) + FLIP3DBatch sun


def render(P, N, tri, s, cam, W, H, near=1.0, chunk=1_500_000):
    pos = np.asarray(cam["pos"], float); look = np.asarray(cam["look"], float)
    Mz = np.array([1.0, 1.0, -1.0])
    nv = len(P)
    PP = np.vstack([P, P * Mz]); NN = np.vstack([N, N * Mz])
    TT = np.vstack([tri, tri + nv])
    fnf = face_normals(P, tri, s)
    FN = np.vstack([fnf, fnf * Mz])                            # mirrored copy: outward normal mirrored
    f = look - pos; f /= np.linalg.norm(f)
    r = np.cross([0.0, 1.0, 0.0], f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    tv = math.tan(math.radians(cam["fov"]) / 2); asp = W / H
    d = PP - pos
    zc = d @ f
    with np.errstate(divide="ignore", invalid="ignore"):
        px = ((d @ r) / (zc * tv * asp) * 0.5 + 0.5) * W
        py = (0.5 - (d @ u) / (zc * tv) * 0.5) * H
    Z3 = zc[TT]; X3 = px[TT]; Y3 = py[TT]
    valid = Z3.min(1) > near
    xmn = np.ceil(np.nan_to_num(X3.min(1)) - 0.5); xmx = np.floor(np.nan_to_num(X3.max(1)) - 0.5)
    ymn = np.ceil(np.nan_to_num(Y3.min(1)) - 0.5); ymx = np.floor(np.nan_to_num(Y3.max(1)) - 0.5)
    xmn = np.clip(xmn, 0, W - 1); xmx = np.clip(xmx, -1, W - 1); ymn = np.clip(ymn, 0, H - 1); ymx = np.clip(ymx, -1, H - 1)
    area = (X3[:, 1] - X3[:, 0]) * (Y3[:, 2] - Y3[:, 0]) - (Y3[:, 1] - Y3[:, 0]) * (X3[:, 2] - X3[:, 0])
    valid &= (xmx >= xmn) & (ymx >= ymn) & (np.abs(area) > 1e-9) & np.isfinite(area)
    ti = np.where(valid)[0]
    w_ = (xmx[ti] - xmn[ti] + 1).astype(np.int64); h_ = (ymx[ti] - ymn[ti] + 1).astype(np.int64)
    sz = w_ * h_
    zbuf = np.full(W * H, np.inf); tbuf = np.full(W * H, -1, np.int64)
    b0b = np.zeros(W * H, np.float32); b1b = np.zeros(W * H, np.float32)
    cs = np.cumsum(sz)
    start = 0
    while start < len(ti):
        stop = int(np.searchsorted(cs, (cs[start - 1] if start else 0) + chunk, "right"))
        stop = max(stop, start + 1)
        sl = slice(start, stop)
        t_ = ti[sl]; ww = w_[sl]; nn = sz[sl]
        rep = np.repeat(np.arange(len(t_)), nn)
        k = np.arange(nn.sum()) - np.repeat(np.cumsum(nn) - nn, nn)
        tt = t_[rep]
        cx_ = xmn[tt] + (k % ww[rep]) + 0.5; cy_ = ymn[tt] + (k // ww[rep]) + 0.5
        ax, ay, bx, by, qx, qy = X3[tt, 0], Y3[tt, 0], X3[tt, 1], Y3[tt, 1], X3[tt, 2], Y3[tt, 2]
        ar = area[tt]
        w0 = ((bx - cx_) * (qy - cy_) - (by - cy_) * (qx - cx_)) / ar
        w1 = ((qx - cx_) * (ay - cy_) - (qy - cy_) * (ax - cx_)) / ar
        w2 = 1.0 - w0 - w1
        ins = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
        tt, w0, w1, w2, cx_, cy_ = tt[ins], w0[ins], w1[ins], w2[ins], cx_[ins], cy_[ins]
        l0 = w0 / Z3[tt, 0]; l1 = w1 / Z3[tt, 1]; l2 = w2 / Z3[tt, 2]
        S_ = l0 + l1 + l2
        dep = 1.0 / S_
        pid = (cy_ - 0.5).astype(np.int64) * W + (cx_ - 0.5).astype(np.int64)
        o = np.lexsort((dep, pid))
        ps = pid[o]
        first = np.r_[True, ps[1:] != ps[:-1]]
        sel = o[first]
        p_ = pid[sel]
        better = dep[sel] < zbuf[p_]
        sel = sel[better]; p_ = p_[better]
        zbuf[p_] = dep[sel]; tbuf[p_] = tt[sel]
        b0b[p_] = (l0[sel] / S_[sel]).astype(np.float32); b1b[p_] = (l1[sel] / S_[sel]).astype(np.float32)
        start = stop
    hit = tbuf >= 0
    img = np.zeros((W * H, 3))
    # sky (flat approximation of the procedural sky) for every pixel, then water
    jj, ii = np.divmod(np.arange(W * H), W)
    dirs = (f[None, :] + ((ii + 0.5) / W * 2 - 1)[:, None] * tv * asp * r[None, :] + (1 - (jj + 0.5) / H * 2)[:, None] * tv * u[None, :])
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    sk = MAT["Hor"][None, :] + (MAT["Top"] - MAT["Hor"])[None, :] * np.clip(dirs[:, 1:2] * 1.5, 0, 1)
    img[:] = sk
    t = tbuf[hit]
    b0 = b0b[hit].astype(float); b1 = b1b[hit].astype(float); b2 = 1.0 - b0 - b1
    n = b0[:, None] * NN[TT[t, 0]] + b1[:, None] * NN[TT[t, 1]] + b2[:, None] * NN[TT[t, 2]]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    wp = b0[:, None] * PP[TT[t, 0]] + b1[:, None] * PP[TT[t, 1]] + b2[:, None] * PP[TT[t, 2]]
    v = pos[None, :] - wp; v /= np.linalg.norm(v, axis=1, keepdims=True)
    front = (FN[t] * v).sum(1) > 0
    n = np.where(front[:, None], n, -n)                        # GW_WATER_DOUBLE_SIDED: back faces with the flipped normal
    ndv = np.clip((n * v).sum(1), 0, 1)
    fres = MAT["F0"] + (1 - MAT["F0"]) * (1 - ndv) ** 5
    rr = -v + 2 * (n * v).sum(1)[:, None] * n
    sky = MAT["Hor"][None, :] + (MAT["Top"] - MAT["Hor"])[None, :] * np.clip(rr[:, 1:2] * 1.5, 0, 1)
    sky = sky + (MAT["Lit"][None, :] - sky) * np.clip(-rr[:, 1:2] * 3.0, 0, 1)
    Ld = MAT["L"]
    ndl = np.clip(((n @ Ld) + MAT["Wrap"]) / (1 + MAT["Wrap"]), 0, 1)
    body = (MAT["Deep"][None, :] + (MAT["Lit"] - MAT["Deep"])[None, :] * ndl[:, None]) * MAT["LightC"][None, :]
    hv = Ld[None, :] + v; hv /= np.linalg.norm(hv, axis=1, keepdims=True)
    spec = np.clip((n * hv).sum(1), 0, 1) ** MAT["SunPower"] * MAT["SunScale"]
    col = body + (sky - body) * fres[:, None] + spec[:, None] * MAT["LightC"][None, :]
    img[hit] = col
    out = (lin2srgb(img) * 255 + 0.5).astype(np.uint8).reshape(H, W, 3)
    return out, hit.reshape(H, W)


def luma(img):
    a = img.astype(float) / 255.0
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def grid_energy(img, mask):
    Y = luma(img)
    hp = np.abs(Y - ndi.gaussian_filter(Y, 1.5))
    m = ndi.binary_erosion(mask, iterations=3)
    return float(hp[m].mean()) if m.any() else None


def font(sz):
    for p in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/meiryo.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except Exception:
            pass
    return ImageFont.load_default()


def tiles(imgs, labels, cols, path, title):
    h, w = imgs[0].shape[:2]
    rows = (len(imgs) + cols - 1) // cols
    top = 44
    can = Image.new("RGB", (cols * w, rows * (h + 30) + top), (245, 245, 242))
    dr = ImageDraw.Draw(can)
    dr.text((10, 10), title, fill=(20, 20, 20), font=font(20))
    for k, (im, lb) in enumerate(zip(imgs, labels)):
        x0 = (k % cols) * w; y0 = top + (k // cols) * (h + 30)
        can.paste(Image.fromarray(im), (x0, y0 + 30))
        dr.text((x0 + 8, y0 + 5), lb, fill=(20, 20, 20), font=font(16))
    can.save(path)
    return path


def section_plot(secs, xg, off, path, title):
    """centre-section curves (lateral 0.5 m) of the variants, crest window, 40 px/m, one panel per variant over orig."""
    x0, x1, e0, e1, s = xg - 30.0, xg + 20.0, -3.0, 9.0, 32.0
    W = int((x1 - x0) * s); Hh = int((e1 - e0) * s)
    names = [k for k in secs if k != "orig"]
    can = Image.new("RGB", (W, len(names) * (Hh + 26) + 40), (255, 255, 255))
    dr = ImageDraw.Draw(can)
    dr.text((8, 8), title, fill=(0, 0, 0), font=font(18))
    for k, nm in enumerate(names):
        oy = 40 + k * (Hh + 26)
        dr.text((8, oy), "%s (blue) over orig (grey). 1 m grid, x %.0f..%.0f m, elevation %.0f..%.0f m" % (nm, x0, x1, e0, e1), fill=(0, 0, 0), font=font(14))
        oy += 20
        for gx in range(int(math.ceil(x0)), int(x1) + 1):
            dr.line([((gx - x0) * s, oy), ((gx - x0) * s, oy + Hh)], fill=(236, 236, 236))
        for ge in range(int(e0), int(e1) + 1):
            dr.line([(0, oy + (e1 - ge) * s), (W, oy + (e1 - ge) * s)], fill=(200, 200, 200) if ge == 0 else (236, 236, 236))
        for name_, colr, wd in (("orig", (150, 150, 150), 3), (nm, (20, 60, 200), 1)):
            for a, b in secs[name_]:
                if max(a[0], b[0]) < x0 or min(a[0], b[0]) > x1:
                    continue
                dr.line([((a[0] - x0) * s, oy + (e1 - (a[1] - off)) * s), ((b[0] - x0) * s, oy + (e1 - (b[1] - off)) * s)], fill=colr, width=wd)
    can.save(path)
    return path


# ====================================================================== test
def opt(a, k, d=None):
    return a[a.index(k) + 1] if k in a else d


def cams_from_clip(f):
    m = json.load(open(CLIP_DEF + "/manifest.json", encoding="utf-8"))
    i = int(f) - int(m["frame_first"])
    hv = m["heave"][i] if 0 <= i < len(m["heave"]) else 0.0
    pr = dict(pos=m["cam_print_pos"], look=m["cam_print_look_at"], fov=float(m["cam_print_fov_v"]))
    close = dict(pos=m["cam_print_pos"], look=[m["cam_print_look_at"][0], m["cam_print_look_at"][1] - 1.0, 0.0], fov=9.0)
    seat = dict(pos=[m["seat_x"], m["seat_eye_m"] + hv, m["seat_z"]], look=m["cam_seat_look_at"], fov=float(m["cam_seat_fov_v"]))
    return dict(print=pr, print_close=close, seat=seat), dict(src=rel(CLIP_DEF + "/manifest.json"), heave_m=hv)


def main_test(a):
    T0 = time.time()
    prio = low_priority()
    rd = opt(a, "--run", RUN_DEF).replace("\\", "/").rstrip("/")
    od = opt(a, "--out", OUT_DEF).replace("\\", "/").rstrip("/")
    if not os.path.abspath(od).replace("\\", "/").startswith(HIRES):
        raise SystemExit("refused: --out must be under %s" % rel(HIRES))
    frames = [int(x) for x in opt(a, "--frames", "2112,2149,1470").split(",")]
    fa, fb = [int(x) for x in opt(a, "--flicker", "2147-2151").split("-")]
    fl = list(range(fa, fb + 1))
    still_f = 2149 if 2149 in frames else frames[0]
    force = "--force" in a
    do_render = "--no-render" not in a
    os.makedirs(od, exist_ok=True)
    print("priority:", prio, "| run", rel(rd), "| out", rel(od))
    R = Ruler(rd)
    print("ruler ready (off %.4f, Lc %.1f, margin %.2f) %.1f s" % (R.off, R.Lc, R.margin, time.time() - T0))
    rep = dict(tool=TOOL, created=time.strftime("%Y-%m-%d %H:%M:%S"), run=rel(rd), out=rel(od), priority=prio, threads=os.environ["OMP_NUM_THREADS"],
               variants={k: v["note"] for k, v in VARIANTS.items()}, lam=LAM, mu=MU, crest_box=CREST_BOX, wide_box=WIDE_BOX, stats_region=REG,
               flicker_regions=FLK_REG, section_lateral_m=LAT_SEC, free_surface_rule="connected pieces reaching elevation >= %.1f m" % FREE_EMAX,
               distance_rule="exact signed point-to-triangle distance (nearest of the %d triangles with the nearest centroids; sign by the outward face normal)" % SurfRef.K,
               tags="record numbers 【測定】; derived 【計算】; variants / boxes / regions / close-up camera 【選び】; renders = numpy approximation of the shader",
               frames={}, flicker={}, render={})
    keep = {}
    for f in sorted(set(frames) | set(fl)):
        src = "%s/surf/s_%05d.gw45s" % (rd, f)
        d = read_srf(src)
        T = topo(d["P"], d["tri"])
        s, s_agree = orient_sign(d["P"], d["tri"], d["N"])
        xe = crest_x(d["P"], d["tri"], d["off"])
        xc, ec = xe if xe else (265.0, 6.0)
        main = f in frames
        fr = dict(src=rel(src), t=d["t"], nv=len(d["P"]), nt=len(d["tri"]), bytes=d["bytes"], quant_half_step_m=float((d["hi"] - d["lo"]).max() / 65535 / 2),
                  orient_sign=s, orient_agree=s_agree, topo={k: T[k] for k in ("n_boundary_v", "n_seam_v", "n_fixed_v", "n_nonmanifold_e")},
                  section_crest_x=xc, section_crest_e=ec, off=d["off"], variants={})
        reg0 = crest_region(d["P"], xc, d["off"])
        fs0 = free_surface_tris(d["P"], d["tri"], d["off"])
        free_v = np.zeros(len(d["P"]), bool); free_v[d["tri"][fs0].ravel()] = True
        fr["lattice_free"] = lattice_stats(d["P"][free_v]); fr["lattice_crest"] = lattice_stats(d["P"][reg0])
        fr["pieces"] = deep_share(d["P"], d["tri"], d["off"])
        Ngeo = awn(d["P"], d["tri"], s, T["seam"])
        fr["stored_vs_geometric_normals_free"] = bad_normals(d["N"], Ngeo, free_v)
        fr["stored_vs_geometric_normals_crest"] = bad_normals(d["N"], Ngeo, reg0)
        if main:
            ref0 = SurfRef(d["P"], d["tri"], s)
            X, Z = R.grid(xc, ec + d["off"] + 2.0)
            fr["r2_record"] = R.r2(f, xc)
            secs = {}
        for name in VARIANTS:
            P2, N2, V2, tri2, info = make_variant(name, d, T, s, xc, ec)
            vr = dict(info=info, nv=len(P2), nt=len(tri2))
            if name != "orig":
                t1 = time.perf_counter()
                outp = write_srf("%s/%s/s_%05d.gw45s" % (od, name, f), d, P2, N2, V2, tri2, force=force)
                vr["t_write_s"] = time.perf_counter() - t1
                vr["file"] = rel(outp)
                vr["readback"] = readback(outp, P2, tri2)
            reg = crest_region(P2, xc, d["off"])
            Tn = topo(P2, tri2) if len(tri2) != len(d["tri"]) else T
            vr["normal_rough_crest"] = normal_rough(P2, N2, Tn["E"], reg)
            vr["shading_vs_geometry_crest"] = bad_normals(N2, awn(P2, tri2, s, Tn["seam"]), reg)   # angle drawn normal vs the variant's own surface
            if reg.any():
                k = np.argmax(np.where(reg, P2[:, 1], -1e9))
                vr["top3d_crest"] = dict(e=float(P2[k, 1] - d["off"]), x=float(P2[k, 0]), lateral=float(P2[k, 2]))
            if main:
                if name != "orig":
                    n0 = len(d["P"])
                    dv = np.linalg.norm(P2[:n0] - d["P"], axis=1)
                    vr["vertex_disp_free"] = stats(dv[free_v]); vr["vertex_disp_crest"] = stats(dv[reg0])
                    fs2 = free_surface_tris(P2, tri2, d["off"])
                    fv2 = np.zeros(len(P2), bool); fv2[tri2[fs2].ravel()] = True
                    ds = ref0.dist(P2[fv2 | reg])
                    m_reg = reg[fv2 | reg]
                    vr["to_orig_surface_free"] = stats(ds); vr["to_orig_surface_crest"] = stats(ds[m_reg])
                    ref2 = SurfRef(P2, tri2, s)
                    dr_ = ref2.dist(d["P"][free_v | reg0])
                    vr["orig_to_new_surface_free"] = stats(dr_); vr["orig_to_new_surface_crest"] = stats(dr_[reg0[free_v | reg0]])
                row, M, seg = R.mesh(P2, tri2, s, xc, X, Z)
                vr["section"] = row
                secs[name] = seg
                if name == "orig":
                    M0, seg0 = M, seg
                else:
                    vr["section_vs_orig"] = sec_compare(seg_points(seg0, xc, d["off"]), seg_points(seg, xc, d["off"]))
                    vr["mask_xor_m2"] = float((M0 ^ M).sum() * FINE * FINE)
            if f in fl:
                keep[(f, name)] = (P2, N2, tri2, s)
            if f == still_f and do_render:
                keep[("still", name)] = (P2, N2, tri2, s)
            fr["variants"][name] = vr
        if main:
            o = fr["variants"]["orig"]
            so = o.get("section") or {}
            for name in VARIANTS:
                vr = fr["variants"][name]
                sec = vr.get("section") or {}
                dd = lambda k: (sec.get(k) - so.get(k)) if (isinstance(sec.get(k), (int, float)) and isinstance(so.get(k), (int, float))) else None
                vr["delta_vs_orig"] = dict(section_top_m=dd("section_top_m"), eta_c_m=dd("eta_c"), score3=dd("score3"), lip=dd("lip"), chord_deg=dd("chord"),
                                           foot=dd("foot"), hood=dd("hood"),
                                           top3d_m=((vr.get("top3d_crest") or {}).get("e", 0) - (o.get("top3d_crest") or {}).get("e", 0)) if vr.get("top3d_crest") and o.get("top3d_crest") else None)
            section_plot({k: v for k, v in secs.items()}, xc, d["off"], "%s/hs_section_f%05d.png" % (od, f),
                         "centre section (lateral 0.5 m) frame %d t %.3f s: variants over the original record (numpy, %s)" % (f, d["t"], TOOL))
        rep["frames"][str(f)] = fr
        print("frame %d: nv %d nt %d, crest x %.1f e %.2f, %.1f s" % (f, len(d["P"]), len(d["tri"]), xc, ec, time.time() - T0))
    # ---------------- frame-to-frame consistency (geometric, exact distances)
    geo = {}
    for name in VARIANTS:
        geo[name] = {}
        refs = {f: SurfRef(keep[(f, name)][0], keep[(f, name)][2], keep[(f, name)][3]) for f in fl}
        for rn in FLK_REG:
            acc, vel = [], []
            for f in fl[1:-1]:
                Pk = keep[(f, name)][0]
                fr = rep["frames"][str(f)]
                q = Pk[flk_region(Pk, fr["section_crest_x"], fr["off"], rn)]
                dp = refs[f - 1].dist(q); dn = refs[f + 1].dist(q)
                acc.append(dp + dn); vel.append(0.5 * (dp - dn))
            acc = np.concatenate(acc); vel = np.concatenate(vel)
            geo[name][rn] = dict(second_diff_rms_m=float(np.sqrt(np.mean(acc ** 2))), second_diff_p95_m=float(np.percentile(np.abs(acc), 95)),
                                 motion_per_frame_rms_m=float(np.sqrt(np.mean(vel ** 2))), n=int(len(acc)))
    rep["flicker"]["geometric"] = dict(frames=fl, rule="vertices of frames %d..%d in each region: a = d(prev) + d(next), exact signed distances to the "
                                       "previous / next frame mesh of the SAME variant (0 for steady motion; real acceleration g dt^2 = 0.017 m); "
                                       "RMS / p95 of |a|; motion = (d_prev - d_next)/2" % (fl[1], fl[-2]), per_variant=geo)
    print("flicker geometric done %.1f s" % (time.time() - T0))
    # ---------------- renders
    if do_render:
        cams, cinfo = cams_from_clip(still_f)
        rep["render"]["cameras"] = dict(cams, **cinfo)
        for view, (W, H) in (("print", (960, 540)), ("print_close", (960, 540)), ("seat", (960, 540))):
            imgs, labs, ge = [], [], {}
            for name in VARIANTS:
                P2, N2, tri2, s = keep[("still", name)]
                t1 = time.perf_counter()
                im, mask = render(P2, N2, tri2, s, cams[view], W, H)
                ge[name] = dict(grid_energy=grid_energy(im, mask), render_s=time.perf_counter() - t1)
                imgs.append(im); labs.append("%s   grid energy %.4f" % (name, ge[name]["grid_energy"] or float("nan")))
                Image.fromarray(im).save("%s/render_f%05d_%s_%s.png" % (od, still_f, view, name))
            tiles(imgs, labs, 3, "%s/hs_f%05d_%s_tiles.png" % (od, still_f, view),
                  "frame %d, %s view: numpy approximation of FLIP3DWater.shader (not Unity). orig = record as is" % (still_f, view))
            if view in ZOOM:
                x0, y0, x1, y1 = ZOOM[view]
                zs = [np.asarray(Image.fromarray(im).crop((x0, y0, x1, y1)).resize((2 * (x1 - x0), 2 * (y1 - y0)), Image.NEAREST)) for im in imgs]
                tiles(zs, labs, 3, "%s/hs_f%05d_%s_zoom2x.png" % (od, still_f, view),
                      "frame %d, %s view, crop x %d-%d y %d-%d of the 960x540 still at 2x (nearest): numpy shader approximation" % (still_f, view, x0, x1, y0, y1))
            rep["render"][view] = ge
            print("render %s done %.1f s" % (view, time.time() - T0))
        rep["flicker"]["image"] = {}
        for view in ("print", "seat"):
            cam = dict(cams[view])
            imf = {}
            for name in VARIANTS:
                seq = [render(keep[(f, name)][0], keep[(f, name)][1], keep[(f, name)][2], keep[(f, name)][3], cam, 640, 360) for f in fl]
                Ys = [luma(im) for im, _ in seq]; Ms = [m for _, m in seq]
                sd, fd = [], []
                for k in range(1, len(fl) - 1):
                    m = ndi.binary_erosion(Ms[k - 1] & Ms[k] & Ms[k + 1], iterations=2)
                    sd.append(float(np.abs(Ys[k + 1] - 2 * Ys[k] + Ys[k - 1])[m].mean()))
                for k in range(1, len(fl)):
                    m = ndi.binary_erosion(Ms[k - 1] & Ms[k], iterations=2)
                    fd.append(float(np.abs(Ys[k] - Ys[k - 1])[m].mean()))
                imf[name] = dict(second_diff_mean=float(np.mean(sd)), per_middle_frame=sd, first_diff_mean=float(np.mean(fd)))
            rep["flicker"]["image"][view] = dict(frames=fl, camera="%s camera of frame %d, fixed (no heave), 640x360" % (view, still_f),
                                                 rule="mean |Y(k+1) - 2Y(k) + Y(k-1)| (sRGB luma 0..1) over water pixels present in all three frames "
                                                      "(eroded 2 px); first_diff = mean |Y(k) - Y(k-1)|", per_variant=imf)
            print("flicker image %s done %.1f s" % (view, time.time() - T0))
    rep["wall_s"] = time.time() - T0
    jp = "%s/hs_smooth_report.json" % od
    json.dump(clean(rep), open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    summary(rep)
    print("report", rel(jp), "wall %.1f s" % rep["wall_s"])


def summary(rep):
    for f, fr in rep["frames"].items():
        if "r2_record" not in fr:
            continue
        r2 = fr["r2_record"]; bn = fr["stored_vs_geometric_normals_free"]; pc = fr["pieces"]
        print("\nframe %s t %.3f  r2-record score3 %s lip %s eta_c %s | lattice(free) 2+axes %.3f (random %.4f) | deep skin %.0f%% tris | "
              "stored normals >30 deg off: %d of %d free verts" % (
                  f, fr["t"], r2.get("score3"), _g(r2.get("lip")), _g(r2.get("eta_c")), fr["lattice_free"]["share_2plus_axes_on"],
                  fr["lattice_free"]["random_expect_2plus"], 100 * pc["deep_tri_share"], bn["n_over30"], bn["n"]))
        print("  %-6s %6s %7s | %6s %6s %6s %7s | %6s %6s %7s | %6s %6s %6s | %6s %6s %6s" % (
            "var", "t_s", "nt", "s3", "lip", "eta_c", "dtop", "Hd_sec", "xor", "d3top", "dsMax", "dsP99", "rsMax", "nAng50", "nAng90", "e_med"))
        for nm, vr in fr["variants"].items():
            sec = vr.get("section") or {}; dl = vr.get("delta_vs_orig") or {}; sc = vr.get("section_vs_orig") or {}
            nr = vr.get("normal_rough_crest") or {}; dsc = vr.get("to_orig_surface_crest") or {}; rsc = vr.get("orig_to_new_surface_crest") or {}
            print("  %-6s %6.3f %7d | %6s %6s %6s %7s | %6s %6s %7s | %6s %6s %6s | %6s %6s %6s" % (
                nm, vr["info"].get("t_smooth_s", 0), vr["nt"], _g(sec.get("score3"), "%.3f"), _g(sec.get("lip")), _g(sec.get("eta_c")),
                _g(dl.get("section_top_m"), "%+.3f"), _g(sc.get("hausdorff_m"), "%.3f"), _g(vr.get("mask_xor_m2"), "%.2f"), _g(dl.get("top3d_m"), "%+.3f"),
                _g(dsc.get("max"), "%.3f"), _g(dsc.get("p99"), "%.3f"), _g(rsc.get("max"), "%.3f"),
                _g(nr.get("edge_angle_deg_median"), "%.2f"), _g(nr.get("edge_angle_deg_p90"), "%.2f"), _g(nr.get("edge_len_m_median"), "%.3f")))
    g = (rep.get("flicker") or {}).get("geometric", {}).get("per_variant", {})
    im = (rep.get("flicker") or {}).get("image", {})
    print("\nflicker %s: second-difference RMS (m) crest / back / front | image 2nd-diff print / seat" % rep["flicker"].get("geometric", {}).get("frames"))
    for nm in VARIANTS:
        a = g.get(nm, {})
        print("  %-6s %8s %8s %8s | %8s %8s" % (nm, *[_g((a.get(r) or {}).get("second_diff_rms_m"), "%.4f") for r in FLK_REG],
                                              *[_g(((im.get(v) or {}).get("per_variant", {}).get(nm) or {}).get("second_diff_mean"), "%.4f") for v in ("print", "seat")]))
    for view in ("print", "print_close", "seat"):
        ge = (rep.get("render") or {}).get(view)
        if ge:
            print("  grid energy %-11s " % view + "  ".join("%s %.4f" % (k, v["grid_energy"] or float("nan")) for k, v in ge.items()))


def _g(v, f="%.3f"):
    return (f % v) if isinstance(v, (int, float)) and v is not None and math.isfinite(v) else "-"


# ====================================================================== apply (batch, for a later clip)
def main_apply(a):
    low_priority()
    rd, od = a[1].replace("\\", "/").rstrip("/"), a[2].replace("\\", "/").rstrip("/")
    name = opt(a, "--variant", "T5")
    if name not in VARIANTS or name == "orig":
        raise SystemExit("variant must be one of %s" % [k for k in VARIANTS if k != "orig"])
    f0 = int(opt(a, "--from", "0")); f1 = int(opt(a, "--to", "999999"))
    files = [p for p in sorted(glob.glob(rd + "/surf/s_*.gw45s")) if f0 <= int(os.path.basename(p)[2:7]) <= f1]
    log = []
    for p in files:
        d = read_srf(p)
        T = topo(d["P"], d["tri"])
        s, _ = orient_sign(d["P"], d["tri"], d["N"])
        xe = crest_x(d["P"], d["tri"], d["off"]) if VARIANTS[name].get("subdiv") else None
        xc, ec = xe if xe else (265.0, 6.0)
        P2, N2, V2, tri2, info = make_variant(name, d, T, s, xc, ec)
        outp = write_srf("%s/%s" % (od, os.path.basename(p)), d, P2, N2, V2, tri2, force="--force" in a)
        log.append(dict(frame=d["frame"], src=rel(p), out=rel(outp), nv=len(P2), nt=len(tri2), t_s=info["t_smooth_s"]))
    json.dump(clean(dict(tool=TOOL, variant=name, note=VARIANTS[name]["note"], run=rel(rd), n=len(log), frames=log)),
              open(od + "/hs_apply_%s.json" % name, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("applied %s to %d records -> %s" % (name, len(log), rel(od)))


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("test", "apply"):
        print(__doc__)
        sys.exit(1)
    main_test(a) if a[0] == "test" else main_apply(a)
