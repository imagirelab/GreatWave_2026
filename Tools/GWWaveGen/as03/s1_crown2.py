# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S1：参照モデルの波頭の冠を、3 つの大きさで開いて測る（数だけ）。s1_obj.py の一時キャッシュ（断面の座標）を読む。
生成器はこのファイルも OBJ も読まない（F13-1）。形・頂点・画像はリポジトリにも成果物にも書かない。
  - 指（digit）：半径 R_DIGIT の球で開いた体との差のつながり（先の細い指）
  - 手（hand）：半径 R_HAND の球で開いた体との差のつながり（掌＋指。一次の指）
  - 手ごとに、その中に入る指の数（枝分かれ）と、指が分かれ始める所（手の根元からの道のりの割合）
道のりは 26 近傍の重み付き（1・√2・√3 × 格子）の最短路（Dijkstra）。
出力：キャッシュのフォルダーの tmp_crown2_raw<tag>.json（数と根元・先の座標。キャッシュと一緒に消す）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s1_crown2.py   （環境変数 S1_VOX・S1_RD・S1_RH・S1_YLO・S1_TAG・S1_BOX）
"""
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s1_obj as SO  # noqa: E402
from s1_crown import voxelize_sec  # noqa: E402

OFFS = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) > (0, 0, 0)]


def opened(din, R, vox):
    er = din > R
    dout = ndimage.distance_transform_edt(~er) * vox
    return dout <= R


def geodesic(m, src, vox):
    """m：成分の箱の中の真偽、src：始まりの真偽。重み付きの 26 近傍の最短路 [m]（届かない所は inf）。"""
    pts = np.argwhere(m)
    n = len(pts)
    idx = -np.ones(m.shape, np.int64)
    idx[tuple(pts.T)] = np.arange(n)
    rows, cols, ws = [], [], []
    for o in OFFS:
        q = pts + np.array(o)
        ok = np.all((q >= 0) & (q < np.array(m.shape)), 1)
        j = np.full(n, -1, np.int64)
        j[ok] = idx[tuple(q[ok].T)]
        ok2 = j >= 0
        rows.append(np.nonzero(ok2)[0])
        cols.append(j[ok2])
        ws.append(np.full(ok2.sum(), vox * np.sqrt(sum(abs(x) for x in o))))
    r = np.concatenate(rows)
    c = np.concatenate(cols)
    w = np.concatenate(ws)
    G = coo_matrix((np.r_[w, w], (np.r_[r, c], np.r_[c, r])), shape=(n, n)).tocsr()
    s = idx[src & m]
    s = s[s >= 0]
    if not len(s):
        return pts, np.full(n, np.inf)
    d = dijkstra(G, directed=False, indices=s, min_only=True)
    return pts, d


def comp_metrics(m, touch, din_sub, off, lo, vox, gfield):
    pts, d = geodesic(m, touch, vox)
    fin = np.isfinite(d)
    if fin.sum() < 3:
        return None
    pts, d = pts[fin], d[fin]
    Lg = float(d.max())
    wpos = lambda ijk: lo + (np.asarray(ijk, float) + 0.5) * vox
    root = wpos(np.argwhere(touch & m).mean(0) + off)
    tip = wpos(pts[int(np.argmax(d))] + off)
    fr = d / max(Lg, 1e-9)
    spine, rad = [], []
    for a_, b_ in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
        s_ = (fr >= a_) & ((fr < b_) if b_ < 1 else (fr <= 1.0))
        if s_.any():
            spine.append(wpos(pts[s_].mean(0) + off))
            rad.append(float(din_sub[tuple(pts[s_].T)].max()))
        else:
            spine.append(spine[-1] if spine else root)
            rad.append(float("nan"))
    spine = np.array(spine)
    ijk = np.clip(np.round((root - lo) / vox - 0.5).astype(int), 0, np.array(gfield[0].shape) - 1)
    g = -np.array([gfield[0][tuple(ijk)], gfield[1][tuple(ijk)], gfield[2][tuple(ijk)]], np.float64)
    unit = lambda v: v / max(np.linalg.norm(v), 1e-9)
    ang = lambda u, v: float(np.degrees(np.arccos(np.clip(u @ v, -1, 1))))
    nrm = unit(g)
    d0 = unit(spine[3] - spine[0])
    dall = unit(tip - root)
    dtip = unit(spine[9] - spine[7])
    up = np.array([0.0, 1.0, 0.0])
    # 骨格の端（指先）：根元からの道のりの割合 > 0.3 の端を、0.25 m 以内でまとめて数える
    from skimage.morphology import skeletonize
    sk = skeletonize(m)
    nbc = ndimage.convolve(sk.astype(np.uint8), np.ones((3, 3, 3), np.uint8), mode="constant").astype(int) - 1
    ends_ = np.argwhere(sk & (nbc == 1))
    dmap = np.full(m.shape, np.nan)
    dmap[tuple(pts.T)] = d
    tips_ = []
    for e in ends_:
        de = dmap[tuple(e)]
        if not np.isfinite(de):
            # 骨格の端が道のりの点にない時は、近い点の値
            k_ = int(np.argmin(np.sum((pts - e) ** 2, 1)))
            de = d[k_]
        if de / max(Lg, 1e-9) > 0.3:
            tips_.append((wpos(e + off), float(de)))
    tips_.sort(key=lambda t: -t[1])
    kept = []
    for p_, de in tips_:
        if all(np.linalg.norm(p_ - q_) > 0.25 for q_, _ in kept):
            kept.append((p_, de))
    n_tips = len(kept)
    tip_fr = [de / max(Lg, 1e-9) for _, de in kept]
    return {"n_tips": n_tips, "tip_fr": tip_fr, "root": root.tolist(), "tip": tip.tolist(), "n": nrm.tolist(), "len_geo": Lg, "len_chord": float(np.linalg.norm(tip - root)),
            "vol": float(m.sum() * vox ** 3), "r_profile": rad, "spine": spine.tolist(),
            "ang_root_n": ang(d0, nrm), "ang_all_n": ang(dall, nrm), "ang_tip_n": ang(dtip, nrm),
            "ang_all_up": ang(dall, up), "ang_tip_up": ang(dtip, up), "ang_root_up": ang(d0, up), "curl": ang(d0, dtip),
            "d0": d0.tolist(), "dall": dall.tolist(), "dtip": dtip.tolist()}, pts, d


def main():
    t0 = time.time()
    VOX = float(os.environ.get("S1_VOX", "0.05"))
    RD = float(os.environ.get("S1_RD", "0.22"))
    RH = float(os.environ.get("S1_RH", "0.70"))
    Y_LO = float(os.environ.get("S1_YLO", "8.0"))
    TAG = os.environ.get("S1_TAG", "")
    box = [float(v) for v in os.environ.get("S1_BOX", "-14.5,16.5,-16.8,16.8").split(",")]
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
    res = {"vox_m": VOX, "r_digit_m": RD, "r_hand_m": RH, "y_lo": Y_LO, "lo": lo.tolist(), "shape": list(occ.shape), "odd_columns": int(odd)}
    st6 = ndimage.generate_binary_structure(3, 1)
    out = {}
    labs = {}
    for nm, R in (("digit", RD), ("hand", RH)):
        body = opened(din, R, VOX)
        fing = occ & ~body
        fing = ndimage.binary_opening(fing, structure=st6)
        lab, nl = ndimage.label(fing, structure=np.ones((3, 3, 3)))
        bs = ndimage.gaussian_filter(body.astype(np.float32), 3.0)
        gfield = np.gradient(bs)
        body_d = ndimage.binary_dilation(body, iterations=2)
        objs = ndimage.find_objects(lab)
        comps = []
        keep_lab = np.zeros(nl + 1, np.int32)
        for li, sl in enumerate(objs, start=1):
            if sl is None:
                continue
            sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in sl)
            m = lab[sl] == li
            if m.sum() * VOX ** 3 < 0.003:
                continue
            touch = m & body_d[sl]
            if touch.sum() < 2:
                continue
            off = np.array([s.start for s in sl])
            r = comp_metrics(m, touch, din[sl], off, lo, VOX, gfield)
            if r is None:
                continue
            mt, pts, dgeo = r
            if mt["len_geo"] < 0.25:
                continue
            mt["label"] = li
            comps.append(mt)
            keep_lab[li] = len(comps)
        out[nm] = comps
        labs[nm] = (lab, keep_lab)
        print(nm, "R", R, "components", nl, "kept", len(comps), "%.1fs" % (time.time() - t0), flush=True)
        if nm == "hand":
            # 胴（手の大きさで開いた体）の頂の線と、前の縁
            na, ny, nc = occ.shape
            cc = lo[2] + (np.arange(nc) + 0.5) * VOX
            top_y = np.full(nc, np.nan)
            top_a = np.full(nc, np.nan)
            occ_top = np.full(nc, np.nan)
            for k in range(nc):
                s2 = body[:, :, k]
                if s2.any():
                    j = np.nonzero(s2.any(0))[0].max()
                    ii = np.nonzero(s2[:, j])[0]
                    top_y[k] = lo[1] + (j + 0.5) * VOX
                    top_a[k] = lo[0] + (ii.mean() + 0.5) * VOX
                s3 = occ[:, :, k]
                if s3.any():
                    occ_top[k] = lo[1] + (np.nonzero(s3.any(0))[0].max() + 0.5) * VOX
            amax = {}
            for yb in np.arange(10.0, 22.01, 1.0):
                j = int((yb - lo[1]) / VOX)
                am = np.full(nc, np.nan)
                for k in range(nc):
                    ii = np.nonzero(body[:, j, k])[0]
                    if len(ii):
                        am[k] = lo[0] + (ii.max() + 0.5) * VOX
                amax["%.0f" % yb] = am.tolist()
            res.update({"c": cc.tolist(), "body_top_y": top_y.tolist(), "body_top_a": top_a.tolist(), "occ_top_y": occ_top.tolist(),
                        "body_amax_at_y": amax})
            # 前から見たすき間（+a から見る）：手の大きさの胴の前の縁の下の帯で、指（手）が覆う割合
            proj_f = fing.any(0)             # (ny, nc)
            proj_b = body.any(0)
            res["front_proj_finger_px"] = int(proj_f.sum())
            res["front_proj_body_px"] = int(proj_b.sum())
            import cv2
            img = np.zeros(proj_b.shape + (3,), np.uint8)
            img[proj_b] = (110, 110, 110)
            img[proj_f & ~proj_b] = (255, 255, 255)
            img[proj_f & proj_b] = (190, 215, 255)
            cv2.imwrite(SO.CACHE_DIR + "/tmp_crown2_front_hand%s.png" % TAG, img[::-1])
        del body, fing
    # 手ごとの指の数：手の成分の中に体積の半分以上が入る指
    labD, keepD = labs["digit"]
    labH, keepH = labs["hand"]
    for h in out["hand"]:
        h["digits"] = []
    for di, dg in enumerate(out["digit"]):
        li = dg["label"]
        m = labD == li
        hv = labH[m]
        hv = hv[hv > 0]
        if not len(hv):
            dg["hand"] = -1
            continue
        vals, cnt = np.unique(hv, return_counts=True)
        k = int(vals[np.argmax(cnt)])
        frac = float(cnt.max() / m.sum())
        hidx = int(keepH[k]) - 1
        dg["hand"] = hidx if (hidx >= 0 and frac >= 0.5) else -1
        if dg["hand"] >= 0:
            out["hand"][hidx]["digits"].append(di)
    # 指が手の中で始まる所：指の根元の点の、手の根元からの道のり / 手の長さ
    for h in out["hand"]:
        li = h["label"]
        sl = ndimage.find_objects((labH == li).astype(np.int8))[0]
        sl = tuple(slice(max(s.start - 2, 0), s.stop + 2) for s in sl)
        m = labH[sl] == li
        body_h = ~m & ndimage.binary_dilation(m, iterations=2) & occ[sl]
        touch = m & ndimage.binary_dilation(body_h, iterations=1)
        pts, dgeo = geodesic(m, touch, VOX)
        if not np.isfinite(dgeo).any():
            h["digit_start_fr"] = []
            continue
        Lh = np.nanmax(np.where(np.isfinite(dgeo), dgeo, np.nan))
        off = np.array([s.start for s in sl])
        idx = {tuple(p): i for i, p in enumerate(pts)}
        fr = []
        for di in h["digits"]:
            r = np.array(out["digit"][di]["root"])
            ijk = tuple(np.round((r - lo) / VOX - 0.5).astype(int) - off)
            # 最も近い手の点
            pp = pts
            k = int(np.argmin(np.sum((pp - np.array(ijk)) ** 2, 1)))
            if np.isfinite(dgeo[k]):
                fr.append(float(dgeo[k] / max(Lh, 1e-9)))
        h["digit_start_fr"] = fr
    res["digit"] = out["digit"]
    res["hand"] = out["hand"]
    res["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(res, open(SO.CACHE_DIR + "/tmp_crown2_raw%s.json" % TAG, "w"), default=float)
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
