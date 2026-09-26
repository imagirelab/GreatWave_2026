# -*- coding: utf-8 -*-
"""番号31「白の出現と縞の追従」：Unity の描画（ID の連続・静止画・動画・t*）と UV 空間の検査から、項目 102・135・176・177 を測り、
図・動画・metrics.json・run.json を Docs/Evidence/ArtFirst/31 へまとめる。

使い方（リポジトリの根で）:
    py -3.10 Tools/GWWaveGen/af31_evidence.py
入力（Git 対象外の Unity/Build/ArtFirst/31）:
    white/af31_twhite.json・af31_uvcheck.json・af31_texel_cache.npz（af31_white.py）
    ids/af31_{painting,seat_form}_{shown,final,uv}_tSS.SS.png（AF31WhiteFormation.Render。主役波だけ、線なし、線形の RT、MSAA なし）
        shown＝表示している色区の ID（白の時間場を入れた後）、final＝終態の色区の ID、uv＝焼き込みの UV3 のテクセル番号
    stills/・arrival/・video/・af31_render_report.json・af31_tstar_remeasure.json（af31_tstar_eval.py）
    Unity/Build/ArtFirst/30/af30_tstar_remeasure.json（番号30 の t* の再測定、読むだけ）
    Tools/PaintingTruth/colour/colour_polylines.json・colour_truth.json（番号28 の第A部の真値、読むだけ）
測り方：
    ・102：UV（テクセル）空間で白くなったテクセルの割合（30 Hz）と世界の面積、ID の連続で『表示が白 かつ 終態が白でない』画素の数。
    ・135：t* の原画視点で 134 の白い帯（上側の端 → 船側の端、弧の割合 s）に入るテクセルを取り、時刻ごとの白くなった割合と s の平均、
           s の区間ごとの白の到着時刻。終点は t* の 133・134 の境界（番号28修正01 と同じ評価）。
    ・176：175 の 198 の色区（白の中の淡い水色・藍中・藍濃）を t* の原画視点で UV の連結成分へ対応させ、ID の連続で各色区の画素の
           表示が白になった数（一時的な白の塗りつぶし）と、見えている画素の数を数える。
    ・177：藍中の帯 25 本（番号28 の第A部）を同じ方法で UV の連結成分へ対応させ、同じテクセルの世界の高さ（30 Hz、keypose）と
           原画視点の画面上の位置を追う。終点は t* の 77・118 の境界。
"""
import datetime
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(REPO, "Tools", "PaintingTruth"))
sys.path.insert(0, HERE)
import truthlib as T  # noqa: E402
import af31_white as AW  # noqa: E402

B31 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "31")
B30 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "30")
EV = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "31")
COL = os.path.join(REPO, "Tools", "PaintingTruth", "colour")
FFMPEG = r"G:\ffmpeg-2024-12-19-git-494c961379-full_build\bin\ffmpeg.exe"
S = AW.S
W_, H_ = 1920, 1080
CLS_JA = {0: "白", 1: "淡い水色", 2: "藍中", 3: "藍濃"}
CLS_KEY = {"white": 0, "mizuiro": 1, "ai_mid": 2, "ai_dark": 3}


def sha(p):
    return AW.sha256_file(p)


def rel(p):
    return os.path.relpath(p, REPO).replace("\\", "/")


# ---------------------------------------------------------------- 画像の読み取り
def read_ids(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    if im is None:
        raise SystemExit("読めません: " + path)
    b, g, r = im[..., 0].astype(np.int32), im[..., 1].astype(np.int32), im[..., 2].astype(np.int32)
    out = np.full(im.shape[:2], -1, np.int8)
    out[(r == 255) & (g == 0) & (b == 0)] = 0
    out[(r == 0) & (g == 255) & (b == 0)] = 1
    out[(r == 0) & (g == 0) & (b == 255)] = 2
    out[(r == 255) & (g == 255) & (b == 0)] = 3
    other = (out < 0) & ~((r == 255) & (g == 255) & (b == 255))
    return out, int(other.sum())


def read_uv(path):
    im = cv2.imread(path, cv2.IMREAD_COLOR)
    b, g, r = im[..., 0].astype(np.int32), im[..., 1].astype(np.int32), im[..., 2].astype(np.int32)
    U = r * 16 + (g >> 4)
    V = (g & 15) * 256 + b
    return U, V


def id_path(view, kind, t):
    return os.path.join(B31, "ids", "af31_%s_%s_t%05.2f.png" % (view, kind, t))


# ---------------------------------------------------------------- 真値の色区（表示 px の多角形）
def region_mask(reg, shape=(H_, W_), erode=1):
    m = np.zeros(shape, np.uint8)
    sh = 4
    outer = [np.round(np.asarray(r["points_display"]) * (1 << sh)).astype(np.int32) for r in reg["rings"] if not r["hole"]]
    holes = [np.round(np.asarray(r["points_display"]) * (1 << sh)).astype(np.int32) for r in reg["rings"] if r["hole"]]
    for p in outer:
        cv2.fillPoly(m, [p], 1, lineType=cv2.LINE_8, shift=sh)
    for p in holes:
        cv2.fillPoly(m, [p], 0, lineType=cv2.LINE_8, shift=sh)
    if erode > 0 and m.sum() > 30:
        e = cv2.erode(m, np.ones((2 * erode + 1, 2 * erode + 1), np.uint8))
        if e.sum() > 0:
            m = e
    return m.astype(bool)


def uv_components(cls):
    """終態の色区ごとの UV の連結成分（8 近傍）。戻り値：成分番号の地図（0 は白、白以外は 1 から通し番号）、成分ごとの色区。"""
    comp = np.zeros((S, S), np.int32)
    comp_cls = [0]
    off = 0
    for k in (1, 2, 3):
        n, lab = cv2.connectedComponents((cls == k).astype(np.uint8), connectivity=8, ltype=cv2.CV_32S)
        m = lab > 0
        comp[m] = lab[m] + off
        comp_cls += [k] * (n - 1)
        off += n - 1
    return comp, np.asarray(comp_cls, np.int8)


def map_regions(reg_ids, polys, shown_t, U_t, V_t, comp, comp_cls):
    """t* の原画視点の画素 → UV の連結成分。色区ごとに、真値の多角形（1 px 縮めた）の中で表示の色区が同じ画素のテクセルを集め、
    そのテクセルの 10% 以上が入る成分を、その色区の成分とする。"""
    out = {}
    for rid in reg_ids:
        reg = polys[rid]
        k = CLS_KEY[reg["class"]]
        m = region_mask(reg) & (shown_t == k)
        n = int(m.sum())
        rec = {"id": rid, "class": reg["class"], "area_display_px2": reg["area_display_px2"], "centroid_display": reg["centroid_display"], "tstar_px": n, "comps": [], "texels": None}
        if n > 0:
            u, v = U_t[m], V_t[m]
            cc = comp[v, u]
            cc = cc[(cc > 0) & (comp_cls[np.maximum(cc, 0)] == k)]
            if len(cc):
                ids, cnt = np.unique(cc, return_counts=True)
                keep = ids[cnt >= max(1, 0.1 * len(cc))]
                rec["comps"] = [int(x) for x in keep]
                uv = np.unique(np.stack([v, u], 1), axis=0)
                rec["texels"] = uv
        out[rid] = rec
    return out


# ---------------------------------------------------------------- 本体
def main():
    t_start = time.time()
    P = T.load_json(os.path.join(HERE, "af31_white.json"))
    P["_path"] = os.path.join(HERE, "af31_white.json")
    wmeta = T.load_json(os.path.join(B31, "white", "af31_twhite.json"))
    uvc = T.load_json(os.path.join(B31, "white", "af31_uvcheck.json"))
    rr = T.load_json(os.path.join(B31, "af31_render_report.json"))
    br = T.load_json(os.path.join(B31, "af31_build_report.json"))
    tsr = T.load_json(os.path.join(B31, "af31_tstar_remeasure.json"))
    tsr30p = os.path.join(B30, "af30_tstar_remeasure.json")
    tsr30 = T.load_json(tsr30p) if os.path.exists(tsr30p) else None
    cache = np.load(os.path.join(B31, "white", "af31_texel_cache.npz"))
    Tt = cache["Tt"]
    Rt = cache["Rt"]
    cls, _ = AW.load_classes(P)
    uW, vW = AW.load_warp(P)
    colf, rowf = AW.texel_grid(uW, vW)
    pre = int(wmeta["pre_white_index"])
    t_end = float(wmeta["t_end_s"])
    t_star = float(wmeta["t_star_s"])
    ts_id = [round(float(x), 2) for x in rr["idTimes"]]
    views = ["painting", "seat_form"]
    polys = {r["id"]: r for r in T.load_json(os.path.join(COL, "colour_polylines.json"))["regions"]}
    truth = T.load_json(os.path.join(COL, "colour_truth.json"))
    reg175 = truth["white"]["regions_175"]["regions"]
    bands = [b["region"] for b in truth["stripes"]["ai_mid_bands"]]
    log = []

    def say(s):
        print(s)
        log.append(s)

    # ---- UV の連結成分と、t* の原画視点での対応
    comp, comp_cls = uv_components(cls)
    shown_t, oth = read_ids(id_path("painting", "shown", t_star))
    U_t, V_t = read_uv(id_path("painting", "uv", t_star))
    reg_map = map_regions(reg175, polys, shown_t, U_t, V_t, comp, comp_cls)
    band_map = map_regions(bands, polys, shown_t, U_t, V_t, comp, comp_cls)
    ncomp = len(comp_cls)
    reg_list = [r for r in reg175 if reg_map[r]["comps"]]
    band_list = [b for b in bands if band_map[b]["comps"]]
    # 色区（または帯）× 成分の対応の行列（複数の色区が同じ UV の成分に当たることがあるので、成分ごとに数えてから色区へ足す）
    from collections import Counter
    use_r = Counter(c for r in reg_list for c in reg_map[r]["comps"])
    use_b = Counter(c for b in band_list for c in band_map[b]["comps"])
    lut_b = np.full(ncomp, -1, np.int32)
    for i, bid in enumerate(band_list):
        for c in band_map[bid]["comps"]:
            lut_b[c] = i
    shared = sorted(set(use_r) & set(use_b))
    shared_r = sorted(c for c, n in use_r.items() if n > 1)
    shared_b = sorted(c for c, n in use_b.items() if n > 1)
    say("色区の対応：175 の %d のうち UV の成分へ対応 %d（2 つ以上の色区が当たる成分 %d）、藍中の帯 %d のうち %d（帯どうしで共通 %d、175 と共通 %d）"
        % (len(reg175), len(reg_list), len(shared_r), len(bands), len(band_list), len(shared_b), len(shared)))

    def by_region(counts_per_comp, rlist, rmap):
        return np.asarray([sum(int(counts_per_comp[c]) for c in rmap[r]["comps"]) for r in rlist], np.int64)

    # 色区ごとの、白が最初に接する時刻（成分の周り 3 テクセルの終態の白の T の最小）
    t_reach = {}
    # 成分の外接箱を一度に求める
    idx = np.nonzero(comp > 0)
    cc_all = comp[idx]
    order = np.argsort(cc_all, kind="stable")
    cc_sorted = cc_all[order]
    vy = idx[0][order]
    ux = idx[1][order]
    starts = np.searchsorted(cc_sorted, np.arange(len(comp_cls) + 1))

    def comp_pixels(c):
        a, b = starts[c], starts[c + 1]
        return vy[a:b], ux[a:b]
    Wm = cls == 0
    for rid in reg_list:
        vs, us = [], []
        for c in reg_map[rid]["comps"]:
            v_, u_ = comp_pixels(c)
            vs.append(v_)
            us.append(u_)
        v_ = np.concatenate(vs)
        u_ = np.concatenate(us)
        y0, y1 = max(v_.min() - 4, 0), min(v_.max() + 5, S)
        x0, x1 = max(u_.min() - 4, 0), min(u_.max() + 5, S)
        m = np.zeros((y1 - y0, x1 - x0), np.uint8)
        m[v_ - y0, u_ - x0] = 1
        ring = cv2.dilate(m, np.ones((7, 7), np.uint8)).astype(bool) & ~m.astype(bool) & Wm[y0:y1, x0:x1]
        t_reach[rid] = float(Tt[y0:y1, x0:x1][ring].min()) if ring.any() else None
        reg_map[rid]["uv_texels"] = int(len(v_))

    # ---- ID の連続（原画視点・座席）
    per = {v: [] for v in views}
    reg_vis = {v: np.zeros((len(ts_id), len(reg_list)), np.int32) for v in views}
    reg_own = {v: np.zeros((len(ts_id), len(reg_list)), np.int32) for v in views}
    reg_white = {v: np.zeros((len(ts_id), len(reg_list)), np.int32) for v in views}
    band_px = np.zeros((len(ts_id), len(band_list)), np.int32)
    band_own = np.zeros((len(ts_id), len(band_list)), np.int32)
    band_cx = np.full((len(ts_id), len(band_list)), np.nan)
    band_cy = np.full((len(ts_id), len(band_list)), np.nan)
    for i, t in enumerate(ts_id):
        for v in views:
            sh, o1 = read_ids(id_path(v, "shown", t))
            fi, o2 = read_ids(id_path(v, "final", t))
            U, V = read_uv(id_path(v, "uv", t))
            wave = fi >= 0
            vio = (sh == 0) & (fi != 0) & wave
            other = wave & (sh != fi) & ~((fi == 0) & (sh == pre))
            # 予測（UV のテクセルの中心の色区と T から）
            fu = cls[V, U]
            pred = np.where((fu == 0) & (Tt[V, U] > t) & (t < t_end), pre, fu)
            agree = float(((pred == sh) & wave).sum() / max(wave.sum(), 1))
            agree_final = float(((fu == fi) & wave).sum() / max(wave.sum(), 1))
            cid = comp[V, U]
            # 色区の画素：UV の成分がその色区のもので、同じ時刻の終態の ID もその色区の色（テクセルの中心の色区と、フィルターした距離の
            # argmax が境界の 1 画素で食い違う所を除く）
            ccls = np.asarray(comp_cls)[np.maximum(cid, 0)]
            member = wave & (cid > 0) & (fi == ccls)
            cm = cid[member]
            reg_vis[v][i] = by_region(np.bincount(cm, minlength=ncomp), reg_list, reg_map)
            reg_own[v][i] = by_region(np.bincount(cid[member & (sh == ccls)], minlength=ncomp), reg_list, reg_map)
            reg_white[v][i] = by_region(np.bincount(cid[member & (sh == 0)], minlength=ncomp), reg_list, reg_map)
            if v == "painting":
                bi = np.where(member, lut_b[np.maximum(cid, 0)], -1)
                bs = bi >= 0
                if bs.any():
                    band_px[i] = np.bincount(bi[bs], minlength=len(band_list))
                    band_own[i] = np.bincount(bi[bs & (sh == 2)], minlength=len(band_list))
                    yy, xx = np.nonzero(bs)
                    bb = bi[bs]
                    sx = np.bincount(bb, weights=xx, minlength=len(band_list))
                    sy = np.bincount(bb, weights=yy, minlength=len(band_list))
                    nz = band_px[i] > 0
                    band_cx[i, nz] = sx[nz] / band_px[i][nz]
                    band_cy[i, nz] = sy[nz] / band_px[i][nz]
            per[v].append({"t": t, "wave_px": int(wave.sum()), "white_shown_px": int(((sh == 0) & wave).sum()), "white_final_px": int(((fi == 0) & wave).sum()),
                           "pre_white_px": int(((fi == 0) & (sh == pre) & wave).sum()),
                           "white_on_nonwhite_px": int(vio.sum()), "other_mismatch_px": int(other.sum()), "non_id_px": o1 + o2,
                           "uv_prediction_agreement": round(agree, 5), "uv_final_agreement": round(agree_final, 5)})
    say("ID の連続：%d 時刻 × %d 視点" % (len(ts_id), len(views)))

    # ---- 102
    vio_total = {v: int(sum(p["white_on_nonwhite_px"] for p in per[v])) for v in views}
    oth_total = {v: int(sum(p["other_mismatch_px"] for p in per[v])) for v in views}
    first_px = {}
    for v in views:
        f = [p["t"] for p in per[v] if p["white_shown_px"] > 0]
        first_px[v] = f[0] if f else None
    frac = np.asarray(uvc["white_fraction"])
    hz = float(uvc["hz"])
    ts30 = np.arange(len(frac)) / hz
    area = np.asarray(uvc["white_area_world_m2"])
    area_f = np.asarray(uvc["final_white_area_world_m2"])
    area_rel_step = float(np.max(np.abs(np.diff(area))) / max(area_f[int(t_star * hz)], 1e-9))
    early = Rt[Wm & (Tt <= 3.0)]
    item102 = {
        "white_first_uv_s": uvc["t_first_white_s"], "white_complete_uv_s": uvc["t_all_white_s"], "rise_start_s": P["timeline"]["t_start_s"],
        "uv_fraction_before_start": uvc["white_fraction_before_start"], "uv_fraction_step_max_per_frame_30hz": uvc["white_fraction_step_max"],
        "uv_fraction_step_limit": uvc["white_fraction_step_limit"], "uv_fraction_monotone": uvc["white_fraction_monotone"],
        "uv_fraction_at_t_star": uvc["white_fraction_at_t_star"], "world_area_step_max_over_final": round(area_rel_step, 5),
        "nonwhite_texels_shown_white_uv": uvc["nonwhite_texels_shown_white"],
        "white_on_nonwhite_px_painting": vio_total["painting"], "white_on_nonwhite_px_seat": vio_total["seat_form"],
        "first_white_frame_s_painting": first_px["painting"], "first_white_frame_s_seat": first_px["seat_form"],
        "white_by_3s_rho_range": [float(early.min()), float(early.max())] if early.size else None,
        "white_by_3s_texels": int(early.size),
        "id_frames": len(ts_id),
    }
    pass102 = (uvc["white_fraction_before_start"] == 0 and uvc["white_fraction_step_max"] <= uvc["white_fraction_step_limit"] and uvc["white_fraction_monotone"]
               and uvc["nonwhite_texels_shown_white"] == 0 and vio_total["painting"] == 0 and vio_total["seat_form"] == 0 and abs(uvc["white_fraction_at_t_star"] - 1.0) < 1e-12)
    say("102：最初の白 %.3f s、1 フレームの増分の最大 %.4f、表示が白で終態が白でない画素 原画 %d・座席 %d → %s" % (uvc["t_first_white_s"], uvc["white_fraction_step_max"], vio_total["painting"], vio_total["seat_form"], pass102))

    # ---- 135：134 の白い帯（UV に固定した t* の帯のテクセル）
    band = truth["white"]["band_134"]
    prof = band["profile"]
    nsmp = len(prof)
    sidx = np.full((H_, W_), -1, np.int32)
    for j, pr_ in enumerate(prof):
        p = np.asarray(pr_["p"])
        n = np.asarray(pr_["n"])
        q = p + n * float(pr_["width"])
        cv2.line(sidx, tuple(np.round(p).astype(int)), tuple(np.round(q).astype(int)), int(j), 3)
    bm = (sidx >= 0) & (shown_t == 0)
    bu, bv = U_t[bm], V_t[bm]
    bs = sidx[bm] / max(nsmp - 1, 1)
    bT = Tt[bv, bu].astype(np.float64)
    ok = cls[bv, bu] == 0
    bu, bv, bs, bT = bu[ok], bv[ok], bs[ok], bT[ok]
    ts_b = ts30
    bfrac = np.array([(bT <= t).mean() for t in ts_b])
    bmean = np.array([bs[bT <= t].mean() if (bT <= t).any() else np.nan for t in ts_b])
    nb = 10
    bins = np.minimum((bs * nb).astype(int), nb - 1)
    bin_first = [float(bT[bins == k].min()) for k in range(nb)]
    bin_med = [float(np.median(bT[bins == k])) for k in range(nb)]
    bin_last = [float(bT[bins == k].max()) for k in range(nb)]

    def spearman(a, b):
        ra = np.argsort(np.argsort(a))
        rb = np.argsort(np.argsort(b))
        return float(np.corrcoef(ra, rb)[0, 1])
    sp = spearman(np.arange(nb), np.asarray(bin_med))
    q05 = np.quantile(bT, 0.05)
    q95 = np.quantile(bT, 0.95)
    s_first5 = float(bs[bT <= q05].mean())
    s_last5 = float(bs[bT >= q95].mean())
    bmean_valid = bmean[~np.isnan(bmean)]
    bmean_drop = float(np.max(np.maximum(0, -np.diff(bmean_valid)))) if len(bmean_valid) > 1 else 0.0
    b133 = next(x for x in tsr["boundaries_vs_28r01"] if x["item"] == "133")
    b134 = next(x for x in tsr["boundaries_vs_28r01"] if x["item"] == "134")
    b79 = next(x for x in tsr["boundaries_vs_28r01"] if x["item"] == "79")
    bstep = float(np.max(np.diff(bfrac)))
    item135 = {"band_texels": int(len(bT)), "band_samples": nsmp, "bins": nb, "bin_first_s": [round(x, 3) for x in bin_first], "bin_median_s": [round(x, 3) for x in bin_med],
               "bin_last_s": [round(x, 3) for x in bin_last], "spearman_bin_vs_median_arrival": round(sp, 4),
               "s_of_first_5pct": round(s_first5, 3), "s_of_last_5pct": round(s_last5, 3),
               "band_white_fraction_step_max_30hz": round(bstep, 5), "band_white_mean_s_max_drop": round(bmean_drop, 4),
               "band_complete_s": float(bT.max()),
               "end_133_max_px": b133["af31_max_px"], "end_134_max_px": b134["af31_max_px"], "end_79_max_px": b79["af31_max_px"],
               "end_verdicts": {"133": b133["af31_verdict"], "134": b134["af31_verdict"], "79": b79["af31_verdict"]}}
    pass135 = (sp >= 0.9 and s_first5 < 1 / 3 and s_last5 > 2 / 3 and bstep <= 0.02 and bT.max() < t_star
               and max(b133["af31_max_px"], b134["af31_max_px"]) <= 4.0)
    say("135：Spearman %.3f、最初の 5%% の s %.2f、最後の 5%% の s %.2f、帯の 1 フレームの増分 %.4f、終点 133 %.2f・134 %.2f px → %s" % (sp, s_first5, s_last5, bstep, b133["af31_max_px"], b134["af31_max_px"], pass135))

    # ---- 176
    ti = np.asarray(ts_id)
    reg_rows = []
    fill_events = {v: 0 for v in views}
    fill_px = {v: 0 for v in views}
    for j, rid in enumerate(reg_list):
        row = {"id": rid, "class": reg_map[rid]["class"], "area_display_px2": reg_map[rid]["area_display_px2"], "tstar_px": reg_map[rid]["tstar_px"],
               "uv_components": len(reg_map[rid]["comps"]), "uv_texels": reg_map[rid].get("uv_texels"), "t_white_reach_s": t_reach[rid]}
        for v in views:
            wv = reg_white[v][:, j]
            fill_events[v] += int((wv > 0).sum())
            fill_px[v] += int(wv.sum())
            tr = t_reach[rid] if t_reach[rid] is not None else float(wmeta["t_start_s"])
            win = (ti >= tr) & (ti <= t_star)
            win2 = (ti >= float(wmeta["t_start_s"])) & (ti <= t_star)
            row[v] = {"white_px_total": int(wv.sum()), "frames_visible_after_reach": int((reg_own[v][win, j] > 0).sum()), "frames_after_reach": int(win.sum()),
                      "frames_visible_from_start": int((reg_own[v][win2, j] > 0).sum()), "frames_from_start": int(win2.sum()),
                      "own_px_at_tstar": int(reg_own[v][ts_id.index(t_star), j])}
        reg_rows.append(row)
    lost = [r for r in reg175 if not reg_map[r]["comps"]]
    vis_after = [r["painting"]["frames_visible_after_reach"] / max(r["painting"]["frames_after_reach"], 1) for r in reg_rows]
    vis_start = [r["painting"]["frames_visible_from_start"] / max(r["painting"]["frames_from_start"], 1) for r in reg_rows]
    all_after = sum(1 for x in vis_after if x >= 1.0)
    item176 = {"regions_175": len(reg175), "regions_mapped": len(reg_list), "regions_not_mapped_at_tstar": lost, "uv_components_shared_by_regions": len(shared_r),
               "regions_not_visible_every_frame_after_reach": [{"id": r["id"], "class": r["class"], "area_display_px2": r["area_display_px2"], "t_white_reach_s": r["t_white_reach_s"],
                                                               "frames_visible_after_reach": r["painting"]["frames_visible_after_reach"], "frames_after_reach": r["painting"]["frames_after_reach"],
                                                               "own_px_at_tstar": r["painting"]["own_px_at_tstar"]}
                                                              for r in reg_rows if r["painting"]["frames_visible_after_reach"] < r["painting"]["frames_after_reach"]],
               "transient_white_fill_events_painting": fill_events["painting"], "transient_white_fill_px_painting": fill_px["painting"],
               "transient_white_fill_events_seat": fill_events["seat_form"], "transient_white_fill_px_seat": fill_px["seat_form"],
               "regions_visible_every_frame_after_white_reach_painting": all_after,
               "visible_fraction_after_reach_painting_min": round(float(min(vis_after)), 3) if vis_after else None,
               "visible_fraction_after_reach_painting_median": round(float(np.median(vis_after)), 3) if vis_after else None,
               "visible_fraction_from_start_painting_median": round(float(np.median(vis_start)), 3) if vis_start else None,
               "regions_visible_at_tstar_painting": int(sum(1 for r in reg_rows if r["painting"]["own_px_at_tstar"] > 0)),
               "t_white_reach_s_min_median_max": [round(float(np.min([x for x in t_reach.values() if x is not None])), 3),
                                                  round(float(np.median([x for x in t_reach.values() if x is not None])), 3),
                                                  round(float(np.max([x for x in t_reach.values() if x is not None])), 3)]}
    pass176 = fill_events["painting"] == 0 and fill_events["seat_form"] == 0 and vio_total["painting"] == 0 and vio_total["seat_form"] == 0 and uvc["nonwhite_texels_shown_white"] == 0
    say("176：対応 %d/%d、一時的な白の塗りつぶし 原画 %d 件・座席 %d 件、白が接してから毎フレーム見える色区 %d/%d → %s" % (len(reg_list), len(reg175), fill_events["painting"], fill_events["seat_form"], all_after, len(reg_list), pass176))

    # ---- 177：藍中の帯の追従
    kp = AW.Keypose(P)
    band_tex = []
    for bid in band_list:
        tx = band_map[bid]["texels"]
        band_tex.append(tx)
    # テクセル → 格子の小数の位置
    allv = np.concatenate([tx[:, 0] for tx in band_tex])
    allu = np.concatenate([tx[:, 1] for tx in band_tex])
    seg = np.concatenate([np.full(len(tx), i) for i, tx in enumerate(band_tex)])
    cf = colf[allu]
    rf = rowf[allv]
    c0 = np.clip(np.floor(cf).astype(int), 0, 398)
    r0 = np.clip(np.floor(rf).astype(int), 0, 238)
    fx = cf - c0
    fy = rf - r0
    heights = np.zeros((len(ts30), len(band_list)))
    for f, t in enumerate(ts30):
        X = kp.X(t)
        Y = X[..., 1]
        lower = (fx + fy) <= 1
        a = Y[r0, c0] + fx * (Y[r0, c0 + 1] - Y[r0, c0]) + fy * (Y[r0 + 1, c0] - Y[r0, c0])
        b = Y[r0 + 1, c0 + 1] + (1 - fx) * (Y[r0 + 1, c0] - Y[r0 + 1, c0 + 1]) + (1 - fy) * (Y[r0, c0 + 1] - Y[r0 + 1, c0 + 1])
        y = np.where(lower, a, b)
        heights[f] = np.bincount(seg, weights=y, minlength=len(band_list)) / np.bincount(seg, minlength=len(band_list))
    i2, i12 = int(round(2.0 * hz)), int(round(t_star * hz))
    dh = np.diff(heights[i2:i12 + 1], axis=0)
    band_rows = []
    for j, bid in enumerate(band_list):
        vis = band_px[:, j] > 0
        band_rows.append({"id": bid, "tstar_px": band_map[bid]["tstar_px"], "uv_components": len(band_map[bid]["comps"]),
                          "height_m_t2": round(float(heights[i2, j]), 3), "height_m_tstar": round(float(heights[i12, j]), 3),
                          "height_max_drop_per_frame_m": round(float(max(0.0, -dh[:, j].min())), 4),
                          "height_total_drop_m": round(float(np.sum(np.maximum(0, -dh[:, j]))), 4),
                          "painting_frames_visible": int(vis.sum()), "painting_own_class_fraction": round(float(band_own[vis, j].sum() / max(band_px[vis, j].sum(), 1)), 5)})
    # 下側の帯の並び（原画視点の重心の x の順が t* と同じか）
    lower_ids = [b["region"] for b in truth["stripes"]["ai_mid_bands"] if b["lower_end_display"][1] > 690 and b["region"] in band_list]
    li = [band_list.index(b) for b in lower_ids]
    it = ts_id.index(t_star)
    ref_order = np.argsort(band_cx[it, li])
    inversions = []
    for i in range(len(ts_id)):
        xs = band_cx[i, li]
        okk = ~np.isnan(xs) & ~np.isnan(band_cx[it, li])
        if okk.sum() < 2:
            inversions.append(None)
            continue
        a = band_cx[it, li][okk]
        b = xs[okk]
        inv = 0
        for p in range(len(a)):
            for q in range(p + 1, len(a)):
                if (a[p] - a[q]) * (b[p] - b[q]) < 0:
                    inv += 1
        inversions.append(inv)
    own_frac_min = float(min(r["painting_own_class_fraction"] for r in band_rows if r["painting_frames_visible"] > 0))
    rise_all = all(r["height_m_tstar"] > r["height_m_t2"] for r in band_rows)
    max_drop = float(max(r["height_max_drop_per_frame_m"] for r in band_rows))
    b77 = next(x for x in tsr["boundaries_vs_28r01"] if x["item"] == "77")
    b118 = next(x for x in tsr["boundaries_vs_28r01"] if x["item"] == "118")
    item177 = {"bands": len(bands), "bands_mapped": len(band_list), "bands_not_mapped": [b for b in bands if b not in band_list],
               "same_texels_by_construction": True, "components_shared_between_bands": shared_b, "painting_own_class_fraction_min": round(own_frac_min, 5),
               "rise_t2_to_tstar_all": rise_all, "height_max_drop_per_frame_m": round(max_drop, 4),
               "lower_side_bands": lower_ids, "lower_side_order_inversions_vs_tstar": inversions,
               "end_77_max_px": b77["af31_max_px"], "end_118_max_px": b118["af31_max_px"], "end_verdicts": {"77": b77["af31_verdict"], "118": b118["af31_verdict"]},
               "per_band": band_rows}
    pass177 = own_frac_min >= 0.999 and rise_all and max(b77["af31_max_px"], b118["af31_max_px"]) <= 4.0
    say("177：帯 %d/%d、表示が藍中の割合の最小 %.4f、t=2→t* で全部上がる %s、1 フレームの下がりの最大 %.4f m、終点 77 %.2f・118 %.2f px → %s"
        % (len(band_list), len(bands), own_frac_min, rise_all, max_drop, b77["af31_max_px"], b118["af31_max_px"], pass177))

    # ---- 図
    os.makedirs(EV, exist_ok=True)
    figs = make_figures(P, wmeta, uvc, per, ts_id, ts30, frac, area, area_f, bT, bs, ts_b, bfrac, bmean, bin_first, bin_med, bin_last,
                        reg_list, reg_map, reg_own, reg_white, t_reach, band_list, band_map, heights, band_cx, band_cy, band_px, lower_ids, Tt, cls, U_t, V_t, shown_t, comp, lut_b)
    vids = make_videos(rr)

    # ---- metrics.json
    t30 = None
    if tsr30:
        t30 = {x["item"] + ":" + x["measure"]: x["af30_max_px"] for x in tsr30["boundaries_vs_28r01"]}
    bd = []
    for x in tsr["boundaries_vs_28r01"]:
        k = x["item"] + ":" + x["measure"]
        bd.append({"item": x["item"], "measure": x["measure"], "af31_max_px": x["af31_max_px"], "af30_max_px": (t30 or {}).get(k), "r28r01_max_px": x["r28r01_max_px"],
                   "diff_vs_af30_px": None if not t30 or t30.get(k) is None else round(x["af31_max_px"] - t30[k], 4), "verdict": x["af31_verdict"]})
    tstar_same30 = all(b["diff_vs_af30_px"] == 0 for b in bd if b["diff_vs_af30_px"] is not None)
    metrics = {
        "schema": "GreatWave.AF31.metrics/1", "number": "31", "name_ja": "白の出現と縞の追従",
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "evidence_kind_ja": "numpy（UV 空間の検査）と Unity 6000.4.3f1 Editor の batchmode による PC のオフスクリーン描画（RTX 3080、Direct3D11）。HMD 実機の結果ではない。",
        "defaults_ja": [
            "白の前の色＝藍中（バックログの『水色』の既定の読み。既定値・利用者未回答。別案は淡い水色）",
            "白の出現の始まり＝形成の始まり 2.0 s（rig の t0。水面が上がり始める時刻）、全部そろう＝11.8 s（t* の 0.2 s 前）",
            "102 の『連続』＝30 Hz の 1 フレームで白くなる割合が終態の白の 2% 以下（番号31 で決めた）",
            "135 の『上側から船側へ』＝134 の白い帯（上側の端 → 船側の端）を 10 区間に分けた到着時刻の中央値の順位相関 ≥0.9、最初の 5% の白が上側の 1/3、最後の 5% が船側の 1/3（番号31 で決めた）",
            "176 の『一時的な白の塗りつぶし』＝ID の連続（原画視点・座席、47 時刻）で 175 の色区の画素が白で表示された件数。見えている時間は記録",
            "177 の『同じ縞が同じ水面とともに上がる』＝藍中の帯 25 本の t* のテクセルの世界の高さが t = 2 s から t* までに上がり、表示が藍中のまま（割合 ≥0.999）。1 フレームの下がりは記録"],
        "summary_verdicts": {"102": "pass" if pass102 else "fail", "135": "pass" if pass135 else "fail", "176": "pass" if pass176 else "fail", "177": "pass" if pass177 else "fail",
                             "tstar_same_as_30": "pass" if tstar_same30 else "record"},
        "items": {
            "102": {"ja": "水面が上がり始めると上側に白が現れ、0 から連続して、終態の白の内側にある", "value": item102, "verdict": "pass" if pass102 else "fail"},
            "135": {"ja": "上側に現れた白が船側へ曲がる水面に沿って広がり、終点の白の境界が ≤4 px", "value": item135, "verdict": "pass" if pass135 else "fail"},
            "176": {"ja": "白が広がる間も白の中の藍・水色が見え続け、一時的な白の塗りつぶし 0", "value": item176, "verdict": "pass" if pass176 else "fail"},
            "177": {"ja": "同じ縞が同じ水面とともに上がり、終点の色区の境界 ≤4 px", "value": item177, "verdict": "pass" if pass177 else "fail"},
            "tstar_remeasure": {"ja": "t* の色区の境界と輪郭（番号28修正01 の評価）。番号30 と同じ値か", "value": {"boundaries": bd, "silhouettes": tsr["silhouettes_vs_26r01_28r01"],
                                "verdicts_28r01_procedure": tsr["summary_verdicts_af31"], "worst_abs_diff_vs_28r01_px": tsr["worst_abs_diff_px"]},
                                "verdict": "pass" if tstar_same30 else "record"},
            "id_series": {"ja": "ID の連続（主役波だけ）の時刻ごとの数", "value": per, "verdict": "record"},
            "uv": {"ja": "UV 空間の白の割合（30 Hz）と世界の面積", "value": {"hz": hz, "white_fraction": [round(x, 6) for x in frac.tolist()], "white_area_world_m2": [round(x, 3) for x in area.tolist()],
                                                                    "final_white_area_world_m2_tstar": round(float(area_f[int(t_star * hz)]), 3), "by_segment": uvc["white_texels_by_segment"]}, "verdict": "record"},
            "regions_176": {"ja": "175 の色区ごとの表示（原画視点・座席）", "value": reg_rows, "verdict": "record"},
        },
        "open_ja": [
            "形成の途中の配色のうち、番号31 の範囲外のものは残る：唇が巻き切る前（9〜11.5 s）に唇の下面（t* で隠れ、焼き込みで藍濃）が原画視点で前を向いて暗い帯に見える（番号41）。座席から唇の奥の櫛の歯（28修正01 の限界、番号41）。",
            "0〜6 s の平らな海・低いうねりの上の縞：白の色区は白の前の色（藍中）になったが、淡い水色・藍中・藍濃の色区は K* の配色が押し縮められた縞のまま見える（原画視点の左下・座席の左下）。縞は同じ水面に貼り付いて動く（177）が、平らな海での見え方は番号41 と 260（接合をまたぐ縞）で扱う。",
            "白の前の色を藍中にしたので、白の中の藍中の色区（175 の 16 成分）は、白が周りに届くまでは白の前の色と同じ色で見分けられない（塗りつぶしではない）。淡い水色（166 成分）は常に見分けられる。",
            "白の波面は ρ の等値線（波峰線方向に揺らぎ）で、滑らかな線として動く。泡の形で咲くような出方（色区ごとの成長）は入れていない。",
            "座席 v1（唇の方位・仰角 30°）からは、白は 2〜4 s に頂に少し見え、5〜8 s は頂が向こうを向くので見えず、唇先・唇の下面・内壁の泡の白が 10.5〜11.7 s に現れる（形のため。表示の数は metrics の id_series）。",
            "175 の M171（唇先の淡い水色）は t* で描画に残らない（28修正01 と同じ）ので 176 の対応から外れる。M167・M178（17・11 表示 px²）は白が届いた後の一部の時刻で画素が 0（面の向きと大きさのため。白での表示は 0）。",
            "HMD 実機は未検証。立体視は SPI のキーワードでのコンパイルだけ。性能（81/112）は測っていない（頂点ごとの Load が 1 回、画素の分岐が数個増えた）。",
            "keypose の再生と白の時間場は AF31_White.unity だけ。体験の場面への統合は番号38・43。"],
        "log": log,
    }
    T.save_json(os.path.join(EV, "metrics.json"), metrics)

    # ---- run.json
    inputs = {rel(p): sha(p) for p in [P["_path"], os.path.join(HERE, "af31_white.py"), os.path.join(HERE, "af31_evidence.py"), os.path.join(HERE, "af31_tstar_eval.py"),
                                         os.path.join(HERE, "run_af31.ps1"), os.path.join(HERE, "run_af31_unity.ps1"),
                                         AW.rp(P["inputs"]["bake_sdf"]), AW.rp(P["inputs"]["bake_warp"]), os.path.join(AW.rp(P["inputs"]["kstar_dir"]), "kstar_a45.gwb"),
                                         os.path.join(AW.rp(P["inputs"]["keypose_dir"]), "af30_pos_rgba16.bin"), os.path.join(AW.rp(P["inputs"]["keypose_dir"]), "af30_keypose.json"),
                                         os.path.join(COL, "colour_polylines.json"), os.path.join(COL, "colour_truth.json")] if os.path.exists(p)}
    unity_files = ["Unity/Assets/GreatWave/ArtFirst/Shaders/AF31_NPR_White.shader", "Unity/Assets/GreatWave/ArtFirst/Scripts/AF31WhiteField.cs",
                   "Unity/Assets/GreatWave/ArtFirst/Editor/AF31WhiteFormation.cs", "Unity/Assets/GreatWave/ArtFirst/Materials/AF31_NPR_White.mat",
                   "Unity/Assets/GreatWave/ArtFirst/Materials/AF31_Outline_Keypose.mat", "Unity/Assets/GreatWave/Scenes/Tests/AF31_White.unity"]
    for f in unity_files:
        for g in (f, f + ".meta"):
            p = os.path.join(REPO, g)
            if os.path.exists(p):
                inputs[g] = sha(p)
    nc = {}
    for p in sorted(glob.glob(os.path.join(B31, "white", "*")) + glob.glob(os.path.join(B31, "video", "*.mp4")) + glob.glob(os.path.join(B31, "*.json"))):
        nc[rel(p)] = {"bytes": os.path.getsize(p), "sha256": sha(p)}
    ids_list = sorted(glob.glob(os.path.join(B31, "ids", "*.png")))
    h = hashlib.sha256()
    for p in ids_list:
        h.update(os.path.basename(p).encode())
        h.update(bytes.fromhex(sha(p)))
    ev_files = {rel(p): sha(p) for p in sorted(glob.glob(os.path.join(EV, "*"))) if os.path.basename(p) not in ("run.json",)}
    run = {
        "schema": "GreatWave.AF31.run/1", "number": "31", "generated_utc": metrics["generated_utc"],
        "commands": [
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af31.ps1",
            "py -3.10 Tools/GWWaveGen/af31_white.py --stage all",
            "powershell -NoProfile -ExecutionPolicy Bypass -File Tools/GWWaveGen/run_af31_unity.ps1 -Method GreatWave.ArtFirst.EditorTools.AF31WhiteFormation.BuildAndRender -Log build_render",
            "py -3.10 Tools/GWWaveGen/af31_tstar_eval.py",
            "py -3.10 Tools/GWWaveGen/af31_evidence.py"],
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "unity": rr.get("unity"), "device": rr.get("device"),
                     "graphics_api": rr.get("graphicsApi"), "color_space": rr.get("colorSpace"), "ffmpeg": os.path.basename(os.path.dirname(os.path.dirname(FFMPEG)))},
        "unity_render_seconds": rr.get("totalSeconds"), "unity_render_passed": rr.get("passed"), "protected_unchanged_build": br.get("protectedUnchanged"),
        "protected_unchanged_render": rr.get("protectedUnchanged"), "protected_files": rr.get("protectedFiles"),
        "spi": rr.get("spi"), "scene_sha256": rr.get("sceneSha256"), "white_field_sha256": wmeta["sha256"],
        "inputs_sha256": inputs, "not_committed_sha256": nc,
        "ids_png": {"count": len(ids_list), "combined_sha256_of_names_and_hashes": h.hexdigest()},
        "videos": vids, "figures": figs, "evidence_files_sha256": ev_files,
        "white_off_vs_af30_video": {k: {"af31_off_sha256": sha(os.path.join(B31, "video", a_)), "af30_sha256": sha(os.path.join(B30, "video", b_)) if os.path.exists(os.path.join(B30, "video", b_)) else None,
                                         "identical": os.path.exists(os.path.join(B30, "video", b_)) and sha(os.path.join(B31, "video", a_)) == sha(os.path.join(B30, "video", b_))}
                                    for k, a_, b_ in (("painting", "af31_formation_painting_off_60fps.mp4", "af30_formation_painting_60fps.mp4"),
                                                      ("seat_form_waveonly", "af31_formation_seat_form_waveonly_off_60fps.mp4", "af30_formation_seat_form_waveonly_60fps.mp4"))},
        "determinism_ja": "2026-09-26 に run_af31.ps1 を 4 回通した（ログは Unity/Build/ArtFirst/31/run_af31_log1〜4.txt）。1 回目と 2 回目は動画 7 本・T_white・ID の画像 282 枚の SHA-256 がすべて一致。2 回目と 3 回目の間で、白がそろった所の色を lerp でなく白そのものにする修正（番号30 の色と 1 ulp の差をなくす）を入れた。3 回目で、Unity が出す白の時間場ありの動画 4 本（原画視点・座席 v1 の場面全体・座席 v1 の主役波だけ・左の側面）と白の時間場を切った座席（主役波だけ）の動画 1 本は 1・2 回目と同じ SHA-256、白の時間場を切った原画視点の動画は 1・2 回目から変わって番号30 の動画と同じ SHA-256 になった（white_off_vs_af30_video）。これを使う 2×2 の比べる動画も変わった。3 回目と 4 回目の間は検査の数え方だけを変え（af31_white.py の白でないテクセルの確かめを全フレームにした。af31_evidence.py の 176 で、2 つの色区が同じ UV の成分に当たる所を成分ごとに数えてから色区へ足すようにし、白が届いてから毎時刻見える色区が 192/197 から 195/197 になった）、4 回目の動画 7 本・T_white・ID の画像 282 枚は 3 回目と同じ SHA-256。証拠は 4 回目の出力。",
        "seconds": round(time.time() - t_start, 1),
    }
    T.save_json(os.path.join(EV, "run.json"), run)
    print("AF31_EVIDENCE_DONE %.1f s" % (time.time() - t_start))


# ---------------------------------------------------------------- 図
_FONTS = {}


def put(img, txt, org, scale=0.8, col=(20, 20, 20)):
    """日本語の文字を描く（Pillow、游ゴシック）。文字の周りだけを切り出して描く。"""
    from PIL import Image, ImageDraw, ImageFont
    size = int(28 * scale)
    if size not in _FONTS:
        for fp in (r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"):
            if os.path.exists(fp):
                _FONTS[size] = ImageFont.truetype(fp, size)
                break
    f = _FONTS[size]
    x0, y0 = int(org[0]), int(org[1])
    bb = f.getbbox(txt)
    x1, y1 = min(img.shape[1], x0 + bb[2] + 4), min(img.shape[0], y0 + bb[3] + 6)
    x0c, y0c = max(0, x0), max(0, y0)
    if x1 <= x0c or y1 <= y0c:
        return
    sub = img[y0c:y1, x0c:x1]
    pil = Image.fromarray(cv2.cvtColor(sub, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(pil)
    d.text((x0 - x0c, y0 - y0c), txt, fill=(col[2], col[1], col[0]), font=f)
    img[y0c:y1, x0c:x1] = cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)


def grid(paths, labels, cols, cell=(640, 360), title=None):
    rows = (len(paths) + cols - 1) // cols
    top = 50 if title else 0
    out = np.full((rows * cell[1] + top, cols * cell[0], 3), 255, np.uint8)
    for i, (p, lab) in enumerate(zip(paths, labels)):
        im = cv2.imread(p)
        im = cv2.resize(im, cell, interpolation=cv2.INTER_AREA)
        put(im, lab, (8, 4), 0.85)
        r, c = divmod(i, cols)
        out[top + r * cell[1]:top + (r + 1) * cell[1], c * cell[0]:(c + 1) * cell[0]] = im
    if title:
        put(out, title, (10, 8), 0.95)
    return out


def fit1080(img):
    h, w = img.shape[:2]
    s = min(1920 / w, 1080 / h)
    im = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    out = np.full((1080, 1920, 3), 255, np.uint8)
    y0, x0 = (1080 - im.shape[0]) // 2, (1920 - im.shape[1]) // 2
    out[y0:y0 + im.shape[0], x0:x0 + im.shape[1]] = im
    return out


def make_figures(P, wmeta, uvc, per, ts_id, ts30, frac, area, area_f, bT, bs, ts_b, bfrac, bmean, bin_first, bin_med, bin_last,
                 reg_list, reg_map, reg_own, reg_white, t_reach, band_list, band_map, heights, band_cx, band_cy, band_px, lower_ids, Tt, cls, U_t, V_t, shown_t, comp, lut_b):
    figs = {}
    st = os.path.join(B31, "stills")
    times = [3, 5, 7, 8, 9, 10, 10.5, 11, 12]
    # 1) 原画視点
    im = grid([os.path.join(st, "af31_painting_t%05.2f.png" % t) for t in times], ["t = %.1f s" % t for t in times], 3,
              title="番号31 原画視点（Unity、場面全体）：白は上側から船側へ広がる。白の前は藍中、白の中の淡い水色・藍は終態の色のまま。t* = 12.0 s")
    p = os.path.join(EV, "af31_painting_white.png")
    cv2.imwrite(p, fit1080(im))
    figs["painting"] = rel(p)
    # 2) 座席
    im = grid([os.path.join(st, "af31_seat_form_waveonly_t%05.2f.png" % t) for t in times], ["t = %.1f s" % t for t in times], 3,
              title="番号31 座席 v1（唇の方位・仰角 30°、主役波・空・海だけ）")
    p = os.path.join(EV, "af31_seat_white_waveonly.png")
    cv2.imwrite(p, fit1080(im))
    figs["seat_waveonly"] = rel(p)
    im = grid([os.path.join(st, "af31_seat_form_t%05.2f.png" % t) for t in times], ["t = %.1f s" % t for t in times], 3,
              title="番号31 座席 v1（場面全体。下半分は番号39・40 までの仮置き）")
    p = os.path.join(EV, "af31_seat_white.png")
    cv2.imwrite(p, fit1080(im))
    figs["seat"] = rel(p)
    # 3) 番号30 との比べ（白の時間場なし＝番号30 と同じ色）
    ct = [5, 8, 9, 10, 11]
    paths, labs = [], []
    for t in ct:
        paths += [os.path.join(st, "af31_painting_off_t%05.2f.png" % t), os.path.join(st, "af31_painting_t%05.2f.png" % t),
                  os.path.join(st, "af31_seat_form_waveonly_off_t%05.2f.png" % t), os.path.join(st, "af31_seat_form_waveonly_t%05.2f.png" % t)]
        labs += ["%.1f s 白の時間場なし（番号30 の色）" % t, "%.1f s 番号31" % t, "%.1f s 座席 なし" % t, "%.1f s 座席 番号31" % t]
    im = grid(paths, labs, 4, cell=(480, 270), title="番号30（白は最初から終態）と番号31（白の時間場）の比べ。左 2 列 原画視点、右 2 列 座席（主役波だけ）")
    p = os.path.join(EV, "af31_compare_30.png")
    cv2.imwrite(p, fit1080(im))
    figs["compare_30"] = rel(p)
    # 4) 白の到着時刻
    ar = os.path.join(B31, "arrival")
    tiles = []
    for v, lab in (("painting", "原画視点"), ("seat_form", "座席 v1"), ("side_left", "左の側面"), ("back", "背面")):
        im = cv2.resize(cv2.imread(os.path.join(ar, "af31_arrival_%s.png" % v)), (800, 450), interpolation=cv2.INTER_AREA)
        put(im, lab + "（t* の形に白の到着時刻を色で描く）", (8, 4), 0.75)
        tiles.append(im)
    uvp = cv2.imread(os.path.join(B31, "white", "af31_uv_twhite.png"))
    uvp = cv2.resize(uvp, (450, 450), interpolation=cv2.INTER_AREA)
    bar = np.full((450, 320, 3), 255, np.uint8)
    for y in range(40, 400):
        x = (400 - y) / 360.0
        c = ramp_bgr(x)
        bar[y, 20:60] = c
    for tt in (2, 4, 6, 8, 10, 12):
        y = int(400 - (tt - 2) / 10 * 360)
        put(bar, "%d s" % tt, (68, y - 14), 0.7)
    put(bar, "白の到着時刻", (20, 5), 0.75)
    put(bar, "灰：白でない色区", (20, 410), 0.7)
    right = np.hstack([uvp, bar])
    put(right, "UV（上 = 波峰線の奥の行、左 = 背面）", (6, 420), 0.65)
    top = np.hstack([tiles[0], tiles[1]])
    mid = np.hstack([tiles[2], tiles[3]])
    fig = np.full((450 * 3 + 50, 1600, 3), 255, np.uint8)
    put(fig, "白の時間場 T_white：頂（上側）で 2 s に始まり、唇先（船側）に約 10.5 s、唇の下面・内壁の泡に 11.4〜11.7 s に届く（背面は頂から足へ）", (10, 8), 0.8)
    fig[50:500] = top
    fig[500:950] = mid
    fig[950:1400, :770] = right[:, :770]
    # 帯の到着
    plot = np.full((450, 830, 3), 255, np.uint8)
    draw_band_plot(plot, bin_first, bin_med, bin_last)
    fig[950:1400, 770:1600] = plot
    p = os.path.join(EV, "af31_arrival.png")
    cv2.imwrite(p, fit1080(fig))
    figs["arrival"] = rel(p)
    # 5) 数の図（matplotlib を使わず OpenCV で描く）
    p = os.path.join(EV, "af31_white_metrics.png")
    cv2.imwrite(p, metrics_plot(ts30, frac, area, area_f, per, ts_b, bfrac, bmean, reg_list, reg_own, reg_white, ts_id, t_reach))
    figs["metrics"] = rel(p)
    # 6) 縞の追従
    p = os.path.join(EV, "af31_stripes.png")
    cv2.imwrite(p, stripes_plot(ts_id, ts30, band_list, band_map, heights, band_cx, band_cy, band_px, lower_ids, comp, lut_b))
    figs["stripes"] = rel(p)
    return figs


def ramp_bgr(x):
    x = min(max(x, 0.0), 1.0)
    cs = [(0.19, 0.07, 0.55), (0.10, 0.55, 0.95), (0.20, 0.85, 0.35), (0.98, 0.80, 0.15), (0.85, 0.12, 0.08)]
    y = x * 4
    i = min(int(y), 3)
    f = y - i
    c = [cs[i][k] * (1 - f) + cs[i + 1][k] * f for k in range(3)]
    return (int(c[2] * 255), int(c[1] * 255), int(c[0] * 255))


def axes(img, x0, y0, w, h, xr, yr, xlabel, ylabel, xticks, yticks):
    cv2.rectangle(img, (x0, y0), (x0 + w, y0 + h), (60, 60, 60), 1)
    lo_x, hi_x = min(xr), max(xr)
    lo_y, hi_y = min(yr), max(yr)
    for xt in [v for v in xticks if lo_x - 1e-9 <= v <= hi_x + 1e-9]:
        x = int(x0 + (xt - xr[0]) / (xr[1] - xr[0]) * w)
        cv2.line(img, (x, y0 + h), (x, y0 + h + 5), (60, 60, 60), 1)
        cv2.line(img, (x, y0), (x, y0 + h), (225, 225, 225), 1)
        put(img, ("%g" % xt), (x - 10, y0 + h + 6), 0.55)
    for yt in [v for v in yticks if lo_y - 1e-9 <= v <= hi_y + 1e-9]:
        y = int(y0 + h - (yt - yr[0]) / (yr[1] - yr[0]) * h)
        cv2.line(img, (x0 - 5, y), (x0, y), (60, 60, 60), 1)
        cv2.line(img, (x0, y), (x0 + w, y), (225, 225, 225), 1)
        put(img, ("%g" % yt), (x0 - 48, y - 9), 0.55)
    put(img, xlabel, (x0 + w // 2 - 60, y0 + h + 26), 0.6)
    put(img, ylabel, (x0, y0 - 26), 0.6)

    def f(x, y):
        return (int(x0 + (x - xr[0]) / (xr[1] - xr[0]) * w), int(y0 + h - (y - yr[0]) / (yr[1] - yr[0]) * h))
    return f


def polyline(img, f, xs, ys, col, th=2):
    pts = [f(x, y) for x, y in zip(xs, ys) if not (np.isnan(x) or np.isnan(y))]
    if len(pts) > 1:
        cv2.polylines(img, [np.asarray(pts, np.int32).reshape(-1, 1, 2)], False, col, th, cv2.LINE_AA)


def draw_band_plot(img, first, med, last):
    f = axes(img, 90, 60, 700, 320, (0, 1), (2, 12), "134 の白い帯の位置 s（0 上側の端 → 1 船側の端）", "白の到着時刻（s）", [0, 0.2, 0.4, 0.6, 0.8, 1.0], [2, 4, 6, 8, 10, 12])
    xs = (np.arange(len(med)) + 0.5) / len(med)
    polyline(img, f, xs, first, (200, 120, 40))
    polyline(img, f, xs, med, (30, 30, 200), 3)
    polyline(img, f, xs, last, (40, 160, 40))
    put(img, "青：区間の最初の白　赤：中央値　緑：区間の最後の白", (90, 422), 0.6)


def metrics_plot(ts30, frac, area, area_f, per, ts_b, bfrac, bmean, reg_list, reg_own, reg_white, ts_id, t_reach):
    img = np.full((1080, 1920, 3), 255, np.uint8)
    put(img, "番号31 白の出現の数（UV 空間 30 Hz・世界の面積・ID の連続 47 時刻、主役波だけ）", (20, 10), 0.95)
    # (a) UV の割合・世界の面積
    f = axes(img, 90, 110, 800, 330, (0, 17), (0, 1.05), "時刻（s）", "終態の白に対する割合", [0, 2, 4, 6, 8, 10, 12, 14, 16], [0, 0.25, 0.5, 0.75, 1.0])
    polyline(img, f, ts30, frac, (30, 30, 200), 3)
    af = area / np.maximum(area_f, 1e-9)
    polyline(img, f, ts30, af, (200, 120, 40), 2)
    pw = [p["white_shown_px"] / max(per["painting"][-1]["white_final_px"], 1) for p in per["painting"]]
    ps = [p["white_shown_px"] / max(per["seat_form"][-1]["white_final_px"], 1) for p in per["seat_form"]]
    polyline(img, f, ts_id, pw, (40, 160, 40), 2)
    polyline(img, f, ts_id, ps, (150, 60, 150), 2)
    put(img, "赤：白くなったテクセル（UV）　青：世界の面積（その時刻の形）", (90, 492), 0.55)
    put(img, "緑：原画視点の白の画素　紫：座席の白の画素（主役波だけ。各 t* の値で割る）", (90, 516), 0.55)
    # (b) 違反
    f2 = axes(img, 1010, 110, 820, 330, (0, 17), (0, 1), "時刻（s）", "終態が白でない画素が白で表示された数（原画視点・座席）", [0, 2, 4, 6, 8, 10, 12, 14, 16], [0, 1])
    polyline(img, f2, ts_id, [p["white_on_nonwhite_px"] for p in per["painting"]], (40, 160, 40), 3)
    polyline(img, f2, ts_id, [p["white_on_nonwhite_px"] for p in per["seat_form"]], (150, 60, 150), 2)
    put(img, "全時刻で 0（緑 原画視点・紫 座席、各 47 時刻）", (1010, 492), 0.6)
    # (c) 134 の帯
    f3 = axes(img, 90, 600, 800, 360, (0, 17), (0, 1.05), "時刻（s）", "134 の白い帯", [0, 2, 4, 6, 8, 10, 12, 14, 16], [0, 0.25, 0.5, 0.75, 1.0])
    polyline(img, f3, ts_b, bfrac, (30, 30, 200), 3)
    polyline(img, f3, ts_b, bmean, (200, 120, 40), 2)
    put(img, "赤：帯の白くなった割合　青：白くなった所の帯の位置 s の平均（0 上側 → 1 船側）", (90, 1012), 0.55)
    # (d) 176 の色区：白が接してから見えている割合
    f4 = axes(img, 1010, 600, 820, 360, (0, 17), (0, len(reg_list) + 2), "時刻（s）", "175 の色区のうち（原画視点）", [0, 2, 4, 6, 8, 10, 12, 14, 16], [0, 50, 100, 150, 200])
    vis = (reg_own["painting"] > 0).sum(1)
    reached = np.array([sum(1 for r in reg_list if t_reach[r] is not None and t_reach[r] <= t) for t in ts_id])
    wh = (reg_white["painting"] > 0).sum(1)
    polyline(img, f4, ts_id, vis, (40, 160, 40), 3)
    polyline(img, f4, ts_id, reached, (200, 120, 40), 2)
    polyline(img, f4, ts_id, wh, (30, 30, 200), 2)
    put(img, "緑：自分の色で見えている色区　青：周りに白が届いた色区　赤：白で表示された色区（全時刻で 0）", (1010, 1012), 0.55)
    return img


def stripes_plot(ts_id, ts30, band_list, band_map, heights, band_cx, band_cy, band_px, lower_ids, comp, lut_b):
    img = np.full((1080, 1920, 3), 255, np.uint8)
    put(img, "番号31 縞の追従：藍中の帯（番号28 の第A部の 25 本）の同じテクセルを追う。色は帯ごと（原画視点、主役波だけの ID 描画）", (20, 10), 0.9)
    rng = np.random.RandomState(3)
    cols = [tuple(int(c) for c in rng.randint(40, 230, 3)) for _ in band_list]
    tt = [6.0, 8.0, 10.0, 12.0]
    for k, t in enumerate(tt):
        sh, _ = read_ids(id_path("painting", "shown", t))
        U, V = read_uv(id_path("painting", "uv", t))
        base = np.full((H_, W_, 3), 255, np.uint8)
        pal = np.array([[223, 243, 248], [203, 215, 198], [147, 105, 44], [97, 64, 35]], np.uint8)
        wv = sh >= 0
        base[wv] = (pal[sh[wv]] * 0.3 + 170).astype(np.uint8)
        cid = comp[V, U]
        bi = np.where(wv & (cid > 0), lut_b[np.maximum(cid, 0)], -1)
        for j in range(len(band_list)):
            base[bi == j] = cols[j]
        crop = base[60:1020, 0:1300]
        crop = cv2.resize(crop, (650, 480), interpolation=cv2.INTER_AREA)
        put(crop, "t = %.1f s" % t, (8, 4), 0.8)
        r, c = divmod(k, 2)
        img[60 + r * 490:60 + r * 490 + 480, 10 + c * 660:10 + c * 660 + 650] = crop
    f = axes(img, 1400, 110, 470, 400, (0, 17), (0, float(np.nanmax(heights)) * 1.1 + 0.5), "時刻（s）", "帯のテクセルの平均の高さ（m、keypose）", [0, 4, 8, 12, 16],
             [0, 5, 10, 15, 20])
    for j in range(len(band_list)):
        polyline(img, f, ts30, heights[:, j], cols[j], 2)
    f2 = axes(img, 1400, 620, 470, 380, (0, 1920), (1080, 0), "原画視点の画面 x（px）", "帯の重心の軌跡（ID の連続、t 6→12 s）", [0, 480, 960, 1440, 1920], [0, 270, 540, 810, 1080])
    for j in range(len(band_list)):
        m = [(x, y) for t, x, y in zip(ts_id, band_cx[:, j], band_cy[:, j]) if t >= 6 and t <= 12 and not np.isnan(x)]
        if len(m) > 1:
            polyline(img, f2, [a for a, b in m], [b for a, b in m], cols[j], 2)
            cv2.circle(img, f2(*m[-1]), 4, cols[j], -1)
    return img


def make_videos(rr):
    vd = os.path.join(B31, "video")
    out = {}
    for v in rr["videos"]:
        out[v["view"]] = {"path": rel(v["path"]), "sha256": v["sha256"], "frames": v["frames"], "fps": v["fps"], "bytes": os.path.getsize(v["path"])}
    # 比べる動画（2×2、1920×1080）：左 番号30 の色（白の時間場なし）、右 番号31。上 原画視点、下 座席（主役波だけ）
    cmp_ = os.path.join(vd, "af31_compare_30_60fps.mp4")
    a = os.path.join(vd, "af31_formation_painting_off_60fps.mp4")
    b = os.path.join(vd, "af31_formation_painting_60fps.mp4")
    c = os.path.join(vd, "af31_formation_seat_form_waveonly_off_60fps.mp4")
    d = os.path.join(vd, "af31_formation_seat_form_waveonly_60fps.mp4")
    font = "C\\:/Windows/Fonts/YuGothM.ttc"
    lab = ["白の時間場なし（番号30 の色）", "番号31（白の時間場）", "座席 なし", "座席 番号31"]
    fc = "".join("[%d:v]scale=960:540,drawtext=fontfile='%s':text='%s':x=12:y=10:fontsize=28:fontcolor=black:box=1:boxcolor=white@0.6[v%d];" % (i, font, lab[i], i) for i in range(4))
    fc += "[v0][v1]hstack[t];[v2][v3]hstack[b];[t][b]vstack[o]"
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", a, "-i", b, "-i", c, "-i", d, "-filter_complex", fc, "-map", "[o]", "-c:v", "libx264", "-preset", "medium", "-crf", "24",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", cmp_]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("比べる動画を作れません: " + r.stderr[-2000:])
    out["compare_30"] = {"path": rel(cmp_), "sha256": sha(cmp_), "bytes": os.path.getsize(cmp_), "ffmpeg_filter": fc}
    # 証拠へ写す（5 MB を超えるものは 720p の版を作る）
    for k in list(out.keys()):
        src = os.path.join(REPO, out[k]["path"])
        if k in ("painting_off", "seat_form_waveonly_off"):
            continue
        dst = os.path.join(EV, os.path.basename(src))
        if os.path.getsize(src) <= 5 * 1024 * 1024:
            shutil.copy2(src, dst)
            out[k]["evidence"] = rel(dst)
        else:
            dst = dst.replace("_60fps.mp4", "_60fps_720p.mp4")
            r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "medium", "-crf", "24", "-pix_fmt", "yuv420p",
                                "-movflags", "+faststart", dst], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if r.returncode != 0:
                raise SystemExit("720p の動画を作れません: " + r.stderr[-2000:])
            if os.path.getsize(dst) > 5 * 1024 * 1024:
                r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "medium", "-crf", "30", "-pix_fmt", "yuv420p",
                                    "-movflags", "+faststart", dst], capture_output=True, text=True, encoding="utf-8", errors="replace")
            out[k]["evidence"] = rel(dst)
            out[k]["evidence_note_ja"] = "元の 1920×1080 が 5 MB を超えるので 1280×720 に縮めた版"
        out[k]["evidence_sha256"] = sha(dst)
        out[k]["evidence_bytes"] = os.path.getsize(dst)
    return out


if __name__ == "__main__":
    main()
