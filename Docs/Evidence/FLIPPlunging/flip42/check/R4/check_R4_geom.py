# -*- coding: utf-8 -*-
"""FLIP42 R4 の独立の確かめ：形の量（巻き始め・着水・H（前と後ろの谷）・η_c・前の面の険しさ・唇・空気）を、
記録（hf と断面の水面の場）から自前で計算し直す。g_analyze.py・g_shape.py・x_r4_visual.py は使わず、読み込んでもいない。
py -3.10 check_R4_geom.py  → check_R4_geom.json・check_R4_rows.json（全コマの量）

自前の読み方（「計画の読み方」1・7・8・9・12・13・14・16 の文から作った）：
- 静かな水面：造波板から 0〜930 m・0.5〜2.0 s の一番上の水面の高さ（真ん中の節）の中央値。
- 頂・η_c・前の谷・後ろの谷・険しさ：一番上の水面の高さ（真ん中の節）。頂は断面の範囲（造波板から 321〜863 m）の最大、
  前の谷は頂から前へ 0.75 Lc まで、後ろの谷は後ろへ 0.75 Lc までの最小。険しさ＝η_c ÷（頂から、前で静かな水面を切る点までの水平の距離）。
- 断面の水面の線：断面の場の 0 の等高線（skimage.measure.find_contours）のうち、左右の端をつなぐ線で最も高いもの。
  最も高い点から前へ、線を格子 1 個の長さで取り直してたどる。
- 巻き始め：たどった線が静かな水面の高さに下りるまでの間に、隣り合う 2 点の弦が前へ進まない（dx ≤ 0、傾き 90° 以上）最初のコマ。
  場所はその弦の真ん中の x。
- 唇の先：たどった線で x が初めて極大になり、その後 1 格子以上戻った点。届く距離＝先の x − 先から後の線の最も後ろの x、
  厚み＝その半分の x での上の線と下の線の高さの差。
- 空気：閉じた 0 の等高線で中が空気（中の格子点の場が正。格子点がない小さな線は線の向きで決める）のもの。面積は多角形の面積。
- 着水：巻き始めのコマより後で、唇の先が静かな水面以下になるか、格子 1 個以上の空気ができた最初のコマ。
  場所は先の x か、空気の線の最も前の x。
"""
import os, json, math, sys
import numpy as np
from skimage import measure, draw
from ck_common import cfg, load_hf, load_sec, still_level, PLAN, FPS

OUTDIR = os.path.dirname(os.path.abspath(__file__))
P = json.load(open(PLAN, encoding="utf-8"))
Tc = P["full"]["Tc"]; Lc = P["full"]["Lc"]
TOB = P["lab"]["tob_DK"] * math.sqrt(P["full"]["lam"])   # 19.04 s × √70（plan_numbers.json の full.tob_DK と同じになるはず）
XOB = P["lab"]["xob_DK"] * P["full"]["lam"]             # 8.35 m × 70
BAND_D2 = P["full"]["breaking_band_RM_x"]


def orient_rule_test():
    """skimage の線の向き：空気（高い値）を囲む閉じた線の符号付き面積の符号を、作った場で確かめる。"""
    yy, xx = np.mgrid[0:60, 0:80].astype(float)
    S = -np.ones_like(xx) * 3.0            # 水（負）
    r = np.hypot(xx - 40, (yy - 30) * 1.0)
    S = np.where(r < 10, 10 - r, -np.minimum(r - 10, 3))   # 真ん中に空気（正）の泡
    cs = measure.find_contours(S, 0.0)
    c = max(cs, key=len)
    x = c[:, 1]; y = c[:, 0]
    a = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
    return float(np.sign(a))


AIR_SIGN = None


def resample(x, y, step):
    d = np.hypot(np.diff(x), np.diff(y))
    s = np.concatenate([[0], np.cumsum(d)])
    if s[-1] < step:
        return x[:1], y[:1], s[:1]
    sk = np.arange(0, s[-1] + 1e-9, step)
    return np.interp(sk, s, x), np.interp(sk, s, y), sk


def analyze_frame(sdf, meta, xp, off, vox, xc_hf, step_cells=1.0):
    S = sdf.astype(np.float32)
    cs = measure.find_contours(S, 0.0)
    x0, dx, y0, dy = meta["x0"], meta["dx"], meta["y0"], meta["dy"]
    width = (meta["nx"] - 1) * dx
    main = None; best = -1e9
    cav = []
    for c in cs:
        x = x0 + c[:, 1] * dx - xp
        y = y0 + c[:, 0] * dy - off
        closed = np.allclose(c[0], c[-1])
        if not closed:
            if x.max() - x.min() > 0.9 * width and y.max() > best:
                best = y.max(); main = (x, y)
            continue
        a = 0.5 * np.sum(x[:-1] * y[1:] - x[1:] * y[:-1])
        area = abs(a)
        if area < vox * vox - 1e-9:
            continue
        rr, cc = draw.polygon(c[:, 0], c[:, 1], S.shape)
        if len(rr) > 0:
            is_air = float(np.mean(S[rr, cc])) > 0
        else:
            is_air = (np.sign(a) == AIR_SIGN)
        if is_air:
            cav.append(dict(area=float(area), xmin=float(x.min()), xmax=float(x.max()), ymin=float(y.min()), ymax=float(y.max()),
                            npts_in=int(len(rr))))
    out = dict(cav=cav)
    if main is None:
        return out
    x, y = main
    if x[0] > x[-1]:
        x = x[::-1]; y = y[::-1]
    it = int(np.argmax(y))
    out["top_x"] = float(x[it]); out["top_y"] = float(y[it])
    # 前へたどる（頂から前へ 0.6 Lc まで、または静かな水面より 1 m 下まで）
    xs, ys, sk = resample(x[it:], y[it:], step_cells * vox)
    stop = len(xs)
    for k in range(len(xs)):
        if ys[k] < -1.0 or xs[k] > x[it] + 0.6 * Lc:
            stop = k + 1; break
    xs = xs[:stop]; ys = ys[:stop]
    # 静かな水面の高さに下りるまで（前の面）
    k0 = np.where(ys <= 0.0)[0]
    kz = int(k0[0]) if len(k0) else len(ys) - 1
    ddx = np.diff(xs[:kz + 1]); ddy = np.diff(ys[:kz + 1])
    over = np.where(ddx <= 0)[0]
    out["overhang"] = bool(len(over))
    if len(over):
        j = int(over[0])
        out["vertical_x"] = float(0.5 * (xs[j] + xs[j + 1])); out["vertical_y"] = float(0.5 * (ys[j] + ys[j + 1]))
    ang = np.degrees(np.arctan2(-ddy, ddx))
    m60 = (ddy < 0) & (ang > 60)
    out["h60"] = float(np.sum(-ddy[m60]))
    out["thmax"] = float(np.max(np.where(ang < -90, ang + 360, ang))) if len(ang) else None
    # 唇の先
    xm = -1e9; im = None; tip = None
    for k in range(len(xs)):
        if xs[k] > xm:
            xm = xs[k]; im = k
        elif xs[k] < xm - vox * 1.0 + 1e-9:
            tip = im; break
    if tip is not None:
        xt, yt = xs[tip], ys[tip]
        rest = slice(tip, len(xs))
        kw = tip + int(np.argmin(xs[rest]))
        xw = xs[kw]
        reach = xt - xw
        xh = 0.5 * (xt + xw)
        # 上の線：頂→先で x_h を切る最後の所。下の線：先→壁で x_h を切る最初の所
        yu = None
        for k in range(tip - 1, -1, -1):
            if (xs[k] - xh) * (xs[k + 1] - xh) <= 0 and xs[k] != xs[k + 1]:
                yu = ys[k] + (xh - xs[k]) / (xs[k + 1] - xs[k]) * (ys[k + 1] - ys[k]); break
        yl = None
        for k in range(tip, kw):
            if (xs[k] - xh) * (xs[k + 1] - xh) <= 0 and xs[k] != xs[k + 1]:
                yl = ys[k] + (xh - xs[k]) / (xs[k + 1] - xs[k]) * (ys[k + 1] - ys[k]); break
        out["tip"] = dict(x=float(xt), y=float(yt), xw=float(xw), reach=float(reach),
                          thick=float(yu - yl) if (yu is not None and yl is not None) else None)
    return out


def hf_quant(e, xr, off, x_lo, x_hi):
    """一番上の水面の高さ（真ん中の節）から頂・谷・険しさ・頂の断面積。"""
    e = e - off
    m = (xr >= x_lo) & (xr <= x_hi) & np.isfinite(e)
    idx = np.where(m)[0]
    ic = idx[np.nanargmax(e[idx])]
    xc = xr[ic]; ec = float(e[ic])
    fm = (xr > xc) & (xr <= xc + 0.75 * Lc) & np.isfinite(e)
    bm = (xr < xc) & (xr >= xc - 0.75 * Lc) & np.isfinite(e)
    jf = np.where(fm)[0][np.nanargmin(e[fm])]
    jb = np.where(bm)[0][np.nanargmin(e[bm])]
    # 前で静かな水面を切る点
    d0 = None; xf0 = None
    for j in range(ic + 1, len(e)):
        if np.isfinite(e[j]) and e[j] <= 0:
            xf0 = xr[j - 1] + (xr[j] - xr[j - 1]) * (e[j - 1] / (e[j - 1] - e[j])); d0 = xf0 - xc; break
    xb0 = None
    for j in range(ic - 1, 0, -1):
        if np.isfinite(e[j]) and e[j] <= 0:
            xb0 = xr[j] + (xr[j + 1] - xr[j]) * (e[j] / (e[j] - e[j + 1])); break
    area = None
    if xb0 is not None and xf0 is not None:
        mm = (xr >= xb0) & (xr <= xf0)
        area = float(np.nansum(np.clip(e[mm], 0, None)) * (xr[1] - xr[0]))
    return dict(xc=float(xc), eta_c=ec, x_tf=float(xr[jf]), trough_f=float(e[jf]), H=float(ec - e[jf]),
                x_tr=float(xr[jb]), trough_r=float(e[jb]), H_rear=float(ec - e[jb]),
                d_zero=None if d0 is None else float(d0), steep=None if d0 is None else float(ec / d0),
                x_back0=None if xb0 is None else float(xb0), x_front0=None if xf0 is None else float(xf0), crest_area=area)


def run_one(run, step_cells=1.0, rows_out=True):
    c = cfg(run); xp = c["parms"]["x_p"]; vox = c["parms"]["dp"] * 2.0
    hf = load_hf(run)
    off = still_level(hf, xp, "mid")
    sec = load_sec(run)
    meta = sec["meta"]
    xr = hf["x"] - xp
    x_lo = meta["x0"] - xp; x_hi = meta["x0"] + (meta["nx"] - 1) * meta["dx"] - xp
    fidx = {int(f): i for i, f in enumerate(hf["frames"])}
    rows = []
    for f in sec["frames"]:
        f = int(f)
        q = hf_quant(hf["mid"][fidx[f]], xr, off, x_lo, x_hi)
        g = analyze_frame(sec["sdf"][f], meta, xp, off, vox, q["xc"], step_cells)
        q.update(g); q["frame"] = f; q["t"] = (f - 1) / FPS
        q["ss_n"] = int(hf["ss_n"][fidx[f]])
        rows.append(q)
    info = dict(run=run, vox=vox, x_p=xp, off=off, off_in3=still_level(hf, xp, "in3"),
                hf_frames=[int(hf["frames"][0]), int(hf["frames"][-1]), int(len(hf["frames"]))], hf_overlap=[hf["overlap_same"], hf["overlap_diff"]],
                sec_frames=[int(sec["frames"][0]), int(sec["frames"][-1]), int(len(sec["frames"]))], sec_overlap=[sec["overlap_same"], sec["overlap_diff"]],
                sec_x=[x_lo, x_hi])
    # 小刻み・1 コマの秒・粒子
    ssn = hf["ss_n"]; info["substeps_hist"] = {str(k): int(np.sum(ssn == k)) for k in sorted(set(ssn.tolist())) if k >= 0}
    cap = np.where(ssn == 8)[0]
    info["substeps_cap8_t"] = [float(hf["t"][i]) for i in cap]
    w = hf["wall"]; t = hf["t"]
    info["wall_median"] = float(np.median(w[1:])); info["wall_sum_h"] = float(np.sum(w) / 3600)
    for a, b in ((0, 138.2), (138.2, 154), (154, 160), (160, 188)):
        mm = (t >= a) & (t < b)
        info["wall_%g_%g" % (a, b)] = [float(np.median(w[mm])), float(np.sum(w[mm]) / 3600)]
    n = hf["npts"]
    info["npts_f1"] = int(n[0]); info["npts_f48"] = int(n[hf["frames"] == 48][0]) if np.any(hf["frames"] == 48) else None
    info["npts_max_recorded"] = int(n.max())
    info["lvl_drop_max_per_launch"] = None
    # 1 回の起動の中の水面の平均の下がり
    dmax = 0.0
    for L in sorted(set(hf["launch"].tolist())):
        mm = hf["launch"] == L
        lv = hf["lvl"][mm]
        if len(lv) > 1:
            dmax = max(dmax, float(lv[0] - lv.min()))
    info["lvl_drop_max_in_launch"] = dmax
    return info, rows


def first(rows, cond, start=0):
    for i in range(start, len(rows)):
        if cond(rows[i]):
            return i
    return None


def events(info, rows, t_from=138.2):
    vox = info["vox"]
    i_on = first(rows, lambda r: r.get("overhang", False))
    on = rows[i_on]
    ev = dict(onset=dict(frame=on["frame"], t=on["t"], x_vertical=on["vertical_x"], y_vertical=on["vertical_y"], xc=on["xc"],
                         eta_c=on["eta_c"], H=on["H"], trough_f=on["trough_f"], x_tf_from_crest=on["x_tf"] - on["xc"],
                         H_rear=on["H_rear"], trough_r=on["trough_r"], x_tr_from_crest=on["xc"] - on["x_tr"],
                         d_zero=on["d_zero"], steep=on["steep"], h60=on["h60"], crest_area=on["crest_area"]))
    # 巻き始めより前に空気があったか（記録の決まりにない場所の空気の確かめ）
    pre = [(r["t"], cv["area"], cv["xmin"]) for r in rows[:i_on] for cv in r["cav"]]
    ev["cavities_before_onset"] = pre[:10]
    ev["n_cav_frames_before_onset"] = len(set(p[0] for p in pre))

    def touch_cond(r):
        if r.get("tip") and r["tip"]["y"] <= 0:
            return True
        return any(True for cv in r["cav"])
    i_td = first(rows, touch_cond, i_on + 1)
    td = rows[i_td]
    by = "tip" if (td.get("tip") and td["tip"]["y"] <= 0) else "cavity"
    if by == "cavity":
        cv = max(td["cav"], key=lambda c: c["xmax"])
        xtd = cv["xmax"]; cvinfo = cv
    else:
        xtd = td["tip"]["x"]; cvinfo = None
    ev["touchdown"] = dict(frame=td["frame"], t=td["t"], x=xtd, by=by, cavity=cvinfo, all_cav=td["cav"],
                           eta_c=td["eta_c"], H=td["H"], H_rear=td["H_rear"], h60=td["h60"], tip=td.get("tip"))
    ev["jet_time"] = td["t"] - on["t"]; ev["jet_dist"] = xtd - on["vertical_x"]
    # 巻き始めにそろえた時刻
    ph = []
    tt = np.array([r["t"] for r in rows])
    for o in (-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3):
        i = int(np.argmin(np.abs(tt - (on["t"] + o * Tc))))
        r = rows[i]
        big = max(r["cav"], key=lambda c: c["area"]) if r["cav"] else None
        ph.append(dict(off_Tc=o, t=r["t"], eta_c=r["eta_c"], H=r["H"], H_rear=r["H_rear"], trough_f=r["trough_f"], trough_r=r["trough_r"],
                       h60=r["h60"], tip=r.get("tip"), cav_max=big, crest_area=r["crest_area"], steep=r["steep"], xc=r["xc"]))
    ev["phases"] = ph
    # 唇と空気の時間の窓
    def lipmax(i0, i1):
        best = None
        for r in rows[i0:i1]:
            tp = r.get("tip")
            if tp and (best is None or tp["reach"] > best["reach"]):
                best = dict(tp); best["t"] = r["t"]
        return best
    t_on = on["t"]; t_td = td["t"]
    i_m02 = int(np.argmin(np.abs(tt - (t_on - 0.2))))
    i_td1 = int(np.searchsorted(tt, t_td + 1.0 + 1e-9))
    i_36 = int(np.searchsorted(tt, t_on + 3.6 + 1e-9))
    ev["lip_win1_onset-0.2_to_touch"] = lipmax(i_m02, i_td)
    ev["lip_win1_incl_touch"] = lipmax(i_m02, i_td + 1)
    ev["lip_win2_touch_to_+1s"] = lipmax(i_td, i_td1)
    ev["lip_win3_after_to_onset+3.6"] = lipmax(i_td1, i_36)
    # 前の面の低い所（下の端が静かな水面から 2 m 以下）に 4 m² 以上の空気ができた最初のコマ
    i_low = first(rows, lambda r: any(cv["area"] >= 4.0 and cv["ymin"] <= 2.0 for cv in r["cav"]), i_on)
    if i_low is not None:
        rl = rows[i_low]
        cl = max([cv for cv in rl["cav"] if cv["area"] >= 4.0 and cv["ymin"] <= 2.0], key=lambda c: c["area"])
        ev["low_air_first"] = dict(t=rl["t"], frame=rl["frame"], cav=cl)
        ev["lip_before_low_air"] = lipmax(i_m02, i_low)
    i4 = first(rows, lambda r: any(cv["area"] >= 4.0 for cv in r["cav"]), i_on)
    if i4 is not None:
        ev["air4_first"] = dict(t=rows[i4]["t"], cav=max(rows[i4]["cav"], key=lambda c: c["area"]))
    # 最大の空気（巻き始め + 3.6 s まで）と、その後の推移
    best = None
    for r in rows[i_on:i_36]:
        for cv in r["cav"]:
            if best is None or cv["area"] > best["area"]:
                best = dict(cv); best["t"] = r["t"]
    ev["air_max_to_onset+3.6"] = best
    # 噴流の先の最も低い所（巻き始めから最後まで、唇がある時）
    low = None
    for r in rows[i_on:]:
        tp = r.get("tip")
        if tp and (low is None or tp["y"] < low["y"]):
            low = dict(tp); low["t"] = r["t"]
    ev["tip_lowest_after_onset"] = low
    low2 = None
    for r in rows[i_on:i_36]:
        tp = r.get("tip")
        if tp and (low2 is None or tp["y"] < low2["y"]):
            low2 = dict(tp); low2["t"] = r["t"]
    ev["tip_lowest_to_onset+3.6"] = low2
    # 2 つ目の噴流の空気の線が開いたコマ（low_air_first の後、+3.6 s までで、下の端 2 m 以下・4 m² 以上の空気がないコマ）
    if i_low is not None:
        opened = []
        for r in rows[i_low:i_36]:
            if not any(cv["area"] >= 4.0 and cv["ymin"] <= 2.0 for cv in r["cav"]):
                opened.append(round(r["t"], 3))
        ev["low_air_open_frames"] = opened
    # 群の次の頂（170 s から）の巻き始め
    i2 = first(rows, lambda r: r.get("overhang", False) and r["t"] > 170)
    if i2 is not None:
        r2 = rows[i2]
        lm = None
        for r in rows[i2:]:
            tp = r.get("tip")
            if tp and r["t"] < r2["t"] + 3 and (lm is None or tp["reach"] > lm["reach"]):
                lm = dict(tp); lm["t"] = r["t"]
        ev["second_crest"] = dict(t=r2["t"], x_vertical=r2["vertical_x"], xc=r2["xc"], steep=r2["steep"], lip_max=lm)
    # 最も険しい（巻き始めの前後）と、巻き始めのコマの前後の値
    ev["around_onset"] = [dict(t=rows[i]["t"], overhang=rows[i].get("overhang"), vertical_x=rows[i].get("vertical_x"), eta_c=rows[i]["eta_c"],
                               H=rows[i]["H"], steep=rows[i]["steep"], d_zero=rows[i]["d_zero"], x_tf=rows[i]["x_tf"] - rows[i]["xc"], trough_f=rows[i]["trough_f"])
                          for i in range(max(0, i_on - 3), min(len(rows), i_on + 4))]
    # 小刻みが 8 のコマ
    ev["ss8_t"] = [round(r["t"], 3) for r in rows if r["ss_n"] == 8]
    return ev


def comp(fine, coarse):
    """(c) の比べ。比の基準は細かい方（計画の読み方の続き 17）。"""
    a = coarse; b = fine
    rel = lambda va, vb: (va - vb) / vb
    C1 = dict(dt=a["onset"]["t"] - b["onset"]["t"], dx=a["onset"]["x_vertical"] - b["onset"]["x_vertical"])
    C1["dt_Tc"] = C1["dt"] / Tc; C1["dx_Lc"] = C1["dx"] / Lc
    C1["ok"] = abs(C1["dt_Tc"]) <= 0.1 and abs(C1["dx_Lc"]) <= 0.1
    C2 = dict(H=rel(a["onset"]["H"], b["onset"]["H"]), eta_c=rel(a["onset"]["eta_c"], b["onset"]["eta_c"]))
    C2["ok"] = abs(C2["H"]) <= 0.05 and abs(C2["eta_c"]) <= 0.05
    C3 = dict(steep=rel(a["onset"]["steep"], b["onset"]["steep"]))
    C3["ok"] = abs(C3["steep"]) <= 0.10
    C4 = dict(jet_time=rel(a["jet_time"], b["jet_time"]), jet_dist=rel(a["jet_dist"], b["jet_dist"]))
    C4["ok"] = abs(C4["jet_time"]) <= 0.10 and abs(C4["jet_dist"]) <= 0.10
    return dict(C1=C1, C2=C2, C3=C3, C4=C4, all_ok=C1["ok"] and C2["ok"] and C3["ok"] and C4["ok"])


def sensitivity(info_f, rows_f, info_c, rows_c, ev_f, ev_c):
    """C3 が幅の端に近いので、巻き始めのコマを ±1 コマずらした時と、中の 3 節の平均で読んだ時の C3。"""
    out = []
    def idx(rows, f):
        return [i for i, r in enumerate(rows) if r["frame"] == f][0]
    i_f = idx(rows_f, ev_f["onset"]["frame"]); i_c = idx(rows_c, ev_c["onset"]["frame"])
    for df in (-1, 0, 1):
        for dc in (-1, 0, 1):
            sf = rows_f[i_f + df]["steep"]; sc = rows_c[i_c + dc]["steep"]
            Hf = rows_f[i_f + df]["H"]; Hc = rows_c[i_c + dc]["H"]
            out.append(dict(d_frame_R4=df, d_frame_R3=dc, steep_R4=sf, steep_R3=sc, C3=(sc - sf) / sf, C2H=(Hc - Hf) / Hf))
    return out


def main():
    global AIR_SIGN
    AIR_SIGN = orient_rule_test()
    res = dict(note="自前の確かめ（check_R4_geom.py）。g_analyze.py・g_shape.py・x_r4_visual.py は使っていない。", air_sign=AIR_SIGN,
               Tc=Tc, Lc=Lc, tob_DK=TOB, xob_DK=XOB)
    allrows = {}
    evs = {}
    for run in ("R4d", "R3", "R2"):
        info, rows = run_one(run)
        ev = events(info, rows)
        res[run] = dict(info=info, events=ev)
        allrows[run] = rows; evs[run] = ev
        print(run, "onset", ev["onset"]["t"], round(ev["onset"]["x_vertical"], 2), "touch", ev["touchdown"]["t"], round(ev["touchdown"]["x"], 2), ev["touchdown"]["by"])
        sys.stdout.flush()
    res["C_R3_vs_R4d"] = comp(evs["R4d"], evs["R3"])
    res["C_R2_vs_R4d"] = comp(evs["R4d"], evs["R2"])
    res["C_R2_vs_R3"] = comp(evs["R3"], evs["R2"])
    res["C3_sensitivity_R3_R4d"] = sensitivity(res["R4d"]["info"], allrows["R4d"], res["R3"]["info"], allrows["R3"], evs["R4d"], evs["R3"])
    td = evs["R4d"]["touchdown"]
    res["D3_R4d"] = dict(t=td["t"], x=td["x"], dt=td["t"] - TOB, dx=td["x"] - XOB, dt_Tc=(td["t"] - TOB) / Tc, dx_Lc=(td["x"] - XOB) / Lc,
                         ok=abs(td["t"] - TOB) <= 0.25 * Tc and abs(td["x"] - XOB) <= 0.25 * Lc)
    lo = evs["R4d"].get("low_air_first")
    if lo:
        res["D3_R4d_ref_low_air"] = dict(t=lo["t"], x=lo["cav"]["xmax"], dt_Tc=(lo["t"] - TOB) / Tc, dx_Lc=(lo["cav"]["xmax"] - XOB) / Lc)
    on = evs["R4d"]["onset"]
    res["D2_R4d"] = dict(x=on["x_vertical"], xc=on["xc"], band=BAND_D2, ok=BAND_D2[0] <= on["x_vertical"] <= BAND_D2[1],
                        tob_plan=P["full"]["tob_DK"], xob_plan=P["full"]["xob_DK"])
    # 小刻み 1 の 2 段の時間の刻みでの比べ（R3 と R4 で巻き始めの前の水の体）
    json.dump(res, open(os.path.join(OUTDIR, "check_R4_geom.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    slim = {k: [{kk: vv for kk, vv in r.items()} for r in v] for k, v in allrows.items()}
    json.dump(slim, open(os.path.join(OUTDIR, "check_R4_rows.json"), "w", encoding="utf-8"), ensure_ascii=False, default=float)
    print(json.dumps(res["C_R3_vs_R4d"], indent=1, default=float))


if __name__ == "__main__":
    main()
