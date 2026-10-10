# -*- coding: utf-8 -*-
"""FLIP42 R2 の段：断面の水面の場から、巻き始め・着水・(c) の量（C1〜C4）と §6 の見た目の量を出す（py -3.10）。
測り方は record_ja.md の「計画の読み方」7〜9 と、その続き 12〜18（R3 の結果を見る前に決めた）のとおり。
巻き始めと着水の時刻の決め方は g_analyze.py と同じ関数（frame_shape）を使う。
使い方: py -3.10 g_shape.py <run_id> [--parent=<run_id>]   → runs/<run_id>/shape.json
  --parent：静かな水面をその計算の ana.json から取る（R5' は 138.2 s より前の記録がないため。読み方 15）。
"""
import sys, os, json
import numpy as np
from skimage import measure

sys.path.insert(0, r"G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/flip42")
import g_analyze as A

OFFS = [-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3]


def contours(sdf, meta, off):
    S = sdf.astype(np.float32)
    xs = meta["x0"] + meta["dx"] * np.arange(meta["nx"])
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - off
    j0 = int(np.searchsorted(ys, -25.0))
    S2 = S[j0:]; ys2 = ys[j0:]
    out = []
    for c in measure.find_contours(S2, 0.0):
        out.append(np.stack([xs[0] + c[:, 1] * meta["dx"], ys2[0] + c[:, 0] * meta["dy"]], 1))
    return out, S, xs, ys


def cross_y(path, xq):
    """path（折れ線）が x = xq を横切る所の y（全部）。"""
    ys = []
    for i in range(len(path) - 1):
        x0, x1 = path[i, 0], path[i + 1, 0]
        if (x0 - xq) * (x1 - xq) <= 0 and x0 != x1:
            w = (xq - x0) / (x1 - x0)
            ys.append(path[i, 1] + w * (path[i + 1, 1] - path[i, 1]))
    return ys


def extra(sdf, meta, off, vox, Lc, sh, xp):
    """読み方 12・13・16 の量（1 コマ）。sh は g_analyze.frame_shape の出力。"""
    lines, S, xs, ys = contours(sdf, meta, off)
    face = sh["face"]; main = sh["main"]
    r = {}
    # 12：前の面に沿って初めて 90° 以上になった点
    if len(face) >= 3:
        d = face[2:] - face[:-2]
        th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
        k = np.where((th >= 90) & (th <= 180))[0]
        r["vertical_x_rel"] = float(face[k[0] + 1, 0] - xp) if len(k) else None
        r["vertical_y"] = float(face[k[0] + 1, 1]) if len(k) else None
    # 噴流（唇）：前の面を頂から前へたどり、x が初めて極大になって、その後 1 格子以上戻る点を唇の先とする。
    # 2026-10-10 04:40 に直した（R3 を見た後）：g_analyze.frame_shape の先（前の面全体の x の最大）は、唇の先が
    # 前の面の静かな水面を切る点より後ろにある形では見つからなかった。巻き始め・着水の時刻の決め方は変わらない。
    jet = None
    if len(face) >= 3:
        xx = face[:, 0]
        for i in range(1, len(xx) - 1):
            if xx[i] >= xx[i - 1] and xx[i] > xx[i + 1]:
                j = i + 1
                while j < len(xx) and xx[j] <= xx[i]:
                    j += 1
                seg = face[i:j]
                iw_rel = int(np.argmin(seg[:, 0]))
                if xx[i] - seg[iw_rel, 0] >= vox:
                    iw = i + iw_rel
                    xw = float(face[iw, 0]); xt = float(xx[i])
                    reach = xt - xw
                    xm = xw + 0.5 * reach
                    up = cross_y(face[:i + 1], xm); lo = cross_y(face[i:iw + 1], xm)
                    thick = (max(up) - max(lo)) if (up and lo) else None
                    jet = dict(kind="lip", x_tip_rel=xt - xp, y_tip=float(face[i, 1]), x_wall_rel=xw - xp, reach=reach, thick_mid=thick)
                    break
    # 空気を囲む閉じた線（g_analyze と同じ選び方）の前の端と後ろの端
    cav = []
    xc, yc = sh["xc"], sh["yc"]
    for l in lines:
        if len(l) > 4 and np.allclose(l[0], l[-1]):
            Aa = A.poly_area(l)
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            if Aa >= vox * vox and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                ix = int(round((cx - xs[0]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0:
                    cav.append(dict(x_front_rel=float(l[:, 0].max() - xp), x_back_rel=float(l[:, 0].min() - xp), area=float(Aa),
                                    y_top=float(l[:, 1].max()), y_bot=float(l[:, 1].min()), poly=l))
    if cav:
        big = max(cav, key=lambda q: q["area"])
        xb_, xf_ = big["x_back_rel"] + xp, big["x_front_rel"] + xp
        xm = 0.5 * (xb_ + xf_)
        up = cross_y(main, xm); lo = cross_y(big["poly"], xm)
        thick = (max(up) - max(lo)) if (up and lo) else None
        r["cavity"] = dict(n=len(cav), x_front_rel=big["x_front_rel"], x_back_rel=big["x_back_rel"], area=big["area"], reach=xf_ - xb_, thick_mid=thick)
        jet_cav = dict(kind="cavity", x_tip_rel=big["x_front_rel"], x_wall_rel=big["x_back_rel"], reach=xf_ - xb_, thick_mid=thick)
    else:
        jet_cav = None
    r["jet_lip"] = jet; r["jet_cav"] = jet_cav
    r["jet"] = jet if jet is not None else jet_cav
    # 16 (4)：頂の断面積（頂の前後で水面が静かな水面を切る 2 点の間、静かな水面より上の水）
    ic = int(np.argmax(main[:, 1]))
    a_ = main[max(ic - 3, 0)][0]; b_ = main[min(ic + 3, len(main) - 1)][0]
    back = main[:ic + 1][::-1] if b_ >= a_ else main[ic:]
    xback = None
    for j in range(len(back)):
        if back[j, 1] <= 0:
            xback = float(back[j, 0]); break
    xfront = float(face[-1, 0]) if (len(face) and face[-1, 1] <= 0) else None
    jy = ys > 0
    cell = meta["dx"] * meta["dy"]
    if xback is not None and xfront is not None:
        jx = (xs >= xback) & (xs <= xfront)
        r["crest_area"] = float((S[np.ix_(jy, jx)] < 0).sum() * cell)
    else:
        r["crest_area"] = None
    r["x_back0_rel"] = None if xback is None else xback - xp
    r["x_front0_rel"] = None if xfront is None else xfront - xp
    # 16 (5)：噴流の後ろの端より前にある、静かな水面より上の水
    if jet is not None:
        x_end = (xfront if xfront is not None else jet["x_tip_rel"] + xp) + vox
        x_end = max(x_end, jet["x_tip_rel"] + xp + vox)
        jx = (xs > jet["x_wall_rel"] + xp) & (xs <= x_end)
        r["ahead_area"] = float((S[np.ix_(jy, jx)] < 0).sum() * cell)
    else:
        r["ahead_area"] = None
    return r


def run(rid, parent=None):
    P = A.plan(); C = A.comps_full(P)
    cfg = json.load(open(os.path.join(A.ROOT, rid, "cfg.json"), encoding="utf8"))
    xp = cfg["parms"]["x_p"]; Lc = C["Lc"]; Tc = C["Tc"]
    vox = cfg["parms"]["dp"] * 2.0
    D = A.load_hf(rid)
    if parent:
        off = json.load(open(os.path.join(A.ROOT, parent, "ana.json"), encoding="utf8"))["still_level_offset_m"]
    else:
        off = json.load(open(os.path.join(A.ROOT, rid, "ana.json"), encoding="utf8"))["still_level_offset_m"]
    SEC = A.load_sec(rid)
    meta = SEC["meta"]
    x = D["x"]; mid = D["eta"].shape[1] // 2
    fidx = {int(fv): i for i, fv in enumerate(D["frames"])}
    rows = []
    onset = touch = None
    cache = {}
    for j, fv in enumerate(SEC["frames"]):
        i = fidx.get(int(fv))
        if i is None:
            continue
        sh = A.frame_shape(SEC["sdf"][j], meta, off, vox, Lc, None, None)
        if sh is None:
            continue
        etop = D["eta"][i, mid, :] - off
        tm = A.top_measures(etop, x, sh["xc"], Lc)
        row = dict(frame=int(fv), t=float(SEC["t"][j]), xc_rel=sh["xc"] - xp, yc=sh["yc"], thmax=sh["thmax"], steep_h60=sh["steep_h60"],
                   tip=None if sh["tip"] is None else [sh["tip"][0] - xp, sh["tip"][1]], ncav=len(sh["cav"]))
        if tm:
            row.update(eta_c=tm["eta_c"], H=tm["H"], trough=tm["trough"], x_trough_rel=tm["x_trough"] - xp, d_zero=tm["d_zero"], steep=tm["steep"])
        is_onset = onset is None and np.isfinite(sh["thmax"]) and sh["thmax"] >= 90.0
        is_touch = (not is_onset) and onset is not None and touch is None and \
            ((sh["tip"] is not None and sh["tip"][1] <= 0.0) or len(sh["cav"]) > 0)
        row.update(extra(SEC["sdf"][j], meta, off, vox, Lc, sh, xp))
        rows.append(row)
        if is_onset:
            onset = dict(row)
        elif is_touch:
            touch = dict(row)
            touch["by"] = "tip<=0" if (sh["tip"] is not None and sh["tip"][1] <= 0.0) else "cavity"
            if touch["by"] == "tip<=0":
                touch["x_rel"] = sh["tip"][0] - xp
            else:
                touch["x_rel"] = (touch.get("cavity") or {}).get("x_front_rel")
    out = dict(run_id=rid, parent=parent, still_level_offset_m=off, vox=vox, onset=onset, touchdown=touch)
    if onset is not None:
        out["C"] = dict(t_onset=onset["t"], x_onset=onset.get("vertical_x_rel"), xc_onset=onset["xc_rel"], H=onset.get("H"), eta_c=onset.get("eta_c"),
                        steep=onset.get("steep"))
        if touch is not None:
            out["C"].update(t_touch=touch["t"], x_touch=touch.get("x_rel"), jet_time=touch["t"] - onset["t"],
                            jet_dist=(touch["x_rel"] - onset["vertical_x_rel"]) if (touch.get("x_rel") is not None and onset.get("vertical_x_rel") is not None) else None)
        # 巻き始めにそろえた時刻の見た目の量（読み方 16）
        ph = []
        tt_all = np.array([r["t"] for r in rows])
        for o in OFFS:
            k = int(np.argmin(abs(tt_all - (onset["t"] + o * Tc))))
            r = rows[k]
            ph.append(dict(off_Tc=o, t=r["t"], eta_c=r.get("eta_c"), H=r.get("H"), steep_h60=r.get("steep_h60"), steep_h60_over_H=(r.get("steep_h60") / r["H"]) if r.get("H") else None,
                           thmax=r.get("thmax"), jet=r.get("jet"), jet_lip=r.get("jet_lip"), jet_cav=r.get("jet_cav"), crest_area=r.get("crest_area"), ahead_area=r.get("ahead_area"), xc_rel=r["xc_rel"]))
        if touch is not None:
            ph.append(dict(off_Tc="touchdown", t=touch["t"], eta_c=touch.get("eta_c"), H=touch.get("H"), steep_h60=touch.get("steep_h60"),
                           steep_h60_over_H=(touch.get("steep_h60") / touch["H"]) if touch.get("H") else None, thmax=touch.get("thmax"),
                           jet=touch.get("jet"), jet_lip=touch.get("jet_lip"), jet_cav=touch.get("jet_cav"), crest_area=touch.get("crest_area"), ahead_area=touch.get("ahead_area"), xc_rel=touch["xc_rel"]))
        out["phases"] = ph
    # D の判定（R3・R4）
    full = P["full"]
    D_ = {}
    if onset is not None:
        D_["D1_plunge"] = dict(onset=True, touchdown=touch is not None, by=None if touch is None else touch["by"],
                               cavity_at_or_after_touch=bool(touch is not None and (touch.get("cavity") is not None)))
        xo = onset.get("vertical_x_rel")
        D_["D2_onset_place"] = dict(x=xo, xc=onset["xc_rel"], band=full["breaking_band_RM_x"],
                                    ok=bool(xo is not None and full["breaking_band_RM_x"][0] <= xo <= full["breaking_band_RM_x"][1]))
        if touch is not None:
            dt = touch["t"] - full["tob_DK"]; dx = (touch.get("x_rel") or np.nan) - full["xob_DK"]
            D_["D3_touchdown"] = dict(t=touch["t"], x=touch.get("x_rel"), dt=dt, dx=dx, dt_over_Tc=dt / Tc, dx_over_Lc=dx / Lc,
                                      ok=bool(abs(dt) <= 0.25 * Tc and abs(dx) <= 0.25 * Lc))
    out["D"] = D_
    out["rows"] = rows
    json.dump(out, open(os.path.join(A.ROOT, rid, "shape.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
    return out


def compare(fine, coarse):
    """(c)：C1〜C4。基準は細かい方（刻みの小さい方）＝ fine（読み方 17）。"""
    P = A.plan(); C = A.comps_full(P)
    Tc, Lc = C["Tc"], C["Lc"]
    a = json.load(open(os.path.join(A.ROOT, fine, "shape.json"), encoding="utf8"))
    b = json.load(open(os.path.join(A.ROOT, coarse, "shape.json"), encoding="utf8"))
    ca, cb = a.get("C"), b.get("C")
    if not ca or not cb:
        return dict(fine=fine, coarse=coarse, note="巻き始めのない計算がある", fine_C=ca, coarse_C=cb)

    def rel(q):
        va, vb = ca.get(q), cb.get(q)
        return None if (va in (None, 0) or vb is None) else (vb - va) / va
    r = dict(fine=fine, coarse=coarse)
    dt = cb["t_onset"] - ca["t_onset"]
    dx = (cb["x_onset"] - ca["x_onset"]) if (ca.get("x_onset") is not None and cb.get("x_onset") is not None) else None
    r["C1"] = dict(dt=dt, dt_over_Tc=dt / Tc, dx=dx, dx_over_Lc=None if dx is None else dx / Lc,
                   ok=bool(abs(dt) <= 0.1 * Tc and dx is not None and abs(dx) <= 0.1 * Lc))
    r["C2"] = dict(H=(cb.get("H"), ca.get("H"), rel("H")), eta_c=(cb.get("eta_c"), ca.get("eta_c"), rel("eta_c")),
                   ok=bool(rel("H") is not None and abs(rel("H")) <= 0.05 and rel("eta_c") is not None and abs(rel("eta_c")) <= 0.05))
    r["C3"] = dict(steep=(cb.get("steep"), ca.get("steep"), rel("steep")), ok=bool(rel("steep") is not None and abs(rel("steep")) <= 0.10))
    if ca.get("jet_time") is not None and cb.get("jet_time") is not None:
        r["C4"] = dict(jet_time=(cb["jet_time"], ca["jet_time"], rel("jet_time")), jet_dist=(cb.get("jet_dist"), ca.get("jet_dist"), rel("jet_dist")),
                       ok=bool(rel("jet_time") is not None and abs(rel("jet_time")) <= 0.10 and rel("jet_dist") is not None and abs(rel("jet_dist")) <= 0.10))
    else:
        r["C4"] = dict(note="着水のない計算がある", ok=False)
    r["all_ok"] = bool(r["C1"]["ok"] and r["C2"]["ok"] and r["C3"]["ok"] and r["C4"]["ok"])
    return r


if __name__ == "__main__":
    if sys.argv[1] == "--compare":
        res = compare(sys.argv[2], sys.argv[3])
        outp = sys.argv[4] if len(sys.argv) > 4 else None
        if outp:
            json.dump(res, open(outp, "w", encoding="utf8"), ensure_ascii=False, indent=1, default=float)
        print(json.dumps(res, ensure_ascii=False, default=float))
    else:
        rid = sys.argv[1]
        par = None
        for q in sys.argv[2:]:
            if q.startswith("--parent="):
                par = q.split("=", 1)[1]
        o = run(rid, par)
        print(json.dumps(dict(run=rid, onset=None if not o["onset"] else {k: o["onset"].get(k) for k in ("t", "xc_rel", "vertical_x_rel", "eta_c", "H", "steep", "thmax")},
                              touch=None if not o["touchdown"] else {k: o["touchdown"].get(k) for k in ("t", "x_rel", "by")}, C=o.get("C"), D=o.get("D")),
                         ensure_ascii=False, default=float))
