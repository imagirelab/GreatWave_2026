# -*- coding: utf-8 -*-
"""仕上げ33（設計33 爪の造形）：頂の裏の「冠の爪」（pl33_crown）を作り、射線の向きに立ち上げた原画の爪（pl33_claw_relief.py の出力）に足す（numpy）。

なぜ：原画の爪（一覧の 184 本）は、どれも原画のカメラから見える面（頂の前・唇・b区域）に付いている。左右の側面・後ろ 65°・真上・回り台の
90〜330° からは、その面が見えないので、爪がほとんど読めなかった（仕上げ29 の限界 1、仕上げ32 の第 4 節）。参照モデル（彫刻）は頂の稜に沿って
白い指が突き出し、後ろから見ても稜がぎざぎざの指の列として読める（写真のフォルダー Q16 を目で見た。形・寸法は写していない）。

名前の付いた美術の誘導（どれも帯の頂点の並びだけで決まり、色は PL29 Claw Shade の段。原画カメラからの投影の色は使わない。Q28）：
  - pl33_crown：t* の主役波の白の範囲（PL29 の白の範囲 pl31_zone_vertex）のうち、原画のカメラから隠れている面（numpy の z バッファで
    奥行きが手前の面より HID_M 以上奥）で、原画視点で見える面の縁（稜）から 3D の距離 BAND_M 以内の帯に、根元を間隔 SPACING_M の
    Poisson 円盤で置く。根元は主役波のシートの頂点 (行, 列) に固定（105・137 と同じ結び付け）。
  - pl33_crown_curl：爪の中心線は、根元の局所の座標系 [e1 e2 n] の中で、面の法線から THETA0 だけ稜の向き u（根元から最も近い稜の点の向きを
    接線の面へ射影し、±TWIST_DEG だけ振る）へ傾いて立ち上がり、先へ向かって THETA1 まで稜の側へ巻く（鉤）。帯は設計33 と同じ 8 頂点の輪 × 20 ＋ 先 ＋
    根元の円で、幅は根元 W_REL × 長さ（W_MIN〜W_MAX）から先へ細り、側面の厚みは幅の TH_REL（0.45。99 の 15〜25% は原画の船側の列の中央の爪の項目で、原画にない冠の爪には当てず、
    横から見ても指の量感が読める厚みにした。進行役の既定）。上面（白）は巻きの外側、下面（水色の版）は内側。
  - pl33_crown_hidden：t* で、爪の全部の頂点が原画のカメラから隠れている（主役波の面より HID_M 以上奥、かつ原画視点の主役波の中）ことを確かめ、
    満たさない爪は長さを 0.85 倍ずつ 5 回まで縮め、届かなければ稜と逆の向きへ巻く案（pl33_crown_flip）で同じことをし、
    それでも満たさない爪は作らない（根元の円と輪の辺の中点も確かめる）。原画視点の t* の描画（評価器の関門）は変わらない。
  - pl33_crown_clear：t* で、輪の中心が面より上にある（面の外側に THICK の半分以上）ことを確かめ、満たさない爪は巻きを弱め、それでも面に入る爪は作らない。
  - 成長：根元の T_white（τ_w、−0.3 s より遅い時は −0.3 s）で生まれ、s = (τ − τ_w)/(0 − τ_w) で、長さ 0.12 → 1（s 0.1〜0.75）、
    幅 0.4 → 1（s 0〜0.4）、巻き 0 → 1（s 0.35〜1）。τ_w より前は根元の点に潰す（設計33 と同じ。面積 0 で描かれない）。t* の後は保持。

入力（Git 対象外）：--relief（pl33_claw_relief.py の出力。既定 Unity/Build/Polish/33/relief）、主役波 Unity/Build/Polish/32/white/hero_pkg、
  時間曲線 Unity/Build/Polish/28/G_p28rec/timewarp_G_p28rec.json、白の範囲 Unity/Build/Polish/32/white/pl31_zone_vertex.npy
出力（Git 対象外）：--out（既定 Unity/Build/Polish/33/claws）。ds33_claw_layout.json と同じ書式（爪 = 原画の爪 184 ＋ 冠の爪、id は K001〜）。
使い方（リポジトリの根で。重い numpy の処理と同時に回さない）：py -3.10 -B Tools/GWWaveGen/pl33/pl33_crown.py
"""
import argparse
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds33")
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds31")
import ds33_common as U  # noqa: E402
import ds31_white as W31  # noqa: E402
sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
from pl33_common import layout_tris  # noqa: E402

B = REPO + "/Unity/Build/Polish"
HERO = B + "/32/white/hero_pkg"
WARP = B + "/28/G_p28rec/timewarp_G_p28rec.json"
ZONE = B + "/32/white/pl31_zone_vertex.npy"
RELIEF = B + "/33/relief"
OUT = B + "/33/claws"
RING = 8
N_ST = 20
PHI = 2 * np.pi * np.arange(RING) / RING
HZ = 30.0
K_STAR = 360

P = dict(SPACING_M=1.1, BAND_M=4.5, BAND_MIN_M=0.8, Y_MIN=6.0, HID_M=0.5, VIS_M=0.20, TW_MAX=-0.2,
         L_MIN=1.6, L_MAX=3.0, W_REL=0.30, W_MIN=0.30, W_MAX=0.75, TH_REL=0.45, TIP_W=0.25,
         THETA0=62.0, THETA1=-40.0, TWIST_DEG=28.0, CURL_POW=1.4, TW_FLOOR=-0.3, SEED=33, FOLD_M=1.0, FOLD_PX=6)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def centerline(root, u, n, L, th0, th1):
    """根元から、法線 n と稜の向き u の面の中で θ(a) = θ0 + (θ1 − θ0)·a^p（面からの角）で伸びる中心線（N_ST+1 点）と θ。"""
    a = np.linspace(0, 1, N_ST + 1)
    th = np.radians(th0 + (th1 - th0) * a ** P["CURL_POW"])
    d = np.cos(th)[:, None] * u[None, :] + np.sin(th)[:, None] * n[None, :]
    seg = 0.5 * (d[1:] + d[:-1]) * (L / N_ST)
    pts = root[None, :] + np.concatenate([np.zeros((1, 3)), np.cumsum(seg, axis=0)], axis=0)
    return pts, th, d


def band(pts, th, d, u, n, w0, thick_rel):
    """中心線から輪（N_ST×8×3）と先端。上面（φ 90°）は巻きの外側 N = −sinθ·u + cosθ·n、B = N × T（設計33 と同じ向きの決まり）。"""
    T = d / np.linalg.norm(d, axis=1, keepdims=True)
    N = -np.sin(th)[:, None] * u[None, :] + np.cos(th)[:, None] * n[None, :]
    Bv = np.cross(N, T)
    Bv /= np.maximum(np.linalg.norm(Bv, axis=1, keepdims=True), 1e-12)
    Nn = np.cross(T, Bv)
    a = np.linspace(0, 1, N_ST + 1)
    w = w0 * (1 - (1 - P["TIP_W"]) * a ** 1.5)
    t = thick_rel * w
    ring = (pts[:N_ST, None, :] + Bv[:N_ST, None, :] * (0.5 * w[:N_ST, None] * np.cos(PHI)[None, :])[..., None]
            + Nn[:N_ST, None, :] * (0.5 * t[:N_ST, None] * np.sin(PHI)[None, :])[..., None])
    return ring, pts[N_ST], w, t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relief", default=RELIEF)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--spacing", type=float, default=P["SPACING_M"])
    a = ap.parse_args()
    P["SPACING_M"] = a.spacing
    t0 = time.time()
    rng = np.random.default_rng(P["SEED"])
    hero = U.K.Pkg(HERO)
    wt, wtau = W31.load_warp(WARP)
    lay = json.load(open(os.path.join(a.relief, "ds33_claw_layout.json"), encoding="utf-8"))
    F, V0 = lay["frames"], lay["vertices"]
    tk = np.arange(F) / HZ
    taus = np.where(tk >= 12.0 - 1e-9, 0.0, np.interp(tk, wt, wtau))
    X0 = hero.world(0.0)
    R, C = X0.shape[:2]
    tw = np.fromfile(HERO + "/ds27_twhite_r32f.bin", dtype="<f4").reshape(R, C).astype(np.float64)
    zone = np.load(ZONE).reshape(R, C)
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    cam = U.CamWH(spec, 1920, 1080)
    b0, b1 = U.BODY
    Tg = U.K.grid_tris(R, C, b0, b1)
    Vf = X0.reshape(-1, 3)
    idb, zb = U.raster(cam, Vf[Tg], np.arange(1, len(Tg) + 1))
    znear = cv2.dilate(zb.astype(np.float32), np.ones((5, 5), np.uint8)).astype(np.float64)   # 5×5 の中で最も手前の面（1/z の最大）
    zfar = cv2.erode(zb.astype(np.float32), np.ones((3, 3), np.uint8)).astype(np.float64)     # 3×3 がどれも主役波なら > 0
    # pl33_crown_fold：主役波の面の折れ（原画視点で奥行きが 5×5 の中で FOLD_M より変わる所。b区域の肩の稜の線など）の FOLD_PX の内は
    # 隠れとみなさない（試しの描画で、折れの線の裏の冠の爪が線の際から覗いた）
    zz = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 0.0).astype(np.float32)
    zmax = cv2.dilate(zz, np.ones((5, 5), np.uint8)); zmin = cv2.erode(np.where(zb > 0, zz, 1e6).astype(np.float32), np.ones((5, 5), np.uint8))
    fold = ((zmax - zmin) > P["FOLD_M"]) | (zb <= 0)
    fold = cv2.dilate(fold.astype(np.uint8), np.ones((2 * P["FOLD_PX"] + 1, 2 * P["FOLD_PX"] + 1), np.uint8)).astype(bool)
    zfar = np.where(fold, 0.0, zfar)

    def depth_test(Q):
        xy, z = cam.project(Q)
        xi = np.round(xy[..., 0]).astype(int); yi = np.round(xy[..., 1]).astype(int)
        inb = (xi >= 0) & (xi < 1920) & (yi >= 0) & (yi < 1080)
        xi = np.clip(xi, 0, 1919); yi = np.clip(yi, 0, 1079)
        zs_near = np.where(znear[yi, xi] > 0, 1.0 / np.maximum(znear[yi, xi], 1e-9), np.inf)
        zs_pix = np.where(zb[yi, xi] > 0, 1.0 / np.maximum(zb[yi, xi], 1e-9), np.inf)
        hidden = inb & (zfar[yi, xi] > 0) & (z > zs_near + P["HID_M"])
        visible = inb & (z <= zs_pix + P["VIS_M"])
        return hidden, visible

    hid, vis = depth_test(Vf)
    hid = hid.reshape(R, C); vis = vis.reshape(R, C)
    cols = np.zeros((R, C), bool); cols[:, b0:b1 + 1] = True
    rim = vis & zone & cols
    tree_rim = cKDTree(X0[rim])
    drim, irim = tree_rim.query(Vf)
    drim = drim.reshape(R, C)
    band_m = zone & hid & cols & (tw < P["TW_MAX"]) & (drim >= P["BAND_MIN_M"]) & (drim <= P["BAND_M"]) & (X0[..., 1] >= P["Y_MIN"])
    rr, cc = np.nonzero(band_m)
    order = rng.permutation(len(rr))
    acc = []
    grid = {}
    sp = P["SPACING_M"]
    for k in order:
        p = X0[rr[k], cc[k]]
        key = tuple(np.floor(p / sp).astype(int))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        if np.linalg.norm(X0[q[0], q[1]] - p) < sp:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            acc.append((rr[k], cc[k]))
            grid.setdefault(key, []).append((rr[k], cc[k]))
    acc.sort(key=lambda q: (q[1], q[0]))
    rim_pts = X0[rim]
    crowns = []
    drop = {"hidden": 0, "clear": 0}
    for (r, c) in acc:
        Fr = U.frame_at(X0, float(r), float(c))           # 行が e1 e2 n
        n = Fr[2]
        root = X0[r, c]
        _, j = tree_rim.query(root)
        v = rim_pts[j] - root
        u = v - (v @ n) * n
        if np.linalg.norm(u) < 1e-6:
            u = Fr[1].copy()
        u /= np.linalg.norm(u)
        psi = np.radians(rng.uniform(-P["TWIST_DEG"], P["TWIST_DEG"]))
        u = np.cos(psi) * u + np.sin(psi) * np.cross(n, u)
        L0 = rng.uniform(P["L_MIN"], P["L_MAX"])
        made = None
        drop_reason = "hidden"
        ang = 2 * np.pi * np.arange(RING) / RING
        # 稜の向きへ巻く案 → 届かなければ（原画視点で見えてしまう）稜と逆の向きへ巻く案（pl33_crown_flip）
        for flip in (1.0, -1.0):
            uu = flip * u
            L = L0
            th1 = P["THETA1"]
            for it in range(6):
                pts, th, d = centerline(root, uu, n, L, P["THETA0"], th1)
                w0 = float(np.clip(P["W_REL"] * L, P["W_MIN"], P["W_MAX"]))
                ring, tip, w, t = band(pts, th, d, uu, n, w0, P["TH_REL"])
                e2 = np.cross(n, uu)
                rc_c = 0.55 * w0
                circ = root[None, :] + rc_c * (np.cos(ang)[:, None] * uu[None, :] * np.where(np.cos(ang) < 0, 1.35, 1.0)[:, None] + np.sin(ang)[:, None] * e2[None, :])
                Qp = np.concatenate([ring.reshape(-1, 3), tip[None, :], circ, 0.5 * (ring[:, :, :] + np.roll(ring, -1, axis=1)).reshape(-1, 3)])
                h_ok, _ = depth_test(Qp)
                # 面より上か（輪の中心の、シートへの最も近い点からの法線の高さ）
                rcs = np.tile([[float(r), float(c)]], (N_ST, 1))
                _, _, hh, _ = U.project_to_sheet(X0, pts[1:N_ST + 1], rcs[:N_ST])
                clear = bool(np.all(hh > 0.25 * t[1:N_ST + 1]))
                if h_ok.all() and clear and L >= P["L_MIN"] * 0.6:
                    made = (L, th1, w0, flip)
                    break
                if not clear:
                    th1 = th1 + 25.0                               # 巻きを弱める
                    drop_reason = "clear"
                else:
                    L *= 0.85
                    drop_reason = "hidden"
            if made is not None:
                break
        if made is None:
            drop[drop_reason] += 1
            continue
        u = made[3] * u
        ul = Fr @ u                                        # 局所の成分
        # 根元の円（面の上の 8 点。t* の面の (行, 列) に結び付ける）
        rc_c = 0.55 * made[2]
        e1 = u; e2 = np.cross(n, u)
        circ = root[None, :] + rc_c * (np.cos(ang)[:, None] * e1[None, :] * np.where(np.cos(ang) < 0, 1.35, 1.0)[:, None] + np.sin(ang)[:, None] * e2[None, :])
        cr, ccq, _, _ = U.project_to_sheet(X0, circ, np.tile([[float(r), float(c)]], (RING, 1)))
        crowns.append(dict(id="K%03d" % (len(crowns) + 1), r=int(r), c=int(c), ul=ul.tolist(), L=float(made[0]), th1=float(made[1]), w0=float(made[2]),
                           tw=float(tw[r, c]), circ_rc=np.stack([cr, ccq], 1).tolist(), drim_m=float(drim[r, c]), y=float(root[1]), flip=float(made[3])))
    print("band vertices", int(band_m.sum()), "accepted roots", len(acc), "crowns", len(crowns), "dropped", drop, flush=True)
    # ---- コマごとの帯
    NV = RING * N_ST + 11
    nC = len(crowns)
    Yc = np.zeros((F, nC * NV, 3), np.float32)
    skel = np.zeros((F, nC, 36), np.float32)
    tri_all, att_all = [], []
    base0 = V0
    for i in range(nC):
        Tt, kd = layout_tris(N_ST, base0 + i * NV)
        tri_all.append(Tt)
        att_all.append(np.stack([np.full(len(kd), len(lay["claws"]) + i), kd], 1))
    for f in range(F):
        tau = taus[f]
        Xf = X0 if abs(tau) < 1e-12 else hero.world(float(tau))
        for i, cw in enumerate(crowns):
            r, c = cw["r"], cw["c"]
            o = i * NV
            root = Xf[r, c]
            twr = min(cw["tw"], P["TW_FLOOR"])
            if tau < twr - 1e-9:
                Yc[f, o:o + NV] = root
                continue
            s = float(np.clip((tau - twr) / (0.0 - twr), 0.0, 1.0))
            gL = 0.12 + 0.88 * sm((s - 0.1) / 0.65)
            gw = 0.4 + 0.6 * sm(s / 0.4)
            gc = sm((s - 0.35) / 0.65)
            Fr = U.frame_at(Xf, float(r), float(c))
            n = Fr[2]
            u = Fr.T @ np.array(cw["ul"])
            u = u - (u @ n) * n
            u /= max(np.linalg.norm(u), 1e-12)
            th1 = P["THETA0"] + (cw["th1"] - P["THETA0"]) * gc
            pts, th, d = centerline(root, u, n, cw["L"] * gL, P["THETA0"], th1)
            ring, tip, w, t = band(pts, th, d, u, n, cw["w0"] * gw, P["TH_REL"])
            cr = np.array(cw["circ_rc"])
            cp = U.tri_eval(Xf, cr[:, 0], cr[:, 1]) + 0.004 * U.normal_at(Xf, cr[:, 0], cr[:, 1])
            cp = root[None, :] + gw * (cp - root[None, :])
            Yc[f, o] = root
            Yc[f, o + 1:o + 1 + N_ST * RING] = ring.reshape(-1, 3)
            Yc[f, o + 1 + N_ST * RING] = tip
            Yc[f, o + 2 + N_ST * RING] = root + 0.004 * n
            Yc[f, o + 3 + N_ST * RING:o + NV] = cp
            js = pts[[0, 5, 10, 15, 20]]
            skel[f, i, :15] = js.reshape(-1)
            skel[f, i, 15:30] = np.tile(n, 5)
            skel[f, i, 30:36] = [s, gL, 0.0, gw, 1.0, float(np.linalg.norm(np.diff(pts, axis=0), axis=1).sum())]
        if f % 60 == 0:
            print("frame", f, "tau", round(float(tau), 3), round(time.time() - t0, 1), "s", flush=True)
    # ---- 書き出し（原画の爪の写し ＋ 冠の爪）
    os.makedirs(a.out, exist_ok=True)
    src = lambda k: os.path.join(a.relief, lay["files"][k]["file"])  # noqa: E731
    Xr = np.fromfile(src("frames"), dtype=np.float32).reshape(F, V0, 3)
    Yall = np.concatenate([Xr, Yc], axis=1)
    del Xr
    fr_out = os.path.join(a.out, lay["files"]["frames"]["file"])
    Yall.tofile(fr_out)
    tris0 = np.fromfile(src("tris"), dtype=np.int32).reshape(-1, 3)
    att0 = np.fromfile(src("tri_attr"), dtype=np.uint16).reshape(-1, 2)
    tris = np.concatenate([tris0] + [t.astype(np.int32) for t in tri_all]) if nC else tris0
    att = np.concatenate([att0] + [x.astype(np.uint16) for x in att_all]) if nC else att0
    tris.astype(np.int32).tofile(os.path.join(a.out, lay["files"]["tris"]["file"]))
    att.astype(np.uint16).tofile(os.path.join(a.out, lay["files"]["tri_attr"]["file"]))
    sk0 = np.fromfile(src("skel"), dtype=np.float32).reshape(F, len(lay["claws"]), 36)
    np.concatenate([sk0, skel], axis=1).tofile(os.path.join(a.out, lay["files"]["skel"]["file"]))
    for k in ("frames", "tris", "tri_attr", "skel"):
        p = os.path.join(a.out, lay["files"][k]["file"])
        lay["files"][k]["sha256"] = sha(p)
        lay["files"][k]["bytes"] = os.path.getsize(p)
    for i, cw in enumerate(crowns):
        lay["claws"].append({"id": cw["id"], "index": len(lay["claws"]), "vert_offset": V0 + i * NV, "vert_count": NV, "stations": N_ST,
                             "type": "T6", "pl33_crown": True})
    lay["vertices"] = V0 + nC * NV
    lay["triangles"] = int(len(tris))
    lay["pl33_crown"] = {"note_ja": __doc__.strip().split("\n\n")[0], "params": P, "crowns": nC, "dropped": drop,
                         "relief_src": os.path.relpath(a.relief, REPO).replace("\\", "/"), "hero_pkg": os.path.relpath(HERO, REPO).replace("\\", "/"),
                         "zone_sha256": sha(ZONE), "warp_sha256": sha(WARP)}
    json.dump(lay, open(os.path.join(a.out, "ds33_claw_layout.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump({"params": P, "crowns": crowns, "band_vertices": int(band_m.sum()), "accepted_roots": len(acc), "dropped": drop,
               "elapsed_s": round(time.time() - t0, 1)}, open(os.path.join(a.out, "pl33_crown.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("PL33_CROWN_DONE crowns", nC, "vertices", lay["vertices"], "triangles", lay["triangles"], round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
