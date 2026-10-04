# -*- coding: utf-8 -*-
"""美術の見本05 の渡す準備（Q33）：利用者に見せる図（どれも 1920×1080、日本語の見出し）と rules_check_A.json・rules_check_B.json・
metrics.json・run.json を Docs/Evidence/ArtSample05/ へ書く。

使う描画（どれも Git 対象外、描き直さない）：
  見本04 = Build/Polish/sample04/assemble/render/FX1（爪なしの回り台は Build/Polish/sample05/assemble/render/S04_ttnc）
  形 A = Build/Polish/sample05/fix1/assemble/render/A9（爪なしの回り台 A9_ttnc）
  形 B = Build/Polish/sample05/fix1/assemble/render/B10（爪なしの回り台 B10_ttnc）
粘土と層の色づけは as05_clay.py の numpy の z バッファ（Build/Polish/sample05/deliver/clay。Unity の描画ではない。船・爪なし）。
彫刻の写真・写真から作った画像・利用者のマスクと画像は使わない（入れない）。①②③ の範囲は s4_common の多角形の点（原画の画素）から線で、
利用者の切り出しの所は表示の画素の四角（mat_common.T6_CROP）で描き足す。

  as05_1a_painting_view.png   原画視点（爪あり）：原画｜見本04｜形 A｜形 B（①②③ の線）と、左側（③・②・wave4）の拡大
  as05_1b_inner_edge.png      利用者の切り出し（唇の下の内の縁）の 2 倍の拡大：原画｜見本04｜形 A｜形 B
  as05_2a_clay.png            粘土（色なし・爪なし）：見本04｜形 A｜形 B の行、左右の側面・真上・後ろ 65° の列
  as05_2b_clay_turntable.png  粘土の回り台 0°・30°・300°・330°
  as05_2c_layers.png          三つの層の色づけ（側面・真上・回り台）と S11 の読み
  as05_3_material_noclaws.png 平らな塗り・爪なし：座席・座席から波・左右の側面・後ろ 65°・真上（形 A｜形 B を対に）
  as05_4_material_claws.png   同じ 6 視点の爪あり
  as05_5a〜5c_turntable.png   回り台 12 方位（爪あり）：見本04｜形 A｜形 B の行
  as05_6_rules.png            測る規則のまとめ（形 A・形 B）
使い方：py -3.10 -B Tools/GWWaveGen/as05/as05_deliver.py（先に as05_clay.py）
"""
import datetime
import hashlib
import json
import os
import platform
import shutil
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import s5_targets as T  # noqa: E402
import mat_common as M  # noqa: E402

S4 = T.S.S4
REPO = "G:/Unity/GreatWave_2026_Fresh"
P = REPO + "/Unity/Build/Polish"
P5 = P + "/sample05"
R04 = P + "/sample04/assemble/render/FX1"
R04NC = P5 + "/assemble/render/S04_ttnc"
RA = P5 + "/fix1/assemble/render/A9"
RB = P5 + "/fix1/assemble/render/B10"
CLAY = P5 + "/deliver/clay"
OUT = REPO + "/Docs/Evidence/ArtSample05"
W, H = 1920, 1080
FOOT = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし、波頭の爪なし。美術が届いたかは利用者が決める（Q29・Q30）。"
FOOT_NP = "numpy の z バッファの粘土（Unity の描画ではない）。t* = 12 s の静止、爪・船なし。カメラは Unity の描画と同じ視点。美術が届いたかは利用者が決める（Q29・Q30）。"
FOOT_RULES = "測る規則は見本を出す前の自動の確かめで、閉じる条件ではない。目標の値は進行役の既定で、利用者の言葉ではない。美術が届いたかは利用者が決める（Q29・Q30）。"
VIEWJ = {"painting": "原画視点", "seat": "座席（VR の視点）", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面",
         "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
KINDS = (("S04", "見本04", R04), ("A9", "形 A（A9）", RA), ("B10", "形 B（B10）", RB))
RED, GRN, CYN, YEL, MAG = (225, 40, 40), (30, 160, 60), (0, 170, 205), (255, 205, 0), (230, 0, 200)
USED = {}
OUTS = []


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def jl(p):
    USED[p] = None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


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
    d.text((14, 10), title, font=font(28, True), fill=(10, 10, 10))
    if sub:
        y = 50
        for line in sub.split("\n"):
            d.text((14, y), line, font=font(18), fill=(60, 60, 60))
            y += 23
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


def fit(im, w, h):
    s = min(w / im.width, h / im.height)
    r = im.resize((max(1, int(round(im.width * s))), max(1, int(round(im.height * s)))), Image.LANCZOS)
    c = Image.new("RGB", (w, h), (255, 255, 255))
    c.paste(r, ((w - r.width) // 2, (h - r.height) // 2))
    return c


def tag(d, x, y, text, sz=17):
    f = font(sz, True)
    bb = d.textbbox((x, y), text, font=f)
    d.rectangle((bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3), fill=(255, 255, 255))
    d.text((x, y), text, font=f, fill=(10, 10, 10))


def paste(img, d, im, x, y, w, h, lab=None, lab_sz=17):
    img.paste(fit(im, w, h), (x, y))
    d.rectangle((x, y, x + w - 1, y + h - 1), outline=(200, 200, 200))
    if lab:
        tag(d, x + 8, y + 6, lab, lab_sz)


# ---------------------------------------------------------------- 1 原画視点
def painting_disp():
    USED[S4.PAINT] = None
    return Image.fromarray(T.painting_disp())


def regions_disp():
    r = S4.regions_ref()
    return {k: S4.ref_to_disp(r[k]) for k in ("r1", "r2", "r3")}


def outlined(im, regs, w=4, crop=False):
    im = im.copy()
    d = ImageDraw.Draw(im)
    for k, col in (("r1", RED), ("r2", GRN), ("r3", CYN)):
        q = [(float(x), float(y)) for x, y in regs[k]]
        d.line(q + [q[0]], fill=col, width=w, joint="curve")
    x0, y0, x1, y1 = M.T6_CROP
    d.rectangle((x0, y0, x1, y1), outline=MAG, width=3)
    return im


LEFT_BOX = (110, 330, 650, 800)       # 表示の画素：③ の区域（x 157〜419、y 462〜770）・② の左・wave4（④）を含む


def sheet1():
    pd = painting_disp()
    regs = regions_disp()
    srcs = [("原画", pd)] + [(nm, load(r + "/views/painting_t120_claws.png")) for _, nm, r in KINDS]
    img, d = new_sheet("美術の見本05：原画視点（爪あり）　原画｜見本04｜形 A｜形 B",
                       "線：赤 ① 浪尖（頂と唇）・緑 ② b区域（中の出っ張った爪の区域）・水色 ③ 最も左の小さな区域（利用者が確かめた範囲）。桃の四角 = 利用者の切り出し（唇の下の内の縁、T6）\n"
                       "下の段：左側の拡大（③ の区域・② の左の端・左端の青い波 wave4）。同じカメラ・同じ時刻 t*。波頭の爪（浪尖）は出していない（Q33）")
    cw, ch = 470, 264
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        paste(img, d, outlined(im, regs, 5), x, 104, cw, ch, nm, 19)
    x0, y0, x1, y1 = LEFT_BOX
    for k, (nm, im) in enumerate(srcs):
        x = 8 + k * 478
        z = outlined(im, regs, 3).crop(LEFT_BOX)
        paste(img, d, z, x, 404, cw, 409, "%s ／ 左側の拡大" % nm, 18)
    note = ("見方：形 A は ③ を ② の左前の別の小さな波（layer3）にし、一艘目の船を相似で手前へ（倍率 0.7434）。形 B は ②・③ を ① から左下へ下りる段にし、船は動かさない。"
            "\n白い粒（T5）は形 A・形 B とも原画視点で 0（見本04 は 92）。いちばん高い峰（行 c −8 m 以上）は 3 つとも同じ。")
    yy = 830
    for line in note.split("\n"):
        d.text((14, yy), line, font=font(19), fill=(40, 40, 40))
        yy += 27
    finish(img, d, "as05_1a_painting_view.png")

    # 1b 内の縁の拡大
    x0, y0, x1, y1 = M.T6_CROP
    box = (x0 - 30, y0 - 20, x1 + 40, y1 + 20)
    t6 = {k: jl(P5 + "/rules_check_%s.json" % k)["rules"]["T6"] for k in ("A", "B")}
    img, d = new_sheet("美術の見本05：利用者の切り出し（唇の下の内の縁）の 2 倍の拡大　原画｜見本04｜形 A｜形 B（爪あり）",
                       "桃の四角 = 利用者の切り出し（表示の画素 x %d〜%d、y %d〜%d）。ここに白・水色を置かず、藍の面がそのまま縁の線まで来る（Q33、T6）。"
                       "\n切り出しの中の白・水色の割合：見本04 %.2f → 形 A %.2f・形 B %.2f"
                       % (x0, x1, y0, y1, t6["A"]["sample04_painting_crop_pale_share"], t6["A"]["painting_crop_pale_share"], t6["B"]["painting_crop_pale_share"]))
    bw, bh = box[2] - box[0], box[3] - box[1]
    for k, (nm, im) in enumerate(srcs):
        z = im.crop(box).resize((bw * 2, bh * 2), Image.LANCZOS)
        dz = ImageDraw.Draw(z)
        dz.rectangle(((x0 - box[0]) * 2, (y0 - box[1]) * 2, (x1 - box[0]) * 2, (y1 - box[1]) * 2), outline=MAG, width=3)
        x = 40 + k * (bw * 2 + 30)
        img.paste(z, (x, 104))
        tag(d, x + 8, 110, nm, 20)
    finish(img, d, "as05_1b_inner_edge.png")


# ---------------------------------------------------------------- 2 粘土と層
def crop_box(v, labels=(1, 2, 3, 4, 5, 8), margin=0.07):
    xs0, ys0, xs1, ys1 = [], [], [], []
    for k, _, _ in KINDS:
        L = np.load(CLAY + "/%s_%s_labels.npy" % (k, v))
        USED[CLAY + "/%s_%s_labels.npy" % (k, v)] = None
        m = np.isin(L, labels)
        if not m.any():
            continue
        yy, xx = np.nonzero(m)
        xs0.append(xx.min()); xs1.append(xx.max()); ys0.append(yy.min()); ys1.append(yy.max())
    Hh, Ww = 540, 960
    if not xs0:
        return (0, 0, Ww, Hh)
    a, b, c, e = min(xs0), min(ys0), max(xs1), max(ys1)
    w = (c - a) * (1 + 2 * margin); h = (e - b) * (1 + 2 * margin)
    if w / h < 16 / 9:
        w = h * 16 / 9
    else:
        h = w * 9 / 16
    w = min(w, Ww); h = min(h, Hh)
    cx, cy = (a + c) / 2, (b + e) / 2
    x0 = int(np.clip(cx - w / 2, 0, Ww - w)); y0 = int(np.clip(cy - h / 2, 0, Hh - h))
    return (x0, y0, int(x0 + w), int(y0 + h))


def clay_img(kind, v, mode):
    return load(CLAY + "/%s_%s_%s.png" % (kind, v, mode)).crop(crop_box(v))


def sep_text(kind, v):
    src = {"S04": P5 + "/study/baseline_sample04.json", "A9": P5 + "/fix1/assemble/measure/targets_A9.json",
           "B10": P5 + "/fix1/assemble/measure/targets_B10.json"}[kind]
    x = jl(src)["separation_views"].get(v)
    if not x:
        return ""

    def one(pk, lab):
        s = x["pairs"][pk]["separated"]
        return "%s %s" % (lab, "片方が見えない" if s is None else ("分かれる" if s else "続く"))
    return "　".join(one(pk, lab) for pk, lab in (("1-2", "①②"), ("2-3", "②③"), ("1-3", "①③")))


def sep_summary(kind):
    src = {"S04": P5 + "/study/baseline_sample04.json", "A9": P5 + "/fix1/assemble/measure/targets_A9.json",
           "B10": P5 + "/fix1/assemble/measure/targets_B10.json"}[kind]
    s = jl(src)["separation_summary"]
    return "①② %.2f・②③ %.2f・①③ %.2f" % (s["1-2"]["separated_share"], s["2-3"]["separated_share"], s["1-3"]["separated_share"])


def clay_grid(name, title, sub, views, mode, captions=False):
    img, d = new_sheet(title, sub)
    cw, chh = 470, 264
    y0 = 108 if not sub or sub.count("\n") < 2 else 130
    gap = 46 if captions else 36
    for r, (kind, nm, _) in enumerate(KINDS):
        for k, v in enumerate(views):
            x = 8 + k * 478
            y = y0 + r * (chh + gap)
            paste(img, d, clay_img(kind, v, mode), x, y, cw, chh, "%s ／ %s" % (nm, vjname(v)), 18)
            if captions:
                d.text((x + 4, y + chh + 4), sep_text(kind, v), font=font(16, True), fill=(40, 40, 40))
    finish(img, d, name, FOOT_NP)


def sheet2():
    sub_clay = ("色なしの粘土（一つの灰色に固定の光の陰影、黒い線 = 遮る縁）。周りの海は青みの灰。主役波 ＋ 左端の青い波 wave4（形 A は ③ の小さな波 layer3 も）。"
                "\n形だけで三つの層（① 浪尖・② b区域・③ 最も左の小さな区域）が読めるかを見る図。同じ視点・同じカメラ・同じ切り抜き")
    clay_grid("as05_2a_clay.png", "美術の見本05：粘土（色なし・爪なし）　見本04｜形 A｜形 B　左右の側面・真上・後ろ 65°",
              sub_clay, ("side_left", "side_right", "top", "back65"), "clay")
    clay_grid("as05_2b_clay_turntable.png", "美術の見本05：粘土（色なし・爪なし）の回り台　見本04｜形 A｜形 B　0°・30°・300°・330°",
              sub_clay.replace("同じ視点", "回り台は距離 72 m・仰角 16°、0° が原画の側、300°・330° は左（③ の側）から。同じ視点"), ("tt0", "tt30", "tt300", "tt330"), "clay")
    sub = ("層の色づけ：赤 ①・緑 ②・水色 ③・青 wave4 と形 A の layer3 のうち層でない所・灰 ほかの前の面・濃い灰 背。黒い線 = 遮る縁。"
           "\n見本04 は c の帯（② −15.5〜−11.5 m、③ −23〜−17 m）で、形 A・B は形づくりの係の行の印で色を付けた（印の決め方が違うので、色の広さは比べられない）"
           "\n各図の下：S11 の読み（遮る縁か別の塊で分かれる）。15 視点で分かれる割合（基準 0.5）：見本04 %s／形 A %s／形 B %s"
           % (sep_summary("S04"), sep_summary("A9"), sep_summary("B10")))
    clay_grid("as05_2c_layers.png", "美術の見本05：三つの層 ①②③ の色づけ（爪なし）　見本04｜形 A｜形 B",
              sub, ("side_left", "top", "tt300", "tt330"), "tint", captions=True)


# ---------------------------------------------------------------- 3・4 平らな塗りの視点
def sheet34():
    views = ("seat", "seat_toward_wave", "side_left", "side_right", "back65", "top")
    for name, tagw, lab in (("as05_3_material_noclaws.png", "clawfree", "爪なし（形だけを見る）"), ("as05_4_material_claws.png", "claws", "爪あり（面の内 25・近い海 10）")):
        img, d = new_sheet("美術の見本05：平らな塗り（材質 AS05、白い粒なし）・%s　形 A｜形 B を対に" % lab,
                           "左の対と右の対で別の視点。座席は唇の真下の右の船の上（D7）。後ろ 65° は背の一つの山（S4）を見る視点。形 A は一艘目の船を手前へ動かした（倍率 0.7434）")
        cw, chh = 470, 264
        for i, v in enumerate(views):
            r, cpair = divmod(i, 2)
            for j, (kind, nm, root) in enumerate(KINDS[1:]):
                x = 8 + (cpair * 2 + j) * 478 + (8 if cpair else 0)
                y = 100 + r * (chh + 36)
                paste(img, d, load(root + "/views/%s_t120_%s.png" % (v, tagw)), x, y, cw, chh, "%s ／ %s" % (nm, VIEWJ[v]), 18)
        finish(img, d, name)


# ---------------------------------------------------------------- 5 回り台
def sheet5():
    for tg, azs in (("a", (0, 30, 60, 90)), ("b", (120, 150, 180, 210)), ("c", (240, 270, 300, 330))):
        img, d = new_sheet("美術の見本05：回り台（距離 72 m・仰角 16°、爪あり・飛沫なし）　見本04｜形 A｜形 B の行",
                           "方位 %s。0° は原画の側、270°〜330° は左（③ と wave4 の側）から。回り台の画には船を入れていない" % "・".join("%d°" % a for a in azs))
        cw, chh = 470, 264
        for r, (kind, nm, root) in enumerate(KINDS):
            for k, az in enumerate(azs):
                x = 8 + k * 478
                y = 100 + r * (chh + 36)
                paste(img, d, load(root + "/tt/t120_az%03d_claws.png" % az), x, y, cw, chh, "%s ／ %d°" % (nm, az), 18)
        finish(img, d, "as05_5%s_turntable.png" % tg)


# ---------------------------------------------------------------- 6 規則
def vj(v):
    return {"pass": "合", "fail": "否"}.get(v, str(v))


def sheet6():
    ra = jl(P5 + "/rules_check_A.json")["rules"]
    rb = jl(P5 + "/rules_check_B.json")["rules"]
    r3 = jl(P5 + "/fix1/assemble/measure/r3box_white.json")

    def g2(r):
        g = r["G2"]["gates"]
        return "78 %.2f・130 %.2f・131 %.2f・132 %.2f・72 %.2f px" % (g["78"]["claws"], g["130"]["claws"], g["131"]["claws"], g["132_s12"]["claws"], g["72_s12_p95"]["claws"])

    def g1(r):
        n = r["G1"]["surface_stretch_where"]["this_mesh"]["patterned_tri_w_outside"]
        return "伸びの三角形 %d（見本03 の形は 0）。コードと記録の検査は合" % n

    def s11(r):
        s = r["S11"]
        return "must %s。否：%s" % (s["must_pass"], "・".join(s["must_fail_ids"]))

    def t5(r):
        t = r["T5"]
        return "原画視点の白い粒 %d（見本04 %d）。全 32 視点 %d（見本04 %d）" % (t["painting_body_blobs_excluding_boat_edges"], t["sample04_painting_body_blobs"],
                                                                   t["all_views_total"], t["sample04_all_views_total"])

    def t6(r):
        t = r["T6"]
        return "切り出しの白・水色 %.2f（見本04 %.2f）" % (t["painting_crop_pale_share"], t["sample04_painting_crop_pale_share"])

    def c3(r):
        a = r["C3"]["iou_painting_p10_p50_min_sample02"]
        return "爪 35 本、IoU p10・p50・最小 %.3f・%.3f・%.3f" % tuple(a)

    def kb(r):
        return "一艘目の船の画素の比 %.2f（見本04 = 1）" % r["K-boat"]["ratio"]

    rows = [("G1", "投影なし・面の座標の伸びなし", g1), ("G2", "原画視点の輪郭（4 px 以下）", g2),
            ("S4", "背は一つの山", lambda r: "へこみなし"), ("S8", "黄色の線の帯に出っ張りなし", lambda r: "内の面からの距離 p95 0.00 m"),
            ("S9", "左の白は低い・④ は wave4", lambda r: "④ の 98.7% を wave4"), ("S10", "峰に沿う長さ（頂の幅は元のまま）", lambda r: "0.6〜0.9 H の帯は見本04 と差 0.00 m"),
            ("S11", "三つの層を形で分ける", s11), ("T5", "波の本体に白い粒を描かない", t5), ("T6", "切り出しの内の縁に白を置かない", t6),
            ("C2・C3", "爪の水準・位置", c3), ("K-top", "いちばん高い峰は見本04 のまま", lambda r: "行 c −8 m 以上の動き 0 m"), ("K-boat", "一艘目の船を隠さない", kb)]
    img, d = new_sheet("美術の見本05：測る規則のまとめ　形 A（A9）・形 B（B10）",
                       "rules_check_A.json・rules_check_B.json（直しの回 fix1 の後）。S11 の目標の値は進行役の既定で、利用者の言葉ではない")
    xs = (14, 120, 470, 1195)
    y = 92
    for x, t in zip(xs, ("規則", "中身", "形 A（A9）", "形 B（B10）")):
        d.text((x, y), t, font=font(19, True), fill=(0, 0, 0))
    y += 30
    for rid, what, fn in rows:
        key = "C3" if rid == "C2・C3" else rid
        va, vb = ra[key]["verdict"], rb[key]["verdict"]
        d.line((14, y - 3, W - 14, y - 3), fill=(220, 220, 220))
        d.text((xs[0], y), rid, font=font(17, True), fill=(0, 0, 0))
        d.text((xs[1], y), what, font=font(16), fill=(30, 30, 30))
        for x, v, r in ((xs[2], va, ra), (xs[3], vb, rb)):
            col = (0, 120, 40) if v == "pass" else (200, 30, 30)
            d.text((x, y), vj(v), font=font(17, True), fill=col)
            d.text((x + 34, y), fn(r)[:72], font=font(16), fill=(30, 30, 30))
        y += 31
    y += 14
    d.text((14, y), "S11 の項目（目標は進行役の既定）", font=font(19, True), fill=(0, 0, 0))
    y += 30
    items = [("L1-2", "② の突出（m）", "0.6 以上"), ("L1-3", "③ の突出（m）", "1.0 以上"), ("L2-2", "② の峰が鞍より前（m）", "1.5 以上"),
             ("L2-3", "③ の峰が鞍より前（m）", "2.0 以上"), ("L6-sep", "15 視点の分かれ ①②・②③", "0.5 以上"), ("L6-label", "原画視点の層の印 ①・②・③", "0.6 以上"),
             ("P1-top", "③ の上の帯の色", "藍 0.10〜0.40 ほか"), ("P1-mid", "③ の中の帯 白＋水色", "0.20〜0.60"), ("P1-cells", "③ の升の色の並び", "差 0.28 以下・相関 0.45 以上"),
             ("P2-top", "② の上の帯の色", "藍 0.10〜0.40・水色 0.10 以上")]
    xs2 = (14, 130, 480, 760, 1290)
    for x, t in zip(xs2, ("項目", "中身", "目標", "形 A", "形 B")):
        d.text((x, y), t, font=font(18, True), fill=(0, 0, 0))
    y += 28

    def val(r, k):
        t = r["S11"]["targets"].get(k)
        if not t:
            return "—", None
        v = t.get("value")
        if isinstance(v, dict):
            s = "・".join("%s" % (round(x, 3) if isinstance(x, float) else x) for x in v.values())
        elif isinstance(v, list):
            s = "・".join("%s" % (round(x, 3) if isinstance(x, float) else x) for x in v)
        elif isinstance(v, float):
            s = "%.3g" % v
        else:
            s = str(v)
        return s, t.get("pass")
    for k, what, goal in items:
        d.text((xs2[0], y), k, font=font(16, True), fill=(0, 0, 0))
        d.text((xs2[1], y), what, font=font(16), fill=(30, 30, 30))
        d.text((xs2[2], y), goal, font=font(16), fill=(30, 30, 30))
        for x, r in ((xs2[3], ra), (xs2[4], rb)):
            s, ok = val(r, k)
            col = (0, 120, 40) if ok else (200, 30, 30)
            d.text((x, y), ("合 " if ok else "否 ") + s[:60], font=font(16, True if not ok else False), fill=col)
        y += 27
    y += 10
    ra3 = r3.get("A9", {}).get("ratio") if isinstance(r3.get("A9"), dict) else None
    d.text((14, y), "批評の目安：③ の区域の中の白 ÷ 原画の枠の左の外の白（目標 2 以上）　形 A 0.97 → 2.86、形 B 3.47 → 3.75（直す前 → 直し、fix1/assemble/measure/r3box_white.json）",
           font=font(17), fill=(40, 40, 40))
    finish(img, d, "as05_6_rules.png", FOOT_RULES)


# ---------------------------------------------------------------- JSON
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def rel(p):
    return p.replace(REPO + "/", "")


def write_json():
    os.makedirs(OUT, exist_ok=True)
    for k in ("A", "B"):
        shutil.copyfile(P5 + "/rules_check_%s.json" % k, OUT + "/rules_check_%s.json" % k)
        USED[P5 + "/rules_check_%s.json" % k] = None
    m = {"schema": "GreatWave.AS05.metrics/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
         "note_ja": "美術の見本05（Q33）の主な数。形 A = A9、形 B = B10（直しの回 fix1 の後）。目標の値は進行役の既定で、利用者の言葉ではない。美術が届いたかは利用者が決める",
         "variants": {}}
    for k, nm in (("A", "A9"), ("B", "B10")):
        r = jl(P5 + "/rules_check_%s.json" % k)
        rr = r["rules"]
        g = rr["G2"]["gates"]
        m["variants"][k] = {
            "render": nm, "summary": r["summary"],
            "G1_patterned_tri_w_outside": rr["G1"]["surface_stretch_where"]["this_mesh"]["patterned_tri_w_outside"],
            "G2_gates_px": {x: g[x]["claws"] for x in ("78", "130", "131", "132_s12", "72_s12_p95")},
            "S11_must_pass": rr["S11"]["must_pass"], "S11_must_fail_ids": rr["S11"]["must_fail_ids"],
            "S11_targets": {t: {"value": v.get("value"), "pass": v.get("pass"), "kind": v.get("kind")} for t, v in rr["S11"]["targets"].items()},
            "T5_painting_body_blobs": rr["T5"]["painting_body_blobs_excluding_boat_edges"], "T5_all_views_total": rr["T5"]["all_views_total"],
            "T5_sample04_painting": rr["T5"]["sample04_painting_body_blobs"], "T5_sample04_all_views": rr["T5"]["sample04_all_views_total"],
            "T6_crop_pale_share": rr["T6"]["painting_crop_pale_share"], "T6_sample04": rr["T6"]["sample04_painting_crop_pale_share"],
            "C3_iou_p10_p50_min": rr["C3"]["iou_painting_p10_p50_min_sample02"], "K_boat_ratio": rr["K-boat"]["ratio"]}
    m["separation_15views"] = {}
    for kind, src in (("S04", P5 + "/study/baseline_sample04.json"), ("A9", P5 + "/fix1/assemble/measure/targets_A9.json"),
                      ("B10", P5 + "/fix1/assemble/measure/targets_B10.json")):
        m["separation_15views"][kind] = jl(src)["separation_summary"]
    m["critic_r3box_white_ratio"] = {"A": {"before_A5": 0.97, "fix_A9": 2.86}, "B": {"before_B6": 3.47, "fix_B10": 3.75},
                                     "source": "Unity/Build/Polish/sample05/fix1/assemble/measure/r3box_white.json"}
    USED[P5 + "/fix1/assemble/measure/r3box_white.json"] = None
    m["clay_report"] = rel(CLAY + "/clay_report.json")
    with open(OUT + "/metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(m, f, ensure_ascii=False, indent=1)
    tools = [HERE + "/as05_deliver.py", HERE + "/as05_clay.py"]
    run = {"schema": "GreatWave.AS05.deliver_run/1", "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
           "note_ja": "Docs/Evidence/ArtSample05 の図と JSON を作った記録。描画は描き直していない（Git 対象外の Build/Polish の描画を並べた）。粘土と層は numpy の z バッファ",
           "commands": ["py -3.10 -B Tools/GWWaveGen/as05/as05_clay.py", "py -3.10 -B Tools/GWWaveGen/as05/as05_deliver.py"],
           "python": platform.python_version(), "numpy": np.__version__,
           "tools": {rel(p): sha(p) for p in tools},
           "upstream_runs": {rel(p): sha(p) for p in (P5 + "/fix1/assemble/run.json", P5 + "/assemble/run.json", P5 + "/mat/run.json",
                                                       P5 + "/shapeA/run.json", P5 + "/shapeB/run.json") if os.path.isfile(p)},
           "inputs": {rel(p): sha(p) for p in sorted(USED) if os.path.isfile(p)},
           "outputs": {rel(p): sha(p) for p in OUTS + [OUT + "/metrics.json", OUT + "/rules_check_A.json", OUT + "/rules_check_B.json"]},
           "not_in_docs_ja": "彫刻の写真・写真から作った画像・利用者の画像とマスクは入れていない。①②③ の範囲は多角形の線だけ"}
    with open(OUT + "/run.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(run, f, ensure_ascii=False, indent=1)
    print("JSON done", flush=True)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else "all"
    if only in ("all", "1"):
        sheet1()
    if only in ("all", "2"):
        sheet2()
    if only in ("all", "34"):
        sheet34()
    if only in ("all", "5"):
        sheet5()
    if only in ("all", "6"):
        sheet6()
    if only == "all":
        write_json()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
