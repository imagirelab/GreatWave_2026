# -*- coding: utf-8 -*-
"""美術の見本06・B-LOBES（Q34）の並べ図：見本05 形 B（B10）と見本06 の形 L（LB1）を、同じ視点・同じカメラで並べる。
  py -3.10 -B Tools/GWWaveGen/as06/lobes_sheets.py
入力：粘土（numpy の z バッファ、shapeB_clay.py の出力。Unity の描画ではない、船・爪なし）Build/Polish/sample06/lobes/deliver/clay、
      Unity の描画（材質 AS05）Build/Polish/sample05/fix1/assemble/render/B10・Build/Polish/sample06/lobes/assemble/render/LB1、
      断面の図（lobes_plot.py）、測る規則（rules_check_LB1.json・quick.json）。
出力：Build/Polish/sample06/lobes/deliver/sheets/as06L_*.png（1920×1080、見出しは日本語）。原画の色は面へ写さない。
"""
import json
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, "G:/Unity/GreatWave_2026_Fresh/Tools/GWWaveGen/as05")
import as05_deliver as D  # noqa: E402

P = D.P
P6 = P + "/sample06/lobes"
CLAY = P6 + "/deliver/clay"
RB = P + "/sample05/fix1/assemble/render/B10"
TAG = os.environ.get("AS06L_TAG", "LB2")                          # 並べる形 L の版（LB1 = assemble/final、LB2 = assemble2/final2）
RL = P6 + ("/assemble/render/LB1" if TAG == "LB1" else "/assemble2/render/" + TAG)
OUT = P6 + "/deliver/sheets"
D.OUT = OUT
KINDS = (("B10", "見本05 形 B（B10）", RB), (TAG, "見本06 形 L（%s）" % TAG, RL))
FOOT_NP = "numpy の z バッファの粘土（Unity の描画ではない）。t* = 12 s の静止、爪・船なし。美術が届いたかは利用者が決める（Q29・Q30）。"
FOOT_U = "Unity 6000.4.3f1 の PC オフスクリーン描画（HMD 実機ではない）。t* = 12 s の静止、飛沫なし、波頭の爪なし。美術が届いたかは利用者が決める（Q29・Q30）。"
VIEWJ = dict(D.VIEWJ)


def vj(v):
    return "回り台 %s°" % v[2:] if v.startswith("tt") else VIEWJ[v]


def clay(kind, v, mode):
    return Image.open(CLAY + "/%s_%s_%s.png" % (kind, v, mode)).convert("RGB")


def crop_of(v, margin=0.08):
    """B10 と LB1 の粘土で、波（暖かい灰）の画素を囲む枠（両方の和）。海（青みの灰）と空は外す。"""
    box = None
    for k, _, _ in KINDS:
        a = np.asarray(clay(k, v, "clay")).astype(int)
        m = (a[..., 0] > a[..., 2] + 6) & (a[..., 0] < 235)
        ys, xs = np.nonzero(m)
        if not len(xs):
            continue
        b = [xs.min(), ys.min(), xs.max(), ys.max()]
        box = b if box is None else [min(box[0], b[0]), min(box[1], b[1]), max(box[2], b[2]), max(box[3], b[3])]
    Hh, Ww = a.shape[:2]
    w, h = box[2] - box[0], box[3] - box[1]
    # 16:9 に広げる
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    w, h = w * (1 + 2 * margin), h * (1 + 2 * margin)
    if w / h < 16 / 9:
        w = h * 16 / 9
    else:
        h = w * 9 / 16
    x0, y0 = max(0, int(cx - w / 2)), max(0, int(cy - h / 2))
    x1, y1 = min(Ww, int(cx + w / 2)), min(Hh, int(cy + h / 2))
    return (x0, y0, x1, y1)


def clay_pair(name, title, sub, views, mode, crop=True):
    img, d = D.new_sheet(title, sub)
    n = len(views)
    cw = (1920 - 16 - (n - 1) * 8) // n
    ch = int(cw * 9 / 16)
    y = 120
    for k, nm, _ in KINDS:
        for j, v in enumerate(views):
            im = clay(k, v, mode)
            if crop:
                im = im.crop(crop_of(v))
            D.paste(img, d, im, 8 + j * (cw + 8), y, cw, ch, "%s ／ %s" % (nm, vj(v)), 16)
        y += ch + 10
    return img, d, y


def tt_grid(name, title, sub, mode=None, unity=False):
    img, d = D.new_sheet(title, sub)
    cw, ch = 312, 176
    y = 112
    azs = list(range(0, 360, 30))
    for half in (azs[:6], azs[6:]):
        for k, nm, r in KINDS:
            for j, az in enumerate(half):
                if unity:
                    p = r + "/tt/t120_az%03d_claws.png" % az
                    im = Image.open(p).convert("RGB")
                else:
                    im = clay(k, "tt%d" % az, mode).crop(crop_of("tt%d" % az, 0.06))
                D.paste(img, d, im, 8 + j * (cw + 6), y, cw, ch, "%s %d°" % (k, az), 14)
            y += ch + 6
        y += 8
    return img, d


def sheet_painting():
    pd = D.painting_disp()
    regs = D.regions_disp()
    srcs = [("原画", pd)] + [(nm, Image.open(r + "/views/painting_t120_claws.png").convert("RGB")) for _, nm, r in KINDS] \
        + [("見本06 %s（爪なし）" % TAG, Image.open(RL + "/views/painting_t120_clawfree.png").convert("RGB"))]
    img, d = D.new_sheet("美術の見本06 B-LOBES：原画視点　原画｜見本05 B10｜見本06 %s（爪あり・爪なし）" % TAG,
                         "線：赤 ① 浪尖・緑 ② b区域・水色 ③ 最も左の小さな区域（利用者が確かめた範囲）。桃の四角 = 利用者の切り出し（T6）。下の段は左側の拡大。\n"
                         "一艘目の船は Q34（船は動かしてよい）に従い、原画のカメラを中心とする相似（倍率 0.7434）で手前へ動かした（原画視点の船の画は同じ）。")
    cw, ch = 374, 210
    for k, (nm, im) in enumerate(srcs):
        D.paste(img, d, D.outlined(im, regs, 5), 8 + k * 382, 104, cw, ch, nm, 17)
    for k, (nm, im) in enumerate(srcs):
        z = D.outlined(im, regs, 3).crop(D.LEFT_BOX)
        D.paste(img, d, z, 8 + k * 382, 330, cw, 326, "%s ／ 左側の拡大" % nm, 16)
    return img, d


def sheet_sections():
    img, d = D.new_sheet("美術の見本06 B-LOBES：断面（行 c ごと）　灰 = 見本04 AS04F・薄緑 = 見本05 B10・青 = 見本06 " + TAG + "（緑の点 ② の印・水色の点 ③ の印）",
                         "赤い丸 = 塊の縁の頂 R（断面の座標 a 右が前・原画のカメラの側、y 上）。黒の点 = 背の頂の列 90、赤の点 = 列 200、桃の点 = 列 314。横線 = 0・0.4・0.5・0.6 H0。")
    im = Image.open(P6 + "/deliver/sections_%s.png" % TAG).convert("RGB")
    D.paste(img, d, im, 8, 100, 1904, 940)
    return img, d


def sheet_rules():
    rc = json.load(open(P6 + "/rules_check_%s.json" % TAG, encoding="utf-8"))
    rb = json.load(open(P + "/sample05/rules_check_B.json", encoding="utf-8"))
    tg = rc["rules"]["S11"]["targets"]
    tb = rb["rules"]["S11"]["targets"]
    img, d = D.new_sheet("美術の見本06 B-LOBES：測る規則（見本05 B10 → 見本06 %s）" % TAG,
                         "S11 の目標の値は進行役の既定で、利用者の言葉ではない。合否は自動の確かめで、閉じる条件ではない（美術は利用者が決める）。")
    y = 100
    f = D.font(19)
    for k in ("G1", "G2", "S4", "S8", "S9", "S10", "S11", "T5", "T6", "C2", "C3", "K-top"):
        vb = rb["rules"].get(k, {}).get("verdict"); vl = rc["rules"].get(k, {}).get("verdict")
        d.text((20, y), "%-6s  B10 %-5s → %s %-5s" % (k, vb, TAG, vl), font=f, fill=(20, 20, 20) if vl == "pass" else (190, 30, 30))
        y += 26
    y = 100
    for tid, r in tg.items():
        b = tb.get(tid, {})

        def fmt(v):
            if isinstance(v, dict):
                return " ".join("%s:%s" % (kk, (round(vv, 3) if isinstance(vv, float) else vv)) for kk, vv in list(v.items())[:4])
            return str(round(v, 3) if isinstance(v, float) else v)
        col = (20, 20, 20) if r["pass"] else (190, 30, 30)
        d.text((520, y), "%-9s %-6s B10 %s → %s %s  %s" % (tid, r["kind"], fmt(b.get("value")), TAG, fmt(r["value"]), "合" if r["pass"] else "否"), font=D.font(16), fill=col)
        y += 23
    return img, d


def main():
    os.makedirs(OUT, exist_ok=True)
    img, d = sheet_painting(); D.finish(img, d, TAG + "_as06L_1_painting_view.png", FOOT_U)
    V1 = ["painting", "seat", "seat_toward_wave", "side_left"]
    V2 = ["side_right", "back65", "top"]
    for mode, mj in (("clay", "色なしの粘土"), ("tint", "層の色づけ（赤 ①・緑 ②・水色 ③・青 wave4・灰 ほか）")):
        for part, vs in (("a", V1), ("b", V2)):
            img, d, _ = clay_pair("x", "美術の見本06 B-LOBES：%s　上 = 見本05 B10・下 = 見本06 %s" % (mj, TAG),
                                  "形だけで三つの層（① 浪尖・② b区域・③ 最も左の小さな区域）が段に読めるかを見る図。同じ視点・同じカメラ・同じ切り抜き。船・爪なし。", vs, mode)
            D.finish(img, d, TAG + "_as06L_2%s_%s.png" % (part, mode), FOOT_NP)
        img, d = tt_grid("x", "美術の見本06 B-LOBES：%s　回り台 12 方位（距離 72 m・仰角 16°、0° が原画の側）" % mj,
                         "各組の上の段 = 見本05 B10、下の段 = 見本06 " + TAG + "。300°・330° は左（③ の側）から。", mode)
        D.finish(img, d, TAG + "_as06L_3_turntable_%s.png" % mode, FOOT_NP)
    for part, vs in (("a", V1), ("b", V2)):
        img, d = D.new_sheet("美術の見本06 B-LOBES：材質 AS05（平らな塗り）　上 = 見本05 B10・下 = 見本06 " + TAG + "（爪なし）",
                             "白い粒なし（T5）・内の縁は藍（T6）のまま。② ③ の白は塊ごとの縁の頂の帯だけ、凹み・下の面は藍。")
        n = len(vs); cw = (1920 - 16 - (n - 1) * 8) // n; ch = int(cw * 9 / 16); y = 120
        for k, nm, r in KINDS:
            for j, v in enumerate(vs):
                im = Image.open(r + "/views/%s_t120_clawfree.png" % v).convert("RGB")
                D.paste(img, d, im, 8 + j * (cw + 8), y, cw, ch, "%s ／ %s" % (nm, vj(v)), 16)
            y += ch + 10
        D.finish(img, d, TAG + "_as06L_4%s_material.png" % part, FOOT_U)
    img, d = tt_grid("x", "美術の見本06 B-LOBES：材質 AS05　回り台 12 方位（爪あり）", "各組の上の段 = 見本05 B10、下の段 = 見本06 " + TAG + "。", unity=True)
    D.finish(img, d, TAG + "_as06L_5_turntable_material.png", FOOT_U)
    if os.path.isfile(P6 + "/deliver/sections_%s.png" % TAG):
        img, d = sheet_sections(); D.finish(img, d, TAG + "_as06L_6_sections.png", FOOT_NP)
    if os.path.isfile(P6 + "/rules_check_%s.json" % TAG):
        img, d = sheet_rules(); D.finish(img, d, TAG + "_as06L_7_rules.png", D.FOOT_RULES)
    # 8 帯の座標 w の伸び（G1 の否）の場所と、② ③ の白の当て方の比べ（LB1 で試した「縁の帯の全体」と「縁の頂の帯」）
    sm = P6 + "/assemble2/stretch_map_%s.png" % TAG
    cw_ = P6 + "/assemble/cmp_white.png"
    if os.path.isfile(sm) and os.path.isfile(cw_):
        img, d = D.new_sheet("美術の見本06 B-LOBES：残った問題の場所（%s）と、白の当て方の比べ" % TAG,
                             "左：帯の座標 w の伸びの三角形（G1、赤い点。隠れは見ていない）。塊の右の端の下の面と、塊の前の谷に集まる。" + chr(10) +
                             "右：② ③ の白の当て方（上から 見本05 B10・縁の帯の全体（LB1 の最初の版）・縁の頂の帯（採った方））。原画視点と回り台 330°。")
        D.paste(img, d, Image.open(sm).convert("RGB"), 8, 110, 1100, 620, "G1 の伸びの場所", 16)
        D.paste(img, d, Image.open(cw_).convert("RGB"), 1116, 110, 796, 672, "白の当て方", 16)
        D.finish(img, d, TAG + "_as06L_8_notes.png", FOOT_U)
    print(json.dumps(D.OUTS, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
