# -*- coding: utf-8 -*-
"""美術の見本02（Q30）爪の部：小さなメッシュ（爪 1 本・利用者の模型）を確かめるための numpy＋OpenCV の描画（Unity の描画ではない）。

- 正射影または透視のカメラで、三角形を奥から順に塗る（画家の方法。爪 1 本の大きさなら十分）。
- 色は面の向きの陰（Lambert）と、縁の線（輪郭と折れ）。見本の図の「面から見た形」「3/4」「利用者の模型との大きさの比べ」に使う。
参照モデル（OBJ）は読まない。利用者の模型（claw_low・claw_mid）はメモリの中で読むだけで、形・画像をリポジトリへ入れない（図は Git 対象外の Build へ）。
"""
import numpy as np
import cv2


def read_obj(path):
    V, F = [], []
    for l in open(path, encoding="utf-8", errors="ignore"):
        if l.startswith("v "):
            V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith("f "):
            p = [int(x.split("/")[0]) - 1 for x in l.split()[1:]]
            for j in range(1, len(p) - 1):
                F.append([p[0], p[j], p[j + 1]])
    return np.array(V, np.float64), np.array(F, np.int64)


def look_basis(view_dir, up=(0.0, 1.0, 0.0)):
    f = np.asarray(view_dir, np.float64)
    f = f / np.linalg.norm(f)
    u = np.asarray(up, np.float64)
    u = u - (u @ f) * f
    if np.linalg.norm(u) < 1e-6:
        u = np.array([0.0, 0.0, 1.0]) - f[2] * f
    u /= np.linalg.norm(u)
    r = np.cross(u, f)
    return r, u, f


def render_ortho(V, F, view_dir, up=(0.0, 1.0, 0.0), size=(400, 400), center=None, scale=None, colors=None,
                 bg=(255, 255, 255), light=(0.3, 0.8, -0.5), line=(40, 40, 60), line_w=1, margin=0.08, crease_deg=50.0):
    """正射影。view_dir はカメラの見る向き（世界）。scale は 1 m あたりの画素（None なら収まる大きさ）。戻り値 (BGR 画像, scale, center)。"""
    W, H = size
    r, u, f = look_basis(view_dir, up)
    if center is None:
        center = 0.5 * (V.min(0) + V.max(0))
    d = V - center
    x, y, z = d @ r, d @ u, d @ f
    if scale is None:
        ext = max(np.ptp(x), np.ptp(y) * W / H, 1e-9)
        scale = (1 - 2 * margin) * W / ext
    px = np.stack([W * 0.5 + x * scale, H * 0.5 - y * scale], -1)
    img = np.full((H, W, 3), bg, np.uint8)
    T = V[F]
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    nn = np.linalg.norm(n, axis=1, keepdims=True)
    n = n / np.maximum(nn, 1e-12)
    L = np.asarray(light, np.float64)
    L /= np.linalg.norm(L)
    # 両面：カメラへ向く側の法線で陰を付ける
    facing = (n @ f) < 0
    ns = np.where(facing[:, None], n, -n)
    lam = np.clip(ns @ (-L if False else L), 0, 1)
    shade = 0.45 + 0.55 * lam
    zc = z[F].mean(1)
    order = np.argsort(-zc)  # 奥（z 大）から
    for t in order:
        pts = np.round(px[F[t]] * 16).astype(np.int32)
        if colors is None:
            col = np.array([235, 240, 245], np.float64)
        else:
            col = np.asarray(colors[t], np.float64)
        c = tuple(int(v) for v in np.clip(col * shade[t], 0, 255))
        cv2.fillConvexPoly(img, pts, c, lineType=cv2.LINE_AA, shift=4)
    if line_w > 0:
        # 輪郭（前向きと後ろ向きの境）と折れの辺
        edges = {}
        for ti, tri in enumerate(F):
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                k = (min(a, b), max(a, b))
                edges.setdefault(k, []).append(ti)
        segs = []
        cosc = np.cos(np.radians(crease_deg))
        for (a, b), ts in edges.items():
            if len(ts) == 1:
                segs.append((a, b))
            elif len(ts) == 2:
                t0, t1 = ts
                if facing[t0] != facing[t1] or (n[t0] @ n[t1]) < cosc:
                    segs.append((a, b))
        # 線は前の面に隠れるものも描く（爪 1 本の確かめの図なので簡単にする）
        for a, b in segs:
            p0 = tuple(np.round(px[a] * 16).astype(int))
            p1 = tuple(np.round(px[b] * 16).astype(int))
            cv2.line(img, p0, p1, line, line_w, cv2.LINE_AA, shift=4)
    return img, scale, center


def silhouette_ortho(V, F, view_dir, up, size, center, scale):
    """同じ正射影での塗りのマスク（0/255）。"""
    W, H = size
    r, u, f = look_basis(view_dir, up)
    d = V - center
    px = np.stack([W * 0.5 + (d @ r) * scale, H * 0.5 - (d @ u) * scale], -1)
    m = np.zeros((H, W), np.uint8)
    for tri in F:
        cv2.fillConvexPoly(m, np.round(px[tri] * 16).astype(np.int32), 255, lineType=cv2.LINE_8, shift=4)
    return m


def outline_lumps(C, w_ref, eps=0.15, n=400):
    """閉じた輪郭 C（k×2）の「でこぼこ」の数：幅 w_ref の 4% の窓でならし、n 点に分け、曲率 × w_ref が +eps より大きい所と −eps より小さい所の
    入れ替わりの回数（ヒステリシス。ほぼまっすぐな所の小さな揺れは数えない）。利用者の模型と爪で同じ関数を使う。"""
    import numpy as _np
    from scipy import ndimage as _nd
    P = _np.vstack([C, C[:1]])
    d = _np.r_[0, _np.cumsum(_np.linalg.norm(_np.diff(P, axis=0), axis=1))]
    s = _np.linspace(0, d[-1], n + 1)[:-1]
    Q = _np.stack([_np.interp(s, d, P[:, k]) for k in range(2)], -1)
    ds = d[-1] / n
    k_s = max(int(round(0.04 * w_ref / ds)), 1)
    Q = _nd.uniform_filter1d(Q, size=2 * k_s + 1, axis=0, mode="wrap")
    a1 = (_np.roll(Q, -1, 0) - _np.roll(Q, 1, 0)) / (2 * ds)
    a2 = (_np.roll(Q, -1, 0) - 2 * Q + _np.roll(Q, 1, 0)) / (ds * ds)
    kap = (a1[:, 0] * a2[:, 1] - a1[:, 1] * a2[:, 0]) / _np.maximum(_np.linalg.norm(a1, axis=1) ** 3, 1e-12) * w_ref
    kap = _nd.uniform_filter1d(kap, 5, mode="wrap")
    st = _np.where(kap > eps, 1, _np.where(kap < -eps, -1, 0))
    st = st[st != 0]
    if len(st) < 2:
        return 0
    return int(_np.sum(st != _np.roll(st, 1)))
