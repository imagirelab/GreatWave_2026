# -*- coding: utf-8 -*-
"""仕上げ33 修正の回 1：b区域の爪を房（5〜10 本の指の束）として読めるようにする「房の添え指」（pl33f_tuft_fingers）。numpy。

［利用者の言葉］Q16・Q21：b区域の爪は原画視点で房として読めない。自己評審：前と後がほとんど同じで、平らな白の上に離れた鉤が並ぶだけ、
5〜10 本の指の房がない。原画の b区域の線の成分 176 に対して描画は 81。

名前の付いた美術の誘導（帯の頂点の並びだけで決まり、原画カメラからの投影の色は使わない。Q28）：
  - pl33f_tuft_fingers：b区域の帯（一覧の row b区域、膜でない原画の爪）ごとに、同じ向きに巻く短い添え指を両側に 1 本ずつ置く。
    添え指の中心線は、親の帯の中心線（根元 → 輪 → 先）を弧長の LAMBDA（0.72・0.60）までなぞり、親の帯の横の向き
    （根元の円の法線 × 中心線の向き。コマごとに作り直すので、断面を 180° 回した輪でも側が入れ替わらない）へ、親の幅の最大 × OFFSET（0.95）だけずらしたもの。
    断面は親の輪を WIDTH（0.70）倍にした形。親の成長（そのコマの弧長）にそのまま付いていくので、生まれる時刻・伸びる順は親と同じ。
  - pl33f_tuft_floor：添え指の輪の中心の面からの高さ（近い頂点の法線）を、親の同じ所の高さにそろえる（面の曲がりで刺さる・浮くのを防ぐ）。全コマ。
  - 根元の点と根元の円も同じだけずらし、円は WIDTH 倍に縮める（PL32ClawLook の根元の水色の版の雲と、根元で開く線はそのまま付く）。
  - pl33f_tuft_halfline：添え指の縁の線は、親の帯に向く側の半分（輪の頂点 3〜5 または 7・0・1）を描かない（PL33ClawLook が縁の線のメッシュの UV3.x を −1 にする）。
    添え指と親の線が交わって閉じた輪（米粒）になるのを防ぎ、添え指は外の縁だけに墨版の線を持つ巻き（原画の房の指の描き方）になる。
  id は S ＋ 親の id ＋ p／m（親から見て幅の軸 0−4 の ＋／− の側。p は頂点 3〜5、m は 7・0・1 の側の線を描かない）、type は S。

入力（Git 対象外）：--src（pl33f_relief.py の出力。既定 Unity/Build/Polish/33/fix01/relief）。出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/fix01/relief_t）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/pl33/pl33f_tuft.py
"""
import argparse
import json
import os
import shutil
import sys
import time

import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
import pl33_common as Q  # noqa: E402
from pl33f_relief import taus_of, K_STAR  # noqa: E402

SRC = REPO + "/Unity/Build/Polish/33/fix01/relief"
OUT = REPO + "/Unity/Build/Polish/33/fix01/relief_t"
INV = REPO + "/Unity/Build/Polish/32/fix01/list/ds32_claw_inventory.json"
RING = 8
K_STAR = 360
SIDES = ((1.0, 0.72, "a", 1.25), (-1.0, 0.60, "b", 1.25))     # （外側の向きの倍率 ＋1 外・−1 内、弧長、名前、ずらし／親の幅の最大）
OFFSET = 1.0
WIDTH = 0.65


def interp_poly(Pp, cum, u):
    """Pp：(n, 3) の折れ線、cum：弧長の累積 (n,)、u：弧長の位置 (m,) → (m, 3) と区間の番号。"""
    k = np.clip(np.searchsorted(cum, u, side="right") - 1, 0, len(cum) - 2)
    seg = np.maximum(cum[k + 1] - cum[k], 1e-12)
    w = np.clip((u - cum[k]) / seg, 0.0, 1.0)
    return Pp[k] + w[:, None] * (Pp[k + 1] - Pp[k]), k, w


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=SRC)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args()
    t0 = time.time()
    lay = json.load(open(os.path.join(a.src, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V = lay["frames"], lay["vertices"]
    X = np.fromfile(os.path.join(a.src, lay["files"]["frames"]["file"]), dtype=np.float32).reshape(F, V, 3)
    rowof = {c["id"]: c.get("row") for c in json.load(open(INV, encoding="utf-8"))["claws"]}
    parents = [c for c in lay["claws"] if c.get("type") not in ("W", "T6", "S") and rowof.get(c["id"]) == "b区域"]
    # 外側：鉤の内の膜（pl33_hook_web）と反対の側。膜が頂点 0 の側（phi0）なら −（幅の軸 0−4 の逆）、頂点 4 の側なら +
    rep = {r["id"]: r for r in json.load(open(os.path.join(a.src, "pl33f_relief_report.json"), encoding="utf-8"))["claws"]}
    outer = {c["id"]: (-1.0 if rep.get(c["id"], {}).get("web", {}).get("inner_edge") == "phi0" else 1.0) for c in parents}
    taus = taus_of(F)
    hero = Q.U.K.Pkg(Q.HERO)
    nS = len(parents) * len(SIDES)
    base = {}
    tot = 0
    for i, c in enumerate(parents):
        for si in range(len(SIDES)):
            base[(i, si)] = tot
            tot += RING * c["stations"] + 11
    Ys = np.zeros((F, tot, 3), np.float32)
    # pl33f_tuft_zone：t* で、添え指の中心線の点の近いシートの頂点が白の範囲（PL29 の白の範囲 pl31_zone_vertex。3D の属性）の外なら、
    # 弧長の倍率を 0.85 倍ずつ（最小 0.4）縮める（添え指を藍の面へ出さない）。倍率は時刻によらない。
    zone = np.load(Q.ZONE).reshape(-1)
    Xk = hero.world(0.0)
    treek = cKDTree(Xk.reshape(-1, 3))
    lam_scale = {}
    Xs_ = X[K_STAR].astype(np.float64)
    for i, c in enumerate(parents):
        o, st = c["vert_offset"], c["stations"]
        R = Xs_[o + 1:o + 1 + st * RING].reshape(st, RING, 3)
        ctr = R.mean(1)
        Pp = np.concatenate([Xs_[o][None], ctr, Xs_[o + 1 + st * RING][None]], 0)
        cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
        ax = R[:, 0] - R[:, 4]; ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-12)
        lat = np.concatenate([ax[:1], ax, ax[-1:]], 0)
        wmax = float(np.linalg.norm(R[:, 0] - R[:, 4], axis=1).max())
        for si, (sgn0, lam, suf, offs) in enumerate(SIDES):
            sgn = sgn0 * outer[c["id"]]
            sc = 1.0
            for it in range(6):
                u = lam * sc * cum
                pts, _, _ = interp_poly(Pp, cum, u)
                lt, _, _ = interp_poly(lat, cum, u)
                lt /= np.maximum(np.linalg.norm(lt, axis=1, keepdims=True), 1e-12)
                _, ii = treek.query(pts + sgn * offs * wmax * lt)
                if zone[ii].all() or sc <= 0.4:
                    break
                sc = max(0.4, sc * 0.85)
            lam_scale[(i, si)] = sc
    print("parents", len(parents), "sub-fingers", nS, flush=True)
    for f in range(F):
        Xs = hero.world(float(taus[f]))
        dr = np.gradient(Xs, axis=0); dc = np.gradient(Xs, axis=1)
        nrm = np.cross(dr, dc); nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-12)
        Vf = Xs.reshape(-1, 3); nrm = nrm.reshape(-1, 3)
        tree = cKDTree(Vf)
        Xf = X[f].astype(np.float64)
        for i, c in enumerate(parents):
            o, st = c["vert_offset"], c["stations"]
            NV = RING * st + 11
            root = Xf[o]
            R = Xf[o + 1:o + 1 + st * RING].reshape(st, RING, 3)
            tip = Xf[o + 1 + st * RING]
            cen = Xf[o + 2 + st * RING]
            circ = Xf[o + 3 + st * RING:o + NV]
            ctr = R.mean(1)
            Pp = np.concatenate([root[None], ctr, tip[None]], 0)
            cum = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Pp, axis=0), axis=1))]
            Ltot = cum[-1]
            for si, (sgn0, lam, suf, offs) in enumerate(SIDES):
                sgn = sgn0 * outer[c["id"]]
                b = base[(i, si)]
                if Ltot < 1e-4 or np.linalg.norm(circ - cen, axis=1).max() < 1e-6:
                    Ys[f, b:b + NV] = root
                    continue
                # 横の向き：親の帯の輪の幅の軸（頂点 0 − 4。断面を 180° 回して続けた輪なので、コマの間で側が入れ替わらない）
                ax = R[:, 0] - R[:, 4]
                ax /= np.maximum(np.linalg.norm(ax, axis=1, keepdims=True), 1e-12)
                lat = np.concatenate([ax[:1], ax, ax[-1:]], 0)
                wmax = float(np.linalg.norm(R[:, 0] - R[:, 4], axis=1).max())
                dlt = sgn * offs * wmax
                u = lam * lam_scale[(i, si)] * cum[np.r_[0, 1:st + 1, st + 1]]        # 根元・輪・先の弧長を lam 倍
                pts, k, w = interp_poly(Pp, cum, u)
                lt, _, _ = interp_poly(lat, cum, u)
                lt /= np.maximum(np.linalg.norm(lt, axis=1, keepdims=True), 1e-12)
                # 断面：親の輪（k の区間の両端の輪の形を補間）を WIDTH 倍
                Rx = np.concatenate([np.repeat(R[:1], 1, 0), R, R[-1:]], 0)          # Pp の点と同じ番号（根元・先は端の輪の形）
                cx = np.concatenate([root[None], ctr, tip[None]], 0)
                shape = (1 - w)[:, None, None] * (Rx[k] - cx[k][:, None, :]) + w[:, None, None] * (Rx[k + 1] - cx[k + 1][:, None, :])
                sub_c = pts + dlt * lt
                # pl33f_tuft_floor：面からの高さを親の同じ所にそろえる
                _, ip = tree.query(pts); _, isb = tree.query(sub_c)
                hp = ((pts - Vf[ip]) * nrm[ip]).sum(1)
                hs = ((sub_c - Vf[isb]) * nrm[isb]).sum(1)
                sub_c = sub_c + (hp - hs)[:, None] * nrm[isb]
                rings = sub_c[1:st + 1, None, :] + WIDTH * shape[1:st + 1]
                Ys[f, b] = sub_c[0]
                Ys[f, b + 1:b + 1 + st * RING] = rings.reshape(-1, 3)
                Ys[f, b + 1 + st * RING] = sub_c[-1]
                Ys[f, b + 2 + st * RING] = cen + (sub_c[0] - root)
                Ys[f, b + 3 + st * RING:b + NV] = sub_c[0] + WIDTH * (circ - root)
        if f % 60 == 0:
            print("frame", f, round(time.time() - t0, 1), "s", flush=True)
    os.makedirs(a.out, exist_ok=True)
    tris = [np.fromfile(os.path.join(a.src, lay["files"]["tris"]["file"]), dtype=np.int32).reshape(-1, 3)]
    att = [np.fromfile(os.path.join(a.src, lay["files"]["tri_attr"]["file"]), dtype=np.uint16).reshape(-1, 2)]
    nb = len(lay["claws"])
    sk = np.fromfile(os.path.join(a.src, lay["files"]["skel"]["file"]), dtype=np.float32).reshape(F, nb, 36)
    k = 0
    for i, c in enumerate(parents):
        for si, (sgn0, lam, suf, offs) in enumerate(SIDES):
            sgn = sgn0 * outer[c["id"]]
            off = V + base[(i, si)]
            NV = RING * c["stations"] + 11
            Tt, kd = Q.layout_tris(c["stations"], off)
            tris.append(Tt.astype(np.int32))
            att.append(np.stack([np.full(len(kd), nb + k), kd], 1).astype(np.uint16))
            lay["claws"].append({"id": "S" + c["id"] + ("p" if sgn > 0 else "m"), "index": nb + k, "vert_offset": off, "vert_count": NV, "stations": c["stations"], "type": "S",
                                 "pl33f_tuft_of": c["id"], "lambda": lam, "side": sgn, "offset": offs})
            k += 1
    Yall = np.concatenate([X, Ys], axis=1)
    Yall.tofile(os.path.join(a.out, lay["files"]["frames"]["file"]))
    np.concatenate(tris).tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
    np.concatenate(att).tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
    np.concatenate([sk, np.zeros((F, nS, 36), np.float32)], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
    lay["vertices"] = V + tot
    lay["triangles"] = int(sum(len(t) for t in tris))
    for kk in ("frames", "tris", "tri_attr", "skel"):
        p = os.path.join(a.out, lay["files"][kk]["file"])
        lay["files"][kk]["sha256"] = Q.sha(p)
        lay["files"][kk]["bytes"] = os.path.getsize(p)
    lay["pl33f_tuft"] = {"note_ja": __doc__.strip().split("\n\n")[0], "tool": "Tools/GWWaveGen/pl33/pl33f_tuft.py", "parents": len(parents), "sub_fingers": nS,
                         "sides": [list(s_) for s_ in SIDES], "width": WIDTH,
                         "lambda_scale_lt1": int(sum(1 for v in lam_scale.values() if v < 0.999)), "src": os.path.relpath(a.src, REPO).replace("\\", "/")}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33F_TUFT_DONE parents", len(parents), "sub", nS, "vertices", lay["vertices"], round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
