# -*- coding: utf-8 -*-
"""美術の見本05 やり方 B：並べ図（1920 幅、見出しは日本語）。py -3.10 -B Tools/GWWaveGen/as05/shapeB_sheets.py [描画の名前（既定 B2）]

  sB_1_painting.png   原画視点：原画｜見本04（Unity）｜見本05 B（Unity）と、左の部分の拡大（区域の線 ②緑・③水色、読んだ頂の線 桃）
  sB_2_clay.png       粘土（形だけ、numpy）：見本04｜見本05 B。原画視点・座席・左右の側面・後ろ 65°・真上
  sB_3_layers.png     同じ視点の三つの層の色づけ（① 赤・② 緑・③ 水色・wave4 青・ほかの前の面 灰）
  sB_4_tt_clay.png    回り台 12 方位の粘土（上：色づけなし、下：層の色づけ）
  sB_5_unity_views.png  Unity の材質つき：座席・座席から波・左右の側面・後ろ 65°・真上（見本04｜見本05 B）
  sB_6_tt_unity.png   Unity の回り台 12 方位（見本05 B）
  sB_7_sections.png   断面（行 c ごと。灰 = 見本04、赤 = 見本05 B、薄い灰 = 原画の空の射線の禁止域、橙 = 船・手前の海の射線の禁止域）
原画の色は面へ写さない（並べるだけ）。
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shapeB_common as B  # noqa: E402
import s5_targets as T5  # noqa: E402

TAG = sys.argv[1] if len(sys.argv) > 1 else "B2"
SB = B.OUT
P4 = B.P + "/sample04"
R04 = P4 + "/assemble/render/FX1"
RB = SB + "/render/" + TAG
CL = SB + "/clay"
OUTD = SB + "/sheets"
FONT = "C:/Windows/Fonts/meiryo.ttc"
VJA = {"painting": "原画視点", "seat": "座席", "seat_toward_wave": "座席から波", "side_left": "左の側面", "side_right": "右の側面", "back65": "後ろ 65°",
       "top": "真上"}


def font(n):
    return ImageFont.truetype(FONT, n)


def im(p, size=None):
    x = Image.open(p).convert("RGB")
    return x.resize(size, Image.LANCZOS) if size else x


def title(W, H, t, sub=None):
    S = Image.new("RGB", (W, H), (248, 246, 240))
    d = ImageDraw.Draw(S)
    d.text((20, 12), t, fill=(20, 20, 20), font=font(30))
    if sub:
        d.text((20, 56), sub, fill=(60, 60, 60), font=font(17))
    return S, d


def label(d, xy, t, n=20, fill=(20, 20, 20), bg=(248, 246, 240)):
    x, y = xy
    w = d.textlength(t, font=font(n))
    d.rectangle([x - 3, y - 2, x + w + 3, y + n + 6], fill=bg)
    d.text((x, y), t, fill=fill, font=font(n))


def outline_regions(img, scale=1.0):
    d = ImageDraw.Draw(img)
    for k, col in (("r2", (40, 150, 60)), ("r3", (20, 160, 200))):
        p = T5.A.ref_to_px(T5.S.REG[k]) * scale
        d.line([tuple(x) for x in np.r_[p, p[:1]]], fill=col, width=2)
    for key in ("r2", "r3"):
        p = T5.A.ref_to_px(np.array(B.READ_CREST[key], float)) * scale
        d.line([tuple(x) for x in p], fill=(230, 0, 200), width=2)
    return img


def sheet1():
    S, d = title(1920, 1130, "見本05 やり方 B：原画視点（原画｜見本04｜見本05 B、Unity）",
                 "下の段は左の部分の拡大。緑 = ② b区域、水色 = ③ 最左側の小区域（利用者が確かめた多角形）、桃 = 進行役が読んだ ②・③ の頂の線。爪あり。HMD の実機ではない")
    pd = Image.fromarray(T5.painting_disp())
    a = im(R04 + "/views/painting_t120_claws.png"); b = im(RB + "/views/painting_t120_claws.png")
    for k, (x, t) in enumerate(((pd, "原画 DP130155"), (a, "見本04（AS04F）"), (b, "見本05 B（AS05B）"))):
        S.paste(x.resize((632, 356), Image.LANCZOS), (8 + k * 636, 90))
        label(d, (14 + k * 636, 94), t)
    for k, (x, t) in enumerate(((pd, "原画"), (a, "見本04"), (b, "見本05 B"))):
        z = outline_regions(x.copy()).crop((0, 300, 800, 860)).resize((632, 442), Image.LANCZOS)
        S.paste(z, (8 + k * 636, 470))
        label(d, (14 + k * 636, 474), t + "（左の部分）")
    d.text((20, 925), "見方：② は ① の左下の手前に出る段（縁の頂 0.515 H0、原画のカメラから 48.6 m）、③ はさらに左下の低い段（0.413 H0、44.4 m）。"
                      "② と ③ の白は自分の縁の頂の帯だけで、その下は藍の面。", fill=(30, 30, 30), font=font(17))
    d.text((20, 955), "白い点（波の本体の模様）は描かない（Q33・T5）。唇の下の内の縁（Q33 の切り出し）は唇の下の白を藍にした（T6）。"
                      "見本04 の白い点は比べのために残っている。", fill=(30, 30, 30), font=font(17))
    return S


def grid_views(names, a_tmpl, b_tmpl, ttl, sub, a_lab="見本04", b_lab="見本05 B"):
    n = len(names)
    W, H = 1920, 110 + n * 300
    S, d = title(W, H, ttl, sub)
    for k, vn in enumerate(names):
        y = 100 + k * 300
        for j, (tmpl, lb) in enumerate(((a_tmpl, a_lab), (b_tmpl, b_lab))):
            p = tmpl % vn
            if os.path.isfile(p):
                S.paste(im(p, (520, 293)), (8 + j * 528, y))
            label(d, (14 + j * 528, y + 4), "%s %s" % (lb, VJA.get(vn, vn)), n=18)
    return S


def grid_two_cols(names, a_tmpl, b_tmpl, ttl, sub, a_lab, b_lab, cols=2):
    rows = (len(names) + cols - 1) // cols
    W, H = 1920, 100 + rows * 280
    S, d = title(W, H, ttl, sub)
    w, h = 476, 268
    for k, vn in enumerate(names):
        r, cc = divmod(k, cols)
        for j, (tmpl, lb) in enumerate(((a_tmpl, a_lab), (b_tmpl, b_lab))):
            x = 8 + cc * 960 + j * 480; y = 96 + r * 280
            p = tmpl % vn
            if os.path.isfile(p):
                S.paste(im(p, (w, h)), (x, y))
            label(d, (x + 6, y + 4), "%s %s" % (lb, VJA.get(vn, vn)), n=16)
    return S


def tt_sheet(tmpl, azs, ttl, sub, tmpl2=None, lab1="", lab2=""):
    rows = 2 if tmpl2 is None else 4
    W, H = 1920, 100 + rows * 250
    S, d = title(W, H, ttl, sub)
    w, h = 316, 178
    for k, az in enumerate(azs):
        r, cc = divmod(k, 6)
        for j, (t, lb) in enumerate(((tmpl, lab1), (tmpl2, lab2))):
            if t is None:
                continue
            p = t % az
            y = 96 + (r + j * 2) * 250
            if os.path.isfile(p):
                S.paste(im(p, (w, h)), (8 + cc * 318, y))
            label(d, (14 + cc * 318, y + 4), "%s %d°" % (lb, az), n=16)
    return S


def sections():
    import r2_common as R
    c, A, Y = B.load_rows(SB + "/final/cand/kstarAS05B_a45_rows.npz"); c0, A0, Y0 = B.load_rows()
    zp = np.load(B.REPO + "/Unity/Build/Polish/28/rec/cache/protect_grids.npz")
    Gp = np.unpackbits(zp["G"], axis=-1)[..., :R.NA].astype(bool)
    Gs = R.keepout_grids(c, 3, 2, cache=B.REPO + "/Unity/Build/Polish/28/r2/cache/keepout_d3.npz")
    cs = [-20.0, -18.6, -17.8, -17.0, -15.6, -14.0, -12.4, -11.6, -11.0, -10.2, -9.4, -8.0]
    Wp, Hp, sc = 470, 330, 21.0
    S, d = title(1920, 110 + 3 * (Hp + 6), "見本05 やり方 B：断面（行 c ごと。numpy、Unity の描画ではない）",
                 "灰 = 見本04（AS04F）、赤 = 見本05 B。薄い灰 = 原画の空の射線の禁止域、橙 = 船・手前の海の射線の禁止域（仕上げ28 の格子）。目盛り 0.35〜0.55 H0。左が後ろ、右が前（原画のカメラの側）")
    arr = np.array(S)
    for k, cc in enumerate(cs):
        i = int(np.argmin(np.abs(c - cc)))
        ox, oy = 8 + (k % 4) * (Wp + 4), 100 + (k // 4) * (Hp + 6)
        panel = np.full((Hp, Wp, 3), 252, np.uint8)
        P_ = lambda a, y: (int(Wp * 0.36 + a * sc), int(Hp - 16 - (y - 3.0) * sc))
        for G, col in ((Gs[i], (215, 215, 215)), (Gp[i], (250, 200, 150))):
            ys, xs = np.nonzero(G)
            for yy, xx in zip(ys, xs):
                q = P_(R.GA0 + xx * R.GRES, R.GY0 + yy * R.GRES)
                if 0 <= q[0] < Wp and 0 <= q[1] < Hp:
                    panel[q[1], q[0]] = col
        for AA, YY, col, t in ((A0, Y0, (150, 150, 150), 1), (A, Y, (210, 40, 40), 2)):
            pts = np.array([P_(AA[i, j], YY[i, j]) for j in range(400)], np.int32)
            cv2.polylines(panel, [pts], False, col, t, cv2.LINE_AA)
        for yy in (0.35, 0.45, 0.55):
            p0 = P_(-7.0, yy * B.H0)
            cv2.line(panel, p0, (p0[0] + 10, p0[1]), (0, 0, 0), 1)
        arr[oy:oy + Hp, ox:ox + Wp] = panel
    S = Image.fromarray(arr)
    d = ImageDraw.Draw(S)
    for k, cc in enumerate(cs):
        i = int(np.argmin(np.abs(c - cc)))
        ox, oy = 8 + (k % 4) * (Wp + 4), 100 + (k // 4) * (Hp + 6)
        lay = "③ の段" if -18.9 <= c[i] <= -16.6 else ("② の段" if -13.2 <= c[i] <= -10.0 else ("見本04 のまま" if c[i] >= -8.4 else "湾・鼻"))
        label(d, (ox + 6, oy + 4), "c %.1f m（%s）" % (c[i], lay), n=16, bg=(252, 252, 252))
    return S


def main():
    os.makedirs(OUTD, exist_ok=True)
    sheet1().save(OUTD + "/sB_1_painting.png")
    names = ["painting", "seat", "side_left", "side_right", "back65", "top"]
    grid_two_cols(names, CL + "/AS04F_%s_clay.png", CL + "/AS05B_%s_clay.png", "見本05 やり方 B：粘土（形だけ、numpy の z バッファ）",
                  "左 = 見本04（AS04F ＋ wave4）、右 = 見本05 B（AS05B ＋ wave4）。光の向きの陰影だけの灰の粘土。黒い線 = 遮る縁", "見本04", "見本05 B").save(OUTD + "/sB_2_clay.png")
    grid_two_cols(names, CL + "/AS04F_%s_tint.png", CL + "/AS05B_%s_tint.png", "見本05 やり方 B：三つの層の色づけ（numpy）",
                  "① 赤・② 緑・③ 水色・wave4（④）青・ほかの前の面 灰・背 濃い灰。見本04 は c の帯の既定の印、見本05 B は段の行の印（層の間は印を空ける）",
                  "見本04", "見本05 B").save(OUTD + "/sB_3_layers.png")
    azs = list(range(0, 360, 30))
    tt_sheet(CL + "/AS05B_tt%d_clay.png", azs, "見本05 やり方 B：回り台 12 方位の粘土（numpy）", "上の 2 段 = 色づけなし、下の 2 段 = 三つの層の色づけ（① 赤・② 緑・③ 水色・wave4 青）",
             CL + "/AS05B_tt%d_tint.png", "粘土", "層").save(OUTD + "/sB_4_tt_clay.png")
    names_u = ["seat", "seat_toward_wave", "side_left", "side_right", "back65", "top"]
    grid_two_cols(names_u, R04 + "/views/%s_t120_claws.png", RB + "/views/%s_t120_claws.png", "見本05 やり方 B：Unity の材質つき（爪あり）",
                  "左 = 見本04、右 = 見本05 B（白い点なし・唇の下の内の縁を藍）。PC のオフスクリーン描画で、HMD の実機ではない", "見本04", "見本05 B").save(OUTD + "/sB_5_unity_views.png")
    tt_sheet(R04 + "/tt/t120_az%03d_claws.png", azs, "回り台 12 方位（Unity、爪あり）", "上の 2 段 = 見本04、下の 2 段 = 見本05 B",
             RB + "/tt/t120_az%03d_claws.png", "見本04", "見本05 B").save(OUTD + "/sB_6_tt_unity.png")
    sections().save(OUTD + "/sB_7_sections.png")
    print("SHEETS_DONE", OUTD)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
