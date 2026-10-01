# -*- coding: utf-8 -*-
"""仕上げ32 修正の回 1：爪の一覧の直し（pl32_claw_list.py --fix01 から呼ぶ。numpy・OpenCV。Unity の描画ではない）。

審査の指摘（計画 §5.3 仕上げ32 の行）に対して、次の 3 つを一覧に足す。
  1. 利用者の 100 本の位置合わせが不確かな爪（ECC の後の NCC < 0.70）の位置合わせのし直し（reregister）。
     設計32 の ds32_user100_register.py は倍率だけを探し、回転を探さなかった。ここでは同じ切り抜き（G:/research/爪形分析、読み取りのみ。
     画像・マスクは複製しない。メモリの中だけ）を、回転 −14〜+14°（2° おき）× 倍率 40 段で粗く探し、細かく詰め、ECC（アフィン）で仕上げる。
     NCC ≥ 0.70 になった爪は「確か」とし、ほかは「不確かのまま」とする。
  2. 利用者の 100 本で一覧に対応がない爪を加える（user100_additions）：主浪の左の群の下側（範囲の外）の爪と、位置合わせのし直しで
     確かになった爪は、利用者の根元・先端を種に、通れる画素の最短路（設計32 の path_between）で中心線を作って主浪の爪として加える
     （既存の爪の中心線・領域と 40% 以上重なるなら加えずに対応とする）。手前の波の爪は、手前の波（設計30 の海）に爪の層がないので、
     一覧に zone "front" の爪として加える（主役波のシートには結び付けない。右側の爪と同じ扱い）。同じ画像の利用者の爪（claw069／076）と、
     同じ所に合う爪（claw098／099）は 1 本にまとめる。
  3. 根元の先で指が続く爪の根元を、指の溝に沿って延ばす（extend_roots。名前の付いた決まり pl32f_root_extend）：
     根元から根元の側へ 2 px ずつ、断面の両側が藍（墨版の線）に閉じ、幅が根元の近くの幅の 1.5 倍 + 6 px 以下で、
     1 歩の幅の変化 ≤ max(6 px, 35%)・中心のずれ ≤ 4 px（同じ 2 本の線が続く）間だけ、断面の真ん中へ寄せながら進む（最大 80 px）。
     ほかの爪の中心線から 3 px に入ったら止める。6 px 以上延びた爪だけ根元を替える。
"""
import json
import math
import os

import cv2
import numpy as np

USER = "G:/research/爪形分析"
CROPS = USER + "/final_100_claws_centerlines_from_fill_masks_v3"
POINTS = USER + "/final_100_claw_structural_points_v2/final_points_long.csv"


def _imread_u(p, flag):
    return cv2.imdecode(np.fromfile(p, np.uint8), flag)


def _ncc(a, b):
    a = a.astype(np.float64) - a.mean()
    b = b.astype(np.float64) - b.mean()
    d = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else 0.0


def _rot_scale(tpl, s, ang):
    h, w = tpl.shape
    M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), ang, s)
    c, si = abs(M[0, 0]), abs(M[0, 1])
    W2, H2 = int(math.ceil(w * c + h * si)), int(math.ceil(w * si + h * c))
    M[0, 2] += W2 / 2.0 - w / 2.0
    M[1, 2] += H2 / 2.0 - h / 2.0
    img = cv2.warpAffine(tpl, M, (W2, H2), flags=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC, borderValue=float(tpl.mean()))
    msk = cv2.warpAffine(np.full_like(tpl, 255), M, (W2, H2), flags=cv2.INTER_NEAREST, borderValue=0)
    return img, msk, M


def reregister(paint_path, user_ids, near=None, half=260):
    """回転つきの位置合わせ。設計32 の位置（near[user_id] = 根元の原画 px）の ±half px の中を探す（回転で切り抜きの角が空く所は切り抜きの平均の明るさで埋める）。
    戻り値：user_id → dict（A_crop_to_ref、ncc_after_ecc、回転、倍率、peak_margin）。"""
    import csv
    G = cv2.cvtColor(_imread_u(paint_path, cv2.IMREAD_COLOR), cv2.COLOR_BGR2GRAY)
    G2 = cv2.resize(G, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    pts = {}
    with open(POINTS, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            pts.setdefault(r["claw_id"], []).append(r)
    out = {}
    for uid in user_ids:
        tpl = _imread_u(CROPS + "/" + uid + "/original.png", cv2.IMREAD_GRAYSCALE)
        cx0, cy0 = near[uid]
        x0 = int(max(0, cx0 - half - 300)) // 2 * 2; y0 = int(max(0, cy0 - half - 300)) // 2 * 2
        x1 = int(min(G.shape[1], cx0 + half + 300)); y1 = int(min(G.shape[0], cy0 + half + 300))
        sub2 = G2[y0 // 2:y1 // 2, x0 // 2:x1 // 2]
        best = (-2, None)
        for ang in np.arange(-14, 14.01, 2.0):
            for s in np.geomspace(0.08, 0.70, 40):
                ts, tm, _ = _rot_scale(tpl, s * 0.5, ang)
                if min(ts.shape) < 10 or ts.shape[0] >= sub2.shape[0] or ts.shape[1] >= sub2.shape[1]:
                    continue
                r = cv2.matchTemplate(sub2, ts, cv2.TM_CCORR_NORMED if False else cv2.TM_CCOEFF_NORMED, mask=None)
                _, mx, _, ml = cv2.minMaxLoc(r)
                if mx > best[0]:
                    best = (mx, (s, ang, ml, ts.shape))
        mx0, (s0, a0, ml, shp) = best
        cx, cy = x0 + ml[0] * 2, y0 + ml[1] * 2
        fine = (-2, None)
        for ang in np.arange(a0 - 2, a0 + 2.01, 0.5):
            for f in np.linspace(0.92, 1.08, 17):
                s = s0 * f
                ts, tm, M = _rot_scale(tpl, s, ang)
                h, w = ts.shape
                X0, Y0 = max(0, cx - 20), max(0, cy - 20)
                win = G[Y0:min(G.shape[0], cy + 20 + h), X0:min(G.shape[1], cx + 20 + w)]
                if win.shape[0] < h or win.shape[1] < w:
                    continue
                r = cv2.matchTemplate(win, ts, cv2.TM_CCOEFF_NORMED)
                _, mx, _, l = cv2.minMaxLoc(r)
                if mx > fine[0]:
                    fine = (mx, (s, ang, (X0 + l[0], Y0 + l[1]), M))
        mxf, (sf, af, (tx, ty), M) = fine
        # 切り抜き → 原画（回転と倍率の M の後に平行移動）
        A0 = M.astype(np.float64).copy()
        A0[:, 2] += [tx, ty]
        # 2 番目の峰（粗の画像、同じ回転・倍率、最良から 15 px（粗）を除く）
        ts2, _, _ = _rot_scale(tpl, sf * 0.5, af)
        r2 = cv2.matchTemplate(sub2, ts2, cv2.TM_CCOEFF_NORMED)
        bx, by = (tx - x0) / 2.0, (ty - y0) / 2.0
        yy, xx = np.mgrid[0:r2.shape[0], 0:r2.shape[1]]
        second = float(np.where(np.hypot(xx - bx, yy - by) > 15, r2, -2).max())
        tplf = cv2.GaussianBlur(tpl.astype(np.float32), (0, 0), 1.0)
        Gf = cv2.GaussianBlur(G.astype(np.float32), (0, 0), max(1.0, sf))
        warp = A0.astype(np.float32).copy()
        ok = True
        try:
            _, warp = cv2.findTransformECC(tplf, Gf, warp, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), None, 5)
        except cv2.error:
            ok = False
        h, w = tpl.shape
        back0 = cv2.warpAffine(G, A0, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        n0 = _ncc(back0, tpl)
        A1 = warp.astype(np.float64) if ok else A0
        back1 = cv2.warpAffine(G, A1, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REPLICATE)
        n1 = _ncc(back1, tpl)
        corners = np.array([[0, 0, 1], [w - 1, 0, 1], [0, h - 1, 1], [w - 1, h - 1, 1]], np.float64)
        dev = float(np.hypot(*((corners @ A1.T) - (corners @ A0.T)).T).max())
        use = ok and n1 >= n0 and dev <= 0.25 * sf * max(h, w)
        A = A1 if use else A0
        P_ = sorted(pts.get(uid, []), key=lambda q: int(q["point_order"]))
        xy = np.array([[float(q["x"]), float(q["y"])] for q in P_], np.float64)
        xy_ref = np.c_[xy, np.ones(len(xy))] @ A.T if len(xy) else xy
        m = _imread_u(CROPS + "/" + uid + "/fill_mask.png", cv2.IMREAD_GRAYSCALE) > 127
        out[uid] = dict(rotation_deg=round(float(af), 2), scale=round(float(sf), 5), ncc_template=round(float(mxf), 4),
                        peak_margin=round(float(mxf - second), 4), ncc_similarity=round(n0, 4), ncc_after_ecc=round(n1 if use else n0, 4),
                        ecc_used=bool(use), A_crop_to_ref=np.round(A, 6).tolist(),
                        root_ref=np.round(xy_ref[0], 2).tolist() if len(xy_ref) else None,
                        tip_ref=np.round(xy_ref[-1], 2).tolist() if len(xy_ref) else None,
                        points_ref=np.round(xy_ref, 2).tolist(), _mask=m, _A=A)
    return out


def mask_to_ref(m, A, shape):
    """利用者のマスク（切り抜きの座標）を原画の画素へ写す（メモリの中だけ）。"""
    H, W = shape
    return cv2.warpAffine(m.astype(np.uint8), A, (W, H), flags=cv2.INTER_NEAREST, borderValue=0).astype(bool)


def extend_root(L32, paint, cl_ref, block, max_ext=80.0, step=2.0, continuity=True):
    """pl32f_root_extend：根元から根元の側へ、指の溝（同じ 2 本の線）に沿って延ばす。戻り値：延ばした点（原画の局所 px、根元から外へ）。"""
    cl = paint.loc(cl_ref)
    if len(cl) < 4:
        return np.zeros((0, 2)), None
    d = cl[0] - cl[3]
    d /= max(np.linalg.norm(d), 1e-9)
    near = cl[:min(6, len(cl))]
    nn, _ = L32.normals(near) if len(near) >= 3 else (np.repeat(np.array([[-d[1], d[0]]]), len(near), 0), None)
    sn = L32.sections(paint, near, nn)
    okn = (sn["wl"] == 1) & (sn["wr"] == 1)
    wn = (sn["dl"] + sn["dr"])[okn]
    w0 = float(np.median(wn)) if len(wn) else float(np.median(sn["dl"] + sn["dr"]))
    p = cl[0].copy()
    pts = []
    wprev = None
    why = "最大の長さ"
    for _ in range(int(max_ext / step)):
        q = p + step * d
        n = np.array([-d[1], d[0]])
        xi, yi = int(round(q[0])), int(round(q[1]))
        if not (0 <= xi < paint.W and 0 <= yi < paint.H) or not paint.passable[yi, xi]:
            why = "通れない画素"
            break
        if block[yi, xi]:
            why = "ほかの爪の中心線"
            break
        s = L32.sections(paint, q[None, :], n[None, :])
        dl, dr, wl, wr = float(s["dl"][0]), float(s["dr"][0]), int(s["wl"][0]), int(s["wr"][0])
        if not (wl == 1 and wr == 1):
            why = "断面が開く（口）"
            break
        w = dl + dr
        if w > 1.5 * w0 + 6.0:
            why = "幅が広がる（口）"
            break
        if continuity and ((wprev is not None and abs(w - wprev) > max(6.0, 0.35 * wprev)) or abs(dr - dl) / 2.0 > 4.0):
            why = "壁が跳ぶ（別の線）"
            break
        c = q + n * ((dr - dl) / 2.0)
        nd = c - p
        nd /= max(np.linalg.norm(nd), 1e-9)
        d = 0.6 * d + 0.4 * nd
        d /= max(np.linalg.norm(d), 1e-9)
        p = c
        pts.append(c.copy())
        wprev = w
    return np.array(pts).reshape(-1, 2), dict(w0_ref_px=round(w0, 1), stop_ja=why)
