# -*- coding: utf-8 -*-
"""番号27修正01：座席を唇の真下の右船へ移す（D7 = (a)、利用者の CP1 回答 2026-09-26）。

使い方（リポジトリ根で）: py -3.10 Tools/GWContext/af27r01_seat.py
前提（読むだけ）:
    Tools/GWContext/context_layout.json（番号27 の配置。右船の置き方はここから出発する）
    Unity/Build/ArtFirst/27/dump/（番号27 の AF27ContextBuilder.Dump の出力：船の blockout と斜面の仮置きの頂点）
    Unity/Build/ArtFirst/26/kstar/kstar_a45.gwb・_meta.json・_rows.npz（番号26 の K* 45°。唇先の位置を読む）
出力:
    Tools/GWContext/seat_v1.json          座席 v1（番号26・30 ほかが読む座席の定義。Unity の JsonUtility でも読める `unity` 区画付き）
    Unity/Build/ArtFirst/27R01/water/af27r01_right_slope.bin・.json   右船を載せる水面（右の斜面の仮置きの修正版）の頂点と三角形
    Unity/Build/ArtFirst/27R01/place/af27r01_place.json               計算の記録（候補の座席、接水の表、船内への浸水の検査）

やること
1. 右船（boat_mid）を PaintingCam v1 の投影中心を中心に一様に縮める（k 倍）。原画視点での像は変わらない（同じ射線の上を動くだけ）。
   k は「船体の最も低い点が平らな海面（y = 0：番号26 の K* の水面シートの平らな海の高さ）より喫水だけ下」になる値にする。
   喫水は番号27 と同じ定義（船体中央の深さ 0.96 m の 35% × 縮尺）。番号27 の右船は船首の側が海面より 1 m 以上低く、
   平らな海と右の斜面の仮置きの両方に沈んでいた。縮めると船首が上がり、深度平面が番号26 の唇先の深さに近づく（唇の真下）。
2. 座席：番号27 と同じ測り方（船の根の局所 (0, 10, z) から船の局所の下向きに甲板 Boat_Deck_Planks を測り、その 1.2 m 上）。
   z は |z| ≤ 3.0（甲板の幅が 0.78 m 以上ある範囲）を 0.5 刻みで調べ、K* 45° の唇先の線（目より 3 m 以上高い唇先）に水平距離で
   最も近い点を選ぶ（唇の真下）。
3. 右船の水面：番号27 の右の斜面の仮置き（M1_Revision_RightSlope、+1.6126 m 移動済み）の殻を、z 方向に 0.25 m 刻みの行を
   足して作り直し、船の周りだけ鉛直に動かす。目標の高さ T(s) = 竜骨の線（船体中央部 |z| ≤ 3 の底の線の直線当てはめ）＋喫水。
   ただし T は 0.05 m 以上（K* の平らな海 y = 0 と重ならないよう少し上）。重み w = w_s(s)·w_d(d)（s は船の軸に沿った水平距離、
   d は軸からの水平距離。船体の範囲とその横 d0 までは 1、その外は smoothstep で B 先・E 先に 0）。上面と下面を同じ量だけ動かす。
   M1 の FBX とプレハブは変えない（Unity 側で新しいメッシュ資産に差し替える）。
"""
import json
import math
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import af27common as C  # noqa: E402
from af27common import T  # noqa: E402
import af27_place as P27  # noqa: E402

REPO = C.REPO
BUILD = os.path.join(REPO, "Unity", "Build", "ArtFirst", "27R01")
B26 = os.path.join(REPO, "Unity", "Build", "ArtFirst", "26", "kstar")
SEAT_JSON = os.path.join(HERE, "seat_v1.json")
KEY_WAVE = "a45"                 # D6 の裁定（45°、利用者の CP1 回答 2026-09-26）
Y_WATER = 0.0                    # 平らな海の高さ（番号26 の K* の水面シートの縁と平らな海。参照海面の上面は −0.07）
EYE_ABOVE_DECK = 1.2
SEAT_Z_CANDIDATES = [round(v, 2) for v in np.arange(-3.0, 3.01, 0.5)]
LIP_ABOVE_EYE_MIN = 3.0          # 唇先の線のうち、目より 3 m 以上高い点だけを「頭上の唇」とみなす
T_MIN = 0.05                     # 斜面の仮置きの水面の下限（K* の平らな海 y = 0 と z-fighting しないよう少し上）
D0_MARGIN = 0.3                  # 船体の横幅（平面図）の外へ w = 1 を広げる幅
B_LATERAL = 3.0                  # 横方向に w が 1 → 0 へ下がる幅
E_ENDS = 2.5                     # 船の両端の先で w が 1 → 0 へ下がる長さ
Z_REFINE = 0.25                  # 作り直す殻の z 方向の行の間隔（船の周り ±Z_BAND）
Z_BAND = 7.0
KEEL_FIT_Z = 3.0                 # 竜骨の線を当てはめる船体中央部（船の根の局所 |z| ≤ 3）
FLAT_DECK_HALF_WIDTH_MIN = 0.39  # 甲板の局所の半幅の下限（|z| ≤ 3 で満たす）
HOLE_GAP = 0.05                  # 船体の足跡の中で、水面を船体の最も低い面より下げる量


def r(v, n=4):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r(x, n) for x in v]
    return round(float(v), n)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def read_gwb(p):
    b = open(p, "rb").read()
    if b[:4] != b"GWW0":
        raise SystemExit("GWW0 ではない: " + p)
    _, nu, nv, _ = struct.unpack("<4i", b[4:20])
    _, ntri = struct.unpack("<2i", b[24:32])
    n = nu * nv
    off = 32 + n * 16
    tri = np.frombuffer(b, np.int32, ntri * 3, off).reshape(-1, 3)
    off += ntri * 12
    P = np.frombuffer(b, np.float32, n * 3, off).reshape(-1, 3).astype(np.float64)
    return nu, nv, tri, P


def main_lip(meta, rows):
    """番号26・CP1 の 68 と同じ：主断面の唇先・内壁の下端・頂（世界座標）。"""
    fr_t = np.array(meta["frame"]["t_travel"])
    O0 = np.array(meta["frame"]["section_origin_world"])
    vm = meta["rows"]["main_row"]
    A, Y = rows["A"][vm], rows["Y"][vm]
    jt, jk, jf = meta["profile"]["index"]["j_top"], meta["profile"]["index"]["j_corner"], meta["profile"]["index"]["j_facebot"]
    world = lambda aa, yy: O0 + aa * fr_t + np.array([0, 1.0, 0]) * yy  # noqa: E731
    jtip = jt + int(np.argmax(A[jt:jk + 1]))
    return world(A[jtip], Y[jtip]), world(A[jf], Y[jf]), world(A[jt], Y[jt])


def heights_at(tris, x, z):
    """鉛直線 (x, z) と三角形の交点の y をすべて（昇順）。"""
    A, B, Cc = tris[:, 0], tris[:, 1], tris[:, 2]
    v0 = np.stack([B[:, 0] - A[:, 0], B[:, 2] - A[:, 2]], 1)
    v1 = np.stack([Cc[:, 0] - A[:, 0], Cc[:, 2] - A[:, 2]], 1)
    v2 = np.stack([x - A[:, 0], z - A[:, 2]], 1)
    den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
    ok = np.abs(den) > 1e-12
    u = np.where(ok, (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / np.where(ok, den, 1), -1)
    w = np.where(ok, (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / np.where(ok, den, 1), -1)
    ins = ok & (u >= -1e-9) & (w >= -1e-9) & (u + w <= 1 + 1e-9)
    return np.sort(A[ins, 1] + u[ins] * (B[ins, 1] - A[ins, 1]) + w[ins] * (Cc[ins, 1] - A[ins, 1]))


class BoxIndex:
    """平面図の格子で三角形を引く（鉛直線との交点を速く求めるため）。"""

    def __init__(self, tris, cell=1.0):
        self.tris, self.cell = tris, cell
        lo = tris[:, :, [0, 2]].min(1)
        hi = tris[:, :, [0, 2]].max(1)
        self.cells = {}
        for i, (a, b) in enumerate(zip(lo, hi)):
            for gx in range(int(math.floor(a[0] / cell)), int(math.floor(b[0] / cell)) + 1):
                for gz in range(int(math.floor(a[1] / cell)), int(math.floor(b[1] / cell)) + 1):
                    self.cells.setdefault((gx, gz), []).append(i)

    def heights(self, x, z):
        idx = self.cells.get((int(math.floor(x / self.cell)), int(math.floor(z / self.cell))))
        if not idx:
            return np.zeros(0)
        return heights_at(self.tris[idx], x, z)


def rebuild_slope(slopes, dy27):
    """番号27 の右の斜面の仮置き（上面 97×21 の格子・下面・4 側面の殻）を格子に戻す（世界座標、+dy27 移動済み）。"""
    rs = slopes["M1_Revision_RightSlope"]
    V = rs["V"] + np.array([0, dy27, 0])
    top_i = np.unique(rs["subI"][0])
    bot_i = np.unique(rs["subI"][1])
    xs = np.unique(np.round(V[top_i, 0], 3))
    zs = np.unique(np.round(V[top_i, 2], 3))
    ytop = np.full((len(zs), len(xs)), np.nan)
    ybot = np.full((len(zs), len(xs)), np.inf)
    xi = {v: i for i, v in enumerate(xs)}
    zi = {v: i for i, v in enumerate(zs)}
    for v in V[top_i]:
        j, i = zi[round(v[2], 3)], xi[round(v[0], 3)]
        ytop[j, i] = v[1] if np.isnan(ytop[j, i]) else max(ytop[j, i], v[1])
    for v in V[bot_i]:
        k = (round(v[2], 3), round(v[0], 3))
        if k[0] in zi and k[1] in xi:
            j, i = zi[k[0]], xi[k[1]]
            ybot[j, i] = min(ybot[j, i], v[1])
    if np.isnan(ytop).any() or np.isinf(ybot).any():
        raise SystemExit("斜面の仮置きを格子に戻せない")
    return xs, zs, ytop, ybot, V


def main():
    os.makedirs(os.path.join(BUILD, "water"), exist_ok=True)
    os.makedirs(os.path.join(BUILD, "place"), exist_ok=True)
    spec = T.load_spec()
    cam = C.Cam(spec)
    L = C.load_json(C.LAYOUT_JSON)
    boat = P27.group_tris("boat_blockout")
    slopes = P27.group_tris("revision_slopes")
    b27 = L["boats"]["boat_mid"]
    R = C.quat_to_mat(b27["rotation_quat_xyzw"])
    t0, s0 = np.array(b27["position"]), float(b27["scale"])
    c = cam.pos

    hull_l = boat["Boat_Hull_OpenThick"]["V"]
    hull0 = hull_l * s0 @ R.T + t0
    # ---------------------------------------------------------------- 1. k（投影中心を中心に一様に縮める）
    y_low0 = float(hull0[:, 1].min())
    draft_per_scale = P27.DRAFT_FRACTION * P27.HULL_DEPTH_MID
    k = (c[1] - Y_WATER) / (c[1] - y_low0 - draft_per_scale * s0)
    t1 = c + k * (t0 - c)
    s1 = k * s0
    draft = draft_per_scale * s1

    def W(v):
        return np.asarray(v) * s1 @ R.T + t1
    hull = W(hull_l)
    tips1 = W(np.stack([P27.TIP_PLUS_Z, P27.TIP_MINUS_Z]))
    tips0 = np.stack([P27.TIP_PLUS_Z, P27.TIP_MINUS_Z]) * s0 @ R.T + t0
    px0, _ = cam.project(tips0)
    px1, _ = cam.project(tips1)
    print("k %.5f depth %.3f -> %.3f m, length %.3f -> %.3f m, draft %.3f m" % (
        k, cam.depth(t0), cam.depth(t1), 10 * s0, 10 * s1, draft))
    print("tips px before", np.round(px0, 4).tolist(), "after", np.round(px1, 4).tolist())

    # ---------------------------------------------------------------- K* 45° の唇
    meta = C.load_json(os.path.join(B26, "kstar_%s_meta.json" % KEY_WAVE))
    rows = np.load(os.path.join(B26, "kstar_%s_rows.npz" % KEY_WAVE))
    nu, nv, ktri, KP = read_gwb(os.path.join(B26, "kstar_%s.gwb" % KEY_WAVE))
    Gk = KP.reshape(nv, nu, 3)
    j_tip = meta["profile"]["index"]["j_tip"]
    lip_line = Gk[:, j_tip]
    tip_main, fb_main, crest_main = main_lip(meta, rows)
    k_tris = KP[ktri]
    k_index = BoxIndex(k_tris, 2.0)

    # ---------------------------------------------------------------- 2. 座席の候補
    deck = np.concatenate(boat["Boat_Deck_Planks"]["subs"], 0).reshape(-1, 3)
    deck_w = W(deck).reshape(-1, 3, 3)
    up_b = R[:, 1]
    cands = []
    for zc in SEAT_Z_CANDIDATES:
        probe = W(np.array([0.0, 10.0, zc]))
        hit = P27.ray_hit(deck_w, probe, -up_b)
        if hit is None:
            continue
        eye = hit + np.array([0, EYE_ABOVE_DECK, 0])
        hi = lip_line[lip_line[:, 1] > eye[1] + LIP_ABOVE_EYE_MIN]
        dh = np.hypot(hi[:, 0] - eye[0], hi[:, 2] - eye[2])
        j = int(np.argmin(dh))
        v = hi[j] - eye
        dm = tip_main - eye
        cands.append({"probe_local_z": zc, "deck_hit": r(hit), "eye_world": r(eye),
                      "nearest_lip_tip_horizontal_m": r(dh[j], 3), "nearest_lip_tip_world": r(hi[j], 3),
                      "nearest_lip_tip_elevation_deg": r(math.degrees(math.atan2(v[1], math.hypot(v[0], v[2]))), 2),
                      "main_section_lip_tip_horizontal_m": r(math.hypot(dm[0], dm[2]), 3),
                      "main_section_lip_tip_elevation_deg": r(math.degrees(math.atan2(dm[1], math.hypot(dm[0], dm[2]))), 2)})
        print("seat z %+.1f eye %s lip nearest %.2f m elev %.1f°, main tip %.2f m elev %.1f°" % (
            zc, np.round(eye, 3), dh[j], cands[-1]["nearest_lip_tip_elevation_deg"],
            cands[-1]["main_section_lip_tip_horizontal_m"], cands[-1]["main_section_lip_tip_elevation_deg"]))
    best = min(cands, key=lambda q: (q["nearest_lip_tip_horizontal_m"], -q["probe_local_z"]))
    seat_z = best["probe_local_z"]
    eye = np.array(best["eye_world"])
    look = np.array(best["nearest_lip_tip_world"])
    fwd = (look - eye) / np.linalg.norm(look - eye)
    yaw = math.degrees(math.atan2(fwd[0], fwd[2]))
    pitch = math.degrees(math.asin(fwd[1]))
    print("chosen seat z", seat_z, "eye", eye, "look", look, "yaw %.2f pitch %.2f" % (yaw, pitch))

    # ---------------------------------------------------------------- 3. 竜骨の線と水面の目標
    ax = R[:, 2]                                     # 船の根の局所 +z（原画で左の先端＝船首）
    ah = np.array([ax[0], 0.0, ax[2]])
    ah /= np.linalg.norm(ah)
    nh = np.array([-ah[2], 0.0, ah[0]])
    zl = np.round(hull_l[:, 2], 2)
    slices = []
    for z in np.unique(zl):
        sel = zl == z
        wv = hull[sel]
        lo = wv[np.argmin(wv[:, 1])]
        slices.append((float(z), lo))
    fit = [(z, lo) for z, lo in slices if abs(z) <= KEEL_FIT_Z + 1e-6]
    p_ref = t1.copy()
    s_of = lambda p: (np.asarray(p)[..., [0, 2]] - p_ref[[0, 2]]) @ ah[[0, 2]]  # noqa: E731
    d_of = lambda p: (np.asarray(p)[..., [0, 2]] - p_ref[[0, 2]]) @ nh[[0, 2]]  # noqa: E731
    fs = np.array([s_of(lo) for _, lo in fit])
    fy = np.array([lo[1] for _, lo in fit])
    g, y0 = np.polyfit(fs, fy, 1)
    keel_y = lambda s: y0 + g * s  # noqa: E731
    s_all = s_of(hull)
    d_all = d_of(hull)
    s_min, s_max = float(s_all.min()), float(s_all.max())
    d0 = float(np.abs(d_all).max()) + D0_MARGIN
    print("keel line: y = %.4f + %.4f s (pitch %.2f°), s %.2f..%.2f, d0 %.3f" % (y0, g, math.degrees(math.atan(g)), s_min, s_max, d0))

    def target(x, z):
        p = np.stack([x, np.zeros_like(x), z], -1)
        s = s_of(p)
        d = np.abs(d_of(p))
        ws = 1.0 - smoothstep(0.0, E_ENDS, np.maximum(s_min - s, s - s_max))
        wd = 1.0 - smoothstep(d0, d0 + B_LATERAL, d)
        return np.maximum(keel_y(s) + draft, T_MIN), ws * wd

    # ---------------------------------------------------------------- 4. 斜面の仮置きを作り直して動かす
    dy27 = float(L["placeholders"]["M1_Revision_RightSlope"]["translate_y"])
    xs, zs, ytop, ybot, _ = rebuild_slope(slopes, dy27)
    zc_boat = float(t1[2])
    extra = np.arange(zc_boat - Z_BAND, zc_boat + Z_BAND + 1e-9, Z_REFINE)
    zr = np.unique(np.round(np.concatenate([zs, extra[(extra > zs.min()) & (extra < zs.max())]]), 4))
    yt = np.stack([np.interp(zr, zs, ytop[:, i]) for i in range(len(xs))], 1)
    yb = np.stack([np.interp(zr, zs, ybot[:, i]) for i in range(len(xs))], 1)
    X, Z = np.meshgrid(xs, zr)
    tgt, w = target(X, Z)
    dy = w * (tgt - yt)
    # 船体の平面図の足跡（鉛直線が船体に当たる格子点）では、水面を船体の最も低い面より HOLE_GAP 下げる。
    # 高さ場の水面が船の中（甲板の上）を横切らないようにするため（Unity の不透明な平塗りでは、船体は水を押しのけない）。
    hull_tris = np.concatenate([W(tri.reshape(-1, 3)).reshape(-1, 3, 3) for tri in boat["Boat_Hull_OpenThick"]["subs"]], 0)
    hull_index = BoxIndex(hull_tris, 0.5)
    yt_nohole = yt + dy
    n_hole = 0
    for j in range(len(zr)):
        for i in range(len(xs)):
            if w[j, i] <= 0:
                continue
            hh = hull_index.heights(xs[i], zr[j])
            if len(hh):
                lim = float(hh.min()) - HOLE_GAP
                if yt[j, i] + dy[j, i] > lim:
                    dy[j, i] = lim - yt[j, i]
                    n_hole += 1
    yt2, yb2 = yt + dy, yb + dy
    print("hull footprint grid points lowered:", n_hole)
    nz, nx = yt.shape
    print("slope grid", nx, "x", nz, "dy range %.3f..%.3f" % (dy.min(), dy.max()))

    def grid_tris(off):
        I = []
        for j in range(nz - 1):
            for i in range(nx - 1):
                a, b, cc, d = off + j * nx + i, off + j * nx + i + 1, off + (j + 1) * nx + i, off + (j + 1) * nx + i + 1
                I += [[a, cc, b], [b, cc, d]]
        return I
    Vt = np.stack([X, yt2, Z], -1).reshape(-1, 3)
    Vb = np.stack([X, yb2, Z], -1).reshape(-1, 3)
    verts = [Vt, Vb]
    tri_top = grid_tris(0)
    tri_bot = [[a, c_, b] for a, b, c_ in grid_tris(len(Vt))]
    # 側面（4 辺）：上面と下面の境界の点を結ぶ
    ring = [(0, i) for i in range(nx)] + [(j, nx - 1) for j in range(1, nz)] + [(nz - 1, i) for i in range(nx - 2, -1, -1)] + [(j, 0) for j in range(nz - 2, 0, -1)]
    base = len(Vt) + len(Vb)
    wall_v = []
    for j, i in ring:
        wall_v += [Vt[j * nx + i], Vb[j * nx + i]]
    verts.append(np.array(wall_v))
    tri_wall = []
    m = len(ring)
    for q in range(m):
        a, b = base + 2 * q, base + 2 * ((q + 1) % m)
        tri_wall += [[a, a + 1, b], [b, a + 1, b + 1]]
    Vall = np.concatenate(verts, 0).astype(np.float32)
    sub0 = np.array(tri_top, np.int32)
    sub1 = np.array(tri_bot + tri_wall, np.int32)
    binp = os.path.join(BUILD, "water", "af27r01_right_slope.bin")
    with open(binp, "wb") as f:
        f.write(b"GWM1")
        f.write(struct.pack("<3i", len(Vall), len(sub0) * 3, len(sub1) * 3))
        f.write(Vall.tobytes())
        f.write(sub0.tobytes())
        f.write(sub1.tobytes())
    mesh_meta = {"format_ja": "先頭 'GWM1' + int32 頂点数, 小メッシュ0 の添字数, 小メッシュ1 の添字数。続いて頂点 (N×3 float32、Unity の世界座標 m)、"
                              "小メッシュ0（上面＝白）の三角形 (int32)、小メッシュ1（下面と側面＝藍濃）の三角形 (int32)。",
                 "vertices": int(len(Vall)), "sub0_triangles": int(len(sub0)), "sub1_triangles": int(len(sub1)),
                 "grid_x": int(nx), "grid_z": int(nz), "sha256": C.sha256(binp),
                 "source_ja": "番号27 の M1_Revision_RightSlope（revision_slopes.fbx、+%.4f m 鉛直移動）を格子に戻し、z に 0.25 m 刻みの行を足して作り直した。" % dy27}
    C.save_json(os.path.join(BUILD, "water", "af27r01_right_slope.json"), mesh_meta)

    # ---------------------------------------------------------------- 5. 検査：接水・浸水
    top_tris = Vt[np.array(tri_top)].reshape(-1, 3, 3)
    top_index = BoxIndex(top_tris, 1.0)
    Vt_nohole = np.stack([X, yt_nohole, Z], -1).reshape(-1, 3)
    top_index_nohole = BoxIndex(Vt_nohole[np.array(tri_top)].reshape(-1, 3, 3), 1.0)
    sea_ref = -0.07

    def water_y(x, z, hole=True):
        """その鉛直線上の水面（斜面の仮置きの上面・K* の最も低い面・参照海面の最大）。K* は船の周りでは平らな海だけ。
        hole=False は船体の足跡の穴を開ける前の水面（船の外側の水位＝接水の判定に使う）。"""
        hs = (top_index if hole else top_index_nohole).heights(x, z)
        hk = k_index.heights(x, z)
        cand = [sea_ref]
        if len(hs):
            cand.append(float(hs.max()))
        if len(hk):
            cand.append(float(hk.min()))
        return max(cand)
    contact = []
    for z, lo in slices:
        wy = water_y(lo[0], lo[2], hole=False)
        contact.append({"local_z": z, "hull_bottom_world": r(lo, 4), "water_y": r(wy, 4), "immersion_m": r(wy - lo[1], 4)})
    imm = np.array([q["immersion_m"] for q in contact])
    mid = np.array([abs(q["local_z"]) <= KEEL_FIT_Z for q in contact])
    # 船内の点（甲板・舷・梁の頂点）が水面より下にないか
    inside = {}
    for part in ("Boat_Deck_Planks", "Boat_Gunwale_Left", "Boat_Gunwale_Right", "Boat_Crossbeams"):
        pv = W(boat[part]["V"])
        cl = np.array([p[1] - water_y(p[0], p[2]) for p in pv])
        inside[part] = {"vertices": int(len(pv)), "below_water": int((cl < 0).sum()), "min_clearance_m": r(cl.min(), 4)}
    eye_clear = float(eye[1] - water_y(eye[0], eye[2]))
    # 目が K* の水の中にないか：目から真上へ K* の面の数（奇数なら水の中の可能性）
    hk_eye = k_index.heights(eye[0], eye[2])
    above = hk_eye[hk_eye > eye[1]]
    print("contact immersion mid %.3f..%.3f all %.3f..%.3f; inside" % (imm[mid].min(), imm[mid].max(), imm.min(), imm.max()), inside, "eye clear %.3f" % eye_clear, "K* above eye", np.round(above, 3))

    # 番号27 の置き方（同じ斜面、k なし）の接水（比較）
    contact27 = []
    for z, lo in slices:
        lo0 = c + (lo - c) / k
        hs = heights_at(np.concatenate(slopes["M1_Revision_RightSlope"]["subs"][:1], 0) + np.array([0, dy27, 0]), lo0[0], lo0[2])
        contact27.append({"local_z": z, "hull_bottom_world": r(lo0, 4), "slope_top_y": r(hs.max() if len(hs) else None, 4),
                          "immersion_m": r((max(hs.max(), sea_ref) if len(hs) else sea_ref) - lo0[1], 4)})

    # 68（番号26・CP1 と同じ式）を新しい座席で：3 解釈とも
    m68 = {}
    for kk in ("a30", "a45", "a60"):
        mt = C.load_json(os.path.join(B26, "kstar_%s_meta.json" % kk))
        rw = np.load(os.path.join(B26, "kstar_%s_rows.npz" % kk))
        tp, fb, cr = main_lip(mt, rw)
        d_tip = math.hypot(*(tp - eye)[[0, 2]])
        d_fb = math.hypot(*(fb - eye)[[0, 2]])
        m68[kk] = {"horizontal_distance_seat_to_lip_tip_m": r(d_tip, 3), "horizontal_distance_seat_to_face_bottom_m": r(d_fb, 3),
                   "lip_tip_elevation_deg": r(math.degrees(math.atan2(tp[1] - eye[1], d_tip)), 2),
                   "crest_elevation_deg": r(math.degrees(math.atan2(cr[1] - eye[1], math.hypot(*(cr - eye)[[0, 2]]))), 2),
                   "lip_tip_world": r(tp, 3), "face_bottom_world": r(fb, 3), "verdict": "pass" if d_tip < d_fb else "fail"}
        print("68", kk, m68[kk]["horizontal_distance_seat_to_lip_tip_m"], "<", m68[kk]["horizontal_distance_seat_to_face_bottom_m"], m68[kk]["verdict"])

    # 比較の記録：k を大きくして右船を奥（唇の深さ）へ寄せた場合（採らなかった案。座席の選び方は同じ）
    sweep = []
    k_lip = float(cam.depth(tip_main) / cam.depth(tips0[0]))
    for kk in sorted(set([round(k, 4), 0.80, 0.82, 0.84, round(k_lip, 4)])):
        tt, ss = c + kk * (t0 - c), kk * s0
        Wk = lambda v: np.asarray(v) * ss @ R.T + tt  # noqa: E731
        dwk = Wk(deck).reshape(-1, 3, 3)
        bestk = None
        for zc in SEAT_Z_CANDIDATES:
            hk_ = P27.ray_hit(dwk, Wk(np.array([0.0, 10.0, zc])), -up_b)
            if hk_ is None:
                continue
            ek = hk_ + np.array([0, EYE_ABOVE_DECK, 0])
            hh = lip_line[lip_line[:, 1] > ek[1] + LIP_ABOVE_EYE_MIN]
            dd = np.hypot(hh[:, 0] - ek[0], hh[:, 2] - ek[2])
            jj = int(np.argmin(dd))
            if bestk is None or dd[jj] < bestk[1]:
                bestk = (zc, float(dd[jj]), math.degrees(math.atan2(hh[jj, 1] - ek[1], dd[jj])), ek)
        hw = Wk(hull_l)
        sweep.append({"k": kk, "tips_depth_m": r(cam.depth(Wk(P27.TIP_PLUS_Z)), 3), "tip_to_tip_length_m": r(10 * ss, 3),
                      "hull_lowest_y": r(hw[:, 1].min(), 4), "draft_m": r(draft_per_scale * ss, 4),
                      "bow_immersion_below_flat_sea_m": r(Y_WATER - hw[:, 1].min(), 4), "deck_lowest_y": r(Wk(deck)[:, 1].min(), 4),
                      "seat_probe_local_z": bestk[0], "eye_world": r(bestk[3], 3), "nearest_lip_tip_horizontal_m": r(bestk[1], 3),
                      "nearest_lip_tip_elevation_deg": r(bestk[2], 2), "chosen": bool(abs(kk - k) < 1e-3),
                      "note_ja": "唇先（主断面）の深さに船の両端をそろえる k" if abs(kk - k_lip) < 1e-4 else ""})
        print("sweep k %.4f lip %.2f m elev %.1f deck low %.3f bow imm %.3f" % (kk, bestk[1], bestk[2], sweep[-1]["deck_lowest_y"], sweep[-1]["bow_immersion_below_flat_sea_m"]))

    q1 = C.mat_to_quat(R)
    rec = {
        "k_sweep_record_only": sweep, "k_lip_depth": r(k_lip, 5),
        "k": r(k, 6), "root_depth_m_27": r(cam.depth(t0), 4), "root_depth_m": r(cam.depth(t1), 4),
        "tips_depth_m_27": r(cam.depth(tips0), 4), "tips_depth_m": r(cam.depth(tips1), 4),
        "position_27": r(t0, 5), "position": r(t1, 5), "scale_27": r(s0, 6), "scale": r(s1, 6),
        "tip_to_tip_length_m_27": r(10 * s0, 3), "tip_to_tip_length_m": r(10 * s1, 3), "draft_m": r(draft, 4),
        "tips_world": r(tips1, 4), "tips_projected_px_27": r(px0, 4), "tips_projected_px": r(px1, 4),
        "tips_projected_max_diff_px": r(np.abs(px1 - px0).max(), 6),
        "hull_lowest_y_27": r(y_low0, 4), "hull_lowest_y": r(hull[:, 1].min(), 4),
        "seat_candidates": cands, "seat_probe_local_z": seat_z,
        "keel_line": {"y0": r(y0, 5), "slope_dy_ds": r(g, 5), "pitch_deg": r(math.degrees(math.atan(g)), 3), "s_min": r(s_min, 4), "s_max": r(s_max, 4),
                      "axis_h": r(ah, 6), "normal_h": r(nh, 6), "p_ref": r(p_ref, 5), "d0_m": r(d0, 4)},
        "water": {"T_min": T_MIN, "lateral_blend_m": B_LATERAL, "end_blend_m": E_ENDS, "z_refine_m": Z_REFINE, "z_band_m": Z_BAND,
                  "dy_min_m": r(dy.min(), 4), "dy_max_m": r(dy.max(), 4), "hull_footprint_points_lowered": int(n_hole), "hole_gap_m": HOLE_GAP,
                  "mesh": mesh_meta},
        "contact": contact, "contact_27": contact27,
        "contact_summary": {"immersion_mid_min_m": r(imm[mid].min(), 4), "immersion_mid_max_m": r(imm[mid].max(), 4),
                            "immersion_all_min_m": r(imm.min(), 4), "immersion_all_max_m": r(imm.max(), 4),
                            "slices_floating": int((imm < 0).sum()), "slices": len(imm)},
        "inside_boat_below_water": inside, "eye_above_water_m": r(eye_clear, 4), "kstar_surfaces_above_eye_y": r(above, 3),
        "item68": m68,
    }
    C.save_json(os.path.join(BUILD, "place", "af27r01_place.json"), rec)
    write_seat(rec, L, q1, eye, best, look, yaw, pitch, fwd, tip_main, spec)
    return rec


def write_seat(rec, L, q, eye, best, look, yaw, pitch, fwd, tip_main, spec):
    g26 = os.path.join(B26, "kstar_%s.gwb" % KEY_WAVE)
    S = {
        "schema": "GreatWave.AF27R01.seat/1",
        "version": "seat_v1",
        "number": "27修正01",
        "decision_ja": "D7 = (a)「座席を唇の下の船へ移す」。利用者の CP1 回答（2026-09-26）で、座席は唇の真下の右船（boat_mid）に置く。",
        "coordinates_ja": "Unity の世界座標（m、左手系、Y 上）。回転は Unity の Quaternion の成分 (x, y, z, w)。PaintingCam v1 は (0, 3, −62) から +Z 方向を見る。",
        "boat": {
            "key": "boat_mid", "m1_name": "M1 middle boat", "role_ja": "右の船（原画で唇の下にいる船）。座席のある船。",
            "position": rec["position"], "rotation_quat_xyzw": r(q, 8), "scale": rec["scale"],
            "tips_depth_m": rec["tips_depth_m"], "root_depth_m": rec["root_depth_m"], "tip_to_tip_length_m": rec["tip_to_tip_length_m"], "draft_m": rec["draft_m"],
            "depth_note_ja": "深さは PaintingCam v1 の光軸方向の距離。tips_depth_m は船の両端の先端（番号27 ではこの点を右船の深度平面 59.11 m に置いた）、root_depth_m は船の根の原点。",
            "from_27_ja": "番号27 の右船（context_layout.json の boat_mid）を、PaintingCam v1 の投影中心 (0, 3, −62) を中心に k 倍した。"
                          "回転は番号27 と同じ。原画視点の像は変わらない（両端の投影の差 %.6f px）。" % rec["tips_projected_max_diff_px"],
            "k": rec["k"], "position_27": rec["position_27"], "scale_27": rec["scale_27"], "tips_depth_m_27": rec["tips_depth_m_27"], "root_depth_m_27": rec["root_depth_m_27"],
            "k_rule_ja": "船体の最も低い点が平らな海（y = 0）より喫水（0.35 × 0.96 m × 縮尺）だけ下になる k。",
        },
        "seat": {
            "posture_ja": "座位。目は甲板から 1.2 m 上（世界の上向き）。",
            "probe_local": [0.0, 10.0, best["probe_local_z"]], "eye_above_deck_m": EYE_ABOVE_DECK,
            "deck_hit_world": best["deck_hit"], "eye_world": best["eye_world"],
            "rule_ja": "船の根の局所 (0, 10, z) から船の局所の下向きに甲板（Boat_Deck_Planks）を測り、当たった点の 1.2 m 上（番号27 と同じ測り方）。"
                       "z は |z| ≤ 3.0 を 0.5 刻みで調べ、K* 45°（番号26）の唇先の線（目より 3 m 以上高い点）に水平距離で最も近い甲板の点を選んだ。"
                       "選ばれた z = +3.0 は調べた範囲の船首側の端（甲板は局所 z ±3.49 まで、その先は尖った船首）。",
            "consumers_ja": "Python（番号26・30 など）は seat.eye_world・view.target_world・view.vertical_fov_deg を読む。Unity は unity 区画（JsonUtility）か、"
                            "プレハブ AF27R01_Context.prefab の「AF27R01 座席 v1」の Transform（位置＝目、向き＝注視点）を使う。"
                            "番号26 の af26_blender_qa.py には eye_world と view.qa_hemisphere_look_world を渡す。",
            "up_world": [0.0, 1.0, 0.0],
            "up_note_ja": "視点の上向きは世界の +Y（水平線を水平に保つ）。船の t* の傾き（軸の縦の傾き約 33°・軸まわり 25°）には合わせない（既定値・利用者未回答）。",
        },
        "view": {
            "target_world": r(look, 3), "forward_world": r(fwd, 6), "yaw_deg": r(yaw, 3), "pitch_deg": r(pitch, 3),
            "vertical_fov_deg": 80.0,
            "target_source_ja": "K* 45°（番号26 のコミット a2e6abc、kstar_a45.gwb）の唇先の線のうち座席に水平で最も近い点。PC の座席の静止画の注視点に使う。"
                                "番号26修正01 で唇が変わったら、同じ規則で注視点だけ取り直せばよい（座席の位置は変えない）。",
            "recenter_yaw_deg": r(yaw, 3), "recenter_ja": "HMD の再センタリングの正面（水平の向き）。未検証（HMD 未所持）。",
            "main_section_lip_tip_world": r(tip_main, 3),
            "qa_hemisphere_look_world": r(eye + (np.array([fwd[0], 0.0, fwd[2]]) / math.hypot(fwd[0], fwd[2]) * math.cos(math.radians(20)) + np.array([0.0, math.sin(math.radians(20)), 0.0])) * 10.0, 4),
            "qa_hemisphere_ja": "座席からの射線検査（83/115/116 の事前検査）の半球の中心：唇の方位（yaw_deg）で仰角 20°、目から 10 m 先の点。Unity の「座席 v1（唇の方位、仰角 20°）」のカメラと同じ向き。",
        },
        "water_contact": {
            "keel_line_ja": "竜骨の線 y = y0 + slope·s（s は p_ref から船の軸の水平方向 axis_h へ測る水平距離。船体中央部 |z| ≤ 3 の船底の直線当てはめ）。"
                            "右船の水面（番号40 の右側の波で置き換えるときも）は、船体のすぐ外側で 竜骨の線 + 喫水（0.3806 m）の高さにし、船体の平面図の足跡の中では船底より下に置く"
                            "（高さ場の水面が船の中の甲板と座席を横切らないように）。",
            **{k_: rec["keel_line"][k_] for k_ in ("y0", "slope_dy_ds", "pitch_deg", "s_min", "s_max", "axis_h", "p_ref")},
            "draft_m": rec["draft_m"],
            "placeholder_ja": "番号40 までは、右の斜面の仮置きを作り直した水面（Unity の AF27R01_RightSlope.asset）で支える。",
            "immersion_summary": rec["contact_summary"],
            "immersion_note_ja": "immersion は船の根の局所 z の 11 の切り口ごとの船底の沈み（正が水面より下）。水面より上に出る 2 つは反り上がった船尾の先（局所 z −5.0・−4.6）で、宙に浮いた船体ではない。",
        },
        "legacy_seats": {
            "m1_revision01_eye": [-0.707, 1.5143, -33.407],
            "number27_fg_eye": L["seat"]["eye_world"],
            "cp1_candidate_right_boat_eye_27_pose": [11.274, 5.048, -1.582],
            "note_ja": "旧い座席。番号27 の手前の船の座席は CP1 まで使った。CP1 の候補 (a) は番号27 の右船の置き方（k なし）での確認用の機位。",
        },
        "sources_sha256": {
            "Tools/GWContext/context_layout.json": C.sha256(C.LAYOUT_JSON),
            "Unity/Build/ArtFirst/26/kstar/kstar_a45.gwb": C.sha256(g26),
            "Unity/Build/ArtFirst/27/dump/boat_blockout.bin": C.sha256(os.path.join(C.BUILD, "dump", "boat_blockout.bin")),
            "Unity/Build/ArtFirst/27/dump/revision_slopes.bin": C.sha256(os.path.join(C.BUILD, "dump", "revision_slopes.bin")),
            "Tools/PaintingTruth/painting_truth.json": C.sha256(os.path.join(REPO, "Tools", "PaintingTruth", "painting_truth.json")),
        },
        "generator": "Tools/GWContext/af27r01_seat.py",
        "painting_cam": spec["painting_cam"],
    }
    S["unity"] = {
        "boatKey": "boat_mid", "boatPosition": S["boat"]["position"], "boatRotation": S["boat"]["rotation_quat_xyzw"], "boatScale": S["boat"]["scale"],
        "probeLocal": S["seat"]["probe_local"], "eyeAboveDeck": EYE_ABOVE_DECK, "eyeNumpy": S["seat"]["eye_world"],
        "target": S["view"]["target_world"], "fov": 80.0, "waterMeshBin": "Build/ArtFirst/27R01/water/af27r01_right_slope.bin",
        "keelY0": rec["keel_line"]["y0"], "keelSlope": rec["keel_line"]["slope_dy_ds"], "keelAxisH": rec["keel_line"]["axis_h"],
        "keelNormalH": rec["keel_line"]["normal_h"], "keelRef": rec["keel_line"]["p_ref"], "draft": rec["draft_m"],
    }
    C.save_json(SEAT_JSON, S)
    print("wrote", SEAT_JSON)


if __name__ == "__main__":
    main()
