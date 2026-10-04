# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S2：原画 DP130155 の波頭（主の頂・唇・b区域の第二の頂）の解剖を原画の画素で測り、原画のカメラで
t* の主役波 K*' AS02C の面の m へ直す（painting_crest.json）。見本02 の 83 本の爪を、冠（CREST_CROWN）・面の内（FACE_INTERIOR）・
近い海（NEAR_SEA）に分ける（claw_roles.json）。

入力（どれも読み取りのみ）：
  - s2_map.npz（s2_map.py：原画の画素 → 主役波のシートの r・c、深さ、|n·v|、xyz）と s2_classes.npz（s2_classes.py：原画の 5 色＋空）
  - 主役波 AS02C の頂点の属性（見本02 の attr/pl29：s = 巻きの向きの本当の弧長、ca = 頂に並ぶ向きの本当の弧長）
  - 仕上げ32 の爪の一覧（原画から我々が取り出した爪。利用者のマスクではない）
  - 見本02 の爪の記録（as02_claws_report.json）と置いた爪の形（ds33_claw_frames_f32.bin・ds33_claw_layout.json）
原画の色は面へ写さない（Q28）。原画のカメラは、原画の画素と面の点を結ぶ測りにだけ使う。生成器はこの道具の出力を読まない。
参照モデルの OBJ・彫刻の写真・利用者のマスクは読まない（利用者のマスクから作った値は見本02 の記録の IoU だけを写す）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/s2_study.py
"""
import hashlib
import json
import math
import os
import sys
import time

import cv2
import numpy as np
from scipy import ndimage

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as01")
import claws_common as CC  # noqa: E402

U = CC.U
ST = REPO + "/Unity/Build/Polish/sample03/study"
TMP = ST + "/tmp"
S02 = REPO + "/Unity/Build/Polish/sample02/fix01/assemble"
ATTR = S02 + "/attr/pl29/pl29_hero_attr_f32.bin"
PARAM = S02 + "/attr_pin/s01_param_f32.bin"
HERO = S02 + "/hero_pkg_AS02C"
CLAWD = S02 + "/claws/mesh"
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
A = 0.4163454124903624
OFFX = 156.66152659984573
SKY, WHITE, MIZU, MIX, AIMID, AIDARK = range(6)
ROLE_CACHE = {}
EDGES = {}
ROW_GROUP = {"上側": "crest_top", "途中": "lip", "船側": "lip", "b区域": "b_crest", "主浪の左下": "face_lowleft"}


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return str(p).replace("\\", "/").replace(REPO + "/", "")


def pct(a, qs=(10, 50, 90)):
    a = np.asarray(a, np.float64)
    a = a[np.isfinite(a)]
    if not len(a):
        return None
    d = {"n": int(len(a))}
    for q in qs:
        d["p%d" % q] = round(float(np.percentile(a, q)), 3)
    d["mean"] = round(float(a.mean()), 3)
    return d


def r3(v, k=3):
    if v is None:
        return None
    if isinstance(v, dict):
        return {kk: r3(x, k) for kk, x in v.items()}
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r3(x, k) for x in v]
    v = float(v)
    return round(v, k) if math.isfinite(v) else None


def runs(lab):
    """1 次元のラベル列の連続の区間 (値, 始め, 終わり(含まない))。"""
    if not len(lab):
        return []
    ch = np.nonzero(np.diff(lab) != 0)[0] + 1
    st = np.r_[0, ch]
    en = np.r_[ch, len(lab)]
    return [(int(lab[a]), int(a), int(b)) for a, b in zip(st, en)]


class Maps:
    def __init__(self):
        m = np.load(TMP + "/s2_map.npz")
        c = np.load(TMP + "/s2_classes.npz")
        self.meta = json.loads(str(m["meta"]))
        self.surf = m["surf"]; self.r = m["r"]; self.c = m["c"]; self.depth = m["depth"]; self.ndv = m["ndv"]; self.P = m["P"]
        self.cls = c["cls"]; self.sky = c["sky"]
        self.H, self.W = self.cls.shape
        self.px_rad = float(self.meta["px_rad"])
        att = np.fromfile(ATTR, np.float32).reshape(240, 400, 12)
        self.att = att
        hm = self.surf == 1
        self.hm = hm
        ys, xs = np.nonzero(hm)
        sa = U.bilin(att[..., 4:6].astype(np.float64), self.r[ys, xs].astype(np.float64), self.c[ys, xs].astype(np.float64))
        self.s = np.full(self.cls.shape, np.nan, np.float32)
        self.ca = np.full(self.cls.shape, np.nan, np.float32)
        self.s[ys, xs] = sa[:, 0]; self.ca[ys, xs] = sa[:, 1]
        self.mpp = self.depth * self.px_rad                              # 画素 1 つの大きさ（m、射線に直交）
        self.area = self.mpp ** 2 / np.clip(self.ndv, 0.25, 1.0)          # 面の上の画素 1 つの面積（m²、斜めは 4 倍で止める）

    def near_hero(self, x, y, rad=60):
        """(x, y) に最も近い主役波の画素（原画の画素）。"""
        x0, x1 = max(0, int(x) - rad), min(self.W, int(x) + rad + 1)
        y0, y1 = max(0, int(y) - rad), min(self.H, int(y) + rad + 1)
        sub = self.hm[y0:y1, x0:x1]
        if not sub.any():
            return None
        yy, xx = np.nonzero(sub)
        d = (xx + x0 - x) ** 2 + (yy + y0 - y) ** 2
        k = int(np.argmin(d))
        return int(xx[k] + x0), int(yy[k] + y0), float(math.sqrt(d[k]))


def zone_masks(M, inv):
    """我々の領域の線引き（原画の画素）：爪の一覧の領域の多角形を行の群ごとに合わせ、閉じて塊にする＋藍の面＋白い点。"""
    H, W = M.H, M.W
    groups = {}
    for k in inv["claws"]:
        if k["zone"] != "main":
            continue
        g = ROW_GROUP.get(k["row"])
        if g is None:
            continue
        if g not in groups:
            groups[g] = np.zeros((H, W), np.uint8)
        poly = k.get("region_polygon_ref") or k.get("polygon_ref_af29")
        if poly:
            cv2.fillPoly(groups[g], [np.round(np.array(poly, np.float64)).astype(np.int32)], 1)
        else:
            cv2.polylines(groups[g], [np.round(np.array(k["centerline_ref"], np.float64)).astype(np.int32)], False, 1, 15)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (51, 51))
    zm = {}
    for g, m in groups.items():
        m2 = cv2.morphologyEx(cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (25, 25))), cv2.MORPH_CLOSE, ker)
        zm[g] = (m2 > 0) & (M.cls != SKY)
    # 藍の面（線を除き、白い点の穴を埋める）
    ind = np.isin(M.cls, [AIMID, AIDARK])
    ind_open = cv2.morphologyEx(ind.astype(np.uint8), cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))) > 0
    lab, n = ndimage.label(ind_open)
    sizes = ndimage.sum(np.ones_like(lab), lab, np.arange(1, n + 1))
    big = np.isin(lab, np.nonzero(sizes >= 20000)[0] + 1)
    holes = ndimage.binary_fill_holes(big) & ~big
    hl, hn = ndimage.label(holes)
    hs = ndimage.sum(np.ones_like(hl), hl, np.arange(1, hn + 1))
    small = np.isin(hl, np.nonzero(hs <= 3000)[0] + 1)
    face = big | small
    # 白い点：800 画素以下で細長くない穴（爪の白い胴を白い点に数えない）
    fl_ok = np.zeros(hn + 1, bool)
    sl = ndimage.find_objects(hl)
    for i, sli in enumerate(sl):
        if sli is None or hs[i] > 800:
            continue
        hh = sli[0].stop - sli[0].start; ww = sli[1].stop - sli[1].start
        if max(hh, ww) / max(min(hh, ww), 1) <= 3.0 and hs[i] / max(hh * ww, 1) >= 0.35:
            fl_ok[i + 1] = True
    flecks = fl_ok[hl] & np.isin(M.cls, [WHITE, MIZU])
    # 大きな白い泡の塊（白・水色。爪の線は 5 px の閉じでつなぐ）：背・頂の冠・唇・b区域の泡
    wm = np.isin(M.cls, [WHITE, MIZU]).astype(np.uint8)
    wm = cv2.morphologyEx(wm, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))) > 0
    wm &= ~face
    wl, wn = ndimage.label(wm)
    ws = ndimage.sum(np.ones_like(wl), wl, np.arange(1, wn + 1))
    big_white = np.isin(wl, np.nonzero(ws >= 30000)[0] + 1)
    return zm, face, flecks, ind_open, big_white


def crest_profiles(M, face, zm, rows, c_lo, c_hi, region_mask):
    """行ごと（巻きの向きの線）の、頂の側から巻きの奥への色の並び。s は本当の弧長 [m]。"""
    out = []
    for r0 in rows:
        sel = M.hm & (np.abs(M.r - r0) < 0.5) & (M.c >= c_lo) & (M.c <= c_hi) & region_mask
        ys, xs = np.nonzero(sel)
        if len(ys) < 50:
            continue
        s = M.s[ys, xs].astype(np.float64)
        o = np.argsort(s)
        ys, xs, s = ys[o], xs[o], s[o]
        # 一続きの区間だけ（s の飛び > 0.5 m で切り、いちばん長い区間）
        br = np.nonzero(np.diff(s) > 0.5)[0]
        segs = np.split(np.arange(len(s)), br + 1)
        seg = max(segs, key=lambda q: s[q[-1]] - s[q[0]])
        ys, xs, s = ys[seg], xs[seg], s[seg]
        # 0.02 m の区切りで多数決
        b = np.floor((s - s[0]) / 0.02).astype(int)
        nb = b.max() + 1
        cl = M.cls[ys, xs]
        fc = face[ys, xs]
        lab = np.full(nb, -1, np.int16)
        isface = np.zeros(nb, bool)
        for k in range(6):
            cnt = np.bincount(b, weights=(cl == k).astype(float), minlength=nb)
            if k == 0:
                best = cnt.copy(); lab[:] = 0
            else:
                upd = cnt > best
                best[upd] = cnt[upd]; lab[upd] = k
        fcount = np.bincount(b, weights=fc.astype(float), minlength=nb)
        tot = np.bincount(b, minlength=nb)
        isface = fcount > 0.5 * np.maximum(tot, 1)
        filled = tot > 0
        sb = s[0] + (np.arange(nb) + 0.5) * 0.02
        # 藍の面の始まり：0.2 m 以上続く藍の面の最初
        f0 = None
        for v, a, e in runs(isface.astype(np.int8)):
            if v == 1 and (e - a) * 0.02 >= 0.2:
                f0 = a
                break
        # 冠（白い泡と爪）の始まり：最初の線（mix・藍濃の細い区間 ≤ 0.12 m）または水色
        c0 = None
        skip = int(0.2 / 0.02)
        for i in range(skip, nb):
            if filled[i] and lab[i] in (MIZU,):
                c0 = i
                break
            if filled[i] and lab[i] in (MIX, AIDARK) and not isface[i]:
                c0 = i
                break
        s90 = float(M.att[int(r0), 90, 4])
        rec = dict(row=int(r0), s_crest_col90=r3(s90), s_top=r3(s[0]), s_end=r3(s[-1]), n_px=int(len(s)),
                   top_from_crest_m=r3(s[0] - s90))
        if f0 is not None:
            rec["s_face_start"] = r3(sb[f0])
            rec["white_top_to_face_m"] = r3(sb[f0] - s[0])
            rec["face_start_from_crest_m"] = r3(sb[f0] - s90)
            if c0 is not None and c0 < f0:
                rec["s_crown_start"] = r3(sb[c0])
                rec["crown_start_from_crest_m"] = r3(sb[c0] - s90)
                rec["crown_depth_m"] = r3(sb[f0] - sb[c0])
                seg_lab = lab[c0:f0][filled[c0:f0]]
                rec["crown_frac"] = {n: r3((seg_lab == k).mean()) for k, n in
                                     [(WHITE, "white"), (MIZU, "mizuiro"), (MIX, "line_mix"), (AIMID, "ai_mid"), (AIDARK, "ai_dark")]}
                # 爪の線の横切り：白・水色の中の暗い細い区間（≤ 0.12 m）
                rr = runs(np.where(np.isin(seg_lab, [MIX, AIDARK, AIMID]), 1, 0).astype(np.int8))
                ncross = sum(1 for v, a, e in rr if v == 1 and (e - a) * 0.02 <= 0.12)
                rec["claw_line_crossings"] = ncross
                rec["claw_line_crossings_per_m"] = r3(ncross / max(sb[f0] - sb[c0], 1e-6))
                mz = np.where(seg_lab == MIZU, 1, 0).astype(np.int8)
                mr = [(e - a) * 0.02 for v, a, e in runs(mz) if v == 1]
                rec["mizuiro_runs_m"] = r3(mr)
            # 面の中（藍の面の始まりから 4 m まで）
            e4 = min(nb, f0 + int(4.0 / 0.02))
            fl = lab[f0:e4][filled[f0:e4]]
            rec["face_0_4m_frac"] = {n: r3((fl == k).mean()) for k, n in
                                     [(WHITE, "white"), (MIZU, "mizuiro"), (MIX, "line_mix"), (AIMID, "ai_mid"), (AIDARK, "ai_dark")]}
        out.append(rec)
    return out


def across_profiles(M, face, cols, r_lo, r_hi, region_mask, name):
    """列ごと（頂に並ぶ向きの線）に、藍の面の中の藍中の帯・藍濃・白の並び。ca は本当の弧長 [m]。"""
    out = []
    for c0 in cols:
        sel = M.hm & (np.abs(M.c - c0) < 0.5) & (M.r >= r_lo) & (M.r <= r_hi) & face & region_mask
        ys, xs = np.nonzero(sel)
        if len(ys) < 80:
            continue
        ca = M.ca[ys, xs].astype(np.float64)
        o = np.argsort(ca)
        ys, xs, ca = ys[o], xs[o], ca[o]
        br = np.nonzero(np.diff(ca) > 0.4)[0]
        segs = np.split(np.arange(len(ca)), br + 1)
        seg = max(segs, key=lambda q: ca[q[-1]] - ca[q[0]])
        ys, xs, ca = ys[seg], xs[seg], ca[seg]
        span = ca[-1] - ca[0]
        if span < 1.0:
            continue
        step = 0.02
        b = np.floor((ca - ca[0]) / step).astype(int)
        nb = b.max() + 1
        cl = M.cls[ys, xs]
        best = None
        lab = np.zeros(nb, np.int16)
        for k in range(6):
            cnt = np.bincount(b, weights=(cl == k).astype(float), minlength=nb)
            if best is None:
                best = cnt.copy(); lab[:] = k
            else:
                upd = cnt > best
                best[upd] = cnt[upd]; lab[upd] = k
        tot = np.bincount(b, minlength=nb)
        # 空の区切り（画素のない所）は前の値で埋める
        for i in range(1, nb):
            if tot[i] == 0:
                lab[i] = lab[i - 1]
        caB = ca[0] + (np.arange(nb) + 0.5) * step
        mid = [(a, e) for v, a, e in runs((lab == AIMID).astype(np.int8)) if v == 1 and (e - a) * step >= 0.06]
        dark = [(a, e) for v, a, e in runs((lab == AIDARK).astype(np.int8)) if v == 1 and (e - a) * step >= 0.06]
        wht = [(a, e) for v, a, e in runs(np.isin(lab, [WHITE, MIZU]).astype(np.int8)) if v == 1]
        cent = [caB[(a + e - 1) // 2] for a, e in mid]
        out.append(dict(col=int(c0), ca_span_m=r3(span), n_ai_mid_bands=len(mid), ai_mid_bands_per_m=r3(len(mid) / span),
                        ai_mid_width_m=r3([(e - a) * step for a, e in mid]),
                        ai_dark_width_m=r3([(e - a) * step for a, e in dark]),
                        ai_mid_spacing_m=r3(np.diff(cent).tolist() if len(cent) > 1 else []),
                        white_crossings=len(wht), white_width_m=r3([(e - a) * step for a, e in wht]),
                        frac={n: r3((lab == k).mean()) for k, n in [(WHITE, "white"), (MIZU, "mizuiro"), (MIX, "line_mix"), (AIMID, "ai_mid"), (AIDARK, "ai_dark")]}))
    return out


def fleck_stats(M, flecks, face, region_mask):
    lab, n = ndimage.label(flecks & region_mask)
    if n == 0:
        return None, []
    idx = np.arange(1, n + 1)
    npx = ndimage.sum(np.ones_like(lab), lab, idx)
    ar = ndimage.sum(np.where(M.hm, M.area, 0.0), lab, idx)
    cy, cx = np.array(ndimage.center_of_mass(np.ones_like(lab), lab, idx)).T
    keep = npx >= 15
    fa = (face & region_mask & M.hm)
    face_area = float(M.area[fa].sum())
    eqd = 2 * np.sqrt(ar / math.pi)
    items = []
    for i in np.nonzero(keep)[0]:
        x, y = int(round(cx[i])), int(round(cy[i]))
        items.append(dict(x=x, y=y, px=int(npx[i]), area_m2=r3(ar[i], 4), eq_diam_m=r3(eqd[i]),
                          s=r3(M.s[y, x]) if M.hm[y, x] else None, ca=r3(M.ca[y, x]) if M.hm[y, x] else None))
    st = dict(count=int(keep.sum()), face_area_m2=r3(face_area, 1), per_m2=r3(keep.sum() / max(face_area, 1e-6)),
              eq_diam_m=pct(eqd[keep]), area_m2=pct(ar[keep]), px=pct(npx[keep]),
              cover_frac_of_face=r3(ar[keep].sum() / max(face_area, 1e-6)))
    return st, items


def tongue_stats(prof):
    """行ごとの藍の面の始まり s_face_start を、頂に並ぶ向き（行）に並べ、白が下へ伸びる所（舌）と藍が上へ伸びる所（藍の頭）を数える。"""
    rr = np.array([p["row"] for p in prof if "s_face_start" in p], float)
    if len(rr) < 5:
        return None
    sf = np.array([p["face_start_from_crest_m"] for p in prof if "s_face_start" in p], float)
    # 0.5 行の細かさで並んでいる前提：3 点でならす
    sm = ndimage.uniform_filter1d(sf, 3, mode="nearest")
    peaks = [i for i in range(1, len(sm) - 1) if sm[i] > sm[i - 1] and sm[i] >= sm[i + 1]]
    vall = [i for i in range(1, len(sm) - 1) if sm[i] < sm[i - 1] and sm[i] <= sm[i + 1]]
    depth = []
    for i in peaks:
        lv = [v for v in vall if v < i]
        rv = [v for v in vall if v > i]
        if lv and rv:
            depth.append(sm[i] - 0.5 * (sm[lv[-1]] + sm[rv[0]]))
    # 行の間の頂に並ぶ向きの弧長（ca）で、舌の間隔を m に
    return dict(rows=rr.tolist(), face_start_from_crest_m=r3(sf.tolist()), n_tongue_peaks=len(peaks), n_indigo_heads=len(vall),
                tongue_relief_m=pct(depth), peak_rows=[int(rr[i]) for i in peaks], valley_rows=[int(rr[i]) for i in vall])


def tongues2d(M, face_c, x_lo, x_hi, y_lo, y_hi, sig=60.0, prom=10.0, jump=25):
    """藍の面の上の縁（原画の画面で列ごとの最も上の藍の面の画素）を、大きくならした線と比べ、白が下へ入り込む所（舌）と藍が上へ出る所（藍の頭）を数える。"""
    xs = np.arange(x_lo, x_hi)
    sub = face_c[y_lo:y_hi, x_lo:x_hi]
    has = sub.any(0)
    ytop = np.where(has, np.argmax(sub, 0) + y_lo, np.nan)
    ok = np.isfinite(ytop)
    if ok.sum() < 50:
        return None, None
    xi = xs[ok]; yt = ytop[ok]
    # 縁の飛び（隣の列で 25 px を超える段、列の抜け）で区切り、40 列以上の区間だけで数える
    cut = np.nonzero((np.abs(np.diff(yt)) > jump) | (np.diff(xi) > 1))[0] + 1
    segs = [sg for sg in np.split(np.arange(len(xi)), cut) if len(sg) >= 40]
    if not segs:
        return None, None
    keep = np.concatenate(segs)
    base = np.zeros_like(yt)
    for sg in segs:
        base[sg] = ndimage.gaussian_filter1d(yt[sg], sig, mode="nearest")
    dev = yt - base                                    # 正＝縁が下がる（白が入り込む）
    from scipy.signal import find_peaks
    pk_l, hd_l, pp_l, hp_l = [], [], [], []
    for sg in segs:
        a_, pa = find_peaks(dev[sg], prominence=prom, distance=15)
        b_, pb = find_peaks(-dev[sg], prominence=prom, distance=15)
        pk_l += list(sg[a_]); pp_l += list(pa["prominences"])
        hd_l += list(sg[b_]); hp_l += list(pb["prominences"])
    pk = np.array(pk_l, int); hd = np.array(hd_l, int)
    pp = {"prominences": np.array(pp_l)}; hp = {"prominences": np.array(hp_l)}
    segid = np.zeros(len(xi), int) - 1
    for j, sg in enumerate(segs):
        segid[sg] = j
    def m_at(x, y):
        y = int(round(y)); x = int(x)
        if 0 <= y < M.H and M.hm[y, x]:
            return float(M.s[y, x]), float(M.ca[y, x]), float(M.mpp[y, x])
        return None
    tong = []
    for i, k in enumerate(pk):
        a = m_at(xi[k], yt[k]); b = m_at(xi[k], base[k] - 0.0)
        # 舌の深さ：縁の点と、隣の藍の頭の高さの平均の点の、s の差（m）
        left = [h for h in hd if h < k and segid[h] == segid[k]]; right = [h for h in hd if h > k and segid[h] == segid[k]]
        ref_y = np.mean([yt[h] for h in (left[-1:] + right[:1])]) if (left or right) else base[k]
        c = m_at(xi[k], ref_y)
        depth_m = abs(a[0] - c[0]) if (a and c) else None
        if depth_m is not None and depth_m > 3.0:          # 別の面へ乗り換えた所（ぶれ）は数えない
            depth_m = None
        depth_px = float(yt[k] - ref_y)
        tong.append(dict(x=int(xi[k]), y=int(yt[k]), prominence_px=r3(pp["prominences"][i], 1), depth_px=r3(depth_px, 1),
                         depth_m_along_s=r3(depth_m), depth_m_screen=r3(depth_px * a[2]) if a else None))
    heads = [dict(x=int(xi[k]), y=int(yt[k]), prominence_px=r3(hp["prominences"][i], 1)) for i, k in enumerate(hd)]
    # 藍の頭の間隔（m：頭の点の xyz の距離）
    sp = []
    hd = np.sort(hd)
    for a_, b_ in zip(hd[:-1], hd[1:]):
        if segid[a_] != segid[b_]:
            continue
        ya, yb = int(yt[a_]), int(yt[b_])
        Pa = M.P[ya, int(xi[a_])]; Pb = M.P[yb, int(xi[b_])]
        if np.isfinite(Pa).all() and np.isfinite(Pb).all():
            dsp = float(np.linalg.norm(Pa.astype(float) - Pb.astype(float)))
            if dsp <= 3.0:                        # 別の面への乗り換え（3 m 超）は数えない
                sp.append(dsp)
    edge = [np.stack([xi[sg], yt[sg]], 1) for sg in segs]
    return dict(x_range=[int(x_lo), int(x_hi)], n_segments=len(segs), edge_columns=int(len(keep)), n_tongues=len(pk), n_indigo_heads=len(hd),
                tongue_depth_m_along_s=pct([q["depth_m_along_s"] for q in tong if q["depth_m_along_s"] is not None]),
                tongue_depth_m_screen=pct([q["depth_m_screen"] for q in tong if q["depth_m_screen"] is not None]),
                head_spacing_m=pct(sp), tongues=tong, heads=heads), edge


def silhouette_lengths(M):
    """主役波の画素の、空に接する縁（原画の画素）を輪郭として取り、xyz で長さを測る。区間は原画の x・y で分ける。"""
    hm = M.hm.astype(np.uint8)
    cs, _ = cv2.findContours(hm, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    C = max(cs, key=len)[:, 0, :]
    sky_d = cv2.dilate(M.sky.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    on_sky = sky_d[C[:, 1], C[:, 0]]
    P = M.P[C[:, 1], C[:, 0]].astype(np.float64)
    ok = on_sky & np.isfinite(P).all(1)
    return C, P, ok


def seg_len(P):
    """xyz の輪郭の長さ（6 点でならす）。輪郭の 1 画素で 0.25 m を超える飛び（別の面への乗り換え）は数えない。"""
    if len(P) < 3:
        return 0.0
    Ps = ndimage.gaussian_filter1d(P, 6, axis=0, mode="nearest")
    d = np.linalg.norm(np.diff(P, axis=0), axis=1)
    ds = np.linalg.norm(np.diff(Ps, axis=0), axis=1)
    return float(ds[d <= 0.25].sum())


def screen_len(M, C):
    """原画の画面の輪郭の長さを、その所の深さで m に直した長さ（射線に直交する見えの長さ）。"""
    if len(C) < 3:
        return 0.0
    q = C.astype(np.float64)
    qs = ndimage.gaussian_filter1d(q, 4, axis=0, mode="nearest")
    dl = np.linalg.norm(np.diff(qs, axis=0), axis=1)
    mpp = M.mpp[C[1:, 1], C[1:, 0]]
    return float(np.nansum(dl * mpp))


def main():
    t0 = time.time()
    M = Maps()
    inv = json.load(open(INV, encoding="utf-8"))
    rep = json.load(open(CLAWD + "/as02_claws_report.json", encoding="utf-8"))
    lay = json.load(open(CLAWD + "/ds33_claw_layout.json", encoding="utf-8"))
    V = np.fromfile(CLAWD + "/ds33_claw_frames_f32.bin", np.float32).reshape(-1, 3).astype(np.float64)
    zm, face, flecks, ind_open, big_white = zone_masks(M, inv)
    np.savez_compressed(TMP + "/s2_zones.npz", face=face, flecks=flecks, big_white=big_white, **{"z_" + k: v for k, v in zm.items()})
    cam = CC.painting_cam()
    CC.HERO = HERO
    Xw = CC.load_hero()
    out = dict(schema="GreatWave.AS03.S2.painting_crest/1", date="2026-10-04",
               noteJa="原画 DP130155 の波頭の解剖を原画の画素で測り、原画のカメラ（PaintingCam v1）で t* の主役波 K*' AS02C の面の m に直した値。"
                      "原画の色は面へ写していない（Q28）。測りのためだけの値で、生成器の入力ではない。",
               units=dict(painting_px="原画 DP130155 の画素（3859×2594）", m="AS02C の面の上の m（s：巻きの向きの本当の弧長、ca：頂に並ぶ向きの本当の弧長）"),
               conversion=dict(px_rad=r3(M.px_rad, 8), m_per_painting_px_at_50m=r3(50 * M.px_rad, 5),
                               display_px_per_painting_px=A,
                               methodJa="原画の画素 1 つを、原画のカメラの射線が最初に当たる AS02C の点へ結び（z バッファ。s2_map.py）、その点の s・ca（頂点の本当の弧長の双線形）と深さを使う。"
                                        "長さは面の上の弧長で、斜めの見えの縮みは含まない。爪の長さだけは、根元の深さでの画面の長さ（射線に直交する長さ。斜めの縮みを戻していない下限）"),
               inputs={rel(p): sha(p) for p in [PAINT, ATTR, INV, CLAWD + "/as02_claws_report.json", CLAWD + "/ds33_claw_layout.json",
                                                 CLAWD + "/ds33_claw_frames_f32.bin", HERO + "/ds27_keypose.json", HERO + "/ds27_pos_rgba16.bin",
                                                 REPO + "/Tools/PaintingTruth/targets/palette.json",
                                                 REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png"]})
    # ---------------------------------------------------------------- 色の割合（領域ごと）
    names = ["sky", "white", "mizuiro", "line_mix", "ai_mid", "ai_dark"]
    zinfo = {}
    for g, m in zm.items():
        cl = M.cls[m]
        hm_in = m & M.hm
        zinfo[g] = dict(painting_px=int(m.sum()), on_hero_px=int(hm_in.sum()), area_on_hero_m2=r3(M.area[hm_in].sum(), 1),
                        frac={names[k]: r3((cl == k).mean()) for k in range(1, 6)},
                        bbox_painting_px=[int(v) for v in (np.nonzero(m.any(0))[0][[0, -1]].tolist() + np.nonzero(m.any(1))[0][[0, -1]].tolist())],
                        s_range_m=r3([np.nanpercentile(M.s[hm_in], 2), np.nanpercentile(M.s[hm_in], 98)]) if hm_in.any() else None,
                        ca_range_m=r3([np.nanpercentile(M.ca[hm_in], 2), np.nanpercentile(M.ca[hm_in], 98)]) if hm_in.any() else None,
                        r_range=r3([np.nanpercentile(M.r[hm_in], 2), np.nanpercentile(M.r[hm_in], 98)], 1) if hm_in.any() else None,
                        c_range=r3([np.nanpercentile(M.c[hm_in], 2), np.nanpercentile(M.c[hm_in], 98)], 1) if hm_in.any() else None)
    out["zones"] = zinfo
    # 主の面（藍の面のうち、b区域の領域の外で、x ≥ 950 の大きな塊）と b区域の下の面
    xs_grid = np.arange(M.W)[None, :]
    ys_grid = np.arange(M.H)[:, None]
    main_reg = (xs_grid >= 1000) & (ys_grid <= 1350) & ~zm.get("b_crest", np.zeros_like(face))
    b_reg = (xs_grid < 1450) & (ys_grid >= 850) & (ys_grid <= 1600)
    # ---------------------------------------------------------------- 巻きの向きの並び（行ごと）
    prof_main = crest_profiles(M, face, zm, np.arange(100, 151, 1), 85, 205, main_reg)
    prof_b = crest_profiles(M, face, zm, np.arange(60, 112, 1), 85, 205, b_reg)
    out["along_curl_main"] = dict(
        noteJa="主の頂：主役波の行（頂に並ぶ向きの番号）ごとに、見える面を s（巻きの向きの弧長）の順に並べ、頂の側の縁から藍の面までと、面の中の色を測った。"
               "s_top は見えている最も頂の側の点（背の白の縁）、s_crown_start は最初の爪の線か水色、s_face_start は 0.2 m 以上続く藍の面の始まり。",
        rows=prof_main,
        summary=dict(white_top_to_face_m=pct([p.get("white_top_to_face_m") for p in prof_main if p.get("white_top_to_face_m") is not None]),
                     crown_depth_m=pct([p.get("crown_depth_m") for p in prof_main if p.get("crown_depth_m") is not None]),
                     claw_line_crossings_per_m=pct([p.get("claw_line_crossings_per_m") for p in prof_main if p.get("claw_line_crossings_per_m") is not None]),
                     crown_mizuiro_frac=pct([p["crown_frac"]["mizuiro"] for p in prof_main if p.get("crown_frac")]),
                     crown_white_frac=pct([p["crown_frac"]["white"] for p in prof_main if p.get("crown_frac")]),
                     mizuiro_run_m=pct(sum([p.get("mizuiro_runs_m", []) for p in prof_main], [])),
                     face0_4_ai_mid=pct([p["face_0_4m_frac"]["ai_mid"] for p in prof_main if p.get("face_0_4m_frac")]),
                     face0_4_ai_dark=pct([p["face_0_4m_frac"]["ai_dark"] for p in prof_main if p.get("face_0_4m_frac")]),
                     face0_4_white=pct([p["face_0_4m_frac"]["white"] for p in prof_main if p.get("face_0_4m_frac")])))
    out["along_curl_b"] = dict(noteJa="b区域（左肩の第二の頂）：同じ測り。", rows=prof_b,
                               summary=dict(white_top_to_face_m=pct([p.get("white_top_to_face_m") for p in prof_b if p.get("white_top_to_face_m") is not None]),
                                            crown_depth_m=pct([p.get("crown_depth_m") for p in prof_b if p.get("crown_depth_m") is not None]),
                                            claw_line_crossings_per_m=pct([p.get("claw_line_crossings_per_m") for p in prof_b if p.get("claw_line_crossings_per_m") is not None]),
                                            crown_mizuiro_frac=pct([p["crown_frac"]["mizuiro"] for p in prof_b if p.get("crown_frac")])))
    out["tongues_rows_main"] = tongue_stats(prof_main)
    out["tongues_rows_b"] = tongue_stats(prof_b)
    lab_f, nf = ndimage.label(face & main_reg)
    if nf:
        szf = ndimage.sum(np.ones_like(lab_f), lab_f, np.arange(1, nf + 1))
        face_main = lab_f == (int(np.argmax(szf)) + 1)
    else:
        face_main = face & main_reg
    t2m, e_m = tongues2d(M, face_main, 850, 1640, 0, 1350, jump=200)
    t2b, e_b = tongues2d(M, face & b_reg & ~face_main, 150, 1350, 900, 1900, jump=40)
    out["tongues_main"] = dict(noteJa="主の藍の面の上の縁（原画の画面の列ごとの最も上の藍の面）を、σ 60 px でならした線と比べた（目立ち 10 px 以上）。舌＝縁が下がる所（白の泡が藍の面へ垂れ下がる）、"
                                      "藍の頭＝縁が上がる所。深さは舌の先と隣の藍の頭の高さの差で、s（巻きの向きの弧長。3 m を超える乗り換えは除く）と、画面の長さを深さで m にした値。頭の間隔は頭の点の xyz の距離。", **(t2m or {}))
    out["tongues_b"] = dict(noteJa="b区域の下の藍の面の上の縁：同じ測り（x 150〜1350、y ≥ 900。縁が 40 px より飛ぶ所で区切る）。", **(t2b or {}))
    edges_all = (e_m or []) + (e_b or [])
    arr = np.empty(len(edges_all), dtype=object)
    for i_, e_ in enumerate(edges_all):
        arr[i_] = e_
    np.save(TMP + "/s2_face_edges.npy", arr, allow_pickle=True)
    EDGES["main"] = np.vstack(e_m) if e_m else np.zeros((0, 2))
    EDGES["b"] = np.vstack(e_b) if e_b else np.zeros((0, 2))
    # 横の線（原画の画面の y 一定）で、主の藍の面の藍中の帯を数える（帯は巻きに沿って縦に走るので、横の線が帯を横切る）
    hz = []
    for yy in (650, 700, 750, 800, 850, 900, 950):
        xs_f = np.nonzero(face_main[yy])[0]
        if len(xs_f) < 50:
            continue
        xa, xb = int(xs_f.min()), int(xs_f.max())
        labr = M.cls[yy, xa:xb + 1]
        fr = face_main[yy, xa:xb + 1]
        midm = (labr == AIMID) & fr
        raw = [(a + xa, e + xa) for v, a, e in runs(midm.astype(np.int8)) if v == 1]
        bands = []
        for a, e in raw:                                   # 6 px 以下の隙間（線・ぼけ）はつなぐ
            if bands and a - bands[-1][1] <= 6:
                bands[-1] = (bands[-1][0], e)
            else:
                bands.append((a, e))
        bands = [(a, e) for a, e in bands if e - a >= 6]

        def P_at(x, yy=yy):
            p_ = M.P[yy, x]
            return p_.astype(np.float64) if np.isfinite(p_).all() else None
        cen, wid = [], []
        for a, e in bands:
            pa, pb = P_at(a), P_at(e - 1)
            pc_ = P_at((a + e - 1) // 2)
            if pa is not None and pb is not None:
                wid.append(float(np.linalg.norm(pa - pb)))
            if pc_ is not None:
                cen.append(pc_)
        spc = [float(np.linalg.norm(cen[i + 1] - cen[i])) for i in range(len(cen) - 1)]
        pa, pb = P_at(xa), P_at(xb)
        span = float(np.linalg.norm(pa - pb)) if (pa is not None and pb is not None) else None
        darkm = (labr == AIDARK) & fr
        dk = [(a + xa, e + xa) for v, a, e in runs(darkm.astype(np.int8)) if v == 1 and (e - a) >= 6]
        dwid = []
        for a, e in dk:
            pa_, pb_ = P_at(a), P_at(e - 1)
            if pa_ is not None and pb_ is not None:
                dwid.append(float(np.linalg.norm(pa_ - pb_)))
        hz.append(dict(y=int(yy), x_range=[xa, xb], face_width_m_chord=r3(span), n_ai_mid_bands=len(bands),
                       ai_mid_band_x=[[int(a), int(e)] for a, e in bands], ai_mid_width_m=r3(wid), ai_mid_spacing_m=r3(spc),
                       ai_dark_width_m=r3(dwid)))
    out["face_bands_horizontal_main"] = dict(
        noteJa="主の藍の面を原画の画面の横の線（y 650〜950、50 px おき）で切り、藍中の帯（6 px 以下の隙間はつなぎ、6 画素以上）を数えた。帯の幅と間隔は、帯の両端・中心の画素の射線が当たる AS02C の点の距離（弦、m）。"
               "帯は巻きに沿って縦に走るので、横の線は帯をほぼ横切る（斜めの分だけ幅は大きめに出る）。",
        lines=hz, summary=dict(n_ai_mid_bands=pct([h["n_ai_mid_bands"] for h in hz]), ai_mid_width_m=pct(sum([h["ai_mid_width_m"] for h in hz], [])),
                               ai_mid_spacing_m=pct(sum([h["ai_mid_spacing_m"] for h in hz], [])), ai_dark_width_m=pct(sum([h["ai_dark_width_m"] for h in hz], [])),
                               face_width_m_chord=pct([h["face_width_m_chord"] for h in hz if h["face_width_m_chord"] is not None])))
    # ---------------------------------------------------------------- 頂に並ぶ向き（列ごと）：藍中の帯
    acr_main = across_profiles(M, face, np.arange(140, 200, 5), 95, 160, main_reg, "main")
    acr_b = across_profiles(M, face, np.arange(170, 200, 5), 55, 112, b_reg, "b")
    def acr_sum(a):
        return dict(n_ai_mid_bands=pct([x["n_ai_mid_bands"] for x in a]), ai_mid_bands_per_m=pct([x["ai_mid_bands_per_m"] for x in a]),
                    ai_mid_width_m=pct(sum([x["ai_mid_width_m"] for x in a], [])), ai_dark_width_m=pct(sum([x["ai_dark_width_m"] for x in a], [])),
                    ai_mid_spacing_m=pct(sum([x["ai_mid_spacing_m"] for x in a], [])), white_width_m=pct(sum([x["white_width_m"] for x in a], [])))
    out["across_face_main"] = dict(noteJa="主の面：主役波の列（巻きの向きの番号）ごとに、藍の面の中を ca（頂に並ぶ向きの弧長）の順に並べ、藍中の帯（巻きに沿って走る線）を数えた。",
                                   cols=acr_main, summary=acr_sum(acr_main))
    out["across_face_b"] = dict(noteJa="b区域の下の藍の面：同じ測り。", cols=acr_b, summary=acr_sum(acr_b))
    # ---------------------------------------------------------------- 白い点
    fs_main, fi_main = fleck_stats(M, flecks, face, main_reg)
    fs_b, fi_b = fleck_stats(M, flecks, face, b_reg & ~main_reg)
    # 面の始まりからの深さ別（主）
    sf_by_row = {p["row"]: p["s_face_start"] for p in prof_main if "s_face_start" in p}
    dep = []
    for it in fi_main:
        if it["s"] is None:
            continue
        y, x = it["y"], it["x"]
        rr = int(round(float(M.r[y, x])))
        if rr in sf_by_row:
            dep.append(it["s"] - sf_by_row[rr])
    dep = np.array(dep)
    bins = [0, 1, 2, 4, 6, 10, 20]
    hist = {"%g-%g m" % (bins[i], bins[i + 1]): int(((dep >= bins[i]) & (dep < bins[i + 1])).sum()) for i in range(len(bins) - 1)}
    out["flecks_main"] = dict(noteJa="藍の面（線を除き、白い点の穴を埋めた塊）の中の、白・水色の小さな塊（原画の画素 15〜800、縦横の比 ≤ 3、外接の箱の 35% 以上を占める。爪の白い胴を除くため）。面積は面の上の m²。",
                              stats=fs_main, depth_below_face_top_m=pct(dep), depth_hist=hist)
    out["flecks_b"] = dict(stats=fs_b)
    # ---------------------------------------------------------------- 縁（空に接する主役波の輪郭）
    C, P, ok = silhouette_lengths(M)
    lip_tip_x = int(C[:, 0][ok].max())
    k_tip = int(np.nonzero(ok & (C[:, 0] == lip_tip_x))[0][0])
    # 頂点（最も上の点）
    k_top = int(np.nonzero(ok)[0][np.argmin(C[ok][:, 1])])
    sil = dict(noteJa="主役波の画素のうち空に接する縁（原画の画素の輪郭）の長さ。*_screen_m は画面の長さをその所の深さで m にした見えの長さ（主に使う値）。"
                      "*_m（xyz）は縁の点の射線の当たる点をつないだ長さで、縁の点の奥行きのぶれ（かすめる面）を含むので参考。頂の最も高い点（原画の画素）・唇の先（x 最大）・唇の下の奥の角（y < 1100 で x 最小）で区切る。",
               summit_painting_px=[int(C[k_top, 0]), int(C[k_top, 1])], lip_tip_painting_px=[int(C[k_tip, 0]), int(C[k_tip, 1])])
    # 輪郭の向きに沿って：頂点 → 唇の先、唇の先 → 唇の下で空が終わる所
    n = len(C)
    def walk(a, b):
        idx = []
        k = a
        while True:
            idx.append(k)
            if k == b or len(idx) > n:
                break
            k = (k + 1) % n
        return np.array(idx)
    i1 = walk(k_top, k_tip)
    i2 = walk(k_tip, k_top)
    if len(i1) > len(i2):
        i1, i2 = i2, i1
        dirn = -1
    else:
        dirn = 1
    # 頂点 → 唇の先（空に接する所だけ）
    seg1 = i1[ok[i1]]
    sil["summit_to_lip_tip_m"] = r3(seg_len(P[seg1]))
    sil["summit_to_lip_tip_screen_m"] = r3(screen_len(M, C[i1]))
    sil["summit_to_lip_tip_painting_px"] = int(len(i1))
    # 唇の先から下（唇の下の空）へ、空に接する一続きの所
    k = k_tip
    seg2 = []
    step = 1 if dirn == 1 else -1
    gap = 0
    for _ in range(n):
        k = (k + step) % n
        if not ok[k]:
            gap += 1
            if gap > 150:
                break
            continue
        gap = 0
        seg2.append(k)
    # 唇の下：唇の先から、y < 1100 の中で x が最も小さい所（唇の下の奥の角）まで
    if seg2:
        s2 = np.array(seg2)
        cand = np.nonzero(C[s2, 1] < 1100)[0]
        cut = int(cand[np.argmin(C[s2[cand], 0])]) if len(cand) else len(s2) - 1
        s2 = s2[:cut + 1]
        sil["lip_tip_to_underside_m"] = r3(seg_len(P[s2]))
        sil["lip_tip_to_underside_screen_m"] = r3(screen_len(M, C[s2]))
        sil["lip_underside_end_painting_px"] = [int(C[s2[-1], 0]), int(C[s2[-1], 1])]
        seg2 = list(s2)
    # 頂点から背へ（左へ）空に接する一続き
    k = k_top
    seg3 = []
    gap = 0
    for _ in range(n):
        k = (k - step) % n
        if not ok[k]:
            gap += 1
            if gap > 150:
                break
            continue
        gap = 0
        seg3.append(k)
    sil["summit_to_back_left_m"] = r3(seg_len(P[np.array(seg3)])) if len(seg3) > 5 else None
    sil["summit_to_back_left_screen_m"] = r3(screen_len(M, C[np.array(seg3)])) if len(seg3) > 5 else None
    sil["back_left_end_painting_px"] = [int(C[seg3[-1], 0]), int(C[seg3[-1], 1])] if seg3 else None
    i1o = i1 if dirn == 1 else i1[::-1]
    np.save(TMP + "/s2_sil.npy", np.vstack([C[seg3[::-1]] if seg3 else np.zeros((0, 2), int), C[i1o], C[np.array(seg2)] if seg2 else np.zeros((0, 2), int)]))
    out["silhouette"] = sil
    # ---------------------------------------------------------------- 原画の爪（仕上げ32 の一覧：原画から我々が取り出した爪）
    rows = {}
    for k in inv["claws"]:
        if k["zone"] != "main":
            continue
        g = ROW_GROUP.get(k["row"], k["row"])
        rt = np.array(k["root_ref"], float); tp = np.array(k["tip_ref"], float)
        x, y = int(round(rt[0])), int(round(rt[1]))
        if not (0 <= x < M.W and 0 <= y < M.H):
            continue
        nh = M.near_hero(x, y)
        if nh is None:
            continue
        hx, hy, dpx = nh
        z = float(M.depth[hy, hx])
        Lpx = float(k.get("length_ref_px") or np.linalg.norm(tp - rt))
        cl = np.array(k["centerline_ref"], float)
        arc = float(np.linalg.norm(np.diff(cl, axis=0), axis=1).sum())
        v = tp - rt
        ang = math.degrees(math.atan2(v[1], v[0]))
        rows.setdefault(g, []).append(dict(id=k["id"], row_ja=k["row"], s=float(M.s[hy, hx]), ca=float(M.ca[hy, hx]), r=float(M.r[hy, hx]), c=float(M.c[hy, hx]),
                                           depth=z, Lpx=Lpx, arc_px=arc, L_m=Lpx * z * M.px_rad, arc_m=arc * z * M.px_rad, ang=ang,
                                           silhouette=bool(k.get("silhouette")), over_indigo=bool(k.get("over_indigo")), root_off_hero_px=dpx))
    claws_p = {}
    for g, L in rows.items():
        ca = np.array([q["ca"] for q in L]); s = np.array([q["s"] for q in L])
        span_ca = float(np.percentile(ca, 97) - np.percentile(ca, 3))
        span_s = float(np.percentile(s, 97) - np.percentile(s, 3))
        # 最も近い根元の間隔（面の上の xyz の代わりに (s, ca) で）
        Q = np.stack([s, ca], 1)
        dmin = []
        for i in range(len(Q)):
            d = np.linalg.norm(Q - Q[i], axis=1)
            d[i] = np.inf
            dmin.append(d.min())
        angs = np.array([q["ang"] for q in L])
        hist = {}
        for lo, hi, nm in [(-180, -135, "左"), (-135, -45, "上"), (-45, 45, "右"), (45, 135, "下"), (135, 181, "左")]:
            hist[nm] = hist.get(nm, 0) + int(((angs >= lo) & (angs < hi)).sum())
        claws_p[g] = dict(count=len(L), rows_ja=sorted(set(q["row_ja"] for q in L)),
                          ca_span_m=r3(span_ca), s_span_m=r3(span_s),
                          per_m_along_crest=r3(len(L) / max(span_ca, 1e-6)),
                          length_root_to_tip_m=pct([q["L_m"] for q in L]), length_arc_m=pct([q["arc_m"] for q in L]),
                          length_painting_px=pct([q["Lpx"] for q in L]),
                          nearest_root_m=pct(dmin), silhouette_frac=r3(np.mean([q["silhouette"] for q in L])),
                          over_indigo_frac=r3(np.mean([q["over_indigo"] for q in L])),
                          tip_direction_painting_count=hist,
                          r_range=r3([min(q["r"] for q in L), max(q["r"] for q in L)], 1), c_range=r3([min(q["c"] for q in L), max(q["c"] for q in L)], 1),
                          s_range_m=r3([float(s.min()), float(s.max())]), ca_range_m=r3([float(ca.min()), float(ca.max())]))
    if "lip" in claws_p and sil.get("summit_to_lip_tip_screen_m"):
        lip_len = (sil["summit_to_lip_tip_screen_m"] or 0) + (sil.get("lip_tip_to_underside_screen_m") or 0)
        claws_p["lip"]["per_m_of_lip_silhouette_screen"] = r3(claws_p["lip"]["count"] / max(lip_len, 1e-6))
        claws_p["lip"]["lip_silhouette_screen_m"] = r3(lip_len)
    for g_, v_ in claws_p.items():
        za = (zinfo.get(g_) or {}).get("area_on_hero_m2")
        if za:
            v_["zone_area_on_hero_m2"] = za
            v_["per_m2_of_zone"] = r3(v_["count"] / za)
    out["painting_claws"] = dict(noteJa="仕上げ32 の爪の一覧（原画 DP130155 から我々が取り出した爪。利用者のマスクではない）の主の波の 213 本を、行の群で集計。"
                                        "根元が主役波の外（空の中）の爪は、最も近い主役波の画素の値を使う。長さは根元の深さでの画面の長さ（下限）。"
                                        "向きは原画の画面で根元 → 先の向き（上＝空の側、右＝唇の進む側、下＝船の側）。",
                                 groups=claws_p,
                                 group_map_ja={"crest_top": "上側（主の頂の縁から背へ巻く爪）", "lip": "途中＋船側（唇の泡の塊の爪）", "b_crest": "b区域（左肩の第二の頂）",
                                               "face_lowleft": "主浪の左下"})
    out["elapsed_s"] = r3(time.time() - t0, 1)
    with open(ST + "/painting_crest.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    # ---------------------------------------------------------------- 見本02 の 83 本の役割
    roles(M, zm, face, ind_open, big_white, rep, lay, V, cam, Xw, claws_p)
    print("done", round(time.time() - t0, 1))


def roles(M, zm, face, ind_open, big_white, rep, lay, V, cam, Xw, claws_p):
    A_ = A
    offx = OFFX
    hero = CC.Hero(Xw)
    # 進む向き（主の行 164 で頂の列 90 → 唇の先の列 200 の水平の向き）
    fwd = Xw[164, 200] - Xw[164, 90]
    fwd[1] = 0
    fwd /= np.linalg.norm(fwd)
    lid = {c["user_id"]: c for c in lay["claws"]}
    sky_dt = ndimage.distance_transform_edt(~M.sky)
    face_dt = ndimage.distance_transform_edt(~face)
    claws_out = []
    tally = {}
    for k in rep["claws"]:
        uid = k["user_id"]
        if not k.get("placed"):
            continue
        L = lid[uid]
        o, n_v, st = L["vert_offset"], L["vert_count"], L["stations"]
        Vc = V[o:o + n_v]
        root = Vc[0]
        tip = Vc[1 + st * 8]
        rings = Vc[1:1 + st * 8].reshape(st, 8, 3).mean(1)
        spine = np.vstack([root, rings, tip])
        q, z = cam.project(spine)
        qp = np.stack([(q[:, 0] + 0.5 - offx) / A_ - 0.5, (q[:, 1] + 0.5) / A_ - 0.5], 1)   # 原画の画素
        xi = np.clip(np.round(qp[:, 0]).astype(int), 0, M.W - 1)
        yi = np.clip(np.round(qp[:, 1]).astype(int), 0, M.H - 1)
        inside = (qp[:, 0] >= 0) & (qp[:, 0] < M.W) & (qp[:, 1] >= 0) & (qp[:, 1] < M.H)
        rh = k["root_hit"]
        surf = rh["surface"]
        rec = dict(id=uid, layout_id=L["id"], surface=surf,
                   root_sheet_rc=[r3(rh["r"], 2), r3(rh["c"], 2)] if surf == "hero" else None,
                   root_xyz=r3(rh["P"]), root_depth_m=r3(rh["depth_m"], 2),
                   root_painting_px=r3(qp[0].tolist(), 1), tip_painting_px=r3(qp[-1].tolist(), 1),
                   iou_painting_sample02=k.get("iou_painting"), iou_face_sample02=k.get("iou_face"),
                   pl32_id=k.get("pl32_best_id"), length_3d_m=k.get("length_3d_m"))
        if surf == "hero":
            sa = U.bilin(M.att[..., 4:6].astype(np.float64), np.array([rh["r"]]), np.array([rh["c"]]))[0]
            rec["root_s_ca_m"] = r3(sa.tolist())
        # 原画の上の周り：骨の点（原画の画素）から空までの距離、骨の周り 30 px の輪の色
        dsky = float(sky_dt[yi[inside], xi[inside]].min()) if inside.any() else None
        mask = np.zeros((M.H, M.W), np.uint8)
        pts = np.round(qp[inside]).astype(np.int32)
        if len(pts) >= 2:
            cv2.polylines(mask, [pts], False, 1, 9)
        ring = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61))) > 0
        ring &= ~(mask > 0)
        cl = M.cls[ring]
        nn = max(len(cl), 1)
        f_ind = float(np.isin(cl, [AIMID, AIDARK]).sum() / nn)
        f_ind_area = float(ind_open[ring].sum() / nn)
        f_white = float(np.isin(cl, [WHITE, MIZU]).sum() / nn)
        f_sky = float((cl == SKY).sum() / nn)
        f_face = float(face[ring].sum() / nn)
        # 根元の画素の領域
        x0, y0 = int(round(qp[0, 0])), int(round(qp[0, 1]))
        zone_at = [g for g, m in zm.items() if 0 <= x0 < M.W and 0 <= y0 < M.H and m[y0, x0]]
        rec["painting_context"] = dict(min_dist_to_sky_px=r3(dsky, 1), ring30_frac=dict(sky=r3(f_sky), white_mizuiro=r3(f_white), indigo=r3(f_ind),
                                                                                        indigo_area=r3(f_ind_area), face=r3(f_face)),
                                       root_in_zone=zone_at, root_dist_to_face_px=r3(float(face_dt[y0, x0]) if 0 <= x0 < M.W and 0 <= y0 < M.H else None, 1))
        # 役割（大きな白い泡の塊に付いているか）
        bw_dt = ROLE_CACHE.get("bw_dt")
        if bw_dt is None:
            bw_dt = ndimage.distance_transform_edt(~big_white)
            ROLE_CACHE["bw_dt"] = bw_dt
        nfirst = max(2, int(0.4 * len(qp)))
        qi = inside[:nfirst]
        d_bw_px = float(bw_dt[yi[:nfirst][qi], xi[:nfirst][qi]].min()) if qi.any() else None
        mpp_root = float(rh["depth_m"]) * M.px_rad
        d_bw_m = d_bw_px * mpp_root if d_bw_px is not None else None
        d_face_m = float(face_dt[y0, x0]) * mpp_root if (0 <= x0 < M.W and 0 <= y0 < M.H) else None
        in_face_m = float(ROLE_CACHE.setdefault("face_in_dt", ndimage.distance_transform_edt(face))[y0, x0]) * mpp_root if (0 <= x0 < M.W and 0 <= y0 < M.H) else None
        rec["painting_context"].update(dist_spine40_to_big_white_px=r3(d_bw_px, 1), dist_spine40_to_big_white_m=r3(d_bw_m),
                                       root_depth_into_face_m=r3(in_face_m))
        if surf != "hero":
            role = "NEAR_SEA"
            why = "根元が近い海（手前の小波）の面にある"
        else:
            at_sil = dsky is not None and dsky <= 12
            in_foam = f_white >= 0.45 and f_face <= 0.35
            on_face = f_face >= 0.45
            if at_sil:
                role = "CREST_CROWN"
                why = "爪の骨が空の縁から %.0f px（原画の画素）：原画の爪の輪（外の縁）" % dsky
            elif in_foam:
                role = "CREST_CROWN"
                why = "骨の周り 30 px の白・水色 %.0f%%・藍の面 %.0f%%：白い泡の塊の中の爪" % (100 * f_white, 100 * f_face)
            elif on_face:
                role = "FACE_INTERIOR"
                why = "骨の周り 30 px の藍の面 %.0f%%（白・水色 %.0f%%）、空から %.0f px：藍の面の上に描かれた鉤" % (100 * f_face, 100 * f_white, dsky if dsky is not None else -1)
            else:
                role = "CREST_CROWN" if f_white >= f_face else "FACE_INTERIOR"
                why = "境の場合：骨の周りの白・水色 %.0f%%、藍の面 %.0f%% の多い方" % (100 * f_white, 100 * f_face)
            # 藍の面の上の縁（主・b区域）までの、根元からの距離（m）
            dE = None
            for key in ("main", "b"):
                E = EDGES.get(key)
                if E is not None and len(E):
                    dd_ = float(np.min(np.hypot(E[:, 0] - qp[0, 0], E[:, 1] - qp[0, 1]))) * mpp_root
                    dE = dd_ if dE is None else min(dE, dd_)
            rec["painting_context"]["root_to_face_top_edge_m"] = r3(dE)
            rec["face_top_fringe"] = bool(role == "FACE_INTERIOR" and dE is not None and dE <= 0.8)
            # どの冠か：根元の領域、なければ最も近い領域
            part = None
            for g in ("lip", "crest_top", "b_crest"):
                if g in zone_at:
                    part = g
                    break
            if part is None:
                best = None
                for g in ("lip", "crest_top", "b_crest", "face_lowleft"):
                    if g not in zm:
                        continue
                    dt = ROLE_CACHE.setdefault("zdt_" + g, ndimage.distance_transform_edt(~zm[g]))
                    dv = float(dt[y0, x0]) if (0 <= x0 < M.W and 0 <= y0 < M.H) else 1e9
                    if best is None or dv < best[0]:
                        best = (dv, g)
                part = best[1] if best else None
                rec["painting_context"]["nearest_zone_px"] = r3(best[0], 1) if best else None
                if best and best[0] > 150:
                    part = "other_foam"           # 我々の領域から 150 px より遠い（左下の手前の泡など）
            rec["crown_part" if role == "CREST_CROWN" else "zone_part"] = part
        rec["role"] = role
        rec["role_reason_ja"] = why
        # 指の向きの提案（原画の画面の根元 → 先の向きを、根元の面の法線（外）・進む向き（前）・下（垂れ）の画面の向きと比べる）
        d2 = qp[min(len(qp) - 1, max(2, len(qp) // 2))] - qp[0]
        d2t = qp[-1] - qp[0]
        def img_dir(vec):
            P0 = root
            a, _ = cam.project(np.vstack([P0, P0 + 0.5 * vec]))
            v = (a[1] - a[0]) / A_
            return v / max(np.linalg.norm(v), 1e-9)
        if surf == "hero":
            nrm = hero.frame(np.array([rh["r"]]), np.array([rh["c"]]))[0][2]
        else:
            nrm = np.array([0.0, 1.0, 0.0])
        e_out, e_fwd, e_down = img_dir(nrm), img_dir(fwd), img_dir(np.array([0.0, -1.0, 0.0]))
        dd = d2t / max(np.linalg.norm(d2t), 1e-9)
        dm = d2 / max(np.linalg.norm(d2), 1e-9)
        cosv = dict(outward=float(dd @ e_out), forward=float(dd @ e_fwd), droop=float(dd @ e_down))
        cosm = dict(outward=float(dm @ e_out), forward=float(dm @ e_fwd), droop=float(dm @ e_down))
        lab = [kname for kname, v in sorted(cosv.items(), key=lambda t: -t[1]) if v >= 0.35]
        if not lab:
            lab = [max(cosv, key=cosv.get)]
        # 巻き：根元の半分の向きと全体の向きの差
        curl = math.degrees(math.acos(np.clip(dd @ dm, -1, 1)))
        # 根元の法線と射線の角：|n·v| が大きい（面がカメラを向く）と、法線の画面の向きは短く、「外へ」の判定は弱い
        vray = root - cam.pos
        vray /= max(np.linalg.norm(vray), 1e-9)
        ndv_root = float(abs(nrm @ vray))
        # 3D の向きの手がかり：余弦が正の向き（外へ＝法線、前へ＝進む向き、垂れる＝下）を余弦で重み付けした和
        wv = np.zeros(3)
        for kname, vec in (("outward", nrm), ("forward", fwd), ("droop", np.array([0.0, -1.0, 0.0]))):
            if kname == "outward" and ndv_root > 0.8:
                continue
            wv += max(cosv[kname], 0.0) * vec
        sv = (wv / np.linalg.norm(wv)).tolist() if np.linalg.norm(wv) > 1e-6 else None
        if ndv_root > 0.8 and "outward" in lab and len(lab) > 1:
            lab = [x for x in lab if x != "outward"]
        rec["finger_direction"] = dict(suggest=lab, cos_root_to_tip=r3(cosv), cos_first_half=r3(cosm), curl_first_half_vs_whole_deg=r3(curl, 1),
                                       painting_angle_deg=r3(math.degrees(math.atan2(dd[1], dd[0])), 1),
                                       root_normal_dot_view=r3(ndv_root), outward_reliable=bool(ndv_root <= 0.8),
                                       suggest_vec_world=r3(sv),
                                       noteJa="原画の画面で、根元 → 先の向きと、根元の法線（外へ）・進む向き（前へ）・下向き（垂れる）を画面へ写した向きの余弦。0.35 以上を挙げた。"
                                              "根元の面がカメラを向く（|n·v| > 0.8）時は「外へ」の画面の向きが短く弱いので、ほかの向きがあれば外し、3D の手がかりにも入れない。"
                                              "suggest_vec_world は余弦が正の向きを余弦で重み付けして足した世界の単位ベクトル（Unity の座標、y が上）で、指の向きの手がかり（決まりではない）")
        claws_out.append(rec)
        tally[role] = tally.get(role, 0) + 1
    by_part = {}
    for c in claws_out:
        key = c["role"] + ":" + str(c.get("crown_part") or c.get("zone_part"))
        by_part[key] = by_part.get(key, 0) + 1
    res = dict(schema="GreatWave.AS03.S2.claw_roles/1", date="2026-10-04",
               noteJa="見本02（修正の回 1）で置いた 83 本の爪（主役波 73・近い海 10）を、原画の上の周りで分けた。CREST_CROWN＝頂・唇・b区域の冠の縁（立体の白い指の先になる）、"
                      "FACE_INTERIOR＝藍の面の上の原画の鉤（Q29 の区域 2）、NEAR_SEA＝近い海。決め方は rule_ja。役割は進行役の読みで、利用者は未確認。",
               rule_ja=["NEAR_SEA：根元の面が近い海",
                        "CREST_CROWN：爪の骨（置いた 3D の爪の背骨を原画のカメラで写した線）が空の縁から 12 px 以内（原画の爪の輪＝Q29 の「原画の爪の輪」）、または骨の周り 30 px の輪の白・水色 ≥ 45% かつ藍の面 ≤ 35%（白い泡の塊の中の爪）",
                        "FACE_INTERIOR：骨の周り 30 px の輪の藍の面 ≥ 45%（藍の面の上に描かれた鉤。Q29 の区域 2）",
                        "どちらでもない時は、輪の白・水色と藍の面の多い方",
                        "face_top_fringe：FACE_INTERIOR のうち、根元が藍の面の上の縁（tongues_main・tongues_b の縁の線）から 0.8 m 以内の爪（藍の面の上の縁で、白の泡の垂れの先に付く鉤）",
                        "冠の部分（crown_part）は、根元が入る我々の領域（一覧の爪の領域を行の群ごとに閉じた塊：crest_top＝上側、lip＝途中＋船側、b_crest＝b区域）。入らない時は最も近い領域",
                        "藍の面＝藍中・藍濃（9 px の開きで線を除く）の 2 万画素以上の塊に、3,000 画素以下の穴（白い点）を足したもの",
                        "参考に、骨の周り 30 px の輪の色の割合と空までの距離も記録した（ring30_frac・min_dist_to_sky_px）"],
               counts=tally, crown_parts=by_part, claws=claws_out,
               inputs={rel(CLAWD + "/as02_claws_report.json"): sha(CLAWD + "/as02_claws_report.json"),
                       rel(CLAWD + "/ds33_claw_frames_f32.bin"): sha(CLAWD + "/ds33_claw_frames_f32.bin"),
                       rel(CLAWD + "/ds33_claw_layout.json"): sha(CLAWD + "/ds33_claw_layout.json")},
               forward_vector_world=r3(fwd.tolist()))
    with open(ST + "/claw_roles.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("roles", tally, by_part)


if __name__ == "__main__":
    main()
