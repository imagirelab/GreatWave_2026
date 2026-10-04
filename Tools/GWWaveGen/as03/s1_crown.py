# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの波頭の冠（白い指）を数だけ測る。s1_obj.py の一時キャッシュ（断面の座標）を読む。
生成器はこのファイルも OBJ も読まない（F13-1）。結果は数だけ（キャッシュのフォルダーの一時の JSON → s1_numbers.py が数をまとめる）。
確かめの一時の図（形の画像）はキャッシュのフォルダーに置き、s1_obj.py delete で消す。

測り方：
  1. 範囲（y > y_lo）を一辺 VOX の格子で中身の詰まった体にする（y の向きの射線の偶奇）。
  2. 半径 R_OPEN の球で開く（距離変換で：内の距離 > R の芯を R だけ太らせる）。体 − 開いた体 ＝ 指の候補。
  3. つながり（26 近傍）ごとに、根元（胴に触れる所）から指の中の道のりを測り、長さ・太さの変化（10 区間の半径）・骨格の端と分かれ目・向きを出す。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_crown.py   （環境変数 S1_VOX・S1_ROPEN・S1_YLO・S1_MINLEN・S1_TAG・S1_BOX）
"""
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402


def voxelize_sec(V, F, lo, hi, vox):
    """断面の座標 (a, y, c) の格子で、偶奇の規則で中身を詰める（+y の向きの射線）。格子 (na, ny, nc)。"""
    n = np.ceil((hi - lo) / vox).astype(int)
    na, ny, nc = n
    sel = (V[F, 0].max(1) >= lo[0]) & (V[F, 0].min(1) <= hi[0]) & (V[F, 2].max(1) >= lo[2]) & (V[F, 2].min(1) <= hi[2])
    Fs = F[sel]
    P0, P1, P2 = V[Fs[:, 0]], V[Fs[:, 1]], V[Fs[:, 2]]
    xs = np.stack([P0[:, 0], P1[:, 0], P2[:, 0]], 1)
    zs = np.stack([P0[:, 2], P1[:, 2], P2[:, 2]], 1)
    i0 = np.floor((xs.min(1) - lo[0]) / vox - 0.5).astype(int) + 1
    i1 = np.floor((xs.max(1) - lo[0]) / vox - 0.5).astype(int)
    k0 = np.floor((zs.min(1) - lo[2]) / vox - 0.5).astype(int) + 1
    k1 = np.floor((zs.max(1) - lo[2]) / vox - 0.5).astype(int)
    span_i = np.clip(i1 - i0 + 1, 0, None)
    span_k = np.clip(k1 - k0 + 1, 0, None)
    idx = np.nonzero((span_i > 0) & (span_k > 0))[0]
    cols, ys = [], []

    def hit(sel_, ii, kk):
        px = lo[0] + (ii + 0.5) * vox
        pz = lo[2] + (kk + 0.5) * vox
        a, b, c = P0[sel_], P1[sel_], P2[sel_]
        v0x, v0z = b[:, 0] - a[:, 0], b[:, 2] - a[:, 2]
        v1x, v1z = c[:, 0] - a[:, 0], c[:, 2] - a[:, 2]
        v2x, v2z = px - a[:, 0], pz - a[:, 2]
        den = v0x * v1z - v1x * v0z
        ok = np.abs(den) > 1e-14
        den = np.where(ok, den, 1.0)
        u = (v2x * v1z - v1x * v2z) / den
        w = (v0x * v2z - v2x * v0z) / den
        inside = ok & (u >= 0) & (w >= 0) & (u + w <= 1) & (ii >= 0) & (ii < na) & (kk >= 0) & (kk < nc)
        y = a[:, 1] + u * (b[:, 1] - a[:, 1]) + w * (c[:, 1] - a[:, 1])
        cols.append((ii[inside] * nc + kk[inside]).astype(np.int64))
        ys.append(y[inside])

    small = idx[(span_i[idx] <= 12) & (span_k[idx] <= 12)]
    big = idx[(span_i[idx] > 12) | (span_k[idx] > 12)]
    if len(small):
        mi = int(span_i[small].max())
        mk = int(span_k[small].max())
        for di in range(mi):
            for dk in range(mk):
                s_ = small[(span_i[small] > di) & (span_k[small] > dk)]
                if len(s_):
                    hit(s_, i0[s_] + di, k0[s_] + dk)
    for t in big:
        a_i = np.arange(max(i0[t], 0), min(i1[t], na - 1) + 1)
        a_k = np.arange(max(k0[t], 0), min(k1[t], nc - 1) + 1)
        if not len(a_i) or not len(a_k):
            continue
        gi, gk = np.meshgrid(a_i, a_k, indexing="ij")
        hit(np.full(gi.size, t), gi.ravel(), gk.ravel())
    cols = np.concatenate(cols)
    ys = np.concatenate(ys)
    o = np.lexsort((ys, cols))
    cols, ys = cols[o], ys[o]
    occ = np.zeros((na, ny, nc), bool)
    starts = np.r_[0, np.nonzero(np.diff(cols))[0] + 1]
    ends = np.r_[starts[1:], len(cols)]
    odd = 0
    for s, e in zip(starts, ends):
        c = cols[s]
        yy = ys[s:e]
        if len(yy) % 2:
            odd += 1
            yy = yy[:-1]
        i, k = divmod(int(c), nc)
        for a_, b_ in zip(yy[0::2], yy[1::2]):
            j0 = max(int(np.ceil((a_ - lo[1]) / vox - 0.5)), 0)
            j1 = min(int(np.floor((b_ - lo[1]) / vox - 0.5)), ny - 1)
            if j1 >= j0:
                occ[i, j0:j1 + 1, k] = True
    return occ, odd


def main():
    from skimage.morphology import skeletonize
    import cv2
    t0 = time.time()
    VOX = float(os.environ.get("S1_VOX", "0.06"))
    R_OPEN = float(os.environ.get("S1_ROPEN", "0.42"))
    Y_LO = float(os.environ.get("S1_YLO", "8.0"))
    MIN_LEN = float(os.environ.get("S1_MINLEN", "0.35"))
    TAG = os.environ.get("S1_TAG", "")
    box = [float(v) for v in os.environ.get("S1_BOX", "-14.5,16.5,-16.8,16.8").split(",")]   # a0,a1,c0,c1
    V, F = SO.load()
    hi = np.array([box[1], V[:, 1].max() + VOX, box[3]])
    lo_full = np.array([box[0], V[:, 1].min() - VOX, box[2]])
    occ_full, odd = voxelize_sec(V, F, lo_full, hi, VOX)
    j_cut = int(round((Y_LO - lo_full[1]) / VOX))
    occ = occ_full[:, j_cut:, :].copy()
    del occ_full
    lo = lo_full.copy()
    lo[1] = lo_full[1] + j_cut * VOX
    print("vox", occ.shape, int(occ.sum()), "odd", odd, "%.1fs" % (time.time() - t0), flush=True)
    din = (ndimage.distance_transform_edt(occ) * VOX).astype(np.float32)
    er = din > R_OPEN
    dout = (ndimage.distance_transform_edt(~er) * VOX).astype(np.float32)
    body = dout <= R_OPEN
    del dout, er
    fing = occ & ~body
    fing = ndimage.binary_opening(fing, structure=ndimage.generate_binary_structure(3, 1))
    lab, nl = ndimage.label(fing, structure=np.ones((3, 3, 3)))
    print("components", nl, "%.1fs" % (time.time() - t0), flush=True)
    bs = ndimage.gaussian_filter(body.astype(np.float32), 3.0)
    gx, gy, gz = np.gradient(bs)
    body_d = ndimage.binary_dilation(body, iterations=2)
    objs = ndimage.find_objects(lab)

    def wpos(ijk):
        return lo + (np.asarray(ijk, float) + 0.5) * VOX

    def unit(v):
        return v / max(np.linalg.norm(v), 1e-9)

    def ang(u, v):
        return float(np.degrees(np.arccos(np.clip(u @ v, -1, 1))))

    up = np.array([0.0, 1.0, 0.0])
    fwd = np.array([1.0, 0.0, 0.0])
    st26 = np.ones((3, 3, 3), bool)
    claws = []
    for li, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in sl)
        m = lab[sl] == li
        nv = int(m.sum())
        if nv * VOX ** 3 < 0.004:
            continue
        off = np.array([s.start for s in sl])
        touch = m & body_d[sl]
        if touch.sum() < 2:
            continue
        dist = np.full(m.shape, -1, np.int32)
        front = touch.copy()
        dist[front] = 0
        seen = front.copy()
        k = 0
        while front.any() and k < 3000:
            k += 1
            nxt = ndimage.binary_dilation(front, structure=st26) & m & ~seen
            dist[nxt] = k
            seen |= nxt
            front = nxt
        Lg = float(dist.max() * VOX)
        if Lg < MIN_LEN:
            continue
        pts = np.argwhere(m & (dist >= 0))
        dd = dist[tuple(pts.T)]
        root = wpos(np.argwhere(touch).mean(0) + off)
        it = int(np.argmax(dd))
        tip = wpos(pts[it] + off)
        fr = dd / max(dd.max(), 1)
        spine, rad = [], []
        dsub = din[sl]
        bands = np.linspace(0, 1, 11)
        for a_, b_ in zip(bands[:-1], bands[1:]):
            s_ = (fr >= a_) & ((fr < b_) if b_ < 1 else (fr <= 1.0))
            if s_.any():
                spine.append(wpos(pts[s_].mean(0) + off))
                rad.append(float(dsub[tuple(pts[s_].T)].max()))
            else:
                spine.append(spine[-1] if spine else root)
                rad.append(float("nan"))
        spine = np.array(spine)
        rad = np.array(rad)
        sk = skeletonize(m)
        nb = ndimage.convolve(sk.astype(np.uint8), np.ones((3, 3, 3), np.uint8), mode="constant").astype(int) - 1
        ends_ = np.argwhere(sk & (nb == 1))
        brs_ = np.argwhere(sk & (nb >= 3))
        end_fr = [float(dist[tuple(e)]) / max(dd.max(), 1) for e in ends_]
        free_ends = [f for f in end_fr if f > 0.25]
        # 分かれ目：近い分かれ目の画素をまとめる（2 画素以内）
        brf = []
        if len(brs_):
            lb, nbl = ndimage.label(ndimage.binary_dilation(_mask_from(brs_, m.shape), iterations=1))
            for q in range(1, nbl + 1):
                pp = np.argwhere(lb == q)
                dq = dist[tuple(pp.T)]
                dq = dq[dq >= 0]
                if len(dq):
                    brf.append(float(dq.mean()) / max(dd.max(), 1))
        ijk = np.clip(np.round((root - lo) / VOX - 0.5).astype(int), 0, np.array(occ.shape) - 1)
        g = -np.array([gx[tuple(ijk)], gy[tuple(ijk)], gz[tuple(ijk)]], np.float64)
        nrm = unit(g)
        d0 = unit(spine[3] - spine[0])
        dall = unit(tip - root)
        dtip = unit(spine[9] - spine[7])
        claws.append({
            "root": root.tolist(), "tip": tip.tolist(), "n": nrm.tolist(), "len_geo": Lg, "len_chord": float(np.linalg.norm(tip - root)),
            "vol": nv * VOX ** 3, "r_profile": rad.tolist(), "free_ends": len(free_ends), "end_fr": sorted(free_ends),
            "branch_fr": sorted(brf),
            "ang_root_n": ang(d0, nrm), "ang_all_n": ang(dall, nrm), "ang_tip_n": ang(dtip, nrm),
            "ang_all_up": ang(dall, up), "ang_tip_up": ang(dtip, up), "ang_root_up": ang(d0, up),
            "ang_all_fwd": ang(dall, fwd), "curl": ang(d0, dtip),
            "d0": d0.tolist(), "dall": dall.tolist(), "dtip": dtip.tolist(), "spine": spine.tolist(),
        })
    print("claws", len(claws), "%.1fs" % (time.time() - t0), flush=True)
    na, ny, nc = occ.shape
    cc = lo[2] + (np.arange(nc) + 0.5) * VOX
    top_y = np.full(nc, np.nan)
    top_a = np.full(nc, np.nan)
    for k in range(nc):
        s2 = body[:, :, k]
        if not s2.any():
            continue
        j = np.nonzero(s2.any(0))[0].max()
        ii = np.nonzero(s2[:, j])[0]
        top_y[k] = lo[1] + (j + 0.5) * VOX
        top_a[k] = lo[0] + (ii.mean() + 0.5) * VOX
    occ_top = np.full(nc, np.nan)
    for k in range(nc):
        s2 = occ[:, :, k]
        if s2.any():
            occ_top[k] = lo[1] + (np.nonzero(s2.any(0))[0].max() + 0.5) * VOX
    lip = {}
    for yb in np.arange(10.0, 22.01, 1.0):
        j = int((yb - lo[1]) / VOX)
        if 0 <= j < ny:
            amax = np.full(nc, np.nan)
            amin = np.full(nc, np.nan)
            for k in range(nc):
                ii = np.nonzero(body[:, j, k])[0]
                if len(ii):
                    amax[k] = lo[0] + (ii.max() + 0.5) * VOX
                    amin[k] = lo[0] + (ii.min() + 0.5) * VOX
            lip["%.0f" % yb] = {"amax": amax.tolist(), "amin": amin.tolist()}
    res = {"vox_m": VOX, "r_open_m": R_OPEN, "y_lo": Y_LO, "min_len_m": MIN_LEN, "lo": lo.tolist(), "shape": list(occ.shape),
           "odd_columns": int(odd), "c": cc.tolist(), "body_top_y": top_y.tolist(), "body_top_a": top_a.tolist(),
           "occ_top_y": occ_top.tolist(), "body_a_at_y": lip, "claws": claws, "n_components": int(nl),
           "finger_voxels": int(fing.sum()), "elapsed_s": round(time.time() - t0, 1)}
    os.makedirs(SO.CACHE_DIR, exist_ok=True)
    json.dump(res, open(SO.CACHE_DIR + "/tmp_crown_raw%s.json" % TAG, "w"), default=float)
    # 確かめの一時の図（形の画像。キャッシュのフォルダーに置き、delete で消す）：前・横・上から見た胴（灰）と指（白）
    for nm, ax, tr in (("front", 0, lambda x: x[::-1]), ("side", 2, lambda x: np.transpose(x, (1, 0, 2))[::-1]), ("top", 1, lambda x: x)):
        pb = body.any(ax)
        pf = fing.any(ax)
        if ax == 0:
            pb, pf = pb, pf          # (ny, nc)
        img = np.zeros(pb.shape + (3,), np.uint8)
        img[pb] = (110, 110, 110)
        img[pf & ~pb] = (255, 255, 255)
        img[pf & pb] = (190, 215, 255)
        cv2.imwrite(SO.CACHE_DIR + "/tmp_crown_%s%s.png" % (nm, TAG), tr(img))
    print("done %.1fs" % (time.time() - t0))


def _mask_from(ijk, shape):
    m = np.zeros(shape, bool)
    if len(ijk):
        m[tuple(np.asarray(ijk).T)] = True
    return m


if __name__ == "__main__":
    main()
