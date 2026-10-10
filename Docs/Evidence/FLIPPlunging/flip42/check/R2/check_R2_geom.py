# -*- coding: utf-8 -*-
"""FLIP42 R2 の段の独立の確かめ（形の量）。確かめ役が自前で書いた。g_analyze.py・g_shape.py は使わず、読み込まない。
読むもの：runs/<計算>/hf_c*.npz（一番上の水面の高さ）、sec_c*_b*.npz（板の真ん中の断面の水面の場、符号付き距離、水の中が負）。
記録の形は g_run.py を読んで確かめた：hf の x は 0 から格子の間隔、z は 5 節（真ん中が 2）。sec の x0・y0 は格子の中心（indexToPos）。
出力：check_R2_geom.json
使い方：py -3.10 check_R2_geom.py
"""
import glob, json, os, re, sys
import numpy as np
from skimage import measure

BASE = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/FLIP42"
RUNS = BASE + "/runs"
OUT = BASE + "/check/R2"
X_P = 135.46329754326246
TC = 9.507500301523587
LC = 135.46329754326246
FPS = 24.0
SEC_REL = (321.27, 863.13)  # 断面の範囲（造波板から）。cfg の sec x0・x1 − x_p
DK_T, DK_X = 19.04 * np.sqrt(70.0), 8.35 * 70.0   # D&K 表 3.1 の t_ob・x_ob を 70 倍（フルードの相似）
XB, TB = 592.2, 20.5 * np.sqrt(70.0)


def launches(run, kind):
    pat = os.path.join(RUNS, run, kind + "_c*.npz")
    fs = glob.glob(pat)
    def key(f):
        m = re.search(r"_c(\d+)(?:_b(\d+))?\.npz$", f)
        return (int(m.group(1)), int(m.group(2) or 0))
    return sorted(fs, key=key), key


def load_hf(run):
    """各コマは最後の起動の値を使う（途中保存から続けた計算）。前の起動と重なったコマの差も返す。"""
    fs, key = launches(run, "hf")
    data = {}
    overlap = []
    x = None
    for f in fs:
        d = np.load(f)
        x = d["x"]
        E = d["eta"]; T = d["t"]; SN = d["ss_n"]; SD = d["ss_dt"]; FR = d["frames"]
        for i, fr in enumerate(FR):
            fr = int(fr)
            row = (E[i, 2].astype(np.float64), float(T[i]), int(SN[i]), float(SD[i]), E[i, 1:4].astype(np.float64))
            if fr in data:
                a, b = data[fr][0], row[0]
                ok = np.isfinite(a) & np.isfinite(b)
                overlap.append((fr, float(np.nanmax(np.abs(a[ok] - b[ok]))) if ok.any() else None))
            data[fr] = row
    frames = np.array(sorted(data))
    return dict(x=x, frames=frames, eta=np.array([data[f][0] for f in frames]), t=np.array([data[f][1] for f in frames]),
                ssn=np.array([data[f][2] for f in frames]), ssdt=np.array([data[f][3] for f in frames]),
                eta3=np.array([data[f][4] for f in frames]), overlap=overlap)


def load_sec(run):
    fs, key = launches(run, "sec")
    data = {}
    meta = None
    overlap = []
    for f in fs:
        d = np.load(f)
        m = json.loads(str(d["meta"]))
        meta = m if meta is None else meta
        assert m["x0"] == meta["x0"] and m["dx"] == meta["dx"] and m["y0"] == meta["y0"], f
        SDF = d["sdf"]; FR = d["frames"]
        for i, fr in enumerate(FR):
            fr = int(fr)
            if fr in data:
                a = data[fr].astype(np.float32); b = SDF[i].astype(np.float32)
                overlap.append((fr, float(np.max(np.abs(a - b)))))
            data[fr] = SDF[i]
    return data, meta, overlap


def still_level(hf):
    x_rel = hf["x"] - X_P
    sel_t = (hf["t"] >= 0.5) & (hf["t"] <= 2.0)
    sel_x = (x_rel >= 0) & (x_rel <= 930)
    v = hf["eta3"][sel_t][:, :, sel_x]
    v_mid = hf["eta"][sel_t][:, sel_x]
    return float(np.nanmedian(v_mid)), float(np.nanmedian(v))


def crest_trough(eta, x_rel, level):
    """計画の読み方 9：断面の範囲の最も高い点を頂、頂から前へ 0.75 Lc までの最も低い点を前の谷。"""
    sel = (x_rel >= SEC_REL[0]) & (x_rel <= SEC_REL[1]) & np.isfinite(eta)
    idx = np.where(sel)[0]
    ic = idx[np.argmax(eta[idx])]
    ahead = np.where(sel & (x_rel > x_rel[ic]) & (x_rel <= x_rel[ic] + 0.75 * LC))[0]
    it = ahead[np.argmin(eta[ahead])]
    # 前で静かな水面を切る点（頂から前へ最初に level 以下）
    j = ic
    xz = None
    while j + 1 < len(eta) and x_rel[j + 1] <= SEC_REL[1]:
        if np.isfinite(eta[j + 1]) and eta[j + 1] <= level:
            e0, e1 = eta[j] - level, eta[j + 1] - level
            xz = x_rel[j] + (x_rel[j + 1] - x_rel[j]) * e0 / (e0 - e1) if e0 != e1 else x_rel[j + 1]
            break
        j += 1
    # 後ろで切る点
    j = ic
    xb = None
    while j - 1 >= 0 and x_rel[j - 1] >= SEC_REL[0]:
        if np.isfinite(eta[j - 1]) and eta[j - 1] <= level:
            e0, e1 = eta[j] - level, eta[j - 1] - level
            xb = x_rel[j] - (x_rel[j] - x_rel[j - 1]) * e0 / (e0 - e1) if e0 != e1 else x_rel[j - 1]
            break
        j -= 1
    is_local_min = bool(it - 1 >= 0 and it + 1 < len(eta) and eta[it] <= eta[it - 1] and eta[it] <= eta[it + 1])
    edge = bool(x_rel[it] > x_rel[ic] + 0.75 * LC - 1.0)
    area = None
    if xz is not None and xb is not None:
        s = (x_rel >= xb) & (x_rel <= xz) & np.isfinite(eta)
        area = float(np.sum(np.clip(eta[s] - level, 0, None)) * (x_rel[1] - x_rel[0]))
    return dict(xc=float(x_rel[ic]), yc=float(eta[ic]), eta_c=float(eta[ic] - level), xt=float(x_rel[it]),
                yt=float(eta[it] - level), H=float(eta[ic] - eta[it]), x_zero=xz, d_zero=(None if xz is None else float(xz - x_rel[ic])),
                steep=(None if xz is None else float((eta[ic] - level) / (xz - x_rel[ic]))), trough_local_min=is_local_min,
                trough_at_window_edge=edge, x_back0=xb, crest_area=area)


def contours(sdf, meta):
    a = sdf.astype(np.float32)
    cs = measure.find_contours(a, 0.0)
    out = []
    for c in cs:
        y = meta["y0"] + c[:, 0] * meta["dy"]
        x = meta["x0"] + c[:, 1] * meta["dx"] - X_P
        closed = bool(np.allclose(c[0], c[-1]))
        out.append((x, y, closed))
    return out


def poly_area(x, y):
    return 0.5 * (np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def inside_value(sdf, meta, x, y):
    """閉じた線の中の格子の点の sdf の中央値（中が空気か水かを決める）。"""
    a = sdf.astype(np.float32)
    ix = (x + X_P - meta["x0"]) / meta["dx"]
    iy = (y - meta["y0"]) / meta["dy"]
    i0, i1 = int(np.floor(ix.min())), int(np.ceil(ix.max()))
    j0, j1 = int(np.floor(iy.min())), int(np.ceil(iy.max()))
    vals = []
    for j in range(max(j0, 0), min(j1, a.shape[0] - 1) + 1):
        for i in range(max(i0, 0), min(i1, a.shape[1] - 1) + 1):
            if point_in_poly(i, j, ix, iy):
                vals.append(a[j, i])
    return (float(np.median(vals)) if vals else None), len(vals)


def point_in_poly(px, py, xs, ys):
    n = len(xs)
    inside = False
    j = n - 1
    for i in range(n):
        if ((ys[i] > py) != (ys[j] > py)) and (px < (xs[j] - xs[i]) * (py - ys[i]) / (ys[j] - ys[i] + 1e-30) + xs[i]):
            inside = not inside
        j = i
    return inside


def pockets(sdf, meta, cs, cell):
    out = []
    for x, y, closed in cs:
        if not closed or len(x) < 4:
            continue
        A = abs(poly_area(x, y))
        if A < 0.2 * cell:
            continue
        v, n = inside_value(sdf, meta, x, y)
        kind = "air" if (v is not None and v > 0) else ("water" if v is not None else "unknown")
        out.append(dict(kind=kind, area=float(A), x_front=float(x.max()), x_back=float(x.min()), y_top=float(y.max()),
                        y_bot=float(y.min()), n_in=n))
    return out


def resample(x, y, step):
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    if s[-1] < step:
        return x, y
    ss = np.arange(0, s[-1], step)
    return np.interp(ss, s, x), np.interp(ss, s, y)


def front_branch(cs, level, cell):
    """最も長い線（主な水面）の最も高い点から前へ、静かな水面の高さに下りるまで。"""
    main = max(cs, key=lambda c: len(c[0]))
    x, y, closed = main
    i = int(np.argmax(y))
    # どちら向きが前か：線に沿って 3 m 進んだ点の x が大きい方
    fw = (x[i:], y[i:])
    bw = (x[i::-1], y[i::-1])
    def xa(b):
        xb, yb = b
        s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xb), np.diff(yb)))])
        k = np.searchsorted(s, 3.0)
        return xb[min(k, len(xb) - 1)]
    br = fw if xa(fw) > xa(bw) else bw
    bx, by = br
    # 静かな水面以下に下りた所で切る
    below = np.where(by <= level)[0]
    end = below[0] + 1 if len(below) else len(bx)
    bx, by = bx[:end], by[:end]
    rx, ry = resample(bx, by, cell)
    return rx, ry, float(x[i]), float(y[i])


def face_measures(rx, ry, level, cell):
    dxs = np.diff(rx); dys = np.diff(ry)
    th = np.degrees(np.arctan2(-dys, dxs))  # 90 = 鉛直に下る、90 より大 = 前へかぶさる
    out = dict(thmax=float(th.max()) if len(th) else None)
    k = np.where(th >= 90.0)[0]
    out["vertical_x"] = float(0.5 * (rx[k[0]] + rx[k[0] + 1])) if len(k) else None
    out["vertical_y"] = float(0.5 * (ry[k[0]] + ry[k[0] + 1])) if len(k) else None
    # 60° より立った所の高さ（鉛直の落ちの和）：(i) 60° 以上全部、(ii) 60〜120°、(iii) 頂から続く一続きの所でなく全体
    m1 = th >= 60.0
    out["h60_all"] = float(np.sum(-dys[m1 & (dys < 0)]))
    m2 = (th >= 60.0) & (th <= 120.0)
    out["h60_60_120"] = float(np.sum(-dys[m2 & (dys < 0)]))
    m3 = (th >= 60.0) & (dxs >= 0)
    out["h60_forward_only"] = float(np.sum(-dys[m3 & (dys < 0)]))
    # 唇：頂から前へ、x が初めて極大になり、その後 1 格子以上戻る点
    tip = None
    for i in range(1, len(rx) - 1):
        if rx[i] >= rx[i - 1] and rx[i] >= rx[i + 1]:
            j = i + 1
            while j < len(rx) and rx[j] <= rx[i]:
                if rx[i] - rx[j] >= cell:
                    tip = i
                    break
                if rx[j] > rx[j - 1] + 1e-9 and rx[i] - rx[j] < cell and j > i + 1 and rx[j] > rx[j-1]:
                    pass
                j += 1
            if tip is not None:
                break
    if tip is not None:
        # 下の面：先から戻って x が最小になる点（その後 x が増え始めるまで）
        j = tip
        jmin = tip
        while j + 1 < len(rx):
            j += 1
            if rx[j] < rx[jmin]:
                jmin = j
            elif rx[j] > rx[jmin] + cell:
                break
        reach = float(rx[tip] - rx[jmin])
        xm = rx[jmin] + 0.5 * reach
        # 上の面（頂から先まで）と下の面（先から jmin まで）で xm の高さ
        up = _y_at(rx[:tip + 1], ry[:tip + 1], xm)
        lo = _y_at(rx[tip:jmin + 1], ry[tip:jmin + 1], xm)
        out["lip"] = dict(x_tip=float(rx[tip]), y_tip=float(ry[tip]), x_wall=float(rx[jmin]), y_wall=float(ry[jmin]), reach=reach,
                          thick_mid=(None if (up is None or lo is None) else float(up - lo)))
    else:
        out["lip"] = None
    # 噴流の先（計画の文の定義）：頂から前へ x が最大になる点。静かな水面より上で、前の面が静かな水面を切る点より前に出ているか
    imax = int(np.argmax(rx))
    out["xmax_pt"] = dict(x=float(rx[imax]), y=float(ry[imax]), is_end=bool(imax == len(rx) - 1))
    return out


def _y_at(xs, ys, xm):
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        if (a - xm) * (b - xm) <= 0 and a != b:
            return ys[i] + (ys[i + 1] - ys[i]) * (xm - a) / (b - a)
    return None


def analyze(run, hf, sec, meta, level, cell, f_from=None, f_to=None):
    x_rel = hf["x"] - X_P
    fidx = {int(f): i for i, f in enumerate(hf["frames"])}
    rows = []
    frames = sorted(sec)
    if f_from:
        frames = [f for f in frames if f >= f_from]
    if f_to:
        frames = [f for f in frames if f <= f_to]
    for f in frames:
        if f not in fidx:
            continue
        i = fidx[f]
        ct = crest_trough(hf["eta"][i], x_rel, level)
        cs = contours(sec[f], meta)
        rx, ry, xc_s, yc_s = front_branch(cs, level, cell)
        fm = face_measures(rx, ry, level, cell)
        pk = pockets(sec[f], meta, cs, cell)
        rows.append(dict(frame=f, t=float(hf["t"][i]), **ct, sec_crest_x=xc_s, sec_crest_y=yc_s - level, **fm,
                         pockets=pk, branch_n=len(rx)))
    return rows


def find_events(rows, level, cell, x_near=None):
    on = None
    for r in rows:
        if r["thmax"] is not None and r["thmax"] >= 90.0:
            on = r
            break
    if on is None:
        return dict(onset=None)
    td_air = None
    for r in rows:
        if r["t"] < on["t"]:
            continue
        air = [p for p in r["pockets"] if p["kind"] == "air" and p["area"] >= cell * cell
               and on["xc"] - 0.25 * LC <= p["x_front"] <= on["xc"] + 0.6 * LC and p["y_top"] > level - 12]
        if air:
            td_air = (r, max(air, key=lambda p: p["area"]))
            break
    # 計画の文のままの着水：前へ出た噴流の先（頂から前へ x が最大の点で、線の終わりではない）が静かな水面の高さ以下
    td_swl = None
    for r in rows:
        if r["t"] < on["t"]:
            continue
        lip = r.get("lip")
        if lip and lip["y_tip"] <= level + 1e-9:
            td_swl = r
            break
    return dict(onset=on, td_air=td_air, td_swl=td_swl)


def main():
    res = {}
    lv = {}
    hfs, secs = {}, {}
    for run in ["R3", "R2", "R5p", "R3m", "R1b"]:
        hf = load_hf(run)
        sec, meta, ov = load_sec(run)
        hfs[run], secs[run] = hf, (sec, meta)
        if run in ("R5p", "R3m"):
            level = lv["R3"][0]
            lmid = None
        else:
            level, l3 = still_level(hf)
            lmid = l3
        lv[run] = (level, lmid)
        ovh = [o for o in hf["overlap"] if o[1] is not None]
        res[run] = dict(level=level, level_3nodes=lmid, hf_frames=[int(hf["frames"][0]), int(hf["frames"][-1]), len(hf["frames"])],
                        sec_frames=[min(sec), max(sec), len(sec)], meta=meta,
                        hf_overlap_n=len(ovh), hf_overlap_maxdiff=(max(o[1] for o in ovh) if ovh else None),
                        sec_overlap_n=len(ov), sec_overlap_maxdiff=(max(o[1] for o in ov) if ov else None))
        print(run, "level", level, lmid, res[run]["hf_frames"], res[run]["sec_frames"], "overlap hf", res[run]["hf_overlap_n"],
              res[run]["hf_overlap_maxdiff"], "sec", res[run]["sec_overlap_n"], res[run]["sec_overlap_maxdiff"])
        sys.stdout.flush()
    json.dump(res, open(OUT + "/check_R2_load.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    allrows = {}
    for run in ["R3", "R2", "R5p", "R3m", "R1b"]:
        hf = hfs[run]; sec, meta = secs[run]
        cell = meta["dx"]
        rows = analyze(run, hf, sec, meta, lv[run][0], cell)
        allrows[run] = rows
        ev = find_events(rows, lv[run][0], cell)
        on = ev["onset"]
        out = dict(level=lv[run][0], cell=cell)
        if on:
            out["onset"] = {k: on[k] for k in ("frame", "t", "xc", "eta_c", "H", "xt", "yt", "steep", "d_zero", "vertical_x", "vertical_y",
                                               "thmax", "h60_all", "h60_60_120", "h60_forward_only", "trough_local_min",
                                               "trough_at_window_edge", "crest_area", "sec_crest_x", "sec_crest_y")}
            if ev["td_air"]:
                r, pk = ev["td_air"]
                out["touch_air"] = dict(frame=r["frame"], t=r["t"], x=pk["x_front"], area=pk["area"], y_top=pk["y_top"] - lv[run][0],
                                        y_bot=pk["y_bot"] - lv[run][0], x_back=pk["x_back"], eta_c=r["eta_c"], H=r["H"],
                                        jet_time=r["t"] - on["t"], jet_dist=pk["x_front"] - on["vertical_x"])
            if ev["td_swl"]:
                r = ev["td_swl"]
                out["touch_swl"] = dict(frame=r["frame"], t=r["t"], lip=r["lip"], jet_time=r["t"] - on["t"],
                                        jet_dist=r["lip"]["x_tip"] - on["vertical_x"])
            # 巻き始めにそろえた時刻
            ph = []
            for off in (-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3):
                tt = on["t"] + off * TC
                rr = min(rows, key=lambda r: abs(r["t"] - tt))
                ph.append(dict(off_Tc=off, t=rr["t"], eta_c=rr["eta_c"], H=rr["H"], xc=rr["xc"], steep=rr["steep"], h60_all=rr["h60_all"],
                               h60_60_120=rr["h60_60_120"], h60_forward_only=rr["h60_forward_only"], lip=rr["lip"], thmax=rr["thmax"],
                               air=[p for p in rr["pockets"] if p["kind"] == "air" and p["area"] >= cell * cell],
                               crest_area=rr["crest_area"]))
            out["phases"] = ph
        res[run]["events"] = out
        print(run, json.dumps(out.get("onset"), ensure_ascii=False))
        print("  air", json.dumps(out.get("touch_air"), ensure_ascii=False))
        print("  swl", json.dumps(out.get("touch_swl"), ensure_ascii=False))
        sys.stdout.flush()
    # 比べ（基準は細かい方・刻みの小さい方）
    def C(fine, coarse):
        a = res[fine]["events"]; b = res[coarse]["events"]
        oa, ob = a["onset"], b["onset"]
        ta, tb = a["touch_air"], b["touch_air"]
        return dict(fine=fine, coarse=coarse,
                    C1_dt=ob["t"] - oa["t"], C1_dt_Tc=(ob["t"] - oa["t"]) / TC, C1_dx=ob["vertical_x"] - oa["vertical_x"],
                    C1_dx_Lc=(ob["vertical_x"] - oa["vertical_x"]) / LC,
                    C2_H=(ob["H"] - oa["H"]) / oa["H"], C2_eta=(ob["eta_c"] - oa["eta_c"]) / oa["eta_c"],
                    C3=(ob["steep"] - oa["steep"]) / oa["steep"],
                    C4_t=(tb["jet_time"] - ta["jet_time"]) / ta["jet_time"], C4_x=(tb["jet_dist"] - ta["jet_dist"]) / ta["jet_dist"])
    res["compare"] = [C("R5p", "R3"), C("R3", "R2"), C("R3", "R3m"), C("R2", "R1b")]
    for c in res["compare"]:
        print(json.dumps(c))
    on = res["R3"]["events"]["onset"]; ta = res["R3"]["events"]["touch_air"]
    res["D"] = dict(DK_t=DK_T, DK_x=DK_X, xb=XB, tb=TB, D2_range=[XB - 5 / (2 * np.pi / LC), XB],
                    D3_dt=ta["t"] - DK_T, D3_dx=ta["x"] - DK_X, D3_dt_Tc=(ta["t"] - DK_T) / TC, D3_dx_Lc=(ta["x"] - DK_X) / LC,
                    onset_vs_linear_focus_Tc=(TB - on["t"]) / TC, onset_vs_linear_focus_m=XB - on["vertical_x"])
    print(json.dumps(res["D"]))
    # 全部のコマの行（大きいので要る量だけ）
    slim = {}
    for run, rows in allrows.items():
        slim[run] = [dict(frame=r["frame"], t=r["t"], xc=r["xc"], eta_c=r["eta_c"], H=r["H"], xt=r["xt"], steep=r["steep"],
                          thmax=r["thmax"], h60_all=r["h60_all"], lip=r["lip"],
                          air=[p for p in r["pockets"] if p["kind"] == "air"], xmax_pt=r["xmax_pt"]) for r in rows]
    json.dump(slim, open(OUT + "/check_R2_rows.json", "w", encoding="utf-8"), ensure_ascii=False)
    json.dump(res, open(OUT + "/check_R2_geom.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)


if __name__ == "__main__":
    main()
