# -*- coding: utf-8 -*-
"""美術の見本04 の渡す準備（Q32）：証拠の図（どれも 1920×1080、日本語の見出し）と metrics.json・run.json・rules_check.json を
Docs/Evidence/ArtSample04/ へ書く。

使う描画（どれも Git 対象外、描き直さない）：
  見本04 = 直しの回 1 の Unity の描画 Build/Polish/sample04/assemble/render/FX1（主役波 K*′ AS04F ＋ ④ の別の青い波 wave4 ＋ AS04F の材質 ＋ 爪 35 本）
  見本03 V2 = Build/Polish/sample03/fix01/render/V2（同じ視点・同じカメラ・同じ時刻）
粘土と層の色づけは numpy の z バッファ（Unity の描画ではない。asm4_common.scene・raster と同じ三角形。爪なし）でここで描く。
彫刻の写真・写真から作った画像・利用者のマスクと画像は使わない（入れない）。利用者の黄色の線（④・出っ張りの所）と ①②③ の範囲は、
s4_common の多角形の点（原画の画素）から線で描き足す。

  as04_1a_painting_view.png   原画視点：原画｜見本03 V2｜見本04（①②③④ の範囲の線）と、左側の拡大（④ と ②③）
  as04_1b_painting_bulge.png  原画視点の拡大：出っ張りの所（利用者の黄色の線）。上：原画｜見本03 V2｜見本04、下：粘土の見本03 の形｜見本04 の形｜見本04 爪なし
  as04_2_clay.png             粘土（形だけ）：見本03 の形｜見本04。左右の側面・真上・後ろ 65°、峰に沿う長さ（0.3 H・0.8 H）の線と表
  as04_3_layers.png           三つの層 ①②③ の色づけ（numpy の粘土）：側面・真上・回り台。S11 の読み（分かれる・続く）を各図に
  as04_4a_material_views.png  平らな塗りの見本04：座席・座席から波・左の側面・右の側面・後ろ 65°・真上
  as04_4b_material_views_s03.png 同じ 6 視点の見本03 V2（比べ）
  as04_5a_turntable.png・5b   回り台 12 方位：見本03 V2｜見本04 を並べる
  as04_6_rules.png            測る規則のまとめ
使い方：py -3.10 -B Tools/GWWaveGen/as04/as04_deliver.py
"""
import datetime
import json
import os
import platform
import shutil
import sys

os.environ.setdefault("AS04_FIX", "fix1")

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import PIL  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "as03"))
import asm4_common as A  # noqa: E402
import shape_common as SC  # noqa: E402
import shape_clay as SCL  # noqa: E402
import asm_sheets as AS  # noqa: E402

assert A.FIX == "fix1", A.FIX
REPO = A.REPO
P = A.P
P4 = A.P4
R04 = A.ASM + "/render/" + A.RTAG          # FX1
R03 = P + "/sample03/fix01/render/V2"
PAINT = A.S4.PAINT
OUT = REPO + "/Docs/Evidence/ArtSample04"
W, H = 1920, 1080
FOOT = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし。美術が届いたかは利用者が決める（Q29・Q30）。"
FOOT_NP = "numpy の z バッファの粘土（Unity の描画ではない）。t* = 12 s の静止、爪なし。美術が届いたかは利用者が決める（Q29・Q30）。"
FOOT_RULES = "測る規則は見本を出す前の自動の確かめで、閉じる条件ではない。美術が届いたかは利用者が決める（Q29・Q30）。"
VIEWJ = {"painting": "原画視点", "seat": "座席（VR の視点）", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面",
         "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
N03 = "見本03 V2"
N04 = "見本04"
RED, GRN, CYN, YEL = (225, 40, 40), (30, 160, 60), (0, 170, 205), (255, 205, 0)
USED = {}
OUTS = []


def font(sz, bold=False):
    return AS.font(sz, bold)


def load(p):
    USED[p] = None
    return Image.open(p).convert("RGB")


def vjname(v):
    if v.startswith("tt"):
        return "回り台 %s°" % v[2:]
    return VIEWJ[v]


def new_sheet(title, sub=None):
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 10), title, font=font(30, True), fill=(10, 10, 10))
    if sub:
        y = 52
        for line in sub.split("\n"):
            d.text((14, y), line, font=font(18), fill=(60, 60, 60))
            y += 24
    return img, d


def finish(img, d, name, foot=FOOT):
    d.text((14, H - 28), foot, font=font(17), fill=(80, 80, 80))
    os.makedirs(OUT, exist_ok=True)
    p = OUT + "/" + name
    assert img.size == (W, H), img.size
    img.save(p, optimize=True)
    OUTS.append(p)
    print("SHEET", p, flush=True)
    return p


def paste(img, d, im, x, y, w, h, lab=None, lab_sz=17):
    img.paste(AS.fit(im, w, h), (x, y))
    if lab:
        AS.label(d, x + 8, y + 6, lab, lab_sz)


# ---------------------------------------------------------------- 原画を表示の枠（Unity の 1920×1080）に置く
def painting_disp():
    im = load(PAINT)
    w = round(im.width * A.S4.A_DISP)
    h = round(im.height * A.S4.A_DISP)
    c = Image.new("RGB", (W, H), (255, 255, 255))
    c.paste(im.resize((w, h), Image.LANCZOS), (int(round(A.S4.OFFX)), 0))
    return c


def regs_disp():
    r = A.S4.regions_ref()
    out = {k: A.S4.ref_to_disp(r[k]) for k in ("r1", "r2", "r3", "r4")}
    out["bulge"] = np.array(A.S4.BULGE_DISP, float)
    return out


def poly(im, pts, col, w=4, scale=1.0, off=(0, 0)):
    d = ImageDraw.Draw(im)
    q = [((float(x) - off[0]) * scale, (float(y) - off[1]) * scale) for x, y in pts]
    d.line(q + [q[0]], fill=col, width=w, joint="curve")


def marked(im, regs, keys, w=5):
    im = im.copy()
    cols = {"r1": RED, "r2": GRN, "r3": CYN, "r4": YEL, "bulge": YEL}
    for k in keys:
        poly(im, regs[k], cols[k], w)
    return im


# ---------------------------------------------------------------- 1a・1b 原画視点
def sheet1():
    regs = regs_disp()
    pd = painting_disp()
    s03 = load(R03 + "/views/painting_t120_claws.png")
    s04 = load(R04 + "/views/painting_t120_claws.png")
    img, d = new_sheet("美術の見本04：原画視点（t*）　原画｜見本03 V2｜見本04",
                       "見本04：主役波 K*′ AS04F ＋ 左端の別の小さな青い波（④）＋ 平らな塗り（冠・彫り・白の彫ったような跡なし）＋ 爪 35 本（面の内 25・近い海 10。波頭の 48 本は出さない）\n"
                       "線：赤 ① 浪尖・緑 ② b区域・水色 ③ 最左側の小区域（進行役の図、利用者が確かめた。Q32-2）・黄 ④（利用者が黄色の線で示した、輪郭線の最も左の短い一区間）。どれも原画の画素の点から描き足した")
    keys = ("r1", "r2", "r3", "r4")
    top = 104
    cw, chh = 636, 358
    for k, (im, lab) in enumerate(((pd, "原画 DP130155（メトロポリタン美術館の公開の画像）"), (s03, "見本03 V2（冠 OUT・彫りの面・平らな色）"),
                                   (s04, "見本04（AS04F ＋ wave4 ＋ 平らな塗り）"))):
        paste(img, d, marked(im, regs, keys, 6), k * 642, top, cw, chh, lab)
    # 左側の拡大（④ と ②③）
    box = (157, 290, 797, 717)
    y2 = top + chh + 12
    AS.label(d, 14, y2, "左側の拡大：④ は左端の小さな青い波の上の縁（黄）。その下の白は低く、③（水色）・②（緑）が白い房の層として並ぶか", 19, True)
    for k, (im, lab) in enumerate(((pd, "原画"), (s03, "見本03 V2：白い波が左へ長く延び、高い輪郭に合わせていた"),
                                   (s04, "見本04：④ は別の青い波、白は低く、尾は c −23.4 m まで"))):
        c = marked(im, regs, ("r2", "r3", "r4"), 4).crop(box)
        paste(img, d, c, k * 642, y2 + 34, 636, 424, lab)
    finish(img, d, "as04_1a_painting_view.png")

    # 1b 出っ張りの所
    img, d = new_sheet("美術の見本04：原画視点の拡大　頂の下・唇の左の内側の面の帯（出っ張り、S8）",
                       "黄色の線は利用者が見本03 V1 の原画視点の上に描いた所（Q32-3）。原画では内側の藍・淡い青の面と同じ弧の上にあり、出っ張り・折り重なりは要らない\n"
                       "上：Unity の描画（爪あり）。下：numpy の粘土（形だけ、爪なし。Unity の描画ではない）と見本04 の爪なしの描画")
    box = (470, 130, 990, 508)
    rows_y = (104, 104 + 470)
    clay03 = clay_painting("S03")
    clay04 = clay_painting("S04")
    s04f = load(R04 + "/views/painting_t120_clawfree.png")
    row1 = ((pd, "原画"), (s03, "見本03 V2（出っ張りの層が手前に重なる）"), (s04, "見本04（唇を短くし、内の面の弧が頂の下まで続く）"))
    row2 = ((clay03, "粘土：見本03 の形（AS02C）"), (clay04, "粘土：見本04 の形（AS04F ＋ wave4）"), (s04f, "見本04 爪なし"))
    for r, row in enumerate((row1, row2)):
        for k, (im, lab) in enumerate(row):
            c = marked(im, regs, ("bulge",), 4).crop(box)
            paste(img, d, c, k * 642, rows_y[r], 636, 462, lab)
    finish(img, d, "as04_1b_painting_bulge.png")


# ---------------------------------------------------------------- numpy の粘土
_SCN = {}


def scene(kind):
    if kind not in _SCN:
        tris, lab, _ = A.scene(kind, with_claws=False, with_sea=True)
        n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        lam = (0.40 + 0.60 * np.abs(n @ SCL.LIGHT)).astype(np.float32)
        _SCN[kind] = (tris, lab, lam)
    return _SCN[kind]


CLAY_RGB = {1: (196, 188, 176), 2: (196, 188, 176), 3: (196, 188, 176), 4: (196, 188, 176), 8: (196, 188, 176),
            5: (150, 168, 196), 6: (214, 220, 226), 7: (250, 250, 250)}
LAYER_RGB = {1: (214, 64, 52), 2: (64, 160, 72), 3: (40, 170, 190), 4: (196, 188, 176), 8: (150, 146, 140),
             5: (90, 112, 200), 6: (214, 220, 226), 7: (250, 250, 250)}


def shade(kind, cam, layers=False):
    tris, lab, lam = scene(kind)
    idb, D, L = A.raster(cam, tris, lab)
    img = np.full((cam.H, cam.W, 3), 246.0, np.float32)
    m = idb > 0
    t = idb[m] - 1
    pal = LAYER_RGB if layers else CLAY_RGB
    col = np.zeros((len(lab), 3), np.float32)
    for k, c in pal.items():
        col[lab == k] = c
    sh = lam[t, None]
    sea = (lab[t] == 6)
    sh = np.where(sea[:, None], 0.75 + 0.25 * sh, sh)
    img[m] = col[t] * sh
    e = A.occl_edges(D)
    img[e & m] = (40, 40, 48)
    return np.clip(img, 0, 255).astype(np.uint8), D, L


def clay_painting(kind):
    cam = A.painting_cam()
    img, _, _ = shade(kind, cam)
    return Image.fromarray(img)


_CAM = {}


def fitted_cam(view, Wc=960, Hc=540):
    key = (view, Wc, Hc)
    if key not in _CAM:
        pts = []
        for kind in ("S03", "S04"):
            tris, lab, _ = scene(kind)
            k = np.isin(lab, (1, 2, 3, 4, 8, 5))
            v = tris[k].reshape(-1, 3)
            pts.append(v[:: max(1, len(v) // 60000)])
        X = np.concatenate(pts)
        _CAM[key] = SCL.fit_cam(view, X, Wc, Hc, fill=0.84)
    return _CAM[key]


def crest_points(rows_path):
    c, Ar, Y = SC.load_rows(rows_path)
    X = SC.world(c, Ar, Y)
    j0, j1 = SC.J_B, SC.J_TIP
    jj = j0 + np.argmax(Y[:, j0:j1 + 1], axis=1)
    P = X[np.arange(len(c)), jj]
    return c, P, SC.band_extent(c, Ar, Y)


def crest_at(c, P, cv):
    i = int(np.clip(np.searchsorted(c, cv), 1, len(c) - 1))
    t = (cv - c[i - 1]) / max(c[i] - c[i - 1], 1e-9)
    return P[i - 1] + np.clip(t, 0, 1) * (P[i] - P[i - 1])


BAND_COL = {"0.3": (230, 120, 0), "0.8": (190, 0, 160)}


def draw_bands(im, cam, cp, scale):
    c, P, ext = cp
    d = ImageDraw.Draw(im)
    for f, col in BAND_COL.items():
        e = ext.get(f)
        if not e:
            continue
        a = crest_at(c, P, e["c_lo"]); b = crest_at(c, P, e["c_hi"])
        xy, z = cam.project(np.stack([a, b]))
        if not np.all(z > 0):
            continue
        q = [(float(x) * scale, float(y) * scale) for x, y in xy]
        d.line(q, fill=col, width=7)
        for x, y in q:
            d.ellipse((x - 10, y - 10, x + 10, y + 10), fill=col)
        if f == "0.8":   # 0.8 H は右の端の下、0.3 H は左の端の上（重ならないように）
            qi = q[0] if q[0][0] > q[1][0] else q[1]
            tx, ty = qi[0] - 120, qi[1] + 14
        else:
            qi = q[0] if q[0][0] < q[1][0] else q[1]
            tx, ty = qi[0] + 4, qi[1] - 46
        lab = "%s H %.1f m" % (f, e["width_m"])
        bb = d.textbbox((tx, ty), lab, font=font(32, True))
        d.rectangle((bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3), fill=(255, 255, 255))
        d.text((tx, ty), lab, font=font(32, True), fill=col)
    return im


def sheet2():
    views = ("side_left", "side_right", "top", "back65")
    cp = {"S03": crest_points(A.ROWS02C), "S04": crest_points(A.ROWS04)}
    rc = A.jl(P4 + "/rules_check.json")["rules"]["S10"]
    img, d = new_sheet("美術の見本04：粘土（形だけ）　見本03 の形（AS02C）｜見本04（AS04F ＋ ④ の青い波 wave4）",
                       "numpy の z バッファの粘土（Unity の描画ではない。爪なし）。主役波は灰、wave4 は青みの灰、周りの海は薄い灰。同じ視点・同じカメラ\n"
                       "線：波の峰に沿う向き（横向）の長さ。頂がその高さ（H = 20.27 m の 0.3・0.8）を越える範囲の両端を、主役波の頂の上で結んだ（主役波だけの値）")
    cw, chh = 476, 268
    y0 = 104
    for r, kind in enumerate(("S03", "S04")):
        for k, v in enumerate(views):
            cam = fitted_cam(v)
            arr, _, _ = shade(kind, cam)
            im = Image.fromarray(arr)
            im = draw_bands(im, cam, cp[kind], 1.0)
            name = "見本03 の形" if kind == "S03" else "見本04"
            paste(img, d, im, k * 481, y0 + r * (chh + 6), cw, chh, "%s ／ %s" % (name, VIEWJ[v]))
    # 表
    ty = y0 + 2 * (chh + 6) + 14
    d.text((14, ty), "峰に沿う長さ（m）：高さの帯ごとに、頂がその高さを越える c の範囲の幅（S10、rules_check.json）", font=font(20, True), fill=(10, 10, 10))
    ty += 34
    bands = ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]
    cols_x = [14, 420] + [560 + 150 * i for i in range(len(bands))]
    hdr = ["", ""] + ["%s H" % b for b in bands]
    for x, t in zip(cols_x, hdr):
        d.text((x, ty), t, font=font(18, True), fill=(30, 30, 30))
    e0 = rc["AS02C_sample03_shape"]; eh = rc["AS04_hero_only"]; eu = rc["AS04_union_hero_wave4"]; rat = rc["ratio_vs_sample03"]
    rows = [("見本03 の形（主役波 AS02C）", "", [e0[b]["width_m"] for b in bands]),
            ("見本04 主役波だけ（AS04F）", "", [eh[b]["width_m"] for b in bands]),
            ("見本04 主役波 ＋ wave4", "", [eu[b]["width_m"] for b in bands]),
            ("比（主役波 ＋ wave4 ÷ 見本03）", "", [rat[b]["union"] for b in bands])]
    for i, (lab, _, vals) in enumerate(rows):
        yy = ty + 30 * (i + 1)
        d.text((14, yy), lab, font=font(18), fill=(30, 30, 30))
        for x, v in zip(cols_x[2:], vals):
            s = ("%.2f" % v) if i == 3 else ("%.1f" % v)
            col = (0, 120, 40) if (i == 3 and v < 0.995) else (30, 30, 30)
            d.text((x, yy), s, font=font(18, i == 3), fill=col)
    yy = ty + 30 * 5 + 6
    d.text((14, yy), "詰めたのは低い帯（0.1〜0.5 H、左の白い尾を c −60 m から −23.4 m へ）だけ。見える頂の帯（0.6〜0.9 H）は見本03 と同じ長さ（第 2 段、原画視点の関門 D6 に触れる）。",
           font=font(18), fill=(150, 30, 30))
    finish(img, d, "as04_2_clay.png", FOOT_NP)


# ---------------------------------------------------------------- 3 三つの層
def s11_text(name, v):
    rc = A.jl(P4 + "/rules_check.json")["rules"]["S11"]["views"][name]
    key = {"tt%d" % a: "tt%d" % a for a in range(0, 360, 30)}.get(v, v)
    x = rc.get(key)
    if not x:
        return ""

    def one(pk, lab):
        s = x["pairs"][pk]["separated"]
        return "%s %s" % (lab, "片方が見えない" if s is None else ("分かれる" if s else "続く"))
    return "%s・%s" % (one("1-2", "①②"), one("2-3", "②③"))


def sheet3():
    rows = [("S03", "AS02C_sample03_shape", ("side_left", "top", "tt90", "tt300")),
            ("S04", "AS04_union", ("side_left", "top", "tt90", "tt300")),
            ("S04", "AS04_union", ("tt0", "tt120", "tt270", "tt330"))]
    s11 = A.jl(P4 + "/rules_check.json")["rules"]["S11"]["summary"]
    sm = lambda n, pk: s11[n][pk]["separated_share"]  # noqa: E731
    img, d = new_sheet("美術の見本04：三つの層 ①②③（numpy の粘土に色づけ、爪なし）　1 段目 見本03 の形、2・3 段目 見本04",
                       "赤 ① 浪尖（主の頂と唇、c −2〜+8 m）・緑 ② b区域の房（c −15.5〜−11.5 m）・水色 ③ 最左側の小さな房（c −23〜−17 m）。どれも頂より前で高さ 0.25 H0 以上の面。"
                       "青 wave4、灰 ほかの前の面、濃い灰 背。黒い線 = 遮る縁\n"
                       "各図の下の字は S11 の読み（側面・真上・回り台 12 方位の 15 視点で測った。分かれる＝遮る縁 20 画素以上か、前の面が別の塊）。"
                       "分かれて読める割合：①② %.3f → %.3f、②③ %.3f → %.3f（基準 0.5）"
                       % (sm("AS02C_sample03_shape", "1-2"), sm("AS04_union", "1-2"), sm("AS02C_sample03_shape", "2-3"), sm("AS04_union", "2-3")))
    cw, chh = 476, 268
    y0 = 128
    for r, (kind, name, views) in enumerate(rows):
        for k, v in enumerate(views):
            cam = fitted_cam(v)
            arr, _, _ = shade(kind, cam, layers=True)
            x = k * 481
            y = y0 + r * (chh + 34)
            paste(img, d, Image.fromarray(arr), x, y, cw, chh, "%s ／ %s" % ("見本03 の形" if kind == "S03" else "見本04", vjname(v)))
            t = s11_text(name, v)
            ok12 = "①② 分かれる" in t
            d.text((x + 8, y + chh + 4), t, font=font(18, True), fill=(0, 110, 40) if ok12 else (60, 60, 60))
    finish(img, d, "as04_3_layers.png", FOOT_NP)


# ---------------------------------------------------------------- 4 平らな塗りの視点
def sheet4():
    views = ("seat", "seat_toward_wave", "side_left", "side_right", "back65", "top")
    for tag, root, nm, sub in (("a", R04, N04, "見本04：主役波 AS04F ＋ wave4、AS04F Flat Smooth（光・艶・陰なしの平らな区域の色）、冠・彫り・泡の皮なし、爪 35 本"),
                               ("b", R03, N03, "比べ：見本03 V2（白い指の冠 OUT・泡の皮・滴・彫りの面の溝・平らな色）。見本04 の図と同じ視点・同じカメラ")):
        img, d = new_sheet("美術の見本04：平らな塗りの視点　%s" % nm if tag == "a" else "比べ：見本03 V2 の同じ 6 視点", sub)
        for k, v in enumerate(views):
            r, c = divmod(k, 3)
            paste(img, d, load(root + "/views/%s_t120_claws.png" % v), c * 642, 96 + r * 404, 636, 358, "%s ／ %s" % (nm, VIEWJ[v]), 19)
        d.text((14, 96 + 2 * 404 + 4), "爪あり（面の内 25・近い海 10）。座席は唇の真下の右の船の上（D7）。後ろ 65° は背の一つの山（S4）を見る視点", font=font(19), fill=(60, 60, 60))
        finish(img, d, "as04_4%s_material_views%s.png" % (tag, "" if tag == "a" else "_s03"))


# ---------------------------------------------------------------- 5 回り台
def sheet5():
    for tag, azs in (("a", (0, 30, 60, 90, 120, 150)), ("b", (180, 210, 240, 270, 300, 330))):
        img, d = new_sheet("美術の見本04：回り台（距離 72 m・仰角 16°、爪あり・飛沫なし）　見本03 V2｜見本04 を対に並べる",
                           "方位 %s。0° は原画の側、270°〜330° は左（③ と wave4 の側）から" % "・".join("%d°" % a for a in azs))
        cw, chh = 476, 268
        for i, az in enumerate(azs):
            r, cpair = divmod(i, 2)
            for j, (root, nm) in enumerate(((R03, N03), (R04, N04))):
                x = (cpair * 2 + j) * 481
                y = 84 + r * (chh + 30)
                paste(img, d, load(root + "/tt/t120_az%03d_claws.png" % az), x, y, cw, chh, "%s ／ %d°" % (nm, az))
        finish(img, d, "as04_5%s_turntable.png" % tag)


# ---------------------------------------------------------------- 6 規則
def sheet6():
    rk = A.jl(P4 + "/rules_check.json")["rules"]
    g = rk["G2"]["gates"]
    s11 = rk["S11"]["summary"]
    fl = A.jl(P4 + "/fix1/fleck_marks.json") if os.path.isfile(P4 + "/fix1/fleck_marks.json") else {}
    USED[P4 + "/fix1/fleck_marks.json"] = None
    rows = [
        ("G1", "原画カメラの投影を使わない。引き伸ばし・継ぎ目なし", rk["G1"]["verdict"],
         "シェーダー AS04F（AS04 の写し、白い点だけ直した）。禁じた語 0。模様の面の |∇w| が 1/3〜3 倍の外の三角形 0"),
        ("G2", "原画視点の輪郭（4 px 以下）", rk["G2"]["verdict"],
         "78 %.4f・130 %.4f・131 %.4f・132 σ12 %.3f・72 σ12 p95 %.4f px（主役波 ＋ wave4、爪あり・なし同じ）"
         % (g["78"]["claws"], g["130"]["claws"], g["131"]["claws"], g["132_s12"]["claws"], g["72_s12_p95"]["claws"])),
        ("S4", "背は一つの山（へこみ 0）", rk["S4"]["verdict"], "頂の高さ H(c) のへこみ 0 m。後ろからの輪郭のへこみ 0・0.27・0.37 px（1 px まで）"),
        ("S8", "黄色の線の帯は内の面と同じ弧（出っ張りなし）", rk["S8"]["verdict"],
         "内の面の線からの距離 p95 見本03 の形 %.2f m → %.2f m（0.15 m まで）。内の面に当たる割合 %.3f"
         % (rk["S8"]["AS02C_sample03_shape"]["dev_from_inner_face_m"]["p95"], rk["S8"]["AS04"]["dev_from_inner_face_m"]["p95"],
            rk["S8"]["AS04"]["first_hit_inner_face_share"])),
        ("S9", "左の白は低い。④ の輪郭は青い波が作る", rk["S9"]["verdict"],
         "④（x < 360）の輪郭の %.1f%% を wave4 が作る。x 360 以上は主役波 100%%。白の最も左 c −60.0 → −23.4 m"
         % (100 * rk["S9"]["per_segment"]["78"]["region4_x_lt_360"]["owner_share"]["wave4"])),
        ("S10", "峰に沿う向きに詰める", rk["S10"]["verdict"],
         "見本03 に対する比 0.1 H %.2f・0.3 H %.2f・0.5 H %.2f・0.6〜0.9 H 1.00（高い帯は詰めていない）"
         % (rk["S10"]["ratio_vs_sample03"]["0.1"]["union"], rk["S10"]["ratio_vs_sample03"]["0.3"]["union"], rk["S10"]["ratio_vs_sample03"]["0.5"]["union"])),
        ("S11", "三つの層 ①②③ が別の層に読める", rk["S11"]["verdict"],
         "分かれて読める視点の割合 ①② %.3f（見本03 の形 %.3f）・②③ %.3f（%.3f）。基準 0.5。①② が届かない"
         % (s11["AS04_union"]["1-2"]["separated_share"], s11["AS02C_sample03_shape"]["1-2"]["separated_share"],
            s11["AS04_union"]["2-3"]["separated_share"], s11["AS02C_sample03_shape"]["2-3"]["separated_share"])),
        ("T4・C5", "冠・彫り・凹凸なし、平らな塗り", rk["T4"]["verdict"], "冠のメッシュなし。主役波の点の滑らかな土台からのずれ 0.0000 m。光・艶・陰の語なし"),
        ("C2", "爪は利用者の模型の水準", rk["C2"]["verdict"], "爪 35 本（面の内 25・近い海 10）、不合 0。波頭の 48 本は出さない"),
        ("C3", "爪は原画の位置（原画視点の影）", rk["C3"]["verdict"], "置き直しは原画のカメラを中心とする倍率だけ。原画視点の影は画素まで同じ。IoU p10・p50・最小 0.875・0.892・0.853"),
    ]
    img, d = new_sheet("美術の見本04：測る規則のまとめ（美術の要求書 §1〜§4。rules_check.json）",
                       "測る規則は見本を出す前の自動の確かめ。美術が届いたかは利用者が決める（Q29・Q30）。数は PC の描画と numpy の測りで、HMD の実機ではない")
    y = 100
    xs = (14, 120, 610, 700)
    for x, t in zip(xs, ("規則", "中身", "結果", "主な数")):
        d.text((x, y), t, font=font(20, True), fill=(10, 10, 10))
    y += 34
    for code, ja, vd, num in rows:
        ok = vd == "pass"
        d.rectangle((8, y - 4, W - 8, y + 54), fill=(240, 248, 240) if ok else (253, 232, 228))
        d.text((xs[0], y), code, font=font(20, True), fill=(10, 10, 10))
        d.text((xs[1], y), ja, font=font(17), fill=(30, 30, 30))
        d.text((xs[2], y), "合" if ok else "不合", font=font(22, True), fill=(0, 120, 40) if ok else (190, 20, 20))
        # 主な数は 2 行に折る
        lines = wrap(num, 66)
        for i, ln in enumerate(lines[:2]):
            d.text((xs[3], y + i * 24), ln, font=font(17), fill=(30, 30, 30))
        y += 64
    y += 6
    notes = [
        "S11 の ①② が届かない理由：左・前・上からは、② から ① へ頂の前の帯（c −11.5〜−2 m）が一続きの面でつながる。頂の高さは ② の 13 m から ① の 20 m へ",
        "単調に上がる（S4 の一つの山）ので、遮る縁ができない。切るには ② と ① の間で頂を一度下げる鞍が要り、S4 に反する。① の唇を左へ延ばすと S8 の出っ張りが戻る。",
        "②③ は直しの回 1 で唇に湾（c −16.9〜−15.7 m で 8 m 短く）を足し、直す前の見本04 の 0.182 から 0.636 になった。測りと基準 0.5 は進行役の既定。①② は利用者が見て決める。",
    ]
    if fl:
        notes.append("白い点（直しの回 1）：黄色の線の中の白い印 6 → 19、縦横比 p95 29.6 → 3.8、最長 183 → 16 px（原画は 62 の丸い点、縦横比 4 以下）。")
    for ln in notes:
        d.text((14, y), ln, font=font(18), fill=(40, 40, 40) if ln.startswith("白い点") else (140, 30, 30))
        y += 28
    finish(img, d, "as04_6_rules.png", FOOT_RULES)


def wrap(s, n):
    out, cur = [], ""
    for ch in s:
        cur += ch
        if len(cur) >= n and ch in "。、・）） ":
            out.append(cur); cur = ""
    if cur:
        out.append(cur)
    if len(out) > 2:
        out = [out[0], "".join(out[1:])]
    return out


# ---------------------------------------------------------------- metrics・run
def write_json():
    rk = A.jl(P4 + "/rules_check.json")
    shutil.copyfile(P4 + "/rules_check.json", OUT + "/rules_check.json")
    r = rk["rules"]
    fl = A.jl(P4 + "/fix1/fleck_marks.json")
    un = A.jl(A.UNION)
    met = {
        "schema": "GreatWave.AS04.metrics/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "sample_ja": "美術の見本04（Q32）直しの回 1 の後：主役波 K*′ AS04F ＋ ④ の別の青い波 wave4 ＋ AS04F Flat Smooth ＋ 爪 35 本（面の内 25・近い海 10）。t* = 12 s の静止",
        "judge_ja": "美術が届いたかは利用者が決める（Q29・Q30）。数は PC の描画と numpy の測りで、HMD の実機ではない",
        "rules_summary": rk["summary"],
        "G2_gates_px": r["G2"]["gates"],
        "S4_checks": r["S4"]["checks"],
        "S8": {k: r["S8"][k] for k in ("AS02C_sample03_shape", "AS04", "painting_view_owner_share_in_loop_S04")},
        "S9_region4_owner_share": r["S9"]["per_segment"]["78"]["region4_x_lt_360"],
        "S9_wedge_lower_edge_too_high_px_ref": [x.get("too_high_px") for x in r["S9"]["wedge_lower_edge"]],
        "S9_white_part": r["S9"]["white_part"],
        "S10_width_m": {"sample03_shape_AS02C": r["S10"]["AS02C_sample03_shape"], "AS04F_hero_only": r["S10"]["AS04_hero_only"],
                        "AS04F_union_hero_wave4": r["S10"]["AS04_union_hero_wave4"], "ratio_vs_sample03": r["S10"]["ratio_vs_sample03"]},
        "S11_summary": r["S11"]["summary"],
        "S11_geometry_steps": r["S11"]["geometry_steps"],
        "S11_per_view_AS04F_union": {v: {pk: {"separated": x["pairs"][pk]["separated"], "occlusion_edge_px": x["pairs"][pk]["occlusion_edge_px"]}
                                         for pk in ("1-2", "2-3")} for v, x in r["S11"]["views"]["AS04_union"].items()},
        "T4_relief": r["T4"]["relief_vs_smooth_base"].get("AS04_hero_in_union"),
        "C2": {k: r["C2"][k] for k in ("by_role", "fail", "moved_gt_1cm")},
        "C3": {k: r["C3"][k] for k in ("iou_painting_p10_p50_min_sample02", "painting_visible_frac_p10_p50_min")},
        "white_flecks_fix1": fl,
        "union_mesh": {k: un.get(k) for k in ("vertices", "triangles", "bin", "sha256") if k in un},
        "claws_float_above_surface_m_ja": "置き直した面の内の爪のうち claw057 1.34・claw079 1.43・claw054 1.40・claw037 1.33 m が面から出る（見本03 0.17〜0.60 m）。直していない",
    }
    A.jdump(OUT + "/metrics.json", met)
    ins = sorted(USED) + [A.UNION, A.ROWS04, A.ROWS02C, A.HERO_SM02C, P4 + "/rules_check.json", P4 + "/fix1/run.json"]
    run = {
        "schema": "GreatWave.AS04.deliver_run/1",
        "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "tool": "Tools/GWWaveGen/as04/as04_deliver.py",
        "env": {"AS04_FIX": A.FIX, "python": platform.python_version(), "numpy": np.__version__, "opencv": cv2.__version__, "Pillow": PIL.__version__},
        "renders_ja": "見本04 = Unity/Build/Polish/sample04/assemble/render/FX1（Unity 6000.4.3f1、PC オフスクリーン、描画の記録 as03asm_render_report.json）、"
                      "見本03 V2 = Unity/Build/Polish/sample03/fix01/render/V2。粘土・層の色づけは numpy の z バッファ（この道具が描いた）",
        "not_used_ja": "彫刻の写真・写真から作った画像・参照モデルの OBJ・利用者の画像とマスクは読んでいない・入れていない（①②③④ と出っ張りの線は s4_common の点から描いた）",
        "inputs_sha256": {A.rel(p): A.sha(p) for p in ins if os.path.isfile(p)},
        "outputs_sha256": {A.rel(p): A.sha(p) for p in OUTS + [OUT + "/rules_check.json", OUT + "/metrics.json"]},
    }
    A.jdump(OUT + "/run.json", run)


def main():
    os.makedirs(OUT, exist_ok=True)
    sheet1()
    sheet2()
    sheet3()
    sheet4()
    sheet5()
    sheet6()
    write_json()
    print("DELIVER_DONE", len(OUTS), flush=True)


if __name__ == "__main__":
    main()
