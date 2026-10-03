# -*- coding: utf-8 -*-
"""美術の見本02 爪の部：一覧の図（爪ごとに 利用者のマスク｜3D の爪を面から｜3/4｜利用者の模型 claw_mid を同じ縮尺で）。
numpy の描画（頂点の法線で陰を補う簡単な描画。Unity の描画ではない）。利用者のマスクを含むので、図は Git 対象外の Build にだけ置く（D14・D23）。

使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_gallery.py [--mesh DIR] [--out PNG] [--cols 4]
"""
import argparse
import json
import math
import os
import sys

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/as02")
import as02_claws100 as A  # noqa: E402
from as02_mini_render import read_obj  # noqa: E402

TILE = 230
WHITE = np.array([223, 243, 248], np.float64)     # BGR（白 248,243,223）
MIZU = np.array([203, 202, 180], np.float64)      # BGR（水色 180,202,203）
LINE = (94, 60, 31)


def vnormals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    vn = np.zeros_like(V)
    for k in range(3):
        np.add.at(vn, F[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def render(V, F, vcol, view_dir, up, size, center, scale, light=(-0.6, 0.6, -0.5)):
    """正射影、z バッファ、頂点の法線の陰（Gouraud）、輪郭の線。"""
    W = H = size
    f = np.asarray(view_dir, float)
    f /= np.linalg.norm(f)
    u = np.asarray(up, float)
    u = u - (u @ f) * f
    u /= np.linalg.norm(u)
    r = np.cross(u, f)
    d = V - center
    x = W * 0.5 + (d @ r) * scale
    y = H * 0.5 - (d @ u) * scale
    z = d @ f
    vn = vnormals(V, F)
    L = np.asarray(light, float)
    L /= np.linalg.norm(L)
    # 両面：カメラへ向く側
    vns = np.where(((vn @ f) > 0)[:, None], -vn, vn)
    lam = 0.66 + 0.40 * np.clip(vns @ (-L), 0, 1) + 0.06 * np.clip(-(vns @ f), 0, 1)
    vc = np.clip(vcol * lam[:, None], 0, 255)
    img = np.full((H, W, 3), 255.0)
    zb = np.full((H, W), np.inf)
    idb = np.full((H, W), -1, np.int64)
    for t, tri in enumerate(F):
        xs, ys = x[tri], y[tri]
        x0, x1 = int(max(np.floor(xs.min()), 0)), int(min(np.ceil(xs.max()), W - 1))
        y0, y1 = int(max(np.floor(ys.min()), 0)), int(min(np.ceil(ys.max()), H - 1))
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        den = (ys[1] - ys[2]) * (xs[0] - xs[2]) + (xs[2] - xs[1]) * (ys[0] - ys[2])
        if abs(den) < 1e-12:
            continue
        w0 = ((ys[1] - ys[2]) * (gx - xs[2]) + (xs[2] - xs[1]) * (gy - ys[2])) / den
        w1 = ((ys[2] - ys[0]) * (gx - xs[2]) + (xs[0] - xs[2]) * (gy - ys[2])) / den
        w2 = 1 - w0 - w1
        m = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not m.any():
            continue
        zz = w0 * z[tri[0]] + w1 * z[tri[1]] + w2 * z[tri[2]]
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        upd = m & (zz < sub)
        if not upd.any():
            continue
        col = w0[..., None] * vc[tri[0]] + w1[..., None] * vc[tri[1]] + w2[..., None] * vc[tri[2]]
        sub[upd] = zz[upd]
        img[y0:y1 + 1, x0:x1 + 1][upd] = col[upd]
        idb[y0:y1 + 1, x0:x1 + 1][upd] = t
    out = img.astype(np.uint8)
    sil = idb >= 0
    e = cv2.morphologyEx(sil.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((2, 2), np.uint8)) > 0
    out[e] = LINE
    return out


def fail_en(f):
    """記録の日本語の不合格の文を、図の中の英字の短い名前へ（OpenCV の文字は英字だけ）。"""
    for k, v in (("輪郭のでこぼこ", "outline lumps"), ("背骨の曲率の跳び", "spine curvature jump"), ("面から見た IoU", "face IoU<0.85"),
                 ("断面の幅:厚み", "section ratio"), ("先の角", "blunt tip"), ("先の細り", "weak taper")):
        if f.startswith(k):
            import re
            nums = re.findall(r"[0-9.]+", f)
            return v + (" " + "/".join(nums[:2]) if nums else "")
    return "other"


def claw_colors(n_st):
    """PL29 Claw Shade と同じ段（as02 の値の表：q1〜q3 と q5〜q7 が白、縁 q0・q4 の近くが水色）。頂点の色で近似する。"""
    up = A.CC.vert_up(n_st)
    c = np.where((np.abs(up) > 0.30)[:, None], WHITE, MIZU)
    return c


def frame_of(e):
    """爪の自分の枠：面から（厚みの向き N の平均の反対から見る）、上＝根元 → 先の弦に直交する向き。"""
    nf = A.unit(e["N"].mean(0))
    V = e["V"]
    chord = V[8 * e["n"] + 1] - V[1]
    chord -= (chord @ nf) * nf
    up = A.unit(np.cross(nf, chord)) if np.linalg.norm(chord) > 1e-9 else np.array([0, 1.0, 0])
    return nf, up


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh", default=A.OUTD)
    ap.add_argument("--out", default=REPO + "/Unity/Build/Polish/sample02/claws/figs/gallery.png")
    ap.add_argument("--cols", type=int, default=4)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    E = list(np.load(a.mesh + "/as02_entries.npy", allow_pickle=True))
    rep = json.load(open(a.mesh + "/as02_claws_report.json", encoding="utf-8"))
    rmap = {c["user_id"]: c for c in rep["claws"]}
    users, _, _ = A.load_user()
    um = {u["uid"]: u for u in users}
    if a.only:
        keep = set(a.only.split(","))
        E = [e for e in E if e["uid"] in keep]
    Vm, Fm = read_obj("G:/research/model/claw_mid.obj")
    Hm_ = np.ptp(Vm[:, 1])   # 模型の高さ（m、模型の単位のまま）
    tiles = []
    for e in E:
        uid = e["uid"]
        r = rmap[uid]
        V = e["V"].astype(np.float64)
        F = e["T"][e["kind"] != 2]
        col = claw_colors(e["n"])
        # 作り直した爪（置く前の平らな三日月、Vcan）を、面から（原画のカメラから見る向き＝利用者がマスクを描いた向き。正射影、上はカメラの上）と 3/4 で。
        # 5 枚目は置いた爪（原画の射線の上で奥行きだけ曲げたもの）の 3/4
        cam = A.CC.painting_cam()
        Vc = e["Vcan"].astype(np.float64)
        ctr = 0.5 * (Vc.min(0) + Vc.max(0))
        vd = A.unit(ctr - cam.pos)
        up = A.unit(cam.u - (cam.u @ vd) * vd)
        side = np.cross(up, vd)
        ext = max(np.ptp((Vc - ctr) @ side), np.ptp((Vc - ctr) @ up), 1e-6)
        sc = 0.80 * TILE / ext
        face = render(Vc, F, col, vd, up, TILE, ctr, sc)
        R = math.radians(55.0)
        v34 = math.cos(R) * vd + math.sin(R) * side
        s34 = np.cross(up, v34)
        ext34 = max(np.ptp((Vc - ctr) @ s34), np.ptp((Vc - ctr) @ up), 1e-6)
        q34 = render(Vc, F, col, v34, up, TILE, ctr, 0.80 * TILE / ext34)
        ctrp = 0.5 * (V.min(0) + V.max(0))
        extp = max(np.ptp((V - ctrp) @ s34), np.ptp((V - ctrp) @ up), 1e-6)
        p34 = render(V, F, col, v34, up, TILE, ctrp, 0.80 * TILE / extp)
        # マスク（切り抜き、白黒）。面から見た図と同じ向きに回さず、利用者の切り抜きのまま
        m = A.imread_u(um[uid]["dir"] + "/fill_mask.png", cv2.IMREAD_GRAYSCALE)
        s = 0.86 * TILE / max(m.shape)
        mm = cv2.resize(m, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        mt = np.full((TILE, TILE, 3), 255, np.uint8)
        oy, ox = (TILE - mm.shape[0]) // 2, (TILE - mm.shape[1]) // 2
        mt[oy:oy + mm.shape[0], ox:ox + mm.shape[1]][mm > 127] = (150, 150, 150)
        # 利用者の模型 claw_mid：模型の単位は任意なので、模型の背骨の弧長（4.92 単位）を、この爪の面から見た背骨の長さに合わせた縮尺で描く
        cen = np.array([Vc[1 + 8 * k: 1 + 8 * (k + 1)].mean(0) for k in range(e["n"])])
        Lface = float(np.sum(np.linalg.norm(np.diff(np.stack([(cen - ctr) @ side, (cen - ctr) @ up], -1), axis=0), axis=1)))
        scm = sc * Lface / 4.9177
        cm = render(Vm, Fm, np.tile(WHITE, (len(Vm), 1)), (-1, 0, 0), (0, 1, 0), TILE, 0.5 * (Vm.min(0) + Vm.max(0)), scm)
        row = np.hstack([mt, face, q34, p34, cm])
        bar = np.full((44, row.shape[1], 3), 255, np.uint8)
        fails = r.get("standard_fails_ja") or []
        t1 = "%s  IoU face %.2f  painting %.2f  placed L %.2fm (x%.1f)  lift %.0f deg" % (uid, r["iou_face"], r["iou_painting"], r["length_3d_m"], r["stretch"], r["alpha_deg"])
        t2 = "root vs normal %.0f deg  | %s" % (r["root_dir_vs_normal_deg"], ("FAIL: " + ", ".join(fail_en(f) for f in fails))[:80] if fails else "standard checks pass")
        cv2.putText(bar, t1, (6, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(bar, t2, (6, 37), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 160) if fails else (0, 100, 0), 1, cv2.LINE_AA)
        tile = np.vstack([bar, row])
        cv2.rectangle(tile, (0, 0), (tile.shape[1] - 1, tile.shape[0] - 1), (180, 180, 180), 1)
        tiles.append(tile)
    cols = a.cols
    while len(tiles) % cols:
        tiles.append(np.full_like(tiles[0], 255))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    # 大きすぎる時はページに分ける（1 ページ 6 行）
    per = 6
    outs = []
    for p in range(0, len(rows), per):
        img = np.vstack(rows[p:p + per])
        hdr = np.full((40, img.shape[1], 3), 255, np.uint8)
        cv2.putText(hdr, "user mask | rebuilt 3D claw face-on (painting direction) | same claw 3/4 (55 deg) | placed claw (bent along painting rays) 3/4 | user claw_mid, same spine length", (8, 27),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1, cv2.LINE_AA)
        img = np.vstack([hdr, img])
        fn = a.out.replace(".png", "_p%d.png" % (p // per + 1))
        cv2.imwrite(fn, img)
        outs.append(fn)
    print("AS02_GALLERY", outs)


if __name__ == "__main__":
    main()
