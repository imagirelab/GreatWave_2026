# -*- coding: utf-8 -*-
"""FLIP55 C2H STITCH: the per-frame Unity surface of the hero C2H = the 0.25 m nest's own surface inside the nest region and DFG-2B-V's
every-frame hero surface outside it, joined along a fixed seam without a crack and without overlapping sheets (py -3.10 -B; numpy, scipy).
2026-10-19 written new (Claude, workflow subagent) for the user's Q90 (verbatim, recorded in Docs/Workflow/Production_Workflow_ja.md):
  把 0.25 m 局部加密继续算到第 2、3 组，并和外面的水面拼接，做成主角。
  OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral
Nothing frozen is edited and no record is changed: the nest's surf records (C2H run) and the parent's (DFGBVr hero re-record) are READ;
the stitched records are NEW files under Unity/Build/FLIP55/stitch/C2H/. DISPLAY ONLY: the physics records stay as they are.

Seam (registered in AM-F55-C2H before C2H runs; chosen by `seamscan` on C2's 113 recorded frames, rule SEAM_RULE) [chosen + measured]:
  nest region R = x_s <= x <= x_e, 0 <= lateral <= y_s (plan metres; lateral = |Unity z|, the record holds lateral >= 0 and the FLIP3D
  player mirrors it at y = 0). The nest's surface record covers x 179.9-356.1 m, lateral 0-45.4 m (crop_z1 = the y band's inner edge
  45 m): the y seam therefore lies at or inside 45 m (the nest has no recorded surface in its y band 45-60 m). The end seam x_e closes the
  nest's closed face x 356 m (the parent's swash runs on to x ~381 m).
Per frame (rule STITCH_RULE):
  1. clip both meshes EXACTLY at the seam planes (triangles cut by the vertical planes x = x_s, lateral = y_s, x = x_e; cut vertices
     interpolated, shared by both sides of each cut): the nest keeps R, the parent keeps the complement. No overlap -> no z-fighting flicker.
  2. on the visible free-surface pieces (connected pieces reaching >= -1 m above still, the hs_mesh_smooth rule; the hidden under-water skin
     near the bed is clipped but not joined) take each mesh's TOP boundary chain on the seam path (the highest boundary edge at every path
     coordinate s) and measure the seam mismatch dz(s) = h_parent(s) - h_nest(s) [measured per frame: mean, rms, max, p95].
  3. blend strip (display only): nest vertices of the visible pieces within BLEND_M of the seam (inside R) and within BLEND_DEPTH_M below
     the nest's top chain (so the hidden bed skin is not moved) are moved vertically by
     w(d) x clip(dz(s), +-CAP_M), w = smoothstep(1 - d / BLEND_M), d = plan distance to the seam, s = the seam coordinate of the nearest
     point -> at the seam the nest's top chain lies on the parent's top chain; the 0.25 m detail fades in over BLEND_M.
  4. zipper: the two top chains (sorted by s) are joined by a strip of triangles that uses ONLY their existing vertices (no new vertex),
     on the s intervals where both chains exist -> no crack on the visible top surface; where dz was capped the strip is a short step.
  5. N3 normals of the stitched record (hs_hero_n3.n3_bytes, unchanged: area-weighted normals + 3 one-ring averages, seam rule).
Every stitched record keeps the GW45SRF1 layout (g52b3_run.write_surface: positions uint16 over the record's box, oct normals, velocity
float16, uint32 triangles; |lateral| < 1e-4 -> normal lateral 0) so the FLIP3D player streams it unchanged (GW45LIST1).

usage (py -3.10 -B; every command prints ONE json line last):
  f55_stitch.py seamscan [--frames=a-b] [--step=3]   seam mismatch of C2 (the recorded group-1 nest) vs the parent on candidate lines ->
                                                    Unity/Build/FLIP55/stitch/seamscan_C2.json (+ the chosen seam by SEAM_RULE)
  f55_stitch.py selftest                            synthetic clip / zipper / blend / write-read checks + one real C2 frame stitched into
                                                    Unity/Build/FLIP55/_scratch/stitch_selftest (no C2H needed)
  f55_stitch.py stitch [--nest=<run dir>] [--from=F] [--to=F] [--workers=N] [--simulate] [--out=<dir>]
                                                    stitched records s_<f>.gw45s + rows.jsonl (resumable; --simulate: C2's frames into
                                                    _scratch/stitch_sim, the real code)
  f55_stitch.py verify [--out=<dir>]                every stitched record: readable, finite, header = name, indices, N3 unit normals,
                                                    open visible seam edges, seam mismatch summary -> stitch_verify.json
  f55_stitch.py status
Tags: [measured] records, [computed] derived, [chosen] rules.
"""
import os
for _k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
import sys, json, time, struct, hashlib, glob, math, importlib.util

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
REPO = "G:/Unity/GreatWave_2026_Fresh"
TOOLS = REPO + "/Tools/GWWaveGen"
TOOL = "Tools/GWWaveGen/flip55/f55_stitch.py"
import numpy as np                                                     # noqa: E402

B55 = REPO + "/Unity/Build/FLIP55"
STITCH_ROOT = B55 + "/stitch"
OUT_DEF = STITCH_ROOT + "/C2H"
SCAN_JSON = STITCH_ROOT + "/seamscan_C2.json"
SIM_OUT = B55 + "/_scratch/stitch_sim"
SELFTEST_OUT = B55 + "/_scratch/stitch_selftest"
PARENT_RID = "DFGBVr_D19B_xf272p25_in5c0p6_tp3_dp0p5_c1152_t125_long"
PARENT_RUN = REPO + "/Unity/Build/FLIP52B3/hero/runs/" + PARENT_RID          # every-frame surface 1153-3001, bit-identical to the judged run
C2_RID = "F55N_D19B_x180y60_dp0p25_c1056"
C2_RUN = B55 + "/runs/" + C2_RID
C2H_RID = "F55NH_D19B_x180y60_dp0p25_c1056_t125"                        # = f55_c2h.RID_C2H
C2H_RUN = B55 + "/runs/" + C2H_RID
F_FIRST, F_LAST = 1153, 3001                                            # 48-125 s (the hero window, Q86)
FPS = 24.0
STILL = 0.0759846568107605                                              # DFG-2B-V still offset [measured]; both records carry it
N3_TOOL = TOOLS + "/flip52hs/hs_hero_n3.py"
N3_TOOL_SHA = None                                                      # filled by load_n3 (reported, the tool is used unchanged)
LABEL = "OUT-OF-RULE 0.25 m nest (C2ID crest +5.9% vs +-2%, Q89/Q90); parent DFG-2B-V valid; energy = DM1A spectral"
LABEL_JA = "規則の外の 0.25 m の入れ子（同一性の試しで頂の高さ +5.9 %、容差 ±2 %、Q89/Q90）。親 DFG-2B-V は有効。エネルギーは DM1A のスペクトル"
DISPLAY_EN = ("DISPLAY STITCH: inside the nest region the 0.25 m nest's own surface, outside it DFG-2B-V's 0.5 m surface; along the seam a "
              "display-only blend strip and a zipper strip join them (no physics record changed)")

# ------------------------------------------------------------------ the seam (registered; see SEAM_RULE / seamscan_C2.json)
SEAM = dict(x_s=189.0, y_s=44.0, x_e=350.0, blend_m=6.0, cap_m=1.5)     # [chosen by SEAM_RULE on C2's 113 frames, seamscan_C2.json 2026-10-19:
# pooled rms of dz x_s 187 0.063 / 189 0.064 m (tie -> 189), y_s 43 0.244 / 44 0.250 m (tie -> 44; 45 = the crop edge, max 15 m), x_e 350
# 0.327 m (345 0.384, 335 0.432) [measured]]
SEAM_CANDIDATES = dict(x_s=(181.0, 183.0, 185.0, 187.0, 189.0, 191.0, 193.0, 195.0, 197.0), y_s=(38.0, 40.0, 42.0, 43.0, 44.0, 45.0),
                       x_e=(320.0, 325.0, 330.0, 335.0, 340.0, 345.0, 350.0))
SEAM_RULE = ("on C2's recorded frames (r5 every 3rd frame, 55-69 s, the only 0.25 m surfaces before C2H) against the parent's surface at the "
             "same frames: for each candidate line the pooled rms over frames and seam samples (every 0.25 m) of dz = h_parent - h_nest "
             "(top of the visible free surface on that vertical line); x_s and x_e = the candidate with the smallest pooled rms (ties within "
             "0.01 m: x_s the one farther from the nest's closed face x 180 m, x_e the larger x); y_s = the smallest pooled rms among the "
             "candidates <= 44 m (the nest's recorded surface ends at its crop 45 m; 1 m margin so the crop edge never enters the stitch) "
             "[chosen before C2H]; BLEND_M 6 m (24 nest cells): the display blend touches only the nest strips x 189-195 m (lateral 0-44 m, "
             "inside the nest's x relaxation band 180-195 m), x 344-350 m (lateral 0-44 m, the beach next to the closed face) and lateral "
             "38-44 m (x 189-350 m; this strip lies in the nest INTERIOR, 1-7 m inside the y band's inner edge 45 m, because the nest's surface "
             "record ends at 45 m); the nest interior x 195-344 m, lateral 0-38 m (seat x 284 / lateral 20 m, the crest x 230-300 m) is never "
             "moved; CAP_M 1.5 m (the scan's p95 |dz| on the y / end seams is 0.53 / 0.62 m and its max 1.72 / 1.60 m [measured]: above 1.5 m "
             "the strip keeps a short step) [chosen]")
FREE_EMAX = -1.0                     # a connected piece whose highest point is below still - 1 m is not the free surface (hs_mesh_smooth rule)
TOL = 1e-6
SAMPLE_DS = 0.25                     # seam sample spacing for the mismatch [chosen = the nest particle spacing]
CHAIN_GAP_M = 1.0                    # gaps <= 1 m in a top chain are bridged by the zipper (4 nest cells, 2 parent cells) [chosen]
BLEND_DEPTH_M = 3.0                  # the blend moves only vertices within 3 m below the nest chain at their seam coordinate (the hidden bed skin
                                     # piece lies 4-15 m below the surface away from the beach [measured on C2 records]) [chosen]
OPEN_EMIN = -2.5                     # verify: an open seam edge counts as visible when it reaches above still - 2.5 m (the skin: -15 .. -3 m) [chosen]
HEAD = struct.Struct("<8sIIdiIIffffffff")
HEAD_BYTES = 96
STITCH_RULE = ("clip at the seam planes (nest keeps R = x_s..x_e x 0..y_s, parent the rest; cut vertices shared within each mesh); top "
               "boundary chain of the visible pieces (pieces reaching >= still - 1 m) on the seam path; dz(s) = h_parent - h_nest at the "
               "nest chain's vertices (parent chain linear in s); blend nest vertices within blend_m (and within 3 m below the nest chain) by smoothstep(1 - d/blend_m) x "
               "clip(dz, +-cap_m); zipper the two chains (existing vertices only) on the s intervals both cover (chain gaps <= 1 m bridged); N3 normals "
               "(hs_hero_n3.n3_bytes unchanged)")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def rel(p):
    p = str(p).replace("\\", "/")
    return p[len(REPO) + 1:] if p.startswith(REPO + "/") else p


def sha(p):
    if not os.path.exists(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jload(p):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        v = float(o)
        return v if math.isfinite(v) else None
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def guard(p):
    a = os.path.abspath(p).replace("\\", "/")
    ok = any(a.lower().startswith(r.lower() + "/") for r in (B55, REPO + "/Unity/Build/FLIP3D"))
    if not ok:
        raise SystemExit("refused to write %s: outside Unity/Build/FLIP55 and Unity/Build/FLIP3D" % a)
    os.makedirs(os.path.dirname(a), exist_ok=True)
    return a


def jdump(o, p):
    guard(p)
    tmp = p + ".part"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(clean(o), fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p


def final(d):
    d = clean(dict([("label", LABEL)] + [(k, v) for k, v in d.items() if k != "label"]))
    print(json.dumps(d, ensure_ascii=False, default=str), flush=True)
    return 0 if d.get("ok") else 1


def opts(argv):
    o = {a[2:].split("=", 1)[0]: (a.split("=", 1)[1] if "=" in a else "1") for a in argv if a.startswith("--")}
    return [a for a in argv if not a.startswith("--")], o


def t_of(f):
    return (int(f) - 1) / FPS


# ====================================================================== GW45SRF1 read / write (g52b3_run.write_surface layout)
def oct_decode(n2):
    f = n2.astype(np.float64) / 65535.0 * 2.0 - 1.0
    x, y = f[:, 0], f[:, 1]
    z = 1.0 - np.abs(x) - np.abs(y)
    t = np.clip(-z, 0, None)
    x = np.where(x >= 0, x - t, x + t); y = np.where(y >= 0, y - t, y + t)
    n = np.stack([x, y, z], 1)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def oct_encode(n):                                                       # = g52b3_run.oct_encode / hs_mesh_smooth.oct_encode
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
    tri = np.frombuffer(b, np.uint32, nt * 3, o).reshape(nt, 3).astype(np.int64)
    lo = np.array([x0, y0, z0], np.float64); hi = np.array([x1, y1, z1], np.float64)
    P = q.astype(np.float64) / 65535.0 * (hi - lo) + lo
    return dict(t=float(t), frame=int(fr), off=float(off), P=P, N=oct_decode(n2), V=v.astype(np.float64), T=tri, lo=lo, hi=hi, bytes=len(b),
                qstep=(hi - lo) / 65535.0, path=path)


def srf_bytes(t, frame, off, P, N, V, T):
    """the record bytes exactly as g52b3_run.write_surface writes them (seam |lateral| < 1e-4 -> normal lateral 0; box quantisation)."""
    N = np.array(N, np.float64)
    seam = np.abs(P[:, 2]) < 1e-4
    N[seam, 2] = 0.0
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    lo = P.min(0) if len(P) else np.zeros(3); hi = P.max(0) if len(P) else np.ones(3)
    q = np.round((P - lo) / np.maximum(hi - lo, 1e-9) * 65535).astype(np.uint16)
    head = HEAD.pack(b"GW45SRF1", 1, HEAD_BYTES, float(t), int(frame), len(P), len(T), *[float(x) for x in lo], *[float(x) for x in hi],
                     float(off), 0.0)
    head = head + b"\0" * (HEAD_BYTES - len(head))
    return (head + q.tobytes() + oct_encode(N).tobytes() + np.asarray(V, np.float16).tobytes() + np.asarray(T, np.uint32).tobytes(),
            float(np.max(np.abs(q.astype(np.float64) / 65535.0 * (hi - lo) + lo - P))) if len(P) else 0.0)


_N3 = None


def load_n3():
    """hs_hero_n3 imported by path, unchanged (its n3_bytes is the N3 recipe judged in Unity)."""
    global _N3, N3_TOOL_SHA
    if _N3 is None:
        sys.path.insert(0, TOOLS + "/flip52hs")
        spec = importlib.util.spec_from_file_location("hs_hero_n3", N3_TOOL)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        _N3 = m
        N3_TOOL_SHA = sha(N3_TOOL)
    return _N3


# ====================================================================== mesh pieces
def components_max(P, T, nv):
    """connected component label per vertex and the highest elevation (up) of each component."""
    from scipy import sparse
    from scipy.sparse.csgraph import connected_components
    if len(T) == 0:
        return np.zeros(nv, np.int64), np.full(1, -1e9)
    A = sparse.coo_matrix((np.ones(3 * len(T)), (T[:, [0, 1, 2]].ravel(), T[:, [1, 2, 0]].ravel())), shape=(nv, nv))
    n, lab = connected_components(A, directed=False)
    cmax = np.full(n, -1e9)
    np.maximum.at(cmax, lab, P[:, 1])
    return lab, cmax


class Mesh:
    """a growing vertex set (P, V, N, lab) and a triangle list; split() appends shared cut vertices."""

    def __init__(self, d, off):
        self.P = d["P"].copy(); self.V = d["V"].copy(); self.N = d["N"].copy()
        self.T = d["T"].copy()
        lab, cmax = components_max(self.P, self.T, len(self.P))
        self.vis_v = (cmax[lab] - off) >= FREE_EMAX                     # vertex belongs to a visible free-surface piece
        self.cache = {}
        self.n0 = len(self.P)

    def cut_vertex(self, a, b, axis, value, d):
        key = (min(a, b), max(a, b), axis, value)
        k = self.cache.get(key)
        if k is not None:
            return k
        a_, b_ = key[0], key[1]
        t = d[a_] / (d[a_] - d[b_])
        p = self.P[a_] + t * (self.P[b_] - self.P[a_]); p[axis] = value
        v = self.V[a_] + t * (self.V[b_] - self.V[a_])
        n = self.N[a_] + t * (self.N[b_] - self.N[a_]); n = n / max(np.linalg.norm(n), 1e-12)
        k = len(self.P) + len(self.newP)
        self.newP.append(p); self.newV.append(v); self.newN.append(n); self.newvis.append(bool(self.vis_v[a_] or self.vis_v[b_]))
        self.cache[key] = k
        return k

    def split(self, T, axis, value):
        """T (m,3) -> (T_lo, T_hi): triangles of T cut by the plane coord[axis] = value; T_lo on the side <= value, T_hi >= value. Vertices within
        TOL of the plane are snapped onto it (both sides keep them); cut vertices are shared by the two sides."""
        d = self.P[:, axis] - value
        near = np.abs(d) <= TOL
        if near.any():
            self.P[near, axis] = value
            d = np.where(near, 0.0, d)
        if len(T) == 0:
            return T.copy(), T.copy()
        dt = d[T]
        lo_all = (dt <= 0).all(1)
        hi_all = (dt >= 0).all(1)
        on_plane = lo_all & hi_all                       # a triangle lying in the plane (vertical face): kept on the hi side only
        T_lo = [T[lo_all & ~on_plane]]
        T_hi = [T[hi_all]]
        mixed = np.where(~(lo_all | hi_all))[0]
        self.newP, self.newV, self.newN, self.newvis = [], [], [], []
        lo_new, hi_new = [], []
        for i in mixed:
            tr = T[i]; s = dt[i]
            sg = np.sign(s)
            # rotate so that the 'special' vertex is first, keeping the cyclic order (orientation)
            if (sg == 0).sum() == 1:
                k = int(np.where(sg == 0)[0][0])
                a, b, c = tr[k], tr[(k + 1) % 3], tr[(k + 2) % 3]
                x = self.cut_vertex(b, c, axis, value, d)
                t1, t2 = (a, b, x), (a, x, c)
                if d[b] < 0:
                    lo_new.append(t1); hi_new.append(t2)
                else:
                    hi_new.append(t1); lo_new.append(t2)
            else:
                pos = sg > 0
                k = int(np.where(pos)[0][0]) if pos.sum() == 1 else int(np.where(~pos)[0][0])      # the lone vertex
                a, b, c = tr[k], tr[(k + 1) % 3], tr[(k + 2) % 3]
                xab = self.cut_vertex(a, b, axis, value, d)
                xac = self.cut_vertex(a, c, axis, value, d)
                lone = (a, xab, xac)
                quad = [(xab, b, c), (xab, c, xac)]
                if d[a] > 0:
                    hi_new.append(lone); lo_new += quad
                else:
                    lo_new.append(lone); hi_new += quad
        if self.newP:
            self.P = np.vstack([self.P, np.array(self.newP)]); self.V = np.vstack([self.V, np.array(self.newV)])
            self.N = np.vstack([self.N, np.array(self.newN)]); self.vis_v = np.concatenate([self.vis_v, np.array(self.newvis, bool)])
        if lo_new:
            T_lo.append(np.array(lo_new, np.int64))
        if hi_new:
            T_hi.append(np.array(hi_new, np.int64))
        return np.vstack(T_lo) if T_lo else np.zeros((0, 3), np.int64), np.vstack(T_hi) if T_hi else np.zeros((0, 3), np.int64)


def split_all(m, seam):
    """every triangle of the record cut by all three seam planes (the cut vertices of one edge are shared by every triangle that uses that
    edge, so no T-junction is left where the planes cross, e.g. at the corners (x_s, y_s) / (x_e, y_s))."""
    T = m.T
    for axis, value in ((0, seam["x_s"]), (2, seam["y_s"]), (0, seam["x_e"])):
        lo, hi = m.split(T, axis, value)
        T = np.vstack([lo, hi])
    c = m.P[T].mean(1)
    inside = (c[:, 0] >= seam["x_s"]) & (c[:, 0] <= seam["x_e"]) & (c[:, 2] <= seam["y_s"])
    return T, inside


def clip_nest(m, seam):
    T, inside = split_all(m, seam)
    return T[inside]


def clip_parent(m, seam):
    T, inside = split_all(m, seam)
    return T[~inside]


# ====================================================================== the seam path
def path_s(P, seam, tol=1e-5):
    """path coordinate s of points on the seam path (NaN elsewhere): X x = x_s (s = lateral), Y lateral = y_s (s = y_s + x - x_s), E x = x_e
    (s = y_s + (x_e - x_s) + (y_s - lateral))."""
    xs, ys, xe = seam["x_s"], seam["y_s"], seam["x_e"]
    x, la = P[:, 0], P[:, 2]
    s = np.full(len(P), np.nan)
    onX = (np.abs(x - xs) <= tol) & (la <= ys + tol) & (la >= -tol)
    onY = (np.abs(la - ys) <= tol) & (x >= xs - tol) & (x <= xe + tol)
    onE = (np.abs(x - xe) <= tol) & (la <= ys + tol) & (la >= -tol)
    s[onE] = ys + (xe - xs) + (ys - la[onE])
    s[onY] = ys + (x[onY] - xs)
    s[onX] = la[onX]
    return s


def path_len(seam):
    return 2 * seam["y_s"] + (seam["x_e"] - seam["x_s"])


def path_point(s, seam):
    """plan (x, lateral) of path coordinates s."""
    xs, ys, xe = seam["x_s"], seam["y_s"], seam["x_e"]
    s = np.asarray(s, float)
    x = np.where(s <= ys, xs, np.where(s <= ys + (xe - xs), xs + (s - ys), xe))
    la = np.where(s <= ys, s, np.where(s <= ys + (xe - xs), ys, ys - (s - ys - (xe - xs))))
    return x, la


def nearest_on_path(x, la, seam):
    """for points inside R: distance d to the seam path and the path coordinate s of the nearest point."""
    xs, ys, xe = seam["x_s"], seam["y_s"], seam["x_e"]
    dX = x - xs; dY = ys - la; dE = xe - x
    D = np.stack([dX, dY, dE], 1)
    k = np.argmin(D, 1)
    d = D[np.arange(len(x)), k]
    s = np.where(k == 0, np.clip(la, 0, ys), np.where(k == 1, ys + np.clip(x - xs, 0, xe - xs), ys + (xe - xs) + (ys - np.clip(la, 0, ys))))
    return d, s


def boundary_edges(T, nv):
    """directed boundary edges (u -> v as in their only triangle)."""
    if len(T) == 0:
        return np.zeros((0, 2), np.int64)
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    es = np.sort(e, 1)
    key = es[:, 0] * nv + es[:, 1]
    uk, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
    once = cnt[inv] == 1
    return e[once]


def top_chain(P, T, vis_v, seam):
    """the top boundary chain of the visible pieces on the seam path -> dict(v (vertex ids sorted by s), s, z, edges, intervals, multi)."""
    E = boundary_edges(T, len(P))
    s = path_s(P, seam)
    on = np.isfinite(s[E[:, 0]]) & np.isfinite(s[E[:, 1]]) & vis_v[E[:, 0]] & vis_v[E[:, 1]]
    E = E[on]
    s0, s1 = s[E[:, 0]], s[E[:, 1]]
    z0, z1 = P[E[:, 0], 1], P[E[:, 1], 1]
    keep = np.abs(s1 - s0) > 1e-9
    E, s0, s1, z0, z1 = E[keep], s0[keep], s1[keep], z0[keep], z1[keep]
    out = dict(n_edges_on_path=int(len(E)))
    if len(E) == 0:
        out.update(v=np.zeros(0, np.int64), s=np.zeros(0), z=np.zeros(0), edges=np.zeros((0, 2), np.int64), intervals=[], multi_frac=0.0)
        return out
    a = np.minimum(s0, s1); b = np.maximum(s0, s1)
    za = np.where(s0 <= s1, z0, z1); zb = np.where(s0 <= s1, z1, z0)
    sm = 0.5 * (a + b)
    # height of every edge at every midpoint (NaN outside its s range)
    cover = (a[None, :] <= sm[:, None] + 1e-5) & (b[None, :] >= sm[:, None] - 1e-5)
    w = np.clip((sm[:, None] - a[None, :]) / np.maximum(b - a, 1e-12)[None, :], 0, 1)
    zh = np.where(cover, za[None, :] + w * (zb - za)[None, :], -np.inf)
    zself = za + 0.5 * (zb - za)
    top = zself >= zh.max(1) - 1e-6
    ncov = (cover & (zh > -1e8) & (np.abs(zh - zh.max(1)[:, None]) > 0.3)).sum(1)        # other crossings > 0.3 m below the top at this s
    Et = E[top]
    vv = np.unique(Et.ravel())
    order = np.lexsort((P[vv, 1], s[vv]))
    vv = vv[order]
    # coverage intervals of the top chain (union of its edges' s ranges)
    iv = sorted(zip(a[top], b[top]))
    merged = []
    for lo, hi in iv:
        if merged and lo <= merged[-1][1] + CHAIN_GAP_M:          # small gaps of the top chain (a fold, a vertical step) are bridged
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    out.update(v=vv, s=s[vv], z=P[vv, 1], edges=Et, intervals=merged, multi_frac=float(np.mean(ncov[top] > 0)) if top.any() else 0.0,
               dirs={(int(u), int(w_)): 1 for u, w_ in E})
    return out


def _edge_height(ch, sq):
    """the top chain's height at path coordinates sq (linear along its edges; NaN outside its coverage)."""
    E = ch["edges"]
    if len(E) == 0:
        return np.full(len(sq), np.nan)
    P_s = dict(zip(ch["v"].tolist(), ch["s"].tolist()))
    P_z = dict(zip(ch["v"].tolist(), ch["z"].tolist()))
    a = np.array([min(P_s[u], P_s[w]) for u, w in E]); b = np.array([max(P_s[u], P_s[w]) for u, w in E])
    za = np.array([P_z[u] if P_s[u] <= P_s[w] else P_z[w] for u, w in E]); zb = np.array([P_z[w] if P_s[u] <= P_s[w] else P_z[u] for u, w in E])
    sq = np.asarray(sq, float)
    cover = (a[None, :] <= sq[:, None] + 1e-5) & (b[None, :] >= sq[:, None] - 1e-5)          # 1e-5: records hold lateral -4e-8 on y = 0
    w = np.clip((sq[:, None] - a[None, :]) / np.maximum(b - a, 1e-12)[None, :], 0, 1)
    zh = np.where(cover, za[None, :] + w * (zb - za)[None, :], -np.inf)
    h = zh.max(1)
    return np.where(np.isfinite(h), h, np.nan)


def intersect_intervals(A, B):
    out = []
    i = j = 0
    while i < len(A) and j < len(B):
        lo = max(A[i][0], B[j][0]); hi = min(A[i][1], B[j][1])
        if hi > lo + 1e-6:
            out.append([lo, hi])
        if A[i][1] < B[j][1]:
            i += 1
        else:
            j += 1
    return out


def zipper(av, as_, bv, bs, dir_a, dir_b):
    """triangles joining two chains sorted by s (existing vertex ids only). Orientation: each triangle runs its chain edge opposite to the
    edge's direction in its own mesh (dir_* holds the directed boundary edges), so the strip continues the surfaces' winding."""
    tris = []
    i = j = 0
    while i < len(av) - 1 or j < len(bv) - 1:
        if j >= len(bv) - 1 or (i < len(av) - 1 and as_[i + 1] <= bs[j + 1]):
            p, q, r = av[i], av[i + 1], bv[j]
            i += 1
            d = dir_a
        else:
            p, q, r = bv[j], bv[j + 1], av[i]
            j += 1
            d = dir_b
        # the chain edge p-q: if its mesh has p -> q, the strip uses q -> p
        tris.append((q, p, r) if (int(p), int(q)) in d else (p, q, r))
    return tris


# ====================================================================== the line scan (seamscan): top of the visible surface on a vertical line
def line_tops(P, T, vis_t, axis, value, other, s_lo, s_hi, ds=SAMPLE_DS):
    """heights of the visible free surface where the vertical plane coord[axis] = value meets it, sampled every ds along the other plan axis
    in [s_lo, s_hi]: per sample the top crossing (NaN if none) and the number of crossings > 0.3 m below the top (overturning / sheets)."""
    sq = np.arange(s_lo, s_hi + 1e-9, ds)
    Tv = T[vis_t]
    c = P[Tv][:, :, axis]
    m = (c.min(1) <= value) & (c.max(1) >= value)
    Tv = Tv[m]
    top = np.full(len(sq), np.nan); nlow = np.zeros(len(sq), np.int64)
    if len(Tv) == 0:
        return sq, top, nlow
    segs = []
    for k in range(3):
        a, b = Tv[:, k], Tv[:, (k + 1) % 3]
        da, db = P[a, axis] - value, P[b, axis] - value
        cr = (da * db < 0) | ((da == 0) & (db != 0))
        t = np.where(cr, da / np.where(da - db == 0, 1, da - db), np.nan)
        pt_o = P[a, other] + t * (P[b, other] - P[a, other])
        pt_z = P[a, 1] + t * (P[b, 1] - P[a, 1])
        segs.append((cr, pt_o, pt_z))
    so = np.full((len(Tv), 2), np.nan); sz = np.full((len(Tv), 2), np.nan); cnt = np.zeros(len(Tv), np.int64)
    for cr, po, pz in segs:
        for idx in np.where(cr)[0]:
            if cnt[idx] < 2:
                so[idx, cnt[idx]] = po[idx]; sz[idx, cnt[idx]] = pz[idx]; cnt[idx] += 1
    ok = cnt == 2
    so, sz = so[ok], sz[ok]
    a_ = so.min(1); b_ = so.max(1)
    za = np.where(so[:, 0] <= so[:, 1], sz[:, 0], sz[:, 1]); zb = np.where(so[:, 0] <= so[:, 1], sz[:, 1], sz[:, 0])
    for i0 in range(0, len(sq), 256):
        q = sq[i0:i0 + 256]
        cov = (a_[None, :] <= q[:, None]) & (b_[None, :] >= q[:, None])
        w = np.clip((q[:, None] - a_[None, :]) / np.maximum(b_ - a_, 1e-12)[None, :], 0, 1)
        zh = np.where(cov, za[None, :] + w * (zb - za)[None, :], -np.inf)
        mx = zh.max(1)
        top[i0:i0 + 256] = np.where(np.isfinite(mx), mx, np.nan)
        nlow[i0:i0 + 256] = (cov & (zh < mx[:, None] - 0.3)).sum(1)
    return sq, top, nlow


def vis_tris(d):
    lab, cmax = components_max(d["P"], d["T"], len(d["P"]))
    return (cmax[lab[d["T"][:, 0]]] - d["off"]) >= FREE_EMAX


def surf_path(rd, f):
    return "%s/surf/s_%05d.gw45s" % (rd, f)


def cmd_seamscan(o):
    """C2's recorded frames vs the parent at the same frames, on every candidate line (SEAM_CANDIDATES) -> SCAN_JSON + the chosen seam."""
    t0 = time.time()
    nest_rd = o.get("nest", C2_RUN)
    fr = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(nest_rd + "/surf/s_*.gw45s"))
    if "frames" in o:
        a_, b_ = [int(v) for v in o["frames"].split("-")]
        fr = [f for f in fr if a_ <= f <= b_]
    step = int(o.get("step", "1"))
    fr = fr[::step]
    fr = [f for f in fr if os.path.exists(surf_path(PARENT_RUN, f))]
    if not fr:
        return final(dict(ok=False, step="seamscan", why="no common nest / parent surface frames"))
    acc = {k: {v: [] for v in vals} for k, vals in SEAM_CANDIDATES.items()}
    multi = {k: {v: [0, 0] for v in vals} for k, vals in SEAM_CANDIDATES.items()}
    per_frame = []
    for f in fr:
        dn, dp = read_srf(surf_path(nest_rd, f)), read_srf(surf_path(PARENT_RUN, f))
        vn, vp = vis_tris(dn), vis_tris(dp)
        row = dict(frame=f, t=t_of(f))
        for key, vals in SEAM_CANDIDATES.items():
            for v in vals:
                if key == "x_s":
                    args = (0, v, 2, 0.0, SEAM["y_s"])
                elif key == "x_e":
                    args = (0, v, 2, 0.0, SEAM["y_s"])
                else:
                    args = (2, v, 0, SEAM["x_s"], SEAM["x_e"])
                sq, hn, mn = line_tops(dn["P"], dn["T"], vn, *args)
                _, hp, mp = line_tops(dp["P"], dp["T"], vp, *args)
                ok = np.isfinite(hn) & np.isfinite(hp)
                dz = (hp - hn)[ok]
                acc[key][v].append(dz)
                multi[key][v][0] += int(((mn > 0) | (mp > 0))[ok].sum()); multi[key][v][1] += int(ok.sum())
                if v == SEAM[key]:
                    row[key] = dict(n=int(ok.sum()), n_nest_only=int((np.isfinite(hn) & ~np.isfinite(hp)).sum()),
                                    n_parent_only=int((~np.isfinite(hn) & np.isfinite(hp)).sum()),
                                    mean=float(dz.mean()) if len(dz) else None, rms=float(np.sqrt((dz ** 2).mean())) if len(dz) else None,
                                    max_abs=float(np.abs(dz).max()) if len(dz) else None)
        per_frame.append(row)
    summ = {}
    for key, vals in SEAM_CANDIDATES.items():
        summ[key] = {}
        for v in vals:
            z = np.concatenate(acc[key][v]) if acc[key][v] else np.zeros(0)
            summ[key][str(v)] = dict(n=int(len(z)), mean=float(z.mean()) if len(z) else None, rms=float(np.sqrt((z ** 2).mean())) if len(z) else None,
                                     p95_abs=float(np.percentile(np.abs(z), 95)) if len(z) else None, max_abs=float(np.abs(z).max()) if len(z) else None,
                                     multi_frac=(multi[key][v][0] / max(multi[key][v][1], 1)))
    # the rule
    def pick(key, cand, prefer):
        rows = [(summ[key][str(v)]["rms"], v) for v in cand if summ[key][str(v)]["rms"] is not None]
        if not rows:
            return None
        best = min(r[0] for r in rows)
        near = [v for r_, v in rows if r_ <= best + 0.01]
        return max(near) if prefer == "max" else min(near)
    chosen = dict(x_s=pick("x_s", SEAM_CANDIDATES["x_s"], "max"), y_s=pick("y_s", [v for v in SEAM_CANDIDATES["y_s"] if v <= 44.0], "max"),
                  x_e=pick("x_e", SEAM_CANDIDATES["x_e"], "max"))
    res = dict(date=now(), tool=TOOL, step="seamscan", nest_run=rel(nest_rd), parent_run=rel(PARENT_RUN), frames=[fr[0], fr[-1]], n_frames=len(fr),
               rule=SEAM_RULE, sample_ds_m=SAMPLE_DS, candidates=SEAM_CANDIDATES, summary=summ, chosen_by_rule=chosen, seam_in_tool=SEAM,
               tool_matches_rule=bool(all(chosen[k] == SEAM[k] for k in chosen)), per_frame=per_frame,
               still_level_note=dict(calib_step_vs_parent_hf_m=-0.0331101459608714,
                                     text="calib55_C2.json: the nest's still level (R1 surface) reads 0.033 m below the parent's hf level [measured]; "
                                          "the seam means here are dz = h_parent - h_nest on the surface MESHES (r5), reported as measured, the "
                                          "cause of a mean offset is not asserted"),
               label=LABEL, seconds=round(time.time() - t0, 1),
               tags=dict(dz="measured (record to record, top of the visible surface on each vertical line)", rule="chosen before C2H"))
    if "out" not in o:
        jdump(res, SCAN_JSON)
    return final(dict(ok=True, step="seamscan", out=rel(SCAN_JSON), frames=res["frames"], n_frames=len(fr), chosen_by_rule=chosen,
                      tool_matches_rule=res["tool_matches_rule"],
                      at_chosen={k: summ[k][str(chosen[k])] for k in chosen if chosen[k] is not None}, seconds=res["seconds"]))


# ====================================================================== one stitched frame
def stitch_frame(nest_path, parent_path, seam=SEAM, with_n3=True):
    """-> (record bytes, row dict). See STITCH_RULE."""
    t0 = time.time()
    dn, dp = read_srf(nest_path), read_srf(parent_path)
    if dn["frame"] != dp["frame"] or abs(dn["t"] - dp["t"]) > 1e-9:
        raise ValueError("frame / time differ: nest %s %s, parent %s %s" % (dn["frame"], dn["t"], dp["frame"], dp["t"]))
    off = dp["off"]
    mn, mp = Mesh(dn, dn["off"]), Mesh(dp, off)
    Tn = clip_nest(mn, seam)
    Tp = clip_parent(mp, seam)
    # compact each side
    def compact(m, T):
        used = np.unique(T.ravel()) if len(T) else np.zeros(0, np.int64)
        remap = -np.ones(len(m.P), np.int64); remap[used] = np.arange(len(used))
        return m.P[used].copy(), m.V[used].copy(), m.N[used].copy(), m.vis_v[used].copy(), remap[T]
    Pn, Vn, Nn, visn, Tn = compact(mn, Tn)
    Pp, Vp, Np_, visp, Tp = compact(mp, Tp)
    cn = top_chain(Pn, Tn, visn, seam)
    cp = top_chain(Pp, Tp, visp, seam)
    # seam mismatch at the nest chain's vertices (before the blend) and on a regular s grid
    L = path_len(seam)
    sq = np.arange(0.0, L + 1e-9, SAMPLE_DS)
    hn_q, hp_q = _edge_height(cn, sq) if len(cn["edges"]) else np.full(len(sq), np.nan), _edge_height(cp, sq) if len(cp["edges"]) else np.full(len(sq), np.nan)
    okq = np.isfinite(hn_q) & np.isfinite(hp_q)
    dzq = (hp_q - hn_q)[okq]
    segq = np.where(sq[okq] <= seam["y_s"], 0, np.where(sq[okq] <= seam["y_s"] + seam["x_e"] - seam["x_s"], 1, 2))
    seg_stats = {}
    for k_, nm in enumerate(("X", "Y", "E")):
        z = dzq[segq == k_]
        seg_stats[nm] = dict(n=int(len(z)), mean=float(z.mean()) if len(z) else None, rms=float(np.sqrt((z ** 2).mean())) if len(z) else None,
                             max_abs=float(np.abs(z).max()) if len(z) else None)
    # blend (nest vertices of the visible pieces within blend_m of the seam)
    dz_v = _edge_height(cp, cn["s"]) - cn["z"] if len(cn["v"]) and len(cp["edges"]) else np.zeros(len(cn["v"]))
    dz_v = np.where(np.isfinite(dz_v), dz_v, 0.0)
    capped = int((np.abs(dz_v) > seam["cap_m"]).sum())
    dz_v = np.clip(dz_v, -seam["cap_m"], seam["cap_m"])
    moved = 0
    if len(cn["v"]):
        d, sv = nearest_on_path(Pn[:, 0], Pn[:, 2], seam)
        order0 = np.argsort(cn["s"])
        top_at = np.interp(sv, cn["s"][order0], cn["z"][order0])
        sel = visn & (d < seam["blend_m"]) & (Pn[:, 1] >= top_at - BLEND_DEPTH_M)
        u = np.clip(1.0 - d[sel] / seam["blend_m"], 0.0, 1.0)
        w = u * u * (3 - 2 * u)
        order = np.argsort(cn["s"])
        Pn[sel, 1] += w * np.interp(sv[sel], cn["s"][order], dz_v[order])
        moved = int(sel.sum())
        # the chain vertices themselves: exactly onto the parent's chain (w = 1)
        Pn[cn["v"], 1] = cn["z"] + dz_v
    # merge + zipper
    off_n = len(Pp)
    P = np.vstack([Pp, Pn]); V = np.vstack([Vp, Vn]); N = np.vstack([Np_, Nn])
    T = np.vstack([Tp, Tn + off_n])
    zips, zlen = [], 0.0
    iv = intersect_intervals(cn["intervals"], cp["intervals"])
    dir_n = {(u + off_n, w_ + off_n): 1 for (u, w_) in (cn.get("dirs") or {})}
    dir_p = dict(cp.get("dirs") or {})
    for lo, hi in iv:
        a_sel = (cn["s"] >= lo - 1e-6) & (cn["s"] <= hi + 1e-6)
        b_sel = (cp["s"] >= lo - 1e-6) & (cp["s"] <= hi + 1e-6)
        if a_sel.sum() < 1 or b_sel.sum() < 1 or (a_sel.sum() + b_sel.sum()) < 3:
            continue
        zt = zipper(cn["v"][a_sel] + off_n, cn["s"][a_sel], cp["v"][b_sel], cp["s"][b_sel], dir_n, dir_p)
        zips += zt
        zlen += hi - lo
    Tz = np.array(zips, np.int64).reshape(-1, 3)
    # strip quality after the blend: the nest chain (linear in s) against the parent chain at the PARENT chain's vertices (the widest gap
    # the zipper strip covers between two nest vertices; 0 where the chains coincide) and at the nest chain's own vertices (0 unless capped)
    zgap, zgap_v = 0.0, 0.0
    if len(cn["v"]) > 1 and len(cp["v"]):
        cn2 = dict(cn, z=Pn[cn["v"], 1])
        hn2 = _edge_height(cn2, cp["s"])
        okg = np.isfinite(hn2)
        zgap = float(np.abs(hn2[okg] - cp["z"][okg]).max()) if okg.any() else 0.0
        hp2 = _edge_height(cp, cn["s"])
        okv = np.isfinite(hp2)
        zgap_v = float(np.abs(hp2[okv] - Pn[cn["v"], 1][okv]).max()) if okv.any() else 0.0
    T_all = np.vstack([T, Tz]) if len(Tz) else T
    b, qerr = srf_bytes(dp["t"], dp["frame"], off, P, N, V, T_all)
    info_n3 = None
    if with_n3:
        b, info_n3 = load_n3().n3_bytes(b)
    cov_n = sum(h - l for l, h in cn["intervals"]); cov_p = sum(h - l for l, h in cp["intervals"])
    row = dict(frame=int(dp["frame"]), t=float(dp["t"]), nv=int(len(P)), nt=int(len(T_all)), nt_zip=int(len(Tz)), bytes=len(b), qerr_m=qerr,
               nest=dict(nv_in=int(len(Pn)), nt_in=int(len(Tn)), chain_v=int(len(cn["v"])), chain_cover_m=cov_n, multi_frac=cn["multi_frac"]),
               parent=dict(nv_out=int(len(Pp)), nt_out=int(len(Tp)), chain_v=int(len(cp["v"])), chain_cover_m=cov_p, multi_frac=cp["multi_frac"]),
               seam=dict(path_m=L, zipped_m=zlen, open_m=max(0.0, L - zlen), n=int(okq.sum()), mean=float(dzq.mean()) if len(dzq) else None,
                         rms=float(np.sqrt((dzq ** 2).mean())) if len(dzq) else None, p95_abs=float(np.percentile(np.abs(dzq), 95)) if len(dzq) else None,
                         max_abs=float(np.abs(dzq).max()) if len(dzq) else None, segments=seg_stats, capped_chain_v=capped, blend_moved_v=moved,
                         gap_after_blend_at_parent_v_m=zgap, gap_after_blend_at_nest_v_m=zgap_v),
               n3=None if info_n3 is None else {k: info_n3.get(k) for k in ("orient_agree", "n_seam_v", "n_nonmanifold_e", "n3_vs_geometric_visible_deg")},
               s=round(time.time() - t0, 3))
    return b, row


def open_seam_edges(d, seam, tol=1e-4):
    """verify: boundary edges of the stitched record's visible pieces that lie on the seam path (a crack the zipper did not close)."""
    vt = vis_tris(d)
    T = d["T"]
    lab, cmax = components_max(d["P"], T, len(d["P"]))
    vis_v = (cmax[lab] - d["off"]) >= FREE_EMAX
    E = boundary_edges(T, len(d["P"]))
    s = path_s(d["P"], seam, tol=max(tol, float(np.max(d["qstep"])) * 1.01))
    on0 = np.isfinite(s[E[:, 0]]) & np.isfinite(s[E[:, 1]]) & vis_v[E[:, 0]] & vis_v[E[:, 1]] & (np.abs(s[E[:, 0]] - s[E[:, 1]]) > 1e-9)
    hi = np.maximum(d["P"][E[:, 0], 1], d["P"][E[:, 1], 1]) - d["off"] >= OPEN_EMIN
    deep_len = float(np.abs(s[E[on0 & ~hi, 0]] - s[E[on0 & ~hi, 1]]).sum())
    on = on0 & hi
    Ln = float(np.abs(s[E[on, 0]] - s[E[on, 1]]).sum())
    zmax = float(np.maximum(d["P"][E[on, 0], 1], d["P"][E[on, 1], 1]).max() - d["off"]) if on.any() else None
    sm = 0.5 * (s[E[on, 0]] + s[E[on, 1]]); L = np.abs(s[E[on, 0]] - s[E[on, 1]])
    seg = np.where(sm <= seam["y_s"], 0, np.where(sm <= seam["y_s"] + seam["x_e"] - seam["x_s"], 1, 2))
    by = {nm: float(L[seg == k].sum()) for k, nm in enumerate(("X", "Y", "E"))}
    return dict(n=int(on.sum()), length_m=Ln, by_segment_m=by, highest_above_still_m=zmax, vis_tris=int(vt.sum()), deep_len_m=deep_len)


# ====================================================================== stitch / verify commands
def frames_avail(nest_rd, f0, f1):
    fn = set(int(os.path.basename(p)[2:7]) for p in glob.glob(nest_rd + "/surf/s_*.gw45s"))
    fp = set(int(os.path.basename(p)[2:7]) for p in glob.glob(PARENT_RUN + "/surf/s_*.gw45s"))
    return sorted(f for f in fn & fp if f0 <= f <= f1), sorted(f for f in range(f0, f1 + 1) if f not in fn), sorted(f for f in range(f0, f1 + 1) if f not in fp)


def _work(args):
    f, nest_rd, out = args
    try:
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)      # below normal
        except Exception:
            pass
        b, row = stitch_frame(surf_path(nest_rd, f), surf_path(PARENT_RUN, f))
        p = out + "/surf/s_%05d.gw45s" % f
        guard(p)
        tmp = p + ".part"
        with open(tmp, "wb") as fh:
            fh.write(b)
        os.replace(tmp, p)
        row["sha256"] = hashlib.sha256(b).hexdigest()
        return row
    except Exception as e:
        import traceback
        return dict(frame=f, error="%s: %s" % (type(e).__name__, str(e)[:300]), traceback=traceback.format_exc()[-800:])


def read_rows(out):
    rows = {}
    p = out + "/rows.jsonl"
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            try:
                r = json.loads(ln)
                rows[int(r["frame"])] = r
            except Exception:
                pass
    return rows


def cmd_stitch(o):
    t0 = time.time()
    sim = "simulate" in o
    nest_rd = o.get("nest", C2_RUN if sim else C2H_RUN)
    out = o.get("out", SIM_OUT if sim else OUT_DEF)
    f0, f1 = int(o.get("from", F_FIRST)), int(o.get("to", F_LAST))
    if sim:
        f0, f1 = int(o.get("from", 1321)), int(o.get("to", 1330))
    fr, miss_n, miss_p = frames_avail(nest_rd, f0, f1)
    if not sim and (miss_n or miss_p):
        return final(dict(ok=False, step="stitch", why="surface records missing: nest %d (first %s), parent %d (first %s)" % (
            len(miss_n), miss_n[:5], len(miss_p), miss_p[:5]), nest=rel(nest_rd)))
    rows = read_rows(out)
    todo = [f for f in fr if not (f in rows and not rows[f].get("error") and os.path.exists(out + "/surf/s_%05d.gw45s" % f)
                                  and os.path.getsize(out + "/surf/s_%05d.gw45s" % f) == rows[f].get("bytes"))]
    meta = dict(date=now(), tool=TOOL, tool_sha256=sha(os.path.abspath(__file__)), seam=SEAM, rule=STITCH_RULE, nest_run=rel(nest_rd), parent_run=rel(PARENT_RUN),
                frames=[f0, f1], label=LABEL, display=DISPLAY_EN, n3_tool=rel(N3_TOOL), n3_tool_sha256=sha(N3_TOOL), simulate=sim,
                seamscan=rel(SCAN_JSON), seamscan_sha256=sha(SCAN_JSON))
    jdump(meta, out + "/stitch_meta.json")
    workers = int(o.get("workers", "4"))
    done, errs = 0, []
    rp = guard(out + "/rows.jsonl")
    if todo:
        if workers > 1 and len(todo) > 4:
            from multiprocessing import Pool
            with Pool(workers) as pool, open(rp, "a", encoding="utf-8") as fh:
                for row in pool.imap_unordered(_work, [(f, nest_rd, out) for f in todo], chunksize=4):
                    fh.write(json.dumps(clean(row), ensure_ascii=False) + "\n"); fh.flush()
                    done += 1
                    if row.get("error"):
                        errs.append(row)
                    if done % 100 == 0:
                        print(now(), "stitched %d / %d (%.0f s)" % (done, len(todo), time.time() - t0), flush=True)
        else:
            with open(rp, "a", encoding="utf-8") as fh:
                for f in todo:
                    row = _work((f, nest_rd, out))
                    fh.write(json.dumps(clean(row), ensure_ascii=False) + "\n"); fh.flush()
                    done += 1
                    if row.get("error"):
                        errs.append(row)
    rows = read_rows(out)
    good = [rows[f] for f in fr if f in rows and not rows[f].get("error")]
    rms = [r["seam"]["rms"] for r in good if r["seam"]["rms"] is not None]
    mx = [r["seam"]["max_abs"] for r in good if r["seam"]["max_abs"] is not None]
    return final(dict(ok=bool(not errs and len(good) == len(fr) and (sim or len(fr) == f1 - f0 + 1)), step="stitch", simulate=sim, out=rel(out),
                      frames=[f0, f1], n_frames=len(fr), n_done_now=done, n_ok=len(good), errors=[(e["frame"], e["error"]) for e in errs[:5]],
                      seam_rms_m=dict(median=float(np.median(rms)) if rms else None, max=float(max(rms)) if rms else None),
                      seam_max_abs_m=float(max(mx)) if mx else None, seconds=round(time.time() - t0, 1)))


def cmd_verify(o):
    t0 = time.time()
    out = o.get("out", OUT_DEF)
    f0, f1 = int(o.get("from", F_FIRST)), int(o.get("to", F_LAST))
    rows = read_rows(out)
    files = sorted(int(os.path.basename(p)[2:7]) for p in glob.glob(out + "/surf/s_*.gw45s"))
    want = [f for f in range(f0, f1 + 1)] if "simulate" not in o else files
    miss = [f for f in want if f not in set(files)]
    bad, opn, nvmax, ntmax, nvmin, ntmin, unit = [], [], 0, 0, 1 << 40, 1 << 40, 0.0
    per = []
    step = int(o.get("step", "1"))
    for f in [f for f in want if f in set(files)][::step]:
        p = out + "/surf/s_%05d.gw45s" % f
        try:
            d = read_srf(p)
        except Exception as e:
            bad.append((f, "unreadable %r" % e)); continue
        ok = (d["frame"] == f and abs(d["t"] - t_of(f)) < 1e-6 and np.isfinite(d["P"]).all() and (len(d["T"]) == 0 or int(d["T"].max()) < len(d["P"]))
              and np.isfinite(d["V"]).all())
        r = rows.get(f) or {}
        if r.get("sha256") and r["sha256"] != sha(p):
            ok = False
        if not ok:
            bad.append((f, "header / finite / index / sha"))
        unit = max(unit, float(np.abs(np.linalg.norm(d["N"], axis=1) - 1).max()) if len(d["N"]) else 0.0)
        oe = open_seam_edges(d, SEAM)
        opn.append((f, oe["n"], oe["length_m"], oe["by_segment_m"], oe["deep_len_m"]))
        nvmax, ntmax = max(nvmax, len(d["P"])), max(ntmax, len(d["T"]))
        nvmin, ntmin = min(nvmin, len(d["P"])), min(ntmin, len(d["T"]))
        per.append(dict(frame=f, open_visible_seam_edges=oe["n"], open_len_m=oe["length_m"], open_by_segment_m=oe["by_segment_m"],
                        seam_rms=(r.get("seam") or {}).get("rms"),
                        seam_max=(r.get("seam") or {}).get("max_abs")))
    rms = [x["seam_rms"] for x in per if x["seam_rms"] is not None]
    mx = [x["seam_max"] for x in per if x["seam_max"] is not None]
    worst = max(per, key=lambda x: x["seam_max"] or 0.0) if per else None
    res = dict(date=now(), tool=TOOL, step="verify", out=rel(out), frames=[f0, f1], n_files=len(files), missing=miss[:50], n_missing=len(miss),
               bad=bad[:20], n_bad=len(bad), normal_unit_err_max=unit, vert_max=nvmax, tri_max=ntmax, vert_min=nvmin, tri_min=ntmin,
               open_visible_seam_edges_max=max([x[1] for x in opn] or [0]), open_visible_seam_len_max_m=max([x[2] for x in opn] or [0.0]),
               open_len_max_by_segment_m={k: max([x[3][k] for x in opn] or [0.0]) for k in ("X", "Y", "E")},
               open_note=("open = boundary edges on the seam path, reaching above still - 2.5 m, of the pieces that reach above still - 1 m, "
                          "that the zipper did not join: lower layers of a multi-valued cut (a thin swash film on the beach, a fold); the top surface "
                          "is joined everywhere both chains exist; deeper open edges (the hidden bed skin, -15 .. -3 m) are reported as deep_len_m"),
               deep_open_len_max_m=max([x[4] for x in opn] or [0.0]),
               seam_rms_m=dict(median=float(np.median(rms)) if rms else None, p95=float(np.percentile(rms, 95)) if rms else None, max=float(max(rms)) if rms else None),
               seam_max_abs_m=float(max(mx)) if mx else None, seam_worst_frame=worst, per_frame=per, seam=SEAM, label=LABEL,
               expect=("seam rms of the order of C2ID's GN2 0.155 m (GN2 tol 0.402 m); open visible seam edges only where a top chain is missing "
                       "on one side (reported, e.g. a dry beach)"), seconds=round(time.time() - t0, 1),
               tags=dict(all="measured on the stitched records"))
    res["ok"] = bool(not miss and not bad and unit < 1e-3 and per)
    jdump(res, out + "/stitch_verify.json")
    return final(dict(ok=res["ok"], step="verify", out=rel(out + "/stitch_verify.json"), n_files=len(files), n_missing=len(miss), n_bad=len(bad),
                      vert_max=nvmax, tri_max=ntmax, open_visible_seam_edges_max=res["open_visible_seam_edges_max"],
                      open_visible_seam_len_max_m=res["open_visible_seam_len_max_m"], open_len_max_by_segment_m=res["open_len_max_by_segment_m"],
                      seam_rms_m=res["seam_rms_m"], seam_max_abs_m=res["seam_max_abs_m"],
                      seconds=res["seconds"]))


# ====================================================================== selftest (synthetic + one real C2 frame)
def synth_mesh(fn, x0, x1, y0, y1, h, off=STILL, frame=1500, deep=True):
    """a regular triangulated height field z = fn(x, y) on [x0, x1] x [y0, y1] spacing h (+ a separate deep skin at -10 m)."""
    xs = np.arange(x0, x1 + 1e-9, h); ys = np.arange(y0, y1 + 1e-9, h)
    X, Y = np.meshgrid(xs, ys)
    P = np.stack([X.ravel(), fn(X, Y).ravel(), Y.ravel()], 1)
    nx = len(xs)
    T = []
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            a = j * nx + i
            T += [(a, a + nx, a + 1), (a + 1, a + nx, a + nx + 1)]
    T = np.array(T, np.int64)
    if deep:
        Q = P.copy(); Q[:, 1] = -10.0
        T2 = T + len(P)
        P = np.vstack([P, Q]); T = np.vstack([T, T2])
    N = np.tile([0.0, 1.0, 0.0], (len(P), 1)); V = np.zeros_like(P)
    return dict(t=t_of(frame), frame=frame, off=off, P=P, N=N, V=V, T=T)


def tri_area(P, T):
    return 0.5 * np.linalg.norm(np.cross(P[T[:, 1]] - P[T[:, 0]], P[T[:, 2]] - P[T[:, 0]]), axis=1)


def selftest():
    ck, info = {}, {}
    seam = dict(SEAM)
    # 1. split conserves area and puts the cut on the plane
    d = synth_mesh(lambda X, Y: 0.3 * np.sin(X / 3.1) + 0.2 * np.cos(Y / 2.3), 175.0, 360.0, 0.0, 50.0, 0.7, deep=False)
    m = Mesh(d, d["off"])
    a0 = tri_area(m.P, m.T).sum()
    Tn = clip_nest(m, seam)
    m2 = Mesh(d, d["off"])
    Tp = clip_parent(m2, seam)
    an, ap = tri_area(m.P, Tn).sum(), tri_area(m2.P, Tp).sum()
    ck["split_area_conserved"] = bool(abs(an + ap - a0) < 1e-6 * a0)
    xs_, la_ = m.P[np.unique(Tn.ravel()), 0], m.P[np.unique(Tn.ravel()), 2]
    ck["nest_inside_R"] = bool(xs_.min() >= seam["x_s"] - 1e-9 and xs_.max() <= seam["x_e"] + 1e-9 and la_.max() <= seam["y_s"] + 1e-9)
    pp = m2.P[np.unique(Tp.ravel())]
    cen = m2.P[Tp].mean(1)
    ck["parent_outside_R"] = bool(not ((cen[:, 0] > seam["x_s"] + 1e-6) & (cen[:, 0] < seam["x_e"] - 1e-6) & (cen[:, 2] < seam["y_s"] - 1e-6)).any())
    # 2. a full stitch of two synthetic records (nest = parent + small offset): no open visible seam edge, mismatch = the offset
    fp = lambda X, Y: 0.8 * np.sin(X / 7.0 + Y / 11.0)
    fnest = lambda X, Y: fp(X, Y) - 0.05 + 0.03 * np.sin(X * 2.1) * np.cos(Y * 1.7)
    os.makedirs(SELFTEST_OUT, exist_ok=True)
    pn, ppth = SELFTEST_OUT + "/synth_nest.gw45s", SELFTEST_OUT + "/synth_parent.gw45s"
    dn = synth_mesh(fnest, 179.9, 356.1, 0.0, 45.4, 0.25)
    dp_ = synth_mesh(fp, 0.0, 381.0, 0.0, 97.5, 0.5)
    for p_, dd in ((pn, dn), (ppth, dp_)):
        b_, _ = srf_bytes(dd["t"], dd["frame"], dd["off"], dd["P"], dd["N"], dd["V"], dd["T"])
        with open(guard(p_), "wb") as fh:
            fh.write(b_)
    b, row = stitch_frame(pn, ppth, seam, with_n3=True)
    with open(guard(SELFTEST_OUT + "/synth_stitched.gw45s"), "wb") as fh:
        fh.write(b)
    ds = read_srf(SELFTEST_OUT + "/synth_stitched.gw45s")
    oe = open_seam_edges(ds, seam)
    info["synthetic"] = dict(row=row, open=oe)
    ck["synthetic_no_open_visible_seam"] = bool(oe["n"] == 0)
    ck["synthetic_mismatch_measured"] = bool(row["seam"]["rms"] is not None and 0.02 <= abs(row["seam"]["mean"]) <= 0.09)
    ck["synthetic_zip_closed"] = bool(row["seam"]["gap_after_blend_at_nest_v_m"] < 1e-6 and row["seam"]["gap_after_blend_at_parent_v_m"] < 0.02)
    ck["synthetic_readback_counts"] = bool(len(ds["P"]) == row["nv"] and len(ds["T"]) == row["nt"])
    ck["synthetic_normals_unit"] = bool(np.abs(np.linalg.norm(ds["N"], axis=1) - 1).max() < 1e-3)
    # the hero region (x 200-300, lateral <= 20) is untouched by the blend
    sel = (ds["P"][:, 0] > 200) & (ds["P"][:, 0] < 300) & (ds["P"][:, 2] < 20) & (ds["P"][:, 1] > -5)
    ck["hero_region_untouched"] = bool(np.abs(ds["P"][sel, 1] - fnest(ds["P"][sel, 0], ds["P"][sel, 2])).max() < 0.01)
    # 3. one REAL frame: C2's record (0.25 m, f1456 = its print-like instant) with the parent's same frame
    real = {}
    for f in (1456, 1321):
        p_n, p_p = surf_path(C2_RUN, f), surf_path(PARENT_RUN, f)
        if os.path.exists(p_n) and os.path.exists(p_p):
            b, row = stitch_frame(p_n, p_p, seam)
            q = SELFTEST_OUT + "/real_C2_s_%05d.gw45s" % f
            with open(guard(q), "wb") as fh:
                fh.write(b)
            dr = read_srf(q)
            oe = open_seam_edges(dr, seam)
            # the hero region of the stitched record equals the nest record there (positions within one quantisation step)
            dn_ = read_srf(p_n)
            from scipy.spatial import cKDTree
            reg = lambda P_: (P_[:, 0] > 200) & (P_[:, 0] < 300) & (P_[:, 2] < 20)
            dist, _ = cKDTree(dn_["P"]).query(dr["P"][reg(dr["P"])])
            real[f] = dict(row=row, open=oe, hero_region_nn_max_m=float(dist.max()), qstep_m=float(np.max(dr["qstep"])), file=rel(q))
    info["real"] = real
    if real:
        ck["real_frames_stitched"] = True
        ck["real_open_visible_seam_small"] = bool(all(r["open"]["length_m"] <= 0.05 * path_len(seam) for r in real.values()))
        ck["real_hero_region_unchanged"] = bool(all(r["hero_region_nn_max_m"] <= 2.0 * max(r["qstep_m"], 0.006) + 0.01 for r in real.values()))
    res = dict(date=now(), tool=TOOL, step="selftest", checks=ck, info=info, ok=bool(all(ck.values())), label=LABEL)
    jdump(res, SELFTEST_OUT + "/selftest.json")
    return final(dict(ok=res["ok"], step="selftest", checks=ck, out=rel(SELFTEST_OUT + "/selftest.json"),
                      real={f: dict(seam_rms=r["row"]["seam"]["rms"], seam_mean=r["row"]["seam"]["mean"], seam_max=r["row"]["seam"]["max_abs"],
                                    open_m=r["open"]["length_m"], open_edges=r["open"]["n"], zipped_m=r["row"]["seam"]["zipped_m"],
                                    nv=r["row"]["nv"], s=r["row"]["s"], hero_nn=r["hero_region_nn_max_m"]) for f, r in real.items()}))


def cmd_status(o):
    out = o.get("out", OUT_DEF)
    rows = read_rows(out)
    files = glob.glob(out + "/surf/s_*.gw45s")
    v = jload(out + "/stitch_verify.json") or {}
    return final(dict(ok=True, step="status", out=rel(out), files=len(files), rows=len(rows), errors=len([r for r in rows.values() if r.get("error")]),
                      verify_ok=v.get("ok"), seamscan=bool(os.path.exists(SCAN_JSON)), seam=SEAM, tool_sha256=sha(os.path.abspath(__file__))))


def main(argv):
    if not argv:
        print(__doc__)
        return 1
    pos, o = opts(argv[1:])
    cmd = argv[0]
    try:
        if cmd == "seamscan":
            return cmd_seamscan(o)
        if cmd == "selftest":
            return selftest()
        if cmd == "stitch":
            return cmd_stitch(o)
        if cmd == "verify":
            return cmd_verify(o)
        if cmd == "status":
            return cmd_status(o)
    except SystemExit as e:
        if isinstance(e.code, int) or e.code is None:
            raise
        return final(dict(ok=False, step=cmd, why=str(e.code)[:600]))
    except Exception as e:
        import traceback
        return final(dict(ok=False, step=cmd, why="%s: %s" % (type(e).__name__, str(e)[:400]), traceback=traceback.format_exc()[-1500:]))
    print(__doc__)
    return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
