# -*- coding: utf-8 -*-
"""美術の見本01：面の座標 (u, w) の点検の図（numpy の簡単な描画。Unity の描画ではない。点検と記録のための図）。

t* の主役波の面（K*′ P28R2rec の .gwb）を、審査の視点のカメラ（Unity の描画の記録の camPos・camForward・camUp・fov）から描き、
w の等値線（溝の候補、周期 λ）と u の等値線（巻きの向きの弧長、周期 λu）を色で重ねる。比較のため、仕上げ29 の溝の置き方（行の c）でも描ける。
.gwb の t* の位置はそのままワールドの値（meta の frame.section_origin_world ＝ t* の originWorld）。
使い方：py -3.10 -B Tools/GWWaveGen/sample01/s01_preview.py --param <s01_param_f32.bin> --out <png> [--mode w|row|both]
"""
import argparse
import json
import os
import struct
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from s01_param import load_gwb  # noqa: E402

B = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish"
GWB = B + "/28/kstar_p28rec/kstarP28R2rec_a45.gwb"
ATTR = B + "/29/fix01/attr/pl29_hero_attr_f32.bin"
ORIGIN_TSTAR = np.zeros(3)  # K*′ の .gwb の t* の位置はワールドの値（meta の frame.section_origin_world が t* の枠の原点 originWorld と同じ）
# 審査の視点（仕上げ36 の描画の記録 r_after/pl33_render_report.json の t 12 s の値。回り台は PL36Render.PlaceTurntable と同じ置き方）
CAMS = {
    "painting": ((0.0, 3.0, -62.0), (-0.03765837475657463, 0.10092444717884064, 0.9941810965538025), (0.003820155980065465, 0.9948940873146057, -0.1008521169424057), 26.0),
    "seat": ((3.954400062561035, 1.8322999477386475, -15.030799865722656), (-0.29017001390457153, 0.8942115306854248, 0.3408622443675995), (0.5796414613723755, 0.4476446211338043, -0.6809039115905762), 80.0),
    "seat_toward_wave": ((3.954400062561035, 1.8322999477386475, -15.030799865722656), (-0.7333651781082153, 0.0, 0.6798349618911743), (0, 1, 0), 70.0),
    "side_left": ((-90.0, 30.0, -14.0), (0.9605900049209595, -0.2486233115196228, 0.12431160360574722), (0.24656720459461212, 0.9686002731323242, 0.03190871328115463), 45.0),
    "side_right": ((-2.2348499298095703, 30.0, 80.67579650878906), (-0.051287658512592316, -0.24862337112426758, -0.967241644859314), (-0.013164675794541836, 0.9686002135276794, -0.24827459454536438), 45.0),
    "back65": ((-41.18864440917969, 18.0, 80.63341522216797), (0.3750360608100891, -0.11043152213096619, -0.9204091429710388), (0.041670672595500946, 0.9938837289810181, -0.10226766765117645), 26.0),
    "top": ((-7.227685928344727, 150.0, -2.713169813156128), (0, -1, 0), (-0.7333652377128601, 0, 0.6798349022865295), 40.0),
}


def render_ids(pos_w, tri, cam, W, H):
    eye, fwd, up, fov = [np.array(x, float) if i < 3 else x for i, x in enumerate(cam)]
    fwd = fwd / np.linalg.norm(fwd)
    right = np.cross(up, fwd); right /= np.linalg.norm(right)   # Unity は左手系（right = up × forward）
    up2 = np.cross(fwd, right)
    rel = pos_w - eye
    z = rel @ fwd
    f = 0.5 * H / np.tan(np.radians(fov) * 0.5)
    zc = np.maximum(z, 1e-3)
    sx = W * 0.5 + f * (rel @ right) / zc
    sy = H * 0.5 - f * (rel @ up2) / zc
    tz = z[tri]
    ok = (tz > 0.3).all(1)
    S = np.stack([sx, sy], -1)
    ts = S[tri]
    inside = ok & (ts[..., 0].max(1) > -50) & (ts[..., 0].min(1) < W + 50) & (ts[..., 1].max(1) > -50) & (ts[..., 1].min(1) < H + 50)
    order = np.argsort(-tz.mean(1))
    img = np.zeros((H, W, 3), np.uint8)
    for t in order:
        if not inside[t]:
            continue
        pts = np.round(ts[t] * 16).astype(np.int32)
        k = int(t) + 1
        cv2.fillConvexPoly(img, pts, (k & 255, (k >> 8) & 255, (k >> 16) & 255), lineType=cv2.LINE_8, shift=4)
    ids = img[..., 0].astype(np.int64) + (img[..., 1].astype(np.int64) << 8) + (img[..., 2].astype(np.int64) << 16) - 1
    return ids, sx, sy, z


def interp(ids, sx, sy, z, tri, vals, W, H):
    """画素ごとに透視で正しい重心座標で頂点の値を補間する。"""
    yy, xx = np.mgrid[0:H, 0:W]
    m = ids >= 0
    t = ids[m]
    i0, i1, i2 = tri[t, 0], tri[t, 1], tri[t, 2]
    px, py = xx[m] + 0.5, yy[m] + 0.5
    x0, y0, x1, y1, x2, y2 = sx[i0], sy[i0], sx[i1], sy[i1], sx[i2], sy[i2]
    d = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    d = np.where(np.abs(d) < 1e-12, 1e-12, d)
    b0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / d
    b1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / d
    b2 = 1 - b0 - b1
    w0, w1, w2 = b0 / z[i0], b1 / z[i1], b2 / z[i2]
    s = w0 + w1 + w2
    s = np.where(np.abs(s) < 1e-12, 1e-12, s)
    out = []
    for v in vals:
        o = np.full((H, W), np.nan)
        o[m] = (w0 * v[i0] + w1 * v[i1] + w2 * v[i2]) / s
        out.append(o)
    return m, out


def lines(v, period, width_px=1.2):
    """値 v の周期 period の等値線の覆い（画素の幅）。"""
    q = v / period
    gy, gx = np.gradient(np.nan_to_num(q))
    fw = np.abs(gx) + np.abs(gy)
    d = np.abs(q - np.round(q)) / np.maximum(fw, 1e-6)
    return np.clip(width_px - d, 0, 1) * (fw < 0.45)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--param", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--views", default="painting,seat,seat_toward_wave,side_left,side_right,back65,top")
    ap.add_argument("--lam", type=float, default=1.0)
    ap.add_argument("--lamu", type=float, default=4.0)
    ap.add_argument("--mode", default="w", choices=["w", "row", "gw"])
    ap.add_argument("--W", type=int, default=960)
    a = ap.parse_args()
    nu, nv, uv, uv2, tri, pos = load_gwb(GWB)
    N = nu * nv
    pr = np.fromfile(a.param, np.float32).reshape(N, 8).astype(np.float64)
    at = np.fromfile(ATTR, np.float32).reshape(N, 12).astype(np.float64)
    F = at[:, 0]
    u, w, gw = pr[:, 0], pr[:, 1], pr[:, 3]
    if a.mode == "row":
        w = uv2[:, 1].astype(np.float64)   # 行の c（仕上げ29 の置き方の素の形。kc の 2 倍の段はここでは描かない）
        u = at[:, 7]                         # dtop（行ごとの頂からの弧長）
    pos_w = pos + ORIGIN_TSTAR
    W = a.W; H = W * 9 // 16
    tiles = []
    for vname in a.views.split(","):
        ids, sx, sy, z = render_ids(pos_w, tri, CAMS[vname], W, H)
        m, (wi, ui, Fi, gwi) = interp(ids, sx, sy, z, tri, [w, u, F, gw], W, H)
        img = np.full((H, W, 3), (196, 232, 249), np.float64)  # 空（BGR）
        # 面の地：F の区間で淡く色分け（背 0〜1 灰、1〜2 黄、2〜3 水色、3〜5 薄紫）
        base = np.zeros((H, W, 3))
        Fz = np.nan_to_num(Fi)
        cols = [(150, 150, 150), (120, 200, 230), (230, 200, 140), (210, 170, 190), (200, 190, 170)]
        for k, cc in enumerate(cols):
            sel = m & (Fz >= (k if k else -99)) & (Fz < (k + 1 if k < 4 else 99))
            base[sel] = cc
        if a.mode == "gw":
            # |∇w| の倍率の色：0.67 以下 青、1 白、1.5 以上 赤（log2 で線形）
            lg = np.clip(np.log2(np.nan_to_num(gwi, nan=1.0)) / np.log2(1.5), -1, 1)
            base[..., 0] = np.where(lg < 0, 255, 255 * (1 - lg)); base[..., 2] = np.where(lg > 0, 255, 255 * (1 + lg)); base[..., 1] = 255 * (1 - np.abs(lg))
        img[m] = base[m]
        lw = lines(wi, a.lam, 1.3)
        lu = lines(ui, a.lamu, 1.1)
        img = img * (1 - lw[..., None]) + np.array([90, 40, 20]) * lw[..., None]
        img = img * (1 - lu[..., None]) + np.array([40, 40, 200]) * lu[..., None]
        img = np.clip(img, 0, 255).astype(np.uint8)
        cv2.putText(img, vname + (" (row c)" if a.mode == "row" else " (w)"), (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        tiles.append(img)
    while len(tiles) % 2:
        tiles.append(np.full_like(tiles[0], 235))
    rows = [np.concatenate(tiles[i:i + 2], 1) for i in range(0, len(tiles), 2)]
    sheet = np.concatenate(rows, 0)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    cv2.imwrite(a.out, sheet)
    print(a.out, sheet.shape)


if __name__ == "__main__":
    main()
