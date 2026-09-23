"""G1-G5: mesh tests (spec sections 7 and 9).  Stand-alone, headless:

  blender --background --factory-startup --python-exit-code 1 [file.blend] --python tests/test_mesh.py -- --object <name>
          [--blend <path>] [--build-script <py> [--build-func f] [--build-arg k=v ...]]
          [--frame-start A] [--final-frame N] [--skip G5] [--g5-mode both|inprocess|subprocess]
(--python-exit-code 1 is REQUIRED for direct calls; exceptions inside main() end as verdict ERROR, exit code 2.)

  G1 constant topology + UVs on every frame          G2 hem (mesh boundary) on the still-water plane
  G3 rim thickness near the vertex group 'crest_rim'  G4 no self-intersection (final + every 15th frame)
  G5 two rebuilds from the same parameters give bit-identical vertices (needs --build-script)

Thresholds come ONLY from tests/thresholds.json; both tiers are reported.  The precise definitions
(G3 and G4 contain INTERPRETATIONS) are in docs/tests_readme.md and in metrics.json.
Output: results/<YYYYMMDD_HHMMSS>_mesh/ metrics.json, summary.md, g3_sections.png, g2_hem.png,
g4_intersections.png (only when there are any).

Verdict: a skipped test (--skip, or G5 without --build-script) is NOT judged, so the verdict is INCOMPLETE, never PASS;
an unknown name in --skip is an ERROR.  A non-finite vertex of the evaluated mesh on any frame -> INVALID.
REPORT ONLY (no verdict): G1.max_vertex_step_H, G1.n_vertices (next to the 85,120 of the existing Unity cache),
G1.uv_u_abs_cos_to_crest_line / G1.uv_v_abs_cos_to_crest_line / G1.uv_u_starts_at_back_hem (spec section 7: U along the
section from the hem of the back to the trough, V along the crest line).
"""
import argparse
import math
import os
import subprocess
import sys

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import common_test as ct  # noqa: E402
from common_test import bootstrap, draw, imgio, paths, plot, pm, silhouette, log  # noqa: E402

TEST_NAME = "mesh"
RIM_GROUP = "crest_rim"
G_IDS = ("G1", "G2", "G3", "G4", "G5")
UNITY_CACHE_VERTICES = 85120          # spec section 7: size of the existing Unity cache (reference, not a limit)


def uv_orientation(arr):
    """REPORT ONLY.  Orientation of the first UV layer on the evaluated mesh of one frame (spec section 7: U along the
    section contour hem of the back -> crest -> head tip -> belly -> trough, V along the crest line = world Y).
    Per loop triangle the world-space derivatives dP/dU and dP/dV are computed from the UVs; reported are the area-weighted
    means of |cos| between each of them and the Y axis (U inside the section planes -> 0; V along the crest line -> 1) and
    whether U starts at the back (mean X of the loops with the smallest U < mean X of those with the largest U).
    -> dict or None (no UV layer)"""
    layers = arr.get("uv_layers") or {}
    if not layers:
        return None
    name = sorted(layers)[0]
    uv = layers[name].astype(np.float64)
    co, tl, lv = arr["co_world"], arr["tri_loops"], arr["loop_vert"]
    P = co[lv[tl]]                                             # (m, 3, 3)
    T = uv[tl]                                                 # (m, 3, 2)
    e1, e2 = P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]
    d1, d2 = T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]
    det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    area = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    ok = np.isfinite(det) & (np.abs(det) > 1e-14) & np.isfinite(area) & (area > 0)
    if not ok.any():
        return {"layer": name, "n_triangles_used": 0}
    with np.errstate(divide="ignore", invalid="ignore"):
        dPdU = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / det[:, None]
        dPdV = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / det[:, None]
        cu = np.abs(dPdU[:, 1]) / np.linalg.norm(dPdU, axis=1)
        cv = np.abs(dPdV[:, 1]) / np.linalg.norm(dPdV, axis=1)
        sv = np.sign(dPdV[:, 1])
    ok &= np.isfinite(cu) & np.isfinite(cv)
    w = area[ok] / area[ok].sum()
    x_loop = co[lv, 0]
    u = uv[:, 0]
    fin = np.isfinite(u) & np.isfinite(x_loop)
    lo, hi = np.percentile(u[fin], 2.0), np.percentile(u[fin], 98.0)
    x_lo, x_hi = float(x_loop[fin & (u <= lo)].mean()), float(x_loop[fin & (u >= hi)].mean())
    return {"layer": name, "n_triangles_used": int(ok.sum()), "n_triangles": int(tl.shape[0]),
            "u_abs_cos_to_y": float((cu[ok] * w).sum()), "v_abs_cos_to_y": float((cv[ok] * w).sum()),
            "v_increases_with_y_share": float((w * (sv[ok] > 0)).sum()),
            "u_range": [float(u[fin].min()), float(u[fin].max())], "v_range": [float(uv[fin, 1].min()), float(uv[fin, 1].max())],
            "mean_x_at_smallest_u_m": x_lo, "mean_x_at_largest_u_m": x_hi, "u_starts_at_back_hem": bool(x_lo < x_hi)}


def add_args(ap):
    g = ap.add_argument_group("mesh")
    g.add_argument("--skip", default="", help="comma separated list of tests to skip, e.g. G5")
    g.add_argument("--g5-mode", default="both", choices=["both", "inprocess", "subprocess"],
                   help="rebuild in a reset scene of this process, in a fresh Blender process, or both (default)")
    g.add_argument("--dump-verts", default=None, help="(internal, used by G5) build, write the vertex arrays of --frames to this .npz and exit")
    g.add_argument("--frames", default=None, help="(internal) comma separated frames for --dump-verts")
    return ap


# ------------------------------------------------------------------------------------ G3: sections
def mesh_section(co, tris, y0, in_group=None):
    """Intersection of a triangle mesh with the plane Y = y0.  Vertices with y == y0 count as y > y0,
    so the plane never passes exactly through a vertex.  -> list of chains, each a dict
    {pts (n, 2) world (X, Z), rim (n,) bool, closed}; a node is 'rim' when both vertices of the crossed
    mesh edge belong to the vertex group."""
    nv = co.shape[0]
    side = co[:, 1] >= y0
    ts = side[tris]
    cnt = ts.sum(axis=1)
    sel = (cnt == 1) | (cnt == 2)
    if not sel.any():
        return []
    T, Sd, c = tris[sel].astype(np.int64), ts[sel], cnt[sel]
    lone = np.where(c == 1, Sd.argmax(axis=1), (~Sd).argmax(axis=1))
    r = np.arange(T.shape[0])
    a, b, d = T[r, lone], T[r, (lone + 1) % 3], T[r, (lone + 2) % 3]

    def node(u, v):
        lo, hi = np.minimum(u, v), np.maximum(u, v)
        t = (y0 - co[lo, 1]) / (co[hi, 1] - co[lo, 1])
        p = co[lo] + t[:, None] * (co[hi] - co[lo])
        return lo * nv + hi, p[:, [0, 2]], lo, hi

    k1, p1, l1, h1 = node(a, b)
    k2, p2, l2, h2 = node(a, d)
    keys, first, inv = np.unique(np.concatenate([k1, k2]), return_index=True, return_inverse=True)
    pos = np.concatenate([p1, p2])[first]
    lo_all, hi_all = np.concatenate([l1, l2])[first], np.concatenate([h1, h2])[first]
    rim = np.zeros(len(keys), bool) if in_group is None else (in_group[lo_all] & in_group[hi_all])
    n1, n2 = inv[:len(k1)], inv[len(k1):]
    adj = [[] for _ in range(len(keys))]
    for i, j in zip(n1.tolist(), n2.tolist()):
        if i != j:
            adj[i].append(j)
            adj[j].append(i)
    visited = np.zeros(len(keys), bool)
    chains = []
    order = [i for i in range(len(keys)) if len(adj[i]) == 1] + list(range(len(keys)))
    for st in order:
        if visited[st] or not adj[st]:
            continue
        path, prev, cur = [st], -1, st
        visited[st] = True
        while True:
            nxt = [q for q in adj[cur] if q != prev and not visited[q]]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            visited[cur] = True
            path.append(cur)
        idx = np.asarray(path)
        chains.append({"pts": pos[idx], "rim": rim[idx], "closed": len(adj[st]) != 1})
    return chains


def inscribed_diameter(C, s_q, w, excl, ds):
    """Diameter of the largest circle that touches curve C at C(s_q) from the body side (the right-hand
    side when walking along C) without crossing C.  -> (diameter, touching point, centre) in curve units."""
    q = C.at(s_q)
    a, b = C.at(max(0.0, s_q - w)), C.at(min(C.length, s_q + w))
    t = b - a
    L = math.hypot(t[0], t[1])
    if L <= 0:
        return None, None, None
    t = t / L
    nrm = np.array([t[1], -t[0]])
    n = max(2, int(math.ceil(C.length / ds)) + 1)
    ss = np.linspace(0.0, C.length, n)
    P = C.at(ss)
    far = np.abs(ss - s_q) > excl
    dv = P - q
    dn = dv @ nrm
    ok = far & (dn > 1e-12)
    if not ok.any():
        return None, None, None
    rho = (dv[ok] ** 2).sum(axis=1) / (2.0 * dn[ok])
    k = int(np.argmin(rho))
    return float(2.0 * rho[k]), P[ok][k], q + rho[k] * nrm


def rim_thickness(ctx, arr, tip_cam_H, S):
    """G3 on the current frame.  -> (judged value in % of H or None, details dict, drawable sections)"""
    obj, H = ctx.obj, ctx.H
    vg = obj.vertex_groups.get(RIM_GROUP)
    if vg is None:
        return None, {"error": "vertex group '%s' does not exist" % RIM_GROUP}, []
    gi = vg.index
    in_group = np.zeros(arr["n_vertices"], bool)
    for v in obj.data.vertices:
        for g in v.groups:
            if g.group == gi and g.weight > 0.0:
                in_group[v.index] = True
                break
    if len(obj.data.vertices) != arr["n_vertices"]:
        return None, {"error": "evaluated mesh has %d vertices but the base mesh (which carries the vertex group) has %d"
                               % (arr["n_vertices"], len(obj.data.vertices))}, []
    if not in_group.any():
        return None, {"error": "vertex group '%s' is empty" % RIM_GROUP}, []
    co = arr["co_world"]
    yg = co[in_group, 1]
    p_lo, p_hi = [float(v) for v in S["g3_y_percentiles"]]
    ys = np.linspace(np.percentile(yg, p_lo), np.percentile(yg, p_hi), int(S["g3_n_sections"]))
    w = float(S["g3_normal_window_pct_H"]) / 100.0
    excl = float(S["g3_exclude_pct_H"]) / 100.0
    offs = [float(v) / 100.0 for v in S["g3_probe_offsets_pct_H"]]
    match = float(pm.pct_h_to_H(S["g3_tip_match_pct_h"]))
    sections, drawable = [], []
    for y0 in ys:
        rec = {"y_m": float(y0), "judged": False}
        chains = mesh_section(co, arr["tris"], float(y0), in_group)
        chains = [c for c in chains if c["pts"].shape[0] >= 3]
        if not chains:
            rec["note"] = "no section"
            sections.append(rec)
            continue
        lens = [float(np.hypot(*np.diff(c["pts"], axis=0).T).sum()) for c in chains]
        ch = chains[int(np.argmax(lens))]
        pts, rim = ch["pts"].copy(), ch["rim"].copy()
        if pts[0, 0] > pts[-1, 0]:
            pts, rim = pts[::-1], rim[::-1]
        ptsH = np.stack([pts[:, 0] / H, (pts[:, 1] - ctx.water_z) / H], axis=1)
        rec["n_chains"] = len(chains)
        if not rim.any():
            rec["note"] = "the section does not cross any edge of the rim group"
            sections.append(rec)
            continue
        s_raw = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(ptsH, axis=0).T))])
        try:
            C = pm.Curve(ptsH)
            met = pm.measure_profile(ptsH)
        except ValueError as exc:
            rec["note"] = "degenerate section: %s" % exc
            sections.append(rec)
            continue
        s_r = 0.5 * (float(s_raw[rim].min()) + float(s_raw[rim].max()))
        rec.update({"rim_band_pct_H": 100.0 * float(s_raw[rim].max() - s_raw[rim].min()), "overhanging": bool(met["overhanging"])})
        vals = []
        for o in offs:
            dia, touch, centre = inscribed_diameter(C, s_r + o, w, excl, 2e-4)
            if dia is not None:
                vals.append((dia, touch, centre, s_r + o))
        if not vals:
            rec["note"] = "no inscribed circle found"
            sections.append(rec)
            continue
        vals.sort(key=lambda v: v[0])
        dia, touch, centre, s_used = vals[len(vals) // 2]
        rp = C.at(s_used)
        rec.update({"rim_thickness_pct_H": 100.0 * dia, "rim_point_H": [float(rp[0]), float(rp[1])],
                    "rim_point_world_m": [float(rp[0] * H), float(y0), float(rp[1] * H + ctx.water_z)],
                    "probe_values_pct_H": [100.0 * v[0] for v in vals]})
        if met["overhanging"]:
            tip = met["landmarks"]["head_tip"]
            rec["tip_H"] = tip["H"]
            rec["rim_to_tip_arclength_pct_H"] = 100.0 * abs(s_r - tip["s"])
            if tip_cam_H is not None:
                dist = math.hypot(tip["H"][0] - tip_cam_H[0], tip["H"][1] - tip_cam_H[1])
                rec["tip_to_cam_print_tip_pct_h"] = float(pm.H_to_pct_h(dist))
                rec["judged"] = bool(dist <= match)
        sections.append(rec)
        drawable.append({"y": float(y0), "ptsH": ptsH, "rim_point": rp, "centre": centre, "radius": 0.5 * dia, "judged": rec["judged"],
                         "value": 100.0 * dia})
    judged = [s for s in sections if s.get("judged") and s.get("rim_thickness_pct_H") is not None]
    details = {"n_group_vertices": int(in_group.sum()), "section_y_m": [float(v) for v in ys], "sections": sections,
               "n_judged_sections": len(judged), "cam_print_tip_H": tip_cam_H}
    if not judged:
        details["error"] = "no section whose head tip coincides with the head tip seen by CAM_print (or no overhang)"
        return None, details, drawable
    worst = max(judged, key=lambda s: s["rim_thickness_pct_H"])
    details["worst_section"] = worst
    return float(worst["rim_thickness_pct_H"]), details, drawable


# ------------------------------------------------------------------------------------ G4: self-intersection
def _interval(p, d):
    """Parameter interval (along the intersection line) where a triangle meets the other triangle's plane.
    p (K, 3) projections of the vertices on the line direction, d (K, 3) signed plane distances."""
    ts = []
    with np.errstate(divide="ignore", invalid="ignore"):
        for i, j in ((0, 1), (1, 2), (2, 0)):
            crossing = d[:, i] * d[:, j] < 0
            t = p[:, i] + (p[:, j] - p[:, i]) * d[:, i] / (d[:, i] - d[:, j])
            ts.append(np.where(crossing, t, np.nan))
        for i in range(3):
            ts.append(np.where(d[:, i] == 0, p[:, i], np.nan))
        T = np.stack(ts, axis=1)
        return np.nanmin(T, axis=1), np.nanmax(T, axis=1)


def proper_intersections(A, B, eps, min_angle_deg):
    """A, B (K, 3, 3) triangle pairs.  -> (proper (K,) bool, classes dict of counts, overlap length (K,))"""
    K = A.shape[0]
    n1 = np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0])
    n2 = np.cross(B[:, 1] - B[:, 0], B[:, 2] - B[:, 0])
    l1, l2 = np.linalg.norm(n1, axis=1), np.linalg.norm(n2, axis=1)
    e1 = np.maximum.reduce([np.linalg.norm(A[:, 1] - A[:, 0], axis=1), np.linalg.norm(A[:, 2] - A[:, 1], axis=1), np.linalg.norm(A[:, 0] - A[:, 2], axis=1)])
    e2 = np.maximum.reduce([np.linalg.norm(B[:, 1] - B[:, 0], axis=1), np.linalg.norm(B[:, 2] - B[:, 1], axis=1), np.linalg.norm(B[:, 0] - B[:, 2], axis=1)])
    degenerate = (l1 <= eps * e1) | (l2 <= eps * e2)            # height of the triangle below eps
    with np.errstate(divide="ignore", invalid="ignore"):
        n1u, n2u = n1 / l1[:, None], n2 / l2[:, None]
        dB = ((B - A[:, :1]) * n1u[:, None, :]).sum(axis=2)
        dA = ((A - B[:, :1]) * n2u[:, None, :]).sum(axis=2)
        both_b = (dB.max(axis=1) > eps) & (dB.min(axis=1) < -eps)
        both_a = (dA.max(axis=1) > eps) & (dA.min(axis=1) < -eps)
        D = np.cross(n1u, n2u)
        lD = np.linalg.norm(D, axis=1)
        nonpar = lD > math.sin(math.radians(min_angle_deg))
        cand = ~degenerate & both_a & both_b & nonpar
        overlap = np.zeros(K)
        if cand.any():
            Du = D[cand] / lD[cand][:, None]
            a0, a1 = _interval((A[cand] * Du[:, None, :]).sum(axis=2), dA[cand])
            b0, b1 = _interval((B[cand] * Du[:, None, :]).sum(axis=2), dB[cand])
            overlap[cand] = np.minimum(a1, b1) - np.maximum(a0, b0)
    proper = cand & (overlap > eps)
    touching = ~degenerate & ~proper
    return proper, {"degenerate_pairs": int(degenerate.sum()), "touching_or_coplanar_pairs": int(touching.sum())}, overlap


def self_intersections(arr, H, S):
    """-> dict: n_pairs (proper crossings), examples, counts of ignored pair classes."""
    from mathutils.bvhtree import BVHTree
    co, tris = arr["co_world"], arr["tris"]
    tree = BVHTree.FromPolygons([tuple(v) for v in co.tolist()], [tuple(t) for t in tris.tolist()], all_triangles=True, epsilon=0.0)
    pairs = tree.overlap(tree)
    out = {"n_candidate_pairs_bvh": 0, "n_pairs": 0, "degenerate_pairs": 0, "touching_or_coplanar_pairs": 0, "examples": [], "bbox_world_m": None}
    if not pairs:
        return out
    P = np.asarray(pairs, dtype=np.int64)
    P = P[P[:, 0] < P[:, 1]]
    ta, tb = tris[P[:, 0]], tris[P[:, 1]]
    shared = (ta[:, :, None] == tb[:, None, :]).any(axis=(1, 2))
    P = P[~shared]
    out["n_candidate_pairs_bvh"] = int(P.shape[0])
    if P.shape[0] == 0:
        return out
    eps = float(S["g4_eps_rel_H"]) * H
    proper, classes, overlap = proper_intersections(co[tris[P[:, 0]]], co[tris[P[:, 1]]], eps, float(S["g4_min_plane_angle_deg"]))
    out.update(classes)
    Q = P[proper]
    out["n_pairs"] = int(Q.shape[0])
    if Q.shape[0]:
        cen = 0.5 * (co[tris[Q[:, 0]]].mean(axis=1) + co[tris[Q[:, 1]]].mean(axis=1))
        out["bbox_world_m"] = [[float(v) for v in cen.min(axis=0)], [float(v) for v in cen.max(axis=0)]]
        out["centroid_world_m"] = [float(v) for v in cen.mean(axis=0)]
        polys = np.stack([arr["tri_poly"][Q[:, 0]], arr["tri_poly"][Q[:, 1]]], axis=1)
        out["n_face_pairs"] = int(np.unique(polys, axis=0).shape[0])
        order = np.argsort(-overlap[proper])[:10]
        out["examples"] = [{"faces": [int(polys[k, 0]), int(polys[k, 1])], "location_world_m": [float(v) for v in cen[k]],
                            "intersection_length_m": float(overlap[proper][k])} for k in order]
        out["_centres"] = cen
    return out


# ------------------------------------------------------------------------------------ G5 helpers
def capture_vertices(ctx, frames):
    out = {}
    for f in frames:
        ctx.scene.frame_set(int(f))
        a = ct.eval_mesh_arrays(ctx.obj, topology=False)
        out[int(f)] = {"co": a["co_local"].copy(), "M": a["matrix_world"].copy()}
    return out


def compare_captures(a, b):
    worst, n_diff, per = 0.0, 0, {}
    for f in sorted(a):
        if f not in b or a[f]["co"].shape != b[f]["co"].shape:
            per[f] = {"identical": False, "note": "vertex count differs or frame missing"}
            worst = float("inf")
            continue
        same = a[f]["co"].tobytes() == b[f]["co"].tobytes() and a[f]["M"].tobytes() == b[f]["M"].tobytes()
        wa = a[f]["co"].astype(np.float64) @ a[f]["M"][:3, :3].T + a[f]["M"][:3, 3]
        wb = b[f]["co"].astype(np.float64) @ b[f]["M"][:3, :3].T + b[f]["M"][:3, 3]
        dmax = float(np.abs(wa - wb).max()) if wa.size else 0.0
        nd = int((a[f]["co"] != b[f]["co"]).sum())
        per[f] = {"identical": bool(same), "max_abs_diff_m": dmax, "n_differing_components": nd, "sha1": ct.sha(a[f]["co"], a[f]["M"])}
        worst = max(worst, dmax if not same else 0.0)
        if not same and dmax == 0.0:
            worst = max(worst, float(np.finfo(np.float32).tiny))      # bytes differ although the values compare equal (e.g. -0.0)
        n_diff += nd
    return worst, n_diff, per


def dump_verts_main(args):
    """Internal entry used by G5: build in THIS fresh process and write the vertex arrays."""
    ctx = ct.setup_context(args, TEST_NAME, run_dir=os.path.dirname(ct.resolve_path(args.dump_verts)))
    frames = [int(v) for v in args.frames.split(",")]
    cap = capture_vertices(ctx, frames)
    path = paths.ensure_parent(ct.resolve_path(args.dump_verts))
    np.savez(path, frames=np.asarray(frames), **{"co_%d" % f: cap[f]["co"] for f in frames}, **{"M_%d" % f: cap[f]["M"] for f in frames})
    log("[mesh] dumped %d frames to %s" % (len(frames), path))
    bootstrap.finish(True, "dump-verts")


def rebuild_in_subprocess(ctx, frames, run_dir):
    import bpy
    npz = os.path.join(run_dir, "g5_subprocess_vertices.npz")
    src = ctx.source
    cmd = [bpy.app.binary_path, "--background", "--factory-startup", "--python-exit-code", "1"]
    if src.get("blend"):
        cmd.append(src["blend"])
    cmd += ["--python", os.path.abspath(__file__), "--", "--dump-verts", npz, "--frames", ",".join(str(f) for f in frames),
            "--build-script", src["build_script"], "--build-func", src["build_func"]]
    for k, v in (src.get("build_args") or {}).items():
        cmd += ["--build-arg", "%s=%s" % (k, v if isinstance(v, str) else ct.json.dumps(v))]
    if ctx.args.object:
        cmd += ["--object", ctx.args.object]
    if ctx.args.H is not None:
        cmd += ["--H", str(ctx.args.H)]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    logp = paths.ensure_parent(os.path.join(run_dir, "g5_subprocess.log"))
    with open(logp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(proc.stdout or "")
    if proc.returncode != 0 or not os.path.isfile(npz):
        return None, "fresh Blender process failed (exit %s); log: %s" % (proc.returncode, paths.norm(logp))
    z = np.load(npz)
    return {int(f): {"co": z["co_%d" % f], "M": z["M_%d" % f]} for f in z["frames"]}, None


# ------------------------------------------------------------------------------------ the test
def run(ctx, run_dir=None, skip=()):
    S, H = ctx.settings, ctx.H
    run_dir = run_dir or ctx.run_dir
    skip = set(ct.validate_names(skip, G_IDS, "--skip"))
    f0, fN = int(ctx.frame_start), int(ctx.final_frame)
    frames = list(range(f0, fN + 1))
    checks, vnotes, skipped, outputs, details = [], [], sorted(skip), {}, {}
    valid, nonfinite_frames = True, []
    if skip:
        vnotes.append("skipped on request (--skip): %s - these tests are NOT judged, so the verdict cannot be PASS (INCOMPLETE)" % ", ".join(sorted(skip)))
    sw = ct.StopWatch()

    # ---- G1 + G2 over all frames
    sig0, changes, hem_worst, hem_series, vmove = None, [], None, [], []
    bverts, prev_co, n_b_edges = None, None, 0
    uv_names = []
    for f in frames:
        ctx.scene.frame_set(f)
        a = ct.eval_mesh_arrays(ctx.obj, topology=True, uv=True)
        if a["n_nonfinite_vertices"]:
            nonfinite_frames.append({"frame": f, "n_nonfinite_vertices": a["n_nonfinite_vertices"], "vertex_indices": a["nonfinite_vertex_indices"]})
        uv = a.get("uv_layers", {})
        sig = {"n_vertices": a["n_vertices"], "n_edges": int(a["edges"].shape[0]), "n_polygons": int(a["poly_start"].shape[0]),
               "n_loops": int(a["loop_vert"].shape[0]), "loops": ct.sha(a["loop_vert"], a["poly_start"], a["poly_total"]),
               "edges": ct.sha(a["edges"]), "uv_layers": sorted(uv), "uv": {k: ct.sha(v) for k, v in uv.items()}}
        if sig0 is None:
            sig0, uv_names = sig, sorted(uv)
            bverts, n_b_edges = ct.boundary_vertices(a["loop_vert"], a["poly_start"], a["poly_total"], a["n_vertices"])
        elif sig != sig0:
            changes.append({"frame": f, "differs_in": [k for k in sig if sig[k] != sig0[k]]})
            bverts, n_b_edges = ct.boundary_vertices(a["loop_vert"], a["poly_start"], a["poly_total"], a["n_vertices"])
        if bverts is not None and bverts.size:
            dz = np.abs(a["co_world"][bverts, 2] - ctx.water_z)
            k = int(np.argmax(dz))
            hem_series.append(100.0 * float(dz[k]) / H)
            if hem_worst is None or dz[k] > hem_worst["dz_m"]:
                hem_worst = {"frame": f, "vertex": int(bverts[k]), "dz_m": float(dz[k]), "world_m": [float(v) for v in a["co_world"][bverts[k]]]}
        else:
            hem_series.append(float("nan"))
        if prev_co is not None and prev_co.shape == a["co_world"].shape:
            dv = np.linalg.norm(a["co_world"] - prev_co, axis=1)
            vmove.append(float(np.nanmax(dv)) / H if np.isfinite(dv).any() else float("nan"))
        else:
            vmove.append(float("nan"))
        prev_co = a["co_world"]
    t_g12 = sw.lap()
    if nonfinite_frames:
        valid = False
        vnotes.append("NON-FINITE GEOMETRY: the evaluated mesh has vertices with NaN / inf coordinates on %d frame(s) (first: frame %d, %d vertex / vertices, indices %s). "
                      "Hashes, hem, sections and the BVH test are not trustworthy on such a mesh."
                      % (len(nonfinite_frames), nonfinite_frames[0]["frame"], nonfinite_frames[0]["n_nonfinite_vertices"], nonfinite_frames[0]["vertex_indices"]))
    checks.append(ct.report_value("T", "n_frames_nonfinite_geometry", len(nonfinite_frames), "frames",
                                  where=None if not nonfinite_frames else {"frames": [d["frame"] for d in nonfinite_frames[:20]]},
                                  note="frames %d..%d whose evaluated mesh has a vertex with a NaN / inf coordinate; > 0 -> INVALID" % (f0, fN)))
    details["nonfinite_geometry"] = nonfinite_frames[:50]
    rec_u, note_u = ct.untested_objects_report(ctx)
    checks.append(rec_u)
    if note_u:
        vnotes.append(note_u + " (test_mesh inspects ONLY the first tested object: %s)" % ctx.obj.name)
    if "G1" not in skip:
        if not uv_names:
            checks.append(ct.make_check("G1", "n_topology_or_uv_changes", None, note="the evaluated mesh has NO UV layer (spec section 7 requires UVs), so 'UV constant' cannot be fulfilled"))
        else:
            checks.append(ct.make_check("G1", "n_topology_or_uv_changes", len(changes), target=0,
                                        where=None if not changes else {"frames": [c["frame"] for c in changes[:20]], "frame": changes[0]["frame"]},
                                        note="%d frames; %d vertices, %d polygons, UV layers %s%s" % (len(frames), sig0["n_vertices"], sig0["n_polygons"], uv_names,
                                                                                                        "" if not changes else "; first change differs in %s" % changes[0]["differs_in"])))
        vm = np.asarray(vmove[1:], dtype=np.float64)
        if vm.size and np.isfinite(vm).any():
            k = int(np.nanargmax(vm)) + 1
            checks.append(ct.report_value("G1", "max_vertex_step_H", float(vm[k - 1]), "H / frame", where={"frame": frames[k]},
                                          note="largest movement of a single vertex between two neighbouring frames (spec section 7: the same vertex moves continuously); not judged"))
        # REPORT ONLY: size of the mesh next to the existing Unity cache, and the orientation of the UVs (final frame)
        checks.append(ct.report_value("G1", "n_vertices", sig0["n_vertices"], "count", target={"unity_cache_vertices": UNITY_CACHE_VERTICES},
                                      difference={"ratio_to_unity_cache": sig0["n_vertices"] / float(UNITY_CACHE_VERTICES)},
                                      note="REPORT ONLY (spec section 7: keep the new mesh in the same order of magnitude as the existing Unity cache of %d vertices; "
                                           "the number itself is proposed by the modeller)" % UNITY_CACHE_VERTICES))
        ctx.scene.frame_set(fN)
        uvo = uv_orientation(ct.eval_mesh_arrays(ctx.obj, topology=True, uv=True)) if uv_names else None
        details["G1_uv_orientation"] = uvo
        if uvo and uvo.get("n_triangles_used"):
            checks.append(ct.report_value("G1", "uv_u_abs_cos_to_crest_line", uvo["u_abs_cos_to_y"], "|cos| (0 = U runs inside the section planes)", target=0.0,
                                          note="REPORT ONLY, frame %d, UV layer '%s': area-weighted mean |cos| between dP/dU and the world Y axis (crest line); spec section 7: U along the section contour"
                                               % (fN, uvo["layer"])))
            checks.append(ct.report_value("G1", "uv_v_abs_cos_to_crest_line", uvo["v_abs_cos_to_y"], "|cos| (1 = V runs along the crest line)", target=1.0,
                                          note="REPORT ONLY: area-weighted mean |cos| between dP/dV and the world Y axis; V increases with +Y on %.0f %% of the area; "
                                               "tapered / curved ends lower the value" % (100.0 * uvo["v_increases_with_y_share"])))
            checks.append(ct.report_value("G1", "uv_u_starts_at_back_hem", uvo["u_starts_at_back_hem"], "bool", target=1,
                                          note="REPORT ONLY: mean X of the loops with the smallest 2 %% of U = %.3f m, with the largest 2 %% = %.3f m (spec: U from the hem of the back to the trough)"
                                               % (uvo["mean_x_at_smallest_u_m"], uvo["mean_x_at_largest_u_m"])))
        else:
            checks.append(ct.report_value("G1", "uv_u_abs_cos_to_crest_line", None, None, note="REPORT ONLY: no UV layer / no usable triangle"))
        details["G1"] = {"signature_first_frame": sig0, "changes": changes[:50], "n_frames": len(frames)}
    if "G2" not in skip:
        if bverts is None or not bverts.size:
            checks.append(ct.make_check("G2", "hem_step_pct_H", None, note="the mesh has no boundary edges (closed mesh): no hem"))
        else:
            checks.append(ct.make_check("G2", "hem_step_pct_H", 100.0 * hem_worst["dz_m"] / H, target=0.0,
                                        where={"frame": hem_worst["frame"], "world_m": hem_worst["world_m"], "vertex": hem_worst["vertex"]},
                                        note="%d boundary vertices on %d boundary edges; max |Z - %.3g m| = %.4f m (H = %.3f m)" % (bverts.size, n_b_edges, ctx.water_z, hem_worst["dz_m"], H)))
            details["G2"] = {"n_boundary_vertices": int(bverts.size), "worst": hem_worst, "per_frame_pct_H": hem_series}
            img = plot.line_plot([{"label": "hem step", "x": frames, "y": hem_series, "color": "blue"}], title="G2: largest |Z - still water| of the mesh boundary",
                                 xlabel="frame", ylabel="% of H", size=(1300, 380),
                                 hlines=[{"y": paths.threshold("G2", "hem_step_pct_H", "spec"), "label": "limit", "color": "red"}], ylim=(0.0, None))
            outputs["g2_hem"] = imgio.save_png(os.path.join(run_dir, "g2_hem.png"), img)

    # ---- G3 on the final frame
    ctx.scene.frame_set(fN)
    a_final = ct.eval_mesh_arrays(ctx.obj, topology=True)
    if "G3" not in skip:
        tip_cam = None
        try:
            rect = silhouette.ViewRect.from_cam_print(H=H, scale=float(S["mesh_res_scale"]))
            prof, _mask, _info = silhouette.profile_of_objects(ctx.objs, rect=rect, water_z=ctx.water_z, exact=True)
            if int(_info.get("n_nonfinite_vertices") or 0) or int(_info.get("n_dropped_triangles") or 0):
                valid = False
                vnotes.append("G3: the CAM_print silhouette of the final frame dropped %s triangle(s) because of %s non-finite vertex / vertices"
                              % (_info.get("n_dropped_triangles"), _info.get("n_nonfinite_vertices")))
            mcam = pm.measure_profile(prof["H"])
            if mcam["overhanging"]:
                tip_cam = mcam["landmarks"]["head_tip"]["H"]
        except silhouette.ProfileError as exc:
            vnotes.append("G3: no CAM_print profile on the final frame (%s)" % exc)
        val, det3, drawable = rim_thickness(ctx, a_final, tip_cam, S)
        details["G3"] = det3
        where = None
        if val is not None:
            ws = det3["worst_section"]
            where = {"frame": fN, "world_m": ws["rim_point_world_m"], "px": [float(v) for v in ctx.F.H_to_px(*ws["rim_point_H"])]}
        checks.append(ct.make_check("G3", "rim_thickness_pct_H", val, target=None, where=where,
                                    note=det3.get("error") or "max over %d judged section(s) of %d; all judged values %s %% of H"
                                    % (det3["n_judged_sections"], len(det3["sections"]),
                                       ["%.3f" % s["rim_thickness_pct_H"] for s in det3["sections"] if s.get("judged")])))
        if drawable:
            outputs["g3_sections"] = imgio.save_png(os.path.join(run_dir, "g3_sections.png"), draw_sections(drawable, tip_cam))
    t_g3 = sw.lap()

    # ---- G4 on the final frame and every n-th frame
    if "G4" not in skip:
        stepf = int(paths.threshold("G4", "frame_step", "spec"))
        checks.append(ct.make_check("G4", "frame_step", stepf, note="test setting"))
        g4_frames = sorted(set(range(f0, fN + 1, stepf)) | {fN})
        per, total, worst = [], 0, None
        for f in g4_frames:
            ctx.scene.frame_set(f)
            a = a_final if f == fN else ct.eval_mesh_arrays(ctx.obj, topology=True)
            r = self_intersections(a, H, S)
            cen = r.pop("_centres", None)
            r["frame"] = f
            per.append(r)
            total += r["n_pairs"]
            if r["n_pairs"] and (worst is None or r["n_pairs"] > worst[0]["n_pairs"]):
                worst = (r, cen, a)
        where = None
        if worst is not None:
            r = worst[0]
            where = {"frame": r["frame"], "frames": [p["frame"] for p in per if p["n_pairs"]], "world_m": r["centroid_world_m"],
                     "px": [float(v) for v in ctx.F.m_to_px(r["centroid_world_m"][0], r["centroid_world_m"][2] - ctx.water_z)]}
            outputs["g4_intersections"] = imgio.save_png(os.path.join(run_dir, "g4_intersections.png"), draw_intersections(ctx, worst))
        checks.append(ct.make_check("G4", "n_self_intersections", total, target=0, where=where,
                                    note="properly crossing triangle pairs summed over frames %s; ignored as touching / coplanar: %d pairs, degenerate: %d pairs (not judged)"
                                         % (g4_frames, sum(p["touching_or_coplanar_pairs"] for p in per), sum(p["degenerate_pairs"] for p in per))))
        details["G4"] = {"frames": per}
    t_g4 = sw.lap()

    # ---- G5 rebuild determinism (resets the scene: keep it last)
    if "G5" not in skip:
        if ctx.builder is None:
            skipped.append("G5")
            vnotes.append("G5 not run: it needs --build-script (rebuild from parameters). G5 is therefore NOT judged and the verdict cannot be PASS (INCOMPLETE)")
        else:
            n5 = max(2, int(S["g5_n_frames"]))
            f5 = sorted(set(int(round(v)) for v in np.linspace(f0, fN, n5)))
            mode = getattr(ctx.args, "g5_mode", "both") or "both"
            ref = capture_vertices(ctx, f5)
            runs, worst5, notes5 = {}, 0.0, []
            if mode in ("both", "inprocess"):
                ct.rebuild_scene(ctx)
                w, nd, per5 = compare_captures(ref, capture_vertices(ctx, f5))
                runs["inprocess_rebuild"] = {"max_abs_diff_m": w, "n_differing_components": nd, "frames": per5}
                worst5 = max(worst5, w)
            if mode in ("both", "subprocess"):
                cap, err = rebuild_in_subprocess(ctx, f5, run_dir)
                if cap is None:
                    notes5.append(err)
                    worst5 = None
                else:
                    w, nd, per5 = compare_captures(ref, cap)
                    runs["fresh_process_rebuild"] = {"max_abs_diff_m": w, "n_differing_components": nd, "frames": per5}
                    worst5 = None if worst5 is None else max(worst5, w)
            details["G5"] = {"frames": f5, "mode": mode, "runs": runs, "notes": notes5}
            checks.append(ct.make_check("G5", "rebuild_max_abs_diff_m", worst5, target=0.0,
                                        note="; ".join(notes5) or "frames %s compared bit-exactly (float32 vertex bytes + world matrix): %s"
                                        % (f5, ", ".join("%s: %d differing components" % (k, v["n_differing_components"]) for k, v in runs.items()))))
    t_g5 = sw.lap()

    audit = ctx.audit()
    result = {"schema": ct.RESULT_SCHEMA, "test": TEST_NAME, "run_dir": run_dir, "context": ctx.describe(),
              "summary": ct.summarize(checks, valid, vnotes, skipped, expected=ct.EXPECTED_IDS[TEST_NAME], audit=audit), "checks": checks, "details": details,
              "settings_audit": audit,
              "interpretation_notes": {k: ct.INTERPRETATION_NOTES[k] for k in ("tiers", "verdicts", "validity", "G1", "G2", "G3", "G4", "G5")},
              "outputs": outputs, "seconds": {"G1_G2": t_g12, "G3": t_g3, "G4": t_g4, "G5": t_g5}}
    ct.write_result(run_dir, result)
    ct.log_checks(checks, "test_mesh frames %d..%d" % (f0, fN))
    for nn in vnotes:
        log("[mesh] note: " + nn)
    return result


# ------------------------------------------------------------------------------------ images
def draw_sections(drawable, tip_cam):
    """Head region of every section with the inscribed circle at the rim point."""
    cells = []
    for d in drawable:
        rp, r = d["rim_point"], d["radius"]
        half = max(0.06, 4.0 * r)
        x0, x1, z0, z1 = rp[0] - 1.4 * half, rp[0] + 0.6 * half, rp[1] - half, rp[1] + half
        Wc, Hc = 520, 520
        sx, sz = Wc / (x1 - x0), Hc / (z1 - z0)
        img = draw.canvas(Hc, Wc, "white")
        to = lambda p: np.stack([(np.asarray(p)[..., 0] - x0) * sx, (z1 - np.asarray(p)[..., 1]) * sz], axis=-1)  # noqa: E731
        P = d["ptsH"]
        keep = (P[:, 0] > x0 - 0.2) & (P[:, 0] < x1 + 0.2) & (P[:, 1] > z0 - 0.2) & (P[:, 1] < z1 + 0.2)
        draw.polyline(img, np.where(keep[:, None], to(P), np.nan), "blue", 2.0)
        if d["centre"] is not None:
            draw.circle(img, to(d["centre"]), r * sx, "red" if d["judged"] else "gray", fill=False, width=2.0)
        draw.marker(img, to(rp), "+", 9, "red", 2.0, outline="white")
        if tip_cam is not None:
            draw.marker(img, to(np.asarray(tip_cam)), "x", 8, "green", 2.0, outline="white")
        draw.text(img, 5, 5, "Y=%.2f m  2r=%.3f %% H  %s" % (d["y"], d["value"], "JUDGED" if d["judged"] else "reported only"),
                  "black", 2, bg="white", bg_alpha=0.85)
        cells.append(img)
    sheet = draw.grid(cells, ncols=3, gap=8)
    cap = draw.canvas(30, sheet.shape[1], "white")
    draw.text(cap, 6, 5, "G3: cross-sections Y = const (blue), rim point (+), inscribed circle (red = judged), CAM_print head tip (x)", "black", 2)
    return draw.vstack([cap, sheet], gap=0)


def draw_intersections(ctx, worst):
    r, cen, a = worst
    H = ctx.H
    rect = silhouette.ViewRect.from_cam_print(H=H, scale=0.4)
    mask, _info = silhouette.mask_from_triangles(a["co_world"], a["tris"], rect, ctx.water_z, exact=False)
    img = draw.canvas(rect.height_px, rect.width_px, "white")
    draw.overlay_mask(img, mask, "blue", 0.30)
    if cen is not None:
        x, y = rect.world_to_px(cen[:, 0], cen[:, 2])
        for px, py in list(zip(x, y))[:4000]:
            draw.circle(img, (px, py), 2.0, "red", True)
    draw.text(img, 6, 6, "G4 frame %d: %d properly crossing triangle pairs (red dots = pair centres, CAM_print view)" % (r["frame"], r["n_pairs"]),
              "black", 2, bg="white", bg_alpha=0.85)
    return img


def main():
    ap = argparse.ArgumentParser(description="great_wave mesh tests G1-G5")
    ct.add_common_args(ap)
    add_args(ap)
    args = bootstrap.parse_args(ap)
    if args.dump_verts:
        dump_verts_main(args)                      # internal helper process of G5: no run directory of its own, no verdict
        return

    def body(run_dir):
        ct.validate_names(args.skip.split(","), G_IDS, "--skip")          # before the (possibly long) build
        ctx = ct.setup_context(args, TEST_NAME, run_dir=run_dir)
        result = run(ctx, skip=args.skip.split(","))
        log("[mesh] results: %s" % result["run_dir"])
        return result

    ct.guarded_main(TEST_NAME, args, body)


if __name__ == "__main__":
    main()
