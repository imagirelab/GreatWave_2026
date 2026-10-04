# -*- coding: utf-8 -*-
"""美術の見本04 の形づくり：粘土の下見（numpy の z バッファ。Unity・Blender の描画ではない）を、土台 AS02C と AS04 で同じ視点に描く。

視点：原画視点（原画のカメラ）・座席・座席から波の方向・左の側面・右の側面・後ろ 65°・真上（見本03 の描画の視点 VIEWS と同じ向き。
主役波に合わせて寄せた「寄り」も描く）と、回り台 12 方位（設計33 の回り台の目の位置）。
色：粘土（灰色）。--layers を付けると、三つの層の区域（① 主の頂と唇 c −2〜+15、② の房 c −16〜−11、③ 最左側の小さな房 c −23〜−16。
列 90〜240＝頂から唇の先・唇の下の面）を薄く色づけする。輪郭は空との境と深さの段差。
使い方：py -3.10 -B shape_clay.py <out_dir> [--layers]
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shape_common as S  # noqa: E402

LIGHT = np.array([0.35, 0.85, -0.40]); LIGHT /= np.linalg.norm(LIGHT)
CLAY = np.array([196, 188, 176], float)
LAYER = {"r1": ((-2.0, 15.5), (225, 120, 110)), "r2": ((-16.0, -11.0), (120, 190, 120)), "r3": ((-23.0, -16.0), (110, 170, 220))}
VIEWS = ["painting", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
TT = [0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330]


def fit_cam(name, Xref, W, H, fill=0.86):
    if name == "painting":
        return S.paint_cam(W, H)
    cam = S.CC.cam_view(name, W, H)
    P = Xref.reshape(-1, 3)
    P = P[P[:, 1] > 0.3]
    ctr = 0.5 * (P.min(0) + P.max(0))
    d0 = np.linalg.norm(ctr - cam.pos)
    f = (ctr - cam.pos) / d0
    up = cam.u if abs(f @ cam.u) < 0.95 else np.array([0, 0, 1.0])
    fov = np.degrees(2 * np.arctan(cam.t))
    for _ in range(3):
        c2 = S.CC.Cam(ctr - f * d0, f, up, fov, W, H)
        xy, z = c2.project(P)
        ext = max((xy[:, 0].max() - xy[:, 0].min()) / W, (xy[:, 1].max() - xy[:, 1].min()) / H)
        d0 *= ext / fill
    return S.CC.Cam(ctr - f * d0, f, up, fov, W, H)


def render(c, A, Y, cam, layers=False):
    X = S.world(c, A, Y)
    R, C = A.shape
    idb, zb, T = S.zbuf(cam, X, 0, C - 1)
    V = X.reshape(-1, 3)
    tr = V[T]
    n = np.cross(tr[:, 1] - tr[:, 0], tr[:, 2] - tr[:, 0]); n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    lam = 0.40 + 0.60 * np.abs(n @ LIGHT)
    r, cc = S.tri_cell(np.arange(len(T)), C)
    col = np.tile(CLAY, (len(T), 1))
    sea = (cc < S.J_B) | (cc >= S.J_FACEBOT)
    col[sea] = (150, 160, 170)
    if layers:
        for k, ((c0, c1), rgb) in LAYER.items():
            m = (c[r] >= c0) & (c[r] <= c1) & (cc >= 90) & (cc <= 240) & ~sea
            col[m] = 0.45 * CLAY + 0.55 * np.array(rgb, float)
    img = np.full((cam.H, cam.W, 3), 246.0)
    m = idb > 0
    t = idb[m] - 1
    img[m] = col[t] * lam[t, None]
    z = np.where(zb > 0, 1 / np.maximum(zb, 1e-9), 0)
    e = np.zeros(m.shape, bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = z[:cam.H - dy, :cam.W - dx]; b = z[dy:, dx:]
        j = ((a > 0) != (b > 0)) | ((a > 0) & (b > 0) & (np.abs(a - b) > 0.02 * np.minimum(a, b) + 0.3))
        e[:cam.H - dy, :cam.W - dx] |= j
    img[e] = (40, 40, 48)
    return img.astype(np.uint8)


def main():
    out = sys.argv[1]
    layers = "--layers" in sys.argv
    os.makedirs(out, exist_ok=True)
    W, H = 960, 540
    cb, Ab, Yb = S.load_rows()
    z = np.load(S.OUT + "/final/cand/kstarAS04_a45_rows.npz")
    shapes = {"AS02C": (cb, Ab, Yb), "AS04": (z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float))}
    Xref = S.world(cb, Ab, Yb)
    for lab, (c, A, Y) in shapes.items():
        for v in VIEWS:
            cam = S.paint_cam(W, H) if v == "painting" else S.CC.cam_view(v, W, H)
            cv2.imwrite(out + "/%s__%s.png" % (lab, v), cv2.cvtColor(render(c, A, Y, cam, layers), cv2.COLOR_RGB2BGR))
            if v != "painting":
                camf = fit_cam(v, Xref, W, H)
                cv2.imwrite(out + "/%s__%s_fit.png" % (lab, v), cv2.cvtColor(render(c, A, Y, camf, layers), cv2.COLOR_RGB2BGR))
        for az in TT:
            cam = S.CC.cam_view("tt%d" % az, W, H)
            cv2.imwrite(out + "/%s__tt%03d.png" % (lab, az), cv2.cvtColor(render(c, A, Y, cam, layers), cv2.COLOR_RGB2BGR))
    print("SHAPE_CLAY_DONE", out, "layers" if layers else "plain")


if __name__ == "__main__":
    main()
