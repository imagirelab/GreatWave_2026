# -*- coding: utf-8 -*-
"""番号29（爪の一覧）完成版：Met 原画だけから爪の一覧を作る（草稿 draft1 の続き）。

手順（作業計画 4.2 の 29）：
  1. 白の領域のマスク（番号23 真値 v0.2 と同じ手順の空マスクと、番号23 の 5 色の Lloyd 中心による色分け。船の黄土は除く）
  2. numpy で自作した Zhang–Suen の骨格化（af29_skeleton.py。余分な画素は単純点だけ逐次に除き、8連結で最小の骨格にする）
  3. 枝の分割（とげの除去 → 枝をストロークにまとめる → 先端を持つストローク = 爪。残りの枝は根元の白 web として爪に付ける）
  4. 水色の面の中の白い斑（縁に藍の線がなく、まわりがほぼ水色の白）を爪から除く（完成版で追加）
  5. agent が重ね図を見て修正（af29_params.json の corrections。完成版で先端と根元の入れ替え reverse_tips_ref を追加）
  6. 列：外周の接線の向きで決めた特徴点の近くで、爪の並びの最も広い隙間の中央に境目を置き、境目の余裕と感度を記録する（完成版）
  7. 右側の爪の読み：藍の線（mix）の骨格の自由端から、頭の藍の鉤を探し、「藍の鉤＝爪先」（読みB）と
     「尖る淡い指の先＝爪先」（読みA）の両方を記録する。主の読みは af29_params.json の right_reading.primary（完成版）
範囲は 2 つ：主浪の波頭の泡（列 = 上側・途中・船側）と、右側の波の白の縁（列 = 右側）。
各爪について、番号、所属する列、根元と先端の座標、根元と中央の幅、先端の方向、遮蔽の順序、隣との隙間、
輪郭の多角形、中心線、4〜6 の関節、節の長さ比、曲がり角を記録する。代表10形と船側中央の爪の候補を選ぶ。

参照モデル（Q5、wave_repair_zbrush2.obj）は読まない。numpy・OpenCV・PIL だけを使う。

使い方：
  py -3.10 Tools/PaintingTruth/claws29/af29_claw_inventory.py [--evidence Docs/Evidence/ArtFirst/29] [--out 一覧の JSON]
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

VERSION = "final1"
PARAMS_PATH = os.path.join(HERE, "af29_params.json")
OUT_JSON = os.path.join(HERE, "claw_inventory.json")
DRAFT_COMMIT = "c63e7bb"  # 草稿 draft1（claw_inventory_draft.json）のコミット。番号の対応（draft1_id）に使う
DRAFT1_TIPS = os.path.join(HERE, "af29_draft1_tips.json")  # 草稿 draft1 の番号・列・根元・先端（c63e7bb の claw_inventory_draft.json から抜き出した）
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


def finger_region(F, DT, W):
    """指の画素列 F（x, y の crop 座標）に沿った内接円の和と白の共通部分。戻り値 (by0, bx0, 領域)。"""
    H, Wd = W.shape
    full = np.round(np.asarray(F, np.float64)).astype(int)
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
    return by0, bx0, (reg > 0) & W[by0:by1, bx0:bx1]


def speck_ring(F, DT, W, cls, sky, ring_px):
    """指の領域のまわり（ring_px の輪）の、白（white の色）以外の画素のうち、藍の線（mix）・水色・藍・空の割合。"""
    by0, bx0, reg = finger_region(F, DT, W)
    pad = ring_px + 1
    H, Wd = W.shape
    y0, x0 = max(0, by0 - pad), max(0, bx0 - pad)
    y1, x1 = min(H, by0 + reg.shape[0] + pad), min(Wd, bx0 + reg.shape[1] + pad)
    R = np.zeros((y1 - y0, x1 - x0), np.uint8)
    R[by0 - y0:by0 - y0 + reg.shape[0], bx0 - x0:bx0 - x0 + reg.shape[1]] = reg
    ring = cv2.dilate(R, T.disk(ring_px)).astype(bool) & ~R.astype(bool)
    cc, ss = cls[y0:y1, x0:x1], sky[y0:y1, x0:x1]
    nonw = ring & ~((cc == CLASS_NAMES.index("white")) & ~ss)
    n = max(1, int(nonw.sum()))
    return {"line": float((nonw & (cc == CLASS_NAMES.index("mix")) & ~ss).sum() / n),
            "mizuiro": float((nonw & (cc == CLASS_NAMES.index("mizuiro")) & ~ss).sum() / n),
            "indigo": float((nonw & ((cc == CLASS_NAMES.index("ai_mid")) | (cc == CLASS_NAMES.index("ai_dark"))) & ~ss).sum() / n),
            "sky": float((nonw & ss).sum() / n), "n_px": n}


def line_skeleton(cls, sky, zone, lp):
    """藍の線（番号23 の色分けで mix）の骨格と、その端点（x, y, まわりの線以外のうち白・水色の割合）。crop 座標。"""
    zl = cv2.dilate(zone.astype(np.uint8), T.disk(int(lp["zone_dilate_ref_px"]))).astype(bool)
    line = (cls == CLASS_NAMES.index("mix")) & zl & ~sky
    line = cv2.morphologyEx(line.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(bool)
    n, lab, st, _ = cv2.connectedComponentsWithStats(line.astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    keep[1:] = st[1:, 4] >= int(lp["min_component_ref_px"])
    line = keep[lab]
    S, _ = SK.zhang_suen(line)
    S, _ = SK.thin_final(S)
    DTl = cv2.distanceTransform(line.astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
    S, _ = SK.prune_spurs(S, DTl, 1.5, float(lp["spur_ref_px"]), 5)
    nb = SK.NEIGHBOURS[SK.ncode(S)]
    pale = ((cls == CLASS_NAMES.index("white")) | (cls == CLASS_NAMES.index("mizuiro"))) & ~sky
    ends = []
    h = int(lp["free_end_window_ref_px"])
    H, Wd = S.shape
    for y, x in np.argwhere(S & (nb == 1)):
        y0, y1, x0, x1 = max(0, y - h), min(H, y + h + 1), max(0, x - h), min(Wd, x + h + 1)
        w = ~line[y0:y1, x0:x1]
        f = float((pale[y0:y1, x0:x1] & w).sum() / max(1, w.sum()))
        ends.append((int(x), int(y), f))
    return S, line, ends


def trace_line(S, start, max_len):
    """骨格 S を端点 start（x, y）から max_len まで辿った折れ線（x, y）。分岐では最も直進に近い枝へ進む。"""
    H, Wd = S.shape
    path = [tuple(start)]
    seen = {tuple(start)}
    L = 0.0
    while L < max_len:
        x, y = path[-1]
        nb = [(x + dx, y + dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx or dy)
              and 0 <= x + dx < Wd and 0 <= y + dy < H and S[y + dy, x + dx] and (x + dx, y + dy) not in seen]
        if not nb:
            break
        if len(path) >= 4:
            v = np.array(path[-1], float) - np.array(path[-4], float)
            nb.sort(key=lambda q: -float(np.dot(np.array(q, float) - np.array(path[-1], float), v)))
        else:
            nb.sort(key=lambda q: abs(q[0] - x) + abs(q[1] - y))
        q = nb[0]
        L += math.hypot(q[0] - x, q[1] - y)
        path.append(q)
        seen.add(q)
        for r in nb[1:]:
            seen.add(r)  # 横の画素は戻らない
    return np.asarray(path, np.float64)


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
    sp = cw.get("pale_speck", {})
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
        # 目視の修正：先端と根元の入れ替え（自動の先端がその円に入る爪は、中心線の向きを逆にする。指の画素は同じ）
        reversed_ = ""
        for xt, yt, rr, why in corr.get("reverse_tips_ref", []):
            if math.hypot(C[-1][0] + off[0] - xt, C[-1][1] + off[1] - yt) <= rr:
                C = C[::-1].copy()
                reversed_ = why
        stem = smooth_path(P[:i_root + 1], 5) if i_root >= 1 else P[:1].copy()
        length = float(cumlen(C)[-1])
        tip_abs = C[-1] + off
        rec = {"C": C, "full": P, "pix": pix, "finger": P[i_root:], "stem": stem, "i_root": i_root, "kind": c["kind"], "length": length,
               "rj": c["rj"], "reason": c.get("reason", ""), "root_end": c.get("root_end", ""), "n_edges": c.get("n_edges", 1),
               "root_in_body": bool(i_body > 0 and i_body >= i_rj and not reversed_), "cut_by_length": bool(c.get("cut_by_length", False)),
               "root_by_width_jump": bool(i_jump > 0 and i_jump >= max(i_rj, i_body) and not trimmed and not reversed_), "trimmed": trimmed,
               "reversed": reversed_, "zone": zd["id"], "off": off}
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
        if drop is None and c["kind"] != "manual" and sp.get("enabled", False):
            fr = speck_ring(rec["finger"], DT, W, cls, sky, int(sp["ring_ref_px"]))
            rec["ring_fractions"] = fr
            if fr["line"] <= float(sp["max_line_fraction"]) and fr["mizuiro"] >= float(sp["min_mizuiro_fraction"]):
                drop = "水色の面の中の白い斑（縁の白以外のうち藍の線 %.2f・水色 %.2f。指の縁に藍の線がない）" % (fr["line"], fr["mizuiro"])
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
    # 藍の線の骨格と自由端（右側の爪の読み B：藍の鉤＝爪先。主浪では記録だけ）
    Sl, line_m, ends = line_skeleton(cls, sky, zone, prm["right_reading"]["line"])
    stats["line_skeleton_px"] = int(Sl.sum())
    stats["line_free_ends"] = sum(1 for e in ends if e[2] >= float(prm["right_reading"]["line"]["free_end_pale_fraction"]))
    return {"zd": zd, "crop": crop, "off": off, "zone": zone, "W": W, "DT": DT, "body": body, "indigo": indigo, "sky_dist": sky_dist,
            "S0": S0, "S": S, "claws": claws, "excluded": excluded, "webs": webs, "stats": stats, "body_polys": body_polys,
            "cls": cls, "sky": sky, "line_S": Sl, "line": line_m, "line_ends": ends}


# ---------------------------------------------------------------- 爪ごとの計測（読み A：骨格の向きのまま）
def measure_claw(c, z, cw, step, s_of, disk_ind, rad_ind):
    W, DT, body, indigo, sky_dist = z["W"], z["DT"], z["body"], z["indigo"], z["sky_dist"]
    off = z["off"]
    H, Wd = W.shape
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
    s_root, d_root = s_of(root_abs)
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
    # 輪郭（指の枝に沿った内接円の和 ∩ 白）
    by0, bx0, reg = finger_region(c["finger"], DT, W)
    cnts, _ = cv2.findContours(reg.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    poly = []
    if cnts:
        cmax = max(cnts, key=cv2.contourArea)
        ap_ = cv2.approxPolyDP(cmax, float(cw["polygon_eps_ref_px"]), True).reshape(-1, 2).astype(np.float64)
        poly = (ap_ + off + [bx0, by0]).tolist()
    c.update({
        "Cr": Cr, "tr": tr, "wid": wid, "root_w": root_w, "mid_w": mid_w, "tip_w": tipw, "tip_ang": ang,
        "root_abs": root_abs, "tip_abs": tip_abs, "s_tip": s_tip, "s_root": s_root, "d_tip_curve": d_tip, "d_root_curve": d_root,
        "sky_d": sky_d, "ind_frac": ind_frac, "silhouette": bool(silhouette), "over_indigo": bool(over_indigo),
        "joints": J, "joint_dev": jdev, "seg_ratio": (segL / max(segL.sum(), 1e-9)).tolist(),
        "bend": turning_deg(J), "region": (by0, bx0, reg), "poly": poly, "stem_r": Sr, "stem_w": Sw, "webs": [],
    })


def end_context(z, p_abs, R):
    """点 p（原画座標）の半径 R の円の、白（white の色）以外の画素のうち、藍の線・藍・水色・空の割合。"""
    cls, sky = z["cls"], z["sky"]
    x, y = int(round(p_abs[0] - z["off"][0])), int(round(p_abs[1] - z["off"][1]))
    H, Wd = cls.shape
    y0, y1, x0, x1 = max(0, y - R), min(H, y + R + 1), max(0, x - R), min(Wd, x + R + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    disk_ = np.hypot(yy - y, xx - x) <= R
    cc, ss = cls[y0:y1, x0:x1], sky[y0:y1, x0:x1]
    m = disk_ & ~((cc == CLASS_NAMES.index("white")) & ~ss)
    n = max(1, int(m.sum()))
    return {"line": float((m & (cc == CLASS_NAMES.index("mix")) & ~ss).sum() / n),
            "indigo": float((m & ((cc == CLASS_NAMES.index("ai_mid")) | (cc == CLASS_NAMES.index("ai_dark"))) & ~ss).sum() / n),
            "mizuiro": float((m & (cc == CLASS_NAMES.index("mizuiro")) & ~ss).sum() / n), "sky": float((m & ss).sum() / n)}


# ---------------------------------------------------------------- 列（上側・途中・船側）
def tangent_deg(curve, s, win):
    """基準曲線の各点で、弧長 ±win の 2 点を結ぶ向き（度、画面座標、0°＝右、90°＝下）。"""
    out = np.zeros(len(curve))
    for i in range(len(curve)):
        a = int(np.searchsorted(s, s[i] - win))
        b = int(np.searchsorted(s, s[i] + win))
        a, b = max(0, min(a, len(curve) - 1)), max(0, min(b, len(curve) - 1))
        v = curve[b] - curve[a]
        out[i] = math.degrees(math.atan2(v[1], v[0]))
    return out


def feature_points(curve, s, rows_p, win):
    """外周の特徴点：波頂（s=0）の後で接線が初めて角度 A を超える所、その後で初めて角度 B を超える所。"""
    th = tangent_deg(curve, s, win)
    fa = rows_p["feature_angles_deg"]
    smax = float(rows_p["curve_s_max"])
    idx = np.flatnonzero((s > 0) & (s <= smax) & (th >= float(fa["上側|途中"])))
    sA = float(s[idx[0]]) if len(idx) else float(rows_p["breaks_s_fallback"]["上側|途中"])
    idx = np.flatnonzero((s > sA) & (s <= smax) & (th >= float(fa["途中|船側"])))
    sB = float(s[idx[0]]) if len(idx) else float(rows_p["breaks_s_fallback"]["途中|船側"])
    return {"上側|途中": sA, "途中|船側": sB}, th


def snap_to_gap(values, centre, window):
    """values（並べる値）のうち、中点が centre ± window に入る隣り合う組で、間隔が最も広い組の中点。組がなければ centre。"""
    v = np.sort(np.asarray(values, np.float64))
    best = None
    for a, b in zip(v[:-1], v[1:]):
        m = 0.5 * (a + b)
        if abs(m - centre) <= window and (best is None or b - a > best[1] - best[0]):
            best = (a, b)
    if best is None:
        return float(centre), None
    return float(0.5 * (best[0] + best[1])), [float(best[0]), float(best[1])]


def row_by_rule(zone_rows, s, x, breaks, x_split):
    if zone_rows != "main":
        return zone_rows
    if x < x_split:
        return "上側"
    if s < breaks["上側|途中"]:
        return "上側"
    if s < breaks["途中|船側"]:
        return "途中"
    return "船側"


def assign_rows(claws, rows_p, ref_curve, ref_s):
    win = float(rows_p["feature_tangent_window_ref_px"])
    feats, th = feature_points(ref_curve, ref_s, rows_p, win)
    snap_w = float(rows_p["snap_window_ref_px"])
    main = [c for c in claws if c["zone"] == "main"]
    x0 = float(rows_p["left_split_x_ref"])
    breaks, gaps = {}, {}
    for k in ("上側|途中", "途中|船側"):
        vals = [c["s_tip"] for c in main if c["tip_abs"][0] >= x0]
        breaks[k], gaps[k] = snap_to_gap(vals, feats[k], snap_w)
    # 左の境目（x）：外周への最近点で船側に入る爪（唇の下面の左端）と、左の群（藍の面の上縁）の間の隙間
    xs = [float(c["tip_abs"][0]) for c in main if c["s_tip"] >= breaks["途中|船側"] or c["tip_abs"][0] < x0]
    x_split, gx = snap_to_gap(xs, x0, float(rows_p["left_split_snap_window_ref_px"]))
    for c in claws:
        c["row"] = row_by_rule(c["zd_rows"], c["s_tip"], float(c["tip_abs"][0]), breaks, x_split)
    # 余裕：列を決めた量（s・x）から、越えると列が変わる境目までの最短の距離
    near = float(rows_p["near_boundary_ref_px"])
    for c in main:
        s, x = float(c["s_tip"]), float(c["tip_abs"][0])
        cand = []
        if row_by_rule("main", s, x_split - 0.5, breaks, x_split) != row_by_rule("main", s, x_split + 0.5, breaks, x_split):
            cand.append(abs(x - x_split))
        if x >= x_split:
            cand += [abs(s - breaks[k]) for k in breaks]
        c["row_margin"] = float(min(cand)) if cand else float("inf")
        c["row_near_boundary"] = bool(c["row_margin"] < near)
    # 感度：境目を ±shift 動かす／根元で決める／接線の窓を変える
    sh = float(rows_p["sensitivity_shift_ref_px"])
    base = {id(c): c["row"] for c in main}
    sens = {}
    for k in ("上側|途中", "途中|船側"):
        for d in (-sh, sh):
            b2 = dict(breaks)
            b2[k] = breaks[k] + d
            n = sum(1 for c in main if row_by_rule("main", c["s_tip"], c["tip_abs"][0], b2, x_split) != base[id(c)])
            sens["%s %+g" % (k, d)] = n
    for d in (-sh, sh):
        n = sum(1 for c in main if row_by_rule("main", c["s_tip"], c["tip_abs"][0], breaks, x_split + d) != base[id(c)])
        sens["x_split %+g" % d] = n
    root_diff = [c for c in main if row_by_rule("main", c["s_root"], c["root_abs"][0], breaks, x_split) != base[id(c)]]
    win_rec = {}
    for w2 in rows_p["feature_window_alternatives_ref_px"]:
        f2, _ = feature_points(ref_curve, ref_s, rows_p, float(w2))
        b2 = {}
        for k in f2:
            b2[k], _ = snap_to_gap([c["s_tip"] for c in main if c["tip_abs"][0] >= x0], f2[k], snap_w)
        n = sum(1 for c in main if row_by_rule("main", c["s_tip"], c["tip_abs"][0], b2, x_split) != base[id(c)])
        win_rec[str(w2)] = {"features_s": {k: round(v, 1) for k, v in f2.items()}, "breaks_s": {k: round(v, 1) for k, v in b2.items()}, "row_changes": n}
    return {"features_s": feats, "breaks_s": breaks, "gap_pairs_s": gaps, "x_split": x_split, "x_split_gap": gx,
            "tangent_window": win, "tangent_deg": th, "sensitivity_row_changes": sens,
            "root_based_disagreements": [c for c in root_diff], "window_alternatives": win_rec,
            "near_boundary": [c for c in main if c["row_near_boundary"]]}


# ---------------------------------------------------------------- 右側の爪の読み（A：尖る淡い指の先、B：藍の鉤＝爪先）
def find_hooks(z, rp, bpts):
    """藍の鉤の候補。藍の線の骨格の成分のうち、淡い面の中で終わる端（自由端）を持つもの。
    小さな成分（骨格の画素数 ≤ hook_small_component_px：∩形の弧）は 1 つの鉤とし、弧の画素のうち船に最も近い向きへ出た点を鉤の先とする
    （鉤の先の太い点は骨格が小さな輪になり、端点にならないことがある）。弧＝自由端から骨格をたどり、鉤の先で切った折れ線（先から逆向き）。
    大きな成分（色面の縁の線）は、自由端ごとに 1 つの鉤とし、自由端を鉤の先、そこから hook_trace_ref_px たどった折れ線を弧とする。座標は原画。"""
    off = z["off"]
    S = z["line_S"]
    n, lab, st, _ = cv2.connectedComponentsWithStats(S.astype(np.uint8), connectivity=8)
    groups = {}
    fmin = float(rp["line"]["free_end_pale_fraction"])
    for x, y, f in z["line_ends"]:
        groups.setdefault(int(lab[y, x]), []).append((x, y, f))
    hooks = []
    small = int(rp["hook_small_component_px"])
    for cid in sorted(groups):
        free = sorted((x, y) for x, y, f in groups[cid] if f >= fmin)
        if not free:
            continue
        if st[cid, 4] <= small:
            ys, xs = np.nonzero(lab == cid)
            P = np.stack([xs, ys], -1).astype(np.float64) + off
            ctr = P.mean(0)
            k = int(np.argmin(np.hypot(bpts[:, 0] - ctr[0], bpts[:, 1] - ctr[1])))
            nb = bpts[k] - ctr
            nb = nb / max(1e-9, float(np.hypot(*nb)))
            tip = P[int(np.argmax(P @ nb))]
            tr_ = trace_line(S, free[0], float(small) * 1.5) + off
            i_tip = int(np.argmin(np.hypot(tr_[:, 0] - tip[0], tr_[:, 1] - tip[1])))
            arc = tr_[:i_tip + 1][::-1] if i_tip > 0 else tr_
            if float(np.hypot(*(arc[0] - tip))) > 3.0:
                arc = np.concatenate([tip[None], arc], 0)
            hooks.append({"end": tip, "ends": np.array(free, np.float64) + off, "arc": arc, "component_px": int(st[cid, 4]), "small": True})
        else:
            for e in free:
                arc = trace_line(S, e, float(rp["hook_trace_ref_px"])) + off
                hooks.append({"end": np.array(e, np.float64) + off, "ends": np.array([e], np.float64) + off, "arc": arc,
                              "component_px": int(st[cid, 4]), "small": False})
    return hooks


def right_reading(claws, Z, rp, boat_ref, step, cw):
    """各爪（右側、主浪の over_indigo）の頭の藍の鉤を探す。爪と鉤の組は、読みAの根元から鉤の弧までの距離が hook_search_radius_ref_px
    以内で、鉤の弧の重心が読みAの根元より先端の側へ長さの hook_max_t_frac 以上出ていないものの中から、距離の短い順に 1 対 1 で決める。"""
    by, bx = np.nonzero(boat_ref)
    bpts = np.stack([bx, by], -1).astype(np.float64)
    out = {}
    hook_stats = {}
    for zid in ("right", "main"):
        z = Z[zid]
        hooks = find_hooks(z, rp, bpts)
        cl = [c for c in claws if c["zone"] == zid and (zid == "right" or c["over_indigo"])]
        pairs = []
        for i, c in enumerate(cl):
            rA, tA, L = c["root_abs"], c["tip_abs"], c["length"]
            u = (tA - rA) / max(1e-9, float(np.hypot(*(tA - rA))))
            for j, h in enumerate(hooks):
                t = float((h["arc"].mean(0) - rA) @ u)
                dr = float(np.min(np.hypot(h["arc"][:, 0] - rA[0], h["arc"][:, 1] - rA[1])))
                dt = float(np.min(np.hypot(h["arc"][:, 0] - tA[0], h["arc"][:, 1] - tA[1])))
                Rh, tf = float(rp["hook_search_radius_ref_px"]), float(rp["hook_max_t_frac"])
                # 頭（鉤のある端）は読みAの根元の側にあることが多いが、先端の側にある爪もあるので両方を見る
                if dr <= Rh and t <= tf * L:
                    pairs.append((dr, i, j, t, "rootA"))
                if dt <= Rh and t >= (1.0 - tf) * L:
                    pairs.append((dt, i, j, t, "tipA"))
        pairs.sort()
        ci, hj = {}, set()
        for d, i, j, t, end_ in pairs:
            if i in ci or j in hj:
                continue
            ci[i] = (j, d, t, end_)
            hj.add(j)
        hook_stats[zid] = {"hooks": len(hooks), "small_arcs": sum(1 for h in hooks if h["small"]), "matched": len(ci),
                           "hooks_list": [{"end_ref": rnd(h["end"], 1), "ends_ref": rnd(h["ends"], 1), "small_arc": h["small"],
                                           "component_px": h["component_px"], "arc_ref": rnd(h["arc"], 1),
                                           "matched_claw_index": next((i for i, v in ci.items() if v[0] == j), None)} for j, h in enumerate(hooks)]}
        for i, c in enumerate(cl):
            rA, tA, L = c["root_abs"], c["tip_abs"], c["length"]
            u = (tA - rA) / max(1e-9, float(np.hypot(*(tA - rA))))
            k = int(np.argmin(np.hypot(bpts[:, 0] - rA[0], bpts[:, 1] - rA[1])))
            nb = bpts[k] - rA
            nb = nb / max(1e-9, float(np.hypot(*nb)))
            rec = {"boat_dir": nb, "boat_point": bpts[k], "hook": None,
                   "ctx_tipA": end_context(z, tA, int(rp["end_context_radius_ref_px"])),
                   "ctx_rootA": end_context(z, rA, int(rp["end_context_radius_ref_px"]))}
            if i in ci:
                j, d, t, end_ = ci[i]
                h = hooks[j]
                arc = h["arc"]
                kk = min(int(rp["hook_end_tangent_px"]), len(arc) - 1)
                tan = arc[0] - arc[kk] if kk > 0 else np.zeros(2)
                tan = tan / max(1e-9, float(np.hypot(*tan)))
                # 鉤の曲がり：鉤の先へ向かう向き（弧を逆にたどる）での曲がり角の和（画面で時計回りが正）
                A_, _ = resample(arc[::-1], 4.0) if len(arc) >= 2 else (arc, None)
                turn = float(np.sum(turning_deg(A_))) if len(A_) >= 3 else 0.0
                rootB = tA if end_ == "rootA" else rA
                chB = h["end"] - rootB
                chB = chB / max(1e-9, float(np.hypot(*chB)))
                rec["hook"] = {"end": h["end"], "arc": arc, "end_tangent": tan, "turn_deg": turn, "dist_to_head_end": d, "head_end": end_,
                               "t_frac": t / max(L, 1e-9), "chord_B": chB, "small_arc": h["small"]}
            rec["toward_boat_A"] = bool(float(u @ nb) > 0)
            rec["cos_boat_A"] = float(u @ nb)
            if rec["hook"]:
                rec["cos_boat_B"] = float(rec["hook"]["chord_B"] @ nb)
                rec["toward_boat_B"] = bool(rec["cos_boat_B"] > 0)
                rec["hook_end_cos_boat"] = float(rec["hook"]["end_tangent"] @ nb)
            c["reading"] = rec
            out.setdefault(zid, []).append(c)
    out["hook_stats"] = hook_stats
    return out


def apply_reading_B(c, step):
    """右側の爪の主の読みを B（藍の鉤＝爪先）にする。根元＝鉤のない側の端（多くは読み A の先端＝尖る指の先）、先端＝鉤の先。
    中心線＝淡い指の中心線を根元から頭の端までたどり、頭の端から鉤の先まで直線でつないだもの。幅は淡い指の部分で測る。"""
    hk = c["reading"]["hook"]
    off = c["off"]
    A = {k: c[k] for k in ("Cr", "tr", "wid", "root_w", "mid_w", "tip_w", "tip_ang", "root_abs", "tip_abs", "joints", "joint_dev",
                           "seg_ratio", "bend", "length", "poly")}
    c["reading_A"] = A
    LA = float(c["tr"][-1])
    if hk["head_end"] == "rootA":  # 頭が読みAの根元の側：読みAの中心線を逆にたどり、根元から鉤の先へつなぐ
        Cpart, head = c["Cr"][::-1], c["root_abs"]
        widA_rev, trA_rev = c["wid"][::-1], LA - c["tr"][::-1]
    else:  # 頭が読みAの先端の側：読みAの中心線のまま、先端から鉤の先へつなぐ
        Cpart, head = c["Cr"], c["tip_abs"]
        widA_rev, trA_rev = c["wid"], c["tr"]
    link, _ = resample(np.stack([head - off, hk["end"] - off]), step)
    CB = np.concatenate([Cpart, link[1:]], 0)
    CrB, trB = resample(CB, step)
    LB = float(trB[-1])

    def w_along(t):  # 読み B の根元からの弧長 → 淡い指の部分の幅（頭から鉤の先までのつなぎは幅なし）
        if t > LA + 1e-6:
            return float("nan")
        sel = np.abs(trA_rev - t) <= max(step, 0.06 * LA)
        return float(np.median(widA_rev[sel])) if sel.any() else float(np.interp(t, trA_rev, widA_rev))

    def w_at(frac):  # 根元幅・中央幅・先端付近の幅は、淡い指の部分の長さに対する割合（8%・50%・85%）で測る
        return w_along(frac * LA)
    back = min(20.0, 0.35 * LB)
    pb = np.array([np.interp(LB - back, trB, CrB[:, 0]), np.interp(LB - back, trB, CrB[:, 1])])
    v = CrB[-1] - pb
    jid, jdev = joints_of(CrB, 4, 6, 0.04 * LB)
    J = CrB[jid]
    segL = np.hypot(*np.diff(J, axis=0).T)
    widB = np.array([w_along(t) for t in trB])
    c.update({"Cr": CrB, "tr": trB, "wid": widB, "root_w": w_at(0.08), "mid_w": w_at(0.5), "tip_w": w_at(0.85),
              "tip_ang": math.degrees(math.atan2(v[1], v[0])) % 360.0, "root_abs": CrB[0] + off, "tip_abs": CrB[-1] + off,
              "joints": J, "joint_dev": jdev, "seg_ratio": (segL / max(segL.sum(), 1e-9)).tolist(), "bend": turning_deg(J),
              "length": LB, "reading_primary": "B"})


def head_polygon(c, z, rp):
    """読み B の輪郭：読み A の輪郭（淡い指）に、頭（鉤の弧と読み A の根元の円の凸包の中の白・水色）を足した外周。"""
    off = z["off"]
    cls, sky = z["cls"], z["sky"]
    hk = c["reading"]["hook"]
    A = c["reading_A"]
    pts = [hk["arc"][:int(rp["hook_trace_ref_px"])]]
    head = A["root_abs"] if hk["head_end"] == "rootA" else A["tip_abs"]
    r = max(3.0, 0.6 * float(A["root_w"] if hk["head_end"] == "rootA" else A["tip_w"]))
    ang = np.linspace(0, 2 * np.pi, 24, endpoint=False)
    pts.append(np.stack([head[0] + r * np.cos(ang), head[1] + r * np.sin(ang)], -1))
    pts.append(np.asarray(A["poly"], np.float64).reshape(-1, 2) if A["poly"] else A["root_abs"][None])
    P = np.concatenate(pts, 0) - off
    x0, y0 = np.floor(P.min(0)).astype(int) - 2
    x1, y1 = np.ceil(P.max(0)).astype(int) + 3
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(cls.shape[1], x1), min(cls.shape[0], y1)
    hull = cv2.convexHull(np.round(np.concatenate(pts[:2], 0) - off - [x0, y0]).astype(np.int32))
    m = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillConvexPoly(m, hull, 1)
    pale = ((cls[y0:y1, x0:x1] == CLASS_NAMES.index("white")) | (cls[y0:y1, x0:x1] == CLASS_NAMES.index("mizuiro"))) & ~sky[y0:y1, x0:x1]
    m = (m > 0) & pale
    if A["poly"]:
        cv2.fillPoly(m.view(np.uint8), [np.round(np.asarray(A["poly"]) - off - [x0, y0]).astype(np.int32)], 1)
    m = m.astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, T.disk(2))
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return A["poly"]
    cmax = max(cnts, key=cv2.contourArea)
    ap_ = cv2.approxPolyDP(cmax, 1.0, True).reshape(-1, 2).astype(np.float64)
    return (ap_ + off + [x0, y0]).tolist()


# ---------------------------------------------------------------- 主処理
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="Docs/Evidence/ArtFirst/29")
    ap.add_argument("--out", default=None, help="一覧の JSON の出力先（既定は Tools/PaintingTruth/claws29/claw_inventory.json）")
    ap.add_argument("--debug-hooks", default=None, help="（確認用）鉤の候補の一覧を書き出す JSON の場所")
    args = ap.parse_args()
    out_json = os.path.abspath(args.out) if args.out else OUT_JSON
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
    rp = prm["right_reading"]
    boat_ref = T.boat_mask(ochre_ref, polys[rp["boat_roi"]]["points"], ex.get("boat"))
    timings["sky_s"] = round(time.time() - t_start, 2)
    pal = T.load_json(PALETTE_JSON)
    centres = np.array([pal["classes_lloyd_centers_lab"][k] for k in CLASS_NAMES], np.float32)

    # ---- 2〜5. 範囲ごとに骨格化・分割・白い斑の除外・目視の修正
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
    s_max = float(rows_p.get("curve_s_max", 1e9))
    sel_curve = ref_s <= s_max

    def s_of(pt):
        d = np.hypot(ref_curve[:, 0] - pt[0], ref_curve[:, 1] - pt[1])
        d = np.where(sel_curve, d, np.inf)
        k = int(np.argmin(d))
        return float(ref_s[k]), float(d[k])

    # ---- 6. 各爪の計測（読み A）
    claws = []
    step = float(cw["centerline_step_ref_px"])
    rad_ind = int(cw["indigo_side_radius_ref_px"])
    disk_ind = T.disk(rad_ind).astype(bool)
    for zid, z in Z.items():
        for c in z["claws"]:
            measure_claw(c, z, cw, step, s_of, disk_ind, rad_ind)
            c["zd_rows"] = z["zd"]["rows"]
            claws.append(c)
        for wb in z["webs"]:
            z["claws"][wb["claw"]]["webs"].append(wb)

    # ---- 7. 列
    rowinfo = assign_rows(claws, rows_p, ref_curve, ref_s)

    # ---- 8. 右側の爪の読み（A と B を記録し、主の読みを rp["primary"] にする）
    rr = right_reading(claws, Z, rp, boat_ref, step, cw)
    for c in rr.get("right", []):
        c["reading_A_only"] = True
        if rp["primary"] == "B" and c["reading"]["hook"] is not None:
            apply_reading_B(c, step)
            c["poly_A"] = c["poly"]
            c["poly"] = head_polygon(c, Z["right"], rp)
            c["reading_A_only"] = False
    for c in claws:
        c.setdefault("reading_primary", "A")
    if args.debug_hooks:
        T.save_json(os.path.abspath(args.debug_hooks), {zid: hs for zid, hs in rr["hook_stats"].items()})

    # ---- 番号（列の順 → 列の中で s（右側は読み A の根元と先端の中点の x）の順）
    order = {r: i for i, r in enumerate(rows_p["order"])}
    for c in claws:
        if c["zone"] == "main":
            c["order_key"] = c["s_tip"]
        else:
            A = c.get("reading_A", c)
            c["order_key"] = 0.5 * float(A["root_abs"][0] + A["tip_abs"][0])
    claws.sort(key=lambda c: (order[c["row"]], c["order_key"], c["tip_abs"][1]))
    per_row = {}
    for i, c in enumerate(claws, start=1):
        c["num"] = i
        per_row.setdefault(c["row"], []).append(c)
        c["idx_in_row"] = len(per_row[c["row"]])
        c["id"] = "C%03d" % i
        c["row_id"] = "%s%02d" % (rows_p["code"][c["row"]], c["idx_in_row"])

    # ---- 草稿 draft1 の番号との対応（読み A の根元と先端が最も近い草稿の爪）
    d1 = T.load_json(DRAFT1_TIPS)
    D = [(e["id"], np.asarray(e["root_ref"], np.float64), np.asarray(e["tip_ref"], np.float64)) for e in d1["claws"]]
    for c in claws:
        A = c.get("reading_A", c)
        best = None
        for did, r_, t_ in D:
            same = float(np.hypot(*(A["tip_abs"] - t_)) + np.hypot(*(A["root_abs"] - r_)))
            swap = float(np.hypot(*(A["tip_abs"] - r_)) + np.hypot(*(A["root_abs"] - t_)))
            dd = min(same, swap)
            if best is None or dd < best[0]:
                best = (dd, did, swap < same)
        c["draft1"] = {"id": best[1], "distance_ref_px": best[0], "reversed": bool(best[2])} if best and best[0] <= float(prm["draft1_match_ref_px"]) else None

    # ---- 隣との隙間（列の中の並びで次の爪。主の読みの根元・先端）
    for r, lst in per_row.items():
        for a, b in zip(lst[:-1], lst[1:]):
            a["gap_next"] = {"to": b["id"], "root_ref_px": float(np.hypot(*(a["root_abs"] - b["root_abs"]))),
                             "tip_ref_px": float(np.hypot(*(a["tip_abs"] - b["tip_abs"])))}

    # ---- 遮蔽の順序：列の前後（backlog 140：船側の爪が上側の爪より手前）→ 列の中では根元が画面の下ほど手前（仮）
    op = prm["occlusion"]
    front_rows = {r: i for i, r in enumerate(op["row_order_front_first"])}
    front = sorted(claws, key=lambda c: (c["zone"] != "main", front_rows.get(c["row"], 99), -c["root_abs"][1]))
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
        a["touches"] = []
        ay, ax, ga = grown[i]
        for j, b in enumerate(claws):
            if i == j or a["zone"] != b["zone"]:
                continue
            by_, bx_, gb = grown[j]
            y0_, y1_ = max(ay, by_), min(ay + ga.shape[0], by_ + gb.shape[0])
            x0_, x1_ = max(ax, bx_), min(ax + ga.shape[1], bx_ + gb.shape[1])
            if y1_ <= y0_ or x1_ <= x0_:
                continue
            if (ga[y0_ - ay:y1_ - ay, x0_ - ax:x1_ - ax] & gb[y0_ - by_:y1_ - by_, x0_ - bx_:x1_ - bx_]).any():
                a["touches"].append(b["id"])
                if a["occl_rank"] < b["occl_rank"]:
                    a["occludes"].append(b["id"])

    # ---- 代表10形の候補（主浪の 3 列への割り当て → 列の中で k-medoids）
    rep, rep_note = select_representatives(claws, prm["representative"])
    rep_by_len = sorted(rep, key=lambda c: -c["length"])
    rep_by_root = sorted(rep, key=lambda c: -c["root_w"])
    rep_by_mid = sorted(rep, key=lambda c: -c["mid_w"])

    # ---- 船側中央の候補
    centre, boat, bmed = select_centre(claws, prm["boat_side_centre"])

    # ---- 一覧から描き直した爪の和集合と原画の白の IoU（分母 2 通り）
    M, claw_white, iou_rec = compute_iou(Z, claws, sky_ref.shape, fmap)
    timings["iou_s"] = round(time.time() - t_start - timings["sky_s"] - timings["zones_s"], 2)

    # ---- 数と長さの閾値の感度
    main_claws = [c for c in claws if c["zone"] == "main"]
    excluded = [e for z in Z.values() for e in z["excluded"]]
    count_sens = {}
    for thr in prm["counts"]["length_thresholds_ref_px"]:
        count_sens[str(thr)] = {"main": sum(1 for c in main_claws if c.get("reading_A", c)["length"] >= thr),
                                "right": sum(1 for c in claws if c["zone"] == "right" and c.get("reading_A", c)["length"] >= thr)}

    # ---- 出力
    inv = build_inventory(spec, fmap, prm, claws, per_row, excluded, rep, rep_by_len, rep_by_root, rep_by_mid, rep_note, centre, boat, bmed,
                          Z, rowinfo, rr, iou_rec, count_sens)
    T.save_json(out_json, inv)
    figs = make_figures(fmap, ref_rgb, claws, rep, centre, boat, Z, M, claw_white, ev_dir, iou_rec, inv, rowinfo, rr, ref_curve, ref_s, boat_ref)
    zone_stats = {zid: z["stats"] for zid, z in Z.items()}
    metrics = build_metrics(inv, iou_rec, zone_stats, rep, rep_by_len, centre, sky_check, rowinfo, rr, count_sens)
    T.save_json(os.path.join(ev_dir, "metrics.json"), metrics)
    timings["total_s"] = round(time.time() - t_start, 2)
    run = build_run(spec, args, out_json, figs, timings, zone_stats, sky_check, ev_dir)
    T.save_json(os.path.join(ev_dir, "run.json"), run)
    print(json.dumps({"counts": inv["counts"], "iou_main": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in iou_rec["main"].items()},
                      "rows": inv["rows_definition"]["breaks"], "right": inv["right_side_reading"]["summary"],
                      "rep": [(c["id"], c["row"], round(c["length"], 1)) for c in rep],
                      "centre": [(k_, c["id"], c["row_id"]) for k_, c in centre], "timings": timings}, ensure_ascii=False, indent=1))


def select_representatives(claws, rp):
    rep = []
    rows4 = list(rp["candidate_rows"])
    main_claws = [c for c in claws if c["row"] in MAIN_ROWS]
    Lq = float(np.quantile([c["length"] for c in main_claws], float(rp["min_length_quantile"]))) if main_claws else 0.0
    asp = float(rp.get("min_length_over_mid_width", 0.0))
    tl, th = rp.get("taper_range", [0.0, 1e9])
    pools = {r: [c for c in claws if c["row"] == r and c["length"] >= Lq and c["length"] >= asp * c["mid_w"]
                 and tl <= c["mid_w"] / max(c["root_w"], 1e-6) <= th] for r in rows4}
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
    note = "母集団 %d 本（長さ ≥ %.1f px＝主浪の爪の %.0f%% 分位、長さ ≥ %.1f × 中央幅、中央幅／根元幅が %.2f〜%.2f）。列ごとの本数 %s。" % (
        total, Lq, 100 * float(rp["min_length_quantile"]), asp, tl, th, json.dumps(quota, ensure_ascii=False))
    for i, c in enumerate(rep, start=1):
        c["rep"] = "R%d" % i
    return rep, note


def chord_deg(c):
    v = c["tip_abs"] - c["root_abs"]
    return math.degrees(math.atan2(v[1], v[0])) % 360.0


def select_centre(claws, bp):
    brow = [c for c in claws if c["row"] == bp["row"]]
    bmed = float(np.median([c["length"] for c in brow])) if brow else 0.0
    lo, hi = bp["chord_down_deg"]
    boat = sorted([c for c in brow if c["silhouette"] and lo <= chord_deg(c) <= hi and c["length"] >= bmed], key=lambda c: c["s_tip"])
    for i, c in enumerate(boat):
        c["boat_idx"] = i + 1
    if not boat:
        return [], boat, bmed
    m = 0.5 * (len(boat) - 1)
    for c in boat:
        c["centre_checks"] = {"95_root_wider_than_tip": bool(c["root_w"] > c["tip_w"]),
                              "97_tip_downward": bool(lo <= c["tip_ang"] <= hi),
                              "98_chord_downward": bool(lo <= chord_deg(c) <= hi)}
        c["centre_offset"] = abs(c["boat_idx"] - 1 - m)
    ranked = sorted(boat, key=lambda c: (not (c["centre_checks"]["95_root_wider_than_tip"] and c["centre_checks"]["97_tip_downward"]),
                                         c["centre_offset"], c["s_tip"]))
    n = int(bp["candidates"])
    centre = [(k + 1, c) for k, c in enumerate(ranked[:n])]
    return centre, boat, bmed


def compute_iou(Z, claws, shape, fmap):
    Hf, Wf = shape
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
        A = c.get("reading_A", c)  # 描き直しは淡い指（読み A の中心線と幅）で行う。読みに依らない形
        sweep(cf, A["Cr"] + off, A["wid"])
        sweep(cfs, A["Cr"] + off, A["wid"])
        sweep(ca, A["Cr"] + off, A["wid"])
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
    M["body_poly"] = body_poly_mask > 0
    claw_white = M["white"] & ~M["body"]
    nb = ~M["body"]

    def iou(a, b):
        u = (a | b).sum()
        return float((a & b).sum() / u) if u else 0.0

    def cover(a, b):
        return float((a & b).sum() / max(1, b.sum()))

    def prec(a, b):
        return float((a & b).sum() / max(1, a.sum()))

    def block(sel):
        cwh = claw_white & sel
        wh = M["white"] & sel
        out = {
            "denominator_A_claw_white_ref_px": int(cwh.sum()),
            "denominator_B_all_white_ref_px": int(wh.sum()),
            "flat_crest_white_ref_px": int((M["body"] & sel).sum()),
            # 分母 A：波頭の平らな白を除いた白（爪の白）。分子は平らな白の外の部分
            "A_all_parts": iou(M["all"] & nb & sel, cwh),
            "A_all_parts_recall": cover(M["all"] & nb & sel, cwh),
            "A_all_parts_precision": prec(M["all"] & nb & sel, cwh),
            "A_fingers_stems": iou(M["fingers_stems"] & nb & sel, cwh),
            "A_fingers_only": iou(M["fingers"] & nb & sel, cwh),
            "A_outline_polygons": iou(M["regions"] & nb & sel, cwh),
            # 分母 B：平らな白を含む白の全体。分子は一覧の爪の部分だけ（平らな白は描かない）
            "B_all_parts": iou(M["all"] & sel, wh),
            "B_all_parts_recall": cover(M["all"] & sel, wh),
            "B_all_parts_precision": prec(M["all"] & sel, wh),
            "B_fingers_stems": iou(M["fingers_stems"] & sel, wh),
            "B_fingers_only": iou(M["fingers"] & sel, wh),
            "B_outline_polygons": iou(M["regions"] & sel, wh),
            # 記録：分母 B に対し、分子へ平らな白の多角形（一覧の crest_body_white_polygons_ref）も足した値
            "B_all_parts_plus_flat_white_polygons": iou((M["all"] | M["body_poly"]) & sel, wh),
            "reference_whole_skeleton_mat_vs_A": iou(M["mat"] & nb & sel, cwh),
        }
        return out
    zsel = {}
    for zid, z in Z.items():
        m_ = np.zeros((Hf, Wf), bool)
        m_[z["crop"]] = z["zone"]
        zsel[zid] = m_
    rec = {"all_zones": block(zsel["main"] | zsel["right"]) if "right" in zsel else block(zsel["main"])}
    for zid in Z:
        rec[zid] = block(zsel[zid])

    def to_disp(m):
        return T.ref_mask_to_cov(m, fmap) > 0.5
    cw_d, wh_d = to_disp(claw_white), to_disp(M["white"])
    rec["display_all_zones"] = {"A_all_parts": iou(to_disp(M["all"] & nb), cw_d), "A_fingers_only": iou(to_disp(M["fingers"] & nb), cw_d),
                                "B_all_parts": iou(to_disp(M["all"]), wh_d), "B_fingers_only": iou(to_disp(M["fingers"]), wh_d)}
    return M, claw_white, rec


# ---------------------------------------------------------------- 一覧の JSON
def build_inventory(spec, fmap, prm, claws, per_row, excluded, rep, rep_by_len, rep_by_root, rep_by_mid, rep_note, centre, boat, bmed,
                    Z, rowinfo, rr, iou_rec, count_sens):
    cw = prm["claw"]
    rows_p = prm["rows"]
    rp = prm["right_reading"]
    k_disp = fmap.s
    step = float(cw["centerline_step_ref_px"])

    def disp(p):
        return fmap.ref_to_disp(np.asarray(p, np.float64))

    def nz(v, k=1):
        return None if v is None or (isinstance(v, float) and not math.isfinite(v)) else rnd(v, k)
    centre_rank = {c["id"]: k for k, c in centre}
    out_claws = []
    for c in claws:
        off = c["off"]
        J = c["joints"] + off
        vis = []
        if c["trimmed"]:
            vis.append("根元を付け替え：" + c["trimmed"])
        if c["reversed"]:
            vis.append("先端と根元を入れ替え：" + c["reversed"])
        rec = {
            "id": c["id"], "row": c["row"], "row_id": c["row_id"], "zone": c["zone"],
            "backlog_row_item": rows_p["backlog"][c["row"]],
            "draft1_id": c["draft1"]["id"] if c["draft1"] else None,
            "draft1_reversed": bool(c["draft1"]["reversed"]) if c["draft1"] else None,
            "reading": {"A": "A（骨格の向き：尖る白・淡い指の先＝爪先）", "B": "B（藍の鉤＝爪先。既定値・利用者未確認）"}[c["reading_primary"]],
            "source": {"stroke": "auto", "stroke_free": "auto（両端が端点の白）", "manual": "manual（目視で追加）"}[c["kind"]],
            "root_attach": ("白の塊（波頭の平らな白）" if c["root_in_body"] else {"junction": "他の爪の白との分岐", "end": "端点（切り離された白）", "": "手で描いた根元"}.get(c["root_end"], c["root_end"])) if c["reading_primary"] == "A" else "淡い指の尖る先（読みB）",
            "skeleton_edges": c["n_edges"], "cut_by_max_length": c["cut_by_length"], "root_by_width_jump": c["root_by_width_jump"],
            "visual_correction_ja": "／".join(vis),
            "silhouette": c["silhouette"], "over_indigo": c["over_indigo"],
            "root_ref": rnd(c["root_abs"], 1), "tip_ref": rnd(c["tip_abs"], 1),
            "root_display": rnd(disp(c["root_abs"]), 2), "tip_display": rnd(disp(c["tip_abs"]), 2),
            "length_ref_px": rnd(c["length"], 1), "length_display_px": rnd(c["length"] * k_disp, 2),
            "chord_ref_px": rnd(np.hypot(*(c["tip_abs"] - c["root_abs"])), 1), "chord_direction_deg": rnd(chord_deg(c), 1),
            "root_width_ref_px": nz(c["root_w"]), "mid_width_ref_px": nz(c["mid_w"]), "tip_width_ref_px": nz(c["tip_w"]),
            "root_width_display_px": nz(c["root_w"] * k_disp, 2), "mid_width_display_px": nz(c["mid_w"] * k_disp, 2),
            "taper_mid_over_root": nz(c["mid_w"] / max(c["root_w"], 1e-6), 3),
            "tip_direction_deg": rnd(c["tip_ang"], 1), "tip_direction_ja": compass_ja(c["tip_ang"]),
            "s_tip_ref_px": rnd(c["s_tip"], 1), "s_root_ref_px": rnd(c["s_root"], 1), "tip_to_outline_ref_px": rnd(c["d_tip_curve"], 1),
            "row_margin_ref_px": nz(c["row_margin"]) if "row_margin" in c else None,
            "row_near_boundary": c.get("row_near_boundary"),
            "tip_to_sky_ref_px": rnd(c["sky_d"], 1), "tip_indigo_fraction": rnd(c["ind_frac"], 3),
            "edge_ring_fractions": {k: (rnd(v, 3) if k != "n_px" else v) for k, v in c["ring_fractions"].items()} if "ring_fractions" in c else None,
            "occlusion_rank_front_first": c["occl_rank"], "occludes": c["occludes"], "touches": c["touches"],
            "gap_next": ({"to": c["gap_next"]["to"], "root_ref_px": rnd(c["gap_next"]["root_ref_px"], 1),
                          "tip_ref_px": rnd(c["gap_next"]["tip_ref_px"], 1),
                          "root_display_px": rnd(c["gap_next"]["root_ref_px"] * k_disp, 2),
                          "tip_display_px": rnd(c["gap_next"]["tip_ref_px"] * k_disp, 2)} if "gap_next" in c else None),
            "centerline_ref": rnd(c["Cr"] + off, 1),
            "centerline_width_ref_px": [nz(float(v)) for v in c["wid"]],
            "stem_ref": rnd(c["stem_r"] + off, 1), "stem_width_ref_px": rnd(c["stem_w"], 1),
            "base_web": [{"centerline_ref": rnd(wb["Cr"] + off, 1), "width_ref_px": rnd(wb["wid"], 1)} for wb in c["webs"]],
            "joints_ref": rnd(J, 1), "joint_max_deviation_ref_px": rnd(c["joint_dev"], 2),
            "segment_length_ratio": rnd(c["seg_ratio"], 3), "bend_deg_clockwise": rnd(c["bend"], 1),
            "outline_polygon_ref": rnd(c["poly"], 1),
            "rep_cluster_size": c.get("rep_cluster_size"),
        }
        if c.get("rep"):
            rec["representative_candidate"] = c["rep"]
        if c.get("boat_idx"):
            rec["boat_side_silhouette_down_index"] = c["boat_idx"]
            rec["centre_checks"] = c["centre_checks"]
        if c["id"] in centre_rank:
            rec["boat_side_centre_candidate_rank"] = centre_rank[c["id"]]
        if "reading" in c:
            g = c["reading"]
            hk = g["hook"]
            rr_ = {"boat_direction_deg": rnd(math.degrees(math.atan2(g["boat_dir"][1], g["boat_dir"][0])), 1),
                   "nearest_boat_point_ref": rnd(g["boat_point"], 1),
                   "tip_A_context": {k: rnd(v, 3) for k, v in g["ctx_tipA"].items()},
                   "root_A_context": {k: rnd(v, 3) for k, v in g["ctx_rootA"].items()},
                   "cos_to_boat_A": rnd(g["cos_boat_A"], 3), "toward_boat_A": g["toward_boat_A"],
                   "hook_found": hk is not None}
            if hk is not None:
                rr_.update({"hook_end_ref": rnd(hk["end"], 1), "hook_arc_ref": rnd(hk["arc"], 1),
                            "hook_end_tangent_deg": rnd(math.degrees(math.atan2(hk["end_tangent"][1], hk["end_tangent"][0])) % 360.0, 1),
                            "hook_end_tangent_ja": compass_ja(math.degrees(math.atan2(hk["end_tangent"][1], hk["end_tangent"][0]))),
                            "hook_turn_deg_clockwise": rnd(hk["turn_deg"], 1), "hook_to_head_end_ref_px": rnd(hk["dist_to_head_end"], 1),
                            "head_end": {"rootA": "読みAの根元の側", "tipA": "読みAの先端の側"}[hk["head_end"]],
                            "hook_position_along_A": rnd(hk["t_frac"], 3),
                            "cos_to_boat_B": rnd(g["cos_boat_B"], 3), "toward_boat_B": g["toward_boat_B"],
                            "hook_end_tangent_cos_to_boat": rnd(g["hook_end_cos_boat"], 3)})
            if c["zone"] == "right":
                A = c.get("reading_A")
                if A is not None:
                    rr_["reading_A"] = {"root_ref": rnd(A["root_abs"], 1), "tip_ref": rnd(A["tip_abs"], 1), "length_ref_px": rnd(A["length"], 1),
                                        "root_width_ref_px": rnd(A["root_w"], 1), "mid_width_ref_px": rnd(A["mid_w"], 1), "tip_width_ref_px": rnd(A["tip_w"], 1),
                                        "tip_direction_deg": rnd(A["tip_ang"], 1), "tip_direction_ja": compass_ja(A["tip_ang"]),
                                        "centerline_ref": rnd(A["Cr"] + off, 1), "joints_ref": rnd(A["joints"] + off, 1),
                                        "segment_length_ratio": rnd(A["seg_ratio"], 3), "bend_deg_clockwise": rnd(A["bend"], 1),
                                        "outline_polygon_ref": rnd(A["poly"], 1)}
                rec["right_side_reading"] = rr_
            else:
                keep = ("tip_A_context", "root_A_context", "hook_found", "hook_end_ref", "hook_arc_ref", "hook_to_head_end_ref_px", "head_end", "hook_position_along_A",
                        "hook_end_tangent_deg", "hook_end_tangent_ja")
                rec["type_I_head_hook_record"] = {k: v for k, v in rr_.items() if k in keep}
        out_claws.append(rec)
    row_counts = {r: len(per_row.get(r, [])) for r in rows_p["order"]}
    sil_counts = {r: sum(1 for c in per_row.get(r, []) if c["silhouette"]) for r in rows_p["order"]}
    ind_counts = {r: sum(1 for c in per_row.get(r, []) if c["over_indigo"]) for r in rows_p["order"]}
    n_main = sum(row_counts[r] for r in MAIN_ROWS)
    n_webs = sum(len(c["webs"]) for c in claws)
    ex_reasons = {}
    for e in excluded:
        key = e["reason_ja"].split("（")[0].split("：")[0]
        ex_reasons[key] = ex_reasons.get(key, 0) + 1
    # 右側の読みのまとめ
    R = rr.get("right", [])
    hooks = [c for c in R if c["reading"]["hook"] is not None]
    med = lambda v: float(np.median(v)) if len(v) else None  # noqa: E731
    main_tip_ctx = [end_context(Z["main"], c.get("reading_A", c)["tip_abs"], int(rp["end_context_radius_ref_px"])) for c in claws if c["zone"] == "main"]
    summary = {
        "right_claws": len(R), "hook_found": len(hooks),
        "toward_boat_A": sum(1 for c in R if c["reading"]["toward_boat_A"]),
        "away_from_boat_A": sum(1 for c in R if not c["reading"]["toward_boat_A"]),
        "tip_direction_A_right_or_down_right": sum(1 for c in R if compass_ja(c.get("reading_A", c)["tip_ang"]) in ("右", "右下")),
        "toward_boat_B": sum(1 for c in hooks if c["reading"]["toward_boat_B"]),
        "hook_end_tangent_toward_boat": sum(1 for c in hooks if c["reading"]["hook_end_cos_boat"] > 0),
        "hook_at_rootA_side": sum(1 for c in hooks if c["reading"]["hook"]["head_end"] == "rootA"),
        "hook_at_tipA_side": sum(1 for c in hooks if c["reading"]["hook"]["head_end"] == "tipA"),
        "tip_A_context_median": {"line": med([c["reading"]["ctx_tipA"]["line"] for c in R]), "indigo": med([c["reading"]["ctx_tipA"]["indigo"] for c in R])},
        "main_tip_context_median": {"line": med([x["line"] for x in main_tip_ctx]), "indigo": med([x["indigo"] for x in main_tip_ctx]),
                                    "line_ge_0.3": sum(1 for x in main_tip_ctx if x["line"] >= 0.3), "n": len(main_tip_ctx)},
        "tip_A_line_ge_0.3": sum(1 for c in R if c["reading"]["ctx_tipA"]["line"] >= 0.3),
        "primary": rp["primary"],
    }
    TI = rr.get("main", [])
    summary_main_type_I = {"over_indigo_claws": len(TI), "head_hook_found": sum(1 for c in TI if c["reading"]["hook"] is not None),
                           "ids": [c["id"] for c in TI]}
    ri = rowinfo
    return {
        "schema": "GreatWave.ClawInventory/1",
        "number": "29",
        "version": VERSION,
        "status_ja": "完成版（番号29 の続き、CP2 用）。自動抽出に規則（白い斑の除外）と agent の目視修正（af29_params.json の corrections）を加えた。利用者は未確認。列の境目、右側の読み（B）、代表10形、船側中央の爪、遮蔽の順序（列の前後は backlog 140、列の中は仮）は CP2 で利用者が確かめる。",
        "reference": {"path": spec["reference"]["path"], "sha256": spec["reference"]["sha256"], "width": spec["reference"]["width"], "height": spec["reference"]["height"]},
        "truth_version": spec["version"],
        "coordinate_convention_ja": "*_ref は高解像度原画の画素中心整数系（x 右、y 下）。*_display は番号23 の表示フレーム（1920×1080、x_d = %.6f·(x_r + 0.5) − 0.5 + %.5f、y_d = %.6f·(y_r + 0.5) − 0.5）。向きは画面座標で 0°＝右、90°＝下。" % (fmap.s, fmap.ox, fmap.s),
        "reference_model_used": False,
        "draft1": {"commit": DRAFT_COMMIT, "file": "Tools/PaintingTruth/claws29/claw_inventory_draft.json（コミット %s。完成版では削除し、番号と根元・先端だけを af29_draft1_tips.json に残した）" % DRAFT_COMMIT,
                   "matched": sum(1 for c in claws if c["draft1"]), "unmatched_final_ids": [c["id"] for c in claws if not c["draft1"]],
                   "draft_ids_without_final": sorted(set(e["id"] for e in T.load_json(DRAFT1_TIPS)["claws"]) - set(c["draft1"]["id"] for c in claws if c["draft1"]))},
        "zones": [{"id": zd["id"], "name_ja": zd["name_ja"], "points_ref": zd["points"], "rows": zd["rows"], "body_open_radius_ref_px": zd["body_open_radius_ref_px"]} for zd in prm["zones"]],
        "definitions_ja": {
            "claw": "白（番号23 の色分けで white、空と船の黄土を除く。右側の範囲だけは white と mizuiro を合わせる。zones の mask_classes）の領域を Zhang–Suen で骨格化し、とげを除き、枝を分岐でなめらかに続くストローク（折れ角 ≤ %.0f°の組を貪欲に対にする）にまとめた後、端点（先端）を持つストローク。水色の面の中の白い斑（指の輪郭のまわり %d px の白以外の画素のうち、藍の線 ≤ %.2f かつ水色 ≥ %.2f）は爪に数えず、骨格は根元の白（web）として残す。" % (
                float(prm["stroke"]["max_deflect_deg"]), int(cw["pale_speck"]["ring_ref_px"]), float(cw["pale_speck"]["max_line_fraction"]), float(cw["pale_speck"]["min_mizuiro_fraction"])),
            "reading": "主浪の爪はすべて読みA（骨格の向き：ストロークの端点＝先端。目視で入れ替えた爪は visual_correction_ja）。右側の爪は、頭に藍の鉤が見つかった爪を読みB（藍の鉤＝爪先。根元＝淡い指の尖る先、先端＝鉤の自由端のうち船に最も近い端）とし、読みAの値を right_side_reading.reading_A に残す（right_reading.primary = %s、既定値・利用者未確認）。" % rp["primary"],
            "root": "読みA：中心線の根元側の端。ストロークの根元側の端が分岐なら、その分岐の内接円の縁（他の爪の白から出る所）。先端からたどって白の塊（範囲ごとの半径の円で開いて残る厚い白＝波頭の平らな白）に入るなら、その点。さらに、半幅が先端側の半分の中央値の %.1f 倍（下限 %.1f px）を超える所より根元側は含めない。いずれも先端に近い方を採る。stem_ref は根元より根元側のストロークのうち、白の塊の外の部分（幹）。" % (float(cw["width_jump_ratio"]), float(cw["width_jump_floor_ref_px"])),
            "base_web": "根元の白。どの爪のストロークにも半分以上含まれない骨格の枝（先端の見えない白い舌、爪の間をつなぐ白、長さで切った幹の残り、白い斑）の、白の塊の外の部分。枝の端に最も近い爪に付ける。爪の数には入れない。",
            "width": "白の距離変換の 2 倍（藍の輪郭線と水色の陰は含まない）。根元幅は弧長 8%%、中央幅は 50%%、先端付近の幅は 85%% の位置（±max(%.0f px, 6%%) の中央値）。右側の読みBでは淡い指の部分の長さに対する割合（8%%・50%%・85%%）で淡い指の幅を測り、頭から鉤の先までのつなぎの区間の centerline_width_ref_px は幅なし（null）。" % step,
            "tip_direction": "先端から %.0f px（長さの 35%% が短ければそちら）戻った点から先端への向き。chord_direction_deg は根元から先端への向き。" % float(cw["tip_direction_back_ref_px"]),
            "row": "主浪の爪は、先端から番号23 の包絡版の外周（131→132→72、s ≤ %.0f）への最近点の弧長 s と、先端の x で決める。x < x_split なら上側（波頂の左で藍の面の上縁に並ぶ爪）。それ以外は s < 境目1 が上側、境目1〜境目2 が途中、境目2 以上が船側。境目は、外周の接線（弧長 ±%.0f px の 2 点を結ぶ向き）が波頂の後で初めて %s°・%s° を超える所（特徴点）から ±%.0f px の中で、爪の先端の s の並びの最も広い隙間の中央に置く。x_split も %.0f ± %.0f px の中で、唇の下面の左端の爪と左の群の爪の先端の x の最も広い隙間の中央に置く。右側の範囲の爪はすべて右側。" % (
                float(rows_p["curve_s_max"]), float(rows_p["feature_tangent_window_ref_px"]), rows_p["feature_angles_deg"]["上側|途中"], rows_p["feature_angles_deg"]["途中|船側"],
                float(rows_p["snap_window_ref_px"]), float(rows_p["left_split_x_ref"]), float(rows_p["left_split_snap_window_ref_px"])),
            "row_margin": "列を決めた量（s か x）から最も近い境目までの距離。%.0f px 未満は row_near_boundary。" % float(rows_p["near_boundary_ref_px"]),
            "silhouette": "先端から空まで %.0f px 以内（原画の外輪郭に出ている爪）。" % float(cw["silhouette_sky_dist_ref_px"]),
            "over_indigo": "空から %.0f px より遠く、先端のまわり（半径 %d px）の白以外の半分以上が藍の爪（藍の面へ垂れる爪。右側の爪と同じ描き方：頭の藍の鉤と、藍の中へ尖る白い指）。" % (float(cw["silhouette_sky_dist_ref_px"]), int(cw["indigo_side_radius_ref_px"])),
            "occlusion": "遮蔽の順序（番号1 が最も手前）。主浪は列の前後を backlog 140『船へ曲がる端の爪が上側の爪より手前』に合わせて 船側 → 途中 → 上側 とし、同じ列の中では根元が画面の下にある爪ほど手前（仮、原画の線の重なりからは判定していない）。右側の波は主浪より後ろに番号を振り、根元が下ほど手前（仮）。touches は同じ範囲で輪郭が %.0f px 以内に接する爪、occludes はそのうちこの順で後ろになる爪。" % float(cw["occlusion_touch_ref_px"]),
            "gap_next": "同じ列の中で並び（主浪は s、右側は読みAの根元と先端の中点の x）の次の爪までの、根元どうし・先端どうしの距離（主の読み）。",
            "joints": "中心線に最遠点の挿入で置いた関節（根元と先端を含む %d〜%d 点）。ずれが長さの %.0f%% 以下になる最小の点数。bend_deg_clockwise は内側の関節での曲がり角（画面で時計回りが正）。" % (int(cw["joints_min"]), int(cw["joints_max"]), 100 * float(cw["joints_tol_frac_of_length"])),
            "redraw_for_iou": "一覧の読みAの中心線と幅（指）、stem_ref と stem_width_ref_px（幹）、base_web（根元の白）だけから、各標本に直径＝幅の円を置き、隣の標本を同じ太さの線でつないで塗る。分母は 2 通り：A＝波頭の平らな白（白の塊）を除いた白（爪の白）、B＝平らな白を含む白の全体。",
            "outline_polygon": "読みA：根元→先端の指（幹は含まない）に沿った内接円の和と白の共通部分の外周（%.1f px で単純化）。右側の読みB：それに、鉤の弧（端から %.0f px）と読みAの根元の円の凸包の中の白・水色（頭）を足した外周。" % (float(cw["polygon_eps_ref_px"]), float(rp["hook_trace_ref_px"])),
        },
        "rows_definition": {
            "features_s": {k: rnd(v, 1) for k, v in ri["features_s"].items()},
            "breaks": {"s": {k: rnd(v, 1) for k, v in ri["breaks_s"].items()}, "gap_pairs_s": ri["gap_pairs_s"], "x_split_ref": rnd(ri["x_split"], 1), "x_split_gap_pair": ri["x_split_gap"]},
            "tangent_window_ref_px": ri["tangent_window"],
            "sensitivity_row_changes": ri["sensitivity_row_changes"],
            "root_based_disagreements": [c["id"] for c in ri["root_based_disagreements"]],
            "window_alternatives": ri["window_alternatives"],
            "near_boundary_ids": [c["id"] for c in ri["near_boundary"]],
            "draft1_breaks_ja": "草稿 draft1：s 520・1150、x 1480（目視の暫定値）",
        },
        "right_side_reading": {"summary": summary, "main_wave_over_indigo_head_hooks": summary_main_type_I,
                               "hooks": {zid: {k: v for k, v in hs.items() if k != "hooks_list"} | {"hook_ends_ref": [h["end_ref"] for h in hs["hooks_list"]],
                                                                                                    "unmatched_hook_ends_ref": [h["end_ref"] for h in hs["hooks_list"] if h["matched_claw_index"] is None]}
                                         for zid, hs in rr["hook_stats"].items()},
                               "note_ja": "右側の爪は、白い斜面の縁に並ぶ『頭（淡い面の上に藍の∩形の鉤）＋藍の中へ尖る淡い指』の形。読みA（尖る指の先＝爪先）では多くが右下（船から離れる向き）で、backlog 240『先が船側へ曲がる』と逆になる。読みB（藍の鉤＝爪先）では、根元＝尖る指の先、先端＝鉤の船側の自由端になり、根元から先端への向きが船の側になる。主浪の爪の先端は藍の線で縁取られ鉤で終わる（先端のまわりの白以外のうち藍の線の割合の中央値は main_tip_context_median）。読みAの右側の先端は藍の線でなく藍の面に接する。主浪の左の群（over_indigo）も右側と同じ描き方で、一覧では読みAのまま（CP2 で確かめる）。"},
        "counts": {"total": len(claws), "main_wave_total": n_main, "right_side_total": row_counts.get("右側", 0), "by_row": row_counts,
                   "silhouette_by_row": sil_counts, "over_indigo_by_row": ind_counts,
                   "excluded_candidates": len(excluded), "excluded_by_reason": ex_reasons, "base_web_pieces": n_webs,
                   "by_min_length_ref_px": count_sens,
                   "backlog_139_ja": "backlog 139（B022-03『爪形｜群の連続生長』）の『配置した約150本』は、主浪の爪の群（B017・B020・B022）の項目。右側の波の爪は B055（backlog 240〜256）で別の群。150 と比べるのが主浪だけか、右側を含む全体かは backlog に書かれていない（CP2 で確認）。",
                   "note_ja": "total は端点（見える先端）を持つ爪。main_wave_total は主浪の 3 列（上側・途中・船側）、right_side_total は右側の波。base_web_pieces（根元の白）と excluded_candidates（短い・範囲の縁・白い斑・目視で除外）は数に入れない。by_min_length_ref_px は読みAの長さの下限を変えたときの本数（下限 14 px が一覧）。"},
        "representative_candidates": {
            "ids": [c["id"] for c in rep], "labels": {c["id"]: c["rep"] for c in rep},
            "order_by_length_long_first": [c["id"] for c in rep_by_len],
            "order_by_root_width_wide_first": [c["id"] for c in rep_by_root],
            "order_by_mid_width_wide_first": [c["id"] for c in rep_by_mid],
            "selection_ja": prm["representative"]["note_ja"] + " " + rep_note,
        },
        "boat_side_centre_candidates": [
            {"rank": k_, "id": c["id"], "row_id": c["row_id"], "boat_side_silhouette_down_index": c["boat_idx"], "of": len(boat),
             "checks": c["centre_checks"], "root_width_ref_px": rnd(c["root_w"], 1), "tip_width_ref_px": rnd(c["tip_w"], 1),
             "length_ref_px": rnd(c["length"], 1), "tip_direction_ja": compass_ja(c["tip_ang"])} for k_, c in centre],
        "boat_side_silhouette_down_order": [c["id"] for c in boat],
        "boat_side_centre_rule_ja": prm["boat_side_centre"]["note_ja"] + " 船側の長さの中央値 %.1f px。" % bmed,
        "representative_and_centre_details": [
            {"id": c["id"], "labels": ([c["rep"]] if c.get("rep") else []) + (["船側中央の候補%d" % centre_rank[c["id"]]] if c["id"] in centre_rank else []),
             "row": c["row"], "row_id": c["row_id"],
             "length_ref_px": rnd(c["length"], 1), "root_width_ref_px": rnd(c["root_w"], 1), "mid_width_ref_px": rnd(c["mid_w"], 1),
             "tip_width_ref_px": rnd(c["tip_w"], 1), "tip_direction_deg": rnd(c["tip_ang"], 1),
             "centerline_ref": rnd(c["Cr"] + c["off"], 1), "joints_ref": rnd(c["joints"] + c["off"], 1), "n_joints": int(len(c["joints"])),
             "segment_length_ratio": rnd(c["seg_ratio"], 3), "bend_deg_clockwise": rnd(c["bend"], 1)}
            for c in (rep + [c for _, c in centre if c["id"] not in {r_["id"] for r_ in rep}])],
        "crest_body_white_polygons_ref": {zid: [rnd(p_, 1) for p_ in z["body_polys"]] for zid, z in Z.items()},
        "claws": out_claws,
        "excluded_candidates": excluded,
    }


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
    """原画の矩形（高解像度 px）を W×H に収める（縦横同倍率、余白は暗い灰）。戻り値 (画像, 写像)。"""
    k = min(W / w, H / h)
    cx, cy = x0 + w / 2.0, y0 + h / 2.0
    M = np.array([[k, 0, W / 2.0 - k * cx], [0, k, H / 2.0 - k * cy]], np.float64)
    img = cv2.warpAffine(ref_rgb, M, (W, H), flags=cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT, borderValue=(40, 40, 40))
    return img, M


def _pts(M, P):
    P = np.asarray(P, np.float64)
    return (P @ M[:, :2].T + M[:, 2])


def draw_claws(img, M, claws, rep_ids, centre_ids, label_size, show_ids=True, line=2, dim=0.55, webs=True, only_rows=None, flag_near=False):
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
        if flag_near and c.get("row_near_boundary"):
            cv2.circle(over, (int(round(t[0])), int(round(t[1]))), max(6, 3 * line + 4), (255, 255, 255), max(1, line), cv2.LINE_AA)
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
    P = np.concatenate([np.asarray(c["poly"]).reshape(-1, 2) for c in claws if c["poly"]] + [c["Cr"] + c["off"] for c in claws], 0)
    x0, y0 = P[:, 0].min() - pad, P[:, 1].min() - pad
    return x0, y0, P[:, 0].max() - x0 + pad, P[:, 1].max() - y0 + pad


RESERVED = [tuple(v) for v in ROW_COLOURS.values()] + [(255, 255, 255), (0, 0, 0), (255, 255, 0), (0, 255, 255), (40, 40, 40), (120, 120, 120)]


def make_figures(fmap, ref_rgb, claws, rep, centre, boat, Z, M, claw_white, ev_dir, iou_rec, inv, rowinfo, rr, ref_curve, ref_s, boat_ref):
    rep_ids = {c["id"] for c in rep}
    centre_ids = {c["id"]: k for k, c in centre}
    row_counts = inv["counts"]["by_row"]
    n_main = inv["counts"]["main_wave_total"]
    out = {}
    extra = ["黄の太線＝代表10形の候補（R1〜R10）、水色の太線＝船側中央の候補（中1〜中%d）" % len(centre),
             "白線＝中心線、黒点＝根元、色点＝先端、灰の細線＝根元の白（web、数に入れない）。右側は読みB（藍の鉤＝爪先）",
             "番号は一覧の番号（C001… の数字部分）。主浪 %d 本＋右側 %d 本（完成版 %s）" % (n_main, row_counts.get("右側", 0), VERSION)]
    # 1) 表示フレーム全体（原画視点 1920×1080、番号23 の写像）
    img = fmap.warp_to_disp(ref_rgb, cv2.INTER_LINEAR)
    img[:, :fmap.x0] = 40
    img[:, fmap.x1 + 1:] = 40
    over = draw_claws(img, fmap.M, claws, rep_ids, centre_ids, 11, show_ids=True, line=1, dim=0.8, webs=False)
    over = legend(over, row_counts, ["番号29 爪の一覧 完成版（%s）：原画視点 1920×1080" % VERSION] + extra, size=18)
    p = os.path.join(ev_dir, "29_claws_overlay_display.png")
    T.save_png_reserved(p, over, RESERVED)
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
    T.save_png_reserved(p, over, RESERVED)
    out["overlay_crest"] = p
    # 3) 拡大：船側、途中、上側、右側
    for name, sel, lsize in (("boatside", ("船側",), 20), ("middle", ("途中",), 20), ("upper", ("上側",), 18), ("right", ("右側",), 20)):
        sub = [c for c in claws if c["row"] in sel]
        if not sub:
            continue
        x0, y0, w, h = _bbox_of(sub, 30)
        img, Mv = _view(ref_rgb, x0, y0, w, h)
        over = draw_claws(img, Mv, claws, rep_ids, centre_ids, lsize, line=2, dim=0.85)
        over = legend(over, row_counts, ["拡大：%s（高解像度原画 x %d〜%d、y %d〜%d）。ほかの列の爪も色を変えて描いた" % ("・".join(sel), x0, x0 + w, y0, y0 + h)] + extra[:2], size=20)
        p = os.path.join(ev_dir, "29_claws_zoom_%s.png" % name)
        T.save_png_reserved(p, over, RESERVED)
        out["zoom_" + name] = p
    # 4) 骨格（とげの除去の前後）
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
    # 5) 和集合の IoU（分母 2 通り）
    out["union_iou"] = iou_figure(Z, M, claw_white, iou_rec, ev_dir)
    # 6) 代表10形と船側中央の候補の一覧
    cards = rep + [c for _, c in centre if c["id"] not in rep_ids]
    out["representative_sheet"] = representative_sheet(ref_rgb, cards, rep, centre, ev_dir)
    # 7) 右側の爪の読み（A と B）
    out["right_reading"] = right_reading_figure(ref_rgb, claws, rr, inv, boat_ref, ev_dir)
    # 8) 列の境目と安定性
    out["rows"] = rows_figure(ref_rgb, claws, rowinfo, ref_curve, ref_s, inv, ev_dir)
    # 9) CP2 で利用者が中央の爪を指定し、代表10形を確かめるための図
    out["cp2_nomination"] = cp2_figure(ref_rgb, claws, rep, centre, boat, inv, ev_dir)
    return out


def iou_figure(Z, M, claw_white, iou_rec, ev_dir):
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
    img = _text(img, [(20, 10, "一覧から描き直した和集合と原画の白：白＝指で一致、明るい灰＝幹・根元の白で一致、赤＝描き直しだけ、水色＝原画の爪の白だけ、灰＝波頭の平らな白", (255, 255, 255), (0, 0, 0)),
                      (20, 38, "主浪（上）IoU　分母A（平らな白を除く）：指＋幹＋根元の白 %.3f、指＋幹 %.3f、指だけ %.3f ／ 分母B（平らな白を含む）：%.3f、%.3f、%.3f" % (
                          a["A_all_parts"], a["A_fingers_stems"], a["A_fingers_only"], a["B_all_parts"], a["B_fingers_stems"], a["B_fingers_only"]), (255, 255, 255), (0, 0, 0)),
                      (20, 66, "（分母B で灰の部分は分子に入らず、すべて『原画の白だけ』になる。分子に平らな白の多角形も足すと %.3f＝記録）" % a["B_all_parts_plus_flat_white_polygons"], (255, 255, 255), (0, 0, 0)),
                      (20, 712, "右側（下、白と水色を合わせた面）IoU　分母A：%.3f、%.3f、%.3f ／ 分母B：%.3f、%.3f、%.3f" % (
                          b["A_all_parts"], b["A_fingers_stems"], b["A_fingers_only"], b["B_all_parts"], b["B_fingers_stems"], b["B_fingers_only"]), (255, 255, 255), (0, 0, 0))], 19)
    p = os.path.join(ev_dir, "29_union_iou.png")
    T.save_png_reserved(p, img, [(240, 240, 240), (170, 170, 170), (255, 60, 60), (0, 200, 255), (110, 110, 110), (255, 255, 255), (0, 0, 0)])
    return p


def representative_sheet(ref_rgb, cards, rep, centre, ev_dir):
    cols, rows = 5, 3
    cw_, ch_ = 1920 // cols, (1080 - 40) // rows
    sheet = np.full((1080, 1920, 3), 30, np.uint8)
    texts = [(20, 6, "代表10形の候補（R1〜R10）と船側中央の候補：黄＝中心線、赤＝関節（根元→先端）、数値＝長さ・根元幅・中央幅（表示 px）、節の長さ比、曲がり角", (255, 255, 255), None)]
    cmap = {c["id"]: k for k, c in centre}
    for i, c in enumerate(cards[:cols * rows]):
        off = c["off"]
        gx, gy = (i % cols) * cw_, 40 + (i // cols) * ch_
        P = np.concatenate([np.asarray(c["poly"]).reshape(-1, 2) if c["poly"] else (c["Cr"] + off), c["Cr"] + off], 0)
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


def right_reading_figure(ref_rgb, claws, rr, inv, boat_ref, ev_dir):
    """右側の爪：上の段＝読みA（尖る淡い指の先＝爪先）、下の段＝読みB（藍の鉤＝爪先）。左右は右側の縁の左下半分と右上半分。"""
    R = [c for c in claws if c["zone"] == "right"]
    if not R:
        return None
    s = inv["right_side_reading"]["summary"]
    xs_mid = float(np.median([c.get("reading_A", c)["root_abs"][0] for c in R]))
    halves = [[c for c in R if c.get("reading_A", c)["root_abs"][0] < xs_mid], [c for c in R if c.get("reading_A", c)["root_abs"][0] >= xs_mid]]
    rows_img = []
    for mode in ("A", "B"):
        cols_img = []
        for sub in halves:
            pts = []
            for c in sub:
                A = c.get("reading_A", c)
                pts += [np.asarray(A["poly"]).reshape(-1, 2) if A["poly"] else A["Cr"] + c["off"], A["Cr"] + c["off"]]
                if c["reading"]["hook"] is not None:
                    pts.append(c["reading"]["hook"]["arc"])
            P = np.concatenate(pts, 0)
            x0, y0 = P[:, 0].min() - 30, P[:, 1].min() - 30
            w, h = P[:, 0].max() - x0 + 30, P[:, 1].max() - y0 + 30
            img, Mv = _view(ref_rgb, x0, y0, w, h, 960, 470)
            img = (img.astype(np.float32) * 0.8 + 30).clip(0, 255).astype(np.uint8)
            labels = []
            for c in sub:
                g = c["reading"]
                A = c.get("reading_A", c)
                off = c["off"]
                if mode == "A":
                    C, col = A["Cr"] + off, ((60, 200, 60) if g["toward_boat_A"] else (255, 70, 70))
                else:
                    if g["hook"] is None:
                        q = _pts(Mv, (A["Cr"] + off))
                        cv2.polylines(img, [np.round(q * 4).astype(np.int32)], False, (150, 150, 150), 1, cv2.LINE_AA, shift=2)
                        m_ = q[len(q) // 2]
                        labels.append((m_[0] + 4, m_[1] - 12, "%d 鉤なし" % c["num"], (200, 200, 200), (0, 0, 0)))
                        continue
                    C, col = c["Cr"] + off, ((60, 200, 60) if g["toward_boat_B"] else (255, 70, 70))
                    arc = np.round(_pts(Mv, g["hook"]["arc"]) * 4).astype(np.int32)
                    cv2.polylines(img, [arc], False, (255, 150, 0), 3, cv2.LINE_AA, shift=2)
                Q = _pts(Mv, C)
                cv2.polylines(img, [np.round(Q * 4).astype(np.int32)], False, (255, 255, 255), 2, cv2.LINE_AA, shift=2)
                a_ = Q[max(0, len(Q) - 3)]
                b_ = Q[-1]
                cv2.arrowedLine(img, tuple(np.round(a_).astype(int)), tuple(np.round(b_).astype(int)), col, 3, cv2.LINE_AA, tipLength=1.0)
                r0 = Q[0]
                cv2.circle(img, (int(round(r0[0])), int(round(r0[1]))), 4, (0, 0, 0), -1, cv2.LINE_AA)
                labels.append((b_[0] + 4, b_[1] - 12, str(c["num"]), (255, 255, 255), (0, 0, 0)))
                q0 = _pts(Mv, A["root_abs"][None])[0]
                q1 = q0 + 26 * g["boat_dir"]
                cv2.arrowedLine(img, tuple(np.round(q0).astype(int)), tuple(np.round(q1).astype(int)), (0, 255, 255), 1, cv2.LINE_AA, tipLength=0.3)
            cols_img.append(_text(img, labels, 16))
        row = np.concatenate([cols_img[0], np.full((470, 0, 3), 0, np.uint8), cols_img[1]], 1)
        head = ("読みA（尖る淡い指の先＝爪先、草稿の読み）：根元→先端が船の側 %d 本、離れる側 %d 本（先端の向きが右・右下 %d 本）／全 %d 本" % (
                    s["toward_boat_A"], s["away_from_boat_A"], s["tip_direction_A_right_or_down_right"], s["right_claws"])
                if mode == "A" else
                "読みB（藍の鉤＝爪先、完成版の主の読み・既定値・利用者未確認）：鉤の見つかった %d 本のうち、根元→先端が船の側 %d 本、鉤の先の向きが船の側 %d 本" % (
                    s["hook_found"], s["toward_boat_B"], s["hook_end_tangent_toward_boat"]))
        band = np.full((70, 1920, 3), 30, np.uint8)
        band = _text(band, [(12, 6, head, (255, 255, 255), None),
                            (12, 36, "緑の矢印＝根元→先端が船（右の船）の側、赤＝離れる側。黒点＝根元。水色の細い矢印＝最も近い船の画素への向き" + ("。橙＝頭の藍の鉤の弧。灰＝鉤の見つからない爪（読みAのまま）" if mode == "B" else ""), (220, 220, 220), None)], 17)
        rows_img.append(np.concatenate([band, row], 0))
    fig = np.concatenate(rows_img, 0)
    p = os.path.join(ev_dir, "29_right_reading.png")
    T.save_png_reserved(p, fig, [(60, 200, 60), (255, 70, 70), (255, 150, 0), (255, 255, 255), (0, 0, 0), (0, 255, 255), (30, 30, 30), (40, 40, 40), (150, 150, 150), (220, 220, 220), (200, 200, 200)])
    return p


def rows_figure(ref_rgb, claws, ri, ref_curve, ref_s, inv, ev_dir):
    """列の境目：外周（基準曲線）に s の目盛り、特徴点（接線 45°・90°）と境目、x_split、各爪の先端→最近点の線。白い輪＝境目に近い爪。"""
    main = [c for c in claws if c["zone"] == "main"]
    x0, y0, w, h = 780, 150, 1600, 1000
    img, Mv = _view(ref_rgb, x0, y0, w, h, 1920, 1080)
    img = (img.astype(np.float32) * 0.55 + 60).clip(0, 255).astype(np.uint8)
    sel = ref_s <= 2200
    Q = np.round(_pts(Mv, ref_curve[sel]) * 4).astype(np.int32)
    cv2.polylines(img, [Q], False, (40, 40, 40), 3, cv2.LINE_AA, shift=2)
    labels = []
    for sv in range(-600, 2201, 100):
        i = int(np.argmin(np.abs(ref_s - sv)))
        q = _pts(Mv, ref_curve[i][None])[0]
        cv2.circle(img, tuple(np.round(q).astype(int)), 3, (40, 40, 40), -1)
        if sv % 200 == 0:
            labels.append((q[0] + 5, q[1] - 22, "s%d" % sv, (40, 40, 40), (255, 255, 255)))
    for k, col in (("上側|途中", (255, 170, 0)), ("途中|船側", (0, 200, 90))):
        for name, sv, rad in (("特徴", ri["features_s"][k], 7), ("境目", ri["breaks_s"][k], 12)):
            i = int(np.argmin(np.abs(ref_s - sv)))
            q = _pts(Mv, ref_curve[i][None])[0]
            cv2.circle(img, tuple(np.round(q).astype(int)), rad, col, 3 if name == "境目" else -1, cv2.LINE_AA)
            labels.append((q[0] + 14, q[1] + (4 if name == "境目" else 20), "%s %s s=%.0f" % (k, name, sv), col, (0, 0, 0)))
    xs = _pts(Mv, np.array([[ri["x_split"], 150.0], [ri["x_split"], 1150.0]]))
    cv2.line(img, tuple(np.round(xs[0]).astype(int)), tuple(np.round(xs[1]).astype(int)), (255, 40, 40), 2, cv2.LINE_AA)
    labels.append((xs[0][0] + 6, xs[0][1] + 40, "x_split %.0f（左は上側）" % ri["x_split"], (255, 40, 40), (0, 0, 0)))
    for c in main:
        col = ROW_COLOURS[c["row"]]
        t = _pts(Mv, c["tip_abs"][None])[0]
        i = int(np.argmin(np.abs(ref_s - c["s_tip"])))
        q = _pts(Mv, ref_curve[i][None])[0]
        cv2.line(img, tuple(np.round(t).astype(int)), tuple(np.round(q).astype(int)), col, 1, cv2.LINE_AA)
        cv2.circle(img, tuple(np.round(t).astype(int)), 4, col, -1, cv2.LINE_AA)
        if c.get("row_near_boundary"):
            cv2.circle(img, tuple(np.round(t).astype(int)), 11, (255, 255, 255), 2, cv2.LINE_AA)
            labels.append((t[0] + 8, t[1] - 8, "%d" % c["num"], (255, 255, 255), (0, 0, 0)))
    sens = ri["sensitivity_row_changes"]
    rd = inv["rows_definition"]
    labels += [(16, 10, "列の境目（主浪）：色点＝爪の先端（列の色）、細線＝外周への最近点、白い輪＝境目から %s px 未満の爪（%d 本）" % (
                    "25", len(rd["near_boundary_ids"])), (255, 255, 255), (0, 0, 0)),
               (16, 38, "境目 s：上側|途中 %.0f（特徴点 %.0f）、途中|船側 %.0f（特徴点 %.0f）、x_split %.0f。草稿は s 520・1150、x 1480" % (
                   ri["breaks_s"]["上側|途中"], ri["features_s"]["上側|途中"], ri["breaks_s"]["途中|船側"], ri["features_s"]["途中|船側"], ri["x_split"]), (255, 255, 255), (0, 0, 0)),
               (16, 66, "感度（列の変わる本数）：境目を ±40 px 動かす " + "、".join("%s→%d" % (k, v) for k, v in sens.items()) + "。根元で決めると %d 本が変わる" % len(rd["root_based_disagreements"]), (255, 255, 255), (0, 0, 0))]
    img = _text(img, labels, 17)
    p = os.path.join(ev_dir, "29_rows_boundaries.png")
    T.save_png_reserved(p, img, RESERVED + [(255, 170, 0), (0, 200, 90), (255, 40, 40)])
    return p


def cp2_figure(ref_rgb, claws, rep, centre, boat, inv, ev_dir):
    """CP2：船側の列（唇の右端と下面）を大きくし、番号と候補を示す。利用者はこの図の番号で中央の爪を指定する。上の帯に説明。"""
    sub = [c for c in claws if c["row"] == "船側"]
    x0, y0, w, h = _bbox_of(sub, 25)
    band_h = 230
    img, Mv = _view(ref_rgb, x0, y0, w, h, 1920, 1080 - band_h)
    rep_ids = {c["id"] for c in rep}
    cid = {c["id"]: k for k, c in centre}
    over = draw_claws(img, Mv, [c for c in claws if c["zone"] == "main"], rep_ids, cid, 22, line=2, dim=0.85, webs=False)
    kd = 1080.0 / 2594.0
    lines = ["CP2：船側中央の爪の指定と代表10形の確認用（高解像度原画 x %d〜%d、y %d〜%d）。色：上側＝橙、途中＝緑、船側＝赤。黄の太線＝代表10形の候補、水色の太線＝船側中央の候補" % (x0, x0 + w, y0, y0 + h),
             "船側で外輪郭に出て下を向く長い爪（%d 本、外周に沿った順）：%s" % (len(boat), " ".join("%d" % c["num"] for c in boat)),
             "候補（backlog 95『根元が先より広い』と 97『先が下へ曲がる』を満たす爪を先に、並びの中央に近い順）："]
    for k, c in centre:
        ch = c["centre_checks"]
        lines.append("  中%d ＝ %d（%s、草稿 %s）：外周の順 %d/%d、長さ %.1f、根元幅 %.1f／先端付近 %.1f 表示px、95 %s、97 %s" % (
            k, c["num"], c["row_id"], c["draft1"]["id"] if c["draft1"] else "—", c["boat_idx"], len(boat), c["length"] * kd, c["root_w"] * kd, c["tip_w"] * kd,
            "○" if ch["95_root_wider_than_tip"] else "×", "○" if ch["97_tip_downward"] else "×"))
    band = np.full((band_h, 1920, 3), 30, np.uint8)
    band = _text(band, [(14, 8 + 26 * i, t, (255, 255, 255), None) for i, t in enumerate(lines)], 18)
    fig = np.concatenate([band, over], 0)
    p = os.path.join(ev_dir, "29_cp2_nomination.png")
    T.save_png_reserved(p, fig, RESERVED + [(30, 30, 30)])
    return p


# ---------------------------------------------------------------- 指標と記録
def build_metrics(inv, iou_rec, zone_stats, rep, rep_by_len, centre, sky_check, ri, rr, count_sens):
    n = inv["counts"]["total"]
    n_main = inv["counts"]["main_wave_total"]
    a = iou_rec["main"]
    al = iou_rec["all_zones"]

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
    s = inv["right_side_reading"]["summary"]
    rd = inv["rows_definition"]
    in_range = lambda v: 135 <= v <= 165  # noqa: E731
    return {
        "schema": "GreatWave.ArtFirst.metrics/1",
        "number": "29",
        "version": VERSION,
        "note_ja": "番号29 の完成版（CP2 用）。受入の IoU は分母の定義で合否が分かれるので『定義待ち』とし、爪の数は比べる範囲で合否が分かれるので『範囲待ち』とした。どのバックログ項目も合格にしていない（29 は 95〜98、122〜129、136〜139、240〜256 の前提で、判定は番号33・35・40）。",
        "plan_ja": "作業計画 4.2 の 29（B線、上限 2 日、9/29〜10/4）。草稿 draft1（c63e7bb）の続き。",
        "evidence_kind_ja": "Met 原画（高解像度 DP130155）の numpy/OpenCV 計算と、その重ね図。Unity・Blender・Houdini は使っていない。参照モデル（Q5）は読んでいない。",
        "items": [
            {"item": "29受入：一覧から描き直した爪の和集合と原画の白領域の IoU ≥ 0.85", "target": "≥ 0.85",
             "value": {"denominator_A_flat_crest_white_excluded": round(a["A_all_parts"], 4), "denominator_B_flat_crest_white_included": round(a["B_all_parts"], 4)},
             "value_other": {k: r4(v) for k, v in iou_rec.items()},
             "verdict": "定義待ち（分母A なら %s、分母B なら %s。CP2 で利用者が定義を決める）" % ("≥0.85" if a["A_all_parts"] >= 0.85 else "<0.85", "≥0.85" if a["B_all_parts"] >= 0.85 else "<0.85"),
             "note_ja": "主の値は主浪の波頭の範囲（高解像度 px）で、分子は一覧の指＋幹＋根元の白（base_web）の和集合。分母A＝主浪の白から波頭の平らな白（半径 45 px の円で開いて残る厚い白）を除いた白（爪の白）、分母B＝平らな白を含む主浪の白の全体（分子は平らな白を描かない）。指＋幹だけ：A %.4f・B %.4f、指だけ：A %.4f・B %.4f、輪郭の多角形：A %.4f・B %.4f。2 つの範囲の合計：A %.4f・B %.4f。分母B に対し分子へ平らな白の多角形も足すと %.4f（記録）。" % (
                 a["A_fingers_stems"], a["B_fingers_stems"], a["A_fingers_only"], a["B_fingers_only"], a["A_outline_polygons"], a["B_outline_polygons"],
                 al["A_all_parts"], al["B_all_parts"], a["B_all_parts_plus_flat_white_polygons"])},
            {"item": "29受入：爪の数 150 ± 15（backlog 139『配置した約150本』）", "target": "135〜165",
             "value": {"main_wave": n_main, "main_wave_plus_right_side": n},
             "value_other": {"by_row": inv["counts"]["by_row"], "silhouette_by_row": inv["counts"]["silhouette_by_row"],
                             "over_indigo_by_row": inv["counts"]["over_indigo_by_row"], "by_min_length_ref_px": count_sens,
                             "excluded_by_reason": inv["counts"]["excluded_by_reason"], "base_web_pieces_not_counted": inv["counts"]["base_web_pieces"]},
             "verdict": "範囲待ち（主浪だけなら %d 本で %s、右側を含めると %d 本で %s。CP2 で利用者が比べる範囲を決める）" % (
                 n_main, "範囲内" if in_range(n_main) else "範囲外", n, "範囲内" if in_range(n) else "範囲外"),
             "note_ja": inv["counts"]["backlog_139_ja"]},
            {"item": "29受入：代表10形の長短の順序を自動で出力できる", "target": "出力できる", "value": [c["id"] for c in rep_by_len],
             "verdict": "出力できる（選定は利用者の CP2 確認待ち）" if len(rep) == 10 else "不足（候補が 10 本に届かない）",
             "note_ja": "claw_inventory.json の representative_candidates に長さ・根元幅・中央幅の順、representative_and_centre_details に中心線・関節・節の長さ比・曲がり角を出力した。"},
            {"item": "29受入：利用者が CP2 で中央の爪を指定し、代表10形を確かめる", "target": "CP2", "value": {"centre_candidates": [c["id"] for _, c in centre], "figure": "29_cp2_nomination.png"},
             "verdict": "利用者の確認待ち"},
            {"item": "29：右側の爪の向き（backlog 240『先が船側へ曲がる』との対応、読みの検査）", "target": "記録（読みは CP2 で確認）",
             "value": {"reading_A_toward_boat": s["toward_boat_A"], "reading_A_away_from_boat": s["away_from_boat_A"],
                       "reading_B_hook_found": s["hook_found"], "reading_B_toward_boat": s["toward_boat_B"],
                       "hook_end_tangent_toward_boat": s["hook_end_tangent_toward_boat"], "right_claws": s["right_claws"]},
             "value_other": {"tip_A_context_median": s["tip_A_context_median"], "main_tip_context_median": s["main_tip_context_median"],
                             "tip_A_line_ge_0.3": s["tip_A_line_ge_0.3"], "main_over_indigo": inv["right_side_reading"]["main_wave_over_indigo_head_hooks"]},
             "verdict": "記録のみ（主の読み %s・既定値・利用者未確認）" % s["primary"]},
            {"item": "29：列の境目の安定性", "target": "記録", "value": {"breaks_s": rd["breaks"]["s"], "x_split_ref": rd["breaks"]["x_split_ref"], "near_boundary": len(rd["near_boundary_ids"])},
             "value_other": {"sensitivity_row_changes": rd["sensitivity_row_changes"], "root_based_disagreements": rd["root_based_disagreements"],
                             "window_alternatives": rd["window_alternatives"], "near_boundary_ids": rd["near_boundary_ids"], "features_s": rd["features_s"]},
             "verdict": "記録のみ（境目は CP2 で確認）"},
            {"item": "123/124/125/126（代表10形）、122/127/128（各列の根元・先端）、261（隙間）、95〜98（船側中央）、240/243/246（右側）", "target": "番号33・40 で ≤4 px を判定",
             "value": "一覧に根元・先端・幅・向き・隙間・遮蔽の順序・輪郭を記録", "verdict": "記録のみ（判定は番号33 など）"},
            {"item": "自作 Zhang–Suen の確認（合成図形、原画の白の位相、太さ 2 の残り）", "target": "長方形→中央の 1 本線、穴あき円板と原画の白→成分と穴の数が細線化の前後で同じ、太さ 2 の残り 0",
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


def build_run(spec, args, out_json, figs, timings, zone_stats, sky_check, ev_dir):
    inputs = [spec["reference"]["path"], "Tools/PaintingTruth/painting_truth.json", "Tools/PaintingTruth/manual_annotations.json",
              "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/targets/palette.json",
              "Tools/PaintingTruth/targets/main_wave_outline_envelope.json", "Tools/PaintingTruth/targets/masks/sky_claws_cov.png",
              "Tools/PaintingTruth/claws29/af29_params.json", "Tools/PaintingTruth/claws29/af29_skeleton.py",
              "Tools/PaintingTruth/claws29/af29_claw_inventory.py", "Tools/PaintingTruth/claws29/af29_draft1_tips.json"]
    outs = [out_json] + [p for p in figs.values() if p] + [os.path.join(ev_dir, "metrics.json")]
    return {
        "schema": "GreatWave.ArtFirst.run/1",
        "number": "29",
        "version": VERSION,
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "command": "py -3.10 Tools/PaintingTruth/claws29/af29_claw_inventory.py --evidence " + args.evidence + ((" --out " + args.out) if args.out else ""),
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
