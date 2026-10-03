# -*- coding: utf-8 -*-
"""美術の見本01（Q29）爪の部の共通の道具（numpy。Unity の描画ではない）。

- t*（τ = 0）の主役波 K*′ P28R2rec（仕上げ32 の hero_pkg、時間曲線 G_p28rec）のシート X0（行 240 × 列 400）。行＝波の峰の向き（奥行き）、列＝断面
  （背の根元 → 頂 → 唇の先 → 唇の下 → 前の面 → 前の根元）。
- 原画のカメラ（PaintingCam v1）と見直しの視点（座席・座席から波の方向・左右の側面・後ろ 65°・真上・回り台 12 方位。仕上げ33修正01 の
  PL33Render の t* の値を写した定数）。
- シートへの射線の当たり、最も近い点、局所の座標系、シートからの高さ。
- 管（設計33 の頂点の並び：根元 1・輪 段 × 8・先 1・根元の円 9）と三角形（pl33_common.layout_tris と同じ）。
- 見本の下見の描画（numpy の z バッファ。色は主役波の白の区域・藍、爪は PL29 Claw Shade の段と同じ規則、縁の線は id の境）。
原画カメラからの投影の色は使わない。原画のカメラは、爪を置く場所と向きを決める射線と、重ね図の検査にだけ使う（Q28）。
参照モデル（OBJ）は読まない（F13-1）。
"""
import hashlib
import json
import math
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

REPO = "G:/Unity/GreatWave_2026_Fresh"
for _p in ("Tools/GWWaveGen/ds33", "Tools/GWWaveGen/pl33"):
    if REPO + "/" + _p not in sys.path:
        sys.path.insert(0, REPO + "/" + _p)
import ds33_common as U  # noqa: E402

B = REPO + "/Unity/Build/Polish"
HERO = B + "/32/white/hero_pkg"
ZONE = B + "/32/white/pl31_zone_vertex.npy"
INV = B + "/32/fix01/list/ds32_claw_inventory.json"
OUTD = B + "/sample01/claws"
BODY = U.BODY
RING = 8
# 輪の頂点 q の断面の角度（度）。色は q で決まる（PL29 Claw Shade：sin(45°·q) > 0.30 が白 → q = 1・2・3）。
# 白の向き N の側の約半分（約 2°〜187°）を白、下の約半分を水色の版にする（指の腹＝巻きの内側の陰）。隣の頂点の間は 65° 以下にして、断面を丸く保つ
# （初めの案の −60・−20・90・200…° は 110° の隙間があり、座席から結晶のような角ばった指に見えた）。
Q_FINGER = np.radians([-30.0, 25.0, 90.0, 155.0, 210.0, 240.0, 270.0, 300.0])
# 面に寝る厚い板（面の鉤）：上面（N の側）の q 1〜3 を白、縁と下面を水色の版
Q_SHEET = np.radians([0.0, 30.0, 90.0, 150.0, 180.0, 230.0, 270.0, 310.0])

PAL = dict(white=(248, 243, 223), mizuiro=(203, 215, 206), ai=(34, 63, 96), ai_mid=(41, 105, 148), sky=(249, 232, 196), line=(24, 38, 70))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def jdump(p, o):
    U.jdump(p, o)


def sm(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------- 主役波
def load_hero():
    hero = U.K.Pkg(HERO)
    return hero.world(0.0)


class Hero:
    """t* のシート X0（R × C × 3）と、本体の列の三角形・頂点の法線（空気の側）・KD 木。"""

    def __init__(self, X0):
        self.X = X0
        self.R, self.C = X0.shape[:2]
        b0, b1 = BODY
        self.b0, self.b1 = b0, b1
        rr, cc = np.meshgrid(np.arange(self.R, dtype=np.float64), np.arange(self.C, dtype=np.float64), indexing="ij")
        Fr = U.frame_at(X0, rr, cc)
        self.N = Fr[..., 2, :]
        self.Tg = U.K.grid_tris(self.R, self.C, b0, b1)
        self.V = X0.reshape(-1, 3)
        sel = np.zeros((self.R, self.C), bool)
        sel[:, b0:b1 + 1] = True
        self.vi = np.nonzero(sel.ravel())[0]
        self.tree = cKDTree(self.V[self.vi])
        self.Nf = self.N.reshape(-1, 3)
        self.zone = np.load(ZONE).reshape(self.R, self.C) if os.path.exists(ZONE) else np.zeros((self.R, self.C), bool)

    def height(self, Q):
        """最も近い本体の頂点からの、その頂点の法線の向きの符号付きの距離（設計 sweep_build.Sheet と同じ式）。"""
        sh = Q.shape[:-1]
        Qf = Q.reshape(-1, 3)
        d, j = self.tree.query(Qf)
        j = self.vi[j]
        s = np.sign(((Qf - self.V[j]) * self.Nf[j]).sum(-1))
        s[s == 0] = 1.0
        return (s * d).reshape(sh)

    def nearest(self, Q):
        """最も近い本体の頂点の (r, c) と、その点・法線。"""
        d, j = self.tree.query(Q.reshape(-1, 3))
        j = self.vi[j]
        r, c = np.divmod(j, self.C)
        return r.astype(np.float64), c.astype(np.float64)

    def project(self, Q, rc0):
        r, c, h, tang = U.project_to_sheet(self.X, Q, rc0, iters=10, c_lo=self.b0, c_hi=self.b1)
        return r, c, h

    def frame(self, r, c):
        return U.frame_at(self.X, r, c)

    def point(self, r, c):
        return U.bilin(self.X, r, c)


# ---------------------------------------------------------------- カメラ
class Cam:
    """位置・前・上・縦の画角（Unity と同じ：右 = 上 × 前）の透視カメラ。U.raster が使う W・H・pos・f・project を持つ。"""

    def __init__(self, pos, fwd, up, vfov, W=1920, H=1080):
        self.pos = np.asarray(pos, np.float64)
        f = np.asarray(fwd, np.float64)
        self.f = f / np.linalg.norm(f)
        u = np.asarray(up, np.float64)
        u = u - (u @ self.f) * self.f
        self.u = u / np.linalg.norm(u)
        self.r = np.cross(self.u, self.f)
        self.t = math.tan(math.radians(vfov) * 0.5)
        self.W, self.H = int(W), int(H)
        self.aspect = self.W / self.H

    def project(self, P):
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        czs = np.where(np.abs(cz) < 1e-9, 1e-9, cz)
        vx = 0.5 + 0.5 * (cx / czs) / (self.t * self.aspect)
        vy = 0.5 + 0.5 * (cy / czs) / self.t
        return np.stack([vx * self.W - 0.5, (1.0 - vy) * self.H - 0.5], -1), cz

    def ray(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        vx = (x + 0.5) / self.W
        vy = 1.0 - (y + 0.5) / self.H
        d = self.f + ((2 * vx - 1) * self.t * self.aspect)[..., None] * self.r + ((2 * vy - 1) * self.t)[..., None] * self.u
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def px_m(self, z):
        """深さ z の 1 画素の大きさ（m）。"""
        return z * 2.0 * self.t / self.H


# 仕上げ33修正01 の描画（Unity/Build/Polish/33r01/fix01/r_fix01/pl33_render_report.json、t 12 s）の視点の値。
VIEWS = {
    "painting": ((0.0, 3.0, -62.0), (-0.03765837, 0.10092445, 0.99418110), (0.00382016, 0.99489409, -0.10085212), 26.0),
    "seat": ((3.9544, 1.8323, -15.0308), (-0.29017001, 0.89421153, 0.34086224), (0.57964146, 0.44764462, -0.68090391), 80.0),
    "seat_toward_wave": ((3.9544, 1.8323, -15.0308), (-0.73336518, 0.0, 0.67983496), (0.0, 1.0, 0.0), 70.0),
    "side_left": ((-90.0, 30.0, -14.0), (0.96059000, -0.24862331, 0.12431160), (0.24656720, 0.96860027, 0.03190871), 45.0),
    "side_right": ((-2.23485, 30.0, 80.6758), (-0.05128766, -0.24862337, -0.96724164), (-0.01316468, 0.96860021, -0.24827459), 45.0),
    "back65": ((-41.18864, 18.0, 80.63342), (0.37503606, -0.11043153, -0.92040914), (0.04167067, 0.99388373, -0.10226767), 26.0),
    "top": ((-7.22769, 150.0, -2.71317), (0.0, -1.0, 0.0), (-0.73336524, 0.0, 0.67983490), 40.0),
}
TT_EYE_Y = 28.845890045166016
TT = {0: (1.14783, -71.41537), 30: (34.37682, -58.02325), 60: (56.45792, -29.81086), 90: (61.47451, 5.66235), 120: (48.08240, 38.89134),
      150: (19.87000, 60.97243), 180: (-15.60320, 65.98902), 210: (-48.83219, 52.59692), 240: (-70.91329, 24.38452), 270: (-75.92988, -11.08869),
      300: (-62.53777, -44.31768), 330: (-34.32537, -66.39877)}
# 回り台は中心 O(t*) + (0, 9, 0) を見る（PL33Render.PlaceTurntable）。中心は 0° と 180° の目の中点から求める
_TTC = np.array([0.5 * (TT[0][0] + TT[180][0]), TT_EYE_Y - 72 * math.sin(math.radians(16.0)), 0.5 * (TT[0][1] + TT[180][1])])


def cam_view(name, W=1920, H=1080):
    if name.startswith("tt"):
        az = int(name[2:])
        ex, ez = TT[az]
        eye = np.array([ex, TT_EYE_Y, ez])
        f = _TTC - eye
        return Cam(eye, f, (0, 1, 0), 34.0, W, H)
    p, f, u, fov = VIEWS[name]
    return Cam(p, f, u, fov, W, H)


def painting_cam():
    spec = json.load(open(U.TRUTH, encoding="utf-8"))
    return U.CamWH(spec, 1920, 1080)


# ---------------------------------------------------------------- 管
def ring_frames(pts, n_ref):
    """背骨の接線 T、白の向き N（n_ref を接線に直交させ、回転の少ない枠で運ぶ）、Bv = N × T。"""
    T = np.gradient(pts, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    N = np.zeros_like(pts)
    n0 = n_ref[0] - (n_ref[0] @ T[0]) * T[0]
    if np.linalg.norm(n0) < 1e-6:
        n0 = np.cross(T[0], [0.0, 1.0, 0.0])
    N[0] = n0 / np.linalg.norm(n0)
    for j in range(1, len(pts)):
        # 平行移動（前の N を今の接線に直交させる）と、目標の向き n_ref[j] を混ぜる
        a = N[j - 1] - (N[j - 1] @ T[j]) * T[j]
        b = n_ref[j] - (n_ref[j] @ T[j]) * T[j]
        v = 0.6 * a / max(np.linalg.norm(a), 1e-9) + 0.4 * (b / max(np.linalg.norm(b), 1e-9) if np.linalg.norm(b) > 1e-6 else a)
        if np.linalg.norm(v) < 1e-6:
            v = a
        N[j] = v / max(np.linalg.norm(v), 1e-9)
    Bv = np.cross(N, T)
    return T, N, Bv


def tube_verts(pts, n_ref, rad_w, rad_t, qang, root_disc=None):
    """設計33 の並び：根元 1・輪 (n) × 8・先 1・根元の円の中心 1・円 8。pts は n+1 個（最後が先）。
    rad_w・rad_t（n+1）は断面の半径（Bv の向き・N の向き）。root_disc = (中心, 法線, 半径) なら根元の円を面の上に置く（None なら根元の点に潰す）。"""
    n = len(pts) - 1
    T, N, Bv = ring_frames(pts, n_ref)
    c, s = np.cos(qang), np.sin(qang)
    ring = (pts[:n, None, :] + Bv[:n, None, :] * (rad_w[:n, None] * c[None, :])[..., None]
            + N[:n, None, :] * (rad_t[:n, None] * s[None, :])[..., None])
    V = [pts[0][None, :], ring.reshape(-1, 3), pts[n][None, :]]
    if root_disc is None:
        V.append(np.repeat(pts[0][None, :], 9, 0))
    else:
        cen, nn, rr = root_disc
        e1 = np.cross(nn, [0.0, 1.0, 0.0])
        if np.linalg.norm(e1) < 1e-6:
            e1 = np.cross(nn, [1.0, 0.0, 0.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(nn, e1)
        ang = np.arange(8) * np.pi / 4
        V.append(cen[None, :])
        V.append(cen[None, :] + rr * (np.cos(ang)[:, None] * e1 + np.sin(ang)[:, None] * e2))
    return np.concatenate(V, 0), N


def layout_tris(n_st, base):
    sys.path.insert(0, REPO + "/Tools/GWWaveGen/pl33")
    from pl33_common import layout_tris as lt
    return lt(n_st, base)


def vert_up(n_st):
    """PL29ClawShade が入れる UV2.x（sin φ）を同じ並びで返す（下見の色のため）。"""
    up = [1.0]
    for s in range(n_st):
        for q in range(8):
            up.append(math.sin(q * math.pi / 4))
    up.append(0.0)
    up += [1.0] * 9
    return np.array(up)


# ---------------------------------------------------------------- 下見の描画
def preview(cam, hero, entries, path=None, hero_color=True, scale=1.0, crop=None):
    """主役波（本体の列。白の区域は生成り、ほかは藍。光は面の向きの弱い陰）と爪（entries：dict(V, T, up, web)）を z バッファで描く。
    縁の線は id の境（爪どうし・爪と主役波・空）に引く。戻り値 BGR 画像。"""
    W, H = cam.W, cam.H
    X = hero.X
    tris = [hero.V[hero.Tg]]
    ids = [np.arange(1, len(hero.Tg) + 1)]
    nH = len(hero.Tg)
    off = nH + 1
    tri_col = []
    ent_of = [0] * (nH + 1)
    for k, e in enumerate(entries):
        T = e["T"]
        tris.append(e["V"][T])
        ids.append(np.arange(off, off + len(T)))
        up = e["up"][T].mean(1)
        if e.get("web"):
            col = np.tile(np.array(PAL["mizuiro"][::-1], np.float64), (len(T), 1))
        else:
            col = np.where((up > 0.30)[:, None], np.array(PAL["white"][::-1], np.float64), np.array(PAL["mizuiro"][::-1], np.float64))
        tri_col.append(col)
        ent_of += [k + 1] * len(T)
        off += len(T)
    tris = np.concatenate(tris)
    ids = np.concatenate(ids)
    idb, zb = U.raster(cam, tris, ids)
    img = np.zeros((H, W, 3), np.float64)
    img[:] = np.array(PAL["sky"][::-1], np.float64)
    hm = (idb > 0) & (idb <= nH)
    if hm.any():
        t = idb[hm] - 1
        tv = hero.Tg[t]
        nn = hero.Nf[tv].mean(1)
        nn /= np.linalg.norm(nn, axis=1, keepdims=True)
        lam = 0.75 + 0.25 * np.clip(nn @ np.array([0.3, 0.9, -0.3]) / np.linalg.norm([0.3, 0.9, -0.3]), -1, 1)
        wz = hero.zone.reshape(-1)[tv].mean(1) > 0.5
        base = np.where(wz[:, None], np.array(PAL["white"][::-1], np.float64), np.array(PAL["ai"][::-1], np.float64)) if hero_color else np.array(PAL["ai"][::-1], np.float64)[None, :].repeat(len(t), 0)
        img[hm] = base * lam[:, None]
    cm = idb > nH
    if cm.any() and tri_col:
        allc = np.concatenate(tri_col)
        img[cm] = allc[idb[cm] - nH - 1]
    # 縁の線：爪の entry の境と、爪と主役波・空の境、深さの段差
    ent = np.zeros_like(idb)
    ent[hm] = -1
    if cm.any():
        eo = np.array(ent_of)
        ent[cm] = eo[np.minimum(idb[cm], len(eo) - 1)]
    edge = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = ent[: H - dy, : W - dx]
        b = ent[dy:, dx:]
        e = (a != b) & ((a > 0) | (b > 0))
        edge[: H - dy, : W - dx] |= e
    z = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-9), 0)
    gz = np.zeros((H, W), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = z[: H - dy, : W - dx]
        b = z[dy:, dx:]
        jump = (np.abs(a - b) > 0.04 * np.minimum(a, b) + 0.3) & ((ent[: H - dy, : W - dx] > 0) | (ent[dy:, dx:] > 0))
        gz[: H - dy, : W - dx] |= jump
    edge |= gz
    # 主役波の輪郭（空との境）
    sky = idb == 0
    he = np.zeros((H, W), bool)
    he[:, 1:] |= sky[:, 1:] != sky[:, :-1]
    he[1:, :] |= sky[1:, :] != sky[:-1, :]
    lw = max(1, int(round(1.5 * W / 1920)))
    em = cv2.dilate((edge | he).astype(np.uint8), np.ones((lw, lw), np.uint8)) > 0
    img[em] = np.array(PAL["line"][::-1], np.float64)
    out = np.clip(img, 0, 255).astype(np.uint8)
    if path:
        cv2.imwrite(path, out)
    return out


def label(img, text, org=(12, 34), s=0.9):
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, s, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(img, text, org, cv2.FONT_HERSHEY_SIMPLEX, s, (255, 255, 255), 2, cv2.LINE_AA)
    return img
