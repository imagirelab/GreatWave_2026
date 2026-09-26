# -*- coding: utf-8 -*-
"""番号27「空のドーム・船・富士の配置」の共通処理。

numpy・OpenCV・Pillow だけを使う。番号23の真値と評価器（Tools/PaintingTruth）は読むだけで変えない。
画素座標は番号23と同じ（表示フレーム 1920×1080、画素中心が整数、x 右・y 下）。
世界座標は Unity と同じ（左手系、Y 上、PaintingCam v1 は +Z 方向を向く）。
"""
import hashlib
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PT_DIR = os.path.join(REPO, "Tools", "PaintingTruth")
if PT_DIR not in sys.path:
    sys.path.insert(0, PT_DIR)
import truthlib as T  # noqa: E402

BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "27")
EVIDENCE = os.path.join(REPO, "Docs", "Evidence", "ArtFirst", "27")
SKY_JSON = os.path.join(HERE, "sky_dome.json")
LAYOUT_JSON = os.path.join(HERE, "context_layout.json")
W, H = 1920, 1080


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write("\n")


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def rel(p):
    return T.repo_rel(p)


# ---------------------------------------------------------------- PaintingCam
class Cam:
    """PaintingCam v1（painting_truth.json）の投影。truthlib.project_world と同じ式。"""

    def __init__(self, spec, position=None, target=None, vfov=None):
        c = spec["painting_cam"]
        self.pos = np.array(position if position is not None else c["position"], np.float64)
        tgt = np.array(target if target is not None else c["target"], np.float64)
        f = tgt - self.pos
        self.f = f / np.linalg.norm(f)
        up = np.array([0.0, 1.0, 0.0])
        r = np.cross(up, self.f)
        self.r = r / np.linalg.norm(r)
        self.u = np.cross(self.f, self.r)
        self.vfov = float(vfov if vfov is not None else c["vertical_fov_deg"])
        self.t = math.tan(math.radians(self.vfov) / 2.0)
        self.aspect = W / H
        self.focal_px = (H / 2.0) / self.t

    def project(self, P):
        d = np.asarray(P, np.float64) - self.pos
        cx, cy, cz = d @ self.r, d @ self.u, d @ self.f
        vx = 0.5 + 0.5 * (cx / cz) / (self.t * self.aspect)
        vy = 0.5 + 0.5 * (cy / cz) / self.t
        return np.stack([vx * W - 0.5, (1.0 - vy) * H - 0.5], -1), cz

    def ray(self, x, y):
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        vx = (x + 0.5) / W
        vy = 1.0 - (y + 0.5) / H
        d = self.f + ((2 * vx - 1) * self.t * self.aspect)[..., None] * self.r + ((2 * vy - 1) * self.t)[..., None] * self.u
        return d / np.linalg.norm(d, axis=-1, keepdims=True)

    def depth(self, P):
        return (np.asarray(P, np.float64) - self.pos) @ self.f


def el_az(d):
    """方向 → 世界の仰角・方位角（度）。方位角は +Z が 0、+X 側が正。"""
    d = np.asarray(d, np.float64)
    el = np.degrees(np.arcsin(np.clip(d[..., 1], -1.0, 1.0)))
    az = np.degrees(np.arctan2(d[..., 0], d[..., 2]))
    return el, az


# ---------------------------------------------------------------- 回転（Unity の Quaternion と同じ成分の意味）
def quat_to_mat(q):
    x, y, z, w = [float(v) for v in q]
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def mat_to_quat(R):
    R = np.asarray(R, np.float64)
    tr = np.trace(R)
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        w, x, y, z = 0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = math.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2]) * 2
        w, x, y, z = (R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s
    elif R[1, 1] > R[2, 2]:
        s = math.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2]) * 2
        w, x, y, z = (R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s
    else:
        s = math.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1]) * 2
        w, x, y, z = (R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s
    q = np.array([x, y, z, w])
    q /= np.linalg.norm(q)
    if q[3] < 0:
        q = -q
    return q


def unity_euler_to_mat(e):
    """Unity の Quaternion.Euler(x, y, z)（Z→X→Y の順に回す）を行列にする。

    Unity は左手系で、軸まわりの正の回転は軸の正方向から見て時計回り。成分の式は右手系の標準式と同じ
    行列になる（例：Euler(0,90,0) は +Z を +X へ回す）。
    """
    x, y, z = [math.radians(v) for v in e]
    cx, sx, cy, sy, cz, sz = math.cos(x), math.sin(x), math.cos(y), math.sin(y), math.cos(z), math.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


# ---------------------------------------------------------------- M1 仮形状（AF27ContextBuilder.Dump の出力）
def load_dump(group):
    D = load_json(os.path.join(BUILD, "dump", "dump.json"))
    g = [x for x in D["groups"] if x["group"] == group][0]
    raw = open(os.path.join(BUILD, "dump", group + ".bin"), "rb").read()
    meshes = []
    for m in g["meshes"]:
        off = int(m["byteOffset"])
        nv = int(m["vertexCount"])
        V = np.frombuffer(raw, np.float32, nv * 3, off).reshape(-1, 3).astype(np.float64)
        off += nv * 12
        subs = []
        for ic in m["indexCounts"]:
            I = np.frombuffer(raw, np.int32, ic, off).reshape(-1, 3)
            off += ic * 4
            subs.append(I)
        meshes.append({"name": m["name"], "path": m["path"], "V": V, "subs": subs, "materials": m["materials"]})
    return g, meshes


# ---------------------------------------------------------------- ラスタ化（被覆率マスク、超標本化）
def raster_mask(cam, tris_world, ss=2, near=0.1):
    """三角形（N,3,3 の世界座標）の PaintingCam 上の被覆率（1920×1080、ss×ss 超標本化）。奥行きは見ない。"""
    Hs, Ws = H * ss, W * ss
    m = np.zeros((Hs, Ws), np.uint8)
    P = tris_world.reshape(-1, 3)
    xy, z = cam.project(P)
    xy = xy.reshape(-1, 3, 2)
    z = z.reshape(-1, 3)
    ok = np.all(z > near, axis=1)
    pts = np.round(((xy[ok] + 0.5) * ss - 0.5) * 16).astype(np.int32)
    import cv2
    for tri in pts:
        cv2.fillConvexPoly(m, tri, 1, lineType=cv2.LINE_8, shift=4)
    return m.reshape(H, ss, W, ss).mean((1, 3))
