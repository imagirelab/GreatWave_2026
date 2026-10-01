# -*- coding: utf-8 -*-
"""仕上げ28 第1回 FACE-SWAP：R4 と候補の前後の図（1920×1080 の PNG、同じ視点・同じ t*）を作る（py -3.10、PIL + cv2）。
入力：faceswap_eval.py の出力（renders/<label>__<view>.png、renders/turntable_<label>/f_XXXX.png）と、faceswap_look.py の後ろ 65°・真後ろの描画、
原画視点の関門の重ね図（このスクリプトが作る：原画の板、描いた被覆、78/130/131 の原画の線、132/72 の σ12 の大きな輪郭、左の外輪郭を描く点）。
usage: py -3.10 faceswap_sheet.py <eval_dir> <look_dir> <out_dir> R4=<rows.npz> FS1=<rows.npz>"""
import os
import sys
import json

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import faceswap_common as F  # noqa: E402
KC = F.KC
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

W_, H_ = 1920, 1080


def font(sz):
    for p in (r"C:\Windows\Fonts\YuGothM.ttc", r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\msgothic.ttc", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(p):
            try:
                return ImageFont.truetype(p, sz)
            except Exception:
                pass
    return ImageFont.load_default()


def fit(im, w, h):
    im = im.convert("RGB")
    s = min(w / im.width, h / im.height)
    return im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)


def sheet(path, title, rows, labels=("R4（採用中）", "FS1（第1回 FACE-SWAP）"), notes=None):
    """rows: [(row_title, [img_left, img_right]), ...]"""
    S = Image.new("RGB", (W_, H_), (24, 24, 28))
    d = ImageDraw.Draw(S)
    f1, f2, f3 = font(30), font(22), font(18)
    d.text((16, 8), title, fill=(255, 255, 255), font=f1)
    top = 52
    n = len(rows)
    rh = (H_ - top - (34 if notes else 8)) // n
    cw = W_ // 2
    for i, (rt, ims) in enumerate(rows):
        y0 = top + i * rh
        for k, im in enumerate(ims):
            if im is None:
                continue
            t = fit(im, cw - 12, rh - 30)
            x0 = k * cw + (cw - t.width) // 2
            S.paste(t, (x0, y0 + 26))
            d.text((k * cw + 12, y0 + 2), "%s  %s" % (labels[k], rt), fill=(255, 230, 120), font=f2)
    if notes:
        d.text((16, H_ - 30), notes, fill=(200, 200, 200), font=f3)
    S.save(path)
    return path


def gate_overlay(label, rows_npz, out_png, g):
    import cv2
    z = np.load(rows_npz)
    c, A, Y = z["c"].astype(float), z["A"].astype(float), z["Y"].astype(float)
    gate, cov = g.measure_rows(c, A, Y)
    plate = cv2.imread(os.path.join(F.REPO, "Unity", "Build", "Q20H", "plate", "painting_display_1920x1080.png"))
    img = (plate * 0.6).astype(np.uint8)
    m = cov > 0.5
    img[m] = (img[m] * 0.5 + np.array([200, 120, 40]) * 0.5).astype(np.uint8)
    seg = F.outline_segments()
    for k in ("78", "130", "131"):
        cv2.polylines(img, [np.round(seg[k]).astype(np.int32).reshape(-1, 1, 2)], False, (0, 255, 0), 2, cv2.LINE_AA)
    for k, col in (("132", (0, 255, 255)), ("72", (255, 0, 255))):
        cv2.polylines(img, [np.round(g.lf.lf[k]).astype(np.int32).reshape(-1, 1, 2)], False, col, 2, cv2.LINE_AA)
    # 左の外輪郭を描く点：同じ行の R4 の背の頂（列 90）より何 m 前か（+ = 唇の側）
    c0_, A0_, Y0_ = F.load_r4()
    gen = F.outline_generators(c, A, Y, n_per=7)
    for x in gen:
        px = tuple(int(round(v)) for v in x["px"])
        fw = x["a"] - float(A0_[x["row"], 90])
        cv2.circle(img, px, 5, (0, 0, 255) if fw < 0.5 else (255, 220, 0), -1, cv2.LINE_AA)
        cv2.putText(img, "%+.1f m" % fw, (px[0] + 6, px[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    txt = "%s: 78 %.2f / 130 %.2f / 131 %.2f px (definition), 132 %.2f px, 72 p95 %.2f px (sigma 12 large form)" % (
        label, gate["78"]["max_px"], gate["130"]["max_px"], gate["131"]["max_px"], gate["132_lf12"]["max_px"], gate["72_lf12"]["p95_px"])
    cv2.putText(img, txt, (170, 1050), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(img, "green = 78/130/131 painted line, yellow/magenta = 132/72 sigma-12 large form; dots = point drawing the outline, label = metres forward of R4's crest in that row (cyan >= 0.5 m)",
                (170, 1022), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (230, 230, 230), 1, cv2.LINE_AA)
    cv2.imwrite(out_png, img)
    return gate


def main():
    ev, lk, out = sys.argv[1], sys.argv[2], sys.argv[3]
    items = dict(a.split("=", 1) for a in sys.argv[4:] if "=" in a)
    labs = list(items.keys())
    os.makedirs(out, exist_ok=True)
    g = F.QuickGate()
    gates = {}
    ov = {}
    for lab, p in items.items():
        ov[lab] = os.path.join(out, "gate_overlay_%s.png" % lab)
        gates[lab] = gate_overlay(lab, p, ov[lab], g)

    def rimg(lab, view):
        for d_ in (os.path.join(ev, "renders"), lk):
            p = os.path.join(d_, "%s__%s.png" % (lab, view))
            if os.path.isfile(p):
                return Image.open(p)
        return None

    def tt(lab, f):
        p = os.path.join(ev, "renders", "turntable_%s" % lab, "f_%04d.png" % f)
        return Image.open(p) if os.path.isfile(p) else None
    L = (labs[0], labs[1])
    made = []
    made.append(sheet(os.path.join(out, "sheet1_painting_view.png"), "仕上げ28 第1回 FACE-SWAP：原画視点（t*）— 関門の重ね図と粘土",
                      [("関門の重ね図（点 = 左の外輪郭を描く頂点）", [Image.open(ov[L[0]]).crop((100, 40, 1300, 800)), Image.open(ov[L[1]]).crop((100, 40, 1300, 800))]),
                       ("粘土 v1_painting", [rimg(L[0], "v1_painting"), rimg(L[1], "v1_painting")])],
                      notes="左の外輪郭 78・130・131 を描く点：R4 は背の頂のあたり（頂より後ろ最大 4.8 m）。FS1 は原画カメラに近い行の、頂より前の唇の上面の側（同じ画素で R4 の点より平均 1.8 m 前、1.1 m カメラ寄りの行、0.5 m 低い）。"))
    made.append(sheet(os.path.join(out, "sheet2_back_dome.png"), "仕上げ28 第1回：後ろから（ドームの確かめ）— 後ろ 65° と真後ろ",
                      [("後ろ 65°（b65_back）", [rimg(L[0], "b65_back"), rimg(L[1], "b65_back")]),
                       ("真後ろ（b90_back_straight）", [rimg(L[0], "b90_back_straight"), rimg(L[1], "b90_back_straight")])]))
    made.append(sheet(os.path.join(out, "sheet3_user_failure.png"), "仕上げ28 第1回：利用者の失敗の視点 — 中ほどのドーム（u11）と b区域（u13）",
                      [("u11_v9zoom_crest_bulge", [rimg(L[0], "u11_v9zoom_crest_bulge"), rimg(L[1], "u11_v9zoom_crest_bulge")]),
                       ("u13_v8zoom_b_region", [rimg(L[0], "u13_v8zoom_b_region"), rimg(L[1], "u13_v8zoom_b_region")])]))
    made.append(sheet(os.path.join(out, "sheet4_top_side.png"), "仕上げ28 第1回：真上（v6）と後ろ 3/4（v5）",
                      [("v6_top_down", [rimg(L[0], "v6_top_down"), rimg(L[1], "v6_top_down")]),
                       ("v5_back_three_quarter", [rimg(L[0], "v5_back_three_quarter"), rimg(L[1], "v5_back_three_quarter")])]))
    # ターンテーブルの 4 こま
    frames = [100, 140, 160, 180]
    S = Image.new("RGB", (W_, H_), (24, 24, 28))
    d = ImageDraw.Draw(S)
    d.text((16, 8), "仕上げ28 第1回：ターンテーブル（上 R4、下 FS1、同じこま）", fill=(255, 255, 255), font=font(30))
    cw, rh = W_ // 4, (H_ - 60) // 2
    for i, lab in enumerate(L):
        for k, f in enumerate(frames):
            im = tt(lab, f)
            if im is None:
                continue
            t = fit(im, cw - 8, rh - 30)
            S.paste(t, (k * cw + 4, 56 + i * rh + 26))
            d.text((k * cw + 8, 56 + i * rh + 2), "%s  f%04d" % (lab, f), fill=(255, 230, 120), font=font(20))
    S.save(os.path.join(out, "sheet5_turntable.png")); made.append(os.path.join(out, "sheet5_turntable.png"))
    json.dump({"gates": gates, "sheets": made}, open(os.path.join(out, "sheet_gates.json"), "w", encoding="utf-8"), indent=1, default=float)
    print("\n".join(made))


if __name__ == "__main__":
    main()
