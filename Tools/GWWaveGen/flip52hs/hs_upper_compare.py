# -*- coding: utf-8 -*-
"""FLIP52B hires surfacing test, post-analysis on the written GW45SRF1 files (py -3.10 -B, numpy + scipy; < 1 min). 2026-10-18 written new (Claude).
hs_surface_test.py measured every triangle of the crop, which includes the BOTTOM of the 2.5 m particle layer near the bed (the layer_and_mirror
rule keeps only particles within 2.5 m of the surface, so the surfacer also wraps the layer's underside, ~0.5-1.5 m above the bed where the
water is shallow; it is under water and is not the visible sea surface). This script repeats the shape and facet measures on the UPPER surface
only: triangles whose centroid is more than UPPER_M above the bed (D19B bed, 1:10 from x 160.25 m), inside the core x 202-298 m, lateral <= 38 m.
Point-to-mesh distance = distance to a dense sampling of the other mesh's triangles (spacing 0.03 m, error <= 0.021 m) [computed].
Writes hires/test_fFFFF/hs_upper_compare_fFFFF.json.  usage: py -3.10 -B hs_upper_compare.py [frame=2112]
"""
import sys, os, json, struct
import numpy as np
from scipy.spatial import cKDTree

FRAME = int(sys.argv[1]) if len(sys.argv) > 1 else 2112
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/hires/test_f%04d" % FRAME
HERO = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP52B/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long/surf/s_%05d.gw45s" % FRAME
CORE = dict(x0=202.0, x1=298.0, z1=38.0)
UPPER_M = 2.5          # [chosen] = surf_layer_m: the layer underside lies within ~1.5 m of the bed
SPACING = 0.03
HEAD_FMT = "<8sIIdiIIffffffff"


def bed(x):
    return -(19.0 - np.maximum(x - 160.25, 0.0) / 10.0)


def read(p):
    b = open(p, "rb").read()
    h = struct.unpack(HEAD_FMT, b[:struct.calcsize(HEAD_FMT)])
    nv, nt = h[5], h[6]
    lo = np.array(h[7:10]); hi = np.array(h[10:13]); o = 96
    q = np.frombuffer(b, np.uint16, nv * 3, o).reshape(-1, 3); o += nv * 6
    n = np.frombuffer(b, np.uint16, nv * 2, o).reshape(-1, 2).astype(np.float64) / 65535 * 2 - 1; o += nv * 4
    o += nv * 6
    t = np.frombuffer(b, np.uint32, nt * 3, o).reshape(-1, 3).astype(np.int64)
    x, y = n[:, 0], n[:, 1]
    z = 1 - np.abs(x) - np.abs(y)
    neg = z < 0
    N = np.stack([np.where(neg, (1 - np.abs(y)) * np.sign(x + 1e-30), x), np.where(neg, (1 - np.abs(x)) * np.sign(y + 1e-30), y), z], 1)
    N /= np.linalg.norm(N, axis=1, keepdims=True)
    return q / 65535.0 * (hi - lo) + lo, N, t


def upper_faces(P, t):
    c = P[t].mean(1)
    return t[(c[:, 0] >= CORE["x0"]) & (c[:, 0] <= CORE["x1"]) & (c[:, 2] <= CORE["z1"]) & (c[:, 1] > bed(c[:, 0]) + UPPER_M)]


def samples(P, t):
    out = []
    a, b, c = P[t[:, 0]], P[t[:, 1]], P[t[:, 2]]
    L = np.max(np.stack([np.linalg.norm(b - a, axis=1), np.linalg.norm(c - b, axis=1), np.linalg.norm(a - c, axis=1)], 1), 1)
    nseg = np.maximum(1, np.ceil(L / SPACING)).astype(int)
    for n in np.unique(nseg):
        k = nseg == n
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1), indexing="ij")
        m = (i + j) <= n
        u = (i[m] / n)[None, :, None]
        v = (j[m] / n)[None, :, None]
        out.append((a[k][:, None] * (1 - u - v) + b[k][:, None] * u + c[k][:, None] * v).reshape(-1, 3))
    return np.concatenate(out)


def pct(a, q):
    return [round(float(v), 4) for v in np.percentile(a, q)] if len(a) else None


def facets(P, N, t):
    a, b, c = P[t[:, 0]], P[t[:, 1]], P[t[:, 2]]
    fn = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(fn, axis=1)
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)
    E = np.sort(np.concatenate([t[:, [0, 1]], t[:, [1, 2]], t[:, [2, 0]]]), 1)
    F = np.tile(np.arange(len(t)), 3)
    key = E[:, 0] * (len(P) + 1) + E[:, 1]
    o = np.argsort(key, kind="stable")
    ks = key[o]
    s = np.nonzero(ks[1:] == ks[:-1])[0]
    dih = np.degrees(np.arccos(np.clip((fn[F[o][s]] * fn[F[o][s + 1]]).sum(1), -1, 1)))
    ue = E[o][np.unique(ks, return_index=True)[1]]
    L = np.linalg.norm(P[ue[:, 0]] - P[ue[:, 1]], axis=1)
    vn = N[t].mean(1)
    vn /= np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)
    flip = (fn * vn).sum(1) < 0.0
    nj = np.degrees(np.arccos(np.clip((N[ue[:, 0]] * N[ue[:, 1]]).sum(1), -1, 1)))
    return dict(n_tri=int(len(t)), area_m2=round(float(area.sum()), 1), edge_m_p50_p95_max=pct(L, [50, 95, 100]),
                dihedral_deg_p50_p90_p95_p99=pct(dih, [50, 90, 95, 99]), share_dihedral_gt_20deg=round(float((dih > 20).mean()), 4),
                vertex_normal_jump_per_edge_deg_p50_p90_p99=pct(nj, [50, 90, 99]),
                vertex_normal_turn_per_m_deg_p50_p90=pct(nj / np.maximum(L, 1e-6), [50, 90]),
                flipped_face_share=round(float(flip.mean()), 5), flipped_face_area_m2=round(float(area[flip].sum()), 2))


ORDER = ["b0_base", "a0_adapt0", "v050", "v035", "v050_dse", "v050_dseg", "v050_inf45", "a0_g100", "a0_v050_dse", "a0_v050_dseg"]
names = [n for n in ORDER if os.path.exists(OUT + "/%s/s_%05d.gw45s" % (n, FRAME))]
M = {n: read(OUT + "/%s/s_%05d.gw45s" % (n, FRAME)) for n in names}
if os.path.exists(HERO):
    M["hero"] = read(HERO)
R = dict(tool="Tools/GWWaveGen/flip52hs/hs_upper_compare.py", frame=FRAME, core=CORE, upper_rule="centroid y > bed(x) + %.1f m" % UPPER_M,
         sampling_m=SPACING, tags="[measured] from the GW45SRF1 files; [computed] distances (sampling error <= %.3f m)" % (SPACING / np.sqrt(2)),
         variants={})
U = {n: upper_faces(M[n][0], M[n][2]) for n in M}
for n in M:
    P, N, t = M[n]
    c = P[t].mean(1)
    core = (c[:, 0] >= CORE["x0"]) & (c[:, 0] <= CORE["x1"]) & (c[:, 2] <= CORE["z1"])
    R["variants"][n] = dict(core_tri=int(core.sum()), upper_tri=int(len(U[n])), bottom_layer_tri=int(core.sum() - len(U[n])),
                            upper=facets(P, N, U[n]))
    up = np.unique(U[n].ravel())
    Pu = P[up]
    R["variants"][n]["upper_crest_y_max"] = round(float(Pu[:, 1].max()), 4)
    seam = Pu[np.abs(Pu[:, 2]) < 5e-4]
    R["variants"][n]["upper_section_crest_y_max"] = round(float(seam[:, 1].max()), 4) if len(seam) else None
TREE = {n: cKDTree(samples(M[n][0], U[n])) for n in M}
base = "b0_base"
for n in M:
    if n == base:
        continue
    out = {}
    for a, b, lab in ((n, base, "to_base"), (base, n, "base_to")):
        P = M[a][0]
        up = np.unique(U[a].ravel())
        Q = P[up]
        k = (Q[:, 0] >= CORE["x0"] + 1) & (Q[:, 0] <= CORE["x1"] - 1) & (Q[:, 2] <= CORE["z1"] - 1)
        d, _ = TREE[b].query(Q[k], workers=2)
        out[lab + "_mean_p95_p99_max_m"] = [round(float(d.mean()), 4)] + pct(d, [95, 99, 100])
        out[lab + "_share_gt_0p25m"] = round(float((d > 0.25).mean()), 4)
        far = Q[k][d > 0.5]
        out[lab + "_far_gt_0p5m_n"] = int(len(far))
        if len(far):
            out[lab + "_far_gt_0p5m_where"] = dict(x_p5_p50_p95=pct(far[:, 0], [5, 50, 95]), y_p5_p50_p95=pct(far[:, 1], [5, 50, 95]),
                                                   z_p5_p50_p95=pct(far[:, 2], [5, 50, 95]),
                                                   height_above_bed_p5_p50=pct(far[:, 1] - bed(far[:, 0]), [5, 50]))
    out["crest_y_change_m"] = round(R["variants"][n]["upper_crest_y_max"] - R["variants"][base]["upper_crest_y_max"], 4)
    if R["variants"][n]["upper_section_crest_y_max"] is not None:
        out["section_crest_y_change_m"] = round(R["variants"][n]["upper_section_crest_y_max"] - R["variants"][base]["upper_section_crest_y_max"], 4)
    R["variants"][n]["upper_vs_base"] = out
json.dump(R, open(OUT + "/hs_upper_compare_f%04d.json" % FRAME, "w", encoding="utf8"), indent=1, ensure_ascii=False)
for n, v in R["variants"].items():
    print(n, json.dumps(v, ensure_ascii=False))
