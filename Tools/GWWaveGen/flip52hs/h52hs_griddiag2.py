# -*- coding: utf-8 -*-
"""Grid-artifact diagnosis, part 2 (read only). 2026-10-18 written new (Claude). Reuses h52hs_griddiag (raster, spectrum).

Per frame and region (top sheet only = faces/vertices within 0.25 m of the rasterized top-most surface):
  edges, edge DIRECTION histogram in the horizontal plane (marching-cubes meshes on an axis-aligned voxel grid have edges at
  0/45/90/135 deg), dihedral angles, vertex-normal noise vs Gaussian 1.5 m reference, height/slope spectrum with the share of
  band power near the grid axes and its isotropic baseline, and the temporal behaviour of the 0.5-2 m band against the 4-16 m
  band for lags of 1..24 frames (a pattern locked to the voxel grid keeps a high zero-lag correlation while the real waves move).
  Writes Unity/Build/FLIP52B/hires/diag_grid/griddiag2_*.json and band-pass maps bp_<frame>_<region>.png (top-down, 0.1 m/px).
  py -3.10 -B h52hs_griddiag2.py 2209 2149 2112 1470
"""
import os, sys, json, time
os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                       # noqa: E402
from scipy.spatial import cKDTree        # noqa: E402
from scipy import ndimage                # noqa: E402
from PIL import Image                    # noqa: E402
import h52hs_griddiag as G               # noqa: E402

H = G.H
OUT = G.OUT
REG = [("seat_near", (274.0, 294.0, 10.0, 30.0)),     # water within ~10 m of seat A (284, lateral 20)
       ("seat_mid", (234.0, 274.0, 0.0, 40.0)),       # what the seat looks at (toward offshore), incl. the breaker
       ("offshore", (120.0, 160.0, 20.0, 60.0))]
LAGS = [1, 3, 6, 12, 24]


def bands(Hm, valid, lo, hi):
    Z = G.fill(Hm, valid)
    ny, nx = Z.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    A = np.stack([np.ones(Z.size), xx.ravel(), yy.ravel(), (xx ** 2).ravel(), (yy ** 2).ravel(), (xx * yy).ravel()], 1)
    coef, *_ = np.linalg.lstsq(A, Z.ravel(), rcond=None)
    R = Z - (A @ coef).reshape(Z.shape)
    kx = 2 * np.pi * np.fft.fftfreq(nx, H); ky = 2 * np.pi * np.fft.fftfreq(ny, H)
    K = np.hypot(*np.meshgrid(kx, ky))
    lam = np.where(K > 0, 2 * np.pi / np.maximum(K, 1e-12), np.inf)
    F = np.fft.fft2(R)
    return np.real(np.fft.ifft2(np.where((lam >= lo) & (lam < hi), F, 0)))


def axis_baseline(shape):
    ny, nx = shape
    kx = 2 * np.pi * np.fft.fftfreq(nx, H); ky = 2 * np.pi * np.fft.fftfreq(ny, H)
    KX, KY = np.meshgrid(kx, ky)
    K = np.hypot(KX, KY)
    lam = np.where(K > 0, 2 * np.pi / np.maximum(K, 1e-12), np.inf)
    th = np.degrees(np.arctan2(KY, KX)) % 180.0
    na = (np.minimum(th, 180 - th) <= 10) | (np.abs(th - 90) <= 10)
    return {str(b): round(float((na & (lam >= b[0]) & (lam < b[1])).sum() / max(((lam >= b[0]) & (lam < b[1])).sum(), 1)), 3) for b in G.BANDS}


def top_masks(P, tri, fn, cen, win, Hm, valid):
    u0, u1, v0, v1 = win
    ny, nx = Hm.shape

    def near_top(X):
        i = np.clip(((X[:, 0] - u0) / H).astype(int), 0, nx - 1); j = np.clip(((X[:, 2] - v0) / H).astype(int), 0, ny - 1)
        ins = (X[:, 0] >= u0) & (X[:, 0] < u1) & (X[:, 2] >= v0) & (X[:, 2] < v1)
        ok = ins & valid[j, i] & (np.abs(X[:, 1] - np.where(valid[j, i], Hm[j, i], -1e9)) < 0.25)
        return ok
    return near_top(P), near_top(cen) & (fn[:, 1] > 0.3)


def edge_dir_hist(P, tri, fs):
    t = tri[fs]
    E = np.concatenate([P[t[:, 1]] - P[t[:, 0]], P[t[:, 2]] - P[t[:, 1]], P[t[:, 0]] - P[t[:, 2]]])
    L = np.linalg.norm(E[:, [0, 2]], axis=1)
    a = np.degrees(np.arctan2(E[:, 2], E[:, 0])) % 180.0
    h, _ = np.histogram(a, bins=36, range=(0, 180), weights=L)
    h = h / h.sum()
    near = lambda c: float(h[[int(((c + d) % 180) // 5) for d in (-2.5, 2.4)]].sum())   # 5-deg bins centred near c: [c-2.5, c+2.5)
    # share of edge length within +-5 deg of 0, 45, 90, 135 (4 x 10 deg of 180 = 22 % if directions were uniform)
    m = np.zeros(36, bool)
    for c in (0, 45, 90, 135):
        for b in range(36):
            mid = b * 5 + 2.5
            if min(abs(mid - c), 180 - abs(mid - c)) <= 5:
                m[b] = True
    return dict(share_len_within_5deg_of_0_45_90_135=round(float(h[m].sum()), 3), uniform_baseline=round(float(m.sum() / 36), 3),
                hist5deg=[round(float(v), 3) for v in h])


def save_map(bp, valid, path, clip=None):
    c = clip or max(np.percentile(np.abs(bp[valid]), 99), 1e-6)
    img = np.clip(0.5 + 0.5 * bp / c, 0, 1)
    img = np.where(valid, img, 0.0)
    im = Image.fromarray((img[::-1] * 255).astype(np.uint8))      # north-up: z grows upward
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    im.save(path)
    return round(float(c) * 1000, 2)


def analyse(f):
    t0 = time.time()
    P, N, tri, V, d = G.load(f)
    fn, ar, cen = G.face_geo(P, tri)
    fn, _ = G.orient(fn, N, tri)
    res = dict(frame=f, t=round(d["t"], 3), nv=d["nv"], nt=d["nt"], crest_top_xyz=[round(float(P[np.argmax(P[:, 1]), i]), 2) for i in range(3)])
    later = {}
    for k in LAGS:
        p = G.RUN + "/surf/s_%05d.gw45s" % (f + k)
        if os.path.exists(p):
            later[k] = G.load(f + k)
    regs = {}
    for name, win in REG:
        Hm, Nm, valid = G.raster(P, N, tri, fn, (0, 2, 1), win)
        vt, ft = top_masks(P, tri, fn, cen, win, Hm, valid)
        r = dict(window_x_z=list(win), raster_valid=round(float(valid.mean()), 4), n_top_tri=int(ft.sum()))
        if ft.sum() < 50:
            regs[name] = r; continue
        r.update(G.edge_stats(P, tri, ft))
        r["tri_area_m2_p50_p95"] = [round(float(v), 3) for v in np.percentile(ar[ft], [50, 95])]
        r["edge_dir"] = edge_dir_hist(P, tri, ft)
        r["dihedral_deg_p50_p90_p95_p99"] = G.dihedral(fn, tri, ft)
        inner_v = vt & (P[:, 0] > win[0] + 2) & (P[:, 0] < win[1] - 2) & (P[:, 2] > win[2] + 2) & (P[:, 2] < win[3] - 2)
        # normal noise restricted to top-sheet faces
        r["vnormal_noise_s1p5_top"] = G.normal_noise(P, N, tri[ft], fn[ft], ar[ft], cen[ft], inner_v, 1.5)
        sp, bp, R = G.spectrum(Hm, valid)
        r["spectrum"] = sp
        r["axis_share_isotropic_baseline"] = axis_baseline(Hm.shape)
        Sm = G.smoothN(Nm, valid, 15)
        inner = ndimage.binary_erosion(valid, iterations=30)
        r["pixel_normal_vs_s1p5_deg_p50_p90_p99"] = G.ang(Nm, Sm, inner)
        r["mean_surface_v_xyz"] = [round(float(x), 2) for x in V[vt].mean(0)]
        r["map_clip_mm"] = save_map(bp, valid, OUT + "/bp_%05d_%s.png" % (f, name))
        small0 = bp; large0 = bands(Hm, valid, 4.0, 16.0)
        tl = {}
        for k, Fk in later.items():
            P1, N1, tri1, V1, d1 = Fk
            fn1, ar1, cen1 = G.face_geo(P1, tri1); fn1, _ = G.orient(fn1, N1, tri1)
            Hm1, Nm1, valid1 = G.raster(P1, N1, tri1, fn1, (0, 2, 1), win)
            if valid1.mean() < 0.8:
                continue
            _, bp1, _ = G.spectrum(Hm1, valid1)
            large1 = bands(Hm1, valid1, 4.0, 16.0)
            sl = (slice(30, -30), slice(30, -30))
            z0, b, lag = G.corr_best(small0[sl], bp1[sl], 15)
            zl, bl, lagl = G.corr_best(large0[sl], large1[sl], 15)
            m2 = inner & valid1
            tl[k] = dict(band0p5_2m=dict(zero_lag=z0, best_le_1p5m=b, lag_m=lag), band4_16m=dict(zero_lag=zl, best_le_1p5m=bl, lag_m=lagl),
                         pixel_normal_change_deg_p50_p90_p99=G.ang(Nm, Nm1, m2))
        r["temporal"] = tl
        regs[name] = r
    res["regions"] = regs
    res["s"] = round(time.time() - t0, 1)
    return res


if __name__ == "__main__":
    frames = [int(a) for a in sys.argv[1:]] or [2209]
    allr = []
    for f in frames:
        r = analyse(f)
        allr.append(r)
        print(json.dumps(r, ensure_ascii=False)); sys.stdout.flush()
    json.dump(dict(tool="Tools/GWWaveGen/flip52hs/h52hs_griddiag2.py", run=G.RUN, raster_cell_m=H, frames=allr),
              open(OUT + "/griddiag2_%s.json" % "_".join(map(str, frames)), "w"), indent=1)
