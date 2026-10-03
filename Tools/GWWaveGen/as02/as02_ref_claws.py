# -*- coding: utf-8 -*-
"""美術の見本02（Q30-2 の C4）：参照モデル（他者の展示作品のスキャン、Q5・Q19・Q20）の爪の「置き方」を数だけで測る（記録と、置き方の目標の数）。
生成器はこのファイルも OBJ も読まない（F13-1）。形・頂点・断面・画像はどこにも書かない（数だけの JSON）。

参照モデル G:/research/model/wave_repair_zbrush2.obj（SHA-256 AB4124F9…3D40）を読み取りのみで開き、SHA-256 を照合してから、
作業計画 9.4 の整列（解B、Docs/Evidence/ArtFirst/26/reference/align_B_upright.json）で Unity の世界へ置いた一時キャッシュ
（Git 対象外の Unity/Build/Polish/sample02/_objcache/）を作る。測り終えたらキャッシュを消し、消したファイルの SHA-256 を記録する。

測り方（measure）：
  1. 波頭の範囲（世界 y が y_lo より上）を、一辺 VOX の格子で中身の詰まった体（偶奇の規則：鉛直の射線が面を何回横切ったか）にする。
  2. 半径 R_OPEN の球で「開く」（収縮してから膨張）。細い指（爪）は消え、太い胴（波頭の塊・唇）は残る。体 − 開いた体 ＝ 指の候補。
  3. 指の候補のつながり（26 近傍）のうち、体積と長さが下限より大きく、開いた胴に触れているもの＝爪 1 本。
  4. 爪ごと：根元（胴に触れる所の重心）、先（根元から指の中の道のりで最も遠い所）、長さ、太さ（体積 / 長さから等価の径）、
     根元の胴の外向きの法線（開いた体をぼかした場の勾配）、出方の角（根元から長さの 30% の所への向きと法線の角）、全体の向きと法線の角、
     巻き（初めの向きと先の向きの角）。
  5. 並び：隣の爪の根元の間隔 / 長さ、隣どうしの向きの開き（外への開き＝扇）、爪の向きと「波頭の外向き（胴の重心から根元への水平の向き）」の角。
  6. 重なり：原画のカメラ（PaintingCam v1。整列は原画視点で合わせてあるので同じ世界）から見て、爪の画素の何割がほかの爪と重なるか、画素ごとの爪の重なりの数。
使い方（リポジトリの根で）：
    py -3.10 -B Tools/GWWaveGen/as02/as02_ref_claws.py cache
    py -3.10 -B Tools/GWWaveGen/as02/as02_ref_claws.py measure
    py -3.10 -B Tools/GWWaveGen/as02/as02_ref_claws.py delete
"""
import hashlib
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage

REPO = "G:/Unity/GreatWave_2026_Fresh"
SRC = r"G:\research\model\wave_repair_zbrush2.obj"
SRC_SHA = "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40"
ALIGN = REPO + "/Docs/Evidence/ArtFirst/26/reference/align_B_upright.json"
CACHE_DIR = REPO + "/Unity/Build/Polish/sample02/_objcache"
CACHE = CACHE_DIR + "/ref_world_tmp.npz"
OUT_DIR = REPO + "/Unity/Build/Polish/sample02/claws/ref"
LOG = OUT_DIR + "/as02_ref_cache_log.json"
OUT = OUT_DIR + "/as02_ref_claw_placement%s.json" % os.environ.get("AS02_TAG", "")

VOX = 0.07        # 格子の一辺 [m]（世界）
Y_LO = 9.0        # 波頭の範囲の下限（世界 y）
R_OPEN = float(os.environ.get("AS02_R_OPEN", "0.42"))     # 開く球の半径 [m]
MIN_VOL = 0.02    # 爪の体積の下限 [m³]
MIN_LEN = float(os.environ.get("AS02_MIN_LEN", "0.8"))     # 爪の長さの下限 [m]


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 22), b""):
            h.update(ch)
    return h.hexdigest()


def load_log():
    if os.path.exists(LOG):
        return json.load(open(LOG, encoding="utf-8"))
    return {"source": os.path.basename(SRC), "source_sha256": SRC_SHA, "events": []}


def save_log(d):
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(d, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def cmd_cache():
    t0 = time.time()
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    if h != SRC_SHA:
        raise SystemExit("参照モデルの SHA-256 が違うので使わない: " + h)
    lines = raw.split(b"\n")
    V = np.array([l.split()[1:4] for l in lines if l.startswith(b"v ")], dtype=np.float64)
    tris, quads = [], []
    for l in lines:
        if not l.startswith(b"f "):
            continue
        p = [int(x.split(b"/")[0]) - 1 for x in l.split()[1:]]
        if len(p) == 3:
            tris.append(p)
        elif len(p) == 4:
            quads.append(p)
        else:
            for j in range(1, len(p) - 1):
                tris.append([p[0], p[j], p[j + 1]])
    del raw, lines
    Q = np.array(quads, np.int64).reshape(-1, 4)
    T = np.array(tris, np.int64).reshape(-1, 3)
    F = np.vstack([T, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
    M4 = np.array(json.load(open(ALIGN, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(CACHE, V=Vu.astype(np.float32), F=F)
    d = load_log()
    d["events"].append({"event": "cache_created", "file": os.path.relpath(CACHE, REPO).replace("\\", "/"), "sha256": sha256_file(CACHE),
                        "bytes": os.path.getsize(CACHE), "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "seconds": round(time.time() - t0, 1), "source_sha256_checked": h,
                        "align": os.path.relpath(ALIGN, REPO).replace("\\", "/"), "align_sha256": sha256_file(ALIGN)})
    save_log(d)
    print("cache", CACHE, len(V), len(F), "%.1fs" % (time.time() - t0))


def cmd_delete():
    d = load_log()
    if os.path.isdir(CACHE_DIR):
        for nm in sorted(os.listdir(CACHE_DIR)):
            fp = os.path.join(CACHE_DIR, nm)
            if os.path.isfile(fp):
                s = sha256_file(fp)
                os.remove(fp)
                d["events"].append({"event": "cache_deleted", "file": os.path.relpath(fp, REPO).replace("\\", "/"), "sha256": s,
                                    "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    left = os.listdir(CACHE_DIR) if os.path.isdir(CACHE_DIR) else []
    if os.path.isdir(CACHE_DIR) and not left:
        os.rmdir(CACHE_DIR)
    d["cache_dir_exists_after_delete"] = os.path.isdir(CACHE_DIR)
    save_log(d)
    print("deleted; left:", left)


def voxelize(V, F, lo, hi, vox):
    """偶奇の規則で中身を詰める。格子 (nx, ny, nz)、中心 lo + (i + 0.5) vox。鉛直（+y）の射線と三角形の交わりを列ごとに集める。"""
    n = np.ceil((hi - lo) / vox).astype(int)
    nx, ny, nz = n
    P0, P1, P2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    xs = np.stack([P0[:, 0], P1[:, 0], P2[:, 0]], 1)
    zs = np.stack([P0[:, 2], P1[:, 2], P2[:, 2]], 1)
    i0 = np.floor((xs.min(1) - lo[0]) / vox - 0.5).astype(int) + 1
    i1 = np.floor((xs.max(1) - lo[0]) / vox - 0.5).astype(int)
    k0 = np.floor((zs.min(1) - lo[2]) / vox - 0.5).astype(int) + 1
    k1 = np.floor((zs.max(1) - lo[2]) / vox - 0.5).astype(int)
    cols, ys = [], []
    span_i = np.clip(i1 - i0 + 1, 0, None)
    span_k = np.clip(k1 - k0 + 1, 0, None)
    has = (span_i > 0) & (span_k > 0) & (i1 >= 0) & (i0 < nx) & (k1 >= 0) & (k0 < nz)
    small = has & (span_i <= 6) & (span_k <= 6)
    big = np.nonzero(has & ~small)[0]
    idx = np.nonzero(small)[0]
    mi = int(span_i[idx].max()) if len(idx) else 0
    mk = int(span_k[idx].max()) if len(idx) else 0

    def hit(sel, ii, kk):
        px = lo[0] + (ii + 0.5) * vox
        pz = lo[2] + (kk + 0.5) * vox
        a, b, c = P0[sel], P1[sel], P2[sel]
        v0x, v0z = b[:, 0] - a[:, 0], b[:, 2] - a[:, 2]
        v1x, v1z = c[:, 0] - a[:, 0], c[:, 2] - a[:, 2]
        v2x, v2z = px - a[:, 0], pz - a[:, 2]
        den = v0x * v1z - v1x * v0z
        ok = np.abs(den) > 1e-14
        den = np.where(ok, den, 1.0)
        u = (v2x * v1z - v1x * v2z) / den
        w = (v0x * v2z - v2x * v0z) / den
        inside = ok & (u >= 0) & (w >= 0) & (u + w <= 1) & (ii >= 0) & (ii < nx) & (kk >= 0) & (kk < nz)
        y = a[:, 1] + u * (b[:, 1] - a[:, 1]) + w * (c[:, 1] - a[:, 1])
        cols.append((ii[inside] * nz + kk[inside]).astype(np.int64))
        ys.append(y[inside])

    for di in range(mi):
        for dk in range(mk):
            sel = idx[(span_i[idx] > di) & (span_k[idx] > dk)]
            if len(sel):
                hit(sel, i0[sel] + di, k0[sel] + dk)
    for t in big:
        a_i = np.arange(max(i0[t], 0), min(i1[t], nx - 1) + 1)
        a_k = np.arange(max(k0[t], 0), min(k1[t], nz - 1) + 1)
        if not len(a_i) or not len(a_k):
            continue
        gi, gk = np.meshgrid(a_i, a_k, indexing="ij")
        gi, gk = gi.ravel(), gk.ravel()
        hit(np.full(len(gi), t), gi, gk)
    cols = np.concatenate(cols)
    ys = np.concatenate(ys)
    o = np.lexsort((ys, cols))
    cols, ys = cols[o], ys[o]
    occ = np.zeros((nx, ny, nz), bool)
    # 列ごとに対にして間を詰める
    starts = np.r_[0, np.nonzero(np.diff(cols))[0] + 1]
    ends = np.r_[starts[1:], len(cols)]
    odd = 0
    for s, e in zip(starts, ends):
        c = cols[s]
        yy = ys[s:e]
        if len(yy) % 2:
            odd += 1
            yy = yy[:-1]
        i, k = divmod(int(c), nz)
        for a_, b_ in zip(yy[0::2], yy[1::2]):
            j0 = max(int(np.ceil((a_ - lo[1]) / vox - 0.5)), 0)
            j1 = min(int(np.floor((b_ - lo[1]) / vox - 0.5)), ny - 1)
            if j1 >= j0:
                occ[i, j0:j1 + 1, k] = True
    return occ, odd


def ball(r):
    k = int(np.ceil(r))
    g = np.mgrid[-k:k + 1, -k:k + 1, -k:k + 1]
    return (g ** 2).sum(0) <= r * r


def cmd_measure():
    t0 = time.time()
    z = np.load(CACHE)
    V = z["V"].astype(np.float64)
    F = z["F"]
    sel_f = (V[F, 1].max(1) > Y_LO - 1.0)
    Fh = F[sel_f]
    used = np.unique(Fh)
    lo = V[used].min(0) - 2 * VOX
    hi = V[used].max(0) + 2 * VOX
    lo[1] = Y_LO
    # 範囲の下の切り口は y_lo で閉じる（偶奇は全体の面で数えるので、下の面も入れる）
    occ, odd = voxelize(V, F, lo, hi, VOX)
    lo3 = lo.copy()
    print("vox", occ.shape, occ.sum(), "odd cols", odd, "%.1fs" % (time.time() - t0), flush=True)
    # 開く
    rb = R_OPEN / VOX
    body = ndimage.binary_opening(occ, structure=ball(rb))
    fing = occ & ~body
    # 指の候補を少し整える（1 画素の薄皮を落とす）
    fing = ndimage.binary_opening(fing, structure=ball(1.0))
    lab, nl = ndimage.label(fing, structure=np.ones((3, 3, 3)))
    print("components", nl, "%.1fs" % (time.time() - t0), flush=True)
    # 胴の外向きの法線の場
    bs = ndimage.gaussian_filter(body.astype(np.float32), 2.0)
    gx, gy, gz = np.gradient(bs)
    body_d = ndimage.binary_dilation(body, structure=ball(1.5))
    objs = ndimage.find_objects(lab)
    claws = []
    cen_body = np.argwhere(body).mean(0) * VOX + lo3 + 0.5 * VOX
    for li, sl in enumerate(objs, start=1):
        if sl is None:
            continue
        m = lab[sl] == li
        nv = int(m.sum())
        vol = nv * VOX ** 3
        if vol < MIN_VOL:
            continue
        off = np.array([s.start for s in sl])
        pts = np.argwhere(m) + off
        touch = body_d[tuple(pts.T)]
        if touch.sum() < 3:
            continue
        P = pts * VOX + lo3 + 0.5 * VOX
        root = P[touch].mean(0)
        # 指の中の道のり（根元の点から幅優先）
        loc = {tuple(p): i for i, p in enumerate(pts)}
        dist = np.full(len(pts), -1, np.int32)
        q = list(np.nonzero(touch)[0])
        for i in q:
            dist[i] = 0
        h = 0
        nb = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1) for c in (-1, 0, 1) if (a, b, c) != (0, 0, 0)]
        while h < len(q):
            i = q[h]
            h += 1
            p = pts[i]
            for d in nb:
                j = loc.get((p[0] + d[0], p[1] + d[1], p[2] + d[2]))
                if j is not None and dist[j] < 0:
                    dist[j] = dist[i] + 1
                    q.append(j)
        if (dist < 0).any():
            dist[dist < 0] = dist.max()
        it = int(np.argmax(dist))
        tip = P[it]
        L = float(np.linalg.norm(tip - root))
        Lg = float(dist.max() * VOX)
        if Lg < MIN_LEN:
            continue
        # 道のりの割合ごとの重心（背骨）
        fr = dist / max(dist.max(), 1)
        spine = []
        for a, b in ((0.0, 0.1), (0.25, 0.35), (0.45, 0.55), (0.65, 0.75), (0.9, 1.01)):
            s = (fr >= a) & (fr < b)
            spine.append(P[s].mean(0) if s.any() else root)
        spine = np.array(spine)
        ijk = np.clip(np.round((root - lo3) / VOX - 0.5).astype(int), 0, np.array(occ.shape) - 1)
        g = -np.array([gx[tuple(ijk)], gy[tuple(ijk)], gz[tuple(ijk)]], np.float64)
        if np.linalg.norm(g) < 1e-9:
            continue
        nrm = g / np.linalg.norm(g)
        d0 = spine[1] - spine[0]
        d0 /= max(np.linalg.norm(d0), 1e-9)
        dall = tip - root
        dall /= max(np.linalg.norm(dall), 1e-9)
        dtip = spine[4] - spine[3]
        dtip /= max(np.linalg.norm(dtip), 1e-9)
        outh = root - cen_body
        outh[1] = 0
        outh /= max(np.linalg.norm(outh), 1e-9)
        claws.append({
            "root": root, "tip": tip, "n": nrm, "d0": d0, "dall": dall, "dtip": dtip, "outh": outh,
            "vol": vol, "len_geo": Lg, "len_chord": L, "diam_eq": float(2 * np.sqrt(vol / (np.pi * max(Lg, 1e-6)))),
            "ang_root_n": float(np.degrees(np.arccos(np.clip(d0 @ nrm, -1, 1)))),
            "ang_all_n": float(np.degrees(np.arccos(np.clip(dall @ nrm, -1, 1)))),
            "curl": float(np.degrees(np.arccos(np.clip(d0 @ dtip, -1, 1)))),
            "down_tip": float(-dtip[1]),
            "out_h": float(np.degrees(np.arccos(np.clip(np.r_[dall[0], 0, dall[2]] @ outh / max(np.linalg.norm([dall[0], dall[2]]), 1e-9), -1, 1)))),
            "pts_world_for_overlap": P,
        })
    print("claws", len(claws), "%.1fs" % (time.time() - t0), flush=True)
    R = np.array([c["root"] for c in claws])
    Lg = np.array([c["len_geo"] for c in claws])
    from scipy.spatial import cKDTree
    tr = cKDTree(R)
    dd, jj = tr.query(R, k=min(4, len(R)))
    nn = dd[:, 1]
    fan = np.array([np.degrees(np.arccos(np.clip(claws[i]["dall"] @ claws[jj[i, 1]]["dall"], -1, 1))) for i in range(len(claws))])
    # 根元の法線どうしの角（胴の曲がり）と、向きの開きの差（扇：向きの開き − 法線の開き）
    nfan = np.array([np.degrees(np.arccos(np.clip(claws[i]["n"] @ claws[jj[i, 1]]["n"], -1, 1))) for i in range(len(claws))])
    # 原画のカメラから見た重なり
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
    import claws_common as CC
    cam = CC.painting_cam()
    W, H = cam.W, cam.H
    cover = np.zeros((H, W), np.int32)
    masks = []
    for c in claws:
        q, zc = cam.project(c["pts_world_for_overlap"])
        ok = zc > 0
        q = np.round(q[ok]).astype(int)
        q = q[(q[:, 0] >= 0) & (q[:, 0] < W) & (q[:, 1] >= 0) & (q[:, 1] < H)]
        mm = np.zeros((H, W), bool)
        mm[q[:, 1], q[:, 0]] = True
        mm = ndimage.binary_closing(mm, iterations=1)
        masks.append(mm)
        cover += mm
    ovl = [float((cover[m] > 1).mean()) if m.any() else 0.0 for m in masks]
    any_px = cover > 0
    # 座席側から見て、爪の根元がどの「列」にあるか（根元の法線の向きの高さで層を数える）：根元の、胴の重心からの距離の分布
    hgt = np.array([c["root"][1] for c in claws])

    def st(x):
        x = np.asarray(x, float)
        return {"n": int(len(x)), "p10": round(float(np.percentile(x, 10)), 3), "p50": round(float(np.percentile(x, 50)), 3),
                "p90": round(float(np.percentile(x, 90)), 3), "mean": round(float(x.mean()), 3)}
    out = {
        "schema": "GreatWave.AS02.ref_claw_placement/1",
        "note_ja": "参照モデル（他者の展示作品のスキャン。参考にとどめ写し取らない、Q19・Q20）から測った爪の置き方の数だけ。形・頂点・画像は書かない。"
                   "生成器はこの数を『置き方の目標の範囲』としてだけ使い、OBJ は読まない（F13-1）。",
        "source": {"file": os.path.basename(SRC), "sha256": SRC_SHA, "align": os.path.relpath(ALIGN, REPO).replace("\\", "/")},
        "method": {"vox_m": VOX, "y_lo_world": Y_LO, "r_open_m": R_OPEN, "min_vol_m3": MIN_VOL, "min_len_m": MIN_LEN,
                   "ja": "波頭の範囲を格子で詰め、半径 r_open の球で開いた体との差を指とした（26 近傍のつながり）。角はどれも度。"},
        "claw_count": len(claws),
        "length_geodesic_m": st(Lg),
        "diameter_equiv_m": st([c["diam_eq"] for c in claws]),
        "length_over_diameter": st(Lg / np.maximum([c["diam_eq"] for c in claws], 1e-6)),
        "angle_root_dir_vs_surface_normal_deg": st([c["ang_root_n"] for c in claws]),
        "angle_overall_dir_vs_surface_normal_deg": st([c["ang_all_n"] for c in claws]),
        "curl_root_to_tip_deg": st([c["curl"] for c in claws]),
        "tip_down_component": st([c["down_tip"] for c in claws]),
        "angle_overall_dir_vs_crest_outward_horizontal_deg": st([c["out_h"] for c in claws]),
        "nearest_root_spacing_m": st(nn),
        "nearest_root_spacing_over_length": st(nn / Lg),
        "fan_angle_to_nearest_deg": st(fan),
        "normal_angle_to_nearest_deg": st(nfan),
        "fan_minus_normal_spread_deg": st(fan - nfan),
        "painting_view_overlap_fraction_per_claw": st(ovl),
        "painting_view_layers_per_claw_pixel": {"p50": float(np.percentile(cover[any_px], 50)) if any_px.any() else 0,
                                                 "p90": float(np.percentile(cover[any_px], 90)) if any_px.any() else 0,
                                                 "max": int(cover.max())},
        "root_height_world_y": st(hgt),
        "elapsed_s": round(time.time() - t0, 1),
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 確かめの図（一時。キャッシュのフォルダーへ置き、delete で消す）：原画のカメラから見た爪の塗り（番号の色）。形の画像なのでリポジトリへ入れない
    import cv2
    img = np.full((H, W, 3), 255, np.uint8)
    bp = np.argwhere(body)[::3] * VOX + lo3 + 0.5 * VOX
    qb, zb = cam.project(bp)
    qb = np.round(qb[zb > 0]).astype(int)
    qb = qb[(qb[:, 0] >= 0) & (qb[:, 0] < W) & (qb[:, 1] >= 0) & (qb[:, 1] < H)]
    img[qb[:, 1], qb[:, 0]] = (190, 190, 190)
    rng = np.random.default_rng(1)
    for m in masks:
        img[m] = rng.integers(40, 220, 3)
    cv2.imwrite(CACHE_DIR + "/tmp_ref_claws_painting%s.png" % os.environ.get("AS02_TAG", ""), img)
    np.save(CACHE_DIR + "/tmp_ref_claw_roots.npy", np.array([np.r_[c["root"], c["tip"], c["n"]] for c in claws]))
    print(json.dumps({k: v for k, v in out.items() if k not in ("note_ja",)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "measure"
    {"cache": cmd_cache, "measure": cmd_measure, "delete": cmd_delete}[cmd]()
