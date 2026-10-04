# -*- coding: utf-8 -*-
"""美術の見本03 の作り B1-5：冠の粘土の描画（Blender Workbench）を、S1 の数と並べた図にする（1920×1080、日本語の見出し）。
- b1_1_views_<mode>.png：原画視点・原画視点の頂の拡大・座席・座席から波の方向・左右の側面・後ろ 65°・真上（8 枚）＋数
- b1_2_orbit_<mode>.png：波頭の回り台 8 方位＋頂の輪郭の出っ張り（指）の数
- b1_3_out_vs_in.png：OUT と IN を同じ視点で並べる（原画視点の頂・座席・波頭 45°・180°・後ろ 65°）
- b1_4_numbers.png：S1 の数と OUT・IN の数、関門、検査の表
- b1_5_whitemask.png：白の印（垂れる舌）の展開図と原画視点
写真・参照モデルの形は入れない（描画は我々の主役波と冠だけ）。
使い方：py -3.10 -B Tools/GWWaveGen/as03/crown_sheets.py
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crown_common as G  # noqa: E402

RD = G.OUT + "/render"
SD = G.OUT + "/sheets"
LAB = {"painting": "原画視点", "painting_crest": "原画視点・頂の拡大", "seat": "座席", "seat_toward_wave": "座席から波の方向",
       "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}


def font(sz, bold=False):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), sz)
    except Exception:
        return ImageFont.truetype("C:/Windows/Fonts/msgothic.ttc", sz)


def tile(img_path, w, h):
    im = Image.open(img_path).convert("RGB")
    return im.resize((w, h), Image.LANCZOS)


def label(dr, xy, text, sz=20, fill=(255, 255, 255), bg=(20, 20, 20)):
    f = font(sz, True)
    x, y = xy
    tw = dr.textlength(text, font=f)
    dr.rectangle([x, y, x + tw + 12, y + sz + 8], fill=bg)
    dr.text((x + 6, y + 3), text, font=f, fill=fill)


def protrusions(img_path):
    """空を地にした頂の輪郭の出っ張り（指）の数：上の輪郭の線（列ごとの最も上の物の画素）の、幅 3〜60 px・高さ 6 px 以上の山。"""
    im = cv2.imread(img_path)
    bg = im[2, 2].astype(float)                 # 左上の隅は空（背景の色）
    d = np.abs(im.astype(float) - bg[None, None, :]).sum(-1)
    obj = d > 24
    H, W = obj.shape
    top = np.full(W, H, float)
    ys = np.argmax(obj, axis=0)
    has = obj.any(0)
    top[has] = ys[has]
    # 地平（海）より上だけ：列の最も上の物が画の上 70% にある列
    sm = cv2.GaussianBlur(top.reshape(1, -1).astype(np.float32), (61, 1), 0).ravel()
    resid = sm - top              # 上へ出た量（px）
    cnt = 0
    in_peak = False
    w0 = 0
    for x in range(W):
        if not has[x] or top[x] > 0.8 * H:
            in_peak = False
            continue
        if resid[x] > 6 and not in_peak:
            in_peak, w0 = True, x
        elif resid[x] <= 2 and in_peak:
            in_peak = False
            if 3 <= x - w0 <= 60:
                cnt += 1
    return cnt


def sheet_views(mode, rep):
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (24, 26, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 冠 %s：粘土の描画（Blender Workbench、主役波 AS02C の t*、白の印の色つき）" % mode, font=font(30, True), fill=(255, 255, 255))
    dr.text((24, 56), "主役波＝白の地（明るい灰）と藍（青灰）・冠＝暖かい白・冠の指の先の利用者の爪＝クリーム・面の内の爪（見本02 のまま）＝灰。Unity の描画ではない。HMD 実機ではない",
            font=font(17), fill=(200, 200, 200))
    names = ["painting", "painting_crest", "seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    tw, th = 456, 256
    for i, nm in enumerate(names):
        x = 24 + (i % 4) * (tw + 12)
        y = 96 + (i // 4) * (th + 44)
        p = os.path.join(RD, mode, nm + ".png")
        if os.path.exists(p):
            canvas.paste(tile(p, tw, th), (x, y))
        label(dr, (x, y), LAB[nm], 18)
    m = rep["measure"]
    c = m["counts"]
    ck = rep["checks"]
    lines = [
        "手 %d（S1 → 主役波 33、範囲 33〜59）：頂の縁の房 %d・垂れる縁 %d・唇の縁から垂れる %d・利用者の爪の房 %d" % (c["hands_total"], m["tiers"].get("1", 0), m["tiers"].get("3", 0), m["tiers"].get("4", 0), c["hands_user"]),
        "指の先 %d（S1 → 89、範囲 83〜111）＝手続きの指 %d＋利用者の爪 %d。頂の縁 %.1f m あたり %.2f 本（S1 1.73）" % (c["fingertips_total"], c["digits_procedural"], c["user_claw_tips"], c["rim_length_m"], c["fingertips_per_m"]),
        "指の長さ p50 %.2f m（S1 0.90）・根元の径 p50 %.2f m（S1 0.45）・全体の向き 水平から下 p50 %.0f°（S1 24°）・先 %.0f°（S1 33°）・先が下 %.0f%%（S1 91%%）" % (
            m["digit_len_m"]["ours"]["p50"], m["digit_base_diam_m"]["ours"]["p50"], m["digit_overall_below_horizontal_deg"]["ours"]["p50"],
            m["digit_tip_below_horizontal_deg"]["ours"]["p50"], 100 * (m["frac_tips_down"]["ours"] or 0)),
        "頂点 %d・三角形 %d。芯が面の下に入る指：手続きの指 %d・掌 %d・利用者の袖 %d・利用者の爪 %d（最深 %.2f m）" % (
            ck["vertices"], ck["triangles"], ck["finger_core_below_surface"]["digit"]["n"], ck["finger_core_below_surface"]["palm"]["n"],
            ck["finger_core_below_surface"].get("user_sleeve", {}).get("n", 0), ck["finger_core_below_surface"]["user_claw"]["n"],
            max(v["worst_m"] for v in ck["finger_core_below_surface"].values())),
    ]
    y = 96 + 2 * (th + 44) + 6
    for ln in lines:
        dr.text((24, y), "・" + ln, font=font(19), fill=(230, 230, 230))
        y += 30
    os.makedirs(SD, exist_ok=True)
    canvas.save(os.path.join(SD, "b1_1_views_%s.png" % mode))


def sheet_orbit(mode):
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (24, 26, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 冠 %s：波頭の回り台 8 方位（S3 と同じ：中心 (−6.63, 16.5, −3.27)、34 m、仰角 5°、画角 35°、0° は原画のカメラの向き）" % mode, font=font(24, True), fill=(255, 255, 255))
    tw, th = 456, 256
    prot = {}
    for i in range(8):
        nm = "crest_az%03d" % (45 * i)
        x = 24 + (i % 4) * (tw + 12)
        y = 70 + (i // 4) * (th + 60)
        p = os.path.join(RD, mode, nm + ".png")
        if os.path.exists(p):
            canvas.paste(tile(p, tw, th), (x, y))
            prot[nm] = protrusions(p)
        label(dr, (x, y), "%d°" % (45 * i), 18)
        dr.text((x + 6, y + th + 6), "頂の輪郭の出っ張り（指） %s" % prot.get(nm, "-"), font=font(18), fill=(230, 230, 230))
    txt = ["方位の読み（波の枠）：正面（進む向き）≈ 41°、右の側面 ≈ 131°、背 ≈ 221°、左の側面 ≈ 311°。",
           "出っ張りの数は、空を地にした画の上の輪郭の、幅 3〜60 px・高さ 6 px 以上の山を数えた（S3 の見本02 は 8 方位中 7 方位で 0、1 方位で 1）。",
           "彫刻の写真の読み（S1・S3）：後ろから輪郭の出っ張り約 8、右の写真で頂の縁の櫛 12〜13。"]
    y = 70 + 2 * (th + 60) + 10
    for t in txt:
        dr.text((24, y), "・" + t, font=font(19), fill=(220, 220, 220))
        y += 30
    canvas.save(os.path.join(SD, "b1_2_orbit_%s.png" % mode))
    return prot


def sheet_compare():
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (24, 26, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 冠 OUT（彫刻のように開く）｜ IN（原画視点の影を原画の白の冠・爪の区域に収める）同じ視点", font=font(28, True), fill=(255, 255, 255))
    names = ["painting_crest", "seat", "crest_az045", "crest_az180", "back65"]
    tw, th = 372, 210
    for i, nm in enumerate(names):
        for j, mode in enumerate(("OUT", "IN")):
            x = 24 + i * (tw + 8)
            y = 70 + j * (th + 40) + (0 if j == 0 else 0)
            p = os.path.join(RD, mode, nm + ".png")
            if os.path.exists(p):
                canvas.paste(tile(p, tw, th), (x, y))
            label(dr, (x, y), "%s %s" % (mode, LAB.get(nm, nm.replace("crest_az", "波頭 ") + "°")), 15)
    # 原画視点の全体（OUT・IN）
    for j, mode in enumerate(("OUT", "IN")):
        p = os.path.join(RD, mode, "painting.png")
        x = 24 + j * 950
        y = 70 + 2 * (th + 40)
        if os.path.exists(p):
            canvas.paste(tile(p, 930, 523), (x, y))
        label(dr, (x, y), "%s 原画視点" % mode, 18)
    canvas.save(os.path.join(SD, "b1_3_out_vs_in.png"))


def sheet_numbers(reps, gates, prot):
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (245, 243, 238))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 冠：S1（参照の彫刻を主役波の m へ当てた数）と、作った冠 OUT・IN の数", font=font(30, True), fill=(20, 20, 20))
    sp = G.jload(G.SPEC)["1_crest_crown"]
    rows = [("項目", "S1（主役波へ）", "OUT", "IN")]

    def g(rep, path, fmt="%.2f"):
        o = rep["measure"]
        for k in path:
            o = o.get(k) if isinstance(o, dict) else None
            if o is None:
                return "-"
        return fmt % o if isinstance(o, (int, float)) else str(o)
    R = reps
    rows += [
        ("手（掌＋指）の数", "33（33〜59）", g(R["OUT"], ["counts", "hands_total"], "%d"), g(R["IN"], ["counts", "hands_total"], "%d")),
        ("指の先の数", "89（83〜111）", g(R["OUT"], ["counts", "fingertips_total"], "%d"), g(R["IN"], ["counts", "fingertips_total"], "%d")),
        ("　うち利用者の爪（冠の役 S2）", "—", g(R["OUT"], ["counts", "user_claw_tips"], "%d"), g(R["IN"], ["counts", "user_claw_tips"], "%d")),
        ("頂の縁 1 m あたりの指の先", "1.73", g(R["OUT"], ["counts", "fingertips_per_m"]), g(R["IN"], ["counts", "fingertips_per_m"])),
        ("指の長さ p50（m）", "0.90（p10 0.37・p90 1.32）", g(R["OUT"], ["digit_len_m", "ours", "p50"]), g(R["IN"], ["digit_len_m", "ours", "p50"])),
        ("指の根元の径 p50（m）", "0.45", g(R["OUT"], ["digit_base_diam_m", "ours", "p50"]), g(R["IN"], ["digit_base_diam_m", "ours", "p50"])),
        ("指の全体の向き：水平から下 p50（°）", "24", g(R["OUT"], ["digit_overall_below_horizontal_deg", "ours", "p50"], "%.0f"), g(R["IN"], ["digit_overall_below_horizontal_deg", "ours", "p50"], "%.0f")),
        ("指の先の向き：水平から下 p50（°）", "33", g(R["OUT"], ["digit_tip_below_horizontal_deg", "ours", "p50"], "%.0f"), g(R["IN"], ["digit_tip_below_horizontal_deg", "ours", "p50"], "%.0f")),
        ("先が下を向く割合", "0.91", g(R["OUT"], ["frac_tips_down", "ours"]), g(R["IN"], ["frac_tips_down", "ours"])),
        ("前（進む向き）へ出る割合", "0.91", g(R["OUT"], ["frac_forward", "ours"]), g(R["IN"], ["frac_forward", "ours"])),
        ("手の根元の向きと法線の角 p50（°）", "22（彫刻の根元の面は前・下向き）", g(R["OUT"], ["hand_theta_vs_normal_deg", "ours", "p50"], "%.0f"), g(R["IN"], ["hand_theta_vs_normal_deg", "ours", "p50"], "%.0f")),
        ("利用者の爪の根元と法線の角 p50（°）", "22", g(R["OUT"], ["user_claw_angle_vs_normal_deg", "after", "p50"], "%.0f"), g(R["IN"], ["user_claw_angle_vs_normal_deg", "after", "p50"], "%.0f")),
        ("先の形 丸・口の開いた・ふくらむ", "多数・約 1 割・5% 未満", "丸 {round}・口 {open}・ふくらむ {bulb}".format(**R["OUT"]["measure"]["tips"]), "丸 {round}・口 {open}・ふくらむ {bulb}".format(**R["IN"]["measure"]["tips"])),
        ("根元の高さ（海面から、H0）p50", "0.59（p10 0.39・p90 0.85）", g(R["OUT"], ["root_height_over_H0", "ours", "p50"]), g(R["IN"], ["root_height_over_H0", "ours", "p50"])),
        ("頂点・三角形", "（S3 の見積もり 約 62,000 頂点）", "%d・%d" % (R["OUT"]["checks"]["vertices"], R["OUT"]["checks"]["triangles"]), "%d・%d" % (R["IN"]["checks"]["vertices"], R["IN"]["checks"]["triangles"])),
        ("波頭の回り台 8 方位の出っ張り（最少）", "後ろ約 8・横 12〜13", str(min(prot["OUT"].values())) if prot.get("OUT") else "-", str(min(prot["IN"].values())) if prot.get("IN") else "-"),
        ("関門 78・130・131（定義どおり、px）", "4 以下（見本02 2.741・3.582・3.442）", "%.3f・%.3f・%.3f" % (gates["OUT"]["78"], gates["OUT"]["130"], gates["OUT"]["131"]), "%.3f・%.3f・%.3f" % (gates["IN"]["78"], gates["IN"]["130"], gates["IN"]["131"])),
        ("関門 132 σ12・72 σ12 p95（px）", "4 以下（見本02 3.558・3.658）", "%.3f・%.3f" % (gates["OUT"]["132_s12"], gates["OUT"]["72_s12_p95"]), "%.3f・%.3f" % (gates["IN"]["132_s12"], gates["IN"]["72_s12_p95"])),
    ]
    x0 = [24, 640, 1180, 1550]
    y = 70
    for i, r in enumerate(rows):
        f = font(20, i == 0)
        if i % 2 == 1:
            dr.rectangle([20, y - 3, 1900, y + 30], fill=(232, 228, 220))
        for k, t in enumerate(r):
            dr.text((x0[k], y), str(t), font=f, fill=(20, 20, 20))
        y += 34
    y += 10
    notes = ["S1 の数は参照の彫刻（スキャン）を主役波へ当てた値（sculpture_spec.json）。関門は見本02 の Unity の原画視点の色区 ID の画（爪なし）に冠の覆いを重ねて測った（重ねる方法は見本02 の爪で画素まで一致）。",
             "主役波の頂の前は上を向くので、彫刻の『法線から 22°』をそのまま使うと指が上を向く。向きの数（全体 24° 下・先 33° 下）を先にした。"]
    for t in notes:
        dr.text((24, y), "・" + t, font=font(17), fill=(60, 60, 60))
        y += 28
    canvas.save(os.path.join(SD, "b1_4_numbers.png"))


def sheet_mask():
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (24, 26, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 白の印（共有）：前の白の地・垂れる舌・背の白。左＝原画、右＝原画の視点で見た白の印（S2 の表で引いた値。描画ではない）", font=font(24, True), fill=(255, 255, 255))
    p = os.path.join(G.SHARED, "white_mask_preview_painting_view.png")
    if os.path.exists(p):
        im = Image.open(p).convert("RGB")
        im = im.resize((1560, int(im.height * 1560 / im.width)), Image.LANCZOS)
        canvas.paste(im, (24, 60))
    p2 = os.path.join(G.SHARED, "white_mask_preview_grid.png")
    if os.path.exists(p2):
        im2 = Image.open(p2).convert("RGB")
        im2 = im2.resize((330, int(im2.height * 330 / im2.width)), Image.LANCZOS)
        canvas.paste(im2, (1590, 60))
        dr.text((1590, 70 + im2.height), "展開図（縦＝行、横＝列）\n白・藍・舌（薄い黄）\n桃＝原画の藍の面の縁\n橙＝境の点", font=font(16), fill=(220, 220, 220))
    canvas.save(os.path.join(SD, "b1_5_whitemask.png"))


def sheet_before_after():
    W, H = 1920, 1080
    canvas = Image.new("RGB", (W, H), (24, 26, 30))
    dr = ImageDraw.Draw(canvas)
    dr.text((24, 14), "B1 冠：前（見本02 の爪 83 本のまま、冠なし）｜ OUT ｜ IN（どれも共有の白の印 v2 の色、同じ視点）", font=font(26, True), fill=(255, 255, 255))
    names = ["painting_crest", "seat", "crest_az045", "crest_az225"]
    tw, th = 452, 254
    for i, nm in enumerate(names):
        for j, mode in enumerate(("none", "OUT", "IN")):
            x = 24 + i * (tw + 8)
            y = 70 + j * (th + 70)
            p = os.path.join(RD, mode, nm + ".png")
            if os.path.exists(p):
                canvas.paste(tile(p, tw, th), (x, y))
            label(dr, (x, y), "%s %s" % ({"none": "前", "OUT": "OUT", "IN": "IN"}[mode], LAB.get(nm, nm.replace("crest_az", "波頭 ") + "°")), 15)
    canvas.save(os.path.join(SD, "b1_6_before_after.png"))


def main():
    reps = {m: G.jload(os.path.join(G.OUT, m, "as03_crown_report.json")) for m in ("OUT", "IN")}
    gates = {m: G.jload(os.path.join(G.OUT, "gates", m, "gates_%s.json" % m))["gates_px"] for m in ("OUT", "IN")}
    prot = {}
    for m in ("OUT", "IN"):
        sheet_views(m, reps[m])
        prot[m] = sheet_orbit(m)
    sheet_compare()
    sheet_numbers(reps, gates, prot)
    sheet_mask()
    sheet_before_after()
    G.jdump(os.path.join(SD, "orbit_protrusions.json"), prot)
    print(json.dumps(prot))


if __name__ == "__main__":
    main()
