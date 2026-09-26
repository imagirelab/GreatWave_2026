# -*- coding: utf-8 -*-
"""番号27：3隻の船と富士を原画から各自の深度平面へ逆投影し、配置と縮尺をやり直す。前景のうねりと斜面の仮置きの配色と支えを決める。

使い方（リポジトリ根で）: py -3.10 Tools/GWContext/af27_place.py
前提: Unity の AF27ContextBuilder.Dump の出力（Unity/Build/ArtFirst/27/dump/）と Tools/GWContext/sky_dome.json（af27_sky.py）。
出力: Tools/GWContext/context_layout.json（Unity の AF27 が読む）、Unity/Build/ArtFirst/27/place/（当てはめの記録と確認図）。

船（3隻とも M1 の同じ blockout。船首・船尾の先端の間は 10.0 m）
- 深度平面：各船の M1 Revision01 の基準点（配置用の親の原点）の光軸方向の深さ D を使い、PaintingCam の光軸に垂直な平面 z_c = D を
  その船の深度平面とする（右船 59.11 m は番号24 の主断面と同じ深さ、手前の船 29.48 m は座席のある船、左奥の船 50.30 m）。
- 原画で船の両端（左端・右端の先端、manual_landmarks.json）を読み、その射線と深度平面の交点へ blockout の両端の先端を合わせる
  （船の軸は深度平面の中にある）。blockout の船は原画の三日月形より舷の反りが小さく、両端だけを合わせると船体が原画より上に出て
  富士の裾と暗い空を隠すので、両端の点の組に画面上の相似変換（平行移動・回転・拡大）と軸まわりの傾き（ロール）を加え、番号23 真値の
  船の黄土マスク（閉じて穴を埋めた形）との IoU が最大になるよう Nelder–Mead で決める（初期値は両端の読み、ロール −30/0/30°）。
- 形は変えない（74/75/157/159/161/162 は報告項目。形の修正は G18）。
富士
- 深度平面は M1 の位置（z 420）に固定し、底面を海面（y −0.1）に置いたまま、横位置・幅・高さの縮尺を、真値 74/161（富士の稜線）の
  点までの距離（両方向の平均 + 最大の 1/4）が最小になるよう Nelder–Mead で決める。
支え（船が宙に浮かないように）
- 手前の船は平らな参照海面（上面 y −0.07）、右の船は右の斜面、左奥の船は左の支え斜面に載せる。竜骨の中央（blockout の根の原点、
  船体の底の長さ方向の中央）が支えの面より喫水（船の中央の深さ 0.96 m の 35% × 縮尺）だけ下になるよう、支えの仮置きを鉛直に
  動かす（船は動かさない。海面は動かさず確かめるだけ）。
配色（調色板の平塗り、番号23 palette.json の 8bit sRGB）
- 船：船体・甲板は黄土、縁と梁は藍濃。富士：雪と山肌。参照海面：藍濃（番号24 と同じ）。
- 仮置き：M1 の材質名で置き換える（藍 → 藍濃、青 → 原画でその仮置きの下に最も多い水の色、白泡 → 白）。
"""
import math
import os

import cv2
import numpy as np

import af27common as C
from af27common import T

OUT = os.path.join(C.BUILD, "place")
M1_LAYOUT = os.path.join(C.REPO, "Docs", "Evidence", "M1", "Revision01", "15_revision_layout.json")
LANDMARKS = os.path.join(C.HERE, "manual_landmarks.json")
BOATS = {
    "boat_fg": {"m1": "M1 foreground boat", "close": 6, "backlog": 75, "support": "sea", "fit": "iou", "role_ja": "手前の船（座席のある船）"},
    "boat_mid": {"m1": "M1 middle boat", "close": 6, "backlog": 159, "support": "M1_Revision_RightSlope", "fit": "stern_line", "role_ja": "右の船（番号24 の主断面と同じ深さ）"},
    "boat_left": {"m1": "M1 left boat", "close": 14, "backlog": 157, "support": "M1_Revision_LeftSupport", "fit": "iou", "role_ja": "左奥の船"},
}
TIP_PLUS_Z = np.array([0.012, 1.775, 5.0])    # blockout の +z 端の先端（dump で確認）
TIP_MINUS_Z = np.array([0.012, 1.685, -5.0])  # −z 端の先端
HULL_DEPTH_MID = 0.96                          # blockout の船体中央の深さ（m、縮尺 1）
DRAFT_FRACTION = 0.35
SEA_TOP_Y = -0.07                              # M1 参照海面（位置 y −0.32、厚さ 0.5）の上面
SEAT_PROBE_LOCAL = np.array([0.0, 10.0, -2.0]) # M1RevisionBuilder と同じ座席の測り方
EYE_ABOVE_DECK = 1.2
MAX_IMAGE_ROT = 10.0                           # 両端の読みからの画面上の回転の上限（度、超えた分に罰）
MAX_ROLL = 25.0                                # 船の軸まわりの傾きの上限（度、超えた分に罰）
CLEAR_WEIGHT = 1.0                             # 真値の空・富士の山体を船が覆った面積（船の目標の面積で割る）への罰の重み
FUJI_M1 = {"position": [37.0, -0.1, 420.0], "scale": 2.0}
PALETTE_KEYS_WATER = ["white", "mizuiro", "ai_mid", "ai_dark"]


def nelder_mead(f, x0, step, iters=300, tol=1e-6):
    n = len(x0)
    pts = [np.array(x0, np.float64)]
    for i in range(n):
        p = np.array(x0, np.float64)
        p[i] += step[i]
        pts.append(p)
    vals = [f(p) for p in pts]
    it = 0
    for it in range(iters):
        o = np.argsort(vals)
        pts = [pts[i] for i in o]
        vals = [vals[i] for i in o]
        if abs(vals[-1] - vals[0]) < tol:
            break
        c = np.mean(pts[:-1], axis=0)
        xr = c + (c - pts[-1])
        fr = f(xr)
        if fr < vals[0]:
            xe = c + 2 * (c - pts[-1])
            fe = f(xe)
            pts[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            pts[-1], vals[-1] = xr, fr
        else:
            xc = c + 0.5 * (pts[-1] - c)
            fc = f(xc)
            if fc < vals[-1]:
                pts[-1], vals[-1] = xc, fc
            else:
                for i in range(1, len(pts)):
                    pts[i] = pts[0] + 0.5 * (pts[i] - pts[0])
                    vals[i] = f(pts[i])
    i = int(np.argmin(vals))
    return pts[i], vals[i], it


def group_tris(group, skip=()):
    _, meshes = C.load_dump(group)
    out = {}
    for m in meshes:
        if any(s in m["name"] for s in skip):
            continue
        out[m["name"]] = {"subs": [m["V"][I] for I in m["subs"]], "materials": m["materials"], "V": m["V"], "subI": m["subs"]}
    return out


def unit(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v)


def rot_about(axis, ang_deg, v):
    a = unit(axis)
    t = math.radians(ang_deg)
    return v * math.cos(t) + np.cross(a, v) * math.sin(t) + a * (a @ v) * (1 - math.cos(t))


def boat_pose(cam, lm_left, lm_right, depth, roll_deg):
    """左端 ↔ blockout の +z 端、右端 ↔ −z 端。両端を深度平面 z_c = depth の上に置く。"""
    def on_plane(p):
        d = cam.ray(np.array([p[0]]), np.array([p[1]]))[0]
        return cam.pos + d * (depth / float(d @ cam.f))
    Pb, Ps = on_plane(lm_left), on_plane(lm_right)
    am = unit(TIP_PLUS_Z - TIP_MINUS_Z)
    aw = unit(Pb - Ps)
    s = float(np.linalg.norm(Pb - Ps) / np.linalg.norm(TIP_PLUS_Z - TIP_MINUS_Z))
    Y = np.array([0.0, 1.0, 0.0])
    um = unit(Y - (Y @ am) * am)
    uw = unit(Y - (Y @ aw) * aw)
    uw = rot_about(aw, roll_deg, uw)
    Mm = np.stack([np.cross(um, am), um, am], 1)
    Mw = np.stack([np.cross(uw, aw), uw, aw], 1)
    R = Mw @ Mm.T
    t = Pb - s * (R @ TIP_PLUS_Z)
    return t, R, s, Pb, Ps


def world_of(parts, R, s, t, S=None):
    """parts の三角形を世界へ。S は軸ごとの縮尺（富士）。"""
    out = []
    for p in parts.values():
        for tri in p["subs"]:
            v = tri.reshape(-1, 3)
            v = v * (S if S is not None else s)
            out.append((v @ R.T + t).reshape(-1, 3, 3))
    return np.concatenate(out, 0)


def surface_height(tris, xz):
    """鉛直線 (x, z) と三角形（世界）の交点の y の最大（なければ NaN）。"""
    A, B, Cc = tris[:, 0], tris[:, 1], tris[:, 2]
    out = np.full(len(xz), np.nan)
    for k, (x, z) in enumerate(xz):
        v0 = np.stack([B[:, 0] - A[:, 0], B[:, 2] - A[:, 2]], 1)
        v1 = np.stack([Cc[:, 0] - A[:, 0], Cc[:, 2] - A[:, 2]], 1)
        v2 = np.stack([x - A[:, 0], z - A[:, 2]], 1)
        den = v0[:, 0] * v1[:, 1] - v1[:, 0] * v0[:, 1]
        ok = np.abs(den) > 1e-12
        u = np.where(ok, (v2[:, 0] * v1[:, 1] - v1[:, 0] * v2[:, 1]) / np.where(ok, den, 1), -1)
        w = np.where(ok, (v0[:, 0] * v2[:, 1] - v2[:, 0] * v0[:, 1]) / np.where(ok, den, 1), -1)
        inside = ok & (u >= -1e-9) & (w >= -1e-9) & (u + w <= 1 + 1e-9)
        if inside.any():
            y = A[inside, 1] + u[inside] * (B[inside, 1] - A[inside, 1]) + w[inside] * (Cc[inside, 1] - A[inside, 1])
            out[k] = y.max()
    return out


def ray_hit(tris, p, d):
    """点 p から向き d の射線と三角形の最初の交点（Möller–Trumbore）。"""
    d = unit(d)
    A, B, Cc = tris[:, 0], tris[:, 1], tris[:, 2]
    e1, e2 = B - A, Cc - A
    h = np.cross(np.broadcast_to(d, e2.shape), e2)
    a = np.einsum("ij,ij->i", e1, h)
    ok = np.abs(a) > 1e-12
    f = np.where(ok, 1.0 / np.where(ok, a, 1), 0)
    sv = p - A
    u = f * np.einsum("ij,ij->i", sv, h)
    q = np.cross(sv, e1)
    v = f * (q @ d)
    t = f * np.einsum("ij,ij->i", e2, q)
    hit = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
    if not hit.any():
        return None
    return p + d * t[hit].min()


def main():
    os.makedirs(OUT, exist_ok=True)
    spec = T.load_spec()
    fm = T.FrameMap(spec)
    cam = C.Cam(spec)
    Lm = C.load_json(LANDMARKS)
    M1 = C.load_json(M1_LAYOUT)
    m1b = {b["name"]: b for b in M1["boats"]}
    boat = group_tris("boat_blockout")
    reg = C.load_json(os.path.join(T.TARGET_DIR, "regions.json"))
    palette = C.load_json(os.path.join(T.TARGET_DIR, "palette.json"))["palette"]
    ref, disp = T.painting_display(spec, fm)
    vis = (disp.astype(np.float32) * 0.55).astype(np.uint8)
    slopes = group_tris("revision_slopes")
    sky_t = T.load_cov_png(os.path.join(T.TARGET_DIR, "masks", "sky_claws_cov.png")) > 0.5
    fuji_zone = T.poly_mask((C.H, C.W), reg["polygons_display"]["fuji_zone"])
    res = {"boats": {}}

    # ---------------- 船
    for key, b in BOATS.items():
        cov = T.load_cov_png(os.path.join(T.TARGET_DIR, "masks", key + "_cov.png"))
        m = (cov > 0.5).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, T.disk(b["close"]))
        m = T.fill_small_enclosed(m.astype(bool), 10 ** 7)
        roi = T.poly_mask((C.H, C.W), reg["polygons_display"][key + "_roi"])
        tgt = m & roi
        # 船が覆ってはいけない所：真値の空と、富士の山体（fuji_zone の中で空でも船の黄土でもなく、y ≤ 772 の所）
        clear = (sky_t | (fuji_zone & ~sky_t & ~tgt & (np.mgrid[0:C.H, 0:C.W][0] <= 772))) & ~tgt
        mb = m1b[b["m1"]]
        depth = float(cam.depth([mb["position"][k] for k in "xyz"]))
        lm = Lm["boats"][key]
        c0 = 0.5 * (np.array(lm["left_tip"]) + np.array(lm["right_tip"]))

        def tips(prm):
            dx, dy, th, ls, _ = prm
            ls = 0.0  # 長さは両端の読みのまま（IoU は太い所だけを覆うよう船を縮めてしまうため）
            ct, st = math.cos(math.radians(th)), math.sin(math.radians(th))
            Rm = np.array([[ct, -st], [st, ct]]) * math.exp(ls)
            return [c0 + Rm @ (np.array(lm[k]) - c0) + [dx, dy] for k in ("left_tip", "right_tip")]

        def loss(prm):
            a_, b_ = tips(prm)
            t_, R_, s_, _, _ = boat_pose(cam, a_, b_, depth, prm[4])
            a = C.raster_mask(cam, world_of(boat, R_, s_, t_), ss=1) > 0.5
            pen = 0.01 * max(0.0, abs(prm[2]) - MAX_IMAGE_ROT) ** 2 + 0.01 * max(0.0, abs(prm[4]) - MAX_ROLL) ** 2
            pen += CLEAR_WEIGHT * float((a & clear).sum()) / max(1.0, float(tgt.sum()))
            return 1.0 - float((a & tgt).sum()) / max(1, float((a | tgt).sum())) + pen
        if b["fit"] == "stern_line":
            # 右船：右端（船尾）を合わせ、右半分の上り坂の舷に沿う向きへ、両端の読みと同じ画面上の長さだけ伸ばした点を左端にする。
            # 船首の側は右の斜面の仮置きの中へ沈む。ロールだけ IoU で選ぶ。
            rt = np.array(lm["right_tip"])
            dvec = np.array(lm["stern_line_point"]) - rt
            Limg = float(np.linalg.norm(np.array(lm["left_tip"]) - rt))
            lt = rt + dvec / np.linalg.norm(dvec) * Limg
            sc = []
            for r_ in range(-25, 26):
                t_, R_, s_, _, _ = boat_pose(cam, lt, rt, depth, r_)
                a = C.raster_mask(cam, world_of(boat, R_, s_, t_), ss=1) > 0.5
                sc.append((float((a & tgt).sum()) / max(1, float((a | tgt).sum())), r_))
            _, r_best = max(sc)
            prm = np.array([0.0, 0.0, 0.0, 0.0, float(r_best)])
            tip_l, tip_r = lt, rt
            roll = float(r_best)
        else:
            best = None
            for roll0 in (-20.0, 0.0, 20.0):
                x, v, _ = nelder_mead(loss, np.array([0.0, 0.0, 0.0, 0.0, roll0]), [10.0, 10.0, 3.0, 0.0, 8.0], iters=250)
                x, v, _ = nelder_mead(loss, x, [3.0, 3.0, 1.0, 0.0, 3.0], iters=150)
                if best is None or v < best[1]:
                    best = (x, v)
            prm, v = best
            roll = float(prm[4])
            tip_l, tip_r = tips(prm)
        t_, R_, s_, _, _ = boat_pose(cam, tip_l, tip_r, depth, roll)
        a_fit = C.raster_mask(cam, world_of(boat, R_, s_, t_), ss=1) > 0.5
        iou = float((a_fit & tgt).sum()) / max(1, float((a_fit | tgt).sum()))
        covered_clear = int((a_fit & clear).sum())
        t0_, R0_, s0_, _, _ = boat_pose(cam, lm["left_tip"], lm["right_tip"], depth, 0.0)
        a_lm = C.raster_mask(cam, world_of(boat, R0_, s0_, t0_), ss=1) > 0.5
        lm_iou = float((a_lm & tgt).sum()) / max(1, float((a_lm | tgt).sum()))
        t, R, s, Pb, Ps = boat_pose(cam, tip_l, tip_r, depth, roll)
        W_ = world_of(boat, R, s, t)
        cov_fit = C.raster_mask(cam, W_, ss=2)
        tips_px, _ = cam.project(np.stack([s * R @ TIP_PLUS_Z + t, s * R @ TIP_MINUS_Z + t]))
        hull = boat["Boat_Hull_OpenThick"]["V"] * s @ R.T + t
        low = hull[np.argmin(hull[:, 1])]
        draft = DRAFT_FRACTION * HULL_DEPTH_MID * s
        # M1 の配置で同じ IoU（比較）
        R1 = C.unity_euler_to_mat([mb["rotation"][k] for k in "xyz"])
        a1 = C.raster_mask(cam, world_of(boat, R1, mb["scale"], np.array([mb["position"][k] for k in "xyz"])), ss=1) > 0.5
        iou_m1 = float((a1 & tgt).sum()) / max(1, float((a1 | tgt).sum()))
        res["boats"][key] = {
            "m1_name": b["m1"], "role_ja": b["role_ja"], "backlog": b["backlog"],
            "depth_plane_m": round(depth, 4), "position": [round(float(v), 5) for v in t],
            "rotation_quat_xyzw": [round(float(v), 8) for v in C.mat_to_quat(R)],
            "scale": round(s, 6), "tip_to_tip_length_m": round(10.0 * s, 3),
            "roll_about_axis_deg": round(roll, 3), "iou_target": round(iou, 4), "iou_m1_revision01": round(iou_m1, 4),
            "iou_landmarks_only_roll0": round(lm_iou, 4),
            "covered_sky_or_fuji_px": covered_clear,
            "fit": b["fit"],
            "tips_used_px": [[round(float(v), 3) for v in tip_l], [round(float(v), 3) for v in tip_r]],
            "image_similarity_from_landmarks": {"dx_px": round(float(prm[0]), 3), "dy_px": round(float(prm[1]), 3),
                                                "rotation_deg": round(float(prm[2]), 3), "scale": round(math.exp(float(prm[3])), 4)},
            "tips_world": [[round(float(v), 4) for v in Pb], [round(float(v), 4) for v in Ps]],
            "tips_projected_px": [[round(float(v), 3) for v in p] for p in tips_px],
            "landmarks_px": [lm["left_tip"], lm["right_tip"]],
            "hull_lowest_point": [round(float(v), 4) for v in low], "draft_m": round(draft, 4),
            "support": b["support"],
            "m1": {"position": [mb["position"][k] for k in "xyz"], "euler": [mb["rotation"][k] for k in "xyz"], "scale": mb["scale"]},
        }
        c1 = cv2.findContours(tgt.astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        c2 = cv2.findContours((cov_fit > 0.5).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
        cv2.drawContours(vis, c1, -1, (255, 0, 255), 1)
        cv2.drawContours(vis, c2, -1, (0, 255, 0), 1)
        for p in (lm["left_tip"], lm["right_tip"]):
            cv2.drawMarker(vis, (int(round(p[0])), int(round(p[1]))), (255, 255, 0), cv2.MARKER_CROSS, 12, 1)
        print(key, "prm", np.round(prm, 3), "IoU", round(iou, 4), "(landmarks %.4f, M1 %.4f)" % (lm_iou, iou_m1), "len %.2f m" % (10 * s), "low", np.round(low, 3))

    # ---------------- 支え：船の竜骨の中央（blockout の根の原点 = 船体の底の長さ方向の中央）の真下で、支えの面が喫水の高さに来るようにする
    supports = {}
    for key, b in BOATS.items():
        r = res["boats"][key]
        keel = np.array(r["position"])
        want = keel[1] + r["draft_m"]  # 支えの面の高さ
        r["keel_mid_point"] = [round(float(v), 4) for v in keel]
        if b["support"] == "sea":
            supports[key] = {"object": "sea", "surface_y_before": SEA_TOP_Y, "want_surface_y": round(float(want), 4),
                             "note_ja": "平らな参照海面。海面は動かさず、竜骨の中央が海面より下（喫水）にあるかを確かめる。",
                             "keel_mid_below_surface_m": round(float(SEA_TOP_Y - keel[1]), 4)}
            continue
        tri = np.concatenate(slopes[b["support"]]["subs"], 0)
        y0 = surface_height(tri, np.array([[keel[0], keel[2]]]))[0]
        dy = float(want - y0)
        supports[key] = {"object": b["support"], "surface_y_before": round(float(y0), 4), "want_surface_y": round(float(want), 4),
                         "translate_y": round(dy, 4), "keel_mid_below_surface_m": round(float(r["draft_m"]), 4),
                         "note_ja": "M1 の斜面（revision_slopes.fbx）をこの量だけ鉛直に動かし、竜骨の中央の真上で面が喫水の高さに来るようにした。"}
        print(key, "support", b["support"], "surface y before %.3f want %.3f dy %.3f" % (y0, want, dy))
    res["supports"] = supports

    # ---------------- 座席（手前の船）
    fg = res["boats"]["boat_fg"]
    Rf = C.quat_to_mat(fg["rotation_quat_xyzw"])
    deck = np.concatenate(boat["Boat_Deck_Planks"]["subs"], 0).reshape(-1, 3) * fg["scale"] @ Rf.T + np.array(fg["position"])
    deck = deck.reshape(-1, 3, 3)
    probe = fg["scale"] * Rf @ SEAT_PROBE_LOCAL + np.array(fg["position"])
    # M1RevisionBuilder は世界の真下へ測ったが、船が傾くと外れるので、船の局所の下向き（−up）へ測る（傾きがなければ同じ）。
    hit = ray_hit(deck, probe, -Rf[:, 1])
    if hit is None:
        dv = deck.reshape(-1, 3)
        raise SystemExit("座席の甲板を測れない: probe %s deck min %s max %s" % (np.round(probe, 3), np.round(dv.min(0), 3), np.round(dv.max(0), 3)))
    eye = hit + np.array([0, EYE_ABOVE_DECK, 0])
    old_eye = np.array([M1["eyeWorld"][k] for k in "xyz"])
    res["seat"] = {"boat": "boat_fg（M1 foreground boat）", "rule_ja": "M1RevisionBuilder と同じく船の根の局所 (0,10,−2) から甲板（Boat_Deck_Planks）を測り、その 1.2 m 上（世界の上向き）。測る向きは世界の真下ではなく船の局所の下向き（船が傾いても甲板に当たるように。傾きがなければ同じ）。",
                   "probe_world": [round(float(v), 4) for v in probe], "deck_hit": [round(float(v), 4) for v in hit],
                   "eye_world": [round(float(v), 4) for v in eye], "eye_world_m1_revision01": [round(float(v), 4) for v in old_eye],
                   "eye_moved_m": round(float(np.linalg.norm(eye - old_eye)), 4),
                   "eye_delta": [round(float(v), 4) for v in (eye - old_eye)],
                   "target": [-7, 5, 3], "fov_deg": 80}
    print("seat eye", np.round(eye, 3), "old", np.round(old_eye, 3), "moved %.3f m" % np.linalg.norm(eye - old_eye))

    # ---------------- 富士
    fuji = group_tris("fuji_blockout")
    F = __import__("evaluate").Truth().fam["sky_claws"]
    tr_pts = F["pts"][F["sel"]["fuji_ridge"]]

    def fuji_world(prm):
        dx, sx, sy = prm
        return world_of(fuji, np.eye(3), None, np.array(FUJI_M1["position"]) + [dx, 0, 0], S=np.array([sx, sy, sx]))

    def fuji_loss(prm):
        cv = C.raster_mask(cam, fuji_world(prm), ss=2)
        rp = T.boundary_points(cv, spec, fm)
        zone = T.point_in_poly(rp, reg["polygons_display"]["fuji_zone"], 0.0)
        rp = rp[zone & (rp[:, 1] < 772)]
        if len(rp) < 10:
            return 1e3
        d1, _ = T.nearest(tr_pts, rp)
        d2, _ = T.nearest(rp, tr_pts)
        return float(np.mean(d1) + np.mean(d2)) + 0.25 * float(max(d1.max(), d2.max()))
    fb, fv, fit_it = nelder_mead(fuji_loss, np.array([0.0, 2.0, 2.0]), [3.0, 0.1, 0.1], iters=300)
    cov_f = C.raster_mask(cam, fuji_world(fb), ss=2)
    c2 = cv2.findContours((cov_f > 0.5).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)[0]
    cv2.drawContours(vis, c2, -1, (0, 255, 0), 1)
    for q in tr_pts:
        vis[int(round(q[1])), int(round(q[0]))] = (255, 0, 255)
    res["fuji"] = {"position": [round(float(v), 5) for v in (np.array(FUJI_M1["position"]) + [fb[0], 0, 0])],
                   "scale": [round(float(fb[1]), 5), round(float(fb[2]), 5), round(float(fb[1]), 5)],
                   "depth_plane_m": round(float(cam.depth(np.array(FUJI_M1["position"]) + [fb[0], 0, 0])), 3),
                   "loss_mean_plus_quarter_max_px": round(float(fv), 4), "iterations": int(fit_it), "m1": FUJI_M1,
                   "height_m": round(float(8 * fb[2]), 3), "base_width_m": round(float(24 * fb[1]), 3)}
    print("fuji", res["fuji"])

    # ---------------- 仮置きの配色（M1 の材質名 → 調色板）
    lab_d = tr_lab = T.srgb8_to_lab(disp)
    sky = T.load_cov_png(os.path.join(T.TARGET_DIR, "masks", "sky_claws_cov.png")) > 0.5
    boats_mask = np.zeros_like(sky)
    for key in BOATS:
        boats_mask |= T.load_cov_png(os.path.join(T.TARGET_DIR, "masks", key + "_cov.png")) > 0.5
    pl = np.array([palette[k]["lab"] for k in PALETTE_KEYS_WATER])
    dist = np.stack([T.ciede2000(lab_d, pl[i][None, None, :]) for i in range(len(pl))], -1)
    cls = np.argmin(dist, -1)
    scored = np.zeros_like(sky)
    scored[:, fm.x0:fm.x1 + 1] = True
    usable = ~sky & ~boats_mask & scored
    foam = group_tris("foam_static")
    placeholder_parts = {"M1_ForegroundSwell_Static": foam["M1_ForegroundSwell_Static"], "M1_ForegroundFoam_Static": foam["M1_ForegroundFoam_Static"],
                         "M1_Revision_RightSlope": slopes["M1_Revision_RightSlope"], "M1_Revision_LeftSupport": slopes["M1_Revision_LeftSupport"]}
    colours = {}
    for name, part in placeholder_parts.items():
        dy = 0.0
        for key, sp in supports.items():
            if sp["object"] == name:
                dy = sp["translate_y"]
        mats = []
        for si, (tri, mat) in enumerate(zip(part["subs"], part["materials"])):
            w = tri.reshape(-1, 3) + [0, dy, 0]
            mk = C.raster_mask(cam, w.reshape(-1, 3, 3), ss=1) > 0.5
            u = mk & usable
            hist = np.bincount(cls[u], minlength=len(pl)) if u.any() else np.zeros(len(pl), int)
            if "Indigo" in mat or "DeepBlue" in mat:
                pk, rule = "ai_dark", "藍・濃い青 → 藍濃"
            elif "FoamCream" in mat:
                pk, rule = "white", "白泡 → 白"
            elif hist.sum() > 0:
                pk, rule = PALETTE_KEYS_WATER[int(np.argmax(hist))], "青 → 原画でこの面の下に最も多い水の色"
            else:
                pk, rule = "ai_mid", "青 → 藍中（原画の範囲外）"
            mats.append({"submesh": si, "m1_material": mat, "palette": pk, "srgb8": palette[pk]["srgb8"], "rule_ja": rule,
                         "painting_class_pixels": {PALETTE_KEYS_WATER[i]: int(hist[i]) for i in range(len(pl))}})
        colours[name] = {"translate_y": dy, "materials": mats}
        print("placeholder", name, [(m["m1_material"], m["palette"]) for m in mats])
    res["placeholders"] = colours
    res["hidden_m1_parts_ja"] = "M1_Foam_FrontRibbon と M1_Foam_Claw_*（旧い主役波の白帯と爪）は、番号24 と同じく置かない。"
    T.imwrite(os.path.join(OUT, "place_fit.png"), vis)
    C.save_json(os.path.join(OUT, "place_fit.json"), res)
    write_layout(res, palette, spec)
    return res


def write_layout(res, palette, spec):
    sky = C.load_json(C.SKY_JSON)
    pal = {k: {"srgb8": v["srgb8"], "lab": v["lab"], "name_ja": v["name_ja"]} for k, v in palette.items()}
    boats = {}
    for k, r in res["boats"].items():
        boats[k] = {"m1_name": r["m1_name"], "role_ja": r["role_ja"], "position": r["position"], "rotation_quat_xyzw": r["rotation_quat_xyzw"],
                    "scale": r["scale"], "materials": {"GW_Boat_Wood": "boat_ochre", "GW_Boat_Plank": "boat_ochre", "GW_Boat_Edge": "ai_dark"}}
    L = {
        "schema": "GreatWave.AF27.context_layout/1",
        "number": "27",
        "truth_version": spec["version"],
        "note_ja": "番号27 の配置。Unity の AF27ContextScene.BuildAndRender がこのファイルからシーン・プレハブ・マテリアルを作る。"
                   "位置は Unity の世界座標（m）、回転は Unity の Quaternion の成分 (x, y, z, w)。",
        "palette": pal,
        "boats": boats,
        "fuji": {"position": res["fuji"]["position"], "scale": res["fuji"]["scale"],
                 "materials": {"GW_Fuji_Snow": "fuji_snow", "GW_Fuji_Blue": "fuji_slope"}},
        "sea": {"position": [0, -0.32, 100], "scale": [1000, 0.5, 1000], "palette": "ai_dark",
                "note_ja": "M1 の平らな参照海面と同じ寸法。色は番号24 と同じ藍濃。"},
        "placeholders": {k: {"translate_y": v["translate_y"], "materials": [{"m1_material": m["m1_material"], "palette": m["palette"]} for m in v["materials"]]}
                         for k, v in res["placeholders"].items()},
        "seat": res["seat"],
        "sky_dome": {"json": "Tools/GWContext/sky_dome.json", "radius_m": 800.0, "sha256": C.sha256(C.SKY_JSON), "theta0_deg": sky["theta0_deg"]},
    }
    # Unity の JsonUtility が読める形（辞書と入れ子の配列を使わない）
    U = {"palette": [{"key": k, "srgb8": v["srgb8"]} for k, v in palette.items()],
         "boats": [{"key": k, "m1Name": v["m1_name"], "position": v["position"], "rotation": v["rotation_quat_xyzw"], "scale": v["scale"],
                    "materials": [{"m1Material": a, "palette": b} for a, b in v["materials"].items()]} for k, v in boats.items()],
         "fuji": {"position": L["fuji"]["position"], "scale": L["fuji"]["scale"],
                  "materials": [{"m1Material": a, "palette": b} for a, b in L["fuji"]["materials"].items()]},
         "sea": {"position": L["sea"]["position"], "scale": L["sea"]["scale"], "palette": L["sea"]["palette"]},
         "placeholders": [{"name": k, "translateY": v["translate_y"],
                           "materials": [{"m1Material": m["m1_material"], "palette": m["palette"]} for m in v["materials"]]}
                          for k, v in L["placeholders"].items()],
         "seat": {"boatKey": "boat_fg", "eyeNumpy": res["seat"]["eye_world"], "target": [-7.0, 5.0, 3.0], "fov": 80.0,
                  "probeLocal": SEAT_PROBE_LOCAL.tolist(), "eyeAboveDeck": EYE_ABOVE_DECK},
         "sky": {"radius": 800.0, "theta0": sky["theta0_deg"], "wFull": sky["w_full_deg"], "wZero": sky["w_zero_deg"],
                 "thetaAz0": sky["theta_t"]["az0"], "thetaStep": sky["theta_t"]["step"], "thetaT": sky["theta_t"]["values_deg"],
                 "gradE0": sky["gradient"]["e0"], "gradStep": sky["gradient"]["step"],
                 "gradientRGB": [float(v) for c in sky["gradient"]["linear_rgb"] for v in c]}}
    L["unity"] = U
    C.save_json(C.LAYOUT_JSON, L)


if __name__ == "__main__":
    import sys
    if "--layout-only" in sys.argv:
        # 当てはめ（place_fit.json）をそのまま使い、context_layout.json だけを書き直す
        write_layout(C.load_json(os.path.join(OUT, "place_fit.json")), C.load_json(os.path.join(T.TARGET_DIR, "palette.json"))["palette"], T.load_spec())
    else:
        main()
