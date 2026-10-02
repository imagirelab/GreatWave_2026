# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：自己評審の指摘の数を、前（仕上げ32 修正の回 1）・作る部（仕上げ33）・修正の回 1 の 3 つで同じ式で数え直す（numpy・OpenCV。記録）。

数の定義は、自己評審（数の評審 j33_img・j33_sil・j33_geo）の式に合わせた（閾値・連結・穴の数え方を同じにした。生成器とは別の式）。
画像（Unity の PC オフスクリーン描画、1920×1080、同じ視点・同じ時刻 t 6・9・10.5・12 s）：
  - 視点ごと：爪の画素（作品のままと爪なしの差の最大のチャンネル > 12）、藍の上の爪の画素（爪なしの明るさ < 110）、白・空の上の暗い線、
    明るい地に触れない浮いた成分（8 連結 20 px 以上、5×5 に広げた明るい地に触れない）、ほとんど（80% 超）藍の上の成分。
  - 原画視点 t 9・10.5・12 s：主役波（numpy の z バッファを 7×7 に太らせた所）の外の爪の画素と成分。
  - 閉じた輪（米粒）：爪の差の暗い画素（明るさ < 130）の 8 連結の成分（15 px 以上）が、4 連結の穴（4 px 以上）を囲む数。全体と b区域。
  - 原画視点 t* の律動：一覧の爪の領域（13×13 に太らせた所）と b区域の、白い地の上の水色の版の割合、暗い線（pl32f_measure.dark_lines）、
    b区域の水色の置き場所の精度・再現（4 px の許し）。
  - 回り台：12 方位の前との差の画素と、新しい白の上の暗い線。
幾何（爪の層のコマの表）：断面の上面の向きのコマの間の裏返り（> 90°）と隣の輪の間のねじれ（> 60°）、t* の 45° を超える折れと縁の折れ返り、
  輪の中心が面より 5 cm 以上下（原画の爪・冠の爪・膜、t 9・10.5・12 s、最近の頂点の法線）、冠の爪の原画のカメラから見える頂点（同じ 3 コマ）、
  NaN・瞬間移動（根元に対して 0.5 m 超）・跳び（> 0.15 m かつ前後の 4 倍）・点滅、冠の爪の根元とシートの頂点の距離、T_white より前に生まれる冠の爪。
稜の縁取り：後ろ 65° と回り台 12 方位の t* で、主役波の上の縁の画素のうち、見える爪の頂点（原画の爪・冠の爪の輪）が 15 px 以内にある割合。
出力：Unity/Build/Polish/33/fix01/measure/pl33f_measure.json
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_measure.py [--fix-run …] [--fix-claws …] [--build-run …] [--build-claws …]
修正の回 2：--build-run／--build-claws で build の欄を修正の回 1 にし、fix の欄を修正の回 2 にして同じ式で数える（出力の "runs"・"claws" に置き場所が残る）。
"""
import argparse
import json
import os
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl32")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl32f_measure as M  # noqa: E402
import pl33f_crown as KC  # noqa: E402

U = KC.U
W31 = KC.W31
B = REPO + "/Unity/Build/Polish"
RUNS = dict(before=B + "/32/fix01/r_fix01", build=B + "/33/r_after", fix=B + "/33/fix01/r_fix01")
CLAWS = dict(before=B + "/32/fix01/claws", build=B + "/33/claws", fix=B + "/33/fix01/claws")
INV = B + "/32/fix01/list/ds32_claw_inventory.json"
OUT = B + "/33/fix01/measure"
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TS = ["t060", "t090", "t105", "t120"]
RING = 8
KS = 360
MIZ = np.array([206, 215, 203], np.float64)


def gray(a):
    return cv2.cvtColor(a, cv2.COLOR_BGR2GRAY).astype(np.int32)


def claw_mask(a, f):
    return np.abs(a.astype(np.int32) - f.astype(np.int32)).max(2) > 12


def view_stats(a, f):
    m = claw_mask(a, f)
    gf, ga = gray(f), gray(a)
    light_bg = gf >= 150
    over_ind = m & (gf < 110)
    line = m & (ga < 110) & light_bg
    n, cc, st, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
    lb_d = cv2.dilate(light_bg.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    touch = np.bincount(cc[lb_d & m].ravel(), minlength=n)
    sizes = st[:, 4]
    big = (np.arange(n) > 0) & (sizes >= 20)
    floating = big & (touch == 0)
    ind_cnt = np.bincount(cc[over_ind].ravel(), minlength=n)
    mostly_ind = big & (ind_cnt > 0.8 * sizes)
    return dict(claw_px=int(m.sum()), over_indigo_px=int(over_ind.sum()), line_on_light_px=int(line.sum()),
                floating_comps=int(floating.sum()), floating_px=int(sizes[floating].sum()),
                mostly_indigo_comps=int(mostly_ind.sum()), mostly_indigo_px=int(sizes[mostly_ind].sum()),
                largest_mostly_indigo=int(sizes[mostly_ind].max()) if mostly_ind.any() else 0)


def rings(a, f, Z):
    diff = np.abs(a.astype(int) - f.astype(int)).sum(2) > 20
    dark = diff & (gray(a) < 130) & Z
    n, cc, st, cen = cv2.connectedComponentsWithStats(dark.astype(np.uint8), connectivity=8)
    lst = []
    for k in range(1, n):
        if st[k, 4] < 15:
            continue
        x, y, w, h = st[k, :4]
        sub = (cc[y:y + h, x:x + w] == k).astype(np.uint8)
        n2, cc2, st2, _ = cv2.connectedComponentsWithStats(np.pad(1 - sub, 1, constant_values=1), connectivity=4)
        if n2 > 2:
            holes = sorted(int(s) for s in st2[1:, 4])[:-1]
            lst.append(dict(xy=[int(cen[k, 0]), int(cen[k, 1])], hole_max=max(holes)))
    return dict(rings=len(lst), rings_hole_ge4=sum(1 for r in lst if r["hole_max"] >= 4), big_holes=[r for r in lst if r["hole_max"] >= 20][:8])


def claw_zone():
    inv = json.load(open(INV, encoding="utf-8"))
    Z = np.zeros((1080, 1920), np.uint8)
    for c in inv["claws"]:
        if c.get("zone") != "main" or not c.get("region_polygon_ref"):
            continue
        cv2.fillPoly(Z, [np.round(M.r2d(np.asarray(c["region_polygon_ref"]))).astype(np.int32)], 1)
    return cv2.dilate(Z, np.ones((13, 13), np.uint8)).astype(bool)


def miz_mask(img):
    return np.abs(img.astype(np.float64) - MIZ).max(2) < 30


def load_claws(d):
    lay = json.load(open(d + "/ds33_claw_layout.json", encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    X = np.memmap(d + "/" + lay["files"]["frames"]["file"], dtype=np.float32, mode="r", shape=(F, V, 3))
    return lay, X


def kind(cid):
    return "W" if cid.startswith("W") else ("K" if cid.startswith("K") else ("S" if cid.startswith("S") else "C"))


def rings_of(X, c, f=slice(None)):
    o, st = c["vert_offset"], c["stations"]
    A = np.asarray(X[f, o + 1:o + 1 + st * RING], np.float64)
    return A.reshape(st, RING, 3) if A.ndim == 2 else A.reshape(A.shape[0], st, RING, 3)


def orient(X, lay):
    ff, tr = 0, 0
    per = {}
    for c in lay["claws"]:
        if kind(c["id"]) not in ("C", "K", "S"):
            continue
        rg = rings_of(X, c)
        upv = rg[:, :, 2] - rg[:, :, 6]
        nn = np.linalg.norm(upv, axis=2)
        u_ = upv / np.maximum(nn, 1e-12)[..., None]
        okf = (nn[1:] > 1e-4) & (nn[:-1] > 1e-4)
        nf = int((((u_[1:] * u_[:-1]).sum(2) < 0) & okf).sum())
        okr = (nn[:, 1:] > 1e-4) & (nn[:, :-1] > 1e-4)
        nt = int((((u_[:, 1:] * u_[:, :-1]).sum(2) < 0.5) & okr).sum())
        ff += nf; tr += nt
        if c["id"] in ("C021", "C067", "C090", "C072", "C083", "C114"):
            per[c["id"]] = dict(frame_flips=nf, ring_twists_gt60=nt)
    return dict(frame_flips_gt90=ff, ring_twists_gt60=tr, focus=per)


def bends(X, lay):
    n45, nfold = 0, 0
    for c in lay["claws"]:
        if kind(c["id"]) != "C":
            continue
        rg = rings_of(X, c, KS)
        ctr = rg.mean(1)
        seg = np.diff(ctr, axis=0)
        L = np.linalg.norm(seg, axis=1)
        if L.sum() < 1e-3:
            continue
        s = seg / np.maximum(L, 1e-12)[:, None]
        if (np.degrees(np.arccos(np.clip((s[1:] * s[:-1]).sum(1), -1, 1))) > 45).any():
            n45 += 1
        fold = any(((np.diff(rg[:, e], axis=0) * seg).sum(1) < 0).any() for e in (0, 4))
        nfold += int(fold)
    return dict(claws_bend_gt45=n45, claws_edge_foldback=nfold)


def motion(X, lay):
    mv = {}
    for k in "CWKS":
        nan = 0; worst = 0.0; tele = 0; pops = 0; blinks = 0
        for c in lay["claws"]:
            if kind(c["id"]) != k:
                continue
            o, n = c["vert_offset"], c["vert_count"]
            A = np.asarray(X[:, o:o + n], np.float64)
            nan += int(np.isnan(A).sum())
            rel = A - A[:, :1]
            d1 = np.linalg.norm(np.diff(rel, axis=0), axis=2).max(1)
            worst = max(worst, float(d1.max()))
            tele += int((d1 > 0.5).sum())
            prev = np.r_[np.inf, d1[:-1]]; nxt = np.r_[d1[1:], np.inf]
            nb = np.maximum(np.minimum(prev, nxt), 1e-3)
            pops += int(((d1 > 0.15) & (d1 > 4 * nb)).sum())
            on = np.linalg.norm(rel, axis=2).max(1) > 1e-3
            ups = int(((~on[:-1]) & on[1:]).sum()); downs = int((on[:-1] & (~on[1:])).sum())
            blinks += int(ups > 1 or downs > 0)
        mv[k] = dict(nan=nan, max_rel_step_m=round(worst, 4), teleports_gt0p5m=tele, pops=pops, blink_claws=blinks)
    return mv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix-run", default=RUNS["fix"])
    ap.add_argument("--fix-claws", default=CLAWS["fix"])
    ap.add_argument("--build-run", default=RUNS["build"], help="修正の回 2：build の欄に修正の回 1 を入れて比べる（既定は作る部）")
    ap.add_argument("--build-claws", default=CLAWS["build"])
    ap.add_argument("--out", default=OUT + "/pl33f_measure.json")
    ap.add_argument("--skip-geo", action="store_true")
    a = ap.parse_args()
    RUNS["fix"] = a.fix_run
    CLAWS["fix"] = a.fix_claws
    RUNS["build"] = a.build_run
    CLAWS["build"] = a.build_claws
    t0 = time.time()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    out = {"rule_ja": __doc__, "runs": {k: os.path.relpath(v, REPO).replace("\\", "/") for k, v in RUNS.items()},
           "claws": {k: os.path.relpath(v, REPO).replace("\\", "/") for k, v in CLAWS.items()}}
    # ---- 画像
    views = {}
    for v in VIEWS:
        for t in TS:
            e = {}
            for k, d in RUNS.items():
                im = cv2.imread(d + "/views/%s_%s_asis.png" % (v, t)); fr = cv2.imread(d + "/views/%s_%s_clawfree.png" % (v, t))
                e[k] = view_stats(im, fr) if im is not None and fr is not None else None
            views["%s_%s" % (v, t)] = e
    out["views"] = views
    hero = U.K.Pkg(KC.HERO)
    wt, wtau = W31.load_warp(KC.WARP)
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    pcam = U.CamWH(spec, 1920, 1080)
    b0, b1 = U.BODY

    def tau_of(f):
        t = f / 30.0
        return 0.0 if t >= 12 - 1e-9 else float(np.interp(t, wt, wtau))
    sil = {}
    hero_z = {}
    for f, tag in ((270, "t090"), (315, "t105"), (KS, "t120")):
        Xs = hero.world(tau_of(f))
        R, C = Xs.shape[:2]
        Tg = U.K.grid_tris(R, C, b0, b1)
        idb, zb = U.raster(pcam, Xs.reshape(-1, 3)[Tg], np.arange(1, len(Tg) + 1))
        hero_z[f] = (Xs, zb)
        hmd = cv2.dilate((zb > 0).astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        e = {}
        for k, d in RUNS.items():
            im = cv2.imread(d + "/views/painting_%s_asis.png" % tag); fr = cv2.imread(d + "/views/painting_%s_clawfree.png" % tag)
            m = claw_mask(im, fr)
            om = m & ~hmd
            n, cc, st, cen = cv2.connectedComponentsWithStats(om.astype(np.uint8), connectivity=8)
            big = sorted([(int(st[i, 4]), [int(cen[i, 0]), int(cen[i, 1])]) for i in range(1, n) if st[i, 4] >= 20], reverse=True)
            e[k] = dict(claw_px=int(m.sum()), claw_px_outside_hero=int(om.sum()), outside_components_ge20=len(big), outside_top5=big[:5])
        sil[tag] = e
    out["painting_outside_hero"] = sil
    Zb = M.zone_mask()
    rg = {}
    for k, d in RUNS.items():
        for t in ("t090", "t105", "t120"):
            im = cv2.imread(d + "/views/painting_%s_asis.png" % t); fr = cv2.imread(d + "/views/painting_%s_clawfree.png" % t)
            rg["%s_%s_all" % (k, t)] = rings(im, fr, np.ones_like(Zb))
            rg["%s_%s_bregion" % (k, t)] = rings(im, fr, Zb)
    out["closed_rings"] = rg
    P = M.paint_disp()
    Zc = claw_zone()
    rh = {}
    gP = gray(P)
    pm = miz_mask(P)
    for nm, Z in (("claw_zone", Zc), ("bregion", Zb)):
        rh["%s_painting" % nm] = dict(mizuiro=M.mizuiro_frac(P, Z), **M.dark_lines(P, Z))
        for k, d in RUNS.items():
            im = cv2.imread(d + "/views/painting_t120_asis.png")
            ga = gray(im)
            A_ = miz_mask(im) & Z & (ga > 170)
            B_ = pm & Z & (gP > 170)
            Ad = cv2.dilate(A_.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
            Bd = cv2.dilate(B_.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
            rh["%s_%s" % (nm, k)] = dict(mizuiro=M.mizuiro_frac(im, Z), **M.dark_lines(im, Z),
                                         miz_precision_tol4=round(float((A_ & Bd).sum() / max(1, A_.sum())), 4),
                                         miz_recall_tol4=round(float((B_ & Ad).sum() / max(1, B_.sum())), 4))
    out["painting_tstar_rhythm"] = rh
    # 計画 §5.3 の行 10：空へ出る爪が主役波の輪郭の線に作る白い欠け（t*）。主役波（numpy の z バッファ）の縁の画素のうち、
    # 爪なしの描画では暗い線（明るさ < 110）なのに、作品のままの描画では明るい（> 170）画素の数と、その 8 連結の成分（3 px 以上）の数
    Xs_, zb_ = hero_z[KS]
    hm = (zb_ > 0).astype(np.uint8)
    edge = (cv2.dilate(hm, np.ones((5, 5), np.uint8)) - cv2.erode(hm, np.ones((5, 5), np.uint8))).astype(bool)
    notch = {}
    for k, d in RUNS.items():
        im = cv2.imread(d + "/views/painting_t120_asis.png"); fr = cv2.imread(d + "/views/painting_t120_clawfree.png")
        nm_ = edge & (gray(fr) < 110) & (gray(im) > 170)
        n, cc, st, _ = cv2.connectedComponentsWithStats(nm_.astype(np.uint8), connectivity=8)
        notch[k] = dict(notch_px=int(nm_.sum()), notch_components_ge3=int((st[1:, 4] >= 3).sum()), outline_px=int((edge & (gray(fr) < 110)).sum()))
    out["lip_outline_white_notches_tstar"] = notch
    tt = {}
    for t in ("t090", "t105", "t120"):
        for az in range(0, 360, 30):
            n_ = "%s_az%03d_claws.png" % (t, az)
            bimg = cv2.imread(RUNS["before"] + "/tt/" + n_)
            if bimg is None:
                continue
            gb = gray(bimg)
            e = {}
            for k in ("build", "fix"):
                im = cv2.imread(RUNS[k] + "/tt/" + n_)
                if im is None:
                    continue
                dd = np.abs(im.astype(int) - bimg.astype(int)).max(2) > 12
                e[k] = dict(changed_px=int(dd.sum()), new_dark_line_on_light_px=int((dd & (gray(im) < 110) & (gb >= 150)).sum()))
            tt[n_[:-11]] = e
    out["turntable_vs_before"] = tt
    print("images done", round(time.time() - t0, 1), flush=True)
    if a.skip_geo:
        json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return
    # ---- 幾何
    geo = {}
    lays = {k: load_claws(d) for k, d in CLAWS.items()}
    for k, (lay, X) in lays.items():
        g = dict(counts={kk: sum(1 for c in lay["claws"] if kind(c["id"]) == kk) for kk in "CWKS"}, vertices=lay["vertices"], triangles=lay["triangles"])
        g["section_orientation"] = orient(X, lay)
        g["bends_tstar"] = bends(X, lay)
        g["motion"] = motion(X, lay)
        pen, vis = {}, {}
        for f in (270, 315, KS):
            Xs, zb = hero_z[f]
            Vf = Xs.reshape(-1, 3)
            tree = cKDTree(Vf)
            dr = np.gradient(Xs, axis=0); dc = np.gradient(Xs, axis=1)
            nrm = np.cross(dr, dc); nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)
            nrm = nrm.reshape(-1, 3)
            for nm in "CKWS":
                below, tot, deep = 0, 0, 0.0
                for c in lay["claws"]:
                    if kind(c["id"]) != nm:
                        continue
                    ctr = rings_of(X, c, f).mean(1)
                    if np.linalg.norm(ctr[-1] - ctr[0]) < 1e-3:
                        continue
                    _, ii = tree.query(ctr)
                    e = ctr - Vf[ii]
                    h = (e * nrm[ii]).sum(1)
                    tang = np.linalg.norm(e - h[:, None] * nrm[ii], axis=1)
                    ok = tang < 0.3
                    tot += int(ok.sum())
                    bb = ok & (h < -0.05)
                    below += int(bb.sum())
                    if bb.any():
                        deep = min(deep, float(h[bb].min()))
                pen["%s_t%03d" % (nm, int(round(f / 3)))] = dict(rings_below_5cm=below, rings_checked=tot, deepest_m=round(deep, 3))
            mask = zb > 0
            kv, ksky, kcl = 0, 0, 0
            for c in lay["claws"]:
                if kind(c["id"]) != "K":
                    continue
                Pp = np.asarray(X[f, c["vert_offset"]:c["vert_offset"] + c["vert_count"]], np.float64)
                if np.linalg.norm(Pp - Pp[:1], axis=1).max() < 1e-3:
                    continue
                xy, z = pcam.project(Pp)
                xi = np.round(xy[:, 0]).astype(int); yi = np.round(xy[:, 1]).astype(int)
                inb = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080) & (z > 0)
                xi = np.clip(xi, 0, 1919); yi = np.clip(yi, 0, 1079)
                zs = np.where(zb[yi, xi] > 0, 1.0 / np.maximum(zb[yi, xi], 1e-12), np.inf)
                vv = inb & (z <= zs + 0.05)
                kv += int(vv.sum()); ksky += int((vv & ~mask[yi, xi]).sum()); kcl += int(vv.any())
            vis["t%03d" % int(round(f / 3))] = dict(crown_claws_with_visible_vertices=kcl, crown_visible_vertices=kv, crown_visible_vertices_in_sky=ksky)
        g["penetration"] = pen
        g["crown_painting_cam_visibility"] = vis
        geo[k] = g
        print("geo", k, round(time.time() - t0, 1), flush=True)
    out["geometry"] = geo
    # 原画の爪の t* の輪の中心と先の投影（前＝仕上げ32 修正の回 1 に対する差、表示の px）
    lb, XB = lays["before"]
    for k in ("build", "fix"):
        la_, XA = lays[k]
        ida = {c["id"]: c for c in la_["claws"]}
        dmax, dlist = 0.0, []
        for cb in lb["claws"]:
            ca = ida.get(cb["id"])
            if ca is None:
                continue
            for X_, c_ in ((XB, cb), (XA, ca)):
                pass
            rb = rings_of(XB, cb, KS).mean(1); ra = rings_of(XA, ca, KS).mean(1)
            tb_ = np.asarray(XB[KS, cb["vert_offset"] + 1 + cb["stations"] * RING], np.float64)
            ta_ = np.asarray(XA[KS, ca["vert_offset"] + 1 + ca["stations"] * RING], np.float64)
            pb, _ = pcam.project(np.vstack([rb, tb_[None]])); pa, _ = pcam.project(np.vstack([ra, ta_[None]]))
            dd = float(np.linalg.norm(pa - pb, axis=1).max())
            dlist.append(dd)
        out.setdefault("C_tstar_centre_tip_projection_shift_px", {})[k] = dict(max=round(max(dlist), 4), p99=round(float(np.percentile(dlist, 99)), 4))
    # 冠の爪の根元と T_white
    lay, X = lays["fix"]
    cm = json.load(open(CLAWS["fix"] + "/pl33_crown.json", encoding="utf-8"))["crowns"]
    Ks = [c for c in lay["claws"] if kind(c["id"]) == "K"]
    X0 = hero.world(0.0)
    R, C = X0.shape[:2]
    tw = np.fromfile(KC.HERO + "/ds27_twhite_r32f.bin", dtype="<f4").reshape(R, C).astype(np.float64)
    dmax = 0.0
    for f in list(range(0, lay["frames"], 15)) + [KS]:
        Xs = hero.world(tau_of(f))
        for c, m_ in zip(Ks, cm):
            dmax = max(dmax, float(np.linalg.norm(np.asarray(X[f, c["vert_offset"]], np.float64) - Xs[m_["r"], m_["c"]])))
    early = 0
    for c, m_ in zip(Ks, cm):
        A = np.asarray(X[:, c["vert_offset"]:c["vert_offset"] + c["vert_count"]], np.float64)
        on = np.nonzero(np.linalg.norm(A - A[:, :1], axis=2).max(1) > 1e-3)[0]
        if len(on) and tau_of(int(on[0])) < float(tw[m_["r"], m_["c"]]) - 1.0 / 30:
            early += 1
    out["crown_fix"] = dict(root_to_sheet_vertex_max_m=dmax, born_before_root_white=early, crowns=len(Ks))
    # ---- 稜の縁取り（後ろ 65° と回り台 12 方位、t*）
    o = hero.origin(0.0)
    cams = KC.view_cams(spec, o)
    c0 = o + np.array([0, 9, 0]); pc = np.array([0.0, 3.0, -62.0]) - c0
    az0 = np.arctan2(pc[2], pc[0]); el = np.radians(16.0)
    for azd in range(0, 360, 30):
        az = az0 + np.radians(azd)
        eye = c0 + 72 * np.array([np.cos(el) * np.cos(az), np.sin(el), np.cos(el) * np.sin(az)])
        cams["tt%03d" % azd] = U.look_cam(spec, eye, c0, 34.0, 1920, 1080)
    Tg = U.K.grid_tris(R, C, b0, b1)
    Vf = X0.reshape(-1, 3)
    ring_cov = {}
    pts = {}
    for k, (lay_, X_) in lays.items():
        sel = []
        for c in lay_["claws"]:
            if kind(c["id"]) in ("C", "K"):
                sel.append(np.asarray(X_[KS, c["vert_offset"] + 1:c["vert_offset"] + 1 + c["stations"] * RING], np.float64))
        pts[k] = np.concatenate(sel)
    for nm, cm_ in cams.items():
        if nm in ("tt060", "tt090", "tt120", "tt150", "tt180", "tt210", "tt240", "tt270", "tt300") and nm not in cams:
            continue
        idb, zb = U.raster(cm_, Vf[Tg], np.arange(1, len(Tg) + 1))
        m = idb > 0
        up = np.zeros_like(m); up[3:] = m[:-3]
        top = m & ~up
        ys, xs = np.nonzero(top)
        e = {"top_silhouette_px": int(len(xs))}
        for k, Pp in pts.items():
            xy, z = cm_.project(Pp)
            xi = np.round(xy[:, 0]).astype(int); yi = np.round(xy[:, 1]).astype(int)
            inb = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080) & (z > 0)
            xi_ = np.clip(xi, 0, 1919); yi_ = np.clip(yi, 0, 1079)
            zs = np.where(zb[yi_, xi_] > 0, 1.0 / np.maximum(zb[yi_, xi_], 1e-12), np.inf)
            vv = inb & (z <= zs + 0.05)
            if vv.sum() == 0 or len(xs) == 0:
                e[k] = 0.0
                continue
            d, _ = cKDTree(np.stack([xi[vv], yi[vv]], 1)).query(np.stack([xs, ys], 1))
            e[k] = round(float((d <= 15).mean()), 4)
        ring_cov[nm] = e
    out["ridge_ringed_fraction_tstar"] = ring_cov
    out["elapsed_s"] = round(time.time() - t0, 1)
    json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F_MEASURE_DONE", out["elapsed_s"])


if __name__ == "__main__":
    main()
