# -*- coding: utf-8 -*-
"""Grid-artifact diagnosis of the hero's surface records (read only). 2026-10-18 written new (Claude).

Question (user 10/18 ~16:35): the video shows a visible "grid" - is it a precision problem?  This measures, on the GW45SRF1
surface records of the hero run (DFG-2B-E every-frame re-record), what kind of small-scale structure the mesh has:
  1. triangle edge lengths / areas per region (adaptivity 0.005 of particlefluidsurface makes big triangles on calm water)
  2. dihedral angles between neighbouring faces (how crinkled the mesh is at triangle scale)
  3. vertex-normal noise = angle between the stored vertex normal and a smooth reference normal (area-weighted face normals,
     Gaussian sigma 1.5 m) -> what the shader sees as small-scale shading
  4. bump spectrum: the surface rasterized at 0.1 m (top water: y(x,z); crest face: x(y,z)), plane removed, Hann window, FFT,
     height RMS and slope RMS per wavelength band, and the share of band power within +-10 deg of the grid axes
  5. frame-to-frame: correlation of the 0.5-2 m band between frame f and f+1 (zero lag and best lag <= 1.5 m), and the
     per-pixel normal change split into large-scale (sigma 2 m) and small-scale parts
Tags in the json: measured = read from the records; computed = derived here.  Writes only Unity/Build/FLIP52B/hires/diag_grid/.
  py -3.10 -B h52hs_griddiag.py [frames ...]
"""
import os, sys, json, time
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
sys.dont_write_bytecode = True
sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip45")
import numpy as np                       # noqa: E402
from scipy.spatial import cKDTree        # noqa: E402
from scipy import ndimage                # noqa: E402
import g45_export_unity as E45           # noqa: E402  reader only

REPO = "G:/Unity/GreatWave_2026_Fresh"
RUN = REPO + "/Unity/Build/FLIP52B/hero/runs/DFGB2Er_D19B_xf272p25_dp0p5_c1152_t125_long"
OUT = REPO + "/Unity/Build/FLIP52B/hires/diag_grid"
H = 0.1                                   # raster cell (m)
BANDS = [(0.2, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 4.0), (4.0, 8.0)]


def load(f):
    d = E45.read_frame_bytes(open(RUN + "/surf/s_%05d.gw45s" % f, "rb").read())
    return d["P"], d["N"], d["tri"].astype(np.int64), d["v"].astype(np.float64), d


def face_geo(P, tri):
    a, b, c = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
    cr = np.cross(b - a, c - a)
    ar = 0.5 * np.linalg.norm(cr, axis=1)
    fn = cr / np.maximum(2 * ar[:, None], 1e-15)
    return fn, ar, (a + b + c) / 3.0


def orient(fn, N, tri):
    """Houdini winding is clockwise: flip face normals so they agree with the stored (Houdini point) normals."""
    s = np.sum(fn * (N[tri[:, 0]] + N[tri[:, 1]] + N[tri[:, 2]]), 1)
    return -fn if np.median(s) < 0 else fn, float(np.mean(s * (1 if np.median(s) >= 0 else -1) > 0))


def edge_stats(P, tri, sel):
    t = tri[sel]
    e = np.concatenate([np.linalg.norm(P[t[:, i]] - P[t[:, (i + 1) % 3]], axis=1) for i in range(3)])
    return dict(n_tri=int(sel.sum()), edge_m_p5_25_50_75_95_99_max=[round(float(v), 3) for v in np.percentile(e, [5, 25, 50, 75, 95, 99, 100])])


def dihedral(fn, tri, sel):
    """angle (deg) between face normals across interior edges whose both faces are in sel."""
    idx = np.nonzero(sel)[0]
    t = tri[idx]
    E = np.concatenate([np.sort(t[:, [0, 1]], 1), np.sort(t[:, [1, 2]], 1), np.sort(t[:, [2, 0]], 1)])
    F = np.concatenate([idx, idx, idx])
    key = E[:, 0] * 10_000_000 + E[:, 1]
    o = np.argsort(key, kind="stable")
    k, F = key[o], F[o]
    same = k[1:] == k[:-1]
    f1, f2 = F[:-1][same], F[1:][same]
    ang = np.degrees(np.arccos(np.clip((fn[f1] * fn[f2]).sum(1), -1, 1)))
    return [round(float(v), 2) for v in np.percentile(ang, [50, 90, 95, 99])]


def normal_noise(P, N, tri, fn, ar, cen, vsel, sigma=1.5):
    """angle (deg) between stored vertex normal and the Gaussian(sigma)-weighted area-weighted face normal around the vertex."""
    tree = cKDTree(cen)
    vi = np.nonzero(vsel)[0]
    out = np.empty(len(vi))
    for j, i in enumerate(vi):
        nb = tree.query_ball_point(P[i], 3 * sigma)
        if not nb:
            out[j] = np.nan; continue
        nb = np.asarray(nb)
        w = ar[nb] * np.exp(-((cen[nb] - P[i]) ** 2).sum(1) / (2 * sigma * sigma))
        nn = (fn[nb] * w[:, None]).sum(0)
        # only faces on the same sheet (facing the same side as the vertex normal)
        ok = (fn[nb] @ N[i]) > 0.0
        nn = (fn[nb][ok] * w[ok][:, None]).sum(0)
        nn /= max(np.linalg.norm(nn), 1e-15)
        out[j] = np.degrees(np.arccos(np.clip(nn @ N[i], -1, 1)))
    out = out[np.isfinite(out)]
    return dict(n_vert=int(len(out)), rms_deg=round(float(np.sqrt(np.mean(out ** 2))), 2),
                p50_p90_p95_p99_deg=[round(float(v), 2) for v in np.percentile(out, [50, 90, 95, 99])])


def raster(P, N, tri, fn, ax, win, nthr=0.3, sign=1.0, fmask=None):
    """height w(u,v) on a 0.1 m grid. ax = (iu, iv, iw); win = (u0,u1,v0,v1). Faces with sign*n_w > nthr; top-most hit kept."""
    iu, iv, iw = ax
    u0, u1, v0, v1 = win
    nu, nv = int(round((u1 - u0) / H)), int(round((v1 - v0) / H))
    Hm = np.full((nv, nu), -np.inf); Nm = np.zeros((nv, nu, 3))
    a, b, c = P[tri[:, 0]], P[tri[:, 1]], P[tri[:, 2]]
    umin = np.minimum(np.minimum(a[:, iu], b[:, iu]), c[:, iu]); umax = np.maximum(np.maximum(a[:, iu], b[:, iu]), c[:, iu])
    vmin = np.minimum(np.minimum(a[:, iv], b[:, iv]), c[:, iv]); vmax = np.maximum(np.maximum(a[:, iv], b[:, iv]), c[:, iv])
    sel = (sign * fn[:, iw] > nthr) & (umax >= u0) & (umin <= u1) & (vmax >= v0) & (vmin <= v1)
    if fmask is not None:
        sel &= fmask
    for t in np.nonzero(sel)[0]:
        i0 = max(int(np.floor((umin[t] - u0) / H - 0.5)), 0); i1 = min(int(np.ceil((umax[t] - u0) / H - 0.5)), nu - 1)
        j0 = max(int(np.floor((vmin[t] - v0) / H - 0.5)), 0); j1 = min(int(np.ceil((vmax[t] - v0) / H - 0.5)), nv - 1)
        if i1 < i0 or j1 < j0:
            continue
        uu = u0 + (np.arange(i0, i1 + 1) + 0.5) * H; vv = v0 + (np.arange(j0, j1 + 1) + 0.5) * H
        U, Vv = np.meshgrid(uu, vv)
        A = np.array([a[t, iu], a[t, iv]]); B = np.array([b[t, iu], b[t, iv]]); Cc = np.array([c[t, iu], c[t, iv]])
        den = (B[1] - Cc[1]) * (A[0] - Cc[0]) + (Cc[0] - B[0]) * (A[1] - Cc[1])
        if abs(den) < 1e-12:
            continue
        l1 = ((B[1] - Cc[1]) * (U - Cc[0]) + (Cc[0] - B[0]) * (Vv - Cc[1])) / den
        l2 = ((Cc[1] - A[1]) * (U - Cc[0]) + (A[0] - Cc[0]) * (Vv - Cc[1])) / den
        l3 = 1 - l1 - l2
        ins = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not ins.any():
            continue
        w = l1 * a[t, iw] + l2 * b[t, iw] + l3 * c[t, iw]
        nn = l1[..., None] * N[tri[t, 0]] + l2[..., None] * N[tri[t, 1]] + l3[..., None] * N[tri[t, 2]]
        sub = Hm[j0:j1 + 1, i0:i1 + 1]; subN = Nm[j0:j1 + 1, i0:i1 + 1]
        upd = ins & (w > sub)
        if sign < 0:
            upd = ins & ((-w) > sub)
            sub[upd] = -w[upd]
        else:
            sub[upd] = w[upd]
        subN[upd] = nn[upd]
    valid = np.isfinite(Hm)
    if sign < 0:
        Hm = -Hm
    nl = np.linalg.norm(Nm, axis=2, keepdims=True)
    Nm = Nm / np.maximum(nl, 1e-12)
    return Hm, Nm, valid


def fill(Hm, valid):
    if valid.all():
        return Hm.copy()
    Z = np.where(valid, Hm, 0.0)
    w = ndimage.gaussian_filter(valid.astype(float), 5)
    s = ndimage.gaussian_filter(Z, 5)
    return np.where(valid, Hm, s / np.maximum(w, 1e-9))


def spectrum(Hm, valid):
    Z = fill(Hm, valid)
    ny, nx = Z.shape
    yy, xx = np.mgrid[0:ny, 0:nx]
    A = np.stack([np.ones(Z.size), xx.ravel(), yy.ravel(), (xx ** 2).ravel(), (yy ** 2).ravel(), (xx * yy).ravel()], 1)
    coef, *_ = np.linalg.lstsq(A, Z.ravel(), rcond=None)
    R = Z - (A @ coef).reshape(Z.shape)
    win = np.outer(np.hanning(ny), np.hanning(nx))
    F = np.fft.fft2(R * win)
    pw = np.abs(F) ** 2 / (np.sum(win ** 2))            # Parseval: sum(pw)/N = mean((R*win)^2)/mean(win^2)
    kx = 2 * np.pi * np.fft.fftfreq(nx, H); ky = 2 * np.pi * np.fft.fftfreq(ny, H)
    KX, KY = np.meshgrid(kx, ky)
    K = np.hypot(KX, KY)
    lam = np.where(K > 0, 2 * np.pi / np.maximum(K, 1e-12), np.inf)
    th = np.degrees(np.arctan2(KY, KX)) % 180.0
    near_axis = (np.minimum(th, 180 - th) <= 10) | (np.abs(th - 90) <= 10)
    out = []
    n = Z.size
    for lo, hi in BANDS:
        m = (lam >= lo) & (lam < hi)
        p = pw[m].sum() / n
        s = (pw[m] * K[m] ** 2).sum() / n
        ax = pw[m & near_axis].sum() / max(pw[m].sum(), 1e-30)
        out.append(dict(band_m=[lo, hi], h_rms_mm=round(float(np.sqrt(p)) * 1000, 2), slope_rms_deg=round(float(np.degrees(np.sqrt(s))), 2),
                        axis_share=round(float(ax), 3)))
    # band-pass field 0.5-2 m (for flicker)
    m = (lam >= 0.5) & (lam < 2.0)
    Fb = np.fft.fft2(R)
    bp = np.real(np.fft.ifft2(np.where(m, Fb, 0)))
    return out, bp, R


def corr_best(a, b, maxlag_cells):
    a = a - a.mean(); b = b - b.mean()
    z0 = float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    F = np.fft.fft2(a) * np.conj(np.fft.fft2(b))
    cc = np.real(np.fft.ifft2(F)) / np.sqrt((a * a).sum() * (b * b).sum())
    ny, nx = cc.shape
    best, lag = -2, (0, 0)
    for dy in range(-maxlag_cells, maxlag_cells + 1):
        for dx in range(-maxlag_cells, maxlag_cells + 1):
            v = cc[dy % ny, dx % nx]
            if v > best:
                best, lag = v, (dy, dx)
    return round(z0, 3), round(float(best), 3), [round(lag[0] * H, 2), round(lag[1] * H, 2)]


def ang(N1, N2, m):
    d = np.clip((N1 * N2).sum(-1), -1, 1)
    a = np.degrees(np.arccos(d))[m]
    return [round(float(v), 2) for v in np.percentile(a, [50, 90, 99])]


def smoothN(Nm, valid, sig):
    S = np.stack([ndimage.gaussian_filter(np.where(valid, Nm[..., i], 0), sig) for i in range(3)], -1)
    return S / np.maximum(np.linalg.norm(S, axis=-1, keepdims=True), 1e-12)


# regions: (name, kind, ax, window, extra)  ax for raster: top water y(x,z) = (0,2,1); crest face x(y,z) = (2,1,0)
def regions_for(f):
    # crest x from the hero export (k2 print 265.5 at 2149; k1 262.45 at 1470); other frames: largest y vertex
    return [
        ("seat_water", "top", (0, 2, 1), (270.0, 300.0, 5.0, 35.0)),      # around seat A (284, lateral 20), mirrored side in Unity
        ("calm_far", "top", (0, 2, 1), (320.0, 360.0, 20.0, 60.0)),
        ("offshore", "top", (0, 2, 1), (120.0, 160.0, 20.0, 60.0)),
    ]


def crest_face_window(P, fn, cen):
    top = np.argmax(P[:, 1])
    xc, zc = P[top, 0], P[top, 2]
    return xc, zc


def analyse(f, nxt=True):
    t0 = time.time()
    P, N, tri, V, d = load(f)
    fn, ar, cen = face_geo(P, tri)
    fn, agree = orient(fn, N, tri)
    res = dict(face_normal_agree_share=round(agree, 4), frame=f, t=round(d["t"], 3), nv=d["nv"], nt=d["nt"], quant_half_step_m=round(d["quant_half_step_m"], 5),
               quant_half_step_xyz_m=[round(float(v), 5) for v in (d["hi"] - d["lo"]) / 65535 / 2])
    res["edges_all"] = edge_stats(P, tri, np.ones(len(tri), bool))
    xc, zc = crest_face_window(P, fn, cen)
    res["crest_top_xyz"] = [round(float(P[np.argmax(P[:, 1]), i]), 2) for i in range(3)]
    regs = {}
    F1 = load(f + 1) if nxt else None
    if F1 is not None:
        P1, N1, tri1, V1, d1 = F1
        fn1, ar1, cen1 = face_geo(P1, tri1)
        fn1, _ = orient(fn1, N1, tri1)
    for name, kind, ax, win in regions_for(f):
        u0, u1, v0, v1 = win
        fs = (cen[:, 0] >= u0) & (cen[:, 0] <= u1) & (cen[:, 2] >= v0) & (cen[:, 2] <= v1) & (fn[:, 1] > 0.3)
        vs = (P[:, 0] >= u0 + 2) & (P[:, 0] <= u1 - 2) & (P[:, 2] >= v0 + 2) & (P[:, 2] <= v1 - 2) & (N[:, 1] > 0.3)
        r = dict(window=list(win), kind=kind)
        r.update(edge_stats(P, tri, fs))
        r["tri_area_m2_p50_p95"] = [round(float(v), 3) for v in np.percentile(ar[fs], [50, 95])]
        r["dihedral_deg_p50_p90_p95_p99"] = dihedral(fn, tri, fs)
        r["vnormal_noise_s1p5"] = normal_noise(P, N, tri, fn, ar, cen, vs, 1.5)
        Hm, Nm, valid = raster(P, N, tri, fn, ax, win)
        r["raster_valid"] = round(float(valid.mean()), 4)
        sp, bp, R = spectrum(Hm, valid)
        r["spectrum"] = sp
        vel = V[vs].mean(0) if vs.any() else np.zeros(3)
        r["mean_surface_v"] = [round(float(x), 2) for x in vel]
        # normal noise as the shader sees it: rasterized interpolated vertex normals vs the same field smoothed (sigma 1.5 m)
        Sm = smoothN(Nm, valid, 15)
        inner = valid.copy(); inner[:30, :] = False; inner[-30:, :] = False; inner[:, :30] = False; inner[:, -30:] = False
        r["pixel_normal_vs_s1p5_deg_p50_p90_p99"] = ang(Nm, Sm, inner)
        if F1 is not None:
            Hm1, Nm1, valid1 = raster(P1, N1, tri1, fn1, ax, win)
            sp1, bp1, R1 = spectrum(Hm1, valid1)
            r["next_frame_corr_band0p5_2m"] = dict(zero_lag=None, best=None, lag_m_v_u=None)
            z0, b, lag = corr_best(bp[30:-30, 30:-30], bp1[30:-30, 30:-30], 15)
            r["next_frame_corr_band0p5_2m"] = dict(zero_lag=z0, best_within_1p5m=b, lag_m_v_u=lag,
                                                    expected_shift_m_per_frame_u_v=[round(float(vel[ax[0]] / 24), 3), round(float(vel[ax[1]] / 24), 3)])
            m2 = inner & valid1
            Sm1 = smoothN(Nm1, valid1, 15)
            Lg = smoothN(Nm, valid, 20); Lg1 = smoothN(Nm1, valid1, 20)
            r["frame_step_normal_change_deg_p50_p90_p99"] = dict(total=ang(Nm, Nm1, m2), large_scale_s2m=ang(Lg, Lg1, m2),
                                                                 small_scale_part=None)
            # small-scale part: change of (N - smooth N) residual angles
            dres = np.degrees(np.arccos(np.clip((Nm * Sm).sum(-1), -1, 1)))
            dres1 = np.degrees(np.arccos(np.clip((Nm1 * Sm1).sum(-1), -1, 1)))
            r["frame_step_normal_change_deg_p50_p90_p99"]["residual_angle_f_f1_p50"] = [round(float(np.median(dres[m2])), 2), round(float(np.median(dres1[m2])), 2)]
            # how many triangles change: vertex count change, mean edge change
            if name == "seat_water":
                np.savez_compressed(OUT + "/raster_%05d_%s.npz" % (f, name), H=Hm.astype(np.float32), H1=Hm1.astype(np.float32), bp=bp.astype(np.float32),
                                    bp1=bp1.astype(np.float32), valid=valid, valid1=valid1)
        regs[name] = r
    # crest face: front face of the breaker, x(y,z); window just below the lip
    yc = P[np.argmax(P[:, 1]), 1]
    for name, sgn in (("crest_face_front", 1.0),):
        win = (max(zc - 15, 0.0), zc + 15, 0.5, yc - 1.0)   # (z range) x (y range)
        ax = (2, 1, 0)
        Hm, Nm, valid = raster(P, N, tri, fn, ax, win, nthr=0.3, sign=sgn, fmask=np.abs(cen[:, 0] - xc) < 25)
        fs = (cen[:, 2] >= win[0]) & (cen[:, 2] <= win[1]) & (cen[:, 1] >= win[2]) & (cen[:, 1] <= win[3]) & (sgn * fn[:, 0] > 0.3) & (np.abs(cen[:, 0] - xc) < 25)
        vs = (P[:, 2] >= win[0] + 1) & (P[:, 2] <= win[1] - 1) & (P[:, 1] >= win[2] + 0.5) & (P[:, 1] <= win[3] - 0.5) & (sgn * N[:, 0] > 0.3) & (np.abs(P[:, 0] - xc) < 25)
        r = dict(window_z_y=list(map(float, win)), crest_x=float(xc))
        if fs.sum() > 50:
            r.update(edge_stats(P, tri, fs))
            r["tri_area_m2_p50_p95"] = [round(float(v), 3) for v in np.percentile(ar[fs], [50, 95])]
            r["dihedral_deg_p50_p90_p95_p99"] = dihedral(fn, tri, fs)
            r["vnormal_noise_s1p5"] = normal_noise(P, N, tri, fn, ar, cen, vs, 1.5)
            r["raster_valid"] = round(float(valid.mean()), 4)
            # use only rows/cols fully valid to avoid fill artefacts: crop to the bounding box of valid
            rows = np.nonzero(valid.mean(1) > 0.9)[0]; cols = np.nonzero(valid.mean(0) > 0.9)[0]
            if len(rows) > 40 and len(cols) > 40:
                Hs = Hm[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]; vs2 = valid[rows[0]:rows[-1] + 1, cols[0]:cols[-1] + 1]
                sp, bp, R = spectrum(Hs, vs2)
                r["spectrum"] = sp
                r["spectrum_window_cells"] = list(Hs.shape)
            Sm = smoothN(Nm, valid, 15)
            r["pixel_normal_vs_s1p5_deg_p50_p90_p99"] = ang(Nm, Sm, ndimage.binary_erosion(valid, iterations=20))
        regs[name] = r
    res["regions"] = regs
    res["s"] = round(time.time() - t0, 1)
    return res


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    frames = [int(a) for a in sys.argv[1:]] or [2149]
    allr = []
    for f in frames:
        r = analyse(f)
        allr.append(r)
        print(json.dumps(r, ensure_ascii=False))
        sys.stdout.flush()
    json.dump(dict(tool="Tools/GWWaveGen/flip52hs/h52hs_griddiag.py", run=RUN, raster_cell_m=H, frames=allr), open(OUT + "/griddiag_%s.json" % "_".join(map(str, frames)), "w"), indent=1)
