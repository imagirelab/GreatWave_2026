# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 2：鉤の内の膜（W）と b区域の房の添え指（S）を、t 10 s〜t* のどのコマでも白の範囲の内に収める（pl33f2_white_clip。numpy）。

自己評審（修正の回 1 の再評審）の指摘：原画視点の t* と t 10.5 s で、b区域の頂から輪郭を越えて藍の中へ垂れる淡い水色の細片が出た。
  出どころは WC223（C223 の b区域の膜 × 3.0）と SC223m、t 10.5 s では WC224 も。修正の回 1 の膜の検査は t* の「主役波の外（空）」だけ、
  添え指の検査は t* の 3D の白の範囲だけ（弧長は最小 0.4 倍まで）だったので、藍の上へ出る輪と、t* より前のコマが抜けていた。

名前の付いた美術の誘導（形だけを決める検査。色は作らない。原画カメラからの投影の色は使わない：Q28）：
  - pl33f2_white_clip：t 10.0〜12.0 s の 0.1 s おき（コマ 300〜360 の 3 コマおき、21 コマ）のどのコマでも、膜の輪の外の縁と中ほどの点、
    添え指の輪の 8 頂点と先が、次の 3 つを満たすように縮める。
      (1) 3D の白の範囲：そのコマの主役波のシートで一番近い頂点が白の範囲（pl31_zone_vertex）で白になる時刻 T_white を過ぎている、
          またはそういう頂点まで TOL3D（0.3 m）の内（視点によらない。白の範囲の縁の頂点の並びのぎざぎざの許し）。
      (2) 空の検査：原画のカメラから見える点（そのコマの主役波の z バッファより 10 cm より奥でない）は、主役波の中（5×5 がどれも主役波の画素）。
      (3) 藍の検査：原画のカメラから見える点は、爪なしの原画視点の描画（PL33Render、同じコマ）の暗い所（明るさ < 110 を 5×5 で 1 回削った所。細い線と縁の 2 px の触れは問わない）に載らない。
    膜は輪ごとの幅の倍率（1, 0.7, 0.49 … 0）、添え指は弧長の倍率（1, 0.85, 0.72 … 0.23, 0）の候補のうち、そのコマで、それ以下の候補がどれも
    満たす一番大きいものを「許し」とする。
  - pl33f2_grow_schedule（倍率の時刻の決め方。既定 --mode grow）：コマ f の倍率は「f より後の検査のコマの許しの最小」（時刻とともに増えるだけ）を
    検査のコマの間で線で結び、1 コマに RATE（0.05）より速く増やさない。t 10 s より前は t 10 s の値、t* より後は t* の値。
    t 10 s の頃だけ藍の上に出る添え指は、そこでは根元に潰れ、白の範囲に入ってから伸びる（--mode const は全コマ同じ倍率＝全部の検査のコマの最小。比べの案）。
    膜は同じコマの隣の輪の倍率との小さい方にそろえる。添え指の倍率 0 は輪と先を根元へ潰す。添え指の根元の円は倍率 CIRC_S（0.3）までに 0 から開く
    （潰れていた指が伸び始める時に円が一度に開く跳びを防ぐ）。原画の爪（C…）・冠の爪（K…）は変えない。
  - pl33f2_web_floor（試し、採らない。--web-floor で使う）：膜の候補の倍率は、輪の中ほどが主役波の面より 5 cm より下に入らないことも満たす（検査の 21 コマと、t 9.0〜9.8 s の 6 コマおきの 5 コマ。
    膜は縁 P1（帯の縁より 3 cm 下）へ向けて縮むので、縮めた輪が面の下へ入るのを防ぐ。計画の 262）。面の下の輪の数（t 9・10.5・12 s）は
    変わらず（倍率 0 でも帯の縁が面の下にある輪のため）、縮める膜が 3 本増えただけだったので採らない。
  - pl33f2_tuft_web_wide（試し、採らない。既定 --web-b-max 1.0 で使わない）：b区域の膜の候補に 1 より大きい倍率（横の成分だけを伸ばす、
    面より 2 cm より下に入らない）を足す。
  (2)(3) は原画のカメラで形の範囲を決める検査で、色は作らない（修正の回 1 の pl33_common.TStarDepth・pl33f_crown_hidden_t と同じ扱い）。

入力（Git 対象外）：--src（修正の回 1 の爪の並び。既定 Unity/Build/Polish/33/fix01/claws）、--masks（爪なしの原画視点の描画。既定 Unity/Build/Polish/33/fix02/seq_fix01/views）。
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/fix02/claws）と pl33f2_clip_report.json。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl33/pl33f2_clip.py
"""
import argparse
import json
import os
import shutil
import sys
import time

import cv2
import numpy as np
from PIL import Image
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_common as Q  # noqa: E402
from pl33f_relief import taus_of  # noqa: E402

U = Q.U
SRC = REPO + "/Unity/Build/Polish/33/fix01/claws"
MASKS = REPO + "/Unity/Build/Polish/33/fix02/seq_fix01/views"
OUT = REPO + "/Unity/Build/Polish/33/fix02/claws"
RING = 8
CHECK = [(300 + 3 * k, 100 + k) for k in range(21)]            # (コマ, 描画の名前の t×10)
FLOOR_PRE = [(270 + 6 * k, None) for k in range(5)]              # t 9.0〜9.8 s：膜の床の検査だけのコマ（倍率が t 10 s の値のまま前へ続くため）
WEB_FLOOR = -0.05
W_SCALES = [1.0, 0.7, 0.49, 0.343, 0.24, 0.168, 0.118, 0.0]
S_SCALES = [1.0, 0.85, 0.72, 0.61, 0.52, 0.44, 0.37, 0.32, 0.27, 0.23, 0.0]
VIS_TOL = 0.10
DARK = 110
ERODE = 5
TOL3D = 0.3
RATE = 0.05
CIRC_S = 0.3
WEB_B_MAX = 1.0


def web_lat(R):
    """膜の輪 (..., 8, 3) の、縁 P1（頂点 4）から外の縁 P2（頂点 0）への向きのうち、膜の法線（頂点 2 − 6）に垂直な横の成分。"""
    nn = R[..., 2, :] - R[..., 6, :]
    nn = nn / np.maximum(np.linalg.norm(nn, axis=-1, keepdims=True), 1e-12)
    d = R[..., 0, :] - R[..., 4, :]
    return d - (d * nn).sum(-1, keepdims=True) * nn


def web_far(R, s):
    """倍率 s の外の縁：s ≤ 1 は縁 P1 へ向けて縮め（pl33f2_white_clip）、s > 1 は横の成分だけを伸ばす（pl33f2_tuft_web_wide。下げは変えない）。"""
    P1, P2 = R[..., 4, :], R[..., 0, :]
    if s <= 1.0:
        return P1 + s * (P2 - P1)
    return P2 + (s - 1.0) * web_lat(R)


def web_scale_rings(R, sc):
    """R：(F, st, 8, 3)、sc：(F, st) → 倍率をかけた輪。"""
    P1 = R[:, :, 4:5]
    shrink = P1 + np.minimum(sc, 1.0)[:, :, None, None] * (R - P1)
    ext = np.maximum(sc - 1.0, 0.0)
    if (ext > 0).any():
        lat = web_lat(R)
        cphi = np.cos(2 * np.pi * np.arange(RING) / RING)
        w = 0.5 * (1.0 + cphi)                                   # 頂点 0 で 1、頂点 4 で 0（楕円の輪を横へ伸ばす）
        shrink = shrink + ext[:, :, None, None] * w[None, None, :, None] * lat[:, :, None, :]
    return shrink


def interp_poly(Pp, cum, u):
    k = np.clip(np.searchsorted(cum, u, side="right") - 1, 0, len(cum) - 2)
    seg = np.maximum(cum[k + 1] - cum[k], 1e-12)
    w = np.clip((u - cum[k]) / seg, 0.0, 1.0)
    return Pp[k] + w[..., None] * (Pp[k + 1] - Pp[k]), k, w


def finger_at(Xf, o, st, s):
    """添え指（または帯）を自分の中心線に沿って弧長 s 倍にした輪 (st,8,3) と先 (3,)。"""
    root = Xf[o]
    R = Xf[o + 1:o + 1 + st * RING].reshape(st, RING, 3)
    tip = Xf[o + 1 + st * RING]
    ctr = R.mean(1)
    Pp = np.concatenate([root[None], ctr, tip[None]], 0)
    cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
    if s >= 0.999:
        return R.copy(), tip.copy(), cum[-1]
    u = s * cum
    pts, k, w = interp_poly(Pp, cum, u)
    Rx = np.concatenate([R[:1], R, R[-1:]], 0)
    cx = np.concatenate([root[None], ctr, tip[None]], 0)
    shape = (1 - w)[:, None, None] * (Rx[k] - cx[k][:, None, :]) + w[:, None, None] * (Rx[k + 1] - cx[k + 1][:, None, :])
    rings = pts[1:st + 1, None, :] + shape[1:st + 1]
    return rings, pts[-1], cum[-1]


class Frame:
    def __init__(self, hero, zone, tw, tau, mask_path, erode=5, tol3d=0.0):
        Xs = hero.world(float(tau))
        self.dep = Q.TStarDepth(Xs)
        self.tree = cKDTree(Xs.reshape(-1, 3))
        self.V = Xs.reshape(-1, 3)
        dr = np.gradient(Xs, axis=0); dc = np.gradient(Xs, axis=1)
        nrm = np.cross(dr, dc)
        self.nrm = (nrm / np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)).reshape(-1, 3)
        self.white3d = zone & (tw <= tau + 1e-9)
        self.tol3d = tol3d
        if tol3d > 0:
            self.wtree = cKDTree(Xs.reshape(-1, 3)[self.white3d])
        if mask_path is None:
            self.dark = None
            return
        cf = np.asarray(Image.open(mask_path).convert("RGB")).astype(np.float64)
        dark = (cf.mean(-1) < DARK).astype(np.uint8)
        self.dark = cv2.erode(dark, np.ones((erode, erode), np.uint8)) > 0

    def above(self, P, floor=-0.02):
        """面より floor（m）より下に入らない（近い頂点の法線の高さ。横に 0.3 m より離れた点は問わない）。"""
        sh = P.shape[:-1]
        P = P.reshape(-1, 3)
        _, ii = self.tree.query(P)
        e = P - self.V[ii]
        h = (e * self.nrm[ii]).sum(1)
        tang = np.linalg.norm(e - h[:, None] * self.nrm[ii], axis=1)
        return (~((h < floor) & (tang < 0.3))).reshape(sh)

    def ok(self, P, use3d=True, usepaint=True):
        """P：(..., 3) → (...,) bool。"""
        sh = P.shape[:-1]
        P = P.reshape(-1, 3)
        good = np.ones(len(P), bool)
        if use3d:
            _, ii = self.tree.query(P)
            w3 = self.white3d[ii]
            if self.tol3d > 0 and (~w3).any():
                dw, _ = self.wtree.query(P[~w3])
                w3[~w3] = dw <= self.tol3d
            good &= w3
        if usepaint:
            d = self.dep
            xy, z, xi, yi, inb = d.look(P)
            zs = np.where(d.zb[yi, xi] > 0, 1.0 / np.maximum(d.zb[yi, xi], 1e-9), np.inf)
            vis = inb & np.isfinite(z) & (z > 0) & (z <= zs + VIS_TOL)
            bad = vis & (~(d.zfar[yi, xi] > 0) | self.dark[yi, xi])
            good &= ~bad
        return good.reshape(sh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--masks", default=MASKS)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-3d", action="store_true", help="(1) の 3D の白の範囲の検査を使わない（比べのため）")
    ap.add_argument("--dry", action="store_true", help="倍率を数えるだけで書き出さない")
    ap.add_argument("--web-floor", action="store_true", help="pl33f2_web_floor を使う（試し、採らない）")
    ap.add_argument("--web-b-max", type=float, default=WEB_B_MAX, help="b区域の膜の横の広げの上限（1 で広げない）")
    ap.add_argument("--mode", choices=("grow", "const"), default="grow", help="grow：時刻とともに増えるだけの倍率（既定）、const：全コマ同じ倍率")
    ap.add_argument("--erode", type=int, default=ERODE, help="藍の検査の暗い所を削る大きさ（px の正方形）")
    ap.add_argument("--tol3d", type=float, default=TOL3D, help="(1) の許し：白の範囲の頂点までこの距離（m）の内なら白とみなす。0 は一番近い頂点だけ")
    a = ap.parse_args()
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    fr_path = os.path.join(a.src, lay["files"]["frames"]["file"])
    X = np.fromfile(fr_path, dtype=np.float32).reshape(F, V, 3)
    taus = taus_of(F)
    hero = U.K.Pkg(Q.HERO)
    zone = np.load(Q.ZONE).reshape(-1)
    tw = np.fromfile(Q.HERO + "/ds27_twhite_r32f.bin", dtype="<f4").reshape(-1).astype(np.float64)
    Ws = [c for c in lay["claws"] if c.get("type") == "W"]
    Ss = [c for c in lay["claws"] if c.get("type") == "S"]
    # 検査のコマごとに、輪（膜）・指（添え指）の倍率の候補のうち、それ以下の候補がどれも満たす一番大きいもの（単調な包絡）
    ALL = (FLOOR_PRE if a.web_floor else []) + CHECK
    nK = len(ALL)
    INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
    rowof = {c["id"]: c.get("row") for c in json.load(open(INV, encoding="utf-8"))["claws"]}
    wide = {c["id"]: (a.web_b_max > 1.0 and rowof.get(c.get("pl33_web_of", c["id"][1:])) == "b区域") for c in Ws}
    WS_B = sorted(set([v for v in np.arange(a.web_b_max, 1.0, -0.15).round(3).tolist() if v > 1.0] + W_SCALES), reverse=True)
    a_w = {c["id"]: np.ones((nK, c["stations"])) for c in Ws}
    a_s = {c["id"]: np.ones(nK) for c in Ss}
    mask_sha = {}

    def envelope(okv, scales):
        best = 0.0
        for k in range(len(scales) - 1, -1, -1):
            if not okv[k:].all():
                break
            best = scales[k]
        return best
    for ki, (f, tn) in enumerate(ALL):
        floor_only = tn is None
        if floor_only:
            fr = Frame(hero, zone, tw, taus[f], None, a.erode, a.tol3d)
        else:
            mp = os.path.join(a.masks, f"painting_t{tn:03d}_clawfree.png")
            mask_sha[os.path.basename(mp)] = Q.sha(mp)
            fr = Frame(hero, zone, tw, taus[f], mp, a.erode, a.tol3d)
        Xf = X[f].astype(np.float64)
        for c in Ws:
            o, st = c["vert_offset"], c["stations"]
            R = Xf[o + 1:o + 1 + st * RING].reshape(st, RING, 3)
            P1, P2 = R[:, 4], R[:, 0]
            if np.linalg.norm(P2 - P1, axis=1).max() < 1e-4:
                continue
            scl = WS_B if wide[c["id"]] else W_SCALES
            okm = np.ones((st, len(scl)), bool)
            for k, sv in enumerate(scl):
                P2s = web_far(R, sv)
                test = np.stack([P2s, 0.5 * (P1 + P2s)], 1)
                okm[:, k] = True if floor_only else fr.ok(test, not a.no_3d).all(1)
                if sv > 1.0:
                    okm[:, k] &= fr.above(test).all(1)
                if a.web_floor:                                          # pl33f2_web_floor（試し）：輪の中ほどが面より 5 cm より下に入らない
                    okm[:, k] &= fr.above(0.5 * (P1 + P2s), WEB_FLOOR)
            a_w[c["id"]][ki] = [envelope(okm[j], scl) for j in range(st)]
        for c in Ss:
            if floor_only:
                continue
            o, st = c["vert_offset"], c["stations"]
            okv = np.ones(len(S_SCALES), bool)
            rings, tip, L = finger_at(Xf, o, st, 1.0)
            if L < 1e-4:
                continue
            for k, sv in enumerate(S_SCALES):
                if sv == 0.0:
                    continue
                rings, tip, L = finger_at(Xf, o, st, sv)
                pts = np.concatenate([rings.reshape(-1, 3), tip[None]], 0)
                okv[k] = bool(fr.ok(pts, not a.no_3d).all())
            a_s[c["id"]][ki] = envelope(okv, S_SCALES)
        print("frame", f, round(time.time() - t0, 1), "s", flush=True)
    fk = np.array([f for f, _ in ALL], np.float64)

    def schedule(av):
        """av：(nK, …) の検査のコマの許し → (F, …) のコマごとの倍率。"""
        av = np.asarray(av, np.float64)
        if a.mode == "const":
            env = np.broadcast_to(av.min(0), av.shape)
        else:
            env = np.minimum.accumulate(av[::-1], axis=0)[::-1]          # 後のコマのどれでも満たす（時刻とともに増えるだけ）
        fr_ = np.arange(F, dtype=np.float64)
        flat = env.reshape(nK, -1)
        sc = np.stack([np.interp(fr_, fk, flat[:, j]) for j in range(flat.shape[1])], 1)
        for f in range(1, F):                                            # 増え方の上限（1 コマ RATE）
            sc[f] = np.minimum(sc[f], sc[f - 1] + RATE)
        return sc.reshape((F,) + av.shape[1:])
    w_sc = {}
    for c in Ws:
        sc = schedule(a_w[c["id"]])
        sc = np.minimum(sc, np.minimum(np.concatenate([sc[:, 1:], sc[:, -1:]], 1), np.concatenate([sc[:, :1], sc[:, :-1]], 1)))
        w_sc[c["id"]] = sc
    s_sc = {c["id"]: schedule(a_s[c["id"]]) for c in Ss}
    KS = 360
    summ = {"mode": a.mode, "rate_per_frame": RATE, "webs": len(Ws),
            "webs_changed_tstar": sum(1 for v in w_sc.values() if (v[KS] < 0.999).any()),
            "web_rings_shrunk_tstar": int(sum((v[KS] < 0.999).sum() for v in w_sc.values())),
            "webs_zero_tstar": sum(1 for v in w_sc.values() if (v[KS] < 1e-6).all()),
            "webs_changed_any_frame": sum(1 for v in w_sc.values() if (v < 0.999).any()),
            "tuft_fingers": len(Ss), "tuft_changed_tstar": sum(1 for v in s_sc.values() if v[KS] < 0.999),
            "tuft_zero_tstar": sum(1 for v in s_sc.values() if v[KS] < 1e-6),
            "tuft_zero_all_frames": sum(1 for v in s_sc.values() if (v < 1e-6).all()),
            "tuft_changed_any_frame": sum(1 for v in s_sc.values() if (v < 0.999).any()),
            "use_3d": not a.no_3d, "erode_px": a.erode, "tol3d_m": a.tol3d, "web_b_max": a.web_b_max,
            "webs_widened_tstar": sum(1 for v in w_sc.values() if (v[KS] > 1.001).any())}
    print(json.dumps(summ, ensure_ascii=False))
    for cid in ("WC223", "WC224", "SC223m", "SC223p", "SC224p", "SC224m"):
        if cid in w_sc:
            print(cid, "t10/10.5/t*", np.round(w_sc[cid][[300, 315, 360]].min(1), 3).tolist())
        if cid in s_sc:
            print(cid, "t10/10.5/t*", np.round(s_sc[cid][[300, 315, 360]], 3).tolist())
    if a.dry:
        return
    Y = X.copy()
    for c in Ws:
        sc = w_sc[c["id"]]
        if np.abs(sc - 1.0).max() < 1e-3:
            continue
        o, st = c["vert_offset"], c["stations"]
        R = Y[:, o + 1:o + 1 + st * RING].reshape(F, st, RING, 3).astype(np.float64)
        Rn = web_scale_rings(R, sc)
        Y[:, o + 1:o + 1 + st * RING] = Rn.reshape(F, st * RING, 3).astype(np.float32)
        Y[:, o + 1 + st * RING] = (0.5 * (Rn[:, -1, 0] + Rn[:, -1, 4])).astype(np.float32)
    for c in Ss:
        sv = s_sc[c["id"]]
        if (sv >= 0.999).all():
            continue
        o, st = c["vert_offset"], c["stations"]
        NV = c["vert_count"]
        for f in range(F):
            if sv[f] >= 0.999:
                continue
            Xf = X[f].astype(np.float64)
            root = Xf[o]
            # 根元の円（中心と 8 点）は倍率 CIRC_S までに 0 から広げる（指が生まれる前は根元に潰れ、伸び始めとともに開く。円が一度に開く跳びを防ぐ）
            cs = min(1.0, float(sv[f]) / CIRC_S)
            Y[f, o + 2 + st * RING:o + NV] = (root + cs * (Xf[o + 2 + st * RING:o + NV] - root)).astype(np.float32)
            if sv[f] < 1e-6:
                Y[f, o + 1:o + 2 + st * RING] = root.astype(np.float32)
                continue
            rings, tip, L = finger_at(Xf, o, st, float(sv[f]))
            if L < 1e-4:
                continue
            Y[f, o + 1:o + 1 + st * RING] = rings.reshape(-1, 3).astype(np.float32)
            Y[f, o + 1 + st * RING] = tip.astype(np.float32)
    os.makedirs(a.out, exist_ok=True)
    for k, v in lay["files"].items():
        if k != "frames":
            shutil.copyfile(os.path.join(a.src, v["file"]), os.path.join(a.out, v["file"]))
    for extra in ("pl33_crown.json",):
        if os.path.exists(os.path.join(a.src, extra)):
            shutil.copyfile(os.path.join(a.src, extra), os.path.join(a.out, extra))
    out_fr = os.path.join(a.out, lay["files"]["frames"]["file"])
    Y.tofile(out_fr)
    lay["files"]["frames"]["sha256"] = Q.sha(out_fr)
    lay["files"]["frames"]["bytes"] = os.path.getsize(out_fr)
    lay["pl33f2_clip"] = {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33/pl33f2_clip.py",
                          "src": os.path.relpath(a.src, REPO).replace("\\", "/"), "src_frames_sha256": Q.sha(fr_path),
                          "masks": os.path.relpath(a.masks, REPO).replace("\\", "/"), "check_frames": [f for f, _ in CHECK], "web_floor_frames": [f for f, _ in ALL], "web_floor_m": WEB_FLOOR,
                          "w_scales": W_SCALES, "s_scales": S_SCALES, "vis_tol_m": VIS_TOL, "dark_lum": DARK, **summ}
    np.save(os.path.join(a.out, "pl33f2_web_scale.npy"), np.concatenate([w_sc[c["id"]] for c in Ws], 1).astype(np.float32))
    np.save(os.path.join(a.out, "pl33f2_tuft_scale.npy"), np.stack([s_sc[c["id"]] for c in Ss], 1).astype(np.float32))
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    rep = {"summary": summ, "mask_sha256": mask_sha,
           "web_scale_t10_t105_tstar": {k: np.round(v[[300, 315, 360]], 3).tolist() for k, v in w_sc.items() if (v < 0.999).any()},
           "tuft_scale_t10_t105_tstar": {k: np.round(v[[300, 315, 360]], 3).tolist() for k, v in s_sc.items() if (v < 0.999).any()},
           "elapsed_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(a.out, "pl33f2_clip_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F2_CLIP_DONE", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
