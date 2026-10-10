# -*- coding: utf-8 -*-
"""RT48 つなぎ・確かめの段：Unity の書き出し（RT48VerifyExport）を Python で比べる（record_ja.md の V1〜V6。py -3.10）。
使い方:
  py -3.10 v_compare.py coarse unity_editor      Unity/Build/RT48/verify/coarse/unity_editor/ を比べる
  py -3.10 v_compare.py coarse unity_player
出力：Unity/Build/RT48/verify/<元>/<書き出し>_result.json（数の全部）と、標準出力のまとめ。判定の幅は record_ja.md のとおり（計画 C4〜C6 のまま）。"""
import os as _os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ.setdefault(_v, "1")
import sys, os, json, math, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import r_lib as L
import u_bakeio as U


def _js(o):
    return o.item() if hasattr(o, "item") else str(o)

BUILD = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/RT48"
TOL_POS, TOL_NORM = 1e-4, 0.5
TOL_C4_MAX, TOL_C4_P99 = 0.25, 0.05
TOL_H, TOL_P = 0.001, 0.01


def ulp32(a):
    a = np.maximum(np.abs(a), 1.1754943508222875e-38)
    return np.power(2.0, np.floor(np.log2(a)) - 23.0)


def taper_w(xs, tp):
    return U.taper_weight(xs, tp)


def normals(disp):
    """表示の点（N,2）の i−1・i+1 から左の法線（Unity と同じ）。返り値 (N,2) と長さ"""
    n = len(disp)
    i0 = np.maximum(np.arange(n) - 1, 0); i1 = np.minimum(np.arange(n) + 1, n - 1)
    t = disp[i1] - disp[i0]
    Ln = np.hypot(t[:, 0], t[:, 1])
    with np.errstate(divide="ignore", invalid="ignore"):
        nv = np.stack([-t[:, 1] / Ln, t[:, 0] / Ln], 1)
    return nv, Ln


def check_curve(gpu, xy_raw, seat, x0, tp):
    """gpu (N,4) float32、xy_raw (N,2) float64 の生の曲線（保存の座標）。V1 の幅で比べる"""
    xs = xy_raw[:, 0]
    disp = np.stack([xs, xy_raw[:, 1] * taper_w(xs, tp)], 1)
    X = disp[:, 0] + (x0 - seat)
    Y = disp[:, 1]
    tol = np.maximum(TOL_POS, 4.0 * ulp32(np.maximum(np.abs(disp[:, 0]), np.abs(X))))
    e = np.maximum(np.abs(gpu[:, 0] - X), np.abs(gpu[:, 1] - Y))
    nv, Ln = normals(disp)
    g = gpu[:, 2:4].astype(np.float64)
    gl = np.hypot(g[:, 0], g[:, 1])
    ok = Ln > 1e-12
    dot = np.clip((nv[ok, 0] * g[ok, 0] + nv[ok, 1] * g[ok, 1]) / np.maximum(gl[ok], 1e-30), -1, 1)
    ang = np.degrees(np.arccos(dot))
    return dict(max_pos=float(e.max()), max_over_tol=float((e / tol).max()), n_fail_pos=int((e > tol).sum()),
                max_norm_deg=float(ang.max()) if len(ang) else 0.0, n_fail_norm=int((ang > TOL_NORM).sum()))


def main(src, tag):
    T0 = time.time()
    vd = os.path.join(BUILD, "verify", src)
    ed = os.path.join(vd, tag)
    idx = json.load(open(os.path.join(ed, "index.json"), encoding="utf-8-sig"))
    man = json.load(open(os.path.join(BUILD, "data", src, "manifest.json"), encoding="utf8"))
    N = idx["nPoints"]; x0 = idx["xOriginM"]; tp = tuple(idx["taperStored"])
    P = man["playback"]["n_pairs"]
    pairs = np.fromfile(os.path.join(BUILD, "data", src, "pairs.bin"), dtype="<f4").reshape(P, 2, N, 2)
    curves = np.memmap(os.path.join(ed, "curves.bin"), dtype="<f4", mode="r")
    res = dict(source=src, export=tag, gpu=idx["gpu"], isEditor=idx["isEditor"], graphicsApi=idx["graphicsApi"], unity_utc=idx["utc"])

    def gpu_of(c):
        o = int(c["offsetFloats"])
        return np.asarray(curves[o:o + 4 * N], dtype=np.float32).reshape(N, 4)

    # ---------------- V1・V3
    groups = {}
    for c in idx["curves"]:
        p, a = c["pair"], c["alpha"]
        A = pairs[p, 0].astype(np.float64); B = pairs[p, 1].astype(np.float64)
        raw = A if a == 0.0 else (B if a == 1.0 else A + (B - A) * a)
        r = check_curve(gpu_of(c), raw, c["seatX"], x0, tp)
        g = groups.setdefault(c["group"], dict(n=0, max_pos=0.0, max_over_tol=0.0, n_fail_pos=0, max_norm_deg=0.0, n_fail_norm=0, n_cases_fail=0))
        g["n"] += 1
        for k in ("max_pos", "max_over_tol", "max_norm_deg"):
            g[k] = max(g[k], r[k])
        g["n_fail_pos"] += r["n_fail_pos"]; g["n_fail_norm"] += r["n_fail_norm"]
        g["n_cases_fail"] += int(r["n_fail_pos"] > 0 or r["n_fail_norm"] > 0)
    for g in groups.values():
        g["pass"] = g["n_fail_pos"] == 0 and g["n_fail_norm"] == 0
    res["V1_V3"] = groups
    print("V1/V3", json.dumps(groups, ensure_ascii=False, default=_js), round(time.time() - T0, 1), "s", flush=True)

    # ---------------- V2：再生した形と R3 の記録の等高線
    cz = np.load(os.path.join(vd, "contours.npz"))
    cpts, coffs, cframes = cz["pts"], cz["offs"], cz["frames"]
    f0 = int(cframes[0])
    contour = lambda f: cpts[coffs[f - f0]:coffs[f - f0 + 1]]
    c3max = float(man["checks"]["C3"]["max"])
    src556 = {(c["pair"], c["alpha"]): c for c in idx["curves"] if c["group"] == "src556"}
    v2 = []
    win = (200.0, 825.0)
    for f in range(f0, f0 + P + 1):
        c = src556[(f - f0, 0.0)] if f - f0 < P else src556[(P - 1, 1.0)]
        g = gpu_of(c)
        Pu = np.stack([g[:, 0].astype(np.float64) + c["seatX"], g[:, 1].astype(np.float64)], 1)
        d1, d2 = L.two_way(Pu, contour(f), h=0.005, win=win)
        v2.append(dict(frame=f, max=float(max(d1.max(), d2.max())), p99=float(np.percentile(np.concatenate([d1, d2]), 99))))
    mx = max(r["max"] for r in v2)
    res["V2"] = dict(n_frames=len(v2), max=mx, worst_frame=max(v2, key=lambda r: r["max"])["frame"], tol=c3max + 1e-4, c3max=c3max,
                     n_frames_over_002=sum(1 for r in v2 if r["max"] > 0.02), median_of_max=float(np.median([r["max"] for r in v2])),
                     max_before_onset=max(r["max"] for r in v2 if r["frame"] < man["events"]["onset_frame"]),
                     pass_=mx <= c3max + 1e-4, rows=v2)
    print("V2", {k: v for k, v in res["V2"].items() if k != "rows"}, round(time.time() - T0, 1), "s", flush=True)

    # ---------------- V4：目印
    frows = {r["frame"]: r for r in man["frames"]}
    def curve_xrel(f, seat=556.0):
        c = src556[(f - f0, 0.0)]
        g = gpu_of(c)
        return np.stack([g[:, 0].astype(np.float64) + seat, g[:, 1].astype(np.float64)], 1), g
    lm = {}
    for name, f in (("onset", man["events"]["onset_frame"]), ("contact", man["events"]["first_contact_frame"])):
        Pu, g = curve_xrel(f)
        xr, yr = frows[f]["crest_x"], frows[f]["crest_y"]
        m = np.abs(Pu[:, 0] - xr) <= 40.0
        i = np.where(m)[0][np.argmax(Pu[m, 1])]
        lm[name] = dict(frame=f, record=[xr, yr], record_unity_X=xr - 556.0, unity_X=float(g[i, 0]), unity_Y=float(g[i, 1]),
                        dX=float(Pu[i, 0] - xr), dY=float(Pu[i, 1] - yr), pass_=abs(Pu[i, 0] - xr) <= 1.0 and abs(Pu[i, 1] - yr) <= 0.25)
    f = man["events"]["first_contact_frame"] - 1
    Pu, g = curve_xrel(f)
    lr = frows[f]["lip"]
    ic = L.crest_in(Pu, frows[f]["crest_x"], half=1.0)
    il_u = U.find_lip_tip(Pu, ic)
    il_r = L.lip_tip(Pu, ic, Pu[ic, 0])
    def lipd(il):
        return None if il is None or il < 0 else dict(x=float(Pu[il, 0]), y=float(Pu[il, 1]), d=float(math.hypot(Pu[il, 0] - lr[0], Pu[il, 1] - lr[1])))
    lu, lrr = lipd(il_u), lipd(il_r)
    lm["lip_contact_minus1"] = dict(frame=f, record=lr, u_bakeio_find_lip_tip=lu, r_lib_lip_tip=lrr,
                                    pass_declared=lu is not None and lu["d"] <= 0.5, pass_r_lib=lrr is not None and lrr["d"] <= 0.5)
    bl = [b for b in idx["boats"] if b["kind"].startswith("landmark")] + [b for b in idx["boats"] if not b["kind"].startswith("landmark")]
    ebx = max(abs(b["rootX"]) for b in bl); ebz = max(abs(b["rootZ"]) for b in bl); eby = max(abs(b["rootY"] - b["heave"]) for b in bl)
    erz = max(abs(b["rootRollZDeg"] - b["pitchDeg"]) for b in bl)
    lm["boat_root"] = dict(n=len(bl), max_abs_X=ebx, max_abs_Z=ebz, max_abs_Y_minus_heave=eby, max_abs_rot_minus_pitch_deg=erz,
                           cam_X_range=[min(b["camX"] for b in bl), max(b["camX"] for b in bl)],
                           cam_Y_minus_heave_range=[min(b["camY"] - b["heave"] for b in bl), max(b["camY"] - b["heave"] for b in bl)],
                           pass_=ebx <= 1e-4 and ebz <= 1e-4 and eby <= 1e-4)
    res["V4"] = lm
    print("V4", json.dumps(lm, ensure_ascii=False, default=_js), flush=True)

    # ---------------- V5：取り置いたコマ（C4 を Unity で）
    if idx.get("holdout"):
        hout = np.memmap(os.path.join(ed, idx["holdoutFile"]), dtype="<f4", mode="r")
        hidx = json.load(open(os.path.join(vd, "holdout_index.json"), encoding="utf8"))
        cz_xc = {int(fr): float(x) for fr, x in zip(cz["frames"], cz["xc"])}
        rows2, e3 = [], []
        for c in idx["holdout"]:
            o = int(c["offsetFloats"])
            g = np.asarray(hout[o:o + 4 * N], dtype=np.float32).reshape(N, 4)
            Pu = np.stack([g[:, 0].astype(np.float64) + 556.0, g[:, 1].astype(np.float64)], 1)
            k, kb, a = c["frameA"], c["frameB"], c["alpha"]
            tgt = k + 1 if (kb - k == 2 or abs(a - 1 / 3) < 1e-9) else k + 2
            w = (cz_xc[tgt] - L.WIN_I, cz_xc[tgt] + L.WIN_I)
            d1, d2 = L.two_way(Pu, contour(tgt), h=0.01, win=w)
            d = np.concatenate([d1, d2])
            mxx, p99 = float(d.max()), float(np.percentile(d, 99))
            if kb - k == 2:
                rows2.append(dict(k=k, max=mxx, p99=p99, ok=mxx <= TOL_C4_MAX and p99 <= TOL_C4_P99))
            else:
                e3.append(mxx)
        brow = {r["k"]: r for r in man["checks"]["C4"]["rows"]}
        diff_ok = [r["k"] for r in rows2 if r["ok"] != brow[r["k"]]["ok"]]
        dmax = max(max(abs(r["max"] - brow[r["k"]]["max"]), abs(r["p99"] - brow[r["k"]]["p99"])) for r in rows2)
        E2 = float(np.median([r["max"] for r in rows2])); E3 = float(np.median(e3))
        p_obs = float(np.log((9 / 8) * E3 / E2) / np.log(1.5))
        interp_k = [q["k"] for q in man["pairs"] if q["interp"]]
        near = [r for r in rows2 if r["k"] in interp_k or r["k"] + 1 in interp_k]
        res["V5"] = dict(n=len(rows2), n_fail=sum(1 for r in rows2 if not r["ok"]), n_fail_max=sum(1 for r in rows2 if r["max"] > TOL_C4_MAX),
                         n_fail_p99=sum(1 for r in rows2 if r["p99"] > TOL_C4_P99),
                         max_of_max=max(r["max"] for r in rows2), max_of_p99=max(r["p99"] for r in rows2),
                         median_max=E2, median_p99=float(np.median([r["p99"] for r in rows2])), E2=E2, E3=E3, p_observed=p_obs,
                         err_at_1_24s=(E2 * 2 ** (-p_obs)) if 1.5 <= p_obs <= 2.5 else None,
                         n_ok_flag_differs_from_bake=len(diff_ok), k_differs=diff_ok, max_value_diff_vs_bake=dmax,
                         for_interp_pairs=dict(n=len(near), max_of_max=max((r["max"] for r in near), default=None),
                                               max_of_p99=max((r["p99"] for r in near), default=None)),
                         rows=rows2)
        print("V5", {k: v for k, v in res["V5"].items() if k not in ("rows",)}, round(time.time() - T0, 1), "s", flush=True)

    # ---------------- V6：船
    meta = dict(fps=man["time"]["fps"], frame_first=man["time"]["first_frame"], frame_count=man["time"]["n_frames"], pair_count=P, n_points=N,
                pair_interp=[1 if q["interp"] else 0 for q in man["pairs"]], x_origin_m=x0,
                taper_m=[man["x_fade"]["ranges_x_rel"][0][0], man["x_fade"]["ranges_x_rel"][0][1], man["x_fade"]["ranges_x_rel"][1][0], man["x_fade"]["ranges_x_rel"][1][1]])
    assert np.allclose(U.taper_stored(meta), tp), (U.taper_stored(meta), tp)
    v6 = {}
    caches = {}
    for b in idx["boats"]:
        if b["kind"].startswith("landmark"):
            continue
        seat = b["seatX"]
        cache = caches.setdefault(seat, {})
        h, p, mode, st = U.boat_at(pairs, meta, b["t"], seat, cache)
        s = v6.setdefault("%g" % seat, dict(rows=[]))
        s["rows"].append(dict(t=b["t"], kind=b["kind"], unity_heave=b["heave"], unity_pitch=b["pitchDeg"], unity_mode=b["mode"],
                              py_heave=h, py_pitch=p, py_mode=mode, dh=abs(b["heave"] - h), dp=abs(b["pitchDeg"] - p), same_mode=b["mode"] == mode))
    for seat, s in v6.items():
        rs = s["rows"]
        s.update(n=len(rs), max_dh=max(r["dh"] for r in rs), max_dp=max(r["dp"] for r in rs), n_mode_differs=sum(1 for r in rs if not r["same_mode"]),
                 n_before_K=sum(1 for r in rs if r["kind"] != "after_K"), n_after_K=sum(1 for r in rs if r["kind"] == "after_K"),
                 modes=sorted(set(r["unity_mode"] for r in rs)))
        s["pass_"] = s["max_dh"] <= TOL_H and s["max_dp"] <= TOL_P and s["n_mode_differs"] == 0
        # 船と見せている水面のずれ（90 Hz）
        seatx = float(seat)
        end = man["boat"][seat]["clip_end_t"]
        cache = caches.setdefault(seatx, {})
        t0 = man["time"]["t_first"]
        gapK, gapH = dict(dh=0.0, dp=0.0, t_dh=None, t_dp=None), dict(dh=0.0, dp=0.0, t_dh=None, t_dp=None)
        for t in np.arange(t0, end + 1e-9, 1 / 90.0):
            h, p, mode, st = U.boat_at(pairs, meta, float(t), seatx, cache)
            if mode == "curve":
                continue
            k = st["frame"]
            if k not in cache:
                cache[k] = U.boat_from_curve(U.frame_curve(pairs, meta, k).astype(np.float64), seatx, meta)[:2]
            hs, ps = cache[k]
            tgt = gapK if (man["playback"]["K"] is not None and man["time"]["first_frame"] + k >= man["playback"]["K"]) else gapH
            if abs(h - hs) > tgt["dh"]:
                tgt["dh"], tgt["t_dh"] = abs(h - hs), float(t)
            if abs(p - ps) > tgt["dp"]:
                tgt["dp"], tgt["t_dp"] = abs(p - ps), float(t)
        s["gap_after_K"] = gapK
        s["gap_held_before_K"] = gapH
    res["V6"] = v6
    print("V6", json.dumps({k: {q: w for q, w in v.items() if q != "rows"} for k, v in v6.items()}, ensure_ascii=False, default=_js), flush=True)
    res["seconds"] = round(time.time() - T0, 1)
    out = os.path.join(vd, tag + "_result.json")
    json.dump(res, open(out, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=_js)
    print("wrote", out, res["seconds"], "s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
