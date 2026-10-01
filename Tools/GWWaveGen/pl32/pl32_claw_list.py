# -*- coding: utf-8 -*-
"""仕上げ32：爪の一覧の仕上げ（numpy・OpenCV。Unity の描画ではない）。設計32 の一覧（173 本）を土台に、計画 §5.3 仕上げ32 の行を直す。

1. b区域の爪を数え直して加える（［利用者の言葉］Q16・Q21）：pl32_bregion.py の候補（美術優先29 の骨格化を b区域の帯に当てたもの）を、
   進行役の目視の 1 回の判定（EYE）と自動の重複の検査で選び、新しい ID（C176〜）で加える。
2. 爪ごとに、領域の多角形を原画の輪郭線（墨版の藍の線）へ合わせる（③）。摺りの工程の調べ（記録 第1節）で決め直した D25 の定義：
   爪＝墨版の線で区切られた、紙の地（摺らない白）と水色の版の画素。線（mix・藍中・藍濃）と空・黄土は越えない。
   作り方：全部の爪の中心線を種にした測地の競り合い（各爪は中心線から、その指の白の半幅の 2.2 倍（6〜30 px）までの測地の距離だけ広がり、
   近い種の爪が画素を取る。4 近傍と 8 近傍を交互にして八角形の距離に近づける）。爪どうしは画素を分け合わないので、重なり 0。
   根元の後ろ（根元の接線の後ろ側で根元から広がりの半径の内）の画素は落とす（口の弦）。3×3 の開きで細いとげを落とし、中心線を含む連結成分だけを残す。
3. 中心線を領域の真ん中へ合わせる：根元 → 先端を、領域の中で、領域の距離変換に反比例する費用の最短路（真ん中を通る）で結び直し、5 点でならす。
4. 上側の列（美術優先29 の根元のまま 60 本）に口の規則（設計32 の revise、修正01 の見張りつき）を当てる。
5. 名指しの短い爪（C066・C112・C113。C109 は利用者の名指しの直しの結果なので保つ）を、目視の判定（SHORT）で美術優先29 の根元へ戻す。
   根元の先で指が続く疑い 8 本と C174／C002 は目視の判定（CONT）で直すか理由を残す。
6. 支（主爪＋支）の判定の規則を決め直す（領域を分け合わないので「根元が他の爪の領域の中」は使えない。根元が主爪の中心線の 10〜95% の所の
   主爪の半幅 + 4 px 以内）。爪の型を作る ds33_claw_rig.py へは、この判定を branch_inside_tol で渡す（pl32_claws.py）。
7. 記録：重なり・とげ・他の爪の領域の中の根元・影の割合・IoU（D25 を決め直した定義）・代表の形・船側の中央の爪。

出力（Git 対象外）：Unity/Build/Polish/32/list/ds32_claw_inventory.json（設計32 と同じ書式。ds33 の道具がそのまま読む）、
pl32_claw_list_checks.json、図。右側の爪（C129〜C153）は触らない（低優先・未修正。ブラッシュアップの最後）。
"""
import argparse
import hashlib
import heapq
import json
import math
import os
import sys
import time

import cv2
import numpy as np

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, REPO + "/Tools/GWWaveGen/ds32")
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
import ds32_claw_list as L32  # noqa: E402
import truthlib as T  # noqa: E402

INV32 = REPO + "/Unity/Build/Design/32/list+ids/ds32_claw_inventory.json"
CORR32 = REPO + "/Unity/Build/Design/32/list+ids/ds32_user100_correspondence.json"
BCAND = REPO + "/Unity/Build/Polish/32/list/pl32_bregion_candidates.json"
OUT = REPO + "/Unity/Build/Polish/32/list"
A_DISP, X_OFF = 0.416345, 156.66153

P = dict(
    crop=[0, 0, 2700, 1560],
    grow_factor=2.2, grow_min=6, grow_max=30,       # 測地の広がりの上限 = clip(2.2 × 指の白の半幅の中央値, 6, 30) 原画 px
    mouth_back_px=1.0,                               # 根元の接線の後ろ側のこの距離より後ろは落とす（口の弦）
    open_px=3, hole_px=30,
    centre_cost_eps=0.5,
    trim_len_ref_px=70.0,                            # 目視で「先だけ採る」とした候補の先端からの弧長
    dup_near_px=6.0, dup_frac=0.4,                   # b区域の候補の自動の重複：中心線の 40% 以上が既存の爪の中心線から 6 px 以内か領域の中
    new_id_start=176,
    truth_line_px=14.0, truth_open_r=16,             # IoU の真値：墨版の線から 14 px 以内の紙・水色で、半径 16 px の円が入る厚い所を除く
    branch_sigma=[0.10, 0.95], branch_add_px=4.0,
)

# 進行役の目視の判定（2026-10-02、1 回。b区域の候補 88 の 1:2 の切り抜きを見て決めた。Unity/Build/Polish/32/list の図）
EYE = dict(
    drop={7: "長い道（白の胴を横切る、指でない）", 12: "紙の地の何もない所（背の白）", 16: "紙の地の何もない所（左の船の上）",
          20: "二つの指の間を縦に横切る長い道", 21: "水色の中の何もない所", 23: "短すぎる（線の間の 1 点）", 26: "長い道（胴を横切る）",
          54: "長い道（胴を横切る）", 60: "短すぎる", 84: "舌の上の縁をなぞる長い道（指でない）", 86: "長い道（胴を横切る）"},
    trim={28: "根元の側が胴を横切るので先の鉤だけ採る", 32: "同じ", 66: "同じ"},
    dup={30: "既存の爪に重なる", 46: "既存の爪に重なる", 56: "既存の爪に重なる", 73: "既存の爪に重なる", 74: "既存の爪に重なる",
         82: "既存の爪に重なる", 87: "既存の爪に重なる"},
)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rnd(v, k=1):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    return None if v is None else round(float(v), k)


def r2d(q):
    q = np.asarray(q, np.float64)
    return np.stack([A_DISP * (q[..., 0] + 0.5) - 0.5 + X_OFF, A_DISP * (q[..., 1] + 0.5) - 0.5], -1)


def cumlen(C):
    C = np.asarray(C, np.float64)
    return np.r_[0.0, np.cumsum(np.hypot(*np.diff(C, axis=0).T))] if len(C) > 1 else np.zeros(len(C))


def resample(C, step):
    C = np.asarray(C, np.float64)
    if len(C) < 2:
        return C.copy()
    s = cumlen(C)
    if s[-1] < 1e-9:
        return C[:1].copy()
    n = max(2, int(round(s[-1] / step)) + 1)
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, C[:, 0]), np.interp(t, s, C[:, 1])], 1)


def smooth(C, win=5):
    C = np.asarray(C, np.float64)
    if len(C) < win:
        return C.copy()
    h = win // 2
    Cp = np.concatenate([np.repeat(C[:1], h, 0), C, np.repeat(C[-1:], h, 0)], 0)
    out = np.stack([np.convolve(Cp[:, k], np.ones(win) / win, mode="valid") for k in range(2)], 1)
    out[0], out[-1] = C[0], C[-1]
    return out


def raster_line(M, C, val, thick=1):
    cv2.polylines(M, [np.round(C).astype(np.int32).reshape(-1, 1, 2)], False, int(val), thick)


def grow_labels(L, passable, lim, max_it):
    """測地の競り合い：L（ラベルの画像、0 は空き）を、通れる画素へ 1 回に 1 画素ずつ広げる。lim[label] 回まで。
    奇数回は 4 近傍、偶数回は 8 近傍（八角形の距離）。同じ回で複数のラベルが届く画素は、近傍の決まった順の最初のもの。"""
    L = L.copy()
    free = passable & (L == 0)
    n4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    n8 = n4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    H, W = L.shape
    for it in range(1, max_it + 1):
        act = np.where(lim[L] >= it, L, 0)
        if not act.any():
            break
        new = np.zeros_like(L)
        for dy, dx in (n4 if it % 2 else n8):
            sh = np.zeros_like(L)
            ys0, ys1 = max(0, dy), H + min(0, dy)
            xs0, xs1 = max(0, dx), W + min(0, dx)
            sh[ys0:ys1, xs0:xs1] = act[ys0 - dy:ys1 - dy, xs0 - dx:xs1 - dx]
            take = free & (new == 0) & (sh > 0)
            new[take] = sh[take]
        if not new.any():
            break
        L[new > 0] = new[new > 0]
        free &= new == 0
    return L


def centre_path(R, a, b, eps):
    """領域 R（bool）の中で a → b（(x, y) 整数）を、距離変換に反比例する費用で結ぶ最短路（8 近傍の Dijkstra）。"""
    h, w = R.shape
    DT = cv2.distanceTransform(R.astype(np.uint8), cv2.DIST_L2, 5)
    cost = 1.0 / (DT + eps)
    dist = np.full((h, w), np.inf)
    prev = -np.ones((h, w), np.int64)
    (sx, sy), (tx, ty) = a, b
    dist[sy, sx] = 0.0
    pq = [(0.0, sy, sx)]
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while pq:
        d, y, x = heapq.heappop(pq)
        if d > dist[y, x]:
            continue
        if (y, x) == (ty, tx):
            break
        for dy, dx in nb:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and R[yy, xx]:
                nd = d + math.hypot(dy, dx) * 0.5 * (cost[y, x] + cost[yy, xx])
                if nd < dist[yy, xx]:
                    dist[yy, xx] = nd
                    prev[yy, xx] = y * w + x
                    heapq.heappush(pq, (nd, yy, xx))
    if not np.isfinite(dist[ty, tx]):
        return None
    path, cur = [], ty * w + tx
    while cur >= 0:
        yy, xx = divmod(cur, w)
        path.append((xx, yy))
        if (yy, xx) == (sy, sx):
            break
        cur = prev[yy, xx]
    return np.array(path[::-1], np.float64)


def fix01_steps(paint, claws, byid, eye2, log, t0):
    """修正の回 1（pl32f_list_steps.py）：利用者の 100 本の位置合わせのし直しと追加、根元の先で指が続く爪の根元の延長。"""
    import pl32f_list_steps as F
    rec = dict()
    corr = json.load(open(CORR32, encoding="utf-8"))
    rows = {r["user_id"]: r for r in corr["claws"]}
    # 1. 位置合わせのし直し（ECC の後の NCC < 0.70 の爪。対応なしの 7 本と、対応ありの claw035・claw043）
    unc = sorted(u for u, r in rows.items() if r["ncc_after_ecc"] < 0.70)
    rr = F.reregister(REPO + "/Docs/References/Met_JP1847_DP130155.jpg", unc, near={u: rows[u]["root_ref"] for u in unc})
    rec["reregister"] = {}
    for u, d in rr.items():
        e = {k: v for k, v in d.items() if not k.startswith("_")}
        e.update(before_ncc_after_ecc=rows[u]["ncc_after_ecc"], before_status=rows[u]["status"], before_root_ref=rows[u]["root_ref"])
        rec["reregister"][u] = e
    print("reregister", {u: (d["ncc_after_ecc"], d["rotation_deg"]) for u, d in rr.items()}, "%.1fs" % (time.time() - t0), flush=True)
    # 既存の爪の中心線（主浪）の近さ
    cl_m = np.zeros((paint.H, paint.W), np.uint8)
    for c in claws:
        if c["zone"] == "main":
            raster_line(cl_m, paint.loc(c["centerline_ref"]), 1, 1)
    near8 = cv2.distanceTransform((cl_m == 0).astype(np.uint8), cv2.DIST_L2, 5) <= 8.0

    def dup_of(C):
        Q = np.round(paint.loc(resample(C, 1.0))).astype(int)
        Q[:, 0] = np.clip(Q[:, 0], 0, paint.W - 1); Q[:, 1] = np.clip(Q[:, 1], 0, paint.H - 1)
        return float(near8[Q[:, 1], Q[:, 0]].mean())
    # 2. 加える爪（対応なしの爪の扱いの決め直し）
    adds = []
    nid = max(int(c["id"][1:]) for c in claws) + 1
    same = {"claw076": "claw069", "claw099": "claw098"}
    for u, r in sorted(rows.items()):
        reason = r.get("reason_ja", "")
        if r["status"] != "対応なし":
            if u in rr:
                g = rr[u]
                adds.append(dict(user_id=u, before_ja="対応 " + str(r.get("best_id")), decision="対応のまま（位置合わせだけし直した）",
                                 ncc_after_ecc=g["ncc_after_ecc"], root_shift_ref_px=round(float(np.hypot(*(np.asarray(g["root_ref"]) - r["root_ref"]))), 1)))
            continue
        d = dict(user_id=u, before_ja=reason)
        if u in same:
            d.update(decision="まとめる", into=same[u], reason_ja="同じ画像（claw069／076）か同じ所に合う爪（claw098／099）なので 1 本にまとめる")
            adds.append(d)
            continue
        if "重複か位置合わせの誤り" in reason:
            d.update(decision="対応（設計32 修正01 のまま、C163）", reason_ja="こちらの方法で作ると C163 と同じ指（設計32 修正01 の独立の検査）")
            adds.append(d)
            continue
        if u in rr:
            g = rr[u]
            root, tip = g["root_ref"], g["tip_ref"]
            d["reregistered_ncc"] = g["ncc_after_ecc"]
            if g["ncc_after_ecc"] < 0.70:
                d.update(decision="加えない（不確かのまま）", reason_ja="回転つきでし直しても NCC %.2f < 0.70" % g["ncc_after_ecc"])
                adds.append(d)
                continue
        else:
            root, tip = r["root_ref"], r["tip_ref"]
        front = "手前の波" in reason or (not r["in_main_zone"] and not r["in_b_region"] and root[1] > 1400)
        cl, _ = L32.path_between(paint, root, tip)
        if cl is None or len(cl) < 3:
            d.update(decision="加えない", reason_ja="根元と先端を通れる画素でつなげない")
            adds.append(d)
            continue
        cl = resample(smooth(cl, 5), 3.0)
        if not front:
            fr = dup_of(cl)
            if fr >= 0.4:
                mid = cl[len(cl) // 2]
                ids_ = sorted(((float(np.min(np.hypot(*(np.asarray(c["centerline_ref"]) - mid).T))), c["id"]) for c in claws if c["zone"] == "main"))[:2]
                d.update(decision="対応（既存の爪）", match=[i for _, i in ids_], dup_fraction=round(fr, 2),
                         reason_ja="中心線の %.0f%% が既存の爪の中心線から 8 px 以内" % (100 * fr))
                adds.append(d)
                continue
        cid = "C%03d" % nid
        nid += 1
        recc = {"id": cid, "origin": "pl32f_user100", "zone": "front" if front else "main", "row": "手前の波" if front else "主浪の左下",
                "seed": "user100:" + u, "tip_ref": rnd(cl[-1]), "root_ref": rnd(cl[0]), "centerline_ref": rnd(cl), "root_ref_af29": None,
                "length_ref_px_af29": None, "silhouette": False, "over_indigo": None, "polygon_ref_af29": None,
                "status": "pl32f_user100_front" if front else "pl32f_user100", "b_region_q16": False,
                "mouth_reason": "利用者の根元（構造点 S）を種にした最短路"}
        claws.append(recc)
        d.update(decision="加える", id=cid, zone=recc["zone"], length_ref_px=round(float(cumlen(cl)[-1]), 1))
        adds.append(d)
    # 加えた爪どうしで根元が 6 px 以内なら同じ指（利用者の claw053／069 など）：後の方を消す
    added = [c for c in claws if c.get("origin") == "pl32f_user100"]
    for i_, c1 in enumerate(added):
        for c2 in added[i_ + 1:]:
            if c2.get("_dup") or c1.get("_dup"):
                continue
            if float(np.hypot(*(np.asarray(c1["root_ref"]) - c2["root_ref"]))) < 6.0:
                c2["_dup"] = c1["id"]
    for c2 in [c for c in added if c.get("_dup")]:
        claws.remove(c2)
        for d in adds:
            if d.get("id") == c2["id"]:
                d.update(decision="まとめる", into_id=c2["_dup"], reason_ja="加えた %s と根元が 6 px 以内の同じ指" % c2["_dup"])
                d.pop("id", None)
    rec["user100_additions"] = adds
    print("user100", [(d["user_id"], d["decision"], d.get("id")) for d in adds if d["decision"] != "対応のまま（位置合わせだけし直した）"], flush=True)
    # 3. 根元の先で指が続く爪の根元の延長（pl32f_root_extend）
    keep = set(eye2.get("keep", {}).keys())
    ext = []
    for c in claws:
        if c["zone"] != "main":
            continue
        f_, _ = L32.continues_past_root(paint, c["centerline_ref"])
        if (f_ is None or f_ < L32.P["cont_frac"]) and c["id"] not in eye2.get("pl32f_cont", {}).get("extend", {}):
            continue
        f_ = -1.0 if f_ is None else f_
        if c["id"] in keep:
            ext.append(dict(id=c["id"], before_fraction=round(f_, 2), decision="延ばさない（名指しの長さを保つ）", reason_ja=eye2["keep"][c["id"]]))
            continue
        blk = np.zeros((paint.H, paint.W), np.uint8)
        x0_, y0_ = np.min(paint.loc(c["centerline_ref"]), 0) - 120
        for o in claws:
            if o is not c and o["zone"] == "main":
                raster_line(blk, paint.loc(o["centerline_ref"]), 1, 7)
        pts, info = F.extend_root(L32, paint, c["centerline_ref"], blk.astype(bool))
        e = dict(id=c["id"], before_fraction=round(f_, 2), **info)
        ce = eye2.get("pl32f_cont", {})
        if len(pts) < 3 and c["id"] in ce.get("extend", {}):
            # 目視で「指が続く」とした爪：同じ 2 本の線の続きの検査を外し、断面が閉じて幅が 1.5 倍 + 6 px 以下の間だけ真っ直ぐ延ばす（最大 40 px）
            pts, info2 = F.extend_root(L32, paint, c["centerline_ref"], blk.astype(bool), max_ext=40.0, continuity=False)
            e.update(eye_ja=ce["extend"][c["id"]], stop_ja=info2["stop_ja"], how="目視＋真っ直ぐ")
        elif len(pts) < 3 and c["id"] in ce.get("fp", {}):
            e.update(eye_ja=ce["fp"][c["id"]], how="目視：誤検出")
        if len(pts) >= 3:
            newC = np.concatenate([paint.glob(pts[::-1]), np.asarray(c["centerline_ref"], np.float64)], 0)
            c["root_ref_pl32"] = c["root_ref"]
            c["centerline_ref"] = rnd(resample(newC, 3.0))
            c["root_ref"] = c["centerline_ref"][0]
            c["status"] = (c.get("status") or "") + "+pl32f_root_extend"
            e.update(decision="延ばした", extended_ref_px=round(float(cumlen(pts)[-1]) + 2.0, 1))
        else:
            e.update(decision="延ばさない（溝が続かない）")
        ext.append(e)
    rec["root_extend"] = ext
    print("root extend", [(e["id"], e["decision"], e.get("extended_ref_px"), e.get("stop_ja")) for e in ext], "%.1fs" % (time.time() - t0), flush=True)
    corr_out = dict(corr)
    corr_out["pl32f"] = dict(reregister=rec["reregister"], additions=adds,
                             note_ja="仕上げ32 修正の回 1：位置合わせのし直し（回転つき）と、対応なしの爪の扱いの決め直し。画像・マスクは複製していない")
    return rec, corr_out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--fix01", action="store_true", help="修正の回 1 の直し（pl32f_list_steps.py）を足す。出力は --out へ")
    a = ap.parse_args()
    t0 = time.time()
    os.makedirs(a.out, exist_ok=True)
    if a.fix01:
        P["crop"] = [0, 0, 3859, 2594]      # 修正の回 1：手前の波の爪（画の下側）も一覧に入れるので、原画の全部
    L32.P["crop"] = P["crop"]
    paint = L32.Paint()
    off = paint.off
    print("paint %.1fs" % (time.time() - t0), flush=True)
    inv = json.load(open(INV32, encoding="utf-8"))
    claws = inv["claws"]
    byid = {c["id"]: c for c in claws}
    main_ids = [c["id"] for c in claws if c["zone"] == "main"]
    log = dict(changes=[], eye=EYE)
    eye_p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pl32_claw_eye.json")
    EYE2 = json.load(open(eye_p, encoding="utf-8")) if os.path.exists(eye_p) else {}
    log["eye2"] = EYE2

    # ---- 1. b区域の候補
    bc = json.load(open(BCAND, encoding="utf-8"))
    # 既存の爪の中心線と領域のマスク（重複の検査）
    exist = np.zeros((paint.H, paint.W), np.int32)
    exist_cl = np.zeros((paint.H, paint.W), np.uint8)
    for k, c in enumerate(claws):
        if c["zone"] != "main":
            continue
        cv2.fillPoly(exist, [np.round(paint.loc(c["region_polygon_ref"])).astype(np.int32)], k + 1)
        raster_line(exist_cl, paint.loc(c["centerline_ref"]), 1, 1)
    near_cl = cv2.distanceTransform((exist_cl == 0).astype(np.uint8), cv2.DIST_L2, 5) <= P["dup_near_px"]
    added = []
    bdec = []
    nid = P["new_id_start"]
    for cnd in bc["candidates"]:
        k = cnd["k"]
        C = np.asarray(cnd["centerline_ref"], np.float64)
        dec = dict(k=k, length_ref_px=cnd["length_ref_px"])
        if k in EYE["drop"]:
            dec.update(decision="drop", reason_ja=EYE["drop"][k]); bdec.append(dec); continue
        if k in EYE["trim"]:
            s = cumlen(C)
            C = C[s >= s[-1] - P["trim_len_ref_px"]]
            dec["trimmed_ja"] = EYE["trim"][k]
        Q = np.round(paint.loc(resample(C, 1.0))).astype(int)
        Q[:, 0] = np.clip(Q[:, 0], 0, paint.W - 1); Q[:, 1] = np.clip(Q[:, 1], 0, paint.H - 1)
        hit = (exist[Q[:, 1], Q[:, 0]] > 0) | near_cl[Q[:, 1], Q[:, 0]]
        frac = float(hit.mean())
        dec["auto_dup_fraction"] = round(frac, 3)
        if frac >= P["dup_frac"] or k in EYE["dup"]:
            ids_hit = exist[Q[:, 1], Q[:, 0]]
            ids_hit = ids_hit[ids_hit > 0]
            dec.update(decision="dup", dup_of=(claws[int(np.bincount(ids_hit).argmax()) - 1]["id"] if len(ids_hit) else None),
                       reason_ja=("自動（中心線の %.0f%% が既存の爪の中心線から %.0f px 以内か領域の中）" % (100 * frac, P["dup_near_px"]))
                       + ("・目視：" + EYE["dup"][k] if k in EYE["dup"] else ""),
                       eye_agrees=bool(k in EYE["dup"]) == bool(frac >= P["dup_frac"]))
            bdec.append(dec); continue
        cid = "C%03d" % nid
        nid += 1
        rec = {"id": cid, "origin": "pl32_bregion", "zone": "main", "row": "b区域", "seed": "pl32_bregion_k%d" % k,
               "tip_ref": rnd(C[-1]), "root_ref": rnd(C[0]), "centerline_ref": rnd(C), "root_ref_af29": None, "length_ref_px_af29": None,
               "silhouette": False, "over_indigo": None, "polygon_ref_af29": None, "status": "pl32_bregion", "b_region_q16": True,
               "mouth_reason": "美術優先29 の骨格化の根元（分岐の内接円の縁か、白の塊に入る点）"}
        claws.append(rec)
        byid[cid] = rec
        added.append(cid)
        dec.update(decision="add", id=cid)
        bdec.append(dec)
    log["bregion"] = dict(candidates=len(bc["candidates"]), added=len(added), dropped=sum(1 for d in bdec if d["decision"] == "drop"),
                          dups=sum(1 for d in bdec if d["decision"] == "dup"), decisions=bdec)
    print("bregion added %d  %.1fs" % (len(added), time.time() - t0), flush=True)

    # ---- 4. 上側の列に口の規則（設計32 の revise、修正01 の見張りつき）
    up_changed = []
    for c in claws:
        if c["zone"] != "main" or c.get("status") != "root_kept":
            continue
        if c["id"] in EYE2.get("skip_upper_mouth", {}):
            log["changes"].append(dict(id=c["id"], change="上側の口の規則を当てない", reason_ja=EYE2["skip_upper_mouth"][c["id"]]))
            continue
        L_old = float(cumlen(c["centerline_ref"])[-1])
        r = L32.revise(paint, c["centerline_ref"], L_old, None, keep_root=False, guard_on=True)
        if r["status"] in ("mouth", "mouth_exit"):
            newL = float(cumlen(r["centerline"])[-1])
            mv = float(np.hypot(*(np.asarray(r["root"]) - c["root_ref"])))
            up_changed.append(dict(id=c["id"], status=r["status"], root_move_px=round(mv, 1), length_before=round(L_old, 1), length_after=round(newL, 1),
                                   mouth_reason=r["mouth_reason"]))
            c["root_ref_ds32"] = c["root_ref"]
            c["root_ref"] = rnd(r["root"]); c["centerline_ref"] = rnd(r["centerline"])
            c["status"] = "pl32_upper_" + r["status"]; c["mouth_reason"] = r["mouth_reason"]
    log["upper_mouth"] = dict(changed=len(up_changed), list=up_changed)
    print("upper mouth %d  %.1fs" % (len(up_changed), time.time() - t0), flush=True)

    # ---- 5. 名指しの短い爪（目視の判定は pl32_claw_eye.json。無ければ設計32 のまま）
    eye2 = EYE2
    for cid, d in eye2.get("restore_af29_root", {}).items():
        c = byid[cid]
        cl29 = None
        inv29 = json.load(open(L32.INV29, encoding="utf-8"))
        for o in inv29["claws"]:
            if o["id"] == cid:
                cl29 = o["centerline_ref"]
        if cl29 is None:
            continue
        c["root_ref_ds32"] = c["root_ref"]
        c["root_ref"] = rnd(cl29[0]); c["centerline_ref"] = rnd(cl29)
        c["status"] = "pl32_restore_af29_root"; c["mouth_reason"] = d
        log["changes"].append(dict(id=cid, change="美術優先29 の根元へ戻す", reason_ja=d))
    for cid, d in eye2.get("move_root", {}).items():
        c = byid[cid]
        cl, _ = L32.path_between(paint, d["root_ref"], c["tip_ref"])
        if cl is None:
            continue
        c["root_ref_ds32"] = c["root_ref"]
        c["root_ref"] = rnd(cl[0]); c["centerline_ref"] = rnd(cl)
        c["status"] = "pl32_eye_root"; c["mouth_reason"] = d["reason_ja"]
        log["changes"].append(dict(id=cid, change="根元を目視の種へ", reason_ja=d["reason_ja"]))
    for cid, d in eye2.get("merge", {}).items():
        c = byid[cid]
        into = byid[d["into"]]
        # 先端と根元が近い向きでつなぐ（into の先端が c の根元の近くなら into → c、逆なら c → into）
        ci, cc_ = np.asarray(into["centerline_ref"]), np.asarray(c["centerline_ref"])
        if np.hypot(*(ci[-1] - cc_[0])) <= np.hypot(*(cc_[-1] - ci[0])):
            cl = np.concatenate([ci, cc_], 0)
        else:
            cl = np.concatenate([cc_, ci], 0)
        into["root_ref_ds32"] = into["root_ref"]
        into["root_ref"] = rnd(cl[0]); into["centerline_ref"] = rnd(cl)
        into["status"] = "pl32_merged"; into["mouth_reason"] = d["reason_ja"]
        c["_removed"] = d["reason_ja"]
        log["changes"].append(dict(id=cid, change="%s に統合" % d["into"], reason_ja=d["reason_ja"]))
    for cid, why in eye2.get("remove", {}).items():
        byid[cid]["_removed_plain"] = why
        log["changes"].append(dict(id=cid, change="消す", reason_ja=why))
    for cid, why in eye2.get("keep", {}).items():
        log["changes"].append(dict(id=cid, change="設計32 のまま（長さ）", reason_ja=why))
    removed = list(inv.get("removed_claws", []))
    for c in list(claws):
        if c.get("_removed_plain"):
            removed.append(dict(id=c["id"], origin=c["origin"], kind="消した", reason_ja=c["_removed_plain"], fix="仕上げ32"))
            claws.remove(c)
    for c in list(claws):
        if c.get("_removed"):
            removed.append(dict(id=c["id"], origin=c["origin"], kind="統合", merged_into=next(v["into"] for k_, v in eye2["merge"].items() if k_ == c["id"]),
                                reason_ja=c["_removed"], fix="仕上げ32"))
            claws.remove(c)
    byid = {c["id"]: c for c in claws}
    fixlog, corr_out = None, None
    if a.fix01:
        fixlog, corr_out = fix01_steps(paint, claws, byid, eye2, log, t0)
        byid = {c["id"]: c for c in claws}

    # ---- 2. 測地の競り合いで領域を作る（主浪と b区域の全部。修正の回 1 では手前の波の爪も）
    mains = [c for c in claws if c["zone"] in ("main", "front")]
    Lb = np.zeros((paint.H, paint.W), np.int32)
    white_dt = cv2.distanceTransform(paint.white.astype(np.uint8), cv2.DIST_L2, 5)
    lim = np.zeros(len(mains) + 1, np.int32)
    for i, c in enumerate(mains):
        C = resample(paint.loc(c["centerline_ref"]), 0.5)
        Q = np.round(C).astype(int)
        Q[:, 0] = np.clip(Q[:, 0], 0, paint.W - 1); Q[:, 1] = np.clip(Q[:, 1], 0, paint.H - 1)
        hw = white_dt[Q[:, 1], Q[:, 0]]
        hw = hw[hw > 0]
        hwm = float(np.median(hw)) if len(hw) else 4.0
        c["_hw"] = hwm
        lim[i + 1] = int(np.clip(round(P["grow_factor"] * hwm), P["grow_min"], P["grow_max"]))
        ok = paint.passable[Q[:, 1], Q[:, 0]]
        Lb[Q[ok, 1], Q[ok, 0]] = np.where(Lb[Q[ok, 1], Q[ok, 0]] == 0, i + 1, Lb[Q[ok, 1], Q[ok, 0]])
    Lg = grow_labels(Lb, paint.passable, lim, int(lim.max()))
    print("grow %.1fs" % (time.time() - t0), flush=True)
    regions = {}
    for i, c in enumerate(mains):
        lab = i + 1
        ys, xs = np.nonzero(Lg == lab)
        if not len(xs):
            continue
        x0, y0 = xs.min() - 2, ys.min() - 2
        x1, y1 = xs.max() + 3, ys.max() + 3
        x0, y0 = max(0, x0), max(0, y0)
        M = Lg[y0:y1, x0:x1] == lab
        C = paint.loc(c["centerline_ref"])
        # 口の弦：根元の接線の後ろ側で、根元から広がりの半径 + 3 px の内の画素を落とす
        if len(C) >= 3:
            tvec = C[min(3, len(C) - 1)] - C[0]
            tvec /= max(np.linalg.norm(tvec), 1e-9)
            yy, xx = np.mgrid[y0:y1, x0:x1]
            rel = np.stack([xx - C[0][0], yy - C[0][1]], -1)
            back = (rel @ tvec < -P["mouth_back_px"]) & (np.hypot(rel[..., 0], rel[..., 1]) <= lim[lab] + 3)
            M &= ~back
        Mo = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_OPEN, np.ones((P["open_px"], P["open_px"]), np.uint8)).astype(bool)
        near = np.zeros_like(M, np.uint8)
        raster_line(near, C - [x0, y0], 1, 5)
        spikes_removed = int((M & ~Mo & ~near.astype(bool)).sum())
        M = Mo | (M & near.astype(bool))
        n_, cc = cv2.connectedComponents(M.astype(np.uint8), connectivity=8)
        if n_ > 2:
            q = np.round(C - [x0, y0]).astype(int)
            q[:, 0] = np.clip(q[:, 0], 0, M.shape[1] - 1); q[:, 1] = np.clip(q[:, 1], 0, M.shape[0] - 1)
            keep = np.unique(cc[q[:, 1], q[:, 0]])
            keep = keep[keep > 0]
            M = np.isin(cc, keep)
        # 小さな穴（線の欠片でない、JPEG の斑）を埋める
        inv_ = (~M).astype(np.uint8)
        n2, cc2, st2, _ = cv2.connectedComponentsWithStats(inv_, connectivity=4)
        for k2 in range(1, n2):
            if st2[k2, 4] < P["hole_px"] and st2[k2, 0] > 0 and st2[k2, 1] > 0 and st2[k2, 0] + st2[k2, 2] < M.shape[1] and st2[k2, 1] + st2[k2, 3] < M.shape[0]:
                M[cc2 == k2] = True
        regions[c["id"]] = (x0, y0, M)
        c["_spikes_removed_px"] = spikes_removed

    # ---- 3. 中心線を領域の真ん中へ
    for c in mains:
        if c["id"] not in regions:
            continue
        x0, y0, M = regions[c["id"]]
        C = paint.loc(c["centerline_ref"]) - [x0, y0]
        R = M.copy()
        raster_line(R.view(np.uint8), C, 1, 1)
        R = R.astype(bool)

        def snapi(p):
            q = np.round(p).astype(int)
            ys, xs = np.nonzero(R)
            k = int(np.argmin((xs - q[0]) ** 2 + (ys - q[1]) ** 2))
            return int(xs[k]), int(ys[k])
        pth = centre_path(R, snapi(C[0]), snapi(C[-1]), P["centre_cost_eps"])
        if pth is None or len(pth) < 3:
            c["_centre_refit"] = False
            continue
        newC = resample(smooth(pth, 5), 3.0) + [x0, y0]
        dmax = float(np.max(np.min(np.hypot(*(newC[:, None, :] - C[None, :, :] - [x0, y0]).transpose(2, 0, 1)), axis=1)))
        c["centerline_ref_ds32"] = c["centerline_ref"]
        c["centerline_ref"] = rnd(paint.glob(newC))
        c["root_ref"] = c["centerline_ref"][0]
        c["tip_ref"] = c["centerline_ref"][-1]
        c["_centre_refit"] = True
        c["centre_refit_max_shift_ref_px"] = round(dmax, 1)
    print("centre %.1fs" % (time.time() - t0), flush=True)

    # 多角形
    for c in mains:
        if c["id"] in regions:
            c["region_polygon_ref_ds32"] = c.get("region_polygon_ref")
            c["region_polygon_ref"] = rnd(L32.mask_polygon(regions[c["id"]], off))
        c["root_display"] = rnd(r2d(np.asarray(c["root_ref"])), 2)
        c["tip_display"] = rnd(r2d(np.asarray(c["tip_ref"])), 2)
        c["length_ref_px"] = round(float(cumlen(c["centerline_ref"])[-1]), 1)
    for c in claws:
        if c["zone"] != "main":
            c.setdefault("root_display", rnd(r2d(np.asarray(c["root_ref"])), 2))
            c.setdefault("tip_display", rnd(r2d(np.asarray(c["tip_ref"])), 2))

    fronts = [c for c in mains if c["zone"] == "front"]
    mains = [c for c in mains if c["zone"] == "main"]
    # ---- 7. 記録
    # 重なり（多角形を塗って数える）・他の爪の領域の中の根元
    idimg = np.zeros((paint.H, paint.W), np.int32)
    over_pairs = {}
    for k, c in enumerate(mains):
        M = np.zeros((paint.H, paint.W), np.uint8)
        if not c.get("region_polygon_ref"):
            continue
        cv2.fillPoly(M, [np.round(paint.loc(c["region_polygon_ref"])).astype(np.int32)], 1)
        hit = idimg[M > 0]
        for o in np.unique(hit[hit > 0]):
            n_ = int((hit == o).sum())
            if n_ > 0:
                over_pairs[(mains[o - 1]["id"], c["id"])] = n_
        idimg[(M > 0) & (idimg == 0)] = k + 1
    roots_in_other = []
    for k, c in enumerate(mains):
        q = np.round(paint.loc(c["root_ref"])).astype(int)
        v = idimg[min(max(q[1], 0), paint.H - 1), min(max(q[0], 0), paint.W - 1)]
        if v > 0 and v != k + 1:
            roots_in_other.append(dict(id=c["id"], inside=mains[v - 1]["id"]))
    # 設計32 の同じ数え方（設計32 の多角形）
    idimg32 = np.zeros((paint.H, paint.W), np.int32)
    over32 = 0
    inv0 = json.load(open(INV32, encoding="utf-8"))
    m32 = [c for c in inv0["claws"] if c["zone"] == "main"]
    for k, c in enumerate(m32):
        M = np.zeros((paint.H, paint.W), np.uint8)
        cv2.fillPoly(M, [np.round(paint.loc(c["region_polygon_ref"])).astype(np.int32)], 1)
        hit = idimg32[M > 0]
        over32 += len(np.unique(hit[hit > 0]))
        idimg32[(M > 0) & (idimg32 == 0)] = k + 1
    # 根元の先で指が続く疑い（設計32 の検査をそのまま）
    cont = {}
    for c in mains:
        f_, w0 = L32.continues_past_root(paint, c["centerline_ref"])
        if f_ is not None and f_ >= L32.P["cont_frac"]:
            cont[c["id"]] = round(f_, 2)
    # IoU（D25 を決め直した定義）
    inv29z = json.load(open(L32.INV29, encoding="utf-8"))["zones"][0]["points_ref"]
    zone_m = T.poly_mask((paint.H, paint.W), (np.asarray(inv29z, np.float64) - off).tolist())
    zone_b = T.poly_mask((paint.H, paint.W), (np.asarray(bc["zone_ref"], np.float64) - off).tolist())
    zone = zone_m | zone_b
    dark = paint.dark
    dline = cv2.distanceTransform((~dark).astype(np.uint8), cv2.DIST_L2, 5)
    thick = cv2.morphologyEx(paint.passable.astype(np.uint8), cv2.MORPH_OPEN, T.disk(P["truth_open_r"])).astype(bool)
    truth = paint.passable & zone & (dline <= P["truth_line_px"]) & ~thick
    inv_now = idimg > 0
    inv_32 = idimg32 > 0
    inv_now_z = inv_now & zone
    inv_32_z = inv_32 & zone

    def iou(Aa, Bb):
        i_ = int((Aa & Bb).sum()); u_ = int((Aa | Bb).sum())
        return dict(iou=round(i_ / max(u_, 1), 4), coverage=round(i_ / max(int(Bb.sum()), 1), 4), precision=round(i_ / max(int(Aa.sum()), 1), 4),
                    inventory_px=int(Aa.sum()), truth_px=int(Bb.sum()))
    iou_rec = dict(rule_ja=("D25 を決め直した定義（摺りの工程の調べ、記録 第1節）：爪＝墨版の藍の線で区切られた、紙の地（摺らない白）と水色の版の画素。"
                            "真値＝主浪と b区域の範囲の中で、藍（墨版の線と藍の版）から %.0f px 以内の紙・水色の画素（半径 %d px の円が入る厚い白・水色の塊を除く）。"
                            "一覧の爪の多角形の和と比べる（主浪と b区域。右側の爪は数えない）") % (P["truth_line_px"], P["truth_open_r"]),
                   pl32=iou(inv_now_z, truth), ds32_same_truth=iou(inv_32_z, truth))
    # 影の割合（設計32 の数え方の簡易：爪の領域の水色の割合）
    pale_frac = []
    for c in mains:
        if c["id"] in regions:
            x0, y0, M = regions[c["id"]]
            pl = paint.pale[y0:y0 + M.shape[0], x0:x0 + M.shape[1]]
            pale_frac.append(float((M & pl).sum() / max(1, M.sum())))
    # 支の判定（記録。型は ds33_claw_rig.py が branch_inside_tol で決める）
    branches = []
    for A_ in mains:
        CA = np.asarray(A_["centerline_ref"], np.float64)
        LA = cumlen(CA)
        if LA[-1] < 1:
            continue
        for B_ in mains:
            if A_ is B_ or float(cumlen(B_["centerline_ref"])[-1]) > 1.05 * LA[-1]:
                continue
            d = np.hypot(*(CA - np.asarray(B_["root_ref"])).T)
            k = int(np.argmin(d))
            sa = LA[k] / LA[-1]
            if P["branch_sigma"][0] <= sa <= P["branch_sigma"][1] and d[k] <= 2.0 * A_["_hw"] + P["branch_add_px"]:
                branches.append(dict(parent=A_["id"], branch=B_["id"], sigma=round(sa, 3), dist_ref_px=round(float(d[k]), 1)))
    lens = {c["id"]: c["length_ref_px"] for c in mains}
    chk = dict(
        schema="GreatWave.Polish32.claw_list_checks/1",
        counts=dict(total=len(claws), main=len(mains), right=len([c for c in claws if c["zone"] == "right"]),
                    front=len([c for c in claws if c["zone"] == "front"]),
                    by_row={r_: sum(1 for c in mains if c["row"] == r_) for r_ in sorted(set(c["row"] for c in mains))},
                    b_region=sum(1 for c in mains if c.get("b_region_q16")), added_bregion=len(added)),
        overlap_pairs_pl32=len([1 for v in over_pairs.values() if v > 5]), overlap_pairs_pl32_any=len(over_pairs),
        overlap_pairs_ds32_same_count=over32,
        overlap_rule_ja="多角形を順に塗り、先に塗った爪と重なる画素がある組の数（pl32 は 5 px を超える組と全部）",
        roots_inside_other_region=roots_in_other,
        spikes_removed_px=dict(total=int(sum(c.get("_spikes_removed_px", 0) for c in mains)),
                               claws_with_any=int(sum(1 for c in mains if c.get("_spikes_removed_px", 0) > 0))),
        continues_past_root=cont,
        iou=iou_rec,
        pale_fraction=dict(p10=round(float(np.percentile(pale_frac, 10)), 3), median=round(float(np.median(pale_frac)), 3),
                           p90=round(float(np.percentile(pale_frac, 90)), 3)),
        centre_refit=dict(done=int(sum(1 for c in mains if c.get("_centre_refit"))), failed=[c["id"] for c in mains if c.get("_centre_refit") is False],
                          max_shift_ref_px=dict(median=float(np.median([c.get("centre_refit_max_shift_ref_px", 0) for c in mains])),
                                                max=float(np.max([c.get("centre_refit_max_shift_ref_px", 0) for c in mains])))),
        lengths_named={k_: dict(ds32=next((c["length_ref_px"] for c in m32 if c["id"] == k_), None), pl32=lens.get(k_)) for k_ in ("C066", "C109", "C112", "C113", "C174", "C002")},
        branch_rule_ja=("支：主爪 A より短い（1.05 倍まで）爪 B の根元が、A の中心線の 10〜95%% の所で、A の指の白の半幅の 2 倍 + %.0f px 以内。"
                        "領域を分け合うので「根元が A の領域の中」は使わない（ds33_claw_rig.py へは branch_inside_tol で渡す）") % P["branch_add_px"],
        branch_candidates=branches,
        fix01=fixlog, front_claws=[c["id"] for c in fronts],
        log=log, elapsed_s=round(time.time() - t0, 1))
    for c in claws:
        for k_ in [k_ for k_ in c if k_.startswith("_")]:
            del c[k_]
    inv_out = dict(inv)
    inv_out["number"] = "仕上げ32（設計32 の一覧を土台に、b区域の爪を加え、爪ごとに領域を墨版の線へ、中心線を領域の真ん中へ合わせた）"
    inv_out["definition_region_ja"] = ("D25 を決め直した定義（仕上げ32、摺りの工程の調べ）：爪＝墨版の藍の線で区切られた紙の地（摺らない白）と水色の版の画素。"
                                       "中心線を種にした測地の競り合いで、各爪は指の白の半幅の 2.2 倍（6〜30 px）まで広がり、爪どうしは画素を分け合わない")
    inv_out["claws"] = claws
    inv_out["removed_claws"] = removed
    inv_out["counts"] = chk["counts"]
    inv_out["pl32"] = dict(params=P, eye=EYE, source_inventory=dict(path=INV32.replace(REPO + "/", ""), sha256=sha(INV32)),
                           bregion_candidates=dict(path=BCAND.replace(REPO + "/", ""), sha256=sha(BCAND)))
    json.dump(inv_out, open(os.path.join(a.out, "ds32_claw_inventory.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(chk, open(os.path.join(a.out, "pl32_claw_list_checks.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1,
              default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o))
    if corr_out is not None:
        json.dump(corr_out, open(os.path.join(a.out, "ds32_user100_correspondence_pl32f.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    np.save(os.path.join(a.out, "_idimg.npy"), idimg)
    np.save(os.path.join(a.out, "_truth.npy"), truth)
    print(json.dumps({k: chk[k] for k in ("counts", "overlap_pairs_pl32", "overlap_pairs_ds32_same_count", "spikes_removed_px", "iou", "pale_fraction",
                                          "lengths_named")}, ensure_ascii=False)[:3000])
    print("roots_in_other", len(roots_in_other), "cont", cont, "branches", len(branches))
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
