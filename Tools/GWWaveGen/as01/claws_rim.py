# -*- coding: utf-8 -*-
"""美術の見本01 爪の部 区域 1（頂と唇）：唇の縁と外の巻きの面に、段に重なる彫刻のような立体の白い爪（numpy）。

as01_claw_rows（名前の付いた美術の誘導。v11 で作り直した。v10 までの写しは Build/Polish/sample01/claws/code_v10）：
  - 断面ごと（シートの行 r）に唇の先の列 c_tip(r)（頂より前で、波の進む向き Tdir に最も出る列。行の向きに σ 3 で均す）を求め、
    爪の根元を列（c_tip − dc）に、面の上で等間隔（3D の弧長で gap m おき、列ごとに半分ずらす）に置く。列と行の範囲：
      L0 唇の櫛（dc 2、行 64〜206、gap 1.5 m）：彫刻の唇の縁の櫛。1 本ずつの太い指（根元の半径 0.17 × 長さ、根元は面から盛り上がる）が、
         巻きを唇の先の外へ続けて伸び、先が下へ巻く。白の向きは巻きの外と前の観客（座席と原画のカメラ）の向きの間（as01_white_to_front）。
         b区域（行 128 まで）は短い。
      L1 唇の上の段（dc 16、行 130〜206）：原画の「途中」の爪（一覧の c − c_tip の中央値 −6）。L0 に重なる 2 段目。
      R1 爪の輪（dc 50、行 96〜182）：原画の「上側」の爪（同じく中央値 −50）。白い頂の塊の縁から巻きの向き（唇の先の向き）へ面に沿って垂れる。
         原画のカメラからは藍の舌の頂を縁取る爪の輪、横から見ると彫刻の前の面に垂れる白い指の房。
      R2・R3 上の段（dc 66・82）：R1 の上（頂の側）に重ねる、短い爪（原画の頂の泡の爪の段、彫刻の頂の指の房）。
    c_tip − 45 〜 c_tip − 20 の帯（原画の藍の舌の所）には置かない。
  - 爪 1 つ（as01_claw_hand）：平たく幅の広い掌（幅 wk × 長さ、厚さ tk × 幅）が面から盛り上がって巻きの向きへ面に沿って伸び、
    その先で NF 本の指が掌の幅に並んで出て、少し扇に開き（spread）、先が面の側（−n）へ巻く（th 度）。
    原画の爪（幅のある泡の舌の先が、同じ向きに巻く指先の束に分かれる）と、彫刻の頂の指の房（太い塊の先が巻いた指に分かれる）の両方の読み。
    v10 の脇の鉤（_t）・一つずつ散らばる小さな巻き（知られた原因 (2)）はやめた。
  - 向きは、断面の接線 e1（唇の先へ向かう ∂P/∂c）を面の法線 n へ kappa だけ起こした向き。原画の射線は使わない（座席の箒を作らない、原因 (4)）。
    唇の曲がりで e1 が行ごとに回るので、櫛は自然に外へ開く。
  - 面から半径だけ離れない時は、向きを法線へ 0.3 ずつ起こし（3 回まで）、それでも無理なら長さを 0.8 倍にする。
  - 列の端（rows の両端から fade 行）では長さを 0.5 倍まで細らせ、0.55 倍より短い所には置かない。
  - as01_claw_shadow（v12）：L1・R1〜R3 の爪ごとに、爪の下の面に寝る水色の版の膜（id W…。縁の線なし。幅 SHADOW × 掌の幅、長さ SHADOW_L × 爪の長さ）。
    白の地の上で、爪が浮き彫りの判ではなく面から立つ塊に読めるように（原画の泡の爪の下の水色の陰でもある）。
  - as01_paint_silhouette（v13）：原画のカメラから見て、指・掌が原画の空（原画の爪の形を含む輪郭の外）へ SKY_TOL 画素より深く出る時は、
    長さを 0.85 倍ずつ（4 回まで）縮め、太さも少し細くする（原画視点で唇と頂の上に大きな出っ張りができた。v12b の 17,387 画素 → 9,919 画素）。
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter1d

TDIR = np.array([0.7333652004044829, 0.0, -0.6798348938056156])
SEAT = np.array([3.9544, 1.8323, -15.0308])     # 座席の目の位置（claws_common.VIEWS["seat"]、仕上げ33修正01 の t* の値）
PAINT = np.array([0.0, 3.0, -62.0])             # 原画のカメラの位置（PaintingCam v1）

_F = dict(fade=8.0, stagger=0.0, side=0.60, flare=0.40, b_scale=1.0, kappa=0.70, th_palm=10.0, pl=0.18, wk=0.40, tk=0.55, nf=3,
          spread=32.0, f_off=0.15, rfk=0.30, th=220.0, flk=1.0, rk=0.17, c_side=0.5)


def _fam(**kw):
    d = dict(_F)
    d.update(kw)
    return d


RIM = dict(R0=64, R1=226,
           FAM=(_fam(name="L0", dc=2, rows=(64, 206), fade=6.0, gap=1.5, L=(2.6, 3.6), kappa=0.40, th=200.0, side=0.35, nf=1, rk=0.17,
                     flare=0.45, b_scale=0.55),
                _fam(name="L1", dc=16, rows=(130, 206), gap=2.2, L=(2.5, 3.1), stagger=0.5, kappa=0.25, th=210.0, spread=20.0),
                _fam(name="R1", dc=50, rows=(96, 182), gap=1.8, L=(3.0, 3.8), stagger=0.25, rfk=0.34),
                _fam(name="R2", dc=66, rows=(108, 182), gap=1.9, L=(2.6, 3.2), stagger=0.75, rfk=0.34),
                _fam(name="R3", dc=82, rows=(120, 182), gap=2.0, L=(2.2, 2.8), stagger=0.25, rfk=0.34)),
           ST_PALM=6, ST=12, LK=(1.0, 0.72, 0.86), THK=(0.92, 1.0, 0.96), R_TIP=0.20, CAP=0.88, CLEAR=0.85, P_CURL=1.9,
           B_ROW=128, FLARE_S=0.30, DISC=0.9, FAN_J=0.15, SIDE_LEN=0.70, WHITE_SEAT=1.0, SHADOW=1.2, SHADOW_L=0.60, SKY_TOL=12)


def c_tip_rows(hero):
    X = hero.X
    R = hero.R
    b0, b1 = hero.b0, hero.b1
    ct = np.zeros(R)
    for r in range(R):
        prof = X[r]
        cy = int(np.argmax(prof[b0:b1 + 1, 1])) + b0
        fw = prof @ TDIR
        hi = min(300, b1)
        ct[r] = cy + int(np.argmax(fw[cy:hi]))
    return gaussian_filter1d(ct, 3.0, mode="nearest")


class PaintSky:
    """as01_paint_silhouette：原画のカメラから見て、爪が原画の空（Tools/PaintingTruth/targets/masks/sky_claws_cov.png。原画の爪の形も空でない側）へ
    TOL 画素より深く出ないことの検査（原画のカメラは検査にだけ使う。色は投影しない）。背骨の点と、そこから管の半径だけ画面の上下左右へずらした点を見る。"""

    def __init__(self, CC, tol):
        import cv2
        m = cv2.imread(CC.REPO + "/Tools/PaintingTruth/targets/masks/sky_claws_cov.png", cv2.IMREAD_UNCHANGED).astype(np.float64) / 65535.0 > 0.5
        self.sky = cv2.erode(m.astype(np.uint8), np.ones((2 * tol + 1, 2 * tol + 1), np.uint8)) > 0 if tol > 0 else m
        self.cam = CC.painting_cam()

    def count(self, sp_, rad):
        c = self.cam
        pr = np.concatenate([sp_] + [sp_ + rad[:, None] * o[None, :] for o in (c.u, -c.u, c.r, -c.r)])
        q, z = c.project(pr)
        x = np.round(q[:, 0]).astype(int)
        y = np.round(q[:, 1]).astype(int)
        ok = (z > 0) & (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080)
        return int(self.sky[y[ok], x[ok]].sum())


def _spine(B, hero, P0, D0, C0, n, L, th, st, p_curl, rad_fn, clear, sky=None):
    """背骨（spine_curl）。面から半径だけ離れない時は D0 を法線へ 0.3 ずつ起こす（3 回まで）、それでも無理なら 0.8 倍の長さ。
    sky（PaintSky）があれば、原画の空へ出る点が 0 になるまで長さを 0.85 倍ずつ縮める（4 回まで。as01_paint_silhouette）。"""
    best = None
    for lk in ((1.0, 0.85, 0.72, 0.61, 0.52) if sky is not None else (1.0,)):
        for tr in range(5):
            D = B.unit(D0 + 0.3 * min(tr, 3) * n)
            C = C0 - (C0 @ D) * D
            C = B.unit(C)
            Lk = L * lk * (0.8 if tr == 4 else 1.0)
            sp_ = B.spine_curl(P0, D, C, Lk, th, st, p=p_curl)
            rad = rad_fn(st) * (0.5 + 0.5 * lk)
            h = hero.height(sp_)
            marg = float((h[2:] - clear * rad[2:]).min())
            v = sky.count(sp_, rad) if sky is not None else 0
            key = (-v, min(marg, 0.0), lk)
            if best is None or key > best[0]:
                best = (key, (marg, sp_, rad, Lk, tr))
            if marg > 0 and v == 0:
                return (marg, sp_, rad, Lk, tr)
    return best[1]


def _nref_curl(B, sp_, n, k_up):
    T = np.gradient(sp_, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    kv = np.gradient(T, axis=0)
    out = -kv / np.maximum(np.linalg.norm(kv, axis=1, keepdims=True), 1e-9)
    return B.unit_rows(out + k_up * n[None, :])


def make_rim(hero, B, log, fams=None):
    """B は claws_build（spine_curl・radius_profile・build_entry・unit・jit・unit_rows・rot を使う）。fams は使う列の名前（None なら全部）。"""
    ents = []
    ct = c_tip_rows(hero)
    sky = PaintSky(B.CC, RIM["SKY_TOL"]) if RIM["SKY_TOL"] >= 0 else None
    for fam in RIM["FAM"]:
        if fams is not None and fam["name"] not in fams:
            continue
        r_lo, r_hi = fam["rows"]
        rows = np.arange(r_lo, r_hi + 1)
        cc = ct[rows] - fam["dc"]
        Pts = np.array([hero.point(np.array(float(r)), np.array(float(c))) for r, c in zip(rows, cc)])
        s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pts, axis=0), axis=1))]
        gap = fam["gap"]
        hpos = np.arange((fam["stagger"] + 0.5) * gap, s[-1] - 0.3 * gap, gap)
        for k, sp in enumerate(hpos):
            r = float(np.interp(sp, s, rows))
            c = float(np.interp(sp, s, cc))
            eid = "%s_%03d" % (fam["name"], k)
            Fr = hero.frame(np.array(r), np.array(c))
            e1, e2, n = Fr[0], Fr[1], Fr[2]
            P0 = hero.point(np.array(r), np.array(c))
            a, b = fam["L"]
            L = (a + (b - a) * (0.5 + 0.35 * math.sin(k * 2.1) + 0.15 * B.jit(eid, 1))) * RIM["LK"][k % 3]
            edge = min(B.CC.sm((r - r_lo) / fam["fade"]), B.CC.sm((r_hi - r) / fam["fade"]))
            fl = 0.5 + 0.5 * edge
            if fl < 0.55:
                continue
            L *= fl
            if fam["b_scale"] < 1.0:
                L *= fam["b_scale"] + (1 - fam["b_scale"]) * B.CC.sm((r - RIM["R0"]) / (RIM["B_ROW"] - RIM["R0"]))
            fan0 = 0.08 * math.sin(k * 1.3) + B.jit(eid, 2, RIM["FAN_J"])
            C0 = fam["side"] * (-e2) + math.sqrt(max(0.0, 1 - fam["side"] ** 2)) * (-n)
            if fam["nf"] == 1:
                # 1 本の指（彫刻の唇の櫛）：根元が面から盛り上がり（flare）、巻きの向きへ伸び、先が下へ巻く
                r0 = fam["rk"] * L
                D0 = B.unit(e1 + fam["kappa"] * n + fan0 * e2)

                def rad_one(st, r0=r0):
                    s_ = np.linspace(0, 1, st + 1)
                    return B.radius_profile(st, r0, RIM["R_TIP"] * r0, cap=RIM["CAP"]) * (1 + fam["flare"] * np.clip(1 - s_ / RIM["FLARE_S"], 0, 1) ** 2)
                thf = fam["th"] * RIM["THK"][k % 3] * (1 + B.jit(eid, 3, 0.08))
                m1, sp1, rad1, L1k, tr1 = _spine(B, hero, P0 - 0.25 * r0 * n, D0, C0, n, L, thf, RIM["ST"], RIM["P_CURL"], rad_one, RIM["CLEAR"], sky)
                disc = (P0 + 0.03 * n, n, RIM["DISC"] * r0 * (1 + fam["flare"]))
                # 白の向き：巻きの外と、前の観客（座席と原画のカメラの向きの平均）へ向かう向きの間（as01_white_to_front）。
                # 下から見上げる座席・前から見る原画のカメラで、腹の水色ばかりにならないように（彫刻の指は白い）
                vs = B.unit_rows(B.unit_rows(SEAT[None, :] - sp1) + B.unit_rows(PAINT[None, :] - sp1))
                nr1 = B.unit_rows(0.6 * _nref_curl(B, sp1, n, 0.4) + RIM["WHITE_SEAT"] * vs)
                ents.append(B.build_entry(eid, sp1, nr1, rad1, rad1 * 0.92, B.CC.Q_FINGER, "rim", root_disc=disc))
                log.append(dict(id=eid, fam=fam["name"], rc=[round(r, 2), round(c, 2)], L=round(float(L1k), 3), r0=round(r0, 3), clear=round(m1, 3),
                                lift_steps=int(tr1)))
                continue
            # 掌：平たく幅の広い管（幅 w、厚さ tk·w）。白の向きは面の法線
            w = fam["wk"] * L
            Lp = fam["pl"] * L
            D0 = B.unit(e1 + fam["kappa"] * n + fan0 * e2)
            st_p = RIM["ST_PALM"]

            def rad_palm(st, w=w):
                s_ = np.linspace(0, 1, st + 1)
                rr = 0.5 * w * (0.80 + 0.20 * np.sin(np.pi * np.clip(s_ * 0.8 + 0.2, 0, 1)))
                return rr * (1 + fam["flare"] * np.clip(1 - s_ / RIM["FLARE_S"], 0, 1) ** 2)
            mp, spp, radp, Lpk, trp = _spine(B, hero, P0 - 0.2 * fam["tk"] * w * n, D0, C0, n, Lp, fam["th_palm"], st_p, 1.0, rad_palm,
                                            RIM["CLEAR"] * fam["tk"], sky)
            nref_p = np.repeat(n[None, :], st_p + 1, 0)
            disc = (P0 + 0.03 * n, n, RIM["DISC"] * 0.5 * w * (1 + fam["flare"]))
            ents.append(B.build_entry(eid + "_p", spp, nref_p, radp, radp * fam["tk"], B.CC.Q_SHEET, "rim", root_disc=disc))
            # 指：掌の先の幅に並んで出て、少し扇に開き、先が面の側へ巻く
            Tb = B.unit(spp[-1] - spp[-2])
            side = e2 - (e2 @ Tb) * Tb
            side = B.unit(side)
            ax = B.unit(np.cross(Tb, side))
            nf = fam["nf"]
            u = np.linspace(-1.0, 1.0, nf)
            fl_ = []
            for j, uj in enumerate(u):
                fid = "%s_f%d" % (eid, j)
                fa = uj * fam["spread"] + B.jit(fid, 4, 4.0)
                Dk = B.rot(Tb, ax, math.radians(fa))
                mid = 1.0 - (1.0 - RIM["SIDE_LEN"]) * abs(uj)
                Lf = (L - Lpk) * fam["flk"] * mid * (1 + B.jit(fid, 5, 0.10))
                rf = fam["rfk"] * w * (1.0 - 0.12 * abs(uj))
                Ck = B.unit(C0 + fam["c_side"] * uj * side)
                thf = fam["th"] * RIM["THK"][(j + k) % 3] * (1 + B.jit(fid, 3, 0.07))
                st0 = spp[-1] - 0.6 * rf * Tb + uj * fam["f_off"] * 0.5 * w * side

                def rad_f(st, rf=rf):
                    return B.radius_profile(st, rf, RIM["R_TIP"] * rf, cap=RIM["CAP"])
                mf, spf, radf, Lfk, trf = _spine(B, hero, st0, Dk, Ck, n, Lf, thf, RIM["ST"], RIM["P_CURL"], rad_f, RIM["CLEAR"], sky)
                ents.append(B.build_entry(fid, spf, _nref_curl(B, spf, n, 0.4), radf, radf * 0.92, B.CC.Q_FINGER, "rim"))
                fl_.append(dict(L=round(float(Lfk), 3), rf=round(float(rf), 3), clear=round(mf, 3), lift_steps=int(trf)))
            if RIM["SHADOW"] > 0:
                # as01_claw_shadow：爪の下の面に寝る水色の版の膜（id W…。PL33ClawLook が全部を水色の版にし、縁の線を出さない）。
                # 白の地の上で、爪が浮き彫りの判（デカール）ではなく面から立つ塊に読めるように。原画の泡の爪の下の水色の陰でもある
                t0 = e1 + fan0 * e2
                t0 = B.unit(t0 - (t0 @ n) * n)
                ls = RIM["SHADOW_L"] * L
                pw, nw, _ = B.walk_on_sheet(hero, r, c, t0, 1.0, ls, 8, 0.0, 1.0)
                m = len(pw) - 1
                sw_ = np.linspace(0, 1, m + 1)
                rw = 0.5 * RIM["SHADOW"] * w * np.sin(np.pi * (0.12 + 0.88 * sw_)) ** 0.6
                rw = np.maximum(rw, 0.03)
                ents.append(B.build_entry("W" + eid, pw + nw * (B.P["WEB_T"] * 0.5 + 0.02), nw, rw, np.full(m + 1, 0.5 * B.P["WEB_T"]),
                                          B.CC.Q_SHEET, "rim_shadow", web=True))
            log.append(dict(id=eid, fam=fam["name"], rc=[round(r, 2), round(c, 2)], L=round(L, 3), palm_L=round(float(Lpk), 3), palm_w=round(w, 3),
                            clear_palm=round(mp, 3), fingers=fl_))
    return ents
