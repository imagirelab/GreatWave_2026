# -*- coding: utf-8 -*-
"""美術の見本04 の調べ M（Q32）：見本03 V2 と AS04 Flat Smooth の比べの図。

- 比べの図（1 枚）mat_cmp_s03v2_vs_as04.png：t* の 7 視点（原画視点・座席・座席から波・左右の側面・後ろ 65°・真上）と
  波頭の回り台 8 方位（距離 34 m・仰角 5°）を、左に見本03 V2（平らな色・冠 OUT・彫りの面）、右に AS04 Flat Smooth（冠なし・滑らかな面）で並べる。
  どちらも爪あり（面の内 25・近い海 10。見本03 V2 は冠の指の先の 48 本も冠の一部として入る）・飛沫なし。
- 近くの図 mat_detail_face.png：原画視点の主の面の切り出し（原画｜見本03 V2｜AS04）と、座席から波の方向の面の切り出し（見本03 V2｜AS04）。
原画はメトロポリタン美術館の公開の画像（Docs/References/Met_JP1847_DP130155.jpg）。彫刻の写真・参照モデルは使わない。
使い方：py -3.10 -B Tools/GWWaveGen/as04/mat_sheets.py [AS04 の描画のフォルダー名（既定 final）]
"""
import hashlib
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

REPO = "G:/Unity/GreatWave_2026_Fresh"
S03 = REPO + "/Unity/Build/Polish/sample03/fix01/render/V2"
OUTD = REPO + "/Unity/Build/Polish/sample04/mat"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"


def font(sz, bold=False):
    for p in ("C:/Windows/Fonts/BIZ-UDGothic%s.ttc" % ("B" if bold else "R"), "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


VIEWS = [("painting", "原画視点"), ("seat", "座席（VR の視点）"), ("seat_toward_wave", "座席から波の方向"), ("side_left", "左の側面"),
         ("side_right", "右の側面"), ("back65", "後ろ 65°"), ("top", "真上")]


def main():
    run = sys.argv[1] if len(sys.argv) > 1 else "final"
    A4 = OUTD + "/render/" + run
    items = [(lab, S03 + "/views/%s_t120_claws.png" % v, A4 + "/views/%s_t120_claws.png" % v) for v, lab in VIEWS]
    items += [("波頭の回り台 %d°" % az, S03 + "/crest/t120_az%03d_claws.png" % az, A4 + "/crest/t120_az%03d_claws.png" % az) for az in range(0, 360, 45)]
    iw, ih = 470, 264
    gap, lab_h, head = 8, 30, 96
    pair_w = 2 * iw + gap
    cols = 2
    W = cols * pair_w + (cols + 1) * 24
    rows = (len(items) + cols - 1) // cols
    H = head + rows * (ih + lab_h + 14) + 40
    sh = Image.new("RGB", (W, H), (250, 248, 242))
    d = ImageDraw.Draw(sh)
    d.text((24, 14), "美術の見本04 調べ M：見本03 V2（左）と AS04 Flat Smooth（右）　t* = 12 s、爪あり・飛沫なし", font=font(26, True), fill=(20, 30, 50))
    d.text((24, 52), "左：見本03 V2 ＝ 平らな色＋2 段の陰、冠 OUT（指・泡の皮・滴・瘤）、彫りの面。右：AS04 ＝ 光・陰なしの平らな色の区域、冠なし、凹凸なしの滑らかな面。"
                     "Unity の PC 描画（HMD ではない）", font=font(17), fill=(60, 60, 60))
    used = []
    for i, (lab, pa, pb) in enumerate(items):
        r, c = i // cols, i % cols
        x0 = 24 + c * (pair_w + 24)
        y0 = head + r * (ih + lab_h + 14)
        d.text((x0, y0 + 2), lab, font=font(19, True), fill=(20, 30, 50))
        for k, p in enumerate((pa, pb)):
            im = Image.open(p).convert("RGB").resize((iw, ih), Image.LANCZOS)
            sh.paste(im, (x0 + k * (iw + gap), y0 + lab_h))
            used.append(p)
        d.text((x0 + 6, y0 + lab_h + 4), "見本03 V2", font=font(15, True), fill=(200, 30, 30))
        d.text((x0 + iw + gap + 6, y0 + lab_h + 4), "AS04", font=font(15, True), fill=(200, 30, 30))
    out = OUTD + "/mat_cmp_s03v2_vs_as04.png"
    sh.save(out)
    # ---- 近くの図
    det = Image.new("RGB", (1920, 1080), (250, 248, 242))
    d = ImageDraw.Draw(det)
    d.text((24, 12), "近くで見る：原画視点の主の面（原画｜見本03 V2｜AS04）と、座席から波の方向の面（見本03 V2｜AS04）", font=font(24, True), fill=(20, 30, 50))
    pnt = Image.open(PAINT).convert("RGB").crop((900, 380, 1760, 1100)).resize((600, 502), Image.LANCZOS)   # 原画の主の面（原画の画素）
    box = (500, 150, 1020, 585)   # 描画の原画視点の主の面（1920×1080 の画素）
    a = Image.open(S03 + "/views/painting_t120_claws.png").convert("RGB").crop(box).resize((600, 502), Image.LANCZOS)
    b = Image.open(A4 + "/views/painting_t120_claws.png").convert("RGB").crop(box).resize((600, 502), Image.LANCZOS)
    for k, (im, lab) in enumerate(((pnt, "原画（Met DP130155）"), (a, "見本03 V2"), (b, "AS04 Flat Smooth"))):
        det.paste(im, (24 + k * 630, 80))
        d.text((24 + k * 630, 52), lab, font=font(18, True), fill=(20, 30, 50))
    box2 = (100, 120, 1060, 660)
    a2 = Image.open(S03 + "/views/seat_toward_wave_t120_claws.png").convert("RGB").crop(box2).resize((900, 506 - 40), Image.LANCZOS)
    b2 = Image.open(A4 + "/views/seat_toward_wave_t120_claws.png").convert("RGB").crop(box2).resize((900, 506 - 40), Image.LANCZOS)
    d.text((24, 596), "座席から波の方向：見本03 V2", font=font(18, True), fill=(20, 30, 50))
    d.text((24 + 940, 596), "座席から波の方向：AS04 Flat Smooth", font=font(18, True), fill=(20, 30, 50))
    det.paste(a2, (24, 622)); det.paste(b2, (24 + 940, 622))
    out2 = OUTD + "/mat_detail_face.png"
    det.save(out2)
    rec = {"schema": "GreatWave.AS04.mat_sheets/1", "sheet": out, "sheet_sha256": sha(out), "detail": out2, "detail_sha256": sha(out2),
           "inputs": {p: sha(p) for p in sorted(set(used + [PAINT]))}}
    with open(OUTD + "/mat_sheets.json", "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    print(out, rec["sheet_sha256"], sh.size)
    print(out2, rec["detail_sha256"])


if __name__ == "__main__":
    main()
