# -*- coding: utf-8 -*-
"""P2 の共通：原画カメラ（PaintingCam v1）、原画の大波の輪郭と面、計算の座標 → Unity の座標の置き方、三角形の塗りつぶし。
py -3.10（numpy・cv2）。

座標：
- 計算（Houdini）：x＝波の進む向き、y＝上、z＝峰に沿う向き。静かな水面 y=0。
- Unity（原画カメラの座標）：左手系、y 上。原画カメラは位置 (0,3,-62)、注視点 (-2.5,9.7,4.0)、縦の画角 26°、1920×1080。
- 置き方（記録する変換）：U = O + s·[(x − xa)·T(ψ) + y·Ŷ + (z − za)·E(ψ)]
    T(ψ) = (cos ψ, 0, −sin ψ)：進む向き（ψ=0 で画面の右へ、ψ>0 でカメラの側へ。見本06 の T は ψ=42.8°）
    E(ψ) = (sin ψ, 0, cos ψ)：峰に沿う向き（z<za の側が画面の左・手前）
    (xa, ya, za)：計算の頂（その瞬間の一番高い水面の点）。O は、頂が原画の頂の画素 (766, 93) の光線の上で高さ s·ya に来るように決める。
  高さは動かさない（静かな水面を共有する）。s は一様の倍率（0.9〜1.1）。
"""
import json, math
import numpy as np
import cv2

REPO = r"G:/Unity/GreatWave_2026_Fresh"
TRUTH = REPO + "/Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
W, H = 1920, 1080
CAM_POS = np.array([0.0, 3.0, -62.0]); CAM_TGT = np.array([-2.5, 9.7, 4.0]); VFOV = 26.0
CREST_PX = np.array([766.1, 92.9])
WIN = (157, 1250, 0, 735)   # 比べる窓：x0, x1, y0, y1（表示の画素）。y1 は前の面の見える下の端（手前の小波に隠れる所）


class Cam:
    def __init__(self, pos, fwd, up, vfov, Wd=W, Hd=H):
        self.pos = np.asarray(pos, float)
        f = np.asarray(fwd, float); f = f / np.linalg.norm(f)
        r = np.cross(np.asarray(up, float), f); r /= np.linalg.norm(r)
        u = np.cross(f, r)
        self.f, self.r, self.u = f, r, u
        self.t = math.tan(math.radians(vfov) / 2); self.asp = Wd / Hd; self.W, self.H = Wd, Hd; self.vfov = vfov

    def project(self, P):
        d = np.asarray(P, float) - self.pos
        z = d @ self.f
        x = (d @ self.r) / np.maximum(z, 1e-6) / (self.t * self.asp)
        y = (d @ self.u) / np.maximum(z, 1e-6) / self.t
        px = (0.5 + 0.5 * x) * self.W - 0.5
        py = (1.0 - (0.5 + 0.5 * y)) * self.H - 0.5
        return np.stack([px, py], -1), z

    def ray(self, px):
        px = np.atleast_2d(np.asarray(px, float))
        vx = (px[:, 0] + 0.5) / self.W; vy = 1.0 - (px[:, 1] + 0.5) / self.H
        d = self.f + ((2 * vx - 1) * self.t * self.asp)[:, None] * self.r + ((2 * vy - 1) * self.t)[:, None] * self.u
        return d / np.linalg.norm(d, axis=1, keepdims=True)


def painting_cam(scale=1.0):
    return Cam(CAM_POS, CAM_TGT - CAM_POS, (0, 1, 0), VFOV, int(W * scale), int(H * scale))


# 見本06 の回り台（as01/claws_common.py の値）。中心 _TTC を見る。目の高さ 28.85 m、縦の画角 34°。
TT_EYE_Y = 28.845890045166016
TT_C = np.array([-7.227685, TT_EYE_Y - 72 * math.sin(math.radians(16.0)), -2.713170])


def tt_cam(az_deg, scale=1.0, center=None, R=69.21, eye_y=TT_EYE_Y):
    """回り台の向き az_deg（見本06 と同じ向きの決め方）。R・eye_y を大きくすると遠く高くから見る（P2 の左前の斜めは R 150 m・目の高さ 45 m）。"""
    c = TT_C if center is None else np.asarray(center, float)
    a = math.radians(az_deg + 6.95)
    eye = np.array([c[0] + R * math.sin(a), eye_y, c[2] - R * math.cos(a)])
    return Cam(eye, c - eye, (0, 1, 0), 34.0, int(W * scale), int(H * scale))


def painting_outline():
    src = json.load(open(TRUTH, encoding="utf8"))
    segs = {s["id"]: np.array(s["points_display"], float) for s in src["segments"]}
    outer = np.concatenate([segs["78"], segs["130"][1:], segs["131"][1:], segs["132"][1:]])
    inner = segs["72"]
    return outer, inner, src


def painting_mask(scale=1.0):
    """原画の大波の面（表示の画素）：外側の輪郭 → 内側の輪郭（唇の先 → 内側の壁 → 前の面の下 y=735）→ 窓の下の端を左へ → 左の端。"""
    outer, inner, _ = painting_outline()
    poly = np.concatenate([outer, inner[1:], [[outer[0][0] - 2, inner[-1][1]]]])
    m = np.zeros((int(H * scale), int(W * scale)), np.uint8)
    cv2.fillPoly(m, [np.round((poly + 0.5) * scale - 0.5).astype(np.int32)], 1)
    return m.astype(bool), outer, inner


def window_mask(scale=1.0):
    x0, x1, y0, y1 = WIN
    m = np.zeros((int(H * scale), int(W * scale)), bool)
    m[int(y0 * scale):int(y1 * scale), int(x0 * scale):int(x1 * scale)] = True
    return m


def TE(psi_deg):
    p = math.radians(psi_deg)
    return np.array([math.cos(p), 0.0, -math.sin(p)]), np.array([math.sin(p), 0.0, math.cos(p)])


def place(Psim, anchor, psi_deg, s=1.0, cam=None):
    """計算の点 → Unity の点。anchor = (xa, ya, za)。戻り：U、O。"""
    cam = cam or painting_cam()
    T, E = TE(psi_deg)
    d = cam.ray((CREST_PX + 0.5) * (cam.W / W) - 0.5)[0]
    lam = (s * anchor[1] - cam.pos[1]) / d[1]
    O = cam.pos + lam * d - np.array([0.0, s * anchor[1], 0.0])
    Q = np.asarray(Psim, float) - np.array([anchor[0], 0.0, anchor[2]])
    U = O + s * (Q[..., 0:1] * T + Q[..., 1:2] * np.array([0.0, 1.0, 0.0]) + Q[..., 2:3] * E)
    return U, O


def raster_mask(cam, U, tri):
    """三角形を塗る（シルエット）。カメラの後ろの三角形は捨てる。"""
    px, z = cam.project(U)
    ok = (z[tri] > 3.0).all(1)   # カメラから 3 m 以内の面は捨てる（近すぎる面が画面いっぱいの細い三角形になるため）
    t = tri[ok]
    q = px[t]
    # 画面の外に大きく出た三角形を捨てる（塗りつぶしの範囲を抑える）
    inb = (q[:, :, 0].max(1) > -50) & (q[:, :, 0].min(1) < cam.W + 50) & (q[:, :, 1].max(1) > -50) & (q[:, :, 1].min(1) < cam.H + 50)
    q = q[inb]
    m = np.zeros((cam.H, cam.W), np.uint8)
    # 三角形を 1 つずつ塗る（cv2.fillPoly に全部を一度に渡すと、重なった所が打ち消し合って穴になる）
    for tr in np.round(q * 4).astype(np.int32):
        cv2.fillConvexPoly(m, tr, 1, lineType=cv2.LINE_8, shift=2)
    return m.astype(bool)


def outline_distance(mask, outer, inner, scale):
    """原画の輪郭の点から、流体のシルエットの縁までの距離（表示 1920 の画素）。窓の中の点だけ。"""
    m8 = mask.astype(np.uint8)
    edge = cv2.morphologyEx(m8, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    if not edge.any():
        return None
    dt = cv2.distanceTransform((~edge).astype(np.uint8), cv2.DIST_L2, 5)
    pts = np.concatenate([outer, inner])
    x0, x1, y0, y1 = WIN
    pts = pts[(pts[:, 0] >= x0) & (pts[:, 0] < x1) & (pts[:, 1] >= y0) & (pts[:, 1] < y1 - 2)]
    ij = np.clip(np.round((pts + 0.5) * scale - 0.5).astype(int), 0, [mask.shape[1] - 1, mask.shape[0] - 1])
    d = dt[ij[:, 1], ij[:, 0]] / scale
    return {"mean_px": float(d.mean()), "median_px": float(np.median(d)), "p90_px": float(np.percentile(d, 90)), "n": int(len(d))}


def load_mesh(path):
    d = np.load(path)
    return d["P"].astype(np.float64), d["tri"].astype(np.int64), float(d["t"])


def painting_crest_profile(psi_deg, Hc=20.0):
    """原画の外側の輪郭（左の端から頂まで）を、頂（高さ Hc）を通り峰に沿う縦の平面（法線 T(ψ)）に当てた読み。
    戻り：(s, y)。s は峰に沿う距離（m、負＝画面の左）、y は高さ（m）。峰に沿う頂の高さの形（S4「背は一つの山」）を、
    この置き方で読んだもの（輪郭の左の部分が峰の高さの変化を斜めから見たものと読む場合）。"""
    cam = painting_cam()
    outer, inner, _ = painting_outline()
    ic = int(np.argmin(outer[:, 1]))
    T, E = TE(psi_deg)
    d0 = cam.ray(CREST_PX)[0]
    lam = (Hc - cam.pos[1]) / d0[1]
    Oc = cam.pos + lam * d0
    d = cam.ray(outer[:ic + 1])
    s_ = ((Oc - cam.pos) @ T) / (d @ T)
    P = cam.pos + s_[:, None] * d
    return (P - Oc) @ E, P[:, 1]


def run_mirror(rd):
    """run.json の parms の mirror_z（1 なら z=-Lz/2 の壁を対称の面として鏡に映す）と Lz。"""
    import os
    try:
        pr = json.load(open(os.path.join(rd, "run.json"), encoding="utf8"))["parms"]
    except Exception:
        return False, 240.0
    return bool(float(pr.get("mirror_z", 0) or 0) > 0.5), float(pr.get("Lz", 240.0))


def load_mesh_full(path, mirror=False, Lz=240.0):
    """網目を読み、mirror なら z=-Lz/2 の面で鏡に映した写しを足す（三角形の向きは裏返す）。"""
    P, tri, t = load_mesh(path)
    if not mirror:
        return P, tri, t
    Pm = P.copy(); Pm[:, 2] = -Lz - P[:, 2]
    return np.concatenate([P, Pm]), np.concatenate([tri, tri[:, [0, 2, 1]] + len(P)]), t


def placement_matrix(anchor, psi_deg, s, O):
    """place() と同じ変換の 4×4 行列（行が Unity の x, y, z、列が計算の x, y, z, 1）。U = M · (x, y, z, 1)。
    注：列 T(ψ), Ŷ, E(ψ) の行列式は +1。計算（Houdini、右手系）の座標をそのまま左手系の Unity の座標として置くので、
    形としては鏡に映した置き方になる（重力と流体の式は鏡に映しても同じなので、物理として成り立つ）。"""
    T, E = TE(psi_deg)
    Y = np.array([0.0, 1.0, 0.0])
    O = np.asarray(O, float)
    M = np.eye(4)
    M[:3, 0] = s * T; M[:3, 1] = s * Y; M[:3, 2] = s * E
    M[:3, 3] = O - s * (anchor[0] * T + anchor[2] * E)
    return M
