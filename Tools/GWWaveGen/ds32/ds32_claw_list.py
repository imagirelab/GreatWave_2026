# -*- coding: utf-8 -*-
"""設計32：爪の一覧の修正（計画 第6節の 1〜4、使える水準）。

入力（読むだけ）：
  - 美術優先29 の一覧 Tools/PaintingTruth/claws29/claw_inventory.json（final1、153 本。ID C001〜C153 を保つ）
  - 高解像度原画 Docs/References/Met_JP1847_DP130155.jpg と番号23 の真値 v0.2（空・黄土・5 色の Lloyd 中心）
  - 利用者の爪100本の位置合わせ（ds32_user100_register.py の出力 ds32_user100_registration.json）と、
    利用者のマスク（G:/research/爪形分析、読み取りのみ。メモリの中で重なりの計算にだけ使い、書き出さない）
  - b区域の帯（Tools/GWWaveGen/kstar3/candA4_band_targets.json、原画視点の表示 px）

やること：
  1. 爪の領域（D25 の仮の定義）：白の指だけでなく、爪を囲む藍の輪郭線の内側（白＋水色の影）。中心線の各点で法線の両側へ、
     通れる画素（白・水色で、空・黄土でない）を藍（mix・藍中・藍濃）か空に当たるまでたどり、その断面の和を爪の領域にする。
  2. 起点（根元）の規則：先端から根元へ断面をたどり、片側が開く（40 px の中で藍に当たらない）か、幅が急に広がる所を
     「口」とし、その一つ手前の断面の中央を根元にする。中心線は断面の中点をなめらかにつないだもの（口の中央から滑らかに入る）。
     根元が口に届かない爪は、断面の中点をたどって根元の側へ延ばす（最大 80 px）。
  3. 取りこぼしの追加：127 の下の爪（進行役の目視の種）と、利用者の100本のうち一覧のどの爪とも対応しない爪（位置合わせが確かで、
     主浪の波頭か b区域にあるもの）を、利用者の根元・先端の位置を種にして、こちらの方法（通れる画素の最短路 → 1・2）で作る。
  4. ID：変えた爪も美術優先29 の ID を保つ。加えた爪は C154 から。消した爪は理由とともに対応表に残す。右側の爪は触らない（低優先・未修正）。

出力（Git 対象外、Unity/Build/Design/32/list+ids/）：ds32_claw_inventory.json、ds32_user100_correspondence.json、ds32_claw_list_checks.json と図。
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
sys.path.insert(0, REPO + "/Tools/PaintingTruth")
import truthlib as T  # noqa: E402

INV29 = REPO + "/Tools/PaintingTruth/claws29/claw_inventory.json"
PRM29 = REPO + "/Tools/PaintingTruth/claws29/af29_params.json"
PALETTE = REPO + "/Tools/PaintingTruth/targets/palette.json"
BAND = REPO + "/Tools/GWWaveGen/kstar3/candA4_band_targets.json"
OUT = REPO + "/Unity/Build/Design/32/list+ids"
REG = OUT + "/ds32_user100_registration.json"
USER_CROPS = "G:/research/爪形分析/final_100_claws_centerlines_from_fill_masks_v3"
CLASS_NAMES = ["white", "mizuiro", "mix", "ai_mid", "ai_dark"]

P = dict(
    crop=[180, 0, 2700, 1560],        # 計算する原画の範囲 x0, y0, x1, y1（主浪・b区域・左の群）
    station_step=2.0,                 # 断面の間隔（原画 px）
    ray_max=40.0,                     # 断面の片側の最大（これより遠くまで藍に当たらなければ「開く」）
    ray_step=0.5,
    mouth_min_from_tip_frac=0.25,     # 口を探し始める先端からの弧長（元の長さに対する割合）
    mouth_min_from_tip_px=10.0,
    widen_ratio=2.4,                  # 幅が直前 8 断面の中央値のこの倍を超え、
    widen_abs=10.0,                   # かつ 10 px 以上広がると「口」
    section_grow_ratio=1.8,           # 断面の片側の広がりの上限（直前 8 断面の中央値のこの倍 + 3 px）
    section_grow_abs=3.0,
    side_jump_ratio=2.2,              # 片側の距離が直前 8 断面の中央値のこの倍を超え、
    side_jump_abs=8.0,                # かつ 8 px 以上遠くなると「口」
    extend_max=80.0,                  # 根元が口に届かないときに延ばす最大
    smooth_win=5,
    shadow_ray=30.0,                  # 影の検査：指から藍の線までの最大
    shadow_incl_min=0.50,             # 囲まれた影のうち領域に入る割合の下限（これ未満を「影を外した爪」と数える。進行役の判断、Q24）
    shadow_min_px=20,                 # 囲まれた影がこれ未満の爪は検査の対象外（影なし）
    match_overlap=0.35,               # 利用者の爪と一覧の爪の対応：利用者のマスクのうち一覧の爪の領域に入る割合
    match_tip_px=30.0,
    reg_ncc_min=0.70,                 # 位置合わせが確かとみなす ECC の後の NCC
    new_id_start=154,
    dedupe_overlap=0.5,               # 加える爪の領域のうち、一覧の爪の領域と重なる割合がこれ以上なら同じ爪
    root_move_report_px=8.0,
    band_pad_display_px=30.0,
    breaks_s=[460.0, 1101.9], x_split=1537.0,  # 美術優先29 の列の境目（凍結）
    manual_overrides={
        "C110": {"root_ref": [1868.0, 890.0], "tip_ref": [1863.0, 931.0],
                 "note_ja": "利用者の指摘「爪110 の起始点が違う」。美術優先29 の C110 は V 字の鉤の中の 15 px の白だけで、根元が左下にあった。"
                            "原画では、左の線（x 1845→1861、y 880→930）と右の線（y 925→880）の間の白い指が上の白の胴から下りて、V 字の鉤で終わる。"
                            "進行役の目視で根元の種を上の口（y 約 890）、先端の種を鉤の中に置き、口と中心線は規則で決め直した"},
        # 修正01（独立の検査の指摘 1）：美術優先29 の C105 は、C110 の指（V 字の鉤から上の口まで）と、その上の房（上の線と下の線に囲まれ、
        # 中が水色の影の房）の下の白の縁を 1 本に読み、根元が C110 の鉤の中にあった。C110 の指を C110 へ移したので、C105 は房だけにする。
        "C105": {"root_ref": [1873.0, 873.0], "tip_ref": [1930.0, 891.0],
                 "note_ja": "修正01（独立の検査の指摘：C105 の領域が C110 の指と C107 を呑み込む）。房（上の線 x 1860→1945、y 855→835→890 と、"
                            "下の線 x 1880→1920、y 905→884→893 に囲まれ、中が水色の影）の左の開き（口、x 約 1862〜1880）の右に根元の種、"
                            "美術優先29 の先端（房の右下、二つの線の端の間）に先端の種を置き、口と中心線は規則で決め直した。領域は房の中だけで、C110 の指の上で止まる"},
    },
    # 修正01（独立の検査の指摘 1）：C107 は、C105 の房の上の白の縁（上の線の内側）で、D25 の仮の定義（藍の輪郭線の内側）では C105 の領域の中にある
    # （修正の前、C107 の中心線の 100%、面積の 98.7% が C105 の中）。同じ房なので C105 に統合し、C107 は理由とともに消した爪の表に残す
    merged={"C107": {"into": "C105",
                     "reason_ja": "C105 の房（上の線と下の線に囲まれ、中が水色の影）の上の白の縁で、D25 の仮の定義（藍の輪郭線の内側）では同じ房の中にある。"
                                  "修正の前の C107 は中心線の 100%・面積の 98.7% が C105 の領域の中だった。C105 に統合した（修正01、独立の検査の指摘 1）"}},
    # 修正01（独立の検査の指摘 2）：口の規則が先端の鉤のすぐ上や曲がり目を口と読み、爪を短く切った。元の長さのこの倍未満に縮むときは、
    # 両側の線（藍）がどちらも終わる所（指が胴から離れる所）だけを口と認める。なければ美術優先29 の根元の断面の中央を根元にする
    short_guard_frac=0.5,
    exit_run=2,                       # 両側の線が終わる断面が続く数
    # 修正01（独立の検査の指摘 3）：加える爪どうし・一覧の爪との重複の検査
    dup_overlap_min=0.5,              # 領域の重なりが小さい方の面積のこの割合以上
    dup_centerline_in=0.5,            # 相手の中心線のこの割合以上が領域の中（どちらの向きでも）
    dup_swap_px=15.0,                 # 根元が相手の先端のこの距離以内で、向きが逆（なす角 > 120°）
    dup_angle_deg=120.0,
    # 修正01：加えた爪の ID を修正の前（2026-09-29 20:21 の初回の出力）と同じに保つ（種 → ID）。消した爪の ID は欠番として残す
    id_pin={"127の下": "C154", "claw003": "C155", "claw042": "C156", "claw046": "C157", "claw052": "C158", "claw055": "C159",
            "claw056": "C160", "claw057": "C161", "claw058": "C162", "claw060": "C163", "claw061": "C164", "claw062": "C165",
            "claw063": "C166", "claw064": "C167", "claw065": "C168", "claw071": "C169", "claw072": "C170", "claw075": "C171",
            "claw077": "C172", "claw081": "C173", "claw083": "C174", "claw087": "C175"},
    # 修正01 の検査（規則とは別の組み立て）
    contain_check=0.5,                # 他の爪の中心線のこの割合以上を含む領域の組を数える
    cont_steps=10,                    # 根元の先の 2 px ごとの断面の数（20 px）
    cont_frac=0.6,                    # そのうちこの割合以上で両側が藍に閉じていれば「根元の先で指が続く（切り詰め）」
    manual_seeds=[
        {"name": "127の下", "root_ref": [1690.0, 862.0], "tip_ref": [1661.0, 918.0],
         "note_ja": "利用者の指摘「127下面那一个」。進行役の目視で、C127 の根元のすぐ下の白の胴から左下へ垂れる指の根元と先端の近くに種を置いた（口と中心線は規則で決める）"},
    ],
)


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def _np(o):
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o).__name__)


def jdump(p, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=1, default=_np)


def rnd(v, k=2):
    if isinstance(v, (list, tuple, np.ndarray)):
        return [rnd(x, k) for x in v]
    return None if v is None else round(float(v), k)


def cumlen(C):
    return np.r_[0.0, np.cumsum(np.hypot(*np.diff(C, axis=0).T))]


def resample(C, step):
    C = np.asarray(C, np.float64)
    s = cumlen(C)
    if s[-1] < 1e-9:
        return C[:1].copy()
    n = max(2, int(math.ceil(s[-1] / step)) + 1)
    q = np.linspace(0, s[-1], n)
    return np.stack([np.interp(q, s, C[:, 0]), np.interp(q, s, C[:, 1])], 1)


def smooth(C, win):
    if len(C) < 3 or win < 2:
        return C
    k = np.ones(win) / win
    pad = win // 2
    Cp = np.pad(C, ((pad, pad), (0, 0)), mode="edge")
    S = np.stack([np.convolve(Cp[:, i], k, mode="valid") for i in range(2)], 1)[:len(C)]
    S[0], S[-1] = C[0], C[-1]
    return S


def normals(C):
    t = np.gradient(C, axis=0)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return np.stack([-t[:, 1], t[:, 0]], 1), t


# ---------------------------------------------------------------- 画素の分類
class Paint:
    def __init__(self):
        spec = T.load_spec()
        man = T.load_manual()
        ex = spec["extraction"]
        polys = man["polygons_ref"]
        self.spec = spec
        rgb = T.imread_rgb(T.repo_abs(spec["reference"]["path"]))
        self.rgb_full = rgb
        lab = T.srgb8_to_lab(rgb).astype(np.float32)
        fills = [polys["sky_fill_cartouche"]["points"], polys["sky_fill_signature"]["points"]]
        barriers = list(man.get("barriers_ref", {}).values())
        sky = T.segment_sky(lab, ex["sky"], fills, barriers)
        och = T.ochre_mask(lab, sky, ex["ochre"])
        och = cv2.dilate(och.astype(np.uint8), T.disk(3)).astype(bool)
        x0, y0, x1, y1 = P["crop"]
        self.off = np.array([x0, y0], np.float64)
        L = lab[y0:y1, x0:x1]
        labs = np.stack([cv2.GaussianBlur(L[..., i], (0, 0), 1.0) for i in range(3)], -1)
        pal = T.load_json(PALETTE)
        cen = np.array([pal["classes_lloyd_centers_lab"][k] for k in CLASS_NAMES], np.float32)
        best = np.full(labs.shape[:2], np.inf, np.float32)
        cls = np.zeros(labs.shape[:2], np.uint8)
        for k in range(5):
            d = ((labs - cen[k]) ** 2).sum(-1)
            m = d < best
            best[m] = d[m]
            cls[m] = k
        self.cls = cls
        self.sky = sky[y0:y1, x0:x1]
        self.och = och[y0:y1, x0:x1]
        self.white = (cls == 0) & ~self.sky & ~self.och
        self.pale = (cls == 1) & ~self.sky & ~self.och
        self.passable = self.white | self.pale
        self.dark = (cls >= 2) & ~self.sky
        self.H, self.W = cls.shape
        self.rgb = rgb[y0:y1, x0:x1]

    def loc(self, pts):
        return np.asarray(pts, np.float64) - self.off

    def glob(self, pts):
        return np.asarray(pts, np.float64) + self.off


def cast(paint, C, nrm, sign, mask=None, rmax=None):
    """断面の片側：C（局所 px）から sign·nrm の向きへ、通れない画素に当たるまでの距離と理由（0 開く・1 藍・2 空/黄土・3 画像の外）。"""
    rmax = P["ray_max"] if rmax is None else rmax
    ds = np.arange(P["ray_step"], rmax + 1e-9, P["ray_step"])
    Q = C[:, None, :] + sign * ds[None, :, None] * nrm[:, None, :]
    xi = np.round(Q[..., 0]).astype(int)
    yi = np.round(Q[..., 1]).astype(int)
    inb = (xi >= 0) & (xi < paint.W) & (yi >= 0) & (yi < paint.H)
    xc, yc = np.clip(xi, 0, paint.W - 1), np.clip(yi, 0, paint.H - 1)
    ok = (paint.passable if mask is None else mask)[yc, xc] & inb
    stop = ~ok
    first = np.where(stop.any(1), stop.argmax(1), -1)
    dist = np.where(first >= 0, ds[np.maximum(first, 0)] - P["ray_step"], rmax)
    why = np.zeros(len(C), int)
    for i, f in enumerate(first):
        if f < 0:
            why[i] = 0
        elif not inb[i, f]:
            why[i] = 3
        elif paint.dark[yc[i, f], xc[i, f]]:
            why[i] = 1
        else:
            why[i] = 2
    return dist, why


def sections(paint, C, nrm=None):
    if nrm is None:
        nrm, tan = normals(C)
    else:
        tan = np.stack([nrm[:, 1], -nrm[:, 0]], 1)
    dl, wl = cast(paint, C, nrm, -1.0)
    dr, wr = cast(paint, C, nrm, +1.0)
    # 開いた側は、白だけの幅（指の縁）に留める（領域が胴へ広がらないように）
    dlw, _ = cast(paint, C, nrm, -1.0, paint.white)
    drw, _ = cast(paint, C, nrm, +1.0, paint.white)
    dl_r = np.where(wl == 0, np.minimum(dlw, P["ray_max"]), dl)
    dr_r = np.where(wr == 0, np.minimum(drw, P["ray_max"]), dr)
    return dict(C=C, n=nrm, t=tan, dl=dl, dr=dr, wl=wl, wr=wr, dl_r=dl_r, dr_r=dr_r)


def extend_rootward(paint, C_tip_to_root):
    """根元の側へ、断面の中点をたどって延ばす（口に届かない爪のため）。戻り値：延ばした点（局所、先端→根元の続き）。"""
    C = C_tip_to_root
    ext = []
    p = C[-1].copy()
    t = C[-1] - C[max(0, len(C) - 6)]
    t /= max(np.linalg.norm(t), 1e-9)
    step = P["station_step"]
    for _ in range(int(P["extend_max"] / step)):
        q = p + step * t
        n = np.array([-t[1], t[0]])
        sd = sections(paint, np.array([q]), np.array([n]))
        if sd["wl"][0] == 0 or sd["wr"][0] == 0:
            ext.append(q)
            break
        mid = q + 0.5 * (sd["dr"][0] - sd["dl"][0]) * n
        if not paint.passable[int(np.clip(round(mid[1]), 0, paint.H - 1)), int(np.clip(round(mid[0]), 0, paint.W - 1))]:
            break
        t_new = mid - p
        if np.linalg.norm(t_new) < 1e-6:
            break
        t = 0.6 * t + 0.4 * t_new / np.linalg.norm(t_new)
        t /= np.linalg.norm(t)
        p = mid
        ext.append(p.copy())
    return np.array(ext) if ext else np.zeros((0, 2))


def find_mouth(sd, L_old):
    """先端（i=0）から根元へ、片側が開くか幅が急に広がる最初の断面（2 つ続く）。戻り値：口の番号 m（None なら見つからない）と理由。"""
    n = len(sd["C"])
    s = cumlen(sd["C"])
    w = sd["dl"] + sd["dr"]
    closed = (sd["wl"] != 0) & (sd["wr"] != 0)
    smin = max(P["mouth_min_from_tip_px"], P["mouth_min_from_tip_frac"] * L_old)
    flags = np.zeros(n, bool)
    why = [""] * n
    for i in range(n):
        if s[i] < smin:
            continue
        prev = w[max(0, i - 8):i][closed[max(0, i - 8):i]]
        med = float(np.median(prev)) if len(prev) else None
        if not closed[i]:
            flags[i] = True
            why[i] = "片側が開く"
        elif med is not None and w[i] > P["widen_ratio"] * med and w[i] - med > P["widen_abs"]:
            flags[i] = True
            why[i] = "幅が急に広がる"
        else:
            for dd in (sd["dl"], sd["dr"]):
                pv = dd[max(0, i - 8):i][closed[max(0, i - 8):i]]
                if len(pv):
                    md = float(np.median(pv))
                    if dd[i] > P["side_jump_ratio"] * max(md, 2.0) and dd[i] - md > P["side_jump_abs"]:
                        flags[i] = True
                        why[i] = "片側が急に遠くなる"
    for i in range(1, n - 1):
        if flags[i] and flags[i + 1]:
            return i, why[i]
    if n >= 2 and flags[n - 1]:
        return n - 1, why[n - 1]
    return None, ""


def find_exit(sd, i0, i1):
    """修正01：両側の線が終わる所。i0 から i1 の手前まで根元へ、両側とも 40 px の中で藍に当たらない断面（開くか空）が
    P["exit_run"] 続く最初の所。戻り値：番号か None。"""
    both = (sd["wl"] != 1) & (sd["wr"] != 1)
    run = P["exit_run"]
    for i in range(max(0, i0), min(i1, len(both)) - run + 1):
        if both[i:i + run].all():
            return i
    return None


def region_from_sections(paint, sd, m, finger_mask=None):
    """断面 0..m−1 の和の領域（局所の画素マスク）。"""
    C, n = sd["C"][:m], sd["n"][:m]
    dl, dr = sd["dl_r"][:m].copy(), sd["dr_r"][:m].copy()
    # 1 断面だけ細い隙間を遠くまで通った光線（とげ）を落とす：5 断面の移動中央値 + 2 px を上限にする
    if len(dl) >= 5:
        def med5(a):
            ap_ = np.pad(a, 2, mode="edge")
            return np.median(np.stack([ap_[k:k + len(a)] for k in range(5)], 0), 0)
        dl = np.minimum(dl, med5(dl) + 2.0)
        dr = np.minimum(dr, med5(dr) + 2.0)
    # 先端から根元へ、各断面の片側を直前 8 断面（留めた後の値）の中央値の 1.8 倍 + 3 px までに留める（根元の近くで胴の白へ広がる房を落とす）
    for dd in (dl, dr):
        for i in range(3, len(dd)):
            ref_ = float(np.median(dd[max(0, i - 8):i]))
            dd[i] = min(dd[i], P["section_grow_ratio"] * ref_ + P["section_grow_abs"])
    # 口の手前の 3 断面は、その前の 8 断面の中央値の 1.5 倍（+2 px）までにする（口の縁で線の端をなめる光線のとげを落とす）
    if len(dl) >= 8:
        for dd in (dl, dr):
            ref_ = float(np.median(dd[max(0, len(dd) - 11):len(dd) - 3]))
            dd[len(dd) - 3:] = np.minimum(dd[len(dd) - 3:], 1.5 * ref_ + 2.0)
    Lp = C - dl[:, None] * n
    Rp = C + dr[:, None] * n
    x0 = int(max(0, np.floor(min(Lp[:, 0].min(), Rp[:, 0].min())) - 3))
    y0 = int(max(0, np.floor(min(Lp[:, 1].min(), Rp[:, 1].min())) - 3))
    x1 = int(min(paint.W, np.ceil(max(Lp[:, 0].max(), Rp[:, 0].max())) + 4))
    y1 = int(min(paint.H, np.ceil(max(Lp[:, 1].max(), Rp[:, 1].max())) + 4))
    M = np.zeros((y1 - y0, x1 - x0), np.uint8)
    o = np.array([x0, y0], np.float64)
    for i in range(len(C) - 1):
        quad = np.array([Lp[i], Lp[i + 1], Rp[i + 1], Rp[i]]) - o
        cv2.fillConvexPoly(M, np.round(quad).astype(np.int32), 1)
    for i in range(len(C)):
        cv2.line(M, tuple(np.round(Lp[i] - o).astype(int)), tuple(np.round(Rp[i] - o).astype(int)), 1, 1)
    # 先端の扇：先端から前方 ±110° へ、藍に当たるまで（最大 20 px。開けば 3 px）
    if len(C) >= 3:
        fwd = C[0] - C[2]
        fwd /= max(np.linalg.norm(fwd), 1e-9)
        a0 = math.atan2(fwd[1], fwd[0])
        ang = a0 + np.radians(np.arange(-110, 111, 10))
        dirs = np.stack([np.cos(ang), np.sin(ang)], 1)
        dd, wy = cast(paint, np.repeat(C[:1], len(dirs), 0), dirs, 1.0, None, 20.0)
        dd = np.where(wy == 0, 3.0, dd)
        if len(dd) >= 5:
            ap_ = np.pad(dd, 2, mode="edge")
            dd = np.minimum(dd, np.median(np.stack([ap_[k:k + len(dd)] for k in range(5)], 0), 0) + 2.0)
        fan = np.concatenate([C[:1], C[0] + dd[:, None] * dirs], 0) - o
        fan[:, 0] = np.clip(fan[:, 0], 0, M.shape[1] - 1)
        fan[:, 1] = np.clip(fan[:, 1], 0, M.shape[0] - 1)
        cv2.fillPoly(M, [np.round(fan).astype(np.int32)], 1)
    M = M.astype(bool) & paint.passable[y0:y1, x0:x1]
    # 細いとげ（1〜2 px の幅で断面の外へ伸びた所）を 3×3 の開きで落とす。中心線から 2.5 px 以内は残す（細い爪先を守る）
    near_c = np.zeros_like(M, np.uint8)
    cl_i = np.round(C - o).astype(np.int32)
    cv2.polylines(near_c, [cl_i.reshape(-1, 1, 2)], False, 1, 5)
    M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool) | (M & near_c.astype(bool))
    if finger_mask is not None:
        fx0, fy0, F = finger_mask
        full = np.zeros_like(M)
        ys, xs = np.nonzero(F)
        ys, xs = ys + fy0 - y0, xs + fx0 - x0
        k = (ys >= 0) & (ys < M.shape[0]) & (xs >= 0) & (xs < M.shape[1])
        full[ys[k], xs[k]] = True
        M |= full
    # 断面の外へ漏れた孤立の画素を落とす：中心線を含む連結成分だけ
    n_, lab = cv2.connectedComponents(M.astype(np.uint8), connectivity=8)
    if n_ > 2:
        ci = np.round(C - o).astype(int)
        ci[:, 0] = np.clip(ci[:, 0], 0, M.shape[1] - 1)
        ci[:, 1] = np.clip(ci[:, 1], 0, M.shape[0] - 1)
        keep = np.unique(lab[ci[:, 1], ci[:, 0]])
        keep = keep[keep > 0]
        M = np.isin(lab, keep)
    return (x0, y0, M)


def mask_polygon(reg, off):
    x0, y0, M = reg
    cs, _ = cv2.findContours(M.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cs:
        return []
    c = max(cs, key=cv2.contourArea)
    c = cv2.approxPolyDP(c, 1.0, True)[:, 0, :].astype(np.float64)
    return (c + [x0, y0] + off).tolist()


def finger_from_polygon(paint, poly_ref):
    Q = paint.loc(poly_ref)
    x0, y0 = np.floor(Q.min(0)).astype(int) - 2
    x1, y1 = np.ceil(Q.max(0)).astype(int) + 3
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(paint.W, x1), min(paint.H, y1)
    M = np.zeros((y1 - y0, x1 - x0), np.uint8)
    cv2.fillPoly(M, [np.round(Q - [x0, y0]).astype(np.int32)], 1)
    return (x0, y0, M.astype(bool) & paint.white[y0:y1, x0:x1])


def revise(paint, centre_root_to_tip_ref, L_old, finger=None, keep_root=False, guard_on=True):
    """1・2：中心線（原画 px、根元→先端）から、口・根元・領域・新しい中心線を作る。keep_root なら口は探さず、元の根元までを領域にする。"""
    C = paint.loc(centre_root_to_tip_ref)[::-1]  # 先端→根元
    C = resample(C, P["station_step"])
    extended = 0.0
    sd = sections(paint, C)
    if keep_root:
        m_use = len(sd["C"])
        reg = region_from_sections(paint, sd, m_use, finger)
        return dict(status="root_kept", mouth_reason="上側の列：根元は美術優先29 のまま（計画 第6節の2 は船側と途中の列）",
                    root=paint.glob(C[-1]), centerline=np.asarray(centre_root_to_tip_ref, np.float64), region=reg,
                    extended_px=0.0, section_width=None, mouth_index=None, n_sections=len(sd["C"]), guard=None)
    ext = extend_rootward(paint, C)
    n_orig = len(C)
    m, why = find_mouth(sd, L_old)
    if m is None and len(ext):
        C2 = np.concatenate([C, ext], 0)
        sd = sections(paint, C2)
        m, why = find_mouth(sd, L_old)
        if m is not None and m >= len(C):
            extended = float(cumlen(C2)[m] - cumlen(C2)[len(C) - 1])
    status = "mouth" if m is not None else "no_mouth"
    if m is None:
        m = len(sd["C"])
        why = "口が見つからない（元の根元の断面を根元にした）"
    # 修正01：短く切りすぎる口の候補の見張り（独立の検査の指摘 2）
    guard = None
    if status == "mouth" and L_old > 0 and guard_on:
        s_ = cumlen(sd["C"])
        # 切った後の中心線（断面の中点をなめらかにしたもの）の長さで比べる（元の中心線の弧長より短くなるので）
        mu = max(2, m)
        mid_ = sd["C"][:mu] + (0.5 * (sd["dr"][:mu] - sd["dl"][:mu]))[:, None] * sd["n"][:mu]
        cl_ = (sd["wl"][:mu] != 0) & (sd["wr"][:mu] != 0)
        mid_ = np.where(cl_[:, None], mid_, sd["C"][:mu])
        mid_[0] = sd["C"][0]
        L_cut = float(cumlen(resample(smooth(mid_, P["smooth_win"])[::-1], 3.0))[-1])
        if L_cut < P["short_guard_frac"] * L_old:
            smin = max(P["mouth_min_from_tip_px"], P["mouth_min_from_tip_frac"] * L_old)
            i0 = max(int(np.searchsorted(s_, smin)), int(m))   # 最初の口の候補より根元の側だけを探す
            e = find_exit(sd, i0, n_orig)
            guard = dict(first_mouth_index=int(m), first_mouth_reason=why, first_cut_length_px=round(L_cut, 1),
                         first_cut_over_old=round(L_cut / L_old, 3), exit_index=None if e is None else int(e))
            if e is not None:
                m = e
                status = "mouth_exit"
                why = ("両側の線が終わる所（修正01：最初の口の候補「%s」では元の長さの %.2f 倍に縮むので、両側の線がどちらも終わる所だけを口と認めた）"
                       % (guard["first_mouth_reason"], L_cut / L_old))
            else:
                m = n_orig
                extended = 0.0
                status = "root_kept_guard"
                why = ("美術優先29 の根元の断面（修正01：最初の口の候補「%s」では元の長さの %.2f 倍に縮み、元の根元までに両側の線が終わる所がないので、"
                       "口と認めなかった）" % (guard["first_mouth_reason"], L_cut / L_old))
    m_use = max(2, m)
    # 新しい中心線：断面の中点（両側が閉じた断面）。先端は元の先端
    C, n = sd["C"][:m_use], sd["n"][:m_use]
    mid = C + (0.5 * (sd["dr"][:m_use] - sd["dl"][:m_use]))[:, None] * n
    closed = (sd["wl"][:m_use] != 0) & (sd["wr"][:m_use] != 0)
    mid = np.where(closed[:, None], mid, C)
    mid[0] = C[0]
    mid = smooth(mid, P["smooth_win"])
    root_l = mid[-1].copy()
    reg = region_from_sections(paint, sd, m_use, finger)
    cl = resample(mid[::-1], 3.0)  # 根元→先端
    widths = (sd["dl"][:m_use] + sd["dr"][:m_use])[::-1]
    return dict(status=status, mouth_reason=why, root=paint.glob(root_l), centerline=paint.glob(cl), region=reg,
                extended_px=extended, section_width=widths, mouth_index=m, n_sections=len(sd["C"]), guard=guard)


# ---------------------------------------------------------------- 影の検査（領域の作り方とは別の組み立て）
def enclosed_shadow(paint, finger_glob_mask, other_white_dist, win):
    """指（白）の各画素から最も近い指の画素への向きに、水色だけを通って藍の線に 30 px 以内で当たる水色の画素＝囲まれた影。
    finger_glob_mask：win の中の指のマスク。other_white_dist：win の中の「指以外の白」への距離。"""
    x0, y0, x1, y1 = win
    F = finger_glob_mask
    if not F.any():
        return np.zeros_like(F)
    dist, lab = cv2.distanceTransformWithLabels((~F).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(F)
    fx = np.zeros(lab.max() + 1)
    fy = np.zeros(lab.max() + 1)
    lz = lab[ys, xs]
    fx[lz] = xs
    fy[lz] = ys
    pale = paint.pale[y0:y1, x0:x1]
    dark = paint.dark[y0:y1, x0:x1]
    pas = paint.passable[y0:y1, x0:x1]
    cand = pale & (dist <= P["shadow_ray"]) & (dist <= other_white_dist)
    cy, cx = np.nonzero(cand)
    if not len(cy):
        return np.zeros_like(F)
    nx = fx[lab[cy, cx]]
    ny = fy[lab[cy, cx]]
    vx, vy = cx - nx, cy - ny
    d0 = np.hypot(vx, vy)
    ux, uy = vx / np.maximum(d0, 1e-9), vy / np.maximum(d0, 1e-9)
    hit = np.zeros(len(cy), bool)
    alive = np.ones(len(cy), bool)
    Hh, Ww = F.shape
    for s in np.arange(0.5, P["shadow_ray"] + 0.5, 0.5):
        qx = np.round(nx + ux * s).astype(int)
        qy = np.round(ny + uy * s).astype(int)
        inb = (qx >= 0) & (qx < Ww) & (qy >= 0) & (qy < Hh)
        qxc, qyc = np.clip(qx, 0, Ww - 1), np.clip(qy, 0, Hh - 1)
        is_dark = dark[qyc, qxc] & inb
        is_block = (~pas[qyc, qxc] & ~dark[qyc, qxc]) | ~inb
        beyond = s > d0
        # 画素 m までの区間は通れること（水色か指の白）。m より先で藍に当たれば囲まれている
        before_bad = (~beyond) & (is_dark | is_block)
        alive &= ~before_bad
        newhit = alive & beyond & is_dark & ~hit
        hit |= newhit
        alive &= ~(beyond & (is_dark | is_block))
        if not alive.any():
            break
    E = np.zeros_like(F)
    E[cy[hit], cx[hit]] = True
    return E


def path_between(paint, S_ref, T_ref):
    """根元と先端の種を、通れる画素の最短路（藍から遠いほど安い）でつなぐ。戻り値：原画 px の中心線（根元→先端）と種のずれ。"""
    S_, T_ = paint.loc(S_ref), paint.loc(T_ref)
    pad = 30
    x0 = int(max(0, min(S_[0], T_[0]) - pad)); y0 = int(max(0, min(S_[1], T_[1]) - pad))
    x1 = int(min(paint.W, max(S_[0], T_[0]) + pad + 1)); y1 = int(min(paint.H, max(S_[1], T_[1]) + pad + 1))
    pas = paint.passable[y0:y1, x0:x1]
    dt = cv2.distanceTransform(pas.astype(np.uint8), cv2.DIST_L2, 5)

    def snap(p):
        q = np.round(p - [x0, y0]).astype(int)
        ys, xs = np.nonzero(pas)
        if not len(xs):
            return None
        k = int(np.argmin((xs - q[0]) ** 2 + (ys - q[1]) ** 2))
        return (int(ys[k]), int(xs[k])), float(np.hypot(xs[k] - q[0], ys[k] - q[1]))
    a = snap(S_); b = snap(T_)
    if a is None or b is None:
        return None, None
    (sy, sx), ds_ = a
    (ty, tx), dt_ = b
    h, w = pas.shape
    cost = 1.0 / (dt + 0.5)
    dist = np.full((h, w), np.inf)
    prev = -np.ones((h, w), np.int64)
    dist[ty, tx] = 0.0
    pq = [(0.0, ty, tx)]
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    while pq:
        d, y, x = heapq.heappop(pq)
        if d > dist[y, x]:
            continue
        if (y, x) == (sy, sx):
            break
        for dy, dx in nb:
            yy, xx = y + dy, x + dx
            if 0 <= yy < h and 0 <= xx < w and pas[yy, xx]:
                nd = d + math.hypot(dy, dx) * 0.5 * (cost[y, x] + cost[yy, xx])
                if nd < dist[yy, xx]:
                    dist[yy, xx] = nd
                    prev[yy, xx] = y * w + x
                    heapq.heappush(pq, (nd, yy, xx))
    if not np.isfinite(dist[sy, sx]):
        return None, (ds_, dt_)
    path = []
    cur = sy * w + sx
    while cur >= 0:
        yy, xx = divmod(cur, w)
        path.append((xx + x0, yy + y0))
        if (yy, xx) == (ty, tx):
            break
        cur = prev[yy, xx]
    path = np.array(path, np.float64)  # 根元→先端（局所）
    return paint.glob(smooth(path, 5)), (ds_, dt_)


# ---------------------------------------------------------------- 修正01：重なり・重複・切り詰めの道具
def region_overlap(ra, rb):
    """二つの領域（局所の (x0, y0, M)）の重なりの画素数と、それぞれの面積。"""
    ax, ay, A = ra
    bx, by, B = rb
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + A.shape[1], bx + B.shape[1]), min(ay + A.shape[0], by + B.shape[0])
    if x1 <= x0 or y1 <= y0:
        return 0, int(A.sum()), int(B.sum())
    inter = A[y0 - ay:y1 - ay, x0 - ax:x1 - ax] & B[y0 - by:y1 - by, x0 - bx:x1 - bx]
    return int(inter.sum()), int(A.sum()), int(B.sum())


def centerline_in_region(paint, cl_ref, reg):
    """中心線（原画 px）を 1 px ごとにたどり、領域 reg の中にある点の割合。"""
    x0, y0, M = reg
    Q = resample(paint.loc(cl_ref), 1.0)
    xi = np.round(Q[:, 0]).astype(int) - x0
    yi = np.round(Q[:, 1]).astype(int) - y0
    ok = (xi >= 0) & (xi < M.shape[1]) & (yi >= 0) & (yi < M.shape[0])
    inside = np.zeros(len(Q), bool)
    inside[ok] = M[yi[ok], xi[ok]]
    return float(inside.mean()) if len(Q) else 0.0


def find_duplicate(paint, r, claws):
    """修正01：加える爪 r が、一覧（主浪）か先に加えた爪と同じ指か。同じ指とみなすのは、(a) 領域の重なりが小さい方の面積の
    dup_overlap_min 以上、(b) どちらかの中心線の dup_centerline_in 以上が相手の領域の中、(c) 根元が相手の先端の dup_swap_px 以内で
    向きが逆（根元→先端の向きのなす角が dup_angle_deg より大きい）、のいずれか。最も強い相手を返す。"""
    cl_new = np.asarray(r["centerline"], np.float64)
    v_new = cl_new[-1] - cl_new[0]
    best = None
    for o in claws:
        if o["zone"] != "main" or o.get("_region") is None:
            continue
        inter, a_new, a_o = region_overlap(r["region"], o["_region"])
        ov = inter / max(1, min(a_new, a_o))
        cl_o = np.asarray(o["centerline_ref"], np.float64)
        in_o = centerline_in_region(paint, cl_o, r["region"])      # 相手の中心線のうち新しい領域の中
        in_n = centerline_in_region(paint, cl_new, o["_region"])   # 新しい中心線のうち相手の領域の中
        v_o = cl_o[-1] - cl_o[0]
        cosang = float(np.dot(v_new, v_o) / max(1e-9, np.linalg.norm(v_new) * np.linalg.norm(v_o)))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
        d_swap = float(np.hypot(*(cl_new[0] - np.asarray(o["tip_ref"], np.float64))))
        why = []
        if ov >= P["dup_overlap_min"]:
            why.append("領域の重なりが小さい方の %.0f%%" % (100 * ov))
        if max(in_o, in_n) >= P["dup_centerline_in"]:
            why.append("中心線の %.0f%% が相手の領域の中" % (100 * max(in_o, in_n)))
        if d_swap <= P["dup_swap_px"] and ang > P["dup_angle_deg"]:
            why.append("根元が %s の先端から %.1f px で、向きが逆（なす角 %.0f°）" % (o["id"], d_swap, ang))
        if why:
            score = max(ov, in_o, in_n) + (1.0 if d_swap <= P["dup_swap_px"] and ang > P["dup_angle_deg"] else 0.0)
            if best is None or score > best["score"]:
                best = dict(id=o["id"], score=score, reason_ja="、".join(why),
                            evidence=dict(overlap_of_smaller=round(ov, 3), other_centerline_in_new=round(in_o, 3),
                                          new_centerline_in_other=round(in_n, 3), root_to_other_tip_px=round(d_swap, 1),
                                          angle_deg=round(ang, 1)))
    return best


def continues_past_root(paint, cl_ref):
    """修正01 の検査（口の規則とは別の組み立て）：根元から中心線の向きのまま根元の側へ 2 px ごとに cont_steps 個の断面をとり、
    断面の中央が通れる画素で、両側とも 40 px の中で藍に当たり、幅が根元の近くの幅の 1.5 倍 + 4 px 以下のものの割合。
    cont_frac 以上なら「根元の先で指が続く（切り詰め）」。戻り値：割合と根元の近くの幅。"""
    cl = paint.loc(cl_ref)
    if len(cl) < 4:
        return None, None
    d = cl[0] - cl[3]
    d /= max(np.linalg.norm(d), 1e-9)
    n0 = np.array([-d[1], d[0]])
    near = cl[:min(6, len(cl))]
    nn, _ = normals(near) if len(near) >= 3 else (np.repeat(n0[None], len(near), 0), None)
    sn = sections(paint, near, nn)
    wn = (sn["dl"] + sn["dr"])[((sn["wl"] == 1) & (sn["wr"] == 1))]
    w0 = float(np.median(wn)) if len(wn) else float(np.median(sn["dl"] + sn["dr"]))
    pts = cl[0][None, :] + (np.arange(1, P["cont_steps"] + 1) * P["station_step"])[:, None] * d[None, :]
    sd = sections(paint, pts, np.repeat(n0[None], len(pts), 0))
    xi = np.clip(np.round(pts[:, 0]).astype(int), 0, paint.W - 1)
    yi = np.clip(np.round(pts[:, 1]).astype(int), 0, paint.H - 1)
    ok = paint.passable[yi, xi] & (sd["wl"] == 1) & (sd["wr"] == 1) & ((sd["dl"] + sd["dr"]) <= 1.5 * w0 + 4.0)
    return float(ok.mean()), w0



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()
    t0 = time.time()
    os.makedirs(args.out, exist_ok=True)
    inv = T.load_json(INV29)
    reg = T.load_json(REG)
    paint = Paint()
    print("paint %.1fs" % (time.time() - t0), flush=True)
    off = paint.off
    fm = T.FrameMap(paint.spec)

    def to_disp(pts):
        q = np.asarray(pts, np.float64)
        return np.stack([0.416345 * (q[..., 0] + 0.5) - 0.5 + 156.66153, 0.416345 * (q[..., 1] + 0.5) - 0.5], -1)

    band = T.load_json(BAND)
    top = np.array(band["top_smooth"]); bot = np.array(band["bottom_smooth"])
    padb = P["band_pad_display_px"]
    band_poly_d = np.concatenate([top + [0, -padb], bot[::-1] + [0, padb]], 0)
    band_poly_d[:len(top), 0] = top[:, 0]
    x_lo, x_hi = top[:, 0].min() - padb, top[:, 0].max() + padb

    def in_band(pt_ref):
        q = to_disp(np.asarray(pt_ref))
        return bool(cv2.pointPolygonTest(band_poly_d.astype(np.float32), (float(q[0]), float(q[1])), False) >= 0) or \
            (x_lo <= q[0] <= x_hi and np.interp(q[0], top[:, 0], top[:, 1]) - padb <= q[1] <= np.interp(q[0], bot[:, 0], bot[:, 1]) + padb)

    zone_main = np.array(inv["zones"][0]["points_ref"], np.float64)

    def in_main(pt_ref):
        return bool(cv2.pointPolygonTest(zone_main.astype(np.float32), (float(pt_ref[0]), float(pt_ref[1])), False) >= 0)

    # ---- 1・2：美術優先29 の主浪の爪を直す
    claws = []
    removed = []   # 消した爪（理由つき。ID は欠番として残す）
    old_by_id = {c["id"]: c for c in inv["claws"]}
    for c in inv["claws"]:
        if c["id"] in P["merged"]:
            mg = P["merged"][c["id"]]
            removed.append({"id": c["id"], "origin": "af29", "row_af29": c["row"], "row_id_af29": c["row_id"], "kind": "統合",
                            "merged_into": mg["into"], "reason_ja": mg["reason_ja"], "fix": "修正01",
                            "root_ref_af29": c["root_ref"], "tip_ref_af29": c["tip_ref"], "length_ref_px_af29": c["length_ref_px"]})
            continue
        rec = {"id": c["id"], "origin": "af29", "zone": c["zone"], "row": c["row"], "row_id_af29": c["row_id"],
               "tip_ref": c["tip_ref"], "root_ref_af29": c["root_ref"], "length_ref_px_af29": c["length_ref_px"],
               "silhouette": c["silhouette"], "over_indigo": c["over_indigo"], "polygon_ref_af29": c["outline_polygon_ref"]}
        if c["zone"] != "main":
            rec.update(status="右側・低優先・未修正", root_ref=c["root_ref"], centerline_ref=c["centerline_ref"],
                       region_polygon_ref=c["outline_polygon_ref"], changed=False)
            claws.append(rec)
            continue
        finger = finger_from_polygon(paint, c["outline_polygon_ref"])
        ov = P["manual_overrides"].get(c["id"])
        if ov:
            clo, _ = path_between(paint, ov["root_ref"], ov["tip_ref"])
            r = revise(paint, clo, float(cumlen(clo)[-1]), None)
            rec["manual_override_ja"] = ov["note_ja"]
            rec["tip_ref"] = rnd(clo[-1], 1)
        else:
            r = revise(paint, c["centerline_ref"], float(c["length_ref_px"]), finger, keep_root=(c["row"] == "上側"))
        root_move = float(np.hypot(*(np.asarray(r["root"]) - c["root_ref"])))
        rec.update(status=r["status"], mouth_reason=r["mouth_reason"], root_ref=rnd(r["root"], 1),
                   centerline_ref=rnd(r["centerline"], 1), extended_px=rnd(r["extended_px"], 1),
                   root_move_px=rnd(root_move, 1), _region=r["region"], _finger=finger,
                   region_polygon_ref=rnd(mask_polygon(r["region"], off), 1))
        if r.get("guard"):
            rec["short_guard_fix01"] = r["guard"]
        claws.append(rec)
    # 修正01：見張りで根元を戻した爪の領域が、他の爪の中心線の半分以上を含むなら（他の指を呑み込む＝指摘 1 と同じ誤り）、最初の口の候補へ戻す
    for rec in claws:
        if rec.get("_region") is None or rec["status"] not in ("root_kept_guard", "mouth_exit"):
            continue
        eaten = []
        for o in claws:
            if o is rec or o.get("_region") is None or o["zone"] != "main":
                continue
            f_ = centerline_in_region(paint, o["centerline_ref"], rec["_region"])
            if f_ >= P["contain_check"]:
                eaten.append((o["id"], round(f_, 3)))
        if not eaten:
            continue
        c = old_by_id[rec["id"]]
        r = revise(paint, c["centerline_ref"], float(c["length_ref_px"]), rec["_finger"], guard_on=False)
        g = rec["short_guard_fix01"]
        rec.update(status="mouth_guard_reverted",
                   mouth_reason=("最初の口の候補（%s）。修正01 の見張りで根元を戻すと、領域が %s の中心線を含む（他の指を呑み込む）ので、最初の候補に戻した"
                                 % (g["first_mouth_reason"], "・".join("%s %.0f%%" % (i_, 100 * f_) for i_, f_ in eaten))),
                   root_ref=rnd(r["root"], 1), centerline_ref=rnd(r["centerline"], 1), extended_px=rnd(r["extended_px"], 1),
                   root_move_px=rnd(float(np.hypot(*(np.asarray(r["root"]) - c["root_ref"]))), 1), _region=r["region"],
                   region_polygon_ref=rnd(mask_polygon(r["region"], off), 1))
        g["reverted_because_contains"] = eaten
    print("revised %d  %.1fs" % (len(claws), time.time() - t0), flush=True)

    # ---- 3：利用者の100本との対応
    ureg = {u["user_id"]: u for u in reg["claws"]}

    def region_global_mask(rec):
        return rec.get("_region")

    # 一覧の領域を 1 枚の ID の画像へ（局所の座標）
    idimg = np.zeros((paint.H, paint.W), np.int32)
    for k, rec in enumerate(claws):
        if rec["zone"] != "main":
            Q = paint.loc(rec["region_polygon_ref"])
            M = np.zeros((paint.H, paint.W), np.uint8)
            cv2.fillPoly(M, [np.round(Q).astype(np.int32)], 1)
            idimg[(M > 0) & (idimg == 0)] = k + 1
            continue
        x0, y0, M = rec["_region"]
        sub = idimg[y0:y0 + M.shape[0], x0:x0 + M.shape[1]]
        sub[M & (sub == 0)] = k + 1

    def user_mask_ref(uid):
        u = ureg[uid]
        m = cv2.imdecode(np.fromfile(USER_CROPS + "/" + uid + "/fill_mask.png", np.uint8), cv2.IMREAD_GRAYSCALE)
        A = np.array(u["A_crop_to_ref"], np.float64)
        A_loc = A.copy()
        A_loc[:, 2] -= off
        W_ = cv2.warpAffine((m > 127).astype(np.uint8), A_loc, (paint.W, paint.H), flags=cv2.INTER_NEAREST)
        return W_.astype(bool)

    corr = []
    for uid in sorted(ureg):
        u = ureg[uid]
        M = user_mask_ref(uid)
        area = int(M.sum())
        ids, cnt = np.unique(idimg[M], return_counts=True)
        best = None
        for i_, n_ in zip(ids, cnt):
            if i_ == 0:
                continue
            rec = claws[i_ - 1]
            fr = n_ / max(area, 1)
            td = float(np.hypot(*(np.asarray(rec["tip_ref"]) - u["tip_ref"])))
            if best is None or fr > best[1]:
                best = (rec["id"], fr, td)
        reliable = u["ncc_after_ecc"] >= P["reg_ncc_min"]
        e = {"user_id": uid, "ncc_after_ecc": u["ncc_after_ecc"], "peak_margin": u["peak_margin"], "scale": u["scale"],
             "root_ref": u["root_ref"], "tip_ref": u["tip_ref"], "mask_area_ref_px": area,
             "in_main_zone": in_main(u["tip_ref"]), "in_b_region": in_band(u["tip_ref"]),
             "best_id": best[0] if best else None, "best_overlap": rnd(best[1], 3) if best else 0.0,
             "best_tip_dist_px": rnd(best[2], 1) if best else None, "registration_reliable": bool(reliable)}
        if best and best[1] >= P["match_overlap"]:
            e["status"] = "対応"
        elif not reliable:
            e["status"] = "対応なし"
            e["reason_ja"] = "位置合わせが不確か（ECC の後の NCC %.2f < %.2f）。一覧へ加えない" % (u["ncc_after_ecc"], P["reg_ncc_min"])
        elif not (e["in_main_zone"] or e["in_b_region"]):
            e["status"] = "対応なし"
            if u["tip_ref"][1] > 1500:
                e["reason_ja"] = "手前の波（主浪の外、画の下側）の爪。一覧（主浪と右側の波）の対象の外なので加えない"
            else:
                e["reason_ja"] = ("美術優先29 の主浪の範囲（zones の main）と b区域の帯（±30 表示 px）の外（主浪の左の群の下側など）。"
                                  "この番号では範囲を広げず加えない（仕上げ32 で範囲を広げるかを決める）")
        else:
            e["status"] = "追加の候補"
        corr.append(e)
    # 同じ位置に合う利用者の爪（重複）
    for i, a in enumerate(corr):
        for b in corr[:i]:
            if a["tip_ref"] and b["tip_ref"] and np.hypot(*(np.asarray(a["tip_ref"]) - b["tip_ref"])) < 6.0:
                a["duplicate_of"] = b["user_id"]
    print("correspondence %.1fs" % (time.time() - t0), flush=True)

    # ---- 3（続き）：加える爪
    new_seeds = []
    for s in P["manual_seeds"]:
        new_seeds.append(dict(kind="manual", name=s["name"], root_ref=s["root_ref"], tip_ref=s["tip_ref"], note_ja=s["note_ja"]))
    for e in corr:
        if e["status"] == "追加の候補" and "duplicate_of" not in e:
            new_seeds.append(dict(kind="user100", name=e["user_id"], root_ref=e["root_ref"], tip_ref=e["tip_ref"]))
    added, next_id = [], P["new_id_start"]
    for s in new_seeds:
        cl, snaps = path_between(paint, s["root_ref"], s["tip_ref"])
        if cl is None:
            s["result_ja"] = "通れる画素で根元と先端がつながらない（加えない）"
            continue
        L0 = float(cumlen(cl)[-1])
        if L0 < 14.0:
            s["result_ja"] = "短い（%.1f px < 14 px、加えない）" % L0
            continue
        # すでに一覧の爪（直した領域）の中に先端があれば加えない
        tl = np.round(paint.loc(s["tip_ref"])).astype(int)
        hit = idimg[np.clip(tl[1], 0, paint.H - 1), np.clip(tl[0], 0, paint.W - 1)]
        if hit and s["kind"] == "user100":
            s["result_ja"] = "先端が一覧の爪 %s の領域の中（重なりが小さいだけ。加えない）" % claws[hit - 1]["id"]
            for e in corr:
                if e["user_id"] == s["name"]:
                    e["status"] = "対応"
                    e["best_id"] = claws[hit - 1]["id"]
                    e["note_ja"] = "先端が一覧の爪の領域の中"
            continue
        r = revise(paint, cl, L0, None)
        # 作った領域が一覧の爪の領域と半分以上重なるなら、同じ爪（加えない）
        x0r, y0r, Mr = r["region"]
        sub_ids = idimg[y0r:y0r + Mr.shape[0], x0r:x0r + Mr.shape[1]][Mr]
        if len(sub_ids):
            u_, n_ = np.unique(sub_ids[sub_ids > 0], return_counts=True)
            if len(u_) and n_.max() >= P["dedupe_overlap"] * Mr.sum():
                hid = claws[int(u_[np.argmax(n_)]) - 1]["id"]
                s["result_ja"] = "作った領域の %.0f%% が一覧の爪 %s と重なる（同じ爪。加えない）" % (100.0 * n_.max() / Mr.sum(), hid)
                for e in corr:
                    if e["user_id"] == s["name"]:
                        e["status"] = "対応"
                        e["best_id"] = hid
                        e["note_ja"] = "こちらの方法で作った領域が一覧の爪と重なる"
                continue
        # 修正01（独立の検査の指摘 3）：加えた爪どうし・一覧の爪との重複（向きが逆の同じ指を含む）
        dup = find_duplicate(paint, r, claws)
        if dup is not None:
            pid = P["id_pin"].get(s["name"])
            s["result_ja"] = "重複（%s）。加えない（修正01）" % dup["reason_ja"]
            removed.append({"id": pid, "origin": "ds32_" + s["kind"], "seed": s["name"], "kind": "重複", "duplicate_of": dup["id"],
                            "reason_ja": dup["reason_ja"], "evidence": dup["evidence"], "fix": "修正01",
                            "note_ja": "初回の出力ではこの ID で加えていた。ID は欠番として残す" if pid else None})
            for e in corr:
                if e["user_id"] == s["name"]:
                    e["status"] = "対応なし"
                    e["best_id"] = dup["id"]
                    e["reason_ja"] = ("重複か位置合わせの誤り：こちらの方法で作った爪が %s と同じ指になる（%s）。加えない（修正01、独立の検査の指摘 3）"
                                      % (dup["id"], dup["reason_ja"]))
                    e["removed_id_fix01"] = pid
            continue
        if s["name"] in P["id_pin"]:
            nid = P["id_pin"][s["name"]]
        else:
            next_id = max([next_id] + [int(v[1:]) + 1 for v in P["id_pin"].values()])
            nid = "C%03d" % next_id
            next_id += 1
        tip = cl[-1]
        s_row = "b区域" if in_band(tip) and not in_main(tip) else None
        rec = {"id": nid, "origin": "ds32_" + s["kind"], "seed": s["name"], "zone": "main", "row": s_row, "tip_ref": rnd(tip, 1),
               "root_ref_af29": None, "length_ref_px_af29": None, "silhouette": None, "over_indigo": None, "polygon_ref_af29": None,
               "status": r["status"], "mouth_reason": r["mouth_reason"], "root_ref": rnd(r["root"], 1),
               "centerline_ref": rnd(r["centerline"], 1), "extended_px": rnd(r["extended_px"], 1), "root_move_px": None,
               "_region": r["region"], "_finger": None, "region_polygon_ref": rnd(mask_polygon(r["region"], off), 1),
               "seed_snap_px": rnd(list(snaps), 1)}
        claws.append(rec)
        added.append(nid)
        s["result_ja"] = "加えた（%s）" % nid
        x0, y0, M = r["region"]
        sub = idimg[y0:y0 + M.shape[0], x0:x0 + M.shape[1]]
        sub[M & (sub == 0)] = len(claws)
        for e in corr:
            if e["user_id"] == s["name"]:
                e["status"] = "追加"
                e["added_id"] = nid
    for e in corr:
        if "duplicate_of" in e and e["status"] == "追加の候補":
            d = next((x for x in corr if x["user_id"] == e["duplicate_of"]), None)
            e["status"] = "対応" if d and d.get("added_id") else "対応なし"
            e["best_id"] = d.get("added_id") if d else None
            e["reason_ja"] = "利用者の %s と同じ位置に合う（重複）" % e["duplicate_of"]
    print("added %d  %.1fs" % (len(added), time.time() - t0), flush=True)

    # 列（加えた爪）：美術優先29 の凍結の境目と同じ規則（包絡版の外周への最近点の弧長 s）
    env = T.load_json(os.path.join(T.TARGET_DIR, "main_wave_outline_envelope.json"))
    segs = {s_["id"]: np.asarray(s_["points_ref"], np.float64) for s_ in env["segments"]}
    ref_curve = np.concatenate([segs["131"], segs["132"][1:], segs["72"][1:]], 0)
    ref_s = cumlen(ref_curve)
    ref_s = ref_s - ref_s[len(segs["131"]) - 1]
    for rec in claws:
        if rec["row"] is None:
            tip = np.asarray(rec["tip_ref"])
            d = np.hypot(ref_curve[:, 0] - tip[0], ref_curve[:, 1] - tip[1])
            d = np.where(ref_s <= 2150, d, np.inf)
            s_ = float(ref_s[int(np.argmin(d))])
            if tip[0] < P["x_split"]:
                rec["row"] = "上側"
            elif s_ < P["breaks_s"][0]:
                rec["row"] = "上側"
            elif s_ < P["breaks_s"][1]:
                rec["row"] = "途中"
            else:
                rec["row"] = "船側"
        rec["b_region_q16"] = bool(in_band(rec["tip_ref"]) or in_band(rec["root_ref"]))

    # 加えた爪の根元が一覧の爪の先端の近く（15 px 以内）なら、その爪の先の続きの可能性として記録する（記録のみ。仕上げ32 で確かめる）
    for rec in claws:
        if not rec["origin"].startswith("ds32"):
            continue
        best = None
        for o in claws:
            if o is rec or o["zone"] != "main":
                continue
            d_ = float(np.hypot(*(np.asarray(o["tip_ref"]) - rec["root_ref"])))
            if d_ < 15.0 and (best is None or d_ < best[1]):
                best = (o["id"], d_)
        if best:
            rec["possible_continuation_of"] = {"id": best[0], "root_to_tip_px": round(best[1], 1),
                                               "note_ja": "加えた爪の根元が、この爪の先端の近くにある。同じ爪の先の続きかもしれない（記録のみ。仕上げ32 で確かめる）"}

    # ---- 影の検査（前＝美術優先29 の白の多角形、後＝この番号の領域）
    white_all = paint.white
    shadow = []
    for rec in claws:
        if rec["zone"] != "main":
            continue
        x0, y0, M = rec["_region"]
        pad = int(P["shadow_ray"]) + 4
        X0, Y0 = max(0, x0 - pad), max(0, y0 - pad)
        X1, Y1 = min(paint.W, x0 + M.shape[1] + pad), min(paint.H, y0 + M.shape[0] + pad)
        R = np.zeros((Y1 - Y0, X1 - X0), bool)
        R[y0 - Y0:y0 - Y0 + M.shape[0], x0 - X0:x0 - X0 + M.shape[1]] = M
        F = R & white_all[Y0:Y1, X0:X1]
        other = white_all[Y0:Y1, X0:X1] & ~F
        od = cv2.distanceTransform((~other).astype(np.uint8), cv2.DIST_L2, 5)
        E = enclosed_shadow(paint, F, od, (X0, Y0, X1, Y1))
        # 口より根元の側の影は数えない（中心線の根元から 5 px 以内の画素を除く）
        rl = paint.loc(rec["root_ref"]) - [X0, Y0]
        clr = paint.loc(rec["centerline_ref"]) - [X0, Y0]
        k2 = min(len(clr) - 1, 3)
        troot = clr[k2] - clr[0]
        troot = troot / max(np.linalg.norm(troot), 1e-9)
        yy, xx = np.nonzero(E)
        keep = (np.hypot(xx - rl[0], yy - rl[1]) > 5.0) & (((xx - rl[0]) * troot[0] + (yy - rl[1]) * troot[1]) > 0.0)
        E2 = np.zeros_like(E)
        E2[yy[keep], xx[keep]] = True
        nE = int(E2.sum())
        inc_new = float((E2 & R).sum() / nE) if nE else None
        if rec["polygon_ref_af29"] is not None:
            Mo = np.zeros_like(R, np.uint8)
            cv2.fillPoly(Mo, [np.round(paint.loc(rec["polygon_ref_af29"]) - [X0, Y0]).astype(np.int32)], 1)
            inc_old = float((E2 & Mo.astype(bool)).sum() / nE) if nE else None
        else:
            inc_old = None
        rec["shadow"] = {"enclosed_px": nE, "included_new": rnd(inc_new, 3), "included_af29": rnd(inc_old, 3)}
        shadow.append((rec["id"], nE, inc_new, inc_old))
    tested = [s for s in shadow if s[1] >= P["shadow_min_px"]]
    fail_new = [s[0] for s in tested if s[2] is not None and s[2] < P["shadow_incl_min"]]
    fail_old = [s[0] for s in tested if s[3] is not None and s[3] < P["shadow_incl_min"]]
    below_09_new = [s[0] for s in tested if s[2] is not None and s[2] < 0.9]
    print("shadow tested %d fail_new %d fail_af29 %d  %.1fs" % (len(tested), len(fail_new), len(fail_old), time.time() - t0), flush=True)

    # ---- 修正01 の検査（口・領域の作り方とは別の組み立て）
    mains = [r_ for r_ in claws if r_["zone"] == "main" and r_.get("_region") is not None]
    # (1) 他の爪の中心線の半分以上を含む領域の組（独立の検査の指摘 1 の C105 ⊃ C110・C107 の型）
    contain = []
    for a in mains:
        ax, ay, A = a["_region"]
        for b in mains:
            if a is b:
                continue
            q = paint.loc(b["centerline_ref"])
            if q[:, 0].max() < ax or q[:, 0].min() > ax + A.shape[1] or q[:, 1].max() < ay or q[:, 1].min() > ay + A.shape[0]:
                continue
            f_ = centerline_in_region(paint, b["centerline_ref"], a["_region"])
            if f_ >= P["contain_check"]:
                contain.append({"region_of": a["id"], "centerline_of": b["id"], "fraction": round(f_, 3)})
    # (2) 短く切った爪（元の長さの short_guard_frac 倍未満）と、根元の先で指が続く爪（切り詰め）
    short_list, trunc = [], []
    for r_ in mains:
        L_new = float(cumlen(np.asarray(r_["centerline_ref"], np.float64))[-1])
        r_["_len_new"] = L_new
        if r_.get("length_ref_px_af29"):
            ratio = L_new / r_["length_ref_px_af29"]
            if ratio < P["short_guard_frac"]:
                short_list.append({"id": r_["id"], "row": r_["row"], "status": r_["status"], "length_af29": r_["length_ref_px_af29"],
                                   "length_new": round(L_new, 1), "ratio": round(ratio, 3)})
        f_, w0 = continues_past_root(paint, r_["centerline_ref"])
        r_["fix01_continues_past_root"] = {"fraction": rnd(f_, 2), "width_near_root_px": rnd(w0, 1)}
        if f_ is not None and f_ >= P["cont_frac"] and r_["status"] != "root_kept":
            trunc.append({"id": r_["id"], "row": r_["row"], "status": r_["status"], "fraction": round(f_, 2), "length_new": round(L_new, 1),
                          "length_af29": r_.get("length_ref_px_af29")})
    fix01_named = {}
    for i_ in ["C074", "C075", "C078", "C080", "C081", "C082", "C087", "C092", "C093", "C098", "C106", "C107", "C105", "C110", "C169", "C163"]:
        r_ = next((x for x in claws if x["id"] == i_), None)
        if r_ is None:
            rm = next((x for x in removed if x["id"] == i_), None)
            fix01_named[i_] = {"removed": rm["kind"] if rm else "?", "into_or_dup_of": (rm or {}).get("merged_into") or (rm or {}).get("duplicate_of")}
            continue
        fix01_named[i_] = {"status": r_["status"], "length_af29": r_.get("length_ref_px_af29"), "length_new": rnd(r_.get("_len_new"), 1),
                           "root_ref": r_["root_ref"], "continues_past_root": r_.get("fix01_continues_past_root"),
                           "guard": r_.get("short_guard_fix01")}
    # (3) 記録のみ：領域の重なりの組（小さい方の面積に対する割合）と、他の爪の領域の中にある根元（上側の列は美術優先29 の根元のまま）
    ovl = []
    for k_, a in enumerate(mains):
        for b in mains[k_ + 1:]:
            inter, aa, ab = region_overlap(a["_region"], b["_region"])
            if inter:
                ovl.append({"a": a["id"], "b": b["id"], "of_smaller": round(inter / max(1, min(aa, ab)), 3)})
    roots_in = []
    for a in mains:
        q = np.round(paint.loc(a["root_ref"])).astype(int)
        for b in mains:
            if b is a:
                continue
            x0_, y0_, M_ = b["_region"]
            if 0 <= q[1] - y0_ < M_.shape[0] and 0 <= q[0] - x0_ < M_.shape[1] and M_[q[1] - y0_, q[0] - x0_]:
                roots_in.append({"root_of": a["id"], "row": a["row"], "status": a["status"], "inside_region_of": b["id"]})
                break
    fix01 = {
        "ja": "修正01（独立の検査の 3 つの指摘への 1 回だけの修正、Q26）の検査。口・領域の作り方とは別の組み立て",
        "region_overlap_pairs": len(ovl), "region_overlap_pairs_gt_0_2": [o for o in ovl if o["of_smaller"] > 0.2],
        "roots_inside_other_region": roots_in,
        "containment_pairs_ge_0_5": contain,
        "containment_named_C105_C107_C110": [c_ for c_ in contain if {c_["region_of"], c_["centerline_of"]} & {"C105", "C107", "C110"}],
        "short_below_0_5_of_af29": short_list,
        "continues_past_root_ge_%.1f" % P["cont_frac"]: trunc,
        "named_12_and_others": fix01_named,
        "removed": [{k: v for k, v in x.items() if k in ("id", "kind", "merged_into", "duplicate_of", "seed")} for x in removed],
    }
    print("fix01: contain %d (named %d) short %d trunc %d removed %s" % (len(contain), len(fix01["containment_named_C105_C107_C110"]),
                                                                      len(short_list), len(trunc), [x["id"] for x in removed]), flush=True)

    # ---- IoU（記録のみ、合否は出さない。計画 第6節）：主浪の範囲（美術優先29 の zones の main）で、
    #      仮の定義（藍の輪郭線の内側）を分母と分子の両方に使った値と、美術優先29 の分母A・B の値を並べる
    zm = np.zeros((paint.H, paint.W), np.uint8)
    cv2.fillPoly(zm, [np.round(paint.loc(zone_main)).astype(np.int32)], 1)
    zm = zm.astype(bool)
    wz = paint.white & zm
    flat = cv2.morphologyEx(wz.astype(np.uint8), cv2.MORPH_OPEN, T.disk(45)).astype(bool) & wz   # 平らな白（美術優先29 の body と同じ半径 45 px）
    wA = wz & ~flat
    big = np.full(wz.shape, 1e9, np.float32)
    E_A = enclosed_shadow(paint, wA, big, (0, 0, paint.W, paint.H)) & zm
    E_B = enclosed_shadow(paint, wz, big, (0, 0, paint.W, paint.H)) & zm
    DA = wA | E_A     # 分母A′：平らな白を除く白 ＋ 囲まれた影
    DB = wz | E_B     # 分母B′：白の全体 ＋ 囲まれた影
    num = np.zeros_like(zm)
    num29 = np.zeros((paint.H, paint.W), np.uint8)
    for rec in claws:
        if rec["zone"] != "main" or rec.get("_region") is None:
            continue
        x0, y0, M = rec["_region"]
        num[y0:y0 + M.shape[0], x0:x0 + M.shape[1]] |= M
        if rec["polygon_ref_af29"] is not None:
            cv2.fillPoly(num29, [np.round(paint.loc(rec["polygon_ref_af29"])).astype(np.int32)], 1)
    num &= zm
    num29 = num29.astype(bool) & zm

    def iou(a, b):
        u = (a | b).sum()
        return round(float((a & b).sum() / u), 4) if u else None
    iou_rec = {
        "scope_ja": "主浪の範囲（美術優先29 の zones の main の多角形）。b区域と右側は含めない。高解像度 px",
        "definition_ja": "分母A′＝平らな白（白を半径 45 px の円で開いて残る所）を除く白 ＋ その白に囲まれた影（影の検査と同じ組み立て）。分母B′＝白の全体 ＋ 囲まれた影。"
                         "分子＝設計32 の爪の領域（藍の輪郭線の内側、影を含む）の和。比べとして、美術優先29 の白の多角形の和を同じ分母で測った値と、"
                         "美術優先29 の記録の値（分母A・B、分子＝指＋幹＋根元の白など）を並べる。合否は出さない（仕上げ32 で定義を決め直す、D25）。",
        "pixels": {"denominator_A_prime": int(DA.sum()), "denominator_B_prime": int(DB.sum()), "enclosed_shadow_A": int(E_A.sum()),
                   "enclosed_shadow_B": int(E_B.sum()), "flat_white": int(flat.sum()), "numerator_ds32": int(num.sum()), "numerator_af29_polygons": int(num29.sum())},
        "ds32_regions_vs_A_prime": iou(num, DA), "ds32_regions_vs_B_prime": iou(num, DB),
        "af29_polygons_vs_A_prime": iou(num29, DA), "af29_polygons_vs_B_prime": iou(num29, DB),
        "af29_recorded": {"A_all_parts": 0.8766, "B_all_parts": 0.6006, "A_fingers_stems": 0.6854, "B_fingers_stems": 0.4665,
                          "A_outline_polygons": 0.4660, "B_outline_polygons": 0.3060,
                          "source_ja": "Docs/Evidence/ArtFirst/29/metrics.json（主浪）と Docs/Progress/Step_29_ja.md の IoU の表。分母A・B は白だけ（影を含まない）"},
        "judgement": "記録のみ",
    }
    print("iou", {k: v for k, v in iou_rec.items() if k.startswith("ds32") or k.startswith("af29_poly")}, flush=True)

    # ---- 保存
    out_claws = []
    for rec in claws:
        o = {k: v for k, v in rec.items() if not k.startswith("_")}
        o["tip_display"] = rnd(to_disp(np.asarray(rec["tip_ref"])), 2)
        o["root_display"] = rnd(to_disp(np.asarray(rec["root_ref"])), 2)
        L = float(cumlen(np.asarray(rec["centerline_ref"], np.float64))[-1])
        o["length_ref_px"] = rnd(L, 1)
        o["changed"] = rec["zone"] == "main"
        out_claws.append(o)
    np.save(os.path.join(args.out, "_regions.npy"), np.array([(r["id"], r.get("_region")) for r in claws], dtype=object), allow_pickle=True)
    named = ["C083", "C084", "C085", "C109", "C110", "C105"] + [c["id"] for c in claws if c.get("seed") == "127の下"]  # C105 は修正01 で加えた（C110 の所）
    rows = {}
    for rec in claws:
        rows.setdefault(rec["row"], 0)
        rows[rec["row"]] += 1
    moved = {}
    for rec in claws:
        if rec.get("root_move_px") is not None and rec["root_move_px"] > P["root_move_report_px"]:
            moved.setdefault(rec["row"], []).append(rec["id"])
    inv_out = {
        "schema": "GreatWave.ClawInventory/2",
        "number": "設計32",
        "base": {"path": INV29.replace(REPO + "/", ""), "sha256": sha(INV29), "version": inv["version"]},
        "reference": inv["reference"],
        "coordinate_convention_ja": inv["coordinate_convention_ja"],
        "definition_region_ja": "爪の領域（D25 の仮の定義、印刷工程の調査（仕上げ32）まで）：爪を囲む藍の輪郭線の内側。中心線の各点で法線の両側へ、"
                                "白か水色で空・黄土でない画素を、藍（mix・藍中・藍濃）か空に当たるまでたどった断面の和（片側 40 px まで）。水色の影を含む。",
        "definition_root_ja": "起点（根元）：先端から根元へ断面をたどり、片側が 40 px の中で藍に当たらなくなる（開く）か、幅が直前 8 断面の中央値の 2.4 倍を超え"
                              "かつ 10 px 以上広がる所が 2 断面続く最初の所を「口」とし、その一つ手前の断面の中央を根元にする。中心線は断面の中点を 5 点の移動平均で"
                              "なめらかにし、先端は美術優先29 の先端のまま。口に届かない爪は断面の中点をたどって最大 80 px 延ばす。"
                              "修正01：最初の口の候補で元の長さの 0.5 倍未満に縮むときは、両側の線（藍）がどちらも終わる所（両側とも 40 px の中で藍に当たらない断面が 2 つ続く所）"
                              "だけを口と認め、元の根元までになければ美術優先29 の根元の断面の中央を根元にする（先端の鉤のすぐ上や曲がり目を口と読まない）。",
        "ids_ja": "美術優先29 の ID（C001〜C153）を保つ。加えた爪は C154 から（修正01 でも初回の ID を種ごとに保つ）。消した爪（統合・重複）の ID は欠番とし、"
                  "理由を removed_claws に残す。右側（C129〜C153）は触らない（低優先・未修正）。",
        "params": P,
        "counts": {"total": len(out_claws), "af29": len(inv["claws"]), "added": added, "removed": [x["id"] for x in removed], "by_row": rows,
                   "b_region_q16": [c["id"] for c in out_claws if c["b_region_q16"]]},
        "root_moved_over_px": {"threshold_px": P["root_move_report_px"], "by_row": moved},
        "named_by_user": named,
        "removed_claws": removed,
        "claws": out_claws,
    }
    jdump(os.path.join(args.out, "ds32_claw_inventory.json"), inv_out)
    matched = [e for e in corr if e["status"] in ("対応", "追加")]
    # 修正01：独立の検査の未解決の指摘（記録のみ）。同じ画像の利用者の爪、1 本の一覧の爪に対応した複数の利用者の爪、位置合わせの山の差が小さいもの
    same_png = {}
    for uid_, fs_ in sorted(reg["user_files_sha256"].items()):
        same_png.setdefault(fs_["original_png_sha256"], []).append(uid_)
    multi = {}
    for e in corr:
        if e["status"] == "対応" and e.get("best_id"):
            multi.setdefault(e["best_id"], []).append({"user_id": e["user_id"], "tip_dist_px": e.get("best_tip_dist_px")})
    notes_fix01 = {
        "identical_user_crops": [v for v in same_png.values() if len(v) > 1],
        "list_claws_with_multiple_user_matches": {k: v for k, v in sorted(multi.items()) if len(v) > 1},
        "distinct_list_claws_matched": len(multi),
        "matched_or_added_peak_margin_below_0_02": [e["user_id"] for e in corr if e["status"] in ("対応", "追加") and e["peak_margin"] < 0.02],
        "ja": "記録のみ（修正01 で加えた欄。独立の検査の未解決の指摘）。同じ画像の利用者の爪は同じ所に合う。先端の距離が 60 px を超える対応や、"
              "山の差が 0.02 未満の位置合わせは不確かで、仕上げ32 で見直す",
    }
    jdump(os.path.join(args.out, "ds32_user100_correspondence.json"), {
        "schema": "GreatWave.DS32.user100_correspondence/1",
        "source_registration": {"path": REG.replace(REPO + "/", ""), "sha256": sha(REG)},
        "user_files_sha256_see": "ds32_user100_registration.json の user_files_sha256",
        "rule_ja": "利用者のマスク（位置合わせで原画へ写したもの、メモリの中だけ）のうち、一覧の爪の領域に入る画素の割合が最も大きい爪を対応とする"
                   "（%.2f 以上で対応）。対応しない爪は、位置合わせが確か（NCC ≥ %.2f）で主浪の波頭か b区域にあれば、利用者の根元・先端を種にして"
                   "こちらの方法で作って加える。" % (P["match_overlap"], P["reg_ncc_min"]),
        "summary": {"user_total": len(corr), "matched_existing": sum(1 for e in corr if e["status"] == "対応"),
                    "added_from_user": sum(1 for e in corr if e["status"] == "追加"),
                    "not_matched": sum(1 for e in corr if e["status"] == "対応なし"),
                    "matched_or_added": len(matched)},
        "seeds": new_seeds,
        "notes_fix01": notes_fix01,
        "removed_claws_fix01": [x for x in removed if x["kind"] == "重複"],
        "claws": corr,
    })
    checks = {
        "schema": "GreatWave.DS32.claw_list_checks/1",
        "shadow_check_ja": "囲まれた影：指（領域の中の白）の各画素から最も近い指の画素への向きに、水色だけを通り、先で藍の線に 30 px 以内で当たる水色の画素"
                           "（指以外の白より指に近いもの。根元を通り中心線に直交する線（口の線）より根元の側と、根元から 5 px 以内を除く）。領域の断面の作り方とは別の組み立て。囲まれた影が %d px 以上の爪で、"
                           "そのうち領域に入る割合が %.2f 未満の爪を「影を外した爪」と数える。" % (P["shadow_min_px"], P["shadow_incl_min"]),
        "shadow_tested": len(tested),
        "shadow_excluded_new": fail_new,
        "shadow_excluded_af29": fail_old,
        "shadow_below_0_9_ds32": below_09_new,
        "shadow_pass": len(fail_new) == 0,
        "shadow_threshold_choice_ja": "「囲まれた影を外した爪」を、囲まれた影のうち領域に入る割合が 0.5 未満（影の半分以上を外した）の爪と読む（進行役の判断、Q24）。"
                                      "美術優先29 の白の多角形は 128 本すべてが 0.12 未満（中央値 0.03）で、利用者の指摘（83・84・85 で影を内側と見なかった）はこの状態。"
                                      "0.8・0.9 の数も並べる。0.9 に届かない分は領域の縁の精度で、爪ごとに原画の輪郭線へ合わせる仕上げ32 へ送る",
        "shadow_counts_by_threshold": {str(th): {"ds32": sum(1 for s_ in tested if s_[2] is not None and s_[2] < th),
                                                 "af29": sum(1 for s_ in tested if s_[3] is not None and s_[3] < th)} for th in (0.5, 0.8, 0.9)},
        "shadow_included_quantiles_ds32": [round(float(q), 3) for q in np.percentile([s_[2] for s_ in tested if s_[2] is not None], [0, 5, 10, 25, 50])],
        "shadow_included_quantiles_af29": [round(float(q), 3) for q in np.percentile([s_[3] for s_ in tested if s_[3] is not None], [0, 50, 90, 100])],
        "iou": iou_rec,
        "fix01": fix01,
        "elapsed_s": round(time.time() - t0, 1),
    }
    jdump(os.path.join(args.out, "ds32_claw_list_checks.json"), checks)
    print(json.dumps({k: v for k, v in checks.items() if k != "shadow_check_ja"}, ensure_ascii=False)[:2000])
    print("done %.1fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
