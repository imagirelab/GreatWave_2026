# -*- coding: utf-8 -*-
"""美術の見本04 の調べ S の図（粘土の下見。numpy の z バッファで描く。Unity の描画ではない）。
A：利用者の区域 ①②③・④・出っ張りを主役波 AS02C の面に塗り、原画視点・座席・左右の側面・後ろ 65°・真上で見る。
B：行ごとの原画視点での縛り（輪郭を作る行・見えるだけの行・画の外の行）を同じ 6 視点で見る。
C：④（左端の小さな青い波の上の縁）：原画の左の切り出しに、輪郭の真値・青い楔の下の縁・今の主役波の上の縁を重ね、真上から射線と別の波の置き場所を見る。
D：出っ張り：原画視点で、見えている唇の外の面の、内の面の弧からの出（m）と、断面（s4_bulge_sections.png）。
E：波峰線の向きの長さ：高さの帯ごとの c の幅（主役波と参照モデルの数）と、行の縛り。
参照モデルの形・写真は描かない（数だけ）。原画はメトロポリタン美術館の公開の画像。
使い方：py -3.10 -B Tools/GWWaveGen/as04/s4_sheets.py
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s4_common as S  # noqa: E402
import s4_render as RD  # noqa: E402

FONT = "C:/Windows/Fonts/meiryo.ttc"
FONTB = "C:/Windows/Fonts/meiryob.ttc"
COL = {"r1": (215, 55, 55), "r2": (40, 160, 70), "r3": (30, 150, 200), "r4": (245, 150, 20), "bulge": (190, 50, 200)}
PRIO = ["r1", "r2", "r3", "r4", "bulge"]          # 後ろほど上に塗る
BASE = (205, 205, 200)
VIEWS = [("painting", "原画視点"), ("seat", "座席"), ("side_left", "左の側面"), ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]
SEGC = {"78": (245, 130, 0), "130": (230, 200, 0), "131": (60, 180, 60), "132": (40, 120, 230), "72": (170, 60, 200)}


def font(n, b=False):
    return ImageFont.truetype(FONTB if b else FONT, n)


def cam_of(name):
    return S.CC.painting_cam() if name == "painting" else S.CC.cam_view(name)


def crest_labels(hero, cam, cm, img, every=(-50, -40, -30, -20, -15, -10, -5, 0, 5, 10)):
    d = ImageDraw.Draw(img)
    sx = img.size[0] / cam.W
    for cv in every:
        i = int(np.argmin(np.abs(cm - cv)))
        j = int(np.argmax(hero.X[i, S.J_B:S.J_TIP, 1]) + S.J_B)
        p, z = cam.project(hero.X[i, j][None])
        if z[0] <= 0:
            continue
        x, y = p[0][0] * sx, p[0][1] * sx
        if 0 <= x < img.size[0] and 0 <= y < img.size[1]:
            d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=(20, 20, 20))
            d.text((x + 5, y - 24), "c%+d" % cv, font=font(17), fill=(20, 20, 20))


def vertex_labels(R, C):
    z = np.load(S.TMP + "/s4_vertex_regions.npz")
    lab = np.full((R, C), -1, np.int32)
    for k, nm in enumerate(PRIO):
        m = z[nm]
        m = cv2.dilate(m.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
        lab[m] = k
    return lab


def autocrop(pim, idb, margin=0.06, aspect=16 / 9):
    """背景でない画素の外接矩形を、余白を付け、縦横比を保って切り出す（遠い視点の主役波を大きく見せる）。"""
    ys, xs = np.nonzero(idb > 0)
    if not len(xs):
        return pim
    sx = pim.size[0] / idb.shape[1]
    x0, x1, y0, y1 = xs.min() * sx, xs.max() * sx, ys.min() * sx, ys.max() * sx
    w, h = x1 - x0, y1 - y0
    w *= 1 + 2 * margin; h *= 1 + 2 * margin
    if w / h < aspect:
        w = h * aspect
    else:
        h = w / aspect
    cx, cy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
    box = [int(cx - w / 2), int(cy - h / 2), int(cx + w / 2), int(cy + h / 2)]
    out = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), (236, 236, 232))
    out.paste(pim.crop((max(0, box[0]), max(0, box[1]), min(pim.size[0], box[2]), min(pim.size[1], box[3]))),
              (max(0, -box[0]), max(0, -box[1])))
    return out


def panel_grid(imgs, titles, head, sub, cols=3, pw=880, ph=495, legend=None):
    rows = (len(imgs) + cols - 1) // cols
    W = cols * pw + (cols + 1) * 14
    H = 110 + rows * (ph + 44) + (70 if legend else 20)
    C = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(C)
    d.text((18, 12), head, font=font(34, True), fill=(20, 20, 20))
    d.text((18, 60), sub, font=font(20), fill=(70, 70, 70))
    for k, (im, t) in enumerate(zip(imgs, titles)):
        x = 14 + (k % cols) * (pw + 14); y = 110 + (k // cols) * (ph + 44)
        C.paste(im.resize((pw, ph), Image.LANCZOS), (x, y + 34))
        d.text((x, y + 2), t, font=font(24, True), fill=(30, 30, 30))
    if legend:
        x = 18; y = H - 56
        for nm, col in legend:
            d.rectangle([x, y + 6, x + 30, y + 30], fill=col)
            d.text((x + 38, y + 2), nm, font=font(22), fill=(30, 30, 30))
            x += 60 + int(d.textlength(nm, font=font(22)))
    return C


def main():
    os.makedirs(S.OUT, exist_ok=True)
    X0 = S.load_hero()
    hero = S.CC.Hero(X0)
    cm = S.rows_c()
    M = json.load(open(S.OUT + "/s4_map.json", encoding="utf-8"))
    R, C = hero.R, hero.C
    T = hero.Tg
    tr, tc = np.divmod(T, C)
    tris = hero.V[T]
    # ---------------------------------------------------------------- A：区域
    lab = vertex_labels(R, C)
    tl = lab.reshape(-1)[T].max(1)
    rgbA = np.tile(np.array(BASE, float), (len(T), 1))
    for k, nm in enumerate(PRIO):
        rgbA[tl == k] = COL[nm]
    imgsA, titles = [], []
    for v, vj in VIEWS:
        cam = cam_of(v)
        im, idb = RD.render(cam, tris, rgbA)
        pim = Image.fromarray(im)
        if v == "painting":
            d = ImageDraw.Draw(pim)
            for nm in ("r1", "r2", "r3", "r4", "bulge"):
                P = S.ref_to_disp(S.regions_ref()[nm])
                d.line([tuple(p) for p in P] + [tuple(P[0])], fill=COL[nm], width=4)
            d.line([(157, 0), (157, 1079)], fill=(120, 120, 120), width=2)
            d.text((165, 1040), "← 原画の左の端（x 157）", font=font(26), fill=(60, 60, 60))
        crest_labels(hero, cam, cm, pim)
        if v in ("side_left", "side_right", "back65", "top"):
            pim = autocrop(pim, idb)
        imgsA.append(pim); titles.append(vj + ("（主役波に合わせて拡大）" if v in ("side_left", "side_right", "back65", "top") else ""))
    leg = [(S.REGION_JA[k], COL[k]) for k in PRIO] + [("どの区域でもない", BASE)]
    A = panel_grid(imgsA, titles, "調べ S-1：利用者の区域を t* の主役波 AS02C の面へ（原画のカメラの射線と z バッファ）",
                   "原画視点で区域の多角形の中に見えている面の頂点を塗った（見えない裏の面は塗らない）。黒い点と c±n は頂の線の位置（m）。原画視点の枠線は区域の多角形。粘土の下見（numpy）、Unity の描画ではない。",
                   legend=leg)
    A.save(S.OUT + "/s4_A_regions.png")
    print("A", flush=True)
    # ---------------------------------------------------------------- B：行の縛り
    rows = M["rows_painting_view"]
    rowcol = np.zeros((R, 3))
    for e in rows:
        if e["outline_segments"]:
            rowcol[e["row"]] = SEGC[e["outline_segments"][0]]
        elif e["painting_px"] > 0:
            rowcol[e["row"]] = (175, 190, 210)
        else:
            rowcol[e["row"]] = (240, 205, 205)
    rgbB = rowcol[tr[:, 0]]
    imgsB = []
    for v, vj in VIEWS:
        cam = cam_of(v)
        im, idb = RD.render(cam, tris, rgbB)
        pim = Image.fromarray(im)
        if v == "painting":
            d = ImageDraw.Draw(pim)
            for sid, pts in S.outline_segments().items():
                P = S.ref_to_disp(pts)
                d.line([tuple(p) for p in P[::3]], fill=SEGC[sid], width=3)
        crest_labels(hero, cam, cm, pim)
        if v in ("side_left", "side_right", "back65", "top"):
            pim = autocrop(pim, idb)
        imgsB.append(pim)
    s = M["rows_summary"]
    legB = [("輪郭 78 を作る行", SEGC["78"]), ("130", SEGC["130"]), ("131", SEGC["131"]), ("132", SEGC["132"]), ("72", SEGC["72"]),
            ("原画視点で見えるが輪郭を作らない行", (175, 190, 210)), ("原画の画の外（自由に動かせる）", (240, 205, 205))]
    B = panel_grid(imgsB, titles, "調べ S-3：行ごとの原画視点の縛り（関門 78・130・131・132・72 に効く行と、自由な行）",
                   "行 0〜62（c −60〜−20.6 m）と行 231〜239（c +13.2〜+15 m）は原画の画の外で、関門に入らない。輪郭を作る行は c %.1f〜%+.1f m。色は行の最初の輪郭の区間。"
                   % tuple(s["c_outline_range"]), legend=legB)
    B.save(S.OUT + "/s4_B_rows_pinned.png")
    print("B", flush=True)
    sheet_C(hero, cm, M, tris, rgbA)
    print("C", flush=True)
    sheet_D(hero, cm, tris)
    print("D", flush=True)
    sheet_E(cm, M)
    print("E", flush=True)


def sheet_C(hero, cm, M, tris, rgbA):
    """④：原画の左の切り出しと、真上からの射線。"""
    P = cv2.imdecode(np.fromfile(S.PAINT, np.uint8), cv2.IMREAD_COLOR)[..., ::-1]
    x0, y0, x1, y1 = 0, 620, 900, 1300
    crop = Image.fromarray(np.ascontiguousarray(P[y0:y1, x0:x1]))
    sc = 1.6
    crop = crop.resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
    d = ImageDraw.Draw(crop)
    cols = M["region4"]["columns"]

    def T(x, y):
        return ((x - x0) * sc, (y - y0) * sc)
    s78 = S.outline_segments()["78"]
    d.line([T(*p) for p in s78[::2]], fill=(245, 130, 0), width=4)
    low = [(e["x_ref"], e["wedge_lower_edge_y_ref_smooth"]) for e in cols if e.get("wedge_lower_edge_y_ref_smooth") and e["x_ref"] <= 332]
    d.line([T(*p) for p in low], fill=(0, 200, 230), width=4)
    top = [(e["x_ref"], e["current_top_y_ref"]) for e in cols]
    for p in top[::2]:
        q = T(*p); d.ellipse([q[0] - 4, q[1] - 4, q[0] + 4, q[1] + 4], fill=(220, 30, 30))
    r4 = S.regions_ref()["r4"]
    d.line([T(*p) for p in r4] + [T(*r4[0])], fill=(250, 210, 0), width=3)
    d.text((10, 10), "原画（DP130155）の左の切り出し x 0〜900、y 620〜1300", font=font(24, True), fill=(20, 20, 20))
    # 真上：主役波＋射線
    cam = S.CC.cam_view("top")
    im, _ = RD.render(cam, tris, rgbA)
    pim = Image.fromarray(im)
    d2 = ImageDraw.Draw(pim)
    pc = S.CC.painting_cam()
    opts = M["region4"]["separate_wave_ray_options"]
    for o in opts:
        dd = np.array(o["ray_dir"])
        A_ = pc.pos + 0.0 * dd; B_ = pc.pos + 80.0 * dd
        pa, _ = cam.project(np.array([A_, B_]))
        d2.line([tuple(pa[0]), tuple(pa[1])], fill=(245, 130, 0), width=2)
        for b, cl in zip(o["by_crest_height"], [(120, 120, 120), (60, 140, 220), (20, 60, 200), (10, 30, 120), (0, 0, 60)]):
            q, _ = cam.project(np.array([b["xyz"]]))
            d2.ellipse([q[0][0] - 6, q[0][1] - 6, q[0][0] + 6, q[0][1] + 6], fill=cl, outline=(255, 255, 255))
    for e in cols:
        if "hero_xyz" in e:
            q, _ = cam.project(np.array([e["hero_xyz"]]))
            d2.ellipse([q[0][0] - 4, q[0][1] - 4, q[0][0] + 4, q[0][1] + 4], fill=(220, 30, 30))
    crest_labels(hero, cam, cm, pim)
    pim = pim.crop((300, 250, 1500, 1000))
    # 図の組み立て
    W = crop.size[0] + pim.size[0] + 60
    H = max(crop.size[1], pim.size[1]) + 330
    Cv = Image.new("RGB", (W, H), (250, 248, 242))
    dc = ImageDraw.Draw(Cv)
    dc.text((18, 12), "調べ S-1：④ 左端の小さな青い波の上の縁（利用者の黄色の線）と、別の青い波の置き場所", font=font(34, True), fill=(20, 20, 20))
    Cv.paste(crop, (20, 70))
    Cv.paste(pim, (crop.size[0] + 40, 70))
    dc.text((crop.size[0] + 40, 70 + pim.size[1] + 6), "真上（区域の色は図 A と同じ）。橙の線 = 原画のカメラから ④ の輪郭の点への射線。赤 = 今その輪郭を作る主役波の頂（行 77〜100）。\n青い丸 = 頂の高さ h 6・8・10・12・14 m の別の波を置くときの射線の上の点（濃いほど高い・遠い）", font=font(19), fill=(40, 40, 40))
    y = 70 + max(crop.size[1], pim.size[1]) + 70
    lines = [
        "橙 = 原画の輪郭の真値（区間 78、x 4〜482）。水色 = 左端の青い楔の下の縁（その下は白）。赤い点 = 今の主役波の一番上（原画視点）。黄 = 利用者の ④。",
        "・今 ④ の輪郭を作るのは主役波の左の部分の頂（行 77〜101、c −17.4〜−12.5 m、列 85〜106、高さ 10.9〜12.1 m = 0.53〜0.58 H0、カメラから 46.5〜51.6 m）。海ではない。",
        "・青い楔は x 0〜約 330 で、厚みは左端で 177 原画画素（今の主役波の深さで 1.46 m）、右へ細り x ≈ 330〜360 で輪郭の線だけになる。楔の下の生成りの白は楔の手前にあり、楔の下の部分を隠している。",
        "・別の青い波が楔を作るには、その頂の縁が射線の上で、手前の白（下げた主役波の左）より奥にあること：頂の高さ h = 12 m なら 53〜57 m（a −4.6〜−0.2、c −14.8〜−12.3）、",
        "  h = 14 m なら 65〜70 m（a −15.8〜−10.4、c −9.5〜−6.5）。h = 10 m（43〜44 m）は今の主役波より手前で、白の手前に出てしまう。x 360 では h 12 m の点（a −0.2、c −12.9）が今の主役波の頂（a −0.6、c −12.7）とほぼ重なり、継ぎ目なくつながる。",
    ]
    for k, t in enumerate(lines):
        dc.text((20, y + 34 * k), t, font=font(21), fill=(30, 30, 30))
    Cv.save(S.OUT + "/s4_C_region4.png")


def sheet_D(hero, cm, tris):
    B = json.load(open(S.OUT + "/s4_bulge.json", encoding="utf-8"))
    hits = np.load(S.TMP + "/s4_bulge_hits.npy")
    SX = S.hero_sec(hero.X)
    fit = {p["row"]: p for p in B["per_row_inner_arc"]}
    cam = S.CC.painting_cam()
    rgb = np.tile(np.array(BASE, float), (len(tris), 1))
    im, _ = RD.render(cam, tris, rgb)
    pim = Image.fromarray(im)
    d = ImageDraw.Draw(pim)
    for x, y, r, c, r2, c2, s1, s2 in hits:
        ri, ci = int(round(r)), int(round(c))
        f = fit.get(ri)
        if f is None:
            continue
        ca, cy = f["inner_arc_center_a_y"]
        off = np.hypot(SX[ri, ci, 0] - ca, SX[ri, ci, 1] - cy) - f["inner_arc_radius_m"]
        t = float(np.clip(off / 2.5, 0, 1))
        col = (int(255 * t), int(60 + 120 * (1 - t)), int(255 * (1 - t)))
        d.rectangle([x - 2, y - 2, x + 2, y + 2], fill=col)
    P = np.array(S.BULGE_DISP)
    d.line([tuple(p) for p in P] + [tuple(P[0])], fill=(250, 210, 0), width=3)
    pim = pim.crop((430, 160, 1030, 520)).resize((1200, 720), Image.LANCZOS)
    sec = Image.open(S.OUT + "/s4_bulge_sections.png")
    sec = sec.resize((1500, int(sec.size[1] * 1500 / sec.size[0])), Image.LANCZOS)
    W = 1200 + 1500 + 60
    H = max(720, sec.size[1]) + 420
    Cv = Image.new("RGB", (W, H), (250, 248, 242))
    dc = ImageDraw.Draw(Cv)
    dc.text((18, 12), "調べ S-2：出っ張り（S8）は主役波のどこで、内の面の弧からどれだけ出ているか", font=font(34, True), fill=(20, 20, 20))
    Cv.paste(pim, (20, 70)); Cv.paste(sec, (1240, 70))
    dc.text((20, 70 + 728), "原画視点の切り出し（粘土）。点 = 出っ張りの多角形（黄）の中で見えている面の、その行の内の面の弧からの出：青 0 m → 赤 2.5 m 以上", font=font(19), fill=(40, 40, 40))
    fl, sl = B["first_layer"], B["second_layer"]
    rr = B["per_row_inner_arc"]
    offs = [p["bulge_offset_from_inner_arc_m"]["p50"] for p in rr]
    lines = [
        "・見えている面（射線の 1 枚目）：%d 本すべてが唇の外の面（頂〜唇の先、列 %.0f〜%.0f）。行 %.0f〜%.0f（c %.1f〜%.1f m）、高さ 0.48〜0.69 H0。" % (
            B["rays"], fl["col"]["min"], fl["col"]["max"], fl["row"]["min"], fl["row"]["max"], fl["c_m"]["min"], fl["c_m"]["max"]),
        "・その奥（2 枚目）：%d 本が唇の下〜角の内の面（列 %.0f〜%.0f）。射線の上の距離は p10 %.2f・p50 %.2f・p90 %.2f m。つまり唇の板が内の面の手前に 1〜2.5 m の厚みで立っている。" % (
            sl["col_band_count"].get("唇の下〜角（内の面）", 0), sl["col"]["p10"], sl["col"]["p90"], sl["gap_along_ray_m"]["p10"], sl["gap_along_ray_m"]["p50"], sl["gap_along_ray_m"]["p90"]),
        "・内の面の弧（その行の列 205〜299 に当てた円）からの出：行ごとの p50 %.1f〜%.1f m、最大 %.1f m。" % (min(offs), max(offs), max(p["bulge_offset_from_inner_arc_m"]["max"] for p in rr)),
        "・原因：c −10〜−6 m（主の頂と b区域の間の移り）で、唇の板が厚く（列 185 で 2.1〜2.7 m、主の頂の行 c −1〜+2 では 0.8〜1.2 m）、外の面が頂から急に下りて棚になる（断面の折れ）。",
        "  原画のカメラは前の低い所（a +45.6 m、y 3 m）から見るので、この棚の外の面がカメラへ向き、内の面の弧の手前に凸の層として見える（重なりの順の誤りではない。行の並びは正しい）。",
        "・c −13.6〜−11 m の行では、唇の外の面が頂の後で一度下がって再び盛り上がる（S 字。b区域の唇の瘤）。これも内の面の弧の外へ出る形で、② の作り直しで扱う。",
    ]
    y = max(720, sec.size[1]) + 130
    for k, t in enumerate(lines):
        dc.text((20, y + 40 * k), t, font=font(22), fill=(30, 30, 30))
    Cv.save(S.OUT + "/s4_D_bulge.png")


def sheet_E(cm, M):
    O = json.load(open(S.OUT + "/s4_obj_numbers.json", encoding="utf-8"))
    cl = O["crest_length"]
    W, H = 2400, 1300
    Cv = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(Cv)
    d.text((18, 12), "調べ S-3：波峰線の向き（c）の長さ：高さの帯ごとの c の幅（主役波 AS02C と参照モデルの数）", font=font(34, True), fill=(20, 20, 20))
    d.text((18, 60), "帯 f：頂の高さが f·H 以上の c の範囲。H は主役波 %.2f m（メッシュの最大）、参照モデル %.2f m。参照モデルは両端が台で切られている（c ±16 m。低い帯の長さは下限）。数だけを描いた（形は描かない）。" % (
        cl["hero_H_m"], cl["ref_H_m"]), font=font(20), fill=(70, 70, 70))
    x0, x1 = 300, 1900
    cmin, cmax = -62.0, 18.0

    def X(c):
        return x0 + (c - cmin) / (cmax - cmin) * (x1 - x0)
    y = 140
    # 行の縛りの帯
    rows = M["rows_painting_view"]
    for e in rows:
        col = (240, 205, 205) if e["painting_px"] == 0 else ((250, 200, 140) if e["outline_segments"] else (190, 205, 225))
        d.rectangle([X(e["c_m"]) - 2, y, X(e["c_m"]) + 2, y + 30], fill=col)
    d.text((20, y + 2), "行の縛り", font=font(22), fill=(30, 30, 30))
    for cv in range(-60, 16, 5):
        d.line([X(cv), y + 32, X(cv), H - 120], fill=(225, 225, 225))
        d.text((X(cv) - 14, H - 112), "%d" % cv, font=font(18), fill=(80, 80, 80))
    d.text((X(-2), H - 84), "c（m）  − が原画視点の左・手前、+ が右・奥", font=font(20), fill=(60, 60, 60))
    y = 200
    for f in ["0.1", "0.2", "0.3", "0.4", "0.5", "0.6", "0.7", "0.8", "0.9"]:
        h = cl["hero_band_extent"].get(f); r = cl["ref_band_extent"].get(f)
        d.text((20, y + 8), "帯 %s H" % f, font=font(22), fill=(30, 30, 30))
        if h:
            d.rectangle([X(h["c_min"]), y, X(h["c_max"]), y + 30], fill=(60, 90, 160))
            d.text((X(h["c_max"]) + 8, y + 2), "主役波 %.1f m（%.2f H）" % (h["length_m"], h["length_over_H"]), font=font(19), fill=(40, 60, 120))
        if r:
            d.rectangle([X(r["c_min"]), y + 36, X(r["c_max"]), y + 60], fill=(200, 120, 60))
            d.text((X(r["c_max"]) + 8, y + 36), "参照 %.1f m（%.2f H）" % (r["length_m"], r["length_over_H"]), font=font(19), fill=(140, 70, 30))
        y += 96
    leg = [("主役波 AS02C", (60, 90, 160)), ("参照モデル（数だけ）", (200, 120, 60)), ("画の外の行（自由）", (240, 205, 205)),
           ("原画の輪郭を作る行", (250, 200, 140)), ("見えるだけの行", (190, 205, 225))]
    x = 20
    for nm, col in leg:
        d.rectangle([x, H - 50, x + 26, H - 24], fill=col)
        d.text((x + 32, H - 54), nm, font=font(20), fill=(30, 30, 30))
        x += 60 + int(d.textlength(nm, font=font(20)))
    Cv.save(S.OUT + "/s4_E_length.png")


if __name__ == "__main__":
    main()
