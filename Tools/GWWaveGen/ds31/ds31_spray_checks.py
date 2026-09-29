# -*- coding: utf-8 -*-
"""設計31 飛沫の部：飛沫 v0 のパッケージの検査と図（numpy。Unity の描画ではない）。

生成器（ds31_spray.py）の中の判定とは別の読みで確かめる：
  - 150（元の水面へ引き戻されるもの 0）：パッケージの解析式の表（ds31_spray_inst_f32.bin）だけを読み、240 Hz で、
    主役波の全体・近い海の全体・遠い海の全体の網について、最も近い頂点のまわりの 6 つの三角形への点と三角形の距離（厳密）と
    空気の側の符号を測る。放出の後いったん離れた粒子が、水面の半径 + 5 cm の内へ戻る、または水の側へ入ったら「引き戻し」と数える。
  - 152（四角い下地・黒い縁・光る縁 0）：単位球（42 頂点）の instancing の網を、t* の設計30 の場面と一緒に原画視点で z バッファ描画し、
    粒子ごとの画素の外接箱の充填率（円なら約 0.785、四角い板なら 1.0）と、画素の外周 1 px の色（場面の色のまま＝黒い縁なし）を調べる。
    numpy の描画は無照明・単色・外殻線なしの約束を確かめるもので、Unity の描画の確認は Unity の部へ渡す。
  - 149（離れて隙間が見える、記録）、151（ΔE00、記録）、t* の射線への再投影の誤差。
図：原画と t* の比べ、原画視点の τ の並び、側面の切り出し（軌跡）、2 つ並べた動画（30 fps、τ −1.6 s から t* の 1 s 後まで）。
"""
import argparse
import json
import math
import os
import subprocess
import sys
import time

import cv2
import numpy as np
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ds31_spray as SP  # noqa: E402

K = SP.K
S = SP.S
C27 = SP.C27
REPO = SP.REPO
OUT = SP.OUT
FFMPEG = "G:/ffmpeg-2024-12-19-git-494c961379-full_build/bin/ffmpeg.exe"
SPRAY_ID = 1000


def load_pkg(out):
    meta = S.load_json(os.path.join(out, "ds31_spray_package.json"))
    raw = np.fromfile(os.path.join(out, meta["inst_file"]), np.float32).reshape(-1, 12).astype(np.float64)
    tab = dict(p_e=raw[:, 0:3], tau_e=raw[:, 3], v0=raw[:, 4:7], radius=raw[:, 7], tau_show=raw[:, 8], ramp_s=raw[:, 9],
               mode=raw[:, 10].astype(int), dot_id=raw[:, 11].astype(int))
    return meta, tab


def tri_dist(p, a, b, c):
    """点と三角形の最短距離（Ericson の方法、ベクトル化）。p, a, b, c：(N,3)。戻り値：距離と最近点。"""
    ab = b - a; ac = c - a; ap = p - a
    d1 = np.sum(ab * ap, -1); d2 = np.sum(ac * ap, -1)
    bp = p - b; d3 = np.sum(ab * bp, -1); d4 = np.sum(ac * bp, -1)
    cp = p - c; d5 = np.sum(ab * cp, -1); d6 = np.sum(ac * cp, -1)
    va = d3 * d6 - d5 * d4; vb = d5 * d2 - d1 * d6; vc = d1 * d4 - d3 * d2
    den = np.where(np.abs(va + vb + vc) < 1e-18, 1e-18, va + vb + vc)
    v = vb / den; w = vc / den
    q = a + ab * v[:, None] + ac * w[:, None]
    # 辺・頂点の領域
    m = (d1 <= 0) & (d2 <= 0); q[m] = a[m]
    m = (d3 >= 0) & (d4 <= d3); q[m] = b[m]
    m = (d6 >= 0) & (d5 <= d6); q[m] = c[m]
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0); t = d1 / np.where(np.abs(d1 - d3) < 1e-18, 1e-18, d1 - d3); q[m] = (a + ab * t[:, None])[m]
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0); t = d2 / np.where(np.abs(d2 - d6) < 1e-18, 1e-18, d2 - d6); q[m] = (a + ac * t[:, None])[m]
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    t = (d4 - d3) / np.where(np.abs((d4 - d3) + (d5 - d6)) < 1e-18, 1e-18, (d4 - d3) + (d5 - d6)); q[m] = (b + (c - b) * t[:, None])[m]
    return np.linalg.norm(p - q, axis=-1), q


class Sheet:
    """格子のシートの頂点と、頂点ごとの隣の三角形（最大 6）。"""

    def __init__(self, R, C):
        self.R, self.C = R, C
        T = K.grid_tris(R, C)
        self.T = T
        adj = [[] for _ in range(R * C)]
        for ti, t in enumerate(T):
            for v in t:
                adj[v].append(ti)
        self.adj = np.full((R * C, 6), -1, np.int64)
        for v, a in enumerate(adj):
            self.adj[v, :len(a)] = a[:6]

    def dist(self, V, p, j):
        """p（N,3）と、最も近い頂点 j のまわりの三角形の厳密な距離と符号（三角形の法線の向き＝空気の側が +）。"""
        best = np.full(len(p), np.inf); sgn = np.ones(len(p))
        for k in range(6):
            t = self.adj[j, k]
            ok = t >= 0
            if not ok.any():
                continue
            tt = self.T[np.where(ok, t, 0)]
            a, b, c = V[tt[:, 0]], V[tt[:, 1]], V[tt[:, 2]]
            d, q = tri_dist(p, a, b, c)
            n = np.cross(b - a, c - a)
            s = np.sign(np.sum((p - q) * n, -1))
            upd = ok & (d < best)
            best[upd] = d[upd]; sgn[upd] = np.where(s[upd] == 0, 1, s[upd])
        return best, sgn


def crossings_down(pts, A, B, Cc):
    """点から真下（−y）への半直線が三角形を横切る数（生成器の真上の読みとは別の実装・別の向き）。
    描く水面（主役波の本体・近い海・遠い海）は下を覆うので、空気の中なら奇数、水の中（唇の折り返しの中・海の下）なら偶数。"""
    xmin = np.minimum(np.minimum(A[:, 0], B[:, 0]), Cc[:, 0]); xmax = np.maximum(np.maximum(A[:, 0], B[:, 0]), Cc[:, 0])
    zmin = np.minimum(np.minimum(A[:, 2], B[:, 2]), Cc[:, 2]); zmax = np.maximum(np.maximum(A[:, 2], B[:, 2]), Cc[:, 2])
    ymin = np.minimum(np.minimum(A[:, 1], B[:, 1]), Cc[:, 1])
    out = np.zeros(len(pts), int)
    for i, p in enumerate(pts):
        c = np.nonzero((xmin <= p[0]) & (xmax >= p[0]) & (zmin <= p[2]) & (zmax >= p[2]) & (ymin < p[1]))[0]
        if not len(c):
            continue
        a, b, cc = A[c], B[c], Cc[c]
        # xz の面での符号付き面積で内側を決める（上から見た三角形の向きによらない）
        def cr(u, v):
            return (v[:, 0] - u[:, 0]) * (p[2] - u[:, 2]) - (v[:, 2] - u[:, 2]) * (p[0] - u[:, 0])
        s1, s2, s3 = cr(a, b), cr(b, cc), cr(cc, a)
        inside = ((s1 > 0) & (s2 > 0) & (s3 > 0)) | ((s1 < 0) & (s2 < 0) & (s3 < 0))
        if not inside.any():
            continue
        a, b, cc = a[inside], b[inside], cc[inside]
        n = np.cross(b - a, cc - a)
        ok = np.abs(n[:, 1]) > 1e-14
        # 平面の式で p の真下の高さ
        yh = a[:, 1] - (n[:, 0] * (p[0] - a[:, 0]) + n[:, 2] * (p[2] - a[:, 2])) / np.where(ok, n[:, 1], 1.0)
        out[i] = int((ok & (yh < p[1])).sum())
    return out


def check150(tab, hero, near, far, jb, je, hz=240.0):
    n = len(tab["tau_e"])
    taus = np.arange(tab["tau_show"].min(), 1e-9, 1.0 / hz)
    taus = np.append(taus[taus < 0], 0.0)
    sh = Sheet(hero.R, hero.C); sn = Sheet(near.R, near.C); sf = Sheet(far.R, far.C)
    Tb = K.grid_tris(hero.R, hero.C, jb, je)
    Tn = K.grid_tris(near.R, near.C); Tf = K.grid_tris(far.R, far.C)
    rad = tab["radius"]
    sep = np.full(n, np.nan); back = np.zeros(n, int); inside = np.zeros(n, int)
    min_after = np.full(n, np.inf); d_t = np.full(n, np.nan)
    first_back = np.full(n, np.nan)
    for tau in taus:
        pos, r = SP.eval_state(tab, tau)
        alive = tau >= tab["tau_e"]
        if not alive.any():
            continue
        idx = np.nonzero(alive)[0]
        p = pos[idx]
        dm = np.full(len(idx), np.inf)
        Vh = hero.world(float(tau)).reshape(-1, 3); Vn = near.world(float(tau)).reshape(-1, 3); Vf = far.world(float(tau)).reshape(-1, 3)
        for V, shh in ((Vh, sh), (Vn, sn), (Vf, sf)):
            _, j = cKDTree(V).query(p)
            d, _s = shh.dist(V, p, j)
            dm = np.minimum(dm, d)
        A = np.concatenate([Vh[Tb[:, 0]], Vn[Tn[:, 0]], Vf[Tf[:, 0]]])
        B = np.concatenate([Vh[Tb[:, 1]], Vn[Tn[:, 1]], Vf[Tf[:, 1]]])
        Cc = np.concatenate([Vh[Tb[:, 2]], Vn[Tn[:, 2]], Vf[Tf[:, 2]]])
        ins = crossings_down(p, A, B, Cc) % 2 == 0
        clear = (dm >= rad[idx] + 0.10) & ~ins
        was = ~np.isnan(sep[idx])
        sep[idx[clear & ~was]] = tau
        bk = was & (dm < rad[idx] + 0.05)
        back[idx] += bk.astype(int); inside[idx] += ins.astype(int)
        fb = idx[(bk | ins) & np.isnan(first_back[idx])]
        first_back[fb] = tau
        min_after[idx[was]] = np.minimum(min_after[idx[was]], dm[was])
        if tau == 0.0:
            d_t[idx] = dm
    never = np.isnan(sep)
    bad = (back > 0) | (inside > 0)
    return dict(count=int(n), samples=int(len(taus)), hz=hz,
                pulled_back=int(bad.sum()), pulled_back_ids=[int(i) for i in np.nonzero(bad)[0]],
                returned_to_surface=int((back > 0).sum()), inside_water_any=int((inside > 0).sum()), never_separated=int(never.sum()),
                first_bad_tau=[float(v) for v in first_back[bad]],
                sep_after_s=dict(max=float(np.nanmax(sep - tab["tau_e"])), median=float(np.nanmedian(sep - tab["tau_e"]))),
                min_clearance_after_sep_m=float(np.min(min_after[np.isfinite(min_after)])),
                clearance_tstar_m=dict(min=float(np.nanmin(d_t)), median=float(np.nanmedian(d_t))),
                method_ja="パッケージの解析式だけから位置を出す。距離：主役波・近い海・遠い海の全体の網の、最も近い頂点のまわり 6 三角形への厳密な距離。"
                          "水の側：真下への半直線が描く水面（主役波の本体の列 18〜394・近い海・遠い海）を横切る数が偶数（生成器の真上の読みとは別の実装）。"
                          "放出の時刻から 240 Hz、t* まで。離れた＝距離 ≥ 半径 + 0.10 m かつ空気の側。"
                          "引き戻し＝離れた後に 半径 + 0.05 m より近づく、または放出の後いつでも水の側に入る")


def render_scene_with_spray(cam, tau, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere, hero_rows=None, only_hero=False, decim=1):
    if only_hero:
        Xh = hero.world(tau)
        r0, r1 = hero_rows if hero_rows else (0, hero.R - 1)
        X = Xh[r0:r1 + 1:decim, jb:je + 1:decim]
        T = K.grid_tris(X.shape[0], X.shape[1])
        tris = X.reshape(-1, 3)[T]; ids = np.full(len(T), K.CLS["hero_body"])
    else:
        tris, ids = K.scene_tris(tau, hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far)
    pos, rad = SP.eval_state(tab, tau)
    Vs, Fs = sphere
    live = np.nonzero(rad > 0)[0]
    if len(live):
        st = pos[live, None, :] + rad[live, None, None] * Vs[None, :, :]       # (n, 42, 3)
        stris = st[:, Fs, :].reshape(-1, 3, 3)
        sids = np.repeat(SPRAY_ID + live, len(Fs))
        tris = np.concatenate([tris, stris]); ids = np.concatenate([ids, sids])
    return K.raster_ids(cam, tris, ids)


def colorize(idb, spray_bgr):
    img = K.colorize(np.where(idb >= SPRAY_ID, 0, idb))
    img[idb >= SPRAY_ID] = spray_bgr
    return img


def check152(idb, tab, cam, spray_bgr, scene_img_no_spray):
    """粒子ごとの画素：外接箱の充填率、外周 1 px の色が飛沫なしの場面の色と同じか（黒い縁・光る縁がないか）。"""
    n = len(tab["tau_e"])
    res = []
    img = colorize(idb, spray_bgr)
    for i in range(n):
        m = idb == SPRAY_ID + i
        cnt = int(m.sum())
        if cnt == 0:
            res.append(dict(i=i, px=0))
            continue
        ys, xs = np.nonzero(m)
        bw, bh = xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
        fill = cnt / float(bw * bh)
        ring = cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~(idb >= SPRAY_ID)
        diff = np.abs(img[ring].astype(int) - scene_img_no_spray[ring].astype(int)).max() if ring.any() else 0
        inner_ok = bool(np.all(img[m] == np.array(spray_bgr, np.uint8)))
        res.append(dict(i=i, px=cnt, bbox=[int(bw), int(bh)], fill=float(fill), ring_px=int(ring.sum()), ring_max_diff=int(diff), inner_uniform=inner_ok))
    big = [r for r in res if r["px"] > 0 and min(r["bbox"]) >= 5]
    square = [r["i"] for r in big if r["fill"] > 0.95]
    edge = [r["i"] for r in res if r["px"] > 0 and (r["ring_max_diff"] > 0 or not r["inner_uniform"])]
    return dict(visible=int(sum(1 for r in res if r["px"] > 0)), invisible=[r["i"] for r in res if r["px"] == 0],
                bbox_ge5=len(big), fill_ge5=dict(min=(min(r["fill"] for r in big) if big else None), max=(max(r["fill"] for r in big) if big else None),
                                                 median=(float(np.median([r["fill"] for r in big])) if big else None)),
                square_base=len(square), square_ids=square, black_or_bright_edge=len(edge), edge_ids=edge, per_particle=res)


def de2000(l1, l2):
    L1, a1, b1 = l1; L2, a2, b2 = l2
    C1 = math.hypot(a1, b1); C2 = math.hypot(a2, b2); Cm = (C1 + C2) / 2
    G_ = 0.5 * (1 - math.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = a1 * (1 + G_), a2 * (1 + G_)
    C1p, C2p = math.hypot(a1p, b1), math.hypot(a2p, b2)
    h1p = math.degrees(math.atan2(b1, a1p)) % 360; h2p = math.degrees(math.atan2(b2, a2p)) % 360
    dLp = L2 - L1; dCp = C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dh = 0
    elif dh > 180:
        dh -= 360
    elif dh < -180:
        dh += 360
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin(math.radians(dh / 2))
    Lm = (L1 + L2) / 2; Cmp = (C1p + C2p) / 2
    hs = h1p + h2p
    if C1p * C2p == 0:
        hm = hs
    elif abs(h1p - h2p) > 180:
        hm = (hs + 360) / 2 if hs < 360 else (hs - 360) / 2
    else:
        hm = hs / 2
    T = 1 - 0.17 * math.cos(math.radians(hm - 30)) + 0.24 * math.cos(math.radians(2 * hm)) + 0.32 * math.cos(math.radians(3 * hm + 6)) - 0.20 * math.cos(math.radians(4 * hm - 63))
    dth = 30 * math.exp(-((hm - 275) / 25) ** 2)
    Rc = 2 * math.sqrt(Cmp ** 7 / (Cmp ** 7 + 25 ** 7))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / math.sqrt(20 + (Lm - 50) ** 2); Sc = 1 + 0.045 * Cmp; Sh = 1 + 0.015 * Cmp * T
    Rt = -math.sin(math.radians(2 * dth)) * Rc
    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))


def fit(img, w, h, bg=(196, 232, 249)):
    """縦横比を保って w×h に収め、余りを空の色で埋める（引き伸ばさない）。"""
    sc = min(w / img.shape[1], h / img.shape[0])
    im = cv2.resize(img, (max(1, int(round(img.shape[1] * sc))), max(1, int(round(img.shape[0] * sc)))), interpolation=cv2.INTER_AREA)
    out = np.empty((h, w, 3), np.uint8); out[:] = bg
    oy, ox = (h - im.shape[0]) // 2, (w - im.shape[1]) // 2
    out[oy:oy + im.shape[0], ox:ox + im.shape[1]] = im
    return out


def label(img, text, org=(12, 30), scale=0.8):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 3, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def side_cam(spec, hero, tau, kmeta):
    """側面の切り出し：波の枠に付いて動くカメラ。c = +60 m・高さ 7 m から −e（波峰線の逆）を見る。主役波の行 100〜190 だけを描く。"""
    fr = kmeta["frame"]
    e = np.array(fr["e_crest"]); t = np.array(fr["t_travel"])
    O = hero.origin(tau)
    tgt = O + 2.0 * t + np.array([0, 7.0, 0]) + (-1.0) * e
    pos = tgt + 60.0 * e
    return C27.Cam(spec, position=pos, target=tgt, vfov=22.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--skip", default="")
    args = ap.parse_args()
    skip = set(args.skip.split(",")) if args.skip else set()
    t0 = time.time()
    out = args.out
    fig = os.path.join(out, "fig"); os.makedirs(fig, exist_ok=True)
    meta, tab = load_pkg(out)
    table = S.load_json(os.path.join(out, "ds31_spray_table.json"))["particles"]
    spec = S.load_json(SP.TRUTH)
    cam = C27.Cam(spec)
    kmeta = S.load_json(REPO + "/Unity/Build/Design/28R01F/kstar_final/kstarR4_a45_meta.json")
    hero = K.Pkg(SP.HERO_PKG)
    near = K.Pkg(os.path.join(SP.SEA_DIR, "near")); far = K.Pkg(os.path.join(SP.SEA_DIR, "far"))
    idx30 = S.load_json(os.path.join(SP.SEA_DIR, "near", "ds30_ring0_index.json"))
    jb, je = idx30["body_cols"]
    cls_near = np.fromfile(os.path.join(SP.SEA_DIR, "near", "ds30_class_u8.bin"), np.uint8).reshape(near.R, near.C)
    cls_far = np.fromfile(os.path.join(SP.SEA_DIR, "far", "ds30_class_u8.bin"), np.uint8).reshape(far.R, far.C)
    boats = K.boats_tris(); ph = K.placeholder_tris()
    Vs, Fs = SP.icosphere1()
    sphere = (Vs, Fs)
    rgb = meta["colour_srgb8"]; spray_bgr = (rgb[2], rgb[1], rgb[0])
    M = dict(number="設計31", part="飛沫 v0", schema="GreatWave.DS31.spray_checks/1", renderer_ja="numpy（Unity の描画ではない）",
             package_sha256=dict(inst=meta["inst_sha256"], knots=meta["knots_sha256"]), count=int(len(tab["tau_e"])))

    # t* の位置の再投影（射線の上に置いたか）
    pos0, rad0 = SP.eval_state(tab, 0.0)
    xy, z = cam.project(pos0)
    tx = np.array([p["x_d"] for p in table]); ty = np.array([p["y_d"] for p in table])
    err = np.hypot(xy[:, 0] - tx, xy[:, 1] - ty)
    M["reprojection_tstar_px"] = dict(max=float(err.max()), median=float(np.median(err)))
    M["modes"] = dict(ballistic=int((tab["mode"] == 0).sum()), F8=int((tab["mode"] == 1).sum()))
    ang = np.array([p["angle_deg"] for p in table if p["angle_deg"] is not None])
    M["ballistic"] = dict(angle_deg_max=float(ang.max()), angle_deg_median=float(np.median(ang)),
                          speed_ratio=[float(min(p["speed_ratio"] for p in table)), float(max(p["speed_ratio"] for p in table))],
                          tau_e=[float(tab["tau_e"].min()), float(tab["tau_e"].max())],
                          fall_m=[float((tab["p_e"][:, 1] - pos0[:, 1]).min()), float((tab["p_e"][:, 1] - pos0[:, 1]).max())],
                          emit_after_twhite_min_s=float(min(p["tau_e"] - p["emitter"]["t_white"] for p in table if p["emitter"])),
                          layer_d_m=[float(min(p["layer_d_m"] for p in table)), float(max(p["layer_d_m"] for p in table))])
    print("reproj", M["reprojection_tstar_px"], "%.1fs" % (time.time() - t0))

    # 150
    if "150" not in skip:
        M["b150"] = check150(tab, hero, near, far, jb, je)
        print("150", {k: v for k, v in M["b150"].items() if k != "method_ja"}, "%.1fs" % (time.time() - t0))

    # t* の原画視点の描画と 152
    idb, zb = render_scene_with_spray(cam, 0.0, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere)
    tris, ids = K.scene_tris(0.0, hero, near, far, jb, je, "after", boats, ph, cls_near, cls_far)
    idb0, _ = K.raster_ids(cam, tris, ids)
    img0 = K.colorize(idb0)
    r152 = check152(idb, tab, cam, spray_bgr, img0)
    M["b152"] = {k: v for k, v in r152.items() if k != "per_particle"}
    M["b152"]["method_ja"] = ("原画視点の t*、1920×1080、無照明の単色の 42 頂点の球（instancing の網そのもの）。四角い下地＝外接箱 ≥5 px の粒子で充填率 > 0.95。"
                              "黒い縁・光る縁＝粒子の外周 1 px の色が飛沫なしの場面の色と違う、または粒子の内側が単色でない。numpy の描画なので、Unity の描画の確認は別")
    S.save_json(os.path.join(out, "ds31_spray_152_per_particle.json"), r152["per_particle"])
    print("152", {k: v for k, v in M["b152"].items() if k != "method_ja"}, "%.1fs" % (time.time() - t0))
    img = colorize(idb, spray_bgr)
    cv2.imwrite(os.path.join(fig, "ds31_spray_numpy_painting_tstar.png"), img)

    # 151（記録）：原画の点の色と飛沫の色
    labs = [p["lab_painting"] for p in table]
    des = [de2000(meta["colour_lab"], l) for l in labs]
    M["b151_record"] = dict(dE00_median=float(np.median(des)), dE00_p90=float(np.percentile(des, 90)), dE00_max=float(max(des)),
                            note_ja="原画の点の中心 3×3（高解像度の画素）の Lab と、飛沫の色（調色板の白）。点は小さく、紙の地・摺りのむらと混ざるので記録のみ")

    # 149（記録）
    M["b149_record"] = dict(dist_gap_0p2s_m=dict(min=float(min(p["dist_gap_m"] for p in table)), median=float(np.median([p["dist_gap_m"] for p in table]))),
                            dist_tstar_m=dict(min=float(min(p["dist_tstar_m"] for p in table)), median=float(np.median([p["dist_tstar_m"] for p in table]))),
                            sep_after_s_max=float(max(p["sep_after_s"] for p in table)),
                            note_ja="放出の 0.2 s 後と t* の、粒子から水面の頂点までの距離（生成器の読み）。t* ではどの点も原画視点で空の画素の上にある")

    # 図 1：原画と t* の比べ（切り出し）
    x0, y0, x1, y1 = 760, 250, 1300, 790
    paint = cv2.imread(os.path.join(REPO, "Tools", "PaintingTruth", "build", "painting_display.png"))
    pa = paint.copy()
    for p in table:
        cv2.circle(pa, (int(round(p["x_d"])), int(round(p["y_d"]))), int(max(3, p["diam_display_px"] / 2 + 3)), (0, 0, 255), 1, cv2.LINE_AA)
    A = cv2.resize(paint[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    B = cv2.resize(pa[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    Cc = cv2.resize(img[y0:y1, x0:x1], None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    label(A, "painting (Met JP1847)"); label(B, "extracted white dots: %d (zone)" % len(table)); label(Cc, "numpy render t* + spray v0 (not Unity)")
    cv2.imwrite(os.path.join(fig, "fig_ds31_spray_tstar_compare.png"), np.concatenate([A, B, Cc], 1))

    # 図 2：原画視点の τ の並び（切り出し）と側面の切り出し
    taus = [-1.0, -0.7, -0.45, -0.2, 0.0]
    wx0, wy0, wx1, wy1 = 360, 40, 1440, 820   # 動画と τ の並びの原画視点は広く切る（波が遠くから来るので）
    row_p, row_s = [], []
    for tau in taus:
        ib, _ = render_scene_with_spray(cam, tau, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere)
        im = colorize(ib, spray_bgr)[wy0:wy1, wx0:wx1].copy()
        label(im, "painting view tau %+.2f s" % tau, scale=0.7)
        row_p.append(im)
        cs = side_cam(spec, hero, tau, kmeta)
        ib2, _ = render_scene_with_spray(cs, tau, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere, hero_rows=(100, 190), only_hero=True)
        im2 = colorize(ib2, spray_bgr)
        # 軌跡（放出 → t*）を細線で
        O_now = hero.origin(tau)
        for i in range(len(tab["tau_e"])):
            if tau < tab["tau_e"][i]:
                continue
            tt = np.linspace(tab["tau_e"][i], tau, 24)
            pts = SP.traj(tab["p_e"][i], tab["v0"][i], tab["tau_e"][i], tt)
            # 波の枠に対する道のり（p(τ') − O(τ') + O(τ)）。枠に付いて動くカメラから見た、唇に対する飛沫の動き
            pts = pts - np.array([hero.origin(float(u)) for u in tt]) + O_now[None, :]
            q, _ = cs.project(pts)
            cv2.polylines(im2, [np.round(q).astype(np.int32).reshape(-1, 1, 2)], False, (60, 160, 255), 1, cv2.LINE_AA)
        im2 = fit(im2, wx1 - wx0, wy1 - wy0)
        label(im2, "side cutaway rows 100-190, paths relative to wave frame, tau %+.2f s" % tau, scale=0.6)
        row_s.append(im2)
        print("still", tau, "%.1fs" % (time.time() - t0))
    sheet = np.concatenate([np.concatenate(row_p, 1), np.concatenate(row_s, 1)], 0)
    cv2.imwrite(os.path.join(fig, "fig_ds31_spray_stills.png"), sheet)

    # 動画：τ −1.6 → t* の 1 s 後（30 fps、体験の時刻）。左＝原画視点の切り出し、右＝側面の切り出し
    if "video" not in skip:
        twj = S.load_json(SP.WARP)
        t_all = np.array(twj["t"]); tau_all = np.array(twj["tau"])
        tstart = float(np.interp(min(-1.4, float(tab["tau_e"].min()) - 0.05), tau_all, t_all))
        frames = np.arange(int(tstart * 30), int(13.0 * 30) + 1)
        vd = os.path.join(out, "_work", "video"); os.makedirs(vd, exist_ok=True)
        last = None
        for k, fno in enumerate(frames):
            tt = fno / 30.0
            if k % 2 == 1 and last is not None:
                # 描画は 2 コマに 1 回（15 fps の描画を 30 fps で並べる。numpy の描画の時間を減らすため）
                cv2.imwrite(os.path.join(vd, "f%04d.png" % k), last)
                continue
            tau = float(np.interp(tt, t_all, tau_all)) if tt < twj["t_star_s"] else 0.0
            ib, _ = render_scene_with_spray(cam, tau, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere, only_hero=False)
            im = colorize(ib, spray_bgr)[wy0:wy1, wx0:wx1].copy()
            cs = side_cam(spec, hero, tau, kmeta)
            ib2, _ = render_scene_with_spray(cs, tau, hero, near, far, jb, je, boats, ph, cls_near, cls_far, tab, sphere, hero_rows=(100, 190), only_hero=True, decim=1)
            im2 = fit(colorize(ib2, spray_bgr), wx1 - wx0, wy1 - wy0)
            frm = np.concatenate([im, im2], 1)
            hh = int(round(1920 * frm.shape[0] / frm.shape[1]))
            frm = cv2.resize(frm, (1920, hh), interpolation=cv2.INTER_AREA)
            canvas = np.zeros((1080, 1920, 3), np.uint8); o = (1080 - hh) // 2; canvas[o:o + hh] = frm
            label(canvas, "DS31 spray v0 (numpy, not Unity, 15 fps render)  t %.2f s  tau %+.3f s  left: painting view crop  right: side cutaway rows 100-190" % (tt, tau), (12, 40), 0.7)
            cv2.imwrite(os.path.join(vd, "f%04d.png" % k), canvas)
            last = canvas
            if k % 20 == 0:
                print("frame", k, len(frames), "%.1fs" % (time.time() - t0))
        mp4 = os.path.join(fig, "ds31_spray_numpy_30fps.mp4")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-framerate", "30", "-i", os.path.join(vd, "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", mp4], check=True)
        M["video"] = dict(file="fig/ds31_spray_numpy_30fps.mp4", frames=int(len(frames)), render_every=2, t_range_s=[float(frames[0] / 30.0), float(frames[-1] / 30.0)],
                          sha256=SP.sha(mp4))
    M["acceptance"] = {
        "150": dict(target="水面へ引き戻されるもの 0", value=M.get("b150", {}).get("pulled_back"), verdict=("合格" if M.get("b150", {}).get("pulled_back") == 0 else "不合格")),
        "152": dict(target="四角い下地・黒い縁 0（numpy の描画）", value=[M["b152"]["square_base"], M["b152"]["black_or_bright_edge"]],
                    verdict=("合格（numpy）" if M["b152"]["square_base"] == 0 and M["b152"]["black_or_bright_edge"] == 0 else "不合格")),
    }
    M["seconds"] = time.time() - t0
    S.save_json(os.path.join(out, "ds31_spray_checks.json"), M)
    print("done", M["acceptance"], "%.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
