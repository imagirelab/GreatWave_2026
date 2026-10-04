# -*- coding: utf-8 -*-
"""美術の見本03 の組み立て：並べ図（1920 幅、日本語の見出し）。Unity の描画（asm_render.sh）と見本02（前）を同じ視点で並べる。
  asm_1_painting.png        原画視点：原画 DP130155｜V1｜V2｜V3
  asm_2_crest_closeup.png   原画視点の波頭と唇の拡大：見本02（前）｜V1｜V2｜V3
  asm_3a_views.png・3b      座席・座席から波・左の側面／右の側面・後ろ 65°・真上（行：見本02・V1・V2・V3）
  asm_4a_crest_orbit.png・4b 波頭の回り台 8 方位（行：見本02・V1・V2・V3）
  asm_5a_turntable.png・5b  回り台 12 方位（行：見本02・V1・V2・V3）
  asm_6_numbers.png         測る規則の数（rules_check.json）
  user_only/sculpture_vs_V1.png（利用者だけ。写真を含む。リポジトリと成果物へ入れない）：彫刻の写真｜V1（近い向き：正面・右45・左45・背・上）
使い方：py -3.10 -B Tools/GWWaveGen/as03/asm_sheets.py [all|user]
"""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
S3 = REPO + "/Unity/Build/Polish/sample03"
R = S3 + "/assemble/render"
OUTD = S3 + "/assemble/sheets"
S02V = REPO + "/Unity/Build/Polish/sample02/fix01/assemble/render/AS02C_A"
S02C = S3 + "/study/render/S3_AS02C_crest2"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"
REF = S3 + "/user_only/ref_asm"
VN = {"V1": "V1 冠 OUT（彫刻のように開く）＋ SCULPT（艶と陰）", "V2": "V2 冠 OUT ＋ FLAT（浮世絵の平らな色）", "V3": "V3 冠 IN（原画視点の輪郭に収める）＋ SCULPT",
      "S02": "見本02（前）：冠なし・見本 A の材質"}
VIEWJ = {"painting": "原画視点", "seat": "座席", "seat_toward_wave": "座席から波の方向", "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上"}
AZJ = {0: "0°（原画の側）", 45: "45°（正面）", 90: "90°", 135: "135°（右の側面）", 180: "180°", 225: "225°（背）", 270: "270°", 315: "315°（左の側面）"}
FOOT = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし。美術が届いたかは利用者が決める（Q29・Q30）。"


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fit(im, w, h, bg=(255, 255, 255)):
    im = im.convert("RGB")
    s = min(w / im.width, h / im.height)
    im2 = im.resize((max(1, round(im.width * s)), max(1, round(im.height * s))), Image.LANCZOS)
    c = Image.new("RGB", (w, h), bg)
    c.paste(im2, ((w - im2.width) // 2, (h - im2.height) // 2))
    return c


def font_zh(sz, bold=False):
    # 写真のファイル名（中国語の簡体字 图・顶 など）を含む見出し用。BIZ UD ゴシックには簡体字が無い
    for p in ("C:/Windows/Fonts/msyh%s.ttc" % ("bd" if bold else ""), "C:/Windows/Fonts/msyh.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return font(sz, bold)


def label(d, x, y, text, sz=22, bold=False, zh=False):
    f = font_zh(sz, bold) if zh else font(sz, bold)
    bb = d.textbbox((x, y), text, font=f)
    d.rectangle((bb[0] - 4, bb[1] - 3, bb[2] + 4, bb[3] + 3), fill=(255, 255, 255))
    d.text((x, y), text, font=f, fill=(20, 20, 20))


def sheet(title, cells, cols, cw, ch, path, sub=None):
    rows = (len(cells) + cols - 1) // cols
    top = 64 if not sub else 96
    H = top + rows * ch + 40
    W = cols * cw
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), title, font=font(32, True), fill=(10, 10, 10))
    if sub:
        d.text((14, 56), sub, font=font(20), fill=(60, 60, 60))
    for i, (p, lab, crop) in enumerate(cells):
        x, y = (i % cols) * cw, top + (i // cols) * ch
        if p is None or not os.path.isfile(p):
            d.rectangle((x + 2, y + 2, x + cw - 3, y + ch - 3), outline=(180, 180, 180))
            label(d, x + 10, y + 10, (lab or "") + "（なし）", 18)
            continue
        im = Image.open(p)
        if crop:
            im = im.crop(crop)
        img.paste(fit(im, cw - 4, ch - 4), (x + 2, y + 2))
        if lab:
            label(d, x + 10, y + 8, lab, 18 if cw < 700 else 22)
    d.text((14, H - 32), FOOT, font=font(18), fill=(70, 70, 70))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path)
    return path


def all_sheets():
    out = []
    # 1 原画視点
    cells = [(PAINT, "原画 DP130155（メトロポリタン美術館の公開の画像）", None)]
    cells += [(R + "/%s/views/painting_t120_claws.png" % v, VN[v], None) for v in ("V1", "V2", "V3")]
    out.append(sheet("美術の見本03：原画視点（t*）　原画｜V1｜V2｜V3", cells, 2, 960, 540, OUTD + "/asm_1_painting.png",
                     "冠＝B1 の立体の白い指の冠、面＝B2 の彫りの面（溝を内へ彫る）、面の内と近い海の爪 35 本は見本02 のまま（材質だけ変種と同じ）"))
    # 2 波頭の拡大
    crop = (0, 0, 1280, 720)
    cells = [(S02V + "/views/painting_t120_claws.png", VN["S02"], crop)]
    cells += [(R + "/%s/views/painting_t120_claws.png" % v, VN[v], crop) for v in ("V1", "V2", "V3")]
    out.append(sheet("原画視点の波頭と唇の拡大（左上 1280×720 を切り出し）", cells, 2, 960, 540, OUTD + "/asm_2_crest_closeup.png"))
    # 3 ほかの視点
    for tag, views in (("a", ("seat", "seat_toward_wave", "side_left")), ("b", ("side_right", "back65", "top"))):
        cells = []
        for v in ("S02", "V1", "V2", "V3"):
            for vw in views:
                p = (S02V if v == "S02" else R + "/" + v) + "/views/%s_t120_claws.png" % vw
                cells.append((p, ("%s ／ %s" % (VIEWJ[vw], VN[v].split("：")[0].split("（")[0] if v != "S02" else "見本02（前）")), None))
        out.append(sheet("原画視点のほかの視点（行：見本02・V1・V2・V3）：" + "・".join(VIEWJ[x] for x in views), cells, 3, 640, 360,
                         OUTD + "/asm_3%s_views.png" % tag))
    # 4 波頭の回り台
    for tag, azs in (("a", (0, 45, 90, 135)), ("b", (180, 225, 270, 315))):
        cells = []
        for v in ("S02", "V1", "V2", "V3"):
            for az in azs:
                p = (S02C if v == "S02" else R + "/" + v) + "/crest/t120_az%03d_claws.png" % az
                cells.append((p, "%s ／ 方位 %s" % ("見本02" if v == "S02" else v, AZJ[az]), (240, 135, 1680, 945)))
        out.append(sheet("波頭の回り台（中心 (−6.63, 16.5, −3.27)・距離 34 m・仰角 5°、主役波と冠・爪だけ）　行：見本02・V1・V2・V3", cells, 4, 480, 270,
                         OUTD + "/asm_4%s_crest_orbit.png" % tag))
    # 5 回り台
    for tag, azs in (("a", range(0, 180, 30)), ("b", range(180, 360, 30))):
        cells = []
        for v in ("S02", "V1", "V2", "V3"):
            for az in azs:
                p = (S02V if v == "S02" else R + "/" + v) + "/tt/t120_az%03d_claws.png" % az
                cells.append((p, "%s ／ %d°" % ("見本02" if v == "S02" else v, az), None))
        out.append(sheet("回り台（距離 72 m・仰角 16°、爪あり・飛沫なし、周りの海あり）　行：見本02・V1・V2・V3", cells, 6, 320, 180,
                         OUTD + "/asm_5%s_turntable.png" % tag))
    out.append(numbers_sheet())
    return out


def numbers_sheet():
    rc = json.load(open(S3 + "/rules_check.json", encoding="utf-8"))
    r = rc["rules"]
    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), "美術の見本03：測る規則の自動の確かめ（rules_check.json）", font=font(32, True), fill=(10, 10, 10))
    f, fb = font(21), font(21, True)
    y = 70
    hdr = ["規則", "V1", "V2", "V3", "中身（V1 冠 OUT＋SCULPT・V2 冠 OUT＋FLAT・V3 冠 IN＋SCULPT）"]
    xs = [14, 330, 420, 510, 600]
    for x, t in zip(xs, hdr):
        d.text((x, y), t, font=fb, fill=(0, 0, 0))
    y += 34
    d.line((14, y - 4, W - 14, y - 4), fill=(0, 0, 0), width=2)
    byv = rc["summary"]["by_variant"]
    g2 = r["G2"]["variants"]
    cv = r["T4"]["crown_visibility"]
    cn = r["T4"]["crown_numbers"]

    def gates(v):
        g = g2[v]["gates"]
        return "78 %.2f・130 %.2f・131 %.2f・132 %.2f・72 %.2f" % tuple(g[k]["claws"] for k in ("78", "130", "131", "132_s12", "72_s12_p95"))

    def mark(x):
        return "合" if x == "pass" else "不合"
    lines = [
        ("G1 投影なし", [mark(byv[v]["G1"]) for v in ("V1", "V2", "V3")], "シェーダーは B2 が確かめた版のまま、描画の道具の足した所にも原画カメラの行列・テクスチャなし。面の座標の伸びは AS02C と同じ所・同じ測りで悪くない"),
        ("G2 原画視点の輪郭", [mark(byv[v]["G2"]) for v in ("V1", "V2", "V3")], "V3 は通る必要（V1・V2 は記録）。px：V1 " + gates("V1")),
        ("", ["", "", ""], "V2 " + gates("V2")),
        ("", ["", "", ""], "V3 " + gates("V3")),
        ("S4 背は一つの山", [mark(byv[v]["S4"]) for v in ("V1", "V2", "V3")], "背の頂点は AS02C と同じ（最大 %.6f m）、冠の手の根元は背に無い。見本02 の S4 の合格がそのまま当てはまる" % r["S4"]["relief_vs_AS02C"]["back_u_lt_0"]["max_disp_m"]),
        ("C2 爪の水準（35 本）", [mark(byv[v]["C2"]) for v in ("V1", "V2", "V3")], "面の内 25・近い海 10。頂点は見本02 とバイトまで同じ。不合 %d 本" % r["C2"]["fail"]),
        ("C3 マスクとの重なり", [mark(byv[v]["C3"]) for v in ("V1", "V2", "V3")], "IoU p10・p50・最小 %s（0.85 以上）。冠の役の 48 本は冠の指の先" % "・".join("%.3f" % x for x in r["C3"]["iou_painting_p10_p50_min"])),
        ("T4 波頭の冠", [mark(byv[v]["T4"]) for v in ("V1", "V2", "V3")], "指の先 OUT %d・IN %d（S1 83〜111）、手 OUT %d・IN %d（33〜59）" % (
            cn["OUT"]["checks"]["fingertips_in_S1_range"]["value"], cn["IN"]["checks"]["fingertips_in_S1_range"]["value"],
            cn["OUT"]["checks"]["hands_in_S1_range"]["value"], cn["IN"]["checks"]["hands_in_S1_range"]["value"])),
        ("", ["", "", ""], "指の長さ p50 OUT %.2f・IN %.2f m（S1 0.62〜1.13）、手あたりの指 OUT %.2f・IN %.2f（1.5〜5）" % (
            cn["OUT"]["checks"]["digit_length_p50_in_S1_p25_p75_m"]["value"], cn["IN"]["checks"]["digit_length_p50_in_S1_p25_p75_m"]["value"],
            cn["OUT"]["checks"]["digits_per_hand_mean_in_S1_1p5_to_5"]["value"], cn["IN"]["checks"]["digits_per_hand_mean_in_S1_1p5_to_5"]["value"])),
        ("", ["", "", ""], "垂れる縁の舌 %d 本（S1 の大きさ %d 本）、彫りの面に %d / %d 本" % (
            r["T4"]["drip_tongues"]["checks"]["tongues_total_in_S1_count_range_for_edge"]["value"],
            r["T4"]["drip_tongues"]["checks"]["S1_size_tongues_in_S1_count_range_for_hidden_edge"]["value"],
            r["T4"]["drip_tongues"]["checks"]["tongues_present_on_relief_surface"]["value"], r["T4"]["drip_tongues"]["checks"]["tongues_present_on_relief_surface"]["of"])),
        ("", ["", "", ""], "冠が見える割合の最小（原画視点のほかの 26 視点）：V1 %.2f%%（%s）・V2 %.2f%%（%s）・V3 %.2f%%（%s）、基準 > 0.5%%" % (
            100 * cv["V1"]["min"]["frac"], cv["V1"]["min"]["view"], 100 * cv["V2"]["min"]["frac"], cv["V2"]["min"]["view"], 100 * cv["V3"]["min"]["frac"], cv["V3"]["min"]["view"])),
        ("", ["", "", ""], "0.5% 以下の視点：V1・V2 " + "・".join(k.replace("views/", "").replace("tt/", "回り台 ") for k in cv["V1"]["views_below_0p5pct"]) +
         "／V3 " + "・".join(k.replace("views/", "").replace("tt/", "回り台 ") for k in cv["V3"]["views_below_0p5pct"]) +
         "。冠 ÷（冠＋見える主役波）の最小（記録）：V1 %.1f%%・V3 %.1f%%" % (100 * cv["V1"]["record_crown_share_of_wave_silhouette"]["min"]["share"],
                                                                 100 * cv["V3"]["record_crown_share_of_wave_silhouette"]["min"]["share"])),
        ("T1 模様の間隔と伸び", [mark(byv[v]["T1"]) for v in ("V1", "V2", "V3")], "線の間隔 ÷ 設計の周期が 0.64〜1.56 の面積 %.1f%%、溝の中心の間隔は設計の %s 倍" % (
            100 * r["T1"]["spacing_ratio"]["frac_area_in_0.64_1.56"], "・".join("%.2f" % b["mean_over_design"] for b in r["T1"]["groove_gaps_measured_B2"]["bands"].values()))),
        ("", ["", "", ""], "|∇w| が 1/3〜3 倍の外の三角形 %d（細い三角形 %d を除く）、0.5〜2 倍の外の面積 %.3f%%" % (
            r["T1"]["stretch_grad_w"]["tri_outside_1_3_to_3x"], r["T1"]["stretch_grad_w"]["excluded_slivers_q_lt_0.1"]["triangles"],
            100 * r["T1"]["stretch_grad_w"]["area_frac_outside_0p5_to_2x"])),
    ]
    for name, marks, txt in lines:
        d.text((xs[0], y), name, font=fb if name else f, fill=(0, 0, 0))
        for x, m in zip(xs[1:4], marks):
            d.text((x, y), m, font=fb, fill=(0, 110, 0) if m == "合" else (180, 0, 0))
        # 長い文は幅で折り返す（「・」「、」「。」の後で切れるならそこで）
        t = txt
        maxw = W - xs[4] - 20
        while t:
            n = len(t)
            while n > 1 and d.textlength(t[:n], font=f) > maxw:
                n -= 1
            if n < len(t):
                k = max(t.rfind(ch, 0, n) for ch in "・、。 ")
                if k > n * 0.6:
                    n = k + 1
            d.text((xs[4], y), t[:n], font=f, fill=(30, 30, 30))
            t = t[n:]
            y += 28
        y += 6
    y += 10
    d.text((14, y), "・規則の範囲（S1 の分布の四分位など）の取り方は組み立ての担当の既定で、進行役が変えてよい。目で見た審査は閉じる条件にしない。", font=f, fill=(60, 60, 60))
    d.text((14, H - 32), FOOT, font=font(18), fill=(70, 70, 70))
    p = OUTD + "/asm_6_numbers.png"
    img.save(p)
    return p


def user_sheet():
    pairs = [("front", "正面（正面图）", "V1：方位 30°・仰角 15°"), ("right45", "右45（右45）", "V1：方位 −15°・仰角 28°"),
             ("left45", "左45（左45）", "V1：方位 75°・仰角 28°"), ("back", "背（背图）", "V1：方位 210°・仰角 18°"), ("top", "上（顶图、）", "V1：方位 30°・仰角 85°")]
    W, rowh, top = 1920, 560, 110
    H = top + rowh * len(pairs) + 50
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((14, 12), "利用者だけ：参照の彫刻の写真｜見本03 V1（冠 OUT＋SCULPT）を近い向きから", font=font(32, True), fill=(10, 10, 10))
    d.text((14, 56), "写真は他者の展示作品（Q19・Q20、参考にとどめ写し取らない）。この図はリポジトリ・成果物・Docs へ入れない（Git 対象外）。"
                     "方位は回り台と同じ決め方（0° = 原画の側、反時計回り）。", font=font(19), fill=(150, 0, 0))
    used = []
    for i, (k, pj, vj) in enumerate(pairs):
        y = top + i * rowh
        pp = REF + "/%s.png" % k
        vp = R + "/V1_cmp/cmp/%s.png" % k
        img.paste(fit(Image.open(pp), 720, 540), (10, y))
        img.paste(fit(Image.open(vp), 960, 540), (750, y))
        label(d, 20, y + 10, "写真：" + pj, 22, True, zh=True)
        label(d, 760, y + 10, vj, 22, True)
        used.append({"key": k, "photo_tmp": pp, "photo_tmp_sha256": sha(pp), "render": vp, "render_sha256": sha(vp)})
    d.text((14, H - 36), FOOT, font=font(18), fill=(70, 70, 70))
    p = S3 + "/user_only/sculpture_vs_V1.png"
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)
    log = {"noteJa": "利用者だけの比べの図。写真は Q16 のフォルダーの一時の縮めた写し（user_only/ref_asm、名前と SHA-256 は ref_asm_log.json）。"
                     "リポジトリと成果物へ入れない。要らなくなったら、この図と写しを消す。", "output": p, "output_sha256": sha(p), "used": used}
    json.dump(log, open(S3 + "/user_only/sculpture_vs_V1_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return p


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = []
    if what in ("all", "sheets"):
        res += all_sheets()
    if what in ("all", "user"):
        res.append(user_sheet())
    print("\n".join(res))
