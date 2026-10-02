# -*- coding: utf-8 -*-
"""仕上げ33修正01（Houdini の変種）：立つ白い爪の指の共通の部品（numpy だけ。Houdini を使わない側）。

入力は仕上げ33 の採用の爪の並び（Unity/Build/Polish/33/fix02/claws、GreatWave.DS33.claw_layout/1）。
爪ごとの頂点の並び（設計33）：根元の点 1・輪 stations × 8（φ = 0, 45, …, 315°、φ 90° が上＝面の法線）・先 1・根元の白の円の中心 1・円 8。
ここから、コマごとに「面の上の中心線」（根元・輪の中心 20・先 = 22 点）、上の向き、半幅（φ 0° と 180° の間の半分）を取り出す。
これらは仕上げ32 の爪の一覧（249 本の爪、ID・型、K*′ P28R2rec のシートへの結び付け）から来た中心線で、原画視点の投影は一覧の中心線に合う。

立つ指（pl33r01h_stand）：中心線の各点を、その点から原画のカメラ（PaintingCam v1、Unity の (0, 3, −62)）へ向かう射線の上で手前へ動かす。
  動かす量 d(u) = H · curl(u) · grow / max(n0·L, FACE_MIN)（H は t* の弧長から決める立ち上がりの高さ、curl は Houdini の CTRL の
  曲がりのランプ（根元 0 → 立ち上がり → 先で面の側へ少し巻き戻る）、grow はそのコマの弧長 ÷ t* の弧長）。
  射線の上を動かすだけなので、原画視点の投影（一覧の爪の輪の形）は変わらない。ほかの視点からは、面から立って巻く指に見える。
  冠の爪（K…。原画視点では頂の裏で隠れる）は動かさない（もとから面から 55° で立ち上がる鉤）。
半径 r(u) = 半幅(u) · taper(u)（taper は Houdini の CTRL の細りのランプ）。丸い断面なので、どの視点からも投影の幅は 2r（原画視点の幅は帯と同じ）。
原画カメラからの投影の色は使わない（Q28）。原画のカメラは、立ち上げの向きを決めるためだけに使う。
"""
import json
import os

import numpy as np

ROOT = "G:/Unity/GreatWave_2026_Fresh"
SRC_CLAWS = ROOT + "/Unity/Build/Polish/33/fix02/claws"
OUT = ROOT + "/Unity/Build/Polish/33r01/houdini"
CAM_U = np.array([0.0, 3.0, -62.0])     # PaintingCam v1（Unity のワールド、m）
K_STAR = 360                            # t* = 12 s のコマ
FACE_MIN = 0.35
NPT = 22                                # 根元 1 + 輪 20 + 先 1


def u2h(P):
    """Unity → Houdini（z を反転。kh_common.u2h と同じ。自分自身が逆）"""
    P = np.asarray(P, np.float64)
    return P * np.array([1.0, 1.0, -1.0])


h2u = u2h


def sha256(path, chunk=1 << 22):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def load_layout(d=SRC_CLAWS):
    L = json.load(open(d + "/ds33_claw_layout.json", encoding="utf-8"))
    F = np.memmap(d + "/" + L["files"]["frames"]["file"], np.float32, "r").reshape(L["frames"], L["vertices"], 3)
    return L, F


def select_items(L, kinds=("C", "S", "K")):
    sel = [c for c in L["claws"] if c["id"][0] in kinds]
    return sel


def spines_frame(F, f, items):
    """コマ f の面の上の中心線 C (n,22,3)、上の向き UP (n,22,3)、半幅 HW (n,22)、根元の円 RC (n,9,3)（Unity の座標）。"""
    n = len(items)
    C = np.zeros((n, NPT, 3)); UP = np.zeros((n, NPT, 3)); HW = np.zeros((n, NPT)); RC = np.zeros((n, 9, 3))
    V = np.asarray(F[f], np.float64)
    for i, it in enumerate(items):
        o, st = it["vert_offset"], it["stations"]
        root = V[o]
        rings = V[o + 1:o + 1 + 8 * st].reshape(st, 8, 3)
        tip = V[o + 1 + 8 * st]
        circ = V[o + 2 + 8 * st:o + 11 + 8 * st]
        cen = rings.mean(axis=1)
        up = rings[:, 2] - cen
        nu = np.linalg.norm(up, axis=1, keepdims=True)
        up = np.where(nu > 1e-9, up / np.maximum(nu, 1e-12), 0.0)
        hw = 0.5 * np.linalg.norm(rings[:, 0] - rings[:, 4], axis=1)
        c = np.vstack([root[None], cen, tip[None]])
        u = np.vstack([up[:1], up, up[-1:]])
        w = np.concatenate([hw[:1], hw, [0.0]])
        if st + 2 == NPT:
            C[i], UP[i], HW[i] = c, u, w
        else:   # 輪の数が 20 でない爪（16）は、輪の番号の割合で 22 点へ取り直す
            x0 = np.linspace(0.0, 1.0, st + 2); x1 = np.linspace(0.0, 1.0, NPT)
            for k in range(3):
                C[i, :, k] = np.interp(x1, x0, c[:, k]); UP[i, :, k] = np.interp(x1, x0, u[:, k])
            HW[i] = np.interp(x1, x0, w)
            nu = np.linalg.norm(UP[i], axis=1, keepdims=True)
            UP[i] = np.where(nu > 1e-9, UP[i] / np.maximum(nu, 1e-12), 0.0)
        RC[i] = circ
    return C, UP, HW, RC


def arclen(C):
    return np.linalg.norm(np.diff(C, axis=1), axis=2).sum(axis=1)


def arc_u(C):
    seg = np.linalg.norm(np.diff(C, axis=1), axis=2)
    cum = np.concatenate([np.zeros((len(C), 1)), np.cumsum(seg, axis=1)], axis=1)
    tot = np.maximum(cum[:, -1:], 1e-9)
    return cum / tot


def ramp_eval(samples, u):
    """Houdini の CTRL から書き出したランプの標本（等間隔 0..1）を線形補間する。"""
    s = np.asarray(samples, np.float64)
    x = np.linspace(0.0, 1.0, len(s))
    return np.interp(np.clip(u, 0.0, 1.0), x, s)


def stand(C, UP, HW, U_star, H, kind_lift, A_now, A_star, ramps, prm):
    """立つ指の中心線 P (n,22,3) と半径 R (n,22)（Unity の座標）。U_star は t* の弧長の割合（爪ごとに固定）。"""
    curl = ramp_eval(ramps["curl"], U_star)                     # (n,22)
    taper = ramp_eval(ramps["taper"], U_star)
    g = np.clip(A_now / np.maximum(A_star, 1e-9), 0.0, 1.0)     # 伸びの割合
    gc = np.clip((g - prm["curl_g0"]) / max(1e-6, 1.0 - prm["curl_g0"]), 0.0, 1.0)
    gc = gc * gc * (3 - 2 * gc)
    # 巻き戻し（先の側で curl が下がる部分）は伸びの後半にだけ効かせる：curl_eff = rise + (curl − rise)·gc（rise は curl の最大までの単調な包絡）
    rise = np.maximum.accumulate(curl, axis=1)
    curl_eff = rise + (curl - rise) * gc[:, None]
    L = CAM_U[None, None, :] - C
    L = L / np.maximum(np.linalg.norm(L, axis=2, keepdims=True), 1e-9)
    n0 = UP[:, 0:1, :]
    face = np.clip(np.abs((n0 * L).sum(axis=2)), prm["face_min"], 1.0)
    d = (H * g)[:, None] * curl_eff / face
    d = np.minimum(d, prm["d_max"])
    d = d * kind_lift[:, None]
    P = C + L * d[:, :, None]
    R = np.maximum(HW * taper * prm["r_scale_kind"][:, None], 0.0)
    R = np.where(HW > 1e-6, np.maximum(R, prm["r_min"] * (HW > 1e-6)), 0.0)
    # 先の点（帯の先端 HW = 0）は前の輪の半径の 0.6 倍の丸い先にする
    R[:, -1] = 0.6 * R[:, -2]
    return P, R, d


# Houdini の CTRL のランプの既定（線形。houdini_build.py がこの値で CTRL を作り、評価した標本を ramps.json へ書く。
# deform はその標本を読むので、Houdini の側でランプを変えれば、全部のコマに同じ形が入る）
CURL_KEYS = [(0.0, 0.0), (0.15, 0.3), (0.45, 0.85), (0.7, 1.0), (0.88, 0.8), (1.0, 0.5)]
TAPER_KEYS = [(0.0, 1.15), (0.25, 1.05), (0.6, 0.85), (0.85, 0.55), (1.0, 0.3)]

PRM = {
    "h_rel": 0.75, "h_add": 0.2, "h_min": 0.3, "h_max": 1.8,   # 立ち上がりの高さ H = clip(h_rel·A* + h_add)（原画の爪・添え指）
    "face_min": FACE_MIN, "d_max": 3.0,                         # 射線の上の動きの上限（m）
    "clear": 1.05,                                              # 指の管が面の手前に収まる（d ≥ clear·r / face）
    "r_min": 0.03, "tip_r": 0.6, "rk_C": 1.0, "rk_S": 1.0, "rk_K": 1.3,
    "ell_k": 3.0,                                               # 原画の爪・添え指の断面を射線の向きへ ell_k 倍に伸ばす（原画視点の幅は変わらない。pl33r01h_depth_section）
    "curl_g0": 0.6,                                             # 先の巻き戻しは伸びの 60% から
    "k_lift_u0": 0.15, "k_lift_u1": 0.45,                       # 冠の爪：根元の側を管の半径だけ面の外へ（0.15〜0.45 で 0 へ）
    "pad_rel": 0.4, "pad_min": 0.025, "pad_max": 0.08, "pad_gap": 0.01,   # 頂の帯（根元の白の円の上の薄い帯）の粒の半径
    "close_rel": 0.35, "close_min": 0.02, "close_max": 0.08,     # 滑らかな和（VDB の閉じ）の半径
    "vox_rel": 0.3, "vox_min": 0.01, "vox_max": 0.045,
    "area_per_pt": 0.0035, "npts_min": 60, "npts_max": 900,
    "a_min": 0.05,                                              # t* の弧長がこれ未満の爪（潰れた添え指）は作らない
}


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def circle_normal(RC):
    """根元の白の円（中心 1・円 8）の面の法線 (n,3)。"""
    a = RC[:, 1] - RC[:, 5]
    b = RC[:, 3] - RC[:, 7]
    n = np.cross(a, b)
    nn = np.linalg.norm(n, axis=1, keepdims=True)
    return np.where(nn > 1e-12, n / np.maximum(nn, 1e-12), 0.0)


def stand2(C, UP, HW, RC, U_star, H, kind, sgn, A_now, A_star, ramps, prm=PRM):
    """立つ指の中心線 P (n,22,3)・半径 R (n,22)・外向きの法線 NO (n,3)（Unity の座標）。kind：0 原画の爪 C、1 添え指 S、2 冠の爪 K。
    sgn：t* で決めた根元の円の法線の向き（C・S は原画のカメラの側、K は帯の上の向きの側）。Houdini の stand の wrangle と同じ式。"""
    curl = ramp_eval(ramps["curl"], U_star)
    taper = ramp_eval(ramps["taper"], U_star)
    g = np.clip(A_now / np.maximum(A_star, 1e-9), 0.0, 1.0)
    gc = ss(prm["curl_g0"], 1.0, g)
    rise = np.maximum.accumulate(curl, axis=1)
    curl_eff = rise + (curl - rise) * gc[:, None]
    rk = np.where(kind == 2, prm["rk_K"], np.where(kind == 1, prm["rk_S"], prm["rk_C"]))
    R = HW * taper * rk[:, None]
    R = np.where(HW > 1e-6, np.maximum(R, prm["r_min"]), 0.0)   # pl33r01h_tip_keep：先の細い所も VDB の格子で消えない太さに
    R[:, -1] = prm["tip_r"] * R[:, -2]
    NO = circle_normal(RC) * sgn[:, None]
    L = CAM_U[None, None, :] - C
    L = L / np.maximum(np.linalg.norm(L, axis=2, keepdims=True), 1e-9)
    face = np.clip(np.abs((NO[:, None, :] * L).sum(axis=2)), prm["face_min"], 1.0)
    d = (H * g)[:, None] * curl_eff / face
    d = np.maximum(d, prm["clear"] * R / face)
    d = np.minimum(d, prm["d_max"])
    lift = (kind != 2).astype(np.float64)
    P = C + L * (d * lift[:, None])[:, :, None]
    kl = (kind == 2).astype(np.float64)[:, None] * R * (1.0 - ss(prm["k_lift_u0"], prm["k_lift_u1"], U_star))
    P = P + NO[:, None, :] * kl[:, :, None]
    return P, R, NO


def proj_ratio(F, f, items, C):
    """t* の帯の、原画のカメラから見た幅（射線に直交する面へ投影し、投影した中心線に直交する成分）÷ 帯の 3D の幅（爪ごと・22 点）。
    丸い管の半径をこの比で縮めると、原画視点の投影の幅が帯（＝一覧の領域に合わせた幅）と同じになる（pl33r01h_paint_width）。冠の爪は 1。"""
    n = len(items)
    Rt = np.ones((n, NPT))
    V = np.asarray(F[f], np.float64)
    for i, it in enumerate(items):
        if it["id"][0] == "K":
            continue
        o, st = it["vert_offset"], it["stations"]
        rings = V[o + 1:o + 1 + 8 * st].reshape(st, 8, 3)
        cen = rings.mean(axis=1)
        w = rings[:, 0] - rings[:, 4]
        r = cen - CAM_U[None]; r /= np.maximum(np.linalg.norm(r, axis=1, keepdims=True), 1e-9)
        tg = np.gradient(cen, axis=0) if st > 1 else np.zeros_like(cen)
        tg = tg - (tg * r).sum(1, keepdims=True) * r
        tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)
        wp = w - (w * r).sum(1, keepdims=True) * r
        wp = wp - (wp * tg).sum(1, keepdims=True) * tg
        q = np.clip(np.linalg.norm(wp, axis=1) / np.maximum(np.linalg.norm(w, axis=1), 1e-9), 0.15, 1.0)
        q = np.concatenate([q[:1], q, q[-1:]])
        if st + 2 != NPT:
            q = np.interp(np.linspace(0, 1, NPT), np.linspace(0, 1, st + 2), q)
        Rt[i] = q
    return Rt
