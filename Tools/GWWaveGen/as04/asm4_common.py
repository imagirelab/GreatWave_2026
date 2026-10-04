# -*- coding: utf-8 -*-
"""美術の見本04 の組み立て（Q32）の共通部：測る規則（asm4_rules.py）と並べ図（asm4_sheets.py）が使う場面の読み込みと numpy の z バッファ。

場面（どれも t* の静止。numpy の描画で、Unity の描画ではない。Unity の描画は asm4_render.sh）：
  S04  見本04：主役波 K*′ AS04 と左端の別の青い波 wave4 をつないだ静止のメッシュ（wave4/mesh_as04/union.json。頂点 0〜314399 が主役波）、
       近い海（Polish/30/sea/near/ds30_tstar.gwb）、爪 35 本（shape/claws）。
  S03  見本03 の形（AS02C の t*、冠なしの滑らかな静止のメッシュ mat/mesh/hero_smooth_as02c.json）、近い海、爪 35 本（sample03/assemble/claws35）。
三角形の印（LAB）：1 ①主の頂と唇・2 ② b区域の房・3 ③ 最左側の小さな房（どれも主役波の頂より前 u ≥ 0 で高さ 0.25 H0 以上の面で、行の c が形づくりの
shape_eval.LAYERS の範囲）、4 主役波のほかの前の面、8 主役波の背（u < 0）、5 wave4、6 近い海（と、材質が海の色で塗る主役波の裾）、7 爪。
原画の色は面へ写さない（Q28）。原画のカメラは測りにだけ使う。参照モデルの OBJ と写真は読まない。
"""
import hashlib
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import s4_common as S4  # noqa: E402
import w4_common as W  # noqa: E402

REPO = S4.REPO
U = S4.CC.U
CC = S4.CC
K = S4.K
P = REPO + "/Unity/Build/Polish"
P4 = P + "/sample04"
ASM = P4 + "/assemble"
MEAS = ASM + "/measure"
UNION = P4 + "/wave4/mesh_as04/union.json"
WAVE4 = P4 + "/wave4/mesh_as04/wave4.json"
HERO_SM04 = P4 + "/shape/mesh/hero_smooth_as04.json"
HERO_SM02C = P4 + "/mat/mesh/hero_smooth_as02c.json"
ROWS04 = P4 + "/shape/final/cand/kstarAS04_a45_rows.npz"
ROWS02C = P + "/sample02/fix01/back/final/cand/kstarAS02C_a45_rows.npz"
GWB04 = P4 + "/shape/final/cand/kstarAS04_a45.gwb"
GWB02C = P + "/sample02/fix01/back/final/cand/kstarAS02C_a45.gwb"
RELIEF03 = P + "/sample03/surface/mesh/hero_relief_b1v2c.json"
CLAWS04 = P4 + "/shape/claws/ds33_claw_layout.json"
CLAWS03 = P + "/sample03/assemble/claws35/ds33_claw_layout.json"
SEA_NEAR = S4.SEA_NEAR
# 直しの回（環境変数 AS04_FIX、例 fix1）：主役波・wave4・爪・描画の置き場を直しの回のものへ替える（既定は組み立ての S04 のまま）
FIX = os.environ.get("AS04_FIX", "")
RTAG = "S04"
if FIX:
    _F = P4 + "/" + FIX
    UNION = P4 + "/wave4/mesh_" + FIX + "/union.json"
    WAVE4 = P4 + "/wave4/mesh_" + FIX + "/wave4.json"
    HERO_SM04 = _F + "/shape/mesh/hero_smooth_as04f.json"
    ROWS04 = _F + "/shape/final/cand/kstarAS04F_a45_rows.npz"
    GWB04 = _F + "/shape/final/cand/kstarAS04F_a45.gwb"
    CLAWS04 = _F + "/shape/claws/ds33_claw_layout.json"
    RTAG = os.environ.get("AS04_RTAG", FIX.upper().replace("FIX", "FX"))
    MEAS = ASM + "/measure_" + FIX
N_HERO = 314400
LAYERS = {1: (-2.0, 8.0), 2: (-15.5, -11.5), 3: (-23.0, -17.0)}   # shape_eval.LAYERS と同じ
LAB_JA = {1: "①浪尖（主の頂と唇）", 2: "② b区域の房", 3: "③ 最左側の小さな房", 4: "主役波のほかの前の面", 8: "主役波の背", 5: "④ の別の青い波 wave4",
          6: "近い海", 7: "爪"}


def sha(p):
    if not os.path.isfile(p):
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace("\\", "/").replace(REPO + "/", "")


def rnd(v, k=3):
    return S4.rnd(v, k)


def jdump(p, o):
    S4.jdump(p, o)


def jl(p):
    return json.load(open(p, encoding="utf-8"))


def read_static(p):
    ch, tri, j = W.read_static(p)
    return ch, tri.astype(np.int64), j


LAYER_Y_MIN = 0.25 * S4.H0   # 層は頂から唇の先・唇の下までの上の部分（前の面の下の裾・海へ続く足は層に入れない）


def hero_tri_labels(pos, u, tri, F=None, hrow=None):
    """主役波の三角形の印（1・2・3・4・8、裾は 6）。重心の c・高さ y と、頂点の u の平均の符号で決める。
    材質が周りの海の色で塗る裾（F < 0・F > 4・hrow < 0.25、mat/README.md）は、描画で海に見えるので近い海と同じ 6 にする。"""
    Q = K.sec(pos)
    cm = Q[:, 2][tri].mean(1)
    ym = Q[:, 1][tri].mean(1)
    um = u[tri].mean(1)
    lab = np.where(um >= 0.0, 4, 8).astype(np.int16)
    for k, (c0, c1) in LAYERS.items():
        lab[(um >= 0.0) & (ym >= LAYER_Y_MIN) & (cm >= c0) & (cm <= c1)] = k
    if F is not None:
        fm = F[tri].mean(1); hm = hrow[tri].mean(1)
        lab[(fm < 0.0) | (fm > 4.0) | (hm < 0.25)] = 6
    return lab


def claws_tris(layout_path, kept_only=True):
    lay = jl(layout_path)
    d = os.path.dirname(layout_path)
    fr = np.fromfile(d + "/" + lay["files"]["frames"]["file"], np.float32).reshape(lay["frames"], lay["vertices"], 3)[-1].astype(np.float64)
    tr = np.fromfile(d + "/" + lay["files"]["tris"]["file"], np.int32).reshape(-1, 3).astype(np.int64)
    keep = {k["user_id"]: k["role"] for k in lay["as03_asm"]["kept"]}
    out = []
    for cl in lay["claws"]:
        if kept_only and cl["user_id"] not in keep:
            continue
        o, n = cl["vert_offset"], cl["vert_count"]
        sel = np.nonzero((tr[:, 0] >= o) & (tr[:, 0] < o + n))[0]
        out.append({"user_id": cl["user_id"], "role": keep.get(cl["user_id"]), "verts": fr[o:o + n], "tris": tr[sel] - o})
    return out, lay


_SEA = {}


def sea_tris():
    if not _SEA:
        g = K.read_gwb(SEA_NEAR)
        _SEA["t"] = g["X"][g["tris"].astype(np.int64)]
    return _SEA["t"]


def scene(kind, with_claws=True, with_sea=True):
    """(tris (N,3,3), lab (N,), meta)。kind = 'S04'（主役波 AS04 ＋ wave4）・'S04H'（主役波 AS04 だけ）・'S03'（AS02C の滑らかな面）。"""
    parts, labs = [], []
    if kind in ("S04", "S04H"):
        ch, tri, _ = read_static(UNION)
        pos = ch["position"].astype(np.float64)
        th = tri[tri[:, 0] < N_HERO]
        tw = tri[tri[:, 0] >= N_HERO]
        parts.append(pos[th]); labs.append(hero_tri_labels(pos, ch["uv3"][:, 2].astype(np.float64), th, ch["uv3"][:, 0].astype(np.float64), ch["uv4"][:, 1].astype(np.float64)))
        if kind == "S04":
            parts.append(pos[tw]); labs.append(np.full(len(tw), 5, np.int16))
        clp = CLAWS04
    else:
        ch, tri, _ = read_static(HERO_SM02C)
        pos = ch["position"].astype(np.float64)
        parts.append(pos[tri]); labs.append(hero_tri_labels(pos, ch["uv3"][:, 2].astype(np.float64), tri, ch["uv3"][:, 0].astype(np.float64), ch["uv4"][:, 1].astype(np.float64)))
        clp = CLAWS03
    if with_sea:
        st = sea_tris()
        parts.append(st); labs.append(np.full(len(st), 6, np.int16))
    if with_claws:
        cl, _ = claws_tris(clp)
        for c in cl:
            parts.append(c["verts"][c["tris"]]); labs.append(np.full(len(c["tris"]), 7, np.int16))
    return np.concatenate(parts), np.concatenate(labs), {"claws": clp}


def raster(cam, tris, lab):
    """id（0 は空）・深さ（m、空は inf）・印（0 は空）。"""
    idb, zb = U.raster(cam, tris, np.arange(1, len(tris) + 1, dtype=np.int64))
    idb = idb.reshape(cam.H, cam.W); zb = zb.reshape(cam.H, cam.W)
    L = np.where(idb > 0, lab[np.maximum(idb - 1, 0)], 0).astype(np.int16)
    D = np.where(zb > 0, 1.0 / np.maximum(zb, 1e-12), np.inf)
    return idb, D, L


def painting_cam(scale=1):
    return W.S.CC.U.CamWH(jl(U.TRUTH), 1920 * scale, 1080 * scale)


def ref_to_px(P_ref, scale=1):
    d = S4.ref_to_disp(np.asarray(P_ref, float))
    return scale * (d + 0.5) - 0.5


def px_to_ref(P_px, scale=1):
    d = (np.asarray(P_px, float) + 0.5) / scale - 0.5
    return S4.disp_to_ref(d)


def view_cam(name, W_=1920, H_=1080):
    return CC.cam_view(name, W_, H_)


# 層の色（並べ図と粘土の下見で使う。原画の色ではない）
LAB_RGB = {0: (238, 234, 222), 1: (214, 64, 52), 2: (64, 160, 72), 3: (40, 170, 190), 4: (176, 176, 170), 8: (132, 132, 128),
           5: (70, 96, 200), 6: (206, 214, 220), 7: (250, 250, 250)}


def tint(L, D, edge=True):
    """印の画を色にし、奥行きの跳び（遮る縁）を黒い線で描く。"""
    img = np.zeros(L.shape + (3,), np.uint8)
    for k, c in LAB_RGB.items():
        img[L == k] = c
    if edge:
        e = occl_edges(D)
        img[e] = (20, 20, 20)
    return img


def occl_edges(D, rel_jump=0.03, abs_jump=0.5):
    """遮る縁（深さの跳び）の画素：隣の画素との深さの差が max(abs_jump, rel_jump·近い深さ) を超える所の、手前の側の画素。空との境も含む。"""
    H, W_ = D.shape
    e = np.zeros((H, W_), bool)
    for dy, dx in ((0, 1), (1, 0)):
        a = D[:H - dy, :W_ - dx]; b = D[dy:, dx:]
        fa, fb = np.isfinite(a), np.isfinite(b)
        near = np.minimum(np.where(fa, a, 1e9), np.where(fb, b, 1e9))
        jump = (fa != fb) | (fa & fb & (np.abs(a - b) > np.maximum(abs_jump, rel_jump * near)))
        an = jump & (np.where(fa, a, np.inf) <= np.where(fb, b, np.inf))
        bn = jump & ~an
        e[:H - dy, :W_ - dx] |= an
        e[dy:, dx:] |= bn
    return e
