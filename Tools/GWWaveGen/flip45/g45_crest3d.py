# -*- coding: utf-8 -*-
"""FLIP45：3D だけの頂の量（計画 plan_ja.md §6.1 の ℓ・§6.5 の L-a〜L-e。py -3.10、numpy・scikit-image）。g45_analyze.py が読む。
2026-10-12 進行役が新しく書いた。煙の試し S8 の合成の記録で確かめる（x45_s8.py）。
  frame_crests(...)   断面（縦 × x の水面の場）の全部の頂：頂の位置と高さ、前の面の弦の最大の傾き、唇の先、空気を囲む閉じた線、前の谷・後ろの谷。
                      FLIP44 の g44_analyze.frame_crests（変えていない）を写し、後ろの谷（頂の後ろ 1 λ の最も低い所。H1 のため）を足した。
  crest_width(...)    ℓ（§6.1）：一番上の水面 η_top(横, x) で、頂を含み Ac/2 より高い水のつながった所の、横の最も広い所の幅 × 2（半分を解くため）。
                      横の向きの Ac/2 を切る所は、格子の中心の間を線形に補う。
  long_crest(...)     L-c：η_top が 0.7 η_c より高い水のつながった所の横の幅 × 2。
  overturn_span(...)  L-b：R4（3D の水面の場）の y ごとの x–縦 の断面で、前の面の弦が 90° を越える y の範囲 × 2。
  offaxis_onset(...)  L-e（見直し M7）：R4 のどの y の断面でも前の面の弦が初めて 90° 以上になったコマと、その y・x。
  jet_angle(...)      L-d：唇の先の水の速さの向き（y = 0、水平からの角。下向きが正）。45° より寝ていれば「前へ巻く」、60° より立てば「上へ噴く」。
  plunge_rule(...)    §6.1 の「前へ巻く」（見直し M10）：(a) 唇が前の水面と空気を囲む（閉じた空気の線の面積が格子 1 個以上）か、
                      (b) 唇の先が静かな水面以下に届き、同じコマに覆いかぶさり（同じ x の列で下から水・空気・水）が x に格子 2 個以上続く。
"""
import math
import numpy as np
from skimage import measure
from scipy.signal import find_peaks
from scipy import ndimage

Z_BED = -20.0


def resample(path, ds):
    seg = np.sqrt((np.diff(path, axis=0) ** 2).sum(1))
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < ds:
        return path
    q = np.arange(0, s[-1], ds)
    return np.stack([np.interp(q, s, path[:, 0]), np.interp(q, s, path[:, 1])], 1)


def poly_area(c):
    x, y = c[:, 0], c[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def frame_crests(sdf, meta, off, vox, Lc, min_eta=0.5, prom=0.3, x_lo=None, x_hi=None, z_bed=Z_BED):
    """1 コマの断面の全部の頂（g44_analyze.frame_crests の写し＋後ろの谷）。sdf[縦, x]（水の中で負）。座標は計画の x、高さは静かな水面から。
    z_bed：海底（FLIP45 は −20 m。煙の試し S8 で FLIP42 の R3 を読む時は −42 m）。"""
    S = sdf.astype(np.float32).copy()
    xs = meta["x0"] + meta["dx"] * np.arange(S.shape[1])
    ys = meta["y0"] + meta["dy"] * np.arange(S.shape[0]) - off
    S[ys < (z_bed - off), :] = -1.0
    j0 = int(np.searchsorted(ys, -25.0))
    S = S[j0:]; ys = ys[j0:]
    lines = []
    for c in measure.find_contours(S, 0.0):
        X = xs[0] + c[:, 1] * meta["dx"]; Y = ys[0] + c[:, 0] * meta["dy"]
        lines.append(np.stack([X, Y], 1))
    if not lines:
        return [], None
    ext = [l[:, 0].max() - l[:, 0].min() for l in lines]
    main = lines[int(np.argmax(ext))]
    if main[0, 0] > main[-1, 0]:
        main = main[::-1]
    water = S < 0
    has = water.any(0)
    jt = water.shape[0] - 1 - np.argmax(water[::-1, :], axis=0)
    jt = np.clip(jt, 0, water.shape[0] - 2)
    ii = np.arange(water.shape[1])
    v0 = S[jt, ii]; v1 = S[jt + 1, ii]
    fr_ = np.where(v1 - v0 > 1e-9, -v0 / np.maximum(v1 - v0, 1e-9), 0.0)
    top = np.where(has, ys[jt] + meta["dy"] * np.clip(fr_, 0, 1), np.nan)
    topf = np.nan_to_num(top, nan=-99.0)
    pk, pr = find_peaks(topf, prominence=prom, distance=max(1, int(0.2 * Lc / meta["dx"])))
    closed = [l for l in lines if len(l) > 4 and np.allclose(l[0], l[-1])]
    out = []
    for i in pk:
        if topf[i] < min_eta:
            continue
        xc, yc = float(xs[i]), float(topf[i])
        if (x_lo is not None and xc < x_lo) or (x_hi is not None and xc > x_hi):
            continue
        near = np.where(np.abs(main[:, 0] - xc) <= 2.0 * meta["dx"] + 1e-6)[0]
        if len(near) == 0:
            continue
        ic = int(near[np.argmax(main[near, 1])])
        fwd = main[ic:]
        j_end = len(fwd)
        for j in range(1, len(fwd)):
            if fwd[j, 1] <= 0.0 or fwd[j, 0] - xc > 0.75 * Lc or fwd[j, 0] < xc - 0.75 * Lc:
                j_end = j + 1
                break
        face = resample(fwd[:j_end], 0.5 * vox)
        thmax = float("nan"); tip = None; xv = None
        if len(face) >= 3:
            d = face[2:] - face[:-2]
            th = np.degrees(np.arctan2(-d[:, 1], d[:, 0]))
            okm = (th >= 0) & (th <= 180)
            if okm.any():
                thmax = float(th[okm].max())
                iv = np.where(okm & (th >= 90))[0]
                xv = float(face[1:-1][iv[0], 0]) if len(iv) else None
            xx = face[:, 0]
            imax = int(np.argmax(xx))
            if imax < len(xx) - 1 and (xx[imax] - xx[imax:].min()) >= vox:
                tip = [float(xx[imax]), float(face[imax, 1])]
        cav = []
        for l in closed:
            A = poly_area(l)
            cx, cy = l[:, 0].mean(), l[:, 1].mean()
            if A >= vox * vox and (xc - 0.25 * Lc) <= cx <= (xc + 0.75 * Lc) and cy < yc:
                ix = int(round((cx - xs[0]) / meta["dx"])); iy = int(round((cy - ys[0]) / meta["dy"]))
                if 0 <= ix < S.shape[1] and 0 <= iy < S.shape[0] and S[iy, ix] > 0:
                    cav.append([float(cx), float(cy), float(A)])
        m = (xs > xc) & (xs <= xc + 0.75 * Lc)
        if m.any() and np.isfinite(top[m]).any():
            jt2 = np.where(m)[0][int(np.nanargmin(top[m]))]
            H = yc - float(top[jt2]); xtr = float(xs[jt2])
        else:
            H = float("nan"); xtr = None
        mb = (xs < xc) & (xs >= xc - Lc)                     # 〔FLIP45〕後ろの谷（頂の後ろ 1 λ の最も低い所）
        if mb.any() and np.isfinite(top[mb]).any():
            jb = np.where(mb)[0][int(np.nanargmin(top[mb]))]
            Hb = yc - float(top[jb]); xtb = float(xs[jb]); trb = float(top[jb])
        else:
            Hb = float("nan"); xtb = None; trb = float("nan")
        out.append(dict(xc=xc, eta=yc, thmax=thmax, x_vert=xv, tip=tip, ncav=len(cav), cav=cav[:3], H=H, x_trough=xtr,
                        H1=Hb, x_trough_back=xtb, trough_back=trb, trough_front=(yc - H) if np.isfinite(H) else float("nan")))
    return out, top


def track_crests(rows_by_frame, dx):
    """コマの間で頂をつなぐ（g44_analyze.track_crests の写し）。"""
    tracks = []
    last = {}
    prev_f = None
    for f in sorted(rows_by_frame):
        rows = rows_by_frame[f]
        used = set()
        assign = []
        for r in sorted(rows, key=lambda r: -r["eta"]):
            best = None
            for tid, (pf, px) in last.items():
                if prev_f is None or pf != prev_f or tid in used:
                    continue
                if r["xc"] - 8.0 <= px <= r["xc"] + 3.0:
                    d = abs(px - (r["xc"] - 0.6))
                    if best is None or d < best[0]:
                        best = (d, tid)
            if best is None:
                tid = len(tracks); tracks.append([])
            else:
                tid = best[1]
            used.add(tid)
            assign.append((tid, r))
        for tid, r in assign:
            tracks[tid].append((f, r)); last[tid] = (f, r["xc"])
        prev_f = f
    return tracks


def _component_with(mask, j0, i0):
    lab, n = ndimage.label(mask)
    if not (0 <= j0 < mask.shape[0] and 0 <= i0 < mask.shape[1]) or lab[j0, i0] == 0:
        return None
    return lab == lab[j0, i0]


def crest_width(eta_top, xs, ys, xc, level, ymin_cell=0):
    """ℓ（§6.1）・L-c：η_top[横, x] の、(xc, y = 0) を含み level より高い水のつながった所の、横の最も広い所の幅 × 2。
    横の端は level を切る所を格子の中心の間で線形に補う。返り値 dict(width, x_at, half)。ys は格子の中心（最初が vox/2）。"""
    E = np.nan_to_num(eta_top, nan=-99.0)
    i0 = int(np.argmin(np.abs(xs - xc)))
    j0 = 0
    comp = _component_with(E > level, j0, i0)
    if comp is None:
        return dict(width=0.0, x_at=None, half=0.0, note="頂の所が level より低い")
    best = (0.0, None)
    for i in np.where(comp.any(0))[0]:
        js = np.where(comp[:, i])[0]
        jm = js.max()
        if jm + 1 < len(ys) and E[jm, i] > level >= E[jm + 1, i]:
            yh = ys[jm] + (E[jm, i] - level) / (E[jm, i] - E[jm + 1, i]) * (ys[jm + 1] - ys[jm])
        else:
            yh = ys[jm] + 0.5 * (ys[1] - ys[0])
        if js.min() == 0 and yh > best[0]:
            best = (float(yh), float(xs[i]))
    return dict(width=2.0 * best[0], x_at=best[1], half=best[0])


def face_angle(sl, xs, ys, off, vox, Lc):
    """1 つの x–縦 の断面の最も高い頂の前の面の弦の最大の傾き（度）と頂の x。"""
    meta = dict(x0=float(xs[0]), dx=float(xs[1] - xs[0]), y0=float(ys[0]), dy=float(ys[1] - ys[0]))
    cr, _ = frame_crests(sl, meta, off, vox, Lc)
    if not cr:
        return None
    c = max(cr, key=lambda r: r["eta"])
    return c


def overturn_span(r4, meta4, off, vox, Lc, y_list=None):
    """L-b・L-e の材料：R4 の 1 コマ（sdf[横, 縦, x]）の、y ごとの最も高い頂の前の面の弦の最大の傾き。返り値 [(y, thmax, xc, eta)]。"""
    zs = meta4["z0"] + meta4["dz"] * np.arange(r4.shape[0])
    xs = meta4["x0"] + meta4["dx"] * np.arange(r4.shape[2])
    ys = meta4["y0"] + meta4["dy"] * np.arange(r4.shape[1])
    out = []
    for k in range(r4.shape[0]) if y_list is None else [int(np.argmin(np.abs(zs - y))) for y in y_list]:
        c = face_angle(r4[k].astype(np.float32), xs, ys, off, vox, Lc)
        if c is None:
            continue
        out.append((float(zs[k]), float(c["thmax"]), float(c["xc"]), float(c["eta"])))
    return out


def span_over90(rows):
    """L-b：前の面の弦が 90° を越える y の範囲 × 2（y = 0 から続く範囲）。"""
    ys = sorted((y for y, th, x, e in rows if np.isfinite(th) and th >= 90.0))
    if not ys:
        return 0.0
    return 2.0 * (max(ys) + 0.5 * (rows[1][0] - rows[0][0] if len(rows) > 1 else 0.0))


def jet_angle(u, w):
    """L-d：水平からの角（度、下向きが正）。分類：45° 以下「前へ巻く」、60° 以上「上へ噴く」、間「混じる」。w は上向きが正。"""
    ang = math.degrees(math.atan2(-w, max(abs(u), 1e-9)))
    up = math.degrees(math.atan2(w, max(abs(u), 1e-9)))
    if up >= 60.0:
        kind = "上へ噴く"
    elif abs(math.degrees(math.atan2(w, abs(u)))) <= 45.0:
        kind = "前へ巻く"
    else:
        kind = "混じる"
    return dict(angle_down_deg=ang, angle_from_horizontal_deg=math.degrees(math.atan2(w, abs(u))), kind=kind)


def overhang_cols(sl, xs, ys, off, x_from, x_to):
    """同じ x の列で下から水・空気・水と並ぶ列（覆いかぶさり）の数と、その最も長い続き（x の格子の数）。"""
    water = sl < 0
    cols = []
    for i in np.where((xs >= x_from) & (xs <= x_to))[0]:
        c = water[:, i]
        d = np.diff(np.concatenate([[0], c.astype(np.int8), [0]]))
        starts = np.where(d == 1)[0]
        cols.append(len(starts) >= 2)
    best = run = 0
    for v in cols:
        run = run + 1 if v else 0
        best = max(best, run)
    return int(sum(cols)), int(best)


def plunge_rule(crest, sl, xs, ys, off, vox, Lc):
    """§6.1「前へ巻く」（見直し M10）の 1 コマの判定。crest は frame_crests の頂。返り値 dict(a, b, why)。"""
    a = bool(crest["ncav"] > 0)
    b = False
    tip = crest.get("tip")
    n, run = overhang_cols(sl, xs, ys + 0.0, off, crest["xc"], crest["xc"] + 0.75 * Lc)
    if tip is not None and tip[1] <= 0.0 and run >= 2:
        b = True
    return dict(a_cavity=a, b_tip_overhang=b, overhang_run=run, overhang_cols=n, tip=tip, plunge=bool(a or b))
