# -*- coding: utf-8 -*-
"""美術の見本05 のやり方 A：並べ図（1920 幅の PNG）を作る。読み取りのみ（形・材質は変えない）。
py -3.10 -B Tools/GWWaveGen/as05/shapeA_sheets.py <render_name（例 A2）>

  sA1_painting.png   原画視点：原画｜見本04（FX1、Unity）｜やり方 A（Unity）と、左側の拡大。①②③ の多角形の線
  sA2_clay_layers.png 粘土の層の色づけ：見本04｜やり方 A（原画視点・座席・左右の側面・後ろ 65°・真上）
  sA3_clay_plain.png  粘土（色づけなし）：同じ並び
  sA4_tt_layers.png   回り台 12 方位の層の色づけ（やり方 A）、sA5_tt_plain.png 同じく色づけなし
  sA6_unity_views.png Unity の 6 視点：見本04｜やり方 A、sA7_unity_tt.png Unity の回り台 12 方位（やり方 A）
粘土は numpy の z バッファ（Unity の描画ではない）。Unity は 6000.4.3f1 の PC オフスクリーン描画（HMD ではない）。
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeA_common as C  # noqa: E402

OUT = C.OUT + "/sheets"
CLAY = C.OUT + "/clay"
FX1 = C.P4 + "/assemble/render/FX1"
VJ = {"painting": "原画視点", "seat": "座席", "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°", "top": "真上",
      "seat_toward_wave": "座席から波"}
FOOT = "見本05 やり方 A（進行役のサブエージェント、2026-10-04）。美術が届いたかは利用者が決める（Q29・Q30）。粘土は numpy の z バッファ、Unity は 6000.4.3f1 の PC 描画（HMD ではない）"
LAB_KEY = "層の色：赤 ① 主の頂と唇・緑 ② b区域・青緑 ③ 最左側の小区域（別の波 layer3）・灰 ほかの前・濃い灰 背・青 wave4（④）・淡い灰 近い海・白 爪。黒い線＝遮る縁"


def font(sz, bold=False):
    for p in (("C:/Windows/Fonts/YuGothB.ttc" if bold else "C:/Windows/Fonts/YuGothM.ttc"), "C:/Windows/Fonts/meiryo.ttc", "C:/Windows/Fonts/msgothic.ttc"):
        if os.path.isfile(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def ld(p, w=None):
    im = Image.open(p).convert("RGB")
    if w:
        im = im.resize((w, int(round(im.height * w / im.width))), Image.LANCZOS)
    return im


def sheet(title, sub, rows, colw, labels, outp, gap=6, top=96):
    """rows：[[path, ...], ...]、labels：同じ形の文字。各列 colw 幅。"""
    ims = [[ld(p, colw) if p and os.path.isfile(p) else None for p in r] for r in rows]
    rh = [max((im.height for im in r if im is not None), default=40) + 34 for r in ims]
    ncol = max(len(r) for r in rows)
    W = ncol * colw + (ncol + 1) * gap
    H = top + sum(rh) + gap * len(rows) + 40
    S = Image.new("RGB", (W, H), (248, 246, 240))
    d = ImageDraw.Draw(S)
    d.text((14, 10), title, font=font(30, True), fill=(10, 10, 10))
    d.text((14, 52), sub, font=font(18), fill=(60, 60, 60))
    y = top
    for r, lr, h in zip(ims, labels, rh):
        for j, (im, lb) in enumerate(zip(r, lr)):
            x = gap + j * (colw + gap)
            d.text((x, y), lb, font=font(20, True), fill=(20, 20, 20))
            if im is not None:
                S.paste(im, (x, y + 30))
        y += h + gap
    d.text((14, H - 32), FOOT, font=font(16), fill=(80, 80, 80))
    os.makedirs(os.path.dirname(outp), exist_ok=True)
    S.save(outp)
    print("sheet", outp, S.size)


def painting_sheet(rn):
    import s5_targets as T5
    pd = T5.painting_disp()[..., ::-1]
    tmp = OUT + "/_tmp"
    os.makedirs(tmp, exist_ok=True)
    A = T5.A
    polys = {k: np.round(A.ref_to_px(T5.S.REG[k])).astype(np.int32) for k in ("r1", "r2", "r3")}
    col = {"r1": (40, 40, 225), "r2": (60, 160, 30), "r3": (205, 170, 0)}
    paths = []
    for nm, p in (("painting", None), ("s04", FX1 + "/views/painting_t120_claws.png"), ("as05a", C.OUT + "/render/%s/views/painting_t120_claws.png" % rn)):
        im = pd.copy() if p is None else cv2.imread(p)
        for k, pl in polys.items():
            cv2.polylines(im, [pl], True, col[k], 2, cv2.LINE_AA)
        cv2.imwrite(tmp + "/%s.png" % nm, im)
        cv2.imwrite(tmp + "/%s_left.png" % nm, im[330:800, 100:780])
        paths.append(nm)
    rows = [[tmp + "/%s.png" % n for n in paths], [tmp + "/%s_left.png" % n for n in paths]]
    labels = [["原画（DP130155）", "見本04（FX1、Unity）", "やり方 A（%s、Unity）" % rn], ["左側の拡大", "左側の拡大", "左側の拡大"]]
    sheet("見本05 やり方 A：原画視点（爪あり）", "線：赤 ① 浪尖・緑 ② b区域・水色 ③ 最左側の小区域（利用者が確かめた多角形）。一艘目の船は原画のカメラを中心とする相似で手前へ（原画視点の画は同じ）",
          rows, 630, labels, OUT + "/sA1_painting.png")


def clay_sheets():
    views = ["painting", "seat", "side_left", "side_right", "back65", "top"]
    for kind, fn, ttl in (("layers", "sA2_clay_layers.png", "粘土の層の色づけ"), ("clay", "sA3_clay_plain.png", "粘土（色づけなし）")):
        rows, labels = [], []
        for i in range(0, len(views), 3):
            vs = views[i:i + 3]
            rows.append([CLAY + "/AS04F/AS04F_%s_%s.png" % (v, kind) for v in vs]); labels.append(["見本04 " + VJ[v] for v in vs])
            rows.append([CLAY + "/AS05A/AS05A_%s_%s.png" % (v, kind) for v in vs]); labels.append(["やり方 A " + VJ[v] for v in vs])
        sheet("見本05 やり方 A：%s（見本04 と並べる）" % ttl, LAB_KEY if kind == "layers" else "形だけ（一つの灰色に固定の光の半ランバート、遮る縁は黒い線）。船は入っていない（numpy の場面）",
              rows, 630, labels, OUT + "/" + fn)
    for kind, fn, ttl in (("layers", "sA4_tt_layers.png", "回り台 12 方位の層の色づけ"), ("clay", "sA5_tt_plain.png", "回り台 12 方位の粘土（色づけなし）")):
        rows, labels = [], []
        az = list(range(0, 360, 30))
        for i in range(0, 12, 4):
            rows.append([CLAY + "/AS05A/AS05A_tt%d_%s.png" % (a, kind) for a in az[i:i + 4]]); labels.append(["回り台 %d°" % a for a in az[i:i + 4]])
        sheet("見本05 やり方 A：" + ttl, LAB_KEY if kind == "layers" else "形だけ。0° が原画の側、反時計回り", rows, 470, labels, OUT + "/" + fn)


def unity_sheets(rn):
    views = ["painting", "seat", "side_left", "side_right", "back65", "top"]
    rows, labels = [], []
    for i in range(0, len(views), 3):
        vs = views[i:i + 3]
        rows.append([FX1 + "/views/%s_t120_claws.png" % v for v in vs]); labels.append(["見本04 " + VJ[v] for v in vs])
        rows.append([C.OUT + "/render/%s/views/%s_t120_claws.png" % (rn, v) for v in vs]); labels.append(["やり方 A " + VJ[v] for v in vs])
    sheet("見本05 やり方 A：Unity の 6 視点（材質 AS04F Flat Smooth、白い点なしの値の表、爪あり）", "見本04（FX1）と並べる。波頭の爪は出していない（Q33）",
          rows, 630, labels, OUT + "/sA6_unity_views.png")
    az = list(range(0, 360, 30))
    rows, labels = [], []
    for i in range(0, 12, 4):
        rows.append([C.OUT + "/render/%s/tt/t120_az%03d_claws.png" % (rn, a) for a in az[i:i + 4]]); labels.append(["回り台 %d°" % a for a in az[i:i + 4]])
    sheet("見本05 やり方 A：Unity の回り台 12 方位", "0° が原画の側、反時計回り", rows, 470, labels, OUT + "/sA7_unity_tt.png")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    rn = sys.argv[1] if len(sys.argv) > 1 else "A2"
    painting_sheet(rn)
    clay_sheets()
    unity_sheets(rn)
