# -*- coding: utf-8 -*-
"""Q21 candidate A3b, model side (TEMPORARY, git-ignored outputs only): the reference model's LARGE FORMS as a smoothed
occupancy field in the K* section frame.

  1. the align-B model (temporary cache, candA3b_refcache.py) is taken to the section frame (a, y, c); its own sea
     (median y 1.198 m in align B) is put at still water y = 0;
  2. voxelised by even-odd fill of c-plane slices (0.1 m voxels);
  3. the fingers, claws and sculpt ripples are removed by an anisotropic Gaussian of the occupancy (sigma_a = sigma_y
     = 0.55 m in the section plane, 0.9 m along the crest) and thresholding at 0.5; small detached pieces (claw tips)
     are dropped by 3-D connected components.  What is left: the round shell back, the full body, the barrel, the curl,
     the far-end curl and the b-region lobes as large forms.
The field is written to Unity/Build/Q20L3/candA3b/_tmp (deleted at the end, SHA-256 recorded).  It is used only to
derive per-row target sections for our own sheet (candA3b_fit.py); the model mesh never goes into the repo.
usage: py -3.10 candA3b_model.py <ref_cache.npz> <out_field.npz> [res=0.1]
"""
import sys, os, time, json
import numpy as np
from scipy import ndimage as ndi
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import candA_common as C

REF_SEA = 1.198


def slice_segments(S, F, tri_cmin, tri_cmax, order, c0):
    """segments of the plane c = c0 through the triangles (a, y)."""
    i0 = np.searchsorted(tri_cmin[order], c0, side="right")
    cand = order[:i0]
    cand = cand[tri_cmax[cand] >= c0]
    return C.slice_mesh(S, F, c0, tri_sel=cand)


def fill_slice(segs, a0, na, y0, ny, res):
    img = np.zeros((ny, na), np.uint8)
    if len(segs) == 0:
        return img
    ya = segs[:, 0, 1]; yb = segs[:, 1, 1]; xa = segs[:, 0, 0]; xb = segs[:, 1, 0]
    lo = np.minimum(ya, yb); hi = np.maximum(ya, yb)
    ys = y0 + (np.arange(ny) + 0.5) * res + 1e-7
    for iy in range(ny):
        yv = ys[iy]
        m = (lo <= yv) & (hi > yv)
        if not m.any():
            continue
        t = (yv - ya[m]) / (yb[m] - ya[m])
        xs = np.sort(xa[m] + t * (xb[m] - xa[m]))
        if len(xs) % 2:
            xs = xs[:-1]          # a defect of the scan (open edge): drop the last crossing
        for k in range(0, len(xs) - 1, 2):
            i0 = int(np.ceil((xs[k] - a0) / res - 0.5)); i1 = int(np.floor((xs[k + 1] - a0) / res - 0.5))
            if i1 >= i0:
                img[iy, max(i0, 0):min(i1 + 1, na)] = 1
    return img


def main(cache, out, res=0.1):
    t0 = time.time()
    z = np.load(cache)
    V = z["V"].astype(np.float64); F = z["tris"].astype(np.int64)
    S = C.sec(V); S[:, 1] -= REF_SEA
    lo = np.floor(S.min(0) - 1.5); hi = np.ceil(S.max(0) + 1.5)
    lo[1] = -3.0                               # below the sea is water anyway
    a0, y0, c0 = lo
    na = int(round((hi[0] - a0) / res)); ny = int(round((hi[1] - y0) / res)); nc = int(round((hi[2] - c0) / res))
    tc = S[F][:, :, 2]
    tri_cmin = tc.min(1); tri_cmax = tc.max(1)
    order = np.argsort(tri_cmin)
    occ = np.zeros((nc, ny, na), np.uint8)
    for k in range(nc):
        cc = c0 + (k + 0.5) * res
        segs = slice_segments(S, F, tri_cmin, tri_cmax, order, cc)
        occ[k] = fill_slice(segs, a0, na, y0, ny, res)
        if k % 50 == 0:
            print("slice", k, nc, round(time.time() - t0, 1), flush=True)
    raw_vol = float(occ[:, int(round(-y0 / res)):, :].sum() * res ** 3)
    # large forms: anisotropic Gaussian of the occupancy (fingers / claws / ripples go), threshold 0.5
    sig_ay = float(os.environ.get("A3B_SIG_AY", 0.55)); sig_c = float(os.environ.get("A3B_SIG_C", 0.9))
    f = ndi.gaussian_filter(occ.astype(np.float32), (sig_c / res, sig_ay / res, sig_ay / res), mode="constant")
    big = f > 0.5
    lab, n = ndi.label(big)
    sizes = ndi.sum(big, lab, index=np.arange(1, n + 1))
    keep = 1 + int(np.argmax(sizes))
    big = lab == keep
    f = np.where(big, f, np.minimum(f, 0.49)).astype(np.float32)
    np.savez_compressed(out, field=f.astype(np.float16), occ_raw=np.packbits(occ, axis=-1), shape_raw=np.array(occ.shape),
                        a0=a0, y0=y0, c0=c0, res=res, sig_ay=sig_ay, sig_c=sig_c)
    info = {"shape_c_y_a": [nc, ny, na], "res": res, "origin_a_y_c": [a0, y0, c0], "sigma_ay_m": sig_ay, "sigma_c_m": sig_c,
            "components_after_smoothing": int(n), "kept_voxels": int(big.sum()), "dropped_voxels": int((sizes.sum() - sizes.max())),
            "raw_volume_above_sea_m3": raw_vol, "smoothed_volume_above_sea_m3": float(big[:, int(round(-y0 / res)):, :].sum() * res ** 3),
            "seconds": round(time.time() - t0, 1)}
    json.dump(info, open(os.path.splitext(out)[0] + "_info.json", "w"), indent=1)
    print(json.dumps(info))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.1)
