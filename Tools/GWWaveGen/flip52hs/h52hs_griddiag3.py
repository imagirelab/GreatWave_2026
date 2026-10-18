# -*- coding: utf-8 -*-
"""Grid-artifact diagnosis, part 3 (read only). 2026-10-18 written new (Claude). Reuses h52hs_griddiag (raster).

Part 2's FFT band-pass (no window) rang at the window borders; this part uses local Difference-of-Gaussian bands instead
(no wrap-around): small = G(0.15 m) - G(0.6 m) (passes ~0.5-2.5 m), large = G(1.0 m) - G(4.0 m) (~4-16 m), 2 m border dropped.
  - temporal correlation of each band between frame f and f+k (zero lag, best lag within 1.5 m)
  - shading map: the rasterized interpolated vertex normal minus the same field smoothed with sigma 1.5 m (x and z parts,
    grey = 0, +-3 deg full scale), the field the water shader turns into light; f and f+12 side by side
  - wireframe of the top-sheet triangles, top-down, same window
  py -3.10 -B h52hs_griddiag3.py 2149 2209 1470
"""
import os, sys, json
os.environ.setdefault("OMP_NUM_THREADS", "2")
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np                       # noqa: E402
from scipy import ndimage                # noqa: E402
from PIL import Image, ImageDraw         # noqa: E402
import h52hs_griddiag as G               # noqa: E402

H = G.H
OUT = G.OUT
REG = [("seat_near", (274.0, 294.0, 10.0, 30.0)), ("offshore", (120.0, 160.0, 20.0, 60.0)), ("seat_mid", (234.0, 274.0, 0.0, 40.0))]
LAGS = [1, 3, 6, 12, 24]
B = 20                                    # border cells dropped (2 m)


def dog(Z, s1, s2):
    return ndimage.gaussian_filter(Z, s1 / H, mode="nearest") - ndimage.gaussian_filter(Z, s2 / H, mode="nearest")


def corr(a, b, maxlag):
    best, lag = -2.0, (0, 0)
    ny, nx = a.shape
    z0 = None
    for dy in range(-maxlag, maxlag + 1, 1):
        for dx in range(-maxlag, maxlag + 1, 1):
            aa = a[max(dy, 0):ny + min(dy, 0), max(dx, 0):nx + min(dx, 0)]
            bb = b[max(-dy, 0):ny + min(-dy, 0), max(-dx, 0):nx + min(-dx, 0)]
            aa = aa - aa.mean(); bb = bb - bb.mean()
            c = float((aa * bb).sum() / np.sqrt((aa * aa).sum() * (bb * bb).sum() + 1e-30))
            if dy == 0 and dx == 0:
                z0 = c
            if c > best:
                best, lag = c, (dy, dx)
    return round(z0, 3), round(best, 3), [round(lag[0] * H, 2), round(lag[1] * H, 2)]


def rast(f, win):
    P, N, tri, V, d = G.load(f)
    fn, ar, cen = G.face_geo(P, tri); fn, _ = G.orient(fn, N, tri)
    Hm, Nm, valid = G.raster(P, N, tri, fn, (0, 2, 1), win)
    return P, tri, fn, Hm, Nm, valid


def shade_map(Nm, valid, scale_deg=3.0):
    S = G.smoothN(Nm, valid, 15)
    dx = np.degrees(Nm[..., 0] - S[..., 0]); dz = np.degrees(Nm[..., 2] - S[..., 2])
    g = lambda a: np.clip(0.5 + 0.5 * a / scale_deg, 0, 1)
    img = np.concatenate([g(dx), np.ones((dx.shape[0], 4)), g(dz)], 1)
    return img, float(np.sqrt(np.mean((dx[valid] ** 2 + dz[valid] ** 2))))


def wire(P, tri, fn, Hm, valid, win, px_per_m=20):
    u0, u1, v0, v1 = win
    W, Hh = int((u1 - u0) * px_per_m), int((v1 - v0) * px_per_m)
    im = Image.new("L", (W, Hh), 255); dr = ImageDraw.Draw(im)
    cen = (P[tri[:, 0]] + P[tri[:, 1]] + P[tri[:, 2]]) / 3
    ny, nx = Hm.shape
    i = np.clip(((cen[:, 0] - u0) / H).astype(int), 0, nx - 1); j = np.clip(((cen[:, 2] - v0) / H).astype(int), 0, ny - 1)
    ins = (cen[:, 0] >= u0) & (cen[:, 0] < u1) & (cen[:, 2] >= v0) & (cen[:, 2] < v1) & (fn[:, 1] > 0.3)
    top = ins & valid[j, i] & (np.abs(cen[:, 1] - np.where(valid[j, i], Hm[j, i], -1e9)) < 0.25)
    for t in np.nonzero(top)[0]:
        pts = [((P[k, 0] - u0) * px_per_m, Hh - (P[k, 2] - v0) * px_per_m) for k in tri[t]]
        dr.polygon(pts, outline=0)
    return im


def main(frames):
    res = []
    for f in frames:
        rf = dict(frame=f, regions={})
        for name, win in REG:
            P, tri, fn, Hm, Nm, valid = rast(f, win)
            if valid.mean() < 0.9:
                continue
            Z = G.fill(Hm, valid)
            s0 = dog(Z, 0.15, 0.6)[B:-B, B:-B]; l0 = dog(Z, 1.0, 4.0)[B:-B, B:-B]
            r = dict(window_x_z=list(win), small_rms_mm=round(float(s0.std()) * 1000, 2), large_rms_mm=round(float(l0.std()) * 1000, 2), lags={})
            img0, rms0 = shade_map(Nm, valid)
            r["shade_dev_rms_deg"] = round(rms0, 2)
            for k in LAGS:
                p = G.RUN + "/surf/s_%05d.gw45s" % (f + k)
                if not os.path.exists(p):
                    continue
                P1, tri1, fn1, Hm1, Nm1, valid1 = rast(f + k, win)
                if valid1.mean() < 0.9:
                    continue
                Z1 = G.fill(Hm1, valid1)
                s1 = dog(Z1, 0.15, 0.6)[B:-B, B:-B]; l1 = dog(Z1, 1.0, 4.0)[B:-B, B:-B]
                r["lags"][k] = dict(small_0p5_2m=corr(s0, s1, 15), large_4_16m=corr(l0, l1, 15))
                if k == 12 and name in ("seat_near", "offshore"):
                    img1, _ = shade_map(Nm1, valid1)
                    both = np.concatenate([img0, np.ones((6, img0.shape[1])), img1], 0)
                    Image.fromarray((both[::-1] * 255).astype(np.uint8)).save(OUT + "/shade_%05d_and_%05d_%s.png" % (f, f + k, name))
            if name in ("seat_near", "offshore"):
                wire(P, tri, fn, Hm, valid, win).save(OUT + "/wire_%05d_%s.png" % (f, name))
            rf["regions"][name] = r
            print(f, name, json.dumps(r)); sys.stdout.flush()
        res.append(rf)
    json.dump(dict(tool="Tools/GWWaveGen/flip52hs/h52hs_griddiag3.py", run=G.RUN, frames=res), open(OUT + "/griddiag3_%s.json" % "_".join(map(str, frames)), "w"), indent=1)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [2149])
