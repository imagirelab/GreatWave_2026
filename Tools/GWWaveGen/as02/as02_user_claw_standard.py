# -*- coding: utf-8 -*-
"""美術の見本02（Q30-1）：利用者の爪の模型 claw_mid・claw_low（G:/research/model、利用者自身の作品。読み取りのみ。ファイルはリポジトリへ写さない）
を測り、どの爪も満たすべき「水準」を数にする → Unity/Build/Polish/sample02/claws/user_claw_standard.json（数だけ。形・頂点は書かない）。

測るもの（模型は x が厚みの向き、yz 面が爪の面。x = 0 で左右対称）：
  1. 背骨：面から見た輪郭（yz 面の塗り）を細線にし、2 つの角（下の左の端 BL と上の端 top）を結ぶ主の道。かかと（heel）は主の道から出る枝。
  2. 断面：背骨の各点で背骨に直交する平面でメッシュを切り、断面の幅（面の中、背骨に直交）と厚み（x）と、断面の塗りの割合
     （面積 /（幅 × 厚み）：楕円 0.785、レンズ（2 つの円弧）約 0.67、菱形 0.5）。
  3. 先の細り：先から測った長さの割合 u（先 0）での幅 / 最大幅。べき乗の当てはめ w ∝ u^p（先の 30% の範囲）。
  4. 先の鋭さ：面から見た輪郭の先の角（先から最大幅の 15% の長さの所の両側の輪郭の向きの開き）と、先の丸みの半径 / 最大幅。
  5. かかと：主の道の外側の輪郭からかかとの先までの出っ張り / 最大幅と、その位置（背骨の割合）。
  6. 滑らかさ：背骨の曲率 κ(s)（最大幅で無次元化）の変化の大きさ（隣どうしの差の p95・最大）、面の隣どうしの面の折れ角（p50・p95・最大）、
     輪郭の曲率の符号の変わる回数（でこぼこの数）。
使い方（リポジトリの根で）：py -3.10 -B Tools/GWWaveGen/as02/as02_user_claw_standard.py
"""
import hashlib
import json
import os
import sys
import time

import cv2
import numpy as np
from scipy import ndimage
from skimage.morphology import skeletonize

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from as02_mini_render import read_obj, silhouette_ortho, outline_lumps  # noqa: E402

SRC = {"claw_mid": "G:/research/model/claw_mid.obj", "claw_low": "G:/research/model/claw_low.obj"}
OUT = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample02/claws/user_claw_standard.json"
SC = 400.0          # 1 m あたりの画素（面から見た塗り）
SIZE = (2000, 2000)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def px_to_yz(rc):
    """塗りの画像の (行, 列) → (y, z)。face-on は見る向き −x、上 +y、右 = 上 × 前 = +z。"""
    r, c = rc[..., 0], rc[..., 1]
    return np.stack([(SIZE[1] * 0.5 - r) / SC, (c - SIZE[0] * 0.5) / SC], -1)


def skel_path(sk, a, b):
    """細線の上の a → b の最短の道（8 近傍の幅優先）。"""
    H, W = sk.shape
    prev = -np.ones((H, W, 2), np.int32)
    seen = np.zeros_like(sk, bool)
    q = [tuple(a)]
    seen[a[0], a[1]] = True
    head = 0
    while head < len(q):
        y, x = q[head]
        head += 1
        if (y, x) == tuple(b):
            break
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and sk[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    prev[yy, xx] = (y, x)
                    q.append((yy, xx))
    path = [tuple(b)]
    while path[-1] != tuple(a):
        p = prev[path[-1][0], path[-1][1]]
        if p[0] < 0:
            break
        path.append((int(p[0]), int(p[1])))
    return np.array(path[::-1])


def resample(P, n):
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    s = np.linspace(0, d[-1], n)
    return np.stack([np.interp(s, d, P[:, k]) for k in range(P.shape[1])], -1), d[-1]


def smooth_curve(P, it=30):
    Q = P.copy()
    for _ in range(it):
        Q[1:-1] = 0.5 * Q[1:-1] + 0.25 * (Q[:-2] + Q[2:])
    return Q


def section(V, F, P, T):
    """点 P（3 次元）を通り法線 T の平面でメッシュを切った線分のうち、P に最も近いつながりの点。戻り値 (k×3)。"""
    d = (V - P) @ T
    tri = F
    dv = d[tri]
    s = np.sign(dv)
    cross = (s.max(1) > 0) & (s.min(1) < 0)
    pts = []
    for t in np.nonzero(cross)[0]:
        ids = tri[t]
        seg = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            di, dj = d[ids[i]], d[ids[j]]
            if (di > 0) != (dj > 0):
                a = di / (di - dj)
                seg.append(V[ids[i]] + a * (V[ids[j]] - V[ids[i]]))
        if len(seg) == 2:
            pts.append(seg)
    if not pts:
        return None
    S = np.array(pts)  # m × 2 × 3
    mid = S.mean(1)
    # P から 1.2 m 以内の線分だけ（反対の腕の断面を混ぜない）
    keep = np.linalg.norm(mid - P, axis=1) < 0.9
    S = S[keep]
    return S.reshape(-1, 3) if len(S) else None


def measure(name):
    V, F = read_obj(SRC[name])
    m = silhouette_ortho(V, F, (-1, 0, 0), (0, 1, 0), SIZE, np.zeros(3), SC) > 0
    dt = ndimage.distance_transform_edt(m) / SC
    sk = skeletonize(m)
    K = ndimage.convolve(sk.astype(int), np.ones((3, 3)), mode="constant")
    ep = np.argwhere(sk & (K == 2))
    yz = px_to_yz(ep.astype(float))
    top = ep[np.argmax(yz[:, 0])]
    bl = ep[np.argmin(yz[:, 1] + 0.0 * yz[:, 0])]      # いちばん左（−z）
    heel = [e for e in ep if not (np.array_equal(e, top) or np.array_equal(e, bl))]
    path = skel_path(sk, bl, top)
    P2 = px_to_yz(path.astype(float))
    P2s = smooth_curve(P2, 60)
    Pn, L = resample(P2s, 201)
    s = np.linspace(0, 1, len(Pn))
    # 背骨の 3 次元（x = 0）と接線
    P3 = np.stack([np.zeros(len(Pn)), Pn[:, 0], Pn[:, 1]], -1)
    T3 = np.gradient(P3, axis=0)
    T3 /= np.linalg.norm(T3, axis=1, keepdims=True)
    width, thick, fill = [], [], []
    for i in range(len(P3)):
        S = section(V, F, P3[i], T3[i])
        if S is None:
            width.append(np.nan); thick.append(np.nan); fill.append(np.nan)
            continue
        B = np.array([0.0, -T3[i, 2], T3[i, 1]])
        B /= np.linalg.norm(B)
        a = (S - P3[i]) @ B
        b = S[:, 0]
        w = a.max() - a.min()
        t = b.max() - b.min()
        # 断面の多角形の面積（点を角度で並べる）
        c2 = np.stack([a - a.mean(), b - b.mean()], -1)
        ang = np.arctan2(c2[:, 1], c2[:, 0])
        o = np.argsort(ang)
        q = c2[o]
        area = 0.5 * abs(np.dot(q[:, 0], np.roll(q[:, 1], -1)) - np.dot(q[:, 1], np.roll(q[:, 0], -1)))
        width.append(w); thick.append(t); fill.append(area / max(w * t, 1e-12))
    width = np.array(width); thick = np.array(thick); fill = np.array(fill)
    # 面から見た幅（塗りの距離変換 × 2）も背骨の上で
    rc = np.stack([SIZE[1] * 0.5 - Pn[:, 0] * SC, Pn[:, 1] * SC + SIZE[0] * 0.5], -1)
    w_face = 2 * ndimage.map_coordinates(dt, rc.T, order=1)
    # 背骨の曲率
    d1 = np.gradient(Pn, axis=0) / (L / (len(Pn) - 1))
    d2 = np.gradient(d1, axis=0) / (L / (len(Pn) - 1))
    kap = (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]) / np.maximum(np.linalg.norm(d1, axis=1) ** 3, 1e-12)
    wmax = np.nanmax(w_face)
    turn = float(np.degrees(np.sum(kap[1:-1]) * L / (len(Pn) - 1)))
    kap_n = kap * wmax
    dk = np.abs(np.diff(kap_n[5:-5]))
    # 根元：厚みの最大の側。先：もう一方の端
    thick_f = np.where(np.isnan(thick), 0, thick)
    root_end = "BL" if np.argmax(thick_f) < len(thick_f) / 2 else "top"
    # 先の細り（top 端を先とする。BL 端も同じに測る）
    def taper(end):
        if end == "top":
            u = 1 - s
            w = w_face
        else:
            u = s
            w = w_face
        sel = (u > 0.01) & (u < 0.30)
        p = np.polyfit(np.log(u[sel]), np.log(np.maximum(w[sel], 1e-6) / wmax), 1)
        prof = {f"{x:.2f}": round(float(np.interp(x, u[::-1] if end == 'top' else u, (w / wmax)[::-1] if end == 'top' else w / wmax)), 4)
                for x in (0.02, 0.05, 0.10, 0.20, 0.30, 0.50)}
        return {"power_p_w_prop_u^p_tip30pct": round(float(p[0]), 3), "w_over_wmax_at_u": prof}
    # 先の鋭さ（輪郭の角）：先の点から長さ 0.15·wmax・0.3·wmax の所で、輪郭の両側の点の開き
    cs, _ = cv2.findContours(m.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    C = max(cs, key=len)[:, 0, :].astype(float)   # (x=列, y=行)
    Cyz = np.stack([(SIZE[1] * 0.5 - C[:, 1]) / SC, (C[:, 0] - SIZE[0] * 0.5) / SC], -1)

    def tip_angle(end_rc):
        e = px_to_yz(end_rc.astype(float))
        # 輪郭の上で端の点に最も近い所
        i0 = np.argmin(np.linalg.norm(Cyz - e, axis=1))
        n = len(Cyz)
        out = {}
        for frac in (0.15, 0.30):
            r = frac * wmax
            def walk(sgn):
                acc = 0.0
                i = i0
                while acc < r:
                    j = (i + sgn) % n
                    acc += np.linalg.norm(Cyz[j] - Cyz[i])
                    i = j
                return Cyz[i]
            a, b = walk(1), walk(-1)
            tip = Cyz[i0]
            va, vb = a - tip, b - tip
            ang = np.degrees(np.arccos(np.clip(va @ vb / np.linalg.norm(va) / np.linalg.norm(vb), -1, 1)))
            out[f"angle_deg_at_{frac:.2f}wmax"] = round(float(ang), 2)
        # 先の丸みの半径：端の点の周り（±0.05 wmax の道のり）の 3 点の外接円
        acc = 0.0
        i = i0
        r = 0.05 * wmax
        ia = ib = i0
        while acc < r:
            ia2 = (ia + 1) % n; acc += np.linalg.norm(Cyz[ia2] - Cyz[ia]); ia = ia2
        acc = 0.0
        while acc < r:
            ib2 = (ib - 1) % n; acc += np.linalg.norm(Cyz[ib2] - Cyz[ib]); ib = ib2
        p1, p2, p3 = Cyz[ia], Cyz[i0], Cyz[ib]
        A = np.linalg.norm(p2 - p1); Bl = np.linalg.norm(p3 - p2); Cc = np.linalg.norm(p3 - p1)
        cr = abs((p2 - p1)[0] * (p3 - p1)[1] - (p2 - p1)[1] * (p3 - p1)[0]) / 2
        R = A * Bl * Cc / max(4 * cr, 1e-12)
        out["tip_radius_over_wmax"] = round(float(R / wmax), 4)
        out["halfwidth_dt_at_end_over_wmax"] = round(float(dt[end_rc[0], end_rc[1]] * 2 / wmax), 4)
        return out
    # かかと：枝の先の点と、主の道の外の輪郭の距離
    heel_rec = None
    if heel:
        h = heel[0]
        hyz = px_to_yz(h.astype(float))
        hp = skel_path(sk, h, path[len(path) // 2])
        # 主の道に合流する所
        on_main = set(map(tuple, path))
        j = next((k for k, p in enumerate(hp) if tuple(p) in on_main), len(hp) - 1)
        join = px_to_yz(hp[j].astype(float))
        sj = float(np.argmin(np.linalg.norm(Pn - join, axis=1)) / (len(Pn) - 1))
        # 出っ張り：枝の先の点の円（dt）の外の縁が、合流点の円の外の縁からどれだけ出るか
        dt_h = dt[h[0], h[1]]
        dt_j = dt[hp[j][0], hp[j][1]]
        prot = np.linalg.norm(hyz - join) + dt_h - dt_j
        heel_rec = {"position_s_from_BL": round(sj, 3), "branch_len_over_wmax": round(float(np.linalg.norm(hyz - join) / wmax), 3),
                    "protrusion_over_wmax": round(float(prot / wmax), 3), "heel_end_halfwidth_over_wmax": round(float(dt_h / wmax), 3)}
    # 面の折れ角
    Tm = V[F]
    n = np.cross(Tm[:, 1] - Tm[:, 0], Tm[:, 2] - Tm[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    edges = {}
    for ti, tri in enumerate(F):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            edges.setdefault((min(a, b), max(a, b)), []).append(ti)
    dih = np.array([np.degrees(np.arccos(np.clip(n[t[0]] @ n[t[1]], -1, 1))) for t in edges.values() if len(t) == 2])
    # 輪郭の曲率の符号の変わり（でこぼこ）：輪郭を wmax の 4% で平らにしてから
    Cs = Cyz.copy()
    k_s = max(int(0.04 * wmax * SC), 2)
    Cs = ndimage.uniform_filter1d(Cs, size=2 * k_s + 1, axis=0, mode="wrap")
    Cr, _ = resample(np.vstack([Cs, Cs[:1]]), 400)
    e1 = np.gradient(Cr, axis=0); e2 = np.gradient(e1, axis=0)
    kc = e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]
    kc = ndimage.uniform_filter1d(kc, 9, mode="wrap")
    sign_changes = int(np.sum(np.sign(kc[:-1]) != np.sign(kc[1:])))
    rec = {
        "source": {"path": SRC[name], "sha256": sha(SRC[name]), "vertices": int(len(V)), "triangles_after_split": int(len(F))},
        "bbox_m": {"x_thickness": round(float(np.ptp(V[:, 0])), 4), "y": round(float(np.ptp(V[:, 1])), 4), "z": round(float(np.ptp(V[:, 2])), 4)},
        "spine_from_BL_to_top": {"arc_length": round(float(L), 4), "chord": round(float(np.linalg.norm(Pn[-1] - Pn[0])), 4),
                                 "total_turn_deg": round(turn, 1), "wmax_face": round(float(wmax), 4),
                                 "length_over_wmax": round(float(L / wmax), 3)},
        "root_end_by_thickness": root_end,
        "profile_s": [round(float(x), 3) for x in s[::10]],
        "width_face_over_wmax": [round(float(x), 4) for x in (w_face / wmax)[::10]],
        "section_width": [None if np.isnan(x) else round(float(x), 4) for x in width[::10]],
        "section_thickness": [None if np.isnan(x) else round(float(x), 4) for x in thick[::10]],
        "width_over_thickness": [None if (np.isnan(a) or np.isnan(b) or b <= 0) else round(float(a / b), 3) for a, b in zip(width[::10], thick[::10])],
        "section_fill_ratio": [None if np.isnan(x) else round(float(x), 3) for x in fill[::10]],
        "width_over_thickness_median_mid60": round(float(np.nanmedian((width / thick)[40:161])), 3),
        "section_fill_median_mid60": round(float(np.nanmedian(fill[40:161])), 3),
        "taper_top_end": taper("top"),
        "taper_BL_end": taper("BL"),
        "tip_top": tip_angle(top),
        "tip_BL": tip_angle(bl),
        "heel": heel_rec,
        "spine_curvature_x_wmax": {"max_abs": round(float(np.nanmax(np.abs(kap_n[5:-5]))), 3), "jump_p95": round(float(np.percentile(dk, 95)), 4),
                                   "jump_max": round(float(dk.max()), 4)},
        "dihedral_deg": {"p50": round(float(np.percentile(dih, 50)), 2), "p95": round(float(np.percentile(dih, 95)), 2), "max": round(float(dih.max()), 2)},
        "outline_curvature_sign_changes": sign_changes,
        "outline_lumps_hysteresis": outline_lumps(Cyz, wmax),
        "outline_lumps_note_ja": "輪郭を最大幅の 4% でならし、曲率 × 最大幅 が ±0.15 を超える所の符号の入れ替わりの回数（ほぼまっすぐな所の揺れは数えない。爪と同じ関数 as02_mini_render.outline_lumps）",
    }
    return rec


def main():
    t0 = time.time()
    out = {"schema": "GreatWave.AS02.user_claw_standard/1",
           "note_ja": "利用者の爪の模型（利用者自身の作品、Q30-1）を測った数だけ。形・頂点・画像は書かない。模型のファイルはリポジトリへ写さない。",
           "axes_ja": "模型の x＝厚み（左右対称）、yz＝爪の面。背骨は面から見た塗りの細線の BL 端（下の左）→ top 端（上）。",
           "models": {}}
    for k in SRC:
        out["models"][k] = measure(k)
    out["elapsed_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])


if __name__ == "__main__":
    main()
