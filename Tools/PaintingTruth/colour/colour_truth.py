# -*- coding: utf-8 -*-
"""番号28 第A部：主浪の色区の正解（白・水色・藍中・藍濃、藍の縞の一覧、白い帯、爪と白の関係、内側の明るい色面）。

使い方（リポジトリの根で実行。py -3.10、numpy と OpenCV と PIL だけ）:
    py -3.10 Tools/PaintingTruth/colour/colour_truth.py --evidence Docs/Evidence/ArtFirst/28 --build Unity/Build/ArtFirst/28/partA

入力：
    Docs/References/Met_JP1847_DP130155.jpg            高解像度の原画（3859×2594。SHA-256 を照合する）
    Tools/PaintingTruth/targets/masks/sky_claws_cov.png  番号23の真値の空（爪入り版、表示フレームの被覆率）
    Tools/PaintingTruth/targets/masks/sky_envelope_cov.png 番号23の真値の空（包絡版。134 の帯の幅を測るときの唇の下の空）
    Tools/PaintingTruth/targets/main_wave_outline_*.json 番号23の主浪の輪郭（区間 78/130/131/132/72）
    Tools/PaintingTruth/targets/palette.json            番号23の調色板（分類の初期値と比較だけに使う）
    Tools/PaintingTruth/colour/colour_annotations.json  番号28で手で決めた区域・数え線・つなぎ（表示 px）
出力：
    Tools/PaintingTruth/colour/colour_truth.json        色区の定義、中心の色、水色の対応の決定と根拠、縞の一覧、白い帯、175・270・120・73/263/265 の対象
    Tools/PaintingTruth/colour/colour_polylines.json    ベクター化した境界（ID 付き。表示 px と hi px）
    Tools/PaintingTruth/colour/masks/*.png               表示フレームの色区の被覆率（uint16）とラベル（uint8）、hi px のラベル
    <evidence>/28A_*.png, partA_metrics.json, partA_run.json  人が確かめる重ね図（1920×1080）、数値、実行記録（時刻は run だけに入れ、ほかの出力は決定的）
    <build>/                                             再生成できる中間物（Git に入れない）
座標：表示 px は表示フレーム 1920×1080（画素中心が整数、x 右、y 下）。hi px は高解像度原画の画素（同じ約束）。
写像は番号23 v0.2 と同じ（縦 1080 に合わせて中央に置く、等方）：x_d = s·(x_h+0.5) − 0.5 + ox、y_d = s·(y_h+0.5) − 0.5、s = 1080/2594。
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import time
from collections import deque

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PT))
sys.path.insert(0, PT)
import truthlib as T  # noqa: E402  srgb8_to_lab・ciede2000・lab_to_srgb8_best・save_png_reserved（番号23 で較正済み）

REF_REL = "Docs/References/Met_JP1847_DP130155.jpg"
REF_SHA = "cbb9988f2f18b9180a1cc0cf5dbb0e3bbf8f2e85d17930cf6ca9ab36fac36303"
SKY_REL = "Tools/PaintingTruth/targets/masks/sky_claws_cov.png"
SKY_ENV_REL = "Tools/PaintingTruth/targets/masks/sky_envelope_cov.png"
ENV_REL = "Tools/PaintingTruth/targets/main_wave_outline_envelope.json"
CLAWS_REL = "Tools/PaintingTruth/targets/main_wave_outline_claws.json"
MANIFEST_REL = "Tools/PaintingTruth/targets/truth_manifest.json"
SPEC_REL = "Tools/PaintingTruth/painting_truth.json"
PALETTE23_REL = "Tools/PaintingTruth/targets/palette.json"
ANN_REL = "Tools/PaintingTruth/colour/colour_annotations.json"
OUT_DIR_REL = "Tools/PaintingTruth/colour"

# 色クラス（画素値）
CLS = {"white": 1, "mizuiro": 2, "ai_mid": 3, "ai_dark": 4, "line": 5, "ochre": 6, "sky_pocket": 7}
CLS_JA = {"white": "白・生成り", "mizuiro": "淡い水色（泡の影の淡い青緑。番号23の調色板の mizuiro）",
          "ai_mid": "藍中（明るい藍。バックログの「水色」に当たる。下の決定）", "ai_dark": "藍濃",
          "line": "藍の線（輪郭の版の線と、その縁の混色）", "ochre": "船の黄土", "sky_pocket": "空の色の閉じた小空域"}
NAME = {v: k for k, v in CLS.items()}
OUTSIDE, SKY = 0, 9
VIS = {0: (70, 70, 70), 1: (255, 255, 255), 2: (150, 225, 200), 3: (40, 120, 200), 4: (15, 30, 90),
       5: (230, 40, 40), 6: (230, 170, 80), 7: (255, 210, 220), 9: (255, 205, 205)}
COLOUR_CLASSES = ["white", "mizuiro", "ai_mid", "ai_dark"]

P = {
    "blur_sigma_hi": 1.2,
    "center_refine_de00": 6.0,
    "center_refine_erode_hi": 3,
    "line_de00": 10.0,
    "sliver_open_hi": {"mizuiro": 2, "ai_mid": 1, "white": 1, "ai_dark": 2},
    "lower_side_min_x_disp": 160.0,
    "lower_side_bridge_disp_px": 6.0,
    "lower_strip_disp_px": [3.0, 12.0],
    "lower_strip_min_run_disp_px": 6,
    "lower_strip_same_band_gap_disp_px": 30,
    "lower_end_extend_disp_px": 80.0,
    "lower_strip_min_dark_between_foam_disp_px": 12,
    "lower_side_band_max_gap_disp_px": 50.0,
    "main_stripe_min_len_disp_px": 150.0,
    "stripe_min_body_contact": 0.3,
    "b270_min_len_disp_px": 20.0,
    "band_smooth_samples": 31,
    "thin_dark_open_hi": 4,
    "stroke_fragment_max_hi_px2": 173,
    "stroke_fragment_line_contact": 0.5,
    "min_component_hi_px2": 60,
    "dot_max_hi_px2": 4000,
    "stripe_min_hi_px2": 1000,
    "stripe_min_elong": 2.5,
    "end_probe_disp_px": 8.0,
    "contour_eps_hi": 0.35,
    "region_min_vector_hi_px2": 60,
    "band_max_disp_px": 320.0,
    "band_step_disp_px": 2.0,
    "band_blue_min_area_disp_px2": 1500.0,
    "colour_erode_disp_px": 3,
}
P_JA = {
    "blur_sigma_hi": "分類の前に Lab をガウスで平滑する σ（hi px）。紙の繊維と JPEG の雑音を抑える",
    "center_refine_de00": "中心の色の再推定（1回）に使う画素：最も近い中心まで ΔE00 がこの値未満",
    "center_refine_erode_hi": "同：各クラスをこの半径（hi px）の円で縮めた内側だけを使う",
    "line_de00": "最も近い中心まで ΔE00 がこの値以上の画素は『線・混色』（藍の輪郭線の芯と縁）",
    "sliver_open_hi": "この半径（hi px）の開きで消える色の細片（色の境の混色の縁）を、隣の色面へ吸収する",
    "thin_dark_open_hi": "藍濃のうち、この半径の開きで消え、白・淡い水色に接する細い部分は線として扱う",
    "stroke_fragment_max_hi_px2": "線の切れ端とみなす藍中・藍濃の成分の最大面積（hi px²。表示 px² で約 30）",
    "stroke_fragment_line_contact": "同：周長のうち線に接する割合がこの値以上なら線とする（輪郭線の縁の混色で、色区ではない）",
    "min_component_hi_px2": "これより小さい連結成分（hi px²）は周りへ吸収する（表示 px² で約 10）",
    "dot_max_hi_px2": "藍の胴の中の白い点とみなす最大面積（hi px²、表示 px² で約 690）",
    "stripe_min_hi_px2": "藍中の帯（縞の間の明るい帯）とみなす最小面積（hi px²、表示 px² で約 173）",
    "stripe_min_elong": "同：中心線の長さ／平均幅の最小値",
    "end_probe_disp_px": "縞の端の種類（遮蔽・泡・藍濃の中）を決めるために端の先を調べる距離（表示 px）",
    "contour_eps_hi": "境界の折れ線の間引き（Douglas–Peucker の許容、hi px）",
    "region_min_vector_hi_px2": "ベクター化する連結成分の最小面積（hi px²）",
    "band_max_disp_px": "134 の白い帯の幅を測る法線の最大長（表示 px）",
    "band_step_disp_px": "134 の帯の幅を測る間隔（輪郭に沿って、表示 px）",
    "band_blue_min_area_disp_px2": "134 の帯の内側の縁とみなす藍（藍中・藍濃）の成分の最小面積（表示 px²）。これより小さい爪の中の藍の斑は帯の一部として通り抜ける（175 の対象）",
    "colour_erode_disp_px": "色の中央値を取る前に色区を縮める半径（表示 px。計画の規則どおり 3 px）",
    "lower_side_min_x_disp": "『下側』から除く画面左端の範囲（表示 x がこの値未満の外周）",
    "lower_side_bridge_disp_px": "『下側』の外周の途切れをつなぐ最大の長さ（表示 px）",
    "lower_strip_disp_px": "藍濃の縞を数える帯状の範囲：主浪の外からの距離（表示 px）の下限と上限",
    "lower_strip_min_run_disp_px": "下側に沿った並びで、これより短い藍濃・泡の区間（表示 px）は前の区間へ吸収する",
    "lower_strip_same_band_gap_disp_px": "同じ帯に挟まれた、これ以下の長さ（表示 px）の区間は帯の一部とする（帯が下側に沿って走り、帯状の範囲を出入りする所）",
    "lower_strip_min_dark_between_foam_disp_px": "泡に挟まれた藍濃の区間がこれより短い（表示 px）ときは泡の一部とする（泡の中の線の切れ端）",
    "lower_end_extend_disp_px": "下側に届かない帯の下端から、中心線の向きに延ばして下側に当たる点を探す最大の長さ（表示 px）。当たった点の弧長で並べる",
    "lower_side_band_max_gap_disp_px": "下端から『下側』までの距離がこれ以下の藍中の帯を、下側から始まる帯（SL）として数える（表示 px）",
    "main_stripe_min_len_disp_px": "主要な縞（118）：下側から始まる帯（つなぎを含む）の中心線の長さの合計の最小値（表示 px）",
    "stripe_min_body_contact": "藍中の帯とみなすには、輪郭の外側の画素のうちこの割合以上が藍濃（胴）であること（輪郭線の縁の藍中を除く）",
    "b270_min_len_disp_px": "270 の境界として数える白と明るい青の境の区間の最小の長さ（表示 px）",
    "band_smooth_samples": "134 の帯の幅の移動平均の点数（2 表示 px おき）",
}


# ================================================================= 基本
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    try:
        r = os.path.relpath(p, REPO).replace("\\", "/")
        return p.replace("\\", "/") if r.startswith("..") else r
    except ValueError:
        return p.replace("\\", "/")


def disk(r):
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))


def r3(v):
    return [round(float(x), 3) for x in v]


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _enc(o, ind):
    """indent 1 の JSON。数の列と、数の組（点）の列は 1 行にまとめる。"""
    pad = " " * ind
    if isinstance(o, dict):
        if not o:
            return "{}"
        items = [pad + " " + json.dumps(str(k), ensure_ascii=False) + ": " + _enc(v, ind + 1) for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(o, (list, tuple)):
        if not o:
            return "[]"
        if all(_is_num(v) for v in o) or all(isinstance(v, (list, tuple)) and all(_is_num(u) for u in v) for v in o):
            return json.dumps(o, ensure_ascii=False, separators=(",", ":"))
        items = [pad + " " + _enc(v, ind + 1) for v in o]
        return "[\n" + ",\n".join(items) + "\n" + pad + "]"
    return json.dumps(o, ensure_ascii=False)


def save_json(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    obj = json.loads(json.dumps(obj, ensure_ascii=False))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_enc(obj, 0))
        f.write("\n")


class Frame:
    """高解像度原画（W×H）と表示フレーム 1920×1080 の写像（番号23 v0.2 と同じ式）。"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.s = 1080.0 / H
        self.ox = (1920.0 - W * self.s) / 2.0

    def h2d(self, p):
        p = np.asarray(p, np.float64)
        return np.stack([self.s * (p[..., 0] + 0.5) - 0.5 + self.ox, self.s * (p[..., 1] + 0.5) - 0.5], -1)

    def d2h(self, p):
        p = np.asarray(p, np.float64)
        return np.stack([(p[..., 0] + 0.5 - self.ox) / self.s - 0.5, (p[..., 1] + 0.5) / self.s - 0.5], -1)

    def disp_to_hi_map(self, img, interp=cv2.INTER_LINEAR):
        xs = (self.s * (np.arange(self.W) + 0.5) - 0.5 + self.ox).astype(np.float32)
        ys = (self.s * (np.arange(self.H) + 0.5) - 0.5).astype(np.float32)
        mx, my = np.meshgrid(xs, ys)
        return cv2.remap(img, mx, my, interp)

    def hi_to_disp_cov(self, mask, ss=3):
        """hi px の 0/1 マスク → 表示フレームの被覆率。ss×ss の超標本化格子へ双線形で写して平均（番号23 v0.2 と同じ）。"""
        a = 1.0 / (ss * self.s)
        bx = (0.5 / ss - self.ox) / self.s - 0.5
        by = (0.5 / ss) / self.s - 0.5
        M = np.array([[a, 0, bx], [0, a, by]], np.float64)
        up = cv2.warpAffine(mask.astype(np.float32), M, (1920 * ss, 1080 * ss),
                            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return up.reshape(1080, ss, 1920, ss).mean(axis=(1, 3))

    def poly_mask_hi(self, pts_disp):
        m = np.zeros((self.H, self.W), np.uint8)
        q = self.d2h(np.asarray(pts_disp, np.float64))
        cv2.fillPoly(m, [np.round(q * 8).astype(np.int32)], 1, lineType=cv2.LINE_8, shift=3)
        return m > 0

    def disp_image(self, rgb):
        M = np.array([[self.s, 0, 0.5 * self.s - 0.5 + self.ox], [0, self.s, 0.5 * self.s - 0.5]])
        return cv2.warpAffine(rgb, M, (1920, 1080), flags=cv2.INTER_AREA, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


def de00_to_centers(lab, centers, chunk=400):
    H, W, _ = lab.shape
    out = np.empty((H, W, len(centers)), np.float32)
    for y in range(0, H, chunk):
        sl = lab[y:y + chunk].astype(np.float64)
        for k, c in enumerate(centers):
            out[y:y + chunk, :, k] = T.ciede2000(sl, np.broadcast_to(np.asarray(c, np.float64), sl.shape))
    return out


def nearest_label_fill(label, holes):
    """holes の画素を、holes でない最も近い画素の値で埋める（Voronoi）。"""
    if not holes.any():
        return label
    src = (~holes).astype(np.uint8)
    _, idx = cv2.distanceTransformWithLabels(1 - src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(src)
    lut = np.zeros(len(ys) + 1, label.dtype)
    lut[1:] = label[ys, xs]
    out = label.copy()
    out[holes] = lut[idx[holes]]
    return out


def fill_holes(mask):
    m = mask.astype(np.uint8)
    h, w = m.shape
    ff = np.pad(m, 1).copy()
    flood = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(ff, flood, (0, 0), 2)
    return (ff[1:-1, 1:-1] != 2)


def polyline_len(P):
    P = np.asarray(P, np.float64)
    return float(np.sum(np.linalg.norm(np.diff(P, axis=0), axis=1))) if len(P) > 1 else 0.0


def resample(P, step):
    P = np.asarray(P, np.float64)
    if len(P) < 2:
        return P
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    n = max(2, int(np.ceil(d[-1] / step)) + 1)
    t = np.linspace(0, d[-1], n)
    return np.stack([np.interp(t, d, P[:, 0]), np.interp(t, d, P[:, 1])], -1)


def smooth_polyline(P, sigma):
    P = np.asarray(P, np.float64)
    if len(P) < 5 or sigma <= 0:
        return P
    r = int(3 * sigma)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    Q = np.stack([np.convolve(np.pad(P[:, i], r, mode="edge"), k, mode="valid") for i in range(2)], -1)
    Q[0], Q[-1] = P[0], P[-1]
    return Q


# ================================================================= 第1段：画素の色クラス
def classify(lab, sky, pal23, log):
    labs = np.stack([cv2.GaussianBlur(lab[..., i], (0, 0), P["blur_sigma_hi"]) for i in range(3)], -1)
    names = ["white", "mizuiro", "ai_mid", "ai_dark", "ochre", "sky_pocket"]
    init = [pal23["white"]["lab"], pal23["mizuiro"]["lab"], pal23["ai_mid"]["lab"], pal23["ai_dark"]["lab"],
            pal23["boat_ochre"]["lab"], pal23["sky_top"]["lab"]]
    C = np.array(init, np.float64)
    water = ~sky
    de = de00_to_centers(labs, C)
    l = de.argmin(-1)
    dmin = de.min(-1)
    conf = (dmin < P["center_refine_de00"]) & water
    refined = {}
    for k, n in enumerate(names[:4]):
        m = cv2.erode(((l == k) & conf).astype(np.uint8), disk(P["center_refine_erode_hi"])) > 0
        refined[n] = {"lab_init_from_23": r3(C[k]), "n_hi_px": int(m.sum())}
        if m.sum() > 500:
            C[k] = np.median(labs[m].astype(np.float64), 0)
        refined[n]["lab_refined"] = r3(C[k])
    de = de00_to_centers(labs, C)
    l = de.argmin(-1)
    dmin = de.min(-1)
    del de
    raw = np.zeros(sky.shape, np.uint8)
    for k, n in enumerate(names):
        raw[l == k] = CLS[n]
    raw[dmin >= P["line_de00"]] = CLS["line"]
    raw[sky] = SKY
    log["centers"] = {n: r3(C[k]) for k, n in enumerate(names)}
    log["center_refine"] = refined
    log["raw_counts_hi_px"] = {n: int((raw == CLS[n]).sum()) for n in CLS}
    return raw, labs, C, names


def clean(raw, sky, log):
    lab = raw.copy()
    water = ~sky
    D = (lab == CLS["ai_dark"]).astype(np.uint8)
    thin = (D > 0) & ~(cv2.morphologyEx(D, cv2.MORPH_OPEN, disk(P["thin_dark_open_hi"])) > 0)
    lightnb = cv2.dilate(((lab == CLS["white"]) | (lab == CLS["mizuiro"])).astype(np.uint8), disk(2)) > 0
    lab[thin & lightnb] = CLS["line"]
    # 線の切れ端：線に接する周長の割合が大きい小さな藍中・藍濃の成分（輪郭線の縁の混色）は線とする
    L = (lab == CLS["line"]).astype(np.uint8)
    adjL = cv2.dilate(L, np.ones((3, 3), np.uint8)) > 0
    frag_total = {}
    for n in ("ai_mid", "ai_dark"):
        m = (lab == CLS[n]).astype(np.uint8)
        k, cc, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        perim = (m > 0) & ~(cv2.erode(m, np.ones((3, 3), np.uint8)) > 0)
        pc = np.bincount(cc[perim], minlength=k).astype(np.float64)
        lc = np.bincount(cc[perim & adjL], minlength=k).astype(np.float64)
        frac = lc / np.maximum(pc, 1)
        bad = np.nonzero((st[:, cv2.CC_STAT_AREA] <= P["stroke_fragment_max_hi_px2"]) & (frac >= P["stroke_fragment_line_contact"]))[0]
        bad = bad[bad > 0]
        mm = np.isin(cc, bad)
        lab[mm] = CLS["line"]
        frag_total[n] = {"components": int(len(bad)), "hi_px": int(mm.sum())}
    holes = np.zeros(lab.shape, bool)
    for n, r in P["sliver_open_hi"].items():
        m = (lab == CLS[n]).astype(np.uint8)
        holes |= (m > 0) & ~(cv2.morphologyEx(m, cv2.MORPH_OPEN, disk(r)) > 0)
    fillable = holes & water
    isline = (lab == CLS["line"]) & water
    lab2 = nearest_label_fill(lab, fillable | isline | sky)
    region = lab2.copy()
    region[sky] = SKY
    small_total = 0
    for _ in range(2):
        holes2 = np.zeros(region.shape, bool)
        for n in ["white", "mizuiro", "ai_mid", "ai_dark", "ochre", "sky_pocket"]:
            m = (region == CLS[n]).astype(np.uint8)
            nc, cc, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
            sid = np.nonzero(st[:, cv2.CC_STAT_AREA] < P["min_component_hi_px2"])[0]
            sid = sid[sid > 0]
            if len(sid):
                holes2 |= np.isin(cc, sid)
        small_total += int(holes2.sum())
        region = nearest_label_fill(region, holes2 | sky)
        region[sky] = SKY
    layer = region.copy()
    layer[isline] = CLS["line"]
    log["clean"] = {"thin_dark_to_line_hi_px": int((thin & lightnb).sum()), "stroke_fragments_to_line": frag_total,
                    "sliver_absorbed_hi_px": int(fillable.sum()),
                    "small_component_absorbed_hi_px": small_total, "line_hi_px": int(isline.sum())}
    return region, layer


# ================================================================= 第2段：主浪への振り分け
def assign_main_wave(region, layer, fr, ann, log):
    Z = ann["zones_display"]
    sky = region == SKY
    zone = fr.poly_mask_hi(Z["main_wave_zone"]["points"]) & ~fr.poly_mask_hi(Z["boat_left_zone"]["points"]) & ~sky
    member = np.zeros(region.shape, bool)
    for c in [1, 2, 3, 4, 6, 7]:
        m = (layer == c).astype(np.uint8)
        n, cc, st, _ = cv2.connectedComponentsWithStats(m, connectivity=4)
        inz = np.bincount(cc[zone], minlength=n)
        ok = inz / np.maximum(st[:, cv2.CC_STAT_AREA], 1) >= 0.5
        ok[0] = False
        member |= ok[cc]
    lines = layer == CLS["line"]
    mem = nearest_label_fill(member.astype(np.uint8), lines | sky) > 0
    mem &= ~sky
    # 空の色の閉じた小空域：主浪の中では白（刷っていない紙）として扱い、面積を記録する
    sp = mem & (region == CLS["sky_pocket"])
    ochre = mem & (region == CLS["ochre"])
    mw_region = np.where(mem, region, OUTSIDE).astype(np.uint8)
    mw_region[sp] = CLS["white"]
    mw_region[ochre] = CLS["white"]
    mw_region[sky] = SKY
    mw_layer = mw_region.copy()
    mw_layer[mem & lines] = CLS["line"]
    lz = fr.poly_mask_hi(Z["left_edge_wave_zone"]["points"])
    log["main_wave"] = {
        "hi_px": {n: int(((mw_region == CLS[n]) & mem).sum()) for n in COLOUR_CLASSES},
        "line_hi_px": int((mw_layer == CLS["line"]).sum()),
        "sky_coloured_pocket_to_white_hi_px": int(sp.sum()),
        "ochre_to_white_hi_px": int(ochre.sum()),
        "left_edge_wave_hi_px": int((mem & lz).sum()),
        "note_ja": "主浪の範囲は、手の多角形 main_wave_zone から左奥船を除き、番号23の空を除いた内側。多角形の辺をまたぐ色の連結成分は、面積の過半がある側へ振り分けた。線の画素は最も近い色の画素の振り分けに従う。空の色に近い画素（左端の黄ばんだ紙など）と黄土に近い画素は、主浪の中では白として数えた。",
    }
    return mw_region, mw_layer, mem, lz


# ================================================================= 輪郭のベクター化
def contours_of(mask, x0, y0):
    """0/1 マスク（切り出し）の境界を 2 倍拡大で取り、hi px の座標（画素中心が整数）で返す。外周と穴。"""
    up = cv2.resize(mask.astype(np.uint8), None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    up = np.pad(up, 2)
    cs, hier = cv2.findContours(up, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None:
        return out
    for c, h in zip(cs, hier[0]):
        q = c[:, 0, :].astype(np.float64) - 2.0
        if len(q) < 3:
            continue
        q = cv2.approxPolyDP(q.astype(np.float32).reshape(-1, 1, 2), P["contour_eps_hi"] * 2, True)[:, 0, :].astype(np.float64)
        q = (q + 0.5) / 2.0 - 0.5
        q[:, 0] += x0
        q[:, 1] += y0
        out.append((q, h[3] >= 0))
    return out


def vectorise_regions(mw_region, fr, log):
    """主浪の色区（白・淡い水色・藍中・藍濃）の連結成分ごとの境界。ID は色の頭文字＋面積の大きい順。"""
    regs = []
    comp_id = np.zeros(mw_region.shape, np.int32)
    prefix = {"white": "W", "mizuiro": "M", "ai_mid": "A", "ai_dark": "D"}
    for n in COLOUR_CLASSES:
        m = (mw_region == CLS[n]).astype(np.uint8)
        k, cc, st, cen = cv2.connectedComponentsWithStats(m, connectivity=4)
        order = [i for i in np.argsort(-st[:, cv2.CC_STAT_AREA]) if i > 0 and st[i, cv2.CC_STAT_AREA] >= P["region_min_vector_hi_px2"]]
        for rank, i in enumerate(order):
            x, y, w, h, a = st[i]
            rid = "%s%03d" % (prefix[n], rank + 1)
            sub = cc[y:y + h, x:x + w] == i
            comp_id[y:y + h, x:x + w][sub] = len(regs) + 1
            cs = contours_of(sub, x, y)
            rings = []
            for q, is_hole in cs:
                d = fr.h2d(q)
                rings.append({"hole": bool(is_hole), "n_points": int(len(q)), "points_display": [r3(p) for p in d]})
            c_d = fr.h2d(np.array(cen[i]))
            regs.append({"id": rid, "class": n, "area_display_px2": round(float(a) * fr.s * fr.s, 2),
                         "area_hi_px2": int(a), "centroid_display": r3(c_d),
                         "bbox_display": r3(list(fr.h2d(np.array([x - 0.5, y - 0.5]))) + list(fr.h2d(np.array([x + w - 0.5, y + h - 0.5])))),
                         "rings": rings, "_label": int(i)})
    log["vector"] = {n: sum(1 for r in regs if r["class"] == n) for n in COLOUR_CLASSES}
    return regs, comp_id


# ================================================================= 骨格（Zhang–Suen）と中心線
def zhang_suen(mask):
    img = np.pad(mask.astype(np.uint8), 1)
    while True:
        changed = False
        for step in (0, 1):
            p = img
            p2, p3, p4 = p[:-2, 1:-1], p[:-2, 2:], p[1:-1, 2:]
            p5, p6, p7 = p[2:, 2:], p[2:, 1:-1], p[2:, :-2]
            p8, p9 = p[1:-1, :-2], p[:-2, :-2]
            c = p[1:-1, 1:-1]
            B = p2.astype(np.int32) + p3 + p4 + p5 + p6 + p7 + p8 + p9
            seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            A = np.zeros_like(B)
            for i in range(8):
                A += ((seq[i] == 0) & (seq[i + 1] == 1))
            if step == 0:
                c1, c2 = p2 * p4 * p6, p4 * p6 * p8
            else:
                c1, c2 = p2 * p4 * p8, p2 * p6 * p8
            m = (c == 1) & (B >= 2) & (B <= 6) & (A == 1) & (c1 == 0) & (c2 == 0)
            if m.any():
                c[m] = 0
                changed = True
        if not changed:
            break
    return img[1:-1, 1:-1]


def skeleton_longest_path(sk):
    ys, xs = np.nonzero(sk)
    if len(ys) == 0:
        return np.zeros((0, 2))
    idx = {(y, x): i for i, (y, x) in enumerate(zip(ys, xs))}
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def bfs(s):
        dist = {s: 0.0}
        prev = {s: None}
        dq = deque([s])
        while dq:
            u = dq.popleft()
            y, x = ys[u], xs[u]
            for dy, dx in nb:
                v = idx.get((y + dy, x + dx))
                if v is not None and v not in dist:
                    dist[v] = dist[u] + (1.4142 if dy and dx else 1.0)
                    prev[v] = u
                    dq.append(v)
        far = max(dist, key=dist.get)
        return far, prev

    a, _ = bfs(0)
    b, prev = bfs(a)
    path = []
    u = b
    while u is not None:
        path.append((xs[u], ys[u]))
        u = prev[u]
    return np.array(path, np.float64)


def skeleton_branch_points(sk):
    k = np.ones((3, 3), np.float32)
    k[1, 1] = 0
    nbr = cv2.filter2D(sk.astype(np.float32), -1, k, borderType=cv2.BORDER_CONSTANT)
    return np.argwhere((sk > 0) & (nbr >= 3))


# ================================================================= 縞の一覧
def line_samples(pts_disp, fr, step_hi=0.5):
    q = fr.d2h(np.asarray(pts_disp, np.float64))
    return resample(q, step_hi)


def runs_along(label_img, comp_img, q):
    """折れ線 q（hi px）に沿ってラベルを標本化し、同じ値の区間（run）に分ける。"""
    xi = np.clip(np.round(q[:, 0]).astype(int), 0, label_img.shape[1] - 1)
    yi = np.clip(np.round(q[:, 1]).astype(int), 0, label_img.shape[0] - 1)
    lv = label_img[yi, xi]
    cv_ = comp_img[yi, xi] if comp_img is not None else np.zeros_like(lv)
    runs = []
    s = 0
    for i in range(1, len(q) + 1):
        if i == len(q) or lv[i] != lv[s] or cv_[i] != cv_[s]:
            runs.append((int(lv[s]), int(cv_[s]), s, i - 1))
            s = i
    return runs


def end_kind(mw_layer, comp_id, regs, pt_hi, direction, fr, own_id):
    """縞の端の点から、中心線の向きに沿って先を調べる。線（藍の輪郭線）は飛ばし、藍濃が 3 表示 px 以上続いた後に
    ほかのものに当たる、または何にも当たらない場合は ai_dark（藍濃の中で細って終わる）。それ以外は最初に当たったものの種類：
    occluder＝主浪の外（前景の波・船）、sky＝空、dot＝藍の胴の中の白い点、foam＝泡（白の大きな成分・淡い水色）。"""
    L = P["end_probe_disp_px"] / fr.s
    d = direction / (np.linalg.norm(direction) + 1e-9)
    votes = []
    for off in (-0.35, 0.0, 0.35):
        rot = np.array([[np.cos(off), -np.sin(off)], [np.sin(off), np.cos(off)]])
        dd = rot @ d
        dark = 0.0
        kind = "ai_dark"
        for t in np.arange(1.0, L, 0.5):
            p = pt_hi + t * dd
            x, y = int(round(p[0])), int(round(p[1]))
            if not (0 <= x < mw_layer.shape[1] and 0 <= y < mw_layer.shape[0]):
                kind = "occluder"
                break
            if comp_id[y, x] == own_id:
                continue
            v = int(mw_layer[y, x])
            if v == CLS["line"]:
                continue
            if v == CLS["ai_dark"]:
                dark += 0.5 * fr.s
                continue
            if dark >= 3.0:
                kind = "ai_dark"
                break
            if v == CLS["white"]:
                cid = comp_id[y, x]
                kind = "dot" if (cid > 0 and regs[cid - 1]["area_hi_px2"] < P["dot_max_hi_px2"]) else "foam"
            else:
                kind = {0: "occluder", 9: "sky", 2: "foam", 3: "other_ai_mid"}.get(v, "other")
            break
        votes.append(kind)
    for k in votes:
        if votes.count(k) >= 2:
            return k
    return votes[1]


def lower_side_run(mw_region, fr):
    """『下側』＝主浪の水（色区 1〜4）の外周のうち、主浪の外（前景の小波・左奥船・下の泡）に接する最長の連続区間。
    画面の左端（表示 x < lower_side_min_x_disp）に接する所は除く。表示 lower_side_bridge_disp_px 以下の途切れはつなぐ。
    左から右へ向きをそろえた hi px の点列（8 近傍の輪郭の画素）と、始点からの弧長（表示 px）を返す。"""
    water = np.isin(mw_region, [1, 2, 3, 4]).astype(np.uint8)
    cs, _ = cv2.findContours(water, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    c = max(cs, key=len)[:, 0, :]
    out = (mw_region == OUTSIDE).astype(np.uint8)
    near = cv2.dilate(out, disk(2)) > 0
    xh_min = fr.d2h(np.array([P["lower_side_min_x_disp"], 0.0]))[0]
    flag = near[c[:, 1], c[:, 0]] & (c[:, 0] >= xh_min)
    n = len(c)
    k0 = int(np.argmin(flag))
    f = np.roll(flag, -k0)
    cc = np.roll(c, -k0, axis=0)
    runs = []
    start = None
    for k in range(n + 1):
        ok = k < n and f[k]
        if ok and start is None:
            start = k
        if not ok and start is not None:
            runs.append([start, k])
            start = None
    bridge = P["lower_side_bridge_disp_px"] / fr.s
    merged = []
    for r_ in runs:
        if merged and r_[0] - merged[-1][1] <= bridge:
            merged[-1][1] = r_[1]
        else:
            merged.append(list(r_))
    best = max(merged, key=lambda r_: r_[1] - r_[0])
    run = cc[best[0]:best[1]].astype(np.float64)
    if run[0, 0] > run[-1, 0]:
        run = run[::-1]
    sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(run, axis=0), axis=1))] * fr.s
    return run, sd, {"n_runs_before_bridge": len(runs), "n_runs_after_bridge": len(merged), "length_display_px": round(float(sd[-1]), 1)}


def lower_strip_sequence(mw_region, mw_layer, comp_id, regs, band_labels, run, sd, fr):
    """下側の帯状の範囲（主浪の外から表示 lower_strip_disp_px[0]〜[1] px の水）を、最も近い『下側』の点へ振り分け、
    下側に沿った 1 次元の並び（表示 1 px おき）に畳む。各標本は、帯（藍中の帯の成分番号）・藍濃（藍濃・線・藍の胴の中の白い点）・
    泡（大きな白・淡い水色・帯でない藍中）のどれかの多数決。"""
    H, W = mw_region.shape
    zero = np.ones((H, W), np.uint8)
    ri = np.round(run).astype(int)
    zero[ri[:, 1], ri[:, 0]] = 0
    _, lab = cv2.distanceTransformWithLabels(zero, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.nonzero(zero == 0)
    # 輪郭の画素（ラスタ順）→ 下側の点の番号（同じ画素が 2 回出る所は後の番号）
    idx_of_pix = {}
    for k, (x, y) in enumerate(ri):
        idx_of_pix[(y, x)] = k
    lut = np.full(len(ys) + 1, -1, np.int64)
    for j, (y, x) in enumerate(zip(ys, xs)):
        lut[j + 1] = idx_of_pix[(y, x)]
    dtO = cv2.distanceTransform((mw_region != OUTSIDE).astype(np.uint8), cv2.DIST_L2, 5) * fr.s
    water = np.isin(mw_region, [1, 2, 3, 4])
    lo_, hi_ = P["lower_strip_disp_px"]
    strip = water & (dtO >= lo_) & (dtO <= hi_)
    sy, sx = np.nonzero(strip)
    ridx = lut[lab[sy, sx]]
    ok = ridx >= 0
    sy, sx, ridx = sy[ok], sx[ok], ridx[ok]
    # 近い点への距離が帯の幅を大きく超えるもの（別の縁の近く）を除く
    dd = np.linalg.norm(run[ridx] - np.stack([sx, sy], -1), axis=1) * fr.s
    ok = dd <= hi_ + 3.0
    sy, sx, ridx = sy[ok], sx[ok], ridx[ok]
    v = mw_layer[sy, sx]
    cid = comp_id[sy, sx]
    area = np.array([0] + [r["area_hi_px2"] for r in regs])
    is_band = np.isin(cid, list(band_labels)) & (v == CLS["ai_mid"])
    small_white = (v == CLS["white"]) & (area[cid] < P["dot_max_hi_px2"])
    is_dark = ~is_band & ((v == CLS["ai_dark"]) | (v == CLS["line"]) | small_white | ((v == CLS["ai_mid"]) & ~is_band))
    is_foam = ~is_band & ~is_dark
    # 表示 1 px おきの標本へ
    nb = int(np.ceil(sd[-1])) + 1
    bin_ = np.clip(np.round(sd[ridx]).astype(int), 0, nb - 1)
    nd = np.bincount(bin_[is_dark], minlength=nb)
    nf = np.bincount(bin_[is_foam], minlength=nb)
    nbnd = np.bincount(bin_[is_band], minlength=nb)
    # 帯の標本の成分番号の最頻値（標本ごと）
    bmode = np.zeros(nb, np.int64)
    if is_band.any():
        bb, cc_ = bin_[is_band], cid[is_band]
        order = np.lexsort((cc_, bb))
        bb, cc_ = bb[order], cc_[order]
        key = bb.astype(np.int64) * (len(regs) + 2) + cc_
        uk, cnt = np.unique(key, return_counts=True)
        ub, uc = uk // (len(regs) + 2), uk % (len(regs) + 2)
        best_cnt = np.zeros(nb, np.int64)
        for b_, c_, n_ in zip(ub, uc, cnt):
            if n_ > best_cnt[b_]:
                best_cnt[b_] = n_
                bmode[b_] = c_
    seq = []
    for k in range(nb):
        if nbnd[k] == 0 and nd[k] == 0 and nf[k] == 0:
            seq.append(("none", None))
            continue
        best = max([("dark", nd[k]), ("foam", nf[k]), ("band", nbnd[k])], key=lambda t: t[1])
        seq.append(("band", int(bmode[k])) if best[0] == "band" else (best[0], None))
    # 標本の無い所は前の値で埋める
    last = ("foam", None)
    for k in range(nb):
        if seq[k][0] == "none":
            seq[k] = last
        last = seq[k]
    return seq


def lower_strip_runs(seq, run, sd, fr):
    """lower_strip_sequence の並びを区間（run）にまとめる。表示 lower_strip_min_run_disp_px 未満の短い区間は前の区間へ吸収する。"""
    segs = []
    for k, e in enumerate(seq):
        if segs and segs[-1]["e"] == e:
            segs[-1]["k1"] = k
        else:
            segs.append({"e": e, "k0": k, "k1": k})
    mn = P["lower_strip_min_run_disp_px"]
    mb = P["lower_strip_same_band_gap_disp_px"]

    def length(g):
        return g["k1"] - g["k0"] + 1

    def coalesce(segs):
        out = []
        for g in segs:
            if out and out[-1]["e"] == g["e"]:
                out[-1]["k1"] = g["k1"]
            else:
                out.append(g)
        return out
    changed = True
    while changed and len(segs) > 1:
        changed = False
        for j, g in enumerate(segs):
            if g["e"][0] == "band":
                continue
            prv = segs[j - 1] if j > 0 else None
            nxt = segs[j + 1] if j + 1 < len(segs) else None
            # 同じ帯の間の短い区間（帯が下側に沿って走り、帯状の範囲を出入りする所）→ 帯
            if prv and nxt and prv["e"] == nxt["e"] and prv["e"][0] == "band" and length(g) <= mb:
                g["e"] = prv["e"]
                changed = True
                break
            # 泡に挟まれた短い藍濃（泡の中の線の切れ端）→ 泡
            if prv and nxt and prv["e"][0] == "foam" and nxt["e"][0] == "foam" and g["e"][0] == "dark" and length(g) < P["lower_strip_min_dark_between_foam_disp_px"]:
                g["e"] = prv["e"]
                changed = True
                break
            # 短い区間 → 前（先頭なら後ろ）へ吸収
            if length(g) < mn:
                if prv is not None:
                    prv["k1"] = g["k1"]
                else:
                    nxt["k0"] = g["k0"]
                del segs[j]
                changed = True
                break
        segs = coalesce(segs)
    def pt(sv):
        i = int(np.clip(np.searchsorted(sd, sv), 0, len(sd) - 1))
        return r3(fr.h2d(run[i]))
    for g in segs:
        g["from_display"] = pt(g["k0"])
        g["to_display"] = pt(g["k1"])
        g["s_from"] = float(g["k0"])
        g["s_to"] = float(g["k1"])
        g["len"] = float(g["k1"] - g["k0"] + 1)
    return segs


END_JA = {"occluder": "遮蔽（前景の波・船の縁で切れる）", "sky": "空", "foam": "泡（白・淡い水色・線）",
          "dot": "藍の胴の中の白い点", "other_ai_mid": "別の藍中", "ai_dark": "藍濃の中で細って終わる",
          "undetermined": "不定"}


def stripe_inventory(mw_region, mw_layer, regs, comp_id, fr, ann, log):
    """藍中の帯（バックログの「水色」の帯）の一覧と、その間の藍濃の縞（バックログの「藍の縞」）の一覧。"""
    lab_of = {r["id"]: i + 1 for i, r in enumerate(regs)}
    A_regs = [r for r in regs if r["class"] == "ai_mid" and r["area_hi_px2"] >= P["stripe_min_hi_px2"]]
    run, sd, run_info = lower_side_run(mw_region, fr)
    dto = cv2.distanceTransform((mw_region != OUTSIDE).astype(np.uint8), cv2.DIST_L2, 5)
    cand = []
    rejected = []
    for r in A_regs:
        i = lab_of[r["id"]]
        ys, xs = np.nonzero(comp_id == i)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        sub = comp_id[y0:y1, x0:x1] == i
        ya, yb, xa, xb = max(0, y0 - 3), min(fr.H, y1 + 3), max(0, x0 - 3), min(fr.W, x1 + 3)
        own = comp_id[ya:yb, xa:xb] == i
        ringm = (cv2.dilate(own.astype(np.uint8), disk(2)) > 0) & ~own
        rv = mw_region[ya:yb, xa:xb][ringm]
        contact = float(np.isin(rv, [CLS["ai_dark"]]).mean()) if len(rv) else 0.0
        if contact < P["stripe_min_body_contact"]:
            rejected.append({"region": r["id"], "reason": "body_contact %.2f" % contact})
            continue
        subf = fill_holes(sub)
        sk = zhang_suen(np.pad(subf, 2))[2:-2, 2:-2]
        path = skeleton_longest_path(sk)
        if len(path) < 5:
            continue
        path[:, 0] += x0
        path[:, 1] += y0
        dt = cv2.distanceTransform(np.pad(subf, 1).astype(np.uint8), cv2.DIST_L2, 5)[1:-1, 1:-1]
        cl = smooth_polyline(resample(path, 2.0), 3.0)
        length_hi = polyline_len(cl)
        mean_w = float(subf.sum()) / max(length_hi, 1.0)
        if length_hi / max(mean_w, 1e-6) < P["stripe_min_elong"]:
            rejected.append({"region": r["id"], "reason": "elongation %.2f" % (length_hi / max(mean_w, 1e-6))})
            continue
        if cl[0, 1] < cl[-1, 1]:
            cl = cl[::-1]
        clr = resample(cl, 1.0 / fr.s)  # 1 表示 px おき
        xi = np.clip(np.round(clr[:, 0] - x0).astype(int), 0, subf.shape[1] - 1)
        yi = np.clip(np.round(clr[:, 1] - y0).astype(int), 0, subf.shape[0] - 1)
        wd = 2.0 * dt[yi, xi] * fr.s
        lower, upper = cl[0], cl[-1]
        dl = cl[0] - cl[min(8, len(cl) - 1)]
        du = cl[-1] - cl[max(0, len(cl) - 9)]
        lk = end_kind(mw_layer, comp_id, regs, lower, dl, fr, i)
        uk = end_kind(mw_layer, comp_id, regs, upper, du, fr, i)
        outer = [rg for rg in r["rings"] if not rg["hole"]]
        sides = {}
        if outer:
            ring = np.array(outer[0]["points_display"])
            ld, ud = fr.h2d(lower), fr.h2d(upper)
            il = int(np.argmin(np.linalg.norm(ring - ld, axis=1)))
            iu = int(np.argmin(np.linalg.norm(ring - ud, axis=1)))
            if il <= iu:
                a1 = ring[il:iu + 1]
                a2 = np.r_[ring[iu:], ring[:il + 1]][::-1]
            else:
                a1 = np.r_[ring[il:], ring[:iu + 1]]
                a2 = ring[iu:il + 1][::-1]
            dirv = ud - ld

            def side_sign(arc):
                mid = arc[len(arc) // 2]
                v = mid - ld
                return np.sign(dirv[0] * v[1] - dirv[1] * v[0])
            left, right = (a1, a2) if side_sign(a1) < 0 else (a2, a1)
            sides = {"left_display": [r3(p) for p in left], "right_display": [r3(p) for p in right]}
        n = len(wd)
        q = lambda f: round(float(wd[min(n - 1, int(f * (n - 1)))]), 2)
        cand.append({
            "region": r["id"], "_label": i,
            "area_display_px2": r["area_display_px2"],
            "length_display_px": round(length_hi * fr.s, 2),
            "width_display_px": {"median": round(float(np.median(wd)), 2), "p10": round(float(np.percentile(wd, 10)), 2),
                                 "p90": round(float(np.percentile(wd, 90)), 2), "max": round(float(wd.max()), 2),
                                 "at_25_50_75_percent_from_lower": [q(0.25), q(0.5), q(0.75)],
                                 "argmax_fraction_from_lower": round(float(np.argmax(wd) / max(1, n - 1)), 3)},
            "lower_end_display": r3(fr.h2d(lower)), "lower_end_kind": lk,
            "lower_end_gap_to_occluder_display_px": round(float(dto[int(round(lower[1])), int(round(lower[0]))]) * fr.s, 2),
            "body_contact": round(contact, 3),
            "upper_end_display": r3(fr.h2d(upper)), "upper_end_kind": uk,
            "centerline_display": [r3(p) for p in fr.h2d(clr)],
            "width_profile_display_px": [round(float(v), 2) for v in wd],
            **sides,
        })
    by_label = {c["_label"]: c for c in cand}
    # ---- 下側：帯の下端を『下側』の点へ写し、弧長で並べる
    for c in cand:
        lh = fr.d2h(np.array(c["lower_end_display"]))
        d = np.linalg.norm(run - lh, axis=1)
        k = int(np.argmin(d))
        c["lower_side_gap_display_px"] = round(float(d[k] * fr.s), 2)
        # 中心線の下端の向き（下端から表示 12 px 上の点 → 下端）へ延ばし、主浪の外から表示 lower_strip_disp_px[0] 以内に入った点
        cl = fr.d2h(np.array(c["centerline_display"]))
        j = min(len(cl) - 1, 12)
        dv = cl[0] - cl[j]
        dv = dv / (np.linalg.norm(dv) + 1e-9)
        hit = None
        for t in np.arange(0.0, P["lower_end_extend_disp_px"], 0.5):
            q = lh + dv * (t / fr.s)
            x, y = int(round(q[0])), int(round(q[1]))
            if not (0 <= x < fr.W and 0 <= y < fr.H):
                break
            if dto[y, x] * fr.s <= P["lower_strip_disp_px"][0]:
                hit = q
                break
        if hit is not None:
            k = int(np.argmin(np.linalg.norm(run - hit, axis=1)))
            c["lower_side_hit"] = "extended_centerline"
            c["lower_side_extension_display_px"] = round(float(np.linalg.norm(hit - lh) * fr.s), 2)
        else:
            c["lower_side_hit"] = "nearest_point"
            c["lower_side_extension_display_px"] = None
        c["lower_side_s_display_px"] = round(float(sd[k]), 2)
        c["lower_side_point_display"] = r3(fr.h2d(run[k]))
    seq = lower_strip_sequence(mw_region, mw_layer, comp_id, regs, set(by_label), run, sd, fr)
    segs = lower_strip_runs(seq, run, sd, fr)
    crossing = []
    for g in segs:
        if g["e"][0] == "band" and g["e"][1] not in crossing:
            crossing.append(g["e"][1])
    low_set = [c["_label"] for c in cand if c["lower_side_gap_display_px"] <= P["lower_side_band_max_gap_disp_px"] or c["_label"] in crossing]
    low_set.sort(key=lambda l: by_label[l]["lower_side_s_display_px"])
    for k, l in enumerate(low_set):
        by_label[l]["id"] = "SL%02d" % (k + 1)
        by_label[l]["reaches_lower_strip"] = l in crossing
    # ---- 上側：手の数え線 curl_upper（左から右）
    up_order = []
    for ln, v in ann["counting_lines_display"].items():
        qh = line_samples(v["points"], fr)
        for (lv, cid_, s0, s1) in runs_along(mw_region, comp_id, qh):
            if lv == CLS["ai_mid"] and cid_ in by_label and "id" not in by_label[cid_] and cid_ not in up_order and (s1 - s0 + 1) * 0.5 * fr.s >= 1.5:
                up_order.append(cid_)
    for k, l in enumerate(up_order):
        by_label[l]["id"] = "SU%02d" % (k + 1)
    others = sorted([c for c in cand if "id" not in c], key=lambda c: -c["area_display_px2"])
    for k, c in enumerate(others):
        c["id"] = "SO%02d" % (k + 1)
    for c in cand:
        c.setdefault("reaches_lower_strip", False)
    sid_of = {c["_label"]: c["id"] for c in cand}
    # ---- 藍濃の縞（KL）：下側の帯状の範囲の並びで、藍中の帯・泡に挟まれた藍濃の区間
    seq_out = []
    for g in segs:
        kind = g["e"][0]
        rec = {"kind": {"band": "ai_mid_band", "dark": "ai_dark_stripe", "foam": "foam"}[kind],
               "from_display": g["from_display"], "to_display": g["to_display"],
               "s_from_display_px": g["s_from"], "s_to_display_px": g["s_to"], "length_on_lower_side_display_px": g["len"]}
        if kind == "band":
            rec["band"] = sid_of[g["e"][1]]
        seq_out.append(rec)

    def side(r_):
        if r_ is None:
            return "end"
        return r_["band"] if r_["kind"] == "ai_mid_band" else r_["kind"]
    dark = []
    for j, rec in enumerate(seq_out):
        if rec["kind"] != "ai_dark_stripe":
            continue
        if 0 < j < len(seq_out) - 1 and seq_out[j - 1].get("band") and seq_out[j - 1].get("band") == seq_out[j + 1].get("band"):
            continue
        prv = seq_out[j - 1] if j > 0 else None
        nxt = seq_out[j + 1] if j + 1 < len(seq_out) else None
        under = [c["id"] for c in cand if c["lower_side_gap_display_px"] <= P["lower_side_band_max_gap_disp_px"]
                 and not c["reaches_lower_strip"] and rec["s_from_display_px"] <= c["lower_side_s_display_px"] <= rec["s_to_display_px"]]
        dark.append({"between": [side(prv), side(nxt)], "from_display": rec["from_display"], "to_display": rec["to_display"],
                     "s_from_display_px": rec["s_from_display_px"], "s_to_display_px": rec["s_to_display_px"],
                     "width_on_lower_side_display_px": rec["length_on_lower_side_display_px"],
                     "bands_ending_above": sorted(under)})
    for k, d in enumerate(dark):
        d["id"] = "KL%02d" % (k + 1)
    # ---- 手のつなぎ（同じ帯が泡・白い点で途切れた所）
    chains = {}
    chain_of = {}
    for cn, cv in ann.get("stripe_links_display", {}).get("chains", {}).items():
        mem = []
        for p in cv["points"]:
            h = fr.d2h(np.array(p, np.float64))
            cid_ = int(comp_id[int(round(h[1])), int(round(h[0]))])
            if cid_ not in by_label:
                cid_ = min(by_label, key=lambda l: np.linalg.norm(np.array(regs[l - 1]["centroid_display"]) - np.array(p)))
            if sid_of[cid_] not in mem:
                mem.append(sid_of[cid_])
            chain_of[sid_of[cid_]] = cn
        chains[cn] = {"stripes": mem, "basis_ja": cv.get("basis_ja", ""), "source": "manual（agent の判断。利用者の抜き取り確認待ち）",
                      "note_ja": "手の点がすべて同じ連結成分に入った（色区の地図の上で既に1本につながっている）" if len(mem) == 1 else ""}
    for c in cand:
        c["chain"] = chain_of.get(c["id"])
    # ---- 主要な縞（118）：下側から始まる帯（またはそれを含むつなぎ）で、中心線の長さの合計が main_stripe_min_len 以上
    by_id = {c["id"]: c for c in cand}
    main = []
    seen = set()
    for l in low_set:
        c = by_label[l]
        grp = chains[c["chain"]]["stripes"] if c["chain"] else [c["id"]]
        key = tuple(grp)
        if key in seen:
            continue
        seen.add(key)
        L = sum(by_id[g]["length_display_px"] for g in grp)
        if L >= P["main_stripe_min_len_disp_px"]:
            top = min((by_id[g] for g in grp), key=lambda z: z["upper_end_display"][1])
            main.append({"id": "MS%02d" % (len(main) + 1), "bands": list(grp), "lower_band": c["id"],
                         "total_centerline_length_display_px": round(L, 1),
                         "lower_end_display": c["lower_end_display"], "upper_end_display": top["upper_end_display"]})
    # ---- 分岐の候補（178、記録のみ）：藍中の帯の端が藍濃の中で終わる所では、両側の藍濃の縞がそこで1本につながる
    branches = []
    for c in cand:
        for which in ("lower", "upper"):
            if c[which + "_end_kind"] != "ai_dark":
                continue
            if which == "lower" and c["reaches_lower_strip"]:
                continue
            branches.append({"stripe": c["id"], "end": which, "point_display": c[which + "_end_display"],
                             "meaning_ja": "この点より%sでは、両側の藍濃の縞が1本につながる（藍の縞の分岐点）。" % ("下" if which == "lower" else "上")})
    # 並び順による上下の対応の候補（記録のみ）：右から数えて同じ順位
    up = [sid_of[l] for l in up_order]
    lo = [sid_of[l] for l in low_set]
    order_cand = []
    for k in range(1, max(len(up), len(lo)) + 1):
        order_cand.append({"rank_from_right": k, "upper": up[-k] if k <= len(up) else None, "lower": lo[-k] if k <= len(lo) else None})
    for c in cand:
        del c["_label"]
    cand.sort(key=lambda c: (c["id"][:2], c["id"]))
    lower_side_disp = [r3(p_) for p_ in fr.h2d(resample(run, 1.0 / fr.s))]
    lower = {"run_display": lower_side_disp, "info": run_info, "sequence": seq_out,
             "definition_ja": "『下側』＝主浪の水の外周のうち、主浪の外（前景の小波・左奥船・下の泡の帯）に接する最長の連続区間（画面左端は除く。表示 %.0f px 以下の途切れはつなぐ）。向きは左端の下から前景の小波の右の端へ。帯状の範囲＝主浪の外から表示 %.0f〜%.0f px の水。藍濃の縞（KL）＝この範囲を下側の点へ振り分け、表示 1 px おきに多数決した並びのうち、藍中の帯・泡に挟まれた藍濃の区間（藍の胴の中の白い点・線は藍濃に数える。表示 %.0f px 未満の区間は前へ吸収）。" % (
                 P["lower_side_bridge_disp_px"], P["lower_strip_disp_px"][0], P["lower_strip_disp_px"][1], P["lower_strip_min_run_disp_px"])}
    log["stripes"] = {"n_ai_mid_bands": len(cand), "rejected": rejected,
                      "order": {"lower_side": [sid_of[l] for l in low_set], "curl_upper": up},
                      "n_lower_side_bands": len(low_set), "n_lower_side_bands_reaching_strip": len(crossing),
                      "n_dark_stripes_lower_side": len(dark), "n_main_stripes": len(main), "lower_side_run": run_info}
    return cand, dark, chains, branches, order_cand, lower, main


# ================================================================= 白い帯・内側の帯・白の中の色区
def load_outline(path):
    d = json.load(open(path, encoding="utf-8"))
    return {s["id"]: np.array(s["points_display"], np.float64) for s in d["segments"]}, d


def ring_neighbours(ring_disp, mw_layer, fr, inside_mask_fn, probe=1.2):
    """輪郭の各点で、外向き（領域の外側）に probe 表示 px 進んだ画素の値。"""
    R = np.asarray(ring_disp, np.float64)
    n = len(R)
    out = np.zeros(n, np.int32)
    for i in range(n):
        t = R[(i + 1) % n] - R[i - 1]
        t /= np.linalg.norm(t) + 1e-9
        nrm = np.array([-t[1], t[0]])
        best = None
        for sgn in (1, -1):
            p = fr.d2h(R[i] + sgn * probe * nrm)
            x, y = int(round(p[0])), int(round(p[1]))
            if not (0 <= x < fr.W and 0 <= y < fr.H):
                v, ins = OUTSIDE, False
            else:
                v, ins = int(mw_layer[y, x]), inside_mask_fn(x, y)
            if not ins:
                best = v
                break
        out[i] = best if best is not None else -1
    return out


def split_runs(R, keys):
    """閉じた輪郭 R を keys が同じ区間ごとの折れ線に分ける。"""
    R = np.asarray(R)
    n = len(R)
    if n == 0:
        return []
    ch = np.nonzero(keys != np.roll(keys, 1))[0]
    if len(ch) == 0:
        return [(keys[0], np.r_[R, R[:1]])]
    segs = []
    for j in range(len(ch)):
        s, e = ch[j], ch[(j + 1) % len(ch)]
        idx = np.arange(s, e if e > s else e + n) % n
        idx = np.r_[idx, e % n]
        segs.append((keys[s], R[idx]))
    return segs


def turning_alternation(Pd, step=1.0, sigma=3.0):
    """折れ線の曲がる向き（左右）の入れ替わりの回数（100 表示 px あたり）。270 の『交互に曲がる』の記録用。"""
    if polyline_len(Pd) < 20:
        return None
    Q = smooth_polyline(resample(Pd, step), sigma)
    v = np.diff(Q, axis=0)
    cr = v[:-1, 0] * v[1:, 1] - v[:-1, 1] * v[1:, 0]
    sgn = np.sign(cr[np.abs(cr) > 0.02])
    if len(sgn) < 2:
        return 0.0
    ch = int(np.sum(sgn[1:] != sgn[:-1]))
    return round(ch / (polyline_len(Q) / 100.0), 2)


def white_analysis(mw_region, mw_layer, regs, comp_id, fr, ann, outl, env_sky, log):
    lab_of = {r["id"]: i + 1 for i, r in enumerate(regs)}
    W1 = max([r for r in regs if r["class"] == "white"], key=lambda r: r["area_hi_px2"])
    w1 = comp_id == lab_of[W1["id"]]
    mem = (mw_region != OUTSIDE) & (mw_region != SKY)
    foam = mem & ((mw_layer == CLS["white"]) | (mw_layer == CLS["mizuiro"]) | (mw_layer == CLS["line"]))
    # 白い範囲（175）：主浪の白い成分（W1）と、それに連なる泡（淡い水色・線）の外形の内側
    n, cc, st, _ = cv2.connectedComponentsWithStats(foam.astype(np.uint8), connectivity=8)
    keep = np.unique(cc[w1])
    keep = keep[keep > 0]
    foam_main = np.isin(cc, keep)
    white_range = fill_holes(foam_main) & mem
    # W1 の境界を、隣の色と、手の範囲（white_item_zones_display：79／133／134）で分ける。範囲の外は 0（その他）
    zones = {}
    for it, z in ann.get("white_item_zones_display", {}).items():
        m = np.zeros((1080, 1920), np.uint8)
        cv2.fillPoly(m, [np.round(np.array(z["points"]) * 8).astype(np.int32)], 1, shift=3)
        zones[int(it)] = m > 0

    def inside_w1(x, y):
        return bool(w1[y, x])
    feats = []
    for k, rg in enumerate(W1["rings"]):
        R = np.array(rg["points_display"])
        nb = ring_neighbours(R, mw_layer, fr, inside_w1)
        xi = np.clip(np.round(R[:, 0]).astype(int), 0, 1919)
        yi = np.clip(np.round(R[:, 1]).astype(int), 0, 1079)
        item = np.zeros(len(R), np.int32)
        for it, zm in zones.items():
            item[zm[yi, xi]] = it
        nbk = np.where(nb == SKY, 9, np.where(nb == OUTSIDE, 0, nb))
        key = item * 100 + nbk
        for kk, seg in split_runs(R, key):
            if len(seg) < 3:
                continue
            feats.append({"item_zone": int(kk // 100), "neighbour": int(kk % 100), "ring": k, "hole": rg["hole"],
                          "points": seg})
    # 134：白い帯の幅（132 の外輪郭から内向きに、泡が続く長さ）
    s131 = outl["131"]
    s132 = outl["132"]
    area = np.array([0] + [r["area_display_px2"] for r in regs])
    big_blue = np.isin(mw_region, [CLS["ai_mid"], CLS["ai_dark"]]) & (area[comp_id] >= P["band_blue_min_area_disp_px2"])
    prof = band_width_profile(mw_layer, s132, fr, env_sky, big_blue)
    wv = np.array([p["width"] for p in prof])
    nsm = P["band_smooth_samples"]
    ws = np.convolve(np.pad(wv, nsm // 2, mode="edge"), np.ones(nsm) / nsm, mode="valid") if len(wv) > nsm else wv
    ext = []
    med = float(np.median(ws))
    for k in range(1, len(ws) - 1):
        if ws[k] >= ws[k - 1] and ws[k] > ws[k + 1]:
            ext.append(("wide", k))
        if ws[k] <= ws[k - 1] and ws[k] < ws[k + 1]:
            ext.append(("narrow", k))
    # 小さな揺れを除く（隣の極値との差が中央値の 25% 未満は捨てる）
    ext2 = []
    for e in ext:
        if ext2 and abs(ws[e[1]] - ws[ext2[-1][1]]) < 0.25 * med:
            if (e[0] == "wide" and ws[e[1]] > ws[ext2[-1][1]]) or (e[0] == "narrow" and ws[e[1]] < ws[ext2[-1][1]]):
                if e[0] == ext2[-1][0]:
                    ext2[-1] = e
            continue
        if ext2 and ext2[-1][0] == e[0]:
            if (e[0] == "wide" and ws[e[1]] > ws[ext2[-1][1]]) or (e[0] == "narrow" and ws[e[1]] < ws[ext2[-1][1]]):
                ext2[-1] = e
            continue
        ext2.append(e)
    band = {
        "definition_ja": "134 の白い帯＝番号23の外輪郭 132（包絡版。波頭の 131/132 の境から唇先端まで）から内向きの法線に沿って、藍の胴（面積 ≥ band_blue_min_area の藍中・藍濃の成分）に当たるか、包絡の外（唇の下の空。番号23の sky_envelope）に出るまでの範囲。包絡の内側の爪の間の空は帯の一部として通り抜ける（標本ごとの gap_fraction）。幅は 2 表示 px おきに測り、%d 点の移動平均で広狭を読む（隣の極値との差が中央値の 25%% 未満の揺れは捨てる）。" % P["band_smooth_samples"],
        "start_display": r3(s132[0]), "end_display": r3(s132[-1]),
        "n_samples": len(prof),
        "width_display_px": {"median": round(med, 2), "min": round(float(ws.min()), 2), "max": round(float(ws.max()), 2)},
        "wide_narrow_order_from_crest": [{"kind": e[0], "at_display": prof[e[1]]["p"], "width": round(float(ws[e[1]]), 2),
                                          "arc_fraction": round(e[1] / max(1, len(ws) - 1), 3)} for e in ext2],
        "stop_counts": {k: int(sum(1 for p in prof if p["stop"] == k)) for k in sorted(set(p["stop"] for p in prof))},
        "profile": [{"p": p["p"], "n": p["n"], "width": p["width"], "stop": p["stop"], "gap_fraction": p["gap_fraction"]} for p in prof],
    }
    # 175：白い範囲の中の、白以外の色区（淡い水色・藍中・藍濃）と線
    inv = {}
    items175 = []
    for r in regs:
        if r["class"] == "white":
            continue
        i = lab_of[r["id"]]
        ys, xs = np.nonzero(comp_id == i)
        frac = float(white_range[ys, xs].mean()) if len(ys) else 0.0
        if frac >= 0.9:
            inv.setdefault(r["class"], {"count": 0, "area_display_px2": 0.0})
            inv[r["class"]]["count"] += 1
            inv[r["class"]]["area_display_px2"] += r["area_display_px2"]
            items175.append(r["id"])
    for v in inv.values():
        v["area_display_px2"] = round(v["area_display_px2"], 1)
    line_in = int(((mw_layer == CLS["line"]) & white_range).sum())
    wr_area = float(white_range.sum()) * fr.s * fr.s
    w_in = float((white_range & (mw_region == CLS["white"])).sum()) * fr.s * fr.s
    r175 = {"white_range_area_display_px2": round(wr_area, 1), "white_area_in_range_display_px2": round(w_in, 1),
            "non_white_regions": inv, "line_area_in_range_display_px2": round(line_in * fr.s * fr.s, 1),
            "regions": items175,
            "definition_ja": "白い範囲＝主浪の最大の白の成分（W001：左の白い斜面・波頭・唇の泡）と、それに連なる泡（淡い水色・線）の外形の内側。その中にある白以外の色区（面積の 90% 以上が範囲内）を全部数えた。白の中の色区は、描画の優先順位で白より上に置く対象（計画 4.0）。"}
    # 73/263/265：内側の帯（手のつなぎ inner_face）
    return w1, white_range, feats, band, r175, W1["id"]


def band_width_profile(mw_layer, seg_disp, fr, env_sky, big_blue):
    """134 の白い帯の幅：外輪郭 132（包絡）の各点から内向きの法線に沿って、藍（藍中・藍濃）に当たるか、包絡の外（唇の下の空）に出るまでの長さ。
    包絡の内側の爪の間の空（番号23の爪入り版の空）は帯の一部として通り抜け、その割合を gap_fraction に記す。"""
    Pd = resample(seg_disp, P["band_step_disp_px"])
    out = []
    foamv = (CLS["white"], CLS["mizuiro"], CLS["line"])
    for i in range(len(Pd)):
        a = Pd[max(0, i - 3)]
        b = Pd[min(len(Pd) - 1, i + 3)]
        t = (b - a) / (np.linalg.norm(b - a) + 1e-9)
        n1 = np.array([-t[1], t[0]])
        best = None
        for nn in (n1, -n1):
            ok = 0
            for u in (3.0, 5.0, 7.0):
                h = fr.d2h(Pd[i] + u * nn)
                x, y = int(round(h[0])), int(round(h[1]))
                if 0 <= x < fr.W and 0 <= y < fr.H and not env_sky[y, x] and mw_layer[y, x] != OUTSIDE:
                    ok += 1
            if best is None or ok > best[0]:
                best = (ok, nn)
        nn = best[1]
        L = 0.0
        stop = "max"
        ngap = 0
        nall = 0
        for u in np.arange(0.5, P["band_max_disp_px"], 0.5):
            h = fr.d2h(Pd[i] + u * nn)
            x, y = int(round(h[0])), int(round(h[1]))
            if not (0 <= x < fr.W and 0 <= y < fr.H):
                stop = "frame"
                break
            v = int(mw_layer[y, x])
            if u > 4.0:
                if env_sky[y, x]:
                    stop = "envelope_sky"
                    break
                if v == OUTSIDE or (v in (CLS["ai_mid"], CLS["ai_dark"]) and big_blue[y, x]):
                    stop = {CLS["ai_mid"]: "ai_mid", CLS["ai_dark"]: "ai_dark", OUTSIDE: "outside"}[v]
                    break
            nall += 1
            ngap += int(v == SKY)
            L = u
        out.append({"p": r3(Pd[i]), "n": r3(nn), "width": round(L, 2), "stop": stop, "gap_fraction": round(ngap / max(nall, 1), 3)})
    return out


def region_boundary_by_neighbour(reg, comp_id, regs, mw_layer, fr):
    """ある色区の輪郭を、隣の色（と隣の成分）ごとの区間に分ける。"""
    lab = {r["id"]: i + 1 for i, r in enumerate(regs)}[reg["id"]]

    def inside(x, y):
        return comp_id[y, x] == lab
    segs = []
    for k, rg in enumerate(reg["rings"]):
        R = np.array(rg["points_display"])
        nb = ring_neighbours(R, mw_layer, fr, inside)
        for kk, seg in split_runs(R, nb):
            if len(seg) >= 3:
                segs.append({"neighbour": int(kk), "ring": k, "points": seg})
    return segs


# ================================================================= 色の中央値（表示フレーム、3 px 収縮）
def display_medians(disp_lab, covs):
    out = {}
    for n, cov in covs.items():
        m = (cov >= 0.5).astype(np.uint8)
        m = cv2.erode(m, disk(P["colour_erode_disp_px"])) > 0
        if m.sum() < 20:
            out[n] = None
            continue
        v = disp_lab[m]
        out[n] = {"lab_median": r3(np.median(v, 0)), "n_display_px": int(m.sum()),
                  "lab_p10": r3(np.percentile(v, 10, 0)), "lab_p90": r3(np.percentile(v, 90, 0))}
    return out


def zone_evidence(disp_lab, mw_disp_label, fr, zones, covs, centers_disp):
    ev = {}
    for zn, z in zones.items():
        m = np.zeros((1080, 1920), np.uint8)
        cv2.fillPoly(m, [np.round(np.array(z["points"]) * 8).astype(np.int32)], 1, shift=3)
        m = m > 0
        rec = {"items": z["items"], "area_display_px2": {}, "lab_median_eroded": {}}
        for n in COLOUR_CLASSES + ["line"]:
            rec["area_display_px2"][n] = round(float(((mw_disp_label == CLS[n]) & m).sum()), 1)
        for n in ["mizuiro", "ai_mid"]:
            mm = cv2.erode(((covs[n] >= 0.5) & m).astype(np.uint8), disk(P["colour_erode_disp_px"])) > 0
            if mm.sum() >= 10:
                lm = np.median(disp_lab[mm], 0)
                rec["lab_median_eroded"][n] = {"lab": r3(lm), "n": int(mm.sum()),
                                               "dE00_to_mizuiro_center": round(float(T.ciede2000(lm, centers_disp["mizuiro"])), 2),
                                               "dE00_to_ai_mid_center": round(float(T.ciede2000(lm, centers_disp["ai_mid"])), 2)}
        am, aa = rec["area_display_px2"]["mizuiro"], rec["area_display_px2"]["ai_mid"]
        rec["lighter_than_ai_non_white"] = {"mizuiro_share": round(am / max(am + aa, 1e-9), 3),
                                            "ai_mid_share": round(aa / max(am + aa, 1e-9), 3)}
        rec["dominant_light_blue"] = "ai_mid" if aa > am else "mizuiro"
        ev[zn] = rec
    return ev


# ================================================================= 図（人が確かめるための重ね図。測定には使わない）
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _pil_text(img, items, size=18):
    """日本語の文字を PIL で描く。items = [(x, y, text, rgb)]。"""
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for fp in [r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc"]:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, size)
                break
            except OSError:
                pass
    if font is None:
        font = ImageFont.load_default()
    im = Image.fromarray(img)
    dr = ImageDraw.Draw(im)
    for x, y, t, c in items:
        dr.text((x + 1, y + 1), t, fill=(0, 0, 0), font=font)
        dr.text((x, y), t, fill=tuple(int(v) for v in c), font=font)
    return np.array(im)


def _poly(img, pts, col, th=1, closed=False):
    p = np.round(np.asarray(pts, np.float64) * 4).astype(np.int32)
    if len(p) >= 2:
        cv2.polylines(img, [p], closed, col, th, cv2.LINE_AA, shift=2)


def fig_regions(disp_rgb, disp_label, flat_rgb, path, title):
    base = (disp_rgb.astype(np.float32) * 0.45 + 255 * 0.2).clip(0, 255).astype(np.uint8)
    out = base.copy()
    for n in COLOUR_CLASSES:
        m = disp_label == CLS[n]
        out[m] = flat_rgb[n]
    m = disp_label == CLS["line"]
    out[m] = (220, 40, 40)
    txt = [(20, 20, title, (255, 255, 255))]
    y = 60
    x = 1250
    for n in COLOUR_CLASSES:
        cv2.rectangle(out, (x, y), (x + 30, y + 22), tuple(int(v) for v in flat_rgb[n]), -1)
        cv2.rectangle(out, (x, y), (x + 30, y + 22), (0, 0, 0), 1)
        txt.append((x + 40, y, "%s（%s）" % (CLS_JA[n].split("（")[0], n), (255, 255, 255)))
        y += 30
    cv2.rectangle(out, (x, y), (x + 30, y + 22), (220, 40, 40), -1)
    txt.append((x + 40, y, "藍の線（色面の地図では両側へ吸収）", (255, 255, 255)))
    txt.append((x, y + 34, "主浪の外は原画を暗くして表示。PNG は 256 色", (255, 255, 255)))
    out = _pil_text(out, txt, 20)
    T.save_png_reserved(path, out, [(220, 40, 40)] + [tuple(int(v) for v in flat_rgb[n]) for n in COLOUR_CLASSES])


ENDCOL = {"occluder": (255, 70, 70), "sky": (255, 150, 255), "foam": (255, 230, 60), "dot": (255, 160, 0),
          "ai_dark": (60, 255, 60), "other_ai_mid": (0, 255, 255), "undetermined": (200, 200, 200)}
BANDCOL = {"SL": (0, 235, 255), "SU": (255, 235, 90), "SO": (190, 150, 255)}


def fig_stripes(disp_rgb, band_disp, stripes, dark, chains, branches, main, ann, lower, path):
    """藍の縞の全体図：藍中の帯を種類ごとの色で塗り、ID・下端・上端・主要な縞・つなぎ・分岐の候補を描く。"""
    out = (disp_rgb.astype(np.float32) * 0.5 + 255 * 0.12).clip(0, 255).astype(np.uint8)
    for s in stripes:
        m = band_disp == s["id"]
        col = np.array(BANDCOL[s["id"][:2]], np.float32)
        out[m] = (out[m] * 0.25 + col * 0.75).astype(np.uint8)
    mainb = set(b for ms in main for b in ms["bands"])
    txt = [(20, 20, "28A 藍の縞の一覧（全体）：藍中の帯（バックログの「水色」の帯）の ID と端、主要な縞（118）", (255, 255, 255))]
    _poly(out, lower["run_display"], (255, 255, 255), 2)
    for ln, v in ann["counting_lines_display"].items():
        _poly(out, v["points"], (255, 235, 90), 1)
        p = v["points"][0]
        txt.append((p[0] - 150, p[1] - 12, "数え線 " + ln + "（手）", (255, 235, 90)))
    for s in stripes:
        if s["id"] in mainb:
            _poly(out, s.get("left_display", []), (255, 255, 255), 2)
            _poly(out, s.get("right_display", []), (255, 255, 255), 2)
        lo = np.round(s["lower_end_display"]).astype(int)
        up = np.round(s["upper_end_display"]).astype(int)
        cv2.circle(out, tuple(lo), 6, ENDCOL[s["lower_end_kind"]], 2, cv2.LINE_AA)
        cv2.drawMarker(out, tuple(up), ENDCOL[s["upper_end_kind"]], cv2.MARKER_TRIANGLE_UP, 11, 2)
        if s["id"].startswith("SL"):
            lp = np.array(s["lower_end_display"])
            cv2.line(out, tuple(np.round(lp).astype(int)), tuple(np.round(s["lower_side_point_display"]).astype(int)), (0, 235, 255), 1, cv2.LINE_AA)
    for cn, ch in chains.items():
        pts = [next(s for s in stripes if s["id"] == sid) for sid in ch["stripes"]]
        pts.sort(key=lambda z: -z["lower_end_display"][1])
        for a_, b_ in zip(pts[:-1], pts[1:]):
            p = np.array(a_["upper_end_display"])
            q = np.array(b_["lower_end_display"])
            for t in np.linspace(0, 1, 12)[::2]:
                u = p + (q - p) * t
                w = p + (q - p) * min(1, t + 1 / 11)
                cv2.line(out, tuple(np.round(u).astype(int)), tuple(np.round(w).astype(int)), (255, 0, 255), 2, cv2.LINE_AA)
    for b in branches:
        p = np.round(b["point_display"]).astype(int)
        cv2.drawMarker(out, tuple(p), (60, 255, 60), cv2.MARKER_CROSS, 14, 2)
    # ID の文字：帯の中心線の上端寄り（SL は下端寄り）に置く
    for s in stripes:
        cl = np.array(s["centerline_display"])
        f = 0.3 if s["id"].startswith("SL") else 0.75
        c = cl[int(f * (len(cl) - 1))]
        lab = s["id"] + ("*" if s["id"] in mainb else "")
        txt.append((c[0] + 7, c[1] - 9, lab, BANDCOL[s["id"][:2]]))
    for ms in main:
        p = np.array(ms["upper_end_display"])
        txt.append((p[0] + 8, p[1] - 26, "%s（%s）" % (ms["id"], "+".join(ms["bands"])), (255, 255, 255)))
    y = 60
    leg = [("塗り：SL＝下側から始まる帯（下端が下側から 50 px 以内）", BANDCOL["SL"]), ("　　　SU＝手の数え線 curl_upper に交わる帯", BANDCOL["SU"]),
           ("　　　SO＝そのほかの帯", BANDCOL["SO"]), ("白の太線：主要な縞（118、MS…、* 付きの帯）の左右の境界", (255, 255, 255)),
           ("白の線（下）：『下側』（主浪の外に接する外周）", (255, 255, 255)),
           ("○ 下端 / △ 上端の先にあるもの：", (255, 255, 255))] + [("　%s" % END_JA[k], ENDCOL[k]) for k in ["occluder", "foam", "dot", "ai_dark", "sky"]] + [
        ("紫の破線：手のつなぎ（白い点・泡で途切れた同じ帯。記録のみ）", (255, 0, 255)), ("緑の＋：藍の縞の分岐の候補（178、記録のみ）", (60, 255, 60)),
        ("下側の藍濃の縞（KL）は別図 28A_stripes_lower.png", (255, 255, 255))]
    for t, c in leg:
        txt.append((1250, y, t, c))
        y += 25
    out = _pil_text(out, txt, 17)
    T.save_png_reserved(path, out, [(255, 255, 255), (255, 0, 255), (60, 255, 60)] + list(BANDCOL.values()) + list(ENDCOL.values()))


def fig_stripes_lower(disp_rgb, band_disp, stripes, dark, lower, path, box=(170, 440, 960, 815), scale=2.0):
    """下側の拡大図（2 倍）：『下側』に沿った並び（藍中の帯・藍濃の縞 KL・泡）と、SL の帯の下端。"""
    x0, y0, x1, y1 = box
    crop = disp_rgb[y0:y1, x0:x1].astype(np.float32)
    bd = band_disp[y0:y1, x0:x1]
    crop = (crop * 0.6 + 255 * 0.1)
    for s in stripes:
        m = bd == s["id"]
        col = np.array(BANDCOL[s["id"][:2]], np.float32)
        crop[m] = crop[m] * 0.3 + col * 0.7
    big = cv2.resize(crop.clip(0, 255).astype(np.uint8), None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    canvas = np.zeros((1080, 1920, 3), np.uint8)
    oy = 60
    canvas[oy:oy + big.shape[0], :big.shape[1]] = big[:1080 - oy, :1920]

    def T_(p):
        p = np.asarray(p, np.float64)
        return np.stack([(p[..., 0] - x0 + 0.5) * scale - 0.5, (p[..., 1] - y0 + 0.5) * scale - 0.5 + oy], -1)
    txt = [(20, 16, "28A 下側の藍の縞（表示 px %s を 2 倍）：『下側』に沿った並び。藍濃の縞 KL は藍中の帯（SL）・泡に挟まれた区間" % (box,), (255, 255, 255))]
    run = np.array(lower["run_display"])
    _poly(canvas, T_(run), (255, 255, 255), 1)
    kc = {"ai_dark_stripe": (60, 255, 60), "ai_mid_band": (0, 235, 255), "foam": (200, 200, 200)}
    for k, rec in enumerate(lower["sequence"]):
        a_, b_ = rec["s_from_display_px"], rec["s_to_display_px"]
        sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(run, axis=0), axis=1))]
        m = (sd >= a_ - 0.5) & (sd <= b_ + 0.5)
        if m.sum() >= 2:
            _poly(canvas, T_(run[m]), kc[rec["kind"]], 5)
    for d in dark:
        a_, b_ = d["s_from_display_px"], d["s_to_display_px"]
        sd = np.r_[0, np.cumsum(np.linalg.norm(np.diff(run, axis=0), axis=1))]
        k = int(np.clip(np.searchsorted(sd, 0.5 * (a_ + b_)), 0, len(run) - 1))
        p = T_(run[k])
        if 0 <= p[0] < 1900 and oy <= p[1] < 1075:
            # 外向き（主浪の外の側）へずらして書く
            k0, k1 = max(0, k - 3), min(len(run) - 1, k + 3)
            t = run[k1] - run[k0]
            t = t / (np.linalg.norm(t) + 1e-9)
            nrm = np.array([t[1], -t[0]])
            q = p - nrm * 26
            cv2.line(canvas, tuple(np.round(p).astype(int)), tuple(np.round(q).astype(int)), (60, 255, 60), 1, cv2.LINE_AA)
            txt.append((q[0] - 14, q[1] - 10, d["id"], (60, 255, 60)))
    for s in stripes:
        if not s["id"].startswith("SL"):
            continue
        p = T_(s["lower_end_display"])
        cv2.circle(canvas, tuple(np.round(p).astype(int)), 8, ENDCOL[s["lower_end_kind"]], 2, cv2.LINE_AA)
        cl = np.array(s["centerline_display"])
        c = T_(cl[min(len(cl) - 1, int(0.15 * (len(cl) - 1)) + 4)])
        if 0 <= c[0] < 1880 and oy <= c[1] < 1075:
            txt.append((c[0] + 10, c[1] - 12, s["id"], BANDCOL["SL"]))
    y = 830
    leg = [("太線（下側に沿った並び）：緑＝藍濃の縞（KL）、水色＝藍中の帯、灰＝泡（白・淡い水色）", (255, 255, 255)),
           ("○ SL の帯の下端（色は先にあるもの：赤＝遮蔽、緑＝藍濃の中で終わる、橙＝白い点、黄＝泡）", (255, 255, 255)),
           ("帯状の範囲＝主浪の外から表示 3〜12 px の水を下側の点へ振り分け、表示 1 px おきに多数決（藍の胴の中の白い点は藍濃に数える）", (255, 255, 255))]
    for t, c in leg:
        txt.append((20, y, t, c))
        y += 25
    canvas = _pil_text(canvas, txt, 17)
    T.save_png_reserved(path, canvas, [(255, 255, 255), (60, 255, 60), (200, 200, 200)] + list(BANDCOL.values()) + list(ENDCOL.values()))


def fig_white_band(disp_rgb, w1_disp, feats, band, path):
    """79／133／134：主浪の白（W001）と、その内側の境界の区分、134 の白い帯の幅（法線の線分）と広狭。"""
    out = (disp_rgb.astype(np.float32) * 0.45 + 255 * 0.08).clip(0, 255).astype(np.uint8)
    out[w1_disp] = (out[w1_disp] * 0.35 + np.array([255, 250, 225]) * 0.65).astype(np.uint8)
    col = {79: (255, 140, 0), 133: (255, 225, 0), 134: (0, 255, 120)}
    stopcol = {"ai_dark": (80, 140, 255), "ai_mid": (0, 220, 255), "envelope_sky": (255, 120, 200), "max": (200, 200, 200),
               "outside": (200, 200, 200), "frame": (200, 200, 200)}
    for k, p in enumerate(band["profile"]):
        if k % 4:
            continue
        a = np.array(p["p"])
        n = np.array(p["n"])
        b = a + n * p["width"]
        cv2.line(out, tuple(np.round(a).astype(int)), tuple(np.round(b).astype(int)), stopcol.get(p["stop"], (200, 200, 200)), 1, cv2.LINE_AA)
    for f in feats:
        if f["neighbour"] in (SKY, OUTSIDE) or f["item_zone"] not in col:
            continue
        _poly(out, f["points"], col[f["item_zone"]], 2)
    txt = [(20, 20, "28A 白（79／133／134）：主浪の白（W001、薄い生成りの塗り）と内側の境界、134 の白い帯の幅", (255, 255, 255))]
    for e in band["wide_narrow_order_from_crest"]:
        p = np.round(e["at_display"]).astype(int)
        c = (0, 255, 120) if e["kind"] == "wide" else (255, 80, 80)
        cv2.circle(out, tuple(p), 7, c, 2, cv2.LINE_AA)
        txt.append((p[0] + 10, p[1] - 20, "%s %.0f px" % ("広" if e["kind"] == "wide" else "狭", e["width"]), c))
    leg = [("太線：W001 の内側（空・主浪の外でない側）の境界", (255, 255, 255)), ("　79 左側の白", col[79]), ("　133 上側の白", col[133]),
           ("　134 船側へ曲がる白い帯", col[134]),
           ("細線：134 の帯の幅（外輪郭 132 から内向き、8 表示 px おき）。止まった所：", (255, 255, 255)),
           ("　藍濃の胴", stopcol["ai_dark"]), ("　藍中の帯", stopcol["ai_mid"]), ("　包絡の外（唇の下の空）", stopcol["envelope_sky"]),
           ("○ 134 の帯の広い所（緑）・狭い所（赤）。数字は 31 点移動平均の幅", (255, 255, 255))]
    y = 60
    for t, c in leg:
        txt.append((1250, y, t, c))
        y += 25
    out = _pil_text(out, txt, 17)
    T.save_png_reserved(path, out, [(255, 255, 255), (255, 80, 80)] + list(col.values()) + list(stopcol.values()))


def fig_white_inner(disp_rgb, band_disp_mask, r175_disp, white_range_disp, inner_disp, b270, b120, path):
    """175：白い範囲の中の色区（淡い水色・藍中・藍濃）を塗り分け。73/263/265：内側の藍中の帯。120／270：境界。"""
    out = (disp_rgb.astype(np.float32) * 0.45 + 255 * 0.08).clip(0, 255).astype(np.uint8)
    edge = cv2.morphologyEx(white_range_disp.astype(np.uint8), cv2.MORPH_GRADIENT, disk(1)) > 0
    fill = {"mizuiro": (120, 235, 190), "ai_mid": (40, 150, 255), "ai_dark": (30, 50, 150)}
    for n, m in r175_disp.items():
        out[m] = fill[n]
    out[inner_disp] = (0, 230, 255)
    out[edge] = (255, 255, 255)
    for seg in b270["mizuiro"]:
        _poly(out, seg, (255, 150, 200), 1)
    for seg in b270["ai_mid"]:
        _poly(out, seg, (255, 50, 50), 2)
    for seg in b120:
        _poly(out, seg, (255, 255, 0), 3)
    txt = [(20, 20, "28A 白の中の色区（175）、内側の藍中の帯（73／263／265）、境界 120・270", (255, 255, 255))]
    leg = [("白の細線：白い範囲（W001 とそれに連なる泡の外形）", (255, 255, 255)),
           ("塗り：白い範囲の中の色区（175 で全部残す対象）", (255, 255, 255)), ("　淡い水色（調色板 mizuiro）", fill["mizuiro"]),
           ("　藍中", fill["ai_mid"]), ("　藍濃", fill["ai_dark"]), ("水色の塗り：内側の藍中の帯（73／263／265）", (0, 230, 255)),
           ("黄の太線：120 唇の泡（上）と内側の藍中の帯（下）の境", (255, 255, 0)), ("赤の線：270 既定＝白と藍中の境", (255, 50, 50)),
           ("桃の細線：270 別案＝白と淡い水色の境（唇の区域）", (255, 150, 200))]
    y = 60
    for t, c in leg:
        txt.append((1250, y, t, c))
        y += 25
    out = _pil_text(out, txt, 17)
    T.save_png_reserved(path, out, [(255, 255, 255), (255, 150, 200), (255, 50, 50), (255, 255, 0), (0, 230, 255)] + list(fill.values()))


def fig_evidence(disp_rgb, ev, zones, med_disp, decision_lines, path):
    out = (disp_rgb.astype(np.float32) * 0.8).astype(np.uint8)
    cols = [(255, 60, 60), (60, 200, 255), (255, 220, 0), (255, 0, 255)]
    txt = [(20, 20, "28A バックログの「水色」はどの色か：区域ごとの色の面積と Lab の中央値（表示フレーム、3 px 収縮）", (255, 255, 255))]
    y = 60
    for k, (zn, z) in enumerate(zones.items()):
        c = cols[k % len(cols)]
        _poly(out, z["points"], c, 2, True)
        p = np.array(z["points"][0])
        txt.append((p[0] + 4, p[1] - 22, zn, c))
        e = ev[zn]
        s = "%s（項目 %s）：藍より明るく白でない面積のうち 藍中 %.0f%%・淡い水色 %.0f%%" % (
            zn, "/".join(str(i) for i in e["items"]), 100 * e["lighter_than_ai_non_white"]["ai_mid_share"],
            100 * e["lighter_than_ai_non_white"]["mizuiro_share"])
        txt.append((20, 800 + 26 * k, s, c))
    y = 800 + 26 * len(zones) + 10
    y_end = y + 26 * len(decision_lines)
    sh = out[790:y_end + 6, 10:1560].astype(np.float32)
    out[790:y_end + 6, 10:1560] = (sh * 0.3).astype(np.uint8)
    for t in decision_lines:
        txt.append((20, y, t, (255, 255, 255)))
        y += 26
    # 区域ごとの色の標本（藍中・淡い水色の中央値。3 px 収縮）
    for k, (zn, z) in enumerate(zones.items()):
        xx = 1000
        for n in ("ai_mid", "mizuiro"):
            r_ = ev[zn]["lab_median_eroded"].get(n)
            if not r_:
                continue
            rgb, _ = T.lab_to_srgb8_best(np.array(r_["lab"]))
            yy0 = 800 + 26 * k + 2
            cv2.rectangle(out, (xx, yy0), (xx + 26, yy0 + 18), tuple(int(v) for v in rgb), -1)
            cv2.rectangle(out, (xx, yy0), (xx + 26, yy0 + 18), (255, 255, 255), 1)
            txt.append((xx + 32, yy0 - 2, "%s L*%.0f b*%.0f（n=%d）" % ("藍中" if n == "ai_mid" else "淡い水色", r_["lab"][0], r_["lab"][2], r_["n"]), (255, 255, 255)))
            xx += 270
    # 色見本
    x = 1330
    yy = 60
    for n in ["white", "mizuiro", "ai_mid", "ai_dark"]:
        m = med_disp.get(n)
        if not m:
            continue
        rgb, _ = T.lab_to_srgb8_best(np.array(m["lab_median"]))
        cv2.rectangle(out, (x, yy), (x + 60, yy + 40), tuple(int(v) for v in rgb), -1)
        cv2.rectangle(out, (x, yy), (x + 60, yy + 40), (255, 255, 255), 1)
        txt.append((x + 70, yy + 8, "%s  L*a*b* = %.1f, %.1f, %.1f" % (n, *m["lab_median"]), (255, 255, 255)))
        yy += 50
    out = _pil_text(out, txt, 18)
    T.save_png_reserved(path, out, [(255, 255, 255)] + cols)


def fig_closeup(disp_rgb_hi_crop, label_crop, path, title, scale=3):
    a = cv2.resize(disp_rgb_hi_crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    b = np.zeros(label_crop.shape + (3,), np.uint8)
    for k, c in VIS.items():
        b[label_crop == k] = c
    b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_NEAREST)
    out = np.concatenate([a, b], 1)
    H0 = 1080
    W0 = 1920
    canvas = np.zeros((H0, W0, 3), np.uint8)
    f = min(W0 / out.shape[1], (H0 - 40) / out.shape[0])
    o2 = cv2.resize(out, None, fx=f, fy=f, interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_NEAREST)
    canvas[40:40 + o2.shape[0], :o2.shape[1]] = o2
    canvas = _pil_text(canvas, [(10, 8, title, (255, 255, 255))], 20)
    T.save_png_reserved(path, canvas, [(255, 255, 255)] + [VIS[k] for k in VIS])


# ================================================================= 主処理
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default="Docs/Evidence/ArtFirst/28")
    ap.add_argument("--build", default="Unity/Build/ArtFirst/28/partA")
    ap.add_argument("--reuse-stage-a", action="store_true", help="build の第1〜2段の中間物を再利用する（開発用。証拠の生成には使わない）")
    a = ap.parse_args()
    t0 = time.time()
    build = os.path.join(REPO, a.build)
    evid = os.path.join(REPO, a.evidence)
    outdir = os.path.join(REPO, OUT_DIR_REL)
    for d in (build, evid, os.path.join(outdir, "masks")):
        os.makedirs(d, exist_ok=True)
    inputs = {k: os.path.join(REPO, k) for k in [REF_REL, SKY_REL, SKY_ENV_REL, ENV_REL, CLAWS_REL, PALETTE23_REL, ANN_REL, MANIFEST_REL, SPEC_REL,
                                                  "Tools/PaintingTruth/truthlib.py", "Tools/PaintingTruth/colour/colour_truth.py"]}
    in_sha = {k: sha256(v) for k, v in inputs.items()}
    if in_sha[REF_REL] != REF_SHA:
        raise SystemExit("原画の SHA-256 が違う: " + in_sha[REF_REL])
    ann = json.load(open(inputs[ANN_REL], encoding="utf-8"))
    spec = json.load(open(inputs[SPEC_REL], encoding="utf-8"))
    manifest = json.load(open(inputs[MANIFEST_REL], encoding="utf-8"))
    pal23_doc = json.load(open(inputs[PALETTE23_REL], encoding="utf-8"))
    pal23 = pal23_doc["palette"]
    rgb = cv2.imread(inputs[REF_REL], cv2.IMREAD_COLOR)[..., ::-1].copy()
    H, W = rgb.shape[:2]
    fr = Frame(W, H)
    log = {}
    cache = os.path.join(build, "stage_a.npz")
    if a.reuse_stage_a and os.path.exists(cache):
        z = np.load(cache, allow_pickle=True)
        mw_region, mw_layer, comp_id = z["mw_region"], z["mw_layer"], z["comp_id"]
        regs = list(z["regs"])
        log = z["log"].item()
        C = z["C"]
        cnames = list(z["cnames"])
        print("第1〜2段の中間物を再利用した（開発用）")
    else:
        lab = T.srgb8_to_lab(rgb).astype(np.float32)
        skycov = cv2.imread(inputs[SKY_REL], cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
        sky = fr.disp_to_hi_map(skycov) >= 0.5
        raw, labs, C, cnames = classify(lab, sky, pal23, log)
        del lab, labs
        region, layer = clean(raw, sky, log)
        del raw
        mw_region, mw_layer, mem, left_zone = assign_main_wave(region, layer, fr, ann, log)
        del region, layer
        regs, comp_id = vectorise_regions(mw_region, fr, log)
        np.savez(cache, mw_region=mw_region, mw_layer=mw_layer, comp_id=comp_id, regs=np.array(regs, dtype=object),
                 log=np.array(log, dtype=object), C=C, cnames=np.array(cnames))
    print("第1〜2段", round(time.time() - t0, 1), "s")
    # ---- 表示フレームの被覆率とラベル
    covs = {}
    for n in COLOUR_CLASSES:
        covs[n] = fr.hi_to_disp_cov(mw_region == CLS[n])
    covs["line"] = fr.hi_to_disp_cov(mw_layer == CLS["line"])
    cov_sky = fr.hi_to_disp_cov(mw_region == SKY)
    cov_out = fr.hi_to_disp_cov(mw_region == OUTSIDE)
    stack = np.stack([cov_out, covs["white"], covs["mizuiro"], covs["ai_mid"], covs["ai_dark"], cov_sky], -1)
    vals = np.array([OUTSIDE, CLS["white"], CLS["mizuiro"], CLS["ai_mid"], CLS["ai_dark"], SKY], np.uint8)
    disp_label = vals[stack.argmax(-1)]
    disp_layer = disp_label.copy()
    disp_layer[(covs["line"] >= 0.5) & (disp_label != SKY) & (disp_label != OUTSIDE)] = CLS["line"]
    mask_paths = {}
    for n in COLOUR_CLASSES + ["line"]:
        pth = os.path.join(outdir, "masks", "mw_%s_cov.png" % n)
        T.save_cov_png(pth, covs[n])
        mask_paths[n] = rel(pth)
    pth = os.path.join(outdir, "masks", "mw_colour_labels.png")
    cv2.imwrite(pth, disp_layer)
    mask_paths["labels_display"] = rel(pth)
    pth = os.path.join(outdir, "masks", "mw_colour_labels_hi.png")
    cv2.imwrite(pth, mw_layer, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    mask_paths["labels_hi"] = rel(pth)
    # ---- 表示フレームの原画と Lab、色の中央値（番号23 の規則：表示フレームで 3 px 収縮した内側の中央値）
    disp_rgb = fr.disp_image(rgb)
    disp_lab = T.srgb8_to_lab(disp_rgb)
    med_disp = display_medians(disp_lab, {n: covs[n] for n in COLOUR_CLASSES})
    centers = {n: C[k] for k, n in enumerate(cnames)}
    pal_cmp = {}
    for n, p23 in [("white", "white"), ("mizuiro", "mizuiro"), ("ai_mid", "ai_mid"), ("ai_dark", "ai_dark")]:
        if med_disp[n]:
            pal_cmp[n] = {"lab_median_display": med_disp[n]["lab_median"], "palette23_name": p23, "palette23_lab": pal23[p23]["lab"],
                          "dE00_to_palette23": round(float(T.ciede2000(np.array(med_disp[n]["lab_median"]), np.array(pal23[p23]["lab"]))), 3),
                          "srgb8": [int(v) for v in T.lab_to_srgb8_best(np.array(med_disp[n]["lab_median"]))[0]]}
    # ---- 縞
    stripes, dark, chains, branches, order_cand, lower, main_stripes = stripe_inventory(mw_region, mw_layer, regs, comp_id, fr, ann, log)
    print("縞", round(time.time() - t0, 1), "s")
    # ---- 白い帯など
    outl, outl_doc = load_outline(inputs[ENV_REL])
    envcov = cv2.imread(inputs[SKY_ENV_REL], cv2.IMREAD_UNCHANGED).astype(np.float32) / 65535.0
    env_sky = fr.disp_to_hi_map(envcov) >= 0.5
    w1, white_range, wfeats, band, r175, w1_id = white_analysis(mw_region, mw_layer, regs, comp_id, fr, ann, outl, env_sky, log)
    print("白", round(time.time() - t0, 1), "s")
    reg_by_id = {r["id"]: r for r in regs}
    lab_of = {r["id"]: i + 1 for i, r in enumerate(regs)}
    # 73/263/265：内側の帯（手のつなぎ inner_face の帯）
    inner_ids = [next(s["region"] for s in stripes if s["id"] == sid) for sid in chains.get("inner_face", {}).get("stripes", [])]
    inner_segs = []
    inner_nb = {}
    for rid in inner_ids:
        for sg in region_boundary_by_neighbour(reg_by_id[rid], comp_id, regs, mw_layer, fr):
            nm = {SKY: "sky", OUTSIDE: "outside", CLS["white"]: "white", CLS["mizuiro"]: "mizuiro", CLS["ai_dark"]: "ai_dark",
                  CLS["line"]: "line", CLS["ai_mid"]: "ai_mid"}.get(sg["neighbour"], str(sg["neighbour"]))
            inner_segs.append({"region": rid, "neighbour": nm, "points": sg["points"], "hole": bool(reg_by_id[rid]["rings"][sg["ring"]]["hole"])})
            inner_nb[nm] = round(inner_nb.get(nm, 0.0) + polyline_len(sg["points"]), 1)
    inner_mask = np.isin(comp_id, [lab_of[r] for r in inner_ids])
    inner_cov = fr.hi_to_disp_cov(inner_mask)
    im_ = cv2.erode((inner_cov >= 0.5).astype(np.uint8), disk(P["colour_erode_disp_px"])) > 0
    inner_lab = np.median(disp_lab[im_], 0) if im_.sum() > 10 else None
    inner_rec = None
    if inner_lab is not None:
        inner_rec = {"regions": inner_ids, "stripes": chains.get("inner_face", {}).get("stripes", []),
                     "lab_median_eroded_3px": r3(inner_lab), "n_display_px": int(im_.sum()),
                     "dE00_to_ai_mid_median": round(float(T.ciede2000(inner_lab, np.array(med_disp["ai_mid"]["lab_median"]))), 3),
                     "dE00_to_mizuiro_median": round(float(T.ciede2000(inner_lab, np.array(med_disp["mizuiro"]["lab_median"]))), 3),
                     "dE00_to_palette23_ai_mid": round(float(T.ciede2000(inner_lab, np.array(pal23["ai_mid"]["lab"]))), 3),
                     "dE00_to_palette23_mizuiro": round(float(T.ciede2000(inner_lab, np.array(pal23["mizuiro"]["lab"]))), 3),
                     "lab_p10_p90": [r3(np.percentile(disp_lab[im_], 10, 0)), r3(np.percentile(disp_lab[im_], 90, 0))],
                     "boundary_length_by_neighbour_display_px": inner_nb}
        low = max((next(s for s in stripes if s["region"] == r) for r in inner_ids), key=lambda s: s["lower_end_display"][1])
        inner_rec["lower_end_display"] = low["lower_end_display"]
        inner_rec["lower_end_kind"] = low["lower_end_kind"]
        inner_rec["upper_end_display"] = min((next(s for s in stripes if s["region"] == r) for r in inner_ids),
                                             key=lambda s: s["upper_end_display"][1])["upper_end_display"]
        # 263（記録のみ）：内側の帯の下端の先（主浪の外、前景の小波の右の海）の色
        p = np.array(inner_rec["lower_end_display"])
        box = disp_label[int(p[1]) - 5:int(p[1]) + 45, int(p[0]):int(p[0]) + 70]
        boxl = disp_lab[int(p[1]) - 5:int(p[1]) + 45, int(p[0]):int(p[0]) + 70]
        blu = (boxl[..., 2] < -12) & (boxl[..., 0] < 60)
        inner_rec["below_lower_end_record"] = {"box_display": [int(p[0]), int(p[1]) - 5, int(p[0]) + 70, int(p[1]) + 45],
                                               "blue_px_fraction": round(float(blu.mean()), 3),
                                               "blue_lab_median": r3(np.median(boxl[blu], 0)) if blu.sum() > 5 else None,
                                               "note_ja": "内側の帯の下端から右下の 70×50 表示 px（前景の小波の右の海）で、b* < −12 かつ L* < 60 の藍の画素の割合と中央値。263 の『下方の水面』へ色が続くかの記録。主浪の外なので色区の地図には入れていない。"}
    # 120：唇の泡（上）と内側の藍中の帯（下）の境
    z134 = np.zeros((1080, 1920), np.uint8)
    cv2.fillPoly(z134, [np.round(np.array(ann["white_item_zones_display"]["134"]["points"]) * 8).astype(np.int32)], 1, shift=3)

    def in134(pts):
        q = np.clip(np.round(np.asarray(pts)).astype(int), 0, [1919, 1079])
        return float(z134[q[:, 1], q[:, 0]].mean()) >= 0.5
    b120 = [s["points"] for s in inner_segs if s["neighbour"] in ("white", "mizuiro", "line") and not s["hole"] and in134(s["points"])]
    # 270：白と藍中の境（既定）、白と淡い水色の境（別案）。W001 の輪郭を隣の色で分ける
    w1reg = reg_by_id[w1_id]
    w1segs = region_boundary_by_neighbour(w1reg, comp_id, regs, mw_layer, fr)
    b270 = {"ai_mid": [], "mizuiro": []}
    lipzone = np.zeros((1080, 1920), np.uint8)
    cv2.fillPoly(lipzone, [np.round(np.array(ann["mizuiro_evidence_zones_display"]["white_band_lip_120_270"]["points"]) * 8).astype(np.int32)], 1, shift=3)
    for sg in w1segs:
        if sg["neighbour"] == CLS["ai_mid"]:
            b270["ai_mid"].append(sg["points"])
        elif sg["neighbour"] == CLS["mizuiro"]:
            c = np.mean(sg["points"], 0).astype(int)
            if lipzone[min(1079, max(0, c[1])), min(1919, max(0, c[0]))]:
                b270["mizuiro"].append(sg["points"])
    alt = {}
    for k, segs in b270.items():
        L = sum(polyline_len(s) for s in segs)
        al = [turning_alternation(s) for s in segs if polyline_len(s) >= 20]
        al = [v for v in al if v is not None]
        alt[k] = {"n_segments": len(segs), "length_display_px": round(L, 1), "n_segments_ge20px": len(al),
                  "turn_sign_changes_per_100px_median": round(float(np.median(al)), 2) if al else None}
    print("境界", round(time.time() - t0, 1), "s")
    # ---- 水色の根拠（区域ごと）
    ev = zone_evidence(disp_lab, disp_layer, fr, ann["mizuiro_evidence_zones_display"], covs,
                       {n: np.array(med_disp[n]["lab_median"]) for n in ["mizuiro", "ai_mid"]})
    dm = T.ciede2000(np.array(med_disp["mizuiro"]["lab_median"]), np.array(med_disp["ai_mid"]["lab_median"]))
    decision = {
        "decision": "ai_mid",
        "status_ja": "既定値・利用者未回答（CP1 で利用者に確かめる）",
        "summary_ja": "バックログの「水色」は、番号23の調色板の ai_mid（藍中）に当てる。調色板の mizuiro（淡い青緑）はバックログに名前がなく、泡の中の淡い斑として別の色区のまま残す（175 の対象）。",
        "reasons_ja": [
            "77・269：『水色を挟んで並ぶ藍の縞』『隣り合う藍の縞の間に水色の帯』。胴の下側の区域 between_stripes_77_269 では、藍より明るく白でない面積の %.0f%% が藍中で、藍濃の縞の間にあるのは藍中の帯だけだった（淡い水色は泡の斑で、縞の間には無い）。" % (100 * ev["between_stripes_77_269"]["lighter_than_ai_non_white"]["ai_mid_share"]),
            "73・263・265：唇の下の内側の区域 inner_face_73_263_265 では、藍より明るく白でない面積の %.0f%% が藍中だった。内側の帯（%s）は唇の下から前景の小波の縁まで続く一続きの面で、265 の『藍より明るい水色の色面』に当たる。" % (100 * ev["inner_face_73_263_265"]["lighter_than_ai_non_white"]["ai_mid_share"], "・".join(chains.get("inner_face", {}).get("stripes", []))),
            "120：唇（船側へ曲がる水面）では、上側が泡の白、下側が内側の藍中の帯で、二つの色区の境がはっきりしている（境の長さ %.0f 表示 px）。淡い水色は泡の中に散る斑で、『下側の色の範囲』を作らない。" % sum(polyline_len(s) for s in b120),
            "265 の言い回し『藍より明るい水色』：藍中（L* %.1f）は藍濃（L* %.1f）より明るい。淡い水色（L* %.1f）は白（L* %.1f）に近く、藍との比較で言い分ける必要が薄い。" % (med_disp["ai_mid"]["lab_median"][0], med_disp["ai_dark"]["lab_median"][0], med_disp["mizuiro"]["lab_median"][0], med_disp["white"]["lab_median"][0]),
        ],
        "open_ja": [
            "175・270 は白の中・白との境を述べる項目で、泡の区域（white_band_lip_120_270、foam_left_175）では藍より明るく白でない面積の %.0f%%・%.0f%% が淡い水色だった。『水色』を藍中に当てると、270 の対象は白と藍中の境（唇の付け根と胴の上縁の爪の縁）になる。淡い水色に当てる読み方もできるので、両方の境界を出し、既定は藍中とした。" % (100 * ev["white_band_lip_120_270"]["lighter_than_ai_non_white"]["mizuiro_share"], 100 * ev["foam_left_175"]["lighter_than_ai_non_white"]["mizuiro_share"]),
            "175 は白い範囲の中の藍・水色の色区を『全て残す』項目なので、どちらに当てても、淡い水色・藍中・藍濃の全部を残す対象にした。",
            "番号23の調色板は mizuiro の日本語名を『水色』としている。バックログとの対応を誤らないよう、名前の付け替え（例：mizuiro →『淡い水色』、ai_mid →『藍中（バックログの水色）』）を進行役が判断する。このファイルは調色板を変えない。",
        ],
        "dE00_mizuiro_vs_ai_mid_medians": round(float(dm), 2),
    }
    # 項目ごとの当てはめ（バックログの要求文が指す場所の色を、区域の面積と Lab 中央値で確かめた結果）
    wr_ = r175["non_white_regions"]
    am_ = wr_.get("mizuiro", {}).get("area_display_px2", 0.0)
    aa_ = wr_.get("ai_mid", {}).get("area_display_px2", 0.0)
    ad_ = wr_.get("ai_dark", {}).get("area_display_px2", 0.0)

    def zrow(zn):
        e = ev[zn]
        return {"zone": zn, "light_non_white_share": e["lighter_than_ai_non_white"], "lab_median_eroded_by_class": e["lab_median_eroded"]}
    inner_ids_ = chains.get("inner_face", {}).get("stripes", [])
    per_item = [
        {"item": 73, "text_ja": "船側へ曲がる波の内側に、水色の面", "where_ja": "唇の下の内側の帯（%s）" % "・".join(inner_ids_), **zrow("inner_face_73_263_265"), "maps_to": "ai_mid"},
        {"item": 77, "text_ja": "波の下側に、水色を挟んで並ぶ藍の縞", "where_ja": "胴の下側の藍濃の縞の間", **zrow("between_stripes_77_269"), "maps_to": "ai_mid"},
        {"item": 118, "text_ja": "藍の縞が、波の下側から上側へ曲がって続く", "where_ja": "縞の両側（藍中の帯の左右の境界）", **zrow("between_stripes_77_269"), "maps_to": "ai_mid"},
        {"item": 120, "text_ja": "上側の白と下側の水色を別々の色の範囲として", "where_ja": "唇の下側＝内側の帯の上端（唇の泡との境）", **zrow("inner_face_73_263_265"), "maps_to": "ai_mid"},
        {"item": 175, "text_ja": "波の白い範囲の中に、藍と水色の部分", "where_ja": "白い範囲（W001 とそれに連なる泡）の中",
         "white_range_area_display_px2": {"mizuiro": am_, "ai_mid": aa_, "ai_dark": ad_},
         "mizuiro_share_of_light_non_white": round(am_ / max(am_ + aa_, 1e-9), 3), **zrow("foam_left_175"),
         "maps_to": "mizuiro（主）と ai_mid（従）。175 は全部残す項目なので、両方と藍濃を残す対象にする（当てはめで対象は変わらない）"},
        {"item": 263, "text_ja": "波の内側から下方の水面まで、水色の面が続いて", "where_ja": "内側の帯の下端まで", **zrow("inner_face_73_263_265"), "maps_to": "ai_mid"},
        {"item": 265, "text_ja": "本編の波の内側に、藍より明るい水色の色面", "where_ja": "内側の帯",
         "target_lab_median_eroded_3px": inner_rec["lab_median_eroded_3px"] if inner_rec else None,
         "dE00_to_ai_mid_median": inner_rec["dE00_to_ai_mid_median"] if inner_rec else None,
         "dE00_to_mizuiro_median": inner_rec["dE00_to_mizuiro_median"] if inner_rec else None, "maps_to": "ai_mid"},
        {"item": 269, "text_ja": "隣り合う藍の縞の間に、水色の帯", "where_ja": "胴の藍濃の縞の間", **zrow("between_stripes_77_269"), "maps_to": "ai_mid"},
        {"item": 270, "text_ja": "波の白と水色の境に、白側と水色側へ交互に曲がる境界", "where_ja": "唇（白い帯とその内側）",
         "white_boundary_length_display_px": {"white|ai_mid（主浪全体）": alt["ai_mid"]["length_display_px"], "white|mizuiro（唇の区域）": alt["mizuiro"]["length_display_px"]},
         **zrow("white_band_lip_120_270"), "maps_to": "ai_mid（既定）。mizuiro の読み方も残し、両方の境界を出す"},
        {"item": 266, "text_ja": "水色の面が元の塗り分けを保って", "where_ja": "—", "maps_to": "当てはめに依らない（全色区を中央値で平塗り）"},
    ]
    decision["per_item"] = per_item
    decision["per_item_summary_ja"] = "73・77・118・120・263・265・269 → 藍中（ai_mid）。175（と形成中の 176）→ 白い範囲の中の明るい色は淡い水色（mizuiro）が主で、藍中も残す。270 → 既定は藍中、淡い水色の読み方も記録。266 → 当てはめに依らない。"
    # ---- 出力 JSON
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    item_targets = {
        "73": {"target": "inner_face の帯（藍中）の輪郭", "stripes": chains.get("inner_face", {}).get("stripes", []), "judge_part": "B"},
        "77": {"target": "『下側』に沿った藍濃の縞（KL…）と藍中の帯（SL…）の本数・並び順（stripes.lower_side.sequence）と、SL の帯の下端（lower_end_display）", "judge_part": "B"},
        "79": {"target": "W001 の左側（外輪郭 78/130 に最も近い部分）の内側の境界。空の側は番号23の 78/130", "judge_part": "B"},
        "118": {"target": "主要な藍の縞の両側の境界（藍中の帯の左右の境界）。上下の対応は手のつなぎ（chains）", "judge_part": "B"},
        "120": {"target": "唇の泡と内側の藍中の帯の境（boundary_120）", "judge_part": "B"},
        "133": {"target": "W001 が左側から上側まで一続き（連結）であること、上側（外輪郭 131 に最も近い部分）の内側の境界", "judge_part": "B"},
        "134": {"target": "白い帯（外輪郭 132 から内向きの泡）の内側の境界と、幅の広狭の順", "judge_part": "B"},
        "175": {"target": "白い範囲の中の白以外の色区（regions_175）が全部残ること、その境界", "judge_part": "B"},
        "263": {"target": "inner_face の帯が下側（前景の小波の縁）まで続く範囲。下端の先の海の色は記録のみ", "judge_part": "B"},
        "265": {"target": "inner_face の帯の Lab 中央値（3 px 収縮）を目標色にする（ΔE00 ≤5）", "lab": inner_rec["lab_median_eroded_3px"] if inner_rec else None, "judge_part": "B"},
        "270": {"target": "既定：W001 と藍中の境（boundary_270_ai_mid）。別案：W001 と淡い水色の境（boundary_270_mizuiro、唇の区域）", "judge_part": "B"},
        "178": {"target": "藍の縞の分岐の候補（branches）。記録のみ。計画の損切りどおり、分割が安定しなければ延期", "judge_part": "記録のみ"},
        "266/267": {"target": "色区ごとの色の中央値（palette_display_median）を平塗りにする（照明の帯・灰色の帯 0）", "judge_part": "B"},
    }
    truth = {
        "schema": "GreatWave.PaintingTruth.colour/1", "number": "28", "part": "A", "version": "v0",
        "status_ja": "主浪の色区の正解 v0（番号28 第A部）。原画から半自動で作り、手で決めたのは区域の振り分け・数え線・同じ帯のつなぎだけ。どの項目も合格にしていない（判定は第B部の投影ベイクの後）。",
        "reference": {"path": REF_REL, "sha256": in_sha[REF_REL], "width": W, "height": H},
        "frame": {"width": 1920, "height": 1080, "scale": fr.s, "offset_x": fr.ox,
                  "hi_to_display_ja": "x_d = s·(x_h+0.5) − 0.5 + ox、y_d = s·(y_h+0.5) − 0.5（番号23 painting_truth.json v0.2 の display_frame と同じ）"},
        "truth23": {"painting_truth_version": spec.get("version"), "painting_truth_sha256": in_sha[SPEC_REL],
                    "truth_manifest_sha256": in_sha[MANIFEST_REL], "sky_mask": SKY_REL, "sky_mask_sha256": in_sha[SKY_REL],
                    "outline_envelope_sha256": in_sha[ENV_REL],
                    "note_ja": "番号23の真値（空・外輪郭）が変わったら、このファイルを作り直す（同じコマンド 1 回）。"},
        "classes": {n: {"value": CLS[n], "name_ja": CLS_JA[n]} for n in CLS},
        "label_values_ja": "masks/mw_colour_labels.png（表示）と mw_colour_labels_hi.png（hi px）の値：0＝主浪の外、1＝白、2＝淡い水色、3＝藍中、4＝藍濃、5＝藍の線（色面の地図 mw_*_cov.png では線を両側の色へ吸収済み）、9＝空（番号23）。",
        "params": P, "params_ja": P_JA,
        "centers_hi": {n: r3(centers[n]) for n in cnames},
        "palette_display_median": med_disp,
        "palette_compare_23": pal_cmp,
        "mizuiro_mapping": decision,
        "mizuiro_evidence": ev,
        "stripes": {"definition_ja": "藍中の帯（S…）＝胴の中の細長い藍中の連結成分（面積 ≥ %d hi px²、長さ／平均幅 ≥ %.1f）。ID は数え線に交わる順（SL＝下側の数え線 lower_side に左から、SU＝手の数え線 curl_upper に左から、どちらにも交わらないものは SO で面積の大きい順）。藍濃の縞（K…）＝数え線の上で続く2本の藍中の帯（または胴の縁）の間の藍濃。下端＝中心線の端のうち原画で下にある方。" % (P["stripe_min_hi_px2"], P["stripe_min_elong"]),
                    "ai_mid_bands": stripes, "dark_stripes_lower_side": dark, "lower_side": lower,
                    "main_stripes_118": main_stripes, "chains": chains,
                    "order_candidates_upper_lower": order_cand, "branches_178": branches,
                    "end_kind_ja": END_JA,
                    "limits_ja": "藍中の帯の細い先（幅が約 2 表示 px 未満）は、混色の縁を除く開き（半径 2 hi px）で消えるので、下端・上端は実際の先より少し手前になる場合がある。白い点で切れた帯は別の成分になる（手のつなぎで1本とみなす）。"},
        "white": {"main_white_region": w1_id, "band_134": band, "regions_175": r175,
                  "boundary_parts_ja": "W001 の輪郭を、隣の色と、最も近い番号23の外輪郭の区間（78/130→79、131→133、132→134、72→内側）で分けた（colour_polylines.json の white_parts）。"},
        "inner_face": inner_rec,
        "boundary_270": alt,
        "item_targets": item_targets,
        "for_part_b_ja": [
            "色区の地図：masks/mw_colour_labels_hi.png（高解像度原画の画素、値は label_values_ja）を正とし、表示フレームの判定には masks/mw_*_cov.png（uint16 の被覆率、0.5 で2値化）を使う。境界の SDF はこの地図から作るのがよい（折れ線は同じ地図の輪郭を間引いたもの）。",
            "境界の折れ線：colour_polylines.json の regions（色区の連結成分ごとの外周と穴、ID は W/M/A/D＋番号）と features（項目ごとの区間、kind と items で選ぶ）。座標は表示 px。",
            "藍の線（label 5）は色区の地図では両側の色へ吸収してある。外殻線・色の境界線は番号36（計画 4.2）で扱う。",
            "主浪の範囲の外（前景の小波・左奥船・右の海）は label 0。空は label 9（番号23の爪入り版）。",
            "目標色は palette_display_median（表示フレーム、3 px 収縮の中央値）。265 は inner_face.lab_median_eroded_3px。",
        ],
        "log": log,
    }
    save_json(os.path.join(outdir, "colour_truth.json"), truth)
    # ---- 折れ線
    def pts(P_):
        return [r3(p) for p in P_]
    feat = []
    for s in stripes:
        for side in ("left", "right"):
            if side + "_display" in s:
                feat.append({"id": "%s_%s" % (s["id"], side), "items": [77, 118, 268, 269], "kind": "stripe_edge", "stripe": s["id"],
                             "points_display": s[side + "_display"]})
        feat.append({"id": s["id"] + "_center", "items": [77, 118], "kind": "stripe_centerline", "stripe": s["id"], "points_display": s["centerline_display"]})
    for k, f in enumerate(wfeats):
        nb = {SKY: "sky", OUTSIDE: "outside"}.get(f["neighbour"], NAME.get(f["neighbour"], str(f["neighbour"])))
        feat.append({"id": "WP%04d" % (k + 1), "items": [f["item_zone"]] if f["item_zone"] in (79, 133, 134) else [], "kind": "white_part",
                     "zone_item": f["item_zone"], "neighbour": nb, "hole": f["hole"], "points_display": pts(f["points"])})
    for k, s in enumerate(inner_segs):
        feat.append({"id": "IF%03d" % (k + 1), "items": [73, 263], "kind": "inner_face_boundary", "region": s["region"], "neighbour": s["neighbour"],
                     "points_display": pts(s["points"])})
    for k, s in enumerate(b120):
        feat.append({"id": "B120_%02d" % (k + 1), "items": [120], "kind": "boundary_120", "points_display": pts(s)})
    for cls_ in ("ai_mid", "mizuiro"):
        for k, s in enumerate(b270[cls_]):
            feat.append({"id": "B270%s_%03d" % ("A" if cls_ == "ai_mid" else "M", k + 1), "items": [270], "kind": "boundary_270_" + cls_,
                         "default": cls_ == "ai_mid", "points_display": pts(s)})
    regs_out = [{k: v for k, v in r.items() if not k.startswith("_")} for r in regs]
    for r in regs_out:
        r["in_white_range_175"] = r["id"] in set(r175["regions"])
    poly = {"schema": "GreatWave.PaintingTruth.colour_polylines/1", "number": "28", "part": "A", "version": "v0",
            "coordinate_ja": "表示 px（1920×1080、画素中心が整数）。hi px へは x_h = (x_d + 0.5 − ox)/s − 0.5、y_h = (y_d + 0.5)/s − 0.5。",
            "frame": {"scale": fr.s, "offset_x": fr.ox},
            "regions_note_ja": "regions は主浪の色区（白・淡い水色・藍中・藍濃）の連結成分ごとの輪郭（外周と穴）。線は両側の色へ吸収した地図から取った。ID は色の頭文字＋面積の大きい順（W001 が最大の白）。hi px の 2 倍拡大で輪郭を取り、Douglas–Peucker（%.2f hi px）で間引いた。" % P["contour_eps_hi"],
            "regions": regs_out, "features": feat}
    save_json(os.path.join(outdir, "colour_polylines.json"), poly)
    print("JSON", round(time.time() - t0, 1), "s")
    # ---- 図
    flat = {n: tuple(int(v) for v in T.lab_to_srgb8_best(np.array(med_disp[n]["lab_median"]))[0]) for n in COLOUR_CLASSES}
    figs = {}
    p_ = os.path.join(evid, "28A_colour_regions.png")
    fig_regions(disp_rgb, disp_layer, flat, p_, "28A 主浪の色区（白・淡い水色・藍中・藍濃）を各色区の中央値で平塗りした図")
    figs["colour_regions"] = rel(p_)
    p_ = os.path.join(evid, "28A_stripes.png")
    band_disp = np.full((1080, 1920), "", "<U4")
    for s_ in stripes:
        cov = fr.hi_to_disp_cov(comp_id == lab_of[s_["region"]])
        band_disp[cov >= 0.5] = s_["id"]
    fig_stripes(disp_rgb, band_disp, stripes, dark, chains, branches, main_stripes, ann, lower, p_)
    figs["stripes"] = rel(p_)
    p_ = os.path.join(evid, "28A_stripes_lower.png")
    fig_stripes_lower(disp_rgb, band_disp, stripes, dark, lower, p_)
    figs["stripes_lower"] = rel(p_)
    wr_disp = fr.hi_to_disp_cov(white_range) >= 0.5
    p_ = os.path.join(evid, "28A_white_band.png")
    fig_white_band(disp_rgb, fr.hi_to_disp_cov(w1) >= 0.5, wfeats, band, p_)
    figs["white_band"] = rel(p_)
    r175_disp = {}
    for n_ in ("mizuiro", "ai_mid", "ai_dark"):
        ids = [lab_of[rid] for rid in r175["regions"] if reg_by_id[rid]["class"] == n_]
        r175_disp[n_] = fr.hi_to_disp_cov(np.isin(comp_id, ids)) >= 0.5
    p_ = os.path.join(evid, "28A_white_inner.png")
    fig_white_inner(disp_rgb, None, r175_disp, wr_disp, inner_cov >= 0.5, b270, b120, p_)
    figs["white_inner"] = rel(p_)
    p_ = os.path.join(evid, "28A_mizuiro_evidence.png")
    dl = ["決定（既定値・利用者未回答）：バックログの「水色」＝ 藍中（ai_mid）。淡い水色（調色板 mizuiro）は泡の斑として別の色区で残す。",
          "項目ごと：73・77・118・120・263・265・269 → 藍中。175／176 → 白の中の明るい色は淡い水色が主（藍中も残す）。270 → 既定 藍中・別案 淡い水色。",
          "内側の帯の Lab 中央値 %s、藍中の中央値との ΔE00 %.2f、淡い水色の中央値との ΔE00 %.2f" % (
              inner_rec["lab_median_eroded_3px"], inner_rec["dE00_to_ai_mid_median"], inner_rec["dE00_to_mizuiro_median"]) if inner_rec else ""]
    fig_evidence(disp_rgb, ev, ann["mizuiro_evidence_zones_display"], med_disp, dl, p_)
    figs["mizuiro_evidence"] = rel(p_)
    # 拡大（hi px の原画とラベル、唇の付け根と胴の下側）
    for nm, box in [("lipbase", (740, 300, 960, 520)), ("curl_lower", (560, 480, 780, 700))]:
        a0 = fr.d2h(np.array(box[:2], np.float64)).astype(int)
        a1 = fr.d2h(np.array(box[2:], np.float64)).astype(int)
        p_ = os.path.join(evid, "28A_closeup_%s.png" % nm)
        fig_closeup(rgb[a0[1]:a1[1], a0[0]:a1[0]], mw_layer[a0[1]:a1[1], a0[0]:a1[0]], p_,
                    "28A 拡大（左：高解像度原画、右：色クラス。白・淡い水色・藍中・藍濃・赤＝線・灰＝主浪の外・桃＝空）表示 px %s" % (box,), scale=1)
        figs["closeup_" + nm] = rel(p_)
    print("図", round(time.time() - t0, 1), "s")
    # ---- 数値（記録のみ）と実行記録
    out_files = [os.path.join(outdir, "colour_truth.json"), os.path.join(outdir, "colour_polylines.json")] + \
                [os.path.join(REPO, v) for v in mask_paths.values()] + [os.path.join(REPO, v) for v in figs.values()]
    def feat_len(item):
        return round(sum(polyline_len(f["points"]) for f in wfeats if f["item_zone"] == item and f["neighbour"] not in (SKY, OUTSIDE)), 1)

    def feat_n(item):
        return sum(1 for f in wfeats if f["item_zone"] == item and f["neighbour"] not in (SKY, OUTSIDE))
    n_cls = {n: sum(1 for r in regs if r["class"] == n) for n in COLOUR_CLASSES}
    RO = "record-only"
    JB = "28B（投影ベイクと shader v1 の描画を、この真値に照らして判定する）"
    metrics = {
        "schema": "GreatWave.ArtFirst.metrics/1", "number": "28", "part": "A",
        "evidence_kind_ja": "文書準備と numpy/OpenCV の計算（原画から真値を作る段）。Unity・PCビルド・HMD 実機の結果は含まない。",
        "judgement_ja": "第A部は真値を作る段で、どの項目も合否を出さない（すべて record-only）。境界 ≤4 px と ΔE00 ≤5 の判定は第B部（投影ベイクと shader v1 の描画）で行う。",
        "items": {
            "73": {"value": {"inner_face_bands": chains.get("inner_face", {}).get("stripes", []),
                             "boundary_length_by_neighbour_display_px": inner_rec["boundary_length_by_neighbour_display_px"] if inner_rec else None},
                   "result": RO, "judged_in": JB, "truth": "colour_truth.json#/inner_face, colour_polylines.json features kind=inner_face_boundary"},
            "77": {"value": {"lower_side_ai_mid_bands_ordered": log["stripes"]["order"]["lower_side"],
                             "n_lower_side_ai_mid_bands": log["stripes"]["n_lower_side_bands"],
                             "n_lower_side_ai_mid_bands_reaching_strip": log["stripes"]["n_lower_side_bands_reaching_strip"],
                             "lower_side_dark_stripes": [{"id": d["id"], "between": d["between"], "width_display_px": d["width_on_lower_side_display_px"],
                                                          "bands_ending_above": d["bands_ending_above"]} for d in dark],
                             "n_lower_side_dark_stripes": len(dark),
                             "n_lower_side_dark_stripes_between_two_bands": sum(1 for d in dark if all(str(b_).startswith("SL") for b_ in d["between"])),
                             "lower_ends": {s_["id"]: {"point_display": s_["lower_end_display"], "kind": s_["lower_end_kind"],
                                                       "gap_to_lower_side_display_px": s_["lower_side_gap_display_px"]} for s_ in stripes if s_["id"].startswith("SL")}},
                   "result": RO, "judged_in": JB, "truth": "colour_truth.json#/stripes/lower_side, #/stripes/dark_stripes_lower_side, #/stripes/ai_mid_bands"},
            "79": {"value": {"main_white": w1_id, "white_area_display_px2": reg_by_id[w1_id]["area_display_px2"],
                             "inner_boundary_length_display_px": feat_len(79), "inner_boundary_segments": feat_n(79)},
                   "result": RO, "judged_in": JB, "truth": "colour_polylines.json features kind=white_part, zone_item=79（空の側の境界は番号23の 78/130）"},
            "118": {"value": {"main_stripes": [{"id": m["id"], "bands": m["bands"], "total_centerline_length_display_px": m["total_centerline_length_display_px"],
                                                "lower_end_display": m["lower_end_display"], "upper_end_display": m["upper_end_display"]} for m in main_stripes],
                              "chains": {k: v["stripes"] for k, v in chains.items()}},
                    "result": RO, "judged_in": JB, "truth": "colour_truth.json#/stripes/main_stripes_118, colour_polylines.json features kind=stripe_edge"},
            "120": {"value": {"boundary_length_display_px": round(sum(polyline_len(s_) for s_ in b120), 1), "n_segments": len(b120)},
                    "result": RO, "judged_in": JB, "truth": "colour_polylines.json features kind=boundary_120"},
            "133": {"value": {"main_white": w1_id, "left_and_upper_in_one_component": True,
                              "inner_boundary_length_display_px": feat_len(133), "inner_boundary_segments": feat_n(133)},
                    "result": RO, "judged_in": JB, "truth": "colour_polylines.json features kind=white_part, zone_item=133（空の側は番号23の 131）"},
            "134": {"value": {"band_width_display_px": band["width_display_px"],
                              "wide_narrow_order_from_crest": [{"kind": e["kind"], "width": e["width"], "at_display": e["at_display"]} for e in band["wide_narrow_order_from_crest"]],
                              "stop_counts": band["stop_counts"], "inner_boundary_length_display_px": feat_len(134)},
                    "result": RO, "judged_in": JB, "truth": "colour_truth.json#/white/band_134, colour_polylines.json features kind=white_part, zone_item=134"},
            "175": {"value": {"non_white_regions_in_white_range": r175["non_white_regions"], "line_area_in_range_display_px2": r175["line_area_in_range_display_px2"],
                              "white_range_area_display_px2": r175["white_range_area_display_px2"]},
                    "result": RO, "judged_in": JB, "truth": "colour_truth.json#/white/regions_175, colour_polylines.json regions in_white_range_175=true"},
            "178": {"value": {"n_branch_candidates": len(branches),
                              "branch_points": [{"stripe": b_["stripe"], "end": b_["end"], "point_display": b_["point_display"]} for b_ in branches]},
                    "result": RO, "judged_in": "記録のみ（計画の損切りどおり、分岐の判定は延期できる）", "truth": "colour_truth.json#/stripes/branches_178"},
            "263": {"value": {"lower_end_display": inner_rec["lower_end_display"] if inner_rec else None,
                              "lower_end_kind": inner_rec["lower_end_kind"] if inner_rec else None,
                              "below_lower_end_blue_fraction": inner_rec["below_lower_end_record"]["blue_px_fraction"] if inner_rec else None},
                    "result": RO, "judged_in": JB, "truth": "colour_truth.json#/inner_face"},
            "265": {"value": {"target_lab": inner_rec["lab_median_eroded_3px"] if inner_rec else None,
                              "dE00_to_ai_mid_median": inner_rec["dE00_to_ai_mid_median"] if inner_rec else None,
                              "dE00_to_mizuiro_median": inner_rec["dE00_to_mizuiro_median"] if inner_rec else None},
                    "result": RO, "judged_in": JB, "truth": "colour_truth.json#/inner_face/lab_median_eroded_3px"},
            "266/267": {"value": {"flat_targets_lab": {n: (med_disp[n]["lab_median"] if med_disp[n] else None) for n in COLOUR_CLASSES},
                                  "flat_targets_srgb8": {n: pal_cmp[n]["srgb8"] for n in pal_cmp}},
                        "result": RO, "judged_in": JB, "truth": "colour_truth.json#/palette_display_median"},
            "270": {"value": alt, "default": "ai_mid", "alternative": "mizuiro",
                    "result": RO, "judged_in": JB, "truth": "colour_polylines.json features kind=boundary_270_ai_mid（既定）/ boundary_270_mizuiro（別案）"},
        },
        "mizuiro_mapping": {"decision": decision["decision"], "status": decision["status_ja"], "per_item_summary_ja": decision["per_item_summary_ja"],
                            "per_item": [{"item": r_["item"], "maps_to": r_["maps_to"]} for r_ in decision["per_item"]],
                            "dE00_mizuiro_vs_ai_mid_medians": decision["dE00_mizuiro_vs_ai_mid_medians"], "result": RO},
        "palette_display_median": {n: (med_disp[n]["lab_median"] if med_disp[n] else None) for n in COLOUR_CLASSES},
        "palette_compare_23": {n: {"dE00_to_palette23": v["dE00_to_palette23"]} for n, v in pal_cmp.items()},
        "counts": {"regions_by_class": n_cls, "ai_mid_bands": len(stripes), "main_stripes": len(main_stripes),
                   "hi_px_by_class": log["main_wave"]["hi_px"], "line_hi_px": log["main_wave"]["line_hi_px"]},
        "outputs": {"truth": rel(os.path.join(outdir, "colour_truth.json")), "polylines": rel(os.path.join(outdir, "colour_polylines.json")),
                    "masks": mask_paths, "figures": figs},
    }
    save_json(os.path.join(evid, "partA_metrics.json"), metrics)
    out_files.append(os.path.join(evid, "partA_metrics.json"))
    run = {
        "schema": "GreatWave.ArtFirst.run/1", "number": "28", "part": "A", "generated_utc": now,
        "command": "py -3.10 Tools/PaintingTruth/colour/colour_truth.py --evidence %s --build %s" % (rel(evid), rel(build)),
        "tools": {"python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__,
                  "pillow": __import__("PIL").__version__, "os": platform.platform()},
        "elapsed_s": round(time.time() - t0, 1),
        "reuse_stage_a": bool(a.reuse_stage_a),
        "inputs_sha256": in_sha,
        "outputs_sha256": {rel(p): sha256(p) for p in out_files},
        "build_not_committed": {rel(cache): sha256(cache)} if os.path.exists(cache) else {},
    }
    save_json(os.path.join(evid, "partA_run.json"), run)
    print("完了", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    main()
