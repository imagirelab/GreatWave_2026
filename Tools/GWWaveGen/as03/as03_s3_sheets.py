# -*- coding: utf-8 -*-
"""美術の見本03 の調べ S3：見本02 の診断の図（日本語の見出し）を作る。

作る図（どれも Git 対象外の Unity/Build/Polish/sample03/study/ の下、1920×1080）：
  s3_1_views.png          7 視点（爪あり）と視点ごとの数（as03_s3_measure.py の measure_ours.json・measure_ours_zones.json）
  s3_2_crest_orbit.png    波頭の回り台 8 方位（爪あり）と方位ごとの数
  s3_3_crest_closeups.png 波頭まわりの拡大と、彫刻との違いの書き込み
  s3_4_numbers.png        見本02・彫刻（写真と参照モデルの数）・原画（S2 の数）の比べの表
  user_only/s3_5_ref_compare_USERONLY.png  写真と見本02 の並べ（--ref を渡した時だけ。写真を含むので利用者だけに見せ、リポジトリへ入れない）
読むのは我々の描画と数の JSON（と --ref の時だけ写真の一時の縮めた写し）。参照モデルの OBJ は読まない。
使い方：py -3.10 -B Tools/GWWaveGen/as03/as03_s3_sheets.py [--ref]
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ST = "G:/Unity/GreatWave_2026_Fresh/Unity/Build/Polish/sample03/study"
RV = ST + "/render/S3_AS02C/views"
RC = ST + "/render/S3_AS02C_crest2/crest"
REF = ST + "/ref_tmp"
W, H = 1920, 1080
BG = (24, 26, 30)
FG = (238, 238, 232)
ACC = (255, 214, 92)
RED = (255, 96, 80)


def font(sz, bold=False):
    return ImageFont.truetype("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), sz)


def F(s, sz, bold=False):
    # 簡体字（写真のファイル名・フォルダー名の「图」「斋」）は BIZ UD ゴシックにないので、その行だけ Microsoft YaHei で描く
    if any(ch in s for ch in "图斋"):
        return ImageFont.truetype("C:/Windows/Fonts/msyh%s.ttc" % ("bd" if bold else ""), sz)
    return font(sz, bold)


def load(p):
    return Image.open(p).convert("RGB")


def text_block(d, xy, lines, sz=16, fill=FG, gap=4, bold_first=False):
    x, y = xy
    for i, ln in enumerate(lines):
        f = font(sz, bold_first and i == 0)
        d.text((x, y), ln, font=f, fill=fill)
        y += sz + gap
    return y


VIEWS_JA = [("painting", "原画視点"), ("seat", "座席"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
            ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]


def pct(x):
    return "%.0f%%" % (100 * x) if x is not None else "—"


def sheet1(m, z):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 16), "S3 の調べ①　見本02（背 AS02C・爪 83 本・見本 A の材質）t* = 12 s の 7 視点（爪あり）と視点ごとの数", font=font(26, True), fill=FG)
    d.text((24, 52), "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。見本02 の描画と画素まで同じ（差 0）。数は主役波の画素の中だけ。", font=font(17), fill=(200, 200, 196))
    tw, th = 462, 260
    x0, y0, gx, gy = 24, 92, 12, 118
    for i, (v, ja) in enumerate(VIEWS_JA):
        cx = x0 + (i % 4) * (tw + gx)
        cy = y0 + (i // 4) * (th + gy)
        t = load(f"{RV}/{v}_t120_claws.png").resize((tw, th), Image.LANCZOS)
        im.paste(t, (cx, cy))
        d.rectangle([cx, cy, cx + 150, cy + 26], fill=(0, 0, 0))
        d.text((cx + 6, cy + 3), ja, font=font(18, True), fill=ACC)
        mv = m["views"][v]
        zv = z.get(v, {})
        lip = zv.get("lip_j111-200")
        lipw = (lip["white"] + lip["mizuiro"]) if lip else None
        cf = mv.get("hero_class_frac", {})
        lines = ["主役波の白 %s　唇（頂〜唇の先）の白 %s" % (pct(cf.get("white")), pct(lipw) if lip else "見えない"),
                 "爪 %d 塊（中央値 %s 画素）　艶の光 %d 画素" % (mv.get("claw_blobs", 0), (mv.get("claw_blob_px_p50_p90_max") or ["—"])[0], mv.get("specular_px", 0)),
                 "白の明るさの幅 %s　白の縁の線 %d 画素" % (
                     ("%.1f" % (mv["lum_white_p5_p50_p95"][2] - mv["lum_white_p5_p50_p95"][0])) if "lum_white_p5_p50_p95" in mv else "—",
                     mv.get("edge_line_px", 0))]
        text_block(d, (cx + 2, cy + th + 6), lines, sz=15, gap=5)
    # 8 枠目：読み方
    cx = x0 + 3 * (tw + gx)
    cy = y0 + (th + gy)
    d.rectangle([cx, cy, cx + tw, cy + th + 100], outline=(90, 90, 90))
    notes = ["読み方（彫刻の数は写真と参照モデル）",
             "・唇の白：原画は白 55%＋水色 20%（S2）。",
             "  見本02 は藍の地（唇は爪の帯で藍）。",
             "・爪は藍の上の小さな白い点（塊の中央値",
             "  136〜189 画素＝12 画素四方ほど）。",
             "・白の明るさの幅（p95−p5、0〜255）：",
             "  彫刻の写真 78〜83、見本02 0〜6（平塗り）。",
             "・艶の光：彫刻はどの写真にも艶の筋、",
             "  見本02 は 0（光の計算がない材質）。",
             "・白の縁の線：彫刻には描いた線がない。",
             "・座席から：頂は藍だけ、白 0%。"]
    text_block(d, (cx + 10, cy + 10), notes, sz=16, gap=6, bold_first=True)
    im.save(ST + "/s3_1_views.png")


AZ_JA = {0: "0°（原画のカメラの向き）", 45: "45°（正面 ≈ 進む向き +t 41°）", 90: "90°", 135: "135°（右の側面 +e ≈ 131°）",
         180: "180°", 225: "225°（背 ≈ −t 221°）", 270: "270°", 315: "315°（左の側面 −e ≈ 311°）"}


def sheet2(m, z):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 16), "S3 の調べ②　波頭の回り台 8 方位（t*、爪あり）：頂の輪郭に指が 1 本も立たず、白は平らな帯・背は一枚の白", font=font(26, True), fill=FG)
    d.text((24, 52), "中心 (−6.63, 16.5, −3.27) m（頂の帯 c −6〜+6 m・列 80〜140 の重心の近く）・距離 34 m・仰角 5°・画角 35°。主役波だけ（ほかのシート・平らな海は隠した）。方位は原画のカメラの向きから反時計回り。",
           font=font(16), fill=(200, 200, 196))
    tw, th = 462, 260
    x0, y0, gx, gy = 24, 92, 12, 118
    for i, az in enumerate(range(0, 360, 45)):
        cx = x0 + (i % 4) * (tw + gx)
        cy = y0 + (i // 4) * (th + gy)
        t = load(f"{RC}/t120_az{az:03d}_claws.png").resize((tw, th), Image.LANCZOS)
        im.paste(t, (cx, cy))
        lab = "方位 " + AZ_JA[az]
        f = font(16, True)
        wl = d.textlength(lab, font=f)
        d.rectangle([cx, cy, cx + wl + 12, cy + 24], fill=(0, 0, 0))
        d.text((cx + 6, cy + 3), lab, font=f, fill=ACC)
        mc = m["crest"]["az%03d" % az]
        zc = z.get("crest_az%03d" % az, {})
        lip = zc.get("lip_j111-200")
        crest = zc.get("crest_j90-110")
        lines = ["頂の輪郭の出っ張り（指）%d 本　爪 %d 塊" % (mc.get("silhouette_protrusions", 0), mc.get("claw_blobs", 0)),
                 "頂（列 90〜110）の白 %s　唇の白 %s" % (pct(crest["white"]) if crest else "—", pct(lip["white"] + lip["mizuiro"]) if lip else "—"),
                 "白の明るさの幅 %s　艶の光 %d 画素" % (
                     ("%.1f" % (mc["lum_white_p5_p50_p95"][2] - mc["lum_white_p5_p50_p95"][0])) if "lum_white_p5_p50_p95" in mc else "—",
                     mc.get("specular_px", 0))]
        text_block(d, (cx + 2, cy + th + 6), lines, sz=15, gap=5)
    im.save(ST + "/s3_2_crest_orbit.png")


def arrow(d, a, b, col=RED, w=3):
    d.line([a, b], fill=col, width=w)
    import math
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s in (-1, 1):
        d.line([b, (b[0] - 14 * math.cos(ang + s * 0.45), b[1] - 14 * math.sin(ang + s * 0.45))], fill=col, width=w)


def label(d, xy, s, sz=18):
    f = font(sz, True)
    wl = d.textlength(s, font=f)
    x, y = xy
    d.rectangle([x - 4, y - 3, x + wl + 4, y + sz + 5], fill=(0, 0, 0))
    d.text((x, y), s, font=f, fill=ACC)


def crop_panel(src, box, size):
    t = load(src).crop(box)
    return t.resize(size, Image.LANCZOS), (size[0] / (box[2] - box[0]), size[1] / (box[3] - box[1]))


def sheet3(m, z):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 14), "S3 の調べ③　浪尖（頂と唇）の拡大：彫刻と違う所（数は ①②・④）", font=font(26, True), fill=FG)
    P = [(f"{RV}/painting_t120_claws.png", (250, 50, 1170, 560), (40, 60), "原画視点（拡大）"),
         (f"{RV}/seat_t120_claws.png", (380, 60, 1560, 720), (980, 60), "座席（拡大）"),
         (f"{RC}/t120_az045_claws.png", (200, 120, 1720, 960), (40, 570), "波頭の回り台 45°（正面）"),
         (f"{RC}/t120_az225_claws.png", (100, 120, 1820, 1070), (980, 570), "波頭の回り台 225°（背）")]
    size = (900, 470)
    panels = []
    for src, box, pos, ttl in P:
        t, k = crop_panel(src, box, size)
        im.paste(t, pos)
        panels.append((box, pos, k))
        label(d, (pos[0] + 8, pos[1] + 8), ttl, 18)

    def pt(i, x, y):
        box, pos, k = panels[i]
        return (pos[0] + (x - box[0]) * k[0], pos[1] + (y - box[1]) * k[1])
    # 原画視点
    label(d, pt(0, 760, 62), "頂：平らな白い帯（指の冠がない）", 17)
    arrow(d, pt(0, 800, 92), pt(0, 660, 122))
    label(d, pt(0, 830, 470), "唇：藍の地に白い点（爪 82 塊）", 17)
    arrow(d, pt(0, 960, 470), pt(0, 960, 330))
    label(d, pt(0, 270, 500), "面：細い等間隔の縞（明るい線は周期の 7%）", 17)
    arrow(d, pt(0, 420, 515), pt(0, 455, 548))
    label(d, pt(0, 270, 300), "白と藍の境に描いた線", 17)
    arrow(d, pt(0, 450, 300), pt(0, 470, 262))
    # 座席
    label(d, pt(1, 700, 640), "座席：頂は藍と縞だけ（白 0%）。爪は輪郭の小さな点", 17)
    # 正面
    label(d, pt(2, 260, 880), "頂の輪郭に出っ張り 0。白は頂から前へ 1.6〜2.5 m の帯", 17)
    arrow(d, pt(2, 760, 875), pt(2, 930, 400))
    # 背
    label(d, pt(3, 200, 980), "背：一枚の平らな白（明るさの幅 0・艶 0）。縁は描いた線", 17)
    im.save(ST + "/s3_3_crest_closeups.png")


ROWS = [
    ("項目", "見本02（今）", "参照の彫刻（写真・参照モデル）", "原画（S2 の数）"),
    ("波頭の白い指", "頂の輪郭の出っ張り 0（8 方位のうち 7）。冠の爪 47 本（S2）は面に寝た鉤", "71 本（参照モデル、c ±13.9 m、1.2〜1.3 本/m）。正面の写真で先 ≈ 37", "爪の線の交わり 2.2 本/m（頂）"),
    ("指の大きさ", "爪の長さ p50 1.08 m・最大の幅 p50 0.23 m", "長さ p50 0.96 m（0.044 H）・根元の直径 0.60 m・先 0.27 m・先が下 93%", "—"),
    ("唇（頂〜唇の先）の色", "白 3〜10%＋爪 3%、藍 89〜97%（爪の帯は藍の地）", "白い冠（指の根元は頂から 0.12 H 下・2.2 m 前、深さ ≈ 0.3 H）", "白 55%・水色 20%・線 16%・藍 9%"),
    ("白の垂れる縁", "頂の前の丸い房 1 列（周期 2.6 m・深さ 0.9 m）", "正面の写真で垂れる先 ≈ 19〜20（≈ 1 本/m）。先は丸い", "—"),
    ("面の彫り", "間隔 1.0 m（0.048 H）をどの高さでも保つ（Y 字の枝分かれ）。明るい線 7%・帯 26%（周期の割合）、平塗り", "中ほど ≈ 1.0 m（写真 0.047〜0.054 H・参照モデル 0.40 H）＝同じ。下の方 1.5〜2.0 m（参照モデル 0.25〜0.35 H）。丸く盛り上がる稜（山と谷 0.17〜0.19 m）、溝は暗い", "—"),
    ("陰影・艶", "白の明るさの幅 0〜6（0〜255）、艶の光 0 画素", "白の明るさの幅 78〜83、どの写真にも艶の筋", "平らな版の色"),
    ("藍の明るさ p5/p50/p95", "47 / 60 / 74（平らな中くらいの藍）", "14 / 19 / 58（深い藍と艶）", "—"),
    ("描いた線", "白の縁の線（原画視点 4,632 画素）・爪の縁の線", "なし（色の境だけ）", "藍の線あり（墨版）"),
    ("背（後ろ・横・上）", "一枚の平らな白（明るさの幅 0）。爪はほぼ見えない（後ろ 65° 9 画素）", "艶のある白に形の陰。頂の上に指 ≈ 8（後ろの写真）", "—"),
]


def sheet4():
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 16), "S3 の調べ④　数の比べ（見本02・参照の彫刻・原画）", font=font(26, True), fill=FG)
    cols = [24, 300, 860, 1500]
    wcol = [270, 550, 630, 400]
    y = 70
    for r, row in enumerate(ROWS):
        f = font(17, r == 0)
        # 折り返し
        cells = []
        for k, s in enumerate(row):
            lines, cur = [], ""
            for ch in s:
                if d.textlength(cur + ch, font=f) > wcol[k] - 12:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
            cells.append(lines)
        hgt = max(len(c) for c in cells) * 24 + 14
        d.rectangle([20, y - 4, W - 20, y + hgt - 6], fill=(40, 44, 52) if r % 2 == 0 else (30, 33, 38))
        for k, lines in enumerate(cells):
            yy = y + 2
            for ln in lines:
                d.text((cols[k], yy), ln, font=f, fill=ACC if r == 0 else FG)
                yy += 24
        y += hgt
    notes = ["出典：参照モデルの数は S1 の調べ（s1_crown_numbers_v06.json・s1_crown2_numbers_m05b.json・s1_face_relief.json、作業中の版。OBJ は S1 が一時キャッシュで読み数だけ）。写真の数は G:/research/reality scan/北斋参考 の 1600 幅の一時の写しで測った（ref_measure_auto.json・diagnosis.md）。",
             "原画の数は S2 の調べ（painting_crest.json：原画の画素を原画のカメラで AS02C の面へ結んだ値）。見本02 の数は as03_s3_measure.py（measure_ours.json・measure_ours_zones.json）。",
             "H は波の高さ（AS02C H0 = 20.75 m、彫刻の写真は台の海の面〜頂）。写真の測りは遠近と曲がりで ±15% ほどの不確かさ。"]
    y += 14
    for n in notes:
        d.text((24, y), n, font=F(n, 15), fill=(190, 190, 186))
        y += 24
    im.save(ST + "/s3_4_numbers.png")


PAIRS = [(11, (330, 0, 1330, 750), 45, "写真「正面图」（正面）", "見本02 方位 45°（正面）"),
         (2, (430, 40, 1230, 640), 0, "写真「左45」（左前 45°）", "見本02 方位 0°（原画の向き）"),
         (3, (450, 80, 1250, 680), 315, "写真「左图」（左）", "見本02 方位 315°（左の側面）"),
         (1, (480, 140, 1360, 800), 180, "写真「右图」（右後ろ）", "見本02 方位 180°"),
         (12, (520, 180, 1360, 810), 225, "写真「背图」（背）", "見本02 方位 225°（背）")]


def sheet5():
    os.makedirs(ST + "/user_only", exist_ok=True)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((24, 14), "利用者だけに見せる比べ（彫刻の写真を含む。リポジトリと成果物へ入れない）：参照の彫刻の写真｜見本02 の波頭の回り台", font=font(22, True), fill=RED)
    tw, th = 366, 275
    for i, (ri, box, az, lp, lo) in enumerate(PAIRS):
        cx = 24 + i * (tw + 12)
        p = load(f"{REF}/ref{ri:02d}.png").crop(box).resize((tw, th), Image.LANCZOS)
        o = load(f"{RC}/t120_az{az:03d}_claws.png").crop((240, 0, 1680, 1080)).resize((tw, th), Image.LANCZOS)
        im.paste(p, (cx, 90))
        im.paste(o, (cx, 90 + th + 60))
        d.text((cx, 64), lp, font=F(lp, 17, True), fill=ACC)
        d.text((cx, 90 + th + 34), lo, font=font(17, True), fill=ACC)
    notes = ["彫刻：波頭は艶のある白い指の厚い冠（参照モデルで 71 本、先は丸く下へ垂れる）。白は藍の面へ垂れる。面は丸く盛り上がる稜と暗い溝。白にも藍にも形の陰と艶の筋。描いた線はない。",
             "見本02：頂は平らな白い帯で、輪郭に指が立たない。唇は藍の地に小さな白い点。面は平らに描いた細い縞。光の計算がなく、白は一色。白の縁に描いた線。",
             "写真は G:/research/reality scan/北斋参考 の読み取りのみの一時の縮めた写し（Exif なし）。この図は Build の下だけに置く。"]
    y = 90 + 2 * th + 90
    for n in notes:
        d.text((24, y), n, font=F(n, 16), fill=FG)
        y += 28
    im.save(ST + "/user_only/s3_5_ref_compare_USERONLY.png")


def main():
    m = json.load(open(ST + "/measure_ours.json", encoding="utf-8"))
    z = json.load(open(ST + "/measure_ours_zones.json", encoding="utf-8"))
    sheet1(m, z)
    sheet2(m, z)
    sheet3(m, z)
    sheet4()
    if "--ref" in sys.argv:
        sheet5()
    print("AS03_S3_SHEETS_DONE")


if __name__ == "__main__":
    main()
