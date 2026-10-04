# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S の 3・4（Q32）：参照モデル（他者の展示作品のスキャン。参考にとどめ写し取らない）から、
大きな形の「数だけ」を測る。生成器はこのファイルも OBJ も読まない（F13-1）。形・頂点・断面・画像はリポジトリにも成果物にも書かない。

1. 波峰線の向き（c）の長さ：c ごとの頂の高さ H(c) と、高さの帯（0.1〜0.9 H）ごとの c の幅。主役波 AS02C と同じ定義で比べる。
2. 原画のカメラから見た区域 ①②③④・出っ張りの所の、参照モデルの面の位置（a・y・c・カメラからの距離）。主役波と並べる。
3. 層：区域ごとに射線の交点の列（入る・出る）を数え、②・③ が主の体の前に出た房か、奥の面とどれだけ離れているかを数で読む。
4. ④：原画の左端の輪郭（78 の x 0〜360）の射線で、参照モデルの一番上の面の距離と、その下の面の距離の段差。
参照モデル G:/research/model/wave_repair_zbrush2.obj を読み取りのみで開き、SHA-256 を照合し、整列 B（align_B_upright.json）で
主役波の断面の座標へ移した一時キャッシュ（Git 対象外の Unity/Build/Polish/sample04/map/_objcache_s4/）を作る。測り終えたら同じ実行の中で消し、
消したファイルの SHA-256 を s4_objcache_log.json に記録する。確かめの図もキャッシュの中に置き、一緒に消す。
使い方：py -3.10 -B Tools/GWWaveGen/as04/s4_obj.py [--keep-views]（--keep-views は図を見るために消す前に止まらない。図はキャッシュと一緒に消える）
出力：Unity/Build/Polish/sample04/map/s4_obj_numbers.json（数だけ）
"""
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S  # noqa: E402
import s4_rays as RY  # noqa: E402

SRC = r"G:\research\model\wave_repair_zbrush2.obj"
SRC_SHA = "AB4124F9720D6E27D80E2AE063916292898C87606A64441043F6A64DE3D53D40"
ALIGN = S.REPO + "/Docs/Evidence/ArtFirst/26/reference/align_B_upright.json"
CACHE_DIR = S.OUT + "/_objcache_s4"
CACHE = CACHE_DIR + "/ref_tmp.npz"
LOG = S.OUT + "/s4_objcache_log.json"
OUTJ = S.OUT + "/s4_obj_numbers.json"


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def log_event(e):
    d = json.load(open(LOG, encoding="utf-8")) if os.path.exists(LOG) else {"source": os.path.basename(SRC), "source_sha256": SRC_SHA, "events": []}
    d["events"].append(e)
    S.jdump(LOG, d)


def make_cache():
    t0 = time.time()
    raw = open(SRC, "rb").read()
    h = hashlib.sha256(raw).hexdigest().upper()
    if h != SRC_SHA:
        raise SystemExit("参照モデルの SHA-256 が違うので使わない: " + h)
    lines = raw.split(b"\n")
    del raw
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
    del lines
    Q = np.array(quads, np.int64).reshape(-1, 4)
    Tt = np.array(tris, np.int64).reshape(-1, 3)
    F = np.vstack([Tt, Q[:, [0, 1, 2]], Q[:, [0, 2, 3]]]).astype(np.int32)
    M4 = np.array(json.load(open(ALIGN, encoding="utf-8"))["obj_to_unity_4x4"])
    Vu = (np.c_[V, np.ones(len(V))] @ M4.T)[:, :3]
    os.makedirs(CACHE_DIR, exist_ok=True)
    np.savez(CACHE, Vu=Vu.astype(np.float32), F=F)
    log_event({"event": "cache_created", "file": os.path.relpath(CACHE, S.REPO).replace("\\", "/"), "sha256": S.sha(CACHE),
               "bytes": os.path.getsize(CACHE), "utc": now(), "seconds": round(time.time() - t0, 1), "source_sha256_checked": h,
               "n_v": int(len(V)), "n_f_tri": int(len(F)), "align": os.path.relpath(ALIGN, S.REPO).replace("\\", "/"), "align_sha256": S.sha(ALIGN),
               "frame": "Unity ワールド（整列 B）。測りでは kh_common.sec（a = T, y, c = E）へ移す", "tool": "Tools/GWWaveGen/as04/s4_obj.py"})
    return Vu, F


def delete_cache():
    if os.path.isdir(CACHE_DIR):
        for nm in sorted(os.listdir(CACHE_DIR)):
            fp = os.path.join(CACHE_DIR, nm)
            if os.path.isfile(fp):
                s = S.sha(fp)
                os.remove(fp)
                log_event({"event": "cache_deleted", "file": os.path.relpath(fp, S.REPO).replace("\\", "/"), "sha256": s, "utc": now()})
        if not os.listdir(CACHE_DIR):
            os.rmdir(CACHE_DIR)
    d = json.load(open(LOG, encoding="utf-8"))
    d["cache_dir_exists_after_delete"] = os.path.isdir(CACHE_DIR)
    S.jdump(LOG, d)


def height_profile(c, y, a, cb):
    """c の帯ごとの最も高い点の高さと a。"""
    idx = np.digitize(c, cb)
    H = np.full(len(cb) - 1, np.nan); Aa = np.full(len(cb) - 1, np.nan)
    o = np.argsort(idx, kind="stable")
    ids, starts = np.unique(idx[o], return_index=True)
    ends = np.r_[starts[1:], len(o)]
    for k, s0, s1 in zip(ids, starts, ends):
        if 1 <= k < len(cb):
            sel = o[s0:s1]
            j = sel[np.argmax(y[sel])]
            H[k - 1] = y[j]; Aa[k - 1] = a[j]
    return H, Aa


def band_extent(cc, H, Href, fr=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)):
    out = {}
    for f in fr:
        ok = np.nonzero(H >= f * Href)[0]
        if len(ok):
            out["%.1f" % f] = {"c_min": S.rnd(cc[ok[0]]), "c_max": S.rnd(cc[ok[-1]]), "length_m": S.rnd(cc[ok[-1]] - cc[ok[0]]),
                               "length_over_H": S.rnd((cc[ok[-1]] - cc[ok[0]]) / Href)}
    return out


def main(keep_views=False):
    t0 = time.time()
    Vu, F = make_cache()
    try:
        res = measure(Vu.astype(np.float64), F, keep_views)
        S.jdump(OUTJ, res)
    finally:
        if not keep_views:
            delete_cache()
    print("done", round(time.time() - t0, 1))


def measure(Vu, F, keep_views):
    al = json.load(open(ALIGN, encoding="utf-8"))
    sea = float(al["model_sea_surface_world_y"]["median"])
    Vs = S.K.sec(Vu)
    a, y, c = Vs[:, 0], Vs[:, 1] - sea, Vs[:, 2]
    res = {"schema": "GreatWave.ArtSample04.study_obj_numbers/1", "date": time.strftime("%Y-%m-%d %H:%M"),
           "source": {"file": os.path.basename(SRC), "sha256": SRC_SHA, "align": "align_B_upright.json", "model_sea_y": S.rnd(sea)},
           "note_ja": "数だけ。参照モデルは他者の展示作品（Q19・Q20）で、参考にとどめ写し取らない。高さは整列 B の模型の海面（中央値）から。"}
    # ---------------------------------------------------------------- 1. 波峰線の向きの長さ
    cb = np.arange(-40.0, 30.01, 0.5)
    cc = 0.5 * (cb[1:] + cb[:-1])
    # 台の円盤を除くため、海面より 0.5 m 上の点だけ
    up = y > 0.5
    Hr, Ar = height_profile(c[up], y[up], a[up], cb)
    Href = float(np.nanmax(Hr))
    X0 = S.load_hero()
    SX = S.hero_sec(X0)
    cm = S.rows_c()
    Hh = SX[:, S.J_B:S.J_TIP, 1].max(1)
    res["crest_length"] = {
        "ref_H_m": S.rnd(Href), "hero_H_m": S.rnd(Hh.max()), "ref_c_at_max": S.rnd(cc[np.nanargmax(Hr)]), "hero_c_at_max": S.rnd(cm[np.argmax(Hh)]),
        "ref_band_extent": band_extent(cc, np.nan_to_num(Hr, nan=-1), Href),
        "hero_band_extent": band_extent(cm, Hh, float(Hh.max())),
        "ref_profile_c_H_a": [[S.rnd(x), S.rnd(h), S.rnd(aa)] for x, h, aa in zip(cc, Hr, Ar) if np.isfinite(h)],
        "note_ja": "c の帯ごとの最も高い点。参照モデルは両端が台の円盤で切られている（長さは下限）。主役波は行ごとの頂（列 18〜200 の最大）。"}
    # ---------------------------------------------------------------- 2. 原画視点の区域
    cam = S.CC.painting_cam()
    idb, zb = S.U.raster(cam, Vu[F], np.arange(1, len(F) + 1))
    hitm = idb > 0
    ys, xs = np.nonzero(hitm)
    d = cam.ray(xs.astype(float), ys.astype(float))
    dist = 1.0 / zb[ys, xs]                    # カメラの前の向きの深さ
    P = cam.pos + d * (dist / (d @ cam.f))[:, None]
    Q = S.K.sec(P)
    Aimg = np.full((1080, 1920), np.nan); Yimg = np.full((1080, 1920), np.nan); Cimg = np.full((1080, 1920), np.nan); Dimg = np.full((1080, 1920), np.nan)
    Aimg[ys, xs] = Q[:, 0]; Yimg[ys, xs] = Q[:, 1] - sea; Cimg[ys, xs] = Q[:, 2]; Dimg[ys, xs] = dist
    regs = S.regions_ref()
    res["painting_view_regions"] = {}

    def st(v):
        v = v[np.isfinite(v)]
        return None if not len(v) else {"p05": S.rnd(np.percentile(v, 5)), "p50": S.rnd(np.median(v)), "p95": S.rnd(np.percentile(v, 95))}
    TH = RY.TileHits(cam, Vu, F, tile=16)
    for k, poly in regs.items():
        pd = S.ref_to_disp(poly)
        m = np.zeros((1080, 1920), np.uint8)
        cv2.fillPoly(m, [np.round(pd).astype(np.int32)], 1)
        m = m.astype(bool)
        e = {"px": int(m.sum()), "px_hit": int((m & hitm).sum()), "a_m": st(Aimg[m]), "y_m": st(Yimg[m]), "y_over_H": st(Yimg[m] / Href),
             "c_m": st(Cimg[m]), "depth_m": st(Dimg[m])}
        # 層：多角形の中を 12 画素おきに射線を当て、交点の列（入る・出る）を数える
        yy, xx = np.nonzero(m & hitm)
        sel = (yy % 12 == 0) & (xx % 12 == 0)
        gaps, nl, thick1 = [], [], []
        for x_, y_ in zip(xx[sel], yy[sel]):
            h = RY.merge_layers(TH.hits(float(x_), float(y_)), tol=0.02)
            nl.append(len(h))
            if len(h) >= 3:
                thick1.append(h[1][0] - h[0][0]); gaps.append(h[2][0] - h[1][0])
            elif len(h) == 2:
                thick1.append(h[1][0] - h[0][0])
        nl = np.array(nl)
        e["rays"] = int(len(nl))
        e["rays_with_air_gap_share"] = S.rnd((nl >= 3).mean()) if len(nl) else None
        e["first_solid_thickness_along_ray_m"] = st(np.array(thick1))
        e["air_gap_to_next_surface_m"] = st(np.array(gaps))
        res["painting_view_regions"][k] = e
        print(k, e, flush=True)
    # ---------------------------------------------------------------- 4. ④ の列ごと
    s78 = S.outline_segments()["78"]
    col4 = []
    for xr in range(0, 481, 20):
        xd = S.ref_to_disp(np.array([xr, 0.0]))[0]
        xi = int(round(xd))
        colh = hitm[:, xi]
        k = np.nonzero(colh)[0]
        if not len(k):
            col4.append({"x_ref": xr, "top": None}); continue
        ytop = int(k[0])
        j = np.argmin(np.abs(s78[:, 0] - xr))
        e = {"x_ref": xr, "outline_y_ref": S.rnd(s78[j, 1], 1) if abs(s78[j, 0] - xr) < 3 else None,
             "ref_top_y_ref": S.rnd(S.disp_to_ref(np.array([xd, ytop]))[1], 1),
             "top_depth_m": S.rnd(Dimg[ytop + 1, xi]), "top_a_y_c": S.rnd([Aimg[ytop + 1, xi], Yimg[ytop + 1, xi], Cimg[ytop + 1, xi]])}
        # 一番上から下へ 400 原画画素の範囲で、深さが 2 m 以上手前へ跳ぶ所（前の層の始まり）
        dcol = Dimg[ytop + 1:min(1080, ytop + 1 + 170), xi]
        jump = np.nonzero(np.diff(dcol) < -2.0)[0]
        if len(jump):
            jj = int(jump[0])
            e["front_layer_starts_y_ref"] = S.rnd(S.disp_to_ref(np.array([xd, ytop + 1 + jj + 1]))[1], 1)
            e["front_layer_depth_m"] = S.rnd(dcol[jj + 1]); e["back_layer_depth_m"] = S.rnd(dcol[jj])
            e["front_layer_a_y_c"] = S.rnd([Aimg[ytop + 2 + jj, xi], Yimg[ytop + 2 + jj, xi], Cimg[ytop + 2 + jj, xi]])
        col4.append(e)
    res["region4_columns"] = col4
    # ---------------------------------------------------------------- 上から見た平面の前の縁（高さの帯ごとの最も前の a）
    plan = {}
    for f in (0.2, 0.35, 0.5):
        sel = (y > f * Href - 0.4) & (y < f * Href + 0.4)
        idx = np.digitize(c[sel], cb)
        amax = np.full(len(cc), np.nan)
        for kk in np.unique(idx):
            if 1 <= kk < len(cb):
                amax[kk - 1] = a[sel][idx == kk].max()
        plan["%.2f" % f] = [[S.rnd(x), S.rnd(v)] for x, v in zip(cc, amax) if np.isfinite(v)]
    res["plan_front_edge_a_by_c"] = plan
    if keep_views:
        vis = np.zeros((1080, 1920, 3), np.uint8)
        dn = np.nan_to_num((Dimg - 35) / 40.0, nan=1.0)
        vis[..., 0] = np.clip(255 * (1 - dn), 0, 255)
        vis[..., 1] = np.clip(255 * np.nan_to_num(Yimg / Href), 0, 255)
        vis[~hitm] = (230, 230, 230)
        for k, poly in regs.items():
            cv2.polylines(vis, [np.round(S.ref_to_disp(poly)).astype(np.int32)], True, (0, 0, 255), 2)
        cv2.imwrite(CACHE_DIR + "/tmp_paint_depth.png", vis)
    return res


def cmd_sections():
    """キャッシュがあるときだけ：c ごとの断面の数（頂の高さと a、高さの帯ごとの最も前の a、0.3 H の最も後ろの a）を s4_obj_numbers.json へ足す。
    主役波も同じ定義で並べる（主役波は列 18〜394 の折れ線の交点）。"""
    z = np.load(CACHE)
    Vu = z["Vu"].astype(np.float64)
    al = json.load(open(ALIGN, encoding="utf-8"))
    sea = float(al["model_sea_surface_world_y"]["median"])
    Q = S.K.sec(Vu)
    a, y, c = Q[:, 0], Q[:, 1] - sea, Q[:, 2]
    Hr = float(y.max())
    fr = (0.15, 0.25, 0.35, 0.45, 0.55, 0.7, 0.85)
    ref = []
    for c0 in np.arange(-16.0, 16.01, 1.0):
        s = (np.abs(c - c0) < 0.25) & (y > 0.3)
        if s.sum() < 50:
            continue
        j = np.argmax(y[s])
        e = {"c": float(c0), "top_over_H": S.rnd(y[s][j] / Hr), "a_top": S.rnd(a[s][j]), "front_a_by_height": {}}
        for f in fr:
            t = s & (np.abs(y - f * Hr) < 0.3)
            e["front_a_by_height"]["%.2f" % f] = S.rnd(a[t].max()) if t.sum() else None
        t = s & (np.abs(y - 0.3 * Hr) < 0.3)
        e["back_a_at_0.30"] = S.rnd(a[t].min()) if t.sum() else None
        ref.append(e)
    X0 = S.load_hero()
    SX = S.hero_sec(X0)
    cm = S.rows_c()
    Hh = float(SX[:, S.J_B:S.J_TIP, 1].max())
    hero = []
    for c0 in np.arange(-44.0, 15.01, 2.0):
        i = int(np.argmin(np.abs(cm - c0)))
        A = SX[i, :, 0]; Y = SX[i, :, 1]
        j = int(np.argmax(Y[S.J_B:S.J_TIP]) + S.J_B)
        e = {"c": S.rnd(cm[i]), "row": i, "top_over_H": S.rnd(Y[j] / Hh), "a_top": S.rnd(A[j]), "front_a_by_height": {}}
        for f in fr:
            yy = f * Hh
            k = np.nonzero(np.diff(np.sign(Y[S.J_B:S.J_E + 1] - yy)) != 0)[0] + S.J_B
            aa = [A[q] + (yy - Y[q]) / (Y[q + 1] - Y[q]) * (A[q + 1] - A[q]) for q in k if Y[q + 1] != Y[q]]
            e["front_a_by_height"]["%.2f" % f] = S.rnd(max(aa)) if aa else None
        hero.append(e)
    d = json.load(open(OUTJ, encoding="utf-8"))
    d["sections_by_c"] = {"ref_H_m": S.rnd(Hr), "hero_H_m": S.rnd(Hh), "ref": ref, "hero": hero,
                          "note_ja": "c ごとの断面（参照モデルは |c − c0| < 0.25 m の点、主役波はその c に最も近い行）。front_a_by_height は高さ f·H の帯で最も前（+a）の点の a。"
                                     "参照モデルの低い帯（0.15〜0.25 H）の前の値は、手前の小波の体を含む。"}
    S.jdump(OUTJ, d)
    print("sections added", len(ref), len(hero))


if __name__ == "__main__":
    if "delete" in sys.argv:
        delete_cache()
    elif "sections" in sys.argv:
        cmd_sections()
    else:
        main(keep_views="--keep-views" in sys.argv)
