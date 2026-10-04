# -*- coding: utf-8 -*-
"""美術の見本04 の組み立て（Q32）：並べ図（1920 幅、日本語の見出し）。Unity の描画（asm4_render.sh の S04）を、見本02・見本03 V2 の描画（同じ視点・
同じカメラ。描き直さず、前の描画をそのまま使う）と並べる。測る規則の図は rules_check.json と asm4_rules.py の測り（assemble/measure）から。
  asm4_1_painting.png         原画視点：原画｜見本02｜見本03 V2｜見本04
  asm4_2_painting_zoom.png    原画視点の拡大：左（④ と白）・出っ張りの所（利用者の黄色の線を描き足す）。原画｜見本03 V2｜見本04
  asm4_3a_views.png・3b       座席・座席から波・左の側面／右の側面・後ろ 65°・真上（行：見本02・見本03 V2・見本04）
  asm4_4a_crest_orbit.png・4b 波頭の回り台 8 方位（行：見本02・見本03 V2・見本04）
  asm4_5a_turntable.png・5b   回り台 12 方位（行：見本02・見本03 V2・見本04）
  asm4_6_outline_owner.png    S9：原画視点の輪郭の画素を作る物（主役波・wave4・近い海）と、Unity の描画の wave4 あり・なしの差
  asm4_7a_layers.png・7b      S11：三つの層の色づけ（numpy の粘土。左右の側面・真上・回り台 12 方位。見本03 の形｜見本04）
  asm4_8_numbers.png          測る規則のまとめ
使い方：py -3.10 -B Tools/GWWaveGen/as04/asm4_sheets.py
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "as03"))
import asm4_common as A  # noqa: E402
import asm_sheets as AS  # noqa: E402

P = A.P
R04 = A.ASM + "/render/S04"
R03 = P + "/sample03/fix01/render/V2"
R02V = P + "/sample02/fix01/assemble/render/AS02C_A"
R02C = P + "/sample03/study/render/S3_AS02C_crest2"
A4H = A.P4 + "/shape/render/A4"
OUTD = A.ASM + "/sheets"
PAINT = AS.PAINT
AS.FOOT = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし。美術が届いたかは利用者が決める（Q29・Q30）。"
VN = {"S02": "見本02（K*′ AS02C・見本 A の材質）", "S03": "見本03 V2（冠 OUT・彫りの面・平らな色）", "S04": "見本04（AS04 ＋ ④ の青い波・平らな塗り）"}
if A.FIX:
    # 直しの回：列を「見本03 V2｜見本04（直す前）｜見本04 直しの回 1」に替える（同じ視点・同じカメラ。前の描画をそのまま使う）
    R02V = R03; R02C = R03
    R03 = A.ASM + "/render/S04"
    R04 = A.ASM + "/render/" + A.RTAG
    A4H = A.ASM + "/render/" + A.RTAG + "H"
    OUTD = A.ASM + "/sheets_" + A.FIX
    VN = {"S02": "見本03 V2（冠 OUT・彫りの面・平らな色）", "S03": "見本04 直す前（組み立ての S04）", "S04": "見本04 直しの回 1（②③ の湾・白の印・白い点）"}


def T_(t):
    """直しの回では見出しの列の名前を替える（見本02 → 見本03 V2、見本03 V2 → 見本04 直す前、見本04 → 見本04 直しの回 1）。"""
    if not A.FIX:
        return t
    t = t.replace("見本04：主役波 K*′ AS04（出っ張りを直し、左の白を下げ、左の尾を詰めた）", "@@N：主役波 K*′ AS04F（AS04 に ② と ③ の間の湾を足した）、白の印（湾の床を白に・唇の下の歯の列をならした）、白い点（AS04F）")
    t = t.replace("見本03 V2", "@@B").replace("見本02", "見本03 V2").replace("見本04", "@@N")
    return t.replace("@@B", "見本04 直す前").replace("@@N", "見本04 直しの回 1")


def _sheet(*a, **k):
    return AS.sheet(*[T_(x) if isinstance(x, str) and not x.endswith(".png") else x for x in a], **k)
VIEWJ = AS.VIEWJ
AZJ = AS.AZJ
YEL = (255, 214, 0)


def vpath(v, sub, name):
    if v == "S02":
        return (R02C if sub == "crest" else R02V) + "/%s/%s" % (sub, name)
    return {"S03": R03, "S04": R04}[v] + "/%s/%s" % (sub, name)


def sheet1():
    cells = [(PAINT, "原画 DP130155（メトロポリタン美術館の公開の画像）", None)]
    cells += [(vpath(v, "views", "painting_t120_claws.png"), VN[v], None) for v in ("S02", "S03", "S04")]
    return _sheet("美術の見本04：原画視点（t*）　原画｜見本02｜見本03 V2｜見本04", cells, 2, 960, 540, OUTD + "/asm4_1_painting.png",
                    "見本04：主役波 K*′ AS04（出っ張りを直し、左の白を下げ、左の尾を詰めた）＋ 左端の別の小さな青い波（④）＋ 平らな塗り（冠・彫りなし）＋ 爪 35 本")


def draw_poly(img, pts, col=YEL, w=4):
    d = ImageDraw.Draw(img)
    pts = [tuple(map(float, p)) for p in pts]
    d.line(pts + [pts[0]], fill=col, width=w)


def crop_pair(path, box_disp, poly_disp, is_paint=False):
    """表示の画素の枠 box_disp を、原画なら原画の画素へ直して切り出し、黄色の線を描く。"""
    im = Image.open(path).convert("RGB")
    if is_paint:
        sx = im.width / 3859.0
        b = A.px_to_ref(np.array([[box_disp[0], box_disp[1]], [box_disp[2], box_disp[3]]], float), 1) * sx
        b[:, 0] = np.clip(b[:, 0], 0, im.width); b[:, 1] = np.clip(b[:, 1], 0, im.height)
        pr = [A.px_to_ref(np.array([p], float), 1)[0] * sx for p in poly_disp]
        draw_poly(im, pr, w=max(3, int(4 * sx * 2.4)))
        return im.crop(tuple(int(round(x)) for x in b.ravel()))
    draw_poly(im, poly_disp, w=3)
    return im.crop(box_disp)


def sheet2():
    p4 = A.ref_to_px(np.array(A.S4.REG4, float), 1)
    pb = np.array(A.S4.BULGE_DISP, float)
    rows = [((157, 300, 757, 700), p4, "左（④ の輪郭と、下へ押された白）"), ((480, 180, 980, 480), pb, "頂の下・唇の左の帯（出っ張り S8）")]
    W, H = 1920, 96 + 2 * 470 + 40
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), T_("原画視点の拡大：利用者の黄色の線（Q32-3）の所　原画｜見本03 V2｜見本04"), font=AS.font(30, True), fill=(10, 10, 10))
    d.text((14, 56), "黄色の線は利用者が描いた所（④：輪郭線の最も左の短い一区間＝左端の小さな青い波の上の縁、出っ張り：内側の面の帯）。見本の画の上に同じ位置で描き足した",
           font=AS.font(19), fill=(60, 60, 60))
    for r, (box, poly, ja) in enumerate(rows):
        srcs = [(PAINT, True, "原画"), (vpath("S03", "views", "painting_t120_claws.png"), False, "見本03 V2"),
                (vpath("S04", "views", "painting_t120_claws.png"), False, "見本04")]
        for k, (p, ip, lab) in enumerate(srcs):
            c = crop_pair(p, box, poly, ip)
            c = AS.fit(c, 636, 466)
            img.paste(c, (k * 640 + 2, 96 + r * 470))
            AS.label(d, k * 640 + 12, 96 + r * 470 + 8, "%s ／ %s" % (lab if lab == "原画" else T_(lab), ja), 18)
    d.text((14, H - 32), AS.FOOT, font=AS.font(18), fill=(70, 70, 70))
    os.makedirs(OUTD, exist_ok=True)
    img.save(OUTD + "/asm4_2_painting_zoom.png")
    return OUTD + "/asm4_2_painting_zoom.png"


def sheet3():
    out = []
    for tag, views in (("a", ("seat", "seat_toward_wave", "side_left")), ("b", ("side_right", "back65", "top"))):
        cells = []
        for v in ("S02", "S03", "S04"):
            for vw in views:
                cells.append((vpath(v, "views", "%s_t120_claws.png" % vw), "%s ／ %s" % (VIEWJ[vw], VN[v].split("（")[0]), None))
        out.append(_sheet("原画視点のほかの視点（行：見本02・見本03 V2・見本04）：" + "・".join(VIEWJ[x] for x in views), cells, 3, 640, 360,
                            OUTD + "/asm4_3%s_views.png" % tag))
    return out


def sheet4():
    out = []
    for tag, azs in (("a", (0, 45, 90, 135)), ("b", (180, 225, 270, 315))):
        cells = []
        for v in ("S02", "S03", "S04"):
            for az in azs:
                cells.append((vpath(v, "crest", "t120_az%03d_claws.png" % az), "%s ／ 方位 %s" % (VN[v].split("（")[0], AZJ[az]), (240, 135, 1680, 945)))
        out.append(_sheet("波頭の回り台（中心 (−6.63, 16.5, −3.27)・距離 34 m・仰角 5°）　行：見本02・見本03 V2・見本04", cells, 4, 480, 270,
                            OUTD + "/asm4_4%s_crest_orbit.png" % tag))
    return out


def sheet5():
    out = []
    for tag, azs in (("a", range(0, 180, 30)), ("b", range(180, 360, 30))):
        cells = []
        for v in ("S02", "S03", "S04"):
            for az in azs:
                cells.append((vpath(v, "tt", "t120_az%03d_claws.png" % az), "%s ／ %d°" % (VN[v].split("（")[0], az), None))
        out.append(_sheet("回り台（距離 72 m・仰角 16°、爪あり・飛沫なし、周りの海あり）　行：見本02・見本03 V2・見本04", cells, 6, 320, 180,
                            OUTD + "/asm4_5%s_turntable.png" % tag))
    return out


OWN_RGB = {"hero": (230, 40, 40), "wave4": (40, 90, 255), "sea": (30, 170, 60), "claw": (255, 140, 0)}


def sheet6():
    rc = A.jl(A.P4 + "/rules_check.json")["rules"]["S9"]
    z = np.load(A.MEAS + "/s9_painting_owner_x2.npz")
    L, top, topown = z["L"], z["top"], z["topown"]
    base = Image.open(R04 + "/views/painting_t120_claws.png").convert("RGB").resize((3840, 2160), Image.LANCZOS)
    arr = np.asarray(base).copy()
    for x in range(L.shape[1]):
        if top[x] < 0:
            continue
        o = int(topown[x])
        name = "hero" if o in (1, 2, 3, 4, 8) else {5: "wave4", 6: "sea", 7: "claw"}.get(o)
        if name:
            arr[max(top[x] - 5, 0):top[x] + 6, x] = OWN_RGB[name]
    im = Image.fromarray(arr)
    d = ImageDraw.Draw(im)
    segs = A.S4.outline_segments()
    for sid in ("78", "130", "131", "132"):
        for p in A.ref_to_px(segs[sid], 2)[::8]:
            d.ellipse((p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2), fill=(0, 0, 0))
    p4 = A.ref_to_px(np.array(A.S4.REG4, float), 2)
    draw_poly(im, p4, w=6)
    full = im.resize((1920, 1080), Image.LANCZOS)
    zoom = im.crop((0, 560, 1400, 1300))
    # Unity：wave4 なし（形づくりの A4）とあり（S04）の左の切り出し、差の画素
    dm = np.load(A.MEAS + "/s9_unity_diff_mask.npy")
    a4 = Image.open(A4H + "/views/painting_t120_claws.png").convert("RGB")
    s4 = np.asarray(Image.open(R04 + "/views/painting_t120_claws.png").convert("RGB")).copy()
    s4d = s4.copy(); s4d[dm] = (0.4 * s4d[dm] + 0.6 * np.array([255, 0, 255])).astype(np.uint8)
    box = (0, 280, 700, 660)
    W, H = 1920, 100 + 540 + 10 + 330 + 40
    img = Image.new("RGB", (W, H), (255, 255, 255))
    dd = ImageDraw.Draw(img)
    dd.text((14, 12), "S9：原画視点の輪郭を作る物（赤＝主役波・青＝④ の別の青い波 wave4・緑＝近い海、黒い点＝原画の輪郭の真値、黄色＝利用者の ④）", font=AS.font(26, True), fill=(10, 10, 10))
    r78 = rc["per_segment"]["78"]
    sub = "区間 78 の x が 360 未満（④）の真値の点の持ち主：%s／360 以上：%s。numpy の z バッファ（表示の 2 倍）。下の段：Unity の描画 wave4 なし｜あり｜差の画素（桃色）" % (
        "・".join("%s %.0f%%" % (k, 100 * v) for k, v in r78["region4_x_lt_360"]["owner_share"].items()),
        "・".join("%s %.0f%%" % (k, 100 * v) for k, v in r78["x_ge_360"]["owner_share"].items()))
    dd.text((14, 56), sub, font=AS.font(19), fill=(60, 60, 60))
    img.paste(AS.fit(full, 956, 538), (2, 100))
    img.paste(AS.fit(zoom, 956, 538), (962, 100))
    AS.label(dd, 12, 108, "全体", 18); AS.label(dd, 972, 108, "左の拡大（④ の所）", 18)
    y2 = 100 + 540 + 10
    for k, (im2, lab) in enumerate(((a4, "Unity：wave4 なし（主役波 AS04 だけ、形づくりの A4）"), (Image.fromarray(s4), "Unity：wave4 あり（見本04）"),
                                    (Image.fromarray(s4d), "差の画素（桃色）＝ wave4 が見える所"))):
        c = im2.crop(box)
        img.paste(AS.fit(c, 636, 326), (k * 640 + 2, y2))
        AS.label(dd, k * 640 + 12, y2 + 6, lab, 17)
    dd.text((14, H - 32), AS.FOOT, font=AS.font(18), fill=(70, 70, 70))
    img.save(OUTD + "/asm4_6_outline_owner.png")
    return OUTD + "/asm4_6_outline_owner.png"


def sheet7():
    out = []
    leg = "層の色：赤 ①浪尖（主の頂と唇、c −2〜+8 m）・緑 ② b区域の房（c −15.5〜−11.5）・水色 ③ 最左側の小さな房（c −23〜−17。どれも頂より前で高さ 0.25 H0 以上）・灰 ほかの前の面・濃い灰 背・青 wave4・淡い色 近い海。黒い線＝遮る縁（深さの跳び）"
    cells = []
    for kind, ja in (("S03", "見本03 の形（AS02C）"), ("S04", "見本04（AS04 ＋ wave4）")):
        for v in ("side_left", "side_right", "top"):
            cells.append((A.MEAS + "/s11/%s_%s.png" % (kind, v), "%s ／ %s" % (VIEWJ[v], ja), None))
    out.append(_sheet("S11：三つの層の色づけ（numpy の粘土、Unity の描画ではない）　行：見本03 の形・見本04", cells, 3, 640, 360, OUTD + "/asm4_7a_layers.png", leg))
    cells = []
    for kind, ja in (("S03", "見本03 の形"), ("S04", "見本04")):
        for az in range(0, 360, 30):
            cells.append((A.MEAS + "/s11/%s_tt%d.png" % (kind, az), "%s ／ %d°" % (ja, az), None))
    out.append(_sheet("S11：回り台 12 方位の層の色づけ（numpy の粘土）　上 2 段：見本03 の形、下 2 段：見本04", cells, 6, 320, 180, OUTD + "/asm4_7b_layers_turntable.png", leg))
    return out


def sheet8():
    rc = A.jl(A.P4 + "/rules_check.json")
    r = rc["rules"]
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), "美術の見本04：測る規則の自動の確かめ（Unity/Build/Polish/sample04/rules_check.json）", font=AS.font(30, True), fill=(10, 10, 10))
    f, fb = AS.font(20), AS.font(20, True)
    g = r["G2"]["gates"]
    s8 = r["S8"]; s9 = r["S9"]; s10 = r["S10"]; s11 = r["S11"]; t4 = r["T4"]; s4 = r["S4"]
    rat = s10["ratio_vs_sample03"]
    lines = [
        ("G1 投影なし", r["G1"]["verdict"], ("シェーダー 2 つは調べ M の版から白い点だけを直した写し（AS04F）、" if A.FIX else "シェーダー 2 つは調べ M の版のまま、") + "描画の道具は見本03 の版のまま、冠なし。模様の面の |∇w| の外の三角形 %d（見本03 の形 %d）" % (
            r["G1"]["surface_stretch_front"]["AS04_hero"]["patterned_face"]["gw_tri_outside_1_3_to_3x"], r["G1"]["surface_stretch_front"]["AS02C_smooth_sample03_shape"]["patterned_face"]["gw_tri_outside_1_3_to_3x"])),
        ("G2 原画視点の輪郭", r["G2"]["verdict"], "合わせた輪郭（主役波＋wave4）：78 %.2f・130 %.2f・131 %.2f・132 σ12 %.2f・72 σ12 p95 %.2f px（4 以下）。主役波だけでは 78 %s" % (
            g["78"]["claws"], g["130"]["claws"], g["131"]["claws"], g["132_s12"]["claws"], g["72_s12_p95"]["claws"], (("%.2f" % r["G2"]["hero_only_A4_record"]["78"]) if "78" in r["G2"]["hero_only_A4_record"] else "（直しの回では測っていない）"))),
        ("S4 背は一つの山", s4["verdict"], "合わせた H(c) のへこみ（c が −14 以上）%.3f m、後ろからの輪郭のへこみ b65・b90・b115 %s px（1 以下）" % (
            s4["H_of_c"]["union_hero_wave4"]["window_c_ge_-14"]["dip_depth"], "・".join(str(v["AS04_union"]["dip_px_window_c_ge_-14"]) for v in s4["silhouette_from_behind"].values()))),
        ("S8 出っ張り", s8["verdict"], "黄色の線の中の射線の当たりの、内の面の線からの距離 p95：見本03 の形 %.2f m → 見本04 %.2f m（0.15 以下）。内の面に当たる割合 %.2f" % (
            s8["AS02C_sample03_shape"]["dev_from_inner_face_m"]["p95"], s8["AS04"]["dev_from_inner_face_m"]["p95"], s8["AS04"]["first_hit_inner_face_share"])),
        ("S9 左の白・④", s9["verdict"], "④ の真値の点の持ち主 %s。白の頂点 c < −12.6 m：見本03 の形 %d → %d、白の最も左の c %.1f → %.1f m" % (
            "・".join("%s %.0f%%" % (k, 100 * v) for k, v in s9["per_segment"]["78"]["region4_x_lt_360"]["owner_share"].items()),
            s9["white_part"]["AS02C_sample03_shape"]["white_vertices_c_lt_-12.6"], s9["white_part"]["AS04"]["white_vertices_c_lt_-12.6"],
            s9["white_part"]["AS02C_sample03_shape"]["leftmost_white_c_m"], s9["white_part"]["AS04"]["leftmost_white_c_m"])),
        ("S10 峰に沿う長さ", s10["verdict"], "見本03 に対する比（合わせた形）0.1 H %.2f・0.3 H %.2f・0.5 H %.2f・0.7 H %.2f・0.9 H %.2f（主役波だけ 0.1 H %.2f・0.5 H %.2f）" % (
            rat["0.1"]["union"], rat["0.3"]["union"], rat["0.5"]["union"], rat["0.7"]["union"], rat["0.9"]["union"], rat["0.1"]["hero_only"], rat["0.5"]["hero_only"])),
        ("S11 三つの層", s11["verdict"], "分かれて読める視点の割合（両方見える視点の中）：①② %s・②③ %s・①③ %s（見本03 の形 ①② %s・②③ %s）" % tuple(
            str(s11["summary"][k][pk]["separated_share"]) for k, pk in (("AS04_union", "1-2"), ("AS04_union", "2-3"), ("AS04_union", "1-3"), ("AS02C_sample03_shape", "1-2"), ("AS02C_sample03_shape", "2-3")))),
        ("T4 冠なし・凹凸なし", t4["verdict"], "冠のメッシュなし。主役波の点の滑らかな土台からのずれの最大 %.4f m（見本03 の彫りの面 %.3f m）。wave4 は解析の面" % (
            t4["relief_vs_smooth_base"]["AS04_hero_in_union"]["max_dev_m"], t4["relief_vs_smooth_base"]["sample03_relief_b1v2c（V1・V2・V3 の面）"]["max_dev_m"])),
        ("C2 爪の水準", r["C2"]["verdict"], "35 本（面の内 25・近い海 10）。置き直しは原画のカメラを中心とする相似（倍率 %s）なので形の比は見本02 のまま。不合 %d 本" % (
            "〜".join(str(x) for x in r["C2"]["scale_range_face_interior"]), r["C2"]["fail"])),
        ("C3 マスクとの重なり", r["C3"]["verdict"], "面の内 25 本の原画視点の影は画素まで同じ。IoU p10・p50・最小 %s。原画視点で見える割合 p10・p50・最小 %s（見本03 %s）" % (
            "・".join(str(x) for x in r["C3"]["iou_painting_p10_p50_min_sample02"]), "・".join(str(x) for x in r["C3"]["painting_visible_frac_p10_p50_min"]["S04"]),
            "・".join(str(x) for x in r["C3"]["painting_visible_frac_p10_p50_min"]["S03"]))),
    ]
    wed = [w for w in s9["wedge_lower_edge"] if w["too_high_px"] is not None]
    st = r["G1"]["surface_stretch_front"]["AS04_hero"]
    geo = s11["geometry_steps"]["AS04"]["steps"]; geo0 = s11["geometry_steps"]["AS02C_sample03_shape"]["steps"]
    cl = [e for e in rc["claws_per_claw"] if e["role"] == "FACE_INTERIOR"]
    up = sorted([e for e in cl if abs(e["moved_m"]) > 0.01], key=lambda e: -(e["surface_S04"]["max_above_surface_m"] - e["surface_S03"]["max_above_surface_m"]))[:4]
    lines += [
        ("記録", "", "（ここから下は判定に使わない記録）"),
        ("④ の楔の厚み", "", "wave4 の見える下の縁（＝主役波の白の上の縁）は原画の楔の下の縁より x 0〜260 で %.0f〜%.0f 原画画素高い（楔が細い）。x 276〜340 では %.0f〜%.0f" % (
            min(w["too_high_px"] for w in wed if w["x_ref"] <= 260), max(w["too_high_px"] for w in wed if w["x_ref"] <= 260),
            min(w["too_high_px"] for w in wed if w["x_ref"] > 260), max(w["too_high_px"] for w in wed if w["x_ref"] > 260))),
        ("峰に沿う長さ 0.5 H", "", "主役波だけでは 0.85 倍だが、wave4 の頂（0.56〜0.61 H0）が c −20.3 m まで続くので、合わせた形では %.2f 倍（%.1f m）" % (
            rat["0.5"]["union"], s10["AS04_union_hero_wave4"]["0.5"]["width_m"])),
        ("層の形の段", "", "①②の間の湾：前の縁が ① より %.1f m・② より %.1f m 下がる（見本03 の形 %.1f・%.1f）。② − ③ の頂 %.2f H0（%.2f）、③ の前の縁は ② より %.1f m 後ろ（%.1f）" % (
            geo["r1_front_minus_bay_m"], geo["r2_front_minus_bay_m"], geo0["r1_front_minus_bay_m"], geo0["r2_front_minus_bay_m"],
            geo["r2_crest_minus_r3_crest_over_H0"], geo0["r2_crest_minus_r3_crest_over_H0"], -geo["r3_front_minus_r2_front_m"], -geo0["r3_front_minus_r2_front_m"])),
        ("面の座標の伸び", "", "白（模様なし）の面で |∇w| が外 %d 三角形（唇を短くした所の左の端）、模様の面で |∇u| が外 %d 三角形（c −0.2〜+0.95 m の巻きの内の細い帯。白い点の格子だけ）" % (
            st["white_face"]["gw_tri_outside_1_3_to_3x"], st["patterned_face"]["gu_tri_outside_1_3_to_3x"])),
        ("爪の浮き", "", "置き直した爪（動いた 17 本）で面からの出が最も増えたもの：" + "・".join("%s %.2f m（前 %.2f）" % (e["user_id"], e["surface_S04"]["max_above_surface_m"], e["surface_S03"]["max_above_surface_m"]) for e in up)),
        ("関門 78 の食い違い", "", "wave4 の作りの記録の 78 2.9185 px は古い判定のファイル（18:29 の途中の版）の値。組み立てで測り直すと 1.61 px（同じ画）"),
    ]
    y = 80
    for name, v, txt in lines:
        d.text((14, y), name, font=fb, fill=(0, 0, 0))
        if v:
            d.text((300, y), "合" if v == "pass" else "不合", font=fb, fill=(0, 110, 0) if v == "pass" else (180, 0, 0))
        # 折り返し
        x0, maxw = 380, W - 400
        cur = ""
        for ch in txt:
            if d.textlength(cur + ch, font=f) > maxw:
                d.text((x0, y), cur, font=f, fill=(30, 30, 30)); y += 28; cur = ch
            else:
                cur += ch
        d.text((x0, y), cur, font=f, fill=(30, 30, 30))
        y += 44
    d.text((14, H - 60), "測る規則を通るかだけ。美術が届いたかは利用者が決める（Q29・Q30）。S11 の分かれの読みは numpy の粘土の代わりの測りで、判定の基準は進行役の既定。", font=AS.font(19), fill=(60, 60, 60))
    d.text((14, H - 32), AS.FOOT, font=AS.font(18), fill=(70, 70, 70))
    img.save(OUTD + "/asm4_8_numbers.png")
    return OUTD + "/asm4_8_numbers.png"


def main():
    os.makedirs(OUTD, exist_ok=True)
    out = [sheet1(), sheet2()] + sheet3() + sheet4() + sheet5() + [sheet6()] + sheet7() + [sheet8()]
    rec = {p.replace(A.REPO + "/", ""): A.sha(p) for p in out}
    A.jdump(OUTD + "/sheets.json", {"sheets_sha256": rec,
                                     "inputs_ja": "描画：組み立て S04（Build/Polish/sample04/assemble/render/S04）、見本03 V2（sample03/fix01/render/V2）、見本02（sample02/fix01/assemble/render/AS02C_A、波頭の回り台は sample03/study/render/S3_AS02C_crest2）。同じ視点・同じカメラ"})
    for p in out:
        print(p)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
