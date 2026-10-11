# -*- coding: utf-8 -*-
"""R4b 確かめ：断面の水面の場と一番上の水面の高さから、巻き始め・着水・H・η_c・険しさ・谷・唇・空気・C1〜C4・D3 を自前で出す。
py -3.10 b_geom.py → b_geom.json, b_rows_<run>.json
読み方は record_ja.md の「計画の読み方」7〜9・12〜14・16 の文から自分で書いた（g_analyze・g_shape・check/R4 の道具は使っていない）。
場の符号：水の中が負、空気が正（列 0 の海底の下は正）。静かな水面の 25 m 下より上だけを見る。
"""
import sys, math
import numpy as np
from skimage import measure
import b_common as B

P = B.plan(); C = B.components(P)
Lc, Tc = C["Lc"], C["Tc"]
SEC_LO, SEC_HI = 321.0, 863.0   # 読み方 9 の断面の範囲（造波板から）


def contours(sdf, meta, off, xp):
    ys = meta["y0"] + meta["dy"] * np.arange(meta["ny"]) - off
    j0 = int(np.searchsorted(ys, -25.0))
    S = sdf[j0:]
    out = []
    for c in measure.find_contours(S, 0.0):
        X = meta["x0"] + c[:, 1] * meta["dx"] - xp
        Y = ys[j0] + c[:, 0] * meta["dy"]
        out.append(np.stack([X, Y], 1))
    return out, S, ys[j0:], j0


def resample(p, ds):
    s = np.concatenate([[0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
    if s[-1] < 2 * ds:
        return p
    q = np.arange(0, s[-1] + 1e-9, ds)
    return np.stack([np.interp(q, s, p[:, 0]), np.interp(q, s, p[:, 1])], 1)


def area(l):
    x, y = l[:, 0], l[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def frame_geo(sdf, meta, off, xp, vox, xmin=None, chord_cells=1.0):
    lines, S, ys, j0 = contours(sdf, meta, off, xp)
    if not lines:
        return None
    ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
    main = lines[int(np.argmax(ext))]
    cand = main if xmin is None else main[main[:, 0] >= xmin]
    if len(cand) == 0:
        return None
    ic = int(np.argmax(np.where(main[:, 0] >= (xmin if xmin is not None else -1e9), main[:, 1], -1e9)))
    xc, yc = main[ic]
    # 前（+x）へ進む向きを選ぶ
    fwd_a = main[ic:]; fwd_b = main[:ic + 1][::-1]
    xa = fwd_a[min(6, len(fwd_a) - 1), 0] if len(fwd_a) > 1 else -1e9
    xb_ = fwd_b[min(6, len(fwd_b) - 1), 0] if len(fwd_b) > 1 else -1e9
    fwd = fwd_a if xa >= xb_ else fwd_b
    # 静かな水面以下か 1 Lc 先まで
    end = len(fwd)
    for j in range(1, len(fwd)):
        if fwd[j, 1] <= 0.0 or abs(fwd[j, 0] - xc) > Lc:
            end = j + 1
            break
    face = resample(fwd[:end], 0.5 * vox)
    n = max(1, int(round(chord_cells * 2)))   # 弦の長さ（半格子の刻みの数）
    res = dict(xc=float(xc), yc=float(yc), face=face, lines=lines, main=main)
    if len(face) > n:
        d = face[n:] - face[:-n]
        th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
        res["th"] = th
        ok = np.where(th >= 90.0)[0]
        res["thmax"] = float(th.max())
        res["vert_x"] = float(0.5 * (face[ok[0], 0] + face[ok[0] + n, 0])) if len(ok) else None
        res["vert_x_start"] = float(face[ok[0], 0]) if len(ok) else None
        m60 = (th >= 60.0)
        if m60.sum() >= 1:
            yy = np.concatenate([face[:-n][m60, 1], face[n:][m60, 1]])
            res["h60"] = float(yy.max() - yy.min())
        else:
            res["h60"] = 0.0
    else:
        res["thmax"] = float("nan"); res["vert_x"] = None; res["h60"] = 0.0
    # 唇の先：前の面を頂からたどって x が初めて極大になり、その後 1 格子以上戻る点
    xx = face[:, 0]
    tip = None; rear = None; reach = None; thick = None
    for i in range(1, len(xx) - 1):
        if xx[i] >= xx[i - 1] and xx[i] >= xx[i + 1]:
            after = xx[i:]
            # その後 1 格子以上戻るか（再び前へ出る前に）
            back = False
            run_max = xx[i]
            for v in after[1:]:
                if v > run_max + 1e-9:
                    break
                if xx[i] - v >= vox:
                    back = True
                    break
            if back:
                tip = i
                break
    if tip is not None:
        # 下の面：先から戻って下る線の、再び前へ 1 格子出る前までの最も後ろの x
        seg = face[tip:]
        jmin = 0; rmin = seg[0, 0]
        for j in range(1, len(seg)):
            if seg[j, 0] < rmin:
                rmin = seg[j, 0]; jmin = j
            elif seg[j, 0] > rmin + vox:
                break
        rear = float(rmin)
        reach = float(face[tip, 0] - rmin)
        xm = 0.5 * (face[tip, 0] + rmin)
        up = face[:tip + 1]; lo = seg[:jmin + 1]

        def y_at(pth, x):
            ys_ = []
            for k in range(len(pth) - 1):
                x0, x1 = pth[k, 0], pth[k + 1, 0]
                if (x0 - x) * (x1 - x) <= 0 and x0 != x1:
                    w = (x - x0) / (x1 - x0); ys_.append(pth[k, 1] + w * (pth[k + 1, 1] - pth[k, 1]))
            return ys_
        yu = y_at(up, xm); yl = y_at(lo, xm)
        if yu and yl:
            thick = float(yu[-1] - yl[0])
        res["tip"] = [float(face[tip, 0]), float(face[tip, 1])]
    else:
        res["tip"] = None
    res["reach"] = reach; res["thick"] = thick; res["rear"] = rear
    # 閉じた空気
    cav = []
    for l in lines:
        if len(l) > 4 and np.allclose(l[0], l[-1]):
            A = area(l)
            if A < vox * vox:
                continue
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            ix = int(round((cx + xp - meta["x0"]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
            inside_air = (0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0)
            if not inside_air:
                continue
            if not ((xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc):
                continue
            cav.append(dict(area=float(A), x0=float(l[:, 0].min()), x1=float(l[:, 0].max()), y0=float(l[:, 1].min()), y1=float(l[:, 1].max())))
    res["cav"] = cav
    return res


def top(etop, x, xmin=SEC_LO, xmax=SEC_HI):
    m = (x >= xmin) & (x <= xmax)
    idx = np.where(m)[0]
    ic = idx[int(np.nanargmax(etop[m]))]
    ec = float(etop[ic]); xc = float(x[ic])
    fa = (x > xc) & (x <= xc + 0.75 * Lc)
    jf = np.where(fa)[0][int(np.nanargmin(etop[fa]))]
    ba = (x < xc) & (x >= xc - 0.75 * Lc)
    jb = np.where(ba)[0][int(np.nanargmin(etop[ba]))]
    jz = None
    for j in range(ic, len(x)):
        if etop[j] <= 0:
            jz = j; break
    dz = float(x[jz - 1] + (x[jz] - x[jz - 1]) * etop[jz - 1] / (etop[jz - 1] - etop[jz]) - xc) if jz else float("nan")
    jz0 = None
    for j in range(ic, -1, -1):
        if etop[j] <= 0:
            jz0 = j; break
    # 頂の断面積（前後で静かな水面を切る 2 点の間、静かな水面より上）
    area_ = float("nan")
    if jz and jz0 is not None:
        seg = np.clip(etop[jz0:jz + 1], 0, None)
        area_ = float(np.trapezoid(seg, x[jz0:jz + 1]))
    # 前の谷の候補（局所の極小、0.75 Lc まで）
    e_f = etop[fa]; x_f = x[fa]
    mins = []
    for k in range(1, len(e_f) - 1):
        if e_f[k] <= e_f[k - 1] and e_f[k] < e_f[k + 1]:
            mins.append((float(x_f[k] - xc), float(e_f[k])))
    return dict(eta_c=ec, xc=xc, H=ec - float(etop[jf]), trough=float(etop[jf]), trough_dist=float(x[jf] - xc),
                Hb=ec - float(etop[jb]), trough_b=float(etop[jb]), trough_b_dist=float(xc - x[jb]), d_zero=dz,
                steep=ec / dz if dz > 0 else float("nan"), crest_area=area_, front_minima=mins)


def analyse(rid, scan_from=3319, chord_cells=1.0, verbose=True):
    cf = B.cfg(rid); xp = cf["parms"]["x_p"]; vox = cf["parms"]["dp"] * 2
    D = B.hf(rid)
    off = B.still(D, xp, "mid")
    x = D["x"] - xp
    fidx = {int(f): i for i, f in enumerate(D["frames"])}
    S = B.SecReader(rid)
    rows = {}
    onset = None; touch = None
    for fr in S.frames:
        if fr < scan_from:
            continue
        g = frame_geo(S.get(fr), S.meta, off, xp, vox, chord_cells=chord_cells)
        if g is None:
            continue
        t = (fr - 1) / B.FPS
        tp = top(D["eta"][fidx[int(fr)], 2, :] - off, x)
        row = dict(frame=int(fr), t=t, xc_sec=g["xc"], yc=g["yc"], thmax=g["thmax"], vert_x=g["vert_x"], h60=g["h60"], tip=g["tip"],
                   reach=g["reach"], thick=g["thick"], cav=g["cav"], **{k: v for k, v in tp.items() if k != "front_minima"},
                   front_minima=tp["front_minima"][:6])
        rows[int(fr)] = row
        if onset is None and np.isfinite(g["thmax"]) and g["thmax"] >= 90.0:
            onset = row
        elif onset is not None and touch is None:
            if (g["tip"] is not None and g["tip"][1] <= 0.0) or g["cav"]:
                touch = row
        if onset is not None and t > onset["t"] + 3.7:
            break
    return dict(rid=rid, off=off, xp=xp, vox=vox, onset=onset, touch=touch, rows=rows, D=D, S=S, x=x, fidx=fidx)


def touch_place(row):
    if row["tip"] is not None and row["tip"][1] <= 0.0:
        return row["tip"][0], "tip"
    c = max(row["cav"], key=lambda c: c["area"])
    return c["x1"], "cavity_front"


def summary(A):
    o, tc = A["onset"], A["touch"]
    xt, by = touch_place(tc)
    s = dict(onset_t=o["t"], onset_frame=o["frame"], onset_x=o["vert_x"], crest_x=o["xc"], crest_x_sec=o["xc_sec"], eta_c=o["eta_c"], H=o["H"], trough=o["trough"],
             trough_dist=o["trough_dist"], Hb=o["Hb"], trough_b=o["trough_b"], trough_b_dist=o["trough_b_dist"], steep=o["steep"],
             d_zero=o["d_zero"], crest_area=o["crest_area"], h60=o["h60"], front_minima=o["front_minima"],
             touch_t=tc["t"], touch_x=xt, touch_by=by, touch_cav=tc["cav"], c4_time=tc["t"] - o["t"], c4_dist=xt - o["vert_x"])
    # 巻き始めにそろえた時刻
    al = {}
    for k in (-3, -2, -1, 0, 1, 2, 3):
        tq = o["t"] + 0.1 * k * Tc
        fr = int(round(tq * B.FPS)) + 1
        r = A["rows"].get(fr)
        if r is None:
            continue
        al[str(k)] = dict(t=r["t"], eta_c=r["eta_c"], H=r["H"], Hb=r["Hb"], area=r["crest_area"], h60=r["h60"], reach=r["reach"], thick=r["thick"],
                          cav=[(round(c["area"], 2), round(c["x0"], 1), round(c["x1"], 1), round(c["y0"], 2)) for c in r["cav"]])
    s["aligned"] = al
    # 窓ごとの唇と空気
    fr_list = sorted(A["rows"])
    first_lip = [(A["rows"][f]["reach"], A["rows"][f]["thick"], A["rows"][f]["t"]) for f in fr_list
                 if o["t"] - 0.2 - 1e-9 <= A["rows"][f]["t"] <= tc["t"] + 1e-9 and A["rows"][f]["reach"] is not None]
    s["lip_max_to_touch"] = max(first_lip) if first_lip else None
    low = None; first4 = None; amax = (0, None, None)
    for f in fr_list:
        r = A["rows"][f]
        if r["t"] < tc["t"] - 1e-9 or r["t"] > o["t"] + 3.6 + 1e-9:
            continue
        for c in r["cav"]:
            if c["area"] > amax[0]:
                amax = (c["area"], r["t"], (c["x0"], c["x1"]))
            if first4 is None and c["area"] >= 4.0:
                first4 = (r["t"], c["area"], c["x0"], c["x1"], c["y0"])
            if low is None and c["area"] >= 4.0 and c["y0"] <= 2.0:
                low = (r["t"], c["area"], c["x0"], c["x1"], c["y0"])
    s["air_max"] = amax; s["air_first4"] = first4; s["air_low4"] = low
    if low is not None:
        lips = [(A["rows"][f]["reach"], A["rows"][f]["thick"], A["rows"][f]["t"]) for f in fr_list
                if tc["t"] - 1e-9 <= A["rows"][f]["t"] < low[0] - 1e-9 and A["rows"][f]["reach"] is not None]
        s["lip_max_before_low_air"] = max(lips) if lips else None
    # 着水の後、噴流の先の最も低い所（先がある時）
    tips = [(A["rows"][f]["tip"][1], A["rows"][f]["t"], A["rows"][f]["tip"][0]) for f in fr_list
            if A["rows"][f]["t"] > tc["t"] and A["rows"][f]["tip"] is not None]
    s["tip_lowest_after_touch_in_scan"] = min(tips) if tips else None
    return s


def main():
    out = {}
    runs = sys.argv[1:] or ["R2", "R3", "R4d"]
    for rid in runs:
        A = analyse(rid)
        s = summary(A)
        out[rid] = s
        print(rid, "onset", round(s["onset_t"], 3), round(s["onset_x"], 2), "crest", round(s["crest_x"], 2), "eta_c", round(s["eta_c"], 3), "H", round(s["H"], 3),
              "trough", round(s["trough"], 3), round(s["trough_dist"], 1), "Hb", round(s["Hb"], 3), round(s["trough_b"], 3), round(s["trough_b_dist"], 1),
              "steep", round(s["steep"], 4), round(s["d_zero"], 2), "area", round(s["crest_area"], 1), "h60", round(s["h60"], 2))
        print("   minima", [(round(a, 1), round(b, 3)) for a, b in s["front_minima"]])
        print("   touch", round(s["touch_t"], 3), round(s["touch_x"], 2), s["touch_by"], [(round(c["area"], 2), round(c["y0"], 2), round(c["y1"], 2)) for c in s["touch_cav"]],
              "C4", round(s["c4_time"], 3), round(s["c4_dist"], 2))
        print("   lip to touch", s["lip_max_to_touch"], "before low air", s.get("lip_max_before_low_air"))
        print("   air max", s["air_max"], "first4", s["air_first4"], "low4", s["air_low4"])
        for k, v in s["aligned"].items():
            print("   ", k, {kk: (round(vv, 3) if isinstance(vv, float) else vv) for kk, vv in v.items()})
        sys.stdout.flush()
        B.dump("b_rows_%s.json" % rid, {str(k): {kk: vv for kk, vv in r.items()} for k, r in A["rows"].items()})
    B.dump("b_geom.json", out)


if __name__ == "__main__":
    main()
