# -*- coding: utf-8 -*-
"""番号29（爪の一覧）草稿：Met 原画だけから爪の一覧を作る。

手順（作業計画 4.2 の 29）：
  1. 白の領域のマスク（番号23 真値 v0.2 と同じ手順の空マスクと、番号23 の 5 色の Lloyd 中心による色分け。船の黄土は除く）
  2. numpy で自作した Zhang–Suen の骨格化（af29_skeleton.py。余分な画素は単純点だけ逐次に除き、8連結で最小の骨格にする）
  3. 枝の分割（とげの除去 → 枝をストロークにまとめる → 先端を持つストローク = 爪。残りの枝は根元の白 web として爪に付ける）
  4. agent が重ね図を見て修正（af29_params.json の corrections）
範囲は 2 つ：主浪の波頭の泡（列 = 上側・途中・船側）と、右側の波の白の縁（列 = 右側）。
各爪について、番号、所属する列、根元と先端の座標、根元と中央の幅、先端の方向、遮蔽の順序（仮）、隣との隙間、
輪郭の多角形、中心線、4〜6 の関節、節の長さ比、曲がり角を記録する。代表10形と船側中央の爪の候補を選ぶ。

参照モデル（Q5、wave_repair_zbrush2.obj）は読まない。numpy・OpenCV・PIL だけを使う。

使い方：
  py -3.10 Tools/PaintingTruth/claws29/af29_claw_inventory.py [--evidence Docs/Evidence/ArtFirst/29]
"""
import argparse
import datetime
import json
import math
import os
import platform
import sys
import time

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # Tools/PaintingTruth
import truthlib as T  # noqa: E402
import af29_skeleton as SK  # noqa: E402

VERSION = "draft1"
PARAMS_PATH = os.path.join(HERE, "af29_params.json")
OUT_JSON = os.path.join(HERE, "claw_inventory_draft.json")
ENVELOPE_JSON = os.path.join(T.TARGET_DIR, "main_wave_outline_envelope.json")
PALETTE_JSON = os.path.join(T.TARGET_DIR, "palette.json")
SKY_COV_PNG = os.path.join(T.TARGET_DIR, "masks", "sky_claws_cov.png")

ROW_COLOURS = {  # RGB
    "上側": (255, 170, 0),
    "途中": (0, 200, 90),
    "船側": (255, 40, 40),
    "右側": (230, 60, 230),
}
MAIN_ROWS = ("上側", "途中", "船側")
CLASS_NAMES = ["white", "mizuiro", "mix", "ai_mid", "ai_dark"]


# ---------------------------------------------------------------- 小道具
def rnd(v, k=2):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    return round(float(v), k)


def cumlen(P):
    P = np.asarray(P, np.float64)
    if len(P) < 2:
        return np.zeros(len(P))
    d = np.hypot(*np.diff(P, axis=0).T)
    return np.concatenate([[0.0], np.cumsum(d)])


def resample(P, step):
    """折れ線 P（x,y）を弧長 step ごとに線形補間で取り直す（端点を含む）。"""
    P = np.asarray(P, np.float64)
    L = cumlen(P)
    if L[-1] <= 1e-9:
        return P[:1].copy(), np.array([0.0])
    n = max(2, int(math.ceil(L[-1] / step)) + 1)
    t = np.linspace(0.0, L[-1], n)
    return np.stack([np.interp(t, L, P[:, 0]), np.interp(t, L, P[:, 1])], -1), t


def smooth_path(P, win=5):
    """画素の階段を消すための移動平均（端は短い窓）。"""
    P = np.asarray(P, np.float64)
    if len(P) < 3:
        return P.copy()
    out = np.empty_like(P)
    h = win // 2
    for i in range(len(P)):
        a, b = max(0, i - h), min(len(P), i + h + 1)
        out[i] = P[a:b].mean(0)
    out[0], out[-1] = P[0], P[-1]
    return out


def bilinear(img, pts):
    pts = np.asarray(pts, np.float32)
    return cv2.remap(np.asarray(img, np.float32), pts[:, 0].reshape(1, -1), pts[:, 1].reshape(1, -1),
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE).ravel()


def compass_ja(deg):
    names = ["右", "右下", "下", "左下", "左", "左上", "上", "右上"]
    return names[int(((deg % 360) + 22.5) // 45) % 8]


def joints_of(C, jmin, jmax, tol):
    """中心線 C（根元→先端）に、最遠点の挿入で関節を置く。根元と先端を含め jmin〜jmax 点。
    挿入後の最大のずれが tol 以下になる最小の点数（ただし jmin 以上）を採る。"""
    C = np.asarray(C, np.float64)
    idx = [0, len(C) - 1]

    def dev(ids):
        best, bi = -1.0, None
        for a, b in zip(ids[:-1], ids[1:]):
            if b - a < 2:
                continue
            A, B = C[a], C[b]
            AB = B - A
            n = np.hypot(*AB)
            seg = C[a + 1:b]
            if n < 1e-9:
                d = np.hypot(*(seg - A).T)
            else:
                d = np.abs(AB[0] * (seg[:, 1] - A[1]) - AB[1] * (seg[:, 0] - A[0])) / n
            k = int(np.argmax(d))
            if d[k] > best:
                best, bi = float(d[k]), a + 1 + k
        return best, bi
    while len(idx) < jmax:
        best, bi = dev(idx)
        if bi is None:
            break
        if len(idx) >= jmin and best <= tol:
            break
        idx = sorted(idx + [bi])
    best, _ = dev(idx)
    return idx, max(best, 0.0)


def turning_deg(P):
    """関節の折れ線 P の内側の関節での曲がり角（度）。画面座標（y 下）で時計回りを正。"""
    P = np.asarray(P, np.float64)
    out = []
    for i in range(1, len(P) - 1):
        u, v = P[i] - P[i - 1], P[i + 1] - P[i]
        cr = u[0] * v[1] - u[1] * v[0]
        dt = u[0] * v[0] + u[1] * v[1]
        out.append(math.degrees(math.atan2(cr, dt)))
    return out


def sweep(canvas, Cr, wid, offset=(0.0, 0.0)):
    """中心線 Cr（x,y）の各標本に直径＝幅の円を置き、隣の標本を同じ太さの線でつないで canvas に 1 を塗る。"""
    Cr = np.asarray(Cr, np.float64) - np.asarray(offset, np.float64)
    for i in range(len(Cr)):
        r = max(0.5, wid[i] / 2.0)
        cv2.circle(canvas, (int(round(Cr[i][0])), int(round(Cr[i][1]))), int(round(r)), 1, -1)
        if i + 1 < len(Cr):
            r2 = max(0.5, 0.5 * (wid[i] + wid[i + 1]) / 2.0)
            cv2.line(canvas, tuple(int(round(v)) for v in Cr[i]), tuple(int(round(v)) for v in Cr[i + 1]), 1, max(1, int(round(2 * r2))))


def runs_of(flags):
    """真の連続区間の (始め, 終わり＋1) の並び。"""
    out, s = [], None
    for i, f in enumerate(flags):
        if f and s is None:
            s = i
        elif not f and s is not None:
            out.append((s, i))
            s = None
    if s is not None:
        out.append((s, len(flags)))
    return out


# ---------------------------------------------------------------- 範囲ごとの抽出
def process_zone(zd, prm, ref_rgb, lab_ref, sky_ref, ochre_ref, centres):
    """1 つの範囲（主浪の波頭 / 右側の波）で、白のマスク → 骨格 → ストローク → 爪の候補 → 根元の白（web）を作る。
    爪の画素座標は範囲の切り出し（crop）座標で持ち、off を足すと原画の座標になる。"""
    cw = prm["claw"]
    corr = prm["corrections"]
    zone_full = T.poly_mask(sky_ref.shape, zd["points"])
    ys, xs = np.nonzero(zone_full)
    pad = int(zd["body_open_radius_ref_px"]) + 16  # 白の塊（body）を範囲の外の白も含めて決めるための余白
    X0, Y0 = max(0, xs.min() - pad), max(0, ys.min() - pad)
    X1, Y1 = min(sky_ref.shape[1], xs.max() + pad + 1), min(sky_ref.shape[0], ys.max() + pad + 1)
    crop = (slice(Y0, Y1), slice(X0, X1))
    off = np.array([X0, Y0], np.float64)
    zone = zone_full[crop]
    sky = sky_ref[crop]
    lab = lab_ref[crop]
    och = ochre_ref[crop]
    rdil = int(prm["colour"].get("exclude_ochre_dilate_ref_px", 0))
    if rdil > 0:
        och = cv2.dilate(och.astype(np.uint8), T.disk(rdil)).astype(bool)
    sg = float(prm["colour"]["blur_sigma_ref_px"])
    labs = np.stack([cv2.GaussianBlur(lab[..., i], (0, 0), sg) for i in range(3)], -1)
    d2 = ((labs[:, :, None, :] - centres[None, None]) ** 2).sum(-1)
    cls = np.argmin(d2, -1).astype(np.uint8)
    mcls = zd.get("mask_classes", [prm["colour"]["white_class"]])
    white_ext = np.isin(cls, [CLASS_NAMES.index(k) for k in mcls]) & ~sky & ~och  # 範囲で切る前の白
    seeds = zd.get("exclude_component_seeds_ref", [])
    if seeds:
        # 範囲に入った別の波の面（手前の波の白い帯など）は、種の点を含む連結成分ごと除く
        n_, lab_s = cv2.connectedComponents((white_ext & zone).astype(np.uint8), connectivity=8)
        n_e, lab_e = cv2.connectedComponents(white_ext.astype(np.uint8), connectivity=8)
        for sx, sy in seeds:
            qx, qy = int(round(sx - X0)), int(round(sy - Y0))
            if 0 <= qy < lab_s.shape[0] and 0 <= qx < lab_s.shape[1] and lab_s[qy, qx] > 0:
                white_ext &= ~((lab_s == lab_s[qy, qx]) | ((lab_e == lab_e[qy, qx]) & ~zone))
    white_raw = white_ext & zone

    # ---- 白のマスクの掃除
    cp = prm["clean"]
    n, lab_cc, st, _ = cv2.connectedComponentsWithStats(white_raw.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= int(cp["min_component_ref_px"])
    W = keep[lab_cc]
    n, lab_cc, st, _ = cv2.connectedComponentsWithStats((~W).astype(np.uint8), connectivity=4)
    small = np.zeros(n, bool)
    small[1:] = st[1:, 4] < int(cp["fill_hole_below_ref_px"])
    W |= small[lab_cc] & zone
    if cp.get("open_3x3", True):
        W = cv2.morphologyEx(W.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab_cc, st, _ = cv2.connectedComponentsWithStats(W.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= int(cp["min_component_ref_px"])
    W = keep[lab_cc]
    DT = cv2.distanceTransform(W.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    # 白の塊（波頭の平らな白）：範囲で切る前の白を開き、範囲の中の白と重ねる（範囲の縁で白が細く切られても塊と判定できる）
    body = cv2.morphologyEx(white_ext.astype(np.uint8), cv2.MORPH_OPEN, T.disk(int(zd["body_open_radius_ref_px"]))).astype(bool) & W
    body_touch = cv2.dilate(body.astype(np.uint8), T.disk(int(cw["body_touch_dilate_ref_px"]))).astype(bool)
    indigo = (cls == CLASS_NAMES.index("ai_mid")) | (cls == CLASS_NAMES.index("ai_dark"))
    sky_dist = cv2.distanceTransform((~sky).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    zone_in = zone & (np.arange(zone.shape[1])[None, :] + X0 < sky_ref.shape[1] - 1)  # 画像の右端も範囲の縁として扱う
    zone_dist = cv2.distanceTransform(np.pad(zone_in.astype(np.uint8), 1), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)[1:-1, 1:-1]

    # ---- 骨格化、余分な画素の除去（8連結で最小の骨格）、とげの除去
    t0 = time.time()
    S0, n_iter = SK.zhang_suen(W)
    t_zs = time.time() - t0
    S0, nthin = SK.thin_final(S0)
    pr = prm["prune"]
    t0 = time.time()
    S, pruned = SK.prune_spurs(S0, DT, float(pr["ratio_to_halfwidth"]), float(pr["min_protrusion_ref_px"]), int(pr["rounds"]))
    t_pr = time.time() - t0
    edges, jl, nj = SK.build_graph(S)
    E0, _, _ = SK.build_graph(S0)
    stats = {
        "zhang_suen_iterations": int(n_iter),
        "zhang_suen_s": round(t_zs, 2),
        "thin_final_removed_px": int(nthin),
        "skeleton_px_before_prune": int(S0.sum()),
        "skeleton_px_after_prune": int(S.sum()),
        "edges_before_prune": len(E0),
        "terminal_edges_before_prune": int(sum(1 for e in E0 if (e["end0"] or e["end1"]) and (e["j0"] or e["j1"]))),
        "spurs_removed_per_round": pruned,
        "prune_s": round(t_pr, 2),
        "edges_after_prune": len(edges),
        "junction_clusters_after_prune": int(nj - 1),
        "topology_white_vs_skeleton_before_prune": SK.topology_check(W, S0),
        "topology_white_vs_skeleton_after_prune": SK.topology_check(W, S),
        "white_ref_px": int(W.sum()),
        "body_ref_px": int((W & body).sum()),
    }

    # ---- 爪の候補：枝をなめらかに続くストロークにまとめ、端点（先端）を持つストロークを爪とする
    stp = prm["stroke"]
    strk, _pairs = SK.strokes(edges, float(stp["max_deflect_deg"]), float(stp["probe_ref_px"]), DT, float(stp["max_width_ratio"]))
    stats["strokes_total"] = len(strk)
    stats["strokes_with_endpoint"] = int(sum(1 for st_ in strk if any(e_[0] == "end" for e_ in st_["ends"])))
    stats["strokes_junction_both_ends"] = int(sum(1 for st_ in strk if st_["ends"][0][0] == "junction" and st_["ends"][1][0] == "junction"))
    cands = []
    for st_ in strk:
        k0, k1 = st_["ends"][0][0], st_["ends"][1][0]
        if "end" not in (k0, k1):
            continue
        p, brk = SK.stroke_path(edges, st_["parts"], return_breaks=True)
        if len(p) < 2:
            continue
        if k0 == "end" and k1 == "end":
            # 両端とも端点（線で切り離された白など）：細い方を先端にする。同じなら空に近い方
            n_ = min(10, len(p))
            w0 = float(DT[p[:n_, 0], p[:n_, 1]].mean())
            w1 = float(DT[p[-n_:, 0], p[-n_:, 1]].mean())
            d0, d1 = sky_dist[p[0][0], p[0][1]], sky_dist[p[-1][0], p[-1][1]]
            if w0 < w1 or (w0 == w1 and d0 < d1):
                p = p[::-1]
                brk = [len(p) - b for b in brk]
            rj, kind, root_end = 0.0, "stroke_free", "end"
        elif k0 == "end":
            p = p[::-1]
            brk = [len(p) - b for b in brk]
            rj = SK.junction_radius(DT, jl, st_["ends"][1][1]) if k1 == "junction" else 0.0
            kind, root_end = "stroke", k1
        else:
            rj = SK.junction_radius(DT, jl, st_["ends"][0][1]) if k0 == "junction" else 0.0
            kind, root_end = "stroke", k0
        # 長すぎるストロークは、先端から max_length 以内で最も遠い分岐の継ぎ目で切る（そこを根元側の分岐とする）
        n_parts = len(st_["parts"])
        Lp = cumlen(p[:, ::-1].astype(np.float64))
        maxL = float(stp["max_length_ref_px"])
        cut = False
        if Lp[-1] > maxL and brk:
            ok = sorted(b for b in brk if Lp[-1] - Lp[b] <= maxL)
            if ok:
                b0 = ok[0]
                n_parts = sum(1 for b in brk if b >= b0) + 1
                p = p[b0:]
                rj = float(DT[p[0][0], p[0][1]])
                root_end, cut = "junction", True
        cands.append({"pix": p, "rj": rj, "kind": kind, "root_end": root_end, "n_edges": n_parts, "cut_by_length": cut})

    for add in corr.get("add_claws_ref", []):
        P = np.asarray(add["points"], np.float64)
        if not T.point_in_poly(P[-1:], zd["points"])[0]:
            continue
        C, _ = resample(P - off, 1.0)
        pix = np.clip(np.round(C[:, ::-1]).astype(np.int32), 0, [W.shape[0] - 1, W.shape[1] - 1])
        cands.append({"pix": pix, "rj": 0.0, "kind": "manual", "reason": add.get("reason", "")})

    claws = []
    excluded = []
    for c in cands:
        pix = c["pix"]
        P = pix[:, ::-1].astype(np.float64)  # (x, y) crop 座標
        Ls = cumlen(P)
        n_p = len(P)
        # 根元：先端から分岐側へたどり、白の塊に入る点と、分岐の内接円の縁のうち先端に近い方
        i_rj = int(np.searchsorted(Ls, c["rj"])) if c["rj"] > 0 else 0
        inside = body_touch[pix[:, 0], pix[:, 1]]
        i_body = 0
        for i in range(n_p - 1, -1, -1):
            if inside[i]:
                i_body = i
                break
        i_root = min(max(i_rj, i_body), n_p - 2) if n_p >= 2 else 0
        # 幅の跳び：先端側の半分の半幅の中央値の jump 倍を超える所（厚い白へ入る所）より根元側は爪に含めない
        i_jump = 0
        if c["kind"] != "manual" and n_p - i_root >= 6:
            hwp = DT[pix[:, 0], pix[:, 1]]
            Lt = Ls[-1] - Ls  # 先端からの弧長
            span = Lt[i_root]
            distal = hwp[i_root:][Lt[i_root:] <= 0.5 * span]
            ref_hw = max(float(np.median(distal)) if len(distal) else 1.0, float(cw["width_jump_floor_ref_px"]))
            over = np.flatnonzero(hwp[i_root:] > float(cw["width_jump_ratio"]) * ref_hw)
            if len(over):
                i_jump = i_root + int(over[-1]) + 1
                i_root = min(max(i_root, i_jump), n_p - 2)
        # 目視の修正：根元の付け替え（先端が一致する爪の根元を、指定点に最も近い中心線上の点にする）
        trimmed = ""
        for tx_, ty_, rx_, ry_, rr_, why in corr.get("trim_root_ref", []):
            tip0 = P[-1] + off
            if math.hypot(tip0[0] - tx_, tip0[1] - ty_) <= rr_:
                dd = np.hypot(P[:, 0] + off[0] - rx_, P[:, 1] + off[1] - ry_)
                i_root = min(int(np.argmin(dd)), n_p - 2)
                trimmed = why
        C = smooth_path(P[i_root:], 5)
        if len(C) < 2:
            continue
        stem = smooth_path(P[:i_root + 1], 5) if i_root >= 1 else P[:1].copy()
        length = float(cumlen(C)[-1])
        tip_abs = C[-1] + off
        rec = {"C": C, "full": P, "pix": pix, "finger": P[i_root:], "stem": stem, "i_root": i_root, "kind": c["kind"], "length": length,
               "rj": c["rj"], "reason": c.get("reason", ""), "root_end": c.get("root_end", ""), "n_edges": c.get("n_edges", 1),
               "root_in_body": bool(i_body > 0 and i_body >= i_rj), "cut_by_length": bool(c.get("cut_by_length", False)),
               "root_by_width_jump": bool(i_jump > 0 and i_jump >= max(i_rj, i_body) and not trimmed), "trimmed": trimmed,
               "zone": zd["id"], "off": off}
        drop = None
        tpx = np.clip(np.round(C[-1]).astype(int), 0, [zone.shape[1] - 1, zone.shape[0] - 1])
        if c["kind"] != "manual" and zone_dist[tpx[1], tpx[0]] <= float(cw["zone_edge_margin_ref_px"]):
            drop = "範囲の縁で切った白の角（範囲の境界か画像の端から %.0f px 以内の先端）" % float(cw["zone_edge_margin_ref_px"])
        for xt, yt, rr, why in corr.get("exclude_tips_ref", []):
            if math.hypot(tip_abs[0] - xt, tip_abs[1] - yt) <= rr:
                drop = "目視で除外：" + why
        if drop is None and c["kind"] != "manual" and length < float(cw["min_length_ref_px"]):
            drop = "短い（%.1f px < %.1f px）" % (length, float(cw["min_length_ref_px"]))
        if drop is None and c["kind"] != "manual" and len(C) >= 2:
            mw = 2.0 * float(np.median(DT[np.clip(np.round(C[:, 1]).astype(int), 0, DT.shape[0] - 1),
                                          np.clip(np.round(C[:, 0]).astype(int), 0, DT.shape[1] - 1)]))
            if length < float(cw.get("min_length_over_mid_width", 0.0)) * mw:
                drop = "指の形のない白の塊（長さ %.1f px < %.1f × 幅の中央値 %.1f px）" % (length, float(cw["min_length_over_mid_width"]), mw)
        if drop:
            excluded.append({"zone": zd["id"], "tip_ref": rnd(tip_abs, 1), "length_ref_px": rnd(length, 1), "kind": c["kind"], "reason_ja": drop})
            continue
        claws.append(rec)

    # ---- 根元の白（web）：どの爪のストロークにも半分以上含まれない枝の、白の塊の外の部分を最も近い爪に付ける
    H, Wd = W.shape
    used = np.zeros((H, Wd), bool)
    lab_img = np.zeros((H, Wd), np.int32)
    for i, c in enumerate(claws):
        pp = np.clip(c["pix"], 0, [H - 1, Wd - 1])
        used[pp[:, 0], pp[:, 1]] = True
        lab_img[pp[:, 0], pp[:, 1]] = i + 1
    webs = []
    if claws:
        _, lbl = cv2.distanceTransformWithLabels((lab_img == 0).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        zy, zx = np.nonzero(lab_img > 0)
        lut = np.zeros(int(lbl.max()) + 1, np.int32)
        lut[lbl[zy, zx]] = lab_img[zy, zx]
        step = float(cw["centerline_step_ref_px"])
        for e in edges:
            p = e["path"]
            if used[p[:, 0], p[:, 1]].mean() >= float(cw["web_used_fraction"]):
                continue
            outside = ~body[p[:, 0], p[:, 1]] & ~used[p[:, 0], p[:, 1]]
            for a, b in runs_of(outside):
                if b - a < int(cw["web_min_px"]):
                    continue
                Q = p[a:b][:, ::-1].astype(np.float64)
                Cw = smooth_path(Q, 5)
                Cr, _ = resample(Cw, step) if cumlen(Cw)[-1] > 1e-6 else (Cw[:1], None)
                wid = 2.0 * bilinear(DT, Cr)
                cand = []
                for q in (p[a], p[b - 1]):
                    ci = int(lut[lbl[q[0], q[1]]]) - 1
                    if ci >= 0:
                        dq = float(np.min(np.hypot(claws[ci]["pix"][:, 0] - q[0], claws[ci]["pix"][:, 1] - q[1])))
                        cand.append((dq, ci))
                if not cand:
                    continue
                dq, ci = min(cand)
                webs.append({"Cr": Cr, "wid": wid, "claw": ci, "length": float(cumlen(Cr)[-1]), "dist_to_claw": dq})
    # 波頭の平らな白（body）の外周（記録。白の全体に対する IoU の記録に使う）
    body_polys = []
    cnts, _ = cv2.findContours((body & W).astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    for cn in cnts:
        if cv2.contourArea(cn) < 50:
            continue
        ap_ = cv2.approxPolyDP(cn, 2.0, True).reshape(-1, 2).astype(np.float64) + off
        body_polys.append(ap_)
    stats["claws"] = len(claws)
    stats["excluded"] = len(excluded)
    stats["webs"] = len(webs)
    return {"zd": zd, "crop": crop, "off": off, "zone": zone, "W": W, "DT": DT, "body": body, "indigo": indigo, "sky_dist": sky_dist,
            "S0": S0, "S": S, "claws": claws, "excluded": excluded, "webs": webs, "stats": stats, "body_polys": body_polys}


# ---------------------------------------------------------------- 主処理
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="Docs/Evidence/ArtFirst/29")
    args = ap.parse_args()
    t_start = time.time()
    spec = T.load_spec()  # 原画の SHA-256 を凍結値と照合する
    man = T.load_manual()
    prm = T.load_json(PARAMS_PATH)
    fmap = T.FrameMap(spec)
    ex = spec["extraction"]
    polys = man["polygons_ref"]
    ev_dir = T.repo_abs(args.evidence)
    os.makedirs(ev_dir, exist_ok=True)
    timings = {}

    # ---- 1. 原画、空マスク（真値 v0.2 と同じ手順）、船の黄土
    ref_rgb = T.imread_rgb(T.repo_abs(spec["reference"]["path"]))
    lab_ref = T.srgb8_to_lab(ref_rgb).astype(np.float32)
    fills = [polys["sky_fill_cartouche"]["points"], polys["sky_fill_signature"]["points"]]
    barriers = list(man.get("barriers_ref", {}).values())
    sky_ref = T.segment_sky(lab_ref, ex["sky"], fills, barriers)
    # 番号23 の保存済みの空（表示フレームの被覆率）と一致するかを確かめる（真値と同じ空を使っている確認）
    q16 = lambda c: np.round(np.clip(c, 0.0, 1.0) * 65535.0) / 65535.0  # noqa: E731
    sky_cov_now = q16(T.ref_mask_to_cov(sky_ref, fmap))
    sky_cov_saved = T.load_cov_png(SKY_COV_PNG)
    sky_check = float(np.abs(sky_cov_now - sky_cov_saved).max())
    ochre_ref = T.ochre_mask(lab_ref, sky_ref, ex["ochre"])
    timings["sky_s"] = round(time.time() - t_start, 2)
    pal = T.load_json(PALETTE_JSON)
    centres = np.array([pal["classes_lloyd_centers_lab"][k] for k in CLASS_NAMES], np.float32)

    # ---- 2〜4. 範囲ごとに骨格化・分割・修正
    Z = {}
    for zd in prm["zones"]:
        Z[zd["id"]] = process_zone(zd, prm, ref_rgb, lab_ref, sky_ref, ochre_ref, centres)
    timings["zones_s"] = round(time.time() - t_start - timings["sky_s"], 2)
    cw = prm["claw"]

    # ---- 基準曲線（包絡版の 131 → 132 → 72。s = 0 は 132 の始点＝波頂）
    env = T.load_json(ENVELOPE_JSON)
    segs = {s["id"]: np.asarray(s["points_ref"], np.float64) for s in env["segments"]}
    ref_curve = np.concatenate([segs["131"], segs["132"][1:], segs["72"][1:]], 0)
    ref_s = cumlen(ref_curve)
    ref_s = ref_s - ref_s[len(segs["131"]) - 1]
    rows_p = prm["rows"]
    br = rows_p["breaks_s"]
    s_max = float(rows_p.get("curve_s_max", 1e9))
    x_split = float(rows_p.get("left_split_x_ref", -1e9))
    sel_curve = ref_s <= s_max

    def s_of(pt):
        d = np.hypot(ref_curve[:, 0] - pt[0], ref_curve[:, 1] - pt[1])
        d = np.where(sel_curve, d, np.inf)
        k = int(np.argmin(d))
        return float(ref_s[k]), float(d[k])

    def row_of(zone_rows, s, tip):
        if zone_rows != "main":
            return zone_rows
        if tip[0] < x_split:
            return "上側"
        if s < br["上側|途中"]:
            return "上側"
        if s < br["途中|船側"]:
            return "途中"
        return "船側"

    # ---- 各爪の計測
    claws = []
    step = float(cw["centerline_step_ref_px"])
    rad_ind = int(cw["indigo_side_radius_ref_px"])
    disk_ind = T.disk(rad_ind).astype(bool)
    for zid, z in Z.items():
        W, DT, body, indigo, sky_dist = z["W"], z["DT"], z["body"], z["indigo"], z["sky_dist"]
        off = z["off"]
        H, Wd = W.shape
        for c in z["claws"]:
            C = c["C"]
            Cr, tr = resample(C, step)
            hw = bilinear(DT, Cr)  # 白の半幅
            L = c["length"]
            wid = 2.0 * hw

            def w_at(frac):
                t = frac * L
                sel = np.abs(tr - t) <= max(step, 0.06 * L)
                return float(np.median(wid[sel])) if sel.any() else float(np.interp(t, tr, wid))
            root_w, mid_w, tipw = w_at(0.08), w_at(0.5), w_at(0.85)
            back = min(float(cw["tip_direction_back_ref_px"]), 0.35 * L)
            pb = np.array([np.interp(L - back, tr, Cr[:, 0]), np.interp(L - back, tr, Cr[:, 1])])
            v = Cr[-1] - pb
            ang = math.degrees(math.atan2(v[1], v[0])) % 360.0
            root_abs, tip_abs = Cr[0] + off, Cr[-1] + off
            s_tip, d_tip = s_of(tip_abs)
            s_root, _ = s_of(root_abs)
            ty, tx = int(round(Cr[-1][1])), int(round(Cr[-1][0]))
            ty, tx = min(max(ty, 0), H - 1), min(max(tx, 0), Wd - 1)
            sky_d = float(sky_dist[ty, tx])
            # 先端のまわりの白以外のうち藍の割合
            y0, y1 = max(0, ty - rad_ind), min(H, ty + rad_ind + 1)
            x0, x1 = max(0, tx - rad_ind), min(Wd, tx + rad_ind + 1)
            dk = disk_ind[(y0 - ty + rad_ind):(y1 - ty + rad_ind), (x0 - tx + rad_ind):(x1 - tx + rad_ind)]
            nonwhite = dk & ~W[y0:y1, x0:x1]
            ind_frac = float((indigo[y0:y1, x0:x1] & nonwhite).sum() / max(1, nonwhite.sum()))
            silhouette = sky_d <= float(cw["silhouette_sky_dist_ref_px"])
            over_indigo = (not silhouette) and ind_frac >= float(cw["indigo_side_fraction"])
            row = row_of(z["zd"]["rows"], s_tip, tip_abs)
            # 列の中の並び：主浪は基準曲線の s、右側は先端の x（右側の波の白の縁は左下から右上へ続く）
            order_key = s_tip if z["zd"]["rows"] == "main" else float(tip_abs[0])
            # 関節
            jid, jdev = joints_of(Cr, int(cw["joints_min"]), int(cw["joints_max"]), float(cw["joints_tol_frac_of_length"]) * L)
            J = Cr[jid]
            segL = np.hypot(*np.diff(J, axis=0).T)
            # 幹（分岐の中心 → 根元）の標本と幅。波頭の平らな白（body）の外の部分だけにする
            if len(c["stem"]) >= 2:
                Sr, _ = resample(c["stem"], step)
            else:
                Sr = c["stem"][:1].copy()
            ib = body[np.clip(np.round(Sr[:, 1]).astype(int), 0, H - 1), np.clip(np.round(Sr[:, 0]).astype(int), 0, Wd - 1)]
            inside_idx = np.flatnonzero(ib)
            if len(inside_idx):
                Sr = Sr[inside_idx[-1] + 1:] if inside_idx[-1] + 1 < len(Sr) else Sr[-1:]
            Sw = 2.0 * bilinear(DT, Sr)
            # 輪郭（根元→先端の枝に沿った内接円の和 ∩ 白）
            full = np.round(c["finger"]).astype(int)
            full[:, 0] = np.clip(full[:, 0], 0, Wd - 1)
            full[:, 1] = np.clip(full[:, 1], 0, H - 1)
            rmax = int(math.ceil(float(DT[full[:, 1], full[:, 0]].max()))) + 2
            bx0, by0 = max(0, full[:, 0].min() - rmax), max(0, full[:, 1].min() - rmax)
            bx1, by1 = min(Wd, full[:, 0].max() + rmax + 1), min(H, full[:, 1].max() + rmax + 1)
            reg = np.zeros((by1 - by0, bx1 - bx0), np.uint8)
            for (x, y) in full:
                r = float(DT[y, x])
                if r > 0.5:
                    cv2.circle(reg, (x - bx0, y - by0), int(round(r)), 1, -1)
            reg = (reg > 0) & W[by0:by1, bx0:bx1]
            cnts, _ = cv2.findContours(reg.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            poly = []
            if cnts:
                cmax = max(cnts, key=cv2.contourArea)
                ap_ = cv2.approxPolyDP(cmax, float(cw["polygon_eps_ref_px"]), True).reshape(-1, 2).astype(np.float64)
                poly = (ap_ + off + [bx0, by0]).tolist()
            c.update({
                "Cr": Cr, "tr": tr, "wid": wid, "root_w": root_w, "mid_w": mid_w, "tip_w": tipw, "tip_ang": ang,
                "root_abs": root_abs, "tip_abs": tip_abs, "s_tip": s_tip, "s_root": s_root, "d_tip_curve": d_tip,
                "sky_d": sky_d, "ind_frac": ind_frac, "silhouette": bool(silhouette), "over_indigo": bool(over_indigo), "row": row,
                "order_key": order_key, "joints": J, "joint_dev": jdev, "seg_ratio": (segL / max(segL.sum(), 1e-9)).tolist(),
                "bend": turning_deg(J), "region": (by0, bx0, reg), "poly": poly, "stem_r": Sr, "stem_w": Sw, "webs": [],
            })
            claws.append(c)
        for wb in z["webs"]:
            z["claws"][wb["claw"]]["webs"].append(wb)

    # ---- 番号（列の順 → 列の中で s（右側は x）の順）
    order = {r: i for i, r in enumerate(rows_p["order"])}
    claws.sort(key=lambda c: (order[c["row"]], c["order_key"], c["tip_abs"][1]))
    per_row = {}
    for i, c in enumerate(claws, start=1):
        c["num"] = i
        per_row.setdefault(c["row"], []).append(c)
        c["idx_in_row"] = len(per_row[c["row"]])
        c["id"] = "C%03d" % i
        c["row_id"] = "%s%02d" % (rows_p["code"][c["row"]], c["idx_in_row"])

    # ---- 隣との隙間（列の中の並びで次の爪）
    for r, lst in per_row.items():
        for a, b in zip(lst[:-1], lst[1:]):
            a["gap_next"] = {"to": b["id"], "root_ref_px": float(np.hypot(*(a["root_abs"] - b["root_abs"]))),
                             "tip_ref_px": float(np.hypot(*(a["tip_abs"] - b["tip_abs"])))}

    # ---- 遮蔽の順序（仮）：根元が下（画面の y が大きい）ほど手前。同じ範囲で接する爪どうしで前後を記す
    front = sorted(claws, key=lambda c: -c["root_abs"][1])
    for rank, c in enumerate(front, start=1):
        c["occl_rank"] = rank
    touch = float(cw["occlusion_touch_ref_px"])
    rg = int(round(touch / 2.0))
    ker = T.disk(rg)
    grown = []
    for c in claws:
        by0, bx0, reg = c["region"]
        g = cv2.dilate(np.pad(reg.astype(np.uint8), rg), ker).astype(bool)
        grown.append((by0 - rg + int(c["off"][1]), bx0 - rg + int(c["off"][0]), g))
    for i, a in enumerate(claws):
        a["occludes"] = []
        ay, ax, ga = grown[i]
        for j, b in enumerate(claws):
            if i == j or a["zone"] != b["zone"] or a["occl_rank"] > b["occl_rank"]:
                continue
            by_, bx_, gb = grown[j]
            y0_, y1_ = max(ay, by_), min(ay + ga.shape[0], by_ + gb.shape[0])
            x0_, x1_ = max(ax, bx_), min(ax + ga.shape[1], bx_ + gb.shape[1])
            if y1_ <= y0_ or x1_ <= x0_:
                continue
            if (ga[y0_ - ay:y1_ - ay, x0_ - ax:x1_ - ax] & gb[y0_ - by_:y1_ - by_, x0_ - bx_:x1_ - bx_]).any():
                a["occludes"].append(b["id"])

    # ---- 代表10形の候補（主浪の 3 列への割り当て → 列の中で k-medoids）
    rp = prm["representative"]
    rep = []
    rows4 = list(rp["candidate_rows"])
    main_claws = [c for c in claws if c["row"] in MAIN_ROWS]
    Lq = float(np.quantile([c["length"] for c in main_claws], float(rp["min_length_quantile"]))) if main_claws else 0.0
    asp = float(rp.get("min_length_over_mid_width", 0.0))
    pools = {r: [c for c in claws if c["row"] == r and c["length"] >= Lq and c["length"] >= asp * c["mid_w"]] for r in rows4}
    total = sum(len(v) for v in pools.values())
    quota = {r: min(len(pools[r]), int(rp["min_per_row"])) for r in rows4}
    while sum(quota.values()) < min(int(rp["count"]), total):
        r = max((r for r in rows4 if quota[r] < len(pools[r])), key=lambda r: len(pools[r]) / (quota[r] + 1.0))
        quota[r] += 1

    def feats(lst):
        return np.array([[math.log(c["length"]), c["root_w"], c["mid_w"] / max(c["root_w"], 1e-6),
                          math.cos(math.radians(c["tip_ang"])), math.sin(math.radians(c["tip_ang"]))] for c in lst], np.float64)
    allF = feats([c for r in rows4 for c in pools[r]]) if total else np.zeros((0, 5))
    mu, sd = (allF.mean(0), np.maximum(allF.std(0), 1e-9)) if total else (0.0, 1.0)
    for r in rows4:
        lst, k = pools[r], quota[r]
        if k <= 0:
            continue
        F = (feats(lst) - mu) / sd
        med = [int(np.argmax([c["length"] for c in lst]))]
        while len(med) < k:
            dmin = np.min(np.linalg.norm(F[:, None, :] - F[None, med, :], axis=2), axis=1)
            dmin[med] = -1
            med.append(int(np.argmax(dmin)))
        for _ in range(50):
            D = np.linalg.norm(F[:, None, :] - F[None, med, :], axis=2)
            lab_ = np.argmin(D, axis=1)
            new = []
            for j in range(k):
                mem = np.flatnonzero(lab_ == j)
                if len(mem) == 0:
                    new.append(med[j])
                    continue
                Dm = np.linalg.norm(F[mem][:, None, :] - F[mem][None, :, :], axis=2).sum(1)
                new.append(int(mem[int(np.argmin(Dm))]))
            if new == med:
                break
            med = new
        sizes = np.bincount(np.argmin(np.linalg.norm(F[:, None, :] - F[None, med, :], axis=2), axis=1), minlength=k)
        for j in np.argsort(-sizes, kind="stable"):
            lst[med[j]]["rep_cluster_size"] = int(sizes[j])
            rep.append(lst[med[j]])
    rep_note = "母集団 %d 本（長さ ≥ %.1f px＝主浪の爪の %.0f%% 分位、かつ長さ ≥ %.1f × 中央幅）。列ごとの本数 %s。" % (
        total, Lq, 100 * float(rp["min_length_quantile"]), asp, json.dumps(quota, ensure_ascii=False))
    for i, c in enumerate(rep, start=1):
        c["rep"] = "R%d" % i
    rep_by_len = sorted(rep, key=lambda c: -c["length"])
    rep_by_root = sorted(rep, key=lambda c: -c["root_w"])
    rep_by_mid = sorted(rep, key=lambda c: -c["mid_w"])

    # ---- 船側中央の候補
    bp = prm["boat_side_centre"]
    brow = [c for c in claws if c["row"] == bp["row"]]
    bmed = float(np.median([c["length"] for c in brow])) if brow else 0.0

    def chord_deg(c):
        v = c["tip_abs"] - c["root_abs"]
        return math.degrees(math.atan2(v[1], v[0])) % 360.0
    lo, hi = bp["chord_down_deg"]
    boat = sorted([c for c in brow if c["silhouette"] and lo <= chord_deg(c) <= hi and c["length"] >= bmed], key=lambda c: c["s_tip"])
    centre = []
    if boat:
        m = (len(boat) - 1) // 2
        for k_, j in enumerate([m, m - 1, m + 1]):
            if 0 <= j < len(boat):
                centre.append((k_ + 1, boat[j]))

    # ---- 一覧から描き直した爪の和集合と原画の白の IoU（原画の全体の大きさの配列で、範囲ごとに描いて合わせる）
    Hf, Wf = sky_ref.shape
    M = {k: np.zeros((Hf, Wf), bool) for k in ("white", "body", "fingers", "fingers_stems", "all", "regions", "mat")}
    for zid, z in Z.items():
        cy, cx = z["crop"]
        M["white"][cy, cx] |= z["W"]
        M["body"][cy, cx] |= z["W"] & z["body"]
        ys_, xs_ = np.nonzero(z["S"])
        mat = np.zeros(z["W"].shape, np.uint8)
        for y_, x_ in zip(ys_, xs_):
            r_ = float(z["DT"][y_, x_])
            if r_ > 0.5:
                cv2.circle(mat, (int(x_), int(y_)), int(round(r_)), 1, -1)
        M["mat"][cy, cx] |= (mat > 0) & z["W"]
    cf = np.zeros((Hf, Wf), np.uint8)
    cfs = np.zeros((Hf, Wf), np.uint8)
    ca = np.zeros((Hf, Wf), np.uint8)
    for c in claws:
        off = c["off"]
        sweep(cf, c["Cr"] + off, c["wid"])
        sweep(cfs, c["Cr"] + off, c["wid"])
        sweep(ca, c["Cr"] + off, c["wid"])
        if len(c["stem_r"]) >= 2:
            sweep(cfs, c["stem_r"] + off, c["stem_w"])
            sweep(ca, c["stem_r"] + off, c["stem_w"])
        for wb in c["webs"]:
            sweep(ca, wb["Cr"] + off, wb["wid"])
        by0, bx0, reg = c["region"]
        y0_, x0_ = by0 + int(off[1]), bx0 + int(off[0])
        M["regions"][y0_:y0_ + reg.shape[0], x0_:x0_ + reg.shape[1]] |= reg
    M["fingers"], M["fingers_stems"], M["all"] = cf > 0, cfs > 0, ca > 0
    body_poly_mask = np.zeros((Hf, Wf), np.uint8)
    for zid, z in Z.items():
        for bp_ in z["body_polys"]:
            cv2.fillPoly(body_poly_mask, [np.round(bp_).astype(np.int32)], 1)
    claw_white = M["white"] & ~M["body"]
    nb = ~M["body"]

    def iou(a, b):
        u = (a | b).sum()
        return float((a & b).sum() / u) if u else 0.0

    def cover(a, b):
        return float((a & b).sum() / max(1, b.sum()))

    def prec(a, b):
        return float((a & b).sum() / max(1, a.sum()))

    def iou_block(sel):
        cwh = claw_white & sel
        out = {
            "target_claw_white_ref_px": int(cwh.sum()),
            "target_all_white_ref_px": int((M["white"] & sel).sum()),
            "body_white_ref_px": int((M["body"] & sel).sum()),
            "iou_all_parts_vs_claw_white": iou(M["all"] & nb & sel, cwh),
            "recall_all_parts": cover(M["all"] & nb & sel, cwh),
            "precision_all_parts": prec(M["all"] & nb & sel, cwh),
            "iou_fingers_stems_vs_claw_white": iou(M["fingers_stems"] & nb & sel, cwh),
            "iou_fingers_only_vs_claw_white": iou(M["fingers"] & nb & sel, cwh),
            "iou_outline_polygons_vs_claw_white": iou(M["regions"] & nb & sel, cwh),
            "iou_all_parts_plus_body_polygons_vs_all_white": iou((M["all"] | (body_poly_mask > 0)) & sel, M["white"] & sel),
            "reference_whole_skeleton_mat_iou_vs_claw_white": iou(M["mat"] & nb & sel, cwh),
        }
        return out
    zsel = {}
    for zid, z in Z.items():
        m_ = np.zeros((Hf, Wf), bool)
        m_[z["crop"]] = z["zone"]
        zsel[zid] = m_
    iou_rec = {"all_zones": iou_block(zsel["main"] | zsel["right"]) if "right" in zsel else iou_block(zsel["main"])}
    for zid in Z:
        iou_rec[zid] = iou_block(zsel[zid])
    # 表示解像度（1920×1080 の被覆率 > 0.5）でも測る（主浪の範囲の外も含めた全体）
    def to_disp(m):
        return T.ref_mask_to_cov(m, fmap) > 0.5
    cw_d = to_disp(claw_white)
    iou_rec["display_all_zones"] = {
        "iou_all_parts_vs_claw_white": iou(to_disp(M["all"] & nb), cw_d),
        "iou_fingers_only_vs_claw_white": iou(to_disp(M["fingers"] & nb), cw_d),
    }
    timings["iou_s"] = round(time.time() - t_start - timings["sky_s"] - timings["zones_s"], 2)

    # ---- 出力 JSON
    k_disp = fmap.s

    def disp(p):
        return fmap.ref_to_disp(np.asarray(p, np.float64))
    out_claws = []
    for c in claws:
        off = c["off"]
        J = c["joints"] + off
        rec = {
            "id": c["id"], "row": c["row"], "row_id": c["row_id"], "zone": c["zone"],
            "backlog_row_item": rows_p["backlog"][c["row"]],
            "source": {"stroke": "auto", "stroke_free": "auto（両端が端点の白）", "manual": "manual（目視で追加）"}[c["kind"]],
            "root_attach": ("白の塊（波頭の平らな白）" if c["root_in_body"] else {"junction": "他の爪の白との分岐", "end": "端点（切り離された白）", "": "手で描いた根元"}.get(c["root_end"], c["root_end"])),
            "skeleton_edges": c["n_edges"], "cut_by_max_length": c["cut_by_length"], "root_by_width_jump": c["root_by_width_jump"],
            "visual_correction_ja": ("根元を付け替え：" + c["trimmed"]) if c["trimmed"] else "",
            "silhouette": c["silhouette"], "over_indigo": c["over_indigo"],
            "root_ref": rnd(c["root_abs"], 1), "tip_ref": rnd(c["tip_abs"], 1),
            "root_display": rnd(disp(c["root_abs"]), 2), "tip_display": rnd(disp(c["tip_abs"]), 2),
            "length_ref_px": rnd(c["length"], 1), "length_display_px": rnd(c["length"] * k_disp, 2),
            "chord_ref_px": rnd(np.hypot(*(c["tip_abs"] - c["root_abs"])), 1),
            "root_width_ref_px": rnd(c["root_w"], 1), "mid_width_ref_px": rnd(c["mid_w"], 1), "tip_width_ref_px": rnd(c["tip_w"], 1),
            "root_width_display_px": rnd(c["root_w"] * k_disp, 2), "mid_width_display_px": rnd(c["mid_w"] * k_disp, 2),
            "taper_mid_over_root": rnd(c["mid_w"] / max(c["root_w"], 1e-6), 3),
            "tip_direction_deg": rnd(c["tip_ang"], 1), "tip_direction_ja": compass_ja(c["tip_ang"]),
            "s_tip_ref_px": rnd(c["s_tip"], 1), "s_root_ref_px": rnd(c["s_root"], 1),
            "tip_to_sky_ref_px": rnd(c["sky_d"], 1), "tip_indigo_fraction": rnd(c["ind_frac"], 3),
            "occlusion_rank_front_first": c["occl_rank"], "occludes": c["occludes"],
            "gap_next": ({"to": c["gap_next"]["to"], "root_ref_px": rnd(c["gap_next"]["root_ref_px"], 1),
                          "tip_ref_px": rnd(c["gap_next"]["tip_ref_px"], 1),
                          "root_display_px": rnd(c["gap_next"]["root_ref_px"] * k_disp, 2),
                          "tip_display_px": rnd(c["gap_next"]["tip_ref_px"] * k_disp, 2)} if "gap_next" in c else None),
            "centerline_ref": rnd(c["Cr"] + off, 1),
            "centerline_width_ref_px": rnd(c["wid"], 1),
            "stem_ref": rnd(c["stem_r"] + off, 1), "stem_width_ref_px": rnd(c["stem_w"], 1),
            "base_web": [{"centerline_ref": rnd(wb["Cr"] + off, 1), "width_ref_px": rnd(wb["wid"], 1)} for wb in c["webs"]],
            "rep_cluster_size": c.get("rep_cluster_size"),
            "joints_ref": rnd(J, 1), "joint_max_deviation_ref_px": rnd(c["joint_dev"], 2),
            "segment_length_ratio": rnd(c["seg_ratio"], 3), "bend_deg_clockwise": rnd(c["bend"], 1),
            "outline_polygon_ref": rnd(c["poly"], 1),
        }
        if c.get("rep"):
            rec["representative_candidate"] = c["rep"]
        out_claws.append(rec)
    row_counts = {r: len(per_row.get(r, [])) for r in rows_p["order"]}
    sil_counts = {r: sum(1 for c in per_row.get(r, []) if c["silhouette"]) for r in rows_p["order"]}
    ind_counts = {r: sum(1 for c in per_row.get(r, []) if c["over_indigo"]) for r in rows_p["order"]}
    n_main = sum(row_counts[r] for r in MAIN_ROWS)
    excluded = [e for z in Z.values() for e in z["excluded"]]
    n_webs = sum(len(c["webs"]) for c in claws)
    inv = {
        "schema": "GreatWave.ClawInventory/1",
        "number": "29",
        "version": VERSION,
        "status_ja": "草稿（CP1 用）。自動抽出に agent の目視修正（af29_params.json の corrections）を加えた段階で、利用者は未確認。列の境目、代表10形、船側中央の爪、遮蔽の順序はすべて候補・仮の値。完成版は 10/4 までの番号29 の続きで作る。",
        "reference": {"path": spec["reference"]["path"], "sha256": spec["reference"]["sha256"], "width": spec["reference"]["width"], "height": spec["reference"]["height"]},
        "truth_version": spec["version"],
        "coordinate_convention_ja": "*_ref は高解像度原画の画素中心整数系（x 右、y 下）。*_display は番号23 の表示フレーム（1920×1080、x_d = %.6f·(x_r + 0.5) − 0.5 + %.5f、y_d = %.6f·(y_r + 0.5) − 0.5）。" % (fmap.s, fmap.ox, fmap.s),
        "reference_model_used": False,
        "zones": [{"id": zd["id"], "name_ja": zd["name_ja"], "points_ref": zd["points"], "rows": zd["rows"], "body_open_radius_ref_px": zd["body_open_radius_ref_px"]} for zd in prm["zones"]],
        "definitions_ja": {
            "claw": "白（番号23 の色分けで white、空と船の黄土を除く。右側の範囲だけは white と mizuiro を合わせる。zones の mask_classes）の領域を Zhang–Suen で骨格化し、とげを除き、枝を分岐でなめらかに続くストローク（折れ角 ≤ %.0f°の組を貪欲に対にする）にまとめた後、端点（先端）を持つストローク。根元側から先端へ向かう中心線を持つ。" % float(prm["stroke"]["max_deflect_deg"]),
            "root": "中心線の根元側の端。ストロークの根元側の端が分岐なら、その分岐の内接円の縁（他の爪の白から出る所）。先端からたどって白の塊（範囲ごとの半径の円で開いて残る厚い白＝波頭の平らな白）に入るなら、その点。さらに、半幅が先端側の半分の中央値の %.1f 倍（下限 %.1f px）を超える所（厚い白へ入る所）より根元側は含めない。いずれも先端に近い方を採る。stem_ref は根元より根元側のストロークのうち、白の塊の外の部分（幹）。" % (float(cw["width_jump_ratio"]), float(cw["width_jump_floor_ref_px"])),
            "base_web": "根元の白。どの爪のストロークにも半分以上含まれない骨格の枝（先端の見えない白い舌、爪の間をつなぐ白、長さで切った幹の残り）の、白の塊の外の部分。枝の端に最も近い爪に付ける。爪の数には入れない。",
            "width": "白の距離変換の 2 倍（藍の輪郭線と水色の陰は含まない）。根元幅は弧長 8%%、中央幅は 50%%、先端付近の幅は 85%% の位置（±max(%.0f px, 6%%) の中央値）。" % step,
            "tip_direction": "先端から %.0f px（長さの 35%% が短ければそちら）戻った点から先端への向き。画面座標で 0°＝右、90°＝下。" % float(cw["tip_direction_back_ref_px"]),
            "row": rows_p["assign_ja"] + " 境目は s = " + json.dumps(br, ensure_ascii=False) + "。" + rows_p["note_ja"],
            "silhouette": "先端から空まで %.0f px 以内（原画の外輪郭に出ている爪）。" % float(cw["silhouette_sky_dist_ref_px"]),
            "over_indigo": "空から %.0f px より遠く、先端のまわり（半径 %d px）の白以外の半分以上が藍の爪（藍の面へ垂れる爪）。" % (float(cw["silhouette_sky_dist_ref_px"]), rad_ind),
            "occlusion": "仮：根元が画面の下にある爪ほど手前（番号1が最も手前）。backlog 140『船へ曲がる端の爪が上側の爪より手前』に合わせた推定で、原画の線の重なりからは判定していない。occludes は同じ範囲で輪郭が %.0f px 以内に接する爪のうち、この仮の順で後ろになるもの。" % touch,
            "gap_next": "同じ列の中で並び（主浪は s、右側は先端の x）の次の爪までの、根元どうし・先端どうしの距離。",
            "joints": "中心線に最遠点の挿入で置いた関節（根元と先端を含む %d〜%d 点）。ずれが長さの %.0f%% 以下になる最小の点数。bend_deg_clockwise は内側の関節での曲がり角（画面で時計回りが正）。" % (int(cw["joints_min"]), int(cw["joints_max"]), 100 * float(cw["joints_tol_frac_of_length"])),
            "redraw_for_iou": "一覧の centerline_ref と centerline_width_ref_px（指）、stem_ref と stem_width_ref_px（幹）、base_web（根元の白）だけから、各標本に直径＝幅の円を置き、隣の標本を同じ太さの線でつないで塗る。原画の白（右側の範囲は白と水色）と比べる範囲からは、波頭の平らな白（白の塊）を除く。",
            "outline_polygon": "根元→先端の中心線（幹は含まない）に沿った内接円の和と白の共通部分の外周（%.1f px で単純化）。" % float(cw["polygon_eps_ref_px"]),
        },
        "counts": {"total": len(claws), "main_wave_total": n_main, "right_side_total": row_counts.get("右側", 0), "by_row": row_counts,
                   "silhouette_by_row": sil_counts, "over_indigo_by_row": ind_counts,
                   "excluded_candidates": len(excluded), "base_web_pieces": n_webs,
                   "note_ja": "total は端点（見える先端）を持つ爪。main_wave_total は主浪の 3 列（上側・途中・船側）、right_side_total は右側の波。base_web_pieces（根元の白）と excluded_candidates（短い・範囲の縁・目視で除外）は数に入れない。"},
        "representative_candidates": {
            "ids": [c["id"] for c in rep], "labels": {c["id"]: c["rep"] for c in rep},
            "order_by_length_long_first": [c["id"] for c in rep_by_len],
            "order_by_root_width_wide_first": [c["id"] for c in rep_by_root],
            "order_by_mid_width_wide_first": [c["id"] for c in rep_by_mid],
            "selection_ja": prm["representative"]["note_ja"] + " " + rep_note,
        },
        "boat_side_centre_candidates": [
            {"rank": k_, "id": c["id"], "row_id": c["row_id"], "index_in_boat_side_silhouette": [b["id"] for b in boat].index(c["id"]) + 1, "of": len(boat),
             "root_wider_than_tip": bool(c["root_w"] > c["tip_w"]), "root_width_ref_px": rnd(c["root_w"], 1), "tip_width_ref_px": rnd(c["tip_w"], 1),
             "tip_direction_ja": compass_ja(c["tip_ang"])} for k_, c in centre],
        "boat_side_silhouette_down_order": [c["id"] for c in boat],
        "representative_and_centre_details": [
            {"id": c["id"], "labels": ([c["rep"]] if c.get("rep") else []) + (["船側中央の候補%d" % k_] if k_ else []),
             "row": c["row"], "row_id": c["row_id"],
             "length_ref_px": rnd(c["length"], 1), "root_width_ref_px": rnd(c["root_w"], 1), "mid_width_ref_px": rnd(c["mid_w"], 1),
             "tip_width_ref_px": rnd(c["tip_w"], 1), "tip_direction_deg": rnd(c["tip_ang"], 1),
             "centerline_ref": rnd(c["Cr"] + c["off"], 1), "joints_ref": rnd(c["joints"] + c["off"], 1),
             "segment_length_ratio": rnd(c["seg_ratio"], 3), "bend_deg_clockwise": rnd(c["bend"], 1)}
            for c, k_ in ([(c, dict((cc["id"], kk) for kk, cc in centre).get(c["id"], 0)) for c in rep]
                          + [(c, k_) for k_, c in centre if c["id"] not in {r_["id"] for r_ in rep}])],
        "crest_body_white_polygons_ref": {zid: [rnd(p_, 1) for p_ in z["body_polys"]] for zid, z in Z.items()},
        "claws": out_claws,
        "excluded_candidates": excluded,
    }
    T.save_json(OUT_JSON, inv)

    # ---- 図
    figs = make_figures(fmap, ref_rgb, claws, rep, centre, Z, M, claw_white, ev_dir, iou_rec, row_counts, n_main)

    # ---- 指標と実行記録
    zone_stats = {zid: z["stats"] for zid, z in Z.items()}
    metrics = build_metrics(inv, iou_rec, zone_stats, row_counts, sil_counts, rep, rep_by_len, centre, sky_check, n_main)
    T.save_json(os.path.join(ev_dir, "metrics.json"), metrics)
    timings["total_s"] = round(time.time() - t_start, 2)
    run = build_run(spec, args, figs, timings, zone_stats, sky_check, ev_dir)
    T.save_json(os.path.join(ev_dir, "run.json"), run)
    print(json.dumps({"counts": inv["counts"], "iou": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in iou_rec.items()},
                      "zones": zone_stats, "sky_check": sky_check, "timings": timings,
                      "rep": [(c["id"], c["row"], round(c["length"], 1)) for c in rep],
                      "centre": [(k_, c["id"], c["row_id"]) for k_, c in centre]}, ensure_ascii=False, indent=1))


# ---------------------------------------------------------------- 図
def _font():
    for p in (r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"):
        if os.path.exists(p):
            return p
    return None


def _text(img, items, size):
    """PIL で日本語と数字を描く。items は (x, y, 文字列, RGB, 縁取り RGB or None)。"""
    from PIL import Image, ImageDraw, ImageFont
    fp = _font()
    font = ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    for x, y, s, col, edge in items:
        if edge is not None:
            dr.text((x, y), s, fill=tuple(col), font=font, stroke_width=max(1, size // 8), stroke_fill=tuple(edge))
        else:
            dr.text((x, y), s, fill=tuple(col), font=font)
    return np.asarray(im).copy()


def _view(ref_rgb, x0, y0, w, h, W=1920, H=1080):
    """原画の矩形（高解像度 px）を 1920×1080 に収める（縦横同倍率、余白は暗い灰）。戻り値 (画像, 写像)。"""
    k = min(W / w, H / h)
    cx, cy = x0 + w / 2.0, y0 + h / 2.0
    M = np.array([[k, 0, W / 2.0 - k * cx], [0, k, H / 2.0 - k * cy]], np.float64)
    img = cv2.warpAffine(ref_rgb, M, (W, H), flags=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(40, 40, 40))
    return img, M


def _pts(M, P):
    P = np.asarray(P, np.float64)
    return (P @ M[:, :2].T + M[:, 2])


def draw_claws(img, M, claws, rep_ids, centre_ids, label_size, show_ids=True, line=2, dim=0.55, webs=True, only_rows=None):
    base = (img.astype(np.float32) * dim + 255 * (1 - dim) * 0.35).astype(np.uint8)
    over = base.copy()
    sub = [c for c in claws if only_rows is None or c["row"] in only_rows]
    if webs:
        for c in sub:
            for wb in c["webs"]:
                Q = np.round(_pts(M, wb["Cr"] + c["off"]) * 4).astype(np.int32)
                cv2.polylines(over, [Q], False, (120, 120, 120), max(1, line - 1), cv2.LINE_AA, shift=2)
    labels = []
    for c in sub:
        off = c["off"]
        col = ROW_COLOURS[c["row"]]
        if c["poly"]:
            P = np.round(_pts(M, c["poly"]) * 4).astype(np.int32)
            cv2.polylines(over, [P], True, col, line, cv2.LINE_AA, shift=2)
        C = np.round(_pts(M, c["Cr"] + off) * 4).astype(np.int32)
        cv2.polylines(over, [C], False, (255, 255, 255), max(1, line - 1), cv2.LINE_AA, shift=2)
        r = _pts(M, (c["Cr"][0] + off)[None])[0]
        t = _pts(M, (c["Cr"][-1] + off)[None])[0]
        cv2.circle(over, (int(round(r[0])), int(round(r[1]))), max(2, line + 1), (0, 0, 0), -1, cv2.LINE_AA)
        cv2.circle(over, (int(round(t[0])), int(round(t[1]))), max(2, line + 1), col, -1, cv2.LINE_AA)
        if (c["id"] in rep_ids or c["id"] in centre_ids) and c["poly"]:
            P = np.round(_pts(M, c["poly"]) * 4).astype(np.int32)
            cv2.polylines(over, [P], True, (255, 255, 0) if c["id"] in rep_ids else (0, 255, 255), line + 2, cv2.LINE_AA, shift=2)
        if show_ids:
            lab = str(c["num"])
            if c.get("rep"):
                lab += "/" + c["rep"]
            if c["id"] in centre_ids:
                lab += "/中" + str(centre_ids[c["id"]])
            labels.append((t[0] + 3, t[1] - label_size * 0.6, lab, col, (0, 0, 0)))
    over = _text(over, labels, label_size) if labels else over
    return over


def legend(img, row_counts, extra_lines, size=22, x=20, y=16):
    items = []
    yy = y
    for r, col in ROW_COLOURS.items():
        items.append((x, yy, "■ %s（%d本）" % (r, row_counts.get(r, 0)), col, (0, 0, 0)))
        yy += size + 6
    for s in extra_lines:
        items.append((x, yy, s, (255, 255, 255), (0, 0, 0)))
        yy += size + 6
    return _text(img, items, size)


def _bbox_of(claws, pad):
    P = np.concatenate([np.asarray(c["poly"]) for c in claws if c["poly"]] + [c["Cr"] + c["off"] for c in claws], 0)
    x0, y0 = P[:, 0].min() - pad, P[:, 1].min() - pad
    return x0, y0, P[:, 0].max() - x0 + pad, P[:, 1].max() - y0 + pad


def make_figures(fmap, ref_rgb, claws, rep, centre, Z, M, claw_white, ev_dir, iou_rec, row_counts, n_main):
    rep_ids = {c["id"] for c in rep}
    centre_ids = {c["id"]: k for k, c in centre}
    out = {}
    reserved = [tuple(v) for v in ROW_COLOURS.values()] + [(255, 255, 255), (0, 0, 0), (255, 255, 0), (0, 255, 255), (40, 40, 40), (120, 120, 120)]
    extra = ["黄の太線＝代表10形の候補（R1〜R10）、水色の太線＝船側中央の候補（中1〜中3）",
             "白線＝中心線、黒点＝根元、色点＝先端、灰の細線＝根元の白（web、数に入れない）",
             "番号は一覧の番号（C001… の数字部分）。主浪 %d 本＋右側 %d 本" % (n_main, row_counts.get("右側", 0))]
    # 1) 表示フレーム全体（原画視点 1920×1080、番号23 の写像）
    img = fmap.warp_to_disp(ref_rgb, cv2.INTER_LINEAR)
    img[:, :fmap.x0] = 40
    img[:, fmap.x1 + 1:] = 40
    over = draw_claws(img, fmap.M, claws, rep_ids, centre_ids, 11, show_ids=True, line=1, dim=0.8, webs=False)
    over = legend(over, row_counts, ["番号29 爪の一覧 草稿（%s）：原画視点 1920×1080" % VERSION] + extra, size=18)
    p = os.path.join(ev_dir, "29_claws_overlay_display.png")
    T.save_png_reserved(p, over, reserved)
    out["overlay_display"] = p
    # 2) 主浪の波頭全体の拡大（番号を読むための図）
    main = [c for c in claws if c["zone"] == "main"]
    zm = Z["main"]
    ys, xs = np.nonzero(zm["W"])
    x0, y0 = xs.min() + zm["off"][0] - 20, ys.min() + zm["off"][1] - 20
    w, h = xs.max() - xs.min() + 40, ys.max() - ys.min() + 40
    img, Mv = _view(ref_rgb, x0, y0, w, h)
    over = draw_claws(img, Mv, main, rep_ids, centre_ids, 15, line=2, dim=0.8)
    over = legend(over, row_counts, ["主浪の波頭の拡大（高解像度原画 x %d〜%d、y %d〜%d）" % (x0, x0 + w, y0, y0 + h)] + extra, size=20)
    p = os.path.join(ev_dir, "29_claws_overlay_crest.png")
    T.save_png_reserved(p, over, reserved)
    out["overlay_crest"] = p
    # 3) 拡大：船側（唇の下面と右端）、途中、上側、右側
    for name, sel, lsize in (("boatside", ("船側",), 20), ("middle", ("途中",), 20), ("upper", ("上側",), 18), ("right", ("右側",), 20)):
        sub = [c for c in claws if c["row"] in sel]
        if not sub:
            continue
        x0, y0, w, h = _bbox_of(sub, 30)
        img, Mv = _view(ref_rgb, x0, y0, w, h)
        over = draw_claws(img, Mv, claws, rep_ids, centre_ids, lsize, line=2, dim=0.85)
        over = legend(over, row_counts, ["拡大：%s（高解像度原画 x %d〜%d、y %d〜%d）。ほかの列の爪も色を変えて描いた" % ("・".join(sel), x0, x0 + w, y0, y0 + h)] + extra[:2], size=20)
        p = os.path.join(ev_dir, "29_claws_zoom_%s.png" % name)
        T.save_png_reserved(p, over, reserved)
        out["zoom_" + name] = p
    # 4) 骨格（とげの除去の前後）：主浪と右側を上下に並べる
    panels = []
    for zid, hh in (("main", 700), ("right", 380)):
        z = Z[zid]
        Wz = z["W"]
        ys, xs = np.nonzero(Wz)
        xa, ya = xs.min() - 10, ys.min() - 10
        wz, hz = xs.max() - xa + 10, ys.max() - ya + 10
        k = min(1920.0 / wz, float(hh) / hz)
        Mz = np.array([[k, 0, 960 - k * (xa + wz / 2.0)], [0, k, hh / 2.0 - k * (ya + hz / 2.0)]])
        crop_rgb = np.ascontiguousarray(ref_rgb[z["crop"]])
        base = cv2.warpAffine(crop_rgb, Mz, (1920, hh), flags=cv2.INTER_AREA, borderValue=(40, 40, 40))
        base = (base.astype(np.float32) * 0.45).astype(np.uint8)
        Wv = cv2.warpAffine(Wz.astype(np.uint8) * 255, Mz, (1920, hh), flags=cv2.INTER_AREA) > 127
        base[Wv] = (base[Wv] * 0.3 + np.array([235, 235, 235]) * 0.7).astype(np.uint8)
        for Sk, col in ((z["S0"], (0, 120, 255)), (z["S"], (255, 60, 60))):
            Sv = cv2.warpAffine(cv2.dilate(Sk.astype(np.uint8), np.ones((3, 3), np.uint8)) * 255, Mz, (1920, hh), flags=cv2.INTER_AREA) > 60
            base[Sv] = col
        panels.append(base)
    sk = np.concatenate(panels, 0)
    sk = _text(sk, [(20, 16, "白のマスク（明るい灰）と Zhang–Suen の骨格：青＝とげの除去の前、赤＝除去の後。上＝主浪の波頭、下＝右側の波の白の縁", (255, 255, 255), (0, 0, 0))], 22)
    p = os.path.join(ev_dir, "29_skeleton.png")
    T.save_png_reserved(p, sk, [(0, 120, 255), (255, 60, 60), (255, 255, 255), (0, 0, 0)])
    out["skeleton"] = p
    # 5) 和集合の IoU（一致＝白、描き直しだけ＝赤、原画の爪の白だけ＝水色、波頭の平らな白＝灰）。主浪と右側を上下に並べる
    panels = []
    nbm = ~M["body"]
    for zid, hh in (("main", 700), ("right", 380)):
        z = Z[zid]
        cy, cx = z["crop"]
        Wz = M["white"][cy, cx]
        cwz = claw_white[cy, cx]
        az = M["all"][cy, cx] & nbm[cy, cx]
        fz = M["fingers"][cy, cx] & nbm[cy, cx]
        rgbm = np.zeros(Wz.shape + (3,), np.uint8)
        rgbm[M["body"][cy, cx]] = (110, 110, 110)
        rgbm[cwz & az] = (170, 170, 170)
        rgbm[cwz & fz] = (240, 240, 240)
        rgbm[az & ~cwz] = (255, 60, 60)
        rgbm[cwz & ~az] = (0, 200, 255)
        ys, xs = np.nonzero(Wz)
        xa, ya = xs.min() - 10, ys.min() - 10
        wz, hz = xs.max() - xa + 10, ys.max() - ya + 10
        k = min(1920.0 / wz, float(hh) / hz)
        Mz = np.array([[k, 0, 960 - k * (xa + wz / 2.0)], [0, k, hh / 2.0 - k * (ya + hz / 2.0)]])
        panels.append(cv2.warpAffine(rgbm, Mz, (1920, hh), flags=cv2.INTER_NEAREST, borderValue=(0, 0, 0)))
    img = np.concatenate(panels, 0)
    a, b = iou_rec["main"], iou_rec["right"]
    img = _text(img, [(20, 12, "一覧から描き直した和集合と原画の白：白＝指で一致、明るい灰＝幹・根元の白で一致、赤＝描き直しだけ、水色＝原画の爪の白だけ、灰＝波頭の平らな白（対象外）", (255, 255, 255), (0, 0, 0)),
                      (20, 44, "IoU（高解像度 px）　上＝主浪の波頭（白）：指＋幹＋根元の白 %.3f、指＋幹 %.3f、指だけ %.3f" % (
                          a["iou_all_parts_vs_claw_white"], a["iou_fingers_stems_vs_claw_white"], a["iou_fingers_only_vs_claw_white"]), (255, 255, 255), (0, 0, 0)),
                      (20, 712, "下＝右側の波（白と水色を合わせた面）：指＋幹＋根元の白 %.3f、指＋幹 %.3f、指だけ %.3f" % (
                          b["iou_all_parts_vs_claw_white"], b["iou_fingers_stems_vs_claw_white"], b["iou_fingers_only_vs_claw_white"]), (255, 255, 255), (0, 0, 0))], 19)
    p = os.path.join(ev_dir, "29_union_iou.png")
    T.save_png_reserved(p, img, [(240, 240, 240), (170, 170, 170), (255, 60, 60), (0, 200, 255), (110, 110, 110), (255, 255, 255), (0, 0, 0)])
    out["union_iou"] = p
    # 6) 代表10形と船側中央の候補の一覧（中心線、関節、節の長さ比、曲がり角）
    cards = rep + [c for _, c in centre if c["id"] not in rep_ids]
    out["representative_sheet"] = representative_sheet(ref_rgb, cards, rep, centre, ev_dir)
    return out


def representative_sheet(ref_rgb, cards, rep, centre, ev_dir):
    cols, rows = 5, 3
    cw_, ch_ = 1920 // cols, (1080 - 40) // rows
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    texts = [(20, 6, "代表10形の候補（R1〜R10）と船側中央の候補：黄＝中心線、赤＝関節（根元→先端）、数値＝長さ・根元幅・中央幅（表示 px）、節の長さ比、曲がり角", (255, 255, 255), None)]
    cmap = {c["id"]: k for k, c in centre}
    for i, c in enumerate(cards[:cols * rows]):
        off = c["off"]
        gx, gy = (i % cols) * cw_, 40 + (i // cols) * ch_
        P = np.concatenate([np.asarray(c["poly"]) if c["poly"] else (c["Cr"] + off), c["Cr"] + off], 0)
        x0, y0 = P[:, 0].min(), P[:, 1].min()
        w, h = P[:, 0].max() - x0, P[:, 1].max() - y0
        m = 0.25 * max(w, h) + 10
        x0, y0, w, h = x0 - m, y0 - m, w + 2 * m, h + 2 * m
        k = min(cw_ / w, (ch_ - 70) / h)
        Mv = np.array([[k, 0, gx + cw_ / 2.0 - k * (x0 + w / 2)], [0, k, gy + (ch_ - 70) / 2.0 - k * (y0 + h / 2)]])
        tile = cv2.warpAffine(ref_rgb, Mv, (1920, 1080), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(30, 30, 30))
        cell = (slice(gy, gy + ch_ - 70), slice(gx, gx + cw_))
        sheet[cell] = tile[cell]
        C = np.round(_pts(Mv, c["Cr"] + off) * 4).astype(np.int32)
        cv2.polylines(sheet, [C], False, (255, 255, 0), 2, cv2.LINE_AA, shift=2)
        if c["poly"]:
            cv2.polylines(sheet, [np.round(_pts(Mv, c["poly"]) * 4).astype(np.int32)], True, ROW_COLOURS[c["row"]], 1, cv2.LINE_AA, shift=2)
        Jp = _pts(Mv, c["joints"] + off)
        for j, q in enumerate(Jp):
            cv2.circle(sheet, (int(round(q[0])), int(round(q[1]))), 5 if j in (0, len(Jp) - 1) else 4, (255, 40, 40), -1, cv2.LINE_AA)
        cv2.rectangle(sheet, (gx + 1, gy), (gx + cw_ - 2, gy + ch_ - 2), (90, 90, 90), 1)
        kd = 1080.0 / 2594.0
        head = "%s  %s %s" % (c.get("rep", ""), c["id"], c["row"])
        if c["id"] in cmap:
            head += "  船側中央の候補%d" % cmap[c["id"]]
        l1 = "長さ %.1f・根元幅 %.1f・中央幅 %.1f px" % (c["length"] * kd, c["root_w"] * kd, c["mid_w"] * kd)
        l2 = "節の比 " + "/".join("%.2f" % v for v in c["seg_ratio"])
        l3 = "曲がり角 " + "/".join("%+.0f°" % v for v in c["bend"]) + "  先端 " + compass_ja(c["tip_ang"])
        ty = gy + ch_ - 68
        texts += [(gx + 6, gy + 4, head, (255, 255, 255), (0, 0, 0)), (gx + 6, ty, l1, (230, 230, 230), None),
                  (gx + 6, ty + 21, l2, (230, 230, 230), None), (gx + 6, ty + 42, l3, (230, 230, 230), None)]
    sheet = _text(sheet, texts, 17)
    p = os.path.join(ev_dir, "29_representative_candidates.png")
    T.save_png_reserved(p, sheet, [(255, 255, 0), (255, 40, 40), (255, 255, 255), (230, 230, 230), (30, 30, 30), (90, 90, 90), (0, 0, 0)] + list(ROW_COLOURS.values()))
    return p


# ---------------------------------------------------------------- 指標と記録
def build_metrics(inv, iou_rec, zone_stats, row_counts, sil_counts, rep, rep_by_len, centre, sky_check, n_main):
    n = inv["counts"]["total"]
    a = iou_rec["main"]

    def r4(d):
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items()}
    zs_ok = True
    zs_val = {}
    for zid, st in zone_stats.items():
        tb = st["topology_white_vs_skeleton_before_prune"]
        ta = st["topology_white_vs_skeleton_after_prune"]
        zs_val[zid] = {"before_prune": tb, "after_prune": ta}
        zs_ok &= (tb["components_mask"] == tb["components_skeleton"] and tb["background_regions_mask"] == tb["background_regions_skeleton"]
                  and tb["blocks_2x2"] == 0 and ta["blocks_2x2"] == 0)
    selftest = SK.selftest()
    zs_ok &= all(v["pass"] for v in selftest.values())
    return {
        "schema": "GreatWave.ArtFirst.metrics/1",
        "number": "29",
        "version": VERSION,
        "note_ja": "番号29 の草稿（CP1 用）。受入の数値は完成版（10/4）の目標で、草稿では記録のみ。どのバックログ項目も合格にしていない。",
        "plan_ja": "作業計画 4.2 の 29（B線、上限 2 日、9/29〜10/4）。この草稿の時間枠は 1 日。バックログ 95〜98、122〜129、136〜139、240〜256 の前提（爪の一覧）で、この番号自体はバックログ項目を判定しない。",
        "evidence_kind_ja": "Met 原画（高解像度 DP130155）の numpy/OpenCV 計算と、その重ね図。Unity・Blender・Houdini は使っていない。参照モデル（Q5）は読んでいない。",
        "items": [
            {"item": "29受入：一覧から描き直した爪の和集合と原画の白領域の IoU", "target": "≥ 0.85（完成版）", "value": round(a["iou_all_parts_vs_claw_white"], 4),
             "value_other": {k: r4(v) for k, v in iou_rec.items()},
             "verdict": "記録のみ（草稿）",
             "note_ja": "主の値は主浪の波頭の範囲で、指＋幹＋根元の白（base_web）を一覧だけから描き直した和集合と、波頭の平らな白（半径 45 px の円で開いて残る厚い塊）を除いた原画の白（爪の白）の IoU（高解像度 px）。同じ範囲で、指＋幹だけは %.4f、指だけは %.4f、輪郭の多角形の和は %.4f。右側の範囲（白と水色を合わせた面が対象）、2 つの範囲の合計、白の全体（平らな白の多角形を足す）、表示解像度の値も value_other に記す。reference_whole_skeleton_mat は、とげを除いた骨格の全体の内接円の和と白の共通部分（骨格で表せる白の上限の目安）。" % (
                 a["iou_fingers_stems_vs_claw_white"], a["iou_fingers_only_vs_claw_white"], a["iou_outline_polygons_vs_claw_white"])},
            {"item": "29受入：爪の数（backlog 139『配置した約150本』）", "target": "150 ± 15（完成版）", "value": n_main,
             "value_other": {"main_wave_total": n_main, "right_side_total": row_counts.get("右側", 0), "all_total": n, "by_row": row_counts, "silhouette_by_row": sil_counts,
                             "over_indigo_by_row": inv["counts"]["over_indigo_by_row"],
                             "base_web_pieces_not_counted": inv["counts"]["base_web_pieces"],
                             "excluded_candidates_not_counted": inv["counts"]["excluded_candidates"]},
             "verdict": "記録のみ（草稿）", "note_ja": "主の値は主浪の 3 列（上側・途中・船側）の本数。backlog 139 は主浪の爪の群（B022）の項目なので、右側の波の爪（backlog 240〜256、B055）は別に数えた。両方を足した値も記す。どちらを 150 と比べるかは CP2 で利用者に確かめる。"},
            {"item": "29受入：代表10形の長短の順序を自動で出力できる", "target": "出力できる", "value": [c["id"] for c in rep_by_len],
             "verdict": "記録のみ（草稿。候補の選定は利用者の CP2 確認待ち）" if len(rep) == 10 else "不足（候補が 10 本に届かない）",
             "note_ja": "claw_inventory_draft.json の representative_candidates に長さ・根元幅・中央幅の順を出力した。"},
            {"item": "29：船側中央の爪の候補（backlog 95〜98 の対象）", "target": "利用者が CP2 で指定", "value": [c["id"] for _, c in centre],
             "verdict": "記録のみ（候補）"},
            {"item": "123/124/125/126（代表10形）、122/127/128（各列の根元・先端）、261（隙間）、95〜98（船側中央）、240/243/246（右側）", "target": "番号33・40 で ≤4 px を判定",
             "value": "一覧に根元・先端・幅・向き・隙間を記録", "verdict": "記録のみ（判定は番号33 など）"},
            {"item": "自作 Zhang–Suen の確認（合成図形 2 種、原画の白の位相、太さ 2 の残り）", "target": "長方形→中央の 1 本線、穴あき円板と原画の白→成分と穴の数が細線化の前後で同じ、太さ 2 の残り 0",
             "value": {"selftest": selftest, "white_vs_skeleton": zs_val,
                       "thin_final_removed_px": {zid: st["thin_final_removed_px"] for zid, st in zone_stats.items()}},
             "verdict": "合格" if zs_ok else "不合格（記録）",
             "note_ja": "とげの除去の後は、端の枝を除くので成分の数が変わることがある（after_prune は記録のみ）。"},
            {"item": "空マスクの一致（番号23 真値 v0.2 の sky_claws_cov.png と、同じ手順で作り直した空の表示被覆率の差の最大）", "target": "0（同じ真値を使っている確認）",
             "value": sky_check, "verdict": "合格" if sky_check <= 1.0 / 65535.0 else "不一致"},
        ],
        "zones": {zid: {k: v for k, v in st.items() if not k.endswith("_s")} for zid, st in zone_stats.items()},
        "zones_note_ja": "計算時間（*_s）は run.json の zones に記す（metrics.json は同じ入力で同じバイト列になるようにする）。",
    }


def build_run(spec, args, figs, timings, zone_stats, sky_check, ev_dir):
    inputs = [spec["reference"]["path"], "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/manual_annotations.json",
              "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/targets/palette.json",
              "Tools/PaintingTruth/targets/main_wave_outline_envelope.json", "Tools/PaintingTruth/targets/masks/sky_claws_cov.png",
              "Tools/PaintingTruth/claws29/af29_params.json", "Tools/PaintingTruth/claws29/af29_skeleton.py",
              "Tools/PaintingTruth/claws29/af29_claw_inventory.py"]
    outs = [OUT_JSON] + list(figs.values()) + [os.path.join(ev_dir, "metrics.json")]
    return {
        "schema": "GreatWave.ArtFirst.run/1",
        "number": "29",
        "version": VERSION,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "command": "py -3.10 Tools/PaintingTruth/claws29/af29_claw_inventory.py --evidence " + args.evidence,
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": __import__("PIL").__version__, "os": platform.platform()},
        "reference_model_used": False,
        "inputs_sha256": {p: T.sha256_file(T.repo_abs(p)) for p in inputs},
        "outputs_sha256": {T.repo_rel(p): T.sha256_file(p) for p in outs},
        "outputs_note_ja": "run.json 自身は outputs に含めない（最後に書く）。図は 256 色の PNG（T.save_png_reserved）。",
        "timings_s": timings,
        "zones": zone_stats,
        "sky_mask_check_max_abs_cov_diff": sky_check,
    }


if __name__ == "__main__":
    main()
