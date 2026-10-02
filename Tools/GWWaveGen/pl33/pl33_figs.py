# -*- coding: utf-8 -*-
"""仕上げ33 の記録の図（1920×1080。既にある Unity の PC オフスクリーン描画と numpy の数から並べるだけ）。

  fig_pl33_claws_views.png   原画視点の頂・唇（原画｜前｜後）、座席、後ろ 65°、右の側面の t* の拡大（前｜後）
  fig_pl33_bregion.png       b区域（［利用者の言葉］Q16・Q21）：原画｜前｜後（t* と t 10.5 s）
  fig_pl33_bumps.png         132・72 の細部込み（包絡の真値）の 4 px を超える所：原画に、包絡の真値（緑）・爪の真値（灰）・後の描画の空の境界（赤）と塊の印
使い方：py -3.10 -B Tools/GWWaveGen/pl33/pl33_figs.py
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw

REPO = "G:/Unity/GreatWave_2026_Fresh"
sys.path.insert(0, os.path.join(REPO, "Tools", "GWWaveGen", "pl30"))
from pl30_sheets import font, label, head  # noqa: E402

BEF = REPO + "/Unity/Build/Polish/32/fix01/r_fix01"
AFT = REPO + "/Unity/Build/Polish/33/r_after"
OUT = REPO + "/Docs/Evidence/Polish/33"
PAINT = REPO + "/Docs/References/Met_JP1847_DP130155.jpg"


def paint_disp():
    o = Image.open(PAINT).convert("RGB").resize((1606, 1080), Image.LANCZOS)
    P = Image.new("RGB", (1920, 1080), (200, 200, 200))
    P.paste(o, (157, 0))
    return P


def crop_fit(img, box, size):
    c = img.crop(box)
    c.thumbnail(size, Image.LANCZOS)
    return c


def views_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33 爪の造形｜t* の拡大：原画視点の頂と唇（原画｜前｜後）と、座席・後ろ 65°・右の側面（前｜後）",
         "前＝仕上げ32（ede11c8、修正の回 1 の状態）、後＝仕上げ33（射線の向きの立ち上げ・鉤の内の水色の膜・頂の裏の冠の爪）。Unity の PC オフスクリーン描画（HMD ではない）。")
    P = paint_disp()
    b = {v: Image.open(BEF + "/views/%s_t120_asis.png" % v).convert("RGB") for v in ("painting", "seat", "back65", "side_right")}
    a = {v: Image.open(AFT + "/views/%s_t120_asis.png" % v).convert("RGB") for v in ("painting", "seat", "back65", "side_right")}
    box = (560, 100, 1130, 500)
    for i, (lab, src) in enumerate([("原画（DP130155 を表示の px へ）", P), ("前（仕上げ32）", b["painting"]), ("後（仕上げ33）", a["painting"])]):
        t = crop_fit(src, box, (636, 446))
        im.paste(t, (4 + i * 638, 66))
        label(d, 8 + i * 638, 70, "原画視点 t*｜" + lab)
    rows = [("seat", (520, 330, 1400, 1080), "座席"), ("back65", (700, 230, 1500, 760), "後ろ 65°"), ("side_right", (780, 330, 1320, 800), "右の側面")]
    for j, (v, bx, nm) in enumerate(rows):
        for si, (lab, src) in enumerate([("前", b[v]), ("後", a[v])]):
            t = crop_fit(src[v] if isinstance(src, dict) else src, bx, (316, 300))
            x = 4 + (2 * j + si) * 320
            im.paste(t, (x, 520))
            label(d, x + 4, 524, "%s｜%s t*" % (lab, nm), 13)
    f = font(15)
    txt = ["・原画視点：爪の投影は前と同じ（射線の上を動かした。輪の中心と先の投影の差は最大 0.00005 px）。巻きの内側の水色の膜が、白い指・墨版の線・水色の律動を戻した",
           "  （一覧の爪の領域の中の白い地の上の水色の割合：前 0.322 → 後 0.419、原画 0.412）。冠の爪は t* の原画視点で見えない（描画の差 0 画素）。",
           "・座席：唇の前の爪が面から立ち上がり、白い指として下がって見える（輪郭の線が全周に出る）。後ろ 65°・右の側面：頂の裏の冠の爪が稜に沿って並ぶ（前はほとんど爪がない）。"]
    y = 840
    for s in txt:
        d.text((14, y), s, fill=(40, 48, 64), font=f)
        y += 24
    p = OUT + "/fig_pl33_claws_views.png"
    im.save(p)
    return p


def bregion_fig():
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    d = ImageDraw.Draw(im)
    head(d, "仕上げ33｜b区域の爪（［利用者の言葉］Q16・Q21）：原画｜前｜後（上：t*、下：t 10.5 s）",
         "b区域の爪の膜を帯の幅 × 1.8 にして（pl33_tuft_web）、指の間の水色の版を房ごとの塊に寄せた。藍の窓・3 つの房の形は主役波の形と材質（仕上げ28・29 の限界）で変えていない。")
    P = paint_disp()
    box = (140, 330, 620, 620)
    for r, ts in enumerate(("t120", "t105")):
        srcs = [("原画", P if ts == "t120" else None), ("前", Image.open(BEF + "/views/painting_%s_asis.png" % ts).convert("RGB")),
                ("後", Image.open(AFT + "/views/painting_%s_asis.png" % ts).convert("RGB"))]
        for i, (lab, src) in enumerate(srcs):
            if src is None:
                continue
            t = src.crop(box).resize((636, 384), Image.LANCZOS)
            im.paste(t, (4 + i * 638, 66 + r * 390))
            label(d, 8 + i * 638, 70 + r * 390, "%s｜%s" % (lab, "t*" if ts == "t120" else "t 10.5 s"))
    m = json.load(open(REPO + "/Unity/Build/Polish/33/measure/pl33_measure.json", encoding="utf-8"))["painting_tstar_rhythm"]
    f = font(15)
    s = ("b区域の帯の中（仕上げ32 の読み）の白い地の上の水色の割合：原画 %.3f、前 %.3f、後 %.3f。白い地の上の暗い線の成分：原画 %d、前 %d、後 %d。"
         % (m["bregion_painting"]["mizuiro"], m["bregion_before"]["mizuiro"], m["bregion_after"]["mizuiro"],
            m["bregion_painting"]["components"], m["bregion_before"]["components"], m["bregion_after"]["components"]))
    d.text((14, 860), s, fill=(40, 48, 64), font=f)
    d.text((14, 886), "判定は一部：付け根の水色の塊は増えたが、原画の房（5〜10 本の指が同じ向きに巻く束）と房の間の藍の窓は、主役波の形と材質の限界のまま。", fill=(40, 48, 64), font=f)
    p = OUT + "/fig_pl33_bregion.png"
    im.save(p)
    return p


def bumps_fig():
    sys.path.insert(0, REPO + "/Tools/PaintingTruth")
    cwd = os.getcwd()
    os.chdir(REPO)
    import truthlib as T
    import evaluate as EV
    truth = EV.Truth()
    os.chdir(cwd)
    ids = T.imread_rgb(AFT + "/t28_claws/t28/render/af28r01_class_ids.png")
    reg = EV.render_regions_ids(truth, ids, {"classes": {"sky": [255, 255, 255]}})
    rp = T.boundary_points(reg["sky"], truth.spec, truth.fmap)
    P = np.asarray(paint_disp()).copy()
    vis = (P * 0.55 + 255 * 0.45).astype(np.uint8)
    img = Image.fromarray(vis)
    d = ImageDraw.Draw(img)
    for ver, col in (("claws", (150, 150, 150)), ("envelope", (0, 170, 0))):
        for s in json.load(open(REPO + "/Tools/PaintingTruth/targets/main_wave_outline_%s.json" % ver, encoding="utf-8"))["segments"]:
            if s["id"] in ("132", "72"):
                pts = [tuple(q) for q in s["points_display"]]
                d.line(pts, fill=col, width=1)
    for q in rp[::1]:
        d.point((float(q[0]), float(q[1])), fill=(220, 0, 0))
    bj = json.load(open(AFT + "/pl33_bumps.json", encoding="utf-8"))
    for tid, e in bj["items"].items():
        for c in e["clusters_gt4"]:
            r = 9
            col = (255, 0, 255) if c["bump_out_of_envelope"] else (0, 90, 255)
            d.ellipse([c["x"] - r, c["y"] - r, c["x"] + r, c["y"] + r], outline=col, width=2)
    crop = img.crop((780, 120, 1180, 760)).resize((540, 864), Image.LANCZOS)
    im = Image.new("RGB", (1920, 1080), (238, 238, 238))
    dd = ImageDraw.Draw(im)
    head(dd, "仕上げ33｜132・72 の細部込み（評価器の定義のままの読み・包絡の真値）の 4 px を超える所（後＝仕上げ33 の t* の ID 画像）",
         "緑：包絡の真値（判定の読み）、灰：爪の真値（記録）、赤：描画の空の境界。桃の輪：描画が包絡より外へ出たこぶ、青の輪：描画が包絡に届かないへこみ（爪の先と先の間の空）。")
    im.paste(crop, (4, 66))
    f = font(16)
    y = 80
    for tid, e in bj["items"].items():
        dd.text((570, y), "%s：最大 %.4f px、p95 %.4f px（描画 → 真値 %.4f、真値 → 描画 %.4f）。4 px を超える描画の点 %d／%d" %
                (tid, e["max_px"], e["p95_px"], e["max_render_to_truth"], e["max_truth_to_render"], e["render_points_gt4"], e["render_points"]), fill=(30, 30, 30), font=f)
        y += 26
        for c in e["clusters_gt4"][:8]:
            dd.text((590, y), "(%.0f, %.0f) %d 点 最大 %.2f px %s" % (c["x"], c["y"], c["n"], c["max_px"], "こぶ（包絡の外）" if c["bump_out_of_envelope"] else "へこみ（包絡に届かない）"),
                    fill=(60, 60, 60), font=font(14))
            y += 20
        y += 10
    p = OUT + "/fig_pl33_bumps.png"
    im.save(p)
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn in (views_fig, bregion_fig, bumps_fig):
        print(fn())


if __name__ == "__main__":
    main()
