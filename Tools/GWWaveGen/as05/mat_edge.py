# -*- coding: utf-8 -*-
"""美術の見本05 の材質 AS05（Q33）：「藍の面がそのまま縁の線まで来る」所の白の印 whiteSD を、面の上で書き換える道具（要求書 T6）。

どの形の主役波にも当てられる（形 A・B に作り直した後も同じ引数で回す）。入力は静止のメッシュ（書式 GreatWave.AS03.static_mesh/1）だけで、
読む属性は位置・whiteSD（uv5.z）・行（uv6.x）・列（uv6.y）。書き換えるのは主役波の頂点の whiteSD だけ（ほかのチャンネル・位置・三角形・wave4 は同じ）。

  py -3.10 -B Tools/GWWaveGen/as05/mat_edge.py --mesh <入力の静止のメッシュ .json> --out <出力 .json>
      [--hero-verts 314400] [--claws <爪の並び .json>] [--rules <規則の .json>] [--report <報告 .json>]

規則（--rules を省くと下の DEFAULT_RULES）：
  view の視点の numpy の z バッファ（主役波・wave4・近い海・爪）で、region_px（表示の画素の多角形）の中の、主役波が空に接する縁の画素を探す。
  面の座標 t は、サブ行（uv6.x の値ごと）の頂点を列（uv6.y）の順にたどった弧長（m、断面に沿う）。材質の u は唇を短くした鼻でほとんど
  変わらない（見本04）ので使わない。
  縁の画素ごとに、その三角形の頂点のサブ行 s と t（t_v）、白の印（whiteSD）、内側（空から inward_px 画素奥）の主役波の画素の t の中央値（t_in）を読む。
  side "+t"：見える側が t の大きい側（t_in > t_v、前・巻きの内の面の側）の縁だけを使う。
  主の視点では、縁の画素の面が白（whiteSD > −white_tol_m）のサブ行だけを規則の行にする（縁がもう藍の行は変えない。例：唇の鉤の下）。
  サブ行ごとに t_cut(s) = 縁の t の最小。
  also_views（例：座席・座席から波・波頭の回り台 0°・45°）では、規則の行の中で同じ縁（t が t_cut ± also_t_window_m）を探し、小さい方を取る（座席からも白が見えないように）。行は広げない。
  extend_end "max"：下の端（smax）の先も、同じ稜の白が続くサブ行まで t_cut を傾きで延ばして当てる（原画では隠れる所の白の切れ端を残さない）。
  サブ行の範囲 [smin, smax] の外は taper_subrows で重みを 0 へ下げる。範囲の中で縁の画素のないサブ行は線形に補い、
  最小値のならし（5 サブ行）と σ 2 サブ行でならす。
  頂点の新しい whiteSD = old + w(s)·lim(t)·(min(old, (t_cut(s) − margin_m) − t) − old)。
    つまり縁より margin_m 奥（見えない側）から先だけを白にし、縁から内の面の側は藍にする。lim は t が t_cut + span_m より先で 0（面の下の方は変えない）。
  whiteSD は面に沿った符号付きの距離（m）で、t は断面に沿う弧長（m）なので、min は二つの白の区域の共通部分の距離（の近似）になる。
  白の前の縁の水色の帯・白と藍の境の線は材質が whiteSD から作るので、白の境と一緒に縁の見えない側へ移る。

原画の色は面へ写さない（Q28・G1）。原画のカメラは、どの頂点が縁を作るかを探すのにだけ使い、結果は面の頂点の属性として残る（どの視点でも同じ色）。
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from scipy import ndimage as ndi

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mat_common as M  # noqa: E402

T0 = time.time()

# 既定の規則（見本05、2026-10-04）。表示の画素は 1920×1080 の原画視点の描画（Unity の描画と同じカメラ）。
DEFAULT_RULES = [
    {"id": "T6_inner_curl_edge",
     "ja": "唇の下の内の縁（Q33 の利用者の切り出し）：原画視点で、藍の面が巻きの中の空に接する縁。原画では藍の面がそのまま縁の線まで来る",
     "view": "painting",
     # 切り出し（x 736〜891、y 300〜721）を 6 画素広げ、上の右（y 340〜430）だけ x 925 まで広げる：切り出しの右上の角（x 874〜891、y 365〜380）に
     # 見える白・水色の楔（c 5.5〜6.1 m の鼻の先）の縁の画素は x 897〜925 にあるため（第 1 版の範囲では楔が残った）。唇の鉤（x 925 より右）は入れない。
     "region_px": [[730, 294], [897, 294], [897, 340], [925, 340], [925, 430], [897, 430], [897, 727], [730, 727]],
     "side": "+t", "also_views": ["seat", "seat_toward_wave", "crest0", "crest45"], "also_t_window_m": 3.0, "white_tol_m": 0.1,
     "margin_m": 0.5, "taper_subrows": 10, "span_m": 8.0, "inward_px": [6, 18], "extend_end": "max"},
]

# 原画で「藍の面が輪郭線まで来る」かを見た所（原画視点の表示の画素）。applied = 規則を当てたか。
CHECKED_PLACES = [
    {"id": "T6_inner_curl_edge", "px": [730, 294, 897, 727], "applied": True,
     "painting_ja": "巻きの内の面の右の縁（唇の爪の下から手前の小さな波の後ろまで）。藍の面と藍の帯がそのまま細い縁の線まで来る。白い点は空の側に飛ぶ（飛沫）",
     "sample04_ja": "縁の線の内側に白の帯（右の脇の稜の頂の白）と水色の帯が 10〜40 画素見える（c 6.8〜13.7 m の右の脇の稜）"},
    {"id": "lip_hook_underside", "px": [890, 290, 1110, 480], "applied": False,
     "painting_ja": "唇の先の鉤（浪尖の爪）。白と水色の爪で、藍の面は縁に来ない",
     "reason_ja": "浪尖（波頭の爪）は今は考えない（Q33-6）。白のまま"},
    {"id": "crest_back_outline", "px": [300, 80, 1000, 300], "applied": False,
     "painting_ja": "頂と背の外の輪郭。白（と水色）の頂で、藍は来ない",
     "reason_ja": "原画も白なので変えない"},
    {"id": "left_white_r2_r3", "px": [0, 360, 600, 620], "applied": False,
     "painting_ja": "左側の ②③ の白い房・爪の群れの外の輪郭。白と水色の爪",
     "reason_ja": "原画も白・水色。③ の形は形づくりで扱う（S11）"},
    {"id": "wave4_top_edge", "px": [157, 355, 330, 450], "applied": False,
     "painting_ja": "④ 左端の小さな青い波の上の縁。輪郭線のすぐ下に水色の細い帯があり、その下が藍（白い点 3 つ）",
     "reason_ja": "原画で水色の帯が輪郭線の下にあるので、藍が縁まで来る所ではない。wave4 は見本04 のまま"},
    {"id": "inner_face_low_right", "px": [780, 690, 1100, 800], "applied": False,
     "painting_ja": "巻きの内の面の下（谷へ下りる所）。手前の小さな波の白い頂の後ろに隠れ、見える所は藍が輪郭線まで来る",
     "reason_ja": "見本04 でもここは藍が輪郭線まで来ている（白の帯なし）。T6 の規則の下の端（c 13.7 m）の先は白がない"},
]


def log(*a):
    print("[%6.1fs]" % (time.time() - T0), *a, flush=True)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def edge_pixels(view, tris, lab, th, H, region=None, inward=(6, 18), side="+t"):
    """view の縁の画素：列 (y, x, s, t_v, t_in, wsd)。region（多角形）があればその中だけ。side の向きの縁と、そうでない縁を返す。"""
    cm, idb, D, L = M.raster(view, tris, lab)
    C, sky = M.sky_contour(D, L)
    if region is not None:
        C &= M.poly_mask(region, cm.W, cm.H)
    ys, xs = np.nonzero(C)
    hero = L == 1
    tid = np.where(hero, idb - 1, -1)
    tmap = np.full(L.shape, np.nan)
    hv = th[tid[hero]]
    tmap[hero] = H.t[hv].mean(1)
    dt = ndi.distance_transform_edt(~sky)
    ring = hero & (dt >= inward[0]) & (dt <= inward[1])
    out = []
    R = inward[1]
    for y, x in zip(ys, xs):
        v3 = th[tid[y, x]]
        tv = H.t[v3].mean()
        s = int(np.round(H.sr[v3].mean()))
        y0, y1, x0, x1 = max(y - R, 0), min(y + R + 1, cm.H), max(x - R, 0), min(x + R + 1, cm.W)
        w = ring[y0:y1, x0:x1]
        if not w.any():
            continue
        yy, xx = np.nonzero(w)
        k = (yy + y0 - y) ** 2 + (xx + x0 - x) ** 2 <= R * R
        if k.sum() < 3:
            continue
        tin = float(np.median(tmap[y0:y1, x0:x1][w][k]))
        out.append((y, x, s, tv, tin, H.wsd[v3].mean()))
    a = np.array(out, np.float64).reshape(-1, 6)
    keep = (a[:, 4] > a[:, 3] + 0.2) if side == "+t" else (a[:, 4] < a[:, 3] - 0.2)
    return a[keep], a[~keep], cm


def run_rule(rule, ch, tri, H, claws):
    tris, lab, th = M.scene(ch, tri, H.n, claws=claws)
    tris_ns, lab_ns, _ = M.scene(ch, tri, H.n, claws=claws, with_sea=False)
    tol = rule.get("white_tol_m", 0.1)
    log(rule["id"], "主の視点", rule["view"])
    a_all, rej, _ = edge_pixels(rule["view"], tris, lab, th, H, rule.get("region_px"), tuple(rule.get("inward_px", (6, 18))), rule.get("side", "+t"))
    a = a_all[a_all[:, 5] > -tol] if len(a_all) else a_all
    rec = {"id": rule["id"], "ja": rule.get("ja"), "view": rule["view"], "edge_px_side": int(len(a_all)), "edge_px_other_side": int(len(rej)),
           "edge_px_white": int(len(a))}
    ind = a_all[a_all[:, 5] <= -tol] if len(a_all) else a_all
    if len(ind):
        si = ind[:, 2].astype(int)
        rec["edge_already_indigo"] = {"px": int(len(ind)), "subrows": [int(si.min()), int(si.max())],
                                      "c_m": [M.rnd(H.c_sr[si.min()], 2), M.rnd(H.c_sr[si.max()], 2)],
                                      "note_ja": "縁の画素の面がもう藍の所（規則の行に入れない）"}
    if not len(a):
        rec["note_ja"] = "縁の画素に白がない（この形ではこの縁はもう藍で縁まで来る）。変えない"
        return None, rec
    s = a[:, 2].astype(int)
    tcut = np.full(H.nsr, np.inf)
    np.minimum.at(tcut, s, a[:, 3])
    smin, smax = int(s.min()), int(s.max())
    rec.update({"subrows": [smin, smax], "rows": [M.rnd(H.row_values[smin], 2), M.rnd(H.row_values[smax], 2)],
                "c_m": [M.rnd(H.c_sr[smin], 2), M.rnd(H.c_sr[smax], 2)], "also": {}})
    known = np.isfinite(tcut)
    ref = np.interp(np.arange(H.nsr), np.nonzero(known)[0], tcut[known])
    for v in rule.get("also_views", []):
        log(rule["id"], "ほかの視点", v)
        tv_, lv_ = (tris_ns, lab_ns) if v.startswith("crest") else (tris, lab)   # 波頭の回り台は海を隠して描く（描画と同じ）
        b, _, _ = edge_pixels(v, tv_, lv_, th, H, None, tuple(rule.get("inward_px", (6, 18))), rule.get("side", "+t"))
        if not len(b):
            rec["also"][v] = {"edge_px_same_edge": 0}
            continue
        sb = b[:, 2].astype(int)
        ok = (sb >= smin) & (sb <= smax) & (np.abs(b[:, 3] - ref[np.clip(sb, 0, H.nsr - 1)]) <= rule.get("also_t_window_m", 3.0))
        before = np.where(np.isfinite(tcut), tcut, ref)
        cur = before.copy()
        np.minimum.at(cur, sb[ok], b[ok, 3])
        lowered = cur < before - 1e-9
        tcut = np.where(lowered, cur, tcut)
        rec["also"][v] = {"edge_px_same_edge": int(ok.sum()), "edge_px_white": int((b[ok, 5] > -tol).sum()),
                          "subrows_lowered": int(lowered.sum()),
                          "max_lowering_m": M.rnd((before - cur)[lowered].max(), 2) if lowered.any() else 0.0,
                          "subrows_lowered_ja": "主の視点より縁の t が小さかったサブ行の数（その視点からは稜の向こうが少し多く見える）"}
    known = np.isfinite(tcut)
    idx = np.arange(H.nsr)
    tc = np.interp(idx, np.nonzero(known)[0], tcut[known])
    tc = ndi.minimum_filter1d(tc, 5, mode="nearest")
    tc = ndi.gaussian_filter1d(tc, 2.0, mode="nearest")
    tc[:smin] = tc[smin]
    tc[smax + 1:] = tc[smax]
    if rule.get("extend_end") == "max" and smax - 20 > smin:
        # 下の端（smax より先）：同じ稜の白が続くサブ行まで、t_cut を最後の 20 サブ行の傾きで延ばし、重み 1 で当てる
        # （原画では手前の小さな波の後ろに隠れるが、ほかの視点で稜の先に白の切れ端が残らないように）。
        slope = (tc[smax] - tc[smax - 20]) / 20.0
        ext = smax
        for s2 in range(smax + 1, H.nsr):
            tcs = tc[smax] + slope * (s2 - smax)
            m2 = (H.sr == s2) & (H.wsd > 0) & (H.t > tcs - rule.get("margin_m", 0.5) - 1.0) & (H.t < tcs + rule.get("span_m", 8.0))
            if not m2.any():
                break
            ext = s2
        for s2 in range(smax + 1, H.nsr):
            tc[s2] = tc[smax] + slope * (min(s2, ext + 10) - smax)
        rec["extend_end"] = {"from_subrow": smax, "to_subrow": ext, "c_m": M.rnd(H.c_sr[ext], 2), "slope_m_per_subrow": M.rnd(slope, 3)}
        smax = ext
    taper = int(rule.get("taper_subrows", 10))
    w = np.zeros(H.nsr)
    w[smin:smax + 1] = 1.0
    for k in range(1, taper + 1):
        tt = 0.5 * (1 + np.cos(np.pi * k / (taper + 1)))
        if smin - k >= 0:
            w[smin - k] = tt
        if smax + k < H.nsr:
            w[smax + k] = tt
    rec["t_cut_m_every_10_subrows"] = [[int(i), M.rnd(H.c_sr[i], 2), M.rnd(tc[i], 2)] for i in range(smin, smax + 1, 10)]
    return (tc, w), rec


def apply(H, wsd, tc, w, rule):
    m = rule.get("margin_m", 0.5)
    span = rule.get("span_m", 8.0)
    ws = w[H.sr]
    sel = ws > 0
    tcv = tc[H.sr]
    lim = smoothstep(tcv + span + 2.0, tcv + span, H.t)
    tgt = np.minimum(wsd, (tcv - m) - H.t)
    new = wsd.copy()
    new[sel] = wsd[sel] + (ws * lim)[sel] * (tgt - wsd)[sel]
    return new, ws * lim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=M.UNION04F)
    ap.add_argument("--out", required=True)
    ap.add_argument("--hero-verts", type=int, default=None)
    ap.add_argument("--claws", default=M.CLAWS04F)
    ap.add_argument("--rules", default=None)
    ap.add_argument("--report", default=None)
    g = ap.parse_args()
    ch, tri, j = M.read_static(g.mesh)
    nh = g.hero_verts or (M.N_HERO04F if os.path.normpath(g.mesh) == os.path.normpath(M.UNION04F) else len(ch["position"]))
    log("読み込み", g.mesh, "主役波の頂点", nh)
    H = M.Hero(ch, tri, nh)
    rules = M.jl(g.rules) if g.rules else DEFAULT_RULES
    wsd = H.wsd.copy()
    recs = []
    wmax = np.zeros(nh)
    for r in rules:
        res, rec = run_rule(r, ch, tri, H, g.claws)
        if res is not None:
            uc, w = res
            new, wv = apply(H, wsd, uc, w, r)
            flipped = (wsd > 0) & (new <= 0)
            rec["white_vertices_to_indigo"] = int(flipped.sum())
            rec["white_area_to_indigo_m2"] = M.rnd(H.varea[flipped].sum(), 2)
            rec["indigo_vertices_to_white"] = int(((wsd <= 0) & (new > 0)).sum())
            rec["changed_vertices"] = int((np.abs(new - wsd) > 1e-6).sum())
            wsd = new
            wmax = np.maximum(wmax, wv)
        recs.append(rec)
        log(json.dumps({k: rec.get(k) for k in ("id", "edge_px_white", "subrows", "c_m", "white_vertices_to_indigo")}, ensure_ascii=False))
    ch2 = {k: v.copy() for k, v in ch.items()}
    ch2["uv5"][:nh, 2] = wsd.astype(np.float32)
    extra = {"as05_mat_edge": {"source": M.rel(g.mesh), "source_sha256": j.get("sha256"), "hero_vertices": nh,
                               "note_ja": "主役波の頂点の whiteSD（uv5.z）だけを Tools/GWWaveGen/as05/mat_edge.py で書き換えた。ほかは入力と同じ"}}
    h = M.write_static(g.out, ch2, tri, extra)
    np.save(os.path.splitext(g.out)[0] + "_edge_weight.npy", wmax.astype(np.float32))
    rep = {"schema": "GreatWave.AS05.mat_edge/1", "date": time.strftime("%Y-%m-%d %H:%M"), "tool": M.rel(__file__), "tool_sha256": M.sha(__file__),
           "input": {"mesh": M.rel(g.mesh), "bin_sha256": j.get("sha256"), "claws": M.rel(g.claws) if g.claws else None, "hero_vertices": nh},
           "output": {"mesh": M.rel(g.out), "bin_sha256": h, "edge_weight_npy": M.rel(os.path.splitext(g.out)[0] + "_edge_weight.npy")},
           "rules": rules, "results": recs, "checked_places": CHECKED_PLACES,
           "white_vertices_before_after": [int((H.wsd > 0).sum()), int((wsd > 0).sum())],
           "geometry_unchanged": True, "seconds": round(time.time() - T0, 1),
           "note_ja": ("原画の色は面へ写さない。原画のカメラ（と座席）は縁を作る頂点を探すのにだけ使い、結果は頂点の whiteSD に残る（どの視点でも同じ色）。"
                       "位置・三角形・ほかの属性・wave4 は変えない（原画視点の輪郭の関門は形が同じなので変わらない）。")}
    M.jdump(g.report or os.path.splitext(g.out)[0] + "_edge_report.json", rep)
    log("書いた", g.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
